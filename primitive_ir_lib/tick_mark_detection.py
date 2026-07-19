"""
tick_mark_detection.py — Dò ký hiệu ranh giới witness-line/dimension-line
(tick-mark chéo ~45° hoặc mũi tên hội tụ) tại 1 điểm mút, ĐỘC LẬP với OCR/text.

BỐI CẢNH (xem "Phương án tổng thể", Lớp 1): text-anchor blocking
(line_merging.py, đã triển khai trước) chỉ chặn gộp nhầm khi OCR đọc đúng và
định vị đúng text dimension_value nằm giữa 2 line. Nó sẽ thất bại nếu:
  - OCR không đọc được / đọc sai text đó,
  - text bị lệch vị trí so với witness-line thật,
  - có ghi chú khác chen vào gần witness-line (nhiễu dương tính giả).

Tick-mark/arrowhead là tín hiệu đúng bản chất CAD hơn: mọi witness-line/
dimension-line chuẩn đều có ký hiệu ở 2 đầu mút (gạch chéo ~45° hoặc mũi tên)
bất kể pipeline text có hoạt động đúng hay không. Vì vậy tín hiệu này nên là
LỚP CHÍNH, còn text-anchor lùi thành lớp dự phòng (dùng khi ảnh scan mờ,
không dò được nét chéo, hoặc không có image_bgr truyền vào).

CÁCH DÒ (heuristic hình học thuần túy, không dùng OCR):
  1. Cắt 1 cửa sổ nhỏ (mặc định 20px mỗi cạnh) quanh điểm mút cần kiểm tra.
  2. Canny + HoughLinesP trong cửa sổ đó với minLineLength rất nhỏ (bắt được
     cả nét ngắn 4-5px của tick-mark).
  3. Với mỗi đoạn dò được, loại bỏ các đoạn gần như song song hoặc gần như
     vuông góc với line chính (đó là chính nó / hatch chạy dọc theo line) —
     chỉ giữ đoạn có góc lệch nằm trong dải "chéo" (mặc định 25°-65° so với
     line chính, bao trùm quy ước 45° phổ biến của tick-mark kỹ thuật).
  4. Đoạn chéo đó phải có ít nhất 1 đầu mút nằm sát điểm đang kiểm tra
     (trong bán kính proximity_px) — tránh bắt nhầm nét hatch chéo ở xa.
  5. Nếu có >=1 đoạn thỏa mãn -> coi là có ký hiệu ranh giới tại điểm đó.

GIỚI HẠN TRUNG THỰC (chưa giải quyết hết):
  - Đây là heuristic đơn-tín hiệu (1 đoạn chéo là đủ để báo "có tick-mark"),
    CHƯA phân biệt mũi tên thật (2 đoạn chéo đối xứng hội tụ) với 1 nét hatch
    chéo tình cờ rơi đúng vào cửa sổ + đúng dải góc + đúng gần điểm mút. Rủi
    ro dương tính giả tồn tại trên ảnh có hatch chéo dày đặc gần witness-line.
    Việc phân biệt "1 nét chéo" và "2 nét chéo đối xứng tạo hình mũi tên" là
    bước tinh chỉnh tiếp theo (xem detect_tick_mark_at_point(min_segments=...)
    để tăng độ chắc chắn nếu cần, đánh đổi lấy recall thấp hơn).
  - ĐÃ benchmark trên ảnh scan thật "TP-TL-A001/07/26" (19/07/2026). Kết quả
    quan trọng: bản vẽ này KHÔNG dùng tick-mark chéo 45° cho ranh giới
    dim-chain (2760/1525), mà dùng WITNESS-LINE THẲNG ĐỨNG (vuông góc ~90°
    với dim-line) cắt ngang tại điểm ranh giới. detect_tick_mark_at_point()
    với dải mặc định [25°-65°] KHÔNG bắt được kiểu ký hiệu này — đây là lý do
    thêm hàm split_raw_line_at_tick_marks() bên dưới, dùng phương pháp khác
    (column-projection, không phải Hough góc chéo) cho đúng loại ký hiệu này.

CHỨC NĂNG THỨ 2 — split_raw_line_at_tick_marks() (thêm 19/07/2026):
  Trên ảnh thật, Hough thường tự "fuse" một dim-chain nhiều đoạn (vd
  "2760"+"1525" trên cùng 1 dim-line) thành 1 RawLine LIÊN TỤC — KHÔNG có
  khoảng trống pixel nào ở ranh giới, dù ranh giới đó có witness-line cắt
  ngang. merge_collinear_lines() (line_merging.py) chỉ kiểm tra ranh giới
  tại các khoảng TRỐNG giữa 2 segment khác nhau — nếu Hough đã fuse thành 1
  segment thì không có khoảng trống nào để kiểm tra, nên bug này KHÔNG thể
  fix bằng cơ chế "chặn gộp" (Lớp 1/2 trong merge_collinear_lines) mà phải
  TÁCH line fused đó trước, ngay tại bước tiền xử lý — đó là việc của hàm
  split_raw_line_at_tick_marks().

  CÁCH DÒ (khác hẳn detect_tick_mark_at_point — không dùng Hough góc chéo):
    Quét dọc theo trục chính của line (bước step_px), tại mỗi điểm lấy 1 dải
    cột hẹp (±col_half_px) VUÔNG GÓC với line, đếm số hàng có pixel tối
    (< dark_threshold) trong dải đó — nếu đủ số hàng tối liên tiếp NGAY SÁT
    line (điều kiện "chạm" — touching, để phân biệt với text/ghi chú nổi trôi
    KHÔNG chạm line) và tổng đủ dài — coi là có witness-line cắt ngang tại đó.
    Kiểm tra CẢ 2 phía (trước và sau line theo phương pháp tuyến) vì ký hiệu
    có thể chỉ hiện ở 1 phía trên ảnh scan.

  GIỚI HẠN TRUNG THỰC của split_raw_line_at_tick_marks():
    - Chỉ mới benchmark chính xác trên 1 điểm ranh giới thật (2760/1525 của
      "TP-TL-A001/07/26") + fixture tổng hợp — CHƯA chạy trên nhiều ảnh scan
      khác nhau.
    - Điều kiện "chạm" (touching) là heuristic đơn giản (row liền kề dim-line
      có pixel tối) — trên ảnh scan nhiễu/mờ có thể vẫn lọt sai ở ranh giới
      giữa witness-line thật và ghi chú/hatch tình cờ chạm sát dim-line.
    - CHƯA xử lý line có góc bất kỳ một cách kỹ lưỡng (mới test kỹ dim-line
      ngang/dọc — góc xiên dùng phép quay toạ độ chung nhưng chưa benchmark).
    - CHƯA gộp với detect_tick_mark_at_point() (tick-mark chéo 45°) thành 1
      hàm duy nhất — 2 kiểu ký hiệu (chéo 45° vs vuông góc 90°) hiện dùng 2
      cơ chế dò khác nhau, gọi riêng. Cần thêm ảnh thật dùng tick-mark chéo
      thật để xác nhận cơ chế cũ còn đúng khi kết hợp.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import cv2
import numpy as np

try:  # tránh phụ thuộc vòng khi chỉ cần detect_tick_mark_at_point (không cần RawLine)
    from .geometry_extraction import RawLine
    from .models import new_id
except ImportError:  # pragma: no cover
    RawLine = object  # type: ignore

    def new_id(prefix: str) -> str:  # type: ignore
        import uuid
        return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _angle_diff_mod_pi(a: float, b: float) -> float:
    d = abs(a - b) % math.pi
    return min(d, math.pi - d)


def _crop_window(
    image_gray: np.ndarray, cx: float, cy: float, half_size: float
) -> Tuple[Optional[np.ndarray], Tuple[int, int]]:
    h, w = image_gray.shape[:2]
    x0 = int(max(0, math.floor(cx - half_size)))
    y0 = int(max(0, math.floor(cy - half_size)))
    x1 = int(min(w, math.ceil(cx + half_size)))
    y1 = int(min(h, math.ceil(cy + half_size)))
    if x1 <= x0 or y1 <= y0:
        return None, (0, 0)
    return image_gray[y0:y1, x0:x1], (x0, y0)


def detect_tick_mark_at_point(
    image_bgr: Optional[np.ndarray],
    point: Tuple[float, float],
    ref_angle: float,
    window_px: float = 20.0,
    canny_low: int = 50,
    canny_high: int = 150,
    hough_threshold: int = 8,
    min_segment_len: int = 4,
    max_segment_gap: int = 2,
    diagonal_angle_min_deg: float = 25.0,
    diagonal_angle_max_deg: float = 65.0,
    proximity_px: float = 6.0,
    min_segments: int = 1,
) -> bool:
    """Trả về True nếu tìm thấy ký hiệu ranh giới (nét chéo ~45°, kiểu
    tick-mark/arrowhead) sát điểm mút `point` của 1 witness-line có phương
    `ref_angle` (radian, mod pi).

    image_bgr=None (không có ảnh gốc, vd chỉ có RawLine/RawText tách rời)
    -> luôn trả về False, để tầng gọi tự rơi về lớp tín hiệu dự phòng
    (text-anchor). Đây là hành vi cố ý, không phải lỗi.

    min_segments: số đoạn chéo tối thiểu cần tìm thấy để báo True — mặc định
    1 (ưu tiên recall, "thà báo nhầm còn hơn gộp nhầm"). Tăng lên 2 nếu ảnh
    scan có nhiều hatch chéo gây dương tính giả và cần độ chắc chắn cao hơn
    (gần với "mũi tên thật" = 2 nét chéo).
    """
    if image_bgr is None:
        return False

    gray = image_bgr if image_bgr.ndim == 2 else cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    crop, (ox, oy) = _crop_window(gray, point[0], point[1], window_px)
    if crop is None or crop.size == 0:
        return False

    edges = cv2.Canny(crop, canny_low, canny_high)
    segments = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180, threshold=hough_threshold,
        minLineLength=min_segment_len, maxLineGap=max_segment_gap,
    )
    if segments is None:
        return False

    seg = np.asarray(segments).reshape(-1, 4)
    px, py = point[0] - ox, point[1] - oy

    hits = 0
    for x1, y1, x2, y2 in seg:
        seg_angle = math.atan2(float(y2 - y1), float(x2 - x1)) % math.pi
        diff_deg = math.degrees(_angle_diff_mod_pi(seg_angle, ref_angle))
        if not (diagonal_angle_min_deg <= diff_deg <= diagonal_angle_max_deg):
            continue
        d1 = math.hypot(x1 - px, y1 - py)
        d2 = math.hypot(x2 - px, y2 - py)
        if min(d1, d2) <= proximity_px:
            hits += 1
            if hits >= min_segments:
                return True

    return False


def _perpendicular_witness_at_point(
    gray: np.ndarray,
    px: float,
    py: float,
    angle: float,
    probe_window_px: int = 20,
    col_half_px: int = 3,
    dark_threshold: int = 190,
    leading_gap_max_px: int = 5,
    min_run_px: int = 8,
    run_gap_tol_px: int = 1,
) -> bool:
    """Column-projection: kiểm tra có witness-line/nét CẮT NGANG (~vuông góc)
    line chính tại điểm (px,py) hay không — dùng cho ký hiệu ranh giới kiểu
    "đường dọc chạm dim-line" (khác tick-mark chéo 45° của
    detect_tick_mark_at_point ở trên). Xem docstring đầu file.

    SỬA 19/07/2026 sau benchmark ảnh thật "TP-TL-A001/07/26": bản đầu tiên
    của hàm này dùng điều kiện "touch trong touch_rows_px hàng đầu + tổng
    >= min_dark_rows hàng tối trong CẢ cửa sổ" — benchmark trên đúng ranh
    giới thật (x=776, giữa "2760" và "1525") cho thấy điều kiện này SAI Ở CẢ
    2 CHIỀU:
      - False negative tại witness-line thật: witness-line có "standoff gap"
        (khoảng hở quy ước ~vài px giữa đầu witness-line và dim-line, không
        chạm trực tiếp) — điều kiện "chạm trong touch_rows_px=3 hàng đầu"
        loại luôn ký hiệu thật.
      - False positive tại chỗ không có ranh giới: hàng k=1 (ngay sát/đè lên
        chính dim-line) hầu như LUÔN tối (đó là chính nét dim-line, không
        phải witness-line) nên luôn "touched=True"; sau đó chỉ cần bất kỳ
        pixel tối nào khác trong cửa sổ (rất dễ xảy ra vì số kích thước/ghi
        chú thường nằm cách dim-line 10-25px, đúng trong probe_window_px=20)
        là đủ đạt min_dark_rows=4 dù các pixel đó KHÔNG liên tục / không
        phải cùng 1 đường thẳng — bắt nhầm text/hatch rời rạc thành witness-line.

    THUẬT TOÁN MỚI (chạy dọc theo pháp tuyến, đếm CHUỖI LIÊN TỤC thay vì chỉ
    đếm tổng số hàng tối):
      1. Cho phép hở đầu (standoff) tối đa `leading_gap_max_px` trước khi gặp
         hàng tối đầu tiên — witness-line thật thường không chạm dim-line
         ngay từ pixel đầu tiên.
      2. Từ hàng tối đầu tiên đó, CHUỖI phải liên tục — cho phép hở nhỏ
         `run_gap_tol_px` (nhiễu quét 1px) nhưng hở lớn hơn thì NGẮT chuỗi
         (đây là điểm khác biệt cốt lõi so với bản cũ: text/hatch rải rác ở
         xa không còn nối được vào chuỗi tính từ dim-line).
      3. Chuỗi liên tục đó phải dài >= `min_run_px` mới coi là witness-line
         thật (đường quá ngắn — vd chỉ đúng độ dày nét dim-line — bị loại).

    Kiểm tra CẢ 2 phía của line (theo 2 chiều pháp tuyến +n và -n).

    GIỚI HẠN TRUNG THỰC: ngưỡng leading_gap_max_px=5 / min_run_px=8 hiệu
    chỉnh thủ công trên 1 điểm ranh giới thật (x=776) + 1 điểm false-positive
    đã biết (x=673) của "TP-TL-A001/07/26" — CHƯA quét rộng trên nhiều ảnh
    scan khác để xác nhận ngưỡng này tổng quát.
    """
    h, w = gray.shape[:2]
    dx, dy = math.cos(angle), math.sin(angle)      # dọc theo line
    nx, ny = -math.sin(angle), math.cos(angle)     # pháp tuyến

    def _row_dark(ox: float, oy: float) -> bool:
        for j in range(-col_half_px, col_half_px + 1):
            xi = int(round(ox + j * dx))
            yi = int(round(oy + j * dy))
            if 0 <= yi < h and 0 <= xi < w and gray[yi, xi] < dark_threshold:
                return True
        return False

    for side in (1.0, -1.0):
        run_len = 0
        run_started = False
        started_within_leading = False
        gap = 0
        for k in range(1, probe_window_px + 1):
            ox = px + side * k * nx
            oy = py + side * k * ny
            if _row_dark(ox, oy):
                if not run_started:
                    run_started = True
                    started_within_leading = k <= leading_gap_max_px
                run_len += 1
                gap = 0
            elif run_started:
                gap += 1
                if gap > run_gap_tol_px:
                    break
        if run_started and started_within_leading and run_len >= min_run_px:
            return True
    return False


def find_internal_boundary_offsets(
    image_bgr: Optional[np.ndarray],
    line: "RawLine",
    step_px: float = 2.0,
    endpoint_margin_px: float = 8.0,
    cluster_tol_px: float = 6.0,
    probe_window_px: int = 20,
    col_half_px: int = 3,
    dark_threshold: int = 190,
    leading_gap_max_px: int = 5,
    min_run_px: int = 8,
    run_gap_tol_px: int = 1,
) -> List[float]:
    """Quét dọc theo `line` (từ p1 đến p2), trả về danh sách khoảng cách
    (tính từ p1, đơn vị px) tại đó có ký hiệu ranh giới CẮT NGANG line —
    dùng để tách (split) 1 RawLine bị Hough fuse liền không có gap. Các điểm
    dò được gần nhau (trong `cluster_tol_px`) sẽ được gộp thành 1 (lấy trung
    vị). Bỏ qua vùng sát 2 đầu mút thật của line (`endpoint_margin_px`) vì
    tick-mark ở đó thuộc phạm vi xử lý của gap_blocked_by_tick_mark() trong
    line_merging.py (chỗ đã CÓ khoảng trống pixel), không phải hàm này.
    """
    if image_bgr is None:
        return []
    gray = image_bgr if image_bgr.ndim == 2 else cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    x1, y1 = line.p1_px
    x2, y2 = line.p2_px
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= 2 * endpoint_margin_px:
        return []
    angle = math.atan2(y2 - y1, x2 - x1) % math.pi
    dx, dy = math.cos(angle), math.sin(angle)
    # đảm bảo (dx,dy) cùng hướng p1->p2 (atan2 % pi có thể lật dấu)
    if (x2 - x1) * dx + (y2 - y1) * dy < 0:
        dx, dy = -dx, -dy

    hits: List[float] = []
    t = endpoint_margin_px
    while t <= length - endpoint_margin_px:
        px, py = x1 + t * dx, y1 + t * dy
        if _perpendicular_witness_at_point(
            gray, px, py, angle,
            probe_window_px=probe_window_px, col_half_px=col_half_px,
            dark_threshold=dark_threshold, leading_gap_max_px=leading_gap_max_px,
            min_run_px=min_run_px, run_gap_tol_px=run_gap_tol_px,
        ):
            hits.append(t)
        t += step_px

    if not hits:
        return []

    # gộp các hit liền kề (cluster_tol_px) thành 1 điểm split duy nhất (trung vị)
    clustered: List[List[float]] = [[hits[0]]]
    for h in hits[1:]:
        if h - clustered[-1][-1] <= cluster_tol_px:
            clustered[-1].append(h)
        else:
            clustered.append([h])
    return [sorted(c)[len(c) // 2] for c in clustered]


def split_raw_line_at_tick_marks(
    line: "RawLine",
    image_bgr: Optional[np.ndarray],
    diagonal_angle_min_deg: float = 25.0,
    diagonal_angle_max_deg: float = 65.0,
    step_px: float = 2.0,
    endpoint_margin_px: float = 8.0,
    cluster_tol_px: float = 6.0,
    probe_window_px: int = 20,
    col_half_px: int = 3,
    dark_threshold: int = 190,
    leading_gap_max_px: int = 5,
    min_run_px: int = 8,
    run_gap_tol_px: int = 1,
) -> List["RawLine"]:
    """Tách 1 RawLine dài bị Hough fuse liền (KHÔNG có khoảng trống pixel)
    tại các điểm NẰM GIỮA line có ký hiệu ranh giới cắt ngang (witness-line
    vuông góc — xem _perpendicular_witness_at_point). Trả về [line] nguyên
    vẹn nếu image_bgr=None hoặc không dò được điểm ranh giới nào bên trong.

    LƯU Ý: `diagonal_angle_min_deg`/`diagonal_angle_max_deg` hiện CHƯA được
    dùng trong hàm này (giữ tham số để tương thích chữ ký gọi từ
    line_merging.py và cho hướng mở rộng sau — dò thêm tick-mark chéo 45°
    NẰM GIỮA line bằng detect_tick_mark_at_point, không chỉ witness-line
    vuông góc). Xem giới hạn trung thực ở docstring đầu file.
    """
    if image_bgr is None:
        return [line]

    offsets = find_internal_boundary_offsets(
        image_bgr, line,
        step_px=step_px, endpoint_margin_px=endpoint_margin_px,
        cluster_tol_px=cluster_tol_px, probe_window_px=probe_window_px,
        col_half_px=col_half_px, dark_threshold=dark_threshold,
        leading_gap_max_px=leading_gap_max_px, min_run_px=min_run_px,
        run_gap_tol_px=run_gap_tol_px,
    )
    if not offsets:
        return [line]

    x1, y1 = line.p1_px
    x2, y2 = line.p2_px
    length = math.hypot(x2 - x1, y2 - y1)
    angle = math.atan2(y2 - y1, x2 - x1) % math.pi
    dx, dy = math.cos(angle), math.sin(angle)
    if (x2 - x1) * dx + (y2 - y1) * dy < 0:
        dx, dy = -dx, -dy

    bounds = [0.0] + sorted(offsets) + [length]
    result: List["RawLine"] = []
    for t0, t1 in zip(bounds[:-1], bounds[1:]):
        if t1 - t0 < 1e-6:
            continue
        p_start = (x1 + t0 * dx, y1 + t0 * dy)
        p_end = (x1 + t1 * dx, y1 + t1 * dy)
        bbox = (
            min(p_start[0], p_end[0]), min(p_start[1], p_end[1]),
            max(p_start[0], p_end[0]), max(p_start[1], p_end[1]),
        )
        result.append(RawLine(
            id=new_id("rawline-split"),
            p1_px=p_start,
            p2_px=p_end,
            confidence=line.confidence,
            bbox_px=bbox,
        ))
    return result or [line]
