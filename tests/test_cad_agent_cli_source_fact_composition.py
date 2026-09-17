from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any

import pytest

from cad_agent import cli


SOURCE_BYTES = b"source-bound-facts"
LINKED_ARTIFACT_BYTES = b"source-bound-linked-artifact"
SOURCE_SHA256 = hashlib.sha256(SOURCE_BYTES).hexdigest()
LINKED_ARTIFACT_SHA256 = hashlib.sha256(LINKED_ARTIFACT_BYTES).hexdigest()
SOURCE_IDENTITY = "part-001-R1"
LINKED_ARTIFACT_IDENTITY = "drawing-001-R1"
SOURCE_LOCATOR = "sources/part-001/item.json"
LINKED_ARTIFACT_LOCATOR = "sources/part-001/drawing.json"
CUSTODY_DIGEST = "c" * 64
FACT_EVIDENCE_SHA256 = "e" * 64
APPROVED_ROOT_SENTINEL = object()

COMPILE_INPUT = {
    "profile_id": "simple-stepped-shaft-p1-v1",
    "dimensions_mm": {
        "shaft_diameter_a": "12.7000",
        "shaft_diameter_b": "20.6375",
        "segment_length_a": "5.55625",
        "segment_length_b": "49.2125",
        "hole_diameter": "3.1750",
        "hole_axial_position": "51.59375",
    },
}


def _acquisition_context() -> dict[str, object]:
    return {
        "approved_root_id": "ROOT-001",
        "approved_root_revision": "ROOT-REV-1",
        "approved_root": APPROVED_ROOT_SENTINEL,
        "identity_key": b"server-owned-test-key-32-bytes!!",
        "identity_key_revision": "KEY-REV-1",
        "policy_limits": {"max_items": 2},
        "media_limits": {"max_json_depth": 16},
        "source_bundle": {"bundle_id": "BUNDLE-001", "run_id": "RUN-001"},
    }


def _custody() -> dict[str, object]:
    return {"custody": "validated-by-source-integrity"}


def _snapshots(custody: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        SOURCE_IDENTITY: {
            "source_id": SOURCE_IDENTITY,
            "relative_path": SOURCE_LOCATOR,
            "observed_sha256": SOURCE_SHA256,
            "file_object_identity_token": "source-object-token",
            "path_binding_sha256": "a" * 64,
            "source_custody_sha256": CUSTODY_DIGEST,
            "bytes": SOURCE_BYTES,
        },
        LINKED_ARTIFACT_IDENTITY: {
            "source_id": LINKED_ARTIFACT_IDENTITY,
            "relative_path": LINKED_ARTIFACT_LOCATOR,
            "observed_sha256": LINKED_ARTIFACT_SHA256,
            "file_object_identity_token": "linked-object-token",
            "path_binding_sha256": "b" * 64,
            "source_custody_sha256": CUSTODY_DIGEST,
            "bytes": LINKED_ARTIFACT_BYTES,
        },
    }


def _fact_request() -> dict[str, object]:
    return {
        "source_sha256": SOURCE_SHA256,
        "source_locator": SOURCE_LOCATOR,
        "source_identity": SOURCE_IDENTITY,
        "linked_artifact_sha256": LINKED_ARTIFACT_SHA256,
        "linked_artifact_locator": LINKED_ARTIFACT_LOCATOR,
        "linked_artifact_identity": LINKED_ARTIFACT_IDENTITY,
        "extraction_profile_id": "source-facts-stepped-shaft-v1",
        "extraction_spec": {"trusted": True},
        "extraction_spec_sha256": "d" * 64,
        "proposed_facts": [{"fact_id": "fact-001"}],
        "evidence_basis": "declared_source_facts",
    }


def _p1_proposal() -> dict[str, object]:
    source_binding = {
        "source_sha256": SOURCE_SHA256,
        "page_index": 0,
        "roi_bbox_px": [10, 20, 410, 220],
        "source_render_sha256": "f" * 64,
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": 1.0,
            "origin_px": [0.0, 220.0],
            "method": "manual_override",
            "reference_note": "test source-bound calibration",
            "status": "verified",
            "source_sha256": SOURCE_SHA256,
        },
        "profile_id": "simple-stepped-shaft-p1-v1",
    }
    return {
        "schema_version": "p1-source-bound-proposal-1.0",
        "proposal_source": "external_ai",
        **source_binding,
        "dimensions_mm": deepcopy(COMPILE_INPUT["dimensions_mm"]),
        "evidence_refs": {
            "source_fact_evidence_sha256": FACT_EVIDENCE_SHA256,
        },
    }


