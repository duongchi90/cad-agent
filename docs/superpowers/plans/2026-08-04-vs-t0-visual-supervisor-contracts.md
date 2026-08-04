# VS-T0 Visual Supervisor Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Planned

**Approval date:** 2026-08-04

**Planning base SHA:** `891b811ca820dbe1b188c2988be8da8ba99f399d`

**Implementation base:** Create an isolated execution branch/worktree from the fresh integrated `main` after the design and rollout plan merge. Record that SHA before changing code.

**Completion Head SHA:** Not recorded until the final implementation/evidence commit exists.

**Verification command:** `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1`

**Verification result:** Not recorded until execution completes.

**Required gates:** This is a pure contract/documentation slice. `real_data` is `NOT RUN`; `autocad_mechanical` is `NOT RUN`; no OpenAI API call is made. Hosted/offline tests may pass without promoting those gates.

**Goal:** Add strict, hash-bound Visual Supervisor contracts and cross-contract safety policy so later dimension, comparison, visual-review, repair, orchestration, and publication tasks share one closed vocabulary and Codex cannot self-approve or publish.

**Architecture:** Add a focused `cad_agent.visual_contracts` pure-Python boundary that reuses canonical hashing from `cad_agent.drawing_contracts` but owns Visual Supervisor validation. Store closed JSON Schema draft 2020-12 documents and synthetic examples under `contracts/visual-supervisor/`; test schema/example/validator alignment and safety invariants without adding a runtime schema dependency.

**Tech Stack:** Windows, Python 3.11, pytest, JSON, JSON Schema draft 2020-12 documents, existing `cad_agent.drawing_contracts.canonical_json_sha256`, existing `scripts/verify.ps1`.

## Global Constraints

- Preserve current package boundaries and M2 behavior; do not modify AutoCAD, IPC, generation, repair, or publication runtime behavior in VS-T0.
- Do not add OpenAI client libraries, image-processing libraries, databases, services, or runtime JSON Schema dependencies in this task.
- All schemas are closed with `additionalProperties: false` at every object boundary.
- All identifiers use the existing identifier rule `^[A-Za-z0-9][A-Za-z0-9_.-]*$`.
- Every SHA-256 is exactly 64 lowercase hexadecimal characters.
- Every finite number rejects `NaN`, positive infinity, and negative infinity.
- Contract versions are exact and start at `1.0`; validators reject unknown versions.
- Visual verdict is exactly one of `PASS`, `FAIL`, or `NEEDS_HUMAN`.
- Dimension role is exactly one of `DRIVING`, `REFERENCE`, `DERIVED`, `AMBIGUOUS`, or `CONFLICT`.
- Dimension status is exactly one of `CONFIRMED`, `UNRESOLVED`, or `CONFLICT`.
- A `DRIVING` dimension may be `CONFIRMED` only when both `from_ref` and `to_ref` are present.
- A critical unresolved/conflicting dimension must list at least one `blocker_scope` region ID.
- Repair Plans cannot contain a verdict, pass authority, publication policy, or target-replacement operation.
- Region `VERIFIED` requires visual `PASS`, geometry `PASS`, engineering `PASS`, no unresolved critical items, and equal latest-mutation/evidence binding.
- Auto-publish authorization is run-scoped, path/hash/backup-bound, single-use, and expires after the run.
- Synthetic examples contain no customer names, private paths, real drawings, credentials, or API keys.
- Every implementation task starts with a failing focused test and ends with focused tests, `git diff --check`, diff inspection, and a scoped commit.

---

## File Structure

### New contract files

- `contracts/visual-supervisor/visual-run-manifest.schema.json`: run state, source/drawing identity, evidence root, and authority classification.
- `contracts/visual-supervisor/dimension-register.schema.json`: page/view dimension coverage, observations, blockers, and conflicts.
- `contracts/visual-supervisor/geometry-comparison.schema.json`: alignment provenance and deterministic metrics.
- `contracts/visual-supervisor/visual-review.schema.json`: independent multimodal verdict, findings, repair intent, and evidence references.
- `contracts/visual-supervisor/repair-plan.schema.json`: Codex business-level repair plan without pass/publish authority.
- `contracts/visual-supervisor/region-verification-register.schema.json`: source/CAD/evidence binding and region gate state.
- `contracts/visual-supervisor/auto-publish-authorization.schema.json`: one-run automatic publication authorization.
- `contracts/visual-supervisor/examples/*.json`: one valid synthetic example for every schema.

### New Python and test files

- `cad_agent/visual_contracts.py`: strict validation, deep-copy return, exact contract registry, and cross-contract policy checks.
- `tests/visual_supervisor_fixtures.py`: valid synthetic mappings and mutation helpers.
- `tests/test_visual_supervisor_contracts.py`: validator behavior and canonical hash tests.
- `tests/test_visual_supervisor_schema_alignment.py`: schema/example/validator alignment and closed-object checks.
- `tests/test_visual_supervisor_contract_policy.py`: authority, stale-evidence, dimension attachment, and publication safety tests.

### Modified documentation files

- `docs/ARCHITECTURE.md`: record the contract-only Visual Supervisor boundary and its dependency on later roadmap slices.
- `docs/STATUS.md`: record VS-T0 only after fresh verification; explicitly keep API, private-data, and AutoCAD gates `NOT RUN`.
- `tests/test_documentation_contract.py`: protect the canonical design, rollout plan, detailed VS-T0 plan, and honest contract-only status.

## Stable Interfaces

Implement these exact Python interfaces:

```python
from collections.abc import Mapping
from pathlib import Path


class VisualContractError(ValueError):
    """Raised when a Visual Supervisor contract is malformed or unsafe."""


def validate_visual_contract(
    payload: Mapping[str, object],
    *,
    contract: str,
) -> dict[str, object]:
    """Validate one closed contract and return a deep copy safe from caller mutation."""


def read_visual_contract(
    path: Path,
    *,
    contract: str,
) -> dict[str, object]:
    """Read UTF-8 JSON, validate the selected contract, and return a deep copy."""


def require_dimension_gate_ready(register: Mapping[str, object]) -> None:
    """Reject critical unresolved/conflicting dimensions and incomplete cluster disposition."""


def require_region_verified(region: Mapping[str, object]) -> None:
    """Reject stale or incomplete region evidence and any failed constituent gate."""


def require_auto_publish_authorized(
    authorization: Mapping[str, object],
    *,
    run_id: str,
    target_path: str,
    target_sha256: str,
) -> None:
    """Reject expired, consumed, mismatched, or non-approved run-scoped authorization."""
```

Supported `contract` values are exactly:

```python
SUPPORTED_VISUAL_CONTRACTS = {
    "visual_run_manifest",
    "dimension_register",
    "geometry_comparison",
    "visual_review",
    "repair_plan",
    "region_verification_register",
    "auto_publish_authorization",
}
```

## Shared Synthetic Values

All tests and examples use these identities consistently:

```python
RUN_ID = "RUN-VISUAL-SYNTHETIC-001"
PAGE_ID = "PAGE-001"
VIEW_ID = "SIDE"
REGION_ID = "SIDE-CABIN"
SOURCE_SHA = "1" * 64
DRAWING_SHA = "2" * 64
MUTATION_SHA = "3" * 64
RENDER_SHA = "4" * 64
REFERENCE_PACKAGE_SHA = "5" * 64
COMPARISON_SHA = "6" * 64
REVIEW_SHA = "7" * 64
INITIAL_TARGET_SHA = "8" * 64
TARGET_PATH = "D:\\Synthetic\\drawing.dwg"
BACKUP_ROOT = "D:\\Synthetic\\Backups"
```

No example may use an existing customer or workstation path.

---

### Task 1: Visual contract validation scaffold and run manifest

**Files:**
- Create: `cad_agent/visual_contracts.py`
- Create: `contracts/visual-supervisor/visual-run-manifest.schema.json`
- Create: `contracts/visual-supervisor/examples/visual-run-manifest.json`
- Create: `tests/visual_supervisor_fixtures.py`
- Create: `tests/test_visual_supervisor_contracts.py`
- Create: `tests/test_visual_supervisor_schema_alignment.py`

**Interfaces:**
- Consumes: `cad_agent.drawing_contracts.canonical_json_sha256(payload: Mapping[str, object]) -> str`
- Produces: `VisualContractError`, `validate_visual_contract()`, `read_visual_contract()`, and the exact contract registry used by all later tasks.

- [ ] **Step 1: Write the failing run-manifest validator tests**

Add these tests to `tests/test_visual_supervisor_contracts.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cad_agent.visual_contracts import (
    VisualContractError,
    read_visual_contract,
    validate_visual_contract,
)
from tests.visual_supervisor_fixtures import valid_visual_run_manifest


def test_visual_run_manifest_validates_and_is_deep_copied() -> None:
    source = valid_visual_run_manifest()
    validated = validate_visual_contract(source, contract="visual_run_manifest")
    assert validated == source
    source["state"] = "MUTATED_BY_CALLER"
    assert validated["state"] == "CREATED"


def test_visual_run_manifest_rejects_unknown_state() -> None:
    payload = valid_visual_run_manifest()
    payload["state"] = "DONE_ENOUGH"
    with pytest.raises(VisualContractError, match="state"):
        validate_visual_contract(payload, contract="visual_run_manifest")


def test_visual_run_manifest_rejects_unexpected_property() -> None:
    payload = valid_visual_run_manifest()
    payload["codex_says_ok"] = True
    with pytest.raises(VisualContractError, match="Unexpected properties"):
        validate_visual_contract(payload, contract="visual_run_manifest")


def test_read_visual_contract_rejects_non_object_root(tmp_path: Path) -> None:
    source = tmp_path / "manifest.json"
    source.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    with pytest.raises(VisualContractError, match="root must be an object"):
        read_visual_contract(source, contract="visual_run_manifest")
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py -q -p no:cacheprovider
```

Expected: collection fails because `cad_agent.visual_contracts` and the fixture module do not exist.

- [ ] **Step 3: Create the shared fixture and exact run-manifest shape**

Create `tests/visual_supervisor_fixtures.py` with:

```python
from __future__ import annotations

import copy
from typing import Any

RUN_ID = "RUN-VISUAL-SYNTHETIC-001"
SOURCE_SHA = "1" * 64
DRAWING_SHA = "2" * 64
MUTATION_SHA = "3" * 64
RENDER_SHA = "4" * 64
REFERENCE_PACKAGE_SHA = "5" * 64
COMPARISON_SHA = "6" * 64
REVIEW_SHA = "7" * 64
INITIAL_TARGET_SHA = "8" * 64
PAGE_ID = "PAGE-001"
VIEW_ID = "SIDE"
REGION_ID = "SIDE-CABIN"
TARGET_PATH = "D:\\Synthetic\\drawing.dwg"
BACKUP_ROOT = "D:\\Synthetic\\Backups"


def clone(payload: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(payload)


def valid_visual_run_manifest() -> dict[str, Any]:
    return {
        "schema_version": "visual-run-manifest-1.0",
        "run_id": RUN_ID,
        "state": "CREATED",
        "authority": "DISPOSABLE_REVIEW",
        "source": {
            "source_type": "PDF",
            "source_sha256": SOURCE_SHA,
            "page_ids": [PAGE_ID],
        },
        "drawing": {
            "absolute_path": TARGET_PATH,
            "initial_sha256": DRAWING_SHA,
        },
        "evidence_root": "runs/RUN-VISUAL-SYNTHETIC-001",
        "latest_mutation_sha256": MUTATION_SHA,
    }
```

- [ ] **Step 4: Implement minimal closed validation helpers**

Create `cad_agent/visual_contracts.py` with these helper names and semantics:

