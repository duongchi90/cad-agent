# Startup preload contract — iteration 150

## Result

- Status: offline GREEN; live execution intentionally not run.
- Code head before this record: 0809478af8d1c5b7b6eb78de774aa5745279f160.
- RED oracle: C:\temp\cad-agent-task6-live-20260911\startup-preload-characterization-iteration150.py.
- Authorization: exactly the SOL-authorized offline startup-preload owner characterization and causal RED.

The causal RED reproduced the current plugin-only startup contract: a
WindowsAutoCADStartTabSession configured with bootstrap_plugin_path only
returns bindings with dispatcher_preloaded=False. The existing owner derives
that field from whether bootstrap_lisp_path is supplied; the client-side LISP
path does not retroactively certify that startup loaded the dispatcher.

The bounded GREEN characterization then supplied the existing paired
bootstrap_lisp_path and ipc_root parameters to the same startup owner. It
returned dispatcher_preloaded=True, bootstrap_completion_confirmed=True, and
preserved the claim-bound dispatch trigger. No new transport or production
architecture was added. The live harness repair is therefore a parameter
wiring repair: pass the existing dispatcher LISP and IPC root into the
startup session before it is launched.

## Exact offline evidence

    RED: plugin-only startup expected preload but returned dispatcher_preloaded=False
    GREEN: plugin-only contract characterized as false; fully configured contract returned true
    GREEN: bootstrap_completion_confirmed=True
    GREEN: dispatch trigger claim-bound=True
    focused phase4: 40 passed
    authoritative offline JUnit: 3406 passed; failures=0; errors=0; skipped=0
    C# tests: 238 passed
    DotNet IPC JUnit: 134 passed; failures=0; errors=0; skipped=0
    causal-red: 1 expected failure
    real-data unavailable probe: 2 skipped
    AutoCAD Mechanical unavailable probe: 17 skipped
    scripts/verify.ps1 exit: 0
    live/M2: NOT RUN

The repository regression is
mcp_integration_lib/tests/test_phase4.py::FileIPCClientTests::test_start_tab_preload_certificate_requires_dispatcher_lisp_contract.
The existing production factory already accepts and forwards
bootstrap_lisp_path and ipc_root; the missing values are in the disposable
iteration-116 live harness construction.

## Safety and next review

No live epoch or retry followed iteration 149. No candidate, health, visual,
dimension, persistence, source, DXF, CAD, provider, M2, plugin, or key-policy
state changed. The authoritative SourceCustody HMAC/identity-key contract
remains fail-closed and unchanged. The page-1 PDF remains key-free
DRAFT_REFERENCE / MODIFY NONE.

The next action requires fresh SOL review: if clear, run exactly one
disposable read-only live epoch whose startup owner receives the existing
dispatcher LISP and IPC root, then require startup dispatcher_preloaded=True,
claim-bound readiness, one exact semantic File IPC drawing-open request/result,
zero raw fallback, and exact active-path readback. Stop at the first boundary;
do not retry.

    STATE=OFFLINE_GREEN
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-startup-preload-contract-iteration150.md; C:\temp\cad-agent-task6-live-20260911\startup-preload-characterization-iteration150.py; mcp_integration_lib/tests/test_phase4.py; scripts/verify.ps1; HEAD 0809478af8d1c5b7b6eb78de774aa5745279f160
    VERDICT=CLEAR_CONTINUE
    FIRST_UNSATISFIED_BOUNDARY=LIVE_STARTUP_DISPATCHER_PRELOAD_AND_FILE_IPC_DRAWING_OPEN_NOT_PROVEN
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only live epoch with bootstrap_lisp_path and ipc_root supplied to the startup owner, requiring truthful dispatcher_preloaded and exact File IPC request/result/active-path evidence, with no retry or raw fallback
    HUMAN_GATE=NO
