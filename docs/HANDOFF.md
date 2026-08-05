# CAD Agent — Current Operational Handoff

Status: current operational handoff for PO and coding agents.

Updated: 2026-08-05

This is the first repository document to read in a new PO or coding session. It is an operational index, not a replacement for live GitHub evidence, architecture, status, approved specifications, or implementation plans.

## 1. Source-of-truth order

When sources disagree, use this order:

1. Live GitHub state: `main`, issue, branch, PR, exact final head, changed files, diff, and CI.
2. `docs/STATUS.md` for verified, partial, `SKIP`, and `NOT RUN` gates.
3. `docs/ARCHITECTURE.md` for ownership and safety boundaries.
4. The active approved specification and plan.
5. This handoff for navigation and current-task intent.
6. Old chats and historical documents only as context.

Never treat a chat statement, PR description, branch name, or stale handoff as proof. Verify repository evidence directly.

## 2. Current integrated state

- Repository: `duongchi90/cad-agent`
- Latest accepted implementation base: `07a14ce3623024f2df848b2b88ff447980772492`
- Latest merged implementation PR: #45 — R0-T6 reuse integration audit and roadmap supersession
- Completed issue: #44
- Previous merged R0 PRs:
  - #43 — R0-T5 architecture boundary ratchet
  - #41 — R0-T4 legacy CLI and artifact compatibility baseline
  - #39 — R0-T3 mandatory Reuse Declaration enforcement
  - #37 — R0-T2 repository-wide reuse inventory and completeness gate
  - #35 — R0-T1 closed reuse-inventory contract and validator

The live `main` may be newer because this handoff can be committed after the accepted implementation base. Every implementation branch must use the exact base recorded in its issue, not a later handoff-only commit.

R0-T6 added or modified only:

- `docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md`
- `docs/ARCHITECTURE.md`
- `docs/STATUS.md`
- `docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md`
- `tests/test_reuse_rebaseline_docs.py`

Accepted evidence for PR #45 final head `0b987bdc35d3133ce69bc5372faade7bc31aa057`:

- one bounded implementation commit from exact base `cac38a1cf558aee1245ae669bcc106bf3619b8e5`;
- exactly five allowlisted files changed;
- focused Task 6 suite: 30 passed;
- inventory checker: exit 0;
- architecture checker: PASS;
- GitHub `tests` workflow run #294: success;
- GitHub `reuse-declaration` workflow run #7: success after a metadata-only PR-body normalization;
- CI verified synthetic merge candidate `3053a2aa79d2bb09dfd4cafe64a4f80e2bd5e0cb`;
- hosted verifier: 790 offline tests passed, 18 subtests passed, and 38 dotnet IPC tests passed;
- offline JUnit: 808 tests, 0 failures, 0 errors, 0 skipped;
- private-data unavailable-state probe: 2 `SKIP`; actual private-data acceptance: `NOT RUN`;
- AutoCAD unavailable-state probe: 9 `SKIP`; actual AutoCAD Mechanical live acceptance: `NOT RUN`;
- AutoCAD .NET gate: `NOT RUN` because verification used `-SkipAutoCADDotNet`;
- no runtime capability was added or promoted.

## 3. Active task

- Task: R0-T7 — aggregate verification and implementation record
- Issue: #46
- Expected branch: `task/r0-t7-aggregate-verification`
- Required implementation base: `07a14ce3623024f2df848b2b88ff447980772492`
- PR: none recorded at this handoff update
- Current task authority: Issue #46 plus Task 7 in `docs/superpowers/plans/2026-08-04-reuse-integration-rebaseline.md`
- Execution mode: `SINGLE_LUNA`
- Parallel partner issue: none
- Shared base SHA: `07a14ce3623024f2df848b2b88ff447980772492`
- Overlap check: `PASS`
- Merge order: not applicable

Allowed files for R0-T7:

- `docs/superpowers/implementation-records/2026-08-04-reuse-integration-rebaseline.md`
- `docs/STATUS.md`

Task 7 intentionally uses two bounded documentation commits on one branch and one PR:

1. provisional record committed before the full verifier so the tree is clean;
2. final record-only commit after observed evidence is written.

The implementation record must distinguish the fully verified candidate SHA from the later record-only SHA. It may mark R0 accepted only after the focused suite, governance CLIs, Ruff, canonical verifier, and final record-only verification all pass truthfully.

## 4. Locked work

Until R0-T7 is reviewed and merged:

- do not start S1, S2, or S3 implementation;
- do not start R1-R8;
- do not execute old VS-T4 through VS-T8 unchanged;
- do not add Codex SDK runtime, Source Fusion runtime, base-CAD extraction, component/view registry, revision orchestration, repair loop, publisher, or previous-drawing library;
- do not replace or duplicate OCR, dimension recognition, semantic solving, DXF generation, AutoCAD File IPC/.NET transport, repair execution, manifests, checkpoints, visual verdict, or publication authority.

M2 Drawing Initialization remains authoritative and may not be bypassed or reordered.

## 5. Authoritative design and plan

Design:

- `docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`

Current implementation plan:

- `docs/superpowers/plans/2026-08-04-reuse-integration-rebaseline.md`

Canonical audit:

- `docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md`

Historical rollout:

- `docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md`

The historical rollout is explicitly superseded after VS-T3. Its accepted history remains; VS-T4 through VS-T8 must not be executed unchanged.

## 6. Current package ownership

The authoritative execution chain remains:

```text
primitive_ir_lib
  -> semantic_ir_lib
  -> agent_lib
  -> dxf_builder_lib
  -> mcp_integration_lib
```

- `primitive_ir_lib`: image/PDF recognition, OCR/text, geometry, tables, calibration, source traces.
- `semantic_ir_lib`: parts, compounds, constraints, pruning, solving.
- `agent_lib`: advisory proposal and separate approved apply.
- `dxf_builder_lib`: native DXF/entity generation, dimensions, headless review and repair.
- `mcp_integration_lib` plus the AutoCAD .NET plugin: approved File IPC boundary and AutoCAD Mechanical review, repair, and evidence operations.
- `cad_agent`: thin orchestration, run identity, manifests, checkpoints, resumability, evidence routing, approval gates, and CLI composition.

## 7. Verification rules

Before accepting any task or PR, the PO must verify:

- required implementation base and exact final head SHA;
- changed-file list against the issue allowlist;
- bounded commit history;
- no duplicate engine, truth store, dispatcher, repair authority, verdict authority, or publisher;
- focused tests and verifier evidence belong to the exact candidate or a clearly identified synthetic merge candidate;
- `tests` and `reuse-declaration` workflows pass when applicable;
- all eight Reuse Declaration headings have same-line non-empty values;
- private-data, real-drawing, AutoCAD, and external-model gates are reported truthfully;
- `SKIP` and `NOT RUN` are never described as `PASS`;
- no next task starts before the current issue is reviewed and merged.

GitHub evidence wins whenever this handoff or a chat is stale.

## 8. Parallel Luna Max policy

### Current R0 rule

Until R0-T7 is reviewed and merged, use `SINGLE_LUNA`. A second Luna may perform read-only inspection or prepare draft plans, but may not create another implementation branch or PR.

### First safe two-Luna point

After R0 acceptance, the PO may issue a separately planned `PARALLEL_LUNA` pair only after confirming disjoint write sets:

- Luna A: S1 Codex SDK Windows compatibility spike;
- Luna B: S2 AutoCAD-native render/plot evidence spike.

Do not use S2 plus S3 as the first pair because both are likely to touch AutoCAD plugin, File IPC, dispatcher, or shared AutoCAD contracts.

Parallel implementation requires:

1. separate issue, branch, allowlist, commits, tests, PR, and review for each Luna;
2. the same locked base SHA;
3. disjoint allowlists and agreed interfaces before coding;
4. no shared edits to central files such as `cad_agent/cli.py`, `cad_agent/manifest.py`, `mcp_integration_lib/dotnet_ipc.py`, `OperationDispatcher.cs`, or shared schemas;
5. one PO reviews both and merges sequentially;
6. the second PR rebases or incorporates new `main` and reruns affected verification before merge;
7. any overlap, interface change, or failed assumption pauses the affected branch.

## 9. New-session bootstrap

A new PO or coding session must read:

1. `docs/HANDOFF.md`
2. `docs/STATUS.md`
3. `docs/ARCHITECTURE.md`
4. the approved design and active plan
5. the active issue and any current PR

Then verify live `main`, issue state, branch/PR, exact head, changed files, diff, CI, and execution mode before making a status claim.

## 10. Next action

Execution mode: `SINGLE_LUNA`.

Codex/Luna Max may implement Issue #46 only. The branch must start from `07a14ce3623024f2df848b2b88ff447980772492`, even if `main` contains a later handoff-only commit. Open one non-draft PR with the exact verified candidate SHA, the later record-only SHA, observed evidence, and all eight Reuse Declaration values on separate same-line fields, then stop. The PO must review and merge R0-T7 before any S1/S2/S3 implementation begins.
