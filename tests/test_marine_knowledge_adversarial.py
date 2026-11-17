"""Adversarial regression matrix (Groups A-J, DM-01..DM-13) for Marine Knowledge Pack V0."""

from __future__ import annotations

import pytest

from cad_agent.marine_knowledge import (
    MarineKnowledgeError,
    build_marine_core_proposal,
    classify_marine_drawing,
    detect_drawing_gaps_and_conflicts,
    evaluate_regulation_applicability_and_submittal,
    get_marine_source_manifest,
    normalize_observation,
    validate_check_result,
    verify_source_citation,
)


def _valid_ga(
    *,
    drawing_id: str = "ADV_GA_52M",
    insunits: int = 4,
    length_line: str = "Lpp = 52.00 m",
    breadth_line: str = "B = 9.60 m",
    depth_line: str = "D = 4.20 m",
    draft_line: str = "T = 3.10 m",
    class_line: str = "CẤP TÀU : VR-SB",
    ship_type_line: str = "SHIP TYPE : DRY CARGO",
    ap_x: float = 1000.0,
    fp_x: float = 53000.0,
    bulkheads: int | None = 4,
    extra_texts: list[dict[str, object]] | None = None,
    entity_counts: dict[str, int] | None = None,
) -> dict[str, object]:
    texts: list[dict[str, object]] = [
        {"handle": "A1", "text": "BẢN VẼ BỐ TRÍ CHUNG TOÀN TÀU", "x": 500.0, "y": 500.0, "height": 350.0},
        {"handle": "A2", "text": "KHOANG HÀNG SỐ 1 - BUỒNG MÁY - VÁCH CHỐNG VA", "x": 20000.0, "y": 2000.0, "height": 260.0},
        {"handle": "A3", "text": class_line, "x": 60000.0, "y": 1000.0, "height": 250.0},
        {"handle": "A4", "text": length_line, "x": 60000.0, "y": 1500.0, "height": 250.0},
        {"handle": "A5", "text": breadth_line, "x": 60000.0, "y": 2000.0, "height": 250.0},
        {"handle": "A6", "text": depth_line, "x": 60000.0, "y": 2500.0, "height": 250.0},
        {"handle": "A7", "text": draft_line, "x": 60000.0, "y": 3000.0, "height": 250.0},
        {"handle": "A8", "text": "MAIN ENGINE : 2x550 HP", "x": 60000.0, "y": 3500.0, "height": 250.0},
        {"handle": "A9", "text": ship_type_line, "x": 60000.0, "y": 4000.0, "height": 250.0},
        {"handle": "A10", "text": "PORT OF REGISTRY : HAI PHONG", "x": 60000.0, "y": 4500.0, "height": 250.0},
        {"handle": "A11", "text": "A.P", "x": ap_x, "y": 0.0, "height": 300.0},
        {"handle": "A12", "text": "F.P", "x": fp_x, "y": 0.0, "height": 300.0},
    ]
    if extra_texts:
        texts.extend(extra_texts)
    metrics: dict[str, object] = {}
    if bulkheads is not None:
        metrics["transverse_watertight_bulkhead_count"] = bulkheads
    payload: dict[str, object] = {
        "drawing_id": drawing_id,
        "drawing_code": "GA-01-01",
        "insunits": insunits,
        "measurement": 1,
        "claimed_scale": 100.0,
        "texts": texts,
        "structural_metrics": metrics,
        "blank_fields": [],
    }
    if entity_counts is not None:
        payload["entity_counts"] = entity_counts
    return payload


