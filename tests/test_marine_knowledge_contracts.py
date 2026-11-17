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
