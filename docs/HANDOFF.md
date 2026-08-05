# CAD Agent — Current Operational Handoff

Status: current operational handoff for PO and coding agents.

Updated: 2026-08-05

Live GitHub state, exact commits, diffs, CI logs, approved specifications, plans,
`docs/STATUS.md`, and `docs/ARCHITECTURE.md` remain the sources of truth.

## 1. Current accepted implementation state

- Repository: `duongchi90/cad-agent`.
- Latest accepted implementation merge:
  `3d0aa999904f384efa4eb42a81637e4270591859`.
- Latest merged PR: #55 — S2B fail-closed native-render File IPC seam.
- Previous accepted implementation merges:
  - `ff6d199ef6cd401ccf5d06bace1135e4e55f1216` — PR #59 R1B;
  - `589d708a69f5c710c0a4c25e52a5b17db9749764` — PR #57 R1A;
  - `a8a962281b2d7480c9444eb8e1b56c6795c108aa` — PR #54 S3A.
- Runtime promotion: none.

The exact implementation base for any task that depends on accepted S2B is
`3d0aa999904f384efa4eb42a81637e4270591859`. Later docs-only commits are not
implementation bases.

## 2. S2B accepted evidence

- Issue #52: completed by PR #55.
- Exact implementation base:
  `393f318317032096ec5e055ed1c928090f3b7e31`.
- Final reviewed head:
  `0ed4cd3a0c0a23cd9a52626fd24e35626288c9d9`.
- Synthetic merge with then-current `main`:
  `fd9bb4153837d60483a00b6e3e3fc3a9d80c70e9`.
- Accepted squash merge:
  `3d0aa999904f384efa4eb42a81637e4270591859`.
- Exactly 15 Issue #52 allowlisted files.
- The branch had two bounded commits; the second added only two missing C#
  validator helper overloads. PO accepted the narrow compile-completion change
  and squash-merged both into one main commit.
- Local mandatory .NET gate on final head:
  - restore: PASS;
  - Release/x64 build: PASS;
  - C# tests: 113 passed, 0 failed.
- Autodesk managed references remained external and project references retain
  `Private=false`; no Autodesk DLL was added to the PR.
- Hosted sequential integration:
  - `tests` workflow #346: PASS;
  - offline: 1022 passed plus 18 subtests;
  - offline JUnit: 1040/0/0/0;
  - dotnet IPC JUnit: 38/0/0/0;
  - Reuse Declaration: PASS.
- AutoCAD Mechanical live, actual native capture, and private-data acceptance:
  `NOT RUN`.

Accepted behavior is only the closed File IPC envelope/validator and dispatcher
seam. `native_render_evidence` still returns
`NATIVE_RENDER_NOT_IMPLEMENTED` before drawing-gateway access. No placeholder
artifact, mutation, approval, verdict, repair, or publication path was added.

## 3. R1 accepted offline foundation

### R1A — SourceBundle contract

- PR #57 squash merge:
  `589d708a69f5c710c0a4c25e52a5b17db9749764`.
- Provides the closed deterministic SourceBundle metadata and canonical hash
  boundary.

### R1B — manifest reference binding

- PR #59 squash merge:
  `ff6d199ef6cd401ccf5d06bace1135e4e55f1216`.
- Provides one closed SourceBundle reference in existing image/PDF manifests.
- Legacy unbound manifests remain readable with no injected field.
- No CLI source discovery or source-fusion runtime was promoted.

## 4. Current task state

No implementation task is currently authorized or active.

PR #55 is merged and no longer an environment blocker. Do not continue work on
its old branch. Issue #52 is complete.

The following require separate design/plan/issue/branch gates before coding:

- S2C actual read-only AutoCAD-native capture and live acceptance;
- S3B/S3C exact-base Xref File IPC/live execution;
- R1C SourceBundle byte-integrity audit;
- component/view registry;
- dimension-authority expansion;
- candidate revision orchestration;
- repair-loop, visual verdict, and publication.

## 5. Recommended next bounded work

Priority should be selected from the approved roadmap rather than inferred from
old issue text:

1. **S2C design/task:** implement actual read-only native capture through the
   existing `native_render_evidence` operation and approved .NET drawing
   gateway. Requires AutoCAD Mechanical 2027 live acceptance; code may be
   prepared elsewhere, but the task cannot be accepted without the live gate.
2. **S3B design/task:** extend the accepted S3A exact-base/Xref contract through
   the existing File IPC boundary without creating a second dispatcher.
3. **R1C offline design/task:** verify SourceBundle file existence and SHA-256
   under one safe source root, producing non-authoritative audit evidence only.

These are routing recommendations, not implementation authorization. The PO
must first inspect the current roadmap/specifications, lock the design and
allowlist, then create exact-base issues and branches.

## 6. Authoritative ownership

```text
primitive_ir_lib
  -> semantic_ir_lib
  -> agent_lib
  -> dxf_builder_lib
  -> mcp_integration_lib
```

- recognition/OCR remains in `primitive_ir_lib`;
- semantic solving remains in `semantic_ir_lib`;
- proposal/apply separation remains in `agent_lib`;
- native entity generation/review remains in `dxf_builder_lib`;
- AutoCAD access remains in the existing File IPC/.NET boundary;
- `cad_agent` remains thin orchestration and the sole manifest/checkpoint owner.

No second OCR engine, solver, DXF builder, File IPC transport/dispatcher,
manifest/checkpoint/revision store, repair executor, verdict path, or publisher
is permitted.

## 7. Evidence rule

Do not treat chat claims, branch names, stale PR bodies, or old workflow runs as
proof. Require the exact commit, changed-file list, source diff, appropriate
local/live gate evidence, synthetic-merge CI, and truthful `PASS`, `FAIL`,
`SKIP`, or `NOT RUN` state for every task.
