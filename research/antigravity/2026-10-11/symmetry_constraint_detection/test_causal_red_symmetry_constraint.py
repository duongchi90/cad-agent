"""
test_causal_red_symmetry_constraint.py
Public Causal RED Suite demonstrating 5 deterministic failure modes on current production:
- semantic_ir_lib.constraint_detection.detect_constraints
- semantic_ir_lib.constraint_detection.detect_circle_constraints
- semantic_ir_lib.constraint_solving.solve_constraints
- semantic_ir_lib.models.Constraint
"""

import math
import pytest

from primitive_ir_lib.models import (
    Point2D, Primitive, LineGeometry, CircleGeometry,
    PrimitiveIRDocument, Trace, SourceDocument, Calibration
)
from semantic_ir_lib.models import Constraint
from semantic_ir_lib.constraint_detection import (
    detect_constraints,
    detect_circle_constraints,
)
from semantic_ir_lib.constraint_solving import solve_constraints


def _make_line(id_: str, x0: float, y0: float, x1: float, y1: float, layer: str = "UNCLASSIFIED") -> Primitive:
    return Primitive(
        id=id_,
        type="line",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(int(min(x0, x1)), int(min(y0, y1)), int(max(x0, x1)), int(max(y0, y1)))),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
        layer=layer,
    )


def _make_circle(id_: str, cx: float, cy: float, r: float, layer: str = "UNCLASSIFIED") -> Primitive:
    return Primitive(
        id=id_,
        type="circle",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(int(cx - r), int(cy - r), int(cx + r), int(cy + r))),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=r),
        layer=layer,
    )


def _make_doc(*primitives: Primitive) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(file_name="test.png", page_index=0, image_width_px=1000, image_height_px=1000),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
        primitives=list(primitives),
    )


def test_red_01_angled_chamfer_taper_symmetry_loss():
    """RED 1: Angled symmetric features (chamfers, draft tapers) lose angular symmetry.
    Two chamfer lines angled at +30 deg and -30 deg across a horizontal centerline.
    Angle difference is 60 deg, so baseline detects neither parallel nor perpendicular.
    Baseline emits ONLY equal_length, completely losing the symmetric orientation and axis offset.
    """
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    l_chamfer_top = _make_line("chamfer_top", 0.0, 10.0, 17.3205, 20.0)
    l_chamfer_bot = _make_line("chamfer_bot", 0.0, -10.0, 17.3205, -20.0)

    lines = [l_axis, l_chamfer_top, l_chamfer_bot]
    csts = detect_constraints(lines)

    chamfer_csts = [c for c in csts if set(c.primitive_ids) == {"chamfer_top", "chamfer_bot"}]

    # Production baseline detects ONLY equal_length!
    assert len(chamfer_csts) == 1
    assert chamfer_csts[0].type == "equal_length"

    # CAUSAL FAILURE: Zero symmetry or angular reflection constraint detected!
    assert not any(c.type == "symmetric" for c in chamfer_csts)


def test_red_02_symmetric_bolt_hole_pairs_undetected():
    """RED 2: Symmetrical bolt holes across an axis are completely invisible to production detection.
    Two holes of radius 6.0 mm positioned symmetrically at (50, +25) and (50, -25).
    Baseline detect_circle_constraints produces 0 constraints.
    """
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    hole_top = _make_circle("hole_top", 50.0, 25.0, 6.0)
    hole_bot = _make_circle("hole_bot", 50.0, -25.0, 6.0)

    circle_csts = detect_circle_constraints([l_axis], [hole_top, hole_bot])

    # CAUSAL FAILURE: detect_circle_constraints only checks tangent and concentric.
    # It detects ZERO constraints between hole_top and hole_bot!
    assert len(circle_csts) == 0


def test_red_03_parallel_flange_edges_unanchored_to_axis():
    """RED 3: Production detect_constraints cannot distinguish symmetric from asymmetric parallel lines.
    Two parallel lines: one at y = +25, and one at y = -15 (asymmetric by 10 mm!).
    Because baseline only checks angle difference and length difference, it emits
    'parallel' and 'equal_length' with NO knowledge that the lines are asymmetric about the centerline.
    """
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 0.0, layer="CENTER")
    l_top = _make_line("l_top", 10.0, 25.0, 90.0, 25.0)
    l_asym_bot = _make_line("l_asym_bot", 10.0, -15.0, 90.0, -15.0)  # Off-center!

    csts = detect_constraints([l_axis, l_top, l_asym_bot])
    pair_csts = [c for c in csts if set(c.primitive_ids) == {"l_top", "l_asym_bot"}]

    # CAUSAL FAILURE: Production falsely treats them identically to a symmetric pair!
    types = {c.type for c in pair_csts}
    assert "parallel" in types
    assert "equal_length" in types
    # Baseline has 0 awareness that distance to axis is 25mm vs 15mm (asymmetric defect).


def test_red_04_solvespace_drops_symmetric_constraints():
    """RED 4: solve_constraints skips any 'symmetric' constraint because it is missing from _SUPPORTED_TYPES.
    If a caller provides Constraint(type='symmetric'), solve_constraints drops it into skipped_constraints.
    """
    doc = _make_doc(
        _make_line("ax", 0.0, 0.0, 100.0, 0.0),
        _make_line("l1", 10.0, 20.0, 50.0, 20.0),
        _make_line("l2", 10.0, -20.0, 50.0, -20.0),
    )
    sym_cst = Constraint(
        type="symmetric",  # type not in production _SUPPORTED_TYPES
        primitive_ids=["l1", "l2"],
        confidence=1.0,
        tolerance={"distance_mm": 5.0},
    )

    res = solve_constraints(doc, [sym_cst])

    # CAUSAL FAILURE: Production solve_constraints skips 'symmetric' completely!
    assert sym_cst.id in res.skipped_constraints
    assert res.applied_constraint_count == 0


def test_red_05_inclined_non_cardinal_axis_blindness():
    """RED 5: Non-cardinal inclined symmetry axes (e.g. 45 deg) are completely unhandled.
    A 45 deg centerline with ribs inclined at +15 deg and +75 deg.
    Angle difference between the ribs is 60 deg -> baseline detects 0 angle constraints.
    """
    l_axis = _make_line("axis", 0.0, 0.0, 100.0, 100.0, layer="CENTER")
    l_rib1 = _make_line("rib1", 10.0, 10.0, 29.3185, 15.1764)
    l_rib2 = _make_line("rib2", 10.0, 10.0, 15.1764, 29.3185)

    csts = detect_constraints([l_axis, l_rib1, l_rib2])
    rib_csts = [c for c in csts if set(c.primitive_ids) == {"rib1", "rib2"}]

    types = {c.type for c in rib_csts}
    assert "parallel" not in types
    assert "perpendicular" not in types
    assert not any(c.type == "symmetric" for c in rib_csts)
    # CAUSAL FAILURE: The 45 deg bilateral reflection symmetry is completely dropped!
