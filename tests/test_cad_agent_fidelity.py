from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import ezdxf
import fitz
import cv2
import numpy as np
import pytest

import cad_agent.fidelity as fidelity_module
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


def test_dimension_reconstruction_preserves_source_observed_normal_distance_for_1355_and_1525(
    tmp_path: Path,
) -> None:
    """Source-observed dimension placement must beat synthetic bbox offset."""
    from cad_agent.fidelity import run_fidelity_dimension_reconstruct, sha256_file

    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    rendered = output / manifest["pages"][0]["artifacts"]["rendered_png"]["artifact"]

    fixtures = [
        {
            "candidate_id": "rawtext-bd621064",
            "value": 1355.0,
            "bbox_px": [1732, 1168, 1785, 1186],
            "line_id": "rawline-5c0fc7e1",
            "p1_px": [1645.0, 1189.0],
            "p2_px": [1871.0, 1189.0],
        },
        {
            "candidate_id": "rawtext-6044e704",
            "value": 1525.0,
            "bbox_px": [1732, 1198, 1785, 1216],
            "line_id": "rawline-2e7a2d81",
            "p1_px": [1630.0, 1219.0],
            "p2_px": [1886.0, 1219.0],
        },
    ]
    observation_path = output / "dimension-observation.json"
    observation_path.write_text(json.dumps({
        "schema_version": "fidelity-dimension-observation-1.0",
        "private_artifact": True,
        "state": "needs_human_approval",
        "source": manifest["source"],
        "page": 1,
        "source_render_sha256": sha256_file(rendered),
        "candidates": [
            {
                "text": {
                    "id": item["candidate_id"],
                    "content": str(int(item["value"])),
                    "bbox_px": item["bbox_px"],
                    "rotation_deg": 0.0,
                    "confidence": 1.0,
                    "source": "test_fixture",
                    "semantic_role": "dimension_value",
                    "parsed_value": item["value"],
                },
                "nearby_line_ids": [item["line_id"]],
                "nearby_lines": [{
                    "id": item["line_id"],
                    "p1_px": item["p1_px"],
                    "p2_px": item["p2_px"],
                    "bbox_px": [*item["p1_px"], *item["p2_px"]],
                    "length_px": item["p2_px"][0] - item["p1_px"][0],
                }],
                "state": "needs_human_approval",
            }
            for item in fixtures
        ],
        "unresolved": [],
    }), encoding="utf-8")

    base_dxf = output / "base.dxf"
    ezdxf.new("R2010").saveas(base_dxf)
    approval_path = output / "dimension-approval.json"
    approval_path.write_text(json.dumps({
        "schema_version": "fidelity-dimension-approval-1.0",
        "private_artifact": True,
        "state": "approved-dimension-mappings",
        "source": manifest["source"],
        "page": 1,
        "observation": {"path": observation_path.name, "sha256": sha256_file(observation_path)},
        "base_dxf": {"path": base_dxf.name, "sha256": sha256_file(base_dxf)},
        "approval_reference": "approved-test",
        "mappings": [
            {"candidate_id": item["candidate_id"], "line_evidence_id": item["line_id"]}
            for item in fixtures
        ],
    }), encoding="utf-8")

    result = run_fidelity_dimension_reconstruct(
        source, output, manifest, approval_path, base_dxf, workspace_root=Path.cwd(),
    )
    dimensions = {str(entity.dxf.text): entity for entity in ezdxf.readfile(result).modelspace().query("DIMENSION")}
    scale = float(manifest["pages"][0]["pixel_to_paper_mm"]["used"])
    height_px = int(json.loads((output / manifest["pages"][0]["artifacts"]["layout_audit"]["artifact"]).read_text())["source_page"]["render_height_px"])

    actual_distances = {}
    expected_distances = {}
    for item in fixtures:
        bbox = item["bbox_px"]
        line_y = (item["p1_px"][1] + item["p2_px"][1]) / 2.0
        text_y = (bbox[1] + bbox[3]) / 2.0
        expected_source_distance_mm = abs(line_y - text_y) * scale
        p1 = (item["p1_px"][0] * scale, (height_px - item["p1_px"][1]) * scale)
        p2 = (item["p2_px"][0] * scale, (height_px - item["p2_px"][1]) * scale)
        line_midpoint = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
        dimension = dimensions[str(int(item["value"]))]
        assert (dimension.dxf.defpoint2.x, dimension.dxf.defpoint2.y) == pytest.approx(p1)
        assert (dimension.dxf.defpoint3.x, dimension.dxf.defpoint3.y) == pytest.approx(p2)
        actual_distances[str(int(item["value"]))] = abs(dimension.dxf.text_midpoint.y - line_midpoint[1])
        expected_distances[str(int(item["value"]))] = expected_source_distance_mm

    assert actual_distances == pytest.approx(expected_distances, abs=1e-9), (
        "synthetic current offsets do not preserve the independent source-observed distances: "
        f"actual={actual_distances}, expected={expected_distances}"
    )


@pytest.mark.causal_red
def test_dimension_line_base_separation_red_for_1355_and_1525(tmp_path: Path) -> None:
    """The dimension line base and the independently placed text must not share a point."""
    from cad_agent.fidelity import run_fidelity_dimension_reconstruct, sha256_file

    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    rendered = output / manifest["pages"][0]["artifacts"]["rendered_png"]["artifact"]

    fixtures = [
        {
            "candidate_id": "rawtext-bd621064",
            "value": 1355.0,
            "bbox_px": [1732, 1168, 1785, 1186],
            "line_id": "rawline-5c0fc7e1",
            "p1_px": [1645.0, 1189.0],
            "p2_px": [1871.0, 1189.0],
        },
        {
            "candidate_id": "rawtext-6044e704",
            "value": 1525.0,
            "bbox_px": [1732, 1198, 1785, 1216],
            "line_id": "rawline-2e7a2d81",
            "p1_px": [1630.0, 1219.0],
            "p2_px": [1886.0, 1219.0],
        },
    ]
    observation_path = output / "dimension-observation.json"
    observation_path.write_text(json.dumps({
        "schema_version": "fidelity-dimension-observation-1.0",
        "private_artifact": True,
        "state": "needs_human_approval",
        "source": manifest["source"],
        "page": 1,
        "source_render_sha256": sha256_file(rendered),
        "candidates": [
            {
                "text": {
                    "id": item["candidate_id"],
                    "content": str(int(item["value"])),
                    "bbox_px": item["bbox_px"],
                    "rotation_deg": 0.0,
                    "confidence": 1.0,
                    "source": "test_fixture",
                    "semantic_role": "dimension_value",
                    "parsed_value": item["value"],
                },
                "nearby_line_ids": [item["line_id"]],
                "nearby_lines": [{
                    "id": item["line_id"],
                    "p1_px": item["p1_px"],
                    "p2_px": item["p2_px"],
                    "bbox_px": [*item["p1_px"], *item["p2_px"]],
                    "length_px": item["p2_px"][0] - item["p1_px"][0],
                }],
                "state": "needs_human_approval",
            }
            for item in fixtures
        ],
        "unresolved": [],
    }), encoding="utf-8")

    base_dxf = output / "base.dxf"
    ezdxf.new("R2010").saveas(base_dxf)
    approval_path = output / "dimension-approval.json"
    approval_path.write_text(json.dumps({
        "schema_version": "fidelity-dimension-approval-1.0",
        "private_artifact": True,
        "state": "approved-dimension-mappings",
        "source": manifest["source"],
        "page": 1,
        "observation": {"path": observation_path.name, "sha256": sha256_file(observation_path)},
        "base_dxf": {"path": base_dxf.name, "sha256": sha256_file(base_dxf)},
        "approval_reference": "approved-test",
        "mappings": [
            {"candidate_id": item["candidate_id"], "line_evidence_id": item["line_id"]}
            for item in fixtures
        ],
    }), encoding="utf-8")

    result = run_fidelity_dimension_reconstruct(
        source, output, manifest, approval_path, base_dxf, workspace_root=Path.cwd(),
    )
    dimensions = {str(entity.dxf.text): entity for entity in ezdxf.readfile(result).modelspace().query("DIMENSION")}
    scale = float(manifest["pages"][0]["pixel_to_paper_mm"]["used"])
    height_px = int(json.loads(
        (output / manifest["pages"][0]["artifacts"]["layout_audit"]["artifact"]).read_text()
    )["source_page"]["render_height_px"])

    base_separation_failures = []
    for item in fixtures:
        p1 = (item["p1_px"][0] * scale, (height_px - item["p1_px"][1]) * scale)
        p2 = (item["p2_px"][0] * scale, (height_px - item["p2_px"][1]) * scale)
        line_midpoint = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = (dx**2 + dy**2) ** 0.5
        normal = (-dy / length, dx / length)
        bbox = item["bbox_px"]
        text_center = (
            ((bbox[0] + bbox[2]) / 2.0) * scale,
            (height_px - (bbox[1] + bbox[3]) / 2.0) * scale,
        )
        expected_text_distance = normal[0] * (text_center[0] - line_midpoint[0]) + normal[1] * (text_center[1] - line_midpoint[1])
        dimension = dimensions[str(int(item["value"]))]

        assert (dimension.dxf.defpoint2.x, dimension.dxf.defpoint2.y) == pytest.approx(p1)
        assert (dimension.dxf.defpoint3.x, dimension.dxf.defpoint3.y) == pytest.approx(p2)
        base_vector = (
            dimension.dxf.defpoint.x - line_midpoint[0],
            dimension.dxf.defpoint.y - line_midpoint[1],
        )
        actual_base_normal_distance = normal[0] * base_vector[0] + normal[1] * base_vector[1]
        if actual_base_normal_distance != pytest.approx(0.0, abs=1e-9):
            base_separation_failures.append({
                "value": item["value"],
                "actual_normal_distance": actual_base_normal_distance,
                "base": (dimension.dxf.defpoint.x, dimension.dxf.defpoint.y),
                "line_midpoint": line_midpoint,
            })
        actual_text_distance = normal[0] * (dimension.dxf.text_midpoint.x - line_midpoint[0]) + normal[1] * (
            dimension.dxf.text_midpoint.y - line_midpoint[1]
        )
        assert actual_text_distance == pytest.approx(expected_text_distance, abs=1e-9)

    assert not base_separation_failures, (
        "dimension base must remain on the selected source line while text placement is independent: "
        f"failures={base_separation_failures}"
    )


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
        assert observation["unresolved"][0] == "no OCR candidate is emitted as DXF TEXT or MTEXT without per-text approval and a Unicode glyph-render check"
        if observation["native_pdf_spans"]:
            assert observation["unresolved"][1] == "native PDF spans are separate unverified evidence; they are not OCR approval or reconstruction candidates"
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