```python
from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class VisualContractError(ValueError):
    """Raised when a Visual Supervisor contract is malformed or unsafe."""


def _fail(contract: str, message: str) -> None:
    raise VisualContractError(f"{contract}: {message}")


def _keys(
    payload: Mapping[str, object],
    *,
    contract: str,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    missing = sorted(required - set(payload))
    unexpected = sorted(set(payload) - allowed)
    if missing:
        _fail(contract, f"missing required properties: {', '.join(missing)}")
    if unexpected:
        _fail(contract, f"Unexpected properties: {', '.join(unexpected)}")


def _object(value: object, *, contract: str, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(contract, f"{path} must be an object")
    return value


def _string(value: object, *, contract: str, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(contract, f"{path} must be a non-empty string")
    return value


def _identifier(value: object, *, contract: str, path: str) -> str:
    text = _string(value, contract=contract, path=path)
    if _ID_RE.fullmatch(text) is None:
        _fail(contract, f"{path} has invalid identifier format")
    return text


def _sha256(value: object, *, contract: str, path: str) -> str:
    text = _string(value, contract=contract, path=path)
    if _HASH_RE.fullmatch(text) is None:
        _fail(contract, f"{path} must be a lowercase SHA-256")
    return text


def _finite_number(value: object, *, contract: str, path: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(contract, f"{path} must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        _fail(contract, f"{path} must be finite")
    return value


def _string_list(value: object, *, contract: str, path: str, min_items: int = 0) -> list[str]:
    if not isinstance(value, list) or len(value) < min_items:
        _fail(contract, f"{path} must contain at least {min_items} items")
    for index, item in enumerate(value):
        _string(item, contract=contract, path=f"{path}[{index}]")
    return value


def _validate_visual_run_manifest(payload: dict[str, Any]) -> None:
    contract = "visual_run_manifest"
    required = {
        "schema_version",
        "run_id",
        "state",
        "authority",
        "source",
        "drawing",
        "evidence_root",
        "latest_mutation_sha256",
    }
    _keys(payload, contract=contract, required=required)
    if payload["schema_version"] != "visual-run-manifest-1.0":
        _fail(contract, "schema_version must be 'visual-run-manifest-1.0'")
    _identifier(payload["run_id"], contract=contract, path="run_id")
    states = {
        "CREATED",
        "SOURCE_NORMALIZED",
        "DIMENSIONS_OBSERVED",
        "DIMENSION_GATE_READY",
        "DRAFT_GENERATED",
        "REGIONS_CHECKING",
        "REPAIRING",
        "LOCAL_VISUAL_VERIFIED",
        "GLOBAL_VERIFIED",
        "PUBLISHING",
        "POST_SAVE_VERIFYING",
        "PUBLISHED",
        "NEEDS_HUMAN",
        "DIMENSION_CONFLICT",
        "NO_VISUAL_IMPROVEMENT",
        "EXECUTION_FAILED",
        "PUBLISH_REFUSED",
        "ROLLED_BACK",
    }
    if payload["state"] not in states:
        _fail(contract, "state is invalid")
    if payload["authority"] not in {"DISPOSABLE_REVIEW", "AUTHORITATIVE_CANDIDATE"}:
        _fail(contract, "authority is invalid")
    source = _object(payload["source"], contract=contract, path="source")
    _keys(source, contract=contract, required={"source_type", "source_sha256", "page_ids"})
    if source["source_type"] not in {"IMAGE", "PDF"}:
        _fail(contract, "source.source_type must be IMAGE or PDF")
    _sha256(source["source_sha256"], contract=contract, path="source.source_sha256")
    _string_list(source["page_ids"], contract=contract, path="source.page_ids", min_items=1)
    drawing = _object(payload["drawing"], contract=contract, path="drawing")
    _keys(drawing, contract=contract, required={"absolute_path", "initial_sha256"})
    _string(drawing["absolute_path"], contract=contract, path="drawing.absolute_path")
    _sha256(drawing["initial_sha256"], contract=contract, path="drawing.initial_sha256")
    _string(payload["evidence_root"], contract=contract, path="evidence_root")
    _sha256(payload["latest_mutation_sha256"], contract=contract, path="latest_mutation_sha256")


_VALIDATORS: dict[str, Callable[[dict[str, Any]], None]] = {
    "visual_run_manifest": _validate_visual_run_manifest,
}


def validate_visual_contract(
    payload: Mapping[str, object],
    *,
    contract: str,
) -> dict[str, object]:
    key = contract.replace("-", "_")
    validator = _VALIDATORS.get(key)
    if validator is None:
        raise VisualContractError(f"unsupported contract kind: {contract}")
    if not isinstance(payload, Mapping):
        raise VisualContractError(f"{contract}: root must be an object")
    copied = copy.deepcopy(dict(payload))
    validator(copied)
    return copied


def read_visual_contract(path: Path, *, contract: str) -> dict[str, object]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VisualContractError(f"Cannot read {contract}: {source}") from exc
    if not isinstance(payload, dict):
        raise VisualContractError(f"{contract}: root must be an object")
    return validate_visual_contract(payload, contract=contract)
```

- [ ] **Step 5: Add the closed schema and matching example**

Create `visual-run-manifest.schema.json` with required properties matching `_validate_visual_run_manifest`, exact enums above, ID/hash patterns, `minItems: 1` for `page_ids`, and `additionalProperties: false` for root, `source`, and `drawing`.

Create `examples/visual-run-manifest.json` with the exact literal values returned by `valid_visual_run_manifest()`.

- [ ] **Step 6: Add schema-alignment assertions**

In `tests/test_visual_supervisor_schema_alignment.py`, load every example/schema pair and assert:

```python
def test_every_visual_schema_is_closed_and_example_matches_validator() -> None:
    root = Path(__file__).resolve().parents[1]
    contract_root = root / "contracts" / "visual-supervisor"
    example_root = contract_root / "examples"
    for example_path in sorted(example_root.glob("*.json")):
        schema_path = contract_root / f"{example_path.stem}.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        payload = json.loads(example_path.read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(payload)
        validate_visual_contract(payload, contract=example_path.stem.replace("-", "_"))
```

Add a recursive helper that walks every schema object containing `type: "object"` and asserts `additionalProperties` is exactly `false`.

- [ ] **Step 7: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 8: Inspect and commit**

Run:

```powershell
git diff --check
git status --short
git diff -- cad_agent/visual_contracts.py contracts/visual-supervisor tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_schema_alignment.py tests/visual_supervisor_fixtures.py
```

Commit:

```powershell
git add cad_agent/visual_contracts.py contracts/visual-supervisor tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_schema_alignment.py
git commit -m "feat: add visual supervisor contract foundation"
```

---

### Task 2: Dimension Register contract and gate

**Files:**
- Modify: `cad_agent/visual_contracts.py`
- Create: `contracts/visual-supervisor/dimension-register.schema.json`
- Create: `contracts/visual-supervisor/examples/dimension-register.json`
- Modify: `tests/visual_supervisor_fixtures.py`
- Modify: `tests/test_visual_supervisor_contracts.py`
- Modify: `tests/test_visual_supervisor_schema_alignment.py`
- Create: `tests/test_visual_supervisor_contract_policy.py`

**Interfaces:**
- Consumes: validation helpers and registry from Task 1.
- Produces: contract key `dimension_register` and `require_dimension_gate_ready(register)`.

- [ ] **Step 1: Add failing dimension validation and gate tests**

Add a fixture `valid_dimension_register()` containing:

