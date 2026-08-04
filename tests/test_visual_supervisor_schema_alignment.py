from __future__ import annotations

import json
from pathlib import Path

from cad_agent.visual_contracts import validate_visual_contract


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
