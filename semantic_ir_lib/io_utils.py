"""
io_utils.py — 2 việc:
  1. save_document() / load_document_dict(): lưu/đọc SemanticIRDocument,
     giống io_utils.py của primitive_ir_lib.
  2. load_primitive_ir_document(): đọc NGƯỢC 1 file JSON Primitive IR đã
     lưu ở Phase 1 (vd `demo_output/primitive_ir_demo_output.json`) và dựng
     lại thành object `PrimitiveIRDocument` thật — Phase 1 gốc chưa có hàm
     này (chỉ có save, không có load-thành-object) vì demo_pipeline.py of
     Phase 1 luôn build và dùng object trong cùng 1 lần chạy. Phase 2 cần
     chạy ĐỘC LẬP với Phase 1 (đọc file .json đã lưu từ lần chạy trước, có
     thể ở lần chạy chương trình khác) nên phải có loader thật ở đây.
"""

from __future__ import annotations

import json
from typing import Optional

from primitive_ir_lib.models import (
    ArcGeometry, Calibration, CircleGeometry, CrossValidation, LineGeometry,
    Point2D, Primitive, PrimitiveIRDocument, SourceDocument, TextData, Trace,
    Validation,
)

from .models import (
    Constraint, GeometrySummary, PartValidation, PrimitiveIRRef,
    SemanticIRDocument, SemanticPart,
)


def save_document(doc: SemanticIRDocument, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc.to_dict(), f, indent=2, ensure_ascii=False)


def load_document_dict(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _point_from_dict(d: dict) -> Point2D:
    return Point2D(x=d["x"], y=d["y"])


def _geometry_from_dict(prim_type: str, d: dict):
    if prim_type == "line":
        return LineGeometry(start=_point_from_dict(d["start"]), end=_point_from_dict(d["end"]))
    if prim_type == "circle":
        return CircleGeometry(center=_point_from_dict(d["center"]), radius=d["radius"])
    if prim_type == "arc":
        return ArcGeometry(
            center=_point_from_dict(d["center"]), radius=d["radius"],
            start_angle_deg=d["start_angle_deg"], end_angle_deg=d["end_angle_deg"],
        )
    raise ValueError(f"Không nhận diện được geometry cho primitive type={prim_type!r}")


def _primitive_from_dict(d: dict) -> Primitive:
    geometry = _geometry_from_dict(d["type"], d["geometry"]) if "geometry" in d else None
    text_data = None
    if "text_data" in d:
        td = d["text_data"]
        text_data = TextData(
            content=td["content"],
            position=_point_from_dict(td["position"]),
            rotation_deg=td["rotation_deg"],
            height=td["height"],
            parsed_value=td.get("parsed_value"),
            semantic_role=td.get("semantic_role", "unknown"),
        )
    trace_d = d["trace"]
    trace = Trace(
        bbox_px=tuple(trace_d["bbox_px"]),
        extraction_tool=trace_d.get("extraction_tool"),
        extracted_at=trace_d.get("extracted_at"),
    )
    validation_d = d.get("validation", {})
    validation = Validation(
        status=validation_d.get("status", "unreviewed"),
        notes=validation_d.get("notes"),
    )
    return Primitive(
        id=d["id"],
        type=d["type"],
        source=d["source"],
        confidence=d["confidence"],
        trace=trace,
        layer=d.get("layer", "UNCLASSIFIED"),
        handle=d.get("handle"),
        geometry=geometry,
        text_data=text_data,
        validation=validation,
    )


def load_primitive_ir_document(path: str) -> PrimitiveIRDocument:
    """Đọc file JSON Primitive IR (output Phase 1) và dựng lại thành
    PrimitiveIRDocument object thật — dùng làm input cho
    `semantic_ir_lib.assemble.build_semantic_document()`."""
    data = load_document_dict(path)

    sd = data["source_document"]
    source_document = SourceDocument(
        file_name=sd["file_name"], page_index=sd["page_index"],
        image_width_px=sd["image_width_px"], image_height_px=sd["image_height_px"],
        sha256=sd.get("sha256"),
    )

    cal = data["calibration"]
    calibration = Calibration(
        unit=cal["unit"], pixel_to_unit_scale=cal["pixel_to_unit_scale"],
        origin_px=tuple(cal["origin_px"]), method=cal["method"],
        reference_note=cal.get("reference_note"),
    )

    primitives = [_primitive_from_dict(p) for p in data["primitives"]]

    cross_validations = []
    for cv in data.get("cross_validations", []):
        cross_validations.append(CrossValidation(
            id=cv["id"],
            text_primitive_id=cv["text_primitive_id"],
            geometry_primitive_id=cv["geometry_primitive_id"],
            status=cv["status"],
            text_value=cv.get("text_value"),
            geometry_measured_length=cv.get("geometry_measured_length"),
            delta_percent=cv.get("delta_percent"),
            match_threshold_percent=cv.get("match_threshold_percent", 3.0),
        ))

    return PrimitiveIRDocument(
        source_document=source_document,
        calibration=calibration,
        primitives=primitives,
        cross_validations=cross_validations,
        schema_version=data.get("schema_version", "1.0.0"),
    )


def _geometry_summary_from_dict(d: Optional[dict]) -> Optional[GeometrySummary]:
    if not d:
        return None
    return GeometrySummary(
        length_mm=d.get("length_mm"),
        orientation_deg=d.get("orientation_deg"),
        radius_mm=d.get("radius_mm"),
    )


def _semantic_part_from_dict(d: dict) -> SemanticPart:
    validation_d = d.get("validation", {})
    return SemanticPart(
        id=d["id"],
        part_type=d["part_type"],
        primitive_ids=list(d["primitive_ids"]),
        confidence=d["confidence"],
        source=d.get("source", "rule_geometry"),
        geometry_summary=_geometry_summary_from_dict(d.get("geometry_summary")),
        validation=PartValidation(
            status=validation_d.get("status", "unreviewed"),
            notes=validation_d.get("notes"),
        ),
    )


def _constraint_from_dict(d: dict) -> Constraint:
    return Constraint(
        id=d["id"],
        type=d["type"],
        primitive_ids=list(d["primitive_ids"]),
        confidence=d["confidence"],
        tolerance=d.get("tolerance", {}),
        measured=d.get("measured"),
    )


def load_semantic_ir_document(path: str) -> SemanticIRDocument:
    """Đọc file JSON Semantic IR (output Phase 2, vd
    `demo_output/semantic_ir_demo_output.json`) và dựng lại thành
    `SemanticIRDocument` object thật (parts/constraints là dataclass thật,
    không phải dict thô) — cùng lý do với `load_primitive_ir_document()`:
    Phase 3 (DXF Builder) cần chạy ĐỘC LẬP với Phase 2, đọc file .json đã
    lưu từ lần chạy trước, không dùng chung object trong bộ nhớ."""
    data = load_document_dict(path)

    ref_d = data["primitive_ir_ref"]
    primitive_ir_ref = PrimitiveIRRef(
        file_name=ref_d["file_name"],
        primitive_count=ref_d["primitive_count"],
        sha256=ref_d.get("sha256"),
    )

    parts = [_semantic_part_from_dict(p) for p in data.get("parts", [])]
    constraints = [_constraint_from_dict(c) for c in data.get("constraints", [])]

    return SemanticIRDocument(
        primitive_ir_ref=primitive_ir_ref,
        parts=parts,
        constraints=constraints,
        schema_version=data.get("schema_version", "1.0.0"),
    )
