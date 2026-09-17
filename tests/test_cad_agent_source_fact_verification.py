from __future__ import annotations

from copy import deepcopy
from functools import partial
import hashlib
from pathlib import Path
from typing import Any

import pytest

from cad_agent import source_fusion
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_bundle import build_source_bundle
from cad_agent.source_integrity import (
    inspect_source_bundle_media,
    source_custody_sha256,
    validate_source_custody,
)


SOURCE_BYTES = (
    b'{"source_identity":"part-001-R1","diameter_a_mm":"12.7000",'
    b'"diameter_b_mm":"20.6375","segment_a_mm":"5.55625",'
    b'"segment_b_mm":"49.2125","hole_diameter_mm":"3.1750",'
    b'"hole_position_mm":"51.59375"}\n'
)
LINKED_ARTIFACT_BYTES = (
    b'{"linked_identity":"drawing-001-R1","profile":"stepped_shaft"}\n'
)
SOURCE_SHA256 = hashlib.sha256(SOURCE_BYTES).hexdigest()
LINKED_ARTIFACT_SHA256 = hashlib.sha256(LINKED_ARTIFACT_BYTES).hexdigest()
SOURCE_IDENTITY = "part-001-R1"
LINKED_ARTIFACT_IDENTITY = "drawing-001-R1"
SOURCE_LOCATOR = "sources/part-001/item.json"
LINKED_ARTIFACT_LOCATOR = "sources/part-001/drawing.json"
EXTRACTION_PROFILE_ID = "source-facts-stepped-shaft-v1"


_CUSTODY_POLICY_LIMITS = {
    "max_items": 10,
    "max_total_bytes": 1024 * 1024,
    "max_file_bytes": 1024 * 1024,
    "hash_chunk_size": 3,
    "max_final_path_chars": 32768,
}
_CUSTODY_MEDIA_LIMITS = {
    "max_image_pixels": 16_000_000,
    "max_pdf_pages": 64,
    "max_cad_header_bytes": 4096,
    "max_json_depth": 16,
    "max_json_containers": 4096,
    "max_json_string_chars": 65_536,
    "max_json_key_chars": 1024,
    "max_json_number_chars": 128,
}
_CUSTODY_IDENTITY_KEY = b"server-owned-test-key-32-bytes!!"


