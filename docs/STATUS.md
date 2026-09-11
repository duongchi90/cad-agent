# CAD Agent Status
## Current plugin availability owner inventory (iteration 67)
- Fresh SOL diagnosis of iteration 66 returned
  `VERDICT=MATERIAL_FINDING`, identified the first open boundary as plugin
  availability before semantic dispatch, and authorized one non-live
  reuse-first inventory. The inventory inspected repository metadata and the
  scoped AutoCAD 2027 ApplicationPlugins/registry surfaces only; it did not
  install, register, start AutoCAD, retry NETLOAD/WM_CHAR, invoke
  `CADAGENT_DISPATCH`, touch FileIPC, mutate CAD, or change production code.
- The repository contains no CadAgent `PackageContents.xml`, bundle manifest,
  add-in, registry owner, or equivalent autoload metadata. The installed
  ApplicationPlugins locations contain an unrelated `CadMind.bundle` whose
  manifest demonstrates `LoadOnAutoCADStartup=True` for CadMind only; it is
  not a valid CadAgent owner and was not reused.
- Read-only searches under the current/user and machine Autodesk AutoCAD
  registry roots found no CadAgent demand-load/startup registration. The only
  CadAgent registry hits were NetLoad dialog filename MRU history entries.
  Therefore no existing CadAgent availability owner was found.
- Smallest reuse proposal: keep the existing CadAgent project and semantic
  .NET/FileIPC owner, and use the already demonstrated Autodesk
  `ApplicationPlugins/PackageContents.xml` `LoadOnAutoCADStartup` mechanism
  only after an independently authorized CadAgent bundle/configuration exists.
  This inventory does not introduce that configuration.
- Exact next oracle, once that owner exists: one fresh disposable `/b` session
  with read-only owned-PID module inspection asserting the approved
  `CadAgent.AutoCAD2027.dll` path and SHA-256 before any
  `CADAGENT_DISPATCH`/WM_CHAR/FileIPC action, then exact-PID cleanup. Iteration
  66 remains the negative control: pre-QNEW `NETLOAD` reached document-ready
  with zero matching CadAgent modules.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-plugin-availability-owner-inventory-iteration67.md`.
  Fresh SOL diagnosis is required before any installation/configuration or
  live causal oracle.

## Current pre-plugin NETLOAD module oracle (iteration 66)
- Fresh SOL diagnosis of iteration 65 returned
  `VERDICT=MATERIAL_FINDING`, `HUMAN_GATE=NO`, and authorized exactly one
  disposable pre-plugin bootstrap causal oracle using the existing `/b`
  startup-script owner. The temporary script order was
  `_.NETLOAD -> approved Release CadAgent DLL -> _.QNEW`; after same-HWND
  document-ready, only read-only owned-PID module inspection ran. No
  `CADAGENT_DISPATCH`, raw-LISP/WM_CHAR trigger, FileIPC, Task-6, source,
  candidate, DXF, save, or production change was allowed.
- The fresh owned AutoCAD session reached document-ready with HWND `3215182`
  and PID `32568`. The inspected module list had zero exact matches for the
  approved Release DLL
  `autocad_plugin/CadAgent.AutoCAD2027/bin/x64/Release/net10.0-windows/CadAgent.AutoCAD2027.dll`
  (SHA-256 `BBBD43CC8AFC6558454A003145811F775E4BAC557BF4AFA4153A188D26828A97`)
  and zero CadAgent-named modules. Therefore plugin availability after the
  pre-QNEW NETLOAD script is not proven; no cause is inferred beyond this
  boundary.
- The initial close call reported
  `MCPTimeoutError: START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED`; bounded fallback
  closed the exact disposable PID `32568` without saving and confirmed it
  absent. The proof root
  `C:/temp/cad-agent-task6-live-20260911/pre-plugin-netload-proof-iteration66`
  is empty. No source, candidate, accepted drawing, DXF, FileIPC request, or
  production CAD state changed.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-pre-plugin-netload-module-oracle-iteration66.md`.
  Fresh SOL diagnosis is required before any implementation, dispatcher call,
  or retry.

## Current command-delivery owner inventory (iteration 65)
- Fresh SOL diagnosis of iteration 64 returned
  `VERDICT=MATERIAL_FINDING`, `HUMAN_GATE=NO`, and authorized one non-live
  reuse-first inventory. The inventory inspected the existing Python/.NET/
  AutoCAD integration surfaces and ran only focused offline trigger-contract
  tests; it did not modify production code or perform another live retry.
- The existing semantic owner is already present: Python
  `mcp_integration_lib/dotnet_ipc.py` writes one request, invokes the existing
  `CADAGENT_DISPATCH` command trigger, and polls the exact result file; the
  AutoCAD plugin's `[CommandMethod("CADAGENT_DISPATCH")]` reads that request,
  calls `OperationDispatcher.Dispatch`, and persists a validated `IpcResult`
  through `JsonFileStore.WriteResult` before any disposable close scheduling.
  The result's matching `request_id`, schema, `success`, and error/payload
  fields are the semantic acknowledgement owner. No second transport is
  justified by this inventory.
- Smallest reuse proposal for a future bounded implementation is therefore to
  keep the existing .NET File IPC owner and `DotNetIPCClient` contract, and
  bind the relevant bootstrap/dispatch boundary to its matching result-file
  acknowledgement. This proposal does not claim that the plugin is available
  before NETLOAD or that it solves the pre-plugin bootstrap boundary; that
  prerequisite remains separately unproven. No production write is authorized
  by this inventory.
- The causal RED oracle is the existing marked test
  `test_enqueue_true_without_receiver_consumption_is_causal_red`: with every
  `PostMessageW` call returning true but receiver consumption false, the
  current trigger returns without a handler acknowledgement. It ran as the
  expected RED (`1 failed, 1 passed, 18 deselected`), while the focused
  `DotNetIPCClient` enqueue/result tests ran `3 passed` with no cache writes.
- Exact inventory, proposal, search boundary, and oracle evidence are recorded
  in `docs/superpowers/implementation-records/2026-09-11-command-delivery-owner-inventory-iteration65.md`.
  Fresh SOL diagnosis is required before any implementation or live retry.

## Current focused-receiver causal diagnostic (iteration 64)
- Fresh SOL diagnosis of iteration 63 returned
  `VERDICT=MATERIAL_FINDING`, `HUMAN_GATE=NO`, and authorized exactly one
  disposable focused-receiver causal diagnostic on unchanged reviewed code
  `65fc23ba610091e236f19ee93f8cee69f96d4ce9`. The diagnostic reached QNEW and
  same-HWND document-ready, captured the current owned GUI-thread focus, sent
  only the existing `post_qnew_entry` marker expression with the same UTF-16
  `WM_CHAR` framing directly to that exact focus HWND, waited for the marker,
  then closed and cleaned up.
- Owned session: main HWND/PID `5181128/29312`, GUI thread `19756`. Focus before
  send was owned visible HWND `13044028`, class
  `Afx:00007FF77AB10000:28:0000000000000000:0000000000000002:00000000329103CD`.
  All 299 code units returned success from `PostMessageW` when sent directly to
  that focus HWND, but the exact `CAD_AGENT_START_TAB_POST_QNEW_ENTRY` marker
  was absent. This rules out a simple MDIClient-versus-focus-child target swap
  as a sufficient repair; semantic command consumption is still unproven.
- The initial close call reported
  `MCPTimeoutError: START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED`; bounded fallback
  cleanup closed the exact disposable PID `29312` without saving and a follow-up
  process check confirmed it absent. The proof root
  `C:/temp/cad-agent-task6-live-20260911/focused-receiver-proof-iteration64`
  is empty. No focus workaround, retry, NETLOAD, dispatcher, FileIPC, Task-6,
  source, candidate, DXF, or production mutation occurred.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-focused-receiver-causal-diagnostic-iteration64.md`.
  Fresh SOL diagnosis is required before any further trigger or implementation
  change.

## Current receiver-identity diagnostic (iteration 63)
- Fresh SOL diagnosis of iteration 62 returned
  `VERDICT=MATERIAL_FINDING`, `HUMAN_GATE=NO`, and authorized exactly one
  observation-only receiver-identity diagnostic on unchanged reviewed code
  `65fc23ba610091e236f19ee93f8cee69f96d4ce9`. The diagnostic used one fresh
  disposable QNEW session, waited for same-HWND document-ready, enumerated the
  owned child-window hierarchy, captured the owner GUI thread's active/focus/
  capture identities, compared the result with the existing trigger's
  `MDIClient` selection, then closed and cleaned up.
- The owned AutoCAD main window was HWND `7406996`, PID `29440`, class
  `AfxMDIFrame140u`. The hierarchy contained two owned `MDIClient` windows:
  visible HWND `8521664` and hidden HWND `5244534`. The existing trigger would
  select the unique visible owned `MDIClient` `8521664`; receiver selection is
  not ambiguous in this epoch.
- GUI thread `23156` reported active HWND `7406996` (the main frame), focus HWND
  `5180418` (an owned visible Afx child), and capture HWND `0` (none). Thus the
  trigger's selected receiver is not the actual focused child. This observation
  narrows the delivery boundary but does not by itself prove that the receiver
  mismatch caused the absent marker.
- The initial close call reported
  `MCPTimeoutError: START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED`; the exact owned
  disposable process was cleaned up with the bounded fallback and was confirmed
  absent afterward. The proof root
  `C:/temp/cad-agent-task6-live-20260911/receiver-identity-proof-iteration63`
  is empty. No WM_CHAR/raw-LISP/command, focus workaround, NETLOAD, dispatcher,
  FileIPC, Task-6, source, candidate, DXF, or production mutation occurred.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-receiver-identity-diagnostic-iteration63.md`.
  Fresh SOL diagnosis is required before any trigger retry or implementation
  change.

## Current trigger-time foreground trace (iteration 62)
- Fresh SOL diagnosis of iteration 61 returned
  `VERDICT=MATERIAL_FINDING`, `HUMAN_GATE=NO`, and authorized exactly one
  trigger-time foreground-trace diagnostic on unchanged reviewed code
  `65fc23ba610091e236f19ee93f8cee69f96d4ce9`. The diagnostic used one fresh
  disposable QNEW session, waited for same-HWND document-ready, started
  read-only high-frequency foreground sampling, invoked only the existing
  `post_qnew_entry` raw-LISP marker once, then stopped sampling and closed the
  disposable process.
- The existing trigger returned without an exception, but the exact
  `CAD_AGENT_START_TAB_POST_QNEW_ENTRY` marker was absent. Sampling recorded
  one stable foreground identity transition over 9 samples: HWND `5705374`,
  PID `9184`, process `acad.exe`, title `Autodesk AutoCAD 2027`. No transient
  foreground identity change was observed in the sampled sequence, but the
  absent marker means process-bound command delivery is still not proven.
- The initial bounded close call timed out; the exact owned disposable PID was
  then verified as `acad` with title `Autodesk AutoCAD 2027 - [Drawing1.dwg]`
  and closed without saving. The proof root
  `C:/temp/cad-agent-task6-live-20260911/foreground-trace-proof-iteration62`
  is empty. No NETLOAD, dispatcher, FileIPC, Task-6, source, candidate, DXF,
  or production-CAD state was touched, and no production code changed.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-trigger-time-foreground-trace-iteration62.md`.
  Fresh SOL diagnosis is required before any retry or implementation change.

## Current foreground-identity diagnostic (iteration 61)
- Fresh SOL diagnosis of iteration 60 returned `VERDICT=MATERIAL_FINDING`,
  `HUMAN_GATE=NO`, and authorized one read-only foreground-identity
  diagnostic on unchanged code. The diagnostic launched one disposable QNEW
  session, waited for same-HWND document-ready, recorded owned and actual
  foreground identity, then closed and cleaned up. It did not call the raw
  trigger, use a SetForegroundWindow workaround, load NETLOAD/dispatcher,
  issue FileIPC/Task-6, or access source/candidate/DXF.
- Observation after document-ready: owned HWND/PID were `7867904/10328` and
  foreground HWND/PID were also `7867904/10328`; foreground process was
  `acad.exe` at the approved AutoCAD 2027 path with title `Autodesk AutoCAD
  2027`. The diagnostic therefore captured a matching foreground identity at
  its observation point, without inferring that the earlier trigger failure is
  resolved.
- Cleanup succeeded and the owned proof root was empty. No source, candidate,
  DXF, FileIPC, or production CAD state changed. Fresh SOL diagnosis is
  required before any trigger retry or production-code change.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-foreground-identity-diagnostic-iteration61.md`.

## Current first-boundary post-QNEW diagnostic (iteration 60)
- Fresh SOL diagnosis of iteration 59 returned `VERDICT=MATERIAL_FINDING`,
  `HUMAN_GATE=NO`, and localized the first causal boundary to
  `POST_QNEW_PROCESS_BOUND_COMMAND_EXECUTION_NOT_PROVEN`. SOL authorized one
  narrower disposable diagnostic on unchanged code: QNEW, same-HWND
  document-ready, one existing `post_qnew_entry` raw-LISP marker, exact-marker
  wait, then close/cleanup. NETLOAD, dispatcher load, FileIPC, Task-6, source,
  candidate, DXF, and retry were explicitly excluded.
- The diagnostic reached QNEW and same-HWND document-ready. The first
  process-bound marker trigger was rejected immediately with
  `MCPToolError: WINDOW_FOREGROUND_INVALID`; no marker was observed and no
  downstream bootstrap action was attempted.
- Cleanup completed for the owned disposable process and root. The root had no
  remaining entries and no source/candidate/DXF/FileIPC mutation occurred.
  This is a first-boundary live diagnostic result, not a Task-6 acceptance
  result. Fresh SOL diagnosis is required before any retry or implementation
  change.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-post-qnew-marker-diagnostic-iteration60.md`.

## Current bootstrap-only live proof (iteration 59)
- Fresh SOL review of pushed code `65fc23ba610091e236f19ee93f8cee69f96d4ce9`
  returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, and `HUMAN_GATE=NO`,
  authorizing exactly one bootstrap-only live proof. The proof was bounded to
  one owned disposable AutoCAD Mechanical 2027 session and the sequence
  `QNEW -> same-HWND document-ready -> NETLOAD -> dispatcher LISP load ->
  exact completion acknowledgement -> close/cleanup`; it did not open or
  mutate BVTL.dwg, any source drawing, candidate, DXF, or accepted artifact.
- The proof failed closed with
  `MCPTimeoutError: START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED`. Timing was
  `process_launch -> start_window_observed -> document_ready_transition ->
  completion_wait_start -> completion_timeout`; none of the four opt-in stage
  markers or the exact completion marker was observed.
- Cleanup completed for the owned disposable process and root. The root had no
  remaining entries, the pre-existing AutoCAD process remained running, and no
  source/candidate/DXF/FileIPC mutation was performed. This is a bootstrap
  owner finding, not a live Task-6 acceptance result; do not retry bootstrap or
  Task-6 until fresh SOL diagnosis.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-bootstrap-only-live-proof-iteration59.md`.

## Current two-phase Start-tab bootstrap remediation (iteration 57)
- Fresh SOL diagnosis of iteration 56 returned `VERDICT=MATERIAL_FINDING`,
  `HUMAN_GATE=NO`, and authorized exactly one non-live two-phase bootstrap-owner
  remediation. The defect was that the owned `/b` startup script did not
  reliably continue after `_.QNEW`, so the post-QNEW plugin, dispatcher, and
  completion stages were never reached even after same-HWND document readiness.
- Code/test checkpoint `4bdf197f828737510c1defc39956cf922a3ea28c` is pushed on
  `codex/audit-text-style-compat-20260910`. The owned startup script now emits
  only `_.QNEW\r\n`. After positive same-HWND document-ready confirmation, the
  existing process-bound trigger path runs the opt-in stage marker, NETLOAD,
  dispatcher LISP load, exact completion-marker writer, and completion wait in
  order. Claim-bound dispatch is still unavailable until the exact marker is
  confirmed; failures still close the owned session and remove markers/scripts.
- Stage timing remains diagnostic opt-in only (`False` by default), source-path
  prohibition and timeout values remain unchanged, and no source drawing,
  candidate, accepted drawing, FileIPC request, or live CAD state was touched.
- TDD RED/GREEN: the new phase-order test first reproduced the pre-fix
  completion timeout, then the focused owner suite passed `40` tests with `6`
  subtests. Ruff and `git diff --check` pass.
- Authoritative `scripts/verify.ps1` completed with exit `0` on clean code head:
  .NET `238` passed; offline Python JUnit `3388` with zero failures/errors/
  skips (`3308` passed, `21` deselected, `80` subtests); offline IPC JUnit
  `134` clean; causal-RED expected one negative failure handled; real-data `2`
  unavailable skips; AutoCAD Mechanical `17` unavailable skips; AutoCAD live
  and M2 remain `NOT RUN`.
- No live retry is authorized or implied. Fresh SOL review of this pushed code
  is required before any bootstrap-only live proof or Task-6 operation.
  Repository-readable record:
  `docs/superpowers/implementation-records/2026-09-11-two-phase-start-tab-bootstrap-remediation-iteration57.md`.

## Current bootstrap-only stage-timing proof (iteration 56)
- SOL's iteration-55 review returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`,
  and authorized exactly one fresh bootstrap-only live proof on code
  `b4c8776191b353921944fc4feba3a264bcf39d3e` with
  `stage_timing_enabled=True` and the unchanged `timeout_s=30.0`. The proof
  did not open BVTL.dwg or run Task-6 extraction/query/candidate operations.
- The proof failed closed with
  `START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED`. Timing was
  `process_launch -> start_window_observed -> completion_wait_start`, then
  `document_ready_transition` about `2.640s` after the wait began, followed by
  `completion_timeout` at `30.000s`. None of the four stage events
  (`post_qnew_entry`, `netload_return`, `dispatcher_load_return`,
  `completion_marker_writer_return`) was observed, the exact completion marker
  was absent, and the claim-bound FileIPC ping was not attempted (`0`).
- Evidence is recorded at
  `C:/temp/cad-agent-task6-live-20260911/task6-bootstrap-only-live-proof-iteration56-evidence.txt`.
  The owned proof root was empty and removed; the pre-existing user AutoCAD
  process was preserved. No source, candidate, accepted drawing, or
  production CAD state was mutated.
- Fresh SOL diagnosis is required before another bootstrap or live Task-6
  attempt. Repository-readable record:
  `docs/superpowers/implementation-records/2026-09-11-bootstrap-only-stage-timing-proof-iteration56.md`.

## Current bootstrap stage-localization opt-in correction (iteration 55)
- SOL's iteration-54 review found that the stage writers were enabled for
  every bootstrap session with an IPC root, which violated the authorized
  opt-in boundary. The correction is pushed at code head
  `b4c8776191b353921944fc4feba3a264bcf39d3e`.
- `WindowsAutoCADStartTabSession` and its factory now default
  `stage_timing_enabled=False`. Only the bounded standalone Task-6 diagnostic
  harness that emits `BOOTSTRAP_TIMING_EVENTS` passes `True`; normal bootstrap
  sessions generate no stage paths, stage script expressions, or extra file
  writes. Opt-in mode retains the four fixed-token same-root stage markers,
  monotonic observation, cleanup, and fail-closed semantics.
