# VS-T3 AutoCAD Evidence Exporter Verification Record

Status: verified on the exact implementation/test head; AutoCAD Mechanical live gate not run.

Verification target:

PR #30 implementation/test head after the round-5 provenance fix.
Verified commit SHA: `30620cb17bb050985db86dcc81f9992316690129`.

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -PythonExe 'D:\cad-agent-master\cad-agent\.venv-py311\Scripts\python.exe'
```

Observed result:

- Exit code: `0`
- Lock contract: PASS, 40 pinned and hashed distributions.
- Environment contract: PASS, 40 locked distributions.
- AutoCAD DLL output check: PASS; no Autodesk Managed DLLs copied.
- IPC contract suite: 20 passed, 18 subtests passed.
- Python IPC JUnit: 38 tests, 0 failures, 0 errors, 0 skipped.
- Offline suite: 749 passed, 11 deselected, 18 subtests passed (767 total).
- Real-data unavailable probe: 2 skipped because private inputs were not configured.
- AutoCAD Mechanical unavailable probe: 9 skipped because no live File IPC session was configured.
- AutoCAD .NET gate in the canonical verifier: PASS; 101 passed, 0 failed,
  0 skipped.
- AutoCAD live marker: `NOT RUN`; no AutoCAD Mechanical File IPC prerequisites were available.
- Ruff: PASS on the affected Python files.
- `git diff --check`: PASS.
- Explicit AutoCAD Mechanical 2027 .NET commands on the same implementation
  head:
  `dotnet restore autocad_plugin/CadAgent.AutoCAD2027.sln` exit `0`;
  `dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 --no-restore`
  exit `0` with 1 warning and 0 errors;
  `dotnet test autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64 --no-build --no-restore`
  exit `0`, 101 passed, 0 failed, 0 skipped.

Authority-boundary review:

- `latest_mutation_sha256` is only echoed from the request; VS-T3 does not update mutation state.
- The exact manifest byte hash is checked before promotion; mutation-field equality alone is insufficient.
- Accepted evidence requires `success=true`, `changed=false`, empty entity handles, equal DWG hashes, equal DBMOD, equal session-state fingerprints, and `transient_state_restored=true`.
- Failure results do not invent an accepted visual-evidence payload.
- Artifact transfer is request-owned, bounded, hash-verified, lease-protected, and cleaned by Python after handoff.
- Current drawing bytes are snapshotted by the orchestrator and re-hashed before
  atomic evidence promotion; the manifest's initial hash is not reused as a
  current-state hash.
- Success requires an artifact handoff consumer. A Python scavenger removes only
  lease-free request directories older than 24 hours.
- Python snapshots and validates the exact Visual Run Manifest bytes before
  dispatch and before/after artifact handoff; any change to authority, state,
  drawing identity, or other manifest fields fails closed even when the
  mutation field is unchanged.
- AutoCAD snapshots and restores typed renderer variables, actual view,
  pickfirst selection, layout, and Model/Paper/floating-viewport identity.
  Layer off/frozen flags are read-only snapshot/compare evidence; VS-T3 never
  opens a layer for write or repairs layer drift.
- Region filtering is based on entity extents. The deterministic projection
  covers lines, circles, arcs, polylines including bulges, text, dimensions,
  block references including transformed children, and sampled splines.
  Hatch boundaries and unknown visible entity types fail closed until an
  approved deterministic flattener exists. VS-T3 accepts `DATUM` measurements
  only through bindings derived by the trusted Python adapter from an exact,
  schema-validated Dimension Register snapshot; caller-supplied approval,
  register hash, or entity handle values are not accepted. The binding must
  match the request run/region/manifest, register source/page scope, and a
  confirmed register datum mapping before the managed reader resolves its
  entity handle read-only. The register is rechecked before dispatch and
  before/after artifact handoff. Non-conformal block transforms, including
  reflections/negative orientation, fail closed. Include/exclude and
  Off/Frozen layer policy is shared by top-level and nested block children,
  whose effective layer is emitted; nested layer `0` inherits its insertion
  layer and missing layer state fails explicitly.
  Floating viewport restoration is a no-op when already at the captured
  `CTAB`/`TILEMODE`/`CVPORT` tuple and propagates target-CVPORT errors instead
  of swallowing them.
- Windows reparse points are rejected for manifest, drawing, artifact root,
  request directories, parents, and artifact files; cleanup and scavenging use
  the same component-by-component guard.
- No visual verdict, repair plan, Codex authority, save, publish, or mutation executor is present in VS-T3.

This record does not claim private-drawing or AutoCAD live acceptance.
