"""
test_causal_red_curved_constraint_solving.py — Deterministic Public Causal RED for
Curved and Concentric Geometric Constraint Solving.

Proves 5 distinct failure modes on current production behavior (Strategy A):
- RED-1: Concentric circle pair center offset unaligned (concentric skipped in Strategy A)
- RED-2: Horizontal line and tangent circle gap unresolved (tangent skipped in Strategy A)
- RED-3: Line-arc fillet transition G1 continuity broken (line-arc tangency skipped in Strategy A)
- RED-4: Equal-radius circular hole array radii unharmonized (equal radius skipped in Strategy A)
- RED-5: Ambiguous / unconstrained circle fail-safe preservation without corruption
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from primitive_ir_lib.models import (
    ArcGeometry, Calibration, CircleGeometry, LineGeometry, Point2D, Primitive,
    PrimitiveIRDocument, SourceDocument, Trace,
)
from semantic_ir_lib.models import Constraint

try:
    import python_solvespace
    _HAS_SOLVESPACE = True
except ImportError:
    _HAS_SOLVESPACE = False

from curved_constraint_solver_engine import (
    solve_curved_constraints_strategy_a,
    solve_curved_constraints_strategy_d,
)


def _doc(*prims: Primitive) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=200, image_height_px=200),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=list(prims),
    )


def test_causal_red_1_concentric_circles_omission():
    """RED-1: Concentric circle pair centers unaligned in Strategy A.

    In production Strategy A, 'concentric' is not in _SUPPORTED_TYPES and circles are not in line_by_id.
    Constraint is skipped (applied=0); centers remain 1.0 mm apart.
    In Strategy D, concentric centers are aligned to exact coincidence (offset <= 1e-6 mm).
    """
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c1 = Primitive(
        id="c1", type="circle", source="geo", confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=CircleGeometry(center=Point2D(50.0, 50.0), radius=30.0),
    )
    c2 = Primitive(
        id="c2", type="circle", source="geo", confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=CircleGeometry(center=Point2D(51.0, 50.0), radius=10.0),  # 1.0 mm offset
    )
    doc = _doc(c1, c2)
    c_concentric = Constraint(type="concentric", primitive_ids=["c1", "c2"], confidence=1.0, tolerance={})

    # Strategy A fails: constraint skipped, offset remains 1.0 mm
    res_a = solve_curved_constraints_strategy_a(doc, [c_concentric])
    assert res_a.applied_concentric_count == 0
    assert c_concentric.id in res_a.skipped_constraints
    p_c1_a = res_a.solved_primitives["c1"].center
    p_c2_a = res_a.solved_primitives["c2"].center
    offset_a = math.hypot(p_c1_a.x - p_c2_a.x, p_c1_a.y - p_c2_a.y)
    assert offset_a == pytest.approx(1.0, abs=1e-4)

    # Strategy D succeeds: applied_concentric=1, centers coincide
    res_d = solve_curved_constraints_strategy_d(doc, [c_concentric])
    assert res_d.status == "okay"
    assert res_d.applied_concentric_count == 1
    assert c_concentric.id not in res_d.skipped_constraints
    p_c1_d = res_d.solved_primitives["c1"].center
    p_c2_d = res_d.solved_primitives["c2"].center
    offset_d = math.hypot(p_c1_d.x - p_c2_d.x, p_c1_d.y - p_c2_d.y)
    assert offset_d <= 1e-6


def test_causal_red_2_line_circle_tangency_omission():
    """RED-2: Line-circle tangency omitted in Strategy A.

    Horizontal line at y=0 and circle at (50, 25) with radius 20.
    In Strategy A, 'tangent' is skipped; circle stays at y=25 (5.0 mm gap).
    In Strategy D, circle center y moves to 20.0 mm (exact tangency, gap <= 1e-6 mm).
    """
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    l1 = Primitive(
        id="l1", type="line", source="geo", confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(100.0, 0.0)),
    )
    c1 = Primitive(
        id="c1", type="circle", source="geo", confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=CircleGeometry(center=Point2D(50.0, 25.0), radius=20.0),  # gap = 5mm
    )
    doc = _doc(l1, c1)
    c_tangent = Constraint(type="tangent", primitive_ids=["l1", "c1"], confidence=1.0, tolerance={})

    # Strategy A fails
    res_a = solve_curved_constraints_strategy_a(doc, [c_tangent])
    assert res_a.applied_tangent_count == 0
    assert c_tangent.id in res_a.skipped_constraints
    assert abs(res_a.solved_primitives["c1"].center.y - 20.0) == pytest.approx(5.0, abs=1e-4)

    # Strategy D succeeds
    res_d = solve_curved_constraints_strategy_d(doc, [c_tangent])
    assert res_d.status == "okay"
    assert res_d.applied_tangent_count == 1
    p1 = res_d.solved_primitives["l1"].start
    p2 = res_d.solved_primitives["l1"].end
    c = res_d.solved_primitives["c1"].center
    r = res_d.solved_primitives["c1"].radius
    # Distance from circle center to line should equal radius (tangency invariant)
    dist_to_line = abs((p2.x - p1.x) * (p1.y - c.y) - (p1.x - c.x) * (p2.y - p1.y)) / math.hypot(p2.x - p1.x, p2.y - p1.y)
    assert abs(dist_to_line - r) <= 1e-5


def test_causal_red_3_line_arc_fillet_tangency_omission():
    """RED-3: Line-arc fillet transition tangency omitted in Strategy A.

    Horizontal line l1 from (0, 10) to (50, 10) and 90-degree arc a1 from (50, 10.5) to (70, 30.5)
    with center (50, 30.5) and radius 20.
    In Strategy A, line and arc are not solved together; tangency is skipped.
    In Strategy D, arc center and start endpoint align with line endpoint and maintain G1 tangency.
    """
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    l1 = Primitive(
        id="l1", type="line", source="geo", confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=LineGeometry(start=Point2D(0.0, 10.0), end=Point2D(50.0, 10.0)),
    )
    a1 = Primitive(
        id="a1", type="arc", source="geo", confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=ArcGeometry(center=Point2D(50.0, 30.8), radius=20.0, start_angle_deg=270.0, end_angle_deg=0.0),
    )
    doc = _doc(l1, a1)
    c_tangent = Constraint(type="tangent", primitive_ids=["l1", "a1"], confidence=1.0, tolerance={})

    # Strategy A fails
    res_a = solve_curved_constraints_strategy_a(doc, [c_tangent])
    assert res_a.applied_tangent_count == 0
    assert c_tangent.id in res_a.skipped_constraints

    # Strategy D succeeds
    res_d = solve_curved_constraints_strategy_d(doc, [c_tangent])
    assert res_d.status == "okay"
    assert res_d.applied_tangent_count == 1
    p1 = res_d.solved_primitives["l1"].start
    p2 = res_d.solved_primitives["l1"].end
    c = res_d.solved_primitives["a1"].center
    r = res_d.solved_primitives["a1"].radius
    # Distance from arc center to line must equal radius (exact tangency)
    dist_to_line = abs((p2.x - p1.x) * (p1.y - c.y) - (p1.x - c.x) * (p2.y - p1.y)) / math.hypot(p2.x - p1.x, p2.y - p1.y)
    assert abs(dist_to_line - r) <= 1e-5
    # Start angle radial vector must be perpendicular to line direction vector (G1 continuity)
    ang_rad = math.radians(res_d.solved_primitives["a1"].start_angle_deg)
    radial_vx = math.cos(ang_rad)
    radial_vy = math.sin(ang_rad)
    line_vx = (p2.x - p1.x) / math.hypot(p2.x - p1.x, p2.y - p1.y)
    line_vy = (p2.y - p1.y) / math.hypot(p2.x - p1.x, p2.y - p1.y)
    # Dot product of tangent line vector and radial normal vector must be 0
    dot = abs(line_vx * radial_vx + line_vy * radial_vy)
    assert dot <= 1e-4


def test_causal_red_4_equal_radius_omission():
    """RED-4: Equal-radius circular hole array radii unharmonized in Strategy A.

    Two bolt holes c1 (r=10.2) and c2 (r=9.8) with equal_radius constraint.
    Strategy A skips the constraint; radii remain unequal.
    Strategy D harmonizes radii to exact equality (r=10.0).
    """
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c1 = Primitive(
        id="c1", type="circle", source="geo", confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=CircleGeometry(center=Point2D(20.0, 20.0), radius=10.2),
    )
    c2 = Primitive(
        id="c2", type="circle", source="geo", confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=CircleGeometry(center=Point2D(80.0, 20.0), radius=9.8),
    )
    doc = _doc(c1, c2)
    c_equal_r = Constraint(type="equal_radius", primitive_ids=["c1", "c2"], confidence=1.0, tolerance={})

    # Strategy A fails
    res_a = solve_curved_constraints_strategy_a(doc, [c_equal_r])
    assert res_a.applied_equal_radius_count == 0
    assert c_equal_r.id in res_a.skipped_constraints

    # Strategy D succeeds
    res_d = solve_curved_constraints_strategy_d(doc, [c_equal_r])
    assert res_d.status == "okay"
    assert res_d.applied_equal_radius_count == 1
    r1 = res_d.solved_primitives["c1"].radius
    r2 = res_d.solved_primitives["c2"].radius
    assert r1 == pytest.approx(r2, abs=1e-5)
    assert r1 == pytest.approx(10.0, abs=1e-5)


def test_causal_red_5_unconstrained_circle_preservation():
    """RED-5: Unconstrained circle is preserved without corruption or crash."""
    if not _HAS_SOLVESPACE:
        pytest.skip("python-solvespace required")

    c1 = Primitive(
        id="c_isolated", type="circle", source="geo", confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=CircleGeometry(center=Point2D(123.4, 567.8), radius=42.0),
    )
    doc = _doc(c1)

    res_d = solve_curved_constraints_strategy_d(doc, [])
    assert res_d.status == "okay"
    assert "c_isolated" in res_d.solved_primitives
    c_sol = res_d.solved_primitives["c_isolated"]
    assert c_sol.center.x == pytest.approx(123.4, abs=1e-5)
    assert c_sol.center.y == pytest.approx(567.8, abs=1e-5)
    assert c_sol.radius == pytest.approx(42.0, abs=1e-5)
