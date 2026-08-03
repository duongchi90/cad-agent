from __future__ import annotations

import json
from pathlib import Path


CONTRACT_ROOT = Path(__file__).resolve().parents[2] / "contracts" / "dimension-first"


def test_m3_schema_files_are_closed_and_versioned() -> None:
    expected = {
        "dimension-observation.schema.json",
        "datum.schema.json",
        "constraint.schema.json",
        "approval-register.schema.json",
        "constraint-report.schema.json",
        "solved-drawing-model.schema.json",
    }
    paths = {path.name for path in CONTRACT_ROOT.glob("*.schema.json")}
    assert paths == expected
    for path in sorted(CONTRACT_ROOT.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert "schema_version" in schema["required"]


def test_m3_examples_are_fixture_objects_with_expected_schema_versions() -> None:
    examples = sorted((CONTRACT_ROOT / "examples").glob("*.json"))
    assert len(examples) == 6
    for path in examples:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        assert payload["schema_version"].endswith("-1.0")
        serialized = path.read_text(encoding="utf-8")
        assert "C:\\Users\\" not in serialized
        assert "px" not in serialized

