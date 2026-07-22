from __future__ import annotations

import json
import tempfile
from pathlib import Path

import cv2
import numpy as np

from cad_agent.cli import doctor_payload, main


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
