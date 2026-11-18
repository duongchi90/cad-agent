from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path

import pytest

QCVN72_SHA256 = "4ffed2dad51f16d72bff5661a17be4d4793fe547133f999c41ded1ea72696b20"


def _make_dxf_bytes(
    *,
    insunits: int = 4,
    measurement: int = 1,
    entities: list[tuple[str, list[tuple[str, str]]]],
) -> bytes:
    lines: list[str] = [
        "0",
        "SECTION",
        "2",
        "HEADER",
        "9",
        "$ACADVER",
        "1",
        "AC1015",
        "9",
        "$INSUNITS",
        "70",
        str(insunits),
        "9",
        "$MEASUREMENT",
        "70",
        str(measurement),
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "ENTITIES",
    ]
    for etype, pairs in entities:
        lines.extend(["0", etype])
        for code, val in pairs:
            lines.extend([str(code), str(val)])
    lines.extend(["0", "ENDSEC", "0", "EOF", ""])
    return "\n".join(lines).encode("utf-8")


def _text_ent(
    handle: str,
    layer: str,
    x: float,
    y: float,
    text: str,
    height: float = 200.0,
) -> tuple[str, list[tuple[str, str]]]:
    return (
        "TEXT",
        [
            ("5", handle),
            ("8", layer),
            ("10", f"{x:.3f}"),
            ("20", f"{y:.3f}"),
            ("30", "0.0"),
            ("40", f"{height:.3f}"),
            ("1", text),
        ],
    )


