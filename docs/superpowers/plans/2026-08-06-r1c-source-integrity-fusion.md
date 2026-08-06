# R1C Source Integrity and Deterministic Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-Python, fail-closed source-custody and deterministic fusion-evidence boundary that composes accepted R1A/R1B and current Primitive/Semantic IR artifacts without adding another truth store or any visual/engineering authority.

**Architecture:** Preserve `source-bundle-1.0`. Create adjacent `source-custody-1.0` and `source-fusion-1.0` artifacts, use a bounded Windows final-handle adapter for source identity/containment, project IR observations into UUID-independent canonical digests, and bind only small closed references through the existing `cad_agent.manifest` owner.

**Tech Stack:** Windows; Python 3.11; stdlib `hashlib`, `json`, `os`, `pathlib`, `stat`, `ctypes`, and `msvcrt`; existing locked Pillow 12.3.0 and pypdf 6.14.2; optional ezdxf 1.4.4 remains spike-only; pytest; Ruff; repository architecture checker and canonical verifier.

## Global constraints

- This plan is not executable until a separate runtime Issue supplies the exact implementation base, branch, and final allowlist.
- Runtime implementation remains locked while PR #78 is planning-only.
- Preserve `cad_agent/source_bundle.py` and `source-bundle-1.0` unchanged.
- Preserve current Primitive/Semantic models and producers, including optional `PrimitiveIRRef.sha256` behavior.
- Preserve R1B legacy manifest behavior; absent R1C references remain absent.
- No dependency, lock-file, workflow, CLI, schema-directory, OCR, model call, AutoCAD/File IPC, registry, revision, repair, visual verdict, engineering approval, or publication change.
- No private source, absolute source path, raw Windows volume/file ID, customer content, or parser exception text in Git or ordinary logs.
- Use one writer for the R1C runtime write set. Cell 5 remains independent and read-only.
- No local AutoCAD session is required. AutoCAD Mechanical live and hosted AutoCAD .NET remain `NOT RUN` unless a separate Issue executes them.
- Every task ends in a bounded commit. Do not amend, rebase, squash, force-push, or merge another branch.

---

## Proposed runtime file structure

### Create

- `cad_agent/source_integrity.py` — custody contract, Windows final-handle adapter, read-only byte/media inspection, privacy-safe identity, aliases/duplicates, and custody hash.
- `cad_agent/source_fusion.py` — locators, PDF render provenance, UUID-independent IR projections, conflicts, resolution validation, stale matching, and fusion hash.
- `tests/test_cad_agent_source_integrity.py` — contract, root/identity, handle/race, media/JSON, alias/duplicate, privacy, and resource tests.
- `tests/test_cad_agent_source_fusion.py` — locator/render, deterministic provenance, Semantic compatibility, conflict/resolution, stale, and authority tests.
- `docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md` — exact implementation and verification record.

### Modify

- `cad_agent/manifest.py` — optional closed custody/fusion references and exact bind/match APIs.
- `cad_agent/pdf.py` — validate optional R1C references when reading PDF manifests.
- `tests/test_cad_agent_source_bundle_manifest.py` — reference validation, compatibility, unequal-rebind, and PDF-reader tests.

### Explicitly unchanged

- `cad_agent/source_bundle.py`
- `cad_agent/cli.py`
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

## Task 1: Closed custody contract and exact readiness semantics

**Files:**

- Create: `cad_agent/source_integrity.py`
- Create: `tests/test_cad_agent_source_integrity.py`

**Consumes:**

- `cad_agent.source_bundle.validate_source_bundle()`
- `cad_agent.source_bundle.source_bundle_sha256()`
- `cad_agent.drawing_contracts.canonical_json_sha256()`

**Produces:**

- `SOURCE_CUSTODY_SCHEMA_VERSION = "source-custody-1.0"`
- `class SourceIntegrityError(ValueError)`
- `validate_source_custody(payload: object) -> dict[str, object]`
- `source_custody_sha256(payload: object) -> str`
- closed root/item/alias-group validators

