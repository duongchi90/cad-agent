# CAD Agent — Current Operational Handoff

Status: current operational handoff for PO and coding agents.

Updated: 2026-08-05

This document is an operational index. Live GitHub evidence, `docs/STATUS.md`,
`docs/ARCHITECTURE.md`, approved specifications, and active issues remain the
sources of truth.

## 1. Source-of-truth order

1. Live GitHub state: `main`, issue, branch, PR, exact head, changed files,
   diff, and CI.
2. `docs/STATUS.md` for verified, partial, `SKIP`, and `NOT RUN` gates.
3. `docs/ARCHITECTURE.md` for package ownership and safety boundaries.
4. Approved specifications and implementation plans.
5. This handoff for current task routing.
6. Old chats and historical documents only as context.

Never treat a chat statement, branch name, or PR body as proof without checking
repository evidence.

## 2. Current integrated state

- Repository: `duongchi90/cad-agent`
- Latest accepted implementation base: `5d6074a2969894367df2e5d70b7a362c99e43c61`
- Latest merged PR: #47 — `R0: establish Reuse Integration Rebaseline gates`
- Completed issue: #46
- R0 state: accepted for governance/rebaseline scope only.
- Runtime promotion: none.

R0-T7 evidence:

- Task 7 base: `07a14ce3623024f2df848b2b88ff447980772492`;
- full-verifier candidate: `a373114c91edd02a6a4dd086b02b2a89433be964`;
- final record-only head: `34fca22b59cf2c978a5746b1b12930672b72eefe`;
- exactly two allowlisted documentation files changed;
- focused final record-only suite: 41 passed, 0 skipped;
- hosted synthetic merge verification: 790 offline passed, 18 subtests passed,
  dotnet IPC 38 passed, offline JUnit 808/0/0/0;
- `tests` workflow run #299: success;
- `reuse-declaration` workflow run #9: success;
- AutoCAD .NET: `NOT RUN`;
- private-data acceptance: `NOT RUN`;
- AutoCAD Mechanical live acceptance: `NOT RUN`.

The live `main` may become newer because this handoff is a later operational
commit. Both active implementation branches were already created from the exact
accepted base above and must not be silently rebased onto a handoff-only commit.

## 3. Active parallel code tasks

Execution mode: `PARALLEL_LUNA`.

Shared base SHA: `5d6074a2969894367df2e5d70b7a362c99e43c61`.

Overlap check: `PASS`.

Merge policy: independent PO review, then sequential merge. After the first PR
merges, the second PR must incorporate current `main` and rerun affected checks
before merge.

### Luna A — Issue #48

Task: S1 Codex SDK Windows compatibility adapter and disposable probe.

Branch: `task/s1-codex-sdk-windows-compat`.

Allowed files:

- `agent_lib/codex_sdk_compat.py`
- `agent_lib/tests/test_codex_sdk_compat.py`
- `scripts/probe_codex_sdk_windows.py`
- `docs/superpowers/implementation-records/2026-08-05-codex-sdk-windows-spike.md`

The task is compatibility/probe code only. It must not log in, run a model turn,
modify the workspace through Codex, enable repair planning, or change project
dependencies or `requirements/windows-py311.lock`.

### Luna B — Issue #49

Task: S2A AutoCAD-native render evidence offline contract.

Branch: `task/s2a-autocad-render-evidence-contract`.

Allowed files:

- `mcp_integration_lib/autocad_render_evidence.py`
- `mcp_integration_lib/tests/test_autocad_render_evidence.py`
- `mcp_integration_lib/tests/fixtures/autocad-render-evidence.json`
- `docs/superpowers/implementation-records/2026-08-05-autocad-render-evidence-offline.md`

This is a pure-Python contract slice. It must not modify `dotnet_ipc.py`, C#
plugin/dispatcher code, existing File IPC operations, CLI, dependencies, or
visual verdict authority. AutoCAD integration and live rendering remain
`NOT RUN`.

## 4. Code-first, AutoCAD-live-later policy

The current priority is to complete deterministic code, contracts, adapters,
fixtures, and offline tests before requiring a running AutoCAD Mechanical
session.

This policy does not convert missing live evidence into a pass:

- S2A may be accepted as an offline contract slice only;
- S2 remains incomplete until a separately issued S2B task integrates the
  existing File IPC/.NET dispatcher and passes the approved live gate;
- private-data and AutoCAD live gates remain `NOT RUN` until actually executed;
- code-complete or offline-verified does not mean production-ready.

## 5. Locked work

Until Issues #48 and #49 are independently reviewed and merged:

- do not start S2B AutoCAD integration/live acceptance;
- do not start S3 exact-base Xref extraction;
- do not start R1-R8;
- do not execute old VS-T4 through VS-T8 unchanged;
- do not add production Codex repair planning;
- do not add a second OCR engine, dimension recognizer, solver, DXF builder,
  AutoCAD transport/dispatcher, repair executor, manifest/checkpoint/revision
  truth store, visual-verdict path, or publisher;
- do not bypass or reorder M2 Drawing Initialization.

## 6. Authoritative ownership

```text
primitive_ir_lib
  -> semantic_ir_lib
  -> agent_lib
  -> dxf_builder_lib
  -> mcp_integration_lib
```

- `primitive_ir_lib`: image/PDF recognition, OCR, geometry, tables,
  calibration, and source traces.
- `semantic_ir_lib`: semantic parts, constraints, pruning, and solving.
- `agent_lib`: non-mutating advisory proposals with separate approved apply.
- `dxf_builder_lib`: native DXF/entity generation and headless review/repair.
- `mcp_integration_lib` plus the existing AutoCAD .NET plugin: the only approved
  File IPC and AutoCAD Mechanical boundary.
- `cad_agent`: thin orchestration, run identity, manifests, checkpoints,
  resumability, evidence routing, approval gates, and CLI composition.

## 7. Required review gates

Before accepting either active PR, the PO must verify:

- exact base and exact final head;
- one bounded commit unless the issue explicitly requires otherwise;
- changed files exactly match the issue allowlist;
- no cross-issue overlap or shared central-file modification;
- focused tests, Ruff, architecture checker, `git diff --check`, canonical
  verifier, and GitHub CI on the exact candidate or named synthetic merge;
- all eight Reuse Declaration fields are separate and non-empty;
- unavailable SDK, private data, .NET, File IPC, and AutoCAD gates are reported
  as `SKIP` or `NOT RUN`, never `PASS`;
- no runtime promotion beyond the issue scope.

## 8. Authoritative design and records

- Design: `docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`
- R0 plan: `docs/superpowers/plans/2026-08-04-reuse-integration-rebaseline.md`
- R0 audit: `docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md`
- R0 implementation record: `docs/superpowers/implementation-records/2026-08-04-reuse-integration-rebaseline.md`
- Historical Visual Supervisor rollout: preserved but superseded after VS-T3.

## 9. Next action

- Luna A may implement Issue #48 only on
  `task/s1-codex-sdk-windows-compat`.
- Luna B may implement Issue #49 only on
  `task/s2a-autocad-render-evidence-contract`.
- Each opens one non-draft PR and stops.
- Neither Luna may review, merge, start S2B, S3, or R1 work.
