# R2 Base CAD Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one stateless Base CAD Adapter that binds accepted R1 source/fusion identity to existing S3A/S3B exact-base reuse, delegates candidate-only extraction through the accepted live owner, and emits a deterministic frozen provenance handoff for future R3 without creating another CAD, extraction, registry, revision, approval, or publication authority.

**Architecture:** Add one adjacent `cad_agent/base_cad_adapter.py` owner and one focused test file. The adapter reuses final accepted R1 validators/hashes, S3A inspection/extraction-plan contracts, `canonical_json_sha256()`, and S3B `DotNetIPCClient.exact_base_xref_*`; it never opens/parses CAD or implements File IPC/path policy. R2 outputs closed hash-bound transfer records only; R3/R4 remain responsible for registration/revision state.

**Tech Stack:** Python 3.11; existing `cad_agent` R1 contracts; existing `mcp_integration_lib.exact_base_xref`; existing `mcp_integration_lib.dotnet_ipc.DotNetIPCClient`; pytest; Ruff; repository architecture checker; canonical verifier. No new dependency or lock change.

## Global Constraints

- Runtime execution is locked until **complete R1 acceptance/merge + fresh R2 rebaseline + accepted S3B live inspection/extraction PASS**.
- Before Task 1, final current-main R1 must expose semantically equivalent `validate_source_fusion_packet()`, `source_fusion_sha256()`, and `require_source_fusion_match(*, source_bundle, custody, fusion)` APIs. Material mismatch => `R2 REBASELINE REQUIRED`.
- S3A `validate_xref_inspection()`, `build_extraction_plan()`, `validate_extraction_plan()`, `REUSED_FROM_BASE_CAD`, and `TRANSFORM_POLICY` remain authoritative and are not duplicated.
- S3B `DotNetIPCClient.exact_base_xref_inspection()` / `exact_base_xref_extraction()` and the .NET policy/reader/dispatcher remain the sole live inspection, path-policy, fresh-preflight, and candidate-mutation owners.
- Original exact-base source and accepted/current CAD are immutable. Mutation is allowed only in a new disposable candidate through S3B.
- No global deformation, reflection, arbitrary matrix, non-uniform scale, fit-to-image transform, or adapter-level whole-drawing transform.
- No approval issuer. R2 may build only a `PROPOSED` plan; live execution consumes an already `APPROVED` S3A plan plus matching external approval object.
- No component/view registry, revision store/current pointer, repair executor, visual/engineering verdict, publisher, OCR/model/provider call, CAD parser, DXF builder, new transport, new dispatcher, or new manifest/checkpoint store.
- First runtime tests are synthetic only. No private/customer/accepted CAD and no live AutoCAD operation in hosted tests.
- No schema-directory, dependency, lock, workflow, `agent_lib/**`, `cad_agent/source_fusion.py`, `mcp_integration_lib/**`, or `autocad_plugin/**` changes are presumed by this plan.
- Each task starts with meaningful RED before production edits, ends in a normal forward commit, and keeps PASS / FAIL / SKIP / NOT RUN literal.
- No amend, rebase, squash, force-push, or main-sync after a runtime branch is issued.

---

## Pre-issuance Gate: Fresh R1/S3 Rebaseline

This is a mandatory read-only gate before Task 1 is issued; it creates no files.

- [ ] **Step 1: Verify final accepted R1 current-main identity**

Record exact `main` SHA after the full R1 Source Bundle/Fusion Adapter merges. Confirm no active R1 writer remains on `cad_agent/source_fusion.py` or its tests.

- [ ] **Step 2: Verify the final R1 seam**

Confirm current main provides semantically equivalent public calls:

```python
validate_source_fusion_packet(payload: object) -> dict[str, object]
source_fusion_sha256(payload: object) -> str
require_source_fusion_match(
    *,
    source_bundle: object,
    custody: object,
    fusion: object,
) -> None
```

Confirm a reusable/ready fusion packet can be distinguished from a blocking unresolved packet without R2 interpreting conflict internals.

- [ ] **Step 3: Verify exact-base identity can be bound without reopening a path**

Prove R2 can derive one exact-base item from the validated SourceBundle and accepted custody with:

```text
kind = EXACT_BASE_CAD
role = BASE_CAD
source_id
SourceBundle declared sha256
custody observed_sha256
run_id
```