def _line_ent(
    handle: str,
    layer: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> tuple[str, list[tuple[str, str]]]:
    return (
        "LINE",
        [
            ("5", handle),
            ("8", layer),
            ("10", f"{x1:.3f}"),
            ("20", f"{y1:.3f}"),
            ("30", "0.0"),
            ("11", f"{x2:.3f}"),
            ("21", f"{y2:.3f}"),
            ("31", "0.0"),
        ],
    )


def _dim_ent(
    handle: str,
    layer: str,
    actual_meas: float,
    text: str = "",
    *,
    x: float = 1200.0,
    y: float = 1200.0,
) -> tuple[str, list[tuple[str, str]]]:
    return (
        "DIMENSION",
        [
            ("5", handle),
            ("8", layer),
            ("10", f"{x:.3f}"),
            ("20", f"{y:.3f}"),
            ("30", "0.0"),
            ("11", f"{x:.3f}"),
            ("21", f"{y:.3f}"),
            ("31", "0.0"),
            ("70", "0"),
            ("1", text),
            ("42", f"{actual_meas:.6f}"),
        ],
    )


def _mcn_dxf_obs(
    drawing_id: str,
    *,
    extra_texts: list[tuple[str, float, float, str]],
    dims: list[tuple[str, str, float, str, float, float]] | None = None,
    insunits: int = 4,
    ocr_only: bool = False,
) -> dict:
    from cad_agent.marine_knowledge import observe_dxf_bytes

    entities: list[tuple[str, list[tuple[str, str]]]] = [
        _line_ent("101", "KC", 0.0, 0.0, 9600.0, 0.0),
        _text_ent("102", "TEXT", 100.0, 100.0, "MAT CAT NGANG SUON GIUA"),
        _text_ent("103", "KC", 100.0, 350.0, "TON DAY - TON MAN - DA NGANG DAC"),
    ]
    for handle, x, y, txt in extra_texts:
        entities.append(_text_ent(handle, "0-0", x, y, txt))
    for d_handle, d_layer, d_meas, d_txt, dx, dy in dims or []:
        entities.append(_dim_ent(d_handle, d_layer, d_meas, d_txt, x=dx, y=dy))
    raw = _make_dxf_bytes(insunits=insunits, entities=entities)
    return observe_dxf_bytes(raw, drawing_id=drawing_id, ocr_only=ocr_only)


def _ga_dxf_obs(
    drawing_id: str,
    *,
    extra_texts: list[tuple[str, float, float, str]],
    insunits: int = 4,
    ocr_only: bool = False,
) -> dict:
    from cad_agent.marine_knowledge import observe_dxf_bytes

    entities: list[tuple[str, list[tuple[str, str]]]] = [
        _line_ent("201", "HULL", 0.0, 0.0, 52000.0, 0.0),
        _text_ent("202", "TEXT", 100.0, 100.0, "BAN VE BO TRI CHUNG TOAN TAU"),
        _text_ent("203", "PV", 100.0, 350.0, "BUONG MAY - KHOANG HANG SO 1 - VACH CHONG VA"),
    ]
    for handle, x, y, txt in extra_texts:
        entities.append(_text_ent(handle, "0-0", x, y, txt))
    raw = _make_dxf_bytes(insunits=insunits, entities=entities)
    return observe_dxf_bytes(raw, drawing_id=drawing_id, ocr_only=ocr_only)


def test_v1c_compliant_double_bottom_via_native_bound_text_and_native_dimension() -> None:
    from cad_agent.marine_knowledge import evaluate_double_bottom_height_rule

    # 1. Compliant L <= 120 m (52 m -> min 700 mm) via native bound text (750 mm)
    obs_text = _mcn_dxf_obs(
        "MCN_52M_TEXT",
        extra_texts=[
            ("A01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("A02", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("A03", 100.0, 1200.0, "Chieu cao day doi tai CL = 750 mm"),
        ],
    )
    res_text = evaluate_double_bottom_height_rule(
        [obs_text],
        expected_source_sha256=QCVN72_SHA256,
    )
    assert res_text["skill_id"] == "SKILL_V1C_DOUBLE_BOTTOM_HEIGHT_RULE"
    assert res_text["status"] == "PASS"
    assert res_text["cad_mutation"] is False
    assert res_text["regulatory_compliance_proven"] is False
    assert res_text["proposal_only_actions"] == []

    finding = next(f for f in res_text["findings"] if f["finding_id"] == "F_DOUBLE_BOTTOM_HEIGHT_COMPLIANT")
    assert finding["verdict"] == "PASS"
    assert finding["rule_id"] == "RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT"
    assert finding["source_id"] == "QCVN_72_2025_BGTVT"
    assert finding["source_sha256"] == QCVN72_SHA256
    assert finding["pdf_page"] == [135]
    assert finding["reg_page"] == [151]
    bound_keys = {bf["fact_key"] for bf in finding["evidence"]["bound_facts"]}
    assert {"class_notation", "design_length_l_m", "double_bottom_height_mm"} <= bound_keys
    not_exec_blob = " | ".join(res_text["checks_not_executed"])
    assert "2.4.3-1" in not_exec_blob
    assert "2.4.3-3" in not_exec_blob
    assert "2.4.3-11" in not_exec_blob
    assert "stability" in not_exec_blob.lower()

    # 2. Compliant L <= 120 m via native DIMENSION spatially paired with centerline label
    obs_dim = _mcn_dxf_obs(
        "MCN_52M_DIM",
        extra_texts=[
            ("B01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("B02", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("B03", 1000.0, 1200.0, "CHIEU CAO DAY DOI CL"),
        ],
        dims=[
            ("DD1", "SUNPO", 750.0, "<>", 1450.0, 1200.0),
            # Unrelated breadth dimension far away (> 3000 CAD units) must NOT be misbound as DB height
            ("DD9", "SUNPO", 9600.0, "", 25000.0, 25000.0),
        ],
    )
    db_dim_facts = [f for f in obs_dim["engineering_facts"] if f["fact_key"] == "double_bottom_height_mm"]
    assert len(db_dim_facts) == 1
    assert db_dim_facts[0]["provenance_class"] == "NATIVE_MEASURED_GEOMETRY"
    assert db_dim_facts[0]["verification_state"] == "VERIFIED"
    assert db_dim_facts[0]["entity_handles"] == ["B03", "DD1"]
    assert db_dim_facts[0]["normalized_value"] == 750.0

    res_dim = evaluate_double_bottom_height_rule([obs_dim])
    assert res_dim["status"] == "PASS"
    dim_finding = next(f for f in res_dim["findings"] if f["finding_id"] == "F_DOUBLE_BOTTOM_HEIGHT_COMPLIANT")
    assert any(
        bf["fact_key"] == "double_bottom_height_mm"
        and bf["provenance_class"] == "NATIVE_MEASURED_GEOMETRY"
        and bf["entity_handles"] == ["B03", "DD1"]
        for bf in dim_finding["evidence"]["bound_facts"]
    )

    # 3. Compliant 120 < L <= 140 m (L = 128 m -> min 900 mm, observed 0.95 m = 950 mm)
    obs_128_ok = _mcn_dxf_obs(
        "MCN_128M_OK",
        extra_texts=[
            ("C01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("C02", 100.0, 900.0, "Chieu dai tau L = 128.00 m"),
            ("C03", 100.0, 1200.0, "Double bottom height (CL) = 0.95 m"),
        ],
    )
    res_128_ok = evaluate_double_bottom_height_rule([obs_128_ok])
    assert res_128_ok["status"] == "PASS"
    f_128 = next(f for f in res_128_ok["findings"] if f["finding_id"] == "F_DOUBLE_BOTTOM_HEIGHT_COMPLIANT")
    assert f_128["evidence"]["required_min_db_height_mm"] == 900.0
    assert f_128["evidence"]["observed_db_height_mm"] == 950.0


def test_v1c_negative_oracles_below_minimum_and_dimension_override_conflict() -> None:
    from cad_agent.marine_knowledge import evaluate_double_bottom_height_rule

    # 1. L = 52 m with 650 mm < 700 mm -> CONFLICT
    obs_low_52 = _mcn_dxf_obs(
        "MCN_52M_LOW",
        extra_texts=[
            ("A01", 100.0, 600.0, "CAP TAU : VR-SI"),
            ("A02", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("A03", 100.0, 1200.0, "Chieu cao day doi CL = 650 mm"),
        ],
    )
    res_low_52 = evaluate_double_bottom_height_rule([obs_low_52])
    assert res_low_52["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_DOUBLE_BOTTOM_HEIGHT_BELOW_MINIMUM" for f in res_low_52["findings"])
    assert any(p["action_kind"] == "REVIEW_DOUBLE_BOTTOM_SCANTLINGS" for p in res_low_52["proposal_only_actions"])

    # 2. L = 128 m with 800 mm < 900 mm -> CONFLICT
    obs_low_128 = _mcn_dxf_obs(
        "MCN_128M_LOW",
        extra_texts=[
            ("B01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("B02", 100.0, 900.0, "Chieu dai tau L = 128.00 m"),
            ("B03", 100.0, 1200.0, "h_dd (CL) = 800 mm"),
        ],
    )
    res_low_128 = evaluate_double_bottom_height_rule([obs_low_128])
    assert res_low_128["status"] == "CONFLICT"
    f_low_128 = next(f for f in res_low_128["findings"] if f["finding_id"] == "F_DOUBLE_BOTTOM_HEIGHT_BELOW_MINIMUM")
    assert f_low_128["evidence"]["required_min_db_height_mm"] == 900.0
    assert f_low_128["evidence"]["observed_db_height_mm"] == 800.0
    assert any(p["action_kind"] == "REVIEW_DOUBLE_BOTTOM_SCANTLINGS" for p in res_low_128["proposal_only_actions"])

    # 3. Native DIMENSION text override '800' vs actual_measurement = 620.0 mm -> CONFLICT
    obs_dim_override = _mcn_dxf_obs(
        "MCN_DIM_OVERRIDE",
        extra_texts=[
            ("C01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("C02", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("C03", 1000.0, 1200.0, "Double bottom height CL"),
        ],
        dims=[("DD2", "SUNPO", 620.0, "800", 1300.0, 1200.0)],
    )
    res_ov = evaluate_double_bottom_height_rule([obs_dim_override])
    assert res_ov["status"] == "CONFLICT"
    f_ov = next(f for f in res_ov["findings"] if f["finding_id"] == "F_DOUBLE_BOTTOM_DIMENSION_OVERRIDE_CONFLICT")
    assert f_ov["verdict"] == "CONFLICT"
    assert any(bf["verification_state"] == "CONFLICTING_OVERRIDE" for bf in f_ov["evidence"]["bound_facts"])

    # 4. Contradictory bound text (950 mm) vs calibrated native DIMENSION (750 mm) on same sheet -> CONFLICT (not false PASS!)
    obs_text_vs_dim = _mcn_dxf_obs(
        "MCN_TEXT_VS_DIM_CONFLICT",
        extra_texts=[
            ("D01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("D02", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("D03", 100.0, 1200.0, "Chieu cao day doi CL = 950 mm"),
        ],
        dims=[("DD3", "DB_CL", 750.0, "", 1300.0, 1200.0)],
    )
    res_tvd = evaluate_double_bottom_height_rule([obs_text_vs_dim])
    assert res_tvd["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_DOUBLE_BOTTOM_HEIGHT_CONFLICT" for f in res_tvd["findings"])


def test_v1c_rule_length_gates_missing_bare_lpp_straddle_and_length_conflict() -> None:
    from cad_agent.marine_knowledge import evaluate_double_bottom_height_rule

    # 1. Missing L and Lwl with 750 mm -> INSUFFICIENT_EVIDENCE
    obs_no_l = _mcn_dxf_obs(
        "MCN_NO_L",
        extra_texts=[
            ("A01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("A02", 100.0, 1200.0, "Chieu cao day doi CL = 750 mm"),
        ],
    )
    res_no_l = evaluate_double_bottom_height_rule([obs_no_l])
    assert res_no_l["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_MISSING_RULE_LENGTH_L" for f in res_no_l["findings"])

    # Missing L with 650 mm < 700 mm universal floor still catches CONFLICT
    obs_no_l_floor = _mcn_dxf_obs(
        "MCN_NO_L_FLOOR",
        extra_texts=[
            ("A11", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("A12", 100.0, 1200.0, "Chieu cao day doi CL = 650 mm"),
        ],
    )
    res_floor = evaluate_double_bottom_height_rule([obs_no_l_floor])
    assert res_floor["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_DOUBLE_BOTTOM_HEIGHT_BELOW_MINIMUM" for f in res_floor["findings"])

    # 2. Bare Lpp = 52.00 m without L or Lwl -> INSUFFICIENT_EVIDENCE
    obs_lpp_only = _mcn_dxf_obs(
        "MCN_LPP_ONLY",
        extra_texts=[
            ("B01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("B02", 100.0, 900.0, "Lpp = 52.00 m"),
            ("B03", 100.0, 1200.0, "Chieu cao day doi CL = 800 mm"),
        ],
    )
    res_lpp = evaluate_double_bottom_height_rule([obs_lpp_only])
    assert res_lpp["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_AMBIGUOUS_RULE_LENGTH_L" for f in res_lpp["findings"])

    # 3. Lwl = 122.0 m ([117.12, 122.0] straddling 120.0 m) with h_db = 800 mm -> INSUFFICIENT_EVIDENCE
    obs_straddle_120 = _mcn_dxf_obs(
        "MCN_STRADDLE_120",
        extra_texts=[
            ("C01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("C02", 100.0, 900.0, "Lwl = 122.00 m"),
            ("C03", 100.0, 1200.0, "Chieu cao day doi CL = 800 mm"),
        ],
    )
    res_s120 = evaluate_double_bottom_height_rule([obs_straddle_120])
    assert res_s120["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_RULE_LENGTH_STRADDLES_120M_THRESHOLD" for f in res_s120["findings"])

    # 4. Lwl = 142.0 m ([136.32, 142.0] straddling 140.0 m scope limit) -> INSUFFICIENT_EVIDENCE
    obs_straddle_140 = _mcn_dxf_obs(
        "MCN_STRADDLE_140",
        extra_texts=[
            ("D01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("D02", 100.0, 900.0, "Lwl = 142.00 m"),
            ("D03", 100.0, 1200.0, "Chieu cao day doi CL = 950 mm"),
        ],
    )
    res_s140 = evaluate_double_bottom_height_rule([obs_straddle_140])
    assert res_s140["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_RULE_LENGTH_STRADDLES_140M_SCOPE" for f in res_s140["findings"])

    # 5. Conflicting L declarations on same sheet -> CONFLICT
    obs_l_conflict = _mcn_dxf_obs(
        "MCN_L_CONFLICT",
        extra_texts=[
            ("E01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("E02", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("E03", 100.0, 1050.0, "Design length : 65.00 m"),
            ("E04", 100.0, 1200.0, "Chieu cao day doi CL = 800 mm"),
        ],
    )
    res_l_conf = evaluate_double_bottom_height_rule([obs_l_conflict])
    assert res_l_conf["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_RULE_LENGTH_CONFLICT" for f in res_l_conf["findings"])


def test_v1c_provenance_abstentions_ocr_unbound_side_margin_fixture_and_unitless() -> None:
    from cad_agent.marine_knowledge import evaluate_double_bottom_height_rule

    # 1. OCR_ONLY -> INSUFFICIENT_EVIDENCE (never PASS)
    obs_ocr = _mcn_dxf_obs(
        "MCN_OCR_ONLY",
        extra_texts=[
            ("A01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("A02", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("A03", 100.0, 1200.0, "Chieu cao day doi CL = 800 mm"),
        ],
        ocr_only=True,
    )
    res_ocr = evaluate_double_bottom_height_rule([obs_ocr])
    assert res_ocr["status"] == "INSUFFICIENT_EVIDENCE"

    # 2. Bare unbound 'h = 800 mm' without double-bottom context -> unbound_double_bottom_height_mm, INSUFFICIENT_EVIDENCE
    obs_unbound = _mcn_dxf_obs(
        "MCN_UNBOUND_H",
        extra_texts=[
            ("B01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("B02", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("B03", 100.0, 1200.0, "h = 800 mm"),
        ],
    )
    ub_facts = [f for f in obs_unbound["engineering_facts"] if f["fact_key"] == "unbound_double_bottom_height_mm"]
    assert len(ub_facts) == 1
    assert ub_facts[0]["provenance_class"] == "NATIVE_CAD_UNBOUND_TEXT"
    assert ub_facts[0]["verification_state"] == "UNVERIFIED_UNBOUND_TEXT"
    assert not any(f["fact_key"] == "double_bottom_height_mm" for f in obs_unbound["engineering_facts"])
    res_unbound = evaluate_double_bottom_height_rule([obs_unbound])
    assert res_unbound["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_UNVERIFIED_OR_UNBOUND_DOUBLE_BOTTOM_EVIDENCE" for f in res_unbound["findings"])

    # 3. Side/margin 'chieu cao day doi o man = 800 mm' -> non-centerline unbound, INSUFFICIENT_EVIDENCE
    obs_side = _mcn_dxf_obs(
        "MCN_SIDE_DB",
        extra_texts=[
            ("C01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("C02", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("C03", 100.0, 1200.0, "Chieu cao day doi o man = 800 mm"),
        ],
    )
    side_facts = [f for f in obs_side["engineering_facts"] if f["fact_key"] == "unbound_double_bottom_height_mm"]
    assert len(side_facts) == 1
    assert "2.4.3-2" in side_facts[0]["trust_reason"]
    res_side = evaluate_double_bottom_height_rule([obs_side])
    assert res_side["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_UNVERIFIED_OR_UNBOUND_DOUBLE_BOTTOM_EVIDENCE" for f in res_side["findings"])

    obs_margin = _mcn_dxf_obs(
        "MCN_MARGIN_DB",
        extra_texts=[
            ("C11", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("C12", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("C13", 100.0, 1200.0, "Margin plate height = 650 mm"),
        ],
    )
    assert evaluate_double_bottom_height_rule([obs_margin])["status"] == "INSUFFICIENT_EVIDENCE"

    # 4. FIXTURE_SUPPLIED dict without DXF bytes -> INSUFFICIENT_EVIDENCE when >= 700, CONFLICT when < 700
    fixture_800 = {
        "drawing_id": "MCN_FIXTURE_800",
        "insunits": 4,
        "texts": [
            {"handle": "T1", "text": "MAT CAT NGANG SUON GIUA"},
            {"handle": "T2", "text": "DAY DOI - TON DAY"},
            {"handle": "T3", "text": "CAP TAU : VR-SB"},
            {"handle": "T4", "text": "Chieu dai tau L = 52.00 m"},
        ],
        "structural_metrics": {"double_bottom_height_mm": 800.0},
    }
    res_fix_800 = evaluate_double_bottom_height_rule([fixture_800])
    assert res_fix_800["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_UNVERIFIED_OR_UNBOUND_DOUBLE_BOTTOM_EVIDENCE" for f in res_fix_800["findings"])

    fixture_650 = deepcopy(fixture_800)
    fixture_650["drawing_id"] = "MCN_FIXTURE_650"
    fixture_650["structural_metrics"] = {"double_bottom_height_mm": 650.0}
    res_fix_650 = evaluate_double_bottom_height_rule([fixture_650])
    assert res_fix_650["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_DOUBLE_BOTTOM_HEIGHT_BELOW_MINIMUM" for f in res_fix_650["findings"])

    # 5. $INSUNITS=0 uncalibrated -> INSUFFICIENT_EVIDENCE; calibrated DIMENSION -> PASS
    obs_unitless_text = _mcn_dxf_obs(
        "MCN_UNITLESS_TXT",
        insunits=0,
        extra_texts=[
            ("D01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("D02", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("D03", 100.0, 1200.0, "Chieu cao day doi CL = 800"),
        ],
    )
    res_ul_txt = evaluate_double_bottom_height_rule([obs_unitless_text])
    assert res_ul_txt["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_UNVERIFIED_OR_UNBOUND_DOUBLE_BOTTOM_EVIDENCE" for f in res_ul_txt["findings"])

    obs_unitless_dim = _mcn_dxf_obs(
        "MCN_UNITLESS_DIM",
        insunits=0,
        extra_texts=[
            ("E01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("E02", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("E03", 1000.0, 1200.0, "CHIEU CAO DAY DOI CL"),
        ],
        dims=[("DD5", "DB_CL", 800.0, "", 1300.0, 1200.0)],
    )
    assert evaluate_double_bottom_height_rule([obs_unitless_dim])["status"] == "INSUFFICIENT_EVIDENCE"
    res_cal_dim = evaluate_double_bottom_height_rule(
        [obs_unitless_dim],
        calibration_verified=True,
        verified_scale_to_mm=1.0,
    )
    assert res_cal_dim["status"] == "PASS"


def test_v1c_multi_sheet_comparability_gate_blocks_undeclared_rev_and_skew_and_allows_verified_pair() -> None:
    from cad_agent.marine_knowledge import evaluate_double_bottom_height_rule

    # 1. Matching HULL NO + explicit REV : 01 -> COMPARABLE_VERIFIED -> PASS (L/scope on GA + DB height on MCN)
    ga_rev01 = _ga_dxf_obs(
        "YN500_GA",
        extra_texts=[
            ("A01", 100.0, 600.0, "HULL NO : YN-500"),
            ("A02", 100.0, 800.0, "REV : 01"),
            ("A03", 100.0, 1000.0, "CAP TAU : VR-SB"),
            ("A04", 100.0, 1200.0, "Chieu dai tau L = 52.00 m"),
        ],
    )
    mcn_rev01 = _mcn_dxf_obs(
        "YN500_MCN",
        extra_texts=[
            ("B01", 100.0, 600.0, "HULL NO : YN-500"),
            ("B02", 100.0, 800.0, "REV : 01"),
            ("B03", 100.0, 1200.0, "Chieu cao day doi CL = 750 mm"),
        ],
    )
    res_pair_ok = evaluate_double_bottom_height_rule([ga_rev01, mcn_rev01])
    assert res_pair_ok["status"] == "PASS"
    assert res_pair_ok["observed_scope"]["comparability"]["comparable"] is True

    # 2. Missing REV on both sheets -> refuses cross-sheet pooling -> INSUFFICIENT_EVIDENCE
    ga_no_rev = _ga_dxf_obs(
        "YN500_GA_NOREV",
        extra_texts=[
            ("C01", 100.0, 600.0, "HULL NO : YN-500"),
            ("C02", 100.0, 1000.0, "CAP TAU : VR-SB"),
            ("C03", 100.0, 1200.0, "Chieu dai tau L = 52.00 m"),
        ],
    )
    mcn_no_rev = _mcn_dxf_obs(
        "YN500_MCN_NOREV",
        extra_texts=[
            ("D01", 100.0, 600.0, "HULL NO : YN-500"),
            ("D02", 100.0, 1200.0, "Chieu cao day doi CL = 750 mm"),
        ],
    )
    res_no_rev = evaluate_double_bottom_height_rule([ga_no_rev, mcn_no_rev])
    assert res_no_rev["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_PACKAGE_COMPARABILITY_UNVERIFIED_FOR_RULE" for f in res_no_rev["findings"])

    # 3. Different hull numbers or revision skew -> INSUFFICIENT_EVIDENCE
    mcn_other_hull = _mcn_dxf_obs(
        "YN999_MCN",
        extra_texts=[
            ("E01", 100.0, 600.0, "HULL NO : YN-999"),
            ("E02", 100.0, 800.0, "REV : 01"),
            ("E03", 100.0, 1200.0, "Chieu cao day doi CL = 750 mm"),
        ],
    )
    res_diff_hull = evaluate_double_bottom_height_rule([ga_rev01, mcn_other_hull])
    assert res_diff_hull["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_PACKAGE_COMPARABILITY_UNVERIFIED_FOR_RULE" for f in res_diff_hull["findings"])

    mcn_rev02 = _mcn_dxf_obs(
        "YN500_MCN_REV02",
        extra_texts=[
            ("F01", 100.0, 600.0, "HULL NO : YN-500"),
            ("F02", 100.0, 800.0, "REV : 02"),
            ("F03", 100.0, 1200.0, "Chieu cao day doi CL = 750 mm"),
        ],
    )
    res_rev_skew = evaluate_double_bottom_height_rule([ga_rev01, mcn_rev02])
    assert res_rev_skew["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_PACKAGE_COMPARABILITY_UNVERIFIED_FOR_RULE" for f in res_rev_skew["findings"])


def test_v1c_out_of_scope_and_single_bottom_not_applicable() -> None:
    from cad_agent.marine_knowledge import evaluate_double_bottom_height_rule

    # 1. Sea ship (*VRH / QCVN 21) -> NOT_APPLICABLE
    obs_vrh = _mcn_dxf_obs(
        "SEA_SHIP_MCN",
        extra_texts=[
            ("A01", 100.0, 600.0, "CLASS : *VRH (QCVN 21:2015/BGTVT)"),
            ("A02", 100.0, 900.0, "Chieu dai tau L = 92.40 m"),
        ],
    )
    res_vrh = evaluate_double_bottom_height_rule([obs_vrh])
    assert res_vrh["status"] == "NOT_APPLICABLE"
    assert any(f["finding_id"] == "F_SCOPE_OUT_OF_QCVN72" for f in res_vrh["findings"])

    # 2. FRP craft (QCVN 56) -> NOT_APPLICABLE
    obs_frp = _mcn_dxf_obs(
        "FRP_CRAFT_MCN",
        extra_texts=[
            ("B01", 100.0, 600.0, "VO TAU FRP - QCVN 56:2013/BGTVT"),
            ("B02", 100.0, 900.0, "Chieu dai tau L = 18.00 m"),
        ],
    )
    res_frp = evaluate_double_bottom_height_rule([obs_frp])
    assert res_frp["status"] == "NOT_APPLICABLE"
    assert any(f["finding_id"] == "F_SCOPE_SPECIAL_REGULATION_CLAUSE_1_1_2" for f in res_frp["findings"])

    # 3. Single-bottom inland ship ('tau day don') -> NOT_APPLICABLE
    obs_single = _mcn_dxf_obs(
        "SINGLE_BOTTOM_MCN",
        extra_texts=[
            ("C01", 100.0, 600.0, "CAP TAU : VR-SII"),
            ("C02", 100.0, 900.0, "Chieu dai tau L = 32.00 m"),
            ("C03", 100.0, 1200.0, "Ket cau tau day don"),
        ],
    )
    assert obs_single["particulars"]["single_bottom_evidences"]
    res_single = evaluate_double_bottom_height_rule([obs_single])
    assert res_single["status"] == "NOT_APPLICABLE"
    assert any(f["finding_id"] == "F_SINGLE_BOTTOM_EXEMPT" for f in res_single["findings"])

    # 4. L > 140 m (Clause 1.1.1 upper bound) and non-marine mechanical drawing -> NOT_APPLICABLE
    obs_gt_140 = _mcn_dxf_obs(
        "INLAND_GT_140M",
        extra_texts=[
            ("D01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("D02", 100.0, 900.0, "Chieu dai tau L = 145.00 m"),
            ("D03", 100.0, 1200.0, "Chieu cao day doi CL = 950 mm"),
        ],
    )
    res_gt_140 = evaluate_double_bottom_height_rule([obs_gt_140])
    assert res_gt_140["status"] == "NOT_APPLICABLE"
    assert any(f["finding_id"] == "F_SCOPE_OUT_OF_QCVN72" for f in res_gt_140["findings"])

    from cad_agent.marine_knowledge import observe_dxf_bytes

    mech_dxf = _make_dxf_bytes(
        insunits=4,
        entities=[
            _line_ent("E01", "0", 0.0, 0.0, 500.0, 0.0),
            _text_ent("E02", "0", 10.0, 10.0, "CHI TIET TRUC BAC - THEP C45"),
        ],
    )
    obs_mech = observe_dxf_bytes(mech_dxf, drawing_id="MECH_SHAFT_01")
    res_mech = evaluate_double_bottom_height_rule([obs_mech])
    assert res_mech["status"] == "NOT_APPLICABLE"
    assert any(f["finding_id"] == "F_NON_MARINE_DOMAIN" for f in res_mech["findings"])


def test_v1c_tampered_fact_hash_bad_args_and_disable_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    from cad_agent.marine_knowledge import (
        MarineKnowledgeError,
        evaluate_double_bottom_height_rule,
    )

    obs = _mcn_dxf_obs(
        "MCN_CLEAN",
        extra_texts=[
            ("A01", 100.0, 600.0, "CAP TAU : VR-SB"),
            ("A02", 100.0, 900.0, "Chieu dai tau L = 52.00 m"),
            ("A03", 100.0, 1200.0, "Chieu cao day doi CL = 750 mm"),
        ],
    )
    tampered = deepcopy(obs)
    tampered["engineering_facts"][0]["normalized_value"] = 999.0
    with pytest.raises(MarineKnowledgeError, match="FACT_HASH_MISMATCH"):
        evaluate_double_bottom_height_rule([tampered])

    # Splicing an untampered EngineeringFact from another drawing must also fail closed
    other_obs = _mcn_dxf_obs(
        "OTHER_MCN",
        extra_texts=[("B01", 100.0, 1200.0, "Chieu cao day doi CL = 950 mm")],
    )
    spliced = deepcopy(obs)
    spliced["engineering_facts"].append(deepcopy(other_obs["engineering_facts"][0]))
    with pytest.raises(MarineKnowledgeError, match="FACT_ENVELOPE_DRAWING_ID_MISMATCH"):
        evaluate_double_bottom_height_rule([spliced])

    with pytest.raises(MarineKnowledgeError, match="CALIBRATION_FLAG_INVALID"):
        evaluate_double_bottom_height_rule(
            [obs],
            calibration_verified="false",  # type: ignore[arg-type]
        )

    stale = evaluate_double_bottom_height_rule([obs], expected_source_sha256="0" * 64)
    assert stale["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_STALE_OR_MISMATCHED_SOURCE_SHA256" for f in stale["findings"])

    monkeypatch.setenv("CAD_AGENT_DISABLE_MARINE_PACK", "1")
    dis = evaluate_double_bottom_height_rule([obs])
    assert dis["status"] == "DISABLED"
    assert dis["cad_mutation"] is False


@pytest.mark.real_data
def test_v1c_real_marine_7000_dxf_v0_vs_v1c_abstention() -> None:
    from cad_agent.marine_knowledge import (
        evaluate_double_bottom_height_rule,
        evaluate_regulation_applicability_and_submittal,
        observe_dxf_file,
    )

    thlt_path = os.environ.get("CAD_AGENT_MARINE_THLT_DXF")
    ga_path = os.environ.get("CAD_AGENT_MARINE_GA_DXF")
    if not thlt_path or not ga_path:
        pytest.skip("set CAD_AGENT_MARINE_THLT_DXF and CAD_AGENT_MARINE_GA_DXF for real Marine V1-C DXF validation")

    thlt = observe_dxf_file(Path(thlt_path), drawing_id="THLT7000")
    ga = observe_dxf_file(Path(ga_path), drawing_id="GA7000")

    # General 'Đáy đôi' compartment text on GA7000 must NOT misbind unrelated GA dimensions
    assert not any(f["fact_key"] == "double_bottom_height_mm" for f in ga["engineering_facts"])

    v0_res = evaluate_regulation_applicability_and_submittal([thlt, ga], partial_package=True)
    v1c_res = evaluate_double_bottom_height_rule([thlt, ga], partial_package=True)

    assert v0_res["status"] == "INSUFFICIENT_EVIDENCE"
    assert v1c_res["status"] == "INSUFFICIENT_EVIDENCE"
    assert v1c_res["cad_mutation"] is False
    assert v1c_res["regulatory_compliance_proven"] is False

    v1c_fids = {f["finding_id"] for f in v1c_res["findings"]}
    # V1-C explicitly records comparability, scope, and missing structural sheet reasons without V0's false MAIN_ENGINES conflict
    assert "F_PACKAGE_COMPARABILITY_UNVERIFIED_FOR_RULE" in v1c_fids
    assert "F_SCOPE_UNVERIFIED" in v1c_fids
    assert "F_ELIGIBLE_STRUCTURAL_SHEET_MISSING" in v1c_fids
    assert not any("MAIN_ENGINE" in fid for fid in v1c_fids)
    assert v1c_res["observed_scope"]["eligible_structural_drawing_ids"] == []
    assert v1c_res["checks_not_executed"]
