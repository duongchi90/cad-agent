# CAD Agent — Current Operational Handoff

Status: current operational handoff for PO and coding agents.

Updated: 2026-08-05

This is the first repository document to read in a new PO or coding session. It is an operational index, not a replacement for GitHub evidence, architecture, status, approved specifications, or implementation plans.

## 1. Source-of-truth order

When sources disagree, use this order:

1. Live GitHub state: `main`, issue, branch, PR, final head SHA, changed files, diff, and CI attached to the exact candidate.
2. `docs/STATUS.md` for verified, partial, `SKIP`, and `NOT RUN` gates.
3. `docs/ARCHITECTURE.md` for ownership and safety boundaries.
4. The active approved specification and plan named below.
5. This handoff for navigation and current-task intent.
6. Old chats and historical documents only as context.

Never treat a chat statement, PR description, branch name, or stale handoff as proof. Verify repository evidence directly.

## 2. Current integrated state

- Repository: `duongchi90/cad-agent`
- Latest accepted implementation base: `db91f3585f20984b7892454b3a5f9a6d2c32a567`
- Latest merged implementation PR: #41 — R0-T4 legacy CLI and artifact compatibility baseline
- Completed issue: #40
- Previous merged R0 PRs:
  - #39 — R0-T3 mandatory Reuse Declaration enforcement
  - #37 — R0-T2 repository-wide reuse inventory and completeness gate
  - #35 — R0-T1 closed reuse-inventory contract and validator
- PR #31 was closed without merge because PR #32 superseded it.

The live `main` may be newer because this handoff can be committed after the accepted implementation base. Every new session must resolve the live `main` SHA instead of assuming the SHA above is the branch tip.

R0-T4 added only:

- `contracts/reuse-integration/legacy-cli-baseline.json`
- `scripts/export_cli_contract.py`
- `tests/fixtures/reuse-rebaseline/legacy-run-manifest-v1.json`
- `tests/test_reuse_legacy_compatibility.py`

R0-T4 snapshots all 37 commands present at the implementation base and verifies that a historical v1 run manifest remains readable with safe defaults. It did not change the parser, manifest writer, runtime, dependencies, lock file, AutoCAD behavior, repair authority, Visual Supervisor authority, or publication behavior.

Accepted evidence for PR #41 final head `0cccce7e8afb567c794801b26a413c57cb484334`:

- exactly one bounded implementation commit from base `55736be3ec2dbc93c374868f210b6d833c4f81fa`;
- exactly four allowlisted files changed;
- focused compatibility tests reported 5 passed;
- deterministic exporter reported 37 commands;
- GitHub `tests` workflow run #286: success;
- GitHub `reuse-declaration` workflow run #3: success;
- CI verified the synthetic merge candidate `4fc91c66de0975c293b79544921c0911980f41e2` combining the final head with the then-current `main`;
- hosted verifier: 781 offline tests passed, 18 subtests passed, and 38 dotnet IPC tests passed;
- offline JUnit: 799 tests, 0 failures, 0 errors, 0 skipped;
- private real-data unavailable-state probe: 2 `SKIP`;
- actual private-data/real-drawing acceptance: `NOT RUN`;
- AutoCAD unavailable-state probe: 9 `SKIP`;
- actual AutoCAD Mechanical live marker: `NOT RUN`;
- AutoCAD .NET gate: `NOT RUN` because verification used `-SkipAutoCADDotNet`.

## 3. Active task

- Task: R0-T5 — architecture boundary ratchet
- Issue: #42
- Expected branch: `task/r0-t5-architecture-boundaries`
- Required implementation base: `db91f3585f20984b7892454b3a5f9a6d2c32a567`
- PR: none recorded at this handoff update
- Current task authority: Issue #42 plus Task 5 in the approved R0 plan
- Execution mode: `SINGLE_LUNA`
- Parallel partner issue: none
- Shared base SHA: `db91f3585f20984b7892454b3a5f9a6d2c32a567`
- Overlap check: `PASS`
- Merge order: not applicable

Allowed files for R0-T5:

- `contracts/reuse-integration/architecture-boundaries.json`
- `scripts/check_architecture_boundaries.py`
- `tests/test_reuse_architecture_boundaries.py`

R0-T5 adds a deterministic read-only scanner and an auditable baseline of accepted existing architecture exceptions. It must block new duplicate engines, AutoCAD ownership violations, direct DXF/OCR ownership violations, and second truth-store paths without changing runtime behavior.

Every Reuse Declaration field in the PR body must have a non-empty value on the same line after its colon.

## 4. Locked work

Until R0-T5 is reviewed and merged:

- do not start R0-T6 or R0-T7;
- do not start S1, S2, or S3;
- do not start R1–R8;
- do not resume old VS-T4 or VS-T5 unchanged;
- do not add Codex SDK runtime, Source Fusion runtime, base-CAD extraction, component/view registry, revision orchestration, repair loop, publisher, or previous-drawing library;
- do not replace or duplicate OCR, dimension recognition, semantic solving, DXF generation, AutoCAD File IPC/.NET transport, repair execution, manifests, checkpoints, visual verdict, or publication authority.

M2 Drawing Initialization remains authoritative and may not be bypassed or reordered.

## 5. Authoritative design and plan

Design:

- `docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`

Current implementation plan:

- `docs/superpowers/plans/2026-08-04-reuse-integration-rebaseline.md`

