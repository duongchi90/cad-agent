# R4 Candidate Revision Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement one deterministic Candidate Revision Orchestrator that seals immutable candidate lineage from accepted R1/R2/R3 evidence, binds explicit selection-for-review without self-approval, and persists only optional revision/selection references through the existing manifest/checkpoint owner.

**Architecture:** R4 core is a pure-Python orchestration module. Mutable CAD work remains outside R4 in existing disposable-candidate execution owners; only an already hash-bound candidate workspace may be sealed into an immutable R4 revision. R4 never promotes a candidate to accepted/current/published state, and durable history remains under `cad_agent.manifest` rather than a new store.

**Tech Stack:** Python 3.11; final accepted R1/R2/R3 validators resolved by the mandatory Gate 0; `cad_agent.drawing_contracts.canonical_json_sha256()`; existing `cad_agent.manifest` / `cad_agent.pdf` lifecycle; pytest; Ruff; architecture/reuse ratchet; `scripts/verify.ps1 -SkipAutoCADDotNet`; GitHub hosted `tests` and `reuse-declaration`. No new dependency.

## Global Constraints

- Authoritative planning design: `docs/superpowers/specs/2026-08-09-r4-candidate-revision-orchestrator-design.md`.
- Parent accepted architecture: `docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`.
- Reuse inventory: `docs/superpowers/reuse/2026-08-04-reuse-inventory.json`.
- R4 runtime is blocked until R1, R2 runtime, and R3 runtime are accepted/merged and Master PO performs a fresh post-R3 rebaseline.
- PR #129 is planning-only/HOLD MERGE and moving R3 #128 is planning-only. Do not import or hard-code a planning-time R2/R3 API.
- Every runtime child Issue must record a fresh exact current-main SHA and exact accepted upstream symbols before the first repository write.
- R4 core performs no source/CAD filesystem I/O, parser/OCR/model/provider call, DXF generation, AutoCAD/File IPC call, repair execution, visual/engineering verdict, approval issuance, or publication.
- Mutable candidate workspace and sealed candidate revision are distinct. A sealed candidate is never modified.
- Source, Base-CAD source, accepted drawing, and production-current drawing are immutable R4 inputs and never mutation targets.
- `cad_agent.manifest` remains the sole durable manifest/checkpoint owner. No new database, CAS, revision directory, JSONL log, or second run store.
- `cad_agent.live` and accepted live owners retain backup/rollback and CAD mutation authority.
- R3 retains component/view graph identity. R4 references R3-owned logical/component/view identities and does not reconstruct the graph.
- R5/R6/R7 remain verdict/repair/promotion owners. R4 never emits accepted/current/published authority.
- All R4 canonical identities reuse `cad_agent.drawing_contracts.canonical_json_sha256()`; no second JSON/numeric/hash policy.
- First runtime tests use synthetic/disposable data only. Private/customer/accepted CAD is not required.
- No dependency, lock, workflow, schema-directory, `agent_lib/**`, `mcp_integration_lib/**`, `autocad_plugin/**`, Primitive/Semantic, or DXF-builder change is presumed.
- Every task is RED-first, uses normal forward commits, and preserves literal `PASS` / `FAIL` / `SKIP` / `NOT RUN` semantics.
- No amend, rebase, squash, force-push, merge-main, or main-sync after a child runtime branch is issued.

Each runtime child Issue records its issuance base before the first test edit:

```powershell
$env:R4_TASK_BASE_SHA = (git rev-parse HEAD).Trim()
git rev-parse HEAD
```

---

## Gate 0: Mandatory post-R3 runtime rebaseline — READ ONLY

This gate is mandatory and makes no repository changes.

### Required dependency state

- [ ] R1 final runtime: accepted and merged.
- [ ] R2 final runtime: accepted and merged.
- [ ] R3 final runtime: accepted and merged.
- [ ] No active writer owns the proposed R4 child-task paths.
- [ ] Master PO supplies a fresh exact current-main SHA.

### Exact R1 mapping

Record the exact accepted final R1 validator/hash symbol(s) needed to prove the immutable source/fusion identity transitively used by R3.

The Gate-0 dossier must name:

```text
production path
validator symbol
canonical hash symbol
reusable/blocked state field or exact failure contract
exact upstream digest field consumed transitively/directly by R4
focused test path
```

R4 must not independently interpret conflict internals already validated by R1/R3.

### Exact R2 mapping

For Base-CAD reuse, record the exact accepted R2 symbols/fields that prove:

```text
R2 handoff identity/hash
base source ID
base source SHA-256
base source revision
reused logical component membership
candidate/source provenance binding
stale/re-extraction state
```

