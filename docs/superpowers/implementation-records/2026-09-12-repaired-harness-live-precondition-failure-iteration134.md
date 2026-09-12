# Repaired Harness Live Precondition Failure — Iteration 134

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-133 clear review and exactly one disposable native-outcome diagnostic  
Executor HEAD before this docs-only record: `8e152a7`

## Epoch classification

Exactly one disposable AutoCAD session reached `document_ready=True`. The
repaired harness created a separate benign window (HWND `919106`, PID
`27836`, thread `20716`) and attempted to establish it as foreground. The native
`SetForegroundWindow` call returned `0`; exact foreground readback remained
HWND `330256`, PID `3172`, thread `8844`. The required foreign precondition was
therefore false, and the production foreground helper was not invoked.

The harness then raised `NameError: name 'foreign_verified' is not defined` in
the fail-closed branch. The bounded routine now returns the result as
`foreign_precondition`, but that branch still referenced the former variable
name. This is a disposable-harness defect only and does not justify a
production behavior change.

## Cleanup and integrity

- Owned AutoCAD target: HWND `1181088`, PID `14728`, thread `5700`.
- `foreign_precondition_verified=False`.
- Production helper, plugin bootstrap, raw-LISP, candidate open, and health:
  `NOT RUN`.
- Cleanup warnings: none; owned PID and stage root were absent.
- Default DWT SHA-256 before and after:
  `b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.
- No source, PDF, DXF, CAD, or key-policy path was mutated.

The raw proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\foreground-native-outcome-diagnostic-iteration134-proof.json`.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=CLASSIFIED
EVIDENCE=This record; proof C:\temp\cad-agent-task6-live-20260911\foreground-native-outcome-diagnostic-iteration134-proof.json; exactly one authorized disposable diagnostic; document_ready=True; owned target=HWND 1181088/PID 14728/thread 5700; benign target=HWND 919106/PID 27836/thread 20716; benign SetForegroundWindow result=0; foreign_precondition_verified=False; production helper NOT INVOKED; harness NameError=foreign_verified; plugin/raw-LISP/candidate/health NOT RUN; cleanup clean; DWT unchanged; no source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=DISPOSABLE_HARNESS_FAIL_CLOSED_BRANCH_REFERENCES_STALE_FOREIGN_VERIFIED_NAME
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and authorization for one offline-only disposable harness repair replacing the stale branch variable with the bounded precondition result, plus focused regression; no live retry, production repair, plugin/raw-LISP/candidate/health, or source/DXF/CAD mutation until authorized
HUMAN_GATE=NO
```
