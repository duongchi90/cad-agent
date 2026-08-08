# R6 Repair Executor Adapter Design

Status: planning-only design under Issue #136. This document does not authorize R6 runtime implementation, model/provider calls, AutoCAD mutation, private/customer CAD, schema changes, dependency changes, or publication.

Date: 2026-08-09

Issue: #136 — `[Acceleration][Planning] R6 Repair Executor Adapter executable design and runtime plan`

Exact planning base: `b217ebfd597260d7b59badc3ffbcfbe7b1139754`

Planning branch: `planning/issue-136-r6-repair-executor-adapter`

Planning write-set: this file plus `docs/superpowers/plans/2026-08-09-r6-repair-executor-adapter.md` only.

## 1. Decision summary

R6 is one **thin repair-planning and executor-routing adapter** around accepted owners. It does not become a CAD mutation engine, a second repair executor, a revision store, a visual-verdict owner, an approval issuer, or a publisher.

The accepted program design resolves the Issue #136 scope question. Its P8 workstream is explicitly **“Codex repair planning and existing executor adapter”** and says validated findings are converted into a protected schema-bound repair plan while existing repair executors apply only approved operations to a disposable candidate. The older reuse-first architecture makes the same separation explicit: the Codex Repair Planner produces a closed plan, then `RepairExecutorAdapter` translates an approved plan into existing repair APIs and must not implement another repair engine.

Therefore R6 contains both responsibilities, but keeps their authorities separate:

1. **Planning adapter:** assemble bounded, server-owned repair context; invoke the accepted official worker/provider seam; validate the untrusted result against the existing `repair-plan-1.0` contract; bind it to the exact candidate/evidence context.
2. **Executor router:** after a separate approval gate and a fresh identity/preflight check, route only exact supported plan operations to an already accepted repair executor. R6 itself never emits raw DXF entities, AutoCAD commands, File IPC requests, or geometry mutations.

No `R6 SCOPE GAP — MASTER PO DECISION REQUIRED` is needed for this scope decision. Runtime still requires a fresh rebaseline because R3/R4/R5 and Wave 1A #113 are moving planning/runtime seams at the time of this design.

## 2. Authority model

The authority chain is:

```text
accepted R5 FAIL evidence
+ accepted R4 disposable candidate revision identity
+ accepted R3 component/view impact identity
+ protected engineering/dimension constraints
        |
        v
R6 planner context binding
        |
        v
accepted official worker/provider seam
        |
        v
UNTRUSTED repair-plan candidate
        |
        v
existing repair-plan validator + R6 cross-binding
        |
        v
separate server-owned approval
        |
        v
fresh candidate/evidence/preflight validation
        |
        v
R6 exact-capability route selection
        |
        v
existing headless or AutoCAD repair owner
        |
        v
fresh repair evidence / backup / post-review / cleanup
        |
        v
R4/R5 later re-verification and revision decision
```

R6 may report what was planned, routed, attempted, repaired, refused, rolled back, or left unresolved. It cannot assign visual `PASS`, engineering approval, revision promotion, “current” state, publication eligibility, or final release status.

## 3. Accepted evidence resolving the scope

### 3.1 Program design

`docs/superpowers/specs/2026-08-06-accelerated-reuse-first-program-design.md` is the strongest accepted scope authority. It defines:

- P8 as `Codex repair planning and existing executor adapter`;
- schema-bound repair planning from validated visual/engineering findings;
- application only through existing repair executors;
- mutation only against disposable candidates;
- Wave 4 as P8 plus the integrated closed-loop disposable-candidate flow.

This places bounded repair planning inside R6 while preserving executor separation.

### 3.2 Reuse-first reconstruction design

`docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md` defines separate internal responsibilities:

- Visual Supervisor emits findings/verdict and never edits the DWG;
- Codex Repair Planner produces a closed Repair/Transformation Plan and cannot self-approve, promote, or publish;
- `RepairExecutorAdapter` translates an **approved** plan into existing repair APIs and cannot implement a new repair engine;
- every applied change creates fresh candidate/evidence state rather than overwriting accepted history.