If accepted R3 already validates and carries the R2 binding transitively, record that fact and use the R3 proof instead of a duplicate validation path.

### Exact R3 mapping

Record the accepted R3 symbols/fields for:

```text
registry validator
registry canonical hash
candidate drawing/binding identity
stable logical component IDs
stable logical view IDs
per-component/per-view canonical binding identity or the accepted equivalent
linked impact projection
component/view provenance binding
upstream R1/R2 binding
stale/foreign candidate refusal
```

R4 requires a deterministic accepted way to prove logical component/view correspondence between a parent registry snapshot and a new registry snapshot.

If R3 does not expose this, STOP.

### Exact current-baseline mapping

Record the existing accepted owner and exact fields that provide one immutable read-only current/baseline revision reference sufficient to prove:

```text
baseline revision identity/hash
baseline drawing SHA-256
run/project scope
```

R4 must not mint a second production-current pointer merely because this seam is missing.

### Gate-0 STOP result

If any required mapping is absent or materially inconsistent, report exactly:

```text
R4 REBASELINE REQUIRED
```

Do not create a runtime branch or widen another owner's API in this gate.

---

## Runtime file structure

### R4 core — Tasks 1 and 2

```text
CREATE Task 1:
  cad_agent/candidate_revision.py
  tests/test_cad_agent_candidate_revision.py

MODIFY Task 2:
  cad_agent/candidate_revision.py
  tests/test_cad_agent_candidate_revision.py
```

### Existing-manifest integration — Task 3

```text
MODIFY:
  cad_agent/manifest.py
  cad_agent/pdf.py
  tests/test_cad_agent_candidate_revision.py
```

Task 3 must not modify `cad_agent/candidate_revision.py` unless a fresh Master PO write-set amendment is issued because the accepted Task-2 API is demonstrably insufficient.

### Explicitly do not modify in the first R4 sequence

```text
cad_agent/source_bundle.py
cad_agent/source_integrity.py
cad_agent/source_fusion.py
cad_agent/component_view_registry.py or the final accepted R3 owner
cad_agent/live.py
cad_agent/visual_contracts.py
cad_agent/visual_evidence.py
cad_agent/cli.py
primitive_ir_lib/**
semantic_ir_lib/**
dxf_builder_lib/**
agent_lib/**
mcp_integration_lib/**
autocad_plugin/**
contracts/**
requirements/**
.github/workflows/**
private/source/accepted CAD
```

Any need for one of these paths is a STOP/rebaseline condition, not implicit permission.

---

## Task 1: Seal deterministic immutable candidate revisions

**Conceptual output:** one closed `candidate-revision-1.0` record with deterministic revision identity, immutable parent/baseline lineage, exact accepted R1/R2/R3 bindings, candidate artifact hashes, complete R3 impact scope, component/view lineage references, and mutation-evidence hashes.

**Files:**

- Create first for RED: `tests/test_cad_agent_candidate_revision.py`
- Create only after meaningful RED: `cad_agent/candidate_revision.py`
- Modify: none

**Accepted owner dependencies resolved by Gate 0:**

- final R1 validator/hash seam;
- final R2 validator/hash seam when Base-CAD reuse exists;
- final R3 registry/hash/impact/correspondence seam;
- exact current-baseline reference owner;
- `cad_agent.drawing_contracts.canonical_json_sha256()`.

**R4 public surface produced in Task 1:**

```python
CANDIDATE_REVISION_SCHEMA_VERSION = "candidate-revision-1.0"

class CandidateRevisionError(ValueError): ...

def build_candidate_revision(
    *,
    registry: object,
    base_cad_handoff: object | None,
    baseline_context: object,
    parent_candidate: object | None,
    candidate_artifacts: object,
    change_impact: object,
    mutation_evidence: object,
) -> dict[str, object]: ...

def validate_candidate_revision(
    payload: object,
    *,
    registry: object,
    base_cad_handoff: object | None,
    baseline_context: object,
    parent_candidate: object | None = None,
) -> dict[str, object]: ...

def candidate_revision_sha256(
    payload: object,
    *,
    registry: object,
    base_cad_handoff: object | None,
    baseline_context: object,
    parent_candidate: object | None = None,
) -> str: ...

def evaluate_candidate_revision_freshness(
    *,
    revision: object,
    registry: object,
    base_cad_handoff: object | None,
    baseline_context: object,
) -> dict[str, object]: ...
```

The exact upstream API names are **not** R4 public API. The runtime implementation imports and calls only the exact accepted Gate-0 symbols behind private normalization helpers.

### Closed normalized candidate record

The validator accepts exactly these root concepts:

```text
schema_version
revision_id
state
run_id
baseline_revision
parent_candidate_revision_sha256
upstream_bindings
candidate_artifacts
change_scope
component_lineage
view_lineage
mutation_evidence
candidate_revision_sha256
```

Required constants/state:

```text
schema_version = candidate-revision-1.0
state = SEALED_CANDIDATE
```

`baseline_revision` contains only the exact accepted baseline revision identity/hash, drawing SHA-256, and scope identity resolved by Gate 0.

`upstream_bindings` contains R3 registry SHA-256 and the exact R1/R2 digest references required by Gate 0. The R2 reference is absent or null only when accepted R3 evidence proves no Base-CAD reuse is involved.

`candidate_artifacts` is a sorted closed array of immutable artifact identity records. At least one record is the candidate drawing SHA-256 supplied by an accepted owner. Absolute paths are excluded from the R4 artifact.

`change_scope` contains sorted changed/impacted component IDs, view IDs, layout bindings, and the exact accepted R3 impact-closure evidence SHA-256.

`component_lineage` and `view_lineage` contain only logical IDs plus accepted R3-owned parent/current binding identities and one closed change class:

```text
UNCHANGED
CHANGED
NEW
REMOVED
```

`mutation_evidence` contains only closed evidence digests required by the runtime Issue, such as the exact latest-mutation identity, build/review evidence hash, and verified backup/rollback evidence hash when applicable. It contains no approval/verdict.

### Step 1: Create complete synthetic Gate-0-shaped fixtures

- [ ] Create `tests/test_cad_agent_candidate_revision.py` only.
- [ ] Build synthetic accepted R3 registry and impact fixtures using the exact final shapes mapped by Gate 0.
- [ ] Build optional accepted R2 Base-CAD fixtures only through the exact Gate-0 final shape.
- [ ] Build a server-owned baseline fixture using the exact accepted owner shape mapped by Gate 0.
- [ ] Build parent-candidate fixtures only from the planned R4 record shape above.
- [ ] Use no private/customer CAD and perform no live operation.

### Step 2: Write the Task-1 RED matrix

- [ ] Add tests for valid first child from baseline -> `SEALED_CANDIDATE`.
- [ ] Add tests for valid child from one exact parent candidate.
- [ ] Permute every semantically unordered input array and require identical normalized record/revision ID/hash.
- [ ] Change candidate drawing SHA and require a different revision ID/hash.
- [ ] Change R3 registry SHA and require a different revision ID/hash.
- [ ] Change baseline revision hash or drawing hash and require a different revision or stale refusal as appropriate.
- [ ] Change parent candidate SHA and require a different child revision.
- [ ] Change R3 impact-closure hash or impacted logical IDs and require a different revision.
- [ ] Change only non-authoritative timestamp/path/session/UUID fixture metadata and prove it does not enter R4 identity.
- [ ] Reject unknown root/nested R4 fields.
- [ ] Reject missing/invalid lowercase SHA-256 values.
- [ ] Reject any R4 record containing `approval`, `accepted`, `published`, `production_current`, `visual_verdict`, `engineering_verdict`, `repair_permission`, or equivalent authority fields.

### Step 3: Write lineage/adversarial RED tests

- [ ] self-parent -> fail closed;
- [ ] parent from another run/project scope -> fail closed;
- [ ] parent bound to another baseline -> fail closed;
- [ ] parent-candidate caller mutation after build -> cannot mutate sealed returned copy;
- [ ] stale baseline owner identity -> `STALE_BASELINE` freshness result;
- [ ] changed final R3 registry/upstream identity -> `STALE_UPSTREAM`;
- [ ] foreign run/project context -> `FOREIGN_SCOPE`;
- [ ] current exact context -> `CURRENT`;
- [ ] stale R2 Base-CAD source SHA/revision when reused components exist -> stale/block;
- [ ] Base-CAD handoff provided when R3 proves no reuse -> fail closed if final accepted ownership contract makes this contradictory;
- [ ] reused component requiring R2 evidence but missing accepted R2 handoff -> fail closed;
- [ ] caller-forged logical component/view correspondence that R3 does not prove -> fail closed;
- [ ] omitted R3-linked impacted view/layout -> fail closed;
- [ ] duplicate component/view lineage IDs -> fail closed;
- [ ] R4 must not parse candidate CAD to infer lineage.

### Step 4: Prove meaningful RED before production creation

