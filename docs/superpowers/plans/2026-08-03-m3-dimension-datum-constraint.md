# M3 Dimension, Datum, Constraint IR and Solver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved M3 Dimension IR, Datum IR, Constraint IR,
approval binding, residual/conflict gate, and deterministic solver adapter
without creating or mutating AutoCAD geometry.

**Architecture:** Extend `semantic_ir_lib` with immutable dimension-first
records and a pure validation/attachment boundary. Reuse the existing
`semantic_ir_lib.constraint_solving.solve_constraints()` implementation for
supported geometric constraints, add deterministic scalar measurement checks
for approved dimensions, and return a hash-bound report/model result. M2
setup evidence is required and stale evidence fails closed; M4 remains the
owner of native CAD generation.

**Tech Stack:** Python 3.11, dataclasses, JSON Schema examples, existing
`primitive_ir_lib` geometry models, existing `python-solvespace`, pytest,
Ruff, and `scripts/verify.ps1`.

## Global Constraints

- Preserve all existing `primitive_ir_lib` and `semantic_ir_lib` behavior.
- Approved dimensions/datum/relations are authoritative; pixels and unattached
  OCR values are non-authoritative.
- Normalize `mm`, `cm`, `m`, and `in` to millimetres; reject `px` for
  authoritative dimensions.
- Do not create, open, save, repair, or mutate DWG/DXF or call AutoCAD.
- Do not add COM/ActiveX, native ObjectARX, Mechanical SDK, automatic NETLOAD,
  or a new IPC operation.
- New JSON objects use explicit versions, closed shapes, canonical hashes,
  stable IDs, and deterministic ID ordering.
- Call `require_setup_verified()` before an authoritative solve. Synthetic
  fixtures are never M2 live acceptance evidence.
- Every implementation task follows RED test, minimal implementation, GREEN
  test, diff review, and scoped commit.

## File Map

Create:

- `contracts/dimension-first/` schemas and synthetic examples;
- `semantic_ir_lib/dimension_ir.py`;
- `semantic_ir_lib/datum_ir.py`;
- `semantic_ir_lib/constraint_ir.py`;
- `semantic_ir_lib/solver_gate.py`;
- focused tests under `semantic_ir_lib/tests/`.

Modify only when a failing test requires it:

- `semantic_ir_lib/__init__.py` for public exports;
- `tests/test_documentation_contract.py` for M3 routing;
- `docs/STATUS.md` for fresh offline evidence.

Do not stage profiles, DWT/DWG/DXF files, raw audits, AutoCAD sources, or
private benchmarks.

---

### Task 1: Add closed M3 contracts and synthetic examples

**Files:** Create the six schemas under `contracts/dimension-first/`, their
examples, and `semantic_ir_lib/tests/test_dimension_first_contracts.py`.

**Interfaces:** Contract versions are exactly
`dimension-observation-1.0`, `datum-1.0`, `constraint-1.0`,
`approval-register-1.0`, `constraint-report-1.0`, and
`solved-drawing-model-1.0`.

- [ ] **Step 1: Write the failing contract tests**

Assert every schema is an object with `additionalProperties: false`, a
`schema_version` requirement, and closed nested objects. Assert every example
is JSON, has a `schema_version` ending in `-1.0`, uses fixture hashes only,
and contains no absolute path or `px` authoritative dimension.

- [ ] **Step 2: Run the focused tests and confirm RED**

```powershell
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m pytest semantic_ir_lib/tests/test_dimension_first_contracts.py -q -p no:cacheprovider
```

Expected: FAIL because the schemas and examples do not exist.

- [ ] **Step 3: Add schemas and examples**

Require the fields from the approved M3 spec. Use enums for units, roles,
statuses, report statuses, and blocker severity. Include one approved driving
dimension, datum, geometric constraint, approval register, solved report, and
solved-model fixture.

- [ ] **Step 4: Run tests, Ruff, and `git diff --check`**

```powershell
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m pytest semantic_ir_lib/tests/test_dimension_first_contracts.py -q -p no:cacheprovider
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m ruff check semantic_ir_lib/tests/test_dimension_first_contracts.py
git diff --check
```

- [ ] **Step 5: Commit**

```powershell
git add contracts/dimension-first semantic_ir_lib/tests/test_dimension_first_contracts.py
git commit -m "test: add M3 dimension-first contracts"
```

### Task 2: Implement Dimension IR and unit normalization

**Files:** Create `semantic_ir_lib/dimension_ir.py` and
`semantic_ir_lib/tests/test_dimension_ir.py`.

Expose:

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

def canonical_json_sha256(payload: Mapping[str, object]) -> str: ...
def normalize_dimension(value: float, unit: str) -> float: ...
def validate_dimension_observation(item: DimensionObservation) -> None: ...
def dimension_register_sha256(items: Sequence[DimensionObservation]) -> str: ...
```

- [ ] **Step 1: Write RED tests**

Cover `500 mm == 50 cm == 0.5 m == 19.68503937007874 in` within `1e-9`,
reject `px`, NaN, infinity, invalid role/status, missing attachments, duplicate
IDs, and mutation of frozen records. Assert register hashes are unchanged by
input ordering.

- [ ] **Step 2: Run the focused tests and confirm RED**

```powershell
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m pytest semantic_ir_lib/tests/test_dimension_ir.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement immutable records and validation**

