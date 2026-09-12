# Raw-LISP ACK Placement Repair — Iteration 117

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 `DRAFT_REFERENCE` downstream live acceptance  
SOL authorization: iteration-116 causal review  
Executor HEAD: `7a1d85688d7d4eb21ca8f6e80c43ec78ccac5b42`

## Causal RED

Before the production change, the new regression test
`test_drawing_open_ack_marker_precedes_activation` failed because the marker
token occurred after `(vla-activate mcp-open-doc)` in the generated expression
(marker position 678, activation position 466). The companion causal test
confirmed that an exact ACK marker does not imply active-document success when
the independent document-variables readback reports a different drawing.

## Minimal repair

The existing `FileIPCLiveMCPClient.drawing_open` owner now passes the exact
activation tail `(vla-activate mcp-open-doc)` to the existing ACK wrapper. The
wrapper inserts the same request-owned marker writer immediately before that
tail, inside the same owner-built `progn`. Exact token/path validation, bounded
wait, cleanup, claimed/live semantics, no implicit ACK retry, and legacy
fixture compatibility remain unchanged. The production path does not remove
or bypass the SourceCustody HMAC contract.

## Verification

- Pre-change RED: `1 failed, 5 passed, 40 deselected` for the ACK class;
- focused post-change ACK/fallback: `46 passed, 6 subtests`;
- full `test_mcp_client_drawing_open.py`: `46 passed, 6 subtests`;
- Ruff: changed production/test files passed;
- authoritative `scripts/verify.ps1`: exit `0`;
- .NET: `238 passed`;
- offline Python: `3315 passed, 21 deselected, 80 subtests`;
- offline JUnit: `tests=3395 failures=0 errors=0 skipped=0`;
- intentional causal-red: `1 failed, 19 deselected`;
- real-data unavailable gate: `2 skipped`;
- AutoCAD unavailable gate: `17 skipped`;
- `git diff --check`: clean and tracked tree clean at verification start/end.

No live epoch was run after the repair. Candidate/source/DXF/CAD state was not
mutated by this step.

## Canonical checkpoint

```text
STATE=IMPLEMENTED
EVIDENCE=This record; pushed executor HEAD 7a1d85688d7d4eb21ca8f6e80c43ec78ccac5b42; pre-change RED 1 failed/5 passed; focused ACK/fallback 46 passed with 6 subtests; full scripts/verify.ps1 exit 0; .NET 238 passed; offline Python 3315 passed with 21 deselected and 80 subtests; offline JUnit tests=3395 failures=0 errors=0 skipped=0; causal-red 1 expected failure; real-data 2 skipped; AutoCAD 17 skipped; no live rerun or source/DXF/CAD mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_REPAIR_LIVE_RAW_LISP_ACK_AND_CANDIDATE_ACTIVE_IDENTITY_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of the placement repair and authoritative verification; only after clear review may one exact disposable read-only live epoch rerun against the hash-bound page_01.dxf, with same-expression ACK before activation, one health call, and no-save cleanup
HUMAN_GATE=NO
```
