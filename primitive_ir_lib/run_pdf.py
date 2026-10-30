"""Create one Primitive IR JSON per page of a PDF drawing.

Example:
    python -m primitive_ir_lib.run_pdf --pdf drawing.pdf --output-dir output/pdf_ir \
      --scale-mm-per-px 0.0917 --dpi 144 --merge-lines

    # Không biết tỷ lệ, không muốn tự khoanh ROI OCR:
    python -m primitive_ir_lib.run_pdf --pdf drawing.pdf --output-dir output/pdf_ir \
      --auto-ocr-roi --auto-calibrate --dpi 144
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import fitz
import numpy as np

from .calibration_registry import get_verified_scale
from .geometry_extraction import RawArc, RawLine, RawPdfLine
from .models import new_id
from .run_image import PDF_TEXT_CONFLICT_POLICY_VERSION, run
from .text_extraction import RawText


_CompetingStroke = tuple[tuple[float, float], tuple[float, float], float]
_CompetingStrokeEntry = tuple[
    int,
    tuple[float, float, float, float],
    _CompetingStroke,
]


def _collect_nearby_competing_strokes(
    buckets: dict[tuple[int, int], list[_CompetingStrokeEntry]],
    broad: list[_CompetingStrokeEntry] | tuple[_CompetingStrokeEntry, ...],
    query_cells: set[tuple[int, int]] | None,
    candidate_seqno: int,
    query: tuple[float, float, float, float],
    fallback_entries: list[_CompetingStrokeEntry] | tuple[_CompetingStrokeEntry, ...],
) -> tuple[_CompetingStroke, ...]:
    def overlaps_query(entry: _CompetingStrokeEntry) -> bool:
        seqno, bounds, _ = entry
        return (
            seqno != candidate_seqno
            and bounds[0] <= query[2]
            and bounds[2] >= query[0]
            and bounds[1] <= query[3]
            and bounds[3] >= query[1]
        )

    if query_cells is None:
        return tuple(
            entry[2] for entry in fallback_entries if overlaps_query(entry)
        )

    candidates: set[_CompetingStrokeEntry] = set()
    checked_entry_ids: set[int] = set()
    for entry in broad:
        entry_id = id(entry)
        if entry_id in checked_entry_ids:
            continue
        checked_entry_ids.add(entry_id)
        if overlaps_query(entry):
            candidates.add(entry)
    for cell in query_cells:
        for entry in buckets.get(cell, ()):
            entry_id = id(entry)
            if entry_id in checked_entry_ids:
                continue
            checked_entry_ids.add(entry_id)
            if overlaps_query(entry):
                candidates.add(entry)
    return tuple(entry[2] for entry in candidates)


def _candidate_crop_bbox(
    candidate: dict, width: int, height: int, padding_px: int = 12
) -> tuple[int, int, int, int]:
    boxes = [candidate["bbox_px"], candidate["region_bbox_px"]]
    x0 = max(0, int(min(box[0] for box in boxes)) - padding_px)
    y0 = max(0, int(min(box[1] for box in boxes)) - padding_px)
    x1 = min(width, int(max(box[2] for box in boxes)) + padding_px)
    y1 = min(height, int(max(box[3] for box in boxes)) + padding_px)
    return x0, y0, x1, y1


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _matrix_values(matrix: fitz.Matrix) -> list[float]:
    values = [float(matrix.a), float(matrix.b), float(matrix.c), float(matrix.d), float(matrix.e), float(matrix.f)]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("PDF page transform contains a non-finite value")
    return [round(value, 8) for value in values]


def _page_vector_texts(
    page: fitz.Page,
    pixel_scale: float,
    pixmap_origin: tuple[int, int],
    image_size: tuple[int, int],
) -> tuple[list[RawText], str, int]:
    """Extract embedded PDF spans in the exact page-render pixel frame."""
    if page.rotation not in {0, 90, 180, 270}:
        return [], "unsupported_page_rotation", 0
    try:
        _matrix_values(page.rotation_matrix)
        blocks = page.get_text("dict")["blocks"]
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as exc:
        return [], f"unavailable:{type(exc).__name__}", 0

    width_px, height_px = image_size
    origin_x, origin_y = pixmap_origin
    extracted: list[RawText] = []
    skipped = 0
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                content = span.get("text")
                if not isinstance(content, str) or not content.strip():
                    continue
                try:
                    bbox = tuple(float(value) for value in span["bbox"])
                    if len(bbox) != 4 or not all(math.isfinite(value) for value in bbox):
                        raise ValueError("invalid span bbox")
                    x0, y0, x1, y1 = bbox
                    if x0 >= x1 or y0 >= y1:
                        raise ValueError("degenerate span bbox")
                    transformed = [
                        fitz.Point(x, y) * page.rotation_matrix
                        for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
                    ]
                    left = max(0, math.floor(min(point.x for point in transformed) * pixel_scale - origin_x))
                    top = max(0, math.floor(min(point.y for point in transformed) * pixel_scale - origin_y))
                    right = min(width_px, math.ceil(max(point.x for point in transformed) * pixel_scale - origin_x))
                    bottom = min(height_px, math.ceil(max(point.y for point in transformed) * pixel_scale - origin_y))
                    if left >= right or top >= bottom:
                        raise ValueError("span is outside the rendered page")

                    direction = line.get("dir", (1.0, 0.0))
                    dx, dy = float(direction[0]), float(direction[1])
                    if not math.isfinite(dx) or not math.isfinite(dy) or (dx == 0.0 and dy == 0.0):
                        raise ValueError("invalid span direction")
                    vector_start = fitz.Point(0, 0) * page.rotation_matrix
                    vector_end = fitz.Point(dx, dy) * page.rotation_matrix
                    rotation_deg = math.degrees(
                        math.atan2(-(vector_end.y - vector_start.y), vector_end.x - vector_start.x)
                    )
                    if not math.isfinite(rotation_deg):
                        raise ValueError("invalid transformed span direction")
                except (IndexError, KeyError, TypeError, ValueError, OverflowError):
                    skipped += 1
                    continue

                extracted.append(
                    RawText(
                        id=new_id("pdf-text"),
                        content=content,
                        bbox_px=(left, top, right, bottom),
                        rotation_deg=rotation_deg,
                        confidence=1.0,
                        source="text_pdfvector",
                        semantic_role="unknown",
                    )
                )
    if skipped:
        status = "partial_unsupported_spans" if extracted else "unsupported_spans"
    else:
        status = "available" if extracted else "no_text"
    return extracted, status, skipped


def _boxes_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def _pdf_output_error(path: Path, reason: str) -> ValueError:
    return ValueError(f"Unsafe PDF output {reason}: {path}")


def _is_reparse_point(info: os.stat_result) -> bool:
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & reparse_point
    )


def _same_physical_path(left: Path, right: Path) -> bool:
    try:
        if os.path.samefile(left, right):
            return True
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise _pdf_output_error(left, "identity cannot be verified") from exc
    try:
        return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(
            str(right.resolve(strict=False))
        )
    except (OSError, RuntimeError) as exc:
        raise _pdf_output_error(left, "identity cannot be resolved") from exc


def _validate_pdf_output_directory(output_root: Path, directory: Path) -> None:
    root = Path(os.path.abspath(output_root))
    target = Path(os.path.abspath(directory))
    try:
        if os.path.normcase(str(root.resolve(strict=False))) != os.path.normcase(str(root)):
            raise _pdf_output_error(root, "output root has a redirected ancestor")
    except (OSError, RuntimeError) as exc:
        raise _pdf_output_error(root, "output root identity cannot be resolved") from exc
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise _pdf_output_error(target, "directory escapes its output root") from exc

    current = root
    candidates = [current]
    for part in relative.parts:
        current = current / part
        candidates.append(current)
    for path in candidates:
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise _pdf_output_error(path, "directory cannot be inspected") from exc
        if _is_reparse_point(info):
            raise _pdf_output_error(path, "directory is redirected")
        if not stat.S_ISDIR(info.st_mode):
            raise _pdf_output_error(path, "directory is not a directory")


def _validate_pdf_output_path(
    path: Path,
    output_root: Path,
    source_pdf: Path,
    *,
    atomic_replace: bool = False,
) -> None:
    root = Path(os.path.abspath(output_root))
    target = Path(os.path.abspath(path))
    if _same_physical_path(target, source_pdf):
        raise _pdf_output_error(target, "aliases the source PDF")
    _validate_pdf_output_directory(root, target.parent)
    try:
        info = target.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise _pdf_output_error(target, "file cannot be inspected") from exc

    if _is_reparse_point(info):
        if atomic_replace:
            return
        raise _pdf_output_error(target, "file is redirected")
    if stat.S_ISREG(info.st_mode):
        if getattr(info, "st_nlink", 1) > 1 and not atomic_replace:
            raise _pdf_output_error(target, "file has multiple hard links")
        return
    raise _pdf_output_error(target, "destination is not a regular file")


def _validate_pdf_output_tree(
    output_root: Path, source_pdf: Path, manifest_path: Path
) -> None:
    root = Path(os.path.abspath(output_root))
    manifest_identity_path = os.path.normcase(
        str(Path(os.path.abspath(manifest_path)))
    )
    _validate_pdf_output_directory(root, root)
    if not root.exists():
        return

    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            raise _pdf_output_error(directory, "directory cannot be inspected") from exc
        for entry in entries:
            path = Path(entry.path)
            try:
                info = path.lstat()
            except OSError as exc:
                raise _pdf_output_error(path, "entry cannot be inspected") from exc
            is_manifest = os.path.normcase(str(path)) == manifest_identity_path
            if _same_physical_path(path, source_pdf):
                raise _pdf_output_error(path, "aliases the source PDF")
            if _is_reparse_point(info):
                if is_manifest:
                    continue
                raise _pdf_output_error(path, "entry is redirected")
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
            elif stat.S_ISREG(info.st_mode):
                if getattr(info, "st_nlink", 1) > 1 and not is_manifest:
                    raise _pdf_output_error(path, "file has multiple hard links")
            else:
                raise _pdf_output_error(path, "entry is not a regular file or directory")


def _directory_identity(path: Path) -> tuple[int, int]:
    try:
        info = path.stat()
    except OSError as exc:
        raise _pdf_output_error(path, "parent directory identity cannot be verified") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise _pdf_output_error(path, "parent is not a directory")
    return info.st_dev, info.st_ino


def _pdf_output_identity(path: Path) -> tuple[int, int] | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        return None
    return info.st_dev, info.st_ino


def _cleanup_owned_pdf_output_temp(
    temporary: Path, expected_identity: tuple[int, int]
) -> None:
    if _pdf_output_identity(temporary) == expected_identity:
        temporary.unlink(missing_ok=True)


def _create_pdf_output_temp(
    destination: Path, output_root: Path, source_pdf: Path
) -> tuple[Path, tuple[int, int], int, tuple[int, int]]:
    _validate_pdf_output_path(destination, output_root, source_pdf)
    _validate_pdf_output_directory(output_root, destination.parent)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _validate_pdf_output_directory(output_root, destination.parent)
    parent_identity = _directory_identity(destination.parent)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.stem}.",
        suffix=destination.suffix,
        dir=destination.parent,
    )
    temporary = Path(name)
    created_stat = os.fstat(descriptor)
    created_identity = (created_stat.st_dev, created_stat.st_ino)
    try:
        if _directory_identity(destination.parent) != parent_identity:
            raise _pdf_output_error(
                destination.parent, "parent changed during temporary creation"
            )
        _validate_pdf_output_path(temporary, output_root, source_pdf)
    except Exception:
        os.close(descriptor)
        _cleanup_owned_pdf_output_temp(temporary, created_identity)
        raise
    # Keep the exclusive mkstemp handle open while pathname-based artifact
    # writers run. On the supported Windows filesystem, that prevents another
    # process from unlinking/replacing this entry with a symlink before a
    # writer opens the path. Close only after the writer finishes; publication
    # itself remains the existing atomic replace step.
    return temporary, parent_identity, descriptor, created_identity


def _descriptor_sha256(descriptor: int) -> tuple[os.stat_result, int, str]:
    before = os.fstat(descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or getattr(before, "st_nlink", 1) != 1
        or getattr(before, "st_file_attributes", 0) & 0x0400
    ):
        raise ValueError("PDF artifact writer output is not a single-link regular file.")
    original_offset = os.lseek(descriptor, 0, os.SEEK_CUR)
    digest = hashlib.sha256()
    size = 0
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    finally:
        os.lseek(descriptor, original_offset, os.SEEK_SET)
    after = os.fstat(descriptor)
    if (
        not os.path.samestat(before, after)
        or before.st_size != after.st_size
        or size != after.st_size
    ):
        raise ValueError("PDF artifact changed while its writer output was being bound.")
    return after, size, digest.hexdigest()


def _verify_published_pdf_output(
    destination: Path,
    expected_stat: os.stat_result,
    expected_size: int,
    expected_sha256: str,
) -> None:
    from cad_agent.file_integrity import assert_path_identity, open_bound_file

    descriptor, published_stat = open_bound_file(
        destination,
        flags=os.O_RDONLY | getattr(os, "O_BINARY", 0),
        label="PDF artifact",
    )
    try:
        if not os.path.samestat(expected_stat, published_stat):
            raise ValueError("Published PDF artifact is not the writer-owned file.")
        actual_stat, actual_size, actual_sha256 = _descriptor_sha256(descriptor)
        if (
            not os.path.samestat(expected_stat, actual_stat)
            or actual_size != expected_size
            or actual_sha256 != expected_sha256
        ):
            raise ValueError("Published PDF artifact does not match writer-bound bytes.")
        assert_path_identity(destination, actual_stat, label="PDF artifact")
    finally:
        os.close(descriptor)


def _publish_pdf_output_temp(
    temporary: Path,
    destination: Path,
    output_root: Path,
    source_pdf: Path,
    parent_identity: tuple[int, int],
    expected_stat: os.stat_result,
    expected_size: int,
    expected_sha256: str,
) -> None:
    _validate_pdf_output_path(destination, output_root, source_pdf)
    _validate_pdf_output_path(temporary, output_root, source_pdf)
    if _directory_identity(destination.parent) != parent_identity:
        raise _pdf_output_error(destination.parent, "parent changed before publication")
    from cad_agent.file_integrity import open_bound_file

    descriptor, temporary_stat = open_bound_file(
        temporary,
        flags=os.O_RDONLY | getattr(os, "O_BINARY", 0),
        label="PDF temporary artifact",
    )
    try:
        if not os.path.samestat(expected_stat, temporary_stat):
            raise ValueError("PDF temporary artifact is not the writer-owned file.")
        actual_stat, actual_size, actual_sha256 = _descriptor_sha256(descriptor)
        if (
            not os.path.samestat(expected_stat, actual_stat)
            or actual_size != expected_size
            or actual_sha256 != expected_sha256
        ):
            raise ValueError("PDF temporary artifact does not match writer-bound bytes.")
    finally:
        os.close(descriptor)
    os.replace(temporary, destination)
    _validate_pdf_output_path(destination, output_root, source_pdf)
    _verify_published_pdf_output(destination, expected_stat, expected_size, expected_sha256)


def _write_pdf_output(
    destination: Path,
    output_root: Path,
    source_pdf: Path,
    writer,
) -> None:
    from cad_agent.file_integrity import pin_directory_chain

    output_parent = Path(os.path.abspath(destination.parent))
    with pin_directory_chain(output_parent):
        temporary, parent_identity, descriptor, created_identity = _create_pdf_output_temp(
            destination, output_root, source_pdf
        )
        try:
            result = writer(temporary)
            if result is False:
                raise ValueError(f"PDF artifact writer rejected destination: {destination}")
            expected_stat, expected_size, expected_sha256 = _descriptor_sha256(descriptor)
            os.close(descriptor)
            descriptor = -1
            _publish_pdf_output_temp(
                temporary,
                destination,
                output_root,
                source_pdf,
                parent_identity,
                expected_stat,
                expected_size,
                expected_sha256,
            )
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            _cleanup_owned_pdf_output_temp(temporary, created_identity)


def _materialize_view_children(
    candidates: list[dict],
    rendered_path: Path,
    output_dir: Path,
    source_pdf: Path,
    page_number: int,
    preset: str,
    merge_lines: bool,
) -> None:
    """Create review-only child IRs for non-overlapping evidenced candidates."""
    evidenced = [candidate for candidate in candidates if candidate.get("dimension_evidence")]
    if not evidenced:
        return

    import cv2

    image = cv2.imread(str(rendered_path))
    if image is None:
        raise ValueError(f"Cannot read rendered page for view child IR: {rendered_path}")
    height, width = image.shape[:2]
    accepted_boxes: list[tuple[int, int, int, int]] = []
    child_root = output_dir / "view_ir" / f"page_{page_number:02d}"
    for index, candidate in enumerate(evidenced, start=1):
        bbox = _candidate_crop_bbox(candidate, width, height)
        if any(_boxes_overlap(bbox, other) for other in accepted_boxes):
            candidate["child_state"] = "skipped_overlap"
            continue
        x0, y0, x1, y1 = bbox
        if x1 <= x0 or y1 <= y0:
            candidate["child_state"] = "skipped_invalid_bbox"
            continue
        accepted_boxes.append(bbox)
        _validate_pdf_output_directory(output_dir, child_root)
        child_root.mkdir(parents=True, exist_ok=True)
        _validate_pdf_output_directory(output_dir, child_root)
        child_image = child_root / f"view_{index:02d}.png"
        child_ir = child_root / f"view_{index:02d}.json"
        _write_pdf_output(
            child_image,
            output_dir,
            source_pdf,
            lambda path: cv2.imwrite(str(path), image[y0:y1, x0:x1]),
        )
        child_image_sha256 = hashlib.sha256(child_image.read_bytes()).hexdigest()
        _write_pdf_output(
            child_ir,
            output_dir,
            source_pdf,
            lambda path: run(
                image_path=str(child_image),
                output_path=str(path),
                scale_mm_per_px=float(candidate["pixel_to_unit_scale"]),
                preset=preset,
                merge_lines=merge_lines,
                auto_ocr_roi=True,
                calibration_status="needs_verification",
                calibration_source_sha256=child_image_sha256,
            ),
        )
        candidate["child_ir"] = str(child_ir.relative_to(output_dir)).replace("\\", "/")
        candidate["child_image"] = str(child_image.relative_to(output_dir)).replace("\\", "/")
        candidate["child_bbox_px"] = [x0, y0, x1, y1]
        candidate["child_calibration_status"] = "needs_verification"
        candidate["child_state"] = "needs_verification"
        candidate["child_image_sha256"] = child_image_sha256
        candidate["child_ir_sha256"] = hashlib.sha256(child_ir.read_bytes()).hexdigest()


def _configure_console_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _is_valid_manual_scale(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and value > 0
    except OverflowError:
        return False


def _colors_match(left: object, right: object) -> Optional[bool]:
    """Compare RGB colors conservatively, returning None for unknown values."""
    try:
        left_rgb = np.asarray(left, dtype=np.float64)
        right_rgb = np.asarray(right, dtype=np.float64)
    except (TypeError, ValueError):
        return None
    if (
        left_rgb.shape != (3,)
        or right_rgb.shape != (3,)
        or not np.all(np.isfinite(left_rgb))
        or not np.all(np.isfinite(right_rgb))
    ):
        return None
    return bool(float(np.max(np.abs(left_rgb - right_rgb))) <= 0.08)


def _fit_full_circle_path(
    drawing: dict, background: Optional[np.ndarray]
) -> Optional[tuple[float, float, float]]:
    """Return geometry only when a closed cubic circle contrasts with known paper."""
    if (
        drawing.get("type") != "s"
        or drawing.get("fill") is not None
        or drawing.get("color") is None
        or not math.isfinite(float(drawing.get("width", math.nan)))
        or drawing.get("width", -1) < 0
        or abs(float(drawing.get("stroke_opacity", 0.0)) - 1.0) > 1e-9
        or drawing.get("blendmode") not in {None, "Normal"}
        or str(drawing.get("dashes", "")).strip() not in {"[] 0", "[] 0.0"}
    ):
        return None
    if background is None or _colors_match(drawing.get("color"), background) is not False:
        return None

    items = drawing.get("items", [])
    if len(items) < 3 or any(item[0] != "c" for item in items):
        return None

    samples: list[tuple[float, float]] = []
    endpoints: list[tuple[float, float]] = []
    previous_end: Optional[fitz.Point] = None
    for item in items:
        _, p0, p1, p2, p3 = item
        if (
            previous_end is not None
            and math.hypot(p0.x - previous_end.x, p0.y - previous_end.y) > 0.02
        ):
            return None
        previous_end = p3
        endpoints.append((p0.x, p0.y))
        for t in (0.25, 0.5, 0.75):
            u = 1.0 - t
            x = u**3 * p0.x + 3 * u**2 * t * p1.x + 3 * u * t**2 * p2.x + t**3 * p3.x
            y = u**3 * p0.y + 3 * u**2 * t * p1.y + 3 * u * t**2 * p2.y + t**3 * p3.y
            samples.append((x, y))
    if (
        previous_end is None
        or math.hypot(endpoints[0][0] - previous_end.x, endpoints[0][1] - previous_end.y) > 0.02
    ):
        return None

    points = np.asarray(samples + endpoints, dtype=np.float64)
    matrix = np.column_stack((points[:, 0], points[:, 1], np.ones(len(points))))
    target = -(points[:, 0] ** 2 + points[:, 1] ** 2)
    try:
        a, b, c = np.linalg.lstsq(matrix, target, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    center_x, center_y = -a / 2.0, -b / 2.0
    radius_squared = center_x**2 + center_y**2 - c
    if not math.isfinite(radius_squared) or radius_squared <= 0:
        return None
    radius = math.sqrt(radius_squared)
    radial_errors = np.abs(np.hypot(points[:, 0] - center_x, points[:, 1] - center_y) - radius)
    if float(np.max(radial_errors)) > max(0.25, radius * 0.001):
        return None

    angles = [math.atan2(y - center_y, x - center_x) for x, y in endpoints]
    deltas = [
        math.atan2(math.sin(b - a), math.cos(b - a))
        for a, b in zip(angles, angles[1:] + angles[:1])
    ]
    if not (all(delta > 0 for delta in deltas) or all(delta < 0 for delta in deltas)):
        return None
    if abs(sum(abs(delta) for delta in deltas) - 2.0 * math.pi) > 0.02:
        return None
    return center_x, center_y, radius


def _fit_full_line_circle_path(
    drawing: dict, background: Optional[np.ndarray]
) -> Optional[tuple[float, float, float]]:
    """Return a visible circle fit for one continuous, closed, line-only path."""
    if (
        drawing.get("type") != "s"
        or drawing.get("fill") is not None
        or drawing.get("color") is None
        or not math.isfinite(float(drawing.get("width", math.nan)))
        or drawing.get("width", -1) < 0
        or abs(float(drawing.get("stroke_opacity", 0.0)) - 1.0) > 1e-9
        or str(drawing.get("dashes", "")).strip() not in {"[] 0", "[] 0.0"}
        or background is None
        or _colors_match(drawing.get("color"), background) is not False
    ):
        return None

    items = drawing.get("items", [])
    if len(items) < 8 or any(item[0] != "l" for item in items):
        return None

    starts: list[fitz.Point] = []
    ends: list[fitz.Point] = []
    lengths: list[float] = []
    directions: list[float] = []
    previous_end: Optional[fitz.Point] = None
    for item in items:
        _, start, end = item
        if (
            previous_end is not None
            and math.hypot(start.x - previous_end.x, start.y - previous_end.y) > 0.02
        ):
            return None
        dx, dy = end.x - start.x, end.y - start.y
        length = math.hypot(dx, dy)
        if not math.isfinite(length) or length <= 0.02:
            return None
        starts.append(start)
        ends.append(end)
        lengths.append(length)
        directions.append(math.atan2(dy, dx))
        previous_end = end

    if (
        previous_end is None
        or math.hypot(starts[0].x - previous_end.x, starts[0].y - previous_end.y) > 0.02
    ):
        return None

    signed_turns = [
        math.atan2(
            math.sin(next_direction - direction),
            math.cos(next_direction - direction),
        )
        for direction, next_direction in zip(directions, directions[1:] + directions[:1])
    ]
    if (
        not signed_turns
        or not (
            all(turn > 1e-6 for turn in signed_turns) or all(turn < -1e-6 for turn in signed_turns)
        )
        or max(abs(turn) for turn in signed_turns) > math.radians(45.0)
        or abs(abs(sum(signed_turns)) - 2.0 * math.pi) > 0.02
        or min(lengths) < float(np.median(lengths)) * 0.65
        or max(lengths) > float(np.median(lengths)) * 3.0
    ):
        return None

    # Fit vertices and points along each chord so a coarse polygon or a closing
    # chord cannot masquerade as a circle merely because its vertices are close.
    samples: list[tuple[float, float]] = []
    for start, end in zip(starts, ends):
        for fraction in (0.0, 0.25, 0.5, 0.75):
            samples.append(
                (
                    start.x + fraction * (end.x - start.x),
                    start.y + fraction * (end.y - start.y),
                )
            )
    points = np.asarray(samples, dtype=np.float64)
    if not np.all(np.isfinite(points)):
        return None
    matrix = np.column_stack((points[:, 0], points[:, 1], np.ones(len(points))))
    target = -(points[:, 0] ** 2 + points[:, 1] ** 2)
    try:
        a, b, c = np.linalg.lstsq(matrix, target, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    center_x, center_y = -a / 2.0, -b / 2.0
    radius_squared = center_x**2 + center_y**2 - c
    if not math.isfinite(radius_squared) or radius_squared <= 0:
        return None
    radius = math.sqrt(radius_squared)
    radial_errors = np.abs(np.hypot(points[:, 0] - center_x, points[:, 1] - center_y) - radius)
    stroke_width = float(drawing.get("width") or 0.0)
    if (
        not math.isfinite(stroke_width)
        or stroke_width < 0.0
        or float(np.max(radial_errors)) > max(0.18, min(stroke_width * 0.25, radius * 0.005))
    ):
        return None
    return center_x, center_y, radius


def _is_closed_line_contour(drawing: dict) -> bool:
    """Identify one connected closed line-only path for local witness checking."""
    if drawing.get("type") != "s" or drawing.get("fill") is not None:
        return False
    items = drawing.get("items", [])
    if not items or any(item[0] != "l" for item in items):
        return False

    first_start: Optional[fitz.Point] = None
    previous_end: Optional[fitz.Point] = None
    for item in items:
        _, start, end = item
        if first_start is None:
            first_start = start
        if (
            previous_end is not None
            and math.hypot(start.x - previous_end.x, start.y - previous_end.y) > 0.02
        ):
            return False
        dx, dy = end.x - start.x, end.y - start.y
        if math.hypot(dx, dy) <= 0.02:
            return False
        previous_end = end
    if (
        first_start is None
        or previous_end is None
        or math.hypot(first_start.x - previous_end.x, first_start.y - previous_end.y) > 0.02
    ):
        return False
    return True


def _fit_open_line_circle_arc(
    drawing: dict,
) -> Optional[tuple[float, float, float]]:
    """Recognize a circle-like open polyline that must remain only a suspect."""
    if (
        drawing.get("type") != "s"
        or drawing.get("fill") is not None
        or drawing.get("color") is None
        or not math.isfinite(float(drawing.get("width", math.nan)))
        or drawing.get("width", -1) < 0
        or float(drawing.get("stroke_opacity", 0.0)) <= 0.0
    ):
        return None
    items = drawing.get("items", [])
    if len(items) < 8 or any(item[0] != "l" for item in items):
        return None

    starts: list[fitz.Point] = []
    ends: list[fitz.Point] = []
    lengths: list[float] = []
    directions: list[float] = []
    previous_end: Optional[fitz.Point] = None
    for item in items:
        _, start, end = item
        if (
            previous_end is not None
            and math.hypot(start.x - previous_end.x, start.y - previous_end.y) > 0.02
        ):
            return None
        dx, dy = end.x - start.x, end.y - start.y
        length = math.hypot(dx, dy)
        if not math.isfinite(length) or length <= 0.02:
            return None
        starts.append(start)
        ends.append(end)
        lengths.append(length)
        directions.append(math.atan2(dy, dx))
        previous_end = end

    if (
        previous_end is None
        or math.hypot(starts[0].x - previous_end.x, starts[0].y - previous_end.y) <= 0.02
    ):
        return None

    turns = [
        math.atan2(math.sin(next_direction - direction), math.cos(next_direction - direction))
        for direction, next_direction in zip(directions, directions[1:])
    ]
    sweep = sum(abs(turn) for turn in turns)
    if (
        not turns
        or not (all(turn > 1e-6 for turn in turns) or all(turn < -1e-6 for turn in turns))
        or max(abs(turn) for turn in turns) > math.radians(45.0)
        or not math.radians(15.0) <= sweep < 2.0 * math.pi - 0.02
        or max(lengths) > float(np.median(lengths)) * 3.0
    ):
        return None

    samples: list[tuple[float, float]] = []
    for start, end in zip(starts, ends):
        for fraction in (0.0, 0.25, 0.5, 0.75):
            samples.append(
                (
                    start.x + fraction * (end.x - start.x),
                    start.y + fraction * (end.y - start.y),
                )
            )
    points = np.asarray(samples, dtype=np.float64)
    matrix = np.column_stack((points[:, 0], points[:, 1], np.ones(len(points))))
    target = -(points[:, 0] ** 2 + points[:, 1] ** 2)
    try:
        a, b, c = np.linalg.lstsq(matrix, target, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    center_x, center_y = -a / 2.0, -b / 2.0
    radius_squared = center_x**2 + center_y**2 - c
    if not math.isfinite(radius_squared) or radius_squared <= 0.0:
        return None
    radius = math.sqrt(radius_squared)
    radial_errors = np.abs(
        np.hypot(points[:, 0] - center_x, points[:, 1] - center_y) - radius
    )
    stroke_width = float(drawing.get("width") or 0.0)
    if (
        not math.isfinite(stroke_width)
        or stroke_width <= 0.0
        or float(np.max(radial_errors))
        > max(0.18, min(stroke_width * 0.25, radius * 0.005))
    ):
        return None
    return center_x, center_y, radius


def _open_line_curve_fragment(
    drawing: dict,
) -> Optional[tuple[list[tuple], list[float], int, tuple]]:
    """Describe a visible open line path fragment with one smooth turn direction."""
    if (
        drawing.get("type") != "s"
        or drawing.get("fill") is not None
        or drawing.get("color") is None
        or not math.isfinite(float(drawing.get("width", math.nan)))
        or drawing.get("width", -1) < 0
        or float(drawing.get("stroke_opacity", 0.0)) <= 0.0
    ):
        return None
    items = drawing.get("items", [])
    if len(items) < 2 or any(item[0] != "l" for item in items):
        return None

    directions: list[float] = []
    previous_end: Optional[fitz.Point] = None
    first_start: Optional[fitz.Point] = None
    for item in items:
        _, start, end = item
        if first_start is None:
            first_start = start
        if previous_end is not None and math.hypot(
            start.x - previous_end.x, start.y - previous_end.y
        ) > 0.02:
            return None
        dx, dy = end.x - start.x, end.y - start.y
        length = math.hypot(dx, dy)
        if not math.isfinite(length) or length <= 0.02:
            return None
        directions.append(math.atan2(dy, dx))
        previous_end = end

    if (
        first_start is None
        or previous_end is None
        or math.hypot(first_start.x - previous_end.x, first_start.y - previous_end.y) <= 0.02
    ):
        return None
    turns = [
        math.atan2(math.sin(next_direction - direction), math.cos(next_direction - direction))
        for direction, next_direction in zip(directions, directions[1:])
    ]
    if (
        not turns
        or not (all(turn > 1e-6 for turn in turns) or all(turn < -1e-6 for turn in turns))
        or max(abs(turn) for turn in turns) > math.radians(45.0)
    ):
        return None

    color = drawing["color"]
    style = (
        tuple(color) if isinstance(color, (tuple, list)) else color,
        float(drawing["width"]),
        float(drawing["stroke_opacity"]),
        drawing.get("dashes"),
    )
    return items, directions, 1 if turns[0] > 0.0 else -1, style


def _is_materially_curved_open_line_contour(drawing: dict) -> bool:
    """Recognize long, smooth open curves even when they are not circles."""
    fragment = _open_line_curve_fragment(drawing)
    if fragment is None:
        return False
    items, directions, _, _ = fragment
    if len(items) < 8:
        return False

    turns = [
        math.atan2(math.sin(next_direction - direction), math.cos(next_direction - direction))
        for direction, next_direction in zip(directions, directions[1:])
    ]
    lengths = [math.hypot(item[2].x - item[1].x, item[2].y - item[1].y) for item in items]
    return (
        sum(abs(turn) for turn in turns) >= math.radians(15.0)
        and max(lengths) <= float(np.median(lengths)) * 3.0
    )


def _collect_open_line_curve_suspects(drawings: list[dict]) -> list[dict]:
    """Join adjacent, style-matched open curves as circle or contour suspects."""
    suspects: list[dict] = []
    chain: list[dict] = []
    chain_style: Optional[tuple] = None
    chain_turn: Optional[int] = None
    chain_end: Optional[fitz.Point] = None
    chain_direction: Optional[float] = None

    def finish_chain() -> None:
        if not chain:
            return
        merged = dict(chain[0])
        merged["items"] = [item for fragment in chain for item in fragment["items"]]
        merged["closePath"] = False
        if (
            _fit_open_line_circle_arc(merged) is not None
            or _is_materially_curved_open_line_contour(merged)
        ):
            suspects.append(merged)

    for drawing in drawings:
        fragment = _open_line_curve_fragment(drawing)
        if fragment is None or _fit_open_line_circle_arc(drawing) is not None:
            finish_chain()
            chain = []
            chain_style = None
            chain_turn = None
            chain_end = None
            chain_direction = None
            continue

        items, directions, turn_sign, style = fragment
        fragment_end = items[-1][2]
        fragment_start = items[0][1]
        compatible = False
        if chain:
            boundary_turn = math.atan2(
                math.sin(directions[0] - chain_direction),
                math.cos(directions[0] - chain_direction),
            )
            compatible = (
                style == chain_style
                and chain_turn == turn_sign
                and math.hypot(fragment_start.x - chain_end.x, fragment_start.y - chain_end.y)
                <= 0.02
                and abs(boundary_turn) > 1e-6
                and abs(boundary_turn) <= math.radians(45.0)
                and (1 if boundary_turn > 0.0 else -1) == chain_turn
            )
        if chain and not compatible:
            finish_chain()
            chain = []
        if not chain:
            chain = [drawing]
            chain_style = style
            chain_turn = turn_sign
        else:
            chain.append(drawing)
        chain_end = fragment_end
        chain_direction = directions[-1]

    finish_chain()
    return suspects


def _single_line_record_paths(drawings: list[dict]) -> list[tuple[int, int, dict, bool]]:
    """Join only consecutive, style-matched one-line records at exact endpoints."""
    paths: list[tuple[int, int, dict, bool]] = []
    chain: list[tuple[int, dict]] = []
    chain_style: Optional[tuple] = None
    chain_end: Optional[fitz.Point] = None

    def style_for(drawing: dict) -> Optional[tuple]:
        if (
            drawing.get("type") != "s"
            or drawing.get("fill") is not None
            or drawing.get("color") is None
            or not math.isfinite(float(drawing.get("width", math.nan)))
            or drawing.get("width", -1) < 0
            or float(drawing.get("stroke_opacity", 0.0)) <= 0.0
            or len(drawing.get("items", [])) != 1
            or drawing["items"][0][0] != "l"
            or drawing.get("seqno") is None
        ):
            return None
        color = drawing["color"]
        color_key = tuple(color) if isinstance(color, (tuple, list)) else color
        scissor = drawing.get("scissor")
        scissor_key = tuple(scissor) if scissor is not None else None
        line_cap = drawing.get("lineCap")
        line_cap_key = tuple(line_cap) if isinstance(line_cap, (tuple, list)) else line_cap
        return (
            color_key,
            float(drawing["width"]),
            float(drawing.get("stroke_opacity", 0.0)),
            drawing.get("dashes"),
            line_cap_key,
            drawing.get("lineJoin"),
            int(drawing.get("level") or 0),
            drawing.get("layer"),
            scissor_key,
        )

    def finish_chain() -> None:
        nonlocal chain, chain_style, chain_end
        if len(chain) < 8:
            chain = []
            chain_style = None
            chain_end = None
            return
        items = [record["items"][0] for _, record in chain]
        merged = dict(chain[0][1])
        merged["items"] = items
        merged["seqno"] = chain[-1][1].get("seqno")
        merged["closePath"] = False
        points = [point for item in items for point in item[1:]]
        merged["rect"] = fitz.Rect(
            min(point.x for point in points),
            min(point.y for point in points),
            max(point.x for point in points),
            max(point.y for point in points),
        )
        closed = math.hypot(items[0][1].x - items[-1][2].x, items[0][1].y - items[-1][2].y) <= 0.02
        if closed or _fit_open_line_circle_arc(merged) is not None or _is_materially_curved_open_line_contour(merged):
            paths.append((chain[0][0], chain[-1][0], merged, closed))
        chain = []
        chain_style = None
        chain_end = None

    for index, drawing in enumerate(drawings):
        style = style_for(drawing)
        if style is None:
            finish_chain()
            continue
        _, start, end = drawing["items"][0]
        length = math.hypot(end.x - start.x, end.y - start.y)
        if not math.isfinite(length) or length <= 0.02:
            finish_chain()
            continue

        compatible = bool(chain) and (
            style == chain_style
            and int(drawing["seqno"]) == int(chain[-1][1]["seqno"]) + 1
            and chain_end is not None
            and math.hypot(start.x - chain_end.x, start.y - chain_end.y) <= 0.02
        )
        if chain and not compatible:
            finish_chain()
        if not chain:
            chain_style = style
        chain.append((index, drawing))
        chain_end = end

        first_start = chain[0][1]["items"][0][1]
        if len(chain) >= 8 and math.hypot(end.x - first_start.x, end.y - first_start.y) <= 0.02:
            finish_chain()

    finish_chain()
    return paths


def _suspect_geometry(drawing: dict, pixel_scale: float, page_transform: fitz.Matrix) -> dict:
    """Preserve supported path and paint footprints instead of using bounds alone."""
    segments: list[tuple[float, float, float, float]] = []
    fill_polygons: list[list[tuple[float, float]]] = []
    unsupported_item = False
    pending_path: list[tuple[float, float]] = []
    close_subpaths = drawing.get("type") in {"f", "fs"} or bool(drawing.get("closePath"))

    def to_pixel(point: tuple[float, float]) -> tuple[float, float]:
        transformed = fitz.Point(point) * page_transform
        return transformed.x * pixel_scale, transformed.y * pixel_scale

    def finish_path(*, close: bool) -> None:
        nonlocal pending_path
        if len(pending_path) < 2:
            pending_path = []
            return
        first = pending_path[0]
        last = pending_path[-1]
        is_closed = math.hypot(last[0] - first[0], last[1] - first[1]) <= 0.02
        if close and not is_closed:
            pending_path.append(first)
            is_closed = True
        segments.extend(
            (*to_pixel((x0, y0)), *to_pixel((x1, y1)))
            for (x0, y0), (x1, y1) in zip(pending_path, pending_path[1:])
        )
        if is_closed:
            fill_polygons.append([to_pixel(point) for point in pending_path[:-1]])
        pending_path = []

    for item in drawing.get("items", []):
        if item[0] == "l":
            _, start, end = item
            points = [(start.x, start.y), (end.x, end.y)]
        elif item[0] == "c":
            _, p0, p1, p2, p3 = item
            points = []
            for step in range(33):
                t = step / 32.0
                u = 1.0 - t
                points.append(
                    (
                        u**3 * p0.x + 3 * u**2 * t * p1.x + 3 * u * t**2 * p2.x + t**3 * p3.x,
                        u**3 * p0.y + 3 * u**2 * t * p1.y + 3 * u * t**2 * p2.y + t**3 * p3.y,
                    )
                )
        elif item[0] == "re":
            rect = item[1]
            finish_path(close=close_subpaths)
            points = [
                (rect.x0, rect.y0),
                (rect.x1, rect.y0),
                (rect.x1, rect.y1),
                (rect.x0, rect.y1),
                (rect.x0, rect.y0),
            ]
            pending_path = points
            finish_path(close=True)
            continue
        elif item[0] == "qu":
            quad = item[1]
            finish_path(close=close_subpaths)
            quad_points = [quad.ul, quad.ur, quad.lr, quad.ll]
            points = [(point.x, point.y) for point in quad_points]
            points.append(points[0])
            pending_path = points
            finish_path(close=True)
            continue
        else:
            finish_path(close=close_subpaths)
            unsupported_item = True
            continue
        if (
            pending_path
            and math.hypot(
                pending_path[-1][0] - points[0][0],
                pending_path[-1][1] - points[0][1],
            )
            > 0.02
        ):
            finish_path(close=close_subpaths)
        if pending_path:
            pending_path.extend(points[1:])
        else:
            pending_path = points
    finish_path(close=close_subpaths)

    result = {
        "segments": segments,
        "stroke_radius_px": (
            max(0.0, float(drawing.get("width") or 0.0) * pixel_scale / 2.0)
            if drawing.get("type") in {"s", "fs"}
            else 0.0
        ),
    }
    if drawing.get("type") in {"f", "fs"} and drawing.get("fill") is not None:
        result["fill_polygons"] = fill_polygons
        result["fill_even_odd"] = bool(drawing.get("even_odd"))
    if unsupported_item:
        rect = drawing.get("rect")
        if rect is not None:
            corners = [
                to_pixel((rect.x0, rect.y0)),
                to_pixel((rect.x1, rect.y0)),
                to_pixel((rect.x1, rect.y1)),
                to_pixel((rect.x0, rect.y1)),
            ]
            result["bounds"] = (
                min(point[0] for point in corners),
                min(point[1] for point in corners),
                max(point[0] for point in corners),
                max(point[1] for point in corners),
            )
    return result


def _page_background_color(page: fitz.Page) -> Optional[np.ndarray]:
    """Estimate a uniform page background from low-resolution corner samples."""
    pixmap = page.get_pixmap(matrix=fitz.Matrix(0.1, 0.1), alpha=False)
    if pixmap.width < 2 or pixmap.height < 2:
        return None
    pixels = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )[:, :, :3]
    corners = (
        np.asarray(
            (pixels[0, 0], pixels[0, -1], pixels[-1, 0], pixels[-1, -1]),
            dtype=np.float64,
        )
        / 255.0
    )
    background = np.median(corners, axis=0)
    if float(np.max(np.linalg.norm(corners - background, axis=1))) > 0.08:
        return None
    return background


def _drawing_may_erase_circle(
    drawing: dict, witness_color: object, witness_stroke_width: object
) -> bool:
    """Treat fills, contrasting strokes, and wider same-color strokes as occluders."""
    drawing_type = drawing.get("type")
    if drawing_type in {"f", "fs"} and drawing.get("fill") is not None:
        # A same-color opaque fill can hide part of the perimeter just as
        # effectively as a contrasting fill; color equality is not visibility.
        return True
    stroke_color = drawing.get("color") if drawing_type in {"s", "fs"} else None
    if stroke_color is None:
        return True
    if _colors_match(stroke_color, witness_color) is not True:
        return True
    if drawing_type in {"s", "fs"}:
        try:
            later_stroke_width = drawing.get("width")
            if later_stroke_width is None or witness_stroke_width is None:
                return True
            if isinstance(later_stroke_width, bool) or isinstance(witness_stroke_width, bool):
                return True
            later_stroke_width = float(later_stroke_width)
            witness_stroke_width = float(witness_stroke_width)
        except (OverflowError, TypeError, ValueError):
            return True
        if (
            not math.isfinite(later_stroke_width)
            or not math.isfinite(witness_stroke_width)
            or later_stroke_width < 0.0
            or witness_stroke_width < 0.0
        ):
            return True
        # Width alone cannot prove visibility. Only a same-color stroke no
        # wider than the witness receives the thin-stroke exemption; otherwise
        # the existing path/radial-intersection checks must evaluate it.
        return later_stroke_width > witness_stroke_width + 1e-6
    return False


def _axis_aligned_clip_rect(drawing: dict) -> Optional[fitz.Rect]:
    """Return clip bounds only when its actual path is a closed axis-aligned rectangle."""
    scissor = drawing.get("scissor")
    items = drawing.get("items", [])
    if drawing.get("type") != "clip" or scissor is None:
        return None

    if len(items) == 1 and isinstance(items[0], (tuple, list)) and items[0][0] == "re":
        try:
            clip_rect = fitz.Rect(items[0][1])
        except (IndexError, TypeError, ValueError, OverflowError):
            return None
        if not clip_rect.is_valid or not all(math.isfinite(value) for value in clip_rect):
            return None
        try:
            scissor_rect = fitz.Rect(scissor)
        except (TypeError, ValueError, OverflowError):
            return None
        return clip_rect if scissor_rect.is_valid and all(math.isfinite(value) for value in scissor_rect) else None

    if len(items) == 1 and isinstance(items[0], (tuple, list)) and items[0][0] == "qu":
        try:
            quad = items[0][1]
            points = (quad.ul, quad.ur, quad.lr, quad.ll)
            coordinates = tuple((float(point.x), float(point.y)) for point in points)
            if not all(math.isfinite(value) for point in coordinates for value in point):
                return None
            x0 = min(point[0] for point in coordinates)
            y0 = min(point[1] for point in coordinates)
            x1 = max(point[0] for point in coordinates)
            y1 = max(point[1] for point in coordinates)
            expected_corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
            unmatched = list(expected_corners)
            for point in coordinates:
                matches = [
                    index for index, corner in enumerate(unmatched)
                    if abs(point[0] - corner[0]) <= 0.02
                    and abs(point[1] - corner[1]) <= 0.02
                ]
                if len(matches) != 1:
                    return None
                unmatched.pop(matches[0])
            clip_rect = fitz.Rect(x0, y0, x1, y1)
            scissor_rect = fitz.Rect(scissor)
        except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
            return None
        if (
            not clip_rect.is_valid
            or clip_rect.is_empty
            or not all(math.isfinite(value) for value in clip_rect)
            or not scissor_rect.is_valid
            or not all(math.isfinite(value) for value in scissor_rect)
        ):
            return None
        return clip_rect

    if len(items) != 4:
        return None

    segments: list[tuple[fitz.Point, fitz.Point]] = []
    for item in items:
        if not isinstance(item, (tuple, list)) or len(item) != 3 or item[0] != "l":
            return None
        _, start, end = item
        if any(not math.isfinite(value) for value in (start.x, start.y, end.x, end.y)):
            return None
        if abs(start.x - end.x) > 0.02 and abs(start.y - end.y) > 0.02:
            return None
        segments.append((start, end))
    if any(
        math.hypot(
            segments[index][1].x - segments[(index + 1) % 4][0].x,
            segments[index][1].y - segments[(index + 1) % 4][0].y,
        )
        > 0.02
        for index in range(4)
    ):
        return None

    points = [point for segment in segments for point in segment]
    x0 = min(point.x for point in points)
    y0 = min(point.y for point in points)
    x1 = max(point.x for point in points)
    y1 = max(point.y for point in points)
    expected_corners = {
        (round(x0, 3), round(y0, 3)),
        (round(x1, 3), round(y0, 3)),
        (round(x1, 3), round(y1, 3)),
        (round(x0, 3), round(y1, 3)),
    }
    actual_corners = {(round(point.x, 3), round(point.y, 3)) for point in points}
    if actual_corners != expected_corners:
        return None
    try:
        scissor_rect = fitz.Rect(scissor)
    except (TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(value) for value in scissor_rect):
        return None
    return fitz.Rect(x0, y0, x1, y1) if scissor_rect.is_valid else None


def _clip_fully_contains_rect(drawing: dict, target: fitz.Rect) -> bool:
    """Prove both actual rectangular clip geometry and its scissor contain a target."""
    clip_rect = _axis_aligned_clip_rect(drawing)
    if clip_rect is None or not target.is_valid:
        return False
    scissor_rect = fitz.Rect(drawing["scissor"])
    margin = 0.02
    return (
        clip_rect.x0 <= target.x0 + margin
        and clip_rect.y0 <= target.y0 + margin
        and clip_rect.x1 >= target.x1 - margin
        and clip_rect.y1 >= target.y1 - margin
        and scissor_rect.x0 <= target.x0 + margin
        and scissor_rect.y0 <= target.y0 + margin
        and scissor_rect.x1 >= target.x1 - margin
        and scissor_rect.y1 >= target.y1 - margin
    )


def _clip_fully_contains_circle(
    drawing: dict, center_x: float, center_y: float, radius: float
) -> bool:
    """Prove an axis-aligned clip rectangle leaves a candidate circle intact."""
    target = fitz.Rect(
        center_x - radius, center_y - radius, center_x + radius, center_y + radius
    )
    return _clip_fully_contains_rect(drawing, target)


def _image_paint_operations(page: fitz.Page) -> list[tuple[int, fitz.Rect]]:
    """Return image paint bounds keyed by their PDF paint-order sequence."""
    operations: list[tuple[int, fitz.Rect]] = []
    try:
        for sequence, (kind, bounds) in enumerate(page.get_bboxlog()):
            if kind.startswith("fill-image"):
                operations.append((sequence, fitz.Rect(bounds)))
    except (AttributeError, RuntimeError, ValueError):
        # Older/unsupported PyMuPDF builds cannot prove order, so callers treat
        # the available image rectangles conservatively as later paint.
        for image in page.get_images():
            for rect in page.get_image_rects(image[0]):
                operations.append((-1, rect))
    return operations


def _circle_fill_coverage_fraction(
    circle: tuple[float, float, float],
    polygon: list[tuple[float, float]],
) -> float:
    """Return the exact angular fraction of a circle perimeter inside a polygon."""
    center_x, center_y, radius = circle
    if (
        not all(math.isfinite(value) for value in (center_x, center_y, radius))
        or radius <= 0.0
        or len(polygon) < 3
        or any(not all(math.isfinite(value) for value in point) for point in polygon)
    ):
        return 0.0

    intersections = [0.0, 2.0 * math.pi]
    for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1]):
        dx = x1 - x0
        dy = y1 - y0
        fx = x0 - center_x
        fy = y0 - center_y
        a = dx * dx + dy * dy
        if a <= 1e-18:
            continue
        b = 2.0 * (fx * dx + fy * dy)
        c = fx * fx + fy * fy - radius * radius
        discriminant = b * b - 4.0 * a * c
        if discriminant < -1e-10:
            continue
        root = math.sqrt(max(0.0, discriminant))
        for fraction in ((-b - root) / (2.0 * a), (-b + root) / (2.0 * a)):
            if -1e-10 <= fraction <= 1.0 + 1e-10:
                x = x0 + min(1.0, max(0.0, fraction)) * dx - center_x
                y = y0 + min(1.0, max(0.0, fraction)) * dy - center_y
                intersections.append(math.atan2(y, x) % (2.0 * math.pi))

    intersections.sort()
    angles: list[float] = []
    for angle in intersections:
        if not angles or angle - angles[-1] > 1e-10:
            angles.append(angle)
    if angles[0] > 1e-10:
        angles.insert(0, 0.0)
    if angles[-1] < 2.0 * math.pi - 1e-10:
        angles.append(2.0 * math.pi)

    def inside(x: float, y: float) -> bool:
        winding = 0
        for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1]):
            cross = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
            if (
                abs(cross) <= 1e-8
                and min(x0, x1) - 1e-8 <= x <= max(x0, x1) + 1e-8
                and min(y0, y1) - 1e-8 <= y <= max(y0, y1) + 1e-8
            ):
                return True
            if y0 <= y < y1 and cross > 0:
                winding += 1
            elif y1 <= y < y0 and cross < 0:
                winding -= 1
        return winding != 0

    covered = 0.0
    for start, end in zip(angles, angles[1:]):
        if end - start <= 1e-12:
            continue
        angle = (start + end) / 2.0
        if inside(
            center_x + radius * math.cos(angle),
            center_y + radius * math.sin(angle),
        ):
            covered += end - start
    return min(1.0, max(0.0, covered / (2.0 * math.pi)))


def _dimension_arrowhead_context(
    drawings: list[dict],
    fill_index: int,
    circle: tuple[float, float, float],
    witness_color: Optional[tuple[float, float, float]],
) -> Optional[tuple[tuple[float, float], tuple[float, float]]]:
    """Return the base and circle-touching tip of a small matching dimension arrow."""
    if not 0 < fill_index < len(drawings):
        return None
    fill = drawings[fill_index]
    if fill.get("type") not in {"f", "fs"} or fill.get("fill") is None:
        return None
    if (
        fill.get("blendmode") not in {None, "Normal"}
        or abs(float(fill.get("fill_opacity", 1.0)) - 1.0) > 1e-9
        or (witness_color is not None and _colors_match(fill.get("fill"), witness_color) is not True)
    ):
        return None
    stroke_width = fill.get("width")
    if fill.get("type") == "fs" and (
        stroke_width is None
        or not math.isfinite(float(stroke_width))
        or float(stroke_width) < 0.0
        or float(stroke_width) > 1.0
        or abs(float(fill.get("stroke_opacity", 0.0)) - 1.0) > 1e-9
    ):
        return None

    points: list[tuple[float, float]] = []
    previous_end: Optional[tuple[float, float]] = None
    for item in fill.get("items", []):
        if item[0] != "l":
            return None
        _, start, end = item
        start_xy = (float(start.x), float(start.y))
        end_xy = (float(end.x), float(end.y))
        if not all(math.isfinite(value) for value in (*start_xy, *end_xy)):
            return None
        if previous_end is not None and math.hypot(
            previous_end[0] - start_xy[0], previous_end[1] - start_xy[1]
        ) > 0.05:
            return None
        previous_end = end_xy
        if not points:
            points.append(start_xy)
        if math.hypot(start_xy[0] - end_xy[0], start_xy[1] - end_xy[1]) > 0.05:
            points.append(end_xy)
    if (
        len(points) != 4
        or math.hypot(points[-1][0] - points[0][0], points[-1][1] - points[0][1]) > 0.05
        or len(set(points[:-1])) != 3
    ):
        return None

    polygon = points[:-1]
    edge_lengths = [
        math.hypot(x1 - x0, y1 - y0)
        for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1])
    ]
    area = abs(
        sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1]))
    ) / 2.0
    if min(edge_lengths) < 1.0 or max(edge_lengths) > 12.0 or not 1.0 <= area <= 40.0:
        return None
    if _circle_fill_coverage_fraction(circle, polygon) > 0.08:
        return None
    if fill.get("type") == "fs" and float(stroke_width) > 0.0:
        stroke_radius = float(stroke_width) / 2.0
        for adjusted_radius in (circle[2] - stroke_radius, circle[2] + stroke_radius):
            if adjusted_radius <= 0.0 or _circle_fill_coverage_fraction(
                (circle[0], circle[1], adjusted_radius), polygon
            ) > 0.08:
                return None

    previous = drawings[fill_index - 1]
    if (
        previous.get("type") != "s"
        or len(previous.get("items", [])) != 1
        or previous["items"][0][0] != "l"
        or previous.get("blendmode") not in {None, "Normal"}
        or abs(float(previous.get("stroke_opacity", 0.0)) - 1.0) > 1e-9
        or (witness_color is not None and _colors_match(previous.get("color"), witness_color) is not True)
    ):
        return None
    _, axis_start, axis_end = previous["items"][0]
    shared = (float(axis_start.x), float(axis_start.y))
    tip = (float(axis_end.x), float(axis_end.y))

    def point_on_triangle_vertex(point: tuple[float, float]) -> bool:
        return any(math.hypot(point[0] - x, point[1] - y) <= 0.5 for x, y in polygon)

    def point_in_triangle(x: float, y: float) -> bool:
        signs = [
            (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
            for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1])
        ]
        return all(value >= -0.5 for value in signs) or all(value <= 0.5 for value in signs)

    axis_length = math.hypot(tip[0] - shared[0], tip[1] - shared[1])
    if (
        point_on_triangle_vertex(shared)
        or not point_on_triangle_vertex(tip)
        or not point_in_triangle(*shared)
        or not 1.0 <= axis_length <= 12.0
        or abs(math.hypot(tip[0] - circle[0], tip[1] - circle[1]) - circle[2])
        > max(1.0, circle[2] * 0.005)
    ):
        return None
    return shared, tip


def _paired_circle_dimension_arrowhead(
    drawings: list[dict],
    fill_index: int,
    circle: tuple[float, float, float],
    witness_color: Optional[tuple[float, float, float]],
) -> bool:
    current = _dimension_arrowhead_context(drawings, fill_index, circle, witness_color)
    if current is None:
        return False
    current_shared, current_tip = current
    current_axis = (current_tip[0] - current_shared[0], current_tip[1] - current_shared[1])
    current_axis_length = math.hypot(*current_axis)

    for other_index, other in enumerate(drawings):
        if other_index == fill_index:
            continue
        other_context = _dimension_arrowhead_context(drawings, other_index, circle, witness_color)
        if other_context is None:
            continue
        other_shared, other_tip = other_context
        other_axis = (other_tip[0] - other_shared[0], other_tip[1] - other_shared[1])
        other_axis_length = math.hypot(*other_axis)
        for line_index in range(max(fill_index, other_index) + 1, len(drawings)):
            line = drawings[line_index]
            if (
                line.get("type") != "s"
                or len(line.get("items", [])) != 1
                or line["items"][0][0] != "l"
                or line.get("blendmode") not in {None, "Normal"}
                or abs(float(line.get("stroke_opacity", 0.0)) - 1.0) > 1e-9
                or not math.isfinite(float(line.get("width", math.nan)))
                or not 0.0 <= float(line.get("width", -1.0)) <= 1.0
                or (witness_color is not None and _colors_match(line.get("color"), witness_color) is not True)
            ):
                continue
            _, start, end = line["items"][0]
            start_xy = (float(start.x), float(start.y))
            end_xy = (float(end.x), float(end.y))
            if (
                math.hypot(start_xy[0] - current_shared[0], start_xy[1] - current_shared[1]) <= 0.5
                and math.hypot(end_xy[0] - other_shared[0], end_xy[1] - other_shared[1]) <= 0.5
            ):
                connector = (end_xy[0] - start_xy[0], end_xy[1] - start_xy[1])
            elif (
                math.hypot(end_xy[0] - current_shared[0], end_xy[1] - current_shared[1]) <= 0.5
                and math.hypot(start_xy[0] - other_shared[0], start_xy[1] - other_shared[1]) <= 0.5
            ):
                connector = (start_xy[0] - end_xy[0], start_xy[1] - end_xy[1])
            else:
                continue
            connector_length = math.hypot(*connector)
            center_distance = abs(
                (connector[0] * (current_shared[1] - circle[1])
                 - connector[1] * (current_shared[0] - circle[0]))
                / max(connector_length, 1e-9)
            )
            current_cosine = -(
                current_axis[0] * connector[0] + current_axis[1] * connector[1]
            ) / max(current_axis_length * connector_length, 1e-9)
            opposite_connector = (-connector[0], -connector[1])
            other_cosine = -(
                other_axis[0] * opposite_connector[0] + other_axis[1] * opposite_connector[1]
            ) / max(other_axis_length * connector_length, 1e-9)
            if (
                connector_length >= 1.8 * circle[2]
                and center_distance <= max(1.0, circle[2] * 0.005)
                and current_cosine >= math.cos(math.radians(10.0))
                and other_cosine >= math.cos(math.radians(10.0))
                and abs(math.hypot(other_tip[0] - circle[0], other_tip[1] - circle[1]) - circle[2])
                <= max(1.0, circle[2] * 0.005)
            ):
                return True
    return False


def _dimension_arrowhead_fill(
    drawings: list[dict],
    fill_index: int,
    circle: tuple[float, float, float],
    witness_color: Optional[tuple[float, float, float]] = None,
) -> bool:
    """Recognize only a small filled triangle joined to an axis and outward leader.

    Tolerances are in PDF page points: 0.05 for closed-path continuity, 0.5
    for stroke-to-fill attachment, and 10 degrees for opposite collinear axes.
    The local overprint is capped at 8 percent of the candidate circumference;
    triangle edges are capped at 12 points and its area at 40 square points.
    """
    if _paired_circle_dimension_arrowhead(drawings, fill_index, circle, witness_color):
        return True
    if not 0 < fill_index < len(drawings) - 1:
        return False
    fill = drawings[fill_index]
    if (
        fill.get("type") not in {"f", "fs"}
        or fill.get("fill") is None
        or fill.get("blendmode") not in {None, "Normal"}
        or abs(float(fill.get("fill_opacity", 1.0)) - 1.0) > 1e-9
        or (witness_color is not None and _colors_match(fill.get("fill"), witness_color) is not True)
    ):
        return False
    stroke_width = fill.get("width")
    if fill.get("type") == "fs" and (
        stroke_width is None
        or not math.isfinite(float(stroke_width))
        or float(stroke_width) < 0.0
        or float(stroke_width) > 1.0
    ):
        return False
    items = fill.get("items", [])
    if len(items) != 3 or any(item[0] != "l" for item in items):
        return False

    points: list[tuple[float, float]] = []
    for _, start, end in items:
        if not all(math.isfinite(value) for value in (start.x, start.y, end.x, end.y)):
            return False
        if not points:
            points.append((float(start.x), float(start.y)))
        elif math.hypot(points[-1][0] - start.x, points[-1][1] - start.y) > 0.05:
            return False
        points.append((float(end.x), float(end.y)))
    if math.hypot(points[-1][0] - points[0][0], points[-1][1] - points[0][1]) > 0.05:
        return False
    polygon = points[:-1]
    if len(set(polygon)) != 3:
        return False

    edge_lengths = [
        math.hypot(x1 - x0, y1 - y0)
        for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1])
    ]
    twice_area = abs(sum(
        x0 * y1 - x1 * y0
        for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1])
    ))
    area = twice_area / 2.0
    if min(edge_lengths) < 1.0 or max(edge_lengths) > 12.0 or not 1.0 <= area <= 40.0:
        return False
    coverage = _circle_fill_coverage_fraction(circle, polygon)
    if not 0.0 < coverage <= 0.08:
        return False
    if fill.get("type") == "fs" and float(stroke_width) > 0.0:
        stroke_radius = float(stroke_width) / 2.0
        for adjusted_radius in (circle[2] - stroke_radius, circle[2] + stroke_radius):
            if adjusted_radius <= 0.0 or _circle_fill_coverage_fraction(
                (circle[0], circle[1], adjusted_radius), polygon
            ) > 0.08:
                return False

    previous = drawings[fill_index - 1]
    following = drawings[fill_index + 1]
    if (
        previous.get("type") != "s"
        or len(previous.get("items", [])) != 1
        or previous["items"][0][0] != "l"
        or following.get("type") != "s"
        or not following.get("items")
        or following["items"][0][0] != "l"
    ):
        return False

    _, prior_start, prior_end = previous["items"][0]
    prior_start_xy = (float(prior_start.x), float(prior_start.y))
    prior_end_xy = (float(prior_end.x), float(prior_end.y))
    attachment_tolerance = 0.5
    if math.hypot(prior_start_xy[0] - prior_end_xy[0], prior_start_xy[1] - prior_end_xy[1]) <= 1.0:
        return False

    def point_on_triangle_vertex(point: tuple[float, float]) -> bool:
        return any(math.hypot(point[0] - x, point[1] - y) <= attachment_tolerance for x, y in polygon)

    # The short axis must enter the triangle at a vertex; its other endpoint
    # and the next leader's origin must be the same point inside the triangle.
    if point_on_triangle_vertex(prior_start_xy) or not point_on_triangle_vertex(prior_end_xy):
        return False
    shared_x, shared_y = prior_start_xy
    _, leader_start, leader_end = following["items"][0]
    leader_start_xy = (float(leader_start.x), float(leader_start.y))
    leader_end_xy = (float(leader_end.x), float(leader_end.y))
    if math.hypot(shared_x - leader_start_xy[0], shared_y - leader_start_xy[1]) > attachment_tolerance:
        return False

    def point_in_triangle(x: float, y: float) -> bool:
        signs = []
        for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1]):
            signs.append((x1 - x0) * (y - y0) - (y1 - y0) * (x - x0))
        return all(value >= -0.5 for value in signs) or all(value <= 0.5 for value in signs)

    if not point_in_triangle(shared_x, shared_y):
        return False
    axis_x = prior_end_xy[0] - shared_x
    axis_y = prior_end_xy[1] - shared_y
    leader_x = leader_end_xy[0] - shared_x
    leader_y = leader_end_xy[1] - shared_y
    axis_length = math.hypot(axis_x, axis_y)
    leader_length = math.hypot(leader_x, leader_y)
    if axis_length < 1.0 or leader_length < 6.0:
        return False
    cosine = (axis_x * leader_x + axis_y * leader_y) / (axis_length * leader_length)
    return cosine <= -math.cos(math.radians(10.0))


def _full_page_transparency_group_index(page: fitz.Page, drawings: list[dict]) -> Optional[int]:
    """Identify only the exact, full-page transparency wrapper verified for page content.

    A page-level transparency group is compositing context, not a local paint
    or clipping operation. Only the exact full-page DeviceRGB group with raw
    default attributes is ignored as context. PDF page groups have special
    isolation semantics when rendered directly; do not generalize this rule
    to nested, partial, explicitly decorated, or other transparency groups.
    """
    group_indices = [index for index, drawing in enumerate(drawings) if drawing.get("type") == "group"]
    if group_indices != [0]:
        return None
    group = drawings[0]
    group_rect = group.get("rect")
    page_rect = page.rect
    if (
        group.get("level") != 0
        or group.get("scissor") is not None
        or group.get("blendmode") != "Normal"
        or group.get("knockout") is not False
        or group_rect is None
        or any(
            abs(left - right) > 0.02
            for left, right in zip(
                (group_rect.x0, group_rect.y0, group_rect.x1, group_rect.y1),
                (page_rect.x0, page_rect.y0, page_rect.x1, page_rect.y1),
            )
        )
    ):
        return None
    try:
        key_type, group_value = page.parent.xref_get_key(page.xref, "Group")
    except (AttributeError, RuntimeError, ValueError):
        return None
    if key_type != "dict":
        return None
    normalized_group = re.sub(r"\s+", "", group_value)
    if normalized_group not in {
        "<</S/Transparency/CS/DeviceRGB>>",
        "<</CS/DeviceRGB/S/Transparency>>",
    }:
        return None
    return 0


def _page_circle_witnesses(
    page: fitz.Page, pixel_scale: float
) -> tuple[bool, list[tuple[float, float, float]], list[dict]]:
    """Return global fail-closed state, full-circle witnesses, and suspect regions."""
    drawings = page.get_drawings(extended=True)
    if not drawings:
        return False, [], []
    full_page_group_index = _full_page_transparency_group_index(page, drawings)
    curve_drawings = [
        drawing for drawing in drawings if any(item[0] == "c" for item in drawing.get("items", []))
    ]
    line_contour_indices = {
        index for index, drawing in enumerate(drawings) if _is_closed_line_contour(drawing)
    }
    single_line_paths = _single_line_record_paths(drawings)
    single_line_paths_by_end = {
        end_index: (start_index, drawing, closed)
        for start_index, end_index, drawing, closed in single_line_paths
    }
    open_line_circle_arcs = {
        index: _fit_open_line_circle_arc(drawing)
        for index, drawing in enumerate(drawings)
        if index not in line_contour_indices
    }
    open_line_circle_arcs = {
        index: circle for index, circle in open_line_circle_arcs.items() if circle is not None
    }
    open_line_curve_suspects = _collect_open_line_curve_suspects(drawings)
    open_line_curve_suspects.extend(
        drawing for _, _, drawing, closed in single_line_paths if not closed
    )
    if (
        not curve_drawings
        and not line_contour_indices
        and not single_line_paths
        and not open_line_circle_arcs
        and not open_line_curve_suspects
    ):
        return False, [], []
    background_color = _page_background_color(page)
    page_transform = page.rotation_matrix

    image_paint_operations = _image_paint_operations(page)
    text_paint_operations: Optional[list[tuple[int, fitz.Rect]]]
    try:
        text_paint_operations = []
        for span in page.get_texttrace():
            sequence = span.get("seqno")
            rect = fitz.Rect(span.get("bbox"))
            if isinstance(sequence, bool) or not isinstance(sequence, int):
                raise ValueError("PDF text paint sequence is unavailable")
            if not all(math.isfinite(value) for value in (rect.x0, rect.y0, rect.x1, rect.y1)):
                raise ValueError("PDF text paint bounds are non-finite")
            if not rect.is_empty:
                text_paint_operations.append((sequence, rect))
    except Exception:
        # Without ordered text bounds, a vector circle cannot be independently
        # cleared of later text paint; fail closed for this page's witnesses.
        text_paint_operations = None
    annotation_rects: list[fitz.Rect] = []
    for annotation in page.annots() or ():
        annotation_rects.append(annotation.rect)

    witnesses: list[tuple[float, float, float]] = []
    suspect_regions: list[dict] = [
        _suspect_geometry(drawing, pixel_scale, page_transform)
        for drawing in open_line_curve_suspects
    ]
    for index, drawing in enumerate(drawings):
        line_record_path = single_line_paths_by_end.get(index)
        if line_record_path is not None:
            path_start_index, drawing, closed_line_record_path = line_record_path
        else:
            path_start_index = index
            closed_line_record_path = False
        has_curve = any(item[0] == "c" for item in drawing.get("items", []))
        has_line_contour = index in line_contour_indices or closed_line_record_path
        if not has_curve and not has_line_contour:
            if index in open_line_circle_arcs:
                suspect_regions.append(_suspect_geometry(drawing, pixel_scale, page_transform))
            continue
        if not has_curve and has_line_contour:
            drawing_rect = drawing.get("rect")
            circle = _fit_full_line_circle_path(drawing, background_color)
            if circle is None:
                if drawing_rect is not None:
                    suspect_regions.append(_suspect_geometry(drawing, pixel_scale, page_transform))
                continue
        else:
            circle = None
        drawing_rect = drawing.get("rect")
        if drawing_rect is None:
            continue
        if circle is None:
            circle = _fit_full_circle_path(drawing, background_color)
        if circle is None:
            suspect_regions.append(_suspect_geometry(drawing, pixel_scale, page_transform))
            continue

        cx, cy, radius = circle
        # A fitted path can be geometrically closed while lying partly or
        # wholly outside the page's visible render frame. Such a path has no
        # complete rendered perimeter to support a source witness.
        try:
            stroke_width = float(drawing.get("width") or 0.0)
            if not math.isfinite(stroke_width) or stroke_width < 0.0:
                raise ValueError("invalid circle stroke width")
            margin = stroke_width / 2.0
            circle_bounds = fitz.Rect(
                cx - radius - margin,
                cy - radius - margin,
                cx + radius + margin,
                cy + radius + margin,
            ) * page_transform
            render_bounds = page.rect
            fully_in_render_frame = (
                all(
                    math.isfinite(value)
                    for value in (
                        circle_bounds.x0,
                        circle_bounds.y0,
                        circle_bounds.x1,
                        circle_bounds.y1,
                    )
                )
                and circle_bounds.x0 >= render_bounds.x0 - 1e-4
                and circle_bounds.y0 >= render_bounds.y0 - 1e-4
                and circle_bounds.x1 <= render_bounds.x1 + 1e-4
                and circle_bounds.y1 <= render_bounds.y1 + 1e-4
            )
        except (TypeError, ValueError, OverflowError):
            fully_in_render_frame = False
        if not fully_in_render_frame:
            suspect_regions.append(_suspect_geometry(drawing, pixel_scale, page_transform))
            continue

        witness_level = int(drawing.get("level") or 0)
        prior_clip_context = any(
            int(prior.get("level") or 0) < witness_level
            and (
                (prior.get("type") == "group" and prior_index != full_page_group_index)
                or (
                    prior.get("type") == "clip"
                    and not _clip_fully_contains_circle(prior, cx, cy, radius)
                )
            )
            for prior_index, prior in enumerate(drawings[:path_start_index])
        )
        if prior_clip_context:
            suspect_regions.append(_suspect_geometry(drawing, pixel_scale, page_transform))
            continue

        # A later drawing/clip/group touching this perimeter can obscure or
        # alter the witness. Conservatively reject rather than infer visibility.
        occluded = text_paint_operations is None
        drawing_sequence = drawing.get("seqno")
        occluder_rects = annotation_rects + [
            rect
            for sequence, rect in image_paint_operations
            if drawing_sequence is None or sequence < 0 or sequence > drawing_sequence
        ]
        if text_paint_operations is not None:
            occluder_rects.extend(
                rect
                for sequence, rect in text_paint_operations
                if drawing_sequence is None or sequence < 0 or sequence > drawing_sequence
            )
        for rect in occluder_rects:
            dx = max(rect.x0 - cx, 0.0, cx - rect.x1)
            dy = max(rect.y0 - cy, 0.0, cy - rect.y1)
            min_distance = math.hypot(dx, dy)
            max_distance = max(
                math.hypot(x - cx, y - cy)
                for x, y in (
                    (rect.x0, rect.y0),
                    (rect.x0, rect.y1),
                    (rect.x1, rect.y0),
                    (rect.x1, rect.y1),
                )
            )
            if min_distance <= radius + 1.0 and max_distance >= radius - 1.0:
                occluded = True
                break
        for later_index in range(index + 1, len(drawings)):
            if occluded:
                break
            later = drawings[later_index]
            later_type = later.get("type")
            if later_type == "clip":
                # Extended drawing output reports clipping contexts separately;
                # they constrain later paint but do not paint over this stroke.
                continue
            if later_type not in {"s", "group", "f", "fs"}:
                occluded = True
                break
            if later_type in {"s", "f", "fs"} and not _drawing_may_erase_circle(
                later, drawing.get("color"), drawing.get("width")
            ):
                continue
            if later_type in {"f", "fs"} and _dimension_arrowhead_fill(
                drawings,
                later_index,
                (cx, cy, radius),
                drawing.get("color"),
            ):
                continue
            later_circle = None
            if later_type == "s":
                later_circle = _fit_full_circle_path(later, background_color)
                if later_circle is None:
                    later_circle = _fit_full_line_circle_path(later, background_color)
            if later_circle is not None:
                later_cx, later_cy, later_radius = later_circle
                center_distance = math.hypot(later_cx - cx, later_cy - cy)
                if (
                    center_distance <= radius + later_radius + 1.0
                    and center_distance + min(radius, later_radius)
                    >= max(radius, later_radius) - 1.0
                ):
                    occluded = True
                    break
                continue

            if later_type == "s":
                radial_samples: list[float] = []
                unsupported_item = False
                for item in later.get("items", []):
                    if item[0] == "l":
                        _, start, end = item
                        points = [(start.x, start.y), (end.x, end.y)]
                        dx = end.x - start.x
                        dy = end.y - start.y
                        length_squared = dx * dx + dy * dy
                        if length_squared > 0.0:
                            fraction = min(
                                1.0,
                                max(
                                    0.0,
                                    ((cx - start.x) * dx + (cy - start.y) * dy) / length_squared,
                                ),
                            )
                            closest_x = start.x + fraction * dx
                            closest_y = start.y + fraction * dy
                            radial_samples.append(math.hypot(closest_x - cx, closest_y - cy))
                    elif item[0] == "c":
                        _, p0, p1, p2, p3 = item
                        points = []
                        for step in range(33):
                            t = step / 32.0
                            u = 1.0 - t
                            points.append(
                                (
                                    u**3 * p0.x
                                    + 3 * u**2 * t * p1.x
                                    + 3 * u * t**2 * p2.x
                                    + t**3 * p3.x,
                                    u**3 * p0.y
                                    + 3 * u**2 * t * p1.y
                                    + 3 * u * t**2 * p2.y
                                    + t**3 * p3.y,
                                )
                            )
                    elif item[0] == "qu":
                        try:
                            quad = item[1]
                            # PyMuPDF exposes Quad fields by corner name; walk
                            # the perimeter clockwise, including its closing edge.
                            quad_points = [quad.ul, quad.ur, quad.lr, quad.ll]
                            points = [(float(point.x), float(point.y)) for point in quad_points]
                            if any(
                                not math.isfinite(coordinate)
                                for point in points
                                for coordinate in point
                            ):
                                raise ValueError("non-finite quad point")
                            for edge_index, (start_x, start_y) in enumerate(points):
                                end_x, end_y = points[(edge_index + 1) % len(points)]
                                dx = end_x - start_x
                                dy = end_y - start_y
                                length_squared = dx * dx + dy * dy
                                if not math.isfinite(length_squared) or length_squared <= 0.0:
                                    raise ValueError("degenerate quad edge")
                                fraction = min(
                                    1.0,
                                    max(
                                        0.0,
                                        ((cx - start_x) * dx + (cy - start_y) * dy)
                                        / length_squared,
                                    ),
                                )
                                closest_x = start_x + fraction * dx
                                closest_y = start_y + fraction * dy
                                radial_samples.append(math.hypot(closest_x - cx, closest_y - cy))
                        except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
                            unsupported_item = True
                            points = []
                    else:
                        unsupported_item = True
                        points = []
                    radial_samples.extend(math.hypot(x - cx, y - cy) for x, y in points)
                if unsupported_item:
                    occluded = True
                    break
                if radial_samples:
                    stroke_margin = max(1.0, float(later.get("width") or 0.0) / 2.0)
                    if (
                        min(radial_samples) <= radius + stroke_margin
                        and max(radial_samples) >= radius - stroke_margin
                    ):
                        occluded = True
                        break
                continue

            rect = later.get("scissor") or later.get("rect")
            if rect is None:
                if later_type in {"clip", "group"}:
                    occluded = True
                continue
            dx = max(rect.x0 - cx, 0.0, cx - rect.x1)
            dy = max(rect.y0 - cy, 0.0, cy - rect.y1)
            min_distance = math.hypot(dx, dy)
            max_distance = max(
                math.hypot(x - cx, y - cy)
                for x, y in (
                    (rect.x0, rect.y0),
                    (rect.x0, rect.y1),
                    (rect.x1, rect.y0),
                    (rect.x1, rect.y1),
                )
            )
            if min_distance <= radius + 1.0 and max_distance >= radius - 1.0:
                occluded = True
                break
        if not occluded:
            rendered_center = fitz.Point(cx, cy) * page_transform
            witness = (
                rendered_center.x * pixel_scale,
                rendered_center.y * pixel_scale,
                radius * pixel_scale,
            )
            identity_tolerance = 0.02 * pixel_scale
            if not any(
                math.hypot(witness[0] - prior[0], witness[1] - prior[1]) <= identity_tolerance
                and abs(witness[2] - prior[2]) <= identity_tolerance
                for prior in witnesses
            ):
                witnesses.append(witness)
        else:
            suspect_regions.append(_suspect_geometry(drawing, pixel_scale, page_transform))
    return False, witnesses, suspect_regions


def _page_vector_arcs(
    page: fitz.Page,
    rendered_png_bytes: bytes,
    pixel_scale: float,
    pixmap_origin: tuple[int, int],
    render_dpi: int,
    source_pdf_sha256: str,
    source_page_index: int,
) -> list[RawArc]:
    """Admit only visible, opaque, unclipped, isolated open cubic PDF arcs."""
    if page.rotation not in {0, 90, 180, 270}:
        return []
    import cv2

    if not isinstance(rendered_png_bytes, bytes) or not rendered_png_bytes:
        return []
    image = cv2.imdecode(
        np.frombuffer(rendered_png_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE
    )
    if image is None:
        return []
    height, width = image.shape
    drawings = page.get_drawings(extended=True)
    bboxlog = page.get_bboxlog()
    drawing_by_seqno = {
        drawing.get("seqno"): drawing
        for drawing in drawings
        if isinstance(drawing.get("seqno"), int)
    }
    transform = page.rotation_matrix
    transform_values = (
        transform.a * pixel_scale,
        transform.b * pixel_scale,
        transform.c * pixel_scale,
        transform.d * pixel_scale,
        transform.e * pixel_scale - pixmap_origin[0],
        transform.f * pixel_scale - pixmap_origin[1],
    )
    if not all(math.isfinite(float(value)) for value in transform_values):
        return []
    results: list[RawArc] = []

    def cubic_points(item: tuple, steps: int = 32) -> list[tuple[float, float]]:
        _, p0, p1, p2, p3 = item
        points = []
        for step in range(steps + 1):
            t = step / steps
            u = 1.0 - t
            points.append((
                u**3 * p0.x + 3 * u**2 * t * p1.x + 3 * u * t**2 * p2.x + t**3 * p3.x,
                u**3 * p0.y + 3 * u**2 * t * p1.y + 3 * u * t**2 * p2.y + t**3 * p3.y,
            ))
        return points

    def cubic_segment_bounds(item: tuple, steps: int = 32) -> list[fitz.Rect]:
        """Return conservative control-hull bounds for each cubic subcurve."""
        _, p0, p1, p2, p3 = item
        controls = tuple(
            (float(point.x), float(point.y)) for point in (p0, p1, p2, p3)
        )

        def point_at(t: float) -> tuple[float, float]:
            u = 1.0 - t
            return tuple(
                u**3 * controls[0][axis]
                + 3.0 * u**2 * t * controls[1][axis]
                + 3.0 * u * t**2 * controls[2][axis]
                + t**3 * controls[3][axis]
                for axis in (0, 1)
            )

        def tangent_at(t: float) -> tuple[float, float]:
            u = 1.0 - t
            return tuple(
                3.0 * u**2 * (controls[1][axis] - controls[0][axis])
                + 6.0 * u * t * (controls[2][axis] - controls[1][axis])
                + 3.0 * t**2 * (controls[3][axis] - controls[2][axis])
                for axis in (0, 1)
            )

        if not all(math.isfinite(value) for point in controls for value in point):
            raise ValueError("non-finite cubic control point")
        bounds = []
        for step in range(steps):
            start_t = step / steps
            end_t = (step + 1) / steps
            interval = end_t - start_t
            start = point_at(start_t)
            end = point_at(end_t)
            start_tangent = tangent_at(start_t)
            end_tangent = tangent_at(end_t)
            subcurve_controls = (
                start,
                tuple(start[i] + start_tangent[i] * interval / 3.0 for i in (0, 1)),
                tuple(end[i] - end_tangent[i] * interval / 3.0 for i in (0, 1)),
                end,
            )
            bounds.append(fitz.Rect(
                min(point[0] for point in subcurve_controls),
                min(point[1] for point in subcurve_controls),
                max(point[0] for point in subcurve_controls),
                max(point[1] for point in subcurve_controls),
            ))
        return bounds

    def stroke_segments(
        drawing: dict,
    ) -> Optional[list[tuple[tuple[float, float], tuple[float, float], float]]]:
        """Flatten known stroked paths with a conservative curve error bound."""
        segments: list[tuple[tuple[float, float], tuple[float, float], float]] = []
        for item in drawing.get("items", []):
            kind = item[0]
            if kind == "l":
                points = [(float(point.x), float(point.y)) for point in item[1:3]]
                segments.extend((start, end, 0.0) for start, end in zip(points, points[1:]))
            elif kind == "c":
                try:
                    cubic_segments = flatten_cubic(item)
                except (IndexError, TypeError, ValueError, OverflowError):
                    return None
                if cubic_segments is None:
                    return None
                segments.extend(cubic_segments)
            elif kind == "re":
                rect = fitz.Rect(item[1])
                points = [
                    (rect.x0, rect.y0), (rect.x1, rect.y0),
                    (rect.x1, rect.y1), (rect.x0, rect.y1),
                    (rect.x0, rect.y0),
                ]
                segments.extend((start, end, 0.0) for start, end in zip(points, points[1:]))
            elif kind == "qu":
                quad = item[1]
                points = [
                    (quad.ul.x, quad.ul.y), (quad.ur.x, quad.ur.y),
                    (quad.lr.x, quad.lr.y), (quad.ll.x, quad.ll.y),
                    (quad.ul.x, quad.ul.y),
                ]
                segments.extend((start, end, 0.0) for start, end in zip(points, points[1:]))
            else:
                return None
        return segments

    def intersection_point(
        first_start: tuple[float, float],
        first_end: tuple[float, float],
        second_start: tuple[float, float],
        second_end: tuple[float, float],
    ) -> Optional[tuple[float, float]]:
        ax, ay = first_start
        bx, by = first_end
        cx, cy = second_start
        dx, dy = second_end
        rx, ry = bx - ax, by - ay
        sx, sy = dx - cx, dy - cy
        denominator = rx * sy - ry * sx
        qpx, qpy = cx - ax, cy - ay
        if abs(denominator) <= 1e-10:
            return None
        first_t = (qpx * sy - qpy * sx) / denominator
        second_t = (qpx * ry - qpy * rx) / denominator
        if -1e-9 <= first_t <= 1.0 + 1e-9 and -1e-9 <= second_t <= 1.0 + 1e-9:
            return (ax + first_t * rx, ay + first_t * ry)
        return None

    def point_segment_closest(
        point: tuple[float, float],
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> tuple[float, float]:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length_squared = dx * dx + dy * dy
        if length_squared <= 1e-18:
            return start
        fraction = max(0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared))
        return (start[0] + fraction * dx, start[1] + fraction * dy)

    def segment_closest_points(
        first_start: tuple[float, float],
        first_end: tuple[float, float],
        second_start: tuple[float, float],
        second_end: tuple[float, float],
    ) -> tuple[float, tuple[float, float], tuple[float, float]]:
        intersection = intersection_point(first_start, first_end, second_start, second_end)
        if intersection is not None:
            return 0.0, intersection, intersection
        candidates = []
        for point in (first_start, first_end):
            other = point_segment_closest(point, second_start, second_end)
            candidates.append((math.dist(point, other), point, other))
        for point in (second_start, second_end):
            other = point_segment_closest(point, first_start, first_end)
            candidates.append((math.dist(point, other), other, point))
        return min(candidates, key=lambda item: item[0])

    def flatten_cubic(
        item: tuple,
        *,
        max_flatness: float = 0.025,
        max_depth: int = 12,
    ) -> Optional[list[tuple[tuple[float, float], tuple[float, float], float]]]:
        """Flatten a cubic while retaining a control-hull distance bound."""
        try:
            controls = tuple((float(point.x), float(point.y)) for point in item[1:5])
        except (IndexError, TypeError, ValueError, OverflowError):
            return None
        if len(controls) != 4 or not all(
            math.isfinite(value) for point in controls for value in point
        ):
            return None
        result: list[tuple[tuple[float, float], tuple[float, float], float]] = []

        def midpoint(
            first: tuple[float, float], second: tuple[float, float]
        ) -> tuple[float, float]:
            return ((first[0] + second[0]) / 2.0, (first[1] + second[1]) / 2.0)

        def visit(curve: tuple[tuple[float, float], ...], depth: int) -> bool:
            start, control1, control2, end = curve
            flatness = max(
                math.dist(control1, point_segment_closest(control1, start, end)),
                math.dist(control2, point_segment_closest(control2, start, end)),
            )
            if not math.isfinite(flatness):
                return False
            if flatness <= max_flatness:
                result.append((start, end, flatness))
                return True
            if depth >= max_depth:
                return False
            first = midpoint(start, control1)
            middle = midpoint(control1, control2)
            last = midpoint(control2, end)
            left_middle = midpoint(first, middle)
            right_middle = midpoint(middle, last)
            split = midpoint(left_middle, right_middle)
            return visit((start, first, left_middle, split), depth + 1) and visit(
                (split, right_middle, last, end), depth + 1
            )

        if not visit(controls, 0):
            return None
        return result



    def flatten_arc_items(
        items: list[tuple],
    ) -> Optional[list[tuple[tuple[float, float], tuple[float, float], float]]]:
        segments = []
        for item in items:
            flattened = flatten_cubic(item)
            if flattened is None:
                return None
            segments.extend(flattened)
        return segments

    def later_stroke_crosses_arc(
        drawing: dict,
        arc_segments: list[tuple[tuple[float, float], tuple[float, float], float]],
        arc_samples: list[tuple[float, float]],
        arc_width_pt: float,
    ) -> Optional[bool]:
        segments = stroke_segments(drawing)
        stroke_width = drawing.get("width")
        if (
            segments is None
            or not isinstance(stroke_width, (int, float))
            or not math.isfinite(float(stroke_width))
            or stroke_width < 0
        ):
            return None
        overlap_tolerance = max(0.0, arc_width_pt) / 2.0 + float(stroke_width) / 2.0 + 0.25
        endpoint_join_tolerance = min(0.25, overlap_tolerance * 0.15)
        for arc_start, arc_end, arc_error in arc_segments:
            arc_dx, arc_dy = arc_end[0] - arc_start[0], arc_end[1] - arc_start[1]
            arc_length = math.hypot(arc_dx, arc_dy)
            if arc_length <= 1e-12:
                continue
            for line_start, line_end, line_error in segments:
                distance, arc_point, later_point = segment_closest_points(
                    arc_start, arc_end, line_start, line_end
                )
                if distance > overlap_tolerance + arc_error + line_error:
                    continue

                line_dx, line_dy = line_end[0] - line_start[0], line_end[1] - line_start[1]
                line_length = math.hypot(line_dx, line_dy)
                tangent_joins: list[tuple[float, float]] = []
                if line_length > 1e-12:
                    for endpoint, tangent in (
                        (arc_samples[0], (arc_samples[1][0] - arc_samples[0][0], arc_samples[1][1] - arc_samples[0][1])),
                        (arc_samples[-1], (arc_samples[-1][0] - arc_samples[-2][0], arc_samples[-1][1] - arc_samples[-2][1])),
                    ):
                        tangent_length = math.hypot(*tangent)
                        shares_endpoint = min(math.dist(endpoint, line_start), math.dist(endpoint, line_end)) <= endpoint_join_tolerance
                        tangent_aligned = tangent_length > 1e-12 and abs(
                            (tangent[0] * line_dx + tangent[1] * line_dy) / (tangent_length * line_length)
                        ) >= 0.98
                        if shares_endpoint and tangent_aligned:
                            tangent_joins.append(endpoint)
                if any(math.dist(later_point, endpoint) <= endpoint_join_tolerance for endpoint in tangent_joins):
                    # Allow only the paint overlap at a proven tangent endpoint
                    # join. Any later stroke reaching the arc interior still
                    # fails closed.
                    continue
                return True
        return False

    for index, drawing in enumerate(drawings):
        items = drawing.get("items", [])
        color = drawing.get("color")
        width_pt = drawing.get("width")
        seqno = drawing.get("seqno")
        if (
            drawing.get("type") != "s"
            or drawing.get("fill") is not None
            or not isinstance(color, (tuple, list))
            or len(color) != 3
            or any(not math.isfinite(float(channel)) or float(channel) > 0.45 for channel in color)
            or not isinstance(width_pt, (int, float))
            or not math.isfinite(float(width_pt))
            or width_pt <= 0
            or drawing.get("stroke_opacity") != 1.0
            or drawing.get("dashes") != "[] 0"
            or not isinstance(drawing.get("level"), int)
            or drawing.get("level", -1) < 0
            or not isinstance(seqno, int)
            or seqno < 0
            or not items
            or any(item[0] != "c" for item in items)
        ):
            continue

        samples: list[tuple[float, float]] = []
        curve_segment_bounds: list[fitz.Rect] = []
        connected = True
        previous_end = None
        for item in items:
            try:
                sampled = cubic_points(item)
                item_segment_bounds = cubic_segment_bounds(item)
            except (IndexError, TypeError, ValueError, OverflowError):
                connected = False
                break
            if previous_end is not None and math.dist(previous_end, sampled[0]) > 0.02:
                connected = False
                break
            if samples:
                sampled = sampled[1:]
            samples.extend(sampled)
            curve_segment_bounds.extend(item_segment_bounds)
            previous_end = sampled[-1] if sampled else previous_end
        if not connected or len(samples) < 8 or math.dist(samples[0], samples[-1]) <= 0.02:
            continue
        if any(not math.isfinite(value) for point in samples for value in point):
            continue
        arc_segments = flatten_arc_items(items)
        if arc_segments is None:
            continue

        x0, y0 = samples[0]
        x1, y1 = samples[-1]
        min_x, max_x = min(x for x, _ in samples), max(x for x, _ in samples)
        min_y, max_y = min(y for _, y in samples), max(y for _, y in samples)
        source_rect = fitz.Rect(min_x, min_y, max_x, max_y)
        path_rect = fitz.Rect(min_x - width_pt, min_y - width_pt, max_x + width_pt, max_y + width_pt)

        # Any intersecting clip/group ancestry or later-painted operation is
        # unresolved visibility. Reject conservatively, including image paint.
        level = drawing["level"]
        parent_clips = [
            prior
            for prior in drawings[:index]
            if prior.get("type") == "clip" and int(prior.get("level") or 0) < level
        ]
        prior_group = any(
            prior.get("type") == "group"
            and int(prior.get("level") or 0) < level
            and prior.get("rect") is not None
            and fitz.Rect(prior["rect"]).intersects(path_rect)
            for prior in drawings[:index]
        )
        # PyMuPDF's scissor is only the clip path's rectangular bounding box.
        # Admit nested content only when every parent clip's actual path is
        # proven to be an axis-aligned rectangle containing the full stroke.
        clip_unresolved = level > 0 and (
            not parent_clips
            or any(
                not _clip_fully_contains_rect(clip, path_rect)
                for clip in parent_clips
            )
        )
        paint_margin = max(0.25, float(width_pt) / 2.0)
        if seqno >= len(bboxlog) or len(bboxlog[seqno]) != 2:
            continue
        try:
            current_paint = bboxlog[seqno]
            current_rect = fitz.Rect(current_paint[1])
            current_matches_source = current_paint[0] == "stroke-path" and current_rect.contains(source_rect)
        except (IndexError, TypeError, ValueError, OverflowError):
            continue
        if not current_matches_source:
            continue
        later_paint = False
        for later_seqno, record in enumerate(bboxlog[seqno + 1 :], start=seqno + 1):
            if len(record) != 2:
                later_paint = True
                break
            try:
                paint_rect = fitz.Rect(record[1])
            except (IndexError, TypeError, ValueError, OverflowError):
                later_paint = True
                break
            if any(
                paint_rect.intersects(fitz.Rect(
                    segment_rect.x0 - paint_margin,
                    segment_rect.y0 - paint_margin,
                    segment_rect.x1 + paint_margin,
                    segment_rect.y1 + paint_margin,
                ))
                for segment_rect in curve_segment_bounds
            ):
                if record[0] == "stroke-path":
                    later_drawing = drawing_by_seqno.get(later_seqno)
                    if later_drawing is None:
                        later_paint = True
                    else:
                        crosses_arc = later_stroke_crosses_arc(
                            later_drawing, arc_segments, samples, float(width_pt)
                        )
                        later_paint = crosses_arc is not False
                else:
                    # Filled shapes, text, images, and unknown paint remain
                    # conservative: their paint bounds may hide the source arc.
                    later_paint = True
                if later_paint:
                    break
        if prior_group or clip_unresolved or later_paint:
            continue

        points = np.asarray(samples, dtype=np.float64)
        centered = points - points.mean(axis=0)
        matrix = np.column_stack((centered[:, 0], centered[:, 1], np.ones(len(centered))))
        if not np.isfinite(matrix).all() or np.linalg.cond(matrix) > 1.0e6:
            continue
        target = -(centered[:, 0] ** 2 + centered[:, 1] ** 2)
        try:
            a, b, c = np.linalg.lstsq(matrix, target, rcond=None)[0]
        except np.linalg.LinAlgError:
            continue
        center_local = (-a / 2.0, -b / 2.0)
        center = (center_local[0] + float(points.mean(axis=0)[0]), center_local[1] + float(points.mean(axis=0)[1]))
        radius_squared = center_local[0] ** 2 + center_local[1] ** 2 - c
        if not math.isfinite(radius_squared) or radius_squared <= 0:
            continue
        radius = math.sqrt(radius_squared)
        radial_errors = [abs(math.dist(point, center) - radius) for point in samples]
        if max(radial_errors) > max(0.02, min(float(width_pt) * 0.15, radius * 0.001)):
            continue

        angles = [math.atan2(y - center[1], x - center[0]) for x, y in samples]
        turns = [
            math.atan2(math.sin(b - a), math.cos(b - a))
            for a, b in zip(angles, angles[1:])
        ]
        sweep = sum(turns)
        if (
            not turns
            or not (all(turn > 0 for turn in turns) or all(turn < 0 for turn in turns))
            or max(abs(turn) for turn in turns) > math.radians(15)
            or not math.radians(15) <= abs(sweep) < math.radians(150)
        ):
            continue

        def to_pixel(point: tuple[float, float]) -> tuple[float, float]:
            transformed = fitz.Point(*point) * transform
            return (
                transformed.x * pixel_scale - pixmap_origin[0],
                transformed.y * pixel_scale - pixmap_origin[1],
            )

        pixel_samples = [to_pixel(point) for point in samples]
        pixel_center = to_pixel(center)
        pixel_start, pixel_end = pixel_samples[0], pixel_samples[-1]
        pixel_angles = [math.atan2(y - pixel_center[1], x - pixel_center[0]) for x, y in pixel_samples]
        pixel_turns = [math.atan2(math.sin(b - a), math.cos(b - a)) for a, b in zip(pixel_angles, pixel_angles[1:])]
        pixel_sweep = math.degrees(sum(pixel_turns))

        # Require source stroke to be present in the rendered image along most
        # of its actual path, relative to both local flanks.
        supported = 0
        checked = 0
        for sample_index in range(0, len(pixel_samples), 4):
            px, py = pixel_samples[sample_index]
            before = pixel_samples[max(0, sample_index - 1)]
            after = pixel_samples[min(len(pixel_samples) - 1, sample_index + 1)]
            tx, ty = after[0] - before[0], after[1] - before[1]
            length = math.hypot(tx, ty)
            if length <= 0:
                continue
            nx, ny = -ty / length, tx / length
            ix, iy = int(round(px)), int(round(py))
            if not (1 <= ix < width - 1 and 1 <= iy < height - 1):
                continue
            center_value = min(int(image[iy, ix]), int(image[iy, ix - 1]), int(image[iy, ix + 1]))
            side_values = []
            for direction in (-1, 1):
                sx = int(round(px + direction * 3.0 * nx))
                sy = int(round(py + direction * 3.0 * ny))
                if 0 <= sx < width and 0 <= sy < height:
                    side_values.append(int(image[sy, sx]))
            if len(side_values) < 2:
                continue
            checked += 1
            supported += int(min(side_values) - center_value >= 20 and center_value <= 210)
        if checked < 8 or supported / checked < 0.75:
            continue

        pixel_radius = radius * pixel_scale
        bbox = (
            min(point[0] for point in pixel_samples),
            min(point[1] for point in pixel_samples),
            max(point[0] for point in pixel_samples),
            max(point[1] for point in pixel_samples),
        )
        results.append(RawArc(
            id=new_id("pdf-arc"),
            center_px=pixel_center,
            radius_px=pixel_radius,
            start_px=pixel_start,
            end_px=pixel_end,
            signed_sweep_deg=pixel_sweep,
            confidence=max(0.8, 1.0 - max(radial_errors) / max(float(width_pt), 0.1)),
            bbox_px=bbox,
            source_pdf_sha256=source_pdf_sha256,
            source_page_index=source_page_index,
            source_transform=tuple(float(value) for value in transform_values),
            render_sha256=hashlib.sha256(rendered_png_bytes).hexdigest(),
            render_dpi=render_dpi,
            render_origin_px=pixmap_origin,
        ))
    return results



def _pdf_source_layer_classification(drawing: dict) -> Optional[str]:
    """Recognize only the two reviewed ISO source-layer names and simple strokes."""
    classification = {
        "Oculto (ISO)": "HIDDEN",
        "Linha de centro (ISO)": "CENTERLINE",
    }.get(drawing.get("layer"))
    width = drawing.get("width")
    level = drawing.get("level")
    if (
        classification is None
        or isinstance(level, bool)
        or not isinstance(level, int)
        or level < 0
        or drawing.get("type") != "s"
        or drawing.get("fill") is not None
        or drawing.get("scissor") is not None
        or drawing.get("stroke_opacity") != 1.0
        or drawing.get("blendmode") not in {None, "Normal"}
        or drawing.get("dashes") != "[] 0"
        or not isinstance(width, (int, float))
        or isinstance(width, bool)
        or not math.isfinite(float(width))
        or width <= 0
    ):
        return None
    items = drawing.get("items")
    if not isinstance(items, (tuple, list)) or len(items) != 1:
        return None
    item = items[0]
    if not isinstance(item, (tuple, list)) or len(item) != 3 or item[0] != "l":
        return None
    return classification


def _line_has_full_pixel_difference_support(
    baseline_rgb: np.ndarray,
    layer_off_rgb: np.ndarray,
    start_px: tuple[float, float],
    end_px: tuple[float, float],
    stroke_width_px: float,
    competing_bounds_px: tuple[tuple[float, float, float, float], ...] = (),
    difference_mask: Optional[np.ndarray] = None,
    competing_strokes_px: tuple[
        tuple[tuple[float, float], tuple[float, float], float], ...
    ] = (),
) -> bool:
    """Require changed pixels to overlap the candidate stroke's raster footprint.

    Toggling an optional-content group removes every path in that group. A
    nearby independent path must not provide the pixel difference used to
    witness this candidate, so pixels touched by another same-group path's paint bounds are
    not evidence for this line. Segments in one PDF stroke path share one paint
    operation, so joins are not treated as independent competing paths.
    Pixel squares are tested against both the
    candidate stroke strip and competing bounds, with a small rasterization
    margin; an arbitrary adjacent row is not source support.
    """
    if (
        not isinstance(baseline_rgb, np.ndarray)
        or not isinstance(layer_off_rgb, np.ndarray)
        or baseline_rgb.ndim not in {2, 3}
        or layer_off_rgb.shape != baseline_rgb.shape
        or (baseline_rgb.ndim == 3 and baseline_rgb.shape[2] < 3)
        or not math.isfinite(stroke_width_px)
        or stroke_width_px <= 0
    ):
        return False
    coordinates = (*start_px, *end_px)
    if not all(math.isfinite(value) for value in coordinates):
        return False
    for bounds in competing_bounds_px:
        if (
            len(bounds) != 4
            or not all(math.isfinite(value) for value in bounds)
            or bounds[0] > bounds[2]
            or bounds[1] > bounds[3]
        ):
            return False
    for first, second, width in competing_strokes_px:
        if (
            len(first) != 2
            or len(second) != 2
            or not all(math.isfinite(value) for value in (*first, *second, width))
            or width <= 0
        ):
            return False
    dx = end_px[0] - start_px[0]
    dy = end_px[1] - start_px[1]
    length = math.hypot(dx, dy)
    if not math.isfinite(length) or length <= 1e-6:
        return False
    if difference_mask is None:
        differences = (
            baseline_rgb != layer_off_rgb
            if baseline_rgb.ndim == 2
            else np.any(baseline_rgb[:, :, :3] != layer_off_rgb[:, :, :3], axis=2)
        )
    else:
        if difference_mask.shape != baseline_rgb.shape[:2] or difference_mask.dtype != np.bool_:
            return False
        differences = difference_mask
    height, width = differences.shape
    normal_x, normal_y = -dy / length, dx / length
    tangent_x, tangent_y = dx / length, dy / length
    normal_pixel_extent = 0.5 * (abs(normal_x) + abs(normal_y))
    tangent_pixel_extent = 0.5 * (abs(tangent_x) + abs(tangent_y))
    sample_count = max(2, int(math.ceil(length * 2.0)))
    sample_half_span = length / sample_count / 2.0
    normal_support = stroke_width_px / 2.0 + normal_pixel_extent
    search_radius = int(math.ceil(normal_support + 1.0))
    if height <= 0 or width <= 0:
        return False
    competing_bounds_margin = 0.25
    samples = sample_count + 1
    sample_fractions = [
        (sample_index + 0.5) / (samples + 1) for sample_index in range(samples)
    ]
    sample_x = np.asarray(
        [start_px[0] + dx * fraction for fraction in sample_fractions],
        dtype=np.float64,
    )
    sample_y = np.asarray(
        [start_px[1] + dy * fraction for fraction in sample_fractions],
        dtype=np.float64,
    )
    pixel_offsets = np.arange(
        -search_radius, search_radius + 2, dtype=np.int64
    )
    pixels_per_sample = int(pixel_offsets.size * pixel_offsets.size)
    # Bound temporary arrays for unusually long, high-resolution paths while
    # still evaluating the exact same per-sample pixel neighborhood.
    samples_per_chunk = max(1, min(samples, 100_000 // max(1, pixels_per_sample)))
    all_offsets_x, all_offsets_y = np.meshgrid(pixel_offsets, pixel_offsets)
    offsets_x = all_offsets_x.ravel()[None, :]
    offsets_y = all_offsets_y.ravel()[None, :]

    vector_rejected = False
    for chunk_start in range(0, samples, samples_per_chunk):
        chunk_end = min(samples, chunk_start + samples_per_chunk)
        x = sample_x[chunk_start:chunk_end, None]
        y = sample_y[chunk_start:chunk_end, None]
        center_x = np.floor(x).astype(np.int64)
        center_y = np.floor(y).astype(np.int64)
        pixel_x = center_x + offsets_x
        pixel_y = center_y + offsets_y
        valid = (pixel_x >= 0) & (pixel_x < width) & (pixel_y >= 0) & (pixel_y < height)
        pixel_center_x = pixel_x + 0.5
        pixel_center_y = pixel_y + 0.5
        offset_x = pixel_center_x - x
        offset_y = pixel_center_y - y
        normal_distance = np.abs(offset_x * normal_x + offset_y * normal_y)
        tangent_distance = np.abs(offset_x * tangent_x + offset_y * tangent_y)
        tangent_support = sample_half_span + tangent_pixel_extent
        normal_inside = normal_distance < normal_support
        tangent_inside = tangent_distance < tangent_support
        eligible = valid & normal_inside & tangent_inside
        boundary_pixels = (
            np.abs(normal_distance - normal_support) <= 1e-12
        ) | (np.abs(tangent_distance - tangent_support) <= 1e-12)
        for row, column in zip(*np.nonzero(boundary_pixels)):
            sample_index = chunk_start + row
            fraction = sample_fractions[sample_index]
            sample_px = start_px[0] + dx * fraction
            sample_py = start_px[1] + dy * fraction
            pixel_offset_x = int(pixel_x[row, column]) + 0.5 - sample_px
            pixel_offset_y = int(pixel_y[row, column]) + 0.5 - sample_py
            normal_inside[row, column] = (
                abs(pixel_offset_x * normal_x + pixel_offset_y * normal_y)
                < normal_support
            )
            tangent_inside[row, column] = (
                abs(pixel_offset_x * tangent_x + pixel_offset_y * tangent_y)
                < tangent_support
            )
        eligible = valid & normal_inside & tangent_inside
        safe_x = np.clip(pixel_x, 0, width - 1)
        safe_y = np.clip(pixel_y, 0, height - 1)
        eligible &= differences[safe_y, safe_x]

        for left, top, right, bottom in competing_bounds_px:
            eligible &= ~(
                (left - competing_bounds_margin < pixel_x + 1.0)
                & (right + competing_bounds_margin > pixel_x)
                & (top - competing_bounds_margin < pixel_y + 1.0)
                & (bottom + competing_bounds_margin > pixel_y)
            )

        pixel_is_competing_stroke = np.zeros(eligible.shape, dtype=np.bool_)
        for stroke_start, stroke_end, other_stroke_width in competing_strokes_px:
            other_dx = stroke_end[0] - stroke_start[0]
            other_dy = stroke_end[1] - stroke_start[1]
            other_length_sq = other_dx * other_dx + other_dy * other_dy
            if not math.isfinite(other_length_sq) or other_length_sq <= 1e-12:
                pixel_is_competing_stroke[:] = True
                break
            projection = (
                (pixel_center_x - stroke_start[0]) * other_dx
                + (pixel_center_y - stroke_start[1]) * other_dy
            ) / other_length_sq
            projection = np.clip(projection, 0.0, 1.0)
            nearest_x = stroke_start[0] + projection * other_dx
            nearest_y = stroke_start[1] + projection * other_dy
            distance = np.hypot(
                pixel_center_x - nearest_x, pixel_center_y - nearest_y
            )
            threshold = other_stroke_width / 2.0 + math.sqrt(0.5)
            competing = distance <= threshold
            for row, column in zip(*np.nonzero(np.abs(distance - threshold) <= 1e-12)):
                pixel_x_center = int(pixel_x[row, column]) + 0.5
                pixel_y_center = int(pixel_y[row, column]) + 0.5
                exact_projection = (
                    (pixel_x_center - stroke_start[0]) * other_dx
                    + (pixel_y_center - stroke_start[1]) * other_dy
                ) / other_length_sq
                exact_projection = max(0.0, min(1.0, exact_projection))
                exact_x = stroke_start[0] + exact_projection * other_dx
                exact_y = stroke_start[1] + exact_projection * other_dy
                competing[row, column] = math.hypot(
                    pixel_x_center - exact_x, pixel_y_center - exact_y
                ) <= threshold
            pixel_is_competing_stroke |= competing
        eligible &= ~pixel_is_competing_stroke
        if not np.all(np.any(eligible, axis=1)):
            vector_rejected = True
            break
    if not vector_rejected:
        return True

    # Preserve the former scalar oracle for candidates the vectorized pass
    # rejects. This exact fallback prevents numerical or broadcasting
    # differences from dropping source-supported strokes.
    for sample_index in range(sample_count + 1):
        fraction = (sample_index + 0.5) / (sample_count + 1)
        x = start_px[0] + dx * fraction
        y = start_px[1] + dy * fraction
        supported = False
        center_x = int(math.floor(x))
        center_y = int(math.floor(y))
        for pixel_y in range(center_y - search_radius, center_y + search_radius + 2):
            for pixel_x in range(center_x - search_radius, center_x + search_radius + 2):
                if not (0 <= pixel_x < width and 0 <= pixel_y < height):
                    continue
                pixel_center_x = pixel_x + 0.5
                pixel_center_y = pixel_y + 0.5
                offset_x = pixel_center_x - x
                offset_y = pixel_center_y - y
                normal_distance = abs(offset_x * normal_x + offset_y * normal_y)
                tangent_distance = offset_x * tangent_x + offset_y * tangent_y
                if (
                    normal_distance >= normal_support
                    or abs(tangent_distance) >= sample_half_span + tangent_pixel_extent
                ):
                    continue
                if any(
                    left - competing_bounds_margin < pixel_x + 1.0
                    and right + competing_bounds_margin > pixel_x
                    and top - competing_bounds_margin < pixel_y + 1.0
                    and bottom + competing_bounds_margin > pixel_y
                    for left, top, right, bottom in competing_bounds_px
                ):
                    continue
                pixel_is_competing_stroke = False
                for stroke_start, stroke_end, other_stroke_width in competing_strokes_px:
                    other_dx = stroke_end[0] - stroke_start[0]
                    other_dy = stroke_end[1] - stroke_start[1]
                    other_length_sq = other_dx * other_dx + other_dy * other_dy
                    if not math.isfinite(other_length_sq) or other_length_sq <= 1e-12:
                        pixel_is_competing_stroke = True
                        break
                    projection = (
                        (pixel_center_x - stroke_start[0]) * other_dx
                        + (pixel_center_y - stroke_start[1]) * other_dy
                    ) / other_length_sq
                    projection = max(0.0, min(1.0, projection))
                    nearest_x = stroke_start[0] + projection * other_dx
                    nearest_y = stroke_start[1] + projection * other_dy
                    if math.hypot(pixel_center_x - nearest_x, pixel_center_y - nearest_y) <= (
                        other_stroke_width / 2.0 + math.sqrt(0.5)
                    ):
                        pixel_is_competing_stroke = True
                        break
                if pixel_is_competing_stroke:
                    continue
                if differences[pixel_y, pixel_x]:
                    supported = True
                    break
            if supported:
                break
        if not supported:
            return False
    return True


def _source_path_pixel_supported_items(
    endpoints_px: list[tuple[tuple[float, float], tuple[float, float]]],
    supported_item_indexes: set[int],
) -> set[int]:
    """Return only source items with their own rendered-pixel support."""
    if not endpoints_px or not supported_item_indexes:
        return set()
    if any(index < 0 or index >= len(endpoints_px) for index in supported_item_indexes):
        return set()
    for first, second in endpoints_px:
        if not all(math.isfinite(value) for point in (first, second) for value in point):
            return set()
        length = math.dist(first, second)
        if not math.isfinite(length) or length <= 1e-6:
            return set()
    return set(supported_item_indexes)


def _source_layer_active_ancestors(
    drawings: list[dict], candidate_index: int
) -> Optional[tuple[tuple[int, dict], ...]]:
    """Resolve clip/group ancestry once for a drawing in PyMuPDF's ordered scope list."""
    if not (0 <= candidate_index < len(drawings)):
        return None
    scopes: list[tuple[int, int, dict]] = []
    for index, drawing in enumerate(drawings[: candidate_index + 1]):
        current_level = drawing.get("level")
        if isinstance(current_level, bool) or not isinstance(current_level, int) or current_level < 0:
            return None
        while scopes and scopes[-1][0] >= current_level:
            scopes.pop()
        if index == candidate_index:
            return tuple((scope_index, scope) for _, scope_index, scope in scopes)
        if drawing.get("type") in {"group", "clip"}:
            scopes.append((current_level, index, drawing))
    return None