Normalize engineering units to millimetres, reject `px` for authoritative
status, validate reference syntax `datum:NAME` or
`primitive:NAME:start|end|center`, copy incoming collections, and hash records
sorted by ID using canonical UTF-8 JSON.

- [ ] **Step 4: Run focused tests and Ruff**

```powershell
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m pytest semantic_ir_lib/tests/test_dimension_ir.py -q -p no:cacheprovider
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m ruff check semantic_ir_lib/dimension_ir.py semantic_ir_lib/tests/test_dimension_ir.py
git diff --check
```

- [ ] **Step 5: Commit**

```powershell
git add semantic_ir_lib/dimension_ir.py semantic_ir_lib/tests/test_dimension_ir.py
git commit -m "feat: add hash-bound dimension observations"
```

### Task 3: Implement Datum IR and attachment resolution

**Files:** Create `semantic_ir_lib/datum_ir.py` and
`semantic_ir_lib/tests/test_datum_ir.py`.

Expose an immutable `DatumObservation` with `id`, `kind`, `view_id`,
`coordinate_role`, `entity_ref`, `source_refs`, `status`, and `provenance`,
plus:

```python
def resolve_reference(
    reference: str,
    *,
    datums: Mapping[str, DatumObservation],
    primitive_document: PrimitiveIRDocument,
) -> tuple[float, float]: ...

def datum_register_sha256(items: Sequence[DatumObservation]) -> str: ...
```

- [ ] **Step 1: Write RED tests**

Cover line start/end, circle center, datum-to-primitive resolution, missing
reference, recursive datum, duplicate IDs, cross-view rejection, deterministic
hashing, and unchanged source primitive serialization.

- [ ] **Step 2: Run the focused tests and confirm RED**

```powershell
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m pytest semantic_ir_lib/tests/test_datum_ir.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement the resolver**

Reuse `Point2D`, `LineGeometry`, and `CircleGeometry`. Resolve `datum:NAME`
recursively through `entity_ref` and primitive endpoint/center tokens. Reject
loops, missing IDs, non-geometric primitives, and cross-view references without
an explicit shared frame. Never write coordinates back to source objects.

- [ ] **Step 4: Run tests and Ruff**

```powershell
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m pytest semantic_ir_lib/tests/test_datum_ir.py -q -p no:cacheprovider
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m ruff check semantic_ir_lib/datum_ir.py semantic_ir_lib/tests/test_datum_ir.py
```

- [ ] **Step 5: Commit**

```powershell
git add semantic_ir_lib/datum_ir.py semantic_ir_lib/tests/test_datum_ir.py
git commit -m "feat: add deterministic datum attachment resolution"
```

### Task 4: Implement Constraint IR and approval binding

**Files:** Create `semantic_ir_lib/constraint_ir.py` and
`semantic_ir_lib/tests/test_constraint_ir.py`.

Expose immutable `ConstraintObservation` with `id`, `kind`, `refs`, optional
`value`/`unit`, `tolerance`, `source_refs`, `provenance`, and `status`; expose
immutable `ApprovalRegister` with setup, dimension, datum, and constraint
hashes, approval reference/by, approved/rejected IDs, and policy version.
Also expose `constraint_register_sha256()` and
`validate_approval_register()`.

- [ ] **Step 1: Write RED tests**

Test the kinds `coincident`, `horizontal`, `vertical`, `parallel`,
`perpendicular`, `collinear`, `equal_length`, `distance`, `angle`, `radius`,
`diameter`, `chain`, `baseline`, and `ordinate`; validate reference arity,
finite non-negative tolerances, unit/value pairing, rejected pixel units,
duplicate IDs, register hash mismatch, and unapproved IDs.

- [ ] **Step 2: Run the focused tests and confirm RED**

```powershell
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m pytest semantic_ir_lib/tests/test_constraint_ir.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement immutable constraints and register validation**

Reuse the dimension canonical hash function, sort IDs before hashing, and
return stable blocker records with `code`, `path`, `expected`, `actual`, and
`severity`. Unsupported solver behavior must become a blocker, not a silent
skip.

- [ ] **Step 4: Run tests, Ruff, and `git diff --check`**

```powershell
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m pytest semantic_ir_lib/tests/test_constraint_ir.py -q -p no:cacheprovider
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m ruff check semantic_ir_lib/constraint_ir.py semantic_ir_lib/tests/test_constraint_ir.py
git diff --check
```

- [ ] **Step 5: Commit**

```powershell
git add semantic_ir_lib/constraint_ir.py semantic_ir_lib/tests/test_constraint_ir.py
git commit -m "feat: add approved constraint IR and register binding"
```