```python
{
    "schema_version": "dimension-register-1.0",
    "run_id": RUN_ID,
    "source_sha256": SOURCE_SHA,
    "page_id": PAGE_ID,
    "view_id": VIEW_ID,
    "coverage": {
        "clusters_detected": 1,
        "clusters_processed": 1,
        "page_coverage_percent": 100.0,
    },
    "summary": {
        "confirmed": 1,
        "unresolved": 0,
        "conflicts": 0,
    },
    "dimensions": [
        {
            "id": "DIM-SIDE-001",
            "display_text": "4500",
            "value": 4500.0,
            "unit": "mm",
            "kind": "HORIZONTAL_DISTANCE",
            "role": "DRIVING",
            "status": "CONFIRMED",
            "critical": True,
            "from_ref": {"type": "DATUM", "id": "FRONT_AXLE_CENTER"},
            "to_ref": {"type": "DATUM", "id": "REAR_AXLE_CENTER"},
            "source_evidence": {
                "crop_id": "DIMCLUSTER-001",
                "bbox": [100, 200, 600, 260],
                "crop_sha256": REFERENCE_PACKAGE_SHA,
            },
            "text_confidence": 0.99,
            "attachment_confidence": 0.96,
            "blocker_scope": [],
        }
    ],
}
```

Add tests:

```python
def test_confirmed_driving_dimension_requires_both_attachments() -> None:
    payload = valid_dimension_register()
    del payload["dimensions"][0]["to_ref"]
    with pytest.raises(VisualContractError, match="to_ref"):
        validate_visual_contract(payload, contract="dimension_register")


def test_unresolved_critical_dimension_requires_blocker_scope() -> None:
    payload = valid_dimension_register()
    dimension = payload["dimensions"][0]
    dimension["role"] = "AMBIGUOUS"
    dimension["status"] = "UNRESOLVED"
    dimension["blocker_scope"] = []
    payload["summary"] = {"confirmed": 0, "unresolved": 1, "conflicts": 0}
    with pytest.raises(VisualContractError, match="blocker_scope"):
        validate_visual_contract(payload, contract="dimension_register")


def test_dimension_gate_rejects_incomplete_cluster_disposition() -> None:
    payload = valid_dimension_register()
    payload["coverage"]["clusters_detected"] = 2
    with pytest.raises(VisualContractError, match="clusters"):
        require_dimension_gate_ready(payload)


def test_dimension_gate_accepts_complete_confirmed_register() -> None:
    require_dimension_gate_ready(valid_dimension_register())
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py -q -p no:cacheprovider
```

Expected: failures because `dimension_register` and `require_dimension_gate_ready` are unsupported.

- [ ] **Step 3: Implement exact dimension validation**

Add enum constants:

```python
_DIMENSION_ROLES = {"DRIVING", "REFERENCE", "DERIVED", "AMBIGUOUS", "CONFLICT"}
_DIMENSION_STATUSES = {"CONFIRMED", "UNRESOLVED", "CONFLICT"}
```

Implement `_validate_dimension_register()` with exact root keys from the fixture. Validate:

- detected/processed counts are non-negative integers;
- processed cannot exceed detected;
- coverage percent is finite and between 0 and 100;
- summary counts are non-negative integers and equal the disposition counts in `dimensions`;
- every observation has exact keys;
- bbox is exactly four finite numbers;
- confidence values are between 0 and 1;
- `DRIVING` plus `CONFIRMED` requires `from_ref` and `to_ref`;
- critical `UNRESOLVED` or `CONFLICT` requires non-empty `blocker_scope`;
- `CONFLICT` role must use `CONFLICT` status;
- `AMBIGUOUS` role cannot use `CONFIRMED` status.

Implement:

```python
def require_dimension_gate_ready(register: Mapping[str, object]) -> None:
    validated = validate_visual_contract(register, contract="dimension_register")
    coverage = validated["coverage"]
    if coverage["clusters_processed"] != coverage["clusters_detected"]:
        raise VisualContractError("dimension_register: not all detected clusters have dispositions")
    if coverage["page_coverage_percent"] != 100.0:
        raise VisualContractError("dimension_register: page coverage must be 100 percent")
    for dimension in validated["dimensions"]:
        if dimension["critical"] and dimension["status"] in {"UNRESOLVED", "CONFLICT"}:
            raise VisualContractError(
                f"dimension_register: critical dimension {dimension['id']} blocks {dimension['blocker_scope']}"
            )
```

Register `dimension_register` in `_VALIDATORS`.

- [ ] **Step 4: Add matching closed schema and example**

Create the schema with exact enums and conditional rules:

- `if role == DRIVING and status == CONFIRMED`, then require `from_ref` and `to_ref`;
- `if critical == true and status` is `UNRESOLVED` or `CONFLICT`, then `blocker_scope.minItems = 1`;
- all object levels closed.

Create the example from the fixture using literal hashes.

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 6: Inspect and commit**

```powershell
git diff --check
git diff -- cad_agent/visual_contracts.py contracts/visual-supervisor tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py
git add cad_agent/visual_contracts.py contracts/visual-supervisor tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py
git commit -m "feat: add dimension register contract gate"
```

---

### Task 3: Geometry Comparison contract

**Files:**
- Modify: `cad_agent/visual_contracts.py`
- Create: `contracts/visual-supervisor/geometry-comparison.schema.json`
- Create: `contracts/visual-supervisor/examples/geometry-comparison.json`
- Modify: `tests/visual_supervisor_fixtures.py`
- Modify: `tests/test_visual_supervisor_contracts.py`
- Modify: `tests/test_visual_supervisor_schema_alignment.py`

**Interfaces:**
- Consumes: Task 1 helpers.
- Produces: contract key `geometry_comparison` with stable metric names consumed by VS-T2, VS-T4, and VS-T6.

- [ ] **Step 1: Add the failing valid/invalid metric tests**

Define fixture:

```python
{
    "schema_version": "geometry-comparison-1.0",
    "comparison_id": "GC-SIDE-CABIN-001",
    "run_id": RUN_ID,
    "region_id": REGION_ID,
    "reference_package_sha256": REFERENCE_PACKAGE_SHA,
    "cad_render_sha256": RENDER_SHA,
    "mutation_sha256": MUTATION_SHA,
    "alignment": {
        "status": "ALIGNED",
        "method": "VERIFIED_DATUM_SIMILARITY",
        "anchor_ids": ["FRONT_AXLE_CENTER", "REAR_AXLE_CENTER"],
        "transform_sha256": COMPARISON_SHA,
    },
    "metrics": {
        "silhouette_iou": 0.92,
        "chamfer_distance_normalized": 0.02,
        "hausdorff_p95_normalized": 0.03,
        "centroid_offset_x_ratio": 0.01,
        "centroid_offset_y_ratio": 0.01,
        "width_ratio_error": 0.02,
        "height_ratio_error": 0.02,
        "missing_edge_ratio": 0.01,
        "extra_edge_ratio": 0.01,
        "connected_component_difference": 0,
    },
    "trend": "IMPROVED",
    "previous_comparison_sha256": COMPARISON_SHA,
}
```

Tests must reject:

```python
def test_geometry_comparison_rejects_out_of_range_iou() -> None:
    payload = valid_geometry_comparison()
    payload["metrics"]["silhouette_iou"] = 1.1
    with pytest.raises(VisualContractError, match="silhouette_iou"):
        validate_visual_contract(payload, contract="geometry_comparison")


def test_geometry_comparison_rejects_aligned_without_two_anchors() -> None:
    payload = valid_geometry_comparison()
    payload["alignment"]["anchor_ids"] = ["ONLY_ONE"]
    with pytest.raises(VisualContractError, match="anchor_ids"):
        validate_visual_contract(payload, contract="geometry_comparison")


def test_geometry_comparison_rejects_non_finite_metric() -> None:
    payload = valid_geometry_comparison()
    payload["metrics"]["height_ratio_error"] = float("nan")
    with pytest.raises(VisualContractError, match="finite"):
        validate_visual_contract(payload, contract="geometry_comparison")
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py -q -p no:cacheprovider
```

Expected: unsupported `geometry_comparison` failures.

- [ ] **Step 3: Implement validation and schema**

Use exact enums:

```python
_ALIGNMENT_STATUSES = {"ALIGNED", "FAILED"}
_COMPARISON_TRENDS = {"BASELINE", "IMPROVED", "REGRESSED", "UNCHANGED"}
```

Validate all ratio/distance fields as finite and non-negative; `silhouette_iou` is between 0 and 1; `connected_component_difference` is an integer; `ALIGNED` requires at least two unique anchors; `FAILED` requires an empty metric object and `trend == "BASELINE"`; `BASELINE` requires `previous_comparison_sha256` to be `None`, while other trends require a hash.

Represent nullable previous hash in the example as a real hash because its trend is `IMPROVED`.

Create a closed schema with matching conditionals and register the validator.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
git diff --check
git add cad_agent/visual_contracts.py contracts/visual-supervisor tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_schema_alignment.py
git commit -m "feat: add geometry comparison contract"
```

---

### Task 4: Independent Visual Review contract

**Files:**
- Modify: `cad_agent/visual_contracts.py`
- Create: `contracts/visual-supervisor/visual-review.schema.json`
- Create: `contracts/visual-supervisor/examples/visual-review.json`
- Modify: `tests/visual_supervisor_fixtures.py`
- Modify: `tests/test_visual_supervisor_contracts.py`
- Modify: `tests/test_visual_supervisor_contract_policy.py`
- Modify: `tests/test_visual_supervisor_schema_alignment.py`

**Interfaces:**
- Consumes: Dimension and Geometry contract IDs/hashes.
- Produces: contract key `visual_review`; this is the only contract allowed to carry a visual verdict.

- [ ] **Step 1: Add failing visual-authority tests**

Create fixture with:

```python
{
    "schema_version": "visual-review-1.0",
    "review_id": "VR-SIDE-CABIN-001",
    "run_id": RUN_ID,
    "region_id": REGION_ID,
    "iteration": 1,
    "reference_package_sha256": REFERENCE_PACKAGE_SHA,
    "cad_render_sha256": RENDER_SHA,
    "mutation_sha256": MUTATION_SHA,
    "geometry_comparison_sha256": COMPARISON_SHA,
    "verdict": "FAIL",
    "severity": "MAJOR",
    "confidence": 0.94,
    "findings": [
        {
            "finding_id": "FIND-001",
            "category": "SHAPE_MISMATCH",
            "feature": "CABIN_ROOF",
            "severity": "MAJOR",
            "description": "Roof contour is too high relative to the approved source.",
            "evidence_refs": ["overlay.png", "difference-mask.png"],
        }
    ],
    "repair_intent": {
        "change": ["LOWER_CABIN_ROOF_MIDPOINT"],
        "preserve": ["FRONT_AXLE_CENTER", "CABIN_BOTTOM_DATUM"],
        "required_measurements": ["CABIN_MAX_HEIGHT"],
        "requested_next_evidence": [],
    },
}
```

Tests:

```python
def test_visual_review_rejects_free_form_verdict() -> None:
    payload = valid_visual_review()
    payload["verdict"] = "LOOKS_GOOD"
    with pytest.raises(VisualContractError, match="verdict"):
        validate_visual_contract(payload, contract="visual_review")


def test_visual_review_pass_rejects_findings() -> None:
    payload = valid_visual_review()
    payload["verdict"] = "PASS"
    with pytest.raises(VisualContractError, match="PASS"):
        validate_visual_contract(payload, contract="visual_review")


def test_visual_review_fail_requires_actionable_repair_intent() -> None:
    payload = valid_visual_review()
    payload["repair_intent"]["change"] = []
    with pytest.raises(VisualContractError, match="change"):
        validate_visual_contract(payload, contract="visual_review")


def test_visual_review_needs_human_requires_requested_evidence_or_finding() -> None:
    payload = valid_visual_review()
    payload["verdict"] = "NEEDS_HUMAN"
    payload["findings"] = []
    payload["repair_intent"]["requested_next_evidence"] = []
    with pytest.raises(VisualContractError, match="NEEDS_HUMAN"):
        validate_visual_contract(payload, contract="visual_review")
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement the validator and schema**

Use exact enums:

```python
_VISUAL_VERDICTS = {"PASS", "FAIL", "NEEDS_HUMAN"}
_SEVERITIES = {"INFO", "MINOR", "MAJOR", "CRITICAL"}
_FINDING_CATEGORIES = {
    "MISSING_FEATURE",
    "EXTRA_FEATURE",
    "TOPOLOGY_MISMATCH",
    "POSITION_MISMATCH",
    "PROPORTION_MISMATCH",
    "SHAPE_MISMATCH",
    "DIMENSION_MISMATCH",
    "ANNOTATION_LAYOUT_MISMATCH",
    "SOURCE_TECHNICAL_CONFLICT",
}
```

Validation policy:

- confidence is between 0 and 1;
- each finding has exact keys and non-empty evidence refs;
- `PASS` requires empty findings and empty `change`;
- `FAIL` requires at least one `MAJOR` or `CRITICAL` finding and non-empty `change`;
- `NEEDS_HUMAN` requires at least one finding or requested next evidence;
- `preserve` is required and non-empty for `FAIL`;
- no field named `publish`, `publication`, `target_path`, or `save` is permitted because all objects are closed.

