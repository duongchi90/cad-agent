"""
constraint_detection.py — Phase 2: đối chiếu TỪNG CẶP line primitive, phát
hiện 5 quan hệ hình học deterministic (parallel/perpendicular/equal_length/
coincident_endpoint/collinear), sinh `Constraint`.

Đây là phần "Detection" tách khỏi "Solving" theo đúng phân công đã chốt ở
mục 3 tài liệu kiến trúc (bảng repo `python-solvespace`): module này CHỈ đo
và ghi nhận quan hệ đã tồn tại trong bản vẽ gốc, KHÔNG solve/tính lại tọa độ
— việc solve dùng SolveSpace ở bước sau, đọc `constraints[]` sinh ra từ đây
làm input.

Độ phức tạp: O(n^2) theo số line — chấp nhận được với quy mô 1 trang bản vẽ
(vài chục đến ~200 line theo benchmark mục 9 tài liệu kiến trúc); nếu sau
này gặp bản vẽ nhiều nghìn line mới cần tối ưu (spatial index).

`detect_circle_constraints()` (thêm sau, mục 11.4 tài liệu kiến trúc — "Còn
thiếu: Constraint line-circle/circle-circle") bổ sung 2 quan hệ liên quan
tới circle: 'tangent' (line-circle) và 'concentric' (circle-circle). Tách
riêng khỏi `detect_constraints()` (chỉ line-line) thay vì gộp chung, giữ
đúng quy ước hiện có: mỗi hàm nhận list đã lọc sẵn ĐÚNG 1 type hình học,
raise rõ ràng nếu gọi sai — không tự lọc/im lặng bỏ qua primitive sai type.
"""

from __future__ import annotations

import math
from typing import List

from primitive_ir_lib.models import Primitive, Point2D

from .models import Constraint

_DEFAULT_ANGLE_TOL_DEG = 3.0
_DEFAULT_LENGTH_TOL_PERCENT = 3.0
# 5.0mm (trước là 2.0mm) — 2.0mm thấp hơn cả nhiễu Hough thật đo được trên
# demo pipeline: sau Canny+Hough+merge (Phase 1), 1 góc L vẽ khớp tuyệt đối
# theo pixel vẫn ra khoảng cách góc thực tế ~3.43mm giữa cặp line gần nhất
# (nét vẽ rộng 3px bị tách/làm tròn qua Hough). Với ngưỡng cũ, coincident_
# endpoint không bao giờ trigger được trên dữ liệu thật -> gia_do/khung_chu_nhat
# ở pattern_compound.py không bao giờ có điều kiện để ghép. 5.0mm đủ rộng để
# bao nhiễu đo được (3.43mm) nhưng vẫn từ chối rõ ràng các gap không liên
# quan (đã kiểm tra test cũ: mọi case dùng 0mm hoặc >=50mm, không có ca biên
# 2-10mm). Xem mục 11.6 tài liệu kiến trúc.
_DEFAULT_DISTANCE_TOL_MM = 5.0


def _orientation(p: Primitive) -> float:
    s, e = p.geometry.start, p.geometry.end
    return math.degrees(math.atan2(e.y - s.y, e.x - s.x)) % 180.0


def _angle_diff(a: float, b: float) -> float:
    """Khoảng cách góc ngắn nhất giữa 2 orientation đã chuẩn hoá [0,180)."""
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def _point_distance(p1: Point2D, p2: Point2D) -> float:
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def _point_to_infinite_line_distance(pt: Point2D, line_a: Point2D, line_b: Point2D) -> float:
    """Khoảng cách từ pt tới ĐƯỜNG THẲNG vô hạn qua line_a-line_b (không
    phải đoạn thẳng) — dùng cho collinear (2 đoạn có thể không chạm nhau
    nhưng nằm trên cùng 1 đường thẳng, vd 1 thanh khung bị gãy khúc do
    khung xương/cửa cắt ngang qua)."""
    ax, ay = line_b.x - line_a.x, line_b.y - line_a.y
    seg_len = math.hypot(ax, ay)
    if seg_len == 0:
        return _point_distance(pt, line_a)
    cross = ax * (pt.y - line_a.y) - ay * (pt.x - line_a.x)
    return abs(cross) / seg_len


