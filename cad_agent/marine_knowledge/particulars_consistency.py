"""Cross-Drawing Engineering Particulars Consistency Report (Marine V1-B).

Consumes hash-bound ``engineering-fact-1.0`` records (V1-A) to reconcile
principal dimensions, vessel identity, class/service scope, bulkhead counts,
and structured main-engine specifications across sheets without mutating CAD
Core or raising false conflicts across unrelated vessels, revisions, units, or
distinct naval-architecture length concepts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import re
from typing import Any

from .contracts import (
    MARINE_CHECK_RESULT_SCHEMA_VERSION,
    MarineKnowledgeError,
    validate_check_result,
)
from .evidence_binding import rebind_observation_dimensions, validate_engineering_fact
from .pack import is_marine_pack_enabled
from .skills import (
    _classify_observation,
    _disabled_result,
    _make_finding,
    _pack_context,
    _to_obs_list,
    _validate_calibration_flag,
    _validate_scale_arg,
    build_marine_core_proposal,
)
from .text_normalization import fold_marine_search_text, normalize_marine_cad_text

_TRUSTED_FACT_STATES: frozenset[str] = frozenset({"VERIFIED", "FIXTURE_UNBOUND_TO_DXF_BYTES"})

_PRINCIPAL_DIM_KEYS: tuple[str, ...] = (
    "loa_m",
    "lwl_m",
    "design_length_l_m",
    "lpp_m",
    "breadth_m",
    "depth_m",
    "draft_m",
)

_DIM_PROPOSAL_ACTION: dict[str, str] = {
    "loa_m": "RECONCILE_L_PARTICULAR",
    "lwl_m": "RECONCILE_L_PARTICULAR",
    "design_length_l_m": "RECONCILE_L_PARTICULAR",
    "lpp_m": "RECONCILE_LPP_PARTICULAR",
    "breadth_m": "RECONCILE_B_PARTICULAR",
    "depth_m": "RECONCILE_D_PARTICULAR",
    "draft_m": "RECONCILE_DRAFT_PARTICULAR",
}

_PROJECT_CODE_RE = re.compile(
    r"\b(SF\s*[-_]?\s*\d{2}\s*[-_]\s*\d{2}|"
    r"(?:PROJ(?:ECT)?|DU\s+AN|DESIGN\s+NO|MA\s+THIET\s+KE)\s*[:=-]?\s*[A-Z0-9]{2,}(?:[\s_-]*[A-Z0-9]+)*)\b",
    re.IGNORECASE,
)

_POWER_TOKEN_RE = re.compile(
    r"(?:(?P<mul>\d+)\s*[x×]\s*)?(?P<num>[0-9]+(?:[.,][0-9]+)?)\s*(?P<unit>kw|bhp|hp|cv|ps)\b"
    r"(?:\s*(?P<each>each|per\s+engine|moi\s+may))?",
    re.IGNORECASE,
)
_PREFIX_COUNT_RE = re.compile(r"^\s*(\d+)\s*[x×]\s*(?=[A-Za-z0-9])")
_SETS_COUNT_RE = re.compile(r"(?:\b[x×]\s*)?(\d+)\s*(?:sets?|units?|may|chiec)\b", re.IGNORECASE)
_MAKER_NOISE_RE = re.compile(
    r"\b(?:man\s*b\s*&\s*w|man|wartsila|yanmar|caterpillar|cat|cummins|mitsubishi|"
    r"daihatsu|mak|weichai|doosan|niigata|hanshin|sulzer|diesel|marine|engine|single|twin)\b",
    re.IGNORECASE,
)
_ENGINE_MODEL_RE = re.compile(
    r"\b(\d{1,2}\s*[A-Za-z]{1,4}\s*\d{2,4}\s*[A-Za-z0-9-]*|"
    r"[A-Za-z]{1,5}\s*-?\s*\d{2,5}[A-Za-z0-9-]*)\b"
)


def _safe_target_drawing_id(raw_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", str(raw_id or "").strip()).lstrip("_-")
    return cleaned or "DRAWING_0"


def _unit_to_kw(value: float, unit: str) -> float:
    u = unit.lower()
    if u == "kw":
        return value
    if u in {"hp", "bhp"}:
        return value * 0.7457
    if u in {"cv", "ps"}:
        return value * 0.7355
    return value


def parse_structured_main_engine(raw_text: str) -> dict[str, Any]:
    """Parse a marine main-engine string into count, total power_kw, and normalized model_code."""
    norm = normalize_marine_cad_text(str(raw_text or "")).strip()
    folded = fold_marine_search_text(norm)
    if not norm:
        return {
            "raw": "",
            "count": None,
            "power_kw": None,
            "per_unit_power_kw": None,
            "model_code": None,
        }

    count: int | None = None
    m_sets = _SETS_COUNT_RE.search(folded)
    if m_sets:
        count = int(m_sets.group(1))
    else:
        m_pre = _PREFIX_COUNT_RE.search(folded)
        if m_pre:
            count = int(m_pre.group(1))
        elif re.search(r"\bsingle\b", folded):
            count = 1
        elif re.search(r"\btwin\b", folded):
            count = 2

    power_matches = list(_POWER_TOKEN_RE.finditer(folded))
    chosen_match: re.Match[str] | None = None
    for pm in power_matches:
        if pm.group("unit").lower() == "kw":
            chosen_match = pm
            break
    if chosen_match is None and power_matches:
        chosen_match = power_matches[0]

    power_kw: float | None = None
    per_unit_kw: float | None = None
    if chosen_match is not None:
        raw_num = float(chosen_match.group("num").replace(",", "."))
        unit_kw = _unit_to_kw(raw_num, chosen_match.group("unit"))
        mul_str = chosen_match.group("mul")
        if mul_str is not None:
            mul = int(mul_str)
            if count is None:
                count = mul
            per_unit_kw = round(unit_kw, 2)
            power_kw = round(unit_kw * mul, 2)
        elif chosen_match.group("each") and count is not None and count > 0:
            per_unit_kw = round(unit_kw, 2)
            power_kw = round(unit_kw * count, 2)
        else:
            power_kw = round(unit_kw, 2)
            per_unit_kw = round(unit_kw / count, 2) if count and count > 0 else power_kw

    # Strip parenthetical ratings, power/rpm clauses, counts, and maker names before model scan
    stripped = re.sub(r"\([^)]*\)", " ", norm)
    stripped = _POWER_TOKEN_RE.sub(" ", stripped)
    stripped = re.sub(r"[0-9]+(?:[.,][0-9]+)?\s*(?:rpm|r/min|v/ph)\b", " ", stripped, flags=re.IGNORECASE)
    stripped = _SETS_COUNT_RE.sub(" ", stripped)
    stripped = _PREFIX_COUNT_RE.sub(" ", stripped)
    stripped = _MAKER_NOISE_RE.sub(" ", stripped)

    model_code: str | None = None
    for m_mod in _ENGINE_MODEL_RE.finditer(stripped):
        cand = re.sub(r"[\s_-]+", "", m_mod.group(1)).upper()
        if any(ch.isalpha() for ch in cand) and any(ch.isdigit() for ch in cand):
            model_code = cand
            break

    return {
        "raw": norm,
        "count": count,
        "power_kw": power_kw,
        "per_unit_power_kw": per_unit_kw,
        "model_code": model_code,
    }


def _extract_project_codes(obs: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    raw_dc = str(obs.get("drawing_code") or "")
    for m in _PROJECT_CODE_RE.finditer(fold_marine_search_text(raw_dc)):
        tok = re.sub(r"[\s_-]+", "-", m.group(1).strip()).upper()
        if tok and tok not in codes:
            codes.append(tok)
    for entry in obs.get("texts", []):
        for m in _PROJECT_CODE_RE.finditer(str(entry.get("folded") or "")):
            tok = re.sub(r"[\s_-]+", "-", m.group(1).strip()).upper()
            if tok and tok not in codes:
                codes.append(tok)
    return codes


def _verify_observation_fact_envelope(obs: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed if pre-normalized facts were spliced across drawings or envelope metadata was mutated."""
    copied = deepcopy(dict(obs))
    did = str(copied.get("drawing_id") or "")
    ev = copied.get("drawing_evidence") or {}
    expected_sha = ev.get("drawing_sha256")
    expected_rev = ev.get("revision")
    is_ocr = bool(copied.get("ocr_only", False))

    validated_facts: list[dict[str, Any]] = []
    for raw_fact in copied.get("engineering_facts", []):
        fact = validate_engineering_fact(raw_fact)
        if fact["drawing_id"] != did:
            raise MarineKnowledgeError("FACT_ENVELOPE_DRAWING_ID_MISMATCH")
        if fact["drawing_sha256"] != expected_sha:
            raise MarineKnowledgeError("FACT_ENVELOPE_SHA_MISMATCH")
        if fact["revision"] != expected_rev:
            raise MarineKnowledgeError("FACT_ENVELOPE_REVISION_MISMATCH")
        if is_ocr and fact["provenance_class"] != "OCR_ONLY":
            raise MarineKnowledgeError("FACT_ENVELOPE_OCR_MISMATCH")
        validated_facts.append(fact)
    copied["engineering_facts"] = validated_facts
    return copied


