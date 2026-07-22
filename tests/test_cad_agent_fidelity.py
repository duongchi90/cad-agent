from __future__ import annotations

import json
import tempfile
from pathlib import Path

import ezdxf
import fitz
import pytest

from primitive_ir_lib.geometry_extraction import RawLine
from cad_agent.fidelity import (
    FidelityError,
    new_fidelity_manifest,
    run_fidelity_overlays,
    run_fidelity_pdf,
    run_fidelity_reconstruct,
    write_region_proposal,
    write_region_approval,
    run_fidelity_compose,
)
from cad_agent.cli import CommandError, _refuse_fidelity_dxf, main


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

        dxf.write_text("tampered", encoding="utf-8")
        with pytest.raises(FidelityError, match="no longer matches"):
            run_fidelity_overlays(source, output, output / "fidelity-run-manifest.json", refreshed)


def test_fidelity_manifest_rejects_repo_output_root(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    _pdf(source)
    with pytest.raises(FidelityError, match="outside"):
        new_fidelity_manifest(source, Path.cwd() / "output" / "private", 144, "approved-test", workspace_root=Path.cwd())


def test_mechanical_boundary_refuses_a_fidelity_layout_dxf(tmp_path: Path) -> None:
    dxf = tmp_path / "layout_dxf" / "page_01.dxf"
    dxf.parent.mkdir()
    dxf.write_text("0\nEOF\n", encoding="utf-8")
    (tmp_path / "fidelity-run-manifest.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(CommandError, match="cannot enter Mechanical"):
        _refuse_fidelity_dxf(dxf)


def test_line_pattern_observation_is_sidecar_only() -> None:
    from cad_agent.fidelity import _observe_line_patterns

    lines = [
        RawLine(f"line-{index}", (index * 20.0, 10.0), (index * 20.0 + 12.0, 10.0), 1.0, (index * 20.0, 10.0, index * 20.0 + 12.0, 10.0))
        for index in range(3)
    ]
    patterns = _observe_line_patterns(lines)
    assert patterns == [{"axis": "horizontal", "coordinate_px": 8, "segment_count": 3, "median_gap_px": 8.0, "status": "needs_review"}]


def test_region_proposal_is_source_bound_non_overlapping_and_sidecar_only() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "private-staging"
        _pdf(source)
        manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
        run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
        regions = {
            "regions": [
                {"id": "main_view", "bbox_px": [20, 20, 250, 150], "purpose": "layout-reconstruction"},
                {"id": "detail", "bbox_px": [260, 20, 390, 150], "purpose": "layout-reconstruction"},
            ],
            "excluded_regions": [
                {"id": "title_block", "bbox_px": [20, 400, 390, 580], "purpose": "exclude"},
            ],
        }
        proposal = write_region_proposal(
            source, output, output / "fidelity-run-manifest.json", manifest, 1, regions, workspace_root=Path.cwd(),
        )
        assert proposal["state"] == "needs_human_approval"
        assert proposal["unclassified_area_state"] == "needs_classification"
        assert proposal["page"]["coordinate_system"] == "pixel-top-left"
        assert proposal["source"] == {"name": "drawing.pdf", "sha256": manifest["source"]["sha256"], "kind": "pdf"}
        assert (output / "region_proposals" / "page_01.json").is_file()
        assert not (output / "layout_dxf" / "page_01.dxf").read_text(encoding="utf-8").count("INSERT")

        overlap = dict(regions)
        overlap["regions"] = [
            {"id": "a", "bbox_px": [20, 20, 250, 150], "purpose": "layout-reconstruction"},
            {"id": "b", "bbox_px": [200, 20, 390, 150], "purpose": "layout-reconstruction"},
        ]
        with pytest.raises(FidelityError, match="overlap"):
            write_region_proposal(source, output, output / "fidelity-run-manifest.json", manifest, 1, overlap, workspace_root=Path.cwd())

        revision = write_region_proposal(
            source, output, output / "fidelity-run-manifest.json", manifest, 1, regions, workspace_root=Path.cwd(), revision=2,
        )
        assert revision["revision"] == 2
        assert (output / "region_proposals" / "page_01-r2.json").is_file()
        approval = write_region_approval(source, output, manifest, 1, 2, ["main_view"], "approved-test", workspace_root=Path.cwd())
        assert approval["state"] == "approved-layout-reconstruction-only"
        assert approval["approved_region_ids"] == ["main_view"]
        assert (output / "region_approvals" / "page_01-r2.json").is_file()
        assert main([
            "fidelity-reconstruct", "--input", str(source),
            "--manifest", str(output / "fidelity-run-manifest.json"),
            "--approval", str(output / "region_approvals" / "page_01-r2.json"),
        ]) == 0
        assert (output / "reconstruction_candidates" / "page_01" / "main_view" / "geometry.dxf").is_file()
        assert run_fidelity_compose(source, output, manifest, output / "region_approvals" / "page_01-r2.json", workspace_root=Path.cwd()).is_dir()
        foreign = root / "foreign-approval.json"
        foreign.write_text((output / "region_approvals" / "page_01-r2.json").read_text(encoding="utf-8"), encoding="utf-8")
        with pytest.raises(FidelityError, match="inside the private"):
            run_fidelity_reconstruct(source, output, manifest, foreign, workspace_root=Path.cwd())


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
        regions = root / "regions.json"
        regions.write_text(json.dumps({
            "regions": [{"id": "main", "bbox_px": [20, 20, 250, 150], "purpose": "layout-reconstruction"}],
            "excluded_regions": [{"id": "title", "bbox_px": [20, 400, 390, 580], "purpose": "exclude"}],
        }), encoding="utf-8")
        assert main([
            "fidelity-region-proposal", "--input", str(source),
            "--manifest", str(output / "fidelity-run-manifest.json"), "--page", "1", "--regions", str(regions),
        ]) == 0
        assert (output / "region_proposals" / "page_01.json").is_file()
        assert main([
            "fidelity-region-approve", "--input", str(source),
            "--manifest", str(output / "fidelity-run-manifest.json"), "--page", "1",
            "--region-id", "main", "--approval-reference", "approved-test",
        ]) == 0
        assert (output / "region_approvals" / "page_01.json").is_file()
        assert main(["fidelity-observe", "--input", str(source), "--manifest", str(output / "fidelity-run-manifest.json")]) == 0
        assert (output / "fidelity_observations" / "page_01.json").is_file()
        assert main(["fidelity-review-index", "--input", str(source), "--manifest", str(output / "fidelity-run-manifest.json")]) == 0
        assert (output / "fidelity_review" / "index.html").is_file()
        assert main(["fidelity-review-queue", "--input", str(source), "--manifest", str(output / "fidelity-run-manifest.json")]) == 0
        assert (output / "fidelity_review" / "queue.json").is_file()