def _run_composition(
    monkeypatch: pytest.MonkeyPatch,
    *,
    verifier_result: dict[str, object] | None = None,
    proposal: dict[str, object] | None = None,
) -> tuple[dict[str, object], dict[str, Any]]:
    custody = _custody()
    snapshots = _snapshots(custody)
    calls: dict[str, Any] = {"acquire": [], "verify": [], "invoke": []}
    context = _acquisition_context()

    def acquire(**kwargs: object) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
        calls["acquire"].append(kwargs)
        return custody, snapshots

    def verify(**kwargs: object) -> dict[str, object]:
        calls["verify"].append(kwargs)
        assert kwargs["source_bytes"] == SOURCE_BYTES
        assert kwargs["linked_artifact_bytes"] == LINKED_ARTIFACT_BYTES
        assert kwargs["source_custody"] == custody
        assert kwargs["source_acquisition_evidence"] == custody
        replay = kwargs["source_acquisition_replay"]
        assert callable(replay)
        assert replay() == custody
        return verifier_result or {
            "source_sha256": SOURCE_SHA256,
            "source_locator": SOURCE_LOCATOR,
            "source_identity": SOURCE_IDENTITY,
            "linked_artifact_sha256": LINKED_ARTIFACT_SHA256,
            "linked_artifact_locator": LINKED_ARTIFACT_LOCATOR,
            "linked_artifact_identity": LINKED_ARTIFACT_IDENTITY,
            "source_custody": custody,
            "source_acquisition_binding_sha256": CUSTODY_DIGEST,
            "fact_evidence_sha256": FACT_EVIDENCE_SHA256,
            "compile_input": deepcopy(COMPILE_INPUT),
        }

    def invoke(
        skill_id: str,
        *,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        calls["invoke"].append((skill_id, parameters))
        return {"compiled": True, "parameters": deepcopy(parameters)}

    monkeypatch.setattr("cad_agent.source_integrity.inspect_source_bundle_media_bytes", acquire)
    monkeypatch.setattr("cad_agent.source_fusion.verify_source_fact_evidence", verify)
    monkeypatch.setattr("cad_agent.mechanical_skills.invoke_skill", invoke)

    result = cli._compose_source_bound_simple_shaft(
        acquisition_context=context,
        fact_request=_fact_request(),
        proposal=proposal or _p1_proposal(),
    )
    return result, calls


def test_source_fact_composition_uses_one_shot_snapshots_and_existing_compile_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, calls = _run_composition(monkeypatch)

    assert len(calls["acquire"]) == 1
    assert calls["acquire"][0] == _acquisition_context()
    assert len(calls["verify"]) == 1
    assert len(calls["invoke"]) == 1
    skill_id, parameters = calls["invoke"][0]
    assert skill_id == "geometry.simple_shaft_pilot"
    assert parameters["proposal"]["dimensions_mm"] == COMPILE_INPUT["dimensions_mm"]
    assert parameters["proposal"]["profile_id"] == COMPILE_INPUT["profile_id"]
    assert result["compiled"] is True


@pytest.mark.parametrize(
    "field",
    ["source_custody", "source_sha256", "fact_evidence_sha256"],
)
def test_source_fact_composition_rejects_substituted_verifier_output(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    with pytest.raises(ValueError, match="SOURCE_FACT_COMPOSITION_BINDING"):
        _run_composition(
            monkeypatch,
            verifier_result={
                "source_sha256": "9" * 64 if field == "source_sha256" else SOURCE_SHA256,
                "source_locator": SOURCE_LOCATOR,
                "source_identity": SOURCE_IDENTITY,
                "linked_artifact_sha256": LINKED_ARTIFACT_SHA256,
                "linked_artifact_locator": LINKED_ARTIFACT_LOCATOR,
                "linked_artifact_identity": LINKED_ARTIFACT_IDENTITY,
                "source_custody": {"foreign": True} if field == "source_custody" else _custody(),
                "source_acquisition_binding_sha256": CUSTODY_DIGEST,
                "fact_evidence_sha256": "9" * 64 if field == "fact_evidence_sha256" else FACT_EVIDENCE_SHA256,
                "compile_input": deepcopy(COMPILE_INPUT),
            },
        )


@pytest.mark.parametrize(
    "field",
    ["page_index", "roi_bbox_px", "source_render_sha256", "calibration"],
)
def test_source_fact_composition_rejects_unanchored_visual_binding(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    proposal = _p1_proposal()
    if field == "page_index":
        proposal[field] = 1
    elif field == "roi_bbox_px":
        proposal[field] = [11, 20, 410, 220]
    elif field == "source_render_sha256":
        proposal[field] = "9" * 64
    else:
        calibration = deepcopy(proposal["calibration"])
        assert isinstance(calibration, dict)
        calibration["pixel_to_unit_scale"] = 2.0
        proposal["calibration"] = calibration

    with pytest.raises(ValueError, match="SOURCE_FACT_COMPOSITION_BINDING"):
        _run_composition(monkeypatch, proposal=proposal)
