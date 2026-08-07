from __future__ import annotations

import hashlib
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


VALIDATOR_VERSION = "vision-handoff-validator-1.0"
SCHEMA_ID = "repair-plan"
SCHEMA_VERSION = "repair-plan-1.0"
NOW = datetime(2026, 8, 7, 5, 0, tzinfo=timezone.utc)


def _module():
    try:
        return importlib.import_module("cad_agent.vision_handoff")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Task 1 production boundary is missing: {exc}")


def _schema_document(*, extra: object | None = None) -> dict[str, object]:
    document: dict[str, object] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://cad-agent.local/contracts/repair-plan.schema.json",
        "title": "Disposable repair-plan output",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version"],
        "properties": {"schema_version": {"const": SCHEMA_VERSION}},
    }
    if extra is not None:
        document["extra"] = extra
    return document


def _write_schema(path: Path, document: dict[str, object] | None = None) -> Path:
    path.write_text(json.dumps(document or _schema_document(), ensure_ascii=False), encoding="utf-8")
    return path


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )


def _base_payload() -> dict[str, Any]:
    return {
        "schema_version": "vision-handoff-1.0",
        "handoff_id": "HANDOFF-001",
        "program_id": "PROGRAM-001",
        "run_id": "RUN-001",
        "request_id": "REQUEST-001",
        "created_at": "2026-08-07T04:00:00Z",
        "expires_at": "2026-08-07T06:00:00Z",
        "single_use": True,
        "consumed": False,
        "source": {
            "role": "approved_reference",
            "identity": "synthetic-source-001",
            "sha256": "1" * 64,
            "byte_length": 128,
            "revision": "source-rev-001",
            "immutable": True,
        },
        "accepted_base": {
            "role": "accepted_main",
            "identity": "abcd1453033c6e40378069d4de9fcc4c060110f3",
            "sha256": "2" * 64,
            "byte_length": 40,
            "revision": "main",
            "immutable": True,
        },
        "scope": {
            "components": ["component-001"],
            "views": ["view-front"],
            "regions": ["region-001"],
            "sheets": ["sheet-001"],
            "entities": ["entity-001"],
        },
        "owner_intent": "Produce a bounded advisory vision result.",
        "engineering_objective": "Preserve protected CAD constraints.",
        "dimensions": {
            "confirmed": ["dimension-001"],
            "reference": ["dimension-002"],
            "derived": [],
            "conflicting": [],
            "unresolved": [],
        },
        "protected_constraints": {
            "datums": ["datum-001"],
            "geometry": ["geometry-001"],
            "dimensions": ["dimension-001"],
            "constraints": ["constraint-001"],
            "layers": ["layer-001"],
            "blocks": ["block-001"],
            "handles": ["handle-001"],
        },
        "allowed_operations": ["READ_ONLY_VISION_ANALYSIS"],
        "forbidden_mutations": ["CAD_MUTATION", "REPAIR_APPLICATION", "PUBLICATION"],
        "workspace": {
            "roots": ["C:/disposable/vision-run-001"],
            "write_policy": "DISPOSABLE_ONLY",
        },
        "required_verification_gates": ["IDENTITY", "SCOPE", "SCHEMA_BINDING"],
        "approval_reference": "APPROVAL-001",
        "approval_authority": "OWNER",
        "instruction_sources": [
            {"source_id": "system", "role": "system", "sha256": "3" * 64},
            {"source_id": "project", "role": "project", "sha256": "4" * 64},
        ],
        "provider_policy": {
            "approval_mode": "deny_all",
            "experimental_api": False,
            "model_identity": "fake-disposable-model",
            "config_sha256": "5" * 64,
        },
    }


def _bind(path: Path, payload: dict[str, Any] | None = None, **kwargs: object):
    module = _module()
    source = payload or _base_payload()
    kwargs.setdefault("authority_context", _authority_context(source))
    return module.bind_vision_handoff(
        source,
        schema_path=path,
        schema_id=SCHEMA_ID,
        schema_version=SCHEMA_VERSION,
        validator_version=VALIDATOR_VERSION,
        now=NOW,
        **kwargs,
    )


def _authority_context(payload: dict[str, Any] | None = None):
    module = _module()
    source = payload or _base_payload()
    return module.ServerOwnedAuthorityContext(
        handoff_id=source["handoff_id"],
        program_id=source["program_id"],
        run_id=source["run_id"],
        request_id=source["request_id"],
        source=source["source"],
        accepted_base=source["accepted_base"],
        scope=source["scope"],
        protected_constraints=source["protected_constraints"],
        instruction_sources=tuple(source["instruction_sources"]),
        approval_reference=source["approval_reference"],
        approval_authority=source["approval_authority"],
        workspace=source["workspace"],
        allowed_operations=tuple(source["allowed_operations"]),
        forbidden_mutations=tuple(source["forbidden_mutations"]),
        required_verification_gates=tuple(source["required_verification_gates"]),
        provider_policy=source["provider_policy"],
    )


def test_valid_handoff_returns_immutable_canonical_identity(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)

    assert type(handoff).__name__ == "ValidatedVisionHandoff"
    assert handoff.payload["output_schema_id"] == SCHEMA_ID
    assert handoff.payload["output_schema_version"] == SCHEMA_VERSION
    assert handoff.payload["output_validator_version"] == VALIDATOR_VERSION
    assert handoff.payload["output_schema_sha256"] == hashlib.sha256(
        _canonical_bytes(_schema_document())
    ).hexdigest()
    assert handoff.payload["handoff_sha256"] == hashlib.sha256(handoff.canonical_bytes).hexdigest()
    assert handoff.schema_snapshot.canonical_bytes == _canonical_bytes(_schema_document())


