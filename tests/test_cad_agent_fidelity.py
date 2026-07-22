from __future__ import annotations

import json
import tempfile
from pathlib import Path

import ezdxf
import fitz
import pytest

from cad_agent.fidelity import FidelityError, new_fidelity_manifest, run_fidelity_overlays, run_fidelity_pdf
from cad_agent.cli import main


def _pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.draw_line((20, 20), (380, 20))
    page.insert_text((50, 100), "DRAWING LABEL", fontsize=20)
    document.save(path)
    document.close()


def test_fidelity_pdf_writes_clean_paper_coordinate_layout_and_audit() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "private-staging"
        _pdf(source)

        manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
        run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)

        persisted = json.loads((output / "fidelity-run-manifest.json").read_text(encoding="utf-8"))
        page = persisted["pages"][0]
        assert persisted["private_artifact"] is True
        assert persisted["source"] == {"name": "drawing.pdf", "sha256": persisted["source"]["sha256"], "kind": "pdf"}
        assert page["paper_size_mm"] == pytest.approx([141.1111, 105.8333], abs=0.01)
        assert all(record["sha256"] for record in page["artifacts"].values())

        dxf = output / page["artifacts"]["layout_dxf"]["artifact"]
        types = {entity.dxftype() for entity in ezdxf.readfile(dxf).modelspace()}
        assert "INSERT" not in types
        assert "TEXT" not in types
        assert types <= {"LINE", "CIRCLE"}

        audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
        assert audit["status"] == "needs_review"
        assert audit["source_page"]["render_width_px"] > 0
        assert audit["ocr"]["texts"]

        run_fidelity_overlays(source, output, output / "fidelity-run-manifest.json", persisted)
        refreshed = json.loads((output / "fidelity-run-manifest.json").read_text(encoding="utf-8"))
        report_path = output / refreshed["pages"][0]["artifacts"]["fidelity_report"]["artifact"]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["state"] == "needs_review"
        assert 0.0 <= report["full_page"]["precision"] <= 1.0
        assert 0.0 <= report["content_roi"]["recall"] <= 1.0


def test_fidelity_manifest_rejects_repo_output_root(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    _pdf(source)
    with pytest.raises(FidelityError, match="outside"):
        new_fidelity_manifest(source, Path.cwd() / "output" / "private", 144, "approved-test", workspace_root=Path.cwd())


def test_fidelity_cli_creates_private_baseline() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "private-staging"
        _pdf(source)
        assert main([
            "fidelity-pdf", "--input", str(source), "--output-dir", str(output),
            "--source-approval", "approved-test",
        ]) == 0
        assert (output / "fidelity-run-manifest.json").is_file()
        assert main([
            "fidelity-overlay", "--input", str(source),
            "--manifest", str(output / "fidelity-run-manifest.json"),
        ]) == 0
        assert (output / "fidelity_overlay" / "page_01.png").is_file()
