# R1C Source Integrity and Deterministic Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure-Python, fail-closed source byte custody and deterministic fusion-evidence boundary that composes accepted R1A/R1B contracts and existing Primitive/Semantic IR artifacts without creating a second truth store or any visual/engineering authority.

**Architecture:** Keep `source-bundle-1.0` unchanged. Create adjacent `source-custody-1.0` and `source-fusion-1.0` artifacts, then bind closed hash-only references through the existing `cad_agent.manifest` owner. Source bytes remain external and read-only; explicit page/region locators and deterministic conflict records prevent guessed mappings or silent winners.

**Tech Stack:** Python 3.11; standard-library `hashlib`, `json`, `os`, `pathlib`, and `stat`; existing locked Pillow 12.3.0, pypdf 6.14.2, and optional read-only ezdxf 1.4.4 adapter; pytest; Ruff; existing canonical verifier.

## Global Constraints

- This plan is not executable until a separate runtime Issue pins its exact base and approves the final runtime allowlist.
- Preserve `cad_agent/source_bundle.py` and `source-bundle-1.0` unchanged.
- Preserve R1B legacy manifest behavior; optional R1C references are validated only when present and are never injected into legacy manifests.
- No dependency, lock-file, workflow, schema-directory, CLI, AutoCAD/File IPC, OCR, model-call, registry, revision, repair, verdict, or publication change.
- No private source file, absolute source path, or customer metadata in Git or ordinary logs.
- Use one writer for the R1C write set; Cell 5/Issue #77 remains read-only.
- Source files are opened read-only and hashed before and after metadata extraction.
- Page/region mappings are explicit; sorted labels or filenames are never used to infer page indexes or crop bounds.
- `READY` means fusion inputs are deterministic and unblocked; it is not visual PASS, engineering approval, CAD acceptance, or publication authority.
- Every task ends in one bounded commit. Do not amend, rebase, squash, force-push, or merge another branch.

---

## Proposed Runtime File Structure

### Create

- `cad_agent/source_integrity.py` — closed custody contract, safe read-only inspection, media metadata adapters, alias/duplicate detection, and canonical custody hashing.
- `cad_agent/source_fusion.py` — explicit locator contracts, provenance references, deterministic evidence groups/conflicts, stale matching, and canonical fusion hashing.
- `tests/test_cad_agent_source_integrity.py` — contract, filesystem, parser, race, alias, duplicate, privacy, and determinism tests.
- `tests/test_cad_agent_source_fusion.py` — locator, provenance, conflict, stale, ordering, and no-authority tests.
- `docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md` — exact implementation/evidence record.

### Modify

- `cad_agent/manifest.py` — optional closed custody/fusion references and binding/match APIs under the existing manifest owner.
- `cad_agent/pdf.py` — validate optional R1C references when reading a PDF run manifest.
- `tests/test_cad_agent_source_bundle_manifest.py` — legacy compatibility, closed reference, binding conflict, and PDF-reader regression tests.

### Explicitly unchanged

- `cad_agent/source_bundle.py`
- `tests/fixtures/source-bundle.json`
- `primitive_ir_lib/**`
- `semantic_ir_lib/**`
- `agent_lib/**`
- `dxf_builder_lib/**`
- `mcp_integration_lib/**`
- `autocad_plugin/**`
- `requirements/**`
- `.github/workflows/**`
- `docs/STATUS.md`
- `docs/HANDOFF.md`

---

### Task 1: Closed Source Custody Contract

**Files:**
- Create: `cad_agent/source_integrity.py`
- Test: `tests/test_cad_agent_source_integrity.py`

**Interfaces:**
- Consumes: `cad_agent.source_bundle.validate_source_bundle`, `cad_agent.source_bundle.source_bundle_sha256`, and `cad_agent.drawing_contracts.canonical_json_sha256`.
- Produces:
  - `SOURCE_CUSTODY_SCHEMA_VERSION = "source-custody-1.0"`
  - `class SourceIntegrityError(ValueError)`
  - `validate_source_custody(payload: object) -> dict[str, object]`
  - `source_custody_sha256(payload: object) -> str`
  - closed custody item and alias-group validators used by Task 2.