- TDD RED/GREEN: the default-script regression first failed because stage
  expressions were unconditional and the opt-in parameter was absent; the
  focused owner suite passed `39` tests. Ruff and `git diff --check` pass.
- Authoritative `scripts/verify.ps1` completed on clean code head: .NET `238`
  passed; offline Python JUnit `3387` with zero failures/errors/skips (`3307`
  passed, `21` deselected, `80` subtests); offline IPC JUnit `134` clean;
  causal-RED expected one negative failure handled; real-data `2` unavailable
  skips; AutoCAD Mechanical `17` unavailable skips; AutoCAD live and M2 remain
  `NOT RUN`.
- No live retry, source open, extraction, query, candidate operation, FileIPC
  request, or CAD mutation was performed. Fresh SOL review is required before
  any live proof. Repository-readable record:
  `docs/superpowers/implementation-records/2026-09-11-bootstrap-stage-localization-opt-in-correction-iteration55.md`.

## Current bootstrap stage-localization remediation (iteration 54)
- SOL's iteration-53 review localized the remaining marker-timeout boundary to
  the post-document-ready startup-script path. The exact marker was still
  absent about `28.610s` after `document_ready_transition`, while retained
  stage evidence had previously shown the QNEW-to-ACK sequence completing in
  `0.7392299s`. SOL authorized exactly one non-live observability-only
  remediation; no live retry was allowed.
- Code/test checkpoint `486e2dd72911c5b67b59216a2877b338e03eddc4` adds four
  fixed-token, privacy-safe stage markers and monotonic timing observations:
  `post_qnew_entry`, `netload_return`, `dispatcher_load_return`, and
  `completion_marker_writer_return`. Each path is unique to the owned script,
  stays inside the exact disposable IPC root, is best-effort observed without
  changing the 30-second deadline or success semantics, and is removed during
  cleanup. The existing bootstrap commands, completion marker contract,
  readiness/FileIPC semantics, and fail-closed behavior remain unchanged.
- TDD RED/GREEN: focused stage-script/order/partial-failure cleanup assertions
  first failed because the stage markers were absent; the focused owner suite
  passed `38` tests. Ruff and `git diff --check` pass.
- Authoritative `scripts/verify.ps1` completed on the clean code commit:
  .NET `238` passed; offline Python JUnit `3386` with zero
  failures/errors/skips (`3306` passed, `21` deselected, `80` subtests);
  offline IPC JUnit `134` clean; causal-RED expected one negative failure
  handled; real-data `2` unavailable skips; AutoCAD Mechanical `17`
  unavailable skips; AutoCAD live and M2 remain `NOT RUN`.
- No live retry, source open, extraction, query, candidate operation, FileIPC
  request, or CAD mutation was performed. Fresh SOL review is required before
  any live proof. Repository-readable record:
  `docs/superpowers/implementation-records/2026-09-11-bootstrap-stage-localization-remediation-iteration54.md`.

## Current bootstrap-only live proof (iteration 53)
- SOL's iteration-52 review returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`,
  and authorized exactly one fresh bootstrap-only live proof on code head
  `871db5fb29e944d894ff83d12a6fb4a4695f82bc`. The proof kept
  `timeout_s=30.0`, used the shared timing recorder, required the exact
  completion marker, and allowed exactly one claim-bound FileIPC readiness
  ping only after marker confirmation. No source drawing, Task-6 extraction,
  query, candidate, save, or accepted-drawing operation was in scope.
- The proof failed closed at the first boundary with
  `START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED`. The timing sequence shows
  `start_window_observed` and `completion_wait_start` at the same recorded
  instant, `document_ready_transition` about `1.406s` later, and
  `completion_timeout` about `30.016s` after the completion wait began. The
  completion marker was not observed, so the claim-bound FileIPC ping was not
  attempted (`ping_attempts=0`).
- Cleanup evidence is recorded at
  `C:/temp/cad-agent-task6-live-20260911/task6-bootstrap-only-live-proof-iteration53-evidence.txt`.
  The owned proof root was empty and removed after cleanup. The pre-existing
  user AutoCAD process was preserved; no source, candidate, accepted drawing,
  or production CAD state was mutated.
- Fresh SOL diagnosis is required before another bootstrap or live Task-6
  attempt. Repository-readable record:
  `docs/superpowers/implementation-records/2026-09-11-bootstrap-only-live-proof-iteration53.md`.

## Current bootstrap timing anchor correction (iteration 52)
- SOL's iteration-51 review found that `document_ready_transition` was
  unreachable on the marker-timeout path: `launch_blank_document()` waited for
  marker acknowledgement before the client ran its normal document-ready
  check. The bounded correction is pushed at
  `871db5fb29e944d894ff83d12a6fb4a4695f82bc`.
- While the owned session waits for marker acknowledgement, it now best-effort
  polls the existing same-HWND document-ready probe and records the first
  positive `document_ready_transition` on the shared timing recorder. The
  observation does not gate success, alter any timeout/deadline, or change
  bootstrap commands, readiness/FileIPC semantics, or CAD operations. The
  later normal client check deduplicates the shared transition.
- TDD RED/GREEN: the new deduplication/timeout assertions first failed because
  `record_once` and the in-wait probe path were absent; the focused owner suite
  passed `39` tests with `6` subtests. Ruff and `git diff --check` pass.
- Authoritative `scripts/verify.ps1` exits `0` on the clean implementation
  commit: C# `238` passed; offline Python JUnit `3386` with zero
  failures/errors/skips (`3306` passed, `21` deselected, `80` subtests);
  offline IPC JUnit `134` clean; causal-RED expected one negative failure
  handled; real-data `2` skipped; AutoCAD Mechanical `17` skipped; AutoCAD
  live and M2 remain `NOT RUN`.
- No live retry, source open, candidate operation, FileIPC request, or CAD
  mutation was performed. Fresh SOL review is required before any live run.
- Repository-readable record:
  `docs/superpowers/implementation-records/2026-09-11-bootstrap-timing-anchor-correction-iteration52.md`.

## Current bootstrap observability remediation (iteration 51)
- SOL returned `VERDICT=BLOCKED`, `HUMAN_GATE=NO`, and authorized exactly one
  non-live observability-only remediation after the timing classification
  remained inconclusive. The remediation does not change the 30-second
  timeout, bootstrap commands, readiness semantics, FileIPC behavior, or CAD
  operations.
- Code/test checkpoint is pushed at
  `4a0d33c02db56a71d99ffe207bc031c5bdfb80c5`. A shared privacy-safe
  `BootstrapTimingRecorder` records monotonic events for `process_launch`,
  `start_window_observed`, `completion_wait_start`,
  `document_ready_transition`, `completion_marker_observed`,
  `completion_timeout`, and `cleanup_start`/`cleanup_end`. Recorder failures
  are swallowed so observability cannot alter fail-closed bootstrap behavior.
  The opt-in live harness passes one recorder through the session/client and
  emits `BOOTSTRAP_TIMING_EVENTS` for future evidence; no live run was made.
- TDD RED/GREEN: the new timing tests first failed because the recorder API
  was absent, then the focused owner suite passed `38` tests with `6`
  subtests; the unavailable standalone live gate reported `SKIP` because its
  AutoCAD/FileIPC prerequisites were absent. Ruff and `git diff --check` pass.
- Authoritative `scripts/verify.ps1` exits `0` on this clean commit: C# `238`
  passed; offline Python JUnit `3385` with zero failures/errors/skips
  (`3305` passed, `21` deselected, `80` subtests); offline IPC JUnit `134`
  clean; causal-RED expected one negative failure handled; real-data `2`
  skipped; AutoCAD Mechanical `17` skipped; AutoCAD live and M2 remain
  `NOT RUN`.
- No AutoCAD/FileIPC live retry, source drawing open, candidate operation,
  production CAD mutation, or reviewed-state mutation was performed. Fresh
  SOL review is required before any live run.
- Repository-readable implementation record:
  `docs/superpowers/implementation-records/2026-09-11-bootstrap-observability-remediation-iteration51.md`.

## Current bootstrap timing reconstruction (iteration 50)
- SOL's single bounded action was a non-live reconstruction from retained
  iteration-43/45/47/49 evidence only. No code, AutoCAD, FileIPC, source,
  candidate, or reviewed-HEAD mutation was performed.
- The retained iteration-43 stage markers show exact deltas of
  `QNEW_COMPLETE -> ACK_WRITE_RETURN = 0.7392299s` and
  `DISPATCHER_LOAD_RETURN -> ACK_WRITE_RETURN = 0.0009978s`.
- The current owner/test semantics use a fresh `timeout_s=30.0` completion
  wait after the `[Start]` window/start probe is observed. None of the
  retained iterations 43/45/47/49 records the process-launch time,
  `[Start]` observation, Drawing1 transition, or production timeout instant.
  The proof-root creation timestamps are setup metadata and cannot substitute
  for those missing anchors.
- Therefore `BUDGET_CLASSIFICATION=INCONCLUSIVE_FOR_30S_COMPLETION_DEADLINE`.
  The evidence does not prove a late marker and does not prove a broken marker
  writer. No syntax change or live retry is justified by this reconstruction.
- Private evidence and recoverable state:
  `C:/temp/cad-agent-task6-live-20260911/task6-bootstrap-timing-reconstruction-iteration50-evidence.txt` and
  `C:/temp/cad-agent-task6-live-20260911/wait-safe-resume-state-iteration50.txt`.
  Fresh SOL review is pending; remain in WAIT_SAFE.

## Current live proof boundary (iteration 49)
- SOL returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, and `HUMAN_GATE=NO` for iteration 48 and authorized exactly one fresh bootstrap-only live proof on code `a9c8fa9f7f67d8562e17d55cce383bf975eb3761`: exact unique `.marker` observation/validation, then exactly one claim-bound FileIPC readiness ping; no BVTL.dwg open or Task-6 extraction/query/candidate operation.
- The proof failed closed at the first boundary with `START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED` after 57.547 seconds for the bounded process including cleanup. The production unique same-root `.marker` was not observed; claim-bound ping attempts were 0 and the ping boundary was not reached.
- Cleanup is verified: the owned blank session was closed without save, the dedicated proof root is empty, and no acad.exe process remains. No source path was passed; no source, accepted drawing, candidate, production CAD, or Task-6 state was mutated. Live Task-6 acceptance remains NOT RUN, not PASS.
- Evidence and resume state: `C:/temp/cad-agent-task6-live-20260911/task6-bootstrap-only-live-proof-iteration49-evidence.txt` and `C:/temp/cad-agent-task6-live-20260911/wait-safe-resume-state-iteration49.txt`. Fresh SOL diagnosis is required; do not retry bootstrap or live Task 6 before a new bounded verdict.

## Current code checkpoint (iteration 48)
- SOL's iteration-47 finding isolated a remaining execution-framing difference: the production startup script still evaluated dispatcher-root assignment, `(load mcp_dispatch.lsp)`, and the marker writer inside one enclosing AutoLISP `progn`, while iteration 43 only live-proved a marker write after dispatcher-load return.
- The bounded non-live remediation is pushed at code HEAD `a9c8fa9f7f67d8562e17d55cce383bf975eb3761`. Production now emits the dispatcher-root assignment/load as one completed top-level expression and the canonical completion-marker writer as a separate following top-level expression; marker path/token validation and stale/wrong-token cleanup are unchanged.
- TDD RED/GREEN: the byte-for-byte full-script framing assertion failed before the change and focused owner checks passed afterward: 33 passed and 6 subtests. Ruff and `git diff --check` passed.
- Authoritative `scripts/verify.ps1` exits 0 on code `a9c8fa9`: C# 238 passed; offline Python JUnit 3381 with zero failures/errors/skips (3301 passed, 21 deselected, 80 subtests); offline IPC JUnit 134 clean; causal-red expected one negative failure handled; real-data 2 skipped; AutoCAD Mechanical 17 skipped. Live AutoCAD and M2 remain NOT RUN.
- No bootstrap or Task-6 live retry was made after this remediation. No source, accepted drawing, candidate, or production CAD state was mutated. Fresh SOL review is required before any live retry.
- Evidence and resume state: `C:/temp/cad-agent-task6-live-20260911/task6-bootstrap-framing-remediation-iteration48-evidence.txt` and `C:/temp/cad-agent-task6-live-20260911/wait-safe-resume-state-iteration48.txt`.

## Current live proof boundary (iteration 47)
- SOL returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, and `HUMAN_GATE=NO` for the canonical completion-marker remediation, authorizing exactly one fresh bootstrap-only live proof on code `636a81e186133a24c36d3e0c6b0b67a918fceb3e`: observe/consume the unique marker, then send exactly one claim-bound FileIPC readiness ping; no BVTL.dwg open or Task-6 extraction/query.
- The proof failed closed at the first boundary with `START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED`. The production unique same-root `.marker` was not observed; claim-bound ping attempts were 0 and the ping boundary was not reached.
- Cleanup is verified: the owned blank session was closed without save, the dedicated proof root is empty, and no acad.exe process remains. No source path was passed; no source, accepted drawing, candidate, production CAD, or Task-6 state was mutated. Live Task-6 acceptance remains NOT RUN, not PASS.
- Evidence and resume state: `C:/temp/cad-agent-task6-live-20260911/task6-bootstrap-only-live-proof-iteration47-evidence.txt` and `C:/temp/cad-agent-task6-live-20260911/wait-safe-resume-state-iteration47.txt`. Fresh SOL diagnosis is required; do not retry bootstrap or live Task 6 before a new bounded verdict.

## Current code checkpoint (iteration 46)
- SOL's iteration-45 material finding required exactly one non-live differential between the production startup script and the iteration-43 live-proven staged marker writer. The pre-fix capture showed the same resolved per-session marker path and exact completion token, but the production expression lacked the canonical nested `progn` form used by the staged diagnostic (`PRODUCTION_CONTAINS_DIAGNOSTIC_EXPRESSION=False`).
- The bounded remediation is pushed at code HEAD `636a81e186133a24c36d3e0c6b0b67a918fceb3e`. Production now builds the marker path and exact AutoLISP writer through shared helpers, using the same-root unique `.marker`, `open`/`write-line`/`close` primitive, exact `CAD_AGENT_START_TAB_BOOTSTRAP_COMPLETE` token, and existing stale/wrong-token cleanup and validation.
- TDD RED/GREEN: the exact canonical writer golden assertion failed before the change and focused owner checks passed afterward: 33 passed and 6 subtests. Ruff and `git diff --check` passed.
- Authoritative `scripts/verify.ps1` exits 0 on code `636a81e`: C# 238 passed; offline Python JUnit 3381 with zero failures/errors/skips (3301 passed, 21 deselected, 80 subtests); offline IPC JUnit 134 clean; causal-red expected one negative failure handled; real-data 2 skipped; AutoCAD Mechanical 17 skipped. Live AutoCAD and M2 remain NOT RUN.
- No bootstrap or Task-6 live retry was made. The approved `BVTL.dwg` SHA-256 remains `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`; no source, accepted drawing, candidate, or production CAD state was mutated. Fresh SOL review is pending.
- Evidence and resume state: `C:/temp/cad-agent-task6-live-20260911/task6-completion-marker-differential-remediation-iteration46-evidence.txt` and `C:/temp/cad-agent-task6-live-20260911/wait-safe-resume-state-iteration46.txt`.

## Current live proof boundary (iteration 45)
- SOL returned PASS for iteration 44 and authorized exactly one fresh bootstrap-only live proof on the marker remediation: one owned AutoCAD Mechanical 2027 blank session, positive per-session `.marker` observation/consumption, then exactly one claim-bound FileIPC readiness ping; no BVTL.dwg open or Task-6 extraction/query.
- The proof failed closed at the first boundary: `WindowsAutoCADStartTabSession` did not observe `START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED` marker completion after 68.11 seconds. The claim-bound ping was not reached. The repository HEAD was docs `d75aa27`; the production code/test files were byte-identical to code commit `4d05c46`.
- Cleanup is verified: no acad.exe process remains, the proof root is empty, and BVTL.dwg SHA-256 remains `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`. No source, accepted drawing, candidate, or production CAD state was mutated. Live Task-6 acceptance remains NOT RUN, not PASS.
- Proof root: `C:/temp/cad-agent-task6-live-20260911/bootstrap-proof-iteration45`. Fresh SOL diagnosis is pending; do not run another bootstrap/live proof before a new bounded verdict.

## Current code checkpoint (iteration 44)
- SOL's iteration-43 finding isolated the failure to the `.ready` completion primitive: the owned script reached QNEW, NETLOAD, dispatcher load, and the final conditional, but the `.ready` file was not observed. The bounded remediation is pushed at code HEAD `4d05c46e3710bc7f5e23e0cd3f84438f19c74a09`.
- The owned startup session now uses the same live-proven same-root marker-writing primitive from iteration 43, with one unique per-session `.marker` path under the exact IPC root and the exact `CAD_AGENT_START_TAB_BOOTSTRAP_COMPLETE` token. It validates exact marker content and removes the marker during cleanup; bootstrap confirmation and dispatcher-preloaded state remain false until the marker is observed.
- RED/GREEN coverage includes exact marker path/token, wrong-token rejection, cleanup, and the existing no-ping/source-open-before-confirmation guards. Focused owner/integration checks: 53 passed, 1 skipped, 1 deselected, 9 subtests; Ruff and git diff --check PASS.
- Authoritative `scripts/verify.ps1` exits 0 on code `4d05c46`: C# 238 passed; offline Python JUnit 3381 with zero failures/errors/skips (3301 passed, 21 deselected, 80 subtests); offline IPC JUnit 134 clean; causal-red expected 1 negative failure handled; real-data 2 skipped; AutoCAD Mechanical 17 skipped. AutoCAD live and M2 remain NOT RUN.
- No live bootstrap or Task-6 retry was made after this remediation. `BVTL.dwg` SHA-256 remains `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`; no source, accepted drawing, candidate, or production CAD state was mutated. Fresh SOL review is required before another live run.

## Current bootstrap diagnostic boundary (iteration 43)
- SOL authorized exactly one bootstrap-only staged completion diagnostic after the iteration-42 completion-ack timeout. It used a fresh owned AutoCAD Mechanical 2027 session, the approved release plugin, and the repository dispatcher, with no BVTL.dwg/source-open call and no Task-6 retry.
- The diagnostic positively observed all four staged marker files in the same disposable root: `QNEW_COMPLETE`, `NETLOAD_RETURN`, `DISPATCHER_LOAD_RETURN`, and `ACK_WRITE_RETURN`. The final marker was emitted after the acknowledgement conditional, so it proves the script reached that final expression but does not by itself prove that the `.ready` file was successfully opened/written.
- `WindowsAutoCADStartTabSession` still failed closed with `START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED` after 94.39 seconds. The claim-bound FileIPC ping, BVTL.dwg source open, health, setup audit, inspection, extraction, candidate creation/query, and source reopen were not reached. Live Task-6 acceptance remains NOT RUN, not PASS.
- Cleanup is verified: no acad.exe process remains, the diagnostic root has only the four stage markers and no `.ready` file, the disposable candidate root is empty, and BVTL.dwg SHA-256 remains `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`. No source, accepted drawing, candidate, or production CAD state was mutated.
- Diagnostic root: `C:/temp/cad-agent-task6-live-20260911/bootstrap-stage-iteration43`. The checkpoint is pushed in this documentation commit. Fresh SOL diagnosis is pending; do not retry the bootstrap or live Task 6 before a new verdict.

