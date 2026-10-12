"""
test_merging_strategies_benchmark.py — Strategy Benchmark for Collinear Line Merging.

Empirically compares 4 candidate strategies:
- Strategy A: Current production baseline (merge_collinear_lines)
- Strategy B: Dual-endpoint perpendicular bounding + naive first-element angle
- Strategy C: Dual-endpoint bounding + length-weighted principal angle (SVD/Moments) + parallel overlap guard
- Strategy D: Strategy C + topology-aware multi-tier boundary oracle (crossing line corridor,
             perpendicular witness detection, bilateral arrowhead/hatch rejection)

Evaluates on 8 empirical test suites:
1. Noisy fragment angle skew (15px fragment at 2.8 deg + 400px horizontal line)
2. Single-endpoint perp leakage (250px line at 2.5 deg, far perp=12.9px)
3. Parallel line preservation (4px offset, 200px overlap)
4. Dimension chain boundary with 90-deg witness line (20px gap, no text)
5. 45-deg cross-hatch immunity (hatch background with valid broken line)
6. T-junction preservation (vertical stem in 15px gap)
7. Clean broken collinear line recall (3 fragments of 500px line)
8. Execution runtime (microseconds/call)
"""

from __future__ import annotations

import math
import time
from typing import List, Optional, Sequence, Tuple
import cv2
import numpy as np

from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.line_merging import merge_collinear_lines
from primitive_ir_lib.tick_mark_detection import detect_tick_mark_at_point


def _make_line(p1: tuple[float, float], p2: tuple[float, float], id_: str, conf: float = 0.9) -> RawLine:
    return RawLine(
        id=id_,
        p1_px=p1,
        p2_px=p2,
        confidence=conf,
        bbox_px=(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])),
    )


# ---------------------------------------------------------------------------
# Helper mathematical utilities
# ---------------------------------------------------------------------------

def _angle_mod_pi(dx: float, dy: float) -> float:
    return math.atan2(dy, dx) % math.pi


def _angle_diff_mod_pi(a: float, b: float) -> float:
    d = abs(a - b) % math.pi
    return min(d, math.pi - d)


def _perp_distance(px: float, py: float, x0: float, y0: float, angle: float) -> float:
    dx, dy = math.cos(angle), math.sin(angle)
    vx, vy = px - x0, py - y0
    return abs(vx * dy - vy * dx)


def _project_point(px: float, py: float, x0: float, y0: float, angle: float) -> float:
    dx, dy = math.cos(angle), math.sin(angle)
    return (px - x0) * dx + (py - y0) * dy


# ---------------------------------------------------------------------------
# Strategy Implementations
# ---------------------------------------------------------------------------

