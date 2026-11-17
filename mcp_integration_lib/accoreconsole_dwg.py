"""Isolated headless AutoCAD 2027 `accoreconsole.exe` DWG-to-DXF read-only adapter.

Adapted from `U-C4N/Autocad-MCP` (`backends/dwg_read.py`, MIT) for AutoCAD 2027
and hardened with `cad_agent.file_integrity` bound non-reparse file custody.
This module does not import `ezdxf`; callers pass any DXF reader callable.
"""

from __future__ import annotations

from collections.abc import Callable
import ctypes
import hashlib
import logging
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, TypeVar
import uuid

from cad_agent.file_integrity import FileIdentityError, is_regular_non_reparse, open_bound_file

log = logging.getLogger(__name__)
T = TypeVar("T")

ACCORECONSOLE_2027_DEFAULT_PATH = r"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe"
ACCORECONSOLE_PATH_ENV = "CAD_AGENT_ACCORECONSOLE_PATH"
ACCORECONSOLE_TIMEOUT_ENV = "CAD_AGENT_ACCORECONSOLE_TIMEOUT_S"
ACCORECONSOLE_STAGING_ENV = "CAD_AGENT_ACCORECONSOLE_STAGING_DIR"

DEFAULT_DXF_VERSION = "2018"
SUPPORTED_DXF_VERSIONS = frozenset({"2010", "2013", "2018"})
LOG_LINES_SHOWN = 40
_DISABLED_VALUES = frozenset({"off", "none", "false", "0", "no"})
_REMOVE_PATIENCE_S = 5.0
_REMOVE_PAUSE_S = 0.1
_COPY_CHUNK_BYTES = 1024 * 1024


class DwgConversionError(RuntimeError):
    """Raised when headless DWG->DXF conversion cannot complete cleanly."""

    def __init__(self, message: str, attempts: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.attempts = [dict(row) for row in (attempts or ())]


def resolve_accoreconsole_exe(executable_path: str | Path | None = None) -> tuple[str | None, str]:
    """Return `(exe_path, "")` when usable regular non-reparse file, else `(None, reason)`."""
    raw = str(executable_path) if executable_path is not None else os.getenv(ACCORECONSOLE_PATH_ENV, "").strip()
    if raw.lower() in _DISABLED_VALUES:
        return None, f"disabled by {ACCORECONSOLE_PATH_ENV}={raw!r}"
    candidate = Path(raw) if raw else Path(ACCORECONSOLE_2027_DEFAULT_PATH)
    try:
        st = os.stat(candidate, follow_symlinks=False)
    except OSError:
        label = f"{ACCORECONSOLE_PATH_ENV}={candidate}" if raw else f"default {candidate}"
        return None, f"accoreconsole executable not found ({label})"
    if not is_regular_non_reparse(st):
        return None, f"accoreconsole executable must be a regular non-reparse file: {candidate}"
    return str(candidate), ""


def resolve_timeout_s(timeout_s: float | None = None, *, default: float = 60.0) -> float:
    """Validate finite positive accoreconsole timeout seconds."""
    raw = timeout_s
    if raw is None:
        env_val = os.getenv(ACCORECONSOLE_TIMEOUT_ENV, "").strip()
        if env_val:
            try:
                raw = float(env_val)
            except ValueError as exc:
                raise ValueError(f"{ACCORECONSOLE_TIMEOUT_ENV} must be a finite positive float") from exc
        else:
            raw = default
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) or float(raw) <= 0.0:
        raise ValueError(f"timeout_s must be a finite positive number, got {raw!r}")
    return float(raw)


def _short_path(path: Path) -> str | None:
    if sys.platform != "win32":
        return None
    try:
        size = ctypes.windll.kernel32.GetShortPathNameW(str(path), None, 0)
        if not size:
            return None
        buf = ctypes.create_unicode_buffer(size)
        if not ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, size):
            return None
        return buf.value
    except (OSError, AttributeError, ValueError):
        return None


def prepare_ascii_staging_root(staging_base: str | Path | None = None) -> Path:
    """Create and validate an ASCII staging directory (`<base>/accore`)."""
    base_raw = (
        Path(staging_base)
        if staging_base is not None
        else Path(os.getenv(ACCORECONSOLE_STAGING_ENV, "").strip() or tempfile.gettempdir())
    )
    root = base_raw / "accore"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DwgConversionError(f"cannot create staging directory {root}: {exc}") from exc
    text = str(root)
    if not text.isascii():
        short = _short_path(root)
        if not short or not short.isascii():
            raise DwgConversionError(
                f"staging directory must resolve to an ASCII path (or 8.3 short path): {root}"
            )
        text = short
    return Path(text)


def build_dwg_to_dxf_script(out_dxf: str | Path, *, dxf_version: str = DEFAULT_DXF_VERSION) -> str:
    """Build a strictly constrained ASCII `_SAVEAS _DXF` script without caller strings."""
    if dxf_version not in SUPPORTED_DXF_VERSIONS:
        raise ValueError(f"Unsupported DXF export version: {dxf_version!r}")
    target = str(out_dxf)
    if (
        not target
        or not target.isascii()
        or any(ch in target for ch in ('"', ";", "\n", "\r", "\x00"))
        or any(ord(ch) < 32 for ch in target)
    ):
        raise ValueError(f"Refusing unsafe accoreconsole output path: {target!r}")
    lines = ["_SAVEAS", "_DXF", "_V", f"_{dxf_version}", "16", f'"{target}"', "_QUIT", "_Y"]
    return "\r\n".join(lines) + "\r\n"


