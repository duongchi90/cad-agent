# R1A Source Bundle Offline Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one closed, deterministic, pure-Python SourceBundle contract that describes immutable reconstruction inputs without running recognition, AutoCAD, or manifest integration.

**Architecture:** `cad_agent.source_bundle` owns validation, normalization, building, and canonical hashing only. It reuses `cad_agent.drawing_contracts.canonical_json_sha256` and returns ordinary JSON-compatible dictionaries. Existing manifests, CLI commands, recognition packages, File IPC, C#, CAD operations, registries, and authority gates remain unchanged.

**Tech Stack:** Windows, Python 3.11, pytest, Ruff, existing canonical JSON hashing, existing architecture checker, existing canonical verifier.

## Global Constraints

- Implement exactly the approved design in `docs/superpowers/specs/2026-08-05-source-bundle-offline-contract-design.md`.
- Change exactly four files: `cad_agent/source_bundle.py`, `tests/test_cad_agent_source_bundle.py`, `tests/fixtures/source-bundle.json`, and `docs/superpowers/implementation-records/2026-08-05-source-bundle-offline.md`.
- Do not modify existing production files, CLI, manifests, checkpoints, schemas, File IPC, C#, AutoCAD code, dependencies, or `requirements/windows-py311.lock`.
- Do not read source files, run OCR/PDF/CAD processing, or assign approval, verdict, repair, or publication authority.
- Use one bounded implementation commit and one non-draft PR.

---

### Task 1: Closed SourceBundle contract and fixture

**Files:**

- Create: `cad_agent/source_bundle.py`
- Create: `tests/test_cad_agent_source_bundle.py`
- Create: `tests/fixtures/source-bundle.json`
- Create: `docs/superpowers/implementation-records/2026-08-05-source-bundle-offline.md`

**Interfaces:**

- Consumes: `cad_agent.drawing_contracts.canonical_json_sha256(payload: Mapping[str, object]) -> str`.
- Produces:

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
    ...


def validate_source_bundle(payload: object) -> dict[str, object]:
    ...


def source_bundle_sha256(payload: object) -> str:
    ...
```

- [ ] **Step 1: Create the canonical synthetic fixture**

Create `tests/fixtures/source-bundle.json` with this exact shape and valid values:

```json
{
  "schema_version": "source-bundle-1.0",
  "bundle_id": "BUNDLE-20260805-001",
  "run_id": "RUN-20260805-001",
  "created_at_utc": "2026-08-05T07:30:00Z",
  "items": [
    {
      "source_id": "BASE-CAD-001",
      "kind": "EXACT_BASE_CAD",
      "role": "BASE_CAD",
      "relative_path": "sources/base/original.dwg",
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "media_type": "application/acad",
      "page_ids": [],
      "region_ids": [],
      "captured_at_utc": null,
      "quality": {
        "distortion": "NONE",
        "legibility": "GOOD"
      }
    },
    {
      "source_id": "DETAIL-PDF-001",
      "kind": "PDF",
      "role": "DETAIL",
      "relative_path": "sources/details/detail-pages.pdf",
      "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "media_type": "application/pdf",
      "page_ids": ["PAGE-002", "PAGE-003"],
      "region_ids": ["REGION-DETAIL-A"],
      "captured_at_utc": "2026-08-05T07:20:00Z",
      "quality": {
        "distortion": "PERSPECTIVE",
        "legibility": "LIMITED"
      }
    },
    {
      "source_id": "ENGINEER-DECISION-001",
      "kind": "ENGINEER_RECORD",
      "role": "DECISION",
      "relative_path": "sources/decisions/decision-001.json",
      "sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "media_type": "application/json",
      "page_ids": [],
      "region_ids": ["REGION-DETAIL-A"],
      "captured_at_utc": "2026-08-05T07:25:00Z",
      "quality": {
        "distortion": "NONE",
        "legibility": "GOOD"
      }
    }
  ]
}
```

- [ ] **Step 2: Write failing public-API and deterministic-round-trip tests**

Start `tests/test_cad_agent_source_bundle.py` with imports and these tests:

```python
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_bundle import (
    SOURCE_BUNDLE_SCHEMA_VERSION,
    SourceBundleError,
    build_source_bundle,
    source_bundle_sha256,
    validate_source_bundle,
)


