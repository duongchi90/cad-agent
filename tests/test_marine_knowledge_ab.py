"""Deterministic A/B benchmark and adversarial regression suite for Marine Knowledge Pack V0."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import os
from pathlib import Path
from typing import Any

import pytest

from cad_agent.marine_knowledge import (
    classify_marine_drawing,
    detect_drawing_gaps_and_conflicts,
    evaluate_regulation_applicability_and_submittal,
    get_marine_knowledge_pack,
    get_marine_pack_status,
    lookup_term,
    observe_dxf_file,
    validate_check_result,
)


def _ga_vrsb(
    *,
    drawing_id: str = "GA_52M",
    insunits: int = 4,
    bulkheads: int = 4,
    include_blanks: bool = False,
    service_line: str = "CẤP TÀU : VR-SB",
    engine_line: str = "MAIN ENGINE : 2x550 HP",
) -> dict[str, Any]:
    texts = [
        {"handle": "1", "text": "BẢN VẼ BỐ TRÍ CHUNG", "x": 1000.0, "y": 500.0, "height": 350.0},
        {"handle": "2", "text": "KHOANG HÀNG SỐ 1 - BUỒNG MÁY - VÁCH CHỐNG VA", "x": 20000.0, "y": 2000.0, "height": 260.0},
        {"handle": "3", "text": service_line, "x": 50000.0, "y": 1000.0, "height": 250.0},
        {"handle": "4", "text": "Chiều dài tàu L = 52.00 m", "x": 50000.0, "y": 1500.0, "height": 250.0},
        {"handle": "5", "text": "B = 9.60 m", "x": 50000.0, "y": 2000.0, "height": 250.0},
        {"handle": "6", "text": "D = 4.20 m", "x": 50000.0, "y": 2500.0, "height": 250.0},
        {"handle": "7", "text": engine_line, "x": 50000.0, "y": 3000.0, "height": 250.0},
        {"handle": "8", "text": "SHIP TYPE : DRY CARGO", "x": 50000.0, "y": 3500.0, "height": 250.0},
        {"handle": "8B", "text": "HULL MATERIAL : STEEL", "x": 50000.0, "y": 3750.0, "height": 250.0},
        {"handle": "9", "text": "A.P", "x": 1000.0, "y": 0.0, "height": 300.0},
        {"handle": "10", "text": "F.P", "x": 53000.0, "y": 0.0, "height": 300.0},
    ]
    if include_blanks:
        texts.append({"handle": "11", "text": "PORT OF REGISTRY :", "x": 50000.0, "y": 4000.0, "height": 250.0})
    else:
        texts.append({"handle": "11", "text": "PORT OF REGISTRY : HAI PHONG", "x": 50000.0, "y": 4000.0, "height": 250.0})
    return {
        "drawing_id": drawing_id,
        "drawing_code": "GA-01-01",
        "insunits": insunits,
        "measurement": 1,
        "claimed_scale": 100.0,
        "texts": texts,
        "structural_metrics": {
            "transverse_watertight_bulkhead_count": bulkheads,
            "double_bottom_height_mm": 760.0,
            "bottom_girder_max_spacing_mm": 2400.0,
            "transverse_floor_max_spacing_mm": 1800.0,
        },
        "blank_fields": [],
    }


def _mcn_vrsb(
    *,
    drawing_id: str = "MCN_52M",
    db_mm: float = 760.0,
    engine_line: str = "MAIN ENGINE : 2x550 HP",
) -> dict[str, Any]:
    return {
        "drawing_id": drawing_id,
        "drawing_code": "KC-02-01",
        "insunits": 4,
        "measurement": 1,
        "claimed_scale": 50.0,
        "texts": [
            {"handle": "M1", "text": "MẶT CẮT NGANG SƯỜN GIỮA", "x": 500.0, "y": 500.0, "height": 200.0},
            {"handle": "M2", "text": "ĐÁY ĐÔI - ĐÀ NGANG ĐẶC", "x": 1000.0, "y": 600.0, "height": 150.0},
            {"handle": "M3", "text": "CẤP TÀU : VR-SB", "x": 4000.0, "y": 1000.0, "height": 150.0},
            {"handle": "M4", "text": "Chiều dài tàu L = 52.00 m", "x": 4000.0, "y": 1250.0, "height": 150.0},
            {"handle": "M5", "text": "B = 9.60 m", "x": 4000.0, "y": 1500.0, "height": 150.0},
            {"handle": "M6", "text": "D = 4.20 m", "x": 4000.0, "y": 1750.0, "height": 150.0},
            {"handle": "M7", "text": engine_line, "x": 4000.0, "y": 2000.0, "height": 150.0},
            {"handle": "M8", "text": "SHIP TYPE : DRY CARGO", "x": 4000.0, "y": 2250.0, "height": 150.0},
            {"handle": "M9", "text": "HULL MATERIAL : STEEL", "x": 4000.0, "y": 2500.0, "height": 150.0},
        ],
        "structural_metrics": {
            "double_bottom_height_mm": db_mm,
            "bottom_girder_max_spacing_mm": 2200.0,
            "transverse_floor_max_spacing_mm": 1800.0,
        },
        "blank_fields": [],
    }


def test_marine_pack_ab_benchmark_beats_baseline_and_stays_isolated() -> None:
    """Compare baseline disabled CAD core (A) vs Marine Knowledge Pack V0 (B) on 6 core cases."""
    thlt_bad_title = {
        "drawing_id": "THLT_CONTAMINATED",
        "drawing_code": "SF 01 -05 | GA- 01-01",
        "insunits": 4,
        "texts": [
            {"handle": "1", "text": "bè trÝ chung", "font_hint": ".VnAvantH", "x": 10.0, "y": 10.0, "height": 300.0},
            {"handle": "2", "text": "§.ChuÈn", "x": 10.0, "y": 200.0, "height": 250.0},
            {"handle": "3", "text": "ĐN 1 ĐN 2 CD1 CD2 Sn1 Sn10", "x": 10.0, "y": 400.0, "height": 250.0},
            {"handle": "4", "text": "TUYẾN HÌNH - BODY PLAN - HALF BREADTH", "x": 10.0, "y": 600.0, "height": 250.0},
        ],
    }
    ocean_bare = _ga_vrsb(drawing_id="GA_OCEAN_BARE", insunits=0, service_line="SERVICE AREA : OCEAN GOING")
    ocean_bare["texts"][3]["text"] = "Lpp = 92.40 m"

    ocean_explicit = _ga_vrsb(drawing_id="GA_OCEAN_VRH", insunits=4, service_line="SERVICE AREA : OCEAN GOING")
    ocean_explicit["texts"][3]["text"] = "Lpp = 92.40 m"
    ocean_explicit["texts"].append(
        {"handle": "12", "text": "CLASS : *VRH (QCVN 21:2015/BGTVT)", "x": 50000.0, "y": 4500.0, "height": 250.0}
    )

    scenarios = [
        (
            "S1_INLAND_VRSB_VALID",
            lambda en: evaluate_regulation_applicability_and_submittal(
                [_ga_vrsb(), _mcn_vrsb()], partial_package=True, enabled=en
            ),
            "PASS",
        ),
        (
            "S2_INLAND_SCANTLING_DEFECT",
            lambda en: evaluate_regulation_applicability_and_submittal(
                [
                    {
                        **_ga_vrsb(bulkheads=3),
                        "texts": _ga_vrsb(bulkheads=3)["texts"]
                        + [
                            {"handle": "NS1", "text": "HULL STRUCTURE : SINGLE SIDE", "x": 50000.0, "y": 4250.0, "height": 250.0},
                            {"handle": "NS2", "text": "SHIP TYPE : DRY CARGO NON-CONTAINER", "x": 50000.0, "y": 4500.0, "height": 250.0},
                        ],
                    },
                    _mcn_vrsb(db_mm=550.0),
                ],
                partial_package=True,
                enabled=en,
            ),
            "CONFLICT",
        ),
        (
            "S3_BARE_OCEAN_LABEL_FAIL_CLOSED",
            lambda en: evaluate_regulation_applicability_and_submittal(
                [ocean_bare], partial_package=True, enabled=en
            ),
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "S4_EXPLICIT_CLAUSE_111_EXCLUSION",
            lambda en: evaluate_regulation_applicability_and_submittal(
                [ocean_explicit], partial_package=True, enabled=en
            ),
            "NOT_APPLICABLE",
        ),
        (
            "S5_TITLE_CONTENT_MISMATCH",
            lambda en: classify_marine_drawing(thlt_bad_title, enabled=en),
            "CONFLICT",
        ),
        (
            "S6_CROSS_ENGINE_AND_BLANK_GAP",
            lambda en: detect_drawing_gaps_and_conflicts(
                [_ga_vrsb(include_blanks=True), _mcn_vrsb(engine_line="MAIN ENGINE : 1200 kW")],
                partial_package=True,
                enabled=en,
            ),
            "CONFLICT",
        ),
        (
            "S7_OCR_ONLY_FAIL_CLOSED",
            lambda en: detect_drawing_gaps_and_conflicts(
                [_ga_vrsb()], ocr_only_inputs=True, enabled=en
            ),
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "S8_UNSUPPORTED_REGULATION_VERSION",
            lambda en: evaluate_regulation_applicability_and_submittal(
                [_ga_vrsb()], target_regulation="QCVN_72_2014_BGTVT", enabled=en
            ),
            "INSUFFICIENT_EVIDENCE",
        ),
    ]

    a_domain_detections = 0
    b_passes = 0
    b_mutations = 0
    b_class_proofs = 0

    for _name, runner, expected_b in scenarios:
        res_a = validate_check_result(runner(False))
        res_b = validate_check_result(runner(True))

        assert res_a["status"] == "DISABLED"
        assert res_a["pack_status"] == "DISABLED"
        assert res_a["findings"] == []
        if res_a["findings"]:
            a_domain_detections += 1

        assert res_b["status"] == expected_b
        assert res_b["cad_mutation"] is False
        assert res_b["regulatory_compliance_proven"] is False
        b_passes += 1
        b_mutations += int(res_b["cad_mutation"])
        b_class_proofs += int(res_b["regulatory_compliance_proven"])
        for finding in res_b["findings"]:
            assert finding["source_id"]
            assert len(finding["source_sha256"]) == 64
            assert finding["clause"]
            assert finding["pagination_basis"]

    assert a_domain_detections == 0
    assert b_passes == len(scenarios)
    assert b_mutations == 0
    assert b_class_proofs == 0


def test_marine_regression_bow_z_compression_small_hull_and_empty_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify adversarial cases: reversed bow, Z-axis distortion, small-hull <20m floor, and empty package."""
    reversed_obs = _ga_vrsb(drawing_id="GA_REVERSED_BOW", include_blanks=False)
    for txt in reversed_obs["texts"]:
        if txt["text"] == "A.P":
            txt["x"] = 55000.0
        elif txt["text"] == "F.P":
            txt["x"] = 1000.0
    reversed_obs["structural_metrics"]["body_plan_wl_span_mm"] = 5200.0  # D=4.20 m -> ratio 1.238 > 1.12

    gap_res = detect_drawing_gaps_and_conflicts([reversed_obs], partial_package=True)
    assert gap_res["status"] == "CONFLICT"
    finding_ids = {f["finding_id"] for f in gap_res["findings"]}
    assert "F_BOW_ORIENTATION_GA_REVERSED_BOW" in finding_ids
    assert "F_Z_SCALE_DISTORTION_GA_REVERSED_BOW" in finding_ids

    # Small hull L < 20m (>=50 HP outside QCVN 25) plate thickness < 2.5 mm must trigger RULE_MK_10 conflict
    small_hull = {
        "drawing_id": "MCN_18M_STEEL",
        "drawing_code": "KC-01",
        "insunits": 4,
        "texts": [
            {"handle": "S1", "text": "MẶT CẮT NGANG SƯỜN GIỮA", "x": 100.0, "y": 100.0, "height": 150.0},
            {"handle": "S2", "text": "CẤP TÀU : VR-SII", "x": 200.0, "y": 200.0, "height": 150.0},
            {"handle": "S3", "text": "Chiều dài tàu L = 18.00 m", "x": 200.0, "y": 400.0, "height": 150.0},
            {"handle": "S4", "text": "tôn đáy s=2.0 mm", "x": 200.0, "y": 600.0, "height": 150.0},
            {"handle": "S5", "text": "HULL MATERIAL : STEEL", "x": 200.0, "y": 800.0, "height": 150.0},
            {"handle": "S6", "text": "MAIN ENGINE : 120 HP", "x": 200.0, "y": 950.0, "height": 150.0},
        ],
        "structural_metrics": {"double_bottom_height_mm": 750.0},
    }
    reg_small = evaluate_regulation_applicability_and_submittal([small_hull], partial_package=True)
    assert reg_small["status"] == "CONFLICT"
    assert any(
        f["rule_id"] == "RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL" and f["verdict"] == "CONFLICT"
        for f in reg_small["findings"]
    )

    # Empty observation list fails closed
    empty_reg = evaluate_regulation_applicability_and_submittal([])
    empty_gap = detect_drawing_gaps_and_conflicts([])
    assert empty_reg["status"] == "INSUFFICIENT_EVIDENCE"
    assert empty_gap["status"] == "INSUFFICIENT_EVIDENCE"

    # Toggle false env value keeps pack enabled, whereas '1' disables cleanly
    monkeypatch.setenv("CAD_AGENT_DISABLE_MARINE_PACK", "0")
    assert get_marine_pack_status()["status"] == "CANDIDATE_UNAPPROVED"
    assert get_marine_knowledge_pack()["cad_mutation"] is False
    assert lookup_term("vách chống va") is not None

    monkeypatch.setenv("CAD_AGENT_DISABLE_MARINE_PACK", "1")
    assert get_marine_pack_status()["status"] == "DISABLED"
    assert lookup_term("vách chống va") is None
    assert classify_marine_drawing(_ga_vrsb())["status"] == "DISABLED"