@pytest.fixture
def source_acquisition_context(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "approved-source-root"
    for locator, data in (
        (SOURCE_LOCATOR, SOURCE_BYTES),
        (LINKED_ARTIFACT_LOCATOR, LINKED_ARTIFACT_BYTES),
    ):
        path = root / locator
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    source_bundle = build_source_bundle(
        bundle_id="BUNDLE-SOURCE-001",
        run_id="RUN-SOURCE-001",
        created_at_utc="2026-09-17T02:00:00Z",
        items=[
            {
                "source_id": SOURCE_IDENTITY,
                "kind": "ENGINEER_RECORD",
                "role": "DECISION",
                "relative_path": SOURCE_LOCATOR,
                "sha256": SOURCE_SHA256,
                "media_type": "application/json",
                "page_ids": [],
                "region_ids": [],
                "captured_at_utc": "2026-09-17T02:00:00Z",
                "quality": {"distortion": "NONE", "legibility": "GOOD"},
            },
            {
                "source_id": LINKED_ARTIFACT_IDENTITY,
                "kind": "ENGINEER_RECORD",
                "role": "DECISION",
                "relative_path": LINKED_ARTIFACT_LOCATOR,
                "sha256": LINKED_ARTIFACT_SHA256,
                "media_type": "application/json",
                "page_ids": [],
                "region_ids": [],
                "captured_at_utc": "2026-09-17T02:00:00Z",
                "quality": {"distortion": "NONE", "legibility": "GOOD"},
            },
        ],
    )
    return {
        "approved_root_id": "ROOT-SOURCE-001",
        "approved_root_revision": "ROOT-REV-1",
        "approved_root": root,
        "identity_key": _CUSTODY_IDENTITY_KEY,
        "identity_key_revision": "KEY-REV-1",
        "policy_limits": dict(_CUSTODY_POLICY_LIMITS),
        "media_limits": dict(_CUSTODY_MEDIA_LIMITS),
        "source_bundle": source_bundle,
    }


@pytest.fixture
def acquired_source_custody(
    source_acquisition_context: dict[str, object],
) -> dict[str, object]:
    return inspect_source_bundle_media(**source_acquisition_context)


@pytest.fixture
def source_acquisition_replay(
    source_acquisition_context: dict[str, object],
) -> Any:
    def replay() -> dict[str, object]:
        return inspect_source_bundle_media(**source_acquisition_context)

    return replay


@pytest.fixture
def source_acquisition_binding_sha256(
    acquired_source_custody: dict[str, object],
) -> str:
    return source_custody_sha256(acquired_source_custody)


EXTRACTION_SPEC = {
    "schema_version": "source-fact-extraction-spec-1.0",
    "profile_id": EXTRACTION_PROFILE_ID,
    "source_encoding": "utf-8",
    "required_source_identity": SOURCE_IDENTITY,
    "required_source_locator": SOURCE_LOCATOR,
    "required_linked_artifact_identity": LINKED_ARTIFACT_IDENTITY,
    "required_linked_artifact_locator": LINKED_ARTIFACT_LOCATOR,
    "facts": [
        {
            "fact_id": "fact-001",
            "source_key": "diameter_a_mm",
            "quantity": "length",
            "unit": "mm",
            "compile_field": "shaft_diameter_a",
        },
        {
            "fact_id": "fact-002",
            "source_key": "diameter_b_mm",
            "quantity": "length",
            "unit": "mm",
            "compile_field": "shaft_diameter_b",
        },
        {
            "fact_id": "fact-003",
            "source_key": "segment_a_mm",
            "quantity": "length",
            "unit": "mm",
            "compile_field": "segment_length_a",
        },
        {
            "fact_id": "fact-004",
            "source_key": "segment_b_mm",
            "quantity": "length",
            "unit": "mm",
            "compile_field": "segment_length_b",
        },
        {
            "fact_id": "fact-005",
            "source_key": "hole_diameter_mm",
            "quantity": "length",
            "unit": "mm",
            "compile_field": "hole_diameter",
        },
        {
            "fact_id": "fact-006",
            "source_key": "hole_position_mm",
            "quantity": "length",
            "unit": "mm",
            "compile_field": "hole_axial_position",
        },
    ],
}
EXTRACTION_SPEC_SHA256 = canonical_json_sha256(EXTRACTION_SPEC)
TRUSTED_EXTRACTION_SPEC_SHA256 = EXTRACTION_SPEC_SHA256

EXPECTED_DIMENSIONS = {
    "shaft_diameter_a": "12.7000",
    "shaft_diameter_b": "20.6375",
    "segment_length_a": "5.55625",
    "segment_length_b": "49.2125",
    "hole_diameter": "3.1750",
    "hole_axial_position": "51.59375",
}


def _expected_facts() -> list[dict[str, str]]:
    facts = []
    for record in EXTRACTION_SPEC["facts"]:
        facts.append(
            {
                "fact_id": record["fact_id"],
                "source_key": record["source_key"],
                "quantity": record["quantity"],
                "unit": record["unit"],
                "value": EXPECTED_DIMENSIONS[record["compile_field"]],
                "source_sha256": SOURCE_SHA256,
                "source_locator": SOURCE_LOCATOR,
                "source_identity": SOURCE_IDENTITY,
                "linked_artifact_sha256": LINKED_ARTIFACT_SHA256,
                "linked_artifact_locator": LINKED_ARTIFACT_LOCATOR,
                "linked_artifact_identity": LINKED_ARTIFACT_IDENTITY,
            }
        )
    return facts


def _base_call(
    source_custody: dict[str, object],
    acquisition_binding_sha256: str,
) -> dict[str, Any]:
    return {
        "source_bytes": SOURCE_BYTES,
        "source_sha256": SOURCE_SHA256,
        "source_locator": SOURCE_LOCATOR,
        "source_identity": SOURCE_IDENTITY,
        "linked_artifact_bytes": LINKED_ARTIFACT_BYTES,
        "linked_artifact_sha256": LINKED_ARTIFACT_SHA256,
        "linked_artifact_locator": LINKED_ARTIFACT_LOCATOR,
        "linked_artifact_identity": LINKED_ARTIFACT_IDENTITY,
        "source_custody": deepcopy(source_custody),
        "source_acquisition_evidence": source_custody,
        "source_acquisition_binding_sha256": acquisition_binding_sha256,
        "extraction_profile_id": EXTRACTION_PROFILE_ID,
        "extraction_spec": deepcopy(EXTRACTION_SPEC),
        "extraction_spec_sha256": TRUSTED_EXTRACTION_SPEC_SHA256,
        "proposed_facts": _expected_facts(),
        "evidence_basis": "declared_source_facts",
    }


def _verifier(acquisition_replay: Any) -> Any:
    verifier = getattr(source_fusion, "verify_source_fact_evidence", None)
    assert callable(verifier), "MISSING_GENERIC_SOURCE_FACT_VERIFIER"
    return partial(verifier, source_acquisition_replay=acquisition_replay)


def test_generic_source_fact_verifier_reproduces_bound_facts_and_compile_input(
    acquired_source_custody: dict[str, object],
    source_acquisition_binding_sha256: str,
    source_acquisition_replay: Any,
) -> None:
    result = _verifier(source_acquisition_replay)(
        **_base_call(
            acquired_source_custody,
            source_acquisition_binding_sha256,
        )
    )

    assert result["source_sha256"] == SOURCE_SHA256
    assert result["linked_artifact_sha256"] == LINKED_ARTIFACT_SHA256
    assert result["source_custody"] == acquired_source_custody
    assert result["source_locator"] == SOURCE_LOCATOR
    assert result["source_identity"] == SOURCE_IDENTITY
    assert result["extraction_profile_id"] == EXTRACTION_PROFILE_ID
    assert result["extraction_spec_sha256"] == TRUSTED_EXTRACTION_SPEC_SHA256
    assert result["evidence_basis"] == "declared_source_facts"
    assert result["facts"] == _expected_facts()
    assert result["compile_input"] == {
        "profile_id": "simple-stepped-shaft-p1-v1",
        "dimensions_mm": EXPECTED_DIMENSIONS,
    }
    assert isinstance(result["fact_evidence_sha256"], str)
    assert len(result["fact_evidence_sha256"]) == 64


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        ("caller_fact", "FACT_REPRODUCTION"),
        ("source_hash", "SOURCE_HASH"),
        ("source_replacement", "SOURCE_HASH"),
        ("source_custody_replacement", "SOURCE_CUSTODY_BINDING"),
        ("acquisition_evidence_replacement", "SOURCE_ACQUISITION_BINDING"),
        ("source_identity", "SOURCE_IDENTITY"),
        ("linked_artifact_hash", "LINKED_ARTIFACT_HASH"),
        ("linked_artifact_replacement", "LINKED_ARTIFACT_HASH"),
        ("linked_artifact_custody_replacement", "SOURCE_CUSTODY_BINDING"),
        ("linked_artifact_identity", "LINKED_ARTIFACT_IDENTITY"),
        ("source_locator", "SOURCE_LOCATOR"),
        ("linked_artifact_locator", "LINKED_ARTIFACT_LOCATOR"),
        ("extraction_spec", "EXTRACTION_PROFILE_BINDING"),
        ("raster_basis", "EVIDENCE_BASIS"),
    ],
)
def test_generic_source_fact_verifier_rejects_unbound_or_false_evidence(
    mutation: str,
    error_code: str,
    acquired_source_custody: dict[str, object],
    source_acquisition_binding_sha256: str,
    source_acquisition_replay: Any,
) -> None:
    call = _base_call(
        acquired_source_custody,
        source_acquisition_binding_sha256,
    )
    if mutation == "caller_fact":
        call["proposed_facts"][0]["value"] = "999.0000"
    elif mutation == "source_hash":
        call["source_bytes"] = SOURCE_BYTES + b"drift\n"
    elif mutation == "source_replacement":
        replacement = SOURCE_BYTES.replace(b"12.7000", b"13.7000")
        call["source_bytes"] = replacement
        call["source_sha256"] = hashlib.sha256(replacement).hexdigest()
        call["proposed_facts"][0]["value"] = "13.7000"
        for fact in call["proposed_facts"]:
            fact["source_sha256"] = call["source_sha256"]
    elif mutation == "source_custody_replacement":
        replacement = SOURCE_BYTES.replace(b"12.7000", b"13.7000")
        call["source_bytes"] = replacement
        call["source_sha256"] = hashlib.sha256(replacement).hexdigest()
        call["proposed_facts"][0]["value"] = "13.7000"
        for fact in call["proposed_facts"]:
            fact["source_sha256"] = call["source_sha256"]
        custody_item = next(
            item
            for item in call["source_custody"]["items"]
            if item["source_id"] == SOURCE_IDENTITY
        )
        custody_item["declared_sha256"] = call["source_sha256"]
        custody_item["observed_sha256"] = call["source_sha256"]
        validate_source_custody(call["source_custody"])
    elif mutation == "acquisition_evidence_replacement":
        replacement = SOURCE_BYTES.replace(b"12.7000", b"13.7000")
        call["source_bytes"] = replacement
        call["source_sha256"] = hashlib.sha256(replacement).hexdigest()
        call["proposed_facts"][0]["value"] = "13.7000"
        for fact in call["proposed_facts"]:
            fact["source_sha256"] = call["source_sha256"]
        custody_item = next(
            item
            for item in call["source_custody"]["items"]
            if item["source_id"] == SOURCE_IDENTITY
        )
        custody_item["declared_sha256"] = call["source_sha256"]
        custody_item["observed_sha256"] = call["source_sha256"]
        validate_source_custody(call["source_custody"])
        call["source_acquisition_evidence"] = deepcopy(call["source_custody"])
        validate_source_custody(call["source_acquisition_evidence"])
        forged_binding = source_custody_sha256(call["source_acquisition_evidence"])
        assert forged_binding != call["source_acquisition_binding_sha256"]
        call["source_acquisition_binding_sha256"] = forged_binding
    elif mutation == "source_identity":
        call["source_identity"] = "part-001-R2"
    elif mutation == "linked_artifact_hash":
        call["linked_artifact_bytes"] = LINKED_ARTIFACT_BYTES + b"drift\n"
    elif mutation == "linked_artifact_replacement":
        replacement = LINKED_ARTIFACT_BYTES.replace(b"stepped_shaft", b"other_profile")
        call["linked_artifact_bytes"] = replacement
        call["linked_artifact_sha256"] = hashlib.sha256(replacement).hexdigest()
        for fact in call["proposed_facts"]:
            fact["linked_artifact_sha256"] = call["linked_artifact_sha256"]
    elif mutation == "linked_artifact_custody_replacement":
        replacement = LINKED_ARTIFACT_BYTES.replace(b"stepped_shaft", b"other_profile")
        call["linked_artifact_bytes"] = replacement
        call["linked_artifact_sha256"] = hashlib.sha256(replacement).hexdigest()
        for fact in call["proposed_facts"]:
            fact["linked_artifact_sha256"] = call["linked_artifact_sha256"]
        custody_item = next(
            item
            for item in call["source_custody"]["items"]
            if item["source_id"] == LINKED_ARTIFACT_IDENTITY
        )
        custody_item["declared_sha256"] = call["linked_artifact_sha256"]
        custody_item["observed_sha256"] = call["linked_artifact_sha256"]
        validate_source_custody(call["source_custody"])
    elif mutation == "linked_artifact_identity":
        call["linked_artifact_identity"] = "drawing-001-R2"
    elif mutation == "source_locator":
        call["source_locator"] = "sources/part-002/item.json"
    elif mutation == "linked_artifact_locator":
        call["linked_artifact_locator"] = "sources/part-002/drawing.json"
    elif mutation == "extraction_spec":
        call["extraction_spec"]["facts"][0]["compile_field"] = "segment_length_b"
        call["extraction_spec_sha256"] = canonical_json_sha256(
            call["extraction_spec"]
        )
    else:
        call["evidence_basis"] = "raster_derived"

    with pytest.raises(ValueError, match=error_code):
        _verifier(source_acquisition_replay)(**call)


