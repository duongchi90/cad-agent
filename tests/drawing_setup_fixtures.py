from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

from cad_agent.drawing_contracts import canonical_json_sha256
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
    return {
        "schema_version": "drawing-profile-1.0",
        "id": "SYNTHETIC_A1",
        "revision": "1.0",
        "status": "APPROVED",
        "supported_domains": ["AUTOMOTIVE_CONVERSION"],
        "supported_drawing_types": ["GENERAL_ARRANGEMENT"],
        "model": {"unit": "mm", "scale": "1:1", "ucs": "WORLD"},
        "setup_expectations": {
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
                "new_drawing": {"approved_fonts": ["Arial.ttf"], "substitution_allowed": False},
                "legacy_compatibility": {
                    "preserve_source_styles": True,
                    "mapping_report_required": True,
                },
            },
        },
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
        "vocabulary": ["CHASSIS", "CABIN", "CARGO_BODY", "SPECIAL_EQUIPMENT"],
        "approval": {"reference": "SYNTHETIC-DOMAIN-001", "approved_by": "ENGINEER"},
    }


def approved_template_manifest(*, file_sha256: str) -> dict[str, object]:
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
    profile = approved_profile()
    domain_pack = approved_domain_pack()
    return {
        "schema_version": "drawing-setup-plan-1.0",
        "run_id": "RUN-20260802-001",
        "state": "SETUP_PENDING",
        "definition": {
            "id": approved_definition()["id"],
            "sha256": canonical_json_sha256(approved_definition()),
        },
        "drawing_profile": {
            "id": profile["id"],
            "revision": profile["revision"],
            "sha256": canonical_json_sha256(profile),
        },
        "domain_pack": {
            "id": domain_pack["id"],
            "revision": domain_pack["revision"],
            "sha256": canonical_json_sha256(domain_pack),
        },
        "template": {
            "id": "VX_MECHANICAL_2027_TEMPLATE",
            "revision": "1.0",
            "file_sha256": "a" * 64,
            "embedded_settings_sha256": canonical_json_sha256(profile["setup_expectations"]),
        },
        "setup_expectations": profile["setup_expectations"],
    }


def matching_setup_audit(plan: dict[str, object]) -> dict[str, object]:
    expectations = plan["setup_expectations"]
    return {
        "schema_version": "drawing-setup-audit-1.0",
        "drawing_full_path": r"C:\temp\setup-lite.dwg",
        "drawing_sha256": "b" * 64,
        "changed": False,
        "dbmod_before": 0,
        "dbmod_after": 0,
        "variables": copy.deepcopy(expectations["variables"]),
        "current_layer": expectations["current_layer"],
        "custom_properties": {
            "CAD_AGENT_SETTINGS_SHA256": plan["template"]["embedded_settings_sha256"]
        },
        "layers": copy.deepcopy(expectations["required_layers"]),
        "styles": copy.deepcopy(expectations["required_styles"]),
        "layouts": copy.deepcopy(expectations["layouts"]),
        "font_report": {"missing": [], "substituted": []},
    }


def matching_setup_ipc_result(
    plan: dict[str, object], drawing_full_path: str
) -> dict[str, object]:
    payload = copy.deepcopy(matching_setup_audit(plan))
    for field in ("schema_version", "drawing_full_path", "drawing_sha256"):
        payload.pop(field)
    return {
        "request_id": "setup-lite-001",
        "success": True,
        "operation": "drawing_setup_audit",
        "drawing_full_path": drawing_full_path,
        "changed": False,
        "entity_handles": [],
        "warnings": [],
        "errors": [],
        "started_at": "2026-08-03T02:00:00Z",
        "completed_at": "2026-08-03T02:00:00Z",
        "payload": payload,
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
