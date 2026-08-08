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
- Each runtime child Issue supplies a fresh exact current-main SHA, creates one isolated branch from that SHA, and records it before the first test edit with:

```powershell
$env:R2_TASK_BASE_SHA = (git rev-parse HEAD).Trim()
git rev-parse HEAD
```

- Every task starts with meaningful RED before production edits, ends in a normal forward commit, and keeps PASS / FAIL / SKIP / NOT RUN literal.
- No amend, rebase, squash, force-push, or main-sync after a runtime branch is issued.

---

## Pre-issuance Gate: Fresh R1/S3 Rebaseline

This gate is read-only and must complete before Task 1 is issued.

- [ ] **Step 1: Verify final accepted R1 current-main identity**

Record the exact `main` SHA after the complete R1 Source Bundle/Fusion Adapter merges. Confirm no active R1 writer remains on `cad_agent/source_fusion.py` or its tests.

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

Confirm a reusable/ready fusion packet is distinguishable from a blocking unresolved packet without R2 interpreting conflict internals.

- [ ] **Step 3: Verify exact-base identity can be bound without reopening a path**

Prove R2 can derive exactly one base source from validated SourceBundle + accepted custody using:

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

Read-only verify these exact owner seams:

```python
mcp_integration_lib.exact_base_xref.validate_xref_inspection
mcp_integration_lib.exact_base_xref.build_extraction_plan
mcp_integration_lib.exact_base_xref.validate_extraction_plan
mcp_integration_lib.dotnet_ipc.DotNetIPCClient.exact_base_xref_inspection
mcp_integration_lib.dotnet_ipc.DotNetIPCClient.exact_base_xref_extraction
```

Confirm S3B still owns approval equality, canonical path/root/alias policy, source hash/revision checks, fresh live preflight immediately before mutation, failure cleanup, and disposable-candidate-only output.

- [ ] **Step 5: Verify accepted S3B live evidence**

Require all four states:

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

Any need for a third path is a STOP condition for the current runtime Issue, not implicit permission to widen it.

---

## Task 1: Bind Final R1 Fusion to One Eligible Live Exact Base

**Conceptual output:** one closed deterministic `base-cad-binding-1.0` record proving that accepted R1 source/custody/fusion identity and one fresh S3A-compatible S3B live inspection describe the same eligible exact base.

**Files:**

- Create first: `tests/test_cad_agent_base_cad_adapter.py`
- Create only after meaningful RED: `cad_agent/base_cad_adapter.py`
- Modify: none

**Interfaces consumed:**

```text
cad_agent.source_bundle.validate_source_bundle
cad_agent.source_bundle.source_bundle_sha256
cad_agent.source_integrity.validate_source_custody
cad_agent.source_integrity.source_custody_sha256
cad_agent.source_fusion.validate_source_fusion_packet
cad_agent.source_fusion.source_fusion_sha256
cad_agent.source_fusion.require_source_fusion_match
mcp_integration_lib.exact_base_xref.validate_xref_inspection
mcp_integration_lib.exact_base_xref.TRANSFORM_POLICY
cad_agent.drawing_contracts.canonical_json_sha256
```

**Public API produced:**

```text
BASE_CAD_BINDING_SCHEMA_VERSION = "base-cad-binding-1.0"
BaseCadAdapterError(ValueError)
build_base_cad_binding(*, source_bundle, custody, fusion, live_inspection) -> dict[str, object]
validate_base_cad_binding(payload) -> dict[str, object]
base_cad_binding_sha256(payload) -> str
```

The normalized binding has exactly:

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

- [ ] **Step 1: Create the test file with complete synthetic R1/S3 fixtures**

Use current accepted R1 fixture shapes after the pre-issuance rebaseline. The S3 inspection fixture must contain one exact base, vehicle/model PASS, all five required critical dimensions PASS, `changed=false`, equal DBMOD, read-only Xref, and two inspected BLOCK components.

- [ ] **Step 2: Add the Task-1 RED matrix**

