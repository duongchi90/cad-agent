from __future__ import annotations

import hashlib
import json
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


def _dim_ent(handle: str, layer: str, actual_meas: float, text: str = "") -> tuple[str, list[tuple[str, str]]]:
    return (
        "DIMENSION",
        [
            ("5", handle),
            ("8", layer),
            ("10", "0.0"),
            ("20", "0.0"),
            ("30", "0.0"),
            ("11", "500.0"),
            ("21", "500.0"),
            ("31", "0.0"),
            ("70", "0"),
            ("1", text),
            ("42", f"{actual_meas:.6f}"),
        ],
    )


def test_v1a_engineering_fact_contract_enforces_6_provenance_classes_and_blocks_forged_verified() -> None:
    from cad_agent.marine_knowledge import (
        ENGINEERING_FACT_SCHEMA_VERSION,
        PROVENANCE_CLASSES,
        VERIFICATION_STATES,
        MarineKnowledgeError,
        build_engineering_fact,
        validate_engineering_fact,
    )

    assert ENGINEERING_FACT_SCHEMA_VERSION == "engineering-fact-1.0"
    assert PROVENANCE_CLASSES == frozenset(
        {
            "NATIVE_CAD_EVIDENCE",
            "NATIVE_CAD_UNBOUND_TEXT",
            "NATIVE_MEASURED_GEOMETRY",
            "OCR_ONLY",
            "FIXTURE_SUPPLIED",
            "INFERRED_UNVERIFIED",
        }
    )

    schema_path = (
        Path(__file__).resolve().parents[1]
        / "contracts"
        / "marine-knowledge"
        / "engineering-fact.schema.json"
    )
    assert schema_path.is_file()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert set(schema["properties"]["provenance_class"]["enum"]) == PROVENANCE_CLASSES
    assert set(schema["properties"]["verification_state"]["enum"]) == VERIFICATION_STATES

    valid_sha = "a" * 64
    # Cross-domain extensibility (e.g. mechanical or marine) without plugin framework
    mech_fact = build_engineering_fact(
        domain="mechanical",
        drawing_id="SHAFT_01",
        drawing_path=None,
        drawing_sha256=valid_sha,
        sheet_id=None,
        revision=None,
        fact_key="outer_diameter_mm",
        entity_handles=["E10"],
        entity_type="DIMENSION",
        layer="DIM",
        observed_raw="Ø50",
        observed_value=50.0,
        observed_unit="mm",
        normalized_value=50.0,
        normalized_unit="mm",
        provenance_class="NATIVE_MEASURED_GEOMETRY",
        verification_state="VERIFIED",
        trust_reason="Native calibrated DIMENSION entity E10 on layer DIM.",
    )
    validated = validate_engineering_fact(mech_fact)
    assert validated["domain"] == "mechanical"
    assert validated["verification_state"] == "VERIFIED"

    # Non-native / unbound / OCR / fixture / inferred classes MUST NEVER claim VERIFIED
    for forbidden_prov in (
        "OCR_ONLY",
        "NATIVE_CAD_UNBOUND_TEXT",
        "FIXTURE_SUPPLIED",
        "INFERRED_UNVERIFIED",
    ):
        forged = dict(validated)
        forged["provenance_class"] = forbidden_prov
        with pytest.raises(MarineKnowledgeError, match="FACT_VERIFICATION_PROVENANCE_FORBIDDEN"):
            validate_engineering_fact(forged)

    # Native VERIFIED without drawing_sha256 or without handles MUST fail closed
    no_sha = dict(validated)
    no_sha["drawing_sha256"] = None
    with pytest.raises(MarineKnowledgeError, match="FACT_NATIVE_BINDING_MISSING"):
        validate_engineering_fact(no_sha)

    no_handles = dict(validated)
    no_handles["entity_handles"] = []
    with pytest.raises(MarineKnowledgeError, match="FACT_NATIVE_BINDING_MISSING"):
        validate_engineering_fact(no_handles)

    # Hash tamper MUST fail closed
    tampered = dict(validated)
    tampered["normalized_value"] = 999.0
    with pytest.raises(MarineKnowledgeError, match="FACT_HASH_MISMATCH"):
        validate_engineering_fact(tampered)