- [ ] **Step 1: Write failing round-trip and closed-field tests**

Create `_valid_custody_payload()` containing:

```python
{
    "schema_version": "source-custody-1.0",
    "bundle_id": "BUNDLE-001",
    "run_id": "RUN-001",
    "source_bundle_sha256": "a" * 64,
    "approved_root_id": "ROOT-SYNTHETIC",
    "approved_root_configuration_sha256": "b" * 64,
    "file_identity_scheme": "windows-volume-file-id-v1",
    "status": "READY",
    "eligible_count": 2,
    "blocking_count": 0,
    "items": [...],
    "alias_groups": [],
}
```

Required assertions:

```python
def test_custody_round_trip_is_closed_and_deterministic() -> None:
    payload = _valid_custody_payload()
    normalized = validate_source_custody(payload)
    assert normalized["status"] == "READY"
    assert source_custody_sha256(normalized) == source_custody_sha256(payload)


def test_ready_custody_cannot_contain_blockers() -> None:
    payload = _valid_custody_payload()
    payload["blocking_count"] = 1
    with pytest.raises(SourceIntegrityError, match="READY"):
        validate_source_custody(payload)
```

Test exact required fields, enums, lowercase hashes, count consistency, safe relative paths, media metadata closure, file-identity fields, and rejection of authority fields such as `visual_pass`, `engineering_verdict`, `approved`, `repair`, and `publication`.

- [ ] **Step 2: Write failing BLOCKED-artifact tests**

Prove one complete sanitized artifact may contain blocking states:

```python
def test_blocked_custody_reports_sanitized_item_state() -> None:
    payload = _valid_custody_payload()
    payload["status"] = "BLOCKED"
    payload["eligible_count"] = 1
    payload["blocking_count"] = 1
    payload["items"][1]["custody_state"] = "HASH_MISMATCH"
    payload["items"][1]["blocking_reason_code"] = "SOURCE_HASH_MISMATCH"
    normalized = validate_source_custody(payload)
    assert normalized["status"] == "BLOCKED"
```

Validate that `BLOCKED` contains no absolute path, raw identity, or private detail.

- [ ] **Step 3: Write failing alias-group distinction tests**

Alias groups must include `group_type`, sorted source IDs, byte hash, and sorted privacy-safe file-identity hashes. Test that `SAME_FILE_ALIAS` and `DUPLICATE_BYTES` cannot be interchanged.

- [ ] **Step 4: Run tests and confirm import failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_integrity.py `
  -q -p no:cacheprovider
```

Expected: import failure because `cad_agent.source_integrity` does not exist.

- [ ] **Step 5: Implement minimal closed validators**

Use exact root states `READY`/`BLOCKED` and exact item states from the design. Deep-copy returns; sort item and group arrays by stable keys; reject non-finite values and inconsistent counts.

- [ ] **Step 6: Run focused tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
```

Expected: PASS and Ruff exit 0.

- [ ] **Step 7: Commit Task 1**

```powershell
git add cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
git commit -m "contracts: add closed R1C custody evidence"
```

---

## Task 2: Windows final-handle containment, root revision, and file identity

**Files:**

- Modify: `cad_agent/source_integrity.py`
- Modify: `tests/test_cad_agent_source_integrity.py`

**Consumes:** Task 1 validators and an approved root configuration supplied outside R1A.

**Produces:**

- `inspect_source_bundle(*, approved_root_id: str, approved_root_revision: str, approved_root: Path, policy_limits: Mapping[str, int], source_bundle: object) -> dict[str, object]`
- `require_source_custody_match(*, approved_root_id: str, approved_root_revision: str, approved_root: Path, source_bundle: object, custody: object) -> None`
- private Windows-safe-handle helpers for final path, file identity, reparse checks, and configuration hashing

- [ ] **Step 1: Add failing approved-root revision tests**

Test that equal root ID with a changed path or revision produces another `approved_root_configuration_sha256` and makes old custody stale.

```python
def test_root_id_remap_invalidates_custody(tmp_path: Path) -> None:
    first = _inspect_at_root(tmp_path / "first", revision="R1")
    with pytest.raises(SourceIntegrityError, match="root configuration"):
        require_source_custody_match(
            approved_root_id="ROOT-A",
            approved_root_revision="R2",
            approved_root=tmp_path / "second",
            source_bundle=_bundle(),
            custody=first,
        )