def _valid_mcn(
    *,
    drawing_id: str = "ADV_MCN_52M",
    insunits: int = 4,
    class_line: str = "CẤP TÀU : VR-SB",
    length_line: str = "Lpp = 52.00 m",
    breadth_line: str = "B = 9.60 m",
    depth_line: str = "D = 4.20 m",
    draft_line: str = "T = 3.10 m",
    ship_type_line: str = "SHIP TYPE : DRY CARGO",
    db_mm: float | None = 750.0,
    girder_spacing_mm: float | None = 2200.0,
    extra_texts: list[dict[str, object]] | None = None,
    extra_metrics: dict[str, object] | None = None,
) -> dict[str, object]:
    texts: list[dict[str, object]] = [
        {"handle": "M1", "text": "MẶT CẮT NGANG SƯỜN GIỮA", "x": 500.0, "y": 500.0, "height": 200.0},
        {"handle": "M2", "text": "ĐÁY ĐÔI - ĐÀ NGANG ĐẶC", "x": 1000.0, "y": 600.0, "height": 150.0},
        {"handle": "M3", "text": class_line, "x": 4000.0, "y": 1000.0, "height": 150.0},
        {"handle": "M4", "text": length_line, "x": 4000.0, "y": 1250.0, "height": 150.0},
        {"handle": "M5", "text": breadth_line, "x": 4000.0, "y": 1500.0, "height": 150.0},
        {"handle": "M6", "text": depth_line, "x": 4000.0, "y": 1750.0, "height": 150.0},
        {"handle": "M7", "text": draft_line, "x": 4000.0, "y": 2000.0, "height": 150.0},
        {"handle": "M8", "text": "MAIN ENGINE : 2x550 HP", "x": 4000.0, "y": 2250.0, "height": 150.0},
        {"handle": "M9", "text": ship_type_line, "x": 4000.0, "y": 2500.0, "height": 150.0},
    ]
    if extra_texts:
        texts.extend(extra_texts)
    metrics: dict[str, object] = {}
    if db_mm is not None:
        metrics["double_bottom_height_mm"] = db_mm
    if girder_spacing_mm is not None:
        metrics["bottom_girder_max_spacing_mm"] = girder_spacing_mm
    if extra_metrics:
        metrics.update(extra_metrics)
    return {
        "drawing_id": drawing_id,
        "drawing_code": "KC-02-01",
        "insunits": insunits,
        "measurement": 1,
        "claimed_scale": 50.0,
        "texts": texts,
        "structural_metrics": metrics,
        "blank_fields": [],
    }


def test_group_a_correct_data_and_mixed_unit_normalization() -> None:
    """Group A (DM-02, DM-12): valid multi-sheet inland VR-SB across mm/cm/m normalizes cleanly."""
    ga_mm = _valid_ga(insunits=4, length_line="Chiều dài tàu L = 52.00 m")
    mcn_cm = _valid_mcn(
        drawing_id="ADV_MCN_CM",
        insunits=5,
        length_line="Lpp = 5200",
        breadth_line="B = 960",
        depth_line="D = 420",
        draft_line="T = 310",
    )
    # Heights scaled consistently in cm for 1:50 printed size (>= 2.5 mm)
    for txt in mcn_cm["texts"]:
        txt["height"] = float(txt["height"]) / 10.0
    mcn_m = _valid_mcn(
        drawing_id="ADV_MCN_M",
        insunits=6,
        length_line="Lpp = 52.00",
        breadth_line="B = 9.60",
        depth_line="D = 4.20",
        draft_line="T = 3.10",
    )
    for txt in mcn_m["texts"]:
        txt["height"] = float(txt["height"]) / 1000.0

    reg = evaluate_regulation_applicability_and_submittal([ga_mm, mcn_cm, mcn_m], partial_package=True)
    assert reg["status"] == "PASS"
    assert reg["cad_mutation"] is False
    assert reg["regulatory_compliance_proven"] is False
    assert reg["observed_scope"]["cad_geometry_verified"] is False

    gap = detect_drawing_gaps_and_conflicts([ga_mm, mcn_cm, mcn_m], partial_package=True)
    assert gap["status"] == "PASS"
    assert gap["observed_scope"]["cad_geometry_verified"] is False


