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
from primitive_ir_lib.text_extraction import RawText
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
    run_fidelity_semantic_region_handoff,
    run_fidelity_table_text_reconstruct,
    write_region_proposal,
    write_region_approval,
    run_fidelity_compose,
    promote_fidelity_page,
    review_promoted_fidelity_page,
    write_fidelity_review_index,
    write_fidelity_review_queue,
)
from cad_agent.cli import (
    CommandError,
    _mechanical_repair_command,
    _mechanical_review_command,
    _refuse_fidelity_dxf,
    main,
)
from mcp_integration_lib.mcp_client import FakeMCPClient


def _pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.draw_line((20, 20), (380, 20))
    page.insert_text((50, 100), "DRAWING LABEL", fontsize=20)
    document.save(path)
    document.close()


def test_fidelity_renderer_preserves_explicit_local_coordinate_frame(tmp_path: Path) -> None:
    from cad_agent import fidelity as fidelity_module

    dxf = tmp_path / "coordinate-frame.dxf"
    document = ezdxf.new("R2010")
    model = document.modelspace()
    model.add_line((20, 10), (80, 10))
    model.add_line((80, 10), (80, 40))
    document.saveas(dxf)

    rendered = fidelity_module._render_layout_dxf(dxf, 100.0, 50.0, 200, 100)
    expected = np.full((100, 200), 255, dtype=np.uint8)
    cv2.line(expected, (40, 80), (160, 80), 0, 1, cv2.LINE_AA)
    cv2.line(expected, (160, 80), (160, 20), 0, 1, cv2.LINE_AA)
    metric = fidelity_module._edge_metrics(
        cv2.Canny(expected, 50, 150),
        cv2.Canny(cv2.cvtColor(rendered, cv2.COLOR_BGR2GRAY), 50, 150),
        np.full((100, 200), 255, dtype=np.uint8),
    )
    assert metric["f1"] > 0.95


def _dimension_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.draw_line((20, 24), (200, 24), width=1.5)
    page.insert_text((90, 52), "100", fontsize=18)
    document.save(path)
    document.close()


def _dimension_reconstruction_fixture(tmp_path: Path):
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _dimension_pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    manifest_path = output / "fidelity-run-manifest.json"
    run_fidelity_pdf(source, output, manifest_path, manifest)
    run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())
    observation_path = run_fidelity_dimension_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    candidate = observation["candidates"][0]
    line = candidate["nearby_lines"][0]
    base_dxf = output / "base.dxf"
    base_dxf.write_bytes((output / "layout_dxf" / "page_01.dxf").read_bytes())
    approval_path = output / "dimension-approval.json"
    approval_path.write_text(json.dumps({
        "schema_version": "fidelity-dimension-approval-1.0",
        "private_artifact": True,
        "state": "approved-dimension-mappings",
        "source": manifest["source"],
        "page": 1,
        "observation": {
            "path": str(observation_path.relative_to(output)).replace("\\\\", "/"),
            "sha256": __import__("hashlib").sha256(observation_path.read_bytes()).hexdigest(),
        },
        "base_dxf": {
            "path": str(base_dxf.relative_to(output)).replace("\\\\", "/"),
            "sha256": __import__("hashlib").sha256(base_dxf.read_bytes()).hexdigest(),
        },
        "approval_reference": "approved-test",
        "mappings": [{"candidate_id": candidate["text"]["id"], "line_evidence_id": line["id"]}],
    }), encoding="utf-8")
    return source, output, manifest, manifest_path, approval_path, base_dxf


def test_dimension_observation_persists_stable_line_endpoint_evidence(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _dimension_pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())

    observation = run_fidelity_dimension_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    payload = json.loads(observation.read_text(encoding="utf-8"))
    assert payload["candidates"]
    candidate = payload["candidates"][0]
    assert candidate["nearby_lines"]
    assert set(candidate["nearby_lines"][0]) >= {"id", "p1_px", "p2_px", "bbox_px", "length_px"}


def test_dimension_reconstruction_emits_approved_native_dimension(tmp_path: Path) -> None:
    from cad_agent.fidelity import run_fidelity_dimension_reconstruct

    source, output, manifest, _, approval_path, base_dxf = _dimension_reconstruction_fixture(tmp_path)

    result = run_fidelity_dimension_reconstruct(
        source, output, manifest, approval_path, base_dxf, workspace_root=Path.cwd(),
    )

    report = json.loads((result.parent / "report.json").read_text(encoding="utf-8"))
    assert report["state"] == "needs_review"
    assert report["emitted_dimension_entities"] == 1
    document = ezdxf.readfile(result)
    assert len(list(document.modelspace().query("DIMENSION"))) == 1
    assert list(document.modelspace().query("DIMENSION"))[0].dxf.layer == "FIDELITY_DIMENSIONS"