```

- [ ] **Step 2: Add failing final-handle containment tests**

Use injectable platform adapters, not sleeps, to simulate:

- path component changed after pre-open checks;
- junction/reparse substitution;
- final opened path outside root;
- opened identity changed after parser phase;
- final path unavailable;
- non-Windows or unsupported platform evidence unable to prove required identity.

Expected behavior: sanitized blocking state or `SourceIntegrityError` for platform invariant failure; never fallback to filename/pre-open resolve.

- [ ] **Step 3: Add failing hardlink/duplicate identity tests**

Test:

- two paths to one file identity become `SAME_FILE_ALIAS`;
- two independent identities with equal bytes become `DUPLICATE_BYTES`;
- identical bytes but replaced file identity invalidate prior custody;
- conflicting declarations for one file identity block;
- raw volume/file ID and absolute path never appear in artifact/error.

- [ ] **Step 4: Run focused tests and confirm API failures**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
```

- [ ] **Step 5: Implement bounded Windows handle adapter**

Port concepts, not AutoCAD policy, from `ExactBaseXrefPolicy.cs`:

- open source read-only;
- obtain OS handle from the custody-owned descriptor;
- use bounded `GetFinalPathNameByHandleW` and `GetFileInformationByHandle`/equivalent identity call;
- normalize the final handle path;
- prove final containment under the approved root;
- reject reparse traversal;
- compare identity before/after inspection.

If final path or identity cannot be proved, fail closed.

- [ ] **Step 6: Implement configuration and privacy-safe identity hashes**

Compute:

```python
approved_root_configuration_sha256 = canonical_json_sha256({
    "schema_version": "approved-source-root-1.0",
    "approved_root_id": approved_root_id,
    "approved_root_revision": approved_root_revision,
    "normalized_root_path": normalized_server_path,
    "file_identity_scheme": "windows-volume-file-id-v1",
    "policy_limits": normalized_limits,
})
```

Only the hash enters artifacts.

Compute item identity from the configuration hash, raw opened-handle identity, and final normalized relative path. Do not serialize raw inputs.

- [ ] **Step 7: Run tests repeatedly and Ruff**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { throw "R1C handle repetition $_ failed" }
}
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
```

- [ ] **Step 8: Commit Task 2**

```powershell
git add cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
git commit -m "security: bind R1C custody to final file identity"
```

---

## Task 3: Read-only media adapters and strict engineer JSON

**Files:**

- Modify: `cad_agent/source_integrity.py`
- Modify: `tests/test_cad_agent_source_integrity.py`

**Consumes:** Task 2 custody-owned descriptor and stable first hash.

**Produces:** bounded image/PDF/CAD-header/JSON observations without parser ownership of the source descriptor.

- [ ] **Step 1: Add failing parser-isolation tests**

Provide a fake parser that closes or seeks its input. Assert the custody descriptor remains valid and the second hash/final identity check still runs.

- [ ] **Step 2: Add failing operation-owned snapshot cleanup tests**

For parsers requiring isolation, create a bounded temp snapshot under the current run temp root. Test:

- snapshot hash equals first source hash;
- snapshot is removed on success and exception;
- manifest/custody does not reference snapshot path;
- original source second hash and final identity remain mandatory.

- [ ] **Step 3: Add failing Pillow/pypdf resource tests**

Synthetic cases:

- valid PNG/JPEG dimensions and DPI;
- truncated/mismatched image;
- decompression-bomb warning/error;
- valid one/multi-page PDF;
- encrypted PDF;
- malformed cross-reference/page tree;
- excessive page count, box dimensions, and source bytes;
- declared media mismatch/polyglot disagreement.

- [ ] **Step 4: Add failing strict JSON tests**

Reject:

- duplicate keys;
- `NaN`, `Infinity`, `-Infinity`;
- malformed UTF-8;
- non-object root;
- excessive depth/key/array/string/byte limits.

Assert original byte SHA remains custody authority and canonical JSON digest is derived metadata only.

- [ ] **Step 5: Run focused tests and confirm failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
```

