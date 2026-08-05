# R1B SourceBundle Manifest Binding

Status: Python compatibility adapter implemented; source-fusion runtime and
production authority remain outside this task.

## Identity and bounded scope

- Issue: #58, R1B.
- Branch: `task/r1b-source-bundle-manifest-binding`.
- Exact implementation base SHA: `5950e7b056fc92131a243a7e403e4f187c99086f`.
- Verified candidate SHA: `28063cfd8b4f353ed285288124dc6663cbedec5a`.
- Final head SHA: emitted by the single bounded commit and recorded in the PR
  provenance; a commit cannot contain its own object ID without becoming
  self-referential.
- Changed files: exactly these four allowlisted files:
  - `cad_agent/manifest.py`
  - `cad_agent/pdf.py`
  - `tests/test_cad_agent_source_bundle_manifest.py`
  - `docs/superpowers/implementation-records/2026-08-05-source-bundle-manifest-binding.md`

R1B adds the closed `source_bundle-reference-1.0` reference owned by
`cad_agent.manifest`. It records only bundle ID, run ID, canonical SourceBundle
SHA-256, and item count; it never copies SourceBundle items.

## Public API

- `SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION = "source-bundle-reference-1.0"`
- `validate_source_bundle_reference(value)`
- `bind_source_bundle(manifest, source_bundle)`
- `require_source_bundle_match(manifest, source_bundle)`

The image and PDF readers validate the optional field only when it exists.
Legacy unbound manifests remain readable and do not gain a null/default field.

## Reuse Declaration

Existing capability inspected: `cad_agent.manifest` atomic manifest lifecycle,
`cad_agent.pdf` PDF manifest reader, accepted R1A `cad_agent.source_bundle`,
existing legacy CLI/PDF tests, and the reuse-inventory manifest guidance.

Existing API reused: `validate_source_bundle`, `source_bundle_sha256`,
`write_manifest`, `read_manifest`, `read_pdf_manifest`, `ManifestError`,
pytest, Ruff, architecture checker, and canonical verifier.

Adapter required: one optional closed `source_bundle` reference owned by
`cad_agent.manifest`, validated by both image and PDF readers.

New capability genuinely missing: a deterministic hash-bound bridge from one
full SourceBundle to existing manifests without duplicating its items or
creating another store.

Files allowed to change: exactly the four files listed in the identity section.

Files forbidden to duplicate: SourceBundle validation/hashing, JSON/manifest
writer, manifest/checkpoint/resume store, CLI workflow, OCR/PDF rendering, CAD
parsing, semantic solving, DXF generation, File IPC, C# dispatcher, AutoCAD
operations, component/view registry, dimension authority, source
priority/fusion runtime, revision, repair, verdict, and publisher.

Compatibility behavior: manifests without `source_bundle` remain readable and
unchanged; readers do not inject null/default fields; current schema versions,
`run`, `resume`, `run-pdf`, and `resume-pdf` behavior remain unchanged. A
malformed optional reference fails before stage work.

Migration and rollback path: revert the single bounded R1B commit. Existing
manifests and the R1A SourceBundle contract remain authoritative; no data
migration or runtime promotion occurs.

## Verification evidence

Focused and regression command:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_bundle_manifest.py tests/test_cad_agent_cli.py tests/test_cad_agent_pdf.py -q -p no:cacheprovider
```

Observed result: exit `0`; `55 passed`.

Ruff command:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/manifest.py cad_agent/pdf.py tests/test_cad_agent_source_bundle_manifest.py
```

Observed result: exit `0`; all checks passed.

Architecture command:

```powershell
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
```

Observed result: exit `0`; `Architecture boundaries: PASS`.

Diff command:

```powershell
git diff --check
```

Observed result before the bounded commit: exit `0`.

Canonical verifier command:

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Observed result: exit `0` on verified candidate
`28063cfd8b4f353ed285288124dc6663cbedec5a`. Lock and environment contracts
passed with 40 pinned/locked distributions; dotnet IPC JUnit was
`tests=38 failures=0 errors=0 skipped=0`; offline JUnit was
`tests=1033 failures=0 errors=0 skipped=0`; the real-data unavailable-state
probe was `tests=2 skipped=2`; and the AutoCAD Mechanical unavailable-state
probe was `tests=9 skipped=9`. AutoCAD .NET was explicitly `NOT RUN` by the
skip flag. GitHub CI is recorded in PR provenance after push.

## Gate states and limits

- Legacy image/PDF manifests without binding: preserved and tested.
- Malformed optional references: refused by both readers.
- Full SourceBundle item duplication: not implemented.
- CLI and source-fusion runtime: **NOT IMPLEMENTED**.
- Recognition, OCR, PDF rendering, and CAD parsing: **NOT RUN**.
- File IPC and C# implementation: **NOT RUN**.
- Private-data acceptance: **NOT RUN**.
- AutoCAD Mechanical live gate: **NOT RUN**.
- Component registry, revision, authority, verdict, repair, and publication:
  **NOT IMPLEMENTED**.

No production source discovery, mutation, approval, or runtime promotion is
claimed. R1C, S2C, S3B/S3C, registry, revision, repair, verdict, and
publication remain locked.
