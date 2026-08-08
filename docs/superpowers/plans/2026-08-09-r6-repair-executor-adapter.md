# R6 Repair Executor Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one thin R6 adapter that converts accepted R5 visual failures into validated schema-bound repair plans through the accepted official worker seam, then routes separately approved plans to existing repair executors against disposable R4 candidates only.

**Architecture:** R6 is one adjacent orchestration module, not a CAD engine. It reuses the existing `repair-plan-1.0` contract/validator, canonical hash owner, approval separation, headless repair, AutoCAD live repair/backup/rollback, and future accepted R3/R4/R5/worker owners. Planner output is untrusted; execution occurs only after a fresh server-owned approval and exact preflight. Unsupported plan operations fail closed instead of being translated into raw geometry or AutoCAD commands.

**Tech Stack:** Python 3.11, existing `cad_agent.visual_contracts`, `cad_agent.drawing_contracts.canonical_json_sha256`, existing `agent_lib` worker/approval seams after acceptance, `dxf_builder_lib` review/repair, `cad_agent.live` and `mcp_integration_lib` repair owners, pytest, Ruff, repository architecture/reuse checks, GitHub Actions on Windows.

## Global Constraints

- Planning authority: Issue #136 and `docs/superpowers/specs/2026-08-09-r6-repair-executor-adapter-design.md`.
- Planning base: `b217ebfd597260d7b59badc3ffbcfbe7b1139754`.
- R6 runtime is NOT authorized by this planning PR.
- Before runtime issuance, freshly map accepted R1-R5 and the accepted official worker/provider seam; moving #113/#134/#133/#135 symbols are not runtime APIs.
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

After fresh runtime rebaseline, the future runtime Issue should lock exactly:

```python
R6_ADAPTER_VERSION = "r6-repair-executor-adapter-1.0"

class R6RepairError(ValueError):
    pass


def prepare_repair_plan(
    *,
    visual_failure: Mapping[str, object],
    candidate_revision: Mapping[str, object],
    component_view_impacts: Mapping[str, object],
    protected_constraints: Mapping[str, object],
    worker_boundary: object,
) -> dict[str, object]: ...


def execute_approved_repair(
    *,
    repair_plan: Mapping[str, object],
    approval: Mapping[str, object],
    candidate_revision: Mapping[str, object],
    component_view_impacts: Mapping[str, object],
    protected_constraints: Mapping[str, object],
    execution_boundary: object,
) -> dict[str, object]: ...
```

`worker_boundary` and `execution_boundary` are server-owned injected seams. Runtime rebaseline must bind them to exact accepted owner types; callers cannot mint trusted worker/executor authority merely by matching a protocol shape.

Public API expansion is a STOP condition unless Master PO amends the runtime Issue.

---

### Task 1: Closed R6 context binding and deterministic identity

**Files:**
- Create first for RED: `tests/test_cad_agent_repair_executor_adapter.py`
- Create after meaningful RED: `cad_agent/repair_executor_adapter.py`

**Interfaces:**
- Consumes: accepted future R5 FAIL mapping, R4 candidate-revision mapping, R3 component/view-impact mapping, protected-constraint mapping; current `cad_agent.visual_contracts.validate_visual_contract`; current `cad_agent.drawing_contracts.canonical_json_sha256`.
- Produces: the public `R6RepairError`, `R6_ADAPTER_VERSION`, and the context-validation portion used by `prepare_repair_plan()` and `execute_approved_repair()`.

- [ ] **Step 1: Fresh-rebaseline all required upstream owners before any repository write**

Record exact accepted main and exact symbols for:

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

If any semantic input required by the R6 design cannot be proved without a schema/store/third-path change, STOP with:

```text
R6 REBASELINE REQUIRED
```

Do not invent an upstream symbol.

- [ ] **Step 2: Write the Task-1 RED tests only**

The first future R6 repository content write must be only `tests/test_cad_agent_repair_executor_adapter.py` and must cover at least:

```python
def test_r6_public_surface_is_closed(): ...
def test_context_requires_r5_fail_not_pass_or_needs_human(): ...
def test_context_requires_disposable_candidate_identity(): ...
def test_candidate_hash_must_match_r5_observed_mutation(): ...
def test_stale_r3_r4_r5_context_fails_closed(): ...
def test_protected_driving_dimension_cannot_be_visual_repair_target(): ...
def test_pixel_offset_requires_accepted_datum_mapping(): ...
def test_context_identity_ignores_input_order_and_ambient_fields(): ...
def test_context_identity_changes_when_authority_content_changes(): ...
def test_context_hash_uses_existing_canonical_owner(): ...
def test_errors_do_not_leak_private_path_or_provider_text(): ...
```

Static tests must reject direct imports/usages that would create a second owner:

```text
hashlib/json canonical hashing inside R6
dxf_builder entity creation
MCPClient / DotNetIPCClient mutation calls
AutoCAD plugin APIs
filesystem source CAD reopen
manifest/store writes
visual PASS assignment
revision promotion/publication
```

- [ ] **Step 3: Run focused tests and prove meaningful RED**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_repair_executor_adapter.py `
  -q -p no:cacheprovider
```

Expected: FAIL because the R6 adapter/public surface/context behavior does not exist. Production must still be absent at this point.

Commit the RED-only state before production:

```powershell
git add tests/test_cad_agent_repair_executor_adapter.py
git commit -m "test: RED R6 repair context binding"
```

- [ ] **Step 4: Implement the minimum context validator in the new production module**

The implementation must import accepted owners rather than copy them. The shape should remain equivalent to:

```python
from collections.abc import Mapping

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.visual_contracts import validate_visual_contract

R6_ADAPTER_VERSION = "r6-repair-executor-adapter-1.0"


class R6RepairError(ValueError):
    pass


def _fail(code: str) -> None:
    raise R6RepairError(code)


def _validated_context(
    *,
    visual_failure: Mapping[str, object],
    candidate_revision: Mapping[str, object],
    component_view_impacts: Mapping[str, object],
    protected_constraints: Mapping[str, object],
) -> dict[str, object]:
    # Validate through freshly accepted R3/R4/R5 owners first.
    # Require FAIL, current matching candidate hash, exact run/revision scope,
    # non-stale impacts, protected constraints, and datum mapping rules.
    # Return only normalized server-owned identity material.
    ...
```

The future implementation must replace the explanatory body above with exact accepted validators resolved during rebaseline; it must not add permissive local substitutes. If no accepted validator exists, STOP instead of filling the gap inside R6.

Canonical context identity is:

```python
context_sha256 = canonical_json_sha256(
    {
        "identity_kind": "r6-repair-context-v1",
        "adapter_version": R6_ADAPTER_VERSION,
        "visual_failure": normalized_visual_identity,
        "candidate_revision": normalized_candidate_identity,
        "component_view_impacts": normalized_impact_identity,
        "protected_constraints": normalized_constraint_identity,
    }
)
```

No wall clock, UUID, path spelling, provider thread ID, raw handle, exception text, or caller order enters this identity.

- [ ] **Step 5: Run Task-1 focused and upstream contract regressions**

Run the exact focused file plus the freshly resolved R3/R4/R5 contract tests and current visual-contract/dimension-protection tests. At minimum keep current-base analogues represented by:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_repair_executor_adapter.py `
  tests/test_visual_contracts.py `
  -q -p no:cacheprovider
```

If the accepted test path names moved, use their exact rebaselined names and record them; do not silently skip them.

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
- Consumes: Task-1 normalized R6 context; accepted official worker/provider seam; immutable `contracts/visual-supervisor/repair-plan.schema.json`; `validate_visual_contract(..., contract="repair_plan")`.
- Produces: `prepare_repair_plan(...) -> dict[str, object]`, returning a normalized validated plan envelope with deterministic R6 request/plan identities and no execution authority.

- [ ] **Step 1: Add Task-2 planner RED cases before production edits**

Add tests for:

```python
def test_prepare_repair_plan_calls_only_accepted_worker_boundary(): ...
def test_worker_receives_minimized_bounded_context_and_exact_schema_binding(): ...
def test_worker_output_is_untrusted_until_repair_plan_validator_passes(): ...
def test_plan_source_review_and_run_must_match_server_context(): ...
def test_plan_target_hash_must_equal_current_candidate_hash(): ...
def test_plan_targets_must_resolve_through_r3_scope(): ...
def test_plan_preserve_anchors_and_constraints_cannot_widen_scope(): ...
def test_plan_cannot_change_protected_driving_dimension(): ...
def test_plan_model_space_move_requires_accepted_mapping(): ...
def test_worker_cannot_add_approval_visual_pass_promotion_or_publication_fields(): ...
def test_missing_partial_malformed_provider_output_fails_closed(): ...
def test_provider_timeout_cancel_failure_and_late_output_fail_closed(): ...
def test_worker_attestation_gap_fails_before_plan_acceptance(): ...
def test_plan_identity_is_replay_and_permutation_deterministic(): ...
def test_provider_thread_turn_and_raw_text_do_not_enter_plan_identity(): ...
```

Use a deterministic fake worker boundary. No real model/auth/network call.

- [ ] **Step 2: Prove Task-2 meaningful RED and commit test-only**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_repair_executor_adapter.py `
  -q -p no:cacheprovider