def test_v1a_dxf_table_pairing_non_fabricated_revision_and_bound_file_custody(tmp_path: Path) -> None:
    from cad_agent.file_integrity import FileIdentityError
    from cad_agent.marine_knowledge import observe_dxf_bytes, observe_dxf_file

    dxf_bytes = _make_dxf_bytes(
        insunits=0,
        measurement=0,
        entities=[
            _line_ent("A01", "HULL", 0.0, 0.0, 92400.0, 0.0),
            _text_ent("2C658", "0-0", 140371.4, -112680.5, "PRINCIPAL  PARTICULARS", 480.0),
            _text_ent("2C647", "0-0", 136589.0, -114418.2, "LENGTH    (O.A)", 480.0),
            _text_ent("2C65B", "0-0", 150875.3, -114444.6, "ABT.", 480.0),
            _text_ent("2C62F", "0-0", 153382.0, -114471.0, "99,95 m", 480.0),
            _text_ent("2C646", "0-0", 136589.0, -115524.0, "LENGTH    (P.P)", 480.0),
            _text_ent("2C630", "0-0", 153777.6, -115552.3, "92,40 m", 480.0),
            _text_ent("2C64C", "0-0", 136589.0, -116629.9, "BREADTH   (MLD)", 480.0),
            _text_ent("2C65F", "0-0", 153777.6, -116660.1, "17,50 m", 480.0),
            _text_ent("2C64A", "0-0", 136589.0, -117735.9, "DEPTH     (MLD)", 480.0),
            _text_ent("2C653", "0-0", 144695.3, -117735.9, "UPPER DECK", 480.0),
            _text_ent("2C632", "0-0", 153777.6, -117767.8, "9,60 m", 480.0),
            _text_ent("2C64B", "0-0", 136589.0, -118841.9, "DRAFT (DESIGNED MLD)", 480.0),
            _text_ent("2C65E", "0-0", 154199.8, -118851.0, "7.60 m", 480.0),
            _text_ent("2C648", "0-0", 136589.0, -122269.9, "MAIN ENGINE : 6 S35MC", 480.0),
            _text_ent("2C5F6", "CHU", 154539.0, -223756.5, "So to : 02", 300.0),
            _text_ent("2C5F5", "CHU", 154539.0, -224506.5, "To so : 02", 300.0),
            _text_ent("2C61A", "CHU", 166914.0, -217006.5, "1/2005", 300.0),
            _text_ent("E99", "KC", 10000.0, -50000.0, "s=6", 200.0),
        ],
    )
    dxf_file = tmp_path / "thlt_sample.dxf"
    dxf_file.write_bytes(dxf_bytes)
    expected_sha = hashlib.sha256(dxf_bytes).hexdigest()

    obs = observe_dxf_file(dxf_file, drawing_id="THLT_SAMPLE")
    ev = obs["drawing_evidence"]
    assert ev["drawing_sha256"] == expected_sha
    assert ev["drawing_path"] is not None
    assert ev["sheet_id"] == "02/02"
    # Date 1/2005 must NEVER be fabricated into a revision
    assert ev["revision"] is None
    assert ev["revision_handles"] == []

    facts_by_key = {}
    for f in obs["engineering_facts"]:
        facts_by_key.setdefault(f["fact_key"], []).append(f)

    lpp_fact = facts_by_key["lpp_m"][0]
    assert lpp_fact["entity_handles"] == ["2C646", "2C630"]
    assert lpp_fact["layer"] == "0-0"
    assert lpp_fact["normalized_value"] == 92.4
    assert lpp_fact["normalized_unit"] == "m"
    assert lpp_fact["provenance_class"] == "NATIVE_CAD_EVIDENCE"
    assert lpp_fact["verification_state"] == "VERIFIED"

    loa_fact = facts_by_key["loa_m"][0]
    assert loa_fact["entity_handles"] == ["2C647", "2C65B", "2C62F"]
    assert loa_fact["normalized_value"] == 99.95
    assert loa_fact["verification_state"] == "PROVISIONAL_APPROXIMATE"

    assert facts_by_key["depth_m"][0]["entity_handles"] == ["2C64A", "2C632"]
    assert facts_by_key["depth_m"][0]["normalized_value"] == 9.6
    assert facts_by_key["draft_m"][0]["entity_handles"] == ["2C64B", "2C65E"]
    assert facts_by_key["draft_m"][0]["normalized_value"] == 7.6

    unbound_fact = facts_by_key["unbound_plate_thickness_mm"][0]
    assert unbound_fact["entity_handles"] == ["E99"]
    assert unbound_fact["provenance_class"] == "NATIVE_CAD_UNBOUND_TEXT"
    assert unbound_fact["verification_state"] == "UNVERIFIED_UNBOUND_TEXT"

    # Bytes observation must never invent drawing_path
    obs_bytes = observe_dxf_bytes(dxf_bytes, drawing_id="THLT_BYTES")
    assert obs_bytes["drawing_evidence"]["drawing_path"] is None
    assert obs_bytes["drawing_evidence"]["drawing_sha256"] == expected_sha

    # Explicit revision entity IS bound when genuinely present
    rev_dxf = _make_dxf_bytes(
        insunits=4,
        entities=[
            _line_ent("A11", "0", 0.0, 0.0, 1000.0, 0.0),
            _text_ent("F01", "TITLE", 100.0, 100.0, "REV : B"),
        ],
    )
    obs_rev = observe_dxf_bytes(rev_dxf, drawing_id="WITH_REV")
    assert obs_rev["drawing_evidence"]["revision"] == "B"
    assert obs_rev["drawing_evidence"]["revision_handles"] == ["F01"]

    # Hardlink > 1 link rejected fail-closed via cad_agent.file_integrity.open_bound_file
    hardlink = tmp_path / "thlt_hardlink.dxf"
    os.link(dxf_file, hardlink)
    with pytest.raises((FileIdentityError, ValueError)):
        observe_dxf_file(dxf_file, drawing_id="LINKED")


