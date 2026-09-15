from __future__ import annotations

import copy
import importlib
import json

import pytest


SOURCE_SHA256 = "13d822cf828cccc6cd21b19ec3c410f0ea89aef440aeca4c96248e86c08b5b38"
RENDER_SHA256 = "b03477a1f9cd5df4f8ee6125f8faed1bf35586cb4f891c30bf2351929833b9d0"
ROI = [1898, 216, 1942, 519]


def _binding() -> dict[str, object]:
    return {
        "source_sha256": SOURCE_SHA256,
        "page_index": 0,
        "source_render_sha256": RENDER_SHA256,
        "roi_bbox_px": list(ROI),
    }


def _proposal() -> dict[str, object]:
    return {
        "schema_version": "external-visual-object-proposal-1.0",
        "proposal_source": "external_ai",
        **_binding(),
        "view_role_proposal": "FRONT",
        "primitive_hypotheses": [
            {"id": "mirror_top", "type": "LINE", "start_px": [1912, 347], "end_px": [1942, 347]},
            {"id": "mirror_right", "type": "LINE", "start_px": [1942, 350], "end_px": [1942, 387]},
            {"id": "mirror_bottom", "type": "LINE", "start_px": [1912, 387], "end_px": [1942, 387]},
            {"id": "mirror_left", "type": "LINE", "start_px": [1912, 351], "end_px": [1912, 386]},
            {"id": "main_vertical", "type": "LINE", "start_px": [1905, 216], "end_px": [1905, 519]},
            {"id": "lower_slope", "type": "LINE", "start_px": [1905, 510], "end_px": [1898, 519]},
        ],
        "object_groups": [
            {
                "group_id": "front-right-mirror-001",
                "proposed_label": "RIGHT_MIRROR_HOUSING",
                "primitive_hypothesis_ids": [
                    "mirror_top",
                    "mirror_right",
                    "mirror_bottom",
                    "mirror_left",
                ],
            }
        ],
        "excluded_memberships": [
            {"primitive_hypothesis_id": "main_vertical", "excluded_group_id": "front-right-mirror-001"},
            {"primitive_hypothesis_id": "lower_slope", "excluded_group_id": "front-right-mirror-001"},
        ],
    }


def _proposal_with_topology() -> dict[str, object]:
    proposal = _proposal()
    proposal["object_groups"][0]["topology_hypothesis"] = {
        "kind": "BOUNDARY_CHAIN",
        "ordered_primitive_hypothesis_ids": [
            "mirror_top",
            "mirror_right",
            "mirror_bottom",
            "mirror_left",
        ],
        "closure": "UNRESOLVED",
        "endpoint_tolerance_px": 4,
    }
    return proposal


def _compiler():
    module = importlib.import_module("cad_agent.source_fusion_proposal")
    compiler = getattr(module, "compile_external_visual_object_proposal", None)
    assert callable(compiler)
    return compiler


def test_compile_only_external_visual_object_proposal_contract_exists() -> None:
    _compiler()


def test_benchmark_proposal_compiles_to_proposal_only_verification_request() -> None:
    result = _compiler()(proposal=_proposal(), expected_binding=_binding())

    assert result["kind"] == "DETERMINISTIC_GEOMETRY_VERIFICATION_REQUEST"
    assert result["status"] == "PROPOSAL_ONLY"
    assert result["exact_source_binding"] == _binding()
    assert result["view_role_proposal"] == "FRONT"
    assert result["checks_required"] == [
        "EXACT_SOURCE_BINDING",
        "PER_PRIMITIVE_SOURCE_SUPPORT",
        "GROUP_TOPOLOGY",
        "EXCLUSION_CONSISTENCY",
    ]
    assert result["semantic_label_authority"] == "NONE"
    assert result["primitive_ir_materialized"] is False
    assert result["semantic_observation_materialized"] is False
    assert result["cad_mutation"] is False
    assert len(result["verification_request_sha256"]) == 64
    assert "geometry_opencv" not in json.dumps(result, sort_keys=True)


