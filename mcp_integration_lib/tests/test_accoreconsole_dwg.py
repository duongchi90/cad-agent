"""Offline security/staging contracts and gated AutoCAD 2027 smoke for accoreconsole_dwg."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from dxf_builder_lib._dxf_snapshot import extract_dxf_readback_snapshot
from mcp_integration_lib.accoreconsole_dwg import (
    ACCORECONSOLE_2027_DEFAULT_PATH,
    DwgConversionError,
    build_dwg_to_dxf_script,
    convert_dwg_to_dxf_and_read,
    decode_console_log,
    resolve_accoreconsole_exe,
    resolve_timeout_s,
)


def _live_accoreconsole_enabled() -> bool:
    return (
        os.getenv("CAD_AGENT_FILE_IPC") == "1"
        and os.getenv("CAD_AGENT_ACCORECONSOLE_LIVE") == "1"
        and bool(os.getenv("CAD_AGENT_DISPOSABLE_DWG"))
    )


def test_resolve_accoreconsole_handles_overrides_disabled_and_missing(tmp_path: Path, monkeypatch) -> None:
    fake_exe = tmp_path / "accoreconsole.exe"
    fake_exe.write_bytes(b"MZ")
    monkeypatch.setenv("CAD_AGENT_ACCORECONSOLE_PATH", str(fake_exe))
    exe, why = resolve_accoreconsole_exe()
    assert exe == str(fake_exe)
    assert why == ""

    for disabled in ("off", "NONE", "0", "false"):
        monkeypatch.setenv("CAD_AGENT_ACCORECONSOLE_PATH", disabled)
        exe_d, why_d = resolve_accoreconsole_exe()
        assert exe_d is None
        assert "disabled" in why_d.lower()

    monkeypatch.setenv("CAD_AGENT_ACCORECONSOLE_PATH", str(tmp_path / "absent.exe"))
    exe_m, why_m = resolve_accoreconsole_exe()
    assert exe_m is None
    assert "absent.exe" in why_m
    assert "2027" in ACCORECONSOLE_2027_DEFAULT_PATH


def test_build_script_allows_only_safe_ascii_saveas_and_rejects_injection() -> None:
    script = build_dwg_to_dxf_script(r"D:\Cad_temp\accore\123456\out.dxf")
    assert script == '_SAVEAS\r\n_DXF\r\n_V\r\n_2018\r\n16\r\n"D:\\Cad_temp\\accore\\123456\\out.dxf"\r\n_QUIT\r\n_Y\r\n'

    for bad_path in (
        'D:/tmp/bad"quote/out.dxf',
        "D:/tmp/line\nbreak/out.dxf",
        "D:/tmp/tiếng_việt/out.dxf",
        "D:/tmp/semi;colon/out.dxf",
    ):
        with pytest.raises(ValueError):
            build_dwg_to_dxf_script(bad_path)


def test_decode_console_log_handles_utf16le_bom_bomless_and_utf8() -> None:
    sample = "Line one\r\nCommand: _SAVEAS\r\n"
    assert decode_console_log(b"\xff\xfe" + sample.encode("utf-16-le")) == ["Line one", "Command: _SAVEAS"]
    assert decode_console_log(sample.encode("utf-16-le")) == ["Line one", "Command: _SAVEAS"]
    assert decode_console_log(sample.encode("utf-8")) == ["Line one", "Command: _SAVEAS"]


@pytest.mark.parametrize("bad_timeout", [0, -5.0, float("nan"), float("inf"), True])
def test_resolve_timeout_rejects_invalid_values(bad_timeout) -> None:
    with pytest.raises(ValueError):
        resolve_timeout_s(bad_timeout)


def test_convert_refuses_non_dwg_and_uses_isolated_ascii_staging_without_leaking_caller_path(
    tmp_path: Path, monkeypatch,
) -> None:
    dxf_file = tmp_path / "not_a_dwg.dxf"
    dxf_file.write_text("0\nEOF\n", encoding="ascii")
    with pytest.raises(ValueError, match="\\.dwg"):
        convert_dwg_to_dxf_and_read(dxf_file, lambda p: p)

    caller_dir = tmp_path / "bản_vẽ khách"
    caller_dir.mkdir()
    src_dwg = caller_dir / "secret name.dwg"
    src_dwg.write_bytes(b"AC1032_SYNTHETIC_DWG")
    stage_root = tmp_path / "ascii_stage"
    stage_root.mkdir()
    fake_exe = tmp_path / "accoreconsole.exe"
    fake_exe.write_bytes(b"MZ")

    seen_argv: list[list[str]] = []

    class _FakeProc:
        pid = 99999
        returncode = 0

        def wait(self, timeout=None):
            return 0

    def fake_popen(argv, cwd=None, **_kwargs):
        seen_argv.append(list(argv))
        assert str(caller_dir) not in " ".join(argv)
        assert "secret name" not in " ".join(argv)
        script_path = Path(argv[argv.index("/s") + 1])
        script_txt = script_path.read_text(encoding="ascii")
        assert str(caller_dir) not in script_txt
        out_dxf = Path(cwd) / "out.dxf"
        out_dxf.write_text(
            "0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1032\n9\n$INSUNITS\n70\n4\n0\nENDSEC\n"
            "0\nSECTION\n2\nENTITIES\n0\nLINE\n5\n31\n8\n0\n10\n0.0\n20\n0.0\n30\n0.0\n"
            "11\n50.0\n21\n0.0\n31\n0.0\n0\nENDSEC\n0\nEOF\n",
            encoding="ascii",
        )
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    snap, report = convert_dwg_to_dxf_and_read(
        src_dwg,
        extract_dxf_readback_snapshot,
        staging_base=stage_root,
        executable_path=fake_exe,
        timeout_s=10.0,
    )
    assert snap["insunits"] == 4
    assert len(snap["lines"]) == 1
    assert report["route"] == "accoreconsole"
    assert report["exit_code"] == 0
    assert report["timed_out"] is False
    assert seen_argv and seen_argv[0][0] == str(fake_exe)
    # Staging folder must be cleaned up cleanly afterward
    assert list((stage_root / "accore").iterdir()) == []


def test_convert_kills_process_tree_and_raises_on_timeout(tmp_path: Path, monkeypatch) -> None:
    src_dwg = tmp_path / "hang.dwg"
    src_dwg.write_bytes(b"AC1032_HANG")
    stage_root = tmp_path / "stage"
    stage_root.mkdir()
    fake_exe = tmp_path / "accoreconsole.exe"
    fake_exe.write_bytes(b"MZ")
    killed: list[int] = []

    class _HangingProc:
        pid = 424242
        returncode = -1

        def wait(self, timeout=None):
            if killed:
                return -1
            raise subprocess.TimeoutExpired(cmd="accore", timeout=timeout or 1.0)

        def kill(self):
            killed.append(self.pid)

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: _HangingProc())
    monkeypatch.setattr("mcp_integration_lib.accoreconsole_dwg._kill_tree", lambda proc: killed.append(proc.pid))

    with pytest.raises(DwgConversionError, match="timed_out"):
        convert_dwg_to_dxf_and_read(
            src_dwg,
            lambda p: p,
            staging_base=stage_root,
            executable_path=fake_exe,
            timeout_s=1.0,
        )
    assert killed == [424242]
    assert list((stage_root / "accore").iterdir()) == []


@pytest.mark.autocad_mechanical
@pytest.mark.skipif(
    not _live_accoreconsole_enabled(),
    reason="requires CAD_AGENT_FILE_IPC=1, CAD_AGENT_ACCORECONSOLE_LIVE=1, and CAD_AGENT_DISPOSABLE_DWG",
)
def test_live_accoreconsole_reads_disposable_dwg_snapshot() -> None:
    disposable_dwg = Path(os.environ["CAD_AGENT_DISPOSABLE_DWG"])
    snap, report = convert_dwg_to_dxf_and_read(disposable_dwg, extract_dxf_readback_snapshot)
    assert report["timed_out"] is False
    assert snap["dxf_version"] is not None
    assert "insunits" in snap
