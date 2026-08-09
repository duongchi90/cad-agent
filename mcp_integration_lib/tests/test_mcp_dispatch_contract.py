from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

from mcp_integration_lib.mcp_client import (
    FileIPCLiveMCPClient,
    MCPToolError,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DISPATCHER = REPO_ROOT / "mcp_integration_lib" / "mcp_dispatch.lsp"
MCP_CLIENT = REPO_ROOT / "mcp_integration_lib" / "mcp_client.py"
LIVE_HARNESS = REPO_ROOT / "mcp_integration_lib" / "tests" / "test_dotnet_ipc_live.py"

EXPECTED_FILE_IPC_COMMANDS = {
    "ping",
    "entity-list",
    "drawing-open",
    "drawing-save",
    "drawing-close",
    "drawing-list-open-paths",
    "drawing-save-as-dxf",
    "drawing-get-variables",
    "block-get-attributes",
    "block-update-attribute",
    "entity-get",
    "entity-erase",
    "create-line",
    "create-circle",
    "create-arc",
    "create-text",
}

CATEGORICAL_ERRORS = {
    "IPC_ROOT_INVALID",
    "IPC_REQUEST_MISSING",
    "IPC_REQUEST_AMBIGUOUS",
    "IPC_REQUEST_INVALID",
    "IPC_REQUEST_ID_INVALID",
    "IPC_REQUEST_OVERSIZED",
    "IPC_JSON_INVALID",
    "IPC_COMMAND_UNSUPPORTED",
    "IPC_COMMAND_FAILED",
    "IPC_RESULT_CONFLICT",
}


def _dispatcher_bytes() -> bytes:
    assert DISPATCHER.is_file(), (
        "Issue #147 RED: canonical dispatcher source is absent at "
        "mcp_integration_lib/mcp_dispatch.lsp"
    )
    return DISPATCHER.read_bytes()


def _dispatcher_source() -> str:
    raw = _dispatcher_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AssertionError("canonical dispatcher must be deterministic UTF-8 text") from exc


def _file_ipc_dispatch_commands() -> set[str]:
    tree = ast.parse(MCP_CLIENT.read_text(encoding="utf-8"))
    target = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "FileIPCLiveMCPClient"
    )
    commands: set[str] = set()
    for node in ast.walk(target):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not (
            isinstance(function, ast.Attribute)
            and function.attr == "_dispatch"
            and isinstance(function.value, ast.Name)
            and function.value.id == "self"
        ):
            continue
        if not node.args:
            continue
        command = node.args[0]
        if isinstance(command, ast.Constant) and isinstance(command.value, str):
            commands.add(command.value)
    return commands


def _is_environment_lookup(node: ast.AST, name: str) -> bool:
    if not isinstance(node, ast.Subscript):
        return False
    if not (
        isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "os"
        and node.value.attr == "environ"
    ):
        return False
    key = node.slice
    return isinstance(key, ast.Constant) and key.value == name


def _constructor_keyword_values(class_name: str, keyword: str) -> list[ast.AST | None]:
    tree = ast.parse(LIVE_HARNESS.read_text(encoding="utf-8"))
    values: list[ast.AST | None] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not isinstance(function, ast.Name) or function.id != class_name:
            continue
        match = next((item.value for item in node.keywords if item.arg == keyword), None)
        values.append(match)
    return values


def test_exactly_one_canonical_dispatcher_source_exists() -> None:
    _dispatcher_bytes()
    candidates = sorted(REPO_ROOT.rglob("mcp_dispatch.lsp"))
    assert candidates == [DISPATCHER]


def test_dispatcher_source_is_deterministic_hashable_and_defines_public_command() -> None:
    first = _dispatcher_bytes()
    second = DISPATCHER.read_bytes()
    assert first == second
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()
    source = first.decode("utf-8")
    assert re.search(r"\(defun\s+c:mcp-dispatch\b", source, flags=re.IGNORECASE)
    lowered = source.casefold()
    for nondeterministic_marker in (
        "__date__",
        "__time__",
        "random",
        "getvar \"cdate\"",
        "getvar \"date\"",
        "getvar \"millisecs\"",
        "computername",
        "username",
    ):
        assert nondeterministic_marker not in lowered


