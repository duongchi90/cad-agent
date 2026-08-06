# CAD Agent — Current Operational Handoff

Status: current operational handoff for PO and coding agents.

Updated: 2026-08-06

Live GitHub state, exact commits, diffs, CI logs, approved specifications, plans,
`docs/STATUS.md`, and `docs/ARCHITECTURE.md` remain the sources of truth.

## 1. Current accepted implementation state

- Repository: `duongchi90/cad-agent`.
- Latest accepted implementation merge:
  `365cb2df47cc3d0232a4b5df1901f55dbe46b22c`.
- Latest merged PR: #61 — S2C actual read-only AutoCAD-native layout capture.
- Previous accepted implementation merges:
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

## 4. Acceptance state

S2C is accepted on the exact reviewed head `365cb2df` for the read-only layout
capture boundary. It does not authorize any later source-fusion or mutation
flow. The following remain separate future gates:

- exact-base Xref inspection and approved extraction;
- private-data acceptance when an approved private input exists;
- any future production mutation, repair, verdict, or publication.

Private data remains `NOT RUN` unless separately approved.

## 5. Next authorized slice — S3B planning only

S3B is the next authorized planning slice:
`exact-base Xref File IPC/.NET live inspection and approved extraction`.
Planning must reuse the existing File IPC, dispatcher, and drawing gateway and
the S3A validator/extraction plan. The implementation task is not started by
this handoff.

The planning boundary is:

- source Xref is read-only and its hash must remain stable;
- only inspected components with an approved extraction plan may be used;
- allowed local transforms are translation, rotation, and positive uniform
  scale only;
- mutation is limited to disposable/candidate drawings and never overwrites an
  accepted DWG;
- evidence preserves source handle, layer, block, source revision, source hash,
  and `REUSED_FROM_BASE_CAD` provenance;
- vehicle identity, critical dimensions, source hash, inspection membership,
  and invalid transforms fail closed.

## 6. Locked work

Do not start until S3B live acceptance exists:

- S3B implementation/live extraction;
- S3C repair/publication;
- R1C SourceBundle byte-integrity audit or source-fusion runtime;
- component/view registry;
- dimension-authority expansion;
- candidate revision orchestration;
- repair-loop integration;
- visual verdict or publication;
- duplicate OCR, solver, DXF builder, File IPC transport/dispatcher,
  manifest/checkpoint/revision store, repair executor, verdict path, or publisher.

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

Prepare and approve the S3B design/plan on exact base
`365cb2df47cc3d0232a4b5df1901f55dbe46b22c`. Do not implement S3B from this
governance update alone; require a dedicated implementation Issue/PR, exact
branch, allowlist, and live prerequisites. Decide S3C only after S3B live
acceptance. R1C remains locked.