- [ ] **Step 6: Implement duplicated-handle/snapshot parser boundary**

Keep the original custody descriptor open. Give adapters either a duplicated handle or a bounded snapshot. Always perform the second hash and final-handle checks on the original.

- [ ] **Step 7: Implement bounded media adapters**

- Pillow 12.3.0: `EXTEND_WITH_TEST`; read-only identify/verify; no save/convert/transpose.
- pypdf 6.14.2: `EXTEND_WITH_TEST`; strict structure/page metadata; no rewrite/decrypt/text authority.
- DWG: bounded `AC10xx` header only.
- DXF: header-only first slice; ezdxf remains unused `SPIKE_ONLY` unless a later amendment authorizes it.
- JSON: strict hooks and policy limits.

Parser disagreement becomes a sanitized blocking observation, never a silent priority choice.

- [ ] **Step 8: Run focused tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
```

- [ ] **Step 9: Commit Task 3**

```powershell
git add cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
git commit -m "feat: inspect R1C media through bounded read-only adapters"
```

---

## Task 4: Explicit locators and PDF render provenance

**Files:**

- Create: `cad_agent/source_fusion.py`
- Create: `tests/test_cad_agent_source_fusion.py`

**Consumes:** validated R1A bundle, `READY` custody artifact, existing PDF-render/Primitive artifacts and their checkpoint hashes.

**Produces:**

- `SOURCE_FUSION_SCHEMA_VERSION = "source-fusion-1.0"`
- `class SourceFusionError(ValueError)`
- closed page/region/render-provenance validators
- canonical decimal/coordinate normalization helpers

- [ ] **Step 1: Add failing page locator tests**

Test every R1A page label requires exactly one explicit locator and that label sorting never implies page order. Validate page index, box kind/bounds, rotation, user unit, and custody source hash.

- [ ] **Step 2: Add failing region coordinate tests**

For pixel locators require:

- `RASTER_TOP_LEFT_X_RIGHT_Y_DOWN`;
- exact raster SHA, width, height;
- integer in-bounds coordinates.

For PDF-point locators require:

- `PDF_USER_SPACE_BOTTOM_LEFT_X_RIGHT_Y_UP`;
- exact page locator;
- media/crop box, normalized rotation, user unit;
- canonical non-exponent decimal strings with negative zero refused/normalized.

Add rotated/cropped PDF, ambiguous origin, out-of-bounds, and equivalent-noncanonical number tests.

- [ ] **Step 3: Add failing PDF render-chain tests**

The record must bind:

- custody PDF hash;
- page locator/index;
- selected box/rotation/user unit;
- render DPI and canonical matrix;
- raster convention;
- rendered image hash/dimensions;
- Primitive artifact hash;
- Primitive source-document hash/dimensions/page index.

Test wrong page, DPI, crop, rotation, matrix, raster hash, and Primitive source-document hash.

- [ ] **Step 4: Add direct-image provenance test**

Require Primitive source-document SHA and dimensions to equal custody observations for direct image sources.

- [ ] **Step 5: Run tests and confirm import/API failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
```

- [ ] **Step 6: Implement minimal closed locator/render validators**

No OCR, filename inference, or model mapping. Canonical arrays sort by closed compound keys.

