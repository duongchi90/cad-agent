"""Causal RED->GREEN regression tests and positive controls for MK574-01..MK574-13 (PR #574)."""

from __future__ import annotations

import hashlib
from typing import Any

import fitz
import pytest

from cad_agent.marine_knowledge import (
    MarineKnowledgeError,
    classify_marine_drawing,
    detect_drawing_gaps_and_conflicts,
    evaluate_regulation_applicability_and_submittal,
    get_marine_knowledge_pack,
    get_marine_source_manifest,
    normalize_observation,
    observe_dxf_bytes,
    validate_check_result,
    verify_source_citation,
)
from cad_agent.marine_knowledge.contracts import SOURCE_MANIFEST_SCHEMA_VERSION, seal_source_manifest


def _base_ga(
    *,
    drawing_id: str = "MK574_GA",
    length_line: str = "Chiều dài tàu L = 52.00 m",
    class_line: str = "CẤP TÀU : VR-SB",
    ship_type_line: str = "SHIP TYPE : DRY CARGO",
    material_line: str | None = "HULL MATERIAL : STEEL",
    draft_line: str = "T = 3.10 m",
    bulkheads: Any = 4,
    extra_texts: list[dict[str, Any]] | None = None,
    extra_metrics: dict[str, Any] | None = None,
    metric_provenance: dict[str, str] | None = None,
    include_drawing_id: bool = True,
) -> dict[str, Any]:
    texts: list[dict[str, Any]] = [
        {"handle": "G1", "text": "BẢN VẼ BỐ TRÍ CHUNG TOÀN TÀU", "x": 500.0, "y": 500.0, "height": 350.0},
        {"handle": "G2", "text": "KHOANG HÀNG SỐ 1 - BUỒNG MÁY - VÁCH CHỐNG VA", "x": 20000.0, "y": 2000.0, "height": 260.0},
        {"handle": "G3", "text": class_line, "x": 60000.0, "y": 1000.0, "height": 250.0},
        {"handle": "G4", "text": length_line, "x": 60000.0, "y": 1500.0, "height": 250.0},
        {"handle": "G5", "text": "B = 9.60 m", "x": 60000.0, "y": 2000.0, "height": 250.0},
        {"handle": "G6", "text": "D = 4.20 m", "x": 60000.0, "y": 2500.0, "height": 250.0},
        {"handle": "G7", "text": draft_line, "x": 60000.0, "y": 3000.0, "height": 250.0},
        {"handle": "G8", "text": "MAIN ENGINE : 2x550 HP", "x": 60000.0, "y": 3500.0, "height": 250.0},
        {"handle": "G9", "text": "PORT OF REGISTRY : HAI PHONG", "x": 60000.0, "y": 4500.0, "height": 250.0},
        {"handle": "G10", "text": "A.P", "x": 1000.0, "y": 0.0, "height": 300.0},
        {"handle": "G11", "text": "F.P", "x": 53000.0, "y": 0.0, "height": 300.0},
    ]
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

    payload: dict[str, Any] = {
        "drawing_code": "GA-01-01",
        "insunits": 4,
        "measurement": 1,
        "claimed_scale": 100.0,
        "texts": texts,
        "structural_metrics": metrics,
        "blank_fields": [],
    }
    if include_drawing_id:
        payload["drawing_id"] = drawing_id
    if metric_provenance is not None:
        payload["metric_provenance"] = dict(metric_provenance)
    return payload


def _base_mcn(
    *,
    drawing_id: str = "MK574_MCN",
    length_line: str = "Chiều dài tàu L = 52.00 m",
    class_line: str = "CẤP TÀU : VR-SB",
    ship_type_line: str = "SHIP TYPE : DRY CARGO",
    material_line: str | None = "HULL MATERIAL : STEEL",
    draft_line: str = "T = 3.10 m",
    db_mm: Any = 750.0,
    girder_mm: Any = 2200.0,
    floor_mm: Any = 1800.0,
    extra_texts: list[dict[str, Any]] | None = None,
    extra_metrics: dict[str, Any] | None = None,
    metric_provenance: dict[str, str] | None = None,
    include_drawing_id: bool = True,
) -> dict[str, Any]:
    texts: list[dict[str, Any]] = [
        {"handle": "M1", "text": "MẶT CẮT NGANG SƯỜN GIỮA", "x": 500.0, "y": 500.0, "height": 200.0},
        {"handle": "M2", "text": "ĐÁY ĐÔI - ĐÀ NGANG ĐẶC", "x": 1000.0, "y": 600.0, "height": 150.0},
        {"handle": "M3", "text": class_line, "x": 4000.0, "y": 1000.0, "height": 150.0},
        {"handle": "M4", "text": length_line, "x": 4000.0, "y": 1250.0, "height": 150.0},
        {"handle": "M5", "text": "B = 9.60 m", "x": 4000.0, "y": 1500.0, "height": 150.0},
        {"handle": "M6", "text": "D = 4.20 m", "x": 4000.0, "y": 1750.0, "height": 150.0},
        {"handle": "M7", "text": draft_line, "x": 4000.0, "y": 2000.0, "height": 150.0},
        {"handle": "M8", "text": "MAIN ENGINE : 2x550 HP", "x": 4000.0, "y": 2250.0, "height": 150.0},
    ]
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
    if extra_metrics:
        metrics.update(extra_metrics)

    payload: dict[str, Any] = {
        "drawing_code": "KC-02-01",
        "insunits": 4,
        "measurement": 1,
        "claimed_scale": 50.0,
        "texts": texts,
        "structural_metrics": metrics,
        "blank_fields": [],
    }
    if include_drawing_id:
        payload["drawing_id"] = drawing_id
    if metric_provenance is not None:
        payload["metric_provenance"] = dict(metric_provenance)
    return payload


def _make_multi_clause_pdf_and_manifest() -> tuple[bytes, dict[str, Any]]:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text(
        (72, 72),
        "19 SYNTH REG\n"
        "2.1.1 Alpha rule requires double bottom minimum height 700 mm.\n"
        "2.1.2 Beta rule governs totally separate rudder shaft torque limits.\n"
        "Quotation: 2.1.1 Alpha rule requires double bottom minimum height 700 mm.\n",
    )
    p2 = doc.new_page()
    p2.insert_text(
        (72, 72),
        "20 SYNTH REG\n"
        "Additional requirements\n"
        "Additional requirements are provisions outside this standard.\n"
        "Ship dimensions\n"
        "1 Ship length (L) is measured on the full load waterline.\n"
        "Aft perpendicular\n"
        "Aft perpendicular passes through the rudder stock axis.\n",
    )
    doc.set_toc(
        [
            [1, "2.1.1 Alpha rule", 1],
            [1, "2.1.2 Beta rule", 1],
            [1, "1.4.37 Additional requirements", 2],
            [1, "1.4.43 Ship dimensions", 2],
            [1, "1.4.44 Aft perpendicular", 2],
        ]
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": "MK574_01_MANIFEST",
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [
                {
                    "source_id": "SYNTH_REG_CLAUSE_SPAN",
                    "title": "Synthetic Multi-Clause Regulation PDF",
                    "document_kind": "REGULATION",
                    "version": "2025",
                    "origin": "synthetic-in-memory",
                    "sha256": sha,
                    "page_count": 2,
                    "applicable_scope": ["test"],
                    "usage_rights": "OPEN_ACADEMIC_RESEARCH",
                    "commit_prohibited": True,
                    "usage_status": "ACTIVE_INDEXED",
                    "notes": "Synthetic PDF for MK574-01 clause-span binding.",
                }
            ],
        }
    )
    return pdf_bytes, manifest


def test_mk574_01_citation_binds_excerpt_to_clause_span() -> None:
    """MK574-01: reject wrong-clause excerpt on same page and unanchored clauses; accept true clause-bound excerpt."""
    pdf_bytes, manifest = _make_multi_clause_pdf_and_manifest()
    sha = manifest["sources"][0]["sha256"]

    # 1. Wrong clause on same page (2.1.1 citing excerpt from 2.1.2) MUST fail
    wrong_clause_cite = {
        "source_id": "SYNTH_REG_CLAUSE_SPAN",
        "source_sha256": sha,
        "source_version": "2025",
        "clause": "2.1.1 Alpha rule",
        "pdf_page": [1],
        "reg_page": [19],
        "verbatim_excerpt": "Beta rule governs totally separate rudder shaft torque limits.",
    }
    with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
        verify_source_citation(wrong_clause_cite, manifest, source_bytes=pdf_bytes)

    # 2. Unanchored / nonsense clause MUST NOT reach CLAUSE_CONTENT_VERIFIED
    nonsense_clause_cite = {
        "source_id": "SYNTH_REG_CLAUSE_SPAN",
        "source_sha256": sha,
        "source_version": "2025",
        "clause": "NONSENSE NO CLAUSE ANCHOR",
        "pdf_page": [1],
        "reg_page": [19],
        "verbatim_excerpt": "Alpha rule requires double bottom minimum height 700 mm.",
    }
    with pytest.raises(MarineKnowledgeError, match="CITATION_CLAUSE_PAGE_MISMATCH"):
        verify_source_citation(nonsense_clause_cite, manifest, source_bytes=pdf_bytes)

    # 3. Outline-numbered page (like QCVN 72): citing 1.4.43 with excerpt from 1.4.37 on same page MUST fail
    wrong_outline_slice = {
        "source_id": "SYNTH_REG_CLAUSE_SPAN",
        "source_sha256": sha,
        "source_version": "2025",
        "clause": "1.4.43 Ship dimensions",
        "pdf_page": [2],
        "reg_page": [20],
        "verbatim_excerpt": "Additional requirements are provisions outside this standard.",
    }
    with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
        verify_source_citation(wrong_outline_slice, manifest, source_bytes=pdf_bytes)

    # 4. Positive controls: excerpt truly inside cited clause passes SOURCE_CONTENT_VERIFIED
    good_body = verify_source_citation(
        {
            **wrong_clause_cite,
            "verbatim_excerpt": "Alpha rule requires double bottom minimum height 700 mm.",
        },
        manifest,
        source_bytes=pdf_bytes,
    )
    assert good_body["verification_level"] == "SOURCE_CONTENT_VERIFIED"

    good_outline = verify_source_citation(
        {
            **wrong_outline_slice,
            "verbatim_excerpt": "Ship length (L) is measured on the full load waterline.",
        },
        manifest,
        source_bytes=pdf_bytes,
    )
    assert good_outline["verification_level"] == "SOURCE_CONTENT_VERIFIED"

    # Caller-provided clause order cannot redefine document order in the PDF.
    ordered_multi = verify_source_citation(
        {
            "source_id": "SYNTH_REG_CLAUSE_SPAN",
            "source_sha256": sha,
            "source_version": "2025",
            "clause": "2.1.1 Alpha rule; 2.1.2 Beta rule",
            "pdf_page": [1],
            "reg_page": [19],
            "verbatim_excerpt": (
                "Alpha rule requires double bottom minimum height 700 mm..."
                "Beta rule governs totally separate rudder shaft torque limits."
            ),
        },
        manifest,
        source_bytes=pdf_bytes,
    )
    assert ordered_multi["verification_level"] == "SOURCE_CONTENT_VERIFIED"

    with pytest.raises(MarineKnowledgeError, match="CITATION_CLAUSE_DOCUMENT_ORDER_MISMATCH"):
        verify_source_citation(
            {
                "source_id": "SYNTH_REG_CLAUSE_SPAN",
                "source_sha256": sha,
                "source_version": "2025",
                "clause": "2.1.2 Beta rule; 2.1.1 Alpha rule",
                "pdf_page": [1],
                "reg_page": [19],
                "verbatim_excerpt": (
                    "Beta rule governs totally separate rudder shaft torque limits..."
                    "Alpha rule requires double bottom minimum height 700 mm."
                ),
            },
            manifest,
            source_bytes=pdf_bytes,
        )

    with pytest.raises(MarineKnowledgeError, match="CITATION_PDF_PAGE_ORDER_INVALID"):
        verify_source_citation(
            {
                "source_id": "SYNTH_REG_CLAUSE_SPAN",
                "source_sha256": sha,
                "source_version": "2025",
                "clause": "2.1.1 Alpha rule",
                "pdf_page": [2, 1],
                "reg_page": [20, 19],
                "verbatim_excerpt": "Alpha rule requires double bottom minimum height 700 mm.",
            },
            manifest,
            source_bytes=pdf_bytes,
        )

    # A later quotation that repeats Alpha cannot rebind the second resolved slice
    # after Beta and make caller-supplied reverse clause order appear document-ordered.
    with pytest.raises(MarineKnowledgeError, match="CITATION_CLAUSE_DOCUMENT_ORDER_MISMATCH"):
        verify_source_citation(
            {
                "source_id": "SYNTH_REG_CLAUSE_SPAN",
                "source_sha256": sha,
                "source_version": "2025",
                "clause": "2.1.2 Beta rule; 2.1.1 Alpha rule",
                "pdf_page": [1],
                "reg_page": [19],
                "verbatim_excerpt": (
                    "Beta rule governs totally separate rudder shaft torque limits..."
                    "Alpha rule requires double bottom minimum height 700 mm."
                ),
            },
            manifest,
            source_bytes=pdf_bytes,
        )


