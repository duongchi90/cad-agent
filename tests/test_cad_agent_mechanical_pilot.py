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