- [ ] **Step 1: Add failing closed-contract tests**

Create test helpers that build a complete custody payload with two verified items. Add tests with concrete expectations:

```python
from cad_agent.source_integrity import (
    SOURCE_CUSTODY_SCHEMA_VERSION,
    SourceIntegrityError,
    source_custody_sha256,
    validate_source_custody,
)


def test_source_custody_round_trip_is_closed_and_deterministic() -> None:
    payload = _valid_custody_payload()
    normalized = validate_source_custody(payload)
    assert normalized["schema_version"] == SOURCE_CUSTODY_SCHEMA_VERSION
    assert [item["source_id"] for item in normalized["items"]] == [
        "BASE-CAD-001",
        "DETAIL-PDF-001",
    ]
    assert source_custody_sha256(payload) == source_custody_sha256(normalized)


def test_source_custody_rejects_authority_fields() -> None:
    payload = _valid_custody_payload()
    payload["visual_pass"] = True
    with pytest.raises(SourceIntegrityError, match="unsupported"):
        validate_source_custody(payload)
```

Cover every required root/item field, exact enums, lowercase SHA-256, non-negative size, safe relative paths, closed media metadata, alias-group membership, and rejection of `approved`, `verdict`, `repair`, `publication`, handles, or absolute paths.

- [ ] **Step 2: Run the focused tests and confirm failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_integrity.py `
  -q -p no:cacheprovider
```

Expected: collection/import failure because `cad_agent.source_integrity` does not exist.

- [ ] **Step 3: Implement the minimal closed validators**

Implement exact root fields:

```python
_ROOT_FIELDS = {
    "schema_version",
    "bundle_id",
    "run_id",
    "source_bundle_sha256",
    "approved_root_id",
    "items",
    "alias_groups",
}
```

Implement exact custody states:

```python
_CUSTODY_STATES = {
    "VERIFIED",
    "DUPLICATE_BYTES",
    "ALIAS_PATH",
    "MISSING",
    "PATH_ESCAPE",
    "REPARSE_POINT",
    "UNSUPPORTED_MEDIA",
    "MEDIA_MISMATCH",
    "HASH_MISMATCH",
    "CHANGED_DURING_READ",
    "UNREADABLE",
}
```

Normalize arrays by stable keys and deep-copy all returned data. Reuse the existing R1A identifier/path/hash conventions instead of inventing a permissive parser.

- [ ] **Step 4: Run focused tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_integrity.py `
  -q -p no:cacheprovider

.\.venv-py311\Scripts\python.exe -m ruff check `
  cad_agent/source_integrity.py `
  tests/test_cad_agent_source_integrity.py
```

Expected: all Task 1 tests pass and Ruff exits 0.

- [ ] **Step 5: Commit Task 1**

```powershell
git add cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
git commit -m "contracts: add closed R1C source custody evidence"
```

---

### Task 2: Read-Only Byte Inspection and Media Adapters

**Files:**
- Modify: `cad_agent/source_integrity.py`
- Modify: `tests/test_cad_agent_source_integrity.py`

**Interfaces:**
- Consumes: Task 1 validators; R1A normalized SourceBundle; an approved filesystem root supplied outside the SourceBundle.
- Produces:
  - `inspect_source_bundle(*, approved_root_id: str, approved_root: Path, source_bundle: object) -> dict[str, object]`
  - `require_source_custody_match(*, approved_root: Path, source_bundle: object, custody: object) -> None`
  - private read-only helpers for file identity, two-pass hashing, reparse checks, and supported media metadata.

- [ ] **Step 1: Add failing happy-path tests using synthetic files**

Use `tmp_path` to generate:

- a valid PNG using Pillow;
- a valid one-page PDF using pypdf;
- an ASCII DXF header sample;
- a JSON engineer record.

Build the R1A bundle with exact hashes and assert:

```python
def test_inspect_source_bundle_binds_stable_bytes_and_media(tmp_path: Path) -> None:
    bundle = _bundle_for_synthetic_sources(tmp_path)
    custody = inspect_source_bundle(
        approved_root_id="SYNTHETIC-R1C",
        approved_root=tmp_path,
        source_bundle=bundle,
    )
    assert custody["source_bundle_sha256"] == source_bundle_sha256(bundle)
    assert {item["custody_state"] for item in custody["items"]} == {"VERIFIED"}
    assert source_custody_sha256(custody) == source_custody_sha256(
        inspect_source_bundle(
            approved_root_id="SYNTHETIC-R1C",
            approved_root=tmp_path,
            source_bundle=bundle,
        )
    )
```

- [ ] **Step 2: Add failing path and mutation probes**

Add exact refusal tests for:

- missing root/source;
- lexical `..` escape and absolute path refusal inherited from R1A;
- symlink and Windows reparse/junction when supported;
- directory/non-regular file;
- declared/observed hash mismatch;
- declared/observed media mismatch;
- truncated PNG/JPEG/PDF;
- parser decompression-bomb/oversize refusal;
- file replacement between open and final path identity check;
- file mutation between first and second hash;
- same-file alias under two source IDs;
- identical bytes in two independent files;
- absolute path/private content absent from exception strings and artifacts.

Use an injected test hook around metadata extraction to mutate/replace a file deterministically; do not use sleep-based race tests.

- [ ] **Step 3: Run the focused tests and confirm failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_integrity.py `
  -q -p no:cacheprovider
```

Expected: failures for missing inspection APIs.

- [ ] **Step 4: Implement safe path and descriptor checks**

Implement this order:

1. strict root resolution;
2. lexical containment;
3. per-component `lstat` reparse/symlink refusal;
4. read-only binary open;
5. descriptor stat before read;
6. first streamed SHA-256;
7. metadata extraction on the same descriptor;
8. second streamed SHA-256;
9. descriptor/path stat and same-file checks;
10. declared hash/media comparison.

Do not serialize absolute paths, device IDs, inode/file indexes, timestamps, or parser exception details.

- [ ] **Step 5: Implement bounded media adapters**

Use existing locked libraries only:

- Pillow: `Image.open(handle)` followed by `verify()`; record format, width, height, mode, and bounded DPI fields; never save/convert.
- pypdf: `PdfReader(handle, strict=True)`; record page count, encryption flag, and normalized page boxes; never write/repair/extract text.
- DXF: use a minimal read-only adapter around the already pinned ezdxf only if focused tests prove deterministic structure metadata. Otherwise keep `SPIKE_ONLY` and record header-only metadata in the first slice.
- DWG: verify the bounded `AC10xx` header/media signature only; do not parse geometry.
- Engineer JSON: decode UTF-8, require a JSON object, and record a canonical JSON digest in addition to the original byte hash.

Enforce approved maximum byte/page/pixel limits before expensive parser work.

- [ ] **Step 6: Implement alias/duplicate groups**

Derive deterministic alias group IDs from canonical JSON containing sorted source IDs, stable observed SHA-256, and group type. Preserve separate roles/references. Reject same-file identity with conflicting declarations.

- [ ] **Step 7: Run focused tests, determinism loop, and Ruff**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest `
    tests/test_cad_agent_source_integrity.py `
    -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { throw "R1C custody repetition $_ failed" }
}

.\.venv-py311\Scripts\python.exe -m ruff check `
  cad_agent/source_integrity.py `
  tests/test_cad_agent_source_integrity.py