def test_mk574_01_regulation_citation_rejects_omitted_intervening_page() -> None:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "19 SYNTH REG\n2.1.1 Alpha rule continues on the next page.\n")
    p2 = doc.new_page()
    p2.insert_text((72, 72), "20 SYNTH REG\n2.1.2 Beta rule governs a different requirement.\n")
    p3 = doc.new_page()
    p3.insert_text((72, 72), "21 SYNTH REG\nBeta continuation states rudder shaft torque limits.\n2.2 Closing rule.\n")
    doc.set_toc([[1, "2.1.1 Alpha rule", 1], [1, "2.1.2 Beta rule", 2], [1, "2.2 Closing rule", 3]])
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": "MK574_PAGE_GAP_MANIFEST",
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": "SYNTH_REG_PAGE_GAP", "title": "Synthetic page-gap regulation PDF",
                "document_kind": "REGULATION", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 3, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Synthetic citation page-gap regression.",
            }],
        }
    )
    with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
        verify_source_citation(
            {
                "source_id": "SYNTH_REG_PAGE_GAP", "source_sha256": sha, "source_version": "2025",
                "clause": "2.1.1 Alpha rule", "pdf_page": [1, 3], "reg_page": [19, 21],
                "verbatim_excerpt": "Beta continuation states rudder shaft torque limits.",
            },
            manifest,
            source_bytes=pdf_bytes,
        )


def test_mk574_r20_regulation_excerpt_must_be_on_a_cited_page() -> None:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "19 SYNTH REG\n2.1 Alpha rule opening paragraph.\n")
    p2 = doc.new_page()
    p2.insert_text((72, 72), "20 SYNTH REG\nUNIQUE QUOTED REQUIREMENT ON OMITTED PAGE.\n")
    p3 = doc.new_page()
    p3.insert_text((72, 72), "21 SYNTH REG\n2.2 Closing rule.\n")
    doc.set_toc([[1, "2.1 Alpha rule", 1], [1, "2.2 Closing rule", 3]])
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": "MK574_R20_PAGE_CUSTODY",
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": "SYNTH_REG_R20_PAGE_CUSTODY", "title": "Synthetic page custody PDF",
                "document_kind": "REGULATION", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 3, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Synthetic citation page-custody regression.",
            }],
        }
    )
    base = {
        "source_id": "SYNTH_REG_R20_PAGE_CUSTODY", "source_sha256": sha, "source_version": "2025",
        "clause": "2.1 Alpha rule", "verbatim_excerpt": "UNIQUE QUOTED REQUIREMENT ON OMITTED PAGE.",
    }

    with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
        verify_source_citation({**base, "pdf_page": [1, 3], "reg_page": [19, 21]}, manifest, source_bytes=pdf_bytes)

    cited_interval = verify_source_citation(
        {**base, "pdf_page": [1, 2, 3], "reg_page": [19, 20, 21]}, manifest, source_bytes=pdf_bytes
    )
    assert cited_interval["verification_level"] == "SOURCE_CONTENT_VERIFIED"


def test_mk574_r20_regulation_excerpt_matching_does_not_duplicate_overlapping_clause_slices() -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "19 SYNTH REG\n2.1 Parent clause.\n2.1.1 Alpha rule.\nBRAVO EARLIER PHRASE.\n"
        "2.1.2 Beta rule.\nCHARLIE LATER PHRASE.\n2.2 Closing rule.\n",
    )
    doc.set_toc([[1, "2.1 Parent clause", 1], [2, "2.1.1 Alpha rule", 1], [2, "2.1.2 Beta rule", 1], [1, "2.2 Closing rule", 1]])
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": "MK574_R20_OVERLAP",
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": "SYNTH_REG_R20_OVERLAP", "title": "Synthetic overlapping clause PDF",
                "document_kind": "REGULATION", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 1, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Synthetic citation interval-overlap regression.",
            }],
        }
    )

    def citation(clause: str, excerpt: str) -> dict[str, Any]:
        return {
            "source_id": "SYNTH_REG_R20_OVERLAP", "source_sha256": sha, "source_version": "2025",
            "clause": clause, "pdf_page": [1], "reg_page": [19], "verbatim_excerpt": excerpt,
        }

    for clause, excerpt in (
        ("2.1; 2.1.1", "CHARLIE LATER PHRASE...BRAVO EARLIER PHRASE."),
        ("2.1; 2.1.1", "BRAVO EARLIER PHRASE...BRAVO EARLIER PHRASE."),
    ):
        with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
            verify_source_citation(citation(clause, excerpt), manifest, source_bytes=pdf_bytes)

    ordered_siblings = verify_source_citation(
        citation("2.1.1; 2.1.2", "BRAVO EARLIER PHRASE...CHARLIE LATER PHRASE."),
        manifest,
        source_bytes=pdf_bytes,
    )
    assert ordered_siblings["verification_level"] == "SOURCE_CONTENT_VERIFIED"


def test_mk574_r21_citation_page_offsets_share_normalized_source_coordinates() -> None:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "19 SYNTH REG\n2.1 Alpha rule opening paragraph.\n")
    doc.new_page()  # Empty pages collapse to one normalized whitespace boundary.
    p3 = doc.new_page()
    p3.insert_text((72, 72), "21 SYNTH REG\nFIRSTCHARMATTERS.\n")
    p4 = doc.new_page()
    p4.insert_text((72, 72), "22 SYNTH REG\n2.2 Closing rule.\n")
    doc.set_toc([[1, "2.1 Alpha rule", 1], [1, "2.2 Closing rule", 4]])
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": "MK574_R21_NORMALIZED_PAGE_OFFSETS",
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": "SYNTH_REG_R21_OFFSETS", "title": "Synthetic blank-page offset PDF",
                "document_kind": "REGULATION", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 4, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Synthetic normalized page-offset regression.",
            }],
        }
    )
    citation = {
        "source_id": "SYNTH_REG_R21_OFFSETS", "source_sha256": sha, "source_version": "2025",
        "clause": "2.1 Alpha rule", "pdf_page": [1, 3, 4], "reg_page": [19, 21, 22],
        "verbatim_excerpt": "FIRSTCHARMATTERS.",
    }

    result = verify_source_citation(citation, manifest, source_bytes=pdf_bytes)
    assert result["verification_level"] == "SOURCE_CONTENT_VERIFIED"


def test_mk574_r21_blank_pages_cannot_shift_an_omitted_excerpt_into_a_cited_page() -> None:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "19 SYNTH REG\n2.1 Alpha rule opening paragraph.\n")
    for _ in range(7):
        doc.new_page()
    p9 = doc.new_page()
    p9.insert_text((72, 72), "27 SYNTH REG\n")
    p10 = doc.new_page()
    p10.insert_text((72, 72), "DENIED OMITTED PAGE REQUIREMENT.\n")
    p11 = doc.new_page()
    p11.insert_text((72, 72), "29 SYNTH REG\n2.2 Closing rule.\n")
    doc.set_toc([[1, "2.1 Alpha rule", 1], [1, "2.2 Closing rule", 11]])
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": "MK574_R21_BLANK_PAGE_CUSTODY",
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": "SYNTH_REG_R21_BLANK_CUSTODY", "title": "Synthetic blank-page custody PDF",
                "document_kind": "REGULATION", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 11, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Synthetic omitted-page blank-offset regression.",
            }],
        }
    )
    citation = {
        "source_id": "SYNTH_REG_R21_BLANK_CUSTODY", "source_sha256": sha, "source_version": "2025",
        "clause": "2.1 Alpha rule", "pdf_page": [1, 9, 11], "reg_page": [19, 27, 29],
        "verbatim_excerpt": "DENIED",
    }

    with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
        verify_source_citation(citation, manifest, source_bytes=pdf_bytes)


def test_mk574_r21_textbook_clause_context_keeps_omitted_pages() -> None:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "BEFORE GAP\n1.4 Applied heading.\nVALID TEXT FOR SECTION 1.4.\n")
    p2 = doc.new_page()
    p2.insert_text((72, 72), "1.5 Intervening section heading.\n")
    p3 = doc.new_page()
    p3.insert_text((72, 72), "AFTER GAP CLAIMED UNDER 1.4.\n")
    doc.set_toc([[1, "1.4 Applied heading", 1], [1, "1.5 Intervening section heading", 2]])
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": "MK574_R21_TEXTBOOK_GAP",
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": "SYNTH_TEXTBOOK_R21_GAP", "title": "Synthetic textbook gap PDF",
                "document_kind": "TEXTBOOK", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 3, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Synthetic noncontiguous textbook citation regression.",
            }],
        }
    )
    base = {
        "source_id": "SYNTH_TEXTBOOK_R21_GAP", "source_sha256": sha, "source_version": "2025",
        "clause": "1.4 Applied heading", "pdf_page": [1, 3], "verbatim_excerpt": "AFTER GAP CLAIMED UNDER 1.4.",
    }

    with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
        verify_source_citation(base, manifest, source_bytes=pdf_bytes)

    valid_cited_page_excerpt = verify_source_citation(
        {**base, "verbatim_excerpt": "VALID TEXT FOR SECTION 1.4."}, manifest, source_bytes=pdf_bytes
    )
    assert valid_cited_page_excerpt["verification_level"] == "SOURCE_CONTENT_VERIFIED"


def test_mk574_r22_textbook_omitted_outline_boundaries_do_not_verify_later_section_text() -> None:
    for case_id, boundary_text in (
        ("PUNCTUATED", "1.5. Intervening section heading."),
        ("SECTION_PREFIX", "Section 1.5 Intervening section heading."),
        ("SECTION_COLON", "Section 1.5: Intervening section heading."),
        ("SECTION_COLON_NO_SPACE", "Section 1.5:Intervening section heading."),
        ("OUTLINE_ONLY", ""),
    ):
        doc = fitz.open()
        p1 = doc.new_page()
        p1.insert_text((72, 72), "1.4 Applied heading.\nVALID TEXT FOR SECTION 1.4.\n")
        p2 = doc.new_page()
        if boundary_text:
            p2.insert_text((72, 72), boundary_text)
        p3 = doc.new_page()
        p3.insert_text((72, 72), "LATER SECTION TEXT MUST NOT VERIFY AS 1.4.\n")
        p4 = doc.new_page()
        p4.insert_text((72, 72), "1.6 Closing section heading.\n")
        toc = [[1, "1.4 Applied heading", 1], [1, "1.6 Closing section heading", 4]]
        if case_id == "OUTLINE_ONLY":
            toc.insert(1, [1, "1.5 Intervening section heading", 2])
        doc.set_toc(toc)
        pdf_bytes = doc.tobytes()
        doc.close()
        sha = hashlib.sha256(pdf_bytes).hexdigest()
        source_id = f"SYNTH_TEXTBOOK_R22_{case_id}"
        manifest = seal_source_manifest(
            {
                "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
                "manifest_id": source_id,
                "revision": "0.1.0",
                "status": "CANDIDATE_UNAPPROVED",
                "sources": [{
                    "source_id": source_id, "title": "Synthetic textbook boundary PDF",
                    "document_kind": "TEXTBOOK", "version": "2025", "origin": "synthetic-in-memory",
                    "sha256": sha, "page_count": 4, "applicable_scope": ["test"],
                    "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                    "usage_status": "ACTIVE_INDEXED", "notes": "Synthetic omitted-section boundary regression.",
                }],
            }
        )
        base = {
            "source_id": source_id, "source_sha256": sha, "source_version": "2025",
            "clause": "1.4 Applied heading", "pdf_page": [1, 3, 4],
            "verbatim_excerpt": "LATER SECTION TEXT MUST NOT VERIFY AS 1.4.",
        }

        with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
            verify_source_citation(base, manifest, source_bytes=pdf_bytes)

        positive = verify_source_citation(
            {**base, "verbatim_excerpt": "VALID TEXT FOR SECTION 1.4."},
            manifest,
            source_bytes=pdf_bytes,
        )
        assert positive["verification_level"] == "SOURCE_CONTENT_VERIFIED", case_id


def test_mk574_r23_unresolved_same_page_outline_sibling_does_not_verify_next_page() -> None:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "1.4 Applied heading.\nVALID SECTION 1.4 TEXT.\n")
    p2 = doc.new_page()
    p2.insert_text((72, 72), "UNRESOLVED SAME PAGE OUTLINE SIBLING TEXT.\n")
    p3 = doc.new_page()
    p3.insert_text((72, 72), "1.5 Closing section heading.\n")
    doc.set_toc(
        [
            [1, "Section 1.4 Applied heading", 1],
            [1, "Intervening same-page topic", 1],
            [1, "1.5 Closing section heading", 3],
        ]
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": "SYNTH_TEXTBOOK_R23_SAME_PAGE_OUTLINE",
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": "SYNTH_TEXTBOOK_R23_SAME_PAGE_OUTLINE", "title": "Synthetic textbook bookmark PDF",
                "document_kind": "TEXTBOOK", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 3, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Same-page unresolved outline sibling regression.",
            }],
        }
    )
    citation = {
        "source_id": "SYNTH_TEXTBOOK_R23_SAME_PAGE_OUTLINE", "source_sha256": sha, "source_version": "2025",
        "clause": "1.4 Applied heading", "pdf_page": [1, 2, 3],
        "verbatim_excerpt": "UNRESOLVED SAME PAGE OUTLINE SIBLING TEXT.",
    }
    result = verify_source_citation(citation, manifest, source_bytes=pdf_bytes)
    assert result["verification_level"] == "SOURCE_PAGE_VERIFIED"
    assert "CLAUSE_CONTENT_VERIFIED" not in result["verification_states"]

    positive = verify_source_citation(
        {**citation, "verbatim_excerpt": "VALID SECTION 1.4 TEXT."}, manifest, source_bytes=pdf_bytes
    )
    # The same-page sibling has no resolved text offset, so even a real excerpt
    # from that page cannot be promoted to content-verified on this evidence.
    assert positive["verification_level"] == "SOURCE_PAGE_VERIFIED"
    assert "CLAUSE_CONTENT_VERIFIED" not in positive["verification_states"]


