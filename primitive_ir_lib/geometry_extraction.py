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


# OpenCV HoughCircles allocates several full-resolution work buffers in addition
# to its accumulator. Keep the direct path for ordinary images, but bound each
# Hough input on large rendered sheets by splitting the preprocessed image into
# haloed tiles. With the shipped max-radius presets (<= 200 px), every tile is
# at most 2,000 x 2,000 pixels while retaining a full-radius halo at seams.
_HOUGH_CIRCLE_DIRECT_MAX_PIXELS = 4_000_000
_HOUGH_CIRCLE_TILE_MAX_SIDE_PX = 2_000

# Bound source-raster endpoint recovery for the tuned line detector. The
# CASE01 render has dark line ink (grayscale <= 31) against paper (>= 220);
# focused interruption and adjacency controls guard this operating range.
_LINE_ENDPOINT_MAX_EXTENSION_PX = 30
_LINE_ENDPOINT_DARK_THRESHOLD = 180
_LINE_ENDPOINT_PERP_HALF_WIDTH_PX = 2
_LINE_ENDPOINT_PROFILE_HALF_WIDTH_PX = 8


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


def _extend_line_endpoints_along_ink(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    gray: np.ndarray,
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Extend Hough endpoints only while a narrow source-ink corridor continues."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = float(np.hypot(dx, dy))
    if not np.isfinite(length) or length == 0 or gray.ndim != 2:
        return p1, p2

    height, width = gray.shape
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux

    def profile_ink_count(point: Tuple[float, float]) -> int:
        sample_positions = set()
        for offset in range(
            -_LINE_ENDPOINT_PROFILE_HALF_WIDTH_PX,
            _LINE_ENDPOINT_PROFILE_HALF_WIDTH_PX + 1,
        ):
            px = int(round(point[0] + nx * offset))
            py = int(round(point[1] + ny * offset))
            if 0 <= px < width and 0 <= py < height:
                sample_positions.add((px, py))
        return sum(
            gray[py, px] <= _LINE_ENDPOINT_DARK_THRESHOLD
            for px, py in sample_positions
        )

    def march(endpoint: Tuple[float, float], direction: float) -> Tuple[float, float]:
        best = endpoint
        if length < 2:
            return best
        baseline_counts = [
            profile_ink_count(
                (
                    endpoint[0] - direction * ux * length * fraction,
                    endpoint[1] - direction * uy * length * fraction,
                )
            )
            for fraction in (0.2, 0.35, 0.5, 0.65, 0.8)
        ]
        # Keep the allowance near the candidate's observed width so partial
        # perpendicular junctions cannot hide just below the finite window.
        profile_limit = min(
            max(baseline_counts) + 1,
            2 * _LINE_ENDPOINT_PROFILE_HALF_WIDTH_PX,
        )
        for distance in range(1, _LINE_ENDPOINT_MAX_EXTENSION_PX + 1):
            x = endpoint[0] + direction * ux * distance
            y = endpoint[1] + direction * uy * distance
            center_x = int(round(x))
            center_y = int(round(y))
            if not (0 <= center_x < width and 0 <= center_y < height):
                break
            if gray[center_y, center_x] > _LINE_ENDPOINT_DARK_THRESHOLD:
                break
            if profile_ink_count((x, y)) > profile_limit:
                break

            sample_positions = set()
            for offset in range(-_LINE_ENDPOINT_PERP_HALF_WIDTH_PX, _LINE_ENDPOINT_PERP_HALF_WIDTH_PX + 1):
                px = int(round(x + nx * offset))
                py = int(round(y + ny * offset))
                if 0 <= px < width and 0 <= py < height:
                    sample_positions.add((px, py))
            dark_samples = sum(
                gray[py, px] <= _LINE_ENDPOINT_DARK_THRESHOLD
                for px, py in sample_positions
            )

            if dark_samples >= 2:
                best = (x, y)
            else:
                break
        return best

    return march(p1, -1.0), march(p2, 1.0)


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
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, canny_low, canny_high)
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
        p1, p2 = _extend_line_endpoints_along_ink(
            (float(x1), float(y1)), (float(x2), float(y2)), gray,
        )
        bbox = (float(min(p1[0], p2[0])), float(min(p1[1], p2[1])), float(max(p1[0], p2[0])), float(max(p1[1], p2[1])))
        raw_lines.append(RawLine(
            id=new_id("rawline"),
            p1_px=p1,
            p2_px=p2,
            confidence=round(confidence, 3),
            bbox_px=bbox,
        ))
    return raw_lines


def extract_circles(
    image_bgr: np.ndarray,
    min_radius: int = 5,
    max_radius: int = 200,
    param1: int = 100,
    param2: int = 30,
    min_dist: int = 20,
) -> List[RawCircle]:
    """HoughCircles (phương pháp gradient). confidence ước lượng thô cố định
    ở mức trung bình-cao vì HoughCircles của OpenCV không trả vote count trực
    tiếp qua API Python — nên đánh dấu rõ đây là ước lượng, không phải số đo."""
    gray = _preprocess(image_bgr)
    height, width = gray.shape[:2]

    if height * width <= _HOUGH_CIRCLE_DIRECT_MAX_PIXELS:
        tile_specs = [(0, 0, width, height)]
    else:
        halo = max(0, int(max_radius))
        core_size = max(1, _HOUGH_CIRCLE_TILE_MAX_SIDE_PX - 2 * halo)
        tile_specs = []
        for core_y0 in range(0, height, core_size):
            core_y1 = min(height, core_y0 + core_size)
            y0 = max(0, core_y0 - halo)
            y1 = min(height, core_y1 + halo)
            for core_x0 in range(0, width, core_size):
                core_x1 = min(width, core_x0 + core_size)
                x0 = max(0, core_x0 - halo)
                x1 = min(width, core_x1 + halo)
                tile_specs.append((x0, y0, x1, y1))

    raw_circles: List[RawCircle] = []
    min_dist_sq = float(min_dist) * float(min_dist)

    for x0, y0, x1, y1 in tile_specs:
        tile = gray[y0:y1, x0:x1]
        circles = cv2.HoughCircles(
            tile, cv2.HOUGH_GRADIENT, dp=1, minDist=min_dist,
            param1=param1, param2=param2, minRadius=min_radius, maxRadius=max_radius,
        )
        if circles is None:
            continue

        # Tương thích cả OpenCV 4 (shape (1,N,3)) lẫn OpenCV 5 (shape (N,3)):
        # chuẩn hoá về mảng 2D (N,3), mỗi hàng là [x,y,r].
        circ = np.asarray(circles).reshape(-1, 3)
        for local_x, local_y, r in circ:
            x = float(local_x) + x0
            y = float(local_y) + y0

            # Halo khiến cùng một circle có thể được phát hiện ở hai tile kề
            # nhau. HoughCircles đã dùng minDist trong từng tile; áp cùng ngưỡng
            # lên tọa độ global để giữ semantics cũ ở đường seam.
            if any(
                (x - existing.center_px[0]) ** 2 + (y - existing.center_px[1]) ** 2
                < min_dist_sq
                for existing in raw_circles
            ):
                continue

            radius = float(r)
            bbox = (x - radius, y - radius, x + radius, y + radius)
            raw_circles.append(RawCircle(
                id=new_id("rawcirc"),
                center_px=(x, y),
                radius_px=radius,
                confidence=0.75,  # ước lượng cố định — xem docstring
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
