"""
bolt_circle_engine.py — Reference Engine for Circular Pitch Bolt Pattern Recognition.

Epic: CIRCULAR_PITCH_BOLT_PATTERN_RECOGNITION_V1
Role: ANTIGRAVITY_RESEARCH

Benchmarks and compares circular pattern recognition strategies:
- Strategy A: Current Production Main (semantic_ir_lib/pattern_compound.py)
- Strategy B: Naive Bounding Box / Proximity Clusterer (clusters nearby circles, ignores circular topology)
- Strategy C: Radius-Only Equality Matcher (groups circles by hole radius alone, merges disjoint parts)
- Strategy D: Rigorous Pitch Circle Center & Angular Pitch Validator (Selected Oracle)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from primitive_ir_lib.models import CircleGeometry, Point2D, Primitive
from semantic_ir_lib.models import GeometrySummary, SemanticPart
from semantic_ir_lib.pattern_compound import build_compound_parts as run_strategy_a_compound


@dataclass(frozen=True)
class BoltCirclePattern:
    pattern_id: str
    hole_ids: tuple[str, ...]
    center_circle_id: Optional[str]
    center_x: float
    center_y: float
    pitch_radius_mm: float
    pitch_diameter_mm: float
    hole_radius_mm: float
    hole_count: int
    angular_pitch_deg: float
    is_full_circle: bool
    confidence: float

    def to_semantic_part(self) -> SemanticPart:
        pids = list(self.hole_ids)
        if self.center_circle_id is not None:
            pids.append(self.center_circle_id)
        return SemanticPart(
            part_type="mechanical_hole_feature",
            primitive_ids=pids,
            confidence=round(self.confidence, 3),
            source="rule_geometry",
            geometry_summary=GeometrySummary(
                radius_mm=round(self.pitch_radius_mm, 3),
            ),
        )


# ---------------------------------------------------------------------------
# Circle Geometry Helpers & Algebraic Fit
# ---------------------------------------------------------------------------

def _fit_circle_kasa(points: Sequence[Tuple[float, float]]) -> Optional[Tuple[float, float, float]]:
    """Algebraic circle fit (Kasa method) to 2D center coordinates (x_i, y_i).

    Returns (cx, cy, radius) or None if degenerate / collinear.
    """
    n = len(points)
    if n < 3:
        return None

    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sx2 = sum(p[0] ** 2 for p in points)
    sy2 = sum(p[1] ** 2 for p in points)
    sxy = sum(p[0] * p[1] for p in points)
    sz = sx2 + sy2
    sxz = sum(p[0] * (p[0] ** 2 + p[1] ** 2) for p in points)
    syz = sum(p[1] * (p[0] ** 2 + p[1] ** 2) for p in points)

    # Linear system for Kasa circle fit:
    # [ sx2  sxy  sx ] [ A ]   [ sxz ]
    # [ sxy  sy2  sy ] [ B ] = [ syz ]
    # [ sx   sy   n  ] [ C ]   [ sz  ]
    # where center = (A/2, B/2), R = sqrt(C + center_x^2 + center_y^2)

    # 3x3 determinant:
    m = [
        [sx2, sxy, sx],
        [sxy, sy2, sy],
        [sx, sy, float(n)],
    ]
    det = (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )
    if abs(det) < 1e-9:
        return None  # Collinear points or degenerate

    # Solve via Cramer's rule:
    def det3(a, b, c):
        return (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        )

    da = det3([sxz, syz, sz], [sxy, sy2, sy], [sx, sy, float(n)])
    db = det3([sx2, sxy, sx], [sxz, syz, sz], [sx, sy, float(n)])
    dc = det3([sx2, sxy, sx], [sxy, sy2, sy], [sxz, syz, sz])

    a_val = da / det
    b_val = db / det
    c_val = dc / det

    cx = a_val / 2.0
    cy = b_val / 2.0
    r_sq = c_val + cx**2 + cy**2
    if r_sq <= 0:
        return None

    r = math.sqrt(r_sq)
    return cx, cy, r


# ---------------------------------------------------------------------------
# Strategy B: Naive Bounding Box Proximity Clusterer
# ---------------------------------------------------------------------------

def run_strategy_b_patterns(
    primitives: Sequence[Primitive],
    max_gap_mm: float = 150.0,
) -> List[BoltCirclePattern]:
    """Strategy B: Groups any circles located within max_gap_mm into a single blob."""
    circles = [p for p in primitives if p.type == "circle" and p.geometry is not None]
    if len(circles) < 3:
        return []

    # Blindly clusters all circles if center distance < max_gap_mm
    res: List[BoltCirclePattern] = []
    visited: Set[str] = set()

    for c in circles:
        if c.id in visited:
            continue
        cluster = [c]
        visited.add(c.id)
        cx1, cy1 = c.geometry.center.x, c.geometry.center.y
        for other in circles:
            if other.id in visited:
                continue
            cx2, cy2 = other.geometry.center.x, other.geometry.center.y
            dist = math.hypot(cx2 - cx1, cy2 - cy1)
            if dist <= max_gap_mm:
                cluster.append(other)
                visited.add(other.id)

        if len(cluster) >= 3:
            h_rad = cluster[0].geometry.radius
            mean_cx = sum(p.geometry.center.x for p in cluster) / len(cluster)
            mean_cy = sum(p.geometry.center.y for p in cluster) / len(cluster)
            mean_r = sum(math.hypot(p.geometry.center.x - mean_cx, p.geometry.center.y - mean_cy) for p in cluster) / len(cluster)
            res.append(BoltCirclePattern(
                pattern_id=f"cluster-{len(res)+1}",
                hole_ids=tuple(p.id for p in cluster),
                center_circle_id=None,
                center_x=mean_cx,
                center_y=mean_cy,
                pitch_radius_mm=mean_r,
                pitch_diameter_mm=mean_r * 2.0,
                hole_radius_mm=h_rad,
                hole_count=len(cluster),
                angular_pitch_deg=360.0 / len(cluster),
                is_full_circle=True,
                confidence=0.5,
            ))
    return res


# ---------------------------------------------------------------------------
# Strategy C: Radius-Only Equality Matcher
# ---------------------------------------------------------------------------

def run_strategy_c_patterns(
    primitives: Sequence[Primitive],
    radius_tolerance_pct: float = 0.05,
) -> List[BoltCirclePattern]:
    """Strategy C: Groups circles purely by equal hole radius, ignoring 2D spatial arrangement."""
    circles = [p for p in primitives if p.type == "circle" and p.geometry is not None]
    if len(circles) < 3:
        return []

    # Bin by radius
    bins: List[List[Primitive]] = []
    for c in circles:
        placed = False
        r = c.geometry.radius
        for b in bins:
            br = b[0].geometry.radius
            if abs(r - br) / br <= radius_tolerance_pct:
                b.append(c)
                placed = True
                break
        if not placed:
            bins.append([c])

    res: List[BoltCirclePattern] = []
    for b in bins:
        if len(b) >= 3:
            pts = [(p.geometry.center.x, p.geometry.center.y) for p in b]
            fit = _fit_circle_kasa(pts)
            if fit:
                cx, cy, pr = fit
                res.append(BoltCirclePattern(
                    pattern_id=f"radius-group-{len(res)+1}",
                    hole_ids=tuple(p.id for p in b),
                    center_circle_id=None,
                    center_x=cx,
                    center_y=cy,
                    pitch_radius_mm=pr,
                    pitch_diameter_mm=pr * 2.0,
                    hole_radius_mm=b[0].geometry.radius,
                    hole_count=len(b),
                    angular_pitch_deg=360.0 / len(b),
                    is_full_circle=True,
                    confidence=0.6,
                ))
    return res


# ---------------------------------------------------------------------------
# Strategy D: Rigorous Pitch Circle Center & Angular Pitch Validator (Oracle)
# ---------------------------------------------------------------------------

def detect_bolt_circle_patterns(
    primitives: Sequence[Primitive],
    *,
    hole_max_radius_mm: float = 25.0,
    radius_tolerance_pct: float = 0.05,
    pitch_radius_tol_pct: float = 0.04,
    angle_tolerance_deg: float = 6.0,
    min_hole_count: int = 3,
) -> List[BoltCirclePattern]:
    """Strategy D: Comprehensive Pitch Circle & Angular Pitch Recognition Oracle.

    Validates:
    1. Equal hole radius across pattern members (|r_i - r_mean| / r_mean <= 5%).
    2. Shared pitch circle: either concentric to a detected center bore or fitted with < 4% radial error.
    3. Uniform angular spacing: |Delta theta_k - 360/N| <= 6 degrees for full circles or constant pitch for sectors.
    4. Hole count N >= min_hole_count (default 3).
    """
    # Filter valid finite circles
    circles = [
        p for p in primitives
        if p.type == "circle" and p.geometry is not None
        and math.isfinite(p.geometry.center.x) and math.isfinite(p.geometry.center.y)
        and math.isfinite(p.geometry.radius) and p.geometry.radius > 0
    ]
    if len(circles) < min_hole_count:
        return []

    # 1. Distinguish candidate bolt holes (small circles) vs center bores (larger or central circles)
    candidate_holes = [c for c in circles if c.geometry.radius <= hole_max_radius_mm]

    # Group candidate holes by equal hole radius
    radius_groups: List[List[Primitive]] = []
    for h in candidate_holes:
        placed = False
        hr = h.geometry.radius
        for rg in radius_groups:
            r0 = rg[0].geometry.radius
            if abs(hr - r0) / max(1e-6, r0) <= radius_tolerance_pct:
                rg.append(h)
                placed = True
                break
        if not placed:
            radius_groups.append([h])

    patterns: List[BoltCirclePattern] = []
    consumed_holes: Set[str] = set()

    for rg in radius_groups:
        if len(rg) < min_hole_count:
            continue

        rg_ids = {h.id for h in rg}
        candidate_centers = [
            c for c in circles
            if c.id not in rg_ids and c.geometry.radius > rg[0].geometry.radius * 1.2
        ]

        # Pass 1: Try to find full circles around candidate centers with realistic locality
        for cen_c in candidate_centers:
            cen_p = cen_c.geometry.center
            cen_id = cen_c.id
            max_pcd_radius = max(120.0, cen_c.geometry.radius * 6.0)

            distances: List[Tuple[Primitive, float]] = []
            for h in rg:
                if h.id == cen_id or h.id in consumed_holes:
                    continue
                d = math.hypot(h.geometry.center.x - cen_p.x, h.geometry.center.y - cen_p.y)
                if 5.0 <= d <= max_pcd_radius:
                    distances.append((h, d))

            if len(distances) < min_hole_count:
                continue

            dist_clusters: List[List[Tuple[Primitive, float]]] = []
            for item in distances:
                h, d = item
                placed_d = False
                for dc in dist_clusters:
                    d0 = dc[0][1]
                    if abs(d - d0) / max(1e-6, d0) <= pitch_radius_tol_pct:
                        dc.append(item)
                        placed_d = True
                        break
                if not placed_d:
                    dist_clusters.append([item])

            for dc in dist_clusters:
                if len(dc) >= min_hole_count:
                    cluster_holes = [item[0] for item in dc if item[0].id not in consumed_holes]
                    if len(cluster_holes) >= min_hole_count:
                        pat = _validate_angular_pattern(
                            cluster_holes,
                            cen_p.x,
                            cen_p.y,
                            center_circle_id=cen_id,
                            angle_tolerance_deg=angle_tolerance_deg,
                        )
                        if pat:
                            patterns.append(pat)
                            consumed_holes.update(pat.hole_ids)

        # Pass 2: Circle fitting on remaining unconsumed holes
        remaining = [h for h in rg if h.id not in consumed_holes]
        if len(remaining) >= min_hole_count:
            pts = [(h.geometry.center.x, h.geometry.center.y) for h in remaining]
            fit = _fit_circle_kasa(pts)
            if fit:
                fx, fy, fr = fit
                on_circle_holes = []
                for h in remaining:
                    d = math.hypot(h.geometry.center.x - fx, h.geometry.center.y - fy)
                    if abs(d - fr) / fr <= pitch_radius_tol_pct:
                        on_circle_holes.append(h)

                if len(on_circle_holes) >= min_hole_count:
                    pat = _validate_angular_pattern(
                        on_circle_holes,
                        fx,
                        fy,
                        center_circle_id=None,
                        angle_tolerance_deg=angle_tolerance_deg,
                    )
                    if pat:
                        patterns.append(pat)
                        consumed_holes.update(pat.hole_ids)
                        consumed_holes.update(pat.hole_ids)

    return patterns


def _validate_angular_pattern(
    holes: List[Primitive],
    cx: float,
    cy: float,
    center_circle_id: Optional[str],
    angle_tolerance_deg: float,
) -> Optional[BoltCirclePattern]:
    """Calculates polar angles and verifies uniform angular pitch across branch cuts."""
    n = len(holes)
    if n < 3:
        return None

    # Snap tiny coordinate residues near zero
    if abs(cx) < 1e-9:
        cx = 0.0
    if abs(cy) < 1e-9:
        cy = 0.0

    # Compute polar angle for each hole:
    hole_angles: List[Tuple[Primitive, float, float]] = []
    for h in holes:
        dx = h.geometry.center.x - cx
        dy = h.geometry.center.y - cy
        if abs(dx) < 1e-9:
            dx = 0.0
        if abs(dy) < 1e-9:
            dy = 0.0
        ang = math.atan2(dy, dx) % (2.0 * math.pi)
        if abs(ang - 2.0 * math.pi) < 1e-9:
            ang = 0.0
        r = math.hypot(dx, dy)
        hole_angles.append((h, ang, r))

    # Sort in ascending counter-clockwise order
    hole_angles.sort(key=lambda item: item[1])

    angles = [item[1] for item in hole_angles]
    deltas: List[float] = []
    for i in range(n - 1):
        deltas.append(angles[i + 1] - angles[i])
    # Wrap-around delta across branch cut:
    deltas.append((2.0 * math.pi) - (angles[-1] - angles[0]))

    expected_full_delta = (2.0 * math.pi) / n
    tol_rad = math.radians(angle_tolerance_deg)

    # Check 1: Full 360-degree regular circular array
    is_full = all(abs(d - expected_full_delta) <= tol_rad for d in deltas)

    # Check 2: Sector/Arc array (where largest gap is empty arc of circle)
    is_sector = False
    effective_pitch_rad = expected_full_delta

    if not is_full:
        # For a sector pattern of span < 2pi, the largest gap represents the empty circle sector
        max_gap_idx = max(range(len(deltas)), key=lambda i: deltas[i])
        max_gap = deltas[max_gap_idx]
        interior_deltas = [deltas[i] for i in range(len(deltas)) if i != max_gap_idx]

        if interior_deltas and max_gap > max(interior_deltas):
            mean_int_delta = sum(interior_deltas) / len(interior_deltas)
            if all(abs(d - mean_int_delta) <= tol_rad for d in interior_deltas):
                is_sector = True
                effective_pitch_rad = mean_int_delta

    if not is_full and not is_sector:
        return None  # Irregular or randomly scattered holes

    mean_pitch_radius = sum(item[2] for item in hole_angles) / n
    mean_hole_radius = sum(h.geometry.radius for h in holes) / n

    conf = 0.98 if is_full else 0.90
    if center_circle_id is not None:
        conf = min(0.99, conf + 0.01)

    effective_pitch_deg = math.degrees(effective_pitch_rad)

    return BoltCirclePattern(
        pattern_id=f"bolt-pattern-{n}x-R{mean_pitch_radius:.1f}",
        hole_ids=tuple(item[0].id for item in hole_angles),
        center_circle_id=center_circle_id,
        center_x=cx,
        center_y=cy,
        pitch_radius_mm=mean_pitch_radius,
        pitch_diameter_mm=mean_pitch_radius * 2.0,
        hole_radius_mm=mean_hole_radius,
        hole_count=n,
        angular_pitch_deg=effective_pitch_deg,
        is_full_circle=is_full,
        confidence=conf,
    )
