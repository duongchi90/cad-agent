from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from tests.test_vision_handoff import _authority_context, _bind, _base_payload, _write_schema


def _module():
    try:
        return importlib.import_module("cad_agent.vision_handoff")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Task 1 production boundary is missing: {exc}")


def test_contract_rejects_unknown_root_fields(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["unexpected"] = "caller-controlled"
    with pytest.raises(ValueError, match="Unexpected|unknown|closed"):
        _bind(_write_schema(tmp_path / "schema.json"), payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("output_schema_id", "foreign-schema"),
        ("output_schema_version", "foreign-version"),
        ("output_schema_sha256", "f" * 64),
        ("output_validator_version", "foreign-validator"),
        ("handoff_sha256", "f" * 64),
    ],
)
def test_server_owned_identity_fields_cannot_be_caller_selected(
    tmp_path: Path, field: str, value: object
) -> None:
    payload = _base_payload()
    payload[field] = value
    with pytest.raises(ValueError, match="server-owned|binding|hash|identity"):
        _bind(_write_schema(tmp_path / "schema.json"), payload)


def test_required_schema_binding_metadata_is_present_and_exact(tmp_path: Path) -> None:
    handoff = _bind(_write_schema(tmp_path / "schema.json"))
    for field in (
        "output_schema_id",
        "output_schema_version",
        "output_schema_sha256",
        "output_validator_version",
        "handoff_sha256",
    ):
        assert field in handoff.payload


def test_binding_rejects_changed_provider_schema_bytes(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    module = _module()
    changed = schema_path.read_bytes() + b"\n"
    with pytest.raises(ValueError, match="schema|snapshot|TOCTOU"):
        module.validate_output_schema_binding(
            handoff,
            schema_path=schema_path,
            schema_bytes=changed,
            schema_id="repair-plan",
            schema_version="repair-plan-1.0",
            validator_version="vision-handoff-validator-1.0",
        )


@pytest.mark.parametrize(
    ("group", "field", "value"),
    [
        ("identity", "handoff_id", "FOREIGN-HANDOFF"),
        ("source", "source", {"role": "foreign"}),
        ("accepted_base", "accepted_base", {"role": "foreign"}),
        ("scope", "scope", {"components": ["foreign"]}),
        ("protected", "protected_constraints", {"handles": ["foreign"]}),
        ("instruction", "instruction_sources", [{"source_id": "foreign"}]),
        ("approval", "approval_reference", "FOREIGN-APPROVAL"),
        ("workspace", "workspace", {"roots": ["C:/foreign"], "write_policy": "DISPOSABLE_ONLY"}),
        ("allowed_operations", "allowed_operations", ["FOREIGN_OPERATION"]),
        ("forbidden_mutations", "forbidden_mutations", ["FOREIGN_MUTATION"]),
        ("required_verification_gates", "required_verification_gates", ["FOREIGN_GATE"]),
        (
            "provider",
            "provider_policy",
            {
                "approval_mode": "deny_all",
                "experimental_api": False,
                "model_identity": "foreign-model",
                "config_sha256": "f" * 64,
            },
        ),
    ],
)
def test_every_authority_group_mismatch_fails_closed(
    tmp_path: Path, group: str, field: str, value: object
) -> None:
    payload = _base_payload()
    payload[field] = value
    with pytest.raises(ValueError, match=group):
        _bind(
            _write_schema(tmp_path / "schema.json"),
            payload,
            authority_context=_authority_context(),
        )


def test_validate_compares_every_authority_group_against_context(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    expected_payload = _base_payload()
    expected_context = _authority_context(expected_payload)
    handoff = _bind(schema_path, authority_context=expected_context)
    foreign_payload = _base_payload()
    foreign_payload["provider_policy"]["model_identity"] = "foreign-model"
    foreign_context = _authority_context(foreign_payload)
    with pytest.raises(ValueError, match="provider"):
        module.validate_vision_handoff(
            handoff.payload,
            schema_path=schema_path,
            schema_id="repair-plan",
            schema_version="repair-plan-1.0",
            validator_version="vision-handoff-validator-1.0",
            authority_context=foreign_context,
        )
