# CAD Agent Status
## Canonical checkpoint — AutoCAD discovery/load binding GREEN (iteration 168)
    STATE=OFFLINE_GREEN_VERIFIED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-autocad-discovery-load-binding-green-iteration168.md; parent RED f62e71a3e5c1bab402448a5a6dae5af32ac93f92; existing startup owner now resolves exactly one in-root manifest DLL; focused bundle/startup contracts 7 PASS; ruff/diff-check PASS; no AutoCAD/live/install/registry/env/dispatcher/FileIPC/viewport/source/DXF/CAD/key mutation
    VERDICT=CLEAR_CONTINUE
    MATERIAL_FINDING=NONE_FOR_BUNDLE_ROOT_STARTUP_BINDING
    FIRST_UNSATISFIED_BOUNDARY=TRUTHFUL_AUTOCAD_DISCOVERY_OR_PLUGIN_LOAD_AND_STARTUP_RECEIPT_NOT_PROVEN
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact GREEN; if clear and truthful prerequisites are present, run read-only preflight then at most one disposable live module/startup oracle; otherwise keep LIVE_ORACLE=NOT_RUN and continue with the next approved offline boundary
    HUMAN_GATE=NO

## AutoCAD discovery/load binding GREEN (iteration 168)
- The existing startup factory now accepts an optional disposable bundle root,
  parses exactly one `ComponentEntry`, validates a relative in-root DLL
  `ModuleName`, and forwards that resolved file through the existing direct
  plugin bootstrap owner.
- Focused bundle and startup completion contracts passed: `7 passed in 2.57s`.
  Ruff and `git diff --check` passed.
- This is offline binding evidence only. AutoCAD discovery/plugin load,
  startup receipt, and all downstream live CAD/FileIPC/viewport work remain
  `NOT_RUN`.

## Canonical checkpoint — AutoCAD discovery/load binding causal RED (iteration 167)
    STATE=CAUSAL_RED_CHARACTERIZED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-autocad-discovery-load-binding-causal-red-iteration167.md; parent audit 10dd2dd19869036f6768de858bf8fc8d09366ea9; exact test-only RED; bundle/staging contracts 2 PASS and binding contract 1 intentional RED; ruff/diff-check PASS; no production/live/install/registry/env/dispatcher/FileIPC/viewport/source/DXF/CAD/key mutation
    VERDICT=MATERIAL_FINDING
    MATERIAL_FINDING=AUTOCAD_DISCOVERY_LOAD_OWNER_GAP
    FIRST_UNSATISFIED_BOUNDARY=STAGED_BUNDLE_ROOT_NOT_BOUND_TO_EXISTING_STARTUP_OWNER
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact RED; if clear authorize only the minimal existing startup-owner bundle-root binding and focused GREEN; no live install/launch or downstream dispatcher/FileIPC/viewport/live mutation
    HUMAN_GATE=NO

## AutoCAD discovery/load binding causal RED (iteration 167)
- The test stages a disposable bundle, resolves its manifest-declared DLL,
  and then requires the existing startup factory to accept
  `bootstrap_bundle_path` and bind that exact DLL as its direct
  `bootstrap_plugin_path`/`NETLOAD` target.
- RED is localized at the absent startup-owner binding. Existing bundle and
  packager contracts remain green: `2 passed, 1 failed`; Ruff and diff-check
  passed.
- No production binding or live operation was added. `LIVE_ORACLE=NOT_RUN`.

## Canonical checkpoint — AutoCAD discovery/load owner audit (iteration 166)
    STATE=OFFLINE_DISCOVERY_LOAD_OWNER_AUDITED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-autocad-discovery-load-owner-audit-iteration166.md; exact HEAD 6ce8271221e7a4a027d0edf991e818d58c783220; hosted checks terminal SUCCESS; manifest demand-load, packager staging, startup direct-NETLOAD owner, and tests inspected; no install/launch/registry/env/dispatcher/FileIPC/viewport/live/source/DXF/CAD/key mutation
    VERDICT=MATERIAL_FINDING
    MATERIAL_FINDING=AUTOCAD_DISCOVERY_LOAD_OWNER_GAP
    FIRST_UNSATISFIED_BOUNDARY=STAGED_BUNDLE_ROOT_NOT_BOUND_TO_AUTOCAD_DISCOVERY_OR_DEMAND_LOAD
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact audit; if clear authorize one test-only causal RED for the missing bundle-root-to-startup/discovery binding, otherwise keep LIVE_ORACLE=NOT_RUN; no AutoCAD launch/install or downstream dispatcher/FileIPC/viewport/live mutation
    HUMAN_GATE=NO

## AutoCAD discovery/load owner audit (iteration 166)
- The manifest is demand-loaded (`LoadOnAutoCADStartup=False`,
  `LoadOnCommandInvocation=True`). The packager owns disposable filesystem
  staging only; the startup owner accepts only a direct DLL path and sends
  `_.NETLOAD` after document-ready.
- Existing live tests use the Release DLL directly, and the bundle test does
  not connect its staged bundle root to AutoCAD discovery or command-demand
  loading. The prior bundle availability proof found zero exact installed
  module matches after QNEW-only startup.
- Classification: `AUTOCAD_DISCOVERY_LOAD_OWNER_GAP`; cheapest causal RED is a
  single test-only bundle-root-to-startup/discovery binding contract. No RED or
  live operation was added in this audit; `LIVE_ORACLE=NOT_RUN`.

## Canonical checkpoint — bundle packaging owner GREEN (iteration 165)
    STATE=OFFLINE_GREEN_VERIFIED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-bundle-packaging-owner-green-iteration165.md; parent RED 3dd6e1be3841be68cdbbd99e86a1af904048d981; new owner scripts/package_autocad_bundle.ps1; focused bundle owner + existing contract 2 PASS; ruff and diff-check PASS; no csproj/workflow/AutoCAD/live/dispatcher/FileIPC/viewport/source/DXF/CAD/key mutation
    VERDICT=CLEAR_CONTINUE
    MATERIAL_FINDING=NONE_FOR_BUNDLE_PACKAGING_CONTRACT
    FIRST_UNSATISFIED_BOUNDARY=AUTOCAD_DISCOVERY_PLUGIN_LOAD_AND_STARTUP_RECEIPT_NOT_PROVEN
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact GREEN; if clear and truthful live prerequisites are present, rerun read-only preflight then authorize at most one disposable live module/startup oracle; otherwise keep LIVE_ORACLE=NOT_RUN and continue only with the next approved offline boundary
    HUMAN_GATE=NO

## Bundle packaging owner GREEN (iteration 165)
- The minimal disposable owner `scripts/package_autocad_bundle.ps1` now stages
  the repository manifest and existing Release DLL into the manifest-declared
  `Contents/Windows` path, validates conflicting/missing inputs, and checks
  exact SHA-256 identity.
- Focused GREEN passed for both the new owner contract and the nearest existing
  bundle contract: `2 passed in 0.50s`; Ruff and `git diff --check` passed.
- This proves offline staging only. AutoCAD discovery/plugin load/startup and
  all downstream live CAD/FileIPC/viewport work remain `NOT_RUN`.

## Canonical checkpoint — bundle packaging owner causal RED (iteration 164)
    STATE=CAUSAL_RED_CHARACTERIZED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-bundle-packaging-owner-causal-red-iteration164.md; exact HEAD f5d9a296884a7634e10565bfcdc69bc839ee4a74; test-only contract; existing bundle test 1 PASS and new owner test 1 intentional RED; no production/package/live/CAD/source/DXF/key mutation
    VERDICT=MATERIAL_FINDING
    MATERIAL_FINDING=BUNDLE_PACKAGING_OWNER_GAP
    FIRST_UNSATISFIED_BOUNDARY=DETERMINISTIC_BUNDLE_STAGING_OWNER_ABSENT
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact RED; authorize at most one minimal owner-local packaging implementation only if the contract is accepted, then run focused GREEN; no AutoCAD launch/retry or downstream dispatcher/FileIPC/viewport/live mutation
    HUMAN_GATE=NO

## Bundle packaging owner causal RED (iteration 164)
- One test-only contract now requires the future deterministic owner surface
  `scripts/package_autocad_bundle.ps1` to stage the real Release DLL under
  `CadAgent.bundle/Contents/Windows` with exact bytes/hash and manifest-path
  identity.
- TDD RED is confirmed at the intended missing-owner assertion: focused run
  `1 failed in 0.12s`; nearest existing bundle contract remains green, for a
  combined `1 failed, 1 passed in 0.69s`.
- No owner implementation, generated DLL, AutoCAD/live operation, or
  production/package mutation was performed. `LIVE_ORACLE=NOT_RUN`.

## Canonical checkpoint — bundle packaging owner audit (iteration 163)
    STATE=BUNDLE_PACKAGING_OWNER_AUDITED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-bundle-packaging-owner-audit-iteration163.md; exact HEAD abcfe7dfb0c88e492496eee8b299579f68670b52; PR #424 head matches; base/main e8fc0092ee46750e50de0ea408fd91811cae10c2; hosted checks terminal SUCCESS; manifest present; Release DLL present; bundle Contents/Windows target absent; no packaging/build/bootstrap owner maps Release output into declared bundle target; worktree clean before evidence record; no AutoCAD/live/package/source/DXF/CAD/key mutation
    LIVE_ORACLE=NOT_RUN
    VERDICT=MATERIAL_FINDING
    MATERIAL_FINDING=BUNDLE_PACKAGING_OWNER_GAP
    FIRST_UNSATISFIED_BOUNDARY=DECLARED_BUNDLE_MODULE_NOT_PRODUCED_BY_AN_EXISTING_BUILD_OR_PACKAGING_OWNER
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact audit; authorize at most one minimal owner-local packaging-contract action only if the gap is accepted, otherwise keep LIVE_ORACLE=NOT_RUN and continue with the next approved offline boundary
    HUMAN_GATE=NO

## Bundle packaging owner audit (iteration 163)
- The repository manifest declares `./Contents/Windows/CadAgent.AutoCAD2027.dll`,
  while the Release build emits the DLL only under the project `bin` output.
- No `.csproj`, verifier, hosted workflow, or bootstrap owner stages/copies
  that build output into the declared bundle path. The existing bundle test
  creates only a disposable test bundle and is not a production packaging
  owner.
- The finding is `BUNDLE_PACKAGING_OWNER_GAP`, not an inferred live load result.
  `LIVE_ORACLE=NOT_RUN`; no package repair or AutoCAD operation was attempted.

## Canonical checkpoint — live prerequisite preflight (iteration 162)
    STATE=LIVE_PREREQUISITES_ABSENT
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-live-prerequisite-preflight-iteration162.md; preflight-code-head 139e53db2cf697baf3ba24fbd43b688aaf168c24; local/GitHub main e8fc0092ee46750e50de0ea408fd91811cae10c2; local bridge health 1.0.0 OK; AutoCAD executable exists; AutoCAD process/HWND/document-ready absent; IPC/LISP/disposable-DWG env all unset; bundle-declared plugin DLL absent; no launch/APPLOAD/LISP/FileIPC/viewport/CAD/source/DXF/candidate/key mutation
    LIVE_ORACLE=NOT_RUN
    VERDICT=MATERIAL_FINDING
    FIRST_UNSATISFIED_BOUNDARY=TRUTHFUL_AUTOCAD_PROCESS_HWND_DOCUMENT_AND_PLUGIN_SESSION_NOT_AVAILABLE
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact preflight; if all prerequisites later become truthfully present, rerun only this read-only preflight before any disposable marker oracle; otherwise continue only with the next approved offline boundary
    HUMAN_GATE=NO

## Live prerequisite preflight (iteration 162)
- The local bridge is healthy and the AutoCAD 2027 executable exists, but no
  AutoCAD process/session is present. Consequently process-bound HWND,
  document-ready, loaded-plugin identity, IPC root, and live LISP configuration
  cannot be truthfully observed.
- The Release plugin build exists and its hash is recorded, but the module path
  declared by the repository bundle is absent; a build artifact is not a
  loaded-plugin identity.
- The live oracle is therefore `NOT_RUN`. No readiness repair or AutoCAD launch
  was performed to manufacture a prerequisite.