@pytest.mark.parametrize("missing", ["handoff_id", "program_id", "run_id", "request_id", "source", "accepted_base"])
def test_handoff_rejects_missing_or_foreign_identity(tmp_path: Path, missing: str) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    payload = _base_payload()
    payload.pop(missing)
    with pytest.raises(ValueError, match=missing):
        module = _module()
        module.bind_vision_handoff(
            payload,
            schema_path=schema_path,
            schema_id=SCHEMA_ID,
            schema_version=SCHEMA_VERSION,
            validator_version=VALIDATOR_VERSION,
            authority_context=_authority_context(),
            now=NOW,
        )

    payload = _base_payload()
    with pytest.raises(ValueError, match="identity"):
        foreign_context = _authority_context()
        foreign_context = type(foreign_context)(
            **{
                field: ("FOREIGN-PROGRAM" if field == "program_id" else getattr(foreign_context, field))
                for field in foreign_context.__dataclass_fields__
            }
        )
        _bind(schema_path, payload, authority_context=foreign_context)


def test_scope_widening_is_rejected(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    payload = _base_payload()
    payload["scope"]["regions"].append("region-foreign")
    with pytest.raises(ValueError, match="scope"):
        _bind(schema_path, payload, authority_context=_authority_context())


def test_protected_constraint_widening_is_rejected(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    payload = _base_payload()
    payload["protected_constraints"]["handles"].append("handle-foreign")
    with pytest.raises(ValueError, match="protected"):
        _bind(
            schema_path,
            payload,
            authority_context=_authority_context(),
        )


@pytest.mark.parametrize(
    ("payload_change", "message"),
    [
        ({"expires_at": "2026-08-07T04:59:59Z"}, "expired"),
        ({"consumed": True}, "consumed"),
        ({"single_use": False}, "single_use"),
    ],
)
def test_stale_expired_or_reused_handoff_fails_closed(
    tmp_path: Path, payload_change: dict[str, object], message: str
) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    payload = _base_payload()
    payload.update(payload_change)
    with pytest.raises(ValueError, match=message):
        _bind(schema_path, payload)

    if message == "consumed":
        payload = _base_payload()
        with pytest.raises(ValueError, match="reused"):
            _bind(schema_path, payload, consumed_handoff_ids={payload["handoff_id"]})


def test_changed_instruction_source_identity_is_rejected(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    payload = _base_payload()
    payload["instruction_sources"][0]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="instruction"):
        _bind(schema_path, payload, authority_context=_authority_context())


@pytest.mark.parametrize(
    "forbidden",
    ["cad_truth_authority", "codex_approval", "autocad_mutation", "repair_application", "publication"],
)
def test_codex_cannot_receive_engineering_or_publication_authority(tmp_path: Path, forbidden: str) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    payload = _base_payload()
    payload[forbidden] = True
    with pytest.raises(ValueError, match="forbidden|authority"):
        _bind(schema_path, payload)


def test_noncanonical_or_nonfinite_handoff_is_rejected(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    payload = _base_payload()
    payload["engineering_objective"] = float("nan")
    with pytest.raises(ValueError, match="canonical|finite"):
        _bind(schema_path, payload)


def test_bind_requires_a_complete_server_owned_authority_context(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    with pytest.raises((TypeError, ValueError), match="authority_context|authority context|server-owned"):
        module.bind_vision_handoff(
            _base_payload(),
            schema_path=schema_path,
            schema_id=SCHEMA_ID,
            schema_version=SCHEMA_VERSION,
            validator_version=VALIDATOR_VERSION,
            now=NOW,
        )


def test_validate_requires_a_complete_server_owned_authority_context(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    with pytest.raises((TypeError, ValueError), match="authority_context|authority context|server-owned"):
        module.validate_vision_handoff(
            handoff.payload,
            schema_path=schema_path,
            schema_id=SCHEMA_ID,
            schema_version=SCHEMA_VERSION,
            validator_version=VALIDATOR_VERSION,
            now=NOW,
        )


def test_partial_authority_context_is_rejected(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    with pytest.raises(ValueError, match="complete|ServerOwnedAuthorityContext"):
        module.bind_vision_handoff(
            _base_payload(),
            schema_path=schema_path,
            schema_id=SCHEMA_ID,
            schema_version=SCHEMA_VERSION,
            validator_version=VALIDATOR_VERSION,
            authority_context={"handoff_id": "HANDOFF-001"},
            now=NOW,
        )


def test_naive_now_is_rejected_by_bind_and_validate(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    naive_now = datetime(2026, 8, 7, 5, 0)
    with pytest.raises(ValueError, match="timezone|aware"):
        module.bind_vision_handoff(
            _base_payload(),
            schema_path=schema_path,
            schema_id=SCHEMA_ID,
            schema_version=SCHEMA_VERSION,
            validator_version=VALIDATOR_VERSION,
            authority_context=_authority_context(),
            now=naive_now,
        )

    handoff = _bind(schema_path)
    with pytest.raises(ValueError, match="timezone|aware"):
        module.validate_vision_handoff(
            handoff.payload,
            schema_path=schema_path,
            schema_id=SCHEMA_ID,
            schema_version=SCHEMA_VERSION,
            validator_version=VALIDATOR_VERSION,
            authority_context=_authority_context(),
            now=naive_now,
        )
