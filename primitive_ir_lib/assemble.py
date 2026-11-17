"""
assemble.py — Ghép RawLine/RawCircle/RawText (tọa độ pixel) + Calibration
thành PrimitiveIRDocument hoàn chỉnh (tọa độ CAD, đúng primitive_ir.schema.json).

Đây là bước "chốt hạ" nối 3 module geometry_extraction / text_extraction /
calibration lại, sinh ra đúng object mà cross_validation.py và (sau này)
DXF Builder sẽ đọc.
"""

from __future__ import annotations

import math
from typing import List, Optional

from .calibration import Calibration
from .geometry_extraction import RawArc, RawCircle, RawLine, RawPdfLine
from .models import (
    ArcGeometry, CircleGeometry, LineGeometry, Primitive,
    PrimitiveIRDocument, SourceDocument, Trace, now_iso,
)
from .text_extraction import RawText


def line_to_primitive(raw: RawLine, calibration: Calibration, tool: str = "opencv-canny-hough-v1") -> Primitive:
    start = calibration.pixel_to_cad(*raw.p1_px)
    end = calibration.pixel_to_cad(*raw.p2_px)
    return Primitive(
        id=raw.id,  # giữ nguyên id để CrossValidation (tính trên raw_lines) trỏ đúng
        type="line",
        source="geometry_opencv",
        confidence=raw.confidence,
        geometry=LineGeometry(start, end),
        trace=Trace(bbox_px=raw.bbox_px, extraction_tool=tool, extracted_at=now_iso()),
    )


def circle_to_primitive(raw: RawCircle, calibration: Calibration, tool: str = "opencv-canny-hough-v1") -> Primitive:
    center = calibration.pixel_to_cad(*raw.center_px)
    radius = raw.radius_px * calibration.pixel_to_unit_scale
    return Primitive(
        id=raw.id,
        type="circle",
        source="geometry_opencv",
        confidence=raw.confidence,
        geometry=CircleGeometry(center, radius),
        trace=Trace(bbox_px=raw.bbox_px, extraction_tool=tool, extracted_at=now_iso()),
    )


def pdf_vector_arc_to_primitive(raw: RawArc, calibration: Calibration) -> Primitive:
    center = calibration.pixel_to_cad(*raw.center_px)
    start = calibration.pixel_to_cad(*raw.start_px)
    end = calibration.pixel_to_cad(*raw.end_px)
    start_angle = math.degrees(math.atan2(start.y - center.y, start.x - center.x)) % 360.0
    end_angle = math.degrees(math.atan2(end.y - center.y, end.x - center.x)) % 360.0
    # DXF ARC is counter-clockwise. The page-to-CAD transform reverses the
    # raster Y axis, so choose the endpoint order that preserves the same open
    # minor arc in CAD coordinates.
    if (end_angle - start_angle) % 360.0 > 180.0:
        start_angle, end_angle = end_angle, start_angle
    return Primitive(
        id=raw.id,
        type="arc",
        source="geometry_pdfvector",
        confidence=raw.confidence,
        geometry=ArcGeometry(
            center=center,
            radius=raw.radius_px * calibration.pixel_to_unit_scale,
            start_angle_deg=start_angle,
            end_angle_deg=end_angle,
        ),
        trace=Trace(
            bbox_px=raw.bbox_px,
            extraction_tool="pymupdf-vector-cubic-fit-v1",
            extracted_at=now_iso(),
            source_pdf_sha256=raw.source_pdf_sha256,
            source_page_index=raw.source_page_index,
            source_transform=raw.source_transform,
            source_render_sha256=raw.render_sha256,
            source_render_dpi=raw.render_dpi,
            source_render_origin_px=raw.render_origin_px,
        ),
    )


