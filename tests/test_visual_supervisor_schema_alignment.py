from __future__ import annotations

import json
import math
from pathlib import Path
import re

from cad_agent.visual_contracts import validate_visual_contract
from tests.visual_supervisor_fixtures import valid_dimension_observer_evidence, valid_dimension_register


def _assert_json_schema_accepts(schema: dict[str, object], value: object, path: str = "$") -> None:
    for clause in schema.get("allOf", []):
        condition = clause.get("if", {})
        condition_properties = condition.get("properties", {})
        if isinstance(value, dict) and all(
            value.get(key) == rule.get("const") for key, rule in condition_properties.items()
        ):
            _assert_json_schema_accepts(clause["then"], value, path)
    if "const" in schema:
        assert value == schema["const"], path
    if "enum" in schema:
        assert value in schema["enum"], path
    if "anyOf" in schema:
        assert any(
            _schema_accepts(branch, value, path) for branch in schema["anyOf"]
        ), path
        return
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        if value is None and "null" in schema_type:
            return
        schema_type = next(item for item in schema_type if item != "null")
    if schema_type == "object":
        assert isinstance(value, dict), path
        assert not [key for key in schema.get("required", []) if key not in value], path
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            assert not set(value) - set(properties), path
        for key, item in value.items():
            if key in properties:
                _assert_json_schema_accepts(properties[key], item, f"{path}.{key}")
    elif schema_type == "array":
        assert isinstance(value, list), path
        if "minItems" in schema:
            assert len(value) >= schema["minItems"], path
        if "maxItems" in schema:
            assert len(value) <= schema["maxItems"], path
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                _assert_json_schema_accepts(schema["items"], item, f"{path}[{index}]")
    elif schema_type == "string":
        assert isinstance(value, str), path
        if "minLength" in schema:
            assert len(value) >= schema["minLength"], path
        if "pattern" in schema:
            assert re.fullmatch(schema["pattern"], value), path
    elif schema_type == "number":
        assert isinstance(value, (int, float)) and not isinstance(value, bool), path
        assert math.isfinite(value), path
    elif schema_type == "integer":
        assert isinstance(value, int) and not isinstance(value, bool), path
    elif schema_type == "boolean":
        assert isinstance(value, bool), path


def _schema_accepts(schema: dict[str, object], value: object, path: str) -> bool:
    try:
        _assert_json_schema_accepts(schema, value, path)
    except AssertionError:
        return False
    return True


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
        contract = example_path.stem.replace("-", "_")
        assert validate_visual_contract(payload, contract=contract) == payload


def test_runtime_dimension_evidence_matches_python_and_json_schema() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "contracts" / "visual-supervisor" / "dimension-register.schema.json").read_text(
            encoding="utf-8"
        )
    )
    payload = valid_dimension_register()
    payload["dimensions"][0].update(valid_dimension_observer_evidence())
    payload["dimensions"][0]["ocr_evidence"] = [{
        "id": "rawtext-4500-rot0",
        "content": "4500",
        "bbox": [20.0, 15.0, 100.0, 55.0],
        "rotation_deg": 0.0,
        "confidence": 0.99,
        "source": "text_tesseract",
    }]
    payload["dimensions"][0]["extension_geometry"]["leader_lines"] = []
    payload["dimensions"][0]["provenance"]["ocr_rotations_deg"] = [0.0, 90.0, -90.0]

    validated = validate_visual_contract(payload, contract="dimension_register")
    _assert_json_schema_accepts(schema, validated, path="dimension-register")


def test_visual_run_manifest_schema_closes_nested_objects() -> None:
    root = Path(__file__).resolve().parents[1]
    schema_path = root / "contracts" / "visual-supervisor" / "visual-run-manifest.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["properties"]["source"]["additionalProperties"] is False
    assert schema["properties"]["drawing"]["additionalProperties"] is False


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


def _walk_schema_nodes(value: object, path: str = "schema") -> list[tuple[str, dict[str, object]]]:
    nodes: list[tuple[str, dict[str, object]]] = []
    if isinstance(value, dict):
        nodes.append((path, value))
        for key, nested in value.items():
            nodes.extend(_walk_schema_nodes(nested, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            nodes.extend(_walk_schema_nodes(nested, f"{path}[{index}]"))
    return nodes


def test_every_visual_schema_object_boundary_is_closed_recursively() -> None:
    root = Path(__file__).resolve().parents[1] / "contracts" / "visual-supervisor"
    for schema_path in sorted(root.glob("*.schema.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        for path, node in _walk_schema_nodes(schema, schema_path.name):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, path


def _mutate_nested(value: object) -> bool:
    if isinstance(value, dict):
        for nested in value.values():
            if isinstance(nested, list):
                nested.append("MUTATED_AFTER_VALIDATION")
                return True
            if isinstance(nested, dict) and _mutate_nested(nested):
                return True
    return False


def test_validation_deep_copies_every_visual_example() -> None:
    root = Path(__file__).resolve().parents[1]
    example_root = root / "contracts" / "visual-supervisor" / "examples"
    for example_path in sorted(example_root.glob("*.json")):
        payload = json.loads(example_path.read_text(encoding="utf-8"))
        validated = validate_visual_contract(payload, contract=example_path.stem.replace("-", "_"))
        if not _mutate_nested(validated):
            validated["status"] = "MUTATED_AFTER_VALIDATION"
        assert validated != payload
