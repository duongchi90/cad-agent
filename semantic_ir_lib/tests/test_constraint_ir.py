from __future__ import annotations

import copy

import pytest

from semantic_ir_lib.constraint_ir import (
    ApprovalRegister,
    ConstraintIRValidationError,
    ConstraintObservation,
    constraint_register_sha256,
    validate_approval_register,
    validate_constraint_observation,
)


KINDS = (
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
)


def _constraint(
    constraint_id: str = "CON-001",
    *,
    kind: str = "parallel",
    refs: tuple[str, ...] = ("primitive:line-001", "primitive:line-002"),
    value: float | None = None,
    unit: str | None = None,
    tolerance_mm: float = 0.01,
    status: str = "APPROVED",
) -> ConstraintObservation:
    return ConstraintObservation(
        id=constraint_id,
        kind=kind,
        refs=refs,
        value=value,
        unit=unit,
        tolerance_mm=tolerance_mm,
        source_refs=("SRC-001",),
        provenance="MANUAL_APPROVED",
        status=status,
    )


def _approval(*, constraints_hash: str, approved_ids: tuple[str, ...] = ("CON-001",)) -> ApprovalRegister:
    return ApprovalRegister(
        setup_evidence_sha256="1" * 64,
        dimensions_sha256="2" * 64,
        datums_sha256="3" * 64,
        constraints_sha256=constraints_hash,
        approval_reference="M3-FIXTURE-001",
        approved_by="ENGINEER",
        approved_ids=approved_ids,
        rejected_ids=(),
        policy_version="dimension-first-policy-1.0",
    )


@pytest.mark.parametrize("kind", KINDS)
def test_supported_constraint_kinds_validate(kind: str):
    value = 90.0 if kind == "angle" else (25.0 if kind in {"distance", "radius", "diameter"} else None)
    unit = "deg" if kind == "angle" else ("mm" if value is not None else None)
    item = _constraint(kind=kind, value=value, unit=unit)

    validate_constraint_observation(item)


def test_constraint_validation_rejects_bad_arity_value_pair_and_pixel_units():
    with pytest.raises(ConstraintIRValidationError, match="refs"):
        validate_constraint_observation(_constraint(refs=("primitive:line-001",)))

    with pytest.raises(ConstraintIRValidationError, match="value and unit"):
        validate_constraint_observation(_constraint(value=10.0))

    with pytest.raises(ConstraintIRValidationError, match="value and unit"):
        validate_constraint_observation(_constraint(unit="mm"))

    with pytest.raises(ConstraintIRValidationError, match="unsupported constraint unit"):
        validate_constraint_observation(_constraint(value=10.0, unit="px"))


def test_constraint_validation_rejects_non_finite_and_negative_tolerances():
    with pytest.raises(ConstraintIRValidationError, match="tolerance"):
        validate_constraint_observation(_constraint(tolerance_mm=-0.01))

    with pytest.raises(ConstraintIRValidationError, match="tolerance"):
        validate_constraint_observation(_constraint(tolerance_mm=float("inf")))


def test_register_hash_is_order_independent_and_rejects_duplicate_ids():
    first = _constraint("CON-001")
    second = _constraint("CON-002", kind="perpendicular")
    before = copy.deepcopy(first)

    left = constraint_register_sha256([first, second])
    right = constraint_register_sha256([second, first])

    assert left == right
    assert first == before

    with pytest.raises(ConstraintIRValidationError, match="duplicate constraint id"):
        constraint_register_sha256([first, first])


def test_approval_binding_reports_hash_mismatch_and_unapproved_ids():
    item = _constraint()
    constraints_hash = constraint_register_sha256([item])
    approval = _approval(constraints_hash="f" * 64, approved_ids=())

    blockers = validate_approval_register(
        approval,
        setup_evidence_sha256="1" * 64,
        dimensions_sha256="2" * 64,
        datums_sha256="3" * 64,
        constraints_sha256=constraints_hash,
        required_ids=(item.id,),
    )

    assert [blocker["code"] for blocker in blockers] == [
        "input_hash_mismatch",
        "constraint_not_approved",
    ]
    assert all(set(blocker) == {"code", "path", "expected", "actual", "severity"} for blocker in blockers)


def test_approval_binding_accepts_matching_hashes_and_ids():
    item = _constraint()
    constraints_hash = constraint_register_sha256([item])
    approval = _approval(constraints_hash=constraints_hash)

    assert validate_approval_register(
        approval,
        setup_evidence_sha256="1" * 64,
        dimensions_sha256="2" * 64,
        datums_sha256="3" * 64,
        constraints_sha256=constraints_hash,
        required_ids=(item.id,),
    ) == ()