def pdf_vector_line_to_primitive(raw: RawPdfLine, calibration: Calibration) -> Primitive:
    start = calibration.pixel_to_cad(*raw.p1_px)
    end = calibration.pixel_to_cad(*raw.p2_px)
    return Primitive(
        id=raw.id,
        type="line",
        source="geometry_pdfvector",
        confidence=raw.confidence,
        geometry=LineGeometry(start, end),
        trace=Trace(
            bbox_px=raw.bbox_px,
            extraction_tool="pymupdf-visible-vector-line-v1",
            extracted_at=now_iso(),
            source_pdf_sha256=raw.source_pdf_sha256,
            source_page_index=raw.source_page_index,
            source_transform=raw.source_transform,
            source_render_sha256=raw.render_sha256,
            source_render_dpi=raw.render_dpi,
            source_render_origin_px=raw.render_origin_px,
        ),
    )


def text_to_primitive(raw: RawText, calibration: Calibration, height_px: float = 20.0) -> Primitive:
    """Map text, using an eligible OCR baseline-y estimate when available.

    Metadata-free observations retain canonical bbox-origin geometry. Neither
    that fallback nor the unchanged ink-height sizing claims font fidelity.
    """
    from .models import TextData

    rotation = raw.rotation_deg
    if isinstance(rotation, bool) or not isinstance(rotation, (int, float)) or not math.isfinite(rotation):
        raise ValueError(f"Unsupported non-finite text rotation_deg: {rotation!r}")
    x0, y0, _x1, y1 = raw.bbox_px
    baseline = raw.baseline_y_px
    if baseline is not None:
        if (
            raw.source != "text_tesseract" or rotation % 360 != 0
            or isinstance(baseline, bool) or not isinstance(baseline, (int, float))
            or not math.isfinite(baseline) or baseline < 0
        ):
            raise ValueError("Invalid or ineligible OCR baseline_y_px")
        origin_y = baseline
    else:
        origin_y = y0
    effective_height_px = (y1 - y0) if y1 > y0 else height_px
    position = calibration.pixel_to_cad(x0, origin_y)
    height_cad = effective_height_px * calibration.pixel_to_unit_scale

    tools = {
        "text_tesseract": "tesseract-5.3",
        "text_vision": "claude-vision",
        "text_pdfvector": "pymupdf",
    }
    try:
        tool = tools[raw.source]
    except KeyError as exc:
        raise ValueError(f"Unsupported text source: {raw.source!r}") from exc

    return Primitive(
        id=raw.id,
        type="text",
        source=raw.source,
        confidence=raw.confidence,
        text_data=TextData(
            content=raw.content,
            position=position,
            rotation_deg=raw.rotation_deg,
            height=round(height_cad, 3),
            parsed_value=raw.parsed_value,
            semantic_role=raw.semantic_role,
        ),
        trace=Trace(bbox_px=raw.bbox_px, extraction_tool=tool, extracted_at=now_iso()),
    )


def build_document(
    file_name: str,
    page_index: int,
    image_width_px: int,
    image_height_px: int,
    calibration: Calibration,
    raw_lines: List[RawLine],
    raw_circles: List[RawCircle],
    raw_texts: List[RawText],
    raw_arcs: Optional[List[RawArc]] = None,
    sha256: Optional[str] = None,
    raw_pdf_lines: Optional[List[RawPdfLine]] = None,
) -> PrimitiveIRDocument:
    """Entry point chính: sinh PrimitiveIRDocument đầy đủ (chưa có
    cross_validations — gọi cross_validation.cross_validate() rồi gán vào
    doc.cross_validations sau, vì hàm đó cần raw_texts/raw_lines ở dạng
    pixel gốc, không phải Primitive đã quy đổi)."""
    primitives: List[Primitive] = []
    primitives += [line_to_primitive(l, calibration) for l in raw_lines]
    primitives += [circle_to_primitive(c, calibration) for c in raw_circles]
    primitives += [pdf_vector_arc_to_primitive(a, calibration) for a in (raw_arcs or [])]
    primitives += [pdf_vector_line_to_primitive(line, calibration) for line in (raw_pdf_lines or [])]
    primitives += [text_to_primitive(t, calibration) for t in raw_texts]

    return PrimitiveIRDocument(
        source_document=SourceDocument(
            file_name=file_name, page_index=page_index,
            image_width_px=image_width_px, image_height_px=image_height_px,
            sha256=sha256,
        ),
        calibration=calibration,
        primitives=primitives,
    )
