"""Causal RED for the missing closed R5 -> R6 owner handoff."""

from __future__ import annotations

from copy import deepcopy
import inspect
from unittest.mock import Mock

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.repair_operation_contract import (
    REPAIR_OPERATION_SCHEMA_VERSION,
    normalize_repair_operation,
)
import cad_agent.approved_repair_adapter as r6
import cad_agent.visual_supervisor_adapter as r5


SHA_CANDIDATE = "a" * 64
SHA_STATE = "b" * 64
SHA_REGISTRY = "c" * 64
SHA_ARTIFACT = "d" * 64
SHA_REQUEST = "e" * 64
SHA_OBSERVATION = "f" * 64
SHA_MUTATION = "1" * 64
TARGET_HANDLE = "H276"
COMPONENT_ID = "component-276"
RUN_ID = "run-276"


def _verdict() -> dict[str, object]:
    semantic: dict[str, object] = {
        "schema_version": "r5-visual-verdict-result-1.0",
        "request_sha256": SHA_REQUEST,
        "observation_sha256": SHA_OBSERVATION,
        "verdict": "FAIL",
        "candidate_revision_sha256": SHA_CANDIDATE,
        "candidate_state_sha256": SHA_STATE,
        "registry_snapshot_sha256": SHA_REGISTRY,
        "drawing_reference_sha256": "2" * 64,
        "drawing_observation_sha256": "3" * 64,
        "latest_mutation_sha256": SHA_MUTATION,
        "task6_thread_id": "thread-276",
        "task6_turn_id": "turn-276",
        "regions": [
            {
                "region_id": "critical-region",
                "view_id": "view-276",
                "sheet_id": "sheet-276",
                "layout_id": "layout-276",
                "criticality": "CRITICAL",
                "status": "FAIL",
            }
        ],
    }
    digest = canonical_json_sha256(semantic)
    return {**semantic, "verdict_id": digest, "verdict_sha256": digest}


def _candidate_state() -> dict[str, object]:
    return {
        "schema_version": "candidate-revision-state-1.0",
        "state_sha256": SHA_STATE,
        "current_candidate_revision_sha256": SHA_CANDIDATE,
        "candidate_revisions": [
            {
                "schema_version": "candidate-revision-1.1",
                "candidate_kind": "ROOT_PRE_REPAIR",
                "revision_id": "candidate-276",
                "run_id": RUN_ID,
                "candidate_revision_sha256": SHA_CANDIDATE,
                "candidate_artifacts": {
                    "artifact_sha256": SHA_ARTIFACT,
                },
                "change_scope": {
                    "registry_snapshot_sha256": SHA_REGISTRY,
                    "impact": {
                        "component_ids": [COMPONENT_ID],
                        "view_ids": [],
                        "layout_bindings": [],
                        "link_ids": [],
                    },
                    "provenance_evidence": {},
                },
            }
        ],
    }


def _registry() -> dict[str, object]:
    return {
        "schema_version": "component-view-registry-1.0",
        "registry_snapshot_sha256": SHA_REGISTRY,
        "components": [
            {
                "component_id": COMPONENT_ID,
                "candidate_entity_bindings": [
                    {
                        "target_namespace": "CANDIDATE",
                        "candidate_id": "candidate-001",
                        "entity_handle": TARGET_HANDLE,
                        "block_name": "BLOCK276",
                        "legacy_uuid": "uuid-276",
                        "relative_path": "candidate/revision-276.dwg",
                        "captured_at_utc": "2026-08-17T00:00:00Z",
                    }
                ],
            }
        ],
    }


def _repair_plan(verdict: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "repair-plan-1.0",
        "repair_id": "repair-276",
        "source_review_id": verdict["verdict_id"],
        "run_id": RUN_ID,
        "target_drawing_sha256": SHA_ARTIFACT,
        "operations": [
            {
                "operation": "ADJUST_SPLINE_CONTROL_REGION",
                "target": {
                    "stable_entity_id": COMPONENT_ID,
                    "feature": "EDGE",
                },
                "preserve_anchors": ["anchor-276"],
                "constraint_refs": ["constraint-276"],
            }
        ],
        "affected_regions": ["critical-region"],
        "expected_improvements": ["critical-region:PASS"],
        "must_not_worsen": ["protected-geometry"],
        "rollback_candidate_sha256": SHA_ARTIFACT,
    }


