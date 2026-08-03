from __future__ import annotations

import copy

from primitive_ir_lib.models import (
    Calibration,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)

from semantic_ir_lib.constraint_ir import (
    ApprovalRegister,
    ConstraintObservation,
    constraint_register_sha256,
)
from semantic_ir_lib.datum_ir import datum_register_sha256
from semantic_ir_lib.dimension_ir import (
    DimensionObservation,
    canonical_json_sha256,
    dimension_register_sha256,
)
from semantic_ir_lib.solver_gate import solve_authoritative_model


def _line(id_: str, x0: float, y0: float, x1: float, y1: float) -> Primitive:
    return Primitive(
        id=id_,
        type="line",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 100, 100)),
        geometry=LineGeometry(start=Point2D(x0, y0), end=Point2D(x1, y1)),
    )


def _doc(*lines: Primitive) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(
            file_name="synthetic.png",
            page_index=0,
            image_width_px=100,
            image_height_px=100,
        ),
        calibration=Calibration(
            unit="mm",
            pixel_to_unit_scale=1.0,
            origin_px=(0, 0),
            method="manual_override",
        ),
        primitives=list(lines),
    )


def _dimension(value: float, *, tolerance_mm: float = 0.01) -> DimensionObservation:
    return DimensionObservation(
        id="DIM-001",
        value=value,
        unit="mm",
        kind="horizontal_distance",
        view_id="MODEL",
        from_ref="primitive:l1:start",
        to_ref="primitive:l1:end",
        role="driving",
        status="APPROVED",
        provenance="SYNTHETIC_APPROVED",
    )


def _constraint(
    constraint_id: str = "CON-001",
    *,
    kind: str = "parallel",
    refs: tuple[str, ...] = ("primitive:l1", "primitive:l2"),
) -> ConstraintObservation:
    return ConstraintObservation(
        id=constraint_id,
        kind=kind,
        refs=refs,
        tolerance_mm=0.01,
        source_refs=("SRC-001",),
        provenance="SYNTHETIC_APPROVED",
        status="APPROVED",
    )


def _setup() -> tuple[dict[str, object], str, str, str]:
    plan_hash, profile_hash, template_hash = "1" * 64, "2" * 64, "3" * 64
    evidence: dict[str, object] = {
        "schema_version": "drawing-setup-evidence-1.0",
        "status": "SETUP_VERIFIED",
        "setup_plan_sha256": plan_hash,
        "drawing_profile_sha256": profile_hash,
        "template_file_sha256": template_hash,
        "blockers": [],
    }
    return evidence, plan_hash, profile_hash, template_hash


def _approval(
    evidence: dict[str, object],
    dimensions: list[DimensionObservation],
    datums: list,
    constraints: list[ConstraintObservation],
    *,
    constraints_hash: str | None = None,
    approved_ids: tuple[str, ...] | None = None,
) -> ApprovalRegister:
    return ApprovalRegister(
        setup_evidence_sha256=canonical_json_sha256(evidence),
        dimensions_sha256=dimension_register_sha256(dimensions),
        datums_sha256=datum_register_sha256(datums),
        constraints_sha256=constraints_hash or constraint_register_sha256(constraints),
        approval_reference="M3-SYNTHETIC-001",
        approved_by="ENGINEER",
        approved_ids=approved_ids if approved_ids is not None else tuple(
            item.id for item in [*dimensions, *datums, *constraints]
        ),
        rejected_ids=(),
        policy_version="dimension-first-policy-1.0",
    )


def _solve(
    doc: PrimitiveIRDocument,
    dimensions: list[DimensionObservation],
    constraints: list[ConstraintObservation],
    *,
    evidence: dict[str, object] | None = None,
    approval: ApprovalRegister | None = None,
):
    evidence = evidence or _setup()[0]
    setup_evidence, plan_hash, profile_hash, template_hash = _setup()
    datums: list = []
    approval = approval or _approval(evidence, dimensions, datums, constraints)
    return solve_authoritative_model(
        primitive_document=doc,
        dimensions=dimensions,
        datums=datums,
        constraints=constraints,
        approval=approval,
        setup_evidence=evidence,
        setup_plan_sha256=plan_hash,
        drawing_profile_sha256=profile_hash,
        template_file_sha256=template_hash,
    )


def test_in_tolerance_dimension_emits_solved_hash_bound_model():
    doc = _doc(_line("l1", 0, 0, 100, 0))
    report, model = _solve(doc, [_dimension(100.0)], [])

    assert report["status"] == "SOLVED"
    assert report["max_residual_mm"] == 0.0
    assert model is not None
    assert model.dimensions_sha256 == report["dimensions_sha256"]


