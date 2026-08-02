from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from cad_agent.drawing_contracts import DrawingContractError, canonical_json_sha256, read_contract

from drawing_setup_fixtures import (
    approved_definition,
    approved_domain_pack,
    approved_profile,
    approved_setup_plan,
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


def assert_schema_accepts(schema: dict[str, object], value: object, path: str = "$") -> None:
    for clause in schema.get("allOf", []):
        condition = clause.get("if", {})
        condition_properties = condition.get("properties", {})
        matches = all(
            value.get(key) == rule.get("const")
            for key, rule in condition_properties.items()
        ) if isinstance(value, dict) else False
        if matches and "then" in clause:
            assert_schema_accepts(clause["then"], value, path)
    if "const" in schema:
        assert value == schema["const"], path
    if "enum" in schema:
        assert value in schema["enum"], path
    schema_type = schema.get("type")
    if schema_type == "object":
        assert isinstance(value, dict), path
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        assert not missing, f"{path}: missing {missing}"
        properties = schema.get("properties", {}) or {}
        additional = schema.get("additionalProperties", True)
        if additional is False:
            unknown = set(value) - set(properties)
            assert not unknown, f"{path}: unknown {sorted(unknown)}"
        for key, item in value.items():
            if key in properties:
                assert_schema_accepts(properties[key], item, f"{path}.{key}")
            elif isinstance(additional, dict):
                assert_schema_accepts(additional, item, f"{path}.{key}")
    elif schema_type == "array":
        assert isinstance(value, list), path
        if "minItems" in schema:
            assert len(value) >= schema["minItems"], path
        if "maxItems" in schema:
            assert len(value) <= schema["maxItems"], path
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                assert_schema_accepts(schema["items"], item, f"{path}[{index}]")
    elif schema_type == "string":
        assert isinstance(value, str), path
        if "minLength" in schema:
            assert len(value) >= schema["minLength"], path
        if "pattern" in schema:
            assert re.search(schema["pattern"], value), path
    elif schema_type == "number":
        assert isinstance(value, (int, float)) and not isinstance(value, bool), path
        assert math.isfinite(value), path
    elif schema_type == "integer":
        assert isinstance(value, int) and not isinstance(value, bool), path
    elif schema_type == "boolean":
        assert isinstance(value, bool), path
    if "exclusiveMinimum" in schema:
        assert value > schema["exclusiveMinimum"], path


def test_schema_examples_match_their_closed_contracts() -> None:
    for filename in sorted(CONTRACTS):
        schema_path = ROOT / "contracts" / "drawing-setup" / filename.replace(
            ".json", ".schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        payload = json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))
        assert_schema_accepts(schema, payload, path=filename)


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


def test_verified_evidence_cannot_have_blockers(tmp_path: Path) -> None:
    payload = json.loads((EXAMPLES / "drawing-setup-evidence.json").read_text(encoding="utf-8"))
    payload["status"] = "SETUP_VERIFIED"
    path = tmp_path / "verified-evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DrawingContractError, match="SETUP_VERIFIED"):
        read_contract(path, contract="drawing_setup_evidence")

    schema = json.loads(
        (ROOT / "contracts" / "drawing-setup" / "drawing-setup-evidence.schema.json").read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(AssertionError):
        assert_schema_accepts(schema, payload, path="drawing-setup-evidence.json")


def test_ids_extensions_and_finite_numbers_are_strict(tmp_path: Path) -> None:
    plan = approved_setup_plan()
    plan["run_id"] = "RUN WITH SPACE"
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(DrawingContractError, match="run_id"):
        read_contract(path, contract="drawing_setup_plan")

    evidence = json.loads((EXAMPLES / "drawing-setup-evidence.json").read_text(encoding="utf-8"))
    evidence["run_id"] = "RUN WITH SPACE"
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(DrawingContractError, match="run_id"):
        read_contract(path, contract="drawing_setup_evidence")

    template = approved_template_manifest(file_sha256="a" * 64)
    template["file_name"] = "template.DWT"
    path = tmp_path / "template-uppercase.json"
    path.write_text(json.dumps(template), encoding="utf-8")
    assert read_contract(path, contract="template_manifest")["file_name"] == "template.DWT"

    with pytest.raises(ValueError, match="finite"):
        canonical_json_sha256({"value": float("nan")})
