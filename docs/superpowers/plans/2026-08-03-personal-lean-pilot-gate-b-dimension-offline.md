# Personal Lean Pilot Gate B: Offline Dimension Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build the smallest deterministic one-view linear-dimension pilot that reuses the existing solver and DXF builder, measures native dimensions back headlessly, and remains ineligible for Gate B acceptance while AutoCAD Mechanical 2027 Gate A is open.

**Architecture:** Add strict plan/evidence contracts at the cad_agent boundary. Adapt approved line-endpoint attachments into driving-length and datum-anchor inputs for the existing semantic_ir_lib.solve_constraints() function, then feed its solved geometry into the existing dxf_builder_lib build/review path. The offline command always records acceptance as NOT_RUN and requires real, fresh SETUP_VERIFIED evidence outside tests before it may generate a private candidate.

**Tech Stack:** Windows, Python 3.11, JSON Schema 2020-12, pytest, python-solvespace 3.0.8, ezdxf 1.4.4, PowerShell.

## Global Constraints

- AutoCAD Mechanical 2027 remains the only supported AutoCAD acceptance target; do not use AutoCAD 2018 as substitute evidence.
- Keep the owner-provided DWG, its copy, derived CAD files, raw audit output, private annotations, and workstation path outside Git.
- Never open, save, repair, convert, or overwrite the original DWG during this plan.
- Gate A remains open. This plan must not emit SETUP_VERIFIED, PERSONAL_VERIFIED, RELEASED, or any new product status.
- Acceptance order remains Gate A, then Gate B, then Gate C. This plan produces only an offline implementation candidate.
- Production execution requires fresh real SETUP_VERIFIED evidence. Synthetic setup evidence is allowed only under tests.
- The plan supports approved linear dimensions for one view, one explicit datum frame, and a required positive measurement tolerance in millimetres. It does not infer a datum.
- Do not add a DWG parser, second solver, second DXF builder, generic Operation Plan engine, search subsystem, automatic segmentation, or cross-view behavior.
- Use one writer and TDD for every behavior change.
- Because semantic constraints are extended, the affected private real_data benchmark is required when an approved compatible export exists. Otherwise record it as NOT RUN; an unavailable-state probe is not acceptance.
- Run scripts/verify.ps1 once when closing this offline implementation batch, using only its explicit .NET skip option if .NET remains unavailable.

---

## Existing boundaries to reuse

| Boundary | Classification | Use in this plan |
|---|---|---|
| cad_agent.drawing_setup.require_setup_verified | Reuse as-is | Refuse missing, blocked, or stale Gate A evidence |
| semantic_ir_lib.constraint_solving.solve_constraints | Extend with tests | Add driving lengths and one explicit datum anchor to the same SolverSystem |
| primitive_ir_lib PrimitiveIRDocument | Reuse as-is | Supply approved line geometry; do not add a second IR |
| dxf_builder_lib.builder.build_dxf | Extend with tests | Accept approved native linear-dimension specs while preserving CrossValidation compatibility |
| dxf_builder_lib.reviewer.review_dxf | Extend with tests | Measure native DIMENSION values back against the approved tolerance |
| cad_agent.cli | Extend with tests | Expose one strict offline command with hash and overwrite guards |
| Owner-provided sample DWG | Private external input | Hash and copy only; no content claim without a compatible approved export |

Baseline evidence before implementation:

    .\.venv-py311\Scripts\python.exe -m pytest semantic_ir_lib\tests\test_constraint_solving.py dxf_builder_lib\tests\test_builder.py tests\test_cad_agent_drawing_setup.py -q -p no:cacheprovider

Expected at plan creation: 81 passed.

---

### Task 1: Add strict Dimension Pilot plan and evidence contracts

**Files:**

- Create: contracts/dimension-pilot/dimension-pilot-plan.schema.json
- Create: contracts/dimension-pilot/dimension-pilot-evidence.schema.json
- Create: contracts/dimension-pilot/examples/dimension-pilot-plan.json
- Create: contracts/dimension-pilot/examples/dimension-pilot-evidence.json
- Create: cad_agent/dimension_contracts.py
- Create: tests/dimension_pilot_fixtures.py
- Create: tests/test_dimension_pilot_contracts.py

**Interfaces:**

- Produces: DimensionPilotContractError
- Produces: validate_dimension_plan(payload: Mapping[str, object]) -> dict[str, object]
- Produces: validate_dimension_evidence(payload: Mapping[str, object]) -> dict[str, object]
- Produces: read_dimension_contract(path: Path, *, contract: Literal["plan", "evidence"]) -> dict[str, object]
- Reuses: cad_agent.drawing_contracts.canonical_json_sha256
- Test fixture: approved_dimension_plan() -> dict[str, object]
- Test fixture: offline_dimension_evidence() -> dict[str, object]
- Test fixture: set_nested(payload: dict, path: tuple[object, ...], value: object) -> None
- Test fixture: write_dimension_pilot_inputs(root: Path, *, disconnected: bool = False, conflicting: bool = False) -> SimpleNamespace
- Test fixture: rebind_artifact_hashes(inputs: SimpleNamespace) -> None

The plan contract has exactly these top-level properties:

    schema_version
    pilot_id
    view_id
    source_sha256
    primitive_ir_sha256
    semantic_ir_sha256
    setup
    measurement_tolerance_mm
    datum
    dimensions
    constraint_ids
    approval

The setup object has exactly:

    evidence_sha256
    setup_plan_sha256
    drawing_profile_sha256
    template_file_sha256

The datum object has exactly:

    id
    origin_mm
    origin_attachment
    x_axis
    y_axis
    x_axis_primitive_id
    status
    approval

