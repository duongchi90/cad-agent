"""
line_merging_engine.py — Reference implementations of candidate strategies A, B, C, D
for the Collinear Line Merging and Dimension Boundary Discrimination research program.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple
import cv2
import numpy as np

from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.line_merging import merge_collinear_lines


def make_line(p1: tuple[float, float], p2: tuple[float, float], id_: str, conf: float = 0.9) -> RawLine:
    return RawLine(
        id=id_,
        p1_px=p1,
        p2_px=p2,
        confidence=conf,
        bbox_px=(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])),
    )


def angle_mod_pi(dx: float, dy: float) -> float:
    return math.atan2(dy, dx) % math.pi


def angle_diff_mod_pi(a: float, b: float) -> float:
    d = abs(a - b) % math.pi
    return min(d, math.pi - d)


def perp_distance(px: float, py: float, x0: float, y0: float, angle: float) -> float:
    dx, dy = math.cos(angle), math.sin(angle)
    vx, vy = px - x0, py - y0
    return abs(vx * dy - vy * dx)


def project_point(px: float, py: float, x0: float, y0: float, angle: float) -> float:
    dx, dy = math.cos(angle), math.sin(angle)
    return (px - x0) * dx + (py - y0) * dy


def merge_strategy_a(
    raw_lines: Sequence[RawLine],
    image_bgr: Optional[np.ndarray] = None,
    gap_tol_px: float = 25.0,
    perp_tol_px: float = 6.0,
    angle_tol_deg: float = 3.0,
) -> List[RawLine]:
    """Strategy A: Current production baseline."""
    return merge_collinear_lines(
        raw_lines,
        blocking_texts=[],
        image_bgr=image_bgr,
        gap_tol_px=gap_tol_px,
        perp_tol_px=perp_tol_px,
        angle_tol_deg=angle_tol_deg,
    )


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
        angle = angle_mod_pi(x2 - x1, y2 - y1)
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
            if angle_diff_mod_pi(ai, aj) > angle_tol:
                continue
            perp1 = perp_distance(x1j, y1j, x1i, y1i, ai)
            perp2 = perp_distance(x2j, y2j, x1i, y1i, ai)
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
        ref_angle, ref_x0, ref_y0, _, _ = angles[idxs[0]]
        segs = []
        for i in idxs:
            line = raw_lines[i]
            p1, p2 = line.p1_px, line.p2_px
            t1 = project_point(p1[0], p1[1], ref_x0, ref_y0, ref_angle)
            t2 = project_point(p2[0], p2[1], ref_x0, ref_y0, ref_angle)
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
            result.append(make_line(p1, p2, f"merged-b-{len(result)}", conf))
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
        angle = angle_mod_pi(x2 - x1, y2 - y1) if length > 1e-6 else 0.0
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
            if angle_diff_mod_pi(ai, aj) > angle_tol:
                continue

            if li >= lj:
                ref_a, ref_p = ai, p1i
                other_p1, other_p2 = p1j, p2j
                p1_self, p2_self = p1i, p2i
            else:
                ref_a, ref_p = aj, p1j
                other_p1, other_p2 = p1i, p2i
                p1_self, p2_self = p1j, p2j

            perp1 = perp_distance(other_p1[0], other_p1[1], ref_p[0], ref_p[1], ref_a)
            perp2 = perp_distance(other_p2[0], other_p2[1], ref_p[0], ref_p[1], ref_a)
            max_perp = max(perp1, perp2)
            if max_perp > perp_tol_px:
                continue

            t1_self = project_point(p1_self[0], p1_self[1], ref_p[0], ref_p[1], ref_a)
            t2_self = project_point(p2_self[0], p2_self[1], ref_p[0], ref_p[1], ref_a)
            t1_oth = project_point(other_p1[0], other_p1[1], ref_p[0], ref_p[1], ref_a)
            t2_oth = project_point(other_p2[0], other_p2[1], ref_p[0], ref_p[1], ref_a)
            span_self = (min(t1_self, t2_self), max(t1_self, t2_self))
            span_oth = (min(t1_oth, t2_oth), max(t1_oth, t2_oth))

            overlap = min(span_self[1], span_oth[1]) - max(span_self[0], span_oth[0])
            mean_perp = (perp1 + perp2) / 2.0
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
            t1 = project_point(p1[0], p1[1], cx, cy, ref_angle)
            t2 = project_point(p2[0], p2[1], cx, cy, ref_angle)
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
            result.append(make_line(p1, p2, f"merged-c-{len(result)}", conf))
    return result


def merge_strategy_d(
    raw_lines: Sequence[RawLine],
    blocking_texts: Optional[Sequence[RawText]] = None,
    image_bgr: Optional[np.ndarray] = None,
    all_document_lines: Optional[Sequence[RawLine]] = None,
    angle_tol_deg: float = 3.0,
    perp_tol_px: float = 6.0,
    gap_tol_px: float = 25.0,
    min_parallel_sep_px: float = 1.5,
) -> List[RawLine]:
    """Strategy D: Strategy C + topology-aware multi-tier boundary oracle."""
    n = len(raw_lines)
    if n == 0:
        return []

    doc_lines = list(all_document_lines or raw_lines)
    angle_tol = math.radians(angle_tol_deg)
    line_props = []
    for line in raw_lines:
        x1, y1 = line.p1_px
        x2, y2 = line.p2_px
        length = math.hypot(x2 - x1, y2 - y1)
        angle = angle_mod_pi(x2 - x1, y2 - y1) if length > 1e-6 else 0.0
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
            if angle_diff_mod_pi(ai, aj) > angle_tol:
                continue

            if li >= lj:
                ref_a, ref_p = ai, p1i
                other_p1, other_p2 = p1j, p2j
                p1_self, p2_self = p1i, p2i
            else:
                ref_a, ref_p = aj, p1j
                other_p1, other_p2 = p1i, p2i
                p1_self, p2_self = p1j, p2j

            perp1 = perp_distance(other_p1[0], other_p1[1], ref_p[0], ref_p[1], ref_a)
            perp2 = perp_distance(other_p2[0], other_p2[1], ref_p[0], ref_p[1], ref_a)
            max_perp = max(perp1, perp2)
            if max_perp > perp_tol_px:
                continue

            t1_self = project_point(p1_self[0], p1_self[1], ref_p[0], ref_p[1], ref_a)
            t2_self = project_point(p2_self[0], p2_self[1], ref_p[0], ref_p[1], ref_a)
            t1_oth = project_point(other_p1[0], other_p1[1], ref_p[0], ref_p[1], ref_a)
            t2_oth = project_point(other_p2[0], other_p2[1], ref_p[0], ref_p[1], ref_a)
            span_self = (min(t1_self, t2_self), max(t1_self, t2_self))
            span_oth = (min(t1_oth, t2_oth), max(t1_oth, t2_oth))

            overlap = min(span_self[1], span_oth[1]) - max(span_self[0], span_oth[0])
            mean_perp = (perp1 + perp2) / 2.0
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
            t1 = project_point(p1[0], p1[1], cx, cy, ref_angle)
            t2 = project_point(p2[0], p2[1], cx, cy, ref_angle)
            t_min, t_max = min(t1, t2), max(t1, t2)
            segs.append((t_min, t_max, line, p1, p2))
        segs.sort(key=lambda s: s[0])

        # Precompute nearby text projections if blocking_texts provided
        dx, dy = math.cos(ref_angle), math.sin(ref_angle)
        nx, ny = -dy, dx

        def gap_has_text(t_start: float, t_end: float) -> bool:
            if not blocking_texts:
                return False
            lo, hi = t_start - 4.0, t_end + 4.0
            for text in blocking_texts:
                x0, y0, x1, y1 = text.bbox_px
                tcx, tcy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
                perp = perp_distance(tcx, tcy, cx, cy, ref_angle)
                if perp <= 25.0:
                    t_val = project_point(tcx, tcy, cx, cy, ref_angle)
                    if lo <= t_val <= hi:
                        return True
            return False

        def gap_has_crossing_line(t_start: float, t_end: float) -> bool:
            for other in doc_lines:
                if other.id in [s[2].id for s in segs]:
                    continue
                op1, op2 = other.p1_px, other.p2_px
                o_dx, o_dy = op2[0] - op1[0], op2[1] - op1[1]
                o_len = math.hypot(o_dx, o_dy)
                if o_len < 1e-4:
                    continue
                o_angle = angle_mod_pi(o_dx, o_dy)
                rel_angle = angle_diff_mod_pi(ref_angle, o_angle)
                if rel_angle >= math.radians(20.0):
                    # Compute (t, d_perp) coordinates for both endpoints of the other line
                    v1x, v1y = op1[0] - cx, op1[1] - cy
                    v2x, v2y = op2[0] - cx, op2[1] - cy
                    t1 = v1x * dx + v1y * dy
                    d1 = v1x * nx + v1y * ny
                    t2 = v2x * dx + v2y * dy
                    d2 = v2x * nx + v2y * ny

                    t_lo = t_start - 2.0
                    t_hi = t_end + 2.0

                    # Case 1: Transverse line intersects the line axis (d crosses 0)
                    if (d1 <= 0 and d2 >= 0) or (d1 >= 0 and d2 <= 0):
                        if abs(d2 - d1) > 1e-6:
                            alpha = -d1 / (d2 - d1)
                            t_cross = t1 + alpha * (t2 - t1)
                            if t_lo <= t_cross <= t_hi:
                                return True

                    # Case 2: Endpoint terminates inside the gap corridor (|d| <= 8px and t in range)
                    if abs(d1) <= 8.0 and t_lo <= t1 <= t_hi:
                        return True
                    if abs(d2) <= 8.0 and t_lo <= t2 <= t_hi:
                        return True
            return False

        def gap_has_raster_witness_or_tick(t_start: float, t_end: float) -> bool:
            if image_bgr is None:
                return False
            h, w = image_bgr.shape[:2]

            # Check 1: Perpendicular witness line scanning with drift guard
            # A true 90-degree witness line has dark pixels along normal with drift <= 1.5px across 10+ rows
            t_samples = np.arange(t_start, t_end + 0.5, 1.0)
            for t_val in t_samples:
                px = cx + dx * t_val
                py = cy + dy * t_val
                ix, iy = int(round(px)), int(round(py))
                if 16 <= ix < w - 16 and 16 <= iy < h - 16:
                    # Check positive normal direction
                    pos_offsets = []
                    for k in range(3, 16):
                        row_x = int(round(ix + k * nx))
                        row_y = int(round(iy + k * ny))
                        for d in range(-3, 4):
                            qx = int(round(row_x + d * dx))
                            qy = int(round(row_y + d * dy))
                            if 0 <= qx < w and 0 <= qy < h and image_bgr[qy, qx][0] < 128:
                                pos_offsets.append(d)
                                break
                    if len(pos_offsets) >= 8 and (max(pos_offsets) - min(pos_offsets)) <= 1.5:
                        return True

                    # Check negative normal direction
                    neg_offsets = []
                    for k in range(3, 16):
                        row_x = int(round(ix - k * nx))
                        row_y = int(round(iy - k * ny))
                        for d in range(-3, 4):
                            qx = int(round(row_x + d * dx))
                            qy = int(round(row_y + d * dy))
                            if 0 <= qx < w and 0 <= qy < h and image_bgr[qy, qx][0] < 128:
                                neg_offsets.append(d)
                                break
                    if len(neg_offsets) >= 8 and (max(neg_offsets) - min(neg_offsets)) <= 1.5:
                        return True

            # Check 2: Tick marks or arrowheads at the two segment endpoints facing the gap
            # Uses a 64x64 context window to discriminate isolated tick strokes from periodic hatch fields
            check_points = [(cx + dx * t_start, cy + dy * t_start), (cx + dx * t_end, cy + dy * t_end)]
            for epx, epy in check_points:
                ix, iy = int(round(epx)), int(round(epy))
                win = 32
                if win <= ix < w - win and win <= iy < h - win:
                    roi = image_bgr[max(0, iy - win):min(h, iy + win + 1), max(0, ix - win):min(w, ix + win + 1)]
                    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
                    edges = cv2.Canny(gray, 50, 150)
                    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 8, minLineLength=5, maxLineGap=2)
                    if lines is not None:
                        roi_cx, roi_cy = roi.shape[1] / 2.0, roi.shape[0] / 2.0
                        candidates = []
                        for lx1, ly1, lx2, ly2 in lines.reshape(-1, 4):
                            stroke_angle = angle_mod_pi(float(lx2 - lx1), float(ly2 - ly1))
                            rel = angle_diff_mod_pi(ref_angle, stroke_angle)
                            if math.radians(20.0) <= rel <= math.radians(70.0):
                                d1 = math.hypot(lx1 - roi_cx, ly1 - roi_cy)
                                d2 = math.hypot(lx2 - roi_cx, ly2 - roi_cy)
                                dx_s, dy_s = math.cos(stroke_angle), math.sin(stroke_angle)
                                vx, vy = roi_cx - lx1, roi_cy - ly1
                                perp = abs(vx * dy_s - vy * dx_s)
                                if min(d1, d2) <= 6.0 and perp <= 4.0:
                                    candidates.append((stroke_angle, perp))

                        if candidates:
                            # Verify if any candidate stroke is an isolated tick mark vs a periodic hatch field
                            for stroke_angle, _ in candidates:
                                dx_s, dy_s = math.cos(stroke_angle), math.sin(stroke_angle)
                                perps = []
                                for lx1, ly1, lx2, ly2 in lines.reshape(-1, 4):
                                    sang = angle_mod_pi(float(lx2 - lx1), float(ly2 - ly1))
                                    if angle_diff_mod_pi(sang, stroke_angle) <= math.radians(12.0):
                                        vx, vy = roi_cx - lx1, roi_cy - ly1
                                        perps.append(abs(vx * dy_s - vy * dx_s))
                                if perps:
                                    perps.sort()
                                    distinct = [perps[0]]
                                    for p in perps[1:]:
                                        if p - distinct[-1] >= 6.0:
                                            distinct.append(p)
                                    if len(distinct) >= 2:
                                        # Periodic hatch field detected: reject false tick mark
                                        continue
                                    # Isolated tick mark confirmed!
                                    return True
            return False

        merged_groups = [[segs[0]]]
        for seg in segs[1:]:
            group = merged_groups[-1]
            cur_max = max(s[1] for s in group)
            gap = seg[0] - cur_max

            blocked = False
            if gap > gap_tol_px:
                blocked = True
            elif gap_has_text(cur_max, seg[0]):
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
            result.append(make_line(p1, p2, f"merged-d-{len(result)}", conf))
    return result
