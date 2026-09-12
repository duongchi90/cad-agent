# AutoCAD Discovery/Load Binding GREEN — Iteration 168

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / AutoCAD bundle availability boundary  
Parent RED HEAD: `f62e71a3e5c1bab402448a5a6dae5af32ac93f92`

## Authority and bounded change

Fresh SOL review authorized one minimal implementation at the existing startup
owner. `make_windows_start_tab_session_factory` now accepts an optional
`bootstrap_bundle_path`, reads the bundle's `PackageContents.xml`, requires
exactly one `ComponentEntry` with a relative in-root DLL `ModuleName`, and
forwards the resolved existing DLL as the existing `bootstrap_plugin_path`.
When the bundle-root input is absent, the existing direct-DLL behavior is
unchanged.

No installation, demand-load registry/environment behavior, second loader,
AutoCAD launch, APPLOAD/NETLOAD execution, dispatcher/File IPC, viewport,
source/customer/accepted CAD, candidate, DXF, or key mutation was performed.

## GREEN evidence

Focused command:

```text
.venv-py311\\Scripts\\python.exe -m pytest -p no:cacheprovider -q mcp_integration_lib/tests/test_autocad_application_bundle.py mcp_integration_lib/tests/test_startup_completion_oracle.py
```

Result:

```text
7 passed in 2.57s
```

Additional checks:

```text
ruff check mcp_integration_lib/mcp_client.py mcp_integration_lib/tests/test_autocad_application_bundle.py -> All checks passed!
git diff --check -> clean
```

## Current classification

```text
STATE=OFFLINE_GREEN_VERIFIED
VERDICT=CLEAR_CONTINUE
MATERIAL_FINDING=NONE_FOR_BUNDLE_ROOT_STARTUP_BINDING
FIRST_UNSATISFIED_BOUNDARY=TRUTHFUL_AUTOCAD_DISCOVERY_OR_PLUGIN_LOAD_AND_STARTUP_RECEIPT_NOT_PROVEN
LIVE_ORACLE=NOT_RUN
HUMAN_GATE=NO
```

Fresh SOL review is required before any live oracle. If the required local
prerequisites are truthfully present, the next bounded action is at most one
disposable live module/startup oracle; otherwise remain offline and record the
missing prerequisite.
