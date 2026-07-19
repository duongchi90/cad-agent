"""
assemble.py — Ghép RawLine/RawCircle/RawText (tọa độ pixel) + Calibration
thành PrimitiveIRDocument hoàn chỉnh (tọa độ CAD, đúng primitive_ir.schema.json).

Đây là bước "chốt hạ" nối 3 module geometry_extraction / text_extraction /
calibration lại, sinh ra đúng object mà cross_validation.py và (sau này)
DXF Builder sẽ đọc.
"""

from __future__ import annotations

from typing import List, Optional

from .calibration import Calibration
from .geometry_extraction import RawCircle, RawLine
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


def text_to_primitive(raw: RawText, calibration: Calibration, height_px: float = 20.0) -> Primitive:
    """height_px: chiều cao chữ ước lượng bằng pixel (mặc định lấy chiều cao
    bbox nếu không truyền riêng) -> quy đổi ra đơn vị CAD bằng scale."""
    from .models import TextData

    position = calibration.pixel_to_cad(raw.bbox_px[0], raw.bbox_px[1])
    bbox_height_px = raw.bbox_px[3] - raw.bbox_px[1]
    height_cad = (bbox_height_px if bbox_height_px > 0 else height_px) * calibration.pixel_to_unit_scale

    tool = "tesseract-5.3" if raw.source == "text_tesseract" else "claude-vision"

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
    sha256: Optional[str] = None,
) -> PrimitiveIRDocument:
    """Entry point chính: sinh PrimitiveIRDocument đầy đủ (chưa có
    cross_validations — gọi cross_validation.cross_validate() rồi gán vào
    doc.cross_validations sau, vì hàm đó cần raw_texts/raw_lines ở dạng
    pixel gốc, không phải Primitive đã quy đổi)."""
    primitives: List[Primitive] = []
    primitives += [line_to_primitive(l, calibration) for l in raw_lines]
    primitives += [circle_to_primitive(c, calibration) for c in raw_circles]
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
