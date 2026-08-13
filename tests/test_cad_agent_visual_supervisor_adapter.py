from __future__ import annotations

import copy
from itertools import count
from unittest.mock import Mock, patch

import pytest

from agent_lib.codex_worker import (
    CodexWorkerEvent,
    CodexWorkerResult,
    _issue_task6_result,
)
from agent_lib.codex_worker_process import WorkerCleanupResult


SHA_CANDIDATE = "a" * 64
SHA_STATE = "b" * 64
SHA_DARA = "c" * 64
SHA_DRAWING = "d" * 64
SHA_REGISTRY = "e" * 64
SHA_MANIFEST = "f" * 64
SHA_MUTATION = "1" * 64
SHA_CHANGED = "2" * 64
_RUN_IDS = count(1)


class _HostileStr(str):
    def __new__(cls, value: str) -> "_HostileStr":
        return str.__new__(cls, value)

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return hash("PASS")

    def __str__(self) -> str:
        return "FORGED"


def _scope(*, run_id: str = "run-1") -> dict[str, object]:
    return {
        "schema_version": "visual-review-scope-1.0",
        "scope_id": "scope-1",
        "run_id": run_id,
        "registry_snapshot_sha256": SHA_REGISTRY,
        "candidate_revision_sha256": SHA_CANDIDATE,
        "candidate_state_sha256": SHA_STATE,
        "regions": [
            {
                "region_id": "critical-region",
                "view_id": "view-1",
                "sheet_id": "sheet-1",
                "layout_id": "layout-1",
                "criticality": "CRITICAL",
            },
            {
                "region_id": "normal-region",
                "view_id": "view-1",
                "sheet_id": "sheet-1",
                "layout_id": "layout-1",
                "criticality": "NORMAL",
            },
        ],
    }


def _task6_result(*, status: str = "COMPLETED") -> CodexWorkerResult:
    return CodexWorkerResult(
        operation="turn",
        status=status,
        success=status == "COMPLETED",
        thread_id="thread-1",
        turn_id="turn-1",
        events=(CodexWorkerEvent("turn.completed"),),
        candidate_output=None,
        candidate_trusted=False,
        failure_code=None if status == "COMPLETED" else "WORKER_TIMEOUT",
        cleanup_result=None,
        promotion_safe=False,
    )


def _cleanup() -> WorkerCleanupResult:
    return WorkerCleanupResult(
        status="CLEANUP_SUCCEEDED",
        success=True,
        promotion_safe=True,
        survivor_pids=(),
        survivor_count=0,
        error_code=None,
    )


def _provider_result(scope: dict[str, object], task6: CodexWorkerResult) -> dict[str, object]:
    regions = copy.deepcopy(scope["regions"])
    for region in regions:
        region.update({"status": "PASS"})
    return {
        "task6_result": task6,
        "candidate_revision_sha256": SHA_CANDIDATE,
        "provider_verdict": "PASS",
        "regions": regions,
    }


def _owner_state(scope: dict[str, object], task6: CodexWorkerResult) -> dict[str, object]:
    return {
        "visual_review_scope": copy.deepcopy(scope),
        "candidate_revision_state": {"current_candidate_revision_sha256": SHA_CANDIDATE},
        "drawing_reference": {"reference_sha256": SHA_DARA},
        "drawing_observation": {"reference_sha256": SHA_DARA},
        "drawing_artifact_bytes": b"current drawing",
        "visual_evidence": {"payload": "owner-validated"},
        "visual_run_manifest": {"latest_mutation_sha256": SHA_MUTATION},
        "manifest_bytes_sha256": SHA_MANIFEST,
        "drawing_sha256_before_dispatch": SHA_DRAWING,
        "task6_result": task6,
        "cleanup_result": _cleanup(),
    }


