"""Closed long-horizon local mission contracts.

The compiler materializes already-authorized SOL decisions.  It does not mint
CONTROL_SEQ, widen write/live scope, merge, publish, or create Human approval.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cad_agent.control_snapshot import ControlSnapshotError, validate_control_snapshot


MISSION_SCHEMA_VERSION = "cad-local-mission-1.0"
_REQUEST_FIELDS = frozenset(
    {
        "goal",
        "outcome_predicate",
        "repo_mutation",
        "write_set",
        "forbidden_paths",
        "accepted_evidence",
        "pre_execution_closure",
        "causal_family",
        "causal_budget",
        "allowed_temp_repairs",
        "live_budget",
        "expensive_budget",
        "acceptance_oracle",
        "hard_handoff_conditions",
        "cleanup_requirements",
        "terminal_fields",
        "human_relay_required",
        "merge_authority",
        "publication_authority",
    }
)
_CONTROL_FIELDS = (
    "control_seq",
    "authority_comment_id",
    "consumed_terminal_id",
    "current_main_sha",
    "current_main_tree_sha",
    "active_issue",
    "active_pr",
    "active_pr_base_sha",
    "active_pr_head_sha",
    "active_pr_state",
    "repo_write_allowed",
    "live_allowed",
    "next_owner",
)
_MISSION_FIELDS = _REQUEST_FIELDS | frozenset(_CONTROL_FIELDS) | {
    "schema_version",
    "control_state_sha256",
    "routing_classification",
    "routing_reason",
    "required_evidence_surface",
}
_ALLOWED_ROUTING = {
    "LOCAL_REPO_REQUIRED",
    "LOCAL_WINDOWS_REQUIRED",
    "LOCAL_AUTOCAD_REQUIRED",
}


class MissionContractError(ValueError):
    """Raised when a local mission would violate closed authority/scope rules."""


def _fail(message: str) -> None:
    raise MissionContractError(message)


def _closed_mapping(
    value: Mapping[str, object], *, fields: frozenset[str], name: str
) -> dict[str, object]:
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


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")
    return value


def _bool(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"{field} must be boolean")
    return value


def _budget(value: object, *, field: str, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail(f"{field} must be an integer >= {minimum}")
    if maximum is not None and value > maximum:
        _fail(f"{field} must be <= {maximum}")
    return value


def _string_list(
    value: object, *, field: str, require_nonempty: bool
) -> list[str]:
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


def _accepted_evidence(value: object) -> list[dict[str, str]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("accepted_evidence must be a list")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            _fail(f"accepted_evidence[{index}] must be a mapping")
        if set(item) != {"evidence_ref", "source_ref"}:
            _fail(
                f"accepted_evidence[{index}] must contain evidence_ref and source_ref only"
            )
        evidence_ref = _text(item["evidence_ref"], field=f"accepted_evidence[{index}].evidence_ref")
        source_ref = _text(item["source_ref"], field=f"accepted_evidence[{index}].source_ref")
        if evidence_ref in seen:
            _fail("accepted_evidence evidence_ref values must be unique")
        seen.add(evidence_ref)
        normalized.append({"evidence_ref": evidence_ref, "source_ref": source_ref})
    return sorted(normalized, key=lambda item: item["evidence_ref"])


def _normalize_request(request: Mapping[str, object]) -> dict[str, object]:
    payload = _closed_mapping(request, fields=_REQUEST_FIELDS, name="request")
    repo_mutation = _bool(payload["repo_mutation"], field="repo_mutation")
    write_set = _string_list(
        payload["write_set"], field="write_set", require_nonempty=repo_mutation
    )
    normalized = {
        "goal": _text(payload["goal"], field="goal"),
        "outcome_predicate": _text(
            payload["outcome_predicate"], field="outcome_predicate"
        ),
        "repo_mutation": repo_mutation,
        "write_set": write_set,
        "forbidden_paths": _string_list(
            payload["forbidden_paths"], field="forbidden_paths", require_nonempty=False
        ),
        "accepted_evidence": _accepted_evidence(payload["accepted_evidence"]),
        "pre_execution_closure": _text(
            payload["pre_execution_closure"], field="pre_execution_closure"
        ),
        "causal_family": _text(payload["causal_family"], field="causal_family"),
        "causal_budget": _budget(
            payload["causal_budget"], field="causal_budget", minimum=1, maximum=5
        ),
        "allowed_temp_repairs": _string_list(
            payload["allowed_temp_repairs"],
            field="allowed_temp_repairs",
            require_nonempty=False,
        ),
        "live_budget": _budget(payload["live_budget"], field="live_budget"),
        "expensive_budget": _budget(
            payload["expensive_budget"], field="expensive_budget"
        ),
        "acceptance_oracle": _text(
            payload["acceptance_oracle"], field="acceptance_oracle"
        ),
        "hard_handoff_conditions": _string_list(
            payload["hard_handoff_conditions"],
            field="hard_handoff_conditions",
            require_nonempty=True,
        ),
        "cleanup_requirements": _string_list(
            payload["cleanup_requirements"],
            field="cleanup_requirements",
            require_nonempty=True,
        ),
        "terminal_fields": _string_list(
            payload["terminal_fields"], field="terminal_fields", require_nonempty=True
        ),
        "human_relay_required": _bool(
            payload["human_relay_required"], field="human_relay_required"
        ),
        "merge_authority": _bool(payload["merge_authority"], field="merge_authority"),
        "publication_authority": _bool(
            payload["publication_authority"], field="publication_authority"
        ),
    }
    if set(normalized["write_set"]) & set(normalized["forbidden_paths"]):
        _fail("write_set and forbidden_paths must be disjoint")
    if normalized["human_relay_required"]:
        _fail("human_relay_required must be false for routine local missions")
    if normalized["merge_authority"]:
        _fail("merge_authority must be false")
    if normalized["publication_authority"]:
        _fail("publication_authority must be false")
    return normalized


def _routing_fields(routing: Mapping[str, object]) -> tuple[str, str, str]:
    if not isinstance(routing, Mapping):
        _fail("routing must be a mapping")
    required = {
        "schema_version",
        "classification",
        "reason",
        "required_evidence_surface",
    }
    if set(routing) != required:
        _fail("routing must be the closed work-routing result shape")
    classification = _text(routing["classification"], field="routing.classification")
    if classification == "WEB_CAPABLE":
        _fail("WEB_CAPABLE work must remain with SOL/Web and cannot compile to Luna")
    if classification == "HUMAN_ONLY":
        _fail("HUMAN_ONLY work cannot compile to a local executor mission")
    if classification not in _ALLOWED_ROUTING:
        _fail("routing.classification is unsupported")
    return (
        classification,
        _text(routing["reason"], field="routing.reason"),
        _text(
            routing["required_evidence_surface"],
            field="routing.required_evidence_surface",
        ),
    )


def _validated_snapshot(control_snapshot: Mapping[str, object]) -> dict[str, object]:
    try:
        return validate_control_snapshot(control_snapshot)
    except ControlSnapshotError as exc:
        raise MissionContractError(f"control snapshot is invalid: {exc}") from exc


def compile_local_mission(
    control_snapshot: Mapping[str, object],
    routing: Mapping[str, object],
    request: Mapping[str, object],
) -> dict[str, object]:
    """Compile one closed Luna/local mission from validated SOL-owned inputs."""

    snapshot = _validated_snapshot(control_snapshot)
    classification, reason, surface = _routing_fields(routing)
    normalized = _normalize_request(request)

    if normalized["repo_mutation"] and not snapshot["repo_write_allowed"]:
        _fail("repo_write_allowed is false for requested repository mutation")
    if normalized["live_budget"] > 0 and not snapshot["live_allowed"]:
        _fail("live_allowed is false for non-zero live_budget")

    mission: dict[str, object] = {
        "schema_version": MISSION_SCHEMA_VERSION,
        "control_state_sha256": snapshot["state_sha256"],
        "routing_classification": classification,
        "routing_reason": reason,
        "required_evidence_surface": surface,
        **{field: snapshot[field] for field in _CONTROL_FIELDS},
        **normalized,
    }
    if mission["next_owner"] != "SOL":
        _fail("next_owner must be SOL for this mission contract")
    return mission


def validate_local_mission(
    mission: Mapping[str, object], *, control_snapshot: Mapping[str, object]
) -> dict[str, object]:
    """Validate a compiled mission against the exact current control snapshot."""

    payload = _closed_mapping(mission, fields=_MISSION_FIELDS, name="mission")
    if payload["schema_version"] != MISSION_SCHEMA_VERSION:
        _fail(f"schema_version must be {MISSION_SCHEMA_VERSION!r}")
    snapshot = _validated_snapshot(control_snapshot)
    if payload["control_state_sha256"] != snapshot["state_sha256"]:
        _fail("mission does not match the supplied control snapshot state_sha256")
    for field in _CONTROL_FIELDS:
        if payload[field] != snapshot[field]:
            _fail(f"mission {field} does not match the supplied control snapshot")

    normalized_request = _normalize_request(
        {field: payload[field] for field in _REQUEST_FIELDS}
    )
    classification = _text(
        payload["routing_classification"], field="routing_classification"
    )
    if classification not in _ALLOWED_ROUTING:
        _fail("routing_classification must require a local executor")
    if normalized_request["repo_mutation"] and not snapshot["repo_write_allowed"]:
        _fail("repo_write_allowed is false for requested repository mutation")
    if normalized_request["live_budget"] > 0 and not snapshot["live_allowed"]:
        _fail("live_allowed is false for non-zero live_budget")
    if payload["next_owner"] != "SOL":
        _fail("next_owner must be SOL")

    canonical = {
        "schema_version": MISSION_SCHEMA_VERSION,
        "control_state_sha256": snapshot["state_sha256"],
        "routing_classification": classification,
        "routing_reason": _text(payload["routing_reason"], field="routing_reason"),
        "required_evidence_surface": _text(
            payload["required_evidence_surface"], field="required_evidence_surface"
        ),
        **{field: snapshot[field] for field in _CONTROL_FIELDS},
        **normalized_request,
    }
    if dict(payload) != canonical:
        _fail("mission is not in canonical normalized form")
    return canonical
