from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cad_agent.drawing_setup import DrawingSetupError, create_setup_plan


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_approved_inputs(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    template = root / "approved-template.dwt"
    template.write_bytes(b"approved-template-bytes")
    file_sha256 = hashlib.sha256(template.read_bytes()).hexdigest()
    profile = {
        "schema_version": "drawing-profile-1.0",
        "id": "PROFILE_A1",
        "revision": "1.0",
        "status": "APPROVED",
        "supported_domains": ["AUTOMOTIVE_CONVERSION"],
        "supported_drawing_types": ["GENERAL_ARRANGEMENT"],
        "model": {"unit": "mm", "scale": "1:1", "ucs": "WORLD"},
        "setup_expectations": {
            "variables": {
                "INSUNITS": 4,
                "MEASUREMENT": 1,
                "LTSCALE": 100,
                "CELTSCALE": 1,
                "PSLTSCALE": 1,
                "MSLTSCALE": 1,
                "DIMASSOC": 2,
                "ANNOALLVISIBLE": 0,
            },
            "current_layer": "0",
            "required_layers": [{"name": "0", "linetype": "Continuous", "plottable": True}],
            "required_styles": {
                "text": ["TXT"],
                "dimension": ["DIM"],
                "mleader": ["MLEADER"],
                "table": ["TABLE"],
            },
            "layouts": [{"name": "A1", "viewport_scales": [0.05], "locked": True}],
            "font_policy": {
                "selected_mode": "NEW_DRAWING",
                "new_drawing": {"approved_fonts": ["Arial.ttf"], "substitution_allowed": False},
                "legacy_compatibility": {
                    "preserve_source_styles": True,
                    "mapping_report_required": True,
                },
            },
        },
        "approval": {"reference": "PROFILE-APPROVAL", "approved_by": "ENGINEER"},
    }
    definition = {
        "schema_version": "drawing-definition-1.0",
        "id": "DEFINITION_001",
        "domain": "AUTOMOTIVE_CONVERSION",
        "drawing_type": "GENERAL_ARRANGEMENT",
        "purpose": "DESIGN_APPROVAL",
        "source_mode": "RECONSTRUCT_FROM_APPROVED_SOURCE",
        "revision": "1",
        "release_profile": "REVIEW",
        "status": "APPROVED",
        "approval": {"reference": "DEFINITION-APPROVAL", "approved_by": "ENGINEER"},
    }
    domain_pack = {
        "schema_version": "domain-pack-1.0",
        "id": "AUTOMOTIVE_V1",
        "revision": "1.0",
        "status": "APPROVED",
        "domains": ["AUTOMOTIVE_CONVERSION"],
        "drawing_types": ["GENERAL_ARRANGEMENT"],
        "vocabulary": ["CHASSIS"],
        "approval": {"reference": "DOMAIN-APPROVAL", "approved_by": "ENGINEER"},
    }
    canonical = lambda payload: hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    template_manifest = {
        "schema_version": "template-manifest-1.0",
        "id": "TEMPLATE_A1",
        "revision": "1.0",
        "file_name": template.name,
        "file_sha256": file_sha256,
        "drawing_profile_sha256": canonical(profile),
        "embedded_settings_sha256": canonical(profile["setup_expectations"]),
        "status": "APPROVED",
        "approval": {"reference": "TEMPLATE-APPROVAL", "approved_by": "ENGINEER"},
    }
    return {
        "definition_path": _write_json(root / "definition.json", definition),
        "profile_path": _write_json(root / "profile.json", profile),
        "domain_pack_path": _write_json(root / "domain-pack.json", domain_pack),
        "template_manifest_path": _write_json(root / "template-manifest.json", template_manifest),
        "template_path": template,
    }


def test_create_setup_plan_binds_approved_provenance(tmp_path: Path) -> None:
    paths = _write_approved_inputs(tmp_path)

    plan = create_setup_plan(
        run_id="RUN-20260803-001",
        **paths,
    )

    assert plan["schema_version"] == "drawing-setup-plan-1.0"
    assert plan["run_id"] == "RUN-20260803-001"
    assert plan["state"] == "SETUP_PENDING"
    assert plan["definition"]["id"] == "DEFINITION_001"
    assert plan["drawing_profile"]["id"] == "PROFILE_A1"
    assert plan["domain_pack"]["id"] == "AUTOMOTIVE_V1"
    assert plan["template"]["file_sha256"] == hashlib.sha256(
        paths["template_path"].read_bytes()
    ).hexdigest()
    assert plan["setup_expectations"]["current_layer"] == "0"
    json.dumps(plan)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda paths: paths["template_path"].unlink(), "template path"),
        (lambda paths: (paths["template_path"].unlink(), paths["template_path"].mkdir()), "regular file"),
    ],
)
def test_template_path_must_be_an_existing_regular_dwt(tmp_path: Path, mutation, message: str) -> None:
    paths = _write_approved_inputs(tmp_path)
    mutation(paths)
    with pytest.raises(DrawingSetupError, match=message):
        create_setup_plan(run_id="RUN-20260803-002", **paths)