def test_group_b_missing_evidence_length_and_lpp_boundary_ambiguity() -> None:
    """Group B (DM-04, DM-05, DM-07): missing L, empty metrics, wrong-sheet metrics, Lpp boundary ambiguity."""
    # 1. VR-SB with zero length annotation cannot claim PASS under QCVN 72 L <= 140m
    ga_no_len = _valid_ga(length_line="PHIÊN BẢN THAM KHẢO")
    res_no_len = evaluate_regulation_applicability_and_submittal([ga_no_len])
    assert res_no_len["status"] == "INSUFFICIENT_EVIDENCE"

    # 2. VR-SB with L=52m but ZERO scantling/bulkhead metrics cannot return PASS
    ga_no_metrics = _valid_ga(bulkheads=None)
    res_no_metrics = evaluate_regulation_applicability_and_submittal([ga_no_metrics])
    assert res_no_metrics["status"] == "INSUFFICIENT_EVIDENCE"

    # 3. Boundary ambiguity: Lpp=39.50m sits near 40m threshold without L or Lwl -> must NOT PASS with 3 bulkheads
    ga_boundary = _valid_ga(length_line="Lpp = 39.50 m", ap_x=1000.0, fp_x=40500.0, bulkheads=3)
    res_boundary = evaluate_regulation_applicability_and_submittal([ga_boundary, _valid_mcn(length_line="Lpp = 39.50 m")])
    assert res_boundary["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_LENGTH_L_VS_LPP_AMBIGUOUS" for f in res_boundary["findings"])

    # 4. Wrong-sheet metric placement (LINES_PLAN carrying double_bottom_height_mm with no MCN/KCCB)
    lines_wrong_metric = {
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
    res_wrong_sheet = evaluate_regulation_applicability_and_submittal([lines_wrong_metric])
    assert res_wrong_sheet["status"] == "INSUFFICIENT_EVIDENCE"

    # 5. Metric provenance distinguishes FIXTURE_SUPPLIED vs NATIVE_CAD_TEXT
    obs_ga = normalize_observation(_valid_ga())
    assert obs_ga["metric_provenance"]["transverse_watertight_bulkhead_count"] == "FIXTURE_SUPPLIED"
    assert obs_ga["metric_provenance"]["lpp_m"] == "NATIVE_CAD_TEXT"


def test_group_c_conflicting_particulars_across_sheets() -> None:
    """Group C (DM-08): draft, hull number, ship type, and double bottom height conflicts caught."""
    ga_1 = _valid_ga(draft_line="T = 3.10 m", ship_type_line="SHIP TYPE : DRY CARGO", extra_texts=[{"handle": "H1", "text": "HULL NO : H-01", "x": 60000.0, "y": 5000.0, "height": 250.0}])
    mcn_2 = _valid_mcn(draft_line="T = 4.40 m", ship_type_line="SHIP TYPE : OIL TANKER", db_mm=750.0, extra_texts=[{"handle": "H2", "text": "HULL NO : H-99", "x": 4000.0, "y": 2750.0, "height": 150.0}])
    mcn_3 = _valid_mcn(drawing_id="KCCB_52M", db_mm=920.0)

    gap = detect_drawing_gaps_and_conflicts([ga_1, mcn_2, mcn_3])
    assert gap["status"] == "CONFLICT"
    ids = {f["finding_id"] for f in gap["findings"]}
    assert "F_DIMENSION_CONFLICT_DRAFT" in ids
    assert "F_SHIP_TYPE_CONFLICT" in ids
    assert "F_HULL_NO_CONFLICT" in ids
    assert "F_METRIC_CONFLICT_DOUBLE_BOTTOM_HEIGHT" in ids

    reg = evaluate_regulation_applicability_and_submittal([ga_1, mcn_2])
    assert reg["status"] == "CONFLICT"


def test_group_d_unit_and_calibration_attacks() -> None:
    """Group D (DM-01, DM-02): positive scale without calibration_verified, invalid scale, 1000x mismatch."""
    unitless_ga = _valid_ga(insunits=0)
    unitless_mcn = _valid_mcn(insunits=0)

    # 1. scale > 0 MUST NOT bypass calibration gate when calibration_verified=False
    res_unverified_scale_skill3 = detect_drawing_gaps_and_conflicts(
        [unitless_ga], calibration_verified=False, verified_scale_to_mm=1.0
    )
    assert res_unverified_scale_skill3["status"] == "INSUFFICIENT_EVIDENCE"

    res_unverified_scale_skill2 = evaluate_regulation_applicability_and_submittal(
        [unitless_ga, unitless_mcn], calibration_verified=False, verified_scale_to_mm=1.0
    )
    assert res_unverified_scale_skill2["status"] == "INSUFFICIENT_EVIDENCE"

    # 2. calibration_verified=True WITHOUT positive verified_scale_to_mm still fails closed
    res_no_scale_val = detect_drawing_gaps_and_conflicts(
        [unitless_ga], calibration_verified=True, verified_scale_to_mm=None
    )
    assert res_no_scale_val["status"] == "INSUFFICIENT_EVIDENCE"

    # 3. True independent calibration (calibration_verified=True AND finite scale > 0) unlocks calibrated checks
    res_calibrated = evaluate_regulation_applicability_and_submittal(
        [unitless_ga, unitless_mcn], calibration_verified=True, verified_scale_to_mm=1.0
    )
    assert res_calibrated["status"] == "PASS"

    # 4. Invalid scale values rejected fail-closed
    for bad_scale in (-1.0, 0.0, float("nan"), float("inf"), True):
        with pytest.raises(MarineKnowledgeError, match="CALIBRATION_SCALE_INVALID"):
            detect_drawing_gaps_and_conflicts([unitless_ga], calibration_verified=True, verified_scale_to_mm=bad_scale)  # type: ignore[arg-type]

    # 5. 1000x header unit mismatch: $INSUNITS=6 (meters) vs A.P=1000..F.P=53000 (52 km) while Lpp=52m
    ga_1000x = _valid_ga(insunits=6, ap_x=1000.0, fp_x=53000.0)
    res_1000x = detect_drawing_gaps_and_conflicts([ga_1000x])
    assert res_1000x["status"] == "CONFLICT"
    assert any(f["finding_id"] == "F_UNIT_OR_SCALE_MISMATCH_1000X" for f in res_1000x["findings"])


def test_group_e_source_provenance_and_citation_attacks() -> None:
    """Group E (DM-10): verification levels, pagination offsets, version mismatch, cross-reg clause spoofing."""
    manifest = get_marine_source_manifest()
    qcvn_sha = next(s["sha256"] for s in manifest["sources"] if s["source_id"] == "QCVN_72_2025_BGTVT")

    base_cite = {
        "source_id": "QCVN_72_2025_BGTVT",
        "source_sha256": qcvn_sha,
        "source_version": "2025 (867p)",
        "clause": "Mục I, Chương 1, 1.1.1 Phạm vi điều chỉnh",
        "pdf_page": [3],
        "reg_page": [19],
    }

    # Without source bytes -> METADATA_ONLY / SOURCE_UNAVAILABLE (never claims byte verification)
    meta_only = verify_source_citation(base_cite, manifest)
    assert "MANIFEST_MATCH" in meta_only["verification_states"]
    assert "SOURCE_UNAVAILABLE" in meta_only["verification_states"]
    assert "SOURCE_BYTES_VERIFIED" not in meta_only["verification_states"]

    # Wrong pagination offset on consolidated QCVN 72 local PDF (pdf_page 3 != reg_page 3)
    with pytest.raises(MarineKnowledgeError, match="CITATION_PAGINATION_OFFSET_MISMATCH"):
        verify_source_citation({**base_cite, "reg_page": [3]}, manifest)

    # Wrong source version
    with pytest.raises(MarineKnowledgeError, match="CITATION_VERSION_MISMATCH"):
        verify_source_citation({**base_cite, "source_version": "2014 (legacy)"}, manifest)

    # Textbook with non-empty reg_page rejected
    vmu_sha = next(s["sha256"] for s in manifest["sources"] if s["source_id"] == "VIMARU_VETAU_CH1")
    with pytest.raises(MarineKnowledgeError, match="CITATION_REG_PAGE_MISMATCH"):
        verify_source_citation(
            {"source_id": "VIMARU_VETAU_CH1", "source_sha256": vmu_sha, "clause": "Ch.1", "pdf_page": [15], "reg_page": [15]},
            manifest,
        )

    # Cross-regulation clause spoofing
    with pytest.raises(MarineKnowledgeError, match="CITATION_CLAUSE_SOURCE_MISMATCH"):
        verify_source_citation({**base_cite, "clause": "QCVN 21:2015/BGTVT Phần 2A"}, manifest)

    # Synthetic byte verification mismatch rejected fail-closed
    with pytest.raises(MarineKnowledgeError, match="CITATION_SHA_STALE_OR_MISMATCH"):
        verify_source_citation(base_cite, manifest, source_bytes=b"forged pdf content")


def test_group_f_domain_isolation_and_negation_attacks() -> None:
    """Group F (DM-06): mechanical/automotive drawings and negated marine labels do not trigger inland rules."""
    mech_drawing = {
        "drawing_id": "MECH_SHAFT_01",
        "insunits": 4,
        "texts": [
            {"handle": "1", "text": "BẢN VẼ CHI TIẾT TRỤC BẬC CƠ KHÍ", "x": 10.0, "y": 10.0, "height": 5.0},
            {"handle": "2", "text": "VẬT LIỆU : THÉP C45", "x": 10.0, "y": 20.0, "height": 5.0},
            {"handle": "3", "text": "ĐƯỜNG KÍNH D = 60 mm, L = 240 mm", "x": 10.0, "y": 30.0, "height": 5.0},
        ],
    }
    res_cls = classify_marine_drawing(mech_drawing)
    assert res_cls["status"] == "NOT_APPLICABLE"
    res_reg = evaluate_regulation_applicability_and_submittal([mech_drawing])
    assert res_reg["status"] == "NOT_APPLICABLE"
    assert res_reg["applicable_regulation_scope"]["candidate_referred_regulation"] is None

    negated_note = {
        "drawing_id": "NEGATED_SCOPE",
        "insunits": 4,
        "texts": [
            {"handle": "1", "text": "BẢN VẼ BỐ TRÍ CHUNG", "x": 10.0, "y": 10.0, "height": 250.0},
            {"handle": "2", "text": "GHI CHÚ: KHÔNG ÁP DỤNG QCVN 72 VÀ KHÔNG PHẢI TÀU VR-SB", "x": 10.0, "y": 200.0, "height": 250.0},
            {"handle": "3", "text": "Lpp = 52.00 m", "x": 10.0, "y": 400.0, "height": 250.0},
        ],
    }
    res_neg = evaluate_regulation_applicability_and_submittal([negated_note])
    assert res_neg["status"] == "INSUFFICIENT_EVIDENCE"


def test_group_g_h_ocr_corruption_draft_confusion_and_rule_conditions() -> None:
    """Groups G-H (DM-03, DM-09, DM-12): OCR corrupted numbers, draft T!=plate t, dry cargo & 3.7.3 checks."""
    # 1. Corrupted OCR numeric token must NOT truncate silently to 52.00 m
    corrupt_obs = _valid_ga(length_line="Lpp = 52.O5 m")
    res_corrupt = detect_drawing_gaps_and_conflicts([corrupt_obs])
    assert res_corrupt["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_CORRUPTED_NUMERIC_TOKEN" for f in res_corrupt["findings"])

    # 2. Small hull draft "T = 3.5 m" must NOT be extracted as plate thickness!
    small_draft_only = {
        "drawing_id": "MCN_18M_DRAFT_NO_PLATE",
        "drawing_code": "KC-01",
        "insunits": 4,
        "texts": [
            {"handle": "S1", "text": "MẶT CẮT NGANG SƯỜN GIỮA", "x": 100.0, "y": 100.0, "height": 150.0},
            {"handle": "S2", "text": "CẤP TÀU : VR-SII", "x": 200.0, "y": 200.0, "height": 150.0},
            {"handle": "S3", "text": "Chiều dài tàu L = 18.00 m", "x": 200.0, "y": 400.0, "height": 150.0},
            {"handle": "S4", "text": "T = 1.60 m", "x": 200.0, "y": 600.0, "height": 150.0},
        ],
        "structural_metrics": {"double_bottom_height_mm": 750.0},
    }
    obs_small = normalize_observation(small_draft_only)
    assert "min_plate_thickness_mm" not in obs_small["structural_metrics"]

    # 3. Small hull with min_plate=2.6 mm meets 3.7.2 (>=2.5mm) but cannot claim PASS without 3.7.3 bottom>=3mm & bilge>=4mm
    small_incomplete_plate = {
        **small_draft_only,
        "structural_metrics": {"double_bottom_height_mm": 750.0, "min_plate_thickness_mm": 2.6},
    }
    res_small_incomplete = evaluate_regulation_applicability_and_submittal([small_incomplete_plate])
    assert res_small_incomplete["status"] in {"INSUFFICIENT_EVIDENCE", "CONFLICT"}

    # 4. Non-dry-cargo vessel (OIL TANKER) must not get PASS under 2.4.6-8 dry-cargo table alone
    tanker_ga = _valid_ga(ship_type_line="SHIP TYPE : OIL TANKER", bulkheads=4)
    res_tanker = evaluate_regulation_applicability_and_submittal([tanker_ga, _valid_mcn(ship_type_line="SHIP TYPE : OIL TANKER")])
    assert any(
        f["rule_id"] == "RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT" and f["verdict"] == "INSUFFICIENT_EVIDENCE"
        for f in res_tanker["findings"]
    )
    assert res_tanker["status"] == "INSUFFICIENT_EVIDENCE"


def test_group_i_and_j_geometry_shell_malicious_proposals_and_limits() -> None:
    """Groups I-J (DM-11, DM-12, DM-13): text-only CAD shell, malicious proposals, oversized input guard."""
    # 1. Observation declaring CAD entities with 0 geometric primitives cannot PASS geometry gap check
    text_shell = _valid_ga(entity_counts={"TEXT": 12, "LINE": 0, "LWPOLYLINE": 0, "SPLINE": 0})
    gap_shell = detect_drawing_gaps_and_conflicts([text_shell])
    assert gap_shell["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(f["finding_id"] == "F_CAD_GEOMETRY_MISSING_OR_UNVERIFIED" for f in gap_shell["findings"])

    # 2. Malicious proposals rejected
    with pytest.raises(MarineKnowledgeError, match="PROPOSAL_ACTION_INVALID"):
        build_marine_core_proposal(
            target_drawing_id="ADV_GA_52M",
            action_kind="EXECUTE_AUTOCAD_MUTATION",
            evidence={"ok": False},
        )
    with pytest.raises(MarineKnowledgeError, match="PROPOSAL_TARGET_INVALID"):
        build_marine_core_proposal(
            target_drawing_id="../etc/passwd",
            action_kind="COMPLETE_TITLE_BLOCK_FIELDS",
            evidence={"blank_fields": ["PORT OF REGISTRY"]},
        )
    with pytest.raises(MarineKnowledgeError, match="PROPOSAL_EVIDENCE_INVALID"):
        build_marine_core_proposal(
            target_drawing_id="ADV_GA_52M",
            action_kind="COMPLETE_TITLE_BLOCK_FIELDS",
            evidence={"cad_mutation": True},
        )
    with pytest.raises(MarineKnowledgeError, match="PROPOSAL_STALE_HANDLE"):
        build_marine_core_proposal(
            target_drawing_id="ADV_GA_52M",
            action_kind="CHECK_NON_UNIFORM_VERTICAL_SCALE",
            evidence={"target_handles": ["DEAD"], "observed_handles": ["10A", "10B"]},
        )

    # 3. validate_check_result blocks untrusted mutated proposal embedded in payload
    valid_res = detect_drawing_gaps_and_conflicts([_valid_ga(insunits=0)])
    valid_res["proposal_only_actions"][0]["cad_mutation"] = True
    with pytest.raises(MarineKnowledgeError, match="PROPOSAL_MUTATION_FORBIDDEN"):
        validate_check_result(valid_res)

    # 4. Oversized untrusted observation list rejected fail-closed
    with pytest.raises(MarineKnowledgeError, match="OBSERVATION_INPUT_TOO_LARGE"):
        normalize_observation({"drawing_id": "HUGE", "texts": [{"text": "A"}] * 5001})
