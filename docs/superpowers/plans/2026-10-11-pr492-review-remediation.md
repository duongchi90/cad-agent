# PR #492 independent review remediation

Status: completed (offline implementation; new-head re-review/native promotion pending)
Base SHA: 133294b7f5ea8c4f768a08a9605b3897fab8a784
Completion Head SHA: 6aebdd5d742a76915cac1e13039dc5fb4fe1acc8
Previous Completion Head SHA: f57269bd96a8b2b503306bb2897ef254084e213c
Reviewed Head SHA: eddcc44b80e5e5e29c06c5230cd49ff7c1f7d03e
Approval date: 2026-10-11; Human supplied both independent reviews and authorized
the existing SOLO production loop. No subagents or new subsystem.

## Findings, existing owners and bounded repair

- F1 / Integration finding 1: actual `repair_live` accepted a review containing
  both contour and primitive failures. Make the existing contour refusal
  unconditional before backup or mutation; preserve dimension refusal/recovery.
- F2: saved reversed/tilted ARC extrusion with incident WCS LINE endpoints passed
  headless review but failed live review. Reuse `contour_endpoints` in both paths
  with observed native fields. Unsupported/nonfinite geometry is unavailable,
  never discharged with written expectations. No new geometry engine.
- F3 is a coverage/native-evidence concern, not an established production defect.
  Add narrow native type-bit controls at the existing live reviewer consumer.
  This remains replay/offline evidence; actual AutoCAD semantics are not proven.

## Regression and verification

Before production changes, five targeted controls produced three causal failures:
mixed contour/primitive repair DID NOT RAISE; reversed and tilted ARC headless
review falsely passed. Contour-only and default-plane positive controls passed.
Retained evidence: native-dimension-feature-production-evidence-20261011/
review-remediation-red.xml (outside Git).

After the minimal fixes: contour controls 17 PASS; expanded contour/DIM and owner
boundary selection 56 PASS, including nonfinite ARC center/radius and native DIM
type bits 0/1, 32/33, unsupported 34-38, negative and boolean values.
Command: `python -m pytest mcp_integration_lib/tests/test_contour_join_guard.py
mcp_integration_lib/tests/test_dimension_feature_binding.py
tests/test_reuse_architecture_boundaries.py -q`.
Nearest-owner selection (DXF owner, both relationship guards, native DIM consumer,
Phase4, live CLI/repair and architecture boundaries): 199 PASS.

Canonical `scripts/verify.ps1 -PythonExe C:/cad-agent/.venv-py311/Scripts/python.exe`
completed with exit 0 on the clean previous implementation f57269bd96a8b2b503306bb2897ef254084e213c: 3471 Python
plus 74 subtests PASS, JUnit3545 with zero failures/errors/skips; 261 .NET PASS;
76 IPC plus 52 subtests PASS, JUnit128 with zero failures/errors/skips.
The required causal-RED negative oracle produced its expected failure and the
script gate passed. Lock/environment/lint/Autodesk DLL/diff/side-effect gates
passed. Existing MSB3277 and nullable .NET warnings remain; no .NET source changed.
Real-data unavailable probes2 SKIP; native unavailable probes18 SKIP; AutoCAD/M2
NOT RUN. Full local log: D:/Cad agent temp/
native-dimension-feature-production-evidence-20261011/full-verifier-review-remediation.txt.
Use already-installed SDK10.0.401 through process-local PATH; no installation.
No retry of the unchanged
WINDOW_RECEIVER_AMBIGUOUS condition, no new CAD source case, no frozen/revealed
candidate edit or gold access. Publishing a draft does not close independent
exact-head re-review or native promotion.

## Follow-up independent Integration I1

Re-reviewed published head fd23a642c361350a81bca96dac8e35bc589a014b:
Security bounded offline PASS resolves F1/F2/F3; Integration BLOCKED identifies
low-three-bit DIM type validation accepting ordinate-only/unknown flags.
Integration result is durable at PR492 comment6104654975. Security plain text
was supplied by Human; it grants no native/merge clearance.

[Autodesk group70 specification](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-EDD54EAC-A339-4EBA-AEA6-EC8066505E2B.htm)
permits linear/aligned base types0/1, block bit32 and moved-text bit128. Bit64
applies only to ordinate base type6. Reuse the existing shared DIM predicate;
accept only 0/1,32/33,128/129,160/161. Reject bit64 and unknown combinations.
No API/schema/native mutation change.

Before the predicate edit, native replay and actual saved-DXF controls produced
10 causal FAIL/19 passing controls. Negative flags64/65/96/97/256 falsely passed;
documented positive text-position flags128/129/160/161 remained valid.
Retained dimtype-flag-red.xml. After the single predicate correction, combined
guard/owner-boundary selection74 PASS. Canonical verifier completed on clean
follow-up Completion Head above: 3489 Python plus74 subtests PASS, JUnit3563
with zero failures/errors/skips; 261 .NET and76 IPC plus52 subtests PASS.
Expected causal-RED oracle and lint/lock/environment/diff/side-effect gates PASS.
Real-data2/native18 unavailable probes SKIP; AutoCAD/M2 NOT RUN. Final local log:
D:/Cad agent temp/native-dimension-feature-production-evidence-20261011/
full-verifier-dimtype-flags.txt; SHA256
6267d6633671b51386c5fbd01336134ae8b0cdbed62a2c9d7a9dc2c99a065690.
No repeated CAD case or unchanged receiver retry. New exact-head hosted CI and
independent review remain required. Human requires reviewers to post their
exact-head verdicts directly on PR GitHub and return the comment links.
## Native cold-open bootstrap remediation

