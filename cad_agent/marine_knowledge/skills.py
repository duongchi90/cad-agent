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
    if (
        "proposed_value_mm" in evidence
        and evidence.get("insunits") == 0
        and not evidence.get("calibration_verified")
    ):
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
        "conditions_applied": list(rule["conditions"]),
        "exceptions_checked": list(rule["exceptions"]),
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
    corrupted_tokens: list[str] = []
    unverified_unitless: list[str] = []
    non_marine_hits: list[str] = []
    drawing_types: dict[str, str] = {}
    marine_score = 0

    for obs in obs_list:
        cls = _classify_observation(obs)
        drawing_types[obs["drawing_id"]] = cls["predicted_drawing_type"]
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
        for val in part.get("hull_nos", []):
            if val not in hull_nos:
                hull_nos.append(val)
        for val in part["ship_types"]:
            if val not in ship_types:
                ship_types.append(val)
        for val in part.get("corrupted_numeric_tokens", []):
            if val not in corrupted_tokens:
                corrupted_tokens.append(val)
        for val in part.get("unverified_unitless_particulars", []):
            if val not in unverified_unitless:
                unverified_unitless.append(val)
        for val in part.get("non_marine_domain_hits", []):
            if val not in non_marine_hits:
                non_marine_hits.append(val)

    return {
        "drawing_types_by_id": drawing_types,
        "observed_types": sorted(set(drawing_types.values())),
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
        "corrupted_numeric_tokens": corrupted_tokens,
        "unverified_unitless_particulars": unverified_unitless,
        "non_marine_domain_hits": non_marine_hits,
        "marine_evidence_score": marine_score,
        "cad_geometry_verified": False,
    }


def _length_ambiguity_band(lpp_m: float) -> float | None:
    """Return the QCVN 72 threshold when Lpp without explicit L/Lwl lies in an L-vs-Lpp transition zone."""
    bands: tuple[tuple[float, float, float], ...] = (
        (20.0, 19.0, 20.5),
        (40.0, 38.0, 40.5),
        (60.0, 57.0, 60.5),
        (80.0, 76.0, 80.5),
        (120.0, 114.0, 120.5),
        (140.0, 133.0, 140.5),
    )
    for threshold, lo, hi in bands:
        if lo <= lpp_m <= hi:
            return threshold
    return None


def _referred_regulation_for_exclusion(
    explicit_exclusions: Sequence[str],
    *,
    length_excluded: bool,
) -> str | None:
    if length_excluded or any(
        tag in {"STATUTORY_QCVN_21_SEA_SHIP", "STATUTORY_SEA_CLASS_NOTATION"}
        for tag in explicit_exclusions
    ):
        return "QCVN 21:2015/BGTVT"
    if "STATUTORY_QCVN_56_FRP_CRAFT" in explicit_exclusions:
        return "QCVN 56:2013/BGTVT"
    if "STATUTORY_QCVN_84_WOODEN_CRAFT" in explicit_exclusions:
        return "QCVN 84:2014/BGTVT"
    if "STATUTORY_QCVN_54_HSC" in explicit_exclusions:
        return "QCVN 54:2013/BGTVT"
    return None


def _required_inland_bulkheads(lpp_m: float) -> int:
    if lpp_m < 20.0:
        return 2
    if lpp_m <= 40.0:
        return 3
    if lpp_m <= 60.0:
        return 4
    if lpp_m <= 80.0:
        return 5
    return 6


def _extract_strict_metric(
    obs_list: list[dict[str, Any]],
    key: str,
    *,
    allowed_types: tuple[str, ...],
    drawing_types: Mapping[str, str],
) -> tuple[list[tuple[str, float]], list[str], list[str]]:
    eligible: list[tuple[str, float]] = []
    wrong_sheet_ids: list[str] = []
    ocr_metric_ids: list[str] = []
    for obs in obs_list:
        did = obs["drawing_id"]
        raw_val = obs.get("structural_metrics", {}).get(key)
        if not isinstance(raw_val, (int, float)) or isinstance(raw_val, bool):
            continue
        prov = str(obs.get("metric_provenance", {}).get(key, ""))
        if prov == "UNVERIFIED_OCR_TEXT" or obs.get("ocr_only"):
            ocr_metric_ids.append(did)
        if drawing_types.get(did) in allowed_types:
            eligible.append((did, float(raw_val)))
        else:
            wrong_sheet_ids.append(did)
    return eligible, wrong_sheet_ids, ocr_metric_ids