def test_dimension_reconstruction_preserves_approved_display_text_and_endpoints(tmp_path: Path) -> None:
    from cad_agent.fidelity import run_fidelity_dimension_reconstruct

    source, output, manifest, _, approval_path, base_dxf = _dimension_reconstruction_fixture(tmp_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    observation_path = output / approval["observation"]["path"]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    mapping = approval["mappings"][0]
    candidate = next(item for item in observation["candidates"] if item["text"]["id"] == mapping["candidate_id"])
    candidate["text"]["parsed_value"] = 1525
    observation_path.write_text(json.dumps(observation), encoding="utf-8")
    approval["observation"]["sha256"] = __import__("hashlib").sha256(observation_path.read_bytes()).hexdigest()
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    evidence = next(item for item in candidate["nearby_lines"] if item["id"] == mapping["line_evidence_id"])
    page = manifest["pages"][0]
    audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    scale = float(page["pixel_to_paper_mm"]["used"])
    height_px = int(audit["source_page"]["render_height_px"])
    expected_p1 = (float(evidence["p1_px"][0]) * scale, (height_px - float(evidence["p1_px"][1])) * scale)
    expected_p2 = (float(evidence["p2_px"][0]) * scale, (height_px - float(evidence["p2_px"][1])) * scale)

    result = run_fidelity_dimension_reconstruct(
        source, output, manifest, approval_path, base_dxf, workspace_root=Path.cwd(),
    )

    dimension = next(iter(ezdxf.readfile(result).modelspace().query("DIMENSION")))
    assert dimension.dxf.text == "1525"
    assert (dimension.dxf.defpoint2.x, dimension.dxf.defpoint2.y) == pytest.approx(expected_p1)
    assert (dimension.dxf.defpoint3.x, dimension.dxf.defpoint3.y) == pytest.approx(expected_p2)


def test_dimension_reconstruction_cli_writes_private_candidate(tmp_path: Path) -> None:
    source, output, _, manifest_path, approval_path, base_dxf = _dimension_reconstruction_fixture(tmp_path)

    assert main([
        "fidelity-dimension-reconstruct",
        "--input", str(source),
        "--manifest", str(manifest_path),
        "--approval", str(approval_path),
        "--base-dxf", str(base_dxf),
    ]) == 0
    result = output / "dimension_reconstruction" / "page_01" / "layout.dxf"
    assert result.is_file()
    assert json.loads((result.parent / "report.json").read_text(encoding="utf-8"))["state"] == "needs_review"


def test_dimension_reconstruction_rejects_tampered_observation_before_output(tmp_path: Path) -> None:
    from cad_agent.fidelity import run_fidelity_dimension_reconstruct

    source, output, manifest, _, approval_path, base_dxf = _dimension_reconstruction_fixture(tmp_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["observation"]["sha256"] = "0" * 64
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    with pytest.raises(FidelityError, match="observation no longer matches"):
        run_fidelity_dimension_reconstruct(
            source, output, manifest, approval_path, base_dxf, workspace_root=Path.cwd(),
        )
    assert not (output / "dimension_reconstruction").exists()


def test_dimension_reconstruction_rejects_unknown_line_mapping(tmp_path: Path) -> None:
    from cad_agent.fidelity import run_fidelity_dimension_reconstruct

    source, output, manifest, _, approval_path, base_dxf = _dimension_reconstruction_fixture(tmp_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["mappings"][0]["line_evidence_id"] = "line-does-not-exist"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    with pytest.raises(FidelityError, match="Unknown line evidence"):
        run_fidelity_dimension_reconstruct(
            source, output, manifest, approval_path, base_dxf, workspace_root=Path.cwd(),
        )
    assert not (output / "dimension_reconstruction").exists()


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


@pytest.mark.parametrize(
    "relative_path",
    [
        Path("layout_dxf/page_01.dxf"),
        Path("reconstruction_pages/page_01/layout.dxf"),
        Path("reconstruction_candidates/page_01/main_view/geometry.dxf"),
    ],
)
def test_mechanical_boundary_refuses_every_fidelity_dxf_depth(
    tmp_path: Path,
    relative_path: Path,
) -> None:
    dxf = tmp_path / relative_path
    dxf.parent.mkdir(parents=True)
    dxf.write_text("0\nEOF\n", encoding="utf-8")
    (tmp_path / "fidelity-run-manifest.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(CommandError, match="cannot enter Mechanical"):
        _refuse_fidelity_dxf(dxf)


def test_fidelity_signature_preserves_type_to_layer_association(tmp_path: Path) -> None:
    from cad_agent.fidelity import _fidelity_dxf_signature, _live_entity_signature

    dxf = tmp_path / "signature.dxf"
    document = ezdxf.new("R2010")
    document.modelspace().add_line((0, 0), (1, 0), dxfattribs={"layer": "A"})
    document.modelspace().add_circle((0, 0), 1, dxfattribs={"layer": "B"})
    document.saveas(dxf)

    expected = _fidelity_dxf_signature(dxf)
    swapped = _live_entity_signature(
        [
            {"type": "LINE", "layer": "B"},
            {"type": "CIRCLE", "layer": "A"},
        ]
    )

    assert expected["types"] == swapped["types"]
    assert expected["layers"] == swapped["layers"]
    assert expected != swapped


@pytest.mark.parametrize(
    "command",
    [_mechanical_review_command, _mechanical_repair_command],
)
def test_ordinary_mechanical_commands_refuse_promoted_fidelity(
    tmp_path: Path,
    command,
) -> None:
    from types import SimpleNamespace

    dxf = tmp_path / "reconstruction_pages" / "page_01" / "layout.dxf"
    dxf.parent.mkdir(parents=True)
    dxf.write_text("0\nEOF\n", encoding="utf-8")
    (tmp_path / "fidelity-run-manifest.json").write_text("{}\n", encoding="utf-8")
    args = SimpleNamespace(
        dxf=dxf,
        confirm_repair="APPLY",
        approval_reference="test-approval",
    )

    with pytest.raises(CommandError, match="cannot enter Mechanical"):
        command(args)


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


def test_hatch_observation_assigns_stable_candidate_ids() -> None:
    from cad_agent.fidelity import _observe_hatch_candidates

    image = np.full((100, 100, 3), 255, dtype=np.uint8)
    for offset in range(10, 80, 12):
        cv2.line(image, (offset, 10), (offset + 25, 35), (0, 0, 0), 1)

    candidate = _observe_hatch_candidates(image)[0]

    assert candidate["id"] == "hatch-001"


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


def test_linetype_reconstruction_applies_center_to_hash_bound_horizontal_lines(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    manifest_path = output / "fidelity-run-manifest.json"
    run_fidelity_pdf(source, output, manifest_path, manifest)
    page = manifest["pages"][0]
    rendered = output / page["artifacts"]["rendered_png"]["artifact"]
    from cad_agent.fidelity import sha256_file

    height_px = int(json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))["source_page"]["render_height_px"])
    coordinate_px = 180
    scale = float(page["pixel_to_paper_mm"]["used"])
    y_mm = (height_px - coordinate_px) * scale
    base_dxf = output / "base.dxf"
    document = ezdxf.new("R2010")
    model = document.modelspace()
    model.add_line((10, y_mm), (40, y_mm))
    model.add_line((10, y_mm + 10), (40, y_mm + 10))
    document.saveas(base_dxf)
    observation = output / "linetype-center-observation.json"
    observation.write_text(json.dumps({
        "schema_version": "fidelity-linetype-observation-1.0",
        "private_artifact": True,
        "state": "needs_review",
        "page": 1,
        "source_render_sha256": sha256_file(rendered),
        "patterns": [{
            "axis": "horizontal",
            "coordinate_px": coordinate_px,
            "segment_count": 6,
            "median_gap_px": 12.0,
            "status": "needs_review",
            "suggested_linetype": "CENTER",
        }],
    }), encoding="utf-8")

    result = run_fidelity_linetype_reconstruct(
        source, output, manifest, observation, base_dxf, workspace_root=Path.cwd(),
    )

    entities = list(ezdxf.readfile(result).modelspace().query("LINE"))
    assert entities[0].dxf.linetype == "FIDELITY_CENTER"
    assert entities[1].dxf.linetype == "BYLAYER"
    assert "FIDELITY_CENTER" in ezdxf.readfile(result).linetypes


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
        "state": "needs_human_approval", "source": manifest["source"], "page": 1, "source_render_sha256": sha256_file(rendered),
        "candidates": [
            {"id": "cell-match", "cell_match_state": "matched", "cell_bbox_px": [10, 20, 80, 40], "text": {"content": "MATCH", "bbox_px": [15, 22, 60, 38]}},
            {"id": "cell-skip", "cell_match_state": "needs_review", "cell_bbox_px": None, "text": {"content": "SKIP", "bbox_px": [100, 20, 160, 40]}},
        ],
    }), encoding="utf-8")
    from cad_agent.fidelity import write_fidelity_table_text_approval
    write_fidelity_table_text_approval(
        source, output, manifest, 1, observation, ["cell-match"], "approved-test", workspace_root=Path.cwd(),
    )
    approval = output / "fidelity_table_text_approvals" / "page_01.json"
    result = run_fidelity_table_text_reconstruct(source, output, manifest, approval, base_dxf, workspace_root=Path.cwd())
    assert [entity.dxf.text for entity in ezdxf.readfile(result).modelspace().query("TEXT")] == ["MATCH"]


def test_table_text_approval_is_hash_bound_and_selects_only_approved_cells(tmp_path: Path) -> None:
    from cad_agent.fidelity import write_fidelity_table_text_approval

    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    page = manifest["pages"][0]
    rendered = output / page["artifacts"]["rendered_png"]["artifact"]
    from cad_agent.fidelity import sha256_file

    observation = output / "table-observation.json"
    observation.write_text(json.dumps({
        "schema_version": "fidelity-table-text-observation-1.0", "private_artifact": True,
        "state": "needs_human_approval", "source": manifest["source"], "page": 1,
        "source_render_sha256": sha256_file(rendered),
        "candidates": [
            {"id": "cell-1", "cell_match_state": "matched", "text": {"content": "MATCH", "bbox_px": [15, 22, 60, 38]}},
            {"id": "cell-2", "cell_match_state": "matched", "text": {"content": "REVIEW", "bbox_px": [100, 22, 160, 38]}},
        ],
    }), encoding="utf-8")

    approval = write_fidelity_table_text_approval(
        source, output, manifest, 1, observation, ["cell-1"], "approved-cell-1", workspace_root=Path.cwd(),
    )

    assert approval["state"] == "approved-table-text-candidates"
    assert approval["approved_candidate_ids"] == ["cell-1"]
    assert approval["observation"]["sha256"] == sha256_file(observation)
    assert (output / "fidelity_table_text_approvals" / "page_01.json").is_file()