R6 follows that separation inside one bounded subsystem.

## 4. Reuse map

| Capability | Current owner / exact seam on planning base | R6 classification | R6 rule |
| --- | --- | --- | --- |
| Closed repair-plan contract | `contracts/visual-supervisor/repair-plan.schema.json` | `REUSE_AS_IS` | Do not create a second repair-plan schema. |
| Repair-plan validation | `cad_agent.visual_contracts.validate_visual_contract(..., contract="repair_plan")` | `REUSE_AS_IS` | Provider output remains untrusted until this validator passes. |
| Visual FAIL / repair intent structure | `cad_agent.visual_contracts` visual-review validation | `EXTEND_WITH_ADAPTER` | Consume only accepted future R5 FAIL evidence; R6 does not mint visual verdicts. |
| Headless primitive/component repair | `dxf_builder_lib.repair.repair_dxf`, `repair_insert_components` | `REUSE_AS_IS` | Route only when an exact current repair semantic matches. Do not copy redraw logic. |
| Headless review | `dxf_builder_lib.reviewer.review_dxf` | `REUSE_AS_IS` | Second review remains separate from repair. |
| AutoCAD repair primitive | `mcp_integration_lib.repair2.repair_dxf_live` | `REUSE_AS_IS` | Never issue raw MCP commands from R6. |
| Live safety, backup, second review, rollback | `cad_agent.live.repair_live` | `REUSE_AS_IS` | Preserve pre-review, verified backup, post-review, save-or-rollback behavior. |
| Mechanical operator gate | `cad_agent.cli._mechanical_repair_command` | `REUSE_AS_IS` | Existing literal APPLY + approval-reference semantics remain authoritative for that path. |
| File IPC / .NET dispatcher | `mcp_integration_lib.mcp_client`, `mcp_integration_lib.dotnet_ipc`, AutoCAD plugin dispatcher | `REJECT_DUPLICATE_OWNER` | R6 must never create another transport/dispatcher. |
| Proposal/apply separation | `agent_lib.run._validate_agent_action_approval`, `_apply_report_with_approval`, `agent_lib.batch_agent.apply_agent_report` | `REUSE_AS_IS` | Planning and application are distinct authority events. |
| Worker/provider control | accepted future Wave 1A official worker seam | `EXTEND_WITH_ADAPTER` after fresh rebaseline | Do not assume moving #113 symbols. No second SDK/App Server/CLI/MCP transport. |
| Manifest/checkpoint/resume | `cad_agent.manifest` and accepted run lifecycle owners | `REUSE_AS_IS` | R6 returns evidence to the owner; it does not persist a parallel run store. |
| Canonical JSON hashing | `cad_agent.drawing_contracts.canonical_json_sha256` | `REUSE_AS_IS` | No direct `hashlib` or alternate serializer in R6 identity code. |
| Drawing setup / protected dimensions | `cad_agent.drawing_setup`, `cad_agent.dimension_pilot`, visual dimension-register contracts | `REUSE_AS_IS` | Confirmed DRIVING/protected constraints are immutable unless a separate engineering authority changes them. |
| Candidate revision lineage | accepted future R4 owner | `REUSE_AS_IS` after fresh rebaseline | R6 cannot create/select/promote revision truth. |
| Component/view graph | accepted future R3 owner | `REUSE_AS_IS` after fresh rebaseline | R6 consumes impacts; it does not create a registry. |
| Independent visual verdict | accepted future R5 owner | `REUSE_AS_IS` after fresh rebaseline | R6 consumes validated FAIL evidence and cannot issue PASS. |
| Codex repair planning orchestration | none complete on accepted reuse inventory | `NEW_MISSING_CAPABILITY` | This is the genuine R6 planning gap. |
| Plan-to-existing-executor routing | no complete cross-owner adapter | `NEW_MISSING_CAPABILITY` | Thin routing only; no mutation implementation. |

## 5. Existing repair semantics are narrower than the repair-plan enum

