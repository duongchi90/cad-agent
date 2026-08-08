# R5 Visual Supervisor Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Planning only. Issue #135 authorizes no R5 runtime implementation.

**Planning date:** 2026-08-09

**Planning base:** `b217ebfd597260d7b59badc3ffbcfbe7b1139754`

**Goal:** Add the missing independent visual-verdict adapter by composing accepted VS-T1/T2/T3 evidence, accepted R3/R4 identities, and the accepted Wave 1A worker/provider boundary without creating a second evidence, comparator, provider, repair, revision, approval, or publication authority.

**Architecture:** Extend the existing `cad_agent.visual_contracts` owner with two closed R5 contracts: an untrusted provider-region observation and a server-final deterministic verdict. Keep provider transport in the accepted Wave 1A worker owner, keep evidence freshness in `cad_agent.visual_evidence`, and implement only thin request/freshness/aggregation orchestration in a future adjacent R5 adapter. Region results aggregate deterministically to view, sheet, then overall verdict; provider output never supplies parent membership or final aggregation authority.

**Tech Stack:** Python 3.11, existing `cad_agent.visual_contracts`, existing `cad_agent.visual_evidence`, existing `cad_agent.vision_handoff`, accepted Wave 1A official worker/provider seam after rebaseline, VS-T1 Dimension Observer, VS-T2 Geometry Comparator, VS-T3 File IPC evidence exporter, existing `cad_agent.drawing_contracts.canonical_json_sha256`, pytest, Ruff, current architecture/reuse ratchets, `scripts/verify.ps1 -SkipAutoCADDotNet`, GitHub hosted `tests` and `reuse-declaration`. No new dependency.

## Global Constraints

- Authoritative R5 design: `docs/superpowers/specs/2026-08-09-r5-visual-supervisor-adapter-design.md`.
- Parent reuse-first design: `docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`.
- Reuse inventory: `docs/superpowers/reuse/2026-08-04-reuse-inventory.json`.
- `independent-visual-verdict` is the only genuinely missing capability R5 fills.
- Preserve VS-T1 as the sole dimension-observation owner.
- Preserve VS-T2 as the sole deterministic geometry-comparison owner.
- Preserve VS-T3 plus `cad_agent.visual_evidence` as the sole AutoCAD-native evidence export/freshness boundary.
- Preserve `cad_agent.visual_contracts` as the sole Visual Supervisor contract-validation owner.
- Preserve `cad_agent.vision_handoff` plus the accepted Wave 1A worker/process boundary as the sole model/provider execution boundary.
- Preserve `cad_agent.drawing_contracts.canonical_json_sha256()` as the canonical JSON hash owner for new R5 deterministic identities.
- Preserve final accepted R3 as the component/view/region/sheet identity owner.
- Preserve final accepted R4 as the candidate revision/current mutation/lineage owner.
- Preserve existing manifest/checkpoint/resume ownership; R5 core creates no store.
- R5 cannot emit repair operations or repair intent; R6 owns later repair planning/execution routing.
- R5 cannot create/select/promote/rollback candidate revisions; R4 owns revision lineage.
- R5 cannot issue engineering approval.
- R5 cannot decide publication eligibility or publish; R7 owns that boundary.
- R5 cannot mutate CAD or call a new AutoCAD/File IPC operation.
- R5 cannot create a second SDK/App Server/CLI/MCP/HTTP/provider transport.
- Provider output is untrusted until closed validation and post-provider freshness checks pass.
- `PASS`, `FAIL`, and `NEEDS_HUMAN` are visual evidence states only.
- Whole-sheet or average similarity can never override a failed child region.
- Initial runtime RED/GREEN uses synthetic fixtures and fake/provider-independent worker results only.
- Private/customer CAD, real provider/model/auth, and live AutoCAD are `NOT RUN` unless a later issue explicitly authorizes them.
- Every runtime task is mandatory RED-first, forward-only, and bounded to at most two repository paths unless Master PO explicitly amends the write-set.
- Missing prerequisites are `SKIP` or `NOT RUN`, never `PASS`.
- Moving R3 #134, R4 #133, and Wave 1A #113 symbols are not assumed by this plan.

---

## 0. Mandatory post-R4/Wave-1A rebaseline — no repository write

This gate is mandatory before any R5 runtime task. It is performed by Master PO/runtime issuance against fresh accepted `main`.

The future runtime Issue must record exact accepted paths, symbols, field names, and tests for all of the following:

1. R1 source/fusion identities required by the review evidence;
2. R2 exact-base provenance identity when reused geometry is in scope;
3. R3 component/view/region/sheet membership, region criticality, and registry identity;
4. R4 candidate revision identity, candidate artifact SHA, latest mutation identity, lineage, and stale/current semantics;
5. Wave 1A official worker start/turn/close/cancel/cleanup public boundary actually accepted at that time;
6. provider-observed effective instruction-source, provider-policy, model/config, sandbox/cwd, transport, and output-schema attestation actually accepted after #113;
7. `vision_handoff` authority and immutable output-schema binding actually accepted at that time;
8. VS-T3 live evidence prerequisite state required for the intended R5 acceptance level;
9. current `visual_contracts` and `visual_evidence` owner paths/tests;
10. current active writers on every proposed R5 path;
11. exact current-main SHA used for the first R5 runtime branch;
12. exact runtime sole writer for each issued task.

