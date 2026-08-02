from __future__ import annotations

import json
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import DrawingContractError, canonical_json_sha256, read_contract

from drawing_setup_fixtures import (
    approved_definition,
    approved_domain_pack,
    approved_profile,
    approved_template_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "contracts" / "drawing-setup" / "examples"

CONTRACTS = {
    "drawing-definition.json": "drawing_definition",
    "drawing-profile.json": "drawing_profile",
    "domain-pack.json": "domain_pack",
    "template-manifest.json": "template_manifest",
    "drawing-setup-plan.json": "drawing_setup_plan",
    "drawing-setup-audit.json": "drawing_setup_audit",
    "drawing-setup-evidence.json": "drawing_setup_evidence",
}


@pytest.mark.parametrize(("filename", "contract"), sorted(CONTRACTS.items()))
def test_example_contracts_validate_and_hash_deterministically(filename: str, contract: str) -> None:
    payload = read_contract(EXAMPLES / filename, contract=contract)
    first = canonical_json_sha256(payload)
    second = canonical_json_sha256(dict(reversed(list(payload.items()))))
    assert first == second
    assert len(first) == 64


def test_unapproved_profile_and_unknown_property_fail_closed(tmp_path: Path) -> None:
    payload = json.loads((EXAMPLES / "drawing-profile.json").read_text(encoding="utf-8"))
    payload["status"] = "DRAFT"
    payload["unexpected"] = True
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DrawingContractError, match="Unexpected|APPROVED"):
        read_contract(path, contract="drawing_profile")


def test_missing_required_property_fails_closed(tmp_path: Path) -> None:
    payload = approved_definition()
    del payload["approval"]
    path = tmp_path / "definition.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DrawingContractError, match="missing required properties"):
        read_contract(path, contract="drawing_definition")


def test_wrong_schema_version_fails_closed(tmp_path: Path) -> None:
    payload = approved_domain_pack()
    payload["schema_version"] = "domain-pack-0.9"
    path = tmp_path / "domain.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DrawingContractError, match="schema_version"):
        read_contract(path, contract="domain_pack")


def test_font_policy_requires_both_modes(tmp_path: Path) -> None:
    payload = approved_profile()
    del payload["setup_expectations"]["font_policy"]["legacy_compatibility"]
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DrawingContractError, match="legacy_compatibility"):
        read_contract(path, contract="drawing_profile")


def test_legacy_font_mode_is_explicitly_valid(tmp_path: Path) -> None:
    payload = approved_profile()
    payload["setup_expectations"]["font_policy"]["selected_mode"] = "LEGACY_COMPATIBILITY"
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert read_contract(path, contract="drawing_profile")["setup_expectations"]["font_policy"]["selected_mode"] == "LEGACY_COMPATIBILITY"


def test_schema_roots_are_closed() -> None:
    for path in sorted((ROOT / "contracts" / "drawing-setup").glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False


def test_empty_identifier_and_invalid_template_are_rejected(tmp_path: Path) -> None:
    definition = approved_definition()
    definition["id"] = ""
    path = tmp_path / "definition.json"
    path.write_text(json.dumps(definition), encoding="utf-8")
    with pytest.raises(DrawingContractError, match="id"):
        read_contract(path, contract="drawing_definition")

    template = approved_template_manifest(file_sha256="a" * 64)
    template["file_name"] = "template.dwg"
    path = tmp_path / "template.json"
    path.write_text(json.dumps(template), encoding="utf-8")
    with pytest.raises(DrawingContractError, match="file_name"):
        read_contract(path, contract="template_manifest")
