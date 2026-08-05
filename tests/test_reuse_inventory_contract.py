from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

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


def test_validator_returns_a_deep_copy() -> None:
    module = _module()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    validated = module.validate_inventory(payload)
    validated["capabilities"][0]["current_paths"].append("contracts/new.py")
    assert "contracts/new.py" not in payload["capabilities"][0]["current_paths"]


def test_invalid_classification_is_rejected() -> None:
    module = _module()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["capabilities"][0]["classification"] = "UNKNOWN"
    with pytest.raises(ValueError, match="classification"):
        module.validate_inventory(payload)


def test_capability_id_must_be_a_lowercase_identifier() -> None:
    module = _module()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["capabilities"][0]["capability_id"] = "Primitive IR"
    with pytest.raises(ValueError, match="capability_id"):
        module.validate_inventory(payload)


def test_base_sha_must_be_a_lowercase_git_sha() -> None:
    module = _module()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["base_sha"] = "A" * 40
    with pytest.raises(ValueError, match="base_sha"):
        module.validate_inventory(payload)


def test_repository_paths_are_checked() -> None:
    module = _module()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["capabilities"][0]["current_paths"] = ["missing.py"]
    with pytest.raises(ValueError, match="does not exist"):
        module.validate_against_repository(payload, ROOT)


def test_external_repository_paths_are_allowed() -> None:
    module = _module()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["capabilities"][0]["inspected_paths"] = ["external:approved-private-drawing"]
    module.validate_against_repository(payload, ROOT)


def test_cli_checks_the_example_inventory() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "check",
            str(EXAMPLE),
            "--repo-root",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert str(EXAMPLE.resolve()) in result.stdout