def test_native_pdf_text_observation_is_separate_hash_bound_and_review_only(tmp_path: Path) -> None:
    source = tmp_path / "native.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "NATIVE 123", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)

    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    native = observation["native_pdf_spans"]
    ocr = observation["candidates"]

    assert len(native) == 1
    assert native[0]["content"] == "NATIVE 123"
    assert native[0]["visibility"] == "unverified"
    assert native[0]["source_wmode"] == 0
    assert native[0]["source_paint_evidence"]["wmode"] == 0
    assert native[0]["source_paint_evidence"]["type"] == 0
    assert native[0]["source_paint_evidence"]["opacity"] == 1.0
    assert native[0]["source_sha256"] == manifest["source"]["sha256"]
    audit_path = output / observation["source_layout_audit"]["artifact"]
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert native[0]["render_sha256"] == audit["source_page"]["render_sha256"]
    assert native[0]["mapping_version"] == "displayed-page-box-v1"
    assert native[0]["bbox_px"][0] == pytest.approx(80, abs=1.0)
    assert native[0]["bbox_px"][2] > native[0]["bbox_px"][0]
    assert all(item.get("source") != "native_pdf" for item in ocr)
    assert all(not item.get("semantic_role") for item in native)
    assert "TEXT" not in observation and "MTEXT" not in observation
    with pytest.raises(FidelityError, match="unknown OCR candidate"):
        write_fidelity_text_approval(
            source, output, manifest, 1, observation_path, [native[0]["id"]], "approved-test",
            workspace_root=Path.cwd(),
        )

    # A hand-crafted approval sidecar must not bypass the OCR-only candidate
    # admission performed by write_fidelity_text_approval.
    from cad_agent import fidelity as fidelity_module

    approval_path = output / "fidelity_text_approvals" / "page_01.json"
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(json.dumps({
        "schema_version": "fidelity-text-approval-1.0",
        "private_artifact": True,
        "state": "approved-text-candidates-only",
        "source": manifest["source"],
        "page": 1,
        "observation": fidelity_module._artifact(observation_path, output),
        "approval_reference": "approved-test",
        "approved_candidates": [{
            "candidate": native[0],
            "glyph_render": {"passed": True},
        }],
    }, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(FidelityError, match="OCR candidate"):
        run_fidelity_text_reconstruct(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )
    assert not (output / "text_reconstruction" / "page_01").exists()


def test_native_pdf_observation_maps_exact_spans_inside_aggregated_paint_trace() -> None:
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "414 MM", fontsize=18)
    page.insert_text((190, 80), "ANNOTATION", fontsize=18)
    traces = page.get_texttrace()
    assert len(traces) == 2

    merged = dict(traces[0])
    merged_chars = [*traces[0]["chars"], *traces[1]["chars"]]
    merged["chars"] = merged_chars
    merged["seqno"] = 0
    merged["bbox"] = (
        min(trace["bbox"][0] for trace in traces),
        min(trace["bbox"][1] for trace in traces),
        max(trace["bbox"][2] for trace in traces),
        max(trace["bbox"][3] for trace in traces),
    )

    class AggregatedPaintTracePage:
        def __getattr__(self, name: str) -> Any:
            return getattr(page, name)

        def get_texttrace(self) -> list[dict[str, Any]]:
            return [merged]

        def get_bboxlog(self) -> list[tuple[str, tuple[float, float, float, float]]]:
            return [("fill-text", merged["bbox"])]

    try:
        records = fidelity_module._native_pdf_text_span_records(
            AggregatedPaintTracePage(), 1, "a" * 64, "b" * 64, 800, 600,
            "displayed-page-box-v1",
        )
    finally:
        document.close()

    assert [record["content"] for record in records] == ["414 MM", "ANNOTATION"]
    assert all(record["visibility"] == "unverified" for record in records)
    assert all(record["semantic_role"] is None for record in records)
    assert all(record["evidence_kind"] == "native_pdf" for record in records)
    assert all(record["source_paint_evidence"]["bbox_pt"] != merged["bbox"] for record in records)
    assert [record["source_paint_evidence"]["member_traces"][0]["text"] for record in records] == [
        "414 MM", "ANNOTATION",
    ]
    assert all(
        record["source_paint_evidence"]["member_traces"][0]["character_range"]
        for record in records
    )
    assert records[0]["bbox_px"][0] == pytest.approx(80, abs=1.0)
    assert records[0]["bbox_px"][2] > records[0]["bbox_px"][0]


def test_native_pdf_observation_rejects_source_glyph_remapped_to_space_when_later_filled() -> None:
    from cad_agent import fidelity as fidelity_module

    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((250, 250), "CONTROL", fontsize=12)
    page.clean_contents()
    cmap_stream = (
        b"/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        b"/CMapName /CustomSpaceMap def\n/CMapType 2 def\n"
        b"1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        b"1 beginbfchar\n<4D> <0020>\nendbfchar\nendcmap\n"
        b"CMapName currentdict /CMap defineresource pop\nend\nend\n"
    )
    cmap_xref = document.get_new_xref()
    document.update_object(cmap_xref, "<< >>")
    document.update_stream(cmap_xref, cmap_stream)
    font_xref = document.get_new_xref()
    document.update_object(
        font_xref,
        f"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding /ToUnicode {cmap_xref} 0 R >>",
    )
    pg_obj = document.xref_object(page.xref)
    if "/Font <<" in pg_obj:
        document.update_object(page.xref, pg_obj.replace("/Font <<", f"/Font << /F99 {font_xref} 0 R ", 1))
    else:
        _, res_val = document.xref_get_key(page.xref, "Resources")
        res_xref = int(res_val.split()[0])
        res_obj = document.xref_object(res_xref)
        if "/Font <<" in res_obj:
            document.update_object(res_xref, res_obj.replace("/Font <<", f"/Font << /F99 {font_xref} 0 R ", 1))
        else:
            _, font_val = document.xref_get_key(res_xref, "Font")
            existing_font_xref = int(font_val.split()[0])
            document.update_object(
                existing_font_xref,
                document.xref_object(existing_font_xref).replace("<<", f"<< /F99 {font_xref} 0 R ", 1),
            )
    content_xref = page.get_contents()[0]
    document.update_stream(
        content_xref,
        document.xref_stream(content_xref) + b"\nq BT 0 0 0 rg /F99 18 Tf 1 0 0 1 58 178 Tm (M100) Tj ET Q\n",
    )
    assert "100" in page.get_text("text")
    source_trace = next(trace for trace in page.get_texttrace() if any(char[0] == 0x20 for char in trace["chars"]))
    masked_rect = next(fitz.Rect(char[3]) for char in source_trace["chars"] if char[0] == 0x20)
    baseline_pdf = fitz.open(stream=document.tobytes(), filetype="pdf")
    try:
        baseline_records = fidelity_module._native_pdf_text_span_records(
            baseline_pdf[0], 1, "a" * 64, "b" * 64, 800, 600, "displayed-page-box-v1",
        )
    finally:
        baseline_pdf.close()
    assert any(record["content"].strip() == "100" for record in baseline_records)
    before_fill = page.get_pixmap(clip=masked_rect, alpha=False)
    pdf_y = page.rect.height - masked_rect.y1
    fill = f"\nq 1 1 1 rg {masked_rect.x0:.4f} {pdf_y:.4f} {masked_rect.width:.4f} {masked_rect.height:.4f} re f Q\n".encode("ascii")
    document.update_stream(content_xref, document.xref_stream(content_xref) + fill)

    reopened = fitz.open(stream=document.tobytes(), filetype="pdf")
    document.close()
    try:
        after_fill = reopened[0].get_pixmap(clip=masked_rect, alpha=False)
        assert any(sample < 240 for sample in before_fill.samples)
        assert all(sample > 250 for sample in after_fill.samples)

        import copy

        class EmptyMetricSpaceGlyphPage:
            def __getattr__(self, name: str) -> Any:
                return getattr(reopened[0], name)

            def get_texttrace(self, *args: Any, **kwargs: Any) -> Any:
                traces = copy.deepcopy(reopened[0].get_texttrace(*args, **kwargs))
                for trace in traces:
                    chars = list(trace.get("chars", ()))
                    for index, char in enumerate(chars):
                        if char[0] == 0x20:
                            empty_bbox = (char[3][0], char[3][1], char[3][0], char[3][1])
                            chars[index] = (*char[:3], empty_bbox, *char[4:])
                    trace["chars"] = tuple(chars)
                return traces

        records = fidelity_module._native_pdf_text_span_records(
            EmptyMetricSpaceGlyphPage(), 1, "a" * 64, "b" * 64, 800, 600, "displayed-page-box-v1",
        )
    finally:
        reopened.close()

    assert not any(record["content"].strip() == "100" for record in records)
    assert "CONTROL" in {record["content"] for record in records}


def test_native_pdf_observation_bounds_cumulative_compound_fill_work(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from cad_agent import fidelity as fidelity_module

    original_reserve = fidelity_module._GlyphPairWorkBudget.reserve
    reservation_attempts: list[tuple[int, bool]] = []
    reservation_contexts: list[dict[str, Any]] = []
    separation_calls: list[int] = []

    def observe_reservation(self, left, right) -> bool:
        before = self.work
        reserved = original_reserve(self, left, right)
        reservation_attempts.append((len(left) * len(right), reserved))
        caller = sys._getframe(1)
        source_span = None
        source_trace = None
        frame = caller
        for _ in range(6):
            if frame is None:
                break
            source_span = source_span or frame.f_locals.get("span")
            source_trace = source_trace or frame.f_locals.get("trace")
            frame = frame.f_back
        local = caller.f_locals
        flat_subs = local.get("flat_subs")
        target_glyphs = local.get("target_glyphs")
        reservation_contexts.append({
            "budget_id": id(self),
            "budget_before": before,
            "budget_after": self.work,
            "paint_type": local.get("paint_type"),
            "flat_subpaths": len(flat_subs) if isinstance(flat_subs, list) else None,
            "target_glyphs": len(target_glyphs) if isinstance(target_glyphs, list) else None,
            "metric_hit": local.get("metric_hit"),
            "source_span_chars": len(source_span.get("text", "")) if isinstance(source_span, dict) else None,
            "source_trace_seqno": source_trace.get("seqno") if isinstance(source_trace, dict) else None,
            "source_trace_chars": len(source_trace.get("chars", ())) if isinstance(source_trace, dict) else None,
        })
        return reserved

    monkeypatch.setattr(fidelity_module._GlyphPairWorkBudget, "reserve", observe_reservation)

    def report_verified_separation(self, sequence, *_args, **_kwargs):
        separation_calls.append(sequence)
        return True

    monkeypatch.setattr(
        fidelity_module._NativePdfThinStrokeCheck,
        "separates_dark_fill",
        report_verified_separation,
    )

    document = fitz.open()
    page = document.new_page(width=4000, height=300)
    page.insert_text((10, 250), "CONTROL", fontsize=12)
    page.insert_text((100, 120), "A" * 250, fontsize=12)
    page.clean_contents()

    # A single compound fill has 250 verified subpaths. The first two cover
    # the source glyph metrics; one 250x250 reservation fits, while the second
    # reservation against that same source trace exceeds the 100,000 cap.
    fill = page.new_shape()
    for _ in range(250):
        fill.draw_rect(fitz.Rect(101, 110, 105, 115))
    fill.finish(color=None, fill=(0, 0, 0), closePath=True)
    fill.commit()

    reopened = fitz.open(stream=document.tobytes(), filetype="pdf")
    document.close()
    try:
        records = fidelity_module._native_pdf_text_span_records(
            reopened[0], 1, "a" * 64, "b" * 64, 800, 600, "displayed-page-box-v1",
        )
    finally:
        reopened.close()

    assert "CONTROL" in {record["content"] for record in records}
    grouped_attempts: dict[int, list[tuple[int, bool]]] = {}
    grouped_contexts: dict[int, list[dict[str, Any]]] = {}
    for attempt, context in zip(reservation_attempts, reservation_contexts, strict=True):
        grouped_attempts.setdefault(context["budget_id"], []).append(attempt)
        grouped_contexts.setdefault(context["budget_id"], []).append(context)
    exhausted = [
        budget_id for budget_id, attempts in grouped_attempts.items()
        if attempts == [(62_500, True), (62_500, False)]
    ]
    assert len(exhausted) == 1, repr({key: (grouped_attempts[key], grouped_contexts[key]) for key in grouped_attempts})
    source_bound = grouped_contexts[exhausted[0]]
    assert all(
        context["source_span_chars"] == 250
        and context["source_trace_chars"] == 250
        and context["source_trace_seqno"] == 1
        and context["paint_type"] == "fill-path"
        and context["flat_subpaths"] == 250
        and context["target_glyphs"] == 250
        for context in source_bound
    ), repr(source_bound)
    assert source_bound[0]["budget_before"] == 0 and source_bound[0]["budget_after"] == 62_500
    assert source_bound[1]["budget_before"] == 62_500 and source_bound[1]["budget_after"] == 62_500
    assert not separation_calls, "an exhausted fill must not enter replay with a fresh allowance"
    assert not any(len(record["content"]) >= 250 for record in records), (
        "a later successful optional proof must not clear an exhausted earlier budget"
    )


def test_native_pdf_observation_does_not_replay_after_later_budget_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    from cad_agent import fidelity as fidelity_module

    original_reserve = fidelity_module._GlyphPairWorkBudget.reserve
    reservations: list[tuple[int, int, int, bool, bool]] = []

    def observe_reservation(self, left, right) -> bool:
        before = self.work
        reserved = original_reserve(self, left, right)
        caller = sys._getframe(1).f_locals
        target_glyphs = caller.get("target_glyphs")
        flat_subs = caller.get("flat_subs")
        if isinstance(target_glyphs, list) and isinstance(flat_subs, list):
            deferred = caller.get("deferred_fills")
            reservations.append((
                id(self), before, len(target_glyphs) * len(flat_subs), reserved,
                bool(deferred),
            ))
        return reserved

    monkeypatch.setattr(fidelity_module._GlyphPairWorkBudget, "reserve", observe_reservation)

    optional_proofs: list[int] = []

    def report_verified_separation(self, sequence, *_args, **_kwargs):
        optional_proofs.append(sequence)
        return True

    monkeypatch.setattr(
        fidelity_module._NativePdfThinStrokeCheck,
        "separates_dark_fill",
        report_verified_separation,
    )

    document = fitz.open()
    page = document.new_page(width=4000, height=300)
    page.insert_text((10, 250), "CONTROL", fontsize=12)
    page.insert_text((100, 120), "A" * 250, fontsize=12)
    page.clean_contents()

    # The first fill intersects glyph metrics only below the baseline. It sets
    # deferred optional work and consumes two 37,500-pair reservations. A later
    # fill's first 37,500-pair reservation is then denied at 75,000 pairs.
    for _ in range(2):
        fill = page.new_shape()
        for _ in range(150):
            fill.draw_rect(fitz.Rect(101, 120.1, 105, 121.5))
        fill.finish(color=None, fill=(0, 0, 0), closePath=True)
        fill.commit()

    reopened = fitz.open(stream=document.tobytes(), filetype="pdf")
    document.close()
    try:
        records = fidelity_module._native_pdf_text_span_records(
            reopened[0], 1, "a" * 64, "b" * 64, 800, 600, "displayed-page-box-v1",
        )
    finally:
        reopened.close()

    assert "CONTROL" in {record["content"] for record in records}
    matching_budgets = {}
    for budget_id, before, work, reserved, deferred in reservations:
        if work == 37_500:
            matching_budgets.setdefault(budget_id, []).append((before, reserved, deferred))
    assert any(
        attempts[:3] == [
            (0, True, False),
            (37_500, True, True),
            (75_000, False, True),
        ]
        for attempts in matching_budgets.values()
    ), repr(matching_budgets)
    assert not optional_proofs, (
        "a later reservation failure after earlier fill deferral must not enter fresh-budget replay"
    )


def test_native_pdf_observation_bounds_glyph_by_stroke_segment_comparisons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    from cad_agent import fidelity as fidelity_module

    original_reserve = fidelity_module._GlyphPairWorkBudget.reserve
    stroke_reservations: list[tuple[int, int, int, bool]] = []

    def observe_reservation(self, left, right) -> bool:
        reserved = original_reserve(self, left, right)
        caller = sys._getframe(1).f_locals
        target_glyphs = caller.get("target_glyphs")
        cand_segs = caller.get("cand_segs")
        if isinstance(target_glyphs, list) and isinstance(cand_segs, list):
            stroke_reservations.append((len(target_glyphs), len(cand_segs), len(left) * len(right), reserved))
        return reserved

    monkeypatch.setattr(fidelity_module._GlyphPairWorkBudget, "reserve", observe_reservation)

    document = fitz.open()
    page = document.new_page(width=4000, height=300)
    page.insert_text((10, 250), "CONTROL", fontsize=12)
    page.insert_text((100, 120), "A" * 250, fontsize=12)
    page.clean_contents()
    trace = next(trace for trace in page.get_texttrace() if len(trace.get("chars", ())) == 250)
    x0, y0, x1, y1 = trace["bbox"]
    stroke = page.new_shape()
    for index in range(500):
        y = y0 + (y1 - y0) * index / 499
        stroke.draw_line((x0 + 0.1, y), (x1 - 0.1, y))
    stroke.finish(color=(0, 0, 0), width=0.1)
    stroke.commit()

    reopened = fitz.open(stream=document.tobytes(), filetype="pdf")
    document.close()
    try:
        records = fidelity_module._native_pdf_text_span_records(
            reopened[0], 1, "a" * 64, "b" * 64, 800, 600, "displayed-page-box-v1",
        )
    finally:
        reopened.close()

    assert "CONTROL" in {record["content"] for record in records}
    assert any(
        glyph_count == 250 and segment_count >= 500 and work > 100_000 and not reserved
        for glyph_count, segment_count, work, reserved in stroke_reservations
    ), repr(stroke_reservations)
    assert not any(len(record["content"]) >= 250 for record in records)


def test_native_pdf_observation_bounds_below_baseline_glyph_lookup_work() -> None:
    from cad_agent import fidelity as fidelity_module

    class CountingChars(list):
        def __init__(self, values):
            super().__init__(values)
            self.visited = 0

        def __iter__(self):
            for value in super().__iter__():
                self.visited += 1
                yield value

    document = fitz.open()
    page = document.new_page(width=4000, height=300)
    page.insert_text((100, 120), "A" * 250, fontsize=12)
    page.clean_contents()
    stroke = page.new_shape()
    stroke.draw_line((100, 121), (2101, 121))
    stroke.finish(color=(0, 0, 0), width=0.1)
    stroke.commit()

    reopened = fitz.open(stream=document.tobytes(), filetype="pdf")
    document.close()
    class CountingCharPage:
        def __init__(self, inner):
            self.inner = inner
            self.counted_chars = []

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def get_texttrace(self):
            traces = []
            for trace in self.inner.get_texttrace():
                copied = dict(trace)
                counted = CountingChars(copied.get("chars", ()))
                self.counted_chars.append(counted)
                copied["chars"] = counted
                traces.append(copied)
            return traces

    counted_page = CountingCharPage(reopened[0])
    try:
        records = fidelity_module._native_pdf_text_span_records(
            counted_page, 1, "a" * 64, "b" * 64, 800, 600, "displayed-page-box-v1",
        )
    finally:
        reopened.close()

    assert any(len(record["content"]) == 250 for record in records)
    raw_char_count = max(len(chars) for chars in counted_page.counted_chars)
    visited_chars = sum(chars.visited for chars in counted_page.counted_chars)
    assert raw_char_count == 250
    assert visited_chars <= raw_char_count * 10, (
        f"below-baseline glyph lookup rescanned raw characters {visited_chars} times "
        f"for a {raw_char_count}-character trace"
    )


def test_native_pdf_observation_accepts_genuine_blank_space_when_unoccluded() -> None:
    from cad_agent import fidelity as fidelity_module

    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((60, 120), " 100", fontsize=18)
    try:
        records = fidelity_module._native_pdf_text_span_records(
            page, 1, "a" * 64, "b" * 64, 800, 600, "displayed-page-box-v1",
        )
    finally:
        document.close()
    assert any(record["content"].strip() == "100" for record in records)


def test_glyph_pair_work_budget_caps_cumulative_cartesian_comparisons() -> None:
    from cad_agent.fidelity import _GlyphPairWorkBudget

    budget = _GlyphPairWorkBudget(100_000)
    assert budget.reserve([None] * 320, [None] * 300)
    assert budget.work == 96_000
    assert not budget.reserve([None] * 320, [None] * 20)
    assert budget.work == 96_000
    assert budget.reserve([None] * 2, [None] * 2)
    assert budget.work == 96_004


def test_native_pdf_observation_fails_closed_for_excessive_glyph_pair_work() -> None:
    from cad_agent import fidelity as fidelity_module

    document = fitz.open()
    page = document.new_page(width=5000, height=300)
    page.insert_text((30, 80), "M" * 460, fontsize=4)
    page.insert_text((30, 140), "CONTROL", fontsize=18)
    try:
        records = fidelity_module._native_pdf_text_span_records(
            page, 1, "a" * 64, "b" * 64, 800, 600, "displayed-page-box-v1",
        )
    finally:
        document.close()
    assert "CONTROL" in {record["content"] for record in records}
    assert not any(len(record["content"]) >= 400 for record in records)


@pytest.mark.parametrize("bad_coordinate", [float("inf"), "not-a-number"])
def test_native_pdf_observation_skips_malformed_span_bbox_without_aborting_siblings(bad_coordinate: Any) -> None:
    from cad_agent import fidelity as fidelity_module

    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "BROKEN", fontsize=18)
    page.insert_text((190, 80), "CONTROL", fontsize=18)

    class MalformedSpanPage:
        def __getattr__(self, name: str) -> Any:
            return getattr(page, name)

        def get_text(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            result = page.get_text(*args, **kwargs)
            if args and args[0] == "dict":
                for block in result.get("blocks", []):
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        if spans:
                            bbox = list(spans[0]["bbox"])
                            bbox[2] = bad_coordinate
                            spans[0]["bbox"] = tuple(bbox)
                            return result
            return result

    try:
        records = fidelity_module._native_pdf_text_span_records(
            MalformedSpanPage(), 1, "a" * 64, "b" * 64, 800, 600,
            "displayed-page-box-v1",
        )
    finally:
        document.close()

    assert [record["content"] for record in records] == ["CONTROL"]


@pytest.mark.parametrize(
    ("case", "expected_contents"),
    [
        ("source_mismatch", []),
        ("origin_mismatch", []),
        ("duplicate_trace", []),
        ("later_paint", ["ANNOTATION"]),
    ],
)
def test_native_pdf_aggregated_trace_mapping_fails_closed(
    case: str, expected_contents: list[str],
) -> None:
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "414 MM", fontsize=18)
    page.insert_text((190, 80), "ANNOTATION", fontsize=18)
    traces = page.get_texttrace()
    merged = dict(traces[0])
    merged["chars"] = [*traces[0]["chars"], *traces[1]["chars"]]
    merged["seqno"] = 0
    merged["bbox"] = (
        min(trace["bbox"][0] for trace in traces),
        min(trace["bbox"][1] for trace in traces),
        max(trace["bbox"][2] for trace in traces),
        max(trace["bbox"][3] for trace in traces),
    )
    spans = [
        span
        for block in page.get_text("dict")["blocks"]
        for line in block.get("lines", [])
        for span in line.get("spans", [])
    ]
    target_bbox = next(span["bbox"] for span in spans if span["text"] == "414 MM")

    class ControlledAggregatedTracePage:
        def __getattr__(self, name: str) -> Any:
            return getattr(page, name)

        def get_text(self, option: str, *args: Any, **kwargs: Any) -> Any:
            result = page.get_text(option, *args, **kwargs)
            if option == "dict" and case in {"source_mismatch", "origin_mismatch"}:
                for block in result["blocks"]:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            if span.get("text") == "414 MM":
                                if case == "source_mismatch":
                                    span["text"] = "415 MM"
                                else:
                                    span["origin"] = (span["origin"][0] + 10, span["origin"][1])
            return result

        def get_texttrace(self) -> list[dict[str, Any]]:
            if case == "duplicate_trace":
                duplicate = dict(merged, seqno=1)
                return [merged, duplicate]
            return [merged]

        def get_bboxlog(self) -> list[tuple[str, tuple[float, float, float, float]]]:
            result = [("fill-text", merged["bbox"])]
            if case == "duplicate_trace":
                result.append(("fill-text", merged["bbox"]))
            elif case == "later_paint":
                result.append(("fill-path", target_bbox))
            return result

    try:
        records = fidelity_module._native_pdf_text_span_records(
            ControlledAggregatedTracePage(), 1, "a" * 64, "b" * 64, 800, 600,
            "displayed-page-box-v1",
        )
    finally:
        document.close()

    assert [record["content"] for record in records] == expected_contents
    assert all(record["visibility"] == "unverified" for record in records)
    assert all(record["semantic_role"] is None for record in records)


def test_native_pdf_aggregated_trace_preserves_rotated_text_direction() -> None:
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((190, 250), "ROTATED NOTE", fontsize=18, rotate=90)
    page.insert_text((240, 250), "ROTATED CALL", fontsize=18, rotate=90)
    traces = page.get_texttrace()
    assert len(traces) == 2
    merged = dict(traces[0])
    merged["chars"] = [*traces[0]["chars"], *traces[1]["chars"]]
    merged["seqno"] = 0
    merged["bbox"] = (
        min(trace["bbox"][0] for trace in traces),
        min(trace["bbox"][1] for trace in traces),
        max(trace["bbox"][2] for trace in traces),
        max(trace["bbox"][3] for trace in traces),
    )

    class RotatedAggregatedTracePage:
        def __getattr__(self, name: str) -> Any:
            return getattr(page, name)

        def get_texttrace(self) -> list[dict[str, Any]]:
            return [merged]

        def get_bboxlog(self) -> list[tuple[str, tuple[float, float, float, float]]]:
            return [("fill-text", merged["bbox"])]

    try:
        records = fidelity_module._native_pdf_text_span_records(
            RotatedAggregatedTracePage(), 1, "a" * 64, "b" * 64, 800, 600,
            "displayed-page-box-v1",
        )
    finally:
        document.close()

    assert [record["content"] for record in records] == ["ROTATED NOTE", "ROTATED CALL"]
    assert all(abs(abs(record["rotation_deg"]) - 90) < 0.01 for record in records)
    assert all(record["visibility"] == "unverified" for record in records)
    assert all(record["semantic_role"] is None for record in records)


def test_native_pdf_observation_keeps_named_layer_and_trace_recovers_replacement_glyph() -> None:
    from cad_agent import fidelity as fidelity_module

    document = fitz.open()
    page = document.new_page(width=400, height=300)
    dimensions = document.add_ocg("Dimensions", on=1)
    page.insert_text((40, 80), "639\u00b11", fontsize=18, oc=dimensions)

    class ReplacementGlyphPage:
        def __getattr__(self, name: str) -> Any:
            return getattr(page, name)

        def get_text(self, option: str, *args: Any, **kwargs: Any) -> Any:
            result = page.get_text(option, *args, **kwargs)
            if option == "dict":
                for block in result["blocks"]:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            if span.get("text") == "639\u00b11":
                                span["text"] = "639\ufffd1"
            return result

    try:
        records = fidelity_module._native_pdf_text_span_records(
            ReplacementGlyphPage(), 1, "a" * 64, "b" * 64, 800, 600,
            "displayed-page-box-v1",
        )
    finally:
        document.close()

    assert len(records) == 1
    assert records[0]["content"] == "639\u00b11"
    assert records[0]["source_paint_evidence"]["layer"] == "Dimensions"
    assert records[0]["visibility"] == "unverified"
    assert records[0]["semantic_role"] is None


def test_native_pdf_observation_refuses_conflicting_trace_character_mapping() -> None:
    from cad_agent import fidelity as fidelity_module

    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "639\u00b11", fontsize=18)

    class ConflictingTextPage:
        def __getattr__(self, name: str) -> Any:
            return getattr(page, name)

        def get_text(self, option: str, *args: Any, **kwargs: Any) -> Any:
            result = page.get_text(option, *args, **kwargs)
            if option == "dict":
                for block in result["blocks"]:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            if span.get("text") == "639\u00b11":
                                span["text"] = "639X1"
            return result

    try:
        records = fidelity_module._native_pdf_text_span_records(
            ConflictingTextPage(), 1, "a" * 64, "b" * 64, 800, 600,
            "displayed-page-box-v1",
        )
    finally:
        document.close()

    assert records == []


@pytest.mark.parametrize(
    ("case", "expect_nominal"),
    [
        ("adjacent", True),
        ("clear_trace_gap", True),
        ("substantial_overlap", False),
        ("different_baseline", False),
        ("different_font_size", True),
        ("different_font", False),
        ("different_color", False),
        ("degenerate_bounds", False),
        ("wide_stroke_text", False),
    ],
)
def test_native_pdf_observation_only_ignores_tiny_matching_text_edge(
    case: str, expect_nominal: bool,
) -> None:
    from cad_agent import fidelity as fidelity_module

    document = fitz.open()
    page = document.new_page(width=400, height=300)
    font_size = 18
    first_x = 40
    first_y = 80
    nominal = "639"
    tolerance = "\u00b11"
    first_width = fitz.get_text_length(nominal, fontname="helv", fontsize=font_size)
    second_size = font_size - 1 if case == "different_font_size" else font_size
    second_font = "tiro" if case == "different_font" else "helv"
    overlap = 2.0 if case == "substantial_overlap" else -0.04 if case == "clear_trace_gap" else 0.02
    second_x = first_x + first_width - overlap
    second_y = first_y - 0.1 if case == "different_baseline" else first_y
    render_mode = 1 if case == "wide_stroke_text" else 0
    border_width = 10 if case == "wide_stroke_text" else 1
    page.insert_text(
        (first_x, first_y), nominal, fontname="helv", fontsize=font_size,
        render_mode=render_mode, border_width=border_width,
    )
    text_color = (1, 0, 0) if case == "different_color" else (0, 0, 0)
    page.insert_text(
        (second_x, second_y), tolerance, fontname=second_font, fontsize=second_size,
        color=text_color, render_mode=render_mode, border_width=border_width,
    )

    class SplitSpanPage:
        def __getattr__(self, name: str) -> Any:
            return getattr(page, name)

        def get_text(self, option: str, *args: Any, **kwargs: Any) -> Any:
            result = page.get_text(option, *args, **kwargs)
            if option == "dict":
                traces = page.get_texttrace()
                for block in result["blocks"]:
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        if len(spans) == 1 and spans[0].get("text") == nominal + tolerance:
                            source_span = spans[0]
                            split = []
                            for content, trace in zip((nominal, tolerance), traces):
                                span = dict(source_span)
                                span["text"] = content
                                span["bbox"] = trace["bbox"]
                                span["origin"] = trace["chars"][0][2]
                                span["font"] = trace["font"]
                                span["size"] = trace["size"]
                                split.append(span)
                            line["spans"] = split
            return result

        def get_texttrace(self) -> list[dict[str, Any]]:
            traces = page.get_texttrace()
            if case == "degenerate_bounds" and len(traces) == 2:
                traces[1] = dict(traces[1], bbox=(second_x, second_y, second_x, second_y))
            return traces

    try:
        records = fidelity_module._native_pdf_text_span_records(
            SplitSpanPage(), 1, "a" * 64, "b" * 64, 800, 600, "displayed-page-box-v1",
        )
    finally:
        document.close()

    contents = [record["content"] for record in records]
    assert (nominal in contents) is expect_nominal
    if expect_nominal:
        assert tolerance in contents
        assert all(record["visibility"] == "unverified" for record in records)