- [ ] Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_candidate_revision.py -q -p no:cacheprovider
```

Expected: meaningful failure because `cad_agent.candidate_revision` and Task-1 behavior do not exist. Record exact failure count/reason. Fixture/import failures unrelated to the missing R4 behavior do not count.

- [ ] Commit the RED-only test file normally:

```powershell
git add tests/test_cad_agent_candidate_revision.py
git commit -m "test: define R4 candidate revision contract"
```

### Step 5: Implement only the pure candidate-revision core

- [ ] Create `cad_agent/candidate_revision.py`.
- [ ] Import only stdlib mapping/copy helpers, `canonical_json_sha256`, and the exact accepted Gate-0 upstream validators needed to normalize R1/R2/R3/current-baseline evidence.
- [ ] Keep accepted upstream validation in private normalization helpers; do not clone R3 graph, R2 provenance, or R1 source logic.
- [ ] Derive full deterministic `revision_id` as `candidate:` plus the complete 64-character canonical digest of the normalized identity material.
- [ ] Compute `candidate_revision_sha256` with `canonical_json_sha256()` over the normalized record excluding its own checksum field.
- [ ] Return deep normalized copies.
- [ ] Sort all semantically unordered component/view/artifact collections by accepted stable identity before hashing.
- [ ] Perform no filesystem/network/subprocess/CAD/model operation.

### Step 6: Prove focused GREEN repeatedly

- [ ] Run five identical focused passes:

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_candidate_revision.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

All five runs must PASS with identical counts and zero R4 skips.

### Step 7: Run accepted upstream regressions

- [ ] Run the exact final R1/R2/R3 focused test paths recorded by Gate 0.
- [ ] Run accepted canonical-hash tests.
- [ ] Run offline exact-base tests when R2 evidence is part of the fixture path.
- [ ] AutoCAD live remains `NOT RUN` in this task.
- [ ] Private/customer data remains `NOT RUN`.

### Step 8: Run Ruff, architecture, diff and canonical gates

- [ ] Run:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/candidate_revision.py tests/test_cad_agent_candidate_revision.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
git diff --cached --check
git diff --name-only "$env:R4_TASK_BASE_SHA"..HEAD
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

The cumulative changed-file audit must contain exactly:

```text
cad_agent/candidate_revision.py
tests/test_cad_agent_candidate_revision.py
```

### Step 9: Commit Task 1 production normally

- [ ] Run:

```powershell
git add cad_agent/candidate_revision.py tests/test_cad_agent_candidate_revision.py
git commit -m "feat: seal deterministic candidate revisions"
```

**Paired independent reviewer domains:** revision-identity/determinism/lineage reviewer + reuse/authority/integration reviewer.

**Task-1 STOP conditions:** accepted R3 cannot prove logical cross-snapshot correspondence; current baseline has no accepted owner; R2/R3 production must be modified; filesystem/CAD parsing is needed; any third R4 core path is needed; new store/schema/dependency is required; approval/verdict/promotion logic appears necessary.

---

## Task 2: Explicit selection-for-review, supersession, and logical rollback

**Conceptual output:** one closed `candidate-selection-1.0` artifact that validates an explicit server/caller choice among exact current sealed R4 candidates without ranking, acceptance, publication, or deletion of prior revision evidence.

**Files:**

- Modify first for RED: `tests/test_cad_agent_candidate_revision.py`
- Modify only after meaningful RED: `cad_agent/candidate_revision.py`
- Create: none

**Consumes:** all accepted Task-1 R4 APIs plus exact Gate-0 upstream/current-baseline seams.

**Public surface added:**

```python
CANDIDATE_SELECTION_SCHEMA_VERSION = "candidate-selection-1.0"

def build_candidate_selection(
    *,
    revisions: object,
    selected_revision_sha256: str,
    registry: object,
    base_cad_handoff: object | None,
    baseline_context: object,
) -> dict[str, object]: ...