```

Expected: only the newly added planner behavior fails for missing `prepare_repair_plan`/planner semantics; all Task-1 cases remain PASS.

Commit test-only:

```powershell
git add tests/test_cad_agent_repair_executor_adapter.py
git commit -m "test: RED R6 bounded repair planning"
```

- [ ] **Step 3: Implement planner request construction and output validation**

`prepare_repair_plan()` must perform this sequence:

```text
validate current R6 context
-> build minimized deterministic planner request
-> bind exact accepted repair-plan schema snapshot/hash through worker owner
-> invoke accepted worker/provider seam once with bounded limits
-> reject timeout/cancel/attestation-gap/partial/late output
-> validate returned mapping with existing repair-plan validator
-> cross-bind source_review_id/run_id/target hash/R3 targets/protected constraints
-> canonical-hash normalized R6 plan envelope
-> return evidence only, with executable=false / no approval authority
```

The function must not call `agent_lib` apply, `dxf_builder_lib.repair`, `cad_agent.live.repair_live`, MCP, File IPC, or AutoCAD.

Use the accepted worker owner exactly as rebaselined. If the official seam cannot prove effective instruction/provider policy or immutable schema binding, fail `WORKER_ATTESTATION_GAP` and STOP; do not introduce App Server/CLI/MCP fallback in R6.

- [ ] **Step 4: Run planner-focused and worker-boundary regressions**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_repair_executor_adapter.py `
  <accepted-worker-focused-test-files> `
  -q -p no:cacheprovider
```

The future runtime Issue must replace `<accepted-worker-focused-test-files>` with exact accepted file paths during rebaseline before repository write. If exact worker tests cannot be resolved, STOP `R6 REBASELINE REQUIRED`; do not run a guessed path.

Expected: fake/provider-independent R6 planning PASS; accepted worker regressions PASS; real provider call NOT RUN.

- [ ] **Step 5: Repeat planner determinism at least five times**

Run the R6 replay/permutation subset five times from the same committed source state. Every run must produce identical normalized request/plan hashes for equivalent evidence and different hashes for authoritative-content changes.

A flaky or time/order-dependent identity is FAIL, not retry-to-green evidence.

- [ ] **Step 6: Ruff, architecture/reuse, diff check, and commit Task 2**

Run the same exact-two-path Ruff and architecture commands from Task 1 plus repository Reuse Declaration validation. Commit only the same two R6 paths:

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
- Consumes: validated Task-2 repair plan; accepted server-owned approval owner; fresh R3/R4/R5/protected-constraint evidence; exact rebaselined existing executor-capability map; accepted headless review/repair and live repair safety owners.
- Produces: `execute_approved_repair(...) -> dict[str, object]`, a normalized repair-result evidence envelope only.

- [ ] **Step 1: Freeze an exact executor capability map before Task-3 test write**

On the fresh accepted runtime base, inventory each `repair-plan-1.0` operation against existing accepted executor APIs:

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

For every operation record exactly one:

```text
HEADLESS_EXISTING_REPAIR -> exact owner symbol + required evidence
AUTOCAD_EXISTING_REPAIR -> exact owner symbol + required safety wrapper
UNSUPPORTED -> no exact existing accepted business-operation match
```

Do not infer support because a low-level line/circle/erase primitive exists. A route is supported only when the existing owner already has the required business semantics and safety contract.

