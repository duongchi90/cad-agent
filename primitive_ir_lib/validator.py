"""
validator.py — Kiểm tra 1 dict (đã to_dict() từ PrimitiveIRDocument) có tuân
thủ đúng các ràng buộc quan trọng của primitive_ir.schema.json hay không.

Không dùng thư viện `jsonschema` vì môi trường build package này không có
mạng để cài đặt. Đây KHÔNG phải bản thay thế đầy đủ cho việc validate bằng
`jsonschema.validate(doc, schema)` — nếu môi trường có mạng, nên chạy thêm
jsonschema cho chắc. Hàm ở đây bắt các lỗi phổ biến nhất: thiếu field bắt
buộc, sai enum, oneOf type/geometry không khớp.
"""

from __future__ import annotations

from typing import List

_VALID_TYPES = {"line", "circle", "arc", "text"}
_VALID_SOURCES = {"geometry_opencv", "text_tesseract", "text_vision"}
_VALID_ROLES = {"dimension_value", "title_block_field", "drawing_code", "general_note", "table_cell", "unknown"}
_VALID_VALIDATION_STATUS = {"unreviewed", "reviewer1_pass", "reviewer1_fail", "reviewer2_pass", "reviewer2_fail", "repaired"}
_VALID_CV_STATUS = {"confirmed", "conflict", "unverified"}


class SchemaViolation(Exception):
    pass


def validate_document(doc: dict) -> List[str]:
    """Trả về list các lỗi tìm thấy (rỗng = hợp lệ theo các ràng buộc đã kiểm)."""
    errors: List[str] = []

    for key in ("schema_version", "source_document", "calibration", "primitives"):
        if key not in doc:
            errors.append(f"Thiếu field bắt buộc ở cấp document: '{key}'")

    cal = doc.get("calibration", {})
    for key in ("unit", "pixel_to_unit_scale", "origin_px", "method"):
        if key not in cal:
            errors.append(f"calibration thiếu field bắt buộc: '{key}'")
    if cal.get("method") not in (None, "known_dimension_reference", "title_block_scale", "manual_override"):
        errors.append(f"calibration.method không hợp lệ: {cal.get('method')}")

    primitive_ids = set()
    for i, prim in enumerate(doc.get("primitives", [])):
        prefix = f"primitives[{i}] (id={prim.get('id')})"

        for key in ("id", "type", "source", "confidence", "layer", "handle", "trace", "validation"):
            if key not in prim:
                errors.append(f"{prefix}: thiếu field bắt buộc '{key}'")

        ptype = prim.get("type")
        if ptype not in _VALID_TYPES:
            errors.append(f"{prefix}: type '{ptype}' không hợp lệ")

        source = prim.get("source")
        if source not in _VALID_SOURCES:
            errors.append(f"{prefix}: source '{source}' không hợp lệ")

        conf = prim.get("confidence")
        if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
            errors.append(f"{prefix}: confidence '{conf}' phải là số trong [0,1]")

        if ptype == "text":
            if "text_data" not in prim:
                errors.append(f"{prefix}: type='text' nhưng thiếu 'text_data'")
            elif prim["text_data"].get("semantic_role") not in _VALID_ROLES:
                errors.append(f"{prefix}: semantic_role không hợp lệ")
        elif ptype in ("line", "circle", "arc"):
            if "geometry" not in prim:
                errors.append(f"{prefix}: type='{ptype}' nhưng thiếu 'geometry'")

        val_status = prim.get("validation", {}).get("status")
        if val_status not in _VALID_VALIDATION_STATUS:
            errors.append(f"{prefix}: validation.status '{val_status}' không hợp lệ")

        if prim.get("id") in primitive_ids:
            errors.append(f"{prefix}: id trùng lặp trong document")
        primitive_ids.add(prim.get("id"))

    for i, cv in enumerate(doc.get("cross_validations", [])):
        prefix = f"cross_validations[{i}] (id={cv.get('id')})"
        for key in ("id", "text_primitive_id", "geometry_primitive_id", "status"):
            if key not in cv:
                errors.append(f"{prefix}: thiếu field bắt buộc '{key}'")
        if cv.get("status") not in _VALID_CV_STATUS:
            errors.append(f"{prefix}: status '{cv.get('status')}' không hợp lệ")
        if cv.get("text_primitive_id") and cv["text_primitive_id"] not in primitive_ids:
            errors.append(f"{prefix}: text_primitive_id '{cv['text_primitive_id']}' không tồn tại trong primitives")
        gid = cv.get("geometry_primitive_id")
        if gid and gid not in primitive_ids:
            errors.append(f"{prefix}: geometry_primitive_id '{gid}' không tồn tại trong primitives")

    return errors
