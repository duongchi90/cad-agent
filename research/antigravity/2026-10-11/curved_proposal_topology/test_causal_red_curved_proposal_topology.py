"""Public Causal RED for External Visual Object Proposal Curved Topology.

Reproduces 5 critical baseline failure modes on:
- cad_agent.source_fusion_proposal.compile_external_visual_object_proposal
"""

import sys
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from cad_agent.source_fusion_proposal import compile_external_visual_object_proposal
from curved_proposal_topology_engine import (
    StrategyA_ProductionBaseline,
    StrategyD_UnifiedCurvedTopologyOracle,
)


def _base_binding():
    return {
        "source_sha256": "a" * 64,
        "page_index": 0,
        "source_render_sha256": "b" * 64,
        "roi_bbox_px": [0, 0, 200, 200],
    }


def test_red_1_circle_primitive_causes_unhandled_crash():
    """RED 1: Baseline compiler raises PRIMITIVE_HYPOTHESIS_INVALID on CIRCLE."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {
                "id": "c1",
                "type": "CIRCLE",
                "center_px": [100.0, 100.0],
                "radius_px": 25.0,
            }
        ],
        "object_groups": [
            {
                "group_id": "grp1",
                "proposed_label": "BORE_HOLE",
                "primitive_hypothesis_ids": ["c1"],
            }
        ],
        "excluded_memberships": [],
    }

    # Causal Failure: Baseline rejects circle hypothesis
    with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_INVALID"):
        StrategyA_ProductionBaseline.compile_proposal(proposal, binding)

    # Strategy D successfully compiles circle
    result = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert result["kind"] == "DETERMINISTIC_GEOMETRY_VERIFICATION_REQUEST"
    assert len(result["primitive_hypotheses"]) == 1
    assert result["primitive_hypotheses"][0]["type"] == "CIRCLE"


def test_red_2_arc_primitive_causes_unhandled_crash():
    """RED 2: Baseline compiler raises PRIMITIVE_HYPOTHESIS_INVALID on ARC."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {
                "id": "a1",
                "type": "ARC",
                "center_px": [50.0, 50.0],
                "radius_px": 20.0,
                "start_angle_deg": 0.0,
                "end_angle_deg": 90.0,
            }
        ],
        "object_groups": [
            {
                "group_id": "grp1",
                "proposed_label": "FILLET_CORNER",
                "primitive_hypothesis_ids": ["a1"],
            }
        ],
        "excluded_memberships": [],
    }

    # Causal Failure: Baseline rejects arc hypothesis
    with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_INVALID"):
        StrategyA_ProductionBaseline.compile_proposal(proposal, binding)

    # Strategy D successfully compiles arc
    result = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert result["kind"] == "DETERMINISTIC_GEOMETRY_VERIFICATION_REQUEST"
    assert result["primitive_hypotheses"][0]["type"] == "ARC"


def test_red_3_single_circle_closed_topology_inadmissibility():
    """RED 3: Baseline compiler cannot validate single circle closed topology."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {
                "id": "c1",
                "type": "CIRCLE",
                "center_px": [100.0, 100.0],
                "radius_px": 30.0,
            }
        ],
        "object_groups": [
            {
                "group_id": "grp1",
                "proposed_label": "CIRCULAR_BOSS",
                "primitive_hypothesis_ids": ["c1"],
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ["c1"],
                    "closure": "CLOSED",
                    "endpoint_tolerance_px": 2,
                },
            }
        ],
        "excluded_memberships": [],
    }

    # Causal Failure: Baseline rejects circle
    with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_INVALID"):
        StrategyA_ProductionBaseline.compile_proposal(proposal, binding)

    # Strategy D successfully validates single circle as closed boundary chain
    result = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    top = result["object_groups"][0]["topology_hypothesis"]
    assert top["closure"] == "CLOSED"
    assert top["ordered_primitive_hypothesis_ids"] == ["c1"]


def test_red_4_hybrid_boundary_chain_line_arc_transition_crash():
    """RED 4: Baseline compiler crashes on hybrid line-arc connected contour."""
    binding = _base_binding()
    # Rounded L-bracket:
    # Line 1: (20, 100) -> (100, 100)
    # Arc 1: center (100, 80), r=20, start=270 deg (bottom, at 100,100), end=0 deg (right, at 120,80)
    # Line 2: (120, 80) -> (120, 20)
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "l1", "type": "LINE", "start_px": [20.0, 100.0], "end_px": [100.0, 100.0]},
            {"id": "a1", "type": "ARC", "center_px": [100.0, 80.0], "radius_px": 20.0, "start_angle_deg": 90.0, "end_angle_deg": 0.0},
            {"id": "l2", "type": "LINE", "start_px": [120.0, 80.0], "end_px": [120.0, 20.0]},
        ],
        "object_groups": [
            {
                "group_id": "grp1",
                "proposed_label": "ROUNDED_PROFILE",
                "primitive_hypothesis_ids": ["l1", "a1", "l2"],
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ["l1", "a1", "l2"],
                    "closure": "OPEN",
                    "endpoint_tolerance_px": 2,
                },
            }
        ],
        "excluded_memberships": [],
    }

    # Causal Failure: Baseline rejects arc
    with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_INVALID"):
        StrategyA_ProductionBaseline.compile_proposal(proposal, binding)

    # Strategy D validates G0 connectivity between line1 -> arc1 -> line2
    result = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert len(result["primitive_hypotheses"]) == 3
    assert result["object_groups"][0]["topology_hypothesis"]["closure"] == "OPEN"


def test_red_5_integer_only_endpoint_tolerance_rejection():
    """RED 5: Baseline compiler rejects non-integer endpoint tolerance (e.g. 2.5 px)."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "l1", "type": "LINE", "start_px": [10, 10], "end_px": [50, 10]},
            {"id": "l2", "type": "LINE", "start_px": [52, 10], "end_px": [100, 10]}, # gap of 2px
        ],
        "object_groups": [
            {
                "group_id": "grp1",
                "proposed_label": "DIVIDED_LINE",
                "primitive_hypothesis_ids": ["l1", "l2"],
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ["l1", "l2"],
                    "closure": "OPEN",
                    "endpoint_tolerance_px": 2.5,  # Sub-pixel floating point tolerance!
                },
            }
        ],
        "excluded_memberships": [],
    }

    # Causal Failure: Baseline rejects float tolerance as GROUP_TOPOLOGY_INVALID
    with pytest.raises(ValueError, match="GROUP_TOPOLOGY_INVALID"):
        StrategyA_ProductionBaseline.compile_proposal(proposal, binding)

    # Strategy D accepts floating-point tolerance
    result = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert result["object_groups"][0]["topology_hypothesis"]["endpoint_tolerance_px"] == 2.5
