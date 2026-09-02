from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from primitive_ir_lib.models import (
    Calibration,
    CircleGeometry,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)


def _primitive_doc() -> PrimitiveIRDocument:
    points = [
        (0.0, 0.0),
        (100.0, 0.0),
        (100.0, 20.0),
        (140.0, 20.0),
        (140.0, 80.0),
        (100.0, 80.0),
        (100.0, 100.0),
        (0.0, 100.0),
        (0.0, 0.0),
    ]
    primitives = [
        Primitive(
            id=f"edge-{index}",
            type="line",
            source="geometry_opencv",
            confidence=1.0,
            trace=Trace(bbox_px=(0, 0, 1, 1)),
            geometry=LineGeometry(
                start=Point2D(*start), end=Point2D(*end)
            ),
        )
        for index, (start, end) in enumerate(zip(points, points[1:]))
    ]
    primitives.append(
        Primitive(
            id="hole-1",
            type="circle",
            source="geometry_opencv",
            confidence=1.0,
            trace=Trace(bbox_px=(35, 45, 45, 55)),
            geometry=CircleGeometry(center=Point2D(40.0, 50.0), radius=5.0),
        )
    )
    return PrimitiveIRDocument(
        source_document=SourceDocument(
            file_name="page_01.png",
            page_index=0,
            image_width_px=140,
            image_height_px=100,
        ),
        calibration=Calibration(
            unit="mm",
            pixel_to_unit_scale=1.0,
            origin_px=(0.0, 0.0),
            method="manual_override",
            status="verified",
        ),
        primitives=primitives,
    )


def _write_primitive(path: Path) -> str:
    payload = _primitive_doc().to_dict()
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _write_synthetic_pdf(path: Path) -> None:
    import fitz

    document = fitz.open()
    page = document.new_page(width=600, height=400)
    shape = page.new_shape()
    points = [
        (60, 80),
        (360, 80),
        (360, 150),
        (480, 150),
        (480, 250),
        (360, 250),
        (360, 320),
        (60, 320),
        (60, 80),
    ]
    for start, end in zip(points, points[1:]):
        shape.draw_line(fitz.Point(*start), fitz.Point(*end))
    shape.finish(color=(0, 0, 0), fill=None, width=1.0)
    shape.commit()
    page.draw_circle(fitz.Point(210, 200), 25, color=(0, 0, 0), width=1.0)
    document.set_metadata(
        {
            "format": "PDF 1.7",
            "title": "phase4-synthetic-shaft-v1",
            "author": "cad-agent-test",
            "subject": "deterministic synthetic fixture",
            "keywords": "cad-agent phase4 shaft",
        }
    )
    document.save(path)
    document.close()


def test_phase4_primitive_binds_selected_shaft_and_hole_cluster(
    tmp_path: Path,
) -> None:
    from cad_agent.mechanical_pilot import bind_simple_shaft_pilot_from_primitive

    primitive_path = tmp_path / "page_01.json"
    source_sha = _write_primitive(primitive_path)
    result = bind_simple_shaft_pilot_from_primitive(
        primitive_path, tmp_path / "candidate" / "candidate.dxf"
    )

    assert result.source_sha256 == source_sha
    assert [part.part_type for part in result.semantic_doc.parts] == [
        "mechanical_shaft_step",
        "mechanical_hole_feature",
    ]
    assert result.build.entity_count == 9
    assert result.review.passed is True


def test_phase4_primitive_refuses_ambiguous_geometry(tmp_path: Path) -> None:
    from cad_agent.mechanical_pilot import bind_simple_shaft_pilot_from_primitive

    primitive_path = tmp_path / "ambiguous.json"
    payload = _primitive_doc().to_dict()
    payload["primitives"].append(
        {
            "id": "extra-line",
            "type": "line",
            "source": "geometry_opencv",
            "confidence": 1.0,
            "layer": "UNCLASSIFIED",
            "handle": None,
            "trace": {"bbox_px": [0, 0, 1, 1]},
            "validation": {"status": "unreviewed"},
            "geometry": {
                "start": {"x": 0.0, "y": 0.0},
                "end": {"x": 10.0, "y": 10.0},
            },
        }
    )
    primitive_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="PILOT_SHAFT_PROFILE_INVALID"):
        bind_simple_shaft_pilot_from_primitive(
            primitive_path, tmp_path / "candidate" / "candidate.dxf"
        )


def test_phase4_pdf_pipeline_binds_the_selected_pilot_contract(tmp_path: Path) -> None:
    from cad_agent.mechanical_pilot import bind_simple_shaft_pilot_from_primitive
    from cad_agent.pdf import new_pdf_manifest, run_pdf_stages

    pdf_path = tmp_path / "synthetic_simple_shaft.pdf"
    _write_synthetic_pdf(pdf_path)
    run_dir = tmp_path / "pdf-run"
    manifest_path = run_dir / "pdf-run-manifest.json"
    manifest = new_pdf_manifest(
        pdf_path, 1.0, "phase4-synthetic-calibration-v1", 144
    )
    run_pdf_stages(pdf_path, run_dir, manifest_path, manifest)

    result = bind_simple_shaft_pilot_from_primitive(
        run_dir / "pdf" / "primitive_ir" / "page_01.json",
        tmp_path / "candidate" / "candidate.dxf",
        pdf_manifest_path=manifest_path,
        pdf_source_path=pdf_path,
    )

    assert result.pilot_id == "synthetic-simple-stepped-shaft-v1"
    assert result.primitive_doc.source_document.file_name == "page_01.png"
    assert [part.part_type for part in result.semantic_doc.parts] == [
        "mechanical_shaft_step",
        "mechanical_hole_feature",
    ]
    assert result.build.entity_count == 9
    assert result.review.passed is True
    assert result.source_pdf_name == pdf_path.name
    assert result.source_pdf_sha256 == hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    persisted = json.loads(result.pilot_evidence_path.read_text(encoding="utf-8"))
    assert persisted["primitive_source_document"]["sha256"] == (
        result.primitive_doc.source_document.sha256
    )
    assert persisted["source_sha256"] == result.source_sha256
    assert persisted["source_pdf"]["sha256"] == result.source_pdf_sha256


def test_phase4_pdf_pipeline_rejects_unmerged_extraction_configuration(
    tmp_path: Path,
) -> None:
    from cad_agent.mechanical_pilot import bind_simple_shaft_pilot_from_primitive
    from primitive_ir_lib.run_pdf import run_pdf

    pdf_path = tmp_path / "synthetic_simple_shaft.pdf"
    _write_synthetic_pdf(pdf_path)
    run_dir = tmp_path / "pdf-run"
    run_pdf(
        pdf_path,
        run_dir,
        scale_mm_per_px=1.0,
        dpi=144,
        preset="real_scan_tuned_v1",
        merge_lines=False,
    )

    with pytest.raises(ValueError, match="PILOT_SHAFT_PROFILE_INVALID"):
        bind_simple_shaft_pilot_from_primitive(
            run_dir / "primitive_ir" / "page_01.json",
            tmp_path / "candidate" / "candidate.dxf",
        )