def merge_strategy_b(
    raw_lines: Sequence[RawLine],
    angle_tol_deg: float = 3.0,
    perp_tol_px: float = 6.0,
    gap_tol_px: float = 25.0,
) -> List[RawLine]:
    """Strategy B: Dual-endpoint bounding + naive first-element angle."""
    n = len(raw_lines)
    if n == 0:
        return []

    angle_tol = math.radians(angle_tol_deg)
    angles = []
    for line in raw_lines:
        x1, y1 = line.p1_px
        x2, y2 = line.p2_px
        angle = _angle_mod_pi(x2 - x1, y2 - y1)
        angles.append((angle, x1, y1, x2, y2))

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

    for i in range(n):
        ai, x1i, y1i, _, _ = angles[i]
        for j in range(i + 1, n):
            aj, x1j, y1j, x2j, y2j = angles[j]
            if _angle_diff_mod_pi(ai, aj) > angle_tol:
                continue
            # Dual-endpoint perp check: BOTH endpoints of line j must be within perp_tol of line i
            perp1 = _perp_distance(x1j, y1j, x1i, y1i, ai)
            perp2 = _perp_distance(x2j, y2j, x1i, y1i, ai)
            if max(perp1, perp2) <= perp_tol_px:
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for idx in range(n):
        clusters.setdefault(find(idx), []).append(idx)

    result = []
    for _, idxs in clusters.items():
        if len(idxs) == 1:
            result.append(raw_lines[idxs[0]])
            continue
        # Naive first-element angle
        ref_angle, ref_x0, ref_y0, _, _ = angles[idxs[0]]
        segs = []
        for i in idxs:
            line = raw_lines[i]
            p1, p2 = line.p1_px, line.p2_px
            t1 = _project_point(p1[0], p1[1], ref_x0, ref_y0, ref_angle)
            t2 = _project_point(p2[0], p2[1], ref_x0, ref_y0, ref_angle)
            t_min, t_max = min(t1, t2), max(t1, t2)
            segs.append((t_min, t_max, line))
        segs.sort(key=lambda s: s[0])

        merged_groups = [[segs[0]]]
        for seg in segs[1:]:
            group = merged_groups[-1]
            cur_max = max(s[1] for s in group)
            gap = seg[0] - cur_max
            if gap <= gap_tol_px:
                group.append(seg)
            else:
                merged_groups.append([seg])

        for g in merged_groups:
            if len(g) == 1:
                result.append(g[0][2])
                continue
            t_min = min(s[0] for s in g)
            t_max = max(s[1] for s in g)
            dx, dy = math.cos(ref_angle), math.sin(ref_angle)
            p1 = (ref_x0 + dx * t_min, ref_y0 + dy * t_min)
            p2 = (ref_x0 + dx * t_max, ref_y0 + dy * t_max)
            conf = max(s[2].confidence for s in g)
            result.append(_make_line(p1, p2, f"merged-b-{len(result)}", conf))
    return result