FIXTURE = Path(__file__).parent / "fixtures" / "source-bundle.json"


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_round_trip_is_deterministic() -> None:
    payload = _fixture()
    normalized = validate_source_bundle(payload)
    assert normalized == payload
    assert normalized is not payload
    assert source_bundle_sha256(payload) == canonical_json_sha256(normalized)


def test_builder_normalizes_item_and_reference_order() -> None:
    payload = _fixture()
    items = list(reversed(payload["items"]))
    items[1]["page_ids"] = ["PAGE-003", "PAGE-002", "PAGE-003"]
    items[1]["region_ids"] = ["REGION-DETAIL-A", "REGION-DETAIL-A"]

    built = build_source_bundle(
        bundle_id=payload["bundle_id"],
        run_id=payload["run_id"],
        created_at_utc=payload["created_at_utc"],
        items=items,
    )

    assert built["schema_version"] == SOURCE_BUNDLE_SCHEMA_VERSION
    assert [item["source_id"] for item in built["items"]] == [
        "BASE-CAD-001",
        "DETAIL-PDF-001",
        "ENGINEER-DECISION-001",
    ]
    assert built["items"][1]["page_ids"] == ["PAGE-002", "PAGE-003"]
    assert built["items"][1]["region_ids"] == ["REGION-DETAIL-A"]
```

- [ ] **Step 3: Run the focused tests and confirm RED**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_bundle.py -q -p no:cacheprovider
```

Expected: collection fails because `cad_agent.source_bundle` does not exist.

- [ ] **Step 4: Add closed-root, nested-shape, and authority-refusal tests**

Add parameterized mutations that each must raise `SourceBundleError`:

```python
@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda value: value.__setitem__("unexpected", True), "unsupported"),
        (lambda value: value.__setitem__("schema_version", "source-bundle-2.0"), "schema_version"),
        (lambda value: value.__setitem__("bundle_id", "bad id"), "bundle_id"),
        (lambda value: value.__setitem__("created_at_utc", "2026-08-05T07:30:00+00:00"), "created_at_utc"),
        (lambda value: value.__setitem__("items", []), "items"),
        (lambda value: value.__setitem__("approved", True), "unsupported"),
    ],
)
def test_root_refusals(mutate, match: str) -> None:
    payload = _fixture()
    mutate(payload)
    with pytest.raises(SourceBundleError, match=match):
        validate_source_bundle(payload)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("relative_path", "C:/private/base.dwg", "relative_path"),
        ("relative_path", "../base.dwg", "relative_path"),
        ("relative_path", "sources\\base\\original.dwg", "relative_path"),
        ("sha256", "A" * 64, "sha256"),
        ("captured_at_utc", "not-a-time", "captured_at_utc"),
        ("verdict", "PASS", "unsupported"),
        ("entity_handles", ["2F"], "unsupported"),
    ],
)
def test_item_refusals(field: str, value: object, match: str) -> None:
    payload = _fixture()
    payload["items"][0][field] = value
    with pytest.raises(SourceBundleError, match=match):
        validate_source_bundle(payload)
```

Add explicit tests for duplicate `source_id`, duplicate `relative_path`, invalid quality fields, and more than 10,000 items.

- [ ] **Step 5: Add kind-role-media compatibility tests**

Cover these exact failures:

```python
@pytest.mark.parametrize(
    ("kind", "role", "media_type", "page_ids"),
    [
        ("EXACT_BASE_CAD", "DETAIL", "application/acad", []),
        ("EXACT_BASE_CAD", "BASE_CAD", "application/pdf", []),
        ("IMAGE", "MEASUREMENT", "image/png", []),
        ("IMAGE", "DETAIL", "application/pdf", []),
        ("PDF", "DETAIL", "application/pdf", []),
        ("ENGINEER_RECORD", "OVERALL", "application/json", []),
        ("ENGINEER_RECORD", "DECISION", "image/png", []),
    ],
)
def test_kind_role_media_combinations_fail_closed(
    kind: str,
    role: str,
    media_type: str,
    page_ids: list[str],
) -> None:
    payload = _fixture()
    item = payload["items"][0]
    item.update(
        kind=kind,
        role=role,
        media_type=media_type,
        page_ids=page_ids,
    )
    with pytest.raises(SourceBundleError):
        validate_source_bundle(payload)
```