The runtime Issue must also state the exact semantic mapping from those accepted records to these R5 facts:

```text
candidate_identity
candidate_sha256
latest_mutation_identity
registry_identity
region_id -> view_id -> sheet_id
region_criticality
source/reference evidence identities
confirmed/protected dimension/constraint identities
VS-T2 comparison identity + mutation binding
VS-T3 evidence identity + mutation/freshness binding
accepted worker/provider attestation identity
```

The planning document deliberately does not guess moving R3/R4/#113 function names or field names.

**STOP with `R5 REBASELINE REQUIRED` before any repository write if:**

- one mapping cannot be resolved exactly;
- accepted upstream ownership requires a third authority/store/transport;
- an active writer overlaps the issued task paths;
- provider-observed attestation cannot prove the effective provider boundary;
- the accepted worker seam requires R5 to add a parallel provider protocol;
- R5 would need CAD/source parsing or a new AutoCAD operation.

No repository mutation occurs during Gate 0.

---

## 1. Preferred runtime file ownership after Gate 0

### Existing contract authority

```text
cad_agent/visual_contracts.py
contracts/visual-supervisor/
tests/test_visual_supervisor_contracts.py
tests/test_visual_supervisor_schema_alignment.py
```

R5 extends this existing owner; it does not create a new contract package.

### New thin orchestration ownership

Preferred if Gate 0 confirms no safer accepted adjacent seam:

```text
cad_agent/visual_supervisor_adapter.py
tests/test_cad_agent_visual_supervisor_adapter.py
```

No R5 core runtime task modifies:

```text
primitive_ir_lib/dimension_observer.py
primitive_ir_lib/geometry_comparator.py
cad_agent/geometry_comparison_run.py
cad_agent/visual_evidence.py
mcp_integration_lib/*
autocad_plugin/*
agent_lib/codex_worker.py
agent_lib/codex_worker_process.py
cad_agent/vision_handoff.py
cad_agent/manifest.py
dxf_builder_lib/repair.py
```

If accepted upstream integration proves one of those owners must change, stop and issue an upstream/owner-specific task. Do not widen an R5 core task.

---

## 2. Proposed R5 public API

Subject only to naming conflicts discovered by Gate 0, R5 owns these orchestration functions:

```python
class VisualSupervisorAdapterError(ValueError):
    """Categorical R5 orchestration failure with no raw private/provider detail."""


def build_visual_supervisor_request(
    *,
    upstream_context: object,
    region_ids: object,
) -> dict[str, object]:
    """Build a closed deterministic request from already-validated upstream facts."""


def validate_visual_supervisor_observation(
    observation: object,
    *,
    request: object,
    upstream_context: object,
) -> dict[str, object]:
    """Validate one untrusted provider region observation against server-owned scope."""


def finalize_visual_supervisor_verdict(
    *,
    request: object,
    observation: object,
    upstream_context: object,
) -> dict[str, object]:
    """Recheck freshness and aggregate region -> view -> sheet -> overall verdict."""


def visual_supervisor_verdict_sha256(verdict: object) -> str:
    """Hash a validated final R5 verdict through the existing canonical hash owner."""
```

`upstream_context` is an R5 orchestration parameter name, not an invented R3/R4 contract. Gate 0 must bind it to exact accepted validators and identities before Task 5 begins.

R5 does **not** expose a new public provider-transport API. Provider execution remains through the accepted Wave 1A worker public API recorded by Gate 0.

---

### Task 1: Add the provider-observation JSON Schema in the existing Visual Supervisor contract family

**Sole writer:** the R5 runtime writer named by the Master PO issuance. If the issuance does not name exactly one writer, STOP.

**Files:**
- Create: `contracts/visual-supervisor/visual-supervisor-observation.schema.json`
- Modify: `tests/test_visual_supervisor_schema_alignment.py`
- Third path: forbidden

**Produces:** a closed Draft 2020-12 schema for `visual-supervisor-observation-1.0` containing only untrusted per-region provider observations.

**Contract shape:**

```json
{
  "schema_version": "visual-supervisor-observation-1.0",
  "request_id": "R5-REQUEST-001",
  "regions": [
    {
      "region_id": "REGION-001",
      "verdict": "PASS",
      "severity": "INFO",
      "confidence": 0.99,
      "findings": [],
      "requested_next_evidence": []
    }
  ]
}
```

Each finding is closed and contains exactly:

```text
finding_id
category
feature
severity
description
evidence_refs
```

The schema allows no parent view/sheet/overall verdict and no repair, approval, mutation, revision, provider-policy, or publication fields.

**RED-first attack matrix:**

