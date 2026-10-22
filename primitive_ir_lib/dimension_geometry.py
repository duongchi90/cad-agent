"""Deterministic dimension-line and extension-line evidence detection."""

from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np

Point = tuple[float, float]
Segment = tuple[Point, Point]


@dataclass(frozen=True)
class DimensionGeometryEvidence:
    dimension_line: Segment | None
    extension_lines: tuple[Segment, ...]
    arrow_points: tuple[Point, ...]
    leader_lines: tuple[Segment, ...]
    kind_hint: str | None
    confidence: float


def _point(value: tuple[int, int] | np.ndarray) -> Point:
    return (float(value[0]), float(value[1]))


def _canonical_segment(first: Point, second: Point) -> Segment:
    return (first, second) if first <= second else (second, first)


def _length(segment: Segment) -> float:
    (x0, y0), (x1, y1) = segment
    return math.hypot(x1 - x0, y1 - y0)


def _is_horizontal(segment: Segment, tolerance: float = 3.0) -> bool:
    return abs(segment[1][1] - segment[0][1]) <= tolerance


def _is_vertical(segment: Segment, tolerance: float = 3.0) -> bool:
    return abs(segment[1][0] - segment[0][0]) <= tolerance


def _is_diagonal(segment: Segment) -> bool:
    dx = abs(segment[1][0] - segment[0][0])
    dy = abs(segment[1][1] - segment[0][1])
    if dx == 0.0 or dy == 0.0:
        return False
    angle = math.degrees(math.atan2(dy, dx))
    return 15.0 <= angle <= 75.0


def _endpoint_distance(first: Segment, second: Segment) -> float:
    return min(
        math.hypot(first_point[0] - second_point[0], first_point[1] - second_point[1])
        for first_point in first
        for second_point in second
    )


def _has_leader_marker(candidate: Segment, segments: list[Segment]) -> bool:
    for marker in segments:
        if marker == candidate or not _is_diagonal(marker):
            continue
        marker_length = _length(marker)
        if 18.0 <= marker_length <= 55.0 and _endpoint_distance(candidate, marker) <= 8.0:
            return True
    return False


def _detect_leader_lines(segments: list[Segment]) -> tuple[Segment, ...]:
    diagonal_segments = [segment for segment in segments if _is_diagonal(segment)]
    leaders: list[Segment] = []
    for candidate in sorted(diagonal_segments, key=lambda item: (-_length(item), item)):
        if any(_endpoint_distance(candidate, existing) <= 24.0 for existing in leaders):
            continue
        if _has_leader_marker(candidate, diagonal_segments):
            leaders.append(candidate)
    return tuple(leaders)


def _hough_segments(binary: np.ndarray) -> list[Segment]:
    edges = cv2.Canny(binary, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180.0,
        threshold=20,
        minLineLength=18,
        maxLineGap=6,
    )
    if lines is None:
        return []
    segments: list[Segment] = []
    for raw in np.asarray(lines).reshape(-1, 4):
        segment = _canonical_segment(_point(raw[:2]), _point(raw[2:]))
        if _length(segment) >= 18.0:
            segments.append(segment)
    return segments


def _segment_bbox(segment: Segment, *, padding: int = 18) -> tuple[int, int, int, int]:
    xs = (segment[0][0], segment[1][0])
    ys = (segment[0][1], segment[1][1])
    return (
        int(math.floor(min(xs))) - padding,
        int(math.floor(min(ys))) - padding,
        int(math.ceil(max(xs))) + padding,
        int(math.ceil(max(ys))) + padding,
    )


def _boxes_near(first: tuple[int, int, int, int], second: tuple[int, int, int, int], *, tolerance: int) -> bool:
    return not (
        first[2] < second[0] - tolerance
        or second[2] < first[0] - tolerance
        or first[3] < second[1] - tolerance
        or second[3] < first[1] - tolerance
    )


