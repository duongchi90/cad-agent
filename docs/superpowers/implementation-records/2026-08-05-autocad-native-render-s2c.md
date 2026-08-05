# S2C AutoCAD-Native Layout Capture Implementation Record

Status: production implementation and offline gates complete; AutoCAD
Mechanical 2027 live PNG/PDF acceptance is **NOT RUN** because this machine
has no configured live File IPC session. S2C is not accepted until that gate
passes.

## Identity and bounded scope

- Issue: #60, S2C.
- Exact implementation base: `3d0aa999904f384efa4eb42a81637e4270591859`.
- Implementation branch: `task/s2c-autocad-native-render`.
- Verified pre-record head: `6cee32e696e4f40cec966288cc1e72ae58827375`.
- Production implementation commit: `043dfd4`; live gate commit: `6cee32e`.
- Final head is emitted by the later record-only commit and is recorded in
  PR provenance; a commit cannot contain its own object ID without becoming
  self-referential.
- The branch contains the two approved docs-only commits plus the bounded
  implementation, live-test, and this evidence-record change.
- Changed paths remain inside the exact Issue #60 20-file allowlist. No schema,
  Python production, dependency, project, `STATUS.md`, or `HANDOFF.md` file
  changed.

## Reuse Declaration

Existing capability inspected: existing File IPC request/result store,
`ContractValidator`, `OperationDispatcher`, `IDrawingGateway`, active-document
identity check, `CommandContext.AutoCadDrawingGateway`, Autodesk managed Plot
API references, and the existing `DotNetIPCClient.native_render_evidence()`
contract path.

Existing API reused: existing File IPC root and dispatcher, contract result
envelope, gateway abstraction, AutoCAD `PlotSettings`/
`PlotSettingsValidator`/`PlotInfo`/`PlotInfoValidator`/`PlotEngine` APIs, and
existing live trigger/client helpers.

Adapter required: one `IDrawingGateway.ReadNativeRenderEvidence` adapter and
one AutoCAD-native reader behind the existing gateway; one request-owned
`NativeRenderArtifactBoundary` for safe temporary output and atomic publish.

New capability genuinely missing: read-only AutoCAD paper-space A4 capture to
PNG or one-page PDF, with exact PC3/media selection, DBMOD/DWG/session-state
invariants, and hash-verified request-owned artifact publication.

Files allowed to change: only the 20 paths locked by Issue #60; the exact list
is preserved in the approved plan and issue.

Files forbidden to duplicate: schemas, Python production validators or IPC
transport, a second dispatcher/transport/renderer, Autodesk DLLs in the
repository, verdict/approval/repair/publication owners, dependencies,
`STATUS.md`, and `HANDOFF.md`.

Compatibility behavior: existing operations and S2A/S2B schemas remain
unchanged. Native render accepts only paper-space A4, white, 300 DPI,
fit-to-paper, `monochrome.ctb`, and PNG/PDF. Failures return no artifact
payload; success returns `changed=false`, no entity handles, equal non-negative
DBMOD values, and a relative path below
`IPC_ROOT/native-render/<request_id>/`.

Migration and rollback path: review and merge the single PR only after the
live gate. Roll back the S2C implementation/live-test commits if required;
the pre-existing S2B fail-closed seam remains the safe fallback. No artifact
cleanup or maintenance job is introduced by S2C.

## Implementation boundaries

- The existing File IPC root is reused; no `artifact_directory` is accepted.
- The .NET side owns `native-render/<request_id>/`, uses the validated request
  ID unchanged, rejects traversal/control/drive/path separators, rejects
  reparse points, and uses an exclusive claim.
- Plot output is written to a same-directory temporary file and published with
  no-overwrite atomic rename only after byte validation and SHA-256 hashing.
- PNG signature/IHDR/dimension/IEND and one-page PDF header/EOF/page-count
  checks run before publication. Failed output has no final artifact.
- `BACKGROUNDPLOT` is snapshotted, set to foreground plotting, and restored in
  all exit paths. Current layout, drawing database, and file bytes are not
  modified or saved.
- `layout.identity` is correlation metadata; `layout.name` selects the actual
  paper-space AutoCAD layout. No entity handles, verdict, approval, repair, or
  publication result is produced.

## Verification evidence

### Offline and .NET

- `dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 -p:AutodeskReferenceDir="C:\\Program Files\\Autodesk\\AutoCAD 2027" --no-restore`
  exited `0`: **141 passed, 0 failed, 0 skipped**.
- Focused artifact boundary: **13 passed**.
- Focused read-only policy: **14 passed**.
- Focused dispatcher native-render tests: **2 passed**.
- Python S2A/S2B contract tests: **7 passed**.
- Ruff on affected Python tests: **PASS**.
- Architecture boundary checker: **PASS**.
- `git diff --check`: **PASS**.
- .NET SDK: `10.0.301`.
- Autodesk reference directory: `C:\Program Files\Autodesk\AutoCAD 2027`.
- Built plugin assembly SHA-256 for the implementation candidate:
  `6df76e263c5e28c7ae92e5d823fcf35979bd3e7fdbec84b263b56c4f72b23112`.
- No Autodesk managed DLLs were copied into the repository or plugin output.

### AutoCAD Mechanical live gate

- AutoCAD 2027 `acad.exe` is installed at
  `C:\Program Files\Autodesk\AutoCAD 2027\acad.exe`.
- At verification time there was no running AutoCAD process, no
  `CAD_AGENT_AUTOCAD_HWND`, no `CAD_AGENT_AUTOCAD_LISP_PATH`, no
  `CAD_AGENT_DOTNET_IPC_DIR`, no `CAD_AGENT_FILE_IPC=1`, no
  `CAD_AGENT_S2C_LIVE=1`, and no `CAD_AGENT_LEAN_DISPOSABLE_DWG`.
- Command:

  ```powershell
  & 'C:\temp\cad-agent-s2c-py311\Scripts\python.exe' -m pytest mcp_integration_lib/tests/test_dotnet_ipc_live.py -m autocad_mechanical -ra -p no:cacheprovider
  ```

  exited `0`: **3 skipped, 5 deselected**. The S2C class itself was skipped
  by its explicit prerequisite guard. This is **NOT RUN**, not acceptance.
- Live PNG artifact: **NOT RUN**.
- Live PDF artifact: **NOT RUN**.
- Duplicate, missing-layout, unsupported-profile, and missing-device/media
  refusal probes: **NOT RUN**.
- Product/profile, disposable DWG hash, exact layout, PC3 output, canonical
  media, DBMOD, current-layout, and restored-session live evidence: **NOT RUN**.
- Approved profile constants are fixed in the reader as:
  `AutoCAD PDF (General Documentation).pc3`, `PublishToWeb PNG.pc3`, and
  `ISO_A4_(210.00_x_297.00_MM)`.

### Other gates and scope

- Private-data/real-drawing gate: **NOT RUN**; no private data was supplied.
- Verdict: **NOT IMPLEMENTED**.
- Approval: **NOT IMPLEMENTED**.
- Repair: **NOT IMPLEMENTED**.
- Publication: **NOT IMPLEMENTED**.
- S3B and R1C: not started by this task.

The PR must remain open for PO review and live AutoCAD Mechanical 2027 PNG/PDF
acceptance. Offline success does not promote this implementation to accepted
S2C status.
