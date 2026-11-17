"""Minimal cross-domain Engineering Fact contract and CAD evidence binding (V1-A).

Binds extracted technical facts to verifiable CAD entity handles, entity types,
layers, units, drawing SHA-256 provenance, and fail-closed verification states
without creating a plugin framework or duplicating ``CAD Core`` read facades.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import math
import re
from typing import Any

from cad_agent.drawing_contracts import canonical_json_sha256

from .contracts import MarineKnowledgeError
from .text_normalization import fold_marine_search_text, normalize_marine_cad_text

ENGINEERING_FACT_SCHEMA_VERSION = "engineering-fact-1.0"

PROVENANCE_CLASSES: frozenset[str] = frozenset(
    {
        "NATIVE_CAD_EVIDENCE",
        "NATIVE_CAD_UNBOUND_TEXT",
        "NATIVE_MEASURED_GEOMETRY",
        "OCR_ONLY",
        "FIXTURE_SUPPLIED",
        "INFERRED_UNVERIFIED",
    }
)

VERIFICATION_STATES: frozenset[str] = frozenset(
    {
        "VERIFIED",
        "PROVISIONAL_APPROXIMATE",
        "FIXTURE_UNBOUND_TO_DXF_BYTES",
        "UNVERIFIED_UNITLESS",
        "CONFLICTING_OVERRIDE",
        "UNVERIFIED_UNBOUND_TEXT",
        "UNVERIFIED_OCR",
        "UNVERIFIED_INFERRED",
    }
)

_FACT_FIELDS: frozenset[str] = frozenset(
    {
        "schema_version",
        "domain",
        "drawing_id",
        "drawing_path",
        "drawing_sha256",
        "sheet_id",
        "revision",
        "fact_key",
        "entity_handles",
        "entity_type",
        "layer",
        "observed_raw",
        "observed_value",
        "observed_unit",
        "normalized_value",
        "normalized_unit",
        "provenance_class",
        "verification_state",
        "trust_reason",
        "fact_id",
        "fact_sha256",
    }
)

_DOMAIN_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_INSUNITS_TO_MM: dict[int, float] = {4: 1.0, 5: 10.0, 6: 1000.0}
_DIM_OVERRIDE_NUM_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:[rRdDøØφΦ]\s*)?([0-9]+(?:[.,][0-9]+)?)\s*(mm|cm|m)?(?![A-Za-z0-9_])",
    re.IGNORECASE,
)


def _fail(code: str) -> None:
    raise MarineKnowledgeError(code)


def _opt_str(value: object, code: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value.strip():
        _fail(code)
    return value


def _scalar_val(value: object, code: str) -> float | str | None:
    if value is None:
        return None
    if type(value) is str:
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        fval = float(value)
        if not math.isfinite(fval):
            _fail(code)
        return fval
    _fail(code)
    return None  # pragma: no cover


def strip_mtext_formatting(raw_text: str) -> str:
    """Strip AutoCAD MTEXT inline control codes while preserving visible text."""
    if not raw_text:
        return ""
    cleaned = raw_text.replace(r"\P", " ").replace(r"\~", " ")
    cleaned = re.sub(r"%%[cC]", "Ø", cleaned)
    cleaned = re.sub(r"%%[dD]", "°", cleaned)
    cleaned = re.sub(r"%%[pP]", "±", cleaned)
    # Remove {\fFont|...;content} braces iteratively and inline control codes \C2; \H1.2x; \A1; etc.
    for _ in range(4):
        next_c = re.sub(r"\{([^{}]*)\}", r"\1", cleaned)
        if next_c == cleaned:
            break
        cleaned = next_c
    cleaned = re.sub(r"\\[fFHhWwQqAaCcTtOoLlKk][^;\\]*;", "", cleaned)
    cleaned = re.sub(r"\\[OoLlKk]", "", cleaned)
    return normalize_marine_cad_text(cleaned).strip()


def _fact_hash_body(record: Mapping[str, object]) -> dict[str, object]:
    return {
        k: deepcopy(v)
        for k, v in record.items()
        if k not in {"fact_id", "fact_sha256"}
    }


def validate_engineering_fact(payload: object) -> dict[str, Any]:
    """Validate an ``engineering-fact-1.0`` record fail-closed."""
    if not isinstance(payload, Mapping) or set(payload) != _FACT_FIELDS:
        _fail("FACT_SCHEMA_INVALID")
    data = deepcopy(dict(payload))
    if data["schema_version"] != ENGINEERING_FACT_SCHEMA_VERSION:
        _fail("FACT_SCHEMA_INVALID")
    domain = data["domain"]
    if type(domain) is not str or _DOMAIN_RE.fullmatch(domain) is None:
        _fail("FACT_DOMAIN_INVALID")
    drawing_id = data["drawing_id"]
    if type(drawing_id) is not str or not drawing_id.strip():
        _fail("FACT_DRAWING_ID_INVALID")
    _opt_str(data["drawing_path"], "FACT_DRAWING_PATH_INVALID")
    dsha = data["drawing_sha256"]
    if dsha is not None and (type(dsha) is not str or _SHA256_RE.fullmatch(dsha) is None):
        _fail("FACT_DRAWING_SHA_INVALID")
    _opt_str(data["sheet_id"], "FACT_SHEET_ID_INVALID")
    _opt_str(data["revision"], "FACT_REVISION_INVALID")
    fkey = data["fact_key"]
    if type(fkey) is not str or _KEY_RE.fullmatch(fkey) is None:
        _fail("FACT_KEY_INVALID")

    handles = data["entity_handles"]
    if not isinstance(handles, list) or any(type(h) is not str or not h.strip() for h in handles):
        _fail("FACT_HANDLES_INVALID")
    etype = data["entity_type"]
    if type(etype) is not str or not etype.strip():
        _fail("FACT_ENTITY_TYPE_INVALID")
    _opt_str(data["layer"], "FACT_LAYER_INVALID")
    if type(data["observed_raw"]) is not str:
        _fail("FACT_OBSERVED_RAW_INVALID")
    _scalar_val(data["observed_value"], "FACT_OBSERVED_VALUE_INVALID")
    _opt_str(data["observed_unit"], "FACT_OBSERVED_UNIT_INVALID")
    _scalar_val(data["normalized_value"], "FACT_NORMALIZED_VALUE_INVALID")
    _opt_str(data["normalized_unit"], "FACT_NORMALIZED_UNIT_INVALID")

    prov = data["provenance_class"]
    vstate = data["verification_state"]
    if prov not in PROVENANCE_CLASSES:
        _fail("FACT_PROVENANCE_INVALID")
    if vstate not in VERIFICATION_STATES:
        _fail("FACT_VERIFICATION_STATE_INVALID")
    if type(data["trust_reason"]) is not str or not data["trust_reason"].strip():
        _fail("FACT_TRUST_REASON_INVALID")

    # Enforce strict provenance <-> verification_state invariants
    if vstate == "VERIFIED":
        if prov not in {"NATIVE_CAD_EVIDENCE", "NATIVE_MEASURED_GEOMETRY"}:
            _fail("FACT_VERIFICATION_PROVENANCE_FORBIDDEN")
        if dsha is None or not handles or etype == "NONE":
            _fail("FACT_NATIVE_BINDING_MISSING")
    elif vstate == "PROVISIONAL_APPROXIMATE":
        if prov not in {"NATIVE_CAD_EVIDENCE", "FIXTURE_SUPPLIED"}:
            _fail("FACT_VERIFICATION_PROVENANCE_FORBIDDEN")
        if prov == "NATIVE_CAD_EVIDENCE" and (dsha is None or not handles or etype == "NONE"):
            _fail("FACT_NATIVE_BINDING_MISSING")
    elif prov in {"NATIVE_CAD_EVIDENCE", "NATIVE_MEASURED_GEOMETRY"}:
        if dsha is None or not handles or etype == "NONE":
            _fail("FACT_NATIVE_BINDING_MISSING")

    if prov == "OCR_ONLY" and vstate != "UNVERIFIED_OCR":
        _fail("FACT_VERIFICATION_PROVENANCE_FORBIDDEN")
    if prov == "NATIVE_CAD_UNBOUND_TEXT" and vstate != "UNVERIFIED_UNBOUND_TEXT":
        _fail("FACT_VERIFICATION_PROVENANCE_FORBIDDEN")
    if prov == "INFERRED_UNVERIFIED" and vstate != "UNVERIFIED_INFERRED":
        _fail("FACT_VERIFICATION_PROVENANCE_FORBIDDEN")
    if prov == "FIXTURE_SUPPLIED" and vstate not in {
        "FIXTURE_UNBOUND_TO_DXF_BYTES",
        "UNVERIFIED_UNITLESS",
        "PROVISIONAL_APPROXIMATE",
    }:
        _fail("FACT_VERIFICATION_PROVENANCE_FORBIDDEN")

    expected_sha = canonical_json_sha256(_fact_hash_body(data))
    if data["fact_sha256"] != expected_sha:
        _fail("FACT_HASH_MISMATCH")
    if data["fact_id"] != f"eng-fact-{expected_sha[:16]}":
        _fail("FACT_ID_MISMATCH")
    return data


def build_engineering_fact(
    *,
    domain: str = "marine",
    drawing_id: str,
    drawing_path: str | None = None,
    drawing_sha256: str | None = None,
    sheet_id: str | None = None,
    revision: str | None = None,
    fact_key: str,
    entity_handles: Sequence[str],
    entity_type: str,
    layer: str | None,
    observed_raw: str,
    observed_value: float | str | None,
    observed_unit: str | None,
    normalized_value: float | str | None,
    normalized_unit: str | None,
    provenance_class: str,
    verification_state: str,
    trust_reason: str,
) -> dict[str, Any]:
    """Construct and validate a canonical hash-bound ``engineering-fact-1.0`` record."""
    dedup_handles: list[str] = []
    for h in entity_handles:
        hs = str(h).strip()
        if hs and hs not in dedup_handles:
            dedup_handles.append(hs)
    body: dict[str, Any] = {
        "schema_version": ENGINEERING_FACT_SCHEMA_VERSION,
        "domain": domain,
        "drawing_id": drawing_id,
        "drawing_path": drawing_path,
        "drawing_sha256": drawing_sha256,
        "sheet_id": sheet_id,
        "revision": revision,
        "fact_key": fact_key,
        "entity_handles": dedup_handles,
        "entity_type": entity_type,
        "layer": layer,
        "observed_raw": observed_raw,
        "observed_value": float(observed_value) if isinstance(observed_value, int) and not isinstance(observed_value, bool) else observed_value,
        "observed_unit": observed_unit,
        "normalized_value": float(normalized_value) if isinstance(normalized_value, int) and not isinstance(normalized_value, bool) else normalized_value,
        "normalized_unit": normalized_unit,
        "provenance_class": provenance_class,
        "verification_state": verification_state,
        "trust_reason": trust_reason,
    }
    digest = canonical_json_sha256(body)
    body["fact_id"] = f"eng-fact-{digest[:16]}"
    body["fact_sha256"] = digest
    return validate_engineering_fact(body)


def evaluate_dimension_fact(
    dim_record: Mapping[str, Any],
    *,
    drawing_id: str,
    drawing_path: str | None,
    drawing_sha256: str | None,
    sheet_id: str | None,
    revision: str | None,
    insunits: int,
    calibration_verified: bool = False,
    verified_scale_to_mm: float | None = None,
    ocr_only: bool = False,
) -> dict[str, Any]:
    """Bind a native DXF DIMENSION entity to an EngineeringFact with override & unit checks."""
    if type(calibration_verified) is not bool:
        _fail("CALIBRATION_FLAG_INVALID")
    handle = str(dim_record.get("handle") or "").strip() or "UNKNOWN_DIM"
    layer = str(dim_record.get("layer") or "0").strip() or "0"
    raw_text = str(dim_record.get("raw_text") or "")
    visible_text = strip_mtext_formatting(raw_text)
    actual_raw = dim_record.get("actual_measurement")
    actual_meas = (
        float(actual_raw)
        if isinstance(actual_raw, (int, float))
        and not isinstance(actual_raw, bool)
        and math.isfinite(float(actual_raw))
        else None
    )

    if ocr_only:
        return build_engineering_fact(
            drawing_id=drawing_id,
            drawing_path=drawing_path,
            drawing_sha256=drawing_sha256,
            sheet_id=sheet_id,
            revision=revision,
            fact_key="dimension_measurement",
            entity_handles=[handle],
            entity_type="DIMENSION",
            layer=layer,
            observed_raw=visible_text or raw_text,
            observed_value=actual_meas,
            observed_unit="cad_units",
            normalized_value=None,
            normalized_unit=None,
            provenance_class="OCR_ONLY",
            verification_state="UNVERIFIED_OCR",
            trust_reason=f"Observation marked OCR_ONLY; DIMENSION {handle} cannot be treated as native CAD geometry.",
        )

    if actual_meas is None or actual_meas <= 0.0 or drawing_sha256 is None:
        return build_engineering_fact(
            drawing_id=drawing_id,
            drawing_path=drawing_path,
            drawing_sha256=drawing_sha256,
            sheet_id=sheet_id,
            revision=revision,
            fact_key="dimension_measurement",
            entity_handles=[handle] if handle else [],
            entity_type="DIMENSION",
            layer=layer,
            observed_raw=visible_text or raw_text,
            observed_value=actual_meas,
            observed_unit="cad_units" if actual_meas is not None else None,
            normalized_value=None,
            normalized_unit=None,
            provenance_class="INFERRED_UNVERIFIED",
            verification_state="UNVERIFIED_INFERRED",
            trust_reason=f"DIMENSION {handle} lacks positive finite actual_measurement or native DXF SHA-256.",
        )

    # Parse explicit manual text override (ignoring associative placeholder '<>')
    override_val: float | None = None
    override_unit: str | None = None
    cleaned_for_override = visible_text.replace("<>", "").strip()
    if cleaned_for_override:
        folded_ov = fold_marine_search_text(cleaned_for_override)
        m_ov = _DIM_OVERRIDE_NUM_RE.search(folded_ov)
        if m_ov:
            try:
                override_val = float(m_ov.group(1).replace(",", "."))
                override_unit = (m_ov.group(2) or "").lower().strip() or None
            except ValueError:
                override_val = None

    unit_factor_mm = _INSUNITS_TO_MM.get(insunits)
    if unit_factor_mm is None and calibration_verified and verified_scale_to_mm is not None and verified_scale_to_mm > 0:
        unit_factor_mm = float(verified_scale_to_mm)

    obs_raw_desc = (
        f"actual_measurement={actual_meas:.4f}; text={visible_text!r}"
        if visible_text
        else f"actual_measurement={actual_meas:.4f}"
    )

    if unit_factor_mm is not None:
        meas_mm = round(actual_meas * unit_factor_mm, 4)
        if override_val is not None and override_val > 0:
            if override_unit == "m":
                ov_mm = override_val * 1000.0
            elif override_unit == "cm":
                ov_mm = override_val * 10.0
            elif override_unit == "mm":
                ov_mm = override_val
            else:
                ov_mm = override_val * unit_factor_mm
            rel_err = abs(ov_mm - meas_mm) / max(meas_mm, 1e-6)
            abs_err = abs(ov_mm - meas_mm)
            if rel_err > 0.015 and abs_err > 2.0:
                return build_engineering_fact(
                    drawing_id=drawing_id,
                    drawing_path=drawing_path,
                    drawing_sha256=drawing_sha256,
                    sheet_id=sheet_id,
                    revision=revision,
                    fact_key="dimension_measurement",
                    entity_handles=[handle],
                    entity_type="DIMENSION",
                    layer=layer,
                    observed_raw=obs_raw_desc,
                    observed_value=round(actual_meas, 4),
                    observed_unit="cad_units",
                    normalized_value=None,
                    normalized_unit=None,
                    provenance_class="NATIVE_MEASURED_GEOMETRY",
                    verification_state="CONFLICTING_OVERRIDE",
                    trust_reason=(
                        f"DIMENSION {handle} on layer {layer} displays text override {visible_text!r} "
                        f"({ov_mm:.2f} mm) conflicting with measured geometry {meas_mm:.2f} mm "
                        f"(delta={abs_err:.2f} mm, {rel_err * 100.0:.2f}%)."
                    ),
                )
        return build_engineering_fact(
            drawing_id=drawing_id,
            drawing_path=drawing_path,
            drawing_sha256=drawing_sha256,
            sheet_id=sheet_id,
            revision=revision,
            fact_key="dimension_measurement",
            entity_handles=[handle],
            entity_type="DIMENSION",
            layer=layer,
            observed_raw=obs_raw_desc,
            observed_value=round(actual_meas, 4),
            observed_unit="mm" if insunits == 4 else "cad_units",
            normalized_value=meas_mm,
            normalized_unit="mm",
            provenance_class="NATIVE_MEASURED_GEOMETRY",
            verification_state="VERIFIED",
            trust_reason=(
                f"Calibrated native DIMENSION {handle} on layer {layer} "
                f"(unit_factor_mm={unit_factor_mm}, measured={meas_mm:.2f} mm)."
            ),
        )

    # Unitless ($INSUNITS=0 without verified calibration): check same-magnitude unitless override contradiction
    if (
        override_val is not None
        and override_val > 0
        and override_unit is None
        and 0.2 <= (override_val / actual_meas) <= 5.0
    ):
        rel_raw = abs(override_val - actual_meas) / max(actual_meas, 1e-6)
        abs_raw = abs(override_val - actual_meas)
        if rel_raw > 0.015 and abs_raw > 2.0:
            return build_engineering_fact(
                drawing_id=drawing_id,
                drawing_path=drawing_path,
                drawing_sha256=drawing_sha256,
                sheet_id=sheet_id,
                revision=revision,
                fact_key="dimension_measurement",
                entity_handles=[handle],
                entity_type="DIMENSION",
                layer=layer,
                observed_raw=obs_raw_desc,
                observed_value=round(actual_meas, 4),
                observed_unit="cad_units",
                normalized_value=None,
                normalized_unit=None,
                provenance_class="NATIVE_MEASURED_GEOMETRY",
                verification_state="CONFLICTING_OVERRIDE",
                trust_reason=(
                    f"DIMENSION {handle} on layer {layer} has unitless override {visible_text!r} "
                    f"({override_val:.2f}) conflicting with actual_measurement={actual_meas:.2f} "
                    f"({rel_raw * 100.0:.2f}% mismatch)."
                ),
            )

    return build_engineering_fact(
        drawing_id=drawing_id,
        drawing_path=drawing_path,
        drawing_sha256=drawing_sha256,
        sheet_id=sheet_id,
        revision=revision,
        fact_key="dimension_measurement",
        entity_handles=[handle],
        entity_type="DIMENSION",
        layer=layer,
        observed_raw=obs_raw_desc,
        observed_value=round(actual_meas, 4),
        observed_unit="cad_units",
        normalized_value=None,
        normalized_unit=None,
        provenance_class="NATIVE_MEASURED_GEOMETRY",
        verification_state="UNVERIFIED_UNITLESS",
        trust_reason=(
            f"DIMENSION {handle} on layer {layer} measured {actual_meas:.2f} CAD units in unitless drawing "
            f"($INSUNITS={insunits}) without verified calibration; physical unit unproven."
        ),
    )


def rebind_observation_dimensions(
    obs: Mapping[str, Any],
    *,
    calibration_verified: bool = False,
    verified_scale_to_mm: float | None = None,
) -> dict[str, Any]:
    """Return a deep copy of a normalized observation with validated facts and rebound DIMENSIONs."""
    if type(calibration_verified) is not bool:
        _fail("CALIBRATION_FLAG_INVALID")
    out = deepcopy(dict(obs))
    raw_facts = out.get("engineering_facts", [])
    if not isinstance(raw_facts, list):
        _fail("FACT_SCHEMA_INVALID")
    validated_existing = [validate_engineering_fact(f) for f in raw_facts]
    raw_dims = out.get("dimensions", [])
    ev = out.get("drawing_evidence") or {}
    if not raw_dims:
        out["engineering_facts"] = validated_existing
        return out
    non_dim_facts = [
        f for f in validated_existing if f.get("entity_type") != "DIMENSION"
    ]
    dim_facts = [
        evaluate_dimension_fact(
            d,
            drawing_id=str(out["drawing_id"]),
            drawing_path=ev.get("drawing_path"),
            drawing_sha256=ev.get("drawing_sha256"),
            sheet_id=ev.get("sheet_id"),
            revision=ev.get("revision"),
            insunits=int(out.get("insunits", 0)),
            calibration_verified=calibration_verified,
            verified_scale_to_mm=verified_scale_to_mm,
            ocr_only=bool(out.get("ocr_only", False)),
        )
        for d in raw_dims
    ]
    out["engineering_facts"] = non_dim_facts + dim_facts
    if isinstance(out.get("drawing_evidence"), dict):
        out["drawing_evidence"]["calibration_verified"] = bool(
            calibration_verified and verified_scale_to_mm is not None and verified_scale_to_mm > 0
        )
    return out


def explain_fact_traceability(fact: Mapping[str, object]) -> dict[str, Any]:
    """Produce an audit-grade explanation of a fact's source drawing, CAD entity, and trustworthiness."""
    valid = validate_engineering_fact(fact)
    sufficient = valid["verification_state"] == "VERIFIED"
    sha_short = valid["drawing_sha256"][:12] if valid["drawing_sha256"] else "UNBOUND_NO_SHA256"
    handles_txt = ", ".join(valid["entity_handles"]) if valid["entity_handles"] else "NONE"
    status_word = "SUFFICIENT (VERIFIED)" if sufficient else f"NOT SUFFICIENT ({valid['verification_state']})"
    explanation = (
        f"[{status_word}] Fact '{valid['fact_key']}' on drawing '{valid['drawing_id']}' "
        f"(sha256={sha_short}, sheet={valid['sheet_id']}, rev={valid['revision']}) "
        f"from {valid['entity_type']} handle(s) [{handles_txt}] on layer {valid['layer']!r} "
        f"({valid['provenance_class']}): observed={valid['observed_raw']!r} -> "
        f"normalized={valid['normalized_value']} {valid['normalized_unit'] or ''}. "
        f"Reason: {valid['trust_reason']}"
    ).strip()
    return {
        "fact_id": valid["fact_id"],
        "fact_sha256": valid["fact_sha256"],
        "domain": valid["domain"],
        "fact_key": valid["fact_key"],
        "drawing_id": valid["drawing_id"],
        "drawing_path": valid["drawing_path"],
        "drawing_sha256": valid["drawing_sha256"],
        "sheet_id": valid["sheet_id"],
        "revision": valid["revision"],
        "entity_handles": valid["entity_handles"],
        "entity_type": valid["entity_type"],
        "layer": valid["layer"],
        "observed_raw": valid["observed_raw"],
        "observed_value": valid["observed_value"],
        "observed_unit": valid["observed_unit"],
        "normalized_value": valid["normalized_value"],
        "normalized_unit": valid["normalized_unit"],
        "provenance_class": valid["provenance_class"],
        "verification_state": valid["verification_state"],
        "sufficient_for_verified_check": sufficient,
        "explanation": explanation,
    }


__all__ = [
    "ENGINEERING_FACT_SCHEMA_VERSION",
    "PROVENANCE_CLASSES",
    "VERIFICATION_STATES",
    "build_engineering_fact",
    "evaluate_dimension_fact",
    "explain_fact_traceability",
    "rebind_observation_dimensions",
    "strip_mtext_formatting",
    "validate_engineering_fact",
]
