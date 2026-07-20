"""
test_tick_mark_detection.py — Test detect_tick_mark_at_point() bằng ảnh tổng
hợp vẽ trực tiếp bằng cv2 (không cần ảnh scan thật):

  - Có 1 nét chéo ~45° sát điểm mút -> phải báo True (mô phỏng tick-mark).
  - Không có nét chéo nào gần điểm mút (chỉ có đường nền ngang) -> False.
  - Nét chéo nằm quá xa điểm mút (ngoài proximity_px) -> False, tránh bắt
    nhầm hatch chéo ở xa không liên quan tới witness-line đang xét.
  - image_bgr=None -> luôn False (rơi về lớp dự phòng text-anchor).

Bổ sung 19/07/2026 — test cho split_raw_line_at_internal_witness_lines() /
find_internal_boundary_offsets() (witness-line VUÔNG GÓC, khác tick-mark
chéo ở trên). Các fixture dưới đây mô phỏng LẠI ĐÚNG 2 lỗi phát hiện khi
benchmark trên ảnh thật "TP-TL-A001/07/26" (xem docstring
_perpendicular_witness_at_point trong tick_mark_detection.py):
  1. witness-line thật có "standoff gap" (không chạm dim-line ngay pixel
     đầu) -> vẫn phải detect được (test_...standoff_gap).
  2. text/ghi chú nằm trong cửa sổ probe nhưng KHÔNG liên tục từ dim-line
     -> KHÔNG được coi là witness-line (test_...does_not_confuse_nearby_text).
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from primitive_ir_lib.tick_mark_detection import (
    detect_tick_mark_at_point,
    find_internal_boundary_offsets,
    split_raw_line_at_internal_witness_lines,
)
from primitive_ir_lib.geometry_extraction import RawLine


def _blank_canvas(w=200, h=200):
    return np.full((h, w, 3), 255, dtype=np.uint8)


def _line(p1, p2, id_="l"):
    return RawLine(
        id=id_, p1_px=p1, p2_px=p2, confidence=0.9,
        bbox_px=(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])),
    )


def test_detects_diagonal_tick_mark_near_endpoint():
    img = _blank_canvas()
    # witness-line chính: ngang, kết thúc tại (100, 100)
    cv2.line(img, (20, 100), (100, 100), (0, 0, 0), 2)
    # tick-mark: nét chéo ~45 độ ngay tại đầu mút (100,100)
    cv2.line(img, (92, 108), (108, 92), (0, 0, 0), 2)

    found = detect_tick_mark_at_point(img, point=(100.0, 100.0), ref_angle=0.0)
    assert found is True


def test_no_tick_mark_plain_endpoint():
    img = _blank_canvas()
    # chỉ có witness-line ngang, không có ký hiệu gì ở đầu mút
    cv2.line(img, (20, 100), (100, 100), (0, 0, 0), 2)

    found = detect_tick_mark_at_point(img, point=(100.0, 100.0), ref_angle=0.0)
    assert found is False


def test_ignores_diagonal_far_from_endpoint():
    img = _blank_canvas()
    cv2.line(img, (20, 100), (100, 100), (0, 0, 0), 2)
    # nét chéo có thật, nhưng ở góc khác của ảnh, không liên quan tới điểm mút (100,100)
    cv2.line(img, (10, 10), (30, 30), (0, 0, 0), 2)

    found = detect_tick_mark_at_point(
        img, point=(100.0, 100.0), ref_angle=0.0, window_px=15.0,
    )
    assert found is False


def test_none_image_returns_false():
    found = detect_tick_mark_at_point(None, point=(100.0, 100.0), ref_angle=0.0)
    assert found is False


# ------------------------------------------------------------- split_raw_line_at_internal_witness_lines --

def _canvas_with_internal_witness_line(boundary_x=300, y=200, stem_len_px=16):
    """Ảnh tổng hợp: 1 dim-line NGANG liên tục (Hough sẽ fuse thành 1 line
    duy nhất, không có pixel gap nào) + 1 witness-line DỌC cắt ngang ở giữa,
    CHẠM TRỰC TIẾP vào dim-line — mô phỏng đúng kiểu ranh giới thật quan sát
    được trên "TP-TL-A001/07/26" (x=776, giữa "2760" và "1525"): witness-line
    ở đó liên tục từ xa cho tới đúng dim-line, KHÔNG có standoff gap."""
    img = np.full((400, 600, 3), 255, dtype=np.uint8)
    cv2.line(img, (50, y), (550, y), (0, 0, 0), 2)  # dim-line ngang liên tục
    cv2.line(img, (boundary_x, y - stem_len_px), (boundary_x, y - 1), (0, 0, 0), 1)
    return img


def test_finds_internal_boundary_touching_dim_line():
    # witness-line thật, chạm trực tiếp dim-line (đúng như x=776 trên ảnh thật)
    img = _canvas_with_internal_witness_line(boundary_x=300, y=200, stem_len_px=16)
    line = _line((50, 200), (550, 200), "fused")
    offsets = find_internal_boundary_offsets(img, line)
    assert len(offsets) == 1
    found_x = 50 + offsets[0]
    assert abs(found_x - 300) <= 2, f"Ranh giới tìm thấy lệch quá xa: x={found_x}"


def test_split_raw_line_at_internal_witness_lines_splits_at_boundary():
    img = _canvas_with_internal_witness_line(boundary_x=300, y=200, stem_len_px=16)
    line = _line((50, 200), (550, 200), "fused")
    parts = split_raw_line_at_internal_witness_lines(line, img)
    assert len(parts) == 2, f"Phải tách thành 2 đoạn tại ranh giới, ra: {len(parts)}"
    boundary_candidates = [p.p2_px[0] for p in parts[:-1]]
    assert any(abs(bx - 300) <= 2 for bx in boundary_candidates)


def test_perpendicular_witness_tolerates_small_standoff_gap():
    # Unit test mức thấp, dựng mảng gray thủ công (không qua cv2.line) để
    # kiểm soát chính xác từng pixel: witness-line có standoff 3px (không
    # chạm dim-line) nhưng vẫn trong leading_gap_max_px=5 mặc định -> vẫn
    # phải detect được (tham số leading_gap_max_px tồn tại đúng cho ca này,
    # dù ca thật benchmark được (x=776) không cần tới nó).
    from primitive_ir_lib.tick_mark_detection import _perpendicular_witness_at_point

    gray = np.full((60, 60), 255, dtype=np.uint8)
    dim_y = 40
    gray[dim_y, :] = 0  # dim-line ngang mỏng 1px, KHÔNG có độ dày lấn vào hàng kề
    # witness-line dọc tại x=30, từ y=20 đến y=36 (standoff 3px: y=37,38,39 trắng)
    gray[20:37, 30] = 0

    found = _perpendicular_witness_at_point(gray, 30.0, float(dim_y), 0.0)
    assert found is True


def test_does_not_confuse_nearby_scattered_text_with_witness_line():
    # Mô phỏng false-positive phát hiện trên ảnh thật (x=673): có "text/hatch"
    # nằm RỜI RẠC trong cửa sổ probe nhưng KHÔNG liên tục từ dim-line (có
    # khoảng hở lớn ở giữa) -> KHÔNG được coi là witness-line.
    img = np.full((400, 600, 3), 255, dtype=np.uint8)
    y = 200
    cv2.line(img, (50, y), (550, y), (0, 0, 0), 2)
    # "text" rời rạc, xa dim-line (không liên tục từ dim-line, có hở ~10px)
    cv2.putText(img, "1525", (280, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

    line = _line((50, 200), (550, 200), "fused")
    offsets = find_internal_boundary_offsets(img, line)
    assert offsets == [], f"Không được nhận nhầm text rời rạc thành witness-line, ra offsets={offsets}"

    parts = split_raw_line_at_internal_witness_lines(line, img)
    assert len(parts) == 1, "Không có ranh giới thật -> không được tách"


def test_split_returns_original_line_when_no_internal_boundary():
    # dim-line liên tục, không có witness-line nào cắt ngang ở giữa
    img = np.full((300, 500, 3), 255, dtype=np.uint8)
    cv2.line(img, (50, 150), (450, 150), (0, 0, 0), 2)
    line = _line((50, 150), (450, 150), "solo")
    parts = split_raw_line_at_internal_witness_lines(line, img)
    assert len(parts) == 1
    assert parts[0] is line


def test_split_returns_original_line_when_image_bgr_is_none():
    line = _line((50, 150), (450, 150), "solo")
    parts = split_raw_line_at_internal_witness_lines(line, None)
    assert len(parts) == 1
    assert parts[0] is line


def test_split_ignores_boundary_too_close_to_endpoint():
    # witness-line cắt ngang NẰM SÁT đầu mút thật của line (trong
    # endpoint_margin_px) -- không phải "ranh giới nội bộ" cần split, để lại
    # cho gap_blocked_by_tick_mark() ở line_merging.py xử lý khi có pixel gap.
    img = _canvas_with_internal_witness_line(boundary_x=52, y=200, stem_len_px=16)
    line = _line((50, 200), (550, 200), "fused")
    offsets = find_internal_boundary_offsets(img, line, endpoint_margin_px=8.0)
    assert offsets == []


def test_detects_tick_mark_on_vertical_line():
    img = _blank_canvas()
    # witness-line dọc, kết thúc tại (100, 100)
    cv2.line(img, (100, 20), (100, 100), (0, 0, 0), 2)
    # tick-mark chéo tại đầu mút
    cv2.line(img, (92, 92), (108, 108), (0, 0, 0), 2)

    ref_angle = math.pi / 2  # đường dọc
    found = detect_tick_mark_at_point(img, point=(100.0, 100.0), ref_angle=ref_angle)
    assert found is True


# --------------------------------------------------------------------------
# Regression 19/07/2026: _perpendicular_witness_at_point (dùng bởi
# find_internal_boundary_offsets / split_raw_line_at_internal_witness_lines)
# KHÔNG được nhận nhầm tick-mark CHÉO ~45° (tín hiệu của Lớp 1,
# detect_tick_mark_at_point) thành witness-line VUÔNG GÓC — xem
# test_tick_mark_blocks_merge_even_without_any_blocking_text trong
# test_line_merging.py cho ca tích hợp đầy đủ qua merge_collinear_lines().
# Các test dưới đây kiểm tra trực tiếp ở tầng thấp hơn (tick_mark_detection).
# --------------------------------------------------------------------------

def test_perpendicular_witness_false_positive_diagonal_tick_mark_near_endpoint():
    """False positive: dựng gray thủ công có 1 nét CHÉO 45° (không phải
    vuông góc) đi qua rất gần điểm đang quét, đủ để tạo 1 chuỗi pixel tối
    liên tục theo tiêu chí cũ (không lọc góc) — _perpendicular_witness_at_point
    phải trả về False vì nét chéo trôi dạt offset theo chiều dọc, không phải
    1 witness-line vuông góc đứng yên 1 chỗ."""
    from primitive_ir_lib.tick_mark_detection import _perpendicular_witness_at_point

    gray = np.full((60, 80), 255, dtype=np.uint8)
    dim_y = 40
    gray[dim_y, :] = 0  # dim-line ngang mỏng 1px

    # nét chéo 45°: từ (30,48) tới (46,32) — đi ngang qua vùng ngay dưới
    # điểm quét (30,40) mà không phải là 1 witness-line dọc thật.
    for i in range(17):
        x = 30 + i
        y = 48 - i
        gray[y, x] = 0
        if x + 1 < gray.shape[1]:
            gray[y, x + 1] = 0  # nét dày ~2px để giống cv2.line(thickness=2)

    found = _perpendicular_witness_at_point(gray, 30.0, float(dim_y), 0.0)
    assert found is False, "Không được nhận nhầm nét chéo 45° thành witness-line vuông góc"


def test_perpendicular_witness_true_positive_genuine_vertical_stays_on_axis():
    """True positive (đối chứng trực tiếp với test false-positive ở trên):
    cùng kích thước cửa sổ, nhưng witness-line THẬT (dọc, giữ nguyên cột)
    vẫn phải được detect — xác nhận việc lọc trôi dạt không làm mất tín hiệu
    thật, chỉ loại tín hiệu chéo."""
    from primitive_ir_lib.tick_mark_detection import _perpendicular_witness_at_point

    gray = np.full((60, 80), 255, dtype=np.uint8)
    dim_y = 40
    gray[dim_y, :] = 0
    gray[24:37, 30] = 0  # witness-line dọc thật, đứng yên tại x=30

    found = _perpendicular_witness_at_point(gray, 30.0, float(dim_y), 0.0)
    assert found is True


# --------------------------------------------------------------------------
# Regression 20/07/2026: benchmark mở rộng trên "TP-TL-A001/07/26" bằng
# RawLine trích xuất THẬT qua Hough (không phải toạ độ tự dựng) phát hiện
# min_run_px=8 (mặc định cũ) vẫn lọt sai ở witness-line "1700" (dọc, 1 đoạn)
# và "5500" (ngang, 1 đoạn) — 1 nét hatch CHÉO THOẢI (không phải 45° dốc như
# 2 test false-positive phía trên) đi gần dim-line, trong cửa sổ quét hẹp,
# tình cờ giữ offset trôi dạt CHẬM đủ lâu (~9 hàng) để vượt qua min_run_px=8
# cũ trước khi trôi ra khỏi max_offset_drift_px=2. Nét 45° dốc (2 test trên)
# trôi dạt NHANH nên đã bị chặn từ trước ở cả 2 ngưỡng — đây là ca khác, dốc
# thoải hơn, cần min_run_px cao hơn mới chặn được. Xem docstring
# _perpendicular_witness_at_point mục "SỬA THÊM 20/07/2026" để biết chi tiết
# gốc rễ + số liệu benchmark trên ảnh thật.
# --------------------------------------------------------------------------

def _shallow_diagonal_hatch_near_vertical_line_gray():
    """Dựng gray 100x100 mô phỏng lại đúng cơ chế lỗi Case A/C 20/07/2026:
    dim-line dọc liên tục (x=50) + 1 nét hatch chéo THOẢI (trôi dạt offset
    0,0,1,1,1,2,2,2,2 qua 9 hàng liên tiếp k=1..9, rồi mất tín hiệu) đi gần
    line tại y=40. Đây KHÔNG phải witness-line vuông góc thật (offset không
    đứng yên 1 chỗ) nhưng đủ chậm để fool ngưỡng min_run_px=8 cũ."""
    gray = np.full((100, 100), 255, dtype=np.uint8)
    gray[10:90, 50] = 0  # dim-line dọc kiểu "1700", liên tục 1 đoạn
    py_anchor = 40
    drift_offsets = [0, 0, 1, 1, 1, 2, 2, 2, 2]  # k=1..9
    for k, off in enumerate(drift_offsets, start=1):
        gray[py_anchor + off, 50 - k] = 0
    return gray


def test_perpendicular_witness_regression_shallow_diagonal_drift_needs_min_run_px_12():
    """Đơn vị: với ngưỡng cũ min_run_px=8, hatch chéo thoải (9 hàng liên tục
    trong ngưỡng trôi dạt) bị báo nhầm True. Với min_run_px=12 (mặc định mới
    từ 20/07/2026), cùng dữ liệu bị loại đúng -> False."""
    from primitive_ir_lib.tick_mark_detection import _perpendicular_witness_at_point

    gray = _shallow_diagonal_hatch_near_vertical_line_gray()
    angle = math.pi / 2  # line dọc

    found_old_threshold = _perpendicular_witness_at_point(
        gray, 50.0, 40.0, angle, min_run_px=8)
    assert found_old_threshold is True, (
        "Fixture phải tái hiện đúng lỗi cũ (min_run_px=8 báo nhầm True) — "
        "nếu assert này fail, fixture không còn mô phỏng đúng bug gốc nữa."
    )

    found_new_default = _perpendicular_witness_at_point(
        gray, 50.0, 40.0, angle, min_run_px=12)
    assert found_new_default is False, (
        "min_run_px=12 phải loại được hatch chéo thoải này (fix 20/07/2026)"
    )


def test_find_internal_boundary_offsets_default_rejects_shallow_diagonal_hatch():
    """Tích hợp: find_internal_boundary_offsets() với mặc định HIỆN TẠI
    (min_run_px=12) không được tách nhầm dim-line dọc 1 đoạn (kiểu "1700")
    chỉ vì có hatch chéo thoải gần đó. Đồng thời xác nhận rõ ràng: nếu ai đó
    lỡ hạ min_run_px về 8 (giá trị cũ trước 20/07/2026), lỗi sẽ quay lại —
    ghi thẳng vào test để hồi quy tương lai không âm thầm hạ ngưỡng này."""
    gray = _shallow_diagonal_hatch_near_vertical_line_gray()
    line = _line((50.0, 10.0), (50.0, 90.0), "1700-style")

    offsets_default = find_internal_boundary_offsets(gray, line)
    assert offsets_default == [], (
        f"Mặc định hiện tại (min_run_px=12) phải giữ nguyên 1 đoạn, ra "
        f"offsets={offsets_default}"
    )

    offsets_old_threshold = find_internal_boundary_offsets(gray, line, min_run_px=8)
    assert offsets_old_threshold != [], (
        "Ngưỡng cũ min_run_px=8 phải còn tái hiện được lỗi gốc trên chính "
        "fixture này — nếu assert này fail, fixture đã bị đổi và không còn "
        "chứng minh được vì sao cần fix 20/07/2026 nữa."
    )

    parts = split_raw_line_at_internal_witness_lines(line, gray)
    assert len(parts) == 1, "Không có witness-line vuông góc thật -> không được tách"


def test_find_internal_boundary_offsets_ignores_diagonal_tick_marks_near_interior():
    """False positive ở mức find_internal_boundary_offsets(): 1 line ngang
    liền mạch có 2 tick-mark CHÉO 45° (kiểu Lớp 1) nằm gần 2 đầu mút thật
    nhưng vẫn trong vùng quét nội bộ (ngoài endpoint_margin_px) — không được
    coi là ranh giới nội bộ cần tách, vì đó không phải witness-line vuông
    góc. Đây là fixture tương tự
    test_tick_mark_blocks_merge_even_without_any_blocking_text nhưng chỉ
    test riêng hàm tầng thấp, không qua merge_collinear_lines()."""
    img = np.full((220, 500, 3), 255, dtype=np.uint8)
    y = 140
    cv2.line(img, (0, y), (450, y), (0, 0, 0), 2)  # 1 line liền mạch, không gap
    # 2 tick-mark chéo 45° gần 2 đầu mút (bên trong phạm vi quét nội bộ)
    cv2.line(img, (18, y + 8), (34, y - 8), (0, 0, 0), 2)
    cv2.line(img, (416, y + 8), (432, y - 8), (0, 0, 0), 2)

    line = _line((0, y), (450, y), "solo")
    offsets = find_internal_boundary_offsets(img, line, endpoint_margin_px=8.0)
    assert offsets == [], f"Không được tách nhầm tại tick-mark chéo, ra offsets={offsets}"

    parts = split_raw_line_at_internal_witness_lines(line, img, endpoint_margin_px=8.0)
    assert len(parts) == 1, "Không có witness-line vuông góc thật -> không được tách"