def verify_package_comparability(obs_list: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Verify whether supplied drawings belong to the same vessel and comparable revision."""
    validated_obs = [_verify_observation_fact_envelope(raw_obs) for raw_obs in obs_list]

    eligible_obs = [o for o in validated_obs if not o.get("ocr_only")]
    ocr_ids = [str(o["drawing_id"]) for o in validated_obs if o.get("ocr_only")]

    hulls_by_drawing: dict[str, list[str]] = {}
    project_codes_by_drawing: dict[str, list[str]] = {}
    revisions_by_drawing: dict[str, str | None] = {}
    issue_dates_by_drawing: dict[str, list[str]] = {}
    design_variants_by_drawing: dict[str, list[str]] = {}

    for obs in eligible_obs:
        did = str(obs["drawing_id"])
        ev = obs.get("drawing_evidence") or {}
        raw_rev = ev.get("revision")
        revisions_by_drawing[did] = (
            raw_rev.strip().upper() if isinstance(raw_rev, str) and raw_rev.strip() else None
        )
        issue_dates_by_drawing[did] = list(ev.get("issue_dates", []))
        design_variants_by_drawing[did] = list(ev.get("design_variants", []))
        project_codes_by_drawing[did] = _extract_project_codes(obs)

        sheet_hulls: list[str] = []
        for f in obs["engineering_facts"]:
            if (
                f["fact_key"] == "hull_no"
                and f["verification_state"] in _TRUSTED_FACT_STATES
                and f["normalized_value"] is not None
            ):
                h_val = str(f["normalized_value"]).strip().upper()
                if h_val and h_val not in sheet_hulls:
                    sheet_hulls.append(h_val)
        hulls_by_drawing[did] = sheet_hulls

    if len(eligible_obs) < 2:
        return {
            "status": "INSUFFICIENT_ELIGIBLE_SHEETS",
            "comparable": False,
            "eligible_drawing_ids": [str(o["drawing_id"]) for o in eligible_obs],
            "ocr_excluded_drawing_ids": ocr_ids,
            "hull_nos_by_drawing": hulls_by_drawing,
            "project_codes_by_drawing": project_codes_by_drawing,
            "revisions_by_drawing": revisions_by_drawing,
            "issue_dates_by_drawing": issue_dates_by_drawing,
            "design_variants_by_drawing": design_variants_by_drawing,
            "reason": "At least two non-OCR drawings are required for verified cross-drawing comparison.",
        }

    distinct_hulls = sorted({h for hs in hulls_by_drawing.values() for h in hs})
    if len(distinct_hulls) > 1:
        return {
            "status": "DIFFERENT_VESSEL",
            "comparable": False,
            "eligible_drawing_ids": [str(o["drawing_id"]) for o in eligible_obs],
            "ocr_excluded_drawing_ids": ocr_ids,
            "hull_nos_by_drawing": hulls_by_drawing,
            "project_codes_by_drawing": project_codes_by_drawing,
            "revisions_by_drawing": revisions_by_drawing,
            "issue_dates_by_drawing": issue_dates_by_drawing,
            "design_variants_by_drawing": design_variants_by_drawing,
            "reason": f"Drawings declare distinct vessel hull/yard numbers ({distinct_hulls}); cross-sheet equality is not applicable.",
        }

    all_sheets_share_hull = (
        len(distinct_hulls) == 1
        and all(distinct_hulls[0] in hulls_by_drawing[str(o["drawing_id"])] for o in eligible_obs)
    )
    common_project_codes = set(project_codes_by_drawing[str(eligible_obs[0]["drawing_id"])])
    for o in eligible_obs[1:]:
        common_project_codes &= set(project_codes_by_drawing[str(o["drawing_id"])])

    if not all_sheets_share_hull and not common_project_codes:
        return {
            "status": "UNVERIFIED_SAME_VESSEL",
            "comparable": False,
            "eligible_drawing_ids": [str(o["drawing_id"]) for o in eligible_obs],
            "ocr_excluded_drawing_ids": ocr_ids,
            "hull_nos_by_drawing": hulls_by_drawing,
            "project_codes_by_drawing": project_codes_by_drawing,
            "revisions_by_drawing": revisions_by_drawing,
            "issue_dates_by_drawing": issue_dates_by_drawing,
            "design_variants_by_drawing": design_variants_by_drawing,
            "reason": "Drawings lack a shared explicit Hull/Yard No or shared project design code across all sheets.",
        }

    present_revs = sorted({r for r in revisions_by_drawing.values() if r is not None})
    any_missing_rev = any(r is None for r in revisions_by_drawing.values())
    if len(present_revs) > 1 or (present_revs and any_missing_rev):
        return {
            "status": "DIFFERENT_REVISION",
            "comparable": False,
            "eligible_drawing_ids": [str(o["drawing_id"]) for o in eligible_obs],
            "ocr_excluded_drawing_ids": ocr_ids,
            "hull_nos_by_drawing": hulls_by_drawing,
            "project_codes_by_drawing": project_codes_by_drawing,
            "revisions_by_drawing": revisions_by_drawing,
            "issue_dates_by_drawing": issue_dates_by_drawing,
            "design_variants_by_drawing": design_variants_by_drawing,
            "reason": (
                f"Explicit revision skew across sheets ({revisions_by_drawing}); "
                "cannot treat cross-revision differences as same-revision engineering conflicts."
            ),
        }

    identity_basis = (
        f"HULL_NO:{distinct_hulls[0]}"
        if all_sheets_share_hull
        else f"PROJECT_CODE:{sorted(common_project_codes)[0]}"
    )
    rev_basis = (
        f"MATCHING_REVISION:{present_revs[0]}"
        if present_revs
        else "UNDECLARED_ON_ALL_SHEETS"
    )
    return {
        "status": "COMPARABLE_VERIFIED",
        "comparable": True,
        "identity_basis": identity_basis,
        "revision_basis": rev_basis,
        "eligible_drawing_ids": [str(o["drawing_id"]) for o in eligible_obs],
        "ocr_excluded_drawing_ids": ocr_ids,
        "hull_nos_by_drawing": hulls_by_drawing,
        "project_codes_by_drawing": project_codes_by_drawing,
        "revisions_by_drawing": revisions_by_drawing,
        "issue_dates_by_drawing": issue_dates_by_drawing,
        "design_variants_by_drawing": design_variants_by_drawing,
        "reason": f"Sheets verified comparable via {identity_basis} ({rev_basis}).",
    }


def _trusted_numeric_facts(
    eligible_obs: Sequence[Mapping[str, Any]],
    fact_key: str,
) -> tuple[list[tuple[str, float, dict[str, Any]]], list[tuple[str, float, dict[str, Any]]]]:
    exact: list[tuple[str, float, dict[str, Any]]] = []
    approx: list[tuple[str, float, dict[str, Any]]] = []
    for obs in eligible_obs:
        did = str(obs["drawing_id"])
        for f in obs.get("engineering_facts", []):
            if f["fact_key"] != fact_key or f["normalized_value"] is None:
                continue
            if not isinstance(f["normalized_value"], (int, float)) or isinstance(f["normalized_value"], bool):
                continue
            val = float(f["normalized_value"])
            if f["verification_state"] in _TRUSTED_FACT_STATES:
                exact.append((did, val, deepcopy(f)))
            elif f["verification_state"] == "PROVISIONAL_APPROXIMATE":
                approx.append((did, val, deepcopy(f)))
    return exact, approx


def evaluate_particulars_consistency(
    observations: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    calibration_verified: bool = False,
    verified_scale_to_mm: float | None = None,
    partial_package: bool = True,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """V1-B Skill: Produce a Cross-Drawing Engineering Particulars Consistency Report."""
    skill_id = "SKILL_V1B_PARTICULARS_CONSISTENCY"
    if not is_marine_pack_enabled(enabled):
        return _disabled_result(skill_id, "Marine Knowledge Pack disabled; particulars consistency skipped.")

    cal_ok = _validate_calibration_flag(calibration_verified)
    scale_mm = _validate_scale_arg(verified_scale_to_mm)
    pack, rules_by_id = _pack_context()
    obs_list = [
        _verify_observation_fact_envelope(
            rebind_observation_dimensions(
                o,
                calibration_verified=cal_ok,
                verified_scale_to_mm=scale_mm,
            )
        )
        for o in _to_obs_list(observations)
    ]

    findings: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []

    if len(obs_list) < 2:
        reason_single = (
            f"Only {len(obs_list)} drawing observation supplied; cross-drawing particulars consistency "
            "requires at least two sheets of the same vessel."
        )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_SINGLE_DRAWING_NOT_CROSS_CHECKABLE",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={"drawing_ids": [o["drawing_id"] for o in obs_list]},
                reason=reason_single,
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
                "summary": reason_single,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "comparability": {"status": "SINGLE_DRAWING", "comparable": False},
                    "consistency_matrix": {},
                },
                "applicable_regulation_scope": {"checked": False, "reason": "Cross-drawing particulars check"},
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": ["Minimum multi-sheet package gate"],
                "checks_not_executed": ["Cross-drawing principal particulars matrix"],
                "limitations": [reason_single],
                "proposal_only_actions": [],
            }
        )

    for obs in obs_list:
        if obs.get("ocr_only"):
            did = str(obs["drawing_id"])
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_OCR_ONLY_SHEET_EXCLUDED_{did}",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"drawing_id": did, "source_mode": obs.get("source_mode")},
                    reason=(
                        f"Drawing {did} is OCR_ONLY; its text cannot prove verified vessel particulars "
                        "or trigger false cross-drawing CAD conflicts."
                    ),
                )
            )

    comparability = verify_package_comparability(obs_list)
    if not comparability["comparable"]:
        c_status = comparability["status"]
        if c_status == "DIFFERENT_VESSEL":
            fid = "F_NOT_COMPARABLE_DIFFERENT_VESSEL"
        elif c_status == "DIFFERENT_REVISION":
            fid = "F_REVISION_SKEW_NOT_COMPARABLE"
        elif c_status == "UNVERIFIED_SAME_VESSEL":
            fid = "F_SAME_VESSEL_IDENTITY_UNVERIFIED"
        else:
            fid = "F_INSUFFICIENT_ELIGIBLE_SHEETS"

        findings.append(
            _make_finding(
                rules_by_id,
                finding_id=fid,
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence=comparability,
                reason=comparability["reason"],
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
                "summary": comparability["reason"],
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "comparability": comparability,
                    "consistency_matrix": {},
                },
                "applicable_regulation_scope": {"checked": False, "reason": "Comparability gate stopped cross-check"},
                "partial_package": bool(partial_package),
                "findings": findings,
                "checks_executed": ["Same-vessel and revision comparability gate"],
                "checks_not_executed": ["Cross-drawing principal particulars matrix (package not comparable)"],
                "limitations": [comparability["reason"]],
                "proposal_only_actions": [],
            }
        )

    eligible_obs = [o for o in obs_list if not o.get("ocr_only")]
    drawing_types_by_id = {
        str(o["drawing_id"]): _classify_observation(o)["predicted_drawing_type"]
        for o in eligible_obs
    }
    primary_target_id = _safe_target_drawing_id(str(eligible_obs[0]["drawing_id"]))

    # Surface unitless or corrupted particular tokens on eligible sheets without raising false conflicts
    for obs in eligible_obs:
        did = str(obs["drawing_id"])
        corrupted = list(obs.get("particulars", {}).get("corrupted_numeric_tokens", []))
        if corrupted:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_CORRUPTED_PARTICULAR_TOKEN_{did}",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                    evidence={"drawing_id": did, "corrupted_numeric_tokens": corrupted},
                    reason=f"Drawing {did} contains corrupted numeric particular token(s) {corrupted}.",
                )
            )
        unitless_p_facts = [
            deepcopy(f)
            for f in obs.get("engineering_facts", [])
            if f["fact_key"] in _PRINCIPAL_DIM_KEYS and f["verification_state"] == "UNVERIFIED_UNITLESS"
        ]
        if unitless_p_facts:
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_UNITLESS_PARTICULAR_UNVERIFIED_{did}",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_03_CAD_UNITS_AND_CALIBRATION_REQUIRED",
                    evidence={"drawing_id": did, "bound_facts": unitless_p_facts},
                    reason=(
                        f"Drawing {did} has {len(unitless_p_facts)} unitless principal particular value(s) "
                        "in an uncalibrated $INSUNITS=0 drawing; excluded from numeric equality."
                    ),
                )
            )

    matrix: dict[str, dict[str, Any]] = {}
    exact_by_key: dict[str, list[tuple[str, float, dict[str, Any]]]] = {}
    approx_by_key: dict[str, list[tuple[str, float, dict[str, Any]]]] = {}

    for dim_key in _PRINCIPAL_DIM_KEYS:
        exact_rows, approx_rows = _trusted_numeric_facts(eligible_obs, dim_key)
        exact_by_key[dim_key] = exact_rows
        approx_by_key[dim_key] = approx_rows
        sheets_exact = sorted({d for d, _, _ in exact_rows})
        vals_exact = [v for _, v, _ in exact_rows]
        by_drawing = {
            d: sorted({round(v, 4) for dd, v, _ in exact_rows if dd == d})
            for d in sheets_exact
        }
        approx_by_drawing = {
            d: sorted({round(v, 4) for dd, v, _ in approx_rows if dd == d})
            for d in sorted({dd for dd, _, _ in approx_rows})
        }

        if len(vals_exact) >= 2 and (max(vals_exact) - min(vals_exact)) > 0.05:
            dim_status = "CONFLICT"
            bound_facts = [f for _, _, f in exact_rows]
            reason_dim = (
                f"Principal particular '{dim_key}' conflicts across comparable sheets: {by_drawing} "
                f"(delta={max(vals_exact) - min(vals_exact):.3f} m > 0.05 m tolerance)."
            )
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id=f"F_PARTICULAR_CONFLICT_{dim_key.upper()}",
                    verdict="CONFLICT",
                    rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                    evidence={
                        "fact_key": dim_key,
                        "values_by_drawing": by_drawing,
                        "bound_facts": bound_facts,
                    },
                    reason=reason_dim,
                )
            )
            proposals.append(
                build_marine_core_proposal(
                    target_drawing_id=primary_target_id,
                    action_kind=_DIM_PROPOSAL_ACTION[dim_key],
                    evidence={"fact_key": dim_key, "values_by_drawing": by_drawing},
                    reason=f"Proposal only: reconcile conflicting {dim_key} values {by_drawing}.",
                )
            )
        elif len(sheets_exact) >= 2:
            observed_units = sorted(
                {str(f["observed_unit"] or "insunits_derived") for _, _, f in exact_rows}
            )
            dim_status = "CONSISTENT"
            by_drawing = by_drawing
            observed_units_note = observed_units
        elif len(sheets_exact) == 1:
            dim_status = "SINGLE_SHEET_OBSERVED"
            observed_units_note = []
        elif approx_rows:
            dim_status = "APPROXIMATE_ONLY"
            observed_units_note = []
        else:
            dim_status = "NOT_OBSERVED"
            observed_units_note = []

        matrix[dim_key] = {
            "status": dim_status,
            "values_m_by_drawing": by_drawing,
            "approximate_values_m_by_drawing": approx_by_drawing,
            "unit_normalized": len(observed_units_note) > 1 if dim_status == "CONSISTENT" else False,
        }

    # Cross-concept length ordering check (Loa >= Lwl >= L >= 0.96*Lwl, Loa >= Lpp)
    loa_vals = [v for _, v, _ in exact_by_key["loa_m"]]
    loa_approx_vals = [v for _, v, _ in approx_by_key["loa_m"]]
    lwl_vals = [v for _, v, _ in exact_by_key["lwl_m"]]
    l_vals = [v for _, v, _ in exact_by_key["design_length_l_m"]]
    lpp_vals = [v for _, v, _ in exact_by_key["lpp_m"]]

    length_violations: list[str] = []
    if lpp_vals and loa_vals and max(lpp_vals) > min(loa_vals) + 0.05:
        length_violations.append(f"Lpp ({max(lpp_vals):.2f} m) > Loa ({min(loa_vals):.2f} m)")
    elif lpp_vals and loa_approx_vals and max(lpp_vals) > min(loa_approx_vals) * 1.02 + 0.5:
        length_violations.append(f"Lpp ({max(lpp_vals):.2f} m) > ABT. Loa ({min(loa_approx_vals):.2f} m)")
    if lwl_vals and loa_vals and max(lwl_vals) > min(loa_vals) + 0.05:
        length_violations.append(f"Lwl ({max(lwl_vals):.2f} m) > Loa ({min(loa_vals):.2f} m)")
    if l_vals and loa_vals and max(l_vals) > min(loa_vals) + 0.05:
        length_violations.append(f"L ({max(l_vals):.2f} m) > Loa ({min(loa_vals):.2f} m)")
    if l_vals and lwl_vals:
        if max(l_vals) > min(lwl_vals) + 0.05:
            length_violations.append(
                f"Design length L ({max(l_vals):.2f} m) > Lwl ({min(lwl_vals):.2f} m) violates QCVN 72 Clause 1.4.43-1"
            )
        if min(l_vals) < 0.96 * max(lwl_vals) - 0.05:
            length_violations.append(
                f"Design length L ({min(l_vals):.2f} m) < 0.96 * Lwl ({0.96 * max(lwl_vals):.2f} m) violates QCVN 72 Clause 1.4.43-1"
            )

    len_subkeys = ("loa_m", "lwl_m", "design_length_l_m", "lpp_m")
    observed_len_concepts = [
        k for k in len_subkeys if exact_by_key[k] or approx_by_key[k]
    ]
    sheets_with_exact_len = {
        d for k in len_subkeys for d, _, _ in exact_by_key[k]
    }
    any_same_len_conflict = any(matrix[k]["status"] == "CONFLICT" for k in len_subkeys)
    if length_violations:
        len_bound_facts = [
            f
            for k in len_subkeys
            for _, _, f in (exact_by_key[k] + approx_by_key[k])
        ]
        reason_len_ord = (
            "Implausible naval-architecture length ordering across comparable sheets: "
            + "; ".join(length_violations)
            + "."
        )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_LENGTH_CONCEPT_ORDER_CONFLICT",
                verdict="CONFLICT",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={
                    "violations": length_violations,
                    "observed_concepts": observed_len_concepts,
                    "bound_facts": len_bound_facts,
                },
                reason=reason_len_ord,
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=primary_target_id,
                action_kind="RECONCILE_L_PARTICULAR",
                evidence={"violations": length_violations},
                reason="Proposal only: reconcile physically contradictory vessel length definitions (Loa/Lwl/L/Lpp).",
            )
        )
        lg_status = "CONFLICT"
    elif any_same_len_conflict:
        lg_status = "CONFLICT"
    elif any(matrix[k]["status"] == "CONSISTENT" for k in len_subkeys) and len(observed_len_concepts) == 1:
        lg_status = "CONSISTENT"
    elif len(sheets_with_exact_len) >= 2 and len(observed_len_concepts) >= 2:
        lg_status = "COMPATIBLE_CONCEPTS"
    elif any(matrix[k]["status"] == "CONSISTENT" for k in len_subkeys):
        lg_status = "CONSISTENT"
    elif len(sheets_with_exact_len) == 1:
        lg_status = "SINGLE_SHEET_OBSERVED"
    elif observed_len_concepts:
        lg_status = "APPROXIMATE_ONLY"
    else:
        lg_status = "NOT_OBSERVED"

    matrix["length_group"] = {
        "status": lg_status,
        "observed_concepts": observed_len_concepts,
        "violations": length_violations,
    }

    # Draft vs Depth physical invariant (T <= D)
    depth_vals = [v for _, v, _ in exact_by_key["depth_m"]]
    draft_vals = [v for _, v, _ in exact_by_key["draft_m"]]
    if depth_vals and draft_vals and max(draft_vals) > min(depth_vals) + 0.05:
        matrix["draft_m"]["status"] = "CONFLICT"
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_DRAFT_EXCEEDS_DEPTH_CONFLICT",
                verdict="CONFLICT",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={
                    "max_draft_m": max(draft_vals),
                    "min_depth_m": min(depth_vals),
                    "bound_facts": [f for _, _, f in exact_by_key["draft_m"] + exact_by_key["depth_m"]],
                },
                reason=(
                    f"Design draft T ({max(draft_vals):.2f} m) exceeds molded depth D "
                    f"({min(depth_vals):.2f} m) across comparable sheets."
                ),
            )
        )

    # Ship type consistency
    ship_type_facts: list[tuple[str, str, dict[str, Any]]] = []
    for obs in eligible_obs:
        did = str(obs["drawing_id"])
        for f in obs.get("engineering_facts", []):
            if (
                f["fact_key"] == "ship_type"
                and f["verification_state"] in _TRUSTED_FACT_STATES
                and isinstance(f["normalized_value"], str)
                and f["normalized_value"].strip()
            ):
                ship_type_facts.append((did, f["normalized_value"].strip().upper(), deepcopy(f)))
    distinct_stypes = sorted({v for _, v, _ in ship_type_facts})
    stype_sheets = sorted({d for d, _, _ in ship_type_facts})
    stype_by_drawing = {
        d: sorted({v for dd, v, _ in ship_type_facts if dd == d})
        for d in stype_sheets
    }
    if len(distinct_stypes) > 1:
        st_status = "CONFLICT"
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_PARTICULAR_CONFLICT_SHIP_TYPE",
                verdict="CONFLICT",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={
                    "ship_types_by_drawing": stype_by_drawing,
                    "issue_dates_by_drawing": comparability["issue_dates_by_drawing"],
                    "design_variants_by_drawing": comparability["design_variants_by_drawing"],
                    "bound_facts": [f for _, _, f in ship_type_facts],
                },
                reason=(
                    f"Vessel type / configuration diverges across sheets sharing {comparability['identity_basis']}: "
                    f"{stype_by_drawing} (dates={comparability['issue_dates_by_drawing']}, "
                    f"variants={comparability['design_variants_by_drawing']})."
                ),
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=primary_target_id,
                action_kind="RECONCILE_SHIP_TYPE_AND_HULL_ID",
                evidence={"ship_types_by_drawing": stype_by_drawing},
                reason="Proposal only: reconcile divergent vessel type / design variant declarations across sheets.",
            )
        )
    elif len(stype_sheets) >= 2:
        st_status = "CONSISTENT"
    elif len(stype_sheets) == 1:
        st_status = "SINGLE_SHEET_OBSERVED"
    else:
        st_status = "NOT_OBSERVED"
    matrix["ship_type"] = {"status": st_status, "values_by_drawing": stype_by_drawing}

    # Service area & class notation consistency
    svc_facts: list[tuple[str, str, dict[str, Any]]] = []
    cls_facts: list[tuple[str, str, dict[str, Any]]] = []
    for obs in eligible_obs:
        did = str(obs["drawing_id"])
        for f in obs.get("engineering_facts", []):
            if f["verification_state"] not in _TRUSTED_FACT_STATES or not isinstance(f["normalized_value"], str):
                continue
            if f["fact_key"] == "service_area":
                svc_facts.append((did, f["normalized_value"].strip().upper(), deepcopy(f)))
            elif f["fact_key"] == "class_notation":
                cls_facts.append((did, f["normalized_value"].strip().upper(), deepcopy(f)))
    distinct_svc = sorted({v for _, v, _ in svc_facts})
    distinct_cls = sorted({v for _, v, _ in cls_facts})
    svc_cls_sheets = sorted({d for d, _, _ in (svc_facts + cls_facts)})
    svc_by_drawing = {d: sorted({v for dd, v, _ in svc_facts if dd == d}) for d in sorted({dd for dd, _, _ in svc_facts})}
    cls_by_drawing = {d: sorted({v for dd, v, _ in cls_facts if dd == d}) for d in sorted({dd for dd, _, _ in cls_facts})}
    if len(distinct_svc) > 1 or len(distinct_cls) > 1:
        sc_status = "CONFLICT"
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_PARTICULAR_CONFLICT_SERVICE_CLASS",
                verdict="CONFLICT",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={
                    "service_areas_by_drawing": svc_by_drawing,
                    "class_notations_by_drawing": cls_by_drawing,
                    "bound_facts": [f for _, _, f in (svc_facts + cls_facts)],
                },
                reason=(
                    f"Service area or class notation conflicts across sheets: "
                    f"service={svc_by_drawing}, class={cls_by_drawing}."
                ),
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=primary_target_id,
                action_kind="RECONCILE_SERVICE_AREA_SCOPE",
                evidence={"service_areas_by_drawing": svc_by_drawing, "class_notations_by_drawing": cls_by_drawing},
                reason="Proposal only: reconcile conflicting service area / class notation across sheets.",
            )
        )
    elif len({d for d, _, _ in svc_facts}) >= 2 or len({d for d, _, _ in cls_facts}) >= 2:
        sc_status = "CONSISTENT"
    elif len(svc_cls_sheets) == 1:
        sc_status = "SINGLE_SHEET_OBSERVED"
    else:
        sc_status = "NOT_OBSERVED"
    matrix["service_and_class"] = {
        "status": sc_status,
        "service_areas_by_drawing": svc_by_drawing,
        "class_notations_by_drawing": cls_by_drawing,
    }

    # Watertight bulkhead count (eligible GA / BASIC_STRUCTURAL sheets only)
    bh_eligible: list[tuple[str, int, dict[str, Any]]] = []
    bh_ineligible_ids: list[str] = []
    for obs in eligible_obs:
        did = str(obs["drawing_id"])
        dtype = drawing_types_by_id.get(did, "UNKNOWN")
        for f in obs.get("engineering_facts", []):
            if (
                f["fact_key"] == "transverse_watertight_bulkhead_count"
                and f["verification_state"] in _TRUSTED_FACT_STATES
                and isinstance(f["normalized_value"], (int, float))
                and not isinstance(f["normalized_value"], bool)
            ):
                if dtype in {"GENERAL_ARRANGEMENT", "BASIC_STRUCTURAL"}:
                    bh_eligible.append((did, int(round(float(f["normalized_value"]))), deepcopy(f)))
                elif did not in bh_ineligible_ids:
                    bh_ineligible_ids.append(did)
    distinct_bh = sorted({v for _, v, _ in bh_eligible})
    bh_sheets = sorted({d for d, _, _ in bh_eligible})
    bh_by_drawing = {d: sorted({v for dd, v, _ in bh_eligible if dd == d}) for d in bh_sheets}
    if len(distinct_bh) > 1:
        bh_status = "CONFLICT"
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_PARTICULAR_CONFLICT_BULKHEAD_COUNT",
                verdict="CONFLICT",
                rule_id="RULE_MK_08_WATERTIGHT_BULKHEAD_MIN_COUNT",
                evidence={
                    "bulkhead_count_by_drawing": bh_by_drawing,
                    "excluded_ineligible_sheets": bh_ineligible_ids,
                    "bound_facts": [f for _, _, f in bh_eligible],
                },
                reason=f"Transverse watertight bulkhead count conflicts across GA/KCCB sheets: {bh_by_drawing}.",
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=primary_target_id,
                action_kind="REVIEW_WATERTIGHT_BULKHEAD_SUBDIVISION",
                evidence={"bulkhead_count_by_drawing": bh_by_drawing},
                reason="Proposal only: reconcile watertight bulkhead count between GA and Basic Structural sheets.",
            )
        )
    elif len(bh_sheets) >= 2:
        bh_status = "CONSISTENT"
    elif len(bh_sheets) == 1:
        bh_status = "SINGLE_SHEET_OBSERVED"
    else:
        bh_status = "NOT_OBSERVED"
    matrix["watertight_bulkhead_count"] = {
        "status": bh_status,
        "values_by_drawing": bh_by_drawing,
        "excluded_ineligible_sheets": bh_ineligible_ids,
    }

    # Structured main-engine reconciliation
    eng_entries: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for obs in eligible_obs:
        did = str(obs["drawing_id"])
        for f in obs.get("engineering_facts", []):
            if (
                f["fact_key"] == "main_engine"
                and f["verification_state"] in _TRUSTED_FACT_STATES
                and isinstance(f["normalized_value"], str)
                and f["normalized_value"].strip()
            ):
                eng_entries.append((did, parse_structured_main_engine(f["normalized_value"]), deepcopy(f)))

    eng_sheets = sorted({d for d, _, _ in eng_entries})
    parsed_by_drawing = {
        d: [p for dd, p, _ in eng_entries if dd == d]
        for d in eng_sheets
    }
    counts_seen = sorted({p["count"] for _, p, _ in eng_entries if p["count"] is not None})
    models_seen = sorted({p["model_code"] for _, p, _ in eng_entries if p["model_code"] is not None})
    powers_seen = [float(p["power_kw"]) for _, p, _ in eng_entries if p["power_kw"] is not None]
    unparsed_seen = sorted(
        {
            p["raw"].upper()
            for _, p, _ in eng_entries
            if p["count"] is None and p["model_code"] is None and p["power_kw"] is None and p["raw"]
        }
    )

    power_conflict = (
        len(powers_seen) >= 2
        and (max(powers_seen) - min(powers_seen)) > 5.0
        and ((max(powers_seen) - min(powers_seen)) / max(max(powers_seen), 1e-6)) > 0.05
    )
    if len(counts_seen) > 1 or len(models_seen) > 1 or power_conflict or len(unparsed_seen) > 1:
        eng_status = "CONFLICT"
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_PARTICULAR_CONFLICT_MAIN_ENGINE",
                verdict="CONFLICT",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={
                    "parsed_by_drawing": parsed_by_drawing,
                    "bound_facts": [f for _, _, f in eng_entries],
                },
                reason=f"Main engine specification conflicts across comparable sheets: {parsed_by_drawing}.",
            )
        )
        proposals.append(
            build_marine_core_proposal(
                target_drawing_id=primary_target_id,
                action_kind="RECONCILE_MAIN_ENGINE_SPECIFICATION",
                evidence={"parsed_by_drawing": parsed_by_drawing},
                reason="Proposal only: reconcile contradictory main engine count, model, or power across sheets.",
            )
        )
    elif len(eng_sheets) >= 2:
        sheets_with_model = {d for d, p, _ in eng_entries if p["model_code"] is not None}
        sheets_with_power = {d for d, p, _ in eng_entries if p["power_kw"] is not None}
        model_only_sheets = sheets_with_model - sheets_with_power
        power_only_sheets = sheets_with_power - sheets_with_model
        if model_only_sheets and power_only_sheets and len(sheets_with_model) < 2 and len(sheets_with_power) < 2:
            eng_status = "AMBIGUOUS_SCHEMA"
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_MAIN_ENGINE_SCHEMA_AMBIGUOUS",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                    evidence={
                        "parsed_by_drawing": parsed_by_drawing,
                        "bound_facts": [f for _, _, f in eng_entries],
                    },
                    reason=(
                        f"Main engine entries use non-equivalent schemas across sheets ({parsed_by_drawing}: "
                        "engine model code vs rated power without shared manufacturer MCR table); "
                        "cannot prove consistency or conflict from drawing text alone."
                    ),
                )
            )
        elif len(sheets_with_model) >= 2 or len(sheets_with_power) >= 2:
            eng_status = "CONSISTENT"
        else:
            eng_status = "AMBIGUOUS_SCHEMA"
            findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_MAIN_ENGINE_SCHEMA_AMBIGUOUS",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                    evidence={
                        "parsed_by_drawing": parsed_by_drawing,
                        "bound_facts": [f for _, _, f in eng_entries],
                    },
                    reason=f"Main engine entries lack overlapping structured model/power fields: {parsed_by_drawing}.",
                )
            )
    elif len(eng_sheets) == 1:
        eng_status = "SINGLE_SHEET_OBSERVED"
    else:
        eng_status = "NOT_OBSERVED"

    matrix["main_engine"] = {
        "status": eng_status,
        "parsed_by_drawing": parsed_by_drawing,
    }

    consistent_groups = [
        k for k, v in matrix.items() if v.get("status") in {"CONSISTENT", "COMPATIBLE_CONCEPTS"}
    ]
    conflict_findings = [f for f in findings if f["verdict"] == "CONFLICT"]
    insuff_findings = [f for f in findings if f["verdict"] == "INSUFFICIENT_EVIDENCE"]

    if conflict_findings:
        status = "CONFLICT"
        summary = (
            f"Detected {len(conflict_findings)} cross-drawing engineering particular conflict(s) "
            f"across {len(eligible_obs)} comparable sheet(s) ({comparability['identity_basis']})."
        )
    elif insuff_findings:
        status = "INSUFFICIENT_EVIDENCE"
        summary = (
            f"Cross-drawing particulars check returned INSUFFICIENT_EVIDENCE ({len(insuff_findings)} "
            f"ambiguity/unverified finding(s)) across {len(eligible_obs)} comparable sheet(s)."
        )
    elif consistent_groups:
        status = "PASS"
        summary = (
            f"Principal particulars are consistent across {len(eligible_obs)} comparable sheet(s) "
            f"({comparability['identity_basis']}; verified groups={consistent_groups})."
        )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_PARTICULARS_CONSISTENT",
                verdict="PASS",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={
                    "identity_basis": comparability["identity_basis"],
                    "consistent_groups": consistent_groups,
                },
                reason=summary,
            )
        )
    else:
        status = "INSUFFICIENT_EVIDENCE"
        summary = (
            f"Comparable sheets ({comparability['identity_basis']}) share zero overlapping multi-sheet "
            "principal particular parameters to cross-verify."
        )
        findings.append(
            _make_finding(
                rules_by_id,
                finding_id="F_NO_OVERLAPPING_PARTICULARS",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                evidence={"identity_basis": comparability["identity_basis"]},
                reason=summary,
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
                "drawing_count": len(obs_list),
                "eligible_drawing_ids": comparability["eligible_drawing_ids"],
                "drawing_types_by_id": drawing_types_by_id,
                "comparability": comparability,
                "consistency_matrix": matrix,
                "consistent_groups": consistent_groups,
            },
            "applicable_regulation_scope": {
                "checked": False,
                "reason": "Cross-drawing principal particulars consistency report (V1-B)",
            },
            "partial_package": bool(partial_package),
            "findings": findings,
            "checks_executed": [
                "Same-vessel and revision comparability gate",
                "Unit-normalized scalar principal particulars comparison (Loa, Lwl, L, Lpp, B, D, T)",
                "Cross-concept naval-architecture length ordering & Draft <= Depth check",
                "Ship type, service area, class notation, and eligible-sheet watertight bulkhead coherence",
                "Structured main-engine count / model / rated-power reconciliation",
            ],
            "checks_not_executed": [
                "Manufacturer engine MCR lookup table verification",
                "Full QCVN 72 structural scantling compliance (V1-C)",
                "Cross-view geometric curve projection (V2-A)",
            ],
            "limitations": [
                "Compares bound CAD particular facts across verified comparable sheets only; never mutates CAD entities.",
            ],
            "proposal_only_actions": proposals,
        }
    )


__all__ = [
    "evaluate_particulars_consistency",
    "parse_structured_main_engine",
    "verify_package_comparability",
]
