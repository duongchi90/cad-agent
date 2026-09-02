from __future__ import annotations

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