## Current live boundary (iteration 42)
- SOL authorized one fresh live Task-6 gate on code c415b90139f58d3f76de7e3f15f5dc4c3e68e40a. The owned startup session did not observe its exact completion acknowledgement within the bounded timeout and failed closed with START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED after 53.89s.
- The gate stopped before the claim-bound FileIPC ping, BVTL.dwg source open, health, setup audit, standalone inspection, extraction, candidate creation, query, or source reopen. Live acceptance remains NOT RUN, not PASS.
- Cleanup is verified: no acad.exe process remains, the disposable candidate directory and completion acknowledgement are empty, and BVTL.dwg SHA-256 remains 78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8. No source, accepted drawing, candidate, or production CAD state was mutated.
- Evidence and resume state: C:/temp/cad-agent-task6-live-20260911/task6-live-gate-iteration42-evidence.txt and C:/temp/cad-agent-task6-live-20260911/wait-safe-resume-state-iteration42.txt. Fresh SOL diagnosis is pending; do not retry live Task 6 before verdict.
## Current iteration 41 checkpoint
- SOL's iteration-40 diagnosis identified an ordering gap: document-ready did not prove that the owned startup script had finished NETLOAD and dispatcher load. Code HEAD c415b90139f58d3f76de7e3f15f5dc4c3e68e40a now writes a unique completion acknowledgement after those steps, waits for it with the bounded session timeout, and exposes dispatcher_preloaded only after confirmation.
- Owned bootstrap bindings without bootstrap_completion_confirmed are rejected before any readiness ping; cleanup removes the acknowledgement file as well as the startup script. Explicit legacy fixture behavior is unchanged.
- Focused owner checks: 52 passed, 1 skipped, 1 deselected, 9 subtests; Ruff and git diff --check PASS. Authoritative .\scripts\verify.ps1 exits 0: C# 238 passed; offline Python JUnit 3380 tests with zero failures/errors/skips (3300 passed, 21 deselected, 80 subtests); offline IPC 134 clean; real-data 2 skipped; AutoCAD Mechanical 17 skipped; expected causal-RED handled.
- No live retry was made after this remediation. Approved BVTL.dwg SHA-256 remains 78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8. Fresh SOL review is pending before another live gate.
## Current live boundary (iteration 40)
- SOL approved one fresh live Task-6 gate on code HEAD 386808924829062613d4658af937b98916a0db08. The gate started the owned opt-in bootstrap and stopped at the first claim-bound dispatcher readiness ping: request 05c05ae0456e timed out after 41.81s.
- The failure occurred before BVTL.dwg source open, health, setup audit, standalone inspection, extraction, candidate creation, candidate query, or source reopen. Live Task-6 acceptance remains NOT RUN, not PASS.
- Cleanup is verified: no acad.exe process remains, the disposable candidate directory is empty, BVTL.dwg SHA-256 remains 78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8, and Git remains clean at docs HEAD 0dfebd63d5ac31e175279acb751928c751115d90. No source, accepted drawing, candidate, or production CAD state was mutated.
- Private evidence and resume state: C:/temp/cad-agent-task6-live-20260911/task6-live-gate-iteration40-evidence.txt and C:/temp/cad-agent-task6-live-20260911/wait-safe-resume-state-iteration40.txt. Fresh SOL diagnosis is pending; do not retry live Task 6 before its next bounded verdict.

## Current iteration 39 checkpoint
- SOL's review of code HEAD a44dabb25e490408ccc1b6dffb0e1dff3b17069d found that the bootstrap-bound dispatcher trigger could still leave the client in legacy fixture mode, making the readiness ping claimless.
- The bounded remediation is pushed at code HEAD 386808924829062613d4658af937b98916a0db08. Owned startup bindings now reject a trigger that is not explicitly claim-capable and switch to non-legacy mode before the first readiness ping; explicit legacy fixture callers outside the opt-in startup route are unchanged.
- Focused owner checks: 50 passed, 1 skipped, 1 deselected, 9 subtests; Ruff and git diff --check pass. Authoritative .\scripts\verify.ps1 exits 0: C# 238 passed; offline Python JUnit 3378 tests with zero failures/errors/skips (3298 passed, 21 deselected, 80 subtests); offline IPC 134 with zero failures/errors/skips.
- Unavailable-state probes: real-data 2 skipped and AutoCAD Mechanical 17 skipped. The causal-RED oracle is the expected 1 negative failure. AutoCAD live and M2 Mechanical remain NOT RUN.
- No live retry was made; source SHA remains 78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8, and no source, accepted drawing, candidate, or production CAD state was mutated. Fresh SOL review is pending.

## Status vocabulary

- **Verified:** the named command ran successfully on the named commit and
  environment.
- **Partially verified:** deterministic coverage passed, but a required private
  data or AutoCAD Mechanical gate has not run on the same candidate.
- **Unverified:** no current reproducible evidence supports the claim.
- **NOT RUN:** the gate was intentionally not executed; this is never a pass.

## Supported release environment

- Windows
- Python 3.11
- AutoCAD Mechanical 2027
- Tesseract 5.4.0.20240606

## Current standalone DWG extraction checkpoint (2026-09-11)

- Branch-local implementation head:
  `codex/audit-text-style-compat-20260910`, with standalone extraction code at
  `a17032275a628328dcad0fd15166e413faee3663`; the read-only-open remediation
  is pushed at `1e17f159a2bd089f9797876beb769a872dee45b0`; the latest
  fail-closed fallback remediation is pushed at
  `a21bf814545bbaa3148ce34a7940661be76e1b6d`.
- Task 6 is **Partially verified**: all offline contract/provenance paths pass,
  and the private fixture is now prepared from the approved BVTL inventory. A
  bounded live attempt confirmed health/setup-audit, then correctly failed
  closed at standalone inspection because the existing writable open path did
  not establish `Document.IsReadOnly=true`. Live acceptance remains `NOT RUN`
  (no successful inspection/extraction/query); no source, accepted drawing,
  candidate, or production CAD state was mutated.
- SOL's fresh bounded review of the candidate identity remediation returned
  `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, and `HUMAN_GATE=NO`. The raw
  filesystem identity remains internal for cleanup rechecks; the public
  `candidate_output_identity.file_id` is the schema-valid opaque
  `candidate-file-<sha256(raw identity)>`.
- SOL's next bounded review found and scoped a contract incompatibility: the
  real approved source uses the legitimate AutoCAD layer name `Duong manh`,
  while the standalone request/result validators accepted identifier-only
  text. Commit `a17032275a628328dcad0fd15166e413faee3663` changes only layer
  names to a closed safe-text contract (1-512 printable characters), keeps
  group IDs, component IDs, handles, and entity-type tokens strict, and adds
  the cross-language regression coverage.
- Verification on the exact remediation head exited `0`: C# `238 passed`;
  offline Python `3278 passed`, `21 deselected`, `74 subtests`; offline IPC
  JUnit `134` tests with `0` failures, `0` errors, `0` skipped; real-data
  unavailable probe `2 skipped`; AutoCAD unavailable probe `17 skipped`;
  `git diff --check` passed. The intentional causal RED oracle remains a
  diagnostic expected failure and is not a product failure.
- SOL's fresh review of the first live attempt identified that
  `FileIPCLiveMCPClient.drawing_open` opened the approved source writable. The
  bounded remediation at `1e17f159a2bd089f9797876beb769a872dee45b0` adds an
  opt-in `read_only=True` branch that emits AutoCAD `vla-open` with
  `:vlax-true`; the default path remains writable for disposable candidates
  and existing callers. Focused `drawing_open` tests pass `12`; authoritative
  verification on this commit reports C# `238`, offline Python `3354`, and
  offline IPC `134` with zero product failures. The code commit is pushed;
  fresh SOL review is pending before another live attempt.
- The live Task 6 gate remains `NOT RUN` as acceptance: the previous attempt
  failed closed on `S3C_SOURCE_READ_ONLY_REQUIRED`, and the read-only-open
  remediation is awaiting review. No source, accepted drawing, candidate, or
  production CAD state was mutated. Do not weaken the policy, change source
  metadata, or promote a candidate.
- SOL's fresh review of exact pushed HEAD `cf7b5f139adc63b07d4694a488dd449bf646258f`
  found that a positive start-tab proof could still route `read_only=True`
  through the writable `_.OPEN` fallback when VLA open failed. Commit
  `a21bf814545bbaa3148ce34a7940661be76e1b6d` makes that path fail closed while
  preserving the proven writable fallback for `read_only=False`. The new
  regression covers the exact failure sequence: `13` drawing-open tests pass;
  the focused FileIPC/Task-6 owner set reports `33 passed`, `1 skipped`, and
  `1` intentional causal-RED diagnostic. Authoritative verification on the
  exact pushed HEAD exited `0`: C# `238 passed`, offline Python `3355 passed`,
  offline IPC `134 passed`, real-data `2 skipped`, AutoCAD Mechanical
  unavailable probe `17 skipped`, Ruff and `git diff --check` passed. A fresh
  SOL review of `a21bf814545bbaa3148ce34a7940661be76e1b6d` is pending before
  another live attempt.
- SOL then returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, and
  `HUMAN_GATE=NO` for that remediation. One fresh AutoCAD Mechanical 2027
  attempt was made with `BVTL.dwg` not already open and the approved fixture
  configured. It failed closed before the first source-open call because the
  existing dispatcher did not become ready: `MCPTimeoutError`,
  `request_id=630d574a66d5`, after `14.54s`. No health/setup audit,
  inspection, extraction, candidate, or query ran; live acceptance remains
  **NOT RUN**, not PASS. AutoCAD was on `[Start]` and closed without a drawing,
  the disposable root stayed empty, and the source hash remained
  `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`.
  Private evidence is at
  `C:\temp\cad-agent-task6-live-20260911\task6-live-gate-iteration30-evidence.txt`.
- SOL classified the dispatcher timeout as a bootstrap/readiness boundary and
  authorized one diagnostic without opening `BVTL.dwg`. In a fresh blank
  AutoCAD session, the existing native LISP trigger returned after sending the
  configured `mcp_dispatch.lsp` load expression, but exactly one FileIPC
  `ping` timed out (`request_id=d4f6cc647159`, `5s`) with no result. AutoCAD
  stayed on `[Start]` and was closed; the disposable root stayed empty and the
  source hash remained unchanged. Task-6 live acceptance is still **NOT RUN**.
  Private evidence is at
  `C:\temp\cad-agent-task6-live-20260911\task6-bootstrap-diagnostic-iteration31-evidence.txt`.
- SOL's fresh review of that diagnostic identified the root cause: a native
  text-delivery return does not prove AutoLISP execution on the documentless
  `[Start]` tab. The bounded remediation at code HEAD
  `d79860b91ff34cef9e1898d353a98f6809dc445a` adds an explicit opt-in
  `bootstrap_start_tab` path in the existing File IPC client. With a positive
  Start-tab probe it creates one disposable blank document with `_.QNEW`, loads
  the existing dispatcher, requires a successful FileIPC ping, and only then
  allows source `drawing_open(..., read_only=True)`; load/ping failures close
  the blank document without saving. A real active document does not trigger
  `_.QNEW`, and the default writable path is preserved. The code/plan commit
  is pushed; focused owner tests pass (`21` drawing-open tests; `41` combined
  FileIPC/Task-6 tests excluding the intentional causal-RED diagnostic, with
  one live prerequisite skip); authoritative verification reports C# `238`,
  offline Python `3369`, and offline IPC `134` with zero product failures.
  Fresh SOL review is pending; live acceptance remains **NOT RUN**.
- SOL's next review found a QNEW delivery/readiness race in that remediation:
  a native command-trigger return did not prove the blank document existed
  before LISP was sent. The bounded iteration-33 hardening at code HEAD
  `8040adb54629a533dbfdb3efe1cb2ef0da92fa8e` adds an explicit bounded
  `bootstrap_document_ready_probe` and waits until the window no longer
  reports `[Start]` before marking bootstrap ownership or loading the
  dispatcher. On timeout it emits no LISP or source-open expression and does
  not clean up an unowned document. Task-6 now supplies the matching Windows
  readiness probe. Focused owner tests pass (`24` drawing-open tests; `44`
  combined FileIPC/Task-6 tests with one live prerequisite skip); the exact
  commit's authoritative verify exits `0` with C# `238`, offline IPC `134`,
  offline Python `3372`, zero product failures, and the expected causal-RED
  diagnostic. Private real-data/AutoCAD gates and live Task-6 remain
  **NOT RUN**. Fresh SOL review of `8040adb` is pending.
- SOL then returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, and
  `HUMAN_GATE=NO` for the readiness hardening. Exactly one fresh opt-in live
  Task-6 attempt was run with AutoCAD Mechanical 2027 initially on `[Start]`
  and `BVTL.dwg` closed. `_.QNEW` was delivered, but the bounded readiness
  probe never observed a non-`[Start]` document within `10.26s`; the gate
  failed closed with `START_TAB_BOOTSTRAP_DOCUMENT_NOT_READY` before LISP,
  FileIPC ping, source-open, inspection, extraction, candidate creation, or
  query. AutoCAD remained on `[Start]` and was closed without saving; the
  disposable root stayed empty and source hash
  `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8` stayed
  unchanged. Live Task-6 acceptance remains **NOT RUN**, not PASS. Private
  evidence is at
  `C:\temp\cad-agent-task6-live-20260911\task6-live-gate-iteration34-evidence.txt`;
  fresh SOL review is pending.
- SOL classified iteration 34 as a Start-tab bootstrap-owner defect and
  authorized one bounded primitive diagnostic. Without changing repository
  code or opening `BVTL.dwg`, a fresh AutoCAD Mechanical 2027 process was
  observed at `[Start]`; the existing native startup-script route
  (`acad.exe /nologo /b <script>` with only `_.QNEW`) then produced
  `[Drawing1.dwg]` in the same process. The blank session was closed without
  saving, the disposable root stayed empty, and source SHA
  `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8` stayed
  unchanged. Dispatcher/LISP, FileIPC ping, source read-only open, extraction,
  and live acceptance remain **NOT RUN**. This proves a candidate existing
  native bootstrap primitive; no production owner change has been made.
  Private evidence is at
  `C:\temp\cad-agent-task6-live-20260911\task6-bootstrap-owner-diagnostic-iteration35-evidence.txt`;
  fresh SOL review is pending.
- SOL returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, and `HUMAN_GATE=NO`
  for the iteration-35 primitive diagnostic. The bounded implementation at
  code HEAD
  `8afc7c0494e14cf2711641e4c23b060df4920ef` now owns that proven primitive:
  an opt-in Task-6 path launches a disposable AutoCAD process with an exact
  startup script containing only `_.QNEW`, binds all triggers/probes to that
  launched process's HWND, waits for a positive non-`[Start]` readiness probe,
  loads the existing dispatcher, and only then allows the approved source
  `drawing_open(..., read_only=True)`. Close/timeout cleanup is restricted to
  the owned process; default writable behavior is preserved. Focused checks
  pass (`48 passed`, `1 skipped`, `1 deselected`, `9 subtests`, with the
  intentional causal-RED oracle excluded). The exact authoritative verify
  exits `0`: C# `238 passed`, offline Python `3296 passed`, `21 deselected`,
  `80 subtests`, offline IPC JUnit `134` with zero failures/errors, real-data
  unavailable probe `2 skipped`, and AutoCAD Mechanical unavailable probe
  `17 skipped`. No live Task-6 run has been made on this head; source,
  accepted drawing, candidate, and production CAD state remain unchanged.
  Code is pushed; documentation/evidence is being recorded separately and
  fresh SOL review is required before the next live attempt.
- SOL then returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, and `HUMAN_GATE=NO`
  for the owner remediation and authorized exactly one fresh live Task-6 gate.
  Iteration 37 proved the new startup-session owner reached
  `Autodesk AutoCAD 2027 - [Drawing1.dwg]` in the same owned process
  (`PID 28488`, `HWND 4983510`) from `[Start]`. The first failure then occurred
  at the existing dispatcher readiness boundary:
  `MCPTimeoutError`, FileIPC ping request `03e4086d8d2f`, after `73.71s`.
  The test stopped before opening `BVTL.dwg`, health/setup audit, inspection,
  extraction, candidate creation, or query. Cleanup removed the startup
  script and left no `acad.exe` process; the disposable candidate directory
  stayed empty; source SHA remained
  `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`.
  Live Task-6 acceptance remains **NOT RUN**, not PASS. Private evidence is at
  `C:\temp\cad-agent-task6-live-20260911\task6-live-gate-iteration37-evidence.txt`;
  fresh SOL review of this dispatcher boundary is pending.
- SOL classified iteration 37 as a dispatcher-load owner finding and
  authorized exactly one non-live remediation. Code HEAD
  `669472d2f8c900b58146e23921dab0fc90644d41` now reuses the owned startup
  script to perform bounded bootstrap-only loading: `_.QNEW`, approved plugin
  `_.NETLOAD`, and one root-bound load of the exact `mcp_dispatch.lsp` path.
  The generated script admits no source, save, extraction, candidate, or
  publication command. The client requires a claim-bound FileIPC ping after
  document readiness and before runtime setup/source-open; initial dispatcher
  load no longer depends on keyboard-delivered AutoLISP. Focused checks pass
  (`49 passed`, `1 skipped`, `1 deselected`, `9 subtests`); the exact
  authoritative verify exits `0` with C# `238 passed`, offline Python `3297
  passed`, `21 deselected`, `80 subtests`, offline IPC JUnit `134` with zero
  failures/errors, real-data `2 skipped`, and AutoCAD Mechanical `17 skipped`.
  No live retry was made on this head; live Task-6 acceptance remains **NOT
  RUN**. Fresh SOL review is required before another live gate. Private
  evidence is at
  `C:\temp\cad-agent-task6-live-20260911\task6-bootstrap-dispatcher-owner-remediation-iteration38-evidence.txt`.

## VIEWPORT-by-handle branch checkpoint (2026-09-10)

- The final viewport implementation remediation was pushed as
  `9c2ccbfa358be53b0192591d7153edd542363551` on
  `codex/audit-text-style-compat-20260910`. The authoritative verification
  evidence below was run on that exact final implementation head; this is a
  branch-local checkpoint and does not change the canonical `main` snapshot
  above.
- The dedicated read-only `viewport_query` path is implemented through the
  existing .NET/File IPC owner and Python client. It is bounded to one
  hexadecimal handle, an exact lowercase source hash, closed parameters, and
  `approval=null`; it has no redraw, save, Xref, promotion, or second transport
  path.
- `scripts/bootstrap.ps1` exited `0`; the lock/environment contracts passed for
  40 pinned distributions. The bootstrap emitted only the existing invalid
  `~ip` distribution warning while all locked requirements were already
  satisfied.
- `scripts/verify.ps1` exited `0`: .NET Release build succeeded; 211 C# tests
  passed; offline Python JUnit recorded `tests=3311`, `failures=0`, `errors=0`;
  the `dotnet_ipc` JUnit recorded `tests=124`, `failures=0`, `errors=0`; Ruff passed;
  and the verifier reported `All checks passed`.
- The verifier's causal-RED negative oracle intentionally recorded
  `tests=1`, `failures=1`, `errors=0`; this is an expected diagnostic probe and
  did not fail the authoritative verifier. The unavailable-state probes
  recorded two real-data skips and 16 AutoCAD Mechanical skips. The verifier
  reported `AutoCAD live marker: NOT RUN` and `M2 Mechanical benchmark marker:
  NOT RUN`.
- The new opt-in disposable-DXF viewport test is present but its focused marker
  is `SKIP` because `CAD_AGENT_FILE_IPC`, matching File/.NET IPC roots,
  `CAD_AGENT_AUTOCAD_HWND`, and `CAD_AGENT_AUTOCAD_LISP_PATH` are absent. No
  disposable fixture was created, no live AutoCAD/File IPC request was sent,
  `BVTL.dwg` was not queried in this checkpoint, and the frozen page-1
  candidate was not changed or promoted.
- The three first-pass independent reviews identified material evidence-binding
  drift and protocol-test hardening gaps. Commits
  `e9e692315621682e9d150e1b3cb54a1d71893f2d` and
  `9c2ccbfa358be53b0192591d7153edd542363551` now bind result path/hash/handle,
  enforce closed payload/DBMOD/field-state semantics in Python, schema and C#,
  reject null-present optional field keys, and assert the live plugin binary
  path/SHA-256. Focused remediation evidence is Python `143 passed, 50
  subtests`, C# `43 passed`, live harness `9 passed, 7 skipped`, Ruff `PASS`,
  and `git diff --check PASS`. Requirements/architecture, correctness/test,
  and security/operations final re-reviews all passed with
  `MATERIAL_FINDING=NONE` and `HUMAN_GATE=NO`.
- SOL's bounded continuation action produced the metadata-only, read-only page-1
  reuse execution packet recorded in
  `docs/superpowers/implementation-records/2026-09-10-page1-reuse-execution-packet.md`.
  It freezes the eligible page-2 reuse groups and page-1 delta groups, binds the
  existing source/oracle/candidate hashes, and defines the exact future
  `viewport_query` input/expected invariants. The complete packet remains
  outside Git because it references private drawing artifacts; its SHA-256 is
  `312e2ce76ebf3998cbf7b9d1f6e64c8c5d6c6c2ec3d357047307193a2dfebafe`.
- The packet records the established execution-output item-13
  `PASS_VISUAL_FIDELITY` for the unchanged frozen candidate. This is not
  production approval or authorization to use the candidate as the page-1
  reuse solution: live AutoCAD/FileIPC prerequisites were absent, the viewport
  request remains `NOT RUN`, the candidate remains unpromoted, and no source,
  candidate, or CAD state was mutated.
- This branch remains **Partially verified**: deterministic contracts, owner,
  dispatcher, client, test harness, remediation, and authoritative verification
  passed, but live viewport evidence and private fidelity evidence remain
  `NOT RUN`/unavailable. The source drawing
  hash remains `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`.

## Live bootstrap probe follow-up (2026-09-10)

- A bounded read-only bootstrap probe was attempted after the packet checkpoint.
  AutoCAD Mechanical 2027 opened `BVTL.dwg` as `Read Only`; the source hash
  remained `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`
  and no save or source mutation occurred.
- The repository plugin DLL was not present in the AutoCAD process module list,
  so the existing health request timed out and no result file was produced.
  The request pair is retained outside Git as diagnostic evidence; this is
  `NOT RUN`, not a live-pass claim. No trust/security bypass was used, and the
  frozen candidate, packet, and production drawing were not changed.
- The read-only AutoCAD process was stopped by exact PID after the failed
  bootstrap. A future live attempt requires the approved APPLOAD/NETLOAD
  boundary or equivalent declared prerequisites; it must not retry by bypassing
  AutoCAD trust controls.

## SOL live-gate decision (2026-09-10)

- SOL consumed the pushed bootstrap evidence and returned
  `VERDICT=BLOCKED`, `MATERIAL_FINDING=live viewport registration is blocked at
  the declared human/operator trust boundary`, and `HUMAN_GATE=YES`.
- The single bounded next action is for the human operator to manually load the
  already-approved repository plugin DLL through the declared NETLOAD/APPLOAD
  workflow in a fresh AutoCAD Mechanical 2027 session, verify plugin
  identity/health only, and stop. The operator must not open or mutate
  `BVTL.dwg` or any candidate during this step.
- No automated trust bypass, retry loop, source/candidate mutation, or live-pass
  claim is permitted. Until that human-gated health check occurs, the live
  viewport gate remains `NOT RUN` and the branch remains **Partially verified**.
- The already-approved DLL is present at
  `autocad_plugin/CadAgent.AutoCAD2027/bin/x64/Release/net10.0-windows/CadAgent.AutoCAD2027.dll`
  with size `455168` bytes and SHA-256
  `427c5a80c2c9c1f070a14aad0c311ad9fb94c5d6b31b6f74a13228a48bef1286`.
  This identity check is read-only; it does not establish that AutoCAD has
  loaded the DLL.

## Live health and viewport-query follow-up (2026-09-10)

- SOL subsequently classified the approved session setup as Luna-owned routine
  work (`HUMAN_GATE=NO`) within the existing trust boundary. A fresh AutoCAD
  Mechanical 2027 session loaded the exact approved DLL above; the module list
  confirmed the repository binary before any production drawing was opened.
- The bounded health request passed with plugin version `1.0.0`, host
  `AutoCAD Mechanical 2027`, IPC directory `C:\temp`, `read_only=true`, and
  the expected plugin SHA-256. Health evidence remains outside Git at the
  local run boundary; its SHA-256 is
  `a8f2817c6f24efe685f9ef293adfcf90becb9a48801b84934e43ca9cba3b7bae`.
- `BVTL.dwg` was then opened through the existing read-only owner and exactly
  one packet-bound request ran:
  `request_id=layout-vp-126babe-20260910`, `handle=126BABE`.
  The result was `success=true`, `changed=false`, `type=VIEWPORT`, `layer=0`,
  all seven declared fields were `OBSERVED`, `DBMOD=0 -> 0`, and the source
  hash was unchanged before/after at
  `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`.
  The private result evidence remains outside Git with SHA-256
  `7aa5bd9478c8d84c267edb44bf93de1a5e1ac5fd314d5984f1f9e091663dc11d`.
- The source drawing was closed without save, the disposable template drawing
  was closed without save, and the exact AutoCAD process was shut down. No
  source, accepted drawing, frozen candidate, packet, or production CAD state
  was mutated. This closes the declared read-only viewport-registration gate;
  it does not authorize production promotion or claim that the page-1 drawing
  workflow is complete.

## SOL connector verification follow-up (2026-09-10)

- GitHub independently exposes branch
  `codex/audit-text-style-compat-20260910` at
  `6fc95824beff73782d03ba955b2aa8b29df3df28`, so the live evidence record is
  pushed and readable from the canonical repository surface.
- The existing read-only Codex workspace connector then returned
  `USER_NOT_LOGGED_IN` / `asdk_app_6aa23e5941188191bcc379ec7942dbee is not
  connected` on both fresh status and file reads. This is a connector-account
  failure, not a Git, source, or evidence failure.
- One bounded controller recovery was attempted with the configured narrow root.
  `On` failed Quick Tunnel readiness (`metadata=-1`, `mcp=-1`, timeout) before
  any Worker KV update; `Doctor` reported no runtime state. The controller was
  then returned to intentional `Off` and confirmed no managed devspace or tunnel
  process remained. No AutoCAD, source drawing, candidate, or Git evidence was
  rerun or changed.

## Current canonical snapshot (2026-09-09)

- Fresh GitHub `main` is `2d320361e2146d0602aac6f226f5bffed5f931a5`.
  The drawing-setup expectation-policy candidate is tracked by open PR #422
  and governed by issue #412; those GitHub records are the canonical current
  state pointers. The earlier implementation head
  `90c62eb361f56e3241724f7fa2aa978a40d89ddc` and lifecycle checkpoint
  `5372aa296248e33a4be8917da75bd2b4beb09af3` are historical evidence only.
- REAL IMAGE/PDF P1 live Mechanical review is **Verified** for the private
  nine-page PDF identified by SHA-256
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`.
  The existing `run-pdf` owner completed all 36/36 page stages in manifest
  `90fc43a14dcd52517de273f98e57bc7c1b860c86257cc406080180176953b261` under
  `C:\temp\cad-agent-real-p1-20260908-01` with approved calibration
  `STATUS-e48f3970-144dpi-1to40`, `144` DPI, and `7.055555555556` mm/px.
