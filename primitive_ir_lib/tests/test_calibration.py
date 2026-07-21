"""
test_calibration.py — Test cho lọc theo hướng (angle filtering) trong
find_nearest_line(), thêm 21/07/2026 ("việc nên làm tiếp" #5.3 trong
HANDOFF.md). Test cơ bản khác (scale, pixel_to_cad flip, max_distance) đã
có sẵn trong test_basic.py — file này CHỈ tập trung vào hành vi lọc hướng
mới thêm, không lặp lại.
"""

from __future__ import annotations

import cv2
import numpy as np

from primitive_ir_lib.calibration import auto_estimate_calibration, find_nearest_line
from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.text_extraction import RawText, classify_semantic_role


def _line(p1, p2, id_="l1", confidence=0.9):
    return RawLine(id=id_, p1_px=p1, p2_px=p2, confidence=confidence,
                    bbox_px=(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])))


def _text(content, bbox, rotation_deg=0.0, id_="t1"):
    role, value = classify_semantic_role(content)
    return RawText(id=id_, content=content, bbox_px=bbox, rotation_deg=rotation_deg,
                    confidence=0.95, source="text_vision", parsed_value=value, semantic_role=role)


# --------------------------------------------- rotation_deg == 0.0 (mặc định) --
def test_unrotated_text_still_matches_vertical_line():
    """Text đọc ngang (rotation_deg=0, mặc định — case phổ biến nhất) vẫn
    phải ghép được với 1 line DỌC: chữ số kích thước thường giữ ngang để dễ
    đọc dù đo cạnh dọc. KHÔNG được lọc theo hướng ở case này (nếu lọc sẽ
    loại nhầm line dọc đúng, giống test_find_nearest_line_respects_max_distance
    trong test_basic.py)."""
    vertical = _line((100, 280), (100, 320), id_="vertical")
    text = _text("1700", (95, 290, 110, 310), rotation_deg=0.0)
    found = find_nearest_line(text, [vertical])
    assert found is not None and found.id == "vertical"


def test_unrotated_text_ignores_angle_when_two_candidates_different_orientation():
    """rotation_deg=0: line ngang gần hơn 1 chút vẫn được chọn đúng theo
    khoảng cách thuần — không có gì để lọc (baseline, xác nhận không đổi
    hành vi cũ khi rotation_deg=0)."""
    horizontal = _line((80, 300), (120, 300), id_="closer_horizontal")
    vertical = _line((100, 260), (100, 340), id_="farther_vertical")
    text = _text("1700", (95, 295, 105, 305), rotation_deg=0.0)
    found = find_nearest_line(text, [horizontal, vertical], max_distance_px=200)
    assert found is not None and found.id == "closer_horizontal"


# ------------------------------------------------- rotation_deg != 0 (text xoay) --
def test_rotated_text_prefers_aligned_line_over_closer_misaligned_line():
    """Case cốt lõi (case tier 3 'số kích thước xoay dọc', mục 9.2): text bị
    xoay 90 độ để đọc dọc theo 1 line dọc. Có 1 line NGANG ở gần tâm text
    hơn (nhiễu — vd 1 nét hatch/border tình cờ đi qua gần đó) và 1 line DỌC
    xa tâm text hơn nhưng đúng hướng đọc của text. Phải chọn line DỌC (đúng
    hướng) — đây chính xác cơ chế lẽ ra tránh được lỗi thật đã benchmark ở
    docs/benchmarks/calibration-auto-estimate-real-image-benchmark.md CHO
    CASE text bị xoay (không áp dụng cho ca "1970" đã benchmark, vì ca đó
    rotation_deg=0)."""
    text_center = (300, 300)
    misleading_horizontal = _line((280, 302), (320, 302), id_="misleading_horizontal")  # rất gần tâm text
    correct_vertical = _line((300, 200), (300, 400), id_="correct_vertical")  # xa tâm text hơn, đúng hướng
    text = _text("1700", (295, 295, 305, 305), rotation_deg=90.0)
    assert text.bbox_px == (295, 295, 305, 305)
    found = find_nearest_line(text, [misleading_horizontal, correct_vertical], max_distance_px=200)
    assert found is not None and found.id == "correct_vertical"