Status: executing; actual default cold-open witness passed, final verifier and
exact-head independent native acceptance remain pending.
Base: 133294b7f5ea8c4f768a08a9605b3897fab8a784.
Approval: Human continuous existing-owner hardening scope, 2026-10-11;
[PO causal scope](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6106985455).

The actual native contour/DIM tests passed after deploying identical dispatcher
bytes into the existing trusted bundle directory. No trust configuration changed.
Cold DWG reopening then dropped the one bootstrap expression while the editor
was opening, leaving C:MCP-DISPATCH undefined. Warm binding restored correct
0.1mm gap readback; diagnostic settle8 also restored it. Neither was default
production clearance. A readonly COM observation during cold opening was
temporarily rejected; after exact target/CMD0/quiescence observation, the first
loader succeeded. COM was diagnostic only, never a native command transport.

Reuse FileIPCLiveMCPClient, existing raw-LISP/claim-bound Windows triggers,
normalized exact paths, root checks, and temporary readonly receipt pattern.
Before loading in the real claim-bound route, require a nonce-bound completed
readonly editor expression reporting the requested active full path. At most
three readonly probes within the existing timeout; opening and loader are not
retried. Wrong target/nonce, missing or incomplete receipt are nonPASS before
bootstrap. Retain final dispatcher ping and post-load native path verification.
Legacy fixture replay behavior is unchanged. No new public API, transport,
dependency, dispatcher, store, geometry owner or native mutation capability.

Write-set addition: mcp_integration_lib/mcp_client.py and its existing
tests/test_mcp_client_drawing_open.py, plus this record.
RED: two failures/ten valid controls pass before change: dropped bootstrap and
absent exact-document prerequisite. Focused current selection:145 tests plus
6 subtests PASS; explicit causal_red/native markers excluded as in verifier.
Default native cold reopen of the retained radius-only persisted witness now
reads3 entities/2 joins and rejects both0.1mm gaps without degradation; protected
dirty V13 source custody/hash and disposable DWG bytes unchanged, fixture closed.
Canonical verifier at clean implementation head
d4c09062041e9ab3a574d13a39a4c43c740c889a: PASS,3492 Python tests plus77
subtests,261 .NET tests,76 IPC tests plus52 subtests; zero offline failures,
errors or skips. Command: scripts/verify.ps1 -PythonExe
C:/cad-agent/.venv-py311/Scripts/python.exe, process-local installed SDK PATH.
Known causal_red negative oracle failed as required; unavailable-state native18
and real_data2 probes skipped, not qualification PASS.

Coupled contour and wrong-feature DIM survive actual SaveAs/close/cold-reopen
with unchanged verdicts and no degraded readback. The bound DIM's first batch
reopen was nonPASS before usable entity readback; its exact open failure was not
captured by the batch harness. Subsequent default cold-open instrumentation
passed with one exact-path acknowledgement then one loader,LINE1/DIM1 readback.
Retain that failed epoch; it is not evidence of changed DIM geometry or of
universally reliable cold startup. Native gate acceptance and merge clearance
remain pending independent review of these explicitly bounded observations.
Source V13 remains sole held dirty document,DBMOD29; its disk hash and all
disposable DXF inputs remain unchanged. No source/gold/frozen drawing mutation.

## Joint elevation headless false-PASS remediation

