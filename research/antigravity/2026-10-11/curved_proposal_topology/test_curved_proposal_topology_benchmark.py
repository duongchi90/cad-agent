"""Empirical Benchmark comparing Strategies A-D for Topic 27:
EXTERNAL_VISUAL_OBJECT_PROPOSAL_CURVED_TOPOLOGY_V1.

8 Benchmark Scenarios:
1. Standard Polygon (Pure Lines, Closed Boundary Chain)
2. Isolated Circular Bore (Single Circle, Closed Boundary Chain)
3. Isolated Fillet Arc (Open Arc, Boundary Chain)
4. Slotted Hole (2 Lines + 2 Arcs, Closed Hybrid Boundary Chain)
5. Rounded Rectangle (4 Lines + 4 Fillet Arcs, Closed Boundary Chain)
6. Disconnected Boundary Chain (Gap > Tolerance)
7. Single-Line False Closure Guard (Single Line cannot be CLOSED)
8. Complex Mechanical Flange with Outer Contour + Bolt Holes + Exclusions
"""

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

from curved_proposal_topology_engine import (
    StrategyA_ProductionBaseline,
    StrategyB_NaiveTypeExpansion,
    StrategyC_DisjointPartitioner,
    StrategyD_UnifiedCurvedTopologyOracle,
)


def _base_binding():
    return {
        "source_sha256": "c" * 64,
        "page_index": 0,
        "source_render_sha256": "d" * 64,
        "roi_bbox_px": [0, 0, 500, 500],
    }


def test_scenario_1_standard_polygon_pure_lines():
    """Scenario 1: Pure line closed rectangular contour."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "l1", "type": "LINE", "start_px": [10, 10], "end_px": [100, 10]},
            {"id": "l2", "type": "LINE", "start_px": [100, 10], "end_px": [100, 60]},
            {"id": "l3", "type": "LINE", "start_px": [100, 60], "end_px": [10, 60]},
            {"id": "l4", "type": "LINE", "start_px": [10, 60], "end_px": [10, 10]},
        ],
        "object_groups": [
            {
                "group_id": "grp1",
                "proposed_label": "RECTANGLE_OUTLINE",
                "primitive_hypothesis_ids": ["l1", "l2", "l3", "l4"],
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ["l1", "l2", "l3", "l4"],
                    "closure": "CLOSED",
                    "endpoint_tolerance_px": 2,
                },
            }
        ],
        "excluded_memberships": [],
    }

    # Strategy A passes pure lines
    res_a = StrategyA_ProductionBaseline.compile_proposal(proposal, binding)
    assert res_a["kind"] == "DETERMINISTIC_GEOMETRY_VERIFICATION_REQUEST"

    # Strategy D passes
    res_d = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert res_d["kind"] == "DETERMINISTIC_GEOMETRY_VERIFICATION_REQUEST"
    assert len(res_d["primitive_hypotheses"]) == 4


def test_scenario_2_isolated_circular_bore():
    """Scenario 2: Single circular bore hole with closed topology."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "TOP",
        "primitive_hypotheses": [
            {"id": "c1", "type": "CIRCLE", "center_px": [150.0, 150.0], "radius_px": 35.0},
        ],
        "object_groups": [
            {
                "group_id": "grp_hole",
                "proposed_label": "BORE_HOLE",
                "primitive_hypothesis_ids": ["c1"],
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ["c1"],
                    "closure": "CLOSED",
                    "endpoint_tolerance_px": 2.0,
                },
            }
        ],
        "excluded_memberships": [],
    }

    # Strategy A fails
    with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_INVALID"):
        StrategyA_ProductionBaseline.compile_proposal(proposal, binding)

    # Strategy B fails on line connectivity
    # Strategy C passes if disjoint, but fails if topology is attached
    with pytest.raises(ValueError, match="GROUP_TOPOLOGY_INVALID"):
        StrategyC_DisjointPartitioner.compile_proposal(proposal, binding)

    # Strategy D succeeds
    res_d = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert res_d["primitive_hypotheses"][0]["type"] == "CIRCLE"
    assert res_d["object_groups"][0]["topology_hypothesis"]["closure"] == "CLOSED"


