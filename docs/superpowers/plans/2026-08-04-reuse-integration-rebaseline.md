# Reuse Integration Rebaseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Planned

**Planning date:** 2026-08-04

**Planning base SHA:** `4cc2c0f198484581f5781466e769441d4e7da669`

**Goal:** Establish a machine-verifiable repository-wide reuse inventory, compatibility baseline, architecture ratchet, and governance gate before any reuse-first runtime subsystem is implemented.

**Architecture:** Keep the current CAD Agent runtime unchanged while adding repository governance tooling around it. A strict inventory contract records which existing APIs are reused, extended, or genuinely missing; compatibility and architecture tests then prevent later tasks from creating duplicate OCR, solver, DXF, AutoCAD, repair, manifest, revision, verdict, or publication paths.

**Tech Stack:** Windows, Python 3.11, standard-library Python only for new audit tooling, pytest, JSON Schema draft 2020-12 documents plus strict pure-Python validation, GitHub Actions, existing `scripts/verify.ps1`, AutoCAD Mechanical 2027 gates reported truthfully as `PASS`, `FAIL`, `SKIP`, or `NOT RUN`.

## Global Constraints

- The authoritative design is `docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`.
- Preserve the current `primitive_ir_lib -> semantic_ir_lib -> agent_lib -> dxf_builder_lib -> mcp_integration_lib` execution engine.
- `cad_agent` remains a thin orchestration package and must not absorb OCR, recognition, solver, or CAD-geometry algorithms.
- Do not create a second OCR engine, dimension-recognition engine, semantic solver, DXF builder, AutoCAD dispatcher/transport, repair executor, manifest/checkpoint/revision truth store, visual-verdict path, or publisher.
- Preserve `run`, `resume`, `run-pdf`, `resume-pdf`, Drawing Setup, Dimension Pilot, DXF/headless review, and Mechanical review/repair behavior.
- M2 Drawing Initialization remains authoritative and may not be removed, bypassed, or reordered.
- New runtime workflows remain locked during this plan. This plan adds governance, tests, inventory, and documentation only.
- No previous-drawing library, retrieval index, 3D-first model, or unrestricted Codex mutation belongs in this plan.
- New audit tooling must use Python 3.11 standard library only; do not add dependencies or modify `requirements/windows-py311.lock`.
- Private drawings, source images, generated DWG/DXF, absolute workstation paths, customer data, credentials, API keys, and secrets remain outside Git.
- Missing private-data or live AutoCAD prerequisites are `SKIP` or `NOT RUN`, never `PASS`.
- Each task begins with a focused failing test, implements the smallest passing change, runs focused tests, inspects `git diff --check`, and commits one bounded change.

---

## File structure locked by this plan

```text
contracts/reuse-integration/
  reuse-inventory.schema.json
  legacy-cli-baseline.json
  architecture-boundaries.json
  examples/reuse-inventory.json

scripts/
  reuse_inventory.py
  export_cli_contract.py
  check_reuse_declaration.py
  check_architecture_boundaries.py

tests/
  fixtures/reuse-rebaseline/legacy-run-manifest-v1.json
  test_reuse_inventory_contract.py
  test_reuse_inventory_repository.py
  test_reuse_declaration.py
  test_reuse_legacy_compatibility.py
  test_reuse_architecture_boundaries.py
  test_reuse_rebaseline_docs.py

docs/superpowers/reuse/
  2026-08-04-reuse-inventory.json
  2026-08-04-reuse-integration-audit.md

docs/superpowers/implementation-records/
  2026-08-04-reuse-integration-rebaseline.md

.github/
  pull_request_template.md
  workflows/reuse-declaration.yml
```

`docs/ARCHITECTURE.md`, `docs/STATUS.md`, and `docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md` are modified only after the machine-readable audit passes.

---

### Task 1: Closed reuse-inventory contract and validator

**Files:**
- Create: `contracts/reuse-integration/reuse-inventory.schema.json`
- Create: `contracts/reuse-integration/examples/reuse-inventory.json`
- Create: `scripts/reuse_inventory.py`
- Test: `tests/test_reuse_inventory_contract.py`

**Interfaces:**
- Consumes: UTF-8 JSON inventory files and a repository root `Path`.
- Produces: `CLASSIFICATIONS`, `validate_inventory(payload)`, `read_inventory(path)`, `validate_against_repository(inventory, repo_root)`, and CLI command `python scripts/reuse_inventory.py check <inventory> --repo-root <root>`.

- [ ] **Step 1: Write the failing contract tests**

Create `tests/test_reuse_inventory_contract.py` with these cases:

```python
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/reuse_inventory.py"
EXAMPLE = ROOT / "contracts/reuse-integration/examples/reuse-inventory.json"


def _module():
    spec = importlib.util.spec_from_file_location("reuse_inventory", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_example_inventory_is_closed_and_valid() -> None:
    module = _module()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    validated = module.validate_inventory(payload)
    assert validated == payload
    assert validated["schema_version"] == "reuse-inventory-1.0"


def test_unknown_root_field_fails_closed() -> None:
    module = _module()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    with pytest.raises(ValueError, match="unexpected root fields"):
        module.validate_inventory(payload)


def test_new_missing_capability_requires_inspection_and_gap_reason() -> None:
    module = _module()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    item = payload["capabilities"][0]
    item["classification"] = "NEW_MISSING_CAPABILITY"
    item["inspected_paths"] = []
    item["gap_reason"] = ""
    with pytest.raises(ValueError, match="NEW_MISSING_CAPABILITY"):
        module.validate_inventory(payload)


def test_duplicate_capability_ids_are_rejected() -> None:
    module = _module()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["capabilities"].append(dict(payload["capabilities"][0]))
    with pytest.raises(ValueError, match="duplicate capability_id"):
        module.validate_inventory(payload)
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_inventory_contract.py -q -p no:cacheprovider
```

Expected: FAIL because `scripts/reuse_inventory.py` and the contract files do not exist.

- [ ] **Step 3: Add the closed JSON Schema**