def test_native_pdf_observation_excludes_hidden_ocr_over_visible_raster_text(tmp_path: Path) -> None:
    source = tmp_path / "visible-raster-hidden-ocr.pdf"
    output = tmp_path / "private-staging"
    image = np.full((48, 240, 3), 255, dtype=np.uint8)
    cv2.putText(image, "OCR NOTE", (3, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 0), 2)
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_image(fitz.Rect(40, 45, 280, 93), stream=encoded.tobytes())
    page.insert_text((48, 80), "OCR NOTE", fontsize=18, render_mode=3)
    document.save(source)
    document.close()

    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))

    rendered = cv2.imread(output / manifest["pages"][0]["artifacts"]["rendered_png"]["artifact"])
    assert rendered is not None and np.any(cv2.cvtColor(rendered, cv2.COLOR_BGR2GRAY) < 100)
    assert observation["native_pdf_spans"] == []


def test_native_pdf_observation_excludes_zero_opacity_text(tmp_path: Path) -> None:
    source = tmp_path / "transparent-native-text.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "TRANSPARENT", fontsize=18, fill_opacity=0)
    document.save(source)
    document.close()

    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))

    assert observation["native_pdf_spans"] == []


def test_native_pdf_observation_excludes_text_used_only_as_a_clipping_path(tmp_path: Path) -> None:
    source = tmp_path / "clip-only-native-text.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "CLIP ONLY", fontsize=18, render_mode=7)
    document.save(source)
    document.close()

    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))

    assert observation["native_pdf_spans"] == []


@pytest.mark.parametrize("character_spacing", [0, 1, 2])
def test_native_pdf_observation_excludes_partially_clipped_text(
    tmp_path: Path, character_spacing: int,
) -> None:
    source = tmp_path / "partially-clipped-native-text.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "PARTIALLY CLIPPED", fontsize=18)
    content_xrefs = page.get_contents()
    assert len(content_xrefs) == 1
    stream = document.xref_stream(content_xrefs[0])
    if character_spacing:
        stream = stream.replace(b"BT", f"BT\n{character_spacing} Tc".encode(), 1)
    document.update_stream(content_xrefs[0], b"q 40 210 45 30 re W n\n" + stream + b"\nQ\n")
    document.save(source)
    document.close()

    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))

    assert observation["native_pdf_spans"] == []


def test_native_pdf_observation_excludes_text_covered_by_later_paint(tmp_path: Path) -> None:
    source = tmp_path / "covered-native-text.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "PARTIALLY COVERED", fontsize=18)
    page.draw_rect(fitz.Rect(90, 65, 125, 85), color=None, fill=(1, 1, 1))
    document.save(source)
    document.close()

    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))

    assert observation["native_pdf_spans"] == []


def test_native_pdf_observation_excludes_text_on_disabled_optional_content_layer(tmp_path: Path) -> None:
    source = tmp_path / "disabled-layer-native-text.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    ocg = document.add_ocg("Hidden annotations", on=0)
    page.insert_text((40, 80), "HIDDEN LAYER", fontsize=18, oc=ocg)
    document.save(source)
    document.close()

    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))

    assert observation["native_pdf_spans"] == []


def test_native_pdf_observation_rejects_vertical_writing_mode(tmp_path: Path) -> None:
    from cad_agent import fidelity as fidelity_module

    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "VERTICAL", fontsize=18)

    class VerticalWritingModePage:
        def __init__(self, wrapped: fitz.Page) -> None:
            self._wrapped = wrapped

        def __getattr__(self, name: str) -> Any:
            return getattr(self._wrapped, name)

        def get_text(self, option: str, *args: Any, **kwargs: Any) -> Any:
            result = self._wrapped.get_text(option, *args, **kwargs)
            if option == "dict":
                for block in result["blocks"]:
                    for line in block.get("lines", []):
                        line["wmode"] = 1
            return result

        def get_texttrace(self) -> list[dict[str, Any]]:
            result = self._wrapped.get_texttrace()
            for span in result:
                span["wmode"] = 1
            return result

    with document:
        records = fidelity_module._native_pdf_text_span_records(
            VerticalWritingModePage(page), 1, "a" * 64, "b" * 64, 800, 600,
            "displayed-page-box-v1",
        )

    assert records == []


def test_native_pdf_text_review_shows_source_bound_visibility_choices(tmp_path: Path) -> None:
    source = tmp_path / "native-review.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "VISIBLE NATIVE", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())

    review_path = write_fidelity_text_review_index(source, output, manifest, workspace_root=Path.cwd())
    review_html = review_path.read_text(encoding="utf-8")

    assert "native_pdf_spans" in review_html
    assert "native-span-review" in review_html
    assert "visible_and_legible" in review_html
    assert "VISIBLE NATIVE" in review_html


@pytest.mark.parametrize("source_name", [
    '</script><script id="injected">console.log("proof")</script>',
    '</ScRiPt><img src=x onerror="console.log(1)">',
    'Bản vẽ <1> & "quoted".pdf',
])
def test_native_pdf_text_review_keeps_manifest_source_name_inside_script_data(
    tmp_path: Path, source_name: str,
) -> None:
    from html.parser import HTMLParser

    class ReviewParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.tags: list[str] = []
            self.script_data: list[str] = []
            self.in_script = False

        def handle_starttag(self, tag: str, attrs: list) -> None:
            self.tags.append(tag)
            self.in_script = tag == "script"

        def handle_endtag(self, tag: str) -> None:
            if tag == "script":
                self.in_script = False

        def handle_data(self, data: str) -> None:
            if self.in_script:
                self.script_data.append(data)

    source = tmp_path / "review-source.pdf"
    output = tmp_path / "private-review"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    # A supplied manifest can retain the genuine PDF hash while changing its name.
    manifest["source"]["name"] = source_name
    run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())
    review = write_fidelity_text_review_index(source, output, manifest, workspace_root=Path.cwd())
    parser = ReviewParser()
    parser.feed(review.read_text(encoding="utf-8"))

    assert parser.tags.count("script") == 1
    assert "img" not in parser.tags[parser.tags.index("script") + 1:]
    script = "".join(parser.script_data)
    source_json = script.removeprefix("const source=").split(";const nativeByPage=", 1)[0]
    assert json.loads(source_json) == manifest["source"]


def test_native_pdf_text_selection_creates_typed_per_span_approval(tmp_path: Path) -> None:
    source = tmp_path / "native-selected.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "REPEATED NOTE", fontsize=18)
    page.insert_text((40, 150), "REPEATED NOTE", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    native_spans = observation["native_pdf_spans"]
    assert [item["content"] for item in native_spans] == ["REPEATED NOTE", "REPEATED NOTE"]

    selection_path = output / "native-text-selection.json"
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [],
            "native_span_ids": [item["id"] for item in native_spans],
            "native_span_reviews": [
                {"span": item, "visible_and_legible": True}
                for item in native_spans
            ],
        }],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    approvals = write_fidelity_text_approvals_from_selection(
        source, output, manifest, selection_path, "approved-visible-native-spans", workspace_root=Path.cwd(),
    )
    approval_path = output / "fidelity_text_approvals" / "page_01.json"
    assert approvals[0]["state"] == "approved-text-items-only"
    assert approvals[0]["approved_candidates"] == []
    assert [item["span"]["id"] for item in approvals[0]["approved_native_spans"]] == [
        item["id"] for item in native_spans
    ]
    assert all(item["visibility_review"]["selection"]["sha256"] for item in approvals[0]["approved_native_spans"])

    assert approval_path.is_file()


def test_native_pdf_text_reconstruction_emits_only_approved_source_spans(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "native-reconstruction.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "REPEATED NOTE", fontsize=18)
    page.insert_text((40, 150), "REPEATED NOTE", fontsize=18)
    page.insert_text((40, 220), "UNSELECTED", fontsize=18)
    page.insert_text((230, 100), "ROTATED", fontsize=14, rotate=90)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    native_spans = json.loads(observation_path.read_text(encoding="utf-8"))["native_pdf_spans"]
    selected = [item for item in native_spans if item["content"] != "UNSELECTED"]
    selection_path = output / "native-text-selection.json"
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [],
            "native_span_ids": [item["id"] for item in selected],
            "native_span_reviews": [
                {"span": item, "visible_and_legible": True}
                for item in selected
            ],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    write_fidelity_text_approvals_from_selection(
        source, output, manifest, selection_path, "approved-visible-native-spans", workspace_root=Path.cwd(),
    )
    from cad_agent import fidelity as fidelity_module

    def unexpected_ocr_rerun(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        raise AssertionError("native-only reconstruction must not rerun OCR")

    monkeypatch.setattr(fidelity_module, "_fresh_fidelity_ocr_candidates", unexpected_ocr_rerun)

    output_dxf = run_fidelity_text_reconstruct(
        source, output, manifest, output / "fidelity_text_approvals" / "page_01.json",
        workspace_root=Path.cwd(),
    )
    emitted = list(ezdxf.readfile(output_dxf).modelspace().query("TEXT"))
    assert len(emitted) == 3
    assert sorted(item.dxf.text for item in emitted) == ["REPEATED NOTE", "REPEATED NOTE", "ROTATED"]
    assert len({(round(item.dxf.insert.x, 4), round(item.dxf.insert.y, 4)) for item in emitted}) == 3
    page_record = manifest["pages"][0]
    audit = json.loads((output / page_record["artifacts"]["layout_audit"]["artifact"]).read_text(encoding="utf-8"))
    height_px = audit["source_page"]["render_height_px"]
    width_px = audit["source_page"]["render_width_px"]
    scale = page_record["pixel_to_paper_mm"]["used"]
    render_height = height_px
    for entity, span in zip(emitted, selected):
        origin_x, origin_y = span["source_origin_pt"]
        expected_insert = (
            origin_x * width_px / 400 * scale,
            (height_px - origin_y * height_px / 300) * scale,
        )
        assert (entity.dxf.insert.x, entity.dxf.insert.y) == pytest.approx(expected_insert, abs=1e-5)
        assert entity.dxf.height == pytest.approx(span["source_font_size_pt"] * render_height / 300 * scale, abs=1e-5)
        assert entity.dxf.width == pytest.approx(1.0)
        assert entity.dxf.rotation == pytest.approx(-span["rotation_deg"], abs=1e-5)
    report = json.loads((output_dxf.parent / "report.json").read_text(encoding="utf-8"))
    assert report["emitted_text_entities"] == 3
    assert all(record["source_font_name"] for record in report["text_sizing"])


def test_native_pdf_text_approval_rejects_junctioned_output_directory(tmp_path: Path) -> None:
    import subprocess

    if os.name != "nt":
        pytest.skip("Directory junction protection is Windows-specific.")

    source = tmp_path / "approval-junction.pdf"
    output = tmp_path / "private-approval-junction"
    external = tmp_path / "outside-private-root"
    external.mkdir()
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "APPROVED NOTE", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    candidate = observation["candidates"][0]
    approval_directory = output / "fidelity_text_approvals"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(approval_directory), str(external)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"Directory junction creation unavailable: {result.stderr.strip() or result.stdout.strip()}")
    try:
        with pytest.raises(FidelityError, match="directory|private|identity"):
            write_fidelity_text_approval(
                source, output, manifest, 1, observation_path, [candidate["id"]], "junction-test",
                workspace_root=Path.cwd(),
            )
        assert not (external / "page_01.json").exists()
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(approval_directory)], capture_output=True, check=False)


def test_native_pdf_text_reconstruction_refuses_retry_when_page_mapping_changes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mapping-retry.pdf"
    output = tmp_path / "private-mapping-retry"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "MAPPED NOTE", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    candidate = json.loads(observation_path.read_text(encoding="utf-8"))["candidates"][0]
    approval_path = output / "fidelity_text_approvals" / "page_01.json"
    write_fidelity_text_approval(
        source, output, manifest, 1, observation_path, [candidate["id"]], "mapping-test",
        workspace_root=Path.cwd(),
    )
    published = run_fidelity_text_reconstruct(
        source, output, manifest, approval_path, workspace_root=Path.cwd(),
    )
    assert published.is_file()

    manifest["pages"][0]["pixel_to_paper_mm"]["used"] *= 2
    with pytest.raises(FidelityError, match="already exists"):
        run_fidelity_text_reconstruct(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )


def test_native_pdf_text_reconstruction_reuses_retry_with_base_text(tmp_path: Path) -> None:
    source = tmp_path / "base-text-retry.pdf"
    output = tmp_path / "private-base-text-retry"
    document = fitz.open()
    document.new_page(width=400, height=300).insert_text((40, 80), "RETRY NOTE", fontsize=18)
    document.save(source)
    document.close()

    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    native_spans = json.loads(observation_path.read_text(encoding="utf-8"))["native_pdf_spans"]
    selection_path = output / "native-text-selection.json"
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [],
            "native_span_ids": [item["id"] for item in native_spans],
            "native_span_reviews": [
                {"span": item, "visible_and_legible": True} for item in native_spans
            ],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    write_fidelity_text_approvals_from_selection(
        source, output, manifest, selection_path, "approved-visible-native-spans", workspace_root=Path.cwd(),
    )
    approval_path = output / "fidelity_text_approvals" / "page_01.json"
    base_dxf = output / "base.dxf"
    base_document = ezdxf.new("R2010")
    base_document.modelspace().add_text("BASE NOTE", dxfattribs={"height": 2.5})
    base_document.saveas(base_dxf)

    first = run_fidelity_text_reconstruct(
        source, output, manifest, approval_path, base_dxf=base_dxf, workspace_root=Path.cwd(),
    )
    retry = run_fidelity_text_reconstruct(
        source, output, manifest, approval_path, base_dxf=base_dxf, workspace_root=Path.cwd(),
    )

    assert retry == first
    entities = list(ezdxf.readfile(retry).modelspace().query("TEXT"))
    assert sorted(entity.dxf.text for entity in entities) == ["BASE NOTE", "RETRY NOTE"]


@pytest.mark.parametrize("dxf_format", ["asc", "bin"])
@pytest.mark.parametrize("version", ["R2000", "R2010"])
def test_text_base_snapshot_preserves_existing_dxf_encoding_and_bytes(
    tmp_path: Path, dxf_format: str, version: str,
) -> None:
    import hashlib

    base = tmp_path / "encoded-base.dxf"
    drawing = ezdxf.new(version)
    drawing.encoding = "cp1252"
    drawing.modelspace().add_text("BASE Ø ± café", dxfattribs={"height": 2.5})
    drawing.saveas(base, fmt=dxf_format)
    expected = base.read_bytes()

    snapshot, digest = fidelity_module._read_text_base_snapshot(base)

    assert digest == hashlib.sha256(expected).hexdigest()
    assert [e.dxf.text for e in snapshot.modelspace().query("TEXT")] == ["BASE Ø ± café"]
    assert snapshot.dxfversion == drawing.dxfversion
    assert base.read_bytes() == expected


@pytest.mark.parametrize("dxf_format", ["asc", "bin"])
def test_native_pdf_text_reconstruction_binds_base_read_and_retry_to_same_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dxf_format: str,
) -> None:
    import hashlib

    source = tmp_path / "snapshot-retry.pdf"
    output = tmp_path / "private-snapshot-retry"
    document = fitz.open()
    document.new_page(width=400, height=300).insert_text((40, 80), "RETRY NOTE", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    spans = json.loads(observation.read_text(encoding="utf-8"))["native_pdf_spans"]
    selection = output / "selection.json"
    selection.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0", "source": manifest["source"],
        "selections": [{"page": 1, "candidate_ids": [], "native_span_ids": [s["id"] for s in spans],
                        "native_span_reviews": [{"span": s, "visible_and_legible": True} for s in spans]}],
    }), encoding="utf-8")
    write_fidelity_text_approvals_from_selection(
        source, output, manifest, selection, "approved-visible-native-spans", workspace_root=Path.cwd(),
    )
    approval = output / "fidelity_text_approvals/page_01.json"
    base = output / "base.dxf"
    replacement = output / "replacement.dxf"
    for path, content in [(base, "BASE A"), (replacement, "BASE B")]:
        drawing = ezdxf.new("R2010")
        drawing.modelspace().add_text(content, dxfattribs={"height": 2.5})
        drawing.saveas(path, fmt=dxf_format)
    original_sha = hashlib.sha256(base.read_bytes()).hexdigest()
    replacement_bytes = replacement.read_bytes()
    original_read = ezdxf.readfile
    original_load = ezdxf.document.Drawing.load
    swapped = False

    def read_then_replace(cls, *args, **kwargs):
        nonlocal swapped
        drawing = original_load(*args, **kwargs)
        if not swapped and [e.dxf.text for e in drawing.modelspace().query("TEXT")] == ["BASE A"]:
            base.write_bytes(replacement_bytes)
            swapped = True
        return drawing

    monkeypatch.setattr(ezdxf.document.Drawing, "load", classmethod(read_then_replace))
    first = run_fidelity_text_reconstruct(
        source, output, manifest, approval, base_dxf=base, workspace_root=Path.cwd(),
    )
    assert swapped
    assert sorted(e.dxf.text for e in original_read(first).modelspace().query("TEXT")) == ["BASE A", "RETRY NOTE"]
    report = json.loads(first.with_name("report.json").read_text(encoding="utf-8"))
    refused = False
    try:
        run_fidelity_text_reconstruct(
            source, output, manifest, approval, base_dxf=base, workspace_root=Path.cwd(),
        )
    except FidelityError as error:
        assert "already exists" in str(error)
        refused = True
    assert report["base_dxf_sha256"] == original_sha and refused, (
        "BASE A output must bind BASE A bytes, and must not be reused as BASE B merely because TEXT counts match"
    )


def test_native_pdf_text_reconstruction_failure_after_dxf_write_is_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "atomic-reconstruction.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "ATOMIC NOTE", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    native_spans = json.loads(observation_path.read_text(encoding="utf-8"))["native_pdf_spans"]
    selection_path = output / "native-text-selection.json"
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [],
            "native_span_ids": [item["id"] for item in native_spans],
            "native_span_reviews": [
                {"span": item, "visible_and_legible": True} for item in native_spans
            ],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    write_fidelity_text_approvals_from_selection(
        source, output, manifest, selection_path, "approved-visible-native-spans", workspace_root=Path.cwd(),
    )

    approval_path = output / "fidelity_text_approvals" / "page_01.json"
    page_output = output / "text_reconstruction" / "page_01"
    original_write_text = Path.write_text

    def fail_report_write(path: Path, data: str, *args: Any, **kwargs: Any) -> int:
        if path.name == "report.json" and path.parent.name.startswith(".page_01.staging-"):
            raise OSError("injected report publication failure")
        return original_write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_report_write)
    with pytest.raises(FidelityError, match="report could not be published"):
        run_fidelity_text_reconstruct(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )

    assert not page_output.exists(), "failed publication must not leave a partial final page"
    staging_parent = page_output.parent
    assert not list(staging_parent.glob(".page_01.staging-*")), "failed publication must clean its staging directory"

    monkeypatch.setattr(Path, "write_text", original_write_text)
    output_dxf = run_fidelity_text_reconstruct(
        source, output, manifest, approval_path, workspace_root=Path.cwd(),
    )
    assert output_dxf == page_output / "layout.dxf"
    assert output_dxf.is_file()
    assert (page_output / "report.json").is_file()
    assert len(list(ezdxf.readfile(output_dxf).modelspace().query("TEXT"))) == len(native_spans)


