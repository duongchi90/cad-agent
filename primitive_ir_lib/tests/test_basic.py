"""
test_basic.py — Test cơ bản cho các phép tính CỐT LÕI (không phụ thuộc ảnh
thật): calibration, cross-validation, schema validator, semantic role,
table grid-cell splitting (tier 2).
Chạy: python3 -m pytest primitive_ir_lib/tests/ -v   (hoặc chạy trực tiếp
file này bằng python3 nếu không có pytest).
"""

from __future__ import annotations

import math

from primitive_ir_lib.calibration import estimate_calibration_from_reference, find_nearest_line
from primitive_ir_lib.cross_validation import cross_validate
from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.models import Point2D, Primitive, LineGeometry, Trace
from primitive_ir_lib.table_extraction import build_cells, detect_grid, extract_table_cells
from primitive_ir_lib.text_extraction import RawText, classify_semantic_role
from primitive_ir_lib.validator import validate_document


def _line(p1, p2, id_="l1", confidence=0.9):
    return RawLine(id=id_, p1_px=p1, p2_px=p2, confidence=confidence,
                    bbox_px=(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])))


def _text(content, bbox, source="text_vision", id_="t1"):
    role, value = classify_semantic_role(content)
    return RawText(id=id_, content=content, bbox_px=bbox, rotation_deg=0.0,
                    confidence=0.95, source=source, parsed_value=value, semantic_role=role)


# ---------------------------------------------------------------- classify --
def test_classify_dimension_value():
    role, value = classify_semantic_role("1700")
    assert role == "dimension_value"
    assert value == 1700.0


def test_classify_drawing_code():
    role, value = classify_semantic_role("TP-TL-A001/07/26")
    assert role == "drawing_code"
    assert value is None


def test_classify_general_note():
    role, value = classify_semantic_role("Yêu cầu kỹ thuật hàn kín các mối nối")
    assert role == "general_note"


# ------------------------------------------------------------- calibration --
def test_calibration_scale_correct():
    line = _line((100, 50), (100, 550))  # 500px
    text = _text("1700", (60, 280, 90, 320))
    cal = estimate_calibration_from_reference(text, line, image_height_px=700)
    assert math.isclose(cal.pixel_to_unit_scale, 1700.0 / 500.0, rel_tol=1e-6)
    assert cal.method == "known_dimension_reference"


def test_pixel_to_cad_flips_y():
    line = _line((100, 50), (100, 550))
    text = _text("1700", (60, 280, 90, 320))
    cal = estimate_calibration_from_reference(text, line, image_height_px=700, origin_px=(100, 550))
    p_top = cal.pixel_to_cad(100, 50)      # đỉnh line trong ảnh (y pixel nhỏ)
    p_bottom = cal.pixel_to_cad(100, 550)  # đáy line trong ảnh (y pixel lớn) = origin
    assert math.isclose(p_bottom.y, 0.0, abs_tol=1e-6)
    assert p_top.y > p_bottom.y  # CAD y phải tăng lên khi pixel y giảm (flip đúng)


def test_find_nearest_line_respects_max_distance():
    near = _line((100, 280), (100, 320), id_="near")
    far = _line((900, 900), (950, 950), id_="far")
    text = _text("1700", (95, 290, 110, 310))
    found = find_nearest_line(text, [near, far], max_distance_px=50)
    assert found is not None and found.id == "near"

    found_none = find_nearest_line(text, [far], max_distance_px=50)
    assert found_none is None


# ---------------------------------------------------------- cross_validate --
def test_cross_validate_confirmed_within_threshold():
    line = _line((100, 50), (100, 550))  # 500px chính xác
    text = _text("1700", (60, 280, 90, 320))
    cal = estimate_calibration_from_reference(text, line, image_height_px=700)

    # Line thứ 2 hơi lệch (498px thay vì 500px) -> vẫn phải confirmed vì < 3%
    slightly_off_line = _line((300, 52), (300, 550), id_="l2")
    text2 = _text("1700", (260, 280, 290, 320), id_="t2")

    results = cross_validate([text2], [slightly_off_line], cal, threshold_percent=3.0)
    assert len(results) == 1
    assert results[0].status == "confirmed"


def test_cross_validate_conflict_beyond_threshold():
    line = _line((100, 50), (100, 550))
    text = _text("1700", (60, 280, 90, 320))
    cal = estimate_calibration_from_reference(text, line, image_height_px=700)

    # Line đo được ngắn hơn nhiều (350px) trong khi text ghi 1700 -> delta lớn
    wrong_line = _line((300, 200), (300, 550), id_="l3")  # 350px
    text2 = _text("1700", (260, 280, 290, 320), id_="t3")

    results = cross_validate([text2], [wrong_line], cal, threshold_percent=3.0)
    assert results[0].status == "conflict"
    assert results[0].delta_percent > 3.0