def _valid_inputs() -> dict[str, object]:
    scope = _scope(run_id=f"run-{next(_RUN_IDS)}")
    task6 = _task6_result()
    _issue_task6_result(task6, run_id=scope["run_id"], operation=task6.operation)
    return {
        "server_scope": scope,
        "provider_result": _provider_result(scope, task6),
        "authoritative_state": _owner_state(scope, task6),
        "post_provider_state": _owner_state(scope, task6),
    }


def _owner_patches() -> tuple[Mock, Mock, Mock, Mock]:
    def normalize_scope(payload: object, *, contract: str, server_scope: object) -> dict[str, object]:
        normalized = copy.deepcopy(payload)
        normalized["regions"] = sorted(
            normalized["regions"], key=lambda region: str(region["region_id"])
        )
        return normalized

    scope_validator = Mock(side_effect=normalize_scope)
    candidate_validator = Mock(
        side_effect=lambda payload: {
            "current_candidate_revision_sha256": payload["current_candidate_revision_sha256"],
            "state_sha256": SHA_STATE,
        }
    )
    dara_validator = Mock()
    evidence_validator = Mock(side_effect=lambda evidence, *_args: copy.deepcopy(evidence))
    return scope_validator, candidate_validator, dara_validator, evidence_validator


def _finalize(inputs: dict[str, object]) -> object:
    import cad_agent.visual_supervisor_adapter as module

    scope_validator, candidate_validator, dara_validator, evidence_validator = _owner_patches()
    with (
        patch.object(module, "validate_visual_contract", scope_validator),
        patch.object(module, "validate_candidate_revision_state", candidate_validator),
        patch.object(module, "require_current_drawing_artifact_reference", dara_validator),
        patch.object(module, "validate_visual_evidence_freshness", evidence_validator),
    ):
        return module.finalize_visual_verdict(**inputs)


def test_valid_owner_context_finalizes_deterministically_without_provider_hash_authority() -> None:
    result = _finalize(_valid_inputs())
    assert result["verdict"] == "PASS"
    assert result["task6_thread_id"] == "thread-1"
    assert all("evidence_sha256" not in region for region in result["regions"])


def test_provider_evidence_hash_is_not_an_adapter_authority_field() -> None:
    inputs = _valid_inputs()
    inputs["provider_result"]["regions"][0]["evidence_sha256"] = SHA_MANIFEST
    with pytest.raises(Exception, match="unknown|field|evidence"):
        _finalize(inputs)


def test_composition_calls_existing_scope_revision_dara_and_visual_evidence_owners() -> None:
    import cad_agent.visual_supervisor_adapter as module

    inputs = _valid_inputs()
    scope_validator, candidate_validator, dara_validator, evidence_validator = _owner_patches()
    with (
        patch.object(module, "validate_visual_contract", scope_validator),
        patch.object(module, "validate_candidate_revision_state", candidate_validator),
        patch.object(module, "require_current_drawing_artifact_reference", dara_validator),
        patch.object(module, "validate_visual_evidence_freshness", evidence_validator),
    ):
        module.finalize_visual_verdict(**inputs)
    assert scope_validator.call_count >= 3
    assert candidate_validator.call_count == 2
    assert dara_validator.call_count == 2
    assert evidence_validator.call_count == 2


def test_candidate_selection_change_after_provider_return_fails_closed() -> None:
    inputs = _valid_inputs()
    inputs["post_provider_state"]["candidate_revision_state"]["current_candidate_revision_sha256"] = SHA_CHANGED
    with pytest.raises(Exception, match="candidate|current"):
        _finalize(inputs)


def test_scope_candidate_must_bind_to_current_r4_candidate() -> None:
    inputs = _valid_inputs()
    for state in (inputs["authoritative_state"], inputs["post_provider_state"]):
        state["visual_review_scope"]["candidate_revision_sha256"] = SHA_CHANGED
    inputs["server_scope"]["candidate_revision_sha256"] = SHA_CHANGED
    with pytest.raises(Exception, match="scope.*R4|R4.*scope|candidate"):
        _finalize(inputs)


