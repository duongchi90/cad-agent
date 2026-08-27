# CAD Agent Operating Model Enforcement Design

Date: 2026-08-27
Status: DESIGN — awaiting owner review before implementation planning
Repository: `duongchi90/cad-agent`
Design base: `1263db2f54f505209ba6837b86181af8646b5a58`

## 1. Purpose

This design does **not** replace the existing project authority or operating model.

The canonical standing model remains:

- Human Owner > CONTROL_WRITER_SOL > Local Solo Executor;
- GitHub is the canonical source of truth;
- SOL/Web owns broad reasoning, architecture, reuse, security, root-cause, source/contract analysis, CI/evidence interpretation, acceptance, reconciliation, merge/publication decisions, and successor preparation;
- Luna / Codex Desktop is the single local-machine executor and is reserved for work that requires local checkout state, Windows, build/toolchain state, AutoCAD Mechanical, COM/ROT/UI, NETLOAD, File-IPC, or other evidence unavailable to SOL/Web;
- Luna should continue autonomously through same-layer causal repairs within an explicitly authorized mission instead of returning baton after each small helper/controller/harness failure;
- accepted PASS boundaries are reused absent concrete drift;
- Human relay is not used for routine gates.

The problem addressed here is **enforcement drift**. These principles already exist in Issue #131 standing governance comments, but they are not represented strongly enough in repository startup state, machine-readable control state, mission construction, evidence accounting, or reusable failure knowledge. This allows later sessions to fall back into excessive SOL↔Luna baton churn, stale documentation, repeated discovery, and unnecessary local/live execution.

The goal is to make the existing operating model executable, auditable, and difficult to violate accidentally.

## 2. Canonical governance inputs

Implementation must treat these as authority inputs, not duplicate or reinterpret them:

1. Issue #131 standing operating model comment `5396800691`.
2. Issue #131 cross-chat persistence/enforcement note `5419064061`.
3. The newest valid numbered `CONTROL_SEQ` and its exact consumed terminal.
4. Current GitHub `main`, active issue/PR/base/head tuple, and exact hosted evidence.
5. Repository authority documents, including `docs/AI_OPERATING_MODEL.md`, after reconciliation with the live control plane.

A newer Human Owner or CONTROL_WRITER_SOL governance decision may supersede the standing notes. Repository enforcement must never mint or supersede numbered execution authority by itself.

## 3. Current failure mode

R5 ultimately succeeded and merged, but its history exposed recurring control-plane costs:

- local controller/harness defects repeatedly caused hard handoffs even when the standing model intended same-layer continuation;
- accepted evidence was repeatedly rediscovered in narrative comments;
- failure knowledge such as COM wrapper identity, layout custody, environment restoration, artifact retention, modal identity reconstruction, and cleanup behavior remained primarily in Issue #131 history rather than reusable executable probes/oracles;
- `docs/HANDOFF.md` and `docs/STATUS.md` remained materially stale while Issue #131 carried the actual current state;
- a fresh SOL session could therefore read repository startup documents that lagged the canonical control plane and drift from approved operating invariants.

The enforcement layer must reduce this gap without creating a second governance authority, second runtime store, second AutoCAD transport, or alternate execution plane.

## 4. Design principles

### 4.1 Authority preservation

No new component may supersede Human Owner, CONTROL_WRITER_SOL, GitHub canonical state, or existing runtime authority owners.

The enforcement layer may read canonical governance, validate consistency, materialize derived machine-readable state, refuse stale or contradictory missions, classify work as Web-capable or Local-required, record verification receipts keyed to exact identities, and prepare the next mission.

It may not mint `CONTROL_SEQ`, authorize live AutoCAD or repository mutation, merge or publish by implication, or synthesize owner approval or missing evidence.

### 4.2 SOL-first work allocation

Before Luna is assigned work, SOL/Web must exhaust all work that does not require the local machine.

SOL/Web owns by default:

- GitHub state reads and reconciliation;
- repository/API/contract archaeology available through GitHub;
- architecture and reuse analysis;
- source/contract comparison;
- security and authority review;
- root-cause reasoning over available evidence;
- test/CI interpretation;
- RED/GREEN design;
- mission scoping and acceptance-oracle construction;
- N+1/N+2 lookahead preparation;
- exact-head review and merge disposition.

Luna may be used for:

- local edits when only the local executor is authorized to write;
- local tests/builds requiring Windows or unavailable toolchain state;
- AutoCAD Mechanical execution;
- COM/ROT/UI/foreground/native-dialog handling;
- NETLOAD;
- File-IPC against the real AutoCAD plugin;
- local process/environment cleanup evidence;
- machine-only artifacts and real-surface verification.

This is a routing invariant, not a performance hint.

### 4.3 Long-horizon local missions