def test_file_ipc_constructor_requires_an_explicit_root() -> None:
    with pytest.raises(TypeError):
        FileIPCLiveMCPClient()


@pytest.mark.parametrize(
    "unsafe_root",
    [
        "",
        r"relative\ipc",
        r"C:drive-relative\ipc",
        r"\\server\share\ipc",
        r"C:\cad-agent\session\..\escape",
    ],
)
def test_file_ipc_constructor_rejects_ambiguous_or_nonlocal_roots(unsafe_root: str) -> None:
    with pytest.raises(ValueError):
        FileIPCLiveMCPClient(ipc_dir=unsafe_root)


def test_file_ipc_dispatch_binds_request_filename_payload_and_result_identity(tmp_path: Path) -> None:
    observed: dict[str, str] = {}

    def trigger() -> None:
        requests = list(tmp_path.glob("autocad_mcp_cmd_*.json"))
        assert len(requests) == 1
        request_path = requests[0]
        request = json.loads(request_path.read_text(encoding="utf-8"))
        filename_id = request_path.stem.removeprefix("autocad_mcp_cmd_")
        assert request["request_id"] == filename_id
        observed["request_id"] = filename_id
        result_path = tmp_path / f"autocad_mcp_result_{filename_id}.json"
        result_path.write_text(
            json.dumps(
                {
                    "request_id": filename_id,
                    "ok": True,
                    "payload": {"ready": True},
                }
            ),
            encoding="utf-8",
        )

    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path),
        trigger=trigger,
        timeout_s=0.2,
        poll_interval_s=0.001,
    )
    assert client._dispatch("ping", {}) == {"ready": True}
    assert observed["request_id"]
    assert not list(tmp_path.glob("autocad_mcp_cmd_*.json"))
    assert not list(tmp_path.glob("autocad_mcp_result_*.json"))


def test_file_ipc_dispatch_rejects_result_request_id_mismatch_categorically(tmp_path: Path) -> None:
    def trigger() -> None:
        request_path = next(tmp_path.glob("autocad_mcp_cmd_*.json"))
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request_id = request["request_id"]
        result_path = tmp_path / f"autocad_mcp_result_{request_id}.json"
        result_path.write_text(
            json.dumps(
                {
                    "request_id": "different-request-id",
                    "ok": True,
                    "payload": {},
                }
            ),
            encoding="utf-8",
        )

    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path),
        trigger=trigger,
        timeout_s=0.02,
        poll_interval_s=0.001,
    )
    with pytest.raises(MCPToolError, match="IPC_RESULT_INVALID"):
        client._dispatch("ping", {})
    assert not list(tmp_path.glob("autocad_mcp_cmd_*.json"))
    assert not list(tmp_path.glob("autocad_mcp_result_*.json"))


def test_live_harness_binds_file_ipc_and_dotnet_clients_to_explicit_root_envs() -> None:
    file_ipc_values = _constructor_keyword_values("FileIPCLiveMCPClient", "ipc_dir")
    assert file_ipc_values
    assert all(
        value is not None and _is_environment_lookup(value, "CAD_AGENT_FILE_IPC_DIR")
        for value in file_ipc_values
    )

    dotnet_values = _constructor_keyword_values("DotNetIPCClient", "ipc_dir")
    assert dotnet_values
    assert all(
        value is not None and _is_environment_lookup(value, "CAD_AGENT_DOTNET_IPC_DIR")
        for value in dotnet_values
    )


def test_python_file_ipc_command_surface_is_exact_and_closed() -> None:
    assert _file_ipc_dispatch_commands() == EXPECTED_FILE_IPC_COMMANDS


