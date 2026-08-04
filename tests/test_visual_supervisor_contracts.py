from __future__ import annotations

import json
from pathlib import Path

import pytest

from cad_agent.visual_contracts import (
    VisualContractError,
    read_visual_contract,
    validate_visual_contract,
)
from tests.visual_supervisor_fixtures import valid_dimension_register, valid_visual_run_manifest


def test_visual_run_manifest_validates_and_is_deep_copied() -> None:
    source = valid_visual_run_manifest()
    validated = validate_visual_contract(source, contract="visual_run_manifest")
    assert validated == source
    source["state"] = "MUTATED_BY_CALLER"
    assert validated["state"] == "CREATED"


def test_visual_run_manifest_rejects_unknown_state() -> None:
    payload = valid_visual_run_manifest()
    payload["state"] = "DONE_ENOUGH"
    with pytest.raises(VisualContractError, match="state"):
        validate_visual_contract(payload, contract="visual_run_manifest")


def test_visual_run_manifest_rejects_unexpected_property() -> None:
    payload = valid_visual_run_manifest()
    payload["codex_says_ok"] = True
    with pytest.raises(VisualContractError, match="Unexpected properties"):
        validate_visual_contract(payload, contract="visual_run_manifest")


def test_read_visual_contract_rejects_non_object_root(tmp_path: Path) -> None:
    source = tmp_path / "manifest.json"
    source.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    with pytest.raises(VisualContractError, match="root must be an object"):
        read_visual_contract(source, contract="visual_run_manifest")


def test_confirmed_driving_dimension_requires_both_attachments() -> None:
    payload = valid_dimension_register()
    del payload["dimensions"][0]["to_ref"]
    with pytest.raises(VisualContractError, match="to_ref"):
        validate_visual_contract(payload, contract="dimension_register")


def test_unresolved_critical_dimension_requires_blocker_scope() -> None:
    payload = valid_dimension_register()
    dimension = payload["dimensions"][0]
    dimension["role"] = "AMBIGUOUS"
    dimension["status"] = "UNRESOLVED"
    dimension["blocker_scope"] = []
    payload["summary"] = {"confirmed": 0, "unresolved": 1, "conflicts": 0}
    with pytest.raises(VisualContractError, match="blocker_scope"):
        validate_visual_contract(payload, contract="dimension_register")
