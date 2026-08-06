# R1C Source Integrity and Deterministic Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-Python, fail-closed source-custody and deterministic fusion-evidence boundary that composes accepted R1A/R1B and current Primitive/Semantic IR artifacts without adding another truth store or any visual/engineering authority.

**Architecture:** Preserve `source-bundle-1.0`. Create adjacent `source-custody-1.0` and `source-fusion-1.0` artifacts, use a bounded Windows final-handle adapter for source identity/containment, project IR observations into UUID-independent canonical digests, and bind only small closed references through the existing `cad_agent.manifest` owner.

**Tech Stack:** Windows; Python 3.11; stdlib `hashlib`, `json`, `os`, `pathlib`, `stat`, `ctypes`, and `msvcrt`; existing locked Pillow 12.3.0 and pypdf 6.14.2; pytest; Ruff; repository architecture checker and canonical verifier. Locked ezdxf 1.4.4 remains spike-only and is not used by the first runtime slice.

## Global constraints

- This plan is not executable until a separate runtime Issue supplies the exact implementation base, branch, and final allowlist.
- Runtime implementation remains locked while PR #78 is planning-only.
- Preserve `cad_agent/source_bundle.py`, `source-bundle-1.0`, current Primitive/Semantic models, current CLI producers, and optional `PrimitiveIRRef.sha256` behavior.
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

**Interfaces:**

- Consumes: `validate_source_bundle(payload)`, `source_bundle_sha256(payload)`, and `canonical_json_sha256(payload)`.
- Produces:
  - `SOURCE_CUSTODY_SCHEMA_VERSION = "source-custody-1.0"`
  - `class SourceIntegrityError(ValueError)`
  - `validate_source_custody(payload: object) -> dict[str, object]`
  - `source_custody_sha256(payload: object) -> str`

- [ ] **Step 1: Write the concrete valid fixture and failing round-trip test**

```python
def _valid_custody_payload() -> dict[str, object]:
    return {
        "schema_version": "source-custody-1.0",
        "bundle_id": "BUNDLE-001",
        "run_id": "RUN-001",
        "source_bundle_sha256": "a" * 64,
        "approved_root_id": "ROOT-SYNTHETIC",
        "approved_root_configuration_sha256": "b" * 64,
        "file_identity_scheme": "windows-volume-file-id-v1",
        "status": "READY",
        "eligible_count": 1,
        "blocking_count": 0,
        "items": [
            {
                "source_id": "IMAGE-001",
                "kind": "IMAGE",
                "role": "DETAIL",
                "relative_path": "sources/detail.png",
                "declared_sha256": "c" * 64,
                "observed_sha256": "c" * 64,
                "size_bytes": 128,
                "declared_media_type": "image/png",
                "observed_media_type": "image/png",
                "media_metadata": {
                    "format": "PNG",
                    "width_px": 16,
                    "height_px": 16,
                    "mode": "RGB",
                    "dpi_x": None,
                    "dpi_y": None,
                },
                "page_ids": [],
                "region_ids": ["REGION-DETAIL-001"],
                "file_identity_scheme": "windows-volume-file-id-v1",
                "file_identity_sha256": "d" * 64,
                "alias_group_id": None,
                "custody_state": "VERIFIED",
                "blocking_reason_code": None,
            }
        ],
        "alias_groups": [],
    }


def test_custody_round_trip_is_closed_and_deterministic() -> None:
    payload = _valid_custody_payload()
    normalized = validate_source_custody(payload)
    assert normalized["status"] == "READY"
    assert source_custody_sha256(normalized) == source_custody_sha256(payload)
```

- [ ] **Step 2: Write failing readiness/count and authority tests**

```python
def test_ready_custody_cannot_contain_blockers() -> None:
    payload = _valid_custody_payload()
    payload["blocking_count"] = 1
    with pytest.raises(SourceIntegrityError, match="READY"):
        validate_source_custody(payload)


def test_custody_rejects_visual_authority() -> None:
    payload = _valid_custody_payload()
    payload["visual_pass"] = True
    with pytest.raises(SourceIntegrityError, match="unsupported"):
        validate_source_custody(payload)
```

Add exact tests for required/unknown fields, enums, lowercase hashes, count consistency, safe relative paths, media metadata closure, and rejection of `engineering_verdict`, `approved`, `repair`, and `publication`.

