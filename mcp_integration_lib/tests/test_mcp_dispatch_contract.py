from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

from mcp_integration_lib.mcp_client import (
    FileIPCLiveMCPClient,
    MCPTimeoutError,
    MCPToolError,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DISPATCHER = REPO_ROOT / "mcp_integration_lib" / "mcp_dispatch.lsp"
MCP_CLIENT = REPO_ROOT / "mcp_integration_lib" / "mcp_client.py"
LIVE_HARNESS = REPO_ROOT / "mcp_integration_lib" / "tests" / "test_dotnet_ipc_live.py"
MAX_FILE_IPC_JSON_BYTES = 1024 * 1024

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


def _request_id_from_root(root: Path) -> str:
    request_path = next(root.glob("autocad_mcp_cmd_*.json"))
    request = json.loads(request_path.read_text(encoding="utf-8"))
    filename_id = request_path.stem.removeprefix("autocad_mcp_cmd_")
    assert request["request_id"] == filename_id
    return filename_id


def _write_success_result(root: Path, request_id: str, payload: object | None = None) -> Path:
    result_path = root / f"autocad_mcp_result_{request_id}.json"
    result_path.write_text(
        json.dumps(
            {
                "request_id": request_id,
                "ok": True,
                "payload": {} if payload is None else payload,
            }
        ),
        encoding="utf-8",
    )
    return result_path


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


def test_file_ipc_constructor_rejects_physical_symlink_root_when_supported(tmp_path: Path) -> None:
    physical_root = tmp_path / "physical-root"
    physical_root.mkdir()
    alias_root = tmp_path / "alias-root"
    try:
        alias_root.symlink_to(physical_root, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("directory symlink creation is unavailable on this runner")

    with pytest.raises(ValueError, match="IPC_ROOT"):
        FileIPCLiveMCPClient(ipc_dir=str(alias_root))


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


@pytest.mark.parametrize(
    "stale_content",
    [
        json.dumps({"request_id": "stale", "command": "ping", "params": {}}),
        '{"request_id":"partial"',
        json.dumps(
            {
                "request_id": "oversized",
                "command": "ping",
                "params": {"blob": "x" * (MAX_FILE_IPC_JSON_BYTES + 1)},
            }
        ),
    ],
    ids=("stale", "partial-truncated", "oversized"),
)
def test_file_ipc_dispatch_rejects_preexisting_request_artifact_before_trigger(
    tmp_path: Path,
    stale_content: str,
) -> None:
    stale = tmp_path / "autocad_mcp_cmd_stale.json"
    stale.write_text(stale_content, encoding="utf-8")
    trigger_called = False

    def trigger() -> None:
        nonlocal trigger_called
        trigger_called = True

    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path),
        trigger=trigger,
        timeout_s=0.02,
        poll_interval_s=0.001,
    )
    with pytest.raises(MCPToolError, match="IPC_REQUEST_"):
        client._dispatch("ping", {})
    assert trigger_called is False
    assert stale.exists()


def test_file_ipc_dispatch_rejects_multiple_preexisting_request_candidates_before_trigger(
    tmp_path: Path,
) -> None:
    for request_id in ("stale-a", "stale-b"):
        (tmp_path / f"autocad_mcp_cmd_{request_id}.json").write_text(
            json.dumps({"request_id": request_id, "command": "ping", "params": {}}),
            encoding="utf-8",
        )
    trigger_called = False

    def trigger() -> None:
        nonlocal trigger_called
        trigger_called = True

    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path),
        trigger=trigger,
        timeout_s=0.02,
        poll_interval_s=0.001,
    )
    with pytest.raises(MCPToolError, match="IPC_REQUEST_AMBIGUOUS"):
        client._dispatch("ping", {})
    assert trigger_called is False


def test_file_ipc_dispatch_rejects_preexisting_result_conflict_before_trigger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_request_id = "a1b2c3d4e5f6"

    class FixedUUID:
        hex = fixed_request_id

    monkeypatch.setattr("mcp_integration_lib.mcp_client.uuid.uuid4", lambda: FixedUUID())
    _write_success_result(tmp_path, fixed_request_id, {"stale": True})
    trigger_called = False

    def trigger() -> None:
        nonlocal trigger_called
        trigger_called = True

    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path),
        trigger=trigger,
        timeout_s=0.02,
        poll_interval_s=0.001,
    )
    with pytest.raises(MCPToolError, match="IPC_RESULT_CONFLICT"):
        client._dispatch("ping", {})
    assert trigger_called is False


