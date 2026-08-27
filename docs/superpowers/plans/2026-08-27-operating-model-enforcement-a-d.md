# CAD Agent Operating Model Enforcement A-D Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved operating-model enforcement layers that keep SOL/Web responsible for all Web-capable work, reserve Luna for machine-required work, reuse exact evidence, and convert repeated execution failures into deterministic probes.

**Architecture:** Add pure-Python, no-network governance helpers under the existing thin `cad_agent` orchestration owner. Inputs are explicit snapshots of already-fresh-read GitHub/control evidence; helpers never fetch GitHub, mint authority, authorize mutation, or create a second truth store. Reuse the accepted semantics from PRs #262/#263/#265/#266 rather than inventing parallel currentness logic.

**Tech Stack:** Python 3.11, stdlib only, existing `cad_agent.drawing_contracts.canonical_json_sha256`, pytest/unittest-compatible pure tests, existing Ruff/architecture/reuse/hosted verification.

**Spec:** `docs/superpowers/specs/2026-08-27-operating-model-enforcement-design.md`

## Global Constraints

- Authority remains `Human Owner > CONTROL_WRITER_SOL > Local Solo Executor`.
- GitHub remains canonical; all produced state is derived evidence only.
- `CONTROL_SEQ` mint/supersession is forbidden to repository helpers.
- No AutoCAD, COM, ROT, UI, NETLOAD, File-IPC live action, provider action, private/customer CAD, publication, or persistent system mutation in Slices A-D.
- No new external service, database, daemon, webhook, message bus, hidden agent store, second manifest/checkpoint/revision/currentness owner, second AutoCAD transport, or publisher.
- `WEB_CAPABLE` work cannot be delegated to Luna merely to save SOL tokens.
- `SKIP` and `NOT_RUN` never satisfy a required PASS gate.
- Accepted PASS evidence is reusable only under explicit exact-identity rules.
- Auto-merge is out of scope and deferred.
- Active R8-D/#284/#285 exact-main work must not be disturbed; implementation remains on `governance/operating-model-enforcement` until a separate fresh merge disposition.

## Reuse map locked before implementation

- PR #266: reuse the fail-closed currentness banners and `test_authority_currentness_contract.py` semantics for `docs/AI_OPERATING_MODEL.md` and `docs/HANDOFF.md`.
- PR #265: reuse the `docs/STATUS.md` historical-ledger banner semantics exactly in substance.
- PR #263: reuse the separation between material state projection/fingerprint, authority resolution, task identity, deterministic transition/currentness handling, and `UNMAPPED_MATERIAL_DIFF` fail-closed behavior. Do not implement a scheduler/watchdog in A-D.
- Existing owner: `cad_agent.drawing_contracts.canonical_json_sha256` remains the canonical JSON SHA-256 helper.
- Existing architecture ratchet: filenames must not combine reserved duplicate-owner terms and new code must not import AutoCAD transport owners.

---

### Task 1: Slice A RED — currentness and startup snapshot contract

**Files:**
- Create: `tests/test_cad_agent_control_snapshot.py`
- Create: `tests/test_authority_currentness_contract.py`

**Interfaces:**
- Consumes: explicit Python mappings representing fresh GitHub/control observations.
- Produces requirements for future `cad_agent.control_snapshot.build_control_snapshot(...)` and `validate_control_snapshot(...)`.

- [ ] **Step 1: Add causal tests for deterministic snapshot identity**

Test contract:

```python
from cad_agent.control_snapshot import build_control_snapshot, validate_control_snapshot


def test_generated_at_does_not_change_state_identity():
    first = build_control_snapshot(_observation(), generated_at="2026-08-27T10:00:00Z")
    second = build_control_snapshot(_observation(), generated_at="2026-08-27T10:01:00Z")
    assert first["state_sha256"] == second["state_sha256"]
    assert first["generated_at"] != second["generated_at"]


def test_snapshot_requires_exact_source_references():
    observation = _observation()
    observation["authority_comment_id"] = None
    with pytest.raises(ControlSnapshotError, match="authority_comment_id"):
        build_control_snapshot(observation, generated_at="2026-08-27T10:00:00Z")
```

Also cover exact 40-char lowercase Git SHA, integer positive CONTROL_SEQ/comment IDs, closed terminal/owner strings, sorted unique locks/reuse refs, and rejection of extra fields.

- [ ] **Step 2: Add stale-doc currentness tests by reusing PR #265/#266 semantics**

