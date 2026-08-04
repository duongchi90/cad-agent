from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.drawing_setup import evaluate_setup_plan
from cad_agent.manifest import sha256_file
from primitive_ir_lib.io_utils import save_document as save_primitive_document
from primitive_ir_lib.models import (
    Calibration,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)
from semantic_ir_lib.io_utils import save_document as save_semantic_document
from semantic_ir_lib.models import Constraint, PrimitiveIRRef, SemanticIRDocument

from drawing_setup_fixtures import approved_setup_plan, matching_setup_audit


def approved_dimension_plan() -> dict[str, object]:
    return {
        "schema_version": "dimension-pilot-plan-1.0",
        "pilot_id": "PILOT-SYNTHETIC-001",
        "view_id": "SIDE",
        "source_sha256": "a" * 64,
        "primitive_ir_sha256": "b" * 64,
        "semantic_ir_sha256": "c" * 64,
        "setup": {
            "evidence_sha256": "d" * 64,
            "setup_plan_sha256": "e" * 64,
            "drawing_profile_sha256": "f" * 64,
            "template_file_sha256": "1" * 64,
        },
        "measurement_tolerance_mm": 0.1,
        "datum": {
            "id": "DATUM-SIDE-001",
            "origin_mm": [0.0, 0.0],
            "origin_attachment": {
                "primitive_id": "line-1",
                "endpoint": "start",
            },
            "x_axis": [1.0, 0.0],
            "y_axis": [0.0, 1.0],
            "x_axis_primitive_id": "line-1",
            "status": "APPROVED",
            "approval": {
                "approved_by": "OWNER",
                "reference": "DATUM-APPROVAL-001",
            },
        },
        "dimensions": [
            {
                "id": "DIM-001",
                "kind": "linear",
                "value_mm": 80.0,
                "role": "driving",
                "from": {"primitive_id": "line-1", "endpoint": "start"},
                "to": {"primitive_id": "line-1", "endpoint": "end"},
                "status": "APPROVED",
                "approval": {
                    "approved_by": "OWNER",
                    "reference": "DIM-APPROVAL-001",
                },
            }
        ],
        "constraint_ids": [],
        "approval": {
            "approved_by": "OWNER",
            "reference": "PILOT-APPROVAL-001",
        },
    }


def offline_dimension_evidence() -> dict[str, object]:
    return {
        "schema_version": "dimension-pilot-evidence-1.0",
        "pilot_id": "PILOT-SYNTHETIC-001",
        "offline_passed": True,
        "acceptance": "NOT_RUN",
        "plan_sha256": "2" * 64,
        "setup_evidence_sha256": "d" * 64,
        "source_sha256": "a" * 64,
        "primitive_ir_sha256": "b" * 64,
        "semantic_ir_sha256": "c" * 64,
        "dxf_sha256": "3" * 64,
        "solver": {
            "status": "okay",
            "dof": 6,
            "model_dof": 0,
            "applied_constraint_count": 0,
            "applied_dimension_count": 1,
            "skipped_constraint_ids": [],
            "conflict_ids": [],
        },
        "measurements": [
            {
                "dimension_id": "DIM-001",
                "approved_value_mm": 80.0,
                "solved_value_mm": 80.0,
                "readback_value_mm": 80.0,
                "residual_mm": 0.0,
            }
        ],
        "blockers": [],
    }


def set_nested(
    payload: dict[str, object],
    path: tuple[object, ...],
    value: object,
) -> None:
    current: Any = payload
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value


def copied_plan() -> dict[str, object]:
    return copy.deepcopy(approved_dimension_plan())


