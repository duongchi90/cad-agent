# CAD Agent — Current Operational Handoff

Status: current operational handoff for PO and coding agents.

Updated: 2026-08-05

This document is an operational index. Live GitHub evidence, `docs/STATUS.md`,
`docs/ARCHITECTURE.md`, approved specifications, plans, issues, PRs, exact
heads, diffs, and CI remain the sources of truth.

## 1. Source-of-truth order

1. Live GitHub state: `main`, issue, branch, PR, exact head, changed files,
   synthetic merge candidate, and CI logs.
2. `docs/STATUS.md` for verified, partial, `SKIP`, and `NOT RUN` gates.
3. `docs/ARCHITECTURE.md` for package ownership and safety boundaries.
4. Approved specifications and implementation plans.
5. This handoff for current routing.
6. Old chats, stale issues, and historical PRs only as context.

Never treat a branch name, PR body, chat statement, stale workflow, or old open
issue as proof without checking current code and exact commit evidence.

## 2. Current integrated state

- Repository: `duongchi90/cad-agent`.
- Latest accepted implementation merge: `a8a962281b2d7480c9444eb8e1b56c6795c108aa`.
- Latest merged PR: #54 — S3A exact-base Xref inspection and extraction offline contract.
- Previous accepted implementation merges:
  - #51 S2A at `393f318317032096ec5e055ed1c928090f3b7e31`;
  - #50 S1 at `ca85f2329e606bb307f8dece0bc1081575eec136`.
- Current `main` includes later R1A design/plan documentation through
  `d547ca8b1eb39651a00109da3862b79bcce4f0f9`.
- Runtime promotion: none.

### S3A accepted evidence

- Implementation head: `c53501f93258b39078ed42a4cb0e4a96c4f09790`.
- Squash merge: `a8a962281b2d7480c9444eb8e1b56c6795c108aa`.
- Exactly one commit and four allowlisted files.
- Focused tests: 49 passed.
- Canonical candidate: PASS; offline JUnit 929/0/0/0.
- AutoCAD, File IPC, C#, private data, S3B, and S3C remain `NOT RUN`/locked.

## 3. Environment-blocked PR #55 — S2B

PR: #55.

Branch: `task/s2b-native-render-ipc-seam`.

Exact head: `905508a418866ad51d888cad102994d0518b7d1d`.

State:

- source review: acceptable;
- exactly one commit and 15 allowlisted files;
- fresh sequential integration candidate:
  `78225f922bd92adc25a844c70f513c297059c829`, combining S2B with S3A on main;
- hosted offline: 918 passed plus 18 subtests;
- offline JUnit: 936/0/0/0;
- dotnet IPC JUnit: 38/0/0/0;
- reuse declaration: PASS;
- `.NET SDK 10.0.302`: available;
- `dotnet restore`: exit 0;
- `dotnet build` and `dotnet test`: blocked before valid test discovery because
  `AcCoreMgd.dll`, `AcDbMgd.dll`, and `AcMgd.dll` cannot be resolved;
- workstation does not contain `C:\Program Files\Autodesk\AutoCAD 2027`;
- worktree clean and `git diff --check` PASS.

Classification: environment/reference blocker, not yet an implementation bug.
Do not amend code merely to bypass this gate. Do not merge until restore,
Release x64 build, and Release x64 test all exit 0 using approved Autodesk 2027
managed references, with zero test failures and no Autodesk DLL copied to build
output.

AutoCAD live, actual native capture, S2C, and private data remain `NOT RUN` or
locked.

## 4. Active code task — Issue #56 R1A

Execution mode: `SINGLE_LUNA`.

Issue: #56 — closed SourceBundle offline contract.

Branch: `task/r1a-source-bundle-offline`.

Exact implementation base:
`d547ca8b1eb39651a00109da3862b79bcce4f0f9`.

Overlap with PR #55: `PASS`.

Design:
`docs/superpowers/specs/2026-08-05-source-bundle-offline-contract-design.md`.

Plan:
`docs/superpowers/plans/2026-08-05-source-bundle-offline-contract.md`.