def _source_layer_line_has_safe_ancestry(
    drawings: list[dict],
    candidate_index: int,
    full_page_group_index: Optional[int],
    item_index: int = 0,
    active_ancestors: Optional[tuple[tuple[int, dict], ...]] = None,
) -> bool:
    """Reject scoped source strokes unless their clip/compositing context is proven safe."""
    if not (0 <= candidate_index < len(drawings)):
        return False
    candidate = drawings[candidate_index]
    level = candidate.get("level")
    items = candidate.get("items")
    width = candidate.get("width")
    if (
        isinstance(level, bool)
        or not isinstance(level, int)
        or level < 0
        or not isinstance(items, (tuple, list))
        or isinstance(item_index, bool)
        or not isinstance(item_index, int)
        or not (0 <= item_index < len(items))
        or not isinstance(width, (int, float))
        or isinstance(width, bool)
        or not math.isfinite(float(width))
        or width <= 0
    ):
        return False
    item = items[item_index]
    if len(item) != 3 or item[0] != "l":
        return False
    try:
        first = fitz.Point(item[1])
        second = fitz.Point(item[2])
        margin = float(width) / 2.0
        stroke_bounds = fitz.Rect(
            min(first.x, second.x) - margin,
            min(first.y, second.y) - margin,
            max(first.x, second.x) + margin,
            max(first.y, second.y) + margin,
        )
    except (TypeError, ValueError, OverflowError):
        return False
    if not stroke_bounds.is_valid or stroke_bounds.is_empty:
        return False

    # Extended drawing levels form a scope stack. A later sibling at the same
    # level closes the prior clip/group; only active ancestors affect a path.
    if active_ancestors is None:
        active_ancestors = _source_layer_active_ancestors(drawings, candidate_index)
    if active_ancestors is None:
        return False

    for scope_index, scope in active_ancestors:
        if scope.get("type") == "group":
            # Only the separately verified page-level wrapper is considered
            # neutral context. Nested groups are not accepted based on opacity
            # and Normal blend mode alone because their compositing is contextual.
            if scope_index != full_page_group_index:
                return False
        elif scope.get("type") == "clip":
            if not _clip_fully_contains_rect(scope, stroke_bounds):
                return False
    return True


