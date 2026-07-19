"""
verify_full.py — Kiểm chứng toàn bộ assemble + validator với tier-2 (không cần
binary Tesseract, máy này chưa cài tesseract.exe).

Khác verify_tier2.py: file này chạy đến BƯỚC CUỐI CÙNG mà demo_pipeline chạy —
build_document -> PrimitiveIRDocument (toạ độ CAD) -> validate_document ->
lưu JSON. Verify rằng output có primitive type=text với semantic_role
table_cell/dimension_value, đúng primitive_ir.schema.json.

Chạy: python verify_full.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from primitive_ir_lib.assemble import build_document
from primitive_ir_lib.calibration import auto_estimate_calibration
from primitive_ir_lib.cross_validation import cross_validate
from primitive_ir_lib.demo_pipeline import make_synthetic_drawing, IMG_W, IMG_H, TABLE_ROI
from primitive_ir_lib.geometry_extraction import extract_raw_geometry
from primitive_ir_lib.io_utils import save_document
from primitive_ir_lib.table_extraction import extract_table_cells
from primitive_ir_lib.validator import validate_document

EXPECTED = [["DAI", "RONG", "CAO"], ["4200", "1900", "2100"]]


def stub_reader(image_bgr, bbox):
    x0, y0, x1, y1 = bbox
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    col = min(2, int((cx - TABLE_ROI[0]) / (TABLE_ROI[2] - TABLE_ROI[0]) * 3))
    row = 0 if cy < (TABLE_ROI[1] + TABLE_ROI[3]) / 2 else 1
    return EXPECTED[row][col]


def main() -> int:
    image = make_synthetic_drawing()

    # Geometry
    raw_geom = extract_raw_geometry(image, hough_threshold=50, min_line_length=40, max_line_gap=5)
    print(f"[geometry] {len(raw_geom.lines)} line, {len(raw_geom.circles)} circle")

    # Tier 2 (table)
    cells, raw_texts = extract_table_cells(image, raw_geom.lines, TABLE_ROI, cell_reader=stub_reader)
    print(f"[tier2] {len(cells)} ô, {len(raw_texts)} text")

    # Calibration: dùng 1 dimension_value từ bảng (vd '4200') + line gần nhất
    calibration = auto_estimate_calibration(raw_texts, raw_geom.lines, image_height_px=IMG_H)
    if calibration is None:
        print("[calibration] KHÔNG ước lượng được -> dùng manual_override")
        from primitive_ir_lib.models import Calibration
        calibration = Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0.0, float(IMG_H)), method="manual_override")
    else:
        print(f"[calibration] scale={calibration.pixel_to_unit_scale}")

    # Cross-validate
    cvs = cross_validate(raw_texts, raw_geom.lines, calibration, threshold_percent=3.0)
    print(f"[cross-validate] {len(cvs)} so khớp: {[c.status for c in cvs]}")

    # Assemble
    doc = build_document(
        file_name="synthetic_test_drawing.png", page_index=0,
        image_width_px=IMG_W, image_height_px=IMG_H,
        calibration=calibration, raw_lines=raw_geom.lines,
        raw_circles=raw_geom.circles, raw_texts=raw_texts,
    )
    doc.cross_validations = cvs

    # Validate
    doc_dict = doc.to_dict()
    errors = validate_document(doc_dict)
    if errors:
        print("[validate] LỖI SCHEMA:")
        for e in errors:
            print("   -", e)
        return 1
    print(f"[validate] OK — {len(doc.primitives)} primitives, {len(doc.cross_validations)} cross_validations")

    # Kiểm tra có primitive table_cell không
    roles = [p.text_data.semantic_role for p in doc.primitives if p.type == "text"]
    print(f"[roles] semantic_role trong text primitives: {sorted(set(roles))}")
    assert "table_cell" in roles, "thiếu primitive table_cell"
    assert "dimension_value" in roles, "thiếu primitive dimension_value"

    # Lưu JSON
    out_dir = os.path.join(os.path.dirname(__file__), "demo_output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "primitive_ir_demo_output_tier2.json")
    save_document(doc, out_path)
    print(f"[save] {out_path}")

    print("\n>>> VERIFY FULL OK: tier-2 integrate vào PrimitiveIRDocument, valid theo schema")
    return 0


if __name__ == "__main__":
    sys.exit(main())