def test_v1a_native_dxf_dimension_extraction_override_conflict_and_unitless_calibration() -> None:
    from cad_agent.marine_knowledge import (
        audit_engineering_evidence_binding,
        detect_drawing_gaps_and_conflicts,
        observe_dxf_bytes,
    )

    unitless_dxf = _make_dxf_bytes(
        insunits=0,
        measurement=0,
        entities=[
            _line_ent("AA1", "HULL", 0.0, 0.0, 50000.0, 0.0),
            _text_ent("BB1", "0", 100.0, 100.0, "BAN VE BO TRI CHUNG TOAN TAU"),
            _text_ent("BB2", "0", 100.0, 500.0, "BUONG MAY - KHOANG HANG SO 1"),
            # Override '1200' with MTEXT formatting codes vs actual_measurement=1241.3112 (like THLT7000 1EBD6)
            _dim_ent("1EBD6", "SUNPO", 1241.311187, r"{\f.VnArial|b0|i0|c0|p34;\C2;1200}"),
            # Unitless 17,50m vs 17498.8338 (like GA7000 2BCA)
            _dim_ent("2BCA", "SUNPO", 17498.833760, "17,50m"),
            # Unitless 9,60 m vs 9426.7949 (1.80% mismatch once calibrated, like GA7000 2B8D)
            _dim_ent("2B8D", "SUNPO", 9426.794919, "9,60 m"),
        ],
    )
    obs_u = observe_dxf_bytes(unitless_dxf, drawing_id="GA_UNITLESS")
    dim_facts = {f["entity_handles"][0]: f for f in obs_u["engineering_facts"] if f["entity_type"] == "DIMENSION"}
    assert dim_facts["1EBD6"]["provenance_class"] == "NATIVE_MEASURED_GEOMETRY"
    assert dim_facts["1EBD6"]["verification_state"] == "CONFLICTING_OVERRIDE"
    assert dim_facts["2BCA"]["verification_state"] == "UNVERIFIED_UNITLESS"
    assert dim_facts["2BCA"]["normalized_value"] is None
    assert dim_facts["2B8D"]["verification_state"] == "UNVERIFIED_UNITLESS"

    gap = detect_drawing_gaps_and_conflicts([obs_u], partial_package=True)
    assert gap["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_DIMENSION_TEXT_OVERRIDE_CONFLICT_GA_UNITLESS" for f in gap["findings"])

    # Once independent calibration is supplied (1 CAD unit = 1.0 mm), 2BCA becomes VERIFIED while 2B8D becomes CONFLICTING_OVERRIDE
    cal_audit = audit_engineering_evidence_binding(
        [obs_u],
        calibration_verified=True,
        verified_scale_to_mm=1.0,
    )
    assert cal_audit["status"] == "CONFLICT"
    rebound = {
        f["entity_handles"][0]: f
        for f in cal_audit["observed_scope"]["drawings"][0]["engineering_facts"]
        if f["entity_type"] == "DIMENSION"
    }
    assert rebound["2BCA"]["verification_state"] == "VERIFIED"
    assert rebound["2BCA"]["normalized_unit"] == "mm"
    assert rebound["2BCA"]["normalized_value"] == pytest.approx(17498.8338, abs=1e-2)
    assert rebound["2B8D"]["verification_state"] == "CONFLICTING_OVERRIDE"