def test_mk574_r24_inline_cross_reference_cannot_start_numbered_clause_span() -> None:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "1.3 Background\nSee Section 1.4 for a separate method.\nBACKGROUND ONLY TEXT.\n")
    p2 = doc.new_page()
    p2.insert_text((72, 72), "Section 1.4: Applied method\nACTUAL SECTION TEXT.\n")
    p3 = doc.new_page()
    p3.insert_text((72, 72), "Section 1.5: Closing section.\n")
    doc.set_toc([[1, "Section 1.4 Applied heading", 2], [1, "Section 1.5 Closing section", 3]])
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    source_id = "SYNTH_TEXTBOOK_R24_INLINE_CROSS_REFERENCE"
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": source_id,
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": source_id, "title": "Synthetic inline cross-reference PDF",
                "document_kind": "TEXTBOOK", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 3, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Inline reference must not anchor a clause citation.",
            }],
        }
    )
    base = {
        "source_id": source_id, "source_sha256": sha, "source_version": "2025",
        "clause": "1.4 Applied method", "pdf_page": [1, 2, 3],
    }
    with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
        verify_source_citation(
            {**base, "verbatim_excerpt": "BACKGROUND ONLY TEXT."},
            manifest,
            source_bytes=pdf_bytes,
        )
    positive = verify_source_citation(
        {**base, "verbatim_excerpt": "ACTUAL SECTION TEXT."}, manifest, source_bytes=pdf_bytes
    )
    assert positive["verification_level"] == "SOURCE_CONTENT_VERIFIED"


def test_mk574_r24_repeated_outline_sibling_title_uses_occurrence_after_clause_start() -> None:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "Appendix data\n4.3 Main section\nVALID SECTION 4.3 BODY.\n")
    p2 = doc.new_page()
    p2.insert_text((72, 72), "Appendix data\nAPPENDIX ONLY TEXT.\n")
    p3 = doc.new_page()
    p3.insert_text((72, 72), "4.4 Closing section.\n")
    doc.set_toc([[1, "4.3 Main section", 1], [1, "Appendix data", 1], [1, "4.4 Closing section", 3]])
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    source_id = "SYNTH_TEXTBOOK_R24_REPEATED_OUTLINE_TITLE"
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": source_id,
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": source_id, "title": "Synthetic repeated outline title PDF",
                "document_kind": "TEXTBOOK", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 3, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Earlier title duplicate must not mask later boundary.",
            }],
        }
    )
    result = verify_source_citation(
        {
            "source_id": source_id, "source_sha256": sha, "source_version": "2025",
            "clause": "4.3 Main section", "pdf_page": [1, 2, 3],
            "verbatim_excerpt": "APPENDIX ONLY TEXT.",
        },
        manifest,
        source_bytes=pdf_bytes,
    )
    assert result["verification_level"] != "SOURCE_CONTENT_VERIFIED"
    assert "CLAUSE_CONTENT_VERIFIED" not in result["verification_states"]


def test_mk574_r25_decimal_line_cannot_anchor_clause_and_punctuated_heading_is_valid() -> None:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "1.3 Background\n1.4% scale reference\nBACKGROUND ONLY TEXT.\n")
    p2 = doc.new_page()
    p2.insert_text((72, 72), "1.4. Applied method\nACTUAL SECTION TEXT.\n")
    p3 = doc.new_page()
    p3.insert_text((72, 72), "1.5 Closing section.\n")
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    source_id = "SYNTH_TEXTBOOK_R25_DECIMAL_PREFIX"
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": source_id,
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": source_id, "title": "Synthetic decimal-prefix PDF",
                "document_kind": "TEXTBOOK", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 3, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Decimal prefix is not a clause heading.",
            }],
        }
    )
    base = {
        "source_id": source_id, "source_sha256": sha, "source_version": "2025",
        "clause": "1.4 Applied method", "pdf_page": [1, 2, 3],
    }
    with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
        verify_source_citation(
            {**base, "verbatim_excerpt": "BACKGROUND ONLY TEXT."},
            manifest,
            source_bytes=pdf_bytes,
        )
    positive = verify_source_citation(
        {**base, "verbatim_excerpt": "ACTUAL SECTION TEXT."}, manifest, source_bytes=pdf_bytes
    )
    assert positive["verification_level"] == "SOURCE_CONTENT_VERIFIED"


@pytest.mark.parametrize(
    "numeric_line",
    ["1.4 m freeboard", "1.4 % freeboard margin", "1.4:1 geometric scale", "1.4 m/s at design speed"],
)
def test_mk574_r26_measurement_lines_cannot_anchor_a_textbook_clause(numeric_line: str) -> None:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), f"1.3 Background\n{numeric_line}\nBACKGROUND ONLY TEXT.\n")
    p2 = doc.new_page()
    p2.insert_text((72, 72), "1.4. Applied method\nACTUAL SECTION TEXT.\n")
    p3 = doc.new_page()
    p3.insert_text((72, 72), "1.5. Closing section.\n")
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    source_id = "SYNTH_TEXTBOOK_R26_NUMERIC_PREFIX"
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": source_id,
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": source_id, "title": "Synthetic numeric-prefix PDF",
                "document_kind": "TEXTBOOK", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 3, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Numeric measurement text is not a section heading.",
            }],
        }
    )
    base = {
        "source_id": source_id, "source_sha256": sha, "source_version": "2025",
        "clause": "1.4 Applied method", "pdf_page": [1, 2, 3],
    }
    with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
        verify_source_citation(
            {**base, "verbatim_excerpt": "BACKGROUND ONLY TEXT."},
            manifest,
            source_bytes=pdf_bytes,
        )


def test_mk574_r26_measurement_line_does_not_end_a_textbook_clause() -> None:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "1.3 Background\n")
    p2 = doc.new_page()
    p2.insert_text(
        (72, 72),
        "1.4. Applied method\nACTUAL SECTION TEXT.\n1.5 m minimum clearance\nCONTINUED METHOD TEXT.\n",
    )
    p3 = doc.new_page()
    p3.insert_text((72, 72), "1.5. Closing section.\n")
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    source_id = "SYNTH_TEXTBOOK_R26_NUMERIC_BOUNDARY"
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": source_id,
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": source_id, "title": "Synthetic numeric-boundary PDF",
                "document_kind": "TEXTBOOK", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 3, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Measurement text does not end a section.",
            }],
        }
    )
    citation = {
        "source_id": source_id, "source_sha256": sha, "source_version": "2025",
        "clause": "1.4 Applied method", "pdf_page": [1, 2, 3],
        "verbatim_excerpt": "ACTUAL SECTION TEXT. 1.5 m minimum clearance CONTINUED METHOD TEXT.",
    }
    result = verify_source_citation(citation, manifest, source_bytes=pdf_bytes)
    assert result["verification_level"] == "SOURCE_CONTENT_VERIFIED"


@pytest.mark.parametrize(
    "next_heading,wrong_section_text",
    [
        ("1.5", "5 percent margin is described here."),
        ("2.3:", "30 degrees was the starting angle."),
        ("1.5 In service", "THE IN-SERVICE RULE BELONGS TO SECTION 1.5."),
        ("1.5 In operation", "THE-IN-OPERATION RULE BELONGS TO SECTION 1.5."),
        ("1.5. In service", "THE IN-SERVICE RULE BELONGS TO SECTION 1.5."),
        ("Section 1.5 In service", "THE PREFIXED IN-SERVICE RULE BELONGS TO SECTION 1.5."),
        ("Section 1.5 - In service", "THE DASHED PREFIXED IN-SERVICE RULE BELONGS TO SECTION 1.5."),
        ("Section 1.5 - Auxiliary steering", "THE AUXILIARY STEERING RULE BELONGS TO SECTION 1.5."),
    ],
)
def test_mk574_r27_textbook_citation_stops_at_physical_heading_line(
    next_heading: str,
    wrong_section_text: str,
) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "1.4. Applied method\nACTUAL SECTION 1.4 TEXT.\n"
        f"{next_heading}\n{wrong_section_text}\n1.6. Closing section.\n",
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    source_id = "SYNTH_TEXTBOOK_R27_PHYSICAL_HEADING"
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": source_id,
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": source_id, "title": "Synthetic line-bounded PDF",
                "document_kind": "TEXTBOOK", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 1, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Headings and measurement text are line-bounded.",
            }],
        }
    )
    citation = {
        "source_id": source_id, "source_sha256": sha, "source_version": "2025",
        "clause": "1.4 Applied method", "pdf_page": [1],
        "verbatim_excerpt": wrong_section_text,
    }
    with pytest.raises(MarineKnowledgeError, match="CITATION_EXCERPT_CONTENT_MISMATCH"):
        verify_source_citation(citation, manifest, source_bytes=pdf_bytes)


@pytest.mark.parametrize(
    "measurement_line,measurement_excerpt",
    [
        ("1.4 kPa design limit governs the earlier requirement.", "kPa design limit governs the earlier requirement."),
        ("1.4 MPa proof pressure is required.", "MPa proof pressure is required."),
        ("1.4-MPa proof pressure is required.", "MPa proof pressure is required."),
        ("1.4 kN/m allowable load applies.", "kN/m allowable load applies."),
        ("1.4-kN/m allowable load applies.", "kN/m allowable load applies."),
        ("1.4 t/m3 cargo density applies.", "t/m3 cargo density applies."),
        ("1.4 N/mm^2 proof stress applies.", "N/mm^2 proof stress applies."),
        ("1.4 kN-m shaft torque applies.", "kN-m shaft torque applies."),
        ("1.4 kg/m3 cargo density applies.", "kg/m3 cargo density applies."),
        ("1.4 m^2 deck area applies.", "m^2 deck area applies."),
    ],
)
def test_mk574_r28_measurement_suffix_cannot_anchor_a_textbook_clause(
    measurement_line: str, measurement_excerpt: str
) -> None:
    doc = fitz.open()
    prior_page = doc.new_page()
    prior_page.insert_text(
        (72, 72),
        "1.3 Existing requirements\n"
        f"{measurement_line}\n",
    )
    real_clause_page = doc.new_page()
    real_clause_page.insert_text((72, 72), "Section 1.4\nREAL SECTION 1.4 REQUIREMENT TEXT.\n")
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    source_id = "SYNTH_TEXTBOOK_R28_MEASUREMENT_SUFFIX"
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": source_id,
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": source_id, "title": "Synthetic measurement suffix PDF",
                "document_kind": "TEXTBOOK", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": 2, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "A measurement token is not a clause heading.",
            }],
        }
    )
    citation = {
        "source_id": source_id, "source_sha256": sha, "source_version": "2025",
        "clause": "1.4", "pdf_page": [1],
        "verbatim_excerpt": measurement_excerpt,
    }
    with pytest.raises(MarineKnowledgeError, match="CITATION_CLAUSE_PAGE_MISMATCH"):
        verify_source_citation(citation, manifest, source_bytes=pdf_bytes)


