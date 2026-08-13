"""Offline R6 composition boundary over already accepted owners.

The adapter validates and routes one already-approved repair operation.  It
does not own a CAD transport, approval store, workspace store, revision state,
visual verdict, or publication authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from importlib import import_module

from cad_agent.candidate_revision import validate_candidate_revision_state
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.repair_authorization import RepairAuthorization, consume_repair_authorization
from cad_agent.repair_operation_contract import (
    REPAIR_OPERATION_SCHEMA_VERSION,
    normalize_repair_operation,
)

_DOTNET_IPC = import_module("mcp_integration_lib.dotnet_ipc")
DisposableWorkspaceClosure = _DOTNET_IPC.DisposableWorkspaceClosure
DisposableWorkspaceLease = _DOTNET_IPC.DisposableWorkspaceLease
DisposableWorkspaceValidation = _DOTNET_IPC.DisposableWorkspaceValidation
DotNetIPCClient = _DOTNET_IPC.DotNetIPCClient


R6_RESULT_SCHEMA_VERSION = "r6-repair-executor-result-1.1"


def _execute_supported_repair_capability(*args: object, **kwargs: object) -> object:
    """Resolve the already-owned executor without creating a transport edge."""
    executor = import_module(
        "mcp_integration_lib.repair2"
    ).execute_supported_repair_capability
    return executor(*args, **kwargs)


class RepairExecutorAdapterError(ValueError):
    """Privacy-safe categorical refusal from the R6 composition boundary."""

    _CODES = frozenset(
        {
            "MALFORMED",
            "CANDIDATE_INVALID",
            "R5_FAILURE_INVALID",
            "R5_NOT_FAIL",
            "BINDING_MISMATCH",
            "UNSUPPORTED_REPAIR_OPERATION",
            "WORKSPACE_INVALID",
            "AUTHORIZATION_INVALID",
            "EXECUTOR_FAILED",
            "CLOSURE_FAILED",
        }
    )

    def __init__(self, code: str) -> None:
        if type(code) is not str or code not in self._CODES:
            code = "MALFORMED"
        self.code = code
        labels = {
            "CANDIDATE_INVALID": "CANDIDATE_INVALID candidate/state",
            "R5_FAILURE_INVALID": "R5_FAILURE_INVALID r5/failure",
            "R5_NOT_FAIL": "R5_NOT_FAIL verdict",
            "BINDING_MISMATCH": "BINDING_MISMATCH repair/plan/fingerprint/scope",
            "WORKSPACE_INVALID": "WORKSPACE_INVALID workspace/lease/repair",
            "AUTHORIZATION_INVALID": "AUTHORIZATION_INVALID authorization",
            "UNSUPPORTED_REPAIR_OPERATION": "UNSUPPORTED_REPAIR_OPERATION unsupported",
            "EXECUTOR_FAILED": "EXECUTOR_FAILED executor/failure",
            "CLOSURE_FAILED": "CLOSURE_FAILED closure/cleanup/failure",
        }
        super().__init__(labels.get(code, code))


def _fail(code: str) -> None:
    raise RepairExecutorAdapterError(code)


def _closed(value: object, required: set[str], code: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail(code)
    if any(type(key) is not str for key in value):
        _fail(code)
    if set(value) != required:
        _fail(code)
    return deepcopy(value)


def _text(value: object, code: str) -> str:
    if type(value) is not str or not value:
        _fail(code)
    return value


def _sha(value: object, code: str) -> str:
    if type(value) is not str or len(value) != 64:
        _fail(code)
    if any(char not in "0123456789abcdef" for char in value):
        _fail(code)
    return value


def _string_list(value: object, code: str) -> list[str]:
    if type(value) is not list or any(type(item) is not str or not item for item in value):
        _fail(code)
    return list(value)


def _validate_context(value: object) -> dict[str, object]:
    required = {
        "run_id",
        "work_item_id",
        "candidate_revision_id",
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "repair_plan_id",
        "repair_plan_sha256",
        "repair_plan_version",
        "repair_operation_contract_version",
        "repair_operation_contract_fingerprint",
        "r3_target_handles",
        "protected_target_handles",
    }
    context = _closed(value, required, "MALFORMED")
    for field in (
        "run_id",
        "work_item_id",
        "candidate_revision_id",
        "repair_plan_id",
        "repair_plan_version",
        "repair_operation_contract_version",
        "repair_operation_contract_fingerprint",
    ):
        _text(context[field], "MALFORMED")
    _sha(context["candidate_revision_sha256"], "MALFORMED")
    _sha(context["candidate_state_sha256"], "MALFORMED")
    _sha(context["repair_plan_sha256"], "MALFORMED")
    _sha(context["repair_operation_contract_fingerprint"], "MALFORMED")
    if context["repair_operation_contract_version"] != REPAIR_OPERATION_SCHEMA_VERSION:
        _fail("BINDING_MISMATCH")
    _string_list(context["r3_target_handles"], "MALFORMED")
    _string_list(context["protected_target_handles"], "MALFORMED")
    return context


def _validate_r5_failure(value: object, context: dict[str, object]) -> dict[str, object]:
    required = {
        "verdict",
        "failure_id",
        "failure_sha256",
        "candidate_revision_id",
        "candidate_revision_sha256",
        "repair_plan_id",
        "repair_plan_sha256",
        "repair_plan_version",
    }
    failure = _closed(value, required, "R5_FAILURE_INVALID")
    if type(failure["verdict"]) is not str:
        _fail("R5_FAILURE_INVALID")
    if failure["verdict"] != "FAIL":
        _fail("R5_NOT_FAIL")
    for field in ("failure_id", "candidate_revision_id", "repair_plan_id", "repair_plan_version"):
        _text(failure[field], "R5_FAILURE_INVALID")
    for field in ("failure_sha256", "candidate_revision_sha256", "repair_plan_sha256"):
        _sha(failure[field], "R5_FAILURE_INVALID")
    if (
        failure["candidate_revision_id"] != context["candidate_revision_id"]
        or failure["candidate_revision_sha256"] != context["candidate_revision_sha256"]
        or failure["repair_plan_id"] != context["repair_plan_id"]
        or failure["repair_plan_sha256"] != context["repair_plan_sha256"]
        or failure["repair_plan_version"] != context["repair_plan_version"]
    ):
        _fail("BINDING_MISMATCH")
    return failure


def _validate_candidate(value: object, context: dict[str, object]) -> dict[str, object]:
    try:
        state = validate_candidate_revision_state(value)
    except Exception as exc:  # owner errors are categorical at this boundary
        raise RepairExecutorAdapterError("CANDIDATE_INVALID") from exc
    if (
        state.get("state_sha256") != context["candidate_state_sha256"]
        or
        state.get("current_candidate_revision_sha256")
        != context["candidate_revision_sha256"]
    ):
        _fail("BINDING_MISMATCH")
    current = next(
        (
            record
            for record in state["candidate_revisions"]
            if record["candidate_revision_sha256"]
            == state["current_candidate_revision_sha256"]
        ),
        None,
    )
    if current is None or current.get("revision_id") != context["candidate_revision_id"]:
        _fail("BINDING_MISMATCH")
    return current


def _validate_scope(context: dict[str, object], operation_payload: dict[str, object]) -> None:
    target = operation_payload["target_handle"]
    if type(target) is not str or target not in context["r3_target_handles"]:
        _fail("BINDING_MISMATCH")
    if target not in context["protected_target_handles"]:
        _fail("BINDING_MISMATCH")


def _validate_workspace(
    owner: object,
    lease: object,
    context: dict[str, object],
    failure: dict[str, object],
) -> DisposableWorkspaceValidation:
    if type(owner) is not DotNetIPCClient or type(lease) is not DisposableWorkspaceLease:
        _fail("WORKSPACE_INVALID")
    try:
        validation = owner.validate_disposable_workspace(
            lease,
            candidate_identity=context["candidate_revision_id"],
            source_identity=failure["failure_id"],
            source_fingerprint=failure["failure_sha256"],
        )
    except Exception as exc:
        raise RepairExecutorAdapterError("WORKSPACE_INVALID") from exc
    if type(validation) is not DisposableWorkspaceValidation:
        _fail("WORKSPACE_INVALID")
    if (
        type(validation.lease_id) is not str
        or type(validation.candidate_identity) is not str
        or type(validation.source_identity) is not str
        or type(validation.source_fingerprint) is not str
        or type(validation.purpose) is not str
        or type(validation.disposable) is not bool
        or type(validation.save_changes) is not bool
        or type(validation.lifecycle_state) is not str
        or validation.lease_id != lease.lease_id
        or validation.candidate_identity != context["candidate_revision_id"]
        or validation.source_identity != failure["failure_id"]
        or validation.source_fingerprint != failure["failure_sha256"]
        or validation.disposable is not True
        or validation.save_changes is not False
        or validation.lifecycle_state != "active"
    ):
        _fail("WORKSPACE_INVALID")
    return validation


def _authorization_fields(
    context: dict[str, object],
    failure: dict[str, object],
    operation_fingerprint: str,
) -> dict[str, object]:
    return {
        "run_id": context["run_id"],
        "work_item_id": context["work_item_id"],
        "candidate_revision_id": context["candidate_revision_id"],
        "candidate_revision_sha256": context["candidate_revision_sha256"],
        "r5_failure_id": failure["failure_id"],
        "r5_failure_sha256": failure["failure_sha256"],
        "repair_plan_id": context["repair_plan_id"],
        "repair_plan_sha256": context["repair_plan_sha256"],
        "repair_plan_version": context["repair_plan_version"],
        "repair_operation_contract_version": context["repair_operation_contract_version"],
        "repair_operation_contract_fingerprint": operation_fingerprint,
    }


def _closure_fields(
    value: object,
    lease: DisposableWorkspaceLease,
    context: dict[str, object],
    failure: dict[str, object],
) -> dict[str, object]:
    if type(value) is not DisposableWorkspaceClosure:
        _fail("CLOSURE_FAILED")
    if (
        type(value.lease_id) is not str
        or type(value.candidate_identity) is not str
        or type(value.source_identity) is not str
        or type(value.source_fingerprint) is not str
        or type(value.close_outcome) is not str
        or type(value.cleanup_outcome) is not str
        or type(value.save_changes) is not bool
        or type(value.lifecycle_state) is not str
        or value.lease_id != lease.lease_id
        or value.candidate_identity != context["candidate_revision_id"]
        or value.source_identity != failure["failure_id"]
        or value.source_fingerprint != failure["failure_sha256"]
        or value.close_outcome != "closed"
        or value.cleanup_outcome != "zero_survivors"
        or value.save_changes is not False
        or value.lifecycle_state != "closed"
    ):
        _fail("CLOSURE_FAILED")
    return {
        "lease_id": value.lease_id,
        "candidate_identity": value.candidate_identity,
        "source_identity": value.source_identity,
        "source_fingerprint": value.source_fingerprint,
        "close_outcome": value.close_outcome,
        "cleanup_outcome": value.cleanup_outcome,
        "save_changes": value.save_changes,
        "lifecycle_state": value.lifecycle_state,
    }


def _validate_result_closure(value: object) -> None:
    required = {
        "lease_id",
        "candidate_identity",
        "source_identity",
        "source_fingerprint",
        "close_outcome",
        "cleanup_outcome",
        "save_changes",
        "lifecycle_state",
    }
    if type(value) is not dict:
        _fail("CLOSURE_FAILED")
    if any(type(key) is not str for key in value):
        _fail("CLOSURE_FAILED")
    if set(value) != required:
        _fail("CLOSURE_FAILED")
    for field in (
        "lease_id",
        "candidate_identity",
        "source_identity",
        "source_fingerprint",
        "close_outcome",
        "cleanup_outcome",
        "lifecycle_state",
    ):
        _text(value[field], "CLOSURE_FAILED")
    if type(value["save_changes"]) is not bool:
        _fail("CLOSURE_FAILED")
    if (
        value["close_outcome"] != "closed"
        or value["cleanup_outcome"] != "zero_survivors"
        or value["save_changes"] is not False
        or value["lifecycle_state"] != "closed"
    ):
        _fail("CLOSURE_FAILED")


def validate_approved_repair_result(
    result: Mapping[str, object],
    *,
    expected_candidate_revision_id: str | None = None,
    expected_candidate_revision_sha256: str | None = None,
    expected_candidate_artifact_reference_id: str | None = None,
    expected_candidate_artifact_reference_sha256: str | None = None,
    expected_r5_failure_id: str | None = None,
    expected_r5_failure_sha256: str | None = None,
    expected_repair_plan_id: str | None = None,
    expected_repair_plan_sha256: str | None = None,
    expected_repair_plan_version: str | None = None,
    expected_repair_operation_contract_version: str | None = None,
    expected_repair_operation_contract_fingerprint: str | None = None,
) -> dict[str, object]:
    """Validate one already-produced accepted closed R6 repair result."""

    required = {
        "schema_version",
        "candidate_revision_id",
        "candidate_revision_sha256",
        "candidate_artifact_reference_id",
        "candidate_artifact_reference_sha256",
        "r5_failure_id",
        "r5_failure_sha256",
        "repair_plan_id",
        "repair_plan_sha256",
        "repair_plan_version",
        "repair_operation_contract_version",
        "repair_operation_contract_fingerprint",
        "authorization_id",
        "executor_capability",
        "executor_result_category",
        "mutation_outcome",
        "closure",
        "requires_new_r5_cycle",
        "result_sha256",
    }
    if type(result) is not dict:
        _fail("MALFORMED")
    if any(type(key) is not str for key in result):
        _fail("MALFORMED")
    if set(result) != required:
        _fail("MALFORMED")

    for field in (
        "schema_version",
        "candidate_revision_id",
        "candidate_artifact_reference_id",
        "r5_failure_id",
        "repair_plan_id",
        "repair_plan_version",
        "repair_operation_contract_version",
        "authorization_id",
        "executor_capability",
        "executor_result_category",
        "mutation_outcome",
    ):
        _text(result[field], "MALFORMED")
    for field in (
        "candidate_revision_sha256",
        "candidate_artifact_reference_sha256",
        "r5_failure_sha256",
        "repair_plan_sha256",
        "repair_operation_contract_fingerprint",
        "result_sha256",
    ):
        _sha(result[field], "MALFORMED")

    if result["schema_version"] != R6_RESULT_SCHEMA_VERSION:
        _fail("MALFORMED")
    if result["repair_operation_contract_version"] != REPAIR_OPERATION_SCHEMA_VERSION:
        _fail("MALFORMED")
    if result["executor_result_category"] not in {"HANDLE_RETURNED", "NO_HANDLE"}:
        _fail("MALFORMED")
    if result["mutation_outcome"] != "SUCCESS":
        _fail("MALFORMED")
    if type(result["requires_new_r5_cycle"]) is not bool or result["requires_new_r5_cycle"] is not True:
        _fail("MALFORMED")
    closure = result["closure"]
    _validate_result_closure(closure)
    if (
        closure["candidate_identity"] != result["candidate_revision_id"]
        or closure["source_identity"] != result["r5_failure_id"]
        or closure["source_fingerprint"] != result["r5_failure_sha256"]
    ):
        _fail("BINDING_MISMATCH")

    semantic_result = dict(result)
    supplied_sha256 = semantic_result.pop("result_sha256")
    if canonical_json_sha256(semantic_result) != supplied_sha256:
        _fail("MALFORMED")

    expected_text_bindings = (
        (expected_candidate_revision_id, "candidate_revision_id"),
        (expected_candidate_artifact_reference_id, "candidate_artifact_reference_id"),
        (expected_r5_failure_id, "r5_failure_id"),
        (expected_repair_plan_id, "repair_plan_id"),
        (expected_repair_plan_version, "repair_plan_version"),
        (
            expected_repair_operation_contract_version,
            "repair_operation_contract_version",
        ),
    )
    for expected, field in expected_text_bindings:
        if expected is None:
            continue
        _text(expected, "MALFORMED")
        if result[field] != expected:
            _fail("BINDING_MISMATCH")

    expected_sha_bindings = (
        (expected_candidate_revision_sha256, "candidate_revision_sha256"),
        (
            expected_candidate_artifact_reference_sha256,
            "candidate_artifact_reference_sha256",
        ),
        (expected_r5_failure_sha256, "r5_failure_sha256"),
        (expected_repair_plan_sha256, "repair_plan_sha256"),
        (
            expected_repair_operation_contract_fingerprint,
            "repair_operation_contract_fingerprint",
        ),
    )
    for expected, field in expected_sha_bindings:
        if expected is None:
            continue
        _sha(expected, "MALFORMED")
        if result[field] != expected:
            _fail("BINDING_MISMATCH")

    return deepcopy(result)


def execute_approved_repair(
    *,
    authorization: object,
    repair_operation: object,
    repair_context: Mapping[str, object],
    candidate_state: Mapping[str, object],
    r5_failure: Mapping[str, object],
    workspace_owner: DotNetIPCClient,
    workspace_lease: object,
    executor_client: object,
) -> dict[str, object]:
    """Validate and delegate one approved repair through accepted owners."""

    context = _validate_context(repair_context)
    failure = _validate_r5_failure(r5_failure, context)
    current_candidate = _validate_candidate(candidate_state, context)
    candidate_artifacts = current_candidate.get("candidate_artifacts")
    if type(candidate_artifacts) is not dict:
        _fail("CANDIDATE_INVALID")
    candidate_artifact_reference_id = _text(
        candidate_artifacts.get("reference_id"), "CANDIDATE_INVALID"
    )
    candidate_artifact_reference_sha256 = _sha(
        candidate_artifacts.get("reference_sha256"), "CANDIDATE_INVALID"
    )

    try:
        normalized = normalize_repair_operation(repair_operation)
        operation_payload = normalized.as_executor_payload()
    except Exception as exc:
        code = "UNSUPPORTED_REPAIR_OPERATION" if "unsupported" in str(exc).lower() else "MALFORMED"
        raise RepairExecutorAdapterError(code) from exc
    if set(operation_payload) != {"capability", "target_handle", "geometry", "layer"}:
        _fail("MALFORMED")
    _validate_scope(context, operation_payload)
    operation_fingerprint = canonical_json_sha256(operation_payload)
    if context["repair_operation_contract_fingerprint"] != operation_fingerprint:
        _fail("BINDING_MISMATCH")
    try:
        _validate_workspace(workspace_owner, workspace_lease, context, failure)
    except RepairExecutorAdapterError:
        raise
    except Exception as exc:
        raise RepairExecutorAdapterError("WORKSPACE_INVALID") from exc

    try:
        consumed_authorization = consume_repair_authorization(
            authorization,
            **_authorization_fields(context, failure, operation_fingerprint),
        )
    except Exception as exc:
        raise RepairExecutorAdapterError("AUTHORIZATION_INVALID") from exc
    if type(consumed_authorization) is not RepairAuthorization:
        _fail("AUTHORIZATION_INVALID")
    authorization_id = consumed_authorization.authorization_id
    if type(authorization_id) is not str or not authorization_id:
        _fail("AUTHORIZATION_INVALID")

    executor_result: object = None
    executor_error: Exception | None = None
    try:
        executor_result = _execute_supported_repair_capability(
            executor_client,
            capability=operation_payload["capability"],
            target_handle=operation_payload["target_handle"],
            geometry=operation_payload["geometry"],
            layer=operation_payload["layer"],
        )
    except Exception as exc:
        executor_error = exc

    closure: dict[str, object] | None = None
    closure_error: Exception | None = None
    try:
        closed = workspace_owner.close_disposable_workspace(
            workspace_lease,
            candidate_identity=context["candidate_revision_id"],
            source_identity=failure["failure_id"],
            source_fingerprint=failure["failure_sha256"],
        )
        closure = _closure_fields(closed, workspace_lease, context, failure)
    except Exception as exc:
        closure_error = exc

    if closure_error is not None:
        raise RepairExecutorAdapterError("CLOSURE_FAILED") from closure_error
    if executor_error is not None:
        raise RepairExecutorAdapterError("EXECUTOR_FAILED") from executor_error
    assert closure is not None

    result: dict[str, object] = {
        "schema_version": R6_RESULT_SCHEMA_VERSION,
        "candidate_revision_id": context["candidate_revision_id"],
        "candidate_revision_sha256": context["candidate_revision_sha256"],
        "candidate_artifact_reference_id": candidate_artifact_reference_id,
        "candidate_artifact_reference_sha256": candidate_artifact_reference_sha256,
        "r5_failure_id": failure["failure_id"],
        "r5_failure_sha256": failure["failure_sha256"],
        "repair_plan_id": context["repair_plan_id"],
        "repair_plan_sha256": context["repair_plan_sha256"],
        "repair_plan_version": context["repair_plan_version"],
        "repair_operation_contract_version": context["repair_operation_contract_version"],
        "repair_operation_contract_fingerprint": operation_fingerprint,
        "authorization_id": authorization_id,
        "executor_capability": operation_payload["capability"],
        "executor_result_category": "HANDLE_RETURNED" if executor_result else "NO_HANDLE",
        "mutation_outcome": "SUCCESS",
        "closure": closure,
        "requires_new_r5_cycle": True,
    }
    result["result_sha256"] = canonical_json_sha256(result)
    return result


__all__ = [
    "R6_RESULT_SCHEMA_VERSION",
    "RepairExecutorAdapterError",
    "execute_approved_repair",
    "validate_approved_repair_result",
]
