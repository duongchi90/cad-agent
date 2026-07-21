"""
assemble.py — ghép output pattern_recognition.py + constraint_detection.py
(+ pattern_compound.py ở Phase 2 nâng cao) thành 1 SemanticIRDocument hoàn
chỉnh, đúng chức năng tương tự primitive_ir_lib/assemble.py ở Phase 1.

Phase 2 nâng cao: sau khi đã có single-parts (pattern_recognition) +
constraints (constraint_detection), gọi thêm pattern_compound để ghép
compound parts (khung_chu_nhat/gia_do/ban_le/diem_noi) và gộp vào parts[].
Compound là lớp bổ sung, KHÔNG thay thế single-part — primitive tham gia
compound vẫn giữ single-part của nó (xem docstring pattern_compound.py).
"""

from __future__ import annotations

from typing import List

from primitive_ir_lib.models import Primitive, PrimitiveIRDocument

from .constraint_detection import detect_circle_constraints, detect_constraints
from .models import PrimitiveIRRef, SemanticIRDocument
from .pattern_compound import build_compound_parts
from .pattern_recognition import build_parts_from_primitives


def build_semantic_document(
    primitive_doc: PrimitiveIRDocument,
    primitive_ir_file_name: str,
    angle_tolerance_deg: float = 10.0,
    bolt_hole_max_radius_mm: float = 15.0,
    constraint_angle_tolerance_deg: float = 3.0,
    constraint_length_tolerance_percent: float = 3.0,
    # 5.0mm — đồng bộ _DEFAULT_DISTANCE_TOL_MM của constraint_detection.py,
    # xem comment ở đó cho bằng chứng đo được (corner gap 3.43mm sau Hough).
    constraint_distance_tolerance_mm: float = 5.0,
    enable_compound_parts: bool = True,
    compound_bolt_hole_search_radius_mm: float = 30.0,
    compound_parallel_gap_max_mm: float = 50.0,
) -> SemanticIRDocument:
    """Entry point Phase 2: nhận 1 PrimitiveIRDocument đã có (đầu ra Phase 1),
    sinh SemanticIRDocument tương ứng.

    primitive_ir_file_name: tên file JSON Primitive IR đã lưu (Semantic IR
    chỉ tham chiếu tên + số lượng primitive, không nhúng lại toàn bộ — xem
    semantic_ir.schema.json).

    enable_compound_parts: True (mặc định) — chạy thêm pattern_compound để
    ghép linh kiện phức hợp (khung/gia_do/ban_le/diem_noi). Đặt False nếu chỉ
    muốn single-parts (vd so sánh trước/sau khi bật compound, hoặc debug).
    """
    primitives: List[Primitive] = primitive_doc.primitives
    line_primitives = [p for p in primitives if p.type == "line"]
    circle_primitives = [p for p in primitives if p.type == "circle"]

    parts = build_parts_from_primitives(
        primitives,
        angle_tolerance_deg=angle_tolerance_deg,
        bolt_hole_max_radius_mm=bolt_hole_max_radius_mm,
    )
    constraints = detect_constraints(
        line_primitives,
        angle_tolerance_deg=constraint_angle_tolerance_deg,
        length_tolerance_percent=constraint_length_tolerance_percent,
        distance_tolerance_mm=constraint_distance_tolerance_mm,
    )
    # tangent (line-circle) + concentric (circle-circle) — cùng ngưỡng
    # distance_tolerance_mm với line-line ở trên (mục 11.4 tài liệu kiến
    # trúc: "Còn thiếu: constraint line-circle/circle-circle", đã bổ sung).
    constraints += detect_circle_constraints(
        line_primitives,
        circle_primitives,
        distance_tolerance_mm=constraint_distance_tolerance_mm,
    )

    # Phase 2 nâng cao: ghép compound parts phía trên single-parts. Dùng cùng
    # danh sách constraints đã detect (tái dùng, không đo lại) — compound chỉ
    # xác minh điều kiện tổ hợp. coincident_distance_mm đồng bộ với
    # constraint_distance_tolerance_mm ở trên (cùng ngưỡng cluster endpoint).
    if enable_compound_parts:
        compound_parts = build_compound_parts(
            primitives,
            constraints,
            bolt_hole_search_radius_mm=compound_bolt_hole_search_radius_mm,
            parallel_gap_max_mm=compound_parallel_gap_max_mm,
            coincident_distance_mm=constraint_distance_tolerance_mm,
        )
        parts = parts + compound_parts

    return SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(
            file_name=primitive_ir_file_name,
            primitive_count=len(primitives),
        ),
        parts=parts,
        constraints=constraints,
    )
