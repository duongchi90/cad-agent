# AutoCAD Bundle ProductCode Contract Repair — Iteration 71

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Reviewed code head: `65fc23ba610091e236f19ee93f8cee69f96d4ce9`
Implementation commit: `9f81d67b10afc86cdfe3fd72010cb91cd7544812`

## Authority and boundary

SOL's iteration-70 diagnosis was:

```text
VERDICT=MATERIAL_FINDING
MATERIAL_FINDING=PACKAGE_DISCOVERY_CONTRACT_IS_INCOMPLETE
HUMAN_GATE=NO
```

The authorized action was one offline TDD manifest-contract repair only:

- make the bundle test require a non-empty valid GUID `ProductCode`;
- add one stable repository-owned `ProductCode` to `PackageContents.xml`;
- run focused and authoritative offline verification.

The action excluded bundle installation, AutoCAD launch/retry, dispatcher,
WM_CHAR/raw-LISP, FileIPC, Task-6, source/candidate/DXF access, registry
mutation, and `UpgradeCode`.

## TDD evidence

The test was changed first to require `ApplicationPackage/@ProductCode` and
validate it with `uuid.UUID`.

Focused RED before the manifest change:

```text
1 failed in 0.09s
AssertionError: Issue #409 RED: ApplicationPackage ProductCode is required for local deployment
```

The manifest then added exactly one stable GUID:

```text
ProductCode="E5B9D36B-3E99-4B9E-BF2E-4D9AD2A6A709"
```

Focused GREEN:

```text
1 passed in 0.50s
```

## Authoritative verification

`scripts/bootstrap.ps1` created the clean detached-worktree Python 3.11
environment. `scripts/verify.ps1` then ran at commit `9f81d67` from a clean
detached worktree and exited `0`:

- .NET build/test: `238 succeeded`;
- Autodesk Managed DLL output check: none copied;
- dotnet IPC: `82 passed`, `52 subtests passed`;
- offline: `3309 passed`, `21 deselected`, `80 subtests passed`;
- causal RED: `1 failed`, `19 deselected` (expected negative oracle);
- real-data unavailable state: `2 skipped`;
- AutoCAD Mechanical unavailable state: `17 skipped`;
- live CAD/FileIPC marker: `NOT RUN`.

No live epoch was retried. No source, candidate, accepted drawing, DXF,
registry, or production CAD state changed.
