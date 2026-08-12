"""Causal RED tests for the first offline R6 repair-executor composition slice."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from copy import deepcopy
from importlib import import_module
import importlib.util
from functools import lru_cache
from pathlib import Path

import pytest

from cad_agent.repair_authorization import (
    consume_repair_authorization,
    issue_repair_authorization,
)
from cad_agent.candidate_revision import build_candidate_revision_state
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.repair_operation_contract import (
    REPAIR_OPERATION_SCHEMA_VERSION,
    normalize_repair_operation,
)


try:
    repair_executor_adapter = import_module("cad_agent.approved_repair_adapter")
except ModuleNotFoundError:
    # Keep the first RED causal: the R6 module/public seam is absent, not
    # hidden by an unrelated fixture or live-environment failure.
    repair_executor_adapter = None


SHA_CANDIDATE = "a" * 64
SHA_STATE = "b" * 64
SHA_FAILURE = "c" * 64
SHA_PLAN = "d" * 64
SHA_OPERATION = "e" * 64

def _module():
    if repair_executor_adapter is None:
        pytest.fail("R6 repair-executor adapter module/public API is absent")
    return repair_executor_adapter


def _line_payload() -> dict[str, object]:
    return {
        "schema_version": REPAIR_OPERATION_SCHEMA_VERSION,
        "operation": "REPAIR_DXF_PRIMITIVE",
        "target": {"target_handle": "H204", "layer": "R6-TEST"},
        "parameters": {
            "capability": "LINE",
            "geometry": {
                "type": "line",
                "start": [0.0, 0.0],
                "end": [10.0, 0.0],
            },
        },
        "preserve_anchors": ["anchor-r6-204"],
        "constraint_refs": ["constraint-r6-204"],
    }


def _operation():
    return normalize_repair_operation(_line_payload())


@lru_cache(maxsize=1)
def _accepted_candidate_binding() -> tuple[dict[str, object], dict[str, object]]:
    """Reuse the accepted R4 fixture builder instead of minting a state here."""
    path = Path(__file__).with_name("test_cad_agent_candidate_revision.py")
    spec = importlib.util.spec_from_file_location("r4_candidate_fixtures", path)
    if spec is None or spec.loader is None:
        raise AssertionError("accepted R4 fixture loader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _root_args, root, _child, _grandchild_args = module._valid_lineage_chain()
    state = build_candidate_revision_state(
        candidate_revisions=[root],
        current_candidate_revision_sha256=root["candidate_revision_sha256"],
    )
    return state, root


def _candidate_binding() -> tuple[dict[str, object], dict[str, object]]:
    state, root = _accepted_candidate_binding()
    return deepcopy(state), deepcopy(root)


def _operation_fingerprint() -> str:
    return canonical_json_sha256(_operation().as_executor_payload())


def _authorization_fields() -> dict[str, object]:
    state, candidate = _candidate_binding()
    return {
        "run_id": "run-r6-204",
        "work_item_id": "work-r6-204",
        "candidate_revision_id": candidate["revision_id"],
        "candidate_revision_sha256": candidate["candidate_revision_sha256"],
        "r5_failure_id": "r5-failure-r6-204",
        "r5_failure_sha256": SHA_FAILURE,
        "repair_plan_id": "repair-plan-r6-204",
        "repair_plan_sha256": SHA_PLAN,
        "repair_plan_version": "repair-plan-1.0",
        "repair_operation_contract_version": REPAIR_OPERATION_SCHEMA_VERSION,
        "repair_operation_contract_fingerprint": _operation_fingerprint(),
    }


@dataclass
class _WorkspaceOwner:
    close_calls: list[dict[str, object]] = field(default_factory=list)
    close_error: BaseException | None = None

    def close_disposable_workspace(
        self,
        lease: "_WorkspaceLease",
        *,
        candidate_identity: str,
        source_identity: str,
        source_fingerprint: str,
    ) -> dict[str, object]:
        self.close_calls.append(
            {
                "lease": lease,
                "candidate_identity": candidate_identity,
                "source_identity": source_identity,
                "source_fingerprint": source_fingerprint,
            }
        )
        if self.close_error is not None:
            raise self.close_error
        return {
            "lease_id": lease.lease_id,
            "candidate_identity": candidate_identity,
            "source_identity": source_identity,
            "source_fingerprint": source_fingerprint,
            "close_outcome": "closed",
            "cleanup_outcome": "zero_survivors",
            "save_changes": False,
            "lifecycle_state": "closed",
        }


@dataclass
class _WorkspaceLease:
    owner: _WorkspaceOwner
    lease_id: str = "lease-r6-204"
    candidate_identity: str = "candidate-r6-204"
    source_identity: str = "r5-failure-r6-204"
    source_fingerprint: str = SHA_FAILURE
    disposable: bool = True
    save_changes: bool = False
    lifecycle_state: str = "active"
    workspace_path: Path = Path("C:/disposable/r6-204")


@dataclass
class _ExecutorClient:
    calls: list[dict[str, object]] = field(default_factory=list)
    error: BaseException | None = None

    def entity_erase(self, target_handle: str) -> None:
        if self.error is not None:
            raise self.error
        del target_handle

    def entity_create_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        layer: str,
    ) -> dict[str, str]:
        if self.error is not None:
            raise self.error
        self.calls.append(
            {
                "capability": "LINE",
                "target_handle": None,
                "geometry": {
                    "type": "line",
                    "start": [x1, y1],
                    "end": [x2, y2],
                },
                "layer": layer,
            }
        )
        return {"handle": "H204-NEW"}


def _candidate_state() -> dict[str, object]:
    state, _candidate = _candidate_binding()
    return state


def _repair_context() -> dict[str, object]:
    state, candidate = _candidate_binding()
    return {
        "run_id": "run-r6-204",
        "work_item_id": "work-r6-204",
        "candidate_revision_id": candidate["revision_id"],
        "candidate_revision_sha256": candidate["candidate_revision_sha256"],
        "candidate_state_sha256": state["state_sha256"],
        "repair_plan_id": "repair-plan-r6-204",
        "repair_plan_sha256": SHA_PLAN,
        "repair_plan_version": "repair-plan-1.0",
        "repair_operation_contract_version": REPAIR_OPERATION_SCHEMA_VERSION,
        "repair_operation_contract_fingerprint": _operation_fingerprint(),
        "r3_target_handles": ["H204"],
        "protected_target_handles": ["H204"],
    }


def _r5_failure(**overrides: object) -> dict[str, object]:
    _state, candidate = _candidate_binding()
    result = {
        "verdict": "FAIL",
        "failure_id": "r5-failure-r6-204",
        "failure_sha256": SHA_FAILURE,
        "candidate_revision_id": candidate["revision_id"],
        "candidate_revision_sha256": candidate["candidate_revision_sha256"],
        "repair_plan_id": "repair-plan-r6-204",
        "repair_plan_sha256": SHA_PLAN,
        "repair_plan_version": "repair-plan-1.0",
    }
    result.update(overrides)
    return result


def _valid_inputs(**overrides: object) -> dict[str, object]:
    fields = _authorization_fields()
    token = issue_repair_authorization(**fields)
    _state, candidate = _candidate_binding()
    owner = _WorkspaceOwner()
    inputs: dict[str, object] = {
        "authorization": token,
        "repair_operation": _operation(),
        "repair_context": _repair_context(),
        "candidate_state": _candidate_state(),
        "r5_failure": _r5_failure(),
        "workspace_lease": _WorkspaceLease(
            owner,
            candidate_identity=candidate["revision_id"],
            source_fingerprint=SHA_FAILURE,
        ),
        "executor_client": _ExecutorClient(),
    }
    inputs.update(overrides)
    return inputs


def _consume_exact(token):
    return consume_repair_authorization(token, **_authorization_fields())


def _execute(inputs: dict[str, object]):
    return _module().execute_approved_repair(**inputs)


def test_missing_public_r6_module_is_the_causal_red() -> None:
    module = _module()
    assert callable(module.execute_approved_repair)


def test_exact_owner_composition_returns_one_bounded_success() -> None:
    inputs = _valid_inputs()
    result = _execute(inputs)
    assert isinstance(result, dict)
    assert result["mutation_outcome"] == "SUCCESS"
    assert len(inputs["workspace_lease"].owner.close_calls) == 1
    with pytest.raises(Exception, match="ALREADY_CONSUMED"):
        _consume_exact(inputs["authorization"])


@pytest.mark.parametrize(
    "failure_overrides",
    [
        {"verdict": "PASS"},
        {"failure_id": "stale-failure"},
        {"candidate_revision_sha256": "f" * 64},
        {"repair_plan_sha256": "f" * 64},
    ],
)
def test_non_fail_or_stale_r5_evidence_cannot_consume_or_mutate(
    failure_overrides: dict[str, object],
) -> None:
    inputs = _valid_inputs(r5_failure=_r5_failure(**failure_overrides))
    with pytest.raises(Exception, match="FAIL|stale|candidate|repair"):
        _execute(inputs)
    assert inputs["executor_client"].calls == []
    assert _consume_exact(inputs["authorization"]) is inputs["authorization"]


def test_foreign_r4_candidate_is_rejected_before_consume_or_mutation() -> None:
    inputs = _valid_inputs(candidate_state={**_candidate_state(), "current_candidate_revision_sha256": "f" * 64})
    with pytest.raises(Exception, match="candidate|current|state"):
        _execute(inputs)
    assert inputs["executor_client"].calls == []
    assert _consume_exact(inputs["authorization"]) is inputs["authorization"]


def test_forged_workspace_lease_is_rejected_before_consume_or_mutation() -> None:
    inputs = _valid_inputs(
        workspace_lease=_WorkspaceLease(
            _WorkspaceOwner(),
            candidate_identity="foreign-candidate",
            source_identity="foreign-source",
            source_fingerprint="f" * 64,
        )
    )
    with pytest.raises(Exception, match="workspace|lease|binding"):
        _execute(inputs)
    assert inputs["executor_client"].calls == []
    assert _consume_exact(inputs["authorization"]) is inputs["authorization"]


def test_wrong_repair_plan_keeps_legitimate_authorization_unburned() -> None:
    inputs = _valid_inputs(
        repair_context={**_repair_context(), "repair_plan_id": "foreign-plan"}
    )
    with pytest.raises(Exception, match="repair|plan|fingerprint"):
        _execute(inputs)
    assert inputs["executor_client"].calls == []
    assert _consume_exact(inputs["authorization"]) is inputs["authorization"]


def test_replay_and_concurrent_exact_execution_have_one_consume_and_one_mutation() -> None:
    inputs = _valid_inputs()
    outcomes: list[object] = []
    lock = threading.Lock()

    def attempt() -> None:
        try:
            value = _execute(inputs)
        except Exception as error:  # noqa: BLE001 - categorical owner outcome
            value = error
        with lock:
            outcomes.append(value)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: attempt(), range(2)))
    successes = [value for value in outcomes if isinstance(value, dict)]
    assert len(successes) <= 1
    assert len(inputs["workspace_lease"].owner.close_calls) <= 1


@pytest.mark.parametrize("operation", [
    {
        "schema_version": REPAIR_OPERATION_SCHEMA_VERSION,
        "operation": "REPAIR_DXF_COMPONENT",
        "target": {"target_handle": "H204", "layer": "R6-TEST"},
        "parameters": {"capability": "INSERT", "geometry": {}},
        "preserve_anchors": [],
        "constraint_refs": [],
    },
])
def test_unsupported_operation_fails_closed_without_executor_call(operation: object) -> None:
    inputs = _valid_inputs(repair_operation=operation)
    with pytest.raises(Exception, match="UNSUPPORTED|unsupported|component|INSERT"):
        _execute(inputs)
    assert inputs["executor_client"].calls == []
    assert _consume_exact(inputs["authorization"]) is inputs["authorization"]


class _HostileStr(str):
    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return hash("FAIL")


class _HostileMapping(dict):
    touched = False

    def items(self):
        type(self).touched = True
        raise AssertionError("hostile mapping protocol invoked")


@pytest.mark.parametrize(
    "mutator",
    [
        lambda inputs: inputs["repair_context"].__setitem__("run_id", _HostileStr("evil")),
        lambda inputs: inputs["r5_failure"].__setitem__("verdict", _HostileStr("PASS")),
        lambda inputs: inputs["repair_context"].__setitem__("script", "os.system"),
        lambda inputs: inputs["repair_context"].__setitem__("workspace_path", Path("C:/secret")),
        lambda inputs: inputs["repair_context"].__setitem__("hostile", _HostileMapping()),
    ],
)
def test_hostile_dynamic_fields_fail_before_consume_or_mutation(mutator) -> None:
    inputs = _valid_inputs()
    _HostileMapping.touched = False
    mutator(inputs)
    with pytest.raises(Exception):
        _execute(inputs)
    assert _HostileMapping.touched is False
    assert inputs["executor_client"].calls == []
    assert _consume_exact(inputs["authorization"]) is inputs["authorization"]


def test_protected_or_driving_scope_mismatch_fails_before_consume() -> None:
    inputs = _valid_inputs(
        repair_context={**_repair_context(), "protected_target_handles": ["FOREIGN"]}
    )
    with pytest.raises(Exception, match="protected|scope|target|constraint"):
        _execute(inputs)
    assert inputs["executor_client"].calls == []
    assert _consume_exact(inputs["authorization"]) is inputs["authorization"]


def test_wrong_r3_target_membership_fails_before_consume() -> None:
    inputs = _valid_inputs(
        repair_context={**_repair_context(), "r3_target_handles": ["FOREIGN"]}
    )
    with pytest.raises(Exception, match="R3|target|scope"):
        _execute(inputs)
    assert inputs["executor_client"].calls == []
    assert _consume_exact(inputs["authorization"]) is inputs["authorization"]


@pytest.mark.parametrize("executor_error", [TimeoutError("timeout"), RuntimeError("ambiguous")])
def test_executor_error_is_categorical_and_never_false_success(executor_error: BaseException) -> None:
    executor = _ExecutorClient(error=executor_error)
    inputs = _valid_inputs(executor_client=executor)
    with pytest.raises(Exception, match="TIMEOUT|EXECUTOR|MUTATION|failure|ambiguous"):
        _execute(inputs)
    assert executor.calls == []


def test_uncertain_closure_is_terminal_failure_not_success() -> None:
    owner = _WorkspaceOwner(close_error=RuntimeError("cleanup uncertain"))
    _state, candidate = _candidate_binding()
    inputs = _valid_inputs(
        workspace_lease=_WorkspaceLease(
            owner,
            candidate_identity=candidate["revision_id"],
            source_fingerprint=SHA_FAILURE,
        )
    )
    with pytest.raises(Exception, match="CLEANUP|closure|cleanup|failure"):
        _execute(inputs)
    assert owner.close_calls


def test_executor_delegation_contains_only_accepted_a2_fields() -> None:
    inputs = _valid_inputs()
    _execute(inputs)
    assert len(inputs["executor_client"].calls) == 1
    assert set(inputs["executor_client"].calls[0]) == {
        "capability",
        "target_handle",
        "geometry",
        "layer",
    }


def test_result_evidence_does_not_mint_r4_r5_or_publication_authority() -> None:
    result = _execute(_valid_inputs())
    forbidden = {
        "r4_selected",
        "r4_current",
        "r4_accepted",
        "r5_pass",
        "approval",
        "published",
        "publication_eligible",
    }
    assert forbidden.isdisjoint(result)


def test_mutation_invalidates_pre_repair_r5_for_downstream_acceptance() -> None:
    result = _execute(_valid_inputs())
    assert result["mutation_outcome"] == "SUCCESS"
    assert result.get("requires_new_r5_cycle") is True
    assert result.get("r5_verdict") != "PASS"


def test_privacy_safe_errors_do_not_echo_paths_geometry_or_authorization_secret() -> None:
    secret = "authorization-secret-r6-204"
    inputs = _valid_inputs(
        repair_context={
            **_repair_context(),
            "workspace_path": "C:/customer/private.dxf",
            "secret": secret,
        }
    )
    with pytest.raises(Exception) as exc_info:
        _execute(inputs)
    message = str(exc_info.value)
    assert "C:/customer/private.dxf" not in message
    assert secret not in message
    assert "H204" not in message