Create `contracts/reuse-integration/reuse-inventory.schema.json` with root fields exactly:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "reuse-inventory.schema.json",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "repository",
    "base_sha",
    "generated_at_utc",
    "capabilities"
  ],
  "properties": {
    "schema_version": {"const": "reuse-inventory-1.0"},
    "repository": {"const": "duongchi90/cad-agent"},
    "base_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
    "generated_at_utc": {"type": "string", "format": "date-time"},
    "capabilities": {
      "type": "array",
      "minItems": 1,
      "items": {"$ref": "#/$defs/capability"}
    }
  },
  "$defs": {
    "nonEmptyString": {"type": "string", "minLength": 1},
    "stringList": {
      "type": "array",
      "items": {"$ref": "#/$defs/nonEmptyString"},
      "uniqueItems": true
    },
    "capability": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "capability_id",
        "capability",
        "current_owner",
        "current_paths",
        "current_apis",
        "current_consumers",
        "classification",
        "adapter",
        "tests",
        "acceptance_gate",
        "migration",
        "rollback",
        "inspected_paths",
        "gap_reason"
      ],
      "properties": {
        "capability_id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
        "capability": {"$ref": "#/$defs/nonEmptyString"},
        "current_owner": {"$ref": "#/$defs/nonEmptyString"},
        "current_paths": {"$ref": "#/$defs/stringList"},
        "current_apis": {"$ref": "#/$defs/stringList"},
        "current_consumers": {"$ref": "#/$defs/stringList"},
        "classification": {
          "enum": [
            "REUSE_AS_IS",
            "EXTEND_WITH_ADAPTER",
            "EXTEND_WITH_TEST",
            "REFACTOR_BEHIND_COMPATIBILITY_LAYER",
            "NEW_MISSING_CAPABILITY",
            "DEPRECATED_AFTER_MIGRATION"
          ]
        },
        "adapter": {"type": ["string", "null"]},
        "tests": {"$ref": "#/$defs/stringList"},
        "acceptance_gate": {"$ref": "#/$defs/nonEmptyString"},
        "migration": {"$ref": "#/$defs/nonEmptyString"},
        "rollback": {"$ref": "#/$defs/nonEmptyString"},
        "inspected_paths": {"$ref": "#/$defs/stringList"},
        "gap_reason": {"type": ["string", "null"]}
      }
    }
  }
}
```

- [ ] **Step 4: Add one valid synthetic example**

Create `contracts/reuse-integration/examples/reuse-inventory.json` containing one `REUSE_AS_IS` entry for the existing image/PDF recognition boundary. Use base SHA `4cc2c0f198484581f5781466e769441d4e7da669`, path `primitive_ir_lib/run_image.py`, API `primitive_ir_lib.run_image.run`, and a non-empty test/gate/migration/rollback description. Set `gap_reason` to `null`.

- [ ] **Step 5: Implement the strict pure-Python validator**

Create `scripts/reuse_inventory.py` with these public definitions and closed-field checks:

```python
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping


CLASSIFICATIONS = frozenset({
    "REUSE_AS_IS",
    "EXTEND_WITH_ADAPTER",
    "EXTEND_WITH_TEST",
    "REFACTOR_BEHIND_COMPATIBILITY_LAYER",
    "NEW_MISSING_CAPABILITY",
    "DEPRECATED_AFTER_MIGRATION",
})
_SHA256 = re.compile(r"^[0-9a-f]{40}$")
_ROOT_FIELDS = {
    "schema_version",
    "repository",
    "base_sha",
    "generated_at_utc",
    "capabilities",
}
_CAPABILITY_FIELDS = {
    "capability_id",
    "capability",
    "current_owner",
    "current_paths",
    "current_apis",
    "current_consumers",
    "classification",
    "adapter",
    "tests",
    "acceptance_gate",
    "migration",
    "rollback",
    "inspected_paths",
    "gap_reason",
}


def _non_empty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _string_list(value: object, path: str, *, min_items: int = 0) -> list[str]:
    if not isinstance(value, list) or len(value) < min_items:
        raise ValueError(f"{path} must be a string list with at least {min_items} items")
    result = [_non_empty_string(item, f"{path}[]") for item in value]
    if len(result) != len(set(result)):
        raise ValueError(f"{path} contains duplicates")
    return result


