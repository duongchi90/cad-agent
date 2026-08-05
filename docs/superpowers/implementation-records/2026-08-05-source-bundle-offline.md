# R1A SourceBundle Offline Contract

Status: pure-Python offline contract implemented; orchestration and production
source processing remain outside this task.

## Identity and bounded scope

- Issue: #56, R1A.
- Branch: `task/r1a-source-bundle-offline`.
- Exact implementation base SHA: `d547ca8b1eb39651a00109da3862b79bcce4f0f9`.
- Verified candidate SHA: `2f1a43b8fe2955cbe75c30b1961762e2d1d76b38`.
- Final head SHA: emitted by the single bounded commit and recorded in the PR
  provenance; a commit cannot contain its own object ID without becoming
  self-referential.
- Changed files: exactly these four allowlisted files:
  - `cad_agent/source_bundle.py`
  - `tests/test_cad_agent_source_bundle.py`
  - `tests/fixtures/source-bundle.json`
  - `docs/superpowers/implementation-records/2026-08-05-source-bundle-offline.md`

The contract is closed, deterministic, dependency-free, and offline. It
normalizes stable source references, validates exact-base CAD, images, PDFs,
and engineer records, and reuses the existing canonical JSON SHA-256 helper.
It does not inspect source bytes or assign approval authority.

## Reuse Declaration

Existing capability inspected: `cad_agent.drawing_contracts` canonical hashing,
existing Python 3.11 validation conventions, architecture boundaries, and the
existing offline verifier.

Existing API reused: `canonical_json_sha256`, existing pytest/Ruff commands,
architecture checker, and `scripts/verify.ps1`.

Adapter required: one adjacent `cad_agent.source_bundle` contract module; no
new transport, parser, recognizer, manifest owner, or CAD writer.

New capability genuinely missing: a closed metadata contract for the immutable
multisource evidence inputs of one reconstruction run.

Files allowed to change: exactly the four files listed in the identity section.

Files forbidden to duplicate: image/PDF recognition, OCR, CAD parsing, DXF
building, solver logic, AutoCAD/File IPC transport, C# dispatcher code,
manifest/checkpoint/CLI integration, component registry, revision store,
repair, verdict, publication, dependencies, and
`requirements/windows-py311.lock`.

Compatibility behavior: existing manifests, CLI commands, checkpoints,
recognition packages, CAD operations, and authority gates are unchanged. This
module performs no filesystem, subprocess, AutoCAD, File IPC, or C# operation.

Migration and rollback path: no migration is required; revert the single
bounded R1A commit. R1B, manifest integration, source fusion, S2C, S3B/S3C,
component registry, revision, repair, and publication remain locked.

## Verification evidence

Focused command:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_bundle.py -q -p no:cacheprovider
```

Observed result: exit `0`; `68 passed`.

Ruff command:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_bundle.py tests/test_cad_agent_source_bundle.py
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

Observed result: exit `0`.

Canonical verifier command:

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Observed result: exit `0` on verified candidate
`2f1a43b8fe2955cbe75c30b1961762e2d1d76b38`. Lock and environment contracts
passed with 40 pinned/locked distributions; dotnet IPC JUnit was
`tests=38 failures=0 errors=0 skipped=0`; offline JUnit was
`tests=997 failures=0 errors=0 skipped=0`; the real-data unavailable-state
probe was `tests=2 skipped=2`; and the AutoCAD Mechanical unavailable-state
probe was `tests=9 skipped=9`. AutoCAD .NET was explicitly `NOT RUN` by the
skip flag. GitHub CI is recorded in the PR provenance after push.

## Gate states and limits

- SourceBundle Python offline contract: implementation scope only; acceptance
  is bound to the final focused and canonical verifier evidence.
- Manifest/CLI integration: **NOT IMPLEMENTED**.
- Recognition, OCR, PDF rendering, CAD parsing, and source fusion: **NOT RUN**.
- File IPC and C# implementation: **NOT RUN**.
- AutoCAD Mechanical live gate: **NOT RUN**.
- Private-data acceptance: **NOT RUN**.
- Component registry and revision: **NOT IMPLEMENTED**.
- Verdict, repair, and publication: **NOT IMPLEMENTED**.

No runtime promotion or production readiness is claimed.