## Canonical checkpoint — authoritative receipt contract GREEN (iteration 161)
    STATE=OFFLINE_GREEN_VERIFIED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-authoritative-receipt-contract-green-iteration161.md; verified-code-head 19debd00b63dc1483659993280bcd1facc9893ac; focused owner 78 passed + 9 subtests; focused verifier/project contract 17 passed; full scripts/verify.ps1 exit 0 (offline JUnit 3414, receipt contract JUnit 1 pass, C# 238, .NET IPC 134, real-data 2 SKIP, AutoCAD 17 SKIP, live/M2 NOT RUN); no production-after-GREEN/live/transport/dispatcher/FileIPC/viewport/source/DXF/CAD/key mutation
    VERDICT=MATERIAL_FINDING
    FIRST_UNSATISFIED_BOUNDARY=REAL_AUTOCAD_EVALUATOR_RECEIPT_AND_STARTUP_COMPLETION_NOT_PROVEN
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact verified HEAD; if clear, authorize at most one disposable read-only live marker oracle through the existing startup owner, stopping at the first absent/wrong marker and forbidding retry, downstream FileIPC, viewport, source, DXF, or CAD mutation
    HUMAN_GATE=NO

## Authoritative receipt contract GREEN (iteration 161)
- The approved private-owner GREEN now classifies exact marker readback as a
  combined evaluator receipt and keeps receiver-only consumption explicitly
  `NOT_SEPARATELY_OBSERVABLE`.
- The verifier was reconciled from the stale expected-RED contract to a
  passing receipt-contract gate. It checks exact positive classification and
  missing/wrong/unreadable fail-closed behavior with one owner test.
- The full offline/build verification is green. Real AutoCAD causality,
  startup completion, and downstream FileIPC/viewport remain unproven and
  were not invoked by this checkpoint.

## Canonical checkpoint — evaluator receipt causal RED (iteration 160)
    STATE=CAUSAL_RED_CHARACTERIZED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-evaluator-receipt-causal-red-iteration160.md; verified-code-head ee174db267fc23da6570968eea40865c510ea0de; focused normal 91 passed + 1 deselected + 9 subtests; full scripts/verify.ps1 exit 0 (offline JUnit 3414, C# 238, .NET IPC 134, causal RED 1 test/1 intentional failure, real-data 2 SKIP, AutoCAD 17 SKIP, live/M2 NOT RUN); no production/live/transport/dispatcher/FileIPC/viewport/source/DXF/CAD/key mutation
    VERDICT=MATERIAL_FINDING
    FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_EVALUATOR_RECEIPT_CLASSIFICATION_NOT_EXPOSED_BY_CURRENT_PRIVATE_OWNER
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact-head RED; if clear, implement only the minimal private raw-LISP receipt classification in mcp_integration_lib/mcp_client.py and run the focused GREEN, with no transport/dispatcher/FileIPC/viewport/live change
    HUMAN_GATE=NO

## Evaluator receipt causal RED (iteration 160)
- The exact owner-local RED proves the existing missing/wrong marker paths
  remain fail-closed after one raw-LISP trigger with root-safe cleanup.
- The exact marker path is currently RED only because the private owner returns
  legacy bare `True` instead of the approved explicit combined receipt:
  `raw_lisp_evaluator_receipt=CONFIRMED` and
  `receiver_consumption=NOT_SEPARATELY_OBSERVABLE`.
- The authoritative verifier now runs exactly one causal-red test. Full
  verification passes its contract with the intentional RED; no production or
  live mutation is authorized by this checkpoint.

## Canonical checkpoint — AutoCAD evaluator/receiver receipt adapter design (iteration 159)
    STATE=DESIGN_PROPOSED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-autocad-evaluator-receiver-receipt-adapter-design-iteration159.md; exact-head 9d81a09f5f4fe4753fbc444af52412cb2afdfa2c; existing same-expression AutoLISP marker writer/observer selected as supported semantic mechanism; receiver-only ACK absent; no implementation/live/transport/dispatcher/FileIPC/viewport/source/DXF/CAD/key mutation
    VERDICT=MATERIAL_FINDING
    FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_OR_EVALUATOR_RECEIPT_NOT_PROVEN
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact-head design; only if clear may one causal RED be added for a concrete shared-lifecycle gap, with no live retry or transport change
    HUMAN_GATE=NO

## AutoCAD evaluator/receiver receipt adapter design (iteration 159)
- The supported semantic mechanism is the existing same-expression AutoLISP
  marker writer and exact path/token observer in the current raw-LISP owner.
  It proves a combined evaluator receipt when observed; it does not expose the
  internal Windows queue transition separately.
- The contract is one marker, one existing raw-LISP send, bounded exact
  readback, root-safe cleanup, and fail-closed timeout/error behavior. The
  native `PostMessageW` return remains enqueue-only evidence.
- No implementation is authorized by this record. The next step is a fresh
  SOL design review; only a concrete causal RED may unlock the minimal private
  owner/test write-set.

## Canonical checkpoint — receiver-consumption ACK reuse decision (iteration 158)
    STATE=CHARACTERIZED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-receiver-consumption-ack-reuse-decision-iteration158.md; exact-head e66a7d74a78e93dce425049427a6e4b3784cd21f; focused 31 passed + 1 deselected + 3 subtests; scripts/verify.ps1 exit 0 (offline JUnit 3413, C# 238, .NET IPC 134, intentional causal RED 1, real-data 2 SKIP, AutoCAD 17 SKIP, live/M2 NOT RUN); owner/history scan found no production receiver callback/queue-drain/evaluator hook; no production/live/dispatcher/FileIPC/viewport/source/DXF/CAD/key mutation
    VERDICT=MATERIAL_FINDING
    FIRST_UNSATISFIED_BOUNDARY=RECEIVER_CONSUMPTION_ACK_GENUINELY_MISSING_IN_CURRENT_PRODUCTION_OWNER
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this exact-head reuse decision; if accepted, choose one approved semantic boundary and its owner before any production patch or live epoch
    HUMAN_GATE=NO

## Receiver-consumption ACK reuse decision (iteration 158)
- The exact production owners were reread at `e66a7d7`. Raw-LISP and managed
  dispatch both use the existing asynchronous `PostMessageW` enqueue path; no
  production receiver callback, queue-drain result, window-procedure hook, or
  AutoCAD evaluator callback exists at that seam.
- The existing same-expression marker is the smallest supported semantic
  oracle when observed, but it proves combined evaluator receipt rather than a
  receiver-only queue acknowledgement. The claim-bound File IPC result remains
  a downstream operation oracle after dispatcher readiness.
- The causal RED remains intentional and explicit:
  `POSTMESSAGE_ENQUEUED_BUT_RECEIVER_CONSUMPTION_UNOBSERVED`. No production
  patch, transport substitution, or live retry is justified by the inspection.

## Canonical checkpoint — hosted Integration portability repair (iteration 156)
    STATE=OFFLINE_GREEN_HOSTED_REPLAY_PENDING
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-hosted-integration-portability-repair-iteration156.md; exact-head 04877bffc3ae84afc7580c88130c76000257d510; focused 49 passed + 6 subtests; full scripts/verify.ps1 PASS (offline JUnit 3412, C# 238, .NET IPC 134, causal RED 1 expected failure, real-data 2 SKIP, AutoCAD 17 SKIP, live/M2 NOT RUN); git diff --check PASS; no production/key/schema/transport/source/DXF/CAD/candidate mutation
    VERDICT=MATERIAL_FINDING
    FIRST_UNSATISFIED_BOUNDARY=EXACT_HEAD_HOSTED_VERIFICATION_TERMINAL_PASS
    NEXT_SINGLE_BOUNDED_ACTION=Push the clean bounded commit and inspect the exact-head hosted verification check; restart #392 on the resulting exact HEAD
    HUMAN_GATE=NO

## Hosted Integration portability repair (iteration 156)
- The first real hosted Integration boundary was isolated to the verification
  contract: the bundle test ran without its existing Release x64 DLL build
  prerequisite, and two Windows assertions compared short-name and canonical
  path spellings lexically.
- The bounded repair assigns the bundle assertion to a dedicated
  `autocad_bundle` gate: hosted mode records `all-skipped` without the build
  artifact, while the full verifier runs it after the existing .NET build;
  affected path assertions compare resolved identity. Production startup
  behavior is unchanged.
- SourceCustody HMAC/identity-key remains fail-closed and unchanged; page 1
  remains key-free `DRAFT_REFERENCE` / `MODIFY NONE`.

## Canonical checkpoint — evaluator-entry ACK implementation (iteration 155)
    STATE=OFFLINE_GREEN
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-evaluator-entry-ack-implementation-iteration155.md; verified code HEAD dee0758fafd3b9068cbfb37e6ab8974a4a99d0de; focused 52 passed + 6 subtests; scripts/verify.ps1 PASS (offline JUnit 3412, C# 238, .NET IPC 134; causal RED 1 expected failure; real-data 2 SKIP; AutoCAD 17 SKIP; live/M2 NOT RUN); no key/C#/schema/transport/source/DXF/CAD/candidate mutation
    VERDICT=CLEAR_CONTINUE
    FIRST_UNSATISFIED_BOUNDARY=REAL_AUTOCAD_STARTUP_EVALUATOR_ENTRY_AND_COMPLETION_NOT_PROVEN_AFTER_PRIVATE_REPAIR
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of offline GREEN; if clear authorize exactly one disposable read-only live diagnostic through the repaired startup owner, stopping at the first entry/completion boundary and forbidding downstream client/File IPC unless both exact markers are observed
    HUMAN_GATE=NO

## Evaluator-entry ACK implementation (iteration 155)
- The existing startup raw-LISP owner now places a unique fixed-token
  evaluator-entry marker first in the same expression as IPC-root assignment
  and dispatcher load, then waits for exact path/token readback before the
  existing completion marker.
- Missing/wrong/unreadable/timeout entry markers fail closed before completion,
  client, File IPC, or retry; cleanup remains root-validated and no-save.
- Offline GREEN is verified, but real AutoCAD evaluator/marker causality is
  still unproven. Fresh SOL review is required before exactly one live
  diagnostic. SourceCustody HMAC/identity-key remains unchanged and
  fail-closed; page 1 remains key-free `DRAFT_REFERENCE` / `MODIFY NONE`.

## Canonical checkpoint — evaluator-entry ACK reuse decision (iteration 154)
    STATE=DESIGNED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-evaluator-entry-ack-reuse-decision-iteration154.md; mcp_integration_lib/mcp_client.py; mcp_integration_lib/mcp_dispatch.lsp; autocad_plugin/CadAgent.AutoCAD2027/Commands/CadAgentCommands.cs; autocad_plugin/CadAgent.bundle/PackageContents.xml; causal RED 1 failed, 26 deselected; scripts/verify.ps1 PASS (offline JUnit 3410, C# 238, .NET IPC 134; real-data 2 SKIP; AutoCAD 17 SKIP; live/M2 NOT RUN); HEAD fc4683c19f97849eaea995a967ce39645289cd62; no production/live/CAD/DXF/candidate/SourceCustody mutation
    VERDICT=MATERIAL_FINDING
    FIRST_UNSATISFIED_BOUNDARY=REAL_AUTOCAD_EVALUATOR_ENTRY_NOT_PROVEN
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of the existing-marker same-expression seam; authorize implementation only if the exact owner, write-set, fail-closed contract, and live oracle are accepted
    HUMAN_GATE=NO

## Evaluator-entry ACK reuse decision (iteration 154)
- The existing owner scan found no managed AutoCAD evaluator callback,
  receiver hook, or queue-drain ACK. `PostMessageW=True` remains enqueue-only.
- The smallest honest reuse seam is one exact evaluator-entry marker in the
  existing raw-LISP startup expression, observed under the existing IPC root,
  followed by the existing dispatcher completion marker. This is a design
  decision only; no implementation or live retry is authorized yet.
- The SourceCustody HMAC/identity-key contract is unchanged and remains
  fail-closed. The page-1 PDF remains key-free `DRAFT_REFERENCE` / `MODIFY NONE`.

## Canonical checkpoint — startup completion live diagnostic (iteration 153)
    STATE=CLASSIFIED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-startup-completion-live-diagnostic-iteration153.md; proof C:\temp\cad-agent-task6-live-20260911\startup-completion-live-diagnostic-iteration153-proof.json; code HEAD before record df6a1e38b94759566eabd33e87e93d91359d8935; current canonical HEAD 79ccb910fcf251254669f8d5cab801f878796069; exactly one diagnostic epoch; evaluator-entry ACK not proven; no marker/client/File IPC; candidate/DWT unchanged; cleanup clean
    VERDICT=MATERIAL_FINDING
    FIRST_UNSATISFIED_BOUNDARY=REAL_AUTOCAD_EVALUATOR_ENTRY_NOT_PROVEN
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize one bounded next action for the unowned evaluator-entry acknowledgement seam, with no retry and no downstream client/File IPC work
    HUMAN_GATE=NO

## Startup completion live diagnostic (iteration 153)
- The approved live diagnostic reached document-ready and observed one native
  raw-LISP dispatcher-load trigger return, but no evaluator-entry ACK is owned
  by the current path. It stopped before the marker writer and before client
  construction.
- The exact result is EVALUATOR_ENTRY_NOT_PROVEN, not a claim that evaluation
  failed. Candidate/DWT hashes and cleanup stayed clean.
- No live retry, downstream File IPC/drawing-open, or key-policy mutation
  occurred. Fresh SOL review is required for the next bounded action.

## Canonical checkpoint — startup completion oracle (iteration 152)
## Canonical checkpoint — startup completion oracle (iteration 152)
    STATE=OFFLINE_GREEN
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-startup-completion-oracle-iteration152.md; mcp_integration_lib/tests/test_startup_completion_oracle.py; scripts/verify.ps1 offline JUnit 3410 pass, C# 238 pass, DotNet IPC 134 pass, expected causal RED 1 failure, real-data 2 skip, AutoCAD 17 skip, live/M2 NOT RUN; HEAD d7eba568b8d950e3c6713ae122417f7f9cae934c
    VERDICT=CLEAR_CONTINUE
    FIRST_UNSATISFIED_BOUNDARY=REAL_AUTOCAD_STARTUP_COMPLETION_CAUSALITY_NOT_PROVEN
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of the four-state completion oracle; if causal defect is found authorize only the smallest existing-owner repair, otherwise separately authorize one disposable live epoch with no retry
    HUMAN_GATE=NO

## Startup completion oracle (iteration 152)
- The existing startup load expression, marker-writer expression, and Python
  observer were exercised independently across four deterministic cases:
  NOT_EVALUATED, EVALUATED_MARKER_NOT_WRITTEN, MARKER_WRITTEN_NOT_OBSERVED,
  and EVALUATED_AND_OBSERVED. All classifications matched and the public
  timeout remained fail-closed.
- This offline oracle found no production-owner defect and does not identify
  which real AutoCAD stage failed in iteration 151. No live retry followed;
  the next step is SOL review.
- No drawing/source/DXF/CAD/provider/M2 or key-policy mutation occurred. The
  SourceCustody HMAC/identity-key contract remains fail-closed and unchanged.

## Canonical checkpoint — startup preload completion boundary (iteration 151)
## Canonical checkpoint — startup preload completion boundary (iteration 151)
    STATE=CLASSIFIED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-startup-preload-completion-boundary-iteration151.md; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-dispatcher-live-iteration151-proof.json; HEAD 851d9797dfcea52f12acc12dbd1b3f9289719f93; exactly one live epoch; completion marker not confirmed; no client/File IPC/drawing-open; candidate/DWT unchanged; cleanup clean
    VERDICT=MATERIAL_FINDING
    FIRST_UNSATISFIED_BOUNDARY=START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize one offline startup-completion owner characterization and causal RED, with no live retry until completion-marker causality is reviewed
    HUMAN_GATE=NO

## Startup preload completion boundary (iteration 151)
- Supplying the existing dispatcher LISP and IPC-root parameters moved the
  failure to the startup completion-marker boundary:
  START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED.
- The client was never constructed and no File IPC/drawing-open or downstream
  evidence was produced. Candidate/DWT hashes and cleanup remained clean.
- The next step is an offline owner characterization of completion-marker
  writing/evaluation/observation. No live retry or key-policy mutation is
  authorized before fresh SOL review.

## Canonical checkpoint — startup preload contract (iteration 150)
## Canonical checkpoint — startup preload contract (iteration 150)
    STATE=OFFLINE_GREEN
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-startup-preload-contract-iteration150.md; temp RED/GREEN startup owner characterization; commit 0809478af8d1c5b7b6eb78de774aa5745279f160; scripts/verify.ps1 offline JUnit 3406 pass, C# 238 pass, DotNet IPC 134 pass, expected causal RED 1 failure, real-data 2 skip, AutoCAD 17 skip, live/M2 NOT RUN
    VERDICT=CLEAR_CONTINUE
    FIRST_UNSATISFIED_BOUNDARY=LIVE_STARTUP_DISPATCHER_PRELOAD_AND_FILE_IPC_DRAWING_OPEN_NOT_PROVEN
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only live epoch with bootstrap_lisp_path and ipc_root supplied to the startup owner, requiring truthful dispatcher_preloaded and exact File IPC request/result/active-path evidence, with no retry or raw fallback
    HUMAN_GATE=NO

## Startup preload contract (iteration 150)
- The causal RED reproduced plugin-only startup returning
  dispatcher_preloaded=False. The existing startup owner derives truthful
  preload readiness from its own bootstrap_lisp_path/IPC-root contract.
- The bounded GREEN characterization supplied the existing paired parameters
  and proved dispatcher_preloaded=True, bootstrap completion, and a
  claim-bound trigger before client construction. The repository regression
  and authoritative offline gate pass.
- The next live epoch must use that parameter wiring. No live retry, drawing
  mutation, or key-policy change is authorized before fresh SOL review.

## Canonical checkpoint — ready-dispatcher live preload boundary (iteration 149)
## Canonical checkpoint — ready-dispatcher live preload boundary (iteration 149)
    STATE=CLASSIFIED
    EVIDENCE=docs/superpowers/implementation-records/2026-09-12-ready-dispatcher-live-preload-boundary-iteration149.md; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-dispatcher-live-iteration149-proof.json; HEAD 2fa3040996d7cf5b33d73ae340516cd31deffbf7; exactly one disposable live epoch; client binding applied but dispatcher_preloaded=False; raw fallback forbidden; no File IPC request/result; candidate/DWT unchanged; cleanup clean
    VERDICT=MATERIAL_FINDING
    FIRST_UNSATISFIED_BOUNDARY=LIVE_STARTUP_DISPATCHER_PRELOADED_CERTIFICATE_FALSE
    NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize one offline startup-preload owner characterization and causal RED, with no live retry until the truthful claim-bound readiness path is reviewed
    HUMAN_GATE=NO

## Ready-dispatcher live preload boundary (iteration 149)
- The single authorized live epoch reached document_ready=True and called the
  existing binding-application method, but the client remained
  dispatcher_preloaded=False because the startup session was constructed with
  bootstrap_plugin_path only and no bootstrap_lisp_path/IPC-root preload
  contract.
- The harness correctly stopped at the forbidden raw-LISP fallback before any
  semantic File IPC request/result, active-path readback, or candidate/health
  check. Candidate/DWT hashes and cleanup were unchanged/clean.
- The prior wrapper's missing-field default is explicitly not treated as live
  readiness evidence. The next step is offline owner characterization; no
  live retry or key-policy mutation is allowed.

## Canonical checkpoint — ready-dispatcher readiness propagation (iteration 148)
## Canonical checkpoint — ready-dispatcher readiness propagation (iteration 148)
```text
STATE=OFFLINE_GREEN
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-ready-dispatcher-readiness-propagation-iteration148.md; temp RED/GREEN readiness oracle; commit b02586b; focused tests; scripts/verify.ps1 offline JUnit 3405 pass, dotnet IPC 134 pass, expected causal RED 1 failure, real-data 2 skip, AutoCAD 17 skip, live/M2 NOT RUN
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=LIVE_DISPATCHER_FILE_IPC_DRAWING_OPEN_RESULT_NOT_PROVEN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable live epoch through the repaired bootstrap-binding path, requiring exact request/result/active-path evidence and no retry/raw fallback
HUMAN_GATE=NO
```

## Ready-dispatcher readiness propagation (iteration 148)
- The bounded causal RED proved that startup bindings carried
  `dispatcher_preloaded=True` but a newly constructed live client did not.
  Applying the existing `_apply_start_tab_bootstrap_bindings(bindings)` owner
  repaired only that readiness handoff.
- The repaired offline oracle passed and proved one exact read-only semantic
  File IPC `drawing-open` request/result with zero raw-LISP calls. The full
  authoritative verification completed with 3,405 offline tests passing;
  unavailable private/live gates remain explicitly skipped or not run.
- No live retry followed iteration 147. No drawing/source/DXF/CAD/provider/M2
  or key-policy mutation occurred. The SourceCustody HMAC/identity-key
  contract remains fail-closed and unchanged.

## Canonical checkpoint — ready-dispatcher live boundary (iteration 147)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-ready-dispatcher-live-boundary-iteration147.md; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-dispatcher-live-iteration147-proof.json; HEAD 9e5773f53aebae39c75a1bce89d9de6c3748756a
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=DISPATCHER_READY_STATE_NOT_PROPAGATED_TO_LIVE_CLIENT
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize one offline readiness-propagation characterization and causal RED, with no live retry until reviewed
HUMAN_GATE=NO
```

## Ready-dispatcher live boundary (iteration 147)
- Exactly one SOL-authorized disposable read-only epoch reached
  `document_ready=True`, but the direct-binding harness did not propagate the
  startup binding's `dispatcher_preloaded=True` into the new
  `FileIPCLiveMCPClient` instance.
- The client therefore selected raw-LISP; the oracle forbade that fallback and
  stopped at `RAW_LISP_FALLBACK_FORBIDDEN_IN_ITERATION147` before any File IPC
  request/result, active-path readback, candidate identity, or health call.
- Candidate and default DWT hashes were unchanged; cleanup was clean. No live
  retry or production/drawing/key-policy mutation occurred. The next step is
  offline readiness propagation characterization after SOL review.

## Canonical checkpoint — ready-dispatcher drawing-open offline GREEN (iteration 146)
```text
STATE=OFFLINE_GREEN
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-ready-dispatcher-drawing-open-iteration146.md; commit 9c868af7870c18dfd3cc5302a3b7f77e7e227ab9; focused route/owner tests; scripts/verify.ps1 with offline JUnit 3404 pass, dotnet IPC 134 pass, C# 238 pass, expected causal RED 1 failure, real-data 2 skip, AutoCAD 17 skip, live NOT RUN
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=LIVE_FILE_IPC_DRAWING_OPEN_SEMANTIC_RESULT_NOT_PROVEN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable live epoch through the ready claim-bound dispatcher, then stop at the first unsatisfied boundary
HUMAN_GATE=NO
```

## Ready-dispatcher drawing-open offline GREEN (iteration 146)
- The approved offline RED reproduced the defect: with a ready, claim-bound
  dispatcher, `drawing_open(read_only=True)` still entered the raw-LISP ACK path
  and timed out.
- Minimal GREEN now routes that ready path through the existing File IPC
  `drawing-open` result and passes the optional Boolean to the existing
  AutoLISP `vla-Open` owner. Raw-LISP remains the bootstrap/not-ready path;
  timeout, claim, path, cleanup, and no-retry fail-closed rules remain intact.
- Focused and authoritative offline verification passed. The existing raw
  WM_CHAR causal RED remains intentionally failing, live acceptance is still
  `NOT RUN`, and no drawing/source/DXF/CAD/provider/M2 state was changed.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`; the
  authoritative SourceCustody HMAC/identity-key contract remains fail-closed
  and unchanged.

## Canonical checkpoint — receiver/evaluation oracle reuse decision (iteration 145)
```text
STATE=DESIGN_PROPOSED
EVIDENCE=docs/superpowers/specs/2026-09-12-receiver-evaluation-oracle-reuse-decision.md; iteration 144 live proof and docs/superpowers/implementation-records/2026-09-12-live-receiver-observability-boundary-iteration144.md; existing-owner inspection of mcp_client.py, mcp_dispatch.lsp, dotnet_ipc.py, and CadAgent.AutoCAD2027 command/dispatcher owners
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RECEIVER_CONSUMPTION_OBSERVABLE_ABSENT_IN_CURRENT_LIVE_OWNER
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of the reuse decision; if clear authorize the causal RED and only the bounded client/AutoLISP/test write-set in the proposed design
HUMAN_GATE=NO
```

## Receiver/evaluation oracle reuse decision (iteration 145)
- Existing File IPC plus `mcp_dispatch.lsp` already owns a semantic
  `drawing-open` request/result exchange. The measured gap is that live
  `FileIPCLiveMCPClient` bypasses it whenever raw-LISP bootstrap bindings are
  present, and the dispatcher operation does not yet consume `read_only`.
- Proposed next seam: after dispatcher-ready proof, reuse that existing
  claim-bound File IPC operation and result as the evaluator-entry oracle;
  preserve raw-LISP only for bootstrap/not-ready paths. No production mutation,
  live retry, candidate/health, source/DXF/CAD change, or key-policy change is
  authorized before SOL review.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`; the
  authoritative SourceCustody HMAC/identity-key contract remains fail-closed
  and unchanged.

## Canonical checkpoint — live receiver observability boundary (iteration 144)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-live-receiver-observability-boundary-iteration144.md; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-diagnostic-iteration144-proof.json; exactly one authorized disposable live diagnostic; document_ready=True; one raw-LISP callback; 997 WM_CHAR posts to receiver HWND 1377516; all PostMessageW results=1; receiver/evaluator/marker observables NOT_PROVEN because current owner exposes enqueue only; python_ack_observer_read_exact_token=False; failure=MCPTimeoutError: RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED; candidate identity/health NOT RUN; health_call_count=0; cleanup clean; candidate/DWT unchanged; no retry or source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RECEIVER_CONSUMPTION_OBSERVABLE_ABSENT_IN_CURRENT_LIVE_OWNER
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize one bounded design/reuse decision for an approved receiver-side acknowledgement seam or supported evaluation oracle, with no production mutation or live retry until that seam is approved
HUMAN_GATE=NO
```

## Current live receiver observability boundary (iteration 144)
- One live diagnostic confirmed the existing path reaches the raw-LISP callback
  and enqueues all 997 `WM_CHAR` units successfully, but the owner exposes no
  receiver-consumption callback or queue-drain receipt. The marker was not
  observed and the public ACK timeout remained fail-closed.
- Receiver consumption, evaluator entry, and marker-write success remain
  `NOT_PROVEN`, not false. Candidate identity and health remain downstream and
  were not run.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — raw-LISP seam oracle verified (iteration 143)
```text
STATE=VERIFIED_SEAM_ORACLE
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-raw-lisp-four-observable-seam-oracle-iteration143.md; proof C:\temp\cad-agent-task6-live-20260911\raw-lisp-four-observable-seam-oracle-iteration143-proof.json; five deterministic four-observable cases; all_classifications_match=True; all negative cases preserved RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED; positive observer success=True; exact expression/framing reused; cleanup clean; production_files_modified=False; live_epoch_started=False; no production/live/plugin/candidate/health/source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=REAL_AUTOCAD_RECEIVER_CONSUMPTION_AND_EVALUATION_NOT_PROVEN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only live epoch using the four-observable evidence plan, adding only receiver/evaluator/marker/observer diagnostics and stopping at the first boundary; no retry or production/source/DXF/CAD/key-policy mutation
HUMAN_GATE=NO
```

## Current raw-LISP seam boundary (iteration 143)
- Offline evidence now separates receiver non-consumption, consumption without
  evaluator entry, marker-write failure, marker non-observation, and full ACK
  success with four independent observables while preserving the public
  timeout contract.
- The real AutoCAD receiver/evaluator has not been instrumented or proven by
  this offline oracle. No live retry or production change followed it.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — raw-LISP live owner inspection (iteration 142)
```text
STATE=VERIFIED_OWNER_INSPECTION
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-raw-lisp-live-owner-inspection-iteration142.md; proof C:\temp\cad-agent-task6-live-20260911\raw-lisp-live-owner-inspection-iteration142-proof.json; owners and source lines mapped for native receiver/framing, drawing_open ACK expression, AutoCAD evaluator/marker write, Python ACK observation, live harness forwarding, and post-ACK File IPC dispatcher; four-observable offline classification oracle defined; production_files_modified=False; live_epoch_started=False; no production/live/plugin/candidate/health/source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=LIVE_RECEIVER_CONSUMPTION_VS_EVALUATION_VS_MARKER_OBSERVATION_NOT_DISTINGUISHED
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one offline-only receiver/evaluator/observer seam oracle using the four independent observables and exact existing expression/framing, then stop for review
HUMAN_GATE=NO
```

## Current raw-LISP live owner boundary (iteration 142)
- The native receiver/framing owner, expression/marker owner, AutoCAD
  evaluator/marker-write owner, Python ACK observer, live harness forwarding,
  and post-ACK dispatcher boundary are now mapped from the existing sources.
- The timeout remains unassigned among receiver consumption, evaluation,
  marker write, and observation. The next oracle must record those independently
  rather than infer a cause from timeout.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — post-framing live raw-LISP ACK boundary (iteration 141)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-post-framing-live-ack-boundary-iteration141.md; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration141-proof.json; exactly one authorized disposable read-only live epoch; document_ready=True; raw_lisp_ack_returned=False; failure=MCPTimeoutError: RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED; candidate identity/health NOT RUN; health_call_count=0; cleanup warnings=0; AutoCAD PID 22892 absent; candidate SHA-256 unchanged at 167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714; default DWT SHA-256 unchanged at b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42; no retry or source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=LIVE_RAW_LISP_RECEIVER_ACK_NOT_CONFIRMED_AFTER_FULL_EXPRESSION_FRAMING_ORACLE
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize one offline-only inspection of the live receiver/dispatcher ownership and ACK observation seam, without production mutation or another live retry until the owner is identified
HUMAN_GATE=NO
```

## Current post-framing live boundary (iteration 141)
- The repaired foreground path and full-expression offline framing oracle are
  past; the one authorized live epoch still failed at real raw-LISP receiver
  ACK confirmation. Candidate identity and health were not run.
- Cleanup was clean and candidate/DWT hashes were unchanged. No retry or
  source/DXF/CAD mutation occurred.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — full raw-LISP expression framing verified (iteration 140)
```text
STATE=VERIFIED_CAUSAL_ORACLE
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-raw-lisp-full-expression-framing-iteration140.md; proof C:\temp\cad-agent-task6-live-20260911\raw-lisp-full-expression-framing-iteration140-proof.json; actual drawing_open ACK-wrapped expression length 949; 952 UTF-16LE WM_CHAR code units reconstructed byte-for-byte as ESC ESC + expression + CR; marker/token/path/order verified; all positive PostMessageW results=1; injected [1,0] branch returned WINDOW_DELIVERY_FAILED; no dispatch after failure; cleanup clean; production_files_modified=False; live_epoch_started=False; no production/live/plugin/candidate/health/source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=LIVE_RAW_LISP_RECEIVER_CONSUMPTION_OR_EVALUATION_NOT_PROVEN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only live epoch against the same hash-bound page_01.dxf, requiring the existing live raw-LISP receiver ACK and then exact candidate identity plus one health call, with no retry and no visual/dimension/persistence/source/DXF/CAD/key-policy mutation
HUMAN_GATE=NO
```

## Current full-expression framing boundary (iteration 140)
- The actual generated `drawing_open` ACK-wrapped expression survived the
  existing `WM_CHAR`/UTF-16LE text-trigger path byte-for-byte in the offline
  native owner double. The marker/token/path and marker-before-activation
  ordering were preserved.
- A single injected `PostMessageW` failure returned the existing
  `WINDOW_DELIVERY_FAILED` oracle, stopped later delivery, and cleaned up.
- Live receiver consumption/evaluation is the only next live boundary in this
  sequence; the offline oracle does not claim to prove it. The page-1 PDF
  remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`, and the authoritative
  SourceCustody HMAC/identity-key contract was not changed.

## Canonical checkpoint — raw-LISP ACK characterized (iteration 139)
```text
STATE=VERIFIED_CHARACTERIZATION
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-raw-lisp-ack-characterization-iteration139.md; proof C:\temp\cad-agent-task6-live-20260911\raw-lisp-ack-characterization-iteration139-proof.json; production_files_modified=False; live_epoch_started=False; exact callback/marker/order/wait-cleanup characterization; exact WM_CHAR/UTF-16LE framing characterization; direct live-harness forwarding inventory; no production/live/plugin/candidate/health/source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_ACK_CAUSAL_OWNER_NOT_DISTINGUISHED
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one offline-only causal oracle for the cheapest unresolved ACK owner identified by this characterization, preserving the existing public timeout contract and forbidding live retry or production/source/DXF/CAD/key-policy mutation
HUMAN_GATE=NO
```

## Current raw-LISP ACK boundary (iteration 139)
- The existing path was characterized offline: one callback receives the
  generated expression; the exact marker is under the validated IPC root and
  before activation; exact-marker write allows the dispatcher path to proceed,
  while missing-marker returns the existing bounded timeout and cleans up.
- Native framing is `ESC ESC + expression + CR`, sent as UTF-16LE `WM_CHAR`
  units to the one discovered owned receiver. The live harness forwards
  `bindings.raw_lisp_trigger` directly and observes only the ACK sender return.
- The live timeout is not assigned a speculative cause. Receiver
  non-consumption, framing/delivery, marker construction/path, marker write,
  and harness observation remain separate possible owners for the next oracle.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — post-self-attach raw-LISP boundary (iteration 138)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-post-self-attach-live-boundary-iteration138.md; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration138-proof.json; exactly one disposable full live epoch; document_ready=True; raw_lisp_ack_returned=False; failure=MCPTimeoutError: RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED; candidate/health downstream NOT RUN; health_call_count=0; cleanup warnings=0; AutoCAD PID 26444 absent; candidate SHA-256 unchanged at 167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714; default DWT SHA-256 unchanged at b4f8b4ea726bab4b50049f4aa54ba6540f52bd14961f851f49da705cdc292d42; no retry or source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED_AFTER_SELF_ATTACH_REPAIR
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one offline characterization of the existing raw-LISP receiver ACK path and its disposable harness, with no production mutation, live retry, plugin/candidate/health, visual/dimension, source/DXF/CAD, or key-policy mutation until the characterization is reviewed
HUMAN_GATE=NO
```

## Current post-self-attach live boundary (iteration 138)
- The repaired foreground path was not the blocking boundary in this epoch:
  AutoCAD reached `document_ready=True`, then the existing raw-LISP receiver
  did not confirm its required same-expression ACK.
- The run stopped before downstream candidate identity and health assertions;
  there was no retry, no production/source/DXF/CAD mutation, and cleanup was
  clean. Candidate and default DWT hashes were unchanged.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — self-attach repair verified (iteration 137)
```text
STATE=VERIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-self-attach-repair-iteration137.md; pushed code commit 8cc9bcf; focused Windows-trigger 26 passed/1 deselected/3 subtests; DotNetIPC 82 passed/52 subtests; Ruff passed; scripts/verify.ps1 exit 0; .NET 238 passed; offline Python 3322 passed/21 deselected/80 subtests; offline JUnit tests=3402 failures=0 errors=0 skipped=0; causal-red 1 expected failure; real-data 2 skipped; AutoCAD 17 skipped; live marker/M2 NOT RUN; git diff --check clean; worktree clean; no live retry or source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_SELF_ATTACH_REPAIR_LIVE_FOREGROUND_HANDOFF_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only live epoch against the same hash-bound page_01.dxf, requiring foreground handoff, existing plugin/bootstrap, same-expression raw-LISP ACK, exact active-document identity, one health call, and no-save cleanup; stop at the first causal failure
HUMAN_GATE=NO
```

## Current self-attach boundary (iteration 137)
- The production foreground helper now treats equal caller and foreground
  thread IDs as `attach_not_required`: it skips the invalid self-attach and
  detach calls, then preserves the existing ShowWindow, single
  SetForegroundWindow, and exact-HWND readback sequence.
- The new causal regression proves no AttachThreadInput calls occur for the
  equal-thread case. Existing different-thread coverage and all authoritative
  offline gates remain green.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — native AttachThreadInput failure (iteration 136)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-native-attach-failure-iteration136.md; proof C:\temp\cad-agent-task6-live-20260911\foreground-native-outcome-diagnostic-iteration136-proof.json; exactly one authorized disposable native-outcome diagnostic; document_ready=True; foreign precondition verified HWND 3540730/PID 26992/thread 14952; owned target HWND 9045722/PID 21928/thread 24944; caller_thread_id=14952; foreground_thread_id=14952; AttachThreadInput attach_result=0; stage=ATTACH_FAILED; ShowWindow/SetForegroundWindow/detach NOT CALLED; production helper invoked once; plugin/raw-LISP/candidate/health NOT RUN; cleanup clean; DWT unchanged; no source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=ATTACH_THREAD_INPUT_ATTACH_RESULT_FALSE
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and authorization for one smallest offline TDD repair or diagnostic addressing the AttachThreadInput attach-result failure while preserving the exact-HWND fail-closed contract; no live retry, plugin/raw-LISP/candidate/health, or source/DXF/CAD mutation until authorized
HUMAN_GATE=NO
```

## Current native boundary (iteration 136)
- The benign foreign precondition was proven with exact HWND readback. The
  unchanged production helper then called once with owned AutoCAD target
  `9045722` / PID `21928` / thread `24944`; caller thread `14952` and
  foreground thread `14952` were captured.
- `AttachThreadInput(..., attach=True)` returned `0`, producing
  `ATTACH_FAILED`. Therefore `ShowWindow`, `SetForegroundWindow`, and detach
  did not run; the public error remained `WINDOW_FOREGROUND_INVALID`.
- No plugin/raw-LISP/candidate/health path was entered. Cleanup was clean and
  candidate/PDF/source/DXF/CAD/key-policy state was untouched. The page-1 PDF
  remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`; the authoritative
  SourceCustody HMAC/identity-key contract was not removed or bypassed.

## Canonical checkpoint — harness fail-closed branch repaired (iteration 135)
```text
STATE=VERIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-harness-fail-closed-branch-repair-iteration135.md; disposable harness tests 4 passed; stale foreign_verified absent; syntax check passed; production foreground helper unchanged; no live rerun, plugin/raw-LISP/candidate/health, or source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_HARNESS_FAIL_CLOSED_BRANCH_REPAIR_LIVE_NATIVE_OUTCOME_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only native-outcome diagnostic with repaired harness, verified benign foreign HWND/PID foreground first, then invoke unchanged production helper exactly once and capture all native outcomes; stop immediately afterward
HUMAN_GATE=NO
```

## Current harness boundary (iteration 135)
- The stale fail-closed reference was replaced with the bounded precondition
  result. A focused spy regression proves `verified=False` returns without
  invoking the production helper.
- Four offline harness tests pass, including pointer-width `DefWindowProcW`
  signatures and exact/non-exact precondition gating. Production foreground
  behavior remains unchanged; no live retry followed the repair.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — repaired harness live precondition failure (iteration 134)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-repaired-harness-live-precondition-failure-iteration134.md; proof C:\temp\cad-agent-task6-live-20260911\foreground-native-outcome-diagnostic-iteration134-proof.json; exactly one authorized disposable diagnostic; document_ready=True; owned target=HWND 1181088/PID 14728/thread 5700; benign target=HWND 919106/PID 27836/thread 20716; benign SetForegroundWindow result=0; foreign_precondition_verified=False; production helper NOT INVOKED; harness NameError=foreign_verified; plugin/raw-LISP/candidate/health NOT RUN; cleanup clean; DWT unchanged; no source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=DISPOSABLE_HARNESS_FAIL_CLOSED_BRANCH_REFERENCES_STALE_FOREIGN_VERIFIED_NAME
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and authorization for one offline-only disposable harness repair replacing the stale branch variable with the bounded precondition result, plus focused regression; no live retry, production repair, plugin/raw-LISP/candidate/health, or source/DXF/CAD mutation until authorized
HUMAN_GATE=NO
```

## Current repaired-harness boundary (iteration 134)
- The benign window still did not become foreground (`SetForegroundWindow=0`,
  exact readback false), so the production helper was correctly not invoked.
  The harness then raised `NameError: foreign_verified is not defined` in its
  fail-closed branch because that branch still referenced the old variable
  name after the bounded routine was introduced.
- This is isolated to the disposable harness. Cleanup was clean, AutoCAD/PID
  and stage roots were absent, and the default DWT hash was unchanged. No
  production helper, plugin, raw-LISP, candidate, health, PDF, DXF, CAD, or
  key-policy path was touched.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — disposable harness repair verified (iteration 133)
```text
STATE=VERIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-disposable-harness-repair-iteration133.md; disposable harness tests 3 passed; DefWindowProcW pointer-width signature verified; bounded foreign precondition gate verified for exact and non-exact readback; production foreground helper unchanged; no live rerun, plugin/raw-LISP/candidate/health, or source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_DISPOSABLE_HARNESS_REPAIR_LIVE_NATIVE_OUTCOME_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only native-outcome diagnostic with the repaired harness, verified benign foreign HWND/PID foreground first, then invoke unchanged production helper exactly once and capture all native outcomes; stop immediately afterward
HUMAN_GATE=NO
```

## Current disposable harness boundary (iteration 133)
- The iteration-132 harness-only defect is repaired: `DefWindowProcW` now has
  pointer-width-safe argument and return signatures, and the foreign-window
  setup is a bounded routine that proves exact foreground readback before the
  production helper may run.
- Focused offline harness tests: `3 passed`. No production foreground behavior
  changed and no live retry was run after the repair.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — benign foreign-window precondition boundary (iteration 132)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-benign-foreign-window-precondition-boundary-iteration132.md; proof C:\temp\cad-agent-task6-live-20260911\foreground-native-outcome-diagnostic-iteration132-proof.json; exactly one authorized disposable native-outcome diagnostic; document_ready=True; owned target=HWND 722044/PID 28764/thread 22612; benign target=HWND 787684/PID 28852/thread 22856; benign SetForegroundWindow result=0; foreign_precondition_verified=False; production helper NOT INVOKED; plugin/raw-LISP/candidate/health NOT RUN; cleanup clean; DWT unchanged; no source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=FOREIGN_FOREGROUND_PRECONDITION_SETFOREGROUNDWINDOW_FAILED_IN_DISPOSABLE_HARNESS
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and authorization to repair the disposable benign-window callback/signature, re-establish and verify the foreign foreground precondition, then invoke the unchanged production helper exactly once; no production behavioral repair or full live epoch until authorized
HUMAN_GATE=NO
```

## Current benign-window diagnostic boundary (iteration 132)
- The diagnostic reached `document_ready=True` and created a separate benign
  window owned by the harness, but `SetForegroundWindow` returned `0` and the
  foreground remained another window. The production foreground helper was
  therefore not invoked, so no native handoff outcomes were captured.
- The disposable window callback emitted an `OverflowError` from an incomplete
  `DefWindowProcW` signature. This is isolated to the diagnostic harness; no
  production code, plugin, raw-LISP, candidate, PDF, DXF, or CAD state changed.
- Cleanup was clean, the owned AutoCAD PID and stage root were absent, and the
  default DWT hash was unchanged. The page-1 PDF remains key-free
  `DRAFT_REFERENCE` with `MODIFY NONE`; the authoritative SourceCustody
  HMAC/identity-key contract was not removed or bypassed.

## Canonical checkpoint — native-outcome diagnostic precondition (iteration 131)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-native-outcome-diagnostic-precondition-iteration131.md; proof C:\temp\cad-agent-task6-live-20260911\foreground-native-outcome-diagnostic-iteration131-proof.json; exactly one authorized disposable live foreground/native-outcome diagnostic; document_ready=True; target=HWND 1115332/PID 21416/thread 23412; foreground_before=HWND 1115332/PID 21416/thread 23412; foreground_after=HWND 1115332/PID 21416/thread 23412; helper returned without handoff; native calls only GetForegroundWindow; attach/ShowWindow/SetForegroundWindow/detach outcomes NOT OBSERVED; plugin/raw-LISP/candidate/health NOT RUN; cleanup clean; DWT unchanged; no source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=FOREGROUND_HANDOFF_NATIVE_OUTCOME_NOT_OBSERVED_BECAUSE_TARGET_ALREADY_FOREGROUND
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and authorization for one bounded disposable diagnostic that establishes a foreign foreground precondition before invoking the instrumented helper, then captures native outcomes; no behavioral repair, full epoch, plugin/raw-LISP/candidate/health, or source/DXF/CAD mutation until authorized
HUMAN_GATE=NO
```

## Current native diagnostic boundary (iteration 131)
- The authorized diagnostic reached `document_ready=True`, but the owned
  AutoCAD HWND was already the exact foreground window before the helper ran.
  The helper therefore returned at its early exact-match guard; no
  `AttachThreadInput`, `ShowWindow`, `SetForegroundWindow`, or detach call was
  attempted, so their native return values remain unobserved.
- Target and foreground snapshots were identical before and after the helper;
  cleanup was clean, the owned PID and disposable stage root were absent, and
  the default DWT hash was unchanged. The diagnostic did not enter any plugin,
  raw-LISP, candidate, health, visual, or dimension path.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — native outcome instrumentation verified (iteration 130)
```text
STATE=VERIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-native-outcome-instrumentation-iteration130.md; pushed code commit bcbb88b; focused Windows-trigger 25 passed/1 deselected/3 subtests; DotNetIPC 82 passed/52 subtests; Ruff passed; scripts/verify.ps1 exit 0; .NET 238 passed; offline Python 3321 passed/21 deselected/80 subtests; offline JUnit tests=3401 failures=0 errors=0 skipped=0; causal-red 1 expected failure; real-data 2 skipped; AutoCAD 17 skipped; live marker/M2 NOT RUN; git diff --check clean; worktree clean; no live retry or source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_NATIVE_OUTCOME_INSTRUMENTATION_LIVE_REVIEW_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of the verified native-outcome evidence; await authorization for any live rerun and do not retry the full epoch or mutate source/DXF/CAD/key policy until authorized
HUMAN_GATE=NO
```

## Current native-outcome boundary (iteration 130)
- The diagnostic now captures target HWND/PID, caller and foreground thread
  IDs, raw attach/detach results, ShowWindow result, and
  SetForegroundWindow result while preserving the existing stage taxonomy and
  public `WINDOW_FOREGROUND_INVALID` failure contract.
- The focused regression proves these fields on the exact-readback-mismatch
  branch. Authoritative verification is green. No live rerun followed the
  instrumentation, so the native outcome for the existing live mismatch is
  still not directly observed with the new fields.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — post-foreground diagnostic live boundary (iteration 129)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-post-foreground-diagnostic-live-boundary-iteration129.md; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration129-proof.json; exactly one authorized disposable full live epoch; failure=MCPToolError: WINDOW_FOREGROUND_INVALID; internal_stage=EXACT_HWND_READBACK_MISMATCH; foreground_before=HWND 4786026/PID 14048; foreground_after_set=HWND 4786026/PID 14048; foreground_after_detach=HWND 4786026/PID 14048; candidate_open_call_count=0; raw_lisp_ack_returned=False; health_call_count=0; cleanup warnings=none; PID/IPC/scripts cleaned; candidate and DWT unchanged; no source/DXF/CAD/key-policy mutation
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=EXACT_HWND_READBACK_MISMATCH_DURING_PLUGIN_BOOTSTRAP_TRIGGER
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and authorization for one smallest bounded foreground handoff repair or diagnostic addressing the exact readback mismatch; do not retry the full epoch, invoke raw-LISP/candidate/health, or mutate source/DXF/CAD until authorized
HUMAN_GATE=NO
```

## Current live boundary (iteration 129)
- The single authorized full epoch reached the existing plugin/bootstrap
  boundary, then failed closed before any command delivery because the
  instrumented foreground helper observed the same foreign HWND `4786026` / PID
  `14048` before and after the handoff attempt. The internal stage was
  `EXACT_HWND_READBACK_MISMATCH` and the public error remained
  `WINDOW_FOREGROUND_INVALID`.
- No candidate open, raw-LISP ACK, active-document identity, or health result
  was obtained. Cleanup was clean, the owned AutoCAD PID and disposable IPC/
  script roots were absent, and candidate/DWT hashes were unchanged.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — live foreground diagnostic (iteration 128)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-live-foreground-diagnostic-iteration128.md; proof C:\temp\cad-agent-task6-live-20260911\foreground-stage-diagnostic-iteration128-proof.json; one disposable live diagnostic; document_ready=True; foreground_handoff_succeeded=True; owned HWND=1246720/PID=26208; plugin_bootstrap_invoked=False; raw_lisp_invoked=False; runtime_bootstrap_invoked=False; cleanup_clean=True; PID absent; stage root absent; default DWT unchanged; no candidate/PDF/source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_FOREGROUND_DIAGNOSTIC_PLUGIN_BOOTSTRAP_AND_RAW_LISP_ACK_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; if clear authorize exactly one disposable read-only live epoch through the existing plugin/bootstrap and raw-LISP ACK path, with exact candidate identity and one health call, then no-save cleanup; stop at the first causal failure and do not infer visual/dimension acceptance
HUMAN_GATE=NO
```

## Current live diagnostic boundary (iteration 128)
- One disposable AutoCAD session reached `document_ready=True`; the
  instrumented foreground helper succeeded for owned HWND `1246720` (PID
  `26208`). The session was closed without save, the owned PID and stage root
  were absent afterward, and the default DWT hash was unchanged.
- This diagnostic intentionally stopped immediately after the foreground
  result. It did not bootstrap the plugin, invoke raw-LISP, open the candidate,
  call health, or inspect visual/dimension fidelity.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — foreground-stage instrumentation (iteration 127)
```text
STATE=VERIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-foreground-stage-instrumentation-iteration127.md; pushed code commit 0e18218; focused Windows-trigger 24 passed/1 deselected/3 subtests; DotNetIPC 82 passed/52 subtests; Ruff passed; scripts/verify.ps1 completed; offline JUnit tests=3400 failures=0 errors=0 skipped=0; causal-red tests=1 failures=1 expected; real-data tests=2 skipped; AutoCAD tests=17 skipped; live marker/M2 NOT RUN; git diff --check clean; worktree clean; no live rerun or source/DXF/CAD/key-policy mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_FOREGROUND_STAGE_INSTRUMENTATION_LIVE_DIAGNOSTIC_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review, then if clear run exactly one disposable read-only live diagnostic or live epoch with the internal foreground stage exposed in proof; do not infer raw-LISP ACK, candidate identity, health, visual fidelity, or dimensions and do not mutate source/DXF/CAD
HUMAN_GATE=NO
```

## Current foreground-stage boundary (iteration 127)
- The foreground helper now preserves the public `WINDOW_FOREGROUND_INVALID`
  error while exposing a bounded internal stage and before/after foreground
  HWND/PID snapshots for `ATTACH_FAILED`, `SHOW_OR_SET_NATIVE_ERROR`,
  `EXACT_HWND_READBACK_MISMATCH`, and `DETACH_FAILED`.
- Focused Windows-trigger tests cover each diagnostic branch and prove that the
  public failure contract remains unchanged. The authoritative verification
  completed cleanly; no live retry was made after iteration 126.
- The page-1 PDF remains key-free `DRAFT_REFERENCE` with `MODIFY NONE`. The
  authoritative SourceCustody HMAC/identity-key contract was not removed,
  bypassed, or otherwise changed.

## Canonical checkpoint — post-kernel32 live boundary (iteration 126)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-post-kernel32-live-boundary-iteration126.md; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration126-proof.json; document-ready=True; failure=MCPToolError: WINDOW_FOREGROUND_INVALID after corrected kernel32 binding; candidate_open_call_count=0; raw_lisp_ack_returned=False; health_call_count=0; cleanup warnings=none; PID/IPC/scripts cleaned; candidate and DWT hashes unchanged
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=WINDOW_FOREGROUND_INVALID_AFTER_KERNEL32_FOREGROUND_HANDOFF
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and one smallest bounded foreground diagnostic or repair preserving the exact-HWND fail-closed contract; do not retry candidate activation, invoke plugin bootstrap, call health, or mutate source/DXF/CAD until authorized
HUMAN_GATE=NO
```

## Current live boundary (iteration 126)
- The corrected `kernel32.GetCurrentThreadId` binding was reached, but the
  repaired foreground owner still failed closed at exact foreground readback
  with `WINDOW_FOREGROUND_INVALID`.
- No plugin bootstrap, raw-LISP, FileIPC, candidate open, active-document
  identity, or health call was made. Cleanup and candidate/DWT integrity stayed
  clean.
- The key-free page-1 `DRAFT_REFERENCE` policy remains `MODIFY NONE`; the
  authoritative SourceCustody HMAC contract was not changed or bypassed.

## Canonical checkpoint — kernel32 binding correction (iteration 125)
```text
STATE=VERIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-kernel32-binding-correction-iteration125.md; pushed code commit 8967722f6a502d7a4a31b28ddbba30e88879bbff; focused Windows-trigger 23 passed/1 deselected/3 subtests; DotNetIPC 82 passed/52 subtests; Ruff passed; scripts/verify.ps1 exit 0; .NET 238 passed; offline Python 3319 passed/21 deselected/80 subtests; offline JUnit tests=3399 failures=0 errors=0 skipped=0; causal-red 1 expected failure; real-data 2 skipped; AutoCAD 17 skipped; live marker/M2 NOT RUN; clean tree; no live rerun or source/DXF/CAD mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_KERNEL32_BINDING_LIVE_FOREGROUND_HANDOFF_AND_RAW_LISP_ACK_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review, then if clear run exactly one disposable read-only live epoch against the same hash-bound page_01.dxf with the corrected owner; require exact foreground handoff, same-expression ACK before activation, exact active-document identity, one health call, no-save cleanup, and stop at first causal failure
HUMAN_GATE=NO
```

## Current live boundary (iteration 125)
- The narrow native binding defect from iteration 124 is corrected: the helper
  uses `kernel32.GetCurrentThreadId`, while all window APIs remain on `user32`.
- Offline focused and authoritative verification is green. No live epoch has
  run after this correction, so foreground handoff, raw-LISP ACK, candidate
  identity, health, visual fidelity, and dimensions remain unproven.
- No plugin/raw-LISP/FileIPC/source/DXF/CAD/key-policy mutation occurred. The
  key-free page-1 `DRAFT_REFERENCE` policy remains `MODIFY NONE`; SourceCustody
  HMAC remains unchanged.

## Canonical checkpoint — post-handoff live boundary (iteration 124)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-post-handoff-live-boundary-iteration124.md; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration124-proof.json; document-ready=True; failure=AttributeError: function 'GetCurrentThreadId' not found; candidate_open_call_count=0; raw_lisp_ack_returned=False; health_call_count=0; cleanup warnings=none; PID/IPC/scripts cleaned; candidate and DWT hashes unchanged
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=GETCURRENTTHREADID_BOUND_TO_WRONG_WIN32_DLL
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and authorization for one offline TDD correction that obtains GetCurrentThreadId from kernel32 while keeping user32 AttachThreadInput/ShowWindow/SetForegroundWindow, exact-HWND fail-closed readback, and no live retry until offline verification passes
HUMAN_GATE=NO
```

## Current live boundary (iteration 124)
- The one authorized post-repair epoch reached document-ready, then exposed a
  production binding defect before plugin bootstrap: `GetCurrentThreadId` was
  looked up on `user32` instead of `kernel32`.
- No raw-LISP, FileIPC, candidate open, active-document identity, or health
  result was obtained. Cleanup and candidate/DWT integrity remained clean.
- The key-free page-1 `DRAFT_REFERENCE` policy remains `MODIFY NONE`; the
  authoritative SourceCustody HMAC contract was not changed or bypassed.

## Canonical checkpoint — foreground handoff repair (iteration 123)
```text
STATE=VERIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-foreground-handoff-repair-iteration123.md; pushed code commit f4b2b6012af289afc14f4d2dd55bbcd0b8ebbc19; focused Windows-trigger 23 passed/1 deselected/3 subtests; DotNetIPC 82 passed/52 subtests; Ruff passed; scripts/verify.ps1 exit 0; .NET 238 passed; offline Python 3319 passed/21 deselected/80 subtests; offline JUnit tests=3399 failures=0 errors=0 skipped=0; causal-red 1 expected failure; real-data 2 skipped; AutoCAD 17 skipped; live marker/M2 NOT RUN; clean tree; no live rerun or source/DXF/CAD mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_REPAIR_LIVE_FOREGROUND_HANDOFF_AND_RAW_LISP_ACK_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review, then if clear run exactly one disposable read-only live epoch with the repaired foreground owner against the same hash-bound page_01.dxf; stop at first causal failure and do not infer visual/dimension success
HUMAN_GATE=NO
```

## Current live boundary (iteration 123)
- The Windows foreground owner now performs one bounded
  `AttachThreadInput` handoff around the existing `ShowWindow` plus
  `SetForegroundWindow` sequence, always detaching and preserving exact-HWND
  fail-closed readback.
- Offline focused and authoritative verification passed. No live epoch has
  run after the repair, so live foreground handoff, raw-LISP ACK, candidate
  identity, health, visual fidelity, and dimensions remain unproven.
- No plugin/raw-LISP/FileIPC/source/DXF/CAD/key-policy mutation occurred. The
  key-free page-1 `DRAFT_REFERENCE` policy remains `MODIFY NONE`; SourceCustody
  HMAC remains unchanged.

## Canonical checkpoint — foreground reacquisition diagnostic (iteration 122)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-foreground-reacquisition-diagnostic-iteration122.md; proof C:\temp\cad-agent-task6-live-20260911\foreground-reacquisition-diagnostic-iteration122-proof.json; document-ready=True; owned AutoCAD HWND=1771118/PID=8740; initial foreground HWND=591914/PID=3208/class=Chrome_WidgetWin_1/title=ChatGPT; one ShowWindow returned true; one SetForegroundWindow returned false; ten post-attempt samples remained ChatGPT; classification=FOREGROUND_REACQUIRE_DENIED; plugin/raw-LISP/FileIPC/candidate/health not invoked; PID/scripts cleaned; candidate unchanged
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=FOREGROUND_REACQUIRE_DENIED_DURING_BOOTSTRAP
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and one smallest bounded session-level foreground repair or diagnostic preserving the fail-closed exact-HWND guard; do not retry candidate activation, invoke plugin bootstrap, call health, or mutate source/DXF/CAD until authorized
HUMAN_GATE=NO
```

## Current live boundary (iteration 122)
- AutoCAD reached document-ready, but the existing one-shot foreground
  reacquisition could not move focus from the ChatGPT window to the owned
  AutoCAD top-level HWND: `SetForegroundWindow` returned `false` and all ten
  bounded samples stayed on ChatGPT.
- No plugin bootstrap, command delivery, raw-LISP, FileIPC, candidate open, or
  health call was made. The candidate remained unchanged; owned cleanup left no
  acad.exe.
- Cleanup emitted `START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED`, recorded as a
  secondary warning; the owned PID was absent after the bounded cleanup check.
- The key-free page-1 `DRAFT_REFERENCE` policy remains `MODIFY NONE`; the
  authoritative SourceCustody HMAC contract was not changed or bypassed.

## Canonical checkpoint — foreground identity diagnostic (iteration 121)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-foreground-identity-diagnostic-iteration121.md; proof C:\temp\cad-agent-task6-live-20260911\foreground-identity-diagnostic-iteration121-proof.json; document-ready=True; owned AutoCAD HWND=5048306/PID=13480; foreground HWND=2819782/PID=1428; class/title=#32770 / RYME Worldwide; classification=FOREIGN_PROCESS_STOLE_FOREGROUND; plugin/raw-LISP/FileIPC/candidate/health not invoked; PID/scripts cleaned; candidate unchanged
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=FOREIGN_PROCESS_STOLE_FOREGROUND_DURING_BOOTSTRAP
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of iteration 121 and one bounded foreground/bootstrap corrective or diagnostic action; do not retry candidate activation, call health, invoke SetForegroundWindow, or mutate source/DXF/CAD until authorized
HUMAN_GATE=NO
```

## Current live boundary (iteration 121)
- The read-only diagnostic reached document-ready, then found a different
  process owning the foreground window while AutoCAD's owned top-level window
  was not foreground.
- No plugin bootstrap, raw-LISP, FileIPC, candidate open, or health call was
  made. The candidate remained unchanged; owned cleanup left no acad.exe.
- Cleanup emitted `START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED`, recorded as a
  warning; the owned PID was absent after the bounded cleanup check.
- The key-free page-1 `DRAFT_REFERENCE` policy remains `MODIFY NONE`; the
  authoritative SourceCustody HMAC contract was not changed or bypassed.

## Canonical checkpoint — post-harness live foreground boundary (iteration 120)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-post-harness-live-foreground-boundary-iteration120.md; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration120-proof.json; document-ready=True; WINDOW_FOREGROUND_INVALID during plugin bootstrap; candidate_open_call_count=0; health_call_count=0; PID/IPC/scripts cleaned; candidate and DWT hashes unchanged
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=WINDOW_FOREGROUND_INVALID_DURING_PLUGIN_BOOTSTRAP
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review and one bounded foreground/bootstrap diagnostic or corrective action; do not retry candidate activation, call health, or mutate source/DXF/CAD until authorized
HUMAN_GATE=NO
```

## Current live boundary (iteration 120)
- The corrected harness was used, but plugin bootstrap failed the existing
  foreground guard before candidate activation.
- The post-repair ACK placement, candidate active identity, and health remain
  unproven; no candidate/source/DXF/CAD mutation occurred.
- Cleanup and hash integrity checks passed.

## Canonical checkpoint — disposable harness ACK forwarding repair (iteration 119)
```text
STATE=VERIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-harness-ack-forwarding-repair-iteration119.md; disposable harness callback repair; harness-ack-forwarding-regression-iteration119.py output `harness ack forwarding: PASS`; production tree unchanged from pushed HEAD 6ab0f89ea81a07352454893b0eb10239cba4d9e7
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_HARNESS_REPAIR_LIVE_RAW_LISP_ACK_AND_CANDIDATE_ACTIVE_IDENTITY_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Run exactly one new disposable read-only live epoch against the same hash-bound page_01.dxf using the corrected harness: same-expression ACK before activation -> exact active-document identity -> one DotNetIPCClient.health(candidate_path) -> no-save cleanup; stop at first causal failure and do not retry or mutate source/DXF/CAD
HUMAN_GATE=NO
```

## Current live boundary (iteration 119)
- The disposable harness now forwards the current `ack_before` owner keyword
  and its focused regression passed.
- Production code remains the iteration-117 placement repair; no live result
  has been obtained after correcting the harness.
- The next action is exactly one valid disposable read-only epoch, with no
  retry after its first causal failure.

## Canonical checkpoint — post-repair live harness boundary (iteration 118)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-post-repair-live-harness-boundary-iteration118.md; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration118-proof.json; document-ready=True; harness TypeError occurred before production raw-LISP sender; production expression not sent; health_call_count=0; PID absent after cleanup; candidate and DWT hashes unchanged
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=DISPOSABLE_HARNESS_ACK_WRAPPER_SIGNATURE_MISMATCH
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review; repair only the disposable harness callback signature offline, then await explicit authorization before any new live epoch; do not infer ACK, candidate identity, health, visual, or dimension success
HUMAN_GATE=NO
```

## Current live boundary (iteration 118)
- The post-repair epoch did not reach the production raw-LISP sender because
  the disposable observation wrapper rejected the new `ack_before` keyword.
- No ACK, candidate active identity, or health result was observed; cleanup
  and candidate/DWT integrity checks passed.
- This harness-only failure does not invalidate the offline placement repair;
  a new live epoch requires fresh bounded authorization after the harness is
  corrected.

## Canonical checkpoint — raw-LISP ACK placement repair (iteration 117)
```text
STATE=IMPLEMENTED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-raw-lisp-ack-placement-repair-iteration117.md; pushed executor HEAD 7a1d85688d7d4eb21ca8f6e80c43ec78ccac5b42; pre-change RED 1 failed/5 passed; focused ACK/fallback 46 passed with 6 subtests; full scripts/verify.ps1 exit 0; .NET 238 passed; offline Python 3315 passed with 21 deselected and 80 subtests; offline JUnit tests=3395 failures=0 errors=0 skipped=0; causal-red 1 expected failure; real-data 2 skipped; AutoCAD 17 skipped; no live rerun or source/DXF/CAD mutation
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=POST_REPAIR_LIVE_RAW_LISP_ACK_AND_CANDIDATE_ACTIVE_IDENTITY_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of the placement repair and authoritative verification; only after clear review may one exact disposable read-only live epoch rerun against the hash-bound page_01.dxf, with same-expression ACK before activation, one health call, and no-save cleanup
HUMAN_GATE=NO
```

## Current live boundary (iteration 117)
- The ACK writer is now placed before activation in the same owner-built
  expression, with causal and focused regression coverage.
- Authoritative offline verification is green; the exact post-repair live
  ACK, candidate identity, and health result have not yet been rerun.
- No candidate/source/DXF/CAD mutation occurred, and the key-free page-1
  `DRAFT_REFERENCE` policy remains `MODIFY NONE`.

## Canonical checkpoint — live candidate activation ACK boundary (iteration 116)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-live-candidate-activation-ack-boundary-iteration116.md; proof C:\temp\cad-agent-task6-live-20260911\candidate-activation-iteration116-proof.json; AutoCAD document-ready=True; drawing_open call count=1; RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED; health_call_count=0; PID absent after cleanup; candidate and DWT hashes unchanged
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_EVALUATION_ACK_NOT_CONFIRMED
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of iteration 116; keep candidate, source, DXF, and production code unchanged until a bounded corrective or diagnostic action is authorized; do not retry the live epoch or infer candidate/health/visual success
HUMAN_GATE=NO
```

## Current live boundary (iteration 116)
- The authorized live epoch reached AutoCAD document-ready and invoked the
  exact candidate `drawing_open` once, but the same-expression raw-LISP ACK
  was not confirmed.
- The epoch stopped before `DotNetIPCClient.health`; candidate active identity
  and downstream visual/dimension fidelity remain unproven.
- The owned process and disposable roots were cleaned without warnings, and
  candidate/DWT hashes remained unchanged.

## Canonical checkpoint — live prerequisite recheck (iteration 115)
```text
STATE=WAIT_SAFE
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-live-prerequisite-recheck-iteration115.md; prior pushed HEAD b08816e3c9c587a199c3a78f2dc7d0e5d65608b7; fresh read-only recheck found no acad.exe and all six live prerequisites absent; LiveEpochStarted=False
VERDICT=SKIP_LIVE_PREREQUISITES_UNAVAILABLE
FIRST_UNSATISFIED_BOUNDARY=LIVE_ACCEPTANCE_PREREQUISITES_ABSENT
NEXT_SINGLE_BOUNDED_ACTION=Remain WAIT_SAFE; at the next natural checkpoint recheck the same prerequisites only; if all become available run exactly one previously authorized disposable read-only epoch against the hash-bound page_01.dxf, otherwise retain SKIP/NOT_RUN; do not retry partially or mutate source/DXF/CAD
HUMAN_GATE=NO
```

## Current live boundary (iteration 115)
- SOL reviewed iteration 114 as `CLEAR_CONTINUE` and confirmed the key-free
  draft policy with `MODIFY NONE`.
- The fresh prerequisite recheck again found no AutoCAD process and no live
  prerequisites, so the single live epoch remains `SKIP/NOT RUN`.
- No raw-LISP, FileIPC, AutoCAD, source/DXF/CAD, retry, or cleanup mutation
  occurred.

## Canonical checkpoint — live acceptance prerequisite classification (iteration 114)
```text
STATE=CLASSIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-live-acceptance-prerequisite-classification-iteration114.md; exact candidate C:\temp\cad-agent-real-pdf-current-main-iter80-run\staged\dxf\page_01.dxf with SHA256 167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714; read-only preflight found no acad.exe and all six live prerequisites absent; LiveEpochStarted=False
VERDICT=SKIP_LIVE_PREREQUISITES_UNAVAILABLE
FIRST_UNSATISFIED_BOUNDARY=LIVE_ACCEPTANCE_PREREQUISITES_ABSENT
NEXT_SINGLE_BOUNDED_ACTION=Remain WAIT_SAFE and consume fresh SOL review; if all prerequisites become available, rerun one exact disposable read-only epoch, otherwise retain SKIP/NOT_RUN and do not infer candidate or visual success
HUMAN_GATE=NO
```

## Current live boundary (iteration 114)
- The exact frozen page-1 candidate is identified and hash-bound, but the
  disposable live acceptance epoch was not started because no AutoCAD process
  or required live prerequisites were present.
- Live raw-LISP receiver ACK, candidate active-document identity, and
  `DotNetIPCClient.health` remain `NOT_PROVEN`; no PASS or failure is inferred.
- No FileIPC, AutoCAD, source/DXF/CAD, retry, or cleanup mutation occurred.

## Canonical checkpoint — WAIT_SAFE live-oracle preflight (iteration 113)
```text
STATE=WAIT_SAFE
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-wait-safe-live-oracle-preflight-iteration113.md; iteration-112 authoritative offline verification at 2d78ca1; read-only live preflight found no AutoCAD process and all six live-oracle prerequisites absent; LiveOracleExecuted=False
VERDICT=WAITING_FOR_SOL_REVIEW_WITH_LIVE_PREREQUISITES_UNAVAILABLE
FIRST_UNSATISFIED_BOUNDARY=FRESH_SOL_REVIEW_AFTER_AUTHORITATIVE_OFFLINE_VERIFY
NEXT_SINGLE_BOUNDED_ACTION=Consume the fresh SOL verdict; if clear, recheck prerequisites and run the one read-only live oracle only if its prerequisites become available, otherwise record SKIP/NOT_RUN
HUMAN_GATE=NO
```

## WAIT_SAFE preparation (iteration 113)
- No AutoCAD process or live-oracle prerequisites are present in this session;
  the live gate remains `SKIP`/`NOT RUN`.
- No FileIPC request, candidate activation, health call, AutoCAD interaction,
  source/DXF/CAD mutation, or production mutation occurred while waiting for
  SOL.

## Canonical checkpoint — authoritative raw-LISP ACK verification (iteration 112)
```text
STATE=VERIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-authoritative-verification-raw-lisp-ack-iteration112.md; scripts/verify.ps1 completed at feb1d07; .NET 238 passed; offline Python 3313 passed, 21 deselected, 80 subtests; offline JUnit tests=3393 failures=0 errors=0 skipped=0; causal-red 1 expected failure; real-data 2 skipped; AutoCAD unavailable 17 skipped; git diff --check clean; tracked tree clean
VERDICT=PASS_WITH_RECORDED_UNAVAILABLE_LIVE_GATES
FIRST_UNSATISFIED_BOUNDARY=LIVE_RAW_LISP_RECEIVER_ACK_AND_CANDIDATE_ACTIVE_IDENTITY_NOT_RUN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of this authoritative offline verification; only after clear review may one separately authorized read-only live acceptance epoch run, with no source/DXF/CAD mutation
HUMAN_GATE=NO
```

## Current authoritative raw-LISP ACK verification (iteration 112)
- The full offline gate is green at `feb1d07`: .NET 238, offline Python 3313,
  offline JUnit 3393, with the intentional causal-red and unavailable live
  gates recorded separately rather than promoted to PASS.
- Claimed/live `drawing_open` still requires the same-expression exact marker;
  legacy enqueue-only behavior is confined to unclaimed offline fixture mode.
- Live receiver ACK and candidate active-document identity remain unproven
  until a separately reviewed read-only AutoCAD epoch. No live or source/DXF/
  CAD mutation occurred.

## Canonical checkpoint — raw-LISP ACK legacy-fixture compatibility (iteration 111)
```text
STATE=IMPLEMENTED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-raw-lisp-ack-legacy-fixture-compatibility-iteration111.md; focused ACK/opening 44 passed; phase-4 compatibility 6 passed; Windows-trigger non-causal-red 19 passed; iteration-110 full verify exposed exactly six legacy-fixture failures
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=AUTHORITATIVE_FULL_VERIFY_AFTER_LEGACY_FIXTURE_COMPATIBILITY_REPAIR
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of the legacy_fixture_mode compatibility repair, then rerun clean-tree scripts/verify.ps1; no live acceptance epoch yet
HUMAN_GATE=NO
```

## Current raw-LISP ACK compatibility boundary (iteration 111)
- The same-expression exact marker ACK is mandatory for the claimed/live raw
  LISP opening path and remains separate from active-document identity and
  managed dispatcher success.
- The pre-existing `legacy_fixture_mode` distinction is preserved for
  unclaimed offline fixtures; it does not affect the live CLI path, whose
  dispatch trigger is claim-bound.
- No live AutoCAD epoch, candidate activation, health/FileIPC, source/DXF/CAD,
  or authoritative custody-policy mutation occurred.

## Canonical checkpoint — raw-LISP consumption ACK implementation (iteration 110)
```text
STATE=IMPLEMENTED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-raw-lisp-consumption-ack-implementation-iteration110.md; focused ACK/opening tests 44 passed; Windows-trigger regression 19 passed excluding intentional causal-red; ruff passed; git diff --check passed
VERDICT=CLEAR_CONTINUE
FIRST_UNSATISFIED_BOUNDARY=AUTHORITATIVE_FULL_VERIFY_AFTER_ACK_IMPLEMENTATION
NEXT_SINGLE_BOUNDED_ACTION=Run clean-tree scripts/verify.ps1; stop after offline verification and do not run the live acceptance epoch yet
HUMAN_GATE=NO
```

## Current raw-LISP consumption ACK implementation (iteration 110)
- The existing raw-LISP/opening owner now requires an exact receiver/evaluation
  marker before `drawing_open` proceeds to independent dispatcher and active
  document verification.
- The low-level Windows trigger remains enqueue-only; no second transport,
  managed open/activate subsystem, C# schema/dispatcher change, or implicit
  raw-LISP retry was added.
- The marker is request-owned, fixed-token, same-expression, bounded, and
  cleaned on terminal paths. Missing or wrong marker is fail-closed and never
  claims receiver success.
- The implementation write set is limited to `mcp_client.py`, focused opening
  tests, and this evidence/status documentation. No live AutoCAD, candidate,
  health/FileIPC, source/DXF/CAD, or authoritative custody-policy mutation
  occurred.

## Canonical checkpoint — raw-LISP consumption ACK design (iteration 109)
```text
STATE=DESIGNED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-raw-lisp-consumption-ack-design-iteration109.md; current low-level owner _make_windows_text_trigger/make_windows_lisp_trigger; existing causal-red enqueue-TRUE/ACK-absent oracle; existing marker writer/observer reuse; full verify at 78c09fb exit 0 with intentional causal-red recorded
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_EVALUATION_ACK_ABSENT_IN_CURRENT_OWNER
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of the same-expression marker ACK design and exact write set; no implementation, live retry, candidate activation, health/FileIPC, production/source/DXF/CAD mutation until explicitly authorized
HUMAN_GATE=NO
```

## Current raw-LISP consumption ACK design (iteration 109)
- The low-level Windows trigger remains enqueue-only. The smallest proposed
  seam is a private wrapper at the existing known-expression opening owner:
  append the existing fixed-token marker writer as the final form of the same
  `progn`, send once through the existing raw-LISP trigger, and accept terminal
  consumed/evaluated evidence only after exact marker/path readback within the
  existing bound.
- The design deliberately does not change the trigger return type, add a
  second transport, add managed `drawing_open`/`candidate_activate`, or claim
  that marker readback alone proves the business operation. Existing exact
  active-document readback and managed health remain separate identity/result
  checks.
- TDD outputs are defined as `EXACT_WRITE_SET`, `RED_TEST`,
  `GREEN_CONTRACT`, `REGRESSION_GATE`, and `LIVE_ACCEPTANCE_ORACLE` in the
  iteration-109 record. The future write set is limited to the Python opening
  owner, its focused tests, and documentation; actual decision write set is
  `MODIFY NONE / CREATE NONE`.
- No implementation, live retry, candidate activation, health/FileIPC call,
  production code, source, candidate, DXF, or CAD mutation occurred. Exact
  evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-12-raw-lisp-consumption-ack-design-iteration109.md`.

## Canonical checkpoint — authoritative verification from clean tree (iteration 108)
```text
STATE=VERIFIED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-authoritative-verification-clean-tree-iteration108.md; scripts/verify.ps1 exit 0; .NET 238 passed, 0 failed, 0 skipped; offline Python 3309 passed, 21 deselected, 80 subtests passed; offline JUnit tests=3389 failures=0 errors=0 skipped=0; git diff --check clean; tracked tree clean
VERDICT=PASS_WITH_RECORDED_UNAVAILABLE_LIVE_GATES
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_CONSUMPTION_ACK_ABSENT_IN_CURRENT_OWNER
NEXT_SINGLE_BOUNDED_ACTION=Send clean-tree verification and current raw-LISP boundary to SOL for fresh review; preserve key-free PDF DRAFT_REFERENCE and keep live retry, candidate activation, and production/source/DXF/CAD mutation stopped until separately authorized
HUMAN_GATE=NO
```

## Current authoritative verification from clean tree (iteration 108)
- The local Git disposition is resolved without changing the report: the
  pre-existing CadMind experiment report remains outside Git through local
  `.git/info/exclude`, preserving its contents and keeping private/generated
  artifact references out of the repository.
- `scripts/verify.ps1` completed successfully at commit
  `78c09fbeaf359d1e1720bfe79ccd9a7757bed5f2`: .NET `238 passed`, offline
  Python `3309 passed`, `80 subtests passed`; `git diff --check` and tracked
  worktree cleanliness were confirmed afterward.
- The intentional causal-red test remains a documented negative oracle
  (`1 failed, 19 deselected`) and is not claimed as a product pass. Private
  real-data and AutoCAD live gates remain explicitly `SKIP`/`NOT RUN` because
  their prerequisites are unavailable. The raw-LISP receiver-consumption ACK
  remains the first unsatisfied boundary. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-12-authoritative-verification-clean-tree-iteration108.md`.

## Canonical checkpoint — managed candidate-activation owner decision (iteration 107)
```text
STATE=EXECUTED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-candidate-activation-managed-owner-decision-iteration107.md; fresh raw opening-owner tests 5 passed, 35 deselected; fresh managed active-document identity tests passed 2, failed 0; current HEAD before record 73225159b72dfc92d50fb2a69605a892be34e508
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=MANAGED_CANDIDATE_OPEN_ACTIVATE_OPERATION_ABSENT
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of iteration 107; preserve key-free PDF DRAFT_REFERENCE and keep live candidate activation, health/FileIPC, raw-LISP retry, and production mutation stopped until a separate bounded action is authorized
HUMAN_GATE=NO
```

## Current managed candidate-activation owner decision (iteration 107)
- The current managed dispatcher has no `drawing_open` or
  `candidate_activate` operation. Its `health(candidate_path)` operation only
  confirms that the requested path is already the active document; it cannot
  open or activate it. `IDrawingGateway` exposes no open/activate capability.
- The existing opening owner remains
  `FileIPCLiveMCPClient.drawing_open`: raw-LISP VLA lookup/open/activate,
  guarded Start-tab `_.OPEN` fallback, dispatcher readiness, and exact active
  path readback. This owner split is proven by focused tests: 5 Python opening
  tests and 2 managed identity tests passed.
- A managed replacement would be a behavior/contract change spanning the
  dispatcher operation schema, `OperationDispatcher`, drawing gateway,
  client wrapper, and lifecycle/identity tests. No such change was made;
  `MODIFY NONE / CREATE NONE` remains the write set for this decision.
- A future live discriminator may compose the existing read-only open owner
  with `DotNetIPCClient.health(candidate_path)`, but it is not authorized here.
  No candidate activation, health/FileIPC call, raw-LISP retry, production,
  source, candidate, DXF, or CAD mutation occurred. Exact evidence is recorded
  in `docs/superpowers/implementation-records/2026-09-12-candidate-activation-managed-owner-decision-iteration107.md`.

## Verification gate attempt — pre-existing untracked report (iteration 106)
```text
STATE=EXECUTED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-verification-gate-preexisting-report-iteration106.md; scripts/verify.ps1 stopped before test gates on pre-existing ?? docs/reports/2026-09-11-cadmind-page1-experiment-report.md; focused checks remain 3 passed and 5 passed
VERDICT=NOT_RUN
FIRST_UNSATISFIED_BOUNDARY=VERIFY_REQUIRES_CLEAN_TREE_DUE_TO_PREEXISTING_UNTRACKED_REPORT
NEXT_SINGLE_BOUNDED_ACTION=Preserve the untracked report and rerun scripts/verify.ps1 after its Git disposition is resolved; continue only the SOL-authorized read-only page-1 work in parallel
HUMAN_GATE=NO
```

The authoritative verification gate did not begin because the workspace had a
pre-existing untracked report. The report was preserved and not staged,
deleted, or modified. No pass is claimed; exact evidence is recorded in
`docs/superpowers/implementation-records/2026-09-12-verification-gate-preexisting-report-iteration106.md`.

## Canonical checkpoint — key-free PDF DRAFT_REFERENCE decision (iteration 105)
```text
STATE=DECISION_COMPLETE
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-key-free-draft-policy-decision-iteration105.md; SOL fresh review of canonical main=e8fc0092ee46750e50de0ea408fd91811cae10c2; executor HEAD=e08a589ddb0ddd7ad21e08a572c8859d512911c3; focused PDF policy/custody tests 5 passed, 232 deselected
VERDICT=REQUEST_SATISFIED_WITH_MODIFY_NONE
FIRST_UNSATISFIED_BOUNDARY=NONE_FOR_DRAFT_REFERENCE_KEY_POLICY
NEXT_SINGLE_BOUNDED_ACTION=Preserve the key-free PDF DRAFT_REFERENCE path and continue page-1 acceptance from the raw-LISP receiver-consumption boundary; do not route through authoritative SourceCustody/SourceFusion and do not perform live retry, code, source, DXF, or CAD mutation until the next bounded action is authorized
HUMAN_GATE=NO
```

## Current key-free PDF DRAFT_REFERENCE decision (iteration 105)
- SOL confirmed from fresh canonical `main` that PDF `DRAFT_REFERENCE`
  creation/resume already has no approved-root or identity-key prerequisite.
  No key bytes were read, changed, or removed.
- The authoritative SourceCustody contract intentionally remains fail-closed
  with its HMAC identity scheme and key revision. Removing that requirement
  would be a separate governance/contract change, not part of the requested
  page-1 draft workflow.
- The request is therefore satisfied with `MODIFY NONE`. The active project
  frontier remains the measured raw-LISP receiver-consumption boundary. Exact
  SOL decision evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-12-key-free-draft-policy-decision-iteration105.md`.

## Canonical checkpoint — semantic result owner and key-free draft disposition (iteration 104)
```text
STATE=EXECUTED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-semantic-result-owner-reuse-gate-iteration104.md; current-head focused owner tests 3 passed, 79 deselected; PDF policy/custody tests 5 passed, 232 deselected; prior live semantic-health proof iteration 76
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_CONSUMPTION_ACK_ABSENT_IN_CURRENT_OWNER; AUTHORITATIVE_SOURCE_CUSTODY_KEYLESS_PROMOTION_REMAINS_REJECTED_BY_DESIGN
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of iteration 104; keep raw-LISP retry, live health/FileIPC, candidate activation, authoritative key removal, and production mutation stopped until the next bounded action is authorized
HUMAN_GATE=NO
```

## Current semantic result owner and key-free DRAFT_REFERENCE disposition (iteration 104)
- The smallest reusable semantic result owner is the existing managed
  `DotNetIPCClient.request/health` -> `CADAGENT_DISPATCH` -> `JsonFileStore`
  request/result path. Its exact matching result gives a bounded terminal
  success or failure at the command/result boundary; `PostMessageW=True` alone
  remains enqueue-only evidence.
- Fresh focused owner tests passed `3 passed, 79 deselected`. Fresh PDF
  policy/custody tests passed `5 passed, 232 deselected`. No live operation was
  repeated in this offline characterization; iteration 76 remains the prior
  live proof of the existing semantic-health owner.
- The owner's requested key is the source-integrity `identity-key` requirement,
  not an API key stored in the repository. The PDF page-1 `DRAFT_REFERENCE`
  lane already runs without approved-root or identity-key custody. No key
  removal is required for that draft workflow.
- Authoritative `source-custody-1.0`/source-fusion remains fail-closed on
  `READY` custody. Removing its identity-key requirement would be a separate
  behavior-changing security/design decision. The raw-LISP receiver ACK is
  still absent, and no live retry, health/FileIPC call, candidate activation,
  production code, source, or DXF mutation was performed. Exact evidence is in
  `docs/superpowers/implementation-records/2026-09-12-semantic-result-owner-reuse-gate-iteration104.md`.

## Canonical checkpoint — raw-LISP delivery-path characterization (iteration 103)
```text
STATE=EXECUTED
EVIDENCE=docs/superpowers/implementation-records/2026-09-12-raw-lisp-delivery-path-causal-characterization-iteration103.md; reviewed HEAD 8eb2bbe4bdab88ff03444fbb6a8d7a34fe551630; focused owner/framing tests 5 passed, 15 deselected; causal-red 1 failed, 19 deselected as expected; historical iteration-63/64 evidence
VERDICT=MATERIAL_FINDING
FIRST_UNSATISFIED_BOUNDARY=RAW_LISP_RECEIVER_CONSUMPTION_ACK_ABSENT_IN_CURRENT_OWNER
NEXT_SINGLE_BOUNDED_ACTION=Fresh SOL review of iteration 103; keep live retry, candidate activation, health, FileIPC, and production mutation stopped until the next bounded action is authorized
HUMAN_GATE=NO
```

## Current raw-LISP delivery-path causal characterization (iteration 103)
- Fresh SOL review required one offline, reuse-only characterization of the
  current `_make_windows_text_trigger` / `make_windows_lisp_trigger` owner.
  The owner selects exactly one visible owned `MDIClient`, rechecks PID and
  top-level foreground identity, and posts `WM_CHAR` (`0x0102`) code units for
  UTF-16LE `ESC ESC + expression + CR`. The final `CR` is only a `WM_CHAR`
  `U+000D`; no separate `VK_RETURN` key sequence is sent.
- Focused owner/framing/receiver tests passed `5 passed, 15 deselected`. The
  marked causal-red test remained the expected failure (`1 failed, 19
  deselected`): native `PostMessageW=TRUE` can coexist with modeled receiver
  consumption false. The owner has no receiver callback, queue-drain result,
  or AutoLISP evaluation result.
- Historical evidence shows a visible owned `MDIClient` distinct from the
  actual focused child (iteration 63), while sending the same 299-code-unit
  framing directly to that focused child still produced no marker (iteration
  64). Iteration 102 likewise returned from one current-owner trigger with no
  exact marker or `post_qnew_entry` event. A simple target swap is therefore
  not a sufficient explanation.
- The existing observables can expose a target/control mismatch, verify the
  intended outgoing framing, or prove evaluation when the exact stage marker
  appears. They cannot distinguish `WRONG_RECEIVER_OR_CONTROL`,
  `FRAME_OR_TERMINATOR_NOT_CONSUMED`, and `RECEIVER_ACCEPTED_BUT_AUTOLISP_NOT_EVALUATED`
  in a live three-way result. The first causal gap remains
  `RAW_LISP_RECEIVER_CONSUMPTION_ACK=ABSENT_IN_CURRENT_OWNER`; no production
  change or live retry is justified. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-12-raw-lisp-delivery-path-causal-characterization-iteration103.md`.

## Current raw-LISP consumption oracle (iteration 102)
- Fresh SOL review authorized exactly one disposable live read-only epoch using
  the executor-branch owner, verified DWT, `CADAGENT_DISPATCH` startup, and the
  existing bounded document-ready wait. `DOCUMENT_READY=PROVEN` on owned HWND
  `1902374` / PID `10580`.
- Exactly one existing `post_qnew_entry` stage-marker raw-LISP expression was
  triggered. The trigger returned without an exception, but the exact fixed
  token `CAD_AGENT_START_TAB_POST_QNEW_ENTRY` was not observed within the
  existing 60-second bound and the existing timing observer did not record the
  `post_qnew_entry` event. Classification is
  `RAW_LISP_CONSUMPTION=NOT_PROVEN`; trigger return is enqueue-path evidence,
  not receiver/evaluation acknowledgement.
- Candidate activation, health, FileIPC, setup, persistence, focus workaround,
  retry, timeout/code change, and CAD/source/DXF mutation were not run. Cleanup
  had no warnings; PID, temporary bundle, script, and marker were absent and
  the verified DWT SHA was unchanged. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-12-raw-lisp-consumption-oracle-iteration102.md`
  and the disposable proof under
  `C:\temp\cad-agent-task6-live-20260911\raw-lisp-consumption-iteration102\`.
- The first unsatisfied boundary remains receiver consumption. Candidate
  activation stays downstream pending fresh SOL review; no retry or production
  mutation is authorized by this result.

## Current raw-LISP command-consumption characterization (iteration 99)
- Fresh SOL review required characterization of the existing
  `make_windows_lisp_trigger` / `_make_windows_text_trigger` boundary.
  `PostMessageW=True` and a trigger return prove only native enqueue-path
  success, not AutoCAD receiver consumption or AutoLISP evaluation. The
  intentional `causal_red` test demonstrates this distinction; its positive
  receiver ACK is only a test-double model.
- The smallest existing semantic oracle is the exact temporary stage-marker
  writer/observer: `_start_tab_stage_marker_expression` writes a fixed token
  outside the CAD drawing and `_observe_stage_markers` records the exact
  `post_qnew_entry` event. Exact token readback proves that marker expression
  was consumed/evaluated. The completion marker is a larger bootstrap-coupled
  oracle; health/FileIPC is downstream.
- This oracle is CAD-side-effect-free but writes one disposable evidence file.
  If all filesystem side effects are disallowed, no side-effect-free semantic
  command-consumption oracle exists in the current owner.
- Future placement is one disposable epoch after bounded document-ready and
  before candidate/health/FileIPC: one existing `post_qnew_entry` marker
  trigger, exact-token wait, then cleanup. `PostMessageW=True` without that
  marker remains `RAW_LISP_CONSUMPTION=NOT_PROVEN`. No live retry, code change,
  or CAD/source/DXF mutation occurred. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-12-raw-lisp-command-consumption-characterization-iteration99.md`.

## Current raw-LISP foreground oracle (iteration 98)
- Fresh SOL review authorized exactly one disposable live read-only oracle
  around one existing raw-LISP trigger. The existing bounded document-ready
  wait passed on owned HWND `1312424` / PID `4356`.
- Three read-only foreground samples immediately before/during/after the
  trigger all showed the same foreground HWND/PID as the owner; process
  identity was `acad.exe` at the approved AutoCAD 2027 path. The trigger ran
  exactly once and returned without an exception, but its return is not an
  execution/receiver ACK.
- Per SOL's restricted classification, this epoch is
  `FOREGROUND_BOUNDARY_UNRESOLVED`: it did not reproduce
  `WINDOW_FOREGROUND_INVALID`, but it also does not prove command consumption
  or resolve the prior epoch's failure permanently. Candidate, health, FileIPC,
  setup, persistence, and CAD/source/DXF mutation were `NOT_RUN`/untouched.
- Cleanup completed without warnings; owned PID, temporary bundle, and script
  were absent and the DWT SHA was unchanged. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-12-foreground-oracle-iteration98.md`.

## Current raw-LISP foreground guard characterization (iteration 96)
- Fresh SOL review required one offline characterization of the existing
  `make_windows_lisp_trigger` owner. Its exact foreground predicate is
  `GetForegroundWindow() == hwnd`, after one optional `ShowWindow(hwnd, 9)` /
  `SetForegroundWindow(hwnd)` attempt, and again before every `PostMessageW`
  character enqueue. PID ownership and exactly one visible owned `MDIClient`
  are separate guards.
- Iteration 95 had `DOCUMENT_READY=PROVEN` on owned HWND `460582` / PID `1748`,
  then failed with `WINDOW_FOREGROUND_INVALID`; no foreground identity was
  captured at the guard readback and no `PostMessageW` delivery or health call
  occurred. The evidence therefore cannot distinguish an actually non-
  foreground owner from a foreground race/false negative.
- Historical iterations 61/62/73 provide respectively a point-in-time
  matching foreground observation, a trigger-time trace with no marker
  consumption, and the same guard failure before delivery. Focused offline
  guard tests passed (`8 passed, 12 deselected, 3 subtests passed`); the full
  module's one failure is the intentional `causal_red` receiver-ACK test, not
  a foreground failure.
- Cheapest future read-only oracle is one high-frequency foreground
  HWND/PID/process/title trace around the existing single raw-LISP trigger,
  classified only as `OWNED_HWND_NOT_FOREGROUND` versus
  `FOREGROUND_GUARD_FALSE_NEGATIVE_OR_RACE`. No live retry, workaround,
  production-code change, or CAD/source/DXF mutation occurred. Exact evidence
  is recorded in
  `docs/superpowers/implementation-records/2026-09-12-foreground-guard-characterization-iteration96.md`.

## Current-main exact page-1 candidate-activation discriminator (iteration 95)
- Fresh SOL review authorized exactly one live, read-only candidate-activation
  discriminator epoch using the executor-branch owner, verified DWT, and
  `CADAGENT_DISPATCH` startup. The existing bounded document-ready wait
  reached `DOCUMENT_READY=PROVEN`.
- The existing raw-LISP open/activate trigger then failed closed with
  `MCPToolError: WINDOW_FOREGROUND_INVALID`. The request was not delivered,
  so the single `DotNetIPCClient.health(drawing_full_path=None)` call was not
  reached (`health_call_count=0`). Candidate activation remains
  `NOT_PROVEN`; no candidate-content conclusion is justified.
- FileIPC bootstrap load/ping, setup audit, persistence, retry, timeout/code
  change, and CAD/source/DXF mutation were all `NOT_RUN`. Cleanup removed the
  owned PID, temporary bundle, startup script, and health request/result pair;
  candidate/DWT hashes were unchanged. Normal close confirmation timed out,
  but exact-PID fallback cleanup succeeded.
- Classification is `LIVE_EPOCH=FAIL_CLOSED`,
  `DOCUMENT_READY=PROVEN`, `CANDIDATE_ACTIVATION=NOT_PROVEN`, and
  `DISCRIMINATOR_HEALTH=NOT_RUN`. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-12-real-pdf-candidate-activation-discriminator-iteration95.md`.

## Current-main exact page-1 startup discriminator with bounded wait (iteration 94)
- Fresh SOL review authorized one live read-only startup discriminator using
  the executor-branch owner, verified DWT, and `CADAGENT_DISPATCH` startup
  pattern. The existing bounded `_wait_for_document_ready` observed the owned
  window at `14.391s` and a `document_ready_transition` at `27.031s`.
- `DOCUMENT_READY=PROVEN` within the existing 60-second bound. The timeout
  raw-title branch was not entered, so no candidate activation, health,
  FileIPC, or setup operation ran.
- The runner exited `1` only for normal close confirmation timeout; exact PID
  fallback cleanup succeeded. Bundle/script were removed and candidate/DWT
  hashes were unchanged. Classification is
  `STARTUP_DISCRIMINATOR=PASS`, `CLEANUP=SAFE_WITH_CLOSE_WARNING`, and
  `SETUP_READBACK=NOT_RUN`. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-12-real-pdf-startup-discriminator-iteration94.md`.

## Current-main document-ready probe characterization (iteration 93)
- Fresh SOL review of iteration 92 required one offline characterization of
  the startup readiness predicate. Canonical `origin/main` at
  `e8fc0092ee46750e50de0ea408fd91811cae10c2` does not contain the executor
  branch's `WindowsAutoCADStartTabSession`, document-ready probe, timing
  recorder, or title-reader symbols; the iteration-76/90/92 live epochs
  exercised the executor-branch owner instead.
- On that branch, readiness is title-only: the owned HWND title is read with
  `GetWindowTextLengthW`/`GetWindowTextW`; `[start]` means not ready and any
  non-empty non-`[start]` title means ready. Probe exceptions and missing
  titles collapse to false inside the bounded polling loop.
- Iterations 76 and 90 recorded `document_ready_observed=true`; iteration 92
  found an owned HWND but recorded false. None of the private proofs captured
  raw title samples, title API outcomes, poll counts, or timing events, so the
  distinction between persistent Start-tab and title-reader false negative is
  not proven.
- The cheapest future read-only discriminator is the existing raw title reader
  on the exact owned HWND at timeout plus existing timing events: `[start]`
  supports `AUTOCAD_WINDOW_PRESENT_BUT_DOCUMENT_NOT_READY`, a non-empty
  non-`[start]` sample with a false Boolean supports
  `DOCUMENT_READY_PROBE_FALSE_NEGATIVE_OR_RACE`, and an empty/missing title
  remains unresolved. No live retry, code change, or CAD/source/DXF mutation
  occurred. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-document-ready-probe-characterization-iteration93.md`.
- Focused offline branch tests passed: `40 tests, OK`.

## Current-main exact page-1 drawing-open discriminator live epoch (iteration 92)
- Fresh SOL review authorized one read-only discriminator epoch using the
  verified DWT plus the demand-load `CADAGENT_DISPATCH` bootstrap pattern.
- The owned AutoCAD session reached a window handle, but the existing
  runner made one immediate document-ready probe call after window discovery;
  that one sample returned false, but the runner did not invoke the existing
  bounded `_wait_for_document_ready` owner. Therefore iteration 92 did not
  prove a bounded timeout and its candidate/open conclusion remains
  `NOT_PROVEN`.
- No FileIPC dispatcher load/ping or `drawing_setup_audit` was invoked. The
  candidate remains `CANDIDATE_OPEN_NOT_PROVEN`; no candidate-content defect is
  inferred.
- Cleanup verified the owned PID, temporary bundle, startup script, and both
  health request/result pairs were absent. Candidate and DWT SHA values were
  unchanged. Normal close confirmation timed out, but exact-PID fallback
  cleanup succeeded; this is a cleanup warning, not a semantic pass.
- Classification is `LIVE_EPOCH=FAIL_CLOSED`,
  `DOCUMENT_READY=NOT_PROVEN_BY_THIS_EPOCH`,
  `DISCRIMINATOR_HEALTH=NOT_RUN`, `FILEIPC_LOAD_PING=NOT_RUN`, and
  `SETUP_READBACK=NOT_RUN`. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-drawing-open-discriminator-live-epoch-iteration92.md`.

## Current-main exact page-1 drawing-open stage localization (iteration 91)
- Fresh SOL review of iteration 90 required one offline characterization of
  the existing `FileIPCLiveMCPClient.drawing_open` stages. The ordered path is
  raw-LISP COM open/activate, client-side expected-path assignment, raw-LISP
  dispatcher load, FileIPC ping readiness, then `DWGPREFIX`/`DWGNAME` active
  path verification.
- Iteration 90 reached the post-open FileIPC dispatcher ping timeout. Because
  active-document identity is only read after ping, that result cannot
  distinguish candidate activation failure from candidate activation followed
  by dispatcher non-readiness. No candidate-content defect is inferred.
- The cheapest existing discriminator is one read-only .NET
  `DotNetIPCClient.health(drawing_full_path=None)` result after raw-LISP
  activation and settle, before FileIPC load/ping. Its returned active path
  proves or fails to prove candidate activation; a later ping timeout can
  then be classified without adding an owner.
- Classification is `STAGE_LOCALIZATION=PASS` with
  `CANDIDATE_OPEN_NOT_PROVEN` still the current live state and
  `SETUP_READBACK=NOT_RUN`. No live retry, source/candidate/DXF mutation,
  production-code change, or AutoCAD mutation occurred. Exact evidence is
  recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-drawing-open-stage-localization-iteration91.md`.
- Focused offline tests passed with the standard-library runner: `40 tests,
  OK`.

## Current-main exact page-1 demand-load/setup live oracle (iteration 90)
- Fresh SOL review of iteration 89 authorized exactly one live read-only epoch
  using the proven iteration-76 verified-DWT + `/b CADAGENT_DISPATCH` pattern;
  the Start-tab completion marker was not used.
- Semantic health passed on the owned AutoCAD 2027 session: matching health
  result had `success=true`, `changed=false`, `errors=[]`, expected host, and
  exactly one expected installed module with matching SHA-256.
- The existing read-only `FileIPCLiveMCPClient.drawing_open` path then failed
  closed at dispatcher readiness with
  `MCPTimeoutError: AutoCAD dispatcher did not become ready` (request
  `23afdf5ebdeb`). Candidate-open semantic success was not established and
  `drawing_setup_audit` was not invoked.
- Cleanup and identity invariants passed: owned PID, bundle, requests/results,
  and unique FileIPC root were absent; DWT and exact page-1 candidate SHA
  remained unchanged. No retry or mutation occurred.
- Classification is `SEMANTIC_HEALTH=PASS`,
  `CANDIDATE_READ_ONLY_OPEN=NOT_PROVEN`, `SETUP_READBACK=NOT_RUN`, with
  persistence/visual/dimension still `NOT_PROVEN`. Exact evidence is recorded
  in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-demandload-setup-live-oracle-iteration90.md`.

## Current-main page-1 bootstrap-owner characterization (iteration 89)
- Fresh SOL review of iteration 88 localized the first causal boundary to
  `WindowsAutoCADStartTabSession` completion confirmation, before candidate
  open and before `drawing_setup_audit`.
- Offline inspection confirms that document-ready is only an intermediate
  state. The owner accepts bindings only after a same-root marker file exists
  with the exact `CAD_AGENT_START_TAB_BOOTSTRAP_COMPLETE` token. The AutoLISP
  writer is conditional on `open` returning a handle and emits no failure
  marker; the later writer-return stage marker proves expression delivery, not
  successful completion-file creation/readback.
- Therefore the exact measured missing condition is
  `COMPLETION_MARKER_SUCCESSFUL_CREATE_AND_READBACK=NOT_PROVEN`. No narrower
  filesystem or AutoCAD root cause is inferred, and no live retry was made.
- The already-proven iteration-76 demand-load/semantic-health oracle provides
  the smallest existing reuse path: verified DWT plus `/b CADAGENT_DISPATCH`,
  one matching read-only health result (`success=true`, `changed=false`,
  `errors=[]`), then the existing read-only drawing-open/setup-audit owners.
- This characterization has `MODIFY NONE / CREATE NONE`. Exact evidence is
  recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-bootstrap-owner-characterization-iteration89.md`.
- Focused offline completion-owner checks passed with cache disabled: `8
  passed, 32 deselected`.

## Current-main exact page-1 setup/readback live oracle (iteration 88)
- Fresh SOL review of iteration 87 authorized exactly one live, read-only
  setup/readback oracle for the exact page-1 candidate SHA
  `167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`.
- The existing `WindowsAutoCADStartTabSession` and File/.NET IPC dispatcher
  path were used. AutoCAD 2027 was installed, but no pre-existing `acad.exe`
  session was available.
- The owned bootstrap failed closed before candidate open with
  `START_TAB_BOOTSTRAP_COMPLETION_NOT_CONFIRMED`. Therefore
  `drawing_setup_audit` was not invoked and no setup/readback PASS is claimed.
- Cleanup was verified: no `acad.exe` process remained and the dedicated IPC
  root was empty. The candidate SHA remained unchanged.
- Classification is `SETUP_READBACK=NOT_RUN`; persistence/reopen, visual, and
  dimension remain `NOT_PROVEN`. The failed live epoch was not retried. No
  production code, source, custody artifact, candidate DXF, or live CAD state
  was mutated. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-setup-readback-live-oracle-iteration88.md`.

## Current-main exact page-1 DRAFT_REFERENCE downstream inventory (iteration 87)
- Fresh SOL review of iteration 86 authorized one read-only inventory of the
  exact iteration-80/81 page-1 identity chain, explicitly skipping
  DARA/R3/R4/source-fusion as non-applicable to the Owner's PDF
  `DRAFT_REFERENCE` lane.
- The exact chain remains bound: manifest SHA
  `f7c7b1afbd52f8f504dafbcb9b6efb416ee332b88260a01aea2414ab9d650eaf`, page-1
  DXF SHA
  `167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`, and
  page-1 build-evidence SHA
  `16053d029396a8efc029001991068207c60e4484538eb1f21a765dec2250d659`.
- The manifest explicitly remains `DRAFT_REFERENCE`,
  `authoritative_release_eligible=false`, and
  `drawing_setup_evidence=null`. The isolated staged root contains only
  render/IR/DXF/build evidence artifacts; no setup/readback,
  persistence/reopen, or independent visual-review artifact exists. Page-1
  build evidence reports `dimension_count=0`.
- Ordered downstream classification is: `SETUP_READBACK=NOT_PROVEN` (first
  unproven gate), `PERSISTENCE_REOPEN=NOT_PROVEN`, `VISUAL=NOT_PROVEN`, and
  `DIMENSION=NOT_PROVEN`. No AutoCAD/FileIPC or mutation was performed.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-exact-page1-draft-reference-downstream-inventory-iteration87.md`.

## Current-main PDF lane/source-fusion call-site closure (iteration 86)
- SOL changed the product decision: PDF `DRAFT_REFERENCE` may continue using
  SHA-bound run-pdf/candidate evidence without approved-root or identity-key
  custody. The authoritative `source-custody-1.0` and source-fusion contracts
  remain unchanged.
- A current-main production call-site audit found no PDF-lane caller that sends
  a `DRAFT_REFERENCE` manifest into `build_source_fusion_packet`. The PDF CLI
  and PDF pilot bind source/page/stage hashes only; source-fusion consumers are
  separate authoritative/R3 owners and retain the `READY` custody guard.
- Existing focused workflow evidence passed under `.venv-py311` with cache
  disabled: PDF CLI run/resume, PDF pilot binding from a PDF manifest without
  custody/key, and non-`READY` source-fusion rejection — `3 passed, 240
  deselected`.
- Therefore the immediate-consumer RED is absent in current main and no
  minimal GREEN code change is required: `MODIFY NONE / CREATE NONE` remains
  the exact write-set. The PDF draft lane already continues without key while
  authoritative promotion remains fail-closed.
- No production code, source, custody, candidate, DXF, or live CAD state was
  mutated. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-pdf-lane-source-fusion-call-site-closure-iteration86.md`.

## Current-main DRAFT_REFERENCE owner/write-set closure (iteration 85)
- Fresh SOL review of iteration 84 required one offline closure of the exact
  existing owner and write-set before any implementation.
- The existing owner is `cad_agent.manifest.classify_draft_reference`, reached
  by `cad_agent.pdf.new_pdf_manifest` and `cad_agent.pdf.read_pdf_manifest`.
  It forces `release_profile=DRAFT_REFERENCE`,
  `authoritative_release_eligible=false`, and rejects conflicting claims.
- The immediate production consumers are `cad_agent.cli` and
  `cad_agent.mechanical_pilot`; they read the PDF manifest for run/source
  binding but do not consume or promote `authoritative_release_eligible`.
  No second acceptance authority was found.
- Exact write-set closure is `MODIFY NONE / CREATE NONE`: the existing owner
  already enforces `DRAFT_REFERENCE => NON_AUTHORITATIVE_ONLY`. The existing
  `cad_agent.source_fusion` owner remains the authoritative boundary and still
  rejects non-`READY` custody.
- Causal RED suite passed under `.venv-py311` with cache disabled: the draft
  manifest path stayed non-authoritative, all three unsafe release claims were
  rejected, and non-`READY` custody returned `CUSTODY_NOT_READY` — `5 passed,
  232 deselected`.
- No production code, source, custody, candidate, DXF, or live CAD state was
  mutated. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-draft-reference-owner-write-set-closure-iteration85.md`.

## Current-main DRAFT_REFERENCE policy-split characterization (iteration 84)
- Fresh SOL review of the owner request to remove approved-root and
  identity-key requirements returned `VERDICT=MATERIAL_FINDING` and
  `HUMAN_GATE=NO` for one offline architecture/TDD characterization.
- The existing PDF owner creates the exact source manifest as
  `release_profile=DRAFT_REFERENCE` with
  `authoritative_release_eligible=false`; the source SHA is
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`.
- The smallest existing authoritative acceptance boundary is
  `cad_agent.source_fusion.build_source_fusion_packet`, through the existing
  locator validators. It calls the existing custody validator and rejects a
  non-`READY` custody record with the causal error `CUSTODY_NOT_READY`.
- Existing focused test `test_task4_rejects_non_ready_custody` passed (`1
  passed, 226 deselected`) under `.venv-py311` with the cache provider
  disabled. No production code, source, candidate, DXF, custody, or live CAD
  state was mutated.
- The bounded future write-set, if separately approved, is only a thin
  DRAFT_REFERENCE policy/acceptance adapter plus focused tests. The
  `source-custody-1.0` and authoritative source-fusion contracts must remain
  unchanged; authoritative promotion must continue to require `READY`
  custody. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-draft-reference-policy-characterization-iteration84.md`.

## Current-main source-custody prerequisite inventory (iteration 83)
- Fresh SOL review of iteration 82 localized the first boundary to real source
  custody materialization and authorized one read-only inventory for approved
  source SHA
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`.
- The fresh run-pdf manifest
  `f7c7b1afbd52f8f504dafbcb9b6efb416ee332b88260a01aea2414ab9d650eaf` has no
  source-bundle, source-custody, source-fusion, approved-root, or identity-key
  reference. The only repository SourceBundle fixture is valid but foreign to
  this source identity (bundle `BUNDLE-20260805-001`, run `RUN-20260805-001`,
  bundle SHA
  `47c8d9d984ffc1e4831d201b0a28eedfe735f3be5040e7557451f1435f5fce3b`).
- Existing SourceIntegrity owners require caller-supplied approved-root
  authority, identity-key bytes/revision, policy limits, and source bundle;
  no authorized exact-source custody record or recognized local source-key
  provider was found. No key bytes or private paths were read or recorded.
- `SOURCE_CUSTODY_PREREQUISITES_FOR_EXACT_SOURCE=NOT_AVAILABLE_FOR_EXISTING_OWNER`.
  `HUMAN_GATE=YES` for approved-root authority and matching identity-key
  material. No source-fusion/DARA/R3/R4 or mutation was performed.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-source-custody-prerequisite-inventory-iteration83.md`.

## Current-main DARA/R3/R4 characterization (iteration 82)
- Fresh SOL review of iteration 81 returned `VERDICT=CLEAR_CONTINUE` and
  authorized exactly one read-only characterization for the same fresh page-1
  identity. `HUMAN_GATE=NO`.
- The run-pdf manifest SHA
  `f7c7b1afbd52f8f504dafbcb9b6efb416ee332b88260a01aea2414ab9d650eaf` and
  page-1 DXF SHA
  `167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714` were
  used without mutation. Existing owners rejected the missing source-fusion,
  reuse/base-CAD, DARA, R3, and R4 prerequisites with explicit contract
  errors; no synthetic or historical provenance was reused.
- The first causal missing input is
  `VALIDATED_SOURCE_BUNDLE_AND_READY_SOURCE_CUSTODY_FOR_SOURCE_FUSION`.
  The run-pdf manifest has raw source/configuration/page/stage identity but no
  validated source bundle/custody, locators, render provenance, observations,
  tolerance policy, or fusion input hash. Therefore
  `DARA_R3_R4_SAME_IDENTITY_BINDING=NOT_PROVEN` and the characterization stops
  at this boundary.
- No source/candidate/DXF/code/live CAD mutation or downstream gate was
  performed. Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-dara-r3-r4-characterization-iteration82.md`.

## Current-main candidate/build exact-identity binding (iteration 81)
- Fresh SOL review of iteration 80 returned `VERDICT=CLEAR_CONTINUE` and
  authorized exactly one read-only identity-binding oracle for the fresh
  page-1 staged DXF/build-evidence pair. `HUMAN_GATE=NO`.
- From manifest SHA
  `f7c7b1afbd52f8f504dafbcb9b6efb416ee332b88260a01aea2414ab9d650eaf`, the
  actual page-1 DXF SHA
  `167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`
  matched both the manifest stage and `build_evidence.dxf.sha256`. The actual
  page-1 build-evidence SHA
  `16053d029396a8efc029001991068207c60e4484538eb1f21a765dec2250d659`
  matched its manifest stage, and `build_result.output_path` resolved to the
  exact staged DXF.
- Page identity, approved source SHA
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`,
  calibration reference/scale/DPI, draft profile, and exact current-main
  execution context all matched through the manifest and pre-bound oracle
  context. The composed gate is `PROVEN_CURRENT`.
- The build-evidence schema directly contains only `dxf` and `build_result`;
  it does not duplicate source or execution-context fields. This was recorded
  explicitly and was not treated as release approval. No downstream gate or
  mutation was performed.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-candidate-build-identity-binding-iteration81.md`.

## Current-main real-PDF run-pdf oracle (iteration 80)
- Fresh SOL review of iteration 79 returned `VERDICT=CLEAR_CONTINUE`,
  confirmed the environment prerequisite as `PROVEN_CURRENT`, and authorized
  exactly one current-main `run-pdf` oracle at
  `e8fc0092ee46750e50de0ea408fd91811cae10c2` using the repository-owned
  `.venv-py311`, approved source SHA
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`,
  calibration `STATUS-e48f3970-144dpi-1to40`, `144` DPI, and
  `7.055555555556` mm/px. `HUMAN_GATE=NO`.
- The exact clean detached worktree stayed at the authorized SHA and clean.
  The one run completed the existing manifest/stage contract for all 9 PDF
  pages in a new isolated output root. Manifest SHA-256 is
  `f7c7b1afbd52f8f504dafbcb9b6efb416ee332b88260a01aea2414ab9d650eaf`.
- Current-main stage states are complete for rendered PNG `9/9`, Primitive IR
  `9/9`, Semantic IR `9/9`, staged DXF `9/9`, and SHA-bound build evidence
  `9/9`. The manifest source SHA matches the approved source and the source
  remained unchanged after execution.
- The result is `release_profile=DRAFT_REFERENCE` with
  `authoritative_release_eligible=false`. No retry, AutoCAD/FileIPC,
  persistence/reopen, visual, dimension, provider/M2, or production-code
  action was performed. The source-to-run-pdf gate is now
  `PROVEN_CURRENT`; downstream acceptance gates remain `NOT_PROVEN` pending a
  fresh SOL decision.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-current-main-run-pdf-oracle-iteration80.md`.

## Current-main real-PDF environment prerequisite (iteration 79)
- Fresh SOL diagnosis of iteration 78 returned
  `VERDICT=MATERIAL_FINDING`, localized the failure to the repository-owned
  environment prerequisite, and authorized only the existing
  `scripts/bootstrap.ps1` owner plus a read-only `fitz` probe at exact main
  `e8fc0092ee46750e50de0ea408fd91811cae10c2`. `HUMAN_GATE=NO`.
- The clean detached worktree
  `C:/temp/cad-agent-real-pdf-current-main-iter78` remained at that SHA and
  clean before and after. Bootstrap reported lock contract PASS and
  environment contract PASS; `scripts/check_environment.py` against the
  repository lock also reported PASS for all 40 locked distributions. The
  lock SHA-256 was
  `d4739cc0c3b523ab11069178680f534fa436e4e64e30e07c30d1f07e652d784d`.
- The exact repository-owned interpreter imported `fitz` successfully as
  PyMuPDF `1.28.0` from
  `C:/temp/cad-agent-real-pdf-current-main-iter78/.venv-py311/Lib/site-packages/fitz/__init__.py`.
  The approved source remained unchanged at SHA-256
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`.
- The previous `run-pdf` oracle was not retried, and no downstream gate or
  source/candidate/DXF/production-code mutation was performed. The environment
  prerequisite is `PROVEN_CURRENT`, while the current-main source-to-run-pdf
  manifest/page gate remains `NOT_PROVEN` pending a fresh SOL authorization.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-environment-prerequisite-iteration79.md`.

## Current-main real-PDF run-pdf oracle (iteration 78)
- Fresh SOL diagnosis of iteration 77 returned `VERDICT=CLEAR_CONTINUE`,
  `HUMAN_GATE=NO`, and authorized exactly one disposable current-main
  `run-pdf` oracle at `e8fc0092ee46750e50de0ea408fd91811cae10c2` using only
  approved source SHA
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75` and
  calibration `STATUS-e48f3970-144dpi-1to40`, `144` DPI,
  `7.055555555556` mm/px. The command and identity were pre-bound in an
  external context file; outputs were isolated outside Git.
- The single oracle failed closed before render/page stages because the clean
  detached worktree's Python environment lacked the existing `fitz`
  dependency: `ModuleNotFoundError: No module named 'fitz'`. The generated
  manifest is retained at
  `C:/temp/cad-agent-real-pdf-current-main-iter78-run/staged/pdf-run-manifest.json`,
  SHA-256
  `d1050dc93adb37e4ea185a0a02d32d30e867595cdc608b714cd7f8e7955f39fe`, with
  `render.state=pending`, zero pages, and zero completed page stages.
- Source SHA after the failed oracle remained unchanged; the detached
  worktree and main worktree had no project modifications. No retry,
  bootstrap, candidate/build consumption, DARA/R3/R4, AutoCAD/FileIPC,
  persistence/reopen, visual, dimension, provider, M2, source/candidate/DXF,
  or production-code action was performed. The current-main gate remains
  `NOT_PROVEN` due the missing prerequisite, not a product-pass claim.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-current-main-run-pdf-oracle-iteration78.md`.

## Real-PDF exact-identity acceptance inventory (iteration 77)
- Fresh `origin/main` is `e8fc0092ee46750e50de0ea408fd91811cae10c2`.
  This inventory follows canonical Issue #409 and is read-only; it does not
  launch AutoCAD, run FileIPC, mutate code, source/candidate/DXF, retry a
  provider, or open a new subsystem.
- The approved private source `202607092308.pdf` is present outside Git and
  hashes to
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`.
  The source-identity gate is `PROVEN_CURRENT`.
- The available `run-pdf` evidence binds that source hash, approved manual
  calibration `STATUS-e48f3970-144dpi-1to40`, `144` DPI, and
  `7.055555555556` mm/px. Its exact private root is outside Git; the outer
  manifest SHA-256 is
  `90fc43a14dcd52517de273f98e57bc7c1b860c86257cc406080180176953b261` and
  the manifest records all 36/36 page stages completed. However, the manifest
  contains no code commit/owner identity, and the historical evidence is not
  bound to fresh `origin/main`.
- Relevant owners changed after the historical P1 evidence identity, including
  `cad_agent/cli.py`, `cad_agent/drawing_contracts.py`,
  `cad_agent/drawing_setup.py`, `cad_agent/fidelity.py`,
  `mcp_integration_lib/mcp_dispatch.lsp`, and
  `primitive_ir_lib/dimension_observer.py`. Therefore
  `SOURCE_SHA_BOUND_RUN_PDF_MANIFEST_STAGE_ON_CURRENT_MAIN` is
  `PROVEN_OTHER_IDENTITY`, not current-main proof, and is the
  `FIRST_UNPROVEN_GATE` for this lane.
- The candidate/build, DARA/R3/R4, setup/readback, persistence/reopen, visual,
  and dimension gates were not entered after the first unproven gate and remain
  `NOT_PROVEN` for the current-main identity. Historical artifacts were not
  promoted across the identity boundary.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-real-pdf-exact-identity-inventory-iteration77.md`.

## Current demand-load semantic health oracle (iteration 76)
- Fresh SOL diagnosis of iteration 75 returned `VERDICT=CLEAR_CONTINUE` and
  `HUMAN_GATE=NO`, authorizing exactly one fresh reversible demand-load
  semantic health oracle. The epoch pre-created one unique existing
  `.NET/FileIPC` health request, staged and temporarily installed the proven
  bundle, and launched one disposable AutoCAD with the verified default DWT
  via `/t` and a temporary `/b` script containing only `CADAGENT_DISPATCH`.
  It did not require CadAgent to be loaded before command invocation and used
  no WM_CHAR/PostMessageW, focus manipulation, additional operation, Task-6,
  source/candidate/DXF, registry mutation, or retry.
- The owned session reached document-ready on HWND `6295198` / PID `31780`.
  The exact matching health result for request
  `health-cadagent-demandload-iter76-20260911` reported
  `schema_version=1.0`, `operation=health`, `success=true`, `changed=false`,
  and empty `errors`; the result's read-only payload identified AutoCAD
  Mechanical 2027 and the installed plugin binary.
- After the matching result, read-only owned-PID inspection found exactly one
  demand-loaded `CadAgent.AutoCAD2027.dll` at the installed bundle path.
  Source/staged/installed SHA-256 was identical:
  `BBBD43CC8AFC6558454A003145811F775E4BAC557BF4AFA4153A188D26828A97`.
  The oracle passed. Cleanup verified PID `31780`, the exact temporary
  installed bundle, request/result pair, and startup script absent; the
  verified default DWT hash remained
  `B4F8B4EA726BAB4B50049F4AA54BA6540F52BD14961F851F49DA705CDC292D42`.
- Proof is retained at
  `C:/temp/cad-agent-task6-live-20260911/demandload-semantic-health-iteration76/demandload-health-proof.json`.
  Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-demandload-semantic-health-oracle-iteration76.md`.
  Fresh SOL review is required before any Task-6 or source/candidate/DXF
  action.

## Current command-demand loading repair (iteration 75)
- Fresh SOL diagnosis of iteration 74 returned `VERDICT=MATERIAL_FINDING`,
  localizing the startup-script race to command activation depending on
  startup-load timing. The authorized scope was one offline TDD manifest repair
  only; no AutoCAD install/launch, FileIPC, Task-6, additional command,
  second transport, source/candidate/DXF, registry mutation, or retry occurred.
- The test first produced RED because `LoadOnCommandInvocation` was absent.
  The existing `PackageContents.xml` now preserves the same bundle, DLL, and
  ProductCode owner while declaring `LoadOnAutoCADStartup=False`,
  `LoadOnCommandInvocation=True`, and exactly one global/local
  `CADAGENT_DISPATCH` command mapping. Focused GREEN passed `1 passed in
  1.86s`.
- Authoritative `scripts/verify.ps1` ran from a clean detached worktree at
  commit `4de9399` and exited `0`: .NET `238 succeeded`, dotnet IPC `82
  passed` with `52` subtests, offline `3309 passed` with `80` subtests,
  causal RED `1 failed` as the expected negative oracle, real-data `2
  skipped`, and AutoCAD Mechanical `17 skipped`. No Autodesk Managed DLLs
  were copied; live CAD/FileIPC remains `NOT RUN`.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-command-demand-loading-repair-iteration75.md`.

## Current startup-script health oracle (iteration 74)
- Fresh SOL diagnosis of iteration 73 returned `VERDICT=MATERIAL_FINDING`,
  localizing the remaining boundary to external command activation and
  authorizing exactly one fresh startup-script health oracle. The epoch
  pre-created one unique health request, installed the proven bundle, launched
  one disposable AutoCAD with a verified local default DWT via `/t` and a
  temporary `/b` script containing only `CADAGENT_DISPATCH`, and excluded
  QNEW-in-script, WM_CHAR/PostMessageW, focus manipulation, additional
  operations, Task-6, source/candidate/DXF, registry mutation, production
  changes, and retry.
- The session reached document-ready on HWND `6293526` / PID `24412`, but
  exact owned-PID module inspection found zero installed CadAgent matches
  (`exact_installed_module_matches=0`, `module_paths=[]`). Source and
  installed DLL SHA-256 still matched
  `BBBD43CC8AFC6558454A003145811F775E4BAC557BF4AFA4153A188D26828A97`.
  The epoch stopped before waiting for a health result; no semantic PASS or
  FileIPC defect is inferred.
- Cleanup verified PID `24412`, the exact installed bundle, the exact request/
  result pair, and the temporary script absent. The verified default DWT hash
  remained unchanged. Proof is retained at
  `C:/temp/cad-agent-task6-live-20260911/startup-script-health-dispatch-iteration74/startup-health-dispatch-proof.json`.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-startup-script-health-oracle-iteration74.md`.
  Fresh SOL diagnosis is required; no retry is authorized by this epoch.

## Current semantic health-dispatch oracle (iteration 73)
- Fresh SOL diagnosis of iteration 72 returned `VERDICT=CLEAR_CONTINUE`,
  `HUMAN_GATE=NO`, and authorized exactly one fresh reversible semantic health
  oracle through the existing `CADAGENT_DISPATCH` and .NET/FileIPC path. The
  epoch staged the proven bundle, launched one fresh disposable AutoCAD with
  `_.QNEW` only, confirmed module identity, wrote one unique health request,
  and entered the existing trigger. No second request, additional operation,
  workaround, Task-6, source, candidate, DXF, registry mutation, or retry
  occurred.
- Pre-dispatch availability passed again: document-ready was observed on HWND
  `3673852` / PID `16864`; exactly one installed CadAgent module matched the
  expected path and source/staged/installed SHA-256
  `BBBD43CC8AFC6558454A003145811F775E4BAC557BF4AFA4153A188D26828A97`.
- The existing trigger failed closed at its foreground ownership precondition
  with `DotNetIPCError: WINDOW_FOREGROUND_INVALID`, before its `PostMessageW`
  loop. No matching health result was produced, so semantic dispatch is
  `NOT RUN`/non-PASS at this boundary and no FileIPC or plugin defect is
  inferred.
- Cleanup verified PID `16864` absent, the exact temporary installed bundle
  absent, and the exact request/result pair absent. Proof is retained at
  `C:/temp/cad-agent-task6-live-20260911/semantic-health-dispatch-iteration73/health-dispatch-proof.json`.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-semantic-health-dispatch-oracle-iteration73.md`.
  Fresh SOL diagnosis is required; no retry is authorized by this epoch.

## Current autoload availability oracle after ProductCode repair (iteration 72)
- Fresh SOL diagnosis of iteration 71 returned `VERDICT=CLEAR_CONTINUE`,
  `HUMAN_GATE=NO`, and authorized exactly one fresh reversible user-scoped
  availability epoch using the repaired ProductCode manifest. The epoch staged
  the complete repository bundle with the exact Release DLL, copied it
  temporarily to the current user's Autodesk `ApplicationPlugins`, launched
  one fresh disposable AutoCAD with `_.QNEW` only, observed same-HWND
  document-ready, inspected the owned PID, and cleaned up. No dispatcher,
  WM_CHAR/raw-LISP, FileIPC, Task-6, source, candidate, DXF, registry
  mutation, or retry occurred.
- Source/staged/installed SHA-256 was identical:
  `BBBD43CC8AFC6558454A003145811F775E4BAC557BF4AFA4153A188D26828A97`.
  Document-ready was observed on HWND `5047694` / PID `32152`.
- Read-only module inspection found exactly one installed CadAgent module at
  the expected bundle-contained path, with matching SHA-256
  (`exact_installed_module_matches=1`). The oracle passed.
- Initial close reported `START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED`; bounded
  exact-PID cleanup confirmed PID `32152` absent, and the exact temporary
  installed `CadAgent.bundle` was removed and verified absent. Proof is
  retained at
  `C:/temp/cad-agent-task6-live-20260911/autoload-availability-iteration71/availability-proof.json`.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-autoload-availability-oracle-iteration72.md`.
  Fresh SOL review is required before any downstream dispatcher/FileIPC or
  Task-6 action.

## Current AutoCAD bundle ProductCode contract repair (iteration 71)
- Fresh SOL diagnosis of iteration 70 returned
  `VERDICT=MATERIAL_FINDING`, identifying the missing required local-deployment
  `ApplicationPackage/@ProductCode`. The authorized scope was one offline TDD
  manifest repair only; bundle installation, AutoCAD retry, dispatcher,
  WM_CHAR/raw-LISP, FileIPC, Task-6, source/candidate/DXF, registry mutation,
  and `UpgradeCode` were excluded.
- The test first produced causal RED because `ProductCode` was absent. The
  manifest now contains exactly one stable repository-owned GUID
  `E5B9D36B-3E99-4B9E-BF2E-4D9AD2A6A709`; focused GREEN passed `1 passed in
  0.50s`.
- Authoritative `scripts/verify.ps1` ran from a clean detached worktree at
  commit `9f81d67` and exited `0`: .NET `238 succeeded`, dotnet IPC `82
  passed` with `52` subtests, offline `3309 passed` with `80` subtests,
  causal RED `1 failed` as the expected negative oracle, real-data `2
  skipped`, and AutoCAD Mechanical `17 skipped`. No Autodesk Managed DLLs
  were copied; live CAD/FileIPC remains `NOT RUN`.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-product-code-contract-repair-iteration71.md`.

## Current autoload availability oracle (iteration 70)
- Fresh SOL diagnosis of iteration 69 returned `VERDICT=CLEAR_CONTINUE`,
  `HUMAN_GATE=NO`, and authorized exactly one reversible user-scoped
  availability epoch. The epoch staged the complete repository bundle with
  the existing Release DLL, copied it temporarily to the current user's
  Autodesk `ApplicationPlugins`, launched one fresh disposable AutoCAD with
  `_.QNEW` only, observed same-HWND document-ready, inspected the owned PID,
  and cleaned up. No dispatcher, WM_CHAR/raw-LISP, FileIPC, Task-6, source,
  candidate, DXF, registry mutation, or retry occurred.
- Source/staged/installed DLL SHA-256 was
  `BBBD43CC8AFC6558454A003145811F775E4BAC557BF4AFA4153A188D26828A97`.
  Document-ready was observed on HWND `3280488` / PID `33640`.
- Read-only module inspection completed but found zero exact matches for the
  installed bundle module and no CadAgent module paths
  (`exact_installed_module_matches=0`, `module_paths=[]`). The negative result
  localizes the open boundary to plugin availability/autoload; it does not
  infer a cause or a dispatcher/FileIPC defect.
- Initial close reported
  `START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED`; bounded exact-PID cleanup then
  confirmed PID `33640` absent. The exact temporary installed
  `CadAgent.bundle` was removed and verified absent. Proof is retained at
  `C:/temp/cad-agent-task6-live-20260911/autoload-availability-iteration70/availability-proof.json`.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-autoload-availability-oracle-iteration70.md`.
  Fresh SOL diagnosis is required; no retry is authorized by this epoch.

## Current bundle-contained module packaging repair (iteration 69)
- Fresh SOL diagnosis of iteration 68 returned
  `VERDICT=MATERIAL_FINDING`, identified that the previous `ModuleName` escaped
  `CadAgent.bundle`, and authorized exactly one TDD packaging-contract repair.
  The scope excluded installation/copy into AutoCAD, registry, live AutoCAD,
  dispatcher, WM_CHAR, FileIPC, Task-6, source, candidate, and DXF mutation.
- The regression test was changed first and correctly failed on the old
  parent-relative path with
  `Issue #409 RED: ComponentEntry ModuleName escapes CadAgent.bundle`.
- The manifest now uses the bundle-contained path
  `./Contents/Windows/CadAgent.AutoCAD2027.dll`. The focused test then passed
  `1 passed in 0.56s`; it stages a disposable bundle, copies the existing
  approved Release DLL into that staged `Contents/Windows` directory, verifies
  containment, and matches the approved DLL byte-for-byte by SHA-256.
- The first clean-worktree verification exposed a stale hardcoded SHA from an
  earlier build (`0F3DA87B96D022D2B493F802ADB3FE165F0EE2F404924F62196367E6DCBB919F`
  was the fresh approved input). The test now derives the approved input hash
  at runtime and compares the staged copy to it. After that test-only
  correction, authoritative `scripts/verify.ps1` ran from a clean detached
  worktree at commit `be98bde` and exited `0`: .NET build/test `238
  succeeded`, offline Python `3309 passed` with `80` subtests, causal RED
  failed exactly as expected (`1 failed`), real-data unavailable state was
  `2 skipped`, and AutoCAD Mechanical unavailable state was `17 skipped`.
  No Autodesk Managed DLLs were copied to build output; live CAD/FileIPC
  remains `NOT RUN`, not a pass.
- No generated DLL is committed. AutoCAD installation/copy and the fresh live
  module-presence oracle remain separate gates and were not run.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-cadagent-bundle-contained-module-repair-iteration69.md`.
  Fresh SOL diagnosis is required before any installation/copy or live oracle.

## Current CadAgent autoload bundle contract (iteration 68)
- Fresh SOL diagnosis of iteration 67 returned
  `VERDICT=MATERIAL_FINDING`, identified the genuinely missing plugin
  availability owner, and authorized exactly one TDD implementation of a
  repository-owned Autodesk ApplicationPlugins bundle contract. The bounded
  scope excluded installation/copy, registry, live AutoCAD, dispatcher,
  WM_CHAR, FileIPC, Task-6, source, candidate, and DXF mutation.
- RED was observed first in
  `mcp_integration_lib/tests/test_autocad_application_bundle.py`: with no
  manifest present, the intended assertion failed with
  `Issue #409 RED: repository-owned CadAgent ApplicationPlugins manifest is absent`.
- GREEN was then observed after adding
  `autocad_plugin/CadAgent.bundle/PackageContents.xml`: the focused test ran
  `1 passed in 0.03s`. It verifies the Win64 AutoCAD `R26.0` boundary, exactly
  one CadAgent component, `LoadOnAutoCADStartup=True`, and a relative module
  path resolving to the existing Release `CadAgent.AutoCAD2027.dll`.
- The existing .NET/FileIPC semantic owner and dispatcher remain unchanged;
  no second transport, CadMind reuse, registry owner, or installer subsystem
  was introduced. Installation and the fresh disposable module-presence oracle
  remain separate live gates and were not run.
- Authoritative `scripts/verify.ps1` ran from a clean detached worktree at
  commit `3aea830` and exited `0`: .NET build/test `238 succeeded`, offline
  Python `3309 passed` with `80` subtests, the causal RED gate failed exactly
  as expected (`1 failed`), real-data unavailable state was `2 skipped`, and
  AutoCAD Mechanical unavailable state was `17 skipped`. The live CAD/FileIPC
  gate is `NOT RUN`, not a pass; no Autodesk Managed DLLs were copied to build
  output.
- Exact evidence is recorded in
  `docs/superpowers/implementation-records/2026-09-11-cadagent-autoload-bundle-contract-iteration68.md`.
  Fresh SOL diagnosis is required before any installation/copy or live oracle.

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