def detect_constraints(
    lines: List[Primitive],
    angle_tolerance_deg: float = _DEFAULT_ANGLE_TOL_DEG,
    length_tolerance_percent: float = _DEFAULT_LENGTH_TOL_PERCENT,
    distance_tolerance_mm: float = _DEFAULT_DISTANCE_TOL_MM,
) -> List[Constraint]:
    """Nhận vào danh sách Primitive kiểu 'line' (đã lọc sẵn — hàm này
    KHÔNG tự lọc type để gọi rõ ràng từ nơi gọi, tránh im lặng bỏ qua
    primitive sai type). Trả về mọi Constraint tìm được giữa mọi cặp.

    1 cặp line có thể sinh NHIỀU constraint cùng lúc (vd vừa song song vừa
    bằng độ dài) — đây là hành vi có chủ đích, không loại trừ lẫn nhau.
    """
    for p in lines:
        if p.type != "line" or p.geometry is None:
            raise ValueError(
                f"detect_constraints: primitive {p.id} không phải line hợp lệ "
                f"(type={p.type!r}) — lọc trước khi gọi hàm này."
            )

    constraints: List[Constraint] = []
    n = len(lines)

    for i in range(n):
        li = lines[i]
        oi = _orientation(li)
        len_i = li.geometry.length()

        for j in range(i + 1, n):
            lj = lines[j]
            oj = _orientation(lj)
            len_j = lj.geometry.length()

            angle_diff = _angle_diff(oi, oj)

            # --- parallel ---
            if angle_diff <= angle_tolerance_deg:
                confidence = max(0.5, 1.0 - (angle_diff / angle_tolerance_deg) * 0.5) if angle_tolerance_deg > 0 else 1.0
                constraints.append(Constraint(
                    type="parallel",
                    primitive_ids=[li.id, lj.id],
                    confidence=round(confidence, 3),
                    tolerance={"angle_deg": angle_tolerance_deg},
                    measured={"angle_diff_deg": round(angle_diff, 3)},
                ))

                # --- collinear (chỉ xét khi đã song song) ---
                d1 = _point_to_infinite_line_distance(li.geometry.start, lj.geometry.start, lj.geometry.end)
                d2 = _point_to_infinite_line_distance(li.geometry.end, lj.geometry.start, lj.geometry.end)
                max_d = max(d1, d2)
                if max_d <= distance_tolerance_mm:
                    conf = max(0.5, 1.0 - (max_d / distance_tolerance_mm) * 0.5) if distance_tolerance_mm > 0 else 1.0
                    constraints.append(Constraint(
                        type="collinear",
                        primitive_ids=[li.id, lj.id],
                        confidence=round(conf, 3),
                        tolerance={"distance_mm": distance_tolerance_mm},
                        measured={"endpoint_distance_mm": round(max_d, 3)},
                    ))

            # --- perpendicular ---
            # _angle_diff() luôn trả về giá trị trong [0,90] nên chỉ cần so
            # trực tiếp với 90 - không cần nhánh else.
            perp_diff = abs(angle_diff - 90.0)
            if perp_diff <= angle_tolerance_deg:
                confidence = max(0.5, 1.0 - (perp_diff / angle_tolerance_deg) * 0.5) if angle_tolerance_deg > 0 else 1.0
                constraints.append(Constraint(
                    type="perpendicular",
                    primitive_ids=[li.id, lj.id],
                    confidence=round(confidence, 3),
                    tolerance={"angle_deg": angle_tolerance_deg},
                    measured={"angle_diff_deg": round(perp_diff, 3)},
                ))

            # --- equal_length ---
            if len_i > 0 and len_j > 0:
                length_diff_pct = abs(len_i - len_j) / max(len_i, len_j) * 100.0
                if length_diff_pct <= length_tolerance_percent:
                    confidence = max(0.5, 1.0 - (length_diff_pct / length_tolerance_percent) * 0.5) if length_tolerance_percent > 0 else 1.0
                    constraints.append(Constraint(
                        type="equal_length",
                        primitive_ids=[li.id, lj.id],
                        confidence=round(confidence, 3),
                        tolerance={"length_percent": length_tolerance_percent},
                        measured={"length_diff_percent": round(length_diff_pct, 3)},
                    ))

            # --- coincident_endpoint (4 tổ hợp start/end) ---
            endpoint_pairs = [
                (li.geometry.start, lj.geometry.start),
                (li.geometry.start, lj.geometry.end),
                (li.geometry.end, lj.geometry.start),
                (li.geometry.end, lj.geometry.end),
            ]
            best_dist = min(_point_distance(a, b) for a, b in endpoint_pairs)
            if best_dist <= distance_tolerance_mm:
                confidence = max(0.5, 1.0 - (best_dist / distance_tolerance_mm) * 0.5) if distance_tolerance_mm > 0 else 1.0
                constraints.append(Constraint(
                    type="coincident_endpoint",
                    primitive_ids=[li.id, lj.id],
                    confidence=round(confidence, 3),
                    tolerance={"distance_mm": distance_tolerance_mm},
                    measured={"endpoint_distance_mm": round(best_dist, 3)},
                ))

    return constraints


