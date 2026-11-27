"""Read-only Marine Knowledge Pack V0 engineering skills and CAD Core proposal gate."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import math
import re
from typing import Any

from .contracts import (
    MARINE_CHECK_RESULT_SCHEMA_VERSION,
    MarineKnowledgeError,
    SUPPORTED_REGULATIONS,
    _ALLOWED_PROPOSAL_ACTIONS,
    _SAFE_DRAWING_ID_RE,
    _SHA256_RE,
    validate_check_result,
    verify_source_citation,
)
from .manifest import get_marine_source_manifest
from .observer import normalize_observation
from .pack import get_marine_knowledge_pack, is_marine_pack_enabled

_INSUNITS_TO_MM: dict[int, float] = {
    4: 1.0,     # Millimeters
    5: 10.0,    # Centimeters
    6: 1000.0,  # Meters
}

_REQUIRED_SUBMITTAL_DRAWINGS = (
    "GENERAL_ARRANGEMENT",
    "MIDSHIP_STRUCTURAL",
    "BASIC_STRUCTURAL",
)

_MANIFEST = get_marine_source_manifest()
_SOURCES_BY_ID = {src["source_id"]: src for src in _MANIFEST["sources"]}


_VERIFIED_PROVENANCES = frozenset({"NATIVE_CAD_TEXT", "FIXTURE_SUPPLIED"})
_BOOL_EXCEPTION_METRIC_KEYS = frozenset(
    {
        "double_hull_or_double_side",
        "is_container_ship",
        "single_side_or_non_double_hull",
        "bulkhead_2_4_6_9_exception_applicable",
    }
)
_NON_DIM_METRIC_KEYS = frozenset({"floor_spacing_region", "floor_spacing_measurements"}) | _BOOL_EXCEPTION_METRIC_KEYS
_UNDER_HATCH_REGIONS = frozenset({"UNDER_CARGO_HATCH", "UNDER_HATCH", "CARGO_HATCH", "CARGO_HOLD", "DUOI_MIENG_KHOANG_HANG"})
_OUTSIDE_HATCH_REGIONS = frozenset({"OUTSIDE_CARGO_HATCH", "OUTSIDE_HATCH", "NGOAI_MIENG_KHOANG_HANG", "NGOAI_KHOANG_HANG"})
_INCOMPLETE_OBSERVATION_FIELDS = (
    "skipped_entities",
    "unsupported_insert_transforms",
    "unsupported_text_transforms",
)


def _incomplete_observation_fields(obs: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: deepcopy(obs[field])
        for field in _INCOMPLETE_OBSERVATION_FIELDS
        if obs.get(field)
    }


def _validate_scale_arg(verified_scale_to_mm: object) -> float | None:
    if verified_scale_to_mm is None:
        return None
    if isinstance(verified_scale_to_mm, bool) or not isinstance(verified_scale_to_mm, (int, float)):
        raise MarineKnowledgeError("CALIBRATION_SCALE_INVALID")
    val = float(verified_scale_to_mm)
    if not math.isfinite(val) or val <= 0.0:
        raise MarineKnowledgeError("CALIBRATION_SCALE_INVALID")
    return val


def build_marine_core_proposal(
    *,
    target_drawing_id: str,
    action_kind: str,
    evidence: Mapping[str, Any],
    reason: str = "",
) -> dict[str, Any]:
    """Build a strictly non-mutating CAD Core proposal requiring downstream gate admission."""
    if not isinstance(target_drawing_id, str) or not _SAFE_DRAWING_ID_RE.fullmatch(target_drawing_id.strip()):
        raise MarineKnowledgeError("PROPOSAL_TARGET_INVALID")
    clean_target = target_drawing_id.strip()
    if not isinstance(action_kind, str) or action_kind.strip() not in _ALLOWED_PROPOSAL_ACTIONS:
        raise MarineKnowledgeError("PROPOSAL_ACTION_INVALID")
    clean_action = action_kind.strip()
    if not isinstance(evidence, Mapping):
        raise MarineKnowledgeError("PROPOSAL_EVIDENCE_INVALID")
    if evidence.get("cad_mutation") is True or evidence.get("proposal_only") is False:
        raise MarineKnowledgeError("PROPOSAL_EVIDENCE_INVALID")
    ev_sha = evidence.get("source_sha256")
    if ev_sha is not None and (not isinstance(ev_sha, str) or not _SHA256_RE.fullmatch(ev_sha)):
        raise MarineKnowledgeError("PROPOSAL_SHA_INVALID")
    target_handles = evidence.get("target_handles")
    observed_handles = evidence.get("observed_handles")
    if (
        isinstance(target_handles, Sequence)
        and not isinstance(target_handles, (str, bytes))
        and isinstance(observed_handles, Sequence)
        and not isinstance(observed_handles, (str, bytes))
    ):
        obs_set = {str(h) for h in observed_handles}
        if any(str(h) not in obs_set for h in target_handles):
            raise MarineKnowledgeError("PROPOSAL_STALE_HANDLE")
    if "proposed_value_mm" in evidence:
        insunits = evidence.get("insunits")
        supported_unit = (
            isinstance(insunits, int)
            and not isinstance(insunits, bool)
            and insunits in _INSUNITS_TO_MM
        )
        scale = evidence.get("verified_scale_to_mm")
        calibrated_fallback = (
            evidence.get("calibration_verified") is True
            and isinstance(scale, (int, float))
            and not isinstance(scale, bool)
            and math.isfinite(float(scale))
            and float(scale) > 0.0
        )
        if not supported_unit and not calibrated_fallback:
            raise MarineKnowledgeError("PROPOSAL_UNCALIBRATED_DIM_EDIT")
    if evidence.get("conflicting_measurements") is True:
        raise MarineKnowledgeError("PROPOSAL_CONFLICTING_MEASUREMENTS")
    return {
        "proposal_id": f"PROP_{clean_target}_{clean_action}",
        "target_drawing_id": clean_target,
        "action_kind": clean_action,
        "cad_mutation": False,
        "proposal_only": True,
        "requires_cad_core_admission": True,
        "required_core_gates": ["CAD_CORE_SOURCE_SUPPORT", "CAD_CORE_REVIEW"],
        "evidence": deepcopy(dict(evidence)),
        "reason": reason or f"Proposal only ({clean_action}) for {clean_target}; requires CAD Core approval before any CAD edit.",
    }


def _pack_context() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    pack = get_marine_knowledge_pack(enabled=True)
    rules_by_id = {rule["rule_id"]: rule for rule in pack["rules"]}
    return pack, rules_by_id


def _disabled_result(skill_id: str, summary: str) -> dict[str, Any]:
    return validate_check_result(
        {
            "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
            "skill_id": skill_id,
            "pack_id": "MARINE_KNOWLEDGE_PACK_V0",
            "pack_sha256": None,
            "pack_status": "DISABLED",
            "cad_mutation": False,
            "regulatory_compliance_proven": False,
            "status": "DISABLED",
            "summary": summary,
            "observed_scope": {"disabled": True},
            "applicable_regulation_scope": {"disabled": True},
            "partial_package": True,
            "findings": [],
            "checks_executed": [],
            "checks_not_executed": ["Marine Knowledge Pack disabled; CAD Core behavior untouched"],
            "limitations": ["Marine Knowledge Pack is disabled via argument or CAD_AGENT_DISABLE_MARINE_PACK."],
            "proposal_only_actions": [],
        }
    )


def _make_finding(
    rules_by_id: Mapping[str, Mapping[str, Any]],
    *,
    finding_id: str,
    verdict: str,
    rule_id: str,
    evidence: Mapping[str, Any],
    reason: str,
    confidence: str | None = None,
    limitation: str | None = None,
    exceptions_checked: Sequence[str] | None = None,
    conditions_applied: Sequence[str] | None = None,
) -> dict[str, Any]:
    rule = rules_by_id[rule_id]
    source_entry = _SOURCES_BY_ID[rule["source_id"]]
    source_sha = source_entry["sha256"]
    citation = {
        "source_id": rule["source_id"],
        "source_sha256": source_sha,
        "clause": rule["clause"],
        "pdf_page": list(rule["pdf_page"]),
        "reg_page": list(rule["reg_page"]),
    }
    verify_source_citation(citation, _MANIFEST)
    reg_note = f"reg_page={list(rule['reg_page'])}" if rule["reg_page"] else "reg_page=[] (textbook)"
    pagination_basis = (
        f"bound_local_sha256:{source_sha} | pdf_page={list(rule['pdf_page'])} | {reg_note} "
        "(external uploads may paginate differently)"
    )
    resolved_exceptions = (
        list(exceptions_checked)
        if exceptions_checked is not None
        else [f"Not evaluated in V0: {exc}" for exc in rule["exceptions"]]
    )
    if conditions_applied is not None:
        resolved_conditions = list(conditions_applied)
    elif verdict == "PASS":
        resolved_conditions = list(rule["conditions"])
    else:
        resolved_conditions = [f"Evaluated / gated ({verdict}): {c}" for c in rule["conditions"]]
    return {
        "finding_id": finding_id,
        "verdict": verdict,
        "rule_id": rule["rule_id"],
        "source_id": rule["source_id"],
        "source_sha256": source_sha,
        "source_version": rule["source_version"],
        "clause": rule["clause"],
        "pdf_page": list(rule["pdf_page"]),
        "reg_page": list(rule["reg_page"]),
        "pagination_basis": pagination_basis,
        "conditions_applied": resolved_conditions,
        "exceptions_checked": resolved_exceptions,
        "evidence": deepcopy(dict(evidence)),
        "reason": reason,
        "confidence": confidence or rule["confidence_default"],
        "limitation": limitation or rule["limitation"],
    }


def _to_obs_list(observations: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(observations, Mapping):
        return [normalize_observation(observations)]
    if isinstance(observations, Sequence) and not isinstance(observations, (str, bytes)):
        return [normalize_observation(item) for item in observations]
    raise TypeError("observations must be a mapping or sequence of mappings")


def _detect_title_declared_type(obs: Mapping[str, Any]) -> str | None:
    code_up = str(obs.get("drawing_code") or "").upper()
    code_candidate: str | None = None
    if re.search(r"\bTHLT\b", code_up):
        code_candidate = "LINES_PLAN"
    elif re.search(r"\b(?:GA|BTC)\b", code_up):
        code_candidate = "GENERAL_ARRANGEMENT"
    elif re.search(r"\bMCN\b", code_up):
        code_candidate = "MIDSHIP_STRUCTURAL"
    elif re.search(r"\bKCCB\b", code_up):
        code_candidate = "BASIC_STRUCTURAL"

    text_titles: list[str] = []
    for entry in obs.get("texts", []):
        folded = entry["folded"]
        if any(tok in folded for tok in ("bo tri chung", "general arrangement")):
            text_titles.append("GENERAL_ARRANGEMENT")
        elif any(tok in folded for tok in ("mat cat ngang", "midship section")):
            text_titles.append("MIDSHIP_STRUCTURAL")
        elif any(tok in folded for tok in ("ket cau co ban", "basic structural", "khai trien ton vo", "shell expansion")):
            text_titles.append("BASIC_STRUCTURAL")
        elif any(tok in folded for tok in ("lines plan", "duong hinh dang", "tuyen hinh")) and "body plan" not in folded:
            text_titles.append("LINES_PLAN")

    if code_candidate is not None:
        return code_candidate
    if re.search(r"\bKC\b", code_up):
        if "MIDSHIP_STRUCTURAL" in text_titles:
            return "MIDSHIP_STRUCTURAL"
        return "BASIC_STRUCTURAL"
    return text_titles[0] if text_titles else None


def _score_drawing_content(obs: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, list[str]]]:
    scores = {
        "LINES_PLAN": 0,
        "GENERAL_ARRANGEMENT": 0,
        "MIDSHIP_STRUCTURAL": 0,
        "BASIC_STRUCTURAL": 0,
    }
    hits: dict[str, list[str]] = {key: [] for key in scores}
    corpus = " | ".join(entry["folded"] for entry in obs.get("texts", []))

    rules: tuple[tuple[str, int, str], ...] = (
        ("LINES_PLAN", 3, r"\b(?:d\.?chuan|duong\s+chuan|body\s+plan|half\s+breadth|sheer\s+plan)\b"),
        ("LINES_PLAN", 3, r"\b(?:dn\s*\d+|cd\s*\d+|c\.?doc|sn\s*\d+)\b"),
        ("LINES_PLAN", 2, r"\b(?:tuyen\s+hinh|duong\s+hinh\s+dang|lines\s+plan|bang\s+tri\s+toa\s+do|duong\s+nuoc)\b"),
        ("GENERAL_ARRANGEMENT", 3, r"\b(?:khoang\s+hang|buong\s+may|vach\s+chong\s+va|engine\s+room|cargo\s+hold)\b"),
        ("GENERAL_ARRANGEMENT", 2, r"\b(?:bo\s+tri\s+chung|general\s+arrangement|buong\s+lai|lau\s+lai|fore\s+peak|aft\s+peak|hatch)\b"),
        ("MIDSHIP_STRUCTURAL", 4, r"\b(?:mat\s+cat\s+ngang|midship\s+section)\b"),
        ("MIDSHIP_STRUCTURAL", 3, r"\b(?:day\s+doi|da\s+ngang\s+dac|double\s+bottom|ton\s+man|ton\s+day|ton\s+boong)\b"),
        ("MIDSHIP_STRUCTURAL", 2, r"\b(?:[lt]\d+x\d+(?:x\d+)?)\b"),
        ("MIDSHIP_STRUCTURAL", 1, r"\b(?:suon\s+giua)\b"),
        ("BASIC_STRUCTURAL", 4, r"\b(?:ket\s+cau\s+co\s+ban|basic\s+structural|khai\s+trien\s+ton\s+vo|shell\s+expansion)\b"),
        ("BASIC_STRUCTURAL", 3, r"\b(?:so\s+do\s+ket\s+cau|profile\s+and\s+decks|ket\s+cau\s+doc)\b"),
    )
    for dtype, weight, pattern in rules:
        matches = re.findall(pattern, corpus)
        if matches:
            scores[dtype] += weight * min(len(matches), 3)
            hits[dtype].extend(str(m) for m in matches[:4])

    spline_count = int(obs.get("entity_counts", {}).get("SPLINE", 0) or 0)
    if spline_count >= 15:
        scores["LINES_PLAN"] += 4
        hits["LINES_PLAN"].append(f"SPLINE:{spline_count}")

    return scores, hits


def _classify_observation(obs: Mapping[str, Any]) -> dict[str, Any]:
    scores, hits = _score_drawing_content(obs)
    best_type, best_score = max(scores.items(), key=lambda kv: kv[1])
    predicted = best_type if best_score > 0 else "UNKNOWN"
    title_declared = _detect_title_declared_type(obs)
    mismatch = (
        predicted != "UNKNOWN"
        and title_declared is not None
        and title_declared != predicted
    )
    confidence = "HIGH" if best_score >= 6 else ("MEDIUM" if best_score >= 2 else "LOW")
    return {
        "drawing_id": obs["drawing_id"],
        "drawing_code": obs.get("drawing_code", ""),
        "predicted_drawing_type": predicted,
        "title_declared_type": title_declared,
        "title_content_mismatch": mismatch,
        "confidence": confidence,
        "evidence_scores": scores,
        "matched_tokens": {k: v for k, v in hits.items() if v},
    }


def classify_marine_drawing(
    observation: Mapping[str, Any],
    *,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """Skill 1: Classify marine drawing type and detect title-block vs content mismatch."""
    skill_id = "SKILL_1_DRAWING_CLASSIFIER"
    if not is_marine_pack_enabled(enabled):
        return _disabled_result(skill_id, "Marine Knowledge Pack disabled; classification skipped.")

    pack, rules_by_id = _pack_context()
    obs = normalize_observation(observation)
    cls = _classify_observation(obs)

    findings: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    non_marine_hits = list(obs["particulars"].get("non_marine_domain_hits", []))
    total_marine_score = sum(cls["evidence_scores"].values())
    observed_scope: dict[str, Any] = {
        **cls,
        "detected_service_areas": list(obs["particulars"]["service_areas"]),
        "detected_class_notations": list(obs["particulars"]["class_notations"]),
        "cad_geometry_verified": False,
    }
    if non_marine_hits and total_marine_score == 0 and not obs["particulars"]["class_notations"]:
        status = "NOT_APPLICABLE"
        observed_scope["observed_domain"] = "NON_MARINE_OUT_OF_DOMAIN"
        observed_scope["non_marine_domain_hits"] = non_marine_hits
        summary = (
            f"Drawing {obs['drawing_id']} contains non-marine mechanical/automotive markers "
            f"({', '.join(non_marine_hits[:4])}); Marine Knowledge Pack is NOT_APPLICABLE."
        )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_NON_MARINE_DOMAIN",
                verdict="NOT_APPLICABLE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={"drawing_id": obs["drawing_id"], "non_marine_domain_hits": non_marine_hits},
                reason=summary,
            )
        )
    elif cls["predicted_drawing_type"] == "UNKNOWN":
        status = "INSUFFICIENT_EVIDENCE"
        summary = f"Could not classify marine drawing {obs['drawing_id']}: insufficient recognizable marine tokens."
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_CLASSIFY_UNKNOWN",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={"drawing_id": obs["drawing_id"], "scores": cls["evidence_scores"]},
                reason="No dominant marine sheet markers (LINES_PLAN/GA/MCN/KCCB) were observed.",
                confidence="LOW",
            )
        )
    elif cls["title_content_mismatch"]:
        status = "CONFLICT"
        summary = (
            f"Drawing {obs['drawing_id']} content classifies as {cls['predicted_drawing_type']} "
            f"but title/code declares {cls['title_declared_type']}."
        )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_TITLE_CONTENT_MISMATCH",
                verdict="CONFLICT",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={
                    "drawing_id": obs["drawing_id"],
                    "drawing_code": obs.get("drawing_code", ""),
                    "predicted_drawing_type": cls["predicted_drawing_type"],
                    "title_declared_type": cls["title_declared_type"],
                    "matched_tokens": cls["matched_tokens"],
                },
                reason=summary,
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=obs["drawing_id"],
                action_kind="FIX_TITLE_BLOCK_TYPE_MISMATCH",
                evidence={
                    "predicted_drawing_type": cls["predicted_drawing_type"],
                    "title_declared_type": cls["title_declared_type"],
                },
                reason="Propose reconciling title-block sheet name/code with actual hull lines/arrangement content.",
            )
        )
    else:
        status = "PASS"
        summary = f"Classified drawing {obs['drawing_id']} as {cls['predicted_drawing_type']} without title mismatch."
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_CLASSIFY_MATCH",
                verdict="PASS",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={
                    "drawing_id": obs["drawing_id"],
                    "predicted_drawing_type": cls["predicted_drawing_type"],
                    "title_declared_type": cls["title_declared_type"],
                    "matched_tokens": cls["matched_tokens"],
                },
                reason=summary,
                confidence=cls["confidence"],
            )
        )

    incomplete_fields = _incomplete_observation_fields(obs)
    if incomplete_fields:
        status = "INSUFFICIENT_EVIDENCE"
        summary = (
            f"Classification of {obs['drawing_id']} is incomplete because some CAD entities could not be read."
        )
        observed_scope["observation_complete"] = False
        findings = [
            _make_finding(
                rules_by_id,
                finding_id=f"F_CLASSIFICATION_INCOMPLETE_{obs['drawing_id']}",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={"drawing_id": obs["drawing_id"], "incomplete_observation_fields": incomplete_fields},
                reason="Skipped or unresolved CAD entities may change the drawing classification.",
            )
        ]
        proposals = []

    return validate_check_result(
        {
            "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
            "skill_id": skill_id,
            "pack_id": pack["id"],
            "pack_sha256": pack["pack_sha256"],
            "pack_status": pack["status"],
            "cad_mutation": False,
            "regulatory_compliance_proven": False,
            "status": status,
            "summary": summary,
            "observed_scope": observed_scope,
            "applicable_regulation_scope": {
                "checked": False,
                "service_areas": list(obs["particulars"]["service_areas"]),
                "class_notations": list(obs["particulars"]["class_notations"]),
            },
            "partial_package": True,
            "findings": findings,
            "checks_executed": ["Marine drawing type classification", "Title block vs content coherence"],
            "checks_not_executed": [
                "Cross-drawing principal particulars reconciliation",
                "QCVN 72 structural rule compliance",
            ],
            "limitations": [
                "Classification uses observed CAD text/entity markers only; never proves regulatory compliance.",
            ],
            "proposal_only_actions": proposals,
        }
    )


def _aggregate_package_scope(obs_list: list[dict[str, Any]]) -> dict[str, Any]:
    service_areas: list[str] = []
    class_notations: list[str] = []
    explicit_exclusions: list[str] = []
    design_l_values: list[float] = []
    lpp_values: list[float] = []
    lwl_values: list[float] = []
    breadth_values: list[float] = []
    depth_values: list[float] = []
    draft_values: list[float] = []
    hull_nos: list[str] = []
    ship_types: list[str] = []
    hull_materials: list[str] = []
    corrupted_tokens: list[str] = []
    unverified_unitless: list[str] = []
    non_marine_hits: list[str] = []
    main_engine_hp_values: list[float] = []
    passenger_count_values: list[int] = []
    double_hull_or_double_side = False
    single_side_or_non_double_hull = False
    is_container_ship = False
    non_container_ship = False
    explicit_2_4_6_9_applicable = False
    drawing_types: dict[str, str] = {}
    obs_drawing_types: list[str] = []
    seen_types_by_id: dict[str, set[str]] = {}
    marine_score = 0

    for obs in obs_list:
        cls = _classify_observation(obs)
        pred_type = cls["predicted_drawing_type"]
        did = obs["drawing_id"]
        obs_drawing_types.append(pred_type)
        drawing_types[did] = pred_type
        seen_types_by_id.setdefault(did, set()).add(pred_type)
        marine_score += sum(cls["evidence_scores"].values())
        part = obs["particulars"]
        for val in part["service_areas"]:
            if val not in service_areas:
                service_areas.append(val)
        for val in part["class_notations"]:
            if val not in class_notations:
                class_notations.append(val)
        for val in part.get("explicit_exclusion_evidences", []):
            if val not in explicit_exclusions:
                explicit_exclusions.append(val)
        design_l_values.extend(part.get("design_length_l_m_values", []))
        lpp_values.extend(part["lpp_m_values"])
        lwl_values.extend(part.get("lwl_m_values", []))
        breadth_values.extend(part["breadth_m_values"])
        depth_values.extend(part["depth_m_values"])
        draft_values.extend(part["draft_m_values"])
        main_engine_hp_values.extend(part.get("main_engine_hp_values", []))
        passenger_count_values.extend(part.get("passenger_count_values", []))
        if part.get("double_hull_or_double_side"):
            double_hull_or_double_side = True
        if part.get("single_side_or_non_double_hull"):
            single_side_or_non_double_hull = True
        if part.get("is_container_ship"):
            is_container_ship = True
        if part.get("non_container_ship"):
            non_container_ship = True
        if part.get("explicit_2_4_6_9_applicable"):
            explicit_2_4_6_9_applicable = True
        for val in part.get("hull_nos", []):
            if val not in hull_nos:
                hull_nos.append(val)
        for val in part["ship_types"]:
            if val not in ship_types:
                ship_types.append(val)
        for val in part.get("hull_materials", []):
            if val not in hull_materials:
                hull_materials.append(val)
        for val in part.get("corrupted_numeric_tokens", []):
            if val not in corrupted_tokens:
                corrupted_tokens.append(val)
        for val in part.get("unverified_unitless_particulars", []):
            if val not in unverified_unitless:
                unverified_unitless.append(val)
        for val in part.get("non_marine_domain_hits", []):
            if val not in non_marine_hits:
                non_marine_hits.append(val)

    duplicate_drawing_id_conflicts = sorted(
        did
        for did, types in seen_types_by_id.items()
        if did != "UNSPECIFIED_DRAWING" and len(types) > 1
    )

    return {
        "drawing_types_by_id": drawing_types,
        "obs_drawing_types": obs_drawing_types,
        "duplicate_drawing_id_type_conflicts": duplicate_drawing_id_conflicts,
        "observed_types": sorted(set(obs_drawing_types)),
        "service_areas": service_areas,
        "class_notations": class_notations,
        "explicit_exclusion_evidences": explicit_exclusions,
        "design_length_l_m": design_l_values[0] if design_l_values else None,
        "design_length_l_m_all": sorted(set(design_l_values)),
        "lpp_m": lpp_values[0] if lpp_values else None,
        "lpp_m_all": sorted(set(lpp_values)),
        "lwl_m_all": sorted(set(lwl_values)),
        "breadth_m_all": sorted(set(breadth_values)),
        "depth_m_all": sorted(set(depth_values)),
        "draft_m_all": sorted(set(draft_values)),
        "hull_nos": hull_nos,
        "ship_types": ship_types,
        "hull_materials": hull_materials,
        "corrupted_numeric_tokens": corrupted_tokens,
        "unverified_unitless_particulars": unverified_unitless,
        "non_marine_domain_hits": non_marine_hits,
        "main_engine_hp_values": sorted(set(main_engine_hp_values)),
        "passenger_count_values": sorted(set(passenger_count_values)),
        "double_hull_or_double_side": double_hull_or_double_side,
        "single_side_or_non_double_hull": single_side_or_non_double_hull,
        "is_container_ship": is_container_ship,
        "non_container_ship": non_container_ship,
        "explicit_2_4_6_9_applicable": explicit_2_4_6_9_applicable,
        "marine_evidence_score": marine_score,
        "cad_geometry_verified": False,
    }


_UPCOMING_AMENDMENT_NOTICE = (
    "Sua doi 1:2026 QCVN 72:2025/BGTVT (Circular 78/2026/TT-BXD, effective 2027-05-01)"
)

_CLAUSE_1_1_1_MAP: dict[str, str] = {
    "STATUTORY_QCVN_21_SEA_SHIP": "QCVN 21:2025/BGTVT",
    "STATUTORY_SEA_CLASS_NOTATION": "QCVN 21:2025/BGTVT",
    "STATUTORY_CLAUSE_1_1_1_QCVN_25_SMALL_CRAFT": "QCVN 25:2015/BGTVT",
    "STATUTORY_CLAUSE_1_1_1_EXCLUSION": "QCVN 21:2025/BGTVT",
}

_CURRENT_REFERRAL_META: dict[str, tuple[str, str | None, str | None]] = {
    "STATUTORY_QCVN_21_SEA_SHIP": (
        "QCVN 21:2025/BGTVT",
        "QCVN 21:2015/BGTVT",
        "Circular 09/2025/TT-BGTVT (effective 2025-09-01)",
    ),
    "STATUTORY_SEA_CLASS_NOTATION": (
        "QCVN 21:2025/BGTVT",
        "QCVN 21:2015/BGTVT",
        "Circular 09/2025/TT-BGTVT (effective 2025-09-01)",
    ),
    "STATUTORY_CLAUSE_1_1_1_EXCLUSION": (
        "QCVN 21:2025/BGTVT",
        "QCVN 21:2015/BGTVT",
        "Circular 09/2025/TT-BGTVT (effective 2025-09-01)",
    ),
    "STATUTORY_CLAUSE_1_1_1_QCVN_25_SMALL_CRAFT": (
        "QCVN 25:2015/BGTVT",
        None,
        None,
    ),
    "STATUTORY_CLAUSE_1_1_2_QCVN_50_LEISURE": ("QCVN 50:2012/BGTVT", None, None),
    "STATUTORY_CLAUSE_1_1_2_QCVN_51_FERROCEMENT": ("QCVN 51:2013/BGTVT", None, None),
    "STATUTORY_CLAUSE_1_1_2_QCVN_56_FRP": ("QCVN 56:2013/BGTVT", None, None),
    "STATUTORY_QCVN_56_FRP_CRAFT": ("QCVN 56:2013/BGTVT", None, None),
    "STATUTORY_CLAUSE_1_1_2_QCVN_84_WOOD": ("QCVN 84:2014/BGTVT", None, None),
    "STATUTORY_QCVN_84_WOODEN_CRAFT": ("QCVN 84:2014/BGTVT", None, None),
    "STATUTORY_CLAUSE_1_1_2_QCVN_54_HSC": (
        "QCVN 127:2025/BGTVT",
        "QCVN 54:2013/BGTVT",
        "Circular 06/2025/TT-BGTVT (effective 2025-09-01)",
    ),
    "STATUTORY_CLAUSE_1_1_2_QCVN_55_DOCK": ("QCVN 55:2013/BGTVT", None, None),
}

_CLAUSE_1_1_2_MAP: dict[str, str] = {
    "STATUTORY_CLAUSE_1_1_2_QCVN_50_LEISURE": "QCVN 50:2012/BGTVT",
    "STATUTORY_CLAUSE_1_1_2_QCVN_51_FERROCEMENT": "QCVN 51:2013/BGTVT",
    "STATUTORY_CLAUSE_1_1_2_QCVN_56_FRP": "QCVN 56:2013/BGTVT",
    "STATUTORY_QCVN_56_FRP_CRAFT": "QCVN 56:2013/BGTVT",
    "STATUTORY_CLAUSE_1_1_2_QCVN_84_WOOD": "QCVN 84:2014/BGTVT",
    "STATUTORY_QCVN_84_WOODEN_CRAFT": "QCVN 84:2014/BGTVT",
    "STATUTORY_CLAUSE_1_1_2_QCVN_54_HSC": "QCVN 127:2025/BGTVT",
    "STATUTORY_CLAUSE_1_1_2_QCVN_55_DOCK": "QCVN 55:2013/BGTVT",
}

_CLAUSE_1_1_4_TAGS: frozenset[str] = frozenset(
    {
        "STATUTORY_CLAUSE_1_1_4_DEFENSE_SECURITY",
        "STATUTORY_CLAUSE_1_1_4_FISHING_VESSEL",
    }
)


def _classify_exclusion_basis(
    explicit_exclusions: Sequence[str],
    *,
    length_excluded: bool,
) -> dict[str, Any] | None:
    """Return structured exclusion details separating historical citations from current successors."""
    tags_111 = [t for t in explicit_exclusions if t in _CLAUSE_1_1_1_MAP]
    if length_excluded or tags_111:
        if tags_111:
            detected = tags_111[0]
            referred, historical, circular = _CURRENT_REFERRAL_META.get(
                detected, (_CLAUSE_1_1_1_MAP[detected], None, None)
            )
        else:
            # Proven L > 140 m alone never infers sea-going steel QCVN 21 without case/vessel evidence.
            detected = "L_GT_140M"
            referred, historical, circular = None, None, None
        return {
            "clause_basis": "1.1.1",
            "finding_id": "F_SCOPE_OUT_OF_QCVN72",
            "detected_scope": detected,
            "referred_regulation": referred,
            "historical_cited_regulation": historical,
            "successor_circular": circular,
        }
    tags_112 = [t for t in explicit_exclusions if t in _CLAUSE_1_1_2_MAP]
    if tags_112:
        detected = tags_112[0]
        referred, historical, circular = _CURRENT_REFERRAL_META.get(
            detected, (_CLAUSE_1_1_2_MAP[detected], None, None)
        )
        return {
            "clause_basis": "1.1.2",
            "finding_id": "F_SCOPE_SPECIAL_REGULATION_CLAUSE_1_1_2",
            "detected_scope": detected,
            "referred_regulation": referred,
            "historical_cited_regulation": historical,
            "successor_circular": circular,
        }
    tags_114 = [t for t in explicit_exclusions if t in _CLAUSE_1_1_4_TAGS]
    if tags_114:
        return {
            "clause_basis": "1.1.4",
            "finding_id": "F_SCOPE_NON_MANDATORY_CLAUSE_1_1_4",
            "detected_scope": tags_114[0],
            "referred_regulation": None,
            "historical_cited_regulation": None,
            "successor_circular": None,
        }
    if explicit_exclusions:
        return {
            "clause_basis": "1.1.1",
            "finding_id": "F_SCOPE_OUT_OF_QCVN72",
            "detected_scope": explicit_exclusions[0],
            "referred_regulation": None,
            "historical_cited_regulation": None,
            "successor_circular": None,
        }
    return None


def _required_inland_bulkheads(lpp_m: float) -> int | None:
    if lpp_m < 20.0:
        return 2
    if lpp_m == 20.0:
        return None
    if lpp_m <= 40.0:
        return 3
    if lpp_m <= 60.0:
        return 4
    if lpp_m <= 80.0:
        return 5
    return 6


def _is_valid_finite_metric(key: str, raw_val: object) -> tuple[bool, float | None]:
    if isinstance(raw_val, bool) or not isinstance(raw_val, (int, float)):
        return False, None
    val = float(raw_val)
    if not math.isfinite(val):
        return False, None
    if key == "transverse_watertight_bulkhead_count":
        if val < 0.0 or not val.is_integer():
            return False, None
        return True, val
    if val <= 0.0:
        return False, None
    return True, val


def _extract_strict_metric(
    obs_list: list[dict[str, Any]],
    key: str,
    *,
    allowed_types: tuple[str, ...],
    obs_drawing_types: Sequence[str],
) -> tuple[list[tuple[str, float, dict[str, Any]]], list[str], list[str], list[str]]:
    eligible: list[tuple[str, float, dict[str, Any]]] = []
    wrong_sheet_ids: list[str] = []
    untrusted_prov_ids: list[str] = []
    invalid_issues: list[str] = []
    for idx, obs in enumerate(obs_list):
        did = obs["drawing_id"]
        metrics = obs.get("structural_metrics", {})
        if key not in metrics or metrics[key] is None:
            continue
        raw_val = metrics[key]
        valid, val = _is_valid_finite_metric(key, raw_val)
        if not valid or val is None:
            invalid_issues.append(f"{did}:{key}={raw_val!r}")
            continue
        prov = str(obs.get("metric_provenance", {}).get(key, "")).strip()
        if obs.get("ocr_only") or prov not in _VERIFIED_PROVENANCES:
            untrusted_prov_ids.append(did)
        sheet_type = obs_drawing_types[idx] if idx < len(obs_drawing_types) else "UNKNOWN"
        if sheet_type in allowed_types:
            eligible.append((did, val, obs))
        else:
            wrong_sheet_ids.append(did)
    return eligible, wrong_sheet_ids, untrusted_prov_ids, invalid_issues


def _has_implausible_particulars(scope: Mapping[str, Any], obs_list: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    for val in scope.get("design_length_l_m_all", []) + scope.get("lpp_m_all", []) + scope.get("lwl_m_all", []):
        if not isinstance(val, (int, float)) or not math.isfinite(float(val)) or val > 500.0 or val <= 0.0:
            issues.append(f"length_m={val}")
    for val in scope.get("breadth_m_all", []):
        if not isinstance(val, (int, float)) or not math.isfinite(float(val)) or val > 100.0 or val <= 0.0:
            issues.append(f"breadth_m={val}")
    for val in scope.get("depth_m_all", []):
        if not isinstance(val, (int, float)) or not math.isfinite(float(val)) or val > 60.0 or val <= 0.0:
            issues.append(f"depth_m={val}")
    depth_vals = [float(v) for v in scope.get("depth_m_all", []) if math.isfinite(float(v))]
    draft_vals = [float(v) for v in scope.get("draft_m_all", []) if math.isfinite(float(v))]
    if depth_vals and draft_vals and min(draft_vals) > max(depth_vals) + 0.05:
        issues.append(f"draft_m={min(draft_vals)}_gt_depth_m={max(depth_vals)}")

    # Clause 1.4.43-1 consistency: 0.96 * Lwl <= L <= Lwl when both declared
    design_ls = scope.get("design_length_l_m_all", [])
    lwls = scope.get("lwl_m_all", [])
    for lv in design_ls:
        for lwlv in lwls:
            if lv < (0.96 * lwlv - 0.02) or lv > (lwlv + 0.02):
                issues.append(f"L={lv}_violates_1_4_43_1_range_0.96_to_1.0_Lwl={lwlv}")

    for obs in obs_list:
        did = obs["drawing_id"]
        metrics = obs.get("structural_metrics", {})
        for k, mv in metrics.items():
            if mv is None:
                continue
            if k == "floor_spacing_measurements":
                if not isinstance(mv, list):
                    issues.append(f"{did}:{k}={mv!r}")
                else:
                    for item in mv:
                        if not isinstance(item, Mapping):
                            issues.append(f"{did}:{k}={item!r}")
                            continue
                        valid_sp, sp_val = _is_valid_finite_metric("transverse_floor_max_spacing_mm", item.get("spacing_mm"))
                        if not valid_sp or sp_val is None or sp_val > 20000.0:
                            issues.append(f"{did}:{k}={item!r}")
                continue
            if k in _NON_DIM_METRIC_KEYS:
                continue
            valid, fval = _is_valid_finite_metric(k, mv)
            if not valid or fval is None:
                issues.append(f"{did}:{k}={mv!r}")
                continue
            if k in {"double_bottom_height_mm", "bottom_girder_max_spacing_mm", "transverse_floor_max_spacing_mm", "body_plan_wl_span_mm"} and fval > 20000.0:
                issues.append(f"{did}:{k}={mv!r}")
            elif "plate" in k and fval > 150.0:
                issues.append(f"{did}:{k}={mv!r}")
    return issues


def _collect_untrusted_dependency_provenances(obs_list: list[dict[str, Any]]) -> list[str]:
    flagged: list[str] = []
    dep_keys_to_part = (
        ("design_length_l_m", "design_length_l_m_values"),
        ("lwl_m", "lwl_m_values"),
        ("lpp_m", "lpp_m_values"),
        ("ship_type", "ship_types"),
        ("hull_material", "hull_materials"),
    )
    for obs in obs_list:
        did = obs["drawing_id"]
        part = obs["particulars"]
        mprov = obs.get("metric_provenance", {})
        for pkey, list_key in dep_keys_to_part:
            has_val = bool(part.get(list_key))
            if not has_val and pkey not in mprov:
                continue
            prov = str(mprov.get(pkey, "")).strip()
            if prov and (obs.get("ocr_only") or prov not in _VERIFIED_PROVENANCES):
                flagged.append(f"{did}:{pkey}={prov}")
            elif has_val and pkey in mprov and prov not in _VERIFIED_PROVENANCES:
                flagged.append(f"{did}:{pkey}={prov}")
    return flagged


def _cross_package_conflicts(cross: Mapping[str, Mapping[str, list[str]]]) -> dict[str, Any]:
    conflicts: dict[str, Any] = {}
    if len(cross["engines"]) > 1:
        conflicts["main_engines"] = dict(cross["engines"])
    if len(cross["service_areas"]) > 1:
        conflicts["service_areas"] = dict(cross["service_areas"])
    if len(cross["class_notations"]) > 1:
        conflicts["class_notations"] = dict(cross["class_notations"])
    if len(cross["ship_types"]) > 1:
        conflicts["ship_types"] = dict(cross["ship_types"])
    if len(cross["hull_materials"]) > 1:
        conflicts["hull_materials"] = dict(cross["hull_materials"])
    if len(cross["hull_nos"]) > 1:
        conflicts["hull_nos"] = dict(cross["hull_nos"])
    for key, label, tol in (
        ("design_length_l_m", "L", 0.05),
        ("lpp_m", "Lpp", 0.05),
        ("lwl_m", "Lwl", 0.05),
        ("breadth_m", "B", 0.05),
        ("depth_m", "D", 0.05),
        ("draft_m", "T", 0.05),
        ("double_bottom_height_mm", "double_bottom_height_mm", 10.0),
        ("transverse_watertight_bulkhead_count", "transverse_watertight_bulkhead_count", 0.5),
    ):
        buckets = cross.get(key, {})
        nums = sorted(float(k) for k in buckets)
        if len(nums) > 1 and (max(nums) - min(nums)) > tol:
            conflicts[label] = dict(buckets)
    return conflicts


def evaluate_regulation_applicability_and_submittal(
    observations: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    target_regulation: str = "QCVN_72_2025_BGTVT",
    expected_source_sha256: str | None = None,
    partial_package: bool = True,
    verified_scale_to_mm: float | None = None,
    calibration_verified: bool = False,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """Skill 2: Evaluate QCVN 72 applicability scope, submittal completeness, and conditional structural checks."""
    skill_id = "SKILL_2_REGULATION_AND_SUBMITTAL"
    if not is_marine_pack_enabled(enabled):
        return _disabled_result(skill_id, "Marine Knowledge Pack disabled; regulation check skipped.")

    scale_mm = _validate_scale_arg(verified_scale_to_mm)
    pack, rules_by_id = _pack_context()
    obs_list = _to_obs_list(observations)
    incomplete_observations = {
        obs["drawing_id"]: _incomplete_observation_fields(obs)
        for obs in obs_list
        if _incomplete_observation_fields(obs)
    }
    if incomplete_observations:
        summary = "Marine scope and structural evaluation are incomplete because CAD traversal skipped or could not transform entities."
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "summary": summary,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "observation_complete": False,
                    "incomplete_observations": incomplete_observations,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "supported_regulation": target_regulation in SUPPORTED_REGULATIONS,
                    "in_scope": None,
                    "upcoming_amendment": _UPCOMING_AMENDMENT_NOTICE,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_INCOMPLETE_CAD_TRAVERSAL",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                        evidence={"incomplete_observations": incomplete_observations},
                        reason="Unsupported or unread CAD entities may conceal Marine scope and structural evidence.",
                    )
                ],
                "checks_executed": [],
                "checks_not_executed": ["QCVN 72 scope and structural evaluation (incomplete CAD traversal)"],
                "limitations": ["Unsupported INSERT/text transforms or carriers may hide source annotations."],
                "proposal_only_actions": [],
            }
        )
    if target_regulation not in SUPPORTED_REGULATIONS:
        unsupported_reason = (
            f"Unsupported regulation version {target_regulation!r}; "
            f"Marine Knowledge Pack V0 supports only {sorted(SUPPORTED_REGULATIONS)}."
        )
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "summary": unsupported_reason,
                "observed_scope": {"drawing_count": len(obs_list)},
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "supported_regulation": False,
                    "supported_regulations": sorted(SUPPORTED_REGULATIONS),
                    "in_scope": None,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_UNSUPPORTED_REGULATION_VERSION",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_01_QCVN72_SCOPE",
                        evidence={
                            "target_regulation": target_regulation,
                            "supported_regulations": sorted(SUPPORTED_REGULATIONS),
                        },
                        reason=unsupported_reason,
                    )
                ],
                "checks_executed": ["Regulation version support check"],
                "checks_not_executed": [f"Checks under unsupported regulation {target_regulation}"],
                "limitations": [unsupported_reason],
                "proposal_only_actions": [],
            }
        )

    if expected_source_sha256 is not None:
        indexed_sha = _SOURCES_BY_ID[target_regulation]["sha256"]
        if expected_source_sha256.strip().lower() != indexed_sha:
            stale_reason = (
                f"Stale or mismatched source SHA-256 for {target_regulation}: "
                f"caller expected {expected_source_sha256!r} vs manifest {indexed_sha!r}; "
                "uploaded vs local QCVN PDF cannot be assumed to share identical pagination."
            )
            return validate_check_result(
                {
                    "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                    "skill_id": skill_id,
                    "pack_id": pack["id"],
                    "pack_sha256": pack["pack_sha256"],
                    "pack_status": pack["status"],
                    "cad_mutation": False,
                    "regulatory_compliance_proven": False,
                    "status": "INSUFFICIENT_EVIDENCE",
                    "summary": stale_reason,
                    "observed_scope": {"drawing_count": len(obs_list)},
                    "applicable_regulation_scope": {
                        "target_regulation": target_regulation,
                        "supported_regulation": True,
                        "in_scope": None,
                        "source_sha256_verified": False,
                    },
                    "partial_package": bool(partial_package),
                    "findings": [
                        _make_finding(
                            rules_by_id,
                            finding_id="F_STALE_OR_MISMATCHED_SOURCE_SHA256",
                            verdict="INSUFFICIENT_EVIDENCE",
                            rule_id="RULE_MK_01_QCVN72_SCOPE",
                            evidence={
                                "expected_source_sha256": expected_source_sha256,
                                "manifest_sha256": indexed_sha,
                            },
                            reason=stale_reason,
                        )
                    ],
                    "checks_executed": ["Source manifest SHA-256 verification"],
                    "checks_not_executed": ["All regulation checks blocked by mismatched/stale PDF hash"],
                    "limitations": [stale_reason],
                    "proposal_only_actions": [],
                }
            )

    if not obs_list:
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "summary": "No marine drawing observations provided.",
                "observed_scope": {"drawing_count": 0},
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "supported_regulation": True,
                    "in_scope": None,
                },
                "partial_package": bool(partial_package),
                "findings": [],
                "checks_executed": [],
                "checks_not_executed": ["All QCVN 72 applicability and structural checks"],
                "limitations": ["No drawings supplied."],
                "proposal_only_actions": [],
            }
        )

    scope = _aggregate_package_scope(obs_list)
    service_areas = scope["service_areas"]
    explicit_exclusions = scope["explicit_exclusion_evidences"]
    design_l_all = scope["design_length_l_m_all"]
    lpp_m = scope["lpp_m"]
    lpp_all = scope["lpp_m_all"]
    class_notations = scope["class_notations"]
    findings: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    checks_executed: list[str] = ["Regulatory applicability scope gate (QCVN 72 1.1.1 / 3.2.1)"]
    checks_not_executed: list[str] = []
    limitations: list[str] = [
        "Per RULE_MK_02_NO_SINGLE_CHECK_CERTIFICATION, regulatory_compliance_proven remains False.",
    ]

    if (
        scope["non_marine_domain_hits"]
        and scope["marine_evidence_score"] < 2
        and not class_notations
        and "INLAND_WATERWAY" not in service_areas
    ):
        non_marine_reason = (
            f"Target regulation {target_regulation} is NOT_APPLICABLE: supplied drawings show non-marine "
            f"domain markers ({', '.join(scope['non_marine_domain_hits'][:4])})."
        )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_NON_MARINE_DOMAIN",
                verdict="NOT_APPLICABLE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={"non_marine_domain_hits": scope["non_marine_domain_hits"]},
                reason=non_marine_reason,
            )
        )
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": "NOT_APPLICABLE",
                "summary": non_marine_reason,
                "observed_scope": scope,
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "supported_regulation": True,
                    "in_scope": False,
                    "detected_scope": "NON_MARINE_OUT_OF_DOMAIN",
                    "referred_regulation": None,
                    "candidate_referred_regulation": None,
                },
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": checks_executed,
                "checks_not_executed": ["All QCVN 72 inland structural rules (non-marine domain)"],
                "limitations": limitations,
                "proposal_only_actions": proposals,
            }
        )

    cross_s2 = _collect_cross_sheet_values(obs_list, obs_drawing_types=scope["obs_drawing_types"])
    pkg_conflicts = _cross_package_conflicts(cross_s2)
    implausible_issues = _has_implausible_particulars(scope, obs_list)
    exclusions_111 = [t for t in explicit_exclusions if t in _CLAUSE_1_1_1_MAP]
    exclusions_112 = [t for t in explicit_exclusions if t in _CLAUSE_1_1_2_MAP]
    exclusions_114 = [t for t in explicit_exclusions if t in _CLAUSE_1_1_4_TAGS]
    hp_vals = scope["main_engine_hp_values"]
    pax_vals = scope["passenger_count_values"]
    exclusions_111_non_q25 = [t for t in exclusions_111 if t != "STATUTORY_CLAUSE_1_1_1_QCVN_25_SMALL_CRAFT"]
    q25_explicit = "STATUTORY_CLAUSE_1_1_1_QCVN_25_SMALL_CRAFT" in exclusions_111
    q25_conflict = q25_explicit and (
        "VR-SB" in class_notations
        or (bool(design_l_all) and min(design_l_all) >= 20.0 and bool(hp_vals) and min(hp_vals) >= 50.0)
    )

    # Input trustworthiness gates MUST precede definitive applicability / exclusion verdicts (MV0-01)
    has_ocr_only = any(obs["ocr_only"] for obs in obs_list)
    bad_geom_ids = [
        obs["drawing_id"]
        for obs in obs_list
        if obs.get("geometry_status") in {"MISSING", "CORRUPTED", "UNEDITABLE", "NO_GEOMETRY_PRIMITIVES"}
    ]
    corrupted_tokens = scope["corrupted_numeric_tokens"]
    unverified_unitless = scope["unverified_unitless_particulars"]
    unitless_ids = [
        o["drawing_id"] for o in obs_list if o["insunits"] not in _INSUNITS_TO_MM
    ]
    units_ok = (not unitless_ids) or (calibration_verified is True and scale_mm is not None)
    untrusted_deps = _collect_untrusted_dependency_provenances(obs_list)
    invalid_obs_metrics = [
        f"{obs['drawing_id']}:{item}"
        for obs in obs_list
        for item in obs.get("invalid_structural_metrics", [])
    ]
    incomplete_obs_ids = [o["drawing_id"] for o in obs_list if o.get("skipped_entities")]
    input_gates_blocked = bool(
        has_ocr_only
        or corrupted_tokens
        or unverified_unitless
        or bad_geom_ids
        or not units_ok
        or untrusted_deps
        or invalid_obs_metrics
        or incomplete_obs_ids
    )

    fatal_scope_conflict = (
        ("INLAND_WATERWAY" in service_areas and ("OCEAN_GOING" in service_areas or bool(exclusions_111_non_q25) or q25_conflict))
        or "class_notations" in pkg_conflicts
        or "ship_types" in pkg_conflicts
        or "hull_materials" in pkg_conflicts
        or "L" in pkg_conflicts
        or "Lpp" in pkg_conflicts
        or "Lwl" in pkg_conflicts
        or bool(implausible_issues)
    )
    if fatal_scope_conflict:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_SCOPE_CONFLICT",
                verdict="CONFLICT",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={
                    "service_areas": service_areas,
                    "class_notations": class_notations,
                    "explicit_exclusions": explicit_exclusions,
                    "package_conflicts": pkg_conflicts,
                    "implausible_issues": implausible_issues,
                },
                reason=(
                    "Conflicting scope, length declarations, or physically implausible dimensions "
                    "prevent QCVN 72 applicability resolution."
                ),
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=obs_list[0]["drawing_id"],
                action_kind="RECONCILE_SERVICE_AREA_SCOPE",
                evidence={"package_conflicts": pkg_conflicts, "implausible_issues": implausible_issues},
            )
        )
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": "CONFLICT",
                "summary": "Conflicting scope, vessel length, or implausible numbers prevents QCVN 72 determination.",
                "observed_scope": scope,
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "supported_regulation": True,
                    "in_scope": None,
                    "upcoming_amendment": _UPCOMING_AMENDMENT_NOTICE,
                },
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": checks_executed,
                "checks_not_executed": ["QCVN 72 structural rule compliance"],
                "limitations": limitations,
                "proposal_only_actions": proposals,
            }
        )

    if input_gates_blocked:
        if incomplete_obs_ids:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_INCOMPLETE_CAD_TRAVERSAL",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={
                        "drawing_ids": incomplete_obs_ids,
                        "skipped_entities": {
                            o["drawing_id"]: o["skipped_entities"] for o in obs_list if o.get("skipped_entities")
                        },
                    },
                    reason="Skipped or unresolved CAD entities can conceal scope or submittal evidence.",
                )
            )
        if untrusted_deps:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_UNTRUSTED_DEPENDENCY_PROVENANCE",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"untrusted_provenances": untrusted_deps},
                    reason=(
                        "Length, ship-type, or material dependencies carry untrusted/OCR provenance: "
                        f"{', '.join(untrusted_deps)}."
                    ),
                )
            )
        if invalid_obs_metrics:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_INVALID_STRUCTURAL_METRIC",
                    verdict="CONFLICT",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"invalid_structural_metrics": invalid_obs_metrics},
                    reason=f"Non-finite or invalid structural metrics detected: {', '.join(invalid_obs_metrics)}.",
                )
            )
        if has_ocr_only:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_OCR_ONLY_REJECTED",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"ocr_only_drawing_ids": [o["drawing_id"] for o in obs_list if o["ocr_only"]]},
                    reason="OCR-only inputs cannot establish verified QCVN 72 scope, exclusion, or PASS.",
                )
            )
        if corrupted_tokens:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_CORRUPTED_NUMERIC_TOKEN",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"corrupted_numeric_tokens": corrupted_tokens},
                    reason=f"Corrupted OCR/CAD numeric tokens detected: {', '.join(corrupted_tokens)}.",
                )
            )
        if unverified_unitless:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_UNVERIFIED_UNITLESS_PARTICULARS",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"unverified_unitless_particulars": unverified_unitless},
                    reason="Title-block principal particulars lack explicit m/mm/cm unit in an $INSUNITS=0 drawing.",
                )
            )
        if bad_geom_ids:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_CAD_GEOMETRY_MISSING",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"drawing_ids": bad_geom_ids},
                    reason=f"Drawing(s) {', '.join(bad_geom_ids)} lack verified CAD geometry entities.",
                )
            )
        if not units_ok:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_UNITS_UNVERIFIED",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={
                        "unitless_drawing_ids": unitless_ids,
                        "calibration_verified": calibration_verified is True,
                        "verified_scale_to_mm": scale_mm,
                    },
                    reason=(
                        "Unitless CAD ($INSUNITS=0) requires BOTH calibration_verified=True and valid "
                        "verified_scale_to_mm>0 before QCVN 72 scope confirmation or exclusion."
                    ),
                )
            )
            proposals.append(
                build_marine_core_proposal(
                    target_drawing_id=unitless_ids[0],
                    action_kind="SET_INSUNITS_AND_VERIFY_CALIBRATION",
                    evidence={"unitless_drawing_ids": unitless_ids},
                )
            )
        gate_verdicts = [f["verdict"] for f in findings]
        gate_overall = "CONFLICT" if "CONFLICT" in gate_verdicts else "INSUFFICIENT_EVIDENCE"
        candidate_ref = "QCVN 21:2025/BGTVT" if "OCEAN_GOING" in service_areas else None
        gate_summary = (
            f"Trust/calibration gate blocked definitive QCVN 72 verdict (status={gate_overall})."
            + (
                " Unverified OCEAN GOING label noted (candidate current referral: QCVN 21:2025/BGTVT, successor to QCVN 21:2015/BGTVT)."
                if candidate_ref
                else ""
            )
        )
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": gate_overall,
                "summary": gate_summary,
                "observed_scope": scope,
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "supported_regulation": True,
                    "in_scope": None,
                    "candidate_referred_regulation": candidate_ref,
                    "historical_cited_regulation": "QCVN 21:2015/BGTVT" if candidate_ref else None,
                    "upcoming_amendment": _UPCOMING_AMENDMENT_NOTICE,
                },
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": checks_executed + ["Input trustworthiness / CAD calibration gate"],
                "checks_not_executed": ["QCVN 72 applicability confirmation and structural checks blocked by trust gate"],
                "limitations": limitations,
                "proposal_only_actions": proposals,
            }
        )

    lwl_all = scope["lwl_m_all"]
    effective_l_m: float | None = None
    l_lo: float | None = None
    l_hi: float | None = None
    length_basis = "UNAVAILABLE"
    if design_l_all:
        l_lo = round(min(design_l_all), 4)
        l_hi = round(max(design_l_all), 4)
        effective_l_m = l_lo
        length_basis = "EXPLICIT_DESIGN_LENGTH_L"
    elif lwl_all:
        l_lo = round(0.96 * min(lwl_all), 4)
        l_hi = round(max(lwl_all), 4)
        effective_l_m = l_lo
        length_basis = "PROVEN_LWL_INTERVAL_1_4_43"
    elif lpp_all:
        length_basis = "UNPROVEN_LPP_ONLY_NO_REGULATORY_L"

    # Clause 1.4.43-1 bounds regulatory design length L strictly inside [0.96 * Lwl, Lwl].
    length_excluded = (bool(design_l_all) and min(design_l_all) > 140.0) or (
        not design_l_all and bool(lwl_all) and (0.96 * min(lwl_all)) > 140.0
    )

    if (
        exclusions_114
        and "INLAND_WATERWAY" in service_areas
        and not exclusions_111
        and not exclusions_112
        and not length_excluded
    ):
        mixed_114_reason = (
            f"Insufficient evidence under Clause 1.1.4 ({exclusions_114[0]}): defense, security, and fishing "
            "vessels are not mandatorily governed by QCVN 72:2025/BGTVT, yet inland waterway/class markers appear "
            "on the package; confirm whether voluntary QCVN 72 classification applies."
        )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_SCOPE_CLAUSE_1_1_4_VOLUNTARY_CONFIRMATION_REQUIRED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={
                    "clause_basis": "1.1.4",
                    "service_areas": service_areas,
                    "class_notations": class_notations,
                    "explicit_exclusion_evidences": exclusions_114,
                },
                reason=mixed_114_reason,
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=obs_list[0]["drawing_id"],
                action_kind="CONFIRM_REGULATORY_SERVICE_AREA",
                evidence={"clause_basis": "1.1.4", "explicit_exclusion_evidences": exclusions_114},
            )
        )
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "summary": mixed_114_reason,
                "observed_scope": scope,
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "supported_regulation": True,
                    "in_scope": None,
                    "clause_basis": "1.1.4",
                    "detected_scope": exclusions_114[0],
                    "referred_regulation": None,
                    "upcoming_amendment": _UPCOMING_AMENDMENT_NOTICE,
                },
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    "QCVN 72 structural rule compliance pending Clause 1.1.4 voluntary/non-mandatory confirmation",
                ],
                "limitations": limitations,
                "proposal_only_actions": proposals,
            }
        )

    excl_info = _classify_exclusion_basis(explicit_exclusions, length_excluded=length_excluded)
    if excl_info is not None:
        clause_basis = excl_info["clause_basis"]
        excl_finding_id = excl_info["finding_id"]
        detected = excl_info["detected_scope"]
        referred_reg = excl_info["referred_regulation"]
        historical_reg = excl_info["historical_cited_regulation"]
        successor_circ = excl_info["successor_circular"]
        if clause_basis == "1.1.1":
            hist_note = f" (historically cited as {historical_reg}; superseded by {successor_circ})" if historical_reg else ""
            out_reason = (
                f"Target regulation {target_regulation} is NOT_APPLICABLE under Clause 1.1.1 "
                f"({detected}, L={design_l_all or None}, Lwl={lwl_all or None}, Lpp={lpp_m}); "
                f"governing regulation={referred_reg}{hist_note}."
            )
        elif clause_basis == "1.1.2":
            hist_note = f" (historically cited as {historical_reg}; superseded by {successor_circ})" if historical_reg else ""
            out_reason = (
                f"Target regulation {target_regulation} structural rules are NOT_APPLICABLE under Clause 1.1.2 "
                f"({detected}); specialized replacement regulation={referred_reg}{hist_note}."
            )
        else:
            out_reason = (
                f"Target regulation {target_regulation} is NOT_APPLICABLE by default under Clause 1.1.4 "
                f"({detected}: defense, security, and fishing vessels are not mandatorily governed by QCVN 72)."
            )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id=excl_finding_id,
                verdict="NOT_APPLICABLE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={
                    "clause_basis": clause_basis,
                    "service_areas": service_areas,
                    "explicit_exclusion_evidences": explicit_exclusions,
                    "design_length_l_m_all": design_l_all,
                    "lwl_m_all": lwl_all,
                    "lpp_m": lpp_m,
                    "referred_regulation": referred_reg,
                    "historical_cited_regulation": historical_reg,
                    "successor_circular": successor_circ,
                },
                reason=out_reason,
            )
        )
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": "NOT_APPLICABLE",
                "summary": out_reason,
                "observed_scope": scope,
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "supported_regulation": True,
                    "in_scope": False,
                    "clause_basis": clause_basis,
                    "detected_scope": detected,
                    "referred_regulation": referred_reg,
                    "historical_cited_regulation": historical_reg,
                    "successor_circular": successor_circ,
                    "upcoming_amendment": _UPCOMING_AMENDMENT_NOTICE,
                },
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": checks_executed,
                "checks_not_executed": [f"All QCVN 72 inland structural rules (excluded per Clause {clause_basis})"],
                "limitations": limitations,
                "proposal_only_actions": proposals,
            }
        )

    if "INLAND_WATERWAY" not in service_areas:
        if "OCEAN_GOING" in service_areas:
            reason = (
                "Insufficient evidence for a legal QCVN 72 applicability verdict: drawing shows bare free-text "
                "'OCEAN GOING' label without explicit Class/VR/VRH/QCVN 21/SOLAS statutory notation; missing "
                "QCVN or VR notation is not proof of non-applicability (candidate current referral: QCVN 21:2025/BGTVT, "
                "Circular 09/2025/TT-BGTVT replacing historical QCVN 21:2015/BGTVT)."
            )
            detected_scope = "UNVERIFIED_OCEAN_GOING_LABEL"
        else:
            reason = (
                "Insufficient evidence to confirm QCVN 72:2025/BGTVT scope: unknown vessel classification "
                "(no VR-SB/SI/SII/SIII, QCVN 72, QCVN 21, or statutory exclusion declared; missing QCVN or VR "
                "notation is not proof of non-applicability)."
            )
            detected_scope = "UNKNOWN_CLASSIFICATION"
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_SCOPE_UNVERIFIED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={
                    "service_areas": service_areas,
                    "class_notations": class_notations,
                    "explicit_exclusion_evidences": explicit_exclusions,
                },
                reason=reason,
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=obs_list[0]["drawing_id"],
                action_kind="CONFIRM_REGULATORY_SERVICE_AREA",
                evidence={"observed_service_areas": service_areas, "detected_scope": detected_scope},
            )
        )
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "summary": reason,
                "observed_scope": scope,
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "supported_regulation": True,
                    "in_scope": None,
                    "detected_scope": detected_scope,
                    "candidate_referred_regulation": (
                        "QCVN 21:2025/BGTVT" if "OCEAN_GOING" in service_areas else None
                    ),
                    "historical_cited_regulation": (
                        "QCVN 21:2015/BGTVT" if "OCEAN_GOING" in service_areas else None
                    ),
                    "upcoming_amendment": _UPCOMING_AMENDMENT_NOTICE,
                },
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    "QCVN 72 structural rule checks pending verified classification / service area notation",
                ],
                "limitations": limitations,
                "proposal_only_actions": proposals,
            }
        )

    design_straddles_140 = bool(design_l_all) and min(design_l_all) <= 140.0 < max(design_l_all)
    unproven_gt_140 = (
        not length_excluded
        and (
            design_straddles_140
            or (not design_l_all and ((bool(lwl_all) and max(lwl_all) > 140.0) or (not lwl_all and bool(lpp_all) and max(lpp_all) > 140.0)))
        )
    )
    if unproven_gt_140:
        unproven_reason = (
            "Insufficient evidence to confirm Clause 1.1.1 140 m design-length limit under Clause 1.4.43-1: "
            f"Lwl={lwl_all or None}, Lpp={lpp_all or None} without explicit regulatory length L "
            "(bare Lpp > 140 m or Lwl straddling [0.96*Lwl, Lwl] across 140 m cannot prove NOT_APPLICABLE)."
        )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_LENGTH_L_UNPROVEN_FOR_140M_LIMIT",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={
                    "clause_basis": "1.4.43-1",
                    "lwl_m_all": lwl_all,
                    "lpp_m_all": lpp_all,
                },
                reason=unproven_reason,
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=obs_list[0]["drawing_id"],
                action_kind="CONFIRM_REGULATORY_SERVICE_AREA",
                evidence={"clause_basis": "1.4.43-1", "lwl_m_all": lwl_all, "lpp_m_all": lpp_all},
            )
        )
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "summary": unproven_reason,
                "observed_scope": scope,
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "supported_regulation": True,
                    "in_scope": None,
                    "clause_basis": "1.4.43-1",
                    "detected_scope": "UNPROVEN_140M_BOUNDARY",
                    "upcoming_amendment": _UPCOMING_AMENDMENT_NOTICE,
                },
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    "QCVN 72 applicability and structural checks pending proven Clause 1.4.43-1 design length L",
                ],
                "limitations": limitations,
                "proposal_only_actions": proposals,
            }
        )

    length_unproven = l_lo is None or l_hi is None
    if length_unproven:
        if lpp_all:
            len_fid = "F_LENGTH_L_VS_LPP_AMBIGUOUS"
            len_reason = (
                f"Bare Lpp={lpp_all[0]:.2f}m without explicit Clause 1.4.43-1 rule length L or Lwl "
                "cannot confirm QCVN 72 scope or length-dependent checks."
            )
        else:
            len_fid = "F_MISSING_VESSEL_LENGTH"
            len_reason = (
                "Vessel regulatory length L (Clause 1.4.43-1) is missing; QCVN 72 scope and length-dependent "
                "rules cannot be confirmed."
            )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id=len_fid,
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={"drawing_ids": [o["drawing_id"] for o in obs_list], "lpp_m_all": lpp_all, "length_basis": length_basis},
                reason=len_reason,
            )
        )
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "summary": len_reason,
                "observed_scope": scope,
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "supported_regulation": True,
                    "in_scope": None,
                    "clause_basis": "1.1.1",
                    "detected_scope": "UNRESOLVED_REGULATORY_LENGTH_L",
                    "length_basis": length_basis,
                    "upcoming_amendment": _UPCOMING_AMENDMENT_NOTICE,
                },
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": checks_executed,
                "checks_not_executed": ["QCVN 72 applicability confirmation and structural checks pending proven Clause 1.4.43-1 L"],
                "limitations": limitations,
                "proposal_only_actions": proposals,
            }
        )

    # Resolve QCVN 25:2015/BGTVT small inland craft exclusion BEFORE confirming QCVN 72 scope (MV0-01)
    assert l_lo is not None and l_hi is not None
    q25_exempt_ship_type = any(
        any(tok in st for tok in ("TANKER", "OIL", "CHEMICAL", "GAS", "TUG", "PUSHER", "KEO", "DAY", "MULTIHULL", "HIGH SPEED"))
        for st in scope["ship_types"]
    )
    q25_exempt = (
        ("VR-SB" in class_notations)
        or q25_exempt_ship_type
        or (bool(hp_vals) and min(hp_vals) >= 50.0)
        or (bool(pax_vals) and max(pax_vals) > 12)
    )
    if not q25_exempt:
        if hp_vals and max(hp_vals) < 50.0 and l_lo < 20.0:
            q25_reason = (
                f"Target regulation {target_regulation} is NOT_APPLICABLE under Clause 1.1.1: "
                f"non-VR-SB inland vessel with L in [{l_lo:.2f}, {l_hi:.2f}]m (<20m) and main engine {max(hp_vals):.1f} HP (<50 HP) "
                "falls under QCVN 25:2015/BGTVT."
            )
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_SCOPE_OUT_OF_QCVN72_QCVN25",
                    verdict="NOT_APPLICABLE",
                    rule_id="RULE_MK_01_QCVN72_SCOPE",
                    evidence={"class_notations": class_notations, "l_interval_m": [l_lo, l_hi], "main_engine_hp_values": hp_vals},
                    reason=q25_reason,
                )
            )
            return validate_check_result(
                {
                    "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                    "skill_id": skill_id,
                    "pack_id": pack["id"],
                    "pack_sha256": pack["pack_sha256"],
                    "pack_status": pack["status"],
                    "cad_mutation": False,
                    "regulatory_compliance_proven": False,
                    "status": "NOT_APPLICABLE",
                    "summary": q25_reason,
                    "observed_scope": scope,
                    "applicable_regulation_scope": {
                        "target_regulation": target_regulation,
                        "supported_regulation": True,
                        "in_scope": False,
                        "clause_basis": "1.1.1",
                        "detected_scope": "QCVN_25_SMALL_CRAFT_CRITERIA",
                        "referred_regulation": "QCVN 25:2015/BGTVT",
                        "upcoming_amendment": _UPCOMING_AMENDMENT_NOTICE,
                    },
                    "partial_package": bool(partial_package),
                    "findings": findings,
                    "checks_executed": checks_executed,
                    "checks_not_executed": ["QCVN 72 structural checks excluded under QCVN 25:2015/BGTVT"],
                    "limitations": limitations,
                    "proposal_only_actions": proposals,
                }
            )
        if l_lo < 20.0 or (not hp_vals and not pax_vals and l_hi <= 25.0) or (hp_vals and max(hp_vals) < 50.0):
            q25_unres_reason = (
                f"Insufficient evidence to exclude QCVN 25:2015/BGTVT under Clause 1.1.1: non-VR-SB inland vessel "
                f"(class={class_notations or 'UNSPECIFIED'}, L=[{l_lo:.2f}, {l_hi:.2f}]m) lacks verified >=50 HP propulsion / capacity evidence."
            )
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_SCOPE_QCVN25_UNRESOLVED",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_01_QCVN72_SCOPE",
                    evidence={
                        "class_notations": class_notations,
                        "l_interval_m": [l_lo, l_hi],
                        "main_engine_hp_values": hp_vals,
                        "passenger_count_values": pax_vals,
                    },
                    reason=q25_unres_reason,
                )
            )
            proposals.append(
                build_marine_core_proposal(
                    target_drawing_id=obs_list[0]["drawing_id"],
                    action_kind="CONFIRM_REGULATORY_SERVICE_AREA",
                    evidence={"unresolved_exclusion": "QCVN_25_2015_BGTVT", "l_interval_m": [l_lo, l_hi]},
                )
            )
            return validate_check_result(
                {
                    "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                    "skill_id": skill_id,
                    "pack_id": pack["id"],
                    "pack_sha256": pack["pack_sha256"],
                    "pack_status": pack["status"],
                    "cad_mutation": False,
                    "regulatory_compliance_proven": False,
                    "status": "INSUFFICIENT_EVIDENCE",
                    "summary": q25_unres_reason,
                    "observed_scope": scope,
                    "applicable_regulation_scope": {
                        "target_regulation": target_regulation,
                        "supported_regulation": True,
                        "in_scope": None,
                        "clause_basis": "1.1.1",
                        "detected_scope": "QCVN_25_EXCLUSION_UNRESOLVED",
                        "candidate_referred_regulation": "QCVN 25:2015/BGTVT",
                        "upcoming_amendment": _UPCOMING_AMENDMENT_NOTICE,
                    },
                    "partial_package": bool(partial_package),
                    "findings": findings,
                    "checks_executed": checks_executed,
                    "checks_not_executed": ["QCVN 72 structural rules pending QCVN 25:2015/BGTVT exclusion resolution"],
                    "limitations": limitations,
                    "proposal_only_actions": proposals,
                }
            )

    # Confirmed QCVN 72 scope (all trust, length, and QCVN 25 exclusion gates satisfied)
    findings.append(
        _make_finding(
            rules_by_id,
            finding_id="F_SCOPE_QCVN72_CONFIRMED",
            verdict="PASS",
            rule_id="RULE_MK_01_QCVN72_SCOPE",
            evidence={
                "service_areas": service_areas,
                "class_notations": scope["class_notations"],
                "l_interval_m": [l_lo, l_hi],
                "length_basis": length_basis,
                "main_engine_hp_values": hp_vals,
            },
            reason=f"Confirmed inland waterway scope under {target_regulation}.",
        )
    )

    for c_key, c_buckets in pkg_conflicts.items():
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id=f"F_CROSS_SHEET_CONFLICT_{c_key.upper()}",
                verdict="CONFLICT",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={c_key: c_buckets},
                reason=f"Cross-drawing conflict detected on {c_key}: {c_buckets}.",
            )
        )

    # Partial submittal boundary check
    observed_types = set(scope["observed_types"])
    missing_core_sheets = [dt for dt in _REQUIRED_SUBMITTAL_DRAWINGS if dt not in observed_types]
    if "LINES_PLAN" not in observed_types:
        checks_not_executed.append("Lines Plan hull fairness/offset verification (drawing not in package)")
    for missing_dt in missing_core_sheets:
        checks_not_executed.append(f"{missing_dt} submittal inspection (drawing not in package)")
    checks_not_executed.extend(
        [
            "Intact and damage stability booklet verification (separate calculation)",
            "Freeboard and loadline calculation verification",
            "Machinery, piping, electrical systems, and physical Registry survey",
        ]
    )
    checks_executed.append("Partial package submittal boundary audit (QCVN 72 2.2.1)")
    if partial_package:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_PARTIAL_PACKAGE_BOUNDED",
                verdict="PASS",
                rule_id="RULE_MK_07_PARTIAL_PACKAGE_BOUNDARY",
                evidence={
                    "partial_package": True,
                    "observed_drawing_types": sorted(observed_types),
                    "unprovided_core_drawings": missing_core_sheets,
                },
                reason="Evaluated within supplied drawing subset; unprovided companion drawings recorded in checks_not_executed.",
            )
        )
    elif missing_core_sheets:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_FULL_SUBMITTAL_MISSING_CORE_SHEETS",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_07_PARTIAL_PACKAGE_BOUNDARY",
                evidence={
                    "partial_package": False,
                    "missing_core_drawings": missing_core_sheets,
                },
                reason=f"Complete package claimed but mandatory (*) drawings absent: {', '.join(missing_core_sheets)}.",
            )
        )

    # Input trustworthiness, regulatory L bounds, and QCVN 25 gates are already resolved above.
    structural_checks_ran = 0
    length_unproven = False
    obs_drawing_types = scope["obs_drawing_types"]
    hull_materials = scope["hull_materials"]
    non_steel_materials = [m for m in hull_materials if m != "STEEL"]
    steel_verified = hull_materials == ["STEEL"]
    if not hull_materials:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_HULL_MATERIAL_UNVERIFIED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={"hull_materials": hull_materials},
                reason=(
                    "Hull material (e.g. HULL MATERIAL : STEEL vs ALUMINUM) is unverified; "
                    "steel structural scantling rules cannot return PASS or emit steel CONFLICT."
                ),
            )
        )
    elif non_steel_materials:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_NON_STEEL_HULL_OUT_OF_V0_RULESET",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={"hull_materials": hull_materials},
                reason=(
                    f"Declared hull material(s) {', '.join(non_steel_materials)} require specialized "
                    "non-steel QCVN 72 rules (e.g. Part 2A Chapter 4 aluminum alloy), outside steel V0 ruleset."
                ),
            )
        )

    # Check RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT (dry-cargo steel GENERAL_ARRANGEMENT / BASIC_STRUCTURAL only)
    bh_pairs, bh_wrong, bh_untrusted, bh_invalid = _extract_strict_metric(
        obs_list,
        "transverse_watertight_bulkhead_count",
        allowed_types=("GENERAL_ARRANGEMENT", "BASIC_STRUCTURAL"),
        obs_drawing_types=obs_drawing_types,
    )
    if bh_wrong:
        checks_not_executed.append(
            f"Watertight bulkhead count on non-GA/KCCB sheet(s) {', '.join(bh_wrong)} excluded"
        )
        if not bh_pairs and not bh_invalid:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_WRONG_SHEET_METRIC_BULKHEAD",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                    evidence={"wrong_sheet_drawing_ids": bh_wrong},
                    reason=f"Bulkhead count supplied only on non-GA/KCCB sheet(s) {', '.join(bh_wrong)}.",
                )
            )
    if bh_invalid:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_INVALID_BULKHEAD_COUNT",
                verdict="CONFLICT",
                rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                evidence={"invalid_metrics": bh_invalid},
                reason=f"Invalid non-integer/negative bulkhead count: {', '.join(bh_invalid)}.",
            )
        )
    special_bh_types = [
        st for st in scope["ship_types"]
        if any(tok in st for tok in ("TANKER", "CHỞ DẦU", "CHO DAU", "PASSENGER", "KHÁCH", "KHACH", "BARGE", "SÀ LAN", "SA LAN", "LIQUID", "HÀNG LỎNG", "HANG LONG"))
    ]
    is_dry_cargo = bool(scope["ship_types"]) and not special_bh_types and any(
        any(tok in st for tok in ("DRY CARGO", "HÀNG KHÔ", "HANG KHO", "GENERAL CARGO", "TỔNG HỢP", "TONG HOP"))
        for st in scope["ship_types"]
    )
    mk08_exceptions = [
        "Evaluated: Clause 3.7.21 (< 20 m >= 2 bulkheads) vs Clause 2.4.6-8 (20 m..140 m dry-cargo band)",
        "Not evaluated in V0: Clause 2.4.6-9 double-hull / container Registry-approved exception",
        "Not evaluated in V0: Engine-room boundary bulkhead placement (2.4.6-4) and collision bulkhead position (2.4.6-2)",
    ]
    mk08_unverified = [
        "collision_bulkhead_position_2_4_6_2",
        "machinery_boundary_watertightness_2_4_6_4",
        "watertight_doors_and_coamings_2_4_6_6",
        "bulkhead_max_spacing_6D_2_4_6_1",
    ]
    if bh_pairs and bh_untrusted:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_OCR_METRIC_BULKHEAD",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                evidence={"untrusted_drawing_ids": bh_untrusted, "coverage_scope": "COUNT_ONLY"},
                reason="Bulkhead count lacks verified CAD/fixture provenance and cannot produce PASS.",
                exceptions_checked=mk08_exceptions,
                conditions_applied=["QCVN 72 Clause 2.4.6 count check paused pending verified metric provenance"],
            )
        )
    elif bh_pairs and non_steel_materials:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_WATERTIGHT_BULKHEAD_NON_STEEL_NOT_APPLICABLE",
                verdict="NOT_APPLICABLE",
                rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                evidence={"hull_materials": hull_materials, "coverage_scope": "COUNT_ONLY"},
                reason=f"Steel dry-cargo bulkhead rule is NOT_APPLICABLE to hull material {', '.join(non_steel_materials)}.",
                exceptions_checked=mk08_exceptions,
                conditions_applied=[f"Non-steel hull material observed ({', '.join(non_steel_materials)}); steel rule not applied"],
            )
        )
    elif bh_pairs and not steel_verified:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_WATERTIGHT_BULKHEAD_MATERIAL_UNVERIFIED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                evidence={"hull_materials": hull_materials, "coverage_scope": "COUNT_ONLY"},
                reason="Steel dry-cargo bulkhead rule requires verified STEEL hull material before PASS or CONFLICT.",
                exceptions_checked=mk08_exceptions,
                conditions_applied=["QCVN 72 Clause 2.4.6 count check paused: hull material is not confirmed STEEL"],
            )
        )
    elif bh_pairs:
        worst_did, min_bh, _ = min(bh_pairs, key=lambda item: item[1])
        min_bh_int = int(round(min_bh))
        if special_bh_types or not is_dry_cargo:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_BULKHEAD_SHIP_TYPE_SPECIAL_REVIEW",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                    evidence={"ship_types": scope["ship_types"], "special_types": special_bh_types, "effective_l_m": effective_l_m, "coverage_scope": "COUNT_ONLY"},
                    reason=(
                        f"QCVN 72 Clause 2.4.6-8 dry-cargo bulkhead table requires verified DRY CARGO ship type; "
                        f"observed ship_types={scope['ship_types'] or 'UNSPECIFIED'}."
                    ),
                    exceptions_checked=mk08_exceptions,
                    conditions_applied=["Steel dry-cargo ship type prerequisite unverified/special type"],
                )
            )
        else:
            assert l_lo is not None and l_hi is not None
            req_lo = _required_inland_bulkheads(l_lo)
            req_hi = _required_inland_bulkheads(l_hi)
            crosses_20 = (l_lo <= 20.0 <= l_hi) or req_lo is None or req_hi is None
            if crosses_20:
                checks_executed.append("RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT (20m boundary check)")
                findings.append(
                    _make_finding(
                        rules_by_id,
                        finding_id="F_BULKHEAD_20M_BOUNDARY_UNRESOLVED",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                        evidence={
                            "drawing_id": worst_did,
                            "l_interval_m": [l_lo, l_hi],
                            "observed_bulkheads": min_bh_int,
                            "length_basis": length_basis,
                            "coverage_scope": "COUNT_ONLY",
                            "unverified_subconditions": mk08_unverified,
                        },
                        reason=(
                            f"Exact L=20.0 m (interval [{l_lo:.2f}, {l_hi:.2f}]m) sits at the gap between "
                            "Clause 3.7.21 (L < 20 m -> >=2 bulkheads) and Clause 2.4.6-8 (20 m < L <= 40 m -> >=3 bulkheads); "
                            "manual Registry boundary confirmation required."
                        ),
                        exceptions_checked=mk08_exceptions,
                        conditions_applied=[f"Confirmed QCVN 72 STEEL DRY CARGO; length [{l_lo:.2f}, {l_hi:.2f}]m sits on 20 m Clause 2.4.6-8 / 3.7.21 boundary"],
                    )
                )
            elif req_lo != req_hi:
                checks_executed.append("RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT (threshold interval check)")
                findings.append(
                    _make_finding(
                        rules_by_id,
                        finding_id="F_LENGTH_LWL_INTERVAL_STRADDLES_THRESHOLD",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                        evidence={
                            "drawing_id": worst_did,
                            "l_interval_m": [l_lo, l_hi],
                            "req_lo": req_lo,
                            "req_hi": req_hi,
                            "length_basis": length_basis,
                            "coverage_scope": "COUNT_ONLY",
                        },
                        reason=(
                            f"Length interval [{l_lo:.2f}, {l_hi:.2f}]m ({length_basis}) straddles QCVN 72 bulkhead "
                            f"threshold (required {req_lo}..{req_hi}); reconciled regulatory L required."
                        ),
                        exceptions_checked=mk08_exceptions,
                        conditions_applied=[f"Confirmed QCVN 72 STEEL DRY CARGO; interval [{l_lo:.2f}, {l_hi:.2f}]m straddles bulkhead band"],
                    )
                )
            else:
                has_exc_yes = bool(
                    scope["double_hull_or_double_side"]
                    or scope["is_container_ship"]
                    or scope["explicit_2_4_6_9_applicable"]
                )
                has_exc_no = bool(
                    scope["single_side_or_non_double_hull"] and scope["non_container_ship"]
                )
                has_side_conflict = bool(
                    scope["double_hull_or_double_side"] and scope["single_side_or_non_double_hull"]
                )
                has_cont_conflict = bool(
                    scope["is_container_ship"] and scope["non_container_ship"]
                )
                has_explicit_exc_conflict = bool(
                    scope["explicit_2_4_6_9_applicable"] and has_exc_no
                )
                if l_hi < 20.0:
                    exc_2_4_6_9_status = "NOT_APPLICABLE_UNDER_20M"
                elif has_side_conflict or has_cont_conflict or has_explicit_exc_conflict:
                    exc_2_4_6_9_status = "CONFLICTING_OR_UNKNOWN"
                elif has_exc_yes:
                    exc_2_4_6_9_status = "APPLICABLE"
                elif has_exc_no:
                    exc_2_4_6_9_status = "INAPPLICABLE"
                else:
                    exc_2_4_6_9_status = "UNKNOWN"

                if min_bh_int >= req_hi:
                    checks_executed.append("RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
                    structural_checks_ran += 1
                    findings.append(
                        _make_finding(
                            rules_by_id,
                            finding_id="F_WATERTIGHT_BULKHEAD_COUNT",
                            verdict="PASS",
                            rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                            evidence={
                                "drawing_id": worst_did,
                                "effective_l_m": effective_l_m,
                                "l_interval_m": [l_lo, l_hi],
                                "length_basis": length_basis,
                                "observed_bulkheads": min_bh_int,
                                "required_min": req_hi,
                                "exception_2_4_6_9_eligibility": exc_2_4_6_9_status,
                                "coverage_scope": "COUNT_ONLY",
                                "unverified_subconditions": mk08_unverified,
                            },
                            reason=(
                                f"L in [{l_lo:.2f}, {l_hi:.2f}]m ({length_basis}) requires >= {req_hi} transverse "
                                f"watertight bulkheads (COUNT_ONLY); observed {min_bh_int} on {worst_did}."
                            ),
                            exceptions_checked=mk08_exceptions,
                            conditions_applied=[
                                f"Confirmed QCVN 72 STEEL DRY CARGO (L=[{l_lo:.2f}, {l_hi:.2f}]m)",
                                f"Checked COUNT_ONLY minimum: observed {min_bh_int} >= required {req_hi}",
                            ],
                        )
                    )
                elif min_bh_int < 2 or l_hi < 20.0:
                    checks_executed.append("RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
                    structural_checks_ran += 1
                    floor_reason = (
                        f"Interval L in [{l_lo:.2f}, {l_hi:.2f}]m ({length_basis}) violates unconditional "
                        f"minimum bulkhead requirement (observed {min_bh_int} < {2 if min_bh_int < 2 else req_lo}) "
                        f"on {worst_did}."
                    )
                    findings.append(
                        _make_finding(
                            rules_by_id,
                            finding_id="F_WATERTIGHT_BULKHEAD_COUNT",
                            verdict="CONFLICT",
                            rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                            evidence={
                                "drawing_id": worst_did,
                                "effective_l_m": effective_l_m,
                                "l_interval_m": [l_lo, l_hi],
                                "length_basis": length_basis,
                                "observed_bulkheads": min_bh_int,
                                "required_min": req_lo,
                                "exception_2_4_6_9_eligibility": exc_2_4_6_9_status,
                                "coverage_scope": "COUNT_ONLY",
                                "unverified_subconditions": mk08_unverified,
                            },
                            reason=floor_reason,
                            exceptions_checked=mk08_exceptions,
                            conditions_applied=[
                                f"Confirmed QCVN 72 STEEL DRY CARGO (L=[{l_lo:.2f}, {l_hi:.2f}]m)",
                                f"Checked COUNT_ONLY floor/threshold: observed {min_bh_int} < required {req_lo} (Clause 2.4.6-2 / 2.4.6-8 / 3.7.21)",
                            ],
                        )
                    )
                    proposals.append(
                        build_marine_core_proposal(
                            target_drawing_id=worst_did,
                            action_kind="REVIEW_WATERTIGHT_BULKHEAD_SUBDIVISION",
                            evidence={"observed": min_bh_int, "required_min": req_lo, "l_interval_m": [l_lo, l_hi]},
                        )
                    )
                elif exc_2_4_6_9_status == "APPLICABLE":
                    checks_executed.append("RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT (Clause 2.4.6-9 double-hull/container exception)")
                    findings.append(
                        _make_finding(
                            rules_by_id,
                            finding_id="F_WATERTIGHT_BULKHEAD_2_4_6_9_EXCEPTION_QUALIFIED",
                            verdict="INSUFFICIENT_EVIDENCE",
                            rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                            evidence={
                                "drawing_id": worst_did,
                                "l_interval_m": [l_lo, l_hi],
                                "observed_bulkheads": min_bh_int,
                                "base_table_required_min": req_lo,
                                "exception_clause": "2.4.6-9",
                                "exception_2_4_6_9_eligibility": exc_2_4_6_9_status,
                                "double_hull_or_double_side": scope["double_hull_or_double_side"],
                                "is_container_ship": scope["is_container_ship"],
                                "coverage_scope": "COUNT_ONLY",
                                "unverified_subconditions": mk08_unverified + ["double_side_bulkhead_spacing_le_15a_2_4_6_9", "torsional_strength_approval_2_4_6_9"],
                            },
                            reason=(
                                f"Observed {min_bh_int} bulkheads vs base table >= {req_lo}, but double-hull/container markers "
                                "qualify this design under QCVN 72 Clause 2.4.6-9 cargo-hold reduction (Registry torsional/spacing approval required)."
                            ),
                            exceptions_checked=[
                                "Evaluated Clause 2.4.6-9 candidate: double-hull / container cargo-hold reduction noted; requires Registry approval",
                                "Evaluated: Clause 3.7.21 (< 20 m) vs Clause 2.4.6-8 (20 m < L <= 140 m)",
                            ],
                            conditions_applied=[f"Confirmed QCVN 72 STEEL DRY CARGO; Clause 2.4.6-9 double-hull/container reduction candidate triggered ({min_bh_int} vs {req_lo})"],
                        )
                    )
                elif exc_2_4_6_9_status in {"UNKNOWN", "CONFLICTING_OR_UNKNOWN"}:
                    checks_executed.append("RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT (Clause 2.4.6-8 conditional; 2.4.6-9 eligibility unresolved)")
                    findings.append(
                        _make_finding(
                            rules_by_id,
                            finding_id="F_WATERTIGHT_BULKHEAD_2_4_6_9_ELIGIBILITY_UNKNOWN",
                            verdict="INSUFFICIENT_EVIDENCE",
                            rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                            evidence={
                                "drawing_id": worst_did,
                                "effective_l_m": effective_l_m,
                                "l_interval_m": [l_lo, l_hi],
                                "length_basis": length_basis,
                                "observed_bulkheads": min_bh_int,
                                "base_table_required_min": req_lo,
                                "exception_clause": "2.4.6-9",
                                "exception_2_4_6_9_eligibility": exc_2_4_6_9_status,
                                "double_hull_or_double_side": scope["double_hull_or_double_side"],
                                "single_side_or_non_double_hull": scope["single_side_or_non_double_hull"],
                                "is_container_ship": scope["is_container_ship"],
                                "non_container_ship": scope["non_container_ship"],
                                "coverage_scope": "COUNT_ONLY",
                                "unverified_subconditions": mk08_unverified + [
                                    "clause_2_4_6_9_double_side_or_container_eligibility_unverified",
                                ],
                            },
                            reason=(
                                f"Observed {min_bh_int} bulkheads vs Clause 2.4.6-8 base table >= {req_lo} at "
                                f"L=[{l_lo:.2f}, {l_hi:.2f}]m, while Clause 2.4.6-9 double-side/container exception "
                                f"eligibility is {exc_2_4_6_9_status}; verify side construction and container service "
                                "before emitting definitive count CONFLICT."
                            ),
                            exceptions_checked=[
                                "Evaluated: Clause 3.7.21 (< 20 m >= 2 bulkheads) vs Clause 2.4.6-8 (20 m..140 m dry-cargo band)",
                                f"Unresolved in V0: Clause 2.4.6-9 double-hull / container eligibility ({exc_2_4_6_9_status})",
                                "Not evaluated in V0: Engine-room boundary bulkhead placement (2.4.6-4) and collision bulkhead position (2.4.6-2)",
                            ],
                            conditions_applied=[
                                f"Confirmed QCVN 72 STEEL DRY CARGO (L=[{l_lo:.2f}, {l_hi:.2f}]m)",
                                f"Base table threshold is {req_lo} vs observed {min_bh_int}; Clause 2.4.6-9 exception eligibility={exc_2_4_6_9_status} pauses definitive CONFLICT",
                            ],
                        )
                    )
                    proposals.append(
                        build_marine_core_proposal(
                            target_drawing_id=worst_did,
                            action_kind="REVIEW_WATERTIGHT_BULKHEAD_SUBDIVISION",
                            evidence={
                                "observed": min_bh_int,
                                "base_table_required_min": req_lo,
                                "l_interval_m": [l_lo, l_hi],
                                "exception_2_4_6_9_eligibility": exc_2_4_6_9_status,
                            },
                        )
                    )
                else:
                    checks_executed.append("RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
                    structural_checks_ran += 1
                    findings.append(
                        _make_finding(
                            rules_by_id,
                            finding_id="F_WATERTIGHT_BULKHEAD_COUNT",
                            verdict="CONFLICT",
                            rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                            evidence={
                                "drawing_id": worst_did,
                                "effective_l_m": effective_l_m,
                                "l_interval_m": [l_lo, l_hi],
                                "length_basis": length_basis,
                                "observed_bulkheads": min_bh_int,
                                "required_min": req_lo,
                                "exception_2_4_6_9_eligibility": exc_2_4_6_9_status,
                                "coverage_scope": "COUNT_ONLY",
                                "unverified_subconditions": mk08_unverified,
                            },
                            reason=(
                                f"Interval L in [{l_lo:.2f}, {l_hi:.2f}]m ({length_basis}) requires at least {req_lo} "
                                f"transverse watertight bulkheads (COUNT_ONLY; Clause 2.4.6-9 verified INAPPLICABLE); "
                                f"observed {min_bh_int} on {worst_did}."
                            ),
                            exceptions_checked=[
                                "Evaluated: Clause 3.7.21 (< 20 m >= 2 bulkheads) vs Clause 2.4.6-8 (20 m..140 m dry-cargo band)",
                                "Evaluated Clause 2.4.6-9: verified non-double-side and non-container hull (exception INAPPLICABLE)",
                                "Not evaluated in V0: Engine-room boundary bulkhead placement (2.4.6-4) and collision bulkhead position (2.4.6-2)",
                            ],
                            conditions_applied=[
                                f"Confirmed QCVN 72 STEEL DRY CARGO (L=[{l_lo:.2f}, {l_hi:.2f}]m); Clause 2.4.6-9 verified INAPPLICABLE",
                                f"Checked COUNT_ONLY threshold: observed {min_bh_int} < required {req_lo} (Clause 2.4.6-8)",
                            ],
                        )
                    )
                    proposals.append(
                        build_marine_core_proposal(
                            target_drawing_id=worst_did,
                            action_kind="REVIEW_WATERTIGHT_BULKHEAD_SUBDIVISION",
                            evidence={
                                "observed": min_bh_int,
                                "required_min": req_lo,
                                "l_interval_m": [l_lo, l_hi],
                                "exception_2_4_6_9_eligibility": exc_2_4_6_9_status,
                            },
                        )
                    )
    elif "GENERAL_ARRANGEMENT" in observed_types or "BASIC_STRUCTURAL" in observed_types:
        checks_not_executed.append("Watertight bulkhead count (transverse_watertight_bulkhead_count not annotated/extracted)")

    # Check RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT (MIDSHIP_STRUCTURAL / BASIC_STRUCTURAL only)
    db_pairs, db_wrong, db_untrusted, db_invalid = _extract_strict_metric(
        obs_list,
        "double_bottom_height_mm",
        allowed_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
        obs_drawing_types=obs_drawing_types,
    )
    girder_pairs, gr_wrong, gr_untrusted, gr_invalid = _extract_strict_metric(
        obs_list,
        "bottom_girder_max_spacing_mm",
        allowed_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
        obs_drawing_types=obs_drawing_types,
    )
    floor_pairs, fl_wrong, fl_untrusted, fl_invalid = _extract_strict_metric(
        obs_list,
        "transverse_floor_max_spacing_mm",
        allowed_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
        obs_drawing_types=obs_drawing_types,
    )
    # Collect per-measurement floor spacing records across eligible structural sheets (MV0-05)
    floor_list_records: list[tuple[str, float, str, str]] = []
    floor_list_wrong: list[str] = []
    floor_list_untrusted: list[str] = []
    for idx_o, obs in enumerate(obs_list):
        did = obs["drawing_id"]
        sm_o = obs.get("structural_metrics", {})
        if "floor_spacing_measurements" not in sm_o or sm_o["floor_spacing_measurements"] is None:
            continue
        stype_o = obs_drawing_types[idx_o] if idx_o < len(obs_drawing_types) else "UNKNOWN"
        if stype_o not in {"MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"}:
            floor_list_wrong.append(did)
            continue
        m_prov = str(obs.get("metric_provenance", {}).get("floor_spacing_measurements", "")).strip()
        if obs.get("ocr_only") or m_prov not in _VERIFIED_PROVENANCES:
            floor_list_untrusted.append(did)
        for meas in sm_o["floor_spacing_measurements"]:
            if isinstance(meas, Mapping):
                valid_sp, sp_val = _is_valid_finite_metric("transverse_floor_max_spacing_mm", meas.get("spacing_mm"))
                if valid_sp and sp_val is not None:
                    reg_str = str(meas.get("region") or "").strip().upper()
                    floor_list_records.append((did, sp_val, reg_str, m_prov))

    has_any_floor_metric = bool(floor_pairs or floor_list_records)
    if db_wrong or gr_wrong or fl_wrong or floor_list_wrong:
        excluded_sheets = sorted(set(db_wrong) | set(gr_wrong) | set(fl_wrong) | set(floor_list_wrong))
        checks_not_executed.append(
            f"Double-bottom dimensions on non-structural sheet(s) {', '.join(excluded_sheets)} excluded"
        )
        if not (db_pairs or girder_pairs or has_any_floor_metric) and not (db_invalid or gr_invalid or fl_invalid):
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_WRONG_SHEET_METRIC_DOUBLE_BOTTOM",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                    evidence={"wrong_sheet_drawing_ids": excluded_sheets},
                    reason=(
                        f"Double-bottom dimension(s) supplied only on non-structural sheet(s) "
                        f"{', '.join(excluded_sheets)} without eligible MCN/KCCB evidence."
                    ),
                    conditions_applied=["Excluded metrics on non-MCN/KCCB sheet(s); double-bottom evaluation deferred"],
                )
            )
    mk09_invalid = db_invalid + gr_invalid + fl_invalid
    mk09_untrusted = sorted(set(db_untrusted) | set(gr_untrusted) | set(fl_untrusted) | set(floor_list_untrusted))
    mk09_exceptions = [
        "Evaluated: Clause 2.4.3-1 floor spacing (1800/2000/2400 mm), 2.4.3-2 DB height (700/900 mm), 2.4.3-3 girder spacing (<= 3000 mm)",
        "Not evaluated in V0: Single-bottom ships (where double bottom is not required)",
    ]
    mk09_unverified_subconditions = [
        "centerline_plane_measurement_location_2_4_3_2",
        "floor_spacing_frame_multiple_2_4_3_1",
        "continuous_girder_structural_continuity_2_4_3_3",
    ]
    if mk09_invalid:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_INVALID_DOUBLE_BOTTOM_METRIC",
                verdict="CONFLICT",
                rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                evidence={"invalid_metrics": mk09_invalid},
                reason=f"Invalid non-finite/non-positive double-bottom metrics: {', '.join(mk09_invalid)}.",
                exceptions_checked=mk09_exceptions,
                conditions_applied=["Numeric finiteness/positivity check failed on observed double-bottom metrics"],
            )
        )
    elif (db_pairs or girder_pairs or has_any_floor_metric) and non_steel_materials:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_DOUBLE_BOTTOM_NON_STEEL_NOT_APPLICABLE",
                verdict="NOT_APPLICABLE",
                rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                evidence={"hull_materials": hull_materials, "unverified_subconditions": mk09_unverified_subconditions},
                reason=f"Steel Clause 2.4.3 double-bottom rule is NOT_APPLICABLE to non-steel hull material {', '.join(non_steel_materials)}.",
                exceptions_checked=mk09_exceptions,
                conditions_applied=[f"Non-steel hull material observed ({', '.join(non_steel_materials)}); Clause 2.4.3 steel rule not applicable"],
            )
        )
    elif (db_pairs or girder_pairs or has_any_floor_metric) and not steel_verified:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_DOUBLE_BOTTOM_MATERIAL_UNVERIFIED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                evidence={"hull_materials": hull_materials, "unverified_subconditions": mk09_unverified_subconditions},
                reason="Clause 2.4.3 steel double-bottom check requires verified STEEL hull material before PASS or CONFLICT.",
                exceptions_checked=mk09_exceptions,
                conditions_applied=["QCVN 72 Clause 2.4.3 evaluation paused: hull material is not confirmed STEEL"],
            )
        )
    elif (db_pairs or girder_pairs or has_any_floor_metric) and mk09_untrusted:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_OCR_METRIC_DOUBLE_BOTTOM",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                evidence={"untrusted_drawing_ids": mk09_untrusted},
                reason="Double-bottom height or girder/floor spacing lacks verified provenance and cannot produce PASS.",
                exceptions_checked=mk09_exceptions,
                conditions_applied=["Confirmed STEEL vessel; Clause 2.4.3 check paused due to untrusted metric provenance"],
            )
        )
    elif db_pairs or girder_pairs or has_any_floor_metric:
        checks_executed.append("RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT")
        structural_checks_ran += 1
        worst_db_pair = min(db_pairs, key=lambda item: item[1]) if db_pairs else None
        max_girder_pair = max(girder_pairs, key=lambda item: item[1]) if girder_pairs else None
        max_floor_pair = max(floor_pairs, key=lambda item: item[1]) if floor_pairs else None
        target_db_did = (
            worst_db_pair[0]
            if worst_db_pair
            else (
                max_girder_pair[0]
                if max_girder_pair
                else (max_floor_pair[0] if max_floor_pair else floor_list_records[0][0])
            )
        )

        # Evaluate floor spacing per QCVN 72 Clause 2.4.3-1 paired strictly with EACH measurement's own verified region (MV0-05)
        is_passenger_or_liquid = any(
            any(tok in st for tok in ("TANKER", "LIQUID", "HÀNG LỎNG", "HANG LONG", "CHỞ DẦU", "CHO DAU", "CHỞ HÓA CHẤT", "PASSENGER", "KHÁCH", "KHACH"))
            for st in scope["ship_types"]
        )
        is_dry_cargo_db = bool(scope["ship_types"]) and not is_passenger_or_liquid and any(
            any(tok in st for tok in ("DRY CARGO", "HÀNG KHÔ", "HANG KHO", "GENERAL CARGO", "TỔNG HỢP", "TONG HOP"))
            for st in scope["ship_types"]
        )
        raw_floor_items: list[tuple[str, float, str, str]] = []
        for fdid, fval, fobs in floor_pairs:
            reg_raw = str(fobs.get("structural_metrics", {}).get("floor_spacing_region") or "").strip().upper()
            reg_prov = str(fobs.get("metric_provenance", {}).get("floor_spacing_region") or fobs.get("metric_provenance", {}).get("transverse_floor_max_spacing_mm") or "").strip()
            raw_floor_items.append((fdid, fval, reg_raw, reg_prov))
        raw_floor_items.extend(floor_list_records)

        floor_records: list[dict[str, Any]] = []
        floor_regions: list[str] = []
        for fdid, fval, reg_raw, reg_prov in raw_floor_items:
            if reg_raw in _UNDER_HATCH_REGIONS:
                reg_norm = "UNDER_CARGO_HATCH"
            elif reg_raw in _OUTSIDE_HATCH_REGIONS:
                reg_norm = "OUTSIDE_CARGO_HATCH"
            elif reg_raw:
                reg_norm = f"UNRECOGNIZED:{reg_raw}"
            else:
                reg_norm = "UNSPECIFIED"
            reg_trusted = reg_prov in _VERIFIED_PROVENANCES
            floor_regions.append(reg_norm)

            if is_passenger_or_liquid:
                lim_mm = 2400.0
                rec_status = "CONFLICT" if fval > 2400.0 else "PASS"
            elif is_dry_cargo_db:
                if fval > 2000.0:
                    lim_mm = 2000.0
                    rec_status = "CONFLICT"
                elif reg_norm == "UNDER_CARGO_HATCH":
                    lim_mm = 1800.0
                    rec_status = "CONFLICT" if fval > 1800.0 else "PASS"
                elif reg_norm == "OUTSIDE_CARGO_HATCH":
                    if not reg_trusted and fval > 1800.0:
                        lim_mm = 1800.0
                        rec_status = "INSUFFICIENT_EVIDENCE"
                    elif not reg_trusted:
                        lim_mm = 1800.0
                        rec_status = "INSUFFICIENT_EVIDENCE"
                    else:
                        lim_mm = 2000.0
                        rec_status = "PASS"
                elif fval <= 1800.0:
                    lim_mm = 1800.0
                    rec_status = "PASS"
                else:
                    lim_mm = 1800.0
                    rec_status = "INSUFFICIENT_EVIDENCE"
            else:
                lim_mm = 2400.0
                rec_status = "CONFLICT" if fval > 2400.0 else "INSUFFICIENT_EVIDENCE"

            floor_records.append(
                {
                    "drawing_id": fdid,
                    "spacing_mm": fval,
                    "region": reg_norm,
                    "region_provenance": reg_prov or "UNSPECIFIED",
                    "limit_mm": lim_mm,
                    "status": rec_status,
                }
            )

        if not floor_records:
            floor_status = "MISSING"
            floor_limit_mm: float | None = None
        elif any(r["status"] == "CONFLICT" for r in floor_records):
            floor_status = "CONFLICT"
            floor_limit_mm = min(float(r["limit_mm"]) for r in floor_records if r["status"] == "CONFLICT")
        elif any(r["status"] == "INSUFFICIENT_EVIDENCE" for r in floor_records):
            floor_status = "INSUFFICIENT_EVIDENCE"
            floor_limit_mm = min(float(r["limit_mm"]) for r in floor_records if r["status"] == "INSUFFICIENT_EVIDENCE")
        else:
            floor_status = "PASS"
            floor_limit_mm = max(float(r["limit_mm"]) for r in floor_records)

        # Evaluate girder spacing per Clause 2.4.3-3 (<= 3000 mm)
        if max_girder_pair is None:
            girder_status = "MISSING"
        elif max_girder_pair[1] > 3000.0:
            girder_status = "CONFLICT"
        else:
            girder_status = "PASS"

        # Evaluate DB height per Clause 2.4.3-2 (>= 700 mm if L <= 120 m, >= 900 mm if L > 120 m)
        straddles_120 = False
        req_db_mm: float | None = None
        if worst_db_pair is None:
            db_height_status = "MISSING"
        else:
            min_db_mm = worst_db_pair[1]
            assert l_lo is not None and l_hi is not None
            straddles_120 = l_lo <= 120.0 < l_hi
            if straddles_120:
                db_height_status = "INSUFFICIENT_EVIDENCE"
            else:
                req_db_mm = 700.0 if l_hi <= 120.0 else 900.0
                db_height_status = "CONFLICT" if min_db_mm < req_db_mm else "PASS"

        sub_statuses = (db_height_status, girder_status, floor_status)
        if "CONFLICT" in sub_statuses:
            mk09_verdict = "CONFLICT"
        elif any(s != "PASS" for s in sub_statuses):
            mk09_verdict = "INSUFFICIENT_EVIDENCE"
        else:
            mk09_verdict = "PASS"

        checked_subs: list[str] = []
        if worst_db_pair is not None:
            checked_subs.append(f"db_height:{db_height_status}(req>={req_db_mm}mm)")
        if max_girder_pair is not None:
            checked_subs.append(f"girder_spacing:{girder_status}(limit<=3000.0mm)")
        if floor_records:
            checked_subs.append(
                f"floor_spacing_per_region:{floor_status}("
                + ",".join(f"{r['spacing_mm']}@{r['region']}<={r['limit_mm']}" for r in floor_records)
                + ")"
            )

        actual_conditions_09 = [
            f"Confirmed QCVN 72 STEEL hull (L=[{l_lo:.2f}, {l_hi:.2f}]m, ship_types={scope['ship_types'] or ['UNSPECIFIED']})",
            f"Checked Clause 2.4.3 limits: {'; '.join(checked_subs)}",
            "Centerline-plane measurement location, frame-spacing multiple, and girder continuity remain UNVERIFIED in V0",
        ]

        reason_parts = []
        if worst_db_pair is not None:
            req_s = f"{req_db_mm:.1f}" if req_db_mm is not None else "700.0/900.0"
            reason_parts.append(
                f"DB height={worst_db_pair[1]:.1f} mm on {worst_db_pair[0]} (min {req_s} mm, status={db_height_status})"
            )
        else:
            reason_parts.append("DB height=MISSING")
        if max_girder_pair is not None:
            reason_parts.append(
                f"girder spacing={max_girder_pair[1]:.1f} mm (limit <= 3000.0 mm, status={girder_status})"
            )
        else:
            reason_parts.append("girder spacing=MISSING")
        if floor_records:
            max_fl_val = max(r["spacing_mm"] for r in floor_records)
            reason_parts.append(
                f"floor spacing max={max_fl_val:.1f} mm paired per region={[(r['spacing_mm'], r['region'], r['limit_mm'], r['status']) for r in floor_records]}"
            )
        else:
            reason_parts.append("floor spacing=MISSING")

        finding_id_09 = (
            "F_LENGTH_LWL_INTERVAL_STRADDLES_THRESHOLD"
            if (mk09_verdict == "INSUFFICIENT_EVIDENCE" and straddles_120)
            else "F_DOUBLE_BOTTOM_HEIGHT"
        )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id=finding_id_09,
                verdict=mk09_verdict,
                rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                evidence={
                    "drawing_id": target_db_did,
                    "l_interval_m": [l_lo, l_hi],
                    "observed_db_height_mm": worst_db_pair[1] if worst_db_pair else None,
                    "required_min_db_height_mm": req_db_mm,
                    "max_girder_spacing_mm": max_girder_pair[1] if max_girder_pair else None,
                    "max_floor_spacing_mm": max((r["spacing_mm"] for r in floor_records), default=None),
                    "floor_spacing_limit_mm": floor_limit_mm,
                    "floor_regions": floor_regions,
                    "floor_measurements_evaluated": floor_records,
                    "checked_subconditions": checked_subs,
                    "unverified_subconditions": mk09_unverified_subconditions,
                    "sub_statuses": {
                        "db_height": db_height_status,
                        "girder_spacing": girder_status,
                        "floor_spacing": floor_status,
                    },
                },
                reason="; ".join(reason_parts) + ".",
                exceptions_checked=mk09_exceptions,
                conditions_applied=actual_conditions_09,
            )
        )
        if mk09_verdict == "CONFLICT":
            proposals.append(
                build_marine_core_proposal(
                    target_drawing_id=target_db_did,
                    action_kind="REVIEW_DOUBLE_BOTTOM_SCANTLINGS",
                    evidence={
                        "observed_db_height_mm": worst_db_pair[1] if worst_db_pair else None,
                        "required_min_mm": req_db_mm,
                        "max_girder_spacing_mm": max_girder_pair[1] if max_girder_pair else None,
                        "max_floor_spacing_mm": max((r["spacing_mm"] for r in floor_records), default=None),
                        "floor_measurements_evaluated": floor_records,
                    },
                )
            )

    # Check RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL (only L < 20 m steel hull on MIDSHIP/BASIC)
    plate_pairs, pl_wrong, pl_untrusted, pl_invalid = _extract_strict_metric(
        obs_list,
        "min_plate_thickness_mm",
        allowed_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
        obs_drawing_types=obs_drawing_types,
    )
    bot_pairs, bot_wrong, bot_untrusted, bot_invalid = _extract_strict_metric(
        obs_list,
        "min_bottom_plate_mm",
        allowed_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
        obs_drawing_types=obs_drawing_types,
    )
    bilge_pairs, bil_wrong, bil_untrusted, bil_invalid = _extract_strict_metric(
        obs_list,
        "min_bilge_plate_mm",
        allowed_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
        obs_drawing_types=obs_drawing_types,
    )
    if pl_wrong or bot_wrong or bil_wrong:
        wrong_pl_sheets = sorted(set(pl_wrong) | set(bot_wrong) | set(bil_wrong))
        checks_not_executed.append(
            f"Small-hull plate thickness on non-structural sheet(s) {', '.join(wrong_pl_sheets)} excluded"
        )
        if not length_unproven and l_hi is not None and l_hi < 20.0 and not (plate_pairs or bot_pairs or bilge_pairs):
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_WRONG_SHEET_METRIC_PLATE",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL",
                    evidence={"wrong_sheet_drawing_ids": wrong_pl_sheets},
                    reason=f"Small-hull plate thickness supplied only on non-structural sheet(s) {', '.join(wrong_pl_sheets)}.",
                )
            )
    unbound_pl_ids = [
        obs["drawing_id"]
        for idx, obs in enumerate(obs_list)
        if obs.get("min_plate_from_unbound_text")
        and obs_drawing_types[idx] in {"MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"}
    ]
    mk10_invalid = pl_invalid + bot_invalid + bil_invalid
    mk10_untrusted = sorted(set(pl_untrusted) | set(bot_untrusted) | set(bil_untrusted))
    has_any_plate_metric = bool(plate_pairs or bot_pairs or bilge_pairs)
    mk10_exceptions = [
        "Evaluated: Steel Ch.3 Clause 3.7.2 (>= 2.5 mm) and 3.7.3 (bottom >= 3.0 mm, bilge >= 4.0 mm) applicability vs non-steel hulls",
        "Not evaluated in V0: Ch.3 formula calculations using frame spacing a, draft d, ReH (3.7.3..3.7.9)",
    ]

    if mk10_invalid:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_INVALID_PLATE_METRIC",
                verdict="CONFLICT",
                rule_id="RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL",
                evidence={"invalid_metrics": mk10_invalid},
                reason=f"Invalid non-finite/non-positive plate thickness metrics: {', '.join(mk10_invalid)}.",
                exceptions_checked=mk10_exceptions,
            )
        )
    elif non_steel_materials and (has_any_plate_metric or unbound_pl_ids or (not length_unproven and l_lo is not None and l_lo < 20.0)):
        checks_executed.append("RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL (material applicability exclusion)")
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_SMALL_HULL_STEEL_RULE_NOT_APPLICABLE_MATERIAL",
                verdict="NOT_APPLICABLE",
                rule_id="RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL",
                evidence={"hull_materials": hull_materials},
                reason=(
                    f"Steel small-hull plate rule (QCVN 72 3.7.2-3.7.3) is NOT_APPLICABLE to non-steel "
                    f"hull material {', '.join(non_steel_materials)}."
                ),
                exceptions_checked=mk10_exceptions,
            )
        )
    elif length_unproven:
        if has_any_plate_metric or unbound_pl_ids:
            checks_not_executed.append("RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL deferred (proven L < 20m required)")
    else:
        assert l_lo is not None and l_hi is not None
        straddles_20 = l_lo < 20.0 <= l_hi
        if straddles_20 and (has_any_plate_metric or unbound_pl_ids):
            checks_executed.append("RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL (threshold interval check)")
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_LENGTH_LWL_INTERVAL_STRADDLES_THRESHOLD",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL",
                    evidence={"l_interval_m": [l_lo, l_hi], "rule_threshold_m": 20.0},
                    reason=(
                        f"Length interval [{l_lo:.2f}, {l_hi:.2f}]m straddles 20 m Ch.3 applicability "
                        "boundary; explicit regulatory L required."
                    ),
                    exceptions_checked=mk10_exceptions,
                )
            )
        elif l_hi < 20.0:
            if unbound_pl_ids:
                findings.append(
                    _make_finding(
                        rules_by_id,
                        finding_id="F_UNBOUND_PLATE_THICKNESS_TEXT",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL",
                        evidence={"drawing_ids": unbound_pl_ids},
                        reason=(
                            "Unbound plate thickness text without bottom/bilge/hull structural label cannot verify "
                            "RULE_MK_10."
                        ),
                        exceptions_checked=mk10_exceptions,
                    )
                )
            if has_any_plate_metric and mk10_untrusted:
                findings.append(
                    _make_finding(
                        rules_by_id,
                        finding_id="F_OCR_METRIC_PLATE",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL",
                        evidence={"untrusted_drawing_ids": mk10_untrusted},
                        reason="Plate thickness values lack verified CAD/fixture provenance and cannot produce PASS.",
                        exceptions_checked=mk10_exceptions,
                    )
                )
            elif has_any_plate_metric:
                checks_executed.append("RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL")
                structural_checks_ran += 1
                min_pl_pair = min(plate_pairs, key=lambda item: item[1]) if plate_pairs else None
                min_bot_pair = min(bot_pairs, key=lambda item: item[1]) if bot_pairs else None
                min_bilge_pair = min(bilge_pairs, key=lambda item: item[1]) if bilge_pairs else None
                worst_pl_id = (
                    min_pl_pair[0]
                    if min_pl_pair
                    else (min_bot_pair[0] if min_bot_pair else min_bilge_pair[0])  # type: ignore[index]
                )
                min_pl_mm = min_pl_pair[1] if min_pl_pair else None
                min_bot = min_bot_pair[1] if min_bot_pair else None
                min_bilge = min_bilge_pair[1] if min_bilge_pair else None
                pl_fail = (
                    (min_pl_mm is not None and min_pl_mm < 2.5)
                    or (min_bot is not None and min_bot < 3.0)
                    or (min_bilge is not None and min_bilge < 4.0)
                )
                pl_incomplete = (
                    not pl_fail
                    and (
                        min_pl_mm is None
                        or (min_pl_mm < 4.0 and (min_bot is None or min_bilge is None))
                        or min_bot is None
                        or min_bilge is None
                    )
                )
                if not steel_verified:
                    pl_verdict = "INSUFFICIENT_EVIDENCE"
                elif pl_fail:
                    pl_verdict = "CONFLICT"
                elif pl_incomplete:
                    pl_verdict = "INSUFFICIENT_EVIDENCE"
                else:
                    pl_verdict = "PASS"
                findings.append(
                    _make_finding(
                        rules_by_id,
                        finding_id="F_SMALL_HULL_MIN_PLATE",
                        verdict=pl_verdict,
                        rule_id="RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL",
                        evidence={
                            "drawing_id": worst_pl_id,
                            "l_interval_m": [l_lo, l_hi],
                            "min_plate_thickness_mm": min_pl_mm,
                            "min_bottom_plate_mm": min_bot,
                            "min_bilge_plate_mm": min_bilge,
                            "floor_mm": 2.5,
                            "bottom_floor_mm": 3.0,
                            "bilge_floor_mm": 4.0,
                        },
                        reason=(
                            f"L in [{l_lo:.2f}, {l_hi:.2f}]m (<20m) plating min={min_pl_mm}, "
                            f"bottom={min_bot}, bilge={min_bilge} mm "
                            "(3.7.2 floor 2.5 mm; 3.7.3 bottom>=3.0 mm and bilge>=4.0 mm required)."
                        ),
                        exceptions_checked=mk10_exceptions,
                    )
                )
        elif l_lo >= 20.0:
            checks_not_executed.append("RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL (L >= 20m outside Ch.3 <20m floor rule)")

    if structural_checks_ran == 0 and not length_unproven:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_NO_STRUCTURAL_CHECKS_EXECUTED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_07_PARTIAL_PACKAGE_BOUNDARY",
                evidence={"observed_types": sorted(observed_types), "checks_executed": checks_executed},
                reason=(
                    "No QCVN 72 structural rule (RULE_MK_08/09/10) had verified eligible metrics to evaluate; "
                    "scope check alone cannot return PASS."
                ),
            )
        )

    verdicts = [f["verdict"] for f in findings]
    if "CONFLICT" in verdicts:
        overall = "CONFLICT"
    elif "INSUFFICIENT_EVIDENCE" in verdicts or input_gates_blocked or length_unproven or structural_checks_ran == 0:
        overall = "INSUFFICIENT_EVIDENCE"
    else:
        overall = "PASS"

    summary = (
        f"Evaluated {len(obs_list)} drawing(s) under {target_regulation} "
        f"(partial_package={partial_package}): status={overall}, "
        f"{sum(1 for v in verdicts if v == 'PASS')} PASS, "
        f"{sum(1 for v in verdicts if v == 'CONFLICT')} CONFLICT, "
        f"{sum(1 for v in verdicts if v == 'INSUFFICIENT_EVIDENCE')} INSUFFICIENT_EVIDENCE."
    )
    return validate_check_result(
        {
            "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
            "skill_id": skill_id,
            "pack_id": pack["id"],
            "pack_sha256": pack["pack_sha256"],
            "pack_status": pack["status"],
            "cad_mutation": False,
            "regulatory_compliance_proven": False,
            "status": overall,
            "summary": summary,
            "observed_scope": scope,
            "applicable_regulation_scope": {
                "target_regulation": target_regulation,
                "in_scope": True,
                "clause_basis": "1.1.1",
                "class_notations": scope["class_notations"],
                "effective_l_m": effective_l_m,
                "l_interval_m": [l_lo, l_hi] if l_lo is not None and l_hi is not None else None,
                "length_basis": length_basis,
                "lpp_m": lpp_m,
                "upcoming_amendment": _UPCOMING_AMENDMENT_NOTICE,
            },
            "partial_package": bool(partial_package),
            "findings": findings,
            "checks_executed": checks_executed,
            "checks_not_executed": checks_not_executed,
            "limitations": limitations,
            "proposal_only_actions": proposals,
        }
    )


def _norm_engine(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip().lower()


def _collect_cross_sheet_values(
    obs_list: list[dict[str, Any]],
    *,
    obs_drawing_types: Sequence[str] | None = None,
) -> dict[str, dict[str, list[str]]]:
    engines: dict[str, list[str]] = {}
    service_areas: dict[str, list[str]] = {}
    class_notations: dict[str, list[str]] = {}
    design_l_map: dict[str, list[str]] = {}
    lpp_map: dict[str, list[str]] = {}
    lwl_map: dict[str, list[str]] = {}
    breadth_map: dict[str, list[str]] = {}
    depth_map: dict[str, list[str]] = {}
    draft_map: dict[str, list[str]] = {}
    ship_types: dict[str, list[str]] = {}
    hull_materials: dict[str, list[str]] = {}
    hull_nos: dict[str, list[str]] = {}
    db_map: dict[str, list[str]] = {}
    bh_map: dict[str, list[str]] = {}

    if obs_drawing_types is None:
        obs_drawing_types = [_classify_observation(obs)["predicted_drawing_type"] for obs in obs_list]

    for idx, obs in enumerate(obs_list):
        did = obs["drawing_id"]
        dtype = obs_drawing_types[idx] if idx < len(obs_drawing_types) else "UNKNOWN"
        part = obs["particulars"]
        for eng in part["main_engine_values"]:
            engines.setdefault(_norm_engine(eng), []).append(f"{did}:{eng}")
        for sa in part["service_areas"]:
            service_areas.setdefault(sa, []).append(did)
        for cls_tag in part["class_notations"]:
            class_notations.setdefault(cls_tag, []).append(did)
        for val in part.get("design_length_l_m_values", []):
            design_l_map.setdefault(f"{val:.2f}", []).append(did)
        for val in part["lpp_m_values"]:
            lpp_map.setdefault(f"{val:.2f}", []).append(did)
        for val in part.get("lwl_m_values", []):
            lwl_map.setdefault(f"{val:.2f}", []).append(did)
        for val in part["breadth_m_values"]:
            breadth_map.setdefault(f"{val:.2f}", []).append(did)
        for val in part["depth_m_values"]:
            depth_map.setdefault(f"{val:.2f}", []).append(did)
        for val in part["draft_m_values"]:
            draft_map.setdefault(f"{val:.2f}", []).append(did)
        for st in part["ship_types"]:
            ship_types.setdefault(st, []).append(did)
        for hm in part.get("hull_materials", []):
            hull_materials.setdefault(hm, []).append(did)
        for hno in part.get("hull_nos", []):
            hull_nos.setdefault(hno.upper(), []).append(f"{did}:{hno}")
        sm = obs.get("structural_metrics", {})
        db_val = sm.get("double_bottom_height_mm")
        db_ok, db_f = _is_valid_finite_metric("double_bottom_height_mm", db_val)
        if db_ok and db_f is not None and dtype in {"MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"}:
            db_map.setdefault(f"{db_f:.1f}", []).append(did)
        bh_val = sm.get("transverse_watertight_bulkhead_count")
        bh_ok, bh_f = _is_valid_finite_metric("transverse_watertight_bulkhead_count", bh_val)
        if bh_ok and bh_f is not None and dtype in {"GENERAL_ARRANGEMENT", "BASIC_STRUCTURAL"}:
            bh_map.setdefault(str(int(bh_f)), []).append(did)

    return {
        "engines": engines,
        "service_areas": service_areas,
        "class_notations": class_notations,
        "design_length_l_m": design_l_map,
        "lpp_m": lpp_map,
        "lwl_m": lwl_map,
        "breadth_m": breadth_map,
        "depth_m": depth_map,
        "draft_m": draft_map,
        "ship_types": ship_types,
        "hull_materials": hull_materials,
        "hull_nos": hull_nos,
        "double_bottom_height_mm": db_map,
        "transverse_watertight_bulkhead_count": bh_map,
    }


def detect_drawing_gaps_and_conflicts(
    observations: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    partial_package: bool = True,
    verified_scale_to_mm: float | None = None,
    calibration_verified: bool = False,
    ocr_only_inputs: bool = False,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """Skill 3: Detect CAD unitlessness, OCR-only limits, title blanks, bow direction, and cross-sheet conflicts."""
    skill_id = "SKILL_3_GAPS_AND_CONFLICTS"
    if not is_marine_pack_enabled(enabled):
        return _disabled_result(skill_id, "Marine Knowledge Pack disabled; gap/conflict check skipped.")

    scale_mm = _validate_scale_arg(verified_scale_to_mm)
    pack, rules_by_id = _pack_context()
    obs_list = _to_obs_list(observations)
    findings: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    checks_executed: list[str] = []
    checks_not_executed: list[str] = []
    limitations: list[str] = [
        "All repair suggestions are proposal_only_actions requiring CAD Core admission gates; no CAD mutation performed.",
    ]

    if not obs_list:
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "summary": "No drawing observations provided for gap/conflict detection.",
                "observed_scope": {"drawing_count": 0, "cad_geometry_verified": False},
                "applicable_regulation_scope": {"scope_checked": False},
                "partial_package": bool(partial_package),
                "findings": [],
                "checks_executed": [],
                "checks_not_executed": ["All gap and conflict checks"],
                "limitations": limitations,
                "proposal_only_actions": [],
            }
        )

    scope = _aggregate_package_scope(obs_list)
    if (
        scope["non_marine_domain_hits"]
        and scope["marine_evidence_score"] < 2
        and not scope["class_notations"]
        and "INLAND_WATERWAY" not in scope["service_areas"]
    ):
        nm_reason = (
            f"Supplied drawing(s) match non-marine mechanical/automotive domain "
            f"({', '.join(scope['non_marine_domain_hits'][:4])}); Marine Knowledge Pack is NOT_APPLICABLE."
        )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_NON_MARINE_DOMAIN",
                verdict="NOT_APPLICABLE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={"non_marine_domain_hits": scope["non_marine_domain_hits"]},
                reason=nm_reason,
            )
        )
        return validate_check_result(
            {
                "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
                "skill_id": skill_id,
                "pack_id": pack["id"],
                "pack_sha256": pack["pack_sha256"],
                "pack_status": pack["status"],
                "cad_mutation": False,
                "regulatory_compliance_proven": False,
                "status": "NOT_APPLICABLE",
                "summary": nm_reason,
                "observed_scope": scope,
                "applicable_regulation_scope": {
                    "service_areas": [],
                    "detected_scope": "NON_MARINE_OUT_OF_DOMAIN",
                    "candidate_referred_regulation": None,
                    "referred_regulation": None,
                },
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": ["Domain applicability check"],
                "checks_not_executed": ["Marine CAD gap and cross-sheet checks (non-marine domain)"],
                "limitations": limitations,
                "proposal_only_actions": [],
            }
        )

    has_ocr_only = bool(ocr_only_inputs or any(obs["ocr_only"] for obs in obs_list))
    if has_ocr_only:
        checks_executed.append("OCR-only safety boundary gate")
        checks_not_executed.append("Geometric CAD verification blocked on OCR-only inputs")
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_OCR_ONLY_REJECTED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                evidence={"ocr_only_inputs": True, "drawing_ids": [o["drawing_id"] for o in obs_list]},
                reason="OCR-only inputs cannot establish verified CAD dimensions, constraints, or PASS status.",
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=obs_list[0]["drawing_id"],
                action_kind="REQUEST_NATIVE_CAD_AND_CALIBRATION",
                evidence={"ocr_only_inputs": True},
            )
        )

    # Units & calibration gate (strict: both calibration_verified and positive verified_scale_to_mm)
    checks_executed.append("CAD $INSUNITS / calibration verification gate")
    unitless_ids = [o["drawing_id"] for o in obs_list if o["insunits"] not in _INSUNITS_TO_MM]
    calibrated = calibration_verified is True and scale_mm is not None
    if unitless_ids and not calibrated:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_UNITLESS_BLOCKED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                evidence={
                    "unitless_drawing_ids": unitless_ids,
                    "insunits_expected": [4, 5, 6],
                        "calibration_verified": calibration_verified is True,
                    "verified_scale_to_mm": scale_mm,
                },
                reason=f"Unitless CAD ($INSUNITS=0) on {', '.join(unitless_ids)} without verified calibration.",
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=unitless_ids[0],
                action_kind="SET_INSUNITS_AND_VERIFY_CALIBRATION",
                evidence={"unitless_drawing_ids": unitless_ids, "recommended_insunits": 4},
            )
        )

    # Per-drawing coherence checks: execute only substantive checks with met prerequisites (MV0-06, MV0-07)
    ran_numeric_integrity = False
    ran_title_check = False
    ran_blank_audit = False
    bow_orientation_verified_ran = False
    bow_unresolved_dids: list[str] = []
    bow_missing_dids: list[str] = []
    ran_span_check = False
    span_unavailable_dids: list[str] = []
    span_unavailable_reasons: list[str] = []
    ran_text_height_check = False
    ran_z_scale_check = False

    for obs in obs_list:
        did = obs["drawing_id"]
        part = obs["particulars"]
        if obs.get("unsupported_insert_transforms"):
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_UNSUPPORTED_INSERT_TRANSFORM_{did}",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"drawing_id": did, "unsupported_insert_transforms": obs["unsupported_insert_transforms"]},
                    reason=(
                        f"Drawing {did} contains INSERT/MINSERT block reference(s) with unsupported transform "
                        "(MINSERT array, non-uniform/negative scale, or 3D extrusion; coordinates not fabricated)."
                    ),
                )
            )
            ran_numeric_integrity = True
        if obs.get("unsupported_text_transforms"):
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_UNSUPPORTED_TEXT_TRANSFORM_{did}",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"drawing_id": did, "unsupported_text_transforms": obs["unsupported_text_transforms"]},
                    reason=(
                        f"Drawing {did} contains TEXT/ATTRIB with unsupported orientation/transform flags "
                        "(mirrored/upside-down text_generation_flag or 3D extrusion)."
                    ),
                )
            )
            ran_numeric_integrity = True
        if obs.get("skipped_entities"):
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_SKIPPED_CAD_ENTITIES_{did}",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"drawing_id": did, "skipped_entities": obs["skipped_entities"]},
                    reason=(
                        f"Drawing {did} skipped unsupported or unresolved CAD entities "
                        f"({len(obs['skipped_entities'])} item(s)) whose annotations could not be verified."
                    ),
                )
            )
            ran_numeric_integrity = True
        if obs.get("invalid_structural_metrics"):
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_INVALID_STRUCTURAL_METRIC_{did}",
                    verdict="CONFLICT",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"drawing_id": did, "invalid_structural_metrics": obs["invalid_structural_metrics"]},
                    reason=f"Non-finite or invalid structural metrics on {did}: {', '.join(obs['invalid_structural_metrics'])}.",
                )
            )
            ran_numeric_integrity = True
        if obs.get("geometry_status") in {"MISSING", "CORRUPTED", "UNEDITABLE", "NO_GEOMETRY_PRIMITIVES"}:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_CAD_GEOMETRY_MISSING_OR_UNVERIFIED",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"drawing_id": did, "geometry_status": obs.get("geometry_status"), "entity_counts": obs.get("entity_counts", {})},
                    reason=f"Drawing {did} reports geometry_status={obs.get('geometry_status')} with missing/unverified entities.",
                )
            )
            proposals.append(
                build_marine_core_proposal(
                    target_drawing_id=did,
                    action_kind="VERIFY_CAD_GEOMETRY_ENTITIES",
                    evidence={"geometry_status": obs.get("geometry_status")},
                )
            )
        if part.get("corrupted_numeric_tokens"):
            ran_numeric_integrity = True
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_CORRUPTED_NUMERIC_TOKEN",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"drawing_id": did, "corrupted_numeric_tokens": part["corrupted_numeric_tokens"]},
                    reason=f"Corrupted OCR/CAD numeric token(s) on {did}: {', '.join(part['corrupted_numeric_tokens'])}.",
                )
            )
            proposals.append(
                build_marine_core_proposal(
                    target_drawing_id=did,
                    action_kind="VERIFY_CORRUPTED_NUMERIC_TEXT",
                    evidence={"corrupted_numeric_tokens": part["corrupted_numeric_tokens"]},
                )
            )
        if part.get("unverified_unitless_particulars"):
            ran_numeric_integrity = True
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_UNVERIFIED_UNITLESS_PARTICULARS_{did}",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"drawing_id": did, "unverified_unitless_particulars": part["unverified_unitless_particulars"]},
                    reason=f"Unitless principal particulars without m/mm/cm unit on {did}: {part['unverified_unitless_particulars']}.",
                )
            )
        untrusted_obs_provs = {
            k: v
            for k, v in obs.get("metric_provenance", {}).items()
            if str(v).strip() not in _VERIFIED_PROVENANCES
        }
        if not has_ocr_only and untrusted_obs_provs:
            ran_numeric_integrity = True
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_OCR_ONLY_METRIC_{did}",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"drawing_id": did, "untrusted_metric_provenance": untrusted_obs_provs},
                    reason=f"Drawing {did} contains metrics without verified CAD/fixture provenance: {untrusted_obs_provs}.",
                )
            )

        cls = _classify_observation(obs)
        if obs.get("texts") and (cls["title_declared_type"] is not None or cls["predicted_drawing_type"] != "UNKNOWN"):
            ran_title_check = True
        has_structured_labels = bool(
            obs.get("blank_fields")
            or any(":" in e["text"] or "=" in e["text"] for e in obs.get("texts", []))
            or cls["title_declared_type"] is not None
            or cls["predicted_drawing_type"] != "UNKNOWN"
        )
        if has_structured_labels:
            ran_blank_audit = True
        if obs.get("min_plate_from_unbound_text") and cls["predicted_drawing_type"] in {
            "MIDSHIP_STRUCTURAL",
            "BASIC_STRUCTURAL",
        }:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_UNBOUND_PLATE_TEXT_{did}",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL",
                    evidence={"drawing_id": did, "unbound_plate_thicknesses_mm": part["unbound_plate_thicknesses_mm"]},
                    reason=f"Drawing {did} has unbound plate thickness text not tied to bottom/bilge/hull plating.",
                )
            )
        if cls["title_content_mismatch"]:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_TITLE_MISMATCH_{did}",
                    verdict="CONFLICT",
                    rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                    evidence={
                        "drawing_id": did,
                        "predicted_drawing_type": cls["predicted_drawing_type"],
                        "title_declared_type": cls["title_declared_type"],
                    },
                    reason=f"Title block declares {cls['title_declared_type']} while content matches {cls['predicted_drawing_type']}.",
                )
            )
            proposals.append(
                build_marine_core_proposal(
                    target_drawing_id=did,
                    action_kind="FIX_TITLE_BLOCK_TYPE_MISMATCH",
                    evidence={"predicted": cls["predicted_drawing_type"], "title": cls["title_declared_type"]},
                )
            )

        if obs["blank_fields"]:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_BLANK_TITLE_FIELDS_{did}",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                    evidence={"drawing_id": did, "blank_fields": list(obs["blank_fields"])},
                    reason=f"Drawing {did} has blank title-block fields: {', '.join(obs['blank_fields'])}.",
                )
            )
            proposals.append(
                build_marine_core_proposal(
                    target_drawing_id=did,
                    action_kind="COMPLETE_TITLE_BLOCK_FIELDS",
                    evidence={"blank_fields": list(obs["blank_fields"])},
                )
            )

        unit_factor = _INSUNITS_TO_MM.get(obs["insunits"]) or (scale_mm if calibrated else None)
        scale_denom = obs.get("claimed_scale")

        ap_anchors = part.get("ap_anchors") or [
            {"x": x, "y": None, "handle": "", "occurrence_id": "MODELSPACE"} for x in part["ap_x_coords"]
        ]
        fp_anchors = part.get("fp_anchors") or [
            {"x": x, "y": None, "handle": "", "occurrence_id": "MODELSPACE"} for x in part["fp_x_coords"]
        ]
        if ap_anchors and fp_anchors:
            grouped_aps: dict[str, list[dict[str, Any]]] = {}
            grouped_fps: dict[str, list[dict[str, Any]]] = {}
            for a in ap_anchors:
                key = str(a.get("view_id") or a.get("occurrence_id") or "MODELSPACE")
                grouped_aps.setdefault(key, []).append(a)
            for f in fp_anchors:
                key = str(f.get("view_id") or f.get("occurrence_id") or "MODELSPACE")
                grouped_fps.setdefault(key, []).append(f)

            all_groups = sorted(set(grouped_aps) | set(grouped_fps))
            reversed_occ: list[dict[str, Any]] = []
            unresolved_occ: list[dict[str, Any]] = []
            paired_spans: list[tuple[str, float]] = []
            for gk in all_groups:
                g_aps = grouped_aps.get(gk, [])
                g_fps = grouped_fps.get(gk, [])
                if not g_aps or not g_fps:
                    unresolved_occ.append({"group": gk, "ap_count": len(g_aps), "fp_count": len(g_fps)})
                    continue
                if len(g_aps) == 1 and len(g_fps) == 1:
                    ap_x = float(g_aps[0]["x"])
                    fp_x = float(g_fps[0]["x"])
                    if fp_x < ap_x - 1.0:
                        reversed_occ.append({"group": gk, "ap_x": ap_x, "fp_x": fp_x})
                    else:
                        paired_spans.append((gk, fp_x - ap_x))
                else:
                    ap_xs = [float(a["x"]) for a in g_aps]
                    fp_xs = [float(f["x"]) for f in g_fps]
                    # Without view_id partition, multiple anchors in same group can only conflict if ALL AP > ALL FP; otherwise unresolved!
                    if max(fp_xs) < min(ap_xs) - 1.0:
                        reversed_occ.append({"group": gk, "ap_x": min(ap_xs), "fp_x": max(fp_xs)})
                    else:
                        unresolved_occ.append({"group": gk, "ap_xs": ap_xs, "fp_xs": fp_xs})

            if reversed_occ:
                first_rev = reversed_occ[0]
                findings.append(
                    _make_finding(
                        rules_by_id,
                        finding_id=f"F_BOW_ORIENTATION_{did}",
                        verdict="CONFLICT",
                        rule_id="RULE_MK_04_BOW_RIGHT_AND_BODY_PLAN_HALVES",
                        evidence={
                            "drawing_id": did,
                            "ap_x": first_rev["ap_x"],
                            "fp_x": first_rev["fp_x"],
                            "reversed_occurrences": reversed_occ,
                        },
                        reason=(
                            f"Bow orientation reversed on {did} ({first_rev['group']}): "
                            f"F.P ({first_rev['fp_x']:.1f}) sits left of A.P ({first_rev['ap_x']:.1f})."
                        ),
                    )
                )
                proposals.append(
                    build_marine_core_proposal(
                        target_drawing_id=did,
                        action_kind="VERIFY_LONGLINE_BOW_TO_RIGHT",
                        evidence={"reversed_occurrences": reversed_occ},
                    )
                )
            if reversed_occ or paired_spans:
                bow_orientation_verified_ran = True
            if unresolved_occ:
                if did not in bow_unresolved_dids:
                    bow_unresolved_dids.append(did)
                if not reversed_occ:
                    findings.append(
                        _make_finding(
                            rules_by_id,
                            finding_id=f"F_BOW_ORIENTATION_UNRESOLVED_{did}",
                            verdict="INSUFFICIENT_EVIDENCE",
                            rule_id="RULE_MK_04_BOW_RIGHT_AND_BODY_PLAN_HALVES",
                            evidence={"drawing_id": did, "unresolved_anchor_groups": unresolved_occ},
                            reason=(
                                f"Multiple or unpaired A.P/F.P anchors on {did} without explicit view partitioning "
                                "prevent unambiguous bow orientation check."
                            ),
                        )
                    )

            decl_lengths = part["lpp_m_values"]
            lpp_values_unambiguous = len({round(float(value), 6) for value in decl_lengths}) == 1 if decl_lengths else False
            if paired_spans and decl_lengths and not lpp_values_unambiguous:
                findings.append(
                    _make_finding(
                        rules_by_id,
                        finding_id=f"F_AP_FP_SPAN_LPP_AMBIGUOUS_{did}",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                        evidence={"drawing_id": did, "declared_lpp_values_m": decl_lengths},
                        reason=(
                            f"Distinct Lpp declarations on {did} prevent a trustworthy AP/FP modelspace span comparison; "
                            "the span check was not executed."
                        ),
                    )
                )
            if not has_ocr_only and unit_factor is not None and lpp_values_unambiguous and decl_lengths[0] > 0 and paired_spans:
                ran_span_check = True
                decl_l = decl_lengths[0]
                span_measurements: list[dict[str, Any]] = []
                mismatched_spans: list[dict[str, Any]] = []
                for group, dx in paired_spans:
                    model_m = dx * unit_factor / 1000.0
                    rel_model = abs(model_m - decl_l) / decl_l
                    # This observer only extracts MODELSPACE geometry. A title-block
                    # plot scale is not bound to an individual view or coordinate
                    # basis and must never reconcile a modelspace length mismatch.
                    paper_m = None
                    measurement = {
                        "group": group,
                        "cad_ap_fp_dx": round(dx, 4),
                        "model_span_m": round(model_m, 4),
                        "paper_scaled_span_m": paper_m,
                        "relative_error": round(rel_model, 6),
                    }
                    span_measurements.append(measurement)
                    if rel_model > 0.25:
                        mismatched_spans.append(measurement)
                if mismatched_spans:
                    first_mismatch = mismatched_spans[0]
                    findings.append(
                        _make_finding(
                            rules_by_id,
                            finding_id="F_UNIT_OR_SCALE_MISMATCH_1000X",
                            verdict="CONFLICT",
                            rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                            evidence={
                                "drawing_id": did,
                                "declared_length_m": decl_l,
                                "cad_ap_fp_dx": first_mismatch["cad_ap_fp_dx"],
                                "insunits": obs["insunits"],
                                "unit_factor_mm": unit_factor,
                                "model_span_m": first_mismatch["model_span_m"],
                                "paper_scaled_span_m": first_mismatch["paper_scaled_span_m"],
                                "checked_ap_fp_spans": span_measurements,
                                "mismatched_ap_fp_spans": mismatched_spans,
                            },
                            reason=(
                                f"{len(mismatched_spans)} of {len(span_measurements)} supported CAD A.P-to-F.P views on {did} "
                                f"disagree with declared length {decl_l:.2f}m (likely 1000x unit or drawing scale mismatch)."
                            ),
                        )
                    )
                    proposals.append(
                        build_marine_core_proposal(
                            target_drawing_id=did,
                            action_kind="SET_INSUNITS_AND_VERIFY_CALIBRATION",
                            evidence={
                                "declared_length_m": decl_l,
                                "mismatched_ap_fp_spans": mismatched_spans,
                            },
                        )
                    )
            else:
                if did not in span_unavailable_dids:
                    span_unavailable_dids.append(did)
                miss_bits: list[str] = []
                if has_ocr_only:
                    miss_bits.append("OCR-only input")
                if unit_factor is None:
                    miss_bits.append("drawing units ($INSUNITS) unverified and no verified calibration")
                if not paired_spans:
                    miss_bits.append("paired A.P / F.P view anchors absent or unresolved")
                if not (decl_lengths and decl_lengths[0] > 0):
                    miss_bits.append("declared Lpp absent; design length L is not a substitute for A.P-to-F.P span checks")
                    if paired_spans:
                        findings.append(
                            _make_finding(
                                rules_by_id,
                                finding_id=f"F_AP_FP_SPAN_UNAVAILABLE_LPP_{did}",
                                verdict="INSUFFICIENT_EVIDENCE",
                                rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                                evidence={"drawing_id": did, "paired_span_count": len(paired_spans), "lpp_m_values": []},
                                reason="A.P-to-F.P spans cannot be checked against design length L; verified Lpp is absent.",
                            )
                        )
                span_unavailable_reasons.append(f"{did}: {', '.join(miss_bits)}")
        else:
            if did not in bow_missing_dids:
                bow_missing_dids.append(did)
            if did not in span_unavailable_dids:
                span_unavailable_dids.append(did)
            miss_bits = []
            if has_ocr_only:
                miss_bits.append("OCR-only input")
            if unit_factor is None:
                miss_bits.append("drawing units ($INSUNITS) unverified and no verified calibration")
            miss_bits.append("A.P / F.P markers absent or incomplete")
            decl_lengths = part["lpp_m_values"]
            if not (decl_lengths and decl_lengths[0] > 0):
                miss_bits.append("declared Lpp absent; design length L is not a substitute for A.P-to-F.P span checks")
            span_unavailable_reasons.append(f"{did}: {', '.join(miss_bits)}")

        # Text height check only when scale and calibrated units are known and not OCR-only
        if (
            not has_ocr_only
            and unit_factor is not None
            and isinstance(scale_denom, (int, float))
            and scale_denom > 0
            and obs["text_heights"]
        ):
            ran_text_height_check = True
            checks_executed.append(f"Text height & drafting scale check ({did})")
            printed_mm = sorted({round(h * unit_factor / scale_denom, 2) for h in obs["text_heights"]})
            too_small = [val for val in printed_mm if val < 2.5 - 1e-6]
            if too_small or len(printed_mm) > 4:
                findings.append(
                    _make_finding(
                        rules_by_id,
                        finding_id=f"F_DRAFTING_TEXT_SIZE_{did}",
                        verdict="CONFLICT",
                        rule_id="RULE_MK_05_DRAFTING_SCALE_AND_TEXT_HEIGHTS",
                        evidence={
                            "drawing_id": did,
                            "claimed_scale": scale_denom,
                            "printed_heights_mm": printed_mm,
                            "too_small_mm": too_small,
                        },
                        reason=(
                            f"Drafting text heights violate Vimaru Ch.1 on {did}: "
                            f"printed sizes={printed_mm} (must be >=2.5 mm and <=4 distinct heights)."
                        ),
                    )
                )
                proposals.append(
                    build_marine_core_proposal(
                        target_drawing_id=did,
                        action_kind="STANDARDIZE_TEXT_HEIGHTS_AT_SCALE",
                        evidence={"printed_heights_mm": printed_mm, "claimed_scale": scale_denom},
                    )
                )

        wl_span = obs.get("structural_metrics", {}).get("body_plan_wl_span_mm")
        depths = part["depth_m_values"]
        if (
            not has_ocr_only
            and unit_factor is not None
            and isinstance(wl_span, (int, float))
            and not isinstance(wl_span, bool)
            and math.isfinite(float(wl_span))
            and depths
        ):
            ran_z_scale_check = True
            depth_mm = depths[0] * 1000.0
            ratio = wl_span / depth_mm if depth_mm > 0 else 1.0
            if ratio > 1.12 or ratio < 0.88:
                findings.append(
                    _make_finding(
                        rules_by_id,
                        finding_id=f"F_Z_SCALE_DISTORTION_{did}",
                        verdict="CONFLICT",
                        rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                        evidence={"drawing_id": did, "wl_span_mm": wl_span, "depth_mm": depth_mm, "ratio": round(ratio, 3)},
                        reason=f"Body plan vertical waterline span ({wl_span:.1f} mm) distorts molded Depth ({depth_mm:.1f} mm).",
                    )
                )
                proposals.append(
                    build_marine_core_proposal(
                        target_drawing_id=did,
                        action_kind="CHECK_NON_UNIFORM_VERTICAL_SCALE",
                        evidence={"wl_span_mm": wl_span, "depth_mm": depth_mm},
                    )
                )

    cross = _collect_cross_sheet_values(obs_list, obs_drawing_types=scope["obs_drawing_types"])
    has_cross_inputs = any(bool(cross[k]) for k in cross)

    if ran_numeric_integrity or has_structured_labels or has_cross_inputs:
        checks_executed.append("CAD entity & numeric integrity audit")
    else:
        checks_not_executed.append("CAD entity & numeric integrity audit (no structured texts or metrics provided)")
    if ran_title_check:
        checks_executed.append("Title-block vs content check")
    else:
        checks_not_executed.append("Title-block vs content check (no title/content signals provided)")
    if ran_blank_audit:
        checks_executed.append("Blank title-block field audit")
    else:
        checks_not_executed.append("Blank title-block field audit (no title/colon field annotations provided)")
    if bow_orientation_verified_ran:
        checks_executed.append("Bow direction (A.P vs F.P) orientation check")
        if bow_unresolved_dids:
            checks_not_executed.append(
                f"Bow direction (A.P vs F.P) orientation check unresolved on {', '.join(bow_unresolved_dids)} "
                "(unproven A.P/F.P view association)"
            )
    elif bow_unresolved_dids:
        checks_not_executed.append(
            f"Bow direction (A.P vs F.P) orientation check (unresolved: unproven A.P/F.P view association on "
            f"{', '.join(bow_unresolved_dids)})"
        )
    else:
        checks_not_executed.append(
            "Bow direction (A.P vs F.P) orientation check (A.P / F.P markers absent or incomplete)"
        )

    if ran_span_check:
        checks_executed.append("1000x CAD A.P-to-F.P span vs declared length check")
        if span_unavailable_dids:
            checks_not_executed.append(
                f"1000x CAD A.P-to-F.P span check unavailable on {', '.join(span_unavailable_dids)} "
                f"({'; '.join(span_unavailable_reasons)})"
            )
    else:
        checks_not_executed.append(
            f"1000x CAD A.P-to-F.P span check ({'; '.join(span_unavailable_reasons) or 'prerequisites absent'})"
        )

    if not ran_z_scale_check:
        checks_not_executed.append("Body-plan Z-axis scale vs Depth check (body_plan_wl_span_mm or D absent)")

    substantive_checks_ran = sum(
        int(bool(flag))
        for flag in (
            ran_title_check,
            ran_blank_audit,
            bow_orientation_verified_ran,
            ran_span_check,
            ran_text_height_check,
            ran_z_scale_check,
            has_cross_inputs,
        )
    )
    scope["substantive_checks_ran"] = substantive_checks_ran

    implausible_s3 = _has_implausible_particulars(scope, obs_list)
    if implausible_s3:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_IMPLAUSIBLE_DIMENSIONS",
                verdict="CONFLICT",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={"implausible_issues": implausible_s3},
                reason=f"Physically implausible marine dimensions/metrics: {', '.join(implausible_s3)}.",
            )
        )

    # Cross-drawing & intra-drawing principal particulars consistency
    if has_cross_inputs:
        checks_executed.append("Cross-drawing principal particulars coherence check")
    else:
        checks_not_executed.append("Cross-drawing principal particulars coherence check (no particulars/metrics supplied)")

    if len(cross["hull_materials"]) > 1:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_HULL_MATERIAL_CONFLICT",
                verdict="CONFLICT",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={"hull_materials": cross["hull_materials"]},
                reason=f"Conflicting hull material declarations across sheets: {cross['hull_materials']}.",
            )
        )

    if len(cross["engines"]) > 1:
        eng_summary = {k: v for k, v in cross["engines"].items()}
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_MAIN_ENGINE_CONFLICT",
                verdict="CONFLICT",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={"main_engines": eng_summary},
                reason=f"Conflicting MAIN ENGINE specifications across drawings: {list(eng_summary.keys())}.",
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=obs_list[0]["drawing_id"],
                action_kind="RECONCILE_MAIN_ENGINE_SPECIFICATION",
                evidence={"main_engines": eng_summary},
            )
        )

    if len(cross["service_areas"]) > 1 or len(cross["class_notations"]) > 1:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_SERVICE_AREA_CONFLICT",
                verdict="CONFLICT",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={"service_areas": cross["service_areas"], "class_notations": cross["class_notations"]},
                reason=(
                    f"Conflicting service_area or class notations: "
                    f"service_areas={cross['service_areas']}, class={cross['class_notations']}."
                ),
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=obs_list[0]["drawing_id"],
                action_kind="RECONCILE_SERVICE_AREA_SCOPE",
                evidence={"service_areas": cross["service_areas"], "class_notations": cross["class_notations"]},
            )
        )

    if len(cross["ship_types"]) > 1:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_SHIP_TYPE_CONFLICT",
                verdict="CONFLICT",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={"ship_types": cross["ship_types"]},
                reason=f"Conflicting ship type declarations across sheets: {cross['ship_types']}.",
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=obs_list[0]["drawing_id"],
                action_kind="RECONCILE_SHIP_TYPE_AND_HULL_ID",
                evidence={"ship_types": cross["ship_types"]},
            )
        )

    if len(cross["hull_nos"]) > 1:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_HULL_NO_CONFLICT",
                verdict="CONFLICT",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={"hull_nos": cross["hull_nos"]},
                reason=f"Conflicting Hull No / yard number across sheets: {cross['hull_nos']}.",
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=obs_list[0]["drawing_id"],
                action_kind="RECONCILE_SHIP_TYPE_AND_HULL_ID",
                evidence={"hull_nos": cross["hull_nos"]},
            )
        )

    for map_key, finding_id, param_name, tol, action in (
        ("design_length_l_m", "F_DIMENSION_CONFLICT_L", "L", 0.05, "RECONCILE_L_PARTICULAR"),
        ("lpp_m", "F_DIMENSION_CONFLICT_LPP", "Lpp", 0.05, "RECONCILE_LPP_PARTICULAR"),
        ("lwl_m", "F_DIMENSION_CONFLICT_LWL", "Lwl", 0.05, "RECONCILE_LPP_PARTICULAR"),
        ("breadth_m", "F_DIMENSION_CONFLICT_B", "B", 0.05, "RECONCILE_B_PARTICULAR"),
        ("depth_m", "F_DIMENSION_CONFLICT_D", "D", 0.05, "RECONCILE_D_PARTICULAR"),
        ("draft_m", "F_DIMENSION_CONFLICT_DRAFT", "DRAFT", 0.05, "RECONCILE_DRAFT_PARTICULAR"),
        ("double_bottom_height_mm", "F_METRIC_CONFLICT_DOUBLE_BOTTOM_HEIGHT", "DOUBLE_BOTTOM_MM", 10.0, "RECONCILE_METRIC_CONFLICT"),
        ("transverse_watertight_bulkhead_count", "F_METRIC_CONFLICT_BULKHEAD_COUNT", "BULKHEAD_COUNT", 0.5, "RECONCILE_METRIC_CONFLICT"),
    ):
        buckets = cross[map_key]
        nums = sorted(float(k) for k in buckets)
        if len(nums) > 1 and (max(nums) - min(nums)) > tol:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=finding_id,
                    verdict="CONFLICT",
                    rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                    evidence={param_name: buckets},
                    reason=f"Cross-drawing conflict on {param_name}: {buckets}.",
                )
            )
            proposals.append(
                build_marine_core_proposal(
                    target_drawing_id=obs_list[0]["drawing_id"],
                    action_kind=action,
                    evidence={param_name: buckets},
                )
            )

    if partial_package:
        checks_not_executed.append("Missing companion drawings deferred per RULE_MK_07_PARTIAL_PACKAGE_BOUNDARY")

    verdicts = [f["verdict"] for f in findings]
    if "CONFLICT" in verdicts:
        overall = "CONFLICT"
    elif "INSUFFICIENT_EVIDENCE" in verdicts or has_ocr_only or (unitless_ids and not calibrated) or substantive_checks_ran == 0:
        overall = "INSUFFICIENT_EVIDENCE"
        if substantive_checks_ran == 0 and not findings:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_INSUFFICIENT_OBSERVATION_EVIDENCE",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                    evidence={"drawing_ids": [o["drawing_id"] for o in obs_list], "geometry_statuses": [o.get("geometry_status") for o in obs_list]},
                    reason="No texts, particulars, geometric entities, or structural metrics observed; cannot emit PASS.",
                )
            )
    else:
        overall = "PASS"
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_NO_GAPS_OR_CONFLICTS",
                verdict="PASS",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={"drawing_ids": [o["drawing_id"] for o in obs_list]},
                reason="No unit, orientation, drafting, title-block, or cross-drawing conflicts observed within supplied set.",
            )
        )

    summary = (
        f"Gap/conflict check over {len(obs_list)} drawing(s): status={overall}, "
        f"conflicts={sum(1 for v in verdicts if v == 'CONFLICT')}, "
        f"insufficient={sum(1 for v in verdicts if v == 'INSUFFICIENT_EVIDENCE')}, "
        f"proposals={len(proposals)}."
    )
    return validate_check_result(
        {
            "schema_version": MARINE_CHECK_RESULT_SCHEMA_VERSION,
            "skill_id": skill_id,
            "pack_id": pack["id"],
            "pack_sha256": pack["pack_sha256"],
            "pack_status": pack["status"],
            "cad_mutation": False,
            "regulatory_compliance_proven": False,
            "status": overall,
            "summary": summary,
            "observed_scope": scope,
            "applicable_regulation_scope": {"service_areas": sorted(cross["service_areas"].keys())},
            "partial_package": bool(partial_package),
            "findings": findings,
            "checks_executed": checks_executed,
            "checks_not_executed": checks_not_executed,
            "limitations": limitations,
            "proposal_only_actions": proposals,
        }
    )


__all__ = [
    "build_marine_core_proposal",
    "classify_marine_drawing",
    "detect_drawing_gaps_and_conflicts",
    "evaluate_regulation_applicability_and_submittal",
]
