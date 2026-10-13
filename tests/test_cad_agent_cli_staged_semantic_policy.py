from __future__ import annotations

import json
from pathlib import Path

from cad_agent.cli import _run_dxf, _run_semantic
from cad_agent.live import load_build_evidence
from dxf_builder_lib.reviewer import review_dxf
from primitive_ir_lib.models import (
    Calibration,
    CircleGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
    Validation,
)


def test_staged_cli_preserves_circle_without_implicit_component_geometry(
    tmp_path: Path,
) -> None:
    primitive_path = tmp_path / "primitive.json"
    semantic_path = tmp_path / "semantic.json"
    dxf_path = tmp_path / "staged.dxf"
    evidence_path = tmp_path / "build-evidence.json"
    primitive = Primitive(
        id="wp46-circle",
        type="circle",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 1, 1)),
        validation=Validation(status="unreviewed"),
        geometry=CircleGeometry(center=Point2D(100.0, 200.0), radius=4.0),
    )
    primitive_doc = PrimitiveIRDocument(
        source_document=SourceDocument(
            file_name="synthetic-circle.png",
            page_index=0,
            image_width_px=1,
            image_height_px=1,
        ),
        calibration=Calibration(
            unit="mm",
            pixel_to_unit_scale=1.0,
            origin_px=(0, 0),
            method="manual_override",
            status="verified",
        ),
        primitives=[primitive],
    )
    primitive_path.write_text(json.dumps(primitive_doc.to_dict()), encoding="utf-8")

    _run_semantic(primitive_path, semantic_path)
    semantic_payload = json.loads(semantic_path.read_text(encoding="utf-8"))
    assert len(semantic_payload["parts"]) == 1
    assert semantic_payload["parts"][0]["part_type"] == "lo_bat_vit"
    assert semantic_payload["parts"][0]["source"] == "rule_geometry"
    assert semantic_payload["parts"][0]["validation"]["status"] == "unreviewed"

    _run_dxf(primitive_path, semantic_path, dxf_path, evidence_path)

    build = load_build_evidence(evidence_path, dxf_path)
    review = review_dxf(build, strict_primitive_inventory=True)
    assert review.passed, review.format_report()
    assert review.checked_count == 1
    assert review.component_checked_count == 0
    assert review.dimension_checked_count == 0
    assert build.written_geometry_by_primitive_id == {
        "wp46-circle": {
            "type": "circle",
            "center": [100.0, 200.0],
            "radius": 4.0,
        }
    }
    assert build.dimension_count == 0
    assert build.dimension_handle_by_cross_validation_id == {}
    assert build.written_dimension_by_cross_validation_id == {}
    assert build.component_count == 0
    assert build.component_handle_by_part_id == {}
    assert build.component_type_by_part_id == {}
    assert build.written_component_by_part_id == {}
    assert all(
        not layer.startswith("COMP_")
        for layer in build.layer_by_primitive_id.values()
    )
