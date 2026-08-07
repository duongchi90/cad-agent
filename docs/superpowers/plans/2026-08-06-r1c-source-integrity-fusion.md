# R1C Source Integrity and Deterministic Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-Python, fail-closed custody/fusion/evaluation evidence boundary that composes accepted R1A/R1B and current Primitive/Semantic IR artifacts without adding another truth store, ambient-clock authority, approval issuer, or visual/engineering authority.

**Architecture:** Preserve `source-bundle-1.0`. Create adjacent `source-custody-1.0`, `source-fusion-1.0`, and `source-fusion-evaluation-1.0` records. Use a bounded Windows final-handle adapter, server-keyed domain-separated object/path identities, one canonical numeric policy, UUID-independent IR projections, unresolved deterministic conflicts, injected evaluation-time evidence, and optional closed references under the existing `cad_agent.manifest` owner.

**Tech Stack:** Windows; Python 3.11; stdlib `hashlib`, `hmac`, `json`, `os`, `pathlib`, `stat`, `ctypes`, `msvcrt`, `decimal`, and `datetime`; locked Pillow 12.3.0 and pypdf 6.14.2; pytest; Ruff; repository architecture checker and canonical verifier. Locked ezdxf 1.4.4 remains spike-only and is not used in the first slice.

## Global Constraints

- This plan is not executable until a separate runtime Issue supplies the exact implementation base, branch, final allowlist, approved-root identity context, numeric policy, and gates.
- Preserve `cad_agent/source_bundle.py`, `source-bundle-1.0`, current Primitive/Semantic models, current CLI producers, and optional `PrimitiveIRRef.sha256` behavior.
- Preserve R1B legacy manifests; absent R1C references remain absent.
- First slice supports no `RESOLVED_BY_APPROVAL`, `selected_resolution`, source-conflict approval artifact, or approval issuer/validator API.
- Every blocking source conflict remains `UNRESOLVED` and forces `BLOCKED_UNRESOLVED`.
- No dependency, lock-file, workflow, CLI, schema-directory, OCR, model call, AutoCAD/File IPC, registry, revision, repair, visual verdict, engineering approval, or publication change.
- No private source, absolute source path, raw Windows device/volume/file ID, HMAC key, customer content, or parser exception text in Git or ordinary logs.
- No ambient `now()`/local clock read inside canonical custody, fusion, or evaluation validation.
- Use one writer for the runtime write set; independent review remains read-only.
- No local AutoCAD session is required. AutoCAD Mechanical live and hosted AutoCAD .NET remain `NOT RUN` unless separately authorized.
- Every task ends in one bounded commit. Do not amend, rebase, squash, force-push, or merge another branch.

---

## Proposed Runtime File Structure

### Create

- `cad_agent/source_integrity.py` — closed custody/evaluation/numeric contracts, Windows final-handle adapter, read-only byte/media inspection, HMAC identity, aliases/duplicates, and canonical hashes.
- `cad_agent/source_fusion.py` — locators, PDF render lineage, UUID-independent IR projections, deterministic unresolved conflicts, stale matching, and fusion/evaluation builders.
- `tests/test_cad_agent_source_integrity.py` — numeric, root/key/identity, handle/race, media/JSON, alias/duplicate, privacy, time-evidence, and resource tests.
- `tests/test_cad_agent_source_fusion.py` — locator/render, deterministic provenance, numeric/tolerance, conflict, stale, no-approval, and evaluation tests.
- `docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md` — exact implementation/evidence record.

### Modify

- `cad_agent/manifest.py` — optional closed custody/fusion/evaluation references and exact bind/match APIs.
- `cad_agent/pdf.py` — validate optional R1C references when reading PDF manifests.
- `tests/test_cad_agent_source_bundle_manifest.py` — reference validation, legacy compatibility, unequal-rebind, and PDF-reader tests.

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

## Task 1: Closed Numeric, Custody, and Evaluation Contracts

**Files:**

- Create: `cad_agent/source_integrity.py`
- Create: `tests/test_cad_agent_source_integrity.py`

**Interfaces:**

- Consumes: `cad_agent.source_bundle.validate_source_bundle`, `cad_agent.source_bundle.source_bundle_sha256`, and `cad_agent.drawing_contracts.canonical_json_sha256`.
- Produces:
  - `R1C_NUMERIC_POLICY_VERSION = "r1c-numeric-v1"`
  - `R1C_EXPIRY_POLICY_VERSION = "r1c-expiry-v1"`
  - `SOURCE_CUSTODY_SCHEMA_VERSION = "source-custody-1.0"`
  - `SOURCE_FUSION_EVALUATION_SCHEMA_VERSION = "source-fusion-evaluation-1.0"`
  - `class SourceIntegrityError(ValueError)`
  - `canonicalize_r1c_quantity(value: object, *, quantity: str, unit: str) -> dict[str, str]`
  - `r1c_quantity_within_tolerance(left: object, *, left_unit: str, right: object, right_unit: str, tolerance: object, tolerance_unit: str, quantity: str, tolerance_policy_version: str) -> bool`
  - `validate_source_custody(payload: object) -> dict[str, object]`
  - `source_custody_sha256(payload: object) -> str`
  - `validate_source_fusion_evaluation(payload: object) -> dict[str, object]`
  - `source_fusion_evaluation_sha256(payload: object) -> str`

