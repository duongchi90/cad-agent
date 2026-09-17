from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "phase3_synthetic_simple_shaft_v1.json"


def test_simple_shaft_pilot_builds_typed_features_and_round_trips(tmp_path: Path) -> None:
    from cad_agent.mechanical_pilot import build_simple_shaft_pilot

    candidate = tmp_path / "candidate.dxf"
    result = build_simple_shaft_pilot(FIXTURE, candidate)

    assert result.pilot_id == "synthetic-simple-stepped-shaft-v1"
    assert result.feature_bindings == {
        "shaft-profile-001": {
            "kind": "shaft_step",
            "primitive_ids": [
                "shaft-profile-001:top-main",
                "shaft-profile-001:step-rise",
                "shaft-profile-001:top-step",
                "shaft-profile-001:right-cap",
                "shaft-profile-001:bottom-step",
                "shaft-profile-001:step-fall",
                "shaft-profile-001:bottom-main",
                "shaft-profile-001:left-cap",
            ],
        },
        "hole-axial-001": {
            "kind": "hole_feature",
            "primitive_ids": ["hole-axial-001"],
        },
    }
    assert [part.part_type for part in result.semantic_doc.parts] == [
        "mechanical_shaft_step",
        "mechanical_hole_feature",
    ]
    assert result.build.entity_count == 9
    assert result.review.passed is True
    assert result.build_evidence_path.is_file()
    assert result.pilot_evidence_path.is_file()
    persisted = json.loads(result.pilot_evidence_path.read_text(encoding="utf-8"))
    assert persisted["source_sha256"] == result.source_sha256
    assert persisted["candidate_sha256"] == result.candidate_sha256
    assert persisted["review"]["passed"] is True
    assert result.candidate_sha256 == hashlib.sha256(candidate.read_bytes()).hexdigest()
    assert result.source_sha256 == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert result.build.layer_by_primitive_id["shaft-profile-001:top-main"] == (
        "MECHANICAL_SHAFT_STEP"
    )
    assert result.build.layer_by_primitive_id["hole-axial-001"] == (
        "MECHANICAL_HOLE_FEATURE"
    )