def test_verified_source_fact_handoff_delegates_to_existing_p1_skill_and_rejects_drift(
    acquired_source_custody: dict[str, object],
    source_acquisition_binding_sha256: str,
    source_acquisition_replay: Any,
) -> None:
    """Verified facts must remain bound when handed to the existing P1 owner."""

    from importlib import import_module

    skills = import_module("cad_agent.mechanical_skills")
    handoff = getattr(skills, "invoke_verified_source_fact_evidence", None)
    assert callable(handoff), "MISSING_SOURCE_FACT_P1_HANDOFF"

    verified = _verifier(source_acquisition_replay)(
        **_base_call(
            acquired_source_custody,
            source_acquisition_binding_sha256,
        )
    )

    def trusted_replay() -> dict[str, object]:
        return _verifier(source_acquisition_replay)(
            **_base_call(
                acquired_source_custody,
                source_acquisition_binding_sha256,
            )
        )

    binding = {
        "source_sha256": verified["source_sha256"],
        "page_index": 0,
        "roi_bbox_px": [10, 20, 410, 220],
        "source_render_sha256": "b" * 64,
        "calibration": {
            "unit": "mm",
            "pixel_to_unit_scale": 0.5,
            "origin_px": [10.0, 20.0],
            "method": "manual_override",
            "reference_note": "verified source facts",
            "status": "verified",
            "source_sha256": verified["source_sha256"],
        },
        "profile_id": "simple-stepped-shaft-p1-v1",
    }
    proposal = {
        "schema_version": "p1-source-bound-proposal-1.0",
        "proposal_source": "external_ai",
        **binding,
        "dimensions_mm": deepcopy(verified["compile_input"]["dimensions_mm"]),
        "evidence_refs": {
            "source_fact_evidence_sha256": verified["fact_evidence_sha256"],
            "source_custody_sha256": source_acquisition_binding_sha256,
            "source_sha256": verified["source_sha256"],
            "source_locator": verified["source_locator"],
            "source_identity": verified["source_identity"],
            "linked_artifact_sha256": verified["linked_artifact_sha256"],
            "linked_artifact_locator": verified["linked_artifact_locator"],
            "linked_artifact_identity": verified["linked_artifact_identity"],
        },
    }

    plan = handoff(
        verified_source_fact_evidence=verified,
        proposal=proposal,
        expected_binding=deepcopy(binding),
        source_fact_verification_replay=trusted_replay,
    )
    assert plan["dimensions_mm"] == {
        key: float(value)
        for key, value in verified["compile_input"]["dimensions_mm"].items()
    }
    assert plan["evidence_refs"] == proposal["evidence_refs"]
    assert plan["geometry_contract"]["line_count"] == 8
    assert plan["geometry_contract"]["circle_count"] == 1
    assert plan["feature_contract"]["shaft-profile-001"]["kind"] == "shaft_step"
    assert plan["feature_contract"]["hole-axial-001"]["kind"] == "hole_feature"

    substitutions = []
    dimensions = deepcopy(proposal)
    dimensions["dimensions_mm"]["shaft_diameter_a"] = "13.7000"
    substitutions.append((dimensions, deepcopy(binding)))
    fact_hash = deepcopy(proposal)
    fact_hash["evidence_refs"]["source_fact_evidence_sha256"] = "0" * 64
    substitutions.append((fact_hash, deepcopy(binding)))
    source_binding = deepcopy(proposal)
    source_binding["source_render_sha256"] = "c" * 64
    substitutions.append((source_binding, deepcopy(binding)))
    expected_binding = deepcopy(binding)
    expected_binding["source_render_sha256"] = "d" * 64
    substitutions.append((deepcopy(proposal), expected_binding))

    for substituted_proposal, substituted_expected in substitutions:
        with pytest.raises((ValueError, skills.MechanicalSkillError)):
            handoff(
                verified_source_fact_evidence=verified,
                proposal=substituted_proposal,
                expected_binding=substituted_expected,
                source_fact_verification_replay=trusted_replay,
            )

    forged = deepcopy(verified)
    forged["source_identity"] = "forged-source"
    forged["source_locator"] = "forged/source.json"
    forged["facts"][0]["source_identity"] = "forged-source"
    forged["facts"][0]["source_locator"] = "forged/source.json"
    forged["facts"][0]["value"] = "99.0000"
    forged["compile_input"]["dimensions_mm"]["shaft_diameter_a"] = "99.0000"
    forged["fact_evidence_sha256"] = canonical_json_sha256(
        {
            "schema_version": source_fusion.SOURCE_FUSION_SCHEMA_VERSION,
            "source_sha256": forged["source_sha256"],
            "source_locator": forged["source_locator"],
            "source_identity": forged["source_identity"],
            "linked_artifact_sha256": forged["linked_artifact_sha256"],
            "linked_artifact_locator": forged["linked_artifact_locator"],
            "linked_artifact_identity": forged["linked_artifact_identity"],
            "source_custody_sha256": source_acquisition_binding_sha256,
            "extraction_profile_id": forged["extraction_profile_id"],
            "extraction_spec_sha256": forged["extraction_spec_sha256"],
            "evidence_basis": forged["evidence_basis"],
            "facts": forged["facts"],
            "compile_input": forged["compile_input"],
        }
    )
    forged_proposal = deepcopy(proposal)
    forged_proposal["dimensions_mm"] = deepcopy(
        forged["compile_input"]["dimensions_mm"]
    )
    forged_proposal["evidence_refs"]["source_fact_evidence_sha256"] = (
        forged["fact_evidence_sha256"]
    )
    forged_proposal["evidence_refs"]["source_locator"] = forged["source_locator"]
    forged_proposal["evidence_refs"]["source_identity"] = forged["source_identity"]
    with pytest.raises((ValueError, skills.MechanicalSkillError)):
        handoff(
            verified_source_fact_evidence=forged,
            proposal=forged_proposal,
            expected_binding=deepcopy(binding),
            source_fact_verification_replay=trusted_replay,
        )

    def fake_replay() -> dict[str, object]:
        return deepcopy(forged)

    with pytest.raises((ValueError, skills.MechanicalSkillError)):
        handoff(
            verified_source_fact_evidence=forged,
            proposal=forged_proposal,
            expected_binding=deepcopy(binding),
            source_fact_verification_replay=fake_replay,
        )
