from __future__ import annotations

import copy

import pytest

from cad_agent.control_snapshot import (
    ControlSnapshotError,
    build_control_snapshot,
    validate_control_snapshot,
)


SHA_A = "1" * 40
SHA_B = "2" * 40


def _observation() -> dict[str, object]:
    return {
        "standing_model_comment_id": 5396800691,
        "persistence_comment_id": 5419064061,
        "control_seq": 291,
        "authority_comment_id": 5436556581,
        "consumed_terminal_id": 5436436020,
        "terminal_classification": "OWNER_FIX_RED_READY",
        "next_owner": "SOL",
        "current_main_sha": SHA_A,
        "current_main_tree_sha": SHA_B,
        "active_issue": 284,
        "active_pr": 285,
        "active_pr_base_sha": SHA_A,
        "active_pr_head_sha": "3" * 40,
        "active_pr_state": "OPEN_DRAFT",
        "repo_write_allowed": False,
        "live_allowed": False,
        "locks": ["NO_LIVE", "NO_MAIN_MOVEMENT"],
        "reused_pass_evidence": ["SEQ288:S0", "SEQ289:PHASE_A"],
        "first_unsatisfied_gate": "WINDOWS_TRIGGER_EXECUTION_PROOF",
        "source_refs": [
            "issue:131#comment-5436656589",
            "issue:284",
            "pr:285",
            f"main:{SHA_A}",
        ],
    }


def test_generated_at_does_not_change_state_identity() -> None:
    first = build_control_snapshot(
        _observation(), generated_at="2026-08-27T10:00:00Z"
    )
    second = build_control_snapshot(
        _observation(), generated_at="2026-08-27T10:01:00Z"
    )

    assert first["state_sha256"] == second["state_sha256"]
    assert first["generated_at"] != second["generated_at"]
    assert validate_control_snapshot(first) == first
    assert validate_control_snapshot(second) == second


def test_material_change_changes_state_identity() -> None:
    original = build_control_snapshot(
        _observation(), generated_at="2026-08-27T10:00:00Z"
    )
    changed_observation = _observation()
    changed_observation["control_seq"] = 292
    changed = build_control_snapshot(
        changed_observation, generated_at="2026-08-27T10:00:00Z"
    )

    assert original["state_sha256"] != changed["state_sha256"]


def test_snapshot_requires_exact_source_references() -> None:
    observation = _observation()
    observation["source_refs"] = []

    with pytest.raises(ControlSnapshotError, match="source_refs"):
        build_control_snapshot(observation, generated_at="2026-08-27T10:00:00Z")


def test_snapshot_rejects_missing_authority_comment() -> None:
    observation = _observation()
    observation["authority_comment_id"] = None

    with pytest.raises(ControlSnapshotError, match="authority_comment_id"):
        build_control_snapshot(observation, generated_at="2026-08-27T10:00:00Z")


def test_snapshot_rejects_noncanonical_git_sha() -> None:
    observation = _observation()
    observation["current_main_sha"] = "A" * 40

    with pytest.raises(ControlSnapshotError, match="current_main_sha"):
        build_control_snapshot(observation, generated_at="2026-08-27T10:00:00Z")


def test_snapshot_rejects_duplicate_or_unsorted_sets() -> None:
    observation = _observation()
    observation["locks"] = ["NO_MAIN_MOVEMENT", "NO_LIVE", "NO_LIVE"]

    with pytest.raises(ControlSnapshotError, match="locks"):
        build_control_snapshot(observation, generated_at="2026-08-27T10:00:00Z")


def test_snapshot_rejects_extra_observation_fields() -> None:
    observation = _observation()
    observation["invented_authority"] = True

    with pytest.raises(ControlSnapshotError, match="unexpected"):
        build_control_snapshot(observation, generated_at="2026-08-27T10:00:00Z")


def test_snapshot_validation_detects_resealed_state_tampering() -> None:
    snapshot = build_control_snapshot(
        _observation(), generated_at="2026-08-27T10:00:00Z"
    )
    tampered = copy.deepcopy(snapshot)
    tampered["next_owner"] = "LUNA"

    with pytest.raises(ControlSnapshotError, match="state_sha256"):
        validate_control_snapshot(tampered)