The existing `repair-plan-1.0` contract permits operations such as `MOVE_COMPONENT`, `ALIGN_COMPONENT`, `REPLACE_POLYLINE_SEGMENT`, `ADJUST_ARC`, `ADD_MISSING_FEATURE`, and native-dimension repair. That enum does **not** prove the current headless/live executors support every operation as a stable business operation.

Current repair owners are intentionally narrower:

- `dxf_builder_lib.repair` repairs known review mismatches by deleting/recreating entities from the existing `BuildResult` written-geometry evidence;
- `mcp_integration_lib.repair2` similarly repairs known live primitive mismatches through existing MCP operations;
- `cad_agent.live.repair_live` owns the safety sequence around live repair, not arbitrary free-form plan interpretation.

R6 therefore requires an **exact operation-capability map** at runtime rebaseline. A plan operation may be routed only when an accepted existing executor has a semantically exact entry point with the required safety evidence. R6 may not translate an unsupported operation into lower-level geometry or AutoCAD commands merely to make it executable.

Required fail-closed result for an unmapped operation is categorical `UNSUPPORTED_REPAIR_OPERATION`. If product acceptance requires a currently unsupported business operation, Master PO must issue a separate bounded extension to the existing repair owner/dispatcher, or rebaseline R6. It is not silently implemented inside R6.

## 6. R6 inputs

The final accepted symbols are deliberately unresolved until upstream rebaseline. The semantic inputs are fixed:

### 6.1 Validated R5 failure evidence

R6 requires a closed accepted R5 result whose verdict is exactly `FAIL`. `PASS` is non-repairing. `NEEDS_HUMAN` is not executable repair authority and remains outside automatic planning unless a later accepted contract explicitly converts it to a new FAIL decision.

R6 binds at minimum:

- run identity;
- review/verdict identity and canonical hash;
- candidate mutation/drawing hash observed by the review;
- affected regions/views/sheets;
- findings and severity;
- repair intent change/preserve lists;
- required measurements / missing evidence state;
- evidence freshness identity.

### 6.2 R4 candidate revision identity

R6 requires an accepted disposable candidate identity with at minimum:

- candidate/revision identity;
- exact current drawing hash;
- immutable parent/source lineage;
- mutation generation/evidence generation;
- state proving the target is a candidate, not source/base/accepted/published material.

R6 cannot mint or persist these fields.

### 6.3 R3 component/view impacts

R6 consumes the accepted registry’s stable logical references needed to resolve:

- component IDs;
- view/sheet/region IDs;
- stable entity/block references where available;
- linked-view impact set;
- affected dimensions/constraints/layouts;
- provenance links.

Volatile AutoCAD handles alone are never plan identity.

### 6.4 Protected engineering constraints

The server-owned constraint input identifies protected datums, confirmed DRIVING dimensions, critical constraints, preserved anchors, and any accepted calibration/datum mapping.

A repair requested only to increase pixel similarity cannot change a confirmed DRIVING/protected dimension. A free-form pixel offset cannot become a model-space movement unless an accepted datum/calibration transform explicitly authorizes that mapping.

## 7. Planner boundary

R6 constructs a minimized deterministic planner request from the four input groups above. The request contains only bounded IDs, normalized evidence references, operation allowlist, protected constraints, and the immutable `repair-plan-1.0` schema snapshot/identity required by the accepted worker seam.

The accepted official worker/provider boundary is responsible for model execution. R6 does not import or create a second SDK/App Server/CLI/MCP transport.

The worker result is treated as hostile input. R6 must:

1. reject missing/partial/malformed output;
2. validate it with the existing repair-plan validator;
3. require `source_review_id` and `run_id` to match server-owned R5 context;
4. require `target_drawing_sha256` to match the exact current R4 candidate hash;
5. require every affected region/target/reference to exist in accepted R3 scope;
6. require preserve anchors and constraint references to be a subset of server-owned allowed/protected context;
7. reject any operation requiring an absent datum/calibration mapping;
8. reject any operation that conflicts with confirmed DRIVING/protected constraints;
9. canonical-hash the normalized adapter envelope using the existing hash owner;
10. emit no approval or mutation authority.

