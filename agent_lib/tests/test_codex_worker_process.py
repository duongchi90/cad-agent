from __future__ import annotations

import ast
import dataclasses
import inspect
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Mapping

import pytest

from agent_lib.codex_worker_process import (
    ProcessTreeIdentity,
    WorkerCleanupResult,
    WorkerEnvironmentAttestation,
    WorkerProcessError,
    WorkerProcessHandle,
    cleanup_worker_process,
    launch_worker_process,
    prepare_worker_environment,
)


SOURCE_MODULE = Path(__file__).parents[1] / "codex_worker_process.py"
_FORBIDDEN_ENV_NAMES = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GITHUB_TOKEN",
    "CUSTOM_TOKEN",
    "CUSTOM_SECRET",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_SERVICE_NAME",
    "MCP_CONFIG",
    "CODEX_CONFIG",
    "CODEX_HOME",
}


class _FakeClock:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)
        self.last = 0.0

    def __call__(self) -> float:
        try:
            self.last = next(self._values)
        except StopIteration:
            self.last += 1.0
        return self.last


class _FakeProcessApi:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.query_results: list[object] = []
        self.fail_stage: str | None = None
        self.root_pid = 4101
        self.closed: list[object] = []

    def _maybe_fail(self, stage: str) -> None:
        self.events.append(stage)
        if self.fail_stage == stage:
            raise RuntimeError("FAKE_SECRET C:\\customer\\private\\drawing.dwg")

    def create_job(self, max_processes: int) -> object:
        self._maybe_fail("create_job")
        return "job-handle"

    def configure_job(self, job_handle: object, max_processes: int) -> None:
        assert job_handle == "job-handle"
        self._maybe_fail("configure_job")

    def create_suspended_process(
        self,
        *,
        executable: Path,
        argv: tuple[str, ...],
        cwd: Path,
        environment: Mapping[str, str],
    ) -> object:
        assert executable.is_absolute()
        assert cwd.is_absolute()
        assert isinstance(argv, tuple)
        assert "CODEX_HOME" in environment
        self._maybe_fail("create_process")
        return SimpleNamespace(
            process_handle="process-handle",
            thread_handle="thread-handle",
            pid=self.root_pid,
        )

    def assign_process(self, job_handle: object, process_handle: object) -> None:
        assert job_handle == "job-handle"
        assert process_handle == "process-handle"
        self._maybe_fail("assign_process")

    def resume_process(self, thread_handle: object) -> None:
        assert thread_handle == "thread-handle"
        self._maybe_fail("resume_process")

    def query_job_process_ids(
        self, job_handle: object, *, max_processes: int
    ) -> tuple[int, ...]:
        assert job_handle == "job-handle"
        self._maybe_fail("query_job")
        if not self.query_results:
            return (self.root_pid,)
        result = self.query_results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result  # type: ignore[return-value]

    def terminate_job(self, job_handle: object) -> None:
        assert job_handle == "job-handle"
        self._maybe_fail("terminate_job")

    def terminate_process(self, process_handle: object) -> None:
        assert process_handle == "process-handle"
        self._maybe_fail("terminate_process")

    def close_handle(self, handle: object) -> None:
        self.events.append(f"close:{handle}")
        self.closed.append(handle)
        if self.fail_stage == "close_handle":
            raise RuntimeError("FAKE_SECRET C:\\customer\\private\\drawing.dwg")


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "disposable"
    cwd = root / "cwd"
    cwd.mkdir(parents=True)
    return root, cwd


def _base_source_environment() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", ""),
        "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
        "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
        "COMSPEC": os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
        "PATHEXT": os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD"),
    }


def _prepared(tmp_path: Path) -> WorkerEnvironmentAttestation:
    root, cwd = _paths(tmp_path)
    return prepare_worker_environment(
        disposable_root=root,
        cwd=cwd,
        source_environment=_base_source_environment(),
    )


def _launch_fake(
    tmp_path: Path,
    *,
    api: _FakeProcessApi | None = None,
    cleanup_deadline_seconds: float = 0.25,
    max_processes: int = 8,
) -> WorkerProcessHandle:
    prepared = _prepared(tmp_path)
    executable = Path(sys.executable).resolve()
    backend = api or _FakeProcessApi()
    return launch_worker_process(
        environment=prepared,
        executable=executable,
        argv=("-c", "pass"),
        cleanup_deadline_seconds=cleanup_deadline_seconds,
        max_processes=max_processes,
        _process_api=backend,
    )


