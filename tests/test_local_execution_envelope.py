from __future__ import annotations

import importlib
from copy import deepcopy
from types import ModuleType

import pytest

from cad_agent.control_snapshot import build_control_snapshot
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.mission_contract import compile_local_mission
from cad_agent.work_routing import WORK_ROUTING_SCHEMA_VERSION


MAIN_SHA = "1263db2f54f505209ba6837b86181af8646b5a58"
MAIN_TREE_SHA = "2e9e8d504908168a0ea5d17233506709f478c29c"
AD_HEAD_SHA = "729f005b5c1cad6f88245bb134b524be644c4855"


def _adapter() -> ModuleType:
    try:
        return importlib.import_module("cad_agent.local_execution_envelope")
    except ModuleNotFoundError as exc:
        pytest.fail(f"local_execution_envelope module missing: {exc}")


def _snapshot(*, control_seq: int = 292, live_allowed: bool = False) -> dict[str, object]:
    observation = {
        "standing_model_comment_id": 5396800691,
        "persistence_comment_id": 5419064061,
        "control_seq": control_seq,
        "authority_comment_id": 5436932564,
        "consumed_terminal_id": 5436656589,
        "terminal_classification": "READY",
        "next_owner": "SOL",
        "current_main_sha": MAIN_SHA,
        "current_main_tree_sha": MAIN_TREE_SHA,
        "active_issue": 288,
        "active_pr": 286,
        "active_pr_base_sha": MAIN_SHA,
        "active_pr_head_sha": AD_HEAD_SHA,
        "active_pr_state": "OPEN_DRAFT",
        "repo_write_allowed": False,
        "live_allowed": live_allowed,
        "locks": [] if live_allowed else ["NO_LIVE"],
        "reused_pass_evidence": ["PR286:A-D"],
        "first_unsatisfied_gate": "E1",
        "source_refs": ["issue:131#5436932564"],
    }
    return build_control_snapshot(observation, generated_at="2026-08-27T10:20:00Z")


def _routing() -> dict[str, object]:
    return {
        "schema_version": WORK_ROUTING_SCHEMA_VERSION,
        "classification": "LOCAL_REPO_REQUIRED",
        "reason": "self-hosted Windows checkout verification",
        "required_evidence_surface": "repository checkout + hosted evidence",
    }


def _request(*, live_budget: int = 0) -> dict[str, object]:
    return {
        "goal": "run the fixed authoritative offline verifier",
        "outcome_predicate": "bootstrap and verify complete with exact evidence",
        "repo_mutation": False,
        "write_set": [],
        "forbidden_paths": ["cad_agent/file_ipc.py"],
        "accepted_evidence": [],
        "pre_execution_closure": "exact branch, head, mission, and control identities match",
        "causal_family": "offline-verify",
        "causal_budget": 1,
        "allowed_temp_repairs": [],
        "live_budget": live_budget,
        "expensive_budget": 1,
        "acceptance_oracle": "authoritative offline verifier passes",
        "hard_handoff_conditions": ["scope expansion"],
        "cleanup_requirements": ["repository state remains attributable"],
        "terminal_fields": ["result", "mission_sha256", "local_head_sha"],
        "human_relay_required": False,
        "merge_authority": False,
        "publication_authority": False,
    }


def _mission(*, snapshot: dict[str, object], live_budget: int = 0) -> dict[str, object]:
    return compile_local_mission(snapshot, _routing(), _request(live_budget=live_budget))


def _envelope(*, snapshot: dict[str, object], mission: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "cad-local-execution-envelope-1.0",
        "capability": "OFFLINE_VERIFY",
        "expected_mission_sha256": canonical_json_sha256(mission),
        "mission": mission,
        "control_snapshot": snapshot,
    }


def test_rejects_unknown_capability() -> None:
    adapter = _adapter()
    snapshot = _snapshot()
    mission = _mission(snapshot=snapshot)
    envelope = _envelope(snapshot=snapshot, mission=mission)
    envelope["capability"] = "AUTOCAD_LIVE_PROBE"

    with pytest.raises(adapter.LocalExecutionEnvelopeError, match="capability"):
        adapter.validate_local_execution_envelope(envelope)