def decode_console_log(raw: bytes) -> list[str]:
    """Decode `accoreconsole.exe` UTF-16LE (BOM or BOM-less) or UTF-8 stdout bytes."""
    if raw.startswith(b"\xff\xfe"):
        text = raw[2:].decode("utf-16-le", errors="replace")
    elif len(raw) >= 2 and raw[1::2].count(0) * 2 >= len(raw) // 2:
        text = raw.decode("utf-16-le", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")
    text = text.replace("\x00", "")
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def _copy_bound_dwg(source: Path, destination: Path) -> str:
    """Copy a bound regular non-reparse source DWG into isolated staging, returning SHA-256."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    try:
        fd, _st = open_bound_file(source, flags=flags, label="source_dwg")
    except FileIdentityError as exc:
        raise DwgConversionError(f"unsafe or missing source DWG {source}: {exc}") from exc
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "rb") as src_f, open(destination, "wb") as dst_f:
            while True:
                chunk = src_f.read(_COPY_CHUNK_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
                dst_f.write(chunk)
    except OSError as exc:
        raise DwgConversionError(f"failed copying source DWG to isolated staging: {exc}") from exc
    return digest.hexdigest()


def _kill_tree(proc: subprocess.Popen[Any]) -> None:
    if sys.platform == "win32":
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
        try:
            subprocess.run(
                [str(taskkill), "/F", "/T", "/PID", str(proc.pid)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("taskkill of accoreconsole pid %s failed: %s", proc.pid, exc)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        log.warning("accoreconsole pid %s did not exit after kill", proc.pid)


def _remove_staging(folder: Path) -> bool:
    deadline = time.monotonic() + _REMOVE_PATIENCE_S
    while True:
        shutil.rmtree(folder, ignore_errors=True)
        if not folder.exists():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(_REMOVE_PAUSE_S)


def convert_dwg_to_dxf_and_read(
    source_dwg: str | Path,
    read_dxf: Callable[[Path], T],
    *,
    staging_base: str | Path | None = None,
    executable_path: str | Path | None = None,
    timeout_s: float | None = None,
    dxf_version: str = DEFAULT_DXF_VERSION,
) -> tuple[T, dict[str, Any]]:
    """Copy a `.dwg` safely to isolated ASCII staging, convert to DXF, and apply `read_dxf`.

    `source_dwg` path is never passed to `accoreconsole.exe` or embedded in the script,
    isolating `acaddoc.lsp` search paths and Unicode paths. Caller's `.dwg` stays untouched.
    """
    src_path = Path(source_dwg)
    if src_path.suffix.casefold() != ".dwg":
        raise ValueError(f"Expected a .dwg path, got {src_path.name!r}")
    effective_timeout = resolve_timeout_s(timeout_s)
    exe, why = resolve_accoreconsole_exe(executable_path)
    if exe is None:
        raise DwgConversionError(why, [{"route": "accoreconsole", "reason": why}])
    root = prepare_ascii_staging_root(staging_base)
    folder = root / uuid.uuid4().hex[:12]
    folder.mkdir()
    attempt: dict[str, Any] = {"route": "accoreconsole", "timeout_s": effective_timeout}
    started = time.monotonic()
    try:
        staged_dwg = folder / "in.dwg"
        staged_dxf = folder / "out.dxf"
        script_path = folder / "convert.scr"
        log_path = folder / "accore.log"
        attempt["source_sha256"] = _copy_bound_dwg(src_path, staged_dwg)
        script_path.write_bytes(
            build_dwg_to_dxf_script(staged_dxf, dxf_version=dxf_version).encode("ascii")
        )
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with open(log_path, "wb") as log_handle:
            try:
                proc = subprocess.Popen(
                    [exe, "/i", str(staged_dwg), "/s", str(script_path)],
                    cwd=str(folder),
                    stdin=subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                    start_new_session=sys.platform != "win32",
                )
            except OSError as exc:
                attempt["reason"] = f"accoreconsole could not start ({type(exc).__name__}: {exc})"
                raise DwgConversionError(attempt["reason"], [attempt]) from exc
            try:
                attempt["exit_code"] = proc.wait(timeout=effective_timeout)
                attempt["timed_out"] = False
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                attempt["exit_code"] = proc.returncode
                attempt["timed_out"] = True
        attempt["seconds"] = round(time.monotonic() - started, 3)
        lines = decode_console_log(log_path.read_bytes()) if log_path.exists() else []
        attempt["log_tail"] = lines[-LOG_LINES_SHOWN:]
        attempt["log_lines"] = len(lines)
        if attempt["timed_out"]:
            attempt["reason"] = f"timed_out after {effective_timeout:g}s"
            raise DwgConversionError(attempt["reason"], [attempt])
        if attempt["exit_code"] != 0:
            attempt["reason"] = f"accoreconsole failed with exit code {attempt['exit_code']}"
            raise DwgConversionError(attempt["reason"], [attempt])
        if not staged_dxf.is_file() or staged_dxf.stat().st_size == 0:
            attempt["reason"] = "accoreconsole produced no output DXF"
            raise DwgConversionError(attempt["reason"], [attempt])
        try:
            result = read_dxf(staged_dxf)
        except Exception as exc:
            attempt["reason"] = f"converted DXF readback failed ({type(exc).__name__}: {exc})"
            raise DwgConversionError(attempt["reason"], [attempt]) from exc
        return result, attempt
    finally:
        _remove_staging(folder)