If product acceptance requires an `UNSUPPORTED` operation, STOP and issue/review a separate bounded existing-owner extension; do not implement raw mutation inside R6.

- [ ] **Step 2: Add Task-3 RED cases before execution production edits**

Cover at minimum:

```python
def test_plan_without_separate_approval_cannot_execute(): ...
def test_approval_must_bind_exact_plan_and_candidate_hash(): ...
def test_replayed_expired_or_foreign_approval_fails_closed(): ...
def test_fresh_preflight_rejects_candidate_hash_drift(): ...
def test_fresh_preflight_rejects_newer_r5_or_r3_or_constraint_identity(): ...
def test_source_base_accepted_or_published_target_is_never_executable(): ...
def test_unsupported_plan_operation_fails_before_executor_call(): ...
def test_caller_cannot_forge_executor_capability_or_route(): ...
def test_headless_route_uses_existing_repair_owner_and_requires_second_review(): ...
def test_autocad_route_uses_existing_live_safety_owner_not_raw_mcp(): ...
def test_backup_or_preflight_failure_prevents_mutation(): ...
def test_partial_mutation_is_failure_evidence_only(): ...
def test_timeout_cleanup_or_uncertain_save_state_cannot_succeed(): ...
def test_failed_post_review_requires_existing_owner_rollback_evidence(): ...
def test_rollback_failure_is_terminal_and_not_promotion_safe(): ...
def test_late_executor_result_after_terminal_state_is_rejected(): ...
def test_result_contains_no_visual_pass_engineering_approval_promotion_or_publish_authority(): ...
def test_result_identity_excludes_backup_timestamp_path_and_volatile_handles(): ...
```

Use fake execution-boundary adapters that record calls. The fake must represent accepted existing-owner semantics; it must not become a test-only authorization bypass in production.

- [ ] **Step 3: Prove Task-3 meaningful RED and commit test-only**

Run the focused file. New execution cases must fail while Tasks 1-2 remain GREEN. Commit only the test path:

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
-> reject entire call if any operation unsupported or mixed route is unsafe
-> invoke the accepted existing executor/safety owner
-> require its backup/preflight/post-review/rollback/cleanup evidence as applicable
-> canonicalize a normalized R6 result envelope
-> return evidence only
```

There is no fallback from an unsupported headless operation to raw AutoCAD commands and no fallback from AutoCAD failure to a lower-level transport.

For current audited live semantics, the production integration must delegate to the accepted `cad_agent.live.repair_live`-equivalent owner so verified backup and second review remain outside R6. For current audited headless semantics, repair and review remain separate existing calls; R6 requires the second review result before returning a structurally successful execution status.

- [ ] **Step 5: Run focused R6 plus existing repair/live regressions**

At minimum include exact accepted successors of:

```text
dxf_builder_lib/tests/test_repair.py
dxf_builder_lib/tests/test_reviewer.py
tests/test_cad_agent_cli.py
mcp_integration_lib/tests/test_dotnet_ipc.py
relevant cad_agent.live tests discovered on accepted main
```

AutoCAD Mechanical live is NOT RUN in the first runtime slice. Existing unavailable-state tests may SKIP only for their documented prerequisite conditions.

- [ ] **Step 6: Run architecture anti-duplication checks**

Static checks must prove R6 production does not:

```text
import or call MCPClient entity mutation methods directly
import DotNetIPCClient for mutation
open/rewrite DWG/DXF itself
construct ezdxf entities
write manifest/checkpoint/revision/current state
assign visual PASS or engineering approval
invoke publisher/promote/replace-current APIs
implement retry-until-pass loops
compute SHA-256 with a new direct hash owner
create provider/App Server/CLI/MCP transport
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3 normally**

```powershell
git add cad_agent/repair_executor_adapter.py tests/test_cad_agent_repair_executor_adapter.py
git commit -m "feat: route approved repairs to existing executors"
```

---

### Task 4: Adversarial hardening, exact write-set verification, and hosted GREEN

**Files:**
- Modify only if new RED exposes a genuine R6 defect: `tests/test_cad_agent_repair_executor_adapter.py`, then `cad_agent/repair_executor_adapter.py` after meaningful RED.
- No third path.

**Interfaces:**
- Consumes: Tasks 1-3 final exact head.
- Produces: final reviewable R6 runtime head with deterministic/fail-closed evidence; still no promotion/publication authority.

