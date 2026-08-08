# R6 Repair Executor Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one thin R6 adapter that converts accepted R5 visual failures into validated schema-bound repair plans through the accepted official worker seam, then routes separately approved plans to existing repair executors against disposable R4 candidates only.

**Architecture:** R6 is one adjacent orchestration module, not a CAD engine. It reuses the existing `repair-plan-1.0` contract/validator, canonical hash owner, approval separation, headless repair, AutoCAD live repair/backup/rollback, and future accepted R3/R4/R5/worker owners. Planner output is untrusted; execution occurs only after a fresh server-owned approval and exact preflight. Unsupported plan operations fail closed instead of being translated into raw geometry or AutoCAD commands.

**Tech Stack:** Python 3.11, existing `cad_agent.visual_contracts`, `cad_agent.drawing_contracts.canonical_json_sha256`, accepted future `agent_lib` worker/approval seams after fresh rebaseline, `dxf_builder_lib` review/repair, `cad_agent.live` and `mcp_integration_lib` repair owners, pytest, Ruff, repository architecture/reuse checks, GitHub Actions on Windows.

## Global Constraints

- Planning authority: Issue #136 and `docs/superpowers/specs/2026-08-09-r6-repair-executor-adapter-design.md`.
- Planning base: `b217ebfd597260d7b59badc3ffbcfbe7b1139754`.
- R6 runtime is NOT authorized by this planning PR.
- Before runtime issuance, freshly map accepted R1-R5 and the accepted official worker/provider seam; moving #113/#133/#134/#135 symbols are not runtime APIs.
- Preferred cumulative future R6 runtime write-set is exactly two paths:
  - CREATE `cad_agent/repair_executor_adapter.py`
  - CREATE `tests/test_cad_agent_repair_executor_adapter.py`
- No third path. A third-path need is `R6 REBASELINE REQUIRED`.
- Reuse `contracts/visual-supervisor/repair-plan.schema.json`; do not create a second repair-plan schema.
- Reuse `cad_agent.visual_contracts.validate_visual_contract(..., contract="repair_plan")`.
- Reuse `cad_agent.drawing_contracts.canonical_json_sha256`; do not create a second canonical serializer/hash owner.
- Do not modify existing repair engines, File IPC/dispatcher, schemas, dependencies, lock files, workflows, manifest/store, revision owner, visual verdict owner, approval owner, or publisher merely for convenience.
- R6 may mutate only an upstream-proven disposable candidate through an existing executor. Source/base/accepted/published CAD is immutable.
- A valid repair plan is not execution approval.
- `NEEDS_HUMAN` is not executable repair authority. The automatic planner input is an accepted R5 `FAIL` only.
- Confirmed DRIVING/protected dimensions and datums cannot be changed for visual similarity alone.
- Pixel-space evidence cannot authorize model-space movement without accepted datum/calibration mapping.
- One R6 call is one bounded attempt. Retry/iteration/best-candidate ownership remains R4.
- First runtime tests use deterministic fakes and synthetic/disposable data. Real provider, private/customer CAD, and live AutoCAD remain NOT RUN until separately authorized.
- Preserve literal PASS / FAIL / SKIP / NOT RUN semantics.

## File Structure Locked for the Preferred Runtime

```text
Create:
  cad_agent/repair_executor_adapter.py
    Thin R6 context binding, planner orchestration, approval/freshness checks,
    exact-capability route selection, and normalized result evidence.

  tests/test_cad_agent_repair_executor_adapter.py
    All R6 RED-first contract, authority, determinism, fake-worker,
    fake-executor, and existing-owner integration tests.

Modify:
  NONE
```

The single production module is intentional. Splitting planner and execution into separate new modules would create unnecessary authority ambiguity; changing existing executors would expand ownership. Internal private helpers/protocols keep planning and execution responsibilities separated inside the one R6 boundary.

## Proposed Closed Public Surface

After fresh runtime rebaseline, the future runtime Issue should lock exactly these names and semantic parameters:

```text
R6_ADAPTER_VERSION = "r6-repair-executor-adapter-1.0"
R6RepairError(ValueError)

prepare_repair_plan(
    visual_failure,
    candidate_revision,
    component_view_impacts,
    protected_constraints,
    worker_boundary,
) -> normalized repair-plan evidence mapping

execute_approved_repair(
    repair_plan,
    approval,
    candidate_revision,
    component_view_impacts,
    protected_constraints,
    execution_boundary,
) -> normalized repair-result evidence mapping
```

`worker_boundary` and `execution_boundary` are server-owned injected seams. Runtime rebaseline must bind them to exact accepted owner types; callers cannot mint trusted worker/executor authority merely by matching an object shape.

Public API expansion is a STOP condition unless Master PO amends the runtime Issue.

---

### Task 1: Closed R6 context binding and deterministic identity

**Files:**
- Create first for RED: `tests/test_cad_agent_repair_executor_adapter.py`
- Create after meaningful RED: `cad_agent/repair_executor_adapter.py`

**Interfaces:**
- Consumes: accepted future R5 FAIL identity, R4 candidate/revision identity, R3 component/view-impact identity, protected-constraint identity; current repair-plan validator and canonical hash owner.
- Produces: `R6RepairError`, `R6_ADAPTER_VERSION`, and private normalized context identity used by both public operations.

- [ ] **Step 1: Fresh-rebaseline all required upstream owners before any repository write**

The runtime Issue must record exact accepted main SHA and exact symbols for:

```text
R3 component/view impact identity + freshness
R4 candidate/revision identity + disposable-candidate state + current drawing hash
R5 closed visual verdict + freshness/mutation binding
Wave 1A server-owned official worker/provider seam
approval identity/apply gate
repair-plan schema + validator
headless repair + review
live repair + backup/second-review/rollback
canonical hash owner
```

If any semantic input required by the R6 design cannot be proved without a schema/store/third-path change, STOP with `R6 REBASELINE REQUIRED`. Do not invent an upstream symbol.

- [ ] **Step 2: Write the Task-1 RED tests only**

The first future R6 repository content write must be only `tests/test_cad_agent_repair_executor_adapter.py`. Use synthetic dictionaries/fakes with explicit stable IDs/hashes and prove these behaviors:

```text
closed public surface
R5 verdict must be FAIL, never PASS or NEEDS_HUMAN
candidate must be disposable/current for the supplied R4 identity
R5 observed mutation hash must equal current candidate hash
stale R3/R4/R5 identity fails closed
protected DRIVING dimension cannot be a visual-similarity mutation target
pixel delta without accepted datum/calibration mapping fails closed
reordered set-like inputs produce the same canonical context identity
authoritative content mutation changes canonical identity
R6 calls the existing canonical hash owner rather than a local hash function
private path/provider-text sentinels never appear in errors
```

Static tests must reject direct R6 ownership of `hashlib` canonical hashing, DXF entity creation, MCP/.NET mutation, AutoCAD plugin APIs, source CAD reopen, manifest/store writes, visual PASS, revision promotion, and publication.

- [ ] **Step 3: Run focused tests and prove meaningful RED**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_repair_executor_adapter.py `
  -q -p no:cacheprovider
```

Expected: FAIL because `cad_agent.repair_executor_adapter` does not exist. Production must still be absent. Commit the RED-only test file before creating production:

```powershell
git add tests/test_cad_agent_repair_executor_adapter.py
git commit -m "test: RED R6 repair context binding"
```

- [ ] **Step 4: Implement only the normalized context boundary**

Create `cad_agent/repair_executor_adapter.py` and import exact accepted upstream validators resolved in Step 1. The implementation order is fixed:

```text
validate R5 closed evidence through accepted R5 owner
-> require verdict == FAIL
-> validate R4 candidate through accepted R4 owner
-> require disposable-candidate state and exact current drawing hash
-> validate R3 impact set through accepted R3 owner
-> validate protected constraints through accepted engineering/dimension owner
-> cross-bind run/revision/mutation identities
-> reject protected-dimension and missing-datum/calibration mutations
-> construct a normalized mapping containing only accepted identity material
-> compute context SHA through cad_agent.drawing_contracts.canonical_json_sha256
```

If an exact accepted validator is absent, STOP rather than implementing a permissive R6 substitute.