```

Expected: five identical successful test runs and Ruff exit 0.

- [ ] **Step 8: Commit Task 2**

```powershell
git add cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
git commit -m "feat: inspect R1C source bytes without mutation"
```

---

### Task 3: Explicit Locators, Provenance, and Deterministic Conflicts

**Files:**
- Create: `cad_agent/source_fusion.py`
- Create: `tests/test_cad_agent_source_fusion.py`

**Interfaces:**
- Consumes:
  - `cad_agent.source_bundle.validate_source_bundle`
  - `cad_agent.source_bundle.source_bundle_sha256`
  - `cad_agent.source_integrity.validate_source_custody`
  - `cad_agent.source_integrity.source_custody_sha256`
  - parsed Primitive/Semantic IR mappings with externally verified artifact hashes.
- Produces:
  - `SOURCE_FUSION_SCHEMA_VERSION = "source-fusion-1.0"`
  - `class SourceFusionError(ValueError)`
  - `build_source_fusion_packet(*, source_bundle: object, custody: object, page_locators: object, region_locators: object, primitive_evidence: object, semantic_evidence: object, resolution_references: object = ()) -> dict[str, object]`
  - `validate_source_fusion_packet(payload: object) -> dict[str, object]`
  - `source_fusion_sha256(payload: object) -> str`
  - `require_source_fusion_match(*, source_bundle: object, custody: object, fusion: object) -> None`

- [ ] **Step 1: Add failing locator tests**

Add tests proving:

- every R1A page/region label requires exactly one locator;
- page index must be within observed PDF page count;
- region bounds must be finite, ordered, and within observed dimensions/page box;
- locator `source_id`, page/region labels, and source hash must match custody;
- a multi-page PDF with labels but no explicit page mapping is blocked;
- sorted labels are never implicitly mapped to ascending page indexes.

Concrete assertion:

```python
def test_multi_page_pdf_without_explicit_page_locators_is_blocked() -> None:
    with pytest.raises(SourceFusionError, match="explicit page locator"):
        build_source_fusion_packet(
            source_bundle=_multi_page_bundle(),
            custody=_multi_page_custody(),
            page_locators=[],
            region_locators=[],
            primitive_evidence=[],
            semantic_evidence=[],
        )
```

- [ ] **Step 2: Add failing provenance tests**

Test that:

- Primitive evidence requires artifact SHA, source/page/region locator, primitive ID, trace bounds, and calibration SHA.
- Semantic evidence requires semantic artifact SHA, exact Primitive IR SHA, part/constraint ID, and sorted primitive IDs.
- a Semantic IR reference to the wrong Primitive IR hash fails;
- IDs without artifact hashes fail;
- changed calibration/source hash produces stale state.

- [ ] **Step 3: Add failing conflict and authority tests**

Test deterministic conflict records for byte identity, media type, locator, calibration, measurement, geometry, material, and decision conflicts.

```python
def test_conflicting_measurements_are_preserved_and_block_ready_status() -> None:
    packet = build_source_fusion_packet(**_conflicting_measurement_inputs())
    assert packet["status"] == "BLOCKED_UNRESOLVED"
    assert packet["conflicts"][0]["conflict_type"] == "MEASUREMENT_CONFLICT"
    assert packet["conflicts"][0]["state"] == "UNRESOLVED"
    assert packet["conflicts"][0]["blocking"] is True
```

Reject fields such as `visual_pass`, `engineering_verdict`, `approved`, `repair`, `publication`, CAD handles, or model confidence winner.

- [ ] **Step 4: Run focused tests and confirm failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_fusion.py `
  -q -p no:cacheprovider
```

Expected: import/API failures.

- [ ] **Step 5: Implement closed locator/provenance validators**

Implement closed objects and stable identifiers. Preserve explicit locator order only through canonical sorting by compound key; do not preserve caller list order as authority.

- [ ] **Step 6: Implement evidence grouping and conflict construction**

Use exact role lanes:

- `BASE_CAD`
- `MEASUREMENT`
- `DECISION`
- `DETAIL`
- `SECTION`
- `OVERALL`
- `MATERIAL_TABLE`

Role rank controls display/order only. Never discard an evidence reference. Create `conflict_id` from canonical conflict content. A resolution is accepted only as a separately supplied hash-bound reference; an engineer `DECISION` record alone does not resolve a conflict.

- [ ] **Step 7: Implement packet status and stale matching**

Rules:

- `STALE` if SourceBundle/custody/evidence/calibration/resolution hashes do not match.
- `BLOCKED_UNRESOLVED` if any blocking conflict remains.
- `READY` only when all custody items are eligible, all locators/provenance resolve, hashes match, and no blocking unresolved conflict exists.

`require_source_fusion_match()` must raise on stale/malformed evidence and return `None` only for an exact match.

- [ ] **Step 8: Run focused tests, ordering permutations, and Ruff**

Add permutation tests that shuffle source, locator, primitive, semantic, and conflict inputs and require identical packet JSON/hash.

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_fusion.py `
  -q -p no:cacheprovider