1. required observation schema path is absent;
2. valid synthetic observation must validate through the schema-alignment helper;
3. unknown root or region field fails;
4. unknown verdict fails;
5. NaN/Infinity confidence fails;
6. confidence outside `[0,1]` fails;
7. duplicate/empty evidence references fail according to the closed contract rule;
8. `repair_intent`, `operations`, `approval`, `publish`, `revision`, `overall_verdict`, `sheet_verdict`, and `view_verdict` are rejected;
9. schema object boundaries all set `additionalProperties: false`;
10. synthetic example data contains no private path/customer/CAD information.

- [ ] **Step 1: Write RED only**

Modify only `tests/test_visual_supervisor_schema_alignment.py` so it loads the exact new schema path and checks the attack matrix above. Do not create the schema yet.

- [ ] **Step 2: Prove meaningful RED**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
```

Expected: FAIL because the R5 observation schema does not exist. A fixture/import/environment failure does not count.

Commit the RED-only test change before creating the schema.

- [ ] **Step 3: Create the minimal closed schema**

Create only `contracts/visual-supervisor/visual-supervisor-observation.schema.json`. Reuse the current identifier/hash/finiteness vocabulary from the existing Visual Supervisor schema family. Do not add a runtime schema dependency.

- [ ] **Step 4: Prove focused GREEN**

Run the focused schema-alignment test and then:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check tests/test_visual_supervisor_schema_alignment.py

git diff --check

git diff --cached --check
```

- [ ] **Step 5: Verify exact task diff and commit**

The Task-1 branch delta since its issuance SHA must contain exactly the two Task-1 paths. Commit normally; no amend/rebase/squash/force-push.

**Independent reviewer:** contract/authority reviewer. Attack for hidden repair/publish/parent-aggregation fields and open JSON objects.

**STOP conditions:** third path, runtime schema dependency, a provider transport change, or any repair/revision/approval/publication field.

---

### Task 2: Extend the existing Python visual-contract owner for provider observations

**Sole writer:** same single R5 runtime writer named in issuance unless Master PO explicitly reassigns between tasks.

**Files:**
- Modify: `cad_agent/visual_contracts.py`
- Modify: `tests/test_visual_supervisor_contracts.py`
- Third path: forbidden

**Consumes:** the Task-1 schema semantics and existing Visual Supervisor validation vocabulary.

**Produces:** `validate_visual_contract(payload, contract="visual_supervisor_observation")` support under the existing authority.

**RED-first attack matrix:**

1. new contract name is rejected before implementation;
2. valid synthetic closed observation is accepted and deep-copied;
3. provider cannot include parent aggregation results;
4. provider cannot include `repair_intent` or repair operations;
5. provider cannot include approval/revision/publication fields;
6. `PASS` requires `severity=INFO` and no MAJOR/CRITICAL finding;
7. `FAIL` requires at least one MAJOR/CRITICAL finding but **does not require repair intent**;
8. `NEEDS_HUMAN` requires a finding or requested next evidence;
9. finding/evidence arrays are bounded by the accepted contract limits added in this task;
10. unknown/duplicate IDs fail closed;
11. non-finite numbers fail closed;
12. validator output cannot be mutated through caller aliasing;
13. historical `visual_review-1.0` behavior remains unchanged, including its historical repair-intent requirements;
14. no import of worker/provider/AutoCAD/repair/revision code into `visual_contracts.py`.

- [ ] **Step 1: Write Task-2 RED only**

Modify only `tests/test_visual_supervisor_contracts.py`. Add positive, negative, compatibility, and deep-copy tests. The RED must fail because the existing contract registry has no R5 observation contract.

- [ ] **Step 2: Prove meaningful RED and commit it**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_visual_supervisor_contracts.py -q -p no:cacheprovider
```

Expected: focused new cases FAIL for unsupported contract/behavior; historical cases remain GREEN.

- [ ] **Step 3: Implement only in the existing contract owner**

Modify only `cad_agent/visual_contracts.py`:

```python
# conceptual registry outcome; preserve the repository's accepted dispatch style
# "visual_supervisor_observation" -> _validate_visual_supervisor_observation
```

The validator performs shape/enum/finiteness/authority checks only. It does not open files, call models, aggregate views/sheets, or run repair logic.

- [ ] **Step 4: Prove focused + legacy GREEN**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/visual_contracts.py tests/test_visual_supervisor_contracts.py
```

- [ ] **Step 5: Run architecture/reuse gates and commit**

```powershell
.\.venv-py311\Scripts\python.exe scripts/reuse_inventory.py check docs/superpowers/reuse/2026-08-04-reuse-inventory.json --repo-root .
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
```

**Independent reviewer:** compatibility + authority reviewer. Verify historical `visual_review` is not weakened and new observation has no repair/publish authority.

**STOP conditions:** need for a new Python validator module, historical contract semantic rewrite, third path, or repair/provider import.

---

### Task 3: Add the server-final R5 verdict JSON Schema

**Sole writer:** one R5 runtime writer.

**Files:**
- Create: `contracts/visual-supervisor/visual-supervisor-verdict.schema.json`
- Modify: `tests/test_visual_supervisor_schema_alignment.py`
- Third path: forbidden

**Produces:** a closed `visual-supervisor-verdict-1.0` schema for the deterministic final R5 evidence record.