- [ ] **Step 1: Write failing canonical numeric tests**

```python
@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (1, "mm", "1"),
        (1.0, "mm", "1"),
        ("-0.0004", "mm", "0"),
        ("25.4", "mm", "25.4"),
        (1, "in", "25.4"),
        ("2.3455", "mm", "2.346"),
        ("2.3445", "mm", "2.344"),
    ],
)
def test_r1c_length_canonicalization(value: object, unit: str, expected: str) -> None:
    assert canonicalize_r1c_quantity(value, quantity="physical_length", unit=unit) == {
        "policy_version": "r1c-numeric-v1",
        "quantity": "physical_length",
        "unit": "mm",
        "value": expected,
    }
```

Add exact tests for:

- finite-only values;
- unsupported units;
- inclusive range limits;
- fixed-point/no exponent output;
- locale independence;
- `ROUND_HALF_EVEN` halfway cases;
- negative zero;
- `1`, `1.0`, and `Decimal("1")` equality;
- inch/cm/m/point conversions;
- pixel integer refusal for fractions;
- angle, confidence, DPI, render-matrix, and scale quantities.

- [ ] **Step 2: Write failing tolerance boundary tests**

```python
def test_tolerance_boundary_is_inclusive_and_does_not_change_digest() -> None:
    assert r1c_quantity_within_tolerance(
        "10.000",
        left_unit="mm",
        right="10.005",
        right_unit="mm",
        tolerance="0.005",
        tolerance_unit="mm",
        quantity="physical_length",
        tolerance_policy_version="r1c-tolerance-v1",
    ) is True
    assert r1c_quantity_within_tolerance(
        "10.000",
        left_unit="mm",
        right="10.006",
        right_unit="mm",
        tolerance="0.005",
        tolerance_unit="mm",
        quantity="physical_length",
        tolerance_policy_version="r1c-tolerance-v1",
    ) is False
```

Assert tolerance affects conflict classification only; two distinct canonical values retain distinct hashes.

- [ ] **Step 3: Write failing closed custody fixture tests**

Use a complete fixture with exact fields:

```python
def _valid_custody_payload() -> dict[str, object]:
    return {
        "schema_version": "source-custody-1.0",
        "bundle_id": "BUNDLE-001",
        "run_id": "RUN-001",
        "source_bundle_sha256": "a" * 64,
        "approved_root_id": "ROOT-SYNTHETIC",
        "approved_root_revision": "ROOT-REV-1",
        "approved_root_configuration_sha256": "b" * 64,
        "identity_scheme": "HMAC-SHA-256",
        "identity_scheme_version": "r1c-file-identity-v1",
        "identity_key_revision": "KEY-REV-1",
        "numeric_policy_version": "r1c-numeric-v1",
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
                "region_ids": ["REGION-001"],
                "file_object_identity_token": "d" * 64,
                "path_binding_sha256": "e" * 64,
                "identity_scheme": "HMAC-SHA-256",
                "identity_scheme_version": "r1c-file-identity-v1",
                "identity_key_revision": "KEY-REV-1",
                "approved_root_revision": "ROOT-REV-1",
                "alias_group_id": None,
                "custody_state": "VERIFIED",
                "blocking_reason_code": None,
            }
        ],
        "alias_groups": [],
    }
```

Test round-trip determinism, exact fields, count invariants, `READY/BLOCKED`, and rejection of visual/engineering/approval/repair/publication fields.

- [ ] **Step 4: Write failing evaluation contract tests**

```python
def _valid_evaluation_payload() -> dict[str, object]:
    return {
        "schema_version": "source-fusion-evaluation-1.0",
        "run_id": "RUN-001",
        "source_fusion_sha256": "f" * 64,
        "fusion_input_sha256": "1" * 64,
        "evaluation_time_utc": "2026-08-06T16:00:00.000000Z",
        "evaluation_time_source": "SERVER-CLOCK-EVIDENCE-1",
        "evaluation_time_evidence_sha256": "2" * 64,
        "expiry_policy_version": "r1c-expiry-v1",
        "evaluated_reference_hashes": ["3" * 64],
        "status": "REUSABLE",
        "blocking_codes": [],
    }
```

