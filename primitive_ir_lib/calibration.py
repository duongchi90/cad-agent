"""
calibration.py — Ước lượng Calibration (pixel -> mm) từ 1 kích thước tham
chiếu đã biết trên bản vẽ (method="known_dimension_reference", xem mục 10.3
tài liệu tổng hợp v1.3: cách này đáng tin hơn suy tỷ lệ từ title block vì
không phụ thuộc ảnh có bị crop/resize khi scan hay không).
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

from .geometry_extraction import RawLine
from .models import Calibration
from .text_extraction import RawText
from .tick_mark_detection import detect_tick_mark_at_point


def _bbox_center(bbox) -> Tuple[float, float]:
    x0, y0, x1, y1 = bbox
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def _line_angle_deg(line: RawLine) -> float:
    """Góc của line (độ), chuẩn hoá về [0, 180) — line vô hướng nên 10° và
    190° là cùng 1 hướng."""
    dx = line.p2_px[0] - line.p1_px[0]
    dy = line.p2_px[1] - line.p1_px[1]
    angle = float(np.degrees(np.arctan2(dy, dx))) % 180.0
    return angle


def _angular_diff_deg(a: float, b: float) -> float:
    """Khoảng cách góc nhỏ nhất giữa 2 hướng đã chuẩn hoá [0, 180)."""
    diff = abs(a - b) % 180.0
    return min(diff, 180.0 - diff)


def _line_angle_rad(line: RawLine) -> float:
    """Giống `_line_angle_deg()` nhưng trả về radian mod pi — đúng đơn vị
    tham số `ref_angle` mà `detect_tick_mark_at_point()` (tick_mark_detection.py)
    yêu cầu."""
    dx = line.p2_px[0] - line.p1_px[0]
    dy = line.p2_px[1] - line.p1_px[1]
    return math.atan2(dy, dx) % math.pi


def _count_tick_mark_endpoints(
    line: RawLine,
    image_bgr: Optional[np.ndarray],
    window_px: float,
    proximity_px: float,
) -> int:
    """Đếm số đầu mút (0/1/2) của `line` có ký hiệu ranh giới (tick-mark
    chéo/mũi tên) sát bên, dùng `detect_tick_mark_at_point()`. Trả về 0 ngay
    nếu image_bgr=None (không có ảnh gốc) — hành vi rơi về lớp dự phòng cũ
    (chỉ so khoảng cách), không tính là lỗi."""
    if image_bgr is None:
        return 0
    ref_angle = _line_angle_rad(line)
    hits = 0
    for point in (line.p1_px, line.p2_px):
        if detect_tick_mark_at_point(
            image_bgr, point=point, ref_angle=ref_angle,
            window_px=window_px, proximity_px=proximity_px,
        ):
            hits += 1
    return hits


def find_nearest_line(
    text: RawText,
    lines: List[RawLine],
    max_distance_px: float = 150.0,
    angle_tolerance_deg: float = 20.0,
    image_bgr: Optional[np.ndarray] = None,
    tick_mark_window_px: float = 20.0,
    tick_mark_proximity_px: float = 6.0,
) -> Optional[RawLine]:
    """Tìm RawLine gần 1 RawText nhất — heuristic cho witness-line/
    dimension-line, dùng khoảng cách tâm bbox làm tín hiệu chính, có 2 lớp
    tinh chỉnh cộng thêm (không thay thế nhau, xếp chồng):

    1. Lọc theo hướng (thêm 21/07/2026, "việc nên làm tiếp" #5.3): CHỈ áp
       dụng khi `text.rotation_deg` khác 0 — tức text bị xoay chủ ý để đọc
       dọc theo 1 line (case "số kích thước xoay dọc cạnh view", mục
       9.2/tier 3). KHÔNG lọc khi `rotation_deg == 0.0` (mặc định — hầu hết
       OCR hiện tại luôn trả 0.0): text đọc ngang vẫn có thể đo 1 line DỌC,
       lọc ở case này sẽ loại nhầm line dọc đúng.

    2. Ưu tiên "chạm mũi tên" (thêm 21/07/2026, hướng sửa #2 trong
       docs/benchmarks/calibration-auto-estimate-real-image-benchmark.md
       mục 6 — CHỈ áp dụng khi có truyền `image_bgr`): trong các line còn
       lại sau lọc hướng và trong bán kính `max_distance_px`, ưu tiên line
       có nhiều đầu mút (0/1/2) chạm ký hiệu ranh giới (tick-mark chéo/mũi
       tên, dò bằng `detect_tick_mark_at_point()` — tái dùng nguyên hàm đã
       có ở `tick_mark_detection.py`, KHÔNG cần code phát hiện mũi tên mới
       như báo cáo benchmark từng ghi nhầm là "chưa có"). Chỉ dùng khoảng
       cách tâm bbox làm tie-break khi số đầu mút chạm bằng nhau. Đây đúng
       là cơ chế sửa ca thật đã benchmark: text "1970" từng bị ghép nhầm
       với line 337px bị Hough cắt cụt (không chạm mũi tên phải) thay vì
       line 428px đúng (chạm cả 2 mũi tên) — vì 2 line này CÙNG HƯỚNG NGANG
       nên lọc #1 không phân biệt được, nhưng #2 phân biệt được nhờ line
       337px chỉ chạm 1/2 đầu mút trong khi line 428px chạm 2/2.

    `image_bgr=None` (mặc định, vd chỉ có RawLine/RawText tách rời không
    kèm ảnh gốc) -> bỏ qua hoàn toàn lớp #2, giữ nguyên hành vi cũ (chỉ
    khoảng cách + lọc hướng) — không phải lỗi, là fallback cố ý, giống cách
    `detect_tick_mark_at_point(image_bgr=None)` luôn trả False.
    """
    tx, ty = _bbox_center(text.bbox_px)
    apply_angle_filter = text.rotation_deg % 180.0 != 0.0
    text_angle = text.rotation_deg % 180.0

    candidates: List[Tuple[RawLine, float]] = []
    for line in lines:
        if apply_angle_filter:
            if _angular_diff_deg(_line_angle_deg(line), text_angle) > angle_tolerance_deg:
                continue
        mx = (line.p1_px[0] + line.p2_px[0]) / 2.0
        my = (line.p1_px[1] + line.p2_px[1]) / 2.0
        dist = float(np.hypot(mx - tx, my - ty))
        if dist <= max_distance_px:
            candidates.append((line, dist))

    if not candidates:
        return None

    if image_bgr is None:
        best_line, _ = min(candidates, key=lambda item: item[1])
        return best_line

    def _sort_key(item: Tuple[RawLine, float]) -> Tuple[int, float]:
        line, dist = item
        hits = _count_tick_mark_endpoints(
            line, image_bgr, window_px=tick_mark_window_px, proximity_px=tick_mark_proximity_px,
        )
        return (-hits, dist)  # nhiều đầu mút chạm hơn trước, rồi mới tới khoảng cách gần hơn

    best_line, _ = min(candidates, key=_sort_key)
    return best_line


def estimate_calibration_from_reference(
    reference_text: RawText,
    reference_line: RawLine,
    image_height_px: int,
    unit: str = "mm",
    origin_px: Optional[Tuple[float, float]] = None,
) -> Calibration:
    """Dùng 1 cặp (text kích thước đã đọc, line đo được bằng pixel) làm mốc.
    origin_px mặc định = góc dưới-trái ảnh (0, image_height_px), tức quy ước
    y hướng lên như CAD — có thể override nếu bản vẽ có gốc khác rõ ràng
    (vd đường tâm/mép chuẩn ghi trên title block)."""
    if reference_text.parsed_value is None:
        raise ValueError("reference_text phải có parsed_value (đã classify là dimension_value)")

    pixel_length = reference_line.length_px()
    if pixel_length <= 0:
        raise ValueError("reference_line có độ dài pixel bằng 0, không thể dùng làm mốc")

    scale = reference_text.parsed_value / pixel_length
    origin = origin_px if origin_px is not None else (0.0, float(image_height_px))

    return Calibration(
        unit=unit,
        pixel_to_unit_scale=round(scale, 6),
        origin_px=origin,
        method="known_dimension_reference",
        reference_note=(
            f"Dùng kích thước '{reference_text.content}' "
            f"({reference_text.parsed_value} {unit}) đối chiếu với line "
            f"{reference_line.id} đo được {pixel_length:.1f}px "
            f"-> scale={scale:.4f} {unit}/px."
        ),
    )


def _median(values: List[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def auto_estimate_calibration(
    raw_texts: List[RawText],
    raw_lines: List[RawLine],
    image_height_px: int,
    unit: str = "mm",
    max_distance_px: float = 150.0,
    angle_tolerance_deg: float = 20.0,
    image_bgr: Optional[np.ndarray] = None,
    require_consensus: bool = False,
    consensus_tolerance_pct: float = 10.0,
    min_consensus_candidates: int = 2,
) -> Optional[Calibration]:
    """Tự động ước lượng calibration từ các text `dimension_value` ghép với
    line gần nhất (`find_nearest_line` — lọc theo hướng khi
    `text.rotation_deg != 0` (#1), VÀ ưu tiên line chạm mũi tên khi có
    truyền `image_bgr` (#2); xem docstring `find_nearest_line`).

    `require_consensus=False` (MẶC ĐỊNH, đổi lại sau khi tự phát hiện lỗi):
    tắt cơ chế #3, giữ nguyên hành vi CŨ — dùng ngay ứng viên ĐẦU TIÊN theo
    thứ tự `raw_texts`, không kiểm tra đồng thuận. Lý do mặc định là
    `False` (không phải `True` như khuyến nghị ban đầu ở mục 6 báo cáo
    benchmark): khi tự thử bật `require_consensus=True` mặc định, chạy lại
    `python3 -m primitive_ir_lib.demo_pipeline` bị crash ngay
    (`RuntimeError: Không tự động ước lượng được calibration`) vì 3
    `dimension_value` trong fixture demo cho 3 scale KHÔNG đồng thuận —
    lộ ra rằng bật mặc định sẽ phá vỡ mọi call site hiện có
    (`demo_pipeline.py`, `run_image.py`, `verify_full.py`) mà chưa ai cập
    nhật để xử lý `None`. Giữ nhất quán với cách #1/#2 đã làm (opt-in, mặc
    định giữ hành vi cũ) — set `require_consensus=True` TƯỜNG MINH khi
    muốn bật lớp an toàn này (khuyến khích cho code mới/production, xem
    test `test_calibration.py`).

    Khi `require_consensus=True`, hàm thu thập MỌI cặp (text, line) hợp lệ
    thay vì dừng ở cặp đầu tiên:

    - Nếu tìm được `>= min_consensus_candidates` ứng viên: tính scale
      trung vị (median) của tất cả, coi các ứng viên có độ lệch tương đối
      so với trung vị `<= consensus_tolerance_pct` (%) là "đồng thuận". Nếu
      số ứng viên đồng thuận cũng `>= min_consensus_candidates`, trả về
      Calibration dựng từ ứng viên đồng thuận GẦN trung vị nhất (đại diện
      ổn định nhất), kèm ghi chú số ứng viên đã đồng thuận/tổng số. Nếu
      KHÔNG đủ ứng viên đồng thuận (lệch nhau quá nhiều, như ca thật
      "1970" từng benchmark — 60%) -> **từ chối, trả về `None`** thay vì
      đoán liều — đúng khuyến nghị #3 trong báo cáo benchmark ("coi là dấu
      hiệu không đáng tin và từ chối trả kết quả").
    - Nếu chỉ tìm được 1 ứng viên (không đủ để so đồng thuận): trả về ứng
      viên đó như cũ (không có cách nào kiểm tra đồng thuận với 1 điểm dữ
      liệu), nhưng `reference_note` ghi rõ "chỉ 1 ứng viên, CHƯA xác minh
      đồng thuận" — để `needs_verification` (calibration_registry.py) và
      người review biết mà không tự tin dùng ngay.
    - Nếu không tìm được ứng viên nào: trả về `None` như cũ.

    LƯU Ý TRUNG THỰC: cơ chế đồng thuận này mới kiểm bằng test tổng hợp
    (`test_calibration.py`), CHƯA chạy lại trên đúng ảnh thật
    "TP-GC-A018/07/26" để xem trong 7 `dimension_value` tìm được ở ca đó,
    có bao nhiêu ứng viên thực sự đồng thuận sau khi thêm #3 — vẫn cần
    benchmark thật để đóng vòng lặp (xem mục 9/11 báo cáo benchmark).
    Không dùng kết quả hàm này cho DXF sản xuất mà không xác minh — xem
    `calibration_registry.py` (`needs_verification`).
    """
    candidates: List[Tuple[RawText, RawLine, float]] = []
    for text in raw_texts:
        if text.semantic_role != "dimension_value" or text.parsed_value is None:
            continue
        line = find_nearest_line(
            text, raw_lines, max_distance_px=max_distance_px,
            angle_tolerance_deg=angle_tolerance_deg, image_bgr=image_bgr,
        )
        if line is None:
            continue
        pixel_length = line.length_px()
        if pixel_length <= 0:
            continue
        scale = text.parsed_value / pixel_length
        candidates.append((text, line, scale))
        if not require_consensus:
            break  # hành vi cũ: dùng ngay ứng viên đầu tiên, không thu thập thêm

    if not candidates:
        return None

    if not require_consensus or len(candidates) < min_consensus_candidates:
        text, line, _scale = candidates[0]
        cal = estimate_calibration_from_reference(text, line, image_height_px, unit=unit)
        if require_consensus and len(candidates) < min_consensus_candidates:
            cal.reference_note = (
                (cal.reference_note or "")
                + f" [Chỉ tìm được {len(candidates)} ứng viên dimension_value hợp lệ"
                f" (cần >= {min_consensus_candidates} để kiểm tra đồng thuận) —"
                " CHƯA xác minh đồng thuận, dùng thận trọng.]"
            )
        return cal

    scales = [c[2] for c in candidates]
    median_scale = _median(scales)
    agreeing = [
        c for c in candidates
        if median_scale != 0 and abs(c[2] - median_scale) / abs(median_scale) * 100.0 <= consensus_tolerance_pct
    ]

    if len(agreeing) < min_consensus_candidates:
        return None  # không đủ đồng thuận -> từ chối, không đoán liều

    best_text, best_line, best_scale = min(
        agreeing, key=lambda c: abs(c[2] - median_scale)
    )
    cal = estimate_calibration_from_reference(best_text, best_line, image_height_px, unit=unit)
    cal.reference_note = (
        (cal.reference_note or "")
        + f" [Đồng thuận: {len(agreeing)}/{len(candidates)} ứng viên dimension_value"
        f" khớp scale trong dung sai {consensus_tolerance_pct:.0f}%"
        f" (median={median_scale:.4f} {unit}/px).]"
    )
    return cal