Create matching schema conditionals, example, fixture, registry entry, and tests.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
git diff --check
git add cad_agent/visual_contracts.py contracts/visual-supervisor tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py
git commit -m "feat: add independent visual review contract"
```

---

### Task 5: Codex Repair Plan contract with no pass/publish authority

**Files:**
- Modify: `cad_agent/visual_contracts.py`
- Create: `contracts/visual-supervisor/repair-plan.schema.json`
- Create: `contracts/visual-supervisor/examples/repair-plan.json`
- Modify: `tests/visual_supervisor_fixtures.py`
- Modify: `tests/test_visual_supervisor_contracts.py`
- Modify: `tests/test_visual_supervisor_contract_policy.py`
- Modify: `tests/test_visual_supervisor_schema_alignment.py`

**Interfaces:**
- Consumes: validated Visual Review ID, target drawing hash, stable target identities, and allowed business operation names.
- Produces: contract key `repair_plan` consumed by VS-T5 and VS-T6.

- [ ] **Step 1: Add failing repair authority tests**

Fixture:

```python
{
    "schema_version": "repair-plan-1.0",
    "repair_id": "RP-SIDE-CABIN-001",
    "source_review_id": "VR-SIDE-CABIN-001",
    "run_id": RUN_ID,
    "target_drawing_sha256": DRAWING_SHA,
    "operations": [
        {
            "operation": "ADJUST_SPLINE_CONTROL_REGION",
            "target": {
                "stable_entity_id": "PART:CABIN_OUTER",
                "feature": "ROOF",
            },
            "preserve_anchors": ["CABIN_ROOF_FRONT", "CABIN_ROOF_REAR"],
            "constraint_refs": ["DIM-SIDE-008"],
        }
    ],
    "affected_regions": [REGION_ID, "SIDE-ANNOTATION-R02"],
    "expected_improvements": ["height_ratio_error:DECREASE"],
    "must_not_worsen": ["engineering_constraints", "centroid_offset_x_ratio"],
    "rollback_candidate_sha256": DRAWING_SHA,
}
```

Tests:

```python
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("verdict", "PASS"),
        ("publish", True),
        ("publication_policy", "AUTO"),
        ("target_path", "D:\\Synthetic\\drawing.dwg"),
    ],
)
def test_repair_plan_rejects_pass_and_publish_authority(field: str, value: object) -> None:
    payload = valid_repair_plan()
    payload[field] = value
    with pytest.raises(VisualContractError, match="Unexpected properties"):
        validate_visual_contract(payload, contract="repair_plan")


def test_repair_plan_rejects_direct_pixel_coordinate_operation() -> None:
    payload = valid_repair_plan()
    payload["operations"][0]["operation"] = "MOVE_TO_PIXEL"
    with pytest.raises(VisualContractError, match="operation"):
        validate_visual_contract(payload, contract="repair_plan")


def test_repair_plan_requires_affected_regions() -> None:
    payload = valid_repair_plan()
    payload["affected_regions"] = []
    with pytest.raises(VisualContractError, match="affected_regions"):
        validate_visual_contract(payload, contract="repair_plan")
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_visual_supervisor_contract_policy.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement exact allowed operations**

Use only:

```python
_ALLOWED_REPAIR_OPERATIONS = {
    "MOVE_COMPONENT",
    "ALIGN_COMPONENT",
    "REPLACE_POLYLINE_SEGMENT",
    "ADJUST_ARC",
    "ADJUST_SPLINE_CONTROL_REGION",
    "ADD_MISSING_FEATURE",
    "REMOVE_EXTRA_FEATURE",
    "REPLACE_WITH_APPROVED_BLOCK",
    "CREATE_NATIVE_DIMENSION",
    "REPAIR_NATIVE_DIMENSION",
}
```

Each operation requires exact `target`, non-empty `preserve_anchors`, and `constraint_refs` list. Root requires non-empty operations, affected regions, expected improvements, and must-not-worsen entries. Validate all hashes and IDs. Close every schema object so authority fields are rejected structurally.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
git diff --check
git add cad_agent/visual_contracts.py contracts/visual-supervisor tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py
git commit -m "feat: constrain codex repair plan authority"
```

---

### Task 6: Region Verification Register and stale-evidence gate

**Files:**
- Modify: `cad_agent/visual_contracts.py`
- Create: `contracts/visual-supervisor/region-verification-register.schema.json`
- Create: `contracts/visual-supervisor/examples/region-verification-register.json`
- Modify: `tests/visual_supervisor_fixtures.py`
- Modify: `tests/test_visual_supervisor_contracts.py`
- Modify: `tests/test_visual_supervisor_contract_policy.py`
- Modify: `tests/test_visual_supervisor_schema_alignment.py`

**Interfaces:**
- Consumes: source crop, CAD render, mutation, comparison, visual review, dimension, and entity evidence hashes.
- Produces: contract key `region_verification_register` and `require_region_verified(region)`.

- [ ] **Step 1: Add failing stale and aggregate-gate tests**

Fixture:

```python
{
    "schema_version": "region-verification-register-1.0",
    "run_id": RUN_ID,
    "region_id": REGION_ID,
    "view_id": VIEW_ID,
    "criticality": "CRITICAL",
    "source_crop": {
        "source_sha256": SOURCE_SHA,
        "crop_sha256": REFERENCE_PACKAGE_SHA,
        "bbox": [100, 100, 700, 600],
    },
    "cad_evidence": {
        "drawing_sha256": DRAWING_SHA,
        "render_sha256": RENDER_SHA,
        "mutation_sha256": MUTATION_SHA,
        "latest_mutation_sha256": MUTATION_SHA,
    },
    "expected_features": ["cabin_outline", "front_axle_centerline"],
    "dimension_refs": ["DIM-SIDE-001"],
    "entity_refs": ["PART:CABIN_OUTER"],
    "geometry": {"status": "PASS", "comparison_sha256": COMPARISON_SHA},
    "visual": {"status": "PASS", "review_sha256": REVIEW_SHA},
    "engineering": {"status": "PASS", "measurement_sha256": COMPARISON_SHA},
    "unresolved_critical_items": [],
    "status": "VERIFIED",
}
```

Tests:

```python
def test_region_verified_rejects_stale_mutation_binding() -> None:
    payload = valid_region_verification_register()
    payload["cad_evidence"]["latest_mutation_sha256"] = "9" * 64
    with pytest.raises(VisualContractError, match="stale"):
        require_region_verified(payload)


@pytest.mark.parametrize(("gate", "status"), [("geometry", "FAIL"), ("visual", "FAIL"), ("engineering", "FAIL")])
def test_region_verified_requires_every_constituent_gate(gate: str, status: str) -> None:
    payload = valid_region_verification_register()
    payload[gate]["status"] = status
    with pytest.raises(VisualContractError, match=gate):
        require_region_verified(payload)


