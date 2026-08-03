from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import isclose

import pytest

from semantic_ir_lib.dimension_ir import (
    DimensionIRValidationError,
    DimensionObservation,
    dimension_register_sha256,
    normalize_dimension,
    validate_dimension_observation,
)


def _dimension(**overrides: object) -> DimensionObservation:
    values: dict[str, object] = {
        "id": "DIM-001",
        "value": 500.0,
        "unit": "mm",
        "kind": "horizontal_distance",
        "view_id": "SIDE",
        "from_ref": "datum:DATUM-LEFT",
        "to_ref": "datum:DATUM-RIGHT",
        "role": "driving",
        "status": "APPROVED",
        "provenance": "MANUAL_APPROVED",
    }
    values.update(overrides)
    return DimensionObservation(**values)


def test_engineering_units_normalize_to_millimetres() -> None:
    assert normalize_dimension(500.0, "mm") == 500.0
    assert normalize_dimension(50.0, "cm") == 500.0
    assert normalize_dimension(0.5, "m") == 500.0
    assert isclose(normalize_dimension(19.68503937007874, "in"), 500.0, abs_tol=1e-9)


def test_pixel_unit_and_non_finite_values_are_rejected() -> None:
    with pytest.raises(DimensionIRValidationError):
        normalize_dimension(10.0, "px")
    with pytest.raises(DimensionIRValidationError):
        normalize_dimension(float("nan"), "mm")
    with pytest.raises(DimensionIRValidationError):
        normalize_dimension(float("inf"), "mm")


def test_dimension_validation_rejects_missing_attachment_and_invalid_state() -> None:
    with pytest.raises(DimensionIRValidationError):
        validate_dimension_observation(_dimension(from_ref=""))
    with pytest.raises(DimensionIRValidationError):
        validate_dimension_observation(_dimension(status="UNKNOWN"))
    with pytest.raises(DimensionIRValidationError):
        validate_dimension_observation(_dimension(role="UNKNOWN"))
    with pytest.raises(DimensionIRValidationError):
        validate_dimension_observation(_dimension(from_ref="point:DATUM-LEFT"))


def test_dimension_records_are_frozen_and_register_hash_is_order_independent() -> None:
    first = _dimension(id="DIM-001")
    second = _dimension(id="DIM-002", value=750.0)
    assert dimension_register_sha256([first, second]) == dimension_register_sha256([second, first])
    with pytest.raises(FrozenInstanceError):
        first.value = 501.0  # type: ignore[misc]

