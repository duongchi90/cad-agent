# M3 Disposable LINE Live Packet — provider-backed follow-up

## Status and boundary

- Packet state: **PREPARED / LIVE NOT RUN**.
- Packet basis: GitHub `main` at
  `d71cf60c7e9809aca9d9c0dbeef13f066b261f23` after PR #315 merged.
- Contract-only evidence is complete in
  `mcp_integration_lib/tests/test_m3_disposable_repair_acceptance.py` and is
  not live/provider evidence.
- Candidate head `910643227299c36ed96c846b6edaf2b2eb4320e9` now supplies the
  RED-first, opt-in callback composition seam and canonical fail-closed record
  oracle at `mcp_integration_lib/m3_live_harness.py` and
  `cad_agent/m3_live_record.py`. Offline contract verification is complete;
  no live command is invented or presented as ready until this candidate is
  hosted-reviewed and a provider-backed AutoCAD epoch is deliberately
  scheduled.
- A subsequent red-team audit (`#301` comment `5468292161`) found and blocked
  four false-PASS paths. The hardening candidate now requires exact canonical
  R5/R6 owner results, zero transport failures/retries, one repair-executor
  attempt bound to the one R6 attempt, and permits an explicitly captured
  zero-Human event list. The hardening itself is still offline/provider-
  callback only and is not live acceptance evidence.

## Frozen implementation and plugin identity

- Repository: `duongchi90/cad-agent`
- Accepted implementation: PR #314, head
  `0a1106fcb6cf435b96971abc506363d4089b795a`.
- AutoCAD product: `AutoCAD Mechanical 2027`.
- Frozen plugin artifact:
  `C:\temp\cad-agent-m2-plugin-identity\autocad_plugin\CadAgent.AutoCAD2027\bin\x64\Release\net10.0-windows\CadAgent.AutoCAD2027.dll`
- Observed SHA-256:
  `f7d3467a57ccb186b78d515ffe737afba08d3d3c691e0518e020a16ddfcbf40c`.
- The artifact exists outside the repository and must not be overwritten or
  rebuilt while an AutoCAD process may have it loaded.
- Existing dispatcher:
  `C:\temp\cad-agent-m2-plugin-identity\mcp_integration_lib\mcp_dispatch.lsp`

## One bounded manual prerequisite when live is deliberately scheduled

Use a fresh AutoCAD Mechanical 2027 session and a disposable candidate only;
never use `BVTL.dwg`, a source drawing, or an accepted drawing as the repair
target. In that fresh session, the one bounded operator load action is:

```text
NETLOAD
C:\temp\cad-agent-m2-plugin-identity\autocad_plugin\CadAgent.AutoCAD2027\bin\x64\Release\net10.0-windows\CadAgent.AutoCAD2027.dll
APPLOAD
C:\temp\cad-agent-m2-plugin-identity\mcp_integration_lib\mcp_dispatch.lsp
Load Once
```

NETLOAD/APPLOAD success is only a prerequisite. It is never a repair PASS.
The active runtime identity must be observed from the actual AutoCAD PID/HWND
and active-document full path; caller-provided labels, guessed HWND values, or
stale session IDs cannot establish identity.

## Existing transport configuration

These are the existing FileIPC/.NET IPC variables only. The HWND must be
filled from the observed fresh process by the future live driver; it must not
be guessed or copied from an earlier epoch.

```powershell
$env:CAD_AGENT_FILE_IPC = '1'
$env:CAD_AGENT_FILE_IPC_DIR = 'C:\temp'
$env:CAD_AGENT_DOTNET_IPC_DIR = 'C:\temp'
$env:CAD_AGENT_AUTOCAD_LISP_PATH = 'C:\temp\cad-agent-m2-plugin-identity\mcp_integration_lib\mcp_dispatch.lsp'
$env:CAD_AGENT_AUTOCAD_HWND = '<observed fresh AutoCAD frame HWND; never caller-invented>'
```

The future driver must allocate one unique directory below `C:\temp`, create
or stage one disposable candidate-only LINE fixture, and record the exact
source/candidate/staged-DXF/build identities. The offline seam now exists, but
it remains callback-injected and non-live; wiring real providers and entering
the exclusive AutoCAD lane are the remaining boundaries.

## Required live owner sequence

The future opt-in live test is accepted only if it composes this exact chain:

1. Observe the fresh AutoCAD runtime and disposable candidate identity.
2. Use the existing native/FileIPC render and entity owners to collect fresh
   pre-repair evidence.
3. Run the official Task6 provider through its existing worker seam and require
   a real provider-backed R5 `FAIL` for the intentional LINE defect.
4. Seal and validate R5 with `finalize_visual_verdict` and
   `validate_visual_verdict_result`.
5. Bind exactly one LINE operation and one single-use authorization to the
   current candidate, R5 failure, and operation fingerprint.
6. Execute one mutation only through `prepare_repair_plan` and
   `execute_approved_repair`; submission, timeout, `SKIP`, or ambiguous result
   is non-PASS.
7. Produce a distinct POST_REPAIR candidate/evidence identity and collect fresh
   native/provider evidence; never reuse the pre-repair R5 verdict.
8. Require a new official Task6 turn and a fresh provider-backed R5 `PASS` with
   no new applicable defects.
9. Verify source/base/accepted hashes, close the disposable document without
   save, remove only disposable artifacts, and record cleanup as observed.

Required negative evidence remains: stale candidate, wrong target, replayed
authorization, changed operation, and candidate/runtime identity drift must
fail closed before mutation. There must be exactly one repair attempt.

## Current run command and non-claims

The only current M3 command is the already-accepted contract-only check:

```powershell
& 'C:\Users\dkv\Downloads\cad-agent-merge\.venv-py311\Scripts\python.exe' -m pytest 'mcp_integration_lib\tests\test_m3_disposable_repair_acceptance.py' -q -p no:cacheprovider
```

That command must not be relabelled as live. The new seam is verified offline
through injected callbacks only; a future live command may be published only
with real provider bindings, its exact current main/head/plugin binding, and
an explicit `autocad_mechanical` opt-in gate.
Until then: `M3_CONTRACT_COMPOSITION=PASS`,
`LIVE_REPAIR_ACCEPTANCE=NOT_RUN`, and `M3_MILESTONE=NOT_CLOSED`.

## Safety invariants

- No automated NETLOAD, UI automation, AutoCAD restart/kill, COM/process
  control, source/accepted save, or overwrite of a loaded binary.
- One exclusive AutoCAD/COM/ROT/FileIPC/active-DWG lane at a time.
- Any runtime, candidate, plugin, transport, or cleanup ambiguity is
  `NOT_RUN`/non-PASS and stops the live epoch without blind retry.