def test_region_verified_rejects_unresolved_critical_items() -> None:
    payload = valid_region_verification_register()
    payload["unresolved_critical_items"] = ["DIM-SIDE-014"]
    with pytest.raises(VisualContractError, match="unresolved"):
        require_region_verified(payload)
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_visual_supervisor_contract_policy.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement validation and gate**

Use statuses:

```python
_REGION_STATUSES = {"PENDING", "CHECKING", "FAILED", "NEEDS_REVIEW", "VERIFIED", "STALE"}
_GATE_STATUSES = {"PASS", "FAIL", "NOT_RUN"}
_CRITICALITIES = {"CRITICAL", "NORMAL"}
```

Implement:

```python
def require_region_verified(region: Mapping[str, object]) -> None:
    validated = validate_visual_contract(region, contract="region_verification_register")
    if validated["status"] != "VERIFIED":
        raise VisualContractError("region_verification_register: status must be VERIFIED")
    evidence = validated["cad_evidence"]
    if evidence["mutation_sha256"] != evidence["latest_mutation_sha256"]:
        raise VisualContractError("region_verification_register: render evidence is stale")
    for gate in ("geometry", "visual", "engineering"):
        if validated[gate]["status"] != "PASS":
            raise VisualContractError(f"region_verification_register: {gate} gate must PASS")
    if validated["unresolved_critical_items"]:
        raise VisualContractError("region_verification_register: unresolved critical items remain")
```

The validator itself must reject `status == VERIFIED` when these invariants are false, so invalid persisted evidence cannot be loaded even without the enforcement helper.

- [ ] **Step 4: Add schema, example, run GREEN, and commit**

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
git diff --check
git add cad_agent/visual_contracts.py contracts/visual-supervisor tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py
git commit -m "feat: add region verification stale-evidence gate"
```

---

### Task 7: Run-scoped Auto-Publish Authorization contract

**Files:**
- Modify: `cad_agent/visual_contracts.py`
- Create: `contracts/visual-supervisor/auto-publish-authorization.schema.json`
- Create: `contracts/visual-supervisor/examples/auto-publish-authorization.json`
- Modify: `tests/visual_supervisor_fixtures.py`
- Modify: `tests/test_visual_supervisor_contracts.py`
- Modify: `tests/test_visual_supervisor_contract_policy.py`
- Modify: `tests/test_visual_supervisor_schema_alignment.py`

**Interfaces:**
- Consumes: exact run ID, absolute target path, current target hash, backup root, approval identity, and consumed state.
- Produces: contract key `auto_publish_authorization` and `require_auto_publish_authorized()`.

- [ ] **Step 1: Add failing authorization binding tests**

Fixture:

```python
{
    "schema_version": "auto-publish-authorization-1.0",
    "authorization_id": "AUTH-VISUAL-SYNTHETIC-001",
    "run_id": RUN_ID,
    "policy": "AUTO_PUBLISH_AFTER_ALL_GATES",
    "target_path": TARGET_PATH,
    "expected_initial_sha256": INITIAL_TARGET_SHA,
    "allowed_backup_root": BACKUP_ROOT,
    "single_use": True,
    "expires_after_run": True,
    "consumed": False,
    "authorized_by": "OWNER",
    "approval_reference": "APPROVAL-SYNTHETIC-001",
    "status": "APPROVED",
}
```

Tests:

```python
def test_publish_authorization_requires_single_use_and_expiry() -> None:
    payload = valid_auto_publish_authorization()
    payload["single_use"] = False
    with pytest.raises(VisualContractError, match="single_use"):
        validate_visual_contract(payload, contract="auto_publish_authorization")


def test_publish_authorization_rejects_consumed_permission() -> None:
    payload = valid_auto_publish_authorization()
    payload["consumed"] = True
    with pytest.raises(VisualContractError, match="consumed"):
        require_auto_publish_authorized(
            payload,
            run_id=RUN_ID,
            target_path=TARGET_PATH,
            target_sha256=INITIAL_TARGET_SHA,
        )


def test_publish_authorization_rejects_target_hash_mismatch() -> None:
    with pytest.raises(VisualContractError, match="target SHA"):
        require_auto_publish_authorized(
            valid_auto_publish_authorization(),
            run_id=RUN_ID,
            target_path=TARGET_PATH,
            target_sha256="9" * 64,
        )


def test_publish_authorization_accepts_exact_binding() -> None:
    require_auto_publish_authorized(
        valid_auto_publish_authorization(),
        run_id=RUN_ID,
        target_path=TARGET_PATH,
        target_sha256=INITIAL_TARGET_SHA,
    )
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_visual_supervisor_contract_policy.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement strict validation and enforcement**

Validation requires:

- policy exactly `AUTO_PUBLISH_AFTER_ALL_GATES`;
- status exactly `APPROVED`;
- target and backup paths are absolute Windows paths with drive letter and are not equal;
- `single_use` and `expires_after_run` are exactly `true`;
- consumed is boolean;
- all identifiers and hashes are valid;
- no wildcard path or directory traversal segment is accepted.

Implement exact match enforcement for run ID, case-insensitive normalized Windows target path, and target SHA. Do not mutate the authorization in this contract-only task; VS-T7 later owns atomic consumption recording.

- [ ] **Step 4: Add schema, example, run GREEN, and commit**

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
git diff --check
git add cad_agent/visual_contracts.py contracts/visual-supervisor tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py
git commit -m "feat: add run-scoped publish authorization contract"
```

---

### Task 8: Cross-contract completeness, documentation, and authoritative verification

**Files:**
- Modify: `cad_agent/visual_contracts.py`
- Modify: `tests/test_visual_supervisor_contracts.py`
- Modify: `tests/test_visual_supervisor_contract_policy.py`
- Modify: `tests/test_visual_supervisor_schema_alignment.py`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/STATUS.md`
- Modify: `tests/test_documentation_contract.py`

**Interfaces:**
- Consumes: every VS-T0 contract and policy helper.
- Produces: complete contract-only acceptance evidence and canonical documentation; no runtime visual loop.

- [ ] **Step 1: Add failing registry-completeness and authority tests**

Add:

```python
def test_supported_visual_contract_registry_is_exact() -> None:
    assert set(SUPPORTED_VISUAL_CONTRACTS) == {
        "visual_run_manifest",
        "dimension_register",
        "geometry_comparison",
        "visual_review",
        "repair_plan",
        "region_verification_register",
        "auto_publish_authorization",
    }


def test_only_visual_review_schema_contains_verdict_property() -> None:
    root = Path(__file__).resolve().parents[1] / "contracts" / "visual-supervisor"
    verdict_schemas = []
    for schema_path in sorted(root.glob("*.schema.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if "verdict" in schema.get("properties", {}):
            verdict_schemas.append(schema_path.name)
    assert verdict_schemas == ["visual-review.schema.json"]


def test_only_authorization_schema_contains_target_path() -> None:
    root = Path(__file__).resolve().parents[1] / "contracts" / "visual-supervisor"
    target_schemas = []
    for schema_path in sorted(root.glob("*.schema.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if "target_path" in schema.get("properties", {}):
            target_schemas.append(schema_path.name)
    assert target_schemas == ["auto-publish-authorization.schema.json"]
```