def test_primitive_bound_pilot_validates_source_candidate_binding(
    tmp_path: Path,
) -> None:
    """Require the real build path to bind source geometry to its candidate."""

    import importlib.util

    helper_path = Path(__file__).with_name("test_cad_agent_phase4_pilot_binding.py")
    spec = importlib.util.spec_from_file_location(
        "phase4_pilot_test_helpers_for_build_binding", helper_path
    )
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)

    from cad_agent.live import load_build_evidence
    from cad_agent.mechanical_pilot import (
        bind_simple_shaft_pilot_from_primitive,
        validate_primitive_bound_candidate,
    )
    from dxf_builder_lib.reviewer import review_dxf

    primitive_a_path = tmp_path / "primitive-a" / "page_01.json"
    primitive_a_path.parent.mkdir()
    helper._write_primitive(primitive_a_path)
    result_a = bind_simple_shaft_pilot_from_primitive(
        primitive_a_path, tmp_path / "candidate-a" / "candidate.dxf"
    )
    assert validate_primitive_bound_candidate(
        primitive_a_path, result_a.candidate_path, result_a.build_evidence_path
    ) == (result_a.source_sha256, result_a.candidate_sha256)

    primitive_b_path = tmp_path / "primitive-b" / "page_01.json"
    primitive_b_path.parent.mkdir()
    primitive_b = json.loads(primitive_a_path.read_text(encoding="utf-8"))
    primitive_b["calibration"]["pixel_to_unit_scale"] = 2.0
    for primitive in primitive_b["primitives"]:
        geometry = primitive["geometry"]
        if primitive["type"] == "line":
            for point in (geometry["start"], geometry["end"]):
                point["x"] *= 2.0
                point["y"] *= 2.0
        else:
            geometry["center"]["x"] *= 2.0
            geometry["center"]["y"] *= 2.0
            geometry["radius"] *= 2.0
    primitive_b_path.write_text(
        json.dumps(primitive_b, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    result_b = bind_simple_shaft_pilot_from_primitive(
        primitive_b_path, tmp_path / "candidate-b" / "candidate.dxf"
    )
    loaded_b = load_build_evidence(
        result_b.build_evidence_path, result_b.candidate_path
    )
    assert review_dxf(loaded_b).passed is True

    with pytest.raises(ValueError, match="PILOT_PRIMITIVE_BUILD_BINDING_MISMATCH"):
        validate_primitive_bound_candidate(
            primitive_a_path, result_b.candidate_path, result_b.build_evidence_path
        )


def test_primitive_bound_pilot_rejects_untracked_extra_dxf_entity(
    tmp_path: Path,
) -> None:
    """The source-bound validator must reject extra actual DXF entities."""

    import importlib.util

    helper_path = Path(__file__).with_name("test_cad_agent_phase4_pilot_binding.py")
    spec = importlib.util.spec_from_file_location(
        "phase4_pilot_test_helpers_for_extra_entity_binding", helper_path
    )
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)

    from cad_agent.live import load_build_evidence
    from cad_agent.mechanical_pilot import (
        bind_simple_shaft_pilot_from_primitive,
        validate_primitive_bound_candidate,
    )
    from dxf_builder_lib.reviewer import review_dxf
    from dxf_builder_lib.tests.dxf_test_support import add_untracked_entity_for_test

    primitive_path = tmp_path / "primitive" / "page_01.json"
    primitive_path.parent.mkdir()
    helper._write_primitive(primitive_path)
    result = bind_simple_shaft_pilot_from_primitive(
        primitive_path, tmp_path / "candidate" / "candidate.dxf"
    )

    extra_handle = add_untracked_entity_for_test(result.candidate_path, "LINE")
    assert extra_handle not in result.build.handle_by_primitive_id.values()

    evidence = json.loads(result.build_evidence_path.read_text(encoding="utf-8"))
    evidence["dxf"]["sha256"] = hashlib.sha256(
        result.candidate_path.read_bytes()
    ).hexdigest()
    result.build_evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    refreshed_build = load_build_evidence(
        result.build_evidence_path, result.candidate_path
    )
    assert review_dxf(refreshed_build).passed is True

    with pytest.raises(ValueError, match="PILOT_PRIMITIVE_BUILD_REVIEW_FAILED"):
        validate_primitive_bound_candidate(
            primitive_path, result.candidate_path, result.build_evidence_path
        )


def test_primitive_bound_pilot_rejects_untracked_lwpolyline_entity(
    tmp_path: Path,
) -> None:
    """The source-bound validator must reject extra non-primitive entities."""

    import importlib.util

    helper_path = Path(__file__).with_name("test_cad_agent_phase4_pilot_binding.py")
    spec = importlib.util.spec_from_file_location(
        "phase4_pilot_test_helpers_for_lwpolyline_binding", helper_path
    )
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)

    from cad_agent.live import load_build_evidence
    from cad_agent.mechanical_pilot import (
        bind_simple_shaft_pilot_from_primitive,
        validate_primitive_bound_candidate,
    )
    from dxf_builder_lib.reviewer import review_dxf
    from dxf_builder_lib.tests.dxf_test_support import add_untracked_entity_for_test

    primitive_path = tmp_path / "primitive" / "page_01.json"
    primitive_path.parent.mkdir()
    helper._write_primitive(primitive_path)
    result = bind_simple_shaft_pilot_from_primitive(
        primitive_path, tmp_path / "candidate" / "candidate.dxf"
    )

    extra_handle = add_untracked_entity_for_test(
        result.candidate_path, "LWPOLYLINE"
    )
    assert extra_handle not in result.build.handle_by_primitive_id.values()

    evidence = json.loads(result.build_evidence_path.read_text(encoding="utf-8"))
    evidence["dxf"]["sha256"] = hashlib.sha256(
        result.candidate_path.read_bytes()
    ).hexdigest()
    result.build_evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    refreshed_build = load_build_evidence(
        result.build_evidence_path, result.candidate_path
    )
    assert review_dxf(refreshed_build).passed is True

    with pytest.raises(ValueError, match="PILOT_PRIMITIVE_BUILD_REVIEW_FAILED"):
        validate_primitive_bound_candidate(
            primitive_path, result.candidate_path, result.build_evidence_path
        )


