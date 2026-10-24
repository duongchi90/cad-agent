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
import stat
import sys
import tempfile
from pathlib import Path
from typing import Optional

import fitz
import numpy as np

from .calibration_registry import get_verified_scale
from .models import new_id
from .run_image import run
from .text_extraction import RawText


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


def _clip_fully_contains_circle(
    drawing: dict, center_x: float, center_y: float, radius: float
) -> bool:
    """Prove an axis-aligned clip rectangle leaves a candidate circle intact."""
    scissor = drawing.get("scissor")
    items = drawing.get("items", [])
    if drawing.get("type") != "clip" or scissor is None or len(items) != 4:
        return False

    segments: list[tuple[fitz.Point, fitz.Point]] = []
    for item in items:
        if item[0] != "l":
            return False
        _, start, end = item
        if abs(start.x - end.x) > 0.02 and abs(start.y - end.y) > 0.02:
            return False
        segments.append((start, end))
    if any(
        math.hypot(
            segments[index][1].x - segments[(index + 1) % 4][0].x,
            segments[index][1].y - segments[(index + 1) % 4][0].y,
        )
        > 0.02
        for index in range(4)
    ):
        return False

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
        return False

    margin = 0.02
    return (
        scissor.x0 <= center_x - radius + margin
        and scissor.y0 <= center_y - radius + margin
        and scissor.x1 >= center_x + radius - margin
        and scissor.y1 >= center_y + radius - margin
        and x0 <= center_x - radius + margin
        and y0 <= center_y - radius + margin
        and x1 >= center_x + radius - margin
        and y1 >= center_y + radius - margin
    )


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


def _dimension_arrowhead_fill(
    drawings: list[dict],
    fill_index: int,
    circle: tuple[float, float, float],
) -> bool:
    """Recognize only a small filled triangle joined to an axis and outward leader.

    Tolerances are in PDF page points: 0.05 for closed-path continuity, 0.5
    for stroke-to-fill attachment, and 10 degrees for opposite collinear axes.
    The local overprint is capped at 8 percent of the candidate circumference;
    triangle edges are capped at 12 points and its area at 40 square points.
    """
    if not 0 < fill_index < len(drawings) - 1:
        return False
    fill = drawings[fill_index]
    if fill.get("type") not in {"f", "fs"} or fill.get("fill") is None:
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


def _page_circle_witnesses(
    page: fitz.Page, pixel_scale: float
) -> tuple[bool, list[tuple[float, float, float]], list[dict]]:
    """Return global fail-closed state, full-circle witnesses, and suspect regions."""
    drawings = page.get_drawings(extended=True)
    if not drawings:
        return False, [], []
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
        witness_level = int(drawing.get("level") or 0)
        prior_clip_context = any(
            int(prior.get("level") or 0) < witness_level
            and (
                prior.get("type") == "group"
                or (
                    prior.get("type") == "clip"
                    and not _clip_fully_contains_circle(prior, cx, cy, radius)
                )
            )
            for prior in drawings[:path_start_index]
        )
        if prior_clip_context:
            suspect_regions.append(_suspect_geometry(drawing, pixel_scale, page_transform))
            continue

        # A later drawing/clip/group touching this perimeter can obscure or
        # alter the witness. Conservatively reject rather than infer visibility.
        occluded = False
        drawing_sequence = drawing.get("seqno")
        occluder_rects = annotation_rects + [
            rect
            for sequence, rect in image_paint_operations
            if drawing_sequence is None or sequence < 0 or sequence > drawing_sequence
        ]
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

    render_dir = output_dir / "rendered"
    ir_dir = output_dir / "primitive_ir"
    manifest_path = output_dir / "manifest.json"
    _validate_pdf_output_directory(output_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    manifest = {
        "status": "in_progress",
        "source_pdf": pdf_path.name,
        "source_pdf_sha256": _sha256_file(pdf_path),
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
        document = fitz.open(str(pdf_path))
        for index, page in enumerate(document, start=1):
            current_page_index = index - 1
            require_all_vector_witnesses, vector_circle_witnesses, suspect_regions = (
                _page_circle_witnesses(page, scale)
            )
            image_path = render_dir / f"page_{index:02d}.png"
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            _write_pdf_output(
                image_path,
                output_dir,
                pdf_path,
                lambda path: path.write_bytes(pixmap.tobytes("png")),
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
            if require_all_vector_witnesses or vector_circle_witnesses or suspect_regions:
                vector_kwargs = {
                    "pdf_vector_circle_witnesses": vector_circle_witnesses,
                    "pdf_vector_circle_suspect_regions": suspect_regions,
                    "require_pdf_vector_circle_witness": require_all_vector_witnesses,
                }
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
                        source_page_index=index - 1,
                        **vector_kwargs,
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
                    "rendered_png_sha256": _sha256_file(image_path),
                    "primitive_ir": str(output_path.relative_to(output_dir)),
                    "pdf_vector_text_status": pdf_text_status,
                    "skipped_pdf_vector_text_span_count": skipped_pdf_text_spans,
                    "excluded_unverified_pdf_vector_text_span_count": len(pdf_vector_texts),
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
