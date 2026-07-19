"""
calibration.py — Ước lượng Calibration (pixel -> mm) từ 1 kích thước tham
chiếu đã biết trên bản vẽ (method="known_dimension_reference", xem mục 10.3
tài liệu tổng hợp v1.3: cách này đáng tin hơn suy tỷ lệ từ title block vì
không phụ thuộc ảnh có bị crop/resize khi scan hay không).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from .geometry_extraction import RawLine
from .models import Calibration
from .text_extraction import RawText


def _bbox_center(bbox) -> Tuple[float, float]:
    x0, y0, x1, y1 = bbox
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def find_nearest_line(text: RawText, lines: List[RawLine], max_distance_px: float = 150.0) -> Optional[RawLine]:
    """Tìm RawLine gần 1 RawText nhất theo khoảng cách tâm bbox — heuristic
    đơn giản cho witness-line/dimension-line. Đủ dùng khi bản vẽ không quá
    dày đặc; với bảng nhiều cột/nhiều kích thước sát nhau cần heuristic tinh
    hơn (vd so hướng line với rotation_deg của text) — để lại cho Phase 2."""
    tx, ty = _bbox_center(text.bbox_px)
    best, best_dist = None, float("inf")
    for line in lines:
        mx = (line.p1_px[0] + line.p2_px[0]) / 2.0
        my = (line.p1_px[1] + line.p2_px[1]) / 2.0
        dist = float(np.hypot(mx - tx, my - ty))
        if dist < best_dist:
            best, best_dist = line, dist
    if best is not None and best_dist <= max_distance_px:
        return best
    return None


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
) -> Optional[Calibration]:
    """Tự động: quét raw_texts tìm text đầu tiên có semantic_role
    'dimension_value', ghép với line gần nhất, dùng làm mốc calibration.
    Trả về None nếu không tìm được cặp nào phù hợp — khi đó cần
    method='manual_override' (người dùng tự nhập, xem mục 10.3)."""
    for text in raw_texts:
        if text.semantic_role != "dimension_value" or text.parsed_value is None:
            continue
        line = find_nearest_line(text, raw_lines, max_distance_px=max_distance_px)
        if line is not None:
            return estimate_calibration_from_reference(text, line, image_height_px, unit=unit)
    return None
