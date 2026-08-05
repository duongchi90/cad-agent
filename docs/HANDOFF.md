# CAD Agent — Current Operational Handoff

Status: current operational handoff for PO and coding agents.

Updated: 2026-08-05

This is the first repository document to read in a new PO or coding session. It is an operational index, not a replacement for GitHub evidence, architecture, status, approved specifications, or implementation plans.

## 1. Source-of-truth order

When sources disagree, use this order:

1. Live GitHub state: `main`, issue, branch, PR, final head SHA, changed files, diff, and CI attached to the exact candidate.
2. `docs/STATUS.md` for verified, partial, `SKIP`, and `NOT RUN` gates.
3. `docs/ARCHITECTURE.md` for package ownership and safety boundaries.
4. The active approved specification and implementation plan.
5. This handoff for navigation and current-task intent.
6. Old chats and historical documents only as context.

Never treat a chat statement, PR description, branch name, or stale handoff as proof. Verify repository evidence directly.

## 2. Current integrated state

- Repository: `duongchi90/cad-agent`
- Latest accepted implementation base: `cac38a1cf558aee1245ae669bcc106bf3619b8e5`
- Latest merged implementation PR: #43 — R0-T5 architecture boundary ratchet
- Completed issue: #42
- Previous merged R0 PRs:
  - #41 — R0-T4 legacy CLI and artifact compatibility baseline
  - #39 — R0-T3 mandatory Reuse Declaration enforcement
  - #37 — R0-T2 repository-wide reuse inventory and completeness gate
  - #35 — R0-T1 closed reuse-inventory contract and validator

The live `main` may be newer because this handoff can be committed after the accepted implementation base. Every implementation branch must use the exact base recorded in its issue, not a later handoff-only commit.

R0-T5 added only:

- `contracts/reuse-integration/architecture-boundaries.json`
- `scripts/check_architecture_boundaries.py`
- `tests/test_reuse_architecture_boundaries.py`

The ratchet scans tracked Python and C# files, records reviewed existing exceptions, and blocks unbaselined duplicate-engine, AutoCAD ownership, DXF/OCR ownership, and second-truth-store violations. It does not change runtime behavior.

Accepted evidence for PR #43 final head `53d38754cf12df937b7a977100165ad48d4605e9`:

- exactly one bounded implementation commit from base `db91f3585f20984b7892454b3a5f9a6d2c32a567`;
- exactly three allowlisted files changed;
- focused architecture tests reported 6 passed;
- GitHub `tests` workflow run #290: success;
- GitHub `reuse-declaration` workflow run #5: success after a metadata-only PR-body correction;
- CI verified synthetic merge candidate `b5ae876978fc39710841b84da783e450c32cda5a`;
- hosted verifier: 787 offline tests passed, 18 subtests passed, and 38 dotnet IPC tests passed;
- offline JUnit: 805 tests, 0 failures, 0 errors, 0 skipped;
- private real-data unavailable-state probe: 2 `SKIP`;
- actual private-data/real-drawing acceptance: `NOT RUN`;
- AutoCAD unavailable-state probe: 9 `SKIP`;
- actual AutoCAD Mechanical live marker: `NOT RUN`;
- AutoCAD .NET gate: `NOT RUN` because verification used `-SkipAutoCADDotNet`.

## 3. Active task

- Task: R0-T6 — rebaseline audit report and roadmap supersession
- Issue: #44
- Expected branch: `task/r0-t6-rebaseline-audit`
- Required implementation base: `cac38a1cf558aee1245ae669bcc106bf3619b8e5`
- PR: none recorded at this handoff update
- Current task authority: Issue #44 plus Task 6 in `docs/superpowers/plans/2026-08-04-reuse-integration-rebaseline.md`
- Execution mode: `SINGLE_LUNA`
- Parallel partner issue: none
- Shared base SHA: `cac38a1cf558aee1245ae669bcc106bf3619b8e5`
- Overlap check: `PASS`
- Merge order: not applicable

Allowed files for R0-T6:

- `docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md`
- `docs/ARCHITECTURE.md`
- `docs/STATUS.md`
- `docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md`
- `tests/test_reuse_rebaseline_docs.py`

R0-T6 creates the canonical audit report, links architecture and status to the inventory, and marks the old Visual Supervisor rollout superseded after VS-T3 without deleting historical evidence. It must leave R0 state as `Executing`; R0-T7 owns final aggregate verification and acceptance.

## 4. Locked work

Until R0-T6 is reviewed and merged:

- do not start R0-T7;
- do not start S1, S2, or S3;
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

Historical rollout:

- `docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md`

The historical rollout remains evidence and background. Task 6 must mark its post-VS-T3 tasks superseded without deleting them.

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

At every task transition, the PO must explicitly choose and record:

- `SINGLE_LUNA`: one coding Luna owns one bounded issue;
- `PARALLEL_LUNA`: two coding Lunas own two independent issues.

### R0 rule

Until R0-T7 is reviewed and merged, only one Luna may create code, commits, implementation branches, or PRs at a time. A second Luna may perform read-only inspection or planning but may not implement another issue.

### First safe two-Luna point

After R0 acceptance, the PO may prepare separately approved plans for the first parallel pair:

- Luna A: `S1 Codex SDK Windows compatibility spike`;
- Luna B: `S2 AutoCAD-native render/plot evidence spike`.

R0 acceptance permits planning; it does not automatically authorize implementation. Each spike still requires its own plan, issue, locked base SHA, disjoint allowlist, tests, PR, and review.

Do not use `S2 + S3` as the first pair because both are likely to touch the AutoCAD plugin, File IPC, dispatcher, or shared AutoCAD contracts.

Parallel work is allowed only when:

1. Each Luna has a separate issue, branch, allowlist, commit history, and PR.
2. Both branches start from the same locked base SHA.
3. Allowlists are disjoint and interfaces are agreed before coding.
4. They do not both modify central files such as `cad_agent/cli.py`, `cad_agent/manifest.py`, `mcp_integration_lib/dotnet_ipc.py`, `OperationDispatcher.cs`, or a shared schema.
5. One PO reviews both; neither Luna reviews or merges its own PR.
6. PRs merge sequentially; the second branch incorporates the new `main` and reruns affected verification when assumptions changed.
7. Any overlap, interface change, or failure pauses the affected parallel branch.
8. Parallel execution never bypasses Drawing Setup, human approval, Visual Supervisor independence, private-data gates, AutoCAD live gates, or stop points.

Before every new implementation issue, record:

```text
Execution mode: SINGLE_LUNA or PARALLEL_LUNA
Parallel partner issue: <issue number or none>
Shared base SHA: <exact SHA>
Overlap check: PASS or BLOCKED
Merge order: <issue A then issue B, or not applicable>
```

If these fields cannot be answered confidently, use `SINGLE_LUNA`.

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

Codex/Luna Max may implement Issue #44 only. The implementation branch must start from `cac38a1cf558aee1245ae669bcc106bf3619b8e5`, even if `main` contains a later handoff-only commit. Open one non-draft PR with all eight Reuse Declaration values on separate same-line fields, then stop. The PO must review that PR before R0-T7 is issued.