Provider-generated IDs are lookup/evidence fields only; they never replace the server-owned candidate/evidence identities.

## 8. Approval boundary

A valid repair plan is **not executable authority**.

Execution requires a separate server-owned approval record/reference bound to the exact:

- normalized repair-plan hash;
- target candidate/revision identity and current drawing hash;
- source R5 FAIL identity;
- allowed operation set;
- protected constraints;
- expiry/single-use/freshness state required by the accepted approval owner.

R6 reuses the accepted proposal/apply separation pattern. A plan produced by Codex cannot approve itself, and a worker/provider approval callback is never sufficient.

If the final accepted approval owner cannot bind the required identities without a schema/store change, runtime must stop with `R6 REBASELINE REQUIRED` rather than creating a second approval record owner.

## 9. Fresh preflight before mutation

Immediately before routing any operation, R6 must re-read or be supplied fresh server-owned evidence from accepted owners and prove:

- target remains the same disposable R4 candidate;
- current candidate drawing hash equals the approved target hash;
- R3 component/view impact identity is unchanged;
- R5 FAIL evidence still refers to the current mutation generation;
- protected constraints/DRIVING dimensions have not changed;
- approval is current and bound to this exact plan/candidate;
- selected executor capability remains available;
- required live session/File IPC/DBMOD/path/backup prerequisites are fresh when the selected owner is AutoCAD-backed.

Any mismatch fails before mutation with `STALE_REPAIR_CONTEXT` or a more specific categorical code.

No prior inspection, previous run ID, stale HWND, stale handle, or old plan permits a later mutation.

## 10. Executor routing

R6 chooses only among accepted executor capabilities. It does not expose a raw “command” or “geometry” route.

Conceptual route classes are:

```text
HEADLESS_EXISTING_REPAIR
AUTOCAD_EXISTING_REPAIR
UNSUPPORTED
```

The final exact map from repair-plan operation to route must be established by a fresh runtime rebaseline and frozen in tests. `UNSUPPORTED` is a valid fail-closed result.

For the headless route, R6 preserves the current repair/review separation and requires a fresh post-repair `review_dxf` before the result can be considered structurally successful.

For the AutoCAD route, R6 reuses `cad_agent.live.repair_live` or its accepted successor so that backup, pre-review, verified source/backup hashes, mutation, post-review, save-or-rollback, and backup reopen verification remain owned by the existing live safety boundary.

R6 must not call `MCPClient.entity_*`, `DotNetIPCClient` mutation operations, or plugin dispatcher methods directly.

## 11. Candidate-only mutation and immutability

R6 execution is permitted only when upstream R4 proves the target is a disposable candidate.

Always immutable to R6:

```text
source evidence
exact base CAD / Xref source
accepted CAD
published CAD
previous immutable revisions
```

If a caller supplies a source/base/accepted/published target or a path without a server-owned candidate identity/hash, execution fails before selecting an executor.

R6 does not copy a candidate over “current”, rename an accepted file, update revision truth, or perform publication replacement. Those belong to R4/R7.

## 12. Repair result evidence

R6 returns an immutable normalized evidence envelope, not a verdict or revision mutation. It includes only facts available from accepted owners, such as:

- adapter version;
- repair-plan hash;
- source R5 failure hash;
- target R4 candidate identity and pre-hash;
- R3 impact identity;
- protected-constraint identity;
- approval identity/reference hash where safe;
- selected existing executor class/operation identity;
- backup identity/evidence when the selected owner provides it;
- pre-review/preflight evidence identity;
- executed/skipped/refused operation IDs;
- existing executor result identity;
- post-hash and post-review evidence identity;
- rollback state/evidence;
- cleanup/session state;
- categorical terminal status.

The envelope’s deterministic identity is computed with `cad_agent.drawing_contracts.canonical_json_sha256`. It excludes ambient timestamps, filesystem enumeration order, random UUIDs, private paths, raw provider text, exception text, and transport-specific volatile identifiers unless an accepted owner requires them solely as evidence outside canonical identity.

