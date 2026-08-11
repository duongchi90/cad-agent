from __future__ import annotations

import json
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.visual_contracts import (
    SUPPORTED_VISUAL_CONTRACTS,
    VisualContractError,
    read_visual_contract,
    validate_visual_contract,
)
from tests.visual_supervisor_fixtures import (
    valid_dimension_register,
    valid_dimension_observer_evidence,
    valid_geometry_comparison,
    valid_visual_review,
    valid_visual_run_manifest,
)


def test_visual_run_manifest_validates_and_is_deep_copied() -> None:
    source = valid_visual_run_manifest()
    validated = validate_visual_contract(source, contract="visual_run_manifest")
    assert validated == source
    source["state"] = "MUTATED_BY_CALLER"
    assert validated["state"] == "CREATED"


def test_visual_run_manifest_rejects_unknown_state() -> None:
    payload = valid_visual_run_manifest()
    payload["state"] = "DONE_ENOUGH"
    with pytest.raises(VisualContractError, match="state"):
        validate_visual_contract(payload, contract="visual_run_manifest")


def test_visual_run_manifest_rejects_unexpected_property() -> None:
    payload = valid_visual_run_manifest()
    payload["codex_says_ok"] = True
    with pytest.raises(VisualContractError, match="Unexpected properties"):
        validate_visual_contract(payload, contract="visual_run_manifest")


def test_read_visual_contract_rejects_non_object_root(tmp_path: Path) -> None:
    source = tmp_path / "manifest.json"
    source.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    with pytest.raises(VisualContractError, match="root must be an object"):
        read_visual_contract(source, contract="visual_run_manifest")


def test_confirmed_driving_dimension_requires_both_attachments() -> None:
    payload = valid_dimension_register()
    del payload["dimensions"][0]["to_ref"]
    with pytest.raises(VisualContractError, match="to_ref"):
        validate_visual_contract(payload, contract="dimension_register")


def test_unresolved_critical_dimension_requires_blocker_scope() -> None:
    payload = valid_dimension_register()
    dimension = payload["dimensions"][0]
    dimension["role"] = "AMBIGUOUS"
    dimension["status"] = "UNRESOLVED"
    dimension["blocker_scope"] = []
    payload["summary"] = {"confirmed": 0, "unresolved": 1, "conflicts": 0}
    with pytest.raises(VisualContractError, match="blocker_scope"):
        validate_visual_contract(payload, contract="dimension_register")


def test_dimension_register_accepts_page_with_no_dimension_clusters() -> None:
    payload = valid_dimension_register()
    payload["coverage"] = {
        "clusters_detected": 0,
        "clusters_processed": 0,
        "page_coverage_percent": 100.0,
    }
    payload["summary"] = {"confirmed": 0, "unresolved": 0, "conflicts": 0}
    payload["dimensions"] = []
    assert validate_visual_contract(payload, contract="dimension_register") == payload


def test_unreadable_unresolved_dimension_accepts_null_value() -> None:
    payload = valid_dimension_register()
    dimension = payload["dimensions"][0]
    dimension["value"] = None
    dimension["role"] = "AMBIGUOUS"
    dimension["status"] = "UNRESOLVED"
    dimension["blocker_scope"] = ["SIDE-CABIN"]
    payload["summary"] = {"confirmed": 0, "unresolved": 1, "conflicts": 0}
    assert validate_visual_contract(payload, contract="dimension_register") == payload


def test_confirmed_dimension_requires_numeric_value() -> None:
    payload = valid_dimension_register()
    payload["dimensions"][0]["value"] = None
    with pytest.raises(VisualContractError, match="value"):
        validate_visual_contract(payload, contract="dimension_register")


def test_unreadable_observation_accepts_empty_text_null_value_and_unit() -> None:
    payload = valid_dimension_register()
    item = payload["dimensions"][0]
    item.update({
        "display_text": "",
        "value": None,
        "unit": None,
        "role": "AMBIGUOUS",
        "status": "UNRESOLVED",
        "blocker_scope": ["SIDE-CABIN"],
        "raw_text_candidates": [],
    })
    payload["summary"] = {"confirmed": 0, "unresolved": 1, "conflicts": 0}
    assert validate_visual_contract(payload, contract="dimension_register") == payload


