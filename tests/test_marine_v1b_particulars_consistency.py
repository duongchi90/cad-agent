from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path

import pytest


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


def _text_ent(handle: str, layer: str, x: float, y: float, text: str, height: float = 250.0) -> tuple[str, list[tuple[str, str]]]:
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


def _line_ent(handle: str, layer: str, x1: float, y1: float, x2: float, y2: float) -> tuple[str, list[tuple[str, str]]]:
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


def _ship_sheet(
    drawing_id: str,
    *,
    title: str = "BAN VE BO TRI CHUNG TOAN TAU",
    extra_texts: list[tuple[str, str]],
    insunits: int = 4,
    ocr_only: bool = False,
) -> dict:
    from cad_agent.marine_knowledge import observe_dxf_bytes

    ents: list[tuple[str, list[tuple[str, str]]]] = [
        _line_ent("A01", "HULL", 0.0, 0.0, 52000.0, 0.0),
        _text_ent("A02", "TEXT", 100.0, 100.0, title),
        _text_ent("A03", "PV", 100.0, 400.0, "BUONG MAY - KHOANG HANG SO 1 - VACH CHONG VA"),
    ]
    for idx, (handle, txt) in enumerate(extra_texts, start=1):
        ents.append(_text_ent(handle, "0-0", 100.0, float(600 + idx * 300), txt))
    raw = _make_dxf_bytes(insunits=insunits, entities=ents)
    return observe_dxf_bytes(raw, drawing_id=drawing_id, ocr_only=ocr_only)