Require UTC `Z`, exactly six fractional digits, sorted unique hashes, closed statuses, and no local timezone/ambient timestamp fields.

- [ ] **Step 5: Run tests and confirm import failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
```

Expected: collection/import failure because `cad_agent.source_integrity` does not exist.

- [ ] **Step 6: Implement minimal validators and canonicalizers**

Use `Decimal(str(value))`, exact conversion factors, `ROUND_HALF_EVEN`, closed policy tables, fixed-point serialization, and deep-copy normalization. Do not read locale or time.

- [ ] **Step 7: Run focused tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
```

- [ ] **Step 8: Commit Task 1**

```powershell
git add cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
git commit -m "contracts: add closed R1C numeric custody and evaluation evidence"
```

---

## Task 2: Server-Keyed Object Identity and Separate Path Binding

**Files:**

- Modify: `cad_agent/source_integrity.py`
- Modify: `tests/test_cad_agent_source_integrity.py`

**Interfaces:**

- Produces:
  - `inspect_source_bundle(*, approved_root_id: str, approved_root_revision: str, approved_root: Path, identity_key: bytes, identity_key_revision: str, policy_limits: Mapping[str, int], source_bundle: object) -> dict[str, object]`
  - `require_source_custody_match(*, approved_root_id: str, approved_root_revision: str, approved_root: Path, identity_key: bytes, identity_key_revision: str, policy_limits: Mapping[str, int], source_bundle: object, custody: object) -> None`
  - private `_file_object_identity_token(...) -> str`
  - private `_path_binding_sha256(...) -> str`

- [ ] **Step 1: Add object-versus-path tests**

Test with an injectable platform adapter:

- same filesystem object through two hardlinks -> same object token, different path binding;
- moved/renamed same object -> same object token, changed path binding;
- copied equal bytes -> different object token, equal byte SHA;
- replaced same path/equal bytes with another object -> changed object token;
- changed root revision -> changed configuration/path binding;
- changed key revision -> changed opaque tokens and stale prior custody.

- [ ] **Step 2: Add domain-separation/privacy tests**

Assert object and path tokens differ for the same input context, raw path/device/volume/file IDs never appear in artifacts/errors, tokens cannot be recomputed with an unrelated key, and artifacts contain only key revision—not key material.

- [ ] **Step 3: Add alias/duplicate classification tests**

```python
def test_hardlinks_are_aliases_but_copies_are_duplicate_bytes(tmp_path: Path) -> None:
    hardlink_packet = _inspect_hardlink_pair(tmp_path)
    assert hardlink_packet["alias_groups"][0]["group_type"] == "SAME_FILE_ALIAS"

    copy_packet = _inspect_copy_pair(tmp_path)
    assert copy_packet["alias_groups"][0]["group_type"] == "DUPLICATE_BYTES"
```

Assert duplicate byte count never changes source precedence or authority.

- [ ] **Step 4: Add final-handle containment/race tests**

Use deterministic injected hooks for component replacement, reparse substitution, final path outside root, object identity change after parser work, and unavailable final path. Never use sleep-based tests.

- [ ] **Step 5: Run focused tests and confirm API failures**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
```

- [ ] **Step 6: Implement bounded Windows handle adapter**

Port only concepts from `ExactBaseXrefPolicy.cs`: read-only open, bounded `GetFinalPathNameByHandleW`, file information by handle, normalized final path, post-open containment, reparse refusal, and before/after identity comparison. Unsupported evidence fails closed.

- [ ] **Step 7: Implement domain-separated HMAC**

Object domain:

```text
cad-agent:r1c:file-object:v1
```

Path domain:

```text
cad-agent:r1c:path-binding:v1
```

The object message contains identity scheme/version, key revision, and raw opened-handle volume/file identity—never path. The path message contains root configuration/revision, normalized final relative path, and object token.

- [ ] **Step 8: Run repeated tests and Ruff**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { throw "R1C identity repetition $_ failed" }
}
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
```

- [ ] **Step 9: Commit Task 2**

```powershell
git add cad_agent/source_integrity.py tests/test_cad_agent_source_integrity.py
git commit -m "security: separate R1C object identity from path binding"
```

---

## Task 3: Read-Only Media Adapters and Strict Engineer JSON

**Files:**

- Modify: `cad_agent/source_integrity.py`
- Modify: `tests/test_cad_agent_source_integrity.py`

**Interfaces:**

- Consumes: Task 2 custody-owned descriptor and first byte hash.
- Produces: bounded image/PDF/DWG-header/DXF-header/JSON observations; complete `READY` or sanitized `BLOCKED` custody packet.

- [ ] **Step 1: Add parser-isolation and cleanup tests**