- AutoCAD Mechanical 2027 live session identity was PID `17520`, HWND
  `1705904`. The nine accepted read-only reports recorded structural/geometry
  counts `828/828`, `855/855`, `675/675`, `878/878`, `396/396`, `528/528`,
  `606/606`, `653/653`, and `990/990`; every report had
  `passed=true`, `geometry_degraded=false`, zero mismatches, and zero warnings.
  No repair, save, or production drawing mutation was performed.
- The observed P1 blocker was AutoLISP real-number serialization truncating
  values through `vl-princ-to-string`. Commit `973b6151da34d20adc1d7b399e37eb20920abb7a`
  changes only `mcp_integration_lib/mcp_dispatch.lsp` and its contract test to
  use `(rtos value 2 16)`. Focused coverage is `104 passed`; the authoritative
  verifier on that exact commit exited `0` with offline JUnit `3260/0/0/0`,
  dotnet IPC `118/0/0/0`, .NET `202 passed`, and the declared causal RED plus
  unavailable-state skips recorded by the script.
- The private source and all live artifacts remain outside Git. The run remains
  `release_profile=DRAFT_REFERENCE` and
  `authoritative_release_eligible=false`; no visual-fidelity, authoritative
  drawing-setup, production mutation, or release claim is implied by this P1
  review.
- `FIRST_UNSATISFIED_PRODUCT_BOUNDARY` is now
  `M2_DRAWING_INITIALIZATION_SETUP_VERIFIED`: the existing image/PDF path still
  requires approved Drawing Definition/Profile/Domain Pack/template provenance
  and hash-bound read-only `SETUP_VERIFIED` evidence before it can be promoted
  beyond `DRAFT_REFERENCE`. M2 remains separate from this read-only P1 pass.
- M3 real-provider acceptance remains
  `BLOCKED_BY_CREDIT_BALANCE_EXHAUSTED`; no provider retry, billing action, or
  credential use is included here.
- Older sections below remain historical evidence and do not override this
  snapshot. Current GitHub state and exact-head evidence remain canonical.

## Drawing Setup expectation-policy candidate (2026-09-09)

- The approved contract proposal is bound to SHA-256
  `17ee02ea89d6fadce5148b730a8f62d302b032a29431cba6a3a33847b4e0da6d`.
  The earlier implementation head `90c62eb361f56e3241724f7fa2aa978a40d89ddc`
  is a historical checkpoint; the current candidate and its evidence are
  tracked by PR #422 and issue #412. The CLI compatibility proof confirmed
  that `cad_agent/cli.py` required no change.
- Historical pre-remediation focused Drawing Setup regression/contracts passed:
  `98 passed`; the policy-bearing `drawing-setup-verify` CLI proof passed and
  emitted valid scoped evidence.
- Historical pre-remediation `scripts/verify.ps1` evidence recorded exit code
  `0` in
  isolated worktree `C:\temp\cad-agent-release-verify-20260909-01`, using a
  private writable `TEMP/TMP` root
  `C:\temp\cad-agent-release-verify-temp-20260909-01`. It recorded .NET
  plugin tests `202/202`, `dotnet_ipc` `68 passed + 50 subtests`, offline
  Python `3222 passed, 19 deselected, 72 subtests`, and JUnit totals
  `3294` with zero failures/errors. The expected causal RED oracle was handled
  by the verifier; it is not a product-test failure.
- Current remediation verification is bound to the canonical PR #422 / issue
  #412 state. The remediation head passed the local combined release evidence
  and all hosted checks; issue #412 comment `5603356625` records the
  authoritative SOL acceptance.
- This is **Partially verified**: deterministic contract/evaluator/CLI and
  authoritative offline gates passed, while live AutoCAD/FileIPC and private
  real-data gates were `NOT RUN`/`SKIP`. The prior live
  `drawing_setup_verify` projection remains **NON_PASS** and was **not
  retried**. No M2 `SETUP_VERIFIED` claim is made, and no source drawing was
  saved or mutated.
- AutoCAD PID `12012` remained running because the Computer Use surface did
  not expose the disposable session; no force termination, drawing save, or
  CAD mutation was performed. M2 and private real-data acceptance remain
  deferred with their existing owners/reasons.

## Historical provider-independent hardening ledger (through 2026-09-02)

- This status record uses canonical `main` evidence baseline
  `549fd27d1c44600fd467665ae71759d0eda74a9f` after bounded Phase 1A PR #373.
  This docs-only reconciliation records that new evidence without changing
  any implementation. The implementation/evidence below includes the preceding
  #344–#347 hardening records, the Phase 1/2 facades, the late active-drawing
  currentness repair, canonical rollback restoration, the bounded Phase 3
  pilot, the bounded Phase 4 PDF-to-pilot binding, and the documentation
  currentness reconciliations in PRs #366–#370, plus the bounded Phase 1A
  query adapter in PR #371 and its late active-DWG currentness repair in PR
  #373. The eventual publication merge commit is the
  exact GitHub source of truth for this record.
- PR #344 (`c50f90f145e91e397137fd0305208e8c64c03c4e`) closed the measured
  abandoned publication-manifest lock boundary. The existing manifest owner
  now records a bounded Windows PID/process-start identity, retains an
  exclusive lock handle, reclaims only a provably dead owner, and remains
  fail-closed for missing, malformed, inaccessible, live, or uncertain locks.
- Evidence at the merged implementation head: focused publication-manifest
  tests `32 passed`; broader owner/IPC regression `206 passed` with one
  intentional causal RED deselected; canonical verifier exit `0` with offline
  `3062 passed`, dotnet IPC `117 passed`, the one expected causal RED, real-data
  `2 skipped`, and AutoCAD unavailable `14 skipped`. No provider call, M2
  retest, live CAD mutation, credential, source drawing, or accepted drawing
  was involved.
- A new disposable staged-run crash/restart/resume epoch used the existing
  `cad_agent` owner: the child exited `17` during Semantic IR, the manifest
  retained Primitive IR as `completed` and later stages as `pending`, one
  `resume` completed all stages, the input SHA-256 was unchanged before/after,
  no manifest lock survived, and the disposable root was removed. This closes
  the measured staged-pipeline resume boundary only; it does not claim live
  AutoCAD, FileIPC, provider, or M2 acceptance.
- PR #347 (`cae0250f836f2710ba3122406e97ae1fb10355bf`) closed the measured
  `UNCERTAIN_FILEIPC_COMPLETION_CLEANUP` boundary. On timeout the existing
  `DotNetIPCClient` now preserves only the exact request/result pair because
  receiver completion is not disproven; successful and terminal error paths
  retain their exact-pair cleanup behavior, with no retry or daemon.
- FileIPC timeout evidence: a delayed receiver wrote a result after the old
  client had already deleted the pair, leaving an unowned
  `cadagent_dotnet_result_timeout-late-001.json` survivor. The RED regression
  then passed after the bounded owner fix. Focused owner/IPC coverage was
  `71 passed` with `5` live prerequisite skips and `50` subtests; the canonical
  verifier recorded dotnet IPC `118 passed` and offline `3063 passed`.
- PR #358 (`ccc2fd13a7795fade1212f7a27d21c7`) closed the measured late
  active-DWG TOCTOU currentness boundary. PR #360
  (`3af290c3a8ccace082ba896eb64fbbcdb511e5d5`) then restored canonical staged
  DXF and build-evidence bytes after a failed second review and verified a
  canonical reopen, with the backup path excluded from the reopen assertion.
- PR #361 (`d2d8865516ceffb6d41dd7ae3075a7d3715d7953`) added the bounded
  synthetic simple-shaft pilot on merged main
  `ac049a2ed43d3e5b25f0da1adcf217491933198f`. The selected fixture is
  `tests/fixtures/phase3_synthetic_simple_shaft_v1.json`, SHA-256
  `a9c3a17b59aace782c5c28679e55b68b8036b9636ede5d40bc64d0697e10f55f`.
  It reuses Primitive IR, Semantic IR, the DXF builder, headless review, and
  SHA-bound build evidence for a typed `mechanical_shaft_step` plus
  `mechanical_hole_feature` candidate. Focused/regression coverage was
  `133 passed`; exact-head hosted checks and the full offline verifier passed
  with `3178` JUnit tests and no failures or errors.
- PR #364 (`a6590f4d74a0fe6e54a70ce32121462707439e7f`) closed the bounded
  synthetic Phase 4 PDF-to-typed-pilot binding boundary. The existing fixed
  `run_pdf_stages` path is now accepted only when it yields exactly eight
  axis-aligned outline lines plus one interior circle under the declared
  tolerance/topology contract; the adapter binds the existing page/source
  hashes before producing the typed shaft/hole pilot. Focused coverage was
  `8 passed`, the nearest regression was `296 passed` with one expected
  private-data skip, and the authoritative verifier recorded `3110 passed`,
  `3182` JUnit tests, `.NET 198 passed`, and exact-head hosted checks PASS.
- PR #371 (`e2a0dc9b690b72db5b57c376759950f5cae35397`) closed the measured
  Phase 1A bounded-read gap. The new `cad_agent/drawing_query.py` adapter
  reuses DARA, the R3 component/view registry, R4 candidate state, and the
  existing typed `drawing_get_variables`/`entity_get` owner. It accepts only
  closed explicit-handle or exact component/view selectors, resolves at most
  64 handles before live lookup, and emits tamper-evident observation/query
  results. It never enumerates the drawing and never owns document lifecycle
  or mutation. Focused coverage was `13` new tests and `147` related tests;
  the authoritative verifier recorded `3123` offline tests and `118` .NET
  IPC tests, with the intentional causal RED and unavailable live markers
  unchanged. This closes the bounded offline MECH-1A contract only; broad
  layer/type/bbox discovery remains deferred to the existing transport owner.
- PR #373 (`52f9a56bebc6f84bd3fe38caa4d38718e8d5f5ce`, merged as
  `549fd27d1c44600fd467665ae71759d0eda74a9f`) closed the measured late
  active-DWG TOCTOU reopened by the Phase 1A adapter. A switching-client
  causal RED showed that `query_entities` could seal a result after the active
  document changed; the adapter now reuses `_live_session` immediately before
  result finalization and refuses `ACTIVE_DOCUMENT_MISMATCH`. Focused
  drawing-query/facade/candidate/registry/skill coverage was `253 passed`, and
  exact-head hosted checks passed. No live query, provider call, M2 retest, or
  CAD mutation was involved.
- A bounded generated-pilot provenance successor is under review in PR #378,
  based on exact main `8cfbce22ba9f965164fbc9a4d67824475c15f150` at
  implementation head `7a49d201d9815fb138862edef13e156de5a13abf`. It composes
  the existing Mechanical pilot, DARA, R3, R4, and drawing-query owners
  without fabricating a Base-CAD R2 handoff. Its explicit generated mode seals
  source/candidate/build/pilot evidence, a non-disclosing canonical candidate
  path binding, and candidate-handle bindings, and rejects mixed, foreign,
  stale, replaced, or tampered provenance. Focused coverage is `235 passed`;
  the canonical verifier at the implementation head exited `0` with offline
  `3140 passed, 18 deselected, 72 subtests`, .NET `198 passed`, IPC `68 passed
  + 50 subtests`, and the intentional causal FileIPC RED retained. This
  remains deterministic/offline evidence only: live Phase 1A FileIPC query
  acceptance is not claimed and M3 real-provider acceptance remains blocked by
  exhausted credit balance.
