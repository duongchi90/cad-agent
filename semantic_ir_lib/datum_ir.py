"""Immutable datum records and read-only Primitive IR attachment resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from primitive_ir_lib.models import (
    ArcGeometry,
    CircleGeometry,
    LineGeometry,
    PrimitiveIRDocument,
)

from .dimension_ir import (
    DimensionIRValidationError,
    canonical_json_sha256,
)


class DatumIRValidationError(DimensionIRValidationError):
    """Raised when a datum or attachment cannot be resolved safely."""


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_REF_RE = re.compile(
    r"^(?:datum:[A-Za-z0-9][A-Za-z0-9_.-]*|"
    r"primitive:[A-Za-z0-9][A-Za-z0-9_.-]*:(?:start|end|center))$"
)
_KINDS = {"NAMED_POINT", "NAMED_AXIS", "CENTERLINE", "LEVEL", "ORIGIN"}
_ROLES = {"X_ORIGIN", "Y_ORIGIN", "X_AXIS", "Y_AXIS", "REFERENCE"}
_STATUSES = {"CANDIDATE", "APPROVED", "REJECTED", "UNRESOLVED"}


@dataclass(frozen=True)
class DatumObservation:
    id: str
    kind: str
    view_id: str
    coordinate_role: str
    entity_ref: str
    source_refs: tuple[str, ...]
    status: str
    provenance: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "view_id": self.view_id,
            "coordinate_role": self.coordinate_role,
            "entity_ref": self.entity_ref,
            "source_refs": list(self.source_refs),
            "status": self.status,
            "provenance": self.provenance,
        }


def _identifier(value: str, *, field: str) -> None:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise DatumIRValidationError(f"{field} must be a stable identifier")


def validate_datum_observation(item: DatumObservation) -> None:
    if not isinstance(item, DatumObservation):
        raise DatumIRValidationError("item must be a DatumObservation")
    _identifier(item.id, field="id")
    _identifier(item.view_id, field="view_id")
    if item.kind not in _KINDS:
        raise DatumIRValidationError(f"unsupported datum kind: {item.kind!r}")
    if item.coordinate_role not in _ROLES:
        raise DatumIRValidationError(
            f"unsupported datum coordinate role: {item.coordinate_role!r}"
        )
    if not isinstance(item.entity_ref, str) or _REF_RE.fullmatch(item.entity_ref) is None:
        raise DatumIRValidationError(
            "entity_ref must use datum:NAME or primitive:NAME:start|end|center"
        )
    if item.status not in _STATUSES:
        raise DatumIRValidationError(f"unsupported datum status: {item.status!r}")
    if not item.source_refs or any(not isinstance(value, str) or not value for value in item.source_refs):
        raise DatumIRValidationError("source_refs must contain non-empty strings")
    if not isinstance(item.provenance, str) or not item.provenance.strip():
        raise DatumIRValidationError("provenance must be non-empty")


def _primitive_points(document: PrimitiveIRDocument, primitive_id: str) -> dict[str, tuple[float, float]]:
    primitive = next(
        (item for item in document.primitives if item.id == primitive_id),
        None,
    )
    if primitive is None or primitive.geometry is None:
        raise DatumIRValidationError(f"primitive reference not found: {primitive_id}")
    geometry = primitive.geometry
    if isinstance(geometry, LineGeometry):
        return {
            "start": (float(geometry.start.x), float(geometry.start.y)),
            "end": (float(geometry.end.x), float(geometry.end.y)),
        }
    if isinstance(geometry, CircleGeometry):
        return {"center": (float(geometry.center.x), float(geometry.center.y))}
    if isinstance(geometry, ArcGeometry):
        return {"center": (float(geometry.center.x), float(geometry.center.y))}
    raise DatumIRValidationError(f"primitive has unsupported geometry: {primitive_id}")


def resolve_reference(
    reference: str,
    *,
    datums: Mapping[str, DatumObservation],
    primitive_document: PrimitiveIRDocument,
    view_id: str | None = None,
    _seen: frozenset[str] = frozenset(),
) -> tuple[float, float]:
    """Resolve a symbolic datum/primitive reference without mutating inputs."""
    if not isinstance(reference, str) or _REF_RE.fullmatch(reference) is None:
        raise DatumIRValidationError(f"invalid attachment reference: {reference!r}")
    if reference.startswith("datum:"):
        datum_id = reference.removeprefix("datum:")
        if datum_id in _seen:
            raise DatumIRValidationError(f"recursive datum reference: {datum_id}")
        datum = datums.get(datum_id)
        if datum is None:
            raise DatumIRValidationError(f"datum reference not found: {datum_id}")
        validate_datum_observation(datum)
        if view_id is not None and datum.view_id != view_id:
            raise DatumIRValidationError(
                f"datum {datum_id} belongs to view {datum.view_id}, expected {view_id}"
            )
        return resolve_reference(
            datum.entity_ref,
            datums=datums,
            primitive_document=primitive_document,
            view_id=datum.view_id,
            _seen=_seen | {datum_id},
        )

    _, primitive_id, point_kind = reference.split(":", 2)
    points = _primitive_points(primitive_document, primitive_id)
    try:
        return points[point_kind]
    except KeyError as exc:
        raise DatumIRValidationError(
            f"{point_kind} is not available for primitive {primitive_id}"
        ) from exc


def datum_register_sha256(items: Sequence[DatumObservation]) -> str:
    if not isinstance(items, Sequence):
        raise TypeError("items must be a sequence")
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in items:
        validate_datum_observation(item)
        if item.id in seen:
            raise DatumIRValidationError(f"duplicate datum id: {item.id}")
        seen.add(item.id)
        records.append(item.to_dict())
    records.sort(key=lambda record: str(record["id"]))
    return canonical_json_sha256(
        {"schema_version": "datum-register-1.0", "datums": records}
    )

