from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DISPATCHER = REPO_ROOT / "mcp_integration_lib" / "mcp_dispatch.lsp"
MCP_CLIENT = REPO_ROOT / "mcp_integration_lib" / "mcp_client.py"


CATEGORICAL_ERRORS = {
    "IPC_ROOT_INVALID",
    "IPC_REQUEST_MISSING",
    "IPC_REQUEST_AMBIGUOUS",
    "IPC_REQUEST_INVALID",
    "IPC_REQUEST_ID_INVALID",
    "IPC_JSON_INVALID",
    "IPC_COMMAND_UNSUPPORTED",
    "IPC_COMMAND_FAILED",
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


def test_dispatcher_requires_explicit_isolated_ipc_root_without_shared_temp_fallback() -> None:
    source = _dispatcher_source()
    lowered = source.casefold().replace("\\\\", "/").replace("\\", "/")
    assert "cad_agent_file_ipc" in lowered
    assert "getenv" in lowered
    assert "ipc_root_invalid" in lowered
    for forbidden in (
        "c:/temp",
        "c:/windows/temp",
        "getenv \"temp\"",
        "getenv \"tmp\"",
        "getvar \"tempprefix\"",
    ):
        assert forbidden not in lowered


def test_request_selection_is_single_candidate_identity_bound_and_fail_closed() -> None:
    source = _dispatcher_source()
    lowered = source.casefold()
    assert "autocad_mcp_cmd_" in lowered
    assert "autocad_mcp_result_" in lowered
    assert "vl-directory-files" in lowered
    assert "ipc_request_missing" in lowered
    assert "ipc_request_ambiguous" in lowered
    assert "ipc_request_id_invalid" in lowered
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
    assert "ping" in commands
    assert commands
    missing = sorted(command for command in commands if command.casefold() not in source)
    assert not missing, f"dispatcher is missing existing File IPC commands: {missing}"


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
    )
    found = [marker for marker in forbidden if marker in source]
    assert not found, f"dispatcher crossed forbidden authority boundaries: {found}"
