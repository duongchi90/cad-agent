"""Deterministic matching for previously learned execution failure families.

The registry is descriptive only.  It returns a probe identifier and escalation
boundary; it never executes commands, repairs code, authorizes live work, or
mutates repository/system state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


FAILURE_FAMILY_SCHEMA_VERSION = "cad-failure-family-1.0"
_FAMILY_FIELDS = frozenset(
    {
        "schema_version",
        "family_id",
        "causal_layer",
        "required_signatures",
        "allowed_additional_signatures",
        "probe_id",
        "safe_auto_repair",
        "hard_escalation",
        "source_refs",
    }
)


class FailureRegistryError(ValueError):
    """Raised when failure knowledge is malformed or ambiguous."""


def _fail(message: str) -> None:
    raise FailureRegistryError(message)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")
    return value


def _string_set(
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


def validate_failure_family(payload: Mapping[str, object]) -> dict[str, object]:
    """Validate one closed, non-authoritative failure-family record."""

    if not isinstance(payload, Mapping):
        _fail("failure family must be a mapping")
    keys = set(payload)
    missing = sorted(_FAMILY_FIELDS - keys)
    unexpected = sorted(keys - _FAMILY_FIELDS)
    if missing:
        _fail(f"failure family missing required fields: {', '.join(missing)}")
    if unexpected:
        _fail(f"failure family has unexpected fields: {', '.join(unexpected)}")
    if payload["schema_version"] != FAILURE_FAMILY_SCHEMA_VERSION:
        _fail(f"schema_version must be {FAILURE_FAMILY_SCHEMA_VERSION!r}")

    required = _string_set(
        payload["required_signatures"],
        field="required_signatures",
        require_nonempty=True,
    )
    allowed = _string_set(
        payload["allowed_additional_signatures"],
        field="allowed_additional_signatures",
        require_nonempty=False,
    )
    overlap = set(required) & set(allowed)
    if overlap:
        _fail("required_signatures and allowed_additional_signatures must be disjoint")

    return {
        "schema_version": FAILURE_FAMILY_SCHEMA_VERSION,
        "family_id": _text(payload["family_id"], field="family_id"),
        "causal_layer": _text(payload["causal_layer"], field="causal_layer"),
        "required_signatures": required,
        "allowed_additional_signatures": allowed,
        "probe_id": _text(payload["probe_id"], field="probe_id"),
        "safe_auto_repair": _text(
            payload["safe_auto_repair"], field="safe_auto_repair"
        ),
        "hard_escalation": _text(
            payload["hard_escalation"], field="hard_escalation"
        ),
        "source_refs": _string_set(
            payload["source_refs"], field="source_refs", require_nonempty=True
        ),
    }


def match_failure_family(
    signatures: Sequence[str], families: Sequence[Mapping[str, object]]
) -> dict[str, object] | None:
    """Return one unambiguous exact-family match, otherwise fail closed/no match."""

    observed = _string_set(signatures, field="signatures", require_nonempty=True)
    observed_set = set(observed)
    if isinstance(families, (str, bytes)) or not isinstance(families, Sequence):
        _fail("families must be a list")

    matches: list[dict[str, object]] = []
    for raw_family in families:
        family = validate_failure_family(raw_family)
        required = set(family["required_signatures"])
        allowed = required | set(family["allowed_additional_signatures"])
        if required <= observed_set <= allowed:
            matches.append(family)
    if len(matches) > 1:
        _fail("failure signatures match multiple families ambiguously")
    return matches[0] if matches else None


def recommended_probe(family: Mapping[str, object]) -> str:
    """Return the reviewed probe identifier without executing it."""

    return str(validate_failure_family(family)["probe_id"])
