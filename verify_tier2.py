"""
verify_tier2.py — Kiểm chứng tier-2 (table grid-cell splitting) trên OpenCV
THẬT, không cần binary Tesseract (máy Windows này chưa cài tesseract.exe).

Pipeline thật được kiểm tra: sinh ảnh bảng 2x3 -> Canny+Hough (OpenCV thật) ->
detect_grid (từ RawLine) -> build_cells -> 6 ô. Reader dùng STUB theo vị trí ô
(vì mục đích verify là phần HÌNH HỌC/lưới, không phải OCR — OCR từng ô đã được
test riêng qua test_extract_table_cells_uses_reader_per_cell).

Chạy: python verify_tier2.py  (từ thư mục cha của primitive_ir_lib)
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

# đảm bảo import được package khi chạy từ thư mục primitive_ir_lib/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from primitive_ir_lib.demo_pipeline import make_synthetic_drawing, IMG_W, IMG_H, TABLE_ROI
from primitive_ir_lib.geometry_extraction import extract_raw_geometry
from primitive_ir_lib.table_extraction import detect_grid, build_cells, extract_table_cells


EXPECTED = [["DAI", "RONG", "CAO"], ["4200", "1900", "2100"]]


def stub_reader_by_position(image_bgr: np.ndarray, bbox) -> str:
    """Stub: trả nội dung ô dựa vào vị trí (giống unit test), thay OCR thật."""
    x0, y0, x1, y1 = bbox
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    col = min(2, int((cx - TABLE_ROI[0]) / (TABLE_ROI[2] - TABLE_ROI[0]) * 3))
    row = 0 if cy < (TABLE_ROI[1] + TABLE_ROI[3]) / 2 else 1
    return EXPECTED[row][col]


def main() -> int:
    # 1) Sinh ảnh bảng 2x3 (dùng đúng hàm demo_pipeline dùng)
    image = make_synthetic_drawing()
    print(f"[image] {image.shape[1]}x{image.shape[0]} px, TABLE_ROI={TABLE_ROI}")

    # 2) Geometry extraction thật (OpenCV Canny + Hough)
    raw_geom = extract_raw_geometry(image, hough_threshold=50, min_line_length=40, max_line_gap=5)
    print(f"[geometry] {len(raw_geom.lines)} line, {len(raw_geom.circles)} circle")

    # 3) detect_grid từ RawLine (KHÔNG chạy Hough riêng)
    xs, ys = detect_grid(raw_geom.lines, TABLE_ROI)
    print(f"[grid] cột={len(xs)} (kỳ vọng 4), hàng={len(ys)} (kỳ vọng 3)")
    print(f"       xs={[round(v,1) for v in xs]}")
    print(f"       ys={[round(v,1) for v in ys]}")

    assert len(xs) == 4, f"FAIL: chỉ phát hiện {len(xs)} cột, kỳ vọng 4"
    assert len(ys) == 3, f"FAIL: chỉ phát hiện {len(ys)} hàng, kỳ vọng 3"

    # 4) build_cells + đọc bằng stub reader
    cells, raw_texts = extract_table_cells(image, raw_geom.lines, TABLE_ROI, cell_reader=stub_reader_by_position)
    print(f"[cells] {len(cells)} ô (kỳ vọng 6)")
    assert len(cells) == 6, f"FAIL: {len(cells)} ô, kỳ vọng 6"

    print("\n[cells] nội dung từng ô (row, col -> content):")
    by_pos = {}
    for c in cells:
        print(f"        ({c.row},{c.col}) bbox={[round(v,1) for v in c.bbox_px]} -> '{c.content}'")
        by_pos[(c.row, c.col)] = c.content

    # 5) Kiểm tra KHÔNG có cross-contamination: nội dung đúng vị trí, không trộn
    ok = True
    for (r, col), exp in zip(sorted(by_pos), [EXPECTED[r][c] for r in (0, 1) for c in (0, 1, 2)]):
        got = by_pos.get((r, col))
        status = "OK" if got == exp else "MISMATCH"
        if got != exp:
            ok = False
        print(f"  [{status}] ô ({r},{col})='{got}' kỳ vọng '{exp}'")

    print(f"\n[raw_texts] {len(raw_texts)} RawText (kỳ vọng 6)")
    for t in raw_texts:
        print(f"        '{t.content}' role={t.semantic_role} parsed={t.parsed_value}")

    if not ok:
        print("\n>>> VERIFY FAIL: có ô đọc sai vị trí (cross-contamination)")
        return 1
    print("\n>>> VERIFY OK: 6/6 ô đúng vị trí, không xáo trộn — tier-2 chạy đúng trên OpenCV thật")
    return 0


if __name__ == "__main__":
    sys.exit(main())
