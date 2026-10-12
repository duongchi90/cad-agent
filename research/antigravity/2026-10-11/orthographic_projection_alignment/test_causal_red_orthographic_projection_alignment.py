"""Causal RED reproducing 5 baseline failure modes on production component_view_registry.py."""

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

from cad_agent.component_view_registry import _derive_links
from orthographic_projection_alignment_engine import (
    AlignmentLink,
    OrthographicAlignmentEngine,
    ViewPrimitive,
    ViewRegion,
    run_strategy_a,
)


def _views_to_prod_dicts(views: list[ViewRegion]) -> list[dict]:
    """Convert ViewRegion objects into the exact dictionary format expected by production _derive_links."""
    return [
        {
            "view_id": v.view_id,
            "view_role": v.view_role,
            "component_ids": v.component_ids,
            "source_projection_refs": [],
            "semantic_projection_refs": v.semantic_projection_refs,
            "candidate_entity_bindings": [],
            "layout_bindings": v.layout_bindings,
        }
        for v in views
    ]


def test_red_01_horizontal_elevation_side_alignment_omission():
    """RED 1: Front and Right-Side views share exact height and vertical span, but production Strategy A returns 0 links."""
    # Front view: X in [50, 200], Y in [100, 250] (Height = 150)
    front_prims = [
        ViewPrimitive("f1", "LINE", (50, 100), (200, 100)),
        ViewPrimitive("f2", "LINE", (50, 160), (200, 160)),  # step transition
        ViewPrimitive("f3", "LINE", (50, 250), (200, 250)),
    ]
    front = ViewRegion(
        view_id="view-front",
        view_role="FRONT",
        bbox=(50.0, 100.0, 200.0, 250.0),
        primitives=front_prims,
        component_ids=[],  # Not yet populated
    )

    # Right-Side view: X in [260, 360], Y in [100, 250] (Height = 150)
    side_prims = [
        ViewPrimitive("s1", "LINE", (260, 100), (360, 100)),
        ViewPrimitive("s2", "LINE", (260, 160), (360, 160)),  # matching step transition
        ViewPrimitive("s3", "LINE", (260, 250), (360, 250)),
    ]
    side = ViewRegion(
        view_id="view-side",
        view_role="RIGHT_SIDE",
        bbox=(260.0, 100.0, 360.0, 250.0),
        primitives=side_prims,
        component_ids=[],
    )

    # Production Baseline Strategy A:
    prod_views = _views_to_prod_dicts([front, side])
    prod_links = _derive_links(prod_views)
    # Strategy A outputs 0 links because component_ids is empty
    assert len(prod_links) == 0, "Production Baseline unexpectedly emitted links"

    # Strategy D:
    engine = OrthographicAlignmentEngine()
    result = engine.analyze([front, side])
    assert result["valid"] is True
    h_links = [l for l in result["links"] if l.relation_type == "VIEWS_ALIGNED_HORIZONTALLY"]
    assert len(h_links) == 1
    assert h_links[0].source_id == "view-front"
    assert h_links[0].target_id == "view-side"
    assert h_links[0].diagnostics["matched_rays"] >= 2
    assert h_links[0].projection_system == "THIRD_ANGLE"


def test_red_02_vertical_elevation_plan_alignment_omission():
    """RED 2: Front and Top views share exact width and horizontal span, but production Strategy A returns 0 links."""
    # Front view: X in [100, 350], Y in [50, 180] (Width = 250)
    front_prims = [
        ViewPrimitive("f1", "LINE", (100, 50), (100, 180)),
        ViewPrimitive("f2", "LINE", (180, 50), (180, 180)),  # vertical step
        ViewPrimitive("f3", "LINE", (270, 50), (270, 180)),  # vertical shoulder
        ViewPrimitive("f4", "LINE", (350, 50), (350, 180)),
    ]
    front = ViewRegion(
        view_id="view-front",
        view_role="FRONT",
        bbox=(100.0, 50.0, 350.0, 180.0),
        primitives=front_prims,
        component_ids=[],
    )

    # Top view: X in [100, 350], Y in [220, 320] (Width = 250)
    top_prims = [
        ViewPrimitive("t1", "LINE", (100, 220), (100, 320)),
        ViewPrimitive("t2", "LINE", (180, 220), (180, 320)),  # matching vertical step
        ViewPrimitive("t3", "LINE", (270, 220), (270, 320)),  # matching vertical shoulder
        ViewPrimitive("t4", "LINE", (350, 220), (350, 320)),
    ]
    top = ViewRegion(
        view_id="view-top",
        view_role="TOP",
        bbox=(100.0, 220.0, 350.0, 320.0),
        primitives=top_prims,
        component_ids=[],
    )

    # Production Baseline Strategy A:
    prod_views = _views_to_prod_dicts([front, top])
    prod_links = _derive_links(prod_views)
    assert len(prod_links) == 0, "Production Baseline unexpectedly emitted links"

    # Strategy D:
    engine = OrthographicAlignmentEngine()
    result = engine.analyze([front, top])
    assert result["valid"] is True
    v_links = [l for l in result["links"] if l.relation_type == "VIEWS_ALIGNED_VERTICALLY"]
    assert len(v_links) == 1
    assert v_links[0].source_id == "view-front"
    assert v_links[0].target_id == "view-top"
    assert v_links[0].diagnostics["matched_rays"] >= 3
    assert v_links[0].projection_system == "THIRD_ANGLE"