def test_confirmed_observation_requires_text_value_and_unit() -> None:
    for field, invalid in (("display_text", ""), ("value", None), ("unit", None)):
        payload = valid_dimension_register()
        payload["dimensions"][0][field] = invalid
        with pytest.raises(VisualContractError, match=field):
            validate_visual_contract(payload, contract="dimension_register")


def test_dimension_register_accepts_closed_observer_evidence_fields() -> None:
    payload = valid_dimension_register()
    payload["dimensions"][0].update(valid_dimension_observer_evidence())
    assert validate_visual_contract(payload, contract="dimension_register") == payload


def test_observer_evidence_rejects_unknown_property() -> None:
    payload = valid_dimension_register()
    evidence = valid_dimension_observer_evidence()
    evidence["provenance"]["codex_guess"] = True
    payload["dimensions"][0].update(evidence)
    with pytest.raises(VisualContractError, match="Unexpected properties"):
        validate_visual_contract(payload, contract="dimension_register")


def test_geometry_comparison_rejects_out_of_range_iou() -> None:
    payload = valid_geometry_comparison()
    payload["metrics"]["silhouette_iou"] = 1.1
    with pytest.raises(VisualContractError, match="silhouette_iou"):
        validate_visual_contract(payload, contract="geometry_comparison")


def test_geometry_comparison_rejects_aligned_without_two_anchors() -> None:
    payload = valid_geometry_comparison()
    payload["alignment"]["anchor_ids"] = ["ONLY_ONE"]
    with pytest.raises(VisualContractError, match="anchor_ids"):
        validate_visual_contract(payload, contract="geometry_comparison")


def test_geometry_comparison_rejects_non_finite_metric() -> None:
    payload = valid_geometry_comparison()
    payload["metrics"]["height_ratio_error"] = float("nan")
    with pytest.raises(VisualContractError, match="finite"):
        validate_visual_contract(payload, contract="geometry_comparison")


def test_visual_review_rejects_free_form_verdict() -> None:
    payload = valid_visual_review()
    payload["verdict"] = "LOOKS_GOOD"
    with pytest.raises(VisualContractError, match="verdict"):
        validate_visual_contract(payload, contract="visual_review")


def test_visual_review_pass_rejects_findings() -> None:
    payload = valid_visual_review()
    payload["verdict"] = "PASS"
    with pytest.raises(VisualContractError, match="PASS"):
        validate_visual_contract(payload, contract="visual_review")


def test_visual_review_fail_requires_actionable_repair_intent() -> None:
    payload = valid_visual_review()
    payload["repair_intent"]["change"] = []
    with pytest.raises(VisualContractError, match="change"):
        validate_visual_contract(payload, contract="visual_review")


def test_visual_review_needs_human_requires_requested_evidence_or_finding() -> None:
    payload = valid_visual_review()
    payload["verdict"] = "NEEDS_HUMAN"
    payload["findings"] = []
    payload["repair_intent"]["requested_next_evidence"] = []
    with pytest.raises(VisualContractError, match="NEEDS_HUMAN"):
        validate_visual_contract(payload, contract="visual_review")


def test_visual_review_pass_requires_info_severity() -> None:
    payload = valid_visual_review()
    payload["verdict"] = "PASS"
    payload["severity"] = "MAJOR"
    payload["findings"] = []
    payload["repair_intent"]["change"] = []
    with pytest.raises(VisualContractError, match="PASS"):
        validate_visual_contract(payload, contract="visual_review")


def test_visual_review_fail_requires_major_or_critical_top_level_severity() -> None:
    payload = valid_visual_review()
    payload["severity"] = "INFO"
    with pytest.raises(VisualContractError, match="FAIL"):
        validate_visual_contract(payload, contract="visual_review")


def test_supported_visual_contract_registry_is_exact() -> None:
    assert set(SUPPORTED_VISUAL_CONTRACTS) == {
        "visual_run_manifest",
        "dimension_register",
        "geometry_comparison",
        "visual_review",
        "repair_plan",
        "region_verification_register",
        "auto_publish_authorization",
        "visual_review_scope",
    }


