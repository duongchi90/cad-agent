# M2 Drawing Initialization Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Executing

**Approval date:** 2026-08-02

**Base SHA:** `ca8a768c8e7897c1418d44c810cd295b9139e5bf`

**Completion Head SHA:** Not recorded until the final implementation/evidence commit exists.

**Verification command:** `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1`

**Verification result:** Not recorded until execution completes.

**Required gates:** `real_data` is not required for contract-only tasks and is `NOT RUN`; the final task requires an `autocad_mechanical` live run against disposable drawings and records `PASS`, `SKIP`, or `NOT RUN` exactly.

**Current execution record (2026-08-03):** Tasks 1–9 and T10 Step 1 are
implemented on the continuation branch. Authoritative offline/.NET evidence
passes on the current candidate, while T10 operator-controlled live inputs,
candidate-DWG/profile approval, and T11 independent review/closure remain
pending. The live prerequisite guard now requires an existing disposable
drawing and records missing input as an unavailable-state skip.

**Goal:** Add a hash-bound Drawing Definition/Profile/Domain Pack/Template workflow and a read-only AutoCAD setup audit so every future authoritative drawing path, across configurable automotive-conversion jobs, must present `SETUP_VERIFIED` evidence before geometry can be created.

**Architecture:** Python owns contract validation, profile/template provenance, setup-plan creation, comparison, blocker reporting, and evidence. The existing .NET plugin gains one deterministic read-only `drawing_setup_audit` operation through the current JSON/File IPC channel. DWT binaries and raw customer/candidate-DWG audits remain outside Git; Git stores schemas, code, synthetic examples, and only engineer-approved non-sensitive profile metadata.

**Tech Stack:** Windows, Python 3.11, pytest, JSON, AutoCAD Mechanical 2027, .NET 10 (`net10.0-windows`, x64), AutoCAD Managed API, existing `DotNetIPCClient`, existing `scripts/verify.ps1`.

## Global Constraints

- Preserve current package boundaries and verified `main` behavior.
- Inspect and reuse existing contracts, helpers, tests, IPC behavior, and verified package boundaries before adding code. If an execution-base file already provides part of a planned `Create` item, extend it compatibly instead of replacing it.
- Do not encode a fixed source/target vehicle conversion, body type, crane, flatbed, or other specific equipment in Drawing Setup contracts. Such details belong in approved job/profile/domain/component data.
- Keep the legacy `run`/`run-pdf` paths operational but explicitly classify their outputs as `DRAFT_REFERENCE` and ineligible for authoritative release.
- Do not add a geometry-generation or production-write operation in this milestone.
- `drawing_setup_audit` is read-only, reports `changed=false`, and must prove `DBMOD` is unchanged across the audit.
- Do not add COM/ActiveX, native ObjectARX C++, Mechanical SDK, web services, database services, or automatic NETLOAD.
- Do not commit DWT/DWG binaries, private audit output, customer data, absolute workstation paths, Autodesk DLLs, API keys, or generated DXF files.
- The DWT is identified by a local file SHA-256 plus an approved template manifest. The drawing is linked to the profile by a stamped settings-contract digest or an explicit engineer approval; no code infers template origin from appearance alone.
- Model requirements are `INSUNITS=4` (millimetres), Model Space `1:1`, and approved Layout/viewport scales from the profile.
- Layer, style, viewport, plot, font, and custom-property checks use exact profile values; missing values produce blockers rather than defaults.
- `SECURELOAD=0` is forbidden. Live instructions require a configured `TRUSTEDPATHS` location.
- Every code task starts with a failing test and ends with focused verification plus a scoped commit.

---

## File Structure

### New Python and contract files

- `contracts/drawing-setup/drawing-definition.schema.json`: classification and release intent.
- `contracts/drawing-setup/drawing-profile.schema.json`: expected variables, layers, styles, layouts, viewport rules, and font policy.
- `contracts/drawing-setup/domain-pack.schema.json`: domain vocabulary and supported drawing types without geometry.
- `contracts/drawing-setup/template-manifest.schema.json`: DWT identity, binary SHA-256, settings digest, and approval.
- `contracts/drawing-setup/drawing-setup-plan.schema.json`: immutable inputs and `SETUP_PENDING` plan.
- `contracts/drawing-setup/drawing-setup-audit.schema.json`: normalized read-only AutoCAD facts.
- `contracts/drawing-setup/drawing-setup-evidence.schema.json`: `SETUP_VERIFIED` or `NEEDS_REVIEW` result.
- `contracts/drawing-setup/examples/*.json`: synthetic, non-customer examples used by tests.
- `cad_agent/drawing_contracts.py`: strict pure-Python contract validation and canonical JSON hashing.
- `cad_agent/drawing_setup.py`: plan construction, audit comparison, evidence, and enforcement API.
- `tests/drawing_setup_fixtures.py`: complete synthetic approved contracts and mutation helpers shared by M2 tests.
- `tests/test_drawing_setup_contracts.py`: schema/example and validator tests.
- `tests/test_cad_agent_drawing_setup.py`: plan, state, hash, CLI, and blocker tests.

### New .NET files

- `autocad_plugin/CadAgent.AutoCAD2027/DrawingSetup/DrawingSetupModels.cs`: normalized immutable snapshot records.
- `autocad_plugin/CadAgent.AutoCAD2027/DrawingSetup/DrawingSetupPayload.cs`: deterministic JSON payload mapping.
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/DrawingSetup/DrawingSetupFixtures.cs`: complete synthetic C# snapshots.
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/DrawingSetup/DrawingSetupPayloadTests.cs`: pure ordering and payload tests.

### Modified files

- `cad_agent/cli.py`: add `drawing-setup-plan`, `drawing-setup-audit`, and `drawing-setup-verify` command glue.
- `cad_agent/manifest.py`: mark new image runs `DRAFT_REFERENCE` while reading historical manifests compatibly.
- `cad_agent/pdf.py`: apply the same release classification to new PDF manifests.
- `mcp_integration_lib/dotnet_ipc.py`: add `drawing_setup_audit()` with empty parameters.
- `mcp_integration_lib/tests/test_dotnet_ipc.py`: fake-dispatcher coverage for the new operation.
- `mcp_integration_lib/tests/test_dotnet_ipc_live.py`: disposable live audit and source-hash/DBMOD invariants.
- `contracts/autocad-ipc/request.schema.json`: add the read-only operation and its parameter schema.
- `contracts/autocad-ipc/result.schema.json`: add the operation enum value.
- `contracts/autocad-ipc/operations/drawing-setup-audit.schema.json`: require an empty parameter object.
- `contracts/autocad-ipc/examples/drawing-setup-audit-request.json`: contract example.
- `contracts/autocad-ipc/examples/drawing-setup-audit-result.json`: deterministic result example.
- `autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs`: add `ReadDrawingSetup()`.
- `autocad_plugin/CadAgent.AutoCAD2027/Drawing/NullDrawingGateway.cs`: safe empty implementation.
- `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`: implement live AutoCAD read-only snapshot collection.
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs`: register the operation.
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs`: validate empty parameters.
- `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`: dispatch and return the setup snapshot.
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs`: JSON/schema round-trip coverage.
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`: full-path, read-only, and deterministic payload tests.
- `docs/PROJECT.md`, `docs/ARCHITECTURE.md`, `docs/QUALITY.md`, `docs/STATUS.md`: approved scope and fresh evidence only.
- `tests/test_documentation_contract.py`: protect the new canonical design and setup gate.