def test_table_text_reconstruction_cli_accepts_only_approval(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    manifest_path = output / "fidelity-run-manifest.json"
    run_fidelity_pdf(source, output, manifest_path, manifest)
    page = manifest["pages"][0]
    rendered = output / page["artifacts"]["rendered_png"]["artifact"]
    base_dxf = output / page["artifacts"]["layout_dxf"]["artifact"]
    from cad_agent.fidelity import sha256_file, write_fidelity_table_text_approval

    observation = output / "table-observation.json"
    observation.write_text(json.dumps({
        "schema_version": "fidelity-table-text-observation-1.0", "private_artifact": True,
        "state": "needs_human_approval", "source": manifest["source"], "page": 1,
        "source_render_sha256": sha256_file(rendered),
        "candidates": [{"id": "cell-1", "cell_match_state": "matched", "text": {"content": "MATCH", "bbox_px": [15, 22, 60, 38]}}],
    }), encoding="utf-8")
    write_fidelity_table_text_approval(
        source, output, manifest, 1, observation, ["cell-1"], "approved-test", workspace_root=Path.cwd(),
    )
    approval = output / "fidelity_table_text_approvals" / "page_01.json"

    assert main([
        "fidelity-table-text-reconstruct", "--input", str(source), "--manifest", str(manifest_path),
        "--approval", str(approval), "--base-dxf", str(base_dxf),
    ]) == 0
    result = output / "table_text_reconstruction" / "page_01" / "layout.dxf"
    assert result.is_file()


def test_table_text_reconstruction_rejects_observation_without_approval(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    page = manifest["pages"][0]
    rendered = output / page["artifacts"]["rendered_png"]["artifact"]
    base_dxf = output / page["artifacts"]["layout_dxf"]["artifact"]
    from cad_agent.fidelity import sha256_file

    observation = output / "legacy-table-observation.json"
    observation.write_text(json.dumps({
        "schema_version": "fidelity-table-text-observation-1.0", "private_artifact": True,
        "state": "needs_human_approval", "source": manifest["source"], "page": 1,
        "source_render_sha256": sha256_file(rendered), "candidates": [],
    }), encoding="utf-8")

    with pytest.raises(FidelityError, match="approval"):
        run_fidelity_table_text_reconstruct(
            source, output, manifest, observation, base_dxf, workspace_root=Path.cwd(),
        )


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
        assert json.loads((text_dxf.parent / "report.json").read_text(encoding="utf-8"))["output_dxf_sha256"] == __import__("hashlib").sha256(text_dxf.read_bytes()).hexdigest()


def test_text_observation_uses_hash_bound_approved_region_for_single_component_dimension_roi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    manifest_path = output / "fidelity-run-manifest.json"
    run_fidelity_pdf(source, output, manifest_path, manifest)
    page = manifest["pages"][0]
    audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    width = audit["source_page"]["render_width_px"]
    height = audit["source_page"]["render_height_px"]
    regions = {
        "regions": [{"id": "dimension-band", "bbox_px": [20, 20, width - 100, height - 20], "purpose": "layout-reconstruction"}],
        "excluded_regions": [{"id": "outside", "bbox_px": [width - 70, 20, width - 20, height - 20], "purpose": "exclude"}],
    }
    write_region_proposal(
        source, output, manifest_path, manifest, 1, regions, workspace_root=Path.cwd(),
    )
    write_region_approval(
        source, output, manifest, 1, 1, ["dimension-band"], "approved-region-ocr-test", workspace_root=Path.cwd(),
    )
    approval_path = output / "region_approvals" / "page_01.json"

    calls: list[tuple[str, object]] = []

    def fake_detect(image: np.ndarray, **kwargs: object) -> list[tuple[int, int, int, int]]:
        calls.append(("detect", kwargs))
        return [(10, 10, 30, 30)]

    def fake_ocr(
        image: np.ndarray, *, roi_boxes: list[tuple[int, int, int, int]], min_confidence: int = 40,
        psm: int = 6, lang: str = "vie+eng",
    ) -> list[RawText]:
        del image, min_confidence, psm, lang
        calls.append(("ocr", roi_boxes))
        return [RawText("approved-dimension", "1490", (5, 12, 15, 22), 0.0, 0.99, "text_tesseract", 1490.0, "dimension_value")]

    from cad_agent import fidelity as fidelity_module

    monkeypatch.setattr(fidelity_module, "detect_text_candidate_rois", fake_detect)
    monkeypatch.setattr(fidelity_module, "extract_text_tesseract", fake_ocr)

    observation_path = run_fidelity_text_observations(
        source,
        output,
        manifest,
        region_approval_path=approval_path,
        workspace_root=Path.cwd(),
    )[0]
    payload = json.loads(observation_path.read_text(encoding="utf-8"))
    assert any(candidate["content"] == "1490" for candidate in payload["candidates"])
    assert payload["region_approval"]["artifact"] == "region_approvals/page_01.json"
    assert calls
    rotated = next(candidate for candidate in payload["candidates"] if candidate["rotation_deg"] == 90.0)
    assert rotated["bbox_px"] == [27, height - 35, 37, height - 25]


def test_approved_title_region_ocr_keeps_block_level_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cad_agent import fidelity as fidelity_module

    image = np.full((700, 1400, 3), 255, dtype=np.uint8)
    calls: list[tuple[tuple[int, int], list[tuple[int, int, int, int]], int]] = []

    def fake_detect(image: np.ndarray, **kwargs: object) -> list[tuple[int, int, int, int]]:
        del image, kwargs
        return []

    def fake_ocr(
        image: np.ndarray,
        *,
        roi_boxes: list[tuple[int, int, int, int]],
        min_confidence: int = 40,
        psm: int = 6,
        lang: str = "vie+eng",
    ) -> list[RawText]:
        del min_confidence, lang
        calls.append((image.shape[:2], roi_boxes, psm))
        if psm != 6:
            return []
        return [RawText(
            "full-title",
            "THIET KE CAI TAO O TO TAI THUNG KIN THACO K190",
            (30, 45, 900, 80),
            0.0,
            0.90,
            "text_tesseract",
            None,
            "general_note",
        )]

    monkeypatch.setattr(fidelity_module, "detect_text_candidate_rois", fake_detect)
    monkeypatch.setattr(fidelity_module, "extract_text_tesseract", fake_ocr)

    candidates, metrics = fidelity_module._approved_region_text_candidates(
        image,
        [{"id": "title", "bbox_px": [100, 200, 1200, 580], "ocr_roi_px": [374, 0, 1089, 133]}],
    )

    assert metrics == {"detector_roi_count": 0, "ocr_call_count": 1}
    assert [candidate["content"] for candidate in candidates] == [
        "THIET KE CAI TAO O TO TAI THUNG KIN THACO K190",
    ]
    assert candidates[0]["approved_region_id"] == "title"
    assert candidates[0]["bbox_px"] == [484, 215, 774, 226]
    assert calls == [((399, 2145), [(0, 0, 2145, 399)], 6)]


def test_approved_region_ocr_rejects_oversized_block_before_resize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cad_agent import fidelity as fidelity_module

    image = np.full((2000, 2000, 3), 255, dtype=np.uint8)
    monkeypatch.setattr(fidelity_module, "detect_text_candidate_rois", lambda image, **kwargs: [])
    resize_calls: list[bool] = []

    def fail_resize(*args: object, **kwargs: object) -> np.ndarray:
        del args, kwargs
        resize_calls.append(True)
        raise AssertionError("oversized OCR ROI was resized before the bound check")

    monkeypatch.setattr(fidelity_module.cv2, "resize", fail_resize)
    with pytest.raises(FidelityError, match="canvas limit"):
        fidelity_module._approved_region_text_candidates(
            image,
            [{"id": "title", "bbox_px": [0, 0, 2000, 2000], "ocr_roi_px": [0, 0, 2000, 2000]}],
        )
    assert resize_calls == []


def test_text_observation_rejects_approved_region_page_other_than_page_one(tmp_path: Path) -> None:
    source = tmp_path / "two-page-drawing.pdf"
    document = fitz.open()
    for label in ("PAGE ONE", "PAGE TWO"):
        page = document.new_page(width=400, height=300)
        page.insert_text((50, 100), label, fontsize=20)
    document.save(source)
    document.close()
    output = tmp_path / "private-staging"
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    manifest_path = output / "fidelity-run-manifest.json"
    run_fidelity_pdf(source, output, manifest_path, manifest)
    page = manifest["pages"][1]
    audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    width = audit["source_page"]["render_width_px"]
    height = audit["source_page"]["render_height_px"]
    regions = {
        "regions": [{"id": "page-two", "bbox_px": [20, 20, width - 100, height - 20], "purpose": "layout-reconstruction"}],
        "excluded_regions": [{"id": "outside", "bbox_px": [width - 70, 20, width - 20, height - 20], "purpose": "exclude"}],
    }
    write_region_proposal(source, output, manifest_path, manifest, 2, regions, workspace_root=Path.cwd())
    write_region_approval(source, output, manifest, 2, 1, ["page-two"], "approved-region-ocr-test", workspace_root=Path.cwd())

    with pytest.raises(FidelityError, match="page 1 only"):
        run_fidelity_text_observations(
            source,
            output,
            manifest,
            region_approval_path=output / "region_approvals" / "page_02.json",
            workspace_root=Path.cwd(),
        )


def test_text_observation_rejects_stale_region_proposal_page_metadata(
    tmp_path: Path,
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    manifest_path = output / "fidelity-run-manifest.json"
    run_fidelity_pdf(source, output, manifest_path, manifest)
    page = manifest["pages"][0]
    audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    width = audit["source_page"]["render_width_px"]
    height = audit["source_page"]["render_height_px"]
    regions = {
        "regions": [{"id": "dimension-band", "bbox_px": [20, 20, width - 100, height - 20], "purpose": "layout-reconstruction"}],
        "excluded_regions": [{"id": "outside", "bbox_px": [width - 70, 20, width - 20, height - 20], "purpose": "exclude"}],
    }
    write_region_proposal(source, output, manifest_path, manifest, 1, regions, workspace_root=Path.cwd())
    write_region_approval(source, output, manifest, 1, 1, ["dimension-band"], "approved-region-ocr-test", workspace_root=Path.cwd())
    proposal_path = output / "region_proposals" / "page_01.json"
    approval_path = output / "region_approvals" / "page_01.json"
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    proposal["page"]["number"] = 2
    proposal_path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["proposal"]["sha256"] = __import__("hashlib").sha256(proposal_path.read_bytes()).hexdigest()
    approval_path.write_text(json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(FidelityError, match="proposal page"):
        run_fidelity_text_observations(
            source, output, manifest, region_approval_path=approval_path, workspace_root=Path.cwd(),
        )


def test_text_observation_rejects_hash_consistent_malformed_approved_region_ocr_roi(
    tmp_path: Path,
) -> None:
    from cad_agent import fidelity as fidelity_module

    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    manifest_path = output / "fidelity-run-manifest.json"
    run_fidelity_pdf(source, output, manifest_path, manifest)
    page = manifest["pages"][0]
    audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    width = audit["source_page"]["render_width_px"]
    height = audit["source_page"]["render_height_px"]
    regions = {
        "regions": [{"id": "title", "bbox_px": [20, 20, width - 100, height - 20], "purpose": "layout-reconstruction"}],
        "excluded_regions": [{"id": "outside", "bbox_px": [width - 70, 20, width - 20, height - 20], "purpose": "exclude"}],
    }
    write_region_proposal(source, output, manifest_path, manifest, 1, regions, workspace_root=Path.cwd())
    write_region_approval(source, output, manifest, 1, 1, ["title"], "approved-region-ocr-test", workspace_root=Path.cwd())
    proposal_path = output / "region_proposals" / "page_01.json"
    approval_path = output / "region_approvals" / "page_01.json"
    base_proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    for invalid_roi in (
        [0, 0, "not-an-integer", 100],
        [-1, 0, 100, 100],
        [0, 0, width, 100],
        [0, 0, 20, 20],
    ):
        proposal = json.loads(json.dumps(base_proposal))
        proposal["regions"][0]["ocr_roi_px"] = invalid_roi
        proposal["proposal_definition_sha256"] = fidelity_module._region_proposal_definition_sha256(proposal)
        proposal_path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        approval["proposal"]["sha256"] = __import__("hashlib").sha256(proposal_path.read_bytes()).hexdigest()
        approval["proposal"]["definition_sha256"] = proposal["proposal_definition_sha256"]
        approval_path.write_text(json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        with pytest.raises(FidelityError, match="ocr_roi_px"):
            run_fidelity_text_observations(
                source, output, manifest, region_approval_path=approval_path, workspace_root=Path.cwd(),
            )


def test_text_observation_discards_ocr_boxes_outside_approved_region(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    manifest_path = output / "fidelity-run-manifest.json"
    run_fidelity_pdf(source, output, manifest_path, manifest)
    page = manifest["pages"][0]
    audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    width = audit["source_page"]["render_width_px"]
    height = audit["source_page"]["render_height_px"]
    regions = {
        "regions": [{"id": "dimension-band", "bbox_px": [100, 100, width - 100, height - 100], "purpose": "layout-reconstruction"}],
        "excluded_regions": [{"id": "outside", "bbox_px": [20, 20, 70, 70], "purpose": "exclude"}],
    }
    write_region_proposal(source, output, manifest_path, manifest, 1, regions, workspace_root=Path.cwd())
    write_region_approval(source, output, manifest, 1, 1, ["dimension-band"], "approved-region-ocr-test", workspace_root=Path.cwd())
    approval_path = output / "region_approvals" / "page_01.json"

    def fake_detect(image: np.ndarray, **kwargs: object) -> list[tuple[int, int, int, int]]:
        del image, kwargs
        return [(10, 10, 30, 30)]

    def fake_ocr(
        image: np.ndarray, *, roi_boxes: list[tuple[int, int, int, int]], min_confidence: int = 40,
        psm: int = 6, lang: str = "vie+eng",
    ) -> list[RawText]:
        del image, roi_boxes, min_confidence, psm, lang
        return [RawText("outside", "OUTSIDE", (-50, 12, 15, 22), 0.0, 0.99, "text_tesseract", None, "general_text")]

    from cad_agent import fidelity as fidelity_module

    monkeypatch.setattr(fidelity_module, "detect_text_candidate_rois", fake_detect)
    monkeypatch.setattr(fidelity_module, "extract_text_tesseract", fake_ocr)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, region_approval_path=approval_path, workspace_root=Path.cwd(),
    )[0]
    payload = json.loads(observation_path.read_text(encoding="utf-8"))
    assert not any(candidate["content"] == "OUTSIDE" for candidate in payload["candidates"])


def test_text_observation_enforces_approved_region_canvas_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    manifest_path = output / "fidelity-run-manifest.json"
    run_fidelity_pdf(source, output, manifest_path, manifest)
    page = manifest["pages"][0]
    audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    width = audit["source_page"]["render_width_px"]
    height = audit["source_page"]["render_height_px"]
    regions = {
        "regions": [{"id": "dimension-band", "bbox_px": [20, 20, width - 100, height - 20], "purpose": "layout-reconstruction"}],
        "excluded_regions": [{"id": "outside", "bbox_px": [width - 70, 20, width - 20, height - 20], "purpose": "exclude"}],
    }
    write_region_proposal(source, output, manifest_path, manifest, 1, regions, workspace_root=Path.cwd())
    write_region_approval(source, output, manifest, 1, 1, ["dimension-band"], "approved-region-ocr-test", workspace_root=Path.cwd())
    approval_path = output / "region_approvals" / "page_01.json"

    def fake_detect(image: np.ndarray, **kwargs: object) -> list[tuple[int, int, int, int]]:
        del kwargs
        return [(0, 0, image.shape[1], image.shape[0])] * 50

    monkeypatch.setattr("cad_agent.fidelity.detect_text_candidate_rois", fake_detect)
    with pytest.raises(FidelityError, match="canvas limit"):
        run_fidelity_text_observations(
            source, output, manifest, region_approval_path=approval_path, workspace_root=Path.cwd(),
        )


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


def _hatch_reconstruction_fixture(tmp_path: Path):
    from cad_agent.fidelity import sha256_file

    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    manifest_path = output / "fidelity-run-manifest.json"
    run_fidelity_pdf(source, output, manifest_path, manifest)
    page = manifest["pages"][0]
    rendered = output / page["artifacts"]["rendered_png"]["artifact"]
    base_dxf = output / "base.dxf"
    base_dxf.write_bytes((output / page["artifacts"]["layout_dxf"]["artifact"]).read_bytes())
    observation = output / "hatch-observation.json"
    observation.write_text(json.dumps({
        "schema_version": "fidelity-hatch-observation-1.0", "private_artifact": True,
        "state": "needs_review", "source": manifest["source"], "page": 1,
        "source_render_sha256": sha256_file(rendered),
        "candidates": [{"id": "hatch-1", "bbox_px": [10, 10, 140, 140], "diagonal_segment_count": 8, "state": "needs_review"}],
    }), encoding="utf-8")
    mappings = [{
        "candidate_id": "hatch-1",
        "boundary_px": [[20, 20], [120, 20], [120, 120], [20, 120]],
        "angle": 45.0,
        "scale": 1.0,
    }]
    return source, output, manifest, manifest_path, observation, base_dxf, mappings


def test_hatch_approval_reconstructs_only_an_explicit_polygon(tmp_path: Path) -> None:
    from cad_agent.fidelity import run_fidelity_hatch_reconstruct, write_fidelity_hatch_approval

    source, output, manifest, _, observation, base_dxf, mappings = _hatch_reconstruction_fixture(tmp_path)
    approval = write_fidelity_hatch_approval(
        source, output, manifest, 1, observation, base_dxf, mappings,
        "approved-hatch-1", workspace_root=Path.cwd(),
    )

    assert approval["state"] == "approved-hatch-boundaries"
    assert approval["base_dxf"]["sha256"]
    result = run_fidelity_hatch_reconstruct(
        source, output, manifest, output / "fidelity_hatch_approvals" / "page_01.json", base_dxf,
        workspace_root=Path.cwd(),
    )
    document = ezdxf.readfile(result)
    hatches = list(document.modelspace().query("HATCH"))
    assert len(hatches) == 1
    assert hatches[0].dxf.layer == "FIDELITY_HATCH"


def test_hatch_reconstruction_rejects_changed_base_dxf(tmp_path: Path) -> None:
    from cad_agent.fidelity import run_fidelity_hatch_reconstruct, write_fidelity_hatch_approval

    source, output, manifest, _, observation, base_dxf, mappings = _hatch_reconstruction_fixture(tmp_path)
    write_fidelity_hatch_approval(
        source, output, manifest, 1, observation, base_dxf, mappings,
        "approved-hatch-1", workspace_root=Path.cwd(),
    )
    base_dxf.write_bytes(base_dxf.read_bytes() + b"\n")

    with pytest.raises(FidelityError, match="base DXF"):
        run_fidelity_hatch_reconstruct(
            source, output, manifest, output / "fidelity_hatch_approvals" / "page_01.json", base_dxf,
            workspace_root=Path.cwd(),
        )
    assert not (output / "hatch_reconstruction").exists()


def test_hatch_reconstruction_rejects_tampered_observation(tmp_path: Path) -> None:
    from cad_agent.fidelity import run_fidelity_hatch_reconstruct, write_fidelity_hatch_approval

    source, output, manifest, _, observation, base_dxf, mappings = _hatch_reconstruction_fixture(tmp_path)
    write_fidelity_hatch_approval(
        source, output, manifest, 1, observation, base_dxf, mappings,
        "approved-hatch-1", workspace_root=Path.cwd(),
    )
    observation.write_text(observation.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(FidelityError, match="no longer matches"):
        run_fidelity_hatch_reconstruct(
            source, output, manifest, output / "fidelity_hatch_approvals" / "page_01.json", base_dxf,
            workspace_root=Path.cwd(),
        )
    assert not (output / "hatch_reconstruction").exists()


def test_hatch_approval_rejects_duplicate_candidate_mapping(tmp_path: Path) -> None:
    from cad_agent.fidelity import write_fidelity_hatch_approval

    source, output, manifest, _, observation, base_dxf, mappings = _hatch_reconstruction_fixture(tmp_path)

    with pytest.raises(FidelityError, match="duplicate hatch candidate"):
        write_fidelity_hatch_approval(
            source, output, manifest, 1, observation, base_dxf, mappings + mappings,
            "approved-hatch-1", workspace_root=Path.cwd(),
        )
    assert not (output / "fidelity_hatch_approvals").exists()


def test_hatch_reconstruction_revalidates_approved_polygon(tmp_path: Path) -> None:
    from cad_agent.fidelity import run_fidelity_hatch_reconstruct, write_fidelity_hatch_approval

    source, output, manifest, _, observation, base_dxf, mappings = _hatch_reconstruction_fixture(tmp_path)
    write_fidelity_hatch_approval(
        source, output, manifest, 1, observation, base_dxf, mappings,
        "approved-hatch-1", workspace_root=Path.cwd(),
    )
    approval_path = output / "fidelity_hatch_approvals" / "page_01.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["mappings"][0]["boundary_px"][0] = [500, 500]
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    with pytest.raises(FidelityError, match="candidate bbox"):
        run_fidelity_hatch_reconstruct(
            source, output, manifest, approval_path, base_dxf, workspace_root=Path.cwd(),
        )
    assert not (output / "hatch_reconstruction").exists()


def test_hatch_approval_and_reconstruction_cli(tmp_path: Path) -> None:
    source, output, _, manifest_path, observation, base_dxf, mappings = _hatch_reconstruction_fixture(tmp_path)
    mappings_path = output / "hatch-mappings.json"
    mappings_path.write_text(json.dumps(mappings), encoding="utf-8")

    assert main([
        "fidelity-hatch-approve", "--input", str(source), "--manifest", str(manifest_path),
        "--page", "1", "--observation", str(observation), "--base-dxf", str(base_dxf),
        "--mappings", str(mappings_path),
        "--approval-reference", "approved-hatch-cli",
    ]) == 0
    approval_path = output / "fidelity_hatch_approvals" / "page_01.json"
    assert approval_path.is_file()
    assert main([
        "fidelity-hatch-reconstruct", "--input", str(source), "--manifest", str(manifest_path),
        "--approval", str(approval_path), "--base-dxf", str(base_dxf),
    ]) == 0
    assert (output / "hatch_reconstruction" / "page_01" / "layout.dxf").is_file()


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
                {"id": "main_view", "bbox_px": [20, 20, 250, 150], "ocr_roi_px": [5, 5, 220, 120], "purpose": "layout-reconstruction"},
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
        assert proposal["regions"][0]["ocr_roi_px"] == [5, 5, 220, 120]
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
        composed = run_fidelity_compose(
            source,
            output,
            manifest,
            output / "region_approvals" / "page_01-r2.json",
            workspace_root=Path.cwd(),
        )
        assert composed.is_dir()
        promotion_path = promote_fidelity_page(
            source,
            output,
            output / "fidelity-run-manifest.json",
            manifest,
            1,
            composed,
            "delegated-visual-approval",
            workspace_root=Path.cwd(),
        )
        promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
        assert promotion["state"] == "approved_for_mechanical_review"
        assert promotion["allowed_actions"] == ["mechanical-review-read-only"]
        assert promotion["expected_structure"]["entity_count"] > 0
        persisted = json.loads(
            (output / "fidelity-run-manifest.json").read_text(encoding="utf-8")
        )
        assert persisted["pages"][0]["fidelity_state"] == "approved_for_mechanical_review"
        assert persisted["pages"][0]["mechanical_review"]["state"] == "pending"

        client = FakeMCPClient()
        document = ezdxf.readfile(composed / "layout.dxf")
        for index, entity in enumerate(document.modelspace(), start=1):
            client.preload_entity(
                format(index, "X"),
                entity.dxftype(),
                str(entity.dxf.layer),
                {},
            )
        live_report_path, passed = review_promoted_fidelity_page(
            source,
            output,
            output / "fidelity-run-manifest.json",
            manifest,
            1,
            client,
            workspace_root=Path.cwd(),
        )
        assert passed is True
        live_report = json.loads(live_report_path.read_text(encoding="utf-8"))
        assert live_report["state"] == "passed"
        assert live_report["save_performed"] is False
        assert live_report["repair_performed"] is False
        final_manifest = json.loads(
            (output / "fidelity-run-manifest.json").read_text(encoding="utf-8")
        )
        assert final_manifest["pages"][0]["fidelity_state"] == "mechanical_reviewed"
        assert final_manifest["pages"][0]["mechanical_review"]["state"] == "completed"
        foreign = root / "foreign-approval.json"
        foreign.write_text((output / "region_approvals" / "page_01-r2.json").read_text(encoding="utf-8"), encoding="utf-8")
        with pytest.raises(FidelityError, match="inside the private"):
            run_fidelity_reconstruct(source, output, manifest, foreign, workspace_root=Path.cwd())


def test_fidelity_compose_preserves_semantic_entities_and_nondefault_linetype(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    regions = {
        "regions": [{"id": "main", "bbox_px": [20, 20, 250, 150], "purpose": "layout-reconstruction"}],
        "excluded_regions": [{"id": "outside", "bbox_px": [300, 200, 390, 290], "purpose": "exclude"}],
    }
    write_region_proposal(
        source, output, output / "fidelity-run-manifest.json", manifest, 1, regions, workspace_root=Path.cwd(),
    )
    approval = write_region_approval(
        source, output, manifest, 1, 1, ["main"], "approved-compose-transfer-test", workspace_root=Path.cwd(),
    )
    candidate = output / "reconstruction_candidates" / "page_01" / "main" / "geometry.dxf"
    candidate.parent.mkdir(parents=True)
    document = ezdxf.new("R2010")
    document.linetypes.add("DASHED", [0.0, 4.0, -2.0])
    model = document.modelspace()
    model.add_line((10, 10), (100, 10), dxfattribs={"linetype": "DASHED"})
    model.add_circle((50, 50), 12)
    model.add_text("TRANSFER ME", dxfattribs={"height": 5}).set_placement((20, 30))
    dimension = model.add_linear_dim(base=(20, 70), p1=(10, 10), p2=(100, 10), location=(55, 70))
    dimension.render()
    document.saveas(candidate)

    composed = run_fidelity_compose(
        source, output, manifest, output / "region_approvals" / "page_01.json", workspace_root=Path.cwd(),
    )
    result = ezdxf.readfile(composed / "layout.dxf")
    assert len(result.modelspace().query("LINE")) == 1
    assert len(result.modelspace().query("CIRCLE")) == 1
    assert len(result.modelspace().query("TEXT")) == 1
    assert len(result.modelspace().query("DIMENSION")) == 1
    assert result.modelspace().query("TEXT")[0].dxf.text == "TRANSFER ME"
    assert result.modelspace().query("DIMENSION")[0].dxf.text == "<>"
    assert result.modelspace().query("DIMENSION")[0].get_measurement() == pytest.approx(90.0)
    assert result.modelspace().query("LINE")[0].dxf.linetype == "DASHED"
    assert "DASHED" in result.linetypes


def test_fidelity_compose_rejects_unsupported_dimension_type_before_linear_transfer(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    regions = {
        "regions": [{"id": "main", "bbox_px": [20, 20, 250, 150], "purpose": "layout-reconstruction"}],
        "excluded_regions": [{"id": "outside", "bbox_px": [300, 200, 390, 290], "purpose": "exclude"}],
    }
    write_region_proposal(
        source, output, output / "fidelity-run-manifest.json", manifest, 1, regions, workspace_root=Path.cwd(),
    )
    approval = write_region_approval(
        source, output, manifest, 1, 1, ["main"], "approved-unsupported-dimension-test", workspace_root=Path.cwd(),
    )
    candidate = output / "reconstruction_candidates" / "page_01" / "main" / "geometry.dxf"
    candidate.parent.mkdir(parents=True)
    document = ezdxf.new("R2010")
    dimension_override = document.modelspace().add_linear_dim(
        base=(20, 70), p1=(10, 10), p2=(100, 10), location=(55, 70),
    )
    dimension_override.render()
    dimension_override.dimension.dxf.dimtype = 2
    document.saveas(candidate)

    persisted = ezdxf.readfile(candidate).modelspace().query("DIMENSION")[0]
    assert persisted.dxf.dimtype == 2
    with pytest.raises(FidelityError, match=r"(?i)unsupported.*dimension"):
        run_fidelity_compose(
            source, output, manifest, output / "region_approvals" / "page_01.json", workspace_root=Path.cwd(),
        )


def test_semantic_owner_handoff_translates_owner_outputs_into_local_region_candidates(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    regions = {
        "regions": [{"id": "main", "bbox_px": [20, 20, 250, 150], "purpose": "layout-reconstruction"}],
        "excluded_regions": [{"id": "outside", "bbox_px": [300, 200, 390, 290], "purpose": "exclude"}],
    }
    write_region_proposal(
        source, output, output / "fidelity-run-manifest.json", manifest, 1, regions, workspace_root=Path.cwd(),
    )
    approval_path = output / "region_approvals" / "page_01.json"
    write_region_approval(source, output, manifest, 1, 1, ["main"], "approved-semantic-owner-handoff", workspace_root=Path.cwd())
    run_fidelity_reconstruct(source, output, manifest, approval_path, workspace_root=Path.cwd())

    from cad_agent import fidelity as fidelity_module

    page = manifest["pages"][0]
    audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    height_px = float(audit["source_page"]["render_height_px"])
    scale = float(page["pixel_to_paper_mm"]["used"])
    region = regions["regions"][0]
    offset_x = float(region["bbox_px"][0]) * scale
    offset_y = (height_px - float(region["bbox_px"][3])) * scale
    rendered_sha256 = fidelity_module.sha256_file(output / page["artifacts"]["rendered_png"]["artifact"])

    candidate_path = output / "reconstruction_candidates" / "page_01" / "main" / "geometry.dxf"
    candidate = ezdxf.readfile(candidate_path)
    horizontal = next(
        entity for entity in candidate.modelspace().query("LINE")
        if abs(float(entity.dxf.start.y) - float(entity.dxf.end.y)) <= 1e-6
    )
    local_start = horizontal.dxf.start
    local_end = horizontal.dxf.end

    text_root = output / "text_reconstruction" / "page_01"
    text_root.mkdir(parents=True)
    text_dxf = text_root / "layout.dxf"
    text_document = ezdxf.new("R2010")
    text = text_document.modelspace().add_text("SEMANTIC TEXT", dxfattribs={"height": 4.0})
    text.set_placement((offset_x + 20.0, offset_y + 15.0))
    text_document.saveas(text_dxf)
    text_approval = output / "fidelity_text_approvals" / "page_01.json"
    text_approval.parent.mkdir(parents=True)
    text_approval.write_text(json.dumps({
        "schema_version": "fidelity-text-approval-1.0",
        "private_artifact": True,
        "state": "approved-text-candidates-only",
        "source": manifest["source"],
        "page": 1,
    }), encoding="utf-8")
    (text_root / "report.json").write_text(json.dumps({
        "state": "needs_review",
        "text_approval_sha256": fidelity_module.sha256_file(text_approval),
        "output_dxf_sha256": fidelity_module.sha256_file(text_dxf),
    }), encoding="utf-8")

    dimension_root = output / "dimension_reconstruction" / "page_01"
    dimension_root.mkdir(parents=True)
    dimension_dxf = dimension_root / "layout.dxf"
    dimension_document = ezdxf.new("R2010")
    dimension = dimension_document.modelspace().add_linear_dim(
        base=(offset_x + 10.0, offset_y + 20.0),
        p1=(offset_x + 10.0, offset_y + 10.0),
        p2=(offset_x + 30.0, offset_y + 10.0),
        location=(offset_x + 20.0, offset_y + 20.0),
        text="<>",
    )
    dimension.render()
    dimension_document.saveas(dimension_dxf)
    (dimension_root / "report.json").write_text(json.dumps({
        "state": "needs_review",
        "source_render_sha256": rendered_sha256,
        "output_dxf_sha256": fidelity_module.sha256_file(dimension_dxf),
    }), encoding="utf-8")

    linetype_root = output / "linetype_reconstruction" / "page_01"
    linetype_root.mkdir(parents=True)
    linetype_dxf = linetype_root / "layout.dxf"
    linetype_document = ezdxf.new("R2010")
    linetype_document.linetypes.add("FIDELITY_CENTER", [0.0, 4.0, -1.0, 1.0, -1.0])
    linetype_document.modelspace().add_line(
        (offset_x + float(local_start.x), offset_y + float(local_start.y)),
        (offset_x + float(local_end.x), offset_y + float(local_end.y)),
        dxfattribs={"linetype": "FIDELITY_CENTER"},
    )
    linetype_document.modelspace().add_line(
        (offset_x + float(local_start.x), offset_y + float(local_start.y) + 0.2),
        (offset_x + float(local_end.x), offset_y + float(local_end.y) + 0.2),
        dxfattribs={"linetype": "FIDELITY_CENTER"},
    )
    linetype_document.saveas(linetype_dxf)
    (linetype_root / "report.json").write_text(json.dumps({
        "state": "needs_review",
        "source_render_sha256": rendered_sha256,
        "output_dxf_sha256": fidelity_module.sha256_file(linetype_dxf),
    }), encoding="utf-8")

    assert main([
        "fidelity-semantic-region-handoff",
        "--input", str(source),
        "--manifest", str(output / "fidelity-run-manifest.json"),
        "--approval", str(approval_path),
    ]) == 0
    handoff = json.loads((output / "semantic_region_handoff" / "page_01.json").read_text(encoding="utf-8"))
    assert handoff["transferred"][0]["counts"]["LINETYPE"] == 1

    candidate = ezdxf.readfile(candidate_path)
    assert [entity.dxf.text for entity in candidate.modelspace().query("TEXT")] == ["SEMANTIC TEXT"]
    dimensions = list(candidate.modelspace().query("DIMENSION"))
    assert len(dimensions) == 1
    assert dimensions[0].get_measurement() == pytest.approx(20.0)
    assert sum(entity.dxf.linetype == "FIDELITY_CENTER" for entity in candidate.modelspace().query("LINE")) == 1

    composed = run_fidelity_compose(source, output, manifest, approval_path, workspace_root=Path.cwd())
    result = ezdxf.readfile(composed / "layout.dxf")
    assert len(result.modelspace().query("TEXT")) == 1
    assert len(result.modelspace().query("DIMENSION")) == 1
    assert result.modelspace().query("LINE")[0].dxf.linetype == "FIDELITY_CENTER"
    compose_report = json.loads((composed / "report.json").read_text(encoding="utf-8"))
    assert "semantic owner handoff remains review-only" in compose_report["unresolved"]


def test_semantic_handoff_transfers_measured_page1_horizontal_512_dashed_line(tmp_path: Path) -> None:
    """The measured page-1 @512 DASHED owner line must reach side."""
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    regions = {
        "regions": [{"id": "side", "bbox_px": [20, 20, 350, 500], "purpose": "layout-reconstruction"}],
        "excluded_regions": [{"id": "outside", "bbox_px": [360, 520, 390, 590], "purpose": "exclude"}],
    }
    write_region_proposal(
        source, output, output / "fidelity-run-manifest.json", manifest, 1, regions, workspace_root=Path.cwd(),
    )
    approval_path = output / "region_approvals" / "page_01.json"
    write_region_approval(source, output, manifest, 1, 1, ["side"], "measured-page1-horizontal-512", workspace_root=Path.cwd())
    run_fidelity_reconstruct(source, output, manifest, approval_path, workspace_root=Path.cwd())

    import cad_agent.fidelity as fidelity_module

    page = manifest["pages"][0]
    audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    height_px = float(audit["source_page"]["render_height_px"])
    scale = float(page["pixel_to_paper_mm"]["used"])
    region = regions["regions"][0]
    offset_x = float(region["bbox_px"][0]) * scale
    offset_y = (height_px - float(region["bbox_px"][3])) * scale

    # These are the measured local endpoints from the exact BVTL page-1 @512
    # failure. The intended local candidate is the existing overlapping side
    # LINE; the owner output is the full-page transformed DASHED line.
    local_target_start = (36.50253171971714, 35.44448713571971)
    local_target_end = (46.024931239853855, 35.62082792998169)
    owner_local_start = (34.033761458480235, 34.915465123207696)
    owner_local_end = (43.379820304591384, 34.915465123207696)

    candidate_path = output / "reconstruction_candidates" / "page_01" / "side" / "geometry.dxf"
    candidate_document = ezdxf.new("R2010")
    candidate_document.modelspace().add_line(local_target_start, local_target_end)
    candidate_document.saveas(candidate_path)

    owner_root = output / "linetype_reconstruction" / "page_01"
    owner_root.mkdir(parents=True)
    owner_path = owner_root / "layout.dxf"
    owner_document = ezdxf.new("R2010")
    owner_document.linetypes.add("FIDELITY_DASHED", [0.0, 4.0, -2.0])
    owner_document.modelspace().add_line(
        (offset_x + owner_local_start[0], offset_y + owner_local_start[1]),
        (offset_x + owner_local_end[0], offset_y + owner_local_end[1]),
        dxfattribs={"linetype": "FIDELITY_DASHED"},
    )
    owner_document.saveas(owner_path)
    (owner_root / "report.json").write_text(json.dumps({
        "state": "needs_review",
        "source_render_sha256": fidelity_module.sha256_file(output / page["artifacts"]["rendered_png"]["artifact"]),
        "output_dxf_sha256": fidelity_module.sha256_file(owner_path),
    }), encoding="utf-8")

    # Intended GREEN behavior: one supported DASHED output transfers to the
    # existing side LINE, with no unrelated LINE mutation.
    run_fidelity_semantic_region_handoff(
        source, output, manifest, approval_path, workspace_root=Path.cwd(),
    )
    candidate = ezdxf.readfile(candidate_path)
    lines = list(candidate.modelspace().query("LINE"))
    assert len(lines) == 1
    assert lines[0].dxf.linetype == "FIDELITY_DASHED"
    assert (float(lines[0].dxf.start.x), float(lines[0].dxf.start.y)) == pytest.approx(local_target_start)
    assert (float(lines[0].dxf.end.x), float(lines[0].dxf.end.y)) == pytest.approx(local_target_end)


def test_semantic_handoff_rejects_ambiguous_fuzzy_horizontal_matches(tmp_path: Path) -> None:
    """Two fuzzy targets must not be resolved by target iteration order."""
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    regions = {
        "regions": [{"id": "side", "bbox_px": [20, 20, 350, 500], "purpose": "layout-reconstruction"}],
        "excluded_regions": [{"id": "outside", "bbox_px": [360, 520, 390, 590], "purpose": "exclude"}],
    }
    write_region_proposal(
        source, output, output / "fidelity-run-manifest.json", manifest, 1, regions, workspace_root=Path.cwd(),
    )
    approval_path = output / "region_approvals" / "page_01.json"
    write_region_approval(source, output, manifest, 1, 1, ["side"], "ambiguous-fuzzy-horizontal", workspace_root=Path.cwd())
    run_fidelity_reconstruct(source, output, manifest, approval_path, workspace_root=Path.cwd())

    import cad_agent.fidelity as fidelity_module

    page = manifest["pages"][0]
    audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    height_px = float(audit["source_page"]["render_height_px"])
    scale = float(page["pixel_to_paper_mm"]["used"])
    region = regions["regions"][0]
    offset_x = float(region["bbox_px"][0]) * scale
    offset_y = (height_px - float(region["bbox_px"][3])) * scale

    # Both distinct targets are outside the exact endpoint tolerance but are
    # inside the existing one-pixel horizontal fuzzy rule and overlap the
    # owner segment by the required 50% shorter-segment threshold.
    local_targets = [
        ((0.0, 0.6), (8.0, 0.6)),
        ((2.0, 0.6), (10.0, 0.6)),
    ]
    candidate_path = output / "reconstruction_candidates" / "page_01" / "side" / "geometry.dxf"
    candidate_document = ezdxf.new("R2010")
    for start, end in local_targets:
        candidate_document.modelspace().add_line(start, end)
    candidate_document.saveas(candidate_path)

    owner_root = output / "linetype_reconstruction" / "page_01"
    owner_root.mkdir(parents=True)
    owner_path = owner_root / "layout.dxf"
    owner_document = ezdxf.new("R2010")
    owner_document.linetypes.add("FIDELITY_DASHED", [0.0, 4.0, -2.0])
    owner_document.modelspace().add_line(
        (offset_x, offset_y),
        (offset_x + 10.0, offset_y),
        dxfattribs={"linetype": "FIDELITY_DASHED"},
    )
    owner_document.saveas(owner_path)
    (owner_root / "report.json").write_text(json.dumps({
        "state": "needs_review",
        "source_render_sha256": fidelity_module.sha256_file(output / page["artifacts"]["rendered_png"]["artifact"]),
        "output_dxf_sha256": fidelity_module.sha256_file(owner_path),
    }), encoding="utf-8")

    try:
        run_fidelity_semantic_region_handoff(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )
    except FidelityError as exc:
        assert "ambiguous fuzzy horizontal" in str(exc).lower()
        candidate = ezdxf.readfile(candidate_path)
        assert all(str(line.dxf.get("linetype", "")).upper() in {"", "BYLAYER", "BYBLOCK", "CONTINUOUS"}
                   for line in candidate.modelspace().query("LINE"))
    else:
        candidate = ezdxf.readfile(candidate_path)
        dashed_indices = [
            index for index, line in enumerate(candidate.modelspace().query("LINE"))
            if str(line.dxf.get("linetype", "")).upper() == "FIDELITY_DASHED"
        ]
        pytest.fail(f"Current handoff silently selected matches[0]; dashed target indices={dashed_indices}.")


def test_semantic_handoff_stays_fail_closed_for_unmatched_dashed_line(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    regions = {
        "regions": [{"id": "side", "bbox_px": [20, 20, 350, 500], "purpose": "layout-reconstruction"}],
        "excluded_regions": [{"id": "outside", "bbox_px": [360, 520, 390, 590], "purpose": "exclude"}],
    }
    write_region_proposal(
        source, output, output / "fidelity-run-manifest.json", manifest, 1, regions, workspace_root=Path.cwd(),
    )
    approval_path = output / "region_approvals" / "page_01.json"
    write_region_approval(source, output, manifest, 1, 1, ["side"], "unmatched-dashed-fail-closed", workspace_root=Path.cwd())
    run_fidelity_reconstruct(source, output, manifest, approval_path, workspace_root=Path.cwd())

    import cad_agent.fidelity as fidelity_module

    page = manifest["pages"][0]
    audit = json.loads((output / page["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    height_px = float(audit["source_page"]["render_height_px"])
    scale = float(page["pixel_to_paper_mm"]["used"])
    region = regions["regions"][0]
    offset_x = float(region["bbox_px"][0]) * scale
    offset_y = (height_px - float(region["bbox_px"][3])) * scale

    candidate_path = output / "reconstruction_candidates" / "page_01" / "side" / "geometry.dxf"
    candidate_document = ezdxf.new("R2010")
    candidate_document.modelspace().add_line((10.0, 10.0), (20.0, 10.0))
    candidate_document.saveas(candidate_path)

    owner_root = output / "linetype_reconstruction" / "page_01"
    owner_root.mkdir(parents=True)
    owner_path = owner_root / "layout.dxf"
    owner_document = ezdxf.new("R2010")
    owner_document.linetypes.add("FIDELITY_DASHED", [0.0, 4.0, -2.0])
    owner_document.modelspace().add_line(
        (offset_x + 30.0, offset_y + 40.0),
        (offset_x + 40.0, offset_y + 40.0),
        dxfattribs={"linetype": "FIDELITY_DASHED"},
    )
    owner_document.saveas(owner_path)
    (owner_root / "report.json").write_text(json.dumps({
        "state": "needs_review",
        "source_render_sha256": fidelity_module.sha256_file(output / page["artifacts"]["rendered_png"]["artifact"]),
        "output_dxf_sha256": fidelity_module.sha256_file(owner_path),
    }), encoding="utf-8")

    with pytest.raises(FidelityError, match="no matching local region line"):
        run_fidelity_semantic_region_handoff(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )


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


def test_fidelity_review_queue_exposes_hash_bound_advanced_states(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)

    records = {
        "text": ("fidelity_text_observations", {"state": "needs_human_approval"}),
        "table_text": ("fidelity_table_text_observations", {"state": "needs_human_approval"}),
        "dimension": ("fidelity_dimension_observations", {"state": "needs_human_approval"}),
        "hatch": ("fidelity_hatch_observations", {"state": "needs_review"}),
        "linetype": ("linetype_reconstruction", {"state": "needs_review", "profile": "fidelity-layout-linetype"}),
    }
    for kind, (directory, payload) in records.items():
        path = output / directory / "page_01" / ("report.json" if kind == "linetype" else "observation.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    manifest_path = output / "fidelity-run-manifest.json"
    queue_path = write_fidelity_review_queue(source, output, manifest, workspace_root=Path.cwd())
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    assert queue["state"] == "needs_review"
    advanced = {item["kind"]: item for item in queue["items"][0]["advanced_reviews"]}
    assert set(advanced) == set(records)
    for item in advanced.values():
        assert item["artifact"]["sha256"]
        assert item["state"] in {"needs_human_approval", "needs_review"}
        assert item["next_action"]

    index = write_fidelity_review_index(source, output, manifest, workspace_root=Path.cwd())
    html = index.read_text(encoding="utf-8")
    assert "Advanced fidelity" in html
    assert all(kind in html for kind in records)
    assert manifest_path.is_file()


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


def test_table_text_reconstruction_uses_unicode_ttf_style_for_vietnamese_content(tmp_path: Path) -> None:
    """Bug: run_fidelity_table_text_reconstruct() dùng model.add_text() không
    set dxfattribs['style'], nên TEXT rơi về style 'Standard' (font txt.shx)
    -- không có glyph dấu tiếng Việt. Nội dung ô bảng thật (vd "VẬT LIỆU")
    phải render đúng khi mở trong AutoCAD."""
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
        "state": "needs_human_approval", "source": manifest["source"], "page": 1, "source_render_sha256": sha256_file(rendered),
        "candidates": [
            {"id": "cell-vn", "cell_match_state": "matched", "cell_bbox_px": [10, 20, 120, 40], "text": {"content": "VẬT LIỆU", "bbox_px": [15, 22, 100, 38]}},
        ],
    }), encoding="utf-8")
    from cad_agent.fidelity import write_fidelity_table_text_approval
    write_fidelity_table_text_approval(
        source, output, manifest, 1, observation, ["cell-vn"], "approved-test", workspace_root=Path.cwd(),
    )
    approval = output / "fidelity_table_text_approvals" / "page_01.json"
    result = run_fidelity_table_text_reconstruct(source, output, manifest, approval, base_dxf, workspace_root=Path.cwd())

    saved = ezdxf.readfile(result)
    entities = list(saved.modelspace().query("TEXT"))
    assert [entity.dxf.text for entity in entities] == ["VẬT LIỆU"]
    style_name = entities[0].dxf.style
    assert style_name != "Standard", "TEXT tiếng Việt không được dùng style 'Standard' (txt.shx)"
    style = saved.styles.get(style_name)
    assert (style.dxf.font or "").lower().endswith(".ttf"), (
        f"style '{style_name}' phải dùng font TTF Unicode, đang là {style.dxf.font!r}"
    )


def test_text_reconstruction_uses_unicode_ttf_style_for_vietnamese_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cùng bug ở run_fidelity_text_reconstruct() (nhánh 'ghi chú dài' khác
    với bảng) -- TEXT tiếng Việt phải dùng style TTF Unicode, không rơi về
    'Standard'."""
    monkeypatch.setenv("CAD_AGENT_FIDELITY_TEXT_FONT", r"C:\Windows\Fonts\arial.ttf")
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)

    outputs = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())
    observation_path = outputs[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    assert observation["candidates"], "fixture PDF phải có ít nhất 1 candidate OCR"
    # ghi đè nội dung candidate đầu tiên thành tiếng Việt có dấu -- vẫn giữ
    # nguyên cấu trúc/hash-binding thật do run_fidelity_text_observations tạo
    observation["candidates"][0]["content"] = "SỐ LƯỢNG"
    observation_path.write_text(json.dumps(observation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    approved = write_fidelity_text_approval(
        source, output, manifest, 1, observation_path, [observation["candidates"][0]["id"]], "approved-test", workspace_root=Path.cwd(),
    )
    assert approved["approved_candidates"][0]["glyph_render"]["passed"] is True
    text_dxf = run_fidelity_text_reconstruct(
        source, output, manifest, output / "fidelity_text_approvals" / "page_01.json", workspace_root=Path.cwd(),
    )

    saved = ezdxf.readfile(text_dxf)
    entities = list(saved.modelspace().query("TEXT"))
    assert [entity.dxf.text for entity in entities] == ["SỐ LƯỢNG"]
    style_name = entities[0].dxf.style
    assert style_name != "Standard", "TEXT tiếng Việt không được dùng style 'Standard' (txt.shx)"
    style = saved.styles.get(style_name)
    assert (style.dxf.font or "").lower().endswith(".ttf"), (
        f"style '{style_name}' phải dùng font TTF Unicode, đang là {style.dxf.font!r}"
    )


def test_text_reconstruction_sizes_from_visible_glyphs_but_keeps_ocr_anchor() -> None:
    """OCR boxes may include line spacing that must not become DXF glyph height."""
    from cad_agent import fidelity as fidelity_module

    image = np.full((80, 240, 3), 255, dtype=np.uint8)
    cv2.line(image, (10, 6), (229, 6), (0, 0, 0), 1)
    cv2.line(image, (10, 55), (229, 55), (0, 0, 0), 1)
    cv2.putText(image, "VISIBLE", (28, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 0), 1, cv2.LINE_AA)
    ocr_bbox = [10, 6, 230, 56]

    sizing = fidelity_module._derive_text_reconstruction_size(
        image, "VISIBLE", ocr_bbox, 0.1,
    )

    glyph_bbox = sizing["glyph_bbox_px"]
    assert glyph_bbox[1] > ocr_bbox[1]
    assert glyph_bbox[3] < ocr_bbox[3]
    assert sizing["height_mm"] < (ocr_bbox[3] - ocr_bbox[1]) * 0.1
    assert 0.0 < sizing["width_factor"] <= 2.0
    assert sizing["insertion_px"] == [ocr_bbox[0], ocr_bbox[3]]

    tight_bbox = [28, 20, 145, 41]
    tight = fidelity_module._derive_text_reconstruction_size(
        image, "VISIBLE", tight_bbox, 0.1,
    )
    assert tight["glyph_bbox_px"] == tight_bbox
    assert tight["height_mm"] == pytest.approx((tight_bbox[3] - tight_bbox[1]) * 0.1)
    assert tight["width_factor"] == 1.0
    assert tight["insertion_px"] == [tight_bbox[0], tight_bbox[3]]


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