- Disposable Phase 3 live epochs remain **NON_PASS**. Epochs 1–2 stopped at
  the SecureLoad/bootstrap and dispatcher terminal-result boundaries. Fresh
  current-main epochs #05–#07 reused the loaded canonical dispatcher and
  valid foreground/root bindings: #05 timed out on claim-bound `ping`, #06
  returned a terminal `drawing-open` result but timed out on the immediate
  post-activation read-back, and #07 repeated the read-back timeout after a
  bounded settle interval. Epoch #08 had no recoverable request/result
  evidence after cleanup and is not verifiable. Epoch #09 durably captured
  request `a80c0e43547a` for claim-bound `ping`, but no terminal result was
  produced within the bounded timeout; the post-epoch diagnostic reported
  `DISPATCH_SYMBOL_PRESENT`, `ROOT_DIRECTORY_VALID`, `PENDING_OWNER_NIL`, and
  `CMDACTIVE=0`. Epoch #10 then used a fresh disposable candidate and valid
  root/foreground bindings for claim-bound `ping` request `78b713ef4479`; it
  also timed out with no terminal result. A bounded request-path diagnostic
  wrote a correctly shaped claim-bearing `ping` request, invoked the existing
  dispatcher, observed the return marker, and still produced no matching
  result before cleanup. Every candidate was disposable, closed without save,
  kept its source/candidate SHA, and left zero owned IPC survivors. No live
  review PASS is claimed.
- Epoch #12 was a setup-only NON_PASS: its evidence observer accidentally
  dropped the `_mcp_claim_bound` marker, so the client emitted a legacy
  claimless request and timed out. It is not a semantic acceptance result.
  Epoch #13 corrected that harness condition and made one genuine
  claim-bound `ping` attempt (`ab1f472b75ea`), but the normal
  `c:mcp-dispatch` route still produced no terminal result within 30 seconds.
  The candidate remained byte-identical and cleanup left zero owned IPC
  survivors.
- A separate read-only in-session diagnostic then showed `CMDACTIVE=0`, an
  empty-root `c:mcp-dispatch` entry returning normally, and
  `mcp-dispatch-core` returning its expected missing-file error for a
  nonexistent request. Together with the earlier direct-core diagnostic,
  this proves the core request/result owner can work while leaving the
  request-bearing command context unresolved.
- Before Epoch #14, the next provider-independent boundary was
  `PHASE3_FILEIPC_C_MCP_DISPATCH_REQUEST_CONTEXT_TERMINAL_RESULT_UNAVAILABLE`,
  owned by the existing `FileIPCLiveMCPClient` plus the loaded AutoLISP
  dispatcher. The then-current diagnostic was causal RED for the
  request-bearing path but did not justify replacing the intentionally
  asynchronous `PostMessageW` contract with a different transport or generic
  execution ACK.
- Epoch #14 then closed the request-bearing ping/result boundary for the
  existing owner: on canonical main `63795aeda4730cc51c803ce6649f7372e0c9fd95`,
  a fresh disposable root returned claim-bound request `d1d4197d869f` with
  terminal `ok=true` and `{ "ready": true }`. Exact AutoCAD PID/HWND and
  foreground matched, the disposable candidate SHA was unchanged, and owned
  IPC cleanup left zero survivors. This is a ping-only owner acceptance, not
  a Phase 1A entity-query acceptance or provider-backed M3 PASS.
- Epoch #15 then closed the exact-current drawing read-back boundary on current
  main `8dc6b6e0217a8085590e7a7454f24460cc292a28`: the existing owner returned
  claim-bound `drawing-list-open-paths` request `ff4a5a76e560` with the active
  disposable candidate path. AutoCAD PID/HWND and foreground matched, the
  candidate remained at SHA-256
  `f7d21a2c5608d1bf4185d13e619bc9c5663fe01dacab6eea4ad9e0b3a4dbbd90`, and
  owned IPC cleanup left zero survivors. This is exact drawing read-back only;
  it does not establish a Phase 1A provenance-bound entity query.
- After the current-main candidate was regenerated from the canonical fixture,
  Epoch #27 was run once on main `d440073c6913254083696d7c8dfa06da2de9d88c`
  using the existing `FileIPCLiveMCPClient` and loaded canonical dispatcher.
  AutoCAD PID `7964`, HWND `11601136`, and foreground equality were verified;
  the disposable candidate was SHA-256
  `96538393f65df60fc9a76572b0d9aed6cf1b72457f98deed969450d2f87379c9` before
  and after. The claim-bound `ping` request `fcea6377e974` timed out without a
  terminal result, so no entity read or query was attempted. The candidate was
  closed without saving and owned IPC cleanup left zero survivors. This is a
  NON_PASS environment/precondition result, not a provider or code PASS, and
  was not retried.
- The current next provider-independent boundary is
  `PHASE1A_LIVE_BOUND_QUERY_PRECONDITION_MISSING`, owned by the existing
  DARA/R3/R4 provenance-currentness owners plus `drawing_query.query_entities`
  and `FileIPCLiveMCPClient`. The active disposable drawing is
  `C:\\temp\\cad-agent-m3-live-20260831-02\\candidate-pre-repair.dxf` at
  SHA-256 `f7d21a2c5608d1bf4185d13e619bc9c5663fe01dacab6eea4ad9e0b3a4dbbd90`
  with one `2F/LINE` entity, while the accepted Phase 1A fixture binding is a
  different synthetic artifact (`fd50d352fa93db9f171847e7d61a9b2c191cb65ef613be707ef29a8cc834bba0`)
  with bound handle `C3D4`. No exact accepted provenance/candidate binding for
  the active drawing is available, so no entity-query request is justified.
  Independently, Epoch #27 leaves the live runtime precondition
  `PHASE3_FILEIPC_DISPATCHER_TERMINAL_RESULT_MISSING`; no new live epoch is
  justified until the request-bearing canonical dispatcher path is shown ready
  without retrying the uncertain request.
  The next oracle is one future disposable exact-bound candidate/entity query
  with matching artifact, reference, R3 binding, candidate state, and handle,
  followed by claim-bound result/hash, pre/post identity, integrity, and
  zero-survivor cleanup checks. Real/private PDF evidence and provider-backed
  M3 acceptance remain unrun/non-pass.

## M3 real-provider/live boundary — frozen non-pass

- Current state: **`M3_REAL_PROVIDER = BLOCKED_BY_CREDIT_BALANCE_EXHAUSTED`**.
  PR #340 remains an OPEN/DRAFT, unmerged provider lane at exact head
  `714620001e8dbc1c49adbb13b9af4d5821eb6a7d`, branch
  `codex/m3-task3-responses-provider`, based on its frozen base `main`
  `e8386342d4a7bdab7ee12eb7b163f573e6b2df02`. Current `main` has advanced
  independently through provider-independent PRs #344–#369; no rebase was
  performed or implied.
- Frozen real-provider evidence: exactly one authorized synchronous
  `gpt-5.6-sol` attempt was made; the provider returned HTTP `429`; no
  provider-generated `response.id` or terminal status was observed; strict
  structured output was not reached; and no retrieve, cancel, retry, or
  second provider call occurred. Credential contents were not recorded.
- The privacy-safe read-only account/limit inspection classified the captured
  429 as **credit balance exhausted**. This is a non-PASS provider result and
  does not establish a live R5 verdict or a provider-backed M3 acceptance.
- Exact-head offline/hosted evidence remains reusable: focused Responses
  tests `39 passed`, canonical offline `3104 passed` with `18 deselected` and
  `72` subtests, dotnet IPC `117 passed`, and hosted tests/reuse/CodeQL all
  passed (`33420238403`, `33420238347`, `33420238411`). These checks do not
  substitute for real provider acceptance.
- No M3 R5/R6 live AutoCAD/FileIPC epoch was run, no M2 retest was run, and
  PR #340 and historical PR #337 were not merged. No provider call, billing,
  credential use, or CAD mutation is authorized while this boundary is
  frozen. The provider implementation/evidence in PR #340 is preserved
  unchanged; this section is documentation-only currentness reconciliation.
- Next boundary: a future Human-authorized account/entitlement resolution
  followed by one fresh bounded provider acceptance call. No retry or live
  M3 work is implied by this documentation update.

## M3 Task3 two-phase official provider start — merged boundary

- State: **Merged; offline and isolated official-SDK START verified; live
  AutoCAD M3 epoch NOT RUN**. This boundary is START_ONLY. Resume/fork remain
  fail-closed and are outside this boundary.
- Merged implementation: PR #334 at `cac069c45ea44ae09bd1c2062476b0febb4a37cb`;
  its exact implementation head was `42bdf11e256c7b68018962fbcab9142e3798074c`,
  based on `main` `b06e533bbcbe7221e7c3ad9234e8497f9b422ec8`. PR #332 remains
  OPEN/DRAFT/evidence-only and is untouched.
- The canonical Task3 child now validates server-owned start custody first,
  calls the existing low-level official `openai-codex` 0.144.4
  `CodexClient.thread_start`, and only then creates the immutable worker
  binding from the provider-generated thread ID. No caller-selected or
  pre-bound provider thread ID is accepted.
- Provider observation is a reduced typed allowlist: generated thread ID,
  model/provider, cwd, approval policy/reviewer, effective sandbox, and
  instruction-source path/hash observations. Server-owned config hash,
  `experimental_api=false`, schema/hash/validator identity, and authority
  source IDs/roles remain request/custody fields and are not echoed as
  provider evidence.
- Instruction-source binding is fail-closed: canonical observed paths must
  remain inside the disposable runtime root, be regular non-reparse files,
  hash to their actual bytes, and match exactly one expected authority source.
  Missing, extra, duplicate-hash ambiguity, path escape, symlink/reparse, and
  hash drift are rejected. Provider `readOnly` is accepted only as a stricter
  effective policy than server maximum `DISPOSABLE_ONLY`; widening access,
  network, cwd, model, or approval is rejected.
- Focused Task3 suites passed `128` tests; the nearest full offline suite
  passed `3059` tests with `18` deselected and `72` subtests. The affected
  Task6 event suite passed `161` tests after a compatibility repair. The
  authoritative verifier is rerun on the final documentation head before
  release integration.
- Real isolated official SDK START/BIND passed with package `openai-codex`
  `0.144.4` in a fresh disposable CODEX_HOME and no copied credentials. The
  typed response supplied provider-generated thread identity, exact model and
  provider, `approvalPolicy=never`, reviewer `user`, canonical instruction
  source hash, and effective `readOnly`/no-network sandbox. The bind result
  used that same provider thread ID; `config_sha256` was absent from provider
  observation as required. No Task6/R5/R6/AutoCAD mutation was performed.
- Remaining boundary: one NEW disposable provider-backed M3 LINE epoch. The
  current machine has no running AutoCAD process or FileIPC/COM/ROT receiver,
  so no live runtime identity, candidate, R5/R6 mutation, Task6 pair, or
  close-without-save evidence can be produced now. M2 remains accepted and is
  not retested; the bounded MECH-1A read/query contract is accepted, while
  broader unbounded introspection remains deferred.

## Accelerated reuse-first program: PLANNING/GOVERNANCE ONLY

- Exact planning base: `d00b24e4853d2bfa6bd94873d3014e37575e2718`.
- Issue: #68.
- PR: #69; GitHub is the live source of its current state.
- Before merge, complete the PO review and merge gate for PR #69.
- After merge, verify fresh `main` at the program merge SHA, then create three
  separate Wave 1 Issues:
  - official vision handoff;
  - R1C source integrity/fusion;
  - S2C/S3B live readiness.
- No runtime capability is automatically opened by this program, its PR, or its
  merge.
- S3B AutoCAD live: **NOT RUN**.
- Hosted AutoCAD .NET: **NOT RUN**.
- All current future-runtime locks remain in force.

## Reuse Integration Rebaseline

- State: **Accepted for R0 governance/rebaseline scope**. Runtime work remains
  locked; this acceptance does not promote any future subsystem.
- R0-T6 documentation phase state before aggregate verification: **Executing**.
- Current Task 7 implementation base:
  `07a14ce3623024f2df848b2b88ff447980772492`.
- Implementation record:
  `docs/superpowers/implementation-records/2026-08-04-reuse-integration-rebaseline.md`.
- Full-verifier candidate SHA:
  `a373114c91edd02a6a4dd086b02b2a89433be964`.
- Final record-only SHA: recorded in the final PR and handoff after the
  record-only commit; the canonical verifier was not rerun on that commit.
- R0-T6 implementation base:
  `cac38a1cf558aee1245ae669bcc106bf3619b8e5`.
- Design merge:
  `4cc2c0f198484581f5781466e769441d4e7da669`.
- Machine-readable inventory:
  `docs/superpowers/reuse/2026-08-04-reuse-inventory.json`.
- Canonical audit:
  `docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md`.
- Evidence available through R0-T5: the closed inventory contains 20
  capabilities; the legacy compatibility baseline covers 37 commands and
  historical v1 manifest defaults; the architecture ratchet contains 24
  explicitly accepted existing violations; R0-T5 focused tests passed `6` and
  its canonical verifier passed with offline `787` tests and dotnet IPC `38`
  tests on the reviewed candidate.
- Runtime changes: none in the design merge or this documentation task. No
  runtime capability is promoted.
- VS-T4/VS-T5 old rollout: **locked**. M2 Drawing Initialization remains
  authoritative.
- Private-data gate: **NOT RUN**.
- AutoCAD Mechanical live gate: **NOT RUN**.
- Codex SDK spike: **NOT RUN**.
- Unavailable-state `SKIP` results, when collected, are not acceptance evidence.
- R0 acceptance evidence: inventory checker exit `0`; architecture checker
  `PASS`; focused R0 suite `41 passed, 0 skipped`; canonical candidate offline
  JUnit `808/0/0/0` and dotnet IPC JUnit `38/0/0/0`.
- Remaining locked work: S3B implementation/live acceptance, S3C, R1C-R8,
  and old VS-T4 through VS-T8. S1, S2, S3A, R1A, and R1B are accepted as
  recorded above.

## Authoritative verification

After bootstrap, run `.\scripts\verify.ps1`. It runs the offline gate and
collects unavailable-state probes for `real_data` and `autocad_mechanical` as explicit
`SKIP` results with prerequisites removed. A real private-data or live AutoCAD
Mechanical gate that was not separately executed remains `NOT RUN`.

## Roadmap and governance gate — S3B accepted; future runtime locked (2026-08-06)

- S1 and S2 are accepted. S2C, actual read-only AutoCAD-native layout capture,
  is accepted at `365cb2df47cc3d0232a4b5df1901f55dbe46b22c` (PR #61,
  `origin/main`).
- S3A offline inspection evidence and extraction-plan contract is accepted.
  R1A SourceBundle offline contract and R1B manifest binding are accepted.
- S3B implementation is accepted through PR #65 and merge
  `a9968480258e01fda9d4dfbf01a27958b67747bc`.
- Issue #64 is completed.
- Runtime verification head: `9f5dc302643fdfae77cbda65dd6cdc0c8deccc59`.
- Record-only final head: `67c3496da313245fc9ceeee26814e099b32f2c87`.
- The accepted S3B boundary uses read-only exact-base Xref inspection and
  approved extraction into new disposable candidates only. Source Xrefs and
  accepted DWGs remain immutable; allowed local transforms are translation,
  rotation, and positive uniform scale only.
- Fresh server-owned live preflight remains mandatory immediately before
  mutation, and extraction evidence retains source handle, layer, block,
  source revision, source hash, and `REUSED_FROM_BASE_CAD` provenance.
- AutoCAD Mechanical S3B live acceptance: **NOT RUN**.
- Hosted AutoCAD .NET: **NOT RUN**.
- No private drawing/source-data acceptance is promoted.
- S3C, R1C SourceBundle/source-fusion, registry, revision, repair, verdict, publication, and OCR remain **locked**.
- No next runtime milestone is selected by this rebaseline.

## Visual Supervisor VS-T0 contract-only slice (2026-08-04)

- State: **Partially verified; contract-only slice complete**.
- Implementation head SHA: `0a8c9830ee33967a11b774584383caea9d1fde33`.
- Scope is limited to pure-Python validators, closed JSON schemas, fixtures,
  and policy helpers for run manifests, dimensions, geometry comparison,
  independent visual review, repair plans, region verification, and
  run-scoped authorization.
- Contract inventory: 7 validators, 7 schemas, and 7 synthetic examples.
- Focused VS-T0 suite: **55 passed**. Authoritative `scripts/verify.ps1`
  passed on the implementation head; .NET was 76/76, dotnet IPC was
  38/0/0/0, and offline JUnit was 646/0/0/0.
- `real_data: NOT RUN`; `autocad_mechanical: NOT RUN`; `OpenAI API: NOT RUN`.
- No visual model review, image processing/comparator runtime, AutoCAD
  evidence operation, repair loop, Codex bridge runtime, or publication
  mutation is implemented in VS-T0.

## M2 Drawing Initialization Gate

- State: **Executing**. The approved M0-M8 rollout merged at `1969dc9`; the
  complete design is `docs/superpowers/specs/2026-08-02-cad-agent-complete-design.md`
  and the execution record is
  `docs/superpowers/plans/2026-08-02-m2-drawing-initialization-gate.md`.
- T2 Drawing Setup contracts and validation merged at `2b7a756`. Full M2 is
  still executing and has not produced `SETUP_VERIFIED` acceptance.
- Hosted evidence does not promote AutoCAD/.NET/private gates to `PASS`.
  For the current M2 candidate, the required private-data gate is `NOT RUN`;
  the unavailable-state `real_data` probe is `SKIP`; and the AutoCAD/.NET live
  gate is `NOT RUN`. No hosted or contract-only result is a substitute for
  operator-controlled AutoCAD Mechanical evidence.

## M2 Mechanical benchmark

- State: **Representative live acceptance PASS**.
  Four comparable live epochs pass across two genuinely distinct observed
  AutoCAD runtime identities. The approved design is
  `docs/superpowers/specs/2026-08-30-m2-mechanical-benchmark-design.md` and
  the execution record is
  `docs/superpowers/plans/2026-08-30-m2-mechanical-benchmark.md`.
- Draft PR `#309` remains the benchmark integration point at its exact
  GitHub-observed head `738dac0b11231a71f91376ebb5ef22b6c709461d`. The
  bounded C# health-owner successor is branch `codex/m2-plugin-identity`,
  based on that head. The final live implementation/harness evidence ran at
  `5c556b352f401bc084d4ee3f162c77d5df239378`; this acceptance-record update
  is committed at `38c640e4402dfc7868c67197b6d9a5bd4c0baa39`. Fresh
  `origin/main` remains `ffde4673be48f85a7fd4c0a10b9b35000c710e16`.