def _line(
    primitive_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
) -> Primitive:
    return Primitive(
        id=primitive_id,
        type="line",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=LineGeometry(
            start=Point2D(*start),
            end=Point2D(*end),
        ),
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def rebind_artifact_hashes(inputs: SimpleNamespace) -> None:
    semantic = json.loads(inputs.semantic_ir.read_text(encoding="utf-8"))
    primitive_hash = sha256_file(inputs.primitive_ir)
    semantic["primitive_ir_ref"]["sha256"] = primitive_hash
    _write_json(inputs.semantic_ir, semantic)
    inputs.plan["primitive_ir_sha256"] = primitive_hash
    inputs.plan["semantic_ir_sha256"] = sha256_file(inputs.semantic_ir)
    _write_json(inputs.plan_path, inputs.plan)


def write_dimension_pilot_inputs(
    root: Path,
    *,
    disconnected: bool = False,
    conflicting: bool = False,
) -> SimpleNamespace:
    root.mkdir(parents=True, exist_ok=True)
    source = root / "approved-source-export.json"
    source.write_text('{"synthetic": true}\n', encoding="utf-8")
    source_hash = sha256_file(source)

    lines = [_line("line-1", (0.0, 0.0), (100.0, 0.0))]
    dimensions = copy.deepcopy(approved_dimension_plan()["dimensions"])
    constraints: list[Constraint] = []
    constraint_ids: list[str] = []
    if disconnected or conflicting:
        lines.append(_line("line-2", (0.0, 20.0), (100.0, 20.0)))
        dimensions.append(
            {
                "id": "DIM-002",
                "kind": "linear",
                "value_mm": 40.0 if disconnected else 100.0,
                "role": "driving",
                "from": {"primitive_id": "line-2", "endpoint": "start"},
                "to": {"primitive_id": "line-2", "endpoint": "end"},
                "status": "APPROVED",
                "approval": {
                    "approved_by": "OWNER",
                    "reference": "DIM-APPROVAL-002",
                },
            }
        )
    if conflicting:
        constraint = Constraint(
            id="constraint-equal",
            type="equal_length",
            primitive_ids=["line-1", "line-2"],
            confidence=1.0,
            tolerance={},
        )
        constraints.append(constraint)
        constraint_ids.append(constraint.id)

    primitive_document = PrimitiveIRDocument(
        source_document=SourceDocument(
            file_name=source.name,
            page_index=0,
            image_width_px=100,
            image_height_px=100,
            sha256=source_hash,
        ),
        calibration=Calibration(
            unit="mm",
            pixel_to_unit_scale=1.0,
            origin_px=(0.0, 0.0),
            method="manual_override",
            status="verified",
            source_sha256=source_hash,
        ),
        primitives=lines,
    )
    primitive_ir = root / "primitive-ir.json"
    save_primitive_document(primitive_document, str(primitive_ir))
    primitive_hash = sha256_file(primitive_ir)

    semantic_document = SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(
            file_name=primitive_ir.name,
            primitive_count=len(lines),
            sha256=primitive_hash,
        ),
        constraints=constraints,
    )
    semantic_ir = root / "semantic-ir.json"
    save_semantic_document(semantic_document, str(semantic_ir))

    setup_plan = approved_setup_plan()
    setup_audit = matching_setup_audit(setup_plan)
    setup_evidence = evaluate_setup_plan(
        setup_plan,
        setup_audit,
        verified_by="SYNTHETIC-OWNER",
        approval_reference="SYNTHETIC-SETUP-001",
    )
    setup_plan_path = root / "drawing-setup-plan.json"
    setup_evidence_path = root / "drawing-setup-evidence.json"
    _write_json(setup_plan_path, setup_plan)
    _write_json(setup_evidence_path, setup_evidence)

    plan = approved_dimension_plan()
    plan["source_sha256"] = source_hash
    plan["primitive_ir_sha256"] = primitive_hash
    plan["semantic_ir_sha256"] = sha256_file(semantic_ir)
    plan["dimensions"] = dimensions
    plan["constraint_ids"] = constraint_ids
    plan["setup"] = {
        "evidence_sha256": canonical_json_sha256(setup_evidence),
        "setup_plan_sha256": canonical_json_sha256(setup_plan),
        "drawing_profile_sha256": setup_evidence["drawing_profile_sha256"],
        "template_file_sha256": setup_evidence["template_file_sha256"],
    }
    plan_path = root / "dimension-pilot-plan.json"
    _write_json(plan_path, plan)
    return SimpleNamespace(
        root=root,
        source=source,
        primitive_ir=primitive_ir,
        semantic_ir=semantic_ir,
        setup_plan=setup_plan,
        setup_plan_path=setup_plan_path,
        setup_evidence=setup_evidence,
        setup_evidence_path=setup_evidence_path,
        plan=plan,
        plan_path=plan_path,
        output_dxf=root / "dimension-pilot.dxf",
        output_evidence=root / "dimension-pilot-evidence.json",
    )


def dimension_pilot_cli_args(inputs: SimpleNamespace) -> list[str]:
    return [
        "dimension-pilot-run",
        "--plan",
        str(inputs.plan_path),
        "--setup-plan",
        str(inputs.setup_plan_path),
        "--setup-evidence",
        str(inputs.setup_evidence_path),
        "--source",
        str(inputs.source),
        "--primitive-ir",
        str(inputs.primitive_ir),
        "--semantic-ir",
        str(inputs.semantic_ir),
        "--output-dxf",
        str(inputs.output_dxf),
        "--output-evidence",
        str(inputs.output_evidence),
    ]
