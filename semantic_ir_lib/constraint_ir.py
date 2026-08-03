"""Immutable, hash-bound Constraint IR records for the M3 gate."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .dimension_ir import DimensionIRValidationError, canonical_json_sha256


class ConstraintIRValidationError(DimensionIRValidationError):
    """Raised when a constraint or approval binding is unsafe to use."""


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_REF_RE = re.compile(
    r"^(?:datum|dimension|primitive):[A-Za-z0-9][A-Za-z0-9_.-]*"
    r"(?::(?:start|end|center))?$"
)
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_UNITS = {"mm", "cm", "m", "in", "deg"}
_UNIT_FACTORS_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}
_KINDS = {
    "coincident",
    "horizontal",
    "vertical",
    "parallel",
    "perpendicular",
    "collinear",
    "equal_length",
    "distance",
    "angle",
    "radius",
    "diameter",
    "chain",
    "baseline",
    "ordinate",
}
_STATUSES = {"CANDIDATE", "APPROVED", "REJECTED", "UNRESOLVED"}
SUPPORTED_SOLVER_CONSTRAINT_KINDS = frozenset(
    {"parallel", "perpendicular", "equal_length", "coincident", "collinear"}
)
_SCALAR_KINDS = {"distance", "angle", "radius", "diameter"}
_POSITIVE_SCALAR_KINDS = {"distance", "radius", "diameter"}


@dataclass(frozen=True)
class ConstraintObservation:
    id: str
    kind: str
    refs: tuple[str, ...]
    value: float | None = None
    unit: str | None = None
    tolerance_mm: float = 0.0
    source_refs: tuple[str, ...] = ()
    provenance: str = ""
    status: str = "CANDIDATE"

    def to_dict(self) -> dict[str, object]:
        record: dict[str, object] = {
            "id": self.id,
            "kind": self.kind,
            "refs": list(self.refs),
            "tolerance_mm": self.tolerance_mm,
            "source_refs": list(self.source_refs),
            "provenance": self.provenance,
            "status": self.status,
        }
        if self.value is not None:
            record["value"] = self.value
        if self.unit is not None:
            record["unit"] = self.unit
        return record


@dataclass(frozen=True)
class ApprovalRegister:
    setup_evidence_sha256: str
    dimensions_sha256: str
    datums_sha256: str
    constraints_sha256: str
    approval_reference: str
    approved_by: str
    approved_ids: tuple[str, ...]
    rejected_ids: tuple[str, ...]
    policy_version: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "approval-register-1.0",
            "setup_evidence_sha256": self.setup_evidence_sha256,
            "dimensions_sha256": self.dimensions_sha256,
            "datums_sha256": self.datums_sha256,
            "constraints_sha256": self.constraints_sha256,
            "approval_reference": self.approval_reference,
            "approved_by": self.approved_by,
            "approved_ids": list(self.approved_ids),
            "rejected_ids": list(self.rejected_ids),
            "policy_version": self.policy_version,
        }


def _require_identifier(value: str, *, field: str) -> None:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise ConstraintIRValidationError(f"{field} must be a stable identifier")


def _require_reference(value: str, *, field: str) -> None:
    if not isinstance(value, str) or _REF_RE.fullmatch(value) is None:
        raise ConstraintIRValidationError(
            f"{field} must use datum:NAME, dimension:NAME, or primitive:NAME"
        )


def _require_nonempty_strings(values: Iterable[str], *, field: str) -> None:
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise ConstraintIRValidationError(f"{field}[{index}] must be non-empty")


def normalize_constraint_value(value: float, unit: str) -> float:
    """Normalize an engineering scalar to mm; preserve angular values in degrees."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConstraintIRValidationError("constraint value must be numeric")
    if not math.isfinite(float(value)):
        raise ConstraintIRValidationError("constraint value must be finite")
    if unit not in _UNITS:
        raise ConstraintIRValidationError(f"unsupported constraint unit: {unit!r}")
    if unit == "deg":
        return float(value)
    return float(value) * _UNIT_FACTORS_MM[unit]