def test_environment_starts_empty_and_excludes_secrets_proxies_telemetry_and_mcp(
    tmp_path: Path,
) -> None:
    root, cwd = _paths(tmp_path)
    source = _base_source_environment()
    source.update(
        {
            "OPENAI_API_KEY": "sk-test-secret",
            "ANTHROPIC_API_KEY": "anthropic-secret",
            "GITHUB_TOKEN": "ghp_secret",
            "CUSTOM_TOKEN": "token-secret",
            "CUSTOM_SECRET": "secret-secret",
            "HTTP_PROXY": "http://proxy.invalid",
            "HTTPS_PROXY": "http://proxy.invalid",
            "ALL_PROXY": "socks5://proxy.invalid",
            "NO_PROXY": "localhost",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "https://otel.invalid",
            "OTEL_SERVICE_NAME": "customer-service",
            "MCP_CONFIG": r"C:\Users\customer\mcp.json",
            "CODEX_CONFIG": r"C:\Users\customer\config.toml",
            "CODEX_HOME": r"C:\Users\customer\.codex",
            "UNRELATED": "must-not-appear",
        }
    )

    prepared = prepare_worker_environment(
        disposable_root=root,
        cwd=cwd,
        source_environment=source,
    )

    child = dict(prepared.environment)
    assert {name.upper() for name in child}.isdisjoint(_FORBIDDEN_ENV_NAMES)
    assert "UNRELATED" not in child
    assert set(child).issuperset({"CODEX_HOME", "TEMP", "TMP"})
    assert Path(child["CODEX_HOME"]).is_relative_to(root.resolve())
    assert Path(child["TEMP"]).is_relative_to(root.resolve())
    assert Path(child["TMP"]).is_relative_to(root.resolve())


def test_codex_home_and_temp_are_fresh_disposable_directories(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)

    assert prepared.codex_home.is_dir()
    assert prepared.temp_dir.is_dir()
    assert list(prepared.codex_home.iterdir()) == []
    assert list(prepared.temp_dir.iterdir()) == []
    assert prepared.codex_home in prepared.writable_roots
    assert prepared.temp_dir in prepared.writable_roots
    assert prepared.cwd in prepared.writable_roots


@pytest.mark.parametrize("name", ["codex-home", "tmp"])
def test_preexisting_worker_owned_directory_fails_closed(
    tmp_path: Path, name: str
) -> None:
    root, cwd = _paths(tmp_path)
    path = root / name
    path.mkdir()
    (path / "ambient.txt").write_text("ambient", encoding="utf-8")

    with pytest.raises(WorkerProcessError) as caught:
        prepare_worker_environment(
            disposable_root=root,
            cwd=cwd,
            source_environment=_base_source_environment(),
        )

    assert caught.value.code == "WORKER_DISPOSABLE_STATE_UNSAFE"
    assert "ambient.txt" not in str(caught.value)
    assert str(root) not in str(caught.value)


@pytest.mark.parametrize("cwd_kind", ["relative", "missing", "outside"])
def test_uncontrolled_cwd_fails_closed(tmp_path: Path, cwd_kind: str) -> None:
    root = tmp_path / "disposable"
    root.mkdir()
    if cwd_kind == "relative":
        cwd = Path("relative-cwd")
    elif cwd_kind == "missing":
        cwd = root / "missing"
    else:
        cwd = tmp_path / "outside"
        cwd.mkdir()

    with pytest.raises(WorkerProcessError) as caught:
        prepare_worker_environment(
            disposable_root=root,
            cwd=cwd,
            source_environment=_base_source_environment(),
        )

    assert caught.value.code == "WORKER_CWD_UNSAFE"
    assert str(cwd) not in str(caught.value)


def test_reparse_or_junction_cwd_fails_closed_with_injected_probe(tmp_path: Path) -> None:
    root, cwd = _paths(tmp_path)

    with pytest.raises(WorkerProcessError) as caught:
        prepare_worker_environment(
            disposable_root=root,
            cwd=cwd,
            source_environment=_base_source_environment(),
            _path_contains_reparse=lambda path: Path(path) == cwd.resolve(),
        )

    assert caught.value.code == "WORKER_REPARSE_PATH"
    assert str(cwd) not in str(caught.value)


