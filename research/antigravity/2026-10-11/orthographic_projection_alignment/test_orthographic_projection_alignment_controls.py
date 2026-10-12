"""test_orthographic_projection_alignment_controls.py — Positive and Negative Controls Suite."""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

import pytest

from orthographic_projection_alignment_engine import (
    AlignmentLink,
    OrthographicAlignmentEngine,
    ViewPrimitive,
    ViewRegion,
)


def test_control_01_positive_asymmetric_l_bracket_three_view():
    """Positive Control 1: Asymmetric L-bracket with Front, Top, and Side views."""
    # Front: W=150, H=100
    front_prims = [
        ViewPrimitive("f1", "LINE", (50, 100), (200, 100)),
        ViewPrimitive("f2", "LINE", (50, 130), (200, 130)),  # shelf line
        ViewPrimitive("f3", "LINE", (50, 200), (200, 200)),
        ViewPrimitive("f4", "LINE", (50, 100), (50, 200)),
        ViewPrimitive("f5", "LINE", (90, 130), (90, 200)),  # upright inner corner
        ViewPrimitive("f6", "LINE", (200, 100), (200, 130)),
    ]
    front = ViewRegion("front", "FRONT", (50, 100, 200, 200), primitives=front_prims)

    # Top: W=150, H=70 (Depth=70)
    top_prims = [
        ViewPrimitive("t1", "LINE", (50, 240), (200, 240)),
        ViewPrimitive("t2", "LINE", (50, 310), (200, 310)),
        ViewPrimitive("t3", "LINE", (90, 240), (90, 310)),  # upright projection
    ]
    top = ViewRegion("top", "TOP", (50, 240, 200, 310), primitives=top_prims)

    # Right Side: W=70, H=100 (Depth=70)
    side_prims = [
        ViewPrimitive("s1", "LINE", (250, 100), (320, 100)),
        ViewPrimitive("s2", "LINE", (250, 130), (320, 130)),
        ViewPrimitive("s3", "LINE", (250, 200), (320, 200)),
    ]
    side = ViewRegion("side", "RIGHT_SIDE", (250, 100, 320, 200), primitives=side_prims)

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([front, top, side])
    assert res["valid"] is True
    assert res["inferred_projection_system"] == "THIRD_ANGLE"
    types = {l.relation_type for l in res["links"]}
    assert "VIEWS_ALIGNED_HORIZONTALLY" in types
    assert "VIEWS_ALIGNED_VERTICALLY" in types
    assert "VIEWS_DEPTH_CORRESPONDENCE" in types


def test_control_02_positive_pure_elevation_pair_no_top_view():
    """Positive Control 2: Turned shaft with only Front and Side views."""
    front = ViewRegion("front", "FRONT", (100, 100, 300, 180))
    side = ViewRegion("side", "RIGHT_SIDE", (350, 100, 430, 180))

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([front, side])
    assert res["valid"] is True
    h_links = [l for l in res["links"] if l.relation_type == "VIEWS_ALIGNED_HORIZONTALLY"]
    assert len(h_links) == 1
    assert h_links[0].source_id == "front"
    assert h_links[0].target_id == "side"


def test_control_03_positive_pure_plan_pair_no_side_view():
    """Positive Control 3: Flat bracket with only Front and Top views."""
    front = ViewRegion("front", "FRONT", (100, 50, 250, 120))
    top = ViewRegion("top", "TOP", (100, 160, 250, 260))

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([front, top])
    assert res["valid"] is True
    v_links = [l for l in res["links"] if l.relation_type == "VIEWS_ALIGNED_VERTICALLY"]
    assert len(v_links) == 1
    assert v_links[0].source_id == "front"
    assert v_links[0].target_id == "top"


