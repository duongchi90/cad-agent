"""Causal RED->GREEN regression tests and positive controls for PR #574 MV0-01..MV0-07, Custody, and P2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

import fitz
import pytest

from cad_agent.marine_knowledge import (
    MarineKnowledgeError,
    build_marine_core_proposal,
    detect_drawing_gaps_and_conflicts,
    evaluate_regulation_applicability_and_submittal,
    get_marine_knowledge_pack,
    get_marine_source_manifest,
    observe_dxf_bytes,
    validate_check_result,
    verify_source_citation,
)
from cad_agent.marine_knowledge.contracts import (
    SOURCE_MANIFEST_SCHEMA_VERSION,
    seal_knowledge_pack,
    seal_source_manifest,
    validate_knowledge_pack,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _ga(
    *,
    drawing_id: str = "MV0_GA",
    insunits: int = 4,
    length_line: str = "Chiều dài tàu L = 52.00 m",
    class_line: str = "CẤP TÀU : VR-SB",
    ship_type_line: str | None = "SHIP TYPE : DRY CARGO",
    material_line: str | None = "HULL MATERIAL : STEEL",
    engine_line: str | None = "MAIN ENGINE : 2x550 HP",
    bulkheads: Any = 4,
    ocr_only: bool = False,
    extra_texts: list[dict[str, Any]] | None = None,
    extra_metrics: dict[str, Any] | None = None,
    metric_provenance: dict[str, str] | None = None,
) -> dict[str, Any]:
    texts: list[dict[str, Any]] = [
        {"handle": "G1", "text": "BẢN VẼ BỐ TRÍ CHUNG TOÀN TÀU", "x": 500.0, "y": 500.0, "height": 350.0},
        {"handle": "G2", "text": "KHOANG HÀNG SỐ 1 - BUỒNG MÁY - VÁCH CHỐNG VA", "x": 20000.0, "y": 2000.0, "height": 260.0},
        {"handle": "G3", "text": class_line, "x": 60000.0, "y": 1000.0, "height": 250.0},
        {"handle": "G4", "text": length_line, "x": 60000.0, "y": 1500.0, "height": 250.0},
        {"handle": "G5", "text": "B = 9.60 m", "x": 60000.0, "y": 2000.0, "height": 250.0},
        {"handle": "G6", "text": "D = 4.20 m", "x": 60000.0, "y": 2500.0, "height": 250.0},
        {"handle": "G7", "text": "T = 3.10 m", "x": 60000.0, "y": 3000.0, "height": 250.0},
        {"handle": "G9", "text": "PORT OF REGISTRY : HAI PHONG", "x": 60000.0, "y": 4500.0, "height": 250.0},
        {"handle": "G10", "text": "A.P", "x": 1000.0, "y": 0.0, "height": 300.0},
        {"handle": "G11", "text": "F.P", "x": 53000.0, "y": 0.0, "height": 300.0},
    ]
    if engine_line:
        texts.append({"handle": "G8", "text": engine_line, "x": 60000.0, "y": 3500.0, "height": 250.0})
    if ship_type_line:
        texts.append({"handle": "G12", "text": ship_type_line, "x": 60000.0, "y": 4000.0, "height": 250.0})
    if material_line:
        texts.append({"handle": "G13", "text": material_line, "x": 60000.0, "y": 5000.0, "height": 250.0})
    if extra_texts:
        texts.extend(extra_texts)

    metrics: dict[str, Any] = {}
    if bulkheads is not None:
        metrics["transverse_watertight_bulkhead_count"] = bulkheads
    if extra_metrics:
        metrics.update(extra_metrics)

    out: dict[str, Any] = {
        "drawing_id": drawing_id,
        "drawing_code": "GA-01-01",
        "insunits": insunits,
        "measurement": 1,
        "claimed_scale": 100.0,
        "ocr_only": ocr_only,
        "texts": texts,
        "structural_metrics": metrics,
        "blank_fields": [],
    }
    if metric_provenance is not None:
        out["metric_provenance"] = dict(metric_provenance)
    return out


def _mcn(
    *,
    drawing_id: str = "MV0_MCN",
    insunits: int = 4,
    length_line: str = "Chiều dài tàu L = 52.00 m",
    class_line: str = "CẤP TÀU : VR-SB",
    ship_type_line: str | None = "SHIP TYPE : DRY CARGO",
    material_line: str | None = "HULL MATERIAL : STEEL",
    engine_line: str | None = "MAIN ENGINE : 2x550 HP",
    db_mm: Any = 750.0,
    girder_mm: Any = 2200.0,
    floor_mm: Any = 1800.0,
    floor_region: str | None = None,
    extra_texts: list[dict[str, Any]] | None = None,
    extra_metrics: dict[str, Any] | None = None,
    metric_provenance: dict[str, str] | None = None,
) -> dict[str, Any]:
    texts: list[dict[str, Any]] = [
        {"handle": "M1", "text": "MẶT CẮT NGANG SƯỜN GIỮA", "x": 500.0, "y": 500.0, "height": 200.0},
        {"handle": "M2", "text": "ĐÁY ĐÔI - ĐÀ NGANG ĐẶC", "x": 1000.0, "y": 600.0, "height": 150.0},
        {"handle": "M3", "text": class_line, "x": 4000.0, "y": 1000.0, "height": 150.0},
        {"handle": "M4", "text": length_line, "x": 4000.0, "y": 1250.0, "height": 150.0},
        {"handle": "M5", "text": "B = 9.60 m", "x": 4000.0, "y": 1500.0, "height": 150.0},
        {"handle": "M6", "text": "D = 4.20 m", "x": 4000.0, "y": 1750.0, "height": 150.0},
        {"handle": "M7", "text": "T = 3.10 m", "x": 4000.0, "y": 2000.0, "height": 150.0},
    ]
    if engine_line:
        texts.append({"handle": "M8", "text": engine_line, "x": 4000.0, "y": 2250.0, "height": 150.0})
    if ship_type_line:
        texts.append({"handle": "M9", "text": ship_type_line, "x": 4000.0, "y": 2500.0, "height": 150.0})
    if material_line:
        texts.append({"handle": "M10", "text": material_line, "x": 4000.0, "y": 2750.0, "height": 150.0})
    if extra_texts:
        texts.extend(extra_texts)

    metrics: dict[str, Any] = {}
    if db_mm is not None:
        metrics["double_bottom_height_mm"] = db_mm
    if girder_mm is not None:
        metrics["bottom_girder_max_spacing_mm"] = girder_mm
    if floor_mm is not None:
        metrics["transverse_floor_max_spacing_mm"] = floor_mm
    if floor_region is not None:
        metrics["floor_spacing_region"] = floor_region
    if extra_metrics:
        metrics.update(extra_metrics)

    out: dict[str, Any] = {
        "drawing_id": drawing_id,
        "drawing_code": "KC-02-01",
        "insunits": insunits,
        "measurement": 1,
        "claimed_scale": 50.0,
        "texts": texts,
        "structural_metrics": metrics,
        "blank_fields": [],
    }
    if metric_provenance is not None:
        out["metric_provenance"] = dict(metric_provenance)
    return out


def test_mv0_01_scope_trust_qcvn25_incidental_and_contradictions() -> None:
    """MV0-01: trust gates precede scope verdict; resolve L & QCVN 25 exclusion before confirming QCVN 72."""
    # 1. Untrusted OCR-only or unitless input must NOT issue NOT_APPLICABLE or F_SCOPE_QCVN72_CONFIRMED
    ocr_over140 = _ga(drawing_id="OCR_145M", length_line="Chiều dài tàu L = 145.00 m", ocr_only=True)
    res_ocr = evaluate_regulation_applicability_and_submittal([ocr_over140])
    assert res_ocr["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_ocr["applicable_regulation_scope"]["in_scope"] is None
    assert not any(f["finding_id"] == "F_SCOPE_QCVN72_CONFIRMED" for f in res_ocr["findings"])

    unitless_vrsb = _ga(drawing_id="UNITLESS_52M", insunits=0)
    res_unitless = evaluate_regulation_applicability_and_submittal([unitless_vrsb, _mcn(insunits=0)])
    assert res_unitless["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_unitless["applicable_regulation_scope"]["in_scope"] is None
    assert not any(f["finding_id"] == "F_SCOPE_QCVN72_CONFIRMED" for f in res_unitless["findings"])

    # 2. Missing L on VR-SB must NOT confirm QCVN 72 scope (F_SCOPE_QCVN72_CONFIRMED absent)
    ga_no_len = _ga(drawing_id="NO_LEN_VRSB", length_line="PHIÊN BẢN THAM KHẢO")
    res_no_len = evaluate_regulation_applicability_and_submittal([ga_no_len])
    assert res_no_len["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_no_len["applicable_regulation_scope"]["in_scope"] is None
    assert not any(f["finding_id"] == "F_SCOPE_QCVN72_CONFIRMED" for f in res_no_len["findings"])

    # 3. VR-SII L=18m WITHOUT engine power -> QCVN 25 exclusion unresolved -> INSUFFICIENT_EVIDENCE
    vrsii_18_no_eng = _mcn(
        drawing_id="VRSII_18M_NO_ENG",
        class_line="CẤP TÀU : VR-SII",
        length_line="Chiều dài tàu L = 18.00 m",
        engine_line=None,
        db_mm=None,
        girder_mm=None,
        floor_mm=None,
        extra_metrics={"min_plate_thickness_mm": 4.5, "min_bottom_plate_mm": 4.5, "min_bilge_plate_mm": 4.5},
    )
    res_no_eng = evaluate_regulation_applicability_and_submittal([vrsii_18_no_eng])
    assert res_no_eng["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_no_eng["applicable_regulation_scope"]["in_scope"] is None
    assert any(f["finding_id"] == "F_SCOPE_QCVN25_UNRESOLVED" for f in res_no_eng["findings"])

    # 4. VR-SII L=18m WITH 30 HP (< 50 HP) -> QCVN 25:2015/BGTVT applies -> NOT_APPLICABLE for QCVN 72
    vrsii_18_30hp = _mcn(
        drawing_id="VRSII_18M_30HP",
        class_line="CẤP TÀU : VR-SII",
        length_line="Chiều dài tàu L = 18.00 m",
        engine_line="MAIN ENGINE : 30 HP",
        db_mm=None,
        girder_mm=None,
        floor_mm=None,
    )
    res_qcvn25 = evaluate_regulation_applicability_and_submittal([vrsii_18_30hp])
    assert res_qcvn25["status"] == "NOT_APPLICABLE"
    assert res_qcvn25["applicable_regulation_scope"]["referred_regulation"] == "QCVN 25:2015/BGTVT"

    # 5. Contradictory VR-SB + QCVN 25 scope markers -> CONFLICT
    contra_scope = _ga(
        drawing_id="CONTRA_VRSB_QCVN25",
        extra_texts=[{"handle": "Q25", "text": "CẤP TÀU ÁP DỤNG : QCVN 25:2015/BGTVT", "x": 100.0, "y": 900.0}],
    )
    assert evaluate_regulation_applicability_and_submittal([contra_scope])["status"] == "CONFLICT"

    # 6. Positive controls: VR-SII 18m with 120 HP (>=50 HP), VR-SB 18m (coastal), & incidental ref note on VR-SB 52m -> PASS
    vrsii_18_120hp = _mcn(
        drawing_id="VRSII_18M_120HP",
        class_line="CẤP TÀU : VR-SII",
        length_line="Chiều dài tàu L = 18.00 m",
        engine_line="MAIN ENGINE : 120 HP",
        db_mm=None,
        girder_mm=None,
        floor_mm=None,
        extra_metrics={"min_plate_thickness_mm": 4.5, "min_bottom_plate_mm": 4.5, "min_bilge_plate_mm": 4.5},
    )
    assert evaluate_regulation_applicability_and_submittal([vrsii_18_120hp])["status"] == "PASS"

    vrsb_18 = _mcn(
        drawing_id="VRSB_18M",
        class_line="CẤP TÀU : VR-SB",
        length_line="Chiều dài tàu L = 18.00 m",
        engine_line=None,
        db_mm=None,
        girder_mm=None,
        floor_mm=None,
        extra_metrics={"min_plate_thickness_mm": 4.5, "min_bottom_plate_mm": 4.5, "min_bilge_plate_mm": 4.5},
    )
    assert evaluate_regulation_applicability_and_submittal([vrsb_18])["status"] == "PASS"

    ga_incidental = _ga(
        extra_texts=[{"handle": "NOTE1", "text": "GHI CHÚ: THAM CHIẾU QCVN 21:2015 ĐỂ SO SÁNH", "x": 100.0, "y": 900.0}],
    )
    assert evaluate_regulation_applicability_and_submittal([ga_incidental, _mcn()])["status"] == "PASS"


def test_mv0_02_historical_citations_vs_current_referrals_and_over_140m() -> None:
    """MV0-02: never infer sea-going steel referral from L > 140m alone; separate historical editions from 2025-09-01 successors."""
    # 1. Proven L = 150 m without sea-going/VRH evidence must NOT refer QCVN 21
    bare_150 = _ga(drawing_id="BARE_150M", length_line="Chiều dài tàu L = 150.00 m")
    res_150 = evaluate_regulation_applicability_and_submittal([bare_150])
    assert res_150["status"] == "NOT_APPLICABLE"
    scope_150 = res_150["applicable_regulation_scope"]
    assert scope_150["clause_basis"] == "1.1.1"
    assert scope_150["detected_scope"] == "L_GT_140M"
    assert scope_150["referred_regulation"] is None
    assert "01/05/2027" in scope_150["upcoming_amendment"] or "2027-05-01" in scope_150["upcoming_amendment"]

    # 2. Explicit *VRH sea-going ship -> current successor QCVN 21:2025/BGTVT (Circ. 09/2025, 2025-09-01) + historical QCVN 21:2015
    sea_vrh = _ga(
        drawing_id="SEA_VRH_150M",
        length_line="Chiều dài tàu L = 150.00 m",
        class_line="CLASS : *VRH (QCVN 21:2015/BGTVT)",
    )
    res_vrh = evaluate_regulation_applicability_and_submittal([sea_vrh])
    assert res_vrh["status"] == "NOT_APPLICABLE"
    scope_vrh = res_vrh["applicable_regulation_scope"]
    assert scope_vrh["referred_regulation"] == "QCVN 21:2025/BGTVT"
    assert scope_vrh["historical_cited_regulation"] == "QCVN 21:2015/BGTVT"
    assert "09/2025/TT-BGTVT" in scope_vrh["successor_circular"]
    assert "2025-09-01" in scope_vrh["successor_circular"]

    # 3. High-speed craft (Clause 1.1.2-5) -> current successor QCVN 127:2025/BGTVT (Circ. 06/2025, 2025-09-01) + historical QCVN 54:2013
    hsc = _ga(
        drawing_id="HSC_SHIP",
        class_line="TÀU CAO TỐC (QCVN 54:2013/BGTVT)",
    )
    res_hsc = evaluate_regulation_applicability_and_submittal([hsc])
    assert res_hsc["status"] == "NOT_APPLICABLE"
    scope_hsc = res_hsc["applicable_regulation_scope"]
    assert scope_hsc["clause_basis"] == "1.1.2"
    assert scope_hsc["referred_regulation"] == "QCVN 127:2025/BGTVT"
    assert scope_hsc["historical_cited_regulation"] == "QCVN 54:2013/BGTVT"
    assert "06/2025/TT-BGTVT" in scope_hsc["successor_circular"]
    assert "2025-09-01" in scope_hsc["successor_circular"]


def test_mv0_03_bounded_citation_spans_and_rule08_2_4_6_9() -> None:
    """MV0-03: textbook and regulation clause spans must stay bounded; unbounded spans cap at SOURCE_PAGE_VERIFIED."""
    # 1. Textbook bleed test: 2.1 heading followed by unrelated text / 2.2 heading
    doc_tb = fitz.open()
    p1 = doc_tb.new_page()
    p1.insert_text(
        (72, 72),
        "CHAPTER 2\n"
        "2.1 Base plane definition\n"
        "Base plane is perpendicular to the centerline and midship planes.\n"
        "2.2 Propeller shafting\n"
        "Four-blade bronze marine propeller assembly.\n",
    )
    doc_tb.set_toc([[1, "2.1 Base plane definition", 1], [1, "2.2 Propeller shafting", 1]])
    tb_bytes = doc_tb.tobytes()
    doc_tb.close()
    tb_sha = hashlib.sha256(tb_bytes).hexdigest()
    tb_man = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": "MV0_03_TB",
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [
                {
                    "source_id": "SYNTH_TB",
                    "title": "Synthetic Textbook",
                    "document_kind": "TEXTBOOK",
                    "version": "1",
                    "origin": "synth",
                    "sha256": tb_sha,
                    "page_count": 1,
                    "applicable_scope": ["test"],
                    "usage_rights": "OPEN_ACADEMIC_RESEARCH",
                    "commit_prohibited": True,
                    "usage_status": "ACTIVE_INDEXED",
                    "notes": "synth",
                }
            ],
        }
    )

    with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
        verify_source_citation(
            {
                "source_id": "SYNTH_TB",
                "source_sha256": tb_sha,
                "source_version": "1",
                "clause": "Chapter 2, 2.1 Base plane definition",
                "pdf_page": [1],
                "reg_page": [],
                "verbatim_excerpt": "Four-blade bronze marine propeller assembly.",
            },
            tb_man,
            source_bytes=tb_bytes,
        )

    tb_ok = verify_source_citation(
        {
            "source_id": "SYNTH_TB",
            "source_sha256": tb_sha,
            "source_version": "1",
            "clause": "Chapter 2, 2.1 Base plane definition",
            "pdf_page": [1],
            "reg_page": [],
            "verbatim_excerpt": "Base plane is perpendicular to the centerline and midship planes.",
        },
        tb_man,
        source_bytes=tb_bytes,
    )
    assert tb_ok["verification_level"] == "SOURCE_CONTENT_VERIFIED"
    assert tb_ok["clause_span_status"] == "CLAUSE_SPAN_BOUNDED"

    # 2. Regulation outline fallback WITHOUT body heading & WITHOUT closing boundary must NOT claim SOURCE_CONTENT_VERIFIED
    doc_reg = fitz.open()
    rp1 = doc_reg.new_page()
    rp1.insert_text((72, 72), "19 REG\nIntroductory sentence lacking section heading.\nPropeller shaft rule in same page.\n")
    doc_reg.set_toc([[1, "1.1 Scope", 1]])
    reg_bytes = doc_reg.tobytes()
    doc_reg.close()
    reg_sha = hashlib.sha256(reg_bytes).hexdigest()
    reg_man = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": "MV0_03_REG",
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [
                {
                    "source_id": "SYNTH_REG_UNBOUND",
                    "title": "Synthetic Unbounded Reg",
                    "document_kind": "REGULATION",
                    "version": "1",
                    "origin": "synth",
                    "sha256": reg_sha,
                    "page_count": 1,
                    "applicable_scope": ["test"],
                    "usage_rights": "OPEN_ACADEMIC_RESEARCH",
                    "commit_prohibited": True,
                    "usage_status": "ACTIVE_INDEXED",
                    "notes": "synth",
                }
            ],
        }
    )
    reg_unbounded = verify_source_citation(
        {
            "source_id": "SYNTH_REG_UNBOUND",
            "source_sha256": reg_sha,
            "source_version": "1",
            "clause": "1.1 Scope",
            "pdf_page": [1],
            "reg_page": [19],
            "verbatim_excerpt": "Propeller shaft rule in same page.",
        },
        reg_man,
        source_bytes=reg_bytes,
    )
    assert reg_unbounded["clause_span_status"] == "CLAUSE_BOUNDARY_UNBOUNDED"
    assert reg_unbounded["verification_level"] == "SOURCE_PAGE_VERIFIED"

    # 3. RULE_MK_08 must cite Clause 2.4.6-9 explicitly in clause & verbatim_excerpt
    pack = get_marine_knowledge_pack()
    rule08 = next(r for r in pack["rules"] if r["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
    assert "2.4.6-9" in rule08["clause"]
    assert "đáy đôi mạn kép" in (rule08["verbatim_excerpt"] or "").lower()


def test_custody_disposition_14_textbook_summaries_only_and_schema_parity() -> None:
    """Custody: 14 VIMARU records (3/7/2/2) omit committed verbatim_excerpt; summary never promotes to content verification."""
    manifest = get_marine_source_manifest()
    pack = get_marine_knowledge_pack()
    sources = {s["source_id"]: s for s in manifest["sources"]}

    ch_counts = {"VIMARU_VETAU_CH1": 0, "VIMARU_VETAU_CH2": 0, "VIMARU_VETAU_CH3": 0, "VIMARU_VETAU_CH4": 0}
    reg_count = 0
    for rec in [*pack["terms"], *pack["rules"]]:
        sid = rec["source_id"]
        assert isinstance(rec.get("technical_summary"), str) and rec["technical_summary"].strip()
        if sid in ch_counts:
            ch_counts[sid] += 1
            assert rec["excerpt_disposition"] == "PRIVATE_SOURCE_SUMMARY_ONLY"
            assert rec["verbatim_excerpt"] is None
        else:
            reg_count += 1
            assert rec["excerpt_disposition"] == "PUBLIC_VERBATIM_EXCERPT"
            assert isinstance(rec["verbatim_excerpt"], str) and rec["verbatim_excerpt"].strip()

    assert ch_counts == {
        "VIMARU_VETAU_CH1": 3,
        "VIMARU_VETAU_CH2": 7,
        "VIMARU_VETAU_CH3": 2,
        "VIMARU_VETAU_CH4": 2,
    }
    assert reg_count == 22

    # Pack validator rejects private source trying to smuggle non-null verbatim_excerpt
    bad_pack = dict(pack)
    bad_rules = [dict(r) for r in pack["rules"]]
    tb_idx = next(i for i, r in enumerate(bad_rules) if r["source_id"] == "VIMARU_VETAU_CH1")
    bad_rules[tb_idx]["excerpt_disposition"] = "PUBLIC_VERBATIM_EXCERPT"
    bad_rules[tb_idx]["verbatim_excerpt"] = "Leaked private textbook excerpt."
    bad_pack["rules"] = bad_rules
    with pytest.raises(MarineKnowledgeError, match="RULE_PRIVATE_VERBATIM_EXCERPT_FORBIDDEN"):
        seal_knowledge_pack(bad_pack, source_manifest=manifest)
    with pytest.raises(MarineKnowledgeError, match="RULE_PRIVATE_VERBATIM_EXCERPT_FORBIDDEN"):
        validate_knowledge_pack(bad_pack, source_manifest=manifest)

    # verify_source_citation on summary-only private record cannot reach SOURCE_CONTENT_VERIFIED
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "1.2 Quy định tỷ lệ bản vẽ\nTỷ lệ thường dùng là 1:50.\n")
    pbytes = doc.tobytes()
    doc.close()
    psha = hashlib.sha256(pbytes).hexdigest()
    priv_man = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": "PRIV_MAN",
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [
                {
                    "source_id": "PRIV_TB",
                    "title": "Private Textbook",
                    "document_kind": "TEXTBOOK",
                    "version": "1",
                    "origin": "priv",
                    "sha256": psha,
                    "page_count": 1,
                    "applicable_scope": ["test"],
                    "usage_rights": "PRIVATE_LOCAL_NO_COMMIT",
                    "commit_prohibited": True,
                    "usage_status": "ACTIVE_INDEXED",
                    "notes": "priv",
                }
            ],
        }
    )
    res_priv = verify_source_citation(
        {
            "source_id": "PRIV_TB",
            "source_sha256": psha,
            "source_version": "1",
            "clause": "1.2 Quy định tỷ lệ bản vẽ",
            "pdf_page": [1],
            "reg_page": [],
            "excerpt_disposition": "PRIVATE_SOURCE_SUMMARY_ONLY",
            "verbatim_excerpt": None,
            "technical_summary": "Summary only description of drafting scales.",
        },
        priv_man,
        source_bytes=pbytes,
    )
    assert res_priv["verification_level"] == "SOURCE_PAGE_VERIFIED"
    assert "CLAUSE_CONTENT_VERIFIED" not in res_priv["verification_states"]

    with pytest.raises(MarineKnowledgeError, match="CITATION_PRIVATE_VERBATIM_FORBIDDEN"):
        verify_source_citation(
            {
                "source_id": "PRIV_TB",
                "source_sha256": psha,
                "source_version": "1",
                "clause": "1.2 Quy định tỷ lệ bản vẽ",
                "pdf_page": [1],
                "reg_page": [],
                "excerpt_disposition": "PRIVATE_SOURCE_SUMMARY_ONLY",
                "verbatim_excerpt": "Tỷ lệ thường dùng là 1:50.",
                "technical_summary": "Summary",
            },
            priv_man,
            source_bytes=pbytes,
        )


def test_manifest_does_not_publish_unused_private_local_source_identities() -> None:
    """Private local drawing and unrelated archive identities have no V0 check and stay out of the public manifest."""
    manifest = get_marine_source_manifest()
    published = json.dumps(manifest, ensure_ascii=False)
    assert "PRIVATE_HOMEWORK_DWG_20261109" not in published
    assert "bai ve nha 09.11.2026_recover.dwg" not in published
    assert "fca179cc8b89791560268a6da5251853914283b630d40317342aec6a4b057bde" not in published
    assert "EXCLUDED_CDK_VEHICLE_CIRCULARS" not in published
    assert "HỌC PHÍ" not in published
    assert "13855f2999a1bc8e6d879c6111a1cd16dc92afe56756f7c624b52d1833eeffc1" not in published


def test_dxf_insert_entity_budget_streams_and_marks_incomplete_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Geometry-heavy blocks cannot evade the observer work budget merely by carrying one text entity."""
    from cad_agent.marine_knowledge import observer

    monkeypatch.setattr(observer, "_MAX_DXF_ENTITY_TRAVERSAL", 12, raising=False)
    lines = [
        "0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1015",
        "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
        "0", "SECTION", "2", "BLOCKS",
        "0", "BLOCK", "8", "0", "2", "GEOMETRY_HEAVY_WITH_TEXT", "70", "0",
        "10", "0", "20", "0", "30", "0", "3", "GEOMETRY_HEAVY_WITH_TEXT",
    ]
    for idx in range(30):
        lines.extend(
            [
                "0", "LINE", "8", "0", "10", str(idx), "20", "0", "30", "0",
                "11", str(idx), "21", "10", "31", "0",
            ]
        )
    lines.extend(
        [
            "0", "TEXT", "8", "0", "10", "0", "20", "0", "30", "0", "40", "250",
            "1", "HULL STRUCTURE : DOUBLE HULL", "0", "ENDBLK", "0", "ENDSEC",
            "0", "SECTION", "2", "ENTITIES", "0", "INSERT", "8", "0",
            "2", "GEOMETRY_HEAVY_WITH_TEXT", "10", "1000", "20", "1000", "30", "0",
            "0", "ENDSEC", "0", "EOF", "",
        ]
    )

    observation = observe_dxf_bytes("\n".join(lines).encode("ascii"), drawing_id="BUDGETED_INSERT")
    assert any(
        item.get("reason") == "DXF_ENTITY_TRAVERSAL_LIMIT_REACHED"
        for item in observation["skipped_entities"]
    )
    result = detect_drawing_gaps_and_conflicts([observation], partial_package=True)
    assert any(
        finding["finding_id"] == "F_SKIPPED_CAD_ENTITIES_BUDGETED_INSERT"
        and finding["verdict"] == "INSUFFICIENT_EVIDENCE"
        for finding in result["findings"]
    )