@pytest.mark.parametrize("failure_site", ["publish-finalization", "staging-cleanup"])
def test_native_pdf_text_reconstruction_postcommit_failure_is_recoverable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    failure_site: str,
) -> None:
    source = tmp_path / "postcommit-reconstruction.pdf"
    output = tmp_path / "private-postcommit-staging"
    document = fitz.open()
    document.new_page(width=400, height=300).insert_text((40, 80), "POSTCOMMIT NOTE", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    native_spans = json.loads(observation_path.read_text(encoding="utf-8"))["native_pdf_spans"]
    selection_path = output / "native-text-selection.json"
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [],
            "native_span_ids": [item["id"] for item in native_spans],
            "native_span_reviews": [
                {"span": item, "visible_and_legible": True} for item in native_spans
            ],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    write_fidelity_text_approvals_from_selection(
        source, output, manifest, selection_path, "approved-visible-native-spans", workspace_root=Path.cwd(),
    )

    approval_path = output / "fidelity_text_approvals" / "page_01.json"
    page_output = output / "text_reconstruction" / "page_01"

    def publish_by_rename(staging: Path, destination: Path, identity: tuple[int, int]) -> None:
        assert staging.parent == destination.parent
        os.rename(staging, destination)
        if failure_site == "publish-finalization":
            raise fidelity_module.FileIdentityError("injected postcommit publication finalization failure")

    def fail_cleanup(staging: Path) -> None:
        raise fidelity_module.FileIdentityError("injected postcommit cleanup failure")

    monkeypatch.setattr(fidelity_module, "_publish_staging_directory", publish_by_rename)
    monkeypatch.setattr(
        fidelity_module,
        "_remove_staging_reparse_alias",
        fail_cleanup if failure_site == "staging-cleanup" else lambda staging: None,
    )
    with pytest.raises(FidelityError, match=r"published and verified"):
        run_fidelity_text_reconstruct(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )

    output_dxf = page_output / "layout.dxf"
    report_path = page_output / "report.json"
    assert output_dxf.is_file(), "the injected failure happens after atomic publication"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["output_dxf_sha256"] == fidelity_module.sha256_file(output_dxf)
    assert report["staging_directory_identity"] == list(
        (page_output.stat().st_dev, page_output.stat().st_ino)
    )

    monkeypatch.setattr(fidelity_module, "_remove_staging_reparse_alias", lambda staging: None)
    assert run_fidelity_text_reconstruct(
        source, output, manifest, approval_path, workspace_root=Path.cwd(),
    ) == output_dxf
    assert len(list(ezdxf.readfile(output_dxf).modelspace().query("TEXT"))) == len(native_spans)

    report["source_sha256"] = "0" * 64
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(FidelityError, match="already exists"):
        run_fidelity_text_reconstruct(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse-point retry regression")
def test_native_pdf_text_reconstruction_rejects_junctioned_existing_output_parent(
    tmp_path: Path,
) -> None:
    source = tmp_path / "junction-retry.pdf"
    output = tmp_path / "private-junction-retry"
    document = fitz.open()
    document.new_page(width=400, height=300).insert_text((40, 80), "JUNCTION RETRY", fontsize=18)
    document.save(source)
    document.close()

    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    native_spans = json.loads(observation_path.read_text(encoding="utf-8"))["native_pdf_spans"]
    selection_path = output / "native-text-selection.json"
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [],
            "native_span_ids": [item["id"] for item in native_spans],
            "native_span_reviews": [
                {"span": item, "visible_and_legible": True} for item in native_spans
            ],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    write_fidelity_text_approvals_from_selection(
        source, output, manifest, selection_path, "approved-junction-retry",
        workspace_root=Path.cwd(),
    )

    approval_path = output / "fidelity_text_approvals" / "page_01.json"
    page_output = output / "text_reconstruction" / "page_01"
    output_dxf = run_fidelity_text_reconstruct(
        source, output, manifest, approval_path, workspace_root=Path.cwd(),
    )
    expected_hash = fidelity_module.sha256_file(output_dxf)

    external_root = tmp_path / "outside-private-root"
    external_root.mkdir()
    relocated_parent = external_root / "text_reconstruction"
    page_output.parent.rename(relocated_parent)
    junction_result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(page_output.parent), str(relocated_parent)],
        capture_output=True,
        text=True,
        check=False,
    )
    if junction_result.returncode != 0:
        pytest.skip(
            f"Directory junction creation unavailable: "
            f"{junction_result.stderr.strip() or junction_result.stdout.strip()}"
        )

    with pytest.raises(FidelityError, match="private|directory|output"):
        run_fidelity_text_reconstruct(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )
    relocated_dxf = external_root / "text_reconstruction" / "page_01" / "layout.dxf"
    assert fidelity_module.sha256_file(relocated_dxf) == expected_hash


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse-point race regression")
def test_native_pdf_text_reconstruction_pins_staging_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cad_agent import fidelity as fidelity_module

    source = tmp_path / "staging-reparse-race.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "STAGING RACE", fontsize=18)
    document.save(source)
    document.close()

    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    native_spans = json.loads(observation_path.read_text(encoding="utf-8"))["native_pdf_spans"]
    selection_path = output / "native-text-selection.json"
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [],
            "native_span_ids": [item["id"] for item in native_spans],
            "native_span_reviews": [
                {"span": item, "visible_and_legible": True} for item in native_spans
            ],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    write_fidelity_text_approvals_from_selection(
        source, output, manifest, selection_path, "approved-visible-native-spans", workspace_root=Path.cwd(),
    )

    outside = tmp_path / "outside-root"
    outside.mkdir()
    original_saveas = ezdxf.document.Drawing.saveas
    original_rename = fidelity_module.os.rename
    original_handle_rename = fidelity_module._set_file_information_by_handle
    staging_replacement_blocked: list[bool] = []
    publication_race_triggered: list[bool] = []
    staging_for_publication: list[Path] = []
    displaced_staging: list[Path] = []

    def replace_staging_with_junction(
        drawing: ezdxf.document.Drawing, filename: str | Path, *args: object, **kwargs: object,
    ) -> None:
        target = Path(filename)
        staging = target.parent
        if target.name == "layout.dxf" and staging.name.startswith(".page_01.staging-"):
            staging_for_publication.append(staging)
            try:
                staging.rmdir()
            except OSError:
                staging_replacement_blocked.append(True)
            else:
                result = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(staging), str(outside)],
                    capture_output=True, text=True, check=False,
                )
                if result.returncode != 0:
                    staging.mkdir()
                    pytest.skip(f"mklink /J unavailable: {result.stderr.strip()}")
        original_saveas(drawing, filename, *args, **kwargs)

    monkeypatch.setattr(ezdxf.document.Drawing, "saveas", replace_staging_with_junction)
    page_output = output / "text_reconstruction" / "page_01"

    def replace_staging_during_handle_publication(handle: object, destination: Path) -> None:
        assert destination == page_output
        assert staging_for_publication
        staging = staging_for_publication[-1]
        displaced = staging.with_name(f"{staging.name}.displaced")
        original_rename(staging, displaced)
        displaced_staging.append(displaced)
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(staging), str(outside)],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            original_rename(displaced, staging)
            displaced_staging.clear()
            pytest.skip(f"mklink /J unavailable: {result.stderr.strip()}")
        publication_race_triggered.append(True)
        original_handle_rename(handle, destination)

    monkeypatch.setattr(
        fidelity_module, "_set_file_information_by_handle", replace_staging_during_handle_publication,
    )
    try:
        output_dxf = run_fidelity_text_reconstruct(
            source, output, manifest, output / "fidelity_text_approvals" / "page_01.json",
            workspace_root=Path.cwd(),
        )
        assert publication_race_triggered, "test must replace the staging path after the object handle is bound"
        assert output_dxf.is_file()
        assert not (outside / "layout.dxf").exists(), "DXF must not be written through a staging junction"
        assert not (outside / "report.json").exists(), "report must not be written through a staging junction"
        assert staging_replacement_blocked, "staging directory must not be replaceable during output writes"
    finally:
        if page_output.exists() and getattr(page_output.lstat(), "st_file_attributes", 0) & 0x400:
            page_output.rmdir()
        for displaced in displaced_staging:
            if displaced.exists():
                import shutil

                shutil.rmtree(displaced)


def test_native_pdf_text_reconstruct_rejects_forged_mixed_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "mixed-overlap-reconstruction.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((50, 100), "12,00", fontsize=18)
    document.save(source)
    document.close()

    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    native = next(span for span in observation["native_pdf_spans"] if span["content"] == "12,00")
    ocr = next(candidate for candidate in observation["candidates"] if candidate["content"] == "12,00")
    assert (
        max(native["bbox_px"][0], ocr["bbox_px"][0])
        < min(native["bbox_px"][2], ocr["bbox_px"][2])
        and max(native["bbox_px"][1], ocr["bbox_px"][1])
        < min(native["bbox_px"][3], ocr["bbox_px"][3])
    )

    from cad_agent import fidelity as fidelity_module

    monkeypatch.setenv("CAD_AGENT_FIDELITY_TEXT_FONT", r"C:\Windows\Fonts\seguisym.ttf")
    native_review = {"span": native, "visible_and_legible": True}
    selection_path = output / "diagnostic-native-selection.json"
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [],
            "native_span_ids": [native["id"]],
            "native_span_reviews": [native_review],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    native_approval = write_fidelity_text_approval(
        source, output, manifest, 1, observation_path, [], "test-native-only",
        workspace_root=Path.cwd(), native_span_ids=[native["id"]],
        native_span_reviews=[native_review], selection_path=selection_path,
    )
    (output / "fidelity_text_approvals" / "page_01.json").unlink()

    ocr_approval = write_fidelity_text_approval(
        source, output, manifest, 1, observation_path, [ocr["id"]], "test-ocr-only",
        workspace_root=Path.cwd(),
    )
    selection = {
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [ocr["id"]],
            "native_span_ids": [native["id"]],
            "native_span_reviews": [native_review],
        }],
    }
    selection_path.write_text(json.dumps(selection, ensure_ascii=False), encoding="utf-8")
    selection_record = fidelity_module._artifact(selection_path, output)
    native_approval["native_selection"] = selection_record
    for record in native_approval["approved_native_spans"]:
        record["visibility_review"]["selection"] = selection_record
    approval_path = output / "diagnostic-forged-mixed-approval.json"
    approval_path.write_text(json.dumps(native_approval, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(FidelityError, match="selection.*OCR|approved OCR"):
        run_fidelity_text_reconstruct(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )

    native_approval["approved_candidates"] = ocr_approval["approved_candidates"]
    approval_path.write_text(json.dumps(native_approval, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(FidelityError, match="overlap"):
        run_fidelity_text_reconstruct(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )
    assert not (output / "text_reconstruction" / "page_01" / "layout.dxf").exists()


def test_native_pdf_text_reconstruction_rejects_junction_output_redirect(tmp_path: Path) -> None:
    import subprocess

    import os

    if os.name != "nt":
        pytest.skip("Directory junction protection is Windows-specific.")

    source = tmp_path / "native-reconstruction.pdf"
    output = tmp_path / "private-staging"
    external = tmp_path / "outside-private-root"
    external.mkdir()
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "APPROVED NOTE", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    native_spans = json.loads(observation_path.read_text(encoding="utf-8"))["native_pdf_spans"]
    selection_path = output / "native-text-selection.json"
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [],
            "native_span_ids": [item["id"] for item in native_spans],
            "native_span_reviews": [
                {"span": item, "visible_and_legible": True} for item in native_spans
            ],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    write_fidelity_text_approvals_from_selection(
        source, output, manifest, selection_path, "approved-visible-native-spans", workspace_root=Path.cwd(),
    )

    redirected_root = output / "text_reconstruction"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(redirected_root), str(external)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"Directory junction creation unavailable: {result.stderr.strip() or result.stdout.strip()}")

    with pytest.raises(FidelityError, match="private|directory|output"):
        run_fidelity_text_reconstruct(
            source, output, manifest, output / "fidelity_text_approvals" / "page_01.json",
            workspace_root=Path.cwd(),
        )
    assert not (external / "page_01").exists()


@pytest.mark.parametrize("tamper", ["changed_source", "stale_render", "unselected_span", "failed_glyph", "unsupported_transform"])
def test_native_pdf_text_reconstruction_fails_closed_before_output(tmp_path: Path, tamper: str) -> None:
    source = tmp_path / "native-reconstruction.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "SELECTED", fontsize=18)
    page.insert_text((40, 150), "NOT SELECTED", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    native_spans = json.loads(observation_path.read_text(encoding="utf-8"))["native_pdf_spans"]
    selection_path = output / "native-text-selection.json"
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [],
            "native_span_ids": [native_spans[0]["id"]],
            "native_span_reviews": [{"span": native_spans[0], "visible_and_legible": True}],
        }],
    }), encoding="utf-8")
    write_fidelity_text_approvals_from_selection(
        source, output, manifest, selection_path, "approved-visible-native-spans", workspace_root=Path.cwd(),
    )
    approval_path = output / "fidelity_text_approvals" / "page_01.json"
    if tamper == "changed_source":
        source.write_bytes(source.read_bytes() + b"changed")
    elif tamper == "stale_render":
        rendered_path = output / manifest["pages"][0]["artifacts"]["rendered_png"]["artifact"]
        Path(output, rendered_path).write_bytes(b"stale-render")
    elif tamper == "unselected_span":
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        extra_span = native_spans[1]
        approval["approved_native_spans"].append({
            "span": extra_span,
            "glyph_render": approval["approved_native_spans"][0]["glyph_render"],
            "visibility_review": dict(approval["approved_native_spans"][0]["visibility_review"], span_id=extra_span["id"]),
        })
        approval_path.write_text(json.dumps(approval), encoding="utf-8")
    elif tamper == "failed_glyph":
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        approval["approved_native_spans"][0]["glyph_render"]["passed"] = False
        approval_path.write_text(json.dumps(approval), encoding="utf-8")
    elif tamper == "unsupported_transform":
        manifest["configuration"]["transform"] = "unknown-transform"

    from cad_agent.manifest import ManifestError

    with pytest.raises((FidelityError, ManifestError)):
        run_fidelity_text_reconstruct(source, output, manifest, approval_path, workspace_root=Path.cwd())
    assert not (output / "text_reconstruction" / "page_01").exists()


@pytest.mark.parametrize("tamper", ["duplicate_id", "stale_render", "visibility_not_confirmed"])
def test_native_pdf_text_approval_rejects_unbound_or_unreviewed_selection(tmp_path: Path, tamper: str) -> None:
    source = tmp_path / "native-review.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "VISIBLE NATIVE", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    native_span = json.loads(observation_path.read_text(encoding="utf-8"))["native_pdf_spans"][0]
    review_span = dict(native_span)
    if tamper == "stale_render":
        review_span["render_sha256"] = "0" * 64
    review = {"span": review_span, "visible_and_legible": tamper != "visibility_not_confirmed"}
    native_span_ids = [native_span["id"]]
    reviews = [review]
    if tamper == "duplicate_id":
        native_span_ids.append(native_span["id"])
        reviews.append(review)
    selection_path = output / "native-text-selection.json"
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [],
            "native_span_ids": native_span_ids,
            "native_span_reviews": reviews,
        }],
    }, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(FidelityError):
        write_fidelity_text_approvals_from_selection(
            source, output, manifest, selection_path, "approval-attempt", workspace_root=Path.cwd(),
        )
    assert not (output / "fidelity_text_approvals" / "page_01.json").exists()


def test_text_reconstruction_rejects_changed_hash_bound_observation(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    assert observation["candidates"]
    write_fidelity_text_approval(
        source, output, manifest, 1, observation_path,
        [observation["candidates"][0]["id"]], "approved-test", workspace_root=Path.cwd(),
    )

    observation["candidates"][0]["content"] = "CHANGED AFTER APPROVAL"
    observation_path.write_text(json.dumps(observation), encoding="utf-8")

    with pytest.raises(FidelityError, match="hash"):
        run_fidelity_text_reconstruct(
            source, output, manifest, output / "fidelity_text_approvals" / "page_01.json",
            workspace_root=Path.cwd(),
        )
    assert not (output / "text_reconstruction" / "page_01").exists()


def test_text_reconstruction_rejects_rewritten_observation_and_matching_crafted_approval(
    tmp_path: Path,
) -> None:
    """A native PDF span must not become OCR merely by rewriting both sidecars."""
    from cad_agent import fidelity as fidelity_module

    source = tmp_path / "invisible-native-text.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "NATIVE ONLY", fontsize=18, render_mode=3)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    assert observation["candidates"] == []
    assert observation["native_pdf_spans"] == []
    forged_candidate = {
        "id": "forged-ocr-native-span",
        "content": "NATIVE ONLY",
        "bbox_px": [80, 121, 300, 170],
        "rotation_deg": 0.0,
        "confidence": 1.0,
        "source": "text_tesseract",
        "semantic_role": "unknown",
        "parsed_value": None,
    }
    observation["state"] = "needs_human_approval"
    observation["candidates"] = [forged_candidate]
    observation_path.write_text(json.dumps(observation, ensure_ascii=False), encoding="utf-8")

    approval_path = output / "fidelity_text_approvals" / "page_01.json"
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(json.dumps({
        "schema_version": "fidelity-text-approval-1.0",
        "private_artifact": True,
        "state": "approved-text-candidates-only",
        "source": manifest["source"],
        "page": 1,
        "observation": fidelity_module._artifact(observation_path, output),
        "approval_reference": "approved-test",
        "approved_candidates": [{
            "candidate": forged_candidate,
            "glyph_render": fidelity_module._unicode_glyph_render_check(forged_candidate["content"]),
        }],
    }, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(FidelityError, match="fresh OCR"):
        run_fidelity_text_reconstruct(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )
    assert not (output / "text_reconstruction" / "page_01").exists()


def test_text_reconstruction_rejects_alternate_native_observation(tmp_path: Path) -> None:
    from cad_agent import fidelity as fidelity_module

    source = tmp_path / "native.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "NATIVE 123", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    native = observation["native_pdf_spans"][0]

    alternate_path = output / "fidelity_text_observations" / "alternate-page_01.json"
    alternate = {**observation, "candidates": [native]}
    alternate_path.write_text(json.dumps(alternate, ensure_ascii=False), encoding="utf-8")
    approval_path = output / "fidelity_text_approvals" / "page_01.json"
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(json.dumps({
        "schema_version": "fidelity-text-approval-1.0",
        "private_artifact": True,
        "state": "approved-text-candidates-only",
        "source": manifest["source"],
        "page": 1,
        "observation": fidelity_module._artifact(alternate_path, output),
        "approval_reference": "approved-test",
        "approved_candidates": [{
            "candidate": native,
            "glyph_render": fidelity_module._unicode_glyph_render_check(native["content"]),
        }],
    }, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(FidelityError, match="canonical OCR observation"):
        run_fidelity_text_reconstruct(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )
    assert not (output / "text_reconstruction" / "page_01").exists()


def test_text_reconstruction_revalidates_glyph_render_evidence(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    assert observation["candidates"]
    write_fidelity_text_approval(
        source, output, manifest, 1, observation_path,
        [observation["candidates"][0]["id"]], "approved-test", workspace_root=Path.cwd(),
    )
    approval_path = output / "fidelity_text_approvals" / "page_01.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["approved_candidates"][0]["glyph_render"] = {"passed": True}
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    with pytest.raises(FidelityError, match="glyph-render evidence"):
        run_fidelity_text_reconstruct(
            source, output, manifest, approval_path, workspace_root=Path.cwd(),
        )
    assert not (output / "text_reconstruction" / "page_01").exists()


@pytest.mark.parametrize("unsupported", ["rotation", "crop"])
def test_native_pdf_text_observation_fails_closed_for_unsupported_page_frames(
    tmp_path: Path, unsupported: str,
) -> None:
    source = tmp_path / "native.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "NATIVE 123", fontsize=18)
    if unsupported == "rotation":
        page.set_rotation(90)
    else:
        page.set_cropbox(fitz.Rect(10, 10, 390, 290))
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)

    with pytest.raises(FidelityError, match="[Nn]ative PDF text mapping"):
        run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())


@pytest.mark.parametrize("stale_artifact", ["source", "render"])
def test_native_pdf_text_observation_rejects_stale_source_or_render_hash(
    tmp_path: Path, stale_artifact: str,
) -> None:
    source = tmp_path / "native.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "NATIVE 123", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)

    if stale_artifact == "source":
        source.write_bytes(source.read_bytes() + b"stale")
    else:
        rendered = output / manifest["pages"][0]["artifacts"]["rendered_png"]["artifact"]
        rendered.write_bytes(rendered.read_bytes() + b"stale")
    expected_error = FidelityError
    if stale_artifact == "source":
        from cad_agent.manifest import ManifestError

        expected_error = ManifestError
    with pytest.raises(expected_error):
        run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())


@pytest.mark.parametrize("tamper", ["page_bool", "page_float", "page_wrong", "render_hash", "width_positive_wrong", "height_positive_wrong"])
def test_native_pdf_text_observation_rejects_mismatched_audit_frame_metadata(
    tmp_path: Path, tamper: str,
) -> None:
    source = tmp_path / "native.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "NATIVE 123", fontsize=18)
    document.save(source)
    document.close()
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)

    record = manifest["pages"][0]["artifacts"]["layout_audit"]
    audit_path = output / record["artifact"]
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    source_page = audit["source_page"]
    if tamper == "page_bool":
        source_page["page"] = True
    elif tamper == "page_float":
        source_page["page"] = 1.0
    elif tamper == "page_wrong":
        source_page["page"] = 2
    elif tamper == "render_hash":
        source_page["render_sha256"] = "0" * 64
    elif tamper == "width_positive_wrong":
        source_page["render_width_px"] += 1
    else:
        source_page["render_height_px"] += 1
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    record["sha256"] = __import__("hashlib").sha256(audit_path.read_bytes()).hexdigest()

    with pytest.raises(FidelityError, match="[Nn]ative PDF text mapping"):
        run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())


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


def _style_transfer_page(tmp_path: Path):
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "private-staging"
    _pdf(source)
    manifest_path = output / "fidelity-run-manifest.json"
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, manifest_path, manifest)
    regions = [
        {"id": "first", "bbox_px": [20, 20, 250, 150], "purpose": "layout-reconstruction"},
        {"id": "second", "bbox_px": [270, 20, 500, 150], "purpose": "layout-reconstruction"},
    ]
    write_region_proposal(
        source, output, manifest_path, manifest, 1,
        {"regions": regions, "excluded_regions": [
            {"id": "outside", "bbox_px": [300, 200, 390, 290], "purpose": "exclude"},
        ]},
        workspace_root=Path.cwd(),
    )
    write_region_approval(
        source, output, manifest, 1, 1, ["first", "second"], "approved-style-test",
        workspace_root=Path.cwd(),
    )
    approval = output / "region_approvals" / "page_01.json"
    run_fidelity_reconstruct(source, output, manifest, approval, workspace_root=Path.cwd())
    return source, output, manifest, approval