def test_cross_validate_unverified_when_no_line_nearby():
    line = _line((100, 50), (100, 550))
    text = _text("1700", (60, 280, 90, 320))
    cal = estimate_calibration_from_reference(text, line, image_height_px=700)

    far_line = _line((900, 900), (950, 950), id_="far")
    text2 = _text("1700", (260, 280, 290, 320), id_="t4")

    results = cross_validate([text2], [far_line], cal, threshold_percent=3.0, max_distance_px=50)
    assert results[0].status == "unverified"
    assert results[0].geometry_primitive_id == ""


def test_cross_validate_unverified_for_zero_dimension_value():
    """OCR can read drawing labels such as ``00`` as a numeric dimension."""
    line = _line((100, 50), (100, 550), id_="near")
    text = _text("00", (60, 280, 90, 320), id_="zero")
    cal = estimate_calibration_from_reference(_text("1700", (60, 280, 90, 320)), line,
                                              image_height_px=700)

    results = cross_validate([text], [line], cal)

    assert len(results) == 1
    assert results[0].status == "unverified"
    assert results[0].geometry_primitive_id == ""


# ----------------------------------------------------------- table tier 2 --
def _make_grid_lines(table_roi, rows=2, cols=3):
    """Dựng các RawLine tạo thành lưới bảng `rows x cols` ô (vùng table_roi).
    Trả về danh sách RawLine (3 đường ngang + 4 đường dọc cho 2x3) + danh sách
    toạ độ x (cột) / y (hàng) kỳ vọng để test đối chiếu."""
    x0, y0, x1, y1 = table_roi
    xs = [x0 + i * (x1 - x0) / cols for i in range(cols + 1)]
    ys = [y0 + i * (y1 - y0) / rows for i in range(rows + 1)]
    lines = []
    # đường ngang (trải hết chiều rộng bảng)
    for i, y in enumerate(ys):
        lines.append(_line((x0, y), (x1, y), id_=f"h{i}"))
    # đường dọc (trải hết chiều cao bảng)
    for i, x in enumerate(xs):
        lines.append(_line((x, y0), (x, y1), id_=f"v{i}"))
    return lines, xs, ys


def test_detect_grid_finds_columns_and_rows():
    roi = (560, 40, 880, 160)
    lines, exp_xs, exp_ys = _make_grid_lines(roi, rows=2, cols=3)
    xs, ys = detect_grid(lines, roi)
    assert len(xs) == 4, f"thấy {len(xs)} cột, kỳ vọng 4"
    assert len(ys) == 3, f"thấy {len(ys)} hàng, kỳ vọng 3"
    for got, exp in zip(xs, exp_xs):
        assert math.isclose(got, exp, abs_tol=1.0)
    for got, exp in zip(ys, exp_ys):
        assert math.isclose(got, exp, abs_tol=1.0)


def test_detect_grid_ignores_lines_outside_roi():
    roi = (560, 40, 880, 160)
    lines, _, _ = _make_grid_lines(roi, rows=2, cols=3)
    # thêm 1 line ngang xa vùng bảng -> phải bị bỏ qua
    lines.append(_line((10, 10), (50, 10), id_="far"))
    xs, ys = detect_grid(lines, roi)
    assert len(ys) == 3  # vẫn đúng 3 hàng, line 'far' không lẫn vào


def test_detect_grid_clusters_near_duplicate_lines():
    roi = (560, 40, 880, 160)
    lines, exp_xs, exp_ys = _make_grid_lines(roi, rows=2, cols=3)
    # thêm 1 line ngang gần như trùng với hàng giữa (cách 4px < merge_tol 12)
    mid_y = exp_ys[1]
    lines.append(_line((560, mid_y + 4), (880, mid_y + 4), id_="dup"))
    _, ys = detect_grid(lines, roi)
    assert len(ys) == 3, "2 line gần nhau phải gom thành 1 hàng, không thành 4"


def test_build_cells_count_matches_grid():
    roi = (560, 40, 880, 160)
    lines, _, _ = _make_grid_lines(roi, rows=2, cols=3)
    xs, ys = detect_grid(lines, roi)
    cells = build_cells(xs, ys, roi)
    assert len(cells) == 6, f"thấy {len(cells)} ô, kỳ vọng 6 (2x3)"
    rows = {c.row for c in cells}
    cols = {c.col for c in cells}
    assert rows == {0, 1} and cols == {0, 1, 2}