- [ ] **Step 1: Add adversarial cases that cross task boundaries**

Before any final hardening production change, test at least:

```text
R5 FAIL is valid but belongs to an older R4 mutation generation
R3 stable entity exists but moved to a different component/view revision
same plan bytes paired with another candidate revision
approval matches plan ID but not canonical plan hash
caller supplies duplicate/conflicting operation targets
multiple operations touch one protected anchor indirectly
complete plan contains one supported and one unsupported operation
executor reports repaired_count but post-hash is unchanged/unexpected
executor reports success while cleanup or rollback evidence is malformed
worker returns a schema-valid plan containing stale target drawing SHA
provider output contains a private path/secret sentinel
executor exception contains a private path/command sentinel
reordered set-like impacts/anchors produce identical identity
content mutation under same caller ID changes identity
```

Test-only RED first for every newly discovered missing behavior.

- [ ] **Step 2: Run the focused suite repeatedly**

Run all R6 tests at least five consecutive times. No intermittent ordering/time/path failures are acceptable.

- [ ] **Step 3: Run broader accepted R3/R4/R5/Wave-1A/repair regressions**

The runtime Issue must list exact rebaselined paths before execution. Required domains:

```text
R3 registry identity/freshness
R4 candidate/revision immutability and stale behavior
R5 visual verdict/freshness
Wave 1A worker/provider attestation/lifecycle
visual repair-plan contracts
protected dimensions / Drawing Setup / Dimension Pilot
headless review/repair
live repair backup/rollback
manifest/checkpoint/resume compatibility
```

Any unresolved failing upstream regression blocks R6; do not weaken tests.

- [ ] **Step 4: Run canonical verifier**

Run:

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Expected for offline R6 acceptance: canonical verification completes successfully; AutoCAD .NET is literal NOT RUN because of the explicit skip; private/real-data and AutoCAD unavailable probes retain their repository-defined SKIP semantics.

A future separately authorized live acceptance must run through the local AutoCAD lane against disposable fixtures and is not implied by offline GREEN.

- [ ] **Step 5: Run exact Ruff, architecture, reuse, and diff gates**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check `
  cad_agent/repair_executor_adapter.py `
  tests/test_cad_agent_repair_executor_adapter.py

.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check `
  --repo-root . `
  --baseline contracts/reuse-integration/architecture-boundaries.json

git diff --check <R6-EXACT-BASE>...HEAD
```

`<R6-EXACT-BASE>` must be replaced in the future issued runtime task with the fresh Master-PO-supplied SHA before any write. A literal placeholder must never survive into an executing command.

- [ ] **Step 6: Audit cumulative changed paths**

Expected exactly:

```text
cad_agent/repair_executor_adapter.py
tests/test_cad_agent_repair_executor_adapter.py
```

Any third path is `R6 REBASELINE REQUIRED`.

- [ ] **Step 7: Open a DRAFT PR and verify hosted exact-head/current-main synthetic**

The PR body must include the eight literal Reuse Declaration fields:

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

Hosted gates must include:

```text
tests: SUCCESS
reuse-declaration: SUCCESS
exact checkout/synthetic identity observed
no unresolved reviewer blocker hidden by SKIP/NOT RUN
```

Do not mark ready, self-review, or merge.

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

`FAIL` means it executed and contradicted the contract; do not relabel as a flaky/non-gating result without evidence and Master PO disposition.

`SKIP` is only an explicitly coded optional/unavailable-state test outcome.

`NOT RUN` means the operation was not executed, including first-slice real provider, private/customer CAD, AutoCAD Mechanical live, and publication.

Hosted offline GREEN does not convert AutoCAD live or real-provider execution into PASS.

## Migration and Rollback

R6 adds no schema/store/data migration. Existing `repair-plan-1.0`, visual-review, manifest, repair, backup, and AutoCAD transport owners stay intact.

Runtime rollback is a normal revert/removal of the two adjacent R6 paths. Existing legacy headless and mechanical repair commands remain usable under their existing contracts.

A candidate that was actually mutated during a separately authorized live pilot is restored/retained according to the existing repair/revision owners; reverting R6 source code is not a substitute for CAD rollback evidence.

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