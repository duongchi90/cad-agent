"""
arc_constraint_engine.py — Reference Engine for Arc and Fillet Constraint Detection Strategies A, B, C, D.

Empirically benchmarks and compares constraint detection algorithms for curved primitives:
- Strategy A: Current Production Main (semantic_ir_lib/constraint_detection.py)
- Strategy B: Naive Infinite Projection Matcher (ignores segment bounds & arc sweep)
- Strategy C: Endpoint-Only Proximity Matcher (coincident endpoints without tangent vector verification)
- Strategy D: Bounded Sweep Contact Oracle (bounded contact projection, sweep interval containment, multi-primitive concentricity, and robust fillet validation)
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

_repo_root = str(Path(__file__).resolve().parents[4])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from primitive_ir_lib.models import (
    ArcGeometry,
    CircleGeometry,
    LineGeometry,
    Point2D,
    Primitive,
    Trace,
    new_id,
)
from semantic_ir_lib.constraint_detection import (
    detect_circle_constraints as detect_circle_strategy_a,
    detect_constraints as detect_lines_strategy_a,
    _point_to_infinite_line_distance,
)
from semantic_ir_lib.models import Constraint


def make_point(x: float, y: float) -> Point2D:
    return Point2D(x=float(x), y=float(y))


def _safe_bbox(c1: float, c2: float, c3: float, c4: float) -> Tuple[int, int, int, int]:
    if math.isfinite(c1) and math.isfinite(c2) and math.isfinite(c3) and math.isfinite(c4):
        return (int(c1), int(c2), int(c3), int(c4))
    return (0, 0, 0, 0)


def make_line(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    id_: str = "",
) -> Primitive:
    return Primitive(
        id=id_ or new_id("line"),
        type="line",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=_safe_bbox(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1]))),
        geometry=LineGeometry(start=make_point(p1[0], p1[1]), end=make_point(p2[0], p2[1])),
    )


def make_circle(
    center: Tuple[float, float],
    radius: float,
    id_: str = "",
) -> Primitive:
    return Primitive(
        id=id_ or new_id("circle"),
        type="circle",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=_safe_bbox(center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)),
        geometry=CircleGeometry(center=make_point(center[0], center[1]), radius=float(radius)),
    )


def make_arc(
    center: Tuple[float, float],
    radius: float,
    start_deg: float,
    end_deg: float,
    id_: str = "",
) -> Primitive:
    return Primitive(
        id=id_ or new_id("arc"),
        type="arc",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=_safe_bbox(center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)),
        geometry=ArcGeometry(
            center=make_point(center[0], center[1]),
            radius=float(radius),
            start_angle_deg=float(start_deg),
            end_angle_deg=float(end_deg),
        ),
    )


def _is_angle_in_sweep(angle_deg: float, start_deg: float, end_deg: float, tol_deg: float = 3.0) -> bool:
    """Checks whether angle_deg falls within the CCW sweep from start_deg to end_deg."""
    a = angle_deg % 360.0
    s = start_deg % 360.0
    e = end_deg % 360.0

    # Total CCW sweep angle
    sweep = (e - s) % 360.0
    if sweep == 0.0 and start_deg != end_deg:
        sweep = 360.0  # Full circle

    # Offset from start
    diff = (a - s) % 360.0

    # With tolerance
    return diff <= sweep + tol_deg or (360.0 - diff) <= tol_deg


def _point_distance(p1: Point2D, p2: Point2D) -> float:
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


# ---------------------------------------------------------------------------
# Strategy A: Current Production Main
# ---------------------------------------------------------------------------

def run_strategy_a(
    primitives: Sequence[Primitive],
    distance_tolerance_mm: float = 5.0,
) -> List[Constraint]:
    """Strategy A: Current Production Main."""
    lines = [p for p in primitives if p.type == "line"]
    circles = [p for p in primitives if p.type == "circle"]
    # Strategy A explicitly raises ValueError on arc primitives if passed
    res: List[Constraint] = []
    if lines:
        res.extend(detect_lines_strategy_a(lines, distance_tolerance_mm=distance_tolerance_mm))
    if lines and circles:
        res.extend(detect_circle_strategy_a(lines, circles, distance_tolerance_mm=distance_tolerance_mm))
    return res


# ---------------------------------------------------------------------------
# Strategy B: Naive Infinite Projection Matcher
# ---------------------------------------------------------------------------

def run_strategy_b(
    primitives: Sequence[Primitive],
    distance_tolerance_mm: float = 5.0,
) -> List[Constraint]:
    """Strategy B: Treats arcs as circles, but still uses infinite line projection."""
    lines = [p for p in primitives if p.type == "line"]
    curved = [p for p in primitives if p.type in ("circle", "arc")]

    constraints: List[Constraint] = []
    # Tangent: infinite line distance
    for line in lines:
        for c in curved:
            center = c.geometry.center
            radius = c.geometry.radius
            dist = _point_to_infinite_line_distance(center, line.geometry.start, line.geometry.end)
            gap = abs(dist - radius)
            if gap <= distance_tolerance_mm:
                constraints.append(Constraint(
                    type="tangent",
                    primitive_ids=[line.id, c.id],
                    confidence=0.8,
                    tolerance={"distance_mm": distance_tolerance_mm},
                    measured={"tangent_gap_mm": round(gap, 3)},
                ))

    # Concentric: center distance
    for i, c1 in enumerate(curved):
        for c2 in curved[i + 1:]:
            cdist = _point_distance(c1.geometry.center, c2.geometry.center)
            if cdist <= distance_tolerance_mm:
                constraints.append(Constraint(
                    type="concentric",
                    primitive_ids=[c1.id, c2.id],
                    confidence=0.85,
                    tolerance={"distance_mm": distance_tolerance_mm},
                    measured={"center_distance_mm": round(cdist, 3)},
                ))

    return constraints


# ---------------------------------------------------------------------------
# Strategy C: Endpoint-Only Proximity Matcher
# ---------------------------------------------------------------------------

def run_strategy_c(
    primitives: Sequence[Primitive],
    distance_tolerance_mm: float = 5.0,
) -> List[Constraint]:
    """Strategy C: Only flags tangency if endpoints physically touch within tolerance."""
    lines = [p for p in primitives if p.type == "line"]
    arcs = [p for p in primitives if p.type == "arc"]

    constraints: List[Constraint] = []
    for line in lines:
        for arc in arcs:
            c = arc.geometry.center
            r = arc.geometry.radius
            s_rad = math.radians(arc.geometry.start_angle_deg)
            e_rad = math.radians(arc.geometry.end_angle_deg)
            arc_p1 = Point2D(x=c.x + r * math.cos(s_rad), y=c.y + r * math.sin(s_rad))
            arc_p2 = Point2D(x=c.x + r * math.cos(e_rad), y=c.y + r * math.sin(e_rad))

            # Check min distance to line endpoints
            d_min = min(
                _point_distance(line.geometry.start, arc_p1),
                _point_distance(line.geometry.start, arc_p2),
                _point_distance(line.geometry.end, arc_p1),
                _point_distance(line.geometry.end, arc_p2),
            )
            if d_min <= distance_tolerance_mm:
                constraints.append(Constraint(
                    type="tangent",
                    primitive_ids=[line.id, arc.id],
                    confidence=0.80,
                    tolerance={"distance_mm": distance_tolerance_mm},
                    measured={"endpoint_distance_mm": round(d_min, 3)},
                ))
    return constraints


# ---------------------------------------------------------------------------
# Strategy D: Bounded Sweep Contact Oracle
# ---------------------------------------------------------------------------

def _project_point_to_line_segment(
    pt: Point2D,
    line_start: Point2D,
    line_end: Point2D,
) -> Tuple[Point2D, float, float]:
    """Projects pt onto segment [line_start, line_end].
    Returns (closest_point, parameter_t, perpendicular_distance).
    """
    vx = line_end.x - line_start.x
    vy = line_end.y - line_start.y
    seg_len_sq = vx * vx + vy * vy
    if seg_len_sq < 1e-12:
        dist = _point_distance(pt, line_start)
        return line_start, 0.0, dist

    t = ((pt.x - line_start.x) * vx + (pt.y - line_start.y) * vy) / seg_len_sq
    t_clamped = max(0.0, min(1.0, t))
    closest = Point2D(x=line_start.x + t_clamped * vx, y=line_start.y + t_clamped * vy)
    dist = _point_distance(pt, closest)
    return closest, t, dist


def detect_arc_fillet_constraints(
    primitives: Sequence[Primitive],
    distance_tolerance_mm: float = 5.0,
    angle_tolerance_deg: float = 3.5,
    length_tolerance_percent: float = 3.0,
) -> List[Constraint]:
    """Strategy D: Multi-Primitive Bounded Sweep Constraint Engine.

    Detects:
    1. Line-Arc / Line-Circle Bounded Tangency (fillet and slot tangent transitions)
    2. Arc-Arc External and Internal Tangency (compound curves and S-curves)
    3. Multi-Primitive Concentricity (Circle-Circle, Circle-Arc, Arc-Arc)
    4. Line-Arc Coincident Endpoints
    5. Arc-Arc / Arc-Circle Equal Radius
    """
    def _is_valid_point(p: Point2D) -> bool:
        return math.isfinite(p.x) and math.isfinite(p.y)

    def _is_valid_line(p: Primitive) -> bool:
        if p.type != "line" or p.geometry is None:
            return False
        g = p.geometry
        if not (_is_valid_point(g.start) and _is_valid_point(g.end)):
            return False
        return math.hypot(g.end.x - g.start.x, g.end.y - g.start.y) > 1e-4

    def _is_valid_circle(p: Primitive) -> bool:
        if p.type != "circle" or p.geometry is None:
            return False
        g = p.geometry
        return _is_valid_point(g.center) and math.isfinite(g.radius) and g.radius > 1e-4

    def _is_valid_arc(p: Primitive) -> bool:
        if p.type != "arc" or p.geometry is None:
            return False
        g = p.geometry
        if not (_is_valid_point(g.center) and math.isfinite(g.radius) and g.radius > 1e-4):
            return False
        return math.isfinite(g.start_angle_deg) and math.isfinite(g.end_angle_deg)

    lines = [p for p in primitives if _is_valid_line(p)]
    circles = [p for p in primitives if _is_valid_circle(p)]
    arcs = [p for p in primitives if _is_valid_arc(p)]

    constraints: List[Constraint] = []

    # 1. Bounded Line-Circle and Line-Arc Tangency
    for line in lines:
        vx = line.geometry.end.x - line.geometry.start.x
        vy = line.geometry.end.y - line.geometry.start.y
        seg_len_sq = vx * vx + vy * vy
        if seg_len_sq < 1e-12:
            continue

        for curved in circles + arcs:
            center = curved.geometry.center
            radius = curved.geometry.radius

            # 1a. Infinite line distance to center
            dist_to_inf_line = _point_to_infinite_line_distance(
                center, line.geometry.start, line.geometry.end
            )
            radial_gap = abs(dist_to_inf_line - radius)
            if radial_gap > distance_tolerance_mm:
                continue

            # 1b. Compute perpendicular contact point on the infinite line
            t_param = ((center.x - line.geometry.start.x) * vx + (center.y - line.geometry.start.y) * vy) / seg_len_sq
            contact_p = Point2D(
                x=line.geometry.start.x + t_param * vx,
                y=line.geometry.start.y + t_param * vy,
            )

            # Distance from contact point to line segment bounds
            if t_param < 0.0:
                dist_to_seg = _point_distance(contact_p, line.geometry.start)
            elif t_param > 1.0:
                dist_to_seg = _point_distance(contact_p, line.geometry.end)
            else:
                dist_to_seg = 0.0

            if dist_to_seg > distance_tolerance_mm:
                continue

            # 1c. If Arc: Bounded Sweep Guard
            if curved.type == "arc":
                contact_angle_deg = math.degrees(math.atan2(contact_p.y - center.y, contact_p.x - center.x)) % 360.0
                if not _is_angle_in_sweep(
                    contact_angle_deg,
                    curved.geometry.start_angle_deg,
                    curved.geometry.end_angle_deg,
                    tol_deg=angle_tolerance_deg,
                ):
                    continue

            total_gap = max(radial_gap, dist_to_seg)
            confidence = max(0.5, 1.0 - (total_gap / distance_tolerance_mm) * 0.5) if distance_tolerance_mm > 0 else 1.0
            constraints.append(Constraint(
                type="tangent",
                primitive_ids=[line.id, curved.id],
                confidence=round(confidence, 3),
                tolerance={"distance_mm": distance_tolerance_mm},
                measured={"tangent_gap_mm": round(radial_gap, 3)},
            ))

    # 2. Arc-Arc and Arc-Circle Tangency
    curved_all = circles + arcs
    n_curv = len(curved_all)
    for i in range(n_curv):
        c1 = curved_all[i]
        for j in range(i + 1, n_curv):
            c2 = curved_all[j]
            center1, r1 = c1.geometry.center, c1.geometry.radius
            center2, r2 = c2.geometry.center, c2.geometry.radius

            center_dist = _point_distance(center1, center2)
            if center_dist < 1e-4:
                continue

            # External tangency: dist ≈ r1 + r2
            ext_gap = abs(center_dist - (r1 + r2))
            # Internal tangency: dist ≈ |r1 - r2|
            int_gap = abs(center_dist - abs(r1 - r2))

            is_tangent = False
            gap = 0.0
            contact_pt: Optional[Point2D] = None

            if ext_gap <= distance_tolerance_mm:
                is_tangent = True
                gap = ext_gap
                # Contact point is between centers
                t_c = r1 / center_dist
                contact_pt = Point2D(x=center1.x + t_c * (center2.x - center1.x), y=center1.y + t_c * (center2.y - center1.y))
            elif int_gap <= distance_tolerance_mm and abs(r1 - r2) > distance_tolerance_mm:
                is_tangent = True
                gap = int_gap
                # Contact point along ray from center
                t_c = r1 / max(1e-4, (r1 - r2)) if r1 > r2 else -r1 / max(1e-4, (r2 - r1))
                contact_pt = Point2D(x=center1.x + t_c * (center2.x - center1.x), y=center1.y + t_c * (center2.y - center1.y))

            if not is_tangent or contact_pt is None:
                continue

            # Verify contact point is in sweep for arc primitives
            in_sweep1 = True
            if c1.type == "arc":
                ang1 = math.degrees(math.atan2(contact_pt.y - center1.y, contact_pt.x - center1.x)) % 360.0
                in_sweep1 = _is_angle_in_sweep(ang1, c1.geometry.start_angle_deg, c1.geometry.end_angle_deg, tol_deg=angle_tolerance_deg)

            in_sweep2 = True
            if c2.type == "arc":
                ang2 = math.degrees(math.atan2(contact_pt.y - center2.y, contact_pt.x - center2.x)) % 360.0
                in_sweep2 = _is_angle_in_sweep(ang2, c2.geometry.start_angle_deg, c2.geometry.end_angle_deg, tol_deg=angle_tolerance_deg)

            if in_sweep1 and in_sweep2:
                confidence = max(0.5, 1.0 - (gap / distance_tolerance_mm) * 0.5) if distance_tolerance_mm > 0 else 1.0
                constraints.append(Constraint(
                    type="tangent",
                    primitive_ids=[c1.id, c2.id],
                    confidence=round(confidence, 3),
                    tolerance={"distance_mm": distance_tolerance_mm},
                    measured={"tangent_gap_mm": round(gap, 3)},
                ))

    # 3. Concentricity across Circle-Circle, Circle-Arc, and Arc-Arc
    for i in range(n_curv):
        c1 = curved_all[i]
        for j in range(i + 1, n_curv):
            c2 = curved_all[j]
            center_dist = _point_distance(c1.geometry.center, c2.geometry.center)
            if center_dist <= distance_tolerance_mm:
                confidence = max(0.5, 1.0 - (center_dist / distance_tolerance_mm) * 0.5) if distance_tolerance_mm > 0 else 1.0
                constraints.append(Constraint(
                    type="concentric",
                    primitive_ids=[c1.id, c2.id],
                    confidence=round(confidence, 3),
                    tolerance={"distance_mm": distance_tolerance_mm},
                    measured={"center_distance_mm": round(center_dist, 3)},
                ))

    # 4. Line-Arc Coincident Endpoints
    for line in lines:
        for arc in arcs:
            c = arc.geometry.center
            r = arc.geometry.radius
            s_rad = math.radians(arc.geometry.start_angle_deg)
            e_rad = math.radians(arc.geometry.end_angle_deg)
            arc_p1 = Point2D(x=c.x + r * math.cos(s_rad), y=c.y + r * math.sin(s_rad))
            arc_p2 = Point2D(x=c.x + r * math.cos(e_rad), y=c.y + r * math.sin(e_rad))

            endpoint_pairs = [
                (line.geometry.start, arc_p1),
                (line.geometry.start, arc_p2),
                (line.geometry.end, arc_p1),
                (line.geometry.end, arc_p2),
            ]
            best_dist = min(_point_distance(a, b) for a, b in endpoint_pairs)
            if best_dist <= distance_tolerance_mm:
                confidence = max(0.5, 1.0 - (best_dist / distance_tolerance_mm) * 0.5) if distance_tolerance_mm > 0 else 1.0
                constraints.append(Constraint(
                    type="coincident_endpoint",
                    primitive_ids=[line.id, arc.id],
                    confidence=round(confidence, 3),
                    tolerance={"distance_mm": distance_tolerance_mm},
                    measured={"endpoint_distance_mm": round(best_dist, 3)},
                ))

    # 5. Equal Radius across Arcs and Circles
    for i in range(n_curv):
        c1 = curved_all[i]
        for j in range(i + 1, n_curv):
            c2 = curved_all[j]
            r1, r2 = c1.geometry.radius, c2.geometry.radius
            if r1 > 0 and r2 > 0:
                diff_pct = abs(r1 - r2) / max(r1, r2) * 100.0
                if diff_pct <= length_tolerance_percent:
                    confidence = max(0.5, 1.0 - (diff_pct / length_tolerance_percent) * 0.5) if length_tolerance_percent > 0 else 1.0
                    constraints.append(Constraint(
                        type="equal_length",
                        primitive_ids=[c1.id, c2.id],
                        confidence=round(confidence, 3),
                        tolerance={"length_percent": length_tolerance_percent},
                        measured={"radius_diff_percent": round(diff_pct, 3)},
                    ))

    return constraints
