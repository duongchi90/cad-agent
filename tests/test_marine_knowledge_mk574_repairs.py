"""Causal RED->GREEN regression tests and positive controls for MK574-01..MK574-13 (PR #574)."""

from __future__ import annotations

import hashlib
from typing import Any

import fitz
import pytest

from cad_agent.marine_knowledge import (
    MarineKnowledgeError,
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
        "2.1.2 Beta rule governs totally separate rudder shaft torque limits.\n",
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
