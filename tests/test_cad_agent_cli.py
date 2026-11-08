from __future__ import annotations

import json
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from cad_agent.cli import CommandError, _live_client, doctor_payload, main
from cad_agent.manifest import ManifestError, new_manifest, read_manifest, write_manifest


def _drawing(path: Path, offset: int = 0) -> None:
    image = np.full((160, 240, 3), 255, dtype=np.uint8)
    cv2.line(image, (20 + offset, 40), (220, 40), (0, 0, 0), 2)
    cv2.circle(image, (120, 100), 18, (0, 0, 0), 2)
    assert cv2.imwrite(str(path), image)


def test_doctor_reports_supported_contract() -> None:
    payload = doctor_payload()
    assert payload["supported"] == {"os": "windows", "python": "3.11", "tesseract": "5.4.0.20240606"}
    assert "ezdxf" in payload["packages"]
    assert "tesseract_present" in payload


def test_new_image_manifest_is_draft_reference_only(tmp_path: Path) -> None:
    source = tmp_path / "drawing.png"
    source.write_bytes(b"image")

    manifest = new_manifest(source, 0.5, "ticket-123")

    assert manifest["release_profile"] == "DRAFT_REFERENCE"
    assert manifest["authoritative_release_eligible"] is False
    assert manifest["drawing_setup_evidence"] is None


@pytest.mark.parametrize("scale", [0.0, -0.5, float("nan"), float("inf"), True, False])
def test_new_image_manifest_rejects_non_positive_non_finite_or_boolean_scale(
    tmp_path: Path, scale: float | bool
) -> None:
    source = tmp_path / "drawing.png"
    source.write_bytes(b"synthetic image")

    with pytest.raises(ManifestError, match="scale"):
        new_manifest(source, scale, "ticket-123")


@pytest.mark.parametrize("scale", ["0", "-0.5", "nan", "inf"])
def test_run_rejects_invalid_scale_before_manifest_or_primitive_work(
    tmp_path: Path, monkeypatch, capsys, scale: str
) -> None:
    from cad_agent import cli

    source = tmp_path / "drawing.png"
    source.write_bytes(b"synthetic image")
    output = tmp_path / "run"
    calls: list[float] = []

    def unexpected_primitive(_source: Path, _output: Path, value: float) -> None:
        calls.append(value)
        raise RuntimeError("invalid scale reached primitive stage")

    monkeypatch.setattr(cli, "_run_primitive", unexpected_primitive)

    assert main([
        "run", "--input", str(source), "--output-dir", str(output),
        "--scale-mm-per-px", scale, "--calibration-approval", "ticket-123",
    ]) == 2
    assert not (output / "run-manifest.json").exists()
    assert calls == []
    assert "scale" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("scale", [0.0, -0.5, True, float("nan"), float("inf")])
def test_resume_rejects_invalid_persisted_scale_before_conversion_or_staging(
    tmp_path: Path, monkeypatch, capsys, scale: float | bool
) -> None:
    from cad_agent import cli

    source = tmp_path / "drawing.png"
    source.write_bytes(b"synthetic image")
    output = tmp_path / "run"
    output.mkdir()
    manifest_path = output / "run-manifest.json"
    manifest = new_manifest(source, 0.5, "ticket-123")
    manifest["configuration"]["scale_mm_per_px"] = scale
    write_manifest(manifest_path, manifest)
    before = manifest_path.read_bytes()
    calls: list[float] = []

    def unexpected_primitive(_source: Path, _output: Path, value: float) -> None:
        calls.append(value)
        raise RuntimeError("invalid scale reached primitive stage")

    monkeypatch.setattr(cli, "_run_primitive", unexpected_primitive)

    assert main(["resume", "--manifest", str(manifest_path), "--input", str(source)]) == 2
    assert calls == []
    assert manifest_path.read_bytes() == before
    assert "scale" in capsys.readouterr().err.lower()


