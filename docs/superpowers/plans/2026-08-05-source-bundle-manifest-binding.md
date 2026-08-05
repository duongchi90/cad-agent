# R1B SourceBundle Manifest Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind one accepted R1A SourceBundle to the existing image/PDF manifest lifecycle through a small immutable reference while preserving legacy readers and workflows.

**Architecture:** `cad_agent.manifest` remains the sole manifest owner. It derives and validates one closed SourceBundle reference using the accepted R1A validator/hash API; `cad_agent.pdf` only delegates optional-reference validation to that owner. No CLI, recognition, CAD, authority, or source-fusion runtime is added.

**Tech Stack:** Python 3.11 standard library, existing `cad_agent.source_bundle`, pytest, Ruff, architecture checker, existing atomic manifest writer, canonical verifier.

## Global Constraints

- Exact implementation base is the plan commit recorded in Issue #58.
- Change exactly the four files allowlisted by Issue #58.
- Reuse `validate_source_bundle()` and `source_bundle_sha256()`; do not duplicate validation or hashing.
- Do not create another manifest/checkpoint store or JSON writer.
- Do not add CLI integration, source discovery, OCR/PDF/CAD processing, source priority, component/view/dimension mapping, authority, revision, repair, verdict, or publication.
- Preserve existing schema-version values and all legacy manifest behavior when `source_bundle` is absent.
- Do not add dependencies or modify `requirements/windows-py311.lock`.
- AutoCAD .NET/live and private-data gates remain `NOT RUN`.

---

## File structure

- Modify `cad_agent/manifest.py`: closed reference validation, binding, match enforcement, optional validation in image-manifest reads.
- Modify `cad_agent/pdf.py`: optional reference validation in PDF-manifest reads through `cad_agent.manifest`.
- Create `tests/test_cad_agent_source_bundle_manifest.py`: focused binding, mismatch, reader, legacy, and non-interference tests.
- Create `docs/superpowers/implementation-records/2026-08-05-source-bundle-manifest-binding.md`: exact evidence and truthful gate states.

---

### Task 1: Closed SourceBundle reference validator

**Files:**
- Modify: `cad_agent/manifest.py`
- Create: `tests/test_cad_agent_source_bundle_manifest.py`

**Interfaces:**
- Consumes: any object supplied as a SourceBundle reference.
- Produces: `SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION` and `validate_source_bundle_reference(value)`.

- [ ] **Step 1: Write failing tests for a valid closed reference and refusal cases**

Create the focused test module with a helper loading `tests/fixtures/source-bundle.json` and tests equivalent to:

```python
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from cad_agent.manifest import (
    ManifestError,
    SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION,
    bind_source_bundle,
    require_source_bundle_match,
    validate_source_bundle_reference,
)
from cad_agent.source_bundle import source_bundle_sha256, validate_source_bundle

FIXTURE = Path(__file__).parent / "fixtures" / "source-bundle.json"


def _bundle() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _reference() -> dict[str, object]:
    bundle = validate_source_bundle(_bundle())
    return {
        "schema_version": "source-bundle-reference-1.0",
        "bundle_id": bundle["bundle_id"],
        "run_id": bundle["run_id"],
        "source_bundle_sha256": source_bundle_sha256(bundle),
        "item_count": len(bundle["items"]),
    }


def test_source_bundle_reference_is_closed_and_valid() -> None:
    reference = _reference()
    assert validate_source_bundle_reference(reference) == reference
    assert SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION == "source-bundle-reference-1.0"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "source-bundle-reference-2.0"),
        ("bundle_id", "bad id"),
        ("run_id", "bad id"),
        ("source_bundle_sha256", "A" * 64),
        ("item_count", 0),
        ("item_count", True),
        ("unexpected", True),
    ],
)
def test_source_bundle_reference_fails_closed(field: str, value: object) -> None:
    reference = _reference()
    reference[field] = value
    with pytest.raises(ManifestError):
        validate_source_bundle_reference(reference)
```

