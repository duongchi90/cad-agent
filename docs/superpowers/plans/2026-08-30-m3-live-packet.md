# M3 Disposable LINE Live Packet — provider-backed follow-up

## Status and boundary

- Packet state: **PREPARED / LIVE NOT RUN**.
- Task3 successor state: PR #334 is merged at main
  `cac069c45ea44ae09bd1c2062476b0febb4a37cb`. The bounded official provider
  start adapter passed focused/offline verification plus one isolated
  low-level official-SDK START/BIND. This does not promote the packet to live
  acceptance and does not reuse the measured provider thread for a future
  epoch.
- Packet basis: GitHub `main` at
  `cac069c45ea44ae09bd1c2062476b0febb4a37cb` after PR #334 merged.
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
   The record must account for both canonical provider turns exactly:
   `task6_provider.attempts=2`, `successes=2`, `failures=0`, `retries=0`, and
   ordered `turn_ids` equal to the pre-R5 and post-R5 Task6 turn IDs.
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

## Task3 authenticated provider-home custody packet

- Current successor boundary: Issue #336, based on current `main`
  `e8386342d4a7bdab7ee12eb7b163f573e6b2df02`, branch
  `codex/task3-auth-custody-gap`, implementation head
  `f7f1038f7ad81c5ef3758dc6251df817a536cd13`.
- Official runtime identity: `C:\temp\cad-agent-m3-provider-venv-20260831\Lib\site-packages\codex_cli_bin\bin\codex.exe`,
  `codex-cli 0.144.4`, SHA-256
  `51398051c2332b6afe08dc3b9dbb4056085c197f35ca57a307ee303d450cada5`.
- The exact server-created home prepared for the current auth gate is
  `C:\temp\cad-agent-m3-auth-custody-20260831-01\codex-home`. Same-home
  `codex login status` returned exit `0` and `Logged in using ChatGPT`.
  Post-login privacy-safe inventory: `9` entries, `5` files, `4244` bytes,
  no behavior-changing ambient config/instruction/plugin/MCP/reparse state.
  No credential contents or credential-derived content hashes were read,
  copied, transmitted, or put in public evidence; private in-memory hashes are
  used only for pre-launch drift detection.
- The canonical continuation must launch with the exact same home and the
  server-owned authenticated custody attestation. It must fail closed on home,
  executable, manifest, auth-mode, or policy drift, and cleanup must purge the
  exact home after zero-survivor process cleanup. The official command runner
  is an injected boundary fact; the process owner adds no second supervisor or
  transport.
- Current live state: `LIVE_PROVIDER_BACKED=NOT_RUN`; no AutoCAD/M2/NETLOAD
  action is needed for this custody repair. After the genuine provider pre-R5
  boundary is proven, continue the existing two-turn LINE packet sequence.

## Authenticated attempt executable-role repair

- The first fresh same-home login succeeded, but canonical Task3 START stopped
  before child creation with `WORKER_AUTHORITY_MISMATCH`. Custody attested the
  official `codex.exe`; the trusted Task3 child is launched by Python. The old
  validator compared these distinct roles, so the attempt is non-evidence.
- Commit `f7f1038f7ad81c5ef3758dc6251df817a536cd13` keeps exact official
  provider path/hash revalidation and separately validates the child launcher.
  RED/GREEN focused coverage passed `177` tests; canonical verifier exit `0`.
- The authenticated root was purged and verified clean. A NEW exact home and
  one new official login are required after hosted exact-head GREEN; the prior
  home cannot be reused.

## Auth-custody continuation result

- PR #337 hosted checks are green at the previous exact head
  `4df15664cfdcbe40ab378b2ca92976e3a08fe65a`; the new repair head
  `f7f1038` requires fresh hosted checks before merge. No merge or live PASS is
  claimed.
- The latest authenticated continuation reached same-home login but stopped
  before child creation with `WORKER_AUTHORITY_MISMATCH`: the custody official
  binary and trusted Python child launcher were incorrectly compared as one
  executable role. This is non-evidence; the exact authenticated root was
  purged. A distinct provider/launcher RED test now guards the repair.
- `C:\temp\prepare_and_run_m3_auth.py` remains the one-action packet. It
  issues a NEW exact path with `cwd == disposable_root`, runs official login
  and status in that isolated environment, retains custody in-process, then
  attempts canonical Task3 START and one provider turn. The prior home cannot
  be reused. `M2_RETEST=NO` and `NETLOAD_REQUIRED=NO`.

## Safety invariants

- No automated NETLOAD, UI automation, AutoCAD restart/kill, COM/process
  control, source/accepted save, or overwrite of a loaded binary.
- One exclusive AutoCAD/COM/ROT/FileIPC/active-DWG lane at a time.
- Any runtime, candidate, plugin, transport, or cleanup ambiguity is
  `NOT_RUN`/non-PASS and stops the live epoch without blind retry.
