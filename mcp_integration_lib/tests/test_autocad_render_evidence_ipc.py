from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from mcp_integration_lib.autocad_render_evidence import (
    REQUEST_SCHEMA_VERSION,
    AutoCADRenderEvidenceError,
    validate_render_request,
)
from mcp_integration_lib.dotnet_ipc import (
    DotNetIPCClient,
    DotNetIPCProtocolError,
    DotNetIPCResultError,
    SUPPORTED_OPERATIONS,
    atomic_write_json,
    result_path,
)


ROOT = Path(__file__).resolve().parents[2]
IPC_ROOT = ROOT / "contracts" / "autocad-ipc"
S2A_FIXTURE = Path(__file__).with_name("fixtures") / "autocad-render-evidence.json"


def _fixture() -> dict[str, object]:
    return json.loads(S2A_FIXTURE.read_text(encoding="utf-8"))


def _s2a_request() -> dict[str, object]:
    return copy.deepcopy(_fixture()["request"])


def _s2a_evidence() -> dict[str, object]:
    return copy.deepcopy(_fixture()["png"])


def _ipc_result(request: dict[str, object], *, payload: dict[str, object], success: bool = True) -> dict[str, object]:
    return {
        "request_id": request["request_id"],
        "success": success,
        "operation": request["operation"],
        "drawing_full_path": request["drawing_full_path"],
        "changed": False,
        "entity_handles": [],
        "warnings": [],
        "errors": [] if success else ["NATIVE_RENDER_NOT_IMPLEMENTED"],
        "started_at": "2026-08-05T08:00:00Z",
        "completed_at": "2026-08-05T08:00:00Z",
        "payload": payload,
    }


def test_native_render_evidence_maps_s2a_request_through_existing_envelope(tmp_path: Path) -> None:
    request = _s2a_request()
    evidence = _s2a_evidence()
    observed: dict[str, object] = {}

    def trigger() -> None:
        request_file = next(tmp_path.glob("cadagent_dotnet_request_*.json"))
        envelope = json.loads(request_file.read_text(encoding="utf-8"))
        observed.update(envelope)
        atomic_write_json(
            result_path(tmp_path, str(envelope["request_id"])),
            _ipc_result(envelope, payload=evidence),
        )

    result = DotNetIPCClient(ipc_dir=tmp_path, trigger=trigger).native_render_evidence(
        r"C:\drawings\sample.dwg", request
    )

    assert observed["operation"] == "native_render_evidence"
    assert observed["request_id"] == request["request_id"]
    assert observed["drawing_sha256"] == request["drawing_sha256"]
    assert observed["approval"] is None
    assert observed["parameters"] == {
        key: request[key]
        for key in (
            "run_id",
            "latest_mutation_sha256",
            "visual_run_manifest_sha256",
            "layout",
            "artifact_kind",
            "render_options",
            "requested_at",
        )
    }
    assert result["payload"] == evidence
    assert not list(tmp_path.glob("cadagent_dotnet_*.json"))


def test_native_render_evidence_rejects_result_that_does_not_match_s2a_request(tmp_path: Path) -> None:
    request = _s2a_request()
    evidence = _s2a_evidence()
    evidence["run_id"] = "other-run"

    def trigger() -> None:
        request_file = next(tmp_path.glob("cadagent_dotnet_request_*.json"))
        envelope = json.loads(request_file.read_text(encoding="utf-8"))
        atomic_write_json(
            result_path(tmp_path, str(envelope["request_id"])),
            _ipc_result(envelope, payload=evidence),
        )

    client = DotNetIPCClient(ipc_dir=tmp_path, trigger=trigger)
    with pytest.raises(DotNetIPCProtocolError, match="does not match request"):
        client.native_render_evidence(r"C:\drawings\sample.dwg", request)


def test_native_render_evidence_accepts_only_closed_s2a_request(tmp_path: Path) -> None:
    request = _s2a_request()
    request["approval"] = None
    with pytest.raises(AutoCADRenderEvidenceError, match="unknown field|not allowed"):
        DotNetIPCClient(ipc_dir=tmp_path, trigger=lambda: None).native_render_evidence(
            r"C:\drawings\sample.dwg", request
        )