The canonical context material must use `identity_kind = "r6-repair-context-v1"` and `adapter_version = "r6-repair-executor-adapter-1.0"`, plus normalized R5/R4/R3/protected-constraint identity subobjects. It must exclude wall clock, random UUIDs, path spelling, provider thread ID, raw AutoCAD handle, raw exception text, and caller ordering.

- [ ] **Step 5: Run Task-1 focused and upstream contract regressions**

Run the focused R6 file plus the exact R3/R4/R5/protected-dimension contract test files recorded by Step 1. Also retain the current repair-plan contract validator regression. If any recorded path no longer exists, STOP `R6 REBASELINE REQUIRED`; do not silently skip it.

Expected: all selected offline tests PASS; real provider and AutoCAD remain NOT RUN.

- [ ] **Step 6: Run static owner checks and commit Task 1**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check `
  cad_agent/repair_executor_adapter.py `
  tests/test_cad_agent_repair_executor_adapter.py

.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check `
  --repo-root . `
  --baseline contracts/reuse-integration/architecture-boundaries.json

git diff --check
```

Commit only the two R6 paths:

```powershell
git add cad_agent/repair_executor_adapter.py tests/test_cad_agent_repair_executor_adapter.py
git commit -m "feat: bind R6 repair context"
```

---

### Task 2: Bounded Codex repair planning through the accepted worker seam

**Files:**
- Modify first for RED: `tests/test_cad_agent_repair_executor_adapter.py`
- Modify after meaningful RED: `cad_agent/repair_executor_adapter.py`

**Interfaces:**
- Consumes: Task-1 normalized R6 context; exact accepted official worker/provider seam recorded at rebaseline; immutable existing repair-plan schema/validator.
- Produces: `prepare_repair_plan(...)`, returning a normalized validated plan envelope with deterministic R6 request/plan identities and no execution authority.

- [ ] **Step 1: Add Task-2 planner RED cases before production edits**

Add concrete fake-worker tests proving:

```text
only the accepted server-owned worker boundary is invoked
worker receives minimized normalized context and exact accepted schema binding
worker output remains untrusted until repair-plan validation succeeds
source_review_id and run_id exactly match R5/server context
target_drawing_sha256 exactly matches current R4 candidate hash
all plan targets resolve in accepted R3 scope
preserve anchors and constraint refs cannot widen server-owned scope
protected DRIVING dimensions cannot be changed
model-space movement requires accepted datum/calibration mapping
provider cannot add approval, visual PASS, promotion, or publication authority
missing/partial/malformed output fails closed
worker timeout/cancel/failure/late output fails closed
missing worker/provider attestation fails closed
input permutations/replay produce identical request/plan identities
provider thread/turn IDs and raw text do not enter canonical identity
```

No real model/auth/network call is permitted in these tests.

- [ ] **Step 2: Prove Task-2 meaningful RED and commit test-only**

Run the focused R6 file. Expected: only newly added planner cases fail for missing planner behavior while Task-1 cases remain PASS. Commit test-only:

```powershell
git add tests/test_cad_agent_repair_executor_adapter.py
git commit -m "test: RED R6 bounded repair planning"
```

- [ ] **Step 3: Implement `prepare_repair_plan()` in the fixed authority order**

```text
validate current R6 context
-> build minimized deterministic planner request
-> bind exact accepted repair-plan schema snapshot/hash using the accepted worker owner
-> invoke the accepted worker/provider seam once with bounded limits
-> reject timeout/cancel/attestation-gap/partial/late output
-> validate returned mapping with validate_visual_contract(..., contract="repair_plan")
-> cross-bind source_review_id/run_id/target hash/R3 targets/protected constraints
-> canonical-hash normalized R6 plan envelope with existing canonical owner
-> return evidence only; no executable/approval authority is minted
```

The function must not call Agent apply, `dxf_builder_lib.repair`, `cad_agent.live.repair_live`, MCP, File IPC, or AutoCAD.

If the accepted worker seam cannot prove the required instruction/provider policy or immutable schema binding, return categorical `WORKER_ATTESTATION_GAP` and STOP; R6 may not introduce App Server/CLI/MCP fallback.

- [ ] **Step 4: Run planner-focused and exact accepted worker regressions**

Step 1 rebaseline must record the exact accepted worker test-file list in the runtime Issue. Run the R6 focused file together with every path in that recorded list. An unresolved or missing worker test path is `R6 REBASELINE REQUIRED`, not permission to guess or skip.

Expected: fake/provider-independent R6 planning PASS; accepted worker regressions PASS; real provider call NOT RUN.

- [ ] **Step 5: Repeat planner determinism at least five times**

Execute the focused replay/permutation tests five consecutive times from one committed source state. Equivalent evidence must yield identical request/plan hashes; authoritative-content changes must change hashes. A time/order-dependent result is FAIL.

- [ ] **Step 6: Ruff, architecture/reuse, diff check, and commit Task 2**

Run the exact two-path Ruff and architecture commands from Task 1 plus the repository Reuse Declaration checker discovered on the accepted base. Commit only the same two R6 paths:

```powershell
git add cad_agent/repair_executor_adapter.py tests/test_cad_agent_repair_executor_adapter.py
git commit -m "feat: add bounded R6 repair planning"
```

---

### Task 3: Separate approval, fresh preflight, and exact existing-executor routing

**Files:**
- Modify first for RED: `tests/test_cad_agent_repair_executor_adapter.py`
- Modify after meaningful RED: `cad_agent/repair_executor_adapter.py`

**Interfaces:**
- Consumes: validated Task-2 repair plan; accepted server-owned approval owner; fresh R3/R4/R5/protected-constraint evidence; exact rebaselined executor-capability map; accepted headless review/repair and live repair safety owners.
- Produces: `execute_approved_repair(...)`, returning normalized repair-result evidence only.

- [ ] **Step 1: Freeze an exact executor capability map before Task-3 test write**

On the fresh accepted runtime base, inventory every existing `repair-plan-1.0` operation:

```text
MOVE_COMPONENT
ALIGN_COMPONENT
REPLACE_POLYLINE_SEGMENT
ADJUST_ARC
ADJUST_SPLINE_CONTROL_REGION
ADD_MISSING_FEATURE
REMOVE_EXTRA_FEATURE
REPLACE_WITH_APPROVED_BLOCK
CREATE_NATIVE_DIMENSION
REPAIR_NATIVE_DIMENSION
```

Each operation receives exactly one classification:

```text
HEADLESS_EXISTING_REPAIR -> exact owner symbol + required evidence
AUTOCAD_EXISTING_REPAIR -> exact owner symbol + required safety wrapper
UNSUPPORTED -> no exact existing accepted business-operation match
```

Do not infer support from low-level entity-create/erase primitives. If product acceptance requires an `UNSUPPORTED` operation, STOP and issue a separate bounded existing-owner extension; do not implement raw mutation inside R6.

- [ ] **Step 2: Add Task-3 RED cases before execution production edits**

Use fake execution boundaries to prove:

```text
plan without separate approval cannot execute
approval must bind exact canonical plan hash and candidate hash
replayed/expired/foreign approval fails closed
fresh preflight rejects candidate hash drift
fresh preflight rejects changed R3/R5/protected-constraint identity
source/base/accepted/published target is never executable
unsupported operation fails before executor call
caller cannot forge executor capability or route
headless route delegates to existing repair owner and requires second review
autocad route delegates to existing live safety owner, never raw MCP
backup/preflight failure prevents mutation
partial mutation is failure evidence only
timeout/cleanup/uncertain save state cannot succeed
failed post-review requires existing rollback evidence
rollback failure is terminal and not promotion-safe
late executor result after terminal state is rejected
result cannot contain visual PASS, engineering approval, promotion, or publish authority
result identity excludes backup timestamp/path and volatile handles
```

The fake boundary records calls only; production authorization must still come from exact accepted owner identity resolved at rebaseline.

- [ ] **Step 3: Prove Task-3 meaningful RED and commit test-only**

Run the focused R6 file. New execution cases must fail while Tasks 1-2 remain GREEN. Commit only the test path:

```powershell
git add tests/test_cad_agent_repair_executor_adapter.py
git commit -m "test: RED R6 approved repair routing"
```

- [ ] **Step 4: Implement `execute_approved_repair()` with strict sequencing**

Required order:

```text
validate repair plan again
-> validate separate server-owned approval
-> validate current R6 context again
-> prove disposable R4 candidate
-> prove exact approved current candidate hash
-> prove R3/R5/protected identities fresh
-> resolve every operation through frozen accepted capability map
-> reject the entire call if any operation is unsupported or mixed routing is unsafe
-> invoke accepted existing executor/safety owner
-> require its backup/preflight/post-review/rollback/cleanup evidence as applicable
-> canonicalize normalized R6 result envelope
-> return evidence only
```

There is no fallback from unsupported headless semantics to raw AutoCAD commands and no fallback from AutoCAD failure to a lower-level transport.

For the audited live path, delegate to the accepted `cad_agent.live.repair_live`-equivalent owner so backup and second review remain outside R6. For the audited headless path, repair and review remain separate accepted calls; R6 requires the second review result before returning structural success.

- [ ] **Step 5: Run focused R6 plus existing repair/live regressions**

The runtime rebaseline dossier must record exact accepted successors of these current-base domains and run them:

```text
dxf_builder_lib repair tests
dxf_builder_lib reviewer tests
cad_agent CLI/live safety tests
mcp_integration_lib .NET/File IPC contract tests
R3/R4/R5 freshness/identity tests
approval-owner tests
```

AutoCAD Mechanical live is NOT RUN in the first runtime slice. Existing unavailable-state tests may SKIP only for documented prerequisites.

- [ ] **Step 6: Run architecture anti-duplication checks**

Static checks must prove R6 production does not directly mutate through MCP/.NET, open/rewrite CAD itself, construct ezdxf entities, write manifest/revision/current state, assign visual PASS/engineering approval, call publisher/promote, implement retry-until-pass, compute canonical SHA through a second owner, or create a provider transport.

- [ ] **Step 7: Commit Task 3 normally**

```powershell
git add cad_agent/repair_executor_adapter.py tests/test_cad_agent_repair_executor_adapter.py
git commit -m "feat: route approved repairs to existing executors"
```

---

### Task 4: Adversarial hardening, exact write-set verification, and hosted GREEN

**Files:**
- Test-first modifications only within `tests/test_cad_agent_repair_executor_adapter.py`.
- Production remediation, only after meaningful RED, within `cad_agent/repair_executor_adapter.py`.
- No third path.

**Interfaces:**
- Consumes: Tasks 1-3 final exact head.
- Produces: final reviewable R6 runtime head with deterministic/fail-closed evidence and no promotion/publication authority.

- [ ] **Step 1: Add adversarial cross-task tests before any hardening production edit**

Cover:

```text
valid R5 FAIL from older R4 mutation generation
R3 stable entity moved to a different component/view revision
same plan bytes paired with another candidate revision
approval matches plan ID but not canonical plan hash
duplicate/conflicting operation targets
multiple operations indirectly touch one protected anchor
one plan contains both supported and unsupported operations
executor reports repaired_count but post-hash is unchanged/unexpected
executor reports success while cleanup/rollback evidence is malformed
schema-valid worker plan contains stale target drawing hash
provider output contains private path/secret sentinel
executor exception contains private path/command sentinel
reordered set-like impacts/anchors produce identical identity
authoritative content mutation under same caller ID changes identity
```

Every newly exposed behavior gets test-only RED before production remediation.

- [ ] **Step 2: Run the focused suite repeatedly**

Run all R6 tests at least five consecutive times. No intermittent ordering/time/path failures are acceptable.

- [ ] **Step 3: Run broader accepted dependency regressions**

Use the exact test-file lists recorded in the runtime rebaseline dossier for these domains:

```text
R3 registry identity/freshness
R4 candidate/revision immutability/staleness
R5 visual verdict/freshness
Wave 1A worker/provider attestation/lifecycle
repair-plan validation
protected dimensions / Drawing Setup / Dimension Pilot
headless review/repair
live repair backup/rollback
manifest/checkpoint/resume compatibility
```

Any unresolved upstream failure blocks R6; do not weaken predecessor tests.

- [ ] **Step 4: Run canonical verifier**

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Expected for offline R6 acceptance: canonical verification completes successfully; AutoCAD .NET is literal NOT RUN because of the explicit skip; private/real-data and AutoCAD unavailable probes retain repository-defined SKIP semantics. A separately authorized local live acceptance is required before any AutoCAD-live PASS claim.

- [ ] **Step 5: Run exact Ruff, architecture, reuse, and diff gates**

The runtime Issue must export its exact base into `$env:R6_EXACT_BASE` before running verification. Then run:

```powershell
if (-not $env:R6_EXACT_BASE) { throw 'R6_EXACT_BASE is required from the issued runtime task' }

