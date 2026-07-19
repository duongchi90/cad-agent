"""
cross_validation.py — Thực thi nguyên tắc đã chốt ở mục 7 của tài liệu tổng
hợp: "dùng Vision để lấy giá trị, dùng OpenCV để xác nhận vị trí/độ dài —
hai nguồn đối chiếu chéo, không nguồn nào quyết một mình".

Hàm cross_validate() không tự động sửa dữ liệu khi 2 nguồn lệch nhau — nó chỉ
gắn status='conflict' và để nguyên cả 2 giá trị, đẩy quyết định cho Reviewer
(đúng thiết kế mục 2: Reviewer #1/#2, không phải cross_validate, là nơi ra
quyết định cuối).

FIX (theo mục 5/6 báo cáo kiểm thử Phase 1, 18/07/2026): trước khi tìm
witness-line gần nhất, mặc định gộp các RawLine thẳng hàng bị gãy khúc bằng
merge_collinear_lines() (line_merging.py). Việc chặn gộp nhầm qua ranh giới
thật giữa 2 kích thước liền kề trong 1 chuỗi dimension dùng 2 lớp tín hiệu,
ưu tiên giảm dần: (1) tick-mark/arrowhead dò trực tiếp trên ảnh gốc — cần
truyền image_bgr vào cross_validate(); (2) neo vị trí RawText
(dimension_value) — luôn hoạt động, dùng làm dự phòng khi không có image_bgr
hoặc không dò được nét chéo. Có thể tắt cả 2 bằng merge_collinear=False để
giữ hành vi cũ (dùng raw_lines nguyên trạng) nếu cần so sánh/rollback.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from .calibration import find_nearest_line
from .geometry_extraction import RawLine
from .line_merging import merge_collinear_lines
from .models import Calibration, CrossValidation
from .text_extraction import RawText


def cross_validate(
    raw_texts: List[RawText],
    raw_lines: List[RawLine],
    calibration: Calibration,
    threshold_percent: float = 3.0,
    max_distance_px: float = 150.0,
    merge_collinear: bool = True,
    merge_gap_tol_px: float = 25.0,
    image_bgr: Optional[np.ndarray] = None,
) -> List[CrossValidation]:
    """Với mỗi RawText có semantic_role == 'dimension_value':
      1. (mặc định) gộp collinear-line có neo bằng tick-mark (nếu có
         image_bgr) và/hoặc vị trí các RawText dimension_value, nối lại
         witness-line bị gãy khúc kỹ thuật mà KHÔNG nối nhầm qua ranh giới
         thật giữa 2 kích thước liền kề.
      2. tìm RawLine (đã gộp) gần nhất (witness-line/dimension-line ứng viên)
      3. quy đổi độ dài pixel của line đó sang đơn vị CAD bằng calibration
      4. so sánh với parsed_value của text -> status confirmed/conflict/unverified

    image_bgr: ảnh gốc (BGR) để bật tick-mark detection (Lớp 1, ưu tiên hơn
    text-anchor). None -> chỉ dùng text-anchor (Lớp 2), giữ tương thích ngược.

    LƯU Ý: nếu raw_lines rỗng hoặc không tìm được line phù hợp trong
    max_distance_px, trả về status='unverified' — KHÔNG suy đoán, để trống
    cho bước sau (Reviewer hoặc con người) xử lý.
    """
    results: List[CrossValidation] = []

    if merge_collinear:
        dimension_texts = [t for t in raw_texts if t.semantic_role == "dimension_value"]
        raw_lines = merge_collinear_lines(
            raw_lines, blocking_texts=dimension_texts, image_bgr=image_bgr,
            gap_tol_px=merge_gap_tol_px,
        )

    for text in raw_texts:
        if text.semantic_role != "dimension_value" or text.parsed_value is None:
            continue

        line = find_nearest_line(text, raw_lines, max_distance_px=max_distance_px)

        if line is None:
            results.append(CrossValidation(
                text_primitive_id=text.id,
                geometry_primitive_id="",
                status="unverified",
                text_value=text.parsed_value,
                match_threshold_percent=threshold_percent,
            ))
            continue

        measured = line.length_px() * calibration.pixel_to_unit_scale
        delta_percent = abs(text.parsed_value - measured) / text.parsed_value * 100.0
        status = "confirmed" if delta_percent <= threshold_percent else "conflict"

        results.append(CrossValidation(
            text_primitive_id=text.id,
            geometry_primitive_id=line.id,
            status=status,
            text_value=text.parsed_value,
            geometry_measured_length=round(measured, 3),
            delta_percent=round(delta_percent, 4),
            match_threshold_percent=threshold_percent,
        ))

    return results