Purpose: add one closed, deterministic, pure-Python SourceBundle descriptor for
immutable image, PDF, exact-base CAD, and engineer-record evidence metadata.
It does not read source bytes, run recognition, launch AutoCAD, integrate with
manifests/CLI, create a registry, or grant technical authority.

Exactly four implementation files are allowed:

1. `cad_agent/source_bundle.py`
2. `tests/test_cad_agent_source_bundle.py`
3. `tests/fixtures/source-bundle.json`
4. `docs/superpowers/implementation-records/2026-08-05-source-bundle-offline.md`

The worker must use TDD, reuse
`cad_agent.drawing_contracts.canonical_json_sha256`, run focused tests, Ruff,
architecture checker, diff-check, canonical verification with
`-SkipAutoCADDotNet`, open one non-draft PR, and stop.

## 5. Explicit parallel-work amendment

The earlier blanket lock on all R1 work is narrowed because PR #55 is blocked
only by unavailable Autodesk references and R1A has zero file/runtime overlap.

Only R1A Issue #56 is unlocked.

The following remain locked:

- R1B and source-fusion runtime;
- S2C actual AutoCAD-native capture;
- S3B/S3C File IPC/live Xref work;
- component/view registry;
- dimension-authority expansion;
- revision orchestration;
- Codex production repair planning;
- repair-loop integration;
- visual verdict and publication;
- old VS-T4 through VS-T8 unchanged;
- any duplicate OCR, solver, DXF builder, AutoCAD transport/dispatcher,
  manifest/checkpoint/revision store, repair executor, verdict path, or publisher.

This amendment does not convert any missing live gate into PASS.

## 6. Authoritative ownership

```text
primitive_ir_lib
  -> semantic_ir_lib
  -> agent_lib
  -> dxf_builder_lib
  -> mcp_integration_lib
```

- `primitive_ir_lib`: recognition, OCR, geometry, tables, calibration, traces.
- `semantic_ir_lib`: semantic parts, constraints, pruning, solving.
- `agent_lib`: advisory proposals with separate approved apply.
- `dxf_builder_lib`: native entities, DXF generation, headless review/repair.
- `mcp_integration_lib` and the existing .NET plugin: the only approved File
  IPC and AutoCAD Mechanical boundary.
- `cad_agent`: thin orchestration, run identity, manifests, checkpoints,
  resumability, evidence routing, approval gates, and CLI composition.

R1A may add orchestration metadata only; it must not absorb recognition or CAD
algorithms.

## 7. Required PO review for Issue #56

Before accepting the R1A PR, verify:

- ancestry includes exact base `d547ca8b1eb39651a00109da3862b79bcce4f0f9`;
- one bounded commit;
- exactly the four Issue #56 allowlisted files;
- public API and field names match the approved design;
- closed root/item/quality objects;
- strict safe paths, IDs, hashes, timestamps, uniqueness, and compatibility matrix;
- deterministic sorting and fixture hash;
- no imports/calls to manifests, CLI, recognition packages, File IPC, ctypes,
  subprocess, AutoCAD, or C#;
- focused tests, Ruff, architecture checker, diff-check, canonical verifier,
  Reuse Declaration, and GitHub CI pass;
- AutoCAD .NET/live, private data, runtime integration, and later tasks are
  reported truthfully as `NOT RUN`/not implemented;
- no runtime promotion.

## 8. Stale issue warning

Issues #16 and #17 remain open historically, but their intended M2 behavior is
already present in current `main`. Do not execute them from their old issue text
without a fresh live-code audit. PR #18 was closed unmerged, but subsequent
integrated code already contains the Drawing Setup CLI and later audit/verify
implementation.

## 9. Next action

- Luna implements Issue #56 only on `task/r1a-source-bundle-offline`.
- Luna opens one non-draft PR and stops.
- PR #55 remains open and unchanged until approved Autodesk references are
  available for the mandatory .NET build/test gate.
- Neither task may start S2C, S3B/S3C, R1B, registry, revision, repair, verdict,
  or publication work.