If zero/multiple base sources require arbitration, or final R1 does not expose safe source/custody matching, stop with `R2 REBASELINE REQUIRED`.

- [ ] **Step 4: Verify S3A/S3B accepted APIs remain intact**

Read-only verify:

```python
mcp_integration_lib.exact_base_xref.validate_xref_inspection
mcp_integration_lib.exact_base_xref.build_extraction_plan
mcp_integration_lib.exact_base_xref.validate_extraction_plan
mcp_integration_lib.dotnet_ipc.DotNetIPCClient.exact_base_xref_inspection
mcp_integration_lib.dotnet_ipc.DotNetIPCClient.exact_base_xref_extraction
```

Confirm S3B still owns approval equality, canonical path/root/alias policy, source hash/revision checks, fresh live preflight immediately before mutation, failure cleanup, and disposable-candidate-only output.

- [ ] **Step 5: Verify accepted S3B live evidence**

Require all of:

```text
S3B live inspection: PASS
S3B live extraction: PASS
source/accepted immutability: PASS
cleanup/restoration: PASS
```

`SKIP` or `NOT RUN` blocks Task 1 issuance but does not justify code changes.

- [ ] **Step 6: Verify write-set overlap**

Task 1 may start only if no active writer owns either future R2 path:

```text
cad_agent/base_cad_adapter.py
tests/test_cad_agent_base_cad_adapter.py
```

---

## Proposed Runtime File Structure

### Create in Task 1

- `cad_agent/base_cad_adapter.py` — stateless R1/S3 binding, deterministic records, proposal construction, S3B delegation, frozen handoff, stale/re-extraction evaluation.
- `tests/test_cad_agent_base_cad_adapter.py` — synthetic contract, determinism, stale, authority, S3A reuse, S3B delegation, privacy, and no-second-owner tests.

### Modify in Tasks 2–3

- `cad_agent/base_cad_adapter.py`
- `tests/test_cad_agent_base_cad_adapter.py`

### Do not modify during the planned first R2 sequence

- `cad_agent/source_bundle.py`
- `cad_agent/source_integrity.py`
- `cad_agent/source_fusion.py`
- `cad_agent/manifest.py`
- `cad_agent/pdf.py`
- `cad_agent/cli.py`
- `cad_agent/drawing_setup.py`
- `cad_agent/dimension_pilot.py`
- `primitive_ir_lib/**`
- `semantic_ir_lib/**`
- `dxf_builder_lib/**`
- `agent_lib/**`
- `mcp_integration_lib/**`
- `autocad_plugin/**`
- `contracts/**`
- dependency/lock files
- `.github/workflows/**`
- private/source/accepted CAD

Any need for a third path is a STOP condition for the current runtime issue, not implicit permission to widen it.

---

## Task 1: Bind Final R1 Fusion to One Eligible Live Exact Base

**Conceptual deliverable:** one closed deterministic `base-cad-binding-1.0` record proving that the accepted R1 source/custody/fusion identity and one fresh S3A-compatible S3B live inspection describe the same eligible exact base.

**Files:**

- Create: `tests/test_cad_agent_base_cad_adapter.py`
- Create after meaningful RED: `cad_agent/base_cad_adapter.py`
- Modify: none

**Interfaces:**

- Consumes:
  - `cad_agent.source_bundle.validate_source_bundle()`
  - `cad_agent.source_bundle.source_bundle_sha256()`
  - `cad_agent.source_integrity.validate_source_custody()`
  - `cad_agent.source_integrity.source_custody_sha256()`
  - final accepted `cad_agent.source_fusion.validate_source_fusion_packet()`
  - final accepted `cad_agent.source_fusion.source_fusion_sha256()`
  - final accepted `cad_agent.source_fusion.require_source_fusion_match()`
  - `mcp_integration_lib.exact_base_xref.validate_xref_inspection()`
  - `mcp_integration_lib.exact_base_xref.TRANSFORM_POLICY`
  - `cad_agent.drawing_contracts.canonical_json_sha256()`
- Produces:

```python
BASE_CAD_BINDING_SCHEMA_VERSION = "base-cad-binding-1.0"

class BaseCadAdapterError(ValueError): ...

def build_base_cad_binding(
    *,
    source_bundle: object,
    custody: object,
    fusion: object,
    live_inspection: object,
) -> dict[str, object]: ...

def validate_base_cad_binding(payload: object) -> dict[str, object]: ...

def base_cad_binding_sha256(payload: object) -> str: ...
```

