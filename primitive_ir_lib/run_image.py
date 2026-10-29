"""CLI Phase 1 for a real CAD drawing image.

Example:
    .venv\\Scripts\\python -m primitive_ir_lib.run_image ^
      --image drawing.png --output output/primitive_ir.json ^
      --scale-mm-per-px 0.0917 --ocr-roi 620,325,860,385

A scale is deliberately required.  Automatic calibration from noisy OCR can
silently produce incorrect CAD coordinates; use a verified known dimension
until a drawing has passed calibration validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import pytesseract

from .assemble import build_document
from .calibration import Calibration, auto_estimate_calibration
from .calibration_registry import add_record, get_verified_scale
from .cross_validation import cross_validate
from .geometry_extraction import RawArc, RawLine, RawPdfLine, extract_raw_geometry
from .io_utils import save_document
from .line_merging import merge_collinear_lines
from .text_extraction import RawText, detect_text_candidate_rois, extract_text_tesseract
from .view_calibration import detect_view_candidates, parse_scale_label

Bbox = Tuple[int, int, int, int]
PDF_TEXT_CONFLICT_POLICY_VERSION = "ocr-pdf-conflict-exclusion-v1"


class CalibrationCandidateUnavailableError(ValueError):
    """Raised when auto-calibration finds no usable dimension/line pair."""


def _title_block_roi(image_width: int, image_height: int) -> Bbox:
    """Return the conventional lower-right title-block search area."""
    return (
        int(image_width * 0.58),
        int(image_height * 0.50),
        image_width,
        image_height,
    )


def _parse_roi(value: str) -> Bbox:
    try:
        values = tuple(int(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ROI phải có dạng x0,y0,x1,y1") from exc
    if len(values) != 4 or values[0] >= values[2] or values[1] >= values[3]:
        raise argparse.ArgumentTypeError("ROI phải có dạng x0,y0,x1,y1 với x0<x1 và y0<y1")
    return values  # type: ignore[return-value]


def _configure_tesseract(command: Optional[str]) -> None:
    if command:
        if not os.path.isfile(command):
            raise FileNotFoundError(f"Không thấy tesseract.exe: {command}")
        pytesseract.pytesseract.tesseract_cmd = command
        return
    known_windows_path = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    if os.path.isfile(known_windows_path):
        pytesseract.pytesseract.tesseract_cmd = known_windows_path


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _same_span_bbox_match(a: RawText, b: RawText) -> bool:
    ax0, ay0, ax1, ay1 = a.bbox_px
    bx0, by0, bx1, by1 = b.bbox_px
    area_a = max(0, ax1 - ax0) * max(0, ay1 - ay0)
    area_b = max(0, bx1 - bx0) * max(0, by1 - by0)
    overlap_width = max(0, min(ax1, bx1) - max(ax0, bx0))
    overlap_height = max(0, min(ay1, by1) - max(ay0, by0))
    intersection_area = overlap_width * overlap_height
    smaller_area = min(area_a, area_b)
    larger_area = max(area_a, area_b)
    return (
        smaller_area > 0
        and intersection_area / smaller_area >= 0.90
        and smaller_area / larger_area >= 0.40
    )


def _rotation_equivalent(a: RawText, b: RawText) -> bool:
    if not math.isfinite(a.rotation_deg) or not math.isfinite(b.rotation_deg):
        return False
    difference = abs((a.rotation_deg - b.rotation_deg + 180.0) % 360.0 - 180.0)
    return difference <= 1e-6


def _combine_pdf_vector_texts(
    pdf_vector_texts: Optional[List[RawText]], ocr_texts: List[RawText],
    conflict_report: Optional[dict] = None,
) -> List[RawText]:
    """Validate PDF/OCR spans; only OCR text is admissible for visible output."""
    pdf_texts = pdf_vector_texts or []

    for first_index, first in enumerate(pdf_texts):
        for second in pdf_texts[first_index + 1:]:
            if (
                first.content == second.content
                and _same_span_bbox_match(first, second)
            ):
                raise ValueError(
                    "PDF/PDF same-span identity ambiguous: "
                    f"{first.id}={first.rotation_deg}°, "
                    f"{second.id}={second.rotation_deg}°"
                )

    content_conflicts = [
        (pdf, ocr)
        for pdf in pdf_texts
        for ocr in ocr_texts
        if _same_span_bbox_match(pdf, ocr) and pdf.content != ocr.content
    ]
    excluded_pdf_objects = {id(pdf) for pdf, _ in content_conflicts}
    excluded_ocr_objects = {id(ocr) for _, ocr in content_conflicts}
    # Exclude the whole same-span group, including a third OCR/PDF observation
    # that happens to agree with one side of an otherwise conflicting pair.
    seed_pdf_texts = {id(pdf): pdf for pdf, _ in content_conflicts}
    seed_ocr_texts = {id(ocr): ocr for _, ocr in content_conflicts}
    excluded_queue = [
        *((True, pdf) for pdf in seed_pdf_texts.values()),
        *((False, ocr) for ocr in seed_ocr_texts.values()),
    ]
    queue_index = 0
    while queue_index < len(excluded_queue):
        is_pdf, text = excluded_queue[queue_index]
        queue_index += 1
        if is_pdf:
            for ocr in ocr_texts:
                if (
                    id(ocr) not in excluded_ocr_objects
                    and _same_span_bbox_match(text, ocr)
                ):
                    excluded_ocr_objects.add(id(ocr))
                    excluded_queue.append((False, ocr))
        else:
            for pdf in pdf_texts:
                if (
                    id(pdf) not in excluded_pdf_objects
                    and _same_span_bbox_match(pdf, text)
                ):
                    excluded_pdf_objects.add(id(pdf))
                    excluded_queue.append((True, pdf))
    if conflict_report is not None:
        conflict_report.update(
            ocr_text_state=(
                "partial_conflicts_excluded" if content_conflicts else "unverified"
            ),
            ocr_pdf_conflict_count=len(content_conflicts),
            excluded_ocr_text_span_count=len(excluded_ocr_objects),
            excluded_pdf_text_span_count=len(excluded_pdf_objects),
        )
    admitted_pdf_texts = [text for text in pdf_texts if id(text) not in excluded_pdf_objects]
    admitted_ocr_texts = [text for text in ocr_texts if id(text) not in excluded_ocr_objects]

    pdf_matches = {
        pdf_index: [
            ocr_index for ocr_index, ocr in enumerate(admitted_ocr_texts)
            if pdf.content == ocr.content and _same_span_bbox_match(pdf, ocr)
        ]
        for pdf_index, pdf in enumerate(admitted_pdf_texts)
    }
    ocr_matches = {
        ocr_index: [
            pdf_index for pdf_index, pdf in enumerate(admitted_pdf_texts)
            if pdf.content == ocr.content and _same_span_bbox_match(pdf, ocr)
        ]
        for ocr_index, ocr in enumerate(admitted_ocr_texts)
    }

    ambiguous_pairs = [
        (pdf_index, ocr_index)
        for pdf_index, ocr_indexes in pdf_matches.items()
        if len(ocr_indexes) > 1
        for ocr_index in ocr_indexes
    ] + [
        (pdf_index, ocr_index)
        for ocr_index, pdf_indexes in ocr_matches.items()
        if len(pdf_indexes) > 1
        for pdf_index in pdf_indexes
    ]
    if ambiguous_pairs:
        pdf_indexes = sorted({pdf_index for pdf_index, _ in ambiguous_pairs})
        ocr_indexes = sorted({ocr_index for _, ocr_index in ambiguous_pairs})
        pdf_details = ", ".join(
            f"{admitted_pdf_texts[index].id}={admitted_pdf_texts[index].rotation_deg}°"
            for index in pdf_indexes
        )
        ocr_details = ", ".join(
            f"{admitted_ocr_texts[index].id}={admitted_ocr_texts[index].rotation_deg}°"
            for index in ocr_indexes
        )
        raise ValueError(
            "ambiguous OCR/PDF span match: "
            f"OCR [{ocr_details}]; PDF [{pdf_details}]"
        )

    for pdf_index, ocr_indexes in pdf_matches.items():
        if not ocr_indexes:
            continue
        ocr = admitted_ocr_texts[ocr_indexes[0]]
        pdf = admitted_pdf_texts[pdf_index]
        if not _rotation_equivalent(ocr, pdf):
            raise ValueError(
                "PDF/OCR same-span rotation conflict: "
                f"{ocr.id}={ocr.rotation_deg}°, "
                f"{pdf.id}={pdf.rotation_deg}°"
            )
    return admitted_ocr_texts


def _line_is_explained_by_pdf_arc(line, arc: RawArc) -> bool:
    tolerance = max(2.0, arc.radius_px * 0.002)
    if line.length_px() > max(5.0, arc.radius_px * 0.12):
        return False
    start_angle = math.degrees(
        math.atan2(arc.start_px[1] - arc.center_px[1], arc.start_px[0] - arc.center_px[0])
    )
    sweep = arc.signed_sweep_deg
    progresses = []
    for fraction in (0.0, 0.5, 1.0):
        x = line.p1_px[0] + fraction * (line.p2_px[0] - line.p1_px[0])
        y = line.p1_px[1] + fraction * (line.p2_px[1] - line.p1_px[1])
        radial_error = abs(math.hypot(x - arc.center_px[0], y - arc.center_px[1]) - arc.radius_px)
        if radial_error > tolerance:
            return False
        angle = math.degrees(math.atan2(y - arc.center_px[1], x - arc.center_px[0]))
        progress = (angle - start_angle) % 360.0 if sweep >= 0 else (start_angle - angle) % 360.0
        if progress > abs(sweep) + 2.0:
            return False
        progresses.append(progress)
    return max(progresses) - min(progresses) <= 15.0


def _clip_raster_line_to_pdf_vector_witness(
    line: RawLine, witness: RawLine
) -> Optional[RawLine]:
    """Bound an existing raster LINE to the part supported by a PDF stroke."""
    line_dx = line.p2_px[0] - line.p1_px[0]
    line_dy = line.p2_px[1] - line.p1_px[1]
    witness_dx = witness.p2_px[0] - witness.p1_px[0]
    witness_dy = witness.p2_px[1] - witness.p1_px[1]
    line_length = math.hypot(line_dx, line_dy)
    witness_length = math.hypot(witness_dx, witness_dy)
    if not all(math.isfinite(value) for value in (line_length, witness_length)):
        return None
    if line_length <= 1e-9 or witness_length <= 1e-9:
        return None

    direction = (witness_dx / witness_length, witness_dy / witness_length)
    alignment = abs((line_dx * direction[0] + line_dy * direction[1]) / line_length)
    if alignment < 0.98:
        return None

    line_points = (line.p1_px, line.p2_px)
    perpendicular_distances = [
        abs(
            (point[0] - witness.p1_px[0]) * direction[1]
            - (point[1] - witness.p1_px[1]) * direction[0]
        )
        for point in line_points
    ]
    if not all(math.isfinite(value) and value <= 2.5 for value in perpendicular_distances):
        return None

    projections = [
        (point[0] - witness.p1_px[0]) * direction[0]
        + (point[1] - witness.p1_px[1]) * direction[1]
        for point in line_points
    ]
    overlap_start = max(0.0, min(projections))
    overlap_end = min(witness_length, max(projections))
    overlap = overlap_end - overlap_start
    if overlap / witness_length < 0.75:
        return None

    projection_span = projections[1] - projections[0]
    if abs(projection_span) <= 1e-9:
        return None
    parameters = (
        (overlap_start - projections[0]) / projection_span,
        (overlap_end - projections[0]) / projection_span,
    )
    clipped_points = [
        (
            line.p1_px[0] + parameter * line_dx,
            line.p1_px[1] + parameter * line_dy,
        )
        for parameter in parameters
    ]
    clipped_length = math.dist(clipped_points[0], clipped_points[1])
    if not math.isfinite(clipped_length) or clipped_length <= 1e-9:
        return None
    return RawLine(
        id=line.id,
        p1_px=clipped_points[0],
        p2_px=clipped_points[1],
        confidence=line.confidence,
        bbox_px=(
            min(point[0] for point in clipped_points),
            min(point[1] for point in clipped_points),
            max(point[0] for point in clipped_points),
            max(point[1] for point in clipped_points),
        ),
    )


def _union_overlapping_pdf_witness_intervals(
    first: RawLine, second: RawLine, witness: RawLine
) -> Optional[RawLine]:
    """Union overlapping raster intervals on one source-supported PDF stroke."""
    witness_dx = witness.p2_px[0] - witness.p1_px[0]
    witness_dy = witness.p2_px[1] - witness.p1_px[1]
    witness_length = math.hypot(witness_dx, witness_dy)
    if not math.isfinite(witness_length) or witness_length <= 1e-9:
        return None
    direction = (witness_dx / witness_length, witness_dy / witness_length)

    def interval(line: RawLine) -> tuple[float, float]:
        projections = [
            (point[0] - witness.p1_px[0]) * direction[0]
            + (point[1] - witness.p1_px[1]) * direction[1]
            for point in (line.p1_px, line.p2_px)
        ]
        return min(projections), max(projections)

    first_start, first_end = interval(first)
    second_start, second_end = interval(second)
    if min(first_end, second_end) < max(first_start, second_start) - 1e-6:
        return None

    merged_start = max(0.0, min(first_start, second_start))
    merged_end = min(witness_length, max(first_end, second_end))
    if not math.isfinite(merged_start) or not math.isfinite(merged_end) or merged_end <= merged_start:
        return None
    p1 = (
        witness.p1_px[0] + merged_start * direction[0],
        witness.p1_px[1] + merged_start * direction[1],
    )
    p2 = (
        witness.p1_px[0] + merged_end * direction[0],
        witness.p1_px[1] + merged_end * direction[1],
    )
    return RawLine(
        id=first.id if first.confidence >= second.confidence else second.id,
        p1_px=p1,
        p2_px=p2,
        confidence=max(first.confidence, second.confidence),
        bbox_px=(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])),
    )


def _classify_pdf_layer_line_witnesses(
    lines: List[RawLine],
    witnesses: List[Tuple[RawLine, str]],
    endpoint_tolerance_px: float = 1.0,
) -> dict[str, str]:
    """Return classifications only for mutual unique full-span witnesses."""
    if (
        isinstance(endpoint_tolerance_px, bool)
        or not math.isfinite(endpoint_tolerance_px)
        or endpoint_tolerance_px <= 0
    ):
        return {}
    eligible = [
        (index, witness, classification)
        for index, (witness, classification) in enumerate(witnesses)
        if classification in {"HIDDEN", "CENTERLINE"}
    ]
    classification_by_witness_index = {
        index: classification for index, _, classification in eligible
    }
    matches_by_line: dict[int, list[int]] = {}
    matches_by_witness: dict[int, list[int]] = {}

    def endpoints_match(line: RawLine, witness: RawLine) -> bool:
        direct = max(
            math.dist(line.p1_px, witness.p1_px),
            math.dist(line.p2_px, witness.p2_px),
        )
        reverse = max(
            math.dist(line.p1_px, witness.p2_px),
            math.dist(line.p2_px, witness.p1_px),
        )
        return math.isfinite(direct) and math.isfinite(reverse) and min(direct, reverse) <= endpoint_tolerance_px

    for line_index, line in enumerate(lines):
        for witness_index, witness, _ in eligible:
            if endpoints_match(line, witness):
                matches_by_line.setdefault(line_index, []).append(witness_index)
                matches_by_witness.setdefault(witness_index, []).append(line_index)

    classifications_by_line_id: dict[str, str] = {}
    for line_index, witness_indices in matches_by_line.items():
        if len(witness_indices) != 1:
            continue
        witness_index = witness_indices[0]
        if len(matches_by_witness.get(witness_index, ())) != 1:
            continue
        classifications_by_line_id[lines[line_index].id] = (
            classification_by_witness_index[witness_index]
        )
    return classifications_by_line_id


def _apply_pdf_source_layer_classifications(
    document, classifications_by_line_id: dict[str, str]
) -> None:
    """Apply verified PDF layer labels to matching LINE primitives only."""
    if not classifications_by_line_id:
        return
    for primitive in document.primitives:
        if primitive.type != "line":
            continue
        classification = classifications_by_line_id.get(primitive.id)
        if classification in {"HIDDEN", "CENTERLINE"}:
            primitive.layer = classification


def _pdf_line_overlaps_raster(
    source_lines: List[RawPdfLine], raster_lines: List[RawLine], raw_texts: List[RawText]
) -> bool:
    """Refuse a source LINE item when raster/text composition is ambiguous."""
    if not source_lines:
        return False
    cell_size = 256.0

    def cells(bounds: tuple[float, float, float, float], margin: float = 0.0) -> list[tuple[int, int]]:
        left, top, right, bottom = bounds
        x0 = math.floor((left - margin) / cell_size)
        y0 = math.floor((top - margin) / cell_size)
        x1 = math.floor((right + margin) / cell_size)
        y1 = math.floor((bottom + margin) / cell_size)
        if (x1 - x0 + 1) * (y1 - y0 + 1) > 256:
            return []
        return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]

    raster_by_cell: dict[tuple[int, int], list[int]] = {}
    broad_raster: list[int] = []
    for index, raster in enumerate(raster_lines):
        occupied = cells(raster.bbox_px, 1.5)
        if not occupied:
            broad_raster.append(index)
            continue
        for cell in occupied:
            raster_by_cell.setdefault(cell, []).append(index)
    text_by_cell: dict[tuple[int, int], list[int]] = {}
    broad_text: list[int] = []
    for index, text in enumerate(raw_texts):
        occupied = cells(text.bbox_px)
        if not occupied:
            broad_text.append(index)
            continue
        for cell in occupied:
            text_by_cell.setdefault(cell, []).append(index)

    cosine_limit = math.cos(math.radians(2.0))
    for source in source_lines:
        source_cells = cells(source.bbox_px)
        nearby_text: set[int] = set(
            broad_text if source_cells else range(len(raw_texts))
        )
        for cell in source_cells:
            nearby_text.update(text_by_cell.get(cell, ()))
        for text_index in nearby_text:
            left, top, right, bottom = raw_texts[text_index].bbox_px
            source_left, source_top, source_right, source_bottom = source.bbox_px
            if (
                source_left < right and source_right > left
                and source_top < bottom and source_bottom > top
            ):
                return True
        source_dx = source.p2_px[0] - source.p1_px[0]
        source_dy = source.p2_px[1] - source.p1_px[1]
        source_length = math.hypot(source_dx, source_dy)
        if not math.isfinite(source_length) or source_length <= 1e-6:
            return True
        source_unit = (source_dx / source_length, source_dy / source_length)
        source_left, source_top, source_right, source_bottom = source.bbox_px
        source_cells = cells(source.bbox_px, 1.5)
        nearby_raster: set[int] = set(
            broad_raster if source_cells else range(len(raster_lines))
        )
        for cell in source_cells:
            nearby_raster.update(raster_by_cell.get(cell, ()))
        for raster_index in nearby_raster:
            raster = raster_lines[raster_index]
            raster_left, raster_top, raster_right, raster_bottom = raster.bbox_px
            if (
                source_left - 1.5 > raster_right
                or source_right + 1.5 < raster_left
                or source_top - 1.5 > raster_bottom
                or source_bottom + 1.5 < raster_top
            ):
                continue
            raster_dx = raster.p2_px[0] - raster.p1_px[0]
            raster_dy = raster.p2_px[1] - raster.p1_px[1]
            raster_length = math.hypot(raster_dx, raster_dy)
            if not math.isfinite(raster_length) or raster_length <= 1e-6:
                return True
            cosine = abs(
                (source_dx * raster_dx + source_dy * raster_dy)
                / (source_length * raster_length)
            )
            if cosine < cosine_limit:
                continue
            projections = (
                (raster.p1_px[0] - source.p1_px[0]) * source_unit[0]
                + (raster.p1_px[1] - source.p1_px[1]) * source_unit[1],
                (raster.p2_px[0] - source.p1_px[0]) * source_unit[0]
                + (raster.p2_px[1] - source.p1_px[1]) * source_unit[1],
            )
            overlap = max(
                0.0,
                min(source_length, max(projections)) - max(0.0, min(projections)),
            )
            if overlap > 1e-6:
                overlap_start = max(0.0, min(projections))
                overlap_end = min(source_length, max(projections))
                projection_delta = projections[1] - projections[0]
                if abs(projection_delta) <= 1e-6:
                    continue
                raster_t_start = (overlap_start - projections[0]) / projection_delta
                raster_t_end = (overlap_end - projections[0]) / projection_delta
                perpendiculars = tuple(
                    source_unit[0] * (point[1] - source.p1_px[1])
                    - source_unit[1] * (point[0] - source.p1_px[0])
                    for point in (raster.p1_px, raster.p2_px)
                )
                signed_start = perpendiculars[0] + (
                    perpendiculars[1] - perpendiculars[0]
                ) * raster_t_start
                signed_end = perpendiculars[0] + (
                    perpendiculars[1] - perpendiculars[0]
                ) * raster_t_end
                minimum_perpendicular = (
                    0.0 if signed_start * signed_end <= 0.0
                    else min(abs(signed_start), abs(signed_end))
                )
                if minimum_perpendicular <= 1.5:
                    return True
    return False


def run(
    image_path: str,
    output_path: str,
    scale_mm_per_px: Optional[float] = None,
    preset: str = "real_scan_tuned_v1",
    ocr_rois: Optional[List[Bbox]] = None,
    tesseract_cmd: Optional[str] = None,
    ocr_lang: str = "vie+eng",
    merge_lines: bool = False,
    auto_ocr_roi: bool = False,
    auto_calibrate: bool = False,
    calibration_registry_path: Optional[Path] = None,
    calibration_id: Optional[str] = None,
    view_candidates_output_path: Optional[str] = None,
    view_candidates_dpi: Optional[int] = None,
    calibration_status: str = "verified",
    calibration_source_sha256: Optional[str] = None,
    pdf_vector_circle_witnesses: Optional[List[Tuple[float, float, float]]] = None,
    validated_pdf_vector_circle_witnesses: Optional[List[Tuple[float, float, float]]] = None,
    pdf_vector_circle_suspect_regions: Optional[List[dict | Tuple[float, float, float, float]]] = None,
    require_pdf_vector_circle_witness: bool = False,
    pdf_vector_texts: Optional[List[RawText]] = None,
    text_conflict_report: Optional[dict] = None,
    pdf_vector_arcs: Optional[List[RawArc]] = None,
    pdf_vector_line_witnesses: Optional[List[RawLine]] = None,
    pdf_layer_line_witnesses: Optional[List[Tuple[RawLine, str]]] = None,
    pdf_vector_lines: Optional[List[RawPdfLine]] = None,
    source_page_index: int = 0,
    image_bytes: Optional[bytes] = None,
) -> str:
    """Extract a validated Primitive IR JSON from one PNG/JPG drawing image.

    scale_mm_per_px vẫn là cách được khuyến nghị (đã verify thủ công). Nếu
    không có, cần bật auto_calibrate=True để thử suy ra tỷ lệ tự động từ 1
    cặp (text kích thước, line đo được) tìm thấy qua OCR — xem cảnh báo an
    toàn trong auto_estimate_calibration(): kết quả này CHƯA được verify,
    không nên dùng thẳng cho DXF sản xuất mà không kiểm tra lại.
    """
    if scale_mm_per_px is not None and (
        isinstance(scale_mm_per_px, bool)
        or not math.isfinite(scale_mm_per_px)
        or scale_mm_per_px <= 0
    ):
        raise ValueError("scale_mm_per_px phải là số hữu hạn lớn hơn 0")
    if scale_mm_per_px is None and not auto_calibrate:
        raise ValueError("Cần scale_mm_per_px hoặc bật auto_calibrate=True")
    if calibration_status not in {"verified", "needs_verification"}:
        raise ValueError(
            "calibration_status must be verified or needs_verification"
        )
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Không thấy ảnh đầu vào: {image_path}")

    if image_bytes is None:
        image = cv2.imread(image_path)
        image_sha256 = _sha256(image_path)
    else:
        if not isinstance(image_bytes, bytes) or not image_bytes:
            raise ValueError("image_bytes must be non-empty bytes")
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        image_sha256 = hashlib.sha256(image_bytes).hexdigest()
    if image is None:
        raise ValueError(f"Không đọc được ảnh bằng OpenCV: {image_path}")

    if (
        require_pdf_vector_circle_witness
        or pdf_vector_circle_witnesses
        or validated_pdf_vector_circle_witnesses
        or pdf_vector_circle_suspect_regions
    ):
        raw_geometry = extract_raw_geometry(
            image,
            preset=preset,
            pdf_vector_circle_witnesses=pdf_vector_circle_witnesses,
            validated_pdf_vector_circle_witnesses=validated_pdf_vector_circle_witnesses,
            pdf_vector_circle_suspect_regions=pdf_vector_circle_suspect_regions,
            require_pdf_vector_circle_witness=require_pdf_vector_circle_witness,
        )
    else:
        raw_geometry = extract_raw_geometry(image, preset=preset)
    effective_rois = list(ocr_rois) if ocr_rois else []
    if auto_ocr_roi or (auto_calibrate and not effective_rois):
        detected = detect_text_candidate_rois(image)
        effective_rois = list({*effective_rois, *detected}) if effective_rois else detected
        print(f"[run-image] auto-ocr-roi: {len(detected)} vùng ứng viên được phát hiện tự động.")

    ocr_texts: List[RawText] = []
    if effective_rois:
        _configure_tesseract(tesseract_cmd)
        ocr_texts = extract_text_tesseract(image, roi_boxes=effective_rois, lang=ocr_lang)

    if view_candidates_output_path is not None:
        _configure_tesseract(tesseract_cmd)
        title_texts = extract_text_tesseract(
            image,
            roi_boxes=[_title_block_roi(image.shape[1], image.shape[0])],
            min_confidence=10,
            psm=11,
            lang=ocr_lang,
        )
        ocr_texts.extend(text for text in title_texts if parse_scale_label(text.content) is not None)

    raw_texts = _combine_pdf_vector_texts(
        pdf_vector_texts, ocr_texts, conflict_report=text_conflict_report
    )
    # Keep OCR as the only decision-grade text source. Embedded PDF text can
    # be invisible or stale relative to the rendered page and must not replace
    # OCR evidence used by existing geometry association gates.
    decision_texts = raw_texts

    pdf_vector_arcs = pdf_vector_arcs or []
    pdf_vector_line_witnesses = pdf_vector_line_witnesses or []
    raw_lines = []
    pdf_witnessed_lines: dict[int, List[RawLine]] = {}
    for line in raw_geometry.lines:
        if not any(_line_is_explained_by_pdf_arc(line, arc) for arc in pdf_vector_arcs):
            raw_lines.append(line)
            continue
        for witness_index, witness in enumerate(pdf_vector_line_witnesses):
            clipped = _clip_raster_line_to_pdf_vector_witness(line, witness)
            if clipped is not None:
                # Keep the source-bounded segment out of the general line
                # merger: an adjacent raster fragment must not extend it
                # beyond the PDF stroke that independently supports it.
                witnessed_intervals = pdf_witnessed_lines.setdefault(witness_index, [])
                for interval_index, existing in enumerate(witnessed_intervals):
                    merged = _union_overlapping_pdf_witness_intervals(existing, clipped, witness)
                    if merged is not None:
                        witnessed_intervals[interval_index] = merged
                        break
                else:
                    witnessed_intervals.append(clipped)
                break
    if merge_lines:
        raw_lines = merge_collinear_lines(raw_lines, blocking_texts=ocr_texts, image_bgr=image)
    pdf_layer_classifications = _classify_pdf_layer_line_witnesses(
        raw_lines, pdf_layer_line_witnesses or []
    )
    raw_lines.extend(
        line for witnessed_intervals in pdf_witnessed_lines.values() for line in witnessed_intervals
    )
    pdf_vector_lines = [
        line for line in pdf_vector_lines or []
        if not _pdf_line_overlaps_raster([line], raw_lines, raw_texts)
    ]

    if view_candidates_output_path is not None:
        if view_candidates_dpi is None:
            raise ValueError("view_candidates_dpi is required with view_candidates_output_path")
        candidates = detect_view_candidates(decision_texts, raw_lines, image.shape[1], image.shape[0], dpi=view_candidates_dpi)
        candidates_path = Path(view_candidates_output_path)
        candidates_path.parent.mkdir(parents=True, exist_ok=True)
        candidates_path.write_text(json.dumps(candidates, indent=2) + "\n", encoding="utf-8")

    if scale_mm_per_px is not None:
        calibration = Calibration(
            unit="mm",
            pixel_to_unit_scale=scale_mm_per_px,
            origin_px=(0.0, float(image.shape[0])),
            method="manual_override",
            reference_note=(
                "Scale supplied via --scale-mm-per-px; verify against a known "
                "dimension before using output for production DXF."
            ),
            status=calibration_status,
            source_sha256=calibration_source_sha256,
        )
    else:
        calibration = auto_estimate_calibration(decision_texts, raw_lines, image.shape[0], unit="mm")
        if calibration is None:
            raise CalibrationCandidateUnavailableError(
                "auto_calibrate không tìm được cặp (dimension_value, line gần "
                "nhất) hợp lệ trong các ROI đã quét — cần cung cấp "
                "--scale-mm-per-px thủ công hoặc thêm --ocr-roi bao trùm 1 "
                "kích thước đã biết."
            )
        calibration.status = "needs_verification"
        calibration.source_sha256 = calibration_source_sha256 or image_sha256
        print(
            "[run-image] CẢNH BÁO: scale được suy tự động "
            f"({calibration.pixel_to_unit_scale} mm/px, method="
            f"{calibration.method}) — CHƯA được verify, chỉ dùng để test/"
            "khảo sát, không dùng thẳng cho DXF sản xuất."
        )
        if calibration_registry_path is not None and calibration_id is not None:
            add_record(
                calibration_registry_path,
                calibration_id,
                Path(image_path),
                calibration.pixel_to_unit_scale,
                evidence=calibration.reference_note or "auto_estimate_calibration",
                status="needs_verification",
                image_sha256=image_sha256,
            )
            print(
                f"[run-image] Đã ghi bản ghi calibration '{calibration_id}' "
                f"vào {calibration_registry_path} với status=needs_verification "
                "— cần người xác minh và đổi status='verified' trước khi dùng "
                "qua --calibration-registry."
            )
    document = build_document(
        file_name=os.path.basename(image_path),
        page_index=source_page_index,
        image_width_px=image.shape[1],
        image_height_px=image.shape[0],
        calibration=calibration,
        raw_lines=raw_lines,
        raw_circles=raw_geometry.circles,
        raw_texts=raw_texts,
        raw_arcs=pdf_vector_arcs,
        sha256=image_sha256,
        raw_pdf_lines=pdf_vector_lines,
    )
    _apply_pdf_source_layer_classifications(document, pdf_layer_classifications)
    document.cross_validations = cross_validate(
        decision_texts,
        raw_lines,
        calibration,
        merge_collinear=False,
        image_bgr=image if auto_ocr_roi else None,
    )
    if auto_ocr_roi:
        for cross_validation in document.cross_validations:
            cross_validation.status = "unverified"

    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)
    save_document(document, output_path)
    return output_path


def _configure_console_output() -> None:
    """Keep Vietnamese CLI output readable in legacy Windows terminals."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def main() -> int:
    _configure_console_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Ảnh bản vẽ PNG/JPG")
    parser.add_argument("--output", required=True, help="Đường dẫn Primitive IR JSON")
    parser.add_argument("--scale-mm-per-px", type=float,
                        help="Tỷ lệ mm/px đã xác minh từ kích thước chuẩn")
    parser.add_argument("--calibration-registry", help="Hash-bound calibration registry JSON")
    parser.add_argument("--calibration-id", help="Verified calibration record ID")
    parser.add_argument("--preset", default="real_scan_tuned_v1",
                        choices=("default", "real_scan_tuned_v1"))
    parser.add_argument("--ocr-roi", action="append", type=_parse_roi, default=[],
                        help="ROI OCR: x0,y0,x1,y1; có thể truyền nhiều lần")
    parser.add_argument("--auto-ocr-roi", action="store_true",
                        help="Tự động phát hiện vùng ứng viên chứa text (connected-"
                             "components) thay vì phải tự khoanh --ocr-roi bằng tay. "
                             "Có thể kết hợp với --ocr-roi (cộng dồn).")
    parser.add_argument("--auto-calibrate", action="store_true",
                        help="Suy tỷ lệ mm/px tự động từ 1 cặp (kích thước OCR đọc "
                             "được, line gần nhất) thay vì --scale-mm-per-px. KẾT QUẢ "
                             "CHƯA ĐƯỢC VERIFY — chỉ dùng để khảo sát/test, không dùng "
                             "thẳng cho DXF sản xuất. Kết hợp với --calibration-registry "
                             "+ --calibration-id để ghi lại kết quả (status=needs_verification) "
                             "cho việc xác minh sau.")
    parser.add_argument("--tesseract-cmd", help="Đường dẫn tesseract.exe nếu không ở PATH")
    parser.add_argument("--ocr-lang", default="vie+eng",
                        help="Gói ngôn ngữ Tesseract (mặc định 'vie+eng' vì title block "
                             "thật luôn có nhãn tiếng Việt có dấu). Yêu cầu đã cài "
                             "tesseract-ocr-vie; kiểm tra bằng `tesseract --list-langs`. "
                             "Truyền 'eng' nếu chỉ cần đọc mã bản vẽ/số liệu không dấu.")
    parser.add_argument("--merge-lines", action="store_true",
                        help="Bật merge + witness split trước khi assemble IR")
    args = parser.parse_args()

    try:
        scale_mm_per_px: Optional[float] = None
        if args.auto_calibrate:
            if args.calibration_registry and not args.calibration_id:
                parser.error("--calibration-registry với --auto-calibrate cần thêm --calibration-id")
            if args.scale_mm_per_px is not None:
                parser.error("--auto-calibrate không dùng cùng --scale-mm-per-px")
        elif args.calibration_registry:
            if not args.calibration_id or args.scale_mm_per_px is not None:
                parser.error("Registry mode requires --calibration-id and no --scale-mm-per-px")
            scale_mm_per_px = get_verified_scale(Path(args.calibration_registry), args.calibration_id, Path(args.image))
        elif args.scale_mm_per_px is not None:
            scale_mm_per_px = args.scale_mm_per_px
        else:
            parser.error("Supply --scale-mm-per-px, --auto-calibrate, or a verified calibration registry")
        result = run(
            image_path=args.image,
            output_path=args.output,
            scale_mm_per_px=scale_mm_per_px,
            auto_ocr_roi=args.auto_ocr_roi,
            auto_calibrate=args.auto_calibrate,
            calibration_registry_path=Path(args.calibration_registry) if (args.auto_calibrate and args.calibration_registry) else None,
            calibration_id=args.calibration_id if args.auto_calibrate else None,
            preset=args.preset,
            ocr_rois=args.ocr_roi,
            tesseract_cmd=args.tesseract_cmd,
            ocr_lang=args.ocr_lang,
            merge_lines=args.merge_lines,
        )
    except (FileNotFoundError, ValueError, pytesseract.TesseractNotFoundError) as exc:
        parser.error(str(exc))
    print(f"Primitive IR saved: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