Add a documentation test requiring the architecture to contain `Visual Supervisor contract boundary`, `Codex cannot self-approve`, and `VS-T0 contract-only`; status must contain `real_data: NOT RUN`, `autocad_mechanical: NOT RUN`, and `OpenAI API: NOT RUN` in the VS-T0 record.

- [ ] **Step 2: Run tests and verify RED before documentation update**

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py tests/test_documentation_contract.py -q -p no:cacheprovider
```

Expected: documentation assertions fail until canonical docs are updated.

- [ ] **Step 3: Finish registry exports and module API**

Expose:

```python
SUPPORTED_VISUAL_CONTRACTS = tuple(sorted(_VALIDATORS))

__all__ = [
    "SUPPORTED_VISUAL_CONTRACTS",
    "VisualContractError",
    "read_visual_contract",
    "require_auto_publish_authorized",
    "require_dimension_gate_ready",
    "require_region_verified",
    "validate_visual_contract",
]
```

Add one test that mutating nested input after validation cannot mutate the validated return for every example contract.

- [ ] **Step 4: Update architecture honestly**

Add a subsection to `docs/ARCHITECTURE.md` stating:

```text
The Visual Supervisor contract boundary is pure Python and contract-only in VS-T0.
It defines dimension, comparison, independent visual review, repair-plan,
region-verification, run-manifest, and run-scoped publication-authorization
artifacts. Codex cannot self-approve visual fidelity or publication. No model
call, image comparator, AutoCAD evidence operation, repair loop, or publisher is
implemented by VS-T0; those remain later slices.
```

- [ ] **Step 5: Run the full focused contract suite**

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py tests/test_documentation_contract.py -q -p no:cacheprovider
```

Expected: all focused tests pass.

- [ ] **Step 6: Run static checks and aggregate verifier**

Run:

```powershell
git diff --check
python -m ruff check cad_agent/visual_contracts.py tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Expected:

- `git diff --check`: no output and exit 0;
- Ruff: pass;
- aggregate verifier: pass for available offline gates;
- `real_data`: `NOT RUN` for VS-T0;
- `autocad_mechanical`: `NOT RUN` for VS-T0;
- OpenAI API/model call: `NOT RUN`.

- [ ] **Step 7: Review the complete task diff**

Inspect:

```powershell
git status --short
git diff --stat
git diff -- cad_agent/visual_contracts.py contracts/visual-supervisor tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py docs/ARCHITECTURE.md docs/STATUS.md tests/test_documentation_contract.py
```

Reject the candidate if it contains runtime API calls, AutoCAD operations, private paths, customer data, generated drawings, visual-loop code, or publication mutation code.

- [ ] **Step 8: Record fresh status evidence**

Only after Step 6 succeeds, add a dated VS-T0 record to `docs/STATUS.md` containing:

- implementation head SHA;
- focused test counts;
- aggregate verifier result;
- schema/example count;
- `real_data: NOT RUN`;
- `autocad_mechanical: NOT RUN`;
- `OpenAI API: NOT RUN`;
- explicit statement that no visual comparison, model review, AutoCAD evidence, repair, or publication behavior is implemented yet.

Rerun the documentation and aggregate verification after editing status.

- [ ] **Step 9: Commit the integration record**

```powershell
git add cad_agent/visual_contracts.py contracts/visual-supervisor tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_contract_policy.py tests/test_visual_supervisor_schema_alignment.py docs/ARCHITECTURE.md docs/STATUS.md tests/test_documentation_contract.py
git commit -m "docs: record visual supervisor contract gate"
```

- [ ] **Step 10: Produce the VS-T0 handoff report**

The task report must state:

```text
Reused:
- canonical_json_sha256 and existing pure-Python contract style
- current package boundaries and authoritative verifier

Extended:
- new isolated visual contract registry and policy helpers
- canonical architecture/status documentation

New:
- seven closed schemas and seven synthetic examples
- dimension, comparison, visual-review, repair, region, run, and authorization contracts

Not implemented:
- OCR/dimension observation runtime
- geometry comparison runtime
- OpenAI multimodal calls
- AutoCAD render/entity/measurement evidence
- repair execution/orchestration
- production publication

Evidence:
- focused test commands and counts
- aggregate verifier result
- private/live/API gates recorded as NOT RUN
```

## VS-T0 Acceptance Criteria

VS-T0 is complete only when:

1. Seven exact contracts and examples exist under `contracts/visual-supervisor/`.
2. Every object schema is closed and every validator rejects unexpected properties.
3. Schema examples and pure-Python validators agree.
4. Canonical hashing remains deterministic through the existing helper.
5. Dimension role/status/attachment/coverage invariants pass focused tests.
6. Geometry metrics reject invalid ranges and non-finite values.
7. Visual Review is the only contract with visual verdict authority.
8. Repair Plan cannot contain pass or publication authority and cannot use direct pixel-coordinate operations.
9. Region verification rejects stale mutation binding, failed constituent gates, and unresolved critical items.
10. Auto-publish authorization is exact-run/path/hash bound, single-use, expiring, and unconsumed.
11. `docs/ARCHITECTURE.md` and `docs/STATUS.md` describe VS-T0 as contract-only.
12. Focused tests, Ruff, `git diff --check`, and `scripts/verify.ps1` pass on the recorded implementation head.
13. Private data, AutoCAD live, and OpenAI API gates remain honestly `NOT RUN`.

## Plan Self-Review

- Spec coverage: VS-T0 covers all stable contracts and authority boundaries required before VS-T1 through VS-T7; runtime implementation remains correctly deferred.
- Placeholder scan: no `TBD`, `TODO`, “implement later,” or undefined interface remains.
- Type consistency: contract keys, schema versions, fixture IDs, hashes, enum values, and public function signatures are consistent across tasks.
- Scope check: the plan contains pure Python, JSON contracts, tests, and documentation only; no external API, image runtime, AutoCAD operation, repair loop, or publisher mutation is introduced.
- Safety check: Codex self-approval and publication authority are structurally excluded, stale evidence fails closed, and automatic publication remains only an authorization contract for VS-T7 to consume later.