An attachment has exactly primitive_id and endpoint, where endpoint is start or end. A dimension has exactly id, kind, value_mm, role, from, to, status, and approval. kind is linear, role is driving, status is APPROVED, value_mm is finite and positive, and from/to must name the same line with opposite endpoints. Arrays origin_mm, x_axis, and y_axis contain exactly two finite numbers. Axis vectors must have unit length within 1e-9, be orthogonal within 1e-9, and have positive two-dimensional cross product. IDs and dimension attachment pairs are unique. constraint_ids may be an empty list; every present item must be a unique non-empty identifier.

The evidence contract has exactly:

    schema_version
    pilot_id
    offline_passed
    acceptance
    plan_sha256
    setup_evidence_sha256
    source_sha256
    primitive_ir_sha256
    semantic_ir_sha256
    dxf_sha256
    solver
    measurements
    blockers

acceptance is always NOT_RUN in this plan. solver contains status, dof, model_dof, applied_constraint_count, applied_dimension_count, skipped_constraint_ids, and conflict_ids. Each measurement contains dimension_id, approved_value_mm, solved_value_mm, readback_value_mm, and residual_mm. Each blocker contains code, path, expected, and actual. offline_passed=true requires an empty blocker list, a lowercase SHA-256 dxf_sha256, solver.status=okay, solver.model_dof=0, and at least one measurement. offline_passed=false permits dxf_sha256=null.

- [ ] **Step 1: Write contract tests first**

Create tests with these concrete cases:

    def test_example_contracts_match_runtime_and_json_schema() -> None:
        plan = read_dimension_contract(EXAMPLES / "dimension-pilot-plan.json", contract="plan")
        evidence = read_dimension_contract(EXAMPLES / "dimension-pilot-evidence.json", contract="evidence")
        assert plan["schema_version"] == "dimension-pilot-plan-1.0"
        assert evidence["schema_version"] == "dimension-pilot-evidence-1.0"
        assert evidence["acceptance"] == "NOT_RUN"


    @pytest.mark.parametrize(
        ("path", "value", "message"),
        [
            (("measurement_tolerance_mm",), 0.0, "positive"),
            (("datum", "x_axis"), [2.0, 0.0], "unit"),
            (("datum", "y_axis"), [1.0, 0.0], "orthogonal"),
            (("datum", "y_axis"), [0.0, -1.0], "right-handed"),
            (("dimensions", 0, "kind"), "radius", "linear"),
            (("dimensions", 0, "status"), "UNRESOLVED", "APPROVED"),
            (("dimensions", 0, "to", "endpoint"), "start", "opposite"),
        ],
    )
    def test_plan_rejects_unsafe_values(path, value, message) -> None:
        payload = approved_dimension_plan()
        set_nested(payload, path, value)
        with pytest.raises(DimensionPilotContractError, match=message):
            validate_dimension_plan(payload)


    def test_plan_rejects_duplicate_dimension_attachment() -> None:
        payload = approved_dimension_plan()
        duplicate = copy.deepcopy(payload["dimensions"][0])
        duplicate["id"] = "DIM-002"
        duplicate["approval"]["reference"] = "DIM-APPROVAL-002"
        payload["dimensions"].append(duplicate)
        with pytest.raises(DimensionPilotContractError, match="attachment"):
            validate_dimension_plan(payload)


    def test_evidence_cannot_claim_acceptance_or_pass_with_blockers() -> None:
        payload = offline_dimension_evidence()
        payload["acceptance"] = "PASS"
        with pytest.raises(DimensionPilotContractError, match="NOT_RUN"):
            validate_dimension_evidence(payload)
        payload = offline_dimension_evidence()
        payload["blockers"] = [{"code": "x", "path": "$", "expected": None, "actual": None}]
        with pytest.raises(DimensionPilotContractError, match="offline_passed"):
            validate_dimension_evidence(payload)

- [ ] **Step 2: Run RED**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest tests\test_dimension_pilot_contracts.py -q -p no:cacheprovider

Expected: collection fails because cad_agent.dimension_contracts does not exist.

- [ ] **Step 3: Add complete schemas, examples, fixtures, and pure-Python validators**

Use a synthetic example shaped exactly like:

    {
      "schema_version": "dimension-pilot-plan-1.0",
      "pilot_id": "PILOT-SYNTHETIC-001",
      "view_id": "SIDE",
      "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "primitive_ir_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "semantic_ir_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "setup": {
        "evidence_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        "setup_plan_sha256": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        "drawing_profile_sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        "template_file_sha256": "1111111111111111111111111111111111111111111111111111111111111111"
      },
      "measurement_tolerance_mm": 0.1,
      "datum": {
        "id": "DATUM-SIDE-001",
        "origin_mm": [0.0, 0.0],
        "origin_attachment": {"primitive_id": "line-1", "endpoint": "start"},
        "x_axis": [1.0, 0.0],
        "y_axis": [0.0, 1.0],
        "x_axis_primitive_id": "line-1",
        "status": "APPROVED",
        "approval": {"approved_by": "OWNER", "reference": "DATUM-APPROVAL-001"}
      },
      "dimensions": [{
        "id": "DIM-001",
        "kind": "linear",
        "value_mm": 80.0,
        "role": "driving",
        "from": {"primitive_id": "line-1", "endpoint": "start"},
        "to": {"primitive_id": "line-1", "endpoint": "end"},
        "status": "APPROVED",
        "approval": {"approved_by": "OWNER", "reference": "DIM-APPROVAL-001"}
      }],
      "constraint_ids": [],
      "approval": {"approved_by": "OWNER", "reference": "PILOT-APPROVAL-001"}
    }

Implement strict key checking, finite-number checking, lowercase SHA-256 checking, ID checking, approval checking, axis normalization, right-handedness, attachment resolution shape, duplicate ID refusal, and evidence invariants. Return deep-copied validated dictionaries so callers cannot mutate fixture objects through returned aliases.

