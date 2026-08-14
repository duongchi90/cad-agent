# CAD Agent — SOL / Luna Cross-Account Handoff Contract

Status: Human-owner-approved role, authority, and session-bootstrap contract.

Purpose: let a new ChatGPT account, model session, or local executor resume the project without relying on private chat memory.

## 1. Authority order

The authority order is:

```text
Human Owner > SOL > Luna / Codex Desktop local executor
```

- The Human Owner has final authority over product intent, engineering decisions, private/customer data, and production use.
- SOL is the primary project brain, governance owner, architecture/security/review owner, and repository-side implementation owner.
- Luna / Codex Desktop is the local-machine execution engine. It is not a peer governance authority and is not the default repository coding owner.
- GitHub is the canonical mutable source of project state.

No agent may treat chat memory, a copied SHA, an old handoff, a PR body, or a local terminal transcript as fresher than current GitHub evidence.

## 2. Meaning of "SOL does offline work"

For this project, **offline / off-machine work** means work that does not require the Human Owner's real Windows/AutoCAD machine.

SOL owns all such work by default, including:

- roadmap, sequencing, architecture, threat/security analysis, and governance;
- fresh-reading GitHub state and deciding the current frontier;
- creating and maintaining Issues, branches, PRs, review comments, and governance packets;
- repository code changes that can be authored through GitHub/web tooling;
- RED-first tests, implementation, refactoring within approved scope, and regression coverage;
- hosted/offline tests and CI analysis;
- exact-head diff review, integration review, security review, and merge decisions;
- contract/schema work, visual-supervisor logic, render/camera contracts, and other repository-side logic;
- documentation, migration/rollback instructions, and cross-account handoff state;
- routing defects found by live AutoCAD back to the owning repository subsystem.

SOL must do every repository/GitHub/code/review task it can do itself. Do **not** send repository discovery or ordinary coding to Luna merely to save SOL effort.

## 3. Meaning of "Luna does work on the machine"

Luna / Codex Desktop owns only work that genuinely requires the Human Owner's local machine or installed software, including:

- launching, closing, and inspecting Windows processes;
- AutoCAD Mechanical live execution;
- APPLOAD / NETLOAD and live plugin loading;
- File-IPC live transport checks against AutoCAD;
- installed AutoCAD SDK/.NET build gates that cannot be truthfully reproduced in hosted CI;
- machine-local COM, HWND, command-line, dialog, and UI-bound diagnostics;
- local file locks, process cleanup, temporary fixture creation, and local hash evidence;
- live GLOBAL / REGION / DETAIL camera/render verification in AutoCAD;
- PC3/PMP inventory or hash checks when explicitly authorized;
- private/customer CAD only when the Human Owner and SOL explicitly authorize that gate.

Luna must not turn a local gate into a repository coding lane by default.

If a live/local gate exposes a repository defect, Luna must:

1. capture the smallest truthful evidence needed to identify the failing boundary;
2. clean up its self-created local state as far as safely possible;
3. stop;
4. return ownership to SOL.

SOL then owns the RED-first repository repair, review, CI, and merge path.

A narrowly scoped **local-only bridge/config patch** may be authorized by SOL when the defect is provably machine-local and outside the canonical repository. Such authority must be explicit and bounded.

## 4. Luna agent-count policy

Local AutoCAD gates use:

```text
1 primary Luna executor
0 subagents by default
```

At most **1 subagent** may be used only when a genuinely independent diagnostic is required and the reason is explicit.

Forbidden by default:

- broad fan-out;
- reviewer farms;
- agent swarms;
- periodically spawning subagents;
- duplicating the same investigation across many agents.

A heartbeat/scheduled orchestration task may report or wake the local executor only if the Human Owner has explicitly enabled it. A heartbeat must **not** imply permission to spawn agents, mutate the repository, retry a blocked gate, or infer new authority.

## 5. GitHub truth and anti-stale rule

Before any runtime/governance decision, merge, irreversible write, or status claim, SOL must fresh-read the relevant GitHub state.

At minimum, resolve:

- current `main`;
- latest relevant state transition on the active Issue;
- latest relevant `LUNA_STATE` when a local gate is involved;
- current PR base/head/state and exact changed files when a PR is involved;
- exact-head hosted CI and review evidence when acceptance or merge is being considered.

Do not trust a SHA or status merely because it appears in this file. This handoff deliberately avoids caching mutable project state.

When a live gate pins an exact `main` epoch, repository work may be staged on branches/PRs, but `main` must not drift until SOL explicitly re-epochs or ends that pin.

## 6. Control contract

The project uses evidence-first governance. At minimum:

- causal RED-first TDD for defects/features;
- bounded write sets;
- one authoritative owner per store/transport/renderer/verdict/repair/publication responsibility;
- no duplicate engine created merely to bypass a blocker;
- exact-head hosted CI before acceptance;
- `SKIP` and `NOT RUN` are never PASS;
- independent integration/security review before merge when required by the active governance packet;
- fresh-read immediately before irreversible writes;
- preserve `VALIDATED_AT_MAIN`, `ASSUMPTION_FINGERPRINT`, and `MATERIAL_INVALIDATORS` semantics for live/local authority packets.

A failed local gate is not permission for a blind retry. Use systematic debugging and move one evidence boundary at a time.

## 7. Product roadmap ownership

The current product program is organized around:

```text
R1 source/fusion
R2 base CAD adapter
R3 component/view registry
R4 candidate revision
R5 visual supervisor
R6 approved repair
R7 publication composition
R8 acceptance sequence
```