def test_rotated_text_rejects_all_when_no_line_matches_orientation():
    """Text xoay 90 độ, nhưng CHỈ có line ngang trong danh sách (không có
    line nào cùng hướng) — phải trả về None thay vì miễn cưỡng chọn 1 line
    sai hướng. An toàn hơn so với hành vi trước khi thêm lọc hướng (trước
    đây sẽ trả về line ngang này, dù sai hướng, chỉ vì nó gần nhất)."""
    horizontal_only = _line((280, 302), (320, 302), id_="horizontal_only")
    text = _text("1700", (295, 295, 305, 305), rotation_deg=90.0)
    found = find_nearest_line(text, [horizontal_only], max_distance_px=200)
    assert found is None


def test_rotated_text_angle_tolerance_is_configurable():
    """Line lệch 30 độ so với hướng text xoay 90 độ (tức góc line = 60 độ):
    bị loại với dung sai mặc định (20 độ) nhưng được chấp nhận nếu nới dung
    sai lên 40 độ."""
    dx, dy = 20 * 0.5, 20  # xấp xỉ 1 line ở góc 60 độ so với trục ngang (tan(60)=~1.73, dùng toạ độ đơn giản)
    import math
    length = 40.0
    angle_rad = math.radians(60.0)
    p1 = (300.0, 300.0)
    p2 = (300.0 + length * math.cos(angle_rad), 300.0 + length * math.sin(angle_rad))
    skewed_line = _line(p1, p2, id_="skewed_60deg")
    text = _text("1700", (295, 295, 305, 305), rotation_deg=90.0)

    rejected = find_nearest_line(text, [skewed_line], max_distance_px=200, angle_tolerance_deg=20.0)
    assert rejected is None

    accepted = find_nearest_line(text, [skewed_line], max_distance_px=200, angle_tolerance_deg=40.0)
    assert accepted is not None and accepted.id == "skewed_60deg"


def test_rotation_180_degrees_treated_same_as_0():
    """rotation_deg=180.0 về mặt đọc-hình-học tương đương 0.0 (text vẫn đọc
    ngang, chỉ lộn ngược) — không lọc theo hướng, giống case rotation_deg=0."""
    vertical = _line((100, 280), (100, 320), id_="vertical")
    text = _text("1700", (95, 290, 110, 310), rotation_deg=180.0)
    found = find_nearest_line(text, [vertical])
    assert found is not None and found.id == "vertical"


# --------------------------------------- hướng sửa #2: ưu tiên chạm mũi tên --
# Tái hiện ĐÚNG ca lỗi thật đã benchmark
# (docs/benchmarks/calibration-auto-estimate-real-image-benchmark.md, mục 3):
# text "1970" có 2 line ứng viên CÙNG HƯỚNG NGANG (lọc #1 không phân biệt
# được) — 1 line bị Hough cắt cụt (gần tâm text hơn, KHÔNG chạm mũi tên ở
# đầu bị cắt) và 1 line đầy đủ (xa tâm text hơn, chạm cả 2 mũi tên). Ở đây
# dùng ảnh tổng hợp (vẽ tick-mark chéo ~45° bằng cv2, cùng kỹ thuật với
# test_tick_mark_detection.py) thay cho ảnh scan thật, vì ảnh gốc không
# commit (dữ liệu khách hàng).

def _blank_canvas(w=700, h=200):
    return np.full((h, w, 3), 255, dtype=np.uint8)


def _draw_arrow_tick(img, cx, cy, size=8):
    """Vẽ 1 nét chéo ~45° ngay tại (cx, cy) — mô phỏng ký hiệu mũi tên/
    tick-mark ở đầu mút witness-line/dimension-line."""
    cv2.line(img, (int(cx - size), int(cy + size)), (int(cx + size), int(cy - size)), (0, 0, 0), 2)


def _setup_1970_style_case():
    """2 line cùng hướng ngang, chung đầu trái (300,100) — mô phỏng đúng tỷ
    lệ ca thật: line SAI ngắn hơn + gần tâm text hơn, line ĐÚNG dài hơn + xa
    tâm text hơn nhưng chạm cả 2 mũi tên."""
    wrong_cut_short = _line((300, 100), (480, 100), id_="wrong_cut_short")   # center (390,100), dist=10
    correct_full = _line((300, 100), (560, 100), id_="correct_full")        # center (430,100), dist=30
    text = _text("1970", (395, 90, 405, 110), rotation_deg=0.0)
    return wrong_cut_short, correct_full, text