write_dimension_pilot_inputs() creates only synthetic text/JSON/DXF-output paths under root. It builds a verified synthetic Drawing Setup mapping from tests.drawing_setup_fixtures, one PrimitiveIR LINE from [0, 0] to [100, 0], a SemanticIRDocument whose primitive_ir_ref.sha256 matches the Primitive IR file, a plan whose file hashes match all synthetic inputs, and non-existing output paths. rebind_artifact_hashes() rewrites the Semantic IR primitive reference to the current Primitive IR SHA-256, then updates the plan's primitive_ir_sha256 and semantic_ir_sha256. It deliberately does not rewrite PrimitiveIRDocument.source_document.sha256, so provenance-mismatch tests remain meaningful.

- [ ] **Step 4: Run GREEN and the existing Drawing Setup contract suite**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest tests\test_dimension_pilot_contracts.py tests\test_drawing_setup_contracts.py -q -p no:cacheprovider

Expected: PASS.

- [ ] **Step 5: Commit**

    git add contracts/dimension-pilot cad_agent/dimension_contracts.py tests/dimension_pilot_fixtures.py tests/test_dimension_pilot_contracts.py
    git commit -m "feat: add offline dimension pilot contracts"

---

### Task 2: Extend the existing solver with driving lengths and one datum anchor

**Files:**

- Modify: semantic_ir_lib/constraint_solving.py
- Modify: semantic_ir_lib/tests/test_constraint_solving.py

**Interfaces:**

- Produces: DrivingLengthConstraint(id: str, primitive_id: str, value_mm: float)
- Produces: DatumAnchor(id: str, origin_primitive_id: str, origin_endpoint: Literal["start", "end"], x_axis_primitive_id: str)
- Extends: solve_constraints(primitive_doc, constraints, *, driving_lengths=(), datum_anchor=None) -> SolveResult
- Extends SolveResult with model_dof, applied_driving_length_count, driving_length_residual_mm, and conflict_constraint_ids
- Preserves every existing two-positional-argument caller

The same SolverSystem remains authoritative. For each DrivingLengthConstraint, call sys.distance() between the chosen line's start and end points. For the DatumAnchor, call sys.dragged() on the named origin endpoint and sys.horizontal() on the named X-axis line. The cad_agent adapter in Task 4 supplies geometry already transformed into datum-local coordinates.

Track SolveSpace constraint handles because its methods return None: record sys.cons_len before each call, call the constraint method, then map every new integer handle from before+1 through sys.cons_len to the source constraint ID. Map sys.failures() back to sorted unique source IDs.

After the datum constraints, model_dof is max(0, sys.dof() - 6). The subtraction removes only the six fixed SolveSpace work-plane parameters; the datum constraints themselves remove the three global planar rigid-body degrees of freedom. Without a datum anchor, model_dof is None.

- [ ] **Step 1: Add failing solver tests**

    def test_driving_length_and_datum_anchor_close_one_line_model() -> None:
        line = _line("line-1", 0, 0, 100, 0)
        result = solve_constraints(
            _doc(line),
            [],
            driving_lengths=[
                DrivingLengthConstraint(id="DIM-001", primitive_id="line-1", value_mm=80.0)
            ],
            datum_anchor=DatumAnchor(
                id="DATUM-001",
                origin_primitive_id="line-1",
                origin_endpoint="start",
                x_axis_primitive_id="line-1",
            ),
        )
        solved = result.solved_primitives["line-1"]
        assert result.status == "okay"
        assert result.dof == 6
        assert result.model_dof == 0
        assert result.applied_driving_length_count == 1
        assert result.driving_length_residual_mm == {"DIM-001": 0.0}
        assert hypot(solved.end.x - solved.start.x, solved.end.y - solved.start.y) == pytest.approx(80.0)


    def test_two_conflicting_driving_lengths_report_both_ids() -> None:
        line = _line("line-1", 0, 0, 100, 0)
        result = solve_constraints(
            _doc(line),
            [],
            driving_lengths=[
                DrivingLengthConstraint("DIM-080", "line-1", 80.0),
                DrivingLengthConstraint("DIM-100", "line-1", 100.0),
            ],
            datum_anchor=DatumAnchor("DATUM-001", "line-1", "start", "line-1"),
        )
        assert result.status == "inconsistent"
        assert {"DIM-080", "DIM-100"} <= set(result.conflict_constraint_ids)


    def test_disconnected_driven_line_remains_underconstrained() -> None:
        lines = [_line("line-1", 0, 0, 80, 0), _line("line-2", 0, 20, 40, 20)]
        result = solve_constraints(
            _doc(*lines),
            [],
            driving_lengths=[
                DrivingLengthConstraint("DIM-001", "line-1", 80.0),
                DrivingLengthConstraint("DIM-002", "line-2", 40.0),
            ],
            datum_anchor=DatumAnchor("DATUM-001", "line-1", "start", "line-1"),
        )
        assert result.status == "okay"
        assert result.model_dof > 0


    @pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf")])
    def test_driving_length_rejects_nonpositive_or_nonfinite_value(value: float) -> None:
        with pytest.raises(ValueError, match="finite positive"):
            solve_constraints(
                _doc(_line("line-1", 0, 0, 100, 0)),
                [],
                driving_lengths=[DrivingLengthConstraint("DIM-001", "line-1", value)],
            )

- [ ] **Step 2: Run RED**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest semantic_ir_lib\tests\test_constraint_solving.py -q -p no:cacheprovider

Expected: import fails because DrivingLengthConstraint and DatumAnchor are undefined.

- [ ] **Step 3: Add the backward-compatible dataclasses and solver inputs**

