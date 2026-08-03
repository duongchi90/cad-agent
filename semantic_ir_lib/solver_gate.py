"""Fail-closed, offline authoritative solver adapter for M3."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from cad_agent.drawing_setup import require_setup_verified
from primitive_ir_lib.models import (
    Point2D,
    Primitive,
    PrimitiveIRDocument,
)

from .constraint_ir import (
    ApprovalRegister,
    ConstraintObservation,
    ConstraintIRValidationError,
    SUPPORTED_SOLVER_CONSTRAINT_KINDS,
    constraint_register_sha256,
    validate_approval_register,
    validate_constraint_observation,
)
from .constraint_solving import solve_constraints
from .datum_ir import DatumObservation, datum_register_sha256, resolve_reference, validate_datum_observation
from .dimension_ir import (
    DimensionObservation,
    DimensionIRValidationError,
    canonical_json_sha256,
    dimension_register_sha256,
    normalize_dimension,
    validate_dimension_observation,
)
from .models import Constraint


DEFAULT_DIMENSION_TOLERANCE_MM = 0.01
_DIMENSION_KINDS = {
    "horizontal_distance",
    "vertical_distance",
    "aligned_distance",
    "radial",
    "diameter",
    "chain",
    "baseline",
    "ordinate",
}
_PRIMITIVE_REFS = {"line", "circle", "arc"}


@dataclass(frozen=True)
class SolvedDrawingModel:
    model_id: str
    setup_evidence_sha256: str
    dimensions_sha256: str
    datums_sha256: str
    constraints_sha256: str
    solved_views: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "solved-drawing-model-1.0",
            "model_id": self.model_id,
            "setup_evidence_sha256": self.setup_evidence_sha256,
            "dimensions_sha256": self.dimensions_sha256,
            "datums_sha256": self.datums_sha256,
            "constraints_sha256": self.constraints_sha256,
            "solved_views": dict(self.solved_views),
        }


def _blocker(
    code: str,
    path: str,
    expected: object,
    actual: object,
    *,
    severity: str = "P0",
) -> dict[str, object]:
    return {
        "code": code,
        "path": path,
        "expected": expected,
        "actual": actual,
        "severity": severity,
    }


def _safe_register_hash(
    function,
    items: Sequence[object],
    *,
    label: str,
) -> str:
    try:
        return function(items)
    except (TypeError, ValueError, DimensionIRValidationError) as exc:
        return canonical_json_sha256({"invalid": label, "error": str(exc)})


def _setup_failure_report(
    *,
    setup_evidence: Mapping[str, object],
    error: Exception,
    dimensions: Sequence[DimensionObservation],
    datums: Sequence[DatumObservation],
    constraints: Sequence[ConstraintObservation],
) -> tuple[dict[str, object], None]:
    dimensions_hash = _safe_register_hash(dimension_register_sha256, dimensions, label="dimensions")
    datums_hash = _safe_register_hash(datum_register_sha256, datums, label="datums")
    constraints_hash = _safe_register_hash(constraint_register_sha256, constraints, label="constraints")
    evidence_hash = _safe_evidence_hash(setup_evidence)
    return _report(
        model_id=_model_id(dimensions_hash, datums_hash, constraints_hash),
        status="NEEDS_REVIEW",
        setup_evidence_sha256=evidence_hash,
        dimensions_sha256=dimensions_hash,
        datums_sha256=datums_hash,
        constraints_sha256=constraints_hash,
        degrees_of_freedom={"MODEL": 0},
        constraints=constraints,
        blockers=(_blocker("stale_setup_evidence", "setup_evidence", "SETUP_VERIFIED", str(error)),),
        max_residual_mm=0.0,
    ), None


def _safe_evidence_hash(evidence: Mapping[str, object]) -> str:
    try:
        return canonical_json_sha256(evidence)
    except (TypeError, ValueError):
        return "0" * 64


def _model_id(dimensions_hash: str, datums_hash: str, constraints_hash: str) -> str:
    seed = canonical_json_sha256(
        {
            "dimensions_sha256": dimensions_hash,
            "datums_sha256": datums_hash,
            "constraints_sha256": constraints_hash,
        }
    )
    return f"M3-{seed[:16]}"


def _report(
    *,
    model_id: str,
    status: str,
    setup_evidence_sha256: str,
    dimensions_sha256: str,
    datums_sha256: str,
    constraints_sha256: str,
    degrees_of_freedom: Mapping[str, int],
    constraints: Sequence[ConstraintObservation],
    blockers: Sequence[Mapping[str, object]],
    max_residual_mm: float,
    constraint_statuses: Mapping[str, str] | None = None,
    constraint_residuals: Mapping[str, float] | None = None,
) -> dict[str, object]:
    constraint_statuses = constraint_statuses or {}
    constraint_residuals = constraint_residuals or {}
    constraint_rows = []
    for item in sorted(constraints, key=lambda value: value.id):
        constraint_rows.append(
            {
                "id": item.id,
                "status": constraint_statuses.get(item.id, "UNRESOLVED"),
                "residual_mm": round(float(constraint_residuals.get(item.id, 0.0)), 4),
                "tolerance_mm": round(float(item.tolerance_mm), 4),
                "conflict_set": [],
            }
        )
    ordered_blockers = sorted(
        (dict(blocker) for blocker in blockers),
        key=lambda blocker: (
            str(blocker.get("path", "")),
            str(blocker.get("code", "")),
            str(blocker.get("actual", "")),
        ),
    )
    return {
        "schema_version": "constraint-report-1.0",
        "model_id": model_id,
        "status": status,
        "setup_evidence_sha256": setup_evidence_sha256,
        "dimensions_sha256": dimensions_sha256,
        "datums_sha256": datums_sha256,
        "constraints_sha256": constraints_sha256,
        "degrees_of_freedom": dict(degrees_of_freedom),
        "constraints": constraint_rows,
        "blockers": ordered_blockers,
        "max_residual_mm": round(max(0.0, float(max_residual_mm)), 4),
    }


def _primitive_by_id(document: PrimitiveIRDocument) -> dict[str, Primitive]:
    return {primitive.id: primitive for primitive in document.primitives}


def _solved_point(
    reference: str,
    *,
    document: PrimitiveIRDocument,
    solved_primitives: Mapping[str, object],
    datums: Mapping[str, DatumObservation],
    view_id: str,
) -> Point2D:
    parts = reference.split(":")
    if len(parts) == 3 and parts[0] == "primitive":
        primitive_id, role = parts[1], parts[2]
        solved = solved_primitives.get(primitive_id)
        if solved is not None and isinstance(solved, object):
            point = getattr(solved, role, None)
            if isinstance(point, Point2D):
                return point
    point = resolve_reference(
        reference,
        datums=datums,
        primitive_document=document,
        view_id=view_id,
    )
    if isinstance(point, Point2D):
        return point
    if isinstance(point, tuple) and len(point) == 2:
        return Point2D(float(point[0]), float(point[1]))
    raise ValueError(f"reference did not resolve to a point: {reference}")


def _dimension_actual(kind: str, start: Point2D, end: Point2D) -> float:
    dx, dy = end.x - start.x, end.y - start.y
    if kind == "horizontal_distance":
        return abs(dx)
    if kind == "vertical_distance":
        return abs(dy)
    return math.hypot(dx, dy)


def _constraint_primitive_ids(
    item: ConstraintObservation,
    primitive_by_id: Mapping[str, Primitive],
) -> tuple[str, str] | None:
    if len(item.refs) != 2 or any(not ref.startswith("primitive:") for ref in item.refs):
        return None
    ids = tuple(ref.split(":", 1)[1] for ref in item.refs)
    if any(primitive_id not in primitive_by_id for primitive_id in ids):
        return None
    if any(primitive_by_id[primitive_id].type not in _PRIMITIVE_REFS for primitive_id in ids):
        return None
    return ids[0], ids[1]


def _detect_constraint_conflicts(constraints: Sequence[ConstraintObservation]) -> list[dict[str, object]]:
    by_pair: dict[tuple[str, tuple[str, str]], list[str]] = {}
    for item in constraints:
        pair = tuple(sorted(item.refs))
        by_pair.setdefault(("pair", pair), []).append(item.kind)
    blockers = []
    for (_, pair), kinds in sorted(by_pair.items()):
        if "parallel" in kinds and "perpendicular" in kinds:
            blockers.append(
                _blocker(
                    "constraint_conflict",
                    f"constraints[{pair[0]}|{pair[1]}]",
                    "mutually compatible relations",
                    sorted(set(kinds)),
                )
            )
    return blockers


def _solved_views(solved_primitives: Mapping[str, object]) -> dict[str, object]:
    primitives: dict[str, object] = {}
    for primitive_id in sorted(solved_primitives):
        solved = solved_primitives[primitive_id]
        start = getattr(solved, "start", None)
        end = getattr(solved, "end", None)
        if isinstance(start, Point2D) and isinstance(end, Point2D):
            primitives[primitive_id] = {
                "start": start.to_dict(),
                "end": end.to_dict(),
                "displacement_mm": round(float(getattr(solved, "displacement_mm", 0.0)), 4),
            }
    return {"MODEL": {"primitives": primitives}}


def solve_authoritative_model(
    *,
    primitive_document: PrimitiveIRDocument,
    dimensions: Sequence[DimensionObservation],
    datums: Sequence[DatumObservation],
    constraints: Sequence[ConstraintObservation],
    approval: ApprovalRegister,
    setup_evidence: Mapping[str, object],
    setup_plan_sha256: str,
    drawing_profile_sha256: str,
    template_file_sha256: str,
) -> tuple[dict[str, object], SolvedDrawingModel | None]:
    """Validate approved M3 inputs, solve supported relations, and return report/model."""
    try:
        require_setup_verified(
            setup_evidence,
            setup_plan_sha256=setup_plan_sha256,
            drawing_profile_sha256=drawing_profile_sha256,
            template_file_sha256=template_file_sha256,
        )
    except Exception as exc:
        return _setup_failure_report(
            setup_evidence=setup_evidence,
            error=exc,
            dimensions=dimensions,
            datums=datums,
            constraints=constraints,
        )

    dimensions_hash = _safe_register_hash(dimension_register_sha256, dimensions, label="dimensions")
    datums_hash = _safe_register_hash(datum_register_sha256, datums, label="datums")
    constraints_hash = _safe_register_hash(constraint_register_sha256, constraints, label="constraints")
    evidence_hash = _safe_evidence_hash(setup_evidence)
    model_id = _model_id(dimensions_hash, datums_hash, constraints_hash)
    blockers: list[dict[str, object]] = []

    for item in dimensions:
        try:
            validate_dimension_observation(item)
        except DimensionIRValidationError as exc:
            blockers.append(_blocker("dimension_invalid", f"dimensions[{item.id}]", "valid dimension", str(exc)))
        if item.status != "APPROVED":
            blockers.append(_blocker("dimension_not_approved", f"dimensions[{item.id}].status", "APPROVED", item.status))
    for item in datums:
        try:
            validate_datum_observation(item)
        except (TypeError, ValueError, DimensionIRValidationError) as exc:
            blockers.append(_blocker("datum_invalid", f"datums[{item.id}]", "valid datum", str(exc)))
        if item.status != "APPROVED":
            blockers.append(_blocker("datum_not_approved", f"datums[{item.id}].status", "APPROVED", item.status))
    for item in constraints:
        try:
            validate_constraint_observation(item)
        except ConstraintIRValidationError as exc:
            blockers.append(_blocker("constraint_invalid", f"constraints[{item.id}]", "valid constraint", str(exc)))
        if item.status != "APPROVED":
            blockers.append(_blocker("constraint_not_approved", f"constraints[{item.id}].status", "APPROVED", item.status))

    required_ids = tuple(item.id for item in [*dimensions, *datums, *constraints])
    try:
        blockers.extend(
            _blocker(
                blocker["code"],
                str(blocker["path"]),
                blocker["expected"],
                blocker["actual"],
            )
            for blocker in validate_approval_register(
                approval,
                setup_evidence_sha256=evidence_hash,
                dimensions_sha256=dimensions_hash,
                datums_sha256=datums_hash,
                constraints_sha256=constraints_hash,
                required_ids=required_ids,
            )
        )
    except (TypeError, ValueError, ConstraintIRValidationError) as exc:
        blockers.append(_blocker("approval_invalid", "approval", "valid approval register", str(exc)))

    if blockers:
        return _report(
            model_id=model_id,
            status="NEEDS_REVIEW",
            setup_evidence_sha256=evidence_hash,
            dimensions_sha256=dimensions_hash,
            datums_sha256=datums_hash,
            constraints_sha256=constraints_hash,
            degrees_of_freedom={"MODEL": 0},
            constraints=constraints,
            blockers=blockers,
            max_residual_mm=0.0,
        ), None

    datum_by_id = {item.id: item for item in datums}
    primitive_by_id = _primitive_by_id(primitive_document)
    blockers.extend(_detect_constraint_conflicts(constraints))
    semantic_constraints: list[Constraint] = []
    constraint_statuses: dict[str, str] = {}
    for item in constraints:
        if item.kind not in SUPPORTED_SOLVER_CONSTRAINT_KINDS:
            blockers.append(
                _blocker(
                    "constraint_unsupported",
                    f"constraints[{item.id}].kind",
                    sorted(SUPPORTED_SOLVER_CONSTRAINT_KINDS),
                    item.kind,
                )
            )
            constraint_statuses[item.id] = "UNSUPPORTED"
            continue
        primitive_ids = _constraint_primitive_ids(item, primitive_by_id)
        if primitive_ids is None:
            blockers.append(
                _blocker(
                    "constraint_unresolved",
                    f"constraints[{item.id}].refs",
                    "two existing primitive references",
                    list(item.refs),
                )
            )
            constraint_statuses[item.id] = "UNRESOLVED"
            continue
        legacy_kind = "coincident_endpoint" if item.kind == "coincident" else item.kind
        semantic_constraints.append(
            Constraint(
                id=item.id,
                type=legacy_kind,
                primitive_ids=list(primitive_ids),
                confidence=1.0,
                tolerance={"distance_mm": item.tolerance_mm},
            )
        )

    if blockers:
        return _report(
            model_id=model_id,
            status="CONFLICT" if any(item["code"] == "constraint_conflict" for item in blockers) else "NEEDS_REVIEW",
            setup_evidence_sha256=evidence_hash,
            dimensions_sha256=dimensions_hash,
            datums_sha256=datums_hash,
            constraints_sha256=constraints_hash,
            degrees_of_freedom={"MODEL": 0},
            constraints=constraints,
            blockers=blockers,
            max_residual_mm=0.0,
            constraint_statuses=constraint_statuses,
        ), None

    dimension_residuals: list[float] = []
    solved_result = None
    try:
        solved_result = solve_constraints(primitive_document, semantic_constraints)
    except ImportError as exc:
        blockers.append(_blocker("solver_dependency_missing", "solver", "python-solvespace", str(exc)))

    if solved_result is None:
        solve_status = "NEEDS_REVIEW"
        degrees_of_freedom = {"MODEL": 0}
        solved_primitives: Mapping[str, object] = {}
    else:
        degrees_of_freedom = {"MODEL": max(0, int(solved_result.dof))}
        solved_primitives = solved_result.solved_primitives
        solve_status = {
            "inconsistent": "CONFLICT",
            "didnt_converge": "NON_CONVERGENT",
            "too_many_unknowns": "OVERCONSTRAINED",
        }.get(solved_result.status, "SOLVED" if solved_result.status == "okay" else "NEEDS_REVIEW")
        if solved_result.status == "inconsistent":
            blockers.append(_blocker("solver_conflict", "constraints", "consistent constraint set", solved_result.status))
        elif solved_result.status == "didnt_converge":
            blockers.append(_blocker("solver_non_convergent", "solver.status", "okay", solved_result.status))
        elif solved_result.status == "too_many_unknowns":
            blockers.append(_blocker("overconstrained_model", "solver.status", "within solver capacity", solved_result.status))

    for item in constraints:
        if item.id not in constraint_statuses:
            constraint_statuses[item.id] = "SOLVED" if solve_status == "SOLVED" else solve_status

    for item in dimensions:
        try:
            if item.kind not in _DIMENSION_KINDS:
                blockers.append(_blocker("dimension_kind_unsupported", f"dimensions[{item.id}].kind", sorted(_DIMENSION_KINDS), item.kind))
                continue
            start = _solved_point(
                item.from_ref,
                document=primitive_document,
                solved_primitives=solved_primitives,
                datums=datum_by_id,
                view_id=item.view_id,
            )
            end = _solved_point(
                item.to_ref,
                document=primitive_document,
                solved_primitives=solved_primitives,
                datums=datum_by_id,
                view_id=item.view_id,
            )
            actual = _dimension_actual(item.kind, start, end)
            expected = normalize_dimension(item.value, item.unit)
            residual = round(abs(actual - expected), 4)
            dimension_residuals.append(residual)
            if residual > DEFAULT_DIMENSION_TOLERANCE_MM:
                blockers.append(
                    _blocker(
                        "residual_exceeds_tolerance",
                        f"dimensions[{item.id}]",
                        DEFAULT_DIMENSION_TOLERANCE_MM,
                        residual,
                    )
                )
        except (TypeError, ValueError, DimensionIRValidationError) as exc:
            blockers.append(
                _blocker(
                    "dimension_unresolved_attachment",
                    f"dimensions[{item.id}].from_ref/to_ref",
                    "resolvable references in approved view",
                    str(exc),
                )
            )

    if solve_status == "SOLVED" and solved_result is not None and solved_result.dof > 0 and constraints:
        solve_status = "UNDERCONSTRAINED"
        blockers.append(_blocker("underconstrained_model", "degrees_of_freedom.MODEL", 0, solved_result.dof, severity="P1"))
    if blockers and solve_status == "SOLVED":
        solve_status = "NEEDS_REVIEW"

    constraint_residuals = {item.id: 0.0 for item in constraints}
    max_residual = max(dimension_residuals or [0.0] + list(constraint_residuals.values()))
    report = _report(
        model_id=model_id,
        status=solve_status,
        setup_evidence_sha256=evidence_hash,
        dimensions_sha256=dimensions_hash,
        datums_sha256=datums_hash,
        constraints_sha256=constraints_hash,
        degrees_of_freedom=degrees_of_freedom,
        constraints=constraints,
        blockers=blockers,
        max_residual_mm=max_residual,
        constraint_statuses=constraint_statuses,
        constraint_residuals=constraint_residuals,
    )
    if report["status"] != "SOLVED" or report["blockers"]:
        return report, None

    model = SolvedDrawingModel(
        model_id=model_id,
        setup_evidence_sha256=evidence_hash,
        dimensions_sha256=dimensions_hash,
        datums_sha256=datums_hash,
        constraints_sha256=constraints_hash,
        solved_views=_solved_views(solved_primitives),
    )
    return report, model


__all__ = ["SolvedDrawingModel", "solve_authoritative_model"]
