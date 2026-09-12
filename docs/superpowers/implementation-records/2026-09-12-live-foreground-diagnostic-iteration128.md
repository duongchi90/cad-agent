# Live Foreground Diagnostic — Iteration 128

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-127 clear review and one disposable read-only foreground diagnostic  
Executor HEAD before this docs-only record: `6e4bde2`

## Bounded diagnostic

Exactly one disposable AutoCAD Mechanical session was started with the
established `WindowsAutoCADStartTabSession` owner and the existing
`CADAGENT_DISPATCH` startup-script boundary. The session reached
`document_ready=True`. The instrumented `_reacquire_windows_foreground` helper
then succeeded for the owned top-level HWND `1246720` and PID `26208`.

The diagnostic stopped immediately after that foreground result, as authorized
by SOL. It did not invoke plugin bootstrap, raw-LISP, FileIPC, candidate open,
active-document identity, health, visual inspection, dimension inspection, or
any save/mutation path.

## Cleanup and integrity

- Public foreground error: none; `foreground_handoff_succeeded=True`.
- Internal diagnostic: none because the handoff succeeded.
- Cleanup warnings: none; owned AutoCAD PID was absent afterward.
- Disposable stage root was absent afterward.
- Default DWT SHA-256 before and after: `b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42`.
- Candidate/PDF/source/DXF/CAD/key-policy paths were not touched by this
  diagnostic.

The raw proof is retained outside Git at
`C:\temp\cad-agent-task6-live-20260911\foreground-stage-diagnostic-iteration128-proof.json`.

## Key policy

The page-1 PDF remains on the existing key-free `DRAFT_REFERENCE` lane with
`MODIFY NONE`. The authoritative SourceCustody HMAC/identity-key contract is
still fail-closed and was not removed or bypassed.

## Canonical checkpoint

```text
STATE=CLASSIFIED
EVIDENCE=This record; proof C:\temp\cad-agent-task6-live-20260911\foreground-stage-diagnostic-iteration128-proof.json; one disposable live diagnostic; document_ready=True; foreground_handoff_succeeded=True; owned HWND=1246720/PID=26208; plugin_bootstrap_invoked=False; raw_lisp_invoked=False; runtime_bootstrap_invoked=False; cleanup_clean=True; PID absent; stage root absent; default DWT unchanged; no candidate/PDF/source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_FOREGROUND_DIAGNOSTIC_PLUGIN_BOOTSTRAP_AND_RAW_LISP_ACK_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only live epoch through the existing plugin/bootstrap and raw-LISP ACK path, with exact candidate identity and one health call, then no-save cleanup; stop at the first causal failure and do not infer visual/dimension acceptance
HUMAN_GATE=NO
```
