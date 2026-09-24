from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs/LUNA_SESSION_RUNBOOK.md"
TEMPLATE = ROOT / "docs/templates/luna-resume-state.json"
FIELDS = (
    "GOAL",
    "CURRENT_MAIN",
    "CURRENT_HEAD",
    "ACTIVE_PR",
    "DONE",
    "ACCEPTED_EVIDENCE_REFS",
    "FIRST_UNSATISFIED_BOUNDARY",
    "CURRENT_RISK",
    "ACTIVE_WRITESET",
    "LIVE_LOCK_STATE",
    "UNACKED_CURRENT_ADVISORIES",
    "NEXT_ACTION",
)
SCRIPT = ROOT / "scripts/luna-session.ps1"


def test_runbook_routes_through_canonical_owners() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for target in (
        "PROJECT.md",
        "ARCHITECTURE.md",
        "STATUS.md",
        "QUALITY.md",
        "AI_OPERATING_MODEL.md",
        "superpowers/specs/2026-09-24-luna-session-portable-runbook-design.md",
        "superpowers/plans/2026-09-24-luna-session-portable-runbook.md",
    ):
        assert f"]({target})" in text
    for path in (
        "scripts/bootstrap.ps1",
        "scripts/verify.ps1",
        "autocad_plugin/CadAgent.AutoCAD2027.sln",
        "mcp_integration_lib/mcp_dispatch.lsp",
    ):
        assert path in text


def test_runbook_keeps_cad_load_manual_and_reports_unavailable_gates_truthfully() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for instruction in ("NETLOAD", "APPLOAD", "Load Once", "CADAGENT_HEALTH"):
        assert instruction in text
    for state in ("BLOCKER", "SKIP", "NOT RUN"):
        assert state in text
    assert "Never run `NETLOAD`, `APPLOAD`, `Load Once`, or `CADAGENT_HEALTH`" in text
    assert "accepted/source drawing" in text.lower()


def test_resume_template_contains_only_blank_canonical_305_fields() -> None:
    state = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert tuple(state) == FIELDS
    assert all(value == "" for value in state.values())


def test_agents_routes_luna_operators_to_the_runbook() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "[Luna session runbook](docs/LUNA_SESSION_RUNBOOK.md)" in text


def _powershell() -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell.exe")
    if executable is None:
        pytest.skip("PowerShell is unavailable")
    return executable


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _fixture_repo(tmp_path: Path, *, stale_cached_main: bool = False) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    remote = tmp_path / "origin.git"
    repo.mkdir()
    (repo / "scripts").mkdir()
    (repo / "docs/templates").mkdir(parents=True)
    (repo / "autocad_plugin").mkdir()
    (repo / "mcp_integration_lib").mkdir()
    (repo / ".gitignore").write_text("autocad_plugin/**/bin/\nautocad_plugin/**/obj/\n", encoding="utf-8")
    (repo / "docs/templates/luna-resume-state.json").write_bytes(TEMPLATE.read_bytes())
    (repo / "autocad_plugin/CadAgent.AutoCAD2027.sln").write_text("fixture solution\n")
    (repo / "mcp_integration_lib/mcp_dispatch.lsp").write_text("; fixture dispatcher\n")
    if SCRIPT.exists():
        shutil.copy2(SCRIPT, repo / "scripts/luna-session.ps1")

    subprocess.run(["git", "init", "-q", "--initial-branch=main", str(repo)], check=True)
    _git(repo, "config", "user.name", "Contract Test")
    _git(repo, "config", "user.email", "contract@example.invalid")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")
    remote_main = _git(repo, "rev-parse", "HEAD")
    if stale_cached_main:
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        _git(repo, "remote", "add", "origin", str(remote))
        _git(repo, "push", "-q", "-u", "origin", "main")
        _git(repo, "commit", "--allow-empty", "-q", "-m", "cached-only")
        _git(repo, "update-ref", "refs/remotes/origin/main", _git(repo, "rev-parse", "HEAD"))
    return repo, remote_main, _git(repo, "rev-parse", "HEAD")