The test reads the first 40 lines of `docs/AI_OPERATING_MODEL.md`, `docs/HANDOFF.md`, and `docs/STATUS.md` and requires explicit language that they are historical/not-live for mutable state, routes fresh reads to Issue #131 and actual current `main`, and denies scheduler/merge/live authority.

- [ ] **Step 3: Push RED-only commit and verify hosted causal failure**

Expected: import failure for `cad_agent.control_snapshot` plus currentness assertion failures on current main-derived docs. Reuse/architecture should remain PASS because production is unchanged.

---

### Task 2: Slice A GREEN — pure startup snapshot + documentation currentness

**Files:**
- Create: `cad_agent/control_snapshot.py`
- Modify: `docs/AI_OPERATING_MODEL.md`
- Modify: `docs/HANDOFF.md`
- Modify: `docs/STATUS.md`
- Test: `tests/test_cad_agent_control_snapshot.py`
- Test: `tests/test_authority_currentness_contract.py`

**Interfaces:**
- `build_control_snapshot(observation: Mapping[str, object], *, generated_at: str) -> dict[str, object]`
- `validate_control_snapshot(snapshot: Mapping[str, object]) -> dict[str, object]`
- `ControlSnapshotError(ValueError)`

- [ ] **Step 1: Implement closed observation fields**

Required observation fields:

```text
standing_model_comment_id
persistence_comment_id
control_seq
authority_comment_id
consumed_terminal_id
terminal_classification
next_owner
current_main_sha
current_main_tree_sha
active_issue
active_pr
active_pr_base_sha
active_pr_head_sha
active_pr_state
repo_write_allowed
live_allowed
locks
reused_pass_evidence
first_unsatisfied_gate
source_refs
```

`active_*` PR fields may be literal `NONE` as one closed no-PR state. No timestamps belong to canonical state material.

- [ ] **Step 2: Implement deterministic state hash using existing owner**

```python
state_sha256 = canonical_json_sha256(state_fields)
```

`generated_at` is appended after hashing. `validate_control_snapshot` recomputes and requires exact equality.

- [ ] **Step 3: Reuse accepted currentness banners**

Apply the accepted substance of PR #266 to `docs/AI_OPERATING_MODEL.md` and `docs/HANDOFF.md`; apply PR #265 substance to `docs/STATUS.md`. Preserve all historical content below the banner.

- [ ] **Step 4: Run focused/architecture verification**

Expected focused tests PASS, Ruff PASS, architecture boundaries PASS, diff check PASS.

---

### Task 3: Slice B RED — SOL/Luna work routing contract

**Files:**
- Create: `tests/test_cad_agent_work_routing.py`

**Interfaces:**
- Future `cad_agent.work_routing.classify_work(action: Mapping[str, object]) -> dict[str, str]`
- Closed classes: `WEB_CAPABLE`, `LOCAL_REPO_REQUIRED`, `LOCAL_WINDOWS_REQUIRED`, `LOCAL_AUTOCAD_REQUIRED`, `HUMAN_ONLY`.

- [ ] **Step 1: Add deterministic classification matrix**

Representative cases:

```text
GitHub diff/CI/review read -> WEB_CAPABLE
architecture/reuse/security/root-cause analysis -> WEB_CAPABLE
local unpushed checkout byte inspection -> LOCAL_REPO_REQUIRED
Windows-only build/toolchain evidence -> LOCAL_WINDOWS_REQUIRED
AutoCAD/COM/ROT/UI/NETLOAD/live File-IPC -> LOCAL_AUTOCAD_REQUIRED
owner product preference/private secret/irreversible approval -> HUMAN_ONLY
```

- [ ] **Step 2: Add anti-offload tests**

A request with only Web-capable requirements plus `preferred_executor=LUNA` must still return `WEB_CAPABLE`. Missing reason/evidence surface for a `LOCAL_*` classification must fail closed.

- [ ] **Step 3: Push causal RED**

Expected: missing module/API only.

---

### Task 4: Slice B GREEN — work router

**Files:**
- Create: `cad_agent/work_routing.py`
- Test: `tests/test_cad_agent_work_routing.py`

**Interfaces:**
- `classify_work(action: Mapping[str, object]) -> dict[str, str]`
- `WorkRoutingError(ValueError)`

- [ ] **Step 1: Implement closed capability requirement flags**

Input shape:

```text
requires_unpushed_local_state: bool
requires_windows_toolchain: bool
requires_autocad: bool
requires_com_rot_ui: bool
requires_netload: bool
requires_live_file_ipc: bool
requires_owner_decision: bool
requires_private_secret: bool
requires_irreversible_approval: bool
web_capable_analysis: bool
reason: str
```

Precedence: HUMAN_ONLY > LOCAL_AUTOCAD_REQUIRED > LOCAL_WINDOWS_REQUIRED > LOCAL_REPO_REQUIRED > WEB_CAPABLE. A local classification requires at least one matching true capability flag; preference alone cannot elevate it.

- [ ] **Step 2: Verify routing matrix and architecture**

No filesystem/network/process/AutoCAD imports.

---

### Task 5: Slice B RED — long-horizon mission contract

**Files:**
- Create: `tests/test_cad_agent_mission_contract.py`

**Interfaces:**
- Future `compile_local_mission(...)` and `validate_local_mission(...)` in `cad_agent.mission_contract`.

- [ ] **Step 1: Add valid mission fixture**

Required closed fields include goal/outcome, authority/source refs, exact tuple, write-set/forbidden paths, routing class, reuse receipts, pre-execution closure, causal family/budget, temp repair envelope, live/expensive budgets, acceptance oracle, hard handoff conditions, cleanup/parity, terminal schema, and `NEXT_OWNER=SOL`.

- [ ] **Step 2: Add fail-closed cases**

Reject:

```text
WEB_CAPABLE mission delegated to Luna
repo mutation with empty write_set
live budget > 0 when live_allowed is false
merge/publication authority implied by mission
human relay required for routine gate
causal budget < 1 or > 5 in default contract
reused PASS without source evidence reference
main/base/head contradiction against supplied control snapshot
missing cleanup/parity terminal requirements
```

- [ ] **Step 3: Push causal RED**

Expected: missing module/API only.

---

### Task 6: Slice B GREEN — mission compiler/validator

**Files:**
- Create: `cad_agent/mission_contract.py`
- Test: `tests/test_cad_agent_mission_contract.py`

**Interfaces:**
- `compile_local_mission(control_snapshot: Mapping[str, object], routing: Mapping[str, str], request: Mapping[str, object]) -> dict[str, object]`
- `validate_local_mission(mission: Mapping[str, object], *, control_snapshot: Mapping[str, object]) -> dict[str, object]`
- `MissionContractError(ValueError)`

- [ ] **Step 1: Implement pure closed-schema compiler**

The compiler copies authority/currentness only from validated snapshot input and refuses caller override of CONTROL_SEQ, authority comment, current main, or next owner.

- [ ] **Step 2: Implement long-horizon constraints**

Default `causal_budget=5`; terminal only on standing hard boundaries or completion; local temp helper/harness repair envelope is explicit and cannot expand repo/public/security scope.

- [ ] **Step 3: Run focused and cross-slice tests**

Snapshot + routing + mission tests must all pass together.

---

### Task 7: Slice C RED — exact identity-keyed verification receipts

**Files:**
- Create: `tests/test_cad_agent_evidence_ledger.py`

**Interfaces:**
- Future `make_verification_receipt`, `validate_verification_receipt`, `first_unsatisfied_gate` in `cad_agent.evidence_ledger`.

- [ ] **Step 1: Add receipt identity tests**

Receipt fields:

```text
schema_version
head_sha
gate_id
artifact_identity
verification_class
verdict
source_evidence_ref
verifier_role
observed_at
receipt_sha256
```

`receipt_sha256` excludes `observed_at` only if the receipt identity contract explicitly treats time as observational; otherwise observed_at remains source evidence metadata but never a PASS satisfier.

- [ ] **Step 2: Add verdict truth tests**

Required gate satisfaction accepts only `PASS` or explicit `NOT_REQUIRED`; `SKIP`, `NOT_RUN`, `BLOCKED`, and `FAIL` remain unsatisfied.

- [ ] **Step 3: Add head/artifact invalidation tests**

A receipt for another head or artifact cannot satisfy the gate unless acceptance contract carries an explicit reuse relation and the supplied receipt exactly names that relation.

- [ ] **Step 4: Push causal RED**

Expected missing module/API only.

---

### Task 8: Slice C GREEN — verification ledger/query

**Files:**
- Create: `cad_agent/evidence_ledger.py`
- Test: `tests/test_cad_agent_evidence_ledger.py`

