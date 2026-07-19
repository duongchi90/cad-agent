"""
models.py — Dataclass Python khớp 1-1 với primitive_ir.schema.json (v1.0.0).

Nguyên tắc: to_dict() của mọi class ở đây phải sinh ra đúng JSON structure
mà schema yêu cầu (đúng field name, đúng field bắt buộc, additionalProperties=false
nghĩa là KHÔNG được thừa field). Đây là lớp code duy nhất "biết" chi tiết schema,
mọi module khác (geometry_extraction, text_extraction, cross_validation) chỉ
import và dùng các class này, không tự ý build dict tay.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

SCHEMA_VERSION = "1.0.0"

PrimitiveType = Literal["line", "circle", "arc", "text"]
SourceType = Literal["geometry_opencv", "text_tesseract", "text_vision"]
SemanticRole = Literal[
    "dimension_value", "title_block_field", "drawing_code",
    "general_note", "table_cell", "unknown",
]
ValidationStatus = Literal[
    "unreviewed", "reviewer1_pass", "reviewer1_fail",
    "reviewer2_pass", "reviewer2_fail", "repaired",
]
CrossValStatus = Literal["confirmed", "conflict", "unverified"]


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- Point2D --
@dataclass
class Point2D:
    x: float
    y: float

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y}


# ------------------------------------------------------------- Geometries --
@dataclass
class LineGeometry:
    start: Point2D
    end: Point2D

    def to_dict(self) -> dict:
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}

    def length(self) -> float:
        return ((self.end.x - self.start.x) ** 2 + (self.end.y - self.start.y) ** 2) ** 0.5


@dataclass
class CircleGeometry:
    center: Point2D
    radius: float

    def to_dict(self) -> dict:
        return {"center": self.center.to_dict(), "radius": self.radius}


@dataclass
class ArcGeometry:
    center: Point2D
    radius: float
    start_angle_deg: float
    end_angle_deg: float

    def to_dict(self) -> dict:
        return {
            "center": self.center.to_dict(),
            "radius": self.radius,
            "start_angle_deg": self.start_angle_deg,
            "end_angle_deg": self.end_angle_deg,
        }


# ------------------------------------------------------------------ Text --
@dataclass
class TextData:
    content: str
    position: Point2D
    rotation_deg: float
    height: float
    parsed_value: Optional[float] = None
    semantic_role: SemanticRole = "unknown"

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "position": self.position.to_dict(),
            "rotation_deg": self.rotation_deg,
            "height": self.height,
            "parsed_value": self.parsed_value,
            "semantic_role": self.semantic_role,
        }


# ----------------------------------------------------------------- Trace --
@dataclass
class Trace:
    bbox_px: tuple  # (x_min, y_min, x_max, y_max)
    extraction_tool: Optional[str] = None
    extracted_at: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"bbox_px": list(self.bbox_px)}
        if self.extraction_tool is not None:
            d["extraction_tool"] = self.extraction_tool
        if self.extracted_at is not None:
            d["extracted_at"] = self.extracted_at
        return d


@dataclass
class Validation:
    status: ValidationStatus = "unreviewed"
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"status": self.status}
        if self.notes is not None:
            d["notes"] = self.notes
        return d


# ------------------------------------------------------------- Primitive --
@dataclass
class Primitive:
    type: PrimitiveType
    source: SourceType
    confidence: float
    trace: Trace
    id: str = field(default_factory=lambda: new_id("prim"))
    layer: str = "UNCLASSIFIED"
    handle: Optional[str] = None
    geometry: Optional[object] = None       # LineGeometry | CircleGeometry | ArcGeometry
    text_data: Optional[TextData] = None
    validation: Validation = field(default_factory=Validation)

    def __post_init__(self):
        if self.type == "text" and self.text_data is None:
            raise ValueError(f"Primitive {self.id}: type='text' bắt buộc phải có text_data")
        if self.type in ("line", "circle", "arc") and self.geometry is None:
            raise ValueError(f"Primitive {self.id}: type='{self.type}' bắt buộc phải có geometry")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Primitive {self.id}: confidence phải trong [0,1], nhận {self.confidence}")

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "confidence": self.confidence,
            "layer": self.layer,
            "handle": self.handle,
            "trace": self.trace.to_dict(),
            "validation": self.validation.to_dict(),
        }
        if self.geometry is not None:
            d["geometry"] = self.geometry.to_dict()
        if self.text_data is not None:
            d["text_data"] = self.text_data.to_dict()
        return d


# --------------------------------------------------------- CrossValidation --
@dataclass
class CrossValidation:
    text_primitive_id: str
    geometry_primitive_id: str
    status: CrossValStatus
    id: str = field(default_factory=lambda: new_id("cv"))
    text_value: Optional[float] = None
    geometry_measured_length: Optional[float] = None
    delta_percent: Optional[float] = None
    match_threshold_percent: float = 3.0

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "text_primitive_id": self.text_primitive_id,
            "geometry_primitive_id": self.geometry_primitive_id,
            "status": self.status,
            "match_threshold_percent": self.match_threshold_percent,
        }
        if self.text_value is not None:
            d["text_value"] = self.text_value
        if self.geometry_measured_length is not None:
            d["geometry_measured_length"] = self.geometry_measured_length
        if self.delta_percent is not None:
            d["delta_percent"] = self.delta_percent
        return d


# ------------------------------------------------------------- Calibration --
@dataclass
class Calibration:
    unit: Literal["mm", "cm", "m"]
    pixel_to_unit_scale: float
    origin_px: tuple  # (x, y)
    method: Literal["known_dimension_reference", "title_block_scale", "manual_override"]
    reference_note: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "unit": self.unit,
            "pixel_to_unit_scale": self.pixel_to_unit_scale,
            "origin_px": list(self.origin_px),
            "method": self.method,
        }
        if self.reference_note is not None:
            d["reference_note"] = self.reference_note
        return d

    def pixel_to_cad(self, px_x: float, px_y: float) -> Point2D:
        """Quy đổi tọa độ pixel (gốc trên-trái, y xuống) -> tọa độ CAD (y lên)."""
        cad_x = (px_x - self.origin_px[0]) * self.pixel_to_unit_scale
        cad_y = (self.origin_px[1] - px_y) * self.pixel_to_unit_scale
        return Point2D(cad_x, cad_y)


# ----------------------------------------------------------- SourceDocument --
@dataclass
class SourceDocument:
    file_name: str
    page_index: int
    image_width_px: int
    image_height_px: int
    sha256: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "file_name": self.file_name,
            "page_index": self.page_index,
            "image_width_px": self.image_width_px,
            "image_height_px": self.image_height_px,
        }
        if self.sha256 is not None:
            d["sha256"] = self.sha256
        return d


# ------------------------------------------------------- PrimitiveIRDocument --
@dataclass
class PrimitiveIRDocument:
    source_document: SourceDocument
    calibration: Calibration
    primitives: list  # list[Primitive]
    cross_validations: list = field(default_factory=list)  # list[CrossValidation]
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "source_document": self.source_document.to_dict(),
            "calibration": self.calibration.to_dict(),
            "primitives": [p.to_dict() for p in self.primitives],
            "cross_validations": [c.to_dict() for c in self.cross_validations],
        }