def merge_strategy_c(
    raw_lines: Sequence[RawLine],
    angle_tol_deg: float = 3.0,
    perp_tol_px: float = 6.0,
    gap_tol_px: float = 25.0,
    min_parallel_sep_px: float = 1.5,
) -> List[RawLine]:
    """Strategy C: Dual-endpoint bounding + length-weighted principal angle + parallel overlap guard."""
    n = len(raw_lines)
    if n == 0:
        return []

    angle_tol = math.radians(angle_tol_deg)
    line_props = []
    for line in raw_lines:
        x1, y1 = line.p1_px
        x2, y2 = line.p2_px
        length = math.hypot(x2 - x1, y2 - y1)
        angle = _angle_mod_pi(x2 - x1, y2 - y1) if length > 1e-6 else 0.0
        mid = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        line_props.append((angle, length, mid, (x1, y1), (x2, y2)))

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

    for i in range(n):
        ai, li, midi, p1i, p2i = line_props[i]
        for j in range(i + 1, n):
            aj, lj, midj, p1j, p2j = line_props[j]
            if _angle_diff_mod_pi(ai, aj) > angle_tol:
                continue

            # Dual-endpoint perp check (both directions)
            perp1_ij = _perp_distance(p1j[0], p1j[1], p1i[0], p1i[1], ai)
            perp2_ij = _perp_distance(p2j[0], p2j[1], p1i[0], p1i[1], ai)
            perp1_ji = _perp_distance(p1i[0], p1i[1], p1j[0], p1j[1], aj)
            perp2_ji = _perp_distance(p2i[0], p2i[1], p1j[0], p1j[1], aj)
            max_perp = max(perp1_ij, perp2_ij, perp1_ji, perp2_ji)
            if max_perp > perp_tol_px:
                continue

            # Parallel overlap guard: compute longitudinal interval overlap
            # Project endpoints of both lines onto axis ai
            t1i = _project_point(p1i[0], p1i[1], p1i[0], p1i[1], ai)
            t2i = _project_point(p2i[0], p2i[1], p1i[0], p1i[1], ai)
            t1j = _project_point(p1j[0], p1j[1], p1i[0], p1i[1], ai)
            t2j = _project_point(p2j[0], p2j[1], p1i[0], p1i[1], ai)
            span_i = (min(t1i, t2i), max(t1i, t2i))
            span_j = (min(t1j, t2j), max(t1j, t2j))

            overlap = min(span_i[1], span_j[1]) - max(span_i[0], span_j[0])
            # If segments have substantial overlap (> 10px) with non-negligible lateral offset (> min_parallel_sep_px),
            # they are distinct parallel lines (e.g. wall or lineweight outline), NOT broken fragments of 1 line!
            mean_perp = (perp1_ij + perp2_ij) / 2.0
            if overlap > 10.0 and mean_perp >= min_parallel_sep_px:
                continue  # Guarded: parallel lines must not be clustered!

            union(i, j)

    clusters: dict[int, list[int]] = {}
    for idx in range(n):
        clusters.setdefault(find(idx), []).append(idx)

    result = []
    for _, idxs in clusters.items():
        if len(idxs) == 1:
            result.append(raw_lines[idxs[0]])
            continue

        # Length-weighted principal direction & centroid
        weights = [line_props[i][1] ** 2 for i in idxs]
        total_w = sum(weights)
        if total_w <= 1e-9:
            result.append(raw_lines[idxs[0]])
            continue

        # Weighted angular average (doubled angles for orientation invariance mod pi)
        sin_sum = sum(w * math.sin(2.0 * line_props[i][0]) for w, i in zip(weights, idxs))
        cos_sum = sum(w * math.cos(2.0 * line_props[i][0]) for w, i in zip(weights, idxs))
        ref_angle = 0.5 * math.atan2(sin_sum, cos_sum) % math.pi

        # Weighted centroid
        cx = sum(w * line_props[i][2][0] for w, i in zip(weights, idxs)) / total_w
        cy = sum(w * line_props[i][2][1] for w, i in zip(weights, idxs)) / total_w

        segs = []
        for i in idxs:
            line = raw_lines[i]
            p1, p2 = line.p1_px, line.p2_px
            t1 = _project_point(p1[0], p1[1], cx, cy, ref_angle)
            t2 = _project_point(p2[0], p2[1], cx, cy, ref_angle)
            t_min, t_max = min(t1, t2), max(t1, t2)
            segs.append((t_min, t_max, line))
        segs.sort(key=lambda s: s[0])

        merged_groups = [[segs[0]]]
        for seg in segs[1:]:
            group = merged_groups[-1]
            cur_max = max(s[1] for s in group)
            gap = seg[0] - cur_max
            if gap <= gap_tol_px:
                group.append(seg)
            else:
                merged_groups.append([seg])

        for g in merged_groups:
            if len(g) == 1:
                result.append(g[0][2])
                continue
            t_min = min(s[0] for s in g)
            t_max = max(s[1] for s in g)
            dx, dy = math.cos(ref_angle), math.sin(ref_angle)
            p1 = (cx + dx * t_min, cy + dy * t_min)
            p2 = (cx + dx * t_max, cy + dy * t_max)
            conf = max(s[2].confidence for s in g)
            result.append(_make_line(p1, p2, f"merged-c-{len(result)}", conf))
    return result


