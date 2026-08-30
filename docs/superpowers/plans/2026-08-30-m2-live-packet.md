# M2 Mechanical Live Packet — Loaded Plugin Identity Successor

Prepared on 2026-08-30 for the bounded successor to PR #309.

## Frozen implementation and build

- Repository: `duongchi90/cad-agent`
- Branch: `codex/m2-plugin-identity`
- Runtime-bearing implementation/build head: `e8a42a575b7bf0c8b5561ee84ec78388093a8c05`
- Current clean successor source head: `f24e0de0e0d09e1f41647b995936b7d066a24c91`
- Live execution requires this branch to be clean and the exact current GitHub
  PR head to be read immediately before running. The live harness records that
  observed HEAD as `implementation_sha`, `pr_head_sha`, and `harness_sha`.
- AutoCAD product: `AutoCAD Mechanical 2027`
- Exact NETLOAD target:
  `C:\temp\cad-agent-m2-plugin-identity\autocad_plugin\CadAgent.AutoCAD2027\bin\x64\Release\net10.0-windows\CadAgent.AutoCAD2027.dll`
- Expected plugin SHA-256:
  `f7d3467a57ccb186b78d515ffe737afba08d3d3c691e0518e020a16ddfcbf40c`
- The normal main-worktree Release DLL remains locked/unchanged by AutoCAD;
  do not overwrite it. The hash above was captured from the final isolated
  Release build; treat that artifact as immutable and do not rebuild it before
  the live run.

- The final M2 fixture is guarded against proxy/class-indexed entity records and
  is reviewed again after byte normalization; the before/after semantic review
  results must be identical.

## Current M2 acceptance state

M2 representative live acceptance is PASS. The final AutoCAD Mechanical 2027
process PID/HWND `27812/10881220` had the exact successor artifact resident and
produced the fourth successful comparable epoch. The append-only record now has
four successful comparable epochs across the two observed identities
`acad-pid-1720-hwnd-1378378` and `acad-pid-27812-hwnd-10881220`. No further
Human action is required for this M2 gate.

The bounded manual load sequence that produced the second identity was:

```text
NETLOAD
C:\temp\cad-agent-m2-plugin-identity\autocad_plugin\CadAgent.AutoCAD2027\bin\x64\Release\net10.0-windows\CadAgent.AutoCAD2027.dll
APPLOAD
C:\temp\cad-agent-m2-plugin-identity\mcp_integration_lib\mcp_dispatch.lsp
Load Once
```

Do not save `BVTL.dwg`, replace the normal Release DLL, or load a different
binary. The successful epoch was then run with the observed HWND. A successful
NETLOAD by itself is never a PASS; the semantic live result and append-only
record are the acceptance evidence.

## Exact post-NETLOAD run configuration

The following values are the existing FileIPC/.NET IPC contract and may be
exported by Luna immediately before the run; they are not caller identity:

```powershell
$env:CAD_AGENT_FILE_IPC = '1'
$env:CAD_AGENT_FILE_IPC_DIR = 'C:\temp'
$env:CAD_AGENT_DOTNET_IPC_DIR = 'C:\temp'
$env:CAD_AGENT_AUTOCAD_HWND = '10881220'
$env:CAD_AGENT_AUTOCAD_LISP_PATH = 'C:\temp\cad-agent-m2-plugin-identity\mcp_integration_lib\mcp_dispatch.lsp'
$env:CAD_AGENT_M2_RECORD_PATH = 'C:\temp\cad-agent-m2-record-r2.json'
$env:CAD_AGENT_M2_SESSION_ID = 'operator-live-epoch-20260830-pid27812-r9'
$env:CAD_AGENT_M2_HUMAN_EVENTS_JSON = '[{"kind":"NETLOAD","count":1,"detail":"manual load of frozen isolated artifact in fresh AutoCAD process"},{"kind":"APPLOAD","count":1,"detail":"manual load of mcp_dispatch.lsp with Load Once"}]'
```

The observed HWND is captured from the fresh process; it is not caller identity.
The session value above is only an opt-in/comparability capture. The harness
derives the authoritative runtime identity from the AutoCAD HWND/PID and
process path; caller labels cannot establish runtime diversity.

From the clean successor worktree, the exact command is:

```powershell
& 'C:\temp\cad-agent-m2-plugin-identity\.venv-py311\Scripts\python.exe' -m pytest 'mcp_integration_lib\tests\test_m2_mechanical_benchmark_live.py' -q -p no:cacheprovider
```

The harness creates disposable fixture/drawing/probe roots under `C:\temp`,
uses the existing FileIPC and .NET IPC owners, and appends to
`C:\temp\cad-agent-m2-record-r2.json`; its sidecar is
`C:\temp\cad-agent-m2-record-r2.measurements.json`. The existing
`C:\temp\cad-agent-m2-record.json` remains historical append-only evidence and
must not be overwritten.

Current measured state at successor head `5c556b352f401bc084d4ee3f162c77d5df239378`:
the record SHA-256 is
`bbbdc33756b735e32acd7206d02a43f903f5ae944b72917d704260a096044c70`, with
`comparable=4`, `successful=4`, `success_rate=1.0`, and
`representative=true`. The four successful epochs span the distinct observed
runtime identities `acad-pid-1720-hwnd-1378378` and
`acad-pid-27812-hwnd-10881220`. No source, staged DXF, accepted drawing, or
normal Release DLL was mutated.

## Acceptance oracle

M2 is accepted only after at least three successful comparable epochs and at
least two genuinely distinct observed AutoCAD runtime identities. Each epoch
must independently prove:

- headless and live semantic PASS are separate;
- health reports the executing assembly path and exact SHA-256 matching the
  expected artifact;
- geometry/component/dimension checks pass;
- FileIPC/.NET transport attempts, successes, and failures reconcile;
- stale-evidence and wrong-target probes produce observed positive refusals;
- source/staged hashes are unchanged and disposable drawings close without
  save; request/result artifacts and disposable directories are cleaned;
- human intervention is captured, and failures cannot set
  `accepted_comparable` or success.

## Cleanup and invariants

The existing harness performs close-without-save on the disposable document and
verifies cleanup, file release, source/staged integrity, and request/result
removal. If any cleanup or identity evidence is missing, the epoch is recorded
as failed/non-comparable. `BVTL.dwg`, accepted/source drawings, the normal
main-worktree DLL, and the AutoCAD process must remain unchanged.
