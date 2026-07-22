from __future__ import annotations

import json
import tempfile
from pathlib import Path

import fitz

from cad_agent.cli import main
from cad_agent.pdf import new_pdf_manifest, run_pdf_stages


def _pdf(path: Path, label: str = "A") -> None:
    document = fitz.open()
    for index in range(2):
        page = document.new_page(width=400, height=300)
        page.draw_line((30, 50 + index * 30), (350, 50 + index * 30))
        page.insert_text((50, 100), f"{label}-{index + 1}")
    document.save(path)
    document.close()


def test_pdf_run_writes_page_checkpoints_and_resume_preserves_them() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "run"
        _pdf(source)
        manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
        run_pdf_stages(source, output, output / "pdf-run-manifest.json", manifest)

        persisted = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        assert len(persisted["pages"]) == 2
        for page in persisted["pages"]:
            assert page["scale_label_candidates"] == []
            assert all(stage["state"] == "completed" and stage["sha256"] for stage in page["stages"].values())
            assert (output / page["stages"]["dxf"]["artifact"]).is_file()
            assert (output / page["stages"]["build_evidence"]["artifact"]).is_file()

        before = (output / "pdf-run-manifest.json").read_bytes()
        run_pdf_stages(source, output, output / "pdf-run-manifest.json", persisted)
        assert (output / "pdf-run-manifest.json").read_bytes() == before


def test_pdf_resume_rejects_changed_source() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        changed = root / "changed.pdf"
        output = root / "run"
        _pdf(source, "A")
        _pdf(changed, "B")
        manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
        run_pdf_stages(source, output, output / "pdf-run-manifest.json", manifest)

        from cad_agent.manifest import ManifestError

        try:
            run_pdf_stages(changed, output, output / "pdf-run-manifest.json", manifest)
        except ManifestError as exc:
            assert "SHA-256" in str(exc)
        else:  # pragma: no cover - assertion guard
            raise AssertionError("changed PDF was accepted")


def test_pdf_resume_rebuilds_only_affected_page_stages() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "run"
        _pdf(source)
        manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
        run_pdf_stages(source, output, output / "pdf-run-manifest.json", manifest)
        original = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        unaffected = original["pages"][1]["stages"]
        (output / original["pages"][0]["stages"]["semantic_ir"]["artifact"]).unlink()

        run_pdf_stages(source, output, output / "pdf-run-manifest.json", original)

        resumed = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        assert resumed["pages"][1]["stages"] == unaffected
        assert all(stage["state"] == "completed" for stage in resumed["pages"][0]["stages"].values())


def test_pdf_resume_regenerates_missing_primitive_from_verified_render() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "run"
        _pdf(source)
        manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
        run_pdf_stages(source, output, output / "pdf-run-manifest.json", manifest)
        persisted = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        (output / persisted["pages"][0]["stages"]["primitive_ir"]["artifact"]).unlink()

        run_pdf_stages(source, output, output / "pdf-run-manifest.json", persisted)

        resumed = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        assert all(stage["state"] == "completed" for stage in resumed["pages"][0]["stages"].values())


def test_pdf_cli_run_and_resume() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "run"
        _pdf(source)

        assert main([
            "run-pdf",
            "--input", str(source),
            "--output-dir", str(output),
            "--scale-mm-per-px", "0.5",
            "--calibration-approval", "ticket-123",
            "--dpi", "144",
        ]) == 0
        assert main([
            "resume-pdf",
            "--manifest", str(output / "pdf-run-manifest.json"),
            "--input", str(source),
        ]) == 0


def test_pdf_cli_persists_auto_ocr_roi_choice() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "run"
        _pdf(source)

        assert main([
            "run-pdf",
            "--input", str(source),
            "--output-dir", str(output),
            "--scale-mm-per-px", "0.5",
            "--calibration-approval", "ticket-123",
            "--auto-ocr-roi",
        ]) == 0
        manifest = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        assert manifest["configuration"]["auto_ocr_roi"] is True