.\.venv-py311\Scripts\python.exe -m ruff check `
  cad_agent/source_fusion.py `
  tests/test_cad_agent_source_fusion.py
```

Expected: all Task 3 tests pass and Ruff exits 0.

- [ ] **Step 9: Commit Task 3**

```powershell
git add cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
git commit -m "feat: build deterministic R1C fusion evidence"
```

---

### Task 4: Bind R1C References to the Existing Manifest Owner

**Files:**
- Modify: `cad_agent/manifest.py`
- Modify: `cad_agent/pdf.py`
- Modify: `tests/test_cad_agent_source_bundle_manifest.py`

**Interfaces:**
- Consumes: Task 1/3 validators and hashes.
- Produces:
  - `SOURCE_CUSTODY_REFERENCE_SCHEMA_VERSION = "source-custody-reference-1.0"`
  - `SOURCE_FUSION_REFERENCE_SCHEMA_VERSION = "source-fusion-reference-1.0"`
  - `validate_source_custody_reference(value: object) -> dict[str, object]`
  - `validate_source_fusion_reference(value: object) -> dict[str, object]`
  - `bind_source_custody(manifest: Mapping[str, object], source_bundle: object, custody: object) -> dict[str, Any]`
  - `bind_source_fusion(manifest: Mapping[str, object], source_bundle: object, custody: object, fusion: object) -> dict[str, Any]`
  - `require_source_custody_match(...) -> None`
  - `require_source_fusion_match(...) -> None`

- [ ] **Step 1: Add failing reference-validation tests**

Test exact closed fields:

Custody reference:

```python
{
    "schema_version": "source-custody-reference-1.0",
    "source_bundle_sha256": "...",
    "source_custody_sha256": "...",
    "item_count": 4,
    "verified_count": 4,
}
```

Fusion reference:

```python
{
    "schema_version": "source-fusion-reference-1.0",
    "source_bundle_sha256": "...",
    "source_custody_sha256": "...",
    "source_fusion_sha256": "...",
    "status": "READY",
    "conflict_count": 0,
    "unresolved_count": 0,
}
```

Reject unknown fields, wrong versions, bad hashes/counts/status, and inconsistent unresolved/conflict counts.

- [ ] **Step 2: Add failing legacy and conflict tests**

Test:

- legacy image/PDF manifests remain exactly unchanged when R1C fields are absent;
- readers validate fields only when present;
- binding is idempotent for the same reference;
- unequal rebinding fails closed;
- fusion binding requires exact bundle/custody match;
- `READY` with unresolved conflicts is rejected;
- manifest stores references only, never custody/fusion item arrays.

- [ ] **Step 3: Run focused tests and confirm failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_bundle_manifest.py `
  tests/test_cad_agent_cli.py `
  tests/test_cad_agent_pdf.py `
  -q -p no:cacheprovider
```

Expected: new reference/API tests fail; existing legacy tests remain passing.

- [ ] **Step 4: Implement reference validators and binders**

Follow the R1B pattern:

- deep-copy the manifest;
- validate derived artifact before creating a reference;
- bind R1A hash in every reference;
- reject an unequal existing reference;
- never inject absent fields during reads;
- map source-integrity/fusion errors to `ManifestError` without leaking paths.

- [ ] **Step 5: Extend image/PDF manifest readers safely**

`read_manifest()` and `read_pdf_manifest()` validate `source_custody` and `source_fusion` only when keys exist. Preserve the current schema versions and draft-reference defaults.

- [ ] **Step 6: Run focused/regression tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_bundle.py `
  tests/test_cad_agent_source_bundle_manifest.py `
  tests/test_cad_agent_cli.py `
  tests/test_cad_agent_pdf.py `
  -q -p no:cacheprovider

.\.venv-py311\Scripts\python.exe -m ruff check `
  cad_agent/manifest.py `
  cad_agent/pdf.py `
  tests/test_cad_agent_source_bundle_manifest.py
