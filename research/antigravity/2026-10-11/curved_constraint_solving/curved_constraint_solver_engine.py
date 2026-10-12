"""
curved_constraint_solver_engine.py — Reference implementations and benchmarks for
Curved and Concentric Geometric Constraint Solving (Phase 2 constraint solving extensions).

Contract context:
In semantic_ir_lib/constraint_solving.py, current production solve_constraints():
- Only models 'line' primitives (line_by_id)
- Defines _SUPPORTED_TYPES = {"parallel", "perpendicular", "equal_length", "coincident_endpoint", "collinear"}
- Silently skips 'concentric' and 'tangent' constraints (adding them to skipped_constraints)
- Leaves circles and arcs completely unsolved at raw, noisy raster coordinates
- Breaks G1 tangency when adjacent lines move to satisfy linear constraints

This module provides:
- SolvedCurvedPrimitive and CurvedSolveResult dataclasses
- Strategy A: Current Production Main (solve_constraints skips curved constraints)
- Strategy B: Naive Center Snapping (concentric averaging only, ignores tangency)
- Strategy C: Decoupled Line-First Solver (solves lines, naively projects circles)
- Strategy D: Unified 2D Geometric Constraint Solver with SolveSpace Curved Extensions (Selected)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from primitive_ir_lib.models import (
    ArcGeometry, CircleGeometry, LineGeometry, Point2D, Primitive, PrimitiveIRDocument,
)
from semantic_ir_lib.models import Constraint

try:
    import python_solvespace
    from python_solvespace import ResultFlag, SolverSystem
    _HAS_SOLVESPACE = True
except ImportError:
    _HAS_SOLVESPACE = False


@dataclass
class SolvedCurvedPrimitive:
    """Represents a geometrically solved primitive (line, circle, or arc)."""
    primitive_id: str
    type: str  # "line" | "circle" | "arc"
    start: Optional[Point2D] = None
    end: Optional[Point2D] = None
    center: Optional[Point2D] = None
    radius: Optional[float] = None
    start_angle_deg: Optional[float] = None
    end_angle_deg: Optional[float] = None
    displacement_mm: float = 0.0


@dataclass
class CurvedSolveResult:
    """Outcome of curved and linear constraint solving."""
    status: str  # "okay" | "inconsistent" | "didnt_converge" | "too_many_unknowns"
    dof: int = 0
    solved_primitives: Dict[str, SolvedCurvedPrimitive] = field(default_factory=dict)
    skipped_constraints: List[str] = field(default_factory=list)
    applied_constraint_count: int = 0
    applied_concentric_count: int = 0
    applied_tangent_count: int = 0
    applied_equal_radius_count: int = 0
    conflict_constraint_ids: List[str] = field(default_factory=list)


def solve_curved_constraints_strategy_a(
    primitive_doc: PrimitiveIRDocument,
    constraints: List[Constraint],
) -> CurvedSolveResult:
    """Strategy A: Current Production Baseline.

    Delegates to semantic_ir_lib.constraint_solving.solve_constraints().
    Because production only supports lines and skips 'tangent' and 'concentric',
    all curved constraints are skipped and circles/arcs are omitted.
    """
    from semantic_ir_lib.constraint_solving import solve_constraints

    raw_res = solve_constraints(primitive_doc, constraints)
    solved: Dict[str, SolvedCurvedPrimitive] = {}
    for pid, sp in raw_res.solved_primitives.items():
        solved[pid] = SolvedCurvedPrimitive(
            primitive_id=pid,
            type="line",
            start=sp.start,
            end=sp.end,
            displacement_mm=sp.displacement_mm,
        )

    # For primitives not solved by line-only solver, keep original coordinates
    for p in primitive_doc.primitives:
        if p.id not in solved:
            if p.type == "circle" and p.geometry is not None:
                g = p.geometry
                solved[p.id] = SolvedCurvedPrimitive(
                    primitive_id=p.id,
                    type="circle",
                    center=Point2D(g.center.x, g.center.y),
                    radius=g.radius,
                )
            elif p.type == "arc" and p.geometry is not None:
                g = p.geometry
                solved[p.id] = SolvedCurvedPrimitive(
                    primitive_id=p.id,
                    type="arc",
                    center=Point2D(g.center.x, g.center.y),
                    radius=g.radius,
                    start_angle_deg=g.start_angle_deg,
                    end_angle_deg=g.end_angle_deg,
                )

    return CurvedSolveResult(
        status=raw_res.status,
        dof=raw_res.dof,
        solved_primitives=solved,
        skipped_constraints=list(raw_res.skipped_constraints),
        applied_constraint_count=raw_res.applied_constraint_count,
        applied_concentric_count=0,
        applied_tangent_count=0,
        applied_equal_radius_count=0,
        conflict_constraint_ids=list(raw_res.conflict_constraint_ids),
    )


def solve_curved_constraints_strategy_b(
    primitive_doc: PrimitiveIRDocument,
    constraints: List[Constraint],
) -> CurvedSolveResult:
    """Strategy B: Naive Center Snapping.

    Averages the center coordinates of concentric circle pairs, but cannot solve
    line-arc tangency, line-circle tangency, or coupled geometric chains.
    """
    base = solve_curved_constraints_strategy_a(primitive_doc, constraints)
    solved = dict(base.solved_primitives)
    applied_concentric = 0
    skipped: List[str] = list(base.skipped_constraints)

    for c in constraints:
        if c.type == "concentric" and len(c.primitive_ids) == 2:
            a, b = c.primitive_ids
            if a in solved and b in solved and solved[a].center and solved[b].center:
                ca = solved[a].center
                cb = solved[b].center
                avg_x = (ca.x + cb.x) / 2.0
                avg_y = (ca.y + cb.y) / 2.0
                solved[a].center = Point2D(avg_x, avg_y)
                solved[b].center = Point2D(avg_x, avg_y)
                applied_concentric += 1
                if c.id in skipped:
                    skipped.remove(c.id)

    return CurvedSolveResult(
        status=base.status,
        dof=base.dof,
        solved_primitives=solved,
        skipped_constraints=skipped,
        applied_constraint_count=base.applied_constraint_count + applied_concentric,
        applied_concentric_count=applied_concentric,
        applied_tangent_count=0,
        applied_equal_radius_count=0,
    )


def solve_curved_constraints_strategy_c(
    primitive_doc: PrimitiveIRDocument,
    constraints: List[Constraint],
) -> CurvedSolveResult:
    """Strategy C: Decoupled Line-First Solver.

    Solves lines first using line-only solver, then naively projects circles
    onto nearest lines to satisfy tangency. Fails on closed slot profiles or
    when circle constraints should rotate or shift lines.
    """
    base = solve_curved_constraints_strategy_b(primitive_doc, constraints)
    solved = dict(base.solved_primitives)
    applied_tangent = 0
    skipped = list(base.skipped_constraints)

    for c in constraints:
        if c.type == "tangent" and len(c.primitive_ids) == 2:
            a, b = c.primitive_ids
            line_id = a if a in solved and solved[a].type == "line" else (b if b in solved and solved[b].type == "line" else None)
            circ_id = a if a in solved and solved[a].type in ("circle", "arc") else (b if b in solved and solved[b].type in ("circle", "arc") else None)
            if line_id and circ_id:
                lp = solved[line_id]
                cp = solved[circ_id]
                if lp.start and lp.end and cp.center and cp.radius:
                    # Naively snap center y onto line y + radius (assuming horizontal line)
                    dx = lp.end.x - lp.start.x
                    dy = lp.end.y - lp.start.y
                    l_len = math.hypot(dx, dy)
                    if l_len > 1e-9:
                        # Project onto line normal
                        nx, ny = -dy / l_len, dx / l_len
                        # Current distance
                        dist = (cp.center.x - lp.start.x) * nx + (cp.center.y - lp.start.y) * ny
                        sign = 1.0 if dist >= 0 else -1.0
                        shift = (sign * cp.radius) - dist
                        cp.center = Point2D(cp.center.x + nx * shift, cp.center.y + ny * shift)
                        applied_tangent += 1
                        if c.id in skipped:
                            skipped.remove(c.id)

    return CurvedSolveResult(
        status=base.status,
        dof=base.dof,
        solved_primitives=solved,
        skipped_constraints=skipped,
        applied_constraint_count=base.applied_constraint_count + applied_tangent,
        applied_concentric_count=base.applied_concentric_count,
        applied_tangent_count=applied_tangent,
        applied_equal_radius_count=0,
    )


def solve_curved_constraints_strategy_d(
    primitive_doc: PrimitiveIRDocument,
    constraints: List[Constraint],
    *,
    driving_lengths: Sequence[object] = (),
    datum_anchor: object = None,
) -> CurvedSolveResult:
    """Strategy D: Unified 2D Geometric Constraint Solver with SolveSpace Curved Extensions (Selected).

    Formulates a simultaneous 2D constraint system in SolveSpace supporting:
    - Line primitives (2D points start, end, line entity)
    - Circle primitives (2D center point, radius distance, normal 3d)
    - Arc primitives (2D center point, start/end transition points, normal 3d)
    - Constraints:
      - 'parallel', 'perpendicular', 'equal_length', 'coincident_endpoint', 'collinear'
      - 'concentric': coincident center points (circle-circle, circle-arc, arc-arc)
      - 'tangent':
         * line-circle: center point to line distance equals radius
         * line-arc: line endpoint coincident with arc endpoint + line perpendicular to radial segment
         * arc-arc: distance between centers equals r1 + r2 or |r1 - r2|
      - 'equal_radius': equal distance on radial segments
    """
    if not _HAS_SOLVESPACE:
        raise ImportError("python-solvespace is required for Strategy D")

    prims_by_id: Dict[str, Primitive] = {
        p.id: p for p in primitive_doc.primitives if p.geometry is not None
    }
    lines = {pid: p for pid, p in prims_by_id.items() if p.type == "line"}
    circles = {pid: p for pid, p in prims_by_id.items() if p.type == "circle"}
    arcs = {pid: p for pid, p in prims_by_id.items() if p.type == "arc"}

    # Filter constraints relevant to known primitives
    applied_count = 0
    applied_concentric = 0
    applied_tangent = 0
    applied_equal_radius = 0
    skipped: List[str] = []

    # Map status
    status_map = {
        ResultFlag.OKAY: "okay",
        ResultFlag.INCONSISTENT: "inconsistent",
        ResultFlag.DIDNT_CONVERGE: "didnt_converge",
        ResultFlag.TOO_MANY_UNKNOWNS: "too_many_unknowns",
    }

    # Helper function to solve a system attempt
    def _build_and_solve():
        sys = SolverSystem()
        wp = sys.create_2d_base()
        nm = sys.entity(0)

        line_handles = {}
        line_points = {}
        circle_centers = {}
        circle_radii = {}
        arc_centers = {}
        arc_points = {}
        arc_radii = {}

        # 1. Register lines
        for pid, p in lines.items():
            g = p.geometry
            if not (math.isfinite(g.start.x) and math.isfinite(g.start.y) and
                    math.isfinite(g.end.x) and math.isfinite(g.end.y)):
                continue
            p1 = sys.add_point_2d(g.start.x, g.start.y, wp)
            p2 = sys.add_point_2d(g.end.x, g.end.y, wp)
            l = sys.add_line_2d(p1, p2, wp)
            line_handles[pid] = l
            line_points[pid] = (p1, p2)

        # 2. Register circles
        for pid, p in circles.items():
            g = p.geometry
            if not (math.isfinite(g.center.x) and math.isfinite(g.center.y) and math.isfinite(g.radius)) or g.radius <= 0:
                continue
            c_pt = sys.add_point_2d(g.center.x, g.center.y, wp)
            circle_centers[pid] = c_pt
            circle_radii[pid] = float(g.radius)

        # 3. Register arcs
        for pid, p in arcs.items():
            g = p.geometry
            if not (math.isfinite(g.center.x) and math.isfinite(g.center.y) and math.isfinite(g.radius)) or g.radius <= 0:
                continue
            c_pt = sys.add_point_2d(g.center.x, g.center.y, wp)
            # Compute endpoints
            rad_s = math.radians(g.start_angle_deg)
            rad_e = math.radians(g.end_angle_deg)
            sx = g.center.x + g.radius * math.cos(rad_s)
            sy = g.center.y + g.radius * math.sin(rad_s)
            ex = g.center.x + g.radius * math.cos(rad_e)
            ey = g.center.y + g.radius * math.sin(rad_e)
            p_s = sys.add_point_2d(sx, sy, wp)
            p_e = sys.add_point_2d(ex, ey, wp)
            arc_centers[pid] = c_pt
            arc_points[pid] = (p_s, p_e)
            arc_radii[pid] = float(g.radius)

        applied = 0
        app_conc = 0
        app_tang = 0
        app_eq_r = 0
        local_skipped = []

        # 4. Apply constraints
        for c in constraints:
            c_type = c.type
            p_ids = c.primitive_ids
            if len(p_ids) != 2:
                local_skipped.append(c.id)
                continue
            id_a, id_b = p_ids

            # CONCENTRIC (circle-circle, circle-arc, arc-arc)
            if c_type == "concentric":
                center_a = circle_centers.get(id_a) or arc_centers.get(id_a)
                center_b = circle_centers.get(id_b) or arc_centers.get(id_b)
                if center_a and center_b:
                    sys.coincident(center_a, center_b, wp)
                    applied += 1
                    app_conc += 1
                else:
                    local_skipped.append(c.id)

            # EQUAL RADIUS / EQUAL
            elif c_type in ("equal_length", "equal_radius"):
                # If both are circles/arcs
                is_curved_a = id_a in circles or id_a in arcs
                is_curved_b = id_b in circles or id_b in arcs
                if is_curved_a and is_curved_b:
                    # Equal radius
                    r_a = circle_radii.get(id_a) or arc_radii.get(id_a)
                    r_b = circle_radii.get(id_b) or arc_radii.get(id_b)
                    target_r = (r_a + r_b) / 2.0
                    if id_a in circle_radii: circle_radii[id_a] = target_r
                    if id_b in circle_radii: circle_radii[id_b] = target_r
                    if id_a in arc_radii: arc_radii[id_a] = target_r
                    if id_b in arc_radii: arc_radii[id_b] = target_r
                    applied += 1
                    app_eq_r += 1
                elif id_a in line_handles and id_b in line_handles:
                    sys.equal(line_handles[id_a], line_handles[id_b], wp)
                    applied += 1
                else:
                    local_skipped.append(c.id)

            # TANGENT
            elif c_type == "tangent":
                # Case 1: Line and Circle
                line_id = id_a if id_a in line_handles else (id_b if id_b in line_handles else None)
                circ_id = id_a if id_a in circles else (id_b if id_b in circles else None)
                arc_id = id_a if id_a in arcs else (id_b if id_b in arcs else None)

                if line_id and circ_id:
                    c_pt = circle_centers[circ_id]
                    r = circle_radii[circ_id]
                    l = line_handles[line_id]
                    sys.distance(c_pt, l, r, wp)
                    applied += 1
                    app_tang += 1

                # Case 2: Line and Arc (fillet tangency at endpoint)
                elif line_id and arc_id:
                    c_pt = arc_centers[arc_id]
                    r = arc_radii[arc_id]
                    l = line_handles[line_id]
                    l_p1, l_p2 = line_points[line_id]
                    a_ps, a_pe = arc_points[arc_id]

                    # Find closest endpoint pair
                    p_orig = lines[line_id].geometry
                    a_orig = arcs[arc_id].geometry
                    # Test which arc endpoint is closest to line endpoints
                    rad_s = math.radians(a_orig.start_angle_deg)
                    rad_e = math.radians(a_orig.end_angle_deg)
                    as_x, as_y = a_orig.center.x + r * math.cos(rad_s), a_orig.center.y + r * math.sin(rad_s)
                    ae_x, ae_y = a_orig.center.x + r * math.cos(rad_e), a_orig.center.y + r * math.sin(rad_e)

                    d_s1 = math.hypot(p_orig.start.x - as_x, p_orig.start.y - as_y)
                    d_s2 = math.hypot(p_orig.end.x - as_x, p_orig.end.y - as_y)
                    d_e1 = math.hypot(p_orig.start.x - ae_x, p_orig.start.y - ae_y)
                    d_e2 = math.hypot(p_orig.end.x - ae_x, p_orig.end.y - ae_y)
                    min_d = min(d_s1, d_s2, d_e1, d_e2)

                    l_pt = l_p1 if min_d in (d_s1, d_e1) else l_p2
                    a_pt = a_ps if min_d in (d_s1, d_s2) else a_pe

                    sys.coincident(l_pt, a_pt, wp)
                    r_seg = sys.add_line_2d(c_pt, a_pt, wp)
                    sys.perpendicular(l, r_seg, wp)
                    sys.distance(c_pt, a_pt, r, wp)
                    applied += 1
                    app_tang += 1

                # Case 3: Circle-Circle or Arc-Arc tangency
                elif (circ_id or arc_id) and (id_b in circles or id_b in arcs):
                    ca = circle_centers.get(id_a) or arc_centers.get(id_a)
                    cb = circle_centers.get(id_b) or arc_centers.get(id_b)
                    ra = circle_radii.get(id_a) or arc_radii.get(id_a)
                    rb = circle_radii.get(id_b) or arc_radii.get(id_b)
                    if ca and cb and ra and rb:
                        # Determine if external or internal
                        orig_a = circles.get(id_a) or arcs.get(id_a)
                        orig_b = circles.get(id_b) or arcs.get(id_b)
                        cur_dist = math.hypot(orig_a.geometry.center.x - orig_b.geometry.center.x,
                                              orig_a.geometry.center.y - orig_b.geometry.center.y)
                        if abs(cur_dist - (ra + rb)) < abs(cur_dist - abs(ra - rb)):
                            target_dist = ra + rb
                        else:
                            target_dist = abs(ra - rb)
                        sys.distance(ca, cb, target_dist, wp)
                        applied += 1
                        app_tang += 1
                    else:
                        local_skipped.append(c.id)
                else:
                    local_skipped.append(c.id)

            # STANDARD LINE CONSTRAINTS
            elif id_a in line_handles and id_b in line_handles:
                la, lb = line_handles[id_a], line_handles[id_b]
                if c_type == "parallel":
                    sys.parallel(la, lb, wp)
                    applied += 1
                elif c_type == "perpendicular":
                    sys.perpendicular(la, lb, wp)
                    applied += 1
                elif c_type == "coincident_endpoint":
                    pt_a_s, pt_a_e = line_points[id_a]
                    pt_b_s, pt_b_e = line_points[id_b]
                    geom_a, geom_b = lines[id_a].geometry, lines[id_b].geometry
                    dists = [
                        (math.hypot(geom_a.start.x - geom_b.start.x, geom_a.start.y - geom_b.start.y), pt_a_s, pt_b_s),
                        (math.hypot(geom_a.start.x - geom_b.end.x, geom_a.start.y - geom_b.end.y), pt_a_s, pt_b_e),
                        (math.hypot(geom_a.end.x - geom_b.start.x, geom_a.end.y - geom_b.start.y), pt_a_e, pt_b_s),
                        (math.hypot(geom_a.end.x - geom_b.end.x, geom_a.end.y - geom_b.end.y), pt_a_e, pt_b_e),
                    ]
                    _, best_a, best_b = min(dists, key=lambda x: x[0])
                    sys.coincident(best_a, best_b, wp)
                    applied += 1
                elif c_type == "collinear":
                    pt_b_s, _ = line_points[id_b]
                    sys.coincident(pt_b_s, la, wp)
                    applied += 1
                else:
                    local_skipped.append(c.id)
            else:
                local_skipped.append(c.id)

        flag = sys.solve()
        status_str = status_map.get(flag, f"unknown({flag})")
        return (
            status_str, sys, line_points, circle_centers, circle_radii,
            arc_centers, arc_points, arc_radii, applied, app_conc, app_tang, app_eq_r, local_skipped,
        )

    (
        status, sys, line_pts, circ_cts, circ_rs,
        arc_cts, arc_pts, arc_rs, applied_count, applied_concentric, applied_tangent, applied_equal_radius, skipped,
    ) = _build_and_solve()

    solved: Dict[str, SolvedCurvedPrimitive] = {}

    # Extract solved lines
    for pid, (p1, p2) in line_pts.items():
        sx, sy = sys.params(p1.params)
        ex, ey = sys.params(p2.params)
        orig = lines[pid].geometry
        disp = math.hypot(sx - orig.start.x, sy - orig.start.y) + math.hypot(ex - orig.end.x, ey - orig.end.y)
        solved[pid] = SolvedCurvedPrimitive(
            primitive_id=pid,
            type="line",
            start=Point2D(round(sx, 6), round(sy, 6)),
            end=Point2D(round(ex, 6), round(ey, 6)),
            displacement_mm=round(disp, 6),
        )

    # Extract solved circles
    for pid, c_pt in circ_cts.items():
        cx, cy = sys.params(c_pt.params)
        r = circ_rs[pid]
        orig = circles[pid].geometry
        disp = math.hypot(cx - orig.center.x, cy - orig.center.y)
        solved[pid] = SolvedCurvedPrimitive(
            primitive_id=pid,
            type="circle",
            center=Point2D(round(cx, 6), round(cy, 6)),
            radius=round(r, 6),
            displacement_mm=round(disp, 6),
        )

    # Extract solved arcs
    for pid, c_pt in arc_cts.items():
        cx, cy = sys.params(c_pt.params)
        r = arc_rs[pid]
        p_s, p_e = arc_pts[pid]
        sx, sy = sys.params(p_s.params)
        ex, ey = sys.params(p_e.params)
        # Recalculate angles from center to endpoints
        start_ang = math.degrees(math.atan2(sy - cy, sx - cx)) % 360.0
        end_ang = math.degrees(math.atan2(ey - cy, ex - cx)) % 360.0
        orig = arcs[pid].geometry
        disp = math.hypot(cx - orig.center.x, cy - orig.center.y)
        solved[pid] = SolvedCurvedPrimitive(
            primitive_id=pid,
            type="arc",
            center=Point2D(round(cx, 6), round(cy, 6)),
            radius=round(r, 6),
            start_angle_deg=round(start_ang, 4),
            end_angle_deg=round(end_ang, 4),
            displacement_mm=round(disp, 6),
        )

    # Carry through unconstrained primitives
    for pid, p in prims_by_id.items():
        if pid not in solved:
            if p.type == "circle":
                solved[pid] = SolvedCurvedPrimitive(
                    primitive_id=pid, type="circle",
                    center=Point2D(p.geometry.center.x, p.geometry.center.y),
                    radius=p.geometry.radius,
                )
            elif p.type == "arc":
                solved[pid] = SolvedCurvedPrimitive(
                    primitive_id=pid, type="arc",
                    center=Point2D(p.geometry.center.x, p.geometry.center.y),
                    radius=p.geometry.radius,
                    start_angle_deg=p.geometry.start_angle_deg,
                    end_angle_deg=p.geometry.end_angle_deg,
                )
            elif p.type == "line":
                solved[pid] = SolvedCurvedPrimitive(
                    primitive_id=pid, type="line",
                    start=Point2D(p.geometry.start.x, p.geometry.start.y),
                    end=Point2D(p.geometry.end.x, p.geometry.end.y),
                )

    return CurvedSolveResult(
        status=status,
        dof=sys.dof() if hasattr(sys, "dof") else 0,
        solved_primitives=solved,
        skipped_constraints=skipped,
        applied_constraint_count=applied_count,
        applied_concentric_count=applied_concentric,
        applied_tangent_count=applied_tangent,
        applied_equal_radius_count=applied_equal_radius,
        conflict_constraint_ids=[],
    )


# Production alias
solve_curved_constraints = solve_curved_constraints_strategy_d
