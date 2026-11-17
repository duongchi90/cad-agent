from __future__ import annotations


def _inland_vrsb_ga_obs(*, bulkheads: int = 4, lpp_mm: float = 52000.0, insunits: int = 4, include_blanks: bool = False):
    texts = [
        {"handle": "T1", "text": "BẢN VẼ BỐ TRÍ CHUNG TOÀN TÀU", "layer": "TEXT", "x": 1000.0, "y": 500.0, "height": 350.0},
        {"handle": "T2", "text": "SƯỜN GIỮA", "layer": "TEXT", "x": 25000.0, "y": 2000.0, "height": 300.0},
        {"handle": "T3", "text": "KHOANG HÀNG SỐ 1", "layer": "PV", "x": 30000.0, "y": 3000.0, "height": 260.0},
        {"handle": "T4", "text": "BUỒNG MÁY", "layer": "PV", "x": 12000.0, "y": 3000.0, "height": 260.0},
        {"handle": "T5", "text": "VÁCH CHỐNG VA", "layer": "PV", "x": 49000.0, "y": 3000.0, "height": 260.0},
        {"handle": "T6", "text": "CẤP TÀU : VR-SB", "layer": "0", "x": 60000.0, "y": 1000.0, "height": 250.0},
        {"handle": "T7", "text": f"Lpp = {lpp_mm / 1000.0:.2f} m", "layer": "0", "x": 60000.0, "y": 1500.0, "height": 250.0},
        {"handle": "T8", "text": "B = 9.60 m", "layer": "0", "x": 60000.0, "y": 2000.0, "height": 250.0},
        {"handle": "T9", "text": "D = 4.20 m", "layer": "0", "x": 60000.0, "y": 2500.0, "height": 250.0},
        {"handle": "T10", "text": "MAIN ENGINE : 2x550 HP", "layer": "0", "x": 60000.0, "y": 3000.0, "height": 250.0},
        {"handle": "T11", "text": "SHIP TYPE : DRY CARGO", "layer": "0", "x": 60000.0, "y": 3500.0, "height": 250.0},
        {"handle": "T12", "text": "TỶ LỆ : 1:100", "layer": "0", "x": 60000.0, "y": 4000.0, "height": 250.0},
        {"handle": "T13", "text": "A.P", "layer": "0", "x": 1000.0, "y": 0.0, "height": 300.0},
        {"handle": "T14", "text": "F.P", "layer": "0", "x": 53000.0, "y": 0.0, "height": 300.0},
    ]
    if not include_blanks:
        texts.extend(
            [
                {"handle": "T15", "text": "PORT OF REGISTRY : HAI PHONG", "layer": "0", "x": 60000.0, "y": 4500.0, "height": 250.0},
                {"handle": "T16", "text": "GROSS TONNAGE : 980 GT", "layer": "0", "x": 60000.0, "y": 5000.0, "height": 250.0},
            ]
        )
    else:
        texts.extend(
            [
                {"handle": "T15", "text": "PORT OF REGISTRY :", "layer": "0", "x": 60000.0, "y": 4500.0, "height": 250.0},
                {"handle": "T16", "text": "GROSS TONNAGE", "layer": "0", "x": 60000.0, "y": 5000.0, "height": 250.0},
            ]
        )
    return {
        "drawing_id": "GA_VRSB_52M",
        "drawing_code": "GA-01-01",
        "insunits": insunits,
        "measurement": 1,
        "claimed_scale": 100.0,
        "texts": texts,
        "structural_metrics": {
            "transverse_watertight_bulkhead_count": bulkheads,
            "double_bottom_height_mm": 750.0,
            "bottom_girder_max_spacing_mm": 2400.0,
        },
        "blank_fields": ["PORT OF REGISTRY", "GROSS TONNAGE"] if include_blanks else [],
    }


def _inland_midship_obs(*, double_bottom_height_mm: float = 750.0, min_plate_mm: float = 6.0):
    return {
        "drawing_id": "MCN_VRSB_52M",
        "drawing_code": "KC-02-01",
        "insunits": 4,
        "measurement": 1,
        "claimed_scale": 50.0,
        "texts": [
            {"handle": "M1", "text": "MẶT CẮT NGANG SƯỜN GIỮA", "layer": "TEXT", "x": 500.0, "y": 500.0, "height": 200.0},
            {"handle": "M2", "text": "ĐÁY ĐÔI - ĐÀ NGANG ĐẶC", "layer": "TEXT", "x": 1500.0, "y": 600.0, "height": 150.0},
            {"handle": "M3", "text": "Lpp = 52.00 m", "layer": "0", "x": 5000.0, "y": 500.0, "height": 150.0},
            {"handle": "M4", "text": "B = 9.60 m", "layer": "0", "x": 5000.0, "y": 750.0, "height": 150.0},
            {"handle": "M5", "text": "D = 4.20 m", "layer": "0", "x": 5000.0, "y": 1000.0, "height": 150.0},
            {"handle": "M6", "text": "CẤP TÀU : VR-SB", "layer": "0", "x": 5000.0, "y": 1250.0, "height": 150.0},
            {"handle": "M7", "text": "MAIN ENGINE : 2x550 HP", "layer": "0", "x": 5000.0, "y": 1500.0, "height": 150.0},
            {"handle": "M8", "text": "T65x50x6 s=8 L100x75x8", "layer": "KC", "x": 1500.0, "y": 1200.0, "height": 150.0},
        ],
        "structural_metrics": {
            "double_bottom_height_mm": double_bottom_height_mm,
            "bottom_girder_max_spacing_mm": 2200.0,
            "min_plate_thickness_mm": min_plate_mm,
        },
        "blank_fields": [],
    }


