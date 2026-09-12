# AutoCAD Discovery/Load Owner Audit — Iteration 166

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / AutoCAD bundle availability boundary  
Audited code HEAD: `6ce8271221e7a4a027d0edf991e818d58c783220`

## Authority and boundary

Fresh SOL review authorized one offline discovery/load ownership audit only.
The audit read the bundle manifest, the disposable packager, the existing
startup/bootstrap owner, direct NETLOAD/dispatch triggers, and their tests.
It did not install or copy a bundle into Autodesk application directories,
launch AutoCAD, alter registry/environment, invoke dispatcher/File IPC or the
viewport, or touch source, customer/accepted CAD, candidate, DXF, or key state.

## Owner map

- `autocad_plugin/CadAgent.bundle/PackageContents.xml` is demand-loaded:
  `LoadOnAutoCADStartup=False`, `LoadOnCommandInvocation=True`, with the
  `CADAGENT_DISPATCH` command. QNEW alone is therefore not a module-load proof.
- `scripts/package_autocad_bundle.ps1` now owns only disposable filesystem
  staging. It returns a bundle root but has no AutoCAD discovery/install/load
  behavior.
- `mcp_integration_lib.mcp_client.WindowsAutoCADStartTabSession` owns the
  process-bound startup sequence and accepts only an existing direct
  `bootstrap_plugin_path`. After document-ready it sends one direct
  `_.NETLOAD` command for that file. It has no bundle-root input, manifest
  discovery, ApplicationPlugins installation, or demand-load resolution.
- `make_windows_start_tab_session_factory` forwards the direct plugin path;
  the live standalone-DWG test supplies the Release DLL directly. The nearest
  runtime bootstrap test records direct `_.NETLOAD` behavior, not bundle
  discovery.
- The bundle contract test proves manifest containment and disposable staging;
  no test connects its staged bundle root to AutoCAD discovery or command-
  invocation load.
- The prior authorized iteration-70 availability proof staged/installed the
  bundle and reached document-ready, but read-only module inspection found
  zero exact installed-module matches. It did not establish a downstream
  dispatcher/FileIPC defect.

## Classification

```text
STATE=OFFLINE_DISCOVERY_LOAD_OWNER_AUDITED
MATERIAL_FINDING=AUTOCAD_DISCOVERY_LOAD_OWNER_GAP
LIVE_ORACLE=NOT_RUN
HUMAN_GATE=NO
```

`EXISTING_DISCOVERY_LOAD_OWNER_READY` is not established: the current owners
stop at disposable bundle staging or direct DLL NETLOAD, while the manifest's
demand-load/discovery route has no repository owner or offline contract that
binds the staged bundle to AutoCAD. This is an ownership gap, not a new live
load verdict.

## Cheapest causal RED

Add one test-only contract at the existing bundle/startup boundary that stages
the disposable bundle, supplies its manifest-declared module to the existing
startup owner, and requires the owner to expose the exact load target/command
without a second installation or runtime owner. The RED should currently
localize at the missing bundle-root-to-startup/discovery binding. No test is
added in this audit; fresh SOL authorization is required before that RED or
any owner change.