def merge_strategy_d(
    raw_lines: Sequence[RawLine],
    image_bgr: Optional[np.ndarray] = None,
    all_document_lines: Optional[Sequence[RawLine]] = None,
    angle_tol_deg: float = 3.0,
    perp_tol_px: float = 6.0,
    gap_tol_px: float = 25.0,
    min_parallel_sep_px: float = 1.5,
) -> List[RawLine]:
    """Strategy D: Strategy C + topology-aware multi-tier boundary oracle.

    Features:
    - Dual-endpoint bounding + length-weighted principal direction + parallel overlap guard
    - Crossing-line corridor guard (checks if any independent line intersects/terminates in gap)
    - Perpendicular witness line detection in gap region
    - Bilateral arrowhead and robust tick-mark detection (rejects isolated cross-hatch strokes)
    """
    n = len(raw_lines)
    if n == 0:
        return []

    # Other lines in the document that could cross or form T-junctions
    doc_lines = list(all_document_lines or raw_lines)

    angle_tol = math.radians(angle_tol_deg)
    line_props = []
    for line in raw_lines:
        x1, y1 = line.p1_px
        x2, y2 = line.p2_px
        length = math.hypot(x2 - x1, y2 - y1)
        angle = _angle_mod_pi(x2 - x1, y2 - y1) if length > 1e-6 else 0.0
        mid = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        line_props.append((angle, length, mid, (x1, y1), (x2, y2)))

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

    for i in range(n):
        ai, li, midi, p1i, p2i = line_props[i]
        for j in range(i + 1, n):
            aj, lj, midj, p1j, p2j = line_props[j]
            if _angle_diff_mod_pi(ai, aj) > angle_tol:
                continue

            perp1_ij = _perp_distance(p1j[0], p1j[1], p1i[0], p1i[1], ai)
            perp2_ij = _perp_distance(p2j[0], p2j[1], p1i[0], p1i[1], ai)
            perp1_ji = _perp_distance(p1i[0], p1i[1], p1j[0], p1j[1], aj)
            perp2_ji = _perp_distance(p2i[0], p2i[1], p1j[0], p1j[1], aj)
            max_perp = max(perp1_ij, perp2_ij, perp1_ji, perp2_ji)
            if max_perp > perp_tol_px:
                continue

            t1i = _project_point(p1i[0], p1i[1], p1i[0], p1i[1], ai)
            t2i = _project_point(p2i[0], p2i[1], p1i[0], p1i[1], ai)
            t1j = _project_point(p1j[0], p1j[1], p1i[0], p1i[1], ai)
            t2j = _project_point(p2j[0], p2j[1], p1i[0], p1i[1], ai)
            span_i = (min(t1i, t2i), max(t1i, t2i))
            span_j = (min(t1j, t2j), max(t1j, t2j))

            overlap = min(span_i[1], span_j[1]) - max(span_i[0], span_j[0])
            mean_perp = (perp1_ij + perp2_ij) / 2.0
            if overlap > 10.0 and mean_perp >= min_parallel_sep_px:
                continue

            union(i, j)

    clusters: dict[int, list[int]] = {}
    for idx in range(n):
        clusters.setdefault(find(idx), []).append(idx)

    result = []
    for _, idxs in clusters.items():
        if len(idxs) == 1:
            result.append(raw_lines[idxs[0]])
            continue

        weights = [line_props[i][1] ** 2 for i in idxs]
        total_w = sum(weights)
        if total_w <= 1e-9:
            result.append(raw_lines[idxs[0]])
            continue

        sin_sum = sum(w * math.sin(2.0 * line_props[i][0]) for w, i in zip(weights, idxs))
        cos_sum = sum(w * math.cos(2.0 * line_props[i][0]) for w, i in zip(weights, idxs))
        ref_angle = 0.5 * math.atan2(sin_sum, cos_sum) % math.pi

        cx = sum(w * line_props[i][2][0] for w, i in zip(weights, idxs)) / total_w
        cy = sum(w * line_props[i][2][1] for w, i in zip(weights, idxs)) / total_w

        segs = []
        for i in idxs:
            line = raw_lines[i]
            p1, p2 = line.p1_px, line.p2_px
            t1 = _project_point(p1[0], p1[1], cx, cy, ref_angle)
            t2 = _project_point(p2[0], p2[1], cx, cy, ref_angle)
            t_min, t_max = min(t1, t2), max(t1, t2)
            segs.append((t_min, t_max, line, p1, p2))
        segs.sort(key=lambda s: s[0])

        dx, dy = math.cos(ref_angle), math.sin(ref_angle)
        nx, ny = -dy, dx  # normal vector to line

        def gap_has_crossing_line(t_start: float, t_end: float) -> bool:
            """Checks if any independent document line crosses or meets the gap."""
            p_start = (cx + dx * t_start, cy + dy * t_start)
            p_end = (cx + dx * t_end, cy + dy * t_end)
            for other in doc_lines:
                if other.id in [s[2].id for s in segs]:
                    continue
                # Check if other line endpoints are within proximity to gap corridor
                op1, op2 = other.p1_px, other.p2_px
                # Other line angle relative to ref_angle
                o_dx, o_dy = op2[0] - op1[0], op2[1] - op1[1]
                o_angle = _angle_mod_pi(o_dx, o_dy)
                rel_angle = _angle_diff_mod_pi(ref_angle, o_angle)
                # If other line is transverse (> 30 deg)
                if rel_angle >= math.radians(30.0):
                    # Project other line endpoints onto ref axis
                    ot1 = _project_point(op1[0], op1[1], cx, cy, ref_angle)
                    ot2 = _project_point(op2[0], op2[1], cx, cy, ref_angle)
                    # Check if other line passes through [t_start - 2, t_end + 2]
                    min_ot, max_ot = min(ot1, ot2), max(ot1, ot2)
                    if not (max_ot < t_start - 3.0 or min_ot > t_end + 3.0):
                        # Also check perpendicular distance to line axis
                        operp1 = _perp_distance(op1[0], op1[1], cx, cy, ref_angle)
                        operp2 = _perp_distance(op2[0], op2[1], cx, cy, ref_angle)
                        if min(operp1, operp2) <= 8.0:
                            return True  # Crossing line or T-junction in gap!
            return False

        def gap_has_raster_witness_or_tick(t_start: float, t_end: float) -> bool:
            """Robust image-domain witness line / tick mark oracle."""
            if image_bgr is None:
                return False
            h, w = image_bgr.shape[:2]
            t_mid = (t_start + t_end) / 2.0
            p_mid = (cx + dx * t_mid, cy + dy * t_mid)
            ix, iy = int(round(p_mid[0])), int(round(p_mid[1]))
            if not (15 <= ix < w - 15 and 15 <= iy < h - 15):
                return False

            # Check 1: Perpendicular witness line at gap center
            # Sample perpendicular profile across normal
            perp_samples_pos = [image_bgr[int(round(iy + k * ny)), int(round(ix + k * nx))][0] < 128 for k in range(3, 16)]
            perp_samples_neg = [image_bgr[int(round(iy - k * ny)), int(round(ix - k * nx))][0] < 128 for k in range(3, 16)]
            if sum(perp_samples_pos) >= 8 or sum(perp_samples_neg) >= 8:
                return True  # Real 90-deg witness line!

            # Check 2: Tick mark with bilateral symmetry / non-hatch verification
            # Extract ROI around gap
            roi = image_bgr[max(0, iy - 15):min(h, iy + 16), max(0, ix - 15):min(w, ix + 16)]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 10, minLineLength=6, maxLineGap=2)
            if lines is not None:
                diagonal_strokes = 0
                for lx1, ly1, lx2, ly2 in lines.reshape(-1, 4):
                    stroke_angle = _angle_mod_pi(float(lx2 - lx1), float(ly2 - ly1))
                    rel = _angle_diff_mod_pi(ref_angle, stroke_angle)
                    if math.radians(25.0) <= rel <= math.radians(65.0):
                        diagonal_strokes += 1
                # If there are 3 or more parallel diagonal strokes in a tiny 30x30 ROI,
                # it is a HATCH pattern (spacing ~10-15px), NOT an isolated tick mark!
                if diagonal_strokes in (1, 2):
                    return True  # Valid isolated tick mark or arrowhead!
            return False

        merged_groups = [[segs[0]]]
        for seg in segs[1:]:
            group = merged_groups[-1]
            cur_max = max(s[1] for s in group)
            gap = seg[0] - cur_max

            blocked = False
            if gap > gap_tol_px:
                blocked = True
            elif gap_has_crossing_line(cur_max, seg[0]):
                blocked = True
            elif gap_has_raster_witness_or_tick(cur_max, seg[0]):
                blocked = True

            if not blocked:
                group.append(seg)
            else:
                merged_groups.append([seg])

        for g in merged_groups:
            if len(g) == 1:
                result.append(g[0][2])
                continue
            t_min = min(s[0] for s in g)
            t_max = max(s[1] for s in g)
            p1 = (cx + dx * t_min, cy + dy * t_min)
            p2 = (cx + dx * t_max, cy + dy * t_max)
            conf = max(s[2].confidence for s in g)
            result.append(_make_line(p1, p2, f"merged-d-{len(result)}", conf))
    return result