def test_source_environment_mutation_after_prepare_cannot_change_launch_snapshot(
    tmp_path: Path,
) -> None:
    root, cwd = _paths(tmp_path)
    source = _base_source_environment()
    prepared = prepare_worker_environment(
        disposable_root=root,
        cwd=cwd,
        source_environment=source,
    )
    frozen = dict(prepared.environment)

    source["OPENAI_API_KEY"] = "late-secret"
    source["PATH"] = "late-mutated-path"

    assert dict(prepared.environment) == frozen
    assert "OPENAI_API_KEY" not in prepared.environment
    assert prepared.environment["PATH"] != "late-mutated-path"


def test_attestation_is_frozen_and_environment_mapping_is_immutable(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)

    with pytest.raises(dataclasses.FrozenInstanceError):
        prepared.environment_sha256 = "0" * 64  # type: ignore[misc]
    with pytest.raises(TypeError):
        prepared.environment["OPENAI_API_KEY"] = "secret"  # type: ignore[index]


def test_windows_environment_case_collision_is_rejected(tmp_path: Path) -> None:
    root, cwd = _paths(tmp_path)
    source = _base_source_environment()
    source["Path"] = "ambiguous"

    with pytest.raises(WorkerProcessError) as caught:
        prepare_worker_environment(
            disposable_root=root,
            cwd=cwd,
            source_environment=source,
        )

    assert caught.value.code == "WORKER_ENV_AMBIGUOUS"


def test_environment_attestation_is_order_deterministic(tmp_path: Path) -> None:
    first_root, first_cwd = _paths(tmp_path / "first")
    second_root, second_cwd = _paths(tmp_path / "second")
    source = _base_source_environment()
    reversed_source = dict(reversed(list(source.items())))

    first = prepare_worker_environment(
        disposable_root=first_root,
        cwd=first_cwd,
        source_environment=source,
    )
    second = prepare_worker_environment(
        disposable_root=second_root,
        cwd=second_cwd,
        source_environment=reversed_source,
    )

    assert tuple(first.environment) == tuple(second.environment)
    assert first.environment_keys == second.environment_keys


