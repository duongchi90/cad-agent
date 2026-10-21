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
from typing import List, Optional, Tuple

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


def _split_line_at_source_gaps(
    source_gray: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> List[Tuple[int, int, int, int]]:
    """Keep Hough output from spanning intervals with no dark source pixels."""
    dx = float(x2 - x1)
    dy = float(y2 - y1)
    length = float(np.hypot(dx, dy))
    if length == 0:
        return [(x1, y1, x2, y2)]

    sample_count = max(1, int(np.ceil(length)))
    distances = np.linspace(0.0, length, sample_count + 1)
    xs = np.rint(x1 + dx * distances / length).astype(int)
    ys = np.rint(y1 + dy * distances / length).astype(int)

    # A supported point needs a dark transverse ridge, not merely pixels below
    # an absolute brightness cutoff. The candidate may lie on either edge of
    # the physical stroke, so probe nearby centers and require brighter flanks.
    # At an image border, two in-bounds probes on the surviving side are needed;
    # off-image samples never count as support.
    normal_x = -dy / length
    normal_y = dx / length
    offsets = np.arange(-4, 5, dtype=np.float64)
    probe_x = np.rint(xs[:, None] + normal_x * offsets[None, :]).astype(int)
    probe_y = np.rint(ys[:, None] + normal_y * offsets[None, :]).astype(int)
    inside = (
        (probe_x >= 0)
        & (probe_x < source_gray.shape[1])
        & (probe_y >= 0)
        & (probe_y < source_gray.shape[0])
    )
    sampled_gray = source_gray[
        np.clip(probe_y, 0, source_gray.shape[0] - 1),
        np.clip(probe_x, 0, source_gray.shape[1] - 1),
    ]
    supported = np.zeros(xs.shape, dtype=bool)
    for center_index in (3, 4, 5):
        center = sampled_gray[:, center_index]
        left_near_index = center_index - 3
        left_far_index = center_index - 4
        right_near_index = center_index + 3
        right_far_index = center_index + 4
        left_available = (
            inside[:, left_near_index] & inside[:, left_far_index]
            if left_far_index >= 0
            else np.zeros(xs.shape, dtype=bool)
        )
        right_available = (
            inside[:, right_near_index] & inside[:, right_far_index]
            if right_far_index < inside.shape[1]
            else np.zeros(xs.shape, dtype=bool)
        )
        center_gray = center.astype(np.int16)
        left_near_dark = (
            sampled_gray[:, left_near_index].astype(np.int16) - center_gray >= 10
        )
        left_far_dark = (
            sampled_gray[:, max(left_far_index, 0)].astype(np.int16) - center_gray >= 10
        )
        right_near_dark = (
            sampled_gray[:, right_near_index].astype(np.int16) - center_gray >= 10
        )
        right_far_dark = (
            sampled_gray[:, min(right_far_index, inside.shape[1] - 1)].astype(np.int16)
            - center_gray
            >= 10
        )
        two_sided_ridge = (
            left_available
            & right_available
            & left_near_dark
            & right_near_dark
        )
        one_sided_border_ridge = (
            left_available
            & ~right_available
            & left_near_dark
            & left_far_dark
        ) | (
            right_available
            & ~left_available
            & right_near_dark
            & right_far_dark
        )
        supported |= (
            inside[:, center_index]
            & (two_sided_ridge | one_sided_border_ridge)
        )

    transitions = np.diff(np.r_[False, supported, False].astype(np.int8))
    starts = np.flatnonzero(transitions == 1)
    ends = np.flatnonzero(transitions == -1) - 1
    if len(starts) < 2:
        return [(x1, y1, x2, y2)]

    gap_lengths = starts[1:] - ends[:-1] - 1
    if not np.any(gap_lengths >= 2):
        return [(x1, y1, x2, y2)]

    return [
        (int(xs[start]), int(ys[start]), int(xs[end]), int(ys[end]))
        for start, end in zip(starts, ends)
    ]


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
    source_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
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

    hough_lengths = [
        float(np.hypot(x2 - x1, y2 - y1))
        for x1, y1, x2, y2 in seg
    ]
    max_hough_len = max(hough_lengths) if hough_lengths else 1.0
    source_intervals = [
        (interval, hough_length)
        for (x1, y1, x2, y2), hough_length in zip(seg, hough_lengths)
        for interval in _split_line_at_source_gaps(
            source_gray, int(x1), int(y1), int(x2), int(y2)
        )
        if interval[:2] != interval[2:]
    ]

    # Confidence describes the Hough candidate, so splitting its geometry at
    # source gaps must not change its score or renormalize unrelated lines.
    for (x1, y1, x2, y2), hough_length in source_intervals:
        confidence = min(1.0, 0.5 + 0.5 * (hough_length / max_hough_len))
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


_LARGE_CIRCLE_WORK_MAX_SIDE_PX = 1200
_LARGE_CIRCLE_RADIUS_BAND_RATIO = 1.25


def _circle_has_distributed_source_support(
    source_gray: np.ndarray,
    center_x: float,
    center_y: float,
    radius: float,
) -> bool:
    """Require a dark ridge around nearly the whole proposed circumference."""
    if radius <= 0:
        return False

    sample_count = max(180, int(np.ceil(2.0 * np.pi * radius / 3.0)))
    angles = np.linspace(0.0, 2.0 * np.pi, sample_count, endpoint=False)
    radial_offsets = np.arange(-7, 8, dtype=np.float64)
    sample_radii = radius + radial_offsets[None, :]
    xs = np.rint(center_x + np.cos(angles)[:, None] * sample_radii).astype(int)
    ys = np.rint(center_y + np.sin(angles)[:, None] * sample_radii).astype(int)

    inside = (
        (xs >= 0)
        & (xs < source_gray.shape[1])
        & (ys >= 0)
        & (ys < source_gray.shape[0])
    )
    sampled = source_gray[
        np.clip(ys, 0, source_gray.shape[0] - 1),
        np.clip(xs, 0, source_gray.shape[1] - 1),
    ].astype(np.int16)

    supported = np.zeros(sample_count, dtype=bool)
    for center_index in range(4, 11):
        left_index = center_index - 4
        right_index = center_index + 4
        supported |= (
            inside[:, center_index]
            & inside[:, left_index]
            & inside[:, right_index]
            & (sampled[:, left_index] - sampled[:, center_index] >= 10)
            & (sampled[:, right_index] - sampled[:, center_index] >= 10)
        )

    if float(np.mean(supported)) < 0.90:
        return False

    # Overall coverage and fixed sectors can hide a short, contiguous opening.
    # Permit only a small raster-sampling gap; a visible 5-degree opening must
    # not be promoted to a complete circle by this supplemental path.
    first_supported = int(np.flatnonzero(supported)[0])
    unsupported = np.roll(~supported, -first_supported)
    transitions = np.diff(np.r_[False, unsupported, False].astype(np.int8))
    gap_starts = np.flatnonzero(transitions == 1)
    gap_ends = np.flatnonzero(transitions == -1)
    largest_gap = int(np.max(gap_ends - gap_starts)) if gap_starts.size else 0
    max_sampling_gap = max(2, int(np.ceil(sample_count * 0.01)))
    if largest_gap > max_sampling_gap:
        return False

    return all(float(np.mean(section)) >= 0.70 for section in np.array_split(supported, 16))


def _extract_supplemental_large_circles(
    image_bgr: np.ndarray,
    circle_kwargs: dict,
) -> List[RawCircle]:
    """Find supported large circles on a bounded raster using narrow Hough bands."""
    height, width = image_bgr.shape[:2]
    scale = min(1.0, _LARGE_CIRCLE_WORK_MAX_SIDE_PX / float(max(height, width)))
    work_width = max(1, int(round(width * scale)))
    work_height = max(1, int(round(height * scale)))
    if (work_width, work_height) == (width, height):
        work_image = image_bgr
    else:
        work_image = cv2.resize(
            image_bgr, (work_width, work_height), interpolation=cv2.INTER_AREA
        )

    scale_x = work_width / float(width)
    scale_y = work_height / float(height)
    source_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    max_work_radius = min(work_width, work_height) // 2 - 2
    effective_max_radius = int(circle_kwargs.get("max_radius", 200))
    first_radius = max(1, int(np.floor(effective_max_radius * min(scale_x, scale_y))) + 1)
    if first_radius > max_work_radius:
        return []

    supplemental: List[RawCircle] = []
    band_min = first_radius
    param1 = int(circle_kwargs.get("param1", 100))
    param2 = int(circle_kwargs.get("param2", 30))

    while band_min <= max_work_radius:
        band_max = min(
            max_work_radius,
            max(band_min, int(np.floor(band_min * _LARGE_CIRCLE_RADIUS_BAND_RATIO))),
        )
        candidates = extract_circles(
            work_image,
            min_radius=band_min,
            max_radius=band_max,
            param1=param1,
            param2=param2,
            min_dist=1,
        )

        radius_scale = (scale_x + scale_y) / 2.0
        for candidate in candidates:
            center_x = candidate.center_px[0] / scale_x
            center_y = candidate.center_px[1] / scale_y
            radius = candidate.radius_px / radius_scale
            if not _circle_has_distributed_source_support(
                source_gray, center_x, center_y, radius
            ):
                continue

            duplicate = any(
                np.hypot(
                    center_x - existing.center_px[0],
                    center_y - existing.center_px[1],
                ) <= 8.0
                and abs(radius - existing.radius_px) <= 8.0
                for existing in supplemental
            )
            if duplicate:
                continue

            supplemental.append(RawCircle(
                id=candidate.id,
                center_px=(center_x, center_y),
                radius_px=radius,
                confidence=candidate.confidence,
                bbox_px=(
                    center_x - radius,
                    center_y - radius,
                    center_x + radius,
                    center_y + radius,
                ),
            ))

        band_min = band_max + 1

    return supplemental


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


def _polygon_winding_number(
    x: float, y: float, polygon: List[Tuple[float, float]]
) -> int:
    winding = 0
    for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1]):
        cross = (x1 - x0) * (y - y0) - (x - x0) * (y1 - y0)
        if (
            abs(cross) <= 1e-7
            and min(x0, x1) - 1e-7 <= x <= max(x0, x1) + 1e-7
            and min(y0, y1) - 1e-7 <= y <= max(y0, y1) + 1e-7
        ):
            return 1
        if y0 <= y < y1 and cross > 0:
            winding += 1
        elif y1 <= y < y0 and cross < 0:
            winding -= 1
    return winding