def test_scenario_3_isolated_fillet_arc():
    """Scenario 3: Open fillet arc boundary chain."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "SIDE",
        "primitive_hypotheses": [
            {"id": "a1", "type": "ARC", "center_px": [80.0, 80.0], "radius_px": 20.0, "start_angle_deg": 0.0, "end_angle_deg": 90.0},
        ],
        "object_groups": [
            {
                "group_id": "grp_fillet",
                "proposed_label": "CORNER_FILLET",
                "primitive_hypothesis_ids": ["a1"],
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ["a1"],
                    "closure": "OPEN",
                    "endpoint_tolerance_px": 2.0,
                },
            }
        ],
        "excluded_memberships": [],
    }

    # Strategy A fails on arc
    with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_INVALID"):
        StrategyA_ProductionBaseline.compile_proposal(proposal, binding)

    # Strategy D succeeds
    res_d = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert res_d["primitive_hypotheses"][0]["type"] == "ARC"
    assert res_d["object_groups"][0]["topology_hypothesis"]["closure"] == "OPEN"


def test_scenario_4_slotted_hole_hybrid_chain():
    """Scenario 4: Slotted hole with 2 lines and 2 semicircular arcs."""
    binding = _base_binding()
    # Horizontal slot:
    # Top line: (100, 50) -> (200, 50)
    # Right arc: center (200, 75), r=25, start=270 deg (top, 200,50), end=90 deg (bottom, 200,100)
    # Bottom line: (200, 100) -> (100, 100)
    # Left arc: center (100, 75), r=25, start=90 deg (bottom, 100,100), end=270 deg (top, 100,50)
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "top_line", "type": "LINE", "start_px": [100.0, 50.0], "end_px": [200.0, 50.0]},
            {"id": "right_arc", "type": "ARC", "center_px": [200.0, 75.0], "radius_px": 25.0, "start_angle_deg": 270.0, "end_angle_deg": 90.0},
            {"id": "bot_line", "type": "LINE", "start_px": [200.0, 100.0], "end_px": [100.0, 100.0]},
            {"id": "left_arc", "type": "ARC", "center_px": [100.0, 75.0], "radius_px": 25.0, "start_angle_deg": 90.0, "end_angle_deg": 270.0},
        ],
        "object_groups": [
            {
                "group_id": "slot_grp",
                "proposed_label": "SLOTTED_HOLE",
                "primitive_hypothesis_ids": ["top_line", "right_arc", "bot_line", "left_arc"],
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ["top_line", "right_arc", "bot_line", "left_arc"],
                    "closure": "CLOSED",
                    "endpoint_tolerance_px": 2.0,
                },
            }
        ],
        "excluded_memberships": [],
    }

    # Strategy A fails on arc
    with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_INVALID"):
        StrategyA_ProductionBaseline.compile_proposal(proposal, binding)

    # Strategy B fails on hybrid connectivity
    with pytest.raises(ValueError, match="GROUP_TOPOLOGY_INVALID"):
        StrategyB_NaiveTypeExpansion.compile_proposal(proposal, binding)

    # Strategy C fails on hybrid chain
    with pytest.raises(ValueError, match="GROUP_TOPOLOGY_INVALID"):
        StrategyC_DisjointPartitioner.compile_proposal(proposal, binding)

    # Strategy D validates closed hybrid slot contour
    res_d = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert len(res_d["primitive_hypotheses"]) == 4
    assert res_d["object_groups"][0]["topology_hypothesis"]["closure"] == "CLOSED"


def test_scenario_5_rounded_rectangle_8_primitives():
    """Scenario 5: Rounded rectangle with 4 lines and 4 corner arcs."""
    binding = _base_binding()
    # Rectangle 100x100 with 10px corner fillets
    prims = [
        {"id": "l1", "type": "LINE", "start_px": [60.0, 50.0], "end_px": [140.0, 50.0]},
        {"id": "a1", "type": "ARC", "center_px": [140.0, 60.0], "radius_px": 10.0, "start_angle_deg": 270.0, "end_angle_deg": 0.0},
        {"id": "l2", "type": "LINE", "start_px": [150.0, 60.0], "end_px": [150.0, 140.0]},
        {"id": "a2", "type": "ARC", "center_px": [140.0, 140.0], "radius_px": 10.0, "start_angle_deg": 0.0, "end_angle_deg": 90.0},
        {"id": "l3", "type": "LINE", "start_px": [140.0, 150.0], "end_px": [60.0, 150.0]},
        {"id": "a3", "type": "ARC", "center_px": [60.0, 140.0], "radius_px": 10.0, "start_angle_deg": 90.0, "end_angle_deg": 180.0},
        {"id": "l4", "type": "LINE", "start_px": [50.0, 140.0], "end_px": [50.0, 60.0]},
        {"id": "a4", "type": "ARC", "center_px": [60.0, 60.0], "radius_px": 10.0, "start_angle_deg": 180.0, "end_angle_deg": 270.0},
    ]
    ids = [p["id"] for p in prims]
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": prims,
        "object_groups": [
            {
                "group_id": "bracket_outline",
                "proposed_label": "FILLETED_BRACKET",
                "primitive_hypothesis_ids": ids,
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ids,
                    "closure": "CLOSED",
                    "endpoint_tolerance_px": 1.5,
                },
            }
        ],
        "excluded_memberships": [],
    }

    # Strategy D validates 8-primitive hybrid loop
    res_d = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert len(res_d["primitive_hypotheses"]) == 8
    assert res_d["object_groups"][0]["topology_hypothesis"]["closure"] == "CLOSED"


def test_scenario_6_disconnected_boundary_chain_rejection():
    """Scenario 6: Rejection of disconnected boundary chain where gap > tolerance."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "l1", "type": "LINE", "start_px": [10.0, 10.0], "end_px": [50.0, 10.0]},
            {"id": "l2", "type": "LINE", "start_px": [65.0, 10.0], "end_px": [100.0, 10.0]}, # gap of 15px!
        ],
        "object_groups": [
            {
                "group_id": "grp1",
                "proposed_label": "BROKEN_CHAIN",
                "primitive_hypothesis_ids": ["l1", "l2"],
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ["l1", "l2"],
                    "closure": "OPEN",
                    "endpoint_tolerance_px": 5.0,  # 5px < 15px gap
                },
            }
        ],
        "excluded_memberships": [],
    }

    # Strategy D correctly detects disconnected chain
    with pytest.raises(ValueError, match="GROUP_TOPOLOGY_DISCONNECTED"):
        StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)


