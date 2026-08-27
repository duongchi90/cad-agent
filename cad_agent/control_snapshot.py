"""Pure derived control-plane snapshot validation.

This module never fetches GitHub and never creates execution authority.  Callers
must supply already-fresh-read canonical control evidence.  The returned
snapshot is a deterministic, auditable projection for startup/currentness use.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from cad_agent.drawing_contracts import canonical_json_sha256


CONTROL_SNAPSHOT_SCHEMA_VERSION = "cad-control-snapshot-1.0"
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_OBSERVATION_FIELDS = frozenset(
    {
        "standing_model_comment_id",
        "persistence_comment_id",
        "control_seq",
        "authority_comment_id",
        "consumed_terminal_id",
        "terminal_classification",
        "next_owner",
        "current_main_sha",
        "current_main_tree_sha",
        "active_issue",
        "active_pr",
        "active_pr_base_sha",
        "active_pr_head_sha",
        "active_pr_state",
        "repo_write_allowed",
        "live_allowed",
        "locks",
        "reused_pass_evidence",
        "first_unsatisfied_gate",
        "source_refs",
    }
)
_SNAPSHOT_FIELDS = _OBSERVATION_FIELDS | {
    "schema_version",
    "generated_at",
    "state_sha256",
}


class ControlSnapshotError(ValueError):
    """Raised when derived control state is malformed or self-inconsistent."""


def _fail(message: str) -> None:
    raise ControlSnapshotError(message)


def _closed_mapping(value: Mapping[str, object], *, fields: frozenset[str], name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{name} must be a mapping")
    keys = set(value)
    missing = sorted(fields - keys)
    unexpected = sorted(keys - fields)
    if missing:
        _fail(f"{name} missing required fields: {', '.join(missing)}")
    if unexpected:
        _fail(f"{name} has unexpected fields: {', '.join(unexpected)}")
    return dict(value)


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail(f"{field} must be a positive integer")
    return value


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")
    return value


def _git_sha(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _GIT_SHA.fullmatch(text) is None:
        _fail(f"{field} must be a lowercase 40-character Git SHA")
    return text


def _bool(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"{field} must be boolean")
    return value


def _string_set(value: object, *, field: str, require_nonempty: bool) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{field} must be a list of strings")
    items = list(value)
    if require_nonempty and not items:
        _fail(f"{field} must be non-empty")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        _fail(f"{field} must contain non-empty strings")
    if len(items) != len(set(items)):
        _fail(f"{field} must contain unique values")
    return sorted(items)


def _active_identity(value: object, *, field: str) -> int | str:
    if value == "NONE":
        return "NONE"
    return _positive_int(value, field=field)


def _normalize_observation(observation: Mapping[str, object]) -> dict[str, object]:
    payload = _closed_mapping(observation, fields=_OBSERVATION_FIELDS, name="observation")

    normalized: dict[str, object] = {
        "standing_model_comment_id": _positive_int(
            payload["standing_model_comment_id"], field="standing_model_comment_id"
        ),
        "persistence_comment_id": _positive_int(
            payload["persistence_comment_id"], field="persistence_comment_id"
        ),
        "control_seq": _positive_int(payload["control_seq"], field="control_seq"),
        "authority_comment_id": _positive_int(
            payload["authority_comment_id"], field="authority_comment_id"
        ),
        "consumed_terminal_id": _positive_int(
            payload["consumed_terminal_id"], field="consumed_terminal_id"
        ),
        "terminal_classification": _text(
            payload["terminal_classification"], field="terminal_classification"
        ),
        "next_owner": _text(payload["next_owner"], field="next_owner"),
        "current_main_sha": _git_sha(payload["current_main_sha"], field="current_main_sha"),
        "current_main_tree_sha": _git_sha(
            payload["current_main_tree_sha"], field="current_main_tree_sha"
        ),
        "active_issue": _active_identity(payload["active_issue"], field="active_issue"),
        "active_pr": _active_identity(payload["active_pr"], field="active_pr"),
        "repo_write_allowed": _bool(
            payload["repo_write_allowed"], field="repo_write_allowed"
        ),
        "live_allowed": _bool(payload["live_allowed"], field="live_allowed"),
        "locks": _string_set(payload["locks"], field="locks", require_nonempty=False),
        "reused_pass_evidence": _string_set(
            payload["reused_pass_evidence"],
            field="reused_pass_evidence",
            require_nonempty=False,
        ),
        "first_unsatisfied_gate": _text(
            payload["first_unsatisfied_gate"], field="first_unsatisfied_gate"
        ),
        "source_refs": _string_set(
            payload["source_refs"], field="source_refs", require_nonempty=True
        ),
    }

    active_pr = normalized["active_pr"]
    pr_fields = (
        "active_pr_base_sha",
        "active_pr_head_sha",
        "active_pr_state",
    )
    if active_pr == "NONE":
        for field in pr_fields:
            if payload[field] != "NONE":
                _fail(f"{field} must be NONE when active_pr is NONE")
            normalized[field] = "NONE"
    else:
        normalized["active_pr_base_sha"] = _git_sha(
            payload["active_pr_base_sha"], field="active_pr_base_sha"
        )
        normalized["active_pr_head_sha"] = _git_sha(
            payload["active_pr_head_sha"], field="active_pr_head_sha"
        )
        normalized["active_pr_state"] = _text(
            payload["active_pr_state"], field="active_pr_state"
        )

    return normalized


def _state_material(observation: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema_version": CONTROL_SNAPSHOT_SCHEMA_VERSION,
        **_normalize_observation(observation),
    }


def build_control_snapshot(
    observation: Mapping[str, object], *, generated_at: str
) -> dict[str, object]:
    """Build a deterministic derived snapshot from already-fresh control evidence."""

    timestamp = _text(generated_at, field="generated_at")
    state = _state_material(observation)
    return {
        **state,
        "generated_at": timestamp,
        "state_sha256": canonical_json_sha256(state),
    }


def validate_control_snapshot(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Validate closed shape and recompute deterministic control-state identity."""

    payload = _closed_mapping(snapshot, fields=_SNAPSHOT_FIELDS, name="snapshot")
    if payload["schema_version"] != CONTROL_SNAPSHOT_SCHEMA_VERSION:
        _fail(
            "schema_version must be "
            f"{CONTROL_SNAPSHOT_SCHEMA_VERSION!r}"
        )
    _text(payload["generated_at"], field="generated_at")
    supplied_hash = _text(payload["state_sha256"], field="state_sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", supplied_hash):
        _fail("state_sha256 must be a lowercase SHA-256")

    observation = {field: payload[field] for field in _OBSERVATION_FIELDS}
    state = _state_material(observation)
    expected_hash = canonical_json_sha256(state)
    if supplied_hash != expected_hash:
        _fail("state_sha256 does not match canonical state fields")

    normalized = {
        **state,
        "generated_at": payload["generated_at"],
        "state_sha256": supplied_hash,
    }
    if dict(payload) != normalized:
        _fail("snapshot fields are not in canonical normalized form")
    return normalized