@pytest.mark.parametrize(
    "invalid_result",
    [
        "{",
        '{"request_id":',
    ],
    ids=("malformed", "truncated"),
)
def test_file_ipc_dispatch_rejects_malformed_or_truncated_result_and_cleans_owned_files(
    tmp_path: Path,
    invalid_result: str,
) -> None:
    def trigger() -> None:
        request_id = _request_id_from_root(tmp_path)
        (tmp_path / f"autocad_mcp_result_{request_id}.json").write_text(
            invalid_result,
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


def test_file_ipc_dispatch_rejects_oversized_result_and_cleans_owned_files(tmp_path: Path) -> None:
    def trigger() -> None:
        request_id = _request_id_from_root(tmp_path)
        _write_success_result(
            tmp_path,
            request_id,
            {"blob": "x" * (MAX_FILE_IPC_JSON_BYTES + 1)},
        )

    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path),
        trigger=trigger,
        timeout_s=0.02,
        poll_interval_s=0.001,
    )
    with pytest.raises(MCPToolError, match="IPC_RESULT_OVERSIZED"):
        client._dispatch("ping", {})
    assert not list(tmp_path.glob("autocad_mcp_cmd_*.json"))
    assert not list(tmp_path.glob("autocad_mcp_result_*.json"))


@pytest.mark.parametrize(
    "result_factory",
    [
        lambda request_id: {"request_id": request_id, "ok": "true", "payload": {}},
        lambda request_id: {"request_id": request_id, "ok": True},
        lambda request_id: {
            "request_id": request_id,
            "ok": True,
            "payload": {},
            "error": "IPC_COMMAND_FAILED",
        },
        lambda request_id: {
            "request_id": request_id,
            "ok": False,
            "payload": {},
            "error": "IPC_COMMAND_FAILED",
        },
    ],
    ids=("non-boolean-ok", "missing-payload", "success-with-error", "failure-with-payload"),
)
def test_file_ipc_dispatch_rejects_invalid_result_envelopes(
    tmp_path: Path,
    result_factory,
) -> None:
    def trigger() -> None:
        request_id = _request_id_from_root(tmp_path)
        result_path = tmp_path / f"autocad_mcp_result_{request_id}.json"
        result_path.write_text(json.dumps(result_factory(request_id)), encoding="utf-8")

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


def test_file_ipc_dispatch_rejects_conflicting_result_filename_without_deleting_foreign_result(
    tmp_path: Path,
) -> None:
    foreign_result: Path | None = None

    def trigger() -> None:
        nonlocal foreign_result
        request_id = _request_id_from_root(tmp_path)
        foreign_result = tmp_path / "autocad_mcp_result_foreign.json"
        foreign_result.write_text(
            json.dumps({"request_id": request_id, "ok": True, "payload": {}}),
            encoding="utf-8",
        )

    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path),
        trigger=trigger,
        timeout_s=0.02,
        poll_interval_s=0.001,
    )
    with pytest.raises(MCPToolError, match="IPC_RESULT_CONFLICT"):
        client._dispatch("ping", {})
    assert foreign_result is not None and foreign_result.exists()
    assert not list(tmp_path.glob("autocad_mcp_cmd_*.json"))


def test_file_ipc_dispatch_does_not_consume_matching_result_outside_bound_root(tmp_path: Path) -> None:
    root = tmp_path / "bound-root"
    outside = tmp_path / "outside-root"
    root.mkdir()
    outside.mkdir()
    outside_result: Path | None = None

    def trigger() -> None:
        nonlocal outside_result
        request_id = _request_id_from_root(root)
        outside_result = _write_success_result(outside, request_id, {"forged": True})

    client = FileIPCLiveMCPClient(
        ipc_dir=str(root),
        trigger=trigger,
        timeout_s=0.02,
        poll_interval_s=0.001,
    )
    with pytest.raises(MCPTimeoutError):
        client._dispatch("ping", {})
    assert outside_result is not None and outside_result.exists()
    assert not list(root.glob("autocad_mcp_cmd_*.json"))
    assert not list(root.glob("autocad_mcp_result_*.json"))


