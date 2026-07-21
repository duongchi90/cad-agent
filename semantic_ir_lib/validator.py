"""
validator.py — kiểm tra nhẹ 1 dict (đã to_dict() từ SemanticIRDocument) theo
semantic_ir.schema.json, cùng phong cách/lý do như primitive_ir_lib/validator.py
(không dùng lib `jsonschema`, chỉ bắt lỗi phổ biến nhất). Thêm 1 kiểm tra
riêng cho tầng này mà Phase 1 không có: mọi `primitive_ids` tham chiếu
trong parts/constraints phải khớp với 1 id thật trong PrimitiveIRDocument
gốc — lỗi này đặc biệt quan trọng ở Semantic IR vì mọi field ở đây chỉ là
THAM CHIẾU (không tự chứa geometry), tham chiếu treo (dangling reference)
sẽ làm hỏng toàn bộ bước Constraint Solving sau này mà không báo lỗi rõ.
"""

from __future__ import annotations

from typing import List, Optional, Set

_VALID_PART_TYPES = {
    # single-primitive parts
    "thanh_ngang", "thanh_doc", "thanh_xien",
    "lo_bat_vit", "duong_vien_tron",
    # compound parts (pattern_compound.py)
    "khung_chu_nhat", "gia_do", "ban_le", "diem_noi",
    "unclassified",
}
_VALID_PART_SOURCES = {"rule_geometry", "vision_assisted"}
_VALID_CONSTRAINT_TYPES = {
    "parallel", "perpendicular", "equal_length", "coincident_endpoint", "collinear",
    "tangent", "concentric",
}


def validate_document(doc: dict, known_primitive_ids: Optional[Set[str]] = None) -> List[str]:
    """known_primitive_ids: set id primitive của PrimitiveIRDocument gốc —
    truyền vào để bắt tham chiếu treo. Bỏ trống (None) nếu chỉ muốn kiểm
    cấu trúc Semantic IR độc lập, không đối chiếu ngược Phase 1."""
    errors: List[str] = []

    for key in ("schema_version", "primitive_ir_ref", "parts", "constraints"):
        if key not in doc:
            errors.append(f"Thiếu field bắt buộc ở cấp document: '{key}'")

    ref = doc.get("primitive_ir_ref", {})
    for key in ("file_name", "primitive_count"):
        if key not in ref:
            errors.append(f"primitive_ir_ref thiếu field bắt buộc: '{key}'")

    part_ids = set()
    for i, part in enumerate(doc.get("parts", [])):
        prefix = f"parts[{i}] (id={part.get('id')})"
        for key in ("id", "part_type", "primitive_ids", "confidence", "source"):
            if key not in part:
                errors.append(f"{prefix}: thiếu field bắt buộc '{key}'")

        if part.get("part_type") not in _VALID_PART_TYPES:
            errors.append(f"{prefix}: part_type '{part.get('part_type')}' không hợp lệ")
        if part.get("source") not in _VALID_PART_SOURCES:
            errors.append(f"{prefix}: source '{part.get('source')}' không hợp lệ")

        conf = part.get("confidence")
        if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
            errors.append(f"{prefix}: confidence '{conf}' phải là số trong [0,1]")

        pids = part.get("primitive_ids") or []
        if not pids:
            errors.append(f"{prefix}: primitive_ids không được rỗng")
        if known_primitive_ids is not None:
            for pid in pids:
                if pid not in known_primitive_ids:
                    errors.append(f"{prefix}: primitive_ids chứa id treo '{pid}' (không có trong Primitive IR gốc)")

        if part.get("id") in part_ids:
            errors.append(f"{prefix}: id trùng lặp trong document")
        part_ids.add(part.get("id"))

    constraint_ids = set()
    for i, c in enumerate(doc.get("constraints", [])):
        prefix = f"constraints[{i}] (id={c.get('id')})"
        for key in ("id", "type", "primitive_ids", "confidence", "tolerance"):
            if key not in c:
                errors.append(f"{prefix}: thiếu field bắt buộc '{key}'")

        if c.get("type") not in _VALID_CONSTRAINT_TYPES:
            errors.append(f"{prefix}: type '{c.get('type')}' không hợp lệ")

        conf = c.get("confidence")
        if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
            errors.append(f"{prefix}: confidence '{conf}' phải là số trong [0,1]")

        pids = c.get("primitive_ids") or []
        if len(pids) != 2:
            errors.append(f"{prefix}: primitive_ids phải có đúng 2 phần tử, nhận {len(pids)}")
        if known_primitive_ids is not None:
            for pid in pids:
                if pid not in known_primitive_ids:
                    errors.append(f"{prefix}: primitive_ids chứa id treo '{pid}' (không có trong Primitive IR gốc)")

        if c.get("id") in constraint_ids:
            errors.append(f"{prefix}: id trùng lặp trong document")
        constraint_ids.add(c.get("id"))

    return errors