def test_step3_qcvn72_applicability_and_exclusion_matrix() -> None:
    """Cover every Step 3 applicability branch: inland, explicit exclusions, unknown, conflict, stale/unsupported."""
    # 1. Explicit exclusion: FRP hull governed by QCVN 56:2013/BGTVT
    frp_obs = {
        "drawing_id": "FRP_CRAFT_12M",
        "insunits": 4,
        "texts": [
            {"handle": "1", "text": "GENERAL ARRANGEMENT - VỎ FRP (QCVN 56:2013/BGTVT)", "x": 10.0, "y": 10.0, "height": 200.0},
            {"handle": "2", "text": "Lpp = 12.00 m", "x": 10.0, "y": 200.0, "height": 200.0},
        ],
    }
    res_frp = evaluate_regulation_applicability_and_submittal([frp_obs])
    assert res_frp["status"] == "NOT_APPLICABLE"

    # 2. Explicit exclusion: proven design length L > 140 m per Clause 1.1.1 / 1.4.43-1,
    # whereas bare Lpp > 140 m without L or Lwl fails closed with INSUFFICIENT_EVIDENCE.
    long_obs = _ga_vrsb(drawing_id="LONG_155M")
    long_obs["texts"][3]["text"] = "Chiều dài tàu L = 155.00 m"
    res_long = evaluate_regulation_applicability_and_submittal([long_obs])
    assert res_long["status"] == "NOT_APPLICABLE"
    assert res_long["applicable_regulation_scope"]["clause_basis"] == "1.1.1"

    long_lpp_only = _ga_vrsb(drawing_id="LONG_LPP_155M")
    long_lpp_only["texts"][3]["text"] = "Lpp = 155.00 m"
    res_long_lpp = evaluate_regulation_applicability_and_submittal([long_lpp_only])
    assert res_long_lpp["status"] == "INSUFFICIENT_EVIDENCE"
    assert {f["finding_id"] for f in res_long_lpp["findings"]} >= {"F_LENGTH_L_UNPROVEN_FOR_140M_LIMIT"}

    # 3. Unknown classification (no VR, QCVN, or ocean markers)
    unknown_obs = {
        "drawing_id": "UNKNOWN_SHIP",
        "insunits": 4,
        "texts": [
            {"handle": "1", "text": "BẢN VẼ BỐ TRÍ CHUNG", "x": 10.0, "y": 10.0, "height": 200.0},
            {"handle": "2", "text": "KHOANG HÀNG SỐ 1 - BUỒNG MÁY", "x": 10.0, "y": 200.0, "height": 200.0},
        ],
    }
    res_unknown = evaluate_regulation_applicability_and_submittal([unknown_obs])
    assert res_unknown["status"] == "INSUFFICIENT_EVIDENCE"

    # 4. Conflicting inland class grades (VR-SB vs VR-SII across drawings)
    res_class_conflict = evaluate_regulation_applicability_and_submittal(
        [_ga_vrsb(service_line="CẤP TÀU : VR-SB"), _mcn_vrsb() | {"texts": [{"handle": "C", "text": "CẤP TÀU : VR-SII", "x": 10.0, "y": 10.0, "height": 150.0}]}]
    )
    assert res_class_conflict["status"] == "CONFLICT"


