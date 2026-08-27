from __future__ import annotations

import copy

import pytest

from cad_agent.control_snapshot import build_control_snapshot
from cad_agent.mission_contract import (
    MissionContractError,
    compile_local_mission,
    validate_local_mission,
)
from cad_agent.work_routing import classify_work


MAIN = "1" * 40
TREE = "2" * 40
HEAD = "3" * 40


def _snapshot(*, repo_write_allowed: bool = True, live_allowed: bool = True) -> dict[str, object]:
    return build_control_snapshot(
        {
            "standing_model_comment_id": 5396800691,
            "persistence_comment_id": 5419064061,
            "control_seq": 291,
            "authority_comment_id": 5436556581,
            "consumed_terminal_id": 5436436020,
            "terminal_classification": "OWNER_FIX_RED_READY",
            "next_owner": "SOL",
            "current_main_sha": MAIN,
            "current_main_tree_sha": TREE,
            "active_issue": 284,
            "active_pr": 285,
            "active_pr_base_sha": MAIN,
            "active_pr_head_sha": HEAD,
            "active_pr_state": "OPEN_DRAFT",
            "repo_write_allowed": repo_write_allowed,
            "live_allowed": live_allowed,
            "locks": [],
            "reused_pass_evidence": ["SEQ288:S0"],
            "first_unsatisfied_gate": "WINDOWS_TRIGGER_EXECUTION_PROOF",
            "source_refs": ["issue:131#comment-5436656589", "pr:285"],
        },
        generated_at="2026-08-27T10:00:00Z",
    )


def _routing() -> dict[str, str]:
    return classify_work(
        {
            "requires_unpushed_local_state": False,
            "requires_windows_toolchain": True,
            "requires_autocad": False,
            "requires_com_rot_ui": False,
            "requires_netload": False,
            "requires_live_file_ipc": False,
            "requires_owner_decision": False,
            "requires_private_secret": False,
            "requires_irreversible_approval": False,
            "web_capable_analysis": False,
            "preferred_executor": "LUNA",
            "reason": "Windows-only trigger evidence required",
        }
    )


def _request() -> dict[str, object]:
    return {
        "goal": "prove exact Windows trigger execution boundary",
        "outcome_predicate": "focused owner contract GREEN with exact receiver proof",
        "repo_mutation": True,
        "write_set": [
            "mcp_integration_lib/mcp_client.py",
            "mcp_integration_lib/tests/test_file_ipc_windows_trigger.py",
        ],
        "forbidden_paths": ["mcp_integration_lib/mcp_dispatch.lsp"],
        "accepted_evidence": [
            {
                "evidence_ref": "SEQ288:S0",
                "source_ref": "issue:131#comment-5436109816",
            }
        ],
        "pre_execution_closure": "REQUIRED",
        "causal_family": "WINDOWS_LISP_TRIGGER_EXECUTION_BOUNDARY",
        "causal_budget": 5,
        "allowed_temp_repairs": ["run-owned parser/helper/telemetry only"],
        "live_budget": 1,
        "expensive_budget": 1,
        "acceptance_oracle": "exact receiver ownership + execution ACK + cleanup",
        "hard_handoff_conditions": [
            "WRITE_SET_EXPANSION",
            "SECURITY_AUTHORITY_AMBIGUITY",
            "CAUSAL_BUDGET_EXHAUSTED",
            "MISSION_COMPLETE",
        ],
        "cleanup_requirements": ["REPO_PARITY", "PROCESS_ENV_RESTORED"],
        "terminal_fields": ["CONTROL_SEQ", "NEXT_OWNER", "VERDICT", "EVIDENCE"],
        "human_relay_required": False,
        "merge_authority": False,
        "publication_authority": False,
    }


def test_compile_closed_long_horizon_mission() -> None:
    mission = compile_local_mission(_snapshot(), _routing(), _request())
    assert mission["control_seq"] == 291
    assert mission["authority_comment_id"] == 5436556581
    assert mission["current_main_sha"] == MAIN
    assert mission["active_pr_head_sha"] == HEAD
    assert mission["next_owner"] == "SOL"
    assert mission["causal_budget"] == 5
    assert validate_local_mission(mission, control_snapshot=_snapshot()) == mission


def test_rejects_web_capable_delegation() -> None:
    routing = dict(_routing())
    routing["classification"] = "WEB_CAPABLE"
    with pytest.raises(MissionContractError, match="WEB_CAPABLE"):
        compile_local_mission(_snapshot(), routing, _request())


def test_repo_mutation_requires_write_set_and_authority() -> None:
    request = _request()
    request["write_set"] = []
    with pytest.raises(MissionContractError, match="write_set"):
        compile_local_mission(_snapshot(), _routing(), request)

    with pytest.raises(MissionContractError, match="repo_write_allowed"):
        compile_local_mission(
            _snapshot(repo_write_allowed=False), _routing(), _request()
        )


def test_live_budget_requires_live_authority() -> None:
    with pytest.raises(MissionContractError, match="live_allowed"):
        compile_local_mission(_snapshot(live_allowed=False), _routing(), _request())


def test_rejects_merge_publication_and_human_relay_implication() -> None:
    for field in ("merge_authority", "publication_authority", "human_relay_required"):
        request = _request()
        request[field] = True
        with pytest.raises(MissionContractError, match=field):
            compile_local_mission(_snapshot(), _routing(), request)


def test_rejects_out_of_budget_causal_loop() -> None:
    request = _request()
    request["causal_budget"] = 6
    with pytest.raises(MissionContractError, match="causal_budget"):
        compile_local_mission(_snapshot(), _routing(), request)


def test_rejects_reuse_without_source_reference() -> None:
    request = _request()
    request["accepted_evidence"] = [{"evidence_ref": "SEQ288:S0", "source_ref": ""}]
    with pytest.raises(MissionContractError, match="source_ref"):
        compile_local_mission(_snapshot(), _routing(), request)


def test_validation_rejects_snapshot_drift() -> None:
    mission = compile_local_mission(_snapshot(), _routing(), _request())
    drifted = copy.deepcopy(_snapshot())
    drifted["control_seq"] = 292
    with pytest.raises(MissionContractError, match="control snapshot"):
        validate_local_mission(mission, control_snapshot=drifted)
