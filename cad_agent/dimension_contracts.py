"""Strict contracts for the Personal Lean Dimension Pilot."""

from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_AXIS_EPSILON = 1e-9
_SOLVER_STATUSES = {
    "not_run",
    "okay",
    "inconsistent",
    "didnt_converge",
    "too_many_unknowns",
}


class DimensionPilotContractError(ValueError):
    """Raised when a Dimension Pilot contract is malformed or unsafe."""


def _fail(contract: str, message: str) -> None:
    raise DimensionPilotContractError(f"{contract}: {message}")


def _assert_finite_json(value: object, *, contract: str, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        _fail(contract, f"{path} must contain only finite numbers")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_finite_json(item, contract=contract, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_finite_json(
                item,
                contract=contract,
                path=f"{path}[{index}]",
            )


def _object(value: object, *, contract: str, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(contract, f"{path} must be an object")
    return value


def _keys(
    value: Mapping[str, object],
    *,
    contract: str,
    path: str,
    required: set[str],
) -> None:
    missing = sorted(required - set(value))
    unexpected = sorted(set(value) - required)
    if missing:
        _fail(contract, f"{path} missing required properties: {', '.join(missing)}")
    if unexpected:
        _fail(contract, f"{path} Unexpected properties: {', '.join(unexpected)}")


def _string(
    value: object,
    *,
    contract: str,
    path: str,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(contract, f"{path} must be a non-empty string")
    if pattern is not None and pattern.fullmatch(value) is None:
        _fail(contract, f"{path} has invalid format")
    return value


def _identifier(value: object, *, contract: str, path: str) -> str:
    return _string(
        value,
        contract=contract,
        path=path,
        pattern=_ID_RE,
    )


def _sha256(value: object, *, contract: str, path: str) -> str:
    return _string(
        value,
        contract=contract,
        path=path,
        pattern=_SHA256_RE,
    )


def _number(value: object, *, contract: str, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(contract, f"{path} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        _fail(contract, f"{path} must be finite")
    return number


def _positive_number(value: object, *, contract: str, path: str) -> float:
    number = _number(value, contract=contract, path=path)
    if number <= 0:
        _fail(contract, f"{path} must be finite and positive")
    return number


def _nonnegative_int(value: object, *, contract: str, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(contract, f"{path} must be a non-negative integer")
    return value


def _boolean(value: object, *, contract: str, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(contract, f"{path} must be boolean")
    return value


def _approval(value: object, *, contract: str, path: str) -> None:
    item = _object(value, contract=contract, path=path)
    _keys(
        item,
        contract=contract,
        path=path,
        required={"approved_by", "reference"},
    )
    _string(item["approved_by"], contract=contract, path=f"{path}.approved_by")
    _string(item["reference"], contract=contract, path=f"{path}.reference")


def _attachment(
    value: object,
    *,
    contract: str,
    path: str,
) -> tuple[str, Literal["start", "end"]]:
    item = _object(value, contract=contract, path=path)
    _keys(
        item,
        contract=contract,
        path=path,
        required={"primitive_id", "endpoint"},
    )
    primitive_id = _identifier(
        item["primitive_id"],
        contract=contract,
        path=f"{path}.primitive_id",
    )
    endpoint = item["endpoint"]
    if endpoint not in {"start", "end"}:
        _fail(contract, f"{path}.endpoint must be start or end")
    return primitive_id, endpoint


def _vector(
    value: object,
    *,
    contract: str,
    path: str,
) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        _fail(contract, f"{path} must contain exactly two numbers")
    return (
        _number(value[0], contract=contract, path=f"{path}[0]"),
        _number(value[1], contract=contract, path=f"{path}[1]"),
    )


def _unique_identifiers(
    value: object,
    *,
    contract: str,
    path: str,
) -> list[str]:
    if not isinstance(value, list):
        _fail(contract, f"{path} must be a list")
    items = [
        _identifier(item, contract=contract, path=f"{path}[{index}]")
        for index, item in enumerate(value)
    ]
    if len(items) != len(set(items)):
        _fail(contract, f"{path} must contain unique identifiers")
    return items


def validate_dimension_plan(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Validate and deep-copy a Dimension Pilot plan."""
    contract = "dimension_pilot_plan"
    if not isinstance(payload, Mapping):
        _fail(contract, "root must be an object")
    source = dict(payload)
    _assert_finite_json(source, contract=contract)
    required = {
        "schema_version",
        "pilot_id",
        "view_id",
        "source_sha256",
        "primitive_ir_sha256",
        "semantic_ir_sha256",
        "setup",
        "measurement_tolerance_mm",
        "datum",
        "dimensions",
        "constraint_ids",
        "approval",
    }
    _keys(source, contract=contract, path="$", required=required)
    if source["schema_version"] != "dimension-pilot-plan-1.0":
        _fail(contract, "schema_version must be dimension-pilot-plan-1.0")
    _identifier(source["pilot_id"], contract=contract, path="pilot_id")
    _identifier(source["view_id"], contract=contract, path="view_id")
    for name in (
        "source_sha256",
        "primitive_ir_sha256",
        "semantic_ir_sha256",
    ):
        _sha256(source[name], contract=contract, path=name)

    setup = _object(source["setup"], contract=contract, path="setup")
    setup_keys = {
        "evidence_sha256",
        "setup_plan_sha256",
        "drawing_profile_sha256",
        "template_file_sha256",
    }
    _keys(setup, contract=contract, path="setup", required=setup_keys)
    for name in setup_keys:
        _sha256(setup[name], contract=contract, path=f"setup.{name}")

    _positive_number(
        source["measurement_tolerance_mm"],
        contract=contract,
        path="measurement_tolerance_mm",
    )

    datum = _object(source["datum"], contract=contract, path="datum")
    _keys(
        datum,
        contract=contract,
        path="datum",
        required={
            "id",
            "origin_mm",
            "origin_attachment",
            "x_axis",
            "y_axis",
            "x_axis_primitive_id",
            "status",
            "approval",
        },
    )
    _identifier(datum["id"], contract=contract, path="datum.id")
    _vector(datum["origin_mm"], contract=contract, path="datum.origin_mm")
    _attachment(
        datum["origin_attachment"],
        contract=contract,
        path="datum.origin_attachment",
    )
    x_axis = _vector(datum["x_axis"], contract=contract, path="datum.x_axis")
    y_axis = _vector(datum["y_axis"], contract=contract, path="datum.y_axis")
    if abs(math.hypot(*x_axis) - 1.0) > _AXIS_EPSILON:
        _fail(contract, "datum.x_axis must be a unit vector")
    if abs(math.hypot(*y_axis) - 1.0) > _AXIS_EPSILON:
        _fail(contract, "datum.y_axis must be a unit vector")
    if abs(x_axis[0] * y_axis[0] + x_axis[1] * y_axis[1]) > _AXIS_EPSILON:
        _fail(contract, "datum axes must be orthogonal")
    if x_axis[0] * y_axis[1] - x_axis[1] * y_axis[0] <= 0:
        _fail(contract, "datum axes must form a right-handed frame")
    _identifier(
        datum["x_axis_primitive_id"],
        contract=contract,
        path="datum.x_axis_primitive_id",
    )
    if datum["status"] != "APPROVED":
        _fail(contract, "datum.status must be APPROVED")
    _approval(datum["approval"], contract=contract, path="datum.approval")

    dimensions = source["dimensions"]
    if not isinstance(dimensions, list) or not dimensions:
        _fail(contract, "dimensions must be a non-empty list")
    dimension_ids: set[str] = set()
    attachment_pairs: set[tuple[str, tuple[str, str]]] = set()
    for index, value in enumerate(dimensions):
        path = f"dimensions[{index}]"
        item = _object(value, contract=contract, path=path)
        _keys(
            item,
            contract=contract,
            path=path,
            required={
                "id",
                "kind",
                "value_mm",
                "role",
                "from",
                "to",
                "status",
                "approval",
            },
        )
        dimension_id = _identifier(
            item["id"],
            contract=contract,
            path=f"{path}.id",
        )
        if dimension_id in dimension_ids:
            _fail(contract, "dimension IDs must be unique")
        dimension_ids.add(dimension_id)
        if item["kind"] != "linear":
            _fail(contract, f"{path}.kind must be linear")
        _positive_number(
            item["value_mm"],
            contract=contract,
            path=f"{path}.value_mm",
        )
        if item["role"] != "driving":
            _fail(contract, f"{path}.role must be driving")
        from_attachment = _attachment(
            item["from"],
            contract=contract,
            path=f"{path}.from",
        )
        to_attachment = _attachment(
            item["to"],
            contract=contract,
            path=f"{path}.to",
        )
        if (
            from_attachment[0] != to_attachment[0]
            or {from_attachment[1], to_attachment[1]} != {"start", "end"}
        ):
            _fail(
                contract,
                f"{path} attachments must name one line with opposite endpoints",
            )
        pair = (
            from_attachment[0],
            tuple(sorted((from_attachment[1], to_attachment[1]))),
        )
        if pair in attachment_pairs:
            _fail(contract, "dimension attachment pairs must be unique")
        attachment_pairs.add(pair)
        if item["status"] != "APPROVED":
            _fail(contract, f"{path}.status must be APPROVED")
        _approval(item["approval"], contract=contract, path=f"{path}.approval")

    _unique_identifiers(
        source["constraint_ids"],
        contract=contract,
        path="constraint_ids",
    )
    _approval(source["approval"], contract=contract, path="approval")
    return copy.deepcopy(source)


def _measurement(value: object, *, contract: str, path: str) -> None:
    item = _object(value, contract=contract, path=path)
    _keys(
        item,
        contract=contract,
        path=path,
        required={
            "dimension_id",
            "approved_value_mm",
            "solved_value_mm",
            "readback_value_mm",
            "residual_mm",
        },
    )
    _identifier(
        item["dimension_id"],
        contract=contract,
        path=f"{path}.dimension_id",
    )
    _positive_number(
        item["approved_value_mm"],
        contract=contract,
        path=f"{path}.approved_value_mm",
    )
    _positive_number(
        item["solved_value_mm"],
        contract=contract,
        path=f"{path}.solved_value_mm",
    )
    _positive_number(
        item["readback_value_mm"],
        contract=contract,
        path=f"{path}.readback_value_mm",
    )
    residual = _number(
        item["residual_mm"],
        contract=contract,
        path=f"{path}.residual_mm",
    )
    if residual < 0:
        _fail(contract, f"{path}.residual_mm must be non-negative")


def _blocker(value: object, *, contract: str, path: str) -> None:
    item = _object(value, contract=contract, path=path)
    _keys(
        item,
        contract=contract,
        path=path,
        required={"code", "path", "expected", "actual"},
    )
    _string(item["code"], contract=contract, path=f"{path}.code")
    _string(item["path"], contract=contract, path=f"{path}.path")
    _assert_finite_json(item["expected"], contract=contract, path=f"{path}.expected")
    _assert_finite_json(item["actual"], contract=contract, path=f"{path}.actual")


def validate_dimension_evidence(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Validate and deep-copy offline Dimension Pilot evidence."""
    contract = "dimension_pilot_evidence"
    if not isinstance(payload, Mapping):
        _fail(contract, "root must be an object")
    source = dict(payload)
    _assert_finite_json(source, contract=contract)
    required = {
        "schema_version",
        "pilot_id",
        "offline_passed",
        "acceptance",
        "plan_sha256",
        "setup_evidence_sha256",
        "source_sha256",
        "primitive_ir_sha256",
        "semantic_ir_sha256",
        "dxf_sha256",
        "solver",
        "measurements",
        "blockers",
    }
    _keys(source, contract=contract, path="$", required=required)
    if source["schema_version"] != "dimension-pilot-evidence-1.0":
        _fail(contract, "schema_version must be dimension-pilot-evidence-1.0")
    _identifier(source["pilot_id"], contract=contract, path="pilot_id")
    offline_passed = _boolean(
        source["offline_passed"],
        contract=contract,
        path="offline_passed",
    )
    if source["acceptance"] != "NOT_RUN":
        _fail(contract, "acceptance must be NOT_RUN")
    for name in (
        "plan_sha256",
        "setup_evidence_sha256",
        "source_sha256",
        "primitive_ir_sha256",
        "semantic_ir_sha256",
    ):
        _sha256(source[name], contract=contract, path=name)
    if source["dxf_sha256"] is not None:
        _sha256(source["dxf_sha256"], contract=contract, path="dxf_sha256")

    solver = _object(source["solver"], contract=contract, path="solver")
    _keys(
        solver,
        contract=contract,
        path="solver",
        required={
            "status",
            "dof",
            "model_dof",
            "applied_constraint_count",
            "applied_dimension_count",
            "skipped_constraint_ids",
            "conflict_ids",
        },
    )
    if solver["status"] not in _SOLVER_STATUSES:
        _fail(contract, "solver.status is unsupported")
    _nonnegative_int(solver["dof"], contract=contract, path="solver.dof")
    if solver["model_dof"] is not None:
        _nonnegative_int(
            solver["model_dof"],
            contract=contract,
            path="solver.model_dof",
        )
    _nonnegative_int(
        solver["applied_constraint_count"],
        contract=contract,
        path="solver.applied_constraint_count",
    )
    _nonnegative_int(
        solver["applied_dimension_count"],
        contract=contract,
        path="solver.applied_dimension_count",
    )
    _unique_identifiers(
        solver["skipped_constraint_ids"],
        contract=contract,
        path="solver.skipped_constraint_ids",
    )
    _unique_identifiers(
        solver["conflict_ids"],
        contract=contract,
        path="solver.conflict_ids",
    )

    measurements = source["measurements"]
    if not isinstance(measurements, list):
        _fail(contract, "measurements must be a list")
    for index, item in enumerate(measurements):
        _measurement(item, contract=contract, path=f"measurements[{index}]")

    blockers = source["blockers"]
    if not isinstance(blockers, list):
        _fail(contract, "blockers must be a list")
    for index, item in enumerate(blockers):
        _blocker(item, contract=contract, path=f"blockers[{index}]")

    if offline_passed:
        if blockers:
            _fail(contract, "offline_passed evidence cannot contain blockers")
        if source["dxf_sha256"] is None:
            _fail(contract, "offline_passed evidence requires dxf_sha256")
        if solver["status"] != "okay":
            _fail(contract, "offline_passed evidence requires solver.status okay")
        if solver["model_dof"] != 0:
            _fail(contract, "offline_passed evidence requires solver.model_dof 0")
        if not measurements:
            _fail(contract, "offline_passed evidence requires a measurement")
    elif not blockers:
        _fail(contract, "offline_passed=false evidence requires a blocker")
    return copy.deepcopy(source)


def read_dimension_contract(
    path: Path,
    *,
    contract: Literal["plan", "evidence"],
) -> dict[str, object]:
    """Read and validate a Dimension Pilot JSON contract."""
    validators = {
        "plan": validate_dimension_plan,
        "evidence": validate_dimension_evidence,
    }
    validator = validators.get(contract)
    if validator is None:
        raise DimensionPilotContractError(
            f"unsupported Dimension Pilot contract kind: {contract}"
        )
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DimensionPilotContractError(
            f"Cannot read Dimension Pilot {contract}: {source}"
        ) from exc
    if not isinstance(payload, dict):
        raise DimensionPilotContractError(
            f"dimension_pilot_{contract}: root must be an object"
        )
    return validator(payload)


__all__ = [
    "DimensionPilotContractError",
    "read_dimension_contract",
    "validate_dimension_evidence",
    "validate_dimension_plan",
]