def _merge_nearby_boxes(
    boxes: list[tuple[int, int, int, int]], *, tolerance: int
) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []
    for candidate in sorted(boxes, key=lambda box: (box[1], box[0], box[3], box[2])):
        current = candidate
        changed = True
        while changed:
            changed = False
            for index, existing in enumerate(merged):
                if not _boxes_near(existing, current, tolerance=tolerance):
                    continue
                current = (
                    min(existing[0], current[0]),
                    min(existing[1], current[1]),
                    max(existing[2], current[2]),
                    max(existing[3], current[3]),
                )
                merged.pop(index)
                changed = True
                break
        merged.append(current)
    return sorted(merged, key=lambda box: (box[1], box[0], box[3], box[2]))


def _select_dimension_line(segments: list[Segment]) -> tuple[Segment | None, str | None]:
    horizontal = [segment for segment in segments if _is_horizontal(segment)]
    vertical = [segment for segment in segments if _is_vertical(segment)]
    candidates = [*horizontal, *vertical]
    if not candidates:
        return None, None

    best = max(candidates, key=lambda segment: (_length(segment), segment))
    if _is_horizontal(best):
        return best, "HORIZONTAL_DISTANCE"
    if _is_vertical(best):
        return best, "VERTICAL_DISTANCE"
    return best, "ALIGNED_DISTANCE"


def _merge_axis_segments(
    segments: list[Segment], *, axis: str, coordinate: float, tolerance: float = 6.0
) -> Segment | None:
    matching: list[Segment] = []
    for segment in segments:
        if axis == "vertical":
            if not _is_vertical(segment) or abs(segment[0][0] - coordinate) > tolerance:
                continue
        else:
            if not _is_horizontal(segment) or abs(segment[0][1] - coordinate) > tolerance:
                continue
        matching.append(segment)
    if not matching:
        return None

    if axis == "vertical":
        x = sum((segment[0][0] + segment[1][0]) / 2.0 for segment in matching) / len(matching)
        low = min(min(segment[0][1], segment[1][1]) for segment in matching)
        high = max(max(segment[0][1], segment[1][1]) for segment in matching)
        return _canonical_segment((x, low), (x, high))
    y = sum((segment[0][1] + segment[1][1]) / 2.0 for segment in matching) / len(matching)
    low = min(min(segment[0][0], segment[1][0]) for segment in matching)
    high = max(max(segment[0][0], segment[1][0]) for segment in matching)
    return _canonical_segment((low, y), (high, y))


def _detect_extension_lines(segments: list[Segment], dimension_line: Segment) -> tuple[Segment, ...]:
    if _is_horizontal(dimension_line):
        y = dimension_line[0][1]
        endpoints = (dimension_line[0][0], dimension_line[1][0])
        candidates: list[Segment] = []
        for endpoint in endpoints:
            vertical = _merge_axis_segments(segments, axis="vertical", coordinate=endpoint, tolerance=28.0)
            if vertical is None or _length(vertical) < 28.0:
                continue
            if min(vertical[0][1], vertical[1][1]) <= y + 8.0 and max(vertical[0][1], vertical[1][1]) >= y + 24.0:
                candidates.append(vertical)
        return tuple(sorted(candidates, key=lambda item: (item[0][0], item[0][1], item[1][1])))

    x = dimension_line[0][0]
    endpoints = (dimension_line[0][1], dimension_line[1][1])
    candidates = []
    for endpoint in endpoints:
        horizontal = _merge_axis_segments(segments, axis="horizontal", coordinate=endpoint, tolerance=28.0)
        if horizontal is None or _length(horizontal) < 28.0:
            continue
        if min(horizontal[0][0], horizontal[1][0]) <= x - 24.0 and max(horizontal[0][0], horizontal[1][0]) >= x - 8.0:
            candidates.append(horizontal)
    return tuple(sorted(candidates, key=lambda item: (item[0][1], item[0][0], item[1][0])))


