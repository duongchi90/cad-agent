from __future__ import annotations

import copy
import importlib

import pytest


SHA_CANDIDATE = "a" * 64
SHA_STATE = "b" * 64
SHA_DARA = "c" * 64
SHA_DRAWING = "d" * 64
SHA_REGISTRY = "e" * 64
SHA_MANIFEST = "f" * 64
SHA_MUTATION = "1" * 64
SHA_CHANGED = "2" * 64


def _scope() -> dict[str, object]:
    return {
        "schema_version": "visual-review-scope-1.0",
        "scope_id": "scope-1",
        "run_id": "run-1",
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


def _provider_result(scope: dict[str, object]) -> dict[str, object]:
    regions = copy.deepcopy(scope["regions"])
    for region in regions:
        region.update({"status": "PASS", "evidence_sha256": SHA_MANIFEST})
    return {
        "attempt_id": "attempt-1",
        "terminal_status": "COMPLETED",
        "candidate_revision_sha256": SHA_CANDIDATE,
        "provider_verdict": "PASS",
        "regions": regions,
    }


def _authoritative_state(scope: dict[str, object]) -> dict[str, object]:
    return {
        "run_id": "run-1",
        "candidate_revision_sha256": SHA_CANDIDATE,
        "candidate_state_sha256": SHA_STATE,
        "current_candidate_revision_sha256": SHA_CANDIDATE,
        "dara_reference_sha256": SHA_DARA,
        "drawing_sha256": SHA_DRAWING,
        "registry_snapshot_sha256": SHA_REGISTRY,
        "visual_run_manifest_sha256": SHA_MANIFEST,
        "latest_mutation_sha256": SHA_MUTATION,
        "task6_attempt_id": "attempt-1",
        "task6_terminal_status": "COMPLETED",
        "server_scope": scope,
        "consumed_attempt_ids": [],
    }


def _post_provider_state(scope: dict[str, object]) -> dict[str, object]:
    return {
        "candidate_revision_sha256": SHA_CANDIDATE,
        "candidate_state_sha256": SHA_STATE,
        "dara_reference_sha256": SHA_DARA,
        "drawing_sha256": SHA_DRAWING,
        "registry_snapshot_sha256": SHA_REGISTRY,
        "visual_run_manifest_sha256": SHA_MANIFEST,
        "latest_mutation_sha256": SHA_MUTATION,
        "server_scope": copy.deepcopy(scope),
    }


def _valid_inputs() -> dict[str, object]:
    scope = _scope()
    return {
        "provider_result": _provider_result(scope),
        "authoritative_state": _authoritative_state(scope),
        "post_provider_state": _post_provider_state(scope),
    }


def _finalize(inputs: dict[str, object]) -> object:
    """Call the future pure finalizer; missing capability is the intentional RED."""
    try:
        module = importlib.import_module("cad_agent.visual_supervisor_adapter")
        finalizer = getattr(module, "finalize_visual_verdict")
    except (ModuleNotFoundError, AttributeError) as exc:
        pytest.fail(f"R5-B3 RED: finalizer capability is not available: {exc}")
    return finalizer(**inputs)


def test_valid_provider_result_finalizes_deterministically() -> None:
    result = _finalize(_valid_inputs())
    assert result["verdict"] == "PASS"


def test_candidate_selection_change_after_provider_return_fails_closed() -> None:
    inputs = _valid_inputs()
    inputs["authoritative_state"]["current_candidate_revision_sha256"] = SHA_CHANGED
    with pytest.raises(Exception, match="candidate|current"):
        _finalize(inputs)


def test_candidate_state_or_latest_mutation_mismatch_fails_closed() -> None:
    inputs = _valid_inputs()
    inputs["post_provider_state"]["candidate_state_sha256"] = SHA_CHANGED
    with pytest.raises(Exception, match="candidate|state|mutation"):
        _finalize(inputs)


def test_dara_bytes_change_after_provider_return_fails_closed() -> None:
    inputs = _valid_inputs()
    inputs["post_provider_state"]["drawing_sha256"] = SHA_CHANGED
    with pytest.raises(Exception, match="DARA|drawing|current"):
        _finalize(inputs)


def test_visual_evidence_stale_after_provider_return_fails_closed() -> None:
    inputs = _valid_inputs()
    inputs["post_provider_state"]["latest_mutation_sha256"] = SHA_CHANGED
    with pytest.raises(Exception, match="fresh|stale|mutation|evidence"):
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
        inputs["authoritative_state"]["server_scope"]["regions"].pop(0)
    with pytest.raises(Exception, match="critical|scope|region"):
        _finalize(inputs)


@pytest.mark.parametrize(
    "malformed",
    [
        {"unexpected": True},
        "not-an-object",
        None,
    ],
)
def test_malformed_or_unknown_provider_observation_fails_closed(malformed: object) -> None:
    inputs = _valid_inputs()
    inputs["provider_result"]["regions"] = [malformed]
    with pytest.raises(Exception, match="malformed|unknown|object|field|region"):
        _finalize(inputs)


@pytest.mark.parametrize("terminal_status", ["TIMED_OUT", "CANCELLED", "LATE_RESULT"])
def test_task6_non_success_terminal_result_cannot_be_visual_verdict(
    terminal_status: str,
) -> None:
    inputs = _valid_inputs()
    inputs["provider_result"]["terminal_status"] = terminal_status
    with pytest.raises(Exception, match="terminal|timeout|cancel|late|attempt"):
        _finalize(inputs)


def test_replayed_provider_attempt_cannot_finalize_again() -> None:
    inputs = _valid_inputs()
    inputs["authoritative_state"]["consumed_attempt_ids"] = ["attempt-1"]
    with pytest.raises(Exception, match="replay|duplicate|attempt|consum"):
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
    try:
        result = _finalize(inputs)
    except Exception:
        return
    assert result["verdict"] != "PASS"


def test_pre_repair_r5_verdict_is_stale_after_r6_mutation() -> None:
    inputs = _valid_inputs()
    inputs["authoritative_state"]["pre_repair_r5_verdict"] = {
        "verdict": "PASS",
        "candidate_revision_sha256": SHA_CANDIDATE,
        "latest_mutation_sha256": SHA_MUTATION,
    }
    inputs["authoritative_state"]["r6_mutation_sha256"] = SHA_CHANGED
    inputs["authoritative_state"]["r6_review_verdict"] = "PASS"
    inputs["post_provider_state"]["latest_mutation_sha256"] = SHA_CHANGED
    with pytest.raises(Exception, match="stale|repair|R5|mutation|review"):
        _finalize(inputs)
