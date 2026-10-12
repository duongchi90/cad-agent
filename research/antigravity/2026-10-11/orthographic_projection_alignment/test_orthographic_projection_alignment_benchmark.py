"""test_orthographic_projection_alignment_benchmark.py — Multi-Strategy Benchmark Suite.

Compares:
- Strategy A: Current Production Baseline (cad_agent/component_view_registry.py _derive_links)
- Strategy B: Naive Bounding-Box Proximity Matcher
- Strategy C: Axis-Aligned Interval Overlap Matcher
- Strategy D: Robust Multi-View Orthographic Projection Alignment Engine

Across 8 discriminating benchmark scenarios.
"""

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
    run_strategy_b,
    run_strategy_c,
)


def _views_to_prod_dicts(views: list[ViewRegion]) -> list[dict]:
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


def test_benchmark_scenario_01_standard_three_view_third_angle():
    """Scenario 1: Standard 3-view machined part in Third-Angle projection (ASME)."""
    # Front: X[100, 300], Y[100, 220] (W=200, H=120)
    front_prims = [
        ViewPrimitive("f1", "LINE", (100, 100), (300, 100)),
        ViewPrimitive("f2", "LINE", (100, 160), (300, 160)),  # step
        ViewPrimitive("f3", "LINE", (100, 220), (300, 220)),
        ViewPrimitive("f4", "LINE", (180, 100), (180, 220)),  # hole center line
    ]
    front = ViewRegion("front", "FRONT", (100, 100, 300, 220), primitives=front_prims)

    # Top: X[100, 300], Y[260, 340] (W=200, H=80, Depth=80)
    top_prims = [
        ViewPrimitive("t1", "LINE", (100, 260), (300, 260)),
        ViewPrimitive("t2", "LINE", (100, 340), (300, 340)),
        ViewPrimitive("t3", "LINE", (180, 260), (180, 340)),  # matching hole line
    ]
    top = ViewRegion("top", "TOP", (100, 260, 300, 340), primitives=top_prims)

    # Right-Side: X[360, 440], Y[100, 220] (W=80, H=120, Depth=80)
    side_prims = [
        ViewPrimitive("s1", "LINE", (360, 100), (440, 100)),
        ViewPrimitive("s2", "LINE", (360, 160), (440, 160)),  # matching step
        ViewPrimitive("s3", "LINE", (360, 220), (440, 220)),
    ]
    side = ViewRegion("side", "RIGHT_SIDE", (360, 100, 440, 220), primitives=side_prims)

    views = [front, top, side]

    # Strategy A:
    res_a = run_strategy_a(views)
    assert len(res_a) == 0  # 0% discovery without manual component IDs

    # Strategy B:
    res_b = run_strategy_b(views, max_proximity_mm=300.0)
    # Proximity links without directional meaning
    assert all(l.relation_type == "VIEWS_SHARE_COMPONENT" for l in res_b)

    # Strategy C:
    res_c = run_strategy_c(views)
    # Strategy C detects overlaps but misses depth miter and projection system
    c_types = {l.relation_type for l in res_c}
    assert "VIEWS_DEPTH_CORRESPONDENCE" not in c_types

    # Strategy D:
    engine = OrthographicAlignmentEngine()
    res_d = engine.analyze(views)
    assert res_d["valid"] is True
    assert res_d["inferred_projection_system"] == "THIRD_ANGLE"
    types_d = {l.relation_type for l in res_d["links"]}
    assert "VIEWS_ALIGNED_HORIZONTALLY" in types_d
    assert "VIEWS_ALIGNED_VERTICALLY" in types_d
    assert "VIEWS_DEPTH_CORRESPONDENCE" in types_d
    assert "VIEWS_ORTHOGRAPHIC_PROJECTION_PAIR" in types_d


def test_benchmark_scenario_02_standard_three_view_first_angle():
    """Scenario 2: Standard 3-view bracket in First-Angle projection (ISO 5456-2)."""
    # Front: X[150, 350], Y[200, 320] (W=200, H=120)
    front = ViewRegion("front", "FRONT", (150, 200, 350, 320))
    # Top placed BELOW Front in First-Angle: X[150, 350], Y[50, 130] (W=200, H=80)
    top = ViewRegion("top", "TOP", (150, 50, 350, 130))
    # Left-Side placed to the RIGHT of Front in First-Angle: X[400, 480], Y[200, 320] (W=80, H=120)
    side = ViewRegion("side", "LEFT_SIDE", (400, 200, 480, 320))

    views = [front, top, side]

    # Strategy A:
    assert len(run_strategy_a(views)) == 0

    # Strategy D:
    engine = OrthographicAlignmentEngine()
    res_d = engine.analyze(views)
    assert res_d["valid"] is True
    assert res_d["inferred_projection_system"] == "FIRST_ANGLE"
    pairs = [l for l in res_d["links"] if l.relation_type == "VIEWS_ORTHOGRAPHIC_PROJECTION_PAIR"]
    assert len(pairs) == 2


