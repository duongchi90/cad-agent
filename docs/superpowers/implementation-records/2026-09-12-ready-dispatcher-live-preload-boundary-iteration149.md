# Ready-dispatcher live preload boundary — iteration 149

## Result

- Status: classified; stopped at the first unsatisfied boundary.
- Code head: 2fa3040996d7cf5b33d73ae340516cd31deffbf7.
- Oracle: C:\temp\cad-agent-task6-live-20260911\candidate-activation-dispatcher-live-iteration149-proof.json.
- Authorization: exactly one SOL-authorized disposable read-only live epoch through the repaired binding-application path.

The wrapper did call the existing _apply_start_tab_bootstrap_bindings(bindings)
method, but the client still reported _bootstrap_dispatcher_preloaded=False.
The base disposable harness constructs TemplateStartupDispatchSession with
bootstrap_plugin_path only; it does not provide bootstrap_lisp_path or an IPC
root. The existing owner therefore correctly sets dispatcher_preloaded to
false in _confirm_bootstrap_bindings() because that field is defined by
self._bootstrap_lisp_path is not None.

This is a startup-preload contract boundary, not evidence that the semantic
File IPC drawing-open implementation or candidate open failed. The earlier
iteration-149 wrapper's proof enrichment used proof.get("dispatcher_preloaded",
True) when the base proof omitted the field; that derived value is not treated
as direct live evidence here. The direct client state and owner source are the
authoritative observations for this classification.

## Exact live evidence

    live_epoch_started=True
    document_ready=True
    startup_owner=WindowsAutoCADStartTabSession
    client_binding_applied=True
    client_dispatcher_preloaded=False
    raw-LISP fallback calls=1; forbidden by oracle; RuntimeError=RAW_LISP_FALLBACK_FORBIDDEN_IN_ITERATION149
    drawing-open File IPC requests=0
    terminal results=0
    active path=NOT RUN
    candidate identity/health=NOT RUN
    candidate SHA before=167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714
    candidate SHA after=167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714
    default DWT SHA before=b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42
    default DWT SHA after=b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42
    cleanup_warnings=[]; pid_absent_after_cleanup=True; ipc_root_absent_after_cleanup=True; scripts_root_absent_after_cleanup=True

The exact source owner is mcp_integration_lib/mcp_client.py:

    WindowsAutoCADStartTabSession._confirm_bootstrap_bindings()
      dispatcher_preloaded = self._bootstrap_lisp_path is not None
    candidate-activation-iteration116.py
      TemplateStartupDispatchSession(... bootstrap_plugin_path=SOURCE_DLL, ...)
      FileIPCLiveMCPClient(... bootstrap_lisp_path=DISPATCHER_LISP, ...)

The client-side LISP path alone does not certify that the live startup
dispatcher was loaded; the startup binding must carry a true, claim-bound
preload certificate first.

## Safety and next review

This was exactly one live epoch. No retry, no File IPC request/result, no
active-path readback, no candidate/health, no visual/dimension or persistence
work, and no source/DXF/CAD/provider/M2/plugin/key-policy mutation occurred.
The candidate and default DWT hashes are unchanged and cleanup is clean. The
page-1 PDF remains key-free DRAFT_REFERENCE / MODIFY NONE. The SourceCustody
HMAC/identity-key contract remains fail-closed and unchanged; this iteration
did not remove or bypass any key.

The next action requires fresh SOL review: one bounded offline owner
characterization/causal RED for the startup preload contract, identifying the
smallest existing binding owner that can truthfully establish dispatcher
preloaded and claim-bound readiness. No live retry is authorized until that
offline boundary is reviewed and cleared.

    STATE=CLASSIFIED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-ready-dispatcher-live-preload-boundary-iteration149.md; C:\temp\cad-agent-task6-live-20260911\candidate-activation-dispatcher-live-iteration149-proof.json; source owner mcp_integration_lib/mcp_client.py; base harness C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration116.py; HEAD 2fa3040996d7cf5b33d73ae340516cd31deffbf7
    VERDICT=MATERIAL_FINDING
    FIRST_UNSATISFIED_BOUNDARY=LIVE_STARTUP_DISPATCHER_PRELOADED_CERTIFICATE_FALSE
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize one offline startup-preload owner characterization and causal RED, with no live retry until the truthful claim-bound readiness path is reviewed
    HUMAN_GATE=NO
