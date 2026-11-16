"""Fail-closed dimension override, colocation conflict, and unit calibration gate."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .visual_contracts import validate_visual_contract

_INSUNITS_TO_MM: dict[int, float] = {
    1: 25.4,
    2: 304.8,
    4: 1.0,
    5: 10.0,
    6: 1000.0,
}

_NUMBER_RE = re.compile(r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_REF_PARENS_RE = re.compile(r"^\s*\([^)]*\)\s*$")
_REF_TOKEN_RE = re.compile(r"\b(?:REF|REFERENCE)\b|THAM\s+KH[AẢ]O|[~≈]", re.IGNORECASE)
_UNRESOLVED_STATUSES = frozenset({"UNRESOLVED", "CONFLICT"})
_SAFE_ID_CHAR_RE = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class DimensionInput:
    """Single observed dimension candidate paired with its measured CAD geometry."""

    dimension_id: str
    raw_text: str
    measured_geometry_value: float | None
    center_xy: tuple[float, float]
    orientation_deg: float | None = None
    kind: str = "HORIZONTAL_DISTANCE"
    critical: bool = True
    from_ref: Mapping[str, str] | None = None
    to_ref: Mapping[str, str] | None = None
    crop_id: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    crop_sha256: str = "0" * 64
    blocker_scope: tuple[str, ...] = ()
    text_confidence: float = 0.99
    attachment_confidence: float = 0.95


@dataclass(frozen=True)
class EvaluatedDimension:
    """Gate disposition aligned with `dimension-register-1.0` roles and statuses."""

    dimension_id: str
    display_text: str
    parsed_override_value: float | None
    calibrated_measured_mm: float | None
    unit: str | None
    role: str
    status: str
    reason_code: str
    is_reference: bool
    override_diff_mm: float | None
    conflicting_with: tuple[str, ...] = ()
    redundant_of: str | None = None


def is_reference_dimension_text(text: str) -> bool:
    """Return True when display text explicitly marks a non-driving reference dimension."""
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_REF_PARENS_RE.match(cleaned) or _REF_TOKEN_RE.search(cleaned))


def parse_dimension_numeric_value(text: str) -> float | None:
    """Extract the primary numeric measurement from dimension override text, if present."""
    cleaned = text.strip()
    if not cleaned or "<>" in cleaned:
        return None
    normalized = cleaned.replace("%%c", "").replace("%%C", "")
    match = _NUMBER_RE.search(normalized)
    if match is None:
        return None
    try:
        value = float(match.group(0).replace(",", ""))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _resolve_scale_to_mm(insunits: int, verified_scale_to_mm: float | None) -> float | None:
    if verified_scale_to_mm is not None:
        if isinstance(verified_scale_to_mm, bool) or not isinstance(verified_scale_to_mm, (int, float)):
            raise ValueError("verified_scale_to_mm must be numeric when provided")
        scale = float(verified_scale_to_mm)
        if not math.isfinite(scale) or scale <= 0.0:
            raise ValueError("verified_scale_to_mm must be finite and positive")
        return scale
    return _INSUNITS_TO_MM.get(insunits)


def _are_orientations_compatible(deg_a: float | None, deg_b: float | None, tol_deg: float = 15.0) -> bool:
    if deg_a is None or deg_b is None:
        return True
    diff = abs((deg_a - deg_b) % 180.0)
    if diff > 90.0:
        diff = 180.0 - diff
    return diff <= tol_deg


def _effective_numeric_value(item: EvaluatedDimension) -> float | None:
    if item.parsed_override_value is not None:
        return item.parsed_override_value
    return item.calibrated_measured_mm


def _classify_single_dimension(
    dim: DimensionInput,
    *,
    scale_to_mm: float | None,
    abs_tol_mm: float,
    rel_tol: float,
    require_attachments_for_driving: bool,
) -> EvaluatedDimension:
    text = dim.raw_text.strip()
    is_ref = is_reference_dimension_text(text)
    parsed = parse_dimension_numeric_value(text)

    if scale_to_mm is None:
        return EvaluatedDimension(
            dimension_id=dim.dimension_id,
            display_text=text,
            parsed_override_value=parsed,
            calibrated_measured_mm=None,
            unit=None,
            role="AMBIGUOUS",
            status="UNRESOLVED",
            reason_code="UNITLESS_UNCALIBRATED",
            is_reference=is_ref,
            override_diff_mm=None,
        )

    measured_mm: float | None = None
    if (
        dim.measured_geometry_value is not None
        and not isinstance(dim.measured_geometry_value, bool)
        and math.isfinite(float(dim.measured_geometry_value))
    ):
        measured_mm = float(dim.measured_geometry_value) * scale_to_mm

    override_diff: float | None = None
    if parsed is not None and measured_mm is not None:
        override_diff = abs(parsed - measured_mm)
        threshold = max(abs_tol_mm, rel_tol * max(abs(measured_mm), abs(parsed), 1e-9))
        if not is_ref and override_diff > threshold:
            return EvaluatedDimension(
                dimension_id=dim.dimension_id,
                display_text=text or f"{parsed:.6g}",
                parsed_override_value=parsed,
                calibrated_measured_mm=measured_mm,
                unit="mm",
                role="CONFLICT",
                status="CONFLICT",
                reason_code="DIMENSION_OVERRIDE_CONFLICT",
                is_reference=False,
                override_diff_mm=override_diff,
            )

    if is_ref:
        value = parsed if parsed is not None else measured_mm
        if value is None:
            return EvaluatedDimension(
                dimension_id=dim.dimension_id,
                display_text=text,
                parsed_override_value=None,
                calibrated_measured_mm=measured_mm,
                unit=None,
                role="AMBIGUOUS",
                status="UNRESOLVED",
                reason_code="NON_NUMERIC_OR_EMPTY_TEXT",
                is_reference=True,
                override_diff_mm=override_diff,
            )
        return EvaluatedDimension(
            dimension_id=dim.dimension_id,
            display_text=text,
            parsed_override_value=parsed,
            calibrated_measured_mm=measured_mm,
            unit="mm",
            role="REFERENCE",
            status="CONFIRMED",
            reason_code="REFERENCE_DIMENSION",
            is_reference=True,
            override_diff_mm=override_diff,
        )

    effective_val = parsed if parsed is not None else measured_mm
    if effective_val is None:
        return EvaluatedDimension(
            dimension_id=dim.dimension_id,
            display_text=text,
            parsed_override_value=parsed,
            calibrated_measured_mm=measured_mm,
            unit=None,
            role="AMBIGUOUS",
            status="UNRESOLVED",
            reason_code="NON_NUMERIC_OR_EMPTY_TEXT",
            is_reference=False,
            override_diff_mm=override_diff,
        )

    display = text if text and text != "<>" else f"{effective_val:.6g}"
    if require_attachments_for_driving and (dim.from_ref is None or dim.to_ref is None):
        return EvaluatedDimension(
            dimension_id=dim.dimension_id,
            display_text=display,
            parsed_override_value=parsed,
            calibrated_measured_mm=measured_mm,
            unit="mm",
            role="AMBIGUOUS",
            status="UNRESOLVED",
            reason_code="MISSING_ATTACHMENT_REFS",
            is_reference=False,
            override_diff_mm=override_diff,
        )

    return EvaluatedDimension(
        dimension_id=dim.dimension_id,
        display_text=display,
        parsed_override_value=parsed,
        calibrated_measured_mm=measured_mm,
        unit="mm",
        role="DRIVING",
        status="CONFIRMED",
        reason_code="CONFIRMED_DRIVING",
        is_reference=False,
        override_diff_mm=override_diff,
    )


def evaluate_dimension_gate(
    dimensions: Sequence[DimensionInput],
    *,
    insunits: int = 4,
    verified_scale_to_mm: float | None = None,
    abs_tol_mm: float = 2.0,
    rel_tol: float = 0.02,
    conflict_radius_mm: float = 800.0,
    derived_radius_mm: float = 2500.0,
    derived_rel_tol: float = 0.01,
    require_attachments_for_driving: bool = True,
) -> tuple[EvaluatedDimension, ...]:
    """Evaluate unit calibration, override mismatches, colocation conflicts, and duplicates."""
    scale_to_mm = _resolve_scale_to_mm(insunits, verified_scale_to_mm)
    results = [
        _classify_single_dimension(
            dim,
            scale_to_mm=scale_to_mm,
            abs_tol_mm=abs_tol_mm,
            rel_tol=rel_tol,
            require_attachments_for_driving=require_attachments_for_driving,
        )
        for dim in dimensions
    ]
    if scale_to_mm is None:
        return tuple(results)

    conflict_peers: dict[int, list[str]] = {idx: [] for idx in range(len(results))}
    for i in range(len(results)):
        res_i = results[i]
        val_i = _effective_numeric_value(res_i)
        if res_i.is_reference or res_i.status != "CONFIRMED" or val_i is None:
            continue
        cx_i, cy_i = dimensions[i].center_xy
        for j in range(i + 1, len(results)):
            res_j = results[j]
            val_j = _effective_numeric_value(res_j)
            if res_j.is_reference or res_j.status != "CONFIRMED" or val_j is None:
                continue
            if not _are_orientations_compatible(dimensions[i].orientation_deg, dimensions[j].orientation_deg):
                continue
            cx_j, cy_j = dimensions[j].center_xy
            dist_mm = math.hypot((cx_i - cx_j) * scale_to_mm, (cy_i - cy_j) * scale_to_mm)
            if dist_mm > conflict_radius_mm:
                continue
            limit = max(abs_tol_mm, rel_tol * max(abs(val_i), abs(val_j), 1e-9))
            if abs(val_i - val_j) > limit:
                conflict_peers[i].append(res_j.dimension_id)
                conflict_peers[j].append(res_i.dimension_id)

    for idx, peers in conflict_peers.items():
        if not peers:
            continue
        cur = results[idx]
        results[idx] = EvaluatedDimension(
            dimension_id=cur.dimension_id,
            display_text=cur.display_text,
            parsed_override_value=cur.parsed_override_value,
            calibrated_measured_mm=cur.calibrated_measured_mm,
            unit=cur.unit,
            role="CONFLICT",
            status="CONFLICT",
            reason_code="COLOCATED_DIMENSION_CONFLICT",
            is_reference=cur.is_reference,
            override_diff_mm=cur.override_diff_mm,
            conflicting_with=tuple(sorted(set(peers))),
        )

    for i in range(len(results)):
        res_i = results[i]
        val_i = _effective_numeric_value(res_i)
        if res_i.role != "DRIVING" or res_i.status != "CONFIRMED" or val_i is None:
            continue
        cx_i, cy_i = dimensions[i].center_xy
        for j in range(i + 1, len(results)):
            res_j = results[j]
            val_j = _effective_numeric_value(res_j)
            if res_j.role != "DRIVING" or res_j.status != "CONFIRMED" or val_j is None:
                continue
            if not _are_orientations_compatible(dimensions[i].orientation_deg, dimensions[j].orientation_deg):
                continue
            cx_j, cy_j = dimensions[j].center_xy
            dist_mm = math.hypot((cx_i - cx_j) * scale_to_mm, (cy_i - cy_j) * scale_to_mm)
            if dist_mm > derived_radius_mm:
                continue
            limit = max(abs_tol_mm, derived_rel_tol * max(abs(val_i), abs(val_j), 1e-9))
            if abs(val_i - val_j) <= limit:
                results[j] = EvaluatedDimension(
                    dimension_id=res_j.dimension_id,
                    display_text=res_j.display_text,
                    parsed_override_value=res_j.parsed_override_value,
                    calibrated_measured_mm=res_j.calibrated_measured_mm,
                    unit=res_j.unit,
                    role="DERIVED",
                    status="CONFIRMED",
                    reason_code="COLOCATED_REDUNDANT_DERIVED",
                    is_reference=res_j.is_reference,
                    override_diff_mm=res_j.override_diff_mm,
                    redundant_of=res_i.dimension_id,
                )

    return tuple(results)


def build_dimension_register(
    evaluations: Sequence[EvaluatedDimension],
    dimensions: Sequence[DimensionInput],
    *,
    run_id: str,
    source_sha256: str,
    page_id: str,
    view_id: str,
    default_region_id: str = "GLOBAL-REGION",
) -> dict[str, Any]:
    """Serialize evaluated dimensions into a validated `dimension-register-1.0` contract."""
    if len(evaluations) != len(dimensions):
        raise ValueError("evaluations and dimensions must have the same length")

    entries: list[dict[str, Any]] = []
    confirmed_count = 0
    unresolved_count = 0
    conflict_count = 0

    for evaluated, dim_in in zip(evaluations, dimensions):
        if evaluated.dimension_id != dim_in.dimension_id:
            raise ValueError("evaluations and dimensions order/IDs must match")

        if evaluated.status == "CONFIRMED":
            confirmed_count += 1
            blocker_scope: list[str] = list(dim_in.blocker_scope)
            reg_value: float | None = _effective_numeric_value(evaluated)
        elif evaluated.status == "UNRESOLVED":
            unresolved_count += 1
            blocker_scope = list(dim_in.blocker_scope) or (
                [default_region_id] if dim_in.critical else []
            )
            reg_value = None if evaluated.reason_code == "UNITLESS_UNCALIBRATED" else _effective_numeric_value(evaluated)
        else:
            conflict_count += 1
            blocker_scope = list(dim_in.blocker_scope) or (
                [default_region_id] if dim_in.critical else []
            )
            reg_value = _effective_numeric_value(evaluated)

        cx, cy = dim_in.center_xy
        bbox = list(dim_in.bbox) if dim_in.bbox is not None else [cx - 10.0, cy - 10.0, cx + 10.0, cy + 10.0]
        raw_crop_id = dim_in.crop_id or f"CROP-{_SAFE_ID_CHAR_RE.sub('-', evaluated.dimension_id)}"

        entry: dict[str, Any] = {
            "id": evaluated.dimension_id,
            "display_text": evaluated.display_text,
            "value": reg_value,
            "unit": evaluated.unit,
            "kind": dim_in.kind,
            "role": evaluated.role,
            "status": evaluated.status,
            "critical": dim_in.critical,
            "source_evidence": {
                "crop_id": raw_crop_id,
                "bbox": bbox,
                "crop_sha256": dim_in.crop_sha256,
            },
            "text_confidence": dim_in.text_confidence,
            "attachment_confidence": dim_in.attachment_confidence,
            "blocker_scope": blocker_scope,
        }
        if dim_in.from_ref is not None:
            entry["from_ref"] = dict(dim_in.from_ref)
        if dim_in.to_ref is not None:
            entry["to_ref"] = dict(dim_in.to_ref)
        entries.append(entry)

    payload: dict[str, Any] = {
        "schema_version": "dimension-register-1.0",
        "run_id": run_id,
        "source_sha256": source_sha256,
        "page_id": page_id,
        "view_id": view_id,
        "coverage": {
            "clusters_detected": len(entries),
            "clusters_processed": len(entries),
            "page_coverage_percent": 100.0,
        },
        "summary": {
            "confirmed": confirmed_count,
            "unresolved": unresolved_count,
            "conflicts": conflict_count,
        },
        "dimensions": entries,
    }
    return validate_visual_contract(payload, contract="dimension_register")


__all__ = [
    "DimensionInput",
    "EvaluatedDimension",
    "build_dimension_register",
    "evaluate_dimension_gate",
    "is_reference_dimension_text",
    "parse_dimension_numeric_value",
]