def test_out_of_tolerance_dimension_is_a_blocker_and_has_no_model():
    doc = _doc(_line("l1", 0, 0, 100, 0))
    dimension = _dimension(101.0, tolerance_mm=0.1)
    report, model = _solve(doc, [dimension], [])

    assert report["status"] == "NEEDS_REVIEW"
    assert any(blocker["code"] == "residual_exceeds_tolerance" for blocker in report["blockers"])
    assert model is None


def test_parallel_lines_with_remaining_dof_are_underconstrained():
    doc = _doc(
        _line("l1", 0, 0, 100, 0),
        _line("l2", 0, 50, 100, 0),
    )
    report, model = _solve(doc, [], [_constraint()])

    assert report["status"] == "UNDERCONSTRAINED"
    assert report["degrees_of_freedom"]["MODEL"] > 0
    assert model is None


def test_parallel_and_perpendicular_same_pair_is_conflict():
    doc = _doc(
        _line("l1", 0, 0, 100, 0),
        _line("l2", 0, 50, 100, 50),
    )
    constraints = [_constraint(), _constraint("CON-002", kind="perpendicular")]
    report, model = _solve(doc, [], constraints)

    assert report["status"] == "CONFLICT"
    assert any(blocker["code"] == "constraint_conflict" for blocker in report["blockers"])
    assert model is None


def test_stale_setup_evidence_fails_closed_before_solving():
    evidence, plan_hash, profile_hash, template_hash = _setup()
    evidence["status"] = "NEEDS_REVIEW"
    doc = _doc(_line("l1", 0, 0, 100, 0))
    dimensions: list[DimensionObservation] = []
    constraints: list[ConstraintObservation] = []
    approval = _approval(evidence, dimensions, [], constraints)

    report, model = solve_authoritative_model(
        primitive_document=doc,
        dimensions=dimensions,
        datums=[],
        constraints=constraints,
        approval=approval,
        setup_evidence=evidence,
        setup_plan_sha256=plan_hash,
        drawing_profile_sha256=profile_hash,
        template_file_sha256=template_hash,
    )

    assert report["status"] == "NEEDS_REVIEW"
    assert any(blocker["code"] == "stale_setup_evidence" for blocker in report["blockers"])
    assert model is None


def test_mismatched_register_hash_is_refused():
    evidence, _, _, _ = _setup()
    doc = _doc(_line("l1", 0, 0, 100, 0))
    constraint = _constraint()
    approval = _approval(evidence, [], [], [constraint], constraints_hash="f" * 64)

    report, model = _solve(doc, [], [constraint], approval=approval)

    assert report["status"] == "NEEDS_REVIEW"
    assert any(blocker["code"] == "input_hash_mismatch" for blocker in report["blockers"])
    assert model is None


def test_unsupported_relation_and_dangling_reference_are_explicit_blockers():
    doc = _doc(_line("l1", 0, 0, 100, 0))
    unsupported = _constraint(
        kind="distance",
        refs=("primitive:l1", "primitive:l1"),
    )
    unsupported = ConstraintObservation(
        id=unsupported.id,
        kind=unsupported.kind,
        refs=unsupported.refs,
        value=10.0,
        unit="mm",
        tolerance_mm=unsupported.tolerance_mm,
        source_refs=unsupported.source_refs,
        provenance=unsupported.provenance,
        status=unsupported.status,
    )
    report, model = _solve(doc, [], [unsupported])
    assert report["status"] == "NEEDS_REVIEW"
    assert any(blocker["code"] == "constraint_unsupported" for blocker in report["blockers"])
    assert model is None

    dangling = _constraint(refs=("primitive:l1", "primitive:missing"))
    report, model = _solve(doc, [], [dangling])
    assert report["status"] == "NEEDS_REVIEW"
    assert any(blocker["code"] == "constraint_unresolved" for blocker in report["blockers"])
    assert model is None


def test_solver_gate_does_not_mutate_input_objects():
    doc = _doc(_line("l1", 0, 0, 100, 0))
    dimensions = [_dimension(100.0)]
    constraints: list[ConstraintObservation] = []
    before_doc = copy.deepcopy(doc.to_dict())
    before_dimensions = copy.deepcopy(dimensions)
    before_constraints = copy.deepcopy(constraints)

    _solve(doc, dimensions, constraints)

    assert doc.to_dict() == before_doc
    assert dimensions == before_dimensions
    assert constraints == before_constraints
