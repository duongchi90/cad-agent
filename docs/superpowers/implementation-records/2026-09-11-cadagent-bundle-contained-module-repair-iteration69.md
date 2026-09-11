# CadAgent Bundle-Contained Module Repair — Iteration 69

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Reviewed code head: `65fc23ba610091e236f19ee93f8cee69f96d4ce9`
Evidence/docs head before this record: `410ec082529424e726985183789dbbe8b524ad96`

## Authority and boundary

SOL's iteration-68 diagnosis was:

```text
VERDICT=MATERIAL_FINDING
MATERIAL_FINDING=PACKAGE_MODULE_PATH_ESCAPES_BUNDLE_ROOT
HUMAN_GATE=NO
```

The authorized single bounded action was a TDD packaging-contract repair:

- make the offline test reject a `ComponentEntry` `ModuleName` that escapes
  `CadAgent.bundle`;
- change only the manifest path to a bundle-contained `Contents/Windows` path;
- validate a disposable staged bundle containing the exact existing Release DLL
  and matching source SHA-256.

No bundle was copied into AutoCAD's `ApplicationPlugins` directory. No registry,
live AutoCAD, `CADAGENT_DISPATCH`, WM_CHAR, FileIPC, Task-6, source,
candidate, or DXF state was touched.

## TDD evidence

The test was changed first in:

```text
mcp_integration_lib/tests/test_autocad_application_bundle.py
```

With the previous parent-relative manifest path, RED was observed at the new
containment assertion:

```text
1 failed in 0.15s
AssertionError: Issue #409 RED: ComponentEntry ModuleName escapes CadAgent.bundle
```

The manifest was then changed minimally to:

```text
./Contents/Windows/CadAgent.AutoCAD2027.dll
```

The focused test passed:

```text
1 passed in 0.56s
```

The test now proves that the component path stays within the bundle root,
stages a disposable `CadAgent.bundle` outside the repository, copies only the
existing approved Release DLL into `Contents/Windows`, resolves the staged
module path, and matches the approved DLL's SHA-256 byte-for-byte.

The temporary staging directory is removed by the test context manager. No
generated DLL is committed.

The first clean-worktree authoritative verification exposed that a hardcoded
SHA from an earlier build was not stable across a fresh Release build: the
freshly built approved input had SHA-256
`0F3DA87B96D022D2B493F802ADB3FE165F0EE2F404924F62196367E6DCBB919F`.
The test was corrected to derive `approved_sha256` from the exact approved
Release DLL at runtime and compare the staged copy to that value, preserving
the intended byte-for-byte staging check without assuming build metadata is
stable across worktrees.

## Remaining gate

This iteration proves the deploy-time bundle layout contract offline only.
Installing/copying the bundle into AutoCAD's `ApplicationPlugins` directory and
running the fresh disposable module-presence oracle remain separate live
actions requiring a fresh SOL authorization. No live gate ran here.