def test_prefers_line_touching_both_arrowheads_over_closer_cut_short_line():
    wrong_cut_short, correct_full, text = _setup_1970_style_case()
    img = _blank_canvas()
    _draw_arrow_tick(img, 300, 100)  # đầu trái — chung cho cả 2 line
    _draw_arrow_tick(img, 560, 100)  # đầu phải — CHỈ line đúng chạm tới
    # (480,100), đầu phải của line sai, CỐ Ý không vẽ gì — mô phỏng bị cắt cụt

    found = find_nearest_line(
        text, [wrong_cut_short, correct_full], max_distance_px=200, image_bgr=img,
    )
    assert found is not None and found.id == "correct_full"


def test_without_image_bgr_reproduces_old_bug_falls_back_to_distance():
    """Không truyền image_bgr (mặc định None) -> giữ nguyên hành vi cũ, vẫn
    chọn nhầm line gần tâm text hơn — đúng bug đã benchmark trước khi có
    hướng sửa #2. Xác nhận #2 chỉ kích hoạt khi CÓ ảnh gốc, không tự nhiên
    "sửa hộ" khi thiếu dữ liệu."""
    wrong_cut_short, correct_full, text = _setup_1970_style_case()
    found = find_nearest_line(text, [wrong_cut_short, correct_full], max_distance_px=200)
    assert found is not None and found.id == "wrong_cut_short"


def test_no_arrow_marks_anywhere_falls_back_to_distance_even_with_image():
    """Có truyền image_bgr nhưng ảnh trắng trơn, không có ký hiệu nào (vd
    ảnh scan mờ/nhiễu không dò được nét chéo) -> cả 2 line đều 0 đầu mút
    chạm -> tie-break về khoảng cách, giống hệt khi image_bgr=None. Xác nhận
    detect_tick_mark_at_point trả False êm thấm, không crash, không thiên vị."""
    wrong_cut_short, correct_full, text = _setup_1970_style_case()
    blank = _blank_canvas()
    found = find_nearest_line(
        text, [wrong_cut_short, correct_full], max_distance_px=200, image_bgr=blank,
    )
    assert found is not None and found.id == "wrong_cut_short"


def test_tie_break_by_distance_when_both_lines_touch_same_number_of_arrows():
    """Cả 2 line đều chạm đủ 2 đầu mũi tên (không có line nào bị cắt cụt) —
    hướng #2 không phân biệt được (hits bằng nhau cả 2), phải tie-break về
    khoảng cách như hành vi gốc, chọn line GẦN tâm text hơn."""
    closer = _line((300, 100), (500, 100), id_="closer")     # center (400,100), dist=0
    farther = _line((350, 100), (550, 100), id_="farther")   # center (450,100), dist=50
    text = _text("1970", (395, 90, 405, 110), rotation_deg=0.0)
    img = _blank_canvas()
    for x, y in ((300, 100), (500, 100), (350, 100), (550, 100)):
        _draw_arrow_tick(img, x, y)

    found = find_nearest_line(text, [closer, farther], max_distance_px=200, image_bgr=img)
    assert found is not None and found.id == "closer"


# --------------------------------- hướng sửa #3: đồng thuận đa ứng viên --
# (docs/benchmarks/calibration-auto-estimate-real-image-benchmark.md, mục 6
# khuyến nghị #3 và mục 11 cập nhật): thay vì tin ngay ứng viên
# dimension_value ĐẦU TIÊN tìm được line, auto_estimate_calibration() giờ
# thu thập MỌI ứng viên, so scale suy ra giữa chúng, chỉ trả kết quả khi đủ
# ứng viên đồng thuận (trong dung sai `consensus_tolerance_pct`).

def _pair(value: str, cx: float, line_length: float, id_: str):
    """Tạo 1 cặp (RawText dimension_value, RawLine) đặt gần nhau (dist=10px)
    quanh toạ độ x=cx, sao cho scale suy ra = parsed_value / line_length."""
    text = _text(value, (cx - 5, 45, cx + 5, 55), id_=f"t-{id_}")
    line = _line((cx - line_length / 2, 60), (cx + line_length / 2, 60), id_=f"l-{id_}")
    return text, line