def _style_transfer_candidate(output: Path, region: str) -> Path:
    return output / "reconstruction_candidates" / "page_01" / region / "geometry.dxf"


def _style_transfer_add_text(
    document, style, text, position, *, extended=False, family=".VnAvant", filenames=None,
):
    if style and style not in document.styles:
        attributes = {
            "bigfont": "TEST_BIG.shx",
            "height": 2.0,
            "width": 0.75,
            "oblique": 12.0,
            "generation_flags": 2,
        } if extended else {}
        record = document.styles.add(style, font="" if extended else "Arial.ttf", dxfattribs=attributes)
        if extended:
            record.set_xdata("ACAD", [(1000, family), (1071, 1048610)])
            record.update_dxf_attribs(filenames or {})
    entity = document.modelspace().add_text(text, dxfattribs={"style": style, "height": 2.0})
    entity.dxf.insert = position


def _style_transfer_owner(output, manifest, approval, style, *, extended, family=".VnAvant", filenames=None):
    audit = json.loads(approval.read_text(encoding="utf-8"))
    scale = float(manifest["pages"][0]["pixel_to_paper_mm"]["used"])
    x = 270 * scale + 5
    y = (audit["page"]["render_height_px"] - 150) * scale + 5
    document = ezdxf.new("R2010")
    _style_transfer_add_text(
        document, style, "LEGACY-TEST", (x, y), extended=extended, family=family, filenames=filenames,
    )
    first_x = 20 * scale + 5
    _style_transfer_add_text(document, "FirstRegionStyle", "FIRST REGION", (first_x, y))
    _style_transfer_add_text(document, "VN_UNICODE", "Mép boong chính", (x + 5, y))
    owner = output / "text_reconstruction" / "page_01" / "layout.dxf"
    owner.parent.mkdir(parents=True)
    document.saveas(owner)
    text_approval = output / "fidelity_text_approvals" / "page_01.json"
    text_approval.parent.mkdir()
    text_approval.write_text(json.dumps({
        "schema_version": "fidelity-text-approval-1.0",
        "private_artifact": True,
        "state": "approved-text-candidates-only",
        "source": manifest["source"],
        "page": 1,
    }), encoding="utf-8")
    (owner.parent / "report.json").write_text(json.dumps({
        "state": "needs_review",
        "text_approval_sha256": fidelity_module.sha256_file(text_approval),
        "output_dxf_sha256": fidelity_module.sha256_file(owner),
    }), encoding="utf-8")
    return owner


@pytest.mark.parametrize("route", ["handoff", "compose"])
def test_fidelity_text_style_preserves_extended_font_after_reopen(tmp_path: Path, route: str) -> None:
    source, output, manifest, approval = _style_transfer_page(tmp_path)
    candidate = _style_transfer_candidate(output, "second")
    if route == "handoff":
        owner = _style_transfer_owner(output, manifest, approval, "LegacyTest", extended=True)
        source_hash = fidelity_module.sha256_file(owner)
        run_fidelity_semantic_region_handoff(source, output, manifest, approval, workspace_root=Path.cwd())
        assert fidelity_module.sha256_file(owner) == source_hash
        published = candidate
    else:
        document = ezdxf.readfile(candidate)
        _style_transfer_add_text(document, "LegacyTest", "LEGACY-TEST", (5, 5), extended=True)
        _style_transfer_add_text(document, "VN_UNICODE", "Mép boong chính", (10, 5))
        document.saveas(candidate)
        source_hash = fidelity_module.sha256_file(candidate)
        composed = run_fidelity_compose(source, output, manifest, approval, workspace_root=Path.cwd())
        assert fidelity_module.sha256_file(candidate) == source_hash
        published = composed / "layout.dxf"

    result = ezdxf.readfile(published)
    records = {entity.dxf.text: entity.dxf.style for entity in result.modelspace().query("TEXT")}
    assert records == {"LEGACY-TEST": "LegacyTest", "Mép boong chính": "VN_UNICODE"}
    assert result.styles.get("VN_UNICODE").dxf.font == "Arial.ttf"
    style = result.styles.get("LegacyTest")
    assert style.has_extended_font_data, "Fidelity dropped source STYLE extended font data"
    assert [(tag.code, tag.value) for tag in style.get_xdata("ACAD")] == [
        (1000, ".VnAvant"), (1071, 1048610),
    ]
    assert style.dxf.font == ""
    assert style.dxf.bigfont == "TEST_BIG.shx"
    assert style.dxf.height == pytest.approx(2.0)
    assert style.dxf.width == pytest.approx(0.75)
    assert style.dxf.oblique == pytest.approx(12.0)
    assert style.dxf.generation_flags == 2


@pytest.mark.parametrize("route", ["handoff", "compose"])
@pytest.mark.parametrize("field", ["font", "bigfont"])
@pytest.mark.parametrize("valid_utf8", [False, True], ids=["malformed", "unicode"])
def test_fidelity_extended_style_requires_encodable_filenames(
    tmp_path: Path, route: str, field: str, valid_utf8: bool,
) -> None:
    source, output, manifest, approval = _style_transfer_page(tmp_path)
    first, second = (_style_transfer_candidate(output, region) for region in ("first", "second"))
    filename = "legacy-\u6f22.shx" if valid_utf8 else "legacy-\udcff.shx"
    filenames = {field: filename}
    if route == "handoff":
        style_source = _style_transfer_owner(
            output, manifest, approval, "LegacyTest", extended=True, filenames=filenames,
        )
        transfer = run_fidelity_semantic_region_handoff
    else:
        style_source = second
        document = ezdxf.readfile(style_source)
        _style_transfer_add_text(
            document, "LegacyTest", "LEGACY-TEST", (5, 5), extended=True, filenames=filenames,
        )
        document.saveas(style_source)
        transfer = run_fidelity_compose

    source_style = ezdxf.readfile(style_source).styles.get("LegacyTest")
    assert source_style.dxf.get(field) == filename
    if not valid_utf8:
        with pytest.raises(UnicodeDecodeError):
            style_source.read_bytes().decode("utf-8")

    inputs = (source, first, second, style_source) if route == "handoff" else (source, first, second)
    before = [fidelity_module.sha256_file(path) for path in inputs]
    if not valid_utf8:
        with pytest.raises(FidelityError, match=r"(?i)STYLE.*encoding"):
            transfer(source, output, manifest, approval, workspace_root=Path.cwd())
        assert [fidelity_module.sha256_file(path) for path in inputs] == before
        assert not list(output.glob("semantic_region_handoff*"))
        assert not (output / "reconstruction_pages" / "page_01").exists()
        return

    result = transfer(source, output, manifest, approval, workspace_root=Path.cwd())
    published = second if route == "handoff" else result / "layout.dxf"
    published.read_bytes().decode("utf-8")
    assert ezdxf.readfile(published).styles.get("LegacyTest").dxf.get(field) == filename


@pytest.mark.parametrize("route", ["handoff", "compose"])
@pytest.mark.parametrize("byte_length", [255, 256])
def test_fidelity_text_style_enforces_xdata_family_byte_limit(
    tmp_path: Path, route: str, byte_length: int,
) -> None:
    source, output, manifest, approval = _style_transfer_page(tmp_path)
    first, second = (_style_transfer_candidate(output, name) for name in ("first", "second"))
    family = "\u00e9" * 127 + "A" * (byte_length - 254)
    encoding = ezdxf.readfile(second).output_encoding
    assert encoding == "utf-8"
    assert len(family.encode(encoding)) == byte_length
    inputs = [first, second]
    if route == "handoff":
        owner = _style_transfer_owner(output, manifest, approval, "LegacyTest", extended=True, family=family)
        inputs.append(owner)
        transfer = run_fidelity_semantic_region_handoff
    else:
        document = ezdxf.readfile(second)
        _style_transfer_add_text(document, "LegacyTest", "LEGACY-TEST", (5, 5), extended=True, family=family)
        document.saveas(second)
        transfer = run_fidelity_compose

    before = [fidelity_module.sha256_file(path) for path in inputs]
    if byte_length == 256:
        with pytest.raises(FidelityError, match=r"(?i)STYLE"):
            transfer(source, output, manifest, approval, workspace_root=Path.cwd())
        assert [fidelity_module.sha256_file(path) for path in inputs] == before
        assert not list(output.glob("semantic_region_handoff*"))
        assert not (output / "reconstruction_pages" / "page_01").exists()
        return

    result = transfer(source, output, manifest, approval, workspace_root=Path.cwd())
    published = second if route == "handoff" else result / "layout.dxf"
    style = ezdxf.readfile(published).styles.get("LegacyTest")
    assert [(tag.code, tag.value) for tag in style.get_xdata("ACAD")] == [
        (1000, family), (1071, 1048610),
    ]


@pytest.mark.parametrize(("version", "dxf_format"), [("R12", "asc"), ("R2010", "bin")])
@pytest.mark.parametrize("padded_style_marker", [False, True])
def test_fidelity_style_snapshot_preserves_encoding_and_binds_repeated_records(
    tmp_path: Path, version: str, dxf_format: str, padded_style_marker: bool,
) -> None:
    from io import BytesIO

    path = tmp_path / "style-input.dxf"
    document = ezdxf.new(version)
    document.encoding = "cp1252"
    if version == "R12":
        document.header["$HANDLING"] = 0
    family = "Caf\u00e9 Final"
    _style_transfer_add_text(document, "LegacyTest", "M\u00e9p", (5, 5), extended=True, family=family)
    document.saveas(path, fmt=dxf_format)
    original = path.read_bytes()

    valid, duplicates = fidelity_module._read_fidelity_style_document(path)
    style = valid.styles.get("LegacyTest")
    assert not duplicates
    assert [entity.dxf.text for entity in valid.modelspace().query("TEXT")] == ["M\u00e9p"]
    assert list(style.get_xdata("ACAD")) == [(1000, family), (1071, 1048610)]
    assert path.read_bytes() == original

    if dxf_format == "bin":
        encoded = BytesIO()
        writer = ezdxf.lldxf.tagwriter.BinaryTagWriter(
            encoded, dxfversion=document.dxfversion, encoding=document.output_encoding,
        )
        writer.write_tag2(1001, "ACAD")
        writer.write_tag2(1000, family)
        writer.write_tag2(1071, 1048610)
        declaration = encoded.getvalue()
    else:
        declaration = f"1001\nACAD\n1000\n{family}\n1071\n1048610\n".encode(document.output_encoding)
        if b"\r\n" in original:
            declaration = declaration.replace(b"\n", b"\r\n")
    assert original.count(declaration) == 1
    updated = original.replace(
        declaration, declaration.replace(b"Final", b"Other") + declaration,
    )
    if padded_style_marker:
        if dxf_format == "bin":
            marker, padded = b"\x00\x00STYLE\x00", b"\x00\x00\tSTYLE \x00"
        else:
            newline = b"\r\n" if b"\r\n" in original else b"\n"
            marker = b"  0" + newline + b"STYLE" + newline
            padded = b"  0" + newline + b"\tSTYLE " + newline
        assert marker in updated
        updated = updated.replace(marker, padded)
    path.write_bytes(updated)

    snapshot, duplicates = fidelity_module._read_fidelity_style_document(path)
    style = snapshot.styles.get("LegacyTest")
    expected = ("name", "legacytest") if version == "R12" else ("handle", style.dxf.handle)
    assert duplicates == {expected}
    target = ezdxf.new("R2010")
    with pytest.raises(FidelityError, match="Repeated ACAD.*STYLE"):
        fidelity_module._copy_fidelity_text_style(
            snapshot, target, "LEGACYTEST", source_repeated_styles=duplicates,
        )
    assert "LegacyTest" not in target.styles
    assert path.read_bytes() == updated


@pytest.mark.parametrize("location", ["handoff-owner", "handoff-target", "compose", "unused"])
@pytest.mark.parametrize(("padded_marker", "whitespace"), [
    ("", ""), ("STYLE", " "), ("STYLE", "\t"),
    ("SECTION", " "), ("SECTION", "\t"), ("TABLE", " "), ("TABLE", "\t"),
])
def test_fidelity_style_refuses_repeated_acad_before_publication(
    tmp_path: Path, location: str, padded_marker: str, whitespace: str,
) -> None:
    source, output, manifest, approval = _style_transfer_page(tmp_path)
    first, second = (_style_transfer_candidate(output, name) for name in ("first", "second"))
    inputs = [source, first, second]
    family = "FixtureFinal"
    if location.startswith("handoff"):
        owner = _style_transfer_owner(output, manifest, approval, "LegacyTest", extended=True, family=family)
        report = owner.parent / "report.json"
        inputs.extend((owner, report))
        transfer = run_fidelity_semantic_region_handoff
    else:
        transfer = run_fidelity_compose

    style_source = owner if location == "handoff-owner" else second
    if style_source == second:
        document = ezdxf.readfile(second)
        name = "LEGACYTEST" if location == "handoff-target" else "LegacyTest"
        _style_transfer_add_text(document, name, "FIXTURE", (5, 5), extended=True, family=family)
        if location == "unused":
            model = document.modelspace()
            model.delete_entity(model.query("TEXT")[-1])
        document.saveas(second)

    saved = style_source.read_bytes()
    declaration = f"1001\nACAD\n1000\n{family}\n1071\n1048610\n".encode("ascii")
    if b"\r\n" in saved:
        declaration = declaration.replace(b"\n", b"\r\n")
    assert saved.count(declaration) == 1
    earlier = declaration.replace(family.encode("ascii"), b"FixtureEarlier")
    updated = saved.replace(declaration, earlier + declaration)
    if padded_marker:
        newline = b"\r\n" if b"\r\n" in saved else b"\n"
        marker = b"  0" + newline + padded_marker.encode("ascii") + newline
        padded = b"  0" + newline + (whitespace + padded_marker + whitespace).encode("ascii") + newline
        if padded_marker == "SECTION":
            # Keep the first HEADER marker valid for ezdxf's file-type probe.
            tables = b"  2" + newline + b"TABLES" + newline
            marker += tables
            padded += tables
        assert marker in updated
        updated = updated.replace(marker, padded)
    style_source.write_bytes(updated)
    if location == "handoff-owner":
        owner_report = json.loads(report.read_text(encoding="utf-8"))
        owner_report["output_dxf_sha256"] = fidelity_module.sha256_file(owner)
        report.write_text(json.dumps(owner_report), encoding="utf-8")

    before = [fidelity_module.sha256_file(path) for path in inputs]
    if location == "unused":
        result = transfer(source, output, manifest, approval, workspace_root=Path.cwd())
        assert "LegacyTest" not in ezdxf.readfile(result / "layout.dxf").styles
    else:
        with pytest.raises(FidelityError, match="Repeated ACAD.*STYLE"):
            transfer(source, output, manifest, approval, workspace_root=Path.cwd())
        assert not list(output.glob("semantic_region_handoff*"))
        assert not (output / "reconstruction_pages" / "page_01").exists()
    assert [fidelity_module.sha256_file(path) for path in inputs] == before


@pytest.mark.parametrize("destination", ["plain", "extended", "malformed"])
def test_fidelity_text_style_handoff_refuses_late_conflict_before_any_save(
    tmp_path: Path, destination: str,
) -> None:
    source, output, manifest, approval = _style_transfer_page(tmp_path)
    first, second = (_style_transfer_candidate(output, name) for name in ("first", "second"))
    document = ezdxf.readfile(second)
    _style_transfer_add_text(document, "LEGACYTEST", "EXISTING", (2, 2), extended=destination != "plain")
    if destination == "malformed":
        document.styles.get("LEGACYTEST").set_xdata("ACAD", [(1000, ".VnAvant")])
    document.saveas(second)
    owner = _style_transfer_owner(output, manifest, approval, "LegacyTest", extended=destination != "extended")

    def snapshot():
        return tuple(fidelity_module.sha256_file(path) for path in (first, second, owner))

    before = snapshot()
    with pytest.raises(FidelityError, match=r"(?i)style"):
        run_fidelity_semantic_region_handoff(source, output, manifest, approval, workspace_root=Path.cwd())
    assert snapshot() == before
    assert not list(output.glob("semantic_region_handoff*"))


@pytest.mark.parametrize("legacy_first", [False, True])
def test_fidelity_text_style_compose_refuses_unicode_fallback_collision(
    tmp_path: Path, legacy_first: bool,
) -> None:
    source, output, manifest, approval = _style_transfer_page(tmp_path)
    candidates = [_style_transfer_candidate(output, name) for name in ("first", "second")]
    styles = [("vn_unicode", True), ("", False)]
    if not legacy_first:
        styles.reverse()
    for index, (candidate, (style, extended)) in enumerate(zip(candidates, styles)):
        document = ezdxf.readfile(candidate)
        _style_transfer_add_text(document, style, f"ROW {index}", (5, 5), extended=extended)
        document.saveas(candidate)

    before = [fidelity_module.sha256_file(path) for path in candidates]
    with pytest.raises(FidelityError, match=r"(?i)style"):
        run_fidelity_compose(source, output, manifest, approval, workspace_root=Path.cwd())
    assert [fidelity_module.sha256_file(path) for path in candidates] == before
    assert not (output / "reconstruction_pages" / "page_01").exists()


@pytest.mark.parametrize("variant", ["equal", "different-width", "malformed-first", "malformed-second", "plain"])
def test_fidelity_text_style_compose_checks_matching_style_definitions(
    tmp_path: Path, variant: str,
) -> None:
    source, output, manifest, approval = _style_transfer_page(tmp_path)
    candidates = [_style_transfer_candidate(output, name) for name in ("first", "second")]
    for index, (candidate, name) in enumerate(zip(candidates, ("LegacyTest", "LEGACYTEST"))):
        document = ezdxf.readfile(candidate)
        _style_transfer_add_text(document, name, f"ROW {index}", (5, 5), extended=variant != "plain")
        style = document.styles.get(name)
        if index == 1 and variant == "different-width":
            style.dxf.width = 1.0
        if (index == 0 and variant == "malformed-first") or (index == 1 and variant == "malformed-second"):
            style.set_xdata("ACAD", [(1000, ".VnAvant")])
        if index == 1 and variant == "plain":
            style.dxf.font = "other.shx"
        document.saveas(candidate)

    if variant in {"equal", "plain"}:
        composed = run_fidelity_compose(source, output, manifest, approval, workspace_root=Path.cwd())
        result = ezdxf.readfile(composed / "layout.dxf")
        assert len([style for style in result.styles if style.dxf.name.lower() == "legacytest"]) == 1
        assert {entity.dxf.style for entity in result.modelspace().query("TEXT")} == {"LegacyTest", "LEGACYTEST"}
        style = result.styles.get("LegacyTest")
        if variant == "equal":
            assert [(tag.code, tag.value) for tag in style.get_xdata("ACAD")] == [
                (1000, ".VnAvant"), (1071, 1048610),
            ]
        else:
            assert style.dxf.font == "Arial.ttf"
        return

    before = [fidelity_module.sha256_file(path) for path in candidates]
    with pytest.raises(FidelityError, match="STYLE"):
        run_fidelity_compose(source, output, manifest, approval, workspace_root=Path.cwd())
    assert [fidelity_module.sha256_file(path) for path in candidates] == before
    assert not (output / "reconstruction_pages" / "page_01").exists()


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
    from cad_agent import fidelity as fidelity_module

    original_page_ocr = fidelity_module._fidelity_page_text_ocr

    def unicode_fixture_ocr(image: np.ndarray, rois=None):
        texts = original_page_ocr(image, rois)
        if texts:
            # Keep the recognized source geometry while exercising Unicode DXF
            # styling with the existing visible-text fixture.
            texts[0].content = "SỐ LƯỢNG"
        return texts

    monkeypatch.setattr(fidelity_module, "_fidelity_page_text_ocr", unicode_fixture_ocr)
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)

    outputs = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())
    observation_path = outputs[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    assert observation["candidates"], "fixture PDF phải có ít nhất 1 candidate OCR"

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
    from PIL import ImageFont
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
        image, "VISIBLE", tight_bbox, 0.1, allow_tight_box_font_metric=True,
    )
    assert tight["glyph_bbox_px"] == tight_bbox
    assert tight["height_mm"] == pytest.approx((tight_bbox[3] - tight_bbox[1]) * 0.1)
    font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", size=32)
    mask_bbox = font.getmask("VISIBLE").getbbox()
    expected_width_factor = (tight_bbox[2] - tight_bbox[0]) * (mask_bbox[3] - mask_bbox[1]) / ((tight_bbox[3] - tight_bbox[1]) * font.getlength("VISIBLE"))
    assert tight["width_factor"] == pytest.approx(expected_width_factor)
    assert tight["insertion_px"] == [tight_bbox[0], tight_bbox[3]]