def test_v1b_comparability_gate_blocks_different_vessel_revision_skew_and_unverified_identity() -> None:
    from cad_agent.marine_knowledge import evaluate_particulars_consistency

    s1 = _ship_sheet(
        "SHIP_A_GA",
        extra_texts=[
            ("B01", "HULL NO : YN-101"),
            ("B02", "REV : A"),
            ("B03", "Lpp = 52.00 m"),
            ("B04", "B = 9.60 m"),
        ],
    )
    # 1. Single sheet cannot prove cross-drawing consistency
    res_single = evaluate_particulars_consistency([s1])
    assert res_single["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_SINGLE_DRAWING_NOT_CROSS_CHECKABLE" for f in res_single["findings"])

    # 2. Different hull numbers -> DIFFERENT_VESSEL, must NOT emit false Lpp conflict
    s2_other_ship = _ship_sheet(
        "SHIP_B_MCN",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[
            ("C01", "HULL NO : YN-202"),
            ("C02", "REV : A"),
            ("C03", "Lpp = 88.00 m"),
            ("C04", "B = 16.00 m"),
        ],
    )
    res_diff_ship = evaluate_particulars_consistency([s1, s2_other_ship])
    assert res_diff_ship["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_diff_ship["observed_scope"]["comparability"]["status"] == "DIFFERENT_VESSEL"
    fids_diff = {f["finding_id"] for f in res_diff_ship["findings"]}
    assert "F_NOT_COMPARABLE_DIFFERENT_VESSEL" in fids_diff
    assert not any("PARTICULAR_CONFLICT" in fid for fid in fids_diff)

    # 3. Same hull, different explicit revision (REV A vs REV B) -> DIFFERENT_REVISION, not same-rev CONFLICT
    s1_rev_b = _ship_sheet(
        "SHIP_A_MCN_REVB",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[
            ("D01", "HULL NO : YN-101"),
            ("D02", "REV : B"),
            ("D03", "Lpp = 52.00 m"),
            ("D04", "B = 9.80 m"),
        ],
    )
    res_rev_skew = evaluate_particulars_consistency([s1, s1_rev_b])
    assert res_rev_skew["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_rev_skew["observed_scope"]["comparability"]["status"] == "DIFFERENT_REVISION"
    assert any(f["finding_id"] == "F_REVISION_SKEW_NOT_COMPARABLE" for f in res_rev_skew["findings"])

    # 4. No hull_no and no shared project code -> UNVERIFIED_SAME_VESSEL
    u1 = _ship_sheet("UNREL_1", extra_texts=[("E01", "Lpp = 52.00 m"), ("E02", "B = 9.60 m")])
    u2 = _ship_sheet("UNREL_2", extra_texts=[("F01", "Lpp = 52.00 m"), ("F02", "B = 9.60 m")])
    res_unrel = evaluate_particulars_consistency([u1, u2])
    assert res_unrel["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_unrel["observed_scope"]["comparability"]["status"] == "UNVERIFIED_SAME_VESSEL"


def test_v1b_disambiguates_units_length_concepts_missing_fields_approx_and_catches_true_conflicts() -> None:
    from cad_agent.marine_knowledge import evaluate_particulars_consistency

    ga = _ship_sheet(
        "YN300_GA",
        extra_texts=[
            ("B01", "HULL NO : YN-300"),
            ("B02", "REV : 01"),
            ("B03", "Loa = 56.20 m"),
            ("B04", "Chieu dai tau L = 53.50 m"),
            ("B05", "B = 9.60 m"),
            ("B06", "D = 4.20 m"),
            ("B07", "T = 3.10 m"),
            ("B08", "CAP TAU : VR-SB"),
            ("B09", "SHIP TYPE : DRY CARGO"),
            ("B10", "MAIN ENGINE : 2 x 400 kW"),
        ],
    )
    mcn = _ship_sheet(
        "YN300_MCN",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[
            ("C01", "HULL NO : YN-300"),
            ("C02", "REV : 01"),
            # Distinct concept Lpp (52.00 m <= Loa 56.20 m) + mm/cm unit differences + missing T
            ("C03", "Lpp = 52000 mm"),
            ("C04", "B = 9600 mm"),
            ("C05", "D = 420 cm"),
            ("C06", "CAP TAU : VR-SB"),
            ("C07", "SHIP TYPE : DRY CARGO"),
            ("C08", "MAIN ENGINE : 2x400 kW"),
        ],
    )
    res_ok = evaluate_particulars_consistency([ga, mcn])
    assert res_ok["status"] == "PASS"
    matrix = res_ok["observed_scope"]["consistency_matrix"]
    assert matrix["breadth_m"]["status"] == "CONSISTENT"
    assert matrix["depth_m"]["status"] == "CONSISTENT"
    assert matrix["length_group"]["status"] == "COMPATIBLE_CONCEPTS"
    assert matrix["draft_m"]["status"] == "SINGLE_SHEET_OBSERVED"

    # Physical violation across concepts: Lpp (58.0 m) > Loa (56.2 m) MUST trigger CONFLICT
    mcn_bad_lpp = _ship_sheet(
        "YN300_MCN_BAD_LPP",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[
            ("C01", "HULL NO : YN-300"),
            ("C02", "REV : 01"),
            ("C03", "Lpp = 58.00 m"),
            ("C04", "B = 9.60 m"),
        ],
    )
    res_bad_order = evaluate_particulars_consistency([ga, mcn_bad_lpp])
    assert res_bad_order["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_LENGTH_CONCEPT_ORDER_CONFLICT" for f in res_bad_order["findings"])

    # Clause 1.4.43-1 violation: L (55.0 m) > Lwl (53.0 m) MUST trigger CONFLICT
    s_lwl = _ship_sheet(
        "YN300_THLT",
        title="TUYEN HINH LY THUYET - BODY PLAN",
        extra_texts=[
            ("E01", "HULL NO : YN-300"),
            ("E02", "REV : 01"),
            ("E03", "Lwl = 53.00 m"),
            ("E04", "B = 9.60 m"),
        ],
    )
    s_l_gt_lwl = _ship_sheet(
        "YN300_GA_BAD_L",
        extra_texts=[
            ("F01", "HULL NO : YN-300"),
            ("F02", "REV : 01"),
            ("F03", "Chieu dai tau L = 55.00 m"),
            ("F04", "B = 9.60 m"),
        ],
    )
    res_lwl_conflict = evaluate_particulars_consistency([s_lwl, s_l_gt_lwl])
    assert res_lwl_conflict["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_LENGTH_CONCEPT_ORDER_CONFLICT" for f in res_lwl_conflict["findings"])

    # True Breadth conflict on comparable sheets surfaces bound entity handles from both sheets
    mcn_bad_b = _ship_sheet(
        "YN300_MCN_BAD_B",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[
            ("D01", "HULL NO : YN-300"),
            ("D02", "REV : 01"),
            ("D03", "B = 10.20 m"),
        ],
    )
    res_b_conf = evaluate_particulars_consistency([ga, mcn_bad_b])
    assert res_b_conf["status"] == "CONFLICT"
    b_finding = next(f for f in res_b_conf["findings"] if f["finding_id"] == "F_PARTICULAR_CONFLICT_BREADTH_M")
    handles = {h for bf in b_finding["evidence"]["bound_facts"] for h in bf["entity_handles"]}
    assert {"B05", "D03"} <= handles


def test_v1b_main_engine_structured_schema_disambiguation_adversarial_and_disable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cad_agent.marine_knowledge import (
        MarineKnowledgeError,
        evaluate_particulars_consistency,
        parse_structured_main_engine,
    )

    p_model = parse_structured_main_engine("6 S35MC")
    p_power = parse_structured_main_engine("4040 kW (5500 cv)")
    assert p_model["model_code"] == "6S35MC"
    assert p_model["power_kw"] is None
    assert p_power["model_code"] is None
    assert p_power["power_kw"] == pytest.approx(4040.0)

    # 1. Model-only vs Power-only on comparable same-revision sheets -> AMBIGUOUS_SCHEMA (INSUFFICIENT_EVIDENCE)
    e_model = _ship_sheet(
        "ENG_MODEL",
        extra_texts=[
            ("B00", "REV : 01"),
            ("B01", "HULL NO : YN-700"),
            ("B02", "B = 17.50 m"),
            ("B03", "MAIN ENGINE : 6 S35MC"),
        ],
    )
    e_power = _ship_sheet(
        "ENG_POWER",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[
            ("C00", "REV : 01"),
            ("C01", "HULL NO : YN-700"),
            ("C02", "B = 17.50 m"),
            ("C03", "MAIN ENGINE : 4040 kW (5500 cv)"),
        ],
    )
    res_ambig_eng = evaluate_particulars_consistency([e_model, e_power])
    assert res_ambig_eng["observed_scope"]["comparability"]["status"] == "COMPARABLE_VERIFIED"
    assert res_ambig_eng["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_ambig_eng["observed_scope"]["consistency_matrix"]["main_engine"]["status"] == "AMBIGUOUS_SCHEMA"
    assert any(f["finding_id"] == "F_MAIN_ENGINE_SCHEMA_AMBIGUOUS" for f in res_ambig_eng["findings"])

    # 2. True same-revision engine power conflict (4040 kW vs 1200 kW) -> CONFLICT
    e_power_bad = _ship_sheet(
        "ENG_POWER_BAD",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[
            ("D00", "REV : 01"),
            ("D01", "HULL NO : YN-700"),
            ("D02", "B = 17.50 m"),
            ("D03", "MAIN ENGINE : 1200 kW"),
        ],
    )
    res_eng_conf = evaluate_particulars_consistency([e_power, e_power_bad])
    assert res_eng_conf["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_PARTICULAR_CONFLICT_MAIN_ENGINE" for f in res_eng_conf["findings"])

    # 2b. Undeclared-revision engine power difference -> advisory INSUFFICIENT_EVIDENCE (not hard CONFLICT)
    e_power_unrev = _ship_sheet(
        "ENG_POWER_UNREV",
        extra_texts=[
            ("C11", "HULL NO : YN-700"),
            ("C12", "B = 17.50 m"),
            ("C13", "MAIN ENGINE : 4040 kW (5500 cv)"),
        ],
    )
    e_power_bad_unrev = _ship_sheet(
        "ENG_POWER_BAD_UNREV",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[
            ("D11", "HULL NO : YN-700"),
            ("D12", "B = 17.50 m"),
            ("D13", "MAIN ENGINE : 1200 kW"),
        ],
    )
    res_eng_unrev = evaluate_particulars_consistency([e_power_unrev, e_power_bad_unrev])
    assert (
        res_eng_unrev["observed_scope"]["comparability"]["status"],
        res_eng_unrev["status"],
    ) == ("UNVERIFIED_REVISION_OR_CONFIGURATION", "INSUFFICIENT_EVIDENCE")
    assert res_eng_unrev["observed_scope"]["consistency_matrix"]["main_engine"]["status"] == "ADVISORY_DIFFERENCE"
    eng_adv_f = next(f for f in res_eng_unrev["findings"] if f["finding_id"] == "F_ADVISORY_DIFFERENCE_MAIN_ENGINE")
    assert eng_adv_f["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert eng_adv_f["evidence"]["advisory_only"] is True
    assert not any(f["finding_id"] == "F_PARTICULAR_CONFLICT_MAIN_ENGINE" for f in res_eng_unrev["findings"])
    assert res_eng_unrev["proposal_only_actions"] == []

    # 3. OCR-only companion sheet never creates false CONFLICT and blocks PASS
    ocr_sheet = _ship_sheet(
        "ENG_OCR",
        extra_texts=[("E01", "HULL NO : YN-700"), ("E02", "B = 99.00 m")],
        ocr_only=True,
    )
    res_ocr = evaluate_particulars_consistency([e_model, ocr_sheet])
    assert res_ocr["status"] == "INSUFFICIENT_EVIDENCE"
    assert not any("PARTICULAR_CONFLICT_BREADTH" in f["finding_id"] for f in res_ocr["findings"])

    # 4. Tampered fact inside pre-normalized observation fails closed
    tampered = deepcopy(e_model)
    tampered["engineering_facts"][0]["observed_raw"] = "forged"
    with pytest.raises(MarineKnowledgeError, match="FACT_HASH_MISMATCH"):
        evaluate_particulars_consistency([tampered, e_power])

    # 5. Disable toggle
    monkeypatch.setenv("CAD_AGENT_DISABLE_MARINE_PACK", "1")
    dis = evaluate_particulars_consistency([e_model, e_power])
    assert dis["status"] == "DISABLED"
    assert dis["cad_mutation"] is False


@pytest.mark.real_data
def test_v1b_real_marine_7000_dxf_consistency_report() -> None:
    from cad_agent.marine_knowledge import evaluate_particulars_consistency, observe_dxf_file

    thlt_path = os.environ.get("CAD_AGENT_MARINE_THLT_DXF")
    ga_path = os.environ.get("CAD_AGENT_MARINE_GA_DXF")
    if not thlt_path or not ga_path:
        pytest.skip("set CAD_AGENT_MARINE_THLT_DXF and CAD_AGENT_MARINE_GA_DXF for real Marine V1-B validation")

    thlt = observe_dxf_file(Path(thlt_path), drawing_id="THLT7000")
    ga = observe_dxf_file(Path(ga_path), drawing_id="GA7000")

    res = evaluate_particulars_consistency([thlt, ga])
    comp = res["observed_scope"]["comparability"]
    assert (comp["status"], res["status"]) == (
        "UNVERIFIED_REVISION_OR_CONFIGURATION",
        "INSUFFICIENT_EVIDENCE",
    )
    assert comp["comparable"] is False
    assert comp["advisory_comparison_allowed"] is True
    assert comp["same_revision_proven"] is False
    assert comp["same_configuration_proven"] is False
    assert set(comp["configuration_drift_signals"]) == {
        "UNDECLARED_REVISIONS",
        "DESIGN_VARIANT_DIVERGENCE",
        "ISSUE_DATE_SPREAD",
        "VESSEL_DESCRIPTION_DIVERGENCE",
    }

    matrix = res["observed_scope"]["consistency_matrix"]
    # Principal dimensions match across both real drawings, recorded as unverified-comparability matches (never false PASS)
    assert matrix["lpp_m"]["status"] == "OBSERVED_MATCH_UNVERIFIED_COMPARABILITY"
    assert matrix["breadth_m"]["status"] == "OBSERVED_MATCH_UNVERIFIED_COMPARABILITY"
    assert matrix["depth_m"]["status"] == "OBSERVED_MATCH_UNVERIFIED_COMPARABILITY"
    assert matrix["draft_m"]["status"] == "OBSERVED_MATCH_UNVERIFIED_COMPARABILITY"
    assert matrix["length_group"]["status"] == "OBSERVED_MATCH_UNVERIFIED_COMPARABILITY"
    assert matrix["service_and_class"]["status"] == "OBSERVED_MATCH_UNVERIFIED_COMPARABILITY"
    # Engine model ('6 S35MC') vs power ('4040 kW (5500 cv)') disambiguated as schema mismatch
    assert matrix["main_engine"]["status"] == "AMBIGUOUS_SCHEMA"
    # Ship-type / design-option divergence ('TAU HANG - KHACH' PHUONG AN III 1/2005 vs 'TAU HANG - THUC TAP' 12/2005)
    # is preserved as an advisory INSUFFICIENT_EVIDENCE finding rather than a false same-revision hard CONFLICT!
    assert matrix["ship_type"]["status"] == "ADVISORY_DIFFERENCE"
    assert res["observed_scope"]["consistent_groups"] == []
    assert res["status"] == "INSUFFICIENT_EVIDENCE"
    assert res["proposal_only_actions"] == []

    fids = {f["finding_id"] for f in res["findings"]}
    assert "F_COMPARABILITY_UNVERIFIED_REVISION_OR_CONFIG" in fids
    assert "F_ADVISORY_DIFFERENCE_SHIP_TYPE" in fids
    assert "F_MAIN_ENGINE_SCHEMA_AMBIGUOUS" in fids
    assert "F_PARTICULAR_CONFLICT_SHIP_TYPE" not in fids
    assert all(f["verdict"] != "CONFLICT" for f in res["findings"])

    ship_finding = next(f for f in res["findings"] if f["finding_id"] == "F_ADVISORY_DIFFERENCE_SHIP_TYPE")
    assert ship_finding["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert ship_finding["evidence"]["advisory_only"] is True
    assert {bf["drawing_id"] for bf in ship_finding["evidence"]["bound_facts"]} == {"THLT7000", "GA7000"}
    assert all(bf["entity_handles"] for bf in ship_finding["evidence"]["bound_facts"])


def test_v1b_adversarial_envelope_splicing_single_sheet_lengths_partial_revision_and_unitless_exclusion() -> None:
    from cad_agent.marine_knowledge import MarineKnowledgeError, evaluate_particulars_consistency

    # 1. Single sheet having two length concepts (Loa + Lpp) while sheet 2 has ZERO particulars MUST NOT false-PASS!
    s_two_lens = _ship_sheet(
        "YN900_GA",
        extra_texts=[
            ("B00", "REV : 01"),
            ("B01", "HULL NO : YN-900"),
            ("B02", "Loa = 56.20 m"),
            ("B03", "Lpp = 52.00 m"),
        ],
    )
    s_empty_companion = _ship_sheet(
        "YN900_MCN",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[("C00", "REV : 01"), ("C01", "HULL NO : YN-900")],
    )
    res_no_overlap = evaluate_particulars_consistency([s_two_lens, s_empty_companion])
    assert res_no_overlap["observed_scope"]["comparability"]["status"] == "COMPARABLE_VERIFIED"
    assert res_no_overlap["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_no_overlap["observed_scope"]["consistency_matrix"]["length_group"]["status"] == "SINGLE_SHEET_OBSERVED"
    assert any(f["finding_id"] == "F_NO_OVERLAPPING_PARTICULARS" for f in res_no_overlap["findings"])

    # 2. Partial revision skew (REV A on sheet 1 vs undeclared revision on sheet 2) -> DIFFERENT_REVISION
    s_rev_a = _ship_sheet(
        "YN901_GA",
        extra_texts=[("B01", "HULL NO : YN-901"), ("B02", "REV : A"), ("B03", "B = 9.60 m")],
    )
    s_rev_none = _ship_sheet(
        "YN901_MCN",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[("C01", "HULL NO : YN-901"), ("C02", "B = 9.60 m")],
    )
    res_partial_rev = evaluate_particulars_consistency([s_rev_a, s_rev_none])
    assert res_partial_rev["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_partial_rev["observed_scope"]["comparability"]["status"] == "DIFFERENT_REVISION"

    # 3. Envelope splicing / revision-header tampering on pre-normalized observation fails closed
    forged_rev = deepcopy(s_rev_a)
    forged_rev["drawing_evidence"]["revision"] = None
    with pytest.raises(MarineKnowledgeError, match="FACT_ENVELOPE_REVISION_MISMATCH"):
        evaluate_particulars_consistency([forged_rev, s_rev_none])

    spliced = deepcopy(s_rev_none)
    spliced["engineering_facts"].append(deepcopy(s_two_lens["engineering_facts"][0]))
    with pytest.raises(MarineKnowledgeError, match="FACT_ENVELOPE_DRAWING_ID_MISMATCH"):
        evaluate_particulars_consistency([spliced, s_rev_none])

    # 4. Unitless ($INSUNITS=0) companion value 'B = 9600' (no 'mm'/'m') does NOT raise false 9.6m vs 9600m CONFLICT,
    #    and blocks false PASS with F_UNITLESS_PARTICULAR_UNVERIFIED
    s_metric = _ship_sheet(
        "YN902_GA",
        extra_texts=[("B00", "REV : 01"), ("B01", "HULL NO : YN-902"), ("B02", "B = 9.60 m")],
        insunits=4,
    )
    s_unitless = _ship_sheet(
        "YN902_MCN",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[("C00", "REV : 01"), ("C01", "HULL NO : YN-902"), ("C02", "B = 9600")],
        insunits=0,
    )
    res_unitless = evaluate_particulars_consistency([s_metric, s_unitless])
    assert res_unitless["observed_scope"]["comparability"]["status"] == "COMPARABLE_VERIFIED"
    assert res_unitless["status"] == "INSUFFICIENT_EVIDENCE"
    assert not any("PARTICULAR_CONFLICT_BREADTH" in f["finding_id"] for f in res_unitless["findings"])
    assert any(f["finding_id"] == "F_UNITLESS_PARTICULAR_UNVERIFIED_YN902_MCN" for f in res_unitless["findings"])


def test_v1b_targeted_falsification_undeclared_revision_variant_and_date_spread() -> None:
    from cad_agent.marine_knowledge import (
        evaluate_particulars_consistency,
        normalize_observation,
        verify_package_comparability,
    )

    # 1. Undeclared revisions (revision=None on all sheets) with matching particulars
    #    MUST NOT false-PASS -> UNVERIFIED_REVISION_OR_CONFIGURATION + INSUFFICIENT_EVIDENCE
    unrev_1 = _ship_sheet(
        "YN802_GA",
        extra_texts=[("B01", "HULL NO : YN-802"), ("B02", "Lpp = 52.00 m"), ("B03", "B = 9.60 m")],
    )
    unrev_2 = _ship_sheet(
        "YN802_MCN",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[("C01", "HULL NO : YN-802"), ("C02", "Lpp = 52.00 m"), ("C03", "B = 9.60 m")],
    )
    res_unrev_match = evaluate_particulars_consistency([unrev_1, unrev_2])
    comp_unrev = res_unrev_match["observed_scope"]["comparability"]
    assert (comp_unrev["status"], res_unrev_match["status"]) == (
        "UNVERIFIED_REVISION_OR_CONFIGURATION",
        "INSUFFICIENT_EVIDENCE",
    )
    assert comp_unrev["comparable"] is False
    assert comp_unrev["advisory_comparison_allowed"] is True
    assert comp_unrev["same_revision_proven"] is False
    assert comp_unrev["same_configuration_proven"] is True
    assert "UNDECLARED_REVISIONS" in comp_unrev["configuration_drift_signals"]
    assert res_unrev_match["observed_scope"]["consistent_groups"] == []
    mat_unrev = res_unrev_match["observed_scope"]["consistency_matrix"]
    assert mat_unrev["breadth_m"]["status"] == "OBSERVED_MATCH_UNVERIFIED_COMPARABILITY"
    assert mat_unrev["lpp_m"]["status"] == "OBSERVED_MATCH_UNVERIFIED_COMPARABILITY"
    assert mat_unrev["length_group"]["status"] == "OBSERVED_MATCH_UNVERIFIED_COMPARABILITY"

    # 2. Explicit matching revision (REV : 01) + compatible variants + DIFFERENT issue dates (1/2005 vs 12/2005)
    #    MUST NOT assume different issue dates prove different revisions -> COMPARABLE_VERIFIED!
    d_early = _ship_sheet(
        "YN801_GA",
        extra_texts=[
            ("B01", "HULL NO : YN-801"),
            ("B02", "REV : 01"),
            ("B03", "1/2005"),
            ("B04", "PHUONG AN III"),
            ("B05", "Lpp = 92.40 m"),
            ("B06", "B = 17.50 m"),
        ],
    )
    d_late = _ship_sheet(
        "YN801_MCN",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[
            ("C01", "HULL NO : YN-801"),
            ("C02", "REV : 01"),
            ("C03", "12/2005"),
            ("C04", "PHUONG AN III"),
            ("C05", "Lpp = 92.40 m"),
            ("C06", "B = 17.50 m"),
        ],
    )
    comp_dates = verify_package_comparability([d_early, d_late])
    assert comp_dates["status"] == "COMPARABLE_VERIFIED"
    assert comp_dates["comparable"] is True
    assert comp_dates["same_revision_proven"] is True
    assert comp_dates["same_configuration_proven"] is True
    assert "ISSUE_DATE_SPREAD" in comp_dates["configuration_drift_signals"]
    res_dates_ok = evaluate_particulars_consistency([d_early, d_late])
    assert res_dates_ok["status"] == "PASS"

    # 3. Design variant skew (PHUONG AN I vs PHUONG AN III) even with matching REV : 01
    #    + cross-sheet differences -> UNVERIFIED_REVISION_OR_CONFIGURATION + advisory INSUFFICIENT_EVIDENCE
    var_a = _ship_sheet(
        "YN803_OPT1",
        extra_texts=[
            ("B01", "HULL NO : YN-803"),
            ("B02", "REV : 01"),
            ("B03", "PHUONG AN I"),
            ("B04", "Loa = 50.00 m"),
            ("B05", "B = 9.60 m"),
            ("B06", "D = 4.00 m"),
            ("B07", "CAP TAU : VR-SB"),
        ],
    )
    var_b = _ship_sheet(
        "YN803_OPT3",
        title="KET CAU CO BAN TAU",
        extra_texts=[
            ("C01", "HULL NO : YN-803"),
            ("C02", "REV : 01"),
            ("C03", "PHUONG AN III"),
            ("C04", "Lpp = 55.00 m"),
            ("C05", "B = 10.80 m"),
            ("C06", "T = 4.50 m"),
            ("C07", "CAP TAU : VR-SI"),
        ],
    )
    res_var_skew = evaluate_particulars_consistency([var_a, var_b])
    comp_var = res_var_skew["observed_scope"]["comparability"]
    assert comp_var["status"] == "UNVERIFIED_REVISION_OR_CONFIGURATION"
    assert comp_var["same_revision_proven"] is True
    assert comp_var["same_configuration_proven"] is False
    assert "DESIGN_VARIANT_DIVERGENCE" in comp_var["configuration_drift_signals"]
    assert res_var_skew["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_var_skew["proposal_only_actions"] == []
    var_fids = {f["finding_id"] for f in res_var_skew["findings"]}
    assert {
        "F_COMPARABILITY_UNVERIFIED_REVISION_OR_CONFIG",
        "F_ADVISORY_DIFFERENCE_BREADTH_M",
        "F_ADVISORY_DIFFERENCE_LENGTH_ORDER",
        "F_ADVISORY_DIFFERENCE_DRAFT_DEPTH",
        "F_ADVISORY_DIFFERENCE_SERVICE_CLASS",
    } <= var_fids
    assert all(f["verdict"] == "INSUFFICIENT_EVIDENCE" for f in res_var_skew["findings"])
    b_adv = next(f for f in res_var_skew["findings"] if f["finding_id"] == "F_ADVISORY_DIFFERENCE_BREADTH_M")
    assert b_adv["evidence"]["advisory_only"] is True
    assert {"B05", "C05"} <= {h for bf in b_adv["evidence"]["bound_facts"] for h in bf["entity_handles"]}

    # 3b. Bulkhead count advisory difference under undeclared revisions + project-code vessel description divergence
    bh_ga = normalize_observation(
        {
            "drawing_id": "SF02_GA",
            "drawing_code": "SF-02-05",
            "insunits": 4,
            "texts": [
                {"handle": "A10", "text": "BAN VE BO TRI CHUNG TOAN TAU"},
                {"handle": "A11", "text": "REV : 01"},
                {"handle": "A12", "text": "SHIP TYPE : CARGO"},
            ],
            "structural_metrics": {"transverse_watertight_bulkhead_count": 4},
        }
    )
    bh_kccb = normalize_observation(
        {
            "drawing_id": "SF02_KCCB",
            "drawing_code": "SF-02-05",
            "insunits": 4,
            "texts": [
                {"handle": "B10", "text": "KET CAU CO BAN TAU"},
                {"handle": "B11", "text": "REV : 01"},
                {"handle": "B12", "text": "SHIP TYPE : PASSENGER"},
            ],
            "structural_metrics": {"transverse_watertight_bulkhead_count": 6},
        }
    )
    res_proj_div = evaluate_particulars_consistency([bh_ga, bh_kccb])
    comp_proj = res_proj_div["observed_scope"]["comparability"]
    assert comp_proj["status"] == "UNVERIFIED_REVISION_OR_CONFIGURATION"
    assert "VESSEL_DESCRIPTION_DIVERGENCE" in comp_proj["configuration_drift_signals"]
    assert res_proj_div["status"] == "INSUFFICIENT_EVIDENCE"
    assert res_proj_div["proposal_only_actions"] == []
    proj_fids = {f["finding_id"] for f in res_proj_div["findings"]}
    assert "F_ADVISORY_DIFFERENCE_SHIP_TYPE" in proj_fids
    assert "F_ADVISORY_DIFFERENCE_BULKHEAD_COUNT" in proj_fids

    # Conversely, explicit shared hull_no + explicit matching REV : 01 + no variant skew + conflicting ship_type -> hard CONFLICT
    hull_st_1 = _ship_sheet(
        "YN804_GA",
        extra_texts=[("B01", "HULL NO : YN-804"), ("B02", "REV : 01"), ("B03", "SHIP TYPE : CARGO")],
    )
    hull_st_2 = _ship_sheet(
        "YN804_MCN",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[("C01", "HULL NO : YN-804"), ("C02", "REV : 01"), ("C03", "SHIP TYPE : TANKER")],
    )
    res_hull_st = evaluate_particulars_consistency([hull_st_1, hull_st_2])
    assert res_hull_st["observed_scope"]["comparability"]["status"] == "COMPARABLE_VERIFIED"
    assert res_hull_st["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_PARTICULAR_CONFLICT_SHIP_TYPE" for f in res_hull_st["findings"])

    # 4. Single-sheet internal contradiction (B=9.60m AND B=10.40m on the SAME sheet) STILL raises hard CONFLICT
    #    even when cross-sheet revision comparability is unverified!
    self_contra = _ship_sheet(
        "YN805_GA_SELF_BAD",
        extra_texts=[("B01", "HULL NO : YN-805"), ("B02", "B = 9.60 m"), ("B03", "B = 10.40 m")],
    )
    companion_unrev = _ship_sheet(
        "YN805_MCN",
        title="MAT CAT NGANG SUON GIUA",
        extra_texts=[("C01", "HULL NO : YN-805"), ("C02", "B = 9.60 m")],
    )
    res_intra = evaluate_particulars_consistency([self_contra, companion_unrev])
    assert res_intra["observed_scope"]["comparability"]["status"] == "UNVERIFIED_REVISION_OR_CONFIGURATION"
    assert res_intra["status"] == "CONFLICT"
    assert any(
        f["finding_id"] == "F_PARTICULAR_CONFLICT_BREADTH_M" and f["verdict"] == "CONFLICT"
        for f in res_intra["findings"]
    )