```

Expected: all R1A/R1B/R1C compatibility tests pass and Ruff exits 0.

- [ ] **Step 7: Commit Task 4**

```powershell
git add `
  cad_agent/manifest.py `
  cad_agent/pdf.py `
  tests/test_cad_agent_source_bundle_manifest.py
git commit -m "manifest: bind R1C custody and fusion references"
```

---

### Task 5: Security, Determinism, and Resource-Bound Regression Matrix

**Files:**
- Modify: `tests/test_cad_agent_source_integrity.py`
- Modify: `tests/test_cad_agent_source_fusion.py`
- Modify only if a proven defect requires it: `cad_agent/source_integrity.py`, `cad_agent/source_fusion.py`

**Interfaces:**
- Consumes: all Tasks 1-4 APIs.
- Produces: complete synthetic acceptance coverage and benchmark evidence; no new production API.

- [ ] **Step 1: Add deterministic benchmark-style tests**

Generate small, medium, and approved-maximum synthetic inputs. Measure hash and parser phases separately only for regression diagnostics; acceptance is deterministic output and resource-limit enforcement, not a machine-specific timing threshold.

Required assertions:

- repeated runs yield identical custody/fusion canonical hashes;
- reversed/shuffled caller inputs yield identical outputs;
- size/page/pixel limits refuse before unbounded parser work;
- no source file mtime/content changes;
- no absolute path appears in serialized output/error text.

- [ ] **Step 2: Add malformed/fuzz corpus tests**

Use fixed byte sequences for:

- truncated PNG/JPEG/PDF/DXF/JSON;
- unsupported signatures;
- PDF cross-reference and page-count failures;
- oversized dimensions/page counts;
- malformed Unicode JSON;
- duplicate IDs/locators/conflicts;
- NaN/Infinity coordinates and quality values;
- decompression-bomb warning/error mapping.

Do not add a fuzzing dependency; use deterministic parametrized pytest inputs.

- [ ] **Step 3: Add static boundary tests**

AST tests must prove:

- no network/subprocess/AutoCAD/File IPC imports;
- no source write/save/replace/unlink calls in source-inspection paths;
- no OCR/agent/model imports;
- no `visual_pass`, publication, repair, or CAD mutation authority fields.

- [ ] **Step 4: Run the full focused R1 suite**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_bundle.py `
  tests/test_cad_agent_source_bundle_manifest.py `
  tests/test_cad_agent_source_integrity.py `
  tests/test_cad_agent_source_fusion.py `
  tests/test_cad_agent_cli.py `
  tests/test_cad_agent_pdf.py `
  -q -p no:cacheprovider
```

Expected: all tests pass with no warning promoted by the repository warning policy.

- [ ] **Step 5: Run architecture and canonical verification**

```powershell
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check `
  --repo-root . `
  --baseline contracts/reuse-integration/architecture-boundaries.json

.\scripts\verify.ps1
```

If local AutoCAD .NET prerequisites are unavailable, use only the repository-supported skip switch and record AutoCAD .NET as `NOT RUN`; do not call it PASS.

- [ ] **Step 6: Commit Task 5**

```powershell
git add `
  tests/test_cad_agent_source_integrity.py `
  tests/test_cad_agent_source_fusion.py `
  cad_agent/source_integrity.py `
  cad_agent/source_fusion.py