def test_red_03_geometric_incompatibility_blindness_in_component_sharing():
    """RED 3: Production Strategy A blindly accepts VIEWS_SHARE_COMPONENT even when views have 400% height mismatch."""
    front = ViewRegion(
        view_id="view-front",
        view_role="FRONT",
        bbox=(50.0, 100.0, 200.0, 150.0),  # H = 50, W = 150
        component_ids=["comp-shared-123"],
    )
    side = ViewRegion(
        view_id="view-side",
        view_role="RIGHT_SIDE",
        bbox=(260.0, 100.0, 340.0, 350.0),  # H = 250 (400% mismatch!), W = 80
        component_ids=["comp-shared-123"],
    )

    # Production Baseline Strategy A:
    prod_views = _views_to_prod_dicts([front, side])
    prod_links = _derive_links(prod_views)
    # Strategy A blindly links them because comp-shared-123 matches!
    share_links = [l for l in prod_links if l["relation_type"] == "VIEWS_SHARE_COMPONENT"]
    assert len(share_links) == 1, "Production Baseline failed to reproduce blind link creation"

    # Strategy D:
    engine = OrthographicAlignmentEngine()
    result = engine.analyze([front, side])
    # Must flag geometric incompatibility and suppress false valid state
    assert result["valid"] is False
    assert any("GEOMETRIC_INCOMPATIBILITY_REJECTED" in inc for inc in result["incompatibilities"])
    # False component link is suppressed
    assert not any(l.relation_type == "VIEWS_SHARE_COMPONENT" for l in result["links"])


def test_red_04_projection_system_inversion_blindness():
    """RED 4: Top view placed below Front view in a Third-Angle layout is blindly ignored by Strategy A."""
    # Front at Y in [200, 350]
    front = ViewRegion(
        view_id="view-front",
        view_role="FRONT",
        bbox=(100.0, 200.0, 300.0, 350.0),
        primitives=[ViewPrimitive("f1", "LINE", (100, 200), (300, 200))],
    )
    # Side at X in [350, 450], Y in [200, 350] (Right of Front -> defines Third Angle)
    side = ViewRegion(
        view_id="view-side",
        view_role="RIGHT_SIDE",
        bbox=(350.0, 200.0, 450.0, 350.0),
        primitives=[ViewPrimitive("s1", "LINE", (350, 200), (450, 200))],
    )
    # Inverted Top view: placed at Y in [50, 150] (BELOW Front view!)
    top_inverted = ViewRegion(
        view_id="view-top",
        view_role="TOP",
        bbox=(100.0, 50.0, 300.0, 150.0),
        primitives=[ViewPrimitive("t1", "LINE", (100, 50), (300, 50))],
    )

    # Production Baseline Strategy A:
    prod_views = _views_to_prod_dicts([front, side, top_inverted])
    prod_links = _derive_links(prod_views)
    # Strategy A ignores positions and reports no errors
    assert len(prod_links) == 0

    # Strategy D:
    engine = OrthographicAlignmentEngine()
    result = engine.analyze([front, side, top_inverted], declared_projection_system="THIRD_ANGLE")
    # Rejects due to layout inversion
    assert result["valid"] is False
    assert any("ROLE_LAYOUT_INVERSION_REJECTED" in inc for inc in result["incompatibilities"])
    assert result["inferred_projection_system"] == "THIRD_ANGLE"


def test_red_05_miter_depth_correspondence_omission():
    """RED 5: Top view depth matches Side view depth via 45-degree miter projection, but Strategy A produces 0 links."""
    # Top view: Height = 80mm (represents depth of component)
    top = ViewRegion(
        view_id="view-top",
        view_role="TOP",
        bbox=(100.0, 250.0, 300.0, 330.0),  # H = 80mm, W = 200mm
    )
    # Side view: Width = 80mm (represents depth of component)
    side = ViewRegion(
        view_id="view-side",
        view_role="RIGHT_SIDE",
        bbox=(350.0, 100.0, 430.0, 200.0),  # W = 80mm, H = 100mm
    )

    # Production Baseline Strategy A:
    prod_views = _views_to_prod_dicts([top, side])
    prod_links = _derive_links(prod_views)
    assert len(prod_links) == 0

    # Strategy D:
    engine = OrthographicAlignmentEngine()
    result = engine.analyze([top, side])
    assert result["valid"] is True
    depth_links = [l for l in result["links"] if l.relation_type == "VIEWS_DEPTH_CORRESPONDENCE"]
    assert len(depth_links) == 1
    assert depth_links[0].source_id == "view-side"
    assert depth_links[0].target_id == "view-top"
    assert depth_links[0].diagnostics["relative_depth_error"] <= 0.01