def validate_constraint_observation(item: ConstraintObservation) -> None:
    """Validate one immutable constraint without modifying caller-owned data."""
    if not isinstance(item, ConstraintObservation):
        raise ConstraintIRValidationError("item must be a ConstraintObservation")
    _require_identifier(item.id, field="id")
    if item.kind not in _KINDS:
        raise ConstraintIRValidationError(f"unsupported constraint kind: {item.kind!r}")
    if not isinstance(item.refs, Sequence) or len(item.refs) < 2:
        raise ConstraintIRValidationError("refs must contain at least two references")
    for index, reference in enumerate(item.refs):
        _require_reference(reference, field=f"refs[{index}]")
    if item.kind in _SCALAR_KINDS and item.value is None:
        raise ConstraintIRValidationError(f"{item.kind} requires value and unit")
    if (item.value is None) != (item.unit is None):
        raise ConstraintIRValidationError("value and unit must be provided together")
    if item.value is not None and item.unit is not None:
        normalize_constraint_value(item.value, item.unit)
        if item.kind == "angle" and item.unit != "deg":
            raise ConstraintIRValidationError("angle constraints require unit 'deg'")
        if item.kind != "angle" and item.unit == "deg":
            raise ConstraintIRValidationError(
                f"{item.kind} constraints require an engineering unit"
            )
        if item.kind in _POSITIVE_SCALAR_KINDS and item.value <= 0:
            raise ConstraintIRValidationError(
                f"{item.kind} value must be finite and positive"
            )
    if isinstance(item.tolerance_mm, bool) or not isinstance(item.tolerance_mm, (int, float)):
        raise ConstraintIRValidationError("tolerance must be numeric")
    if not math.isfinite(float(item.tolerance_mm)) or item.tolerance_mm < 0:
        raise ConstraintIRValidationError("tolerance must be finite and non-negative")
    _require_nonempty_strings(item.source_refs, field="source_refs")
    if not isinstance(item.provenance, str) or not item.provenance.strip():
        raise ConstraintIRValidationError("provenance must be non-empty")
    if item.status not in _STATUSES:
        raise ConstraintIRValidationError(f"unsupported constraint status: {item.status!r}")


def constraint_register_sha256(items: Sequence[ConstraintObservation]) -> str:
    """Hash a validated constraint register in stable ID order."""
    if not isinstance(items, Sequence):
        raise TypeError("items must be a sequence")
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in items:
        validate_constraint_observation(item)
        if item.id in seen:
            raise ConstraintIRValidationError(f"duplicate constraint id: {item.id}")
        seen.add(item.id)
        records.append(item.to_dict())
    records.sort(key=lambda record: str(record["id"]))
    return canonical_json_sha256(
        {"schema_version": "constraint-register-1.0", "constraints": records}
    )


def _require_hash(value: str, *, field: str) -> None:
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise ConstraintIRValidationError(f"{field} must be a lowercase SHA-256 hash")


def _validate_approval_register(item: ApprovalRegister) -> None:
    if not isinstance(item, ApprovalRegister):
        raise ConstraintIRValidationError("approval must be an ApprovalRegister")
    for field in (
        "setup_evidence_sha256",
        "dimensions_sha256",
        "datums_sha256",
        "constraints_sha256",
    ):
        _require_hash(getattr(item, field), field=field)
    for field in ("approval_reference", "approved_by", "policy_version"):
        value = getattr(item, field)
        if not isinstance(value, str) or not value.strip():
            raise ConstraintIRValidationError(f"{field} must be non-empty")
    _require_nonempty_strings(item.approved_ids, field="approved_ids")
    _require_nonempty_strings(item.rejected_ids, field="rejected_ids")
    if set(item.approved_ids) & set(item.rejected_ids):
        raise ConstraintIRValidationError("approved_ids and rejected_ids must not overlap")


def _blocker(code: str, path: str, expected: object, actual: object) -> dict[str, object]:
    return {
        "code": code,
        "path": path,
        "expected": expected,
        "actual": actual,
        "severity": "BLOCKER",
    }


def validate_approval_register(
    approval: ApprovalRegister,
    *,
    setup_evidence_sha256: str,
    dimensions_sha256: str,
    datums_sha256: str,
    constraints_sha256: str,
    required_ids: Iterable[str] = (),
) -> tuple[dict[str, object], ...]:
    """Return deterministic blockers for stale hashes or unapproved inputs."""
    _validate_approval_register(approval)
    for field, value in (
        ("setup_evidence_sha256", setup_evidence_sha256),
        ("dimensions_sha256", dimensions_sha256),
        ("datums_sha256", datums_sha256),
        ("constraints_sha256", constraints_sha256),
    ):
        _require_hash(value, field=field)

    expected_values = {
        "setup_evidence_sha256": setup_evidence_sha256,
        "dimensions_sha256": dimensions_sha256,
        "datums_sha256": datums_sha256,
        "constraints_sha256": constraints_sha256,
    }
    blockers: list[dict[str, object]] = []
    for field in expected_values:
        expected = expected_values[field]
        actual = getattr(approval, field)
        if actual != expected:
            blockers.append(_blocker("input_hash_mismatch", field, expected, actual))

    approved_ids = set(approval.approved_ids)
    rejected_ids = set(approval.rejected_ids)
    for record_id in sorted(set(required_ids)):
        if record_id not in approved_ids:
            code = "constraint_rejected" if record_id in rejected_ids else "constraint_not_approved"
            blockers.append(_blocker(code, "approved_ids", record_id, sorted(approved_ids)))
    return tuple(blockers)