Add:

    @dataclass(frozen=True)
    class DrivingLengthConstraint:
        id: str
        primitive_id: str
        value_mm: float


    @dataclass(frozen=True)
    class DatumAnchor:
        id: str
        origin_primitive_id: str
        origin_endpoint: Literal["start", "end"]
        x_axis_primitive_id: str


    @dataclass
    class SolveResult:
        status: str
        dof: int
        solved_primitives: Dict[str, SolvedPrimitive] = field(default_factory=dict)
        skipped_constraints: List[str] = field(default_factory=list)
        applied_constraint_count: int = 0
        model_dof: int | None = None
        applied_driving_length_count: int = 0
        driving_length_residual_mm: Dict[str, float] = field(default_factory=dict)
        conflict_constraint_ids: List[str] = field(default_factory=list)

Validate non-empty unique IDs, finite positive values, existing LINE primitive attachments, a valid origin endpoint, and an existing X-axis LINE. Invalid API input raises ValueError before SolverSystem construction. Keep the existing 1,000-unknown capacity guard and include lines referenced only by driving lengths or the datum in relevant_ids.

- [ ] **Step 4: Add handle mapping, datum constraints, residual calculation, and conflict reporting**

Use this handle-capture pattern around every semantic, dimension, and datum constraint:

    def _capture_constraint_handles(system, source_id: str, action, mapping: dict[int, str]) -> None:
        before = system.cons_len
        action()
        for handle in range(before + 1, system.cons_len + 1):
            mapping[handle] = source_id

After solve, compute each actual line length from solved coordinates and store:

    residuals[item.id] = round(abs(actual_length - item.value_mm), 9)

For the final solve attempt:

    conflict_ids = sorted({
        constraint_id_by_handle[handle]
        for handle in system.failures()
        if handle in constraint_id_by_handle
    })

Preserve the existing retry ordering for semantic constraints. Append driving lengths and datum constraints after each reordered semantic list so every attempt uses identical approved driving data.

- [ ] **Step 5: Run GREEN plus pruning and assembly regressions**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest semantic_ir_lib\tests\test_constraint_solving.py semantic_ir_lib\tests\test_constraint_pruning.py semantic_ir_lib\tests\test_semantic_ir.py -q -p no:cacheprovider

Expected: PASS and all pre-existing solve_constraints callers remain valid.

- [ ] **Step 6: Commit**

    git add semantic_ir_lib/constraint_solving.py semantic_ir_lib/tests/test_constraint_solving.py
    git commit -m "feat: solve approved pilot dimensions"

---

### Task 3: Extend native DXF generation and read-back for approved values

**Files:**

- Modify: dxf_builder_lib/builder.py
- Modify: dxf_builder_lib/reviewer.py
- Modify: dxf_builder_lib/tests/test_builder.py
- Modify: dxf_builder_lib/tests/test_reviewer.py

**Interfaces:**

- Produces: NativeLinearDimensionSpec(id: str, geometry_primitive_id: str, approved_value_mm: float | None, source_ref: str)
- Extends: build_dxf(..., dimension_specs: Sequence[NativeLinearDimensionSpec] | None = None) -> BuildResult
- Extends ReviewResult with dimension_measurement_by_id: Dict[str, float]
- Reuses existing build_dimensions=True behavior when dimension_specs is None
- Preserves cad_agent.live BuildResult serialization compatibility

dimension_specs=None adapts existing confirmed CrossValidation records into NativeLinearDimensionSpec objects keyed by the existing CrossValidation ID. An explicit dimension_specs sequence is used by Gate B and must not be combined with implicit unverified records.