def test_file_ipc_dispatch_fails_closed_on_physical_root_replacement_race(tmp_path: Path) -> None:
    root = tmp_path / "ipc-root"
    displaced = tmp_path / "ipc-root-original"
    root.mkdir()
    replacement_blocked = False

    def trigger() -> None:
        nonlocal replacement_blocked
        request_id = _request_id_from_root(root)
        try:
            root.rename(displaced)
        except OSError:
            replacement_blocked = True
            return
        root.mkdir()
        _write_success_result(root, request_id, {"forged": True})

    client = FileIPCLiveMCPClient(
        ipc_dir=str(root),
        trigger=trigger,
        timeout_s=0.02,
        poll_interval_s=0.001,
    )
    try:
        payload = client._dispatch("ping", {})
    except MCPToolError as exc:
        assert "IPC_ROOT_CHANGED" in str(exc)
    except MCPTimeoutError:
        assert replacement_blocked is True
    else:
        pytest.fail(f"accepted result after physical root replacement: {payload!r}")


@pytest.mark.parametrize(
    "attack_command",
    [
        "eval",
        "read",
        "load",
        "command",
        "vl-cmdf",
        '(eval (read "(vl-load-com)"))',
    ],
)
def test_file_ipc_dispatch_rejects_non_allowlisted_command_before_trigger(
    tmp_path: Path,
    attack_command: str,
) -> None:
    assert attack_command not in EXPECTED_FILE_IPC_COMMANDS
    trigger_called = False

    def trigger() -> None:
        nonlocal trigger_called
        trigger_called = True

    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path),
        trigger=trigger,
        timeout_s=0.02,
        poll_interval_s=0.001,
    )
    with pytest.raises(MCPToolError, match="IPC_COMMAND_UNSUPPORTED"):
        client._dispatch(attack_command, {"payload": "data-only"})
    assert trigger_called is False


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
    for dynamic_command_form in (
        r"\(\s*command(?:-s)?\s+(?!\")",
        r"\(\s*vl-cmdf\s+(?!\")",
    ):
        assert re.search(dynamic_command_form, source) is None


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


def test_file_ipc_dispatch_rejects_preexisting_request_part_before_trigger_without_deleting_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_request_id = "a1b2c3d4e5f6"

    class FixedUUID:
        hex = fixed_request_id

    monkeypatch.setattr("mcp_integration_lib.mcp_client.uuid.uuid4", lambda: FixedUUID())
    stale_part = tmp_path / f"autocad_mcp_cmd_{fixed_request_id}.json.part"
    stale_part.write_text("partial", encoding="utf-8")
    trigger_called = False

    def trigger() -> None:
        nonlocal trigger_called
        trigger_called = True

    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path),
        trigger=trigger,
        timeout_s=0.02,
        poll_interval_s=0.001,
    )
    with pytest.raises(MCPToolError, match="IPC_REQUEST_INVALID"):
        client._dispatch("ping", {})
    assert trigger_called is False
    assert stale_part.exists()


def test_file_ipc_dispatch_rejects_preexisting_result_part_before_trigger_without_deleting_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_request_id = "a1b2c3d4e5f6"

    class FixedUUID:
        hex = fixed_request_id

    monkeypatch.setattr("mcp_integration_lib.mcp_client.uuid.uuid4", lambda: FixedUUID())
    stale_part = tmp_path / f"autocad_mcp_result_{fixed_request_id}.json.part"
    stale_part.write_text("partial", encoding="utf-8")
    trigger_called = False

    def trigger() -> None:
        nonlocal trigger_called
        trigger_called = True

    client = FileIPCLiveMCPClient(
        ipc_dir=str(tmp_path),
        trigger=trigger,
        timeout_s=0.02,
        poll_interval_s=0.001,
    )
    with pytest.raises(MCPToolError, match="IPC_RESULT_CONFLICT"):
        client._dispatch("ping", {})
    assert trigger_called is False
    assert stale_part.exists()


def test_dispatcher_rejects_exact_result_part_before_command_execution() -> None:
    source = _dispatcher_source()
    match = re.search(
        r"\(defun\s+mcp-dispatch-core\b(?P<body>.*?)(?=\n\(defun\s+c:mcp-dispatch\b)",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None
    body = match.group("body").casefold()
    part_marker = '".json.part"'
    dispatch_marker = "(mcp-dispatch-command command params)"
    assert part_marker in body
    assert dispatch_marker in body
    assert body.index(part_marker) < body.index(dispatch_marker)
