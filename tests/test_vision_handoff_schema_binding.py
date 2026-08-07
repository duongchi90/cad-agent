from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from tests.test_vision_handoff import (
    SCHEMA_ID,
    SCHEMA_VERSION,
    VALIDATOR_VERSION,
    _bind,
    _canonical_bytes,
    _schema_document,
    _write_schema,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "vision-handoff" / "vision-handoff.schema.json"


def test_vision_handoff_schema_is_closed_and_declares_server_owned_binding() -> None:
    assert SCHEMA_PATH.is_file()
    document = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert document["type"] == "object"
    assert document["additionalProperties"] is False
    required = set(document["required"])
    assert {
        "handoff_id",
        "program_id",
        "run_id",
        "request_id",
        "scope",
        "protected_constraints",
        "output_schema_id",
        "output_schema_version",
        "output_schema_sha256",
        "output_validator_version",
        "handoff_sha256",
    } <= required


def test_schema_canonicalization_is_stable_and_hash_bound(tmp_path: Path) -> None:
    first = {"b": 2, "a": 1}
    second = {"a": 1, "b": 2}
    first_path = _write_schema(tmp_path / "first.json", first)
    second_path = _write_schema(tmp_path / "second.json", second)
    first_handoff = _bind(first_path)
    second_handoff = _bind(second_path)
    assert first_handoff.schema_snapshot.sha256 == second_handoff.schema_snapshot.sha256
    assert first_handoff.schema_snapshot.canonical_bytes == _canonical_bytes(second)
    assert first_handoff.payload["output_schema_sha256"] == hashlib.sha256(_canonical_bytes(first)).hexdigest()


def test_schema_path_replacement_is_rejected_even_when_identity_fields_match(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    replacement = _write_schema(tmp_path / "replacement.json")
    schema_path.unlink()
    replacement.replace(schema_path)
    module = __import__("cad_agent.vision_handoff", fromlist=["validate_output_schema_binding"])
    with pytest.raises(ValueError, match="replaced|identity|snapshot|schema"):
        module.validate_output_schema_binding(
            handoff,
            schema_path=schema_path,
            schema_bytes=handoff.schema_snapshot.raw_bytes,
            schema_id=SCHEMA_ID,
            schema_version=SCHEMA_VERSION,
            validator_version=VALIDATOR_VERSION,
        )


def test_schema_raw_reordering_is_rejected_as_snapshot_change(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json", {"b": 2, "a": 1})
    handoff = _bind(schema_path)
    schema_path.write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")
    module = __import__("cad_agent.vision_handoff", fromlist=["validate_output_schema_binding"])
    with pytest.raises(ValueError, match="changed|snapshot|schema"):
        module.validate_output_schema_binding(
            handoff,
            schema_path=schema_path,
            schema_bytes=handoff.schema_snapshot.raw_bytes,
            schema_id=SCHEMA_ID,
            schema_version=SCHEMA_VERSION,
            validator_version=VALIDATOR_VERSION,
        )


def test_validator_version_drift_is_rejected(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    module = __import__("cad_agent.vision_handoff", fromlist=["validate_output_schema_binding"])
    with pytest.raises(ValueError, match="validator"):
        module.validate_output_schema_binding(
            handoff,
            schema_path=schema_path,
            schema_bytes=handoff.schema_snapshot.raw_bytes,
            schema_id=SCHEMA_ID,
            schema_version=SCHEMA_VERSION,
            validator_version="vision-handoff-validator-foreign",
        )


def test_toc_tou_mutation_between_provider_snapshot_and_local_validation_fails_closed(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    provider_bytes = handoff.schema_snapshot.raw_bytes
    schema_path.write_text(json.dumps(_schema_document(extra="mutated")), encoding="utf-8")
    module = __import__("cad_agent.vision_handoff", fromlist=["validate_output_schema_binding"])
    with pytest.raises(ValueError, match="TOCTOU|changed|snapshot|schema"):
        module.validate_output_schema_binding(
            handoff,
            schema_path=schema_path,
            schema_bytes=provider_bytes,
            schema_id=SCHEMA_ID,
            schema_version=SCHEMA_VERSION,
            validator_version=VALIDATOR_VERSION,
        )


def test_reparse_point_schema_is_rejected_when_platform_allows_creation(tmp_path: Path) -> None:
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    _write_schema(target_dir / "schema.json")
    junction_dir = tmp_path / "junction"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction_dir), str(target_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"junction creation unavailable: {result.stderr or result.stdout}")
    with pytest.raises(ValueError, match="reparse|symlink|schema"):
        _bind(junction_dir / "schema.json")


def test_schema_binding_rejects_provider_identity_drift(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    module = __import__("cad_agent.vision_handoff", fromlist=["validate_output_schema_binding"])
    with pytest.raises(ValueError, match="schema"):
        module.validate_output_schema_binding(
            handoff,
            schema_path=schema_path,
            schema_bytes=handoff.schema_snapshot.raw_bytes,
            schema_id="foreign-schema",
            schema_version=SCHEMA_VERSION,
            validator_version=VALIDATOR_VERSION,
        )
