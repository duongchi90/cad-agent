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
FORBIDDEN_PARENT_NAMES = {
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
}


class _FakeClock:
    def __init__(self, *values: float) -> None:
        self.values = iter(values)
        self.last = 0.0

    def __call__(self) -> float:
        try:
            self.last = next(self.values)
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

    def _stage(self, name: str) -> None:
        self.events.append(name)
        if self.fail_stage == name:
            raise RuntimeError("FAKE_SECRET C:\\customer\\private\\drawing.dwg")

    def create_job(self, max_processes: int) -> object:
        assert max_processes > 0
        self._stage("create_job")
        return "job-handle"

    def configure_job(self, job_handle: object, max_processes: int) -> None:
        assert job_handle == "job-handle" and max_processes > 0
        self._stage("configure_job")

    def create_suspended_process(
        self,
        *,
        executable: Path,
        argv: tuple[str, ...],
        cwd: Path,
        environment: Mapping[str, str],
    ) -> object:
        assert executable.is_absolute() and cwd.is_absolute()
        assert isinstance(argv, tuple) and "CODEX_HOME" in environment
        self._stage("create_process")
        return SimpleNamespace(
            process_handle="process-handle",
            thread_handle="thread-handle",
            pid=self.root_pid,
        )

    def assign_process(self, job_handle: object, process_handle: object) -> None:
        assert job_handle == "job-handle" and process_handle == "process-handle"
        self._stage("assign_process")

    def resume_process(self, thread_handle: object) -> None:
        assert thread_handle == "thread-handle"
        self._stage("resume_process")

    def query_job_process_ids(
        self, job_handle: object, *, max_processes: int
    ) -> tuple[int, ...]:
        assert job_handle == "job-handle" and max_processes > 0
        self._stage("query_job")
        if not self.query_results:
            return (self.root_pid,)
        result = self.query_results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result  # type: ignore[return-value]

    def terminate_job(self, job_handle: object) -> None:
        assert job_handle == "job-handle"
        self._stage("terminate_job")

    def terminate_process(self, process_handle: object) -> None:
        assert process_handle == "process-handle"
        self._stage("terminate_process")

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


def _source_env() -> dict[str, str]:
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
        source_environment=_source_env(),
    )


def _launch_fake(
    tmp_path: Path,
    *,
    api: _FakeProcessApi | None = None,
    deadline: float = 0.25,
    max_processes: int = 8,
) -> WorkerProcessHandle:
    return launch_worker_process(
        environment=_prepared(tmp_path),
        executable=Path(sys.executable).resolve(),
        argv=("-c", "pass"),
        cleanup_deadline_seconds=deadline,
        max_processes=max_processes,
        _process_api=api or _FakeProcessApi(),
    )


def test_environment_starts_empty_and_filters_parent_secrets_and_config(tmp_path: Path) -> None:
    root, cwd = _paths(tmp_path)
    source = _source_env()
    source.update({name: "SECRET_VALUE" for name in FORBIDDEN_PARENT_NAMES})
    source.update(
        {
            "CODEX_HOME": r"C:\Users\customer\.codex",
            "UNRELATED": "not-allowlisted",
        }
    )

    prepared = prepare_worker_environment(
        disposable_root=root,
        cwd=cwd,
        source_environment=source,
    )

    child = dict(prepared.environment)
    assert {name.upper() for name in child}.isdisjoint(FORBIDDEN_PARENT_NAMES)
    assert "UNRELATED" not in child
    assert set(child).issuperset({"CODEX_HOME", "TEMP", "TMP"})
    assert child["CODEX_HOME"] != source["CODEX_HOME"]
    for name in ("CODEX_HOME", "TEMP", "TMP"):
        assert Path(child[name]).is_relative_to(root.resolve())