@pytest.mark.real_data
def test_marine_7000_real_dxf_ab_validation() -> None:
    """Private real-data verification over Marine-7000 DXFs when env paths are supplied outside Git."""
    thlt_path = os.environ.get("CAD_AGENT_MARINE_THLT_DXF")
    ga_path = os.environ.get("CAD_AGENT_MARINE_GA_DXF")
    if not thlt_path or not ga_path:
        pytest.skip("set CAD_AGENT_MARINE_THLT_DXF and CAD_AGENT_MARINE_GA_DXF for real Marine DXF validation")

    thlt_obs = observe_dxf_file(Path(thlt_path), drawing_id="THLT7000")
    ga_obs = observe_dxf_file(Path(ga_path), drawing_id="GA7000")

    cls_thlt = classify_marine_drawing(thlt_obs)
    assert cls_thlt["status"] == "CONFLICT"
    assert cls_thlt["observed_scope"]["predicted_drawing_type"] == "LINES_PLAN"
    assert cls_thlt["observed_scope"]["title_declared_type"] == "GENERAL_ARRANGEMENT"

    # Real Marine-7000 carries free-text 'OCEAN GOING' with blank Port of Registry and zero Class/QCVN/VR notation:
    # Step 3 requires fail-closed INSUFFICIENT_EVIDENCE instead of definitive legal NOT_APPLICABLE.
    reg = evaluate_regulation_applicability_and_submittal([thlt_obs, ga_obs], partial_package=True)
    assert reg["status"] == "INSUFFICIENT_EVIDENCE"
    assert "QCVN 21:2025/BGTVT" in reg["summary"]

    gap_ga = detect_drawing_gaps_and_conflicts([ga_obs], partial_package=True)
    assert not any("1000x" in chk or "Bow direction" in chk for chk in gap_ga["checks_executed"])
    assert any("1000x" in chk for chk in gap_ga["checks_not_executed"])
    assert any("Bow direction" in chk and "unresolved" in chk.lower() for chk in gap_ga["checks_not_executed"])

    gap = detect_drawing_gaps_and_conflicts([thlt_obs, ga_obs], partial_package=True)
    assert gap["status"] == "CONFLICT"
    assert not any("1000x" in chk or "Bow direction" in chk for chk in gap["checks_executed"])
    assert any("1000x" in chk for chk in gap["checks_not_executed"])
    assert any("Bow direction" in chk and "unresolved" in chk.lower() for chk in gap["checks_not_executed"])
    assert gap["cad_mutation"] is False
    assert gap["regulatory_compliance_proven"] is False