def test_page1_text_sizing_uses_font_width_for_tight_approved_boxes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tight OCR boxes still need the existing font-width correction."""
    from PIL import ImageFont
    from cad_agent import fidelity as fidelity_module

    monkeypatch.setenv("CAD_AGENT_FIDELITY_TEXT_FONT", r"C:\Windows\Fonts\arial.ttf")
    image = np.full((150, 500, 3), 255, dtype=np.uint8)
    cases = [
        ("TAO O TO THUNG KIN THACO K190", [10, 10, 463, 27]),
        ("THANH 0 TO TAl TAP LAI", [10, 40, 303, 80]),
        ("O TO SAU CAI TAGs", [10, 95, 401, 133]),
    ]
    # The first and third boxes model a tight source glyph band: every row is
    # active, so the conservative helper intentionally returns the original box.
    for _, bbox in (cases[0], cases[2]):
        x0, y0, x1, y1 = bbox
        image[y0:y1, x0:x1:5] = 0
        image[y0:y1, x1 - 1] = 0
    # The middle case models a separated glyph band and exercises the existing
    # visible-band path without changing the expected OCR anchor.
    x0, y0, x1, y1 = cases[1][1]
    image[y0 + 10:y1 - 10, x0:x1:5] = 0
    image[y0 + 10:y1 - 10, x1 - 1] = 0

    font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", size=32)
    for content, bbox in cases:
        sizing = fidelity_module._derive_text_reconstruction_size(
            image, content, bbox, 0.1, allow_tight_box_font_metric=True,
        )
        visible_width = bbox[2] - bbox[0]
        visible_height = bbox[3] - bbox[1] if content != cases[1][0] else 20
        mask_bbox = font.getmask(content).getbbox()
        expected_width_factor = visible_width * (mask_bbox[3] - mask_bbox[1]) / (visible_height * font.getlength(content))
        assert sizing["width_factor"] == pytest.approx(expected_width_factor, abs=1e-6)
        assert sizing["height_mm"] == pytest.approx(visible_height * 0.1)
        assert sizing["insertion_px"] == [bbox[0], bbox[3]]


def test_text_sizing_preserves_unmeasurable_fallback_for_other_text() -> None:
    """Text with no detectable glyphs keeps the existing safe fallback."""
    from cad_agent import fidelity as fidelity_module

    image = np.full((80, 120, 3), 255, dtype=np.uint8)
    bbox = [12, 18, 92, 42]

    sizing = fidelity_module._derive_text_reconstruction_size(
        image, "OTHER TEXT", bbox, 0.1,
    )

    assert sizing == {
        "glyph_bbox_px": bbox,
        "height_mm": pytest.approx(2.4),
        "width_factor": 1.0,
        "insertion_px": [12, 42],
    }


def test_text_sizing_keeps_tight_box_fallback_without_page1_opt_in() -> None:
    """Other callers keep the legacy tight-box fallback unless opted in."""
    from cad_agent import fidelity as fidelity_module

    image = np.full((80, 120, 3), 255, dtype=np.uint8)
    bbox = [12, 18, 92, 42]
    x0, y0, x1, y1 = bbox
    image[y0:y1, x0:x1:5] = 0
    image[y0:y1, x1 - 1] = 0

    sizing = fidelity_module._derive_text_reconstruction_size(
        image, "OTHER TEXT", bbox, 0.1,
    )

    assert sizing["glyph_bbox_px"] == bbox
    assert sizing["height_mm"] == pytest.approx(2.4)
    assert sizing["width_factor"] == 1.0
    assert sizing["insertion_px"] == [12, 42]


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

@pytest.mark.real_data
def test_native_pdf_observation_maps_exact_b041_aigdt_gid80_to_unverified_diameter_text(
    tmp_path: Path,
) -> None:
    """The exact embedded AIGDT glyph is mapped, but remains review-only TEXT evidence."""
    source_value = os.environ.get("CAD_AGENT_B041_PDF")
    if not source_value:
        pytest.skip("CAD_AGENT_B041_PDF is not configured")
    source = Path(source_value)
    assert source.is_file()
    assert __import__("hashlib").sha256(source.read_bytes()).hexdigest() == (
        "bf853aee4ba9b8381476d5ef1fa930d48a478ea56c3fe097695d41210d3afbe3"
    )
    output = tmp_path / "private-staging"
    manifest = new_fidelity_manifest(
        source, output, 144, "approved-test", workspace_root=Path.cwd(),
    )
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    native = observation["native_pdf_spans"]

    assert len(native) == 1  # Only B041 trace 321 has no later paint overlap under current policy.
    span = native[0]
    assert span["content"] == "\u2300"
    assert span["source_text_raw"] == "n"
    assert span["source_font_resource"] == {
        "xref": 24,
        "resource_name": "F5",
        "base_font": "ADSINV+AIGDT",
    }
    assert span["source_font_file_sha256"] == (
        "aac3c6c7451139928755b08a4bc193a63ed93b51df58ed2fdd559c450696029b"
    )
    assert span["source_glyph_id"] == 80
    assert span["source_glyph_name"] == "uniF06E"
    assert span["source_cmap_codepoint"] == 0xF06E
    assert span["source_paint_evidence"]["sequence_number"] == 321
    assert span["visibility"] == "unverified"
    assert span["source_sha256"] == manifest["source"]["sha256"]
    audit_path = output / observation["source_layout_audit"]["artifact"]
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert span["render_sha256"] == audit["source_page"]["render_sha256"]
    assert observation["candidates"]  # OCR remains a separate typed collection.
    assert all(candidate.get("source") != "native_pdf" for candidate in observation["candidates"])
    assert not any(key in observation for key in ("TEXT", "MTEXT", "DIMENSION"))


@pytest.mark.real_data
def test_native_pdf_observation_rejects_spoofed_b041_aigdt_resource(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AIGDT resource naming and GID 80 cannot substitute for exact embedded font bytes."""
    from cad_agent import fidelity as fidelity_module

    source_value = os.environ.get("CAD_AGENT_B041_PDF")
    if not source_value:
        pytest.skip("CAD_AGENT_B041_PDF is not configured")
    source = Path(source_value)
    assert source.is_file()
    assert fidelity_module.sha256_file(source) == (
        "bf853aee4ba9b8381476d5ef1fa930d48a478ea56c3fe097695d41210d3afbe3"
    )
    original_extract = fitz.Document.extract_font

    def spoof_font(document: fitz.Document, xref: int, *args: Any, **kwargs: Any) -> tuple[Any, ...]:
        extracted = original_extract(document, xref, *args, **kwargs)
        if xref == 24:
            return (*extracted[:3], b"different embedded font bytes")
        return extracted

    monkeypatch.setattr(fitz.Document, "extract_font", spoof_font)
    output = tmp_path / "private-staging-spoofed-font"
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(source, output, manifest, workspace_root=Path.cwd())[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))

    assert not any(span.get("source_glyph_id") == 80 for span in observation["native_pdf_spans"])
    assert not any(span.get("content") == "\u2300" for span in observation["native_pdf_spans"])