def _circle_perimeter_intersects_fill(
    center_x: float,
    center_y: float,
    radius: float,
    polygons: List[List[Tuple[float, float]]],
    *,
    even_odd: bool,
) -> bool:
    if radius <= 0 or not polygons:
        return False
    sample_count = max(72, min(4096, int(np.ceil(2.0 * np.pi * radius))))
    for angle in np.linspace(0.0, 2.0 * np.pi, sample_count, endpoint=False):
        x = center_x + radius * float(np.cos(angle))
        y = center_y + radius * float(np.sin(angle))
        windings = [_polygon_winding_number(x, y, polygon) for polygon in polygons]
        if even_odd:
            inside = sum(winding != 0 for winding in windings) % 2 == 1
        else:
            inside = sum(windings) != 0
        if inside:
            return True
    return False


def _suspect_region_intersects_circle(
    suspect: dict | Tuple[float, float, float, float],
    center_x: float,
    center_y: float,
    radius: float,
    tolerance: float,
) -> bool:
    if isinstance(suspect, dict):
        stroke_margin = max(0.0, float(suspect.get("stroke_radius_px") or 0.0))
        for x0, y0, x1, y1 in suspect.get("segments", []):
            dx = x1 - x0
            dy = y1 - y0
            length_squared = dx * dx + dy * dy
            fraction = 0.0 if length_squared <= 0.0 else min(
                1.0,
                max(0.0, ((center_x - x0) * dx + (center_y - y0) * dy) / length_squared),
            )
            nearest_x = x0 + fraction * dx
            nearest_y = y0 + fraction * dy
            min_distance = float(np.hypot(nearest_x - center_x, nearest_y - center_y))
            max_distance = max(
                float(np.hypot(x0 - center_x, y0 - center_y)),
                float(np.hypot(x1 - center_x, y1 - center_y)),
            )
            if (
                min_distance <= radius + tolerance + stroke_margin
                and max_distance >= radius - tolerance - stroke_margin
            ):
                return True

        fill_polygons = suspect.get("fill_polygons", [])
        if fill_polygons and _circle_perimeter_intersects_fill(
            center_x,
            center_y,
            radius,
            fill_polygons,
            even_odd=bool(suspect.get("fill_even_odd")),
        ):
            return True

        bounds = suspect.get("bounds")
        if bounds is None:
            return False
    else:
        bounds = suspect

    x0, y0, x1, y1 = bounds
    dx = max(x0 - center_x, 0.0, center_x - x1)
    dy = max(y0 - center_y, 0.0, center_y - y1)
    min_distance = float(np.hypot(dx, dy))
    max_distance = max(
        float(np.hypot(x - center_x, y - center_y))
        for x, y in ((x0, y0), (x0, y1), (x1, y1), (x1, y0))
    )
    return (
        min_distance <= radius + tolerance
        and max_distance >= radius - tolerance
    )