Use a fake parser that closes/seeks its input. Prove the custody descriptor remains usable. For an operation-owned snapshot, prove hash equality, cleanup on success/error, no manifest reference, and mandatory second hash/final identity check on the original.

- [ ] **Step 2: Add image/PDF resource tests**

Cover valid/truncated/mismatched PNG/JPEG, decompression-bomb refusal, valid/malformed/encrypted PDF, repaired-only structures, excessive pages/boxes/bytes, and parser disagreement.

- [ ] **Step 3: Add strict JSON tests**

```python
def test_engineer_json_duplicate_keys_block_custody(tmp_path: Path) -> None:
    path = tmp_path / "decision.json"
    path.write_bytes(b'{"value":1,"value":2}')
    custody = _inspect_engineer_record(path)
    assert custody["status"] == "BLOCKED"
    assert custody["items"][0]["blocking_reason_code"] == "JSON_DUPLICATE_KEY"
```

Also reject malformed UTF-8, non-object root, NaN/Infinity, excessive depth/key/array/string/byte limits, and unsupported numeric units.

- [ ] **Step 4: Run tests and confirm failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_integrity.py -q -p no:cacheprovider
```

- [ ] **Step 5: Implement duplicated-handle/snapshot boundary**

Keep original custody descriptor open. Give parser adapters a duplicated handle or bounded temporary snapshot. Always second-hash and final-identity-check the original.

- [ ] **Step 6: Implement bounded adapters**

- Pillow 12.3.0: read-only identify/verify; no save/convert/transpose.
- pypdf 6.14.2: strict page/box/rotation/user-unit observations; no rewrite/decrypt/text authority.
- DWG: bounded `AC10xx` header only.
- DXF: header only; ezdxf remains unused `SPIKE_ONLY`.
- JSON: strict hooks and limits.

Canonicalize all serialized DPI, user-unit, box, and dimension quantities through Task 1 policy.

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

## Task 4: Explicit Locators and PDF Render Provenance

**Files:**

- Create: `cad_agent/source_fusion.py`
- Create: `tests/test_cad_agent_source_fusion.py`

**Interfaces:**

- Consumes: validated R1A bundle, `READY` custody, PDF-render/Primitive artifacts, checkpoint hashes, and `canonicalize_r1c_quantity()`.
- Produces:
  - `SOURCE_FUSION_SCHEMA_VERSION = "source-fusion-1.0"`
  - `class SourceFusionError(ValueError)`
  - `validate_page_locators(payload: object, *, source_bundle: object, custody: object) -> list[dict[str, object]]`
  - `validate_region_locators(payload: object, *, page_locators: object, custody: object) -> list[dict[str, object]]`
  - `validate_render_provenance(payload: object, *, page_locators: object, custody: object, primitive_artifact_sha256: str) -> list[dict[str, object]]`

- [ ] **Step 1: Add explicit page locator tests**

Every R1A page label requires exactly one locator. Test out-of-range index, missing label, duplicate locator, wrong custody hash, wrong box/rotation/user unit, and sorted-label mapping refusal.

- [ ] **Step 2: Add pixel-region tests**

Require:

- `coordinate_convention = RASTER_TOP_LEFT_X_RIGHT_Y_DOWN`;
- exact raster SHA/width/height;
- integer pixel coordinates;
- ordered in-bounds rectangle.

- [ ] **Step 3: Add PDF-region tests**

Require:

- `coordinate_convention = PDF_USER_SPACE_BOTTOM_LEFT_X_RIGHT_Y_UP`;
- exact page locator;
- selected `MEDIA_BOX` or `CROP_BOX` and bounds;
- normalized rotation and user unit;
- `r1c-numeric-v1` fixed-point values.

Test rotated/cropped PDFs, ambiguous origin, half-even normalization, negative zero, range overflow, and equivalent point/inch inputs.

- [ ] **Step 4: Add full PDF render-chain tests**

Require exact chain:

```text
custody PDF SHA
→ explicit page locator/index
→ selected box/rotation/user unit
→ render DPI and canonical matrix
→ rendered raster SHA/dimensions
→ Primitive artifact SHA
→ Primitive source-document SHA/dimensions/page index
```

Test wrong page, box, DPI, rotation, user unit, matrix, raster hash, Primitive artifact hash, and source-document hash.

- [ ] **Step 5: Add direct-image provenance test**

Require Primitive source-document SHA/dimensions to equal custody observations for direct images.

- [ ] **Step 6: Run tests and confirm import/API failure**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
```

- [ ] **Step 7: Implement closed locator/render validators**

No OCR, filename inference, model mapping, local timezone, or noncanonical numeric values. Sort arrays by deterministic closed compound keys.

