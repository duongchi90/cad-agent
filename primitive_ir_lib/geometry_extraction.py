"""
geometry_extraction.py — Trích xuất line/circle bằng OpenCV Canny+Hough.

QUAN TRỌNG: hàm ở đây trả về tọa độ PIXEL (RawLine/RawCircle), KHÔNG phải tọa
độ CAD. Lý do: calibration (pixel -> mm) thường chỉ xác định được SAU khi biết
ít nhất 1 kích thước tham chiếu (thường đọc từ text) — nên geometry extraction
và calibration là 2 bước tách rời, đúng thứ tự trong sơ đồ kiến trúc mục 2.
Dùng calibration.py để quy đổi RawLine/RawCircle -> Primitive (models.py) sau.

ĐÍNH CHÍNH (18/07/2026): docstring bản trước ghi "đã benchmark tốt trên 4 ảnh
thật" — KHÔNG chính xác. Báo cáo kiểm thử Phase 1 (18/07/2026, xem
bao_cao_kiem_thu_cad_agent.docx mục 1) xác nhận bộ tham số mặc định trước đó
chỉ được benchmark trên ảnh tổng hợp (synthetic) sạch; khi chạy trên 1 ảnh
scan thật đầu tiên ("TP-TL-A001/07/26"), Hough Circle/Line mặc định bị nhiễu
nặng bởi hatch (656 line/971 circle, phần lớn circle giả — xem mục 3 báo cáo).

Bộ tham số REAL_SCAN_TUNED_V1 dưới đây là kết quả tinh chỉnh thủ công trên
ĐÚNG 1 ảnh đó, giảm còn 323 line/13 circle khớp đúng vị trí bánh xe. Đây MỚI
chỉ là điểm khởi đầu hợp lý, KHÔNG phải giá trị đã benchmark trên nhiều ảnh —
cần chạy lại trên tập ảnh scan thật đa dạng hơn (khác độ phân giải, độ đậm
nét, loại hatch) trước khi coi là mặc định chính thức. Vì vậy preset này
KHÔNG tự động thay thế "default" (tham số gốc, giữ để không phá vỡ pipeline
đang chạy trên ảnh tổng hợp) — gọi rõ ràng bằng preset="real_scan_tuned_v1".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import cv2
import numpy as np

from .models import new_id


@dataclass
class RawLine:
    id: str
    p1_px: Tuple[float, float]
    p2_px: Tuple[float, float]
    confidence: float
    bbox_px: Tuple[float, float, float, float]

    def length_px(self) -> float:
        return float(np.hypot(self.p2_px[0] - self.p1_px[0], self.p2_px[1] - self.p1_px[1]))


@dataclass
class RawCircle:
    id: str
    center_px: Tuple[float, float]
    radius_px: float
    confidence: float
    bbox_px: Tuple[float, float, float, float]


@dataclass
class RawGeometry:
    lines: List[RawLine] = field(default_factory=list)
    circles: List[RawCircle] = field(default_factory=list)


def _preprocess(image_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    return blurred


def extract_lines(
    image_bgr: np.ndarray,
    canny_low: int = 50,
    canny_high: int = 150,
    hough_threshold: int = 60,
    min_line_length: int = 30,
    max_line_gap: int = 10,
) -> List[RawLine]:
    """HoughLinesP trên ảnh sau Canny. confidence ước lượng thô từ độ dài
    đoạn so với min_line_length (đoạn càng dài, vote Hough càng chắc)."""
    gray = _preprocess(image_bgr)
    edges = cv2.Canny(gray, canny_low, canny_high)
    segments = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180, threshold=hough_threshold,
        minLineLength=min_line_length, maxLineGap=max_line_gap,
    )

    raw_lines: List[RawLine] = []
    if segments is None:
        return raw_lines

    # Tương thích cả OpenCV 4 (shape (N,1,4)) lẫn OpenCV 5 (shape (N,4)):
    # luôn chuẩn hoá về mảng 2D (N,4), mỗi hàng là [x1,y1,x2,y2].
    seg = np.asarray(segments).reshape(-1, 4)

    lengths = [float(np.hypot(x2 - x1, y2 - y1)) for (x1, y1, x2, y2) in seg]
    max_len = max(lengths) if lengths else 1.0

    for (x1, y1, x2, y2), length in zip(seg, lengths):
        confidence = min(1.0, 0.5 + 0.5 * (length / max_len))
        bbox = (float(min(x1, x2)), float(min(y1, y2)), float(max(x1, x2)), float(max(y1, y2)))
        raw_lines.append(RawLine(
            id=new_id("rawline"),
            p1_px=(float(x1), float(y1)),
            p2_px=(float(x2), float(y2)),
            confidence=round(confidence, 3),
            bbox_px=bbox,
        ))
    return raw_lines


def _circle_edge_support(
    edge_distance: np.ndarray, x: float, y: float, radius: float,
) -> Tuple[float, float]:
    """Return supported circumference fraction and longest unsupported gap.

    Sample at least twice per degree and twice per circumference pixel. Allow
    three pixels (or 4% of the radius) for stroke width, pixel rounding and
    Hough localization. Oversampling avoids angular/raster-grid aliasing.
    Samples outside the source image count as unsupported.
    """
    sample_count = max(720, int(np.ceil(4 * np.pi * radius)))
    angles = np.arange(sample_count) * (2 * np.pi / sample_count)
    xs = np.rint(x + radius * np.cos(angles)).astype(int)
    ys = np.rint(y + radius * np.sin(angles)).astype(int)
    height, width = edge_distance.shape
    inside = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
    supported = np.zeros(sample_count, dtype=bool)
    supported[inside] = edge_distance[ys[inside], xs[inside]] <= max(3.0, 0.04 * radius)
    coverage = float(supported.mean())
    if not supported.any():
        return coverage, 360.0

    # Start at a supported sample so a gap crossing zero degrees stays whole.
    start = int(np.flatnonzero(supported)[0])
    longest_gap = current_gap = 0
    for has_edge in np.roll(supported, -start):
        current_gap = 0 if has_edge else current_gap + 1
        longest_gap = max(longest_gap, current_gap)
    return coverage, longest_gap * 360.0 / sample_count


def extract_circles(
    image_bgr: np.ndarray,
    min_radius: int = 5,
    max_radius: int = 200,
    param1: int = 100,
    param2: int = 30,
    min_dist: int = 20,
) -> List[RawCircle]:
    """Admit Hough candidates only when source edges support a full circle.

    confidence is measured circumference support, not an engineering-truth
    probability. Up to 15% distributed raster loss is tolerated, but an open
    interval exceeding 30 degrees is not promoted to a closed CAD circle.
    """
    gray = _preprocess(image_bgr)
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1, minDist=min_dist,
        param1=param1, param2=param2, minRadius=min_radius, maxRadius=max_radius,
    )

    raw_circles: List[RawCircle] = []
    if circles is None:
        return raw_circles

    # Tương thích cả OpenCV 4 (shape (1,N,3)) lẫn OpenCV 5 (shape (N,3)):
    # chuẩn hoá về mảng 2D (N,3), mỗi hàng là [x,y,r].
    circ = np.asarray(circles).reshape(-1, 3)
    edges = cv2.Canny(gray, param1 / 2, param1)
    edge_distance = cv2.distanceTransform(255 - edges, cv2.DIST_L2, 3)

    for x, y, r in circ:
        coverage, longest_gap = _circle_edge_support(edge_distance, float(x), float(y), float(r))
        if coverage < 0.85 or longest_gap > 30.0:
            continue
        bbox = (float(x - r), float(y - r), float(x + r), float(y + r))
        raw_circles.append(RawCircle(
            id=new_id("rawcirc"),
            center_px=(float(x), float(y)),
            radius_px=float(r),
            confidence=round(coverage, 3),
            bbox_px=bbox,
        ))
    return raw_circles


# Bộ tham số tinh chỉnh từ ảnh scan thật đầu tiên (mục 3 báo cáo kiểm thử
# Phase 1, 18/07/2026, bản vẽ "TP-TL-A001/07/26"): giảm nhiễu hatch (circle
# giả) và loại nét hatch ngắn khỏi kết quả line. Xem cảnh báo ở docstring đầu
# file — chỉ mới xác nhận trên 1 ảnh, cần benchmark thêm.
PRESETS = {
    "default": {
        "hough_threshold": 60, "min_line_length": 30, "max_line_gap": 10,
        "param2": 30, "max_radius": 200, "min_dist": 20,
    },
    "real_scan_tuned_v1": {
        "hough_threshold": 90, "min_line_length": 50, "max_line_gap": 5,
        "param2": 55, "max_radius": 80, "min_dist": 40,
    },
}


def extract_raw_geometry(image_bgr: np.ndarray, preset: str = "default", **kwargs) -> RawGeometry:
    """Entry point chính của module.

    preset: bộ tham số nền dùng trước khi áp kwargs override lên trên — xem
    PRESETS ở trên. "default" giữ hành vi gốc (tối ưu cho ảnh tổng hợp sạch);
    "real_scan_tuned_v1" là bộ đã tinh chỉnh cho ảnh scan thật có hatch (mục 3
    báo cáo kiểm thử), CHƯA benchmark rộng — dùng như điểm khởi đầu, không
    phải giá trị chốt.

    kwargs chuyển tiếp cho extract_lines/extract_circles, override lên trên
    preset, để tinh chỉnh thêm nếu cần (vd threshold khác nhau tùy ảnh scan
    cụ thể).
    """
    if preset not in PRESETS:
        raise ValueError(f"preset không hợp lệ: {preset!r}. Chọn 1 trong {sorted(PRESETS)}")

    merged = dict(PRESETS[preset])
    merged.update(kwargs)

    line_kwargs = {k: v for k, v in merged.items() if k in (
        "canny_low", "canny_high", "hough_threshold", "min_line_length", "max_line_gap")}
    circle_kwargs = {k: v for k, v in merged.items() if k in (
        "min_radius", "max_radius", "param1", "param2", "min_dist")}
    return RawGeometry(
        lines=extract_lines(image_bgr, **line_kwargs),
        circles=extract_circles(image_bgr, **circle_kwargs),
    )