def generic_cad_baseline_inspect(
    observations: Sequence[dict[str, Any]],
    *,
    calibration_verified: bool = False,
    verified_scale_to_mm: float | None = None,
    ocr_only_inputs: bool = False,
) -> str:
    """Honest non-marine CAD baseline: checks INSUNITS, OCR flag, blank colons, and zero primitives only."""
    if not observations:
        return "INSUFFICIENT_EVIDENCE"
    if ocr_only_inputs or any(bool(obs.get("ocr_only")) for obs in observations):
        return "INSUFFICIENT_EVIDENCE"
    unitless = any(int(obs.get("insunits", 0)) not in {4, 5, 6} for obs in observations)
    # Generic CAD tool naively accepts any positive scale even without verified calibration
    has_scale = calibration_verified or (verified_scale_to_mm is not None and verified_scale_to_mm > 0)
    if unitless and not has_scale:
        return "INSUFFICIENT_EVIDENCE"
    for obs in observations:
        counts = obs.get("entity_counts") or {}
        if counts:
            prims = sum(
                int(counts.get(k, 0) or 0)
                for k in ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "SPLINE", "ELLIPSE")
            )
            if prims == 0:
                return "INSUFFICIENT_EVIDENCE"
        if obs.get("blank_fields"):
            return "INSUFFICIENT_EVIDENCE"
    return "PASS"


