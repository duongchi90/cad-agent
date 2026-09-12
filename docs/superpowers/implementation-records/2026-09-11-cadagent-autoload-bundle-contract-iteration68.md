# CadAgent Autoload Bundle Contract — Iteration 68

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Reviewed code head: `65fc23ba610091e236f19ee93f8cee69f96d4ce9`
Evidence/docs head before this record: `409a883ec638da3171762e11943fd69d181e7047`

## Authority and boundary

SOL's iteration-67 diagnosis was:

```text
VERDICT=MATERIAL_FINDING
MATERIAL_FINDING=PLUGIN_AVAILABILITY_OWNER_GENUINELY_MISSING
HUMAN_GATE=NO
```

The authorized single bounded action was a TDD implementation of one
repository-owned Autodesk ApplicationPlugins bundle contract. The scope was
limited to an offline manifest contract and its regression test:

- first prove RED while `autocad_plugin/CadAgent.bundle/PackageContents.xml`
  is absent;
- minimally GREEN it with one `CadAgent.AutoCAD2027` component;
- reference only the existing Release `CadAgent.AutoCAD2027.dll`;
- declare `LoadOnAutoCADStartup="True"` for AutoCAD 2027.

No bundle was copied into an AutoCAD installation, and no registry, installer,
AutoCAD process, CADAGENT_DISPATCH, WM_CHAR, FileIPC, Task-6, source,
candidate, or DXF state was touched.

## TDD evidence

The new offline test is:

```text
mcp_integration_lib/tests/test_autocad_application_bundle.py
```

RED was observed before adding the manifest with the repository virtualenv:

```text
1 failed in 0.18s
AssertionError: Issue #409 RED: repository-owned CadAgent ApplicationPlugins manifest is absent
```

The failure was at the intended missing-manifest assertion, not a test
collection or environment error.

GREEN was then observed after adding the minimal manifest:

```text
1 passed in 0.03s
```

The test verifies the XML root, Win64 AutoCAD `R26.0` runtime boundary, one
component only, `AppName="CadAgent.AutoCAD2027"`,
`LoadOnAutoCADStartup="True"`, and that the relative module path resolves to
the existing Release DLL in the repository.

## Minimal contract

The only new production configuration is:

```text
autocad_plugin/CadAgent.bundle/PackageContents.xml
```

Its sole component references:

```text
../CadAgent.AutoCAD2027/bin/x64/Release/net10.0-windows/CadAgent.AutoCAD2027.dll
```

The existing .NET/FileIPC semantic owner and dispatcher are unchanged. No
second transport, CadMind reuse, registry owner, or installer subsystem was
introduced.

## Remaining gate

This iteration proves only the repository-owned manifest contract and its
offline path/attribute checks. Installation/copy into AutoCAD's
`ApplicationPlugins` directory and the fresh disposable module-presence oracle
remain separate live actions requiring a fresh SOL authorization. No live gate
was run in this iteration.

## Authoritative verification

The authoritative `scripts/verify.ps1` gate ran from a clean detached worktree
at commit `3aea830` and exited `0`:

```text
.NET build/test: 238 succeeded; build warnings were reported but no failures
dotnet_ipc: 82 passed, 52 subtests passed
offline: 3309 passed, 21 deselected, 80 subtests passed
causal RED: 1 failed, 19 deselected (expected negative oracle)
real_data unavailable-state: 2 skipped (prerequisite absent)
autocad_mechanical unavailable-state: 17 skipped (live IPC prerequisites absent)
```

The live CAD/FileIPC gate was therefore `NOT RUN`, not a pass. The verifier
also reported that no Autodesk Managed DLLs were copied to build output.