def test_rejects_mission_sha_mismatch() -> None:
    adapter = _adapter()
    snapshot = _snapshot()
    mission = _mission(snapshot=snapshot)
    envelope = _envelope(snapshot=snapshot, mission=mission)
    envelope["expected_mission_sha256"] = "0" * 64

    with pytest.raises(adapter.LocalExecutionEnvelopeError, match="expected_mission_sha256"):
        adapter.validate_local_execution_envelope(envelope)


def test_rejects_mission_control_snapshot_mismatch() -> None:
    adapter = _adapter()
    snapshot = _snapshot(control_seq=292)
    mission = _mission(snapshot=snapshot)
    other_snapshot = _snapshot(control_seq=293)
    envelope = _envelope(snapshot=other_snapshot, mission=mission)

    with pytest.raises(adapter.LocalExecutionEnvelopeError, match="control snapshot"):
        adapter.validate_local_execution_envelope(envelope)


def test_rejects_offline_verify_with_nonzero_live_budget() -> None:
    adapter = _adapter()
    snapshot = _snapshot(live_allowed=True)
    mission = _mission(snapshot=snapshot, live_budget=1)
    envelope = _envelope(snapshot=snapshot, mission=mission)

    with pytest.raises(adapter.LocalExecutionEnvelopeError, match="live_budget"):
        adapter.validate_local_execution_envelope(envelope)


def test_rejects_unexpected_envelope_field() -> None:
    adapter = _adapter()
    snapshot = _snapshot()
    mission = _mission(snapshot=snapshot)
    envelope = _envelope(snapshot=snapshot, mission=mission)
    envelope["command"] = "Write-Host bypass"

    with pytest.raises(adapter.LocalExecutionEnvelopeError, match="unexpected fields"):
        adapter.validate_local_execution_envelope(envelope)


def test_accepts_canonical_offline_verify_envelope() -> None:
    adapter = _adapter()
    snapshot = _snapshot()
    mission = _mission(snapshot=snapshot)
    envelope = _envelope(snapshot=snapshot, mission=mission)

    validated = adapter.validate_local_execution_envelope(envelope)

    assert validated["schema_version"] == "cad-local-execution-envelope-1.0"
    assert validated["capability"] == "OFFLINE_VERIFY"
    assert validated["mission_sha256"] == canonical_json_sha256(mission)
    assert validated["control_state_sha256"] == snapshot["state_sha256"]
    assert validated["mission"] == mission
    assert validated["control_snapshot"] == snapshot


def test_terminal_is_evidence_only() -> None:
    adapter = _adapter()
    terminal = adapter.build_local_mission_terminal(
        mission_sha256="a" * 64,
        control_state_sha256="b" * 64,
        capability="OFFLINE_VERIFY",
        local_branch="governance/local-mission-adapter",
        local_head_sha="c" * 40,
        result="PASS",
        bootstrap_exit_code=0,
        verify_exit_code=0,
    )

    assert set(terminal) == {
        "schema_version",
        "mission_sha256",
        "control_state_sha256",
        "capability",
        "local_branch",
        "local_head_sha",
        "result",
        "bootstrap_exit_code",
        "verify_exit_code",
        "live_result",
        "merge_authority",
        "publication_authority",
    }
    assert "control_seq" not in terminal
    assert terminal["live_result"] == "NOT_RUN"
    assert terminal["merge_authority"] is False
    assert terminal["publication_authority"] is False


def test_terminal_rejects_authority_shaped_inputs_by_closed_signature() -> None:
    adapter = _adapter()
    kwargs = {
        "mission_sha256": "a" * 64,
        "control_state_sha256": "b" * 64,
        "capability": "OFFLINE_VERIFY",
        "local_branch": "governance/local-mission-adapter",
        "local_head_sha": "c" * 40,
        "result": "PASS",
        "bootstrap_exit_code": 0,
        "verify_exit_code": 0,
        "control_seq": 293,
    }

    with pytest.raises(TypeError):
        adapter.build_local_mission_terminal(**deepcopy(kwargs))