def test_scope_state_must_bind_to_current_r4_state() -> None:
    inputs = _valid_inputs()
    for state in (inputs["authoritative_state"], inputs["post_provider_state"]):
        state["visual_review_scope"]["candidate_state_sha256"] = SHA_CHANGED
    inputs["server_scope"]["candidate_state_sha256"] = SHA_CHANGED
    with pytest.raises(Exception, match="scope.*R4|R4.*scope|state"):
        _finalize(inputs)


def test_dara_bytes_change_after_provider_return_fails_closed() -> None:
    inputs = _valid_inputs()
    inputs["post_provider_state"]["drawing_artifact_bytes"] = b"changed drawing"
    with pytest.raises(Exception, match="DARA|drawing|current"):
        _finalize(inputs)


def test_visual_evidence_stale_after_provider_return_fails_closed() -> None:
    inputs = _valid_inputs()
    inputs["post_provider_state"]["visual_run_manifest"] = {"latest_mutation_sha256": SHA_CHANGED}
    with pytest.raises(Exception, match="fresh|stale|mutation|evidence|manifest"):
        _finalize(inputs)


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "foreign"])
def test_provider_regions_must_equal_server_owned_scope(change: str) -> None:
    inputs = _valid_inputs()
    regions = inputs["provider_result"]["regions"]
    if change == "missing":
        regions.pop()
    elif change == "extra":
        regions.append({**regions[0], "region_id": "extra-region"})
    elif change == "duplicate":
        regions.append(copy.deepcopy(regions[0]))
    else:
        regions[0]["region_id"] = "foreign-region"
    with pytest.raises(Exception, match="scope|region|foreign|duplicate"):
        _finalize(inputs)


@pytest.mark.parametrize("change", ["criticality_mask", "critical_scope_shrink"])
def test_provider_cannot_mask_or_shrink_critical_scope(change: str) -> None:
    inputs = _valid_inputs()
    if change == "criticality_mask":
        inputs["provider_result"]["regions"][0]["criticality"] = "NORMAL"
    else:
        inputs["server_scope"]["regions"].pop(0)
        inputs["authoritative_state"]["visual_review_scope"]["regions"].pop(0)
        inputs["post_provider_state"]["visual_review_scope"]["regions"].pop(0)
    with pytest.raises(Exception, match="scope|region|critical"):
        _finalize(inputs)


@pytest.mark.parametrize("malformed", [{"unexpected": True}, "not-an-object", None])
def test_malformed_or_unknown_provider_observation_fails_closed(malformed: object) -> None:
    inputs = _valid_inputs()
    inputs["provider_result"]["regions"] = [malformed]
    with pytest.raises(Exception, match="object|field|region|mapping"):
        _finalize(inputs)


def test_task6_result_must_be_the_accepted_public_object() -> None:
    inputs = _valid_inputs()
    inputs["provider_result"]["task6_result"] = {
        "status": "COMPLETED",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
    }
    with pytest.raises(Exception, match="TASK6_PUBLIC_SEAM|CodexWorkerResult|Task6"):
        _finalize(inputs)


def test_task6_supersession_or_replay_cannot_finalize_again() -> None:
    inputs = _valid_inputs()
    _finalize(inputs)
    with pytest.raises(Exception, match="consume|replay|already|Task6"):
        _finalize(inputs)


def test_task6_tuple_mismatch_does_not_burn_result() -> None:
    inputs = _valid_inputs()
    issued_run = inputs["server_scope"]["run_id"]
    for state in (inputs["authoritative_state"], inputs["post_provider_state"]):
        state["visual_review_scope"]["run_id"] = "wrong-run"
    inputs["server_scope"]["run_id"] = "wrong-run"
    with pytest.raises(Exception, match="consume|Task6|provenance|tuple"):
        _finalize(inputs)
    for state in (inputs["authoritative_state"], inputs["post_provider_state"]):
        state["visual_review_scope"]["run_id"] = issued_run
    inputs["server_scope"]["run_id"] = issued_run
    assert _finalize(inputs)["verdict"] == "PASS"