- [ ] **Step 7: Run focused tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
```

- [ ] **Step 8: Commit Task 4**

```powershell
git add cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
git commit -m "contracts: bind R1C page region and render provenance"
```

---

## Task 5: UUID-independent Primitive and Semantic provenance

**Files:**

- Modify: `cad_agent/source_fusion.py`
- Modify: `tests/test_cad_agent_source_fusion.py`

**Consumes:** current-format Primitive/Semantic JSON mappings plus externally verified artifact/checkpoint hashes.

**Produces:**

- deterministic Primitive observation projections/digests
- deterministic Semantic projections/digests
- duplicate-observation groups and ambiguity blockers
- external Semantic-to-Primitive checkpoint binding

- [ ] **Step 1: Add failing Primitive UUID/order invariance tests**

Create equivalent Primitive artifacts with different UUIDs, handles, extraction timestamps, and list order. Require identical canonical observation digests and final provenance hash.

- [ ] **Step 2: Add failing duplicate-observation tests**

For exactly identical closed projections require one group with `occurrence_count` and deterministic labels. If Semantic references only an indistinguishable subset, require `DUPLICATE_OBSERVATION_AMBIGUITY`.

- [ ] **Step 3: Add failing Semantic UUID/order invariance tests**

Create equivalent Semantic artifacts with different part/constraint UUIDs and order; map legacy primitive IDs to the same deterministic Primitive digests; require identical Semantic projections.

- [ ] **Step 4: Add current-producer compatibility tests**

Use a current-format `PrimitiveIRRef` containing filename/count and omitted optional SHA. Bind externally using existing manifest/checkpoint Primitive hash. Require PASS.

When optional SHA is present, require exact equality. Wrong filename/count/checkpoint hash must fail.

- [ ] **Step 5: Run focused tests and confirm failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
```

- [ ] **Step 6: Implement closed Primitive projection**

Exclude UUID, handle, volatile timestamps, input order, and unapproved validation notes. Include source/render binding, type/source/layer, normalized geometry/text, confidence, trace, and calibration projection.

- [ ] **Step 7: Implement duplicate multiset rule**

Canonical duplicate groups contain digest, multiplicity, and labels derived only from digest/count. Never sort or identify canonical occurrences by legacy UUID.

- [ ] **Step 8: Implement Semantic external checkpoint binding**

Bind Semantic file hash and associated Primitive checkpoint hash from the run manifest. Validate `PrimitiveIRRef` filename/count and optional SHA when present. Do not change Semantic models or producer code.

- [ ] **Step 9: Run focused tests, permutation loop, and Ruff**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { throw "R1C provenance repetition $_ failed" }
}
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
```

- [ ] **Step 10: Commit Task 5**

```powershell
git add cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
git commit -m "feat: project deterministic R1C IR provenance"
```

---

## Task 6: Deterministic conflicts, replay-safe resolutions, and fusion status

**Files:**

- Modify: `cad_agent/source_fusion.py`
- Modify: `tests/test_cad_agent_source_fusion.py`

**Consumes:** Tasks 4-5 locators/render/provenance and Task 1-3 custody.

**Produces:**

- `build_source_fusion_packet(...) -> dict[str, object]`
- `validate_source_fusion_packet(payload: object) -> dict[str, object]`
- `source_fusion_sha256(payload: object) -> str`
- `require_source_fusion_match(...) -> None`
- `validate_source_conflict_resolution(payload: object) -> dict[str, object]`

- [ ] **Step 1: Add failing conflict preservation tests**

Cover every required conflict type:

- byte identity;
- media/parser observation;
- locator/render;
- calibration;
- measurement/geometry/material/decision;
- duplicate observation ambiguity.

Assert source count, confidence, role rank, parser choice, and list order never delete a conflicting evidence reference.

- [ ] **Step 2: Add failing fusion-input hash tests**

Require `fusion_input_sha256` to hash bundle/custody/root/locator/render/provenance/conflict content before resolutions. Shuffling caller input must not change it.

- [ ] **Step 3: Add failing resolution replay tests**

A valid `source-conflict-resolution-1.0` binds:

- run/conflict/subject;
- exact compared evidence hashes;
- bundle/custody/root hashes;
- exact `fusion_input_sha256`;
- selected resolution;
- approval reference;
- issued/expiry UTC;
- `APPROVED` status.

Test replay across another conflict, run, root revision, source bundle, custody hash, compared evidence, fusion input, or expired time. All must fail.

- [ ] **Step 4: Add failing status tests**

Rules:

- custody not `READY` -> no fusion packet;
- stale hashes/approval -> `STALE` or raised match failure;
- blocking unresolved conflict -> `BLOCKED_UNRESOLVED`;
- all inputs exact and no blocker -> `READY`;
- `READY` with authority fields or unresolved blockers -> reject.

- [ ] **Step 5: Run focused tests and confirm failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
```