def test_skill1_classifier_detects_drawing_type_and_title_mismatch() -> None:
    from cad_agent.marine_knowledge.skills import classify_marine_drawing

    ga_res = classify_marine_drawing(_inland_vrsb_ga_obs())
    assert ga_res["status"] == "PASS"
    assert ga_res["observed_scope"]["predicted_drawing_type"] == "GENERAL_ARRANGEMENT"
    assert ga_res["cad_mutation"] is False
    assert ga_res["regulatory_compliance_proven"] is False

    # Contradiction: Lines Plan content carrying a GA title block (like Marine-7000 THLT7000)
    thlt_contaminated = {
        "drawing_id": "THLT_BAD_TITLE",
        "drawing_code": "SF 01 -05 GA- 01-01",
        "insunits": 4,
        "texts": [
            {"handle": "1", "text": "bè trÝ chung (phu¬ng ¸n III)", "layer": "CHU", "x": 100.0, "y": 100.0, "height": 300.0},
            {"handle": "2", "text": "§.ChuÈn", "layer": "0", "x": 10.0, "y": 0.0, "height": 250.0},
            {"handle": "3", "text": "ĐN 1 ĐN 2 ĐN 3", "layer": "0", "x": 10.0, "y": 500.0, "height": 250.0},
            {"handle": "4", "text": "CD1 CD2 CD3 C.DỌC", "layer": "0", "x": 10.0, "y": 1000.0, "height": 250.0},
            {"handle": "5", "text": "Sn1 Sn2 Sn10 A.P F.P", "layer": "0", "x": 10.0, "y": 1500.0, "height": 250.0},
            {"handle": "6", "text": "TUYẾN HÌNH - BODY PLAN - HALF BREADTH", "layer": "0", "x": 10.0, "y": 2000.0, "height": 250.0},
        ],
    }
    res_bad = classify_marine_drawing(thlt_contaminated)
    assert res_bad["status"] == "CONFLICT"
    assert res_bad["observed_scope"]["predicted_drawing_type"] == "LINES_PLAN"
    assert res_bad["observed_scope"]["title_declared_type"] == "GENERAL_ARRANGEMENT"
    assert any(f["verdict"] == "CONFLICT" for f in res_bad["findings"])