def test_build_cells_bboxes_are_disjoint_and_inside_roi():
    roi = (560, 40, 880, 160)
    lines, _, _ = _make_grid_lines(roi, rows=2, cols=3)
    xs, ys = detect_grid(lines, roi)
    cells = build_cells(xs, ys, roi)
    # mọi ô nằm trong roi (sau khi trừ inset vẫn trong)
    for c in cells:
        x0, y0, x1, y1 = c.bbox_px
        assert roi[0] <= x0 and x1 <= roi[2]
        assert roi[1] <= y0 and y1 <= roi[3]
    # không có 2 ô cùng (row, col)
    keys = [(c.row, c.col) for c in cells]
    assert len(keys) == len(set(keys))


def test_extract_table_cells_uses_reader_per_cell():
    """Dùng stub reader trả nội dung cố định theo vị trí ô (không cần OCR thật),
    kiểm tra extract_table_cells tách đúng 6 ô và gán semantic_role."""
    roi = (560, 40, 880, 160)
    lines, _, _ = _make_grid_lines(roi, rows=2, cols=3)
    expected = [["DAI", "RONG", "CAO"], ["4200", "1900", "2100"]]

    def stub_reader(image_bgr, bbox):
        # xác định ô theo toạ độ x: 3 cột đều nhau -> chia khoảng
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        col = min(2, int((cx - roi[0]) / (roi[2] - roi[0]) * 3))
        row = 0 if cy < (roi[1] + roi[3]) / 2 else 1
        return expected[row][col]

    import numpy as np
    dummy = np.zeros((10, 10, 3), dtype=np.uint8)
    cells, raw_texts = extract_table_cells(dummy, lines, roi, cell_reader=stub_reader)

    assert len(cells) == 6
    assert len(raw_texts) == 6, f"thấy {len(raw_texts)} text, kỳ vọng 6"
    contents = {t.content for t in raw_texts}
    assert contents == {"DAI", "RONG", "CAO", "4200", "1900", "2100"}
    # số liệu phải được classify là dimension_value
    numeric = [t for t in raw_texts if t.parsed_value is not None]
    assert len(numeric) == 3
    assert all(t.semantic_role == "dimension_value" for t in numeric)
    # nhãn chữ phải được gán table_cell (vì classify trả unknown -> tier2 override)
    labels = [t for t in raw_texts if t.parsed_value is None]
    assert all(t.semantic_role == "table_cell" for t in labels)


# -------------------------------------------------------------- validator --
def test_validator_passes_on_well_formed_document():
    prim = Primitive(
        type="line", source="geometry_opencv", confidence=0.9,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=LineGeometry(Point2D(0, 0), Point2D(100, 0)),
    )
    doc = {
        "schema_version": "1.0.0",
        "source_document": {"file_name": "x.png", "page_index": 0, "image_width_px": 100, "image_height_px": 100},
        "calibration": {"unit": "mm", "pixel_to_unit_scale": 1.0, "origin_px": [0, 0], "method": "manual_override"},
        "primitives": [prim.to_dict()],
        "cross_validations": [],
    }
    errors = validate_document(doc)
    assert errors == [], f"Không mong đợi lỗi nhưng có: {errors}"


def test_validator_catches_missing_geometry():
    doc = {
        "schema_version": "1.0.0",
        "source_document": {"file_name": "x.png", "page_index": 0, "image_width_px": 100, "image_height_px": 100},
        "calibration": {"unit": "mm", "pixel_to_unit_scale": 1.0, "origin_px": [0, 0], "method": "manual_override"},
        "primitives": [{
            "id": "p1", "type": "line", "source": "geometry_opencv", "confidence": 0.9,
            "layer": "UNCLASSIFIED", "handle": None,
            "trace": {"bbox_px": [0, 0, 1, 1]}, "validation": {"status": "unreviewed"},
            # thiếu "geometry" cố ý
        }],
        "cross_validations": [],
    }
    errors = validate_document(doc)
    assert any("thiếu 'geometry'" in e for e in errors)


if __name__ == "__main__":
    # Cho phép chạy trực tiếp bằng `python3 test_basic.py` nếu máy không có pytest
    import sys
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} test PASS")
    sys.exit(1 if failed else 0)


# ---------------------------------------------------------- geometry preset --
def test_geometry_presets_kwargs_override():
    from primitive_ir_lib.geometry_extraction import PRESETS

    assert PRESETS["real_scan_tuned_v1"]["param2"] == 55
    assert PRESETS["default"]["param2"] == 30


def test_extract_raw_geometry_rejects_unknown_preset():
    import numpy as np
    from primitive_ir_lib.geometry_extraction import extract_raw_geometry

    img = np.zeros((10, 10, 3), dtype=np.uint8)
    try:
        extract_raw_geometry(img, preset="does_not_exist")
        assert False, "phải raise ValueError với preset không hợp lệ"
    except ValueError:
        pass
