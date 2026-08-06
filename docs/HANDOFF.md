# CAD Agent — Current Operational Handoff

Status: current operational handoff for PO and coding agents.

Updated: 2026-08-06

Live GitHub state, exact commits, diffs, CI logs, approved specifications, plans,
`docs/STATUS.md`, and `docs/ARCHITECTURE.md` remain the sources of truth.

## 1. Current accepted implementation state

- Repository: `duongchi90/cad-agent`.
- Latest accepted implementation merge:
  `a9968480258e01fda9d4dfbf01a27958b67747bc`.
- Latest merged PR: #65 — S3B exact-base Xref inspection and approved
  extraction.
- Previous accepted implementation merges:
  - `365cb2df47cc3d0232a4b5df1901f55dbe46b22c` — PR #61 S2C actual
    read-only AutoCAD-native layout capture;
  - `ff6d199ef6cd401ccf5d06bace1135e4e55f1216` — PR #59 R1B;
  - `589d708a69f5c710c0a4c25e52a5b17db9749764` — PR #57 R1A;
  - `a8a962281b2d7480c9444eb8e1b56c6795c108aa` — PR #54 S3A.
- Runtime promotion: no source-fusion, repair, verdict, or publication runtime
  is promoted.

The accepted S2C implementation head is
`365cb2df47cc3d0232a4b5df1901f55dbe46b22c`. Later docs-only commits are not
implementation bases.

## 2. Accepted S2B boundary

S2B provides the closed `native_render_evidence` File IPC request/result
contract, Python client adapter, C# validator, and dispatcher registration.
The accepted seam still returns `NATIVE_RENDER_NOT_IMPLEMENTED` before drawing
access. Its mandatory .NET gate passed with 113 C# tests and hosted sequential
integration passed. AutoCAD Mechanical live/native capture remained `NOT RUN`.

S2C may replace only that unsupported dispatcher path through the existing
drawing gateway. It may not add a second transport, queue, dispatcher, protocol,
renderer fallback, verdict, approval, repair, or publication path.

## 3. Accepted S2C — Issue #60

