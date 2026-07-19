"""
line_merging.py — Gộp các đoạn RawLine thẳng hàng (collinear) bị gãy khúc do
centerline/ký hiệu cắt ngang witness-line, KHÔNG gộp qua ranh giới thật giữa
2 kích thước liền kề trong 1 chuỗi dimension (dimension chain).

BỐI CẢNH: xem mục 5.3 báo cáo kiểm thử Phase 1 (18/07/2026). Heuristic gộp
collinear thuần hình học (chỉ dựa vào gap-distance) không phân biệt được 2
loại khoảng trống:
  - gãy khúc kỹ thuật (centerline cắt ngang witness-line)      -> NÊN gộp
  - ranh giới thật giữa 2 đoạn dimension liền kề trong 1 chuỗi -> KHÔNG gộp
vì khoảng trống quan sát được (~22px) của cả 2 trường hợp trùng lên nhau —
không có ngưỡng gap_tol_px đơn lẻ nào tách được cả hai (đã thử quét
10/15/18/20/25px, không đổi).

FIX — 2 LỚP TÍN HIỆU ĐỘC LẬP VỚI GAP-DISTANCE (xem "Phương án tổng thể",
sau báo cáo 18/07/2026), xếp theo thứ tự ưu tiên:

  Lớp 1 (chính, mới thêm): tick-mark/arrowhead detection
    (tick_mark_detection.py:detect_tick_mark_at_point) — dò ký hiệu ranh
    giới CHÉO ~45°/mũi tên ngay tại ảnh gốc, quanh 2 đầu mút của khoảng
    TRỐNG giữa 2 segment (use_tick_mark_detection, tick_mark_window_px,
    tick_mark_proximity_px bên dưới). Đây là tín hiệu đúng bản chất CAD
    nhất vì KHÔNG phụ thuộc OCR đọc đúng/định vị đúng text — chỉ cần truyền
    image_bgr vào merge_collinear_lines(). Nếu không truyền image_bgr (hoặc
    không dò được nét chéo nào), lớp này coi như "không kết luận được" và
    nhường cho Lớp 2, KHÔNG tự suy ra là "không có ranh giới".

  Lớp 2 (dự phòng, giữ nguyên từ bản trước): text-anchor blocking — dùng vị
    trí các RawText đã đọc được (semantic_role = dimension_value) làm "neo".
    Nếu khoảng trống giữa 2 đoạn line nằm đè lên (hoặc rất gần) bbox của 1
    RawText nào đó, khoảng trống đó được coi là ranh giới thật.

  Quy tắc kết hợp: BẤT KỲ lớp nào báo "có ranh giới" -> KHÔNG gộp (OR logic,
  đúng nguyên tắc "không nguồn nào quyết một mình, thà không gộp nhầm còn
  hơn" của cross_validation.py). Cả 2 lớp đều không báo -> gộp theo
  gap_tol_px như cũ.

BƯỚC TIỀN XỬ LÝ RIÊNG — split_internal_witness_lines (thêm 19/07/2026,
KHÔNG phải Lớp 1/2 ở trên): trên ảnh thật, Hough thường tự "fuse" một
dim-chain nhiều đoạn (vd "2760"+"1525" chung 1 dim-line) thành 1 RawLine
LIÊN TỤC không hề có khoảng trống pixel nào ở ranh giới — khi đó Lớp 1/2 ở
trên (chỉ kiểm tra khoảng TRỐNG giữa 2 segment) không bao giờ được gọi tới.
Trước khi gộp, merge_collinear_lines() gọi
tick_mark_detection.py:split_raw_line_at_internal_witness_lines() cho từng
RawLine đầu vào để tách các line bị fuse kiểu này tại witness-line VUÔNG GÓC
nằm giữa line (khác hẳn tick-mark CHÉO 45° của Lớp 1). Xem tham số
split_internal_witness_lines bên dưới.

  QUY ƯỚC ĐẶT TÊN (để tránh nhầm lẫn 2 khái niệm, xem hồi quy bên dưới):
  "tick_mark" LUÔN chỉ tín hiệu CHÉO ~45°/mũi tên của Lớp 1
  (detect_tick_mark_at_point, use_tick_mark_detection, tick_mark_window_px,
  tick_mark_proximity_px) — dùng cho khoảng TRỐNG giữa 2 segment.
  "witness_line" LUÔN chỉ tín hiệu VUÔNG GÓC của bước tiền xử lý
  (split_internal_witness_lines,
  split_raw_line_at_internal_witness_lines) — dùng để tách 1 RawLine liền
  mạch tại ranh giới NẰM GIỮA line, trước khi union-find/gộp.

  HỒI QUY ĐÃ SỬA (19/07/2026,
  test_tick_mark_blocks_merge_even_without_any_blocking_text): cờ này lúc
  đầu tên là `split_internal_tick_marks` — dùng chung chữ "tick_marks" cho
  cả 2 khái niệm ở trên dù thuật toán bên trong
  (_perpendicular_witness_at_point) không hề lọc theo góc, chỉ hỏi "có pixel
  tối trong cửa sổ quét hay không". Khi 1 tick-mark chéo 45° của Lớp 1 nằm
  sát đầu mút BÊN TRONG phạm vi quét nội bộ của 1 line (như trong fixture
  test), nó cũng tạo ra 1 chuỗi pixel tối liên tục hợp lệ theo tiêu chí cũ,
  khiến line bị tách nhầm thành 4 đoạn thay vì gộp đúng 2 theo ranh giới
  thật. Đã sửa 2 việc: (1) `_perpendicular_witness_at_point` giờ theo dõi vị
  trí cột (offset) của từng hàng tối và NGẮT chuỗi nếu offset trôi dạt quá
  `max_offset_drift_px` — đúng đặc trưng hình học phân biệt 1 nét chéo (trôi
  dạt ~1px/hàng) với 1 nét vuông góc thật (offset gần như cố định); (2) đổi
  tên cờ/hàm liên quan cho khớp đúng phạm vi ("witness_line" thay vì
  "tick_marks" chung chung) để tránh lặp lại nhầm lẫn tương tự sau này.

LƯU Ý QUAN TRỌNG (trung thực về giới hạn):
  - Tick-mark detection (Lớp 1) mới tự-test bằng fixture tổng hợp vẽ bằng
    cv2 (tests/test_tick_mark_detection.py, tests/test_line_merging.py),
    CHƯA benchmark trên ảnh scan thật — xem thêm giới hạn chi tiết trong
    docstring của tick_mark_detection.py (rủi ro dương tính giả từ hatch
    chéo dày đặc).
  - Text-anchor (Lớp 2) cũng mới chỉ tự-test bằng fixture tổng hợp.
  - split_internal_witness_lines (bước tiền xử lý) đã benchmark trên 1 điểm
    ranh giới thật (x=776, "2760"/"1525" của "TP-TL-A001/07/26") cho hàm
    split_raw_line_at_internal_witness_lines() đơn lẻ — nhưng CHƯA chạy lại
    toàn bộ merge_collinear_lines() (kèm blocking_texts thật, cross_validate,
    v.v.) trên ảnh đó để xác nhận pipeline đầu-cuối; mới xác nhận hết hồi quy
    trên fixture tổng hợp.
  - Cả 2 lớp CHƯA chạy lại trên đúng ảnh "TP-TL-A001/07/26" đã gây lỗi trong
    báo cáo gốc qua merge_collinear_lines() đầy đủ. Cần xác nhận trên ảnh
    thật trước khi xem đây là fix đã chốt.
  - Vision API tier 3 (xác nhận thủ công khi cả 2 tín hiệu trên đều mơ hồ) và
    việc phân biệt mũi tên thật (2 nét chéo đối xứng) với 1 nét hatch chéo
    tình cờ VẪN CHƯA triển khai — để lại cho vòng sau.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

import numpy as np

from .geometry_extraction import RawLine
from .models import new_id
from .tick_mark_detection import detect_tick_mark_at_point, split_raw_line_at_internal_witness_lines

try:  # RawText chỉ cần cho type hint / truy cập bbox_px, tránh phụ thuộc vòng
    from .text_extraction import RawText
except ImportError:  # pragma: no cover
    RawText = object  # type: ignore


def _angle_mod_pi(dx: float, dy: float) -> float:
    """Góc của đường thẳng, chuẩn hoá về [0, pi) vì đường thẳng không có hướng."""
    a = math.atan2(dy, dx) % math.pi
    return a


def _angle_diff_mod_pi(a: float, b: float) -> float:
    d = abs(a - b) % math.pi
    return min(d, math.pi - d)


def _perp_distance_point_to_line(px: float, py: float, x0: float, y0: float, angle: float) -> float:
    """Khoảng cách vuông góc từ điểm (px,py) tới đường thẳng đi qua (x0,y0) với góc `angle`."""
    dx, dy = math.cos(angle), math.sin(angle)
    vx, vy = px - x0, py - y0
    # thành phần vuông góc = |v x d| (tích chéo 2D)
    return abs(vx * dy - vy * dx)


def _project_point(px: float, py: float, x0: float, y0: float, angle: float) -> float:
    """Toạ độ 1 chiều của điểm khi chiếu lên đường thẳng (theo hướng `angle`)."""
    dx, dy = math.cos(angle), math.sin(angle)
    return (px - x0) * dx + (py - y0) * dy


def _bbox_center(bbox) -> Tuple[float, float]:
    x0, y0, x1, y1 = bbox
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def _line_angle_and_ref(line: RawLine) -> Tuple[float, float, float]:
    x1, y1 = line.p1_px
    x2, y2 = line.p2_px
    angle = _angle_mod_pi(x2 - x1, y2 - y1)
    return angle, x1, y1


def merge_collinear_lines(
    raw_lines: Sequence[RawLine],
    blocking_texts: Optional[Sequence["RawText"]] = None,
    image_bgr: Optional[np.ndarray] = None,
    angle_tol_deg: float = 3.0,
    perp_tol_px: float = 6.0,
    gap_tol_px: float = 25.0,
    text_block_lateral_px: float = 15.0,
    text_block_padding_px: float = 4.0,
    use_tick_mark_detection: bool = True,
    tick_mark_window_px: float = 20.0,
    tick_mark_proximity_px: float = 6.0,
    split_internal_witness_lines: bool = True,
) -> List[RawLine]:
    """Gộp các RawLine thẳng hàng, gần nhau thành 1 line liền mạch — trừ khi
    khoảng trống giữa chúng bị "chặn" bởi Lớp 1 (tick-mark/arrowhead dò trực
    tiếp trên ảnh gốc) hoặc Lớp 2 (neo vị trí RawText). Xem docstring đầu
    file để biết thứ tự ưu tiên và lý do kết hợp bằng OR.

    Tham số:
      image_bgr               — ảnh gốc (BGR, như cv2.imread trả về) để dò
                                tick-mark (Lớp 1). None -> bỏ qua Lớp 1, chỉ
                                dùng Lớp 2 (text-anchor), giữ tương thích
                                ngược với bản trước không có ảnh.
      use_tick_mark_detection — tắt hẳn Lớp 1 dù có truyền image_bgr (vd để
                                so sánh/rollback riêng lớp này).
      tick_mark_window_px,
      tick_mark_proximity_px  — chuyển tiếp cho detect_tick_mark_at_point().
      split_internal_witness_lines — TRƯỚC khi gộp, cắt các RawLine dài bị
                                Hough tự fuse liền (không hề có khoảng trống
                                pixel) tại các witness-line VUÔNG GÓC NẰM
                                GIỮA line — hiện tượng phát hiện khi benchmark
                                trên ảnh thật "TP-TL-A001/07/26" (19/07/2026):
                                dim-chain nhiều đoạn (vd "2760"+"1525" chung 1
                                dim-line) thường bị Hough fuse thành 1
                                RawLine LIÊN TỤC, khiến Lớp 1/2 phía dưới
                                (vốn chỉ kiểm tra KHOẢNG TRỐNG giữa 2 segment)
                                không bao giờ được gọi tới ở ranh giới đó.
                                Cần image_bgr; bỏ qua (giữ nguyên raw_lines)
                                nếu image_bgr=None. LƯU Ý ĐẶT TÊN: cờ này CHỈ
                                bắt witness-line vuông góc, KHÔNG bắt tick-mark
                                chéo 45° (đó là use_tick_mark_detection ở
                                trên, cho khoảng TRỐNG giữa 2 segment) — tên
                                cũ (`split_internal_tick_marks`, trước
                                19/07/2026) dùng chung chữ "tick_marks" cho cả
                                2 khái niệm khác nhau và là nguồn gây hồi quy
                                test_tick_mark_blocks_merge_even_without_any_blocking_text
                                (line bị tách nhầm tại chính tick-mark chéo
                                của Lớp 1 khi nó nằm sát đầu mút bên trong
                                line) — đã đổi tên cho khớp đúng phạm vi, xem
                                tick_mark_detection.py:
                                split_raw_line_at_internal_witness_lines() và
                                docstring _perpendicular_witness_at_point.
      angle_tol_deg          — 2 line được coi là cùng phương nếu lệch góc <= tol.
      perp_tol_px            — 2 line cùng phương chỉ được gộp nếu nằm trên cùng
                                1 đường thẳng (khoảng cách vuông góc <= tol).
      gap_tol_px              — khoảng trống dọc theo trục line tối đa để vẫn gộp
                                (nếu không bị chặn bởi Lớp 1 hoặc Lớp 2).
      text_block_lateral_px  — bề rộng "hành lang" quanh line dùng để coi 1 text
                                là "nằm trên/sát line đó" (khoảng cách vuông góc
                                từ tâm bbox text tới line).
      text_block_padding_px  — nới rộng khoảng trống thêm bao nhiêu px về 2 phía
                                khi kiểm tra xem text có rơi vào khoảng trống đó
                                không (bảo thủ: thà không gộp nhầm còn hơn).

    Trả về danh sách RawLine mới (line đã gộp + line không đổi). Line đã gộp có
    id mới (tiền tố 'rawline-merged'), confidence = max của các line thành phần.
    """
    if split_internal_witness_lines and image_bgr is not None:
        split_lines: List[RawLine] = []
        for line in raw_lines:
            split_lines.extend(split_raw_line_at_internal_witness_lines(line, image_bgr))
        raw_lines = split_lines

    n = len(raw_lines)
    if n == 0:
        return []

    blocking_texts = blocking_texts or []
    angle_tol = math.radians(angle_tol_deg)

    # --- 1. Gom cụm các line cùng phương, cùng 1 đường thẳng (union-find) ---
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    angles = []
    for line in raw_lines:
        angle, x0, y0 = _line_angle_and_ref(line)
        angles.append((angle, x0, y0))

    for i in range(n):
        ai, x0i, y0i = angles[i]
        for j in range(i + 1, n):
            aj, x0j, y0j = angles[j]
            if _angle_diff_mod_pi(ai, aj) > angle_tol:
                continue
            # dùng góc trung bình đơn giản (đủ dùng vì đã lọc theo angle_tol)
            perp = _perp_distance_point_to_line(x0j, y0j, x0i, y0i, ai)
            if perp <= perp_tol_px:
                union(i, j)

    clusters: dict = {}
    for idx in range(n):
        clusters.setdefault(find(idx), []).append(idx)

    result: List[RawLine] = []

    for _, idxs in clusters.items():
        if len(idxs) == 1:
            result.append(raw_lines[idxs[0]])
            continue

        cluster_lines = [raw_lines[i] for i in idxs]
        ref_angle, ref_x0, ref_y0 = angles[idxs[0]]

        # chiếu 2 đầu mút mỗi line lên trục chung -> khoảng [t_min, t_max],
        # đồng thời giữ lại toạ độ pixel thật của điểm ứng với t_min/t_max
        # (cần cho tick-mark detection, vốn dò trên ảnh gốc chứ không phải
        # trên trục chiếu trừu tượng).
        segs = []
        for line in cluster_lines:
            p1, p2 = line.p1_px, line.p2_px
            t1 = _project_point(p1[0], p1[1], ref_x0, ref_y0, ref_angle)
            t2 = _project_point(p2[0], p2[1], ref_x0, ref_y0, ref_angle)
            if t1 <= t2:
                t_min, t_max, p_at_min, p_at_max = t1, t2, p1, p2
            else:
                t_min, t_max, p_at_min, p_at_max = t2, t1, p2, p1
            segs.append((t_min, t_max, line, p_at_min, p_at_max))
        segs.sort(key=lambda s: s[0])

        # tính trước danh sách text "sát trục" (trong hành lang perp_tol lateral)
        # cùng toạ độ chiếu tâm bbox của chúng lên trục này
        nearby_text_t: List[float] = []
        for text in blocking_texts:
            tcx, tcy = _bbox_center(text.bbox_px)
            perp = _perp_distance_point_to_line(tcx, tcy, ref_x0, ref_y0, ref_angle)
            if perp <= text_block_lateral_px:
                nearby_text_t.append(_project_point(tcx, tcy, ref_x0, ref_y0, ref_angle))

        def gap_blocked_by_text(gap_start: float, gap_end: float) -> bool:
            lo, hi = gap_start - text_block_padding_px, gap_end + text_block_padding_px
            return any(lo <= t <= hi for t in nearby_text_t)

        def gap_blocked_by_tick_mark(p_before_gap, p_after_gap) -> bool:
            # Lớp 1 (chính): kiểm tra ký hiệu ranh giới ở CẢ 2 đầu mút quanh
            # khoảng trống — chỉ cần 1 trong 2 đầu có tick-mark là đủ để coi
            # khoảng trống đó là ranh giới thật (bảo thủ theo đúng nguyên tắc
            # "thà không gộp nhầm còn hơn").
            if image_bgr is None or not use_tick_mark_detection:
                return False
            return (
                detect_tick_mark_at_point(
                    image_bgr, p_before_gap, ref_angle,
                    window_px=tick_mark_window_px, proximity_px=tick_mark_proximity_px,
                )
                or detect_tick_mark_at_point(
                    image_bgr, p_after_gap, ref_angle,
                    window_px=tick_mark_window_px, proximity_px=tick_mark_proximity_px,
                )
            )

        # gộp tuần tự các segment liền kề (đã sort theo t_min)
        merged_groups: List[List[Tuple[float, float, RawLine, Tuple[float, float], Tuple[float, float]]]] = [[segs[0]]]
        for seg in segs[1:]:
            group = merged_groups[-1]
            _, cur_max, _, _, cur_p_at_max = group[-1]
            seg_min, _, _, seg_p_at_min, _ = seg[0], seg[1], seg[2], seg[3], seg[4]
            gap = seg_min - cur_max
            blocked = gap > gap_tol_px or (
                gap_blocked_by_tick_mark(cur_p_at_max, seg_p_at_min)
                or gap_blocked_by_text(cur_max, seg_min)
            )
            if not blocked:
                group.append(seg)
            else:
                merged_groups.append([seg])

        for group in merged_groups:
            if len(group) == 1:
                result.append(group[0][2])
                continue
            t_min = min(s[0] for s in group)
            t_max = max(s[1] for s in group)
            dx, dy = math.cos(ref_angle), math.sin(ref_angle)
            p1 = (ref_x0 + dx * t_min, ref_y0 + dy * t_min)
            p2 = (ref_x0 + dx * t_max, ref_y0 + dy * t_max)
            confidence = max(s[2].confidence for s in group)
            bbox = (
                min(p1[0], p2[0]), min(p1[1], p2[1]),
                max(p1[0], p2[0]), max(p1[1], p2[1]),
            )
            result.append(RawLine(
                id=new_id("rawline-merged"),
                p1_px=p1,
                p2_px=p2,
                confidence=confidence,
                bbox_px=bbox,
            ))

    return result