def _repair_operation() -> dict[str, object]:
    return {
        "schema_version": REPAIR_OPERATION_SCHEMA_VERSION,
        "operation": "REPAIR_DXF_PRIMITIVE",
        "target": {"target_handle": TARGET_HANDLE, "layer": "R6-TEST"},
        "parameters": {
            "capability": "LINE",
            "geometry": {
                "type": "line",
                "start": [0.0, 0.0],
                "end": [10.0, 0.0],
            },
        },
        "preserve_anchors": ["anchor-276"],
        "constraint_refs": ["constraint-276"],
    }


def _patch_accepted_owners(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        r5,
        "validate_visual_verdict_result",
        lambda payload, **_kwargs: deepcopy(payload),
    )
    monkeypatch.setattr(
        r5,
        "validate_candidate_revision_state",
        lambda payload: deepcopy(payload),
    )
    monkeypatch.setattr(
        r5,
        "validate_visual_contract",
        lambda payload, *, contract, **_kwargs: deepcopy(payload)
        if contract == "repair_plan"
        else (_ for _ in ()).throw(AssertionError("unexpected visual contract")),
    )
    monkeypatch.setattr(
        r5,
        "validate_component_view_registry",
        lambda payload, *, upstream_context: deepcopy(payload),
        raising=False,
    )
    monkeypatch.setattr(
        r5,
        "normalize_repair_operation",
        normalize_repair_operation,
        raising=False,
    )


