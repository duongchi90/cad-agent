from __future__ import annotations

from copy import deepcopy

import pytest


def test_pack_contains_26_sourced_terms_and_10_conditional_rules() -> None:
    from cad_agent.marine_knowledge.manifest import get_marine_source_manifest
    from cad_agent.marine_knowledge.pack import get_marine_knowledge_pack

    manifest = get_marine_source_manifest()
    active_ids = {
        src["source_id"]
        for src in manifest["sources"]
        if src["usage_status"] != "EXCLUDED_NON_MARINE"
    }
    excluded_ids = {
        src["source_id"]
        for src in manifest["sources"]
        if src["usage_status"] == "EXCLUDED_NON_MARINE"
    }

    pack = get_marine_knowledge_pack()
    assert pack["schema_version"] == "marine-knowledge-pack-1.0"
    assert pack["status"] == "CANDIDATE_UNAPPROVED"
    assert pack["cad_mutation"] is False
    assert pack["default_core_behavior_changed"] is False
    assert pack["domain_pack_compatibility"]["approved_by"] is None
    assert 20 <= len(pack["terms"]) <= 30
    assert 8 <= len(pack["rules"]) <= 12

    for term in pack["terms"]:
        assert term["source_id"] in active_ids
        assert term["source_id"] not in excluded_ids
        assert term["approval_status"] in {"CANDIDATE_UNAPPROVED", "DRAFT_REVIEW_ONLY"}
        assert term["verbatim_excerpt"]
        assert term["pdf_page"]

    for rule in pack["rules"]:
        assert rule["source_id"] in active_ids
        assert rule["source_id"] not in excluded_ids
        assert rule["approval_status"] in {"CANDIDATE_UNAPPROVED", "DRAFT_REVIEW_ONLY"}
        assert rule["conditions"]
        assert rule["limitation"]
        assert rule["verification_method"]


def test_pack_rejects_excluded_source_or_forged_approved_status() -> None:
    from cad_agent.marine_knowledge.contracts import (
        MarineKnowledgeError,
        seal_knowledge_pack,
        validate_knowledge_pack,
    )
    from cad_agent.marine_knowledge.manifest import get_marine_source_manifest
    from cad_agent.marine_knowledge.pack import get_marine_knowledge_pack

    manifest = get_marine_source_manifest()
    pack = get_marine_knowledge_pack()

    forged = deepcopy(pack)
    forged["status"] = "APPROVED"
    with pytest.raises(MarineKnowledgeError):
        validate_knowledge_pack(forged, source_manifest=manifest)

    excluded = deepcopy(pack)
    excluded["rules"][0]["source_id"] = "EXCLUDED_CDK_VEHICLE_CIRCULARS"
    with pytest.raises(MarineKnowledgeError, match="RULE_UNKNOWN_SOURCE_ID"):
        seal_knowledge_pack(excluded, source_manifest=manifest)


def test_term_lookup_rule_query_text_normalization_and_disable_toggle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cad_agent.marine_knowledge.pack import (
        get_marine_pack_status,
        lookup_term,
        query_rules,
    )
    from cad_agent.marine_knowledge.text_normalization import normalize_marine_cad_text

    # TCVN3 hinted, TCVN3 unhinted, MTEXT escapes, and modern UTF-8 preservation
    assert normalize_marine_cad_text(r"{\f.VnArial|b0|i0|c0|p34;\C2;1200}") == "1200"
    assert normalize_marine_cad_text("§.ChuÈn", font_hint=".VnAvantH") == "Đ.Chuẩn"
    assert normalize_marine_cad_text("§.ChuÈn") == "Đ.Chuẩn"
    assert normalize_marine_cad_text("bè trÝ chung") == "bố trí chung"
    assert normalize_marine_cad_text("bố trí chung", font_hint=".VnAvantH") == "bố trí chung"
    assert normalize_marine_cad_text("boong d\xadíi") == "boong dưới"
    assert normalize_marine_cad_text("boong duíi") == "boong duới"
    assert normalize_marine_cad_text("Kho¶ng s­ên 600") == "Khoảng sườn 600"
    assert normalize_marine_cad_text("Tàu hàng 7000 — Bố trí chung") == "Tàu hàng 7000 — Bố trí chung"

    wl = lookup_term("đường nước")
    assert wl is not None and wl["term_id"] == "waterline_dn"
    base = lookup_term("§.ChuÈn")
    assert base is not None and base["term_id"] == "base_plane"
    vach = lookup_term("watertight bulkhead")
    assert vach is not None and vach["term_id"] == "watertight_bulkhead"

    inland_rules = query_rules(domain="vietnam_inland_waterway", drawing_type="LINES_PLAN")
    assert any(r["rule_id"] == "RULE_MK_01_QCVN72_SCOPE" for r in inland_rules)

    # Disabling pack keeps CAD Core untouched and reports DISABLED cleanly
    disabled = get_marine_pack_status(enabled=False)
    assert disabled["status"] == "DISABLED"
    assert disabled["cad_mutation"] is False
    assert disabled["pack"] is None

    monkeypatch.setenv("CAD_AGENT_DISABLE_MARINE_PACK", "1")
    disabled_env = get_marine_pack_status()
    assert disabled_env["status"] == "DISABLED"
