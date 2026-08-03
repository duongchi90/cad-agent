from __future__ import annotations

import copy

import pytest

from primitive_ir_lib.models import (
    Calibration,
    CircleGeometry,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)
from semantic_ir_lib.datum_ir import (
    DatumIRValidationError,
    DatumObservation,
    datum_register_sha256,
    resolve_reference,
)


def _primitive_document() -> PrimitiveIRDocument:
    line = Primitive(
        id="line-001",
        type="line",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=LineGeometry(start=Point2D(10.0, 20.0), end=Point2D(110.0, 20.0)),
    )
    circle = Primitive(
        id="circle-001",
        type="circle",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=CircleGeometry(center=Point2D(50.0, 60.0), radius=5.0),
    )
    return PrimitiveIRDocument(
        source_document=SourceDocument("fixture.png", 0, 100, 100),
        calibration=Calibration("mm", 1.0, (0, 0), "manual_override"),
        primitives=[line, circle],
    )


def _datum(**overrides: object) -> DatumObservation:
    values: dict[str, object] = {
        "id": "DATUM-LEFT",
        "kind": "NAMED_POINT",
        "view_id": "SIDE",
        "coordinate_role": "X_ORIGIN",
        "entity_ref": "primitive:line-001:start",
        "source_refs": ("SRC-001",),
        "status": "APPROVED",
        "provenance": "MANUAL_APPROVED",
    }
    values.update(overrides)
    return DatumObservation(**values)


def test_resolves_line_endpoints_and_circle_center() -> None:
    document = _primitive_document()
    datums = {
        "DATUM-LEFT": _datum(),
        "DATUM-RIGHT": _datum(id="DATUM-RIGHT", entity_ref="primitive:line-001:end"),
    }
    assert resolve_reference("primitive:circle-001:center", datums={}, primitive_document=document) == (50.0, 60.0)
    assert resolve_reference("datum:DATUM-LEFT", datums=datums, primitive_document=document) == (10.0, 20.0)
    assert resolve_reference("datum:DATUM-RIGHT", datums=datums, primitive_document=document) == (110.0, 20.0)


def test_rejects_missing_recursive_and_cross_view_references() -> None:
    document = _primitive_document()
    with pytest.raises(DatumIRValidationError):
        resolve_reference("datum:MISSING", datums={}, primitive_document=document)

    recursive = {
        "A": _datum(id="A", entity_ref="datum:B"),
        "B": _datum(id="B", entity_ref="datum:A"),
    }
    with pytest.raises(DatumIRValidationError):
        resolve_reference("datum:A", datums=recursive, primitive_document=document)

    top = _datum(id="TOP", view_id="TOP")
    with pytest.raises(DatumIRValidationError):
        resolve_reference("datum:TOP", datums={"TOP": top}, primitive_document=document, view_id="SIDE")


def test_register_hash_is_order_independent_and_source_is_unchanged() -> None:
    document = _primitive_document()
    before = copy.deepcopy([primitive.to_dict() for primitive in document.primitives])
    left = _datum()
    right = _datum(id="DATUM-RIGHT", entity_ref="primitive:line-001:end")
    assert datum_register_sha256([left, right]) == datum_register_sha256([right, left])
    resolve_reference("datum:DATUM-LEFT", datums={"DATUM-LEFT": left}, primitive_document=document)
    assert [primitive.to_dict() for primitive in document.primitives] == before


def test_rejects_duplicate_datum_ids_and_invalid_entity_reference() -> None:
    with pytest.raises(DatumIRValidationError):
        datum_register_sha256([_datum(), _datum()])
    with pytest.raises(DatumIRValidationError):
        datum_register_sha256([_datum(entity_ref="point:DATUM-LEFT")])

