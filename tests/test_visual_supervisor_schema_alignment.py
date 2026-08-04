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
