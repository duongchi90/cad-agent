"""Offline R6 composition boundary over already accepted owners.

The adapter validates and routes one already-approved repair operation.  It
does not own a CAD transport, approval store, workspace store, revision state,
visual verdict, or publication authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from importlib import import_module
from typing import Any

from cad_agent.candidate_revision import validate_candidate_revision_state
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.repair_authorization import consume_repair_authorization
from cad_agent.repair_operation_contract import (
    REPAIR_OPERATION_SCHEMA_VERSION,
    normalize_repair_operation,
)


R6_RESULT_SCHEMA_VERSION = "r6-repair-executor-result-1.0"


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
    return state


def _validate_scope(context: dict[str, object], operation_payload: dict[str, object]) -> None:
    target = operation_payload["target_handle"]
    if type(target) is not str or target not in context["r3_target_handles"]:
        _fail("BINDING_MISMATCH")
    if target not in context["protected_target_handles"]:
        _fail("BINDING_MISMATCH")


def _validate_workspace(value: object, context: dict[str, object], failure: dict[str, object]) -> Any:
    if type(value) is not _workspace_type(value):
        _fail("WORKSPACE_INVALID")
    for field in (
        "lease_id",
        "candidate_identity",
        "source_identity",
        "source_fingerprint",
        "lifecycle_state",
    ):
        _text(getattr(value, field, None), "WORKSPACE_INVALID")
    if (
        getattr(value, "candidate_identity") != context["candidate_revision_id"]
        or getattr(value, "source_identity") != failure["failure_id"]
        or getattr(value, "source_fingerprint") != failure["failure_sha256"]
        or getattr(value, "lifecycle_state") != "active"
        or getattr(value, "disposable", None) is not True
        or getattr(value, "save_changes", None) is not False
    ):
        _fail("WORKSPACE_INVALID")
    owner = getattr(value, "owner", None)
    if owner is None or not callable(getattr(owner, "close_disposable_workspace", None)):
        _fail("WORKSPACE_INVALID")
    return owner


def _workspace_type(value: object) -> type:
    # Keep the public seam owner-shaped while refusing proxy/subclass values.
    return type(value)


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


def _closure_fields(value: object) -> dict[str, object]:
    if type(value) is not dict:
        _fail("CLOSURE_FAILED")
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
    if set(value) != required or any(type(key) is not str for key in value):
        _fail("CLOSURE_FAILED")
    if value["close_outcome"] != "closed" or value["cleanup_outcome"] != "zero_survivors":
        _fail("CLOSURE_FAILED")
    if value["save_changes"] is not False or value["lifecycle_state"] != "closed":
        _fail("CLOSURE_FAILED")
    return deepcopy(value)


def execute_approved_repair(
    *,
    authorization: object,
    repair_operation: object,
    repair_context: Mapping[str, object],
    candidate_state: Mapping[str, object],
    r5_failure: Mapping[str, object],
    workspace_lease: object,
    executor_client: object,
) -> dict[str, object]:
    """Validate and delegate one approved repair through accepted owners."""

    context = _validate_context(repair_context)
    failure = _validate_r5_failure(r5_failure, context)
    _validate_candidate(candidate_state, context)

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
        owner = _validate_workspace(workspace_lease, context, failure)
    except RepairExecutorAdapterError:
        raise
    except Exception as exc:
        raise RepairExecutorAdapterError("WORKSPACE_INVALID") from exc

    try:
        consume_repair_authorization(
            authorization,
            **_authorization_fields(context, failure, operation_fingerprint),
        )
    except Exception as exc:
        raise RepairExecutorAdapterError("AUTHORIZATION_INVALID") from exc

    try:
        executor_result = _execute_supported_repair_capability(
            executor_client,
            capability=operation_payload["capability"],
            target_handle=operation_payload["target_handle"],
            geometry=operation_payload["geometry"],
            layer=operation_payload["layer"],
        )
    except Exception as exc:
        raise RepairExecutorAdapterError("EXECUTOR_FAILED") from exc

    try:
        closure = owner.close_disposable_workspace(
            workspace_lease,
            candidate_identity=context["candidate_revision_id"],
            source_identity=failure["failure_id"],
            source_fingerprint=failure["failure_sha256"],
        )
        closure = _closure_fields(closure)
    except Exception as exc:
        if isinstance(exc, RepairExecutorAdapterError):
            raise
        raise RepairExecutorAdapterError("CLOSURE_FAILED") from exc

    result: dict[str, object] = {
        "schema_version": R6_RESULT_SCHEMA_VERSION,
        "candidate_revision_id": context["candidate_revision_id"],
        "candidate_revision_sha256": context["candidate_revision_sha256"],
        "r5_failure_id": failure["failure_id"],
        "r5_failure_sha256": failure["failure_sha256"],
        "repair_plan_id": context["repair_plan_id"],
        "repair_plan_sha256": context["repair_plan_sha256"],
        "repair_plan_version": context["repair_plan_version"],
        "repair_operation_contract_version": context["repair_operation_contract_version"],
        "repair_operation_contract_fingerprint": operation_fingerprint,
        "executor_capability": operation_payload["capability"],
        "executor_result_category": "HANDLE_RETURNED" if executor_result else "NO_HANDLE",
        "mutation_outcome": "SUCCESS",
        "closure": closure,
        "requires_new_r5_cycle": True,
    }
    result["result_sha256"] = canonical_json_sha256(result)
    return result


__all__ = ["R6_RESULT_SCHEMA_VERSION", "RepairExecutorAdapterError", "execute_approved_repair"]