def test_compile_is_deterministic_and_preserves_benchmark_membership_as_proposal() -> None:
    first = _compiler()(proposal=_proposal(), expected_binding=_binding())
    second = _compiler()(proposal=_proposal(), expected_binding=_binding())

    assert first == second
    assert first["object_groups"] == _proposal()["object_groups"]
    assert first["excluded_memberships"] == _proposal()["excluded_memberships"]


def test_boundary_topology_hypothesis_is_preserved_without_forcing_closure() -> None:
    proposal = _proposal_with_topology()
    result = _compiler()(proposal=proposal, expected_binding=_binding())

    topology = result["object_groups"][0]["topology_hypothesis"]
    assert topology == proposal["object_groups"][0]["topology_hypothesis"]
    assert topology["closure"] == "UNRESOLVED"
    assert result["semantic_label_authority"] == "NONE"
    assert result["primitive_ir_materialized"] is False
    assert result["cad_mutation"] is False


@pytest.mark.parametrize("field", ["source_sha256", "page_index", "source_render_sha256", "roi_bbox_px"])
def test_binding_mismatch_fails_closed(field: str) -> None:
    expected = _binding()
    if field == "page_index":
        expected[field] = 1
    elif field == "roi_bbox_px":
        expected[field] = [1899, 216, 1942, 519]
    else:
        expected[field] = "0" * 64

    with pytest.raises(ValueError, match="BINDING_MISMATCH"):
        _compiler()(proposal=_proposal(), expected_binding=expected)


def test_closed_schema_rejects_execution_payload_and_non_external_source() -> None:
    with_payload = _proposal()
    with_payload["command"] = "draw"
    with pytest.raises(ValueError, match="PROPOSAL_FIELDS_INVALID"):
        _compiler()(proposal=with_payload, expected_binding=_binding())

    wrong_source = _proposal()
    wrong_source["proposal_source"] = "geometry_opencv"
    with pytest.raises(ValueError, match="PROPOSAL_SOURCE_INVALID"):
        _compiler()(proposal=wrong_source, expected_binding=_binding())


def test_primitive_hypotheses_are_line_only_unique_and_inside_roi() -> None:
    unsupported = _proposal()
    unsupported["primitive_hypotheses"][0]["type"] = "CIRCLE"
    with pytest.raises(ValueError, match="PRIMITIVE_HYPOTHESIS_INVALID"):
        _compiler()(proposal=unsupported, expected_binding=_binding())

    duplicate = _proposal()
    duplicate["primitive_hypotheses"][1]["id"] = "mirror_top"
    with pytest.raises(ValueError, match="DUPLICATE_PRIMITIVE_HYPOTHESIS"):
        _compiler()(proposal=duplicate, expected_binding=_binding())

    outside = _proposal()
    outside["primitive_hypotheses"][0]["start_px"] = [1897, 347]
    with pytest.raises(ValueError, match="PRIMITIVE_OUTSIDE_ROI"):
        _compiler()(proposal=outside, expected_binding=_binding())


def test_group_and_exclusion_references_fail_closed() -> None:
    foreign_member = _proposal()
    foreign_member["object_groups"][0]["primitive_hypothesis_ids"].append("not-present")
    with pytest.raises(ValueError, match="GROUP_MEMBERSHIP_INVALID"):
        _compiler()(proposal=foreign_member, expected_binding=_binding())

    contradiction = _proposal()
    contradiction["excluded_memberships"][0]["primitive_hypothesis_id"] = "mirror_top"
    with pytest.raises(ValueError, match="EXCLUSION_CONTRADICTION"):
        _compiler()(proposal=contradiction, expected_binding=_binding())


def test_input_is_detached_and_not_mutated() -> None:
    proposal = _proposal()
    expected = _binding()
    proposal_before = copy.deepcopy(proposal)
    expected_before = copy.deepcopy(expected)

    _compiler()(proposal=proposal, expected_binding=expected)

    assert proposal == proposal_before
    assert expected == expected_before