- [ ] **Step 1: Add failing builder/reviewer tests**

    def test_approved_native_dimension_is_measured_against_approved_value() -> None:
        document = _doc(_line("line-1", 0, 0, 80, 0))
        spec = NativeLinearDimensionSpec(
            id="DIM-001",
            geometry_primitive_id="line-1",
            approved_value_mm=80.0,
            source_ref="PILOT-SYNTHETIC-001",
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "pilot.dxf")
            built = build_dxf(
                document,
                output,
                build_dimensions=True,
                dimension_specs=[spec],
            )
            review = review_dxf(built, tolerance_mm=0.1)
            assert review.passed
            assert review.dimension_measurement_by_id["DIM-001"] == pytest.approx(80.0)
            assert built.written_dimension_by_cross_validation_id["DIM-001"] == {
                "layer": "DIMENSIONS",
                "measurement": 80.0,
                "approved_value_mm": 80.0,
                "geometry_primitive_id": "line-1",
                "source_ref": "PILOT-SYNTHETIC-001",
            }


    def test_readback_rejects_geometry_outside_approved_tolerance() -> None:
        document = _doc(_line("line-1", 0, 0, 81, 0))
        spec = NativeLinearDimensionSpec("DIM-001", "line-1", 80.0, "PILOT-001")
        with tempfile.TemporaryDirectory() as tmp:
            built = build_dxf(
                document,
                os.path.join(tmp, "pilot.dxf"),
                build_dimensions=True,
                dimension_specs=[spec],
            )
            review = review_dxf(built, tolerance_mm=0.1)
            assert not review.passed
            assert any("approved measurement" in item for item in review.dimension_mismatches)


    def test_legacy_confirmed_cross_validation_path_remains_compatible() -> None:
        document = _doc(_line("line-1", 0, 0, 50, 0))
        document.cross_validations = [
            CrossValidation(
                "text-1",
                "line-1",
                "confirmed",
                text_value=50.5,
                geometry_measured_length=50.0,
                delta_percent=1.0,
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            built = build_dxf(
                document,
                os.path.join(tmp, "legacy.dxf"),
                build_dimensions=True,
            )
            assert built.dimension_count == 1
            assert review_dxf(built).passed

- [ ] **Step 2: Run RED**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest dxf_builder_lib\tests\test_builder.py dxf_builder_lib\tests\test_reviewer.py -q -p no:cacheprovider

Expected: import or signature failure for NativeLinearDimensionSpec and dimension_specs.

- [ ] **Step 3: Refactor the existing dimension emitter around one spec type**

Add:

    @dataclass(frozen=True)
    class NativeLinearDimensionSpec:
        id: str
        geometry_primitive_id: str
        approved_value_mm: float | None
        source_ref: str

Refactor _add_confirmed_dimensions() to consume these specs. Keep BuildResult field names unchanged for JSON compatibility, but key both maps by spec.id. Record the actual solved line length in measurement and the approved value separately in approved_value_mm. The compatibility adapter for every existing CrossValidation sets approved_value_mm=None and source_ref equal to text_primitive_id; legacy threshold behavior therefore remains unchanged. When callers pass dimension_specs explicitly, every approved_value_mm must be present, finite, and positive.

Reject duplicate spec IDs, non-finite/non-positive explicit approved values, or missing written LINE geometry before save. Legacy CrossValidation specs always record approved_value_mm=None and check serialization integrity only.

- [ ] **Step 4: Measure the reopened native entity against both written and approved values**

Add to ReviewResult:

    dimension_measurement_by_id: Dict[str, float] = field(default_factory=dict)

For each reopened DIMENSION:

    actual = float(entity.get_measurement())
    measurements[dimension_id] = actual
    if abs(actual - float(expected["measurement"])) > tolerance_mm:
        dimension_mismatches.append(...)
    approved = expected.get("approved_value_mm")
    if approved is not None and abs(actual - float(approved)) > tolerance_mm:
        dimension_mismatches.append(
            f"{dimension_id}: approved measurement {approved}, actual {actual}, "
            f"tolerance {tolerance_mm}"
        )

Do not change cad_agent.live._build_result_dict() or _build_result_from_dict(): the chosen design adds no BuildResult field, so persisted build evidence remains byte-shape compatible.

- [ ] **Step 5: Run GREEN and build-evidence regressions**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest dxf_builder_lib\tests tests\test_cad_agent_cli.py tests\test_cad_agent_live.py mcp_integration_lib\tests\test_phase4.py -q -p no:cacheprovider

Expected: PASS.

- [ ] **Step 6: Commit**

    git add dxf_builder_lib/builder.py dxf_builder_lib/reviewer.py dxf_builder_lib/tests/test_builder.py dxf_builder_lib/tests/test_reviewer.py
    git commit -m "feat: measure approved native dimensions"

---

### Task 4: Add the hash-bound offline Dimension Pilot orchestrator

**Files:**

- Create: cad_agent/dimension_pilot.py
- Create: tests/test_cad_agent_dimension_pilot.py
- Modify: tests/dimension_pilot_fixtures.py

**Interfaces:**

- Produces: DimensionPilotError
- Produces: DimensionPilotRun(evidence: dict[str, object], build_result: BuildResult | None)
- Produces: run_dimension_pilot(*, plan, setup_plan, setup_evidence, source_path, primitive_ir_path, semantic_ir_path, output_dxf) -> DimensionPilotRun
- Produces: write_dimension_evidence(path: Path, evidence: Mapping[str, object]) -> None
- Consumes Task 1 contracts, Task 2 solver inputs, and Task 3 NativeLinearDimensionSpec
- Test helper: run_with(inputs: SimpleNamespace) -> DimensionPilotRun, passing every mapping/path from write_dimension_pilot_inputs() by keyword

Use these stable blocker codes:

    source_changed
    primitive_ir_changed
    semantic_ir_changed
    source_provenance_mismatch
    primitive_provenance_mismatch
    setup_evidence_changed
    setup_incomplete
    attachment_unresolved
    datum_mismatch
    constraint_missing
    solver_failed
    solver_conflict
    underconstrained
    measurement_out_of_tolerance
    headless_review_failed

Sort blockers by code then path.

- [ ] **Step 1: Add failing setup/hash/refusal tests**

    def test_pilot_refuses_before_build_when_setup_is_not_verified(tmp_path: Path) -> None:
        inputs = write_dimension_pilot_inputs(tmp_path)
        inputs.setup_evidence["status"] = "NEEDS_REVIEW"
        inputs.setup_evidence["blockers"] = [{
            "code": "setup_incomplete",
            "path": "$.styles.dimension",
            "expected": "VX_DIM_20",
            "actual": None,
            "severity": "error",
        }]
        inputs.plan["setup"]["evidence_sha256"] = canonical_json_sha256(
            inputs.setup_evidence
        )
        run = run_with(inputs)
        assert run.build_result is None
        assert not inputs.output_dxf.exists()
        assert [item["code"] for item in run.evidence["blockers"]] == ["setup_incomplete"]
        assert run.evidence["acceptance"] == "NOT_RUN"


    @pytest.mark.parametrize(
        ("field", "code"),
        [
            ("source", "source_changed"),
            ("primitive_ir", "primitive_ir_changed"),
            ("semantic_ir", "semantic_ir_changed"),
        ],
    )
    def test_changed_hash_refuses_before_solver(tmp_path: Path, field: str, code: str) -> None:
        inputs = write_dimension_pilot_inputs(tmp_path)
        getattr(inputs, field).write_bytes(b"changed")
        run = run_with(inputs)
        assert [item["code"] for item in run.evidence["blockers"]] == [code]
        assert run.build_result is None


    def test_unresolved_attachment_and_missing_constraint_fail_closed(tmp_path: Path) -> None:
        inputs = write_dimension_pilot_inputs(tmp_path)
        inputs.plan["dimensions"][0]["from"]["primitive_id"] = "missing-line"
        inputs.plan["constraint_ids"] = ["missing-constraint"]
        run = run_with(inputs)
        assert {item["code"] for item in run.evidence["blockers"]} == {
            "attachment_unresolved",
            "constraint_missing",
        }


    def test_matching_file_hashes_do_not_bypass_model_provenance(tmp_path: Path) -> None:
        inputs = write_dimension_pilot_inputs(tmp_path)
        primitive = json.loads(inputs.primitive_ir.read_text(encoding="utf-8"))
        primitive["source_document"]["sha256"] = "0" * 64
        inputs.primitive_ir.write_text(json.dumps(primitive), encoding="utf-8")
        rebind_artifact_hashes(inputs)
        run = run_with(inputs)
        assert [item["code"] for item in run.evidence["blockers"]] == [
            "source_provenance_mismatch"
        ]
        assert run.build_result is None

- [ ] **Step 2: Run RED**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest tests\test_cad_agent_dimension_pilot.py -q -p no:cacheprovider

Expected: collection fails because cad_agent.dimension_pilot does not exist.

- [ ] **Step 3: Implement immutable hash and setup preflight**

Validate the plan first. Re-hash source, Primitive IR, Semantic IR, setup plan, and setup evidence before loading model objects. Use sha256_file() for files and canonical_json_sha256() for validated JSON mappings.

Call:

    require_setup_verified(
        setup_evidence,
        setup_plan_sha256=plan["setup"]["setup_plan_sha256"],
        drawing_profile_sha256=plan["setup"]["drawing_profile_sha256"],
        template_file_sha256=plan["setup"]["template_file_sha256"],
    )

Also require canonical_json_sha256(setup_plan) to equal setup_plan_sha256 and canonical_json_sha256(setup_evidence) to equal evidence_sha256. Convert expected runtime refusals into sorted blockers. Contract syntax errors still raise DimensionPilotError and do not write output.

After loading the model objects, require PrimitiveIRDocument.source_document.sha256 to equal plan.source_sha256 and require SemanticIRDocument.primitive_ir_ref.sha256 to equal plan.primitive_ir_sha256. Record source_provenance_mismatch or primitive_provenance_mismatch and refuse before solving when either link is absent or stale. A matching file hash alone is not provenance.

- [ ] **Step 4: Add datum-local transformation and attachment adaptation**

Use the approved orthonormal frame:

    def to_local(point: Point2D, origin: Point2D, x_axis: tuple[float, float], y_axis: tuple[float, float]) -> Point2D:
        dx, dy = point.x - origin.x, point.y - origin.y
        return Point2D(dx * x_axis[0] + dy * x_axis[1], dx * y_axis[0] + dy * y_axis[1])


    def to_world(point: Point2D, origin: Point2D, x_axis: tuple[float, float], y_axis: tuple[float, float]) -> Point2D:
        return Point2D(
            origin.x + point.x * x_axis[0] + point.y * y_axis[0],
            origin.y + point.x * x_axis[1] + point.y * y_axis[1],
        )

Deep-copy the PrimitiveIRDocument for solving, transform every LINE start/end into datum-local coordinates, and never mutate the loaded source object. Require the origin attachment to map within measurement_tolerance_mm of [0, 0]. Require origin_attachment.primitive_id to equal x_axis_primitive_id for this lean slice, and require the other endpoint of that line to have positive local X. Convert solved line endpoints back to world coordinates before passing them to build_dxf().

Resolve plan constraint_ids against the existing SemanticIRDocument constraints. Resolve each approved dimension attachment into one DrivingLengthConstraint and one NativeLinearDimensionSpec. Do not infer attachments from proximity, OCR, or the DWG.

- [ ] **Step 5: Add solver, residual, build, and read-back evidence tests**

    def test_closed_dimension_pilot_builds_and_reads_native_dimension(tmp_path: Path) -> None:
        inputs = write_dimension_pilot_inputs(tmp_path)
        run = run_with(inputs)
        assert run.evidence["offline_passed"] is True
        assert run.evidence["acceptance"] == "NOT_RUN"
        assert run.evidence["blockers"] == []
        assert run.evidence["solver"]["status"] == "okay"
        assert run.evidence["solver"]["model_dof"] == 0
        assert inputs.output_dxf.is_file()
        measurement = run.evidence["measurements"][0]
        assert measurement["dimension_id"] == "DIM-001"
        assert measurement["approved_value_mm"] == 80.0
        assert measurement["readback_value_mm"] == pytest.approx(80.0)
        assert measurement["residual_mm"] <= 0.1


    def test_underconstrained_or_conflicting_model_never_builds(tmp_path: Path) -> None:
        inputs = write_dimension_pilot_inputs(tmp_path, disconnected=True)
        run = run_with(inputs)
        assert not run.evidence["offline_passed"]
        assert "underconstrained" in {item["code"] for item in run.evidence["blockers"]}
        assert not inputs.output_dxf.exists()

        inputs = write_dimension_pilot_inputs(tmp_path / "conflict", conflicting=True)
        run = run_with(inputs)
        assert "solver_conflict" in {item["code"] for item in run.evidence["blockers"]}
        assert set(run.evidence["solver"]["conflict_ids"]) >= {"DIM-001", "DIM-002"}

- [ ] **Step 6: Implement deterministic evidence and atomic writing**

Populate measurements from Task 2 solved residuals and Task 3 read-back measurements. dxf_sha256 is null until a headless review passes. A failed headless review records headless_review_failed and leaves offline_passed=false. write_dimension_evidence() validates the evidence contract, writes UTF-8 JSON with sorted keys to a sibling .tmp file opened in exclusive-create mode, and uses os.rename() on Windows so an output that appears concurrently is never replaced.

- [ ] **Step 7: Run GREEN with setup and solver suites**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest tests\test_cad_agent_dimension_pilot.py tests\test_dimension_pilot_contracts.py tests\test_cad_agent_drawing_setup.py semantic_ir_lib\tests\test_constraint_solving.py dxf_builder_lib\tests\test_builder.py dxf_builder_lib\tests\test_reviewer.py -q -p no:cacheprovider

Expected: PASS.

- [ ] **Step 8: Commit**

    git add cad_agent/dimension_pilot.py tests/test_cad_agent_dimension_pilot.py tests/dimension_pilot_fixtures.py
    git commit -m "feat: orchestrate offline dimension pilot"

---

### Task 5: Expose one strict offline CLI vertical slice

**Files:**

- Modify: cad_agent/cli.py
- Create: tests/test_cad_agent_dimension_pilot_cli.py

**Interfaces:**

- Produces CLI: cad_agent dimension-pilot-run
- Required flags: --plan, --setup-plan, --setup-evidence, --source, --primitive-ir, --semantic-ir, --output-dxf, --output-evidence
- Exit 0: offline_passed=true while acceptance remains NOT_RUN
- Exit 1: valid execution with blockers
- Exit 2: malformed contract, missing input, unsafe output, or overwrite refusal
- Test helper: dimension_pilot_cli_args(inputs: SimpleNamespace) -> list[str], returning the command and all eight required flags in parser order

- [ ] **Step 1: Add failing happy-path and refusal CLI tests**

    def test_dimension_pilot_cli_writes_dxf_and_not_run_evidence(tmp_path: Path, capsys) -> None:
        inputs = write_dimension_pilot_inputs(tmp_path)
        args = dimension_pilot_cli_args(inputs)
        assert main(args) == 0
        evidence = json.loads(inputs.output_evidence.read_text(encoding="utf-8"))
        assert evidence["offline_passed"] is True
        assert evidence["acceptance"] == "NOT_RUN"
        assert inputs.output_dxf.is_file()
        assert "OFFLINE PASS" in capsys.readouterr().out


    def test_dimension_pilot_cli_refuses_overwrite_and_bad_suffix(tmp_path: Path, capsys) -> None:
        inputs = write_dimension_pilot_inputs(tmp_path)
        inputs.output_evidence.write_text("keep", encoding="utf-8")
        assert main(dimension_pilot_cli_args(inputs)) == 2
        assert inputs.output_evidence.read_text(encoding="utf-8") == "keep"
        assert "already exists" in capsys.readouterr().err

        inputs = write_dimension_pilot_inputs(tmp_path / "bad")
        inputs.output_dxf = inputs.output_dxf.with_suffix(".dwg")
        assert main(dimension_pilot_cli_args(inputs)) == 2
        assert "must be a .dxf" in capsys.readouterr().err


    def test_dimension_pilot_cli_records_blockers_without_dxf(tmp_path: Path) -> None:
        inputs = write_dimension_pilot_inputs(tmp_path, disconnected=True)
        assert main(dimension_pilot_cli_args(inputs)) == 1
        evidence = json.loads(inputs.output_evidence.read_text(encoding="utf-8"))
        assert evidence["offline_passed"] is False
        assert evidence["acceptance"] == "NOT_RUN"
        assert "underconstrained" in {
            item["code"] for item in evidence["blockers"]
        }
        assert not inputs.output_dxf.exists()

- [ ] **Step 2: Run RED**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest tests\test_cad_agent_dimension_pilot_cli.py -q -p no:cacheprovider

Expected: parser rejects the unknown dimension-pilot-run command.

- [ ] **Step 3: Add parser and command boundary**

Add one parser:

    dimension_pilot = subcommands.add_parser(
        "dimension-pilot-run",
        help="Build and measure a hash-bound offline linear-dimension candidate",
    )
    for name in (
        "plan", "setup-plan", "setup-evidence", "source",
        "primitive-ir", "semantic-ir", "output-dxf", "output-evidence",
    ):
        dimension_pilot.add_argument(f"--{name}", type=Path, required=True)

The command must:

- Resolve every path.
- Require all six inputs to be existing files.
- Require output-dxf suffix .dxf and output-evidence suffix .json.
- Refuse if either output exists; never overwrite.
- Refuse if output-dxf or output-evidence resolves inside the repository. Every Dimension Pilot run is private in this slice.
- Read plan/evidence through strict contract readers.
- Call run_dimension_pilot() once.
- Write evidence even when a valid run returns blockers.
- Print cad_agent: dimension pilot OFFLINE PASS; acceptance=NOT_RUN on exit 0.
- Print a deterministic blocker-code summary to stderr on exit 1.

Do not add a flag that bypasses SETUP_VERIFIED, substitutes AutoCAD 2018, or relabels acceptance.

- [ ] **Step 4: Run GREEN and all cad_agent CLI regressions**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest tests\test_cad_agent_dimension_pilot_cli.py tests\test_cad_agent_cli.py tests\test_cad_agent_drawing_setup.py -q -p no:cacheprovider

Expected: PASS.

- [ ] **Step 5: Commit**

    git add cad_agent/cli.py tests/test_cad_agent_dimension_pilot_cli.py
    git commit -m "feat: expose offline dimension pilot CLI"

---

### Task 6: Preserve the private sample, verify the candidate, and record honest status

**Files:**

- Modify: docs/ARCHITECTURE.md
- Modify: docs/STATUS.md
- Do not create a private review record because no compatible source export, real Setup evidence, or Mechanical 2027 session exists

**Interfaces:** Records sample custody and offline implementation evidence without committing the sample, its path, its hash, or generated private CAD.

- [ ] **Step 1: Create a non-overwriting external custody copy**

Set CAD_AGENT_LEAN_SAMPLE_DWG in the current PowerShell process to the owner-provided sample path, then run:

    $source = [IO.Path]::GetFullPath($env:CAD_AGENT_LEAN_SAMPLE_DWG)
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Owner-provided sample DWG is missing."
    }
    if ([IO.Path]::GetExtension($source) -ine ".dwg") {
        throw "Owner-provided sample must be a DWG."
    }
    $privateRoot = [IO.Path]::GetFullPath("C:\temp\cad-agent-lean\private")
    New-Item -ItemType Directory -Path $privateRoot -Force | Out-Null
    $copy = [IO.Path]::GetFullPath((Join-Path $privateRoot "sample-review-copy.dwg"))
    if (-not $copy.StartsWith($privateRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Custody copy escaped the approved private directory."
    }
    $sourceHashBefore = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    if (Test-Path -LiteralPath $copy) {
        $copyHash = (Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash
        if ($copyHash -ne $sourceHashBefore) {
            throw "Existing custody copy has a different hash; overwrite refused."
        }
    } else {
        Copy-Item -LiteralPath $source -Destination $copy
    }
    $sourceHashAfter = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    $copyHashAfter = (Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash
    if ($sourceHashBefore -ne $sourceHashAfter -or $sourceHashBefore -ne $copyHashAfter) {
        throw "Sample custody hash verification failed."
    }

Do not open or convert either file. Keep the hashes in the private terminal record only.

- [ ] **Step 2: Run the complete focused Gate B offline suite**

Run:

    .\.venv-py311\Scripts\python.exe -m pytest tests\test_dimension_pilot_contracts.py tests\test_cad_agent_dimension_pilot.py tests\test_cad_agent_dimension_pilot_cli.py semantic_ir_lib\tests\test_constraint_solving.py dxf_builder_lib\tests\test_builder.py dxf_builder_lib\tests\test_reviewer.py tests\test_cad_agent_drawing_setup.py -q -p no:cacheprovider

Expected: PASS with no live acceptance claim.

- [ ] **Step 3: Run the required constraint benchmark gate or record it accurately**

First run the unavailable-state probe through the authoritative verifier. A real private real_data run requires an owner-approved compatible export and matching benchmark configuration. The supplied DWG alone is not a supported offline geometry export, so do not inspect it or claim a private benchmark pass.

Record:

    real_data private constraint benchmark: NOT RUN — owner-approved compatible export absent
    owner-provided DWG custody: hash-stable copy prepared; content inspection NOT RUN
    AutoCAD Mechanical 2027 Gate A: NOT RUN — application absent

- [ ] **Step 4: Run authoritative verification**

Resolve Python 3.11 and run:

    $python311 = py -3.11 -c "import sys; print(sys.executable)"
    .\scripts\verify.ps1 -PythonExe $python311 -SkipAutoCADDotNet
    git diff --check
    git status --short

Expected:

- verifier exits 0;
- .NET is explicitly NOT RUN;
- real_data unavailable-state probe is SKIP, not PASS;
- AutoCAD Mechanical unavailable-state probe is SKIP, not PASS;
- no DWG, DWT, DXF, raw audit, private path, or private annotation appears in git status.

- [ ] **Step 5: Update architecture and status with only fresh evidence**

docs/ARCHITECTURE.md must state that the Dimension Pilot adapter supplies approved driving lengths and an explicit datum anchor to the existing SolveSpace boundary, then routes solved geometry through the existing native DXF builder/reviewer. It must state that offline readiness does not change Gate A/B/C acceptance order.

docs/STATUS.md must record:

- the candidate commit;
- exact focused and authoritative verifier counts;
- Gate A remains open;
- Gate B private acceptance, private real_data constraint benchmark, .NET, and Mechanical 2027 live gate are NOT RUN where applicable;
- the private sample was hash-copied outside Git without content inspection, conversion, save, or mutation;
- no PERSONAL_VERIFIED outcome exists.

- [ ] **Step 6: Safety scan and commit**

Run:

    git diff --check
    git status --short
    git diff --name-only | Select-String -Pattern '\.(dwg|dwt|dxf)$|raw|private' -CaseSensitive:$false
    $sampleName = [IO.Path]::GetFileName($env:CAD_AGENT_LEAN_SAMPLE_DWG)
    $sampleHash = (Get-FileHash -LiteralPath $env:CAD_AGENT_LEAN_SAMPLE_DWG -Algorithm SHA256).Hash
    $userRootPrefix = "C:" + [IO.Path]::DirectorySeparatorChar + "Users" + [IO.Path]::DirectorySeparatorChar
    $diffText = git diff
    if ($diffText | Select-String -SimpleMatch $userRootPrefix) { throw "Private workstation path found in diff." }
    if ($diffText | Select-String -SimpleMatch $sampleName) { throw "Private sample filename found in diff." }
    if ($diffText | Select-String -SimpleMatch $sampleHash) { throw "Private sample hash found in diff." }

Expected: both safety scans return no matches. Then:

    git add docs/ARCHITECTURE.md docs/STATUS.md
    git commit -m "docs: record Gate B offline candidate"

---

## Gate B offline implementation checklist

- [ ] Strict plan/evidence contracts reject unknown fields, unsafe axes, non-positive tolerance, unsupported dimension kinds, unresolved endpoint shape, and false acceptance claims.
- [ ] The existing SolveSpace solver accepts approved driving lengths and one datum anchor without breaking legacy callers.
- [ ] Solver evidence distinguishes okay, inconsistent, non-converged, underconstrained, skipped, and conflicting outcomes.
- [ ] The existing DXF builder emits native editable DIMENSION entities from explicit specs and preserves legacy confirmed-CrossValidation behavior.
- [ ] Headless review measures reopened native dimensions against the approved value and configured tolerance.
- [ ] Orchestration re-hashes source, Primitive IR, Semantic IR, setup plan, and setup evidence before work.
- [ ] Missing or stale SETUP_VERIFIED evidence prevents entity creation.
- [ ] The CLI never overwrites outputs and always records acceptance=NOT_RUN.
- [ ] The original owner-provided DWG remains unchanged; its copy and every private artifact stay outside Git.
- [ ] Focused tests and scripts/verify.ps1 pass with unavailable live/private gates labeled SKIP or NOT RUN, never PASS.
- [ ] docs/STATUS.md reports an offline implementation candidate only; Gate A and PERSONAL_VERIFIED remain open.
