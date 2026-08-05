# CAD Agent — Current Operational Handoff

Status: current operational handoff for PO and coding agents.

Updated: 2026-08-05

Live GitHub state, exact commits, diffs, CI logs, approved specifications, plans,
`docs/STATUS.md`, and `docs/ARCHITECTURE.md` remain the sources of truth.

## 1. Current accepted implementation state

- Repository: `duongchi90/cad-agent`.
- Latest accepted implementation merge:
  `ff6d199ef6cd401ccf5d06bace1135e4e55f1216`.
- Latest merged PR: #59 — R1B SourceBundle manifest-reference binding.
- Previous accepted implementation merge:
  `589d708a69f5c710c0a4c25e52a5b17db9749764` — PR #57 R1A.
- Runtime promotion: none.

### R1B accepted evidence

- Exact implementation base:
  `5950e7b056fc92131a243a7e403e4f187c99086f`.
- Final head: `ed05d84028fda3378fdf61ff49e18462a7dbcaff`.
- Squash merge: `ff6d199ef6cd401ccf5d06bace1135e4e55f1216`.
- Exactly one bounded commit and four Issue #58 allowlisted files.
- Focused/regression tests: 55 passed.
- Hosted synthetic merge:
  `dcbbd8327b19e16032e7e55905a769d37caabdaf`.
- Hosted offline: 1015 passed plus 18 subtests; JUnit 1033/0/0/0.
- Dotnet IPC JUnit: 38/0/0/0.
- Reuse Declaration: PASS.
- Private data, AutoCAD .NET, and AutoCAD Mechanical live: `NOT RUN`.
- Legacy image/PDF manifests remain readable without injected fields.
- No CLI/source-discovery, source-fusion runtime, recognition, CAD, authority,
  registry, revision, repair, verdict, or publication behavior was promoted.

### R1A accepted evidence

- Final head: `9efe1b75fbf1720db44c3ca947e4c6d082282c57`.
- Squash merge: `589d708a69f5c710c0a4c25e52a5b17db9749764`.
- R1A remains the authoritative closed SourceBundle metadata contract and
  canonical hash boundary.

## 2. Environment-blocked PR #55 — S2B

- PR: #55.
- Branch: `task/s2b-native-render-ipc-seam`.
- Exact head: `905508a418866ad51d888cad102994d0518b7d1d`.
- Source review and hosted sequential offline CI: acceptable/PASS.
- `.NET SDK 10.0.302`: available.
- `dotnet restore`: exit 0.
- Release x64 build/test remain blocked before valid discovery because approved
  AutoCAD 2027 managed references cannot be resolved:
  `AcCoreMgd.dll`, `AcDbMgd.dll`, and `AcMgd.dll`.
- Classification: environment/reference blocker, not an accepted implementation
  failure.
- Do not amend source to bypass the gate and do not merge until restore,
  Release x64 build, and Release x64 test all exit 0 with zero failures and no
  Autodesk DLL copied to output.

S2C, actual native capture, AutoCAD live, and private data remain locked or
`NOT RUN`.

## 3. Completed task — Issue #58 R1B

Issue #58 is closed as completed by PR #59.

The accepted implementation adds only a closed `source_bundle-reference-1.0`
record owned by `cad_agent.manifest`, validates the optional record in image and
PDF readers, preserves legacy manifests, and rejects malformed or conflicting
bindings.

Do not reopen or extend R1B from chat instructions. Any additional behavior
requires a separately approved design, plan, issue, exact base, allowlist, PR,
and CI evidence.

## 4. Design gate for the next offline slice

R1C has not been issued and no implementation branch is authorized.

The recommended next bounded slice is a SourceBundle byte-integrity audit that:

- validates one accepted SourceBundle;
- resolves its safe relative paths under one explicit source root;
- verifies every file exists and matches the recorded SHA-256;
- produces deterministic non-authoritative audit evidence;
- does not run OCR, PDF rendering, CAD parsing, source-priority fusion, CLI
  orchestration, registry, revision, repair, verdict, or publication.

This recommendation remains a design proposal only until its specification is
reviewed and approved. Do not implement it from this handoff paragraph.

## 5. Locked work

Until separately designed, planned, and reissued, do not start:

- R1C or source-fusion runtime;
- S2C actual AutoCAD-native capture;
- S3B/S3C File IPC/live Xref work;
- component/view registry;
- dimension-authority expansion;
- candidate revision orchestration;
- Codex production repair planning;
- repair-loop integration;
- visual verdict or publication;
- old VS-T4 through VS-T8 unchanged;
- duplicate OCR, solver, DXF builder, AutoCAD transport/dispatcher,
  manifest/checkpoint/revision store, repair executor, verdict path, or publisher.

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
- proposals/apply separation remains in `agent_lib`;
- native entity generation/review remains in `dxf_builder_lib`;
- AutoCAD access remains in the existing File IPC/.NET boundary;
- `cad_agent` remains thin orchestration and the sole manifest/checkpoint owner.

## 7. Next action

- No coding task is active after R1B.
- PR #55 remains open and unchanged until approved Autodesk managed references
  make the mandatory .NET gate executable.
- The PO must complete and obtain approval for the R1C design before creating
  an issue or branch.
- No task starts from chat claims alone; require commit, diff, PR, and CI
  evidence on the exact candidate.