@pytest.mark.real_data
def test_native_pdf_text_approval_rejects_overlapping_b041_ocr_and_native_spans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Overlapping OCR/native source boxes cannot both enter one text approval."""
    source_value = os.environ.get("CAD_AGENT_B041_PDF")
    if not source_value:
        pytest.skip("CAD_AGENT_B041_PDF is not configured")
    source = Path(source_value)
    assert source.is_file()
    assert __import__("hashlib").sha256(source.read_bytes()).hexdigest() == (
        "bf853aee4ba9b8381476d5ef1fa930d48a478ea56c3fe097695d41210d3afbe3"
    )
    output = tmp_path / "private-staging"
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    native = next(span for span in observation["native_pdf_spans"] if span["content"] == "\u2300")
    ocr = next(candidate for candidate in observation["candidates"] if candidate["content"] == "12,00")
    native_bbox = native["bbox_px"]
    ocr_bbox = ocr["bbox_px"]
    overlap_width = min(native_bbox[2], ocr_bbox[2]) - max(native_bbox[0], ocr_bbox[0])
    overlap_height = min(native_bbox[3], ocr_bbox[3]) - max(native_bbox[1], ocr_bbox[1])
    assert overlap_width > 0 and overlap_height > 0

    selection_path = output / "diagnostic-mixed-selection.json"
    native_review = {"span": native, "visible_and_legible": True}
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [ocr["id"]],
            "native_span_ids": [native["id"]],
            "native_span_reviews": [native_review],
        }],
    }, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setenv("CAD_AGENT_FIDELITY_TEXT_FONT", r"C:\Windows\Fonts\seguisym.ttf")
    try:
        with pytest.raises(FidelityError, match="overlapping OCR and native PDF text"):
            write_fidelity_text_approval(
                source,
                output,
                manifest,
                1,
                observation_path,
                [ocr["id"]],
                "TEST_ONLY_DIAGNOSTIC_NOT_HUMAN_APPROVAL",
                workspace_root=Path.cwd(),
                native_span_ids=[native["id"]],
                native_span_reviews=[native_review],
                selection_path=selection_path,
            )
    finally:
        monkeypatch.delenv("CAD_AGENT_FIDELITY_TEXT_FONT", raising=False)
    assert not (output / "fidelity_text_approvals" / "page_01.json").exists()


@pytest.mark.real_data
def test_native_pdf_text_approval_keeps_nonoverlapping_b041_ocr_and_native_spans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_value = os.environ.get("CAD_AGENT_B041_PDF")
    if not source_value:
        pytest.skip("CAD_AGENT_B041_PDF is not configured")
    source = Path(source_value)
    assert source.is_file()
    assert __import__("hashlib").sha256(source.read_bytes()).hexdigest() == (
        "bf853aee4ba9b8381476d5ef1fa930d48a478ea56c3fe097695d41210d3afbe3"
    )
    output = tmp_path / "private-staging"
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    native = next(span for span in observation["native_pdf_spans"] if span["content"] == "\u2300")
    ocr = next(candidate for candidate in observation["candidates"] if candidate["content"] == "Adaptador")
    assert (
        max(ocr["bbox_px"][0], native["bbox_px"][0]) >= min(ocr["bbox_px"][2], native["bbox_px"][2])
        or max(ocr["bbox_px"][1], native["bbox_px"][1]) >= min(ocr["bbox_px"][3], native["bbox_px"][3])
    )
    native_review = {"span": native, "visible_and_legible": True}
    selection_path = output / "diagnostic-mixed-selection.json"
    selection_path.write_text(json.dumps({
        "schema_version": "fidelity-text-selection-1.0",
        "source": manifest["source"],
        "selections": [{
            "page": 1,
            "candidate_ids": [ocr["id"]],
            "native_span_ids": [native["id"]],
            "native_span_reviews": [native_review],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CAD_AGENT_FIDELITY_TEXT_FONT", r"C:\Windows\Fonts\seguisym.ttf")
    approval = write_fidelity_text_approval(
        source,
        output,
        manifest,
        1,
        observation_path,
        [ocr["id"]],
        "TEST_ONLY_DIAGNOSTIC_NOT_HUMAN_APPROVAL",
        workspace_root=Path.cwd(),
        native_span_ids=[native["id"]],
        native_span_reviews=[native_review],
        selection_path=selection_path,
    )
    assert len(approval["approved_candidates"]) == 1
    assert len(approval["approved_native_spans"]) == 1


@pytest.mark.real_data
def test_native_pdf_observation_aggregates_complete_nakuja_same_span_glyph_traces(
    tmp_path: Path,
) -> None:
    source_value = os.environ.get("CAD_AGENT_NAKUJA_PDF")
    if not source_value:
        pytest.skip("CAD_AGENT_NAKUJA_PDF is not configured")
    source = Path(source_value)
    assert source.is_file()
    assert __import__("hashlib").sha256(source.read_bytes()).hexdigest() == (
        "c9411e6769725c252425da18380a76b4db07036ad2b7801ceabc11d17f8a246c"
    )
    output = tmp_path / "private-staging"
    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    spans = [span for span in observation["native_pdf_spans"] if span["content"] == "10,00"]
    assert len(spans) == 1
    span = spans[0]
    assert span["visibility"] == "unverified"
    assert span["source_text_agreement"] == "exact"
    assert span["source_paint_evidence"]["member_sequence_numbers"] == [190, 191, 192, 193, 194]
    member_traces = span["source_paint_evidence"]["member_traces"]
    assert "".join(trace["text"] for trace in member_traces) == "10,00"
    assert [trace["sequence_number"] for trace in member_traces] == [190, 191, 192, 193, 194]
    assert all(trace["bbox_pt"] and trace["glyph_ids"] for trace in member_traces)


@pytest.mark.parametrize(
    "compound_mode",
    [
        "fm_a_multi_trace_bt_et_border_zones",
        "fm_b_hollow_frame_and_disjoint_strokes",
        "fm_c_multi_subpath_fill_arrowheads",
        "fm_d_baseline_underline_oblique_leader_and_table_divider",
        "fm_e_per_glyph_multi_trace_and_condensed_tz_spans",
        "combined_all_four_compound_modes",
    ],
)
def test_native_pdf_observation_admits_spans_inside_compound_cad_paint_operators(
    tmp_path: Path, compound_mode: str,
) -> None:
    import math

    source = tmp_path / f"{compound_mode}.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)

    # Interior CAD spans painted BEFORE later sheet-wide compound operators.
    page.insert_text((100, 120), "63", fontsize=12)
    page.insert_text((205, 120), "2 x M3 - 6H", fontsize=12)
    page.insert_text((155, 210), "35", fontsize=12, rotate=90)
    oblique_pivot = fitz.Point(235, 205)
    page.insert_text(
        oblique_pivot, "R13.50", fontsize=12, morph=(oblique_pivot, fitz.Matrix(-35.7)),
    )
    page.insert_text((310, 75), "+/-1", fontsize=8)
    page.insert_text((18, 45), "A", fontsize=10)

    if compound_mode in {"fm_a_multi_trace_bt_et_border_zones", "combined_all_four_compound_modes"}:
        xref = page.get_contents()[0]
        stream = document.xref_stream(xref)
        multi_trace_bt_et = (
            b"\nq BT 0 0 0 rg /F0 10 Tf 1 0 0 1 18 255 Tm (Z) Tj 362 -215 Td (Z) Tj "
            b"/F0 10.5 Tf -362 0 Td (Y) Tj 362 215 Td (W) Tj ET Q\n"
        )
        document.update_stream(xref, stream + multi_trace_bt_et)

    if compound_mode in {"fm_b_hollow_frame_and_disjoint_strokes", "combined_all_four_compound_modes"}:
        sh_stroke = page.new_shape()
        sh_stroke.draw_rect(fitz.Rect(10, 10, 390, 290))
        sh_stroke.draw_line((30, 80), (260, 80))
        sh_stroke.draw_line((30, 250), (360, 250))
        sh_stroke.finish(color=(0, 0, 0), fill=None, width=0.5)
        sh_stroke.commit()

    if compound_mode in {"fm_c_multi_subpath_fill_arrowheads", "combined_all_four_compound_modes"}:
        sh_fill = page.new_shape()
        sh_fill.draw_polyline([(25, 35), (31, 33.5), (31, 36.5)])
        sh_fill.draw_polyline([(370, 275), (364, 273.5), (364, 276.5)])
        sh_fill.finish(color=None, fill=(0, 0, 0), closePath=True)
        sh_fill.commit()

    if compound_mode in {
        "fm_d_baseline_underline_oblique_leader_and_table_divider",
        "combined_all_four_compound_modes",
    }:
        sh_cad = page.new_shape()
        # Horizontal dimension line 2.0 pt below baseline y=120 of "63" (inside char[3] descent).
        sh_cad.draw_line((90, 122.0), (135, 122.0))
        # Leader shelf 1.9 pt below baseline y=120 of "2 x M3 - 6H".
        sh_cad.draw_line((200, 121.9), (285, 121.9))
        # Oblique radial leader 2.2 pt below rotated baseline of "R13.50" (-35.7 deg in fitz -> dir=(0.812, 0.584)).
        ang = math.radians(35.7)
        ux, uy = math.cos(ang), math.sin(ang)
        nx_down, ny_down = -uy, ux
        lp0 = fitz.Point(oblique_pivot.x + 2.2 * nx_down, oblique_pivot.y + 2.2 * ny_down)
        lp1 = fitz.Point(lp0.x + 48.0 * ux, lp0.y + 48.0 * uy)
        sh_cad.draw_line(lp0, lp1)
        # Tall perpendicular table column divider grazing right side-bearing of "+/-1".
        sh_cad.draw_line((323.85, 50.0), (323.85, 100.0))
        sh_cad.finish(color=(0, 0, 0), fill=None, width=0.5)
        sh_cad.commit()

    if compound_mode == "fm_e_per_glyph_multi_trace_and_condensed_tz_spans":
        xref = page.get_contents()[0]
        stream = document.xref_stream(xref)
        # Inventor-style separate BT..ET per glyph ("M", "1", "2") + 75% Tz condensed aggregate run ("AB   CD").
        per_glyph_and_tz = (
            b"\nq BT 0 0 0 rg /F0 12 Tf 1 0 0 1 60 220 Tm (M) Tj ET Q"
            b"\nq BT 0 0 0 rg /F0 12 Tf 1 0 0 1 70 220 Tm (1) Tj ET Q"
            b"\nq BT 0 0 0 rg /F0 12 Tf 1 0 0 1 76.7 220 Tm (2) Tj ET Q"
            b"\nq BT 0 0 0 rg 75 Tz /F0 10 Tf 1 0 0 1 60 245 Tm (AB) Tj 40 0 Td (CD) Tj ET Q\n"
        )
        document.update_stream(xref, stream + per_glyph_and_tz)
        sh_box = page.new_shape()
        sh_box.draw_rect(fitz.Rect(10, 10, 390, 290))
        sh_box.finish(color=(0, 0, 0), fill=None, width=0.5)
        sh_box.commit()

    document.save(source)
    document.close()

    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    contents = {span["content"] for span in observation["native_pdf_spans"]}

    assert {"63", "2 x M3 - 6H", "35", "R13.50", "+/-1"}.issubset(contents)
    if compound_mode == "fm_e_per_glyph_multi_trace_and_condensed_tz_spans":
        assert {"M12", "AB", "CD"}.issubset(contents)
    assert all(span["visibility"] == "unverified" for span in observation["native_pdf_spans"])
    assert all(span["semantic_role"] is None for span in observation["native_pdf_spans"])


@pytest.mark.parametrize(
    "attack_kind",
    [
        "compound_fill_subpath_whiteout",
        "horizontal_mid_body_strikethrough",
        "diagonal_x_crossout_stroke",
        "short_vertical_slash_through_digit",
        "thick_dark_redaction_stroke",
        "thin_rgb_white_erase_stroke",
        "thin_gray_white_erase_stroke",
        "thin_cmyk_white_erase_stroke",
        "later_overlapping_multi_trace_text",
    ],
)
def test_native_pdf_observation_compound_paint_still_excludes_real_masking_and_strikethroughs(
    tmp_path: Path, attack_kind: str,
) -> None:
    source = tmp_path / f"{attack_kind}.pdf"
    output = tmp_path / "private-staging"
    document = fitz.open()
    page = document.new_page(width=400, height=300)

    page.insert_text((60, 120), "100", fontsize=14)
    page.insert_text((240, 220), "SAFE NOTE", fontsize=12)

    if attack_kind == "compound_fill_subpath_whiteout":
        sh = page.new_shape()
        sh.draw_polyline([(20, 30), (25, 28.5), (25, 31.5)])
        sh.draw_rect(fitz.Rect(63, 110, 82, 121))
        sh.finish(color=None, fill=(1, 1, 1), closePath=True)
        sh.commit()
    elif attack_kind == "horizontal_mid_body_strikethrough":
        sh = page.new_shape()
        sh.draw_rect(fitz.Rect(10, 10, 390, 290))
        sh.draw_line((56, 115.0), (92, 115.0))
        sh.finish(color=(0, 0, 0), fill=None, width=0.6)
        sh.commit()
    elif attack_kind == "diagonal_x_crossout_stroke":
        sh = page.new_shape()
        sh.draw_line((58, 121.0), (88, 109.0))
        sh.finish(color=(0, 0, 0), fill=None, width=0.6)
        sh.commit()
    elif attack_kind == "short_vertical_slash_through_digit":
        sh = page.new_shape()
        sh.draw_line((72.0, 109.0), (72.0, 121.0))
        sh.finish(color=(0, 0, 0), fill=None, width=0.6)
        sh.commit()
    elif attack_kind == "thick_dark_redaction_stroke":
        sh = page.new_shape()
        sh.draw_line((72.0, 40.0), (72.0, 260.0))
        sh.finish(color=(0, 0, 0), fill=None, width=8.0)
        sh.commit()
    elif attack_kind == "thin_rgb_white_erase_stroke":
        sh = page.new_shape()
        sh.draw_line((55.0, 121.5), (92.0, 121.5))
        sh.finish(color=(1, 1, 1), fill=None, width=0.5)
        sh.commit()
    elif attack_kind == "thin_gray_white_erase_stroke":
        xref = page.get_contents()[0]
        stream = document.xref_stream(xref)
        # PDF bottom-up y: page height 300 - 121.5 = 178.5
        document.update_stream(xref, stream + b"\nq 1 G 0.5 w 55 178.5 m 92 178.5 l S Q\n")
    elif attack_kind == "thin_cmyk_white_erase_stroke":
        xref = page.get_contents()[0]
        stream = document.xref_stream(xref)
        document.update_stream(xref, stream + b"\nq 0 0 0 0 K 0.5 w 55 178.5 m 92 178.5 l S Q\n")
    elif attack_kind == "later_overlapping_multi_trace_text":
        xref = page.get_contents()[0]
        stream = document.xref_stream(xref)
        # PDF bottom-up y: 300 - 120 = 180 -> overlaps "100" at (60, 120) inside multi-run BT..ET!
        overlap_bt = (
            b"\nq BT 0 0 0 rg /F0 14 Tf 1 0 0 1 18 260 Tm (A) Tj "
            b"/F0 14.5 Tf 44 -80 Td (999) Tj ET Q\n"
        )
        document.update_stream(xref, stream + overlap_bt)

    document.save(source)
    document.close()

    manifest = new_fidelity_manifest(source, output, 144, "approved-test", workspace_root=Path.cwd())
    run_fidelity_pdf(source, output, output / "fidelity-run-manifest.json", manifest)
    observation_path = run_fidelity_text_observations(
        source, output, manifest, workspace_root=Path.cwd(),
    )[0]
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    contents = {span["content"] for span in observation["native_pdf_spans"]}

    assert "100" not in contents
    assert "SAFE NOTE" in contents


@pytest.mark.parametrize(
    "vector_id",
    [
        "vertical_stroke_turns_minus_into_plus",
        "tall_vertical_stroke_through_middle_digit",
        "horizontal_stroke_across_rotated_90_seam",
        "horizontal_stroke_across_upper_cap_bar_066em",
        "horizontal_stroke_across_decimal_point_004em",
        "below_baseline_white_fill_over_q_tail",
        "inverted_font_descriptor_oblique_overwrite",
    ],
)
def test_native_pdf_observation_excludes_perpendicular_cap_dot_and_descender_masks(
    vector_id: str,
) -> None:
    from cad_agent import fidelity as fidelity_module

    document = fitz.open()
    page = document.new_page(width=300, height=200)
    page.insert_text((200, 160), "CONTROL", fontsize=12)

    if vector_id == "vertical_stroke_turns_minus_into_plus":
        target = "-100"
        page.insert_text((80, 100), target, fontsize=12)
        minus_rect = fitz.Rect(page.get_texttrace()[-1]["chars"][0][3])
        mx = 0.5 * (minus_rect.x0 + minus_rect.x1)
        sh = page.new_shape()
        sh.draw_line((mx, 75.0), (mx, 125.0))
        sh.finish(color=(0, 0, 0), fill=None, width=0.8)
        sh.commit()
    elif vector_id == "tall_vertical_stroke_through_middle_digit":
        target = "100"
        page.insert_text((80, 100), target, fontsize=12)
        zero_rect = fitz.Rect(page.get_texttrace()[-1]["chars"][1][3])
        zx = 0.5 * (zero_rect.x0 + zero_rect.x1)
        sh = page.new_shape()
        sh.draw_line((zx, 70.0), (zx, 130.0))
        sh.finish(color=(0, 0, 0), fill=None, width=0.8)
        sh.commit()
    elif vector_id == "horizontal_stroke_across_rotated_90_seam":
        target = "35"
        page.insert_text((140, 120), target, fontsize=12, rotate=90)
        t_rect = fitz.Rect(page.get_texttrace()[-1]["bbox"])
        mid_y = 0.5 * (t_rect.y0 + t_rect.y1)
        sh = page.new_shape()
        sh.draw_line((110.0, mid_y), (170.0, mid_y))
        sh.finish(color=(0, 0, 0), fill=None, width=0.8)
        sh.commit()
    elif vector_id == "horizontal_stroke_across_upper_cap_bar_066em":
        target = "77"
        page.insert_text((80, 100), target, fontsize=12)
        y_upper = 100.0 - 0.66 * 12.0
        sh = page.new_shape()
        sh.draw_rect(fitz.Rect(10, 10, 290, 190))
        sh.draw_line((75.0, y_upper), (105.0, y_upper))
        sh.finish(color=(0, 0, 0), fill=None, width=0.8)
        sh.commit()
    elif vector_id == "horizontal_stroke_across_decimal_point_004em":
        target = "10.5"
        page.insert_text((80, 100), target, fontsize=12)
        y_dot = 100.0 - 0.04 * 12.0
        sh = page.new_shape()
        sh.draw_rect(fitz.Rect(10, 10, 290, 190))
        sh.draw_line((75.0, y_dot), (115.0, y_dot))
        sh.finish(color=(0, 0, 0), fill=None, width=0.8)
        sh.commit()
    elif vector_id == "below_baseline_white_fill_over_q_tail":
        target = "Q10"
        page.insert_text((80, 100), target, fontsize=12)
        sh = page.new_shape()
        sh.draw_polyline([(20, 20), (25, 19), (25, 21)])
        sh.draw_rect(fitz.Rect(78.0, 100.05, 95.0, 104.0))
        sh.finish(color=None, fill=(1, 1, 1), closePath=True)
        sh.commit()
    else:
        target = "OBL1"
        piv = fitz.Point(80, 120)
        page.insert_text(piv, target, fontsize=12, morph=(piv, fitz.Matrix(-35.0)))
        page.insert_text(piv, "OBL2", fontsize=12, morph=(piv, fitz.Matrix(-35.0)))

    reopened = fitz.open(stream=document.tobytes(), filetype="pdf")
    document.close()
    try:
        pg = reopened[0]
        if vector_id == "inverted_font_descriptor_oblique_overwrite":
            class InvertedMetricsPage:
                def __getattr__(self, name: str) -> Any:
                    return getattr(pg, name)

                def get_texttrace(self) -> list[dict[str, Any]]:
                    return [dict(t, ascender=-0.5, descender=0.9) for t in pg.get_texttrace()]

            records = fidelity_module._native_pdf_text_span_records(
                InvertedMetricsPage(), 1, "a" * 64, "b" * 64, 600, 400, "displayed-page-box-v1",
            )
        else:
            records = fidelity_module._native_pdf_text_span_records(
                pg, 1, "a" * 64, "b" * 64, 600, 400, "displayed-page-box-v1",
            )
    finally:
        reopened.close()

    contents = {r["content"] for r in records}
    assert target not in contents
    assert "CONTROL" in contents



@pytest.mark.parametrize(
    "r3_case",
    [
        "multitrace_overprint_M6_to_M68",
        "intra_trace_backspace_overprint_1_to_18",
        "shared_member_seqno_sibling_overwrite",
        "same_seqno_later_trace_whiteout",
        "wide_white_stroke_text_1Tr_erases_100",
        "anisotropic_ctm_whiteout_stroke",
        "acute_miter_spike_whiteout",
        "condensed_50Tz_upper_cap_white_fill",
        "condensed_75Tz_066em_cap_bar_strikethrough",
        "vertical_stroke_right_20pct_of_1C",
        "light_gray_079_comma_tail_erase",
        "descender_g10_dark_strikethrough_015em",
    ],
)
def test_native_pdf_observation_r3_blocks_overprint_anisotropic_miter_condensed_and_gray_escapes(
    r3_case: str,
) -> None:
    from cad_agent import fidelity as fidelity_module

    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((250, 250), "CONTROL", fontsize=12)

    if r3_case == "multitrace_overprint_M6_to_M68":
        target = "M68"
        page.insert_text((60, 120), "M6", fontsize=12)
        page.insert_text((70, 120), "8", fontsize=12)
    elif r3_case == "intra_trace_backspace_overprint_1_to_18":
        target = "18"
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref) + b"\nq BT 0 0 0 rg /F0 12 Tf 1 0 0 1 60 180 Tm (1) Tj 0 0 Td (8) Tj ET Q\n",
        )
    elif r3_case == "shared_member_seqno_sibling_overwrite":
        target = "100"
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq BT 0 0 0 rg /F0 12 Tf 1 0 0 1 60 180 Tm (1) Tj ET Q"
            + b"\nq BT 0 0 0 rg /F0 12 Tf 1 0 0 1 66.67 180 Tm (0) Tj ET Q"
            + b"\nq BT 0 0 0 rg /F0 12 Tf 1 0 0 1 73.34 180 Tm (0) Tj /F0 16 Tf -22.0 -1.2 Td (===) Tj ET Q\n",
        )
    elif r3_case == "same_seqno_later_trace_whiteout":
        target = "100"
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq BT 0 0 0 rg /F0 12 Tf 1 0 0 1 60 180 Tm (100) Tj 1 1 1 rg /F0 16 Tf 1 0 0 1 48 179 Tm (MM) Tj ET Q\n",
        )
    elif r3_case == "wide_white_stroke_text_1Tr_erases_100":
        target = "100"
        page.insert_text((80, 86), target, fontsize=12)
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq BT 1 1 1 RG 20 w 1 j 1 Tr /F0 12 Tf 1 0 0 1 20 280 Tm (A) Tj /F0 12.5 Tf 60 -82 Td (XXX) Tj ET Q\n",
        )
    elif r3_case == "anisotropic_ctm_whiteout_stroke":
        target = "100"
        page.insert_text((60, 120), target, fontsize=12)
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq 0.05 0 0 25 0 0 cm 1 1 1 RG 1.2 w 400 4.0 3600 6.0 re 1000 7.06 m 1900 7.06 l S Q\n",
        )
    elif r3_case == "acute_miter_spike_whiteout":
        target = "100"
        page.insert_text((60, 120), target, fontsize=12)
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq 1 1 1 RG 2.5 w 0 j 30 M 20 120 140 150 re 68.5 140.0 m 70.0 175.0 l 71.5 140.0 l S Q\n",
        )
    elif r3_case == "condensed_50Tz_upper_cap_white_fill":
        target = "77"
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq BT 0 0 0 rg 50 Tz /F0 20 Tf 1 0 0 1 60 180 Tm (77) Tj ET Q"
            + b"\nq 1 1 1 rg 20 20 5 5 re 55 188.2 30 8.0 re f Q\n",
        )
    elif r3_case == "condensed_75Tz_066em_cap_bar_strikethrough":
        target = "77"
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq BT 0 0 0 rg 75 Tz /F0 12 Tf 1 0 0 1 60 180 Tm (77) Tj ET Q"
            + b"\nq 0 0 0 RG 0.8 w 10 10 380 280 re 55 187.92 m 85 187.92 l S Q\n",
        )
    elif r3_case == "vertical_stroke_right_20pct_of_1C":
        target = "1C"
        page.insert_text((80, 100), target, fontsize=12)
        grect = fitz.Rect(page.get_texttrace()[-1]["chars"][1][3])
        rx = grect.x1 - 0.20 * grect.width
        sh = page.new_shape()
        sh.draw_line((rx, 70.0), (rx, 130.0))
        sh.finish(color=(0, 0, 0), fill=None, width=0.8)
        sh.commit()
    elif r3_case == "light_gray_079_comma_tail_erase":
        target = "10,5"
        page.insert_text((60, 120), target, fontsize=12)
        sh = page.new_shape()
        sh.draw_rect(fitz.Rect(10, 10, 390, 290))
        sh.draw_line((55.0, 122.15), (95.0, 122.15))
        sh.finish(color=(0.79, 0.79, 0.79), fill=None, width=2.0)
        sh.commit()
    else:
        target = "g10"
        page.insert_text((80, 100), target, fontsize=12)
        sh = page.new_shape()
        sh.draw_rect(fitz.Rect(10, 10, 390, 290))
        sh.draw_line((76.0, 101.8), (105.0, 101.8))
        sh.finish(color=(0, 0, 0), fill=None, width=0.8)
        sh.commit()

    reopened = fitz.open(stream=document.tobytes(), filetype="pdf")
    document.close()
    try:
        records = fidelity_module._native_pdf_text_span_records(
            reopened[0], 1, "a" * 64, "b" * 64, 800, 600, "displayed-page-box-v1",
        )
    finally:
        reopened.close()

    contents = {r["content"] for r in records}
    assert target not in contents
    assert "CONTROL" in contents



def test_native_pdf_observation_r3_dense_hatch_caching_stays_fast() -> None:
    import time
    from cad_agent import fidelity as fidelity_module

    doc = fitz.open()
    pg = doc.new_page(width=800, height=600)
    for row in range(15):
        for col in range(10):
            pg.insert_text((40 + col * 70, 40 + row * 35), f"{row * 10 + col:03d}", fontsize=10)
    sh = pg.new_shape()
    sh.draw_rect(fitz.Rect(5, 5, 795, 595))
    for k in range(2500):
        y_h = 10.0 + (k % 25) * 0.2
        sh.draw_line((10.0, y_h), (790.0, y_h))
    sh.finish(color=(0, 0, 0), fill=None, width=0.3)
    sh.commit()
    hatch_bytes = doc.tobytes()
    doc.close()

    reopened = fitz.open(stream=hatch_bytes, filetype="pdf")
    try:
        t0 = time.perf_counter()
        records = fidelity_module._native_pdf_text_span_records(
            reopened[0], 1, "a" * 64, "b" * 64, 1600, 1200, "displayed-page-box-v1",
        )
        elapsed = time.perf_counter() - t0
    finally:
        reopened.close()

    assert len(records) == 150
    assert elapsed < 1.5


@pytest.mark.parametrize(
    "r4_case",
    [
        "closed_subpath_start_vertex_acute_miter_whiteout",
        "closed_subpath_zero_length_prefix_acute_miter_whiteout",
        "quad_ul_start_vertex_acute_miter_whiteout",
        "multirun_later_30Tz_tall_white_overwrite",
        "multirun_later_5Tz_extreme_tall_white_overwrite",
        "same_seq_later_uncolored_30Tz_tall_dark_overwrite",
    ],
)
def test_native_pdf_observation_r4_closed_subpath_miter_and_multirun_condensed_text_occluders(
    r4_case: str,
) -> None:
    from cad_agent import fidelity as fidelity_module

    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((250, 250), "CONTROL", fontsize=12)
    target = "100"

    if r4_case == "closed_subpath_start_vertex_acute_miter_whiteout":
        page.insert_text((60, 120), target, fontsize=12)
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq 1 1 1 RG 4.0 w 0 j 10 M 10 10 380 280 re 70.0 175.0 m 55.0 50.0 l 85.0 50.0 l h S Q\n",
        )
    elif r4_case == "closed_subpath_zero_length_prefix_acute_miter_whiteout":
        page.insert_text((60, 120), target, fontsize=12)
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq 1 1 1 RG 4.0 w 0 j 10 M 10 10 380 280 re 70.0 175.0 m 70.0 175.0 l 55.0 50.0 l 85.0 50.0 l h S Q\n",
        )
    elif r4_case == "quad_ul_start_vertex_acute_miter_whiteout":
        page.insert_text((60, 120), target, fontsize=12)
        sh = page.new_shape()
        sh.draw_rect(fitz.Rect(10, 10, 390, 290))
        sh.draw_quad(
            fitz.Quad(
                fitz.Point(70.0, 125.0),
                fitz.Point(85.0, 250.0),
                fitz.Point(55.0, 250.0),
                fitz.Point(70.0, 260.0),
            )
        )
        sh.finish(color=(1, 1, 1), fill=None, width=4.0, lineJoin=0)
        sh.commit()
    elif r4_case == "multirun_later_30Tz_tall_white_overwrite":
        page.insert_text((60, 114), target, fontsize=12)
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq BT 1 1 1 rg /F0 12 Tf 1 0 0 1 15 280 Tm (A) Tj "
            b"30 Tz /F0 30 Tf 45 -106 Td (MMMM) Tj "
            b"100 Tz /F0 12 Tf 290 -154 Td (B) Tj ET Q\n",
        )
    elif r4_case == "multirun_later_5Tz_extreme_tall_white_overwrite":
        page.insert_text((60, 114), target, fontsize=12)
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq BT 1 1 1 rg /F0 12 Tf 1 0 0 1 15 280 Tm (A) Tj "
            b"5 Tz /F0 60 Tf 45 -126 Td (MMMMMMMMMMMM) Tj "
            b"100 Tz /F0 12 Tf 290 -134 Td (B) Tj ET Q\n",
        )
    else:
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq BT 0 0 0 rg /F0 12 Tf 1 0 0 1 60 186 Tm (100) Tj "
            b"30 Tz /F0 30 Tf 0 -12 Td (MMMM) Tj ET Q\n",
        )

    reopened = fitz.open(stream=document.tobytes(), filetype="pdf")
    document.close()
    try:
        records = fidelity_module._native_pdf_text_span_records(
            reopened[0], 1, "a" * 64, "b" * 64, 800, 600, "displayed-page-box-v1",
        )
    finally:
        reopened.close()

    contents = {r["content"] for r in records}
    assert target not in contents
    assert "CONTROL" in contents


@pytest.mark.parametrize(
    ("line_y", "expected"),
    [
        pytest.param(83.2, {"CONTROL"}, id="crosses-ink-above-0.68em"),
        pytest.param(80.5, {"77", "CONTROL"}, id="clear-top-margin"),
        pytest.param(99.5, {"CONTROL"}, id="crosses-ink-near-baseline"),
        pytest.param(101.0, {"77", "CONTROL"}, id="clear-bottom-margin"),
    ],
)
def test_native_pdf_observation_thin_stroke_at_glyph_bounds(
    line_y: float, expected: set[str],
) -> None:
    with fitz.open() as document:
        page = document.new_page(width=300, height=200)
        page.insert_text((80, 100), "77", fontsize=24, fontname="helv")
        page.insert_text((180, 100), "CONTROL", fontsize=12)
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(10, 10, 290, 190))
        shape.draw_line((75, line_y), (112, line_y))
        shape.finish(color=(0, 0, 0), width=0.20)
        shape.commit()
        pdf_bytes = document.tobytes()

    with fitz.open(stream=pdf_bytes, filetype="pdf") as reopened:
        records = fidelity_module._native_pdf_text_span_records(
            reopened[0], 1, "a" * 64, "b" * 64, 600, 400, "displayed-page-box-v1",
        )

    assert {record["content"] for record in records} == expected


def _native_pdf_font_resource_probe(
    monkeypatch: pytest.MonkeyPatch,
    rows: list[tuple[int, str, str, int]],
):
    from types import SimpleNamespace

    import fontTools.ttLib

    resources = [
        (xref, "ttf", "Type0", name, f"F{xref}", encoding, 0)
        for xref, name, encoding, _ in rows
    ]
    programs = {xref: program for xref, _, _, program in rows}
    metadata = {}
    for xref, _, _, program in rows:
        metadata[xref, "DescendantFonts"] = ("array", f"[{xref + 100} 0 R]")
        metadata[xref + 100, "CIDToGIDMap"] = ("name", "/Identity")
        metadata[xref + 100, "FontDescriptor"] = ("xref", f"{xref + 200} 0 R")
        metadata[xref + 200, "FontFile2"] = ("xref", f"{program} 0 R")
        metadata[program, "Length1"] = ("int", "8")

    extracted = []

    def extract_font(xref):
        extracted.append(xref)
        return ("Fixture", "ttf", "Type0", bytes([programs[xref]]) * 8)

    document = SimpleNamespace(
        xref_get_key=lambda xref, key: metadata.get((xref, key), ("null", "null")),
        xref_is_stream=lambda xref: xref in programs.values(),
        extract_font=extract_font,
    )
    page = SimpleNamespace(parent=document, get_fonts=lambda **_: resources)
    # The fixture observes extraction and identity handling before real font parsing.
    monkeypatch.setattr(fontTools.ttLib, "TTFont", lambda stream, **_: stream.read())
    return fidelity_module._NativePdfThinStrokeCheck(page, ()), extracted


def test_native_pdf_preparation_extracts_shared_font_program_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observer, extracted = _native_pdf_font_resource_probe(monkeypatch, [
        (1, "First+Fixture", "Identity-H", 41),
        (2, "Second+Fixture", "Identity-H", 41),
    ])

    assert observer._embedded_font("Fixture") is not None
    assert len(extracted) == 1


def test_native_pdf_preparation_rejects_unsupported_shared_font_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observer, _ = _native_pdf_font_resource_probe(monkeypatch, [
        (1, "First+Fixture", "Identity-H", 41),
        (2, "Second+Fixture", "Identity-V", 41),
    ])

    assert observer._embedded_font("Fixture") is None


@pytest.mark.parametrize(
    ("limit_name", "limit"),
    [("_FONT_PROGRAM_LIMIT", 1), ("_FONT_BYTES_LIMIT", 8)],
    ids=["distinct-programs", "retained-decoded-bytes"],
)
def test_native_pdf_preparation_stops_font_work_at_page_budget(
    monkeypatch: pytest.MonkeyPatch, limit_name: str, limit: int,
) -> None:
    monkeypatch.setattr(fidelity_module._NativePdfThinStrokeCheck, limit_name, limit, raising=False)
    observer, extracted = _native_pdf_font_resource_probe(monkeypatch, [
        (1, "First", "Identity-H", 41),
        (2, "Second", "Identity-H", 42),
        (3, "Third", "Identity-H", 43),
    ])

    assert observer._embedded_font("First") is not None
    later = [observer._embedded_font(name) for name in ("Second", "Third", "Second")]
    assert later == [None, None, None]
    assert extracted == [1]



@pytest.mark.real_data
@pytest.mark.parametrize(
    ("swap_svg_strokes", "expected_target_retained"),
    [
        pytest.param(False, False, id="source-bound-contact"),
        pytest.param(True, True, id="same-kind-substitution-falls-back"),
    ],
)
def test_native_pdf_observation_jxs_below_baseline_stroke_binding(
    monkeypatch: pytest.MonkeyPatch,
    swap_svg_strokes: bool,
    expected_target_retained: bool,
) -> None:
    import hashlib
    from xml.etree import ElementTree as ET

    source_value = os.environ.get("CAD_AGENT_PR578_JXS_PDF")
    if not source_value:
        pytest.skip("CAD_AGENT_PR578_JXS_PDF is not configured")
    source = Path(source_value).read_bytes()
    source_sha = hashlib.sha256(source).hexdigest()
    assert source_sha == "622cb0e63817026bb2d680c8c2e7cb265b9fe3a5c8a6b86e5390e15bf86e8f05"

    swapped = False
    if swap_svg_strokes:
        original_export = fitz.Page.get_svg_image

        def export_with_mismatched_stroke(page, matrix=None, text_as_path=True):
            nonlocal swapped
            svg = original_export(page, matrix=matrix, text_as_path=text_as_path)
            if not text_as_path:
                return svg
            root = ET.fromstring(svg)
            path_positions = [i for i, child in enumerate(root) if child.tag.endswith("}path")]
            path_sequences = [
                i for i, (kind, _) in enumerate(page.get_bboxlog())
                if kind in ("stroke-path", "fill-path")
            ]
            positions_by_sequence = dict(zip(path_sequences, path_positions, strict=True))
            clear_stroke = positions_by_sequence[101]
            contact_stroke = positions_by_sequence[103]
            root[clear_stroke], root[contact_stroke] = root[contact_stroke], root[clear_stroke]
            swapped = True
            return ET.tostring(root, encoding="unicode")

        monkeypatch.setattr(fitz.Page, "get_svg_image", export_with_mismatched_stroke)

    with fitz.open(stream=source, filetype="pdf") as document:
        page = document[0]
        raster = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csGRAY)
        result = fidelity_module._native_pdf_text_span_records(
            page, 1, source_sha, hashlib.sha256(raster.samples).hexdigest(),
            raster.width, raster.height, "displayed-page-box-v1",
        )

    spans = {span["id"]: span for span in result}
    assert "native-pdf-p01-b041-l004-s000" in spans  # Verified clear gap of 0.292 pt.
    assert "native-pdf-p01-b028-l000-s000" not in spans  # Existing stroke rejection.
    assert swapped is swap_svg_strokes
    target_retained = "native-pdf-p01-b007-l001-s000" in spans
    assert target_retained is expected_target_retained


@pytest.mark.real_data
@pytest.mark.parametrize(
    ("font_row_limit", "expected_target_retained"),
    [
        pytest.param(None, True, id="ordinary-source-with-proof"),
        pytest.param(1, False, id="lowered-font-row-budget"),
    ],
)
def test_native_pdf_observation_jxs_dark_fill_requires_glyph_separation(
    monkeypatch: pytest.MonkeyPatch,
    font_row_limit: int | None,
    expected_target_retained: bool,
) -> None:
    import hashlib

    source_value = os.environ.get("CAD_AGENT_PR578_JXS_PDF")
    if not source_value:
        pytest.skip("CAD_AGENT_PR578_JXS_PDF is not configured")
    source_path = Path(source_value)
    source = source_path.read_bytes()
    source_sha = hashlib.sha256(source).hexdigest()
    assert source_sha == "622cb0e63817026bb2d680c8c2e7cb265b9fe3a5c8a6b86e5390e15bf86e8f05"

    if font_row_limit is not None:
        monkeypatch.setattr(fidelity_module._NativePdfThinStrokeCheck, "_FONT_ROW_LIMIT", font_row_limit)

    with fitz.open(stream=source, filetype="pdf") as document:
        page = document[0]
        assert len(page.get_fonts(full=True)) == 6
        raster = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csGRAY)
        records = fidelity_module._native_pdf_text_span_records(
            page, 1, source_sha, hashlib.sha256(raster.samples).hexdigest(),
            raster.width, raster.height, "displayed-page-box-v1",
        )

    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == source_sha
    spans = {span["id"]: span for span in records}
    assert "native-pdf-p01-b041-l004-s000" in spans  # Unrelated clear dimension.
    assert "native-pdf-p01-b028-l000-s000" not in spans  # Existing stroke rejection.
    target_retained = "native-pdf-p01-b009-l000-s000" in spans
    assert target_retained is expected_target_retained


@pytest.mark.parametrize(
    ("fill_left", "separated"),
    [(0.0, False), (0.003, False), (0.004, False), (0.005, True)],
    ids=["touching", "grazing", "touching-after-padding", "positive-padded-gap"],
)
def test_native_pdf_dark_fill_requires_strict_padded_separation(fill_left: float, separated: bool) -> None:
    check = fidelity_module._NativePdfThinStrokeCheck
    assert check._strict_fill_separation((-2.0, 0.0, 0.0, 1.0), (fill_left, 0.0, 2.0, 1.0)) is separated


@pytest.mark.parametrize(
    ("svg_path", "embedded_has_ink", "expected"),
    [
        ("", False, ()),
        ("", True, None),
        ("M0 0 L1 0 L1 1 Z", False, None),
        ("M0 0 L1 0 L1 1 Z", True, (0.0, 0.0, 1.0, 1.0)),
    ],
    ids=["both-empty", "embedded-only-ink", "svg-only-ink", "both-ink"],
)
def test_native_pdf_dark_fill_checks_both_glyph_outlines(
    monkeypatch: pytest.MonkeyPatch, svg_path: str, embedded_has_ink: bool, expected: tuple | None,
) -> None:
    from xml.etree.ElementTree import Element

    from fontTools.pens.recordingPen import RecordingPen

    embedded = RecordingPen()
    if embedded_has_ink:
        embedded.moveTo((0.0, 0.0))
        embedded.lineTo((1.0, 0.0))
        embedded.lineTo((1.0, 1.0))
        embedded.closePath()
    check = fidelity_module._NativePdfThinStrokeCheck(None, [])
    definition = Element("path", d=svg_path)
    glyph_set = {"glyph": type("Glyph", (), {"draw": staticmethod(embedded.replay)})()}
    binding = (glyph_set, "glyph", (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), "#000000", definition, 1.0)
    monkeypatch.setattr(check, "_bound_glyph", lambda *args, **kwargs: binding)

    if expected is None:
        with pytest.raises(ValueError, match="Glyph outlines disagree"):
            check._glyph_control_bounds({}, (), 1.0)
    else:
        assert check._glyph_control_bounds({}, (), 1.0) == expected


def test_native_pdf_dark_fill_rejects_nonunique_glyph_use() -> None:
    from xml.etree.ElementTree import Element

    check = fidelity_module._NativePdfThinStrokeCheck(None, [])
    matrix = (10.0, 0.0, 0.0, -10.0, 20.0, 40.0)
    check.glyphs[("A", 7)] = [(Element("use"), matrix), (Element("use"), matrix)]
    trace = {"type": 0, "opacity": 1, "wmode": 0, "dir": (1.0, 0.0), "size": 10.0}
    glyph = (ord("A"), 7, (20.0, 40.0), (20.0, 30.0, 26.0, 40.0))
    with pytest.raises(ValueError, match="Glyph cannot be uniquely bound"):
        check._glyph_control_bounds(trace, glyph, 10.0)


def test_native_pdf_dark_fill_reuses_unavailable_binding_and_keeps_stroke_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check = fidelity_module._NativePdfThinStrokeCheck(None, [])
    check.export_ready = True
    calls = []
    monkeypatch.setattr(check, "_bound_fill_components", lambda sequence, *_: calls.append(sequence))
    check.pairs = check._PAIR_LIMIT  # The protected stroke phase spent its full allowance.

    for sequence in (5, 5, 6, 7):
        assert not check.separates_dark_fill(sequence, {}, [], {"_trace_order_idx": 0}, 1.0)
    assert calls == [5, 6]
    assert check.pairs == check._PAIR_LIMIT
    assert check.fill_attempts == 2
    assert check.pixels == 0


def test_native_pdf_dark_fill_bounds_glyph_by_component_comparisons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check = fidelity_module._NativePdfThinStrokeCheck(None, [])
    check.export_ready = True
    check.fill_bounds[5] = [(0.0, 0.0, 1.0, 1.0)] * 1_000
    trace = {"_trace_order_idx": 0}
    check.ink_bounds[(0, 18.0, None)] = [(2.0, 2.0, 3.0, 3.0)] * 101
    comparison_count = 0

    def count_comparison(_ink, _fill):
        nonlocal comparison_count
        comparison_count += 1
        return True

    monkeypatch.setattr(check, "_strict_fill_separation", count_comparison)

    separated = check.separates_dark_fill(5, {}, [], trace, 18.0)
    assert comparison_count <= 100_000
    assert not separated


@pytest.mark.parametrize("compare_whole", [False, True])
def test_native_pdf_dark_fill_keeps_binding_receipts_per_character_scope(
    compare_whole: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    check = fidelity_module._NativePdfThinStrokeCheck(None, [])
    check.export_ready = True
    lookups = []
    monkeypatch.setattr(check, "_bound_fill_components", lambda sequence, *_: lookups.append(sequence))

    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((40, 80), "CAD NOTES", fontsize=18)
        trace, = page.get_texttrace()
    whole = {**trace, "_trace_order_idx": 0}
    chars = whole["chars"]
    split = 3

    def selected(start: int, end: int) -> dict[str, Any]:
        return {
            **whole,
            "chars": chars[start:end],
            "_source_character_range": (start, end),
            "_aggregate_trace_char_count": len(chars),
        }

    first = selected(0, split)
    second = selected(split, len(chars))
    malformed = {**second, "_source_character_range": (split, len(chars) + 1)}
    for scope in (first, first, whole if compare_whole else second, malformed):
        assert not check.separates_dark_fill(5, {}, [], scope, 18.0)

    assert len(check.fill_separations) == 2
    assert check.fill_attempts == 2
    assert check.pairs == 0
    assert lookups == [5]


@pytest.mark.parametrize(
    "r5_case",
    [
        "bezier_bezier_acute_miter_whiteout",
        "closed_bezier_line_start_vertex_miter_whiteout",
        "projecting_square_cap_2J_45deg_whiteout",
        "anisotropic_ctm_1M_with_diag_whiteout",
        "oversized_svg_anisotropic_ctm_whiteout",
        "tounicode_space_mapped_glyph_whiteout",
        "expanded_1500Tz_midbody_strikethrough",
        "expanded_500Tz_10pt_thick_bar_erase",
        "tilted_3deg_intratrace_W8_overprint",
        "oblique_35deg_multitrace_W8_overprint",
    ],
)
def test_native_pdf_observation_r5_bezier_miter_square_cap_aniso_ctm_tounicode_space_expanded_tz_and_tilted_overprint(
    r5_case: str,
) -> None:
    import math
    from cad_agent import fidelity as fidelity_module

    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((250, 250), "CONTROL", fontsize=12)
    target = "100"

    if r5_case == "bezier_bezier_acute_miter_whiteout":
        page.insert_text((60, 120), target, fontsize=12)
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq 1 1 1 RG 8.0 w 0 j 10 M 20 100 140 150 re "
            b"55.0 48.0 m 60.0 89.67 65.0 131.33 70.0 173.0 c "
            b"75.0 131.33 80.0 89.67 85.0 48.0 c S Q\n",
        )
    elif r5_case == "closed_bezier_line_start_vertex_miter_whiteout":
        page.insert_text((60, 120), target, fontsize=12)
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq 1 1 1 RG 4.0 w 0 j 10 M 10 10 380 280 re "
            b"70.0 175.0 m 65.0 133.33 60.0 91.67 55.0 50.0 c "
            b"85.0 50.0 l h S Q\n",
        )
    elif r5_case == "projecting_square_cap_2J_45deg_whiteout":
        page.insert_text((60, 120), target, fontsize=12)
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq 1 1 1 RG 40.0 w 2 J 1 j 10 80 160 200 re "
            b"50.0 137.0 m 70.0 157.0 l 90.0 230.0 m 70.0 210.0 l S Q\n",
        )
    elif r5_case in {"anisotropic_ctm_1M_with_diag_whiteout", "oversized_svg_anisotropic_ctm_whiteout"}:
        page.insert_text((60, 120), target, fontsize=12)
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq 0.1 0 0 10 0 0 cm 1 1 1 RG 3.0 w 0 j 1 M "
            b"400 16.0 600 5.0 re 410 16.1 m 420 16.2 l 550 17.5 m 850 17.5 l S Q\n",
        )
    elif r5_case == "tounicode_space_mapped_glyph_whiteout":
        page.insert_text((60, 120), target, fontsize=12)
        page.clean_contents()
        cmap_stream = (
            b"/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            b"/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            b"/CMapName /CustomSpaceMap def\n/CMapType 2 def\n"
            b"1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
            b"1 beginbfchar\n<4D> <0020>\nendbfchar\nendcmap\n"
            b"CMapName currentdict /CMap defineresource pop\nend\nend\n"
        )
        cmap_xref = document.get_new_xref()
        document.update_object(cmap_xref, "<< >>")
        document.update_stream(cmap_xref, cmap_stream)
        font_xref = document.get_new_xref()
        document.update_object(
            font_xref,
            f"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding /ToUnicode {cmap_xref} 0 R >>",
        )
        pg_obj = document.xref_object(page.xref)
        if "/Font <<" in pg_obj:
            document.update_object(page.xref, pg_obj.replace("/Font <<", f"/Font << /F99 {font_xref} 0 R ", 1))
        else:
            res_type, res_val = document.xref_get_key(page.xref, "Resources")
            r_xref = int(res_val.split()[0])
            r_obj = document.xref_object(r_xref)
            if "/Font <<" in r_obj:
                document.update_object(r_xref, r_obj.replace("/Font <<", f"/Font << /F99 {font_xref} 0 R ", 1))
            else:
                _, f_val = document.xref_get_key(r_xref, "Font")
                f_xref = int(f_val.split()[0])
                document.update_object(f_xref, document.xref_object(f_xref).replace("<<", f"<< /F99 {font_xref} 0 R ", 1))
        c_xref = page.get_contents()[0]
        document.update_stream(
            c_xref,
            document.xref_stream(c_xref)
            + b"\nq BT 1 1 1 rg /F99 18 Tf 1 0 0 1 58 178 Tm (M) Tj 2 0 Td (M) Tj 2 0 Td (M) Tj 2 0 Td (M) Tj 2 0 Td (M) Tj ET Q\n",
        )
    elif r5_case == "expanded_1500Tz_midbody_strikethrough":
        target = "10"
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq BT 0 0 0 rg 1500 Tz /F0 10 Tf 1 0 0 1 40 180 Tm (10) Tj ET Q\n"
            b"q 0 0 0 RG 2.0 w 10 10 380 280 re 35 183.6 m 230 183.6 l S Q\n",
        )
    elif r5_case == "expanded_500Tz_10pt_thick_bar_erase":
        page.clean_contents()
        xref = page.get_contents()[0]
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq BT 0 0 0 rg 500 Tz /F0 10 Tf 1 0 0 1 40 180 Tm (100) Tj ET Q\n"
            b"q 0 0 0 RG 10.0 w 10 10 380 280 re 35 176.95 m 195 176.95 l S Q\n",
        )
    elif r5_case == "tilted_3deg_intratrace_W8_overprint":
        target = "W8"
        page.clean_contents()
        xref = page.get_contents()[0]
        ang = math.radians(-3.0)
        ca, sa = math.cos(ang), math.sin(ang)
        t1 = f"{ca:.6f} {sa:.6f} {-sa:.6f} {ca:.6f} 60.0 180.0 Tm".encode("ascii")
        document.update_stream(xref, document.xref_stream(xref) + b"\nq BT 0 0 0 rg /F0 12 Tf " + t1 + b" [(W) 650 (8)] TJ ET Q\n")
    else:
        target = "W8"
        page.clean_contents()
        xref = page.get_contents()[0]
        ang = math.radians(-35.7)
        ca, sa = math.cos(ang), math.sin(ang)
        t1 = f"{ca:.6f} {sa:.6f} {-sa:.6f} {ca:.6f} 60.0 180.0 Tm".encode("ascii")
        t2 = f"{ca:.6f} {sa:.6f} {-sa:.6f} {ca:.6f} {60.0 + 3.5 * ca:.6f} {180.0 + 3.5 * sa:.6f} Tm".encode("ascii")
        document.update_stream(
            xref,
            document.xref_stream(xref)
            + b"\nq BT 0 0 0 rg /F0 12 Tf " + t1 + b" (W) Tj ET Q\n"
            + b"q BT 0 0 0 rg /F0 12 Tf " + t2 + b" (8) Tj ET Q\n",
        )

    reopened = fitz.open(stream=document.tobytes(), filetype="pdf")
    document.close()
    try:
        observation_page: Any = reopened[0]
        if r5_case == "oversized_svg_anisotropic_ctm_whiteout":
            class OversizedSvgPage:
                svg_calls = 0

                def __getattr__(self, name: str) -> Any:
                    return getattr(reopened[0], name)

                def get_svg_image(self, **kwargs: Any) -> str:
                    self.svg_calls += 1
                    return "<svg>" + (" " * (4 * 1024 * 1024 + 1))

            observation_page = OversizedSvgPage()
        records = fidelity_module._native_pdf_text_span_records(
            observation_page, 1, "a" * 64, "b" * 64, 800, 600, "displayed-page-box-v1",
        )
        if r5_case == "oversized_svg_anisotropic_ctm_whiteout":
            assert observation_page.svg_calls == 1
    finally:
        reopened.close()

    contents = {r["content"] for r in records}
    assert target not in contents
    assert "CONTROL" in contents