def test_mv0_04_bulkhead_20m_boundary_steel_gate_and_2_4_6_9_exception() -> None:
    """MV0-04: 2.4.6-8 begins strictly at L > 20m; gate steel before CONFLICT; qualify 2.4.6-9 double-hull/container."""
    # 1. Exact L = 20.00 m -> ambiguous boundary between 3.7.21 (<20m) and 2.4.6-8 (>20m) -> INSUFFICIENT_EVIDENCE
    ga_20 = _ga(drawing_id="GA_EXACT_20M", length_line="Chiều dài tàu L = 20.00 m", bulkheads=2)
    res_20 = evaluate_regulation_applicability_and_submittal([ga_20])
    assert res_20["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_BULKHEAD_20M_BOUNDARY_UNRESOLVED" for f in res_20["findings"])

    # 2. Aluminum / missing hull material with 2 bulkheads on L=52m -> NEVER emit steel RULE_MK_08 CONFLICT
    ga_52_al = _ga(
        drawing_id="GA_52_AL",
        class_line="CẤP TÀU : VR-SB AL",
        material_line="HULL MATERIAL : ALUMINUM ALLOY",
        bulkheads=2,
    )
    res_al = evaluate_regulation_applicability_and_submittal([ga_52_al])
    assert not any(
        f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT" and f["verdict"] == "CONFLICT"
        for f in res_al["findings"]
    )
    assert res_al["status"] in {"INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE"}

    ga_52_nomat = _ga(drawing_id="GA_52_NOMAT", material_line=None, bulkheads=3)
    res_nomat = evaluate_regulation_applicability_and_submittal([ga_52_nomat])
    assert res_nomat["status"] == "INSUFFICIENT_EVIDENCE"
    assert not any(
        f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT" and f["verdict"] == "CONFLICT"
        for f in res_nomat["findings"]
    )

    # 3. Double-hull / double-side cargo vessel L=52m with 3 bulkheads qualifies under 2.4.6-9 -> INSUFFICIENT_EVIDENCE, NOT hard CONFLICT
    ga_dh = _ga(
        drawing_id="GA_DOUBLE_HULL",
        bulkheads=3,
        extra_texts=[{"handle": "DH1", "text": "HULL STRUCTURE : DOUBLE HULL", "x": 100.0, "y": 950.0}],
    )
    res_dh = evaluate_regulation_applicability_and_submittal([ga_dh, _mcn()])
    mk08_dh = next(f for f in res_dh["findings"] if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
    assert mk08_dh["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert mk08_dh["finding_id"] == "F_WATERTIGHT_BULKHEAD_2_4_6_9_EXCEPTION_QUALIFIED"
    assert "2.4.6-9" in mk08_dh["clause"]
    assert res_dh["status"] == "INSUFFICIENT_EVIDENCE"

    # 4. Positive controls: L=20.50m bh=3 -> PASS with coverage_scope=COUNT_ONLY; bh=2 -> CONFLICT
    ga_20_5_ok = _ga(drawing_id="GA_20_5_OK", length_line="Chiều dài tàu L = 20.50 m", bulkheads=3)
    mcn_20_5 = _mcn(drawing_id="MCN_20_5", length_line="Chiều dài tàu L = 20.50 m")
    res_20_5_ok = evaluate_regulation_applicability_and_submittal([ga_20_5_ok, mcn_20_5])
    assert res_20_5_ok["status"] == "PASS"
    mk08_ok = next(f for f in res_20_5_ok["findings"] if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
    assert mk08_ok["evidence"]["coverage_scope"] == "COUNT_ONLY"

    ga_20_5_bad = _ga(
        drawing_id="GA_20_5_BAD",
        length_line="Chiều dài tàu L = 20.50 m",
        bulkheads=2,
        ship_type_line="SHIP TYPE : DRY CARGO NON-CONTAINER",
        extra_texts=[{"handle": "NS0", "text": "HULL STRUCTURE : SINGLE SIDE", "x": 60000.0, "y": 5400.0, "height": 250.0}],
    )
    assert evaluate_regulation_applicability_and_submittal([ga_20_5_bad, mcn_20_5])["status"] == "CONFLICT"


def test_mv0_05_double_bottom_per_region_pairing_provenance_steel_and_truthful_conditions() -> None:
    """MV0-05: pair each floor spacing with its own verified region; gate steel & provenance; truthful conditions."""
    # 1. Luna's exact repro: 1700 mm UNDER_CARGO_HATCH + 1900 mm OUTSIDE_CARGO_HATCH -> PASS
    mcn_uh = _mcn(
        drawing_id="MCN_1700_UH",
        floor_mm=1700.0,
        floor_region="UNDER_CARGO_HATCH",
        metric_provenance={"floor_spacing_region": "FIXTURE_SUPPLIED"},
    )
    mcn_oh = _mcn(
        drawing_id="MCN_1900_OH",
        floor_mm=1900.0,
        floor_region="OUTSIDE_CARGO_HATCH",
        metric_provenance={"floor_spacing_region": "FIXTURE_SUPPLIED"},
    )
    res_pair_pass = evaluate_regulation_applicability_and_submittal([_ga(), mcn_uh, mcn_oh])
    assert res_pair_pass["status"] == "PASS"
    mk09_ok = next(f for f in res_pair_pass["findings"] if f["rule_id"] == "RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT")
    assert mk09_ok["verdict"] == "PASS"
    assert "unverified_subconditions" in mk09_ok["evidence"]

    # Same repro using multi-measurement list on one sheet -> PASS
    mcn_multi_ok = _mcn(
        drawing_id="MCN_MULTI_OK",
        floor_mm=None,
        extra_metrics={
            "floor_spacing_measurements": [
                {"spacing_mm": 1700.0, "region": "UNDER_CARGO_HATCH"},
                {"spacing_mm": 1900.0, "region": "OUTSIDE_CARGO_HATCH"},
            ]
        },
        metric_provenance={"floor_spacing_measurements": "FIXTURE_SUPPLIED"},
    )
    assert evaluate_regulation_applicability_and_submittal([_ga(), mcn_multi_ok])["status"] == "PASS"

    # 2. Control: 1850 mm UNDER_CARGO_HATCH + 1900 mm OUTSIDE_CARGO_HATCH -> CONFLICT
    mcn_uh_fail = _mcn(
        drawing_id="MCN_1850_UH",
        floor_mm=1850.0,
        floor_region="UNDER_CARGO_HATCH",
        metric_provenance={"floor_spacing_region": "FIXTURE_SUPPLIED"},
    )
    res_pair_fail = evaluate_regulation_applicability_and_submittal([_ga(), mcn_uh_fail, mcn_oh])
    assert res_pair_fail["status"] == "CONFLICT"

    # 3. Untrusted OCR provenance on floor_spacing_region cannot relax 1900 mm outside hatch -> INSUFFICIENT_EVIDENCE
    mcn_untrusted_reg = _mcn(
        drawing_id="MCN_OCR_REGION",
        floor_mm=1900.0,
        floor_region="OUTSIDE_CARGO_HATCH",
        metric_provenance={"floor_spacing_region": "UNVERIFIED_OCR_TEXT"},
    )
    res_untrusted_reg = evaluate_regulation_applicability_and_submittal([_ga(), mcn_untrusted_reg])
    assert res_untrusted_reg["status"] == "INSUFFICIENT_EVIDENCE"

    # 4. Aluminum / missing material with db_mm=500 -> NEVER emit steel RULE_MK_09 CONFLICT
    mcn_al_db = _mcn(
        drawing_id="MCN_AL_DB500",
        class_line="CẤP TÀU : VR-SB AL",
        material_line="HULL MATERIAL : ALUMINUM ALLOY",
        db_mm=500.0,
    )
    res_al_db = evaluate_regulation_applicability_and_submittal([mcn_al_db])
    assert not any(
        f["rule_id"] == "RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT" and f["verdict"] == "CONFLICT"
        for f in res_al_db["findings"]
    )

    mcn_nomat_db = _mcn(drawing_id="MCN_NOMAT_DB500", material_line=None, db_mm=500.0)
    res_nomat_db = evaluate_regulation_applicability_and_submittal([mcn_nomat_db])
    assert not any(
        f["rule_id"] == "RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT" and f["verdict"] == "CONFLICT"
        for f in res_nomat_db["findings"]
    )
    mk09_nomat = next(
        (f for f in res_nomat_db["findings"] if f["rule_id"] == "RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT"),
        None,
    )
    if mk09_nomat is not None:
        assert not any("steel vessel" in c.lower() for c in mk09_nomat["conditions_applied"])


def _dxf_with_special_entities(*entities: list[str]) -> bytes:
    lines = [
        "0", "SECTION", "2", "HEADER",
        "9", "$ACADVER", "1", "AC1015",
        "9", "$INSUNITS", "70", "4",
        "9", "$MEASUREMENT", "70", "1",
        "0", "ENDSEC",
        "0", "SECTION", "2", "BLOCKS",
        "0", "BLOCK", "8", "0", "2", "BOW_BLK", "70", "0", "10", "0.0", "20", "0.0", "30", "0.0", "3", "BOW_BLK",
        "0", "TEXT", "8", "0", "10", "1000.0", "20", "0.0", "30", "0.0", "40", "300.0", "1", "A.P",
        "0", "TEXT", "8", "0", "10", "53000.0", "20", "0.0", "30", "0.0", "40", "300.0", "1", "F.P",
        "0", "ENDBLK",
        "0", "BLOCK", "8", "0", "2", "AUTARROW", "70", "0", "10", "0.0", "20", "0.0", "30", "0.0", "3", "AUTARROW",
        "0", "LINE", "8", "0", "10", "0.0", "20", "0.0", "30", "0.0", "11", "100.0", "21", "0.0", "31", "0.0",
        "0", "ENDBLK",
        "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
        "0", "TEXT", "8", "0", "10", "500.0", "20", "500.0", "30", "0.0", "40", "350.0", "1", "BAN VE BO TRI CHUNG",
        "0", "TEXT", "8", "0", "10", "500.0", "20", "1000.0", "30", "0.0", "40", "250.0", "1", "L = 52.00 m",
        "0", "LINE", "8", "0", "10", "0.0", "20", "0.0", "30", "0.0", "11", "52000.0", "21", "0.0", "31", "0.0",
    ]
    for block in entities:
        lines.extend(block)
    lines.extend(["0", "ENDSEC", "0", "EOF", ""])
    return "\n".join(lines).encode("latin-1")


def test_mv0_06_per_occurrence_bow_orientation_minsert_text_transforms_and_skipped() -> None:
    """MV0-06: detect opposing per-occurrence bow orientations, MINSERT, mirrored text, skipped entities; allow geom AUTARROW."""
    # 1. Symmetric opposing-orientation inserts on one sheet (rot=0 AP=1000,FP=53000 & rot=180 at x=100000 AP=99000,FP=47000 -> mean AP=50000 == mean FP!)
    dxf_opposing = _dxf_with_special_entities(
        ["0", "INSERT", "8", "0", "2", "BOW_BLK", "10", "0.0", "20", "0.0", "30", "0.0", "41", "1.0", "42", "1.0", "50", "0.0"],
        ["0", "INSERT", "8", "0", "2", "BOW_BLK", "10", "100000.0", "20", "5000.0", "30", "0.0", "41", "1.0", "42", "1.0", "50", "180.0"],
    )
    obs_opp = observe_dxf_bytes(dxf_opposing, drawing_id="GA_OPPOSING_OCC")
    gap_opp = detect_drawing_gaps_and_conflicts([obs_opp], partial_package=True)
    assert gap_opp["status"] == "CONFLICT"
    assert any("F_BOW_ORIENTATION" in f["finding_id"] and f["verdict"] == "CONFLICT" for f in gap_opp["findings"])

    # 2. Text-bearing MINSERT (col_count=2, row_count=2) -> flagged as unsupported -> INSUFFICIENT_EVIDENCE
    dxf_minsert = _dxf_with_special_entities(
        ["0", "INSERT", "8", "0", "2", "BOW_BLK", "10", "0.0", "20", "0.0", "30", "0.0", "70", "2", "71", "2", "44", "1000.0", "45", "1000.0"],
    )
    obs_minsert = observe_dxf_bytes(dxf_minsert, drawing_id="GA_MINSERT")
    assert obs_minsert["unsupported_insert_transforms"]
    assert detect_drawing_gaps_and_conflicts([obs_minsert])["status"] == "INSUFFICIENT_EVIDENCE"

    # 3. Mirrored TEXT (text_generation_flag=2) -> flagged in unsupported_text_transforms -> INSUFFICIENT_EVIDENCE
    dxf_mir_txt = _dxf_with_special_entities(
        ["0", "TEXT", "8", "0", "10", "1000.0", "20", "0.0", "30", "0.0", "40", "300.0", "71", "2", "1", "A.P"],
        ["0", "TEXT", "8", "0", "10", "53000.0", "20", "0.0", "30", "0.0", "40", "300.0", "1", "F.P"],
    )
    obs_mir = observe_dxf_bytes(dxf_mir_txt, drawing_id="GA_MIRRORED_TEXT")
    assert obs_mir["unsupported_text_transforms"]
    assert detect_drawing_gaps_and_conflicts([obs_mir])["status"] == "INSUFFICIENT_EVIDENCE"

    # 4. Skipped entities surfaced -> INSUFFICIENT_EVIDENCE
    ga_skipped = _ga(drawing_id="GA_SKIPPED")
    ga_skipped["skipped_entities"] = [{"handle": "FF1", "dxftype": "ACAD_PROXY_ENTITY", "reason": "UNSUPPORTED_PROXY_TEXT"}]
    gap_skip = detect_drawing_gaps_and_conflicts([ga_skipped])
    assert gap_skip["status"] == "INSUFFICIENT_EVIDENCE"
    assert any("F_SKIPPED_CAD_ENTITIES" in f["finding_id"] for f in gap_skip["findings"])

    # 5. Mixed unpartitioned MODELSPACE AP/FP anchors without view_id -> INSUFFICIENT_EVIDENCE
    ga_mixed_ap = _ga(
        drawing_id="GA_MIXED_AP",
        extra_texts=[
            {"handle": "AP2", "text": "A.P", "x": 60000.0, "y": 5000.0, "height": 300.0},
            {"handle": "FP2", "text": "F.P", "x": 5000.0, "y": 5000.0, "height": 300.0},
        ],
    )
    gap_mixed = detect_drawing_gaps_and_conflicts([ga_mixed_ap])
    assert gap_mixed["status"] == "INSUFFICIENT_EVIDENCE"

    # 6. Positive control: geometry-only negative-scale AUTARROW block + clean single BOW_BLK -> PASS
    dxf_autarrow = _dxf_with_special_entities(
        ["0", "INSERT", "8", "0", "2", "BOW_BLK", "10", "0.0", "20", "0.0", "30", "0.0", "41", "1.0", "42", "1.0", "50", "0.0"],
        ["0", "INSERT", "8", "0", "2", "AUTARROW", "10", "25000.0", "20", "1000.0", "30", "0.0", "41", "-1.0", "42", "1.0", "50", "0.0"],
    )
    obs_arrow = observe_dxf_bytes(dxf_autarrow, drawing_id="GA_AUTARROW_OK")
    assert obs_arrow["unsupported_insert_transforms"] == []
    assert detect_drawing_gaps_and_conflicts([obs_arrow])["status"] == "PASS"


def test_mv0_07_gap_pass_requires_substantive_checks_executed() -> None:
    """MV0-07: geometry-only or noise-text inputs without substantive checks must return INSUFFICIENT_EVIDENCE, never PASS."""
    geom_dxf = "\n".join(
        [
            "0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1015", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
            "0", "SECTION", "2", "ENTITIES",
            "0", "LINE", "8", "0", "10", "0.0", "20", "0.0", "30", "0.0", "11", "5000.0", "21", "0.0", "31", "0.0",
            "0", "ENDSEC", "0", "EOF", "",
        ]
    ).encode("ascii")
    obs_geom = observe_dxf_bytes(geom_dxf, drawing_id="GEOM_ONLY_LINES")
    res_geom = detect_drawing_gaps_and_conflicts([obs_geom])
    assert res_geom["status"] == "INSUFFICIENT_EVIDENCE"
    assert not any(f["finding_id"] == "F_NO_GAPS_OR_CONFLICTS" for f in res_geom["findings"])

    noise_only = {"drawing_id": "NOISE_ONLY", "insunits": 4, "texts": [{"handle": "N1", "text": "NOTE 123"}]}
    res_noise = detect_drawing_gaps_and_conflicts([noise_only])
    assert res_noise["status"] == "INSUFFICIENT_EVIDENCE"
    assert not any(f["finding_id"] == "F_NO_GAPS_OR_CONFLICTS" for f in res_noise["findings"])

    # Positive control: full valid package -> PASS with substantive_checks_ran >= 3
    res_ok = detect_drawing_gaps_and_conflicts([_ga(), _mcn()], partial_package=True)
    assert res_ok["status"] == "PASS"
    assert res_ok["observed_scope"]["substantive_checks_ran"] >= 3


def _schema_match(instance: Any, schema: dict[str, Any]) -> bool:
    """Minimal strict Draft 2020-12 JSON Schema subset evaluator (no third-party dep)."""
    if "not" in schema and _schema_match(instance, schema["not"]):
        return False
    if "allOf" in schema and not all(_schema_match(instance, sub) for sub in schema["allOf"]):
        return False
    if "anyOf" in schema and not any(_schema_match(instance, sub) for sub in schema["anyOf"]):
        return False
    if "oneOf" in schema and sum(1 for sub in schema["oneOf"] if _schema_match(instance, sub)) != 1:
        return False
    if "if" in schema and "then" in schema and _schema_match(instance, schema["if"]):
        if not _schema_match(instance, schema["then"]):
            return False
    if "const" in schema and instance != schema["const"]:
        return False
    if "enum" in schema and instance not in schema["enum"]:
        return False
    if "type" in schema:
        allowed = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        type_ok = False
        for tname in allowed:
            if tname == "null" and instance is None:
                type_ok = True
            elif tname == "boolean" and type(instance) is bool:
                type_ok = True
            elif tname == "integer" and type(instance) is int:
                type_ok = True
            elif tname == "number" and isinstance(instance, (int, float)) and type(instance) is not bool:
                type_ok = True
            elif tname == "string" and isinstance(instance, str):
                type_ok = True
            elif tname == "array" and isinstance(instance, list):
                type_ok = True
            elif tname == "object" and isinstance(instance, dict):
                type_ok = True
        if not type_ok:
            return False
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            return False
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            return False
    if isinstance(instance, (int, float)) and type(instance) is not bool:
        if "minimum" in schema and instance < schema["minimum"]:
            return False
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            return False
        if "items" in schema and isinstance(schema["items"], dict):
            if not all(_schema_match(elem, schema["items"]) for elem in instance):
                return False
        if "contains" in schema and not any(_schema_match(elem, schema["contains"]) for elem in instance):
            return False
    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                return False
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            if any(k not in props for k in instance):
                return False
        for k, sub in props.items():
            if k in instance and not _schema_match(instance[k], sub):
                return False
    return True


def test_p2_schema_python_proposal_gate_parity() -> None:
    """P2: check result & pack JSON Schemas must enforce the exact same gates as Python validators."""
    pack_schema = json.loads((_REPO_ROOT / "contracts/marine-knowledge/marine-knowledge-pack.schema.json").read_text(encoding="utf-8"))
    res_schema = json.loads((_REPO_ROOT / "contracts/marine-knowledge/marine-check-result.schema.json").read_text(encoding="utf-8"))

    # Valid pack matches pack JSON schema, and private-source non-null verbatim fails schema
    pack = get_marine_knowledge_pack()
    assert _schema_match(pack, pack_schema)

    leaked_pack = json.loads(json.dumps(pack))
    leaked_tb = next(r for r in leaked_pack["rules"] if r["source_id"] == "VIMARU_VETAU_CH1")
    leaked_tb["excerpt_disposition"] = "PRIVATE_SOURCE_SUMMARY_ONLY"
    leaked_tb["verbatim_excerpt"] = "Forbidden committed literal"
    assert not _schema_match(leaked_pack, pack_schema)

    # Valid result with proposal matches schema
    res = detect_drawing_gaps_and_conflicts([_ga(insunits=0)], partial_package=True)
    assert res["proposal_only_actions"]
    assert _schema_match(res, res_schema)

    # 1. Poisoned proposal.evidence (cad_mutation=True / proposal_only=False) rejected by BOTH Python & Schema
    bad_ev = json.loads(json.dumps(res))
    bad_ev["proposal_only_actions"][0]["evidence"] = {"cad_mutation": True}
    with pytest.raises(MarineKnowledgeError, match="PROPOSAL_EVIDENCE_INVALID"):
        validate_check_result(bad_ev)
    assert not _schema_match(bad_ev, res_schema)

    bad_ev2 = json.loads(json.dumps(res))
    bad_ev2["proposal_only_actions"][0]["evidence"] = {"proposal_only": False}
    with pytest.raises(MarineKnowledgeError, match="PROPOSAL_EVIDENCE_INVALID"):
        validate_check_result(bad_ev2)
    assert not _schema_match(bad_ev2, res_schema)

    # 2. Bad pack_sha256, non-disabled null pack_sha256, empty finding pages, and missing required_core_gates rejected by BOTH
    bad_sha = json.loads(json.dumps(res))
    bad_sha["pack_sha256"] = "not-a-sha"
    with pytest.raises(MarineKnowledgeError):
        validate_check_result(bad_sha)
    assert not _schema_match(bad_sha, res_schema)

    bad_null_sha = json.loads(json.dumps(res))
    bad_null_sha["pack_sha256"] = None
    with pytest.raises(MarineKnowledgeError):
        validate_check_result(bad_null_sha)
    assert not _schema_match(bad_null_sha, res_schema)

    bad_pages = json.loads(json.dumps(res))
    bad_pages["findings"][0]["pdf_page"] = []
    bad_pages["findings"][0]["reg_page"] = []
    with pytest.raises(MarineKnowledgeError):
        validate_check_result(bad_pages)
    assert not _schema_match(bad_pages, res_schema)

    bad_gates = json.loads(json.dumps(res))
    bad_gates["proposal_only_actions"][0]["required_core_gates"] = ["CAD_CORE_SOURCE_SUPPORT", "OTHER_GATE"]
    with pytest.raises(MarineKnowledgeError):
        validate_check_result(bad_gates)
    assert not _schema_match(bad_gates, res_schema)

    # Positive control: explicit proposal builder still passes
    prop = build_marine_core_proposal(
        target_drawing_id="MV0_GA",
        action_kind="COMPLETE_TITLE_BLOCK_FIELDS",
        evidence={"blank_fields": ["OWNER"]},
    )
    assert prop["cad_mutation"] is False and prop["proposal_only"] is True


def test_mv0_04_followup_unknown_exception_eligibility_and_tristate_controls() -> None:
    """Luna PR #574 follow-up P1: unknown 2.4.6-9 eligibility must stay INSUFFICIENT_EVIDENCE, never CONFLICT."""
    # 1. Exact Luna acceptance replay: steel dry cargo, L=42.00m, 3 bulkheads, NO 2.4.6-9 facts -> INSUFFICIENT_EVIDENCE
    ga_42_unknown = _ga(drawing_id="GA_42_UNKNOWN", length_line="Chiều dài tàu L = 42.00 m", bulkheads=3)
    res_unknown = evaluate_regulation_applicability_and_submittal([ga_42_unknown])
    assert res_unknown["status"] == "INSUFFICIENT_EVIDENCE"
    mk08_u = next(f for f in res_unknown["findings"] if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
    assert mk08_u["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert mk08_u["finding_id"] == "F_WATERTIGHT_BULKHEAD_2_4_6_9_ELIGIBILITY_UNKNOWN"
    assert mk08_u["evidence"]["exception_2_4_6_9_eligibility"] == "UNKNOWN"
    assert "2.4.6-9" in mk08_u["clause"]

    # 2. Partial exception negation (single-side ONLY, container still unknown) -> still INSUFFICIENT_EVIDENCE
    ga_42_partial = _ga(
        drawing_id="GA_42_SINGLE_ONLY",
        length_line="Chiều dài tàu L = 42.00 m",
        bulkheads=3,
        extra_texts=[{"handle": "NS1", "text": "HULL STRUCTURE : SINGLE SIDE", "x": 60000.0, "y": 5400.0}],
    )
    res_partial = evaluate_regulation_applicability_and_submittal([ga_42_partial])
    assert res_partial["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(
        f["finding_id"] == "F_WATERTIGHT_BULKHEAD_2_4_6_9_ELIGIBILITY_UNKNOWN" and f["verdict"] == "INSUFFICIENT_EVIDENCE"
        for f in res_partial["findings"]
    )

    # 3. Verified INAPPLICABLE (single-side AND non-container, or negated phrase) -> hard CONFLICT
    ga_42_inapp = _ga(
        drawing_id="GA_42_INAPP",
        length_line="Chiều dài tàu L = 42.00 m",
        bulkheads=3,
        ship_type_line="SHIP TYPE : DRY CARGO NON-CONTAINER",
        extra_texts=[
            {"handle": "NS2", "text": "HULL STRUCTURE : KHÔNG CÓ MẠN KÉP", "x": 60000.0, "y": 5400.0},
        ],
    )
    res_inapp = evaluate_regulation_applicability_and_submittal([ga_42_inapp])
    assert res_inapp["status"] == "CONFLICT"
    mk08_c = next(f for f in res_inapp["findings"] if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
    assert mk08_c["verdict"] == "CONFLICT"
    assert mk08_c["finding_id"] == "F_WATERTIGHT_BULKHEAD_COUNT"
    assert mk08_c["evidence"]["exception_2_4_6_9_eligibility"] == "INAPPLICABLE"

    # 4. Contradictory double-side vs single-side markers -> CONFLICTING_OR_UNKNOWN (paused, not false count CONFLICT)
    ga_42_contra = _ga(
        drawing_id="GA_42_CONTRA_EXC",
        length_line="Chiều dài tàu L = 42.00 m",
        bulkheads=3,
        extra_texts=[
            {"handle": "C1", "text": "HULL STRUCTURE : ĐÁY ĐÔI MẠN KÉP", "x": 60000.0, "y": 5400.0},
            {"handle": "C2", "text": "HULL STRUCTURE : SINGLE SIDE", "x": 60000.0, "y": 5600.0},
        ],
    )
    res_contra = evaluate_regulation_applicability_and_submittal([ga_42_contra])
    assert res_contra["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(
        f["evidence"].get("exception_2_4_6_9_eligibility") == "CONFLICTING_OR_UNKNOWN"
        for f in res_contra["findings"]
        if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT"
    )

    # 5. Unconditional Clause 2.4.6-2 floor (<2 bulkheads at L=42m) -> hard CONFLICT regardless of unknown 2.4.6-9
    ga_42_one = _ga(drawing_id="GA_42_ONE_BH", length_line="Chiều dài tàu L = 42.00 m", bulkheads=1)
    assert evaluate_regulation_applicability_and_submittal([ga_42_one])["status"] == "CONFLICT"

    # 6. Positive control: L=40.00m with 3 bulkheads and unknown exception -> PASS
    ga_40_ok = _ga(drawing_id="GA_40_OK", length_line="Chiều dài tàu L = 40.00 m", bulkheads=3)
    assert evaluate_regulation_applicability_and_submittal([ga_40_ok, _mcn(length_line="Chiều dài tàu L = 40.00 m")])["status"] == "PASS"

    # 7. Positive control: container ship via SHIP TYPE at L=42m with 3 bulkheads -> APPLICABLE -> INSUFFICIENT_EVIDENCE
    ga_42_cont = _ga(
        drawing_id="GA_42_CONT",
        length_line="Chiều dài tàu L = 42.00 m",
        ship_type_line="SHIP TYPE : DRY CARGO CONTAINER",
        bulkheads=3,
    )
    res_cont = evaluate_regulation_applicability_and_submittal([ga_42_cont])
    assert res_cont["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_WATERTIGHT_BULKHEAD_2_4_6_9_EXCEPTION_QUALIFIED" for f in res_cont["findings"])


def test_mv0_04_exception_facts_require_vessel_scope_and_typed_boolean_metrics() -> None:
    """Optional equipment text cannot decide hull eligibility; typed boolean inputs stay out of dimensional validation."""
    equipment_note = _ga(
        drawing_id="GA_42_EQUIPMENT_NOTE",
        length_line="Chiều dài tàu L = 42.00 m",
        bulkheads=3,
        extra_texts=[
            {"handle": "EQ1", "text": "LIFEBOAT EQUIPMENT: SINGLE SIDE, NON-CONTAINER", "x": 60000.0, "y": 5400.0},
        ],
    )
    note_result = evaluate_regulation_applicability_and_submittal([equipment_note])
    note_finding = next(
        f for f in note_result["findings"]
        if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT"
    )
    assert note_result["status"] == "INSUFFICIENT_EVIDENCE"
    assert note_finding["finding_id"] == "F_WATERTIGHT_BULKHEAD_2_4_6_9_ELIGIBILITY_UNKNOWN"
    assert note_finding["evidence"]["exception_2_4_6_9_eligibility"] == "UNKNOWN"

    # Explicit typed facts are accepted as scope facts, not treated as numeric dimensions.
    for applicable, expected_eligibility, expected_verdict in (
        (True, "APPLICABLE", "INSUFFICIENT_EVIDENCE"),
        (False, "INAPPLICABLE", "CONFLICT"),
    ):
        typed = _ga(
            drawing_id=f"GA_42_TYPED_{applicable}",
            length_line="Chiều dài tàu L = 42.00 m",
            bulkheads=3,
            extra_metrics={"bulkhead_2_4_6_9_exception_applicable": applicable},
        )
        typed_result = evaluate_regulation_applicability_and_submittal([typed])
        assert not any(f["finding_id"] == "F_SCOPE_CONFLICT" for f in typed_result["findings"])
        typed_finding = next(
            f for f in typed_result["findings"]
            if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT"
        )
        assert typed_result["status"] == expected_verdict
        assert typed_finding["verdict"] == expected_verdict
        assert typed_finding["evidence"]["exception_2_4_6_9_eligibility"] == expected_eligibility


def test_mv0_06_every_supported_ap_fp_view_span_is_checked_order_independently() -> None:
    """A bad supported view span cannot be hidden by whichever AP/FP pair is visited first."""
    def observation(*, short_span_view: str, good_span_view: str) -> dict[str, Any]:
        ga = _ga(drawing_id="GA_MULTI_SPAN", length_line="Chiều dài tàu L = 52.00 m", bulkheads=4)
        ga["texts"] = [text for text in ga["texts"] if text["handle"] not in {"G10", "G11"}]
        for view_id, fp_x in ((short_span_view, 1052.0), (good_span_view, 53000.0)):
            ga["texts"].extend(
                [
                    {"handle": f"{view_id}_AP", "text": "A.P", "x": 1000.0, "y": 0.0, "height": 300.0, "view_id": view_id},
                    {"handle": f"{view_id}_FP", "text": "F.P", "x": fp_x, "y": 0.0, "height": 300.0, "view_id": view_id},
                ]
            )
        return ga

    short_first = detect_drawing_gaps_and_conflicts(
        [observation(short_span_view="A", good_span_view="B")], partial_package=True,
    )
    good_first = detect_drawing_gaps_and_conflicts(
        [observation(short_span_view="B", good_span_view="A")], partial_package=True,
    )
    for result in (short_first, good_first):
        mismatch = next(
            (f for f in result["findings"] if f["finding_id"] == "F_UNIT_OR_SCALE_MISMATCH_1000X"),
            None,
        )
        assert mismatch is not None
        assert mismatch["verdict"] == "CONFLICT"
        assert mismatch["evidence"]["cad_ap_fp_dx"] == 52.0
        assert result["status"] == "CONFLICT"


def test_mv0_06_title_scale_cannot_reconcile_modelspace_span_mismatch() -> None:
    """A title scale without view-space binding cannot turn conflicting modelspace geometry into PASS."""
    ga = _ga(drawing_id="GA_SCALE_CANNOT_HIDE_MODEL_MISMATCH", length_line="Chiều dài tàu L = 52.00 m", bulkheads=4)
    ga.pop("claimed_scale", None)
    ga["texts"] = [text for text in ga["texts"] if text["handle"] not in {"G10", "G11"}]
    ga["texts"].append({"handle": "SCALE1", "text": "SCALE 1:1000", "x": 60000.0, "y": 5500.0, "height": 250.0})
    for view_id, fp_x in (("INSERT_LARGE", 53000.0), ("INSERT_SMALL", 1052.0)):
        ga["texts"].extend(
            [
                {"handle": f"{view_id}_AP", "text": "A.P", "x": 1000.0, "y": 0.0, "height": 300.0, "view_id": view_id},
                {"handle": f"{view_id}_FP", "text": "F.P", "x": fp_x, "y": 0.0, "height": 300.0, "view_id": view_id},
            ]
        )
    # A 1:1000 title scale needs modelspace text heights scaled accordingly to
    # keep the independent printed-text gate valid; only the scale note varies.
    for text in ga["texts"]:
        text["height"] = float(text.get("height", 0.0)) * 10.0

    result = detect_drawing_gaps_and_conflicts([ga], partial_package=True)
    assert result["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_UNIT_OR_SCALE_MISMATCH_1000X" for f in result["findings"])


def test_mv0_04_incidental_hull_text_and_unverified_boolean_cannot_decide_exception() -> None:
    """Equipment/reference hull text and OCR-provenance booleans do not establish vessel exception eligibility."""
    for idx, note in enumerate(
        (
            "LIFEBOAT HULL STRUCTURE : DOUBLE HULL",
            "REFERENCE ONLY: HULL STRUCTURE : DOUBLE HULL",
        ),
        start=1,
    ):
        ga = _ga(
            drawing_id=f"GA_42_NON_VESSEL_HULL_{idx}",
            length_line="Chiều dài tàu L = 42.00 m",
            bulkheads=3,
            extra_texts=[{"handle": f"REF{idx}", "text": note, "x": 60000.0, "y": 5400.0}],
        )
        result = evaluate_regulation_applicability_and_submittal([ga])
        finding = next(
            f for f in result["findings"]
            if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT"
        )
        assert result["status"] == "INSUFFICIENT_EVIDENCE"
        assert finding["evidence"]["exception_2_4_6_9_eligibility"] == "UNKNOWN"

    unverified_boolean = _ga(
        drawing_id="GA_42_UNVERIFIED_BOOLEAN",
        length_line="Chiều dài tàu L = 42.00 m",
        bulkheads=3,
        extra_metrics={"bulkhead_2_4_6_9_exception_applicable": False},
        metric_provenance={"bulkhead_2_4_6_9_exception_applicable": "UNVERIFIED_OCR_TEXT"},
    )
    result = evaluate_regulation_applicability_and_submittal([unverified_boolean])
    finding = next(
        f for f in result["findings"]
        if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT"
    )
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert finding["evidence"]["exception_2_4_6_9_eligibility"] == "UNKNOWN"


def test_mv0_06_followup_independent_orientation_and_1000x_span_coverage() -> None:
    """Luna PR #574 follow-up P1: split bow orientation and 1000x span coverage accurately."""
    # 1. Unitless ($INSUNITS=0) with clean single A.P + F.P pair -> orientation ran, 1000x span did NOT
    ga_unitless_clean_apfp = _ga(drawing_id="GA_U0_CLEAN_APFP", insunits=0)
    res_u0 = detect_drawing_gaps_and_conflicts([ga_unitless_clean_apfp], partial_package=True)
    assert res_u0["status"] == "INSUFFICIENT_EVIDENCE"
    assert any("Bow direction (A.P vs F.P) orientation check" == chk for chk in res_u0["checks_executed"])
    assert not any("1000x" in chk for chk in res_u0["checks_executed"])
    assert any("1000x CAD A.P-to-F.P span check" in chk for chk in res_u0["checks_not_executed"])

    # 2. Unitless with unpaired 1 A.P + 4 F.P (Marine-7000 GA7000 pattern) -> NEITHER orientation NOR span in checks_executed
    ga_unpaired = _ga(
        drawing_id="GA_U0_UNPAIRED",
        insunits=0,
        extra_texts=[
            {"handle": "FP2", "text": "F.P", "x": 52500.0, "y": 500.0, "height": 300.0},
            {"handle": "FP3", "text": "F.P", "x": 52800.0, "y": 900.0, "height": 300.0},
        ],
    )
    res_unpaired = detect_drawing_gaps_and_conflicts([ga_unpaired], partial_package=True)
    assert res_unpaired["status"] == "INSUFFICIENT_EVIDENCE"
    assert not any("Bow direction" in chk for chk in res_unpaired["checks_executed"])
    assert not any("1000x" in chk for chk in res_unpaired["checks_executed"])
    assert any("Bow direction" in chk and "unresolved" in chk.lower() for chk in res_unpaired["checks_not_executed"])
    assert any("1000x" in chk for chk in res_unpaired["checks_not_executed"])

    # 3. Calibrated ($INSUNITS=4) with clean single A.P + F.P pair -> BOTH orientation and 1000x span in checks_executed -> PASS
    ga_ok = _ga(drawing_id="GA_MM_OK", insunits=4)
    res_ok = detect_drawing_gaps_and_conflicts([ga_ok], partial_package=True)
    assert res_ok["status"] == "PASS"
    assert any("Bow direction (A.P vs F.P) orientation check" == chk for chk in res_ok["checks_executed"])
    assert any("1000x CAD A.P-to-F.P span vs declared length check" == chk for chk in res_ok["checks_executed"])

    # 4. Reversed single A.P > F.P -> F_BOW_ORIENTATION CONFLICT + orientation in checks_executed
    ga_rev = _ga(drawing_id="GA_MM_REV", insunits=4)
    for t in ga_rev["texts"]:
        if t["text"] == "A.P":
            t["x"] = 55000.0
        elif t["text"] == "F.P":
            t["x"] = 1000.0
    res_rev = detect_drawing_gaps_and_conflicts([ga_rev], partial_package=True)
    assert res_rev["status"] == "CONFLICT"
    assert any("F_BOW_ORIENTATION" in f["finding_id"] and f["verdict"] == "CONFLICT" for f in res_rev["findings"])
    assert any("Bow direction (A.P vs F.P) orientation check" == chk for chk in res_rev["checks_executed"])