# ---------------------------------------------------------------------------
# Benchmark Suite Runner
# ---------------------------------------------------------------------------

def run_benchmark():
    print("=" * 80)
    print("COLLINEAR LINE MERGING STRATEGY COMPARISON BENCHMARK")
    print("Strategies: [A: Current Main] [B: Dual-Bound Naive] [C: Weighted PCA + Parallel Guard] [D: Topology Oracle]")
    print("=" * 80)

    # 1. Noisy fragment angle skew test
    dx_short = 15.0 * math.cos(math.radians(2.8))
    dy_short = 15.0 * math.sin(math.radians(2.8))
    s1 = _make_line((0.0, 0.0), (dx_short, dy_short), "s1")
    l1 = _make_line((20.0, 0.0), (420.0, 0.0), "l1")

    # 2. Single-endpoint perp leak test
    p1 = (50.0, 2.0)
    p2 = (50.0 + 250.0 * math.cos(math.radians(2.5)), 2.0 + 250.0 * math.sin(math.radians(2.5)))
    base = _make_line((0.0, 0.0), (300.0, 0.0), "base")
    div = _make_line(p1, p2, "div")

    # 3. Parallel lines test
    w_top = _make_line((50.0, 100.0), (250.0, 100.0), "top")
    w_bot = _make_line((50.0, 104.0), (250.0, 104.0), "bot")

    # 4. Dimension chain with 90-deg witness line test
    img_dim = np.full((200, 400, 3), 255, dtype=np.uint8)
    cv2.line(img_dim, (20, 100), (180, 100), (0, 0, 0), 2)
    cv2.line(img_dim, (200, 100), (350, 100), (0, 0, 0), 2)
    cv2.line(img_dim, (190, 70), (190, 130), (0, 0, 0), 2)
    d1 = _make_line((20.0, 100.0), (180.0, 100.0), "d1")
    d2 = _make_line((200.0, 100.0), (350.0, 100.0), "d2")

    # 5. Hatch immunity test
    img_hatch = np.full((200, 300, 3), 255, dtype=np.uint8)
    cv2.line(img_hatch, (50, 100), (150, 100), (0, 0, 0), 1)
    cv2.line(img_hatch, (160, 100), (260, 100), (0, 0, 0), 1)
    for offset in range(-100, 400, 15):
        cv2.line(img_hatch, (offset, 0), (offset + 200, 200), (0, 0, 0), 1)
    h1 = _make_line((50.0, 100.0), (150.0, 100.0), "h1")
    h2 = _make_line((160.0, 100.0), (260.0, 100.0), "h2")

    # 6. T-junction test
    t_left = _make_line((20.0, 100.0), (95.0, 100.0), "tl")
    t_right = _make_line((105.0, 100.0), (200.0, 100.0), "tr")
    t_stem = _make_line((100.0, 100.0), (100.0, 180.0), "ts")

    # 7. Clean broken collinear line recall test
    c1 = _make_line((0.0, 50.0), (150.0, 50.0), "c1")
    c2 = _make_line((155.0, 50.0), (300.0, 50.0), "c2")
    c3 = _make_line((310.0, 50.0), (500.0, 50.0), "c3")

    strategies = [
        ("Strat A (Current)", lambda lines, **kw: merge_collinear_lines(lines, blocking_texts=[], image_bgr=kw.get("img"), gap_tol_px=25.0, perp_tol_px=6.0)),
        ("Strat B (Dual-Bound)", lambda lines, **kw: merge_strategy_b(lines, gap_tol_px=25.0, perp_tol_px=6.0)),
        ("Strat C (Weighted+Guard)", lambda lines, **kw: merge_strategy_c(lines, gap_tol_px=25.0, perp_tol_px=6.0)),
        ("Strat D (Topology Oracle)", lambda lines, **kw: merge_strategy_d(lines, image_bgr=kw.get("img"), all_document_lines=kw.get("doc_lines"), gap_tol_px=25.0, perp_tol_px=6.0)),
    ]

    results = {}
    for name, fn in strategies:
        # Metric 1: Angle error
        res1 = fn([s1, l1])
        m_angle = 0.0
        m_drift = 0.0
        if len(res1) == 1:
            p1_res, p2_res = res1[0].p1_px, res1[0].p2_px
            m_angle = math.degrees(math.atan2(abs(p2_res[1] - p1_res[1]), abs(p2_res[0] - p1_res[0])))
            m_drift = abs(p2_res[1] - 0.0)

        # Metric 2: Diverging perp leak rejection
        res2 = fn([base, div])
        perp_leak_rejected = (len(res2) == 2)

        # Metric 3: Parallel line preservation
        res3 = fn([w_top, w_bot])
        parallel_preserved = (len(res3) == 2)

        # Metric 4: Dimension chain boundary recall
        res4 = fn([d1, d2], img=img_dim)
        dim_chain_preserved = (len(res4) == 2)

        # Metric 5: Hatch immunity (valid line merged despite hatch)
        res5 = fn([h1, h2], img=img_hatch)
        hatch_immune = (len(res5) == 1)

        # Metric 6: T-junction preserved (horizontal lines not merged across vertical stem)
        res6 = fn([t_left, t_right, t_stem], doc_lines=[t_left, t_right, t_stem])
        h_lines = [l for l in res6 if abs(l.p1_px[1] - l.p2_px[1]) <= 2.0]
        t_junction_preserved = (len(h_lines) == 2)

        # Metric 7: Clean broken line recall
        res7 = fn([c1, c2, c3])
        clean_merged = (len(res7) == 1 and abs(res7[0].length_px() - 500.0) <= 1.0)

        # Metric 8: Runtime
        start_t = time.perf_counter()
        for _ in range(500):
            fn([c1, c2, c3])
        elapsed_us = (time.perf_counter() - start_t) / 500.0 * 1e6

        results[name] = {
            "angle_err_deg": m_angle,
            "drift_px": m_drift,
            "perp_leak_rej": perp_leak_rejected,
            "parallel_pres": parallel_preserved,
            "dim_chain_pres": dim_chain_preserved,
            "hatch_immune": hatch_immune,
            "t_junction_pres": t_junction_preserved,
            "clean_merged": clean_merged,
            "runtime_us": elapsed_us,
        }

    print("\nBENCHMARK RESULTS TABLE:")
    print("-" * 115)
    print(f"{'Strategy':<26} | {'Angle Err':<9} | {'Drift':<8} | {'PerpLeakRej':<11} | {'ParallelPres':<12} | {'DimChain':<8} | {'HatchImm':<8} | {'TJunct':<6} | {'Runtime'}")
    print("-" * 115)
    for name, r in results.items():
        print(f"{name:<26} | {r['angle_err_deg']:>7.3f}° | {r['drift_px']:>6.2f}px | {str(r['perp_leak_rej']):<11} | {str(r['parallel_pres']):<12} | {str(r['dim_chain_pres']):<8} | {str(r['hatch_immune']):<8} | {str(r['t_junction_pres']):<6} | {r['runtime_us']:>6.1f} us")
    print("-" * 115)

    return results


