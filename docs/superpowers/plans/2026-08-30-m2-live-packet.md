# M2 Mechanical Live Packet — Loaded Plugin Identity Successor

Prepared on 2026-08-30 for the bounded successor to PR #309.

## Frozen implementation and build

- Repository: `duongchi90/cad-agent`
- Branch: `codex/m2-plugin-identity`
- Binary-bearing implementation commit: `50fc0d8a03c2fae12b4363a95ff4369e75645a90`
- Live execution requires this branch to be clean and the exact current GitHub
  PR head to be read immediately before running. The live harness records that
  observed HEAD as `implementation_sha`, `pr_head_sha`, and `harness_sha`.
- AutoCAD product: `AutoCAD Mechanical 2027`
- Exact NETLOAD target:
  `C:\temp\cad-agent-m2-plugin-identity\autocad_plugin\CadAgent.AutoCAD2027\bin\x64\Release\net10.0-windows\CadAgent.AutoCAD2027.dll`
- Expected plugin SHA-256:
  `1ba41145741a41c1e2a8eb50ac9de750cc3688ecb6e85bbb90dcc4f9cf203901`
- The normal main-worktree Release DLL remains locked/unchanged by AutoCAD;
  do not overwrite it. The hash above was captured from the final isolated
  Release build; treat that artifact as immutable and do not rebuild it before
  the live run.

## Current one Human action

The previous security modal was dismissed with **Load Once**, but a read-only
health probe still returned the older plugin contract without
`plugin_binary_path`/`plugin_binary_sha256`. Physically NETLOAD the exact
successor DLL below once; Luna will not click it or synthesize that consent.

For a future fresh session where the modal is absent, the original load command
is:

```text
NETLOAD
C:\temp\cad-agent-m2-plugin-identity\autocad_plugin\CadAgent.AutoCAD2027\bin\x64\Release\net10.0-windows\CadAgent.AutoCAD2027.dll
```

This is the only manual action for the current state. Do not close/restart AutoCAD, save `BVTL.dwg`,
replace the normal Release DLL, or load a different binary. After this action,
Luna runs the prepared harness using observed PID/HWND and validates the health
payload's exact loaded-binary hash; a successful NETLOAD by itself is never a
PASS.

## Exact post-NETLOAD run configuration

The following values are the existing FileIPC/.NET IPC contract and may be
exported by Luna immediately before the run; they are not caller identity:

```powershell
$env:CAD_AGENT_FILE_IPC = '1'
$env:CAD_AGENT_FILE_IPC_DIR = 'C:\temp'
$env:CAD_AGENT_DOTNET_IPC_DIR = 'C:\temp'
$env:CAD_AGENT_AUTOCAD_HWND = '3606504' # observed now; re-observe if the window changes
$env:CAD_AGENT_AUTOCAD_LISP_PATH = 'C:\temp\cad-agent-m2-plugin-identity\mcp_integration_lib\mcp_dispatch.lsp'
$env:CAD_AGENT_M2_RECORD_PATH = 'C:\temp\cad-agent-m2-record.json'
$env:CAD_AGENT_M2_SESSION_ID = 'observed-by-harness'
$env:CAD_AGENT_M2_HUMAN_EVENTS_JSON = '[{"kind":"NETLOAD","count":1,"detail":"manual operator load"}]'
```

The session value above is only an opt-in/comparability capture. The harness
derives the authoritative runtime identity from the AutoCAD HWND/PID and
process path; caller labels cannot establish runtime diversity.

From the clean successor worktree, the exact command is:

```powershell
& 'C:\temp\cad-agent-m2-plugin-identity\.venv-py311\Scripts\python.exe' -m pytest 'mcp_integration_lib\tests\test_m2_mechanical_benchmark_live.py' -q -p no:cacheprovider
```

The harness creates disposable fixture/drawing/probe roots under `C:\temp`,
uses the existing FileIPC and .NET IPC owners, and appends to
`C:\temp\cad-agent-m2-record.json`; its sidecar is
`C:\temp\cad-agent-m2-record.measurements.json`.

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