def _build_nested_equipment_dxf_bytes(
    *,
    catalogue_as_attribute: bool = False,
    include_lpp: bool = False,
    repeat_nested_insert: bool = False,
    hull_text_in_nested_block: bool = False,
    vessel_length_line: str | None = None,
    length_in_nested_block: bool = False,
    nested_catalogue_label: bool = False,
    root_block_name: str = "VESSEL_ROOT",
    equipment_block_name: str = "STEERING_GEAR",
) -> bytes:
    lines = [
        "0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1015",
        "9", "$INSUNITS", "70", "4", "0", "ENDSEC", "0", "SECTION", "2", "BLOCKS",
        "0", "BLOCK", "8", "0", "2", root_block_name, "70", "0",
        "10", "0", "20", "0", "30", "0", "3", root_block_name,
    ]
    if not hull_text_in_nested_block:
        lines.extend([
            "0", "TEXT", "8", "0", "10", "0", "20", "0", "30", "0", "40", "250",
            "1", "HULL STRUCTURE : SINGLE SIDE",
        ])
    if vessel_length_line and not length_in_nested_block:
        lines.extend([
            "0", "TEXT", "8", "0", "10", "0", "20", "500", "30", "0", "40", "250",
            "1", vessel_length_line,
        ])
    lines.extend([
        "0", "INSERT", "5", "A1", "8", "0", "2", equipment_block_name, "10", "0", "20", "0", "30", "0",
        "41", "1", "42", "1", "43", "1",
    ])
    if catalogue_as_attribute and not nested_catalogue_label:
        lines.extend(["66", "1"])
        lines.extend([
            "0", "ATTRIB", "8", "0", "2", "ITEM", "10", "0", "20", "0", "30", "0",
            "40", "250", "1", "STEERING GEAR CATALOGUE", "0", "SEQEND", "8", "0",
        ])
    if repeat_nested_insert:
        lines.extend([
            "0", "INSERT", "5", "A2", "8", "0", "2", equipment_block_name, "10", "2000", "20", "0", "30", "0",
            "41", "1", "42", "1", "43", "1",
        ])
    lines.extend(["0", "ENDBLK", "8", "0", "2", root_block_name])
    lines.extend([
        "0", "BLOCK", "8", "0", "2", equipment_block_name, "70", "0",
        "10", "0", "20", "0", "30", "0", "3", equipment_block_name,
    ])
    if nested_catalogue_label:
        lines.extend([
            "0", "INSERT", "5", "A3", "8", "0", "2", "GEAR_LABEL", "10", "0", "20", "0", "30", "0",
            "41", "1", "42", "1", "43", "1",
        ])
        if catalogue_as_attribute:
            lines.extend(["66", "1", "0", "ATTRIB", "8", "0", "2", "ITEM", "10", "0", "20", "0", "30", "0", "40", "250", "1", "STEERING GEAR CATALOGUE", "0", "SEQEND", "8", "0"])
    elif not catalogue_as_attribute:
        lines.extend([
            "0", "TEXT", "8", "0", "10", "0", "20", "0", "30", "0", "40", "250",
            "1", "STEERING GEAR CATALOGUE",
        ])
    if vessel_length_line and length_in_nested_block:
        lines.extend([
            "0", "TEXT", "8", "0", "10", "0", "20", "500", "30", "0", "40", "250",
            "1", vessel_length_line,
        ])
    if hull_text_in_nested_block:
        lines.extend([
            "0", "TEXT", "8", "0", "10", "1000", "20", "0", "30", "0", "40", "250",
            "1", "HULL STRUCTURE : SINGLE SIDE",
        ])
    if include_lpp:
        lines.extend([
            "0", "TEXT", "8", "0", "10", "0", "20", "500", "30", "0", "40", "250",
            "1", "Lpp = 52.00 m",
        ])
    lines.extend(["0", "ENDBLK", "8", "0", "2", equipment_block_name])
    if nested_catalogue_label and not catalogue_as_attribute:
        lines.extend([
            "0", "BLOCK", "8", "0", "2", "GEAR_LABEL", "70", "0",
            "10", "0", "20", "0", "30", "0", "3", "GEAR_LABEL",
            "0", "TEXT", "8", "0", "10", "0", "20", "0", "30", "0", "40", "250",
            "1", "STEERING GEAR CATALOGUE", "0", "ENDBLK", "8", "0", "2", "GEAR_LABEL",
        ])
    elif nested_catalogue_label and catalogue_as_attribute:
        lines.extend([
            "0", "BLOCK", "8", "0", "2", "GEAR_LABEL", "70", "0",
            "10", "0", "20", "0", "30", "0", "3", "GEAR_LABEL",
            "0", "ENDBLK", "8", "0", "2", "GEAR_LABEL",
        ])
    lines.extend([
        "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES", "0", "INSERT", "8", "0", "2", root_block_name,
        "10", "0", "20", "0", "30", "0", "41", "1", "42", "1", "43", "1",
        "0", "ENDSEC", "0", "EOF", "",
    ])
    return "\n".join(lines).encode("latin-1")


def test_mk574_r26_nested_equipment_text_and_attrib_keep_parent_hull_fact() -> None:
    def observe(catalogue_as_attribute: bool) -> dict[str, Any]:
        data = _build_nested_equipment_dxf_bytes(catalogue_as_attribute=catalogue_as_attribute)
        return observe_dxf_bytes(data, drawing_id="GA_R24_NESTED_SCOPE")

    # A nested equipment label scopes only its own INSERT occurrence, regardless of
    # whether the label is a child-block TEXT or an ATTRIB attached to that INSERT.
    child_text = observe(catalogue_as_attribute=False)
    child_attrib = observe(catalogue_as_attribute=True)
    assert all("_entity_type" not in item for item in child_text["texts"])
    assert all("_entity_type" not in item for item in child_attrib["texts"])
    assert child_text["particulars"]["single_side_or_non_double_hull"] is True
    assert child_attrib["particulars"]["single_side_or_non_double_hull"] is True


def test_mk574_r25_repeated_nested_insert_occurrences_do_not_share_equipment_scope() -> None:
    observed = observe_dxf_bytes(
        _build_nested_equipment_dxf_bytes(
            catalogue_as_attribute=True,
            repeat_nested_insert=True,
            hull_text_in_nested_block=True,
        ),
        drawing_id="GA_R25_REPEATED_NESTED_SCOPE",
    )
    hull_entries = [item for item in observed["texts"] if item["text"] == "HULL STRUCTURE : SINGLE SIDE"]
    assert len(hull_entries) == 2
    assert len({item["occurrence_id"] for item in hull_entries}) == 2
    assert observed["particulars"]["single_side_or_non_double_hull"] is True


def test_mk574_r26_nested_equipment_text_does_not_mask_parent_vessel_facts() -> None:
    child_text = observe_dxf_bytes(
        _build_nested_equipment_dxf_bytes(vessel_length_line="L = 52.00 m"),
        drawing_id="GA_R26_NESTED_TEXT_SCOPE",
    )
    child_attrib = observe_dxf_bytes(
        _build_nested_equipment_dxf_bytes(
            catalogue_as_attribute=True,
            vessel_length_line="L = 52.00 m",
        ),
        drawing_id="GA_R26_NESTED_ATTRIB_SCOPE",
    )
    for observed in (child_text, child_attrib):
        assert observed["particulars"]["design_length_l_m_values"] == [52.0]
        assert observed["particulars"]["single_side_or_non_double_hull"] is True


@pytest.mark.parametrize("catalogue_as_attribute", [False, True])
def test_mk574_r27_nested_catalogue_label_keeps_equipment_assembly_facts_out_of_vessel_scope(
    catalogue_as_attribute: bool,
) -> None:
    observed = observe_dxf_bytes(
        _build_nested_equipment_dxf_bytes(
            catalogue_as_attribute=catalogue_as_attribute,
            hull_text_in_nested_block=True,
            vessel_length_line="L = 52.00 m",
            length_in_nested_block=True,
            nested_catalogue_label=True,
        ),
        drawing_id=f"GA_R27_EQUIPMENT_ASSEMBLY_{'ATTRIB' if catalogue_as_attribute else 'TEXT'}",
    )
    particulars = observed["particulars"]
    assert particulars["design_length_l_m_values"] == []
    assert particulars["single_side_or_non_double_hull"] is False


def test_mk574_r28_nested_catalogue_does_not_promote_mixed_vessel_ancestor_to_equipment() -> None:
    observed = observe_dxf_bytes(
        _build_nested_equipment_dxf_bytes(
            root_block_name="VESSEL_STEERING_GEAR",
            vessel_length_line="L = 52.00 m",
            nested_catalogue_label=True,
        ),
        drawing_id="GA_R28_MIXED_ASSEMBLY_ANCESTOR_SCOPE",
    )
    particulars = observed["particulars"]
    assert particulars["design_length_l_m_values"] == [52.0]
    assert particulars["single_side_or_non_double_hull"] is True


@pytest.mark.parametrize(
    "equipment_block_name",
    [
        "STEERING_GEAR_ASSY", "STEERING_GEAR_01", "AFT_STEERING_GEAR",
        "PORT_STEERING_GEAR", "STBD_STEERING_GEAR",
        "AFT_PORT_STEERING_GEAR", "FORWARD_STBD_STEERING_GEAR", "STEERING_GEAR_PORT",
    ],
)
def test_mk574_r28_qualified_equipment_assembly_keeps_nested_catalogue_facts_out_of_vessel_scope(
    equipment_block_name: str,
) -> None:
    observed = observe_dxf_bytes(
        _build_nested_equipment_dxf_bytes(
            equipment_block_name=equipment_block_name,
            include_lpp=True,
            hull_text_in_nested_block=True,
            nested_catalogue_label=True,
        ),
        drawing_id=f"GA_R28_QUALIFIED_EQUIPMENT_{equipment_block_name}",
    )
    particulars = observed["particulars"]
    assert particulars["lpp_m_values"] == []
    assert particulars["single_side_or_non_double_hull"] is False


@pytest.mark.parametrize(
    "equipment_block_name",
    ["AFT_PORT_STEERING_GEAR", "FORWARD_STBD_STEERING_GEAR", "STEERING_GEAR_PORT"],
)
def test_mk574_r31_stacked_equipment_location_cannot_satisfy_vessel_acceptance(
    equipment_block_name: str,
) -> None:
    occurrence = f"MODELSPACE/INSERT:GEAR:{equipment_block_name}"
    catalogue_occurrence = f"{occurrence}/INSERT:LABEL:GEAR_LABEL"
    observation = normalize_observation(
        _base_ga(
            length_line="",
            extra_texts=[
                {"handle": "GEAR_CATALOGUE", "text": "STEERING GEAR CATALOGUE", "occurrence_id": catalogue_occurrence},
                {"handle": "GEAR_LPP", "text": "Lpp = 52.00 m", "occurrence_id": occurrence},
                {"handle": "GEAR_HULL", "text": "HULL STRUCTURE : SINGLE SIDE", "occurrence_id": occurrence},
            ],
        )
    )
    assert observation["particulars"]["lpp_m_values"] == []
    assert observation["particulars"]["single_side_or_non_double_hull"] is False
    result = detect_drawing_gaps_and_conflicts([observation], partial_package=True)
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def _build_lpp_row_pairing_dxf_bytes() -> bytes:
    lines = [
        "0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1015", "9", "$INSUNITS", "70", "4",
        "0", "ENDSEC", "0", "SECTION", "2", "BLOCKS", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES",
    ]
    for handle, text, x, y in (
        ("A1", "LENGTH (L.P.P)", 60000, 6000),
        ("A2", "40 m", 60200, 6250),  # closer in X, but belongs to an adjacent detail row
        ("A3", "55 m", 62000, 6000),  # actual same-row Lpp value
        ("A4", "A.P", 1000, 0),
        ("A5", "F.P", 41000, 0),
    ):
        lines.extend([
            "0", "TEXT", "5", handle, "8", "0", "10", str(x), "20", str(y), "30", "0",
            "40", "250", "1", text,
        ])
    lines.extend(["0", "ENDSEC", "0", "EOF", ""])
    return "\n".join(lines).encode("ascii")


def _build_lpp_hold_length_dxf_bytes(*, adjacent_length_label: str = "HOLD LENGTH") -> bytes:
    lines = [
        "0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1015", "9", "$INSUNITS", "70", "4",
        "0", "ENDSEC", "0", "SECTION", "2", "BLOCKS", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES",
    ]
    for handle, text, x, y in (
        ("A1", "LENGTH (L.P.P)", 60000, 6000),
        ("A2", "55 m", 62000, 6050),
        ("A3", adjacent_length_label, 63000, 6000),
        ("A4", "40 m", 65000, 6000),
        ("A5", "A.P", 1000, 0),
        ("A6", "F.P", 41000, 0),
    ):
        lines.extend([
            "0", "TEXT", "5", handle, "8", "0", "10", str(x), "20", str(y), "30", "0",
            "40", "250", "1", text,
        ])
    lines.extend(["0", "ENDSEC", "0", "EOF", ""])
    return "\n".join(lines).encode("ascii")


def _build_blank_lpp_breadth_value_dxf_bytes(*, breadth_label: str = "BREADTH") -> bytes:
    lines = [
        "0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1015", "9", "$INSUNITS", "70", "6",
        "0", "ENDSEC", "0", "SECTION", "2", "BLOCKS", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES",
    ]
    for handle, text, x, y in (
        ("B1", "LENGTH (L.P.P)", 0, 0),
        ("B2", breadth_label, 10, 0),
        ("B3", "15 m", 13, 0),
    ):
        lines.extend([
            "0", "TEXT", "5", handle, "8", "0", "10", str(x), "20", str(y), "30", "0",
            "40", "0.3", "1", text,
        ])
    lines.extend(["0", "ENDSEC", "0", "EOF", ""])
    return "\n".join(lines).encode("ascii")


def test_mk574_r27_off_row_numeric_text_cannot_hide_a_native_ap_fp_lpp_conflict() -> None:
    observation = observe_dxf_bytes(
        _build_lpp_row_pairing_dxf_bytes(),
        drawing_id="GA_R27_OFF_ROW_LPP",
    )
    result = detect_drawing_gaps_and_conflicts([observation], partial_package=True)
    assert observation["particulars"]["lpp_m_values"] == [55.0]
    assert any(item["finding_id"] == "F_UNIT_OR_SCALE_MISMATCH_1000X" for item in result["findings"])


