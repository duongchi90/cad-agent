"""Deterministic SOL/Web versus local-executor work routing.

This module classifies required evidence surfaces only.  It grants no execution,
repository-write, live, merge, publication, or Human approval authority.
"""

from __future__ import annotations

from collections.abc import Mapping


WORK_ROUTING_SCHEMA_VERSION = "cad-work-routing-1.0"
_ACTION_FIELDS = frozenset(
    {
        "requires_unpushed_local_state",
        "requires_windows_toolchain",
        "requires_autocad",
        "requires_com_rot_ui",
        "requires_netload",
        "requires_live_file_ipc",
        "requires_owner_decision",
        "requires_private_secret",
        "requires_irreversible_approval",
        "web_capable_analysis",
        "preferred_executor",
        "reason",
    }
)
_LOCAL_AUTOCAD_FLAGS = (
    "requires_autocad",
    "requires_com_rot_ui",
    "requires_netload",
    "requires_live_file_ipc",
)
_HUMAN_FLAGS = (
    "requires_owner_decision",
    "requires_private_secret",
    "requires_irreversible_approval",
)


class WorkRoutingError(ValueError):
    """Raised when a proposed work item cannot be classified fail-closed."""


def _fail(message: str) -> None:
    raise WorkRoutingError(message)


def _boolean(payload: Mapping[str, object], field: str) -> bool:
    value = payload[field]
    if not isinstance(value, bool):
        _fail(f"{field} must be boolean")
    return value


def _text(payload: Mapping[str, object], field: str) -> str:
    value = payload[field]
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")
    return value


def classify_work(action: Mapping[str, object]) -> dict[str, str]:
    """Classify one proposed action by the strongest required evidence surface."""

    if not isinstance(action, Mapping):
        _fail("action must be a mapping")
    keys = set(action)
    missing = sorted(_ACTION_FIELDS - keys)
    unexpected = sorted(keys - _ACTION_FIELDS)
    if missing:
        _fail(f"action missing required fields: {', '.join(missing)}")
    if unexpected:
        _fail(f"action has unexpected fields: {', '.join(unexpected)}")

    flags = {field: _boolean(action, field) for field in _ACTION_FIELDS if field.startswith("requires_") or field == "web_capable_analysis"}
    reason = _text(action, "reason")
    _text(action, "preferred_executor")

    if any(flags[field] for field in _HUMAN_FLAGS):
        classification = "HUMAN_ONLY"
        surface = "Human Owner decision/secret/irreversible approval"
    elif any(flags[field] for field in _LOCAL_AUTOCAD_FLAGS):
        classification = "LOCAL_AUTOCAD_REQUIRED"
        surface = "Windows AutoCAD/COM/ROT/UI/NETLOAD/live File-IPC"
    elif flags["requires_windows_toolchain"]:
        classification = "LOCAL_WINDOWS_REQUIRED"
        surface = "Windows-local toolchain/build evidence"
    elif flags["requires_unpushed_local_state"]:
        classification = "LOCAL_REPO_REQUIRED"
        surface = "local checkout/process state unavailable to SOL/Web"
    elif flags["web_capable_analysis"]:
        classification = "WEB_CAPABLE"
        surface = "GitHub/Web reasoning and hosted evidence"
    else:
        _fail(
            "web_capable_analysis is false but no local or Human capability requirement is present"
        )

    return {
        "schema_version": WORK_ROUTING_SCHEMA_VERSION,
        "classification": classification,
        "reason": reason,
        "required_evidence_surface": surface,
    }
