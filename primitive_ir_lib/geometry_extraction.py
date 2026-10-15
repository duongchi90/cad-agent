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
# haloed tiles. With the shipped max-radius presets (<= 400 px), every tile is
# at most 2,000 x 2,000 pixels while retaining a full-radius halo at seams.
_HOUGH_CIRCLE_DIRECT_MAX_PIXELS = 4_000_000
_HOUGH_CIRCLE_TILE_MAX_SIDE_PX = 2_000
_CIRCLE_RASTER_FIT_TOLERANCE_PX = float(np.sqrt(2.0))


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


def _fit_supported_circle_contours(
    edges: np.ndarray,
    min_radius: int,
    max_radius: int,
) -> List[Tuple[float, float, float, float]]:
    """Fit only closed, raster-consistent circle contours from source edges.

    The contour residual envelope is derived from raster quantization: a point
    can move at most half a pixel per axis, so the relative two-point bound is
    sqrt(2) px. A complete contour also cannot have an angular sample gap larger
    than the angle subtended by that same pixel-spacing bound.
    """
    contours, _ = cv2.findContours(edges.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    fit_tolerance_px = _CIRCLE_RASTER_FIT_TOLERANCE_PX
    fits: List[Tuple[float, float, float, float]] = []

    for contour in contours:
        points = np.asarray(contour, dtype=np.float64).reshape(-1, 2)
        if len(points) < 12:
            continue

        origin_x = float(np.mean(points[:, 0]))
        origin_y = float(np.mean(points[:, 1]))
        x = points[:, 0] - origin_x
        y = points[:, 1] - origin_y
        matrix = np.column_stack((x, y, np.ones_like(x)))
        try:
            a, b, c = np.linalg.lstsq(matrix, -(x * x + y * y), rcond=None)[0]
        except np.linalg.LinAlgError:
            continue
        center_x = origin_x + float(-a / 2.0)
        center_y = origin_y + float(-b / 2.0)
        radius_squared = (a * a + b * b) / 4.0 - float(c)
        if not np.isfinite(radius_squared) or radius_squared <= 0.0:
            continue
        radius = float(np.sqrt(radius_squared))
        if radius < min_radius or radius > max_radius:
            continue

        radial_error = np.abs(
            np.hypot(points[:, 0] - center_x, points[:, 1] - center_y) - radius
        )
        max_radial_error = float(np.max(radial_error))
        if max_radial_error > fit_tolerance_px:
            continue

        angles = np.sort(np.mod(
            np.arctan2(points[:, 1] - center_y, points[:, 0] - center_x),
            2.0 * np.pi,
        ))
        angular_gaps = np.diff(np.concatenate((angles, angles[:1] + 2.0 * np.pi)))
        max_gap = float(np.max(angular_gaps))
        # Pixel-step spacing plus the observed radial-fit envelope bounds the
        # angular gap between neighboring raster samples on the fitted contour.
        contour_spacing_bound_px = fit_tolerance_px + 2.0 * max_radial_error
        max_gap_from_pixel_spacing = 2.0 * float(np.arcsin(min(
            1.0, contour_spacing_bound_px / (2.0 * radius),
        )))
        if max_gap - max_gap_from_pixel_spacing > 1e-12:
            continue

        fits.append((center_x, center_y, radius, max_radial_error))

    return sorted(fits, key=lambda fit: (fit[1], fit[0], fit[2]))


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


def extract_circles(
    image_bgr: np.ndarray,
    min_radius: int = 5,
    max_radius: int = 200,
    param1: int = 100,
    param2: int = 30,
    min_dist: int = 20,
) -> List[RawCircle]:
    """Propose circles with Hough, then admit only source-fitted closed circles."""
    gray = _preprocess(image_bgr)
    edges = cv2.Canny(gray, param1 / 2, param1)
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
    supported_fits = _fit_supported_circle_contours(
        edges,
        min_radius=min_radius,
        max_radius=max_radius,
    )
    proposed: List[Tuple[float, float, float]] = [
        (x, y, radius)
        for x, y, radius, _ in supported_fits
    ]

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
            radius = float(r)
            # Hough is a proposal source only. It must agree with the same
            # source-fitted closed contour used for large-radius recovery.
            nearest_fit = min(
                supported_fits,
                key=lambda fit: (
                    (fit[0] - x) ** 2 + (fit[1] - y) ** 2
                    + (fit[2] - radius) ** 2
                ),
                default=None,
            )
            if nearest_fit is None:
                continue
            if np.hypot(nearest_fit[0] - x, nearest_fit[1] - y) > _CIRCLE_RASTER_FIT_TOLERANCE_PX:
                continue
            if abs(nearest_fit[2] - radius) > _CIRCLE_RASTER_FIT_TOLERANCE_PX:
                continue
            proposed.append((nearest_fit[0], nearest_fit[1], nearest_fit[2]))

    for x, y, radius in proposed:
        bbox = (x - radius, y - radius, x + radius, y + radius)
        raw_circles.append(RawCircle(
            id=new_id("rawcirc"),
            center_px=(x, y),
            radius_px=radius,
            confidence=0.75,  # ước lượng cố định — xem docstring
            bbox_px=bbox,
        ))

    deduplicated: List[RawCircle] = []
    for circle in raw_circles:
        if any(
            (circle.center_px[0] - existing.center_px[0]) ** 2
            + (circle.center_px[1] - existing.center_px[1]) ** 2 < min_dist_sq
            for existing in deduplicated
        ):
            continue
        deduplicated.append(circle)
    return deduplicated


# Bộ tham số tinh chỉnh từ ảnh scan thật đầu tiên (mục 3 báo cáo kiểm thử
# Phase 1, 18/07/2026, bản vẽ "TP-TL-A001/07/26"): giảm nhiễu hatch (circle
# giả) và loại nét hatch ngắn khỏi kết quả line. Xem cảnh báo ở docstring đầu
# file — chỉ mới xác nhận trên 1 ảnh, cần benchmark thêm.
# max_radius=400 additionally admits the source-supported 312.5 px circle from
# CASE05 motor-mount-top; closed-contour admission and OCR caller semantics gate
# this larger search bound. This is not evidence of broader precision.
PRESETS = {
    "default": {
        "hough_threshold": 60, "min_line_length": 30, "max_line_gap": 10,
        "param2": 30, "max_radius": 200, "min_dist": 20,
    },
    "real_scan_tuned_v1": {
        "hough_threshold": 90, "min_line_length": 50, "max_line_gap": 5,
        "param2": 55, "max_radius": 400, "min_dist": 40,
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