def test_worker_owned_directories_are_fresh_empty_and_disposable(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    assert prepared.codex_home.is_dir() and prepared.temp_dir.is_dir()
    assert not list(prepared.codex_home.iterdir())
    assert not list(prepared.temp_dir.iterdir())
    assert set(prepared.writable_roots) == {
        prepared.cwd,
        prepared.codex_home,
        prepared.temp_dir,
    }


@pytest.mark.parametrize("name", ["codex-home", "tmp"])
def test_preexisting_worker_owned_state_is_rejected(tmp_path: Path, name: str) -> None:
    root, cwd = _paths(tmp_path)
    path = root / name
    path.mkdir()
    (path / "ambient.txt").write_text("ambient", encoding="utf-8")
    with pytest.raises(WorkerProcessError) as caught:
        prepare_worker_environment(
            disposable_root=root,
            cwd=cwd,
            source_environment=_source_env(),
        )
    assert caught.value.code == "WORKER_DISPOSABLE_STATE_UNSAFE"
    assert "ambient" not in str(caught.value) and str(root) not in str(caught.value)


@pytest.mark.parametrize("kind", ["relative", "missing", "outside"])
def test_uncontrolled_cwd_is_rejected(tmp_path: Path, kind: str) -> None:
    root = tmp_path / "disposable"
    root.mkdir()
    cwd = {
        "relative": Path("relative-cwd"),
        "missing": root / "missing",
        "outside": tmp_path / "outside",
    }[kind]
    if kind == "outside":
        cwd.mkdir()
    with pytest.raises(WorkerProcessError) as caught:
        prepare_worker_environment(
            disposable_root=root,
            cwd=cwd,
            source_environment=_source_env(),
        )
    assert caught.value.code == "WORKER_CWD_UNSAFE"
    assert str(cwd) not in str(caught.value)


def test_reparse_or_junction_escape_is_rejected_by_injected_probe(tmp_path: Path) -> None:
    root, cwd = _paths(tmp_path)
    with pytest.raises(WorkerProcessError) as caught:
        prepare_worker_environment(
            disposable_root=root,
            cwd=cwd,
            source_environment=_source_env(),
            _path_contains_reparse=lambda path: Path(path) == cwd.resolve(),
        )
    assert caught.value.code == "WORKER_REPARSE_PATH"


def test_environment_snapshot_is_immutable_after_source_mutation(tmp_path: Path) -> None:
    root, cwd = _paths(tmp_path)
    source = _source_env()
    prepared = prepare_worker_environment(
        disposable_root=root,
        cwd=cwd,
        source_environment=source,
    )
    frozen = dict(prepared.environment)
    source.update({"OPENAI_API_KEY": "late-secret", "PATH": "late-path"})
    assert dict(prepared.environment) == frozen
    assert "OPENAI_API_KEY" not in prepared.environment


def test_attestation_and_environment_are_immutable(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    with pytest.raises(dataclasses.FrozenInstanceError):
        prepared.environment_sha256 = "0" * 64  # type: ignore[misc]
    with pytest.raises(TypeError):
        prepared.environment["OPENAI_API_KEY"] = "secret"  # type: ignore[index]


def test_case_colliding_windows_environment_names_are_rejected(tmp_path: Path) -> None:
    root, cwd = _paths(tmp_path)
    source = _source_env()
    source["Path"] = "ambiguous"
    with pytest.raises(WorkerProcessError) as caught:
        prepare_worker_environment(
            disposable_root=root,
            cwd=cwd,
            source_environment=source,
        )
    assert caught.value.code == "WORKER_ENV_AMBIGUOUS"


def test_environment_key_order_is_deterministic(tmp_path: Path) -> None:
    root1, cwd1 = _paths(tmp_path / "first")
    root2, cwd2 = _paths(tmp_path / "second")
    source = _source_env()
    first = prepare_worker_environment(
        disposable_root=root1, cwd=cwd1, source_environment=source
    )
    second = prepare_worker_environment(
        disposable_root=root2,
        cwd=cwd2,
        source_environment=dict(reversed(list(source.items()))),
    )
    assert tuple(first.environment) == tuple(second.environment)
    assert first.environment_keys == second.environment_keys


def test_missing_executable_fails_before_job_creation(tmp_path: Path) -> None:
    api = _FakeProcessApi()
    with pytest.raises(WorkerProcessError) as caught:
        launch_worker_process(
            environment=_prepared(tmp_path),
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
    api = _FakeProcessApi()
    with pytest.raises(WorkerProcessError) as caught:
        launch_worker_process(
            environment=_prepared(tmp_path),
            executable=Path(sys.executable).resolve(),
            argv=("-c", "pass"),
            cleanup_deadline_seconds=deadline,
            max_processes=max_processes,
            _process_api=api,
        )
    assert caught.value.code == "WORKER_LIMIT_INVALID"
    assert api.events == []


@pytest.mark.parametrize(
    ("stage", "code"),
    [
        ("create_job", "WORKER_JOB_CREATE_FAILED"),
        ("configure_job", "WORKER_JOB_CONFIG_FAILED"),
        ("create_process", "WORKER_LAUNCH_FAILED"),
        ("assign_process", "WORKER_JOB_ASSIGN_FAILED"),
        ("resume_process", "WORKER_RESUME_FAILED"),
    ],
)
def test_partial_launch_failure_is_sanitized_and_resources_are_closed(
    tmp_path: Path, stage: str, code: str
) -> None:
    api = _FakeProcessApi()
    api.fail_stage = stage
    with pytest.raises(WorkerProcessError) as caught:
        launch_worker_process(
            environment=_prepared(tmp_path),
            executable=Path(sys.executable).resolve(),
            argv=("-c", "pass"),
            cleanup_deadline_seconds=1.0,
            max_processes=4,
            _process_api=api,
        )
    assert caught.value.code == code
    assert "FAKE_SECRET" not in str(caught.value) and "customer" not in str(caught.value)
    if stage in {"assign_process", "resume_process"}:
        assert {"process-handle", "thread-handle", "job-handle"}.issubset(api.closed)
    if stage == "assign_process":
        assert "terminate_process" in api.events
    if stage == "resume_process":
        assert "terminate_job" in api.events


def test_process_tree_identity_accounts_for_root_child_and_grandchild(tmp_path: Path) -> None:
    api = _FakeProcessApi()
    api.query_results = [(4101, 4102, 4103)]
    identity = _launch_fake(tmp_path, api=api).snapshot_process_tree()
    assert identity == ProcessTreeIdentity(
        root_pid=4101,
        member_pids=(4101, 4102, 4103),
        member_count=3,
        verified=True,
    )


def test_root_exit_with_surviving_grandchild_is_not_treated_as_clean(tmp_path: Path) -> None:
    api = _FakeProcessApi()
    api.query_results = [(4103,), (4103,), ()]
    handle = _launch_fake(tmp_path, api=api)
    before = handle.snapshot_process_tree()
    result = cleanup_worker_process(
        handle, _clock=_FakeClock(0.0, 0.1, 0.2), _sleep=lambda _: None
    )
    assert before.member_pids == (4103,) and handle.root_pid not in before.member_pids
    assert result.status == "CLEANUP_SUCCEEDED" and result.survivor_pids == ()


def test_cleanup_timeout_with_survivor_is_sticky_failure(tmp_path: Path) -> None:
    api = _FakeProcessApi()
    api.query_results = [(4101, 4102), (4102,), ()]
    handle = _launch_fake(tmp_path, api=api, deadline=0.25)
    first = cleanup_worker_process(
        handle, _clock=_FakeClock(0.0, 0.3), _sleep=lambda _: None
    )
    second = cleanup_worker_process(
        handle, _clock=_FakeClock(1.0, 1.1), _sleep=lambda _: None
    )
    assert first.status == "CLEANUP_FAILED" and first.survivor_pids == (4102,)
    assert first.promotion_safe is False and second == first


def test_cleanup_is_idempotent_after_verified_success(tmp_path: Path) -> None:
    api = _FakeProcessApi()
    api.query_results = [(4101,), ()]
    handle = _launch_fake(tmp_path, api=api)
    first = cleanup_worker_process(
        handle, _clock=_FakeClock(0.0, 0.1), _sleep=lambda _: None
    )
    events = list(api.events)
    second = cleanup_worker_process(
        handle, _clock=_FakeClock(1.0, 1.1), _sleep=lambda _: None
    )
    assert first == second and first.status == "CLEANUP_SUCCEEDED"
    assert api.events == events


@pytest.mark.parametrize(
    "evidence",
    [
        RuntimeError("query unsupported SECRET"),
        None,
        (4101, "bad-pid"),
        (-7,),
        tuple(range(100, 170)),
    ],
)
def test_unsupported_or_malformed_job_evidence_fails_closed(
    tmp_path: Path, evidence: object
) -> None:
    api = _FakeProcessApi()
    api.query_results = [evidence]
    result = cleanup_worker_process(
        _launch_fake(tmp_path, api=api, max_processes=8),
        _clock=_FakeClock(0.0, 0.1),
        _sleep=lambda _: None,
    )
    assert result.status == "CLEANUP_FAILED" and result.promotion_safe is False
    assert result.error_code == "WORKER_TREE_EVIDENCE_UNAVAILABLE"
    assert "SECRET" not in repr(result)


def test_cleanup_resource_close_failure_remains_sanitized_failure(tmp_path: Path) -> None:
    api = _FakeProcessApi()
    api.query_results = [(4101,), ()]
    handle = _launch_fake(tmp_path, api=api)
    api.fail_stage = "close_handle"
    result = cleanup_worker_process(
        handle, _clock=_FakeClock(0.0, 0.1), _sleep=lambda _: None
    )
    assert result.status == "CLEANUP_FAILED" and result.promotion_safe is False
    assert result.error_code == "WORKER_CLEANUP_RESOURCE_CLOSE_FAILED"
    assert "FAKE_SECRET" not in repr(result)


def test_failure_evidence_has_no_raw_stream_command_or_exception_fields() -> None:
    forbidden = {"stdout", "stderr", "exception", "command", "environment_values"}
    assert {field.name for field in dataclasses.fields(WorkerCleanupResult)}.isdisjoint(
        forbidden
    )
    assert {field.name for field in dataclasses.fields(ProcessTreeIdentity)}.isdisjoint(
        forbidden
    )


def test_api_surface_has_no_task4_or_authority_inputs() -> None:
    forbidden = {
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
    for func in (prepare_worker_environment, launch_worker_process, cleanup_worker_process):
        names = {name.lower() for name in inspect.signature(func).parameters}
        assert names.isdisjoint(forbidden)


def test_module_has_no_sdk_provider_model_autocad_file_ipc_or_cad_agent_imports() -> None:
    tree = ast.parse(SOURCE_MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {
        "openai",
        "openai_codex",
        "codex_cli_bin",
        "mcp_integration_lib",
        "autocad_plugin",
        "cad_agent",
    }
    assert {name.split(".", 1)[0] for name in imported}.isdisjoint(forbidden)
    source = SOURCE_MODULE.read_text(encoding="utf-8")
    assert "codex_sdk_compat" not in source
    assert "probe_runtime_start" not in source
    assert "run_disposable_probe" not in source


@pytest.mark.skipif(os.name != "nt", reason="supported Windows integration evidence")
def test_real_windows_job_contains_child_and_grandchild_and_cleans_tree(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    grandchild = "import time; time.sleep(60)"
    child = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{grandchild!r}]);"
        "time.sleep(60)"
    )
    root_code = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{child!r}]);"
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
    assert identity.member_count >= 3 and identity.root_pid == handle.root_pid
    result = cleanup_worker_process(handle)
    assert result.status == "CLEANUP_SUCCEEDED" and result.survivor_pids == ()


@pytest.mark.skipif(os.name != "nt", reason="supported Windows junction evidence")
def test_real_windows_junction_escape_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "disposable"
    outside = tmp_path / "outside"
    root.mkdir()
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
            source_environment=_source_env(),
        )
    assert caught.value.code == "WORKER_REPARSE_PATH"