def test_resume_source_mismatch_precedes_invalid_scale_admission(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from cad_agent import cli

    source = tmp_path / "drawing.png"
    changed = tmp_path / "changed.png"
    source.write_bytes(b"synthetic image")
    changed.write_bytes(b"different synthetic image")
    output = tmp_path / "run"
    output.mkdir()
    manifest_path = output / "run-manifest.json"
    manifest = new_manifest(source, 0.5, "ticket-123")
    manifest["configuration"]["scale_mm_per_px"] = float("nan")
    write_manifest(manifest_path, manifest)
    before = manifest_path.read_bytes()
    calls: list[float] = []
    monkeypatch.setattr(cli, "_run_primitive", lambda *args: calls.append(args[-1]))

    assert main(["resume", "--manifest", str(manifest_path), "--input", str(changed)]) == 2
    assert calls == []
    assert manifest_path.read_bytes() == before
    assert "SHA-256 does not match" in capsys.readouterr().err


def test_historical_image_manifest_reads_as_draft_reference(tmp_path: Path) -> None:
    path = tmp_path / "run-manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {"name": "drawing.png", "sha256": "a" * 64, "kind": "image"},
                "configuration": {"scale_mm_per_px": 0.5},
                "approvals": {
                    "calibration": {"approved": True, "reference": "ticket-123"}
                },
                "stages": {
                    stage: {
                        "state": "pending",
                        "artifact": None,
                        "sha256": None,
                        "details": None,
                    }
                    for stage in ("primitive_ir", "semantic_ir", "dxf")
                },
            }
        ),
        encoding="utf-8",
    )

    manifest = read_manifest(path)

    assert manifest["release_profile"] == "DRAFT_REFERENCE"
    assert manifest["authoritative_release_eligible"] is False
    assert manifest["drawing_setup_evidence"] is None


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("release_profile", "AUTHORITATIVE"),
        ("authoritative_release_eligible", True),
        ("drawing_setup_evidence", {"status": "SETUP_VERIFIED"}),
    ],
)
def test_image_manifest_refuses_unsafe_release_claim(
    tmp_path: Path, field: str, unsafe_value: object
) -> None:
    source = tmp_path / "drawing.png"
    source.write_bytes(b"image")
    manifest = new_manifest(source, 0.5, "ticket-123")
    manifest[field] = unsafe_value
    path = tmp_path / "run-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ManifestError, match=field):
        read_manifest(path)


def test_run_and_resume_create_verified_checkpoints() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.png"
        output = root / "run"
        _drawing(source)

        assert main([
            "run", "--input", str(source), "--output-dir", str(output),
            "--scale-mm-per-px", "0.5", "--calibration-approval", "ticket-123",
        ]) == 0
        manifest_path = output / "run-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["source"]["name"] == "drawing.png"
        assert manifest["approvals"]["calibration"] == {"approved": True, "reference": "ticket-123"}
        assert all(record["state"] == "completed" and record["sha256"] for record in manifest["stages"].values())
        assert (output / "staged.dxf").is_file()
        assert (output / "build-evidence.json").is_file()

        before = manifest_path.read_bytes()
        assert main(["resume", "--manifest", str(manifest_path), "--input", str(source)]) == 0
        assert manifest_path.read_bytes() == before


def test_resume_rejects_a_changed_input_before_stage_work(capsys) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.png"
        changed = root / "changed.png"
        output = root / "run"
        _drawing(source)
        _drawing(changed, offset=2)
        assert main([
            "run", "--input", str(source), "--output-dir", str(output),
            "--scale-mm-per-px", "0.5", "--calibration-approval", "ticket-123",
        ]) == 0
        assert main([
            "resume", "--manifest", str(output / "run-manifest.json"), "--input", str(changed),
        ]) == 2
        assert "SHA-256 does not match" in capsys.readouterr().err


def test_live_client_propagates_timeout_and_rejects_nonpositive(monkeypatch, tmp_path: Path) -> None:
    import mcp_integration_lib.mcp_client as mcp_client

    captured: dict[str, object] = {}

    class _Client:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    dispatcher = tmp_path / "mcp_dispatch.lsp"
    dispatcher.write_text("", encoding="utf-8")
    monkeypatch.setattr(mcp_client, "FileIPCLiveMCPClient", _Client)
    monkeypatch.setenv("CAD_AGENT_FILE_IPC_DIR", str(tmp_path))

    client = _live_client(42, dispatcher, timeout_s=60.0)

    assert isinstance(client, _Client)
    assert captured["ipc_dir"] == str(tmp_path)
    assert captured["timeout_s"] == 60.0
    with pytest.raises(CommandError, match="timeout"):
        _live_client(42, dispatcher, timeout_s=0.0)


@pytest.mark.parametrize("ipc_dir", ["", "   "])
def test_live_client_defaults_blank_ipc_root(monkeypatch, tmp_path: Path, ipc_dir: str) -> None:
    import mcp_integration_lib.mcp_client as mcp_client

    captured: dict[str, object] = {}

    class _Client:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    dispatcher = tmp_path / "mcp_dispatch.lsp"
    dispatcher.write_text("", encoding="utf-8")
    monkeypatch.setattr(mcp_client, "FileIPCLiveMCPClient", _Client)
    monkeypatch.setenv("CAD_AGENT_FILE_IPC_DIR", ipc_dir)

    _live_client(42, dispatcher)

    assert captured["ipc_dir"] == r"C:\temp"
