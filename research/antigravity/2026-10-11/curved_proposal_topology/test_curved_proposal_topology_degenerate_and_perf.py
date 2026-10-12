"""Degenerate, Numeric Safety, and Performance Profiling Tests for Topic 27:
EXTERNAL_VISUAL_OBJECT_PROPOSAL_CURVED_TOPOLOGY_V1.

Evaluates 7 stress cases:
1. Empty primitive hypotheses list rejection
2. Micro-radius circle numeric safety (10^-5 px)
3. Micro-sweep arc numeric safety (0.001 deg)
4. Non-finite coordinates (NaN / Inf) rejection
5. Excessive endpoint tolerance (> 64px) rejection
6. Duplicate primitive and group IDs rejection
7. Large-scale hybrid topology throughput profiling (120 primitives < 20 ms)
"""

import sys
import time
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
        "source_sha256": "1" * 64,
        "page_index": 0,
        "source_render_sha256": "2" * 64,
        "roi_bbox_px": [0, 0, 1000, 1000],
    }


def test_edge_1_empty_primitives_list_rejection():
    """Edge 1: Rejection of empty primitive hypotheses list."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [],
        "object_groups": [],
        "excluded_memberships": [],
    }
    with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESES_INVALID"):
        StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)


def test_edge_2_micro_radius_circle_numeric_safety():
    """Edge 2: Micro-radius circle (10^-5 px) compiles cleanly."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "c_micro", "type": "CIRCLE", "center_px": [100.0, 100.0], "radius_px": 1e-5},
        ],
        "object_groups": [{"group_id": "g1", "proposed_label": "MICRO_HOLE", "primitive_hypothesis_ids": ["c_micro"]}],
        "excluded_memberships": [],
    }
    res = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert res["primitive_hypotheses"][0]["radius_px"] == 1e-5