**Required semantic fields:**

```text
schema_version
verdict_id
request_id
run_id
candidate_revision_identity
candidate_sha256
latest_mutation_identity
registry_identity
request_sha256
provider_observation_sha256
provider_attestation_identity
regions
views
sheets
overall_verdict
finding_summary
```

Each region record contains server-owned membership/criticality plus validated provider result references. View/sheet records contain deterministic child IDs and verdict only. The final contract has no repair, mutation, approval, revision transition, or publication command.

**RED-first attack matrix:**

1. schema absent before implementation;
2. closed valid synthetic verdict passes schema alignment;
3. unknown fields fail at every level;
4. malformed SHA/IDs fail;
5. duplicate child IDs fail via Python semantic validation in Task 4; schema enforces closed arrays/types;
6. `repair_intent`, `operations`, `approval`, `promote`, `rollback`, `publish`, `current_revision`, and `accepted_revision` fields are rejected;
7. only PASS/FAIL/NEEDS_HUMAN verdict enum allowed;
8. finding summary cannot contain free-form action authorization;
9. every array/object is bounded and closed according to the existing contract-family conventions.

- [ ] **Step 1: Add schema-alignment RED only**

Modify only the existing schema-alignment test and prove failure due to missing verdict schema.

- [ ] **Step 2: Commit RED, then create schema**

Create only the new verdict schema after meaningful RED.

- [ ] **Step 3: Focused GREEN + Ruff + diff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check tests/test_visual_supervisor_schema_alignment.py
git diff --check
```

**Independent reviewer:** schema + authority-separation reviewer.

**STOP conditions:** third path, repair/revision/publish authority, or new runtime dependency.

---

### Task 4: Extend the existing Python visual-contract owner for final R5 verdicts

**Sole writer:** one R5 runtime writer.

**Files:**
- Modify: `cad_agent/visual_contracts.py`
- Modify: `tests/test_visual_supervisor_contracts.py`
- Third path: forbidden

**Produces:** `validate_visual_contract(payload, contract="visual_supervisor_verdict")` support.

**Semantic validation requirements:**

1. all region/view/sheet IDs unique;
2. every region references exactly one known view and sheet relationship encoded in the final record;
3. view child region IDs are complete and duplicate-free;
4. sheet child view IDs are complete and duplicate-free;
5. parent verdict matches deterministic precedence `FAIL > NEEDS_HUMAN > PASS`;
6. overall verdict matches deterministic sheet aggregation;
7. one child FAIL cannot coexist with parent PASS/NEEDS_HUMAN;
8. one child NEEDS_HUMAN cannot coexist with parent PASS;
9. final record contains no repair/approval/revision-transition/publication field;
10. all hashes and identities use closed accepted formats;
11. caller mutation after validation cannot alter the validated copy;
12. historical contracts remain unchanged.

- [ ] **Step 1: Write RED-only semantic tests**

Modify only `tests/test_visual_supervisor_contracts.py`. Include adversarial parent/child aggregation mismatches and critical-region examples.

- [ ] **Step 2: Prove meaningful RED and commit it**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_visual_supervisor_contracts.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement minimal final-verdict validation**

Modify only `cad_agent/visual_contracts.py`. Reuse existing helpers and do not add file/provider/CAD/store I/O.

- [ ] **Step 4: Focused + policy GREEN**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/visual_contracts.py tests/test_visual_supervisor_contracts.py
```

- [ ] **Step 5: Architecture/reuse/diff and commit**

Run both governance CLIs and `git diff --check` as in Task 2.

**Independent reviewer:** deterministic aggregation reviewer. Specifically attempt to hide one failed critical region behind passing sibling regions and whole-sheet results.

**STOP conditions:** second aggregation authority outside the existing contract owner/adapter pair, third path, or any action authorization field.

---

### Task 5: Build the pure R5 request/freshness/aggregation adapter core

**Sole writer:** one R5 runtime writer named by the post-rebaseline issuance.

**Files:**
- Create: `cad_agent/visual_supervisor_adapter.py`
- Create: `tests/test_cad_agent_visual_supervisor_adapter.py`
- Third path: forbidden

**Consumes:**
- exact accepted upstream validators/symbols recorded by Gate 0;
- `cad_agent.visual_contracts.validate_visual_contract` for both R5 contract types;
- `cad_agent.drawing_contracts.canonical_json_sha256`;
- accepted VS-T1/T2/T3 freshness and evidence identities;
- accepted R3/R4 facts through Gate-0 mapping.

**Produces:** the four R5 public orchestration functions in Section 2.

**Critical implementation rule:** the adapter may inspect only already-validated mappings/records from accepted owners. It must not open CAD/source image files, run OCR/comparison, call AutoCAD, or implement provider transport.

**RED-first matrix — request identity and scope:**

