# Demand-load document-ready probe characterization — iteration 93

## Authority and scope

Fresh SOL review of iteration 92 required one offline characterization only.
The characterization must compare the existing startup/document-ready
predicate and its observable inputs with the iteration-76/90 successful
epochs and iteration-92 failed epoch. No AutoCAD launch, live retry, code
change, candidate activation, FileIPC operation, setup/readback, or
source/candidate/DXF mutation was performed.

## Identity check: canonical main versus executor branch

Fresh Git inspection found that canonical `origin/main` at
`e8fc0092ee46750e50de0ea408fd91811cae10c2` contains the legacy
`FileIPCLiveMCPClient`, but does not contain the startup owner or its new
observability symbols:

- `WindowsAutoCADStartTabSession`;
- `make_windows_start_tab_document_ready_probe`;
- `BootstrapTimingRecorder`;
- `_make_windows_main_window_title_reader`.

Those symbols exist on the executor branch at the reviewed iteration-92
head. Consequently, the live iteration-76/90/92 evidence exercised the
executor-branch startup owner, not an owner present in canonical `main`. No
canonical-main document-ready predicate can be claimed from the absent
symbols.

## Existing branch predicate and timeout

On the executor branch, the startup owner uses the following observable
chain:

1. `_find_windows_main_window_for_pid` enumerates visible top-level windows
   for the owned PID and accepts a window only when it has a non-empty title;
   exactly one candidate becomes the owned HWND.
2. `make_windows_start_tab_no_document_probe` reads that HWND's title using
   `GetWindowTextLengthW` and `GetWindowTextW`, then returns true only when
   the normalized title ends with `[start]`.
3. `make_windows_start_tab_document_ready_probe` uses the same title reader
   and returns true only when the title is non-empty and does not end with
   `[start]`.
4. `_wait_for_document_ready` polls that Boolean until
   `time.monotonic() + timeout_s`; all probe exceptions are caught and
   collapsed to false, and the loop sleeps for `poll_interval_s`.

Thus the predicate has no independent AutoCAD document identity input. Its
only readiness input is one sampled main-window title, and a missing/failed
title read is indistinguishable from the Start-tab title at the Boolean
boundary.

## Evidence comparison

- Iteration 76: the same `WindowsAutoCADStartTabSession` owner, verified DWT,
  `/nologo /t <DWT> /b <script>`, and `CADAGENT_DISPATCH` script recorded
  `document_ready_observed=true`.
- Iteration 90: the same owner and startup pattern recorded
  `document_ready_observed=true` before the later FileIPC dispatcher timeout.
- Iteration 92: an owned HWND was found under the same startup pattern, but
  `document_ready_observed=false` until the bounded timeout.

The three private proofs do not record the raw title samples, title API
length/return values, poll count, or `BootstrapTimingRecorder` events.
Therefore the current evidence cannot distinguish a persistent Start-tab
title from a title-reader false negative/race. No narrower cause is inferred.

## Smallest future read-only oracle

In one future epoch, after the existing owner records the HWND and before
cleanup, reuse the existing `_make_windows_main_window_title_reader(hwnd)` on
that exact owned HWND and record the raw normalized title category at the
readiness timeout, together with the existing `BootstrapTimingRecorder`
events. Interpret only as follows:

- non-empty title ending `[start]` throughout the final readiness sample:
  `AUTOCAD_WINDOW_PRESENT_BUT_DOCUMENT_NOT_READY` under the current owner
  contract;
- non-empty title not ending `[start]` while the document-ready Boolean was
  false at the same observation boundary:
  `DOCUMENT_READY_PROBE_FALSE_NEGATIVE_OR_RACE`;
- missing/empty title: `DOCUMENT_READY_UNRESOLVED`, because the existing
  title API has not supplied enough evidence to classify readiness.

The timing recorder's `start_window_observed` and
`document_ready_transition` events are supporting observables only; absence
of the transition event is not an independent document-readiness proof.
This is the cheapest reuse-only discriminator and requires
`MODIFY NONE / CREATE NONE`.

## Result

`STAGE_LOCALIZATION=PASS`

`CANONICAL_MAIN_STARTUP_OWNER=ABSENT`

`EXECUTOR_BRANCH_PROBE=TITLE_ONLY`

`ITERATION_92_CLASSIFICATION=DOCUMENT_READY_NOT_PROVEN`

`FUTURE_ORACLE=RAW_TITLE_ON_OWNED_HWND_PLUS_EXISTING_TIMING_EVENTS`

Focused offline branch tests passed: `40 tests, OK`.