@pytest.mark.parametrize("field", ["region_id", "status", "criticality"])
def test_hostile_provider_region_strings_fail_closed_without_burn(field: str) -> None:
    inputs = _valid_inputs()
    original = inputs["provider_result"]["regions"][0][field]
    inputs["provider_result"]["regions"][0][field] = _HostileStr(str(original))
    with pytest.raises(Exception, match="string|invalid|provider|region"):
        _finalize(inputs)
    inputs["provider_result"]["regions"][0][field] = original
    assert _finalize(inputs)["verdict"] == "PASS"


def test_hostile_provider_verdict_fails_closed_without_burn() -> None:
    inputs = _valid_inputs()
    inputs["provider_result"]["provider_verdict"] = _HostileStr("PASS")
    with pytest.raises(Exception, match="string|invalid|provider|verdict"):
        _finalize(inputs)
    inputs["provider_result"]["provider_verdict"] = "PASS"
    assert _finalize(inputs)["verdict"] == "PASS"


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "CLOSED"])
def test_task6_non_success_terminal_result_cannot_be_visual_verdict(status: str) -> None:
    inputs = _valid_inputs()
    inputs["provider_result"]["task6_result"] = _task6_result(status=status)
    with pytest.raises(Exception, match="terminal|timeout|cancel|late|Task6"):
        _finalize(inputs)


def test_provider_region_order_does_not_change_final_result() -> None:
    first = _finalize(_valid_inputs())
    second_inputs = _valid_inputs()
    second_inputs["provider_result"]["regions"] = list(
        reversed(second_inputs["provider_result"]["regions"])
    )
    second = _finalize(second_inputs)
    assert second == first


def test_critical_region_failure_forces_final_fail() -> None:
    inputs = _valid_inputs()
    inputs["provider_result"]["regions"][0]["status"] = "FAIL"
    result = _finalize(inputs)
    assert result["verdict"] == "FAIL"


@pytest.mark.parametrize("status", ["SKIP", "NOT_RUN"])
def test_incomplete_or_skipped_evidence_cannot_be_promoted_to_pass(status: str) -> None:
    inputs = _valid_inputs()
    inputs["provider_result"]["regions"][0]["status"] = status
    result = _finalize(inputs)
    assert result["verdict"] != "PASS"


def test_pre_repair_r5_verdict_is_stale_after_r6_mutation() -> None:
    inputs = _valid_inputs()
    inputs["authoritative_state"]["pre_repair_r5_verdict"] = {
        "verdict": "PASS",
        "latest_mutation_sha256": SHA_CHANGED,
    }
    with pytest.raises(Exception, match="stale|repair|R5|mutation"):
        _finalize(inputs)


def test_old_caller_mintable_mapping_is_rejected_with_explicit_seam_blocker() -> None:
    import cad_agent.visual_supervisor_adapter as module

    with pytest.raises(ValueError, match="R5_B3_TASK6_PUBLIC_SEAM_MISSING"):
        module.finalize_visual_verdict(
            provider_result={"terminal_status": "COMPLETED"},
            authoritative_state={"task6_attempt_id": "attempt-1"},
            post_provider_state={"task6_attempt_id": "attempt-1"},
            server_scope=_scope(),
        )


def test_two_region_scope_requires_one_owner_fresh_visual_evidence_package_per_region() -> None:
    inputs = _valid_inputs()
    assert len(inputs["server_scope"]["regions"]) == 2
    # Current B3 accepts one singular owner-validated package for a two-region
    # scope. B4 must refuse before Task6 consumption because one exact scoped
    # region has no independent VS-T3 freshness package.
    with pytest.raises(Exception, match="R5_EVIDENCE_SET_INVALID|evidence.*region|region.*evidence"):
        _finalize(inputs)
