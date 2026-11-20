from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_marine_contracts_reject_unapproved_promotion_and_tampered_hashes() -> None:
    from cad_agent.marine_knowledge.contracts import (
        MarineKnowledgeError,
        validate_check_result,
        validate_source_manifest,
    )
    from cad_agent.marine_knowledge.manifest import get_marine_source_manifest

    manifest = get_marine_source_manifest()
    assert manifest["schema_version"] == "marine-source-manifest-1.0"
    assert manifest["status"] == "CANDIDATE_UNAPPROVED"
    # No binary books or private DWGs may be marked committable
    for src in manifest["sources"]:
        if src["document_kind"] in {"REGULATION", "TEXTBOOK", "ARCHIVE_BUNDLE", "PRIVATE_SAMPLE"}:
            assert src["commit_prohibited"] is True
        if "VB" in src["title"] or "HỌC PHÍ" in src["title"]:
            assert src["usage_status"] == "EXCLUDED_NON_MARINE"

    tampered = deepcopy(manifest)
    tampered["sources"][0]["title"] = "tampered"
    with pytest.raises(MarineKnowledgeError, match="MANIFEST_HASH_MISMATCH"):
        validate_source_manifest(tampered)

    # Check result must never claim CAD mutation or regulatory compliance approval
    bad_res = {
        "schema_version": "marine-check-result-1.0",
        "skill_id": "marine.scope_check",
        "pack_id": "MARINE_KNOWLEDGE_V0",
        "pack_sha256": "a" * 64,
        "pack_status": "CANDIDATE_UNAPPROVED",
        "cad_mutation": True,
        "regulatory_compliance_proven": False,
        "status": "PASS",
        "summary": "ok",
        "observed_scope": {},
        "applicable_regulation_scope": {},
        "partial_package": True,
        "findings": [],
        "checks_executed": ["scope_gate"],
        "checks_not_executed": [],
        "limitations": ["read_only"],
        "proposal_only_actions": [],
    }
    with pytest.raises(MarineKnowledgeError):
        validate_check_result(bad_res)

    bad_res["cad_mutation"] = False
    bad_res["regulatory_compliance_proven"] = True
    with pytest.raises(MarineKnowledgeError):
        validate_check_result(bad_res)

    bad_res["regulatory_compliance_proven"] = False
    bad_res["pack_status"] = "APPROVED"  # forbidden unapproved escalation
    with pytest.raises(MarineKnowledgeError):
        validate_check_result(bad_res)

    bad_res["pack_status"] = "CANDIDATE_UNAPPROVED"
    validated = validate_check_result(bad_res)
    assert validated["cad_mutation"] is False


def test_manifest_excludes_private_sample_and_archive_identity_records() -> None:
    from cad_agent.marine_knowledge.manifest import get_marine_source_manifest

    manifest = get_marine_source_manifest()
    assert not any(
        src["document_kind"] in {"PRIVATE_SAMPLE", "ARCHIVE_BUNDLE"}
        for src in manifest["sources"]
    )


def test_citation_verification_rejects_missing_stale_and_out_of_range_pages() -> None:
    from cad_agent.marine_knowledge.contracts import MarineKnowledgeError, verify_source_citation
    from cad_agent.marine_knowledge.manifest import get_marine_source_manifest

    manifest = get_marine_source_manifest()
    qcvn_sha = next(s["sha256"] for s in manifest["sources"] if s["source_id"] == "QCVN_72_2025_BGTVT")

    good = {
        "source_id": "QCVN_72_2025_BGTVT",
        "source_sha256": qcvn_sha,
        "clause": "Mục I, Chương 1, 1.1.1",
        "pdf_page": [3],
        "reg_page": [19],
    }
    assert verify_source_citation(good, manifest)["source_sha256"] == qcvn_sha

    with pytest.raises(MarineKnowledgeError, match="CITATION_CLAUSE_MISSING"):
        verify_source_citation({**good, "clause": ""}, manifest)
    with pytest.raises(MarineKnowledgeError, match="CITATION_PAGE_MISSING"):
        verify_source_citation({**good, "pdf_page": [], "reg_page": []}, manifest)
    with pytest.raises(MarineKnowledgeError, match="CITATION_PDF_PAGE_OUT_OF_RANGE"):
        verify_source_citation({**good, "pdf_page": [9999]}, manifest)
    with pytest.raises(MarineKnowledgeError, match="CITATION_SHA_STALE_OR_MISMATCH"):
        verify_source_citation({**good, "source_sha256": "0" * 64}, manifest)
    with pytest.raises(MarineKnowledgeError, match="CITATION_SHA_STALE_OR_MISMATCH"):
        verify_source_citation(good, manifest, expected_sha256="f" * 64)
    with pytest.raises(MarineKnowledgeError, match="CITATION_SOURCE_UNSUPPORTED"):
        verify_source_citation({**good, "source_id": "EXCLUDED_CDK_VEHICLE_CIRCULARS"}, manifest)


def test_marine_json_schema_files_exist_and_align_with_domain_pack() -> None:
    for fname in (
        "source-manifest.schema.json",
        "marine-knowledge-pack.schema.json",
        "marine-check-result.schema.json",
    ):
        schema_path = ROOT / "contracts" / "marine-knowledge" / fname
        assert schema_path.is_file()
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        assert "$schema" in data and "properties" in data
