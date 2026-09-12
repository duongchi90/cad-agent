# AutoCAD Discovery/Load Binding Causal RED — Iteration 167

Date: 2026-09-12 (Asia/Saigon)  
Issue: exact page-1 candidate activation / AutoCAD bundle availability boundary  
Parent audit HEAD: `10dd2dd19869036f6768de858bf8fc8d09366ea9`

## Authority and boundary

Fresh SOL review authorized exactly one test-only causal RED at the existing
bundle/startup boundary. The test stages a disposable bundle using the
approved packager, resolves the manifest-declared module, and requires the
existing startup factory to bind that bundle root to its direct plugin-load
owner. No production implementation, AutoCAD launch, Autodesk directory
install, ApplicationPlugins copy, registry/environment mutation, demand-load
side effect, dispatcher/File IPC, viewport, source, customer/accepted CAD,
candidate, DXF, or key operation was performed.

## RED contract

The new test in
`mcp_integration_lib/tests/test_autocad_application_bundle.py`:

1. invokes `scripts/package_autocad_bundle.ps1` into `tmp_path`;
2. resolves the staged DLL through the copied manifest's `ModuleName`;
3. requires the existing `make_windows_start_tab_session_factory` to expose
   `bootstrap_bundle_path`;
4. will then require the factory/session to bind the exact resolved module as
   its single `bootstrap_plugin_path`; and
5. will assert the existing owner emits exactly one matching `_.NETLOAD`
   target once the binding exists.

The first three steps pass. The contract currently stops at the intended
missing bundle-root binding, before any runtime trigger.

## RED evidence

Focused command:

```text
.venv-py311\\Scripts\\python.exe -m pytest -p no:cacheprovider -q mcp_integration_lib/tests/test_autocad_application_bundle.py::test_autocad2027_bundle_binds_to_existing_startup_owner_causal_red
```

Result:

```text
1 failed in 1.98s
AssertionError: Issue #424 RED: startup owner lacks bundle-root-to-plugin binding
```

Nearest bundle contracts were also run:

```text
2 passed, 1 failed in 1.89s
```

The existing manifest/staging contracts therefore remain GREEN. Ruff and
`git diff --check` passed.

## Current classification

```text
STATE=CAUSAL_RED_CHARACTERIZED
MATERIAL_FINDING=AUTOCAD_DISCOVERY_LOAD_OWNER_GAP
FIRST_UNSATISFIED_BOUNDARY=STAGED_BUNDLE_ROOT_NOT_BOUND_TO_EXISTING_STARTUP_OWNER
LIVE_ORACLE=NOT_RUN
HUMAN_GATE=NO
```

Fresh SOL review is required before adding the minimal startup-owner binding.