def _build_16_ground_truth_cases() -> list[tuple[str, str, list[dict[str, Any]], Callable[[], dict[str, Any]], dict[str, Any]]]:
    valid_ga = _ga_vrsb(bulkheads=4)
    valid_mcn = _mcn_vrsb(db_mm=760.0)

    small_valid = {
        "drawing_id": "MCN_18M_OK",
        "drawing_code": "KC-01",
        "insunits": 4,
        "texts": [
            {"handle": "1", "text": "MẶT CẮT NGANG SƯỜN GIỮA", "x": 100.0, "y": 100.0, "height": 150.0},
            {"handle": "2", "text": "CẤP TÀU : VR-SII", "x": 200.0, "y": 200.0, "height": 150.0},
            {"handle": "3", "text": "Chiều dài tàu L = 18.00 m", "x": 200.0, "y": 400.0, "height": 150.0},
            {"handle": "4", "text": "tôn đáy s=4.5 mm", "x": 200.0, "y": 600.0, "height": 150.0},
            {"handle": "5", "text": "tôn hông s=4.5 mm", "x": 200.0, "y": 750.0, "height": 150.0},
            {"handle": "6", "text": "SHIP TYPE : DRY CARGO", "x": 200.0, "y": 900.0, "height": 150.0},
            {"handle": "7", "text": "HULL MATERIAL : STEEL", "x": 200.0, "y": 1050.0, "height": 150.0},
            {"handle": "8", "text": "MAIN ENGINE : 120 HP", "x": 200.0, "y": 1200.0, "height": 150.0},
        ],
        "structural_metrics": {
            "double_bottom_height_mm": 750.0,
            "bottom_girder_max_spacing_mm": 2200.0,
            "transverse_floor_max_spacing_mm": 1800.0,
        },
    }
    small_bad_plate = {
        **small_valid,
        "drawing_id": "MCN_18M_THIN",
        "texts": [
            *small_valid["texts"][:3],
            {"handle": "4", "text": "tôn đáy s=2.0 mm", "x": 200.0, "y": 600.0, "height": 150.0},
            {"handle": "6", "text": "SHIP TYPE : DRY CARGO", "x": 200.0, "y": 900.0, "height": 150.0},
            {"handle": "7", "text": "HULL MATERIAL : STEEL", "x": 200.0, "y": 1050.0, "height": 150.0},
            {"handle": "8", "text": "MAIN ENGINE : 120 HP", "x": 200.0, "y": 1200.0, "height": 150.0},
        ],
    }

    cross_ga = _ga_vrsb(drawing_id="CROSS_GA")
    cross_ga["texts"].extend(
        [
            {"handle": "D1", "text": "T = 3.10 m", "x": 50000.0, "y": 4500.0, "height": 250.0},
            {"handle": "H1", "text": "HULL NO : H-01", "x": 50000.0, "y": 5000.0, "height": 250.0},
        ]
    )
    cross_mcn = _mcn_vrsb(drawing_id="CROSS_MCN", db_mm=750.0)
    cross_mcn["texts"].extend(
        [
            {"handle": "D2", "text": "T = 4.40 m", "x": 4000.0, "y": 2250.0, "height": 150.0},
            {"handle": "S2", "text": "SHIP TYPE : OIL TANKER", "x": 4000.0, "y": 2500.0, "height": 150.0},
            {"handle": "H2", "text": "HULL NO : H-99", "x": 4000.0, "y": 2750.0, "height": 150.0},
        ]
    )

    span_1000x = _ga_vrsb(drawing_id="SPAN_1000X", insunits=6)  # meters header vs mm coords 1000..53000
    span_1000x["texts"].append({"handle": "LPP_SPAN", "text": "Lpp = 52.00 m", "x": 60000.0, "y": 6100.0, "height": 250.0})

    reversed_bow = _ga_vrsb(drawing_id="BOW_Z_ERR")
    for t in reversed_bow["texts"]:
        if t["text"] == "A.P":
            t["x"] = 55000.0
        elif t["text"] == "F.P":
            t["x"] = 1000.0
    reversed_bow["structural_metrics"]["body_plan_wl_span_mm"] = 5200.0

    tcvn3_mismatch = {
        "drawing_id": "THLT_TCVN3_MISMATCH",
        "drawing_code": "GA-01-01",
        "insunits": 4,
        "texts": [
            {"handle": "1", "text": "bè trÝ chung", "font_hint": ".VnAvantH", "x": 10.0, "y": 10.0, "height": 300.0},
            {"handle": "2", "text": "§.ChuÈn", "x": 10.0, "y": 200.0, "height": 250.0},
            {"handle": "3", "text": "ĐN 1 ĐN 2 CD1 CD2 Sn1 Sn10", "x": 10.0, "y": 400.0, "height": 250.0},
        ],
    }

    no_len_ga = {
        "drawing_id": "NO_LEN_GA",
        "drawing_code": "GA-01",
        "insunits": 4,
        "texts": [
            {"handle": "1", "text": "BẢN VẼ BỐ TRÍ CHUNG", "x": 100.0, "y": 100.0, "height": 250.0},
            {"handle": "2", "text": "KHOANG HÀNG - BUỒNG MÁY - VÁCH CHỐNG VA", "x": 200.0, "y": 200.0, "height": 250.0},
            {"handle": "3", "text": "CẤP TÀU : VR-SB", "x": 300.0, "y": 300.0, "height": 250.0},
        ],
        "structural_metrics": {"transverse_watertight_bulkhead_count": 4},
    }

    boundary_ga = _ga_vrsb(drawing_id="BOUNDARY_39_5M", bulkheads=3)
    boundary_ga["texts"][3]["text"] = "Lpp = 39.50 m"
    boundary_ga["texts"][9]["x"] = 40500.0
    boundary_mcn = _mcn_vrsb(drawing_id="BOUNDARY_MCN")
    boundary_mcn["texts"][3]["text"] = "Lpp = 39.50 m"

    wrong_sheet_thlt = {
        "drawing_id": "THLT_WRONG_METRIC",
        "drawing_code": "THLT-01",
        "insunits": 4,
        "texts": [
            {"handle": "1", "text": "TUYẾN HÌNH LÝ THUYẾT", "x": 10.0, "y": 10.0, "height": 250.0},
            {"handle": "2", "text": "ĐN 1 ĐN 2 CD1 Sn1", "x": 10.0, "y": 300.0, "height": 250.0},
            {"handle": "3", "text": "CẤP TÀU : VR-SB", "x": 10.0, "y": 600.0, "height": 250.0},
            {"handle": "4", "text": "Chiều dài tàu L = 52.00 m", "x": 10.0, "y": 900.0, "height": 250.0},
        ],
        "structural_metrics": {"double_bottom_height_mm": 750.0},
    }

    unitless_ga = _ga_vrsb(drawing_id="UNITLESS_GA", insunits=0)
    unitless_mcn = {**_mcn_vrsb(drawing_id="UNITLESS_MCN"), "insunits": 0}

    negated_ga = {
        "drawing_id": "NEGATED_VRSI",
        "drawing_code": "GA-01",
        "insunits": 4,
        "texts": [
            {"handle": "1", "text": "BẢN VẼ BỐ TRÍ CHUNG", "x": 10.0, "y": 10.0, "height": 250.0},
            {"handle": "2", "text": "KHÔNG ÁP DỤNG VR-SI CHO TÀU NÀY", "x": 10.0, "y": 250.0, "height": 250.0},
            {"handle": "3", "text": "Chiều dài tàu L = 52.00 m", "x": 10.0, "y": 500.0, "height": 250.0},
        ],
        "structural_metrics": {"transverse_watertight_bulkhead_count": 4},
    }

    corrupt_ga = _ga_vrsb(drawing_id="CORRUPT_OCR")
    corrupt_ga["texts"][3]["text"] = "Lpp = 52.O5 m"

    zero_geom_ga = {**_ga_vrsb(drawing_id="ZERO_GEOM"), "entity_counts": {"TEXT": 12, "LINE": 0, "LWPOLYLINE": 0}}

    mech_shaft = {
        "drawing_id": "SHAFT_C45",
        "drawing_code": "CK-01",
        "insunits": 4,
        "texts": [
            {"handle": "1", "text": "CHI TIẾT TRỤC BẠC ĐẠN", "x": 10.0, "y": 10.0, "height": 200.0},
            {"handle": "2", "text": "VẬT LIỆU : THÉP C45 - L = 1200 mm", "x": 10.0, "y": 250.0, "height": 200.0},
        ],
    }

    sea_vrh = {
        **_ga_vrsb(drawing_id="SEA_VRH"),
        "texts": [
            {"handle": "1", "text": "GENERAL ARRANGEMENT SEA SHIP", "x": 10.0, "y": 10.0, "height": 250.0},
            {"handle": "2", "text": "CLASS : *VRH (QCVN 21:2015/BGTVT)", "x": 10.0, "y": 300.0, "height": 250.0},
            {"handle": "3", "text": "L = 92.40 m", "x": 10.0, "y": 600.0, "height": 250.0},
        ],
    }

    return [
        ("C01_VALID_INLAND_GA_MCN_52M", "PASS", [valid_ga, valid_mcn], lambda: evaluate_regulation_applicability_and_submittal([valid_ga, valid_mcn], partial_package=True), {}),
        ("C02_VALID_INLAND_SMALL_HULL_18M", "PASS", [small_valid], lambda: evaluate_regulation_applicability_and_submittal([small_valid], partial_package=True), {}),
        ("C03_CROSS_SHEET_CONFLICT_PACKAGE", "CONFLICT", [cross_ga, cross_mcn], lambda: detect_drawing_gaps_and_conflicts([cross_ga, cross_mcn], partial_package=True), {}),
        ("C04_SPAN_MISMATCH_1000X_INSUNITS6", "CONFLICT", [span_1000x], lambda: detect_drawing_gaps_and_conflicts([span_1000x], partial_package=True), {}),
        ("C05_SMALL_HULL_PLATE_LT_2_5MM", "CONFLICT", [small_bad_plate], lambda: evaluate_regulation_applicability_and_submittal([small_bad_plate], partial_package=True), {}),
        ("C06_REVERSED_BOW_AND_Z_DISTORTION", "CONFLICT", [reversed_bow], lambda: detect_drawing_gaps_and_conflicts([reversed_bow], partial_package=True), {}),
        ("C07_TCVN3_TITLE_VS_CONTENT_MISMATCH", "CONFLICT", [tcvn3_mismatch], lambda: classify_marine_drawing(tcvn3_mismatch), {}),
        ("C08_MISSING_LENGTH", "INSUFFICIENT_EVIDENCE", [no_len_ga], lambda: evaluate_regulation_applicability_and_submittal([no_len_ga], partial_package=True), {}),
        ("C09_LPP_BOUNDARY_39_5M_AMBIGUOUS", "INSUFFICIENT_EVIDENCE", [boundary_ga, boundary_mcn], lambda: evaluate_regulation_applicability_and_submittal([boundary_ga, boundary_mcn], partial_package=True), {}),
        ("C10_WRONG_SHEET_METRIC_THLT", "INSUFFICIENT_EVIDENCE", [wrong_sheet_thlt], lambda: evaluate_regulation_applicability_and_submittal([wrong_sheet_thlt], partial_package=True), {}),
        ("C11_UNITLESS_UNVERIFIED_SCALE", "INSUFFICIENT_EVIDENCE", [unitless_ga, unitless_mcn], lambda: evaluate_regulation_applicability_and_submittal([unitless_ga, unitless_mcn], calibration_verified=False, verified_scale_to_mm=1.0), {"calibration_verified": False, "verified_scale_to_mm": 1.0}),
        ("C12_NEGATED_VRSI_NO_FALSE_INCLUSION", "INSUFFICIENT_EVIDENCE", [negated_ga], lambda: evaluate_regulation_applicability_and_submittal([negated_ga], partial_package=True), {}),
        ("C13_OCR_CORRUPTED_NUMERIC_52O5", "INSUFFICIENT_EVIDENCE", [corrupt_ga], lambda: detect_drawing_gaps_and_conflicts([corrupt_ga], partial_package=True), {}),
        ("C14_TEXT_ONLY_ZERO_GEOMETRY_SHELL", "INSUFFICIENT_EVIDENCE", [zero_geom_ga], lambda: detect_drawing_gaps_and_conflicts([zero_geom_ga], partial_package=True), {}),
        ("C15_NON_MARINE_SHAFT_OUT_OF_DOMAIN", "NOT_APPLICABLE", [mech_shaft], lambda: evaluate_regulation_applicability_and_submittal([mech_shaft], partial_package=True), {}),
        ("C16_EXPLICIT_QCVN21_SEA_SHIP_EXCLUSION", "NOT_APPLICABLE", [sea_vrh], lambda: evaluate_regulation_applicability_and_submittal([sea_vrh], partial_package=True), {}),
    ]