**Interfaces:**
- `make_verification_receipt(...) -> dict[str, object]`
- `validate_verification_receipt(...) -> dict[str, object]`
- `first_unsatisfied_gate(acceptance_contract: Mapping[str, object], receipts: Sequence[Mapping[str, object]], *, head_sha: str, artifact_identity: str = "NONE") -> str | None`
- `EvidenceLedgerError(ValueError)`

- [ ] **Step 1: Implement append-only receipt values in memory only**

No database/file writer is introduced in Slice C. Serialization/persistence is outside this slice; callers may store returned JSON in existing GitHub evidence surfaces.

- [ ] **Step 2: Implement ordered first-unsatisfied query**

Acceptance contract supplies ordered gate IDs and required identity class. Return first unsatisfied gate or `None`.

- [ ] **Step 3: Verify no truth-store duplication**

Architecture/reuse declaration must state the module is a pure derived-evidence validator/query, not a currentness or acceptance authority.

---

### Task 9: Slice D RED — one concrete failure-family registry

**Files:**
- Create: `tests/test_cad_agent_failure_registry.py`
- Create: `tests/fixtures/operating-model/windows-lisp-trigger-execution-boundary.json`

**Interfaces:**
- Future `validate_failure_family`, `match_failure_family`, and `recommended_probe` in `cad_agent.failure_registry`.

- [ ] **Step 1: Freeze first family from current R8-D causal RED**

Use the current #284/#285/SEQ291 evidence as historical fixture facts only:

```text
family_id = WINDOWS_LISP_TRIGGER_EXECUTION_BOUNDARY
causal_layer = LOCAL_WINDOWS_TRIGGER
signatures include exact HWND/PID binding missing, foreign receiver not rejected,
negative delivery not categorical, queue-return without execution receipt,
caller-visible execution ACK absent, receiver PID ownership unverified
probe = focused offline windows-trigger contract test
safe_auto_repair = NONE in A-D
hard_escalation = public owner/API/security scope expansion
```

No live execution is performed from the registry.

- [ ] **Step 2: Add exact and partial match tests**

Exact known signature set matches the family. Unknown cross-layer signatures return no match rather than nearest-guess classification.

- [ ] **Step 3: Push causal RED**

Expected missing module/API only.

---

### Task 10: Slice D GREEN — failure registry/probe selection

**Files:**
- Create: `cad_agent/failure_registry.py`
- Test: `tests/test_cad_agent_failure_registry.py`
- Fixture: `tests/fixtures/operating-model/windows-lisp-trigger-execution-boundary.json`

**Interfaces:**
- `validate_failure_family(payload: Mapping[str, object]) -> dict[str, object]`
- `match_failure_family(signatures: Sequence[str], families: Sequence[Mapping[str, object]]) -> dict[str, object] | None`
- `recommended_probe(family: Mapping[str, object]) -> str`
- `FailureRegistryError(ValueError)`

- [ ] **Step 1: Implement deterministic exact-subset matching**

A family matches only when all required signatures are present; unexpected signatures from another causal layer do not get silently absorbed.

- [ ] **Step 2: Keep registry descriptive, not executable authority**

It returns a probe identifier/path and escalation rule only. It cannot run commands, mutate files, authorize live work, or repair production.

- [ ] **Step 3: Run A-D aggregate focused suite + architecture/reuse/static checks**

Expected all focused tests PASS, existing architecture boundaries PASS, no AutoCAD/live gates invoked.

---

### Task 11: PR reconciliation and adoption gate

**Files:**
- Modify: PR #286 metadata/body only as needed; no additional runtime path solely for reporting.

**Interfaces:**
- Consumes: hosted exact-head tests/reuse, cumulative diff, active R8-D/main state.
- Produces: a fresh SOL acceptance disposition; merge remains a separate decision.

- [ ] **Step 1: Verify cumulative write-set and exact ancestry**

Compare `1263db2f54f505209ba6837b86181af8646b5a58...HEAD`; confirm only approved A-D docs/modules/tests/fixture/plan/spec paths.

- [ ] **Step 2: Verify hosted exact-head evidence**

Require tests + reuse SUCCESS on the exact head. AutoCAD/live/private remain literal NOT RUN.

- [ ] **Step 3: Fresh-read #131/#284/#285/current main before any merge disposition**

If R8-D still pins exact main or a newer authority blocks main movement, keep PR #286 DRAFT/HOLD. No merge by implication.

- [ ] **Step 4: Adoption semantics**

SOL behavior uses the approved routing/long-horizon rules immediately; repository enforcement becomes the default cross-session mechanism only after the corresponding slice is accepted and merged.