def validate_candidate_selection(
    payload: object,
    *,
    revisions: object,
    registry: object,
    base_cad_handoff: object | None,
    baseline_context: object,
) -> dict[str, object]: ...
```

The normalized selection contains exactly:

```text
schema_version
selection_id
state = SELECTED_FOR_REVIEW
run_id
baseline_revision_sha256
candidate_revision_sha256
candidate_revision_id
eligible_candidate_revision_sha256s
selection_context_sha256
candidate_selection_sha256
```

`selection_context_sha256` is the existing canonical hash of the normalized accepted R3/R2/baseline context needed to re-check freshness. It is not approval evidence.

### Step 1: Add Task-2 RED selection matrix

- [ ] valid explicit exact candidate selection -> `SELECTED_FOR_REVIEW`;
- [ ] unknown candidate hash -> fail closed;
- [ ] candidate list permutation -> same selection ID/checksum;
- [ ] selected stale candidate -> fail closed;
- [ ] selected foreign-scope candidate -> fail closed;
- [ ] candidate bound to old baseline -> fail closed;
- [ ] candidate bound to stale R3/R2 context -> fail closed;
- [ ] mixed candidates from different run/baseline scopes -> fail closed;
- [ ] duplicate candidate SHA with conflicting record -> fail closed;
- [ ] caller attempts to select by filename/path/ordinal/quality score -> fail closed;
- [ ] no implicit "best candidate" computation exists;
- [ ] `approval`, `accepted`, `published`, `current`, `PASS`, verdict, or repair fields -> fail closed;
- [ ] caller mutation after selection build cannot change normalized selection.

### Step 2: Add supersession/rollback RED tests

A new selection artifact may select a previously known candidate. This is logical rollback only.

- [ ] selection A then selection B leaves both candidate revisions unchanged;
- [ ] a later selection can point back to A without changing A or B;
- [ ] selection ID/hash changes when the selected revision changes;
- [ ] prior selection artifact remains immutable;
- [ ] no CAD open/save/copy/rollback function is invoked;
- [ ] no backup filename is used as revision/selection identity;
- [ ] candidate rejected downstream may remain referenced historically but is not automatically deleted;
- [ ] a new repaired workspace must be sealed as a new candidate before it can be selected.

### Step 3: Prove Task-2 meaningful RED

- [ ] Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_candidate_revision.py -q -p no:cacheprovider
```

Expected: FAIL only because Task-2 selection behavior/public surface is missing. Record exact failures.

- [ ] Commit RED-only changes normally.

### Step 4: Implement minimal selection validation/binding

- [ ] Validate every supplied candidate with Task-1 `validate_candidate_revision()` against the exact current accepted context.
- [ ] Require `evaluate_candidate_revision_freshness()` -> `CURRENT` for the selected candidate.
- [ ] Normalize the eligible candidate SHA set deterministically.
- [ ] Require the exact caller/server-selected SHA to be present; do not rank or score candidates.
- [ ] Derive `selection_id` deterministically from schema domain, run/baseline identity, normalized eligible candidate set, selected candidate SHA, and `selection_context_sha256`.
- [ ] Compute `candidate_selection_sha256` using `canonical_json_sha256()` with self-checksum excluded.
- [ ] Return a deep normalized copy.
- [ ] Do not import approval, visual verdict, repair, publisher, AutoCAD, filesystem, network, or model owners.

### Step 5: Prove Task-2 repeated GREEN

- [ ] Run five focused passes and require identical counts:

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_candidate_revision.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

### Step 6: Run upstream/static/canonical gates

- [ ] Run Gate-0 final R1/R2/R3 focused regressions.
- [ ] Run:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/candidate_revision.py tests/test_cad_agent_candidate_revision.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
git diff --name-only "$env:R4_TASK_BASE_SHA"..HEAD
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

The Task-2 runtime branch diff must contain only the same two R4 core paths.

### Step 7: Commit normally and STOP WRITE for review

- [ ] Commit only the two R4 paths.

**Paired independent reviewer domains:** candidate-selection/authority-separation reviewer + stale-context/determinism/integration reviewer.

**Task-2 STOP conditions:** automatic quality ranking is required; approval/verdict is needed to select; a candidate needs CAD mutation inside R4; a new history store is proposed; existing candidate evidence must be deleted/overwritten; any third path is needed.

---

## Task 3: Bind immutable R4 references through existing manifest/checkpoint owner

**Conceptual output:** optional manifest-owned candidate revision references, immutable selection-history references, and one selected-candidate-for-review pointer. No new store, no acceptance/current/published promotion.

**Issue separately after Task 2 is accepted/merged and after a fresh exact overlap check.**

**Files:**

- Modify first for RED: `tests/test_cad_agent_candidate_revision.py`
- Modify only after meaningful RED: `cad_agent/manifest.py`
- Modify only after meaningful RED: `cad_agent/pdf.py`
- Do not modify: `cad_agent/candidate_revision.py`

**Consumes:** accepted Task-2 R4 validators and existing manifest atomic/legacy APIs.

**Manifest-owned proposed public surface:**

```python
CANDIDATE_REVISION_REFERENCE_SCHEMA_VERSION = "candidate-revision-reference-1.0"
CANDIDATE_SELECTION_REFERENCE_SCHEMA_VERSION = "candidate-selection-reference-1.0"

def validate_candidate_revision_bindings(manifest: object) -> dict[str, object]: ...

def bind_candidate_revision_reference(
    manifest: Mapping[str, object],
    *,
    revision: object,
    artifact: str,
) -> dict[str, object]: ...

def bind_candidate_selection_reference(
    manifest: Mapping[str, object],
    *,
    selection: object,
    artifact: str,
) -> dict[str, object]: ...
```

