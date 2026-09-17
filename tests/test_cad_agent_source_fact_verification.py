from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any

import pytest

from cad_agent import source_fusion
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_integrity import (
    R1C_NUMERIC_POLICY_VERSION,
    SOURCE_CUSTODY_SCHEMA_VERSION,
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


def _trusted_source_custody() -> dict[str, object]:
    return validate_source_custody(
        {
            "schema_version": SOURCE_CUSTODY_SCHEMA_VERSION,
            "bundle_id": "BUNDLE-SOURCE-001",
            "run_id": "RUN-SOURCE-001",
            "source_bundle_sha256": "a" * 64,
            "approved_root_id": "ROOT-SOURCE-001",
            "approved_root_revision": "ROOT-REV-1",
            "approved_root_configuration_sha256": "b" * 64,
            "identity_scheme": "HMAC-SHA-256",
            "identity_scheme_version": "r1c-file-identity-v1",
            "identity_key_revision": "KEY-REV-1",
            "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
            "status": "READY",
            "eligible_count": 2,
            "blocking_count": 0,
            "items": [
                {
                    "source_id": SOURCE_IDENTITY,
                    "kind": "ENGINEER_RECORD",
                    "role": "DECISION",
                    "relative_path": SOURCE_LOCATOR,
                    "declared_sha256": SOURCE_SHA256,
                    "observed_sha256": SOURCE_SHA256,
                    "size_bytes": len(SOURCE_BYTES),
                    "declared_media_type": "application/json",
                    "observed_media_type": "application/json",
                    "media_metadata": {
                        "format": "JSON",
                        "root_type": "object",
                        "max_depth": 1,
                        "container_count": 1,
                        "object_key_count": 7,
                        "array_item_count": 0,
                        "max_string_chars": 11,
                        "number_count": 0,
                    },
                    "page_ids": [],
                    "region_ids": [],
                    "file_object_identity_token": "1" * 64,
                    "path_binding_sha256": "2" * 64,
                    "identity_scheme": "HMAC-SHA-256",
                    "identity_scheme_version": "r1c-file-identity-v1",
                    "identity_key_revision": "KEY-REV-1",
                    "approved_root_revision": "ROOT-REV-1",
                    "alias_group_id": None,
                    "custody_state": "VERIFIED",
                    "blocking_reason_code": None,
                },
                {
                    "source_id": LINKED_ARTIFACT_IDENTITY,
                    "kind": "ENGINEER_RECORD",
                    "role": "DECISION",
                    "relative_path": LINKED_ARTIFACT_LOCATOR,
                    "declared_sha256": LINKED_ARTIFACT_SHA256,
                    "observed_sha256": LINKED_ARTIFACT_SHA256,
                    "size_bytes": len(LINKED_ARTIFACT_BYTES),
                    "declared_media_type": "application/json",
                    "observed_media_type": "application/json",
                    "media_metadata": {
                        "format": "JSON",
                        "root_type": "object",
                        "max_depth": 1,
                        "container_count": 1,
                        "object_key_count": 2,
                        "array_item_count": 0,
                        "max_string_chars": 14,
                        "number_count": 0,
                    },
                    "page_ids": [],
                    "region_ids": [],
                    "file_object_identity_token": "3" * 64,
                    "path_binding_sha256": "4" * 64,
                    "identity_scheme": "HMAC-SHA-256",
                    "identity_scheme_version": "r1c-file-identity-v1",
                    "identity_key_revision": "KEY-REV-1",
                    "approved_root_revision": "ROOT-REV-1",
                    "alias_group_id": None,
                    "custody_state": "VERIFIED",
                    "blocking_reason_code": None,
                },
            ],
            "alias_groups": [],
        }
    )


TRUSTED_SOURCE_CUSTODY = _trusted_source_custody()

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


def _base_call() -> dict[str, Any]:
    return {
        "source_bytes": SOURCE_BYTES,
        "source_sha256": SOURCE_SHA256,
        "source_locator": SOURCE_LOCATOR,
        "source_identity": SOURCE_IDENTITY,
        "linked_artifact_bytes": LINKED_ARTIFACT_BYTES,
        "linked_artifact_sha256": LINKED_ARTIFACT_SHA256,
        "linked_artifact_locator": LINKED_ARTIFACT_LOCATOR,
        "linked_artifact_identity": LINKED_ARTIFACT_IDENTITY,
        "source_custody": deepcopy(TRUSTED_SOURCE_CUSTODY),
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


def test_generic_source_fact_verifier_reproduces_bound_facts_and_compile_input() -> None:
    result = _verifier()(**_base_call())

    assert result["source_sha256"] == SOURCE_SHA256
    assert result["linked_artifact_sha256"] == LINKED_ARTIFACT_SHA256
    assert result["source_custody"] == TRUSTED_SOURCE_CUSTODY
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
        ("source_identity", "SOURCE_IDENTITY"),
        ("linked_artifact_hash", "LINKED_ARTIFACT_HASH"),
        ("linked_artifact_replacement", "LINKED_ARTIFACT_HASH"),
        ("linked_artifact_identity", "LINKED_ARTIFACT_IDENTITY"),
        ("source_locator", "SOURCE_LOCATOR"),
        ("linked_artifact_locator", "LINKED_ARTIFACT_LOCATOR"),
        ("extraction_spec", "EXTRACTION_PROFILE_BINDING"),
        ("raster_basis", "EVIDENCE_BASIS"),
    ],
)
def test_generic_source_fact_verifier_rejects_unbound_or_false_evidence(
    mutation: str, error_code: str
) -> None:
    call = _base_call()
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
