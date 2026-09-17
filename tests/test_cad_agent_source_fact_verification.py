from __future__ import annotations

from copy import deepcopy
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
def acquired_source_custody(tmp_path: Path) -> dict[str, object]:
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
    return inspect_source_bundle_media(
        approved_root_id="ROOT-SOURCE-001",
        approved_root_revision="ROOT-REV-1",
        approved_root=root,
        identity_key=_CUSTODY_IDENTITY_KEY,
        identity_key_revision="KEY-REV-1",
        policy_limits=dict(_CUSTODY_POLICY_LIMITS),
        media_limits=dict(_CUSTODY_MEDIA_LIMITS),
        source_bundle=source_bundle,
    )


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


def _verifier() -> Any:
    verifier = getattr(source_fusion, "verify_source_fact_evidence", None)
    assert callable(verifier), "MISSING_GENERIC_SOURCE_FACT_VERIFIER"
    return verifier


def test_generic_source_fact_verifier_reproduces_bound_facts_and_compile_input(
    acquired_source_custody: dict[str, object],
    source_acquisition_binding_sha256: str,
) -> None:
    result = _verifier()(
        **_base_call(acquired_source_custody, source_acquisition_binding_sha256)
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
) -> None:
    call = _base_call(acquired_source_custody, source_acquisition_binding_sha256)
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
        assert (
            source_custody_sha256(call["source_acquisition_evidence"])
            != call["source_acquisition_binding_sha256"]
        )
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
        _verifier()(**call)