A Luna mission should represent one meaningful causal mission, not one command.

Within explicit write-set/live scope and causal budget, Luna should be able to inspect local state, reproduce the active same-layer failure, create run-owned temporary probes, repair helper/controller/harness/telemetry defects that do not expand authority or public scope, run focused checks, continue to the next business/evidence boundary, complete cleanup/parity, and emit one material terminal at mission completion or a true hard handoff boundary.

Hard handoff boundaries remain those already defined by the standing model: scope/interface/dependency expansion, security/authority ambiguity, genuinely new cross-layer defect, exhausted causal budget, unprovable cleanup/parity/custody, human-only action, mission completion requiring governance, or superseding authority.

## 5. Enforcement components

### 5.1 Canonical Startup Snapshot

Purpose: prevent stale-session governance decisions.

A deterministic repository tool derives a compact startup snapshot from explicit inputs supplied by SOL or the local executor.

Minimum fields:

- standing model reference;
- persistence note reference;
- newest numbered `CONTROL_SEQ`;
- authority comment ID;
- consumed terminal ID/classification;
- baton/next owner;
- current `main` SHA/tree;
- active issue/PR/base/head/state when applicable;
- current live/repo-write locks;
- accepted PASS evidence references selected for reuse;
- first unresolved gate;
- snapshot generation time and deterministic content hash.

The snapshot is **derived state**, never an authority source. Every material execution decision still fresh-reads GitHub according to the standing model.

Repository startup docs must point to this mechanism and must not cache current SHA/PR state as if static prose were canonical.

### 5.2 Work-Routing Classifier

Purpose: enforce “SOL does everything Web can do; Luna only does machine-required work.”

Every proposed action is classified as one of:

- `WEB_CAPABLE`
- `LOCAL_REPO_REQUIRED`
- `LOCAL_WINDOWS_REQUIRED`
- `LOCAL_AUTOCAD_REQUIRED`
- `HUMAN_ONLY`

The classifier emits a reason and required evidence surface.

Rules:

- `WEB_CAPABLE` work must not be delegated to Luna merely to save SOL effort or tokens.
- `LOCAL_*` requires an explicit statement of which capability is unavailable to SOL/Web.
- `HUMAN_ONLY` is reserved for genuine owner/product decisions, approvals, secrets/private inputs, or irreversible actions that cannot be resolved by experiment or existing authority.
- Classification does not itself authorize execution.

Initial implementation should be deterministic and testable; no LLM dependency is required.

### 5.3 Mission Compiler and Validator

Purpose: convert SOL reasoning into one complete, machine-checkable long-horizon local mission.

A compiled mission contains:

- goal/outcome predicate;
- exact authority reference and consumed terminal;
- exact main/base/head/branch/PR tuple where applicable;
- exact write-set and forbidden paths;
- local/live capability required;
- accepted evidence to reuse;
- pre-execution closure requirements;
- causal family and causal repair budget;
- allowed temporary/harness repairs;
- exact expensive/live budgets;
- acceptance oracle;
- hard handoff conditions;
- cleanup/parity requirements;
- required terminal schema;
- `NEXT_OWNER=SOL` on terminal unless newer authority says otherwise.

The validator rejects stale authority, contradictory tuples, missing exact write-set for repo mutation, live work without explicit live authority, missions whose required action is entirely `WEB_CAPABLE`, unbounded rediscovery of accepted boundaries, implicit merge/publication authority, and human relay for routine gates.

The compiler does not replace CONTROL_WRITER_SOL. It materializes an already authorized SOL mission into a closed contract.

### 5.4 Verification Ledger

Purpose: replace narrative memory with exact identity-keyed verification accounting while preserving original evidence.

The ledger records derived verification receipts. It is not a second truth store and does not replace GitHub comments, CI, or runtime artifacts.

A receipt is keyed at minimum by repository commit/head SHA, contract/gate identifier, artifact/request/evidence identity where relevant, verification class, verdict, source evidence reference, verifier identity/role, timestamp, and receipt hash.

Supported verdict vocabulary preserves current semantics:

- `PASS`
- `FAIL`
- `NOT_RUN`
- `SKIP`
- `BLOCKED`
- `NOT_REQUIRED`

`SKIP` and `NOT_RUN` never satisfy a required PASS gate.

A head SHA change invalidates head-bound receipts unless the contract explicitly permits reuse and the reuse relation is proven. A live artifact receipt cannot silently transfer to different source/candidate/request identity.

The primary deterministic query is:

`first_unsatisfied_gate(acceptance_contract, exact_identity_set)`

This allows SOL to ask “what remains?” without reconstructing thousands of narrative comments.

### 5.5 Failure Knowledge Registry

Purpose: make a solved failure expensive only once.