def _contour_arrow_points(binary: np.ndarray, dimension_line: Segment) -> list[Point]:
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    endpoints = [dimension_line[0], dimension_line[1]]
    found: list[tuple[float, Point]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if not 12.0 <= area <= 500.0:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        approximation = cv2.approxPolyDP(contour, 0.08 * perimeter, True)
        if not 3 <= len(approximation) <= 5:
            continue
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        center = (moments["m10"] / moments["m00"], moments["m01"] / moments["m00"])
        distance = min(math.hypot(center[0] - x, center[1] - y) for x, y in endpoints)
        if distance <= 24.0:
            found.append((distance, (float(center[0]), float(center[1]))))
    found.sort(key=lambda item: (item[0], item[1]))
    points: list[Point] = []
    for _, point in found:
        if all(math.hypot(point[0] - other[0], point[1] - other[1]) > 5.0 for other in points):
            points.append(point)
    return points[:2]


def _endpoint_arrow_points(binary: np.ndarray, dimension_line: Segment) -> tuple[Point, ...]:
    height, width = binary.shape[:2]
    points: list[Point] = []
    for x, y in dimension_line:
        x0, y0 = max(0, int(x) - 9), max(0, int(y) - 9)
        x1, y1 = min(width, int(x) + 10), min(height, int(y) + 10)
        patch = binary[y0:y1, x0:x1]
        if patch.size and int(np.count_nonzero(patch)) >= 15:
            points.append((float(x), float(y)))
    return tuple(points)


def _axis_interval(binary: np.ndarray, dimension_line: Segment) -> tuple[int, int] | None:
    """Measure the shaft's transverse dark-pixel interval away from its ends."""
    first, second = dimension_line
    vertical = _is_vertical(dimension_line)
    axis = int(round((first[0] + second[0]) / 2.0 if vertical else (first[1] + second[1]) / 2.0))
    start = int(round((first[1] + second[1]) / 2.0 if vertical else (first[0] + second[0]) / 2.0))
    profile = binary[start, :] if vertical else binary[:, start]
    indices = np.flatnonzero(profile > 0)
    runs = [run for run in np.split(indices, np.where(np.diff(indices) > 1)[0] + 1) if len(run)]
    ranked = sorted(
        runs,
        key=lambda run: (
            max(int(run[0]) - axis, axis - int(run[-1]), 0),
            int(run[0]),
            int(run[-1]),
        ),
    )
    if not ranked:
        return None
    nearest_gap = max(int(ranked[0][0]) - axis, axis - int(ranked[0][-1]), 0)
    if len(ranked) > 1:
        second_gap = max(int(ranked[1][0]) - axis, axis - int(ranked[1][-1]), 0)
        if second_gap == nearest_gap:
            return None
    return int(ranked[0][0]), int(ranked[0][-1])


def _endpoint_flank_witnesses(binary: np.ndarray, dimension_line: Segment) -> tuple[Point, ...]:
    """Find a unique pair of source-pixel flanks tapering away from a shaft.

    Profile widths, axial reach, and transverse alignment are measured from the
    raster and the candidate shaft. No case coordinates or fixed acceptance
    distances are used.
    """
    if not (_is_horizontal(dimension_line) or _is_vertical(dimension_line)):
        return ()
    shaft_interval = _axis_interval(binary, dimension_line)
    if shaft_interval is None:
        return ()
    shaft_width = shaft_interval[1] - shaft_interval[0] + 1
    height, width = binary.shape[:2]
    vertical = _is_vertical(dimension_line)
    endpoints = (
        tuple(sorted(dimension_line, key=lambda point: (point[1], point[0])))
        if vertical
        else dimension_line
    )
    points: list[Point] = []
    endpoint_intervals: list[tuple[int, int]] = []

    for endpoint_index, endpoint in enumerate(endpoints):
        outward = -1 if endpoint_index == 0 else 1
        axial_endpoint = int(round(endpoint[1] if vertical else endpoint[0]))
        limit = height if vertical else width
        witnesses: list[tuple[tuple[int, int], int, int]] = []
        for direction in (outward, -outward):
            widths: list[int] = []
            intervals: list[tuple[int, int]] = []
            positions: list[int] = []
            started = False
            for distance in range(1, limit + 1):
                position = axial_endpoint + direction * distance
                if not 0 <= position < limit:
                    break
                profile = binary[position, :] if vertical else binary[:, position]
                indices = np.flatnonzero(profile > 0)
                runs = [run for run in np.split(indices, np.where(np.diff(indices) > 1)[0] + 1) if len(run)]
                matching = [
                    run for run in runs
                    if int(run[0]) <= shaft_interval[1] and int(run[-1]) >= shaft_interval[0]
                ]
                if len(matching) != 1:
                    if started:
                        break
                    continue
                run = matching[0]
                interval = (int(run[0]), int(run[-1]))
                if not (interval[0] < shaft_interval[0] and interval[1] > shaft_interval[1]):
                    if started:
                        break
                    continue
                started = True
                widths.append(interval[1] - interval[0] + 1)
                intervals.append(interval)
                positions.append(position)

            valid_profiles: list[tuple[int, int, tuple[int, int], int]] = []
            for start_index in range(len(widths) - 1):
                profile_widths = widths[start_index:]
                if direction == outward:
                    monotonic = all(a >= b for a, b in zip(profile_widths, profile_widths[1:]))
                    contraction = profile_widths[0] - profile_widths[-1]
                else:
                    monotonic = all(a <= b for a, b in zip(profile_widths, profile_widths[1:]))
                    contraction = profile_widths[-1] - profile_widths[0]
                axial_reach = abs(positions[-1] - positions[start_index]) + 1
                initial_gap = abs(positions[start_index] - axial_endpoint)
                if monotonic and contraction > shaft_width and initial_gap <= axial_reach:
                    point_position = positions[-1] if direction == outward else axial_endpoint
                    valid_profiles.append(
                        (len(profile_widths), start_index, intervals[start_index], point_position)
                    )
            if valid_profiles:
                longest = max(profile[0] for profile in valid_profiles)
                best_profiles = [profile for profile in valid_profiles if profile[0] == longest]
                if len(best_profiles) == 1:
                    _, _, first_interval, point_position = best_profiles[0]
                    witnesses.append((first_interval, point_position, direction))

        if len(witnesses) != 1:
            continue
        interval, point_position, _ = witnesses[0]
        endpoint_intervals.append(interval)
        transverse_center = (interval[0] + interval[1]) / 2.0
        points.append(
            (transverse_center, float(point_position))
            if vertical
            else (float(point_position), transverse_center)
        )

    if len(points) != 2 or len(endpoint_intervals) != 2:
        return ()
    common_low = max(endpoint_intervals[0][0], endpoint_intervals[1][0])
    common_high = min(endpoint_intervals[0][1], endpoint_intervals[1][1])
    if common_low > shaft_interval[0] or common_high < shaft_interval[1]:
        return ()
    return tuple(points)


def detect_dimension_geometry(crop_bgr: np.ndarray) -> DimensionGeometryEvidence:
    """Detect controlled line/arrow evidence without scale or attachments."""
    if not isinstance(crop_bgr, np.ndarray) or crop_bgr.ndim not in {2, 3}:
        raise ValueError("crop_bgr must be a grayscale or BGR image")
    gray = crop_bgr if crop_bgr.ndim == 2 else cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    if gray.size == 0 or int(gray.max()) == int(gray.min()):
        return DimensionGeometryEvidence(None, (), (), (), None, 0.0)

    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        25,
        10,
    )
    segments = _hough_segments(binary)
    leader_lines = _detect_leader_lines(segments)
    dimension_line, kind_hint = _select_dimension_line(segments)
    if dimension_line is None:
        return DimensionGeometryEvidence(
            None,
            (),
            (),
            leader_lines,
            "LEADER_ANNOTATION" if leader_lines else None,
            min(1.0, 0.35 + (0.25 if leader_lines else 0.0)),
        )

    extension_lines = _detect_extension_lines(segments, dimension_line)
    if _is_horizontal(dimension_line) and len(extension_lines) >= 2:
        y = dimension_line[0][1]
        dimension_line = _canonical_segment(
            (extension_lines[0][0][0], y),
            (extension_lines[-1][0][0], y),
        )
    elif _is_vertical(dimension_line) and len(extension_lines) >= 2:
        x = dimension_line[0][0]
        dimension_line = _canonical_segment(
            (x, extension_lines[0][0][1]),
            (x, extension_lines[-1][0][1]),
        )
    arrow_points = _contour_arrow_points(binary, dimension_line)
    if len(arrow_points) < 2:
        arrow_points = list(_endpoint_flank_witnesses(binary, dimension_line))
    if len(arrow_points) < 2:
        arrow_points = list(_endpoint_arrow_points(binary, dimension_line))
    arrow_points = tuple(sorted(arrow_points, key=lambda point: (point[0], point[1])))
    confidence = min(
        1.0,
        0.35
        + (0.25 if len(extension_lines) >= 2 else 0.12 if extension_lines else 0.0)
        + (0.25 if len(arrow_points) >= 2 else 0.12 if arrow_points else 0.0)
        + (0.10 if leader_lines else 0.0),
    )
    return DimensionGeometryEvidence(
        dimension_line=dimension_line,
        extension_lines=extension_lines,
        arrow_points=arrow_points,
        leader_lines=leader_lines,
        kind_hint=kind_hint,
        confidence=confidence,
    )


