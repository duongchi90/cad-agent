"""
pattern_recognition.py — Phase 2 bước đầu: suy `SemanticPart` TRỰC TIẾP từ
hình học của 1 primitive đơn lẻ (line: hướng ngang/dọc/xiên; circle: lỗ bắt
vít vs đường viền tròn khác theo bán kính).

CỐ Ý GIỚI HẠN PHẠM VI (xem semantic_ir.schema.json, định nghĩa PartType):
KHÔNG suy các linh kiện ghép nhiều primitive (bản lề, giá đỡ, mối hàn...) —
việc đó cần nhận dạng hình dạng phức hợp hoặc Vision hỗ trợ, chưa làm ở đây.
Primitive nào không rơi vào 1 trong các luật rõ ràng bên dưới thì KHÔNG tạo
SemanticPart cho nó (không ép gán bừa — đúng nguyên tắc mục 10.1 tài liệu
kiến trúc: rule-based/deterministic trước, phần mơ hồ để lại cho vòng sau).

Ngưỡng dùng ở đây (angle_tolerance_deg, bolt_hole_max_radius_mm) là GIÁ TRỊ
ĐỀ XUẤT ban đầu, CHƯA benchmark trên ảnh scan thật của domain khung xương
cải tạo ô tô (khác với ngưỡng cross_validate 3% ở Phase 1 vốn đã benchmark
ở mục 9). Nên tinh chỉnh lại sau khi chạy thử trên vài bản vẽ thật.
"""

from __future__ import annotations

from typing import List

from primitive_ir_lib.models import Primitive

from .models import GeometrySummary, PartType, SemanticPart


def _normalize_orientation(dx: float, dy: float) -> float:
    """Góc line so với trục X, chuẩn hoá về [0, 180) — line không có hướng
    (đầu/cuối hoán đổi vẫn là cùng 1 line), nên 0° và 180° coi là 1."""
    import math
    angle = math.degrees(math.atan2(dy, dx)) % 180.0
    return angle


def _classify_line_orientation(
    orientation_deg: float, angle_tolerance_deg: float,
) -> tuple[PartType, float]:
    """Trả (part_type, confidence). Xem docstring module về ý nghĩa
    angle_tolerance_deg và cách tính confidence (biên độ lệch so với ngưỡng,
    KHÔNG phải xác suất thống kê thật — chỉ để xếp hạng ưu tiên review)."""
    dist_to_horizontal = min(orientation_deg, 180.0 - orientation_deg)
    dist_to_vertical = abs(orientation_deg - 90.0)

    if dist_to_horizontal <= angle_tolerance_deg:
        confidence = max(0.5, 1.0 - (dist_to_horizontal / angle_tolerance_deg) * 0.5)
        return "thanh_ngang", confidence
    if dist_to_vertical <= angle_tolerance_deg:
        confidence = max(0.5, 1.0 - (dist_to_vertical / angle_tolerance_deg) * 0.5)
        return "thanh_doc", confidence

    # Xiên: càng gần 45° (cách đều ngang/dọc) càng chắc chắn KHÔNG phải
    # ngang/dọc bị đọc lệch, nên confidence càng cao. min(dist_h, dist_v)
    # đạt giá trị lớn nhất đúng bằng 45° (tại orientation=45°), nên chuẩn
    # hoá margin theo mẫu số (45 - angle_tolerance_deg), không phải 45/90.
    min_margin = min(dist_to_horizontal, dist_to_vertical) - angle_tolerance_deg
    max_margin = max(1e-9, 45.0 - angle_tolerance_deg)
    confidence = min(1.0, 0.5 + (min_margin / max_margin) * 0.5)
    return "thanh_xien", confidence


def build_parts_from_primitives(
    primitives: List[Primitive],
    angle_tolerance_deg: float = 10.0,
    bolt_hole_max_radius_mm: float = 15.0,
) -> List[SemanticPart]:
    """Entry point Phase 2 bước đầu. Duyệt qua từng primitive kiểu
    line/circle, áp luật hình học đơn giản, sinh SemanticPart tương ứng.

    Primitive kiểu 'text' hoặc 'arc' (chưa có luật cho arc ở bước này) bị
    BỎ QUA có chủ đích, không tạo part 'unclassified' cho mọi thứ không
    match — 'unclassified' trong enum PartType dành cho use case khác
    (đánh dấu thủ công khi cần), không phải giá trị mặc định tự động.
    """
    parts: List[SemanticPart] = []

    for prim in primitives:
        if prim.type == "line" and prim.geometry is not None:
            start, end = prim.geometry.start, prim.geometry.end
            dx, dy = end.x - start.x, end.y - start.y
            length_mm = prim.geometry.length()
            if length_mm == 0:
                continue  # line suy biến (2 điểm trùng nhau) — không phải thanh thật
            orientation_deg = _normalize_orientation(dx, dy)
            part_type, confidence = _classify_line_orientation(orientation_deg, angle_tolerance_deg)
            parts.append(SemanticPart(
                part_type=part_type,
                primitive_ids=[prim.id],
                confidence=round(confidence, 3),
                source="rule_geometry",
                geometry_summary=GeometrySummary(
                    length_mm=round(length_mm, 3),
                    orientation_deg=round(orientation_deg, 3),
                ),
            ))

        elif prim.type == "circle" and prim.geometry is not None:
            radius_mm = prim.geometry.radius
            if radius_mm <= bolt_hole_max_radius_mm:
                part_type: PartType = "lo_bat_vit"
                # Càng nhỏ so với ngưỡng càng chắc là lỗ bắt vít (không phải
                # đường viền tròn lớn bị đo nhầm bán kính).
                confidence = min(1.0, 0.6 + (1.0 - radius_mm / bolt_hole_max_radius_mm) * 0.4)
            else:
                part_type = "duong_vien_tron"
                confidence = 0.6  # ngưỡng đơn-biến (chỉ dựa bán kính) nên trần confidence thấp hơn line
            parts.append(SemanticPart(
                part_type=part_type,
                primitive_ids=[prim.id],
                confidence=round(confidence, 3),
                source="rule_geometry",
                geometry_summary=GeometrySummary(radius_mm=round(radius_mm, 3)),
            ))

        # type == "arc" hoặc "text": bỏ qua có chủ đích, xem docstring.

    return parts