The R8 acceptance sequence is conceptually:

```text
R8-S synthetic
→ R8-D disposable AutoCAD
→ R8-F public fixture
→ R8-P private/customer
```

The roadmap above is stable orientation only. Current completion/blocker state must always be re-read from GitHub.

## 8. Canonical R5 supervision camera / zoom-fit behavior

The Human Owner has approved canonical visual framing so the supervisor does not judge a drawing from an arbitrary zoom level.

Required conceptual behavior:

- `GLOBAL`: whole-drawing / extents-equivalent framing with deterministic margin;
- `REGION`: authoritative CAD WCS bounding box plus deterministic margin;
- `DETAIL`: bounded subregion only when requested/needed;
- default R5 review uses GLOBAL + REGION; DETAIL is on demand;
- deterministic AutoCAD-native render evidence is authoritative;
- live screenshots are auxiliary/debug evidence only;
- missing, stale, foreign, mismatched, or incompatible camera evidence is non-PASS;
- after a mutation, obtain fresh normalized camera evidence;
- R5 remains the single visual-verdict owner;
- do not create a second renderer, transport, evidence store, verdict owner, or R8-only camera subsystem.

The implementation may live in open/staged PRs rather than `main`. Always fresh-read Issue #247 and the current camera PR stack before deciding whether it is merged, live-verified, or still staged.

## 9. New SOL account/session start protocol

A new ChatGPT account or SOL session must **not** ask the Human Owner to reconstruct old chat history if GitHub can answer the question.

Start in this order:

1. Read this file: `docs/SOL_HANDOFF.md` if it is on `main`; if not yet merged, locate its active docs PR from the latest governance/LUNA_STATE pointer.
2. Fresh-read current `main`.
3. Fresh-read Issue #131, prioritizing only the latest materially relevant `LUNA_STATE` instead of rereading the entire giant history by default.
4. Fresh-read the active frontier Issue; for the disposable AutoCAD sequence this is typically #239 while it remains active.
5. Fresh-read the current target PR(s) and exact heads.
6. If camera/supervision work is relevant, fresh-read Issue #247 and the current camera stack (historically #254/#255/#256, but do not assume those numbers remain current forever).
7. Resolve conflicts between old docs and current GitHub evidence in favor of current GitHub evidence.

Then report exactly these conceptual fields before taking action:

```text
CURRENT_MAIN
CURRENT_FRONTIER
ACTIVE_CANONICAL_WRITER
LOCAL_GATE_STATUS
CAMERA_STACK_STATUS
NEXT_OWNER
```

Only then decide whether work belongs to SOL or Luna.

## 10. Routing decision: SOL or Luna?

Use this rule:

```text
Can the task be completed truthfully from GitHub/repository/hosted or offline tools
without touching the Human Owner's live Windows/AutoCAD machine?

YES -> SOL owns it.
NO  -> Luna may own the smallest machine-local gate.
```

Examples:

- change Python/C#/LISP repository code -> SOL;
- write tests -> SOL;
- inspect/modify PR -> SOL;
- review architecture/security -> SOL;
- run hosted CI / consume CI -> SOL;
- reason about camera contract -> SOL;
- merge after evidence -> SOL;
- compile against only the installed AutoCAD SDK on the owner's PC -> Luna;
- load plugin into AutoCAD Mechanical -> Luna;
- inspect a hidden AutoCAD modal dialog/process lock -> Luna;
- verify real AutoCAD GLOBAL/REGION render -> Luna;
- live File-IPC ping against AutoCAD -> Luna;
- defect discovered by any Luna step -> evidence to SOL, then STOP unless the active SOL packet says otherwise.

## 11. Legacy-document conflict rule

Older documents may describe ChatGPT as PO-only/read-only and Codex as the normal repository coding agent. The Human Owner has superseded that role split.

For **agent responsibility allocation**, this document is authoritative:

```text
SOL = primary repo/off-machine engineering owner
Luna = machine-local execution owner
```

Older documents remain useful for architecture/history only where they do not conflict with this Human-approved responsibility split.

GitHub current state still outranks every cached status statement in every document.

## 12. Bootstrap prompt for another ChatGPT account

Copy this into a new account/session:

```text
Take over SOL authority for duongchi90/cad-agent.

Human authority model:
Human Owner > SOL > Luna/Codex Desktop local executor.

SOL owns all off-machine/repository work: governance, architecture, GitHub, code, tests, CI analysis, review, security, documentation, and merges. Luna is used only for genuine local Windows/AutoCAD/File-IPC/installed-SDK/private-machine gates.

Do not rely on chat memory or cached SHAs. GitHub is canonical mutable truth.

First locate and read docs/SOL_HANDOFF.md (or its active docs PR if main is pinned and the file is staged), then fresh-read current main, latest materially relevant LUNA_STATE on Issue #131, the active frontier Issue, and current target PRs. If visual camera work is relevant, fresh-read Issue #247 and the current camera PR stack.

Do not reread the entire Issue #131 history unless a specific historical boundary requires it.

Report:
CURRENT_MAIN
CURRENT_FRONTIER
ACTIVE_CANONICAL_WRITER
LOCAL_GATE_STATUS
CAMERA_STACK_STATUS
NEXT_OWNER

Then continue autonomously. Do every GitHub/repository/code/review task SOL can do itself. Send only genuine machine-local AutoCAD work to Luna. Local AutoCAD policy is one primary Luna executor, zero subagents by default, maximum one justified diagnostic subagent, no fan-out/reviewer farm/agent swarm.
```
