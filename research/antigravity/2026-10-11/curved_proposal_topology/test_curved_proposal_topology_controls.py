"""Positive and Negative Controls for Topic 27:
EXTERNAL_VISUAL_OBJECT_PROPOSAL_CURVED_TOPOLOGY_V1.

8 formal boundary controls:
1. Positive valid circular proposal compilation
2. Positive valid arc proposal compilation
3. Negative circle zero or negative radius rejection
4. Negative arc zero or negative radius rejection
5. Negative arc identical start and end angle rejection
6. Negative primitive coordinate outside ROI bounding box
7. Negative unclosed loop marked as CLOSED rejection
8. Negative exclusion contradiction rejection
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

from curved_proposal_topology_engine import (
    StrategyD_UnifiedCurvedTopologyOracle,
)


def _base_binding():
    return {
        "source_sha256": "e" * 64,
        "page_index": 0,
        "source_render_sha256": "f" * 64,
        "roi_bbox_px": [10, 10, 300, 300],
    }


def test_ctrl_1_positive_valid_circular_proposal():
    """Ctrl 1: Valid circle hypothesis compilation."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "c1", "type": "CIRCLE", "center_px": [150.0, 150.0], "radius_px": 50.0},
        ],
        "object_groups": [
            {"group_id": "g1", "proposed_label": "SHAFT_BORE", "primitive_hypothesis_ids": ["c1"]}
        ],
        "excluded_memberships": [],
    }
    res = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert res["status"] == "PROPOSAL_ONLY"
    assert res["primitive_hypotheses"][0]["radius_px"] == 50.0


def test_ctrl_2_positive_valid_arc_proposal():
    """Ctrl 2: Valid arc hypothesis compilation."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "a1", "type": "ARC", "center_px": [150.0, 150.0], "radius_px": 40.0, "start_angle_deg": 30.0, "end_angle_deg": 120.0},
        ],
        "object_groups": [
            {"group_id": "g1", "proposed_label": "CURVED_LIP", "primitive_hypothesis_ids": ["a1"]}
        ],
        "excluded_memberships": [],
    }
    res = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert res["primitive_hypotheses"][0]["start_angle_deg"] == 30.0
    assert res["primitive_hypotheses"][0]["end_angle_deg"] == 120.0


def test_ctrl_3_negative_circle_zero_or_negative_radius():
    """Ctrl 3: Negative rejection of circle radius <= 0."""
    binding = _base_binding()
    for bad_r in [0.0, -10.0]:
        proposal = {
            "schema_version": "external-visual-object-proposal-1.0",
            "proposal_source": "external_ai",
            **binding,
            "view_role_proposal": "FRONT",
            "primitive_hypotheses": [
                {"id": "c_bad", "type": "CIRCLE", "center_px": [150.0, 150.0], "radius_px": bad_r},
            ],
            "object_groups": [{"group_id": "g1", "proposed_label": "HOLE", "primitive_hypothesis_ids": ["c_bad"]}],
            "excluded_memberships": [],
        }
        with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_INVALID"):
            StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)


def test_ctrl_4_negative_arc_zero_or_negative_radius():
    """Ctrl 4: Negative rejection of arc radius <= 0."""
    binding = _base_binding()
    for bad_r in [0.0, -5.0]:
        proposal = {
            "schema_version": "external-visual-object-proposal-1.0",
            "proposal_source": "external_ai",
            **binding,
            "view_role_proposal": "FRONT",
            "primitive_hypotheses": [
                {"id": "a_bad", "type": "ARC", "center_px": [150.0, 150.0], "radius_px": bad_r, "start_angle_deg": 0.0, "end_angle_deg": 90.0},
            ],
            "object_groups": [{"group_id": "g1", "proposed_label": "ARC", "primitive_hypothesis_ids": ["a_bad"]}],
            "excluded_memberships": [],
        }
        with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_INVALID"):
            StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)


def test_ctrl_5_negative_arc_equal_start_end_angle():
    """Ctrl 5: Negative rejection of arc with identical start and end angle (0 sweep)."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "a_bad", "type": "ARC", "center_px": [150.0, 150.0], "radius_px": 25.0, "start_angle_deg": 45.0, "end_angle_deg": 45.0},
        ],
        "object_groups": [{"group_id": "g1", "proposed_label": "ARC", "primitive_hypothesis_ids": ["a_bad"]}],
        "excluded_memberships": [],
    }
    with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_INVALID"):
        StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)


def test_ctrl_6_negative_primitive_outside_roi():
    """Ctrl 6: Negative rejection of primitive positioned outside ROI bounds."""
    binding = _base_binding() # ROI: [10, 10, 300, 300]
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "c_out", "type": "CIRCLE", "center_px": [400.0, 150.0], "radius_px": 25.0}, # x=400 > 300!
        ],
        "object_groups": [{"group_id": "g1", "proposed_label": "HOLE", "primitive_hypothesis_ids": ["c_out"]}],
        "excluded_memberships": [],
    }
    with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_OUTSIDE_ROI"):
        StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)


def test_ctrl_7_negative_unclosed_loop_marked_closed():
    """Ctrl 7: Negative rejection of open chain marked as CLOSED."""
    binding = _base_binding()
    # 3 lines forming a U-shape, ends at (20, 20) and (20, 100) with 80px gap
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "l1", "type": "LINE", "start_px": [20.0, 20.0], "end_px": [100.0, 20.0]},
            {"id": "l2", "type": "LINE", "start_px": [100.0, 20.0], "end_px": [100.0, 100.0]},
            {"id": "l3", "type": "LINE", "start_px": [100.0, 100.0], "end_px": [20.0, 100.0]},
        ],
        "object_groups": [
            {
                "group_id": "g1",
                "proposed_label": "OPEN_U_SHAPE",
                "primitive_hypothesis_ids": ["l1", "l2", "l3"],
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ["l1", "l2", "l3"],
                    "closure": "CLOSED",  # Unclosed U-shape marked CLOSED!
                    "endpoint_tolerance_px": 5.0,
                },
            }
        ],
        "excluded_memberships": [],
    }
    with pytest.raises(ValueError, match="GROUP_TOPOLOGY_DISCONNECTED"):
        StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)


def test_ctrl_8_negative_exclusion_contradiction():
    """Ctrl 8: Negative rejection of primitive simultaneously member and excluded."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "l1", "type": "LINE", "start_px": [20.0, 20.0], "end_px": [100.0, 20.0]},
        ],
        "object_groups": [
            {"group_id": "g1", "proposed_label": "LINE_GRP", "primitive_hypothesis_ids": ["l1"]}
        ],
        "excluded_memberships": [
            {"primitive_hypothesis_id": "l1", "excluded_group_id": "g1"}  # Contradiction!
        ],
    }
    with pytest.raises(ValueError, match="EXCLUSION_CONTRADICTION"):
        StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