def _has_implausible_particulars(scope: Mapping[str, Any], obs_list: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    for val in scope.get("design_length_l_m_all", []) + scope.get("lpp_m_all", []) + scope.get("lwl_m_all", []):
        if val > 500.0 or val <= 0.0:
            issues.append(f"length_m={val}")
    for val in scope.get("breadth_m_all", []):
        if val > 100.0 or val <= 0.0:
            issues.append(f"breadth_m={val}")
    for val in scope.get("depth_m_all", []):
        if val > 60.0 or val <= 0.0:
            issues.append(f"depth_m={val}")
    depth_vals = scope.get("depth_m_all", [])
    draft_vals = scope.get("draft_m_all", [])
    if depth_vals and draft_vals and min(draft_vals) > max(depth_vals) + 0.05:
        issues.append(f"draft_m={min(draft_vals)}_gt_depth_m={max(depth_vals)}")
    for obs in obs_list:
        metrics = obs.get("structural_metrics", {})
        for k in ("double_bottom_height_mm", "min_plate_thickness_mm", "min_bottom_plate_mm", "min_bilge_plate_mm"):
            mv = metrics.get(k)
            if isinstance(mv, (int, float)) and not isinstance(mv, bool):
                if float(mv) <= 0.0 or (k == "double_bottom_height_mm" and float(mv) > 20000.0) or ("plate" in k and float(mv) > 150.0):
                    issues.append(f"{obs['drawing_id']}:{k}={mv}")
        bh = metrics.get("transverse_watertight_bulkhead_count")
        if isinstance(bh, (int, float)) and not isinstance(bh, bool) and int(bh) < 0:
            issues.append(f"{obs['drawing_id']}:bulkhead_count={bh}")
    return issues


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

    cross_s2 = _collect_cross_sheet_values(obs_list, drawing_types=scope["drawing_types_by_id"])
    pkg_conflicts = _cross_package_conflicts(cross_s2)
    implausible_issues = _has_implausible_particulars(scope, obs_list)
    fatal_scope_conflict = (
        ("INLAND_WATERWAY" in service_areas and ("OCEAN_GOING" in service_areas or bool(explicit_exclusions)))
        or "class_notations" in pkg_conflicts
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
                },
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": checks_executed,
                "checks_not_executed": ["QCVN 72 structural rule compliance"],
                "limitations": limitations,
                "proposal_only_actions": proposals,
            }
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

    length_excluded = (bool(design_l_all) and max(design_l_all) > 140.0) or (
        not design_l_all and bool(lpp_all) and min(lpp_all) > 140.5
    )
    if explicit_exclusions or length_excluded:
        detected = explicit_exclusions[0] if explicit_exclusions else "L_GT_140M"
        referred_reg = _referred_regulation_for_exclusion(explicit_exclusions, length_excluded=length_excluded)
        out_reason = (
            f"Target regulation {target_regulation} is NOT_APPLICABLE based on verified Clause 1.1.1 exclusion "
            f"({detected}, Lpp={lpp_m}); candidate governing regulation={referred_reg}."
        )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_SCOPE_OUT_OF_QCVN72",
                verdict="NOT_APPLICABLE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={
                    "service_areas": service_areas,
                    "explicit_exclusion_evidences": explicit_exclusions,
                    "design_length_l_m_all": design_l_all,
                    "lpp_m": lpp_m,
                    "referred_regulation": referred_reg,
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
                    "detected_scope": detected,
                    "referred_regulation": referred_reg,
                },
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": checks_executed,
                "checks_not_executed": ["All QCVN 72 inland structural rules (explicit statutory exclusion)"],
                "limitations": limitations,
                "proposal_only_actions": proposals,
            }
        )

    if "INLAND_WATERWAY" not in service_areas:
        if "OCEAN_GOING" in service_areas:
            reason = (
                "Insufficient evidence for a legal QCVN 72 applicability verdict: drawing shows bare free-text "
                "'OCEAN GOING' label without explicit Class/VR/VRH/QCVN 21/SOLAS statutory notation; missing "
                "QCVN or VR notation is not proof of non-applicability (candidate reference: QCVN 21:2015/BGTVT)."
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
                        "QCVN 21:2015/BGTVT" if "OCEAN_GOING" in service_areas else None
                    ),
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

    # Confirmed QCVN 72 scope
    findings.append(
        _make_finding(
            rules_by_id,
            finding_id="F_SCOPE_QCVN72_CONFIRMED",
            verdict="PASS",
            rule_id="RULE_MK_01_QCVN72_SCOPE",
            evidence={
                "service_areas": service_areas,
                "class_notations": scope["class_notations"],
                "lpp_m": lpp_m,
            },
            reason=f"Confirmed inland waterway scope under {target_regulation}.",
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

    # Input trustworthiness gates: calibration, OCR-only, corrupted tokens, unitless particulars, geometry
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
    units_ok = (not unitless_ids) or (bool(calibration_verified) and scale_mm is not None)

    lwl_all = scope["lwl_m_all"]
    effective_l_m: float | None = None
    length_basis = "UNAVAILABLE"
    ambig_threshold: float | None = None
    if design_l_all:
        effective_l_m = design_l_all[0]
        length_basis = "EXPLICIT_DESIGN_LENGTH_L"
    elif lpp_all and lwl_all:
        effective_l_m = round(max(lpp_all[0], 0.96 * lwl_all[0]), 4)
        length_basis = "MAX_LPP_OR_96PCT_LWL"
    elif lwl_all:
        effective_l_m = round(0.96 * lwl_all[0], 4)
        length_basis = "ESTIMATED_96PCT_LWL"
    elif lpp_all:
        ambig_threshold = _length_ambiguity_band(lpp_all[0])
        if ambig_threshold is None:
            effective_l_m = lpp_all[0]
            length_basis = "LPP_FAR_FROM_RULE_THRESHOLD"
        else:
            length_basis = f"LPP_IN_THRESHOLD_BAND_{ambig_threshold:.0f}M"

    dims_blocked = False
    if has_ocr_only:
        dims_blocked = True
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_OCR_ONLY_REJECTED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                evidence={"ocr_only_drawing_ids": [o["drawing_id"] for o in obs_list if o["ocr_only"]]},
                reason="OCR-only inputs cannot establish verified QCVN 72 structural compliance or PASS.",
            )
        )
    if corrupted_tokens:
        dims_blocked = True
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
        dims_blocked = True
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
        dims_blocked = True
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
        dims_blocked = True
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_UNITS_UNVERIFIED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                evidence={
                    "unitless_drawing_ids": unitless_ids,
                    "calibration_verified": bool(calibration_verified),
                    "verified_scale_to_mm": scale_mm,
                },
                reason=(
                    "Unitless CAD ($INSUNITS=0) requires BOTH calibration_verified=True and valid "
                    "verified_scale_to_mm>0 before dimensional QCVN 72 checks."
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
    if ambig_threshold is not None:
        dims_blocked = True
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_LENGTH_L_VS_LPP_AMBIGUOUS",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                evidence={"lpp_m": lpp_all[0], "rule_threshold_m": ambig_threshold, "length_basis": length_basis},
                reason=(
                    f"Lpp={lpp_all[0]:.2f}m lies near QCVN 72 rule threshold {ambig_threshold:.0f}m without explicit "
                    "rule length L or Lwl; L vs Lpp ambiguity blocks threshold determination."
                ),
            )
        )
    elif effective_l_m is None:
        dims_blocked = True
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_MISSING_VESSEL_LENGTH",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                evidence={"drawing_ids": [o["drawing_id"] for o in obs_list]},
                reason="Vessel rule length L / Lpp / Lwl is missing; dimensional QCVN 72 rules cannot be verified.",
            )
        )

    structural_checks_ran = 0
    if dims_blocked or effective_l_m is None:
        checks_not_executed.append("Dimensional QCVN 72 scantling/bulkhead rules blocked by input/unit/length gate")
    else:
        # Check RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT (dry-cargo GENERAL_ARRANGEMENT / BASIC_STRUCTURAL only)
        bh_pairs, bh_wrong, bh_ocr = _extract_strict_metric(
            obs_list,
            "transverse_watertight_bulkhead_count",
            allowed_types=("GENERAL_ARRANGEMENT", "BASIC_STRUCTURAL"),
            drawing_types=scope["drawing_types_by_id"],
        )
        if bh_wrong:
            checks_not_executed.append(
                f"Watertight bulkhead count on non-GA/KCCB sheet(s) {', '.join(bh_wrong)} excluded"
            )
        special_bh_types = [
            st for st in scope["ship_types"]
            if any(tok in st for tok in ("TANKER", "CHỞ DẦU", "CHO DAU", "PASSENGER", "KHÁCH", "KHACH", "BARGE", "SÀ LAN", "SA LAN"))
        ]
        if bh_pairs and bh_ocr:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_OCR_METRIC_BULKHEAD",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                    evidence={"ocr_drawing_ids": bh_ocr},
                    reason="Bulkhead count sourced from unverified OCR text cannot produce PASS.",
                )
            )
        elif bh_pairs and special_bh_types:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_BULKHEAD_SHIP_TYPE_SPECIAL_REVIEW",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                    evidence={"ship_types": special_bh_types, "effective_l_m": effective_l_m},
                    reason=(
                        f"Dry-cargo bulkhead table does not prove compliance for specialized ship type "
                        f"({', '.join(special_bh_types)})."
                    ),
                )
            )
        elif bh_pairs:
            checks_executed.append("RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
            structural_checks_ran += 1
            worst_did, min_bh = min(bh_pairs, key=lambda pair: pair[1])
            req_bh = _required_inland_bulkheads(effective_l_m)
            bh_verdict = "PASS" if int(min_bh) >= req_bh else "CONFLICT"
            bh_reason = (
                f"Effective L={effective_l_m:.2f}m ({length_basis}) requires >= {req_bh} transverse "
                f"watertight bulkheads; observed {int(min_bh)} on {worst_did}."
            )
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_WATERTIGHT_BULKHEAD_COUNT",
                    verdict=bh_verdict,
                    rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                    evidence={
                        "drawing_id": worst_did,
                        "effective_l_m": effective_l_m,
                        "length_basis": length_basis,
                        "observed_bulkheads": int(min_bh),
                        "required_min": req_bh,
                    },
                    reason=bh_reason,
                )
            )
            if bh_verdict == "CONFLICT":
                proposals.append(
                    build_marine_core_proposal(
                        target_drawing_id=worst_did,
                        action_kind="REVIEW_WATERTIGHT_BULKHEAD_SUBDIVISION",
                        evidence={"observed": int(min_bh), "required_min": req_bh, "effective_l_m": effective_l_m},
                    )
                )
        elif "GENERAL_ARRANGEMENT" in observed_types or "BASIC_STRUCTURAL" in observed_types:
            checks_not_executed.append("Watertight bulkhead count (transverse_watertight_bulkhead_count not annotated/extracted)")

        # Check RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT (MIDSHIP_STRUCTURAL / BASIC_STRUCTURAL only)
        db_pairs, db_wrong, db_ocr = _extract_strict_metric(
            obs_list,
            "double_bottom_height_mm",
            allowed_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
            drawing_types=scope["drawing_types_by_id"],
        )
        if db_wrong:
            checks_not_executed.append(
                f"Double-bottom height on non-structural sheet(s) {', '.join(db_wrong)} excluded"
            )
        girder_pairs, _, _ = _extract_strict_metric(
            obs_list,
            "bottom_girder_max_spacing_mm",
            allowed_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
            drawing_types=scope["drawing_types_by_id"],
        )
        floor_pairs, _, _ = _extract_strict_metric(
            obs_list,
            "transverse_floor_max_spacing_mm",
            allowed_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
            drawing_types=scope["drawing_types_by_id"],
        )
        if db_pairs and db_ocr:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_OCR_METRIC_DOUBLE_BOTTOM",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                    evidence={"ocr_drawing_ids": db_ocr},
                    reason="Double-bottom dimensions from unverified OCR text cannot produce PASS.",
                )
            )
        elif db_pairs:
            checks_executed.append("RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT")
            structural_checks_ran += 1
            worst_db_id, min_db_mm = min(db_pairs, key=lambda pair: pair[1])
            req_db_mm = 700.0 if effective_l_m <= 120.0 else 900.0
            max_girder_pair = max(girder_pairs, key=lambda pair: pair[1]) if girder_pairs else None
            max_floor_pair = max(floor_pairs, key=lambda pair: pair[1]) if floor_pairs else None
            girder_fail = max_girder_pair is not None and max_girder_pair[1] > 3000.0
            floor_fail = max_floor_pair is not None and max_floor_pair[1] > 2400.0
            db_verdict = "CONFLICT" if (min_db_mm < req_db_mm or girder_fail or floor_fail) else "PASS"
            db_reason = (
                f"Double bottom at CL observed {min_db_mm:.1f} mm on {worst_db_id} "
                f"(min required {req_db_mm:.1f} mm for L={effective_l_m:.2f}m)"
            )
            if max_girder_pair is not None:
                db_reason += f"; max girder spacing {max_girder_pair[1]:.1f} mm (limit <= 3000.0 mm)"
            if max_floor_pair is not None:
                db_reason += f"; max floor spacing {max_floor_pair[1]:.1f} mm (upper limit <= 2400.0 mm)"
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_DOUBLE_BOTTOM_HEIGHT",
                    verdict=db_verdict,
                    rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                    evidence={
                        "drawing_id": worst_db_id,
                        "observed_db_height_mm": min_db_mm,
                        "required_min_db_height_mm": req_db_mm,
                        "max_girder_spacing_mm": max_girder_pair[1] if max_girder_pair else None,
                        "max_floor_spacing_mm": max_floor_pair[1] if max_floor_pair else None,
                    },
                    reason=db_reason,
                )
            )
            if db_verdict == "CONFLICT":
                proposals.append(
                    build_marine_core_proposal(
                        target_drawing_id=worst_db_id,
                        action_kind="REVIEW_DOUBLE_BOTTOM_SCANTLINGS",
                        evidence={"observed_db_height_mm": min_db_mm, "required_min_mm": req_db_mm},
                    )
                )

        # Check RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL (only L < 20 m on MIDSHIP/BASIC)
        plate_pairs, pl_wrong, pl_ocr = _extract_strict_metric(
            obs_list,
            "min_plate_thickness_mm",
            allowed_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
            drawing_types=scope["drawing_types_by_id"],
        )
        bot_pairs, _, _ = _extract_strict_metric(
            obs_list,
            "min_bottom_plate_mm",
            allowed_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
            drawing_types=scope["drawing_types_by_id"],
        )
        bilge_pairs, _, _ = _extract_strict_metric(
            obs_list,
            "min_bilge_plate_mm",
            allowed_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
            drawing_types=scope["drawing_types_by_id"],
        )
        if pl_wrong:
            checks_not_executed.append(
                f"Small-hull plate thickness on non-structural sheet(s) {', '.join(pl_wrong)} excluded"
            )
        unbound_pl_ids = [
            obs["drawing_id"]
            for obs in obs_list
            if obs.get("min_plate_from_unbound_text")
            and scope["drawing_types_by_id"].get(obs["drawing_id"]) in {"MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"}
        ]
        if unbound_pl_ids and effective_l_m < 20.0:
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
                )
            )
        if plate_pairs and pl_ocr:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_OCR_METRIC_PLATE",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL",
                    evidence={"ocr_drawing_ids": pl_ocr},
                    reason="Plate thickness values from unverified OCR text cannot produce PASS.",
                )
            )
        elif plate_pairs and effective_l_m < 20.0:
            checks_executed.append("RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL")
            structural_checks_ran += 1
            worst_pl_id, min_pl_mm = min(plate_pairs, key=lambda pair: pair[1])
            min_bot = min(bot_pairs, key=lambda pair: pair[1])[1] if bot_pairs else None
            min_bilge = min(bilge_pairs, key=lambda pair: pair[1])[1] if bilge_pairs else None
            pl_fail = (
                min_pl_mm < 2.5
                or (min_bot is not None and min_bot < 3.0)
                or (min_bilge is not None and min_bilge < 4.0)
            )
            pl_incomplete = (
                not pl_fail
                and min_pl_mm < 4.0
                and (min_bot is None or min_bilge is None)
            )
            if pl_fail:
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
                        "min_plate_thickness_mm": min_pl_mm,
                        "min_bottom_plate_mm": min_bot,
                        "min_bilge_plate_mm": min_bilge,
                        "floor_mm": 2.5,
                        "bottom_floor_mm": 3.0,
                        "bilge_floor_mm": 4.0,
                    },
                    reason=(
                        f"L < 20m small-hull plating min={min_pl_mm:.2f} mm (3.7.2 floor 2.5 mm; "
                        "3.7.3 bottom>=3.0 mm and bilge>=4.0 mm required unless all hull plates >= 4.0 mm)."
                    ),
                )
            )
        elif effective_l_m >= 20.0:
            checks_not_executed.append("RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL (L >= 20m outside Ch.3 <20m floor rule)")

        if structural_checks_ran == 0:
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
    elif "INSUFFICIENT_EVIDENCE" in verdicts or dims_blocked or structural_checks_ran == 0:
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
                "class_notations": scope["class_notations"],
                "effective_l_m": effective_l_m,
                "length_basis": length_basis,
                "lpp_m": lpp_m,
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
    drawing_types: Mapping[str, str] | None = None,
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
    hull_nos: dict[str, list[str]] = {}
    db_map: dict[str, list[str]] = {}
    bh_map: dict[str, list[str]] = {}

    if drawing_types is None:
        drawing_types = {obs["drawing_id"]: _classify_observation(obs)["predicted_drawing_type"] for obs in obs_list}

    for obs in obs_list:
        did = obs["drawing_id"]
        dtype = drawing_types.get(did, "UNKNOWN")
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
        for hno in part.get("hull_nos", []):
            hull_nos.setdefault(hno.upper(), []).append(f"{did}:{hno}")
        sm = obs.get("structural_metrics", {})
        db_val = sm.get("double_bottom_height_mm")
        if (
            isinstance(db_val, (int, float))
            and not isinstance(db_val, bool)
            and dtype in {"MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"}
        ):
            db_map.setdefault(f"{float(db_val):.1f}", []).append(did)
        bh_val = sm.get("transverse_watertight_bulkhead_count")
        if (
            isinstance(bh_val, (int, float))
            and not isinstance(bh_val, bool)
            and dtype in {"GENERAL_ARRANGEMENT", "BASIC_STRUCTURAL"}
        ):
            bh_map.setdefault(str(int(bh_val)), []).append(did)

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
    calibrated = bool(calibration_verified) and scale_mm is not None
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
                    "calibration_verified": bool(calibration_verified),
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

    # Per-drawing coherence checks: geometry, corrupted numbers, title mismatch, blanks, bow orientation, text heights, Z compression, 1000x span
    checks_executed.extend(
        [
            "CAD entity & numeric integrity audit",
            "Title-block vs content check",
            "Blank title-block field audit",
            "Bow direction (A.P vs F.P) and 1000x CAD span check",
        ]
    )
    for obs in obs_list:
        did = obs["drawing_id"]
        part = obs["particulars"]
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
        if not has_ocr_only and any(v == "UNVERIFIED_OCR_TEXT" for v in obs.get("metric_provenance", {}).values()):
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_OCR_ONLY_METRIC_{did}",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"drawing_id": did, "metric_provenance": obs.get("metric_provenance")},
                    reason=f"Drawing {did} contains metrics with UNVERIFIED_OCR_TEXT provenance.",
                )
            )

        cls = _classify_observation(obs)
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

        ap_coords = part["ap_x_coords"]
        fp_coords = part["fp_x_coords"]
        if ap_coords and fp_coords:
            ap_mean = sum(ap_coords) / len(ap_coords)
            fp_mean = sum(fp_coords) / len(fp_coords)
            if fp_mean < ap_mean - 1.0:
                findings.append(
                    _make_finding(
                        rules_by_id,
                        finding_id=f"F_BOW_ORIENTATION_{did}",
                        verdict="CONFLICT",
                        rule_id="RULE_MK_04_BOW_RIGHT_AND_BODY_PLAN_HALVES",
                        evidence={"drawing_id": did, "ap_x": ap_mean, "fp_x": fp_mean},
                        reason=f"Bow orientation reversed on {did}: F.P ({fp_mean:.1f}) sits left of A.P ({ap_mean:.1f}).",
                    )
                )
                proposals.append(
                    build_marine_core_proposal(
                        target_drawing_id=did,
                        action_kind="VERIFY_LONGLINE_BOW_TO_RIGHT",
                        evidence={"ap_x": ap_mean, "fp_x": fp_mean},
                    )
                )
            decl_lengths = part.get("design_length_l_m_values") or part["lpp_m_values"]
            if not has_ocr_only and unit_factor is not None and decl_lengths and decl_lengths[0] > 0:
                decl_l = decl_lengths[0]
                dx = abs(fp_mean - ap_mean)
                model_m = dx * unit_factor / 1000.0
                paper_m = (
                    model_m * scale_denom
                    if isinstance(scale_denom, (int, float)) and scale_denom > 0
                    else None
                )
                rel_model = abs(model_m - decl_l) / decl_l
                rel_paper = abs(paper_m - decl_l) / decl_l if paper_m is not None else rel_model
                best_rel = min(rel_model, rel_paper)
                if best_rel > 0.25:
                    findings.append(
                        _make_finding(
                            rules_by_id,
                            finding_id="F_UNIT_OR_SCALE_MISMATCH_1000X",
                            verdict="CONFLICT",
                            rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                            evidence={
                                "drawing_id": did,
                                "declared_length_m": decl_l,
                                "cad_ap_fp_dx": round(dx, 4),
                                "insunits": obs["insunits"],
                                "unit_factor_mm": unit_factor,
                                "model_span_m": round(model_m, 4),
                                "paper_scaled_span_m": round(paper_m, 4) if paper_m is not None else None,
                            },
                            reason=(
                                f"CAD A.P-to-F.P span on {did} ({model_m:.4f}m model) disagrees with declared "
                                f"length {decl_l:.2f}m (likely 1000x unit or drawing scale mismatch)."
                            ),
                        )
                    )
                    proposals.append(
                        build_marine_core_proposal(
                            target_drawing_id=did,
                            action_kind="SET_INSUNITS_AND_VERIFY_CALIBRATION",
                            evidence={"declared_length_m": decl_l, "model_span_m": round(model_m, 4)},
                        )
                    )

        # Text height check only when scale and calibrated units are known and not OCR-only
        if (
            not has_ocr_only
            and unit_factor is not None
            and isinstance(scale_denom, (int, float))
            and scale_denom > 0
            and obs["text_heights"]
        ):
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
            and depths
        ):
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
    checks_executed.append("Cross-drawing principal particulars coherence check")
    cross = _collect_cross_sheet_values(obs_list)

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
    elif "INSUFFICIENT_EVIDENCE" in verdicts or has_ocr_only or (unitless_ids and not calibrated):
        overall = "INSUFFICIENT_EVIDENCE"
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
