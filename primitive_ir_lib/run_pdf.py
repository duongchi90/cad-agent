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
import sys
from pathlib import Path
from typing import Optional

import fitz
import numpy as np

from .calibration_registry import get_verified_scale
from .run_image import run


def _candidate_crop_bbox(candidate: dict, width: int, height: int, padding_px: int = 12) -> tuple[int, int, int, int]:
    boxes = [candidate["bbox_px"], candidate["region_bbox_px"]]
    x0 = max(0, int(min(box[0] for box in boxes)) - padding_px)
    y0 = max(0, int(min(box[1] for box in boxes)) - padding_px)
    x1 = min(width, int(max(box[2] for box in boxes)) + padding_px)
    y1 = min(height, int(max(box[3] for box in boxes)) + padding_px)
    return x0, y0, x1, y1


def _boxes_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def _materialize_view_children(
    candidates: list[dict],
    rendered_path: Path,
    output_dir: Path,
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
        child_root.mkdir(parents=True, exist_ok=True)
        child_image = child_root / f"view_{index:02d}.png"
        child_ir = child_root / f"view_{index:02d}.json"
        if not cv2.imwrite(str(child_image), image[y0:y1, x0:x1]):
            raise ValueError(f"Cannot write view child image: {child_image}")
        child_image_sha256 = hashlib.sha256(child_image.read_bytes()).hexdigest()
        run(
            image_path=str(child_image),
            output_path=str(child_ir),
            scale_mm_per_px=float(candidate["pixel_to_unit_scale"]),
            preset=preset,
            merge_lines=merge_lines,
            auto_ocr_roi=True,
            calibration_status="needs_verification",
            calibration_source_sha256=child_image_sha256,
        )
        candidate["child_ir"] = str(child_ir.relative_to(output_dir)).replace("\\", "/")
        candidate["child_image"] = str(child_image.relative_to(output_dir)).replace("\\", "/")
        candidate["child_bbox_px"] = [x0, y0, x1, y1]
        candidate["child_calibration_status"] = "needs_verification"
        candidate["child_state"] = "needs_verification"
        candidate["child_image_sha256"] = child_image_sha256
        candidate["child_ir_sha256"] = hashlib.sha256(
            child_ir.read_bytes()
        ).hexdigest()


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
        or drawing.get("width", 0) <= 0
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
        if previous_end is not None and math.hypot(p0.x - previous_end.x, p0.y - previous_end.y) > 0.02:
            return None
        previous_end = p3
        endpoints.append((p0.x, p0.y))
        for t in (0.25, 0.5, 0.75):
            u = 1.0 - t
            x = u**3 * p0.x + 3 * u**2 * t * p1.x + 3 * u * t**2 * p2.x + t**3 * p3.x
            y = u**3 * p0.y + 3 * u**2 * t * p1.y + 3 * u * t**2 * p2.y + t**3 * p3.y
            samples.append((x, y))
    if previous_end is None or math.hypot(
        endpoints[0][0] - previous_end.x, endpoints[0][1] - previous_end.y
    ) > 0.02:
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
    deltas = [math.atan2(math.sin(b - a), math.cos(b - a)) for a, b in zip(angles, angles[1:] + angles[:1])]
    if not (all(delta > 0 for delta in deltas) or all(delta < 0 for delta in deltas)):
        return None
    if abs(sum(abs(delta) for delta in deltas) - 2.0 * math.pi) > 0.02:
        return None
    return center_x, center_y, radius


def _is_smooth_closed_line_contour(drawing: dict) -> bool:
    """Identify closed, smoothly turning line paths that need local fail-closed handling."""
    if drawing.get("type") != "s" or drawing.get("fill") is not None:
        return False
    items = drawing.get("items", [])
    if not items or any(item[0] != "l" for item in items):
        return False

    directions: list[float] = []
    first_start: Optional[fitz.Point] = None
    previous_end: Optional[fitz.Point] = None
    for item in items:
        _, start, end = item
        if first_start is None:
            first_start = start
        if previous_end is not None and math.hypot(
            start.x - previous_end.x, start.y - previous_end.y
        ) > 0.02:
            return False
        dx, dy = end.x - start.x, end.y - start.y
        if math.hypot(dx, dy) <= 0.02:
            return False
        directions.append(math.atan2(dy, dx))
        previous_end = end
    if (
        first_start is None
        or previous_end is None
        or math.hypot(first_start.x - previous_end.x, first_start.y - previous_end.y) > 0.02
    ):
        return False

    turns = [
        abs(math.atan2(
            math.sin(next_direction - direction),
            math.cos(next_direction - direction),
        ))
        for direction, next_direction in zip(directions, directions[1:] + directions[:1])
    ]
    return bool(turns) and float(np.median(turns)) <= math.radians(20.0) and max(turns) > 1e-6


def _suspect_geometry(drawing: dict, pixel_scale: float) -> dict:
    """Preserve supported source paths instead of treating their bounds as paint."""
    segments: list[tuple[float, float, float, float]] = []
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
                points.append((
                    u**3 * p0.x + 3 * u**2 * t * p1.x + 3 * u * t**2 * p2.x + t**3 * p3.x,
                    u**3 * p0.y + 3 * u**2 * t * p1.y + 3 * u * t**2 * p2.y + t**3 * p3.y,
                ))
        else:
            points = []
        if not points:
            rect = drawing.get("rect")
            if rect is None:
                return {"segments": segments}
            return {"bounds": (
                rect.x0 * pixel_scale, rect.y0 * pixel_scale,
                rect.x1 * pixel_scale, rect.y1 * pixel_scale,
            )}
        segments.extend(
            (x0 * pixel_scale, y0 * pixel_scale, x1 * pixel_scale, y1 * pixel_scale)
            for (x0, y0), (x1, y1) in zip(points, points[1:])
        )
    return {"segments": segments}


def _page_background_color(page: fitz.Page) -> Optional[np.ndarray]:
    """Estimate a uniform page background from low-resolution corner samples."""
    pixmap = page.get_pixmap(matrix=fitz.Matrix(0.1, 0.1), alpha=False)
    if pixmap.width < 2 or pixmap.height < 2:
        return None
    pixels = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )[:, :, :3]
    corners = np.asarray(
        (pixels[0, 0], pixels[0, -1], pixels[-1, 0], pixels[-1, -1]),
        dtype=np.float64,
    ) / 255.0
    background = np.median(corners, axis=0)
    if float(np.max(np.linalg.norm(corners - background, axis=1))) > 0.08:
        return None
    return background