def _valid_visual_review_scope() -> dict[str, object]:
    return {
        "schema_version": "visual-review-scope-1.0",
        "scope_id": "scope-r5-001",
        "run_id": "run-r5-001",
        "registry_snapshot_sha256": "a" * 64,
        "candidate_revision_sha256": "b" * 64,
        "candidate_state_sha256": "c" * 64,
        "regions": [
            {
                "region_id": "region-critical",
                "view_id": "view-front",
                "sheet_id": "sheet-a",
                "layout_id": "layout-a",
                "criticality": "CRITICAL",
            },
            {
                "region_id": "region-normal",
                "view_id": "view-side",
                "sheet_id": "sheet-b",
                "layout_id": "layout-b",
                "criticality": "NORMAL",
            },
        ],
    }


def test_visual_review_scope_validates_and_canonicalizes_region_order() -> None:
    payload = _valid_visual_review_scope()
    reversed_payload = _valid_visual_review_scope()
    reversed_payload["regions"] = list(reversed(reversed_payload["regions"]))

    validated = validate_visual_contract(payload, contract="visual_review_scope")
    reversed_validated = validate_visual_contract(reversed_payload, contract="visual_review_scope")

    assert [region["region_id"] for region in validated["regions"]] == [
        "region-critical",
        "region-normal",
    ]
    assert validated == reversed_validated
    assert canonical_json_sha256(validated) == canonical_json_sha256(reversed_validated)


def test_visual_review_scope_rejects_empty_required_region_set() -> None:
    payload = _valid_visual_review_scope()
    payload["regions"] = []
    with pytest.raises(VisualContractError, match="regions"):
        validate_visual_contract(payload, contract="visual_review_scope")


def test_visual_review_scope_rejects_unknown_region_property() -> None:
    payload = _valid_visual_review_scope()
    payload["regions"][0]["provider_scope"] = "caller-owned"
    with pytest.raises(VisualContractError, match="Unexpected properties"):
        validate_visual_contract(payload, contract="visual_review_scope")


def test_visual_review_scope_rejects_caller_owned_scope_replacement() -> None:
    payload = _valid_visual_review_scope()
    payload["required_region_ids"] = ["region-critical"]
    with pytest.raises(VisualContractError, match="Unexpected properties"):
        validate_visual_contract(payload, contract="visual_review_scope")


def test_visual_review_scope_rejects_duplicate_region_identity() -> None:
    payload = _valid_visual_review_scope()
    payload["regions"][1]["region_id"] = payload["regions"][0]["region_id"]
    with pytest.raises(VisualContractError, match="duplicate region_id"):
        validate_visual_contract(payload, contract="visual_review_scope")


def test_visual_review_scope_rejects_missing_explicit_membership_identity() -> None:
    for field in ("view_id", "sheet_id", "layout_id"):
        payload = _valid_visual_review_scope()
        del payload["regions"][0][field]
        with pytest.raises(VisualContractError, match=field):
            validate_visual_contract(payload, contract="visual_review_scope")


def test_visual_review_scope_rejects_invalid_criticality() -> None:
    for value in ("OPTIONAL", [], {}):
        payload = _valid_visual_review_scope()
        payload["regions"][0]["criticality"] = value
        with pytest.raises(VisualContractError, match="criticality"):
            validate_visual_contract(payload, contract="visual_review_scope")


def test_visual_review_scope_rejects_criticality_omission() -> None:
    payload = _valid_visual_review_scope()
    del payload["regions"][0]["criticality"]
    with pytest.raises(VisualContractError, match="criticality"):
        validate_visual_contract(payload, contract="visual_review_scope")


def test_visual_review_scope_rejects_path_or_name_inference() -> None:
    for field, value in (("sheet_id", "DISPLAY NAME"), ("layout_id", "C:/layout")):
        payload = _valid_visual_review_scope()
        payload["regions"][0][field] = value
        with pytest.raises(VisualContractError, match=field):
            validate_visual_contract(payload, contract="visual_review_scope")


def test_visual_review_scope_rejects_cross_scope_identity_substitution() -> None:
    for field in ("scope_id", "run_id", "candidate_revision_sha256", "candidate_state_sha256"):
        payload = _valid_visual_review_scope()
        payload[field] = "" if field in {"scope_id", "run_id"} else "not-a-sha"
        with pytest.raises(VisualContractError, match=field):
            validate_visual_contract(payload, contract="visual_review_scope")


def test_visual_review_scope_rejects_non_object_or_open_regions_payload() -> None:
    payload = _valid_visual_review_scope()
    payload["regions"] = {"region-critical": payload["regions"][0]}
    with pytest.raises(VisualContractError, match="regions"):
        validate_visual_contract(payload, contract="visual_review_scope")