def test_strategy_benchmark_assertions():
    results = run_benchmark()
    # Strategy A (Current) fails on multiple gates
    assert results["Strat A (Current)"]["angle_err_deg"] > 2.0
    assert results["Strat A (Current)"]["perp_leak_rej"] is False
    assert results["Strat A (Current)"]["parallel_pres"] is False
    assert results["Strat A (Current)"]["dim_chain_pres"] is False
    assert results["Strat A (Current)"]["t_junction_pres"] is False

    # Strategy D satisfies 100% of safety and quality gates
    strat_d = results["Strat D (Topology Oracle)"]
    assert strat_d["angle_err_deg"] < 0.15, f"Strategy D angle error {strat_d['angle_err_deg']} >= 0.15 deg"
    assert strat_d["drift_px"] < 1.0, f"Strategy D drift {strat_d['drift_px']} >= 1.0 px"
    assert strat_d["perp_leak_rej"] is True
    assert strat_d["parallel_pres"] is True
    assert strat_d["dim_chain_pres"] is True
    assert strat_d["hatch_immune"] is True
    assert strat_d["t_junction_pres"] is True
    assert strat_d["clean_merged"] is True
    assert strat_d["runtime_us"] < 500.0, f"Strategy D runtime {strat_d['runtime_us']} us >= 500 us"


if __name__ == "__main__":
    test_strategy_benchmark_assertions()