def validate_inventory(payload: Mapping[str, object]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("reuse inventory must be a JSON object")
    fields = set(payload)
    if fields != _ROOT_FIELDS:
        raise ValueError(
            f"unexpected root fields: missing={sorted(_ROOT_FIELDS - fields)} "
            f"extra={sorted(fields - _ROOT_FIELDS)}"
        )
    if payload["schema_version"] != "reuse-inventory-1.0":
        raise ValueError("unsupported reuse inventory schema_version")
    if payload["repository"] != "duongchi90/cad-agent":
        raise ValueError("reuse inventory repository is invalid")
    if not isinstance(payload["base_sha"], str) or _SHA256.fullmatch(payload["base_sha"]) is None:
        raise ValueError("base_sha must be a lowercase 40-character Git SHA")
    _non_empty_string(payload["generated_at_utc"], "generated_at_utc")
    capabilities = payload["capabilities"]
    if not isinstance(capabilities, list) or not capabilities:
        raise ValueError("capabilities must be a non-empty array")

    seen: set[str] = set()
    for index, raw in enumerate(capabilities):
        if not isinstance(raw, Mapping):
            raise ValueError(f"capabilities[{index}] must be an object")
        fields = set(raw)
        if fields != _CAPABILITY_FIELDS:
            raise ValueError(
                f"capabilities[{index}] fields are not closed: "
                f"missing={sorted(_CAPABILITY_FIELDS - fields)} "
                f"extra={sorted(fields - _CAPABILITY_FIELDS)}"
            )
        capability_id = _non_empty_string(raw["capability_id"], f"capabilities[{index}].capability_id")
        if capability_id in seen:
            raise ValueError(f"duplicate capability_id: {capability_id}")
        seen.add(capability_id)
        _non_empty_string(raw["capability"], f"capabilities[{index}].capability")
        _non_empty_string(raw["current_owner"], f"capabilities[{index}].current_owner")
        _string_list(raw["current_paths"], f"capabilities[{index}].current_paths")
        _string_list(raw["current_apis"], f"capabilities[{index}].current_apis")
        _string_list(raw["current_consumers"], f"capabilities[{index}].current_consumers")
        classification = raw["classification"]
        if classification not in CLASSIFICATIONS:
            raise ValueError(f"capabilities[{index}].classification is invalid")
        if raw["adapter"] is not None:
            _non_empty_string(raw["adapter"], f"capabilities[{index}].adapter")
        _string_list(raw["tests"], f"capabilities[{index}].tests", min_items=1)
        _non_empty_string(raw["acceptance_gate"], f"capabilities[{index}].acceptance_gate")
        _non_empty_string(raw["migration"], f"capabilities[{index}].migration")
        _non_empty_string(raw["rollback"], f"capabilities[{index}].rollback")
        inspected = _string_list(raw["inspected_paths"], f"capabilities[{index}].inspected_paths")
        gap_reason = raw["gap_reason"]
        if classification == "NEW_MISSING_CAPABILITY":
            if not inspected or not isinstance(gap_reason, str) or not gap_reason.strip():
                raise ValueError(
                    "NEW_MISSING_CAPABILITY requires inspected_paths and gap_reason"
                )
        elif gap_reason is not None:
            raise ValueError("gap_reason is only valid for NEW_MISSING_CAPABILITY")
    return copy.deepcopy(dict(payload))


def read_inventory(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read reuse inventory: {path}") from exc
    return validate_inventory(payload)


def validate_against_repository(inventory: Mapping[str, object], repo_root: Path) -> None:
    validated = validate_inventory(inventory)
    root = repo_root.resolve()
    for item in validated["capabilities"]:
        for field in ("current_paths", "inspected_paths", "tests"):
            for relative in item[field]:
                if relative.startswith("external:"):
                    continue
                candidate = (root / relative).resolve()
                try:
                    candidate.relative_to(root)
                except ValueError as exc:
                    raise ValueError(f"inventory path escapes repository: {relative}") from exc
                if not candidate.exists():
                    raise ValueError(f"inventory path does not exist: {relative}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reuse_inventory")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.add_argument("inventory", type=Path)
    check.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args(argv)
    inventory = read_inventory(args.inventory)
    validate_against_repository(inventory, args.repo_root)
    print(args.inventory.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run the focused tests**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_inventory_contract.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 7: Run Ruff and diff checks**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check scripts/reuse_inventory.py tests/test_reuse_inventory_contract.py
git diff --check
```

Expected: both exit `0`.

- [ ] **Step 8: Commit the contract slice**

```powershell
git add contracts/reuse-integration/reuse-inventory.schema.json contracts/reuse-integration/examples/reuse-inventory.json scripts/reuse_inventory.py tests/test_reuse_inventory_contract.py
git commit -m "feat: add reuse inventory contract"
```

---

### Task 2: Repository-wide reuse inventory and completeness gate

**Files:**
- Create: `docs/superpowers/reuse/2026-08-04-reuse-inventory.json`
- Create: `tests/test_reuse_inventory_repository.py`
- Modify: `scripts/reuse_inventory.py`

**Interfaces:**
- Consumes: the validator from Task 1 and the repository at the task base SHA.
- Produces: a complete machine-readable inventory and `required_capability_ids()` used by the repository completeness test.

- [ ] **Step 1: Write the failing completeness test**

Create `tests/test_reuse_inventory_repository.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/superpowers/reuse/2026-08-04-reuse-inventory.json"
SCRIPT = ROOT / "scripts/reuse_inventory.py"

REQUIRED = {
    "image-pdf-recognition",
    "semantic-parts-constraints",
    "ambiguity-proposal-apply",
    "native-dxf-generation",
    "headless-review-repair",
    "autocad-file-ipc",
    "autocad-repair",
    "run-manifest-checkpoint-resume",
    "drawing-setup",
    "dimension-pilot",
    "vs-t1-dimension-observer",
    "vs-t2-geometry-comparator",
    "vs-t3-evidence-exporter",
    "source-bundle-fusion",
    "exact-base-component-extraction",
    "component-view-registry",
    "candidate-revision-synchronization",
    "independent-visual-verdict",
    "codex-repair-planning",
    "verified-promotion",
}


def _module():
    spec = importlib.util.spec_from_file_location("reuse_inventory", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_inventory_is_complete_and_path_valid() -> None:
    module = _module()
    inventory = module.read_inventory(INVENTORY)
    module.validate_against_repository(inventory, ROOT)
    ids = {item["capability_id"] for item in inventory["capabilities"]}
    assert ids == REQUIRED


def test_every_new_capability_names_inspected_existing_boundaries() -> None:
    module = _module()
    inventory = module.read_inventory(INVENTORY)
    for item in inventory["capabilities"]:
        if item["classification"] == "NEW_MISSING_CAPABILITY":
            assert item["inspected_paths"]
            assert item["gap_reason"]
            assert all(path != item["current_owner"] for path in item["inspected_paths"])
```

- [ ] **Step 2: Run the focused test and confirm it fails**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_inventory_repository.py -q -p no:cacheprovider
```

Expected: FAIL because the repository inventory does not exist.

- [ ] **Step 3: Inspect every existing boundary before classifying it**

Use the repository base actually checked out for implementation. Record exact files and callable APIs for at least:

```text
cad_agent/cli.py
cad_agent/manifest.py
cad_agent/pdf.py
cad_agent/drawing_setup.py
cad_agent/dimension_pilot.py
cad_agent/visual_contracts.py
cad_agent/dimension_observer.py
cad_agent/geometry_comparator.py
cad_agent/visual_evidence.py
primitive_ir_lib/run_image.py
primitive_ir_lib/run_pdf.py
primitive_ir_lib/text_extraction.py
semantic_ir_lib/assemble.py
semantic_ir_lib/constraint_pruning.py
semantic_ir_lib/constraint_solving.py
agent_lib/run.py
agent_lib/apply.py
dxf_builder_lib/builder.py
dxf_builder_lib/reviewer.py
dxf_builder_lib/repair.py
mcp_integration_lib/dotnet_ipc.py
mcp_integration_lib/mcp_client.py
autocad_plugin/CadAgent.AutoCAD2027/Commands/CadAgentCommands.cs
autocad_plugin/CadAgent.AutoCAD2027/Review/AutoCadDrawingGateway.cs
contracts/autocad-ipc/
```

When an expected path has moved, use the actual current path and record it; do not create a compatibility alias merely to satisfy the plan.

- [ ] **Step 4: Populate all 20 capability entries**

Create `docs/superpowers/reuse/2026-08-04-reuse-inventory.json` with the exact classifications below unless inspection proves a stricter compatible classification is necessary:

```text
image-pdf-recognition                  REUSE_AS_IS
semantic-parts-constraints             EXTEND_WITH_ADAPTER
ambiguity-proposal-apply               EXTEND_WITH_ADAPTER
native-dxf-generation                  REUSE_AS_IS
headless-review-repair                 REUSE_AS_IS
autocad-file-ipc                       EXTEND_WITH_TEST
autocad-repair                         EXTEND_WITH_ADAPTER
run-manifest-checkpoint-resume          EXTEND_WITH_ADAPTER
drawing-setup                          REUSE_AS_IS
dimension-pilot                        REUSE_AS_IS
vs-t1-dimension-observer               REUSE_AS_IS
vs-t2-geometry-comparator              REUSE_AS_IS
vs-t3-evidence-exporter                REUSE_AS_IS
source-bundle-fusion                   NEW_MISSING_CAPABILITY
exact-base-component-extraction        NEW_MISSING_CAPABILITY
component-view-registry                NEW_MISSING_CAPABILITY
candidate-revision-synchronization     NEW_MISSING_CAPABILITY
independent-visual-verdict              NEW_MISSING_CAPABILITY
codex-repair-planning                  NEW_MISSING_CAPABILITY
verified-promotion                     EXTEND_WITH_ADAPTER
```

Each `NEW_MISSING_CAPABILITY` entry must name the existing boundaries inspected and explain the precise missing orchestration responsibility. It must not claim that OCR, solving, DXF writing, AutoCAD transport, or repair execution is missing.

Use `external:` prefixes only for evidence that is intentionally outside Git, for example `external:AutoCAD Mechanical 2027 live session`.

- [ ] **Step 5: Add a stable required-capability helper**

Add to `scripts/reuse_inventory.py`:

```python
REQUIRED_CAPABILITY_IDS = frozenset({
    "image-pdf-recognition",
    "semantic-parts-constraints",
    "ambiguity-proposal-apply",
    "native-dxf-generation",
    "headless-review-repair",
    "autocad-file-ipc",
    "autocad-repair",
    "run-manifest-checkpoint-resume",
    "drawing-setup",
    "dimension-pilot",
    "vs-t1-dimension-observer",
    "vs-t2-geometry-comparator",
    "vs-t3-evidence-exporter",
    "source-bundle-fusion",
    "exact-base-component-extraction",
    "component-view-registry",
    "candidate-revision-synchronization",
    "independent-visual-verdict",
    "codex-repair-planning",
    "verified-promotion",
})


def validate_completeness(inventory: Mapping[str, object]) -> None:
    validated = validate_inventory(inventory)
    actual = {item["capability_id"] for item in validated["capabilities"]}
    if actual != REQUIRED_CAPABILITY_IDS:
        raise ValueError(
            f"reuse inventory capability set mismatch: "
            f"missing={sorted(REQUIRED_CAPABILITY_IDS - actual)} "
            f"extra={sorted(actual - REQUIRED_CAPABILITY_IDS)}"
        )
```

Call `validate_completeness()` from the CLI `check` command after schema validation.

- [ ] **Step 6: Run the contract and repository tests**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_inventory_contract.py tests/test_reuse_inventory_repository.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe scripts/reuse_inventory.py check docs/superpowers/reuse/2026-08-04-reuse-inventory.json --repo-root .
```

Expected: PASS and the resolved inventory path is printed.

- [ ] **Step 7: Run Ruff and diff checks**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check scripts/reuse_inventory.py tests/test_reuse_inventory_contract.py tests/test_reuse_inventory_repository.py
git diff --check
```

Expected: both exit `0`.

- [ ] **Step 8: Commit the repository inventory**

```powershell
git add docs/superpowers/reuse/2026-08-04-reuse-inventory.json scripts/reuse_inventory.py tests/test_reuse_inventory_repository.py
git commit -m "docs: record repository reuse inventory"
```

---

### Task 3: Mandatory Reuse Declaration for implementation PRs

**Files:**
- Create: `.github/pull_request_template.md`
- Create: `.github/workflows/reuse-declaration.yml`
- Create: `scripts/check_reuse_declaration.py`
- Test: `tests/test_reuse_declaration.py`

**Interfaces:**
- Consumes: pull-request body text plus newline-delimited changed paths.
- Produces: `implementation_change(paths) -> bool`, `missing_sections(body) -> tuple[str, ...]`, CLI exit `0` for compliant or docs-only changes and exit `2` for a missing declaration.

- [ ] **Step 1: Write the failing declaration tests**

Create `tests/test_reuse_declaration.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_reuse_declaration.py"
REQUIRED = (
    "Existing capability inspected:",
    "Existing API reused:",
    "Adapter required:",
    "New capability genuinely missing:",
    "Files allowed to change:",
    "Files forbidden to duplicate:",
    "Compatibility behavior:",
    "Migration and rollback path:",
)


def _module():
    spec = importlib.util.spec_from_file_location("check_reuse_declaration", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_docs_only_change_is_exempt() -> None:
    module = _module()
    assert module.implementation_change(["docs/STATUS.md"]) is False


def test_runtime_contract_or_script_change_requires_declaration() -> None:
    module = _module()
    assert module.implementation_change(["cad_agent/cli.py"]) is True
    assert module.implementation_change(["contracts/autocad-ipc/request.schema.json"]) is True
    assert module.implementation_change(["scripts/verify.ps1"]) is True


def test_complete_declaration_passes() -> None:
    module = _module()
    body = "\n".join(f"{section} value" for section in REQUIRED)
    assert module.missing_sections(body) == ()


def test_heading_without_value_is_missing() -> None:
    module = _module()
    body = "\n".join(REQUIRED)
    assert module.missing_sections(body) == REQUIRED
```

- [ ] **Step 2: Run the focused test and confirm it fails**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_declaration.py -q -p no:cacheprovider
```

Expected: FAIL because the checker does not exist.

- [ ] **Step 3: Implement the checker**

Create `scripts/check_reuse_declaration.py` with exact required sections and docs-only exemption:

```python
from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_SECTIONS = (
    "Existing capability inspected:",
    "Existing API reused:",
    "Adapter required:",
    "New capability genuinely missing:",
    "Files allowed to change:",
    "Files forbidden to duplicate:",
    "Compatibility behavior:",
    "Migration and rollback path:",
)
IMPLEMENTATION_PREFIXES = (
    "cad_agent/",
    "primitive_ir_lib/",
    "semantic_ir_lib/",
    "agent_lib/",
    "dxf_builder_lib/",
    "mcp_integration_lib/",
    "autocad_plugin/",
    "contracts/",
    "scripts/",
    ".github/workflows/",
)
IMPLEMENTATION_ROOT_FILES = {
    "pyproject.toml",
    "requirements/windows-py311.lock",
}


def implementation_change(paths: list[str]) -> bool:
    return any(
        path in IMPLEMENTATION_ROOT_FILES
        or path.startswith(IMPLEMENTATION_PREFIXES)
        for path in paths
    )


def missing_sections(body: str) -> tuple[str, ...]:
    lines = body.splitlines()
    missing: list[str] = []
    for section in REQUIRED_SECTIONS:
        values = [
            line[len(section):].strip()
            for line in lines
            if line.strip().startswith(section)
        ]
        if not values or not any(value for value in values):
            missing.append(section)
    return tuple(missing)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_reuse_declaration")
    parser.add_argument("--body-file", type=Path, required=True)
    parser.add_argument("--changed-files", type=Path, required=True)
    args = parser.parse_args(argv)
    body = args.body_file.read_text(encoding="utf-8")
    paths = [
        line.strip().replace("\\", "/")
        for line in args.changed_files.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not implementation_change(paths):
        print("Reuse Declaration: docs/non-implementation exemption")
        return 0
    missing = missing_sections(body)
    if missing:
        print("Reuse Declaration missing or empty sections:")
        for section in missing:
            print(f"- {section}")
        return 2
    print("Reuse Declaration: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add the PR template**

Create `.github/pull_request_template.md` containing the eight exact fields followed by ordinary summary and verification sections. The template must say that docs-only PRs may write `Not applicable: documentation only`, which is a non-empty value and remains auditable.

- [ ] **Step 5: Add the pull-request workflow**

Create `.github/workflows/reuse-declaration.yml`:

```yaml
name: reuse-declaration

on:
  pull_request:
    types: [opened, edited, synchronize, reopened]

permissions:
  contents: read

jobs:
  check:
    runs-on: windows-2025
    steps:
      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803
        with:
          fetch-depth: 0
          persist-credentials: false
      - name: Write PR body and changed-file list
        shell: pwsh
        env:
          PR_BODY: ${{ github.event.pull_request.body }}
        run: |
          [IO.File]::WriteAllText("$env:RUNNER_TEMP\pr-body.txt", $env:PR_BODY ?? "", [Text.UTF8Encoding]::new($false))
          git diff --name-only "origin/${{ github.base_ref }}...HEAD" | Out-File -Encoding utf8NoBOM "$env:RUNNER_TEMP\changed-files.txt"
      - name: Check Reuse Declaration
        shell: pwsh
        run: |
          python scripts/check_reuse_declaration.py `
            --body-file "$env:RUNNER_TEMP\pr-body.txt" `
            --changed-files "$env:RUNNER_TEMP\changed-files.txt"
```

Do not grant write permissions and do not use secrets.

- [ ] **Step 6: Run focused tests and local CLI probes**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_declaration.py -q -p no:cacheprovider
@"
Existing capability inspected: cad_agent.cli
Existing API reused: build_parser
Adapter required: none
New capability genuinely missing: governance checker only
Files allowed to change: scripts/check_reuse_declaration.py
Files forbidden to duplicate: OCR, DXF, AutoCAD transport
Compatibility behavior: docs-only exempt; runtime PRs checked
Migration and rollback path: remove workflow and checker commit
"@ | Set-Content -Encoding utf8 .artifacts\reuse-body.txt
"cad_agent/cli.py" | Set-Content -Encoding utf8 .artifacts\reuse-paths.txt
.\.venv-py311\Scripts\python.exe scripts/check_reuse_declaration.py --body-file .artifacts\reuse-body.txt --changed-files .artifacts\reuse-paths.txt
```

Expected: tests PASS and CLI prints `Reuse Declaration: PASS`.

- [ ] **Step 7: Run Ruff and diff checks**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check scripts/check_reuse_declaration.py tests/test_reuse_declaration.py
git diff --check
```

- [ ] **Step 8: Commit governance enforcement**

```powershell
git add .github/pull_request_template.md .github/workflows/reuse-declaration.yml scripts/check_reuse_declaration.py tests/test_reuse_declaration.py
git commit -m "ci: require reuse declarations"
```

---

### Task 4: Legacy CLI and artifact compatibility baseline

**Files:**
- Create: `contracts/reuse-integration/legacy-cli-baseline.json`
- Create: `scripts/export_cli_contract.py`
- Create: `tests/fixtures/reuse-rebaseline/legacy-run-manifest-v1.json`
- Test: `tests/test_reuse_legacy_compatibility.py`

**Interfaces:**
- Consumes: `cad_agent.cli.build_parser()` and `cad_agent.manifest.read_manifest()`.
- Produces: deterministic `parser_contract(parser) -> dict[str, object]`, a committed CLI baseline, and a legacy v1 manifest readability fixture.

- [ ] **Step 1: Write the failing compatibility tests**

Create `tests/test_reuse_legacy_compatibility.py`:

```python
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from cad_agent.cli import build_parser
from cad_agent.manifest import read_manifest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/export_cli_contract.py"
BASELINE = ROOT / "contracts/reuse-integration/legacy-cli-baseline.json"
LEGACY_MANIFEST = ROOT / "tests/fixtures/reuse-rebaseline/legacy-run-manifest-v1.json"


def _module():
    spec = importlib.util.spec_from_file_location("export_cli_contract", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_parser_preserves_the_committed_cli_contract() -> None:
    module = _module()
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert module.parser_contract(build_parser()) == expected


def test_legacy_run_manifest_remains_readable_with_safe_defaults() -> None:
    manifest = read_manifest(LEGACY_MANIFEST)
    assert manifest["schema_version"] == "1.0"
    assert manifest["release_profile"] == "DRAFT_REFERENCE"
    assert manifest["authoritative_release_eligible"] is False
    assert manifest["drawing_setup_evidence"] is None
```

- [ ] **Step 2: Run the focused test and confirm it fails**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_legacy_compatibility.py -q -p no:cacheprovider
```

Expected: FAIL because baseline/exporter/fixture files do not exist.

- [ ] **Step 3: Implement deterministic parser export**

Create `scripts/export_cli_contract.py` using `argparse._SubParsersAction` only for read-only introspection:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cad_agent.cli import build_parser


def parser_contract(parser: argparse.ArgumentParser) -> dict[str, object]:
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    commands: dict[str, Any] = {}
    for name, command_parser in sorted(subparsers.choices.items()):
        options: dict[str, object] = {}
        for action in command_parser._actions:
            if action.dest == "help":
                continue
            option_names = sorted(action.option_strings)
            key = option_names[0] if option_names else action.dest
            options[key] = {
                "dest": action.dest,
                "required": bool(getattr(action, "required", False)),
                "nargs": action.nargs,
            }
        commands[name] = {"options": options}
    return {"schema_version": "legacy-cli-baseline-1.0", "commands": commands}


def main() -> int:
    print(json.dumps(parser_contract(build_parser()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Generate and commit the exact current CLI baseline**

Run from a clean implementation base:

```powershell
.\.venv-py311\Scripts\python.exe scripts/export_cli_contract.py | Set-Content -Encoding utf8 contracts/reuse-integration/legacy-cli-baseline.json
```

Open the result and confirm it includes at least:

```text
doctor
run
resume
run-pdf
resume-pdf
drawing-setup-plan
drawing-setup-audit
drawing-setup-verify
dimension-pilot-run
mechanical-review
mechanical-repair
```

Do not hand-edit away existing fidelity commands; the baseline protects all commands present at the implementation base.

- [ ] **Step 5: Add the historical v1 manifest fixture**

Create `tests/fixtures/reuse-rebaseline/legacy-run-manifest-v1.json` without the three newer release fields. It must contain:

```json
{
  "schema_version": "1.0",
  "source": {
    "name": "legacy.png",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "kind": "image"
  },
  "configuration": {"scale_mm_per_px": 1.0},
  "approvals": {
    "calibration": {"approved": true, "reference": "LEGACY-APPROVAL"}
  },
  "stages": {
    "primitive_ir": {"state": "pending", "artifact": null, "sha256": null, "details": null},
    "semantic_ir": {"state": "pending", "artifact": null, "sha256": null, "details": null},
    "dxf": {"state": "pending", "artifact": null, "sha256": null, "details": null}
  }
}
```

- [ ] **Step 6: Run focused compatibility tests**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_legacy_compatibility.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 7: Run Ruff and diff checks**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check scripts/export_cli_contract.py tests/test_reuse_legacy_compatibility.py
git diff --check
```

- [ ] **Step 8: Commit the compatibility baseline**

```powershell
git add contracts/reuse-integration/legacy-cli-baseline.json scripts/export_cli_contract.py tests/fixtures/reuse-rebaseline/legacy-run-manifest-v1.json tests/test_reuse_legacy_compatibility.py
git commit -m "test: lock legacy compatibility baseline"
```

---

### Task 5: Architecture boundary ratchet

**Files:**
- Create: `contracts/reuse-integration/architecture-boundaries.json`
- Create: `scripts/check_architecture_boundaries.py`
- Test: `tests/test_reuse_architecture_boundaries.py`

**Interfaces:**
- Consumes: repository files plus a committed baseline of existing exceptions.
- Produces: `collect_violations(repo_root) -> tuple[str, ...]`, `read_baseline(path)`, and CLI command `check` that fails on any new violation not present at the implementation base.

- [ ] **Step 1: Write the failing architecture-ratchet tests**

Create `tests/test_reuse_architecture_boundaries.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_architecture_boundaries.py"
BASELINE = ROOT / "contracts/reuse-integration/architecture-boundaries.json"


def _module():
    spec = importlib.util.spec_from_file_location("check_architecture_boundaries", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_has_no_unbaselined_architecture_violation() -> None:
    module = _module()
    baseline = module.read_baseline(BASELINE)
    current = set(module.collect_violations(ROOT))
    assert current == set(baseline["accepted_existing_violations"])


def test_reserved_duplicate_package_names_fail() -> None:
    module = _module()
    assert module.reserved_duplicate_name("new_ocr_engine") is True
    assert module.reserved_duplicate_name("parallel_dxf_builder") is True
    assert module.reserved_duplicate_name("second_manifest_store") is True
    assert module.reserved_duplicate_name("source_fusion_adapter") is False
```

- [ ] **Step 2: Run the focused test and confirm it fails**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_architecture_boundaries.py -q -p no:cacheprovider
```

Expected: FAIL because the checker and baseline do not exist.

- [ ] **Step 3: Implement deterministic repository scanning**

Create `scripts/check_architecture_boundaries.py` with these rule groups:

```text
DUPLICATE_PACKAGE_NAME
AUTOCAD_API_OUTSIDE_PLUGIN
AUTOCAD_TRANSPORT_OUTSIDE_APPROVED_BOUNDARY
DIRECT_DXF_WRITE_OUTSIDE_DXF_BUILDER
DIRECT_OCR_IMPORT_OUTSIDE_PRIMITIVE_OWNER
SECOND_TRUTH_STORE_NAME
```

The scanner must:

1. inspect tracked `.py` and `.cs` files only;
2. normalize paths with `/` separators;
3. use Python `ast` for Python imports;
4. use literal namespace detection for C# `Autodesk.AutoCAD` references;
5. allow `Autodesk.AutoCAD` only below `autocad_plugin/`;
6. allow AutoCAD transport code only below `mcp_integration_lib/`, `autocad_plugin/`, and `contracts/autocad-ipc/`;
7. flag new top-level package or module names containing reserved duplicate combinations;
8. return sorted stable strings in the form `RULE:path:detail`;
9. never modify files.

Use these exact reserved token combinations:

```python
RESERVED_COMBINATIONS = (
    ("ocr", "engine"),
    ("dimension", "recognizer"),
    ("semantic", "solver"),
    ("dxf", "builder"),
    ("autocad", "transport"),
    ("repair", "executor"),
    ("manifest", "store"),
    ("checkpoint", "store"),
    ("revision", "store"),
    ("verified", "publisher"),
)
```

Do not flag the approved existing owners themselves:

```text
primitive_ir_lib
semantic_ir_lib
dxf_builder_lib
mcp_integration_lib
cad_agent
agent_lib
autocad_plugin
```

For imports, treat `cv2` and `pytesseract` as recognition-owner signals and `ezdxf` as DXF-owner signal. Existing exceptions found at the implementation base are recorded, not silently deleted or refactored in this task.

- [ ] **Step 4: Generate the current exception baseline**

The checker must support:

```powershell
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py snapshot --repo-root . --output contracts/reuse-integration/architecture-boundaries.json
```

The output contract is closed and contains:

```json
{
  "schema_version": "architecture-boundaries-1.0",
  "base_sha": "<exact implementation base SHA>",
  "accepted_existing_violations": [
    "RULE:path:detail"
  ]
}
```

Review every accepted existing violation manually. The file is a ratchet: later work may remove entries, but may not add entries without an approved architecture amendment.

- [ ] **Step 5: Implement the check command**

The command:

```powershell
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
```

must exit `0` only when the current violation set is a subset of the committed baseline. It must print removed baseline exceptions as informational output and new violations as blockers.

- [ ] **Step 6: Run focused tests and checker**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_architecture_boundaries.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
```

Expected: PASS.

- [ ] **Step 7: Run Ruff and diff checks**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check scripts/check_architecture_boundaries.py tests/test_reuse_architecture_boundaries.py
git diff --check
```

- [ ] **Step 8: Commit the architecture ratchet**

```powershell
git add contracts/reuse-integration/architecture-boundaries.json scripts/check_architecture_boundaries.py tests/test_reuse_architecture_boundaries.py
git commit -m "test: add reuse architecture ratchet"
```

---

### Task 6: Rebaseline audit report and roadmap supersession

**Files:**
- Create: `docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md`
- Test: `tests/test_reuse_rebaseline_docs.py`

**Interfaces:**
- Consumes: the validated inventory, CLI baseline, architecture baseline, and approved design.
- Produces: the canonical audit report and a dependency-ordered queue of future subsystem plans; it does not authorize runtime implementation by itself.

- [ ] **Step 1: Write the failing documentation-gate test**

Create `tests/test_reuse_rebaseline_docs.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md"
ARCHITECTURE = ROOT / "docs/ARCHITECTURE.md"
STATUS = ROOT / "docs/STATUS.md"
OLD_ROLLOUT = ROOT / "docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md"


def test_rebaseline_audit_records_required_future_plan_queue() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    for marker in (
        "R0 Reuse Integration Rebaseline",
        "S1 Codex SDK Windows compatibility spike",
        "S2 AutoCAD-native render/plot evidence spike",
        "S3 Exact-base Xref extraction spike",
        "R1 Source Bundle and Fusion Adapter",
        "R2 Base CAD Adapter",
        "R3 Component/View Registry",
        "R4 Candidate Revision Orchestrator",
        "R5 Visual Supervisor Adapter",
        "R6 Repair Executor Adapter",
        "R7 Verified Publisher",
        "R8 Synthetic and real pilots",
    ):
        assert marker in text


def test_old_rollout_is_explicitly_superseded_after_vs_t3() -> None:
    text = OLD_ROLLOUT.read_text(encoding="utf-8")
    assert "Superseded after VS-T3" in text
    assert "Do not execute VS-T4 through VS-T8 unchanged" in text


def test_architecture_and_status_reference_the_reuse_inventory() -> None:
    inventory_path = "docs/superpowers/reuse/2026-08-04-reuse-inventory.json"
    assert inventory_path in ARCHITECTURE.read_text(encoding="utf-8")
    assert inventory_path in STATUS.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the focused test and confirm it fails**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_rebaseline_docs.py -q -p no:cacheprovider
```

Expected: FAIL because the audit report and supersession markers do not exist.

- [ ] **Step 3: Write the audit report from machine-readable evidence**

Create `docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md` with these sections:

```text
1. Audit identity and exact base SHA
2. Inventory validation command and result
3. Existing capability ownership map
4. Reuse classifications and reasons
5. Genuine missing capabilities
6. Compatibility baseline
7. Architecture-ratchet baseline
8. Risks and rollback
9. Locked future plan queue
10. Gates not run
```

The future queue must be exactly dependency ordered:

```text
R0 Reuse Integration Rebaseline
  -> S1 Codex SDK Windows compatibility spike
  -> S2 AutoCAD-native render/plot evidence spike
  -> S3 Exact-base Xref extraction spike
  -> R1 Source Bundle and Fusion Adapter
  -> R2 Base CAD Adapter
  -> R3 Component/View Registry
  -> R4 Candidate Revision Orchestrator
  -> R5 Visual Supervisor Adapter
  -> R6 Repair Executor Adapter
  -> R7 Verified Publisher
  -> R8 Synthetic and real pilots
```

Record that the three spikes may be planned and executed independently only when their write sets are disjoint. R1-R8 each require a fresh plan against the then-current integrated `main` and a Reuse Declaration.

- [ ] **Step 4: Update architecture documentation without rewriting history**

Append a `Reuse-first multisource reconstruction rebaseline` section to `docs/ARCHITECTURE.md`. It must:

- link the approved design, inventory, audit, and this plan;
- restate that existing packages remain the engine;
- state that new adapters are orchestration-level only;
- state that deterministic VS-T3 projection is structural/offline evidence and not automatically final visual truth;
- state that AutoCAD-native render/plot remains behind the existing File IPC boundary;
- state that future plan names R1-R8 do not authorize implementation until separately approved.

Do not remove the historical Visual Supervisor or M2 sections.

- [ ] **Step 5: Update status truthfully**

Add a top-level `Reuse Integration Rebaseline` section to `docs/STATUS.md` recording:

```text
State: Planned or Executing until this plan's final verifier passes.
Design merge: 4cc2c0f198484581f5781466e769441d4e7da669.
Runtime changes: none in the design merge.
VS-T4/VS-T5 old rollout: locked.
Private-data gate: NOT RUN.
AutoCAD Mechanical live gate: NOT RUN.
Codex SDK spike: NOT RUN.
```

At final completion of this plan, update only the state and exact implementation evidence; do not promote any runtime capability.

- [ ] **Step 6: Supersede the old rollout after VS-T3**

At the top of `docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md`, add:

```markdown
**Status:** Superseded after VS-T3 by the reuse-first multisource reconstruction rebaseline.

VS-T0 through VS-T3 remain historical accepted slices. Do not execute VS-T4 through VS-T8 unchanged. Their useful requirements must be reissued through the reuse inventory, compatibility spikes, and R1-R8 plans, each with a Reuse Declaration.
```

Do not delete or rewrite the historical task definitions and acceptance evidence.

- [ ] **Step 7: Run documentation and inventory gates**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_reuse_rebaseline_docs.py tests/test_reuse_inventory_contract.py tests/test_reuse_inventory_repository.py tests/test_reuse_legacy_compatibility.py tests/test_reuse_architecture_boundaries.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe scripts/reuse_inventory.py check docs/superpowers/reuse/2026-08-04-reuse-inventory.json --repo-root .
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 8: Commit the canonical rebaseline report**

```powershell
git add docs/superpowers/reuse/2026-08-04-reuse-integration-audit.md docs/ARCHITECTURE.md docs/STATUS.md docs/superpowers/plans/2026-08-04-visual-supervisor-rollout.md tests/test_reuse_rebaseline_docs.py
git commit -m "docs: complete reuse integration audit"
```

---

### Task 7: Aggregate verification and implementation record

**Files:**
- Create: `docs/superpowers/implementation-records/2026-08-04-reuse-integration-rebaseline.md`
- Modify: `docs/STATUS.md`

**Interfaces:**
- Consumes: all Task 1-6 artifacts on one clean final head.
- Produces: exact SHA-bound verification evidence and the gate that permits planning S1/S2/S3 and R1, but not automatic runtime implementation.

- [ ] **Step 1: Run all focused rebaseline tests**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_reuse_inventory_contract.py `
  tests/test_reuse_inventory_repository.py `
  tests/test_reuse_declaration.py `
  tests/test_reuse_legacy_compatibility.py `
  tests/test_reuse_architecture_boundaries.py `
  tests/test_reuse_rebaseline_docs.py `
  -q -p no:cacheprovider
```

Expected: all collected tests pass with zero skips.

- [ ] **Step 2: Run governance CLIs directly**

```powershell
.\.venv-py311\Scripts\python.exe scripts/reuse_inventory.py check docs/superpowers/reuse/2026-08-04-reuse-inventory.json --repo-root .
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
```

Expected: both exit `0`.

- [ ] **Step 3: Run Ruff on every new Python file**

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check `
  scripts/reuse_inventory.py `
  scripts/export_cli_contract.py `
  scripts/check_reuse_declaration.py `
  scripts/check_architecture_boundaries.py `
  tests/test_reuse_inventory_contract.py `
  tests/test_reuse_inventory_repository.py `
  tests/test_reuse_declaration.py `
  tests/test_reuse_legacy_compatibility.py `
  tests/test_reuse_architecture_boundaries.py `
  tests/test_reuse_rebaseline_docs.py
```

Expected: exit `0`.

- [ ] **Step 4: Commit all remaining documentation before the canonical verifier**

The verifier requires a clean tree. Add a provisional implementation record containing the exact commands above and gate states `NOT RUN`; commit it before running the canonical verifier.

```powershell
git add docs/superpowers/implementation-records/2026-08-04-reuse-integration-rebaseline.md docs/STATUS.md
git commit -m "docs: record reuse rebaseline verification plan"
```

- [ ] **Step 5: Run the authoritative verifier on the exact committed head**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -PythonExe .\.venv-py311\Scripts\python.exe
```

Expected:

- exit `0`;
- clean-tree provenance printed with the exact final candidate SHA;
- .NET restore/build/test PASS unless the approved environment explicitly uses `-SkipAutoCADDotNet` and records it as `NOT RUN`;
- offline JUnit has zero failures, errors, or skips;
- private-data unavailable-state probes are all skipped and are not called PASS;
- AutoCAD Mechanical live remains `NOT RUN` unless an approved disposable session was actually configured.

- [ ] **Step 6: Update the implementation record with exact evidence**

Record only observed values:

```text
final head SHA
focused test count
inventory checker result
architecture checker result
Ruff result
canonical verifier command and exit code
.NET gate state and counts
Python offline JUnit counts
private-data state
AutoCAD Mechanical live state
changed-file list
```

Because updating the record creates a new commit, rerun at minimum the focused rebaseline suite, Ruff, governance CLIs, and `git diff --check` on the documentation-only final record commit. Do not claim the earlier full verifier ran on the later documentation commit; identify the verified code head and the record-only head separately.

- [ ] **Step 7: Final record-only verification**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_reuse_inventory_contract.py `
  tests/test_reuse_inventory_repository.py `
  tests/test_reuse_declaration.py `
  tests/test_reuse_legacy_compatibility.py `
  tests/test_reuse_architecture_boundaries.py `
  tests/test_reuse_rebaseline_docs.py `
  -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check scripts/reuse_inventory.py scripts/export_cli_contract.py scripts/check_reuse_declaration.py scripts/check_architecture_boundaries.py tests/test_reuse_inventory_contract.py tests/test_reuse_inventory_repository.py tests/test_reuse_declaration.py tests/test_reuse_legacy_compatibility.py tests/test_reuse_architecture_boundaries.py tests/test_reuse_rebaseline_docs.py
.\.venv-py311\Scripts\python.exe scripts/reuse_inventory.py check docs/superpowers/reuse/2026-08-04-reuse-inventory.json --repo-root .
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 8: Commit the final evidence record**

```powershell
git add docs/superpowers/implementation-records/2026-08-04-reuse-integration-rebaseline.md docs/STATUS.md
git commit -m "docs: finalize reuse rebaseline evidence"
```

- [ ] **Step 9: Self-review against the approved design**

Confirm all of the following before opening a PR:

```text
The inventory contains all 20 required capability IDs.
Every NEW_MISSING_CAPABILITY names inspected existing paths and a precise gap.
No runtime workflow, dependency, OCR, solver, DXF, AutoCAD, repair, revision, verdict, or publisher implementation was added.
Legacy CLI baseline includes all commands present at the implementation base.
Legacy v1 run manifest remains readable with DRAFT_REFERENCE defaults.
The architecture checker is a ratchet and does not silently bless new violations.
Docs-only PRs are exempt from Reuse Declaration enforcement; implementation PRs are not.
The old rollout is preserved as history but VS-T4 through VS-T8 are explicitly locked.
M2 Drawing Initialization remains authoritative.
Private-data, AutoCAD live, and Codex SDK gates are stated truthfully.
```

- [ ] **Step 10: Open the implementation PR**

Use a PR body that includes the complete Reuse Declaration. The PR title is:

```text
R0: establish Reuse Integration Rebaseline gates
```

The PR must contain only the files named by this plan. It must not include S1/S2/S3 or R1 runtime work.

---

## Acceptance criteria

R0 is accepted only when:

- the design merge is present on the implementation base;
- the repository inventory is closed, complete, path-valid, and SHA-bound;
- every genuinely missing capability documents what was inspected and why existing APIs are insufficient;
- implementation PRs are required to carry a Reuse Declaration;
- the full current CLI surface is snapshotted and protected;
- historical v1 run manifests remain readable with safe defaults;
- the architecture ratchet reports no unbaselined violation;
- the old Visual Supervisor rollout is explicitly superseded after VS-T3 without deleting history;
- architecture and status docs point to the inventory and audit;
- the canonical verifier passes on a named code head, with later record-only changes distinguished honestly;
- no runtime subsystem from S1/S2/S3 or R1-R8 is implemented in R0.

## Plans authorized after R0 acceptance

R0 acceptance permits writing fresh implementation plans for:

1. `S1 Codex SDK Windows compatibility spike`;
2. `S2 AutoCAD-native render/plot evidence spike`;
3. `S3 Exact-base Xref extraction spike`;
4. `R1 Source Bundle and Fusion Adapter` after the relevant spike findings are integrated.

It does not automatically authorize their implementation. Each receives a fresh base SHA, separate plan, Reuse Declaration, tests, review, and acceptance gate.

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-04-reuse-integration-rebaseline.md`.

Recommended execution is **Subagent-Driven**: one fresh coding worker per task with PO review between tasks. Inline execution is acceptable only when the worker follows `superpowers:executing-plans`, keeps commits bounded, and stops at every review checkpoint.