def _drawing_may_erase_circle(drawing: dict, witness_color: object) -> bool:
    """Treat later paint in a different color as capable of hiding a circle stroke."""
    drawing_type = drawing.get("type")
    colors = []
    if drawing_type in {"s", "fs"}:
        colors.append(drawing.get("color"))
    if drawing_type in {"f", "fs"}:
        colors.append(drawing.get("fill"))
    colors = [color for color in colors if color is not None]
    if not colors:
        return True
    return any(_colors_match(color, witness_color) is not True for color in colors)


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
        ) > 0.02
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


def _page_circle_witnesses(
    page: fitz.Page, pixel_scale: float
) -> tuple[bool, list[tuple[float, float, float]], list[dict]]:
    """Return global fail-closed state, full-circle witnesses, and suspect regions."""
    drawings = page.get_drawings(extended=True)
    if not drawings:
        return False, [], []
    curve_drawings = [
        drawing for drawing in drawings
        if any(item[0] == "c" for item in drawing.get("items", []))
    ]
    line_contour_indices = {
        index for index, drawing in enumerate(drawings)
        if _is_smooth_closed_line_contour(drawing)
    }
    if not curve_drawings and not line_contour_indices:
        return False, [], []
    background_color = _page_background_color(page)

    # Keep PDF-to-render coordinates simple and reject page features that can
    # alter which parts of a source stroke are visible to the raster detector.
    if (
        page.rotation != 0
        or page.cropbox != page.mediabox
        or page.mediabox.x0 != 0
        or page.mediabox.y0 != 0
    ):
        return True, [], []

    occluder_rects: list[fitz.Rect] = []
    for image in page.get_images():
        for rect in page.get_image_rects(image[0]):
            occluder_rects.append(rect)
    for annotation in page.annots() or ():
        occluder_rects.append(annotation.rect)

    witnesses: list[tuple[float, float, float]] = []
    suspect_regions: list[dict] = []
    for index, drawing in enumerate(drawings):
        if not any(item[0] == "c" for item in drawing.get("items", [])):
            drawing_rect = drawing.get("rect")
            if index in line_contour_indices and drawing_rect is not None:
                suspect_regions.append(_suspect_geometry(drawing, pixel_scale))
            continue
        drawing_rect = drawing.get("rect")
        if drawing_rect is None:
            continue
        circle = _fit_full_circle_path(drawing, background_color)
        if circle is None:
            suspect_regions.append(_suspect_geometry(drawing, pixel_scale))
            continue

        cx, cy, radius = circle
        prior_clip_context = any(
            prior.get("type") == "group"
            or (
                prior.get("type") == "clip"
                and not _clip_fully_contains_circle(prior, cx, cy, radius)
            )
            for prior in drawings[:index]
        )
        if prior_clip_context:
            suspect_regions.append(_suspect_geometry(drawing, pixel_scale))
            continue

        # A later drawing/clip/group touching this perimeter can obscure or
        # alter the witness. Conservatively reject rather than infer visibility.
        occluded = False
        for rect in occluder_rects:
            dx = max(rect.x0 - cx, 0.0, cx - rect.x1)
            dy = max(rect.y0 - cy, 0.0, cy - rect.y1)
            min_distance = math.hypot(dx, dy)
            max_distance = max(
                math.hypot(x - cx, y - cy)
                for x, y in ((rect.x0, rect.y0), (rect.x0, rect.y1), (rect.x1, rect.y0), (rect.x1, rect.y1))
            )
            if min_distance <= radius + 1.0 and max_distance >= radius - 1.0:
                occluded = True
                break
        for later in drawings[index + 1 :]:
            if occluded:
                break
            later_type = later.get("type")
            if later_type == "clip":
                # Extended drawing output reports clipping contexts separately;
                # they constrain later paint but do not paint over this stroke.
                continue
            if later_type not in {"s", "group", "f", "fs"}:
                occluded = True
                break
            if later_type in {"s", "f", "fs"} and not _drawing_may_erase_circle(
                later, drawing.get("color")
            ):
                continue
            later_circle = (
                _fit_full_circle_path(later, background_color)
                if later_type == "s"
                else None
            )
            if later_circle is not None:
                later_cx, later_cy, later_radius = later_circle
                center_distance = math.hypot(later_cx - cx, later_cy - cy)
                if (
                    center_distance <= radius + later_radius + 1.0
                    and center_distance + min(radius, later_radius) >= max(radius, later_radius) - 1.0
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
                                    ((cx - start.x) * dx + (cy - start.y) * dy)
                                    / length_squared,
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
                            points.append((
                                u**3 * p0.x + 3 * u**2 * t * p1.x + 3 * u * t**2 * p2.x + t**3 * p3.x,
                                u**3 * p0.y + 3 * u**2 * t * p1.y + 3 * u * t**2 * p2.y + t**3 * p3.y,
                            ))
                    else:
                        unsupported_item = True
                        points = []
                    radial_samples.extend(math.hypot(x - cx, y - cy) for x, y in points)
                if unsupported_item:
                    occluded = True
                    break
                if radial_samples:
                    stroke_margin = max(1.0, float(later.get("width") or 0.0) / 2.0)
                    if min(radial_samples) <= radius + stroke_margin and max(radial_samples) >= radius - stroke_margin:
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
                for x, y in ((rect.x0, rect.y0), (rect.x0, rect.y1), (rect.x1, rect.y0), (rect.x1, rect.y1))
            )
            if min_distance <= radius + 1.0 and max_distance >= radius - 1.0:
                occluded = True
                break
        if not occluded:
            witnesses.append((cx * pixel_scale, cy * pixel_scale, radius * pixel_scale))
        else:
            suspect_regions.append(_suspect_geometry(drawing, pixel_scale))
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
    render_dir.mkdir(parents=True, exist_ok=True)
    ir_dir.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    manifest = {
        "source_pdf": pdf_path.name,
        "render_dpi": dpi,
        "scale_mm_per_px": scale_mm_per_px if scale_mm_per_px is not None else "auto",
        "pages": [],
    }
    document = fitz.open(str(pdf_path))
    try:
        for index, page in enumerate(document, start=1):
            require_all_vector_witnesses, vector_circle_witnesses, suspect_regions = (
                _page_circle_witnesses(page, scale)
            )
            image_path = render_dir / f"page_{index:02d}.png"
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(str(image_path))
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
            run(
                image_path=str(image_path), output_path=str(output_path),
                scale_mm_per_px=scale_mm_per_px, preset=preset,
                merge_lines=merge_lines,
                auto_ocr_roi=auto_ocr_roi,
                auto_calibrate=auto_calibrate,
                calibration_registry_path=calibration_registry_path,
                calibration_id=page_calibration_id,
                view_candidates_output_path=str(view_candidates_path),
                view_candidates_dpi=dpi,
                **vector_kwargs,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            scale_label_candidates = json.loads(view_candidates_path.read_text(encoding="utf-8"))
            _materialize_view_children(
                scale_label_candidates,
                image_path,
                output_dir,
                index,
                preset,
                merge_lines,
            )
            view_candidates_path.write_text(
                json.dumps(scale_label_candidates, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest["pages"].append({
                "page": index,
                "rendered_png": str(image_path.relative_to(output_dir)),
                "primitive_ir": str(output_path.relative_to(output_dir)),
                "primitive_count": len(payload["primitives"]),
                "cross_validation_count": len(payload["cross_validations"]),
                "calibration_method": payload["calibration"]["method"],
                "scale_mm_per_px": payload["calibration"]["pixel_to_unit_scale"],
                "scale_label_candidates": scale_label_candidates,
            })
    finally:
        document.close()
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    _configure_console_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--scale-mm-per-px", type=float,
                        help="Tỷ lệ mm/px đã xác minh, áp dụng cho mọi trang")
    parser.add_argument("--calibration-registry", type=Path,
                        help="Hash-bound calibration registry JSON (verified scale, mode thủ công)")
    parser.add_argument("--calibration-id",
                        help="Verified calibration record ID (registry mode thủ công, không dùng cùng --auto-calibrate)")
    parser.add_argument("--auto-ocr-roi", action="store_true",
                        help="Tự động phát hiện vùng ứng viên chứa text thay vì cần --ocr-roi thủ công")
    parser.add_argument("--auto-calibrate", action="store_true",
                        help="Suy tỷ lệ mm/px tự động cho TỪNG TRANG (mỗi trang 1 ảnh khác nhau). "
                             "KẾT QUẢ CHƯA VERIFY — chỉ dùng để khảo sát/test. Kết hợp với "
                             "--calibration-registry + --calibration-id (dùng làm prefix, mỗi "
                             "trang ghi record riêng '<id>_pageNN' status=needs_verification).")
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--preset", choices=("default", "real_scan_tuned_v1"), default="real_scan_tuned_v1")
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
                parser.error("--calibration-registry với --auto-calibrate cần thêm --calibration-id (dùng làm prefix)")
            registry_for_run = args.calibration_registry
            calibration_id_prefix = args.calibration_id
        elif args.calibration_registry:
            if not args.calibration_id or args.scale_mm_per_px is not None:
                parser.error("Registry mode (verified) requires --calibration-id and no --scale-mm-per-px")
            # Chế độ thủ công: 1 registry record verified dùng chung cho cả PDF
            # (đại diện bởi chính file PDF gốc, không phải từng trang render).
            scale_mm_per_px = get_verified_scale(args.calibration_registry, args.calibration_id, args.pdf)
        elif args.scale_mm_per_px is not None:
            scale_mm_per_px = args.scale_mm_per_px
        else:
            parser.error("Supply --scale-mm-per-px, --auto-calibrate, or a verified calibration registry")

        manifest = run_pdf(
            args.pdf, args.output_dir, scale_mm_per_px, args.dpi, args.preset, args.merge_lines,
            auto_ocr_roi=args.auto_ocr_roi,
            auto_calibrate=args.auto_calibrate,
            calibration_registry_path=registry_for_run,
            calibration_id_prefix=calibration_id_prefix,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(f"PDF Primitive IR saved: {args.output_dir / 'manifest.json'} ({len(manifest['pages'])} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