def test_launch_rejects_missing_executable_before_job_creation(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    api = _FakeProcessApi()

    with pytest.raises(WorkerProcessError) as caught:
        launch_worker_process(
            environment=prepared,
            executable=tmp_path / "missing.exe",
            argv=(),
            cleanup_deadline_seconds=1.0,
            max_processes=4,
            _process_api=api,
        )

    assert caught.value.code == "WORKER_EXECUTABLE_UNSAFE"
    assert api.events == []


@pytest.mark.parametrize(
    ("deadline", "max_processes"),
    [
        (0.0, 4),
        (-1.0, 4),
        (float("nan"), 4),
        (float("inf"), 4),
        (31.0, 4),
        (1.0, 0),
        (1.0, -1),
        (1.0, 65),
    ],
)
def test_invalid_limits_fail_before_launch(
    tmp_path: Path, deadline: float, max_processes: int
) -> None:
    prepared = _prepared(tmp_path)
    api = _FakeProcessApi()

    with pytest.raises(WorkerProcessError) as caught:
        launch_worker_process(
            environment=prepared,
            executable=Path(sys.executable).resolve(),
            argv=("-c", "pass"),
            cleanup_deadline_seconds=deadline,
            max_processes=max_processes,
            _process_api=api,
        )

    assert caught.value.code == "WORKER_LIMIT_INVALID"
    assert api.events == []


@pytest.mark.parametrize(
    ("stage", "expected_code"),
    [
        ("create_job", "WORKER_JOB_CREATE_FAILED"),
        ("configure_job", "WORKER_JOB_CONFIG_FAILED"),
        ("create_process", "WORKER_LAUNCH_FAILED"),
        ("assign_process", "WORKER_JOB_ASSIGN_FAILED"),
        ("resume_process", "WORKER_RESUME_FAILED"),
    ],
)
def test_partial_launch_failures_are_sanitized_and_cleanup_owned_resources(
    tmp_path: Path, stage: str, expected_code: str
) -> None:
    prepared = _prepared(tmp_path)
    api = _FakeProcessApi()
    api.fail_stage = stage

    with pytest.raises(WorkerProcessError) as caught:
        launch_worker_process(
            environment=prepared,
            executable=Path(sys.executable).resolve(),
            argv=("-c", "pass"),
            cleanup_deadline_seconds=1.0,
            max_processes=4,
            _process_api=api,
        )

    assert caught.value.code == expected_code
    assert "FAKE_SECRET" not in str(caught.value)
    assert "customer" not in str(caught.value).lower()
    if stage in {"assign_process", "resume_process"}:
        assert "process-handle" in api.closed
        assert "thread-handle" in api.closed
        assert "job-handle" in api.closed
    if stage == "assign_process":
        assert "terminate_process" in api.events
    if stage == "resume_process":
        assert "terminate_job" in api.events


def test_successful_launch_attests_root_job_membership(tmp_path: Path) -> None:
    api = _FakeProcessApi()
    handle = _launch_fake(tmp_path, api=api)

    identity = handle.snapshot_process_tree()

    assert isinstance(identity, ProcessTreeIdentity)
    assert identity.root_pid == api.root_pid
    assert identity.member_pids == (api.root_pid,)
    assert identity.verified is True
    assert identity.member_count == 1


def test_child_and_grandchild_membership_is_accounted_for(tmp_path: Path) -> None:
    api = _FakeProcessApi()
    api.query_results = [(4101, 4102, 4103)]
    handle = _launch_fake(tmp_path, api=api)

    identity = handle.snapshot_process_tree()

    assert identity.member_pids == (4101, 4102, 4103)
    assert identity.member_count == 3


def test_root_exit_with_surviving_grandchild_is_not_clean(tmp_path: Path) -> None:
    api = _FakeProcessApi()
    api.query_results = [(4103,), (4103,), ()]
    handle = _launch_fake(tmp_path, api=api)

    before = handle.snapshot_process_tree()
    result = cleanup_worker_process(
        handle,
        _clock=_FakeClock(0.0, 0.1, 0.2),
        _sleep=lambda _seconds: None,
    )

    assert before.root_pid not in before.member_pids
    assert before.member_pids == (4103,)
    assert result.success is True
    assert result.status == "CLEANUP_SUCCEEDED"
    assert result.survivor_pids == ()


def test_cleanup_with_survivor_past_deadline_is_sticky_failure(tmp_path: Path) -> None:
    api = _FakeProcessApi()
    api.query_results = [(4101, 4102), (4102,), (4102,), ()]
    handle = _launch_fake(
        tmp_path,
        api=api,
        cleanup_deadline_seconds=0.25,
    )

    first = cleanup_worker_process(
        handle,
        _clock=_FakeClock(0.0, 0.3),
        _sleep=lambda _seconds: None,
    )
    second = cleanup_worker_process(
        handle,
        _clock=_FakeClock(1.0, 1.1),
        _sleep=lambda _seconds: None,
    )

    assert first.status == "CLEANUP_FAILED"
    assert first.success is False
    assert first.promotion_safe is False
    assert first.survivor_pids == (4102,)
    assert second.status == "CLEANUP_FAILED"
    assert second.success is False
    assert second.promotion_safe is False


def test_cleanup_is_idempotent_after_verified_success(tmp_path: Path) -> None:
    api = _FakeProcessApi()
    api.query_results = [(4101,), ()]
    handle = _launch_fake(tmp_path, api=api)

    first = cleanup_worker_process(
        handle,
        _clock=_FakeClock(0.0, 0.1),
        _sleep=lambda _seconds: None,
    )
    events_after_first = list(api.events)
    second = cleanup_worker_process(
        handle,
        _clock=_FakeClock(1.0, 1.1),
        _sleep=lambda _seconds: None,
    )

    assert first == second
    assert first.status == "CLEANUP_SUCCEEDED"
    assert api.events == events_after_first


@pytest.mark.parametrize(
    "bad_evidence",
    [
        RuntimeError("query unsupported SECRET"),
        None,
        (4101, "bad-pid"),
        (-7,),
        tuple(range(100, 170)),
    ],
)
def test_unsupported_or_malformed_job_evidence_fails_closed(
    tmp_path: Path, bad_evidence: object
) -> None:
    api = _FakeProcessApi()
    api.query_results = [bad_evidence]
    handle = _launch_fake(tmp_path, api=api, max_processes=8)

    result = cleanup_worker_process(
        handle,
        _clock=_FakeClock(0.0, 0.1),
        _sleep=lambda _seconds: None,
    )

    assert result.status == "CLEANUP_FAILED"
    assert result.success is False
    assert result.promotion_safe is False
    assert result.error_code == "WORKER_TREE_EVIDENCE_UNAVAILABLE"
    assert "SECRET" not in repr(result)


def test_cleanup_close_failure_remains_sanitized_failure(tmp_path: Path) -> None:
    api = _FakeProcessApi()
    api.query_results = [(4101,), ()]
    api.fail_stage = "close_handle"
    handle = _launch_fake(tmp_path, api=api)

    result = cleanup_worker_process(
        handle,
        _clock=_FakeClock(0.0, 0.1),
        _sleep=lambda _seconds: None,
    )

    assert result.status == "CLEANUP_FAILED"
    assert result.success is False
    assert result.promotion_safe is False
    assert result.error_code == "WORKER_CLEANUP_RESOURCE_CLOSE_FAILED"
    assert "FAKE_SECRET" not in repr(result)


def test_failure_types_have_no_raw_stream_or_exception_payload_surface() -> None:
    cleanup_fields = {field.name for field in dataclasses.fields(WorkerCleanupResult)}
    identity_fields = {field.name for field in dataclasses.fields(ProcessTreeIdentity)}

    forbidden = {"stdout", "stderr", "exception", "command", "environment_values"}
    assert cleanup_fields.isdisjoint(forbidden)
    assert identity_fields.isdisjoint(forbidden)


def test_api_surface_has_no_handoff_thread_approval_schema_provider_or_auth_inputs() -> None:
    forbidden_names = {
        "handoff",
        "thread",
        "approval",
        "schema",
        "provider",
        "model",
        "auth",
        "token",
        "credential",
    }
    for callable_object in (
        prepare_worker_environment,
        launch_worker_process,
        cleanup_worker_process,
    ):
        parameter_names = {
            name.lower() for name in inspect.signature(callable_object).parameters
        }
        assert parameter_names.isdisjoint(forbidden_names)


def test_module_has_no_codex_provider_model_autocad_or_file_ipc_imports() -> None:
    tree = ast.parse(SOURCE_MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden_roots = {
        "openai",
        "openai_codex",
        "codex_cli_bin",
        "mcp_integration_lib",
        "autocad_plugin",
        "cad_agent",
    }
    assert {module.split(".", 1)[0] for module in imported}.isdisjoint(forbidden_roots)


def test_module_does_not_import_or_call_existing_sdk_probe_owner() -> None:
    source = SOURCE_MODULE.read_text(encoding="utf-8")
    assert "codex_sdk_compat" not in source
    assert "probe_runtime_start" not in source
    assert "run_disposable_probe" not in source


@pytest.mark.skipif(os.name != "nt", reason="supported Windows integration evidence")
def test_real_windows_job_contains_child_and_grandchild_and_cleanup(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    grandchild_code = "import time; time.sleep(60)"
    child_code = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{grandchild_code!r}]);"
        "time.sleep(60)"
    )
    root_code = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{child_code!r}]);"
        "time.sleep(60)"
    )
    handle = launch_worker_process(
        environment=prepared,
        executable=Path(sys.executable).resolve(),
        argv=("-c", root_code),
        cleanup_deadline_seconds=5.0,
        max_processes=8,
    )
    deadline = time.monotonic() + 5.0
    identity = handle.snapshot_process_tree()
    while identity.member_count < 3 and time.monotonic() < deadline:
        time.sleep(0.02)
        identity = handle.snapshot_process_tree()

    assert identity.root_pid == handle.root_pid
    assert identity.member_count >= 3
    result = cleanup_worker_process(handle)
    assert result.status == "CLEANUP_SUCCEEDED"
    assert result.survivor_pids == ()


@pytest.mark.skipif(os.name != "nt", reason="supported Windows junction evidence")
def test_real_windows_junction_escape_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "disposable"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    junction = root / "cwd"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        check=True,
        capture_output=True,
        text=True,
    )

    with pytest.raises(WorkerProcessError) as caught:
        prepare_worker_environment(
            disposable_root=root,
            cwd=junction,
            source_environment=_base_source_environment(),
        )

    assert caught.value.code == "WORKER_REPARSE_PATH"


def test_public_evidence_dataclasses_are_frozen() -> None:
    assert WorkerEnvironmentAttestation.__dataclass_params__.frozen is True
    assert ProcessTreeIdentity.__dataclass_params__.frozen is True
    assert WorkerCleanupResult.__dataclass_params__.frozen is True