Cover all of:

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
absolute/private path fields are absent from binding and sanitized errors
```

- [ ] **Step 3: Add deterministic identity tests**

The test must build the same binding twice, permute inspected component order, and require identical normalized output/hash. Changing source SHA, revision, inspection ID, target drawing SHA, or eligible component membership must change the binding hash.

- [ ] **Step 4: Run focused RED before production creation**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_base_cad_adapter.py -q -p no:cacheprovider
```

Expected: collection/import failure because `cad_agent.base_cad_adapter` is absent. Record exact failure count and reason.

- [ ] **Step 5: Implement only the Task-1 owner**

The builder must execute the accepted owner sequence:

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

Then it must require exactly one `EXACT_BASE_CAD/BASE_CAD` item; find the corresponding custody item by `source_id`; bind SourceBundle declared SHA to custody observed SHA and S3 inspection SHA; bind run IDs; require S3A eligibility; take `revision` only from validated inspection; sort component IDs; never reopen a path; validate the closed record before return; hash only through `canonical_json_sha256()`.

- [ ] **Step 6: Run focused GREEN**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_base_cad_adapter.py -q -p no:cacheprovider
```

Expected: PASS with zero Task-1 skips.

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

Any accepted R1/S3 regression failure blocks the task; upstream tests are not weakened.

- [ ] **Step 8: Run Ruff, architecture, diff and exact write-set gates**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/base_cad_adapter.py tests/test_cad_agent_base_cad_adapter.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
git diff --name-only "$env:R2_TASK_BASE_SHA"..HEAD
```

The path audit must list exactly:

```text
cad_agent/base_cad_adapter.py
tests/test_cad_agent_base_cad_adapter.py
```

- [ ] **Step 9: Run canonical verifier**

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Record literal PASS/FAIL/SKIP/NOT RUN counts. AutoCAD live is not rerun by this hosted/offline task.

- [ ] **Step 10: Commit normally**

```powershell
git add cad_agent/base_cad_adapter.py tests/test_cad_agent_base_cad_adapter.py
git commit -m "feat: bind R1 fusion to eligible exact base"
```

**Paired independent reviewer domains:** source-integrity/provenance/reuse authority + integration/CI/write-set/current-main synthetic.

**STOP:** final R1 seam differs materially; a third path is required; source bytes/path must be reopened; S3A eligibility must be duplicated; multiple base-source arbitration is required; path strings would become authority; dependency/schema/manifest change appears necessary.

---

## Task 2: Build Proposed S3A Extraction and Revalidate External Approval

**Conceptual output:** deterministic proposal construction through S3A plus a fail-closed check that an externally approved S3A plan still matches the exact binding and inspection. R2 issues no approval.

**Files:**

- Modify first for RED: `tests/test_cad_agent_base_cad_adapter.py`
- Modify only after meaningful RED: `cad_agent/base_cad_adapter.py`
- Create: none

**Interfaces consumed:** Task-1 APIs plus `build_extraction_plan()`, `validate_extraction_plan()`, `REUSED_FROM_BASE_CAD`, and `TRANSFORM_POLICY` from `mcp_integration_lib.exact_base_xref`.

**Public API produced:**

```text
build_proposed_base_cad_extraction(*, binding, live_inspection, selections, impacted_views, plan_id) -> dict[str, object]
require_approved_base_cad_extraction_match(*, binding, live_inspection, approved_extraction_plan) -> dict[str, object]
```

- [ ] **Step 1: Add RED proposal tests**

Cover:

```text
valid inspected subset -> S3A plan remains PROPOSED with null approval reference
proposal source/run/inspection/target identity exactly matches binding
component metadata comes from inspection, never caller
uninspected logical_component_id -> fail closed
caller-supplied source_handle/layer/block/candidate_handle -> rejected
translation + rotation + positive uniform scale -> allowed
zero/negative scale -> rejected
non-uniform/global matrix/reflection/global_transform -> rejected
whole-drawing/global scale field -> rejected
selection-order permutation -> deterministic normalized plan
```

- [ ] **Step 2: Add RED external-approval tests**

Construct already-APPROVED S3A fixture data and require:

```text
APPROVED + exact binding/inspection -> accepted normalized plan
PROPOSED passed to approval-match helper -> fail closed
changed approval reference -> fail closed
changed source revision/hash -> fail closed
changed target drawing SHA -> fail closed
changed inspection_id/run_id -> fail closed
component added after approval -> fail closed
transform changed after approval -> fail closed
```

