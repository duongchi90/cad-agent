"""Immutable, hash-bound Dimension IR records for the M3 gate."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from collections.abc import Mapping, Sequence


class DimensionIRValidationError(ValueError):
    """Raised when an authoritative dimension cannot be validated safely."""


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_REF_RE = re.compile(
    r"^(?:datum:[A-Za-z0-9][A-Za-z0-9_.-]*|"
    r"primitive:[A-Za-z0-9][A-Za-z0-9_.-]*:(?:start|end|center))$"
)
_UNIT_FACTORS_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}
_KINDS = {
    "horizontal_distance",
    "vertical_distance",
    "aligned_distance",
    "angular",
    "radial",
    "diameter",
    "chain",
    "baseline",
    "ordinate",
}
_ROLES = {"driving", "reference", "inspection"}
_STATUSES = {"CANDIDATE", "APPROVED", "REJECTED", "UNRESOLVED"}


@dataclass(frozen=True)
class DimensionObservation:
    id: str
    value: float
    unit: str
    kind: str
    view_id: str
    from_ref: str
    to_ref: str
    role: str
    status: str
    provenance: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "value": self.value,
            "unit": self.unit,
            "kind": self.kind,
            "view_id": self.view_id,
            "from_ref": self.from_ref,
            "to_ref": self.to_ref,
            "role": self.role,
            "status": self.status,
            "provenance": self.provenance,
        }


def canonical_json_sha256(payload: Mapping[str, object]) -> str:
    """Hash a mapping using the repository's deterministic JSON convention."""
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TypeError("payload must be JSON serializable") from exc
    return hashlib.sha256(encoded).hexdigest()


def normalize_dimension(value: float, unit: str) -> float:
    """Convert one finite positive engineering value to millimetres."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DimensionIRValidationError("dimension value must be numeric")
    if not math.isfinite(float(value)) or float(value) <= 0:
        raise DimensionIRValidationError("dimension value must be finite and positive")
    if unit not in _UNIT_FACTORS_MM:
        raise DimensionIRValidationError(
            f"dimension unit must be one of {sorted(_UNIT_FACTORS_MM)}, got {unit!r}"
        )
    return float(value) * _UNIT_FACTORS_MM[unit]


def _require_identifier(value: str, *, field: str) -> None:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise DimensionIRValidationError(f"{field} must be a stable identifier")


def _require_reference(value: str, *, field: str) -> None:
    if not isinstance(value, str) or _REF_RE.fullmatch(value) is None:
        raise DimensionIRValidationError(
            f"{field} must use datum:NAME or primitive:NAME:start|end|center"
        )


def validate_dimension_observation(item: DimensionObservation) -> None:
    """Validate one dimension without changing the caller's object."""
    if not isinstance(item, DimensionObservation):
        raise DimensionIRValidationError("item must be a DimensionObservation")
    _require_identifier(item.id, field="id")
    normalize_dimension(item.value, item.unit)
    if item.kind not in _KINDS:
        raise DimensionIRValidationError(f"unsupported dimension kind: {item.kind!r}")
    _require_identifier(item.view_id, field="view_id")
    _require_reference(item.from_ref, field="from_ref")
    _require_reference(item.to_ref, field="to_ref")
    if item.role not in _ROLES:
        raise DimensionIRValidationError(f"unsupported dimension role: {item.role!r}")
    if item.status not in _STATUSES:
        raise DimensionIRValidationError(f"unsupported dimension status: {item.status!r}")
    if not isinstance(item.provenance, str) or not item.provenance.strip():
        raise DimensionIRValidationError("provenance must be non-empty")


def dimension_register_sha256(items: Sequence[DimensionObservation]) -> str:
    """Hash a validated register in stable ID order."""
    if not isinstance(items, Sequence):
        raise TypeError("items must be a sequence")
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in items:
        validate_dimension_observation(item)
        if item.id in seen:
            raise DimensionIRValidationError(f"duplicate dimension id: {item.id}")
        seen.add(item.id)
        records.append(item.to_dict())
    records.sort(key=lambda record: str(record["id"]))
    return canonical_json_sha256(
        {"schema_version": "dimension-register-1.0", "dimensions": records}
    )