def test_skill2_submittal_and_regulation_pass_conflict_missing_and_out_of_scope() -> None:
    from cad_agent.marine_knowledge.skills import evaluate_regulation_applicability_and_submittal

    # 1. Valid inland VR-SB ship (GA + MCN) -> PASS (and never proves full statutory approval)
    res_ok = evaluate_regulation_applicability_and_submittal(
        [_inland_vrsb_ga_obs(bulkheads=4), _inland_midship_obs(double_bottom_height_mm=750.0)],
        partial_package=True,
    )
    assert res_ok["status"] == "PASS"
    assert res_ok["regulatory_compliance_proven"] is False
    assert res_ok["cad_mutation"] is False
    assert res_ok["partial_package"] is True
    assert res_ok["checks_not_executed"]  # stability/freeboard not supplied yet

    # 2. Violation: 40m < L=52m <= 60m requires >= 4 transverse bulkheads, given 3 -> CONFLICT
    res_bad_bh = evaluate_regulation_applicability_and_submittal(
        [_inland_vrsb_ga_obs(bulkheads=3), _inland_midship_obs(double_bottom_height_mm=550.0)],
        partial_package=True,
    )
    assert res_bad_bh["status"] == "CONFLICT"
    verdicts = {f["rule_id"]: f["verdict"] for f in res_bad_bh["findings"]}
    assert verdicts["RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT"] == "CONFLICT"
    assert verdicts["RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT"] == "CONFLICT"

    # 3. Missing data / partial package -> INSUFFICIENT_EVIDENCE (never false PASS, never fails unprovided docs)
    ga_no_scope = _inland_vrsb_ga_obs()
    ga_no_scope["texts"] = [t for t in ga_no_scope["texts"] if "VR-SB" not in t["text"]]
    res_missing = evaluate_regulation_applicability_and_submittal([ga_no_scope], partial_package=True)
    assert res_missing["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_missing["partial_package"] is True

    # 4. Out-of-scope: OCEAN GOING vessel evaluated against QCVN 72 -> NOT_APPLICABLE
    ocean_obs = {
        "drawing_id": "GA7000_OCEAN",
        "insunits": 0,
        "texts": [
            {"handle": "G1", "text": "GENERAL ARRANGEMENT CARGO SHIP 7000 MT", "layer": "0", "x": 100.0, "y": 100.0, "height": 250.0},
            {"handle": "G2", "text": "SERVICE AREA : OCEAN GOING", "layer": "0", "x": 100.0, "y": 200.0, "height": 250.0},
            {"handle": "G3", "text": "Lpp = 92.40 m B = 17.50 m", "layer": "0", "x": 100.0, "y": 300.0, "height": 250.0},
        ],
    }
    res_oos = evaluate_regulation_applicability_and_submittal([ocean_obs], partial_package=True)
    assert res_oos["status"] == "NOT_APPLICABLE"
    assert "QCVN 21:2015/BGTVT" in res_oos["summary"]


def test_skill3_gaps_conflicts_ocr_rejection_proposals_and_disable_mode() -> None:
    from cad_agent.marine_knowledge.skills import (
        build_marine_core_proposal,
        detect_drawing_gaps_and_conflicts,
    )

    # 1. Cross-drawing conflict + unitless + missing title fields + reversed bow + source conflict
    obs_a = _inland_vrsb_ga_obs(include_blanks=True)
    obs_b = _inland_midship_obs()
    obs_b["texts"][6]["text"] = "MAIN ENGINE : 1200 kW SINGLE"  # conflicts with 2x550 HP
    obs_b["texts"].append(
        {"handle": "C1", "text": "SERVICE AREA : OCEAN GOING", "layer": "0", "x": 5000.0, "y": 2000.0, "height": 150.0}
    )
    res_conf = detect_drawing_gaps_and_conflicts([obs_a, obs_b], partial_package=True)
    assert res_conf["status"] == "CONFLICT"
    reasons = " ".join(f["reason"] for f in res_conf["findings"])
    assert "MAIN ENGINE" in reasons or "service_area" in reasons.lower()
    assert res_conf["proposal_only_actions"]

    # 2. OCR-only inputs MUST NOT produce verified PASS geometry claim
    res_ocr = detect_drawing_gaps_and_conflicts(
        [_inland_vrsb_ga_obs()],
        ocr_only_inputs=True,
    )
    assert res_ocr["status"] == "INSUFFICIENT_EVIDENCE"

    # 3. Unitless insunits=0 without verified calibration fails closed with INSUFFICIENT_EVIDENCE
    obs_unitless = _inland_vrsb_ga_obs(insunits=0, include_blanks=False)
    res_unitless = detect_drawing_gaps_and_conflicts([obs_unitless], calibration_verified=False)
    assert res_unitless["status"] == "INSUFFICIENT_EVIDENCE"

    # 4. CAD Core proposal boundary never executes CAD mutation directly
    prop = build_marine_core_proposal(
        target_drawing_id="GA_VRSB_52M",
        action_kind="SET_INSUNITS_AND_COMPLETE_TITLE_BLOCK",
        evidence={"observed_insunits": 0, "missing_fields": ["PORT OF REGISTRY"]},
    )
    assert prop["cad_mutation"] is False
    assert prop["proposal_only"] is True
    assert "CAD_CORE_SOURCE_SUPPORT" in prop["required_core_gates"]

    # 5. Disabled Marine Pack preserves untouched baseline cleanly
    res_off = detect_drawing_gaps_and_conflicts([obs_a], enabled=False)
    assert res_off["status"] == "DISABLED"
    assert res_off["pack_status"] == "DISABLED"
    assert res_off["cad_mutation"] is False


def test_observe_dxf_bytes_reuses_snapshot_reader_without_importing_ezdxf() -> None:
    from cad_agent.marine_knowledge import classify_marine_drawing, observe_dxf_bytes

    minimal_dxf = "\n".join(
        [
            "0", "SECTION",
            "2", "HEADER",
            "9", "$ACADVER", "1", "AC1015",
            "9", "$INSUNITS", "70", "4",
            "9", "$MEASUREMENT", "70", "1",
            "0", "ENDSEC",
            "0", "SECTION",
            "2", "ENTITIES",
            "0", "TEXT", "8", "0", "10", "100.0", "20", "200.0", "30", "0.0", "40", "300.0", "1", "bè trÝ chung",
            "0", "TEXT", "8", "0", "10", "100.0", "20", "600.0", "30", "0.0", "40", "250.0", "1", "CARGO HOLD 1 - ENGINE ROOM - VACH CHONG VA",
            "0", "TEXT", "8", "0", "10", "100.0", "20", "900.0", "30", "0.0", "40", "250.0", "1", "Lpp = 52.00 m",
            "0", "ENDSEC",
            "0", "EOF",
            "",
        ]
    ).encode("latin-1")

    obs = observe_dxf_bytes(minimal_dxf, drawing_id="GA_DXF_SMOKE")
    assert obs["insunits"] == 4
    assert obs["measurement"] == 1
    assert obs["particulars"]["lpp_m_values"] == [52.0]
    assert any(t["text"] == "bố trí chung" for t in obs["texts"])
    cls = classify_marine_drawing(obs)
    assert cls["status"] == "PASS"
    assert cls["observed_scope"]["predicted_drawing_type"] == "GENERAL_ARRANGEMENT"