The registry catalogs recurring failure families discovered during real execution. Each entry points to executable probes/oracles/tests rather than only prose.

Initial candidates extracted from R5 include:

- AutoCAD layout/database identity and COM wrapper handling;
- foreground ownership and activation verification;
- unsigned NETLOAD modal Name+Location identity reconstruction;
- FILEDIA snapshot/restoration;
- process-scope environment restoration;
- File-IPC artifact-relative-path containment and retention;
- GLOBAL/REGION retained artifact verification;
- cleanup/CAD_ZERO/IPC_ZERO parity;
- controller-vs-production-defect discrimination.

Each failure family defines signature, causal layer, accepted evidence basis, probe/oracle entry point, safe auto-repair envelope if any, hard escalation boundary, and regression fixtures/tests.

A repeated known signature that again requires broad manual rediscovery is an enforcement regression.

### 5.6 Skill/Eval Promotion Loop

Purpose: test agent-operating knowledge before making it canonical.

A new or materially changed execution skill/oracle is tested against representative historical or synthetic cases.

For judgment-heavy skills, prefer multiple independent candidate runs, organic prompts that do not reveal the rubric, a different model family for independent judging where available, concrete rubrics, verification from actual actions/artifacts rather than self-report, and promotion only when behavior improves without weakening authority or safety.

Deterministic probes do not require multi-model ceremony if a cheap exact test fully verifies them.

## 6. Repository state reconciliation

Repository startup documents currently lag live governance. Reconciliation must avoid copying transient state into prose.

### 6.1 `docs/AI_OPERATING_MODEL.md`

Keep its stable authority model. Amend only where needed to reference standing long-horizon enforcement. Do not turn it into a live status page.

### 6.2 `docs/HANDOFF.md`

Refactor into a navigational handoff that points to current canonical control-plane location, startup snapshot procedure, active milestone lookup procedure, and durable accepted architecture references.

Remove stale claims that pretend August 6 state is current.

### 6.3 `docs/STATUS.md`

Separate durable historical acceptance records from current derived operational state. Current state should be generated or referenced through a machine-readable snapshot, not manually rewritten across historical sections.

No historical evidence should be deleted merely to make the file shorter unless separately reviewed and migrated to an accepted archive/reference location.

## 7. Data ownership and storage

The enforcement layer must avoid creating a competing runtime owner.

Preferred ownership:

- pure governance/enforcement logic under `cad_agent` only if that package is already the accepted thin orchestration owner for the relevant derived state;
- scripts under `scripts/` for deterministic startup/verification CLI surfaces;
- documentation under `docs/`;
- tests under existing test roots;
- no new external service, database, daemon, message bus, or hidden agent store for the first slice.

Persistent derived ledger/registry format should be plain, reviewable, and deterministic. JSON/JSONL is preferred over a database for the first slice unless an existing repository owner provides a better fit.

Any proposal to create a new manifest/checkpoint/revision authority, alternate File-IPC path, or external orchestration service is out of scope.

## 8. Execution flow after enforcement

```text
Human Owner intent
        ↓
SOL fresh-read canonical GitHub governance
        ↓
Startup Snapshot + accepted-evidence reuse map
        ↓
SOL performs all WEB_CAPABLE work
        ↓
Work-Routing Classifier
        ↓
No local need ───────────────→ SOL completes/reviews/merges
        │
        └─ local need
              ↓
      SOL Mission Compiler
              ↓
      Mission Validator PASS
              ↓
      Luna Local Solo Executor
      long-horizon same-layer loop
              ↓
      machine/AutoCAD evidence
              ↓
      Verification Ledger receipts
              ↓
      one material terminal
              ↓
      SOL acceptance/reconciliation
              ↓
      merge/successor/lookahead
```

## 9. Risk classes and verification

### L0 — deterministic governance/mechanical

Examples: snapshot parsing, stale-doc assertions, exact SHA matching, JSON validation.

Verification: focused tests + hosted CI where available.

### L1 — behavioral orchestration

Examples: mission routing, evidence reuse, first-unsatisfied-gate logic.

Verification: focused tests + adversarial/independent review when behavior can fail subtly.

### L2 — local machine / AutoCAD / authority-sensitive

Examples: live mission execution, COM/UI, File-IPC, mutation, publication.

Verification: exact real-surface evidence + independent SOL review. Existing security/authority gates remain unchanged.

This reduces unnecessary ceremony for cheap deterministic work without relaxing high-risk gates.

## 10. Implementation slicing

Implementation must be incremental and each slice independently verifiable.

### Slice A — Governance drift closure

Goal: make new SOL sessions reliably discover the approved standing model and current control plane.

Scope:

- reconcile `docs/HANDOFF.md` and `docs/STATUS.md` navigation;
- add deterministic startup snapshot parsing/validation over supplied GitHub/control inputs;
- add stale-state regression tests;
- no AutoCAD, no live execution, no runtime behavior mutation.

### Slice B — Work routing + mission contract

Goal: prevent Luna delegation for Web-capable work and compile long-horizon local missions.

Scope:

- work classification contract;
- mission schema/model;
- mission validation;
- causal-budget/hard-handoff rules;
- deterministic tests based on historical R5 mission patterns;
- no AutoCAD required for acceptance.

### Slice C — Verification ledger

Goal: materialize exact identity-keyed gate receipts and first-unsatisfied-gate queries.

Scope:

- receipt model;
- exact identity/reuse rules;
- verdict vocabulary;
- deterministic query API/CLI;
- import selected canonical R5 evidence only as explicit fixtures, never as a silent rewrite of history.

### Slice D — Failure knowledge registry

Goal: encode recurring R5 controller/harness lessons as executable probes/oracles.

Start with only the highest-value repeated families. Do not create a broad skill framework before one concrete family proves the pattern.

### Slice E — Local executor integration

Goal: have Luna consume the compiled mission and emit machine-readable evidence/terminal output while preserving numbered SOL authority.

This is the first slice that may require Luna/local execution. All prior slices should be completed by SOL/Web/GitHub and hosted infrastructure to the maximum technically possible.

### Slice F — Skill/eval promotion

Goal: prove promoted skills reduce repeated rediscovery and baton churn without authority regression.

Use blind/multi-agent evaluation only where judgment is material. Keep deterministic cases deterministic.

## 11. Success criteria

The enforcement program is successful when:

1. A fresh SOL session can deterministically locate the standing model, persistence note, newest numbered authority, current terminal/baton, and current main/PR tuple without relying on stale chat memory.
2. Repository startup docs no longer present old operational state as current authority.
3. A proposed task can be deterministically rejected from Luna when it is `WEB_CAPABLE`.
4. A local mission can span same-layer helper/controller/harness repairs without requiring a new numbered authority for each small failure.
5. Accepted PASS evidence can be queried and reused by exact identity without narrative archaeology.
6. `SKIP`/`NOT_RUN` cannot accidentally satisfy required gates.
7. A head or artifact identity change invalidates the appropriate verification receipts.
8. At least one recurring R5 failure family is represented by an executable probe/oracle and regression fixture.
9. Luna is not required for Slices A-D acceptance unless a concrete local-only prerequisite is discovered.
10. No new authority owner, runtime truth store, AutoCAD transport, publisher, or hidden orchestration service is introduced.

## 12. Metrics

Measure improvement by project throughput and unnecessary-local-work reduction, not PR count alone.

Track:

- SOL↔Luna material baton turns per accepted milestone;
- local AutoCAD epochs per new accepted business boundary;
- percentage of Luna missions ending at a true hard handoff or mission completion;
- repeated known failure signatures requiring fresh manual analysis;
- accepted evidence reuse rate;
- time from first causal evidence to verified closure;
- fraction of proposed Luna work rejected as Web-capable;
- local token/tool usage attributable to discovery that SOL could have completed.

A known failure signature that repeatedly forces broad rediscovery is a direct enforcement-quality regression.

## 13. Security and rollback

Security remains fail-closed.

The first implementation slices must not authorize live AutoCAD, mutate private/customer CAD, alter system profile/registry/trust/printer settings, create persistent services, or weaken existing exact-identity, cleanup, publication, or authority gates.

Rollback is repository-only for Slices A-D: revert the enforcement commits. No data migration or machine rollback should be required.

If derived ledger/registry files are introduced, original canonical evidence references remain authoritative and sufficient to reconstruct them.

## 14. Non-goals

This program does not replace SOL with Luna, reduce SOL reasoning to save tokens, make Luna an architecture/research agent by default, create a multi-writer local swarm, auto-merge high-risk work without independent acceptance, move AutoCAD to cloud execution, replace Issue #131 numbered authority, replace existing CAD runtime owners, redesign R6/R7/R8 product behavior, or reopen accepted R5 live gates without concrete drift.

## 15. Recommended first implementation boundary

Begin with **Slice A only** after this written design is approved.

Slice A is intentionally Web/GitHub-first and should require zero Luna involvement unless repository tooling proves impossible to exercise through available hosted/Web capabilities.

Acceptance predicate:

```text
FRESH_SOL_STARTUP_DISCOVERS_CANONICAL_MODEL=PASS
STALE_HANDOFF_CURRENT_STATE_REMOVED=PASS
STARTUP_SNAPSHOT_DETERMINISTIC=PASS
NO_AUTHORITY_MINTING=PASS
NO_RUNTIME_BEHAVIOR_CHANGE=PASS
LUNA_REQUIRED=NO
```