@pytest.mark.parametrize(
    "adjacent_length_label",
    [
        "HOLD LENGTH", "CHIEU DAI HAM HANG", "LOA", "T:", "CHIEU DAI DUONG NUOC", "LTK",
        "MON NUOC", "CHIEU CHIM", "CHIEU CAO MAN", "CHIEU DAI THIET KE",
    ],
)
def test_mk574_r28_intervening_field_label_delimits_lpp_value_binding(adjacent_length_label: str) -> None:
    observation = observe_dxf_bytes(
        _build_lpp_hold_length_dxf_bytes(adjacent_length_label=adjacent_length_label), drawing_id="GA_R28_HOLD_LENGTH_DELIMITER"
    )
    result = detect_drawing_gaps_and_conflicts([observation], partial_package=True)
    assert observation["particulars"]["lpp_m_values"] == [55.0]
    assert observation["metric_provenance"]["lpp_m"] == "NATIVE_CAD_TEXT"
    assert any(item["finding_id"] == "F_UNIT_OR_SCALE_MISMATCH_1000X" for item in result["findings"])


@pytest.mark.parametrize("breadth_label", ["BREADTH", "CHIEU RONG (B)", "B:"])
def test_mk574_r28_breadth_value_cannot_fill_blank_lpp_field(breadth_label: str) -> None:
    observation = observe_dxf_bytes(
        _build_blank_lpp_breadth_value_dxf_bytes(breadth_label=breadth_label), drawing_id="GA_R28_BLANK_LPP_BREADTH_VALUE"
    )
    assert observation["particulars"]["lpp_m_values"] == []
    assert observation["particulars"]["breadth_m_values"] == [15.0]
    assert "lpp_m" not in observation["metric_provenance"]


def test_mk574_r24_equipment_lpp_cannot_supply_vessel_span_length() -> None:
    observed = observe_dxf_bytes(
        _build_nested_equipment_dxf_bytes(include_lpp=True), drawing_id="GA_R24_EQUIPMENT_LPP"
    )
    assert observed["particulars"]["lpp_m_values"] == []
    result = detect_drawing_gaps_and_conflicts([observed], partial_package=True)
    assert result["status"] != "PASS"


def test_mk574_r25_equipment_design_length_cannot_exclude_vessel() -> None:
    observation = normalize_observation(
        _base_ga(
            length_line="",
            extra_texts=[
                {"handle": "GEAR", "text": "STEERING GEAR CATALOGUE", "occurrence_id": "MODELSPACE/INSERT:GEAR"},
                {"handle": "GEAR_L", "text": "L = 151.00 m", "occurrence_id": "MODELSPACE/INSERT:GEAR"},
                {"handle": "GEAR_LWL", "text": "LWL = 149.00 m", "occurrence_id": "MODELSPACE/INSERT:GEAR"},
            ],
        )
    )
    assert observation["particulars"]["design_length_l_m_values"] == []
    assert observation["particulars"]["lwl_m_values"] == []
    result = evaluate_regulation_applicability_and_submittal([observation], partial_package=True)
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(item["finding_id"] == "F_MISSING_VESSEL_LENGTH" for item in result["findings"])


def test_mk574_r25_lpp_label_cannot_pair_with_equipment_occurrence_number() -> None:
    observation = normalize_observation(
        _base_ga(
            length_line="",
            extra_texts=[
                {"handle": "LPP", "text": "LENGTH (L.P.P)", "x": 60000.0, "y": 1500.0},
                {
                    "handle": "GEAR", "text": "STEERING GEAR CATALOGUE", "x": 60000.0, "y": 1700.0,
                    "occurrence_id": "MODELSPACE/INSERT:GEAR",
                },
                {
                    "handle": "GEAR_VALUE", "text": "52 m", "x": 60500.0, "y": 1500.0,
                    "occurrence_id": "MODELSPACE/INSERT:GEAR",
                },
            ],
        )
    )
    assert observation["particulars"]["lpp_m_values"] == []
    result = detect_drawing_gaps_and_conflicts([observation], partial_package=True)
    assert result["status"] != "PASS"


def test_mk574_r26_nearest_lpp_value_must_match_an_explicit_view() -> None:
    observation = normalize_observation(
        _base_ga(
            length_line="",
            extra_texts=[
                {"handle": "LPP_LABEL", "text": "LENGTH (L.P.P)", "x": 60000.0, "y": 6000.0, "view_id": "PROFILE"},
                {"handle": "DETAIL_VALUE", "text": "80 m", "x": 60100.0, "y": 6000.0, "view_id": "DETAIL"},
                {"handle": "PROFILE_VALUE", "text": "52 m", "x": 61000.0, "y": 6000.0, "view_id": "PROFILE"},
            ],
        )
    )
    assert observation["particulars"]["lpp_m_values"] == [52.0]


def test_mk574_r26_nearest_lpp_value_is_stable_when_equal_dx_candidates_reorder() -> None:
    values = [
        {"handle": "ON_ROW_52", "text": "52 m", "x": 61000.0, "y": 6000.0},
        {"handle": "ABOVE_ROW_80", "text": "80 m", "x": 61000.0, "y": 5950.0},
    ]
    for ordered_values in (values, list(reversed(values))):
        observation = normalize_observation(
            _base_ga(
                length_line="",
                extra_texts=[
                    {"handle": "LPP_LABEL", "text": "LENGTH (L.P.P)", "x": 60000.0, "y": 6000.0},
                    *ordered_values,
                ],
            )
        )
        assert observation["particulars"]["lpp_m_values"] == [52.0]


def test_mk574_r26_blank_owner_field_ignores_value_from_another_insert() -> None:
    observation = normalize_observation(
        _base_ga(
            extra_texts=[
                {"handle": "OWNER", "text": "OWNER:", "x": 60000.0, "y": 7000.0},
                {"handle": "GEAR", "text": "STEERING GEAR CATALOGUE", "occurrence_id": "MODELSPACE/INSERT:GEAR"},
                {"handle": "GEAR_VALUE", "text": "52 m", "x": 60500.0, "y": 7000.0, "occurrence_id": "MODELSPACE/INSERT:GEAR"},
            ],
        )
    )
    assert "OWNER" in observation["blank_fields"]


@pytest.mark.parametrize("equipment_fact", ["MAIN ENGINE: EQUIPMENT BENCH 55 HP", "PASSENGERS: 15"])
def test_mk574_r26_equipment_hp_and_capacity_cannot_resolve_vessel_scope(equipment_fact: str) -> None:
    base = _base_ga(length_line="Chiều dài tàu L = 19.00 m", class_line="CẤP TÀU : VR-SI")
    base["texts"] = [item for item in base["texts"] if item["handle"] != "G8"]
    baseline = evaluate_regulation_applicability_and_submittal([base], partial_package=True)
    assert any(item["finding_id"] == "F_SCOPE_QCVN25_UNRESOLVED" for item in baseline["findings"])

    attack = {**base, "texts": list(base["texts"]) + [
        {"handle": "GEAR", "text": "STEERING GEAR CATALOGUE", "occurrence_id": "MODELSPACE/INSERT:GEAR"},
        {"handle": "GEAR_FACT", "text": equipment_fact, "occurrence_id": "MODELSPACE/INSERT:GEAR"},
    ]}
    result = evaluate_regulation_applicability_and_submittal([attack], partial_package=True)
    finding_ids = {item["finding_id"] for item in result["findings"]}
    assert "F_SCOPE_QCVN25_UNRESOLVED" in finding_ids
    assert "F_SCOPE_QCVN72_CONFIRMED" not in finding_ids


def test_mk574_r26_equipment_bow_anchors_and_plate_are_not_vessel_facts() -> None:
    raw = _base_ga(length_line="Chiều dài tàu L = 52.00 m")
    raw["texts"] = [item for item in raw["texts"] if item["handle"] not in {"G10", "G11"}]
    raw["texts"].extend([
        {"handle": "VESSEL_LPP", "text": "Lpp = 52.00 m", "x": 60000.0, "y": 6000.0},
        {"handle": "GEAR", "text": "STEERING GEAR CATALOGUE", "occurrence_id": "MODELSPACE/INSERT:GEAR"},
        {"handle": "GEAR_AP", "text": "A.P", "x": 1000.0, "y": 0.0, "occurrence_id": "MODELSPACE/INSERT:GEAR"},
        {"handle": "GEAR_FP", "text": "F.P", "x": 53000.0, "y": 0.0, "occurrence_id": "MODELSPACE/INSERT:GEAR"},
        {"handle": "GEAR_PLATE", "text": "BOTTOM PLATE t=5 mm", "occurrence_id": "MODELSPACE/INSERT:GEAR"},
    ])
    observation = normalize_observation(raw)
    particulars = observation["particulars"]
    assert particulars["ap_x_coords"] == []
    assert particulars["fp_x_coords"] == []
    assert particulars["extracted_plate_thicknesses_mm"] == []
    result = detect_drawing_gaps_and_conflicts([observation], partial_package=True)
    assert not any("Bow direction" in check for check in result["checks_executed"])
    assert not any("1000x CAD A.P-to-F.P span" in check for check in result["checks_executed"])