No test calls an approval issuer.

- [ ] **Step 3: Run Task-2 RED against the accepted Task-1 head**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_base_cad_adapter.py -q -p no:cacheprovider
```

Expected: FAIL because the Task-2 APIs are absent. Record exact failures attributable to missing Task-2 behavior.

- [ ] **Step 4: Implement proposal construction strictly through S3A**

`build_proposed_base_cad_extraction()` must validate the binding and current inspection, compare the inspection hash/source identity with the binding, call `build_extraction_plan()` with only logical IDs/local transforms/impacted views, and require the returned plan to remain `PROPOSED` with null approval reference. It must not reconstruct S3A component records or transform rules.

- [ ] **Step 5: Implement approval-match as validation only**

`require_approved_base_cad_extraction_match()` must validate binding + inspection; call `validate_extraction_plan(approved_extraction_plan, inspection=normalized_inspection)`; require plan source/run/inspection/target identity to equal the binding; require existing S3A `approval.status == "APPROVED"` and non-empty reference; return a deep normalized copy. It must never add/replace/synthesize approval fields.

- [ ] **Step 6: Run focused GREEN three times**

```powershell
1..3 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_base_cad_adapter.py -q -p no:cacheprovider
}
```

All three runs must PASS with identical counts.

- [ ] **Step 7: Run S3A/R1 regressions and static gates**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest \
  mcp_integration_lib/tests/test_exact_base_xref.py \
  tests/test_cad_agent_source_fusion.py \
  tests/test_cad_agent_base_cad_adapter.py \
  -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/base_cad_adapter.py tests/test_cad_agent_base_cad_adapter.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
git diff --name-only "$env:R2_TASK_BASE_SHA"..HEAD
```

The path audit must list only the same two R2 paths.

- [ ] **Step 8: Run canonical verifier and commit**

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
git add cad_agent/base_cad_adapter.py tests/test_cad_agent_base_cad_adapter.py
git commit -m "feat: bind proposed base CAD extraction"
```

**Paired independent reviewer domains:** exact-base/S3A transform-and-approval boundary + integration/CI/write-set/current-main synthetic.

**STOP:** an approval issuer is needed; S3A must be changed; global deformation is requested; component membership must be inferred outside inspection; a generic extraction-plan owner appears; any third path is needed.

---

## Task 3: Delegate to S3B and Emit Frozen R2-to-R3 Reuse Handoff

**Conceptual output:** one exact live delegation through the accepted S3B extraction method, a deterministic `base-cad-reuse-handoff-1.0`, and stale/re-extraction evaluation that never overwrites frozen geometry.

**Files:**

- Modify first for RED: `tests/test_cad_agent_base_cad_adapter.py`
- Modify only after meaningful RED: `cad_agent/base_cad_adapter.py`
- Create: none

**Interface consumed:** `mcp_integration_lib.dotnet_ipc.DotNetIPCClient.exact_base_xref_extraction()` plus Task-1/2 APIs and accepted S3B extraction-result semantics.

**Public API produced:**

```text
BASE_CAD_REUSE_HANDOFF_SCHEMA_VERSION = "base-cad-reuse-handoff-1.0"
execute_base_cad_extraction(*, client, binding, live_inspection, approved_extraction_plan, approval, drawing_full_path, drawing_sha256, source_full_path, candidate_output_path) -> dict[str, object]
validate_base_cad_reuse_handoff(payload) -> dict[str, object]
base_cad_reuse_handoff_sha256(payload) -> str
evaluate_frozen_base_cad_reuse(*, handoff, current_live_inspection) -> dict[str, object]
```

The normalized handoff has exactly:

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

No absolute path or timestamp is stored in the handoff.

- [ ] **Step 1: Add a strict S3B client spy**

The test spy exposes only `exact_base_xref_extraction()`; it records call count/arguments and returns synthetic data matching the accepted public S3B extraction-result example. It deliberately has no generic `request()` method.

- [ ] **Step 2: Add RED delegation tests**

Cover:

```text
exact approved binding -> exactly one exact_base_xref_extraction call
PROPOSED plan -> zero S3B calls + fail closed
stale binding/inspection -> zero S3B calls + fail closed
missing/mismatched approval -> zero successful extraction + fail closed
adapter has no generic request()/alternate operation path
source/drawing/candidate path values are passed only to S3B and never persisted in handoff
```

- [ ] **Step 3: Add RED returned-invariant tests**

Refuse a handoff when synthetic S3B result claims any of:

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
provenance != REUSED_FROM_BASE_CAD
```