def score_ab_predictions(rows: Sequence[tuple[str, str, str]]) -> dict[str, Any]:
    """Compute conflict confusion matrix + false-PASS + abstention counts over (case_id, gold, pred)."""
    tp = sum(1 for _cid, gold, pred in rows if gold == "CONFLICT" and pred == "CONFLICT")
    fp = sum(1 for _cid, gold, pred in rows if gold != "CONFLICT" and pred == "CONFLICT")
    fn = sum(1 for _cid, gold, pred in rows if gold == "CONFLICT" and pred != "CONFLICT")
    tn = sum(1 for _cid, gold, pred in rows if gold != "CONFLICT" and pred != "CONFLICT")
    exact = sum(1 for _cid, gold, pred in rows if gold == pred)
    false_pass = sum(1 for _cid, gold, pred in rows if gold != "PASS" and pred == "PASS")
    app_abstain = sum(1 for _cid, gold, pred in rows if gold == "INSUFFICIENT_EVIDENCE" and pred == "INSUFFICIENT_EVIDENCE")
    over_abstain = sum(1 for _cid, gold, pred in rows if gold != "INSUFFICIENT_EVIDENCE" and pred == "INSUFFICIENT_EVIDENCE")
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return {
        "total": len(rows),
        "exact_verdict_matches": exact,
        "tp_conflict": tp,
        "fp_conflict": fp,
        "fn_conflict": fn,
        "tn_non_conflict": tn,
        "precision_conflict": round(prec, 4),
        "recall_conflict": round(rec, 4),
        "false_pass": false_pass,
        "appropriate_abstention": app_abstain,
        "over_abstention": over_abstain,
    }