def test_primitive_bound_pilot_rejects_forged_component_inventory(
    tmp_path: Path,
) -> None:
    """The primitive-bound pilot must not trust forged component evidence."""

    import importlib.util

    helper_path = Path(__file__).with_name("test_cad_agent_phase4_pilot_binding.py")
    spec = importlib.util.spec_from_file_location(
        "phase4_pilot_test_helpers_for_forged_component_binding", helper_path
    )
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)

    from cad_agent.live import load_build_evidence
    from cad_agent.mechanical_pilot import (
        bind_simple_shaft_pilot_from_primitive,
        validate_primitive_bound_candidate,
    )
    from dxf_builder_lib.reviewer import review_dxf
    from dxf_builder_lib.tests.dxf_test_support import add_untracked_entity_for_test

    primitive_path = tmp_path / "primitive" / "page_01.json"
    primitive_path.parent.mkdir()
    helper._write_primitive(primitive_path)
    result = bind_simple_shaft_pilot_from_primitive(
        primitive_path, tmp_path / "candidate" / "candidate.dxf"
    )

    extra_handle = add_untracked_entity_for_test(
        result.candidate_path, "INSERT"
    )
    assert extra_handle not in result.build.handle_by_primitive_id.values()

    evidence = json.loads(result.build_evidence_path.read_text(encoding="utf-8"))
    build_evidence = evidence["build_result"]
    build_evidence["component_handle_by_part_id"] = {
        "forged-component": extra_handle
    }
    build_evidence["component_type_by_part_id"] = {
        "forged-component": "frame_beam"
    }
    build_evidence["component_count"] = 1
    build_evidence["written_component_by_part_id"] = {
        "forged-component": {
            "block_name": "UNTRACKED_TEST_COMPONENT",
            "layer": "UNCLASSIFIED",
            "insert": [240.0, 240.0, 0.0],
            "xscale": 1.0,
            "yscale": 1.0,
            "zscale": 1.0,
            "rotation_deg": 0.0,
            "attribs": {"PART_ID": "forged-component"},
        }
    }
    evidence["dxf"]["sha256"] = hashlib.sha256(
        result.candidate_path.read_bytes()
    ).hexdigest()
    result.build_evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    refreshed_build = load_build_evidence(
        result.build_evidence_path, result.candidate_path
    )
    assert review_dxf(refreshed_build).passed is True

    with pytest.raises(ValueError, match="PILOT_PRIMITIVE_BUILD_REVIEW_FAILED"):
        validate_primitive_bound_candidate(
            primitive_path, result.candidate_path, result.build_evidence_path
        )


def test_simple_shaft_pilot_refuses_source_as_candidate(tmp_path: Path) -> None:
    from cad_agent.mechanical_pilot import build_simple_shaft_pilot

    with pytest.raises(ValueError, match="PILOT_CANDIDATE_MUST_DIFFER"):
        build_simple_shaft_pilot(FIXTURE, FIXTURE)


def test_simple_shaft_pilot_refuses_nonempty_candidate_root(tmp_path: Path) -> None:
    from cad_agent.mechanical_pilot import build_simple_shaft_pilot

    (tmp_path / "unrelated.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="PILOT_CANDIDATE_ROOT_NOT_EMPTY"):
        build_simple_shaft_pilot(FIXTURE, tmp_path / "candidate.dxf")


def test_fixture_source_is_canonical_json_and_has_exact_feature_cluster() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "mechanical-shaft-pilot-1.0"
    assert [feature["kind"] for feature in payload["features"]] == [
        "shaft_step",
        "hole_feature",
    ]


def _source_bound_binding() -> dict[str, object]:
    source_sha256 = "1" * 64
    return {
        "source_sha256": source_sha256,
        "page_index": 0,
        "roi_bbox_px": [10, 20, 410, 220],
        "source_render_sha256": "2" * 64,
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": 0.5,
            "origin_px": [10.0, 20.0],
            "method": "manual_override",
            "reference_note": "P1 source dimensions",
            "status": "verified",
            "source_sha256": source_sha256,
        },
        "profile_id": "simple-stepped-shaft-p1-v1",
    }