def test_v1a_check_traceability_explains_drawing_entity_and_trustworthiness_and_disable_toggle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cad_agent.marine_knowledge import (
        audit_engineering_evidence_binding,
        evaluate_regulation_applicability_and_submittal,
        explain_fact_traceability,
        observe_dxf_bytes,
    )

    mcn_dxf = _make_dxf_bytes(
        insunits=4,
        measurement=1,
        entities=[
            _line_ent("CC0", "KC", 0.0, 0.0, 9600.0, 0.0),
            _text_ent("CC1", "TEXT", 100.0, 100.0, "MAT CAT NGANG SUON GIUA"),
            _text_ent("CC2", "0", 100.0, 400.0, "CAP TAU : VR-SB"),
            _text_ent("CC3", "0", 100.0, 700.0, "Chieu dai tau L = 18.00 m"),
            _text_ent("CC4", "KC", 100.0, 1000.0, "ton day s=4.5 mm"),
            _text_ent("CC5", "KC", 100.0, 1300.0, "ton hong s=4.5 mm"),
            _dim_ent("DD1", "SUNPO", 750.0, ""),
        ],
    )
    obs_native = observe_dxf_bytes(mcn_dxf, drawing_id="MCN_18M_NATIVE")
    reg_res = evaluate_regulation_applicability_and_submittal([obs_native], partial_package=True)
    assert reg_res["status"] == "PASS"

    plate_finding = next(
        f for f in reg_res["findings"] if f["rule_id"] == "RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL"
    )
    bound_facts = plate_finding["evidence"]["bound_facts"]
    assert len(bound_facts) >= 2
    handles_flat = {h for bf in bound_facts for h in bf["entity_handles"]}
    assert {"CC3", "CC4", "CC5"} <= handles_flat
    trace = explain_fact_traceability(bound_facts[0])
    assert trace["drawing_id"] == "MCN_18M_NATIVE"
    assert trace["drawing_sha256"] == obs_native["drawing_evidence"]["drawing_sha256"]
    assert trace["sufficient_for_verified_check"] is True
    assert trace["entity_handles"]
    assert trace["explanation"]

    # OCR-only and fixture-only observations explain WHY they are NOT sufficient for verified native proof
    ocr_obs = observe_dxf_bytes(mcn_dxf, drawing_id="MCN_OCR", ocr_only=True)
    ocr_fact = ocr_obs["engineering_facts"][0]
    ocr_trace = explain_fact_traceability(ocr_fact)
    assert ocr_trace["provenance_class"] == "OCR_ONLY"
    assert ocr_trace["sufficient_for_verified_check"] is False
    assert "OCR" in ocr_trace["explanation"]

    fixture_audit = audit_engineering_evidence_binding(
        [
            {
                "drawing_id": "SYNTH_FIXTURE",
                "insunits": 4,
                "texts": [{"handle": "T1", "text": "Chieu dai tau L = 52.00 m", "x": 10.0, "y": 10.0, "height": 200.0}],
                "structural_metrics": {"double_bottom_height_mm": 750.0},
            }
        ],
        require_native_verified_facts=True,
    )
    assert fixture_audit["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_NON_NATIVE_FIXTURE_EVIDENCE_SYNTH_FIXTURE" for f in fixture_audit["findings"])

    monkeypatch.setenv("CAD_AGENT_DISABLE_MARINE_PACK", "1")
    dis = audit_engineering_evidence_binding([obs_native])
    assert dis["status"] == "DISABLED"
    assert dis["cad_mutation"] is False


@pytest.mark.real_data
def test_v1a_real_marine_7000_dxf_v0_vs_v1a_comparison() -> None:
    from cad_agent.marine_knowledge import audit_engineering_evidence_binding, observe_dxf_file

    thlt_path = os.environ.get("CAD_AGENT_MARINE_THLT_DXF")
    ga_path = os.environ.get("CAD_AGENT_MARINE_GA_DXF")
    if not thlt_path or not ga_path:
        pytest.skip("set CAD_AGENT_MARINE_THLT_DXF and CAD_AGENT_MARINE_GA_DXF for real Marine V1-A DXF validation")

    thlt = observe_dxf_file(Path(thlt_path), drawing_id="THLT7000")
    ga = observe_dxf_file(Path(ga_path), drawing_id="GA7000")

    assert thlt["drawing_evidence"]["revision"] is None
    assert ga["drawing_evidence"]["revision"] is None
    assert thlt["drawing_evidence"]["sheet_id"] == "02/02"
    assert ga["drawing_evidence"]["sheet_id"] == "01/01"
    assert thlt["particulars"]["lpp_m_values"] == [92.4]
    assert ga["particulars"]["lpp_m_values"] == [92.4]
    assert thlt["particulars"]["draft_m_values"] == [7.6]
    assert ga["particulars"]["draft_m_values"] == [7.6]

    thlt_lpp = next(f for f in thlt["engineering_facts"] if f["fact_key"] == "lpp_m")
    assert thlt_lpp["entity_handles"] == ["2C646", "2C630"]
    assert thlt_lpp["verification_state"] == "VERIFIED"

    thlt_loa = next(f for f in thlt["engineering_facts"] if f["fact_key"] == "loa_m")
    assert thlt_loa["entity_handles"] == ["2C647", "2C65B", "2C62F"]
    assert thlt_loa["verification_state"] == "PROVISIONAL_APPROXIMATE"

    audit = audit_engineering_evidence_binding([thlt, ga])
    assert audit["status"] == "CONFLICT"
    assert any(
        f["finding_id"] == "F_DIMENSION_TEXT_OVERRIDE_CONFLICT_THLT7000" for f in audit["findings"]
    )