Historical Visual Supervisor rollout:

- `docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md`

The historical rollout remains background only. Post-VS-T3 work must be reissued through the reuse-first process and include a complete Reuse Declaration.

## 6. Current product intent

Preserve the current CAD Agent as the execution engine while adding controlled multisource reconstruction around it.

Primary workflows:

1. Image/PDF reconstruction when no exact base CAD exists.
2. Exact-base CAD transformation using read-only Xref and provenance-bound extraction of unchanged components.
3. Hybrid reconstruction using exact reusable components plus image-derived new or changed components.

Target output:

- one editable DWG;
- canonical Model Space geometry;
- multiple Layouts for overall and detail sheets;
- native editable AutoCAD entities;
- component, view, and dimension provenance;
- candidate revisions rather than in-place overwrite;
- independent Visual Supervisor review;
- selective engineer approval for high-risk, inferred, conflicting, or controlling changes;
- verified promotion and rollback.

A previous-drawing library remains deferred.

## 7. Current package ownership

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

## 8. Verification rules

Before accepting any task or PR, the PO must verify:

- required implementation base and exact final head SHA;
- changed-file list against the issue allowlist;
- one bounded commit unless the task explicitly authorizes otherwise;
- no duplicate engine, truth store, dispatcher, repair authority, verdict authority, or publisher;
- focused tests and verifier evidence belong to the exact candidate or clearly identified synthetic merge candidate;
- `tests` and `reuse-declaration` workflows pass;
- PR body has all eight same-line non-empty Reuse Declaration values;
- private-data, real-drawing, AutoCAD, and external-model gates are reported truthfully as `PASS`, `FAIL`, `SKIP`, or `NOT RUN`;
- `SKIP` and `NOT RUN` are never described as `PASS`;
- no next task starts before the current issue is reviewed and merged.

GitHub evidence wins whenever this handoff or a chat is stale.

## 9. Roles

The stable role split is defined in `docs/AI_OPERATING_MODEL.md`.

- The user is project owner and engineering authority.
- ChatGPT is the PO, reviewer, and governance agent.
- Codex/Luna Max is the implementation agent.
- Visual Supervisor is an independent visual-verdict subsystem, not the coding agent.
- Existing CAD engines and AutoCAD boundaries remain execution authorities for their domains.

## 10. Parallel Luna Max policy

At every task transition, the PO must explicitly choose and record:

- `SINGLE_LUNA`: one coding Luna owns one bounded issue;
- `PARALLEL_LUNA`: two coding Lunas own two independent issues.

The default during R0 is `SINGLE_LUNA`.

### R0 rule

Until R0-T7 is reviewed and merged, only one Luna may create code, commits, implementation branches, or PRs at a time. A second Luna may perform read-only inspection or planning but may not implement another issue.

### First safe two-Luna point

After R0 acceptance, the PO may prepare separately approved plans for the first parallel pair:

- Luna A: `S1 Codex SDK Windows compatibility spike`;
- Luna B: `S2 AutoCAD-native render/plot evidence spike`.

R0 acceptance permits planning; it does not automatically authorize implementation. Each spike still requires a fresh plan, issue, base SHA, allowlist, tests, PR, and review.

Do not use `S2 + S3` as the first parallel pair because both are likely to touch the AutoCAD plugin, File IPC, dispatcher, or shared AutoCAD contracts.

### Mandatory separation for two Luna agents

Parallel work is allowed only when:

1. Each Luna has a separate issue, branch, file allowlist, commit history, and PR.
2. Both branches start from the same locked base SHA.
3. Allowlists are disjoint and interfaces are agreed before coding.
4. Both do not modify shared central files such as `cad_agent/cli.py`, `cad_agent/manifest.py`, `mcp_integration_lib/dotnet_ipc.py`, `OperationDispatcher.cs`, or a shared schema.
5. Neither Luna reviews or merges its own PR; one PO reviews both.
6. The PO merges sequentially. Before the second merge, its branch incorporates the new `main` and reruns affected tests and CI when assumptions changed.
7. A failure, overlap, or interface change pauses the other branch whenever its assumptions are affected.
8. Parallel execution never bypasses Drawing Setup, human approval, Visual Supervisor independence, private-data gates, AutoCAD live gates, or stop points.

### PO reminder

Before every implementation issue, record:

```text
Execution mode: SINGLE_LUNA or PARALLEL_LUNA
Parallel partner issue: <issue number or none>
Shared base SHA: <exact SHA>
Overlap check: PASS or BLOCKED
Merge order: <issue A then issue B, or not applicable>
```

When these fields cannot be answered confidently, use `SINGLE_LUNA`.

## 11. New-session bootstrap

A new PO session must read:

1. `docs/HANDOFF.md`
2. `docs/STATUS.md`
3. `docs/ARCHITECTURE.md`
4. the active design and plan
5. the active issue and any current PR

Then verify live `main`, issue state, branch/PR, final head, changed files, diff, CI, and execution mode before making a status claim.

## 12. Next action

Execution mode: `SINGLE_LUNA`.

Codex/Luna Max may implement Issue #42 only. The implementation branch must start from `db91f3585f20984b7892454b3a5f9a6d2c32a567`, even if live `main` has a later handoff-only documentation commit. Open one non-draft PR with all eight Reuse Declaration values on the same line and then stop. The PO must review and merge it before R0-T6 is issued.