## Stable Interfaces

Implement these names and meanings exactly so M3/M4 can consume them:

```python
class DrawingContractError(ValueError):
    pass


class DrawingSetupError(ValueError):
    pass


def canonical_json_sha256(payload: Mapping[str, object]) -> str:
    """SHA-256 of UTF-8 JSON with sort_keys=True and separators=(',', ':')."""


def read_contract(path: Path, *, contract: str) -> dict[str, object]:
    """Read one object and validate the exact contract version and shape."""


def create_setup_plan(
    *,
    run_id: str,
    definition: Mapping[str, object],
    profile: Mapping[str, object],
    domain_pack: Mapping[str, object],
    template_manifest: Mapping[str, object],
    template_file: Path,
) -> dict[str, object]:
    """Return a validated `SETUP_PENDING` plan bound to every input hash."""


def evaluate_setup_plan(
    plan: Mapping[str, object],
    audit: Mapping[str, object],
    *,
    verified_by: str,
    approval_reference: str,
) -> dict[str, object]:
    """Return `SETUP_VERIFIED` or `NEEDS_REVIEW` evidence with blocker codes."""


def require_setup_verified(
    evidence: Mapping[str, object],
    *,
    setup_plan_sha256: str,
    drawing_profile_sha256: str,
    template_file_sha256: str,
) -> None:
    """Fail closed when status or any bound hash differs."""
```

The .NET boundary adds:

```csharp
public interface IDrawingGateway
{
    string? ActiveDocumentFullPath { get; }
    IReadOnlyList<EntitySnapshot> ReadEntities(IReadOnlyCollection<string> handles);
    DrawingSetupSnapshot ReadDrawingSetup();
}
```

`DrawingSetupSnapshot` contains the active full path, `DBMOD` before/after, system variables, custom properties, layers, text/dimension/mleader/table styles, layouts, and viewports. Collections are ordinally sorted before serialization.

## Shared Synthetic Test Fixtures

Task 2 creates `tests/drawing_setup_fixtures.py`; later tasks import these names rather than inventing private data or redefining shapes:

```python
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from cad_agent.manifest import sha256_file


def approved_definition() -> dict[str, object]:
    return {
        "schema_version": "drawing-definition-1.0",
        "id": "DRAWDEF-SYNTHETIC-001",
        "domain": "AUTOMOTIVE_CONVERSION",
        "drawing_type": "GENERAL_ARRANGEMENT",
        "purpose": "DESIGN_APPROVAL",
        "source_mode": "RECONSTRUCT_FROM_APPROVED_SOURCE",
        "revision": "01",
        "release_profile": "REVIEW",
        "status": "APPROVED",
        "approval": {"reference": "SYNTHETIC-APPROVAL-001", "approved_by": "ENGINEER"},
    }


def approved_profile() -> dict[str, object]:
    expectations = {
        "variables": {
            "INSUNITS": 4,
            "MEASUREMENT": 1,
            "LTSCALE": 100.0,
            "CELTSCALE": 1.0,
            "PSLTSCALE": 1,
            "MSLTSCALE": 1,
            "DIMASSOC": 2,
            "ANNOALLVISIBLE": 0,
        },
        "current_layer": "0",
        "required_layers": [
            {"name": "0", "linetype": "Continuous", "plottable": True},
            {"name": "NET_CHINH", "linetype": "Continuous", "plottable": True},
        ],
        "required_styles": {
            "text": ["VX_TEXT"],
            "dimension": ["VX_DIM_20"],
            "mleader": ["VX_MLEADER"],
            "table": ["VX_TABLE"],
        },
        "layouts": [{"name": "A1-01", "viewport_scales": [0.05], "locked": True}],
        "font_policy": {
            "selected_mode": "NEW_DRAWING",
            "new_drawing": {
                "approved_fonts": ["Arial.ttf"],
                "substitution_allowed": False,
            },
            "legacy_compatibility": {
                "preserve_source_styles": True,
                "mapping_report_required": True,
            },
        },
    }
    return {
        "schema_version": "drawing-profile-1.0",
        "id": "SYNTHETIC_A1",
        "revision": "1.0",
        "status": "APPROVED",
        "supported_domains": ["AUTOMOTIVE_CONVERSION"],
        "supported_drawing_types": ["GENERAL_ARRANGEMENT"],
        "model": {"unit": "mm", "scale": "1:1", "ucs": "WORLD"},
        "setup_expectations": expectations,
        "approval": {"reference": "SYNTHETIC-PROFILE-001", "approved_by": "ENGINEER"},
    }


def approved_domain_pack() -> dict[str, object]:
    return {
        "schema_version": "domain-pack-1.0",
        "id": "AUTOMOTIVE_CONVERSION_V1",
        "revision": "1.0",
        "status": "APPROVED",
        "domains": ["AUTOMOTIVE_CONVERSION"],
        "drawing_types": ["GENERAL_ARRANGEMENT"],
        "vocabulary": ["CHASSIS", "CABIN", "CARGO_BODY", "CRANE"],
        "approval": {"reference": "SYNTHETIC-DOMAIN-001", "approved_by": "ENGINEER"},
    }


def approved_template_manifest(*, file_sha256: str) -> dict[str, object]:
    from cad_agent.drawing_contracts import canonical_json_sha256

    profile = approved_profile()
    return {
        "schema_version": "template-manifest-1.0",
        "id": "VX_MECHANICAL_2027_TEMPLATE",
        "revision": "1.0",
        "file_name": "VX_MECHANICAL_2027_TEMPLATE.dwt",
        "file_sha256": file_sha256,
        "drawing_profile_sha256": canonical_json_sha256(profile),
        "embedded_settings_sha256": canonical_json_sha256(profile["setup_expectations"]),
        "status": "APPROVED",
        "approval": {"reference": "SYNTHETIC-TEMPLATE-001", "approved_by": "ENGINEER"},
    }


def write_approved_setup_inputs(root: Path) -> SimpleNamespace:
    template_file = root / "VX_MECHANICAL_2027_TEMPLATE.dwt"
    template_file.write_bytes(b"synthetic-dwt-fixture")
    payloads = {
        "definition": approved_definition(),
        "profile": approved_profile(),
        "domain_pack": approved_domain_pack(),
        "template_manifest": approved_template_manifest(file_sha256=sha256_file(template_file)),
    }
    paths: dict[str, Path] = {"template_file": template_file}
    for name, payload in payloads.items():
        path = root / f"{name.replace('_', '-')}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        paths[name] = path
    return SimpleNamespace(**paths)


def approved_setup_plan() -> dict[str, object]:
    from cad_agent.drawing_contracts import canonical_json_sha256

    profile = approved_profile()
    return {
        "schema_version": "drawing-setup-plan-1.0",
        "run_id": "RUN-20260802-001",
        "state": "SETUP_PENDING",
        "definition": {"id": approved_definition()["id"], "sha256": canonical_json_sha256(approved_definition())},
        "drawing_profile": {"id": profile["id"], "revision": profile["revision"], "sha256": canonical_json_sha256(profile)},
        "domain_pack": {"id": approved_domain_pack()["id"], "revision": "1.0", "sha256": canonical_json_sha256(approved_domain_pack())},
        "template": {"id": "VX_MECHANICAL_2027_TEMPLATE", "revision": "1.0", "file_sha256": "a" * 64, "embedded_settings_sha256": canonical_json_sha256(profile["setup_expectations"])},
        "setup_expectations": profile["setup_expectations"],
    }


def matching_setup_audit(plan: dict[str, object]) -> dict[str, object]:
    expectations = plan["setup_expectations"]
    return {
        "schema_version": "drawing-setup-audit-1.0",
        "drawing_full_path": r"C:\temp\setup.dwg",
        "drawing_sha256": "b" * 64,
        "changed": False,
        "dbmod_before": 0,
        "dbmod_after": 0,
        "variables": dict(expectations["variables"]),
        "current_layer": expectations["current_layer"],
        "custom_properties": {"CAD_AGENT_SETTINGS_SHA256": plan["template"]["embedded_settings_sha256"]},
        "layers": list(expectations["required_layers"]),
        "styles": dict(expectations["required_styles"]),
        "layouts": list(expectations["layouts"]),
        "font_report": {"missing": [], "substituted": []},
    }


def apply_test_mutation(audit: dict[str, object], mutation: tuple[str, str, object]) -> None:
    section, key, value = mutation
    if section == "variables":
        audit["variables"][key] = value
    elif section == "styles":
        audit["styles"][key] = [value]
    elif section == "viewports":
        audit["layouts"][0]["locked"] = value
    elif section == "custom_properties":
        audit["custom_properties"][key] = value
    else:
        raise AssertionError(f"unsupported synthetic mutation: {mutation!r}")


def write_historical_v1_manifest(root: Path) -> Path:
    path = root / "run-manifest.json"
    stages = {
        name: {"state": "pending", "artifact": None, "sha256": None, "details": None}
        for name in ("primitive_ir", "semantic_ir", "dxf")
    }
    payload = {
        "schema_version": "1.0",
        "source": {"name": "drawing.png", "sha256": "c" * 64, "kind": "image"},
        "configuration": {"scale_mm_per_px": 0.5},
        "approvals": {"calibration": {"approved": True, "reference": "ticket-123"}},
        "stages": stages,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
```