- [ ] **Step 8: Run focused tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
```

- [ ] **Step 9: Commit Task 4**

```powershell
git add cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
git commit -m "contracts: bind R1C page region and render provenance"
```

---

## Task 5: UUID-Independent Primitive and Semantic Projections

**Files:**

- Modify: `cad_agent/source_fusion.py`
- Modify: `tests/test_cad_agent_source_fusion.py`

**Interfaces:**

- Produces:
  - `project_primitive_observations(*, primitive_artifact: object, primitive_artifact_sha256: str, source_bindings: object) -> list[dict[str, object]]`
  - `project_semantic_observations(*, semantic_artifact: object, semantic_artifact_sha256: str, primitive_checkpoint_sha256: str, primitive_observations: object) -> list[dict[str, object]]`

- [ ] **Step 1: Add Primitive UUID/order invariance tests**

Rebuild equivalent Primitive artifacts with changed UUIDs, handles, extraction timestamps, input order, equivalent units, int/float forms, and negative zero. Require identical observation projections and hashes.

- [ ] **Step 2: Add duplicate-observation tests**

Identical closed projections form a multiset with deterministic digest and occurrence count. If a Semantic reference identifies an indistinguishable subset only by legacy UUID, emit `DUPLICATE_OBSERVATION_AMBIGUITY`.

- [ ] **Step 3: Add Semantic UUID/order invariance tests**

Rebuild equivalent Semantic artifacts with changed part/constraint UUIDs/order and map legacy primitive references to deterministic Primitive observation keys. Require identical Semantic projections.

- [ ] **Step 4: Add current producer compatibility tests**

Use a current-format `PrimitiveIRRef` with filename/count and omitted optional SHA. Bind externally using the manifest Primitive checkpoint hash. Validate optional SHA only when present. Wrong filename/count/checkpoint SHA blocks.

- [ ] **Step 5: Add cross-platform numeric serialization fixtures**

Use fixed input/expected JSON fixtures and assert identical canonical JSON/digest on Windows and Linux CI for geometry, confidence, calibration, measurement, tolerance, and matrix values.

- [ ] **Step 6: Run tests and confirm failures**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
```

- [ ] **Step 7: Implement closed projections**

Exclude UUIDs, handles, volatile times, input order, locale, and unapproved notes. Include only source/render binding, canonical type/layer/content/geometry/confidence/trace/calibration, numeric policy version, and checkpoint hashes.

- [ ] **Step 8: Run permutation loop and Ruff**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { throw "R1C provenance repetition $_ failed" }
}
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
```

- [ ] **Step 9: Commit Task 5**

```powershell
git add cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
git commit -m "feat: project deterministic R1C IR provenance"
```

---

## Task 6: Deterministic Unresolved Conflicts — No Approval Resolution

**Files:**

- Modify: `cad_agent/source_fusion.py`
- Modify: `tests/test_cad_agent_source_fusion.py`

**Interfaces:**

- Produces:
  - `build_source_fusion_packet(*, source_bundle: object, custody: object, page_locators: object, region_locators: object, render_provenance: object, primitive_observations: object, semantic_observations: object, tolerance_policy: object) -> dict[str, object]`
  - `validate_source_fusion_packet(payload: object) -> dict[str, object]`
  - `source_fusion_sha256(payload: object) -> str`
  - `require_source_fusion_match(*, source_bundle: object, custody: object, fusion: object) -> None`

There is deliberately no resolution/approval API.

- [ ] **Step 1: Add deterministic conflict tests**

Cover byte/object/path identity, media/parser, locator/render, calibration, measurement, geometry, material, decision, and duplicate-observation conflicts. Assert compared evidence is never discarded by confidence, role, count, parser, or list order.

- [ ] **Step 2: Add tolerance-order tests**

Test equivalent units, exact tolerance boundary, just-over boundary, halfway rounding, and distinct hashes for within-tolerance evidence. Tolerance classifies conflict only; it does not merge evidence.

- [ ] **Step 3: Add no-approval surface tests**

```python
@pytest.mark.parametrize(
    "forbidden_field",
    [
        "resolution_references",
        "selected_resolution",
        "approval",
        "approval_status",
        "RESOLVED_BY_APPROVAL",
    ],
)
def test_first_slice_rejects_approval_resolution_fields(forbidden_field: str) -> None:
    payload = _valid_fusion_payload()
    payload[forbidden_field] = []
    with pytest.raises(SourceFusionError, match="unsupported"):
        validate_source_fusion_packet(payload)