def test_edge_3_micro_sweep_arc_numeric_safety():
    """Edge 3: Micro-sweep arc (0.001 deg) compiles cleanly."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "a_micro", "type": "ARC", "center_px": [100.0, 100.0], "radius_px": 10.0, "start_angle_deg": 45.0, "end_angle_deg": 45.001},
        ],
        "object_groups": [{"group_id": "g1", "proposed_label": "MICRO_ARC", "primitive_hypothesis_ids": ["a_micro"]}],
        "excluded_memberships": [],
    }
    res = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    assert res["primitive_hypotheses"][0]["end_angle_deg"] == 45.001


def test_edge_4_non_finite_coordinates_nan_inf():
    """Edge 4: Non-finite NaN and Inf coordinates rejected."""
    binding = _base_binding()
    for bad_val in [float("nan"), float("inf"), float("-inf")]:
        proposal = {
            "schema_version": "external-visual-object-proposal-1.0",
            "proposal_source": "external_ai",
            **binding,
            "view_role_proposal": "FRONT",
            "primitive_hypotheses": [
                {"id": "c_nan", "type": "CIRCLE", "center_px": [bad_val, 100.0], "radius_px": 10.0},
            ],
            "object_groups": [{"group_id": "g1", "proposed_label": "HOLE", "primitive_hypothesis_ids": ["c_nan"]}],
            "excluded_memberships": [],
        }
        with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_INVALID"):
            StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)


def test_edge_5_excessive_endpoint_tolerance():
    """Edge 5: Endpoint tolerance > 64px rejected."""
    binding = _base_binding()
    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "l1", "type": "LINE", "start_px": [10.0, 10.0], "end_px": [50.0, 10.0]},
        ],
        "object_groups": [
            {
                "group_id": "g1",
                "proposed_label": "LINE_GRP",
                "primitive_hypothesis_ids": ["l1"],
                "topology_hypothesis": {
                    "kind": "BOUNDARY_CHAIN",
                    "ordered_primitive_hypothesis_ids": ["l1"],
                    "closure": "OPEN",
                    "endpoint_tolerance_px": 65.0,  # 65 > 64!
                },
            }
        ],
        "excluded_memberships": [],
    }
    with pytest.raises(ValueError, match="GROUP_TOPOLOGY_INVALID"):
        StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)


def test_edge_6_duplicate_primitive_and_group_ids():
    """Edge 6: Duplicate IDs correctly rejected."""
    binding = _base_binding()
    # Duplicate primitive ID
    prop1 = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "dup_p", "type": "LINE", "start_px": [10.0, 10.0], "end_px": [50.0, 10.0]},
            {"id": "dup_p", "type": "LINE", "start_px": [50.0, 10.0], "end_px": [90.0, 10.0]},
        ],
        "object_groups": [{"group_id": "g1", "proposed_label": "GRP", "primitive_hypothesis_ids": ["dup_p"]}],
        "excluded_memberships": [],
    }
    with pytest.raises(ValueError, match="DUPLICATE_PRIMITIVE_HYPOTHESIS"):
        StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(prop1, binding)

    # Duplicate group ID
    prop2 = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "p1", "type": "LINE", "start_px": [10.0, 10.0], "end_px": [50.0, 10.0]},
            {"id": "p2", "type": "LINE", "start_px": [50.0, 10.0], "end_px": [90.0, 10.0]},
        ],
        "object_groups": [
            {"group_id": "dup_g", "proposed_label": "GRP1", "primitive_hypothesis_ids": ["p1"]},
            {"group_id": "dup_g", "proposed_label": "GRP2", "primitive_hypothesis_ids": ["p2"]},
        ],
        "excluded_memberships": [],
    }
    with pytest.raises(ValueError, match="GROUP_MEMBERSHIP_INVALID"):
        StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(prop2, binding)


def test_perf_7_large_scale_hybrid_topology_throughput():
    """Perf 7: Throughput and latency profiling with 120 primitives across 20 groups."""
    binding = _base_binding()
    prims = []
    groups = []

    # 20 slots: each slot has 2 lines and 2 arcs (4 primitives each) -> 80 primitives
    # Plus 40 circular holes -> 120 primitives total
    for i in range(20):
        cx = float(50 + (i % 5) * 180)
        cy = float(50 + (i // 5) * 180)
        # Slot
        l1_id = f"slot_{i}_l1"
        l2_id = f"slot_{i}_l2"
        a1_id = f"slot_{i}_a1"
        a2_id = f"slot_{i}_a2"
        prims.extend([
            {"id": l1_id, "type": "LINE", "start_px": [cx - 20, cy - 10], "end_px": [cx + 20, cy - 10]},
            {"id": a1_id, "type": "ARC", "center_px": [cx + 20, cy], "radius_px": 10.0, "start_angle_deg": 270.0, "end_angle_deg": 90.0},
            {"id": l2_id, "type": "LINE", "start_px": [cx + 20, cy + 10], "end_px": [cx - 20, cy + 10]},
            {"id": a2_id, "type": "ARC", "center_px": [cx - 20, cy], "radius_px": 10.0, "start_angle_deg": 90.0, "end_angle_deg": 270.0},
        ])
        groups.append({
            "group_id": f"slot_grp_{i}",
            "proposed_label": "SLOT_FEATURE",
            "primitive_hypothesis_ids": [l1_id, a1_id, l2_id, a2_id],
            "topology_hypothesis": {
                "kind": "BOUNDARY_CHAIN",
                "ordered_primitive_hypothesis_ids": [l1_id, a1_id, l2_id, a2_id],
                "closure": "CLOSED",
                "endpoint_tolerance_px": 2.0,
            },
        })

    for i in range(40):
        c_id = f"hole_{i}"
        prims.append({"id": c_id, "type": "CIRCLE", "center_px": [float(i * 20 + 20), 800.0], "radius_px": 5.0})
        groups.append({
            "group_id": f"hole_grp_{i}",
            "proposed_label": "HOLE_FEATURE",
            "primitive_hypothesis_ids": [c_id],
            "topology_hypothesis": {
                "kind": "BOUNDARY_CHAIN",
                "ordered_primitive_hypothesis_ids": [c_id],
                "closure": "CLOSED",
                "endpoint_tolerance_px": 1.0,
            },
        })

    proposal = {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": prims,
        "object_groups": groups,
        "excluded_memberships": [],
    }

    t0 = time.perf_counter()
    res = StrategyD_UnifiedCurvedTopologyOracle.compile_proposal(proposal, binding)
    dt_ms = (time.perf_counter() - t0) * 1000.0

    assert len(res["primitive_hypotheses"]) == 120
    assert len(res["object_groups"]) == 60
    throughput = len(prims) / (dt_ms / 1000.0)
    print(f"\n[Perf] 120 curved primitives + 60 topological groups compiled in {dt_ms:.2f} ms ({throughput:.0f} prims/sec)")
    assert dt_ms < 20.0, f"Compilation latency {dt_ms:.2f} ms exceeded 20 ms budget"
