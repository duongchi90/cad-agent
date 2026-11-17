"""Read-only Marine Knowledge Pack V0 engineering skills and CAD Core proposal gate."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import re
from typing import Any

from .contracts import (
    MARINE_CHECK_RESULT_SCHEMA_VERSION,
    MarineKnowledgeError,
    SUPPORTED_REGULATIONS,
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


def build_marine_core_proposal(
    *,
    target_drawing_id: str,
    action_kind: str,
    evidence: Mapping[str, Any],
    reason: str = "",
) -> dict[str, Any]:
    """Build a strictly non-mutating CAD Core proposal requiring downstream gate admission."""
    if not isinstance(target_drawing_id, str) or not target_drawing_id.strip():
        raise MarineKnowledgeError("PROPOSAL_TARGET_INVALID")
    if not isinstance(action_kind, str) or not action_kind.strip():
        raise MarineKnowledgeError("PROPOSAL_ACTION_INVALID")
    if not isinstance(evidence, Mapping):
        raise MarineKnowledgeError("PROPOSAL_EVIDENCE_INVALID")
    clean_target = target_drawing_id.strip()
    clean_action = action_kind.strip()
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
    if cls["predicted_drawing_type"] == "UNKNOWN":
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
            "observed_scope": {
                **cls,
                "detected_service_areas": list(obs["particulars"]["service_areas"]),
                "detected_class_notations": list(obs["particulars"]["class_notations"]),
            },
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
    lpp_values: list[float] = []
    ship_types: list[str] = []
    drawing_types: dict[str, str] = {}

    for obs in obs_list:
        cls = _classify_observation(obs)
        drawing_types[obs["drawing_id"]] = cls["predicted_drawing_type"]
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
        for val in part["lpp_m_values"]:
            lpp_values.append(val)
        for val in part["ship_types"]:
            if val not in ship_types:
                ship_types.append(val)

    return {
        "drawing_types_by_id": drawing_types,
        "observed_types": sorted(set(drawing_types.values())),
        "service_areas": service_areas,
        "class_notations": class_notations,
        "explicit_exclusion_evidences": explicit_exclusions,
        "lpp_m": lpp_values[0] if lpp_values else None,
        "lpp_m_all": sorted(set(lpp_values)),
        "ship_types": ship_types,
    }


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


def _extract_worst_metric(
    obs_list: list[dict[str, Any]],
    key: str,
    *,
    preferred_types: tuple[str, ...],
    drawing_types: Mapping[str, str],
) -> list[tuple[str, float]]:
    preferred: list[tuple[str, float]] = []
    fallback: list[tuple[str, float]] = []
    for obs in obs_list:
        raw_val = obs.get("structural_metrics", {}).get(key)
        if isinstance(raw_val, (int, float)) and not isinstance(raw_val, bool):
            pair = (obs["drawing_id"], float(raw_val))
            if drawing_types.get(obs["drawing_id"]) in preferred_types:
                preferred.append(pair)
            else:
                fallback.append(pair)
    return preferred if preferred else fallback


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

    lpp_conflict = len(lpp_all) > 1 and (max(lpp_all) - min(lpp_all)) > 0.05
    scope_conflict = (
        ("INLAND_WATERWAY" in service_areas and ("OCEAN_GOING" in service_areas or bool(explicit_exclusions)))
        or len(class_notations) > 1
        or lpp_conflict
    )
    if scope_conflict:
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
                    "lpp_m_all": lpp_all,
                },
                reason="Conflicting service_area, class notation, or Lpp declarations across submittal.",
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=obs_list[0]["drawing_id"],
                action_kind="RECONCILE_SERVICE_AREA_SCOPE",
                evidence={"service_areas": service_areas, "class_notations": class_notations, "lpp_m_all": lpp_all},
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
                "summary": "Conflicting inland vs sea/exclusion scope or particulars prevents QCVN 72 determination.",
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

    length_excluded = lpp_m is not None and lpp_m > 140.0
    if explicit_exclusions or length_excluded:
        detected = explicit_exclusions[0] if explicit_exclusions else "L_GT_140M"
        out_reason = (
            f"Target regulation {target_regulation} is NOT_APPLICABLE based on verified Clause 1.1.1 exclusion "
            f"({detected}, Lpp={lpp_m}): refer to governing sea/special regulation (e.g. QCVN 21:2015/BGTVT)."
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
                    "lpp_m": lpp_m,
                    "referred_regulation": "QCVN 21:2015/BGTVT",
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
                    "referred_regulation": "QCVN 21:2015/BGTVT",
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

    # Unit calibration gate for geometric/structural dimension checks
    unitless_ids = [
        o["drawing_id"] for o in obs_list if o["insunits"] not in _INSUNITS_TO_MM
    ]
    units_ok = (not unitless_ids) or calibration_verified or (verified_scale_to_mm is not None and verified_scale_to_mm > 0)
    if not units_ok:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_UNITS_UNVERIFIED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                evidence={"unitless_drawing_ids": unitless_ids, "calibration_verified": calibration_verified},
                reason="Unitless CAD ($INSUNITS=0) without verified calibration blocks PASS on dimensional QCVN 72 checks.",
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=unitless_ids[0],
                action_kind="SET_INSUNITS_AND_VERIFY_CALIBRATION",
                evidence={"unitless_drawing_ids": unitless_ids},
            )
        )
        checks_not_executed.append("Dimensional QCVN 72 scantling/bulkhead rules blocked pending unit calibration")
    else:
        # Check RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT
        bh_pairs = _extract_worst_metric(
            obs_list,
            "transverse_watertight_bulkhead_count",
            preferred_types=("GENERAL_ARRANGEMENT", "BASIC_STRUCTURAL"),
            drawing_types=scope["drawing_types_by_id"],
        )
        if bh_pairs and lpp_m is not None:
            checks_executed.append("RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT")
            worst_did, min_bh = min(bh_pairs, key=lambda pair: pair[1])
            req_bh = _required_inland_bulkheads(lpp_m)
            bh_verdict = "PASS" if int(min_bh) >= req_bh else "CONFLICT"
            bh_reason = (
                f"Lpp={lpp_m:.2f}m requires >= {req_bh} transverse watertight bulkheads; "
                f"observed {int(min_bh)} on {worst_did}."
            )
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_WATERTIGHT_BULKHEAD_COUNT",
                    verdict=bh_verdict,
                    rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                    evidence={"drawing_id": worst_did, "lpp_m": lpp_m, "observed_bulkheads": int(min_bh), "required_min": req_bh},
                    reason=bh_reason,
                )
            )
            if bh_verdict == "CONFLICT":
                proposals.append(
                    build_marine_core_proposal(
                        target_drawing_id=worst_did,
                        action_kind="REVIEW_WATERTIGHT_BULKHEAD_SUBDIVISION",
                        evidence={"observed": int(min_bh), "required_min": req_bh, "lpp_m": lpp_m},
                    )
                )
        elif "GENERAL_ARRANGEMENT" in observed_types or "BASIC_STRUCTURAL" in observed_types:
            checks_not_executed.append("Watertight bulkhead count (transverse_watertight_bulkhead_count not annotated/extracted)")

        # Check RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT
        db_pairs = _extract_worst_metric(
            obs_list,
            "double_bottom_height_mm",
            preferred_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
            drawing_types=scope["drawing_types_by_id"],
        )
        girder_pairs = _extract_worst_metric(
            obs_list,
            "bottom_girder_max_spacing_mm",
            preferred_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
            drawing_types=scope["drawing_types_by_id"],
        )
        if db_pairs and lpp_m is not None:
            checks_executed.append("RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT")
            worst_db_id, min_db_mm = min(db_pairs, key=lambda pair: pair[1])
            req_db_mm = 700.0 if lpp_m <= 120.0 else 900.0
            max_girder_pair = max(girder_pairs, key=lambda pair: pair[1]) if girder_pairs else None
            girder_fail = max_girder_pair is not None and max_girder_pair[1] > 3000.0
            db_verdict = "CONFLICT" if (min_db_mm < req_db_mm or girder_fail) else "PASS"
            db_reason = (
                f"Double bottom at CL observed {min_db_mm:.1f} mm on {worst_db_id} "
                f"(min required {req_db_mm:.1f} mm for Lpp={lpp_m:.2f}m)"
            )
            if max_girder_pair is not None:
                db_reason += f"; max bottom girder spacing {max_girder_pair[1]:.1f} mm (limit <= 3000.0 mm)."
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

        # Check RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL (only L < 20 m)
        plate_pairs = _extract_worst_metric(
            obs_list,
            "min_plate_thickness_mm",
            preferred_types=("MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"),
            drawing_types=scope["drawing_types_by_id"],
        )
        if plate_pairs and lpp_m is not None and lpp_m < 20.0:
            checks_executed.append("RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL")
            worst_pl_id, min_pl_mm = min(plate_pairs, key=lambda pair: pair[1])
            pl_verdict = "PASS" if min_pl_mm >= 2.5 else "CONFLICT"
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_SMALL_HULL_MIN_PLATE",
                    verdict=pl_verdict,
                    rule_id="RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL",
                    evidence={"drawing_id": worst_pl_id, "min_plate_thickness_mm": min_pl_mm, "floor_mm": 2.5},
                    reason=f"L < 20m small-hull plate thickness min={min_pl_mm:.2f} mm (absolute floor 2.5 mm).",
                )
            )
        elif lpp_m is not None and lpp_m >= 20.0:
            checks_not_executed.append("RULE_MK_10_STEEL_MIN_THICKNESS_SMALL_HULL (Lpp >= 20m outside Ch.3 <20m floor rule)")

    verdicts = [f["verdict"] for f in findings]
    if "CONFLICT" in verdicts:
        overall = "CONFLICT"
    elif "INSUFFICIENT_EVIDENCE" in verdicts:
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
) -> dict[str, dict[str, list[str]]]:
    engines: dict[str, list[str]] = {}
    service_areas: dict[str, list[str]] = {}
    lpp_map: dict[str, list[str]] = {}
    breadth_map: dict[str, list[str]] = {}
    depth_map: dict[str, list[str]] = {}

    for obs in obs_list:
        did = obs["drawing_id"]
        part = obs["particulars"]
        for eng in part["main_engine_values"]:
            engines.setdefault(_norm_engine(eng), []).append(f"{did}:{eng}")
        for sa in part["service_areas"]:
            service_areas.setdefault(sa, []).append(did)
        for val in part["lpp_m_values"]:
            lpp_map.setdefault(f"{val:.2f}", []).append(did)
        for val in part["breadth_m_values"]:
            breadth_map.setdefault(f"{val:.2f}", []).append(did)
        for val in part["depth_m_values"]:
            depth_map.setdefault(f"{val:.2f}", []).append(did)

    return {
        "engines": engines,
        "service_areas": service_areas,
        "lpp_m": lpp_map,
        "breadth_m": breadth_map,
        "depth_m": depth_map,
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
                "observed_scope": {"drawing_count": 0},
                "applicable_regulation_scope": {"scope_checked": False},
                "partial_package": bool(partial_package),
                "findings": [],
                "checks_executed": [],
                "checks_not_executed": ["All gap and conflict checks"],
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

    # Units & calibration gate
    checks_executed.append("CAD $INSUNITS / calibration verification gate")
    unitless_ids = [o["drawing_id"] for o in obs_list if o["insunits"] not in _INSUNITS_TO_MM]
    calibrated = calibration_verified or (verified_scale_to_mm is not None and verified_scale_to_mm > 0)
    if unitless_ids and not calibrated:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_UNITLESS_BLOCKED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                evidence={"unitless_drawing_ids": unitless_ids, "insunits_expected": [4, 5, 6]},
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

    # Per-drawing coherence checks: title mismatch, blanks, bow orientation, text heights, Z compression
    checks_executed.extend(
        [
            "Title-block vs content check",
            "Blank title-block field audit",
            "Bow direction (A.P vs F.P) check",
        ]
    )
    for obs in obs_list:
        did = obs["drawing_id"]
        cls = _classify_observation(obs)
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

        ap_coords = obs["particulars"]["ap_x_coords"]
        fp_coords = obs["particulars"]["fp_x_coords"]
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

        # Text height check only when scale and units are known and not OCR-only
        unit_factor = (
            _INSUNITS_TO_MM.get(obs["insunits"])
            or (float(verified_scale_to_mm) if verified_scale_to_mm and verified_scale_to_mm > 0 else None)
        )
        scale_denom = obs.get("claimed_scale")
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
        depths = obs["particulars"]["depth_m_values"]
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

    # Cross-drawing principal particulars consistency
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

    if len(cross["service_areas"]) > 1:
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_SERVICE_AREA_CONFLICT",
                verdict="CONFLICT",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={"service_areas": cross["service_areas"]},
                reason=f"Conflicting service_area declarations across drawings: {cross['service_areas']}.",
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=obs_list[0]["drawing_id"],
                action_kind="RECONCILE_SERVICE_AREA_SCOPE",
                evidence={"service_areas": cross["service_areas"]},
            )
        )

    for param_name, buckets in (("Lpp", cross["lpp_m"]), ("B", cross["breadth_m"]), ("D", cross["depth_m"])):
        nums = sorted(float(k) for k in buckets)
        if len(nums) > 1 and (max(nums) - min(nums)) > 0.05:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_DIMENSION_CONFLICT_{param_name.upper()}",
                    verdict="CONFLICT",
                    rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                    evidence={param_name: buckets},
                    reason=f"Cross-drawing conflict on {param_name}: {buckets}.",
                )
            )
            proposals.append(
                build_marine_core_proposal(
                    target_drawing_id=obs_list[0]["drawing_id"],
                    action_kind=f"RECONCILE_{param_name.upper()}_PARTICULAR",
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
            "observed_scope": _aggregate_package_scope(obs_list),
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