```

AST/static tests must prove no public function contains `approval`, `resolve_conflict`, or ambient-clock authority.

- [ ] **Step 4: Add fusion status tests**

Rules:

- custody not `READY` -> no packet;
- stale hashes/policies -> `STALE` or exact-match refusal;
- any blocking conflict -> `BLOCKED_UNRESOLVED`;
- no blocking conflict and all inputs exact -> `READY`;
- `READY` with unresolved blocker or authority field -> reject.

- [ ] **Step 5: Add `fusion_input_sha256` permutation tests**

Shuffle every caller array and require identical packet JSON and hash. Change any bundle/custody/root/numeric/tolerance/locator/render/provenance/conflict input and require a changed input hash.

- [ ] **Step 6: Run tests and confirm failures**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
```

- [ ] **Step 7: Implement conflict construction and status**

Conflict IDs hash type, deterministic subject, sorted compared evidence hashes, canonical values/units, policy versions, and exact fusion context. Every first-slice conflict state is `UNRESOLVED`.

- [ ] **Step 8: Run focused tests and Ruff**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_source_fusion.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
```

- [ ] **Step 9: Commit Task 6**

```powershell
git add cad_agent/source_fusion.py tests/test_cad_agent_source_fusion.py
git commit -m "feat: preserve unresolved R1C conflicts without approval authority"
```

---

## Task 7: Injected Evaluation-Time Evidence and Deterministic Reuse Gate

**Files:**

- Modify: `cad_agent/source_integrity.py`
- Modify: `cad_agent/source_fusion.py`
- Modify: `tests/test_cad_agent_source_integrity.py`
- Modify: `tests/test_cad_agent_source_fusion.py`

**Interfaces:**

- Produces:
  - `build_source_fusion_evaluation(*, fusion: object, evaluation_time_utc: str, evaluation_time_source: str, evaluation_time_evidence_sha256: str, expiry_policy_version: str, evaluated_references: object) -> dict[str, object]`
  - `require_source_fusion_evaluation_match(*, fusion: object, evaluation: object) -> None`

- [ ] **Step 1: Add boundary-before/at/after-expiry tests**

For `r1c-expiry-v1`, require:

- issued <= evaluation < expiry -> reusable;
- exactly at expiry -> blocked/expired;
- after expiry -> blocked/expired.

Use explicit RFC 3339 UTC values with six fractional digits.

- [ ] **Step 2: Add timezone/precision refusal tests**

Reject offsets other than `Z`, missing/excess fractional precision, leap/invalid dates, local-time strings, and unordered issued/expiry values.

- [ ] **Step 3: Add clock rollback/replay tests**

Replay identical fusion plus identical evaluation evidence and require identical JSON/hash. Earlier evaluation evidence produces another evaluation record; it never rewrites fusion or silently overrides a later record. Changed evidence hash/source/policy/reference set changes evaluation hash.

- [ ] **Step 4: Add ambient-clock static test**

AST scan canonical custody/fusion/evaluation functions and reject calls to `datetime.now`, `datetime.utcnow`, `time.time`, filesystem mtime, or local timezone APIs.

- [ ] **Step 5: Run tests and confirm failures**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_integrity.py `
  tests/test_cad_agent_source_fusion.py `
  -q -p no:cacheprovider
```

- [ ] **Step 6: Implement injected evaluation builder**

Parse only supplied time/evidence. Bind exact fusion/fusion-input hashes, source, evidence SHA, policy, and sorted evaluated reference hashes. Do not mutate the fusion artifact.

- [ ] **Step 7: Run tests repeatedly and Ruff**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest `
    tests/test_cad_agent_source_integrity.py `
    tests/test_cad_agent_source_fusion.py `
    -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { throw "R1C evaluation repetition $_ failed" }
}
.\.venv-py311\Scripts\python.exe -m ruff check `
  cad_agent/source_integrity.py `
  cad_agent/source_fusion.py `
  tests/test_cad_agent_source_integrity.py `
  tests/test_cad_agent_source_fusion.py
```

- [ ] **Step 8: Commit Task 7**

```powershell
git add `
  cad_agent/source_integrity.py `
  cad_agent/source_fusion.py `
  tests/test_cad_agent_source_integrity.py `
  tests/test_cad_agent_source_fusion.py
git commit -m "feat: evaluate R1C reuse with recorded time evidence"
```

---

## Task 8: Bind R1C References Through the Existing Manifest Owner

**Files:**

- Modify: `cad_agent/manifest.py`
- Modify: `cad_agent/pdf.py`
- Modify: `tests/test_cad_agent_source_bundle_manifest.py`

**Interfaces:**

- Produces:
  - `SOURCE_CUSTODY_REFERENCE_SCHEMA_VERSION = "source-custody-reference-1.0"`
  - `SOURCE_FUSION_REFERENCE_SCHEMA_VERSION = "source-fusion-reference-1.0"`
  - `SOURCE_FUSION_EVALUATION_REFERENCE_SCHEMA_VERSION = "source-fusion-evaluation-reference-1.0"`
  - closed reference validators and bind/match functions.