- Implemented scope: the closed `m2-mechanical-benchmark-record-1.0` oracle,
  cross-process deterministic staged-DXF fixture normalization with
  class-order semantic-invariance guards and post-normalization review,
  opt-in
  read-only Mechanical harness, and fail-closed runtime/implementation/PR/
  harness/plugin identity, transport, semantic wrong-target and stale-probe,
  failure-context, and cleanup accounting. No new transport, database,
  telemetry, or MECH-1 façade was added.
- Focused M2 verification before the final harness-only repairs passed `136`
  Python tests; the full C# suite passed `198`; Ruff and `git diff --check`
  passed. The final successor adds only the existing Python/FileIPC harness
  owner repairs described below; the canonical offline verifier is rerun
  separately before release integration.
- Authoritative full verifier on successor head `e8a42a5` exited `0`: C#
  `198` tests passed; offline JUnit `tests=3089, failures=0, errors=0,
  skipped=0`; dotnet IPC JUnit `tests=117, failures=0, errors=0, skipped=0`;
  real-data `2 skipped`; AutoCAD unavailable-state `14 skipped`; generic and
  M2 live markers **NOT RUN**; causal RED checks for fixture
  reproducibility, loaded identity, and semantic wrong-target refusal were
  accepted.
- Canonical offline verifier `scripts/verify.ps1 -SkipAutoCADDotNet` on
  successor head `78e06e5` exited `0`: offline JUnit `tests=3090`, dotnet IPC
  JUnit `tests=117`, with no failures/errors; the previously verified C# owner
  is unchanged. The final fixture proof includes no proxy/class-indexed entity
  invariant and equality of headless semantic review before/after
  normalization.
- A historical exact full-gate attempt at
  `4ee5e879214531b3d52c82a989de53e5541fbfd2` stopped in the .NET build with
  `MSB3027/MSB3021` because the Release plugin DLL was locked by AutoCAD PID
  `27168`; no process was launched or stopped to work around the lock.
- Current persisted record `C:\temp\cad-agent-m2-record.json` is SHA-256
  `360dd99c9ca88d9f09ef27af942cf2d52f545b7e6a4d58c888ae5d359d2c3ee0`.
  It contains four failed non-comparable epochs, aggregate `0/0`, status
  `BASELINE_ONLY`; after the modal was dismissed with Load Once, the current
  clean-head harness recorded a health/tool failure because the active plugin
  still omits the binary identity fields. That epoch also proved
  `closed_without_save`, source/staged unchanged, and release verified. Its
  sidecar is
  `C:\temp\cad-agent-m2-record.measurements.json`, SHA-256
  `b0e5d8e94bdc4b44d8f3acc58c3d873bb971400a2318b8944855d401d0eb301a`, with
  `0` measurements and `0` entity queries. The record is append-only evidence
  and is not promoted to acceptance.
- After the final artifact was loaded into the fresh runtime PID/HWND
  `27812/10881220`, the append-only
  `C:\temp\cad-agent-m2-record-r2.json` contains twelve total epochs, of
  which four are successful comparable epochs. The current record SHA-256 is
  `bbbdc33756b735e32acd7206d02a43f903f5ae944b72917d704260a096044c70`;
  its aggregate is `comparable=4`, `successful=4`, `success_rate=1.0`,
  `representative=true`, `status=REPRESENTATIVE`. The successful epochs
  observe the two distinct identities `acad-pid-1720-hwnd-1378378` and
  `acad-pid-27812-hwnd-10881220`; earlier non-comparable epochs remain
  recorded and are not backfilled. The successful epochs prove live geometry
  `3/3`, component `1/1`, dimension `1/1`, positive stale/wrong-target
  refusals, complete transport accounting, unchanged source/staged/candidate
  hashes, and close-without-save cleanup. No process control or blind retry
  was used.
- The current live harness binds runtime identity to the observed `acad.exe`
  PID/HWND, exact clean implementation and harness heads, and the exact
  Release DLL hash. The successor C# health owner now reports the executing
  assembly path and lowercase SHA-256, and the harness compares that observed
  value with the exact isolated Release artifact. Focused C# verification
  passed `198` tests; the final isolated x64 Release artifact is
  `C:\temp\cad-agent-m2-plugin-identity\autocad_plugin\CadAgent.AutoCAD2027\bin\x64\Release\net10.0-windows\CadAgent.AutoCAD2027.dll`
  with SHA-256
  `f7d3467a57ccb186b78d515ffe737afba08d3d3c691e0518e020a16ddfcbf40c`.
  The normal main-worktree Release DLL stayed locked/unchanged by AutoCAD;
  no process-control workaround was used. The DIMENSION read owner now uses
  DXF group 13/14 endpoint distance when AutoCAD reports the generated
  dimension's group 42 sentinel `-1.0`; the live evidence proves the fallback
  returns the expected 100 mm without COM write access. The harness also resets
  the disposable candidate after the wrong-target close and waits for the MDI
  transition to settle, preserving DBMOD/read-only evidence.
- Explicit gates: benchmark `autocad_mechanical` representative live
  acceptance is **PASS** with four successful comparable epochs across two
  observed runtime identities, exact loaded-plugin SHA attestation, semantic
  geometry/dimension, transport, stale/wrong-target, identity, and cleanup
  evidence. Benchmark `real_data` is **NOT RUN**; no repair or save attempts
  were made.
- MECH-1A bounded, provenance-bound read/query is now **ACCEPTED** through
  PR #371. This does not justify a second reader, whole-drawing scan, or
  unbounded sidecar; broader discovery remains deferred pending a measured
  product gap.

The exact future operator packet is tracked at
`docs/superpowers/plans/2026-08-30-m2-live-packet.md`. The packet records the
exact artifact, observed runtime identities, and final oracle. No remaining
Human-only action is required for M2 acceptance.

## M3 disposable LINE acceptance — contract-only boundary

- State: **Contract-only composition PASS; live AutoCAD M3 NOT RUN**.
  This is one bounded acceptance epoch over existing R4/R5/R6 owners, not M3
  milestone closure and not production drawing mutation.
- Implementation head: `9fd370120a1cd88f5b94955500d3fa38b8d3123f` on
  `codex/m3-disposable-acceptance`; plan:
  `docs/superpowers/plans/2026-08-30-m3-disposable-line-acceptance.md`.
- Contract-only epoch evidence: one v1.1 `ROOT_PRE_REPAIR` candidate produced
  an owner-validated R5 `FAIL`, one `REPAIR_DXF_PRIMITIVE` `LINE` operation was
  planned and authorized once, the existing `DotNetIPCClient` disposable
  workspace closed with `save_changes=false` and `zero_survivors`, and a new
  v1.1 `POST_REPAIR` candidate received an independently bound R5 `PASS`.
  The executor observed exactly one erase and one LINE create; replay and
  stale/rebound R5 paths were refused before a second mutation.
- Integrity/evidence: source, base, and accepted sentinel files remained
  byte-identical; candidate pre/post hashes and DARA/R3 correspondence were
  refreshed. Human-intervention events were empty because this was explicitly
  `CONTRACT_ONLY`; no AutoCAD process, `BVTL.dwg`, NETLOAD, save, or live visual
  provider was used.
- Causal owner repair: R6 now derives a canonical latest-mutation identity
  only for an owner-validated `candidate-revision-1.1` `ROOT_PRE_REPAIR` record
  whose closed mutation evidence has no legacy latest-mutation field. Legacy
  candidates retain the explicit field requirement; no second identity or
  repair subsystem was added.
- Verification on the exact head: focused M3/R4/R5/R6/R7 suite `300 passed`;
  Ruff passed; `scripts/verify.ps1 -SkipAutoCADDotNet` exited `0` in a clean
  worktree with offline JUnit `tests=3098, failures=0, errors=0, skipped=0`
  and dotnet IPC JUnit `tests=117, failures=0, errors=0, skipped=0`.
  The real-data unavailable probe recorded `2 skipped`, the AutoCAD unavailable
  probe recorded `14 skipped`, and the existing intentional causal RED gate
  failed as expected and was accepted by the verifier.
- Remaining M3 boundary: one real disposable candidate-only LINE epoch with a
  genuinely observed current R5 `FAIL`, live R6 mutation, cleanup, refreshed
  R4 lineage, and a fresh live R5 `PASS`. The current R8-D driver remains
  acceptance-only/read-only, so no live M3 PASS is claimed. The bounded
  MECH-1A read/query contract is accepted, while broader Mechanical
  introspection remains deferred.
- Live follow-up packet: `docs/superpowers/plans/2026-08-30-m3-live-packet.md`.
  It freezes the current main/plugin artifact identity, the existing
  NETLOAD/APPLOAD prerequisite, transport variables, owner sequence, safety
  invariants, and the exact reason no live command is published yet: the
  merged main branch had no M3 live composition test or canonical live record
  writer. The bounded RED-first implementation is now on candidate head
  `910643227299c36ed96c846b6edaf2b2eb4320e9` in
  `codex/m3-live-driver`; it remains offline/provider-callback only until
  hosted review is complete and is not a live acceptance result.

## M3 provider-backed live seam — offline boundary

- State: **Offline contract PASS; provider-backed live acceptance NOT RUN**.
  `R5_MODE=contract-only` remains unchanged and cannot create a live PASS.
- Candidate implementation: `cad_agent/m3_live_record.py` is the pure,
  closed-key canonical record oracle; `mcp_integration_lib/m3_live_harness.py`
  is the opt-in fixed-order callback composition seam. It performs no
  NETLOAD, UI automation, process control, or AutoCAD mutation.
- Fail-closed bindings require observed PID/HWND/document identity, current
  main and exact loaded-plugin SHA-256 equality, provider-backed pre-repair
  R5 `FAIL`, one consumed candidate/R5/operation-bound authorization, exactly
  one semantic R6 mutation, a distinct post-repair candidate, fresh provider
  R5 `PASS`, reconciled FileIPC/.NET/Task6/R6 transport counts, protected-file
  integrity, captured Human-intervention events, and observed zero-survivor
  cleanup. Caller labels, stale/rebound evidence, contract-only results,
  `SKIP`/`NOT_RUN`, retries, and ambiguous outcomes fail closed.
- Verification on candidate head: focused new contract suite `13 passed`,
  nearest M3/R4/R5/R6/R7 regression `225 passed`, Ruff and `git diff --check`
  passed. The canonical offline verifier recorded JUnit
  `tests=3111, failures=0, errors=0, skipped=0`, dotnet IPC
  `tests=117, failures=0, errors=0, skipped=0`, accepted causal RED `1`,
  real-data `2 skipped`, and AutoCAD `14 skipped`.
- Remaining boundary: hosted verification of this bounded seam, then a
  genuine provider-backed disposable AutoCAD epoch with fresh runtime,
  candidate, R5, repair, transport, integrity, and cleanup evidence. No live
  command or Human action is requested while the mode remains contract-only.

## M3 live oracle hardening — red-team correction

- Advisory `#301` comment `5468292161` identified a critical false-PASS risk
  after the seam was merged: reconciled transport failures/retries, reduced
  caller-made R5/R6 mappings, missing repair-executor cross-binding, and an
  unnecessarily non-empty Human-event requirement.
- Candidate hardening is commit
  `4d15a6e7830961f68200b7098a8a15c802e829ea` on
  `codex/m3-oracle-hardening`, based on main
  `ad1ac402b83b88780c7392e36f9f609fea5650b9`. It remains offline and does not
  perform provider calls, NETLOAD, UI automation, process control, or AutoCAD
  mutation.
- `cad_agent/m3_live_record.py` now validates the exact current-main
  `validate_visual_verdict_result` and `validate_approved_repair_result`
  payloads, binds their sealed identities to the reduced record, rejects any
  transport failure/retry, cross-binds `repair_executor` attempts to the one
  R6 attempt, and accepts `human_intervention={captured: true, events: []}`.
- RED/GREEN evidence on the candidate: focused hardening suite `18 passed`;
  nearest M3/R4/R5/R6/R7 regression `230 passed`; Ruff and
  `git diff --check` passed. Canonical verifier on the clean exact commit
  recorded offline JUnit `tests=3116, failures=0, errors=0, skipped=0`,
  dotnet IPC `117/0/0/0`, causal RED `1 accepted`, real-data `2 skipped`,
  AutoCAD `14 skipped`, and exit `0`. `LIVE_REPAIR_ACCEPTANCE=NOT_RUN`
  remains true.
- The critical advisory is actionable, not stale; merge/live decisions remain
  blocked on this exact-head hardening candidate until hosted checks pass.

## M3 Task6 provider accounting correction — follow-up

- Advisory `#301` critical source `#311` comment `5468458694` identified a
  remaining contradiction: the record requires distinct canonical pre/post
  Task6 turns while `transport.task6_provider` could claim only one attempt.
- Candidate commit `8b4c5acfb48d791d11aa28fc42bf7ad5a0b8736d` on
  `codex/m3-task6-accounting`, based on main
  `14ad95bd038f23c4d6e22808762b3a6a7ea49fe3`. The bounded validator now
  requires `task6_provider` attempts `2`, successes `2`, failures `0`, retries
  `0`, and exact ordered `turn_ids=[pre_r5.turn_id, post_r5.turn_id]`.
  Attempts `1`, `>2`, or turn identity drift fail closed; no other transport
  cardinality is generalized.
- Verification: focused Task6/M3 suite `21 passed`; nearest R5/R6/M3
  regression `214 passed`; docs contract `34 passed`; Ruff and
  `git diff --check` passed. Canonical verifier on the clean exact commit
  exited `0` with offline JUnit `tests=3119, failures=0, errors=0, skipped=0`,
  dotnet IPC `117/0/0/0`, causal RED `1 accepted`, real-data `2 skipped`, and
  AutoCAD `14 skipped`. Provider/live AutoCAD acceptance remains `NOT_RUN`
  and `R5_MODE=contract-only` remains unchanged.

## Personal Lean Pilot — Gate A Setup Lite

- State: **Partially verified; Gate A remains open**. The personal-project
  rebaseline is approved in
  `docs/superpowers/specs/2026-08-03-personal-lean-pilot-rebaseline-design.md`;
  its executable Gate A plan is
  `docs/superpowers/plans/2026-08-03-personal-lean-pilot-gate-a-setup-lite.md`.
- Offline implementation candidate: `579732a511e6775ed0b749a28f6627c7b92dba89`
  on `codex/personal-lean-pilot-rebaseline`. It includes legacy
  `DRAFT_REFERENCE` classification, the read-only Drawing Setup snapshot and
  IPC operation, SHA-bound audit/verify CLI commands, deterministic blockers,
  stale-evidence refusal, and the opt-in one-drawing live gate.
- Focused unavailable-state run: the Drawing Setup, IPC, live-harness,
  contract, and CLI suites reported `114 passed, 2 skipped, 18 subtests
  passed`. The personal live test skipped because
  `CAD_AGENT_LEAN_DISPOSABLE_DWG`, `CAD_AGENT_AUTOCAD_HWND`, and
  `CAD_AGENT_DOTNET_IPC_DIR` were absent. This skip is not live acceptance.
- Authoritative verifier on the implementation candidate: `scripts/verify.ps1
  -SkipAutoCADDotNet` exited `0`; dotnet_ipc JUnit was `38/0/0/0`, offline
  JUnit was `547/0/0/0`, the `real_data` unavailable-state probe was `2/2`
  skipped, and the `autocad_mechanical` unavailable-state probe was `8/8`
  skipped. Python was 3.11.9 and the required Tesseract version was present.
  The AutoCAD .NET build/test gate is **NOT RUN** because `dotnet` is absent;
  the AutoCAD live marker is also **NOT RUN**.
- External acceptance prerequisites checked on 2026-08-03 were all absent:
  owner-approved DWT, disposable DWG, AutoCAD HWND, plugin path, Drawing
  Definition, and .NET IPC directory. Therefore the real three-command flow
  and profile gate are **NOT RUN**. No personal profile metadata or live review
  record was created, because approved values and a real run do not exist.
- Acceptance consequence: no owner-approved disposable drawing has produced
  hash-stable, DBMOD-stable `SETUP_VERIFIED` evidence. Gate A cannot be called
  complete, and the legacy image/PDF path remains `DRAFT_REFERENCE` rather
  than authoritative.

## Personal Lean Pilot — Gate B offline dimension candidate

- State: **Partially verified; Gate A remains open and Gate B acceptance is
  NOT RUN**. The approved offline continuation is recorded in
  `docs/superpowers/specs/2026-08-03-personal-lean-pilot-offline-continuation-design.md`
  and its implementation plan is
  `docs/superpowers/plans/2026-08-03-personal-lean-pilot-gate-b-dimension-offline.md`.
  The offline implementation candidate is
  `88bdb1c` on
  `codex/personal-lean-pilot-rebaseline`.
- Implemented scope: strict dimension plan/evidence contracts; approved
  driving lengths and explicit datum anchoring at the existing SolveSpace
  boundary; native editable DXF `DIMENSION` generation and read-back;
  hash/provenance/Setup refusal; immutable IR byte snapshots; post-review and
  post-publish DXF hash binding; a non-overwriting temporary-output publish;
  rogue-geometry refusal; and one non-overwriting private-output CLI.
  Successful offline evidence still fixes `acceptance=NOT_RUN`.
- Focused Gate B offline run on 2026-08-03: **155 passed** with no failure.
  It covered contracts, orchestration, CLI, Drawing Setup, constraint solving,
  native DXF building, and headless review, including mutation and
  non-overwrite regressions.
- Authoritative verifier on the candidate:
  `scripts/verify.ps1 -SkipAutoCADDotNet` exited `0`; dotnet_ipc JUnit was
  `38/0/0/0`, offline JUnit was `603/0/0/0`, the `real_data`
  unavailable-state probe was `2/2` skipped, and the `autocad_mechanical`
  unavailable-state probe was `8/8` skipped. Python was 3.11.9, Ruff passed,
  and the required Tesseract version was present.
- Required gates not executed: the owner-approved compatible geometry export
  is absent, so the private `real_data` constraint benchmark is **NOT RUN**;
  Gate B private acceptance is **NOT RUN**; the AutoCAD .NET gate is **NOT
  RUN**; and the AutoCAD Mechanical 2027 live gate is **NOT RUN** because no
  qualifying session/prerequisites exist on this machine. Unavailable-state
  `SKIP` results are not acceptance evidence.
- Sample custody: an owner-provided DWG was hash-copied to a non-overwriting
  custody location outside Git, and the source hash remained stable. Content
  inspection, conversion, open, save, and mutation were all **NOT RUN**.
- Acceptance consequence: the Gate A → Gate B → Gate C order is unchanged.
  No `PERSONAL_VERIFIED`, `SETUP_VERIFIED` live outcome, or release outcome is
  claimed by this offline candidate.

## AutoCAD .NET plugin — Option A / phần cũ 1

This subsection records the completed Windows-only managed .NET slice. The
read-only Mechanical BOM extension is recorded separately below.

- Integrated into `main` at `bb1c6e9`; latest synchronized head:
  `f69d6a0` on `main` and `origin/main`.
- State: **Verified for the managed disposable smoke scope**; the repository's
  legacy-LISP aggregate marker remains a separate gate.
- Scope completed: Windows-only AutoCAD Mechanical 2027 managed plugin scaffold,
  versioned JSON/File IPC contracts, Mechanical no-op boundary, deterministic
  read-only review core, isolated Python dotnet_ipc backend, and the four
  command/dispatcher boundaries, plus the Windows `CADAGENT_DISPATCH` trigger,
  disposable .NET live-smoke harness, and one-shot `Application.Idle`
  disposable-close fix.