S2C is accepted at merge commit
`365cb2df47cc3d0232a4b5df1901f55dbe46b22c` (PR #61) for the bounded
read-only AutoCAD-native layout capture scope. The branch and plan references
below are the historical implementation record.

Issue: #60 — actual read-only AutoCAD-native layout capture.

Historical implementation branch: `task/s2c-autocad-native-render`.

Exact implementation base:
`3d0aa999904f384efa4eb42a81637e4270591859`.

Approved design on the branch:
`docs/superpowers/specs/2026-08-05-autocad-native-render-s2c-design.md`.

Approved implementation plan on the branch:
`docs/superpowers/plans/2026-08-05-autocad-native-render-s2c.md`.

The branch was prepared with two PO docs-only commits:

- design commit: `091f189bacf21f4d67c228672ff0137ac0af8f84`;
- plan head: `2febca49526f560cd0daaa631aecc262936e8695`.

Those commits were preparation only; the accepted implementation is the S2C
merge recorded above.

### Locked S2C profile

- named paper-space layout only;
- A4;
- white background;
- 300 DPI;
- fit-to-paper enabled;
- `monochrome.ctb`;
- PNG or one-page PDF;
- fixed approved PDF and PNG PC3 devices on AutoCAD Mechanical 2027;
- no device/media/style fallback.

### Locked artifact boundary

```text
<CAD_AGENT_DOTNET_IPC_DIR>/native-render/<request_id>/artifact.png
<CAD_AGENT_DOTNET_IPC_DIR>/native-render/<request_id>/artifact.pdf
```

`artifact.relative_path` is relative to the IPC root. No request output path or
`artifact_directory` field is permitted. Request ownership, safe canonical
containment, exclusive collision handling, temporary byte validation, and
no-overwrite atomic publication are mandatory.

### Read-only gate

Success requires unchanged DBMOD, unchanged on-disk DWG SHA-256, restored
session state/current layout, `changed=false`, and `entity_handles=[]`. Failed
restoration or any invariant produces a failure with `payload={}` and no final
artifact publication.

### Contract and allowlist gate

S2A/S2B schemas and Python production validators remain frozen. Exactly the 20
Issue #60 allowlisted paths may change. If another existing `IDrawingGateway`
implementation or test double requires a change, Codex stops and reports the
exact path instead of expanding scope.

## 4. Accepted S3B boundary

S3B is accepted on PR #65 and merge
`a9968480258e01fda9d4dfbf01a27958b67747bc` for exact-base Xref inspection and
approved extraction. The accepted boundary is:

- source Xrefs and accepted DWGs are read-only and remain immutable;
- inspection is server-built and extraction performs fresh live preflight
  immediately before mutation;
- extraction creates only new disposable candidates;
- allowed local transforms are translation, rotation, and positive uniform
  scale only;
- evidence preserves source handle, layer, block, source revision, source hash,
  and `REUSED_FROM_BASE_CAD` provenance;
- AutoCAD Mechanical live acceptance remains `NOT RUN`;
- private drawing/source-data acceptance remains `NOT RUN`.

Runtime verification head: `9f5dc302643fdfae77cbda65dd6cdc0c8deccc59`.
Record-only final head: `67c3496da313245fc9ceeee26814e099b32f2c87`.

## 5. Future-slice selection gate

No next runtime slice is selected or authorized by this handoff. Any future
runtime work requires a separate Issue, exact base, branch, allowlist,
verification gates, live/private-data gate decisions, and explicit PO
authorization before repository changes begin.

## 6. Locked work

Until a future-slice selection gate is separately accepted, keep locked:

- S3C repair/publication;
- R1C SourceBundle byte-integrity audit or source-fusion runtime;
- component/view registry;
- dimension-authority expansion;
- candidate revision orchestration;
- repair-loop integration;
- visual verdict or publication;
- duplicate OCR, solver, DXF builder, File IPC transport/dispatcher,
  manifest/checkpoint/revision store, repair executor, verdict path, or
  publisher.

## 7. Authoritative ownership

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
- AutoCAD access remains in the existing File IPC/.NET drawing-gateway boundary;
- `cad_agent` remains thin orchestration and the sole manifest/checkpoint owner.

## 8. Next action

Issue #68 / PR #69 is the accelerated reuse-first program planning record.
This program remains planning/governance only; GitHub is the live source of PR
state, and this handoff must not cache whether PR #69 is open, draft, merged, or
closed.

- Program design: `docs/superpowers/specs/2026-08-06-accelerated-reuse-first-program-design.md`.
- Program plan: `docs/superpowers/plans/2026-08-06-accelerated-reuse-first-program.md`.
- Planning branch: `planning/accelerated-reuse-first-program`.
- Exact planning base: `d00b24e4853d2bfa6bd94873d3014e37575e2718`.
- Before PR #69 merges, complete the PO review and merge gate.
- After PR #69 merges, verify fresh `main` at the program merge SHA, then create
  three separate Wave 1 Issues: official vision handoff, R1C source
  integrity/fusion, and S2C/S3B live readiness.
- PR #65 / `a9968480258e01fda9d4dfbf01a27958b67747bc` is the latest accepted
  runtime implementation record; this program does not promote runtime.
- PR #67 / `d00b24e4853d2bfa6bd94873d3014e37575e2718` is the accepted governance
  base for this program; after PR #69 merges, its merge SHA becomes the program
  governance head.
- No runtime is automatically authorized by this program or its merge. Each
  Wave 1 Issue still requires its own scope, exact base, allowlist, reuse
  dossier, verification gates, and PO authorization.

Do not begin S3C, R1C implementation, registry, revision, repair, verdict,
publication, or OCR work from this handoff.
