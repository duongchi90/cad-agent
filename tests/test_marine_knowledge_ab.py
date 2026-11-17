"""Deterministic A/B benchmark and adversarial regression suite for Marine Knowledge Pack V0."""

from __future__ import annotations

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
        {"handle": "4", "text": "Lpp = 52.00 m", "x": 50000.0, "y": 1500.0, "height": 250.0},
        {"handle": "5", "text": "B = 9.60 m", "x": 50000.0, "y": 2000.0, "height": 250.0},
        {"handle": "6", "text": "D = 4.20 m", "x": 50000.0, "y": 2500.0, "height": 250.0},
        {"handle": "7", "text": engine_line, "x": 50000.0, "y": 3000.0, "height": 250.0},
        {"handle": "8", "text": "SHIP TYPE : DRY CARGO", "x": 50000.0, "y": 3500.0, "height": 250.0},
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
            {"handle": "M4", "text": "Lpp = 52.00 m", "x": 4000.0, "y": 1250.0, "height": 150.0},
            {"handle": "M5", "text": "B = 9.60 m", "x": 4000.0, "y": 1500.0, "height": 150.0},
            {"handle": "M6", "text": "D = 4.20 m", "x": 4000.0, "y": 1750.0, "height": 150.0},
            {"handle": "M7", "text": engine_line, "x": 4000.0, "y": 2000.0, "height": 150.0},
        ],
        "structural_metrics": {
            "double_bottom_height_mm": db_mm,
            "bottom_girder_max_spacing_mm": 2200.0,
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
    ocean_trap = _ga_vrsb(drawing_id="GA_OCEAN_7000", insunits=0, service_line="SERVICE AREA : OCEAN GOING")
    ocean_trap["texts"][3]["text"] = "Lpp = 92.40 m"

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
                [_ga_vrsb(bulkheads=3), _mcn_vrsb(db_mm=550.0)], partial_package=True, enabled=en
            ),
            "CONFLICT",
        ),
        (
            "S3_OCEAN_SCOPE_TRAP",
            lambda en: evaluate_regulation_applicability_and_submittal(
                [ocean_trap], partial_package=True, enabled=en
            ),
            "NOT_APPLICABLE",
        ),
        (
            "S4_TITLE_CONTENT_MISMATCH",
            lambda en: classify_marine_drawing(thlt_bad_title, enabled=en),
            "CONFLICT",
        ),
        (
            "S5_CROSS_ENGINE_AND_BLANK_GAP",
            lambda en: detect_drawing_gaps_and_conflicts(
                [_ga_vrsb(include_blanks=True), _mcn_vrsb(engine_line="MAIN ENGINE : 1200 kW")],
                partial_package=True,
                enabled=en,
            ),
            "CONFLICT",
        ),
        (
            "S6_OCR_ONLY_FAIL_CLOSED",
            lambda en: detect_drawing_gaps_and_conflicts(
                [_ga_vrsb()], ocr_only_inputs=True, enabled=en
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
            assert finding["clause"]

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

    # Small hull L < 20m plate thickness < 2.5 mm must trigger RULE_MK_10 conflict
    small_hull = {
        "drawing_id": "MCN_18M_STEEL",
        "drawing_code": "KC-01",
        "insunits": 4,
        "texts": [
            {"handle": "S1", "text": "MẶT CẮT NGANG SƯỜN GIỮA", "x": 100.0, "y": 100.0, "height": 150.0},
            {"handle": "S2", "text": "CẤP TÀU : VR-SII", "x": 200.0, "y": 200.0, "height": 150.0},
            {"handle": "S3", "text": "Lpp = 18.00 m", "x": 200.0, "y": 400.0, "height": 150.0},
            {"handle": "S4", "text": "tôn đáy s=2.0 mm", "x": 200.0, "y": 600.0, "height": 150.0},
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

    reg = evaluate_regulation_applicability_and_submittal([thlt_obs, ga_obs], partial_package=True)
    assert reg["status"] == "NOT_APPLICABLE"
    assert "QCVN 21:2015/BGTVT" in reg["summary"]

    gap = detect_drawing_gaps_and_conflicts([thlt_obs, ga_obs], partial_package=True)
    assert gap["status"] == "CONFLICT"
    assert gap["cad_mutation"] is False
    assert gap["regulatory_compliance_proven"] is False