Normalized binding fields are exactly:

```text
schema_version
run_id
source_bundle_sha256
source_custody_sha256
source_fusion_sha256
base_source {source_id, sha256, revision}
inspection_id
inspection_sha256
target_drawing_sha256
eligible_component_ids
transform_policy
state = READY_FOR_SELECTION
```

- [ ] **Step 1: Add Task-1 test imports and a complete synthetic fixture set**

Create `tests/test_cad_agent_base_cad_adapter.py` with synthetic R1 bundle/custody/fusion fixtures matching the final accepted contracts and an S3A inspection fixture with one exact base, vehicle/model PASS, all five required critical dimensions PASS, `changed=false`, equal DBMOD, read-only Xref, and two inspected BLOCK components.

Import the planned Task-1 APIs only from `cad_agent.base_cad_adapter`.

- [ ] **Step 2: Add RED tests for the exact R1/S3 binding matrix**

Cover at minimum:

```text
valid READY R1 + eligible S3 inspection -> READY_FOR_SELECTION
R1 fusion BLOCKED_UNRESOLVED -> fail closed
custody non-READY -> fail closed
zero exact-base SourceBundle items -> fail closed
multiple EXACT_BASE_CAD/BASE_CAD items -> fail closed
source_id mismatch -> fail closed
SourceBundle/custody/S3 source SHA mismatch -> fail closed
run_id mismatch -> fail closed
S3 inspection eligible=false -> fail closed
S3 conflict -> fail closed through S3A validator
xref read_only=false -> fail closed through S3A validator
changed=true or DBMOD drift -> fail closed through S3A validator
missing vehicle/model/critical dimension -> fail closed through S3A validator
relative_path spelling alone cannot authorize a mismatched source hash
unknown binding field -> validation failure
absolute path/private path fields are absent from binding and error strings
```

- [ ] **Step 3: Add deterministic identity tests**

Assert:

```python
left = build_base_cad_binding(...)
right = build_base_cad_binding(...)
assert left == right
assert base_cad_binding_sha256(left) == base_cad_binding_sha256(right)
assert left["eligible_component_ids"] == sorted(left["eligible_component_ids"])
```

Permute input component order without changing semantics and require the same normalized binding/hash. Change source SHA, revision, inspection ID, target drawing SHA, or eligible component membership and require a different binding hash.

- [ ] **Step 4: Run focused RED before creating production code**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_base_cad_adapter.py -q -p no:cacheprovider
```

Expected: meaningful collection/import failure because `cad_agent.base_cad_adapter` does not exist. Record command, exact failure count, and reason.

- [ ] **Step 5: Implement the smallest closed binding owner**

Create `cad_agent/base_cad_adapter.py` and implement the Task-1 APIs only.

The builder must:

```python
normalized_bundle = validate_source_bundle(source_bundle)
normalized_custody = validate_source_custody(custody)
normalized_fusion = validate_source_fusion_packet(fusion)
require_source_fusion_match(
    source_bundle=normalized_bundle,
    custody=normalized_custody,
    fusion=normalized_fusion,
)
normalized_inspection = validate_xref_inspection(live_inspection)
```

Then require:

- custody/fusion are reusable according to the final accepted R1 public contract;
- exactly one SourceBundle item has `kind == "EXACT_BASE_CAD"` and `role == "BASE_CAD"`;
- the corresponding custody item's `observed_sha256` agrees with the SourceBundle SHA;
- inspection `run_id`, `base_source.source_id`, and `base_source.sha256` agree with R1;
- inspection is eligible and already proves read-only/no-conflict/no-mutation conditions through S3A;
- `base_source.revision` comes only from the validated S3 inspection;
- no path string participates in authority checks;
- component IDs are sorted and unique;
- the binding is validated before return.

Hash only validated normalized records with existing `canonical_json_sha256()`.

- [ ] **Step 6: Run Task-1 focused GREEN**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_base_cad_adapter.py -q -p no:cacheprovider
```

Expected: PASS, zero skips for the Task-1 synthetic suite.

- [ ] **Step 7: Run focused reuse regressions**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest \
  tests/test_cad_agent_source_bundle.py \
  tests/test_cad_agent_source_integrity.py \
  tests/test_cad_agent_source_fusion.py \
  mcp_integration_lib/tests/test_exact_base_xref.py \
  tests/test_cad_agent_base_cad_adapter.py \
  -q -p no:cacheprovider
