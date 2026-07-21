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


def auto_estimate_calibration(
    raw_texts: List[RawText],
    raw_lines: List[RawLine],
    image_height_px: int,
    unit: str = "mm",
    max_distance_px: float = 150.0,
    angle_tolerance_deg: float = 20.0,
    image_bgr: Optional[np.ndarray] = None,
) -> Optional[Calibration]:
    """Tự động: quét raw_texts tìm text đầu tiên có semantic_role
    'dimension_value', ghép với line gần nhất (`find_nearest_line` — lọc
    theo hướng khi text.rotation_deg != 0, VÀ ưu tiên line chạm mũi tên khi
    có truyền `image_bgr`; xem docstring `find_nearest_line`), dùng làm mốc
    calibration. Trả về None nếu không tìm được cặp nào phù hợp — khi đó
    cần method='manual_override' (người dùng tự nhập, xem mục 10.3).

    `image_bgr`: ảnh gốc (BGR, cùng ảnh đã dùng cho `extract_raw_geometry`/
    `extract_text_tesseract`) — TUỲ CHỌN, truyền vào để bật hướng sửa #2
    (ưu tiên line chạm 2 đầu mũi tên, xem
    docs/benchmarks/calibration-auto-estimate-real-image-benchmark.md mục
    6 và 8). Không truyền (mặc định None) -> giữ nguyên hành vi cũ, chỉ so
    khoảng cách + lọc hướng.

    LƯU Ý (xem docs/benchmarks/calibration-auto-estimate-real-image-benchmark.md):
    hàm vẫn dừng ngay ở TEXT ĐẦU TIÊN tìm được line hợp lệ, chưa kiểm tra
    đồng thuận scale giữa nhiều dimension_value khác nhau (hướng sửa #3,
    vẫn CHƯA implement). Ưu tiên chạm-mũi-tên (#2) chỉ giúp chọn đúng line
    trong số các line GẦN text; nó không thay thế việc đối chiếu đa điểm.
    Không dùng kết quả hàm này cho DXF sản xuất mà không xác minh — xem
    `calibration_registry.py` (`needs_verification`).
    """
    for text in raw_texts:
        if text.semantic_role != "dimension_value" or text.parsed_value is None:
            continue
        line = find_nearest_line(
            text, raw_lines, max_distance_px=max_distance_px,
            angle_tolerance_deg=angle_tolerance_deg, image_bgr=image_bgr,
        )
        if line is not None:
            return estimate_calibration_from_reference(text, line, image_height_px, unit=unit)
    return None
