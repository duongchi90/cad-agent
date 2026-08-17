"""Causal RED tests for the first offline R6 repair-executor composition slice."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from copy import deepcopy
from importlib import import_module
import importlib.util
from functools import lru_cache
from pathlib import Path
from tempfile import mkdtemp

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
from cad_agent.visual_contracts import VisualContractError, validate_visual_contract
from cad_agent.visual_supervisor_adapter import (
    VisualSupervisorAdapterError,
    validate_visual_verdict_result,
)
from cad_agent.approved_repair_adapter import RepairExecutorAdapterError
_DOTNET_IPC = importlib.import_module("mcp_integration_lib.dotnet_ipc")
DisposableWorkspaceClosure = _DOTNET_IPC.DisposableWorkspaceClosure
DisposableWorkspaceLease = _DOTNET_IPC.DisposableWorkspaceLease
DotNetIPCClient = _DOTNET_IPC.DotNetIPCClient
result_path = _DOTNET_IPC.result_path


try:
    approved_repair_adapter = import_module("cad_agent.approved_repair_adapter")
except ModuleNotFoundError:
    # Keep the first RED causal: the R6 module/public seam is absent, not
    # hidden by an unrelated fixture or live-environment failure.
    approved_repair_adapter = None


SHA_CANDIDATE = "a" * 64
SHA_STATE = "b" * 64
SHA_FAILURE = "c" * 64
SHA_PLAN = "d" * 64
SHA_OPERATION = "e" * 64

def _module():
    if approved_repair_adapter is None:
        pytest.fail("R6 repair-executor adapter module/public API is absent")
    return approved_repair_adapter


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


@lru_cache(maxsize=1)
def _accepted_foreign_candidate_binding() -> tuple[
    dict[str, object], dict[str, object]
]:
    """Build a second owner-valid current tuple for cross-binding negatives."""
    path = Path(__file__).with_name("test_cad_agent_candidate_revision.py")
    spec = importlib.util.spec_from_file_location("r4_foreign_candidate_fixtures", path)
    if spec is None or spec.loader is None:
        raise AssertionError("accepted R4 fixture loader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _root_args, _root, child, _grandchild_args = module._valid_lineage_chain()
    state = build_candidate_revision_state(
        candidate_revisions=[child],
        current_candidate_revision_sha256=child["candidate_revision_sha256"],
    )
    return state, child


def _foreign_candidate_binding() -> tuple[dict[str, object], dict[str, object]]:
    state, child = _accepted_foreign_candidate_binding()
    return deepcopy(state), deepcopy(child)


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


def _WorkspaceOwner(close_error: BaseException | None = None) -> DotNetIPCClient:
    """Create the real owner with an offline dispatcher and test call ledger."""
    ipc_dir = Path(mkdtemp(prefix="cad-agent-r6-204-"))
    root = ipc_dir / "disposable-workspaces"
    dispatcher = _OfflineDispatcher(ipc_dir)
    owner = DotNetIPCClient(ipc_dir=ipc_dir, trigger=dispatcher, disposable_root=root)
    owner._test_root = root
    owner.close_calls = []
    canonical_close = owner.close_disposable_workspace

    def close(
        lease: DisposableWorkspaceLease,
        *,
        candidate_identity: str,
        source_identity: str,
        source_fingerprint: str,
    ) -> DisposableWorkspaceClosure:
        owner.close_calls.append(
            {
                "lease": lease,
                "candidate_identity": candidate_identity,
                "source_identity": source_identity,
                "source_fingerprint": source_fingerprint,
            }
        )
        if close_error is not None:
            raise close_error
        return canonical_close(
            lease,
            candidate_identity=candidate_identity,
            source_identity=source_identity,
            source_fingerprint=source_fingerprint,
        )

    owner.close_disposable_workspace = close
    return owner


class _OfflineDispatcher:
    def __init__(self, ipc_dir: Path) -> None:
        self.ipc_dir = ipc_dir
        self.requests: list[dict[str, object]] = []

    def __call__(self) -> None:
        request_files = list(self.ipc_dir.glob("cadagent_dotnet_request_*.json"))
        assert len(request_files) == 1
        request = json.loads(request_files[0].read_text(encoding="utf-8"))
        self.requests.append(request)
        result_path(self.ipc_dir, str(request["request_id"])).write_text(
            json.dumps(
                {
                    "request_id": request["request_id"],
                    "operation": request["operation"],
                    "drawing_full_path": request["drawing_full_path"],
                    "success": True,
                    "changed": False,
                    "entity_handles": [],
                    "warnings": [],
                    "errors": [],
                    "started_at": "2026-08-12T00:00:00Z",
                    "completed_at": "2026-08-12T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )


def _WorkspaceLease(
    owner: DotNetIPCClient,
    *,
    candidate_identity: str = "candidate-r6-204",
    source_identity: str = "r5-failure-r6-204",
    source_fingerprint: str = SHA_FAILURE,
) -> DisposableWorkspaceLease:
    return owner.issue_disposable_workspace(
        candidate_identity=candidate_identity,
        source_identity=source_identity,
        source_fingerprint=source_fingerprint,
        purpose="r6-gate-0",
        workspace_root=owner._test_root,
    )


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
        "workspace_owner": owner,
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
    assert len(inputs["workspace_owner"].close_calls) == 1
    assert set(result["closure"]) == {
        "lease_id",
        "candidate_identity",
        "source_identity",
        "source_fingerprint",
        "close_outcome",
        "cleanup_outcome",
        "save_changes",
        "lifecycle_state",
    }
    assert "workspace_path" not in result["closure"]
    with pytest.raises(Exception, match="ALREADY_CONSUMED"):
        _consume_exact(inputs["authorization"])


def test_result_binds_exact_owner_authorization_identity_privacy_safely() -> None:
    inputs = _valid_inputs()
    authorization = inputs["authorization"]
    result = _execute(inputs)
    assert type(result["authorization_id"]) is str
    assert result["authorization_id"] == authorization.authorization_id
    semantic_result = {key: value for key, value in result.items() if key != "result_sha256"}
    assert result["result_sha256"] == canonical_json_sha256(semantic_result)
    forbidden = {"authorization", "tuple_values", "created_at", "expires_at"}
    assert forbidden.isdisjoint(result)


def test_duck_typed_workspace_owner_is_rejected_before_consume() -> None:
    class FakeOwner:
        def validate_disposable_workspace(self, *args, **kwargs):
            return object()

        def close_disposable_workspace(self, *args, **kwargs):
            return object()

    inputs = _valid_inputs(workspace_owner=FakeOwner())
    with pytest.raises(Exception, match="workspace|lease"):
        _execute(inputs)
    assert inputs["executor_client"].calls == []
    assert _consume_exact(inputs["authorization"]) is inputs["authorization"]


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
    foreign_owner = _WorkspaceOwner()
    inputs = _valid_inputs(
        workspace_owner=foreign_owner,
        workspace_lease=_WorkspaceLease(
            foreign_owner,
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
    assert len(inputs["workspace_owner"].close_calls) <= 1


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
    assert len(inputs["workspace_owner"].close_calls) == 1


def test_executor_and_closure_failure_is_categorical_without_retry_or_success() -> None:
    owner = _WorkspaceOwner(close_error=RuntimeError("cleanup uncertain"))
    executor = _ExecutorClient(error=RuntimeError("executor ambiguous"))
    _state, candidate = _candidate_binding()
    inputs = _valid_inputs(
        workspace_owner=owner,
        workspace_lease=_WorkspaceLease(
            owner,
            candidate_identity=candidate["revision_id"],
            source_fingerprint=SHA_FAILURE,
        ),
        executor_client=executor,
    )
    with pytest.raises(Exception, match="CLOSURE|closure|cleanup|failure"):
        _execute(inputs)
    assert executor.calls == []
    assert len(owner.close_calls) == 1


def test_uncertain_closure_is_terminal_failure_not_success() -> None:
    owner = _WorkspaceOwner(close_error=RuntimeError("cleanup uncertain"))
    _state, candidate = _candidate_binding()
    inputs = _valid_inputs(
        workspace_owner=owner,
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


def _result_validator():
    validator = getattr(_module(), "validate_approved_repair_result", None)
    assert callable(validator), "R6 accepted-result validator public API is absent"
    return validator


def _valid_r6_result() -> dict[str, object]:
    return _execute(_valid_inputs())


def _reseal_result(result: dict[str, object]) -> dict[str, object]:
    semantic = deepcopy(result)
    semantic.pop("result_sha256", None)
    result["result_sha256"] = canonical_json_sha256(semantic)
    return result


def _expected_result_bindings(result: dict[str, object]) -> dict[str, object]:
    return {
        "expected_candidate_revision_id": result["candidate_revision_id"],
        "expected_candidate_revision_sha256": result["candidate_revision_sha256"],
        "expected_r5_failure_id": result["r5_failure_id"],
        "expected_r5_failure_sha256": result["r5_failure_sha256"],
        "expected_repair_plan_id": result["repair_plan_id"],
        "expected_repair_plan_sha256": result["repair_plan_sha256"],
        "expected_repair_plan_version": result["repair_plan_version"],
        "expected_repair_operation_contract_version": result["repair_operation_contract_version"],
        "expected_repair_operation_contract_fingerprint": result["repair_operation_contract_fingerprint"],
    }


def test_public_r6_result_validator_is_causal_red_and_deep_copy_isolated() -> None:
    result = _valid_r6_result()
    snapshot = deepcopy(result)
    validated = _result_validator()(result, **_expected_result_bindings(result))
    assert result == snapshot
    assert validated == result
    assert validated is not result
    assert validated["closure"] is not result["closure"]
    validated["closure"]["lifecycle_state"] = "tampered"
    assert result["closure"]["lifecycle_state"] == "closed"


def test_public_r6_result_validator_rejects_hash_mismatch() -> None:
    result = _valid_r6_result()
    result["result_sha256"] = "f" * 64
    with pytest.raises(Exception, match="MALFORMED"):
        _result_validator()(result)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda result: result.__setitem__("unknown", "value"),
        lambda result: result.__delitem__("authorization_id"),
        lambda result: result.__setitem__("schema_version", "foreign-schema"),
        lambda result: result.__setitem__("mutation_outcome", "FAILED"),
        lambda result: result.__setitem__("requires_new_r5_cycle", False),
        lambda result: result.__setitem__("executor_result_category", "FOREIGN"),
        lambda result: result.__setitem__("authorization_id", ""),
        lambda result: result.__setitem__("candidate_revision_id", _HostileStr("foreign")),
        lambda result: result.__setitem__("requires_new_r5_cycle", 1),
    ],
)
def test_public_r6_result_validator_rejects_resealed_structural_type_or_semantic_tamper(mutator) -> None:
    result = _valid_r6_result()
    mutator(result)
    _reseal_result(result)
    with pytest.raises(Exception, match="MALFORMED"):
        _result_validator()(result)


def test_public_r6_result_validator_rejects_dict_subclass_without_hostile_protocol() -> None:
    result = _HostileMapping(_valid_r6_result())
    _HostileMapping.touched = False
    with pytest.raises(Exception, match="MALFORMED"):
        _result_validator()(result)
    assert _HostileMapping.touched is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("save_changes", True),
        ("lifecycle_state", "active"),
        ("cleanup_outcome", "survivors"),
        ("close_outcome", "open"),
        ("lease_id", ""),
    ],
)
def test_public_r6_result_validator_rejects_resealed_non_closed_closure(field: str, value: object) -> None:
    result = _valid_r6_result()
    result["closure"][field] = value
    _reseal_result(result)
    with pytest.raises(Exception, match="CLOSURE_FAILED"):
        _result_validator()(result)


def test_public_r6_result_validator_rejects_resealed_closure_dict_subclass() -> None:
    class PlainDictSubclass(dict):
        pass

    result = _valid_r6_result()
    result["closure"] = PlainDictSubclass(result["closure"])
    _reseal_result(result)
    with pytest.raises(Exception, match="CLOSURE_FAILED"):
        _result_validator()(result)


@pytest.mark.parametrize(
    ("argument", "foreign_value"),
    [
        ("expected_candidate_revision_id", "foreign-candidate"),
        ("expected_candidate_revision_sha256", "f" * 64),
        ("expected_r5_failure_id", "foreign-r5-failure"),
        ("expected_r5_failure_sha256", "f" * 64),
        ("expected_repair_plan_id", "foreign-plan"),
        ("expected_repair_plan_sha256", "f" * 64),
        ("expected_repair_plan_version", "foreign-plan-version"),
        ("expected_repair_operation_contract_version", "foreign-operation-version"),
        ("expected_repair_operation_contract_fingerprint", "f" * 64),
    ],
)
def test_public_r6_result_validator_rejects_foreign_expected_binding(argument: str, foreign_value: str) -> None:
    result = _valid_r6_result()
    with pytest.raises(Exception, match="BINDING_MISMATCH"):
        _result_validator()(result, **{argument: foreign_value})


def test_public_r6_result_validator_binding_error_is_privacy_safe_and_non_mutating() -> None:
    result = _valid_r6_result()
    snapshot = deepcopy(result)
    secret = "C:/customer/private-result.dxf"
    with pytest.raises(Exception) as exc_info:
        _result_validator()(result, expected_candidate_revision_id=secret)
    assert "BINDING_MISMATCH" in str(exc_info.value)
    assert secret not in str(exc_info.value)
    assert result == snapshot


@pytest.mark.parametrize(
    ("closure_field", "foreign_value"),
    [
        ("candidate_identity", "foreign-candidate"),
        ("source_identity", "foreign-r5-failure"),
        ("source_fingerprint", "f" * 64),
    ],
)
def test_public_r6_result_validator_rejects_resealed_foreign_closure_identity(
    closure_field: str,
    foreign_value: str,
) -> None:
    result = _valid_r6_result()
    result["closure"][closure_field] = foreign_value
    _reseal_result(result)
    with pytest.raises(Exception, match="BINDING_MISMATCH"):
        _result_validator()(result)


def _sealed_r5_fail_result() -> dict[str, object]:
    """Build the exact closed owner-shaped R5 result, then validate it canonically."""
    state, candidate = _candidate_binding()
    semantic: dict[str, object] = {
        "schema_version": "r5-visual-verdict-result-1.0",
        "request_sha256": "1" * 64,
        "observation_sha256": "2" * 64,
        "verdict": "FAIL",
        "candidate_revision_sha256": candidate["candidate_revision_sha256"],
        "candidate_state_sha256": state["state_sha256"],
        "registry_snapshot_sha256": candidate["change_scope"]["registry_snapshot_sha256"],
        "drawing_reference_sha256": "3" * 64,
        "drawing_observation_sha256": "4" * 64,
        "latest_mutation_sha256": candidate["mutation_evidence"][
            "latest_mutation_evidence_sha256"
        ],
        "task6_thread_id": "thread-r6-204",
        "task6_turn_id": "turn-r6-204",
        "regions": [
            {
                "region_id": "critical-region",
                "view_id": "view-r6-204",
                "sheet_id": "sheet-r6-204",
                "layout_id": "layout-r6-204",
                "criticality": "CRITICAL",
                "status": "FAIL",
            }
        ],
    }
    verdict_sha256 = canonical_json_sha256(semantic)
    result = {**semantic, "verdict_id": verdict_sha256, "verdict_sha256": verdict_sha256}
    validated = validate_visual_verdict_result(
        result,
        expected_request_sha256=semantic["request_sha256"],
        expected_candidate_revision_sha256=semantic["candidate_revision_sha256"],
        expected_candidate_state_sha256=semantic["candidate_state_sha256"],
        expected_latest_mutation_sha256=semantic["latest_mutation_sha256"],
    )
    assert validated == result
    return validated


def _accepted_repair_plan(
    sealed: dict[str, object], candidate: dict[str, object]
) -> dict[str, object]:
    component_id = candidate["change_scope"]["impact"]["component_ids"][0]
    plan: dict[str, object] = {
        "schema_version": "repair-plan-1.0",
        "repair_id": "repair-plan-r6-204",
        "source_review_id": sealed["verdict_id"],
        "run_id": candidate["run_id"],
        "target_drawing_sha256": candidate["candidate_artifacts"]["artifact_sha256"],
        "operations": [
            {
                "operation": "ADJUST_SPLINE_CONTROL_REGION",
                "target": {"stable_entity_id": component_id, "feature": "EDGE"},
                "preserve_anchors": ["anchor-r6-204"],
                "constraint_refs": ["constraint-r6-204"],
            }
        ],
        "affected_regions": ["critical-region"],
        "expected_improvements": ["critical-region:PASS"],
        "must_not_worsen": ["protected-geometry"],
        "rollback_candidate_sha256": candidate["candidate_artifacts"]["artifact_sha256"],
    }
    validated = validate_visual_contract(plan, contract="repair_plan")
    assert validated == plan
    return validated


def _planner_context(
    sealed: dict[str, object],
    state: dict[str, object],
    candidate: dict[str, object],
) -> dict[str, object]:
    """R3/protected planner context with current candidate bindings only."""
    return {
        "run_id": candidate["run_id"],
        "work_item_id": "work-r6-204",
        "candidate_revision_id": candidate["revision_id"],
        "candidate_revision_sha256": candidate["candidate_revision_sha256"],
        "candidate_state_sha256": state["state_sha256"],
        "request_sha256": sealed["request_sha256"],
        "latest_mutation_sha256": sealed["latest_mutation_sha256"],
        "r3_target_handles": ["H204"],
        "protected_target_handles": ["H204"],
    }


def _executor_context(
    sealed: dict[str, object],
    state: dict[str, object],
    candidate: dict[str, object],
    plan: dict[str, object],
) -> dict[str, object]:
    context = _planner_context(sealed, state, candidate)
    context.update(
        {
            "repair_plan_id": plan["repair_id"],
            "repair_plan_sha256": canonical_json_sha256(plan),
            "repair_plan_version": plan["schema_version"],
            "repair_operation_contract_version": REPAIR_OPERATION_SCHEMA_VERSION,
            "repair_operation_contract_fingerprint": _operation_fingerprint(),
        }
    )
    return context


def _planner_inputs() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    state, candidate = _candidate_binding()
    sealed = _sealed_r5_fail_result()
    plan = _accepted_repair_plan(sealed, candidate)
    context = _planner_context(sealed, state, candidate)
    return sealed, state, candidate, plan, context


def _call_planner(
    sealed: dict[str, object],
    state: dict[str, object],
    candidate: dict[str, object],
    plan: dict[str, object],
    context: dict[str, object],
):
    planner = getattr(_module(), "prepare_repair_plan", None)
    assert callable(planner), (
        "R6 causal RED: missing bounded public prepare_repair_plan seam"
    )
    return planner(
        r5_result=sealed,
        candidate_revision=candidate,
        candidate_state=state,
        repair_plan=plan,
        r3_context=context,
    )


def _sealed_r5_variant(verdict: str) -> dict[str, object]:
    result = deepcopy(_sealed_r5_fail_result())
    result["verdict"] = verdict
    result["regions"][0]["status"] = "PASS" if verdict == "PASS" else "NOT_RUN"
    semantic = {
        key: deepcopy(value)
        for key, value in result.items()
        if key not in {"verdict_id", "verdict_sha256"}
    }
    digest = canonical_json_sha256(semantic)
    result["verdict_id"] = digest
    result["verdict_sha256"] = digest
    validated = validate_visual_verdict_result(
        result,
        expected_request_sha256=result["request_sha256"],
        expected_candidate_revision_sha256=result["candidate_revision_sha256"],
        expected_candidate_state_sha256=result["candidate_state_sha256"],
        expected_latest_mutation_sha256=result["latest_mutation_sha256"],
    )
    assert validated == result
    return validated


def _sealed_executor_inputs() -> tuple[
    dict[str, object], DotNetIPCClient, _ExecutorClient
]:
    state, candidate = _candidate_binding()
    sealed = _sealed_r5_fail_result()
    plan = _accepted_repair_plan(sealed, candidate)
    context = _executor_context(sealed, state, candidate, plan)
    fields = {
        "run_id": context["run_id"],
        "work_item_id": context["work_item_id"],
        "candidate_revision_id": context["candidate_revision_id"],
        "candidate_revision_sha256": context["candidate_revision_sha256"],
        "r5_failure_id": sealed["verdict_id"],
        "r5_failure_sha256": sealed["verdict_sha256"],
        "repair_plan_id": context["repair_plan_id"],
        "repair_plan_sha256": context["repair_plan_sha256"],
        "repair_plan_version": context["repair_plan_version"],
        "repair_operation_contract_version": context[
            "repair_operation_contract_version"
        ],
        "repair_operation_contract_fingerprint": context[
            "repair_operation_contract_fingerprint"
        ],
    }
    owner = _WorkspaceOwner()
    executor = _ExecutorClient()
    inputs: dict[str, object] = {
        "authorization": issue_repair_authorization(**fields),
        "repair_operation": _operation(),
        "repair_context": context,
        "candidate_state": state,
        "r5_result": sealed,
        "workspace_owner": owner,
        "workspace_lease": _WorkspaceLease(
            owner,
            candidate_identity=candidate["revision_id"],
            source_identity=sealed["verdict_id"],
            source_fingerprint=sealed["verdict_sha256"],
        ),
        "executor_client": executor,
    }
    return inputs, owner, executor


def test_r6_planner_public_seam_is_the_causal_red() -> None:
    _call_planner(*_planner_inputs())


def test_r6_executor_consumes_validated_sealed_r5_without_legacy_material() -> None:
    inputs, _owner, _executor = _sealed_executor_inputs()
    try:
        result = _execute(inputs)
    except TypeError:
        pytest.fail(
            "R6 causal RED: execute_approved_repair cannot consume the exact sealed "
            "R5 result without legacy caller material"
        )
    sealed = inputs["r5_result"]
    assert result["r5_failure_id"] == sealed["verdict_id"]
    assert result["r5_failure_sha256"] == sealed["verdict_sha256"]


def test_r6_planner_has_no_authority_or_side_effects(monkeypatch) -> None:
    inputs = _planner_inputs()

    def bomb(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("planner invoked an execution or authority owner")

    module = _module()
    for name in (
        "consume_repair_authorization",
        "normalize_repair_operation",
        "_execute_supported_repair_capability",
    ):
        monkeypatch.setattr(module, name, bomb)
    for name in (
        "issue_disposable_workspace",
        "validate_disposable_workspace",
        "close_disposable_workspace",
    ):
        monkeypatch.setattr(module.DotNetIPCClient, name, bomb)

    result = _call_planner(*inputs)
    _assert_planner_output_has_no_authority(result)


def _assert_planner_output_has_no_authority(value: object, path: tuple[object, ...] = ()) -> None:
    """Reject nested execution/authority payloads without banning declarative operations."""
    forbidden = {
        "approval",
        "authorization",
        "authorization_id",
        "executor",
        "executor_client",
        "executor_payload",
        "lease",
        "publication",
        "r4_selection",
        "repair_operation",
        "workspace",
        "workspace_lease",
        "workspace_owner",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.lower() if isinstance(key, str) else key
            assert normalized not in forbidden, (
                "planner output leaked forbidden authority/executor material at "
                f"{path + (key,)!r}"
            )
            _assert_planner_output_has_no_authority(nested, path + (key,))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _assert_planner_output_has_no_authority(nested, path + (index,))


def test_r6_planner_reuses_sealed_r5_identity_and_is_deterministic() -> None:
    first = _call_planner(*_planner_inputs())
    second = _call_planner(*_planner_inputs())
    assert first == second
    assert first["r5_failure_id"] == first["r5_failure_sha256"]
    assert first["r5_failure_id"] == _planner_inputs()[0]["verdict_id"]
    plan = first.get("repair_plan", first.get("plan"))
    plan_sha256 = first.get("repair_plan_sha256", first.get("plan_sha256"))
    assert plan == _planner_inputs()[3]
    assert plan_sha256 == canonical_json_sha256(plan)

    changed = _planner_inputs()
    changed_plan = deepcopy(changed[3])
    changed_plan["expected_improvements"] = [
        "critical-region:PASS",
        "normal-region:PASS",
    ]
    changed_plan = validate_visual_contract(changed_plan, contract="repair_plan")
    changed_result = _call_planner(
        changed[0], changed[1], changed[2], changed_plan, changed[4]
    )
    assert changed_result != first


@pytest.mark.parametrize("verdict", ["PASS", "NEEDS_HUMAN"])
def test_r6_planner_rejects_owner_valid_non_fail_r5(verdict: str) -> None:
    sealed, state, candidate, plan, context = _planner_inputs()
    sealed = _sealed_r5_variant(verdict)
    plan["source_review_id"] = sealed["verdict_id"]
    plan = validate_visual_contract(plan, contract="repair_plan")
    planner = getattr(_module(), "prepare_repair_plan", None)
    assert callable(planner), "R6 causal RED: planner public seam is absent"
    with pytest.raises((VisualSupervisorAdapterError, VisualContractError), match="FAIL|R5"):
        _call_planner(sealed, state, candidate, plan, context)


def _planner_rejection(mutator) -> None:
    sealed, state, candidate, plan, context = _planner_inputs()
    mutator(sealed, state, candidate, plan, context)
    planner = getattr(_module(), "prepare_repair_plan", None)
    assert callable(planner), "R6 causal RED: planner public seam is absent"
    with pytest.raises((VisualSupervisorAdapterError, VisualContractError)):
        _call_planner(sealed, state, candidate, plan, context)


def _replace_with_owner_valid_foreign_tuple(
    _result: dict[str, object],
    state: dict[str, object],
    candidate: dict[str, object],
    _plan: dict[str, object],
    context: dict[str, object],
) -> None:
    foreign_state, foreign_candidate = _foreign_candidate_binding()
    state.clear()
    state.update(foreign_state)
    candidate.clear()
    candidate.update(foreign_candidate)
    context.update(
        {
            "candidate_revision_id": foreign_candidate["revision_id"],
            "candidate_revision_sha256": foreign_candidate[
                "candidate_revision_sha256"
            ],
            "candidate_state_sha256": foreign_state["state_sha256"],
        }
    )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda result, _state, _candidate, _plan, _context: (
            result.__setitem__("request_sha256", "f" * 64),
            result.update(
                {
                    "verdict_id": canonical_json_sha256(
                        {
                            key: value
                            for key, value in result.items()
                            if key not in {"verdict_id", "verdict_sha256"}
                        }
                    )
                }
            ),
            result.__setitem__("verdict_sha256", result["verdict_id"]),
        ),
        lambda result, _state, _candidate, _plan, _context: (
            result.__setitem__("latest_mutation_sha256", "e" * 64),
            result.update(
                {
                    "verdict_id": canonical_json_sha256(
                        {
                            key: value
                            for key, value in result.items()
                            if key not in {"verdict_id", "verdict_sha256"}
                        }
                    )
                }
            ),
            result.__setitem__("verdict_sha256", result["verdict_id"]),
        ),
        lambda _result, _state, _candidate, _plan, context: context.__setitem__(
            "candidate_state_sha256", "f" * 64
        ),
        _replace_with_owner_valid_foreign_tuple,
        lambda _result, _state, _candidate, plan, _context: plan.__setitem__(
            "source_review_id", "caller-failure"
        ),
        lambda _result, _state, _candidate, plan, _context: plan["operations"][0].__setitem__(
            "operation", "REPAIR_DXF_PRIMITIVE"
        ),
        lambda result, _state, _candidate, _plan, _context: result.pop("regions"),
    ],
)
def test_r6_planner_rejects_isolated_stale_foreign_or_ambiguous_inputs(mutator) -> None:
    _planner_rejection(mutator)


def test_r6_planner_rejects_hostile_subclasses() -> None:
    sealed, state, candidate, plan, context = _planner_inputs()

    class HostileString(str):
        pass

    class HostileMapping(dict):
        pass

    sealed["verdict"] = HostileString("FAIL")
    planner = getattr(_module(), "prepare_repair_plan", None)
    assert callable(planner), "R6 causal RED: planner public seam is absent"
    with pytest.raises(VisualSupervisorAdapterError):
        _call_planner(sealed, state, candidate, plan, context)
    with pytest.raises(VisualSupervisorAdapterError):
        _call_planner(HostileMapping(sealed), state, candidate, plan, context)


def test_r6_planner_rejects_caller_substituted_failure_and_plan_identity() -> None:
    sealed, state, candidate, plan, context = _planner_inputs()
    planner = getattr(_module(), "prepare_repair_plan", None)
    assert callable(planner), "R6 causal RED: planner public seam is absent"
    with pytest.raises((VisualSupervisorAdapterError, VisualContractError, TypeError)):
        planner(
            r5_result=sealed,
            candidate_revision=candidate,
            candidate_state=state,
            repair_plan=plan,
            r3_context=context,
            r5_failure_id="caller-failure",
            r5_failure_sha256="f" * 64,
            repair_plan_id="caller-plan",
            repair_plan_sha256="f" * 64,
        )


def test_r6_planner_plan_never_falls_back_to_operation(monkeypatch) -> None:
    sealed, state, candidate, plan, context = _planner_inputs()
    validation_contracts: list[object] = []
    module = _module()
    canonical_validator = getattr(module, "validate_visual_contract", None)

    def record_repair_plan_validation(payload, *args, **kwargs):
        contract = kwargs.get("contract")
        if contract is None and args:
            contract = args[0]
        validation_contracts.append(contract)
        if canonical_validator is None:
            raise AssertionError("planner has no canonical repair-plan validator owner")
        return canonical_validator(payload, *args, **kwargs)

    def bomb(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("planner silently normalized a repair operation")

    monkeypatch.setattr(module, "validate_visual_contract", record_repair_plan_validation, raising=False)
    monkeypatch.setattr(module, "normalize_repair_operation", bomb)
    plan["operations"][0]["operation"] = "REPAIR_DXF_PRIMITIVE"
    with pytest.raises((VisualSupervisorAdapterError, VisualContractError)):
        _call_planner(sealed, state, candidate, plan, context)
    assert validation_contracts and validation_contracts[0] == "repair_plan"


def test_r6_executor_rejects_malformed_sealed_r5_without_legacy_material(monkeypatch) -> None:
    inputs, owner, executor = _sealed_executor_inputs()
    inputs["r5_result"]["verdict_sha256"] = "f" * 64
    calls: list[str] = []

    def forbidden_call(name: str):
        def bomb(*_args: object, **_kwargs: object) -> None:
            calls.append(name)
            raise AssertionError(f"malformed sealed R5 reached {name}")

        return bomb

    module = _module()
    monkeypatch.setattr(module, "consume_repair_authorization", forbidden_call("authorization"))
    monkeypatch.setattr(owner, "validate_disposable_workspace", forbidden_call("workspace_validate"))
    monkeypatch.setattr(owner, "close_disposable_workspace", forbidden_call("workspace_close"))
    monkeypatch.setattr(inputs["executor_client"], "entity_create_line", forbidden_call("executor"))
    try:
        _execute(inputs)
    except TypeError:
        pytest.fail(
            "R6 causal RED: execute_approved_repair has no direct sealed-R5 validation path"
        )
    except (RepairExecutorAdapterError, VisualSupervisorAdapterError):
        pass
    assert calls == []
    assert owner.close_calls == []
    assert executor.calls == []
