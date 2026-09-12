# Command-Demand Loading Repair — Iteration 75

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Implementation commit: `4de93998b546bf2b4cfd4c9943bea8fd34efdcb3`
Reviewed code head: `65fc23ba610091e236f19ee93f8cee69f96d4ce9`

## Authority and boundary

SOL's iteration-74 diagnosis was:

```text
VERDICT=MATERIAL_FINDING
MATERIAL_FINDING=COMMAND_ACTIVATION_MUST_NOT_DEPEND_ON_STARTUP_LOAD_TIMING
HUMAN_GATE=NO
```

The authorized action was one offline TDD manifest repair only:

- require command-demand loading for exactly `CADAGENT_DISPATCH`;
- minimally update the existing bundle manifest with
  `LoadOnCommandInvocation=True` and one global/local command mapping;
- preserve the existing bundle, DLL, and `ProductCode` owner;
- run focused and authoritative offline verification.

No AutoCAD launch/install, FileIPC, Task-6, other command, second transport,
source/candidate/DXF access, registry mutation, or retry was authorized.

## TDD evidence

The test was changed first to require:

```text
LoadOnCommandInvocation=True
LoadOnAutoCADStartup=False
exactly one Command { Global=CADAGENT_DISPATCH, Local=CADAGENT_DISPATCH }
```

Focused RED before the manifest change:

```text
1 failed in 0.13s
KeyError: 'LoadOnCommandInvocation'
```

The existing `PackageContents.xml` was then minimally changed to retain the
same bundle/DLL/ProductCode and add command-demand loading with one mapping.
Focused GREEN:

```text
1 passed in 1.86s
```

## Authoritative verification

`scripts/bootstrap.ps1` prepared the clean detached-worktree environment.
`scripts/verify.ps1` ran at commit `4de9399` from a clean detached worktree
and exited `0`:

- .NET build/test: `238 succeeded`;
- Autodesk Managed DLL output check: none copied;
- dotnet IPC: `82 passed`, `52 subtests passed`;
- offline: `3309 passed`, `21 deselected`, `80 subtests passed`;
- causal RED: `1 failed`, `19 deselected` (expected negative oracle);
- real-data unavailable state: `2 skipped`;
- AutoCAD Mechanical unavailable state: `17 skipped`;
- live CAD/FileIPC marker: `NOT RUN`.

No live state or production drawing changed.
