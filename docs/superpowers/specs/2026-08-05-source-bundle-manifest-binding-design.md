# R1B SourceBundle Manifest Binding Design

Status: approved for implementation under the owner's standing PO authorization.

Date: 2026-08-05

Implementation base reviewed: `main` after R1A merge `589d708a69f5c710c0a4c25e52a5b17db9749764`.

## 1. Purpose

R1B adds one compatibility adapter that binds an accepted R1A `SourceBundle`
to the existing image/PDF run-manifest lifecycle without creating a second
manifest store or changing legacy CLI behavior.

The adapter records only an immutable reference. It does not embed source items
again, open source files, run recognition, assign technical authority, or start
a source-fusion workflow.

## 2. Approaches considered

### A. Add all SourceBundle items directly to every manifest

Rejected. This duplicates the authoritative SourceBundle object, increases
checkpoint size, and creates two mutable copies of the same evidence metadata.

### B. Add a small hash-bound reference through the existing manifest owner

Selected. `cad_agent.manifest` remains the only owner. A closed reference binds
`bundle_id`, `run_id`, canonical SourceBundle SHA-256, and item count. Existing
image/PDF readers validate the optional reference but leave manifests without
it unchanged.

### C. Add new CLI workflow arguments and source-fusion execution now

Deferred. CLI integration, source discovery, recognition dispatch, semantic
fusion, and production workflow selection require later reviewed tasks. R1B is
only the persistence/compatibility seam.

## 3. Ownership and reuse

R1B reuses:

- `cad_agent.source_bundle.validate_source_bundle`;
- `cad_agent.source_bundle.source_bundle_sha256`;
- existing `cad_agent.manifest.write_manifest` atomic writes;
- existing image and PDF manifest readers;
- existing legacy/default classification behavior.

R1B must not create another JSON writer, manifest class, checkpoint store,
resume path, SourceBundle validator, or canonical hash implementation.

## 4. Public interface

Add to `cad_agent/manifest.py`:

```python
SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION = "source-bundle-reference-1.0"


def validate_source_bundle_reference(value: object) -> dict[str, object]:
    """Return a normalized closed reference or fail with ManifestError."""


def bind_source_bundle(
    manifest: Mapping[str, object],
    source_bundle: object,
) -> dict[str, Any]:
    """Return a copied manifest bound to one validated SourceBundle."""


def require_source_bundle_match(
    manifest: Mapping[str, object],
    source_bundle: object,
) -> None:
    """Fail when the optional manifest reference does not match the bundle."""
```

Exact type aliases may follow existing module conventions, but these names and
meanings remain stable.

## 5. Closed reference contract

The optional manifest field is named exactly `source_bundle` and contains
exactly:

```text
schema_version
bundle_id
run_id
source_bundle_sha256
item_count
```

Rules:

- `schema_version` is exactly `source-bundle-reference-1.0`;
- `bundle_id` and `run_id` must satisfy the R1A identifier contract;
- `source_bundle_sha256` is exactly 64 lowercase hexadecimal characters;
- `item_count` is an integer from 1 through 10,000 and is never boolean;
- unknown or missing fields fail closed;
- the reference is derived only from `validate_source_bundle()` and
  `source_bundle_sha256()`;
- the full SourceBundle items are not copied into the manifest.

## 6. Binding behavior

`bind_source_bundle()`:

1. requires a mapping manifest and a valid SourceBundle;
2. creates the closed immutable reference;
3. deep-copies the manifest before modification;
4. adds `source_bundle` when no reference exists;
5. is idempotent when an existing reference is byte/field equivalent;
6. refuses a conflicting rebind rather than silently replacing provenance;
7. does not mutate the caller's manifest or SourceBundle.

The function does not write to disk. Callers continue using the existing
atomic `write_manifest()` API.

## 7. Reader compatibility

`read_manifest()` and `read_pdf_manifest()` validate `source_bundle` only when
the field exists.

Legacy behavior is preserved:

- manifests without `source_bundle` remain readable;
- readers do not inject a `source_bundle: null` field;
- no-op legacy read/write output stays byte/field compatible with existing
  behavior;
- current schema-version values remain unchanged in R1B;
- current `run`, `resume`, `run-pdf`, and `resume-pdf` call paths do not
  automatically create a SourceBundle binding.

A malformed optional reference causes `ManifestError` before resume or stage
work can continue.

## 8. Match enforcement

`require_source_bundle_match()` validates the supplied full SourceBundle and
compares all four bound values:

```text
bundle_id
run_id
source_bundle_sha256
item_count
```

It fails when:

- the manifest has no binding;
- the reference is malformed;
- the supplied bundle has different identity, contents, or item count;
- the manifest or bundle is not a mapping/valid contract.

This is a provenance check only. It does not verify source files on disk or
grant approval.

## 9. Safety boundaries

R1B must not:

- change CLI arguments or command routing;
- discover or read source image/PDF/CAD/engineer-record files;
- call Primitive IR, Semantic IR, Agent, DXF, File IPC, C#, or AutoCAD;
- add source-priority, conflict-resolution, component/view/dimension mapping,
  approval, verdict, repair, revision, or publication behavior;
- create a new manifest/checkpoint database or sidecar store;
- add dependencies or change `requirements/windows-py311.lock`;
- change the R1A SourceBundle contract.

## 10. Files

Implementation changes exactly four files:

1. `cad_agent/manifest.py`
2. `cad_agent/pdf.py`
3. `tests/test_cad_agent_source_bundle_manifest.py`
4. `docs/superpowers/implementation-records/2026-08-05-source-bundle-manifest-binding.md`

No other production or test file changes are allowed.

## 11. Verification

Required commands:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_bundle_manifest.py tests/test_cad_agent_cli.py tests/test_cad_agent_pdf.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/manifest.py cad_agent/pdf.py tests/test_cad_agent_source_bundle_manifest.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

AutoCAD .NET/live, private data, CLI integration, source-fusion runtime,
component registry, revision, repair, verdict, and publication remain
`NOT RUN` or not implemented.

## 12. Acceptance

- exactly four allowlisted files change;
- one bounded commit and one non-draft PR;
- optional reference is closed and deterministic;
- conflicting rebinding and stale/mismatched bundles fail closed;
- legacy image/PDF manifests without a binding remain unchanged and readable;
- image/PDF readers reject malformed optional references before stage work;
- no full SourceBundle duplication in manifests;
- no new writer/store, CLI, recognition, CAD, authority, or mutation behavior;
- focused tests, existing image/PDF tests, Ruff, architecture, diff-check,
  canonical verifier, Reuse Declaration, and GitHub CI pass;
- the worker stops after opening the PR.
