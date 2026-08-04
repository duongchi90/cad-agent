from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_integration_lib.dotnet_ipc import DotNetIPCClient, DotNetIPCProtocolError


ROOT = Path(__file__).resolve().parents[1]
IPC_ROOT = ROOT / "contracts" / "autocad-ipc"


def valid_parameters() -> dict[str, object]:
    return {
        "run_id": "RUN-001",
        "evidence_id": "EV-SIDE-CABIN-001",
        "region_id": "SIDE-CABIN",
        "latest_mutation_sha256": "a" * 64,
        "visual_run_manifest_sha256": "b" * 64,
        "artifact_policy_version": "vs-t3-artifacts-1",
        "artifact_directory": "artifacts/REQ-VS-T3-001",
        "region": {
            "model_bbox_mm": [0, 0, 2400, 2200],
            "pixel_size": [1600, 1200],
            "background": "WHITE",
            "include_layers": ["CABIN", "CENTER"],
            "exclude_layers": ["TEXT", "DIM"],
        },
        "measurements": [
            {
                "id": "MEASURE-001",
                "kind": "DISTANCE",
                "reference": {"type": "ENTITY", "id": "PART:CABIN_OUTER"},
            }
        ],
    }


def valid_request() -> dict[str, object]:
    return {
        "request_id": "REQ-VS-T3-001",
        "schema_version": "1.0",
        "operation": "visual_evidence_export",
        "drawing_full_path": r"D:\project\vehicle.dwg",
        "drawing_sha256": "c" * 64,
        "parameters": valid_parameters(),
        "approval": None,
    }


def valid_payload() -> dict[str, object]:
    return {
        "run_id": "RUN-001",
        "evidence_id": "EV-SIDE-CABIN-001",
        "region_id": "SIDE-CABIN",
        "drawing_sha256_before": "c" * 64,
        "drawing_sha256_after": "c" * 64,
        "dbmod_before": 0,
        "dbmod_after": 0,
        "latest_mutation_sha256": "a" * 64,
        "visual_run_manifest_sha256": "b" * 64,
        "region_config_sha256": "d" * 64,
        "session_state_sha256_before": "e" * 64,
        "session_state_sha256_after": "e" * 64,
        "transient_state_restored": True,
        "captured_at_utc": "2026-08-04T00:00:02Z",
        "artifacts": [
            {
                "artifact_id": "cad-render",
                "kind": "render",
                "relative_path": "artifacts/REQ-VS-T3-001/cad-render.png",
                "sha256": "f" * 64,
                "byte_length": 123456,
                "mime_type": "image/png",
                "width": 1600,
                "height": 1200,
            },
            {
                "artifact_id": "entity-map",
                "kind": "entity_map",
                "relative_path": "artifacts/REQ-VS-T3-001/entities.json",
                "sha256": "1" * 64,
                "byte_length": 42,
                "mime_type": "application/json",
            },
            {
                "artifact_id": "measurements",
                "kind": "measurements",
                "relative_path": "artifacts/REQ-VS-T3-001/measurements.json",
                "sha256": "2" * 64,
                "byte_length": 42,
                "mime_type": "application/json",
            },
        ],
    }


def valid_result(request: dict[str, object] | None = None) -> dict[str, object]:
    request = request or valid_request()
    return {
        "request_id": request["request_id"],
        "success": True,
        "operation": "visual_evidence_export",
        "drawing_full_path": request["drawing_full_path"],
        "changed": False,
        "entity_handles": [],
        "warnings": [],
        "errors": [],
        "started_at": "2026-08-04T00:00:00Z",
        "completed_at": "2026-08-04T00:00:02Z",
        "payload": valid_payload(),
    }


def test_visual_evidence_examples_exist_and_preserve_the_closed_envelope() -> None:
    request = json.loads(
        (IPC_ROOT / "examples/visual-evidence-export-request.json").read_text(
            encoding="utf-8"
        )
    )
    result = json.loads(
        (IPC_ROOT / "examples/visual-evidence-export-result.json").read_text(
            encoding="utf-8"
        )
    )

    assert set(request) == {
        "request_id",
        "schema_version",
        "operation",
        "drawing_full_path",
        "drawing_sha256",
        "parameters",
        "approval",
    }
    assert request["parameters"] == valid_parameters()
    assert request["approval"] is None
    assert set(result) == {
        "request_id",
        "success",
        "operation",
        "drawing_full_path",
        "changed",
        "entity_handles",
        "warnings",
        "errors",
        "started_at",
        "completed_at",
        "payload",
    }
    assert result == valid_result(request)


def test_vs_t3_request_schema_is_closed_and_rejects_fields_at_the_root() -> None:
    schema = json.loads(
        (IPC_ROOT / "operations/visual-evidence-export.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["additionalProperties"] is False
    request_schema_properties = json.loads(
        (IPC_ROOT / "request.schema.json").read_text(encoding="utf-8")
    )["properties"]
    request = valid_request()
    assert "latest_mutation_sha256" not in request_schema_properties
    assert "latest_mutation_sha256" in request["parameters"]
    request_schema = json.loads((IPC_ROOT / "request.schema.json").read_text(encoding="utf-8"))
    result_schema = json.loads((IPC_ROOT / "result.schema.json").read_text(encoding="utf-8"))
    assert "visual_evidence_export" in request_schema["properties"]["operation"]["enum"]
    assert "visual_evidence_export" in result_schema["properties"]["operation"]["enum"]
    request_branch = next(
        branch for branch in request_schema["allOf"]
        if branch["if"]["properties"]["operation"].get("const") == "visual_evidence_export"
    )
    assert request_branch["then"]["properties"]["parameters"]["$ref"] == (
        "operations/visual-evidence-export.schema.json"
    )
    result_branch = next(
        branch for branch in result_schema["allOf"]
        if branch["if"]["properties"]["operation"].get("const") == "visual_evidence_export"
    )
    assert result_branch["then"]["properties"]["changed"]["const"] is False
    assert result_branch["then"]["properties"]["entity_handles"]["maxItems"] == 0
    assert "payload" in result_branch["then"]["required"]


def test_vs_t3_payload_is_separate_and_closed() -> None:
    schema = json.loads(
        (IPC_ROOT / "operations/visual-evidence-export-result.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["additionalProperties"] is False
    payload = valid_payload()
    payload["latest_mutation_sha256"] = "a" * 64
    assert payload["latest_mutation_sha256"] == valid_parameters()["latest_mutation_sha256"]


def test_python_validator_accepts_valid_vs_t3_parameters() -> None:
    client = DotNetIPCClient(trigger=lambda: None)
    assert client._validate_parameters("visual_evidence_export", valid_parameters()) == valid_parameters()


@pytest.mark.parametrize(
    "field",
    [
        "run_id",
        "evidence_id",
        "region_id",
        "latest_mutation_sha256",
        "visual_run_manifest_sha256",
        "artifact_policy_version",
        "artifact_directory",
        "region",
        "measurements",
    ],
)
def test_python_validator_rejects_missing_vs_t3_parameter(field: str) -> None:
    parameters = valid_parameters()
    parameters.pop(field)
    with pytest.raises(ValueError, match=field):
        DotNetIPCClient._validate_parameters("visual_evidence_export", parameters)


def test_python_validator_rejects_mutating_vs_t3_result() -> None:
    result = valid_result()
    result["changed"] = True
    with pytest.raises(DotNetIPCProtocolError, match="read-only"):
        DotNetIPCClient._validate_result(result, "REQ-VS-T3-001", "visual_evidence_export")
