# M3 Dimension, Datum, Constraint IR and Solver Design

**Status:** Approved for offline-first planning

**Approval date:** 2026-08-03

**Base SHA:** `ef73ff6cf875747889bf58997bdb496502ad4ad4`

**Dependency state:** M2 implementation through T9 is available and its
offline/.NET evidence is green. The operator-controlled M2 AutoCAD live gate
remains `NOT RUN`; this M3 slice may build and test deterministic contracts
against synthetic setup evidence, but it must not promote that evidence to a
production or release claim.

## Goal

Add a versioned, hash-bound Dimension IR, Datum IR, Constraint IR, approval
register, and solver-result gate that can consume approved dimension-first
inputs and report residuals, underconstraint, overconstraint, and conflicts
without creating or mutating AutoCAD geometry.

## Scope

M3 owns the authoritative measurement/model boundary between the existing
primitive/semantic pipeline and future M4 generation:

- dimension observations with explicit attachment to a view and entity or
  datum references;
- datum candidates and approved datum references;
- geometric and dimensional constraints with provenance and tolerance policy;
- an approval register that binds the records to source and setup evidence;
- deterministic normalization, validation, hashing, and stale-evidence refusal;
- an adapter over the existing solver implementation that emits a stable
  constraint report and a hash-bound solved-model record.

M3 does not create DXF/DWG entities, call AutoCAD, infer model-critical
  coordinates from pixels, or expose a production mutation operation.

## Existing boundaries to preserve

The implementation reuses the existing package boundaries:

- `primitive_ir_lib` remains the source of measured primitive observations and
  source trace data;
- `semantic_ir_lib.models.Constraint` and the existing constraint detection,
  pruning, and SolveSpace integration remain backward compatible for the
  current pipeline;
- `cad_agent.drawing_setup.require_setup_verified()` remains the M2 gate and
  is called before an authoritative M3 solve;
- `mcp_integration_lib` and `CadAgent.AutoCAD2027` are not changed by this
  slice;
- M4, not M3, owns native CAD generation, render feedback, and measurement
  round-trip.

## Authoritative source policy

The source priority is strict:

1. approved dimensions;
2. approved datums and geometric relations;
3. approved reusable component constraints;
4. source vector/OCR/vision observations for attachment and topology review;
5. pixels only as non-authoritative visual evidence.

An observation with a numeric value but no valid attachment is
`UNRESOLVED`. A visual estimate may be retained as a candidate, but it cannot
resolve a model-critical degree of freedom or enter an authoritative solved
model. If two authoritative dimensions disagree, the solver returns a
`dimension_conflict` blocker; it never chooses the value that looks closer to
the image.

## Records and contracts

All records are JSON objects with explicit schema versions, closed shapes
(`additionalProperties: false`), canonical JSON hashing, stable IDs, and
deterministic ordering by ID. Timestamps are metadata only and do not enter a
content hash unless the contract explicitly names them as approval evidence.

### DimensionObservation

The stable Python interface is:

```python
@dataclass(frozen=True)
class DimensionObservation:
    id: str
    value: float
    unit: str
    kind: str
    view_id: str
    from_ref: str
    to_ref: str
    role: str
    status: str
    provenance: str
```

The serialized form additionally carries `source_refs`, optional extension
geometry, confidence, tolerance policy, and approval metadata. `unit` accepts
explicit engineering units (`mm`, `cm`, `m`, or `in`) and normalizes to
millimetres for solving. `px` is rejected for authoritative dimensions.

`kind` distinguishes at least horizontal, vertical, aligned, angular, radial,
diameter, chain, baseline, and ordinate dimensions. `role` is one of
`driving`, `reference`, or `inspection`; only approved `driving` dimensions
may close a model-critical degree of freedom.

### Datum IR

Each datum contains:

- stable `id`, `kind`, and `view_id`;
- coordinate role and frame metadata;
- resolved entity or dimension references;
- source references and provenance;
- `CANDIDATE`, `APPROVED`, `REJECTED`, or `UNRESOLVED` status;
- approval metadata when status is `APPROVED`.

Datum references are symbolic. They do not silently become coordinates until
the attachment resolver proves that the referenced entity exists in the
approved view/model register.

### Constraint IR

Each constraint contains:

- stable `id` and `kind`;
- ordered entity/datum references;
- an optional numeric value, angle, relation, unit, and tolerance policy;
- `source_refs`, provenance, approval, and status;
- solver output fields: `solver_status`, `residual`, and `conflict_set`.

The contract supports at least coincident, horizontal, vertical, parallel,
perpendicular, collinear, equal-length, distance, angle, radius, diameter,
chain, baseline, and ordinate relations. Unsupported kinds fail validation;
they are not silently skipped in an authoritative solve.

### ApprovalRegister

The register binds the input set to:

- `setup_evidence_sha256`;
- source manifest and dimension/datum/constraint register hashes;
- approval reference, approver identity, and approval timestamp;
- the list of approved IDs and any rejected/unresolved IDs;
- a deterministic policy version.