def test_control_04_negative_staggered_height_bracket_rejection():
    """Negative Control 4: Adjacent view with 15% height error is rejected for horizontal alignment."""
    front = ViewRegion("front", "FRONT", (100, 100, 300, 200))  # H=100
    side_bad = ViewRegion("side", "RIGHT_SIDE", (350, 100, 450, 215))  # H=115 (15% mismatch)

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([front, side_bad])
    h_links = [l for l in res["links"] if l.relation_type == "VIEWS_ALIGNED_HORIZONTALLY"]
    assert len(h_links) == 0


def test_control_05_negative_lateral_offset_top_view_rejection():
    """Negative Control 5: Top view placed laterally without horizontal overlap is rejected."""
    front = ViewRegion("front", "FRONT", (50, 50, 200, 150))
    # Displaced top view in top-right corner with 0 horizontal overlap:
    top_displaced = ViewRegion("top", "TOP", (300, 200, 450, 300))

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([front, top_displaced])
    assert res["valid"] is False
    assert any("ROLE_LAYOUT_INVERSION_REJECTED" in inc for inc in res["incompatibilities"])
    v_links = [l for l in res["links"] if l.relation_type == "VIEWS_ALIGNED_VERTICALLY"]
    assert len(v_links) == 0


def test_control_06_negative_miter_depth_mismatch_rejection():
    """Negative Control 6: Top view depth does not match Side view width (50% mismatch)."""
    top = ViewRegion("top", "TOP", (100, 200, 300, 260))  # Depth = 60mm
    side = ViewRegion("side", "RIGHT_SIDE", (350, 50, 440, 150))  # Depth = 90mm (mismatch)

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([top, side])
    depth_links = [l for l in res["links"] if l.relation_type == "VIEWS_DEPTH_CORRESPONDENCE"]
    assert len(depth_links) == 0


def test_control_07_positive_background_cross_hatch_and_text_noise_immunity():
    """Positive Control 7: Dense diagonal cross-hatching does not corrupt orthogonal feature rays."""
    # Front view with 20 diagonal 45-degree hatch lines:
    hatch_lines = [
        ViewPrimitive(f"hatch_{i}", "LINE", (100 + i * 5, 100), (100 + i * 5 + 20, 120))
        for i in range(20)
    ]
    # Orthogonal feature lines:
    feature_lines = [
        ViewPrimitive("f1", "LINE", (100, 100), (300, 100)),
        ViewPrimitive("f2", "LINE", (100, 200), (300, 200)),
    ]
    front = ViewRegion("front", "FRONT", (100, 100, 300, 200), primitives=hatch_lines + feature_lines)

    side_prims = [
        ViewPrimitive("s1", "LINE", (350, 100), (450, 100)),
        ViewPrimitive("s2", "LINE", (350, 200), (450, 200)),
    ]
    side = ViewRegion("side", "RIGHT_SIDE", (350, 100, 450, 200), primitives=side_prims)

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([front, side])
    assert res["valid"] is True
    h_links = [l for l in res["links"] if l.relation_type == "VIEWS_ALIGNED_HORIZONTALLY"]
    assert len(h_links) == 1
    # 45-degree hatch lines were properly excluded from horizontal rays:
    assert h_links[0].diagnostics["matched_rays"] == 2
    assert h_links[0].diagnostics["total_rays"] == 2


def test_control_08_negative_conflicting_mixed_angle_rejection():
    """Negative Control 8: Mixed contradictory layout (Side in First Angle, Top in Third Angle)."""
    # Front at (200, 200)
    front = ViewRegion("front", "FRONT", (200, 200, 400, 350))
    # Right Side placed to the LEFT of Front -> First Angle vote
    side_first = ViewRegion("side", "RIGHT_SIDE", (50, 200, 150, 350))
    # Top placed ABOVE Front -> Third Angle vote
    top_third = ViewRegion("top", "TOP", (200, 400, 400, 500))

    engine = OrthographicAlignmentEngine()
    res = engine.analyze([front, side_first, top_third])
    assert res["valid"] is False
    assert any("PROJECTION_SYSTEM_CONTRADICTION_REJECTED" in inc for inc in res["incompatibilities"])