Status: executing; published head remains8cb4c09 during independent review.
Approval: Human existing-owner causal hardening scope,2026-10-11.
Current base remains133294b7f5ea8c4f768a08a9605b3897fab8a784.
Existing Security chat feedback identifies that joint Z translation preserves
LINE/DIM and contour incidence while headless source geometry checks ignoreZ.
The finding is technical input, not a durable independent verdict. Publication
requested from the same Security role; executor confirmed it separately:
[causal checkpoint](https://github.com/duongchi90/cad-agent/pull/492#issuecomment-6107554499).

Actual saved-DXF paired reviewer regression: twoZ2mm cases falsely pass
headless, while native boundary replay rejects the primitive displacement;
twoZ0 controls pass both. All DIM/contour relation checks remain valid, so this
proves the source-written primitive comparison boundary, not a relation defect.
Reuse existing DXF test-support, headless reviewer and dimension integration
tests. Smallest repair compares full native LINE endpoints with source-written
points using existing3D distance; generated2D points implyZ0. Existing INSERT
3D comparison is mathematically unchanged. No native transport/readback logic,
source recognition, schema, geometry engine or subsystem changes.

Focused command: python -m pytest dxf_builder_lib/tests
mcp_integration_lib/tests/test_dimension_feature_binding.py
mcp_integration_lib/tests/test_contour_join_guard.py
tests/test_reuse_architecture_boundaries.py -q
-m "not causal_red and not autocad_mechanical and not real_data".
Result:141PASS; Ruff F401 and diff whitespace checks PASS.
Canonical verifier and publication pending; no repeated native run because the
changed distance helper is used only by the headless reviewer. Existing bounded
native evidence/failed epochs are preserved, not promoted to new clearance.

Security posted matching exact-head CHANGES_REQUESTED directly:
https://github.com/duongchi90/cad-agent/pull/492#issuecomment-6107544090.
Its applicable ARC/other primitive request is confirmed, not assumed: standalone
ARC,CIRCLE,TEXT all falsely pass a2mmZ displacement. Broader deterministic RED
at the LINE-only intermediate head:7FAIL/5valid controlsPASS; failures cover
three remaining displaced primitive types and four nonfinite nativeZ values.
Existing headless owner now compares full LINE WCS endpoints, and ARC/CIRCLE
centers/TEXT insertion transformed by ezdxf's existing OCS-to-WCS API. Generated
2D written points implyZ0; nonfinite distance cannot satisfy tolerance.
No source-approved geometry, dimensions, relation obligation or native reader
is inferred or rewritten. Additional write-set:test_reviewer.py in existing
DXF owner. Final focused/nearest selection:153PASS, Ruff and whitespacePASS.
Final canonical verifier at clean implementation
7fc15e489298592ee0fe9cf413ceeb96751ddde8: PASS,3508 Python tests plus77
subtests,261.NET,76IPC plus52subtests. Offline JUnit3585 and IPC JUnit128 have
zero failures/errors/skips. Command:scripts/verify.ps1 -PythonExe
C:/cad-agent/.venv-py311/Scripts/python.exe with installed SDK process-local PATH.
Known causal_red oracle failed as required; real_data2/native18 unavailable
probes areSKIP, not runtime PASS. This distance function has only headless
callers; native reviewer imports unchanged relation functions. Prior actual
native/persistence observations remain bounded history and require independent
current-head disposition; no new native/merge clearance. Only this record changes
after verified implementation. The earlier LINE-only verifier4703419 passed but
was not final clearance. Independent re-review of the newly published head is
required before merge; previous8cb4c09 verdicts cannot transfer.

## I2 nonfinite scalar geometry remediation

Status: implementation/offline verification complete; publication and independent
exact-head review/native disposition pending.
Approval: Human's explicit four-field I2 repair scope,2026-10-11.
Base133294b7f5ea8c4f768a08a9605b3897fab8a784; reviewed parent
580a8afbfa40d28856f1dd10397a5d1537c4985e.
Independent exact-head Integration finding:
https://github.com/duongchi90/cad-agent/pull/492#issuecomment-6108162329.

Actual standalone saved/reopened DXFs preserve nonfinite CIRCLE radius,
ARC radius,start_angle,end_angle. Causal baseline4FAIL/16controlsPASS: every
NaN falsely passes headless; infinity and finite out-of-tolerance already reject;
finite exact/within-tolerance controls pass. No DIM/contour obligation masks the
scalar comparison. New tests assert the actual reopened scalar remains nonfinite
and review does not alter candidate bytes.

Existing headless reviewer now requires finite observed and written values
before its absolute comparison in only those four fields. Radius tolerance is
unchanged tolerance_mm; angle tolerance remains1e-4deg. Existing live _same
rejects nonfinite observed values against finite source values; its relative
and angular tolerance policies are not copied into the headless owner. No native
reviewer, mutation epic, transport, geometry engine, schema or other scalar
comparison changes. Retained DIM cold-reopen failed epoch stays unchanged.
Write-set:reviewer.py,existing test_reviewer.py,this existing record.

Focused command:python -m pytest dxf_builder_lib/tests
mcp_integration_lib/tests/test_phase4.py
mcp_integration_lib/tests/test_contour_join_guard.py
mcp_integration_lib/tests/test_dimension_feature_binding.py
tests/test_reuse_architecture_boundaries.py -q
-m "not causal_red and not autocad_mechanical and not real_data".
Result:209PASS; Ruff F401/whitespace checks passed.
Canonical verifier at clean implementation
abd1825a529523f5f73e98ebb285bae780b433c5:PASS,3528Python tests+77subtests,
261.NET,76IPC+52subtests; offline JUnit3605/IPC128 zero failures/errors/skips.
Command:scripts/verify.ps1 -PythonExe C:/cad-agent/.venv-py311/Scripts/python.exe
with installed SDK process-local PATH. Known causal_red negative oracle failed
as required; real_data2/native18 unavailable probes skipped, not runtimePASS.
Only this record changes after verified implementation. No live mutation or new
native qualification is claimed for this headless-only repair; exact-head hosted
checks and independent reviews remain pending. Retained failed DIM artifacts
were rehashed unchanged; the unattributed epoch is not rewritten or discarded.