- C# evidence: restore/build/test passed on Release x64 with 51 passed, 0
  failed, 0 skipped; Autodesk reference-conflict warnings remain, and no
  Autodesk DLL was copied to plugin output.
- Python focused evidence: the .NET IPC focused suite passed 16 tests plus 18
  subtests; the opt-in live module passed 2 offline cleanup tests and skipped
  its one live test; the exact three-file Ruff gate passed.
- Authoritative verifier: **PASS** when run on commit `f69d6a0` with the
  explicit lock-matching Python 3.11 interpreter
  `D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe`:
  40/40 locked distributions, .NET 68/68, dotnet_ipc JUnit 36/0/0/0,
  offline JUnit 444/0/0/0, unavailable probes 2 + 7 skipped, and full Ruff
  passed. The verifier reports the current automated AutoCAD marker as
  `NOT RUN` when live prerequisites are absent; this does not invalidate the
  separately recorded managed disposable smoke.
- Direct AutoCAD .NET smoke: **PASS** on a fresh disposable DXF in an isolated
  AutoCAD Mechanical 2027 process. Health and read-only review succeeded for
  handle `2F`; `close_disposable` returned
  `closed_without_saving=true`; after an 8-second independent postcondition
  check AutoCAD was back on `[Start]` and no longer had the DXF document open.
  The DXF remained on disk and was not saved or mutated.
- Automated AutoCAD live marker: **FAIL** when attempted with the legacy LISP
  dispatcher (`8 failed, 5 passed, 423 deselected`); the legacy close path
  reports `Automation Error. Drawing is busy`. The focused .NET live test
  reported `1 passed, 3 deselected`; this is retained as historical evidence for
  the legacy-LISP bootstrap failure and is separate from the direct managed
  smoke above.
- Safety boundary: no production save, repair, or mutation was added or run;
  the existing dispatcher was not modified.
- Evidence records: `docs/reviews/2026-08-01-autocad-dotnet-live-review.md`,
  `docs/reviews/2026-08-01-autocad-dotnet-close-live-review.md`, and
  `docs/reviews/2026-08-01-autocad-dotnet-close-live-followup.md`.
- Completion: the reviewed candidate is integrated and pushed. No COM/ActiveX
  code was added to the plugin. No production drawing or `Drawing1.dwg` was
  opened, saved, or modified by this work.

## AutoCAD .NET plugin — Mechanical BOM 2A extension

- Candidate code head: `1ebb4db` on `integration/mechanical-bom-readonly`.
- Date: 2026-08-01.
- State: **Partially verified**. The managed read-only implementation, IPC
  contract, Python helper, unit tests, and authoritative offline verifier pass;
  the live AutoCAD Mechanical gate is explicitly **NOT RUN**.
- Scope: operation `mechanical_bom` reads direct ModelSpace `BlockReference`
  inserts and direct `AttributeReference` values, returns deterministic
  `component_count`/`components` payload data, and always reports
  `changed=false`. It does not traverse nested blocks, mutate/save drawings,
  create balloons, or use Mechanical SDK/COM/ActiveX/native APIs.
- Contract evidence: schema remains `1.0`; `parameters` is exactly `{}`;
  request/result examples and C#/Python validation are included under
  `contracts/autocad-ipc/`.
- C# evidence: Release x64 build/test passed with **68 passed, 0 failed, 0
  skipped**. Existing Autodesk `MSB3277` reference-conflict warnings remain;
  no Autodesk DLL was copied to plugin output.
- Python evidence: the .NET IPC suite passed **18 tests and 18 subtests**; the
  live-module suite passed **5 offline tests** with one expected live
  prerequisite skip. The fixture topology test passed; actual plugin nested
  exclusion remains live **NOT RUN**.
- Authoritative verifier: **PASS** on code head `1ebb4db` using the lock-matching Python
  3.11 interpreter `D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe`:
  C# **68/68**, dotnet IPC JUnit **36/0/0/0**, offline JUnit
  **444/0/0/0**, real-data unavailable probe **2 skipped**, AutoCAD Mechanical
  unavailable probe **7 skipped**, and Ruff/environment checks passed.
- AutoCAD live marker: **NOT RUN** because `CAD_AGENT_FILE_IPC`, a live
  AutoCAD HWND, and the declared File IPC bootstrap path were not available.
  No AutoCAD process or `Drawing1.dwg` was touched; no live PASS is inferred
  from build or unit tests.
- Evidence records: `docs/superpowers/specs/2026-08-01-mechanical-bom-readonly-design.md`,
  `docs/superpowers/plans/2026-08-01-mechanical-bom-readonly.md`, and the
  task reports/review packages in the plan's ignored SDD workspace.
- Integration: reviewed candidate merged into `main` and pushed as `1d9af6b`.
- Remaining live gate: a future operator-controlled disposable-DXF AutoCAD
  session may promote the live marker from `NOT RUN` to `PASS` or `SKIP`.

## AutoCAD .NET plugin — live BOM and legacy close continuation (2026-08-02)

- State: **Verified for the Windows disposable-DXF live scope**. This
  continuation promotes the Mechanical BOM live gate and removes the legacy
  no-save close race without changing the external dispatcher or .NET plugin.
- Managed BOM live gate: **PASS** on AutoCAD Mechanical 2027 using a fresh
  session and a DXF created below `C:\temp`. The opt-in test passed health,
  read-only review, `mechanical_bom` with two direct components (`COMP_EMPTY`
  and `COMP_FRAME`), unchanged `DBMOD`, unchanged source hash, request/result
  cleanup, and close-without-save (`1 passed, 5 deselected`).
- Legacy close live smoke: **PASS** on a separate disposable DXF. The client
  opened the drawing, read an entity, sent the queued no-save close command,
  and the SHA-256 remained unchanged. No `Drawing is busy` error occurred.
- Legacy aggregate context: the broader `test_file_ipc_e2e.py` run had
  `4 passed, 7 failed`; the remaining failures were existing round-trip handle
  assumptions after save/reopen (`Entity not found`), outside this close fix.
- Regression/unit evidence: the no-save path now emits exactly
  `(command-s "_.CLOSE" "_N")`; the save-enabled branch remains on its COM
  save path. Focused Python tests passed `49` tests plus `18` subtests, and
  Ruff passed.
- Authoritative verifier: **PASS** on the integrated candidate with .NET
  `68/68`, dotnet IPC JUnit `36/0/0/0`, offline JUnit `446/0/0/0`, lock and
  environment contracts passed. Autodesk reference-conflict warnings remain
  informational. No production/customer drawing was saved or modified; all
  live fixtures were disposable files below `C:\temp`.

## Pre-foundation baseline

| State | Date | Commit | Environment | Command | Result |
|---|---|---|---|---|---|
| Verified | 2026-07-22 | `908d016` | Windows, bundled Python 3.12.13, Tesseract 5.4.0.20240606 | `python -m pytest primitive_ir_lib/tests semantic_ir_lib/tests dxf_builder_lib/tests mcp_integration_lib/tests agent_lib/tests -q -p no:cacheprovider` | `255 passed, 11 skipped, 3 warnings` |

This baseline demonstrates that the existing core is worth preserving. It is
not the Python 3.11 foundation certificate because seven solver tests were among
the skips and the run used Python 3.12.

## Current module status

| Area | State | Evidence and limit |
|---|---|---|
| Primitive IR | Verified | Final Python 3.11 offline gate passed with zero skips; the approved private PDF, identified by SHA-256 below, completed Primitive IR for all nine pages. |
| Semantic IR | Verified | Final Python 3.11 offline gate passed with `python-solvespace` installed and zero offline skips; the approved private PDF completed all nine Semantic IR checkpoints. Assembly now uses raw detections for compound inference but persists only deterministic solver-ready constraints, reducing private page 1 from 538,983 raw relations to 3,693 retained constraints. |
| DXF build/review/repair | Verified | Final Python 3.11 offline DXF tests passed; production AutoCAD Mechanical mutation is outside this state. |
| Visual PDF-to-DXF fidelity | Verified for reviewable paper-layout and primary-linework scope | All nine delegated visual approvals were promoted into the fidelity manifest, and 9/9 promoted DXFs passed the dedicated read-only AutoCAD Mechanical review checkpoint. OCR/font, hatch, linetype, table placement, and dimension extensions now have review-only approval/reconstruction paths, but remain non-authoritative CAD content; model export remains excluded. |
| MCP/File IPC | Verified | Offline/fake IPC tests and the current six-test `autocad_mechanical` live gate passed on AutoCAD Mechanical 2027, including identical filenames under different directories and disposable-drawing cleanup. Active-document identity is full-path-bound. |
| Agent advice/audit | Verified | Agent execution is non-mutating by default. Application is a separate step bound to a saved report SHA-256 and exact source/IR hashes; approved constraint drops trigger a new solve before DXF generation. |
| Reproducible foundation | Verified | See the Foundation certificate and `docs/reviews/2026-07-22-reproducible-foundation.md`. |
| Thin image/PDF orchestration CLI | Verified | `cad_agent` run/resume and run-pdf/resume-pdf produce SHA-bound staged DXF and build evidence. Separate Mechanical review/repair commands enforce evidence, approval, backup, and second-review boundaries. |
| Production repair safety loop | Partially verified | Fake-MCP tests cover refusal, hash-verified backup, repair, second review, close-without-save rollback, and verified-backup reopen. A real staged-DXF review passed; no production drawing repair was requested or run. |
| M2 Drawing Initialization Gate | Executing | The image/PDF pipeline remains `DRAFT_REFERENCE`. A separate dimension-first path must provide hash-bound `SETUP_VERIFIED` evidence before an authoritative drawing path can create geometry; current M2 private/live gates are `NOT RUN` or `SKIP` as recorded above. |

## Known production gates

- Calibration may be auto-accepted only with at least two independent
  candidates and median relative error at most 3 percent. Current production
  callers must opt into consensus and retain human approval for unverified
  scale.
- Private drawing benchmarks remain outside Git and are addressed by SHA-256.
- AutoCAD Mechanical mutation requires backup, human approval, live review, repair, and
  a second review.

## Next slice

Maintain the SHA-bound private benchmark and run any future optimization against
it. Review-only fidelity extensions must be rerun against the private PDF before
they can be considered for visual acceptance. Production repair remains a
separate human-approved operation with backup and a second live review; it was
not requested or run here.

## Latest continuation evidence

- Head: `dae1f2c128c1b58eb84a400d15b53d9ada127916`.
- Offline gate: `scripts/verify.ps1` passed with `387 passed, 8 deselected`; the
  unavailable-state probes recorded `2` real-data skips and `6` AutoCAD skips.
- Live gate: with AutoCAD Mechanical 2027 and the local File IPC dispatcher,
  `python -m pytest -m autocad_mechanical -ra -p no:cacheprovider` passed
  `6 passed, 389 deselected` in `143.68s`. All smoke files were disposable
  DXFs under `C:\temp`; each live test now closes its temporary drawing without
  saving.
- Fidelity hatch: commits `50e49a1`, `75b5b80`, and `939cc29` add stable
  candidate IDs, hash-bound polygon approval, native review-only `HATCH`
  reconstruction, and the corresponding CLI/design evidence. No production
  AutoCAD mutation is authorized.

## Fidelity, stable identity, and P1 continuation (2026-08-02)

- Candidate implementation head: `aeaf950`. The specification and plan are
  recorded in `docs/superpowers/specs/2026-08-02-fidelity-legacy-p1-design.md`
  and `docs/superpowers/plans/2026-08-02-fidelity-legacy-p1.md`.
- Stable component identity: review and repair now use an exact `PART_ID`
  fallback when a saved/reopened INSERT handle changes. Ambiguous duplicate
  identities fail closed; the live E2E helper rebinds the current handle before
  inspection. This removes the old `Entity not found` assumption without
  weakening the mismatch gate.
- Advanced fidelity: text, table text, dimension, hatch, and linetype review
  sidecars are now exposed as hash-bound per-page entries in the review index
  and queue. Missing or invalid sidecars remain `not_run`/`invalid_artifact`,
  and the overall fidelity state remains `needs_review`; no production CAD
  mutation or model export is enabled by this change.
- P1 local image gate: **PASS** for the workstation-local page scan
  `bv (1)_p01.png`, SHA-256
  `95fb77b16c61cac7a3463e9fc29d0883fb34fbf5ad92d311e9ee6c658a736918`.
  The official real-image benchmark passed `1` test using Tesseract
  `5.4.0.20240606`/`eng`; it found the expected `2760`/`1525` OCR region and
  the overlapping Hough-line witness chain, with relative scale consistency
  error about `1.46%`. The source image and report remain outside Git.
- Focused evidence: DXF reviewer/repair suite `30 passed`; fidelity suite
  `41 passed`; line-merging/tick suite `26 passed`; Ruff and `git diff --check`
  passed.
- Authoritative verifier: **PASS** on `aeaf950` with the lock-matching Python
  3.11 interpreter: .NET `68/68`, dotnet IPC JUnit `36/0/0/0`, offline JUnit
  `450/0/0/0`, unavailable probes `2` and `7` skipped, environment/lock/Ruff
  checks passed. Autodesk reference-conflict warnings remain informational.
- AutoCAD live session probe: **NOT RUN for acceptance**. An attempt against a
  fresh AutoCAD Mechanical 2027 window with the declared dispatcher path gave
  `2 passed, 10 failed`; all failures timed out waiting for the dispatcher
  after the new session remained on `[Start]`. This is a session/bootstrap
  prerequisite failure, not evidence that offline tests are live PASS. No
  production drawing or `Drawing1.dwg` was opened, saved, or modified.
- Remaining gates: run the live component round-trip only after a fresh
  AutoCAD session has loaded and answered `mcp_dispatch.lsp`; advanced fidelity
  sidecars still require private-data review before visual acceptance; the
  production repair loop remains a separately human-approved operation with
  backup and second review.

## Fidelity P1 live round-trip continuation (2026-08-02)

- The live prerequisite was completed in a fresh AutoCAD Mechanical 2027
  session by loading the declared `mcp_dispatch.lsp` through a startup script.
  All live fixtures were disposable DXFs under `C:\\temp`; no production
  drawing or `Drawing1.dwg` was opened, saved, or modified.
- Live smoke: **PASS**, `1 passed`.
- Live legacy round-trip: **PASS**, `5 passed, 7 subtests passed` in
  `154.69s`. Coverage includes beam `PART_ID` tamper/save/reopen/repair,
  primitive repair, native dimension inspection, six component repairs, and
  same-name drawings in different directories.
- Determinism fixes: command-boundary `CLOSE` with an open-document
  postcondition, command-level `OPEN` fallback when AutoCAD is on the Start
  tab, and a unique expected-block fallback that replaces a tampered component
  instead of creating a duplicate. Ambiguous candidates still fail closed.
- The final live run was performed after the dispatcher was loaded and a
  transient AutoCAD Options modal was dismissed. The result is the acceptance
  evidence for this candidate; the earlier bootstrap-only attempt remains a
  historical failure record above.
- Authoritative verifier on the final implementation: **PASS**, .NET `68/68`,
  dotnet IPC JUnit `36/0/0/0`, offline JUnit `453/0/0/0`, unavailable probes
  `2` and `7` skipped, with lock/environment/Ruff checks passing. Because this
  verifier invocation intentionally did not attach to the interactive AutoCAD
  session, its separate live marker is `NOT RUN`; the direct live result above
  is the live acceptance evidence.
- Remaining limits are unchanged: advanced fidelity sidecars still require
  private-data review before visual acceptance, and production repair remains
  separately human-approved with backup and second review.

## First product milestone decision

- State: **Verified** for the reviewable-DXF scope defined in
  `docs/PROJECT.md`.
- Date: `2026-07-28`.
- The approved nine-page private PDF completed Primitive IR, Semantic IR,
  optional audited Agent advice, staged/reconstructed DXF, headless structural
  checks, delegated visual promotion, and nine SHA-bound read-only AutoCAD
  Mechanical 2027 review checkpoints.
- The Agent path is advisory by default and has a separate explicit approval
  gate. No production drawing was mutated.
- Deferred work does not block the reviewable milestone: the user explicitly
  deferred the known font/OCR correction. Hatch, linetype, table placement,
  and true dimension semantics remain review observations rather than
  fabricated authoritative CAD entities.
- Production repair is an operational gate, not an automatic completion step:
  it still requires a named production DXF, matching evidence, verified backup,
  explicit repair confirmation, and a passing post-repair review.

## Thin vertical-slice CLI evidence

- State: **Verified**
- Date: `2026-07-22`
- Implementation Head SHA: `8410712f0c7c23f707acc1b251620712806be971`
- Design and plan: `docs/superpowers/specs/2026-07-22-vertical-slice-cli-design.md`; `docs/superpowers/plans/2026-07-22-vertical-slice-cli.md`
- Focused command: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_cli.py -q -p no:cacheprovider` → `3 passed`
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` → exit `0`
- Offline JUnit: `tests=295; failures=0; errors=0; skipped=0`
- `real_data`: unavailable-state probe `SKIP` (`tests=1; skipped=1`); approved private run `NOT RUN`
- `autocad_lt`: historical unavailable-state probe `SKIP` (`tests=4; skipped=4`); live session run `NOT RUN` at this pre-target-change commit
- Historical limitation: this former image-only slice is superseded by the PDF vertical-slice evidence below.

## PDF vertical-slice orchestration evidence

- State: **Verified**
- Date: `2026-07-22`
- Implementation Head SHA: `1669f25e88847b47284219c92769801a5bc81768`
- Design and plan: `docs/superpowers/specs/2026-07-22-pdf-vertical-slice-design.md`; `docs/superpowers/plans/2026-07-22-pdf-vertical-slice.md`
- Behavior: `run-pdf` and `resume-pdf` SHA-bind a PDF, its explicit scale approval, the package render manifest, and per-page rendered PNG, Primitive IR, Semantic IR, staged DXF, and build-evidence checkpoints. Resume reuses intact pages, rebuilds only invalid dependent stages, and rejects a changed PDF before reuse.
- Focused command: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_pdf.py tests\test_cad_agent_cli.py tests\test_cad_agent_live.py -q -p no:cacheprovider` -> `12 passed`; coverage includes multi-page output, byte-identical resume, changed source refusal, affected-page rebuild, missing Primitive IR recovery, and CLI run/resume.
- Live staged review: a newly generated two-page PDF under `C:\temp\cad-agent-pdf-live-20260722` completed through `run-pdf`; `mechanical-review` opened only page 1's staged DXF through the AutoCAD Mechanical 2027 File IPC dispatcher and reported `passed=true`, `structural_checked=1`, `geometry_checked=1`, with no mismatches or warnings. No repair or production save was requested.
- Current live marker gate: with AutoCAD Mechanical HWND `393650` and the loaded dispatcher, `& '.\.venv-py311\Scripts\python.exe' -m pytest -m autocad_mechanical -ra -p no:cacheprovider` -> `4 passed, 305 deselected` in `69.50s`; the smoke scope used only disposable DXFs under `C:\temp`.
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` -> exit `0`; offline JUnit `tests=304; failures=0; errors=0; skipped=0`; SHA-256 `d9f8d85ed0ae42b14d4db00639a51d329a438b11ee2878cb8428b576dbd0e0fe`.
- `real_data`: unavailable-state probe `SKIP` (`tests=1; skipped=1`), SHA-256 `9bef0b1195208264fc4b7e0f07c0ec898f659f9925b6caa983143659ebb107d5`; approved private run `NOT RUN`.
- `autocad_mechanical`: unavailable-state probe `SKIP` (`tests=4; skipped=4`), SHA-256 `ec6a9b12540c9188a76988880e3651f81c63c399d4da5c989002f2c9b4b801f4`.
- Remaining risk: no approved private PDF was run at this historical command; the later full private-PDF evidence is recorded below.