def test_native_render_evidence_surfaces_deterministic_unsupported_result(tmp_path: Path) -> None:
    request = _s2a_request()

    def trigger() -> None:
        request_file = next(tmp_path.glob("cadagent_dotnet_request_*.json"))
        envelope = json.loads(request_file.read_text(encoding="utf-8"))
        atomic_write_json(
            result_path(tmp_path, str(envelope["request_id"])),
            _ipc_result(envelope, payload={}, success=False),
        )

    with pytest.raises(DotNetIPCResultError, match="NATIVE_RENDER_NOT_IMPLEMENTED"):
        DotNetIPCClient(ipc_dir=tmp_path, trigger=trigger).native_render_evidence(
            r"C:\drawings\sample.dwg", request
        )


def test_native_render_ipc_examples_and_schema_branches_are_closed() -> None:
    request_envelope = json.loads(
        (IPC_ROOT / "examples/native-render-evidence-request.json").read_text(encoding="utf-8")
    )
    result_envelope = json.loads(
        (IPC_ROOT / "examples/native-render-evidence-result.json").read_text(encoding="utf-8")
    )
    request_schema = json.loads((IPC_ROOT / "request.schema.json").read_text(encoding="utf-8"))
    result_schema = json.loads((IPC_ROOT / "result.schema.json").read_text(encoding="utf-8"))
    operation_schema = json.loads(
        (IPC_ROOT / "operations/native-render-evidence.schema.json").read_text(encoding="utf-8")
    )
    result_payload_schema = json.loads(
        (IPC_ROOT / "operations/native-render-evidence-result.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert operation_schema["additionalProperties"] is False
    assert result_payload_schema["additionalProperties"] is False
    assert request_envelope["operation"] == "native_render_evidence"
    assert result_envelope == {
        **result_envelope,
        "operation": "native_render_evidence",
        "success": False,
        "changed": False,
        "entity_handles": [],
        "errors": ["NATIVE_RENDER_NOT_IMPLEMENTED"],
        "payload": {},
    }
    native_request = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "request_id": request_envelope["request_id"],
        "run_id": request_envelope["parameters"]["run_id"],
        "drawing_sha256": request_envelope["drawing_sha256"],
        "latest_mutation_sha256": request_envelope["parameters"]["latest_mutation_sha256"],
        "visual_run_manifest_sha256": request_envelope["parameters"]["visual_run_manifest_sha256"],
        "layout": request_envelope["parameters"]["layout"],
        "artifact_kind": request_envelope["parameters"]["artifact_kind"],
        "render_options": request_envelope["parameters"]["render_options"],
        "requested_at": request_envelope["parameters"]["requested_at"],
    }
    assert validate_render_request(native_request)["request_id"] == request_envelope["request_id"]
    assert result_envelope["payload"] == {}
    assert "native_render_evidence" in request_schema["properties"]["operation"]["enum"]
    assert "native_render_evidence" in result_schema["properties"]["operation"]["enum"]
    request_branch = next(
        branch
        for branch in request_schema["allOf"]
        if branch["if"]["properties"]["operation"].get("const") == "native_render_evidence"
    )
    assert request_branch["then"]["properties"]["parameters"]["$ref"] == (
        "operations/native-render-evidence.schema.json"
    )
    result_branch = next(
        branch
        for branch in result_schema["allOf"]
        if branch["if"]["properties"]["operation"].get("const") == "native_render_evidence"
    )
    assert result_branch["then"]["properties"]["changed"]["const"] is False
    assert result_branch["then"]["properties"]["entity_handles"]["maxItems"] == 0


def test_legacy_operation_allowlist_entries_remain_unchanged() -> None:
    assert {
        "health",
        "review",
        "close_disposable",
        "mechanical_bom",
        "drawing_setup_audit",
        "visual_evidence_export",
    }.issubset(SUPPORTED_OPERATIONS)