- [ ] **Step 2: Run the focused tests and confirm the interface is missing**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_bundle_manifest.py -q -p no:cacheprovider
```

Expected: FAIL importing the new manifest symbols.

- [ ] **Step 3: Implement the minimal closed validator**

In `cad_agent/manifest.py`:

- import `copy`, `re`, and `Mapping` from `collections.abc` as needed;
- define `SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION`;
- validate exactly the five required fields;
- reuse the R1A identifier shape `[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}`;
- require lowercase 64-character SHA-256;
- reject boolean `item_count` and require `1 <= item_count <= 10000`;
- return a newly constructed normalized dictionary.

Do not import CLI, PDF, recognition, or CAD packages.

- [ ] **Step 4: Run the focused tests**

Expected: the reference tests PASS; later binding imports may remain failing until Task 2.

---

### Task 2: Deterministic binding and match enforcement

**Files:**
- Modify: `cad_agent/manifest.py`
- Modify: `tests/test_cad_agent_source_bundle_manifest.py`

**Interfaces:**
- Consumes: an existing manifest mapping and a full R1A SourceBundle.
- Produces: `bind_source_bundle(manifest, source_bundle)` and `require_source_bundle_match(manifest, source_bundle)`.

- [ ] **Step 1: Add failing binding tests**

Add tests equivalent to:

```python
def _legacy_manifest() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "source": {"name": "input.png", "sha256": "a" * 64, "kind": "image"},
        "configuration": {"scale_mm_per_px": 1.0},
        "approvals": {"calibration": {"approved": True, "reference": "TEST"}},
        "stages": {
            name: {"state": "pending", "artifact": None, "sha256": None, "details": None}
            for name in ("primitive_ir", "semantic_ir", "dxf")
        },
        "release_profile": "DRAFT_REFERENCE",
        "authoritative_release_eligible": False,
        "drawing_setup_evidence": None,
    }


def test_bind_source_bundle_returns_copy_and_small_reference_only() -> None:
    manifest = _legacy_manifest()
    original = copy.deepcopy(manifest)
    bundle = _bundle()
    bound = bind_source_bundle(manifest, bundle)

    assert manifest == original
    assert bound is not manifest
    assert bound["source_bundle"] == _reference()
    assert "items" not in bound["source_bundle"]


def test_binding_is_idempotent_but_conflicting_rebind_is_refused() -> None:
    first = bind_source_bundle(_legacy_manifest(), _bundle())
    assert bind_source_bundle(first, _bundle()) == first

    changed = _bundle()
    changed["items"][0]["sha256"] = "d" * 64
    with pytest.raises(ManifestError, match="conflict"):
        bind_source_bundle(first, changed)


def test_require_source_bundle_match_checks_all_bound_identity() -> None:
    bound = bind_source_bundle(_legacy_manifest(), _bundle())
    require_source_bundle_match(bound, _bundle())

    changed = _bundle()
    changed["run_id"] = "RUN-OTHER"
    with pytest.raises(ManifestError, match="does not match"):
        require_source_bundle_match(bound, changed)
```

Also cover:

- non-mapping manifests;
- missing binding in `require_source_bundle_match`;
- malformed full SourceBundle translated to `ManifestError`;
- caller manifest and bundle remain unmodified;
- item-count mismatch and hash mismatch.

- [ ] **Step 2: Run the focused tests and confirm failure**

Expected: FAIL because binding/match functions are absent.

- [ ] **Step 3: Implement reference derivation and binding**

Use only:

```python
from cad_agent.source_bundle import (
    SourceBundleError,
    source_bundle_sha256,
    validate_source_bundle,
)
```

Translate `SourceBundleError` into `ManifestError` with a clear prefix.

Reference derivation must use the normalized validated bundle and include only:

```python
{
    "schema_version": SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION,
    "bundle_id": normalized["bundle_id"],
    "run_id": normalized["run_id"],
    "source_bundle_sha256": source_bundle_sha256(normalized),
    "item_count": len(normalized["items"]),
}
```

`bind_source_bundle()` deep-copies the manifest. If an existing valid reference
equals the derived one, return the copied manifest unchanged. If it differs,
raise `ManifestError("source_bundle binding conflict")` or an equivalent clear
message.

`require_source_bundle_match()` validates the manifest reference and derived
reference, then compares the complete normalized dictionaries.

- [ ] **Step 4: Run focused tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_bundle_manifest.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/manifest.py tests/test_cad_agent_source_bundle_manifest.py
```

Expected: PASS.

