# CAD Agent Runtime Environment Inventory

This is the documentation owner referenced by #305 and #429. Read it before
rediscovering workstation topology. It routes supported paths and fresh preflight;
it is not runtime authority or a cached PID/HWND/plugin/active-drawing certificate.
For the operation sequence, use the [native operator workflow](../PROJECT.md#native-operator-workflow).

## Supported topology and owners

| Surface | Location / owner |
| --- | --- |
| Host | Windows, Python 3.11, AutoCAD Mechanical 2027, Tesseract 5.4.0.20240606. The .NET project requires Mechanical/2027/Mechanical product properties and uses `AcadDir` (default `%ProgramFiles%\Autodesk\AutoCAD 2027`) for the installed Autodesk managed assemblies. |
| Python environment | Repository `.venv-py311`; `scripts/bootstrap.ps1` installs `requirements/windows-py311.lock`, and `scripts/verify.ps1` validates it. `cad_agent doctor --json` reports Python/package/Tesseract prerequisites; it does not inspect native runtime admission. |
| Plugin source/build | `autocad_plugin/CadAgent.AutoCAD2027.sln`; existing verifier restores, builds Release/x64 and runs .NET tests. Build output: `autocad_plugin/CadAgent.AutoCAD2027/bin/x64/Release/net10.0-windows/CadAgent.AutoCAD2027.dll`. Never copy Autodesk managed DLLs into plugin deployment output. |
| Package discovery | Repository `autocad_plugin/CadAgent.bundle/PackageContents.xml` restricts discovery to `ACADM`/R26.0 and demand-loads `CADAGENT_DISPATCH`. Its relative DLL location is `Contents/Windows/CadAgent.AutoCAD2027.dll`; a source manifest alone is not an installed bundle. The [bundle regression](../../mcp_integration_lib/tests/test_autocad_application_bundle.py) shows staging/hash validation. |
| Accepted local dispatcher | #461/#463 used `C:\cad-agent\trusted-dispatcher\CadAgent.AutoCAD2027.dll`. Its accepted identity is evidence in those packets; re-check the actual file, build basis and loaded identity before reuse. Current builds do not automatically deploy or reload this path. Use the existing authorized loading route and a fresh process when a loaded .NET assembly must change. |
| Typed transport | `mcp_integration_lib.dotnet_ipc.DotNetIPCClient`, `make_windows_dotnet_dispatch_trigger(hwnd)` and the existing `CADAGENT_DISPATCH` command. Confirm the exact top-level AutoCAD HWND/process; foreground-child admission requires that exact root. The legacy LISP/FileIPC path has separate callers; it is not a substitute plugin-currentness proof. |
| IPC root | Default `C:\temp`; the existing `CAD_AGENT_DOTNET_IPC_DIR` or client `ipc_dir` can explicitly select another root. Confirm client and plugin use the same root. Protected native edits require the existing Windows ACL/reparse/file-identity custody checks. Do not weaken them or move active requests during a run. |
| Disposable work | Prefer a new, separate child of `D:\Cad agent temp` for scratch, candidates, build and evidence outputs when the owner permits it. Keep private drawings/annotations outside Git. #461/#463 accepted evidence roots are routed by STATUS and their final GitHub comments; they are immutable, not disposable workspaces. |

`scripts/verify.ps1 -SkipAutoCADDotNet` explicitly leaves the .NET gate NOT RUN.
The full verifier builds/tests the plugin offline; neither form proves a loaded
AutoCAD process or runs the actual opted-in native edit. Test fixtures and
contract examples are regression inputs, not source/customer authority.

## Fresh live admission

Before a necessary live .NET/NETLOAD/FileIPC epoch, record the tuple required by
[#429 RUNTIME_CONTRACT_CURRENTNESS_V1](https://github.com/duongchi90/cad-agent/issues/429):

```text
CURRENT_MAIN=<fresh GitHub SHA>
CLIENT_CONTRACT_BASIS=<exact client SHA or compatible contract identity>
PLUGIN_BUILD_BASIS=<exact build SHA>
PLUGIN_SHA256=<deployed DLL SHA-256>
LOADED_PLUGIN_SHA256=<observed SHA-256 or NOT_LOADED>
EXPLICIT_COMPATIBILITY_ORACLE=<PASS or NOT_RUN>
```

Default admission requires plugin build basis equal to current main. If they
differ, use one focused offline compatibility oracle for that exact client/plugin
pair. A trusted path, approved hash, successful load or old health result alone
does not establish compatibility. Missing proof means
`RUNTIME_CLIENT_PLUGIN_CONTRACT_SKEW`; resolve build/compatibility offline first.

Only after this preflight, construct the typed client with the exact HWND trigger
and confirmed IPC root. A necessary `client.health(exact_drawing_path)` reports
the executing plugin binary identity and active full path; compare both with the
admitted tuple and intended disposable candidate. Do not send a health request
merely for reassurance when no live work is needed. Identify the exact source and
candidate bytes, DBMOD/currentness, smallest action, expected semantic result and
rollback/cleanup before any mutation. AutoCAD/COM/ROT/NETLOAD/FileIPC is one
exclusive mutable lane; do not blindly retry an uncertain command.

Update this owner only for a material topology/owner change. Record transient
process, active-file, hashes and gate results in the current Issue/evidence packet,
and fresh-read them on resume. No daemon, watcher, registry, second transport or
approval authority is introduced by this inventory.

## External tool / connector allowlist

This inventory also records the small set of external tools/connectors that are
allowed to participate in the development workflow. This is documentation and
preflight evidence only; it is not a runtime authority, permission service,
registry, approval system, or second control plane.

Default rules:

```text
NOT_IN_ALLOWLIST => NOT_ASSUMED_AVAILABLE
NEW_CONNECTOR => CURRENT_PRODUCT_NEED + EXISTING_OWNER_GAP + LEAST_AUTHORITY_SCOPE
EXISTING_GITHUB_CONNECTOR => NO_SECOND_GITHUB_MCP_WITHOUT_MEASURED_NEED
EXISTING_CAD_TRANSPORT => NO_SECOND_CAD_TRANSPORT_WITHOUT_MEASURED_RED
DISABLED_OR_STALE_CONNECTOR => DO_NOT_ROUTE_WORK_THROUGH_IT
```

Before adding or materially expanding an external tool, verify that the current
product boundary actually needs it, the same capability is not already owned,
and the permission surface is the minimum required. Prefer read-only scope for
research/review. Credentials, private/customer data and destructive external
actions remain genuine Human Gates.

Record only material, durable facts when a connector is actually admitted:

| Field | Required fact |
| --- | --- |
| Tool / connector | Exact product or connector identity |
| Purpose | Current product/review need it serves |
| Existing owner | Owner/path it extends rather than duplicates |
| Capability | Read-only or exact bounded write capability |
| Permission scope | Least-authority repository/service scope |
| Credential boundary | Where authorization lives; never store secrets here |
| Current identity | Version/build/plugin identity when material to compatibility |
| State | ENABLED / DISABLED / STALE / NOT_ADMITTED |
| Last verified | GitHub/runtime evidence reference or date when material |

Do not create a machine-readable registry merely to mirror this table. Transient
session IDs, tokens, PIDs, HWNDs and active-file facts belong in the current
issue/evidence packet, not here.