def detect_circle_constraints(
    lines: List[Primitive],
    circles: List[Primitive],
    distance_tolerance_mm: float = _DEFAULT_DISTANCE_TOL_MM,
) -> List[Constraint]:
    """Phát hiện 2 quan hệ hình học deterministic liên quan tới circle, tách
    riêng khỏi `detect_constraints()` (chỉ xét line-line) vì khác type input:

    - 'tangent' (line-circle): khoảng cách từ tâm circle tới ĐƯỜNG THẲNG vô
      hạn chứa line (dùng lại `_point_to_infinite_line_distance()`, cùng
      cách đo với 'collinear' ở trên) gần bằng đúng bán kính circle — line
      "chạm" đường tròn tại đúng 1 điểm. Dùng đường thẳng vô hạn (không
      phải đoạn) vì điểm tiếp tuyến hình học có thể rơi ngoài đoạn line đã
      merge/cắt ngắn do Hough — cùng lý do đã áp dụng cho collinear.
    - 'concentric' (circle-circle): khoảng cách giữa 2 tâm gần bằng 0 (2
      circle bán kính khác nhau nhưng cùng tâm — vd lỗ bắt vít có gờ/vòng
      đệm được vẽ 2 vòng tròn đồng tâm).

    Cùng ngưỡng `distance_tolerance_mm` mặc định (5.0mm, đồng bộ
    `_DEFAULT_DISTANCE_TOL_MM` dùng cho coincident_endpoint/collinear ở
    trên) — cùng bản chất dung sai "khoảng cách đo được giữa 2 điểm/đường
    xấp xỉ nhau", cùng bậc sai số Hough đã đo (mục 11.6 tài liệu kiến trúc).

    `lines`/`circles`: 2 list đã lọc sẵn ĐÚNG type tương ứng — cùng quy ước
    với `detect_constraints()`: gọi rõ ràng từ nơi gọi, hàm này KHÔNG tự lọc
    type để tránh im lặng bỏ qua primitive sai type.
    """
    for p in lines:
        if p.type != "line" or p.geometry is None:
            raise ValueError(
                f"detect_circle_constraints: primitive {p.id} không phải line hợp lệ "
                f"(type={p.type!r}) — lọc trước khi gọi hàm này."
            )
    for p in circles:
        if p.type != "circle" or p.geometry is None:
            raise ValueError(
                f"detect_circle_constraints: primitive {p.id} không phải circle hợp lệ "
                f"(type={p.type!r}) — lọc trước khi gọi hàm này."
            )

    constraints: List[Constraint] = []

    # --- tangent (line-circle) ---
    for line in lines:
        for circle in circles:
            dist_center_to_line = _point_to_infinite_line_distance(
                circle.geometry.center, line.geometry.start, line.geometry.end
            )
            gap = abs(dist_center_to_line - circle.geometry.radius)
            if gap <= distance_tolerance_mm:
                confidence = max(0.5, 1.0 - (gap / distance_tolerance_mm) * 0.5) if distance_tolerance_mm > 0 else 1.0
                constraints.append(Constraint(
                    type="tangent",
                    primitive_ids=[line.id, circle.id],
                    confidence=round(confidence, 3),
                    tolerance={"distance_mm": distance_tolerance_mm},
                    measured={"tangent_gap_mm": round(gap, 3)},
                ))

    # --- concentric (circle-circle) ---
    n = len(circles)
    for i in range(n):
        ci = circles[i]
        for j in range(i + 1, n):
            cj = circles[j]
            center_dist = _point_distance(ci.geometry.center, cj.geometry.center)
            if center_dist <= distance_tolerance_mm:
                confidence = max(0.5, 1.0 - (center_dist / distance_tolerance_mm) * 0.5) if distance_tolerance_mm > 0 else 1.0
                constraints.append(Constraint(
                    type="concentric",
                    primitive_ids=[ci.id, cj.id],
                    confidence=round(confidence, 3),
                    tolerance={"distance_mm": distance_tolerance_mm},
                    measured={"center_distance_mm": round(center_dist, 3)},
                ))

    return constraints