def test_benchmark_scenario_03_mixed_scale_detail_view():
    """Scenario 3: Elevation view at 1:1 scale and side view at 1:2 scale (detail view)."""
    # Front: scale 1.0, W=240, H=120
    front = ViewRegion("front", "FRONT", (100, 100, 340, 220), scale=1.0)
    # Side: scale 0.5 (half-scale), raw H=60 -> normalized H = 60 / 0.5 = 120
    # raw bbox: X[400, 440], Y[50, 110] -> normalized Y[100, 220]
    side = ViewRegion("side", "RIGHT_SIDE", (400, 50, 440, 110), scale=0.5)

    views = [front, side]

    # Strategy C: Raw coordinates do not overlap in Y (50..110 vs 100..220 -> minimal overlap)
    res_c = run_strategy_c(views)
    assert len(res_c) == 0 or not any(l.confidence >= 0.9 for l in res_c)

    # Strategy D: Scale normalization maps both to H=120mm with matching baselines
    engine = OrthographicAlignmentEngine()
    res_d = engine.analyze(views)
    assert res_d["valid"] is True
    h_links = [l for l in res_d["links"] if l.relation_type == "VIEWS_ALIGNED_HORIZONTALLY"]
    assert len(h_links) == 1
    assert h_links[0].diagnostics["relative_height_error"] <= 0.01


def test_benchmark_scenario_04_four_view_cross_shaft_with_feature_rays():
    """Scenario 4: 4-view drawing with rich feature rays across all views."""
    # Front: W=200, H=100
    front_prims = [
        ViewPrimitive("f1", "LINE", (100, 100), (300, 100)),
        ViewPrimitive("f2", "LINE", (100, 130), (300, 130)),
        ViewPrimitive("f3", "LINE", (100, 170), (300, 170)),
        ViewPrimitive("f4", "LINE", (100, 200), (300, 200)),
        ViewPrimitive("f5", "LINE", (150, 100), (150, 200)),
        ViewPrimitive("f6", "LINE", (250, 100), (250, 200)),
    ]
    front = ViewRegion("front", "FRONT", (100, 100, 300, 200), primitives=front_prims)

    # Top: W=200, H=60
    top_prims = [
        ViewPrimitive("t1", "LINE", (100, 250), (300, 250)),
        ViewPrimitive("t2", "LINE", (100, 310), (300, 310)),
        ViewPrimitive("t3", "LINE", (150, 250), (150, 310)),
        ViewPrimitive("t4", "LINE", (250, 250), (250, 310)),
    ]
    top = ViewRegion("top", "TOP", (100, 250, 300, 310), primitives=top_prims)

    # Right Side: W=60, H=100
    r_side_prims = [
        ViewPrimitive("r1", "LINE", (350, 100), (410, 100)),
        ViewPrimitive("r2", "LINE", (350, 130), (410, 130)),
        ViewPrimitive("r3", "LINE", (350, 170), (410, 170)),
        ViewPrimitive("r4", "LINE", (350, 200), (410, 200)),
    ]
    r_side = ViewRegion("r_side", "RIGHT_SIDE", (350, 100, 410, 200), primitives=r_side_prims)

    # Left Side: W=60, H=100
    l_side_prims = [
        ViewPrimitive("l1", "LINE", (10, 100), (70, 100)),
        ViewPrimitive("l2", "LINE", (10, 130), (70, 130)),
        ViewPrimitive("l3", "LINE", (10, 170), (70, 170)),
        ViewPrimitive("l4", "LINE", (10, 200), (70, 200)),
    ]
    l_side = ViewRegion("l_side", "LEFT_SIDE", (10, 100, 70, 200), primitives=l_side_prims)

    views = [front, top, r_side, l_side]

    # Strategy D:
    engine = OrthographicAlignmentEngine()
    res_d = engine.analyze(views)
    assert res_d["valid"] is True
    assert res_d["inferred_projection_system"] == "THIRD_ANGLE"
    h_links = [l for l in res_d["links"] if l.relation_type == "VIEWS_ALIGNED_HORIZONTALLY"]
    assert len(h_links) == 3  # front <-> r_side, front <-> l_side, and r_side <-> l_side
    v_links = [l for l in res_d["links"] if l.relation_type == "VIEWS_ALIGNED_VERTICALLY"]
    assert len(v_links) == 1  # front <-> top


