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

Never treat a chat statement, branch name, PR body, or stale workflow run as
proof without checking the exact commit and synthetic merge candidate.

## 2. Current integrated state

- Repository: `duongchi90/cad-agent`
- Latest accepted implementation base: `393f318317032096ec5e055ed1c928090f3b7e31`
- Latest merged PR: #51 — S2A AutoCAD-native render evidence offline contract
- Previous merged PR: #50 — S1 Codex SDK Windows compatibility spike
- Completed issues: #49 and #48
- R0 state: accepted for governance/rebaseline scope only.
- Runtime promotion: none.

### S1 accepted evidence

- Implementation head: `b3f2ddeb2773fbb4cd94ee1364d0a50cb770944b`.
- Squash merge: `ca85f2329e606bb307f8dece0bc1081575eec136`.
- Exactly one bounded commit and four Issue #48 allowlisted files.
- Focused tests: 14 passed.
- Sequential hosted verification before merge: 804 offline tests plus 18
  subtests; offline JUnit 822/0/0/0; dotnet IPC JUnit 38/0/0/0.
- Official SDK inspection/probe is optional and fail-closed; no login, model
  turn, repair execution, dependency/lock change, or production integration.

### S2A accepted evidence

- Implementation head: `43903547130625b9edf9261536bf6653da7a4736`.
- Squash merge: `393f318317032096ec5e055ed1c928090f3b7e31`.
- Exactly one bounded commit and four Issue #49 allowlisted files.
- Focused tests: 58 passed.
- Final sequential integration candidate:
  `2b0df841de8ef5bce6ad52be7c00cff68f001dd2`, combining S2A with current
  main containing S1.
- `tests` run #314 and `reuse-declaration` run #16: success.
- Integrated hosted verification: 862 offline tests plus 18 subtests; offline
  JUnit 880/0/0/0; dotnet IPC JUnit 38/0/0/0.
- File IPC integration, C# native capture, AutoCAD .NET, AutoCAD Mechanical
  live, private-data acceptance, and visual verdict remain `NOT RUN` or not
  implemented.

The live `main` may become newer because this handoff is a later operational
commit. Both active implementation branches below were created from exact base
`393f318317032096ec5e055ed1c928090f3b7e31` and must not silently use the later
handoff-only commit as their implementation base.

## 3. Active parallel code tasks

Execution mode: `PARALLEL_LUNA`.

Shared base SHA: `393f318317032096ec5e055ed1c928090f3b7e31`.

Overlap check: `PASS`.

Merge policy: independent PO review, then sequential merge. After the first PR
merges, the second PR must receive fresh synthetic-merge CI against current
`main`. A stale workflow using an earlier merge ref is not sufficient.

### Luna A — Issue #52

Task: S2B File IPC envelope and fail-closed native-render dispatcher seam.

Branch: `task/s2b-native-render-ipc-seam`.

Scope:

- extend the existing request/result schemas and examples;
- add one `native_render_evidence` adapter to `DotNetIPCClient`;
- register and validate the operation in the existing C# contract/dispatcher;
- return a deterministic unsupported/fail-closed result until S2C implements
  actual AutoCAD-native capture;
- run Python, schema, C# restore/build/test, architecture, canonical, and CI
  verification.

It must not modify `IDrawingGateway`, `CommandContext`, AutoCAD database/plot
code, dependencies, or lock files. It must not create placeholder render
artifacts or claim that native rendering works.

### Luna B — Issue #53

Task: S3A exact-base Xref inspection and extraction offline contract.

Branch: `task/s3a-exact-base-xref-contract`.

Allowed files:

- `mcp_integration_lib/exact_base_xref.py`
- `mcp_integration_lib/tests/test_exact_base_xref.py`
- `mcp_integration_lib/tests/fixtures/exact-base-xref-inspection.json`
- `docs/superpowers/implementation-records/2026-08-05-exact-base-xref-offline.md`

This is a pure-Python contract slice for exact-base identity, eligibility,
critical-dimension comparison, inspected components, frozen source provenance,
and bounded extraction planning. It must not attach an Xref, copy entities,
mutate a DWG, modify File IPC/C#, create a component registry, or claim live
extraction.

## 4. Code-first, AutoCAD-live-later policy

The current priority is deterministic code, contracts, adapters, schemas,
fixtures, and offline/unit tests before requiring a running AutoCAD Mechanical
session.

This policy does not convert missing live evidence into a pass:

- S2B may establish only the envelope and fail-closed dispatcher seam;
- S2 remains incomplete until S2C implements actual read-only native capture
  and the approved AutoCAD live gate runs;
- S3A may establish only inspection/extraction-plan contracts;
- S3 remains incomplete until later File IPC/.NET and live Xref slices run;
- private-data, actual CAD mutation, and AutoCAD live gates remain `NOT RUN`
  until executed on an approved disposable environment;
- code-complete or offline-verified does not mean production-ready.

## 5. Locked work

Until Issues #52 and #53 are independently reviewed and merged:

- do not start S2C actual AutoCAD-native capture;
- do not start S3B/S3C File IPC/live Xref work;
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

- exact implementation base and exact final head;
- bounded commit history;
- changed files exactly match the issue allowlist;
- no overlap between Issues #52 and #53;
- focused tests, Ruff, architecture checker, `git diff --check`, canonical
  verifier, and GitHub CI on the exact candidate or named synthetic merge;
- S2B C# restore/build/test pass because it changes managed contract code;
- all eight Reuse Declaration fields are separate and non-empty;
- unavailable private data, File IPC live, AutoCAD .NET/live, and later-slice
  gates are reported as `SKIP` or `NOT RUN`, never `PASS`;
- no runtime promotion beyond the exact issue scope.

## 8. Authoritative design and records

- Design: `docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`
- R0 plan: `docs/superpowers/plans/2026-08-04-reuse-integration-rebaseline.md`
- R0 audit: `docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md`
- R0 implementation record: `docs/superpowers/implementation-records/2026-08-04-reuse-integration-rebaseline.md`
- S1 record: `docs/superpowers/implementation-records/2026-08-05-codex-sdk-windows-spike.md`
- S2A record: `docs/superpowers/implementation-records/2026-08-05-autocad-render-evidence-offline.md`
- Historical Visual Supervisor rollout: preserved but superseded after VS-T3.

## 9. Next action

- Luna A may implement Issue #52 only on
  `task/s2b-native-render-ipc-seam`.
- Luna B may implement Issue #53 only on
  `task/s3a-exact-base-xref-contract`.
- Each opens one non-draft PR and stops.
- Neither Luna may review, merge, start S2C, S3B/S3C, or R1 work.