R6 never labels the result `VISUAL_PASS`, `ENGINEERING_APPROVED`, `PROMOTED`, or `PUBLISHED`.

## 13. Failure and rollback semantics

Required categorical outcomes include:

- `R6_INPUT_INVALID`
- `VISUAL_FAIL_REQUIRED`
- `STALE_REPAIR_CONTEXT`
- `CANDIDATE_IDENTITY_MISMATCH`
- `REPAIR_PLAN_INVALID`
- `REPAIR_PLAN_TARGET_MISMATCH`
- `REPAIR_TARGET_OUT_OF_SCOPE`
- `PROTECTED_CONSTRAINT_VIOLATION`
- `DATUM_MAPPING_REQUIRED`
- `APPROVAL_REQUIRED`
- `APPROVAL_MISMATCH`
- `UNSUPPORTED_REPAIR_OPERATION`
- `EXECUTOR_UNAVAILABLE`
- `REPAIR_EXECUTION_FAILED`
- `PARTIAL_MUTATION_REJECTED`
- `ROLLBACK_FAILED`
- `CLEANUP_FAILED`
- `LATE_RESULT_REJECTED`
- `WORKER_ATTESTATION_GAP`

Errors are privacy-safe and categorical. Raw customer paths, source content, prompt text, provider output, command lines, secrets, AutoCAD exception text, and unredacted IPC payloads must not be copied into public failures.

If an executor reports partial mutation, timeout, cleanup failure, uncertain save state, or unverifiable rollback, R6 returns failure evidence only. It cannot promote or retry autonomously.

## 14. Retry and iteration ownership

R6 performs one approved planning/execution attempt per call. It does not own an unbounded “repair until PASS” loop.

Iteration count, candidate supersession, retry budget, best-candidate choice, and repeated-failure policy belong to the accepted R4 orchestration/revision owner. Fresh R5 evidence is required before another repair decision.

R6 must ignore late worker/executor output after cancellation/timeout or after the attempt has reached a terminal failure state.

## 15. Proposed runtime public surface

After fresh R6 rebaseline, prefer one adjacent module:

`cad_agent/repair_executor_adapter.py`

and exactly these two public operations:

```python
prepare_repair_plan(
    *,
    visual_failure,
    candidate_revision,
    component_view_impacts,
    protected_constraints,
    worker_boundary,
) -> dict[str, object]

execute_approved_repair(
    *,
    repair_plan,
    approval,
    candidate_revision,
    component_view_impacts,
    protected_constraints,
    execution_boundary,
) -> dict[str, object]
```

The concrete accepted upstream types are resolved at runtime issuance. Until then the semantic inputs above are authoritative and no moving R3/R4/R5/#113 symbol is invented.

The module may expose one categorical `R6RepairError` and one adapter version constant if the final runtime Issue explicitly includes them in the closed public surface. Internal worker/execution protocols are test seams only and are not new transports or authority owners.

No public “raw operation”, “raw MCP”, “run command”, “write DXF”, “promote revision”, “visual verdict”, or “publish” API is allowed.

## 16. Proposed minimal runtime write-set

Preferred cumulative R6 runtime write-set after rebaseline:

```text
CREATE:
  cad_agent/repair_executor_adapter.py
  tests/test_cad_agent_repair_executor_adapter.py

MODIFY:
  NONE
```

The same two paths may be extended through forward TDD tasks. This is deliberately adjacent to existing owners so R6 can orchestrate them without changing them for convenience.

A need to change any of the following is a STOP/rebaseline condition, not implicit R6 scope:

- `dxf_builder_lib/repair.py`
- `mcp_integration_lib/repair2.py`
- `mcp_integration_lib/mcp_client.py`
- `mcp_integration_lib/dotnet_ipc.py`
- `autocad_plugin/**`
- `cad_agent/live.py`
- `cad_agent/manifest.py`
- `cad_agent/visual_contracts.py`
- `contracts/visual-supervisor/repair-plan.schema.json`
- moving R3/R4/R5 modules/contracts
- `agent_lib/**` worker/provider owners
- dependencies, lock files, workflows, or schemas.