`bind_candidate_selection_reference()` appends a new immutable selection reference and updates only the non-authoritative `selected_candidate_revision_sha256` pointer to the selection's candidate. It never updates release/accepted/current-production/published state.

### Proposed manifest fields

When present, the existing run/PDF manifest may contain:

```text
candidate_revision_refs[]
candidate_selection_refs[]
selected_candidate_revision_sha256
```

Legacy manifests without these fields remain field/behavior compatible and are not rewritten merely by reading.

A candidate revision reference contains exactly:

```text
schema_version = candidate-revision-reference-1.0
revision_id
revision_sha256
artifact
baseline_revision_sha256
registry_sha256
```

A selection reference contains exactly:

```text
schema_version = candidate-selection-reference-1.0
selection_id
selection_sha256
artifact
selected_candidate_revision_sha256
```

`artifact` must be one safe normalized relative artifact path/name inside the owning run output; absolute paths, `..`, empty components, drive roots, UNC roots, and reparse authority are not accepted as identity.

### Step 1: Add RED legacy and manifest-binding tests

- [ ] legacy image manifest without R4 fields reads with exactly prior safe defaults and no injected R4 null/empty fields;
- [ ] legacy PDF manifest without R4 fields behaves the same;
- [ ] first valid candidate revision reference binds by copied normalized data;
- [ ] same reference rebind is idempotent;
- [ ] same revision ID with different revision hash -> fail closed;
- [ ] duplicate revision SHA under contradictory metadata -> fail closed;
- [ ] unsafe/absolute/traversal artifact path -> fail closed;
- [ ] malformed optional revision reference blocks `read_manifest()`;
- [ ] malformed optional revision reference blocks `read_pdf_manifest()`;
- [ ] caller mutation after bind cannot mutate returned manifest reference.

### Step 2: Add RED selection-history/pointer tests

- [ ] selection can reference only an already bound candidate revision;
- [ ] selection reference is appended; prior selection refs remain;
- [ ] selection A -> B -> A preserves all three selection records and both candidate refs;
- [ ] `selected_candidate_revision_sha256` follows only the newest valid selection reference;
- [ ] same selection reference rebind is idempotent;
- [ ] same selection ID/different hash -> fail closed;
- [ ] selection cannot target a stale/foreign candidate when Task-2 validation is run before binding;
- [ ] manifest binding never changes `release_profile`;
- [ ] manifest binding never changes `authoritative_release_eligible`;
- [ ] no `accepted`, `published`, production-current, approval, or verdict field is created;
- [ ] moving selection pointer does not delete candidate artifacts/evidence.

### Step 3: Prove meaningful Task-3 RED

- [ ] Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_candidate_revision.py -q -p no:cacheprovider
```

Expected: FAIL only because the manifest-owned R4 binding APIs/reader behavior are missing.

- [ ] Commit the RED-only test modification normally.

### Step 4: Implement manifest-owned closed reference validation

- [ ] Modify `cad_agent/manifest.py` only for the R4 reference constants/helpers.
- [ ] Import Task-2 R4 validators only in the direction `manifest -> candidate_revision`; `candidate_revision.py` must not import manifest.
- [ ] Deep-copy caller data.
- [ ] Keep revision/selection reference arrays deterministic by stable ID/hash ordering for validation while preserving explicit selection-history append order where order represents successive selection events.
- [ ] Validate safe relative artifact strings without reading/opening the artifact in the pure binding helper.
- [ ] Ensure conflicting same-ID/different-hash binding fails closed.
- [ ] Ensure `selected_candidate_revision_sha256` points to one bound revision and is derived from the latest valid selection reference.
- [ ] `write_manifest()` remains the sole atomic writer and is not replaced.

### Step 5: Use the same owner from both manifest readers

- [ ] Extend `read_manifest()` to validate optional R4 fields only through `validate_candidate_revision_bindings()`.
- [ ] Extend `cad_agent.pdf.read_pdf_manifest()` to call the same manifest-owned validator.
- [ ] Do not define PDF-specific revision-reference validation.
- [ ] Preserve absent-field behavior for legacy manifests.

### Step 6: Prove Task-3 focused GREEN

- [ ] Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest \
  tests/test_cad_agent_candidate_revision.py \
  tests/test_cad_agent_source_bundle_manifest.py \
  tests/test_cad_agent_cli.py \
  tests/test_cad_agent_pdf.py \
  -q -p no:cacheprovider
```

