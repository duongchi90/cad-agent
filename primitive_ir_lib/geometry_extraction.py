"""
geometry_extraction.py — Trích xuất line/circle bằng OpenCV Canny+Hough.

QUAN TRỌNG: hàm ở đây trả về tọa độ PIXEL (RawLine/RawCircle/RawArc), KHÔNG phải tọa
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
class RawArc:
    """Pixel-space arc carrier for an upstream owner that already observed an arc.

    Angles use the image's top-left origin and y-down coordinate system.  The
    end angle may be unwrapped past 360 degrees so the observed sweep is not
    lost before ``assemble.arc_to_primitive`` converts it to CAD coordinates.
    The detector intentionally does not populate this carrier yet.
    """

    id: str
    center_px: Tuple[float, float]
    radius_px: float
    start_angle_deg: float
    end_angle_deg: float
    confidence: float
    bbox_px: Tuple[float, float, float, float]


@dataclass
class RawGeometry:
    lines: List[RawLine] = field(default_factory=list)
    circles: List[RawCircle] = field(default_factory=list)
    arcs: List[RawArc] = field(default_factory=list)


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

    for x, y, r in circ:
        bbox = (float(x - r), float(y - r), float(x + r), float(y + r))
        raw_circles.append(RawCircle(
            id=new_id("rawcirc"),
            center_px=(float(x), float(y)),
            radius_px=float(r),
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


def _fit_circle(points: np.ndarray) -> tuple[float, float, float, np.ndarray] | None:
    """Fit one circle to residual edge pixels with a linear least-squares fit."""
    if len(points) < 3:
        return None
    coordinates = points.astype(np.float64, copy=False)
    x = coordinates[:, 0]
    y = coordinates[:, 1]
    matrix = np.column_stack((2.0 * x, 2.0 * y, np.ones_like(x)))
    if np.linalg.matrix_rank(matrix) < 3:
        return None
    center_x, center_y, constant = np.linalg.lstsq(
        matrix, x * x + y * y, rcond=None
    )[0]
    radius_squared = constant + center_x * center_x + center_y * center_y
    if radius_squared <= 0.0:
        return None
    radius = float(np.sqrt(radius_squared))
    residuals = np.abs(np.hypot(x - center_x, y - center_y) - radius)
    return float(center_x), float(center_y), radius, residuals


def _arc_angle_interval(
    points: np.ndarray, center_x: float, center_y: float
) -> tuple[float, float, float]:
    """Return the occupied circular interval in image (y-down) coordinates."""
    angles = np.degrees(
        np.arctan2(-(points[:, 1] - center_y), points[:, 0] - center_x)
    ) % 360.0
    ordered = np.sort(angles)
    gaps = np.diff(np.concatenate((ordered, ordered[:1] + 360.0)))
    largest_gap_index = int(np.argmax(gaps))
    start = float(ordered[(largest_gap_index + 1) % len(ordered)])
    end = float(ordered[largest_gap_index])
    if end < start:
        end += 360.0
    return start, end, end - start


def _extract_arcs(
    image_bgr: np.ndarray,
    lines: List[RawLine],
    circles: List[RawCircle],
) -> List[RawArc]:
    """Recover partial-circle witnesses left after existing line/circle owners.

    This is intentionally a narrow handoff detector for source-supported
    residual arcs.  It removes the already-owned LINE/CIRCLE geometry from the
    existing Canny edge map, fits only connected residual components, and
    returns the components that satisfy the established support/span contract.
    It does not alter the LINE/CIRCLE detectors or their presets.
    """
    edges = cv2.Canny(_preprocess(image_bgr), 50, 150)
    residual = (edges > 0).astype(np.uint8)
    owned = np.zeros_like(residual)
    for line in lines:
        cv2.line(
            owned,
            (round(line.p1_px[0]), round(line.p1_px[1])),
            (round(line.p2_px[0]), round(line.p2_px[1])),
            255,
            3,
        )
    for circle in circles:
        cv2.circle(
            owned,
            (round(circle.center_px[0]), round(circle.center_px[1])),
            round(circle.radius_px),
            255,
            3,
        )
    residual[owned > 0] = 0

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        residual, connectivity=8
    )
    arcs: List[RawArc] = []
    for label in range(1, component_count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < 100:
            continue
        points = np.column_stack(np.where(labels == label))[:, ::-1]
        fit = _fit_circle(points)
        if fit is None:
            continue
        center_x, center_y, radius, residuals = fit
        if not 20.0 <= radius <= 130.0:
            continue
        support = float(np.mean(residuals <= 3.0))
        if support < 0.5 or float(np.median(residuals)) > 3.0:
            continue
        start, end, span = _arc_angle_interval(points, center_x, center_y)
        if span < 60.0:
            continue
        x0 = float(stats[label, cv2.CC_STAT_LEFT])
        y0 = float(stats[label, cv2.CC_STAT_TOP])
        x1 = x0 + float(stats[label, cv2.CC_STAT_WIDTH])
        y1 = y0 + float(stats[label, cv2.CC_STAT_HEIGHT])
        arcs.append(
            RawArc(
                id=new_id("rawarc"),
                center_px=(center_x, center_y),
                radius_px=radius,
                start_angle_deg=start,
                end_angle_deg=end,
                confidence=min(1.0, support),
                bbox_px=(x0, y0, x1, y1),
            )
        )
    return arcs


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
    lines = extract_lines(image_bgr, **line_kwargs)
    circles = extract_circles(image_bgr, **circle_kwargs)
    return RawGeometry(
        lines=lines,
        circles=circles,
        arcs=_extract_arcs(image_bgr, lines, circles),
    )
