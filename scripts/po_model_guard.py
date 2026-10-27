"""On-demand PO configuration repair and exact-turn runtime evidence checks.

No agent creation, inference request, polling service, or production dependency.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import queue
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import threading
import time
import tomllib
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "docs/templates/PO_SOL.toml"
EXPECTED = {"model": "gpt-6-luna", "model_reasoning_effort": "medium"}
PO_MODEL, PO_EFFORT = "gpt-6.1-sol", "high"
AGENTS = {"default_subagent_model": PO_MODEL, "default_subagent_reasoning_effort": PO_EFFORT}


class GuardError(RuntimeError):
    """A bounded PO prerequisite remains unverified; routine work may continue."""


def _parse(data: bytes) -> dict:
    try:
        return tomllib.loads(data.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as error:
        raise GuardError("invalid configuration; preserved without repair") from error


def _setting(text: str, section: str | None, key: str, value: str) -> str:
    headers = list(re.finditer(r"(?m)^\s*\[[^\n]+\][ \t]*(?:#.*)?$", text))
    start, end = 0, headers[0].start() if headers else len(text)
    if section:
        found = next((i for i, h in enumerate(headers) if h.group().strip().split('#')[0].strip() == f"[{section}]"), None)
        if found is None:
            text += f"\n[{section}]\n"
            start, end = len(text), len(text)
        else:
            start = headers[found].end()
            end = headers[found + 1].start() if found + 1 < len(headers) else len(text)
    part = text[start:end]
    line = f"{key} = {json.dumps(value)}"
    pattern = rf"(?m)^[ \t]*{re.escape(key)}[ \t]*=.*$"
    part = re.sub(pattern, line, part, count=1) if re.search(pattern, part) else part.rstrip('\n') + '\n' + line + '\n'
    return text[:start] + part + text[end:]


def _write(path: Path, data: bytes, before: bytes | None) -> None:
    # Never follow a config/agent junction or symlink into an unrelated target.
    for item in (path, *path.parents):
        if item.exists() and (item.is_symlink() or getattr(item.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise GuardError("reparse/symlink configuration path; repair refused")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.po-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        current = path.read_bytes() if path.exists() else None
        if current != before:
            raise GuardError("configuration changed during repair; retry at next PO boundary")
        os.replace(temporary, path)
        if path.read_bytes() != data:
            raise GuardError("configuration readback failed")
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def ensure_configuration(home: Path, *, repair: bool, read_effective) -> dict:
    path = home / "config.toml"
    before = path.read_bytes() if path.exists() else None
    current = _parse(before or b"")
    if not isinstance(current.get("agents", {}), dict):
        raise GuardError("invalid agents table; configuration preserved")
    expected = {**current, **EXPECTED, "agents": {**current.get("agents", {}), **AGENTS}}
    repaired = []
    if current != expected:
        if not repair:
            raise GuardError("configured model/effort mismatch; run with --repair")
        text = (before or b"").decode("utf-8-sig").replace('\r\n', '\n')
        for key, value in EXPECTED.items():
            text = _setting(text, None, key, value)
        for key, value in AGENTS.items():
            text = _setting(text, "agents", key, value)
        if before and b'\r\n' in before:
            text = text.replace('\n', '\r\n')
        data = text.encode("utf-8-sig" if before and before.startswith(b'\xef\xbb\xbf') else "utf-8")
        if _parse(data) != expected:
            raise GuardError("unsupported TOML layout; configuration preserved")
        _write(path, data, before)
        repaired.append("model defaults")
    role = home / "agents/po-sol.toml"
    baseline = TEMPLATE.read_bytes()
    standard = _parse(baseline)
    if (standard.get("model"), standard.get("model_reasoning_effort")) != (PO_MODEL, PO_EFFORT):
        raise GuardError("PO template identity mismatch")
    prior_role = role.read_bytes() if role.exists() else None
    if prior_role != baseline:
        if not repair:
            raise GuardError("PO definition missing or changed; run with --repair")
        _write(role, baseline, prior_role)
        repaired.append("PO definition")
    effective = read_effective(home)
    if any(effective.get(k) != v for k, v in EXPECTED.items()) or any(effective.get("agents", {}).get(k) != v for k, v in AGENTS.items()):
        raise GuardError("effective override mismatch; PO only remains pending")
    return {"configuration": "VERIFIED", "repaired": repaired, "executor_defaults": EXPECTED,
            "po_model": PO_MODEL, "po_effort": PO_EFFORT, "runtime": "NOT_VERIFIED"}


def _runtime_executable(explicit: str | None) -> str:
    if explicit:
        return explicit
    if os.name == "nt":
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='codex.exe'\" | Select-Object -ExpandProperty ExecutablePath -Unique"],
            capture_output=True, text=True, timeout=10, check=False)
        paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if len(paths) == 1:
            return paths[0]
        if len(paths) > 1:
            raise GuardError("multiple current Codex runtimes; verify the owning executable")
    found = shutil.which("codex.exe" if os.name == "nt" else "codex")
    if not found:
        raise GuardError("current official Codex executable unavailable")
    return found


def read_effective(home: Path, executable: str) -> dict:
    env = {**os.environ, "CODEX_HOME": str(home)}
    process = subprocess.Popen([executable, "--strict-config", "app-server"], env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", errors="replace")
    output: queue.Queue = queue.Queue()
    def collect():
        for line in process.stdout:
            output.put(line)
    threading.Thread(target=collect, daemon=True).start()
    def request(ident, method, params):
        process.stdin.write(json.dumps({"id": ident, "method": method, "params": params}) + '\n')
        process.stdin.flush()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                message = json.loads(output.get(timeout=0.2))
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            except ValueError:
                continue
            if message.get("id") == ident:
                if "error" in message:
                    break
                return message.get("result", {})
        raise GuardError("official configuration read unavailable; PO only remains pending")
    try:
        request(1, "initialize", {"clientInfo": {"name": "po_model_guard", "version": "1.0"}})
        process.stdin.write('{"method":"initialized"}\n')
        process.stdin.flush()
        return request(2, "config/read", {"includeLayers": True, "cwd": str(Path.cwd())})["config"]
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _timestamp(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise GuardError("runtime time boundary needs an explicit timezone")
    return parsed


def verify_turn(events: list[dict], turn_id: str, not_before: str) -> dict:
    context = None
    executed = completed = False
    for event in events:
        payload = event.get("payload", {})
        if event.get("type") == "turn_context":
            context = event if payload.get("turn_id") == turn_id else None
            executed = completed = False
        elif context and event.get("type") == "event_msg":
            if payload.get("type") == "token_count":
                executed |= payload.get("info", {}).get("last_token_usage", {}).get("output_tokens", 0) > 0
            if payload.get("type") == "task_complete" and payload.get("turn_id") == turn_id:
                completed = True
    if not context or _timestamp(context["timestamp"]) < _timestamp(not_before) or not executed or not completed:
        raise GuardError("no exact fresh executed completed runtime turn")
    applied = context["payload"]
    if (applied.get("model"), applied.get("effort")) != (PO_MODEL, PO_EFFORT):
        raise GuardError("runtime model/effort mismatch; no PO verdict may be consumed")
    return {"runtime": "VERIFIED", "turn_id": turn_id, "model": applied["model"],
            "reasoning_effort": applied["effort"], "evidence": "runtime turn_context + usage + completion"}


def read_turn(home: Path, thread_id: str, turn_id: str, not_before: str) -> dict:
    database = home / "state_5.sqlite"
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        row = connection.execute("select rollout_path from threads where id=?", (thread_id,)).fetchone()
    if row is None:
        raise GuardError("PO thread runtime record missing")
    value = row[0]
    if os.name == "nt":
        if value.startswith('\\\\?\\UNC\\'):
            value = '\\\\' + value[8:]
        elif value.startswith('\\\\?\\'):
            value = value[4:]
    path = Path(value).resolve()
    if not path.is_relative_to((home / "sessions").resolve()):
        raise GuardError("runtime path outside Codex session owner")
    with path.open("rb") as stream:
        size = path.stat().st_size
        stream.seek(max(0, size - 8 * 1024 * 1024))
        data = stream.read()
    if size > 8 * 1024 * 1024:
        data = data.split(b'\n', 1)[-1]
    events = [json.loads(line) for line in data.splitlines() if line.strip()]
    return {"thread_id": thread_id, **verify_turn(events, turn_id, not_before)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    parser.add_argument("--codex-exe")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--thread-id")
    parser.add_argument("--turn-id")
    parser.add_argument("--not-before")
    args = parser.parse_args()
    try:
        executable = _runtime_executable(args.codex_exe)
        result = ensure_configuration(args.codex_home, repair=args.repair,
            read_effective=lambda home: read_effective(home, executable))
        if any((args.thread_id, args.turn_id, args.not_before)):
            if not all((args.thread_id, args.turn_id, args.not_before)):
                raise GuardError("runtime check requires thread, turn and fresh time boundary")
            result["po_runtime"] = read_turn(args.codex_home, args.thread_id, args.turn_id, args.not_before)
            result["runtime"] = result["po_runtime"]["runtime"]
        print(json.dumps(result))
        return 0
    except (GuardError, OSError, ValueError, KeyError, sqlite3.Error, subprocess.SubprocessError) as error:
        # Never print configuration, provider credentials, or raw subprocess output.
        message = str(error) if isinstance(error, GuardError) else "configuration/runtime observation unavailable"
        print(json.dumps({"configuration_or_runtime": "NOT_VERIFIED", "reason": message, "scope_held": "PO only"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