Expected: PASS. Existing SourceBundle binding and run/resume behavior must not be weakened.

### Step 7: Run broader manifest/resume and R4 regressions

- [ ] Run accepted R1/R2/R3 focused suites named by Gate 0.
- [ ] Run ordinary `run`/`resume` and PDF run/resume tests.
- [ ] Run exact R4 Task-1/Task-2 suite.
- [ ] Do not execute live AutoCAD.

### Step 8: Run Ruff, architecture, diff and canonical gates

- [ ] Run:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/manifest.py cad_agent/pdf.py tests/test_cad_agent_candidate_revision.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
git diff --cached --check
git diff --name-only "$env:R4_TASK_BASE_SHA"..HEAD
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

The Task-3 branch diff must contain exactly:

```text
cad_agent/manifest.py
cad_agent/pdf.py
tests/test_cad_agent_candidate_revision.py
```

### Step 9: Commit normally and STOP WRITE

- [ ] Commit only the three Task-3 paths.

**Paired independent reviewer domains:** manifest/backward-compatibility/truth-store reviewer + revision-authority/promotion-separation reviewer.

**Task-3 STOP conditions:** `cad_agent/cli.py` is needed; a new manifest/database/store path is proposed; R4 core must change because integration cannot use its accepted API; PDF would need a second validator; release/accepted/published state must change; another active writer owns `manifest.py` or `pdf.py`.

---

## Whole-R4 invariant matrix

Before Master PO can consider R4 runtime complete, independently prove all of the following.

### Candidate/revision invariants

- [ ] Every R4 revision is `SEALED_CANDIDATE` only.
- [ ] No sealed candidate is mutated in place.
- [ ] New mutation -> new disposable workspace -> new candidate revision.
- [ ] Revision ID/hash is deterministic and order-independent.
- [ ] Parent/baseline lineage is acyclic and scope-bound.
- [ ] Prior candidate artifacts and references remain intact.

### Upstream/provenance invariants

- [ ] Final R1/R2/R3 identity is validated only through accepted owners.
- [ ] R4 never becomes component/view registry.
- [ ] R4 never reconstructs Base-CAD provenance.
- [ ] Linked R3 impacts cannot be silently omitted.
- [ ] Stale Base-CAD/R3/baseline evidence fails closed.
- [ ] Old stale candidate remains historical evidence and is never silently rebound.

### Authority invariants

- [ ] Selection means only `SELECTED_FOR_REVIEW`.
- [ ] No automatic quality ranking.
- [ ] No approval issuer.
- [ ] No visual/engineering verdict.
- [ ] No repair execution.
- [ ] No accepted state.
- [ ] No production-current transition.
- [ ] No publisher.

### Persistence invariants

- [ ] Existing manifest/checkpoint owner is the only durable reference owner.
- [ ] Legacy manifests remain compatible.
- [ ] Candidate/selection history is preserved across pointer changes.
- [ ] No second revision database/CAS/directory.
- [ ] `write_manifest()` remains the atomic writer.

### CAD safety invariants

- [ ] Source/Base-CAD/accepted/current drawing are immutable R4 inputs.
- [ ] R4 core has no CAD I/O.
- [ ] Existing live owner retains backup/rollback.
- [ ] Existing AutoCAD/File IPC retains mutation transport.
- [ ] AutoCAD live is not required for core RED/GREEN.

---

## PASS / FAIL / SKIP / NOT RUN semantics

| State | Meaning |
|---|---|
| `PASS` | The exact check ran against the stated head/evidence and satisfied every required assertion. |
| `FAIL` | The exact check ran and contradicted an invariant. It blocks progression. |
| `SKIP` | An explicitly optional/gated probe was intentionally skipped under a declared prerequisite. It is not acceptance evidence. |
| `NOT RUN` | A required live/private/environment operation was unavailable or not attempted. It is never promoted to PASS. |

Unavailable AutoCAD/private data cannot be used to block the pure R4 core when those operations are outside the task, but they also cannot be claimed as live acceptance.

---

## Review topology

Each runtime child Issue requires at minimum:

1. sole bounded writer on exact allowlist;
2. independent domain reviewer for revision identity/authority or manifest compatibility as named by the task;
3. independent integration/CI reviewer on exact final head/current-main synthetic;
4. Master PO as final acceptance/merge authority.

Reviewers remain read-only. Findings are fixed only by normal forward writer commits inside the issued allowlist.

---

## Dependency / overlap matrix