def test_marine_independent_engineering_baseline_comparison() -> None:
    """Part B (Internal Developer-Authored Regression): Compare Generic CAD Baseline Inspector vs Marine Knowledge Pack V0 on 16 synthetic fixtures (not an independent or blind benchmark)."""
    cases = _build_16_ground_truth_cases()
    assert len(cases) == 16

    baseline_rows: list[tuple[str, str, str]] = []
    pack_rows: list[tuple[str, str, str]] = []
    for cid, gold, obs_list, fn_pack, base_kwargs in cases:
        base_pred = generic_cad_baseline_inspect(obs_list, **base_kwargs)
        pack_res = validate_check_result(fn_pack())
        assert pack_res["cad_mutation"] is False
        assert pack_res["regulatory_compliance_proven"] is False
        baseline_rows.append((cid, gold, base_pred))
        pack_rows.append((cid, gold, pack_res["status"]))

    base_metrics = score_ab_predictions(baseline_rows)
    pack_metrics = score_ab_predictions(pack_rows)

    assert pack_metrics["exact_verdict_matches"] == 16
    assert pack_metrics["tp_conflict"] == 5
    assert pack_metrics["fp_conflict"] == 0
    assert pack_metrics["fn_conflict"] == 0
    assert pack_metrics["false_pass"] == 0
    assert pack_metrics["appropriate_abstention"] == 7
    assert pack_metrics["over_abstention"] == 0
    assert pack_metrics["precision_conflict"] == 1.0
    assert pack_metrics["recall_conflict"] == 1.0

    # Baseline catches C14 (empty geometry shell) -> 1 appropriate abstention, misses 13 hazards (13 False PASS, 0 conflicts caught)
    assert base_metrics["false_pass"] >= 10
    assert base_metrics["tp_conflict"] == 0
    assert base_metrics["exact_verdict_matches"] < pack_metrics["exact_verdict_matches"]