- [ ] **Step 6: Implement deterministic conflict construction**

Generate conflict IDs from canonical conflict content. Preserve compared evidence and normalized values. Role rank is display ordering only.

- [ ] **Step 7: Implement closed resolution validator**

R1C validates externally issued approval evidence but does not issue approval. An engineer `DECISION` source does not satisfy the resolution contract.

- [ ] **Step 8: Implement packet status and stale matching**

`require_source_fusion_match()` returns only for an exact current match; otherwise raises a closed `SourceFusionError` without leaking paths/content.

- [ ] **Step 9: Run focused tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
```

- [ ] **Step 10: Commit Task 6**

```powershell
git add cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
git commit -m "feat: preserve R1C conflicts and validate resolutions"
```

---

## Task 7: Bind R1C references through the existing manifest owner

**Files:**

- Modify: `cad_agent/manifest.py`
- Modify: `cad_agent/pdf.py`
- Modify: `tests/test_cad_agent_source_bundle_manifest.py`

**Consumes:** validated custody/fusion artifacts and hashes.

**Produces:**

- `SOURCE_CUSTODY_REFERENCE_SCHEMA_VERSION = "source-custody-reference-1.0"`
- `SOURCE_FUSION_REFERENCE_SCHEMA_VERSION = "source-fusion-reference-1.0"`
- reference validators
- `bind_source_custody(...)`
- `bind_source_fusion(...)`
- manifest-level exact match helpers

- [ ] **Step 1: Add failing custody-reference tests**

Exact fields:

```python
{
    "schema_version": "source-custody-reference-1.0",
    "source_bundle_sha256": "...",
    "approved_root_configuration_sha256": "...",
    "source_custody_sha256": "...",
    "status": "READY",
    "item_count": 4,
    "eligible_count": 4,
    "blocking_count": 0,
}
```

Reject inconsistent counts/readiness.

- [ ] **Step 2: Add failing fusion-reference tests**

Exact fields:

```python
{
    "schema_version": "source-fusion-reference-1.0",
    "source_bundle_sha256": "...",
    "source_custody_sha256": "...",
    "approved_root_configuration_sha256": "...",
    "source_fusion_sha256": "...",
    "fusion_input_sha256": "...",
    "status": "READY",
    "conflict_count": 0,
    "unresolved_count": 0,
    "resolution_count": 0,
}
```

Reject `READY` with blockers/unresolved conflicts.

- [ ] **Step 3: Add legacy and unequal-rebind tests**

Prove:

- legacy image/PDF manifests are unchanged when R1C fields are absent;
- readers validate only present fields;
- equal bind is idempotent;
- unequal bind fails;
- fusion bind requires exact bundle/custody/root match;
- manifests store references only, never full item/provenance/conflict arrays.

- [ ] **Step 4: Run focused/regression tests and confirm failures**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_bundle.py `
  tests/test_cad_agent_source_bundle_manifest.py `
  tests/test_cad_agent_cli.py `
  tests/test_cad_agent_pdf.py `
  -q -p no:cacheprovider
```