---

### Task 3: Image and PDF reader compatibility

**Files:**
- Modify: `cad_agent/manifest.py`
- Modify: `cad_agent/pdf.py`
- Modify: `tests/test_cad_agent_source_bundle_manifest.py`

**Interfaces:**
- Consumes: legacy or optionally SourceBundle-bound image/PDF manifest JSON.
- Produces: existing `read_manifest()` and `read_pdf_manifest()` behavior with optional-reference validation.

- [ ] **Step 1: Add failing reader tests**

Use temporary files and current reader APIs. Cover:

```python
def test_legacy_image_and_pdf_manifests_do_not_gain_source_bundle_field(tmp_path: Path) -> None:
    # Build valid legacy image/PDF payloads using existing helpers or minimal
    # accepted shapes, write them, read them, and assert "source_bundle" is absent.
    ...


def test_bound_image_and_pdf_manifests_round_trip_reference(tmp_path: Path) -> None:
    # Bind valid legacy payloads, write with existing write_manifest(), read with
    # read_manifest()/read_pdf_manifest(), and assert the closed reference survives.
    ...


def test_image_and_pdf_readers_reject_malformed_optional_reference(tmp_path: Path) -> None:
    # Add an invalid uppercase hash or unknown field and assert ManifestError.
    ...
```

Use existing fixture/build helpers where available. Do not duplicate full image
or PDF runtime logic.

- [ ] **Step 2: Run focused tests and confirm malformed references currently pass**

Expected: FAIL because readers do not yet validate the optional field.

- [ ] **Step 3: Wire optional validation into both readers**

In `read_manifest()` and `read_pdf_manifest()`:

```python
if "source_bundle" in manifest:
    manifest["source_bundle"] = validate_source_bundle_reference(
        manifest["source_bundle"]
    )
```

`cad_agent.pdf` imports `validate_source_bundle_reference` from
`cad_agent.manifest`; it must not reimplement the validator.

Do not add a missing-field default and do not alter schema versions.

- [ ] **Step 4: Run focused and regression tests**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_bundle_manifest.py tests/test_cad_agent_cli.py tests/test_cad_agent_pdf.py -q -p no:cacheprovider
```

Expected: PASS with legacy CLI/PDF behavior unchanged.

---

### Task 4: Architecture guards and implementation record

**Files:**
- Modify: `tests/test_cad_agent_source_bundle_manifest.py`
- Create: `docs/superpowers/implementation-records/2026-08-05-source-bundle-manifest-binding.md`

**Interfaces:**
- Produces: evidence that R1B remains an adapter and does not become a new store/runtime.

- [ ] **Step 1: Add source-level non-interference tests**

Parse changed Python modules with `ast` and assert no new imports from:

```text
primitive_ir_lib
semantic_ir_lib
agent_lib
dxf_builder_lib
mcp_integration_lib
autocad_plugin
ctypes
subprocess
```

Assert the new test/production path does not define another `write_manifest`,
open files outside existing reader/writer functions, or introduce CLI command
names.

- [ ] **Step 2: Run all required verification**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_bundle_manifest.py tests/test_cad_agent_cli.py tests/test_cad_agent_pdf.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/manifest.py cad_agent/pdf.py tests/test_cad_agent_source_bundle_manifest.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

- [ ] **Step 3: Write the implementation record**

Record:

- exact base and final head provenance;
- exactly four changed files;
- focused/regression and canonical counts;
- reference schema and public APIs;
- legacy manifests unchanged when unbound;
- malformed and conflicting bindings refused;
- no SourceBundle item duplication;
- no CLI/source-fusion/runtime/CAD/authority behavior;
- private data, AutoCAD .NET/live, and later slices `NOT RUN`.

- [ ] **Step 4: Confirm one bounded commit and clean worktree**

```powershell
git status --short
git diff --check
git log --oneline <exact-base>..HEAD
```

Expected: exactly one implementation commit after final squashing/amendment and a clean worktree.

- [ ] **Step 5: Open one non-draft PR and stop**

The PR must contain all eight Reuse Declaration fields on the same lines as
their values so the repository checker can parse them. Do not start R1C,
source-fusion runtime, S2C, S3B/S3C, registry, revision, repair, verdict, or
publication.
