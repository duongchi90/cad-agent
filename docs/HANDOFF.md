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
- Latest accepted implementation base at this handoff update: `c325d009c3035be5c3202e3939efd4a82bcd2f42`
- Latest merged implementation PR: #35 — R0-T1 closed reuse-inventory contract and validator
- Completed issue: #34
- PR #31 was closed without merge because the reviewed and merged PR #32 superseded it.

The current `main` may be newer because operational documentation can be committed after the implementation base above. Every new session must resolve the live `main` SHA from GitHub rather than assuming the SHA written here is the branch tip.

R0-T1 added only:

- `contracts/reuse-integration/reuse-inventory.schema.json`
- `contracts/reuse-integration/examples/reuse-inventory.json`
- `scripts/reuse_inventory.py`
- `tests/test_reuse_inventory_contract.py`

R0-T1 did not change the CAD runtime, dependencies, lock file, AutoCAD behavior, repair authority, Visual Supervisor verdict authority, or publication behavior.

## 3. Active task

- Task: R0-T2 — repository-wide reuse inventory and completeness gate
- Issue: #36
- Expected branch: `task/r0-t2-repository-reuse-inventory`
- Required implementation base: `c325d009c3035be5c3202e3939efd4a82bcd2f42`
- PR: none recorded at this handoff update
- Current task authority: Issue #36 plus Task 2 in the approved R0 plan

Allowed files for R0-T2:

- `docs/superpowers/reuse/2026-08-04-reuse-inventory.json`
- `tests/test_reuse_inventory_repository.py`
- `scripts/reuse_inventory.py`

R0-T2 must inventory exactly 20 required capabilities and add a completeness gate. It is audit/governance work only.

## 4. Locked work

Until R0-T2 is reviewed and merged:

- do not start R0-T3;
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
- AutoCAD, private-data, real-drawing, or external-model gates are recorded truthfully as `PASS`, `FAIL`, `SKIP`, or `NOT RUN`;
- `SKIP` and `NOT RUN` are never described as PASS;
- no next task starts before the current issue is reviewed and merged.

GitHub evidence wins when this handoff or a chat is stale.

## 9. Roles

The stable role split is defined in `docs/AI_OPERATING_MODEL.md`.

Summary:

- The user is project owner and engineering authority.
- ChatGPT is the PO/reviewer/governance agent.
- Codex is the implementation agent.
- Visual Supervisor is the independent visual-verdict subsystem, not the coding agent.
- Existing CAD engines and AutoCAD boundaries remain the execution authorities for their domains.

## 10. New-session bootstrap

A new PO chat must begin by reading:

1. `docs/HANDOFF.md`
2. `docs/STATUS.md`
3. `docs/ARCHITECTURE.md`
4. the design and active plan named above
5. the active issue and any current PR

Then verify `main`, issue state, branch/PR, final head, changed files, diff, and CI before making any status claim.

## 11. Next action

Codex may implement Issue #36 only. The PO must review its eventual PR before R0-T3 is issued.