- [ ] **Step 5: Implement validators/binders following the R1B pattern**

Deep-copy manifests, validate derived artifacts first, bind all context hashes, refuse unequal rebinding, and map domain errors to `ManifestError` without private detail.

- [ ] **Step 6: Extend readers only when keys exist**

Preserve manifest schema versions and draft-reference safety defaults. Do not inject absent R1C keys.

- [ ] **Step 7: Run focused/regression tests and Ruff**

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

- [ ] **Step 8: Commit Task 7**

```powershell
git add cad_agent/manifest.py cad_agent/pdf.py tests/test_cad_agent_source_bundle_manifest.py
git commit -m "manifest: bind R1C custody and fusion references"
```

---

## Task 8: Security, resource, determinism, and static-boundary hardening

**Files:**

- Modify: `tests/test_cad_agent_source_integrity.py`
- Modify: `tests/test_cad_agent_source_fusion.py`
- Modify only for proven defects: `cad_agent/source_integrity.py`, `cad_agent/source_fusion.py`

**Produces:** complete synthetic acceptance matrix; no new public API.

- [ ] **Step 1: Add fixed malformed corpus**

Include valid/truncated/mismatched PNG/JPEG/PDF/DWG-header/DXF/JSON; encrypted/malformed PDF; duplicate JSON keys; malformed UTF-8; non-finite values; oversized limits.

- [ ] **Step 2: Add deterministic race/path hooks**

No sleep-based tests. Inject component replacement, reparse substitution, source mutation, source replacement with same bytes, parser closure, and identity change.

- [ ] **Step 3: Add permutation/rebuild determinism tests**

Require byte-identical custody/fusion hashes across:

- reversed/shuffled inputs;
- repeated runs;
- different UUIDs/list order in equivalent IR;
- equal JSON values with different input key order;
- duplicate observation multiplicity.

- [ ] **Step 4: Add privacy/static AST tests**

Prove:

- no network/subprocess/AutoCAD/File IPC/OCR/model imports;
- source inspection has no save/write/replace/unlink path for approved source files;
- operation-owned temp cleanup is bounded;
- no visual PASS, repair, publisher, or CAD mutation authority;
- no absolute path/raw file identity in canonical artifacts or closed errors.

- [ ] **Step 5: Run complete focused R1 suite**

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

- [ ] **Step 6: Run architecture and canonical verification without local AutoCAD**

```powershell
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check `
  --repo-root . `
  --baseline contracts/reuse-integration/architecture-boundaries.json

.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Record AutoCAD .NET, AutoCAD Mechanical live, and private-data gates as `NOT RUN`/`SKIP`, never PASS.

- [ ] **Step 7: Commit Task 8**

Stage only files that actually changed:

```powershell
git add tests/test_cad_agent_source_integrity.py tests/test_cad_agent_source_fusion.py
if (git diff --name-only | Select-String '^cad_agent/source_(integrity|fusion)\.py$') {
  git add cad_agent/source_integrity.py cad_agent/source_fusion.py
}
git diff --cached --name-only
git commit -m "test: harden R1C custody and fusion boundaries"
```

---

## Task 9: Implementation record, exact audit, and draft PR handoff

**Files:**

- Create: `docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md`

**Consumes:** exact runtime Issue, commit chain, changed files, verification, hosted runs, and Cell 5 findings.

- [ ] **Step 1: Require concrete runtime identity**

Before executing any runtime task, the runtime Issue must set these environment values:

```powershell
$runtimeBase = $env:CAD_AGENT_R1C_RUNTIME_BASE_SHA
$runtimeBranch = $env:CAD_AGENT_R1C_RUNTIME_BRANCH
if (-not $runtimeBase -or -not $runtimeBranch) {
  throw 'R1C runtime exact base and branch must come from the approved runtime Issue'
}
```

- [ ] **Step 2: Write exact implementation record**

Include:

- Issue/base/branch/final head;
- bounded commits;
- exact files;
- internal reuse and external classifications;
- Cell 5 blocker dispositions;
- tests and canonical verifier counts;
- hosted run IDs and synthetic merge SHA;
- private/live/AutoCAD .NET `NOT RUN`/`SKIP` states;
- migration/rollback and retained locks.

- [ ] **Step 3: Audit exact allowlist**

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
$actual = git diff --name-only "$runtimeBase...HEAD" | Sort-Object
$comparison = Compare-Object $expected $actual
if ($comparison) {
  $comparison | Format-Table | Out-String | Write-Host
  throw 'R1C runtime allowlist mismatch'
}
```