def test_dispatcher_consumes_prebound_root_without_environment_or_shared_temp_authority() -> None:
    source = _dispatcher_source()
    lowered = source.casefold().replace("\\\\", "/").replace("\\", "/")
    assert "ipc_root_invalid" in lowered
    for forbidden in (
        "getenv",
        "setenv",
        "c:/temp",
        "c:/windows/temp",
        "tempprefix",
        "\"temp\"",
        "\"tmp\"",
    ):
        assert forbidden not in lowered


def test_request_selection_is_single_candidate_identity_bound_bounded_and_fail_closed() -> None:
    source = _dispatcher_source()
    lowered = source.casefold()
    assert "autocad_mcp_cmd_" in lowered
    assert "autocad_mcp_result_" in lowered
    assert "vl-directory-files" in lowered
    assert "ipc_request_missing" in lowered
    assert "ipc_request_ambiguous" in lowered
    assert "ipc_request_id_invalid" in lowered
    assert "ipc_request_oversized" in lowered
    assert "ipc_json_invalid" in lowered
    assert "ipc_result_conflict" in lowered
    assert "request_id" in lowered
    assert ".." not in re.sub(r";[^\n]*", "", lowered)
    for caller_owned_result_name in (
        "result_path",
        "result_file",
        "output_path",
        "alternate_result",
    ):
        assert caller_owned_result_name not in lowered


def test_dispatcher_covers_every_existing_file_ipc_dispatch_command() -> None:
    source = _dispatcher_source().casefold()
    commands = _file_ipc_dispatch_commands()
    assert commands == EXPECTED_FILE_IPC_COMMANDS
    missing = sorted(command for command in commands if command.casefold() not in source)
    assert not missing, f"dispatcher is missing existing File IPC commands: {missing}"


def test_dispatcher_never_converts_json_into_executable_autolisp() -> None:
    source = _dispatcher_source().casefold()
    for forbidden_form in (
        r"\(\s*eval\b",
        r"\(\s*read\b",
        r"\(\s*load\b",
        r"\(\s*apply\b",
        r"\(\s*vl-symbol-function\b",
    ):
        assert re.search(forbidden_form, source) is None


def test_ping_and_result_envelope_preserve_request_identity_without_granting_authority() -> None:
    source = _dispatcher_source().casefold()
    for required in ("ping", "request_id", "ok", "payload", "error"):
        assert required in source
    assert "ipc_command_unsupported" in source
    for forbidden_authority in (
        "accepted_for_publication",
        "engineering_approval",
        "promotion_safe",
        "cad_truth_authority",
    ):
        assert forbidden_authority not in source


def test_failures_use_fixed_categorical_material_and_never_own_python_cleanup() -> None:
    source = _dispatcher_source()
    lowered = source.casefold()
    present = {code for code in CATEGORICAL_ERRORS if code.casefold() in lowered}
    assert present == CATEGORICAL_ERRORS
    assert "vl-file-delete" not in lowered
    assert "deletefile" not in lowered
    assert "remove-item" not in lowered
    assert "autocad_mcp_result_" in lowered
    assert "autocad_mcp_cmd_" in lowered


def test_dispatcher_contains_no_second_transport_or_forbidden_system_authority() -> None:
    source = _dispatcher_source().casefold()
    forbidden = (
        "http://",
        "https://",
        "socket",
        "curl",
        "powershell",
        "cmd.exe",
        "wscript",
        "startapp",
        "vl-registry",
        "registry",
        ".pc3",
        ".pmp",
        "printer",
        "plotter",
        "netload",
        ".dll",
        "provider",
        "model_identity",
        "ocr",
        "repair_plan",
        "visual_verdict",
        "auto_publish",
        "renderer",
        "session_store",
    )
    found = [marker for marker in forbidden if marker in source]
    assert not found, f"dispatcher crossed forbidden authority boundaries: {found}"