def _source_bound_proposal() -> dict[str, object]:
    binding = _source_bound_binding()
    return {
        "schema_version": "p1-source-bound-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "dimensions_mm": {
            "shaft_diameter_a": 40.0,
            "shaft_diameter_b": 60.0,
            "segment_length_a": 80.0,
            "segment_length_b": 50.0,
            "hole_diameter": 10.0,
            "hole_axial_position": 95.0,
        },
        "evidence_refs": {},
    }


def _source_fact_bound_evidence() -> dict[str, object]:
    proposal = _source_bound_proposal()
    dimensions = deepcopy(proposal["dimensions_mm"])
    assert isinstance(dimensions, dict)
    fact_specs = (
        ("fact-001", "diameter_a_mm", "shaft_diameter_a"),
        ("fact-002", "diameter_b_mm", "shaft_diameter_b"),
        ("fact-003", "segment_a_mm", "segment_length_a"),
        ("fact-004", "segment_b_mm", "segment_length_b"),
        ("fact-005", "hole_diameter_mm", "hole_diameter"),
        ("fact-006", "hole_position_mm", "hole_axial_position"),
    )
    return {
        "source_sha256": "1" * 64,
        "source_locator": "sources/part-001/item.json",
        "source_identity": "part-001-R1",
        "linked_artifact_sha256": "2" * 64,
        "linked_artifact_locator": "sources/part-001/drawing.json",
        "linked_artifact_identity": "drawing-001-R1",
        "source_custody_sha256": "3" * 64,
        "source_acquisition_binding_sha256": "3" * 64,
        "fact_evidence_sha256": "4" * 64,
        "extraction_profile_id": "source-facts-stepped-shaft-v1",
        "extraction_spec_sha256": "5" * 64,
        "evidence_basis": "declared_source_facts",
        "profile_id": "simple-stepped-shaft-p1-v1",
        "dimensions_mm": dimensions,
        "compile_input": {
            "profile_id": "simple-stepped-shaft-p1-v1",
            "dimensions_mm": deepcopy(dimensions),
        },
        "facts": [
            {
                "fact_id": fact_id,
                "source_key": source_key,
                "quantity": "length",
                "unit": "mm",
                "value": str(dimensions[compile_field]),
                "source_sha256": "1" * 64,
                "source_locator": "sources/part-001/item.json",
                "source_identity": "part-001-R1",
                "linked_artifact_sha256": "2" * 64,
                "linked_artifact_locator": "sources/part-001/drawing.json",
                "linked_artifact_identity": "drawing-001-R1",
            }
            for fact_id, source_key, compile_field in fact_specs
        ],
        "evidence_refs": {
            "source_fact_evidence_sha256": "4" * 64,
            "source_identity": "part-001-R1",
            "linked_artifact_identity": "drawing-001-R1",
        },
    }


