"""
dimension_geometry_engine.py — Reference Engine for Dimension Geometry Strategies A, B, C, D.

Empirically benchmarks and compares dimension line, extension line, and arrowhead extraction algorithms:
- Strategy A: Current Production Main (primitive_ir_lib/dimension_geometry.py)
- Strategy B: Naive Bidirectional Extension (two-way check, but flawed dimension line selection)
- Strategy C: Orthogonal Pair Matching (ranks dimension line by orthogonal extension count, H/V only)
- Strategy D: Dimension Topology Oracle (Bidirectional extension, collinear gap bridging, hatch rejection, inward/outward arrows)
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Sequence, Dict, Any

_repo_root = str(Path(__file__).resolve().parents[4])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import cv2
import numpy as np

from primitive_ir_lib.dimension_geometry import (
    DimensionGeometryEvidence,
    detect_dimension_geometry,
    _hough_segments,
    _point,
    _canonical_segment,
    _length,
    _is_horizontal,
    _is_vertical,
    _is_diagonal,
    _merge_axis_segments,
    _detect_leader_lines,
    _contour_arrow_points,
    _endpoint_arrow_points,
    _select_dimension_line,
)

Point = Tuple[float, float]
Segment = Tuple[Point, Point]


@dataclass(frozen=True)
class RobustDimensionEvidence:
    dimension_line: Optional[Segment]
    extension_lines: Tuple[Segment, ...]
    arrow_points: Tuple[Point, ...]
    arrow_orientation: str  # "INWARD", "OUTWARD", "NONE"
    leader_lines: Tuple[Segment, ...]
    kind_hint: Optional[str]  # "HORIZONTAL_DISTANCE", "VERTICAL_DISTANCE", "ALIGNED_DISTANCE", "LEADER_ANNOTATION"
    confidence: float


# ---------------------------------------------------------------------------
# Helper Geometry Functions
# ---------------------------------------------------------------------------

def segment_angle_deg(seg: Segment) -> float:
    (x0, y0), (x1, y1) = seg
    dx, dy = x1 - x0, y1 - y0
    if dx == 0.0 and dy == 0.0:
        return 0.0
    return math.degrees(math.atan2(dy, dx)) % 180.0


def angle_diff_deg(a: float, b: float) -> float:
    diff = abs(a - b) % 180.0
    return min(diff, 180.0 - diff)


# ---------------------------------------------------------------------------
# Strategy A (Production Main)
# ---------------------------------------------------------------------------

def run_strategy_a(crop_bgr: np.ndarray) -> DimensionGeometryEvidence:
    """Strategy A: Current Production Main."""
    return detect_dimension_geometry(crop_bgr)


# ---------------------------------------------------------------------------
# Strategy B (Naive Bidirectional)
# ---------------------------------------------------------------------------

def _detect_extension_lines_bidirectional_naive(
    segments: list[Segment], dimension_line: Segment
) -> tuple[Segment, ...]:
    """Strategy B helper: Naive bidirectional check for H/V."""
    if _is_horizontal(dimension_line):
        y = dimension_line[0][1]
        endpoints = (dimension_line[0][0], dimension_line[1][0])
        candidates: list[Segment] = []
        for endpoint in endpoints:
            vertical = _merge_axis_segments(segments, axis="vertical", coordinate=endpoint, tolerance=28.0)
            if vertical is None or _length(vertical) < 28.0:
                continue
            y_min = min(vertical[0][1], vertical[1][1])
            y_max = max(vertical[0][1], vertical[1][1])
            if (y_min <= y + 8.0 and y_max >= y + 24.0) or (y_min <= y - 24.0 and y_max >= y - 8.0):
                candidates.append(vertical)
        return tuple(sorted(candidates, key=lambda item: (item[0][0], item[0][1], item[1][1])))

    x = dimension_line[0][0]
    endpoints = (dimension_line[0][1], dimension_line[1][1])
    candidates = []
    for endpoint in endpoints:
        horizontal = _merge_axis_segments(segments, axis="horizontal", coordinate=endpoint, tolerance=28.0)
        if horizontal is None or _length(horizontal) < 28.0:
            continue
        x_min = min(horizontal[0][0], horizontal[1][0])
        x_max = max(horizontal[0][0], horizontal[1][0])
        if (x_min <= x - 24.0 and x_max >= x - 8.0) or (x_min <= x + 8.0 and x_max >= x + 24.0):
            candidates.append(horizontal)
    return tuple(sorted(candidates, key=lambda item: (item[0][1], item[0][0], item[1][0])))


def run_strategy_b(crop_bgr: np.ndarray) -> DimensionGeometryEvidence:
    """Strategy B: Naive Bidirectional Extension (two-way check, but inherits Strategy A line selection bug)."""
    if not isinstance(crop_bgr, np.ndarray) or crop_bgr.ndim not in {2, 3}:
        raise ValueError("crop_bgr must be a grayscale or BGR image")
    gray = crop_bgr if crop_bgr.ndim == 2 else cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    if gray.size == 0 or int(gray.max()) == int(gray.min()):
        return DimensionGeometryEvidence(None, (), (), (), None, 0.0)

    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 10
    )
    segments = _hough_segments(binary)
    if not segments:
        return DimensionGeometryEvidence(None, (), (), (), None, 0.0)

    dimension_line, kind_hint = _select_dimension_line(segments)
    if dimension_line is None:
        leader_lines = tuple(_detect_leader_lines(segments))
        return DimensionGeometryEvidence(None, (), (), leader_lines, None, 0.0)

    extension_lines = _detect_extension_lines_bidirectional_naive(segments, dimension_line)
    arrow_points = _contour_arrow_points(binary, dimension_line)
    if len(arrow_points) < 2:
        arrow_points = list(_endpoint_arrow_points(binary, dimension_line))
    arrow_points = tuple(sorted(arrow_points, key=lambda point: (point[0], point[1])))
    leader_lines = tuple(_detect_leader_lines(segments))
    confidence = min(0.9, 0.45 + 0.2 * len(extension_lines) + 0.1 * len(arrow_points))

    return DimensionGeometryEvidence(
        dimension_line=dimension_line,
        extension_lines=extension_lines,
        arrow_points=arrow_points,
        leader_lines=leader_lines,
        kind_hint=kind_hint,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Strategy C (Orthogonal Pair Matching - H/V only)
# ---------------------------------------------------------------------------

def run_strategy_c(crop_bgr: np.ndarray) -> DimensionGeometryEvidence:
    """Strategy C: Orthogonal Pair Matching (H and V only, scores candidate by attached orthogonal extensions)."""
    if not isinstance(crop_bgr, np.ndarray) or crop_bgr.ndim not in {2, 3}:
        raise ValueError("crop_bgr must be a grayscale or BGR image")
    gray = crop_bgr if crop_bgr.ndim == 2 else cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    if gray.size == 0 or int(gray.max()) == int(gray.min()):
        return DimensionGeometryEvidence(None, (), (), (), None, 0.0)

    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 10
    )
    segments = _hough_segments(binary)
    if not segments:
        return DimensionGeometryEvidence(None, (), (), (), None, 0.0)

    h_segs = [s for s in segments if _is_horizontal(s)]
    v_segs = [s for s in segments if _is_vertical(s)]

    scored_candidates = []
    for h in h_segs:
        exts = _detect_extension_lines_bidirectional_naive(segments, h)
        scored_candidates.append((len(exts), _length(h), h, "HORIZONTAL_DISTANCE", exts))
    for v in v_segs:
        exts = _detect_extension_lines_bidirectional_naive(segments, v)
        scored_candidates.append((len(exts), _length(v), v, "VERTICAL_DISTANCE", exts))

    if not scored_candidates:
        leader_lines = tuple(_detect_leader_lines(segments))
        return DimensionGeometryEvidence(None, (), (), leader_lines, None, 0.0)

    scored_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best = scored_candidates[0]
    dimension_line = best[2]
    kind_hint = best[3]
    extension_lines = best[4]

    arrow_points = _contour_arrow_points(binary, dimension_line)
    if len(arrow_points) < 2:
        arrow_points = list(_endpoint_arrow_points(binary, dimension_line))
    arrow_points = tuple(sorted(arrow_points, key=lambda point: (point[0], point[1])))
    leader_lines = tuple(_detect_leader_lines(segments))
    confidence = min(0.9, 0.45 + 0.2 * len(extension_lines) + 0.1 * len(arrow_points))

    return DimensionGeometryEvidence(
        dimension_line=dimension_line,
        extension_lines=extension_lines,
        arrow_points=arrow_points,
        leader_lines=leader_lines,
        kind_hint=kind_hint,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Strategy D (Dimension Topology Oracle)
# ---------------------------------------------------------------------------

def _detect_arrow_evidence(
    binary: np.ndarray,
    dim_line: Segment,
    has_ext_mask: tuple[bool, bool] = (False, False),
    search_dist_px: float = 24.0,
) -> tuple[tuple[Point, ...], str]:
    """Detects arrowheads and determines INWARD vs OUTWARD orientation."""
    p1, p2 = dim_line
    length = _length(dim_line)
    if length <= 1e-3:
        return (), "NONE"

    dx = (p2[0] - p1[0]) / length
    dy = (p2[1] - p1[1]) / length

    # 1. Contour analysis for distinct arrowheads
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    matched_contours: list[tuple[Point, float]] = []

    for contour in contours:
        area = float(cv2.contourArea(contour))
        if not (12.0 <= area <= 600.0):
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        approx = cv2.approxPolyDP(contour, 0.08 * perimeter, True)
        if not (3 <= len(approx) <= 6):
            continue
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        cx = moments["m10"] / moments["m00"]
        cy = moments["m01"] / moments["m00"]

        d_p1 = math.hypot(cx - p1[0], cy - p1[1])
        d_p2 = math.hypot(cx - p2[0], cy - p2[1])
        min_d = min(d_p1, d_p2)

        if min_d <= search_dist_px:
            t = (cx - p1[0]) * dx + (cy - p1[1]) * dy
            matched_contours.append(((float(cx), float(cy)), t))

    unique_arrows: list[Point] = []
    t_coords: list[float] = []
    for pt, t in matched_contours:
        if all(math.hypot(pt[0] - other[0], pt[1] - other[1]) > 8.0 for other in unique_arrows):
            unique_arrows.append(pt)
            t_coords.append(t)

    # 2. Patch density fallback if contour didn't find both arrows
    h_img, w_img = binary.shape[:2]
    if len(unique_arrows) < 2:
        for i, ep in enumerate((p1, p2)):
            if any(math.hypot(ep[0] - a[0], ep[1] - a[1]) <= 15.0 for a in unique_arrows):
                continue
            ix, iy = int(round(ep[0])), int(round(ep[1]))
            patch = binary[max(0, iy - 9):min(h_img, iy + 10), max(0, ix - 9):min(w_img, ix + 10)]
            if patch.size:
                nz = int(np.count_nonzero(patch))
                thresh = 70 if has_ext_mask[i] else 45
                if nz >= thresh:
                    unique_arrows.append(ep)
                    t_ep = 0.0 if i == 0 else length
                    t_coords.append(t_ep)

    # 3. Check outward arrowheads outside endpoints
    if len(unique_arrows) < 2:
        for ep, d_sign, t_out in [(p1, -1.0, -12.0), (p2, 1.0, length + 12.0)]:
            ox = ep[0] + d_sign * dx * 12.0
            oy = ep[1] + d_sign * dy * 12.0
            oix, oiy = int(round(ox)), int(round(oy))
            opatch = binary[max(0, oiy - 9):min(h_img, oiy + 10), max(0, oix - 9):min(w_img, oix + 10)]
            if opatch.size and int(np.count_nonzero(opatch)) >= 45:
                if all(math.hypot(ox - other[0], oy - other[1]) > 8.0 for other in unique_arrows):
                    unique_arrows.append((ox, oy))
                    t_coords.append(t_out)

    if len(unique_arrows) < 2:
        return (), "NONE"

    if any(t < -2.0 or t > (length + 2.0) for t in t_coords) or length < 40.0:
        orientation = "OUTWARD"
    else:
        orientation = "INWARD"

    return tuple(unique_arrows[:2]), orientation


def _is_hatch_line(cand: Segment, all_segs: list[Segment], min_dist: float = 8.0, max_dist: float = 80.0) -> bool:
    (x1, y1), (x2, y2) = cand
    l1 = _length(cand)
    if l1 < 1e-3:
        return False
    ux, uy = (x2 - x1) / l1, (y2 - y1) / l1
    nx, ny = -uy, ux
    ang = segment_angle_deg(cand)
    spaced_count = 0
    for s in all_segs:
        if s == cand:
            continue
        if angle_diff_deg(segment_angle_deg(s), ang) <= 4.0:
            (sx1, sy1), (sx2, sy2) = s
            d1 = abs((sx1 - x1) * nx + (sy1 - y1) * ny)
            d2 = abs((sx2 - x1) * nx + (sy2 - y1) * ny)
            d_mid = (d1 + d2) / 2.0
            if min_dist <= d_mid <= max_dist:
                spaced_count += 1
    return spaced_count >= 4


def _merge_collinear_candidates(segs: list[Segment], gap_tol_px: float = 120.0) -> list[Segment]:
    if not segs:
        return []
    merged = list(segs)
    changed = True
    while changed:
        changed = False
        for i in range(len(merged)):
            for j in range(i + 1, len(merged)):
                s1, s2 = merged[i], merged[j]
                a1, a2 = segment_angle_deg(s1), segment_angle_deg(s2)
                if angle_diff_deg(a1, a2) > 3.0:
                    continue
                (x1, y1), (x2, y2) = s1
                l1 = _length(s1)
                if l1 < 1e-3:
                    continue
                ux, uy = (x2 - x1) / l1, (y2 - y1) / l1
                nx, ny = -uy, ux
                (x3, y3), (x4, y4) = s2
                d_perp1 = abs((x3 - x1) * nx + (y3 - y1) * ny)
                d_perp2 = abs((x4 - x1) * nx + (y4 - y1) * ny)
                if max(d_perp1, d_perp2) > 3.0:
                    continue
                t1 = 0.0
                t2 = l1
                t3 = (x3 - x1) * ux + (y3 - y1) * uy
                t4 = (x4 - x1) * ux + (y4 - y1) * uy
                low = min(t1, t2, t3, t4)
                high = max(t1, t2, t3, t4)
                span = high - low
                total_len = l1 + _length(s2)
                gap = span - total_len
                if gap <= gap_tol_px:
                    p_start = (x1 + low * ux, y1 + low * uy)
                    p_end = (x1 + high * ux, y1 + high * uy)
                    merged[i] = _canonical_segment(p_start, p_end)
                    merged.pop(j)
                    changed = True
                    break
            if changed:
                break
    return merged


def run_strategy_d(
    crop_bgr: np.ndarray,
    min_line_len_px: float = 20.0,
    extension_perp_tol_px: float = 12.0,
) -> RobustDimensionEvidence:
    """Strategy D: Dimension Topology Oracle.

    1. Extracts segments via adaptive threshold and Hough.
    2. Identifies candidate dimension lines across horizontal, vertical, and aligned angles.
    3. Merges collinear segments across dimension text gaps.
    4. Rejects dense cross-hatching and periodic grids.
    5. Searches for orthogonal extension lines at both endpoints in BOTH positive and negative directions.
    6. Ranks candidate dimension lines by attached extension count and arrowhead evidence.
    7. Detects inward vs outward arrowheads and leader lines.
    """
    if not isinstance(crop_bgr, np.ndarray) or crop_bgr.ndim not in {2, 3}:
        raise ValueError("crop_bgr must be a grayscale or BGR image")
    gray = crop_bgr if crop_bgr.ndim == 2 else cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    if gray.size == 0 or int(gray.max()) == int(gray.min()):
        return RobustDimensionEvidence(None, (), (), "NONE", (), None, 0.0)

    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 10
    )
    segments = _hough_segments(binary)
    if not segments:
        return RobustDimensionEvidence(None, (), (), "NONE", (), None, 0.0)

    leader_lines = tuple(_detect_leader_lines(segments))

    # Categorize all segments
    h_segs = [s for s in segments if _is_horizontal(s, tolerance=4.0) and _length(s) >= min_line_len_px]
    v_segs = [s for s in segments if _is_vertical(s, tolerance=4.0) and _length(s) >= min_line_len_px]
    d_segs = [s for s in segments if not _is_horizontal(s, tolerance=4.0) and not _is_vertical(s, tolerance=4.0) and _length(s) >= min_line_len_px]

    # Include both unmerged segments and collinear merged spans
    h_candidates = list(dict.fromkeys(h_segs + _merge_collinear_candidates(h_segs)))
    v_candidates = list(dict.fromkeys(v_segs + _merge_collinear_candidates(v_segs)))
    d_candidates = list(dict.fromkeys(d_segs + _merge_collinear_candidates(d_segs)))


    candidate_results: List[Dict[str, Any]] = []

    def evaluate_candidate(dim_line: Segment, expected_axis: str) -> Optional[Dict[str, Any]]:
        if _is_hatch_line(dim_line, segments):
            return None

        p1, p2 = dim_line
        length = _length(dim_line)
        ang = segment_angle_deg(dim_line)
        dx, dy = (p2[0] - p1[0]) / length, (p2[1] - p1[1]) / length
        nx, ny = -dy, dx

        attached_extensions = []
        ext_found_mask = [False, False]
        for ep_idx, ep in enumerate((p1, p2)):
            best_ext = None
            best_ext_len = 0.0
            for seg in segments:
                if seg == dim_line:
                    continue
                seg_ang = segment_angle_deg(seg)
                rel_ang = angle_diff_deg(ang, seg_ang)
                if not (70.0 <= rel_ang <= 110.0):
                    continue

                (sx1, sy1), (sx2, sy2) = seg
                v1x, v1y = sx1 - ep[0], sy1 - ep[1]
                v2x, v2y = sx2 - ep[0], sy2 - ep[1]
                t1 = v1x * dx + v1y * dy
                t2 = v2x * dx + v2y * dy
                n1 = v1x * nx + v1y * ny
                n2 = v2x * nx + v2y * ny

                if max(abs(t1), abs(t2)) <= extension_perp_tol_px or (min(t1, t2) <= 0.0 and max(t1, t2) >= 0.0):
                    seg_len = _length(seg)
                    if max(abs(n1), abs(n2)) >= 15.0 and seg_len > best_ext_len:
                        best_ext = seg
                        best_ext_len = seg_len

            if best_ext is not None:
                attached_extensions.append(best_ext)
                ext_found_mask[ep_idx] = True

        arrows, arrow_mode = _detect_arrow_evidence(
            binary, dim_line, has_ext_mask=(ext_found_mask[0], ext_found_mask[1])
        )

        score = len(attached_extensions) * 100.0 + len(arrows) * 150.0 + length * 0.1
        return {
            "dim_line": dim_line,
            "extensions": tuple(attached_extensions),
            "arrows": arrows,
            "arrow_mode": arrow_mode,
            "kind": expected_axis,
            "score": score,
            "num_extensions": len(attached_extensions),
        }

    for hl in h_candidates:
        eval_res = evaluate_candidate(hl, "HORIZONTAL_DISTANCE")
        if eval_res is not None:
            candidate_results.append(eval_res)
    for vl in v_candidates:
        eval_res = evaluate_candidate(vl, "VERTICAL_DISTANCE")
        if eval_res is not None:
            candidate_results.append(eval_res)
    for dl in d_candidates:
        eval_res = evaluate_candidate(dl, "ALIGNED_DISTANCE")
        if eval_res is not None:
            candidate_results.append(eval_res)

    if not candidate_results:
        return RobustDimensionEvidence(None, (), (), "NONE", leader_lines, None, 0.0)

    candidate_results.sort(key=lambda c: c["score"], reverse=True)
    best = candidate_results[0]

    dim_line = best["dim_line"]
    exts = best["extensions"]
    arrows = best["arrows"]
    kind = best["kind"]
    arrow_mode = best["arrow_mode"]

    if len(arrows) >= 2 and len(exts) >= 2:
        conf = 0.95
    elif len(arrows) >= 2 and len(exts) == 1:
        conf = 0.80
    elif len(arrows) >= 2 and len(exts) == 0:
        conf = 0.65
    elif len(arrows) == 0 and len(exts) >= 2:
        conf = 0.40
    elif len(arrows) == 0 and len(exts) == 1:
        conf = 0.25
    else:
        conf = 0.10

    return RobustDimensionEvidence(
        dimension_line=dim_line,
        extension_lines=exts,
        arrow_points=arrows,
        arrow_orientation=arrow_mode,
        leader_lines=leader_lines,
        kind_hint=kind,
        confidence=conf,
    )