These are cross-boundary checks over accepted S3B facts, not a second path-policy or AutoCAD implementation.

- [ ] **Step 4: Add RED frozen provenance/determinism tests**

Every handoff component must freeze exact source SHA/revision/handle/layer/block, local transform, candidate handle, and `REUSED_FROM_BASE_CAD`. Permuting S3B component/mapping order must normalize to the same handoff/hash. Changing any frozen source/candidate/provenance fact must change the handoff hash.

- [ ] **Step 5: Add RED stale/re-extraction tests**

`evaluate_frozen_base_cad_reuse()` must return only:

```text
CURRENT
STALE_REEXTRACTION_REQUIRED
```

Use a fresh S3A-valid inspection as current identity. Same `source_id + sha256 + revision` => `CURRENT` with no affected components. Any source ID/hash/revision change => `STALE_REEXTRACTION_REQUIRED` with sorted affected logical component IDs, prior/current source identity and deterministic reason codes. The stale result contains no approval, candidate-handle rewrite, current pointer, or mutation instruction.

- [ ] **Step 6: Run Task-3 RED against the accepted Task-2 head**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_base_cad_adapter.py -q -p no:cacheprovider
```

Expected: FAIL only because Task-3 APIs/behavior are missing.

- [ ] **Step 7: Implement exact S3B delegation**

`execute_base_cad_extraction()` must validate binding; validate the current S3A inspection and compare its canonical identity to the binding; call `require_approved_base_cad_extraction_match()`; call exactly `client.exact_base_xref_extraction(...)` with the already approved plan and approval object; never construct a raw generic IPC operation; normalize/check the returned extraction result; emit the closed handoff only after all invariants pass.

Production runtime issuance must use the accepted `DotNetIPCClient` seam. The test spy exists only for synthetic tests and does not become a transport abstraction owner.

- [ ] **Step 8: Implement frozen handoff validation/hash**

Use closed exact fields, deep normalized copies, sorted component/mapping lists, strict lowercase SHA-256 values, and existing `canonical_json_sha256()` only. Exclude absolute paths, timestamps, raw S3B exception text, component-current/revision state, view ownership, verdict, approval, repair and publication fields.

- [ ] **Step 9: Implement stale evaluation without mutation authority**

Validate prior handoff + fresh current inspection, compare only `source_id`, `sha256`, `revision`, and return deterministic state/reason/affected IDs. The evaluator never calls extraction; re-extraction requires a new proposal/approval/execution cycle.

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

Hosted/offline tests must PASS. Gated AutoCAD Mechanical tests remain literal `SKIP`/`NOT RUN` where not executed.

- [ ] **Step 11: Run Ruff, architecture, diff, canonical and exact path gates**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/base_cad_adapter.py tests/test_cad_agent_base_cad_adapter.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
git diff --name-only "$env:R2_TASK_BASE_SHA"..HEAD
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

The path audit must list only the two R2 paths.

- [ ] **Step 12: Prove no second authority owner**

Focused architecture assertions must prove R2 does not define/import ownership for CAD parsing, DXF building, component/view registry, revision/current store, repair execution, visual verdict, approval issuance, publication, a new IPC request/operation builder, source-byte opening, OCR, model or provider execution. Direct reuse imports from accepted R1/S3 and the canonical hash owner are allowed.

- [ ] **Step 13: Commit normally**

```powershell
git add cad_agent/base_cad_adapter.py tests/test_cad_agent_base_cad_adapter.py
git commit -m "feat: freeze exact-base reuse provenance"
```

**Paired independent reviewer domains:** AutoCAD/S3B candidate-mutation + provenance boundary, and integration/CI/write-set/current-main synthetic. Luna/local operator remains the live-evidence owner, not the repository writer.

**STOP:** any S3B production edit is required; a new transport/dispatcher/path policy is needed; accepted/current drawing mutation is required; live preflight would be duplicated/bypassed; R2 must persist component/current revision state; private CAD is needed; source/accepted immutability cannot be proven; result normalization requires schema change.

---

## Whole-R2 Verification and Handoff Gate

After Task 3, the union of the three independently audited child-issue diffs must contain only:

```text
cad_agent/base_cad_adapter.py
tests/test_cad_agent_base_cad_adapter.py
```

Before R2 is declared complete:

- [ ] focused R2 synthetic tests — PASS, zero R2 skips;
- [ ] R1 SourceBundle/custody/final-fusion regressions — PASS;
- [ ] S3A inspection/extraction-plan regressions — PASS;
- [ ] S3B Python transport regressions — PASS;
- [ ] Ruff on exactly the two R2 paths — PASS;
- [ ] architecture ratchet — PASS;
- [ ] `git diff --check` — PASS;
- [ ] canonical verifier — exact counts recorded;
- [ ] hosted `tests` — PASS on exact child head/current-main synthetic;
- [ ] hosted `reuse-declaration` — PASS;
- [ ] all additional required hosted checks — PASS;
- [ ] unresolved review threads — 0 before Master PO acceptance;
- [ ] independent provenance/authority review — PASS;
- [ ] independent integration/CI review — PASS.

No unavailable live gate may be relabeled PASS.

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
| Active/future R1 Source Fusion | `cad_agent/source_fusion.py`, `tests/test_cad_agent_source_fusion.py`, possible final manifest-reference work | `NONE` | R2 waits for complete R1 merge and imports the accepted seam read-only. |
| S3A exact-base contract | `mcp_integration_lib/exact_base_xref.py`, its tests | `READ-ONLY REUSE` | No modification; plan/inspection semantics stay S3A-owned. |
| S3B transport/.NET | `mcp_integration_lib/dotnet_ipc.py`, `autocad_plugin/**`, IPC contracts | `READ-ONLY REUSE` | R2 delegates through accepted methods; any production change requires rebaseline. |
| Luna / Issue #72 local lane | local AutoCAD session and live evidence harness | `NO REPOSITORY OVERLAP` | Live AutoCAD remains serialized under one local operator; R2 writer does not control the same session. |
| Existing manifest/checkpoint owner | `cad_agent/manifest.py`, `cad_agent/pdf.py`, CLI run/resume | `NONE` | No second store/reference field is added in first R2 sequence. |
| DXF/native geometry owner | `dxf_builder_lib/**` | `NONE` | R2 does not generate changed/new geometry. |
| Future R3 registry | future component/view-registry owner/tests | `NONE` | R2 emits transfer evidence only; no component/current/revision persistence. |
| Future R4 revision orchestrator | future candidate-revision owner | `NONE` | R2 does not mark current/accepted revision or own rollback history. |

## R3 Handoff Contract

R3 may rely only on validated `base-cad-reuse-handoff-1.0` fields and its canonical SHA-256. R3 must not rely on R2 process memory, absolute S3B paths, a current-component state inside R2, implicit candidate ordering, ambient AutoCAD session state, or old inspection IDs as mutation authority.

A future R3 task may register candidate handles/provenance under its separately accepted store/contract. R2 remains stateless.

## Migration and Rollback

**Migration:** none. No existing schema, manifest, CAD file, registry, revision store, IPC contract, or producer artifact changes in the planned first R2 sequence.

**Rollback:** revert the R2 commits/remove the two R2 files. R1, S3A, S3B, manifests, DXF builder and future R3/R4 owners remain unchanged. Disposable candidates from separately authorized live operations are cleaned by existing S3B/local-operator rules; source/accepted CAD require no rollback because they must never change.

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

Each child Issue receives a fresh exact current-main SHA and only its exact two-path CREATE/MODIFY allowlist. If any child needs a third path or wider authority, stop and return to Master PO instead of widening the issue.

## Final STOP Conditions

Stop and report `R2 REBASELINE REQUIRED` rather than widening scope if:

- final accepted R1 API/source identity is insufficient for the binding;
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