Task 5 also creates `DrawingSetupFixtures.cs` with `VerifiedSnapshot(path)` returning the same variables/layers/styles/layout as above, and `UnsortedSnapshot()` returning the same entries in reverse order. This gives the C# payload tests concrete data without reading AutoCAD.

---

### Task 1: Commit the Approved Design and Route Canonical Documentation

**Files:**

- Create: `docs/superpowers/specs/2026-08-02-cad-agent-complete-design.md`
- Create: `docs/superpowers/plans/2026-08-02-cad-agent-approved-design-rollout.md`
- Create: `docs/superpowers/plans/2026-08-02-m2-drawing-initialization-gate.md`
- Modify: `docs/PROJECT.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `tests/test_documentation_contract.py`

**Interfaces:** Produces the approved design record and routes current documentation to M2. It changes no runtime behavior.

- [x] **Step 1: Write the failing documentation test**

```python
def test_approved_complete_design_and_m2_plan_are_canonical() -> None:
    design = (ROOT / "docs/superpowers/specs/2026-08-02-cad-agent-complete-design.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    project = (ROOT / "docs/PROJECT.md").read_text(encoding="utf-8")
    assert "ĐÃ DUYỆT" in design
    assert "Drawing Initialization Gate" in architecture
    assert "dimension-first" in project
    assert "DRAFT_REFERENCE" in architecture
```

- [x] **Step 2: Run the test and verify the missing-record failure**

Run: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_documentation_contract.py::DocumentationContractTests -q -p no:cacheprovider`

Expected: FAIL because the approved design/plan is not yet present in the repository and canonical docs do not route to it.

- [x] **Step 3: Add the approved records and concise routing text**

Add these architecture rules verbatim in substance:

```text
The existing image/PDF pipeline remains DRAFT_REFERENCE until a separate
dimension-first path presents hash-bound SETUP_VERIFIED evidence. Drawing
Initialization is orchestration/verification behavior; it does not move CAD
algorithms into cad_agent and does not replace the .NET/File IPC boundary.
```

- [x] **Step 4: Run the focused documentation test**

Run: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_documentation_contract.py -q -p no:cacheprovider`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add docs/superpowers/specs/2026-08-02-cad-agent-complete-design.md docs/superpowers/plans/2026-08-02-cad-agent-approved-design-rollout.md docs/superpowers/plans/2026-08-02-m2-drawing-initialization-gate.md docs/PROJECT.md docs/ARCHITECTURE.md tests/test_documentation_contract.py
git commit -m "docs: approve CAD Agent design and M2 plan"
```

### Task 2: Drawing Setup Contracts and Strict Python Validation

**Files:**

- Create: `contracts/drawing-setup/*.schema.json`
- Create: `contracts/drawing-setup/examples/*.json`
- Create: `cad_agent/drawing_contracts.py`
- Create: `tests/drawing_setup_fixtures.py`
- Create: `tests/test_drawing_setup_contracts.py`

**Interfaces:** Produces `DrawingContractError`, `canonical_json_sha256()`, and `read_contract()` for every later task.

- [x] **Step 1: Write failing tests for exact versions, fields, and deterministic hashes**

```python
def test_example_contracts_validate_and_hash_deterministically() -> None:
    definition = read_contract(EXAMPLES / "drawing-definition.json", contract="drawing_definition")
    first = canonical_json_sha256(definition)
    second = canonical_json_sha256(dict(reversed(list(definition.items()))))
    assert first == second
    assert len(first) == 64


def test_unapproved_profile_and_unknown_property_fail_closed(tmp_path: Path) -> None:
    payload = json.loads((EXAMPLES / "drawing-profile.json").read_text(encoding="utf-8"))
    payload["status"] = "DRAFT"
    payload["unexpected"] = True
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DrawingContractError, match="unexpected|APPROVED"):
        read_contract(path, contract="drawing_profile")
```

At the top of the test module define:

```python
ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "contracts" / "drawing-setup" / "examples"
```

- [x] **Step 2: Run the tests and verify imports fail**

Run: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_drawing_setup_contracts.py -q -p no:cacheprovider`

Expected: FAIL with `ModuleNotFoundError: cad_agent.drawing_contracts`.

- [x] **Step 3: Implement canonical hashing and contract dispatch**

```python
def canonical_json_sha256(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_contract(path: Path, *, contract: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DrawingContractError(f"Cannot read {contract}: {path}") from exc
    if not isinstance(payload, dict):
        raise DrawingContractError(f"{contract} root must be an object")
    _VALIDATORS[contract](payload)
    return payload
```

The explicit validators reject extra keys, wrong schema versions, empty IDs/revisions, non-64-character hashes, non-approved production profiles, non-mm/non-1:1 models, invalid viewport ratios, and missing approval references. They require both font-policy branches: new drawings use only engineer-approved fonts without implicit substitution, while legacy drawings preserve source styles and require a mapping report. Do not add a new runtime dependency on `jsonschema` in this task.

- [x] **Step 4: Add synthetic examples and assert every schema declares `additionalProperties: false`**

Use `SYNTHETIC_A1`, `VX_TEXT`, `VX_DIM_20`, and a 64-character repeated test hash. Examples contain no vehicle registration, customer name, private path, or real drawing geometry.

- [x] **Step 5: Run focused tests and Ruff**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_drawing_setup_contracts.py -q -p no:cacheprovider
& '.\.venv-py311\Scripts\python.exe' -m ruff check cad_agent\drawing_contracts.py tests\test_drawing_setup_contracts.py
```

Expected: PASS.

- [x] **Step 6: Commit**

```powershell
git add contracts/drawing-setup cad_agent/drawing_contracts.py tests/drawing_setup_fixtures.py tests/test_drawing_setup_contracts.py
git commit -m "feat: add drawing setup contracts"
```

### Task 3: Template/Profile Provenance and Setup Plan Construction

**Files:**

- Create: `cad_agent/drawing_setup.py`
- Create: `tests/test_cad_agent_drawing_setup.py`

**Interfaces:** Consumes validated contracts from Task 2. Produces `create_setup_plan()` and a `SETUP_PENDING` artifact bound to the DWT bytes, profile, domain pack, definition, and settings digest.

- [x] **Step 1: Write failing hash/refusal tests**

```python
def test_create_setup_plan_binds_every_input_hash(tmp_path: Path) -> None:
    template = tmp_path / "VX_MECHANICAL_2027_TEMPLATE.dwt"
    template.write_bytes(b"synthetic-dwt-fixture")
    manifest = approved_template_manifest(file_sha256=sha256_file(template))
    plan = create_setup_plan(
        run_id="RUN-20260802-001",
        definition=approved_definition(),
        profile=approved_profile(),
        domain_pack=approved_domain_pack(),
        template_manifest=manifest,
        template_file=template,
    )
    assert plan["state"] == "SETUP_PENDING"
    assert plan["template"]["file_sha256"] == sha256_file(template)
    assert plan["drawing_profile"]["sha256"] == canonical_json_sha256(approved_profile())


def test_changed_template_is_refused_before_plan_creation(tmp_path: Path) -> None:
    template = tmp_path / "template.dwt"
    template.write_bytes(b"changed")
    with pytest.raises(DrawingSetupError, match="template_hash_mismatch"):
        create_setup_plan(
            run_id="RUN-1",
            definition=approved_definition(),
            profile=approved_profile(),
            domain_pack=approved_domain_pack(),
            template_manifest=approved_template_manifest(file_sha256="a" * 64),
            template_file=template,
        )
```

- [x] **Step 2: Run tests and verify the function is missing**

Run: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_drawing_setup.py -q -p no:cacheprovider`

Expected: FAIL importing `create_setup_plan`.

- [x] **Step 3: Implement immutable references and compatibility checks**

```python
def _artifact_ref(kind: str, identifier: str, revision: str, payload: Mapping[str, object]) -> dict[str, str]:
    return {
        "kind": kind,
        "id": identifier,
        "revision": revision,
        "sha256": canonical_json_sha256(payload),
    }
```

`create_setup_plan()` must also enforce:

- `definition.domain` is listed by the domain pack;
- `definition.drawing_type` is supported by both domain pack and profile;
- `definition.release_profile` is `REVIEW` or `AUTHORITATIVE` for this gate;
- profile and template manifest are `APPROVED`;
- template manifest points to the exact profile digest;
- the template file is a regular `.dwt` file and its current SHA-256 matches;
- `embedded_settings_sha256` equals the digest of `profile.setup_expectations`.

- [x] **Step 4: Run focused tests and Ruff**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_drawing_setup.py -q -p no:cacheprovider
& '.\.venv-py311\Scripts\python.exe' -m ruff check cad_agent\drawing_setup.py tests\test_cad_agent_drawing_setup.py
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add cad_agent/drawing_setup.py tests/test_cad_agent_drawing_setup.py
git commit -m "feat: bind drawing setup plans to approved inputs"
```

### Task 4: Setup Plan and Verification CLI

**Files:**

- Modify: `cad_agent/cli.py`
- Modify: `tests/test_cad_agent_drawing_setup.py`

**Interfaces:** Adds three thin orchestrator commands. It does not contain AutoCAD or recognition algorithms.

- [x] **Step 1: Write failing parser and output tests**

```python
def test_drawing_setup_plan_cli_writes_pending_plan(tmp_path: Path) -> None:
    paths = write_approved_setup_inputs(tmp_path)
    output = tmp_path / "drawing-setup-plan.json"
    assert main([
        "drawing-setup-plan",
        "--run-id", "RUN-20260802-001",
        "--definition", str(paths.definition),
        "--profile", str(paths.profile),
        "--domain-pack", str(paths.domain_pack),
        "--template-manifest", str(paths.template_manifest),
        "--template-file", str(paths.template_file),
        "--output", str(output),
    ]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["state"] == "SETUP_PENDING"
```

- [x] **Step 2: Run the test and verify argparse rejects the command**

Run: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_drawing_setup.py::test_drawing_setup_plan_cli_writes_pending_plan -q -p no:cacheprovider`

Expected: FAIL because `drawing-setup-plan` is not registered.

- [x] **Step 3: Add exact command arguments and atomic JSON writes**

Register:

```text
drawing-setup-plan   --run-id --definition --profile --domain-pack
                     --template-manifest --template-file --output
drawing-setup-audit  --drawing --hwnd --ipc-dir --output [--timeout-s]
drawing-setup-verify --plan --audit --verified-by --approval-reference --output
```

Use the existing `write_manifest()` atomic writer for all three JSON artifacts. `drawing-setup-audit` is wired in Task 7; before that task, its handler may raise the explicit `unsupported_operation` error and its CLI test remains scoped to parser registration only.

- [x] **Step 4: Run focused CLI tests**

Run: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_drawing_setup.py tests\test_cad_agent_cli.py -q -p no:cacheprovider`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add cad_agent/cli.py tests/test_cad_agent_drawing_setup.py
git commit -m "feat: add drawing setup CLI boundaries"
```

### Task 5: Read-only AutoCAD Drawing Setup Snapshot

**Files:**

- Create: `autocad_plugin/CadAgent.AutoCAD2027/DrawingSetup/DrawingSetupModels.cs`
- Create: `autocad_plugin/CadAgent.AutoCAD2027/DrawingSetup/DrawingSetupPayload.cs`
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/DrawingSetup/DrawingSetupFixtures.cs`
- Create: `autocad_plugin/CadAgent.AutoCAD2027.Tests/DrawingSetup/DrawingSetupPayloadTests.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Drawing/NullDrawingGateway.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs`

**Interfaces:** Produces `DrawingSetupSnapshot` and `IDrawingGateway.ReadDrawingSetup()`. It is a single read-only transaction plus system-variable reads.

- [x] **Step 1: Write failing deterministic-payload tests**

```csharp
[Fact]
public void PayloadSortsLayersStylesLayoutsAndViewportsOrdinally()
{
    var snapshot = DrawingSetupFixtures.UnsortedSnapshot();
    var payload = DrawingSetupPayload.Create(snapshot);
    Assert.Equal(new[] { "0", "NET_CHINH" },
        payload["layers"].EnumerateArray().Select(x => x.GetProperty("name").GetString()));
    Assert.False(payload["changed"].GetBoolean());
    Assert.Equal(0, payload["dbmod_before"].GetInt32());
    Assert.Equal(0, payload["dbmod_after"].GetInt32());
}
```

- [x] **Step 2: Run C# tests and verify types are missing**

Run: `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64 --filter FullyQualifiedName~DrawingSetup`

Expected: build failure because `DrawingSetupSnapshot` is undefined.

- [x] **Step 3: Implement normalized records**

```csharp
public sealed record DrawingSetupSnapshot(
    string DrawingFullPath,
    int DbModBefore,
    int DbModAfter,
    int InsUnits,
    int Measurement,
    double LtScale,
    double Celtscale,
    int PsLtScale,
    int MsLtScale,
    int DimAssoc,
    int AnnoAllVisible,
    string CurrentLayer,
    IReadOnlyDictionary<string, string> CustomProperties,
    IReadOnlyList<LayerSetupSnapshot> Layers,
    IReadOnlyList<TextStyleSetupSnapshot> TextStyles,
    IReadOnlyList<NamedStyleSnapshot> DimensionStyles,
    IReadOnlyList<NamedStyleSnapshot> MLeaderStyles,
    IReadOnlyList<NamedStyleSnapshot> TableStyles,
    IReadOnlyList<LayoutSetupSnapshot> Layouts);
```

`LayerSetupSnapshot` includes name, ACI color, linetype, lineweight, plottable, frozen, and locked. `LayoutSetupSnapshot` includes name, model/paper flag, canonical media name, device, plot type, numerator/denominator, and its viewport records; each viewport includes handle, custom scale, and locked state.

Define the subordinate records and shared fixture explicitly:

```csharp
public sealed record LayerSetupSnapshot(
    string Name, int ColorIndex, string Linetype, int LineWeight,
    bool Plottable, bool Frozen, bool Locked);
public sealed record TextStyleSetupSnapshot(string Name, string Font, string BigFont);
public sealed record NamedStyleSnapshot(string Name);
public sealed record ViewportSetupSnapshot(string Handle, double CustomScale, bool Locked);
public sealed record LayoutSetupSnapshot(
    string Name, bool IsModel, string CanonicalMediaName, string PlotDevice,
    string PlotType, double ScaleNumerator, double ScaleDenominator,
    IReadOnlyList<ViewportSetupSnapshot> Viewports);

internal static class DrawingSetupFixtures
{
    internal static DrawingSetupSnapshot VerifiedSnapshot(string path) => new(
        path, 0, 0, 4, 1, 100.0, 1.0, 1, 1, 2, 0, "0",
        new Dictionary<string, string>
        {
            ["CAD_AGENT_SETTINGS_SHA256"] = new string('a', 64)
        },
        new[]
        {
            new LayerSetupSnapshot("0", 7, "Continuous", -1, true, false, false),
            new LayerSetupSnapshot("NET_CHINH", 7, "Continuous", 35, true, false, false)
        },
        new[] { new TextStyleSetupSnapshot("VX_TEXT", "Arial.ttf", "") },
        new[] { new NamedStyleSnapshot("VX_DIM_20") },
        new[] { new NamedStyleSnapshot("VX_MLEADER") },
        new[] { new NamedStyleSnapshot("VX_TABLE") },
        new[]
        {
            new LayoutSetupSnapshot(
                "A1-01", false, "ISO_A1_(841.00_x_594.00_MM)",
                "DWG To PDF.pc3", "Layout", 1.0, 1.0,
                new[] { new ViewportSetupSnapshot("2F", 0.05, true) })
        });

    internal static DrawingSetupSnapshot UnsortedSnapshot()
    {
        var source = VerifiedSnapshot(@"C:\temp\setup.dwg");
        return source with
        {
            Layers = source.Layers.Reverse().ToArray(),
            Layouts = source.Layouts.Reverse().ToArray()
        };
    }
}
```

- [x] **Step 4: Implement live collection without mutation**

In `AutoCadDrawingGateway.ReadDrawingSetup()`:

1. read `DBMOD` before;
2. read system variables;
3. open layer/style/layout dictionaries `ForRead` only;
4. read custom summary properties;
5. close the transaction without commit/write-opened objects;
6. read `DBMOD` after;
7. throw if the values differ.

Do not call `UpgradeOpen`, `StartTransaction` with writes, `Save`, `Regen`, `SetSystemVariable`, or any entity mutation method.

- [x] **Step 5: Run focused C# tests and build**

Run:

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64 --filter FullyQualifiedName~DrawingSetup
dotnet build autocad_plugin/CadAgent.AutoCAD2027.sln -c Release -p:Platform=x64
```

Expected: PASS, with no Autodesk DLL copied to output.

- [x] **Step 6: Commit**

```powershell
git add autocad_plugin/CadAgent.AutoCAD2027/DrawingSetup autocad_plugin/CadAgent.AutoCAD2027.Tests/DrawingSetup autocad_plugin/CadAgent.AutoCAD2027/Drawing/IDrawingGateway.cs autocad_plugin/CadAgent.AutoCAD2027/Drawing/NullDrawingGateway.cs autocad_plugin/CadAgent.AutoCAD2027/Commands/CommandContext.cs
git commit -m "feat: read AutoCAD drawing setup without mutation"
```

### Task 6: Versioned IPC Operation and Dispatcher

**Files:**

- Modify: `contracts/autocad-ipc/request.schema.json`
- Modify: `contracts/autocad-ipc/result.schema.json`
- Create: `contracts/autocad-ipc/operations/drawing-setup-audit.schema.json`
- Create: `contracts/autocad-ipc/examples/drawing-setup-audit-request.json`
- Create: `contracts/autocad-ipc/examples/drawing-setup-audit-result.json`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractModels.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/ContractValidator.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027/Ipc/OperationDispatcher.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/ContractTests.cs`
- Modify: `autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc/OperationDispatcherTests.cs`

**Interfaces:** Adds `drawing_setup_audit` compatibly to schema version `1.0`; existing operation shapes remain byte-for-byte compatible.

- [x] **Step 1: Write failing contract and dispatcher tests**

```csharp
[Fact]
public void DrawingSetupAuditRequiresEmptyParametersAndMatchingFullPath()
{
    var gateway = new StubDrawingGateway
    {
        ActiveDocumentFullPath = @"C:\temp\setup.dwg",
        DrawingSetup = DrawingSetupFixtures.VerifiedSnapshot(@"C:\temp\setup.dwg")
    };
    var result = CreateDispatcher(gateway).Dispatch(Request(
        "drawing_setup_audit", "setup-001", @"C:\temp\setup.dwg", Parameters()));
    Assert.True(result.Success);
    Assert.False(result.Changed);
    Assert.Equal(0, result.Payload!["dbmod_after"].GetInt32());
    Assert.Equal(1, gateway.ReadDrawingSetupCallCount);
}
```

- [x] **Step 2: Run focused tests and verify unsupported-operation failure**

Run: `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64 --filter "FullyQualifiedName~ContractTests|FullyQualifiedName~OperationDispatcherTests"`

Expected: FAIL because the operation is not registered.

- [x] **Step 3: Add the operation to JSON schemas and C# validation**

The request parameters schema is exactly:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "maxProperties": 0
}
```

The dispatcher first verifies the active full path, then calls `ReadDrawingSetup()`, returns its normalized payload, `changed=false`, no entity handles, and no save status. A path mismatch blocks the gateway call.

- [x] **Step 4: Run all C# tests**

Run: `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64`

Expected: PASS with all existing health/review/close/BOM tests unchanged.

- [x] **Step 5: Commit**

```powershell
git add contracts/autocad-ipc autocad_plugin/CadAgent.AutoCAD2027/Ipc autocad_plugin/CadAgent.AutoCAD2027.Tests/Ipc
git commit -m "feat: expose read-only drawing setup audit"
```

### Task 7: Python IPC Client and CLI Audit Artifact

**Files:**

- Modify: `mcp_integration_lib/dotnet_ipc.py`
- Modify: `mcp_integration_lib/tests/test_dotnet_ipc.py`
- Modify: `cad_agent/cli.py`
- Modify: `tests/test_cad_agent_drawing_setup.py`

**Interfaces:** Produces `DotNetIPCClient.drawing_setup_audit()` and completes the `drawing-setup-audit` command from Task 4.

- [x] **Step 1: Write failing fake-dispatcher tests**

```python
def test_drawing_setup_audit_uses_empty_parameters_and_preserves_payload() -> None:
    with TemporaryDirectory() as temporary:
        dispatcher = FakeDispatcher(Path(temporary), {"dbmod_before": 0, "dbmod_after": 0, "changed": False})
        client = DotNetIPCClient(ipc_dir=temporary, trigger=dispatcher)
        result = client.drawing_setup_audit(r"C:\temp\setup.dwg", drawing_sha256="a" * 64)
        assert dispatcher.requests[0]["operation"] == "drawing_setup_audit"
        assert dispatcher.requests[0]["parameters"] == {}
        assert result["payload"]["dbmod_after"] == 0
```

- [x] **Step 2: Run focused tests and verify the method is missing**

Run: `& '.\.venv-py311\Scripts\python.exe' -m pytest mcp_integration_lib\tests\test_dotnet_ipc.py tests\test_cad_agent_drawing_setup.py -q -p no:cacheprovider`

Expected: FAIL with missing method/unsupported operation.

- [x] **Step 3: Implement the thin client method**

```python
def drawing_setup_audit(
    self,
    drawing_full_path: str | Path,
    *,
    drawing_sha256: str,
    request_id: str | None = None,
) -> dict[str, Any]:
    return self.request(
        "drawing_setup_audit",
        drawing_full_path,
        drawing_sha256=drawing_sha256,
        parameters={},
        approval=None,
        request_id=request_id,
    )
```

Add `drawing_setup_audit` to the dispatcher's supported-operation set and require its parameters object to be empty. Keep the operation read-only and approval-free; write-capable operations retain the existing approval path.

The CLI hashes the drawing before the request, executes the audit, hashes it again, refuses `source_changed` if the file changed, and writes a normalized `drawing-setup-audit-1.0` artifact that contains the source hash and IPC result payload.

- [x] **Step 4: Run focused Python tests and Ruff**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest mcp_integration_lib\tests\test_dotnet_ipc.py tests\test_cad_agent_drawing_setup.py -q -p no:cacheprovider
& '.\.venv-py311\Scripts\python.exe' -m ruff check mcp_integration_lib\dotnet_ipc.py mcp_integration_lib\tests\test_dotnet_ipc.py cad_agent\cli.py cad_agent\drawing_setup.py tests\test_cad_agent_drawing_setup.py
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add mcp_integration_lib/dotnet_ipc.py mcp_integration_lib/tests/test_dotnet_ipc.py cad_agent/cli.py tests/test_cad_agent_drawing_setup.py
git commit -m "feat: collect drawing setup audit through dotnet IPC"
```

### Task 8: Setup Comparison, Blocker Codes, and Enforcement API

**Files:**

- Modify: `cad_agent/drawing_setup.py`
- Modify: `tests/test_cad_agent_drawing_setup.py`

**Interfaces:** Produces `evaluate_setup_plan()` and `require_setup_verified()` for M3/M4.

- [x] **Step 1: Write failing pass/fail/stale-evidence tests**

```python
def test_matching_audit_becomes_setup_verified() -> None:
    plan = approved_setup_plan()
    evidence = evaluate_setup_plan(
        plan,
        matching_setup_audit(plan),
        verified_by="ENGINEER",
        approval_reference="M2-LIVE-001",
    )
    assert evidence["status"] == "SETUP_VERIFIED"
    assert evidence["blockers"] == []
    require_setup_verified(
        evidence,
        setup_plan_sha256=canonical_json_sha256(plan),
        drawing_profile_sha256=plan["drawing_profile"]["sha256"],
        template_file_sha256=plan["template"]["file_sha256"],
    )


@pytest.mark.parametrize("mutation,code", [
    (("variables", "INSUNITS", 0), "setup_incomplete"),
    (("styles", "dimstyle", "Standard"), "profile_hash_mismatch"),
    (("viewports", "SIDE", False), "viewport_scale_mismatch"),
    (("custom_properties", "CAD_AGENT_SETTINGS_SHA256", "bad"), "template_hash_mismatch"),
])
def test_setup_mismatch_returns_needs_review(mutation, code) -> None:
    plan = approved_setup_plan()
    audit = matching_setup_audit(plan)
    apply_test_mutation(audit, mutation)
    evidence = evaluate_setup_plan(plan, audit, verified_by="ENGINEER", approval_reference="M2-LIVE-001")
    assert evidence["status"] == "NEEDS_REVIEW"
    assert code in {item["code"] for item in evidence["blockers"]}
```

- [x] **Step 2: Run tests and verify missing comparison behavior**

Run: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_drawing_setup.py -q -p no:cacheprovider`

Expected: FAIL for undefined `evaluate_setup_plan`/`require_setup_verified`.

- [x] **Step 3: Implement exact comparisons and blocker output**

Required blocker codes for this milestone:

```python
SETUP_BLOCKERS = {
    "source_changed",
    "setup_incomplete",
    "profile_missing",
    "profile_hash_mismatch",
    "template_hash_mismatch",
    "font_substitution_risk",
    "viewport_scale_mismatch",
    "drawing_target_mismatch",
}
```

Each blocker includes `code`, `path`, `expected`, `actual`, and `severity`. `evaluate_setup_plan()` compares every required profile item, checks `dbmod_before == dbmod_after`, checks the audit drawing hash, and sets evidence hashes for the plan/audit/profile/template. It never changes the input mappings.

- [x] **Step 4: Make `drawing-setup-verify` write evidence even on mismatch**

The command returns exit code `0` only for `SETUP_VERIFIED`; for `NEEDS_REVIEW` it atomically writes the evidence and returns exit code `2` with a concise blocker summary.

- [x] **Step 5: Run focused tests and Ruff**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_drawing_setup.py -q -p no:cacheprovider
& '.\.venv-py311\Scripts\python.exe' -m ruff check cad_agent\drawing_setup.py cad_agent\cli.py tests\test_cad_agent_drawing_setup.py
```

Expected: PASS.

- [x] **Step 6: Commit**

```powershell
git add cad_agent/drawing_setup.py cad_agent/cli.py tests/test_cad_agent_drawing_setup.py
git commit -m "feat: enforce drawing initialization gate"
```

### Task 9: Preserve the Legacy Pixel-first Path as Draft/Reference

**Files:**

- Modify: `cad_agent/manifest.py`
- Modify: `cad_agent/pdf.py`
- Modify: `tests/test_cad_agent_cli.py`
- Modify: `tests/test_cad_agent_pdf.py`
- Modify: `docs/ARCHITECTURE.md`

**Interfaces:** Existing commands keep working. New manifests explicitly say they are not authoritative; old on-disk manifests remain resumable.

- [x] **Step 1: Write failing classification and compatibility tests**

```python
def test_new_image_manifest_is_draft_reference_only(tmp_path: Path) -> None:
    source = tmp_path / "drawing.png"
    source.write_bytes(b"image")
    manifest = new_manifest(source, 0.5, "ticket-123")
    assert manifest["release_profile"] == "DRAFT_REFERENCE"
    assert manifest["authoritative_release_eligible"] is False
    assert manifest["drawing_setup_evidence"] is None


def test_historical_manifest_without_release_fields_still_reads_as_draft(tmp_path: Path) -> None:
    path = write_historical_v1_manifest(tmp_path)
    payload = read_manifest(path)
    assert payload["release_profile"] == "DRAFT_REFERENCE"
    assert payload["authoritative_release_eligible"] is False
```

- [x] **Step 2: Run focused legacy tests and verify fields are absent**

Run: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_cli.py tests\test_cad_agent_pdf.py -q -p no:cacheprovider`

Expected: FAIL on the new assertions.

- [x] **Step 3: Add defaults without changing stage behavior or schema version**

New manifests write the three fields. Readers use `setdefault()` after validating the historical `1.0` shape so exact old checkpoints remain resumable. Do not require setup evidence for the legacy commands and do not label them authoritative.

- [x] **Step 4: Run image/PDF focused tests**

Run: `& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_cad_agent_cli.py tests\test_cad_agent_pdf.py -q -p no:cacheprovider`

Expected: PASS, including byte-identical resume for manifests created by the new code.

- [x] **Step 5: Commit**

```powershell
git add cad_agent/manifest.py cad_agent/pdf.py tests/test_cad_agent_cli.py tests/test_cad_agent_pdf.py docs/ARCHITECTURE.md
git commit -m "feat: classify legacy reconstruction as draft reference"
```

### Task 10: Disposable AutoCAD Live Gate and Candidate-DWG Audit

**Files:**

- Modify: `mcp_integration_lib/tests/test_dotnet_ipc_live.py`
- Create after the run: `docs/reviews/2026-08-02-m2-drawing-setup-live-review.md`
- Create only after engineer approval: `profiles/drawing/VEHICLE_CONVERSION_V1.json`
- Create only after engineer approval: `profiles/domains/AUTOMOTIVE_CONVERSION_V1.json`
- Create only after engineer approval: `profiles/templates/VX_MECHANICAL_2027_TEMPLATE.json`

**Interfaces:** Produces live evidence and the first approved non-sensitive profile metadata. DWT/DWG binaries and raw audit JSON remain outside Git.

- [x] **Step 1: Add an opt-in live test with source and DBMOD invariants**

```python
@pytest.mark.autocad_mechanical
def test_live_drawing_setup_audit_is_read_only_and_deterministic() -> None:
    drawing = Path(os.environ["CAD_AGENT_M2_DISPOSABLE_DWG"])
    hwnd = int(os.environ["CAD_AGENT_AUTOCAD_HWND"])
    trigger = make_windows_dotnet_dispatch_trigger(hwnd)
    dotnet_client = DotNetIPCClient(ipc_dir=r"C:\temp", trigger=trigger, timeout_s=30.0)
    before = _sha256(drawing)
    result = dotnet_client.drawing_setup_audit(
        normalize_windows_absolute_path(drawing),
        drawing_sha256=before,
        request_id="m2-live-setup-audit",
    )
    assert result["changed"] is False
    assert result["payload"]["dbmod_before"] == result["payload"]["dbmod_after"]
    assert _sha256(drawing) == before
```

- [ ] **Step 2: Prepare operator-controlled inputs**

On the Windows workstation, set:

```powershell
$env:CAD_AGENT_FILE_IPC = '1'
$env:CAD_AGENT_AUTOCAD_HWND = '<active AutoCAD Mechanical 2027 HWND>'
$env:CAD_AGENT_AUTOCAD_LISP_PATH = '<approved existing File IPC bootstrap path>'
$env:CAD_AGENT_M2_DISPOSABLE_DWG = 'C:\temp\cad-agent-m2\setup-audit.dwg'
$ApprovedTemplatePath = 'C:\approved-cad-agent-templates\VX_MECHANICAL_2027_TEMPLATE.dwt'
```

The operator replaces the placeholder HWND/bootstrap values, verifies `$ApprovedTemplatePath` exists, creates and opens the disposable DWG from that exact approved DWT, and confirms AutoCAD's active document full path equals `CAD_AGENT_M2_DISPOSABLE_DWG`. The DWT and candidate files are stored outside Git. The AutoCAD plugin/dispatcher is loaded from an approved trusted path; do not change `SECURELOAD`.

- [ ] **Step 3: Run the live setup audit**

Run:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m pytest mcp_integration_lib\tests\test_dotnet_ipc_live.py -m autocad_mechanical -ra -p no:cacheprovider
```

Expected for acceptance: the named setup audit test passes, source SHA-256 is unchanged, `changed=false`, DBMOD is unchanged, and the drawing closes without save. If a prerequisite is absent, record `SKIP` or `NOT RUN`.

- [ ] **Step 4: Audit `BVTL.dwg` and ten candidate DWGs without committing them**

For each file, open a copy as a disposable document and run `drawing-setup-audit`. Store the raw JSON outside Git in a directory identified by an evidence manifest containing file name, source SHA-256, audit SHA-256, AutoCAD version, and result state. The candidate set must contain exactly eleven records: `BVTL.dwg` plus ten engineer-selected candidates.

The engineer classifies every layer/style/layout/font entry as `REUSABLE_STANDARD`, `SOURCE_SPECIFIC`, `LEGACY_COMPATIBILITY`, `NEEDS_REVIEW`, or `DO_NOT_REUSE`. Only approved non-sensitive `REUSABLE_STANDARD` metadata is copied into the three `profiles/` JSON files. The approved profile must retain both font-policy branches: strict approved fonts for new drawings and source-style preservation plus a mapping report for legacy compatibility.

- [ ] **Step 5: Verify the approved profile against a fresh disposable drawing**

Run the three commands in order:

```powershell
& '.\.venv-py311\Scripts\python.exe' -m cad_agent drawing-setup-plan --run-id M2-LIVE-001 --definition C:\temp\cad-agent-m2\drawing-definition.json --profile .\profiles\drawing\VEHICLE_CONVERSION_V1.json --domain-pack .\profiles\domains\AUTOMOTIVE_CONVERSION_V1.json --template-manifest .\profiles\templates\VX_MECHANICAL_2027_TEMPLATE.json --template-file $ApprovedTemplatePath --output C:\temp\cad-agent-m2\drawing-setup-plan.json
& '.\.venv-py311\Scripts\python.exe' -m cad_agent drawing-setup-audit --drawing $env:CAD_AGENT_M2_DISPOSABLE_DWG --hwnd $env:CAD_AGENT_AUTOCAD_HWND --ipc-dir C:\temp --output C:\temp\cad-agent-m2\drawing-setup-audit.json
& '.\.venv-py311\Scripts\python.exe' -m cad_agent drawing-setup-verify --plan C:\temp\cad-agent-m2\drawing-setup-plan.json --audit C:\temp\cad-agent-m2\drawing-setup-audit.json --verified-by ENGINEER --approval-reference M2-LIVE-001 --output C:\temp\cad-agent-m2\drawing-setup-evidence.json
```

Expected: final evidence status is `SETUP_VERIFIED` and contains no blockers. If the approved standard data has not yet been supplied, record the live profile gate as `NOT RUN`; do not fabricate profile values.

- [ ] **Step 6: Record review evidence and commit only approved metadata/tests**

```powershell
git add mcp_integration_lib/tests/test_dotnet_ipc_live.py docs/reviews/2026-08-02-m2-drawing-setup-live-review.md profiles
git commit -m "test: verify M2 drawing setup gate in AutoCAD"
```

Before committing, verify `git status --short` contains no DWT, DWG, DXF, raw audit JSON, customer data, or absolute local paths in profile JSON.

### Task 11: Authoritative Verification, Independent Review, and Status Closure

**Files:**

- Modify: `docs/STATUS.md`
- Modify only if the aggregate gate changes: `scripts/verify.ps1`
- Modify only with a matching script-contract change: `tests/test_verification_contract.py`

**Interfaces:** Produces final M2 evidence and closes the plan. It does not add new behavior.

- [x] **Step 1: Run focused suites from a clean integration tree**

```powershell
dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64
& '.\.venv-py311\Scripts\python.exe' -m pytest tests\test_drawing_setup_contracts.py tests\test_cad_agent_drawing_setup.py mcp_integration_lib\tests\test_dotnet_ipc.py tests\test_cad_agent_cli.py tests\test_cad_agent_pdf.py -q -p no:cacheprovider
```

Expected: PASS with zero unexpected warnings.

- [x] **Step 2: Run the authoritative verifier**

Run: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1`

Expected: exit `0`, clean-tree checks pass, .NET tests pass, offline JUnit has zero failures/errors/skips, unavailable probes remain explicit, Ruff passes, and verification does not alter repository status.

- [ ] **Step 3: Run required independent reviews**

Use three independent review packets from `docs/templates/`:

1. requirements/architecture: setup gate matches the approved design and legacy paths remain draft;
2. correctness/test: hashes, comparisons, backward compatibility, and deterministic ordering;
3. security/operations: read-only AutoCAD behavior, trusted loading, no private artifacts, and no production save.

Accept a finding only when it names scope, impact, evidence, and verification. Resolve all P0/P1 before closure.

- [x] **Step 4: Update status with exact evidence**

Record the implementation Head SHA, commands, exit codes, test totals, live state, template/profile evidence identifiers, and remaining risks. Do not copy a local absolute path into `docs/STATUS.md`; identify external artifacts by SHA-256 and approved record name.

- [ ] **Step 5: Close the plan lifecycle and commit**

Update this plan to `Status: Completed`, add `Completion Head SHA`, exact verification results, and live/private gate states, then commit:

```powershell
git add docs/STATUS.md docs/superpowers/plans/2026-08-02-m2-drawing-initialization-gate.md
git commit -m "docs: close M2 drawing initialization gate"
```

---

## Dependency and Ownership Order

| Task | Depends on | May run in parallel | Primary write set |
|---|---|---|---|
| T1 docs | None | None | docs + documentation contract test |
| T2 contracts | T1 | None | drawing-setup contracts + Python validator |
| T3 plan provenance | T2 | None | `cad_agent/drawing_setup.py` + tests |
| T4 CLI | T3 | None | `cad_agent/cli.py` + setup tests |
| T5 .NET snapshot | T2 | T3 after T2 is integrated | DrawingSetup/gateway C# files |
| T6 IPC dispatcher | T5 | None | IPC schemas/C# dispatcher/tests |
| T7 Python IPC | T6 | None | dotnet client + CLI audit glue/tests |
| T8 comparison gate | T4 and T7 | None | setup evaluator/CLI/tests |
| T9 legacy classification | T3 | T5–T7 when write sets do not overlap | manifests/PDF/tests/docs |
| T10 live/profile | T8 and T9 | None | live test, review record, approved profiles |
| T11 closure | T10 | None | status and plan lifecycle |

One integration owner merges tasks sequentially. T3 and T5 may be implemented in parallel only after T2 is integrated and only because their write sets do not overlap. No two workers edit `cad_agent/cli.py`, IPC contracts, or `docs/STATUS.md` concurrently.

For PO Luna Max, use one implementer per active write set and at most the
parallel windows named in the table. Multiple implementers return bounded
commits to the integration owner; they do not merge themselves. Use one
designated reviewer agent across M2. That reviewer performs the required review
passes sequentially after each integration wave and again on the final M2
candidate.

## M2 Acceptance Criteria

- Approved design and M2 plan are present in repo and routed by canonical docs.
- All seven Drawing Setup contract kinds validate strictly and hash deterministically, including both new-drawing and legacy-compatibility font policies.
- Setup plan binds definition, profile, domain pack, DWT bytes, settings digest, run ID, and approvals.
- Synthetic examples remain configuration-generic; adding another automotive-conversion configuration does not require a new core branch or equipment-specific setup schema.
- `.NET` setup audit is read-only, full-path-bound, deterministically ordered, and reports unchanged DBMOD/source hash.
- `SETUP_VERIFIED` is emitted only when every required variable/layer/style/layout/viewport/font/template check passes.
- Every mismatch produces `NEEDS_REVIEW` with a stable blocker code and evidence.
- `require_setup_verified()` rejects stale/mismatched plan, profile, or template hashes.
- Existing `run` and `run-pdf` behavior remains working and explicitly `DRAFT_REFERENCE`.
- `BVTL.dwg` plus ten candidate DWGs are audited outside Git, or the external gate is honestly recorded `NOT RUN`.
- Only engineer-approved non-sensitive profile metadata is committed; no source drawings or DWT binaries are committed.
- Focused suites, `scripts/verify.ps1`, required live gate, and independent reviews have fresh evidence with no unresolved P0/P1.

## Execution Handoff

After this plan is committed, execute it either:

1. **Subagent-Driven (recommended):** fresh implementers for bounded tasks, using only the parallel windows in the ownership table, with one designated reviewer and one integration owner.
2. **Inline Execution:** execute tasks sequentially in the current session with `superpowers:executing-plans` checkpoints.

Do not start M3 until M2 is closed as `PASS` or the project owner explicitly approves a revised M2 scope.