def _pixmap_rgb_array(pixmap: fitz.Pixmap) -> Optional[np.ndarray]:
    if pixmap.n < 3:
        return None
    samples = np.frombuffer(pixmap.samples, dtype=np.uint8)
    expected = pixmap.height * pixmap.width * pixmap.n
    if samples.size != expected:
        return None
    return samples.reshape((pixmap.height, pixmap.width, pixmap.n))[:, :, :3].copy()


def _restore_pdf_optional_content_state(document, expected_configs: list[dict]) -> bool:
    """Restore every saved OCG visibility and verify the complete state by readback."""
    restore_failed = False
    for config in expected_configs:
        number = config.get("number")
        on = config.get("on")
        if (
            isinstance(number, bool)
            or not isinstance(number, int)
            or number < 0
            or isinstance(on, bool)
            or on not in {0, 1}
        ):
            restore_failed = True
            continue
        try:
            document.set_layer_ui_config(
                number, fitz.PDF_OC_ON if on == 1 else fitz.PDF_OC_OFF
            )
        except Exception:
            restore_failed = True
    try:
        observed_configs = document.layer_ui_configs()
    except Exception:
        return False
    return not restore_failed and observed_configs == expected_configs


def _page_pdf_source_layer_line_witnesses(
    page,
    baseline_pixmap: fitz.Pixmap,
    pixel_scale: float,
    pixmap_origin: tuple[int, int],
    *,
    include_pdf_vector_lines: bool = False,
    source_pdf_sha256: Optional[str] = None,
    source_page_index: Optional[int] = None,
    render_dpi: Optional[int] = None,
    _candidate_seqnos: Optional[set[int]] = None,
) -> list[tuple[RawLine, str]] | tuple[list[tuple[RawLine, str]], list[RawPdfLine]]:
    """Return only uniquely addressable ISO layer strokes visible in the page render."""
    if page.rotation not in {0, 90, 180, 270} or not math.isfinite(pixel_scale) or pixel_scale <= 0:
        return []
    document = page.parent
    try:
        ui_configs = document.layer_ui_configs()
        if not isinstance(ui_configs, (tuple, list)) or any(
            not isinstance(config, dict) for config in ui_configs
        ):
            return []
        initial_ui_configs = [dict(config) for config in ui_configs]
        drawings = page.get_drawings(extended=True)
        bboxlog = page.get_bboxlog()
        optional_content_groups = document.get_ocgs()
        page_images = page.get_images(full=True)
        image_info = page.get_image_info(xrefs=True)
    except Exception:
        return []
    config_by_name: dict[str, dict] = {}
    if _candidate_seqnos is not None and (
        not isinstance(_candidate_seqnos, set)
        or any(
            isinstance(seqno, bool) or not isinstance(seqno, int) or seqno < 0
            for seqno in _candidate_seqnos
        )
    ):
        return ([], []) if include_pdf_vector_lines else []
    selected_candidate_layers = {
        drawing.get("layer")
        for drawing in drawings
        if _candidate_seqnos is not None
        and drawing.get("seqno") in _candidate_seqnos
        and isinstance(drawing.get("layer"), str)
    }
    source_names = (
        selected_candidate_layers
        if include_pdf_vector_lines and _candidate_seqnos is not None
        else {
            drawing.get("layer")
            for drawing in drawings
            if isinstance(drawing.get("layer"), str) and drawing.get("layer")
        }
        if include_pdf_vector_lines
        else {"Oculto (ISO)", "Linha de centro (ISO)"}
    )
    for source_name in source_names:
        matches = [config for config in ui_configs if config.get("text") == source_name]
        if len(matches) == 1 and matches[0].get("on") == 1:
            config_by_name[source_name] = matches[0]
    if not config_by_name:
        return []
    try:
        text_spans = page.get_texttrace()
    except Exception:
        return []
    baseline = _pixmap_rgb_array(baseline_pixmap)
    if baseline is None:
        return []
    if include_pdf_vector_lines:
        import cv2

        baseline = cv2.cvtColor(baseline, cv2.COLOR_RGB2GRAY)
    origin_x, origin_y = pixmap_origin
    transform = page.rotation_matrix
    source_layers = {drawing.get("layer") for drawing in drawings}
    difference_by_name: dict[str, np.ndarray] = {}
    for source_name, config in config_by_name.items():
        if source_name not in source_layers:
            continue
        number = config.get("number")
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            continue
        off_pixmap = None
        restore_failed = False
        try:
            document.set_layer_ui_config(number, fitz.PDF_OC_OFF)
            off_pixmap = page.get_pixmap(
                matrix=fitz.Matrix(pixel_scale, pixel_scale), alpha=False
            )
        except Exception:
            off_pixmap = None
        finally:
            restore_failed = not _restore_pdf_optional_content_state(
                document, initial_ui_configs
            )
        if restore_failed:
            raise RuntimeError("Failed to restore PDF optional-content layer state")
        off = _pixmap_rgb_array(off_pixmap) if off_pixmap is not None else None
        if include_pdf_vector_lines and off is not None:
            off = cv2.cvtColor(off, cv2.COLOR_RGB2GRAY)
        if (
            off is None
            or off.shape != baseline.shape
            or off_pixmap.x != baseline_pixmap.x
            or off_pixmap.y != baseline_pixmap.y
        ):
            continue
        difference_by_name[source_name] = off
        del off_pixmap

    competing_bounds_by_layer: dict[str, dict[int, tuple[float, float, float, float]]] = {}
    invalid_competitor_layers: set[str] = set()
    for drawing in drawings:
        source_name = drawing.get("layer")
        if source_name not in difference_by_name:
            continue
        seqno = drawing.get("seqno")
        if (
            isinstance(seqno, bool)
            or not isinstance(seqno, int)
            or not (0 <= seqno < len(bboxlog))
        ):
            invalid_competitor_layers.add(source_name)
            continue
        try:
            record = bboxlog[seqno]
            if len(record) != 2:
                raise ValueError("invalid bounding-box record")
            bounds = fitz.Rect(record[1])
            if (
                not bounds.is_valid
                or bounds.is_empty
                or not all(math.isfinite(value) for value in bounds)
            ):
                raise ValueError("invalid path bounds")
            bounds *= transform
            competing_bounds_by_layer.setdefault(source_name, {})[seqno] = (
                bounds.x0 * pixel_scale - origin_x,
                bounds.y0 * pixel_scale - origin_y,
                bounds.x1 * pixel_scale - origin_x,
                bounds.y1 * pixel_scale - origin_y,
            )
        except (IndexError, TypeError, ValueError, OverflowError):
            invalid_competitor_layers.add(source_name)

    # Text paint is not returned by get_drawings(). Texttrace binds each text
    # paint sequence to its OCG; use the corresponding bboxlog bounds as
    # competing evidence so OCG text cannot impersonate a covered source line.
    for span in text_spans:
        if not isinstance(span, dict):
            invalid_competitor_layers.update(difference_by_name)
            continue
        source_name = span.get("layer")
        if source_name not in difference_by_name:
            continue
        seqno = span.get("seqno")
        if isinstance(seqno, bool) or not isinstance(seqno, int) or not (0 <= seqno < len(bboxlog)):
            invalid_competitor_layers.add(source_name)
            continue
        try:
            record = bboxlog[seqno]
            if len(record) != 2 or record[0] not in {"fill-text", "stroke-text"}:
                raise ValueError("text trace does not match text paint")
            bounds = fitz.Rect(record[1])
            if (
                not bounds.is_valid
                or bounds.is_empty
                or not all(math.isfinite(value) for value in bounds)
            ):
                raise ValueError("invalid text paint bounds")
            bounds *= transform
            bounds_px = (
                bounds.x0 * pixel_scale - origin_x,
                bounds.y0 * pixel_scale - origin_y,
                bounds.x1 * pixel_scale - origin_x,
                bounds.y1 * pixel_scale - origin_y,
            )
            if not all(math.isfinite(value) for value in bounds_px):
                raise ValueError("invalid transformed text paint bounds")
            competing_bounds_by_layer.setdefault(source_name, {})[seqno] = bounds_px
        except (IndexError, TypeError, ValueError, OverflowError):
            invalid_competitor_layers.add(source_name)

    # PDF image paint operations are absent from get_drawings(). An image with
    # its own OCG can therefore change the layer-toggle render inside a vector
    # candidate's stroke even though it has no peer path seqno. Treat its full
    # paint rectangle as competing evidence; transparency cannot be inferred
    # safely from the rectangle alone.
    group_name_by_xref = {
        xref: entry.get("name")
        for xref, entry in optional_content_groups.items()
        if isinstance(xref, int) and isinstance(entry, dict)
    }
    for image in page_images:
        try:
            image_xref = image[0]
            if (
                isinstance(image_xref, bool)
                or not isinstance(image_xref, int)
                or image_xref <= 0
            ):
                invalid_competitor_layers.update(difference_by_name)
                continue
            group_xref = document.get_oc(image_xref)
            if group_xref is None:
                continue
            source_name = group_name_by_xref.get(group_xref)
            if source_name is None:
                invalid_competitor_layers.update(difference_by_name)
                continue
            if source_name not in difference_by_name:
                continue
            image_rects = page.get_image_rects(image_xref)
            if not image_rects:
                invalid_competitor_layers.add(source_name)
                continue
            for image_index, image_rect in enumerate(image_rects):
                bounds = fitz.Rect(image_rect)
                if not bounds.is_valid or bounds.is_empty or not all(math.isfinite(v) for v in bounds):
                    invalid_competitor_layers.add(source_name)
                    continue
                bounds *= transform
                competing_bounds_by_layer.setdefault(source_name, {})[-(image_xref * 1000 + image_index + 1)] = (
                    bounds.x0 * pixel_scale - origin_x,
                    bounds.y0 * pixel_scale - origin_y,
                    bounds.x1 * pixel_scale - origin_x,
                    bounds.y1 * pixel_scale - origin_y,
                )
        except (IndexError, TypeError, ValueError, OverflowError, RuntimeError):
            # If its OCG or bounds cannot be resolved, its pixels cannot be
            # excluded from any active source-layer attribution probe.
            invalid_competitor_layers.update(difference_by_name)
            continue

    # get_images() omits inline PDF images (their xref is zero). Their OCG
    # relationship is not exposed by get_image_info(), so any pixel in their
    # paint rectangle is ambiguous evidence for every source-layer probe.
    # Exclude those rectangles for all probed groups; malformed metadata makes
    # the affected classification fail closed.
    for image_index, image in enumerate(image_info):
        if not isinstance(image, dict):
            invalid_competitor_layers.update(difference_by_name)
            continue
        image_xref = image.get("xref")
        if (
            isinstance(image_xref, bool)
            or not isinstance(image_xref, int)
            or image_xref < 0
        ):
            invalid_competitor_layers.update(difference_by_name)
            continue
        if image_xref != 0:
            continue
        try:
            bounds = fitz.Rect(image["bbox"])
            if (
                not bounds.is_valid
                or bounds.is_empty
                or not all(math.isfinite(value) for value in bounds)
            ):
                raise ValueError("invalid inline image bounds")
            bounds *= transform
            bounds_px = (
                bounds.x0 * pixel_scale - origin_x,
                bounds.y0 * pixel_scale - origin_y,
                bounds.x1 * pixel_scale - origin_x,
                bounds.y1 * pixel_scale - origin_y,
            )
            if not all(math.isfinite(value) for value in bounds_px):
                raise ValueError("invalid transformed inline image bounds")
            for source_name in difference_by_name:
                competing_bounds_by_layer.setdefault(source_name, {})[
                    -(2_000_000_000 + image_index)
                ] = bounds_px
        except (KeyError, TypeError, ValueError, OverflowError):
            invalid_competitor_layers.update(difference_by_name)

    competing_bounds_by_layer_precise: dict[
        str, list[tuple[int, tuple[float, float, float, float]]]
    ] = {name: [] for name in difference_by_name}
    competing_strokes_by_layer_precise: dict[
        str, list[
            tuple[
                int,
                tuple[float, float, float, float],
                tuple[tuple[float, float], tuple[float, float], float],
            ]
        ]
    ] = {name: [] for name in difference_by_name}
    line_path_seqnos_by_layer: dict[str, set[int]] = {}
    for drawing in drawings:
        source_name = drawing.get("layer")
        seqno = drawing.get("seqno")
        items = drawing.get("items")
        width_pt = drawing.get("width")
        if (
            source_name not in difference_by_name
            or isinstance(seqno, bool)
            or not isinstance(seqno, int)
            or not isinstance(items, (tuple, list))
            or not items
            or drawing.get("type") != "s"
            or any(
                not isinstance(item, (tuple, list))
                or len(item) != 3
                or item[0] != "l"
                for item in items
            )
            or isinstance(width_pt, bool)
            or not isinstance(width_pt, (int, float))
            or not math.isfinite(float(width_pt))
            or width_pt <= 0
        ):
            continue
        line_path_seqnos_by_layer.setdefault(source_name, set()).add(seqno)
        stroke_width_px = float(width_pt) * pixel_scale
        margin = stroke_width_px / 2.0 + 1.0
        for item in items:
            try:
                first = fitz.Point(item[1]) * transform
                second = fitz.Point(item[2]) * transform
                first_px = (
                    first.x * pixel_scale - origin_x,
                    first.y * pixel_scale - origin_y,
                )
                second_px = (
                    second.x * pixel_scale - origin_x,
                    second.y * pixel_scale - origin_y,
                )
                bounds = (
                    min(first_px[0], second_px[0]) - margin,
                    min(first_px[1], second_px[1]) - margin,
                    max(first_px[0], second_px[0]) + margin,
                    max(first_px[1], second_px[1]) + margin,
                )
                if not all(math.isfinite(value) for value in (*bounds, *first_px, *second_px)):
                    raise ValueError("non-finite line-item bounds")
                competing_strokes_by_layer_precise[source_name].append(
                    (seqno, bounds, (first_px, second_px, stroke_width_px))
                )
            except (IndexError, TypeError, ValueError, OverflowError):
                invalid_competitor_layers.add(source_name)
                competing_bounds_by_layer_precise[source_name] = []
                line_path_seqnos_by_layer[source_name].clear()
                break
    for source_name, bounds_by_seqno in competing_bounds_by_layer.items():
        precise = competing_bounds_by_layer_precise.setdefault(source_name, [])
        line_path_seqnos = line_path_seqnos_by_layer.get(source_name, set())
        precise.extend(
            (seqno, bounds)
            for seqno, bounds in bounds_by_seqno.items()
            if seqno not in line_path_seqnos
        )

    competing_cell_size = 8.0

    def stroke_cells(
        first: tuple[float, float], second: tuple[float, float], width_px: float
    ) -> Optional[set[tuple[int, int]]]:
        dx = second[0] - first[0]
        dy = second[1] - first[1]
        length = math.hypot(dx, dy)
        if not math.isfinite(length) or length <= 1e-6:
            return None
        steps = max(1, int(math.ceil(length / (competing_cell_size / 2.0))))
        if steps > 10000:
            return None
        radius = 1 + int(math.ceil((width_px / 2.0 + math.sqrt(0.5)) / competing_cell_size))
        cells: set[tuple[int, int]] = set()
        for step in range(steps + 1):
            fraction = step / steps
            cell_x = math.floor((first[0] + dx * fraction) / competing_cell_size)
            cell_y = math.floor((first[1] + dy * fraction) / competing_cell_size)
            for offset_x in range(-radius, radius + 1):
                for offset_y in range(-radius, radius + 1):
                    cells.add((cell_x + offset_x, cell_y + offset_y))
        return cells

    competing_bounds_index: dict[
        str, tuple[dict[tuple[int, int], list[tuple[int, tuple[float, float, float, float]]]],
                   list[tuple[int, tuple[float, float, float, float]]]]
    ] = {}
    for source_name, bounds_entries in competing_bounds_by_layer_precise.items():
        buckets: dict[
            tuple[int, int], list[tuple[int, tuple[float, float, float, float]]]
        ] = {}
        broad: list[tuple[int, tuple[float, float, float, float]]] = []
        for seqno, bounds in bounds_entries:
            x0 = math.floor(bounds[0] / competing_cell_size)
            y0 = math.floor(bounds[1] / competing_cell_size)
            x1 = math.floor(bounds[2] / competing_cell_size)
            y1 = math.floor(bounds[3] / competing_cell_size)
            if (x1 - x0 + 1) * (y1 - y0 + 1) > 256:
                broad.append((seqno, bounds))
                continue
            entry = (seqno, bounds)
            for cell_x in range(x0, x1 + 1):
                for cell_y in range(y0, y1 + 1):
                    buckets.setdefault((cell_x, cell_y), []).append(entry)
        competing_bounds_index[source_name] = (buckets, broad)

    competing_strokes_index: dict[
        str, tuple[
            dict[
                tuple[int, int],
                list[tuple[int, tuple[float, float, float, float], tuple[tuple[float, float], tuple[float, float], float]]],
            ],
            list[tuple[int, tuple[float, float, float, float], tuple[tuple[float, float], tuple[float, float], float]]],
        ]
    ] = {}
    for source_name, entries in competing_strokes_by_layer_precise.items():
        buckets = {}
        broad = []
        for entry in entries:
            seqno, bounds, _ = entry
            _, _, stroke = entry
            cells = stroke_cells(stroke[0], stroke[1], stroke[2])
            if cells is None:
                broad.append(entry)
                continue
            for cell in cells:
                buckets.setdefault(cell, []).append(entry)
        competing_strokes_index[source_name] = (buckets, broad)

    def nearby_competing_bounds(
        source_name: str,
        candidate_seqno: int,
        query: tuple[float, float, float, float],
    ) -> tuple[tuple[float, float, float, float], ...]:
        indexed = competing_bounds_index.get(source_name)
        if indexed is None:
            return ()
        buckets, broad = indexed
        x0 = math.floor(query[0] / competing_cell_size)
        y0 = math.floor(query[1] / competing_cell_size)
        x1 = math.floor(query[2] / competing_cell_size)
        y1 = math.floor(query[3] / competing_cell_size)
        if (x1 - x0 + 1) * (y1 - y0 + 1) > 256:
            candidates = competing_bounds_by_layer_precise[source_name]
        else:
            candidate_entries = set(broad)
            for cell_x in range(x0, x1 + 1):
                for cell_y in range(y0, y1 + 1):
                    candidate_entries.update(buckets.get((cell_x, cell_y), ()))
            candidates = list(candidate_entries)
        return tuple(
            bounds
            for seqno, bounds in candidates
            if seqno != candidate_seqno
            and bounds[0] <= query[2]
            and bounds[2] >= query[0]
            and bounds[1] <= query[3]
            and bounds[3] >= query[1]
        )

    def nearby_competing_strokes(
        source_name: str,
        candidate_seqno: int,
        query: tuple[float, float, float, float],
        start: tuple[float, float],
        end: tuple[float, float],
        width_px: float,
    ) -> tuple[tuple[tuple[float, float], tuple[float, float], float], ...]:
        indexed = competing_strokes_index.get(source_name)
        if indexed is None:
            return ()
        buckets, broad = indexed
        query_cells = stroke_cells(start, end, width_px)
        return _collect_nearby_competing_strokes(
            buckets,
            broad,
            query_cells,
            candidate_seqno,
            query,
            competing_strokes_by_layer_precise[source_name],
        )

    results: list[tuple[RawLine, str]] = []
    seen_seqnos: set[int] = set()
    full_page_group_index = _full_page_transparency_group_index(page, drawings)
    for drawing_index, drawing in enumerate(drawings):
        classification = _pdf_source_layer_classification(drawing)
        if (
            classification is None
            or drawing.get("layer") not in difference_by_name
            or not _source_layer_line_has_safe_ancestry(
                drawings, drawing_index, full_page_group_index
            )
        ):
            continue
        seqno = drawing.get("seqno")
        if (
            isinstance(seqno, bool)
            or not isinstance(seqno, int)
            or seqno < 0
            or seqno >= len(bboxlog)
            or seqno in seen_seqnos
        ):
            continue
        seen_seqnos.add(seqno)
        try:
            record = bboxlog[seqno]
            if len(record) != 2 or record[0] != "stroke-path":
                continue
            source_bounds = fitz.Rect(record[1])
            item = drawing["items"][0]
            first = fitz.Point(item[1]) * transform
            second = fitz.Point(item[2]) * transform
            first_px = (
                first.x * pixel_scale - origin_x,
                first.y * pixel_scale - origin_y,
            )
            second_px = (
                second.x * pixel_scale - origin_x,
                second.y * pixel_scale - origin_y,
            )
            stroke_width_px = float(drawing["width"]) * pixel_scale
        except (IndexError, TypeError, ValueError, OverflowError):
            continue
        if (
            not source_bounds.is_valid
            or source_bounds.is_empty
            or not all(math.isfinite(value) for value in source_bounds)
            or drawing["layer"] in invalid_competitor_layers
            or not all(math.isfinite(value) for point in (first_px, second_px) for value in point)
            or not _line_has_full_pixel_difference_support(
                baseline,
                difference_by_name[drawing["layer"]],
                first_px,
                second_px,
                stroke_width_px,
                tuple(
                    bounds
                    for other_seqno, bounds in competing_bounds_by_layer.get(
                        drawing["layer"], {}
                    ).items()
                    if other_seqno != seqno
                ),
            )
        ):
            continue
        results.append(
            (
                RawLine(
                    id=f"pdf-layer-line-{seqno}",
                    p1_px=first_px,
                    p2_px=second_px,
                    confidence=1.0,
                    bbox_px=(
                        min(first_px[0], second_px[0]),
                        min(first_px[1], second_px[1]),
                        max(first_px[0], second_px[0]),
                        max(first_px[1], second_px[1]),
                    ),
                ),
                classification,
            )
        )
    if not include_pdf_vector_lines:
        return results
    if (
        not isinstance(source_pdf_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", source_pdf_sha256) is None
        or isinstance(source_page_index, bool)
        or not isinstance(source_page_index, int)
        or source_page_index < 0
        or isinstance(render_dpi, bool)
        or not isinstance(render_dpi, int)
        or render_dpi <= 0
    ):
        return results, []

    pdf_vector_lines: list[RawPdfLine] = []
    difference_mask_by_name = {
        name: np.not_equal(baseline, layer_off)
        for name, layer_off in difference_by_name.items()
    }
    full_page_group_index = _full_page_transparency_group_index(page, drawings)
    transform_values = (
        transform.a * pixel_scale,
        transform.b * pixel_scale,
        transform.c * pixel_scale,
        transform.d * pixel_scale,
        transform.e * pixel_scale - origin_x,
        transform.f * pixel_scale - origin_y,
    )
    render_sha256 = hashlib.sha256(baseline_pixmap.tobytes("png")).hexdigest()
    if all(math.isfinite(float(value)) for value in transform_values):
        for drawing_index, drawing in enumerate(drawings):
            source_layer = drawing.get("layer")
            seqno = drawing.get("seqno")
            items = drawing.get("items")
            color = drawing.get("color")
            width_pt = drawing.get("width")
            line_cap = drawing.get("lineCap")
            if _candidate_seqnos is not None and seqno not in _candidate_seqnos:
                continue
            if (
                not isinstance(source_layer, str)
                or not source_layer
                or source_layer not in difference_by_name
                or source_layer in invalid_competitor_layers
                or isinstance(seqno, bool)
                or not isinstance(seqno, int)
                or not (0 <= seqno < len(bboxlog))
                or not isinstance(items, (tuple, list))
                or not items
                or any(
                    not isinstance(item, (tuple, list))
                    or len(item) != 3
                    or item[0] != "l"
                    for item in items
                )
                or drawing.get("type") != "s"
                or drawing.get("fill") is not None
                or drawing.get("stroke_opacity") != 1.0
                or drawing.get("blendmode") not in {None, "Normal"}
                or drawing.get("dashes") != "[] 0"
                or not isinstance(color, (tuple, list))
                or len(color) != 3
                or any(
                    isinstance(channel, bool)
                    or not isinstance(channel, (int, float))
                    or not math.isfinite(float(channel))
                    or not 0.0 <= float(channel) <= 1.0
                    for channel in color
                )
                or isinstance(width_pt, bool)
                or not isinstance(width_pt, (int, float))
                or not math.isfinite(float(width_pt))
                or width_pt <= 0
                or not isinstance(line_cap, (tuple, list))
                or len(line_cap) != 3
                or any(cap not in {0, 1, 2} for cap in line_cap)
            ):
                continue
            active_ancestors = _source_layer_active_ancestors(drawings, drawing_index)
            if active_ancestors is None:
                continue
            try:
                source_kind, source_bounds_value = bboxlog[seqno]
                source_bounds = fitz.Rect(source_bounds_value)
            except (IndexError, TypeError, ValueError, OverflowError):
                continue
            if (
                source_kind != "stroke-path"
                or not source_bounds.is_valid
                or source_bounds.is_empty
                or not all(math.isfinite(value) for value in source_bounds)
            ):
                continue

            endpoints: list[tuple[fitz.Point, fitz.Point]] = []
            segment_keys: set[tuple] = set()
            path_valid = True
            for item in items:
                try:
                    first = fitz.Point(item[1])
                    second = fitz.Point(item[2])
                    coordinates = (first.x, first.y, second.x, second.y)
                    if not all(math.isfinite(float(value)) for value in coordinates):
                        path_valid = False
                        break
                    if first.distance_to(second) <= 1e-6:
                        path_valid = False
                        break
                    key = tuple(
                        sorted(
                            (
                                (round(first.x, 6), round(first.y, 6)),
                                (round(second.x, 6), round(second.y, 6)),
                            )
                        )
                    )
                    if key in segment_keys:
                        path_valid = False
                        break
                    segment_keys.add(key)
                    endpoints.append((first, second))
                except (IndexError, TypeError, ValueError, OverflowError):
                    path_valid = False
                    break
            if not path_valid or len(endpoints) != len(items):
                continue

            stroke_width_px = float(width_pt) * pixel_scale
            if not math.isfinite(stroke_width_px) or stroke_width_px <= 0:
                continue
            transformed_endpoints: list[tuple[tuple[float, float], tuple[float, float]]]=[]
            for first, second in endpoints:
                first_transformed = first * transform
                second_transformed = second * transform
                first_px = (
                    first_transformed.x * pixel_scale - origin_x,
                    first_transformed.y * pixel_scale - origin_y,
                )
                second_px = (
                    second_transformed.x * pixel_scale - origin_x,
                    second_transformed.y * pixel_scale - origin_y,
                )
                if not all(math.isfinite(value) for point in (first_px, second_px) for value in point):
                    path_valid = False
                    break
                transformed_endpoints.append((first_px, second_px))
            if not path_valid:
                continue

            source_path_strokes = {
                (first_px, second_px, stroke_width_px)
                for first_px, second_px in transformed_endpoints
            }

            supported_item_indexes: set[int] = set()
            for sibling_index, (first_px, second_px) in enumerate(transformed_endpoints):
                if not _source_layer_line_has_safe_ancestry(
                    drawings,
                    drawing_index,
                    full_page_group_index,
                    sibling_index,
                    active_ancestors,
                ):
                    path_valid = False
                    break
                margin = stroke_width_px / 2.0 + 2.0
                query_bounds = (
                    min(first_px[0], second_px[0]) - margin,
                    min(first_px[1], second_px[1]) - margin,
                    max(first_px[0], second_px[0]) + margin,
                    max(first_px[1], second_px[1]) + margin,
                )
                competing_bounds = nearby_competing_bounds(
                    source_layer, seqno, query_bounds
                )
                competing_strokes = nearby_competing_strokes(
                    source_layer, seqno, query_bounds, first_px, second_px,
                    stroke_width_px,
                )
                indexed_strokes = competing_strokes_index.get(source_layer)
                nearby_source_strokes = (
                    _collect_nearby_competing_strokes(
                        indexed_strokes[0],
                        indexed_strokes[1],
                        stroke_cells(first_px, second_px, stroke_width_px),
                        -1,
                        query_bounds,
                        competing_strokes_by_layer_precise[source_layer],
                    )
                    if indexed_strokes is not None
                    else ()
                )
                def sibling_can_compete(
                    other_start: tuple[float, float],
                    other_end: tuple[float, float],
                    other_stroke_width: float,
                ) -> bool:
                    """Whether another item can explain this item's pixels.

                    The pixel-footprint check below limits competition to
                    pixels the sibling can actually explain. Include a
                    shared-endpoint sibling only when their raster footprints
                    overlap beyond the local join.
                    """
                    shared = {
                        point
                        for point in (first_px, second_px)
                        if point in {other_start, other_end}
                    }
                    if len(shared) != 1:
                        return True
                    # A subpixel-scale source item may have no independently
                    # resolvable pixels beyond its join, so keep its sibling
                    # as a competing witness even when endpoints connect.
                    candidate_length = math.dist(first_px, second_px)
                    other_length = math.dist(other_start, other_end)
                    if candidate_length <= 1.0:
                        return True
                    join_x, join_y = next(iter(shared))
                    other_tip = other_end if other_start == (join_x, join_y) else other_start
                    candidate_tip = second_px if first_px == (join_x, join_y) else first_px
                    candidate_dx = candidate_tip[0] - join_x
                    candidate_dy = candidate_tip[1] - join_y
                    other_dx = other_tip[0] - join_x
                    other_dy = other_tip[1] - join_y
                    dot = candidate_dx * other_dx + candidate_dy * other_dy
                    if dot <= 0:
                        return False
                    sine = abs(candidate_dx * other_dy - candidate_dy * other_dx) / (
                        candidate_length * other_length
                    )
                    competing_radius = other_stroke_width / 2.0 + math.sqrt(0.5)
                    projected_overlap = min(
                        candidate_length,
                        dot / candidate_length,
                    )
                    if sine > 1e-12:
                        projected_overlap = min(
                            projected_overlap, competing_radius / sine
                        )
                    if other_length <= 1.0:
                        # A short sibling can explain a short candidate's
                        # entire sampled extent even when it is too short to
                        # explain a longer line. Match the last sample used by
                        # _line_has_full_pixel_difference_support and include
                        # the sibling's raster footprint when deciding.
                        sample_count = max(2, math.ceil(candidate_length * 2.0))
                        last_sample_fraction = (sample_count + 0.5) / (
                            sample_count + 2.0
                        )
                        last_sample_distance = candidate_length * last_sample_fraction
                        return projected_overlap + competing_radius >= last_sample_distance
                    # Ignore a one-pixel-scale contact at an ordinary join.
                    raster_footprint_diameter = (
                        other_stroke_width + 2.0 * math.sqrt(0.5)
                    )
                    return projected_overlap > raster_footprint_diameter

                competing_strokes += tuple(
                    other_stroke for other_stroke in nearby_source_strokes
                    if other_stroke in source_path_strokes
                    and other_stroke != (first_px, second_px, stroke_width_px)
                    and sibling_can_compete(
                        other_stroke[0], other_stroke[1], other_stroke[2]
                    )
                )
                has_pixel_support = _line_has_full_pixel_difference_support(
                    baseline,
                    difference_by_name[source_layer],
                    first_px,
                    second_px,
                    stroke_width_px,
                    competing_bounds,
                    difference_mask_by_name.get(source_layer),
                    competing_strokes,
                )
                if has_pixel_support:
                    supported_item_indexes.add(sibling_index)
            if not path_valid:
                continue
            admitted_item_indexes = _source_path_pixel_supported_items(
                transformed_endpoints, supported_item_indexes
            )
            if not admitted_item_indexes:
                continue

            encoded_layer = quote(source_layer, safe="")
            for item_index, (first_px, second_px) in enumerate(transformed_endpoints):
                if item_index not in admitted_item_indexes:
                    continue
                pdf_vector_lines.append(RawPdfLine(
                    id=(
                        f"pdf-vector-line-{source_pdf_sha256[:16]}-p{source_page_index}"
                        f"-s{seqno}-i{item_index}-layer-{encoded_layer}"
                    ),
                    p1_px=first_px,
                    p2_px=second_px,
                    confidence=1.0,
                    bbox_px=(
                        min(first_px[0], second_px[0]),
                        min(first_px[1], second_px[1]),
                        max(first_px[0], second_px[0]),
                        max(first_px[1], second_px[1]),
                    ),
                    source_pdf_sha256=source_pdf_sha256,
                    source_page_index=source_page_index,
                    source_transform=tuple(float(value) for value in transform_values),
                    render_sha256=render_sha256,
                    render_dpi=render_dpi,
                    render_origin_px=pixmap_origin,
                    source_layer=source_layer,
                    source_seqno=seqno,
                    source_item_index=item_index,
                ))
    return results, pdf_vector_lines

def _opaque_stroke_fully_covers_line(
    drawing: dict,
    line_start: fitz.Point,
    line_end: fitz.Point,
    source_width_pt: float,
    source_line_cap: tuple[int, int, int],
) -> bool:
    """Prove a later opaque background stroke covers one complete line witness."""
    color = drawing.get("color")
    width = drawing.get("width")
    items = drawing.get("items", [])
    cover_line_cap = drawing.get("lineCap")
    caps_match = cover_line_cap == source_line_cap
    butt_source_is_contained = (
        isinstance(source_line_cap, (tuple, list))
        and len(source_line_cap) == 3
        and all(cap == 0 for cap in source_line_cap)
        and isinstance(cover_line_cap, (tuple, list))
        and len(cover_line_cap) == 3
        and all(cap in (0, 1, 2) for cap in cover_line_cap)
    )
    if (
        drawing.get("type") != "s"
        or drawing.get("fill") is not None
        or drawing.get("stroke_opacity") != 1.0
        or drawing.get("dashes") != "[] 0"
        or not (caps_match or butt_source_is_contained)
        or not isinstance(color, (tuple, list))
        or len(color) != 3
        or any(
            not isinstance(channel, (int, float))
            or not math.isfinite(float(channel))
            or float(channel) < 0.95
            for channel in color
        )
        or not isinstance(width, (int, float))
        or not math.isfinite(float(width))
        or not math.isfinite(source_width_pt)
        or width <= source_width_pt
    ):
        return False

    line_dx = line_end.x - line_start.x
    line_dy = line_end.y - line_start.y
    line_length = math.hypot(line_dx, line_dy)
    if not math.isfinite(line_length) or line_length <= 1e-9:
        return False
    direction = (line_dx / line_length, line_dy / line_length)
    cover_radius = (float(width) - source_width_pt) / 2.0
    epsilon = 1e-7

    # A line or one cubic is sufficient when its entire control polygon stays
    # within the cover radius of the witness and advances monotonically from
    # one endpoint to the other. The cubic's convex hull then proves continuous
    # coverage; a broad bbox alone is never enough.
    for item in items:
        if not isinstance(item, (tuple, list)) or not item:
            continue
        if item[0] == "l" and len(item) == 3:
            controls = item[1:3]
        elif item[0] == "c" and len(item) == 5:
            controls = item[1:5]
        else:
            continue
        try:
            points = [(float(point.x), float(point.y)) for point in controls]
        except (AttributeError, TypeError, ValueError, OverflowError):
            continue
        if not all(math.isfinite(value) for point in points for value in point):
            continue
        projections = []
        perpendicular = []
        for x, y in points:
            relative_x, relative_y = x - line_start.x, y - line_start.y
            projections.append(relative_x * direction[0] + relative_y * direction[1])
            perpendicular.append(abs(relative_x * direction[1] - relative_y * direction[0]))
        if any(distance > cover_radius + epsilon for distance in perpendicular):
            continue
        increasing = all(
            later >= earlier - epsilon
            for earlier, later in zip(projections, projections[1:])
        )
        decreasing = all(
            later <= earlier + epsilon
            for earlier, later in zip(projections, projections[1:])
        )
        if (increasing or decreasing) and min(projections[0], projections[-1]) <= epsilon and max(
            projections[0], projections[-1]
        ) >= line_length - epsilon:
            return True
    return False


def _page_vector_line_witnesses(
    page,
    pixel_scale: float,
    pixmap_origin: tuple[int, int],
) -> list[RawLine]:
    """Return simple PDF strokes that can corroborate already-detected raster lines.

    These witnesses do not create Primitive IR geometry. They only prevent the
    image owner from discarding a Hough line that matches an independent source
    stroke merely because it lies close to a separately admitted PDF ARC.
    """
    if page.rotation not in {0, 90, 180, 270}:
        return []
    transform = page.rotation_matrix
    origin_x, origin_y = pixmap_origin
    bboxlog = page.get_bboxlog()
    drawings = page.get_drawings(extended=True)
    drawing_by_seqno: dict[int, dict] = {}
    for drawing in drawings:
        seqno = drawing.get("seqno")
        if seqno is None:
            continue
        if (
            isinstance(seqno, bool)
            or not isinstance(seqno, int)
            or seqno < 0
            or seqno >= len(bboxlog)
            or seqno in drawing_by_seqno
            or not isinstance(bboxlog[seqno], (tuple, list))
            or len(bboxlog[seqno]) != 2
        ):
            # A partial or ambiguous sequence map cannot support line witnesses.
            return []
        drawing_by_seqno[seqno] = drawing
    results: list[RawLine] = []
    for drawing in drawings:
        color = drawing.get("color")
        width_pt = drawing.get("width")
        seqno = drawing.get("seqno")
        items = drawing.get("items", [])
        if (
            drawing.get("type") != "s"
            or drawing.get("fill") is not None
            or drawing.get("level") != 0
            or not isinstance(color, (tuple, list))
            or len(color) != 3
            or any(
                not math.isfinite(float(channel)) or float(channel) > 0.45
                for channel in color
            )
            or not isinstance(width_pt, (int, float))
            or not math.isfinite(float(width_pt))
            or width_pt <= 0
            or drawing.get("stroke_opacity") != 1.0
            or drawing.get("dashes") != "[] 0"
            or not isinstance(seqno, int)
            or seqno < 0
            or len(items) != 1
            or items[0][0] != "l"
        ):
            continue
        if seqno >= len(bboxlog) or len(bboxlog[seqno]) != 2:
            continue
        try:
            source_kind, source_bounds = bboxlog[seqno]
            source_paint_rect = fitz.Rect(source_bounds)
        except (IndexError, TypeError, ValueError, OverflowError):
            continue
        if (
            source_kind != "stroke-path"
            or not source_paint_rect.is_valid
            or source_paint_rect.is_empty
            or not all(math.isfinite(value) for value in source_paint_rect)
        ):
            continue

        # A source path is not a valid line witness when a later non-stroke
        # paint fully covers its recorded stroke bounds. Stroke-path bounds
        # are not enough to prove occlusion: a later arc may only touch this
        # line at its tangent point, while an opaque fill/image/text can erase
        # the whole stroke without changing the source drawing record.
        hidden_by_later_fill = False
        for later_seqno, later_record in enumerate(
            bboxlog[seqno + 1 :], start=seqno + 1
        ):
            if len(later_record) != 2:
                hidden_by_later_fill = True
                break
            later_kind, later_bounds = later_record
            try:
                later_rect = fitz.Rect(later_bounds)
            except (TypeError, ValueError, OverflowError):
                hidden_by_later_fill = True
                break
            if (
                not later_rect.is_valid
                or not all(math.isfinite(value) for value in later_rect)
            ):
                hidden_by_later_fill = True
                break
            if later_kind == "stroke-path":
                if later_rect.contains(source_paint_rect):
                    later_drawing = drawing_by_seqno.get(later_seqno)
                    if later_drawing is None or later_drawing.get("type") not in {"s", "fs"}:
                        hidden_by_later_fill = True
                        break
                    if _opaque_stroke_fully_covers_line(
                        later_drawing,
                        fitz.Point(items[0][1]),
                        fitz.Point(items[0][2]),
                        float(width_pt),
                        tuple(drawing.get("lineCap", ())),
                    ):
                        hidden_by_later_fill = True
                        break
                continue
            if later_rect.contains(source_paint_rect):
                hidden_by_later_fill = True
                break
        if hidden_by_later_fill:
            continue
        try:
            first = fitz.Point(items[0][1]) * transform
            second = fitz.Point(items[0][2]) * transform
            first_px = (
                first.x * pixel_scale - origin_x,
                first.y * pixel_scale - origin_y,
            )
            second_px = (
                second.x * pixel_scale - origin_x,
                second.y * pixel_scale - origin_y,
            )
        except (IndexError, TypeError, ValueError, OverflowError):
            continue
        if not all(
            math.isfinite(value)
            for point in (first_px, second_px)
            for value in point
        ):
            continue
        if math.dist(first_px, second_px) <= 1e-6:
            continue
        results.append(
            RawLine(
                id=f"pdf-line-witness-{seqno}",
                p1_px=first_px,
                p2_px=second_px,
                confidence=1.0,
                bbox_px=(
                    min(first_px[0], second_px[0]),
                    min(first_px[1], second_px[1]),
                    max(first_px[0], second_px[0]),
                    max(first_px[1], second_px[1]),
                ),
            )
        )
    return results


def run_pdf(
    pdf_path: Path,
    output_dir: Path,
    scale_mm_per_px: Optional[float] = None,
    dpi: int = 144,
    preset: str = "real_scan_tuned_v1",
    merge_lines: bool = False,
    auto_ocr_roi: bool = False,
    auto_calibrate: bool = False,
    calibration_registry_path: Optional[Path] = None,
    calibration_id_prefix: Optional[str] = None,
) -> dict:
    """Render each PDF page locally and emit a validated Primitive IR JSON.

    scale_mm_per_px vẫn là cách khuyến nghị (đã verify). Nếu để None, cần
    auto_calibrate=True — mỗi trang PDF là 1 ảnh khác nhau nên tỷ lệ được
    suy riêng cho từng trang (không giả định các trang cùng scale), và nếu
    có calibration_registry_path thì mỗi trang ghi 1 record riêng với id
    "{calibration_id_prefix}_page{N:02d}", status=needs_verification — xem
    cảnh báo an toàn trong run_image.run()/auto_estimate_calibration().
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    if scale_mm_per_px is not None and not _is_valid_manual_scale(scale_mm_per_px):
        raise ValueError("scale_mm_per_px must be a finite positive number")
    if scale_mm_per_px is None and not auto_calibrate:
        raise ValueError("Cần scale_mm_per_px hoặc bật auto_calibrate=True")
    if auto_calibrate and calibration_registry_path is not None and not calibration_id_prefix:
        raise ValueError("calibration_registry_path cần đi kèm calibration_id_prefix")

    source_pdf_bytes = pdf_path.read_bytes()
    source_pdf_sha256 = hashlib.sha256(source_pdf_bytes).hexdigest()

    render_dir = output_dir / "rendered"
    ir_dir = output_dir / "primitive_ir"
    manifest_path = output_dir / "manifest.json"
    _validate_pdf_output_directory(output_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    manifest = {
        "status": "in_progress",
        "source_pdf": pdf_path.name,
        "source_pdf_sha256": source_pdf_sha256,
        "render_dpi": dpi,
        "scale_mm_per_px": scale_mm_per_px if scale_mm_per_px is not None else "auto",
        "pdf_vector_text_visibility": "not_assessed",
        "pages": [],
    }
    from cad_agent.manifest import write_manifest

    _validate_pdf_output_path(manifest_path, output_dir, pdf_path, atomic_replace=True)
    write_manifest(manifest_path, manifest)
    document = None
    current_page_index = None
    try:
        _validate_pdf_output_tree(output_dir, pdf_path, manifest_path)
        _validate_pdf_output_directory(output_dir, render_dir)
        _validate_pdf_output_directory(output_dir, ir_dir)
        render_dir.mkdir(parents=True, exist_ok=True)
        ir_dir.mkdir(parents=True, exist_ok=True)
        _validate_pdf_output_tree(output_dir, pdf_path, manifest_path)
        document = fitz.open(stream=source_pdf_bytes, filetype="pdf")
        for index, page in enumerate(document, start=1):
            current_page_index = index - 1
            require_all_vector_witnesses, vector_circle_witnesses, suspect_regions = (
                _page_circle_witnesses(page, scale)
            )
            image_path = render_dir / f"page_{index:02d}.png"
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            rendered_png_bytes = pixmap.tobytes("png")
            rendered_png_sha256 = hashlib.sha256(rendered_png_bytes).hexdigest()
            _write_pdf_output(
                image_path,
                output_dir,
                pdf_path,
                lambda path: path.write_bytes(rendered_png_bytes),
            )
            pdf_vector_arcs = _page_vector_arcs(
                page,
                rendered_png_bytes,
                scale,
                (pixmap.x, pixmap.y),
                dpi,
                manifest["source_pdf_sha256"],
                index - 1,
            )
            source_line_result = _page_pdf_source_layer_line_witnesses(
                page,
                pixmap,
                scale,
                (pixmap.x, pixmap.y),
                include_pdf_vector_lines=True,
                source_pdf_sha256=manifest["source_pdf_sha256"],
                source_page_index=index - 1,
                render_dpi=dpi,
            )
            if isinstance(source_line_result, tuple):
                pdf_layer_line_witnesses, pdf_vector_lines = source_line_result
            else:
                pdf_layer_line_witnesses, pdf_vector_lines = source_line_result, []
            pdf_vector_line_witnesses = (
                _page_vector_line_witnesses(page, scale, (pixmap.x, pixmap.y))
                if pdf_vector_arcs
                else []
            )
            if auto_ocr_roi:
                pdf_vector_texts, pdf_text_status, skipped_pdf_text_spans = _page_vector_texts(
                    page,
                    scale,
                    (pixmap.x, pixmap.y),
                    (pixmap.width, pixmap.height),
                )
            else:
                # The existing auto-OCR opt-out is the explicit geometry-only
                # mode; keep that contract free of newly surfaced text.
                pdf_vector_texts, pdf_text_status, skipped_pdf_text_spans = [], "disabled", 0
            output_path = ir_dir / f"page_{index:02d}.json"
            view_candidates_path = ir_dir / f"page_{index:02d}.view_candidates.json"
            page_calibration_id = (
                f"{calibration_id_prefix}_page{index:02d}"
                if (auto_calibrate and calibration_registry_path is not None)
                else None
            )
            vector_kwargs = {}
            text_conflict_report = {
                "ocr_text_state": "unverified" if auto_ocr_roi else "disabled",
                "ocr_pdf_conflict_count": 0,
                "excluded_ocr_text_span_count": 0,
                "excluded_pdf_text_span_count": 0,
            }
            if require_all_vector_witnesses or vector_circle_witnesses or suspect_regions:
                vector_kwargs = {
                    "validated_pdf_vector_circle_witnesses": vector_circle_witnesses,
                    "pdf_vector_circle_suspect_regions": suspect_regions,
                    "require_pdf_vector_circle_witness": require_all_vector_witnesses,
                }
            if pdf_vector_arcs:
                vector_kwargs["pdf_vector_arcs"] = pdf_vector_arcs
            if pdf_vector_line_witnesses:
                vector_kwargs["pdf_vector_line_witnesses"] = pdf_vector_line_witnesses
            if pdf_layer_line_witnesses:
                vector_kwargs["pdf_layer_line_witnesses"] = pdf_layer_line_witnesses
            if pdf_vector_lines:
                vector_kwargs["pdf_vector_lines"] = pdf_vector_lines

            def process_page_ir(path: Path) -> None:
                (
                    candidates_temp,
                    candidates_parent_identity,
                    candidates_descriptor,
                    candidates_created_identity,
                ) = _create_pdf_output_temp(view_candidates_path, output_dir, pdf_path)
                try:
                    run(
                        image_path=str(image_path),
                        output_path=str(path),
                        scale_mm_per_px=scale_mm_per_px,
                        preset=preset,
                        merge_lines=merge_lines,
                        auto_ocr_roi=auto_ocr_roi,
                        auto_calibrate=auto_calibrate,
                        calibration_registry_path=calibration_registry_path,
                        calibration_id=page_calibration_id,
                        view_candidates_output_path=str(candidates_temp),
                        view_candidates_dpi=dpi,
                        pdf_vector_texts=pdf_vector_texts,
                        text_conflict_report=text_conflict_report,
                        source_page_index=index - 1,
                        image_bytes=rendered_png_bytes,
                        **vector_kwargs,
                    )
                    if _sha256_file(image_path) != rendered_png_sha256:
                        raise ValueError(
                            "PDF rendered page changed while its source-bound image was extracted."
                        )
                    candidates_stat, candidates_size, candidates_sha256 = (
                        _descriptor_sha256(candidates_descriptor)
                    )
                    os.close(candidates_descriptor)
                    candidates_descriptor = -1
                    _validate_pdf_output_path(
                        candidates_temp, output_dir, pdf_path
                    )
                    _publish_pdf_output_temp(
                        candidates_temp,
                        view_candidates_path,
                        output_dir,
                        pdf_path,
                        candidates_parent_identity,
                        candidates_stat,
                        candidates_size,
                        candidates_sha256,
                    )
                finally:
                    if candidates_descriptor >= 0:
                        os.close(candidates_descriptor)
                    _cleanup_owned_pdf_output_temp(
                        candidates_temp, candidates_created_identity
                    )

            _write_pdf_output(output_path, output_dir, pdf_path, process_page_ir)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            scale_label_candidates = json.loads(view_candidates_path.read_text(encoding="utf-8"))
            _materialize_view_children(
                scale_label_candidates,
                image_path,
                output_dir,
                pdf_path,
                index,
                preset,
                merge_lines,
            )
            if _sha256_file(image_path) != rendered_png_sha256:
                raise ValueError("PDF rendered page changed before its source checkpoint was recorded.")
            _write_pdf_output(
                view_candidates_path,
                output_dir,
                pdf_path,
                lambda path: path.write_text(
                    json.dumps(scale_label_candidates, indent=2) + "\n",
                    encoding="utf-8",
                ),
            )
            manifest["pages"].append(
                {
                    "page_index": index - 1,
                    "page": index,
                    "page_rotation": page.rotation,
                    "page_cropbox": [round(float(value), 8) for value in page.cropbox],
                    "page_rotation_matrix": _matrix_values(page.rotation_matrix),
                    "render_scale_px_per_point": scale,
                    "pixmap_origin_px": [pixmap.x, pixmap.y],
                    "rendered_png": str(image_path.relative_to(output_dir)),
                    "rendered_png_sha256": rendered_png_sha256,
                    "primitive_ir": str(output_path.relative_to(output_dir)),
                    "pdf_vector_text_status": pdf_text_status,
                    "pdf_vector_arc_count": len(pdf_vector_arcs),
                    "skipped_pdf_vector_text_span_count": skipped_pdf_text_spans,
                    "excluded_unverified_pdf_vector_text_span_count": len(pdf_vector_texts),
                    **(
                        {"pdf_text_conflict_policy_version": PDF_TEXT_CONFLICT_POLICY_VERSION}
                        if auto_ocr_roi
                        else {}
                    ),
                    **text_conflict_report,
                    "primitive_count": len(payload["primitives"]),
                    "cross_validation_count": len(payload["cross_validations"]),
                    "calibration_method": payload["calibration"]["method"],
                    "scale_mm_per_px": payload["calibration"]["pixel_to_unit_scale"],
                    "scale_label_candidates": scale_label_candidates,
                }
            )
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["failed_page_index"] = current_page_index
        manifest["error"] = {"type": type(exc).__name__, "message": str(exc)}
        _validate_pdf_output_path(manifest_path, output_dir, pdf_path, atomic_replace=True)
        write_manifest(manifest_path, manifest)
        raise
    finally:
        if document is not None:
            document.close()
    manifest["status"] = "complete"
    _validate_pdf_output_path(manifest_path, output_dir, pdf_path, atomic_replace=True)
    write_manifest(manifest_path, manifest)
    return manifest


def main() -> int:
    _configure_console_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--scale-mm-per-px", type=float, help="Tỷ lệ mm/px đã xác minh, áp dụng cho mọi trang"
    )
    parser.add_argument(
        "--calibration-registry",
        type=Path,
        help="Hash-bound calibration registry JSON (verified scale, mode thủ công)",
    )
    parser.add_argument(
        "--calibration-id",
        help="Verified calibration record ID (registry mode thủ công, không dùng cùng --auto-calibrate)",
    )
    parser.add_argument(
        "--auto-ocr-roi",
        action="store_true",
        help="Tự động phát hiện vùng ứng viên chứa text thay vì cần --ocr-roi thủ công",
    )
    parser.add_argument(
        "--auto-calibrate",
        action="store_true",
        help="Suy tỷ lệ mm/px tự động cho TỪNG TRANG (mỗi trang 1 ảnh khác nhau). "
        "KẾT QUẢ CHƯA VERIFY — chỉ dùng để khảo sát/test. Kết hợp với "
        "--calibration-registry + --calibration-id (dùng làm prefix, mỗi "
        "trang ghi record riêng '<id>_pageNN' status=needs_verification).",
    )
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument(
        "--preset", choices=("default", "real_scan_tuned_v1"), default="real_scan_tuned_v1"
    )
    parser.add_argument("--merge-lines", action="store_true")
    args = parser.parse_args()

    try:
        scale_mm_per_px: Optional[float] = None
        registry_for_run: Optional[Path] = None
        calibration_id_prefix: Optional[str] = None

        if args.auto_calibrate:
            if args.scale_mm_per_px is not None:
                parser.error("--auto-calibrate không dùng cùng --scale-mm-per-px")
            if args.calibration_registry and not args.calibration_id:
                parser.error(
                    "--calibration-registry với --auto-calibrate cần thêm --calibration-id (dùng làm prefix)"
                )
            registry_for_run = args.calibration_registry
            calibration_id_prefix = args.calibration_id
        elif args.calibration_registry:
            if not args.calibration_id or args.scale_mm_per_px is not None:
                parser.error(
                    "Registry mode (verified) requires --calibration-id and no --scale-mm-per-px"
                )
            # Chế độ thủ công: 1 registry record verified dùng chung cho cả PDF
            # (đại diện bởi chính file PDF gốc, không phải từng trang render).
            scale_mm_per_px = get_verified_scale(
                args.calibration_registry, args.calibration_id, args.pdf
            )
        elif args.scale_mm_per_px is not None:
            scale_mm_per_px = args.scale_mm_per_px
        else:
            parser.error(
                "Supply --scale-mm-per-px, --auto-calibrate, or a verified calibration registry"
            )

        manifest = run_pdf(
            args.pdf,
            args.output_dir,
            scale_mm_per_px,
            args.dpi,
            args.preset,
            args.merge_lines,
            auto_ocr_roi=args.auto_ocr_roi,
            auto_calibrate=args.auto_calibrate,
            calibration_registry_path=registry_for_run,
            calibration_id_prefix=calibration_id_prefix,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(
        f"PDF Primitive IR saved: {args.output_dir / 'manifest.json'} ({len(manifest['pages'])} pages)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