```

Expected: PASS. Any failure in accepted R1/S3 behavior is a Task-1 blocker; do not weaken upstream tests.

- [ ] **Step 8: Run static/architecture/diff gates**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/base_cad_adapter.py tests/test_cad_agent_base_cad_adapter.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
git diff --name-only <TASK1_BASE>..HEAD
```

The final command must list exactly the two Task-1 CREATE paths.

- [ ] **Step 9: Run canonical verifier supported by the runtime environment**

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Record exact PASS/FAIL/SKIP/NOT RUN counts. AutoCAD live is not rerun by this hosted/offline task.

- [ ] **Step 10: Commit Task 1 normally**

```powershell
git add cad_agent/base_cad_adapter.py tests/test_cad_agent_base_cad_adapter.py
git commit -m "feat: bind R1 fusion to eligible exact base"
```

**Paired independent reviewer domains:** source-integrity/provenance/reuse authority reviewer + integration/CI/write-set reviewer.

**Task-1 STOP conditions:** final R1 seam differs materially; third path required; source bytes/path must be reopened; S3A eligibility must be duplicated; multiple base-source arbitration is required; path strings would become authority; accepted R1/S3 test must be weakened; dependency/schema/manifest change appears necessary.

---

## Task 2: Build Only Proposed S3A Extraction Selections and Revalidate External Approval

**Conceptual deliverable:** deterministic extraction proposal generation through S3A, plus a fail-closed check that an externally approved S3A plan still matches the exact R2 binding and inspection. R2 issues no approval.

**Files:**

- Modify: `tests/test_cad_agent_base_cad_adapter.py`
- Modify after meaningful RED: `cad_agent/base_cad_adapter.py`
- Create: none

**Interfaces:**

- Consumes Task-1 binding APIs plus:
  - `mcp_integration_lib.exact_base_xref.build_extraction_plan()`
  - `mcp_integration_lib.exact_base_xref.validate_extraction_plan()`
  - `mcp_integration_lib.exact_base_xref.REUSED_FROM_BASE_CAD`
  - `mcp_integration_lib.exact_base_xref.TRANSFORM_POLICY`
- Produces:

```python
def build_proposed_base_cad_extraction(
    *,
    binding: object,
    live_inspection: object,
    selections: object,
    impacted_views: object,
    plan_id: str,
) -> dict[str, object]: ...

def require_approved_base_cad_extraction_match(
    *,
    binding: object,
    live_inspection: object,
    approved_extraction_plan: object,
) -> dict[str, object]: ...
```

The second helper returns the normalized already-approved S3A plan or raises. It never changes approval state.

- [ ] **Step 1: Add RED proposal/reuse tests**

Cover:

```text
valid subset -> S3A plan with approval.status=PROPOSED and reference=null
proposal source/run/inspection/target hashes exactly match binding
component metadata comes from inspection, never caller
uninspected logical_component_id -> fail closed
caller-supplied source_handle/layer/block/candidate_handle -> rejected by S3A shape
translation + rotation + positive uniform scale -> allowed
zero/negative scale -> rejected
non-uniform/global matrix/reflection/global_transform -> rejected
whole-drawing/global scale field -> rejected
permutation of selection order -> deterministic normalized plan
caller input mutation after return cannot mutate normalized adapter output
```

- [ ] **Step 2: Add RED external-approval tests**

Construct an S3A plan that is already `APPROVED` by external test data and verify:

```text
APPROVED + exact binding/inspection -> accepted normalized plan
PROPOSED plan passed to approval-match helper -> fail closed
changed approval reference -> fail closed
changed source revision/hash -> fail closed
changed target drawing SHA -> fail closed
changed inspection_id/run_id -> fail closed
component added after approval -> fail closed
transform changed after approval -> fail closed
```

No test calls an approval issuer.