def extract_raw_geometry(
    image_bgr: np.ndarray,
    preset: str = "default",
    *,
    pdf_vector_circle_witnesses: Optional[List[Tuple[float, float, float]]] = None,
    pdf_vector_circle_suspect_regions: Optional[List[dict | Tuple[float, float, float, float]]] = None,
    require_pdf_vector_circle_witness: bool = False,
    **kwargs,
) -> RawGeometry:
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
    circles = extract_circles(image_bgr, **circle_kwargs)
    if (
        preset == "real_scan_tuned_v1"
        and "min_radius" not in kwargs
        and "max_radius" not in kwargs
    ):
        supplemental = _extract_supplemental_large_circles(image_bgr, circle_kwargs)
        for candidate in supplemental:
            duplicate = any(
                np.hypot(
                    candidate.center_px[0] - existing.center_px[0],
                    candidate.center_px[1] - existing.center_px[1],
                ) <= 8.0
                and abs(candidate.radius_px - existing.radius_px) <= 8.0
                for existing in circles
            )
            if not duplicate:
                circles.append(candidate)

    if (
        require_pdf_vector_circle_witness
        or pdf_vector_circle_witnesses
        or pdf_vector_circle_suspect_regions
    ):
        witnesses = pdf_vector_circle_witnesses or []
        suspect_regions = pdf_vector_circle_suspect_regions or []
        candidate_matches: list[list[int]] = []
        candidate_has_suspect_region: list[bool] = []
        witness_match_counts = [0] * len(witnesses)
        for candidate in circles:
            matches = []
            center_x, center_y = candidate.center_px
            radius = candidate.radius_px
            suspect_tolerance = max(4.0, radius * 0.01)
            has_suspect_region = False
            for suspect in suspect_regions:
                if _suspect_region_intersects_circle(
                    suspect, center_x, center_y, radius, suspect_tolerance
                ):
                    has_suspect_region = True
                    break
            for index, (witness_x, witness_y, witness_radius) in enumerate(witnesses):
                tolerance = max(4.0, witness_radius * 0.01)
                center_error = float(np.hypot(
                    candidate.center_px[0] - witness_x,
                    candidate.center_px[1] - witness_y,
                ))
                if (
                    center_error <= tolerance
                    and abs(candidate.radius_px - witness_radius) <= tolerance
                ):
                    matches.append(index)
                    witness_match_counts[index] += 1
            candidate_matches.append(matches)
            candidate_has_suspect_region.append(has_suspect_region)

        circles = [
            candidate
            for candidate, matches, has_suspect_region in zip(
                circles, candidate_matches, candidate_has_suspect_region
            )
            if (
                len(matches) == 1 and witness_match_counts[matches[0]] == 1
            ) or (
                not require_pdf_vector_circle_witness
                and not has_suspect_region
                and not matches
            )
        ]

    return RawGeometry(
        lines=extract_lines(image_bgr, **line_kwargs),
        circles=circles,
    )