1. module/public surface absent initially;
2. identical canonical accepted upstream facts produce identical request mapping/hash regardless of input dictionary/list ordering where ordering is semantically irrelevant;
3. candidate SHA or latest mutation change changes request identity;
4. registry identity change changes request identity;
5. foreign/unknown/dangling region fails closed;
6. caller cannot set region criticality/membership different from accepted R3 facts;
7. missing required VS-T2 comparison fails input readiness;
8. stale/foreign VS-T3 evidence fails before provider stage;
9. critical unresolved/conflicting protected dimension blocks relevant region;
10. unrequested source/evidence artifact cannot enter provider-visible request;
11. absolute private path/private exception text is not copied to categorical failure output;
12. request contains no mutation/repair/approval/publish operation.

**RED-first matrix — untrusted observation:**

13. extra/missing/duplicate provider region fails;
14. provider evidence ref outside request allowlist fails;
15. provider cannot override request/candidate/registry/mutation identity;
16. provider cannot supply view/sheet/overall verdict authority;
17. malformed contract output fails categorical `R5_PROVIDER_OUTPUT_INVALID` semantic equivalent;
18. provider PASS cannot override a blocking deterministic comparator/evidence condition;
19. provider FAIL needs valid closed finding evidence but no repair intent.

**RED-first matrix — finalization/freshness:**

20. candidate mutation after request but before finalization fails stale and emits no final verdict;
21. VS-T3 evidence identity/freshness drift fails stale;
22. R3/R4 identity drift fails stale;
23. one region FAIL -> parent view FAIL -> sheet FAIL -> overall FAIL;
24. no FAIL but one NEEDS_HUMAN -> parent NEEDS_HUMAN;
25. parent PASS only when every required child is PASS;
26. critical region FAIL cannot be hidden by normal-region PASS or average similarity;
27. final verdict hash changes when any freshness/evidence/child verdict material changes;
28. final verdict contains no repair, approval, revision transition, or publication field;
29. errors are categorical and sanitized;
30. static import scan rejects OCR/comparator implementation modules, AutoCAD/File IPC, DXF/repair, provider SDK/App Server/CLI/MCP, database/store, and publisher ownership.

- [ ] **Step 1: Create only the R5 test file and prove RED**

First write for Task 5 is only:

```text
tests/test_cad_agent_visual_supervisor_adapter.py
```

Use deterministic synthetic upstream records that match the exact Gate-0 accepted semantic mapping. Do not create an R3/R4 fake API module or compatibility shim.

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_visual_supervisor_adapter.py -q -p no:cacheprovider
```

Expected: meaningful FAIL because the R5 adapter/public behavior is absent.

Commit RED-only before production creation.

- [ ] **Step 2: Implement minimal pure adapter core**

Create only `cad_agent/visual_supervisor_adapter.py`.

Required coding rules:

```python
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.visual_contracts import validate_visual_contract
```

Use exact accepted upstream validation imports recorded by Gate 0. Do not add alternate canonical hashing or duplicate upstream validation.

Aggregation is a pure function with precedence:

```python
FAIL > NEEDS_HUMAN > PASS
```

Sort normalized identity collections deterministically before canonical hashing where their semantics are sets. Preserve order only where the accepted upstream contract says order is meaningful.

- [ ] **Step 3: Repeat focused determinism GREEN**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_visual_supervisor_adapter.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

- [ ] **Step 4: Run R5 contract and upstream regressions**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_visual_supervisor_adapter.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_schema_alignment.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_evidence.py tests/test_geometry_comparison_run.py tests/test_geometry_comparator_policy.py tests/test_dimension_observer_run.py -q -p no:cacheprovider
```

Also run the exact final R3/R4 focused tests recorded by Gate 0. Those paths must be copied exactly into the runtime Issue before execution; if they are absent, STOP rather than guessing them.