- [ ] **Step 3: Write failing BLOCKED artifact and alias-group tests**

Prove one complete sanitized `BLOCKED` artifact is valid, but `READY` with a blocking item is invalid. Prove `SAME_FILE_ALIAS` and `DUPLICATE_BYTES` have distinct group types and identity evidence.

- [ ] **Step 4: Run tests and confirm import failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
```

Expected: collection/import failure because `cad_agent.source_integrity` does not exist.

- [ ] **Step 5: Implement minimal closed validators**

Implement exact root statuses `READY` and `BLOCKED`, exact item states from the design, deep-copy returns, stable sorting, finite-value checks, and count/group invariants.

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

**Interfaces:**

- Produces:
  - `inspect_source_bundle(*, approved_root_id: str, approved_root_revision: str, approved_root: Path, policy_limits: Mapping[str, int], source_bundle: object) -> dict[str, object]`
  - `require_source_custody_match(*, approved_root_id: str, approved_root_revision: str, approved_root: Path, policy_limits: Mapping[str, int], source_bundle: object, custody: object) -> None`

- [ ] **Step 1: Add failing approved-root revision test**

```python
def test_root_id_remap_invalidates_custody(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    custody = _inspect_at_root(first_root, revision="R1")
    with pytest.raises(SourceIntegrityError, match="root configuration"):
        require_source_custody_match(
            approved_root_id="ROOT-A",
            approved_root_revision="R2",
            approved_root=second_root,
            policy_limits=_policy_limits(),
            source_bundle=_bundle_for_root(second_root),
            custody=custody,
        )
```

- [ ] **Step 2: Add deterministic final-handle refusal tests**

Use injected platform adapters, not sleeps, for path-component replacement, junction/reparse substitution, final path outside root, identity change after parser work, and unavailable final-path evidence. No fallback to filename or pre-open `resolve()` is allowed.

- [ ] **Step 3: Add hardlink/duplicate tests**

Prove:

- same opened file identity -> `SAME_FILE_ALIAS`;
- independent identities with equal bytes -> `DUPLICATE_BYTES`;
- replacement with identical bytes but another identity invalidates custody;
- conflicting declarations for one identity block;
- raw identity and absolute path never appear in artifact/error.

- [ ] **Step 4: Run tests and confirm API failures**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
```

- [ ] **Step 5: Implement bounded Windows handle adapter**

Port only the safe-handle concepts from `ExactBaseXrefPolicy.cs`: read-only open, bounded `GetFinalPathNameByHandleW`, file information by handle, normalized final path, post-open containment, reparse refusal, and identity comparison before/after inspection. Failure to prove containment/identity is fail-closed.

- [ ] **Step 6: Implement root and privacy-safe identity hashes**

```python
approved_root_configuration_sha256 = canonical_json_sha256(
    {
        "schema_version": "approved-source-root-1.0",
        "approved_root_id": approved_root_id,
        "approved_root_revision": approved_root_revision,
        "normalized_root_path": normalized_server_path,
        "file_identity_scheme": "windows-volume-file-id-v1",
        "policy_limits": normalized_limits,
    }
)
```

Only the hash enters artifacts. Compute `file_identity_sha256` from the root configuration hash, raw opened-handle volume/file identity, and final normalized relative path; never serialize raw inputs.

- [ ] **Step 7: Run repeated tests and Ruff**

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

**Interfaces:**

- Consumes: Task 2 custody-owned descriptor and stable first hash.
- Produces: bounded image/PDF/CAD-header/JSON observations without parser ownership of the source descriptor.

- [ ] **Step 1: Add parser-isolation and cleanup tests**

Use a fake parser that closes/seeks its input. Prove the custody descriptor remains usable. For an operation-owned snapshot, prove hash equality, cleanup on success/error, no manifest reference, and mandatory second hash/final identity check on the original.

- [ ] **Step 2: Add Pillow/pypdf resource tests**

Cover valid and truncated PNG/JPEG, decompression-bomb refusal, valid and malformed/encrypted PDF, excessive page/box/byte limits, declared-media mismatch, and parser disagreement.

- [ ] **Step 3: Add strict JSON tests**

```python
def test_engineer_json_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "decision.json"
    path.write_bytes(b'{"value":1,"value":2}')
    custody = _inspect_engineer_record(path)
    assert custody["status"] == "BLOCKED"
    assert custody["items"][0]["blocking_reason_code"] == "JSON_DUPLICATE_KEY"
```

Also reject malformed UTF-8, non-object root, `NaN`/Infinity, and excessive byte/depth/key/array/string limits.

- [ ] **Step 4: Run tests and confirm failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
```

- [ ] **Step 5: Implement duplicated-handle/snapshot boundary**

Keep the original custody descriptor open. Parser adapters receive a duplicated handle or a bounded snapshot. Always second-hash and final-identity-check the original.

- [ ] **Step 6: Implement bounded adapters**

- Pillow 12.3.0: read-only identify/verify; no save/convert/transpose.
- pypdf 6.14.2: strict page/box/rotation/user-unit observations; no rewrite/decrypt/text authority.
- DWG: bounded `AC10xx` header only.
- DXF: header only; ezdxf remains unused spike-only.
- JSON: duplicate-key and non-finite refusal plus policy limits.

- [ ] **Step 7: Run focused tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
```

- [ ] **Step 8: Commit Task 3**

```powershell
git add cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
git commit -m "feat: inspect R1C media through bounded read-only adapters"
```

---

## Task 4: Explicit locators and PDF render provenance

**Files:**

- Create: `cad_agent/source_fusion.py`
- Create: `tests/test_cad_agent_source_fusion.py`

**Interfaces:**

- Produces:
  - `SOURCE_FUSION_SCHEMA_VERSION = "source-fusion-1.0"`
  - `class SourceFusionError(ValueError)`
  - `validate_page_locators(*, source_bundle: object, custody: object, page_locators: object) -> list[dict[str, object]]`
  - `validate_region_locators(*, custody: object, page_locators: object, region_locators: object) -> list[dict[str, object]]`
  - `validate_render_provenance(*, custody: object, page_locators: object, render_provenance: object, primitive_documents: object, checkpoint_bindings: object) -> list[dict[str, object]]`

- [ ] **Step 1: Add page and region locator tests**

Require exactly one explicit mapping per R1A label. For pixels require `RASTER_TOP_LEFT_X_RIGHT_Y_DOWN`, exact raster SHA/dimensions, and integer bounds. For PDF points require `PDF_USER_SPACE_BOTTOM_LEFT_X_RIGHT_Y_UP`, page box, rotation, user unit, and canonical decimal strings.

- [ ] **Step 2: Add PDF render-chain tests**

Bind custody PDF hash, page index/box/rotation/user unit, DPI/matrix, rendered image hash/dimensions, Primitive artifact hash, and Primitive source-document hash/dimensions/page index. Test wrong page, DPI, crop, rotation, matrix, raster hash, and Primitive source hash.

- [ ] **Step 3: Add direct-image provenance test**

```python
def test_direct_image_primitive_source_must_match_custody() -> None:
    with pytest.raises(SourceFusionError, match="source_document sha256"):
        validate_render_provenance(
            custody=_image_custody(observed_sha256="a" * 64),
            page_locators=[],
            render_provenance=[],
            primitive_documents=[_primitive_document(source_sha256="b" * 64)],
            checkpoint_bindings=_checkpoint_bindings(),
        )
```

- [ ] **Step 4: Run tests and confirm import failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
```

- [ ] **Step 5: Implement closed locator/render validators**

No OCR, filename inference, or model mapping. Normalize finite PDF decimal values to non-exponent strings and sort arrays by closed compound keys.

- [ ] **Step 6: Run focused tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
```

- [ ] **Step 7: Commit Task 4**

```powershell
git add cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
git commit -m "contracts: bind R1C page region and render provenance"
```

---

## Task 5: UUID-independent Primitive and Semantic provenance

**Files:**

- Modify: `cad_agent/source_fusion.py`
- Modify: `tests/test_cad_agent_source_fusion.py`

**Interfaces:**

- Produces:
  - `project_primitive_observations(*, primitive_documents: object, render_provenance: object, checkpoint_bindings: object) -> list[dict[str, object]]`
  - `project_semantic_observations(*, semantic_documents: object, primitive_observations: object, checkpoint_bindings: object) -> list[dict[str, object]]`

- [ ] **Step 1: Add Primitive UUID/order invariance test**

Build equivalent Primitive artifacts with different UUIDs, handles, extraction timestamps, and order. Require identical observation projections/hashes.

- [ ] **Step 2: Add duplicate-observation ambiguity test**

Represent identical closed projections as one digest plus multiplicity. Require `DUPLICATE_OBSERVATION_AMBIGUITY` when Semantic selects an indistinguishable strict subset.

- [ ] **Step 3: Add Semantic UUID/order invariance and producer compatibility tests**

Use a current-format `PrimitiveIRRef` with filename/count and omitted optional SHA; bind externally through checkpoint hashes. When optional SHA exists, require equality.

```python
def test_current_semantic_without_optional_primitive_sha_is_supported() -> None:
    projected = project_semantic_observations(
        semantic_documents=[_semantic_document(primitive_sha256=None)],
        primitive_observations=_primitive_observations(),
        checkpoint_bindings=_checkpoint_bindings(),
    )
    assert projected[0]["primitive_checkpoint_sha256"] == "a" * 64
```

- [ ] **Step 4: Run tests and confirm failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
```

- [ ] **Step 5: Implement closed projections**

Exclude UUID, handle, volatile timestamps, input order, and unapproved notes. Include source/render binding, normalized geometry/text/trace/calibration, and checkpoint hashes. Duplicate labels derive only from content digest and multiplicity.

- [ ] **Step 6: Run permutation loop and Ruff**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { throw "R1C provenance repetition $_ failed" }
}
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
```

- [ ] **Step 7: Commit Task 5**

```powershell
git add cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
git commit -m "feat: project deterministic R1C IR provenance"
```

---

## Task 6: Deterministic conflicts, replay-safe resolutions, and fusion status

**Files:**

- Modify: `cad_agent/source_fusion.py`
- Modify: `tests/test_cad_agent_source_fusion.py`

**Interfaces:**

- Produces:
  - `validate_source_conflict_resolution(payload: object) -> dict[str, object]`
  - `build_source_fusion_packet(*, source_bundle: object, custody: object, page_locators: object, region_locators: object, render_provenance: object, primitive_documents: object, semantic_documents: object, checkpoint_bindings: object, resolution_references: object = ()) -> dict[str, object]`
  - `validate_source_fusion_packet(payload: object) -> dict[str, object]`
  - `source_fusion_sha256(payload: object) -> str`
  - `require_source_fusion_match(*, source_bundle: object, custody: object, page_locators: object, region_locators: object, render_provenance: object, primitive_documents: object, semantic_documents: object, checkpoint_bindings: object, resolution_references: object, fusion: object) -> None`

- [ ] **Step 1: Add conflict-preservation tests**

Cover byte identity, media/parser, locator/render, calibration, measurement, geometry, material, decision, and duplicate-observation conflicts. Prove source count, confidence, role rank, parser choice, and list order never discard evidence.

- [ ] **Step 2: Add fusion-input hash test**

Require `fusion_input_sha256` to cover bundle/custody/root/locator/render/provenance/conflict content before resolutions and remain invariant to input permutation.

- [ ] **Step 3: Add replay/expiry tests**

A resolution binds run/conflict/subject, exact compared evidence hashes, bundle/custody/root hashes, exact `fusion_input_sha256`, selected resolution, approval reference, issued/expiry UTC, and `APPROVED`. Replay across any changed context or expiry fails.

- [ ] **Step 4: Add status tests**

```python
def test_unresolved_measurement_conflict_blocks_ready() -> None:
    packet = build_source_fusion_packet(**_conflicting_measurement_inputs())
    assert packet["status"] == "BLOCKED_UNRESOLVED"
    assert packet["conflicts"][0]["conflict_type"] == "MEASUREMENT_CONFLICT"
```

Also test custody not READY, stale hashes/approval, exact READY, and rejection of visual/repair/publication authority.

- [ ] **Step 5: Run tests and confirm failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
```

- [ ] **Step 6: Implement conflict construction, resolution validation, status, and stale matching**

Generate conflict IDs from canonical content. R1C validates externally issued approval evidence but does not issue approval. `require_source_fusion_match()` returns only for an exact current match.

- [ ] **Step 7: Run focused tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
```

- [ ] **Step 8: Commit Task 6**

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

**Interfaces:**

- Produces:
  - `SOURCE_CUSTODY_REFERENCE_SCHEMA_VERSION = "source-custody-reference-1.0"`
  - `SOURCE_FUSION_REFERENCE_SCHEMA_VERSION = "source-fusion-reference-1.0"`
  - `validate_source_custody_reference(value: object) -> dict[str, object]`
  - `validate_source_fusion_reference(value: object) -> dict[str, object]`
  - `bind_source_custody(manifest: Mapping[str, object], source_bundle: object, custody: object) -> dict[str, Any]`
  - `bind_source_fusion(manifest: Mapping[str, object], source_bundle: object, custody: object, fusion: object) -> dict[str, Any]`
  - `require_manifest_source_custody_match(manifest: Mapping[str, object], source_bundle: object, custody: object) -> None`
  - `require_manifest_source_fusion_match(manifest: Mapping[str, object], source_bundle: object, custody: object, fusion: object) -> None`

- [ ] **Step 1: Add concrete custody-reference tests**

```python
def _custody_reference() -> dict[str, object]:
    return {
        "schema_version": "source-custody-reference-1.0",
        "source_bundle_sha256": "a" * 64,
        "approved_root_configuration_sha256": "b" * 64,
        "source_custody_sha256": "c" * 64,
        "status": "READY",
        "item_count": 4,
        "eligible_count": 4,
        "blocking_count": 0,
    }
```

Reject inconsistent counts/readiness and unknown fields.

- [ ] **Step 2: Add concrete fusion-reference tests**

```python
def _fusion_reference() -> dict[str, object]:
    return {
        "schema_version": "source-fusion-reference-1.0",
        "source_bundle_sha256": "a" * 64,
        "source_custody_sha256": "c" * 64,
        "approved_root_configuration_sha256": "b" * 64,
        "source_fusion_sha256": "d" * 64,
        "fusion_input_sha256": "e" * 64,
        "status": "READY",
        "conflict_count": 0,
        "unresolved_count": 0,
        "resolution_count": 0,
    }
```

Reject READY with blockers/unresolved conflicts.

- [ ] **Step 3: Add legacy and unequal-rebind tests**

Prove legacy image/PDF manifests remain unchanged, readers validate only present fields, equal bind is idempotent, unequal bind fails, fusion requires exact bundle/custody/root match, and manifests store references only.

- [ ] **Step 4: Run focused/regression tests and confirm failures**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_bundle.py `
  tests/test_cad_agent_source_bundle_manifest.py `
  tests/test_cad_agent_cli.py `
  tests/test_cad_agent_pdf.py `
  -q -p no:cacheprovider
```

- [ ] **Step 5: Implement validators/binders following R1B**

Deep-copy manifests, validate artifacts first, bind context hashes, refuse unequal rebinding, and map errors to `ManifestError` without private detail. Extend readers only when keys exist.

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

- [ ] **Step 7: Commit Task 7**

```powershell
git add cad_agent/manifest.py cad_agent/pdf.py tests/test_cad_agent_source_bundle_manifest.py
git commit -m "manifest: bind R1C custody and fusion references"
```

---

## Task 8: Security, resource, determinism, and static-boundary hardening

**Files:**

- Modify: `tests/test_cad_agent_source_integrity.py`
- Modify: `tests/test_cad_agent_source_fusion.py`
- Modify only for a proven defect: `cad_agent/source_integrity.py`, `cad_agent/source_fusion.py`

- [ ] **Step 1: Add fixed malformed and resource corpus**

Include valid/truncated/mismatched PNG/JPEG/PDF/DWG-header/DXF/JSON, encrypted/malformed PDF, duplicate JSON keys, malformed UTF-8, non-finite values, and oversized limits.

- [ ] **Step 2: Add deterministic race/path hooks**

Inject component replacement, reparse substitution, source mutation, same-byte identity replacement, parser closure, and identity change. Do not use sleeps.

- [ ] **Step 3: Add permutation/rebuild determinism tests**

Require byte-identical custody/fusion hashes across reversed inputs, repeated runs, different UUIDs/order in equivalent IR, different JSON key order, and duplicate-observation multiplicity.

- [ ] **Step 4: Add privacy/static AST tests**

Prove no network/subprocess/AutoCAD/File IPC/OCR/model imports; no approved-source write/save/replace/unlink; bounded temp cleanup; no visual/repair/publication authority; and no absolute path/raw identity leakage.

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

```powershell
git add tests/test_cad_agent_source_integrity.py tests/test_cad_agent_source_fusion.py
$productionChanges = git diff --name-only | Select-String '^cad_agent/source_(integrity|fusion)\.py$'
if ($productionChanges) {
  git add cad_agent/source_integrity.py cad_agent/source_fusion.py
}
git diff --cached --name-only
git commit -m "test: harden R1C custody and fusion boundaries"
```

---

## Task 9: Implementation record, exact audit, and draft PR handoff

**Files:**

- Create: `docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md`

- [ ] **Step 1: Require concrete runtime identity**

```powershell
$runtimeBase = $env:CAD_AGENT_R1C_RUNTIME_BASE_SHA
$runtimeBranch = $env:CAD_AGENT_R1C_RUNTIME_BRANCH
if (-not $runtimeBase -or -not $runtimeBranch) {
  throw 'R1C runtime exact base and branch must come from the approved runtime Issue'
}
```

- [ ] **Step 2: Write the exact implementation record**

Record Issue/base/branch/final head, bounded commits, exact files, internal/external reuse, Cell 5 dispositions, test/verifier counts, hosted run IDs/synthetic merge, truthful private/live/AutoCAD states, migration/rollback, and retained locks.

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

The runtime Issue may narrow this list; the command must use its exact approved list.

- [ ] **Step 4: Run final exact-head verification**

```powershell
git diff --check "$runtimeBase...HEAD"
.\scripts\verify.ps1 -SkipAutoCADDotNet
git status --short
```

Expected: verifier exit 0 and a clean worktree after the record commit.

- [ ] **Step 5: Commit, push, and stop**

```powershell
git add docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md
git commit -m "docs: record R1C source integrity verification"
git push -u origin $runtimeBranch
```

Open/retain a draft PR. Do not mark ready or merge. Post the exact head to Cell 5 and Master PO.

---

## Planning-only verification for PR #78

```powershell
git diff --check d71d0c97e28e03cb430f05589c8381b4ede70e66...HEAD
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

When no local worktree is available, report local verification as `NOT RUN`; hosted checks remain required. The cumulative planning diff must contain exactly:

- `docs/superpowers/specs/2026-08-06-r1c-source-integrity-fusion-design.md`
- `docs/superpowers/plans/2026-08-06-r1c-source-integrity-fusion.md`

PR #78 remains `OPEN/DRAFT` until the second Cell 5 review and Master PO decision.

## Plan self-review

### Spec coverage

- root revision, privacy-safe identity, aliases/duplicates, final-handle containment: Tasks 1-2;
- parser isolation and strict JSON: Task 3;
- PDF/render/coordinate chain: Task 4;
- UUID-independent IR provenance and current Semantic compatibility: Task 5;
- conflict preservation and replay-safe approval: Task 6;
- sole manifest owner: Task 7;
- security/resource/determinism: Task 8;
- exact evidence/allowlist/handoff: Task 9.

### Name/type consistency

- custody statuses: `READY`, `BLOCKED`;
- fusion statuses: `READY`, `BLOCKED_UNRESOLVED`, `STALE`;
- identity scheme: `windows-volume-file-id-v1`;
- pixel convention: `RASTER_TOP_LEFT_X_RIGHT_Y_DOWN`;
- PDF convention: `PDF_USER_SPACE_BOTTOM_LEFT_X_RIGHT_Y_UP`;
- resolution context: `fusion_input_sha256` before resolution application.

### Placeholder scan

The plan contains concrete fixture values and exact public signatures. No runtime SHA or branch is guessed; execution is guarded by exact values supplied by the future approved runtime Issue.

## Execution handoff

After this planning PR is accepted, Master PO must create a separate runtime Issue with exact base/branch, accepted/narrowed eight-path allowlist, root/identity policy limits, approved no-lock-change dependency posture, exact offline/hosted gates, Cell 5 disposition, and truthful `NOT RUN` AutoCAD/private-data states.

Recommended execution mode: subagent-driven development with one writer and independent requirements/security review after each bounded task.
