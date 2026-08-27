"""Closed execution envelopes for the existing local Windows executor.

This module validates already-compiled local missions. It grants no repository,
live, merge, publication, or CONTROL_SEQ authority and performs no execution or
persistence itself.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from cad_agent.control_snapshot import (
    ControlSnapshotError,
    validate_control_snapshot,
)
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.mission_contract import MissionContractError, validate_local_mission


LOCAL_EXECUTION_ENVELOPE_SCHEMA_VERSION = "cad-local-execution-envelope-1.0"
LOCAL_MISSION_TERMINAL_SCHEMA_VERSION = "cad-local-mission-terminal-1.0"
ALLOWED_CAPABILITIES = frozenset({"OFFLINE_VERIFY"})
_ENVELOPE_FIELDS = frozenset(
    {
        "schema_version",
        "capability",
        "expected_mission_sha256",
        "mission",
        "control_snapshot",
    }
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class LocalExecutionEnvelopeError(ValueError):
    """Raised when a local execution envelope or terminal is unsafe/invalid."""


def _fail(message: str) -> None:
    raise LocalExecutionEnvelopeError(message)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")
    return value


def _closed_envelope(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("envelope must be a mapping")
    keys = set(value)
    missing = sorted(_ENVELOPE_FIELDS - keys)
    unexpected = sorted(keys - _ENVELOPE_FIELDS)
    if missing:
        _fail(f"envelope missing required fields: {', '.join(missing)}")
    if unexpected:
        _fail(f"envelope has unexpected fields: {', '.join(unexpected)}")
    return dict(value)


def _sha256(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _SHA256.fullmatch(text) is None:
        _fail(f"{field} must be a lowercase SHA-256")
    return text


def _terminal_identity(value: object, *, field: str, result: str) -> str:
    text = _text(value, field=field)
    if text == "UNVALIDATED":
        if result != "FAIL":
            _fail("UNVALIDATED terminal identity is permitted only for FAIL")
        return text
    if field in {"mission_sha256", "control_state_sha256"}:
        if _SHA256.fullmatch(text) is None:
            _fail(f"{field} must be a lowercase SHA-256 or UNVALIDATED")
    elif field == "local_head_sha" and _GIT_SHA.fullmatch(text) is None:
        _fail("local_head_sha must be a lowercase 40-character Git SHA or UNVALIDATED")
    return text


def _exit_code(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{field} must be a non-negative integer")
    return value


def validate_local_execution_envelope(
    envelope: Mapping[str, object],
) -> dict[str, object]:
    """Validate one sealed E1 execution envelope without executing it."""

    payload = _closed_envelope(envelope)
    if payload["schema_version"] != LOCAL_EXECUTION_ENVELOPE_SCHEMA_VERSION:
        _fail(
            "schema_version must be "
            f"{LOCAL_EXECUTION_ENVELOPE_SCHEMA_VERSION!r}"
        )

    capability = _text(payload["capability"], field="capability")
    if capability not in ALLOWED_CAPABILITIES:
        _fail(f"capability {capability!r} is not allowed")

    expected_mission_sha256 = _sha256(
        payload["expected_mission_sha256"], field="expected_mission_sha256"
    )
    mission = payload["mission"]
    control_snapshot = payload["control_snapshot"]
    if not isinstance(mission, Mapping):
        _fail("mission must be a mapping")
    if not isinstance(control_snapshot, Mapping):
        _fail("control_snapshot must be a mapping")

    mission_sha256 = canonical_json_sha256(mission)
    if expected_mission_sha256 != mission_sha256:
        _fail("expected_mission_sha256 does not match canonical mission bytes")

    try:
        validated_snapshot = validate_control_snapshot(control_snapshot)
    except ControlSnapshotError as exc:
        raise LocalExecutionEnvelopeError(
            f"control snapshot validation failed: {exc}"
        ) from exc

    try:
        validated_mission = validate_local_mission(
            mission,
            control_snapshot=validated_snapshot,
        )
    except MissionContractError as exc:
        raise LocalExecutionEnvelopeError(
            f"mission/control snapshot validation failed: {exc}"
        ) from exc

    if validated_mission["routing_classification"] != "LOCAL_REPO_REQUIRED":
        _fail("OFFLINE_VERIFY requires routing_classification LOCAL_REPO_REQUIRED")
    if validated_mission["live_budget"] != 0:
        _fail("OFFLINE_VERIFY requires live_budget == 0")
    if validated_mission["merge_authority"] is not False:
        _fail("merge_authority must be false")
    if validated_mission["publication_authority"] is not False:
        _fail("publication_authority must be false")

    return {
        "schema_version": LOCAL_EXECUTION_ENVELOPE_SCHEMA_VERSION,
        "capability": capability,
        "expected_mission_sha256": mission_sha256,
        "mission": validated_mission,
        "control_snapshot": validated_snapshot,
        "mission_sha256": mission_sha256,
        "control_state_sha256": validated_snapshot["state_sha256"],
    }


def build_local_mission_terminal(
    *,
    mission_sha256: str,
    control_state_sha256: str,
    capability: str,
    local_branch: str,
    local_head_sha: str,
    result: str,
    bootstrap_exit_code: int,
    verify_exit_code: int,
) -> dict[str, object]:
    """Build closed evidence-only terminal output for the E1 executor."""

    normalized_result = _text(result, field="result")
    if normalized_result not in {"PASS", "FAIL"}:
        _fail("result must be PASS or FAIL")

    normalized_capability = _text(capability, field="capability")
    if normalized_capability not in ALLOWED_CAPABILITIES:
        _fail(f"capability {normalized_capability!r} is not allowed")

    normalized_mission_sha256 = _terminal_identity(
        mission_sha256,
        field="mission_sha256",
        result=normalized_result,
    )
    normalized_control_state_sha256 = _terminal_identity(
        control_state_sha256,
        field="control_state_sha256",
        result=normalized_result,
    )
    normalized_branch = _terminal_identity(
        local_branch,
        field="local_branch",
        result=normalized_result,
    )
    normalized_head = _terminal_identity(
        local_head_sha,
        field="local_head_sha",
        result=normalized_result,
    )

    return {
        "schema_version": LOCAL_MISSION_TERMINAL_SCHEMA_VERSION,
        "mission_sha256": normalized_mission_sha256,
        "control_state_sha256": normalized_control_state_sha256,
        "capability": normalized_capability,
        "local_branch": normalized_branch,
        "local_head_sha": normalized_head,
        "result": normalized_result,
        "bootstrap_exit_code": _exit_code(
            bootstrap_exit_code, field="bootstrap_exit_code"
        ),
        "verify_exit_code": _exit_code(verify_exit_code, field="verify_exit_code"),
        "live_result": "NOT_RUN",
        "merge_authority": False,
        "publication_authority": False,
    }
