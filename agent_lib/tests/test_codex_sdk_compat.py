from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_lib.codex_sdk_compat import (
    CodexSdkCompatibilityError,
    inspect_codex_sdk,
    probe_runtime_start,
    render_probe_json,
    require_compatible_codex_sdk,
)


def _fake_sdk(tmp_path: Path, version: str = "0.144.4") -> tuple[object, Path, Path]:
    package_root = tmp_path / "site-packages" / "codex_cli_bin"
    package_root.mkdir(parents=True)
    runtime_path = package_root / "vendor" / "win32-x86_64" / "codex.exe"
    runtime_path.parent.mkdir(parents=True)
    runtime_path.write_bytes(b"disposable fake runtime")
    module = SimpleNamespace(
        __version__=version,
        __file__=str(package_root / "__init__.py"),
    )
    return module, runtime_path, package_root


def test_missing_package_fails_closed() -> None:
    def missing_import(_name: str) -> object:
        raise ModuleNotFoundError("openai_codex is not installed")

    report = inspect_codex_sdk(module_loader=missing_import, platform_system="Windows")

    assert report["import_available"] is False
    assert report["status"] == "incompatible"
    with pytest.raises(CodexSdkCompatibilityError, match="import"):
        require_compatible_codex_sdk(module_loader=missing_import, platform_system="Windows")


def test_supported_windows_python_and_bundled_runtime_pass(tmp_path: Path) -> None:
    module, runtime_path, package_root = _fake_sdk(tmp_path)

    report = require_compatible_codex_sdk(
        sdk_module=module,
        platform_system="Windows",
        python_version=(3, 11, 9),
        runtime_path=runtime_path,
        runtime_package_root=package_root,
    )

    assert report["status"] == "compatible"
    assert report["runtime"]["classification"] == "bundled"
    assert report["sdk_version"] == "0.144.4"


@pytest.mark.parametrize(
    ("platform_system", "python_version", "reason"),
    [("Linux", (3, 11, 9), "unsupported_os"), ("Windows", (3, 10, 0), "unsupported_python")],
)
def test_unsupported_platform_or_python_fails_closed(
    tmp_path: Path,
    platform_system: str,
    python_version: tuple[int, int, int],
    reason: str,
) -> None:
    module, runtime_path, package_root = _fake_sdk(tmp_path)

    report = inspect_codex_sdk(
        sdk_module=module,
        platform_system=platform_system,
        python_version=python_version,
        runtime_path=runtime_path,
        runtime_package_root=package_root,
    )

    assert report["status"] == "incompatible"
    assert reason in report["reasons"]
    with pytest.raises(CodexSdkCompatibilityError):
        require_compatible_codex_sdk(
            sdk_module=module,
            platform_system=platform_system,
            python_version=python_version,
            runtime_path=runtime_path,
            runtime_package_root=package_root,
        )


@pytest.mark.parametrize("runtime_value", [None, "", object()])
def test_missing_or_malformed_runtime_fails_closed(
    tmp_path: Path, runtime_value: object
) -> None:
    module, _runtime_path, package_root = _fake_sdk(tmp_path)

    report = inspect_codex_sdk(
        sdk_module=module,
        platform_system="Windows",
        python_version=(3, 11, 9),
        runtime_path=runtime_value,
        runtime_package_root=package_root,
    )

    assert report["status"] == "incompatible"
    assert report["runtime"]["classification"] in {"missing", "malformed"}
    with pytest.raises(CodexSdkCompatibilityError):
        require_compatible_codex_sdk(
            sdk_module=module,
            platform_system="Windows",
            python_version=(3, 11, 9),
            runtime_path=runtime_value,
            runtime_package_root=package_root,
        )


def test_runtime_outside_approved_package_root_fails_closed(tmp_path: Path) -> None:
    module, _runtime_path, package_root = _fake_sdk(tmp_path)
    unapproved = tmp_path / "customer" / "codex.exe"
    unapproved.parent.mkdir()
    unapproved.write_bytes(b"not approved")

    report = inspect_codex_sdk(
        sdk_module=module,
        platform_system="Windows",
        python_version=(3, 11, 9),
        runtime_path=unapproved,
        runtime_package_root=package_root,
    )

    assert report["runtime"]["classification"] == "unapproved"
    assert report["status"] == "incompatible"


def test_probe_json_is_deterministic_and_utf8() -> None:
    payload = {"z": "café", "nested": {"b": 2, "a": 1}, "a": True}

    encoded = render_probe_json(payload)

    assert encoded == '{"a":true,"nested":{"a":1,"b":2},"z":"café"}\n'
    assert encoded.encode("utf-8").decode("utf-8") == encoded
    assert json.loads(encoded) == payload


def test_runtime_probe_timeout_is_explicit_failure() -> None:
    def timed_out_popen(*_args: object, **_kwargs: object) -> TimedOutProcess:
        raise subprocess.TimeoutExpired(cmd="codex", timeout=0.001)

    result = probe_runtime_start(
        Path("codex.exe"), timeout_seconds=0.001, popen_factory=timed_out_popen
    )

    assert result["status"] == "timeout"
    assert result["success"] is False


def test_runtime_probe_startup_failure_is_explicit() -> None:
    class FailedProcess:
        def poll(self) -> int:
            return 17

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 17

    def failed_popen(*_args: object, **_kwargs: object) -> FailedProcess:
        return FailedProcess()

    result = probe_runtime_start(
        Path("codex.exe"), timeout_seconds=0.1, popen_factory=failed_popen
    )

    assert result["status"] == "startup_failed"
    assert result["returncode"] == 17
    assert result["success"] is False


def test_runtime_probe_clean_exit_is_a_successful_start() -> None:
    class CleanProcess:
        def poll(self) -> int:
            return 0

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 0

    def clean_popen(*_args: object, **_kwargs: object) -> CleanProcess:
        return CleanProcess()

    result = probe_runtime_start(
        Path("codex.exe"), timeout_seconds=0.1, popen_factory=clean_popen
    )

    assert result == {
        "returncode": 0,
        "status": "started_and_closed",
        "success": True,
    }


def test_runtime_probe_hanging_process_is_a_timeout_failure() -> None:
    class HangingProcess:
        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> None:
            return None

    def hanging_popen(*_args: object, **_kwargs: object) -> HangingProcess:
        return HangingProcess()

    result = probe_runtime_start(
        Path("codex.exe"), timeout_seconds=0.001, popen_factory=hanging_popen
    )

    assert result == {
        "returncode": None,
        "status": "timeout",
        "success": False,
    }


def test_inspection_does_not_call_authentication_or_model_apis(tmp_path: Path) -> None:
    module, runtime_path, package_root = _fake_sdk(tmp_path)
    calls: list[str] = []

    def forbidden(*_args: object, **_kwargs: object) -> None:
        calls.append("forbidden")
        raise AssertionError("inspection invoked a runtime API")

    module.login_api_key = forbidden
    module.login_chatgpt = forbidden
    module.thread_start = forbidden
    module.models = forbidden

    report = inspect_codex_sdk(
        sdk_module=module,
        platform_system="Windows",
        python_version=(3, 11, 9),
        runtime_path=runtime_path,
        runtime_package_root=package_root,
    )

    assert report["status"] == "compatible"
    assert calls == []
