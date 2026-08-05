"""Fail-closed, optional compatibility checks for the official Codex SDK.

This module deliberately does not expose a production client or turn runner.
Inspection reads package metadata and the pinned runtime location only. The
runtime probe is reserved for the disposable command-line spike.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

SDK_PACKAGE = "openai-codex"
SDK_IMPORT = "openai_codex"
RUNTIME_PACKAGE = "openai-codex-cli-bin"
SUPPORTED_OS = "Windows"
SUPPORTED_PYTHON = (3, 11)
MAX_PROBE_TIMEOUT_SECONDS = 30.0

_MISSING = object()
_PopenFactory = Callable[..., Any]


class CodexSdkCompatibilityError(RuntimeError):
    """Raised when the optional SDK cannot be used safely on this host."""


def _python_version(value: object) -> tuple[int, int, int] | None:
    if value is None:
        info = sys.version_info
        return (info.major, info.minor, info.micro)
    if isinstance(value, str):
        pieces = value.split(".")
        if len(pieces) < 2:
            return None
        try:
            return (int(pieces[0]), int(pieces[1]), int(pieces[2]) if len(pieces) > 2 else 0)
        except ValueError:
            return None
    if isinstance(value, tuple) and len(value) >= 2:
        try:
            return (int(value[0]), int(value[1]), int(value[2]) if len(value) > 2 else 0)
        except (TypeError, ValueError):
            return None
    return None


def _version_text(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _module_root(module: object) -> Path | None:
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, (str, os.PathLike)):
        return None
    try:
        return Path(module_file).resolve().parent
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def _runtime_details(runtime_value: object, package_root: object) -> dict[str, object]:
    if runtime_value is _MISSING or runtime_value is None:
        return {"available": False, "classification": "missing"}
    if not isinstance(runtime_value, (str, os.PathLike)):
        return {"available": False, "classification": "malformed"}
    try:
        runtime_path = Path(runtime_value)
        if not runtime_path.is_absolute():
            return {"available": False, "classification": "malformed"}
        if not runtime_path.is_file():
            return {"available": False, "classification": "missing"}
        if not isinstance(package_root, (str, os.PathLike)):
            return {"available": False, "classification": "unapproved"}
        root = Path(package_root).resolve()
        resolved = runtime_path.resolve()
        if not resolved.is_relative_to(root):
            return {"available": False, "classification": "unapproved"}
    except (OSError, RuntimeError, TypeError, ValueError):
        return {"available": False, "classification": "malformed"}
    return {"available": True, "classification": "bundled"}


def _discover_runtime() -> tuple[object, Path | None]:
    try:
        runtime_module = importlib.import_module("codex_cli_bin")
    except ImportError:
        return _MISSING, None
    path_factory = getattr(runtime_module, "bundled_codex_path", None)
    if not callable(path_factory):
        return object(), _module_root(runtime_module)
    try:
        return path_factory(), _module_root(runtime_module)
    except Exception:
        return object(), _module_root(runtime_module)


def _load_sdk(module_loader: Callable[[str], object] | None, sdk_module: object) -> object:
    if sdk_module is not _MISSING:
        return sdk_module
    loader = module_loader or importlib.import_module
    return loader(SDK_IMPORT)


def inspect_codex_sdk(
    *,
    sdk_module: object = _MISSING,
    module_loader: Callable[[str], object] | None = None,
    sdk_version: object = _MISSING,
    python_version: object = None,
    platform_system: str | None = None,
    runtime_path: object = _MISSING,
    runtime_package_root: object = _MISSING,
) -> dict[str, object]:
    """Inspect the SDK without constructing a client or starting a runtime."""

    system = platform_system if platform_system is not None else platform.system()
    version_info = _python_version(python_version)
    version_text = (
        _version_text(sdk_version)
        if sdk_version is not _MISSING
        else None
    )
    import_available = True
    module: object = _MISSING
    reasons: list[str] = []
    try:
        module = _load_sdk(module_loader, sdk_module)
    except ImportError:
        import_available = False
        reasons.append("missing_import")
    except Exception:
        import_available = False
        reasons.append("import_error")

    if import_available and version_text is None:
        version_text = _version_text(getattr(module, "__version__", None))
    if import_available and version_text is None:
        try:
            version_text = _version_text(importlib.metadata.version(SDK_PACKAGE))
        except importlib.metadata.PackageNotFoundError:
            reasons.append("missing_sdk_metadata")
        except Exception:
            reasons.append("malformed_sdk_metadata")
    if import_available and version_text is None and "missing_sdk_metadata" not in reasons:
        reasons.append("malformed_sdk_version")

    if system != SUPPORTED_OS:
        reasons.append("unsupported_os")
    if version_info is None or version_info[:2] != SUPPORTED_PYTHON:
        reasons.append("unsupported_python")

    package_root: object = None if runtime_package_root is _MISSING else runtime_package_root
    if runtime_path is _MISSING:
        runtime_value, discovered_root = _discover_runtime()
        if package_root is None:
            package_root = discovered_root
    else:
        runtime_value = runtime_path
    runtime = _runtime_details(runtime_value, package_root)
    classification = runtime["classification"]
    if classification == "missing":
        reasons.append("missing_runtime")
    elif classification == "malformed":
        reasons.append("malformed_runtime")
    elif classification == "unapproved":
        reasons.append("unapproved_runtime")

    report: dict[str, object] = {
        "import_available": import_available,
        "os": system,
        "python_version": ".".join(str(part) for part in version_info) if version_info else None,
        "reasons": sorted(set(reasons)),
        "runtime": runtime,
        "sdk_version": version_text,
        "status": "compatible" if not reasons else "incompatible",
    }
    return report


def require_compatible_codex_sdk(**kwargs: object) -> dict[str, object]:
    """Return an inspection report or reject every unsafe/unknown state."""

    report = inspect_codex_sdk(**kwargs)
    if report["status"] != "compatible":
        reasons = ", ".join(str(reason) for reason in report["reasons"])
        raise CodexSdkCompatibilityError(f"Codex SDK compatibility check failed: {reasons}")
    return report


def render_probe_json(payload: dict[str, object]) -> str:
    """Encode probe output with stable key order and UTF-8 characters."""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _safe_probe_environment() -> dict[str, str]:
    environment = {"PATH": os.environ.get("PATH", "")}
    for name in ("SystemRoot", "WINDIR", "TEMP", "TMP"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    return environment


def _stop_process(process: Any) -> None:
    try:
        process.terminate()
        process.wait(timeout=2.0)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def probe_runtime_start(
    runtime_path: Path,
    *,
    timeout_seconds: float = 10.0,
    popen_factory: _PopenFactory = subprocess.Popen,
) -> dict[str, object]:
    """Start and close only the pinned app-server runtime in a disposable cwd."""

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    if timeout_seconds > MAX_PROBE_TIMEOUT_SECONDS:
        raise ValueError("timeout_seconds exceeds the bounded probe limit")
    command = [str(runtime_path), "app-server", "--listen", "stdio://"]
    try:
        process = popen_factory(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=tempfile.gettempdir(),
            env=_safe_probe_environment(),
            text=True,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired:
        return {"returncode": None, "status": "timeout", "success": False}
    except OSError:
        return {"returncode": None, "status": "startup_failed", "success": False}
    try:
        deadline = time.monotonic() + timeout_seconds
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
        returncode = process.poll()
        if returncode is not None:
            if returncode == 0:
                return {
                    "returncode": 0,
                    "status": "started_and_closed",
                    "success": True,
                }
            return {
                "returncode": int(returncode),
                "status": "startup_failed",
                "success": False,
            }
        return {"returncode": None, "status": "timeout", "success": False}
    finally:
        _stop_process(process)


def run_disposable_probe(*, timeout_seconds: float = 10.0) -> dict[str, object]:
    """Run inspection and, when compatible, the bounded disposable start check."""

    inspection = inspect_codex_sdk()
    payload: dict[str, object] = {"inspection": inspection, "mode": "inspect"}
    if inspection["status"] != "compatible":
        return payload
    runtime_path, _root = _discover_runtime()
    if not isinstance(runtime_path, (str, os.PathLike)):
        payload["runtime_start"] = {"status": "missing", "success": False}
        return payload
    payload["mode"] = "start"
    payload["runtime_start"] = probe_runtime_start(
        Path(runtime_path), timeout_seconds=timeout_seconds
    )
    return payload