def test_primitive_loader_accepts_verified_title_block_scale_calibration(
    tmp_path: Path,
) -> None:
    """The pilot must accept the verified calibration emitted by the source owner."""

    from cad_agent.mechanical_pilot import _load_primitive_document

    source_sha256 = "a" * 64
    primitive_payload = {
        "schema_version": "1.0.0",
        "source_document": {
            "file_name": "page_01.png",
            "page_index": 0,
            "image_width_px": 140,
            "image_height_px": 100,
            "sha256": source_sha256,
        },
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": 1.0,
            "origin_px": [0.0, 0.0],
            "method": "title_block_scale",
            "reference_note": "verified source calibration",
            "status": "verified",
            "source_sha256": source_sha256,
        },
        "primitives": [
            {
                "id": "source-bound-line",
                "type": "line",
                "source": "geometry_opencv",
                "confidence": 1.0,
                "layer": "UNCLASSIFIED",
                "handle": None,
                "trace": {"bbox_px": [0, 0, 1, 1]},
                "validation": {"status": "unreviewed"},
                "geometry": {
                    "start": {"x": 0.0, "y": 0.0},
                    "end": {"x": 100.0, "y": 0.0},
                },
            }
        ],
    }

    primitive_path = tmp_path / "title-block-scale.json"
    primitive_path.write_text(
        json.dumps(primitive_payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    document, loaded_source_sha256 = _load_primitive_document(primitive_path)

    assert loaded_source_sha256 == hashlib.sha256(primitive_path.read_bytes()).hexdigest()
    assert document.calibration.method == "title_block_scale"
    assert document.source_document.sha256 == source_sha256


def test_primitive_loader_accepts_verified_external_geometry_source(
    tmp_path: Path,
) -> None:
    """The pilot must accept source-bound primitives from the source owner."""

    from cad_agent.mechanical_pilot import _load_primitive_document

    source_sha256 = "b" * 64
    primitive_payload = {
        "schema_version": "1.0.0",
        "source_document": {
            "file_name": "page_01.png",
            "page_index": 0,
            "image_width_px": 140,
            "image_height_px": 100,
            "sha256": source_sha256,
        },
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": 1.0,
            "origin_px": [0.0, 0.0],
            "method": "title_block_scale",
            "reference_note": "verified source calibration",
            "status": "verified",
            "source_sha256": source_sha256,
        },
        "primitives": [
            {
                "id": "source-bound-external-line",
                "type": "line",
                "source": "geometry_external_ai",
                "confidence": 1.0,
                "layer": "UNCLASSIFIED",
                "handle": None,
                "trace": {
                    "bbox_px": [0, 0, 1, 1],
                    "verification_request_sha256": "c" * 64,
                    "verification_result_sha256": "d" * 64,
                },
                "validation": {"status": "unreviewed"},
                "geometry": {
                    "start": {"x": 0.0, "y": 0.0},
                    "end": {"x": 100.0, "y": 0.0},
                },
            }
        ],
    }

    primitive_path = tmp_path / "external-geometry.json"
    primitive_path.write_text(
        json.dumps(primitive_payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    document, _ = _load_primitive_document(primitive_path)

    assert document.primitives[0].source == "geometry_external_ai"


def test_primitive_bound_pilot_rejects_fabricated_external_provenance(
    tmp_path: Path,
) -> None:
    """External provenance hashes must be backed by the source verifier."""

    from cad_agent.live import write_build_evidence
    from cad_agent.mechanical_pilot import (
        _load_primitive_document,
        validate_primitive_bound_candidate,
    )
    from dxf_builder_lib.builder import build_dxf

    source_sha256 = "e" * 64
    primitive_payload = {
        "schema_version": "1.0.0",
        "source_document": {
            "file_name": "fabricated-source.png",
            "page_index": 0,
            "image_width_px": 140,
            "image_height_px": 100,
            "sha256": source_sha256,
        },
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": 1.0,
            "origin_px": [0.0, 0.0],
            "method": "title_block_scale",
            "reference_note": "fabricated but schema-valid calibration",
            "status": "verified",
            "source_sha256": source_sha256,
        },
        "primitives": [
            {
                "id": "fabricated-external-line",
                "type": "line",
                "source": "geometry_external_ai",
                "confidence": 1.0,
                "layer": "UNCLASSIFIED",
                "handle": None,
                "trace": {
                    "bbox_px": [0, 0, 100, 1],
                    "verification_request_sha256": "c" * 64,
                    "verification_result_sha256": "d" * 64,
                },
                "validation": {"status": "unreviewed"},
                "geometry": {
                    "start": {"x": 0.0, "y": 0.0},
                    "end": {"x": 100.0, "y": 0.0},
                },
            }
        ],
    }

    primitive_path = tmp_path / "fabricated-external.json"
    primitive_path.write_text(
        json.dumps(primitive_payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    document, _ = _load_primitive_document(primitive_path)

    candidate_path = tmp_path / "candidate" / "candidate.dxf"
    candidate_path.parent.mkdir()
    build = build_dxf(
        document,
        str(candidate_path),
        semantic_doc=None,
        build_components=False,
        build_dimensions=False,
    )
    assert build.entity_count == 1
    assert set(build.handle_by_primitive_id) == {"fabricated-external-line"}

    evidence_path = candidate_path.with_name("build-evidence.json")
    write_build_evidence(evidence_path, build)

    with pytest.raises(
        ValueError, match="PILOT_EXTERNAL_GEOMETRY_PROVENANCE_INVALID"
    ):
        validate_primitive_bound_candidate(
            primitive_path, candidate_path, evidence_path
        )


def test_primitive_bound_validator_accepts_canonical_external_verification(
    tmp_path: Path,
) -> None:
    """Canonical source verification remains an accepted external path."""

    import importlib.util

    helper_path = Path(__file__).with_name(
        "test_external_visual_primitive_ir_admission.py"
    )
    spec = importlib.util.spec_from_file_location(
        "external_visual_admission_helpers_for_mechanical_pilot", helper_path
    )
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)

    from cad_agent.live import write_build_evidence
    from cad_agent.mechanical_pilot import validate_primitive_bound_candidate
    from cad_agent.source_verified_geometry import (
        materialize_verified_external_visual_lines,
    )
    from dxf_builder_lib.builder import build_dxf

    request, result, render_bytes = helper._verified_case()
    document = materialize_verified_external_visual_lines(
        verification_request=request,
        verification_result=result,
        source_render_bytes=render_bytes,
        calibration=helper._calibration(),
        source_file_name="source.png",
        image_width_px=64,
        image_height_px=64,
    )
    primitive_path = tmp_path / "canonical-external.json"
    primitive_path.write_text(
        json.dumps(document.to_dict(), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    candidate_path = tmp_path / "candidate" / "candidate.dxf"
    candidate_path.parent.mkdir()
    build = build_dxf(
        document,
        str(candidate_path),
        semantic_doc=None,
        build_components=False,
        build_dimensions=False,
    )
    evidence_path = candidate_path.with_name("build-evidence.json")
    write_build_evidence(evidence_path, build)

    assert validate_primitive_bound_candidate(
        primitive_path,
        candidate_path,
        evidence_path,
        verification_request=request,
        verification_result=result,
        source_render_bytes=render_bytes,
    ) == (
        hashlib.sha256(primitive_path.read_bytes()).hexdigest(),
        hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
    )


def test_source_bound_external_proposal_compiles_deterministically_without_false_opencv_provenance() -> None:
    import cad_agent.mechanical_pilot as pilot

    compiler = getattr(pilot, "compile_source_bound_simple_shaft_proposal", None)
    assert callable(compiler), "source-bound P1 proposal compiler is not implemented"

    proposal = _source_bound_proposal()
    binding = _source_bound_binding()
    first = compiler(proposal, expected_binding=binding)
    second = compiler(proposal, expected_binding=binding)

    assert first == second
    assert first["schema_version"] == "p1-source-bound-compile-plan-1.0"
    assert first["proposal_source"] == "external_ai"
    assert first["source_binding"] == binding
    assert first["profile_id"] == "simple-stepped-shaft-p1-v1"
    assert first["geometry_contract"]["line_count"] == 8
    assert first["geometry_contract"]["circle_count"] == 1
    assert len(first["geometry_contract"]["lines"]) == 8
    assert first["feature_contract"]["shaft-profile-001"]["kind"] == "shaft_step"
    assert first["feature_contract"]["hole-axial-001"]["kind"] == "hole_feature"
    assert len(first["plan_sha256"]) == 64
    assert "geometry_opencv" not in json.dumps(first, sort_keys=True)


def test_source_fact_bound_compiler_reuses_one_geometry_plan_without_visual_claims() -> None:
    from cad_agent.mechanical_pilot import (
        compile_source_bound_simple_shaft_proposal,
        compile_source_fact_bound_simple_shaft_proposal,
    )

    fact_evidence = _source_fact_bound_evidence()
    source_fact_plan = compile_source_fact_bound_simple_shaft_proposal(
        fact_evidence
    )
    visual_plan = compile_source_bound_simple_shaft_proposal(
        _source_bound_proposal(), expected_binding=_source_bound_binding()
    )

    assert source_fact_plan["geometry_contract"] == visual_plan["geometry_contract"]
    assert source_fact_plan["feature_contract"] == visual_plan["feature_contract"]
    encoded = json.dumps(source_fact_plan, sort_keys=True)
    assert "page_index" not in encoded
    assert "roi_bbox_px" not in encoded
    assert "source_render_sha256" not in encoded
    assert "calibration" not in encoded


@pytest.mark.parametrize(
    "field",
    [
        "fact_evidence_sha256",
        "source_sha256",
        "linked_artifact_sha256",
        "source_custody_sha256",
        "source_acquisition_binding_sha256",
        "profile_id",
        "dimensions_mm",
    ],
)
def test_source_fact_bound_compiler_rejects_mutated_verified_payload(
    field: str,
) -> None:
    from cad_agent.mechanical_pilot import compile_source_fact_bound_simple_shaft_proposal

    payload = _source_fact_bound_evidence()
    if field == "dimensions_mm":
        dimensions = deepcopy(payload["dimensions_mm"])
        assert isinstance(dimensions, dict)
        dimensions["hole_diameter"] = 11.0
        payload[field] = dimensions
    elif field == "profile_id":
        payload[field] = "other-profile"
    else:
        payload[field] = "9" * 64

    with pytest.raises(ValueError):
        compile_source_fact_bound_simple_shaft_proposal(payload)


@pytest.mark.parametrize(
    "field",
    ["source_sha256", "source_render_sha256", "page_index", "roi_bbox_px", "calibration"],
)
def test_source_bound_proposal_refuses_stale_or_foreign_binding(field: str) -> None:
    from cad_agent.mechanical_pilot import compile_source_bound_simple_shaft_proposal

    expected = _source_bound_binding()
    if field == "source_sha256":
        expected["source_sha256"] = "3" * 64
        expected["calibration"]["source_sha256"] = "3" * 64
    elif field == "source_render_sha256":
        expected[field] = "4" * 64
    elif field == "page_index":
        expected[field] = 1
    elif field == "roi_bbox_px":
        expected[field] = [11, 20, 410, 220]
    else:
        expected["calibration"] = deepcopy(expected["calibration"])
        expected["calibration"]["pixel_to_unit_scale"] = 0.6

    with pytest.raises(ValueError, match="PILOT_P1_SOURCE_BINDING_MISMATCH"):
        compile_source_bound_simple_shaft_proposal(
            _source_bound_proposal(), expected_binding=expected
        )


def test_source_bound_proposal_refuses_unsupported_extra_surface() -> None:
    from cad_agent.mechanical_pilot import compile_source_bound_simple_shaft_proposal

    proposal = _source_bound_proposal()
    proposal["thread"] = {"pitch": 1.5}
    with pytest.raises(ValueError, match="PILOT_P1_PROPOSAL_SCHEMA_INVALID"):
        compile_source_bound_simple_shaft_proposal(
            proposal, expected_binding=_source_bound_binding()
        )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("shaft_diameter_a", 0.0, "PILOT_P1_SHAFT_DIAMETER_A_INVALID"),
        ("shaft_diameter_b", 40.0, "PILOT_P1_SHAFT_STEP_REQUIRED"),
        ("hole_axial_position", 999.0, "PILOT_P1_HOLE_POSITION_INVALID"),
        ("hole_diameter", 100.0, "PILOT_P1_HOLE_DIAMETER_INVALID"),
    ],
)
def test_source_bound_proposal_refuses_invalid_or_inconsistent_dimensions(
    field: str, value: float, error: str
) -> None:
    from cad_agent.mechanical_pilot import compile_source_bound_simple_shaft_proposal

    proposal = _source_bound_proposal()
    proposal["dimensions_mm"][field] = value
    with pytest.raises(ValueError, match=error):
        compile_source_bound_simple_shaft_proposal(
            proposal, expected_binding=_source_bound_binding()
        )