- [ ] **Step 3: Run Task-2 RED against the Task-1 head**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_base_cad_adapter.py -q -p no:cacheprovider
```

Expected: FAIL because Task-2 functions are absent. Record exact failures attributable to the missing behavior.

- [ ] **Step 4: Implement proposal construction strictly through S3A**

`build_proposed_base_cad_extraction()` must:

1. validate the binding;
2. validate the current inspection with S3A;
3. recompute and compare inspection hash/binding source facts;
4. call `build_extraction_plan()` with the caller's logical IDs/local transforms and `impacted_views`;
5. require S3A's returned plan to remain `PROPOSED` with null approval reference;
6. return only the normalized S3A plan.

Do not reconstruct S3A component records or transforms manually.

- [ ] **Step 5: Implement approval-match as validation only**

`require_approved_base_cad_extraction_match()` must:

1. validate the same binding and inspection;
2. call `validate_extraction_plan(approved_extraction_plan, inspection=normalized_inspection)`;
3. require plan source/run/inspection/target identity to equal the binding;
4. require `approval.status == "APPROVED"` and a non-empty reference under existing S3A semantics;
5. return a deep normalized copy.

It must not add, replace, or synthesize approval fields.

- [ ] **Step 6: Run Task-2 focused GREEN and repeat for determinism**

```powershell
1..3 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_base_cad_adapter.py -q -p no:cacheprovider
}
```

All three runs must PASS with identical test counts.

- [ ] **Step 7: Run S3A + R1 regressions and static gates**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest \
  mcp_integration_lib/tests/test_exact_base_xref.py \
  tests/test_cad_agent_source_fusion.py \
  tests/test_cad_agent_base_cad_adapter.py \
  -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/base_cad_adapter.py tests/test_cad_agent_base_cad_adapter.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
git diff --name-only <TASK2_BASE>..HEAD
```

Task-2 diff must contain only the same two R2 paths.

- [ ] **Step 8: Run canonical verifier and commit**

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
git add cad_agent/base_cad_adapter.py tests/test_cad_agent_base_cad_adapter.py
git commit -m "feat: propose approved-bound base CAD extraction"
```

**Paired independent reviewer domains:** exact-base/S3A transform-and-approval-boundary reviewer + integration/CI/write-set reviewer.

**Task-2 STOP conditions:** any approval issuer is needed; S3A must be changed to accept the proposal; global deformation is requested; component membership must be inferred outside inspection; a generic CAD/extraction plan owner appears; any third path is needed.

---

## Task 3: Delegate to S3B and Emit Frozen R2-to-R3 Reuse Handoff

**Conceptual deliverable:** one live-delegation API that calls the existing S3B exact-base extraction method without bypasses, validates result invariants, emits `base-cad-reuse-handoff-1.0`, and evaluates later source/revision drift without overwriting frozen geometry.

**Files:**

- Modify: `tests/test_cad_agent_base_cad_adapter.py`
- Modify after meaningful RED: `cad_agent/base_cad_adapter.py`
- Create: none

**Interfaces:**

- Consumes Task-1/2 APIs plus:
  - `mcp_integration_lib.dotnet_ipc.DotNetIPCClient.exact_base_xref_extraction()`
  - existing S3B validated result shape.
- Produces:

```python
BASE_CAD_REUSE_HANDOFF_SCHEMA_VERSION = "base-cad-reuse-handoff-1.0"

def execute_base_cad_extraction(
    *,
    client: object,
    binding: object,
    live_inspection: object,
    approved_extraction_plan: object,
    approval: object,
    drawing_full_path: object,
    drawing_sha256: str,
    source_full_path: object,
    candidate_output_path: object,
) -> dict[str, object]: ...

def validate_base_cad_reuse_handoff(payload: object) -> dict[str, object]: ...

def base_cad_reuse_handoff_sha256(payload: object) -> str: ...