The register is not an approval of production mutation. It only authorizes
these records to enter the M3 solve gate.

### ConstraintReport and SolvedDrawingModel

The solver emits a deterministic report with:

- overall status: `SOLVED`, `UNDERCONSTRAINED`, `OVERCONSTRAINED`,
  `CONFLICT`, `NON_CONVERGENT`, or `NEEDS_REVIEW`;
- degrees of freedom by view and model-critical group;
- per-constraint residual, tolerance, status, and conflict set;
- unresolved attachments and rejected inputs;
- maximum residual and tolerance summary;
- hashes of every input register and the setup evidence.

The stable downstream interface is:

```python
@dataclass(frozen=True)
class SolvedDrawingModel:
    model_id: str
    setup_evidence_sha256: str
    dimensions_sha256: str
    datums_sha256: str
    constraints_sha256: str
    solved_views: Mapping[str, object]
```

`SolvedDrawingModel` is emitted only when the report is `SOLVED` for the
requested model-critical groups. A report with any unresolved, conflicting,
or tolerance-failing driving input remains a blocker and may not be consumed
as authoritative generation input.

## Data flow

```text
approved source/registers
        |
        v
canonical validation + attachment resolution
        |
        +--> unresolved/conflict register --> NEEDS_REVIEW
        |
        v
approved Dimension/Datum/Constraint IR
        |
        v
existing semantic solver adapter
        |
        +--> residual/DOF/conflict report
        |
        v
hash-bound SolvedDrawingModel (SOLVED only)
        |
        v
M4 Operation Plan input; no M3 CAD mutation
```

The adapter may translate the new authoritative constraints into the existing
`semantic_ir_lib.models.Constraint` representation for supported geometric
relations. That translation is explicit and recorded; it must not weaken the
new attachment, approval, unit, or tolerance checks.

## Gate and failure behavior

Before solving, M3 calls `require_setup_verified()` with the exact setup,
profile, and template hashes required by the M2 evidence. It refuses stale,
missing, or mismatched evidence.

The gate returns structured blockers rather than guessing:

- `dimension_unresolved_attachment`;
- `dimension_conflict`;
- `dimension_unit_invalid`;
- `dimension_not_approved`;
- `datum_unresolved`;
- `constraint_not_approved`;
- `constraint_unsupported`;
- `underconstrained_model`;
- `overconstrained_model`;
- `solver_non_convergent`;
- `residual_exceeds_tolerance`;
- `stale_setup_evidence`;
- `input_hash_mismatch`.

All blockers contain stable `code`, record ID/path, expected value or policy,
actual value, and severity. No blocker path writes to AutoCAD or changes input
records.

## File-level design

The implementation plan will add only the following bounded surfaces unless a
failing test demonstrates that an existing seam must be extended:

- `contracts/dimension-first/` — versioned schemas and synthetic examples for
  dimension, datum, constraint, approval, report, and solved-model records;
- `semantic_ir_lib/dimension_ir.py` — immutable dimension records, unit
  normalization, attachment validation, and canonical serialization;
- `semantic_ir_lib/datum_ir.py` — immutable datum records and reference
  resolution;
- `semantic_ir_lib/constraint_ir.py` — immutable constraints, approval binding,
  tolerance policy, and blocker normalization;
- `semantic_ir_lib/solver_gate.py` — adapter to the existing solver and
  deterministic report/model construction;
- `semantic_ir_lib/tests/` — focused contract, attachment, conflict, residual,
  stale-hash, and solver tests;
- `tests/test_documentation_contract.py` and `docs/STATUS.md` only for the
  resulting contract/status routing.

No AutoCAD plugin source, live fixture, private drawing, DWT, DWG, DXF, or raw
audit is added by M3.

## Verification strategy

The M3 offline gate must cover:

- strict schema validation and canonical hashes;
- unit conversion and rejection of pixel-authoritative values;
- deterministic attachment resolution and rejection of missing references;
- approval and provenance state transitions;
- dimension chain, baseline, ordinate, angle, radius, and distance fixtures;
- exact solve with zero residual within tolerance;
- underconstraint and overconstraint classification;
- conflicting authoritative dimensions and stable conflict sets;
- stale setup/register/input hash refusal;
- backward compatibility for all existing semantic IR tests;
- Ruff, `git diff --check`, and the aggregate offline verifier.

No offline test may report AutoCAD live PASS or `SETUP_VERIFIED` for a real
drawing. Synthetic evidence is clearly labeled as fixture evidence.

## Explicit non-goals

- opening, saving, repairing, or mutating production DWG/DXF;
- automatic NETLOAD, COM/ActiveX, Mechanical SDK, or native ObjectARX;
- deriving authoritative model coordinates from image pixels;
- native CAD dimension/entity generation;
- render feedback and measurement round-trip;
- component similarity or SQLite legacy knowledge;
- release readiness or production approval.