def test_scenario_7_single_line_false_closure_guard():
    """Scenario 7: Rejection of single open line falsely marked as CLOSED."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "l1", "type": "LINE", "start_px": [10.0, 10.0], "end_px": [100.0, 10.0]},
        ],
        "object_groups": [
            {
                "group_id": "grp1",
                "proposed_label": "FAKE_CLOSED_LINE",
                "primitive_hypothesis_ids": ["l1"],
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ["l1"],
                    "closure": "CLOSED",  # A single line cannot be CLOSED!
                    "endpoint_tolerance_px": 2.0,
                },
            }
        ],
        "excluded_memberships": [],
    }

    # Strategy D rejects false closure on single line
    with pytest.raises(ValueError, match="GROUP_TOPOLOGY_INVALID"):
        StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)


def test_scenario_8_complex_mechanical_flange_with_bolt_holes():
    """Scenario 8: Complex mechanical flange with outer profile, 4 holes, and exclusions."""
    binding = _base_binding()
    prims = [
        # Outer circular flange
        {"id": "outer_circle", "type": "CIRCLE", "center_px": [250.0, 250.0], "radius_px": 100.0},
        # 4 internal bolt holes
        {"id": "h1", "type": "CIRCLE", "center_px": [200.0, 250.0], "radius_px": 10.0},
        {"id": "h2", "type": "CIRCLE", "center_px": [300.0, 250.0], "radius_px": 10.0},
        {"id": "h3", "type": "CIRCLE", "center_px": [250.0, 200.0], "radius_px": 10.0},
        {"id": "h4", "type": "CIRCLE", "center_px": [250.0, 300.0], "radius_px": 10.0},
    ]

    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": prims,
        "object_groups": [
            {
                "group_id": "outer_rim",
                "proposed_label": "FLANGE_BODY",
                "primitive_hypothesis_ids": ["outer_circle"],
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ["outer_circle"],
                    "closure": "CLOSED",
                    "endpoint_tolerance_px": 2.0,
                },
            },
            {
                "group_id": "bolt_pattern",
                "proposed_label": "BOLT_HOLE_PATTERN",
                "primitive_hypothesis_ids": ["h1", "h2", "h3", "h4"],
            },
        ],
        "excluded_memberships": [
            {"primitive_hypothesis_id": "outer_circle", "excluded_group_id": "bolt_pattern"},
            {"primitive_hypothesis_id": "h1", "excluded_group_id": "outer_rim"},
        ],
    }

    # Strategy D validates complete mechanical assembly
    res_d = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert len(res_d["primitive_hypotheses"]) == 5
    assert len(res_d["object_groups"]) == 2
    assert len(res_d["excluded_memberships"]) == 2