git commit -m "test: harden R1C custody and fusion boundaries"
```

Do not stage unchanged production files merely to match the command; verify `git diff --cached --name-only` before commit.

---

### Task 6: Implementation Record, Exact Audit, and Draft PR Handoff

**Files:**
- Create: `docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md`

**Interfaces:**
- Consumes: exact commit chain, diff, focused/full verification, hosted CI, and Cell 5 findings.
- Produces: one evidence record and a draft PR ready for Master PO review.

- [ ] **Step 1: Write the implementation record with exact evidence**

Include:

- runtime Issue and exact implementation base selected by Master PO;
- branch, bounded commits, and exact final head;
- exact changed-file list;
- internal reuse owners and external candidate classifications;
- selected adjacent-artifact architecture;
- test commands/counts;
- canonical verifier output;
- hosted synthetic merge SHA/checks;
- Cell 5 findings and dispositions;
- private-data, AutoCAD Mechanical live, and hosted AutoCAD .NET states;
- migration/rollback;
- retained locks and no-production-readiness statement.

Do not write unexecuted gates as PASS.

- [ ] **Step 2: Run exact changed-file audit**

Replace `<RUNTIME_BASE_SHA>` only with the exact SHA recorded in the approved runtime Issue before executing this plan. The runtime Issue must make this value concrete; execution is forbidden otherwise.

```powershell
$expected = @(
  'cad_agent/manifest.py',
  'cad_agent/pdf.py',
  'cad_agent/source_fusion.py',
  'cad_agent/source_integrity.py',
  'docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md',
  'tests/test_cad_agent_source_bundle_manifest.py',
  'tests/test_cad_agent_source_fusion.py',
  'tests/test_cad_agent_source_integrity.py'
) | Sort-Object

$actual = git diff --name-only <RUNTIME_BASE_SHA>...HEAD | Sort-Object
$comparison = Compare-Object $expected $actual
if ($comparison) {
  $comparison | Format-Table | Out-String | Write-Host
  throw 'R1C runtime allowlist mismatch'
}
```

- [ ] **Step 3: Run final verification on exact head**

```powershell
git diff --check <RUNTIME_BASE_SHA>...HEAD
.\scripts\verify.ps1
git status --short
```

Expected: diff check and verifier exit 0; worktree clean after committing the record.

- [ ] **Step 4: Commit the implementation record**

```powershell
git add docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md
git commit -m "docs: record R1C source integrity verification"
```

- [ ] **Step 5: Push normally and open/retain a draft PR**

```powershell
git push -u origin <APPROVED_RUNTIME_BRANCH>
```

The runtime Issue must provide `<APPROVED_RUNTIME_BRANCH>` before execution. No force-push, rebase, amend, squash, or merge.

PR body must contain the complete eight-heading Reuse Declaration, exact base/head/commit list, exact changed files, verification evidence, Cell 5 disposition, truthful external gates, migration/rollback, and retained locks.

- [ ] **Step 6: Stop for Master PO review**

PR remains `OPEN/DRAFT`. Do not mark ready or merge. R1C does not authorize Wave 2, registry, revision, repair, verdict, publisher, OCR expansion, model calls, or AutoCAD mutation.

---

## Plan Self-Review

### Spec coverage

- R1A/R1B composition: Tasks 1 and 4.
- Byte custody, media, alias/duplicate, mutation detection: Task 2.
- Page/region identity: Task 3.
- Primitive/Semantic provenance: Task 3.
- Deterministic conflict/unresolved/stale behavior: Task 3.
- Existing manifest/checkpoint ownership: Task 4.
- Security/resource/determinism tests: Task 5.
- Migration, rollback, evidence, and PO handoff: Task 6.

### Type and name consistency

- `source-custody-1.0` and `source-fusion-1.0` names match the design.
- Manifest reference versions and API names are consistent across Tasks 1-4.
- `READY`, `BLOCKED_UNRESOLVED`, and `STALE` are the only fusion statuses.
- Runtime exact base/branch are intentionally supplied by the later approved runtime Issue; this planning document does not guess them.

### Placeholder policy

`<RUNTIME_BASE_SHA>` and `<APPROVED_RUNTIME_BRANCH>` are execution guards, not planning omissions: the future runtime Issue must replace them with exact values before this plan may be executed. No implementation step may proceed while either value is unresolved.

## Execution handoff

After the planning PR is accepted, Master PO must create a separate runtime Issue with:

- exact implementation base;
- exact branch;
- accepted/narrowed eight-path allowlist;
- approved versions/dependency posture;
- Cell 5 final research disposition;
- required focused/private/live gates.

Recommended execution mode: subagent-driven development with one writer and independent requirements/security review after each task. Inline execution is acceptable only with the same task-by-task commit and review gates.
