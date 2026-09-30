"""Opt-in acceptance regression for an explicitly admitted disposable native edit."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time

import pytest

from mcp_integration_lib.dotnet_ipc import (
    DotNetIPCClient,
    make_windows_dotnet_dispatch_trigger,
)


@pytest.mark.autocad_mechanical
def test_bounded_native_edit_survives_readback_and_owned_save() -> None:
    fixture_path = os.environ.get("CAD_AGENT_BOUNDED_NATIVE_EDIT_FIXTURE_JSON")
    if not fixture_path:
        pytest.skip("requires an admitted disposable native edit fixture and live AutoCAD")
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8-sig"))
    assert fixture["disposable_edit_authorized"] is True
    candidate = Path(fixture["candidate_path"])
    protected_source = Path(fixture["protected_source_path"])
    assert candidate.resolve() != protected_source.resolve()
    assert candidate.name.endswith(".candidate.dwg")

    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    source_before = sha256(protected_source)
    assert source_before == fixture["protected_source_sha256"]
    assert sha256(candidate) == fixture["candidate_sha256_before"]
    parameters = fixture["parameters"]
    targets = parameters["targets"]
    assert targets
    client = DotNetIPCClient(
        ipc_dir=fixture["ipc_directory"],
        trigger=make_windows_dotnet_dispatch_trigger(fixture["autocad_hwnd"]),
        timeout_s=45,
    )
    request_id = f"bounded-native-save-regression-{time.time_ns()}"
    health = client.health(candidate, request_id=f"{request_id}-health")
    assert health["payload"]["plugin_binary_sha256"] == fixture["plugin_binary_sha256"]
    result = client.request(
        "bounded_native_line_edit",
        candidate,
        drawing_sha256=fixture["candidate_sha256_before"],
        parameters=parameters,
        request_id=request_id,
    )
    Path(fixture["result_path"]).write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert result["success"] is True
    assert result["changed"] is True
    assert set(result["entity_handles"]) == {target["handle"] for target in targets}
    payload = result["payload"]
    assert payload["durable_state"] == "SAVED"
    assert payload["save_performed"] is True
    assert payload["drawing_sha256_after"] == sha256(candidate)
    assert payload["drawing_sha256_after"] != fixture["candidate_sha256_before"]
    assert {item["handle"]: item["after"] for item in payload["targets"]} == {
        item["handle"]: item["after"] for item in targets
    }
    assert all(item["before"] == item["after"] for item in payload["protected"])
    assert sha256(protected_source) == source_before