def test_template_extension_and_hash_are_checked(tmp_path: Path) -> None:
    paths = _write_approved_inputs(tmp_path)
    paths["template_path"].rename(tmp_path / "approved-template.dwg")
    paths["template_path"] = tmp_path / "approved-template.dwg"
    with pytest.raises(DrawingSetupError, match=r"\.dwt"):
        create_setup_plan(run_id="RUN-20260803-003", **paths)

    paths = _write_approved_inputs(tmp_path / "hash-case")
    paths["template_path"].write_bytes(b"changed-template-bytes")
    with pytest.raises(DrawingSetupError, match="template SHA-256"):
        create_setup_plan(run_id="RUN-20260803-004", **paths)


def test_profile_and_embedded_settings_hashes_are_checked(tmp_path: Path) -> None:
    paths = _write_approved_inputs(tmp_path)
    manifest = json.loads(paths["template_manifest_path"].read_text(encoding="utf-8"))
    manifest["drawing_profile_sha256"] = "0" * 64
    paths["template_manifest_path"].write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(DrawingSetupError, match="drawing profile SHA-256"):
        create_setup_plan(run_id="RUN-20260803-005", **paths)

    paths = _write_approved_inputs(tmp_path / "settings-case")
    manifest = json.loads(paths["template_manifest_path"].read_text(encoding="utf-8"))
    manifest["embedded_settings_sha256"] = "0" * 64
    paths["template_manifest_path"].write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(DrawingSetupError, match="embedded settings SHA-256"):
        create_setup_plan(run_id="RUN-20260803-006", **paths)


def test_approved_status_and_compatibility_are_required(tmp_path: Path) -> None:
    paths = _write_approved_inputs(tmp_path)
    profile = json.loads(paths["profile_path"].read_text(encoding="utf-8"))
    profile["status"] = "DRAFT"
    paths["profile_path"].write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(DrawingSetupError, match="APPROVED"):
        create_setup_plan(run_id="RUN-20260803-007", **paths)

    paths = _write_approved_inputs(tmp_path / "domain-case")
    domain = json.loads(paths["domain_pack_path"].read_text(encoding="utf-8"))
    domain["domains"] = ["OTHER_DOMAIN"]
    paths["domain_pack_path"].write_text(json.dumps(domain), encoding="utf-8")
    with pytest.raises(DrawingSetupError, match="domain.*domain pack"):
        create_setup_plan(run_id="RUN-20260803-008", **paths)

    paths = _write_approved_inputs(tmp_path / "type-case")
    definition = json.loads(paths["definition_path"].read_text(encoding="utf-8"))
    definition["drawing_type"] = "DETAIL"
    paths["definition_path"].write_text(json.dumps(definition), encoding="utf-8")
    with pytest.raises(DrawingSetupError, match="drawing type"):
        create_setup_plan(run_id="RUN-20260803-009", **paths)


def test_run_id_input_contract_and_plan_references_are_strict(tmp_path: Path) -> None:
    paths = _write_approved_inputs(tmp_path)
    with pytest.raises(DrawingSetupError, match="invalid run ID"):
        create_setup_plan(run_id="RUN WITH SPACE", **paths)

    with pytest.raises(DrawingSetupError, match="inconsistent input contract"):
        create_setup_plan(
            run_id="RUN-20260803-010",
            definition_path=paths["definition_path"],
            definition=paths["definition_path"],
            profile_path=paths["profile_path"],
            domain_pack_path=paths["domain_pack_path"],
            template_manifest_path=paths["template_manifest_path"],
            template_path=paths["template_path"],
        )

    plan = create_setup_plan(run_id="RUN-20260803-011", **paths)
    with pytest.raises(TypeError, match="immutable"):
        plan["definition"]["id"] = "MUTATED"
    with pytest.raises(TypeError, match="immutable"):
        plan["setup_expectations"]["required_layers"].append({})


def test_common_positional_input_orders_are_supported(tmp_path: Path) -> None:
    paths = _write_approved_inputs(tmp_path)
    plan = create_setup_plan(
        paths["definition_path"],
        paths["profile_path"],
        paths["domain_pack_path"],
        paths["template_manifest_path"],
        paths["template_path"],
        run_id="RUN-20260803-012",
    )
    assert plan["run_id"] == "RUN-20260803-012"

    paths = _write_approved_inputs(tmp_path / "run-first")
    plan = create_setup_plan(
        "RUN-20260803-013",
        paths["definition_path"],
        paths["profile_path"],
        paths["domain_pack_path"],
        paths["template_path"],
        paths["template_manifest_path"],
    )
    assert plan["run_id"] == "RUN-20260803-013"