def _run_script(repo: Path, *arguments: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    executable = _powershell()
    command = [executable, "-NoLogo", "-NoProfile", "-NonInteractive"]
    if Path(executable).name.lower().startswith("powershell"):
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(["-File", str(repo / "scripts/luna-session.ps1"), *arguments])
    return subprocess.run(
        command,
        cwd=repo,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _fake_dotnet(tmp_path: Path, repo: Path, *, mode: str = "success") -> tuple[dict[str, str], Path, Path]:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(exist_ok=True)
    log = tmp_path / "dotnet-args.txt"
    dll = (
        repo
        / "autocad_plugin/CadAgent.AutoCAD2027/bin/x64/Release/net10.0-windows/CadAgent.AutoCAD2027.dll"
    )
    dirty_marker = repo / "created-during-build.txt"
    command_file = fake_bin / "dotnet.cmd"
    command_file.write_text(
        "@echo off\r\n"
        '>>"%FAKE_DOTNET_LOG%" echo %*\r\n'
        'if /I "%1"=="clean" goto clean\r\n'
        'if /I "%1"=="build" goto build\r\n'
        "exit /b 0\r\n"
        ":clean\r\n"
        'if exist "%FAKE_DOTNET_DLL%" del /q "%FAKE_DOTNET_DLL%"\r\n'
        "exit /b 0\r\n"
        ":build\r\n"
        'if /I "%FAKE_DOTNET_MODE%"=="fail" exit /b 7\r\n'
        'if /I "%FAKE_DOTNET_MODE%"=="dirty" echo dirty>"%FAKE_DOTNET_DIRTY%"\r\n'
        'if /I "%FAKE_DOTNET_MODE%"=="no-output" exit /b 0\r\n'
        'for %%I in ("%FAKE_DOTNET_DLL%") do if not exist "%%~dpI" mkdir "%%~dpI"\r\n'
        '>>"%FAKE_DOTNET_DLL%" echo fresh-dll-bytes\r\n'
        "exit /b 0\r\n",
        encoding="ascii",
    )
    env = os.environ.copy()
    env.update(
        {
            "PATH": str(fake_bin) + os.pathsep + env.get("PATH", ""),
            "FAKE_DOTNET_LOG": str(log),
            "FAKE_DOTNET_DLL": str(dll),
            "FAKE_DOTNET_DIRTY": str(dirty_marker),
            "FAKE_DOTNET_MODE": mode,
        }
    )
    return env, log, dll


def _valid_resume() -> dict[str, str]:
    return {
        "GOAL": "Complete the approved bounded implementation",
        "CURRENT_MAIN": "1" * 40,
        "CURRENT_HEAD": "2" * 40,
        "ACTIVE_PR": "#453 OPEN/DRAFT",
        "DONE": "Documentation task complete",
        "ACCEPTED_EVIDENCE_REFS": "https://github.com/duongchi90/cad-agent/pull/453",
        "FIRST_UNSATISFIED_BOUNDARY": "Exact-head independent review",
        "CURRENT_RISK": "No live AutoCAD validation performed",
        "ACTIVE_WRITESET": "Runbook and validator files only",
        "LIVE_LOCK_STATE": "No live lock held",
        "UNACKED_CURRENT_ADVISORIES": "None observed",
        "NEXT_ACTION": "Run focused verification",
    }


def test_start_uses_fresh_remote_main_instead_of_cached_ref(tmp_path: Path) -> None:
    repo, remote_main, local_head = _fixture_repo(tmp_path, stale_cached_main=True)
    result = _run_script(repo, "Start")
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"REMOTE_MAIN={remote_main}" in result.stdout
    assert f"LOCAL_HEAD={local_head}" in result.stdout
    assert local_head != remote_main


def test_doctor_reports_missing_tools_without_launching_autocad(tmp_path: Path) -> None:
    repo, _, _ = _fixture_repo(tmp_path)
    empty_path = tmp_path / "empty-path"
    empty_path.mkdir()
    env = os.environ.copy()
    env["PATH"] = str(empty_path) + os.pathsep + r"C:\Windows\System32"
    result = _run_script(repo, "Doctor", env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "BLOCKER=" in result.stdout
    assert "AUTOCAD_ACTION=NOT RUN" in result.stdout


def test_doctor_finds_standard_tesseract_installation_outside_path(tmp_path: Path) -> None:
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    tesseract = program_files / "Tesseract-OCR/tesseract.exe"
    if not tesseract.is_file():
        pytest.skip("standard Tesseract installation is unavailable")

    repo, _, _ = _fixture_repo(tmp_path)
    empty_path = tmp_path / "empty-path"
    empty_path.mkdir()
    env = os.environ.copy()
    env["PATH"] = str(empty_path) + os.pathsep + r"C:\Windows\System32"
    result = _run_script(repo, "Doctor", env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "tesseract.exe=tesseract v5.4.0.20240606" in result.stdout


def test_build_plugin_refuses_dirty_source_before_dotnet(tmp_path: Path) -> None:
    repo, _, _ = _fixture_repo(tmp_path)
    (repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    env, log, _ = _fake_dotnet(tmp_path, repo)
    result = _run_script(repo, "BuildPlugin", env=env)
    assert result.returncode != 0
    assert "WORKTREE_DIRTY" in result.stdout + result.stderr
    assert not log.exists()


def test_packet_binds_fresh_build_output_to_unchanged_clean_head(tmp_path: Path) -> None:
    repo, _, head = _fixture_repo(tmp_path)
    env, log, dll = _fake_dotnet(tmp_path, repo)
    result = _run_script(repo, "Packet", env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert dll.is_file()
    expected_sha = hashlib.sha256(dll.read_bytes()).hexdigest().upper()
    assert f"SOURCE_HEAD={head}" in result.stdout
    assert f"DLL_SHA256={expected_sha}" in result.stdout
    calls = log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 2
    assert calls[0].startswith("clean ") and "-c Release" in calls[0]
    assert calls[1].startswith("build ") and "-p:Platform=x64" in calls[1]
    assert "MANUAL LOAD PACKET" in result.stdout


@pytest.mark.parametrize(
    ("mode", "expected"),
    (("fail", "BUILD_FAILED"), ("no-output", "BUILD_OUTPUT_MISSING"), ("dirty", "WORKTREE_DIRTY")),
)
def test_packet_fails_closed_on_build_failure_missing_output_or_changed_tree(
    tmp_path: Path, mode: str, expected: str
) -> None:
    repo, _, _ = _fixture_repo(tmp_path)
    env, _, _ = _fake_dotnet(tmp_path, repo, mode=mode)
    result = _run_script(repo, "Packet", env=env)
    assert result.returncode != 0
    assert expected in result.stdout + result.stderr
    assert "MANUAL LOAD PACKET" not in result.stdout


def test_validate_resume_accepts_all_current_canonical_fields(tmp_path: Path) -> None:
    repo, _, _ = _fixture_repo(tmp_path)
    state = tmp_path / "resume.json"
    state.write_text(json.dumps(_valid_resume()), encoding="utf-8")
    result = _run_script(repo, "ValidateResume", "-ResumeState", str(state))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESUME_VALID=YES" in result.stdout


@pytest.mark.parametrize(
    "invalid",
    (
        {key: value for key, value in _valid_resume().items() if key != "NEXT_ACTION"},
        {**_valid_resume(), "CURRENT_RISK": "  "},
        {**_valid_resume(), "NEXT_ACTION": "TODO"},
        {"STATE": "COMPLETED"},
    ),
)
def test_validate_resume_rejects_missing_blank_placeholder_or_coordination_only_state(
    tmp_path: Path, invalid: dict[str, str]
) -> None:
    repo, _, _ = _fixture_repo(tmp_path)
    state = tmp_path / "resume.json"
    state.write_text(json.dumps(invalid), encoding="utf-8")
    result = _run_script(repo, "ValidateResume", "-ResumeState", str(state))
    assert result.returncode != 0
    assert "RESUME_INVALID" in result.stdout + result.stderr


def test_validate_resume_rejects_malformed_json(tmp_path: Path) -> None:
    repo, _, _ = _fixture_repo(tmp_path)
    state = tmp_path / "resume.json"
    state.write_text("{not json", encoding="utf-8")
    result = _run_script(repo, "ValidateResume", "-ResumeState", str(state))
    assert result.returncode != 0
    assert "RESUME_INVALID" in result.stdout + result.stderr


def test_unknown_action_fails_closed(tmp_path: Path) -> None:
    repo, _, _ = _fixture_repo(tmp_path)
    result = _run_script(repo, "ExecuteCad")
    assert result.returncode != 0
    assert "UNKNOWN_ACTION" in result.stdout + result.stderr