def test_public_evidence_dataclasses_are_frozen() -> None:
    assert WorkerEnvironmentAttestation.__dataclass_params__.frozen is True
    assert ProcessTreeIdentity.__dataclass_params__.frozen is True
    assert WorkerCleanupResult.__dataclass_params__.frozen is True


def _test_environment_digest(environment: Mapping[str, str]) -> str:
    import hashlib
    import json

    payload = json.dumps(
        sorted(environment.items(), key=lambda item: item[0].casefold()),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize(
    "forgery",
    [
        "unauthorized_key",
        "environment_keys",
        "codex_home_value",
        "temp_tmp_values",
        "writable_roots",
    ],
)
def test_launch_rejects_forged_self_consistent_environment_attestation(
    tmp_path: Path, forgery: str
) -> None:
    prepared = _prepared(tmp_path)
    forged_environment = dict(prepared.environment)
    environment_keys = prepared.environment_keys
    writable_roots = prepared.writable_roots

    if forgery == "unauthorized_key":
        forged_environment["OPENAI_API_KEY"] = "forged-secret"
        environment_keys = tuple(
            sorted(forged_environment, key=lambda name: name.casefold())
        )
    elif forgery == "environment_keys":
        environment_keys = tuple(reversed(prepared.environment_keys))
    elif forgery == "codex_home_value":
        forged_environment["CODEX_HOME"] = str(prepared.cwd)
    elif forgery == "temp_tmp_values":
        forged_environment["TEMP"] = str(prepared.cwd)
        forged_environment["TMP"] = str(prepared.cwd)
    else:
        writable_roots = (prepared.codex_home, prepared.temp_dir)

    forged = dataclasses.replace(
        prepared,
        environment=forged_environment,
        environment_keys=environment_keys,
        environment_sha256=_test_environment_digest(forged_environment),
        writable_roots=writable_roots,
    )
    assert forged.environment_sha256 == _test_environment_digest(forged.environment)

    api = _FakeProcessApi()
    with pytest.raises(WorkerProcessError) as caught:
        launch_worker_process(
            environment=forged,
            executable=Path(sys.executable).resolve(),
            argv=("-c", "pass"),
            cleanup_deadline_seconds=1.0,
            max_processes=4,
            _process_api=api,
        )
    assert caught.value.code == "WORKER_ENV_ATTESTATION_MISMATCH"
    assert "forged-secret" not in str(caught.value)
    assert api.events == []


@pytest.mark.parametrize(
    "name", ["PATH", "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT"]
)
def test_prepare_rejects_embedded_nul_in_allowlisted_environment_value(
    tmp_path: Path, name: str
) -> None:
    root, cwd = _paths(tmp_path)
    source = _source_env()
    source[name] = "trusted\x00OPENAI_API_KEY=injected-secret"

    with pytest.raises(WorkerProcessError) as caught:
        prepare_worker_environment(
            disposable_root=root,
            cwd=cwd,
            source_environment=source,
        )
    assert caught.value.code == "WORKER_ENV_INVALID"
    assert "injected-secret" not in str(caught.value)