.\.venv-py311\Scripts\python.exe -m ruff check `
  cad_agent/repair_executor_adapter.py `
  tests/test_cad_agent_repair_executor_adapter.py

.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check `
  --repo-root . `
  --baseline contracts/reuse-integration/architecture-boundaries.json

git diff --check "$env:R6_EXACT_BASE...HEAD"
```

- [ ] **Step 6: Audit cumulative changed paths**

Expected exactly:

```text
cad_agent/repair_executor_adapter.py
tests/test_cad_agent_repair_executor_adapter.py
```

Any third path is `R6 REBASELINE REQUIRED`.

- [ ] **Step 7: Open a DRAFT PR and verify hosted exact-head/current-main synthetic**

The PR body must include all eight literal Reuse Declaration labels:

```text
Existing capability inspected:
Existing API reused:
Adapter required:
New capability genuinely missing:
Files allowed to change:
Files forbidden to duplicate:
Compatibility behavior:
Migration and rollback path:
```

Hosted `tests` and `reuse-declaration` must both be SUCCESS, and the checkout/log must identify the exact writer head/current-main synthetic. Do not convert unrelated SKIP/NOT RUN into PASS.

- [ ] **Step 8: Independent review and STOP WRITE**

Security/authority reviewer checks candidate-only mutation, stale evidence, protected constraints, approval separation, unsupported-operation closure, rollback/cleanup, no second owner, and privacy-safe failures.

Integration/CI reviewer checks exact base/head/synthetic, RED-first chronology, exact two-path write-set, hosted CI/reuse, current-main compatibility, regression coverage, and PASS/FAIL/SKIP/NOT RUN truthfulness.

Writer stops repository writes until Master PO disposition.

---

## Runtime RED-First Matrix Summary

| Domain | Required RED before implementation | Expected fail-closed behavior |
| --- | --- | --- |
| R5 input | PASS/NEEDS_HUMAN/stale FAIL | `VISUAL_FAIL_REQUIRED` / `STALE_REPAIR_CONTEXT` |
| Candidate authority | source/base/accepted/published/foreign candidate | refuse before worker/executor |
| Candidate freshness | changed current drawing hash | `CANDIDATE_IDENTITY_MISMATCH` |
| R3 scope | missing/foreign/stale entity/component/view | `REPAIR_TARGET_OUT_OF_SCOPE` |
| Protected dimensions | visual change conflicts with DRIVING/protected value | `PROTECTED_CONSTRAINT_VIOLATION` |
| Coordinate mapping | pixel delta without accepted datum/calibration | `DATUM_MAPPING_REQUIRED` |
| Worker output | malformed/partial/extra-authority fields | `REPAIR_PLAN_INVALID` |
| Plan cross-binding | wrong review/run/target hash | `REPAIR_PLAN_TARGET_MISMATCH` |
| Worker security | missing provider/instruction/schema evidence | `WORKER_ATTESTATION_GAP` |
| Approval | absent/stale/foreign/wrong hash | `APPROVAL_REQUIRED` / `APPROVAL_MISMATCH` |
| Operation routing | no exact existing executor semantic | `UNSUPPORTED_REPAIR_OPERATION` before mutation |
| Executor authority | caller-forged/raw route | reject before executor call |
| Live preflight | stale session/hash/backup/DBMOD/evidence | fail before mutation through accepted safety owner |
| Partial failure | some mutation then error | failure evidence; no promotion |
| Post-review | repaired but verification fails | existing rollback path, no success |
| Rollback/cleanup | uncertain or failed | terminal `ROLLBACK_FAILED` / `CLEANUP_FAILED` |
| Late result | result after timeout/cancel/terminal | `LATE_RESULT_REJECTED` |
| Determinism | order/UUID/path/time changes only | same canonical identity |
| Mutation sensitivity | authoritative content changes | different canonical identity |
| Privacy | raw path/prompt/exception sentinel | categorical error only |

## Verification Semantics

`PASS` means the exact command/gate executed and met its contract.

`FAIL` means it executed and contradicted the contract; do not relabel it without evidence and Master PO disposition.

`SKIP` is only an explicitly coded optional/unavailable-state test outcome.

`NOT RUN` means the operation was not executed, including first-slice real provider, private/customer CAD, AutoCAD Mechanical live, and publication.

Hosted offline GREEN does not convert AutoCAD live or real-provider execution into PASS.

## Migration and Rollback

R6 adds no schema/store/data migration. Existing `repair-plan-1.0`, visual-review, manifest, repair, backup, and AutoCAD transport owners stay intact.

Runtime rollback is a normal revert/removal of the two adjacent R6 paths. Existing legacy headless and mechanical repair commands remain usable under their existing contracts.

A candidate actually mutated during a separately authorized live pilot is restored/retained according to existing repair/revision owners; reverting R6 source code is not a substitute for CAD rollback evidence.

## Overlap Matrix

| Lane / owner | Expected overlap with preferred R6 two-path runtime write-set | Rule |
| --- | --- | --- |
| #123 R1C Task 5 | None | #123 branch remains frozen until separately reactivated. |
| R3 planning/runtime | Semantic dependency only; no path overlap intended | R6 waits for accepted R3 APIs and does not edit registry owner. |
| R4 planning/runtime | Semantic dependency only | R4 owns candidate/revision state, retries, promotion/rollback lineage. |
| R5 planning/runtime | Semantic dependency only | R5 owns verdict/freshness; R6 consumes FAIL only. |
| Wave 1A worker/provider | Semantic dependency only | R6 calls accepted seam; no `agent_lib/**` modification in preferred scope. |
| `dxf_builder_lib` repair/review | Read-only dependency | No R6 modification; unsupported semantics require separate owner task. |
| AutoCAD/File IPC/.NET | Read-only dependency | No dispatcher/transport modification; live execution serialized by local operator lane. |
| R7 Publisher | No overlap | R6 emits no publication eligibility or promotion. |

Any real path overlap at runtime issuance requires explicit one-writer rebaseline before work begins.

## STOP Conditions

Stop and return to Master PO instead of widening R6 when any of these occurs:

- final R3/R4/R5/worker contracts cannot supply the semantic identities required by the design;
- the accepted repair-plan contract must change to express R6 safety;
- `cad_agent.visual_contracts.py` must change;
- an existing executor lacks a required operation and product scope requires adding it;
- `dxf_builder_lib/repair.py`, `cad_agent/live.py`, `mcp_integration_lib/**`, or `autocad_plugin/**` must change;
- a second approval, manifest, checkpoint, revision, verdict, repair, provider, or publisher owner appears necessary;
- source/base/accepted/published CAD would need mutation;
- path-only, volatile-handle-only, stale evidence, or uncalibrated pixel geometry would need to be trusted;
- a third repository path appears necessary;
- dependency/lock/workflow/schema changes appear necessary;
- private/customer CAD or real provider is claimed necessary for first offline runtime acceptance;
- exact base/branch lineage or one-writer ownership is no longer clean.

Return exactly `R6 REBASELINE REQUIRED` with the path/authority gap rather than improvising scope.

## Planning-to-Runtime Handoff

When R1-R5 and the worker/provider seam are accepted, Master PO should issue a fresh R6 runtime task only after recording:

```text
fresh exact main SHA
accepted R3 identity/freshness APIs
accepted R4 candidate/revision/disposable APIs
accepted R5 FAIL/freshness APIs
accepted worker/provider/schema-attestation APIs
accepted approval API
repair-plan schema/validator exact identity
existing executor capability map
existing backup/rollback/live safety APIs
exact two-path runtime allowlist or explicit rebaseline amendment
paired security + integration reviewers
```

With those fields resolved, Task 1 can begin RED-first immediately without another architecture discovery round.