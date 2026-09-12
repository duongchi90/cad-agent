# Raw-LISP Four-Observable Seam Oracle — Iteration 143

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-142 clear review and exactly one offline-only four-observable seam oracle  
Executor HEAD before this docs-only record: `0b3ac13`

## Bounded oracle

The disposable oracle reused the exact generated `drawing_open` ACK-wrapped
expression and the existing `make_windows_lisp_trigger` /
`_make_windows_text_trigger` path with `RecordingUser32`. It independently
controlled and recorded receiver consumption, evaluator entry, exact marker
write, and Python ACK observation. It did not start AutoCAD, invoke the plugin,
open a candidate, call health, or modify production files.

## Deterministic classification evidence

All five cases reconstructed the exact expression frame and matched its
UTF-16LE bytes byte-for-byte. Every positive `PostMessageW` result was `1`, and
all messages targeted receiver HWND `4353`.

| Case | Independent result | Classification | Public timeout |
| --- | --- | --- | --- |
| receiver does not consume | receiver=false | `NOT_CONSUMED` | preserved |
| receiver consumes, evaluator does not enter | receiver=true, evaluator=false | `CONSUMED_NOT_EVALUATED` | preserved |
| evaluator enters, marker write fails | evaluator=true, marker=false | `EVALUATED_MARKER_NOT_WRITTEN` | preserved |
| evaluator writes marker, observer cannot read it | evaluator=true, marker=true, observer=false | `EVALUATED_MARKER_NOT_OBSERVED` | preserved |
| evaluator writes marker and observer reads exact token | all four=true | `EVALUATED_AND_OBSERVED` | success |

The success case reached the existing dispatcher/identity stub only after the
ACK observer succeeded. Every negative case made no dispatcher call before the
existing `RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED` timeout. Each case
left its IPC root empty after the existing cleanup.

The first disposable runner attempt caught two harness-only defects before any
live action: a receiver-queue tuple index used `lParam` instead of `wParam`,
and the positive case lacked its fake dispatcher binding. Both were corrected
in the disposable script before the final proof was produced; no production
file or live epoch was involved.

## Boundary conclusion

The four independent observables now deterministically separate
`NOT_CONSUMED`, `CONSUMED_NOT_EVALUATED`, marker-write failure, marker
non-observation, and full ACK success while preserving the public timeout
contract. This is an offline seam result; it does not claim that the real
AutoCAD receiver consumed or evaluated the expression in the earlier live
epoch.

## Evidence and safety

- Disposable proof:
  `C:\\temp\\cad-agent-task6-live-20260911\\raw-lisp-four-observable-seam-oracle-iteration143-proof.json`.
- `all_classifications_match=True`;
  `all_negative_cases_preserve_public_timeout=True`;
  `positive_case_observer_success=True`.
- `production_files_modified=False`; `live_epoch_started=False`.
- No production mutation, live retry, plugin/candidate/health execution,
  visual/dimension work, persistence, source/DXF/CAD mutation, provider/M2
  work, or key-policy change occurred.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=VERIFIED_SEAM_ORACLE
EVIDENCE=This record; proof C:\\temp\\cad-agent-task6-live-20260911\\raw-lisp-four-observable-seam-oracle-iteration143-proof.json; five deterministic four-observable cases; all_classifications_match=True; all negative cases preserved RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED; positive observer success=True; exact expression/framing reused; cleanup clean; production_files_modified=False; live_epoch_started=False; no production/live/plugin/candidate/health/source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=REAL_AUTOCAD_RECEIVER_CONSUMPTION_AND_EVALUATION_NOT_PROVEN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only live epoch using the four-observable evidence plan, adding only receiver/evaluator/marker/observer diagnostics and stopping at the first boundary; no retry or production/source/DXF/CAD/key-policy mutation
HUMAN_GATE=NO
```