- [ ] **Step 1: Add custody reference tests**

Exact fields include bundle/root revision/config hash, identity scheme/version/key revision, numeric policy, custody hash, status, item/eligible/blocking counts.

- [ ] **Step 2: Add fusion reference tests**

Exact fields include bundle/custody/root, numeric/tolerance policy versions, fusion-input/fusion hashes, status, conflict and unresolved counts. No resolution/approval fields are allowed.

- [ ] **Step 3: Add evaluation reference tests**

Exact fields include fusion/fusion-input/evaluation hashes, evaluation-time source/evidence hash, expiry policy version, status, and blocking count. Do not store time-source private details or ambient timestamp.

- [ ] **Step 4: Add legacy and unequal-rebind tests**

Prove absent fields remain absent, readers validate only present fields, equal bind is idempotent, unequal bind fails, and full evidence arrays/key material are not stored.

- [ ] **Step 5: Run focused/regression tests and confirm failures**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_source_bundle.py `
  tests/test_cad_agent_source_bundle_manifest.py `
  tests/test_cad_agent_cli.py `
  tests/test_cad_agent_pdf.py `
  -q -p no:cacheprovider
```

- [ ] **Step 6: Implement following the R1B pattern**

Deep-copy manifests, validate derived records first, bind every context/policy hash, refuse unequal rebinding, map domain errors to `ManifestError`, and never inject absent keys.

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

- [ ] **Step 8: Commit Task 8**

```powershell
git add cad_agent/manifest.py cad_agent/pdf.py tests/test_cad_agent_source_bundle_manifest.py
git commit -m "manifest: bind R1C custody fusion and evaluation references"
```

---

## Task 9: Security, Determinism, and Boundary Hardening

**Files:**

- Modify: `tests/test_cad_agent_source_integrity.py`
- Modify: `tests/test_cad_agent_source_fusion.py`
- Modify only for proven defects: `cad_agent/source_integrity.py`, `cad_agent/source_fusion.py`

**Produces:** complete synthetic acceptance matrix; no new public API.

- [ ] **Step 1: Add fixed malformed/resource corpus**

Include valid/truncated/mismatched PNG/JPEG/PDF/DWG-header/DXF/JSON; encrypted/malformed PDF; duplicate JSON keys; malformed UTF-8; non-finite/out-of-range values; oversized limits.

- [ ] **Step 2: Add deterministic path/object race hooks**

Inject component replacement, reparse substitution, source mutation, same-byte object replacement, parser closure, object identity change, path move, copy, hardlink, root remap, and key rotation. No sleeps.

- [ ] **Step 3: Add numeric golden vectors**

Create fixed JSON golden vectors for every quantity/unit/rounding/range/tolerance boundary. Run the same vectors on Windows and Linux hosted Python and require identical serialization/digests.

- [ ] **Step 4: Add complete permutation/replay tests**

Require identical custody/fusion/evaluation hashes across shuffled inputs, rebuilt UUIDs, repeated runs, equivalent units/forms, and identical time evidence.

- [ ] **Step 5: Add static authority/privacy tests**

Prove:

- no network/subprocess/OCR/model/AutoCAD/File IPC import;
- no source write/save/replace/unlink path;
- no approval-resolution schema/API/field;
- no ambient clock read;
- no raw path/device/file ID/key material in artifacts/errors;
- manifest remains the only run/checkpoint owner.

- [ ] **Step 6: Run complete focused R1 suite**

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

- [ ] **Step 7: Run architecture and canonical verification without AutoCAD**

```powershell
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check `
  --repo-root . `
  --baseline contracts/reuse-integration/architecture-boundaries.json

.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Record AutoCAD .NET, AutoCAD Mechanical live, and private-data as `NOT RUN`/`SKIP`, never PASS.

- [ ] **Step 8: Commit Task 9**

Stage only files actually changed:

```powershell
git add tests/test_cad_agent_source_integrity.py tests/test_cad_agent_source_fusion.py
if (git diff --name-only | Select-String '^cad_agent/source_(integrity|fusion)\.py$') {
  git add cad_agent/source_integrity.py cad_agent/source_fusion.py
}
git diff --cached --name-only
git commit -m "test: harden R1C custody fusion and evaluation boundaries"
```

---

## Task 10: Implementation Record, Exact Audit, and Draft PR Handoff

**Files:**

- Create: `docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md`

**Interfaces:**

- Consumes: separate runtime Issue identity, commit chain, exact diff, verification, hosted runs, and independent review.
- Produces: exact implementation/evidence record and draft PR handoff.