The runtime Issue may narrow this expected list; the command must then use that exact approved list.

- [ ] **Step 4: Run final exact-head verification**

```powershell
git diff --check "$runtimeBase...HEAD"
.\scripts\verify.ps1 -SkipAutoCADDotNet
git status --short
```

Expected: verifier exit 0 and clean worktree after committing the record.

- [ ] **Step 5: Commit the implementation record**

```powershell
git add docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md
git commit -m "docs: record R1C source integrity verification"
```

- [ ] **Step 6: Push normally and open/retain draft PR**

```powershell
git push -u origin $runtimeBranch
```

No force-push, rebase, amend, squash, ready-for-review transition, or merge.

- [ ] **Step 7: Stop for independent review**

Post exact head and PR to Cell 5 and Master PO. Runtime remains unaccepted until hosted tests, Reuse Declaration, Cell 5 review, and Master PO exact-head review pass.

---

## Planning-only verification for PR #78

The writer of this planning PR must:

```powershell
git diff --check d71d0c97e28e03cb430f05589c8381b4ede70e66...HEAD
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

When the local worktree is unavailable, report local verification as `NOT RUN`; hosted checks remain required. The final cumulative diff must contain exactly:

- `docs/superpowers/specs/2026-08-06-r1c-source-integrity-fusion-design.md`
- `docs/superpowers/plans/2026-08-06-r1c-source-integrity-fusion.md`

PR #78 remains `OPEN/DRAFT` until the second Cell 5 review and Master PO decision.

## Plan self-review

### Spec coverage

- root revision, privacy-safe identity, alias/duplicate distinction: Tasks 1-2;
- final-handle containment and TOCTOU: Task 2;
- parser isolation and strict JSON: Task 3;
- PDF/render/coordinate chain: Task 4;
- UUID-independent IR provenance and current Semantic compatibility: Task 5;
- conflict preservation and replay-safe approval: Task 6;
- sole manifest owner: Task 7;
- security/resource/determinism: Task 8;
- exact evidence/allowlist/handoff: Task 9.

### Name/type consistency

- custody statuses are `READY` and `BLOCKED`;
- fusion statuses are `READY`, `BLOCKED_UNRESOLVED`, and `STALE`;
- identity scheme is `windows-volume-file-id-v1`;
- pixel convention is `RASTER_TOP_LEFT_X_RIGHT_Y_DOWN`;
- PDF convention is `PDF_USER_SPACE_BOTTOM_LEFT_X_RIGHT_Y_UP`;
- conflict resolutions bind `fusion_input_sha256` before resolution application.

### Placeholder scan

No guessed runtime SHA or branch is embedded. Execution is guarded by exact values supplied by the future approved runtime Issue.

## Execution handoff

After this planning PR is accepted, Master PO must create a separate runtime Issue with:

- exact implementation base and branch;
- accepted/narrowed eight-path allowlist;
- root/identity policy limits;
- approved dependency posture with no lock change;
- exact offline verification and hosted gates;
- Cell 5 second-review disposition;
- truthful `NOT RUN` states for AutoCAD and private data.

Recommended execution mode: subagent-driven development with one writer and independent requirements/security review after each bounded task.
