"""Fail-closed offline orchestration for the Personal Lean Dimension Pilot."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from primitive_ir_lib.models import Point2D, Primitive, PrimitiveIRDocument
from semantic_ir_lib.constraint_solving import (
    DatumAnchor,
    DrivingLengthConstraint,
    SolvedPrimitive,
    solve_constraints,
)
from semantic_ir_lib.io_utils import (
    load_primitive_ir_document_bytes,
    load_semantic_ir_document_bytes,
)

from dxf_builder_lib.builder import (
    BuildResult,
    NativeLinearDimensionSpec,
    build_dxf,
)
from dxf_builder_lib.reviewer import review_dxf

from .dimension_contracts import (
    DimensionPilotContractError,
    validate_dimension_evidence,
    validate_dimension_plan,
)
from .drawing_contracts import canonical_json_sha256
from .drawing_setup import DrawingSetupError, require_setup_verified
from .manifest import sha256_file


class DimensionPilotError(ValueError):
    """Raised for malformed inputs or unsafe Dimension Pilot operations."""


@dataclass(frozen=True)
class DimensionPilotRun:
    evidence: dict[str, object]
    build_result: BuildResult | None


def to_local(
    point: Point2D,
    origin: Point2D,
    x_axis: tuple[float, float],
    y_axis: tuple[float, float],
) -> Point2D:
    dx, dy = point.x - origin.x, point.y - origin.y
    return Point2D(
        dx * x_axis[0] + dy * x_axis[1],
        dx * y_axis[0] + dy * y_axis[1],
    )


def to_world(
    point: Point2D,
    origin: Point2D,
    x_axis: tuple[float, float],
    y_axis: tuple[float, float],
) -> Point2D:
    return Point2D(
        origin.x + point.x * x_axis[0] + point.y * y_axis[0],
        origin.y + point.x * x_axis[1] + point.y * y_axis[1],
    )


def _blocker(
    code: str,
    path: str,
    expected: object,
    actual: object,
) -> dict[str, object]:
    return {
        "code": code,
        "path": path,
        "expected": expected,
        "actual": actual,
    }


def _sorted_blockers(
    blockers: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    return sorted(
        blockers,
        key=lambda item: (str(item["code"]), str(item["path"])),
    )


def _solver_evidence() -> dict[str, object]:
    return {
        "status": "not_run",
        "dof": 0,
        "model_dof": None,
        "applied_constraint_count": 0,
        "applied_dimension_count": 0,
        "skipped_constraint_ids": [],
        "conflict_ids": [],
    }


def _evidence_base(
    *,
    plan: Mapping[str, object],
    plan_sha256: str,
    setup_evidence_sha256: str,
    source_sha256: str,
    primitive_ir_sha256: str,
    semantic_ir_sha256: str,
) -> dict[str, object]:
    return {
        "schema_version": "dimension-pilot-evidence-1.0",
        "pilot_id": plan["pilot_id"],
        "offline_passed": False,
        "acceptance": "NOT_RUN",
        "plan_sha256": plan_sha256,
        "setup_evidence_sha256": setup_evidence_sha256,
        "source_sha256": source_sha256,
        "primitive_ir_sha256": primitive_ir_sha256,
        "semantic_ir_sha256": semantic_ir_sha256,
        "dxf_sha256": None,
        "solver": _solver_evidence(),
        "measurements": [],
        "blockers": [],
    }


def _finish_blocked(
    evidence: dict[str, object],
    blockers: Sequence[dict[str, object]],
    *,
    build_result: BuildResult | None = None,
) -> DimensionPilotRun:
    evidence["offline_passed"] = False
    evidence["dxf_sha256"] = None
    evidence["blockers"] = _sorted_blockers(blockers)
    try:
        validated = validate_dimension_evidence(evidence)
    except DimensionPilotContractError as exc:
        raise DimensionPilotError(str(exc)) from exc
    return DimensionPilotRun(evidence=validated, build_result=build_result)


def _file_hash(path: Path, *, label: str) -> str:
    try:
        return sha256_file(path)
    except OSError as exc:
        raise DimensionPilotError(f"Cannot hash {label}: {path}") from exc


def _snapshot_file(path: Path, *, label: str) -> tuple[bytes, str]:
    """Read and hash one immutable input byte stream for loading."""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise DimensionPilotError(f"Cannot snapshot {label}: {path}") from exc
    return payload, hashlib.sha256(payload).hexdigest()


def _cleanup_path(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _artifact_change_blockers(
    *,
    source_path: Path,
    primitive_ir_path: Path,
    semantic_ir_path: Path,
    source_sha256: str,
    primitive_ir_sha256: str,
    semantic_ir_sha256: str,
) -> list[dict[str, object]]:
    comparisons = (
        ("source_changed", "$.source_sha256", source_path, source_sha256, "source"),
        (
            "primitive_ir_changed",
            "$.primitive_ir_sha256",
            primitive_ir_path,
            primitive_ir_sha256,
            "Primitive IR",
        ),
        (
            "semantic_ir_changed",
            "$.semantic_ir_sha256",
            semantic_ir_path,
            semantic_ir_sha256,
            "Semantic IR",
        ),
    )
    blockers: list[dict[str, object]] = []
    for code, path, artifact, expected, label in comparisons:
        try:
            actual: object = _file_hash(artifact, label=label)
        except DimensionPilotError:
            actual = None
        if actual != expected:
            blockers.append(_blocker(code, path, expected, actual))
    return blockers


def _mapping_hash(value: Mapping[str, object], *, label: str) -> str:
    try:
        return canonical_json_sha256(value)
    except (TypeError, ValueError) as exc:
        raise DimensionPilotError(f"Cannot hash malformed {label}") from exc


def _load_models(
    primitive_ir_payload: bytes,
    semantic_ir_payload: bytes,
) -> tuple[PrimitiveIRDocument, object]:
    try:
        return (
            load_primitive_ir_document_bytes(primitive_ir_payload),
            load_semantic_ir_document_bytes(semantic_ir_payload),
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise DimensionPilotError("Cannot load validated Primitive/Semantic IR") from exc


def _line_by_id(document: PrimitiveIRDocument) -> dict[str, Primitive]:
    return {
        primitive.id: primitive
        for primitive in document.primitives
        if primitive.type == "line" and primitive.geometry is not None
    }


def _endpoint(line: Primitive, name: str) -> Point2D:
    return line.geometry.start if name == "start" else line.geometry.end


def _setup_blockers(evidence: Mapping[str, object]) -> list[dict[str, object]]:
    raw = evidence.get("blockers")
    if not isinstance(raw, list) or not raw:
        return [
            _blocker(
                "setup_incomplete",
                "$.setup",
                "SETUP_VERIFIED",
                evidence.get("status"),
            )
        ]
    blockers: list[dict[str, object]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            blockers.append(
                _blocker(
                    "setup_incomplete",
                    f"$.setup.blockers[{index}]",
                    "valid setup blocker",
                    item,
                )
            )
            continue
        blockers.append(
            _blocker(
                "setup_incomplete",
                str(item.get("path", f"$.setup.blockers[{index}]")),
                item.get("expected"),
                item.get("actual"),
            )
        )
    return blockers


def _world_solutions(
    solved: Mapping[str, SolvedPrimitive],
    original: PrimitiveIRDocument,
    origin: Point2D,
    x_axis: tuple[float, float],
    y_axis: tuple[float, float],
) -> dict[str, SolvedPrimitive]:
    original_lines = _line_by_id(original)
    world: dict[str, SolvedPrimitive] = {}
    for primitive_id, item in solved.items():
        start = to_world(item.start, origin, x_axis, y_axis)
        end = to_world(item.end, origin, x_axis, y_axis)
        source = original_lines[primitive_id].geometry
        displacement = math.hypot(
            start.x - source.start.x,
            start.y - source.start.y,
        ) + math.hypot(
            end.x - source.end.x,
            end.y - source.end.y,
        )
        world[primitive_id] = SolvedPrimitive(
            primitive_id=primitive_id,
            start=start,
            end=end,
            displacement_mm=round(displacement, 4),
        )
    return world


def run_dimension_pilot(
    *,
    plan: Mapping[str, object],
    setup_plan: Mapping[str, object],
    setup_evidence: Mapping[str, object],
    source_path: Path,
    primitive_ir_path: Path,
    semantic_ir_path: Path,
    output_dxf: Path,
) -> DimensionPilotRun:
    """Run the approved offline slice; Mechanical acceptance stays NOT_RUN."""
    try:
        validated_plan = validate_dimension_plan(plan)
    except DimensionPilotContractError as exc:
        raise DimensionPilotError(str(exc)) from exc
    if not isinstance(setup_plan, Mapping) or not isinstance(setup_evidence, Mapping):
        raise DimensionPilotError("Drawing Setup plan and evidence must be objects")

    source_path = Path(source_path)
    primitive_ir_path = Path(primitive_ir_path)
    semantic_ir_path = Path(semantic_ir_path)
    output_dxf = Path(output_dxf)
    if output_dxf.suffix.lower() != ".dxf":
        raise DimensionPilotError("Dimension Pilot output must use the .dxf suffix")
    if output_dxf.exists():
        raise DimensionPilotError(f"Output already exists: {output_dxf}")

    setup_plan = copy.deepcopy(dict(setup_plan))
    setup_evidence = copy.deepcopy(dict(setup_evidence))
    plan_hash = _mapping_hash(validated_plan, label="Dimension Pilot plan")
    setup_plan_hash = _mapping_hash(setup_plan, label="Drawing Setup plan")
    setup_evidence_hash = _mapping_hash(
        setup_evidence,
        label="Drawing Setup evidence",
    )
    source_hash = _file_hash(source_path, label="source")
    primitive_payload, primitive_hash = _snapshot_file(
        primitive_ir_path,
        label="Primitive IR",
    )
    semantic_payload, semantic_hash = _snapshot_file(
        semantic_ir_path,
        label="Semantic IR",
    )
    evidence = _evidence_base(
        plan=validated_plan,
        plan_sha256=plan_hash,
        setup_evidence_sha256=setup_evidence_hash,
        source_sha256=source_hash,
        primitive_ir_sha256=primitive_hash,
        semantic_ir_sha256=semantic_hash,
    )

    setup = validated_plan["setup"]
    blockers: list[dict[str, object]] = []
    comparisons = (
        ("source_changed", "$.source_sha256", validated_plan["source_sha256"], source_hash),
        ("primitive_ir_changed", "$.primitive_ir_sha256", validated_plan["primitive_ir_sha256"], primitive_hash),
        ("semantic_ir_changed", "$.semantic_ir_sha256", validated_plan["semantic_ir_sha256"], semantic_hash),
        ("setup_incomplete", "$.setup.setup_plan_sha256", setup["setup_plan_sha256"], setup_plan_hash),
        ("setup_evidence_changed", "$.setup.evidence_sha256", setup["evidence_sha256"], setup_evidence_hash),
    )
    for code, path, expected, actual in comparisons:
        if expected != actual:
            blockers.append(_blocker(code, path, expected, actual))
    if blockers:
        return _finish_blocked(evidence, blockers)

    try:
        require_setup_verified(
            setup_evidence,
            setup_plan_sha256=setup["setup_plan_sha256"],
            drawing_profile_sha256=setup["drawing_profile_sha256"],
            template_file_sha256=setup["template_file_sha256"],
        )
    except DrawingSetupError:
        return _finish_blocked(evidence, _setup_blockers(setup_evidence))

    primitive_document, semantic_document = _load_models(
        primitive_payload,
        semantic_payload,
    )
    blockers.extend(
        _artifact_change_blockers(
            source_path=source_path,
            primitive_ir_path=primitive_ir_path,
            semantic_ir_path=semantic_ir_path,
            source_sha256=source_hash,
            primitive_ir_sha256=primitive_hash,
            semantic_ir_sha256=semantic_hash,
        )
    )
    if primitive_document.source_document.sha256 != validated_plan["source_sha256"]:
        blockers.append(
            _blocker(
                "source_provenance_mismatch",
                "$.primitive_ir.source_document.sha256",
                validated_plan["source_sha256"],
                primitive_document.source_document.sha256,
            )
        )
    if semantic_document.primitive_ir_ref.sha256 != validated_plan["primitive_ir_sha256"]:
        blockers.append(
            _blocker(
                "primitive_provenance_mismatch",
                "$.semantic_ir.primitive_ir_ref.sha256",
                validated_plan["primitive_ir_sha256"],
                semantic_document.primitive_ir_ref.sha256,
            )
        )
    if blockers:
        return _finish_blocked(evidence, blockers)

    local_document = copy.deepcopy(primitive_document)
    local_lines = _line_by_id(local_document)
    datum = validated_plan["datum"]
    origin = Point2D(*datum["origin_mm"])
    x_axis = tuple(datum["x_axis"])
    y_axis = tuple(datum["y_axis"])
    tolerance = float(validated_plan["measurement_tolerance_mm"])
    origin_attachment = datum["origin_attachment"]
    origin_primitive_id = origin_attachment["primitive_id"]
    origin_endpoint = origin_attachment["endpoint"]
    x_axis_primitive_id = datum["x_axis_primitive_id"]

    if origin_primitive_id != x_axis_primitive_id:
        blockers.append(
            _blocker(
                "datum_mismatch",
                "$.datum.origin_attachment.primitive_id",
                x_axis_primitive_id,
                origin_primitive_id,
            )
        )
    datum_line = local_lines.get(origin_primitive_id)
    x_axis_line = local_lines.get(x_axis_primitive_id)
    if datum_line is None:
        blockers.append(
            _blocker(
                "attachment_unresolved",
                "$.datum.origin_attachment",
                "written LINE endpoint",
                origin_primitive_id,
            )
        )
    if x_axis_line is None and x_axis_primitive_id != origin_primitive_id:
        blockers.append(
            _blocker(
                "attachment_unresolved",
                "$.datum.x_axis_primitive_id",
                "written LINE",
                x_axis_primitive_id,
            )
        )

    for line in local_lines.values():
        line.geometry.start = to_local(line.geometry.start, origin, x_axis, y_axis)
        line.geometry.end = to_local(line.geometry.end, origin, x_axis, y_axis)

    if datum_line is not None:
        attached = _endpoint(datum_line, origin_endpoint)
        other = _endpoint(datum_line, "end" if origin_endpoint == "start" else "start")
        if math.hypot(attached.x, attached.y) > tolerance:
            blockers.append(
                _blocker(
                    "datum_mismatch",
                    "$.datum.origin_mm",
                    [0.0, 0.0],
                    [attached.x, attached.y],
                )
            )
        if other.x <= 0:
            blockers.append(
                _blocker(
                    "datum_mismatch",
                    "$.datum.x_axis",
                    "other endpoint at positive local X",
                    [other.x, other.y],
                )
            )

    semantic_by_id = {
        constraint.id: constraint for constraint in semantic_document.constraints
    }
    selected_constraints = []
    for index, constraint_id in enumerate(validated_plan["constraint_ids"]):
        constraint = semantic_by_id.get(constraint_id)
        if constraint is None:
            blockers.append(
                _blocker(
                    "constraint_missing",
                    f"$.constraint_ids[{index}]",
                    constraint_id,
                    None,
                )
            )
        else:
            selected_constraints.append(constraint)

    driving_lengths: list[DrivingLengthConstraint] = []
    dimension_specs: list[NativeLinearDimensionSpec] = []
    for index, dimension in enumerate(validated_plan["dimensions"]):
        primitive_id = dimension["from"]["primitive_id"]
        line = local_lines.get(primitive_id)
        if line is None:
            blockers.append(
                _blocker(
                    "attachment_unresolved",
                    f"$.dimensions[{index}]",
                    "one LINE with resolved opposite endpoints",
                    primitive_id,
                )
            )
            continue
        driving_lengths.append(
            DrivingLengthConstraint(
                id=dimension["id"],
                primitive_id=primitive_id,
                value_mm=float(dimension["value_mm"]),
            )
        )
        dimension_specs.append(
            NativeLinearDimensionSpec(
                id=dimension["id"],
                geometry_primitive_id=primitive_id,
                approved_value_mm=float(dimension["value_mm"]),
                source_ref=dimension["approval"]["reference"],
            )
        )
    covered_line_ids = {origin_primitive_id, x_axis_primitive_id}
    for constraint in selected_constraints:
        covered_line_ids.update(constraint.primitive_ids)
    covered_line_ids.update(driving.primitive_id for driving in driving_lengths)
    uncovered_line_ids = sorted(set(local_lines) - covered_line_ids)
    if uncovered_line_ids:
        blockers.append(
            _blocker(
                "underconstrained",
                "$.primitive_ir.primitives",
                "every LINE participates in the approved pilot model",
                uncovered_line_ids,
            )
        )
    if blockers:
        return _finish_blocked(evidence, blockers)

    result = solve_constraints(
        local_document,
        selected_constraints,
        driving_lengths=driving_lengths,
        datum_anchor=DatumAnchor(
            id=datum["id"],
            origin_primitive_id=origin_primitive_id,
            origin_endpoint=origin_endpoint,
            x_axis_primitive_id=x_axis_primitive_id,
        ),
    )
    evidence["solver"] = {
        "status": result.status,
        "dof": result.dof,
        "model_dof": result.model_dof,
        "applied_constraint_count": result.applied_constraint_count,
        "applied_dimension_count": result.applied_driving_length_count,
        "skipped_constraint_ids": sorted(set(result.skipped_constraints)),
        "conflict_ids": sorted(set(result.conflict_constraint_ids)),
    }
    if result.status == "inconsistent":
        blockers.append(
            _blocker(
                "solver_conflict",
                "$.solver.conflict_ids",
                [],
                evidence["solver"]["conflict_ids"],
            )
        )
    elif result.status != "okay":
        blockers.append(
            _blocker(
                "solver_failed",
                "$.solver.status",
                "okay",
                result.status,
            )
        )
    if (
        result.applied_constraint_count != len(selected_constraints)
        or result.applied_driving_length_count != len(driving_lengths)
        or result.skipped_constraints
    ):
        blockers.append(
            _blocker(
                "solver_failed",
                "$.solver.applied_constraint_count",
                len(selected_constraints) + len(driving_lengths),
                result.applied_constraint_count
                + result.applied_driving_length_count,
            )
        )
    if result.status == "okay" and result.model_dof != 0:
        blockers.append(
            _blocker(
                "underconstrained",
                "$.solver.model_dof",
                0,
                result.model_dof,
            )
        )
    for index, driving in enumerate(driving_lengths):
        residual = result.driving_length_residual_mm.get(driving.id)
        if residual is None or residual > tolerance:
            blockers.append(
                _blocker(
                    "measurement_out_of_tolerance",
                    f"$.dimensions[{index}].value_mm",
                    f"residual <= {tolerance}",
                    residual,
                )
            )
    if blockers:
        return _finish_blocked(evidence, blockers)

    world_solutions = _world_solutions(
        result.solved_primitives,
        primitive_document,
        origin,
        x_axis,
        y_axis,
    )
    build_document = copy.deepcopy(primitive_document)
    blockers.extend(
        _artifact_change_blockers(
            source_path=source_path,
            primitive_ir_path=primitive_ir_path,
            semantic_ir_path=semantic_ir_path,
            source_sha256=source_hash,
            primitive_ir_sha256=primitive_hash,
            semantic_ir_sha256=semantic_hash,
        )
    )
    if blockers:
        return _finish_blocked(evidence, blockers)

    temporary_dxf = output_dxf.with_suffix(output_dxf.suffix + ".tmp")
    if temporary_dxf.exists():
        raise DimensionPilotError(
            f"Temporary DXF output already exists: {temporary_dxf}"
        )
    temporary_created = False
    try:
        with temporary_dxf.open("x"):
            pass
        temporary_created = True
        built = build_dxf(
            build_document,
            str(temporary_dxf),
            semantic_doc=semantic_document,
            solved_primitives=world_solutions,
            build_dimensions=True,
            dimension_specs=dimension_specs,
        )
        dxf_bytes_before_review = temporary_dxf.read_bytes()
        dxf_hash_before_review = hashlib.sha256(dxf_bytes_before_review).hexdigest()
        review = review_dxf(built, tolerance_mm=tolerance)
        dxf_bytes_after_review = temporary_dxf.read_bytes()
        dxf_hash_after_review = hashlib.sha256(dxf_bytes_after_review).hexdigest()
    except (OSError, ValueError) as exc:
        if temporary_created:
            _cleanup_path(temporary_dxf)
        raise DimensionPilotError("Dimension Pilot DXF build failed") from exc

    measurements: list[dict[str, object]] = []
    for driving in driving_lengths:
        solved_line = result.solved_primitives[driving.primitive_id]
        solved_value = math.hypot(
            solved_line.end.x - solved_line.start.x,
            solved_line.end.y - solved_line.start.y,
        )
        readback_value = review.dimension_measurement_by_id.get(driving.id)
        if readback_value is None:
            continue
        measurements.append(
            {
                "dimension_id": driving.id,
                "approved_value_mm": driving.value_mm,
                "solved_value_mm": solved_value,
                "readback_value_mm": readback_value,
                "residual_mm": result.driving_length_residual_mm[driving.id],
            }
        )
    evidence["measurements"] = measurements
    if dxf_hash_before_review != dxf_hash_after_review:
        blockers.append(
            _blocker(
                "headless_review_failed",
                "$.dxf_sha256",
                dxf_hash_before_review,
                dxf_hash_after_review,
            )
        )
    if not review.passed or len(measurements) != len(driving_lengths):
        blockers.append(
            _blocker(
                "headless_review_failed",
                "$.headless_review",
                "all primitive and DIMENSION checks pass",
                review.format_report(),
            )
        )
    blockers.extend(
        _artifact_change_blockers(
            source_path=source_path,
            primitive_ir_path=primitive_ir_path,
            semantic_ir_path=semantic_ir_path,
            source_sha256=source_hash,
            primitive_ir_sha256=primitive_hash,
            semantic_ir_sha256=semantic_hash,
        )
    )
    if blockers:
        _cleanup_path(temporary_dxf)
        return _finish_blocked(evidence, blockers, build_result=built)

    if output_dxf.exists():
        _cleanup_path(temporary_dxf)
        raise DimensionPilotError(f"Output already exists: {output_dxf}")
    try:
        os.rename(temporary_dxf, output_dxf)
    except FileExistsError as exc:
        _cleanup_path(temporary_dxf)
        raise DimensionPilotError(f"Output already exists: {output_dxf}") from exc
    except OSError as exc:
        _cleanup_path(temporary_dxf)
        raise DimensionPilotError(
            f"Output already exists or could not be published: {output_dxf}"
        ) from exc
    temporary_created = False
    try:
        published_hash = _file_hash(output_dxf, label="published output DXF")
    except DimensionPilotError as exc:
        _cleanup_path(output_dxf)
        raise DimensionPilotError("Cannot verify published DXF") from exc
    if published_hash != dxf_hash_after_review:
        _cleanup_path(output_dxf)
        raise DimensionPilotError("published DXF changed after review")
    built.output_path = str(output_dxf)

    evidence["offline_passed"] = True
    evidence["dxf_sha256"] = published_hash
    evidence["blockers"] = []
    try:
        validated_evidence = validate_dimension_evidence(evidence)
    except DimensionPilotContractError as exc:
        raise DimensionPilotError(str(exc)) from exc
    return DimensionPilotRun(evidence=validated_evidence, build_result=built)


def write_dimension_evidence(
    path: Path,
    evidence: Mapping[str, object],
) -> None:
    """Validate and atomically create evidence without replacing any file."""
    target = Path(path)
    if target.exists():
        raise DimensionPilotError(f"Evidence output already exists: {target}")
    try:
        validated = validate_dimension_evidence(evidence)
    except DimensionPilotContractError as exc:
        raise DimensionPilotError(str(exc)) from exc

    temporary = target.with_suffix(target.suffix + ".tmp")
    created = False
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            json.dump(
                validated,
                stream,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
        os.rename(temporary, target)
        created = False
    except FileExistsError as exc:
        raise DimensionPilotError(
            f"Evidence output or temporary file already exists: {target}"
        ) from exc
    except OSError as exc:
        raise DimensionPilotError(f"Cannot create evidence output: {target}") from exc
    finally:
        if created:
            try:
                temporary.unlink()
            except OSError:
                pass


__all__ = [
    "DimensionPilotError",
    "DimensionPilotRun",
    "run_dimension_pilot",
    "to_local",
    "to_world",
    "write_dimension_evidence",
]
