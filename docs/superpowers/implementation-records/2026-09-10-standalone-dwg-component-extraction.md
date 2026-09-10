# Standalone DWG Component Extraction — Task 6 Implementation Record

Date: 2026-09-11
Branch: `codex/audit-text-style-compat-20260910`
Implementation/evidence commits: `1e17f159a2bd089f9797876beb769a872dee45b0`,
`a1fece80b1efae831d442626c6454a0ae23533d0`,
`94719ca3e854dd3bb6b668217924c85e3d07c214`, and
`a17032275a628328dcad0fd15166e413faee3663`

## Scope and boundary

Task 6 adds an opt-in `autocad_mechanical` gate for the approved standalone
`BVTL.dwg` source. The gate consumes an operator-prepared private fixture and
never stores the source DWG, customer annotations, candidate DWG, or private
evidence in Git.

The live path is candidate-only and read-only with respect to the source:

1. Open the approved source through the existing File IPC client.
2. Verify the loaded `AutoCAD Mechanical 2027` host and exact plugin binary
   identity through `health`.
3. Run `drawing_setup_audit` and require stable DBMOD/read-only setup evidence.
4. Run `standalone_dwg_component_inspection` and require `XREF=0`, exact
   inspection groups/handles, unchanged source hash/DBMOD, and eligibility.
5. Require an absent disposable output, then run
   `standalone_dwg_component_extraction` with `EMPTY_NEW_DATABASE`.
6. Reopen and hash the candidate before accepting `save_performed=true`.
7. Compose the detached source BASELINE, `R3_CANDIDATE`, registry, and root
   `R4` candidate revision. Query only the candidate-bound handles through
   `drawing_query`.
8. Close the candidate without saving and remove it only after the returned
   candidate hash and identity match. Reopen/check/close the source without
   saving.

The page-1 delta regression uses the existing inspection-backed allowlist:
`cargo-side-frame` is rejected by `build_standalone_extraction_plan` when it
has not been inspected. No native full-drawing or exact-base-Xref restriction
was changed.

The candidate identity boundary was then remediated after independent review
found that the real .NET cleanup identity (`path|length|creation ticks|write
ticks`) was being exposed as the schema `file_id`. The raw filesystem identity
is now retained only as the internal cleanup recheck, while the public result
exposes `candidate-file-<sha256(raw identity)>`, which satisfies the frozen
schema grammar. C# reader/dispatcher coverage and the Python result validator
now exercise this real-like raw identity end to end.

The layer-name boundary was then remediated after the live read-only setup
probe established that the approved source legitimately uses the AutoCAD layer
name `Duong manh`. The previous identifier-only validator rejected that name
before File IPC, so a truthful fixture could not reach the inspection gate.
Commit `a17032275a628328dcad0fd15166e413faee3663` changes only
`source_layer_expectations` and observed `layers` to a closed safe-text
contract: 1-512 printable characters, with empty, control-character,
malformed-array, and unknown-field inputs rejected. Group IDs, component IDs,
handles, and entity-type tokens remain identifier-strict. Python, JSON schema,
and C# validators now share the boundary, with `Duong manh` regression tests.

## Interfaces and fixture contract

The gate reuses the existing `DotNetIPCClient`, `FileIPCLiveMCPClient`, Windows
trigger helpers, standalone adapter, DARA, component-view registry, candidate
revision, and drawing-query owners. It adds no transport or truth store.

The private fixture must contain exactly these logical fields:

- `project_id`, `drawing_id`, `candidate_id`;
- `inspection_request`, `extraction_plan`;
- `source_upstream_evidence`, `observation_evidence_sha256`;
- `candidate_upstream_evidence`, `candidate_observation_evidence_sha256`;
- `query`.

The opt-in environment additionally supplies the File IPC roots, AutoCAD HWND
and LISP path, fixture path, approved source path/hash/setup-audit hash, and
disposable candidate root. The gate reports each absent or invalid prerequisite
as `SKIP`; it does not turn an unavailable live session into a PASS.

## Evidence and verification

Evidence captured on the layer-name remediation head
`a17032275a628328dcad0fd15166e413faee3663`:

- `scripts/verify.ps1`: exit `0`, all checks passed.
- Full offline Python suite: `3278 passed`, `21 deselected`, `74 subtests`.
- Offline IPC JUnit: `134` tests, `0` failures, `0` errors, `0` skipped.
- Full C# solution: `238 passed`, `0` failed, `0` skipped.
- Layer-name remediation focused set: Python/C# cross-language contract tests
  passed (`97` Python tests in the focused owner set; `49` C# contract tests).
- Read-only live preparation: approved `BVTL.dwg` opened with source hash
  `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`, .NET
  `health` and `drawing_setup_audit` succeeded with `changed=false` and
  `DBMOD=0`. The standalone live gate remained `NOT RUN` because the truthful
  private fixture was absent; no inspection, extraction, candidate creation,
  source save, or accepted-drawing mutation occurred. The detailed private
  preparation record is outside Git at
  `C:\temp\cad-agent-task6-live-20260911\task6-live-prep-20260911.txt`.
- `autocad_mechanical` unavailable-state probe: `17 skipped`; live marker
  `NOT RUN` because the AutoCAD/File IPC session was not prepared.
- Real-data/private gates: `2 skipped` because their private inputs were not
  supplied.
- Causal trigger RED oracle: `1 expected failing negative test`, retained as
  an intentional oracle and not counted as a product failure.
- Python 3.11.9, .NET SDK 10.0.302, and repository Ruff checks passed.
- `git diff --check`: pass; verification left the repository clean.

The preceding hash-binding and candidate-identity remediations had SOL status
`VERDICT=PASS`, with `MATERIAL_FINDING=NONE` and `HUMAN_GATE=NO`. SOL's fresh
review then identified the real layer-name incompatibility and requested this
single contract remediation; the remediation is now locally verified and
awaits fresh SOL review. No live CAD verdict is inferred from these offline
results.

## Reuse dossier classification

Classification: reuse-first, thin orchestration test gate. Existing owners
remain responsible for request/result schemas, source freshness, candidate
serialization/readback, cleanup policy, DARA custody/currentness, R3 registry
binding, R4 candidate revision state, and bounded entity reads. The new file
only coordinates those owners and records truthful live availability.

## State and remaining risk

Source and accepted drawings were not modified. No private artifact was added
to Git. No production candidate was promoted.

The remaining risk is explicitly live-gated: one bounded attempt had the
approved `BVTL.dwg` source, AutoCAD Mechanical 2027 session, operator fixture,
and File IPC prerequisites available, but it correctly failed closed at
`S3C_SOURCE_READ_ONLY_REQUIRED` because the existing open path opened the
source writable. Therefore this record remains implementation and
offline-contract evidence, not live CAD acceptance or release evidence.

## Read-only source-open remediation and iteration 27

SOL's fresh review of the live finding identified the existing owner boundary:
`FileIPCLiveMCPClient.drawing_open` called AutoCAD `vla-open` without its
read-only argument. The bounded remediation in commit
`1e17f159a2bd089f9797876beb769a872dee45b0` adds an explicit keyword
`read_only=True` opt-in. Only the standalone Task-6 source-open call uses it;
candidate opens remain on the default writable path. The `S3C` read-only policy
was not weakened, and the source/fixture/accepted drawing were not changed.

Regression evidence on the pushed code commit:

- `test_mcp_client_drawing_open.py`: `12 passed`, including the exact
  `:vlax-true` read-only call, active-document path verification, and the
  unchanged writable default signature.
- Focused FileIPC/Task-6 owner set: `32 passed`, one live prerequisite skip,
  and one intentional causal-RED diagnostic.
- `scripts/verify.ps1`: exit `0`; C# `238 passed`, offline Python `3354`
  passed, offline IPC `134` passed, real-data `2 skipped`, AutoCAD Mechanical
  `17 skipped`, and `git diff --check` passed.

Iteration-27 live evidence is private at
`C:\temp\cad-agent-task6-live-20260911\task6-live-gate-iteration27-evidence.txt`.
The gate reached health, setup audit, and standalone inspection dispatch, then
failed closed with `S3C_SOURCE_READ_ONLY_REQUIRED`. No candidate was created;
the disposable root was empty and the source hash remained
`78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`.
Live acceptance remains `NOT RUN` until SOL reviews this remediation and a new
attempt actually passes inspection/extraction/query.

## Read-only fallback fail-closed remediation and iteration 29

SOL's fresh review of exact pushed HEAD
`cf7b5f139adc63b07d4694a488dd449bf646258f` found one remaining escape path in
the new owner-level contract: when VLA read-only open failed and the positive
start-tab proof was available, `drawing_open(read_only=True)` could still call
the generic writable `_.OPEN` fallback. The bounded remediation in commit
`a21bf814545bbaa3148ce34a7940661be76e1b6d` propagates the VLA failure whenever
`read_only=True`, so no writable command fallback is possible. The existing
writable fallback remains available for `read_only=False`.

Regression and verification evidence on the exact pushed code commit:

- `test_mcp_client_drawing_open.py`: `13 passed`, including the new
  fail-closed regression and the existing writable-fallback regression.
- Focused FileIPC/Task-6 owner set: `33 passed`, one live prerequisite skip,
  and one intentional causal-RED diagnostic.
- `scripts/verify.ps1`: exit `0`; C# `238 passed`, offline Python `3355`
  passed, offline IPC `134` passed, real-data `2 skipped`, AutoCAD Mechanical
  unavailable probe `17 skipped`, Ruff passed, and `git diff --check` passed.

The source DWG, private fixture, accepted drawing, candidate output, and live
AutoCAD state were not changed. This is implementation and offline-contract
evidence only. Live acceptance remains `NOT RUN` pending a fresh SOL review of
`a21bf814545bbaa3148ce34a7940661be76e1b6d`; only after `VERDICT=PASS` may the
standalone live inspection/extraction/query gate be attempted again.

## Iteration 30 live session bootstrap result

SOL returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, and `HUMAN_GATE=NO` for
the fail-closed remediation. One fresh opt-in live gate was then attempted
with AutoCAD Mechanical 2027 started without `BVTL.dwg` already open, the
approved fixture and source hashes configured, and the existing plugin/dispatcher
bootstrap route. The attempt stopped before `drawing_open(read_only=True)`:

- `MCPTimeoutError`: AutoCAD dispatcher did not become ready;
  `request_id=630d574a66d5`.
- Pytest result: `1 failed, 1 deselected` in `14.54s`.
- No health, setup audit, inspection, extraction, candidate creation, query,
  or cleanup gate ran.
- AutoCAD was on `[Start]` and closed without a drawing. The source hash stayed
  `78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`, and the
  disposable root remained empty.

This is a session/bootstrap readiness finding, not a read-only-path result.
Live acceptance therefore remains `NOT RUN`. The detailed private evidence is
at `C:\temp\cad-agent-task6-live-20260911\task6-live-gate-iteration30-evidence.txt`.
No retry or production-code mutation was made after the bounded failure; the
next action is held for a fresh SOL decision on the existing bootstrap path.

## Iteration 31 bootstrap/readiness diagnostic

SOL classified the iteration-30 timeout as a bootstrap/readiness boundary and
authorized exactly one diagnostic on a fresh blank AutoCAD Mechanical 2027
session, without running the Task-6 extraction gate. The existing native LISP
trigger was called once with the configured load expression for
`mcp_dispatch.lsp`, and it returned without a delivery exception:

- `LISP_LOAD_TRIGGER_RETURNED=YES`.
- Exactly one FileIPC `ping` was issued through the existing dispatch trigger,
  with a five-second timeout.
- The ping failed with `MCPTimeoutError: Timeout waiting for result`
  (`request_id=d4f6cc647159`); no terminal result/evidence was produced.

The session remained on `[Start]` and was closed without a drawing. The IPC
root had no request/result residue, the disposable root remained empty, and
the source hash remained
`78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`. No
source, candidate, accepted drawing, production CAD, or reviewed HEAD was
mutated. This diagnostic does not test the read-only source-open path; live
acceptance remains `NOT RUN`. Detailed private evidence is at
`C:\temp\cad-agent-task6-live-20260911\task6-bootstrap-diagnostic-iteration31-evidence.txt`.

## Iteration 32 explicit Start-tab bootstrap remediation

SOL's fresh review identified that the iteration-31 native text-delivery
return did not prove AutoLISP execution while AutoCAD was on the documentless
`[Start]` tab. The bounded remediation at code HEAD
`d79860b91ff34cef9e1898d353a98f6809dc445a` adds an explicit opt-in
`bootstrap_start_tab` path to the existing File IPC client. When the positive
Start-tab probe succeeds, the path creates one disposable blank document with
`_.QNEW`, loads the existing dispatcher, and requires one successful FileIPC
ping before source `drawing_open(..., read_only=True)` is allowed. Load or
ping failure closes the blank document without saving. A real active document
does not trigger `_.QNEW`, and the default writable path remains unchanged.

Focused owner tests passed (`21` drawing-open tests; `41` combined FileIPC and
Task-6 tests excluding the intentional causal-RED diagnostic, with one live
prerequisite skip). Authoritative verification passed with C# `238`, offline
Python `3369`, and offline IPC `134` tests, with zero product failures; the
private real-data and AutoCAD Mechanical gates remain unavailable, and live
Task-6 acceptance remains `NOT RUN`. The code/plan commit is pushed and the
fresh SOL review is pending. Private evidence and recoverable resume state are
at `C:\temp\cad-agent-task6-live-20260911\task6-bootstrap-context-iteration32-evidence.txt`
and `C:\temp\cad-agent-task6-live-20260911\wait-safe-resume-state-iteration32.txt`.

## Iteration 33 QNEW readiness hardening

SOL's fresh review found a delivery/readiness race in iteration 32: the native
command trigger can return after posting `_.QNEW` while the AutoCAD window is
still on the documentless `[Start]` tab. The bounded remediation at code HEAD
`8040adb54629a533dbfdb3efe1cb2ef0da92fa8e` adds an explicit bounded
`bootstrap_document_ready_probe` and waits until the window no longer reports
`[Start]` before marking bootstrap ownership, loading the existing dispatcher,
or issuing a FileIPC ping. If readiness times out, no LISP or source-open
expression is emitted and no cleanup is attempted for an unowned document.
Task-6 supplies the matching Windows probe; the existing no-QNEW real-document
path and default writable behavior remain unchanged.

The RED tests covered delayed/non-executed QNEW and the GREEN run passed `24`
drawing-open tests and `44` combined FileIPC/Task-6 tests with one live
prerequisite skip. Authoritative `scripts/verify.ps1` on the exact code commit
exited `0`: C# `238`, offline IPC `134`, and offline Python `3372`, with zero
product failures; the causal-RED diagnostic remains intentionally failing and
private real-data/AutoCAD Mechanical prerequisites remain skipped. No live
Task-6 gate was rerun, no source/candidate/accepted drawing was touched, and
fresh SOL review of `8040adb54629a533dbfdb3efe1cb2ef0da92fa8e` is required.

## Iteration 34 fresh live readiness result

SOL returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, and `HUMAN_GATE=NO` for
the iteration-33 readiness hardening. Exactly one fresh opt-in Task-6 live
attempt was run with AutoCAD Mechanical 2027 initially on `[Start]`, the
approved fixture and source hashes configured, and `BVTL.dwg` not open. The
native command trigger delivered `_.QNEW`, but the bounded readiness probe did
not observe a non-`[Start]` document within `10.26s`; the gate failed closed
with `START_TAB_BOOTSTRAP_DOCUMENT_NOT_READY` before LISP load, FileIPC ping,
source `drawing_open(read_only=True)`, health, setup audit, inspection,
extraction, candidate creation, or query.

Postcondition inspection showed AutoCAD still on `[Start]`; it was closed
without saving. The disposable root remained empty and source
`BVTL.dwg` retained SHA-256
`78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`. No
source, accepted drawing, candidate, production CAD, or reviewed HEAD was
mutated. Live Task-6 acceptance remains `NOT RUN`, not `PASS`. Detailed
private evidence is at
`C:\temp\cad-agent-task6-live-20260911\task6-live-gate-iteration34-evidence.txt`;
fresh SOL review of this live boundary is required.

## Iteration 35 Start-tab bootstrap-owner primitive diagnostic

SOL classified iteration 34 as a bootstrap-owner defect and authorized exactly
one bounded diagnostic focused only on creating the disposable blank document
through an existing AutoCAD-native mechanism. Repository code was not changed,
`BVTL.dwg` was not opened, and the Task-6 dispatcher was not loaded. A fresh
AutoCAD Mechanical 2027 process was observed at `[Start]`; the existing native
startup-script route (`acad.exe /nologo /b <script>`) with a disposable script
containing only `_.QNEW` transitioned the same process to
`[Drawing1.dwg]` in the observed session.

The blank session was closed through the native process close path without
saving. The source hash remained
`78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`, and the
disposable extraction root remained empty. A separate LISP sentinel probe did
not produce output, so it is not used as dispatcher evidence. This diagnostic
proves only the candidate native Start-to-blank primitive; dispatcher load,
FileIPC ping, source read-only open, extraction, and live acceptance remain
`NOT RUN`. Fresh SOL review is required before any production-owner change.
Private evidence is at
`C:\temp\cad-agent-task6-live-20260911\task6-bootstrap-owner-diagnostic-iteration35-evidence.txt`.

## Iteration 36 startup-session owner remediation

SOL returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, and `HUMAN_GATE=NO` for
the iteration-35 diagnostic. The exact bounded owner change was implemented
and pushed at code HEAD
`8afc7c0494e14cf2711641e4c23b060df4920ef`.

`WindowsAutoCADStartTabSession` launches a fresh disposable `acad.exe` with a
temporary startup script whose exact bytes are `_.QNEW\r\n`. It discovers the
main window by the launched process ID, requires the positive `[Start]`
observation, and returns process-bound command/LISP/dispatch/readiness
bindings. `FileIPCLiveMCPClient` waits for a non-`[Start]` document before
loading the existing dispatcher. Task 6 then loads the approved plugin through
the bound HWND and proceeds to the existing read-only source-open path. A
failed readiness/ping path closes the owned session without opening the source;
close timeout cleanup can terminate only the process created by this session.
No source, accepted drawing, candidate, or production CAD state was mutated.

Focused verification on the code head reported `48 passed`, `1 skipped`, `1
deselected`, and `9 subtests` with the intentional causal-RED test excluded;
Ruff and `git diff --check` passed. The authoritative
`.\scripts\verify.ps1` ran on the clean pushed commit and exited `0`:
C# `238 passed`; offline Python `3296 passed`, `21 deselected`, `80
subtests`; offline IPC JUnit `tests=134`, `failures=0`, `errors=0`;
real-data unavailable probe `2 skipped`; AutoCAD Mechanical unavailable probe
`17 skipped`; live Task 6 `NOT RUN`. The verifier also ran the expected causal
RED negative oracle and recorded one intentional failure without failing the
verification contract.

Private evidence and recoverable state are recorded at:

- `C:\temp\cad-agent-task6-live-20260911\task6-bootstrap-owner-remediation-iteration36-evidence.txt`
- `C:\temp\cad-agent-task6-live-20260911\wait-safe-resume-state-iteration36.txt`

Fresh SOL review of the pushed owner change is required before another live
Task-6 attempt.

## Iteration 37 fresh live Task-6 result

SOL returned `VERDICT=PASS`, `MATERIAL_FINDING=NONE`, and `HUMAN_GATE=NO` for
the iteration-36 owner remediation and authorized exactly one fresh live
Task-6 gate. The startup-session owner successfully created a blank document
from `[Start]` in the same owned AutoCAD process (`PID 28488`, `HWND 4983510`,
title `Autodesk AutoCAD 2027 - [Drawing1.dwg]`).

The first failure was the existing dispatcher readiness boundary: FileIPC
`ping` request `03e4086d8d2f` timed out and the client raised
`MCPTimeoutError: AutoCAD dispatcher did not become ready` after `73.71s`.
The gate stopped before `BVTL.dwg` open, health, setup audit, inspection,
extraction, candidate creation, candidate query, or source reopen. Cleanup
left no AutoCAD process, removed the disposable startup script, and left the
candidate directory empty. The approved source SHA remained
`78490aa0c57d24ffd58c4555f0945df527429658180e414735da68f4e24cc9b8`; no
source, accepted drawing, candidate, or production CAD state was mutated.
Live Task-6 acceptance remains `NOT RUN`, not `PASS`. The exact private
evidence is at
`C:\temp\cad-agent-task6-live-20260911\task6-live-gate-iteration37-evidence.txt`.

The next action is a fresh bounded SOL diagnosis of this dispatcher boundary;
do not retry live Task 6 or weaken readiness/custody policy before that
review.
