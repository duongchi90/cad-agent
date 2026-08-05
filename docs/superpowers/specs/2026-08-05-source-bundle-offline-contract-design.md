# R1A Source Bundle Offline Contract Design

Status: approved for implementation under the owner's standing PO authorization.

Date: 2026-08-05

Base reviewed: `main` at `a8a962281b2d7480c9444eb8e1b56c6795c108aa`.

## 1. Purpose

R1A introduces one closed, pure-Python `SourceBundle` contract for describing the immutable evidence inputs of one CAD reconstruction run. It allows later orchestration to refer to images, PDFs, an optional exact-base CAD, and engineer records without launching AutoCAD, running recognition, mutating a manifest, or assigning global technical authority.

This slice is intentionally limited to data shape, deterministic normalization, validation, canonical hashing, synthetic fixtures, and offline tests.

## 2. Approaches considered

### A. Extend the existing run manifest directly

Rejected. The current image/PDF manifests are compatibility-sensitive and already classify legacy paths as `DRAFT_REFERENCE`. Adding multisource fields there would couple R1A to CLI/resume behavior and create unnecessary migration risk.

### B. Add one independent orchestration contract module

Selected. A new `cad_agent.source_bundle` module can be tested in isolation, reused later by adapters, and integrated into manifests only in a separate reviewed task.

### C. Add JSON Schema, CLI, and manifest integration together

Deferred. That would combine contract definition, orchestration, persistence, and migration in one task. R1A needs only a dependency-free Python boundary and a canonical fixture.

## 3. Public interface

Create `cad_agent/source_bundle.py` with this public surface:

```python
SOURCE_BUNDLE_SCHEMA_VERSION = "source-bundle-1.0"

class SourceBundleError(ValueError):
    pass


def build_source_bundle(
    *,
    bundle_id: str,
    run_id: str,
    created_at_utc: str,
    items: object,
) -> dict[str, object]:
    """Validate, normalize, and return one deterministic SourceBundle."""


def validate_source_bundle(payload: object) -> dict[str, object]:
    """Return a normalized copy or fail closed."""


def source_bundle_sha256(payload: object) -> str:
    """Return the canonical SHA-256 of a validated SourceBundle."""
```

`source_bundle_sha256()` must reuse `cad_agent.drawing_contracts.canonical_json_sha256`; it must not add another canonical JSON implementation.

## 4. Root contract

The root object is closed and contains exactly:

```text
schema_version
bundle_id
run_id
created_at_utc
items
```

Rules:

- `schema_version` is exactly `source-bundle-1.0`;
- `bundle_id` and `run_id` are stable identifiers matching `[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}`;
- `created_at_utc` is RFC 3339 UTC using `Z`, with at most six fractional digits;
- `items` is a non-empty array with at most 10,000 entries;
- source IDs and relative paths are unique;
- normalized output sorts items by `source_id` and sorts/deduplicates list fields.

## 5. Item contract

Each item is a closed object containing exactly:

```text
source_id
kind
role
relative_path
sha256
media_type
page_ids
region_ids
captured_at_utc
quality
```

Allowed `kind` values:

```text
IMAGE
PDF
EXACT_BASE_CAD
ENGINEER_RECORD
```

Allowed `role` values:

```text
OVERALL
DETAIL
SECTION
MATERIAL_TABLE
BASE_CAD
MEASUREMENT
DECISION
```

Compatibility rules:

- `EXACT_BASE_CAD` requires role `BASE_CAD` and media type `application/acad` or `application/dxf`;
- `IMAGE` allows roles `OVERALL`, `DETAIL`, `SECTION`, or `MATERIAL_TABLE` and media type `image/png` or `image/jpeg`;
- `PDF` allows roles `OVERALL`, `DETAIL`, `SECTION`, or `MATERIAL_TABLE`, requires media type `application/pdf`, and requires at least one `page_id`;
- `ENGINEER_RECORD` allows role `MEASUREMENT` or `DECISION` and requires media type `application/json`;
- `page_ids` and `region_ids` contain unique stable identifiers;
- non-PDF items must have an empty `page_ids` list;
- `captured_at_utc` may be `null` or a valid UTC timestamp;
- `sha256` is exactly 64 lowercase hexadecimal characters;
- `relative_path` is a safe relative POSIX path: no drive prefix, leading slash, backslash, empty segment, `.`, or `..`.

## 6. Quality metadata

`quality` is a closed object containing exactly:

```text
distortion
legibility
```

Allowed values:

```text
distortion: NONE | PERSPECTIVE | UNKNOWN
legibility: GOOD | LIMITED | UNREADABLE
```

These values are observations only. They do not grant authority, approve dimensions, or determine a visual verdict.

## 7. Safety and authority boundaries

Validation fails closed for unknown fields, malformed identifiers, unsafe paths, duplicate sources, uppercase or malformed hashes, invalid timestamps, unsupported kind/role/media combinations, and invalid quality values.

The contract must reject any field named or semantically acting as:

```text
authoritative
approved
approval
verdict
pass
repair
publication
entity_handles
model_space
```

R1A must not:

- read source bytes or verify files on disk;
- run OCR, image processing, PDF rendering, or CAD parsing;
- call AutoCAD, File IPC, C#, ctypes, or subprocess;
- modify existing manifests, checkpoints, CLI commands, registries, or revision stores;
- contain dimensions, engineering values, component mappings, entity handles, or approval authority;
- add dependencies or modify `requirements/windows-py311.lock`.

## 8. Files and ownership

Implementation changes exactly four files:

1. `cad_agent/source_bundle.py`
2. `tests/test_cad_agent_source_bundle.py`
3. `tests/fixtures/source-bundle.json`
4. `docs/superpowers/implementation-records/2026-08-05-source-bundle-offline.md`

No existing production file is modified.

## 9. Verification

Required focused verification:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_bundle.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_bundle.py tests/test_cad_agent_source_bundle.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

AutoCAD .NET, AutoCAD Mechanical live, private-data acceptance, recognition, manifest integration, component registry, revision, repair, and publication remain `NOT RUN` or not implemented.

## 10. Acceptance

- exactly four allowlisted files change;
- one bounded commit and one non-draft PR;
- deterministic fixture round-trip and canonical hash pass;
- focused tests cover every refusal rule and legacy-package non-interference;
- no new runtime dependency, CLI, manifest, transport, CAD operation, authority, or mutation path;
- the PR contains all eight Reuse Declaration fields separately;
- the worker stops after opening the PR.