- [ ] **Step 1: Require exact runtime identity from the approved Issue**

```powershell
$runtimeBase = $env:CAD_AGENT_R1C_RUNTIME_BASE_SHA
$runtimeBranch = $env:CAD_AGENT_R1C_RUNTIME_BRANCH
if (-not $runtimeBase -or -not $runtimeBranch) {
  throw 'R1C runtime exact base and branch must come from the approved runtime Issue'
}
```

- [ ] **Step 2: Write exact evidence record**

Include Issue/base/branch/head, bounded commits, exact files, reuse classifications, first-slice approval lock, identity/numeric/time policy versions, test counts, hosted run IDs, synthetic merge SHA, review dispositions, migration/rollback, retained locks, and truthful external gates.

- [ ] **Step 3: Audit exact runtime allowlist**

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

The runtime Issue may narrow this list; the command must then use that exact approved list.

- [ ] **Step 4: Run final exact-head verification**

```powershell
git diff --check "$runtimeBase...HEAD"
.\scripts\verify.ps1 -SkipAutoCADDotNet
git status --short
```

- [ ] **Step 5: Commit implementation record**

```powershell
git add docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md
git commit -m "docs: record R1C source integrity verification"
```

- [ ] **Step 6: Push normally and retain draft PR**

```powershell
git push -u origin $runtimeBranch
```

No force-push, amend, rebase, squash, ready transition, or merge.

- [ ] **Step 7: Stop for independent review**

Post exact head and PR to the independent source-integrity reviewer and Master PO. Runtime remains unaccepted until exact-head hosted tests, Reuse Declaration, and independent reviews pass.

---

## Planning-Only Verification for PR #78

The planning writer must run, where a local repository is available:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_documentation_contract.py `
  tests/test_reuse_rebaseline_docs.py `
  tests/test_reuse_declaration.py `
  -q -p no:cacheprovider

git diff --check d71d0c97e28e03cb430f05589c8381b4ede70e66...HEAD
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Exact cumulative planning paths must be:

```powershell
$expected = @(
  'docs/superpowers/plans/2026-08-06-r1c-source-integrity-fusion.md',
  'docs/superpowers/specs/2026-08-06-r1c-source-integrity-fusion-design.md'
) | Sort-Object
$actual = git diff --name-only d71d0c97e28e03cb430f05589c8381b4ede70e66...HEAD | Sort-Object
if (Compare-Object $expected $actual) {
  throw 'Issue #71 planning allowlist mismatch'
}
```

When the local worktree is unavailable, record local focused/canonical verification as `NOT RUN`; fresh hosted checks remain mandatory.

PR #78 remains `OPEN/DRAFT` until Cell 5 exact-head re-review and Master PO decision.

## Plan Self-Review

### Spec coverage

- approval issuer locked and no resolution surface: Task 6;
- deterministic injected time evidence: Tasks 1 and 7;
- complete numeric/unit/rounding/tolerance policy: Tasks 1, 4, 5, 6, and 9;
- opaque object identity separated from path binding: Task 2;
- final-handle containment and immutable bytes: Tasks 2 and 3;
- PDF/render and coordinate lineage: Task 4;
- UUID-independent current-format IR compatibility: Task 5;
- sole manifest/checkpoint ownership: Task 8;
- security/privacy/replay/cross-platform proof: Task 9;
- exact evidence/allowlist/handoff: Task 10.

### Name and type consistency

- custody statuses: `READY`, `BLOCKED`;
- fusion statuses: `READY`, `BLOCKED_UNRESOLVED`, `STALE`;
- conflict state: first slice only `UNRESOLVED`;
- evaluation statuses: `REUSABLE`, `BLOCKED_EXPIRED`, `STALE`;
- numeric policy: `r1c-numeric-v1`;
- tolerance policy: `r1c-tolerance-v1`;
- expiry policy: `r1c-expiry-v1`;
- identity scheme/version: `HMAC-SHA-256` / `r1c-file-identity-v1`;
- object identity and path binding are separate fields/functions;
- no approval/resolution API or field exists.

### Placeholder scan

No guessed runtime SHA/branch is embedded. Runtime identity is read from environment values that a future exact runtime Issue must set. No `TBD`, `TODO`, illustrative ellipsis, or unresolved public signature remains.

## Execution Handoff

After planning acceptance, Master PO must create a separate runtime Issue containing:

- exact implementation base and branch;
- accepted/narrowed eight-path allowlist;
- approved-root revision and identity-key ownership/injection rules;
- exact identity/numeric/tolerance/time policy versions and limits;
- no-approval-resolution first-slice lock;
- required focused/hosted/private/live gates;
- independent source-integrity review requirement.

Approval-based source-conflict resolution requires a different prerequisite Issue and remains locked.
