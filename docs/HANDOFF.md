# CAD Agent — Current Operational Handoff

Status: current operational handoff for PO and coding agents.

Updated: 2026-08-05

Live GitHub state, exact commits, diffs, CI logs, approved specifications, plans,
`docs/STATUS.md`, and `docs/ARCHITECTURE.md` remain the sources of truth.

## 1. Current accepted implementation state

- Repository: `duongchi90/cad-agent`.
- Latest accepted implementation merge:
  `589d708a69f5c710c0a4c25e52a5b17db9749764`.
- Latest merged PR: #57 — R1A closed SourceBundle offline contract.
- Previous accepted implementation merge:
  `a8a962281b2d7480c9444eb8e1b56c6795c108aa` — PR #54 S3A.
- Runtime promotion: none.

### R1A accepted evidence

- Exact implementation base:
  `d547ca8b1eb39651a00109da3862b79bcce4f0f9`.
- Final head: `9efe1b75fbf1720db44c3ca947e4c6d082282c57`.
- Squash merge: `589d708a69f5c710c0a4c25e52a5b17db9749764`.
- Exactly one bounded commit and four allowlisted new files.
- Focused tests: 68 passed.
- Hosted synthetic merge:
  `9c5ded397a67efb1c90ad6eeaa50060d693815a1`.
- Hosted offline: 979 passed plus 18 subtests; JUnit 997/0/0/0.
- Dotnet IPC JUnit: 38/0/0/0.
- Reuse Declaration: PASS after PR-body formatting correction only.
- Private data and AutoCAD Mechanical live: `NOT RUN`.
- No manifest/CLI, source-fusion runtime, registry, revision, repair, verdict, or
  publication implementation was promoted.

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

## 3. Active code task — Issue #58 R1B

Execution mode: `SINGLE_LUNA`.

Issue: #58 — bind SourceBundle reference to existing manifests.

Branch: `task/r1b-source-bundle-manifest-binding`.

Exact implementation base:
`5950e7b056fc92131a243a7e403e4f187c99086f`.

Overlap with PR #55: `PASS`.

Design:
`docs/superpowers/specs/2026-08-05-source-bundle-manifest-binding-design.md`.

Plan:
`docs/superpowers/plans/2026-08-05-source-bundle-manifest-binding.md`.

Goal: add one small closed `source_bundle` reference owned by
`cad_agent.manifest`, validate it in image/PDF readers, preserve all legacy
manifests when unbound, and refuse conflicting or stale bindings.

Exactly four files may change:

1. `cad_agent/manifest.py`
2. `cad_agent/pdf.py`
3. `tests/test_cad_agent_source_bundle_manifest.py`
4. `docs/superpowers/implementation-records/2026-08-05-source-bundle-manifest-binding.md`

Required boundaries:

- reuse R1A validation and canonical hash APIs;
- do not copy SourceBundle items into manifests;
- do not create another writer/store;
- no CLI integration or automatic binding in legacy workflows;
- no source discovery, recognition, source-priority fusion, CAD, authority,
  registry, revision, repair, verdict, or publication behavior;
- no dependency or lock change;
- AutoCAD .NET/live and private data remain `NOT RUN`.

The worker opens one non-draft PR and stops.

## 4. Locked work

Until separately reissued and reviewed, do not start:

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

## 5. Authoritative ownership

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

## 6. Next action

- Luna implements Issue #58 only on
  `task/r1b-source-bundle-manifest-binding`.
- PR #55 remains open and unchanged until approved Autodesk managed references
  make the mandatory .NET gate executable.
- No later task starts from chat claims alone; require commit, diff, PR, and CI
  evidence on the exact candidate.