def test_auto_estimate_consensus_uses_majority_and_ignores_outlier():
    """3 ứng viên: 2 cái cho scale=2.0 mm/px (đồng thuận), 1 cái ("3000",
    line rất ngắn) cho scale=30.0 mm/px (outlier, lệch xa median) — phải
    chọn scale từ 2 ứng viên đồng thuận, bỏ qua outlier."""
    text1, line1 = _pair("1000", 300, 500, "a")     # scale = 1000/500 = 2.0
    text2, line2 = _pair("2000", 2300, 1000, "b")   # scale = 2000/1000 = 2.0
    text3, line3 = _pair("3000", 4300, 100, "c")    # scale = 3000/100 = 30.0 (outlier)

    cal = auto_estimate_calibration(
        [text1, text2, text3], [line1, line2, line3], image_height_px=200,
        require_consensus=True,
    )
    assert cal is not None
    assert abs(cal.pixel_to_unit_scale - 2.0) < 1e-6
    assert "Đồng thuận: 2/3" in (cal.reference_note or "")


def test_auto_estimate_rejects_when_only_two_candidates_disagree():
    """Chỉ 2 ứng viên, lệch nhau quá xa (2.0 vs 30.0 mm/px, không ai nằm
    trong dung sai 10% so với trung vị) -> không đủ đồng thuận -> từ chối
    (`None`) thay vì đoán liều theo ứng viên đầu tiên — đúng ca thật đã
    benchmark (lệch 60%)."""
    text1, line1 = _pair("1000", 300, 500, "a")   # scale = 2.0
    text2, line2 = _pair("3000", 2300, 100, "b")  # scale = 30.0

    cal = auto_estimate_calibration(
        [text1, text2], [line1, line2], image_height_px=200, require_consensus=True,
    )
    assert cal is None


def test_auto_estimate_single_candidate_returns_with_unverified_note():
    """Chỉ 1 ứng viên hợp lệ trong toàn ảnh -> không đủ dữ liệu để kiểm tra
    đồng thuận -> vẫn trả về (không có lựa chọn nào khác) nhưng ghi rõ CHƯA
    xác minh đồng thuận trong reference_note, để needs_verification/reviewer
    biết mà thận trọng."""
    text1, line1 = _pair("1000", 300, 500, "a")
    cal = auto_estimate_calibration(
        [text1], [line1], image_height_px=200, require_consensus=True,
    )
    assert cal is not None
    assert abs(cal.pixel_to_unit_scale - 2.0) < 1e-6
    assert "CHƯA xác minh đồng thuận" in (cal.reference_note or "")


def test_auto_estimate_default_keeps_old_first_wins_behavior_backward_compat():
    """MẶC ĐỊNH (không truyền `require_consensus`) phải giữ nguyên hành vi
    CŨ — dùng ngay ứng viên đầu tiên, bất kể đồng thuận — để không phá vỡ
    các call site hiện có (`demo_pipeline.py`, `run_image.py`,
    `verify_full.py`) chưa được cập nhật để xử lý `None`. Xem lý do đổi
    default trong docstring `auto_estimate_calibration` (tự phát hiện demo
    pipeline crash khi thử bật `require_consensus=True` mặc định)."""
    text_outlier, line_outlier = _pair("3000", 4300, 100, "c")  # scale = 30.0, đứng đầu
    text1, line1 = _pair("1000", 300, 500, "a")
    text2, line2 = _pair("2000", 2300, 1000, "b")

    cal = auto_estimate_calibration(
        [text_outlier, text1, text2], [line_outlier, line1, line2], image_height_px=200,
    )
    assert cal is not None
    assert abs(cal.pixel_to_unit_scale - 30.0) < 1e-6


def test_auto_estimate_require_consensus_false_keeps_old_first_wins_behavior():
    """require_consensus=False -> tắt hẳn #3, quay lại hành vi CŨ: dùng
    ngay ứng viên ĐẦU TIÊN theo thứ tự raw_texts, bất kể có đồng thuận hay
    không. Cố ý đặt outlier ("3000", scale=30.0) làm phần tử ĐẦU trong danh
    sách để phân biệt rõ với hành vi consensus (vốn sẽ bỏ qua outlier này)."""
    text_outlier, line_outlier = _pair("3000", 4300, 100, "c")  # scale = 30.0, đứng đầu danh sách
    text1, line1 = _pair("1000", 300, 500, "a")                  # scale = 2.0
    text2, line2 = _pair("2000", 2300, 1000, "b")                # scale = 2.0

    cal = auto_estimate_calibration(
        [text_outlier, text1, text2], [line_outlier, line1, line2],
        image_height_px=200, require_consensus=False,
    )
    assert cal is not None
    assert abs(cal.pixel_to_unit_scale - 30.0) < 1e-6