- [ ] **Step 5: Ruff + governance + diff**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/visual_supervisor_adapter.py tests/test_cad_agent_visual_supervisor_adapter.py
.\.venv-py311\Scripts\python.exe scripts/reuse_inventory.py check docs/superpowers/reuse/2026-08-04-reuse-inventory.json --repo-root .
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
git diff --cached --check
```

- [ ] **Step 6: Commit and paired review**

Cumulative Task-5 branch delta must be exactly the two R5 core paths. Stop write for independent review before any worker composition task.

**Independent reviewers:**
- evidence freshness/security reviewer;
- visual-verdict/authority reviewer.

**STOP conditions:** provider transport needed, third path, upstream API invention, direct file/CAD/image/comparator I/O, store, repair/revision/publish behavior.

---

### Task 6: Compose R5 with the accepted official worker/provider seam

**Dependency:** Task 5 accepted plus Gate 0 containing the exact accepted Wave 1A worker and provider-attestation symbols after #113 is no longer moving.

**Sole writer:** one R5 runtime writer.

**Files:**
- Modify: `cad_agent/visual_supervisor_adapter.py`
- Modify: `tests/test_cad_agent_visual_supervisor_adapter.py`
- Third path: forbidden

**No new transport type is introduced.** The implementation imports and calls only the exact accepted worker lifecycle/provider-attestation API recorded by Gate 0. If that API cannot carry the immutable R5 output schema and bounded evidence payload, STOP with `R5 REBASELINE REQUIRED`; do not introduce a local worker protocol.

**Required flow:**

```text
build_visual_supervisor_request
-> server-owned vision handoff / output schema binding
-> accepted worker open/start boundary
-> accepted provider-observed effective instruction/policy/schema attestation
-> accepted worker turn with bounded request payload
-> receive candidate_trusted == false provider output
-> accepted worker close/cleanup
-> validate_visual_supervisor_observation
-> recheck upstream candidate/evidence freshness
-> finalize_visual_supervisor_verdict
```

Provider output must never bypass `validate_visual_supervisor_observation()` merely because the worker lifecycle returned success.

**RED-first matrix:**

1. fake accepted worker success yields untrusted candidate only until R5 validation;
2. provider observation with perfect-looking PASS but missing/foreign region fails;
3. worker authority mismatch fails before provider work;
4. missing provider-observed attestation fails closed;
5. instruction-source mismatch fails closed;
6. model/config mismatch fails closed;
7. sandbox/cwd/writable-root mismatch fails closed;
8. alternate transport/full-access/approval escalation/auto-review evidence fails according to the accepted Wave 1A policy;
9. malformed schema binding fails closed;
10. timeout emits no final verdict;
11. cancel/interrupt emits no final verdict;
12. provider failure emits no final verdict;
13. missing terminal output emits no final verdict;
14. cleanup survivors or cleanup failure emit no final verdict;
15. late output after timeout/cancel is rejected;
16. candidate/latest-mutation change during provider execution invalidates otherwise valid output;
17. custom fake boundary that is not the accepted worker authority cannot mint trusted provider provenance;
18. raw provider/private error detail is not exposed;
19. no App Server/CLI/MCP/HTTP fallback;
20. no real model/auth call is needed for focused GREEN.

- [ ] **Step 1: Add fake worker/provider RED cases only**

Modify only the existing R5 test file. Use the repository's accepted worker test harness/fakes from Gate 0 by import/reuse where their ownership allows it; do not copy lifecycle logic into R5 tests.

- [ ] **Step 2: Prove meaningful RED**

Run the R5 focused test. RED must be missing R5 composition behavior, not unavailable real credentials/model.

- [ ] **Step 3: Implement minimal composition with accepted worker imports**

Modify only `cad_agent/visual_supervisor_adapter.py`. Use exact Gate-0 worker/provider symbols. R5 may prepare the visual-review payload and consume the untrusted candidate; lifecycle/process/attestation/cleanup stay in their existing owner.

- [ ] **Step 4: Focused fake GREEN and accepted Wave 1A regressions**

Run R5 focused tests plus every exact worker/handoff/provider-attestation regression file listed by Gate 0. No real provider call.

- [ ] **Step 5: Canonical verification**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -SkipAutoCADDotNet
```

Truthful required states for this task:

```text
fake/provider-independent R5: PASS only if executed GREEN
real provider/model/auth: NOT RUN
AutoCAD .NET: NOT RUN under -SkipAutoCADDotNet
AutoCAD Mechanical live: NOT RUN
private/customer CAD: NOT RUN
```

- [ ] **Step 6: Hosted current-main synthetic**

Open a DRAFT runtime PR only after local/supported verification. Record exact branch head and current `main`. Hosted `tests` and `reuse-declaration` must run on the exact PR synthetic. A moving main is not silently merged/rebased into the writer branch.

**Independent reviewers:**
- worker/provider security reviewer;
- evidence freshness/authority reviewer.

**STOP conditions:** worker owner modification, second provider protocol, real credentials required for unit acceptance, third path, or missing accepted attestation semantics.

---

### Task 7: Final R5 fake/runtime integration gate and STOP WRITE

This is a verification/review gate, not a new implementation owner. It creates no third runtime path.

**Repository writes:** none unless a reviewer identifies a defect that Master PO reissues with an exact bounded write-set.

- [ ] **Step 1: Re-run exact R5 focused suites**

Run observation/verdict schema tests, visual-contract tests, adapter tests, VS-T1/T2/T3 regressions, final R3/R4 regressions from Gate 0, and final accepted Wave 1A worker/handoff/provider tests.

