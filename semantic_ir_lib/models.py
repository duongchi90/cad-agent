"""
models.py — Dataclass Python khớp 1-1 với semantic_ir.schema.json (v1.0.0).

Cùng nguyên tắc đã áp dụng ở primitive_ir_lib/models.py: to_dict() phải sinh
đúng cấu trúc schema yêu cầu, đây là lớp code DUY NHẤT "biết" chi tiết
schema. pattern_recognition.py và constraint_detection.py chỉ import và
dùng class ở đây, không tự build dict tay.

QUAN TRỌNG: SemanticPart/Constraint chỉ giữ id tham chiếu (primitive_ids),
KHÔNG sao chép geometry/text từ Primitive IR gốc (xem mô tả trong
semantic_ir.schema.json và mục 10.1 tài liệu kiến trúc) — muốn lấy geometry
đầy đủ của 1 part, tra ngược primitive_ids đó trong PrimitiveIRDocument gốc.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Literal, Optional

SCHEMA_VERSION = "1.0.0"

PartType = Literal[
    # --- single-primitive parts (pattern_recognition.py) ---
    "thanh_ngang", "thanh_doc", "thanh_xien",
    "lo_bat_vit", "duong_vien_tron",
    # --- compound parts: ghép nhiều primitive (pattern_compound.py) ---
    # Thêm ở Phase 2 nâng cao (mục 11.4 tài liệu kiến trúc) — luật hình học
    # thuần tái dùng các constraint đã detect, KHÔNG đoán bừa (mục 10.1).
    "khung_chu_nhat",   # 4 line tạo khung kín (2 cặp parallel + 4 coincident_endpoint)
    "gia_do",            # L-bracket: 2 line vuông góc + coincident_endpoint tại 1 đầu
    "ban_le",            # hinge: 2 line song song + coincident_endpoint + 2 lỗ bắt vít
    "diem_noi",          # điểm nối hàn/gia cố: >=2 line coincident_endpoint tại 1 điểm chung
    "unclassified",
]
PartSource = Literal["rule_geometry", "vision_assisted"]
PartValidationStatus = Literal["unreviewed", "reviewer2_pass", "reviewer2_fail", "repaired"]
ConstraintType = Literal[
    "parallel", "perpendicular", "equal_length", "coincident_endpoint", "collinear",
]


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ------------------------------------------------------------ GeometrySummary --
@dataclass
class GeometrySummary:
    length_mm: Optional[float] = None
    orientation_deg: Optional[float] = None
    radius_mm: Optional[float] = None

    def to_dict(self) -> dict:
        d = {}
        if self.length_mm is not None:
            d["length_mm"] = self.length_mm
        if self.orientation_deg is not None:
            d["orientation_deg"] = self.orientation_deg
        if self.radius_mm is not None:
            d["radius_mm"] = self.radius_mm
        return d


@dataclass
class PartValidation:
    status: PartValidationStatus = "unreviewed"
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"status": self.status}
        if self.notes is not None:
            d["notes"] = self.notes
        return d


# ------------------------------------------------------------------ SemanticPart --
@dataclass
class SemanticPart:
    part_type: PartType
    primitive_ids: List[str]
    confidence: float
    source: PartSource = "rule_geometry"
    id: str = field(default_factory=lambda: new_id("part"))
    geometry_summary: Optional[GeometrySummary] = None
    validation: PartValidation = field(default_factory=PartValidation)

    def __post_init__(self):
        if not self.primitive_ids:
            raise ValueError(f"SemanticPart {self.id}: primitive_ids không được rỗng")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"SemanticPart {self.id}: confidence phải trong [0,1], nhận {self.confidence}")

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "part_type": self.part_type,
            "primitive_ids": list(self.primitive_ids),
            "confidence": self.confidence,
            "source": self.source,
            "validation": self.validation.to_dict(),
        }
        if self.geometry_summary is not None:
            gs = self.geometry_summary.to_dict()
            if gs:
                d["geometry_summary"] = gs
        return d


# -------------------------------------------------------------------- Constraint --
@dataclass
class Constraint:
    type: ConstraintType
    primitive_ids: List[str]
    confidence: float
    tolerance: dict  # {"angle_deg": ...} | {"length_percent": ...} | {"distance_mm": ...}
    id: str = field(default_factory=lambda: new_id("cst"))
    measured: Optional[dict] = None

    def __post_init__(self):
        if len(self.primitive_ids) != 2:
            raise ValueError(f"Constraint {self.id}: primitive_ids phải có đúng 2 phần tử")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Constraint {self.id}: confidence phải trong [0,1], nhận {self.confidence}")

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "type": self.type,
            "primitive_ids": list(self.primitive_ids),
            "confidence": self.confidence,
            "tolerance": self.tolerance,
        }
        if self.measured is not None:
            d["measured"] = self.measured
        return d


# ------------------------------------------------------------- PrimitiveIRRef --
@dataclass
class PrimitiveIRRef:
    file_name: str
    primitive_count: int
    sha256: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"file_name": self.file_name, "primitive_count": self.primitive_count}
        if self.sha256 is not None:
            d["sha256"] = self.sha256
        return d


# --------------------------------------------------------- SemanticIRDocument --
@dataclass
class SemanticIRDocument:
    primitive_ir_ref: PrimitiveIRRef
    parts: List[SemanticPart] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "primitive_ir_ref": self.primitive_ir_ref.to_dict(),
            "parts": [p.to_dict() for p in self.parts],
            "constraints": [c.to_dict() for c in self.constraints],
        }