def evaluate_frozen_base_cad_reuse(
    *,
    handoff: object,
    current_live_inspection: object,
) -> dict[str, object]: ...
```

`execute_base_cad_extraction()` returns the normalized R2 handoff, not a new transport envelope.

Handoff fields are exactly:

```text
schema_version
run_id
source_bundle_sha256
source_custody_sha256
source_fusion_sha256
base_cad_binding_sha256
inspection_sha256
extraction_plan_sha256
base_source {source_id, sha256, revision}
candidate_input_sha256
candidate_output_sha256
live_preflight_evidence_sha256
components[] {
  logical_component_id
  source_handle
  source_layer
  source_block
  source_sha256
  source_revision
  candidate_handle
  transform
  provenance
}
source_handle_to_candidate_handle[]
```

No absolute paths or timestamps are stored in the handoff.

- [ ] **Step 1: Add a strict fake/client spy for hosted tests**

The fake exposes only:

```python
def exact_base_xref_extraction(self, *args, **kwargs) -> dict[str, object]: ...
```

It records call count/arguments and returns a synthetic result matching the accepted public S3B extraction-result example. It has no `request()` method so tests cannot accidentally exercise a generic transport path.

- [ ] **Step 2: Add RED delegation tests**

Cover:

```text
exact approved binding -> exactly one exact_base_xref_extraction call
PROPOSED plan -> zero S3B calls + fail closed
stale binding/inspection -> zero S3B calls + fail closed
approval object missing/mismatched -> zero S3B calls + fail closed before or through existing S3B equality semantics
adapter never calls generic request()/alternate operation
candidate/source/drawing path values are only passed to S3B and never persisted in handoff
```

- [ ] **Step 3: Add RED S3B-result invariant tests**

Require handoff refusal when synthetic S3B result claims any of:

```text
success != true
operation != exact_base_xref_extraction
changed != true on success
accepted_target_overwrite != false
source_mutated != false
source_saved != false
source_sha256_before != source_sha256_after
source SHA/revision differs from binding/approved plan
live_preflight.eligible != true
live_preflight.source_sha256 mismatch
live_preflight.target_drawing_sha256 mismatch
candidate_output_sha256 missing/invalid
component source metadata differs from approved plan
candidate handle missing or duplicate
source_handle_to_candidate_handle incomplete/inconsistent
unexpected provenance != REUSED_FROM_BASE_CAD
```

These are adapter-boundary cross-checks over returned accepted S3B facts, not a second implementation of S3B path or AutoCAD logic.

- [ ] **Step 4: Add RED frozen provenance/determinism tests**

Assert every handoff component freezes:

```text
source_sha256
source_revision
source_handle
source_layer
source_block
local transform
candidate_handle
REUSED_FROM_BASE_CAD
```

Permute S3B component/mapping order and require deterministic normalized ordering/hash. Change any frozen source/candidate/provenance fact and require a different handoff hash.

- [ ] **Step 5: Add RED stale/re-extraction tests**

`evaluate_frozen_base_cad_reuse()` must return exactly one of:

```text
CURRENT
STALE_REEXTRACTION_REQUIRED
```

Use a fresh S3A-valid inspection as the current source identity.

Require:

```text
same source_id + sha256 + revision -> CURRENT, no affected components
changed sha256 -> STALE_REEXTRACTION_REQUIRED
changed revision -> STALE_REEXTRACTION_REQUIRED
changed source_id -> STALE_REEXTRACTION_REQUIRED
stale result lists sorted affected logical_component_ids
stale result contains old/new source identity + reason codes
stale result contains no approval, candidate-handle rewrite, current-pointer, or mutation instruction
```

- [ ] **Step 6: Run Task-3 RED against Task-2 head**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_base_cad_adapter.py -q -p no:cacheprovider
```

Expected: FAIL only because Task-3 APIs/behavior are missing.

- [ ] **Step 7: Implement exact S3B delegation**

`execute_base_cad_extraction()` must:

1. validate the Task-1 binding;
2. validate current S3A inspection and compare its canonical hash/source identity with the binding;
3. call `require_approved_base_cad_extraction_match()`;
4. call exactly `client.exact_base_xref_extraction(...)` with the already-approved plan and approval object;
5. never call a generic `request()` or construct raw IPC operations;
6. normalize/check the returned extraction result;
7. emit the closed R2 handoff only after all invariants pass.

For production, runtime issuance must require the accepted `DotNetIPCClient` instance or an equally strict typed seam approved by the architecture checker; a generic transport callable is not an alternate authority.

- [ ] **Step 8: Implement frozen handoff validation/hash**

Use closed exact fields, deep normalized copies, sorted component/mapping lists, strict lowercase SHA-256 fields, and `canonical_json_sha256()` only.

Do not include:

```text
absolute drawing/source/candidate paths
started_at/completed_at/capture timestamp
raw S3B error text
component current/revision-registry state
view/layout ownership
visual/engineering verdict
approval/publish/repair fields
```

- [ ] **Step 9: Implement stale evaluation with no mutation authority**

Validate both the prior handoff and fresh current inspection. Compare only canonical source identity:

```text
source_id
sha256
revision
```

Return deterministic reason codes and affected logical component IDs. Do not call S3B extraction from the stale evaluator; re-extraction remains a proposal requiring a new approval/execution cycle.

