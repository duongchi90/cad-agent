"""Single Verified Conditional Rule Vertical Slice (Marine V1-C).

Evaluates ``RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT`` (QCVN 72:2025/BGTVT Phần 2A,
Chương 2, Clause ``2.4.3-2``: centerline double-bottom minimum height ``700.0 mm``
for ``L <= 120.0 m`` and ``900.0 mm`` for ``120.0 m < L <= 140.0 m``) strictly from
hash-bound V1-A ``engineering-fact-1.0`` records and V1-B package comparability.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .contracts import (
    MARINE_CHECK_RESULT_SCHEMA_VERSION,
    SUPPORTED_REGULATIONS,
    validate_check_result,
)
from .evidence_binding import rebind_observation_dimensions
from .manifest import get_marine_source_manifest
from .observer import rebind_double_bottom_dimension_facts
from .pack import is_marine_pack_enabled
from .particulars_consistency import (
    _safe_target_drawing_id,
    _verify_observation_fact_envelope,
    verify_package_comparability,
)
from .skills import (
    _CLAUSE_1_1_1_MAP,
    _CLAUSE_1_1_2_MAP,
    _CLAUSE_1_1_4_TAGS,
    _classify_exclusion_basis,
    _classify_observation,
    _disabled_result,
    _make_finding,
    _pack_context,
    _to_obs_list,
    _validate_calibration_flag,
    _validate_scale_arg,
    build_marine_core_proposal,
)

_MANIFEST = get_marine_source_manifest()
_SOURCES_BY_ID = {src["source_id"]: src for src in _MANIFEST["sources"]}

_NATIVE_VERIFIED_PROVENANCES: frozenset[str] = frozenset(
    {"NATIVE_CAD_EVIDENCE", "NATIVE_MEASURED_GEOMETRY"}
)
_TRUSTED_OR_FIXTURE_STATES: frozenset[str] = frozenset(
    {"VERIFIED", "FIXTURE_UNBOUND_TO_DXF_BYTES"}
)
_ELIGIBLE_STRUCTURAL_TYPES: frozenset[str] = frozenset(
    {"MIDSHIP_STRUCTURAL", "BASIC_STRUCTURAL"}
)
_INLAND_SCOPE_VALUES: frozenset[str] = frozenset(
    {"VR-SB", "VR-SI", "VR-SII", "VR-SIII", "INLAND_WATERWAY"}
)

_MANDATORY_UNEXECUTED_SIBLING_CHECKS: tuple[str, ...] = (
    "QCVN 72 Phần 2A Chương 2 Clause 2.4.3-1: transverse floor spacing (khoảng cách đà ngang đáy <= 1.8 m / 2.0 m / 2.4 m)",
    "QCVN 72 Phần 2A Chương 2 Clause 2.4.3-3: center and side bottom girder spacing (khoảng cách sống đáy <= 3.0 m)",
    "QCVN 72 Phần 2A Chương 2 Clauses 2.4.3-11 & 2.4.3-12: bottom framing section modulus W and moment of inertia J",
    "QCVN 72 Phần 2A Chương 2 Clause 2.4.6: transverse watertight bulkhead subdivision",
    "Intact and damage stability booklet verification (separate calculation)",
)


def _is_native_verified_fact(fact: Mapping[str, Any]) -> bool:
    return (
        fact.get("provenance_class") in _NATIVE_VERIFIED_PROVENANCES
        and fact.get("verification_state") == "VERIFIED"
    )


def _dedup_facts(facts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for fact in facts:
        fsha = str(fact.get("fact_sha256") or "")
        if fsha and fsha not in seen:
            seen.add(fsha)
            out.append(deepcopy(dict(fact)))
    return out


def _is_package_comparable_for_rule(comparability: Mapping[str, Any]) -> bool:
    rev_map = comparability.get("revisions_by_drawing") or {}
    missing_any_rev = (not rev_map) or any(v is None for v in rev_map.values())
    var_map = comparability.get("design_variants_by_drawing") or {}
    variant_sets = {tuple(sorted(vs)) for vs in var_map.values()}
    has_variant_skew = len(variant_sets) > 1
    return bool(comparability.get("comparable")) and not missing_any_rev and not has_variant_skew


def _collect_inland_scope_facts(
    obs_seq: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    inland_all: list[dict[str, Any]] = []
    inland_native: list[dict[str, Any]] = []
    ocean_all: list[dict[str, Any]] = []
    class_notations: list[str] = []

    for obs in obs_seq:
        if obs.get("ocr_only"):
            continue
        for fact in obs.get("engineering_facts", []):
            fkey = fact.get("fact_key")
            vstate = fact.get("verification_state")
            nval = fact.get("normalized_value")
            if vstate not in _TRUSTED_OR_FIXTURE_STATES or not isinstance(nval, str):
                continue
            norm_up = nval.strip().upper()
            if fkey == "class_notation" and norm_up in _INLAND_SCOPE_VALUES:
                inland_all.append(fact)
                if _is_native_verified_fact(fact):
                    inland_native.append(fact)
                if norm_up not in class_notations:
                    class_notations.append(norm_up)
            elif fkey == "service_area":
                if norm_up == "INLAND_WATERWAY":
                    inland_all.append(fact)
                    if _is_native_verified_fact(fact):
                        inland_native.append(fact)
                elif norm_up == "OCEAN_GOING":
                    ocean_all.append(fact)
    return (
        _dedup_facts(inland_all),
        _dedup_facts(inland_native),
        _dedup_facts(ocean_all),
        class_notations,
    )


def evaluate_double_bottom_height_rule(
    observations: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    target_regulation: str = "QCVN_72_2025_BGTVT",
    expected_source_sha256: str | None = None,
    calibration_verified: bool = False,
    verified_scale_to_mm: float | None = None,
    partial_package: bool = True,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """V1-C Skill: Evaluate QCVN 72:2025/BGTVT Clause 2.4.3-2 centerline double-bottom minimum height."""
    skill_id = "SKILL_V1C_DOUBLE_BOTTOM_HEIGHT_RULE"
    if not is_marine_pack_enabled(enabled):
        return _disabled_result(
            skill_id,
            "Marine Knowledge Pack disabled; V1-C double-bottom height rule skipped.",
        )

    cal_ok = _validate_calibration_flag(calibration_verified)
    scale_mm = _validate_scale_arg(verified_scale_to_mm)
    pack, rules_by_id = _pack_context()

    pre_validated = [_verify_observation_fact_envelope(o) for o in _to_obs_list(observations)]
    obs_list = [
        _verify_observation_fact_envelope(
            rebind_double_bottom_dimension_facts(
                rebind_observation_dimensions(
                    o,
                    calibration_verified=cal_ok,
                    verified_scale_to_mm=scale_mm,
                ),
                calibration_verified=cal_ok,
                verified_scale_to_mm=scale_mm,
            )
        )
        for o in pre_validated
    ]

    limitations_base = [
        "Per RULE_MK_02_NO_SINGLE_CHECK_CERTIFICATION, regulatory_compliance_proven remains False.",
        "Evaluates only QCVN 72:2025/BGTVT Phần 2A Chương 2 Clause 2.4.3-2 centerline double-bottom height.",
    ]

    if target_regulation not in SUPPORTED_REGULATIONS:
        unsupported_reason = (
            f"Unsupported regulation version {target_regulation!r}; "
            f"supported regulations: {sorted(SUPPORTED_REGULATIONS)}."
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
                    "in_scope": None,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_UNSUPPORTED_REGULATION_VERSION",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_01_QCVN72_SCOPE",
                        evidence={"target_regulation": target_regulation},
                        reason=unsupported_reason,
                    )
                ],
                "checks_executed": ["Regulation version support check"],
                "checks_not_executed": [
                    f"QCVN 72 Clause 2.4.3-2 check blocked by unsupported {target_regulation}",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": [unsupported_reason, *limitations_base],
                "proposal_only_actions": [],
            }
        )

    if expected_source_sha256 is not None:
        indexed_sha = _SOURCES_BY_ID[target_regulation]["sha256"]
        if expected_source_sha256.strip().lower() != indexed_sha:
            stale_reason = (
                f"Stale or mismatched source SHA-256 for {target_regulation}: "
                f"caller expected {expected_source_sha256!r} vs manifest {indexed_sha!r}."
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
                    "checks_not_executed": [
                        "QCVN 72 Clause 2.4.3-2 check blocked by mismatched source PDF hash",
                        *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                    ],
                    "limitations": [stale_reason, *limitations_base],
                    "proposal_only_actions": [],
                }
            )

    if not obs_list:
        empty_reason = "No drawing observations provided for V1-C double-bottom rule evaluation."
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
                "summary": empty_reason,
                "observed_scope": {"drawing_count": 0, "drawing_ids": []},
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "supported_regulation": True,
                    "in_scope": None,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_NO_OBSERVATIONS_SUPPLIED",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_07_PARTIAL_PACKAGE_BOUNDARY",
                        evidence={"drawing_count": 0},
                        reason=empty_reason,
                    )
                ],
                "checks_executed": ["Input observation presence check"],
                "checks_not_executed": [
                    "QCVN 72 Clause 2.4.3-2 centerline double-bottom height check",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": [empty_reason, *limitations_base],
                "proposal_only_actions": [],
            }
        )

    classifications = {str(o["drawing_id"]): _classify_observation(o) for o in obs_list}
    drawing_types_by_id = {
        did: cls["predicted_drawing_type"] for did, cls in classifications.items()
    }
    non_ocr_obs = [o for o in obs_list if not o.get("ocr_only")]
    eligible_structural_ids = [
        str(o["drawing_id"])
        for o in non_ocr_obs
        if classifications[str(o["drawing_id"])]["predicted_drawing_type"] in _ELIGIBLE_STRUCTURAL_TYPES
        and not classifications[str(o["drawing_id"])]["title_content_mismatch"]
        and o.get("geometry_status") == "PRESENT"
    ]
    primary_target_id = _safe_target_drawing_id(str(obs_list[0]["drawing_id"]))

    # Non-marine domain gate (all non-OCR drawings clearly non-marine)
    non_marine_hits_all = [
        h
        for o in non_ocr_obs
        for h in o.get("particulars", {}).get("non_marine_domain_hits", [])
    ]
    total_marine_score = sum(
        sum(classifications[str(o["drawing_id"])]["evidence_scores"].values())
        for o in non_ocr_obs
    )
    inland_all_pre, inland_native_pre, ocean_all_pre, class_pre = _collect_inland_scope_facts(
        non_ocr_obs
    )
    if (
        non_ocr_obs
        and non_marine_hits_all
        and total_marine_score < 2
        and not inland_all_pre
        and not class_pre
    ):
        nm_reason = (
            f"Target regulation {target_regulation} is NOT_APPLICABLE: supplied drawing(s) "
            f"show non-marine mechanical/automotive markers ({', '.join(non_marine_hits_all[:4])})."
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
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "observed_domain": "NON_MARINE_OUT_OF_DOMAIN",
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": False,
                    "detected_scope": "NON_MARINE_OUT_OF_DOMAIN",
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_NON_MARINE_DOMAIN",
                        verdict="NOT_APPLICABLE",
                        rule_id="RULE_MK_01_QCVN72_SCOPE",
                        evidence={"non_marine_domain_hits": non_marine_hits_all},
                        reason=nm_reason,
                    )
                ],
                "checks_executed": ["Domain applicability check (QCVN 72 Clause 1.1.1)"],
                "checks_not_executed": [
                    "QCVN 72 Clause 2.4.3-2 centerline double-bottom height (non-marine domain)",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": limitations_base,
                "proposal_only_actions": [],
            }
        )

    # Multi-sheet statutory-exclusion shortcut when ALL non-OCR sheets explicitly carry statutory exclusions
    if len(obs_list) >= 2 and non_ocr_obs and len(non_ocr_obs) == len(obs_list):
        all_sheet_excls = [
            list(o.get("particulars", {}).get("explicit_exclusion_evidences", []))
            for o in non_ocr_obs
        ]
        if all(bool(ex) for ex in all_sheet_excls) and not inland_all_pre:
            merged_excls: list[str] = []
            for ex_list in all_sheet_excls:
                for item in ex_list:
                    if item not in merged_excls:
                        merged_excls.append(item)
            excl_multi = _classify_exclusion_basis(merged_excls, length_excluded=False)
            if excl_multi is not None:
                c_basis, excl_fid, detected, ref_reg = excl_multi
                excl_reason = (
                    f"Target regulation {target_regulation} is NOT_APPLICABLE across all supplied sheets "
                    f"under Clause {c_basis} ({detected}); governing regulation={ref_reg}."
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
                        "summary": excl_reason,
                        "observed_scope": {
                            "drawing_count": len(obs_list),
                            "drawing_ids": [o["drawing_id"] for o in obs_list],
                            "drawing_types_by_id": drawing_types_by_id,
                            "eligible_structural_drawing_ids": eligible_structural_ids,
                        },
                        "applicable_regulation_scope": {
                            "target_regulation": target_regulation,
                            "sub_clause": "2.4.3-2",
                            "in_scope": False,
                            "clause_basis": c_basis,
                            "detected_scope": detected,
                            "referred_regulation": ref_reg,
                        },
                        "partial_package": bool(partial_package),
                        "findings": [
                            _make_finding(
                                rules_by_id,
                                finding_id=excl_fid,
                                verdict="NOT_APPLICABLE",
                                rule_id="RULE_MK_01_QCVN72_SCOPE",
                                evidence={
                                    "clause_basis": c_basis,
                                    "explicit_exclusion_evidences": merged_excls,
                                    "referred_regulation": ref_reg,
                                },
                                reason=excl_reason,
                            )
                        ],
                        "checks_executed": ["Statutory scope exclusion check (QCVN 72 1.1.1 / 1.1.2 / 1.1.4)"],
                        "checks_not_executed": [
                            f"QCVN 72 Clause 2.4.3-2 centerline double-bottom height (excluded per Clause {c_basis})",
                            *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                        ],
                        "limitations": limitations_base,
                        "proposal_only_actions": [],
                    }
                )

    # Multi-sheet Comparability Gate (reuse V1-B verify_package_comparability)
    comparability: dict[str, Any] = {
        "status": "SINGLE_DRAWING",
        "comparable": True,
    }
    if len(obs_list) >= 2:
        comparability = verify_package_comparability(obs_list)
        if not _is_package_comparable_for_rule(comparability):
            rev_map = comparability.get("revisions_by_drawing") or {}
            comp_reason = (
                f"Multi-sheet package comparability is unverified for cross-drawing rule pooling "
                f"(status={comparability.get('status')}, revisions={rev_map}, "
                f"variants={comparability.get('design_variants_by_drawing')}): "
                f"{comparability.get('reason')}"
            )
            comp_findings: list[dict[str, Any]] = [
                _make_finding(
                    rules_by_id,
                    finding_id="F_PACKAGE_COMPARABILITY_UNVERIFIED_FOR_RULE",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                    evidence={"comparability": deepcopy(comparability)},
                    reason=comp_reason,
                )
            ]
            if not inland_native_pre:
                scope_note = (
                    "Package also lacks verified native QCVN 72 inland waterway class/scope notation "
                    f"(observed ocean_going={bool(ocean_all_pre)}, class_notations={class_pre})."
                )
                comp_findings.append(
                    _make_finding(
                        rules_by_id,
                        finding_id="F_SCOPE_UNVERIFIED",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_01_QCVN72_SCOPE",
                        evidence={
                            "drawing_types_by_id": drawing_types_by_id,
                            "ocean_going_observed": bool(ocean_all_pre),
                            "class_notations": class_pre,
                        },
                        reason=scope_note,
                    )
                )
            if not eligible_structural_ids:
                sheet_note = (
                    "Package contains no eligible MIDSHIP_STRUCTURAL or BASIC_STRUCTURAL drawing with "
                    f"native CAD geometry (observed types={drawing_types_by_id})."
                )
                comp_findings.append(
                    _make_finding(
                        rules_by_id,
                        finding_id="F_ELIGIBLE_STRUCTURAL_SHEET_MISSING",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                        evidence={
                            "drawing_types_by_id": drawing_types_by_id,
                            "eligible_structural_drawing_ids": [],
                        },
                        reason=sheet_note,
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
                    "summary": comp_reason,
                    "observed_scope": {
                        "drawing_count": len(obs_list),
                        "drawing_ids": [o["drawing_id"] for o in obs_list],
                        "drawing_types_by_id": drawing_types_by_id,
                        "eligible_structural_drawing_ids": eligible_structural_ids,
                        "comparability": comparability,
                        "cross_sheet_pooling_permitted": False,
                    },
                    "applicable_regulation_scope": {
                        "target_regulation": target_regulation,
                        "sub_clause": "2.4.3-2",
                        "in_scope": None,
                        "comparability_verified": False,
                    },
                    "partial_package": bool(partial_package),
                    "findings": comp_findings,
                    "checks_executed": [
                        "Multi-sheet vessel and explicit revision comparability gate (V1-B)",
                    ],
                    "checks_not_executed": [
                        "Cross-sheet pooling of vessel length L, scope, and double-bottom height (comparability unverified)",
                        "QCVN 72 Clause 2.4.3-2 centerline double-bottom height evaluation",
                        *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                    ],
                    "limitations": [comp_reason, *limitations_base],
                    "proposal_only_actions": [],
                }
            )

    # OCR-only rejection gate (when all supplied observations are OCR_ONLY)
    if not non_ocr_obs:
        ocr_db_facts = [
            deepcopy(f)
            for o in obs_list
            for f in o.get("engineering_facts", [])
            if f.get("fact_key") in {"double_bottom_height_mm", "unbound_double_bottom_height_mm"}
        ]
        ocr_reason = (
            "All supplied drawing observations are OCR_ONLY; unverified OCR text cannot prove "
            "QCVN 72 scope, vessel length L, or Clause 2.4.3-2 centerline double-bottom compliance."
        )
        ocr_findings = [
            _make_finding(
                rules_by_id,
                finding_id="F_SCOPE_UNVERIFIED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={"ocr_only_drawing_ids": [o["drawing_id"] for o in obs_list]},
                reason=ocr_reason,
            ),
            _make_finding(
                rules_by_id,
                finding_id="F_UNVERIFIED_OR_UNBOUND_DOUBLE_BOTTOM_EVIDENCE",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                evidence={
                    "provenance_classes": ["OCR_ONLY"],
                    "verification_states": ["UNVERIFIED_OCR"],
                    "bound_facts": ocr_db_facts,
                },
                reason=ocr_reason,
            ),
        ]
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
                "summary": ocr_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": [],
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": None,
                    "detected_scope": "OCR_ONLY_UNVERIFIED",
                },
                "partial_package": bool(partial_package),
                "findings": ocr_findings,
                "checks_executed": ["OCR provenance gate"],
                "checks_not_executed": [
                    "QCVN 72 Clause 2.4.3-2 centerline double-bottom height (OCR_ONLY blocked)",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": [ocr_reason, *limitations_base],
                "proposal_only_actions": [],
            }
        )

    # Scope, statutory exclusion, and single-bottom gate on single sheet or COMPARABLE_VERIFIED package
    checks_executed: list[str] = [
        "Regulatory applicability scope gate (QCVN 72 Clauses 1.1.1, 1.1.2, 1.1.4 & 3.2.1)",
    ]
    if len(obs_list) >= 2:
        checks_executed.insert(0, "Multi-sheet vessel and explicit revision comparability gate (V1-B)")

    inland_all, inland_native, ocean_all, class_vals = _collect_inland_scope_facts(non_ocr_obs)
    explicit_exclusions: list[str] = []
    single_bottom_evidences: list[str] = []
    single_bottom_facts: list[dict[str, Any]] = []
    all_non_ocr_db_facts: list[dict[str, Any]] = []

    trusted_l_vals: list[float] = []
    trusted_lwl_vals: list[float] = []
    for obs in non_ocr_obs:
        part = obs.get("particulars", {})
        for ex in part.get("explicit_exclusion_evidences", []):
            if ex not in explicit_exclusions:
                explicit_exclusions.append(ex)
        for sb in part.get("single_bottom_evidences", []):
            if sb not in single_bottom_evidences:
                single_bottom_evidences.append(sb)
        for fact in obs.get("engineering_facts", []):
            fkey = fact.get("fact_key")
            vstate = fact.get("verification_state")
            nval = fact.get("normalized_value")
            if fkey == "hull_bottom_configuration" and nval == "SINGLE_BOTTOM":
                single_bottom_facts.append(deepcopy(fact))
            elif fkey == "double_bottom_height_mm":
                all_non_ocr_db_facts.append(deepcopy(fact))
            elif (
                fkey == "design_length_l_m"
                and vstate in _TRUSTED_OR_FIXTURE_STATES
                and isinstance(nval, (int, float))
                and not isinstance(nval, bool)
            ):
                trusted_l_vals.append(float(nval))
            elif (
                fkey == "lwl_m"
                and vstate in _TRUSTED_OR_FIXTURE_STATES
                and isinstance(nval, (int, float))
                and not isinstance(nval, bool)
            ):
                trusted_lwl_vals.append(float(nval))

    exclusions_111 = [t for t in explicit_exclusions if t in _CLAUSE_1_1_1_MAP]
    exclusions_112 = [t for t in explicit_exclusions if t in _CLAUSE_1_1_2_MAP]
    exclusions_114 = [t for t in explicit_exclusions if t in _CLAUSE_1_1_4_TAGS]

    if (inland_all and (ocean_all or exclusions_111)) or len(class_vals) > 1:
        scope_conf_reason = (
            "Conflicting service-area or class-notation declarations prevent QCVN 72 applicability "
            f"resolution (class_notations={class_vals}, ocean_going={bool(ocean_all)}, exclusions={exclusions_111})."
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
                "summary": scope_conf_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": None,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_SCOPE_CONFLICT",
                        verdict="CONFLICT",
                        rule_id="RULE_MK_01_QCVN72_SCOPE",
                        evidence={
                            "class_notations": class_vals,
                            "explicit_exclusions": explicit_exclusions,
                            "bound_facts": _dedup_facts(inland_all + ocean_all),
                        },
                        reason=scope_conf_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    "QCVN 72 Clause 2.4.3-2 centerline double-bottom height (scope conflict)",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": limitations_base,
                "proposal_only_actions": [
                    build_marine_core_proposal(
                        target_drawing_id=primary_target_id,
                        action_kind="RECONCILE_SERVICE_AREA_SCOPE",
                        evidence={"class_notations": class_vals, "explicit_exclusions": explicit_exclusions},
                    )
                ],
            }
        )

    length_conflict_pre = (
        (len(trusted_l_vals) >= 2 and (max(trusted_l_vals) - min(trusted_l_vals)) > 0.05)
        or (len(trusted_lwl_vals) >= 2 and (max(trusted_lwl_vals) - min(trusted_lwl_vals)) > 0.05)
    )
    length_excluded = (
        not length_conflict_pre
        and (
            (bool(trusted_l_vals) and min(trusted_l_vals) > 140.0)
            or (not trusted_l_vals and bool(trusted_lwl_vals) and (0.96 * min(trusted_lwl_vals)) > 140.0)
        )
    )

    if (
        exclusions_114
        and inland_all
        and not exclusions_111
        and not exclusions_112
        and not length_excluded
    ):
        mixed_114_reason = (
            f"Insufficient evidence under Clause 1.1.4 ({exclusions_114[0]}): defense, security, and fishing "
            "vessels are not mandatorily governed by QCVN 72:2025/BGTVT, yet inland class markers are present."
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
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": None,
                    "clause_basis": "1.1.4",
                    "detected_scope": exclusions_114[0],
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_SCOPE_CLAUSE_1_1_4_VOLUNTARY_CONFIRMATION_REQUIRED",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_01_QCVN72_SCOPE",
                        evidence={
                            "clause_basis": "1.1.4",
                            "explicit_exclusion_evidences": exclusions_114,
                            "bound_facts": inland_all,
                        },
                        reason=mixed_114_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    "QCVN 72 Clause 2.4.3-2 centerline double-bottom height pending Clause 1.1.4 confirmation",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": [mixed_114_reason, *limitations_base],
                "proposal_only_actions": [
                    build_marine_core_proposal(
                        target_drawing_id=primary_target_id,
                        action_kind="CONFIRM_REGULATORY_SERVICE_AREA",
                        evidence={"clause_basis": "1.1.4", "explicit_exclusion_evidences": exclusions_114},
                    )
                ],
            }
        )

    excl_info = _classify_exclusion_basis(explicit_exclusions, length_excluded=length_excluded)
    if excl_info is not None:
        clause_basis, excl_fid, detected, referred_reg = excl_info
        out_reason = (
            f"Target regulation {target_regulation} Clause 2.4.3-2 is NOT_APPLICABLE under Clause "
            f"{clause_basis} ({detected}); referred regulation={referred_reg}."
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
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": False,
                    "clause_basis": clause_basis,
                    "detected_scope": detected,
                    "referred_regulation": referred_reg,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id=excl_fid,
                        verdict="NOT_APPLICABLE",
                        rule_id="RULE_MK_01_QCVN72_SCOPE",
                        evidence={
                            "clause_basis": clause_basis,
                            "detected_scope": detected,
                            "explicit_exclusion_evidences": explicit_exclusions,
                            "referred_regulation": referred_reg,
                        },
                        reason=out_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    f"QCVN 72 Clause 2.4.3-2 centerline double-bottom height (excluded per Clause {clause_basis})",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": limitations_base,
                "proposal_only_actions": [],
            }
        )

    # Single-bottom exemption vs contradictory bottom configuration
    if single_bottom_evidences:
        checks_executed.append("Single-bottom hull configuration exemption check (QCVN 72 2.4.3)")
        if all_non_ocr_db_facts:
            sb_conf_reason = (
                "Contradictory hull bottom configuration: drawing declares single-bottom "
                f"({single_bottom_evidences}) while also supplying double-bottom height facts."
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
                    "summary": sb_conf_reason,
                    "observed_scope": {
                        "drawing_count": len(obs_list),
                        "drawing_ids": [o["drawing_id"] for o in obs_list],
                        "drawing_types_by_id": drawing_types_by_id,
                        "eligible_structural_drawing_ids": eligible_structural_ids,
                        "comparability": comparability,
                    },
                    "applicable_regulation_scope": {
                        "target_regulation": target_regulation,
                        "sub_clause": "2.4.3-2",
                        "in_scope": True,
                    },
                    "partial_package": bool(partial_package),
                    "findings": [
                        _make_finding(
                            rules_by_id,
                            finding_id="F_BOTTOM_CONFIGURATION_CONFLICT",
                            verdict="CONFLICT",
                            rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                            evidence={
                                "single_bottom_evidences": single_bottom_evidences,
                                "bound_facts": _dedup_facts(single_bottom_facts + all_non_ocr_db_facts),
                            },
                            reason=sb_conf_reason,
                        )
                    ],
                    "checks_executed": checks_executed,
                    "checks_not_executed": list(_MANDATORY_UNEXECUTED_SIBLING_CHECKS),
                    "limitations": limitations_base,
                    "proposal_only_actions": [
                        build_marine_core_proposal(
                            target_drawing_id=primary_target_id,
                            action_kind="REVIEW_DOUBLE_BOTTOM_SCANTLINGS",
                            evidence={"single_bottom_evidences": single_bottom_evidences},
                        )
                    ],
                }
            )

        sb_reason = (
            f"Rule RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT (Clause 2.4.3-2) is NOT_APPLICABLE: "
            f"vessel explicitly declares single-bottom construction ({single_bottom_evidences})."
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
                "summary": sb_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "single_bottom_evidences": single_bottom_evidences,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": False,
                    "detected_scope": "SINGLE_BOTTOM_EXEMPT",
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_SINGLE_BOTTOM_EXEMPT",
                        verdict="NOT_APPLICABLE",
                        rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                        evidence={
                            "single_bottom_evidences": single_bottom_evidences,
                            "bound_facts": single_bottom_facts,
                        },
                        reason=sb_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    "QCVN 72 Phần 2A Chương 2 Clause 2.4.2 single-bottom floors and keelson scantlings",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": limitations_base,
                "proposal_only_actions": [],
            }
        )

    # Missing verified inland waterway scope
    if not inland_all:
        detected_scope = "UNVERIFIED_OCEAN_GOING_LABEL" if ocean_all else "UNKNOWN_CLASSIFICATION"
        unv_scope_reason = (
            "Insufficient evidence to confirm QCVN 72:2025/BGTVT inland waterway scope "
            f"(detected_scope={detected_scope}; VR-SB/SI/SII/SIII or explicit QCVN 72 notation required)."
        )
        scope_findings = [
            _make_finding(
                rules_by_id,
                finding_id="F_SCOPE_UNVERIFIED",
                verdict="INSUFFICIENT_EVIDENCE",
                rule_id="RULE_MK_01_QCVN72_SCOPE",
                evidence={
                    "detected_scope": detected_scope,
                    "ocean_going_observed": bool(ocean_all),
                    "drawing_types_by_id": drawing_types_by_id,
                },
                reason=unv_scope_reason,
            )
        ]
        if not eligible_structural_ids:
            scope_findings.append(
                _make_finding(
                    rules_by_id,
                    finding_id="F_ELIGIBLE_STRUCTURAL_SHEET_MISSING",
                    verdict="INSUFFICIENT_EVIDENCE",
                    rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                    evidence={
                        "drawing_types_by_id": drawing_types_by_id,
                        "eligible_structural_drawing_ids": [],
                    },
                    reason=(
                        "No eligible MIDSHIP_STRUCTURAL or BASIC_STRUCTURAL sheet with native CAD "
                        f"geometry supplied (observed types={drawing_types_by_id})."
                    ),
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
                "summary": unv_scope_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": None,
                    "detected_scope": detected_scope,
                },
                "partial_package": bool(partial_package),
                "findings": scope_findings,
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    "QCVN 72 Clause 2.4.3-2 centerline double-bottom height pending verified inland scope",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": [unv_scope_reason, *limitations_base],
                "proposal_only_actions": [
                    build_marine_core_proposal(
                        target_drawing_id=primary_target_id,
                        action_kind="CONFIRM_REGULATORY_SERVICE_AREA",
                        evidence={"detected_scope": detected_scope},
                    )
                ],
            }
        )

    # Eligible structural sheet & title-content coherence gate
    checks_executed.append("Eligible structural drawing type and CAD geometry gate (MCN / KCCB)")
    mismatched_structural = [
        str(o["drawing_id"])
        for o in non_ocr_obs
        if classifications[str(o["drawing_id"])]["title_content_mismatch"]
    ]
    if mismatched_structural:
        mm_did = mismatched_structural[0]
        mm_cls = classifications[mm_did]
        mm_reason = (
            f"Drawing {mm_did} declares title type {mm_cls['title_declared_type']} "
            f"but content classifies as {mm_cls['predicted_drawing_type']}."
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
                "summary": mm_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": True,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_TITLE_CONTENT_MISMATCH",
                        verdict="CONFLICT",
                        rule_id="RULE_MK_06_CROSS_DRAWING_COHERENCE",
                        evidence=mm_cls,
                        reason=mm_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": list(_MANDATORY_UNEXECUTED_SIBLING_CHECKS),
                "limitations": limitations_base,
                "proposal_only_actions": [
                    build_marine_core_proposal(
                        target_drawing_id=_safe_target_drawing_id(mm_did),
                        action_kind="FIX_TITLE_BLOCK_TYPE_MISMATCH",
                        evidence={
                            "predicted_drawing_type": mm_cls["predicted_drawing_type"],
                            "title_declared_type": mm_cls["title_declared_type"],
                        },
                    )
                ],
            }
        )

    structural_obs_any_geom = [
        o
        for o in non_ocr_obs
        if classifications[str(o["drawing_id"])]["predicted_drawing_type"] in _ELIGIBLE_STRUCTURAL_TYPES
    ]
    if not structural_obs_any_geom:
        no_sheet_reason = (
            "Cannot evaluate RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT: no MIDSHIP_STRUCTURAL or "
            f"BASIC_STRUCTURAL sheet supplied (observed types={drawing_types_by_id})."
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
                "summary": no_sheet_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": [],
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": True,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_ELIGIBLE_STRUCTURAL_SHEET_MISSING",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                        evidence={
                            "drawing_types_by_id": drawing_types_by_id,
                            "eligible_structural_drawing_ids": [],
                        },
                        reason=no_sheet_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    "QCVN 72 Clause 2.4.3-2 centerline double-bottom height (MCN/KCCB drawing absent)",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": [no_sheet_reason, *limitations_base],
                "proposal_only_actions": [],
            }
        )

    # Inspect double-bottom facts on structural sheets (override conflicts, fixture floor violations, provenance)
    checks_executed.append("Centerline double-bottom EngineeringFact provenance and DIMENSION override gate")
    override_db_facts = [
        deepcopy(f)
        for o in structural_obs_any_geom
        for f in o.get("engineering_facts", [])
        if f.get("fact_key") == "double_bottom_height_mm"
        and f.get("verification_state") == "CONFLICTING_OVERRIDE"
    ]
    if override_db_facts:
        ov_did = _safe_target_drawing_id(str(override_db_facts[0]["drawing_id"]))
        ov_reason = (
            f"Native DIMENSION override conflict on centerline double-bottom height ({ov_did}): "
            f"{override_db_facts[0]['trust_reason']}"
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
                "summary": ov_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": True,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_DOUBLE_BOTTOM_DIMENSION_OVERRIDE_CONFLICT",
                        verdict="CONFLICT",
                        rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                        evidence={
                            "sub_clause": "2.4.3-2",
                            "bound_facts": override_db_facts,
                        },
                        reason=ov_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": list(_MANDATORY_UNEXECUTED_SIBLING_CHECKS),
                "limitations": limitations_base,
                "proposal_only_actions": [
                    build_marine_core_proposal(
                        target_drawing_id=ov_did,
                        action_kind="VERIFY_CAD_GEOMETRY_ENTITIES",
                        evidence={"conflict_count": len(override_db_facts)},
                    )
                ],
            }
        )

    fixture_below_floor = [
        deepcopy(f)
        for o in structural_obs_any_geom
        for f in o.get("engineering_facts", [])
        if f.get("fact_key") == "double_bottom_height_mm"
        and f.get("provenance_class") == "FIXTURE_SUPPLIED"
        and isinstance(f.get("normalized_value"), (int, float))
        and not isinstance(f.get("normalized_value"), bool)
        and float(f["normalized_value"]) < 700.0
    ]
    if fixture_below_floor:
        worst_fix = min(fixture_below_floor, key=lambda x: float(x["normalized_value"]))
        fix_did = _safe_target_drawing_id(str(worst_fix["drawing_id"]))
        fix_val = float(worst_fix["normalized_value"])
        fix_low_reason = (
            f"Observed centerline double-bottom height {fix_val:.1f} mm on {fix_did} violates "
            "QCVN 72 Clause 2.4.3-2 universal 700.0 mm minimum floor."
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
                "summary": fix_low_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": True,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_DOUBLE_BOTTOM_HEIGHT_BELOW_MINIMUM",
                        verdict="CONFLICT",
                        rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                        evidence={
                            "sub_clause": "2.4.3-2",
                            "observed_db_height_mm": fix_val,
                            "required_min_db_height_mm": 700.0,
                            "invariant_minimum": True,
                            "bound_facts": [worst_fix],
                        },
                        reason=fix_low_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": list(_MANDATORY_UNEXECUTED_SIBLING_CHECKS),
                "limitations": limitations_base,
                "proposal_only_actions": [
                    build_marine_core_proposal(
                        target_drawing_id=fix_did,
                        action_kind="REVIEW_DOUBLE_BOTTOM_SCANTLINGS",
                        evidence={"observed_db_height_mm": fix_val, "required_min_mm": 700.0},
                    )
                ],
            }
        )

    eligible_structural_obs = [
        o for o in structural_obs_any_geom if o.get("geometry_status") == "PRESENT"
    ]
    verified_db_facts = [
        deepcopy(f)
        for o in eligible_structural_obs
        for f in o.get("engineering_facts", [])
        if f.get("fact_key") == "double_bottom_height_mm"
        and _is_native_verified_fact(f)
        and isinstance(f.get("normalized_value"), (int, float))
        and not isinstance(f.get("normalized_value"), bool)
    ]
    unverified_or_unbound_db_facts = [
        deepcopy(f)
        for o in structural_obs_any_geom
        for f in o.get("engineering_facts", [])
        if f.get("fact_key") in {"double_bottom_height_mm", "unbound_double_bottom_height_mm"}
        and not (
            f.get("fact_key") == "double_bottom_height_mm"
            and _is_native_verified_fact(f)
            and o.get("geometry_status") == "PRESENT"
        )
    ]

    if not verified_db_facts:
        if unverified_or_unbound_db_facts:
            prov_classes = sorted({str(f["provenance_class"]) for f in unverified_or_unbound_db_facts})
            ver_states = sorted({str(f["verification_state"]) for f in unverified_or_unbound_db_facts})
            reasons_joined = "; ".join(f["trust_reason"] for f in unverified_or_unbound_db_facts[:3])
            unv_db_reason = (
                "Double-bottom height evidence lacks verified native centerline CAD provenance "
                f"(provenance={prov_classes}, state={ver_states}): {reasons_joined}"
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
                    "summary": unv_db_reason,
                    "observed_scope": {
                        "drawing_count": len(obs_list),
                        "drawing_ids": [o["drawing_id"] for o in obs_list],
                        "drawing_types_by_id": drawing_types_by_id,
                        "eligible_structural_drawing_ids": eligible_structural_ids,
                        "comparability": comparability,
                    },
                    "applicable_regulation_scope": {
                        "target_regulation": target_regulation,
                        "sub_clause": "2.4.3-2",
                        "in_scope": True,
                    },
                    "partial_package": bool(partial_package),
                    "findings": [
                        _make_finding(
                            rules_by_id,
                            finding_id="F_UNVERIFIED_OR_UNBOUND_DOUBLE_BOTTOM_EVIDENCE",
                            verdict="INSUFFICIENT_EVIDENCE",
                            rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                            evidence={
                                "sub_clause": "2.4.3-2",
                                "provenance_classes": prov_classes,
                                "verification_states": ver_states,
                                "bound_facts": unverified_or_unbound_db_facts,
                            },
                            reason=unv_db_reason,
                        )
                    ],
                    "checks_executed": checks_executed,
                    "checks_not_executed": [
                        "QCVN 72 Clause 2.4.3-2 compliance verdict (verified native centerline CAD fact required)",
                        *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                    ],
                    "limitations": [unv_db_reason, *limitations_base],
                    "proposal_only_actions": [],
                }
            )

        if not eligible_structural_obs:
            no_geom_reason = (
                "Structural drawing(s) lack verified native CAD geometry primitives "
                f"(geometry_status={[o.get('geometry_status') for o in structural_obs_any_geom]})."
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
                    "summary": no_geom_reason,
                    "observed_scope": {
                        "drawing_count": len(obs_list),
                        "drawing_ids": [o["drawing_id"] for o in obs_list],
                        "drawing_types_by_id": drawing_types_by_id,
                        "eligible_structural_drawing_ids": [],
                        "comparability": comparability,
                    },
                    "applicable_regulation_scope": {
                        "target_regulation": target_regulation,
                        "sub_clause": "2.4.3-2",
                        "in_scope": True,
                    },
                    "partial_package": bool(partial_package),
                    "findings": [
                        _make_finding(
                            rules_by_id,
                            finding_id="F_ELIGIBLE_STRUCTURAL_SHEET_MISSING",
                            verdict="INSUFFICIENT_EVIDENCE",
                            rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                            evidence={
                                "drawing_types_by_id": drawing_types_by_id,
                                "eligible_structural_drawing_ids": [],
                            },
                            reason=no_geom_reason,
                        )
                    ],
                    "checks_executed": checks_executed,
                    "checks_not_executed": [
                        "QCVN 72 Clause 2.4.3-2 centerline double-bottom height (CAD geometry missing)",
                        *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                    ],
                    "limitations": [no_geom_reason, *limitations_base],
                    "proposal_only_actions": [],
                }
            )

        missing_db_reason = (
            f"Eligible structural drawing(s) {eligible_structural_ids} contain no centerline "
            "double-bottom height annotation or bound DIMENSION entity."
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
                "summary": missing_db_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": True,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_MISSING_DOUBLE_BOTTOM_HEIGHT_EVIDENCE",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                        evidence={"eligible_structural_drawing_ids": eligible_structural_ids},
                        reason=missing_db_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    "QCVN 72 Clause 2.4.3-2 centerline double-bottom height (value not annotated)",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": [missing_db_reason, *limitations_base],
                "proposal_only_actions": [],
            }
        )

    # Rule Length L Gate (Clause 1.4.43-1) & Clause 2.4.3-2 threshold evaluation
    checks_executed.append("Rule design length L gate (QCVN 72 Clause 1.4.43-1)")
    verified_l_facts: list[dict[str, Any]] = []
    verified_lwl_facts: list[dict[str, Any]] = []
    verified_loa_facts: list[dict[str, Any]] = []
    lpp_or_approx_facts: list[dict[str, Any]] = []

    for obs in non_ocr_obs:
        for fact in obs.get("engineering_facts", []):
            fkey = fact.get("fact_key")
            nval = fact.get("normalized_value")
            is_num = isinstance(nval, (int, float)) and not isinstance(nval, bool)
            if fkey == "design_length_l_m" and _is_native_verified_fact(fact) and is_num:
                verified_l_facts.append(deepcopy(fact))
            elif fkey == "lwl_m" and _is_native_verified_fact(fact) and is_num:
                verified_lwl_facts.append(deepcopy(fact))
            elif fkey == "loa_m" and _is_native_verified_fact(fact) and is_num:
                verified_loa_facts.append(deepcopy(fact))
            elif fkey in {"lpp_m", "design_length_l_m", "lwl_m", "loa_m"} and fact.get("verification_state") in {
                "VERIFIED",
                "PROVISIONAL_APPROXIMATE",
                "UNVERIFIED_UNITLESS",
            }:
                lpp_or_approx_facts.append(deepcopy(fact))

    l_vals = [float(f["normalized_value"]) for f in verified_l_facts]
    lwl_vals = [float(f["normalized_value"]) for f in verified_lwl_facts]
    loa_vals = [float(f["normalized_value"]) for f in verified_loa_facts]

    l_violations: list[str] = []
    if len(l_vals) >= 2 and (max(l_vals) - min(l_vals)) > 0.05:
        l_violations.append(f"conflicting design_length_l_m values {sorted(set(l_vals))}")
    if len(lwl_vals) >= 2 and (max(lwl_vals) - min(lwl_vals)) > 0.05:
        l_violations.append(f"conflicting lwl_m values {sorted(set(lwl_vals))}")
    if l_vals and loa_vals and max(l_vals) > min(loa_vals) + 0.05:
        l_violations.append(f"design length L ({max(l_vals):.2f} m) > Loa ({min(loa_vals):.2f} m)")
    if lwl_vals and loa_vals and max(lwl_vals) > min(loa_vals) + 0.05:
        l_violations.append(f"Lwl ({max(lwl_vals):.2f} m) > Loa ({min(loa_vals):.2f} m)")
    if l_vals and lwl_vals:
        if max(l_vals) > min(lwl_vals) + 0.05:
            l_violations.append(
                f"design length L ({max(l_vals):.2f} m) > Lwl ({min(lwl_vals):.2f} m) violates Clause 1.4.43-1"
            )
        if min(l_vals) < 0.96 * max(lwl_vals) - 0.05:
            l_violations.append(
                f"design length L ({min(l_vals):.2f} m) < 0.96 * Lwl ({0.96 * max(lwl_vals):.2f} m) violates Clause 1.4.43-1"
            )

    if l_violations:
        l_conf_reason = "Conflicting vessel rule length declarations: " + "; ".join(l_violations) + "."
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
                "summary": l_conf_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": True,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_RULE_LENGTH_CONFLICT",
                        verdict="CONFLICT",
                        rule_id="RULE_MK_01_QCVN72_SCOPE",
                        evidence={
                            "violations": l_violations,
                            "bound_facts": _dedup_facts(
                                verified_l_facts + verified_lwl_facts + verified_loa_facts
                            ),
                        },
                        reason=l_conf_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    "QCVN 72 Clause 2.4.3-2 threshold evaluation (rule length L conflict)",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": limitations_base,
                "proposal_only_actions": [
                    build_marine_core_proposal(
                        target_drawing_id=primary_target_id,
                        action_kind="RECONCILE_L_PARTICULAR",
                        evidence={"violations": l_violations},
                    )
                ],
            }
        )

    l_lo: float | None = None
    l_hi: float | None = None
    length_basis = "UNAVAILABLE"
    length_bound_facts: list[dict[str, Any]] = []
    if verified_l_facts:
        l_lo = round(l_vals[0], 4)
        l_hi = l_lo
        length_basis = "EXPLICIT_DESIGN_LENGTH_L"
        length_bound_facts = _dedup_facts(verified_l_facts + verified_lwl_facts)
    elif verified_lwl_facts:
        l_lo = round(0.96 * lwl_vals[0], 4)
        l_hi = round(lwl_vals[0], 4)
        length_basis = "PROVEN_LWL_INTERVAL_1_4_43"
        length_bound_facts = _dedup_facts(verified_lwl_facts)

    if l_lo is not None and l_hi is not None and l_lo <= 140.0 < l_hi:
        s140_reason = (
            f"Clause 1.4.43-1 design length interval [{l_lo:.2f}, {l_hi:.2f}] m derived from "
            "Lwl straddles the QCVN 72 Clause 1.1.1 140.0 m upper scope limit; explicit L required."
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
                "summary": s140_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "l_interval_m": [l_lo, l_hi],
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": None,
                    "clause_basis": "1.4.43-1",
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_RULE_LENGTH_STRADDLES_140M_SCOPE",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_01_QCVN72_SCOPE",
                        evidence={
                            "l_interval_m": [l_lo, l_hi],
                            "scope_limit_m": 140.0,
                            "bound_facts": length_bound_facts,
                        },
                        reason=s140_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    "QCVN 72 Clause 2.4.3-2 centerline double-bottom height pending explicit L <= 140 m",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": [s140_reason, *limitations_base],
                "proposal_only_actions": [],
            }
        )

    worst_db_fact = min(verified_db_facts, key=lambda f: float(f["normalized_value"]))
    min_verified_db_mm = round(float(worst_db_fact["normalized_value"]), 4)
    max_verified_db_mm = round(max(float(f["normalized_value"]) for f in verified_db_facts), 4)
    worst_db_did = _safe_target_drawing_id(str(worst_db_fact["drawing_id"]))

    if len(verified_db_facts) >= 2 and (max_verified_db_mm - min_verified_db_mm) > 10.0:
        db_conf_reason = (
            f"Contradictory verified centerline double-bottom height facts observed "
            f"(min={min_verified_db_mm:.1f} mm vs max={max_verified_db_mm:.1f} mm; delta > 10.0 mm tolerance)."
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
                "summary": db_conf_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "observed_db_height_min_mm": min_verified_db_mm,
                    "observed_db_height_max_mm": max_verified_db_mm,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": True,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_DOUBLE_BOTTOM_HEIGHT_CONFLICT",
                        verdict="CONFLICT",
                        rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                        evidence={
                            "sub_clause": "2.4.3-2",
                            "min_db_height_mm": min_verified_db_mm,
                            "max_db_height_mm": max_verified_db_mm,
                            "bound_facts": verified_db_facts,
                        },
                        reason=db_conf_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": list(_MANDATORY_UNEXECUTED_SIBLING_CHECKS),
                "limitations": limitations_base,
                "proposal_only_actions": [
                    build_marine_core_proposal(
                        target_drawing_id=worst_db_did,
                        action_kind="REVIEW_DOUBLE_BOTTOM_SCANTLINGS",
                        evidence={
                            "min_db_height_mm": min_verified_db_mm,
                            "max_db_height_mm": max_verified_db_mm,
                        },
                    )
                ],
            }
        )

    # Universal 700.0 mm floor violation across all QCVN 72 ship lengths
    if min_verified_db_mm < 700.0:
        checks_executed.append("QCVN 72 Clause 2.4.3-2 centerline double-bottom minimum height check")
        req_floor = 900.0 if (l_hi is not None and l_hi > 120.0 and l_lo is not None and l_lo > 120.0) else 700.0
        floor_reason = (
            f"Observed centerline double-bottom height {min_verified_db_mm:.1f} mm on "
            f"{worst_db_fact['drawing_id']} is below QCVN 72 Clause 2.4.3-2 minimum {req_floor:.1f} mm."
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
                "summary": floor_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "l_interval_m": [l_lo, l_hi] if l_lo is not None and l_hi is not None else None,
                    "observed_db_height_mm": min_verified_db_mm,
                    "required_min_db_height_mm": req_floor,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": True,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_DOUBLE_BOTTOM_HEIGHT_BELOW_MINIMUM",
                        verdict="CONFLICT",
                        rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                        evidence={
                            "sub_clause": "2.4.3-2",
                            "drawing_id": worst_db_fact["drawing_id"],
                            "l_interval_m": [l_lo, l_hi] if l_lo is not None and l_hi is not None else None,
                            "length_basis": length_basis,
                            "observed_db_height_mm": min_verified_db_mm,
                            "required_min_db_height_mm": req_floor,
                            "bound_facts": _dedup_facts(
                                inland_native + length_bound_facts + verified_db_facts
                            ),
                        },
                        reason=floor_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": list(_MANDATORY_UNEXECUTED_SIBLING_CHECKS),
                "limitations": limitations_base,
                "proposal_only_actions": [
                    build_marine_core_proposal(
                        target_drawing_id=worst_db_did,
                        action_kind="REVIEW_DOUBLE_BOTTOM_SCANTLINGS",
                        evidence={
                            "observed_db_height_mm": min_verified_db_mm,
                            "required_min_mm": req_floor,
                        },
                    )
                ],
            }
        )

    # Require native-verified inland scope before length-dependent PASS
    if not inland_native:
        non_native_scope_reason = (
            "Inland scope notation was supplied without native DXF SHA-256 / CAD handle provenance; "
            "cannot issue verified QCVN 72 Clause 2.4.3-2 PASS."
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
                "summary": non_native_scope_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": None,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_SCOPE_UNVERIFIED",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_01_QCVN72_SCOPE",
                        evidence={"bound_facts": inland_all},
                        reason=non_native_scope_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": list(_MANDATORY_UNEXECUTED_SIBLING_CHECKS),
                "limitations": [non_native_scope_reason, *limitations_base],
                "proposal_only_actions": [],
            }
        )

    if l_lo is None or l_hi is None:
        if lpp_or_approx_facts:
            amb_l_reason = (
                "Bare Lpp, approximate (ABT.), or unitless length observation does not prove "
                "QCVN 72 Clause 1.4.43-1 design length L required to select the 120.0 m threshold."
            )
            l_fid = "F_AMBIGUOUS_RULE_LENGTH_L"
        else:
            amb_l_reason = (
                "Vessel rule length L and waterline length Lwl are missing; cannot resolve "
                "QCVN 72 Clause 2.4.3-2 120.0 m step threshold (700.0 mm vs 900.0 mm)."
            )
            l_fid = "F_MISSING_RULE_LENGTH_L"
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
                "summary": amb_l_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "observed_db_height_mm": min_verified_db_mm,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": True,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id=l_fid,
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                        evidence={
                            "sub_clause": "2.4.3-2",
                            "observed_db_height_mm": min_verified_db_mm,
                            "bound_facts": _dedup_facts(lpp_or_approx_facts + verified_db_facts),
                        },
                        reason=amb_l_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": [
                    "QCVN 72 Clause 2.4.3-2 L > 120 m (900 mm) threshold check pending verified L",
                    *_MANDATORY_UNEXECUTED_SIBLING_CHECKS,
                ],
                "limitations": [amb_l_reason, *limitations_base],
                "proposal_only_actions": [],
            }
        )

    if l_lo <= 120.0 < l_hi and 700.0 <= min_verified_db_mm < 900.0:
        s120_reason = (
            f"Clause 1.4.43-1 length interval [{l_lo:.2f}, {l_hi:.2f}] m derived from Lwl straddles "
            f"the 120.0 m Clause 2.4.3-2 step threshold (700.0 mm vs 900.0 mm) while observed "
            f"centerline double-bottom height is {min_verified_db_mm:.1f} mm (< 900.0 mm)."
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
                "summary": s120_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "l_interval_m": [l_lo, l_hi],
                    "observed_db_height_mm": min_verified_db_mm,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": True,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_RULE_LENGTH_STRADDLES_120M_THRESHOLD",
                        verdict="INSUFFICIENT_EVIDENCE",
                        rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                        evidence={
                            "sub_clause": "2.4.3-2",
                            "l_interval_m": [l_lo, l_hi],
                            "threshold_m": 120.0,
                            "observed_db_height_mm": min_verified_db_mm,
                            "bound_facts": _dedup_facts(length_bound_facts + verified_db_facts),
                        },
                        reason=s120_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": list(_MANDATORY_UNEXECUTED_SIBLING_CHECKS),
                "limitations": [s120_reason, *limitations_base],
                "proposal_only_actions": [],
            }
        )

    checks_executed.append("QCVN 72 Clause 2.4.3-2 centerline double-bottom minimum height check")
    required_min_mm = 700.0 if l_hi <= 120.0 else 900.0
    final_bound_facts = _dedup_facts(inland_native + length_bound_facts + verified_db_facts)

    if min_verified_db_mm < required_min_mm:
        below_reason = (
            f"Observed centerline double-bottom height {min_verified_db_mm:.1f} mm on "
            f"{worst_db_fact['drawing_id']} is below QCVN 72 Clause 2.4.3-2 minimum "
            f"{required_min_mm:.1f} mm for L in [{l_lo:.2f}, {l_hi:.2f}] m ({length_basis})."
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
                "summary": below_reason,
                "observed_scope": {
                    "drawing_count": len(obs_list),
                    "drawing_ids": [o["drawing_id"] for o in obs_list],
                    "drawing_types_by_id": drawing_types_by_id,
                    "eligible_structural_drawing_ids": eligible_structural_ids,
                    "l_interval_m": [l_lo, l_hi],
                    "length_basis": length_basis,
                    "observed_db_height_mm": min_verified_db_mm,
                    "required_min_db_height_mm": required_min_mm,
                    "comparability": comparability,
                },
                "applicable_regulation_scope": {
                    "target_regulation": target_regulation,
                    "sub_clause": "2.4.3-2",
                    "in_scope": True,
                    "class_notations": class_vals,
                },
                "partial_package": bool(partial_package),
                "findings": [
                    _make_finding(
                        rules_by_id,
                        finding_id="F_DOUBLE_BOTTOM_HEIGHT_BELOW_MINIMUM",
                        verdict="CONFLICT",
                        rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                        evidence={
                            "sub_clause": "2.4.3-2",
                            "drawing_id": worst_db_fact["drawing_id"],
                            "l_interval_m": [l_lo, l_hi],
                            "length_basis": length_basis,
                            "observed_db_height_mm": min_verified_db_mm,
                            "required_min_db_height_mm": required_min_mm,
                            "bound_facts": final_bound_facts,
                        },
                        reason=below_reason,
                    )
                ],
                "checks_executed": checks_executed,
                "checks_not_executed": list(_MANDATORY_UNEXECUTED_SIBLING_CHECKS),
                "limitations": limitations_base,
                "proposal_only_actions": [
                    build_marine_core_proposal(
                        target_drawing_id=worst_db_did,
                        action_kind="REVIEW_DOUBLE_BOTTOM_SCANTLINGS",
                        evidence={
                            "observed_db_height_mm": min_verified_db_mm,
                            "required_min_mm": required_min_mm,
                            "l_interval_m": [l_lo, l_hi],
                        },
                    )
                ],
            }
        )

    pass_reason = (
        f"Verified centerline double-bottom height {min_verified_db_mm:.1f} mm on "
        f"{worst_db_fact['drawing_id']} satisfies QCVN 72:2025/BGTVT Phần 2A Chương 2 "
        f"Clause 2.4.3-2 minimum {required_min_mm:.1f} mm for L in [{l_lo:.2f}, {l_hi:.2f}] m ({length_basis})."
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
            "status": "PASS",
            "summary": pass_reason,
            "observed_scope": {
                "drawing_count": len(obs_list),
                "drawing_ids": [o["drawing_id"] for o in obs_list],
                "drawing_types_by_id": drawing_types_by_id,
                "eligible_structural_drawing_ids": eligible_structural_ids,
                "l_interval_m": [l_lo, l_hi],
                "length_basis": length_basis,
                "observed_db_height_mm": min_verified_db_mm,
                "required_min_db_height_mm": required_min_mm,
                "comparability": comparability,
            },
            "applicable_regulation_scope": {
                "target_regulation": target_regulation,
                "sub_clause": "2.4.3-2",
                "in_scope": True,
                "class_notations": class_vals,
            },
            "partial_package": bool(partial_package),
            "findings": [
                _make_finding(
                    rules_by_id,
                    finding_id="F_DOUBLE_BOTTOM_HEIGHT_COMPLIANT",
                    verdict="PASS",
                    rule_id="RULE_MK_09_DOUBLE_BOTTOM_MIN_HEIGHT",
                    evidence={
                        "sub_clause": "2.4.3-2",
                        "drawing_id": worst_db_fact["drawing_id"],
                        "l_interval_m": [l_lo, l_hi],
                        "length_basis": length_basis,
                        "observed_db_height_mm": min_verified_db_mm,
                        "required_min_db_height_mm": required_min_mm,
                        "bound_facts": final_bound_facts,
                    },
                    reason=pass_reason,
                )
            ],
            "checks_executed": checks_executed,
            "checks_not_executed": list(_MANDATORY_UNEXECUTED_SIBLING_CHECKS),
            "limitations": limitations_base,
            "proposal_only_actions": [],
        }
    )


__all__ = ["evaluate_double_bottom_height_rule"]
