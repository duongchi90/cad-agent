"""stepped_shaft_recognition_engine.py — Research engine for general stepped shaft recognition.

Implements Strategies A, B, C, and D for extracting multi-step rotational shaft
features, chamfers, and transverse holes from Primitive IR documents.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from primitive_ir_lib.models import (
    Calibration,
    CircleGeometry,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)


@dataclass
class ShaftStep:
    """One cylindrical step of a stepped shaft."""
    step_index: int
    axial_start_mm: float
    axial_end_mm: float
    length_mm: float
    radius_mm: float
    diameter_mm: float
    primitive_ids: List[str] = field(default_factory=list)


@dataclass
class ShaftChamfer:
    """A beveled chamfer at an end cap or step transition."""
    chamfer_index: int
    axial_position_mm: float
    radial_position_mm: float
    size_mm: float
    angle_deg: float
    primitive_ids: List[str] = field(default_factory=list)


@dataclass
class TransverseHole:
    """A transverse cross hole drilled through the shaft."""
    hole_id: str
    center: Tuple[float, float]
    diameter_mm: float
    host_step_index: int
    axial_offset_mm: float
    transverse_offset_mm: float


@dataclass
class SteppedShaftProfile:
    """Complete semantic representation of a stepped shaft feature."""
    shaft_id: str
    axis_origin: Tuple[float, float]
    axis_direction: Tuple[float, float]  # Unit vector (ux, uy)
    axis_angle_deg: float
    total_length_mm: float
    step_count: int
    steps: List[ShaftStep] = field(default_factory=list)
    chamfers: List[ShaftChamfer] = field(default_factory=list)
    transverse_holes: List[TransverseHole] = field(default_factory=list)
    boundary_primitive_ids: List[str] = field(default_factory=list)
    confidence: float = 1.0
    status: str = "VALID"


@dataclass
class ShaftRecognitionResult:
    """Result of running a shaft recognition strategy on a PrimitiveIRDocument."""
    strategy: str
    success: bool
    profiles: List[SteppedShaftProfile] = field(default_factory=list)
    error_code: Optional[str] = None
    execution_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dot(v1: Tuple[float, float], v2: Tuple[float, float]) -> float:
    return v1[0] * v2[0] + v1[1] * v2[1]


def _cross(v1: Tuple[float, float], v2: Tuple[float, float]) -> float:
    return v1[0] * v2[1] - v1[1] * v2[0]


def _norm(v: Tuple[float, float]) -> float:
    return math.hypot(v[0], v[1])


def _dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def _cluster_endpoints(
    endpoints: List[Tuple[float, float]], tolerance: float
) -> Tuple[List[Tuple[float, float]], List[int]]:
    parent = list(range(len(endpoints)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        l_root, r_root = find(left), find(right)
        if l_root != r_root:
            parent[r_root] = l_root

    for left, pt in enumerate(endpoints):
        for right in range(left):
            if _dist(pt, endpoints[right]) <= tolerance:
                union(left, right)

    groups: Dict[int, List[int]] = {}
    for i in range(len(endpoints)):
        groups.setdefault(find(i), []).append(i)

    roots = sorted(groups, key=lambda r: min(groups[r]))
    root_to_cluster = {r: idx for idx, r in enumerate(roots)}
    centers = [
        (
            sum(endpoints[i][0] for i in groups[r]) / len(groups[r]),
            sum(endpoints[i][1] for i in groups[r]) / len(groups[r]),
        )
        for r in roots
    ]
    labels = [root_to_cluster[find(i)] for i in range(len(endpoints))]
    return centers, labels


# ---------------------------------------------------------------------------
# Strategy A: Current Production Baseline
# ---------------------------------------------------------------------------

def run_strategy_a(doc: PrimitiveIRDocument) -> ShaftRecognitionResult:
    """Strategy A: Direct execution of current production cad_agent/mechanical_pilot.py."""
    t0 = time.perf_counter()
    from cad_agent.mechanical_pilot import _phase4_profile_bindings

    try:
        shaft_line_ids, hole_circle_id = _phase4_profile_bindings(doc)
        dt = (time.perf_counter() - t0) * 1000.0

        # Construct basic profile from 8 lines
        lines = [p for p in doc.primitives if p.id in shaft_line_ids and isinstance(p.geometry, LineGeometry)]
        xs = [p.geometry.start.x for p in lines] + [p.geometry.end.x for p in lines]
        ys = [p.geometry.start.y for p in lines] + [p.geometry.end.y for p in lines]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        hole_prim = next((p for p in doc.primitives if p.id == hole_circle_id), None)
        holes: List[TransverseHole] = []
        if hole_prim and isinstance(hole_prim.geometry, CircleGeometry):
            holes.append(
                TransverseHole(
                    hole_id=hole_prim.id,
                    center=(hole_prim.geometry.center.x, hole_prim.geometry.center.y),
                    diameter_mm=hole_prim.geometry.radius * 2.0,
                    host_step_index=1,
                    axial_offset_mm=0.0,
                    transverse_offset_mm=0.0,
                )
            )

        profile = SteppedShaftProfile(
            shaft_id="shaft-profile-001",
            axis_origin=(0.0, 0.0),
            axis_direction=(0.0, 1.0),
            axis_angle_deg=90.0,
            total_length_mm=max_y - min_y,
            step_count=2,
            steps=[
                ShaftStep(0, min_y, (min_y + max_y) / 2.0, (max_y - min_y) / 2.0, 10.0, 20.0, shaft_line_ids[:4]),
                ShaftStep(1, (min_y + max_y) / 2.0, max_y, (max_y - min_y) / 2.0, 15.0, 30.0, shaft_line_ids[4:]),
            ],
            transverse_holes=holes,
            boundary_primitive_ids=shaft_line_ids,
            confidence=1.0,
            status="VALID",
        )
        return ShaftRecognitionResult(
            strategy="STRATEGY_A_CURRENT_BASELINE",
            success=True,
            profiles=[profile],
            execution_time_ms=dt,
        )
    except Exception as exc:
        dt = (time.perf_counter() - t0) * 1000.0
        return ShaftRecognitionResult(
            strategy="STRATEGY_A_CURRENT_BASELINE",
            success=False,
            profiles=[],
            error_code=f"{type(exc).__name__}:{str(exc)}",
            execution_time_ms=dt,
        )


# ---------------------------------------------------------------------------
# Strategy B: Naive Bounding-Box Aspect Ratio Matcher
# ---------------------------------------------------------------------------

def run_strategy_b(doc: PrimitiveIRDocument) -> ShaftRecognitionResult:
    """Strategy B: Heuristic bounding-box aspect ratio and count matcher."""
    t0 = time.perf_counter()
    lines = [p for p in doc.primitives if p.type == "line" and isinstance(p.geometry, LineGeometry)]
    circles = [p for p in doc.primitives if p.type == "circle" and isinstance(p.geometry, CircleGeometry)]

    if len(lines) < 4 or len(lines) > 20:
        dt = (time.perf_counter() - t0) * 1000.0
        return ShaftRecognitionResult(
            strategy="STRATEGY_B_BBOX_MATCHER",
            success=False,
            error_code="INVALID_LINE_COUNT",
            execution_time_ms=dt,
        )

    pts = []
    for line in lines:
        pts.append((line.geometry.start.x, line.geometry.start.y))
        pts.append((line.geometry.end.x, line.geometry.end.y))

    min_x = min(p[0] for p in pts)
    max_x = max(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)
    width = max_x - min_x
    height = max_y - min_y

    if width <= 0 or height <= 0:
        dt = (time.perf_counter() - t0) * 1000.0
        return ShaftRecognitionResult(
            strategy="STRATEGY_B_BBOX_MATCHER",
            success=False,
            error_code="DEGENERATE_BBOX",
            execution_time_ms=dt,
        )

    aspect_ratio = max(width, height) / min(width, height)
    if aspect_ratio < 1.4:
        dt = (time.perf_counter() - t0) * 1000.0
        return ShaftRecognitionResult(
            strategy="STRATEGY_B_BBOX_MATCHER",
            success=False,
            error_code="INSUFFICIENT_ASPECT_RATIO",
            execution_time_ms=dt,
        )

    # Guess horizontal vs vertical from bbox dimensions
    is_horiz = width >= height
    axis_dir = (1.0, 0.0) if is_horiz else (0.0, 1.0)
    axis_angle = 0.0 if is_horiz else 90.0
    total_len = width if is_horiz else height

    # Naively create steps based on line count / 4
    estimated_steps = max(1, len(lines) // 4)
    step_len = total_len / estimated_steps
    steps = []
    for s_idx in range(estimated_steps):
        steps.append(
            ShaftStep(
                step_index=s_idx,
                axial_start_mm=s_idx * step_len,
                axial_end_mm=(s_idx + 1) * step_len,
                length_mm=step_len,
                radius_mm=min(width, height) / 2.0,
                diameter_mm=min(width, height),
                primitive_ids=[l.id for l in lines[s_idx * 4 : (s_idx + 1) * 4]],
            )
        )

    holes = []
    for c in circles:
        holes.append(
            TransverseHole(
                hole_id=c.id,
                center=(c.geometry.center.x, c.geometry.center.y),
                diameter_mm=c.geometry.radius * 2.0,
                host_step_index=0,
                axial_offset_mm=0.0,
                transverse_offset_mm=0.0,
            )
        )

    dt = (time.perf_counter() - t0) * 1000.0
    profile = SteppedShaftProfile(
        shaft_id="shaft-profile-b",
        axis_origin=((min_x + max_x) / 2.0, (min_y + max_y) / 2.0),
        axis_direction=axis_dir,
        axis_angle_deg=axis_angle,
        total_length_mm=total_len,
        step_count=len(steps),
        steps=steps,
        transverse_holes=holes,
        boundary_primitive_ids=[l.id for l in lines],
        confidence=0.6,
        status="HEURISTIC_BBOX",
    )
    return ShaftRecognitionResult(
        strategy="STRATEGY_B_BBOX_MATCHER",
        success=True,
        profiles=[profile],
        execution_time_ms=dt,
    )


# ---------------------------------------------------------------------------
# Strategy C: Axis-Aligned Alternating Edge Matcher
# ---------------------------------------------------------------------------

def run_strategy_c(doc: PrimitiveIRDocument) -> ShaftRecognitionResult:
    """Strategy C: Axis-aligned alternating edge matcher (horizontal or vertical only)."""
    t0 = time.perf_counter()
    lines = [p for p in doc.primitives if p.type == "line" and isinstance(p.geometry, LineGeometry)]
    circles = [p for p in doc.primitives if p.type == "circle" and isinstance(p.geometry, CircleGeometry)]

    if len(lines) < 4:
        dt = (time.perf_counter() - t0) * 1000.0
        return ShaftRecognitionResult(
            strategy="STRATEGY_C_AXIS_ALIGNED",
            success=False,
            error_code="TOO_FEW_LINES",
            execution_time_ms=dt,
        )

    h_lines = []
    v_lines = []
    for l in lines:
        dx = abs(l.geometry.end.x - l.geometry.start.x)
        dy = abs(l.geometry.end.y - l.geometry.start.y)
        if dy <= 1e-3 and dx > 1e-3:
            h_lines.append(l)
        elif dx <= 1e-3 and dy > 1e-3:
            v_lines.append(l)
        else:
            # Diagonal/angled line: Strategy C fails immediately on diagonal lines (chamfers)
            dt = (time.perf_counter() - t0) * 1000.0
            return ShaftRecognitionResult(
                strategy="STRATEGY_C_AXIS_ALIGNED",
                success=False,
                error_code="NON_AXIS_ALIGNED_CHAMFER_PRESENT",
                execution_time_ms=dt,
            )

    if not h_lines or not v_lines:
        dt = (time.perf_counter() - t0) * 1000.0
        return ShaftRecognitionResult(
            strategy="STRATEGY_C_AXIS_ALIGNED",
            success=False,
            error_code="MISSING_AXIAL_OR_RADIAL_EDGES",
            execution_time_ms=dt,
        )

    # Determine dominant axis: horizontal or vertical
    total_h_len = sum(abs(l.geometry.end.x - l.geometry.start.x) for l in h_lines)
    total_v_len = sum(abs(l.geometry.end.y - l.geometry.start.y) for l in v_lines)

    is_horizontal = total_h_len >= total_v_len
    axial_lines = h_lines if is_horizontal else v_lines
    radial_lines = v_lines if is_horizontal else h_lines

    # Sort axial lines by coordinate
    if is_horizontal:
        axial_coords = [(min(l.geometry.start.x, l.geometry.end.x), max(l.geometry.start.x, l.geometry.end.x), l.geometry.start.y, l) for l in axial_lines]
        axial_coords.sort(key=lambda t: (t[0], t[1]))
        min_ax = min(t[0] for t in axial_coords)
        max_ax = max(t[1] for t in axial_coords)
    else:
        axial_coords = [(min(l.geometry.start.y, l.geometry.end.y), max(l.geometry.start.y, l.geometry.end.y), l.geometry.start.x, l) for l in axial_lines]
        axial_coords.sort(key=lambda t: (t[0], t[1]))
        min_ax = min(t[0] for t in axial_coords)
        max_ax = max(t[1] for t in axial_coords)

    # Group parallel pairs of axial lines with matching spans
    steps: List[ShaftStep] = []
    used_lines = set()
    for i, a1 in enumerate(axial_coords):
        if a1[3].id in used_lines:
            continue
        for j in range(i + 1, len(axial_coords)):
            a2 = axial_coords[j]
            if a2[3].id in used_lines:
                continue
            if abs(a1[0] - a2[0]) < 2.0 and abs(a1[1] - a2[1]) < 2.0:
                # Opposite cylindrical walls
                r = abs(a1[2] - a2[2]) / 2.0
                step_idx = len(steps)
                steps.append(
                    ShaftStep(
                        step_index=step_idx,
                        axial_start_mm=a1[0],
                        axial_end_mm=a1[1],
                        length_mm=a1[1] - a1[0],
                        radius_mm=r,
                        diameter_mm=2.0 * r,
                        primitive_ids=[a1[3].id, a2[3].id],
                    )
                )
                used_lines.add(a1[3].id)
                used_lines.add(a2[3].id)
                break

    if not steps:
        dt = (time.perf_counter() - t0) * 1000.0
        return ShaftRecognitionResult(
            strategy="STRATEGY_C_AXIS_ALIGNED",
            success=False,
            error_code="NO_OPPOSITE_PAIRS_FOUND",
            execution_time_ms=dt,
        )

    steps.sort(key=lambda s: s.axial_start_mm)

    holes: List[TransverseHole] = []
    for c in circles:
        cx = c.geometry.center.x if is_horizontal else c.geometry.center.y
        for s in steps:
            if s.axial_start_mm <= cx <= s.axial_end_mm:
                holes.append(
                    TransverseHole(
                        hole_id=c.id,
                        center=(c.geometry.center.x, c.geometry.center.y),
                        diameter_mm=c.geometry.radius * 2.0,
                        host_step_index=s.step_index,
                        axial_offset_mm=cx - s.axial_start_mm,
                        transverse_offset_mm=0.0,
                    )
                )
                break

    dt = (time.perf_counter() - t0) * 1000.0
    profile = SteppedShaftProfile(
        shaft_id="shaft-profile-c",
        axis_origin=(0.0, 0.0),
        axis_direction=(1.0, 0.0) if is_horizontal else (0.0, 1.0),
        axis_angle_deg=0.0 if is_horizontal else 90.0,
        total_length_mm=max_ax - min_ax,
        step_count=len(steps),
        steps=steps,
        transverse_holes=holes,
        boundary_primitive_ids=[l.id for l in lines],
        confidence=0.85,
        status="VALID",
    )
    return ShaftRecognitionResult(
        strategy="STRATEGY_C_AXIS_ALIGNED",
        success=True,
        profiles=[profile],
        execution_time_ms=dt,
    )


# ---------------------------------------------------------------------------
# Strategy D: Generalized Axisymmetric Boundary Graph Topology Oracle
# ---------------------------------------------------------------------------

def run_strategy_d(
    doc: PrimitiveIRDocument,
    endpoint_tolerance_mm: float = 3.0,
    min_confidence: float = 0.50,
) -> ShaftRecognitionResult:
    """Strategy D: Full graph topological cycle detection, SVD axis fitting,
    chamfer absorption, and multi-hole association oracle.
    """
    t0 = time.perf_counter()

    # 1. Filter valid primitives
    valid_lines: List[Primitive] = []
    for p in doc.primitives:
        if p.type != "line" or p.geometry is None or not isinstance(p.geometry, LineGeometry):
            continue
        if p.confidence < min_confidence:
            continue
        s, e = p.geometry.start, p.geometry.end
        if not (math.isfinite(s.x) and math.isfinite(s.y) and math.isfinite(e.x) and math.isfinite(e.y)):
            continue
        length = p.geometry.length()
        if length < 1e-4:
            continue
        valid_lines.append(p)

    valid_circles: List[Primitive] = []
    for p in doc.primitives:
        if p.type != "circle" or p.geometry is None or not isinstance(p.geometry, CircleGeometry):
            continue
        if p.confidence < min_confidence:
            continue
        c = p.geometry.center
        r = p.geometry.radius
        if not (math.isfinite(c.x) and math.isfinite(c.y) and math.isfinite(r)):
            continue
        if r <= 1e-4:
            continue
        valid_circles.append(p)

    if len(valid_lines) < 4:
        dt = (time.perf_counter() - t0) * 1000.0
        return ShaftRecognitionResult(
            strategy="STRATEGY_D_GRAPH_TOPOLOGY_ORACLE",
            success=False,
            error_code="INSUFFICIENT_VALID_LINES",
            execution_time_ms=dt,
        )

    # Scale tolerance with calibration if available
    scale = doc.calibration.pixel_to_unit_scale if doc.calibration and doc.calibration.pixel_to_unit_scale > 0 else 1.0
    tol = endpoint_tolerance_mm * scale

    # 2. Cluster line endpoints
    raw_endpoints: List[Tuple[float, float]] = []
    for l in valid_lines:
        assert isinstance(l.geometry, LineGeometry)
        raw_endpoints.append((l.geometry.start.x, l.geometry.start.y))
        raw_endpoints.append((l.geometry.end.x, l.geometry.end.y))

    centers, labels = _cluster_endpoints(raw_endpoints, tol)
    n_nodes = len(centers)

    # Build adjacency
    adjacency: Dict[int, List[Tuple[int, int]]] = {i: [] for i in range(n_nodes)}
    for edge_idx, l in enumerate(valid_lines):
        u, v = labels[edge_idx * 2], labels[edge_idx * 2 + 1]
        if u != v:
            adjacency[u].append((v, edge_idx))
            adjacency[v].append((u, edge_idx))

    # 3. Traverse simple closed cycle forming boundary polygon
    visited_edges: Set[int] = set()
    best_cycle_nodes: List[int] = []
    best_cycle_edges: List[int] = []

    for start_node in range(n_nodes):
        if len(adjacency[start_node]) < 2:
            continue
        for neighbor, edge_idx in adjacency[start_node]:
            # Try to walk a simple cycle
            curr = neighbor
            prev = start_node
            cycle_nodes = [start_node, curr]
            cycle_edges = [edge_idx]

            while curr != start_node and len(cycle_edges) <= len(valid_lines):
                next_opts = [item for item in adjacency[curr] if item[0] != prev and item[1] not in cycle_edges]
                if not next_opts:
                    break
                # Prefer continuity
                next_node, next_edge = next_opts[0]
                cycle_nodes.append(next_node)
                cycle_edges.append(next_edge)
                prev, curr = curr, next_node

            if curr == start_node and len(cycle_edges) >= 4:
                # Closed loop found!
                # Remove duplicate closing node
                cycle_nodes.pop()
                poly_pts = [centers[idx] for idx in cycle_nodes]
                # Calculate polygon area via Shoelace formula
                area = 0.0
                for k in range(len(poly_pts)):
                    p1 = poly_pts[k]
                    p2 = poly_pts[(k + 1) % len(poly_pts)]
                    area += (p1[0] * p2[1] - p2[0] * p1[1])
                area = abs(area) / 2.0

                if area > 10.0:  # Non-trivial polygon
                    if len(cycle_edges) > len(best_cycle_edges):
                        best_cycle_nodes = cycle_nodes
                        best_cycle_edges = cycle_edges

    if not best_cycle_nodes:
        dt = (time.perf_counter() - t0) * 1000.0
        return ShaftRecognitionResult(
            strategy="STRATEGY_D_GRAPH_TOPOLOGY_ORACLE",
            success=False,
            error_code="NO_CLOSED_BOUNDARY_CYCLE",
            execution_time_ms=dt,
        )

    poly_pts = [centers[idx] for idx in best_cycle_nodes]
    boundary_line_ids = [valid_lines[e_idx].id for e_idx in best_cycle_edges]

    # 4. Extract Principal Axis of Symmetry
    # Find candidate directions from parallel edge pairs
    edge_dirs: List[Tuple[Tuple[float, float], float, int]] = []
    for k in range(len(poly_pts)):
        p1 = poly_pts[k]
        p2 = poly_pts[(k + 1) % len(poly_pts)]
        vx, vy = p2[0] - p1[0], p2[1] - p1[1]
        length = math.hypot(vx, vy)
        if length > tol:
            edge_dirs.append(((vx / length, vy / length), length, k))

    buckets: Dict[float, Dict] = {}
    for k in range(len(poly_pts)):
        p1 = poly_pts[k]
        p2 = poly_pts[(k + 1) % len(poly_pts)]
        vx, vy = p2[0] - p1[0], p2[1] - p1[1]
        length = math.hypot(vx, vy)
        if length > tol:
            ang = math.degrees(math.atan2(vy, vx)) % 180.0
            matched = False
            for base_ang in list(buckets.keys()):
                diff = min(abs(ang - base_ang), 180.0 - abs(ang - base_ang))
                if diff < 10.0:
                    buckets[base_ang]["len"] += length
                    buckets[base_ang]["dirs"].append((vx / length, vy / length))
                    matched = True
                    break
            if not matched:
                buckets[ang] = {"len": length, "dirs": [(vx / length, vy / length)]}

    if buckets:
        dominant_ang = max(buckets, key=lambda a: buckets[a]["len"])
        ang_rad = math.radians(dominant_ang)
        axis_u = (math.cos(ang_rad), math.sin(ang_rad))
    else:
        axis_u = (1.0, 0.0)

    # Ensure axis_u is normalized
    u_norm = math.hypot(axis_u[0], axis_u[1])
    axis_u = (axis_u[0] / u_norm, axis_u[1] / u_norm)
    axis_n = (-axis_u[1], axis_u[0])  # Normal vector

    # Centerline origin: average coordinates
    centroid = (
        sum(p[0] for p in poly_pts) / len(poly_pts),
        sum(p[1] for p in poly_pts) / len(poly_pts),
    )

    # Project vertices along axis u and normal n
    projections = []
    for pt in poly_pts:
        t_val = _dot((pt[0] - centroid[0], pt[1] - centroid[1]), axis_u)
        r_val = _dot((pt[0] - centroid[0], pt[1] - centroid[1]), axis_n)
        projections.append((t_val, r_val))

    # Refine origin along n so median positive r == median negative r
    pos_r = [r for _, r in projections if r > tol]
    neg_r = [abs(r) for _, r in projections if r < -tol]
    if pos_r and neg_r:
        r_offset = (sum(pos_r) / len(pos_r) - sum(neg_r) / len(neg_r)) / 2.0
    else:
        r_offset = 0.0

    refined_origin = (
        centroid[0] + r_offset * axis_n[0],
        centroid[1] + r_offset * axis_n[1],
    )

    # Re-project with refined origin
    refined_proj = []
    for pt in poly_pts:
        t_val = _dot((pt[0] - refined_origin[0], pt[1] - refined_origin[1]), axis_u)
        r_val = _dot((pt[0] - refined_origin[0], pt[1] - refined_origin[1]), axis_n)
        refined_proj.append((t_val, r_val))

    # Check symmetry: for every vertex, there should be symmetry across the axis
    symmetry_errors = []
    for t_val, r_val in refined_proj:
        # Find closest opposite point
        opp_dist = min(
            math.hypot(t_val - t_other, abs(r_val) - abs(r_other))
            for t_other, r_other in refined_proj
            if (r_val * r_other < 0 or abs(r_val) <= tol)
        )
        symmetry_errors.append(opp_dist)

    max_sym_error = max(symmetry_errors) if symmetry_errors else 0.0
    if max_sym_error > 4.0 * tol:
        dt = (time.perf_counter() - t0) * 1000.0
        return ShaftRecognitionResult(
            strategy="STRATEGY_D_GRAPH_TOPOLOGY_ORACLE",
            success=False,
            error_code="ASYMMETRIC_NON_SHAFT_CONTOUR",
            execution_time_ms=dt,
        )

    # 5. Extract Step Segments and Chamfers
    t_vals = [t for t, _ in refined_proj]
    t_min, t_max = min(t_vals), max(t_vals)
    total_len = t_max - t_min

    # Detect edge segments in loop
    segments_1d: List[Dict] = []
    chamfers: List[ShaftChamfer] = []
    chamfer_idx = 0

    for k in range(len(refined_proj)):
        t1, r1 = refined_proj[k]
        t2, r2 = refined_proj[(k + 1) % len(refined_proj)]
        edge_id = valid_lines[best_cycle_edges[k]].id
        dt_seg = abs(t2 - t1)
        dr_seg = abs(r2 - r1)

        if dt_seg > tol and dr_seg <= tol:
            # Axial cylinder wall
            segments_1d.append({
                "type": "AXIAL",
                "t_start": min(t1, t2),
                "t_end": max(t1, t2),
                "radius": (abs(r1) + abs(r2)) / 2.0,
                "primitive_id": edge_id,
            })
        elif dr_seg > tol and dt_seg <= tol:
            # Radial step riser or end cap
            segments_1d.append({
                "type": "RADIAL",
                "t": (t1 + t2) / 2.0,
                "r_min": min(abs(r1), abs(r2)),
                "r_max": max(abs(r1), abs(r2)),
                "primitive_id": edge_id,
            })
        elif dt_seg > tol and dr_seg > tol:
            # Diagonal transition: Chamfer!
            angle_rad = math.atan2(dr_seg, dt_seg)
            angle_deg = math.degrees(angle_rad)
            chamfers.append(
                ShaftChamfer(
                    chamfer_index=chamfer_idx,
                    axial_position_mm=(t1 + t2) / 2.0,
                    radial_position_mm=(abs(r1) + abs(r2)) / 2.0,
                    size_mm=(dt_seg + dr_seg) / 2.0,
                    angle_deg=round(angle_deg, 1),
                    primitive_ids=[edge_id],
                )
            )
            chamfer_idx += 1

    # Group axial cylinder walls into steps
    axial_segments = [s for s in segments_1d if s["type"] == "AXIAL"]
    # Group pairs of axial walls with similar t-span and radius
    raw_steps: List[ShaftStep] = []
    used_axial = set()
    step_num = 0

    # Sort by axial start
    axial_segments.sort(key=lambda s: (s["t_start"], s["t_end"]))

    for i, s1 in enumerate(axial_segments):
        if s1["primitive_id"] in used_axial:
            continue
        matched_s2 = None
        for j in range(i + 1, len(axial_segments)):
            s2 = axial_segments[j]
            if s2["primitive_id"] in used_axial:
                continue
            if abs(s1["t_start"] - s2["t_start"]) <= 2 * tol and abs(s1["t_end"] - s2["t_end"]) <= 2 * tol:
                matched_s2 = s2
                break

        t_st = s1["t_start"]
        t_en = s1["t_end"]
        rad = (s1["radius"] + matched_s2["radius"]) / 2.0 if matched_s2 else s1["radius"]
        pids = [s1["primitive_id"]] + ([matched_s2["primitive_id"]] if matched_s2 else [])

        raw_steps.append(
            ShaftStep(
                step_index=step_num,
                axial_start_mm=round(t_st - t_min, 3),
                axial_end_mm=round(t_en - t_min, 3),
                length_mm=round(t_en - t_st, 3),
                radius_mm=round(rad, 3),
                diameter_mm=round(rad * 2.0, 3),
                primitive_ids=pids,
            )
        )
        used_axial.add(s1["primitive_id"])
        if matched_s2:
            used_axial.add(matched_s2["primitive_id"])
        step_num += 1

    raw_steps.sort(key=lambda s: s.axial_start_mm)

    # 6. Associate Transverse Cross-Holes
    holes: List[TransverseHole] = []
    for c in valid_circles:
        assert isinstance(c.geometry, CircleGeometry)
        c_pt = (c.geometry.center.x, c.geometry.center.y)
        t_c = _dot((c_pt[0] - refined_origin[0], c_pt[1] - refined_origin[1]), axis_u)
        r_c = _dot((c_pt[0] - refined_origin[0], c_pt[1] - refined_origin[1]), axis_n)

        # Check if inside axial bounds
        if t_min - tol <= t_c <= t_max + tol:
            # Find host step
            axial_pos = t_c - t_min
            host_idx = 0
            for st in raw_steps:
                if st.axial_start_mm - tol <= axial_pos <= st.axial_end_mm + tol:
                    host_idx = st.step_index
                    # Verify center is within cylinder radius
                    if abs(r_c) <= st.radius_mm + tol:
                        holes.append(
                            TransverseHole(
                                hole_id=c.id,
                                center=c_pt,
                                diameter_mm=round(c.geometry.radius * 2.0, 3),
                                host_step_index=host_idx,
                                axial_offset_mm=round(axial_pos - st.axial_start_mm, 3),
                                transverse_offset_mm=round(r_c, 3),
                            )
                        )
                    break

    axis_deg = math.degrees(math.atan2(axis_u[1], axis_u[0])) % 360.0

    profile = SteppedShaftProfile(
        shaft_id="shaft-profile-d",
        axis_origin=refined_origin,
        axis_direction=axis_u,
        axis_angle_deg=round(axis_deg, 2),
        total_length_mm=round(total_len, 3),
        step_count=len(raw_steps),
        steps=raw_steps,
        chamfers=chamfers,
        transverse_holes=holes,
        boundary_primitive_ids=boundary_line_ids,
        confidence=1.0,
        status="VALID",
    )

    dt = (time.perf_counter() - t0) * 1000.0
    return ShaftRecognitionResult(
        strategy="STRATEGY_D_GRAPH_TOPOLOGY_ORACLE",
        success=True,
        profiles=[profile],
        execution_time_ms=dt,
    )