If a genuine accepted executor gap requires one of those paths, split it into a separate bounded owner-extension Issue before or alongside a rebaselined R6 task.

## 17. Determinism rules

R6 deterministic identities reuse the existing canonical hash owner and sort/normalize all set-like evidence before hashing. Identity must not depend on:

- input list order where semantics are unordered;
- random/UUID generation;
- wall clock/timezone;
- raw filesystem path spelling;
- AutoCAD volatile handle when a stable R3 entity/component identity exists;
- raw provider thread/turn IDs;
- raw exception/provider/IPC text;
- backup filename timestamp;
- caller-selected labels that are not accepted authority.

Content or accepted authority identity changes must change the corresponding plan/request/result identity.

## 18. Security invariants

R6 must prove all of the following before runtime acceptance:

- no source/base/accepted/published mutation;
- no second CAD repair engine;
- no direct AutoCAD/File IPC mutation from R6;
- no second provider transport;
- no second approval/verdict/revision/publisher owner;
- no path-only or handle-only authority;
- no pixel-space free-form mutation without accepted mapping;
- protected/DRIVING dimensions preserved;
- no stale R3/R4/R5/approval evidence use;
- no caller-minted executor capability;
- no provider self-approval;
- unsupported operation fails closed;
- partial mutation/timeout/cleanup/rollback uncertainty cannot be promoted;
- fresh evidence is required after every successful repair before any later R4/R5 decision.

## 19. Compatibility and migration

R6 is additive orchestration. It does not migrate existing DXF, DWG, manifest, repair-plan, visual-review, or approval records.

Existing legacy mechanical/headless repair commands remain unchanged and authoritative for their current use cases. R6 consumes them only through accepted internal seams.

Rollback of R6 runtime is removal/revert of the adjacent adapter/test paths. No persisted schema or data rewrite is required.

## 20. Upstream dependency and rebaseline gates

R6 runtime remains blocked until Master PO verifies final accepted seams for all required dependencies:

1. R1 Source Bundle/Fusion accepted/merged;
2. R2 Base CAD Adapter accepted/merged where base-CAD provenance is relevant;
3. R3 Component/View Registry accepted/merged;
4. R4 Candidate Revision Orchestrator accepted/merged;
5. R5 Visual Supervisor Adapter accepted/merged;
6. official Wave 1A worker/provider boundary required for Codex repair planning accepted/merged;
7. existing repair owners and live safety owners still provide the audited semantics;
8. exact repair-plan contract/validator remains compatible;
9. exact operation-capability routing map is proven;
10. Master PO issues a fresh exact R6 runtime base/write-set.

Any material mismatch yields `R6 REBASELINE REQUIRED`.

## 21. Review topology

Every R6 runtime slice requires paired independent review:

- **Security/authority reviewer:** stale evidence, protected constraints, candidate immutability, approval separation, unsupported-operation fail-closed behavior, no second transport/executor/verdict/revision/publisher owner.
- **Integration/CI reviewer:** exact base/head/synthetic, write-set, TDD RED-first chronology, hosted CI, reuse declaration, current-main compatibility, executor regression coverage, truthful PASS/FAIL/SKIP/NOT RUN.

Neither reviewer self-merges or edits the writer branch.

## 22. Planning acceptance

This planning task is complete only when:

- exactly the two Issue #136 planning documents exist in the diff;
- this scope resolution is explicit;
- the runtime plan is executable without assuming moving upstream API names;
- the reuse map names existing repair/approval/transport/rollback/hash owners;
- the proposed runtime does not create a second repair executor or CAD mutation path;
- hosted `tests` and `reuse-declaration` are GREEN on the final planning head/current-main PR synthetic;
- the PR remains DRAFT and the writer stops repository writes.

Issue #123 remains frozen throughout this planning lane unless Master PO explicitly preempts R6 after exact hosted RED becomes observable.