| Lane | R4 dependency | Write overlap policy |
|---|---|---|
| Active/final R1 Source Fusion | must be accepted before R4 | no R1 path changes; read-only dependency |
| PR #129 R2 planning | non-authoritative planning input only | no branch/path reuse; keep #129 DRAFT/HOLD MERGE independently |
| Final R2 runtime | required before R4 | accepted evidence read-only; no R2 production edit |
| Moving #128 R3 planning | non-authoritative planning input only | do not use moving API as implementation contract |
| Final R3 runtime | immediate dependency | accepted registry/impact API read-only; R4 never writes R3 owner |
| Existing manifest/PDF owner | Task 3 only | fresh overlap check immediately before Task-3 issuance |
| Wave 1A `agent_lib`/vision worker lanes | unrelated | no overlap |
| Luna/Issue #72 local AutoCAD lane | live operator only | R4 core does not control AutoCAD; no concurrent session authority |
| `dxf_builder_lib` | candidate artifact producer | no R4 write |
| `cad_agent.live` / repair owners | backup/rollback evidence | no R4 write; no duplicate executor |
| Future R5 | consumes sealed R4 candidate | R4 must not pre-implement verdict |
| Future R6 | may produce repaired child workspace | R4 seals new revision after external mutation; no repair execution |
| Future R7 | promotion/publication | R4 never modifies current/published authority |

If any active writer owns a proposed child-task path at issuance time, STOP and reissue after the overlap is resolved. Do not rebase or silently widen.

---

## Hosted/current-main verification for every child PR

After local/focused GREEN and before acceptance:

- [ ] exact cumulative changed paths match the Issue allowlist;
- [ ] branch ancestry equals the exact issuance base plus normal forward commits;
- [ ] hosted `tests` = SUCCESS on exact head/current-main synthetic;
- [ ] hosted `reuse-declaration` = SUCCESS;
- [ ] any additional required docs/architecture workflow = SUCCESS;
- [ ] canonical verifier counts are recorded literally;
- [ ] real/private probe states remain literal `SKIP`/`NOT RUN` where unavailable;
- [ ] AutoCAD live state remains literal `NOT RUN` unless separately authorized and actually executed;
- [ ] unresolved review threads = 0 before Master PO acceptance;
- [ ] no PR body claims acceptance/promotion authority that the code does not own.

---

## Migration

### Core Tasks 1–2

Additive only. The two R4 core files introduce no persistent state and require no migration of existing artifacts.

### Task 3

Add optional manifest fields only. Existing manifests without R4 fields stay readable and are not rewritten on read.

No existing revision/current/published record is migrated into R4 automatically.

---

## Rollback

### Core

Revert/remove the R4 core commits. R1/R2/R3, existing manifests, DXF, repair, Visual Supervisor, and AutoCAD behavior remain unchanged.

### Manifest integration

Revert the optional manifest-binding changes. Legacy manifests remain authoritative and candidate artifact files are not deleted.

### Candidate operation rollback

R4 does not perform CAD rollback. Existing live/repair owner handles workspace backup/recovery. R4 logical rollback is a new selection reference to a prior sealed candidate while preserving all historical revision and selection references.

---

## Final STOP conditions

Stop and report `R4 REBASELINE REQUIRED` if any of the following appears during rebaseline or runtime:

- final accepted R1/R2/R3 API semantics cannot provide the required immutable identity/provenance seam;
- R3 cannot prove logical component/view correspondence across snapshots;
- no accepted current/baseline revision reference owner exists;
- R4 would need to parse source/CAD/DXF or calculate geometry correspondence;
- R4 would need to call Base-CAD extraction;
- R4 would need to modify R3 registry production;
- R4 would need a database/CAS/revision directory/second manifest;
- R4 would need AutoCAD/File IPC transport;
- R4 would need backup/restore or repair execution;
- R4 would need to issue approval;
- R4 would need to produce visual/engineering PASS;
- R4 would need to mark a candidate accepted/current/published or release-eligible;
- an upstream accepted test must be weakened/skipped to obtain GREEN;
- private/customer CAD is required for the first runtime slice;
- dependency/lock/workflow/schema-directory change appears necessary;
- any runtime child needs a path outside its exact issued allowlist.

Do not solve a STOP condition by inventing a compatibility shim or duplicate owner inside R4.

---

## Runtime issuance order

After Gate 0 completes successfully:

```text
R4 Task 1 — seal deterministic candidate revision core
    -> hosted GREEN + independent review + merge
R4 Task 2 — explicit selection/supersession/logical rollback
    -> hosted GREEN + independent review + merge
R4 Task 3 — existing-manifest revision/selection references
    -> hosted GREEN + independent review + merge
R4 complete
    -> fresh R5 runtime/planning rebaseline
```

No R4 child authorizes R5 verdict, R6 repair execution, or R7 promotion/publication.