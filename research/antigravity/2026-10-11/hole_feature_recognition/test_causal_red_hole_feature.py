"""Causal RED tests demonstrating current production deficiencies in hole feature recognition.

Exercises:
1. cad_agent/mechanical_pilot.py: rejects counterbore/blind parametric fields with schema error.
2. cad_agent/mechanical_skills.py: geometry.hole_feature is DEFERRED_UNSUPPORTED blocked by MECH3_GEOMETRY_OWNER.
3. semantic_ir_lib/pattern_recognition.py: circles with radius > 15mm rejected from lo_bat_vit.
4. semantic_ir_lib/pattern_compound.py: concentric plan circles not bound into compound hole.
5. semantic_ir_lib/pattern_recognition.py: section-view stepped hole cavity lines emit 0 hole features.
"""

import pytest
from primitive_ir_lib.models import Point2D, CircleGeometry, LineGeometry, Primitive, Trace
from semantic_ir_lib.pattern_recognition import build_parts_from_primitives
from semantic_ir_lib.pattern_compound import build_compound_parts
from cad_agent.mechanical_skills import get_mechanical_skill_catalog
from cad_agent import mechanical_pilot


def _make_line(id_: str, x0: float, y0: float, x1: float, y1: float) -> Primitive:
    return Primitive(
        id=id_,
        type="line",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
    )


def _make_circle(id_: str, cx: float, cy: float, r: float) -> Primitive:
    return Primitive(
        id=id_,
        type="circle",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=(cx - r, cy - r, cx + r, cy + r)),
        geometry=CircleGeometry(center=Point2D(cx, cy), radius=r),
    )


def test_red_01_pilot_schema_rejects_counterbore_and_blind_parameters():
    """RED 1: mechanical_pilot._validate_definition strictly enforces _HOLE_FIELDS = {id, kind, center, diameter_mm},
    throwing PILOT_HOLE_FEATURE_SCHEMA_INVALID when counterbore or depth attributes are provided."""
    doc_with_cb = {
        "schema_version": mechanical_pilot.PILOT_SCHEMA_VERSION,
        "pilot_id": "test_pilot",
        "source_document": {
            "file_name": "shaft.png",
            "page_index": 0,
            "image_width_px": 800,
            "image_height_px": 600,
        },
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": 1.0,
            "origin_px": [0.0, 0.0],
            "method": "manual_override",
            "reference_note": "ref",
            "status": "verified",
        },
        "features": [
            {
                "id": "step_1",
                "kind": "shaft_step",
                "segments": [{"id": "s1", "start": [0.0, 0.0], "end": [10.0, 0.0]}],
            },
            {
                "id": "hole_cb_1",
                "kind": "hole_feature",
                "center": [50.0, 50.0],
                "diameter_mm": 10.0,
                # Parametric counterbore extensions:
                "counterbore_diameter_mm": 18.0,
                "counterbore_depth_mm": 5.0,
            },
        ],
    }

    with pytest.raises(ValueError) as excinfo:
        mechanical_pilot._validate_definition(doc_with_cb)
    assert "PILOT_HOLE_FEATURE_SCHEMA_INVALID" in str(excinfo.value)


def test_red_02_mechanical_skills_geometry_hole_feature_blocked():
    """RED 2: cad_agent/mechanical_skills catalog reports geometry.hole_feature as DEFERRED_UNSUPPORTED
    blocked by MECH3_GEOMETRY_OWNER."""
    catalog = get_mechanical_skill_catalog()
    hole_records = [s for s in catalog["skills"] if s["skill_id"] == "geometry.hole_feature"]
    assert len(hole_records) == 1
    rec = hole_records[0]
    assert rec["support_state"] == "DEFERRED_UNSUPPORTED"
    assert rec["blocked_by"] == "MECH3_GEOMETRY_OWNER"


def test_red_03_pattern_recognition_rejects_large_hole_radius():
    """RED 3: pattern_recognition.build_parts_from_primitives caps bolt_hole_max_radius_mm at 15.0mm.
    A counterbore recess circle (e.g. radius 18.0mm / diameter 36.0mm) is misclassified as
    'duong_vien_tron' (outer body contour) instead of a hole ('lo_bat_vit')."""
    large_circle = _make_circle("c_large_cb", 100.0, 100.0, 18.0)
    parts = build_parts_from_primitives([large_circle])
    assert len(parts) == 1
    assert parts[0].part_type == "duong_vien_tron"
    assert parts[0].part_type != "lo_bat_vit"


def test_red_04_pattern_compound_fails_concentric_plan_circles():
    """RED 4: pattern_compound.build_compound_parts does not recognize concentric plan circles
    (through-hole circle + counterbore circle), generating 0 compound parts for the pair."""
    c_inner = _make_circle("c_inner", 50.0, 50.0, 6.0)
    c_outer = _make_circle("c_outer", 50.0, 50.0, 12.0)
    # Even if single-parts exist, build_compound_parts knows only khung_chu_nhat, gia_do, ban_le, diem_noi
    compounds = build_compound_parts([c_inner, c_outer], constraints=[])
    assert len(compounds) == 0


def test_red_05_pattern_recognition_blind_to_section_hole_cavity():
    """RED 5: In section views, stepped cavity lines (bore walls + counterbore shoulders)
    are treated as disconnected horizontal/vertical lines, emitting 0 hole features."""
    # Stepped counterbore cavity in section:
    # Outer bore walls (diam 24 -> y = 38 and y = 62) from x=10 to x=18
    w1 = _make_line("w1", 10.0, 62.0, 18.0, 62.0)
    w2 = _make_line("w2", 10.0, 38.0, 18.0, 38.0)
    # Inner bore walls (diam 12 -> y = 44 and y = 56) from x=18 to x=40
    w3 = _make_line("w3", 18.0, 56.0, 40.0, 56.0)
    w4 = _make_line("w4", 18.0, 44.0, 40.0, 44.0)
    # Shoulders at x=18:
    s1 = _make_line("s1", 18.0, 56.0, 18.0, 62.0)
    s2 = _make_line("s2", 18.0, 38.0, 18.0, 44.0)

    parts = build_parts_from_primitives([w1, w2, w3, w4, s1, s2])
    # Only classified as thanh_ngang and thanh_doc
    part_types = [p.part_type for p in parts]
    assert all(pt in ("thanh_ngang", "thanh_doc") for pt in part_types)
    assert not any("hole" in pt or "lo_bat_vit" in pt for pt in part_types)
