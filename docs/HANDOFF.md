# CAD Agent — Current Operational Handoff

Status: current operational handoff for PO and coding agents.

Updated: 2026-08-05

This file is the first repository document to read when continuing the project in a new chat or coding session. It is an operational index, not a replacement for the authoritative architecture, status, specification, plan, PR diff, or CI evidence.

## 1. Source-of-truth order

Use this order whenever sources disagree:

1. Current GitHub repository state: `main`, issue, branch, PR head SHA, changed files, diff, and CI attached to the exact final head.
2. `docs/STATUS.md` for verified/partially verified/NOT RUN gates.
3. `docs/ARCHITECTURE.md` for current package ownership and safety boundaries.
4. The active approved specification and implementation plan named below.
5. This handoff file for navigation and current-task intent.
6. Previous chat messages and historical documents only as context.

Never treat a chat statement, PR body, branch name, or old status note as proof that work exists or passed. Verify the repository evidence directly.

## 2. Current integrated state

- Repository: `duongchi90/cad-agent`
- Latest accepted implementation base at this handoff update: `55736be3ec2dbc93c374868f210b6d833c4f81fa`
- Latest merged implementation PR: #39 — R0-T3 mandatory Reuse Declaration enforcement
- Completed issue: #38
- Previous R0 implementation PR: #37 — R0-T2 repository-wide reuse inventory and completeness gate
- Earlier R0 implementation PR: #35 — R0-T1 closed reuse-inventory contract and validator
- PR #31 was closed without merge because the reviewed and merged PR #32 superseded it.

The current `main` may be newer because operational documentation can be committed after the implementation base above. Every new session must resolve the live `main` SHA from GitHub rather than assuming the SHA written here is the branch tip.

R0-T3 added only:

- `.github/pull_request_template.md`
- `.github/workflows/reuse-declaration.yml`
- `scripts/check_reuse_declaration.py`
- `tests/test_reuse_declaration.py`

R0-T3 requires implementation PRs to provide all eight non-empty Reuse Declaration fields. Docs/non-implementation changes remain auditable and exempt. It did not change CAD runtime packages, CLI behavior, artifact behavior, dependencies, the lock file, AutoCAD behavior, repair authority, Visual Supervisor verdict authority, or publication behavior.

Accepted evidence for PR #39 final head `e3248c1c529d74cbc96fb119f54311bc580a7e65`:

- one bounded implementation commit from base `20be1cff9502115ddeb9171d9f856bddb9f90f63`;
- exactly four allowlisted files changed;
- focused tests: 11 passed;
- GitHub `tests` workflow run #282: success;
- GitHub `reuse-declaration` workflow run #2: success after a metadata-only correction to place the `Files allowed to change:` value on the same line;
- hosted verifier: 776 offline tests passed and 38 dotnet IPC tests passed;
- private real-data unavailable-state probe: 2 SKIP;
- actual private-data/real-drawing acceptance: NOT RUN;
- AutoCAD unavailable-state probe: 9 SKIP;
- actual AutoCAD Mechanical live marker: NOT RUN;
- AutoCAD .NET gate: NOT RUN because the hosted verifier used `-SkipAutoCADDotNet`.

## 3. Active task

- Task: R0-T4 — legacy CLI and artifact compatibility baseline
- Issue: #40
- Expected branch: `task/r0-t4-legacy-compatibility`
- Required implementation base: `55736be3ec2dbc93c374868f210b6d833c4f81fa`
- PR: none recorded at this handoff update
- Current task authority: Issue #40 plus Task 4 in the approved R0 plan

Allowed files for R0-T4:

- `contracts/reuse-integration/legacy-cli-baseline.json`
- `scripts/export_cli_contract.py`
- `tests/fixtures/reuse-rebaseline/legacy-run-manifest-v1.json`
- `tests/test_reuse_legacy_compatibility.py`

R0-T4 snapshots the complete current CLI surface and proves that a historical v1 run manifest remains readable with safe defaults. It must not modify the parser, manifest writer, CAD runtime, dependencies, lock file, or AutoCAD behavior.

Every Reuse Declaration field in the R0-T4 PR body must have a non-empty value on the same line after the colon so the merged R0-T3 workflow can verify it.

## 4. Locked work

Until R0-T4 is reviewed and merged:

- do not start R0-T5, R0-T6, or R0-T7;
- do not start S1, S2, or S3;
- do not start R1–R8;
- do not resume the old VS-T4 or VS-T5 tasks unchanged;
- do not add Codex SDK runtime, Source Fusion runtime, base-CAD extraction, component/view registry, revision orchestration, repair loop, publisher, or previous-drawing library;
- do not replace or duplicate OCR, dimension recognition, semantic solving, DXF generation, AutoCAD File IPC/.NET transport, repair execution, manifests, checkpoints, visual verdict, or publication authority.

M2 Drawing Initialization remains an authoritative product path and must not be bypassed or reordered.

## 5. Authoritative design and plan

Design:

- `docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`

Current implementation plan:

- `docs/superpowers/plans/2026-08-04-reuse-integration-rebaseline.md`

Historical Visual Supervisor rollout:

- `docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md`

The historical rollout remains useful background, but post-VS-T3 tasks must be reissued through the reuse-first plan and include a Reuse Declaration.

## 6. Current product intent

The product must preserve the existing CAD Agent as its execution engine while adding controlled multisource reconstruction around it.

Primary workflows:

1. Image/PDF reconstruction when no exact base CAD exists.
2. Exact-base CAD transformation using a read-only Xref and provenance-bound extraction of unchanged components.
3. Hybrid reconstruction using exact reusable components plus image-derived new/changed components.

Target output:

- one editable DWG;
- canonical geometry in Model Space;
- multiple Layouts for overall and detail sheets;
- native editable AutoCAD entities;
- component/view/dimension provenance;
- candidate revisions rather than in-place overwrite;
- independent Visual Supervisor review;
- selective engineer approval for high-risk, inferred, conflicting, or controlling changes;
- verified promotion and rollback.

A previous-drawing library is explicitly deferred.

## 7. Current package ownership

The existing execution chain remains authoritative:

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
- `mcp_integration_lib` plus AutoCAD .NET plugin: approved File IPC boundary, AutoCAD Mechanical review/repair/evidence operations.
- `cad_agent`: thin orchestration, run identity, manifests, checkpoints, resumability, evidence routing, approval gates, CLI composition.

## 8. Verification rules

Before accepting any task or PR, the PO must verify:

- the PR base and exact final head SHA;
- the changed-file list matches the issue allowlist;
- the diff does not duplicate an existing engine or authority path;
- focused tests and aggregate verifier results belong to the exact final head;
- CI status is read from the exact final head;
- the `reuse-declaration` workflow passes for every implementation PR after R0-T3;
- AutoCAD, private-data, real-drawing, or external-model gates are recorded truthfully as `PASS`, `FAIL`, `SKIP`, or `NOT RUN`;
- `SKIP` and `NOT RUN` are never described as PASS;
- no next task starts before the current issue is reviewed and merged.

GitHub evidence wins when this handoff or a chat is stale.

## 9. Roles

The stable role split is defined in `docs/AI_OPERATING_MODEL.md`.

Summary:

- The user is project owner and engineering authority.
- ChatGPT is the PO/reviewer/governance agent.
- Codex/Luna Max is the implementation agent.
- Visual Supervisor is the independent visual-verdict subsystem, not the coding agent.
- Existing CAD engines and AutoCAD boundaries remain the execution authorities for their domains.

## 10. Parallel Luna Max policy

At every task transition, the PO must explicitly decide and record one of these execution modes:

- `SINGLE_LUNA`: one coding Luna Max owns the bounded issue;
- `PARALLEL_LUNA`: two coding Luna Max agents own two independent issues.

The default during R0 is `SINGLE_LUNA`.

### R0 rule

Until R0-T7 is reviewed and merged, only one Luna Max may create code, commits, branches, or PRs at a time. R0-T3 through R0-T7 form a dependency chain of governance baselines and final SHA-bound verification. A second Luna may perform read-only repository inspection or planning, but must not create an implementation branch or PR.

### First safe two-Luna point

After R0 acceptance, the PO may authorize fresh, separately approved plans for the first parallel pair:

- Luna Max A: `S1 Codex SDK Windows compatibility spike`;
- Luna Max B: `S2 AutoCAD-native render/plot evidence spike`.

R0 acceptance permits planning these spikes; it does not automatically authorize implementation. Each spike still requires its own approved issue and implementation plan.

Do not use `S2 + S3` as the first parallel pair because both are likely to touch AutoCAD plugin, File IPC, dispatcher, or shared AutoCAD contracts.

### Mandatory separation for two Luna agents

Parallel work is allowed only when all conditions below are true:

1. Each Luna has a separate issue, branch, file allowlist, commit history, and PR.
2. Both branches start from the same locked and recorded base SHA.
3. Their allowlists are disjoint and their interfaces are agreed before coding.
4. They do not both modify shared central files such as `cad_agent/cli.py`, `cad_agent/manifest.py`, `mcp_integration_lib/dotnet_ipc.py`, `OperationDispatcher.cs`, or a shared schema.
5. Neither Luna reviews or merges its own PR; the single PO reviews both.
6. The PO merges the PRs sequentially. Before the second merge, its branch must incorporate the new `main` and rerun affected focused tests, Reuse Declaration, and CI if the first merge changed its base assumptions.
7. A failure, overlap, or interface change in either branch pauses the other branch when its assumptions are affected.
8. Parallel execution never bypasses Drawing Setup, human approval, Visual Supervisor independence, private-data gates, AutoCAD live gates, or task stop points.

### PO reminder

Before issuing every new implementation issue, the PO must answer in the issue or handoff:

```text
Execution mode: SINGLE_LUNA or PARALLEL_LUNA
Parallel partner issue: <issue number or none>
Shared base SHA: <exact SHA>
Overlap check: PASS or BLOCKED
Merge order: <issue A then issue B, or not applicable>
```

If these fields cannot be answered confidently, use `SINGLE_LUNA`.

## 11. New-session bootstrap

A new PO chat must begin by reading:

1. `docs/HANDOFF.md`
2. `docs/STATUS.md`
3. `docs/ARCHITECTURE.md`
4. the design and active plan named above
5. the active issue and any current PR

Then verify `main`, issue state, branch/PR, final head, changed files, diff, CI, and the execution mode before making any status claim.

## 12. Next action

Execution mode: `SINGLE_LUNA`.

Codex/Luna Max may implement Issue #40 only. The implementation branch must start from `55736be3ec2dbc93c374868f210b6d833c4f81fa`, even if `main` has a later handoff-only documentation commit. Codex must open one non-draft PR with all eight Reuse Declaration values on the same line as their fields and then stop. The PO must review that PR before R0-T5 is issued.