def test_v1a_adversarial_tampered_prenormalized_facts_truthy_calibration_and_unbound_mix() -> None:
    from copy import deepcopy
    from cad_agent.marine_knowledge import (
        MarineKnowledgeError,
        audit_engineering_evidence_binding,
        observe_dxf_bytes,
    )

    clean_dxf = _make_dxf_bytes(
        insunits=4,
        measurement=1,
        entities=[
            _line_ent("AA0", "KC", 0.0, 0.0, 9600.0, 0.0),
            _text_ent("AA1", "0", 100.0, 400.0, "Chieu dai tau L = 52.00 m"),
        ],
    )
    obs_clean = observe_dxf_bytes(clean_dxf, drawing_id="CLEAN_NATIVE")
    assert audit_engineering_evidence_binding([obs_clean])["status"] == "PASS"

    # 1. Tampered fact inside pre-normalized observation must be rejected fail-closed
    tampered_obs = deepcopy(obs_clean)
    tampered_obs["engineering_facts"][0]["normalized_value"] = 12.0
    with pytest.raises(MarineKnowledgeError, match="FACT_HASH_MISMATCH"):
        audit_engineering_evidence_binding([tampered_obs])

    # 2. Truthy string calibration_verified='false' must NOT unlock unitless $INSUNITS=0 geometry
    unitless_dxf = _make_dxf_bytes(
        insunits=0,
        measurement=0,
        entities=[
            _line_ent("BB0", "KC", 0.0, 0.0, 9600.0, 0.0),
            _dim_ent("BB1", "SUNPO", 17500.0, "17,50m"),
        ],
    )
    obs_unitless = observe_dxf_bytes(unitless_dxf, drawing_id="UNITLESS_DIM")
    with pytest.raises(MarineKnowledgeError, match="CALIBRATION_FLAG_INVALID"):
        audit_engineering_evidence_binding(
            [obs_unitless],
            calibration_verified="false",  # type: ignore[arg-type]
            verified_scale_to_mm=1.0,
        )

    # 3. Unbound CAD text or unmeasurable DIMENSION (actual_measurement=0) must block PASS in V1-A audit
    mixed_unbound_dxf = _make_dxf_bytes(
        insunits=4,
        measurement=1,
        entities=[
            _line_ent("CC0", "KC", 0.0, 0.0, 9600.0, 0.0),
            _text_ent("CC1", "0", 100.0, 400.0, "Chieu dai tau L = 52.00 m"),
            _text_ent("CC2", "KC", 100.0, 800.0, "s=6"),
            _dim_ent("DD0", "SUNPO", 0.0, ""),
        ],
    )
    obs_mixed = observe_dxf_bytes(mixed_unbound_dxf, drawing_id="MIXED_UNBOUND")
    res_mixed = audit_engineering_evidence_binding([obs_mixed])
    assert res_mixed["status"] == "INSUFFICIENT_EVIDENCE"
    fids = {f["finding_id"] for f in res_mixed["findings"]}
    assert "F_UNBOUND_CAD_TEXT_FACTS_MIXED_UNBOUND" in fids
    assert "F_INFERRED_OR_UNMEASURABLE_FACTS_MIXED_UNBOUND" in fids

    # 4. Diameter/Radius override 'R500' vs actual_measurement=620.0 in mm must trigger CONFLICTING_OVERRIDE
    rad_dxf = _make_dxf_bytes(
        insunits=4,
        measurement=1,
        entities=[
            _line_ent("EE0", "KC", 0.0, 0.0, 1000.0, 0.0),
            _dim_ent("EE1", "SUNPO", 620.0, "R500"),
        ],
    )
    obs_rad = observe_dxf_bytes(rad_dxf, drawing_id="RAD_CONFLICT")
    assert audit_engineering_evidence_binding([obs_rad])["status"] == "CONFLICT"