def test_mk574_r20_equipment_reference_prefix_cannot_assert_vessel_ship_type() -> None:
    ga = _base_ga(
        drawing_id="GA_R20_EQUIPMENT_REF_SCOPE",
        length_line="Chiều dài tàu L = 42.00 m",
        ship_type_line="",
        bulkheads=3,
        extra_texts=[
            {"handle": "EQREF", "text": "STEERING GEAR CATALOGUE (REF.); SHIP TYPE : DRY CARGO NON-CONTAINER", "x": 60000.0, "y": 5200.0, "height": 200.0},
            {"handle": "HULL", "text": "HULL STRUCTURE : SINGLE SIDE", "x": 60000.0, "y": 5400.0, "height": 200.0},
        ],
    )
    observed = normalize_observation(ga)
    assert observed["particulars"]["ship_types"] == []
    assert observed["particulars"]["non_container_ship"] is False
    result = evaluate_regulation_applicability_and_submittal([ga], partial_package=True)
    mk08 = next(f for f in result["findings"] if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
    assert mk08["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_mk574_r21_equipment_catalogue_scope_cannot_assert_vessel_hull_structure() -> None:
    for idx, hull_text in enumerate(("SINGLE SIDE", "DOUBLE SIDE"), start=1):
        ga = _base_ga(
            drawing_id=f"GA_R21_EQUIPMENT_HULL_SCOPE_{idx}",
            length_line="Chiều dài tàu L = 42.00 m",
            ship_type_line="SHIP TYPE : DRY CARGO NON-CONTAINER",
            bulkheads=3,
            extra_texts=[
                {
                    "handle": "EQ",
                    "text": f"STEERING GEAR CATALOGUE (REF.); HULL STRUCTURE : {hull_text}",
                    "x": 60000.0,
                    "y": 5200.0,
                },
            ],
        )
        observed = normalize_observation(ga)
        assert observed["particulars"]["double_hull_or_double_side"] is False
        assert observed["particulars"]["single_side_or_non_double_hull"] is False
        result = evaluate_regulation_applicability_and_submittal([ga], partial_package=True)
        mk08 = next(f for f in result["findings"] if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
        assert result["status"] == "INSUFFICIENT_EVIDENCE"
        assert mk08["evidence"]["exception_2_4_6_9_eligibility"] == "UNKNOWN"

    vessel_fact = normalize_observation({
        "drawing_id": "GA_R21_VESSEL_HULL_SCOPE",
        "insunits": 4,
        "texts": [
            {"handle": "HULL", "text": "HULL STRUCTURE : SINGLE SIDE"},
        ],
        "structural_metrics": {},
    })
    assert vessel_fact["particulars"]["single_side_or_non_double_hull"] is True


def test_mk574_r22_equipment_scope_is_shared_by_text_entities_in_one_insert() -> None:
    from cad_agent.marine_knowledge import normalize_observation

    for idx, (catalogue, hull_text) in enumerate(
        (
            ("STEERING GEAR CATALOGUE (REF.)", "HULL STRUCTURE : SINGLE SIDE"),
            ("STEERING GEAR CATALOGUE (REFERENCE ONLY, NOT APPLICABLE)", "HULL CONFIGURATION=NON-DOUBLE-HULL"),
            ("STEERING GEAR CATALOGUE", "HULL STRUCTURE : DOUBLE SIDE"),
        ),
        start=1,
    ):
        ga = _base_ga(
            drawing_id=f"GA_R22_INSERT_EQUIPMENT_SCOPE_{idx}",
            length_line="Chiều dài tàu L = 42.00 m",
            ship_type_line="SHIP TYPE : DRY CARGO NON-CONTAINER",
            bulkheads=3,
            extra_texts=[
                {
                    "handle": "EQCAT",
                    "text": catalogue,
                    "occurrence_id": "MODELSPACE/STEERING_GEAR_INSERT",
                    "x": 60000.0,
                    "y": 5200.0,
                },
                {
                    "handle": "EQHULL",
                    "text": hull_text,
                    "occurrence_id": "MODELSPACE/STEERING_GEAR_INSERT",
                    "x": 60000.0,
                    "y": 5400.0,
                },
            ],
        )
        observed = normalize_observation(ga)
        assert observed["particulars"]["double_hull_or_double_side"] is False
        assert observed["particulars"]["single_side_or_non_double_hull"] is False
        result = evaluate_regulation_applicability_and_submittal([ga], partial_package=True)
        mk08 = next(f for f in result["findings"] if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
        assert result["status"] == "INSUFFICIENT_EVIDENCE"
        assert mk08["evidence"]["exception_2_4_6_9_eligibility"] == "UNKNOWN"

    standalone = normalize_observation(
        {
            "drawing_id": "GA_R22_STANDALONE_HULL_FACT",
            "insunits": 4,
            "texts": [{"handle": "HULL", "text": "HULL STRUCTURE : SINGLE SIDE"}],
            "structural_metrics": {},
        }
    )
    assert standalone["particulars"]["single_side_or_non_double_hull"] is True


def test_mk574_r23_equipment_scope_propagates_from_parent_insert_to_child_text() -> None:
    for idx, (catalogue, hull_text) in enumerate(
        (
            ("STEERING GEAR CATALOGUE (REF.)", "HULL STRUCTURE : SINGLE SIDE"),
            ("STEERING GEAR CATALOGUE (REFERENCE ONLY, NOT APPLICABLE)", "HULL CONFIGURATION=NON-DOUBLE-HULL"),
            ("STEERING GEAR CATALOGUE", "HULL STRUCTURE : DOUBLE SIDE"),
        ),
        start=1,
    ):
        ga = _base_ga(
            drawing_id=f"GA_R23_NESTED_EQUIPMENT_SCOPE_{idx}",
            length_line="Chiều dài tàu L = 42.00 m",
            ship_type_line="SHIP TYPE : DRY CARGO NON-CONTAINER",
            bulkheads=3,
            extra_texts=[
                {
                    "handle": "EQCAT",
                    "text": catalogue,
                    "occurrence_id": "MODELSPACE/INSERT:ROOT:BOW",
                    "x": 60000.0,
                    "y": 5200.0,
                },
                {
                    "handle": "EQHULL",
                    "text": hull_text,
                    "occurrence_id": "MODELSPACE/INSERT:ROOT:BOW/CHILD",
                    "x": 60000.0,
                    "y": 5400.0,
                },
            ],
        )
        observed = normalize_observation(ga)
        assert observed["particulars"]["double_hull_or_double_side"] is False
        assert observed["particulars"]["single_side_or_non_double_hull"] is False
        result = evaluate_regulation_applicability_and_submittal([ga], partial_package=True)
        mk08 = next(f for f in result["findings"] if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
        assert result["status"] == "INSUFFICIENT_EVIDENCE"
        assert mk08["evidence"]["exception_2_4_6_9_eligibility"] == "UNKNOWN"


def test_mk574_r20_equipment_prefix_does_not_mask_explicit_vessel_scope() -> None:
    from cad_agent.marine_knowledge.observer import normalize_observation as observe

    observation = observe({
        "drawing_id": "GA_R20_EXPLICIT_VESSEL_SCOPE", "insunits": 4,
        "texts": [{"handle": "SCOPE", "text": "LIFEBOAT EQUIPMENT; VESSEL REGULATION : QCVN 21:2025", "x": 0, "y": 0, "height": 100}],
    })
    assert "OCEAN_GOING" in observation["particulars"]["service_areas"]


@pytest.mark.parametrize("reference_suffix", ["REF.", "[REF.]", "(REFERENCE)"])
def test_mk574_r20_reference_lpp_cannot_supply_skill3_span_length(reference_suffix: str) -> None:
    from cad_agent.marine_knowledge import detect_drawing_gaps_and_conflicts

    data = _build_insert_dxf_bytes().replace(
        b"Lpp = 52.00 m", f"Lpp = 52.00 m {reference_suffix}".encode("ascii")
    )
    observation = observe_dxf_bytes(data, drawing_id="GA_R20_REFERENCE_LPP")
    assert observation["particulars"]["lpp_m_values"] == []
    result = detect_drawing_gaps_and_conflicts([observation], partial_package=True)
    assert result["status"] != "PASS"
    assert any(f["finding_id"] == "F_AP_FP_SPAN_UNAVAILABLE_LPP_GA_R20_REFERENCE_LPP" for f in result["findings"])

    unqualified = observe_dxf_bytes(_build_insert_dxf_bytes(), drawing_id="GA_R20_UNQUALIFIED_LPP")
    assert unqualified["particulars"]["lpp_m_values"] == [52.0]
    positive = detect_drawing_gaps_and_conflicts([unqualified], partial_package=True)
    assert positive["status"] == "PASS"
    assert not any("F_AP_FP_SPAN_UNAVAILABLE_LPP_GA_R20_UNQUALIFIED_LPP" == f["finding_id"] for f in positive["findings"])


def test_mk574_r20_nested_missing_block_definition_abstains() -> None:
    data = "\n".join(
        [
            "0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1015",
            "9", "$INSUNITS", "70", "4", "9", "$MEASUREMENT", "70", "1", "0", "ENDSEC",
            "0", "SECTION", "2", "BLOCKS",
            "0", "BLOCK", "8", "0", "2", "CARRIER", "70", "0", "10", "0", "20", "0", "30", "0", "3", "CARRIER",
            "0", "TEXT", "8", "0", "10", "0", "20", "0", "30", "0", "40", "300", "1", "GENERAL ARRANGEMENT",
            "0", "INSERT", "8", "0", "2", "MISSING_INNER", "10", "0", "20", "0", "30", "0",
            "0", "INSERT", "8", "0", "2", "REMOTE_XREF", "10", "0", "20", "0", "30", "0",
            "0", "ENDBLK", "8", "0",
            "0", "BLOCK", "8", "0", "2", "REMOTE_XREF", "70", "4", "10", "0", "20", "0", "30", "0", "3", "REMOTE_XREF", "1", "unavailable-reference.dwg",
            "0", "ENDBLK", "8", "0", "0", "ENDSEC",
            "0", "SECTION", "2", "ENTITIES",
            "0", "INSERT", "8", "0", "2", "CARRIER", "10", "0", "20", "0", "30", "0",
            "0", "ENDSEC", "0", "EOF", "",
        ]
    ).encode("ascii")
    observed = observe_dxf_bytes(data, drawing_id="GA_R20_NESTED_MISSING")
    assert any(item.get("reason") == "MISSING_BLOCK_DEFINITION" for item in observed["skipped_entities"])
    assert any(item.get("reason") == "EXTERNAL_REFERENCE_BLOCK_UNRESOLVED" for item in observed["skipped_entities"])
    assert classify_marine_drawing(observed)["status"] == "INSUFFICIENT_EVIDENCE"


def test_mk574_r20_actual_pdf_page_count_is_checked_before_expanding_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    import cad_agent.marine_knowledge.contracts as contracts

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "19 SYNTH REG\n2.1 Alpha rule.\n2.2 Closing rule.\n")
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    manifest = seal_source_manifest(
        {
            "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
            "manifest_id": "MK574_R20_PAGE_BOUND",
            "revision": "0.1.0",
            "status": "CANDIDATE_UNAPPROVED",
            "sources": [{
                "source_id": "SYNTH_REG_R20_PAGE_BOUND", "title": "Synthetic page-bound PDF",
                "document_kind": "REGULATION", "version": "2025", "origin": "synthetic-in-memory",
                "sha256": sha, "page_count": None, "applicable_scope": ["test"],
                "usage_rights": "OPEN_ACADEMIC_RESEARCH", "commit_prohibited": True,
                "usage_status": "ACTIVE_INDEXED", "notes": "Synthetic actual-PDF-page-count regression.",
            }],
        }
    )
    builtin_range = range

    def reject_unbounded_range(*args: int) -> range:
        if max(args) > 1_000_000:
            raise AssertionError("PDF page interval expanded before validating actual page count")
        return builtin_range(*args)

    monkeypatch.setattr(contracts, "range", reject_unbounded_range, raising=False)
    with pytest.raises(MarineKnowledgeError, match="CITATION_PDF_PAGE_OUT_OF_RANGE"):
        verify_source_citation(
            {
                "source_id": "SYNTH_REG_R20_PAGE_BOUND", "source_sha256": sha, "source_version": "2025",
                "clause": "2.1 Alpha rule", "pdf_page": [1, 10_000_000], "reg_page": [19, 20],
            },
            manifest,
            source_bytes=pdf_bytes,
        )


def test_mk574_02_pack_term_and_rule_citations_metadata_integrity() -> None:
    """MK574-02: every term (incl. midship_plane) and rule passes verify_source_citation metadata checks cleanly."""
    manifest = get_marine_source_manifest()
    pack = get_marine_knowledge_pack()
    sources = {s["source_id"]: s for s in manifest["sources"]}

    for term in pack["terms"]:
        src = sources[term["source_id"]]
        rec = {**term, "source_sha256": src["sha256"]}
        res = verify_source_citation(rec, manifest)
        assert "MANIFEST_MATCH" in res["verification_states"]
        if src["document_kind"] == "TEXTBOOK":
            assert term["reg_page"] == [], f"Textbook term {term['term_id']} must not set reg_page"

    for rule in pack["rules"]:
        src = sources[rule["source_id"]]
        rec = {**rule, "source_sha256": src["sha256"]}
        res = verify_source_citation(rec, manifest)
        assert "MANIFEST_MATCH" in res["verification_states"]
        if src["document_kind"] == "TEXTBOOK":
            assert rule["reg_page"] == [], f"Textbook rule {rule['rule_id']} must not set reg_page"


def test_mk574_03_incidental_equipment_does_not_suppress_inland_defects() -> None:
    """MK574-03: FRP locker / SOLAS extinguisher must NOT trigger vessel NOT_APPLICABLE and hide bulkhead defect."""
    ga_frp_locker = _base_ga(
        drawing_id="GA_FRP_LOCKER",
        ship_type_line="SHIP TYPE : DRY CARGO NON-CONTAINER",
        bulkheads=3,  # Violates 2.4.6-8 (40 < L=52 <= 60 requires >= 4)
        extra_texts=[
            {"handle": "EQ1", "text": "FRP LIFERAFT LOCKER ON POOP DECK", "x": 15000.0, "y": 5000.0, "height": 200.0},
            {"handle": "EQ2", "text": "DECK CABINET MATERIAL : FRP", "x": 16000.0, "y": 5200.0, "height": 200.0},
            {"handle": "NS1", "text": "HULL STRUCTURE : SINGLE SIDE", "x": 60000.0, "y": 5400.0, "height": 200.0},
        ],
    )
    res_frp_eq = evaluate_regulation_applicability_and_submittal(
        [ga_frp_locker, _base_mcn(ship_type_line="SHIP TYPE : DRY CARGO NON-CONTAINER")], partial_package=True,
    )
    assert res_frp_eq["status"] == "CONFLICT"
    assert any(
        f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT" and f["verdict"] == "CONFLICT"
        for f in res_frp_eq["findings"]
    )

    ga_solas_ext = _base_ga(
        drawing_id="GA_SOLAS_EXT",
        ship_type_line="SHIP TYPE : DRY CARGO NON-CONTAINER",
        bulkheads=3,
        extra_texts=[
            {"handle": "EQ3", "text": "FIRE EXTINGUISHER SOLAS APPROVED", "x": 17000.0, "y": 5200.0, "height": 200.0},
            {"handle": "EQ4", "text": "LIFEBUOY IMO / SOLAS TYPE", "x": 18000.0, "y": 5200.0, "height": 200.0},
            {"handle": "NS2", "text": "HULL STRUCTURE : SINGLE SIDE", "x": 60000.0, "y": 5400.0, "height": 200.0},
        ],
    )
    res_solas_eq = evaluate_regulation_applicability_and_submittal(
        [ga_solas_ext, _base_mcn(ship_type_line="SHIP TYPE : DRY CARGO NON-CONTAINER")], partial_package=True,
    )
    assert res_solas_eq["status"] == "CONFLICT"
    assert any(
        f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT" and f["verdict"] == "CONFLICT"
        for f in res_solas_eq["findings"]
    )

    # Positive control: genuine declared FRP hull vessel -> NOT_APPLICABLE (Clause 1.1.2)
    frp_hull = _base_ga(
        drawing_id="GA_TRUE_FRP_HULL",
        material_line="HULL MATERIAL : FRP (QCVN 56:2013/BGTVT)",
        class_line="TÀU VỎ CHẤT DẺO CỐT SỢI THỦY TINH (FRP)",
    )
    res_true_frp = evaluate_regulation_applicability_and_submittal([frp_hull], partial_package=True)
    assert res_true_frp["status"] == "NOT_APPLICABLE"
    assert res_true_frp["applicable_regulation_scope"]["clause_basis"] == "1.1.2"


def test_mk574_04_length_l_vs_lwl_and_threshold_straddle() -> None:
    """MK574-04: contradictory L vs Lwl -> CONFLICT; tolerance-straddling thresholds must never PASS."""
    # 1. Contradictory L=52m and Lwl=90m (0.96*90 = 86.4 > 52) -> CONFLICT
    ga_contra = _base_ga(
        drawing_id="GA_L_LWL_CONFLICT",
        length_line="Chiều dài tàu L = 52.00 m",
        extra_texts=[{"handle": "LW1", "text": "Lwl = 90.00 m", "x": 60000.0, "y": 5500.0, "height": 250.0}],
        bulkheads=4,
    )
    res_contra = evaluate_regulation_applicability_and_submittal([ga_contra, _base_mcn()], partial_package=True)
    assert res_contra["status"] == "CONFLICT"

    # 2. Tolerance-collapsed 40m boundary straddle: L=40.00m on GA vs L=40.04m on MCN with 3 bulkheads -> NOT PASS
    ga_40_00 = _base_ga(drawing_id="GA_40_00", length_line="Chiều dài tàu L = 40.00 m", bulkheads=3)
    mcn_40_04 = _base_mcn(drawing_id="MCN_40_04", length_line="Chiều dài tàu L = 40.04 m")
    res_40_straddle = evaluate_regulation_applicability_and_submittal([ga_40_00, mcn_40_04], partial_package=True)
    assert res_40_straddle["status"] in {"INSUFFICIENT_EVIDENCE", "CONFLICT"}

    # 3. Tolerance-collapsed 120m DB boundary straddle: 119.98m vs 120.02m with DB=750mm -> NOT PASS
    ga_119 = _base_ga(drawing_id="GA_119_98", length_line="Chiều dài tàu L = 119.98 m", bulkheads=6)
    mcn_120 = _base_mcn(drawing_id="MCN_120_02", length_line="Chiều dài tàu L = 120.02 m", db_mm=750.0)
    res_120_straddle = evaluate_regulation_applicability_and_submittal([ga_119, mcn_120], partial_package=True)
    assert res_120_straddle["status"] in {"INSUFFICIENT_EVIDENCE", "CONFLICT"}

    # 4. Tolerance-collapsed 140m scope boundary straddle: 139.98m vs 140.02m -> NOT PASS
    ga_139 = _base_ga(drawing_id="GA_139_98", length_line="Chiều dài tàu L = 139.98 m", bulkheads=6)
    mcn_140 = _base_mcn(drawing_id="MCN_140_02", length_line="Chiều dài tàu L = 140.02 m", db_mm=950.0)
    res_140_straddle = evaluate_regulation_applicability_and_submittal([ga_139, mcn_140], partial_package=True)
    assert res_140_straddle["status"] in {"INSUFFICIENT_EVIDENCE", "CONFLICT"}

    # 5. Positive control: consistent L=52.00m and Lwl=53.00m (0.96*53 = 50.88 <= 52 <= 53) -> PASS
    ga_ok = _base_ga(
        drawing_id="GA_L_LWL_OK",
        length_line="Chiều dài tàu L = 52.00 m",
        extra_texts=[{"handle": "LW2", "text": "Lwl = 53.00 m", "x": 60000.0, "y": 5500.0, "height": 250.0}],
        bulkheads=4,
    )
    res_ok = evaluate_regulation_applicability_and_submittal([ga_ok, _base_mcn()], partial_package=True)
    assert res_ok["status"] == "PASS"


def test_mk574_05_non_finite_and_invalid_structural_metrics_fail_closed() -> None:
    """MK574-05: NaN/Inf/fractional structural metrics fail closed without OverflowError or false PASS."""
    # 1. NaN double-bottom height -> NOT PASS
    res_nan_db = evaluate_regulation_applicability_and_submittal(
        [_base_ga(), _base_mcn(db_mm=float("nan"))], partial_package=True
    )
    assert res_nan_db["status"] in {"INSUFFICIENT_EVIDENCE", "CONFLICT"}

    # 2. +Inf bulkhead count -> MUST NOT raise OverflowError and MUST NOT return PASS
    res_inf_bh = evaluate_regulation_applicability_and_submittal(
        [_base_ga(bulkheads=float("inf")), _base_mcn()], partial_package=True
    )
    assert res_inf_bh["status"] in {"INSUFFICIENT_EVIDENCE", "CONFLICT"}

    # 3. Fractional bulkhead count 4.5 -> NOT PASS
    res_frac_bh = evaluate_regulation_applicability_and_submittal(
        [_base_ga(bulkheads=4.5), _base_mcn()], partial_package=True
    )
    assert res_frac_bh["status"] in {"INSUFFICIENT_EVIDENCE", "CONFLICT"}

    # 4. NaN plate thickness on 18m steel ship -> NOT PASS
    mcn_18_nan = _base_mcn(
        drawing_id="MCN_18_NAN",
        length_line="Chiều dài tàu L = 18.00 m",
        extra_metrics={
            "min_plate_thickness_mm": float("nan"),
            "min_bottom_plate_mm": 4.0,
            "min_bilge_plate_mm": 4.5,
        },
    )
    res_nan_plate = evaluate_regulation_applicability_and_submittal([mcn_18_nan], partial_package=True)
    assert res_nan_plate["status"] in {"INSUFFICIENT_EVIDENCE", "CONFLICT"}

    # 5. Positive control: valid finite metrics -> PASS
    res_valid = evaluate_regulation_applicability_and_submittal([_base_ga(), _base_mcn()], partial_package=True)
    assert res_valid["status"] == "PASS"


def test_mk574_06_dry_cargo_floor_spacing_limits() -> None:
    """MK574-06: enforce QCVN 72 Clause 2.4.3-1 floor spacing (1800 under hatch / 2000 outside / 2400 passenger-tanker)."""
    # 1. Dry cargo with 2200 mm floor spacing (> 2000 mm max for dry cargo) -> CONFLICT
    res_dry_2200 = evaluate_regulation_applicability_and_submittal(
        [_base_ga(), _base_mcn(floor_mm=2200.0)], partial_package=True
    )
    assert res_dry_2200["status"] == "CONFLICT"
    assert any(
        f["rule_id"] == "RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT" and f["verdict"] == "CONFLICT"
        for f in res_dry_2200["findings"]
    )

    # 2. Dry cargo with 1900 mm floor spacing & unresolved region -> INSUFFICIENT_EVIDENCE (not PASS)
    res_dry_1900_unknown = evaluate_regulation_applicability_and_submittal(
        [_base_ga(), _base_mcn(floor_mm=1900.0)], partial_package=True
    )
    assert res_dry_1900_unknown["status"] == "INSUFFICIENT_EVIDENCE"

    # 3. Dry cargo 1900 mm explicitly under cargo hatch -> CONFLICT
    res_dry_1900_hatch = evaluate_regulation_applicability_and_submittal(
        [_base_ga(), _base_mcn(floor_mm=1900.0, extra_metrics={"floor_spacing_region": "UNDER_CARGO_HATCH"})],
        partial_package=True,
    )
    assert res_dry_1900_hatch["status"] == "CONFLICT"

    # 4. Positive control: Dry cargo 1900 mm explicitly outside cargo hatch -> PASS
    res_dry_1900_outside = evaluate_regulation_applicability_and_submittal(
        [_base_ga(), _base_mcn(floor_mm=1900.0, extra_metrics={"floor_spacing_region": "OUTSIDE_CARGO_HATCH"})],
        partial_package=True,
    )
    assert res_dry_1900_outside["status"] == "PASS"

    # 5. Positive control: Dry cargo 1800 mm -> PASS; Oil tanker 2300 mm -> RULE_MK_09 PASS (<= 2400 mm)
    res_dry_1800 = evaluate_regulation_applicability_and_submittal(
        [_base_ga(), _base_mcn(floor_mm=1800.0)], partial_package=True
    )
    assert res_dry_1800["status"] == "PASS"

    res_tanker_2300 = evaluate_regulation_applicability_and_submittal(
        [_base_mcn(ship_type_line="SHIP TYPE : OIL TANKER", floor_mm=2300.0)], partial_package=True
    )
    assert any(
        f["rule_id"] == "RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT" and f["verdict"] == "PASS"
        for f in res_tanker_2300["findings"]
    )


def test_mk574_07_positive_applicability_dry_cargo_steel_hull_and_exceptions() -> None:
    """MK574-07: require positive DRY CARGO + STEEL hull; abstain on AL/unknown; do not forge exceptions_checked."""
    # 1. Missing SHIP TYPE -> RULE_MK_08 must NOT claim dry-cargo PASS
    ga_no_ship_type = _base_ga(ship_type_line="")
    res_no_type = evaluate_regulation_applicability_and_submittal(
        [ga_no_ship_type, _base_mcn(ship_type_line="")], partial_package=True
    )
    assert res_no_type["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(
        f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT" and f["verdict"] == "INSUFFICIENT_EVIDENCE"
        for f in res_no_type["findings"]
    )

    # 2. Aluminum hull (VR-SB AL / ALUMINUM ALLOY) -> steel RULE_MK_10 NOT_APPLICABLE, overall NOT PASS
    mcn_18_al = _base_mcn(
        drawing_id="MCN_18_AL",
        length_line="Chiều dài tàu L = 18.00 m",
        class_line="CẤP TÀU : VR-SB AL",
        material_line="HULL MATERIAL : ALUMINUM ALLOY",
        extra_metrics={"min_plate_thickness_mm": 4.5, "min_bottom_plate_mm": 4.5, "min_bilge_plate_mm": 4.5},
    )
    res_al = evaluate_regulation_applicability_and_submittal([mcn_18_al], partial_package=True)
    assert res_al["status"] in {"INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE"}
    assert any(
        f["rule_id"] == "RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL" and f["verdict"] == "NOT_APPLICABLE"
        for f in res_al["findings"]
    )

    # 3. Missing hull material -> steel scantling rules must NOT claim PASS
    res_no_mat = evaluate_regulation_applicability_and_submittal(
        [_base_ga(material_line=None), _base_mcn(material_line=None)], partial_package=True
    )
    assert res_no_mat["status"] == "INSUFFICIENT_EVIDENCE"

    # 4. Positive control: DRY CARGO + STEEL -> PASS and exceptions_checked does not falsely claim unverified 2.4.6-9 check
    res_ok = evaluate_regulation_applicability_and_submittal([_base_ga(), _base_mcn()], partial_package=True)
    assert res_ok["status"] == "PASS"
    mk08 = next(f for f in res_ok["findings"] if f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
    assert all("2.4.6-9" not in exc or "not evaluated" in exc.lower() or "chưa" in exc.lower() for exc in mk08["exceptions_checked"])


def test_mk574_08_missing_primary_metric_cannot_hide_submetric_defect_or_pass_mk09() -> None:
    """MK574-08: DB height alone cannot PASS RULE_MK_09; missing primary metric cannot hide girder/floor/plate defects."""
    # 1. DB height supplied WITHOUT girder/floor spacing -> RULE_MK_09 INSUFFICIENT_EVIDENCE (not PASS)
    res_db_only = evaluate_regulation_applicability_and_submittal(
        [_base_ga(), _base_mcn(db_mm=750.0, girder_mm=None, floor_mm=None)], partial_package=True
    )
    assert res_db_only["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(
        f["rule_id"] == "RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT" and f["verdict"] == "INSUFFICIENT_EVIDENCE"
        for f in res_db_only["findings"]
    )

    # 2. DB height ABSENT, girder spacing violates 3000 mm -> CONFLICT (not skipped)
    res_girder_fail = evaluate_regulation_applicability_and_submittal(
        [_base_ga(), _base_mcn(db_mm=None, girder_mm=3400.0, floor_mm=1600.0)], partial_package=True
    )
    assert res_girder_fail["status"] == "CONFLICT"
    assert any(
        f["rule_id"] == "RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT" and f["verdict"] == "CONFLICT"
        for f in res_girder_fail["findings"]
    )

    # 3. 18m steel ship: min_plate_thickness_mm ABSENT, min_bottom_plate_mm=1.0 -> CONFLICT (not PASS!)
    mcn_18_sub_fail = _base_mcn(
        drawing_id="MCN_18_BOTTOM_1MM",
        length_line="Chiều dài tàu L = 18.00 m",
        extra_metrics={"min_bottom_plate_mm": 1.0},
    )
    res_sub_plate = evaluate_regulation_applicability_and_submittal([mcn_18_sub_fail], partial_package=True)
    assert res_sub_plate["status"] == "CONFLICT"
    assert any(
        f["rule_id"] == "RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL" and f["verdict"] == "CONFLICT"
        for f in res_sub_plate["findings"]
    )

    # 4. Positive control: 18m steel ship with complete valid DB + spacing + plate/bottom/bilge -> PASS
    mcn_18_ok = _base_mcn(
        drawing_id="MCN_18_COMPLETE_OK",
        length_line="Chiều dài tàu L = 18.00 m",
        extra_metrics={"min_plate_thickness_mm": 4.5, "min_bottom_plate_mm": 4.5, "min_bilge_plate_mm": 4.5},
    )
    res_18_ok = evaluate_regulation_applicability_and_submittal([mcn_18_ok], partial_package=True)
    assert res_18_ok["status"] == "PASS"


def test_mk574_09_provenance_gating_on_all_structural_dependencies() -> None:
    """MK574-09: OCR/unknown provenance on length, spacing, sub-plate, or material blocks PASS."""
    # 1. OCR provenance on design_length_l_m
    res_ocr_len = evaluate_regulation_applicability_and_submittal(
        [
            _base_ga(metric_provenance={"design_length_l_m": "UNVERIFIED_OCR_TEXT"}),
            _base_mcn(metric_provenance={"design_length_l_m": "UNVERIFIED_OCR_TEXT"}),
        ],
        partial_package=True,
    )
    assert res_ocr_len["status"] == "INSUFFICIENT_EVIDENCE"

    # 2. Unknown provenance on girder / floor spacing
    res_unk_girder = evaluate_regulation_applicability_and_submittal(
        [_base_ga(), _base_mcn(metric_provenance={"bottom_girder_max_spacing_mm": "UNKNOWN_UNVERIFIED"})],
        partial_package=True,
    )
    assert res_unk_girder["status"] == "INSUFFICIENT_EVIDENCE"

    res_ocr_floor = evaluate_regulation_applicability_and_submittal(
        [_base_ga(), _base_mcn(metric_provenance={"transverse_floor_max_spacing_mm": "UNVERIFIED_OCR_TEXT"})],
        partial_package=True,
    )
    assert res_ocr_floor["status"] == "INSUFFICIENT_EVIDENCE"

    # 3. OCR provenance on min_bottom_plate_mm on 18m steel ship
    mcn_18_ocr_plate = _base_mcn(
        drawing_id="MCN_18_OCR_SUB",
        length_line="Chiều dài tàu L = 18.00 m",
        extra_metrics={"min_plate_thickness_mm": 4.5, "min_bottom_plate_mm": 4.5, "min_bilge_plate_mm": 4.5},
        metric_provenance={"min_bottom_plate_mm": "UNVERIFIED_OCR_TEXT"},
    )
    res_ocr_plate = evaluate_regulation_applicability_and_submittal([mcn_18_ocr_plate], partial_package=True)
    assert res_ocr_plate["status"] == "INSUFFICIENT_EVIDENCE"

    # 4. Positive control: NATIVE_CAD_TEXT / FIXTURE_SUPPLIED provenance -> PASS
    res_ok = evaluate_regulation_applicability_and_submittal([_base_ga(), _base_mcn()], partial_package=True)
    assert res_ok["status"] == "PASS"


def test_mk574_10_duplicate_or_default_drawing_id_preserves_per_sheet_classification() -> None:
    """MK574-10: duplicate or omitted drawing_id must not let sheet 2 overwrite sheet 1's classification."""
    # Sheet 1 is GA carrying misplaced DB/girder/floor metrics; Sheet 2 is MCN with NO DB metrics; both share ID
    ga_wrong = _base_ga(
        drawing_id="DUP_SHEET",
        extra_metrics={
            "double_bottom_height_mm": 750.0,
            "bottom_girder_max_spacing_mm": 2200.0,
            "transverse_floor_max_spacing_mm": 1800.0,
        },
    )
    mcn_empty_db = _base_mcn(drawing_id="DUP_SHEET", db_mm=None, girder_mm=None, floor_mm=None)
    res_dup = evaluate_regulation_applicability_and_submittal([ga_wrong, mcn_empty_db], partial_package=True)
    assert res_dup["status"] == "INSUFFICIENT_EVIDENCE"
    assert not any(
        f["rule_id"] == "RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT" and f["verdict"] == "PASS"
        for f in res_dup["findings"]
    )

    # Same attack when both omit drawing_id (defaulting to UNSPECIFIED_DRAWING)
    ga_no_id = _base_ga(
        include_drawing_id=False,
        extra_metrics={
            "double_bottom_height_mm": 750.0,
            "bottom_girder_max_spacing_mm": 2200.0,
            "transverse_floor_max_spacing_mm": 1800.0,
        },
    )
    mcn_no_id = _base_mcn(include_drawing_id=False, db_mm=None, girder_mm=None, floor_mm=None)
    res_no_id = evaluate_regulation_applicability_and_submittal([ga_no_id, mcn_no_id], partial_package=True)
    assert res_no_id["status"] == "INSUFFICIENT_EVIDENCE"
    assert not any(
        f["rule_id"] == "RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT" and f["verdict"] == "PASS"
        for f in res_no_id["findings"]
    )

    # Positive control: two distinct sheets omitting drawing_id with metrics on their proper sheets -> PASS
    res_ok_no_id = evaluate_regulation_applicability_and_submittal(
        [_base_ga(include_drawing_id=False), _base_mcn(include_drawing_id=False)],
        partial_package=True,
    )
    assert res_ok_no_id["status"] == "PASS"


def _build_insert_dxf_bytes(
    *,
    rotation_deg: float = 0.0,
    insert_x: float = 0.0,
    second_occurrence: bool = False,
    extrusion: tuple[float, float, float] | None = None,
) -> bytes:
    lines = [
        "0", "SECTION",
        "2", "HEADER",
        "9", "$ACADVER", "1", "AC1015",
        "9", "$INSUNITS", "70", "4",
        "9", "$MEASUREMENT", "70", "1",
        "0", "ENDSEC",
        "0", "SECTION",
        "2", "BLOCKS",
        "0", "BLOCK",
        "8", "0",
        "2", "BOW_BLK",
        "70", "0",
        "10", "0.0", "20", "0.0", "30", "0.0",
        "3", "BOW_BLK",
        "0", "TEXT", "8", "0", "10", "1000.0", "20", "0.0", "30", "0.0", "40", "300.0", "1", "A.P",
        "0", "TEXT", "8", "0", "10", "53000.0", "20", "0.0", "30", "0.0", "40", "300.0", "1", "F.P",
        "0", "ENDBLK",
        "0", "ENDSEC",
        "0", "SECTION",
        "2", "ENTITIES",
        "0", "TEXT", "8", "0", "10", "500.0", "20", "500.0", "30", "0.0", "40", "350.0", "1", "BAN VE BO TRI CHUNG",
        "0", "TEXT", "8", "0", "10", "500.0", "20", "1000.0", "30", "0.0", "40", "250.0", "1", "Lpp = 52.00 m",
        "0", "TEXT", "8", "0", "10", "500.0", "20", "1500.0", "30", "0.0", "40", "250.0", "1", "PORT OF REGISTRY : HAI PHONG",
        "0", "LINE", "8", "0", "10", "0.0", "20", "0.0", "30", "0.0", "11", "52000.0", "21", "0.0", "31", "0.0",
        "0", "INSERT", "8", "0", "2", "BOW_BLK",
        "10", f"{insert_x}", "20", "0.0", "30", "0.0",
        "41", "1.0", "42", "1.0", "43", "1.0",
        "50", f"{rotation_deg}",
    ]
    if extrusion is not None:
        lines.extend(["210", str(extrusion[0]), "220", str(extrusion[1]), "230", str(extrusion[2])])
    if second_occurrence:
        lines.extend(
            [
                "0", "INSERT", "8", "0", "2", "BOW_BLK",
                "10", "10000.0", "20", "5000.0", "30", "0.0",
                "41", "1.0", "42", "1.0", "43", "1.0",
                "50", "0.0",
            ]
        )
    lines.extend(["0", "ENDSEC", "0", "EOF", ""])
    return "\n".join(lines).encode("latin-1")


def test_mk574_11_insert_transforms_and_repeated_occurrences() -> None:
    """MK574-11: rotated INSERT reverses bow in WCS (CONFLICT); repeated INSERT preserves all instances."""
    # 1. 180 deg rotated INSERT at x=100000 puts A.P at 99000 and F.P at 47000 -> F_BOW_ORIENTATION CONFLICT
    rotated_dxf = _build_insert_dxf_bytes(rotation_deg=180.0, insert_x=100000.0)
    obs_rot = observe_dxf_bytes(rotated_dxf, drawing_id="GA_ROT180")
    ap_rot = obs_rot["particulars"]["ap_x_coords"]
    fp_rot = obs_rot["particulars"]["fp_x_coords"]
    assert ap_rot and fp_rot
    assert ap_rot[0] > fp_rot[0]
    gap_rot = detect_drawing_gaps_and_conflicts([obs_rot], partial_package=True)
    assert gap_rot["status"] == "CONFLICT"
    assert any("F_BOW_ORIENTATION" in f["finding_id"] for f in gap_rot["findings"])

    # 2. Repeated INSERT of same block preserves both occurrences (2 A.P + 2 F.P)
    dup_dxf = _build_insert_dxf_bytes(rotation_deg=0.0, insert_x=0.0, second_occurrence=True)
    obs_dup = observe_dxf_bytes(dup_dxf, drawing_id="GA_TWO_INSERTS")
    assert len(obs_dup["particulars"]["ap_x_coords"]) == 2
    assert len(obs_dup["particulars"]["fp_x_coords"]) == 2

    # 3. Unsupported 3D extrusion INSERT records unsupported transform warning rather than inventing coordinates
    ext_dxf = _build_insert_dxf_bytes(rotation_deg=0.0, insert_x=0.0, extrusion=(0.0, 1.0, 0.0))
    obs_ext = observe_dxf_bytes(ext_dxf, drawing_id="GA_3D_EXT")
    assert obs_ext.get("unsupported_insert_transforms")

    # 4. Positive control: unrotated single INSERT has A.P < F.P -> PASS (no bow conflict)
    normal_dxf = _build_insert_dxf_bytes(rotation_deg=0.0, insert_x=0.0)
    obs_ok = observe_dxf_bytes(normal_dxf, drawing_id="GA_NORMAL_INS")
    assert obs_ok["particulars"]["ap_x_coords"][0] < obs_ok["particulars"]["fp_x_coords"][0]
    gap_ok = detect_drawing_gaps_and_conflicts([obs_ok], partial_package=True)
    assert gap_ok["status"] == "PASS"


def test_mk574_12_metadata_only_empty_observation_cannot_pass_gap_check() -> None:
    """MK574-12: empty/METADATA_ONLY observation fails closed with INSUFFICIENT_EVIDENCE and honest checks_executed."""
    res_empty = validate_check_result(
        detect_drawing_gaps_and_conflicts([{"drawing_id": "EMPTY", "insunits": 4}])
    )
    assert res_empty["status"] == "INSUFFICIENT_EVIDENCE"
    assert not any(f["finding_id"] == "F_NO_GAPS_OR_CONFLICTS" for f in res_empty["findings"])
    assert not any("Bow direction" in chk for chk in res_empty["checks_executed"])

    # Positive control: populated valid package returns PASS and lists genuinely executed checks
    ga_with_lpp = _base_ga()
    mcn_with_lpp = _base_mcn()
    ga_with_lpp["texts"].append({"handle": "GA_LPP", "text": "Lpp = 52.00 m", "x": 60000.0, "y": 6000.0, "height": 250.0})
    mcn_with_lpp["texts"].append({"handle": "MCN_LPP", "text": "Lpp = 52.00 m", "x": 4000.0, "y": 3000.0, "height": 150.0})
    res_ok = validate_check_result(
        detect_drawing_gaps_and_conflicts([ga_with_lpp, mcn_with_lpp], partial_package=True)
    )
    assert res_ok["status"] == "PASS"
    assert any("Bow direction" in chk for chk in res_ok["checks_executed"])


def test_mk574_13_uppercase_draft_and_draught_extraction() -> None:
    """MK574-13: uppercase DRAFT/DRAUGHT must extract even though 'T' is in string; plate 't=' must stay excluded."""
    ga_draft = _base_ga(drawing_id="GA_UPPER_DRAFT", draft_line="DRAFT = 3.10 m")
    mcn_draught = _base_mcn(drawing_id="MCN_UPPER_DRAUGHT", draft_line="DRAUGHT = 5.10 m")

    obs_a = normalize_observation(ga_draft)
    obs_b = normalize_observation(mcn_draught)
    assert obs_a["particulars"]["draft_m_values"] == [3.1]
    assert obs_b["particulars"]["draft_m_values"] == [5.1]

    gap = detect_drawing_gaps_and_conflicts([ga_draft, mcn_draught], partial_package=True)
    assert gap["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_DIMENSION_CONFLICT_DRAFT" for f in gap["findings"])

    # Positive control: lowercase plate thickness "t = 8 mm" is NOT extracted as draft
    obs_plate = normalize_observation(
        _base_mcn(drawing_id="MCN_PLATE_NOT_DRAFT", draft_line="t = 8 mm")
    )
    assert obs_plate["particulars"]["draft_m_values"] == []


def test_p2a_qcvn51_ferrocement_year_matches_qcvn72_clause_1_1_2() -> None:
    """P2-A: QCVN 72:2025/BGTVT Clause 1.1.2 (PDF p.3 / reg p.19) cites QCVN 51:2013/BGTVT."""
    ferro_obs = _base_ga(
        drawing_id="FERRO_SHIP",
        class_line="TÀU XI MĂNG LƯỚI THÉP (QCVN 51:2013/BGTVT)",
        material_line="HULL MATERIAL : XI MĂNG LƯỚI THÉP",
    )
    res = evaluate_regulation_applicability_and_submittal([ferro_obs], partial_package=True)
    assert res["status"] == "NOT_APPLICABLE"
    assert res["applicable_regulation_scope"]["clause_basis"] == "1.1.2"
    assert res["applicable_regulation_scope"]["referred_regulation"] == "QCVN 51:2013/BGTVT"