### Task 5: Add the solver gate and solved-model hash

**Files:** Create `semantic_ir_lib/solver_gate.py` and
`semantic_ir_lib/tests/test_solver_gate.py`.

Expose:

```python
@dataclass(frozen=True)
class SolvedDrawingModel:
    model_id: str
    setup_evidence_sha256: str
    dimensions_sha256: str
    datums_sha256: str
    constraints_sha256: str
    solved_views: Mapping[str, object]

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
) -> tuple[dict[str, object], SolvedDrawingModel | None]: ...
```

Call `require_setup_verified()` first. Translate only validated geometric
relations to the existing semantic `Constraint`, run `solve_constraints()`,
and perform scalar dimension residual checks from resolved primitive/datum
geometry. M3 never adjusts geometry; a mismatch returns
`residual_exceeds_tolerance`.

Classify `SOLVED`, `UNDERCONSTRAINED`, `OVERCONSTRAINED`, `CONFLICT`,
`NON_CONVERGENT`, and `NEEDS_REVIEW` deterministically. A solved model is
created only when every approved driving input resolves, all residuals are in
tolerance, no conflict exists, and required DOF is zero.

- [ ] **Step 1: Write RED solver tests**

Use synthetic `PrimitiveIRDocument` fixtures for exact parallel lines, an
in-tolerance scalar distance, an out-of-tolerance distance, underconstraint,
an inconsistent parallel/perpendicular set, conflicting driving dimensions,
stale M2 evidence, mismatched register hashes, unsupported relations, and
dangling references. Assert all input objects remain unchanged.

- [ ] **Step 2: Run the focused tests and confirm RED**

```powershell
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m pytest semantic_ir_lib/tests/test_solver_gate.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement the report and adapter**

Use schema version `constraint-report-1.0`, sort blockers/constraints by ID,
round report measurements to four decimals, preserve register/setup hashes,
and map all refusal paths to structured blockers. Do not rely on the existing
solver's legacy silent-skip behavior as the M3 validation boundary.

- [ ] **Step 4: Run solver tests, existing solver tests, and Ruff**

```powershell
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m pytest semantic_ir_lib/tests/test_solver_gate.py semantic_ir_lib/tests/test_constraint_solving.py -q -p no:cacheprovider
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m ruff check semantic_ir_lib/solver_gate.py semantic_ir_lib/tests/test_solver_gate.py
```

- [ ] **Step 5: Commit**

```powershell
git add semantic_ir_lib/solver_gate.py semantic_ir_lib/tests/test_solver_gate.py
git commit -m "feat: add dimension-first solver evidence gate"
```

### Task 6: Export APIs, route docs, and run the authoritative verifier

**Files:** Modify `semantic_ir_lib/__init__.py`,
`tests/test_documentation_contract.py`, and `docs/STATUS.md`.

- [ ] **Step 1: Write the failing export/documentation test**

Require imports for `DimensionObservation`, `DatumObservation`,
`ConstraintObservation`, `ApprovalRegister`, `SolvedDrawingModel`, and
`solve_authoritative_model`; require the M3 spec and plan paths.

- [ ] **Step 2: Run the focused test and confirm RED**

```powershell
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m pytest tests/test_documentation_contract.py -q -p no:cacheprovider
```

- [ ] **Step 3: Add exports and status evidence**

Export only the stable interfaces named by the spec. Record the implementation
head, contract/solver totals, Ruff result, and explicit
`autocad_mechanical: NOT RUN`; do not claim M2 `SETUP_VERIFIED`, private-data
PASS, or production readiness.

- [ ] **Step 4: Run focused and full verification**

```powershell
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m pytest semantic_ir_lib/tests tests/test_documentation_contract.py -q -p no:cacheprovider
& 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe' -m ruff check semantic_ir_lib semantic_ir_lib/tests tests
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -PythonExe 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe'
git diff --check
```

Expected: existing tests remain green, unavailable probes stay explicit, and
the AutoCAD live marker remains `NOT RUN`.

- [ ] **Step 5: Review and commit**

Confirm no private drawing, binary, absolute workstation path, or generated
artifact is staged, then run:

```powershell
git add semantic_ir_lib contracts/dimension-first tests/test_documentation_contract.py docs/STATUS.md
git commit -m "docs: record M3 offline solver evidence"
```

## Completion criteria

- All six contracts validate strictly and hash deterministically.
- Driving dimensions carry value, unit, kind, attachment, view, role, status,
  provenance, and approval.
- Datum/entity attachments resolve or return stable blockers.
- Approval binds all input/register/setup hashes.
- Residual, underconstraint, overconstraint, conflict, stale-evidence, and
  unsupported-input states are explicit and tested.
- `SolvedDrawingModel` exists only for a fully solved synthetic model.
- Existing semantic IR/solver tests remain green and the authoritative verifier
  passes with AutoCAD live honestly `NOT RUN`.
- M4 native generation is not started by this plan.