def _materialize(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> dict[str, object]:
    _patch_accepted_owners(monkeypatch)
    verdict = _verdict()
    inputs: dict[str, object] = {
        "verdict_result": verdict,
        "candidate_state": _candidate_state(),
        "repair_plan": _repair_plan(verdict),
        "repair_operation": _repair_operation(),
        "r3_registry": _registry(),
        "r3_upstream_context": {"accepted": True},
    }
    inputs.update(overrides)
    return r5.materialize_r5_repair_handoff(**inputs)


def test_missing_public_owner_handoff_is_the_causal_red() -> None:
    assert callable(r5.materialize_r5_repair_handoff)


def test_public_handoff_surface_accepts_owner_objects_not_caller_minted_ids() -> None:
    parameters = inspect.signature(r5.materialize_r5_repair_handoff).parameters
    assert list(parameters) == [
        "verdict_result",
        "candidate_state",
        "repair_plan",
        "repair_operation",
        "r3_registry",
        "r3_upstream_context",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in parameters.values()
    )
    assert {
        "work_item_id",
        "failure_id",
        "failure_sha256",
        "repair_plan_sha256",
        "r3_target_handles",
        "protected_target_handles",
    }.isdisjoint(parameters)


def test_handoff_delegates_validation_to_existing_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verdict_validator = Mock(side_effect=lambda payload, **_kwargs: deepcopy(payload))
    candidate_validator = Mock(side_effect=lambda payload: deepcopy(payload))
    plan_validator = Mock(side_effect=lambda payload, *, contract, **_kwargs: deepcopy(payload))
    registry_validator = Mock(
        side_effect=lambda payload, *, upstream_context: deepcopy(payload)
    )
    operation_validator = Mock(side_effect=normalize_repair_operation)
    monkeypatch.setattr(r5, "validate_visual_verdict_result", verdict_validator)
    monkeypatch.setattr(r5, "validate_candidate_revision_state", candidate_validator)
    monkeypatch.setattr(r5, "validate_visual_contract", plan_validator)
    monkeypatch.setattr(
        r5, "validate_component_view_registry", registry_validator, raising=False
    )
    monkeypatch.setattr(
        r5, "normalize_repair_operation", operation_validator, raising=False
    )
    verdict = _verdict()
    r5.materialize_r5_repair_handoff(
        verdict_result=verdict,
        candidate_state=_candidate_state(),
        repair_plan=_repair_plan(verdict),
        repair_operation=_repair_operation(),
        r3_registry=_registry(),
        r3_upstream_context={"accepted": True},
    )
    assert verdict_validator.call_count == 1
    assert candidate_validator.call_count == 1
    assert plan_validator.call_count == 1
    assert plan_validator.call_args.kwargs["contract"] == "repair_plan"
    assert registry_validator.call_count == 1
    assert operation_validator.call_count == 1


def test_exact_fail_materializes_closed_packet_consumable_by_current_r6(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _materialize(monkeypatch)
    assert set(result) == {
        "schema_version",
        "repair_context",
        "r5_failure",
        "handoff_sha256",
    }
    assert result["schema_version"] == "r5-r6-repair-handoff-1.0"
    context = r6._validate_context(result["repair_context"])
    failure = r6._validate_r5_failure(result["r5_failure"], context)
    assert context["run_id"] == RUN_ID
    assert context["candidate_revision_id"] == "candidate-276"
    assert context["candidate_revision_sha256"] == SHA_CANDIDATE
    assert context["candidate_state_sha256"] == SHA_STATE
    assert context["repair_plan_id"] == "repair-276"
    assert context["repair_plan_version"] == "repair-plan-1.0"
    assert context["r3_target_handles"] == [TARGET_HANDLE]
    assert context["protected_target_handles"] == [TARGET_HANDLE]
    assert failure["verdict"] == "FAIL"
    assert failure["repair_plan_id"] == context["repair_plan_id"]
    assert result["handoff_sha256"] == canonical_json_sha256(
        {
            key: value
            for key, value in result.items()
            if key != "handoff_sha256"
        }
    )


def test_failure_identity_is_owner_materialized_not_verdict_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verdict = _verdict()
    result = _materialize(monkeypatch, verdict_result=verdict)
    failure = result["r5_failure"]
    assert failure["failure_id"] == failure["failure_sha256"]
    assert failure["failure_id"] != verdict["verdict_id"]
    assert failure["failure_sha256"] != verdict["verdict_sha256"]
    assert len(failure["failure_sha256"]) == 64


def test_work_item_and_plan_bindings_are_owner_derived_and_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _materialize(monkeypatch)
    second = _materialize(monkeypatch)
    assert second == first
    context = first["repair_context"]
    assert type(context["work_item_id"]) is str and context["work_item_id"]
    assert context["repair_plan_sha256"] == canonical_json_sha256(
        _repair_plan(_verdict())
    )
    normalized = normalize_repair_operation(_repair_operation())
    assert context["repair_operation_contract_version"] == REPAIR_OPERATION_SCHEMA_VERSION
    assert context["repair_operation_contract_fingerprint"] == canonical_json_sha256(
        normalized.as_executor_payload()
    )


@pytest.mark.parametrize(
    "change, expected",
    [
        ("pass", "FAIL"),
        ("foreign_candidate", "candidate|binding|current"),
        ("foreign_plan_run", "run|plan|binding"),
        ("foreign_plan_review", "review|verdict|plan|binding"),
        ("foreign_plan_artifact", "artifact|drawing|candidate|plan|binding"),
        ("foreign_plan_target", "target|plan|R3|registry|binding"),
        ("foreign_target", "target|R3|registry|binding"),
        ("foreign_anchor", "anchor|plan|binding"),
    ],
)
def test_stale_foreign_or_unbound_inputs_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    expected: str,
) -> None:
    verdict = _verdict()
    state = _candidate_state()
    plan = _repair_plan(verdict)
    operation = _repair_operation()
    if change == "pass":
        verdict["verdict"] = "PASS"
    elif change == "foreign_candidate":
        verdict["candidate_revision_sha256"] = "9" * 64
    elif change == "foreign_plan_run":
        plan["run_id"] = "foreign-run"
    elif change == "foreign_plan_review":
        plan["source_review_id"] = "foreign-review"
    elif change == "foreign_plan_artifact":
        plan["target_drawing_sha256"] = "9" * 64
    elif change == "foreign_plan_target":
        plan["operations"][0]["target"]["stable_entity_id"] = "foreign-component"
    elif change == "foreign_target":
        operation["target"]["target_handle"] = "FOREIGN"
    else:
        operation["preserve_anchors"] = ["foreign-anchor"]
    with pytest.raises(Exception, match=expected):
        _materialize(
            monkeypatch,
            verdict_result=verdict,
            candidate_state=state,
            repair_plan=plan,
            repair_operation=operation,
        )


def test_handoff_mints_no_r6_execution_or_downstream_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _materialize(monkeypatch)
    forbidden = {
        "authorization",
        "authorization_id",
        "workspace",
        "workspace_lease",
        "executor",
        "mutation_outcome",
        "approved",
        "accepted",
        "published",
        "r5_pass",
        "publication",
        "current_candidate_revision_sha256",
    }
    assert forbidden.isdisjoint(result)
    assert forbidden.isdisjoint(result["repair_context"])
    assert forbidden.isdisjoint(result["r5_failure"])
