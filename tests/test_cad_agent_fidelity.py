from __future__ import annotations

import json
import tempfile
from pathlib import Path

import ezdxf
import fitz
import cv2
import numpy as np
import pytest

from primitive_ir_lib.geometry_extraction import RawGeometry, RawLine
from cad_agent.fidelity import (
    FidelityError,
    new_fidelity_manifest,
    run_fidelity_overlays,
    run_fidelity_pdf,
    run_fidelity_reconstruct,
    run_fidelity_text_observations,
    run_fidelity_observations,
    run_fidelity_table_text_observations,
    write_fidelity_text_review_index,
    write_fidelity_text_approval,
    write_fidelity_text_approvals_from_selection,
    run_fidelity_text_reconstruct,
    run_fidelity_dimension_observations,
    run_fidelity_linetype_reconstruct,
    run_fidelity_table_text_reconstruct,
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


def test_hatch_observation_finds_a_cluster_of_diagonal_strokes() -> None:
    from cad_agent.fidelity import _observe_hatch_candidates

    image = np.full((160, 160, 3), 255, dtype=np.uint8)
    for offset in range(20, 70, 10):
        cv2.line(image, (offset, 70), (offset + 35, 35), (0, 0, 0), 1)

    candidates = _observe_hatch_candidates(image)

    assert len(candidates) == 1
    assert candidates[0]["bbox_px"] == [0, 0, 100, 100]
    assert candidates[0]["diagonal_segment_count"] >= 5
    assert candidates[0]["state"] == "needs_review"


def test_linetype_reconstruction_is_hash_bound_and_changes_only_matching_horizontal_lines(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    page = manifest["pages"][0]
    scale = float(page["pixel_to_paper_mm"]["used"])
    audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    y_px = 40
    y_mm = (audit["source_page"]["render_height_px"] - y_px) * scale
    base_dxf = output / "base.dxf"
    document = ezdxf.new("R2010")
    model = document.modelspace()
    model.add_line((10, y_mm), (40, y_mm))
    model.add_line((10, y_mm + 10), (40, y_mm + 10))
    model.add_line((10, y_mm), (20, y_mm + 10))
    document.saveas(base_dxf)
    rendered = output / page["artifacts"]["rendered_png"]["artifact"]
    from cad_agent.fidelity import sha256_file

    observation = output / "linetype-observation.json"
    observation.write_text(json.dumps({
        "schema_version": "fidelity-linetype-observation-1.0",
        "private_artifact": True,
        "state": "needs_review",
        "page": 1,
        "source_render_sha256": sha256_file(rendered),
        "patterns": [{"axis": "horizontal", "coordinate_px": y_px, "segment_count": 3, "median_gap_px": 8.0, "status": "needs_review", "suggested_linetype": "DASHED"}],
    }), encoding="utf-8")

    result = run_fidelity_linetype_reconstruct(source, output, manifest, observation, base_dxf, workspace_root=Path.cwd())
    entities = list(ezdxf.readfile(result).modelspace())
    assert entities[0].dxf.linetype == "FIDELITY_DASHED"
    assert entities[1].dxf.linetype == "BYLAYER"
    assert entities[2].dxf.linetype == "BYLAYER"
    report = json.loads(result.with_name("report.json").read_text(encoding="utf-8"))
    assert report["state"] == "needs_review"
    assert report["changed_line_entities"] == 1
    revision = run_fidelity_linetype_reconstruct(source, output, manifest, observation, base_dxf, workspace_root=Path.cwd())
    assert revision.parent.parent.name == "linetype_reconstruction-r2"


def test_linetype_reconstruction_cli_writes_private_candidate(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    manifest_path = output / "fidelity-run-manifest.json"
    run_fidelity_pdf(source, output, manifest_path, manifest)
    page = manifest["pages"][0]
    base_dxf = output / page["artifacts"]["layout_dxf"]["artifact"]
    rendered = output / page["artifacts"]["rendered_png"]["artifact"]
    from cad_agent.fidelity import sha256_file

    observation = output / "linetype-observation.json"
    observation.write_text(json.dumps({
        "schema_version": "fidelity-linetype-observation-1.0",
        "private_artifact": True,
        "state": "needs_review",
        "page": 1,
        "source_render_sha256": sha256_file(rendered),
        "patterns": [],
    }), encoding="utf-8")

    assert main([
        "fidelity-linetype-reconstruct", "--input", str(source), "--manifest", str(manifest_path),
        "--observation", str(observation), "--base-dxf", str(base_dxf),
    ]) == 0
    assert (output / "linetype_reconstruction" / "page_01" / "layout.dxf").is_file()


def test_table_text_reconstruction_emits_only_matched_cells(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    page = manifest["pages"][0]
    rendered = output / page["artifacts"]["rendered_png"]["artifact"]
    base_dxf = output / page["artifacts"]["layout_dxf"]["artifact"]
    from cad_agent.fidelity import sha256_file
    observation = output / "table-observation.json"
    observation.write_text(json.dumps({
        "schema_version": "fidelity-table-text-observation-1.0", "private_artifact": True,
        "state": "needs_human_approval", "page": 1, "source_render_sha256": sha256_file(rendered),
        "candidates": [
            {"cell_match_state": "matched", "cell_bbox_px": [10, 20, 80, 40], "text": {"content": "MATCH", "bbox_px": [15, 22, 60, 38]}},
            {"cell_match_state": "needs_review", "cell_bbox_px": None, "text": {"content": "SKIP", "bbox_px": [100, 20, 160, 40]}},
        ],
    }), encoding="utf-8")
    result = run_fidelity_table_text_reconstruct(source, output, manifest, observation, base_dxf, workspace_root=Path.cwd())
    assert [entity.dxf.text for entity in ezdxf.readfile(result).modelspace().query("TEXT")] == ["MATCH"]


def test_text_observations_are_hash_bound_and_never_emit_dxf_text() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "private-staging"
        _pdf(source)
        manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
        run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)

        outputs = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())
        assert len(outputs) == 1
        observation = json.loads(outputs[0].read_text(encoding="utf-8"))
        assert observation["state"] == "needs_human_approval"
        assert observation["source_layout_audit"]["sha256"]
        assert observation["candidates"]
        assert all(candidate["content"] for candidate in observation["candidates"])
        assert observation["unresolved"] == ["no OCR candidate is emitted as DXF TEXT or MTEXT without per-text approval and a Unicode glyph-render check"]
        review = write_fidelity_text_review_index(source, output, manifest, workspace_root=Path.cwd())
        assert review.is_file()
        assert observation["candidates"][0]["id"] in review.read_text(encoding="utf-8")
        with pytest.raises(FidelityError, match="already exists"):
            run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())

        approved = write_fidelity_text_approval(
            source, output, manifest, 1, outputs[0], [observation["candidates"][0]["id"]], "approved-test", workspace_root=Path.cwd(),
        )
        assert approved["state"] == "approved-text-candidates-only"
        assert approved["approved_candidates"][0]["glyph_render"]["passed"] is True
        assert (output / "fidelity_text_approvals" / "page_01.json").is_file()
        text_dxf = run_fidelity_text_reconstruct(source, output, manifest, output / "fidelity_text_approvals" / "page_01.json", workspace_root=Path.cwd())
        assert {entity.dxftype() for entity in ezdxf.readfile(text_dxf).modelspace()} == {"TEXT"}


def test_text_selection_file_creates_page_approvals(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    candidate_id = json.loads(observation.read_text(encoding="utf-8"))["candidates"][0]["id"]
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps({"schema_version": "fidelity-text-selection-1.0", "source": manifest["source"], "selections": [{"page": 1, "candidate_ids": [candidate_id]}]}), encoding="utf-8")
    approvals = write_fidelity_text_approvals_from_selection(source, output, manifest, selection, "approved-test", workspace_root=Path.cwd())
    assert [approval["page"] for approval in approvals] == [1]


def test_table_cell_observations_stay_sidecar_only(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    run_fidelity_observations(source, output, manifest, workspace_root=Path.cwd())
    outputs = run_fidelity_table_text_observations(source, output, manifest, workspace_root=Path.cwd())
    payload = json.loads(outputs[0].read_text(encoding="utf-8"))
    assert payload["state"] in {"needs_human_approval", "not_evaluated"}
    assert payload["unresolved"] == ["no table-cell OCR candidate is emitted as DXF text or a table entity without per-cell approval"]


def test_dimension_observations_are_hash_bound_and_sidecar_only(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())

    outputs = run_fidelity_dimension_observations(source, output, manifest, workspace_root=Path.cwd())
    payload = json.loads(outputs[0].read_text(encoding="utf-8"))
    assert payload["state"] in {"needs_human_approval", "not_evaluated"}
    assert payload["source"] == manifest["source"]
    assert payload["unresolved"] == ["no candidate is emitted as a DXF DIMENSION without explicit mapping approval"]


def test_hatch_observations_are_hash_bound_and_sidecar_only(tmp_path: Path) -> None:
    from cad_agent.fidelity import run_fidelity_hatch_observations

    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)

    outputs = run_fidelity_hatch_observations(source, output, manifest, workspace_root=Path.cwd())

    assert len(outputs) == 1
    payload = json.loads(outputs[0].read_text(encoding="utf-8"))
    assert payload["state"] == "needs_review"
    assert payload["source"] == manifest["source"]
    assert payload["source_render_sha256"]
    assert payload["unresolved"] == ["no candidate is emitted as a DXF HATCH without boundary approval"]


def test_hatch_observation_cli_writes_private_sidecars(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    manifest_path = output / "fidelity-run-manifest.json"
    run_fidelity_pdf(source, output, manifest_path, manifest)

    assert main(["fidelity-hatch-observe", "--input", str(source), "--manifest", str(manifest_path)]) == 0
    assert (output / "fidelity_hatch_observations" / "page_01.json").is_file()


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
        candidate = output / "reconstruction_candidates" / "page_01" / "main_view"
        assert (candidate / "geometry.dxf").is_file()
        report = json.loads((candidate / "report.json").read_text(encoding="utf-8"))
        assert report["quality"]["selected_profile"] in {"baseline", "filtered"}
        assert "f1" in report["quality"]["baseline"]["edge_metric"]
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
        assert main(["fidelity-text-observe", "--input", str(source), "--manifest", str(output / "fidelity-run-manifest.json")]) == 0
        assert (output / "fidelity_text_observations" / "page_01.json").is_file()
        assert main(["fidelity-dimension-observe", "--input", str(source), "--manifest", str(output / "fidelity-run-manifest.json")]) == 0
        assert (output / "fidelity_dimension_observations" / "page_01.json").is_file()
        assert main(["fidelity-dimension-review-index", "--input", str(source), "--manifest", str(output / "fidelity-run-manifest.json")]) == 0
        assert (output / "fidelity_dimension_review" / "index.html").is_file()
        assert main(["fidelity-text-review-index", "--input", str(source), "--manifest", str(output / "fidelity-run-manifest.json")]) == 0
        assert (output / "fidelity_text_review" / "index.html").is_file()
        candidate_id = json.loads((output / "fidelity_text_observations" / "page_01.json").read_text(encoding="utf-8"))["candidates"][0]["id"]
        assert main([
            "fidelity-text-approve", "--input", str(source), "--manifest", str(output / "fidelity-run-manifest.json"),
            "--page", "1", "--observation", str(output / "fidelity_text_observations" / "page_01.json"),
            "--candidate-id", candidate_id, "--approval-reference", "approved-test",
        ]) == 0
        assert (output / "fidelity_text_approvals" / "page_01.json").is_file()
        assert main(["fidelity-review-index", "--input", str(source), "--manifest", str(output / "fidelity-run-manifest.json")]) == 0
        assert (output / "fidelity_review" / "index.html").is_file()
        assert main(["fidelity-review-queue", "--input", str(source), "--manifest", str(output / "fidelity-run-manifest.json")]) == 0
        assert (output / "fidelity_review" / "queue.json").is_file()


def test_region_quality_selects_filtered_geometry_only_when_f1_improves() -> None:
    from cad_agent.fidelity import _select_fidelity_geometry

    crop = np.full((160, 200, 3), 255, dtype=np.uint8)
    cv2.line(crop, (20, 80), (180, 80), (0, 0, 0), 1)
    raw = RawGeometry(lines=[
        RawLine("main", (20.0, 80.0), (180.0, 80.0), 1.0, (20.0, 80.0, 180.0, 80.0)),
        RawLine("noise-1", (20.0, 25.0), (27.0, 25.0), 0.2, (20.0, 25.0, 27.0, 25.0)),
        RawLine("noise-2", (35.0, 35.0), (42.0, 35.0), 0.2, (35.0, 35.0, 42.0, 35.0)),
    ])

    selected, quality = _select_fidelity_geometry(raw, crop, 1.0)

    assert quality["selected_profile"] == "filtered"
    assert quality["filtered"]["edge_metric"]["f1"] > quality["baseline"]["edge_metric"]["f1"]
    assert [line.id for line in selected.lines] == ["main"]


def test_region_quality_removes_a_near_duplicate_only_when_f1_improves() -> None:
    from cad_agent.fidelity import _select_fidelity_geometry

    crop = np.full((160, 200, 3), 255, dtype=np.uint8)
    cv2.line(crop, (20, 80), (180, 80), (0, 0, 0), 1)
    raw = RawGeometry(lines=[
        RawLine("main", (20.0, 80.0), (180.0, 80.0), 1.0, (20.0, 80.0, 180.0, 80.0)),
        RawLine("duplicate", (20.0, 86.0), (180.0, 86.0), 0.8, (20.0, 86.0, 180.0, 86.0)),
    ])

    selected, quality = _select_fidelity_geometry(raw, crop, 1.0)

    assert quality["selected_profile"] == "filtered"
    assert quality["filtered"]["edge_metric"]["f1"] > quality["baseline"]["edge_metric"]["f1"]
    assert [line.id for line in selected.lines] == ["main"]
