"""
symmetry_constraint_engine.py
Empirical Research Engine for Symmetry Axis & Symmetric Feature Constraint Detection & Solving (V1).

Compares:
- Strategy A: Current Production Baseline (semantic_ir_lib detect_constraints / detect_circle_constraints)
- Strategy B: Bounding Box Midpoint Pairing
- Strategy C: Pairwise Perpendicular Bisector Induction
- Strategy D: Consensus Axis & Reflection Invariant Oracle
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Sequence, Tuple, Union

from primitive_ir_lib.models import Point2D, Primitive, LineGeometry, CircleGeometry, PrimitiveIRDocument
from semantic_ir_lib.models import Constraint
from semantic_ir_lib.constraint_detection import (
    detect_constraints as prod_detect_constraints,
    detect_circle_constraints as prod_detect_circle_constraints,
)

# Safe dimensionless bounds & thresholds
DEFAULT_DISTANCE_TOL_MM = 5.0
DEFAULT_ANGLE_TOL_DEG = 3.0
DEFAULT_LENGTH_TOL_PERCENT = 3.0
AXIS_CONSENSUS_MIN_PAIRS = 2
AXIS_ANGLE_CLUSTER_TOL_DEG = 1.5
AXIS_OFFSET_CLUSTER_TOL_MM = 2.0


@dataclass(frozen=True)
class SymmetryAxis:
    id: str
    start: Point2D
    end: Point2D
    is_explicit: bool
    confidence: float
    source_primitive_id: Optional[str] = None

    @property
    def length(self) -> float:
        return math.hypot(self.end.x - self.start.x, self.end.y - self.start.y)

    @property
    def angle_deg(self) -> float:
        return math.degrees(math.atan2(self.end.y - self.start.y, self.end.x - self.start.x)) % 180.0


@dataclass
class SymmetricPair:
    feature_type: Literal["line_pair", "circle_pair", "self_symmetric_line"]
    primitive_ids: List[str]
    axis_id: str
    confidence: float
    endpoint_pairing: Optional[Tuple[str, str]] = None  # ("start", "start"), ("end", "end") or ("start", "end")
    measured: dict = field(default_factory=dict)
    tolerance: dict = field(default_factory=dict)


@dataclass
class SymmetryDetectionResult:
    axes: List[SymmetryAxis] = field(default_factory=list)
    symmetric_pairs: List[SymmetricPair] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Geometric Utilities
# ---------------------------------------------------------------------------

def point_distance(p1: Point2D, p2: Point2D) -> float:
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def line_orientation_deg(start: Point2D, end: Point2D) -> float:
    return math.degrees(math.atan2(end.y - start.y, end.x - start.x)) % 180.0


def angle_difference_deg(a: float, b: float) -> float:
    diff = abs(a - b) % 180.0
    return min(diff, 180.0 - diff)


def point_to_infinite_line_signed_distance(pt: Point2D, line_start: Point2D, line_end: Point2D) -> Tuple[float, Point2D, Point2D]:
    """Returns (signed_distance, unit_normal, projection_point)."""
    dx = line_end.x - line_start.x
    dy = line_end.y - line_start.y
    seg_len = math.hypot(dx, dy)
    if seg_len == 0:
        return point_distance(pt, line_start), Point2D(0.0, 0.0), line_start

    ux = dx / seg_len
    uy = dy / seg_len
    nx = -uy
    ny = ux

    vx = pt.x - line_start.x
    vy = pt.y - line_start.y
    signed_dist = vx * nx + vy * ny
    proj_dist = vx * ux + vy * uy
    proj_pt = Point2D(line_start.x + proj_dist * ux, line_start.y + proj_dist * uy)
    return signed_dist, Point2D(nx, ny), proj_pt


def reflect_point(pt: Point2D, line_start: Point2D, line_end: Point2D) -> Point2D:
    signed_dist, normal, _ = point_to_infinite_line_signed_distance(pt, line_start, line_end)
    return Point2D(pt.x - 2.0 * signed_dist * normal.x, pt.y - 2.0 * signed_dist * normal.y)


# ---------------------------------------------------------------------------
# Strategy A: Current Production Baseline
# ---------------------------------------------------------------------------

def detect_symmetry_strategy_a(
    lines: List[Primitive],
    circles: List[Primitive],
    distance_tolerance_mm: float = DEFAULT_DISTANCE_TOL_MM,
) -> SymmetryDetectionResult:
    """Current production baseline: calls existing detect_constraints and detect_circle_constraints.
    Does NOT detect any symmetry axes or symmetric constraints.
    """
    valid_lines = [p for p in lines if p.type == "line" and p.geometry is not None]
    valid_circles = [p for p in circles if p.type == "circle" and p.geometry is not None]

    base_constraints = prod_detect_constraints(valid_lines)
    circle_constraints = prod_detect_circle_constraints(valid_lines, valid_circles)
    all_constraints = base_constraints + circle_constraints

    # Baseline has 0 symmetry axes, 0 symmetric pairs
    return SymmetryDetectionResult(
        axes=[],
        symmetric_pairs=[],
        constraints=all_constraints,
    )


# ---------------------------------------------------------------------------
# Strategy B: Bounding Box Midpoint Pairing
# ---------------------------------------------------------------------------

def detect_symmetry_strategy_b(
    lines: List[Primitive],
    circles: List[Primitive],
    distance_tolerance_mm: float = DEFAULT_DISTANCE_TOL_MM,
) -> SymmetryDetectionResult:
    """Strategy B: Bounding Box Midpoint Pairing.
    Computes global bounding box center (cx, cy) and checks horizontal/vertical axis reflection.
    Fails when part has asymmetric protrusions, diagonal axes, or multi-axis features.
    """
    valid_lines = [p for p in lines if p.type == "line" and p.geometry is not None]
    valid_circles = [p for p in circles if p.type == "circle" and p.geometry is not None]

    all_pts: List[Point2D] = []
    for l in valid_lines:
        all_pts.extend([l.geometry.start, l.geometry.end])
    for c in valid_circles:
        all_pts.append(c.geometry.center)

    if not all_pts:
        return SymmetryDetectionResult()

    min_x = min(p.x for p in all_pts)
    max_x = max(p.x for p in all_pts)
    min_y = min(p.y for p in all_pts)
    max_y = max(p.y for p in all_pts)
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    # Test horizontal axis (y = cy) and vertical axis (x = cx)
    h_axis = SymmetryAxis("axis_bbox_h", Point2D(min_x, cy), Point2D(max_x, cy), False, 0.6)
    v_axis = SymmetryAxis("axis_bbox_v", Point2D(cx, min_y), Point2D(cx, max_y), False, 0.6)

    candidates = [h_axis, v_axis]
    best_axis: Optional[SymmetryAxis] = None
    best_pairs: List[SymmetricPair] = []

    for axis in candidates:
        pairs: List[SymmetricPair] = []
        # Test lines
        n_lines = len(valid_lines)
        for i in range(n_lines):
            li = valid_lines[i]
            for j in range(i + 1, n_lines):
                lj = valid_lines[j]
                # Midpoint check
                m1 = Point2D((li.geometry.start.x + li.geometry.end.x)/2, (li.geometry.start.y + li.geometry.end.y)/2)
                m2 = Point2D((lj.geometry.start.x + lj.geometry.end.x)/2, (lj.geometry.start.y + lj.geometry.end.y)/2)
                m_avg = Point2D((m1.x + m2.x)/2, (m1.y + m2.y)/2)
                d_to_axis, _, _ = point_to_infinite_line_signed_distance(m_avg, axis.start, axis.end)
                if abs(d_to_axis) <= distance_tolerance_mm:
                    # check length
                    l1 = li.geometry.length()
                    l2 = lj.geometry.length()
                    if max(l1, l2) > 0 and abs(l1 - l2)/max(l1, l2) <= 0.10:
                        pairs.append(SymmetricPair(
                            feature_type="line_pair",
                            primitive_ids=[li.id, lj.id],
                            axis_id=axis.id,
                            confidence=0.65,
                            measured={"midpoint_dist": abs(d_to_axis)},
                        ))
        if len(pairs) > len(best_pairs):
            best_pairs = pairs
            best_axis = axis

    axes = [best_axis] if best_axis and best_pairs else []
    constraints = [
        Constraint(
            type="parallel",  # Strategy B falls back to parallel
            primitive_ids=p.primitive_ids,
            confidence=p.confidence,
            tolerance={"distance_mm": distance_tolerance_mm},
        )
        for p in best_pairs
    ]
    return SymmetryDetectionResult(axes=axes, symmetric_pairs=best_pairs, constraints=constraints)


# ---------------------------------------------------------------------------
# Strategy C: Pairwise Perpendicular Bisector Induction
# ---------------------------------------------------------------------------

def detect_symmetry_strategy_c(
    lines: List[Primitive],
    circles: List[Primitive],
    distance_tolerance_mm: float = DEFAULT_DISTANCE_TOL_MM,
) -> SymmetryDetectionResult:
    """Strategy C: Pairwise Perpendicular Bisector Induction.
    For every pair of primitives, forms an ad-hoc bisector line.
    Suffers from O(N^2) pseudo-axes, conflicting pairwise lines, and no consensus.
    """
    valid_lines = [p for p in lines if p.type == "line" and p.geometry is not None]
    n_lines = len(valid_lines)
    axes: List[SymmetryAxis] = []
    pairs: List[SymmetricPair] = []

    for i in range(n_lines):
        li = valid_lines[i]
        for j in range(i + 1, n_lines):
            lj = valid_lines[j]
            m1 = Point2D((li.geometry.start.x + li.geometry.end.x)/2, (li.geometry.start.y + li.geometry.end.y)/2)
            m2 = Point2D((lj.geometry.start.x + lj.geometry.end.x)/2, (lj.geometry.start.y + lj.geometry.end.y)/2)
            d = point_distance(m1, m2)
            if d < 1e-4:
                continue
            # Midpoint between m1 and m2
            mid = Point2D((m1.x + m2.x)/2, (m1.y + m2.y)/2)
            # Perpendicular vector
            vx = m2.x - m1.x
            vy = m2.y - m1.y
            perp = Point2D(-vy / d, vx / d)
            axis_start = Point2D(mid.x - 50.0 * perp.x, mid.y - 50.0 * perp.y)
            axis_end = Point2D(mid.x + 50.0 * perp.x, mid.y + 50.0 * perp.y)
            ax_id = f"axis_c_{i}_{j}"
            axis = SymmetryAxis(ax_id, axis_start, axis_end, False, 0.5)
            axes.append(axis)
            pairs.append(SymmetricPair(
                feature_type="line_pair",
                primitive_ids=[li.id, lj.id],
                axis_id=ax_id,
                confidence=0.5,
                measured={"mid_dist": d},
            ))

    constraints = [
        Constraint(
            type="parallel",
            primitive_ids=p.primitive_ids,
            confidence=p.confidence,
            tolerance={"distance_mm": distance_tolerance_mm},
        )
        for p in pairs
    ]
    return SymmetryDetectionResult(axes=axes, symmetric_pairs=pairs, constraints=constraints)


# ---------------------------------------------------------------------------
# Strategy D: Consensus Axis & Reflection Invariant Oracle
# ---------------------------------------------------------------------------

def is_explicit_centerline(p: Primitive) -> bool:
    """Detects if a primitive is explicitly annotated as a centerline or axis."""
    if p.type != "line" or p.geometry is None:
        return False
    # Check layer / role / linetype metadata if present
    layer = str(getattr(p, "layer", "") or "").lower()
    role = str(getattr(p, "role", "") or "").lower()
    linetype = str(getattr(p, "linetype", "") or "").lower()

    centerline_markers = ["center", "axis", "tam", "truc", "symmetry", "dashdot"]
    for marker in centerline_markers:
        if marker in layer or marker in role or marker in linetype:
            return True
    return False


def _cluster_axes(candidate_axes: List[SymmetryAxis]) -> List[SymmetryAxis]:
    """Clusters candidate axes by orientation angle and perpendicular offset."""
    clusters: List[List[SymmetryAxis]] = []
    for ax in candidate_axes:
        matched = False
        for c in clusters:
            rep = c[0]
            if angle_difference_deg(ax.angle_deg, rep.angle_deg) <= AXIS_ANGLE_CLUSTER_TOL_DEG:
                # Perpendicular distance from ax.start to rep line
                d1, _, _ = point_to_infinite_line_signed_distance(ax.start, rep.start, rep.end)
                d2, _, _ = point_to_infinite_line_signed_distance(ax.end, rep.start, rep.end)
                if max(abs(d1), abs(d2)) <= AXIS_OFFSET_CLUSTER_TOL_MM:
                    c.append(ax)
                    matched = True
                    break
        if not matched:
            clusters.append([ax])

    result: List[SymmetryAxis] = []
    for idx, c in enumerate(clusters):
        # If cluster contains an explicit datum axis, preserve it pristine (never average with noisy inferred lines)
        explicit_axes = [ax for ax in c if ax.is_explicit]
        if explicit_axes:
            rep = explicit_axes[0]
            result.append(SymmetryAxis(
                id=rep.id,
                start=rep.start,
                end=rep.end,
                is_explicit=True,
                confidence=1.0,
                source_primitive_id=rep.source_primitive_id,
            ))
        elif len(c) >= AXIS_CONSENSUS_MIN_PAIRS:
            # Average start and end for purely inferred candidate axes
            avg_sx = sum(ax.start.x for ax in c) / len(c)
            avg_sy = sum(ax.start.y for ax in c) / len(c)
            avg_ex = sum(ax.end.x for ax in c) / len(c)
            avg_ey = sum(ax.end.y for ax in c) / len(c)
            conf = min(0.95, 0.70 + 0.05 * len(c))
            result.append(SymmetryAxis(
                id=f"sym_axis_{idx + 1}",
                start=Point2D(avg_sx, avg_sy),
                end=Point2D(avg_ex, avg_ey),
                is_explicit=False,
                confidence=round(conf, 3),
            ))
    return result


def detect_symmetry_strategy_d(
    lines: List[Primitive],
    circles: List[Primitive],
    explicit_axes: Optional[List[SymmetryAxis]] = None,
    distance_tolerance_mm: float = DEFAULT_DISTANCE_TOL_MM,
    angle_tolerance_deg: float = DEFAULT_ANGLE_TOL_DEG,
    length_tolerance_percent: float = DEFAULT_LENGTH_TOL_PERCENT,
) -> SymmetryDetectionResult:
    """Strategy D: Consensus Axis & Reflection Invariant Oracle.
    1. Identifies explicit centerlines and clusters inferred candidate axes from agreeing pairs.
    2. Performs exact metric reflection mapping for line pairs, circle pairs, and self-symmetric lines.
    3. Synthesizes validated Constraint(type='symmetric') objects for solver integration.
    """
    valid_lines = [p for p in lines if p.type == "line" and p.geometry is not None]
    valid_circles = [p for p in circles if p.type == "circle" and p.geometry is not None]
    n_lines = len(valid_lines)
    n_circ = len(valid_circles)

    # Non-finite coordinate safety
    for p in valid_lines:
        geom = p.geometry
        if not (math.isfinite(geom.start.x) and math.isfinite(geom.start.y) and
                math.isfinite(geom.end.x) and math.isfinite(geom.end.y)):
            raise ValueError(f"Line {p.id} contains non-finite coordinates")
    for p in valid_circles:
        geom = p.geometry
        if not (math.isfinite(geom.center.x) and math.isfinite(geom.center.y) and math.isfinite(geom.radius)):
            raise ValueError(f"Circle {p.id} contains non-finite coordinates or radius")

    # Step 1: Discover candidate axes
    candidate_axes: List[SymmetryAxis] = []
    if explicit_axes:
        candidate_axes.extend(explicit_axes)

    # Check for tagged centerlines in primitives
    for p in valid_lines:
        if is_explicit_centerline(p):
            candidate_axes.append(SymmetryAxis(
                id=f"axis_{p.id}",
                start=p.geometry.start,
                end=p.geometry.end,
                is_explicit=True,
                confidence=1.0,
                source_primitive_id=p.id,
            ))

    # If no explicit axes, infer candidate axes from parallel lines and circle pairs
    if not candidate_axes:
        n_lines = len(valid_lines)
        for i in range(n_lines):
            li = valid_lines[i]
            len_i = li.geometry.length()
            if len_i <= 1e-4:
                continue
            ori_i = line_orientation_deg(li.geometry.start, li.geometry.end)
            for j in range(i + 1, n_lines):
                lj = valid_lines[j]
                len_j = lj.geometry.length()
                if len_j <= 1e-4:
                    continue
                ori_j = line_orientation_deg(lj.geometry.start, lj.geometry.end)
                # Parallel check
                if angle_difference_deg(ori_i, ori_j) <= angle_tolerance_deg:
                    len_pct = abs(len_i - len_j) / max(len_i, len_j) * 100.0
                    if len_pct <= length_tolerance_percent:
                        # Midline between them
                        m_start = Point2D((li.geometry.start.x + lj.geometry.start.x) / 2.0, (li.geometry.start.y + lj.geometry.start.y) / 2.0)
                        m_end = Point2D((li.geometry.end.x + lj.geometry.end.x) / 2.0, (li.geometry.end.y + lj.geometry.end.y) / 2.0)
                        if point_distance(m_start, m_end) > 1e-4:
                            candidate_axes.append(SymmetryAxis(
                                id=f"inferred_{li.id}_{lj.id}",
                                start=m_start,
                                end=m_end,
                                is_explicit=False,
                                confidence=0.7,
                            ))

        # Also infer candidate axes from circle pairs of equal radius
        n_circ = len(valid_circles)
        for i in range(n_circ):
            ci = valid_circles[i]
            for j in range(i + 1, n_circ):
                cj = valid_circles[j]
                if abs(ci.geometry.radius - cj.geometry.radius) <= distance_tolerance_mm:
                    c1 = ci.geometry.center
                    c2 = cj.geometry.center
                    d = point_distance(c1, c2)
                    if d >= distance_tolerance_mm:
                        mid = Point2D((c1.x + c2.x) / 2.0, (c1.y + c2.y) / 2.0)
                        # Perpendicular bisector
                        dx = c2.x - c1.x
                        dy = c2.y - c1.y
                        nx = -dy / d
                        ny = dx / d
                        candidate_axes.append(SymmetryAxis(
                            id=f"inferred_circ_{ci.id}_{cj.id}",
                            start=Point2D(mid.x - 50.0 * nx, mid.y - 50.0 * ny),
                            end=Point2D(mid.x + 50.0 * nx, mid.y + 50.0 * ny),
                            is_explicit=False,
                            confidence=0.75,
                        ))

    active_axes = _cluster_axes(candidate_axes)
    if not active_axes:
        return SymmetryDetectionResult()

    symmetric_pairs: List[SymmetricPair] = []
    constraints: List[Constraint] = []
    seen_pairs: set = set()

    for axis in active_axes:
        ax_start = axis.start
        ax_end = axis.end
        ax_angle = axis.angle_deg

        # 1. Line pairs reflection evaluation
        for i in range(n_lines):
            li = valid_lines[i]
            # Don't pair centerline with itself
            if axis.source_primitive_id and li.id == axis.source_primitive_id:
                continue
            s1, e1 = li.geometry.start, li.geometry.end
            len_1 = li.geometry.length()
            if len_1 <= 1e-4:
                continue

            # Check self-symmetric line (perpendicular to axis, bisected by axis)
            s1_ref = reflect_point(s1, ax_start, ax_end)
            e1_ref = reflect_point(e1, ax_start, ax_end)
            d_self_swap = max(point_distance(s1, e1_ref), point_distance(e1, s1_ref))
            if d_self_swap <= distance_tolerance_mm:
                key = (li.id,)
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    conf = max(0.5, 1.0 - (d_self_swap / distance_tolerance_mm) * 0.5)
                    symmetric_pairs.append(SymmetricPair(
                        feature_type="self_symmetric_line",
                        primitive_ids=[li.id],
                        axis_id=axis.id,
                        confidence=round(conf, 3),
                        endpoint_pairing=("start", "end"),
                        measured={"endpoint_reflection_gap_mm": round(d_self_swap, 3)},
                        tolerance={"distance_mm": distance_tolerance_mm},
                    ))
                    constraints.append(Constraint(
                        type="perpendicular",
                        primitive_ids=[li.id, axis.source_primitive_id or li.id],
                        confidence=round(conf, 3),
                        tolerance={"distance_mm": distance_tolerance_mm},
                        measured={"self_symmetric_gap_mm": round(d_self_swap, 3)},
                    ))

            for j in range(i + 1, n_lines):
                lj = valid_lines[j]
                if axis.source_primitive_id and lj.id == axis.source_primitive_id:
                    continue
                pair_key = tuple(sorted([li.id, lj.id]))
                if pair_key in seen_pairs:
                    continue

                len_2 = lj.geometry.length()
                if len_2 <= 1e-4:
                    continue

                # Length difference check
                len_pct = abs(len_1 - len_2) / max(len_1, len_2) * 100.0
                if len_pct > length_tolerance_percent * 2.0:
                    continue

                s2, e2 = lj.geometry.start, lj.geometry.end

                # Direct pairing: s2 matches s1_ref, e2 matches e1_ref
                d_direct = max(point_distance(s2, s1_ref), point_distance(e2, e1_ref))
                # Reversed pairing: s2 matches e1_ref, e2 matches s1_ref
                d_reversed = max(point_distance(s2, e1_ref), point_distance(e2, s1_ref))

                best_gap = min(d_direct, d_reversed)
                if best_gap <= distance_tolerance_mm:
                    pairing = ("start", "start") if d_direct <= d_reversed else ("start", "end")
                    seen_pairs.add(pair_key)
                    conf = max(0.5, 1.0 - (best_gap / distance_tolerance_mm) * 0.5)
                    symmetric_pairs.append(SymmetricPair(
                        feature_type="line_pair",
                        primitive_ids=[li.id, lj.id],
                        axis_id=axis.id,
                        confidence=round(conf, 3),
                        endpoint_pairing=pairing,
                        measured={"reflection_gap_mm": round(best_gap, 3), "length_diff_pct": round(len_pct, 2)},
                        tolerance={"distance_mm": distance_tolerance_mm},
                    ))
                    # Synthesize semantic Constraint with explicit endpoint mapping
                    constraints.append(Constraint(
                        type="symmetric",  # Extended constraint type
                        primitive_ids=[li.id, lj.id],
                        confidence=round(conf, 3),
                        tolerance={"distance_mm": distance_tolerance_mm, "angle_deg": angle_tolerance_deg},
                        measured={
                            "reflection_gap_mm": round(best_gap, 3),
                            "axis_id": axis.id,
                            "pairing": f"{pairing[0]}_{pairing[1]}",
                        },
                    ))

        # 2. Circle pairs reflection evaluation
        for i in range(n_circ):
            ci = valid_circles[i]
            c1 = ci.geometry.center
            r1 = ci.geometry.radius
            c1_ref = reflect_point(c1, ax_start, ax_end)

            for j in range(i + 1, n_circ):
                cj = valid_circles[j]
                pair_key = tuple(sorted([ci.id, cj.id]))
                if pair_key in seen_pairs:
                    continue

                c2 = cj.geometry.center
                r2 = cj.geometry.radius

                # Radius match
                r_diff = abs(r1 - r2)
                if r_diff > distance_tolerance_mm:
                    continue

                center_gap = point_distance(c2, c1_ref)
                if center_gap <= distance_tolerance_mm:
                    seen_pairs.add(pair_key)
                    conf = max(0.5, 1.0 - (center_gap / distance_tolerance_mm) * 0.5)
                    symmetric_pairs.append(SymmetricPair(
                        feature_type="circle_pair",
                        primitive_ids=[ci.id, cj.id],
                        axis_id=axis.id,
                        confidence=round(conf, 3),
                        endpoint_pairing=("center", "center"),
                        measured={"center_gap_mm": round(center_gap, 3), "radius_diff_mm": round(r_diff, 3)},
                        tolerance={"distance_mm": distance_tolerance_mm},
                    ))
                    constraints.append(Constraint(
                        type="symmetric",
                        primitive_ids=[ci.id, cj.id],
                        confidence=round(conf, 3),
                        tolerance={"distance_mm": distance_tolerance_mm},
                        measured={
                            "center_gap_mm": round(center_gap, 3),
                            "axis_id": axis.id,
                        },
                    ))

    return SymmetryDetectionResult(
        axes=active_axes,
        symmetric_pairs=symmetric_pairs,
        constraints=constraints,
    )


# ---------------------------------------------------------------------------
# SolveSpace Symmetry Formulation & Solving
# ---------------------------------------------------------------------------

@dataclass
class SymmetrySolveResult:
    status: str
    dof: int
    solved_coordinates: Dict[str, Tuple[Point2D, Point2D]] = field(default_factory=dict)
    applied_symmetry_count: int = 0
    symmetry_residual_mm: float = 0.0


def solve_with_symmetry_constraints(
    primitive_doc: PrimitiveIRDocument,
    symmetric_pairs: List[SymmetricPair],
    axes: List[SymmetryAxis],
) -> SymmetrySolveResult:
    """Builds a python-solvespace SolverSystem and solves with sys.symmetric constraints."""
    try:
        import python_solvespace as ps
    except ImportError as e:
        raise ImportError("python_solvespace is required for symmetry solving") from e

    sys = ps.SolverSystem()
    wp = sys.create_2d_base()

    line_by_id = {p.id: p for p in primitive_doc.primitives if p.type == "line" and p.geometry is not None}
    axis_by_id = {ax.id: ax for ax in axes}

    point_handles: Dict[str, Tuple[object, object]] = {}
    line_handles: Dict[str, object] = {}

    # Register lines
    for pid, prim in line_by_id.items():
        s, e = prim.geometry.start, prim.geometry.end
        p_start = sys.add_point_2d(s.x, s.y, wp)
        p_end = sys.add_point_2d(e.x, e.y, wp)
        point_handles[pid] = (p_start, p_end)
        line_handles[pid] = sys.add_line_2d(p_start, p_end, wp)

    # Register symmetry axes in solvespace
    axis_line_handles: Dict[str, object] = {}
    for ax in axes:
        if ax.source_primitive_id and ax.source_primitive_id in line_handles:
            axis_line_handles[ax.id] = line_handles[ax.source_primitive_id]
            p_ax1, p_ax2 = point_handles[ax.source_primitive_id]
            sys.dragged(p_ax1, wp)
            sys.dragged(p_ax2, wp)
        else:
            p_ax1 = sys.add_point_2d(ax.start.x, ax.start.y, wp)
            p_ax2 = sys.add_point_2d(ax.end.x, ax.end.y, wp)
            sys.dragged(p_ax1, wp)
            sys.dragged(p_ax2, wp)
            axis_line_handles[ax.id] = sys.add_line_2d(p_ax1, p_ax2, wp)

    applied_sym = 0
    for pair in symmetric_pairs:
        if pair.axis_id not in axis_line_handles:
            continue
        ax_line = axis_line_handles[pair.axis_id]

        if pair.feature_type == "line_pair":
            p1_id, p2_id = pair.primitive_ids[0], pair.primitive_ids[1]
            if p1_id not in point_handles or p2_id not in point_handles:
                continue
            p1_start, p1_end = point_handles[p1_id]
            p2_start, p2_end = point_handles[p2_id]

            if pair.endpoint_pairing == ("start", "start"):
                sys.symmetric(p1_start, p2_start, ax_line, wp)
                sys.symmetric(p1_end, p2_end, ax_line, wp)
            else:
                sys.symmetric(p1_start, p2_end, ax_line, wp)
                sys.symmetric(p1_end, p2_start, ax_line, wp)
            applied_sym += 1

    res_flag = sys.solve()
    status_map = {0: "okay", 1: "inconsistent", 2: "didnt_converge", 3: "too_many_unknowns"}
    status = status_map.get(res_flag, f"unknown_{res_flag}")

    solved_coords: Dict[str, Tuple[Point2D, Point2D]] = {}
    max_residual = 0.0

    if status == "okay":
        for pid, (p_start, p_end) in point_handles.items():
            sx, sy = sys.params(p_start.params)
            ex, ey = sys.params(p_end.params)
            solved_coords[pid] = (Point2D(sx, sy), Point2D(ex, ey))

        # Check symmetry residual on solved pairs
        for pair in symmetric_pairs:
            if pair.feature_type == "line_pair":
                p1_id, p2_id = pair.primitive_ids[0], pair.primitive_ids[1]
                if p1_id in solved_coords and p2_id in solved_coords:
                    s1, e1 = solved_coords[p1_id]
                    s2, e2 = solved_coords[p2_id]
                    ax = axis_by_id[pair.axis_id]
                    s1_ref = reflect_point(s1, ax.start, ax.end)
                    e1_ref = reflect_point(e1, ax.start, ax.end)
                    if pair.endpoint_pairing == ("start", "start"):
                        res = max(point_distance(s2, s1_ref), point_distance(e2, e1_ref))
                    else:
                        res = max(point_distance(s2, e1_ref), point_distance(e2, s1_ref))
                    max_residual = max(max_residual, res)

    return SymmetrySolveResult(
        status=status,
        dof=sys.dof() if hasattr(sys, "dof") else 0,
        solved_coordinates=solved_coords,
        applied_symmetry_count=applied_sym,
        symmetry_residual_mm=round(max_residual, 6),
    )