- [ ] **Step 2: Run full canonical offline verifier**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -SkipAutoCADDotNet
```

- [ ] **Step 3: Re-run governance checks**

```powershell
.\.venv-py311\Scripts\python.exe scripts/reuse_inventory.py check docs/superpowers/reuse/2026-08-04-reuse-inventory.json --repo-root .
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
git diff --cached --check
```

- [ ] **Step 4: Verify authority bans by diff/import review**

Confirm cumulative R5 runtime code contains no new:

```text
OCR/dimension recognition
geometry comparator/image alignment implementation
AutoCAD/File IPC operation
SDK/App Server/CLI/MCP/HTTP transport
CAD parser/DXF writer
manifest/checkpoint/revision store
approval issuer
repair planner/executor
publisher/promotion owner
```

- [ ] **Step 5: Verify current-main synthetic policy**

Record exact runtime head, exact fresh current-main SHA, exact hosted synthetic merge SHA, hosted `tests` state, and hosted `reuse-declaration` state. Never call a missing/queued/skipped gate PASS.

- [ ] **Step 6: STOP WRITE for independent review**

Do not start R6 or R7. R5 runtime acceptance belongs to Master PO after independent review.

---

## 3. Contract semantics locked across all R5 tasks

### 3.1 Provider observation is region-only

The provider may classify each requested region as exactly:

```text
PASS
FAIL
NEEDS_HUMAN
```

It may emit findings and request additional evidence. It cannot emit repair actions, parent aggregation, approval, revision, or publication decisions.

### 3.2 Deterministic aggregation

Server-owned membership determines aggregation:

```text
region -> view -> sheet -> overall
```

Precedence:

```text
FAIL > NEEDS_HUMAN > PASS
```

No averaging or model-supplied parent verdict participates in this rule.

### 3.3 Critical-region rule

One failed critical region is sufficient to fail its containing view, sheet, and overall visual verdict. Passing siblings and strong sheet-average similarity cannot mask it.

A critical region with unresolved/conflicting protected evidence cannot become PASS. Request construction blocks or finalization yields the non-PASS state required by the accepted server-owned policy; the provider cannot waive the blocker.

### 3.4 Freshness rule

The request binds exact candidate/latest-mutation/evidence identities. After provider completion, finalization revalidates them. Any change produces stale failure and no final verdict artifact from the old provider output.

### 3.5 PASS is not approval

R5 PASS is visual evidence for one exact candidate state only. It is not engineering approval, R4 promotion, R6 repair authorization, or R7 publication eligibility.

---

## 4. Error and cleanup policy

R5 public failures are categorical and privacy-safe. Exact names are locked by the runtime Issue after Gate 0 reconciles accepted error vocabulary, but required categories are:

```text
R5_REBASELINE_REQUIRED
R5_INPUT_INVALID
R5_INPUT_NOT_READY
R5_EVIDENCE_STALE
R5_WORKER_AUTHORITY_MISMATCH
R5_PROVIDER_ATTESTATION_GAP
R5_PROVIDER_FAILED
R5_PROVIDER_TIMEOUT
R5_PROVIDER_CANCELLED
R5_PROVIDER_OUTPUT_INVALID
R5_CLEANUP_FAILED
R5_AGGREGATION_INVALID
```

R5 does not duplicate worker cleanup. It consumes the accepted worker cleanup result and rejects output if cleanup is not proven safe according to that owner.

Provider/private exception text, customer path, prompt content, source image bytes, and CAD content must not leak through categorical exceptions or `repr()`.

---

## 5. Prompt/input minimization verification matrix

The adapter tests must prove:

| Input | Provider-visible? | Authority |
|---|---:|---|
| Requested region source crop / bounded reference artifact | yes, when server-selected | existing source/evidence owner |
| Requested VS-T3 bounded render artifact | yes | VS-T3/visual_evidence |
| VS-T2 metrics/trend for requested region | yes | VS-T2 |
| Confirmed/protected dimension facts relevant to region | yes | accepted dimension/protected owner |
| R3 stable region/view/sheet labels | yes, minimum required IDs | accepted R3 |
| Entire private/customer CAD | no | outside R5 provider input |
| Accepted/base CAD write path | no | immutable external owner |
| Unrelated project files | no | outside scope |
| Credentials/API keys | no | worker/provider owner only |
| Repair tools/operations | no | R6/existing executor owner |
| Publication authorization | no | R7/existing promotion owner |

All provider-visible artifacts must satisfy accepted size/count/root/hash bounds. R5 does not invent a new artifact copying mechanism.

---

## 6. Reviewer-domain matrix

Every runtime task receives at least one independent reviewer; Tasks 5-6 require paired domains.

| Task | Primary review | Adversarial focus |
|---|---|---|
| 1 | schema/authority | open objects, hidden repair/publish fields |
| 2 | compatibility/authority | legacy visual_review weakening, duplicate validator |
| 3 | schema/lineage | action fields in final verdict |
| 4 | aggregation | critical-region masking, dangling membership |
| 5 | evidence/security | freshness races, foreign evidence, identity leakage |
| 5 | visual semantics | PASS vs engineering approval, deterministic aggregation |
| 6 | worker/provider security | custom provenance, alternate transport, attestation gaps |
| 6 | lifecycle/evidence | timeout/cancel/cleanup/late-output stale behavior |
| 7 | integration/CI | exact head/current-main synthetic, truthful gates |

A reviewer cannot approve from a different head SHA than the one named in the review request.

---

## 7. Dependency and overlap matrix at planning time

| Dependency/lane | Planning-time state | R5 runtime action |
|---|---|---|
| R1 Source Bundle/Fusion | required accepted dependency | wait for accepted/merged and map exact symbols |
| R2 Base CAD Adapter | required accepted dependency | wait for accepted/merged and map provenance seam |
| R3 PR #134 | DRAFT planning, not merged/runtime accepted | no moving API assumption |
| R4 Issue #133 | planning active, not runtime accepted | no moving API assumption |
| Wave 1A PR #113 | DRAFT/moving provider-attestation work | no moving API assumption; Gate 0 resolves final accepted seam |
| VS-T1 | accepted reusable owner | read/consume only |
| VS-T2 | accepted reusable owner | read/consume only |
| VS-T3 #29 | accepted reusable owner | read/consume only |
| Wave 1C #72 | operator/live evidence lane | no repository write overlap; live prerequisite reported truthfully |
| R6 #136 | separate planning lane | R5 emits evidence only; no repair scope |
| existing promotion/R7 future | external owner | no publisher authority |

Before each future runtime task the assigned writer must repeat active-writer overlap against fresh main. Any overlap with the exact task paths is a STOP unless Master PO sequences/reissues it.

---

## 8. Migration and rollback

### Contract migration

- keep historical `visual_review-1.0` semantics unchanged;
- add R5 contracts under the existing Visual Supervisor contract family;
- do not auto-convert historical `visual_review` into R5 final verdict;
- consumers that require R5 must require the new contract version explicitly.

### Runtime migration

The new adapter is additive. Existing VS-T1/T2/T3, fidelity, Mechanical review, repair, manifest, and publication behavior remain unchanged until later roadmap tasks explicitly integrate the new R5 artifact.

### Rollback

Each R5 task can be reverted independently because it does not migrate source/CAD data or replace existing stores. Reverting R5 leaves accepted evidence producers and historical contracts intact.

---

## 9. Current-main synthetic policy

For every future R5 PR:

1. writer branch is created from the exact Master PO issuance SHA;
2. no writer-side rebase/main-sync/cherry-pick is performed unless explicitly reissued;
3. before final review, record fresh current `main` SHA;
4. hosted PR checks test the exact head against GitHub's current-main PR synthetic;
5. record the synthetic SHA when available from hosted evidence;
6. if current main introduces overlap/architecture conflict, verdict is not GREEN; Master PO decides rebaseline;
7. `SKIP`, `NOT RUN`, queued, missing, or unavailable is never reported as PASS.

---

## 10. Final runtime verification dossier

A future R5 runtime completion packet must contain:

```text
Issuance base SHA
Branch
Exact final head SHA
Fresh current-main SHA
Hosted synthetic SHA
Exact cumulative changed paths
RED-first commits and commands per task
Focused R5 counts
Legacy visual-contract regression counts
VS-T1/T2/T3 regression counts
Final R3/R4 regression counts from Gate 0
Final Wave 1A worker/handoff/provider-attestation regression counts
Ruff results
Reuse inventory checker result
Architecture boundary checker result
git diff --check result
Canonical verifier result
Hosted tests run ID/conclusion
Hosted reuse-declaration run ID/conclusion
AutoCAD .NET state
AutoCAD Mechanical live state
Real provider/model/auth state
Private/customer CAD state
Independent reviewer exact-head verdicts
Open/unresolved review threads
Locked-scope confirmation
STOP WRITE confirmation
```

No entry may be inferred from another gate.

---

## 11. Program STOP conditions

Stop R5 work and return to Master PO if any task requires:

- a second visual-contract validator owner;
- a second OCR/dimension observer;
- a second deterministic geometry comparator;
- a second AutoCAD render/measurement/evidence exporter;
- a second SDK/App Server/CLI/MCP/HTTP/provider transport;
- a second component/view registry;
- a second revision/current store;
- a second manifest/checkpoint/evidence store;
- engineering approval authority;
- repair planning or execution authority;
- publication/promotion authority;
- CAD/source parsing or DXF geometry ownership;
- source/base/accepted/published CAD mutation;
- a third path for a bounded task without explicit amendment;
- private/customer CAD or real credentials for the first RED/GREEN slice;
- guessed R3/R4/#113 API symbols;
- provider output accepted without post-provider freshness recheck;
- whole-sheet/average similarity overriding a failed required region.

Required stop report for unresolved upstream ownership:

```text
R5 REBASELINE REQUIRED
```

---

## 12. Issue #135 planning verification

This planning lane itself is complete only when all of the following are proven on its final planning head:

- branch ancestry starts exactly at `b217ebfd597260d7b59badc3ffbcfbe7b1139754`;
- cumulative diff contains exactly:
  - `docs/superpowers/specs/2026-08-09-r5-visual-supervisor-adapter-design.md`
  - `docs/superpowers/plans/2026-08-09-r5-visual-supervisor-adapter.md`;
- both paths are additions;
- no runtime/test/workflow/dependency/lock/schema/contract path changed;
- design/plan name concrete reuse owners and the legacy `visual_review-1.0` migration issue;
- no moving R3/R4/#113 runtime API is invented;
- relevant docs/reuse/architecture verification is GREEN through the supported hosted verifier;
- hosted `tests` is SUCCESS on final planning head/current-main PR synthetic;
- hosted `reuse-declaration` is SUCCESS on that same final planning head;
- DRAFT PR is open;
- writer performs no repository content write after declaring STOP WRITE.

Required final planning return:

```text
CODER C R5 PLANNING READY — STOP WRITE
```

This plan does not authorize R5 runtime implementation, real provider/model/auth execution, live AutoCAD execution, private/customer CAD use, R6 repair work, or R7 publication work.