- [ ] **Step 10: Run focused and broader GREEN**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest \
  tests/test_cad_agent_base_cad_adapter.py \
  mcp_integration_lib/tests/test_exact_base_xref.py \
  mcp_integration_lib/tests/test_dotnet_ipc.py \
  tests/test_cad_agent_source_bundle.py \
  tests/test_cad_agent_source_integrity.py \
  tests/test_cad_agent_source_fusion.py \
  -q -p no:cacheprovider
```

Hosted/offline tests must PASS. Any gated AutoCAD Mechanical live test remains `NOT RUN` or `SKIP` in this code task and must not be promoted to PASS.

- [ ] **Step 11: Run static, architecture, diff, canonical gates**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/base_cad_adapter.py tests/test_cad_agent_base_cad_adapter.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
git diff --name-only <R2_RUNTIME_BASE>..HEAD
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Cumulative R2 runtime diff must remain exactly:

```text
cad_agent/base_cad_adapter.py
tests/test_cad_agent_base_cad_adapter.py
```

- [ ] **Step 12: Run no-second-owner architecture assertions**

Focused tests must inspect the R2 module or import graph and prove it does not define/import ownership for:

```text
CAD parsing
DXF building
component/view registry
revision/current store
repair execution
visual verdict
approval issuance
publication
new IPC operation/request builder
filesystem source-byte opening
OCR/model/provider execution
```

Direct reuse imports from accepted R1/S3 and canonical hash owners are allowed.

- [ ] **Step 13: Commit Task 3 normally**

```powershell
git add cad_agent/base_cad_adapter.py tests/test_cad_agent_base_cad_adapter.py
git commit -m "feat: freeze exact-base reuse provenance"
```

**Paired independent reviewer domains:** AutoCAD/S3B candidate-mutation and provenance-boundary reviewer + integration/CI/current-main synthetic reviewer. Luna/local operator remains the live-evidence owner, not a repository writer for this task.

**Task-3 STOP conditions:** any S3B production edit is required; a new transport/dispatcher/path policy is needed; an accepted/current drawing must be mutated; live preflight would be duplicated or bypassed; R2 must persist component/current revision state; private CAD is needed; source/accepted immutability cannot be proven; result semantics cannot be normalized without schema change.

---

## Whole-R2 Verification and Handoff Gate

After Task 3, before R2 is declared complete:

- [ ] **Focused R2 tests** — PASS, zero skips for synthetic adapter tests.
- [ ] **R1 regressions** — SourceBundle, custody, final source-fusion tests PASS.
- [ ] **S3A regressions** — exact-base inspection/plan tests PASS.
- [ ] **S3B Python regressions** — `test_dotnet_ipc.py` PASS; live-only prerequisites remain literal `SKIP`/`NOT RUN` where not executed.
- [ ] **Ruff** — PASS on exactly the two R2 files.
- [ ] **Architecture ratchet** — PASS.
- [ ] **`git diff --check`** — PASS.
- [ ] **Cumulative path audit** — exactly the two R2 runtime paths.
- [ ] **Canonical verifier** — record exact PASS/FAIL/SKIP/NOT RUN counts.
- [ ] **Hosted `tests`** — PASS on exact head/current-main synthetic.
- [ ] **Hosted `reuse-declaration`** — PASS.
- [ ] **Other required hosted checks** — PASS.
- [ ] **Unresolved review threads** — 0 before Master PO acceptance.
- [ ] **Independent provenance/authority review** — PASS.
- [ ] **Independent integration/CI review** — PASS.

No result from an unavailable live gate may be relabeled PASS.

## PASS / FAIL / SKIP / NOT RUN Semantics

| State | Meaning in R2 |
|---|---|
| `PASS` | The named check actually executed against the exact stated head/evidence and satisfied its assertions. |
| `FAIL` | The named check executed and contradicted a required invariant. A FAIL blocks progression. |
| `SKIP` | An explicitly optional/gated probe was intentionally skipped under its declared prerequisite rule. It is not acceptance evidence. |
| `NOT RUN` | A required live/private/environment operation was unavailable or not attempted. It is never promoted to PASS. |

Historical accepted S3B live PASS may satisfy the pre-issuance dependency only when Master PO confirms it remains applicable to the accepted S3B implementation identity. R2 hosted tests do not recreate that live authority.

## Overlap Matrix

| Lane / owner | Paths or authority | R2 overlap result | Rule |
|---|---|---|---|
| Wave 1A active/future worker control | `agent_lib/**`, `cad_agent/vision_handoff.py`, worker-policy tests | `NONE` | R2 never modifies worker/provider control. |
| Active/future R1 Source Fusion | `cad_agent/source_fusion.py`, `tests/test_cad_agent_source_fusion.py`, possible final manifest-reference work | `NONE` in planned R2 write-set | R2 runtime waits for complete R1 merge and then imports the accepted seam read-only. |
| S3A exact-base contract | `mcp_integration_lib/exact_base_xref.py`, its tests | `READ-ONLY REUSE` | No modification; plan/inspection semantics stay S3A-owned. |
| S3B transport/.NET | `mcp_integration_lib/dotnet_ipc.py`, `autocad_plugin/**`, IPC contracts | `READ-ONLY REUSE` | R2 delegates through accepted methods; any production change requires rebaseline. |
| Luna / Issue #72 local lane | local AutoCAD session, live harness, potentially bounded live-test defect paths under separate Issues | `NO REPOSITORY OVERLAP` | Live AutoCAD remains serialized under one local operator; R2 writer does not control the same session. |
| Existing manifest/checkpoint owner | `cad_agent/manifest.py`, `cad_agent/pdf.py`, CLI run/resume | `NONE` in first R2 sequence | No second store/reference field is added. |
| DXF/native geometry owner | `dxf_builder_lib/**` | `NONE` | R2 does not generate changed/new geometry. |
| Future R3 registry | future `cad_agent` component/view-registry owner and tests | `NONE` | R2 emits transfer evidence only; no component/current/revision persistence. |
| Future R4 revision orchestrator | future candidate-revision owner | `NONE` | R2 does not mark current/accepted revision or own rollback history. |

## R3 Handoff Contract

R3 may rely only on the validated `base-cad-reuse-handoff-1.0` fields and its canonical SHA-256. R3 must not rely on:

- R2 process memory;
- absolute S3B paths;
- a “current component” state inside R2;
- implicit candidate ordering;
- ambient AutoCAD session state;
- old inspection IDs as mutation authority.

A future R3 plan may register the candidate handles and provenance under its own separately accepted store/contract. R2 remains stateless.

## Migration and Rollback

**Migration:** none. No existing schema, manifest, CAD file, registry, revision store, IPC contract, or producer artifact changes in the planned first R2 sequence.

**Rollback:** revert the R2 commits/remove the two R2 files. R1, S3A, S3B, manifests, DXF builder, and future R3/R4 owners remain unchanged. Disposable candidates from separately authorized live operations are cleaned by existing S3B/local-operator rules; source/accepted CAD require no rollback because they must never change.

## Runtime Issue Issuance Order

Issue R2 tasks strictly in this order after the pre-issuance gate:

```text
R2 Task 1 — Final R1 + S3 live exact-base binding
    -> independent PASS + merge
R2 Task 2 — Proposed selection + external-approved-plan revalidation
    -> independent PASS + merge
R2 Task 3 — Existing S3B delegation + frozen provenance handoff + stale proposal
    -> independent PASS + merge
R2 complete -> fresh R3 planning/runtime rebaseline
```

Each child Issue receives a fresh exact current-main SHA and only its exact two-path CREATE/MODIFY allowlist above. If any child needs a third path or wider authority, stop and return to Master PO instead of editing this plan ad hoc.

## Final STOP Conditions

Stop and report `R2 REBASELINE REQUIRED` rather than widening scope if any of these becomes true:

- final accepted R1 API/source identity is insufficient for Section 5 binding;
- R1 requires source arbitration that R2 would have to invent;
- S3A/S3B accepted API or fresh-preflight semantics materially changed;
- S3B live acceptance is not PASS;
- R2 needs to reopen/parse source CAD or inspect Xrefs independently;
- an S3B/File IPC/.NET production owner must change merely to support the adapter;
- global deformation is necessary to reuse the base;
- an approval issuer must be created;
- manifest/checkpoint/current-component persistence is required before R3/R4 defines ownership;
- a component registry or revision store starts appearing in R2;
- accepted/current/source CAD would be mutable;
- private/customer CAD is required for first runtime tests;
- dependency/lock/workflow/schema-directory changes are required;
- any accepted upstream test must be weakened, skipped, or rewritten to obtain GREEN.