## Approved private PDF full-run evidence

- State: **Verified**
- Date: `2026-07-22`
- Approved input: private PDF SHA-256 `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`; it remains outside Git.
- Calibration: all nine title blocks state `1:40`; the approved 144-DPI conversion is `7.055555555556 mm/px`. OCR also records any detected scale label as a `needs_verification` candidate and never overrides the approved manual calibration.
- Checkpoints: all 9/9 rendered-page, Primitive IR, Semantic IR, staged-DXF, and SHA-bound build-evidence records completed under private staging. Every staged DXF passed the headless reviewer.
- Visual-fidelity correction: these checkpoints are analysis-pipeline evidence only. The page-wide model-scale transform, zero extracted text primitives, and semantic `INSERT` overlays mean they must not be read as faithful drawing-sheet reconstructions. The separate fidelity workflow below is the only current visual-comparison path.
- Dense-data optimization evidence: page 1 completed compound recognition with 1,170 primitives and 538,983 detected constraints. Page 5 reduced 109,399 raw constraints to 1,392 after pruning; its 478 relevant lines exceed the documented 1,000-coordinate solver capacity, so the DXF preserved calibrated primitive geometry through the explicit `too_many_unknowns` fallback instead of spending minutes in an unstable solve.
- Live staged review: the standard `cad_agent mechanical-review` command with `--timeout-s 60` reviewed page 5 through AutoCAD Mechanical 2027 and reported `passed=true`, `structural_checked=485`, `geometry_checked=485`, no mismatches, no warnings, and no degraded geometry check. It was read-only: no repair or save was requested.
- Final repository verification: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` passed on `8c24896` with `318 passed, 5 deselected`; the final timeout-option revision is covered by focused CLI/live tests and the same verifier run.

## Fidelity reconstruction CLI evidence

- State: **Partially verified**
- Date: `2026-07-22`
- Implementation Head SHA: `374e75fb15abe9fd33df74fe61a84c966946f488`
- Design and plan: `docs/superpowers/specs/2026-07-22-fidelity-reconstruction-cli-design.md`; `docs/superpowers/plans/2026-07-22-fidelity-reconstruction-cli.md`
- Behavior: the private `fidelity-pdf`, `fidelity-overlay`, `fidelity-region-proposal`, `fidelity-region-approve`, `fidelity-reconstruct`, and `fidelity-observe` commands bind source and artifact hashes, keep output outside Git, forbid Mechanical operations on fidelity DXFs, and preserve `needs_review` rather than claiming a visual pass.
- Private source evidence: all nine paper-coordinate baselines and overlays completed. Under the user's explicit 2026-07-22 approval, every page has one SHA-bound `sheet_content` layout-region approval, reconstruction candidate, and composed page DXF outside Git (page 5 uses revision 4). These are broad layout regions, not approved model-view geometry. Table-grid observations and bounded table-region OCR completed for 9/9 pages. After the user's explicit approval to accept OCR subject to later correction, all 419 ordinary OCR candidates were hash-approved and emitted as `TEXT` into fresh private DXFs; the original geometry layouts remain unchanged.
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` -> exit `0` on `ef7140d`; offline JUnit `tests=327; failures=0; errors=0; skipped=0`.
- `real_data`: private command evidence exists but the marker benchmark is **NOT RUN** for this workflow; `autocad_mechanical`: **NOT RUN** by design because fidelity artifacts are refused before live review/repair.
- Follow-on fidelity evidence: after the user's blanket approval for correctable OCR, 419 ordinary OCR candidates were emitted as Unicode `TEXT`. Bounded table-region OCR then supplied 81 additional table-text candidates (pages 2, 3, 5, 6, 8, and 9); dashed-line candidates and 14 dimension-value candidates were observed with provenance outside Git. These later candidates remain `needs_review`: linetypes are heuristic, table placement needs visual review, dimensions are observations only (no inferred `DIMENSION` entities), and hatch/model-view reconstruction are intentionally not fabricated.
- Latest source verification: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` passed on `99f9931`; offline JUnit `tests=328; failures=0; errors=0; skipped=0`. The private integrated PDF/DXF overlay set covers 9/9 pages and remains a diagnostic comparison, not a fidelity pass.
- Linetype reconstruction: `fidelity-linetype-reconstruct` was added on `1c8cbc8`. It clones an existing private layout DXF, applies `FIDELITY_DASHED` only to hash-bound observed horizontal patterns, and writes revisioned candidates with a report. The private nine-page revision changed 76, 88, 7, 60, 8, 14, 82, 16, and 67 LINE entities respectively; this remains a visual candidate, not an authoritative linetype mapping. The official verifier passed on that commit with `330 passed, 6 deselected`.
- Region-quality gate: the review-only reconstruction now compares an unfiltered and a short/near-duplicate-stroke filtered candidate on the approved crop before writing DXF. A private nine-page rerun under `C:\temp\cad-agent-fidelity-e48f3970-region-quality-r2` rejected the filtered profile on all pages because local F1 would decrease (baseline: 0.799, 0.817, 0.758, 0.738, 0.826, 0.875, 0.785, 0.709, 0.764; filtered: 0.787, 0.808, 0.751, 0.728, 0.821, 0.851, 0.781, 0.701, 0.757). The composed-page candidates therefore retain baseline geometry; their review-only F1 values are 0.506, 0.539, 0.369, 0.425, 0.345, 0.419, 0.380, 0.313, and 0.432. This is evidence that the heuristic was safely rejected, not a visual-fidelity pass.
- Hatch observation: `fidelity-hatch-observe` now writes SHA-bound, review-only diagonal-stroke sidecars. Its nine-page private rerun found six candidates only on pages 3, 5, and 9 (peak segment counts 20, 5, and 10); it found none on the other pages. No DXF `HATCH` entity or production mutation is emitted, and every candidate remains `needs_review` pending explicit boundary approval.
- Remaining risk: all nine compositions remain `needs_review`, and broad layout approvals do not validate visual similarity. OCR text remains correctable and text placement/style needs review. Disciplined model-view reconstruction, true dimension semantics, verified linetypes/hatches, and table-cell placement still require visual review before they can be represented as authoritative CAD content.

## Delegated-review fidelity promotion

- State: **Verified** (reviewable paper-layout and primary-linework scope only)
- Date: `2026-07-28`
- Source: approved private PDF, SHA-256
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`.
- Private artifact identifier: source prefix `e48f3970`, final manifest SHA-256
  `e36814340cb8ec32b71cefec67f454de29619632be30283d3bf77311fe0fe90d`.
  The external root contains all nine rendered pages, structural round-trip
  passes, overlays, observations, approvals, composed DXFs, promotions, and
  Mechanical review reports.
- OCR evidence: all 419 new OCR candidates exactly match the candidate text and
  pixel boxes in the previously approved set. Nine fresh text-approval files
  were created. Fresh DXF text reconstruction was intentionally not run because
  the user deferred the known Vietnamese preview-font correction.
- Private-data command with `<private-pdf>` and `<private-fidelity-root>`
  environment values plus `CAD_AGENT_FIDELITY_REQUIRE_RECONSTRUCTION=1`:
  `python -m pytest tests\test_cad_agent_fidelity_real_data.py -ra -p
  no:cacheprovider` -> `1 passed`. The gate validates 9/9 promotion and
  Mechanical checkpoints.
- Live command: AutoCAD Mechanical 2027 session `acad.exe`, HWND `787740`,
  loaded File IPC dispatcher; `python -m pytest -m autocad_mechanical -ra -p
  no:cacheprovider` -> `5 passed, 355 deselected` in `82.78s`. All live DXFs
  were disposable.
- Authoritative offline command:
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1`
  -> exit `0`; offline JUnit `tests=353; failures=0; errors=0; skipped=0`.
- Delegated visual review: all nine `reconstruction_pages/page_XX/overlay.png`
  files were inspected on 2026-07-28. Red is source raster edge, cyan is
  reconstructed DXF edge, and green is overlap. The paper layout and primary
  vehicle/structure linework were accepted for review use on every page.
- Integrated promotion: all nine composed pages received a delegated visual
  approval record and transitioned through
  `approved_for_mechanical_review` to `mechanical_reviewed`. The dedicated
  command compared each promoted type/layer signature with AutoCAD and wrote
  nine SHA-bound reports. Every report records `save_performed=false` and
  `repair_performed=false`.
- Limit: this is not a production model or a claim of pixel-perfect fidelity.
  Text/font/OCR, hatch, linetype, table placement, and dimension semantics are
  outside the accepted primary-linework scope.

## Agent action approval evidence

- State: **Verified**
- Date: `2026-07-28`
- Hardened Head SHA: `4656e9f148bcd90c43c9eba672fdd5977f8cc307`.
- Design and plan:
  `docs/superpowers/specs/2026-07-28-agent-action-approval-design.md`;
  `docs/superpowers/plans/2026-07-28-agent-action-approval.md`.
- Safety behavior: the file runner and synthetic demo are advisory by default.
  Application is a second step requiring a saved report and SHA-256, literal
  `APPLY`, an approval reference, and exact source/Primitive/Semantic IR hashes.
  The audit records provenance/action hashes and the post-application solve
  state. Approved constraint drops are solved again before DXF generation.
- Advisory smoke: the real runner loaded the repository's 900x700 synthetic
  image and IR, produced 10 constraint-drop proposals, exited `0`, and recorded
  `application_requested=false` and `actions_applied=false` under
  `C:\temp\cad-agent-agent-gate-09c276c`.
- Final authoritative command is recorded in the release candidate section:
  353 offline tests, one private fidelity test, and five live AutoCAD
  Mechanical tests all passed.
- Boundary: this gate controls in-memory IR application only. It does not grant
  permission to repair or save a production AutoCAD drawing.

## Semantic constraint compaction evidence

- State: **Verified** on
  `4656e9f148bcd90c43c9eba672fdd5977f8cc307`.
- Date: `2026-07-28`.
- Design and plan:
  `docs/superpowers/specs/2026-07-28-semantic-constraint-compaction-design.md`;
  `docs/superpowers/plans/2026-07-28-semantic-constraint-compaction.md`.
- Behavior: assembly uses the complete detected set for compound inference and
  persists only `prune_constraints(...).kept` in Semantic IR.
- Focused result: compound/pruning tests -> `26 passed`; final authoritative
  offline run -> `353 passed, 7 deselected`; Ruff -> `PASS`.
- Approved private page 1: 1,170 primitives, 1,187 parts, 3,693 retained
  constraints, Semantic assembly `34.002s`. The earlier raw count was 538,983.
- Approved private page 5: 485 primitives, 495 parts, 1,392 retained
  constraints, Semantic assembly `5.758s`, matching the previously recorded
  pruning result.
- Final private-data and live AutoCAD Mechanical gates passed on the same
  candidate.

## File IPC active-document verification

- State: **Verified** on
  `4656e9f148bcd90c43c9eba672fdd5977f8cc307`.
- Date: `2026-07-28`.
- Release-gate observation: the initial four-test AutoCAD Mechanical run had
  one transient `block-get-attributes` timeout followed by one wrong-document
  `Entity not found`; four later component subcases passed.
- Root cause: raw-LISP document opening waited for a dispatcher ping and
  originally verified only the basename.
- Fix: `drawing_open()` verifies normalized `DWGPREFIX + DWGNAME`, retries one
  mismatch, and rejects identical basenames under another directory.
  `block_get_attributes()` retries one timeout because it is read-only. No
  mutating command is retried.
- Final live evidence: five tests passed in `82.78s`, including two disposable
  `same-name.dxf` files in different directories.
- Design and plan:
  `docs/superpowers/specs/2026-07-28-file-ipc-active-document-verification-design.md`;
  `docs/superpowers/plans/2026-07-28-file-ipc-active-document-verification.md`.

## Mechanical production review/repair evidence

- State: **Partially verified**
- Date: `2026-07-22`
- Implementation Head SHA: `ddf683431cabf4b4a12c3448aed0a20b7b54d429`
- Design and plan: `docs/superpowers/specs/2026-07-22-mechanical-production-repair-design.md`; `docs/superpowers/plans/2026-07-22-mechanical-production-repair.md`
- Safety behavior: `run` writes `build-evidence.json` bound to the staged DXF
  SHA-256. `mechanical-review` is read-only; `mechanical-repair` requires an
  approval reference, literal `--confirm-repair APPLY`, source/copy hash-verified
  DXF/evidence backups, and a passing post-repair live review before save. A
  failed review closes the modified drawing without save before reopening the
  verified backup.
- Focused tests: `tests/test_cad_agent_live.py` and `tests/test_cad_agent_cli.py` → `7 passed`; coverage includes missing approval refusal, backup creation, successful fake repair, and failed-second-review rollback.
- Live staged review: `cad_agent mechanical-review` on a disposable DXF under `C:\temp` through AutoCAD Mechanical 2027 → `passed=true`, `structural_checked=10`, `geometry_checked=10`, no mismatch or degraded geometry check.
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` → exit `0`; offline JUnit `tests=299; failures=0; errors=0; skipped=0`; SHA-256 `80140e4ca6c7089742a8282ad0e9cea083ce167c110b91f11cbe3f0d485e3569`
- `real_data`: unavailable-state probe `SKIP` (`tests=1; skipped=1`), SHA-256 `f6b25dd4aa7da9b5c12eaad290bc042061a53b54897fec50d176e9035f0aadb3`; approved private run `NOT RUN`
- `autocad_mechanical`: unavailable-state probe `SKIP` (`tests=4; skipped=4`), SHA-256 `69ba0f74887b47dfb2a09f4a4a670acdead32db67677e63f70b28084f7a402e5`
- Remaining risk: no customer/production drawing was repaired. A real repair remains gated on an approved input, backup verification, explicit operator approval, and a post-repair review.

## Historical File IPC evidence before the AutoCAD Mechanical target change

- State: **Partially verified**
- Date: `2026-07-22`
- Head SHA: `52b92885698827c36984f02e8461f4e18de6072c`
- Command: `CAD_AGENT_FILE_IPC=1`, AutoCAD HWND `393650`, and the locally loaded dispatcher; `& '.\.venv-py311\Scripts\python.exe' -m pytest -m autocad_lt -ra -p no:cacheprovider`
- Result: `4 passed, 296 deselected` in `69.52s`; the run covered active-document access, primitive live review/repair, beam INSERT attribute repair, and five remaining component INSERT repairs.
- Session: AutoCAD Mechanical 2027, process `acad.exe`, HWND `393650`.
- Safety: all smoke DXFs were newly created under `C:\temp`; no production drawing was saved or modified.
- Limit: the then-current marker was `autocad_lt`, so this evidence predates the AutoCAD Mechanical target contract and is retained as historical context only.

## AutoCAD Mechanical 2027 target evidence

- State: **Verified**
- Date: `2026-07-22`
- Implementation Head SHA: `bda0cf0ea094d67bddca65aa8f9df953a4f25078`
- Design and plan: `docs/superpowers/specs/2026-07-22-autocad-mechanical-2027-design.md`; `docs/superpowers/plans/2026-07-22-autocad-mechanical-2027.md`
- Live command: `CAD_AGENT_FILE_IPC=1`, AutoCAD Mechanical HWND `393650`, and the loaded dispatcher; `& '.\.venv-py311\Scripts\python.exe' -m pytest -m autocad_mechanical -ra -p no:cacheprovider` → `4 passed, 296 deselected` in `69.41s`
- Live scope: active-document access, primitive live review/repair, beam INSERT attribute repair, and five remaining component INSERT repairs; every smoke DXF was created under `C:\temp`.
- Session: AutoCAD Mechanical 2027, `acad.exe`, HWND `393650`.
- Authoritative command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` → exit `0`
- Offline JUnit: `tests=295; failures=0; errors=0; skipped=0`; SHA-256 `5d380796e1c5582ee3f1df48b9979853cda782f66ba3268fe8a46f5126b57298`
- `real_data`: unavailable-state probe `SKIP` (`tests=1; skipped=1`); SHA-256 `c2e3927cd97a46b1c45658ec263e5d221cb169a0be3de26a99a5651c9e42d289`; approved private run `NOT RUN`
- `autocad_mechanical`: unavailable-state probe `SKIP` (`tests=4; skipped=4`); SHA-256 `039a06a9c3c6a0a4aa7c6283fae44cd4c44caa04c7809f5bc7ffdbe20146be74`
- Remaining risk: production drawing mutation remains prohibited without a verified backup, explicit human approval, live review, repair, and a second review.

## Foundation certificate

- State: **Verified**
- Date: `2026-07-22`
- Reviewed implementation Head SHA: `a96a31df6a735d103c29548855fa8a170e535c18`
- Command: `.\scripts\verify.ps1`
- Exit code: `0`
- Python: `3.11.9`
- Tesseract executable: `C:\Program Files\Tesseract-OCR\tesseract.exe (tesseract v5.4.0.20240606)`
- Dependencies: `numpy=2.4.6; opencv-python=5.0.0.93; pytesseract=0.3.13; Pillow=12.3.0; pypdf=6.14.2; PyMuPDF=1.28.0; ezdxf=1.4.4; anthropic=0.117.1; python-solvespace=3.0.8; pytest=9.1.1; ruff=0.15.22`
- Offline JUnit: `tests=292; failures=0; errors=0; skipped=0`; SHA-256 `c35bde5ee7f22eeb7489baa7bcabdf3a16b6c89555a079482e0d3d61a41e742c`
- `real_data`: `SKIP` unavailable-state probe; `tests=1; skipped=1`; SHA-256 `b63e0effc175a3854ea6b217d68f894a3fcc0bc7299a5616f6f3d452c2028986`
- `autocad_lt`: `SKIP` unavailable-state probe; `tests=4; skipped=4`; SHA-256 `6818b5d401859ff92ee0b3b3f40891ac320018bdf386aa29bc8fb2cb0aa1bd0c`
- Unexpected warnings: `0`; scoped intentional ROI warning policy remains documented in `docs/QUALITY.md`
- Ruff: `PASS`
- Lock/environment, Git whitespace, and repository content-hash side-effect checks: `PASS`
- Verification transcript SHA-256: `486ec0fe693a209a866e96673a34e249b4496ec3906e35d101e44f538c93de3a`
- Independent review: `docs/reviews/2026-07-22-reproducible-foundation.md`; three final-head reports; unresolved P0/P1 `0`
- Remaining risks: at this historical foundation head, the approved private `real_data`
  gate and then-current live `autocad_lt` gate were not run, and the Agent
  entry points still auto-applied reports. Later sections supersede those
  specific limits with private-data, AutoCAD Mechanical 2027, and Agent
  approval-gate evidence.