def test_benchmark_scenario_05_unaligned_auxiliary_or_isometric_view():
    """Scenario 5: 3D Isometric pictorial view present alongside orthographic views."""
    front = ViewRegion("front", "FRONT", (100, 100, 300, 200))
    side = ViewRegion("side", "RIGHT_SIDE", (350, 100, 450, 200))
    # Isometric view positioned in top corner: X[400, 550], Y[250, 400]
    iso = ViewRegion("iso", "ISOMETRIC", (400, 250, 550, 400))

    views = [front, side, iso]

    # Strategy B links iso to side and front because dist < 300mm:
    res_b = run_strategy_b(views, max_proximity_mm=300.0)
    iso_links_b = [l for l in res_b if "iso" in (l.source_id, l.target_id)]
    assert len(iso_links_b) > 0  # False positive cluster

    # Strategy D does NOT link isometric view into orthographic projection chains:
    engine = OrthographicAlignmentEngine()
    res_d = engine.analyze(views)
    assert res_d["valid"] is True
    iso_links_d = [l for l in res_d["links"] if "iso" in (l.source_id, l.target_id)]
    assert len(iso_links_d) == 0


def test_benchmark_scenario_06_inverted_role_layout_detection():
    """Scenario 6: Inverted role layout where Top view is below Front in Third Angle."""
    front = ViewRegion("front", "FRONT", (100, 200, 300, 300))
    side = ViewRegion("side", "RIGHT_SIDE", (350, 200, 450, 300))
    # Top view mistakenly placed below Front view:
    top_inverted = ViewRegion("top", "TOP", (100, 50, 300, 150))

    views = [front, side, top_inverted]

    # Strategy A & C do not detect the flaw:
    assert len(run_strategy_a(views)) == 0

    # Strategy D detects the layout inversion and rejects:
    engine = OrthographicAlignmentEngine()
    res_d = engine.analyze(views, declared_projection_system="THIRD_ANGLE")
    assert res_d["valid"] is False
    assert any("ROLE_LAYOUT_INVERSION_REJECTED" in inc for inc in res_d["incompatibilities"])


def test_benchmark_scenario_07_geometric_dimension_incompatibility_rejection():
    """Scenario 7: Views sharing component_id but having incompatible dimensions."""
    front = ViewRegion("front", "FRONT", (100, 100, 300, 200), component_ids=["comp-A"])  # H=100, W=200
    side = ViewRegion("side", "RIGHT_SIDE", (400, 100, 500, 450), component_ids=["comp-A"])  # H=350, W=100 (H mismatch 250%)

    views = [front, side]

    # Strategy A falsely declares they share component:
    res_a = run_strategy_a(views)
    assert any(l.relation_type == "VIEWS_SHARE_COMPONENT" for l in res_a)

    # Strategy D detects geometric incompatibility and suppresses:
    engine = OrthographicAlignmentEngine()
    res_d = engine.analyze(views)
    assert res_d["valid"] is False
    assert any("GEOMETRIC_INCOMPATIBILITY_REJECTED" in inc for inc in res_d["incompatibilities"])
    assert not any(l.relation_type == "VIEWS_SHARE_COMPONENT" for l in res_d["links"])


def test_benchmark_scenario_08_dense_multi_part_sheet_disambiguation():
    """Scenario 8: Multi-part sheet with two distinct parts placed adjacent to each other."""
    # Part 1: Shaft (Front & Side) at Y[50, 150]
    p1_front = ViewRegion("p1_f", "FRONT", (50, 50, 200, 150))
    p1_side = ViewRegion("p1_s", "RIGHT_SIDE", (240, 50, 300, 150))

    # Part 2: Bracket (Front & Side) at Y[200, 350]
    p2_front = ViewRegion("p2_f", "FRONT", (50, 200, 200, 350))
    p2_side = ViewRegion("p2_s", "RIGHT_SIDE", (240, 200, 300, 350))

    views = [p1_front, p1_side, p2_front, p2_side]

    # Strategy B merges everything within 200mm:
    res_b = run_strategy_b(views, max_proximity_mm=250.0)
    # Strategy B links p1_front to p2_front (cross-part contamination):
    cross_links_b = [l for l in res_b if ("p1_f" in (l.source_id, l.target_id) and "p2_f" in (l.source_id, l.target_id))]
    assert len(cross_links_b) > 0

    # Strategy D strictly links p1_f <-> p1_s and p2_f <-> p2_s without cross-contamination:
    engine = OrthographicAlignmentEngine()
    res_d = engine.analyze(views)
    assert res_d["valid"] is True
    h_links = [l for l in res_d["links"] if l.relation_type == "VIEWS_ALIGNED_HORIZONTALLY"]
    assert len(h_links) == 2
    pairs = {(l.source_id, l.target_id) for l in h_links}
    assert ("p1_f", "p1_s") in pairs
    assert ("p2_f", "p2_s") in pairs