Also test that non-PDF items reject non-empty `page_ids` and that region/page identifiers reject whitespace and control characters.

- [ ] **Step 6: Implement minimal dependency-free validation**

Create `cad_agent/source_bundle.py` with:

- compiled regexes for identifiers, lowercase SHA-256, Windows drive prefixes, and UTC timestamps;
- `_closed_object()` to reject missing and unknown fields;
- `_identifier()`, `_timestamp_or_none()`, `_safe_relative_path()`, and `_unique_identifiers()` helpers;
- `_validate_item()` implementing the exact kind-role-media matrix;
- `validate_source_bundle()` returning a deep normalized copy;
- `build_source_bundle()` constructing the root object and delegating to validation;
- `source_bundle_sha256()` calling `canonical_json_sha256(validate_source_bundle(payload))`.

Use `datetime.datetime.strptime()` or `datetime.datetime.fromisoformat()` only after the strict `Z` regex accepts the text. Do not accept timezone offsets or more than six fractional digits.

Normalization must:

```python
normalized_items.sort(key=lambda item: item["source_id"])
item["page_ids"] = sorted(set(item["page_ids"]))
item["region_ids"] = sorted(set(item["region_ids"]))
```

Do not access the filesystem and do not import recognition, File IPC, ctypes, subprocess, AutoCAD, or C# modules.

- [ ] **Step 7: Run focused tests and Ruff**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_bundle.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_bundle.py tests/test_cad_agent_source_bundle.py
```

Expected: all focused tests pass and Ruff exits `0`.

- [ ] **Step 8: Add import-boundary and non-interference tests**

Add tests that parse the source module with `ast` and reject imports/calls involving:

```text
ctypes
subprocess
mcp_integration_lib
autocad_plugin
primitive_ir_lib
semantic_ir_lib
dxf_builder_lib
agent_lib
```

Also assert that the implementation does not import `cad_agent.manifest` or `cad_agent.cli`, proving R1A does not silently integrate itself into runtime orchestration.

Run the focused suite again and require PASS.

- [ ] **Step 9: Write the implementation record**

Create `docs/superpowers/implementation-records/2026-08-05-source-bundle-offline.md` containing:

- issue number and branch;
- exact implementation base and final head;
- exactly four changed files;
- focused pytest count;
- Ruff, architecture checker, `git diff --check`, canonical verifier, and GitHub CI results;
- explicit statements that manifest/CLI integration, recognition, File IPC, C#, AutoCAD Mechanical, private data, component registry, revision, repair, verdict, and publication are `NOT RUN` or not implemented;
- one rollback statement: revert the single R1A commit.

Do not claim runtime promotion or production readiness.

- [ ] **Step 10: Run aggregate verification**

Run:

```powershell
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Expected:

- architecture checker: PASS;
- diff check: clean;
- canonical verifier: PASS;
- AutoCAD .NET: `NOT RUN` due explicit skip;
- AutoCAD Mechanical live and private data remain truthful `NOT RUN`/unavailable-state skips, never promoted to PASS.

- [ ] **Step 11: Commit and open the PR**

Before committing, confirm exactly four changed files:

```powershell
git status --short
git diff --name-only
```

Commit:

```powershell
git add cad_agent/source_bundle.py tests/test_cad_agent_source_bundle.py tests/fixtures/source-bundle.json docs/superpowers/implementation-records/2026-08-05-source-bundle-offline.md
git commit -m "feat: add source bundle offline contract"
git push -u origin task/r1a-source-bundle-offline
```

Open one non-draft PR to `main`. The PR body must include all eight Reuse Declaration fields separately, exact commands/counts, exact final head, and truthful `NOT RUN` gates. Stop after opening the PR; do not start manifest integration, source fusion runtime, R1B, S2C, S3B/S3C, component registry, revision, repair, or publication.