def detect_dimension_geometry_regions(image_bgr: np.ndarray) -> tuple[tuple[int, int, int, int], ...]:
    """Return deterministic page regions containing independent dimension geometry."""
    if not isinstance(image_bgr, np.ndarray) or image_bgr.ndim not in {2, 3}:
        raise ValueError("image_bgr must be a grayscale or BGR image")
    if image_bgr.size == 0:
        return ()

    gray = image_bgr if image_bgr.ndim == 2 else cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    if gray.size == 0 or int(gray.max()) == int(gray.min()):
        return ()
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        25,
        10,
    )
    structural_segments = [
        segment
        for segment in _hough_segments(binary)
        if (_is_horizontal(segment) or _is_vertical(segment)) and _length(segment) >= 40.0
    ]
    height, width = gray.shape[:2]
    regions: list[tuple[int, int, int, int]] = []
    # Evaluate each structural segment in its own locally padded box. Merging
    # all page segments first can create a near-page ROI from unrelated lines.
    for segment in structural_segments:
        left, top, right, bottom = _segment_bbox(segment)
        clipped = (
            max(0, left),
            max(0, top),
            min(width, right),
            min(height, bottom),
        )
        if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
            continue
        crop = image_bgr[clipped[1] : clipped[3], clipped[0] : clipped[2]]
        geometry = detect_dimension_geometry(crop)
        if geometry.dimension_line is None:
            continue
        crop_gray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        crop_binary = cv2.adaptiveThreshold(
            crop_gray,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV,
            25,
            10,
        )
        has_extensions = len(geometry.extension_lines) >= 2
        has_flank_pair = len(
            _endpoint_flank_witnesses(crop_binary, geometry.dimension_line)
        ) == 2
        if not has_extensions and not has_flank_pair:
            continue
        if clipped not in regions:
            regions.append(clipped)
    return tuple(sorted(regions, key=lambda box: (box[1], box[0], box[3], box[2])))


__all__ = [
    "DimensionGeometryEvidence",
    "Point",
    "Segment",
    "detect_dimension_geometry",
    "detect_dimension_geometry_regions",
]
