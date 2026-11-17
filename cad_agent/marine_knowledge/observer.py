"""Read-only marine CAD and structural observation extractor.

Reuses ``dxf_builder_lib._dxf_snapshot.read_dxf_snapshot`` for raw DXF reading
without importing ``ezdxf`` directly outside ``dxf_builder_lib/``, preserving
existing architecture boundaries.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math
from pathlib import Path
import re
from typing import Any

from dxf_builder_lib._dxf_snapshot import read_dxf_snapshot

from .text_normalization import fold_marine_search_text, normalize_marine_cad_text

_KNOWN_BLANK_FIELD_LABELS = (
    "PORT OF REGISTRY",
    "GROSS TONNAGE",
    "NET TONNAGE",
    "MAX. OUTPUT",
    "NOR. OUTPUT",
    "DEADWEIGHT",
    "CLASSIFICATION",
    "SERVICE AREA",
    "OWNER",
    "SHIPYARD",
    "HULL NO",
)

_LPP_RE = re.compile(
    r"\b(?:lpp|l\.p\.p|ltk|chieu\s+dai\s+thiet\s+ke|length\s*\(?l\.?p\.?p\)?|"
    r"chieu\s+dai\s+giua\s+2\s+tru)\b\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)\s*(mm|m)?\b"
)
_BREADTH_RE = re.compile(
    r"(?:^|\b)(?:breadth(?:\s*\(?b\)?)?|chieu\s+rong(?:\s*\(?b\)?)?|b)\s*[:=]\s*"
    r"([0-9]+(?:[.,][0-9]+)?)\s*(mm|m)?\b"
)
_DEPTH_RE = re.compile(
    r"(?:^|\b)(?:depth(?:\s*\(?d\)?)?|chieu\s+cao\s+man(?:\s*\(?d\)?)?|d)\s*[:=]\s*"
    r"([0-9]+(?:[.,][0-9]+)?)\s*(mm|m)?\b"
)
_DRAFT_RE = re.compile(
    r"(?:^|\b)(?:draught|draft|chieu\s+chim(?:\s*\(?t\)?)?|mon\s+nuoc)\s*[:=]?\s*"
    r"([0-9]+(?:[.,][0-9]+)?)\s*(mm|m)?\b|(?:^|\b)T\s*[:=]\s*([0-9]+(?:[.,][0-9]+)?)\s*(mm|m)\b"
)
_ENGINE_RE = re.compile(r"(?:main\s*engine|may\s*chinh)\s*[:=]?\s*(.+)$", re.IGNORECASE)
_SCALE_RE = re.compile(r"\b(?:ty\s+le|scale)\s*[:=]?\s*1\s*[:/]\s*([0-9]+(?:[.,][0-9]+)?)\b")
_PLATE_THICK_RE = re.compile(r"\b(?:s|t)\s*=\s*([0-9]+(?:[.,][0-9]+)?)\b")
_CLASS_NOTATION_RE = re.compile(r"\bvr\s*-?\s*(sb|si|sii|siii)\b")
_EXPLICIT_CAP_RE = re.compile(r"\bcap\s+tau\s*[:=]\s*(?:vr\s*-?\s*)?(sb|si|sii|siii)\b")
_SHIP_TYPE_RE = re.compile(
    r"\b(?:ship\s+type|loai\s+tau)\s*[:=]\s*([a-z0-9\s\-/]+?)$"
)
_CODE_TOKEN_RE = re.compile(
    r"\b(?:GA|THLT|KCCB|MCN|KC|SF)\s*[-_]?\s*\d{2}(?:\s*[-_]\s*\d{2})?\b",
    re.IGNORECASE,
)
_TRAILING_EMPTY_COLON_RE = re.compile(r"^([A-Za-zÀ-ỹ0-9\s./()-]{3,48}?)\s*[:=]\s*[-–—_?.]*$")
_AP_ONLY_RE = re.compile(r"^(?:a\.?p\.?|vuong\s+goc\s+lai|aft\s+perpendicular)$")
_FP_ONLY_RE = re.compile(r"^(?:f\.?p\.?|vuong\s+goc\s+mui|forward\s+perpendicular)$")

_MAX_BLOCK_TEXT_ITEMS = 250


def _to_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        out = float(value)
        return out if math.isfinite(out) else None
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        try:
            out = float(cleaned)
        except ValueError:
            return None
        return out if math.isfinite(out) else None
    return None


def _unit_value_to_meters(raw_num: str, unit: str | None) -> float | None:
    val = _to_float(raw_num)
    if val is None or val <= 0:
        return None
    unit_norm = (unit or "").lower().strip()
    if unit_norm == "mm" or (not unit_norm and val > 350.0):
        return round(val / 1000.0, 4)
    return round(val, 4)


def _extract_style_font_hints(doc: Any) -> dict[str, str]:
    hints: dict[str, str] = {}
    for style in getattr(doc, "styles", ()):
        name = str(getattr(style.dxf, "name", "") or "")
        if not name:
            continue
        font = str(getattr(style.dxf, "font", "") or "")
        hint = font
        has_xdata = getattr(style, "has_xdata", None)
        if callable(has_xdata) and has_xdata("ACAD"):
            for code, val in style.get_xdata("ACAD"):
                if code == 1000 and isinstance(val, str):
                    lower = val.lower()
                    if lower.startswith(".vn") or "tcvn" in lower:
                        hint = val
                        break
        hints[name] = hint
    return hints


def _entity_text_payload(entity: Any, style_fonts: Mapping[str, str], *, dx: float = 0.0, dy: float = 0.0) -> dict[str, Any] | None:
    dxftype = entity.dxftype()
    if dxftype == "MTEXT":
        raw_text = entity.plain_text() if hasattr(entity, "plain_text") else str(getattr(entity.dxf, "text", "") or "")
        height = _to_float(getattr(entity.dxf, "char_height", None)) or 0.0
    elif dxftype in {"TEXT", "ATTRIB"}:
        raw_text = str(getattr(entity.dxf, "text", "") or "")
        height = _to_float(getattr(entity.dxf, "height", None)) or 0.0
    else:
        return None
    if not raw_text.strip():
        return None
    style_name = str(getattr(entity.dxf, "style", "") or "")
    font_hint = style_fonts.get(style_name, "")
    insert = getattr(entity.dxf, "insert", None)
    x = (_to_float(getattr(insert, "x", None)) or 0.0) + dx
    y = (_to_float(getattr(insert, "y", None)) or 0.0) + dy
    return {
        "handle": str(getattr(entity.dxf, "handle", "") or ""),
        "text": normalize_marine_cad_text(raw_text, font_hint=font_hint),
        "raw_text": raw_text,
        "font_hint": font_hint,
        "layer": str(getattr(entity.dxf, "layer", "0") or "0"),
        "x": round(x, 3),
        "y": round(y, 3),
        "height": round(height, 4),
    }


def _collect_dxf_texts(doc: Any, style_fonts: Mapping[str, str]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    texts: list[dict[str, Any]] = []
    entity_counts: dict[str, int] = {}
    referenced_blocks: dict[str, tuple[float, float]] = {}

    msp = doc.modelspace()
    for entity in msp:
        dxftype = entity.dxftype()
        entity_counts[dxftype] = entity_counts.get(dxftype, 0) + 1
        item = _entity_text_payload(entity, style_fonts)
        if item is not None:
            texts.append(item)
            continue
        if dxftype == "INSERT":
            for attrib in getattr(entity, "attribs", ()):
                attr_item = _entity_text_payload(attrib, style_fonts)
                if attr_item is not None:
                    texts.append(attr_item)
            block_name = str(getattr(entity.dxf, "name", "") or "")
            if block_name and block_name not in referenced_blocks and not block_name.startswith("*"):
                ins = getattr(entity.dxf, "insert", None)
                bx = _to_float(getattr(ins, "x", None)) or 0.0
                by = _to_float(getattr(ins, "y", None)) or 0.0
                referenced_blocks[block_name] = (bx, by)

    for block_name, (bx, by) in referenced_blocks.items():
        if block_name not in doc.blocks:
            continue
        block = doc.blocks.get(block_name)
        block_items: list[dict[str, Any]] = []
        for entity in block:
            item = _entity_text_payload(entity, style_fonts, dx=bx, dy=by)
            if item is not None:
                block_items.append(item)
            if len(block_items) > _MAX_BLOCK_TEXT_ITEMS:
                block_items.clear()
                break
        texts.extend(block_items)

    return texts, entity_counts


def observe_dxf_bytes(
    data: bytes,
    *,
    drawing_id: str,
    drawing_code: str = "",
    claimed_scale: float | None = None,
    ocr_only: bool = False,
) -> dict[str, Any]:
    """Read raw DXF bytes via ``dxf_builder_lib._dxf_snapshot`` into normalized observation."""
    doc, _styles = read_dxf_snapshot(data, observe_styles=True)
    style_fonts = _extract_style_font_hints(doc)
    texts, entity_counts = _collect_dxf_texts(doc, style_fonts)

    insunits_raw = doc.header.get("$INSUNITS", 0)
    measurement_raw = doc.header.get("$MEASUREMENT", 0)
    insunits = int(insunits_raw) if isinstance(insunits_raw, (int, float)) else 0
    measurement = int(measurement_raw) if isinstance(measurement_raw, (int, float)) else 0

    return normalize_observation(
        {
            "drawing_id": drawing_id,
            "drawing_code": drawing_code,
            "insunits": insunits,
            "measurement": measurement,
            "claimed_scale": claimed_scale,
            "ocr_only": bool(ocr_only),
            "source_mode": "OCR_ONLY" if ocr_only else "NATIVE_DXF_SNAPSHOT",
            "entity_counts": entity_counts,
            "texts": texts,
        }
    )


def observe_dxf_file(
    path: str | Path,
    *,
    drawing_id: str | None = None,
    drawing_code: str = "",
    claimed_scale: float | None = None,
    ocr_only: bool = False,
) -> dict[str, Any]:
    """Read an on-disk DXF file in strict read-only mode using ``observe_dxf_bytes``."""
    target = Path(path)
    return observe_dxf_bytes(
        target.read_bytes(),
        drawing_id=drawing_id or target.stem,
        drawing_code=drawing_code,
        claimed_scale=claimed_scale,
        ocr_only=ocr_only,
    )


def _normalize_text_entries(raw_texts: object) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not isinstance(raw_texts, list):
        return entries
    for idx, item in enumerate(raw_texts):
        if not isinstance(item, Mapping):
            continue
        raw_str = str(item.get("raw_text", item.get("text", "")) or "")
        font_hint = str(item.get("font_hint", "") or "")
        if "raw_text" in item and item.get("text") is not None:
            norm_text = str(item.get("text") or "").strip()
        else:
            norm_text = normalize_marine_cad_text(str(item.get("text", raw_str) or ""), font_hint=font_hint)
        if not norm_text:
            continue
        folded = fold_marine_search_text(norm_text, font_hint="")
        entries.append(
            {
                "handle": str(item.get("handle", f"T{idx + 1}")),
                "raw_text": raw_str,
                "text": norm_text,
                "folded": folded,
                "font_hint": font_hint,
                "layer": str(item.get("layer", "0") or "0"),
                "x": _to_float(item.get("x")),
                "y": _to_float(item.get("y")),
                "height": _to_float(item.get("height")),
            }
        )
    return entries


def _has_neighbor_value(label_entry: Mapping[str, Any], entries: list[dict[str, Any]]) -> bool:
    lx = label_entry.get("x")
    ly = label_entry.get("y")
    if lx is None or ly is None:
        return False
    h = label_entry.get("height") or 200.0
    max_dx = max(h * 60.0, 22000.0)
    max_dy_row = max(h * 1.8, 350.0)
    max_dy_below = max(h * 3.0, 600.0)
    for other in entries:
        if other is label_entry:
            continue
        ox = other.get("x")
        oy = other.get("y")
        if ox is None or oy is None:
            continue
        upper_folded = other["folded"].upper()
        if any(lbl in upper_folded for lbl in _KNOWN_BLANK_FIELD_LABELS):
            continue
        if _TRAILING_EMPTY_COLON_RE.fullmatch(other["text"].strip()):
            continue
        if ":" in other["text"] and _ENGINE_RE.search(other["text"]) is None:
            key_part = other["text"].split(":", 1)[0].strip().upper()
            if len(key_part.split()) <= 4:
                continue
        dx = ox - lx
        dy = ly - oy
        same_row_right = 0.0 < dx <= max_dx and abs(dy) <= max_dy_row
        directly_below = abs(dx) <= max(h * 8.0, 1500.0) and 0.0 < dy <= max_dy_below
        if same_row_right or directly_below:
            return True
    return False


def _nearest_right_numeric(label_entry: Mapping[str, Any], entries: list[dict[str, Any]]) -> float | None:
    lx = label_entry.get("x")
    ly = label_entry.get("y")
    if lx is None or ly is None:
        return None
    h = label_entry.get("height") or 200.0
    candidates: list[tuple[float, float]] = []
    for other in entries:
        if other is label_entry:
            continue
        ox = other.get("x")
        oy = other.get("y")
        if ox is None or oy is None:
            continue
        dx = ox - lx
        if dx <= 0.0 or dx > max(h * 70.0, 30000.0):
            continue
        if abs(oy - ly) > max(h * 1.6, 350.0):
            continue
        m = re.fullmatch(r"\s*([0-9]+(?:[.,][0-9]+)?)\s*(mm|m)?\s*", other["folded"])
        if m:
            val = _unit_value_to_meters(m.group(1), m.group(2))
            if val is not None:
                candidates.append((dx, val))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    return candidates[0][1]


def _detect_blank_fields(entries: list[dict[str, Any]], explicit: object) -> list[str]:
    blanks: list[str] = []
    if isinstance(explicit, list):
        for item in explicit:
            text = str(item or "").strip()
            if text and text not in blanks:
                blanks.append(text)
    for entry in entries:
        text = entry["text"].strip()
        upper_folded = re.sub(r"\s+", " ", entry["folded"].upper()).strip(" :=")
        match_colon = _TRAILING_EMPTY_COLON_RE.fullmatch(text)
        if match_colon:
            label = normalize_marine_cad_text(match_colon.group(1)).strip().upper()
            if not _has_neighbor_value(entry, entries) and label not in blanks:
                blanks.append(label)
            continue
        if upper_folded in _KNOWN_BLANK_FIELD_LABELS:
            if not _has_neighbor_value(entry, entries) and upper_folded not in blanks:
                blanks.append(upper_folded)
            continue
        for prefix in ("GROSS TONNAGE", "NET TONNAGE", "MAX. OUTPUT", "NOR. OUTPUT"):
            if upper_folded.startswith(prefix) and not re.search(
                r"\d", re.sub(r"I\.C\.T\.M\.?\s*1969|85%\s*MCR", "", upper_folded)
            ):
                if not _has_neighbor_value(entry, entries) and prefix not in blanks:
                    blanks.append(prefix)
                break
    return blanks


def _append_unique(items: list[Any], value: Any) -> None:
    if value not in items:
        items.append(value)


def _extract_particulars(entries: list[dict[str, Any]], raw: Mapping[str, Any]) -> dict[str, Any]:
    lpp_values: list[float] = []
    breadth_values: list[float] = []
    depth_values: list[float] = []
    draft_values: list[float] = []
    main_engines: list[str] = []
    class_notations: list[str] = []
    service_areas: list[str] = []
    explicit_exclusion_evidences: list[str] = []
    ship_types: list[str] = []
    claimed_scales: list[float] = []
    ap_coords: list[float] = []
    fp_coords: list[float] = []
    extracted_plate_mm: list[float] = []

    raw_scale = _to_float(raw.get("claimed_scale"))
    if raw_scale is not None and raw_scale > 0:
        _append_unique(claimed_scales, round(raw_scale, 3))

    for entry in entries:
        text = entry["text"]
        folded = entry["folded"]

        lpp_matched = False
        for m in _LPP_RE.finditer(folded):
            val = _unit_value_to_meters(m.group(1), m.group(2))
            if val is not None:
                _append_unique(lpp_values, val)
                lpp_matched = True
        if not lpp_matched and any(tok in folded for tok in ("length (l.p.p)", "chieu dai giua 2 tru")):
            nb = _nearest_right_numeric(entry, entries)
            if nb is not None:
                _append_unique(lpp_values, nb)

        b_matched = False
        for m in _BREADTH_RE.finditer(folded):
            val = _unit_value_to_meters(m.group(1), m.group(2))
            if val is not None:
                _append_unique(breadth_values, val)
                b_matched = True
        if not b_matched and folded.startswith("breadth"):
            nb = _nearest_right_numeric(entry, entries)
            if nb is not None:
                _append_unique(breadth_values, nb)

        d_matched = False
        for m in _DEPTH_RE.finditer(folded):
            val = _unit_value_to_meters(m.group(1), m.group(2))
            if val is not None:
                _append_unique(depth_values, val)
                d_matched = True
        if not d_matched and folded.startswith("depth"):
            nb = _nearest_right_numeric(entry, entries)
            if nb is not None:
                _append_unique(depth_values, nb)

        for m in _DRAFT_RE.finditer(text if "T" in text else folded):
            raw_num = m.group(1) or m.group(3)
            raw_unit = m.group(2) if m.group(1) else m.group(4)
            if raw_num:
                val = _unit_value_to_meters(raw_num, raw_unit)
                if val is not None:
                    _append_unique(draft_values, val)

        eng_match = _ENGINE_RE.search(text)
        if eng_match:
            rhs = re.sub(r"\s+", " ", eng_match.group(1)).strip(" :-=")
            if rhs and rhs != "?":
                _append_unique(main_engines, rhs)

        for m in _SCALE_RE.finditer(folded):
            sc = _to_float(m.group(1))
            if sc is not None and sc > 0:
                _append_unique(claimed_scales, round(sc, 3))

        for m in _CLASS_NOTATION_RE.finditer(folded):
            tag = f"VR-{m.group(1).upper()}"
            _append_unique(class_notations, tag)
            _append_unique(service_areas, "INLAND_WATERWAY")
        for m in _EXPLICIT_CAP_RE.finditer(folded):
            tag = f"VR-{m.group(1).upper()}"
            _append_unique(class_notations, tag)
            _append_unique(service_areas, "INLAND_WATERWAY")

        if any(tok in folded for tok in ("thuy noi dia", "qcvn 72")):
            _append_unique(service_areas, "INLAND_WATERWAY")
        if any(
            tok in folded
            for tok in ("ocean going", "vien duong", "tau bien", "qcvn 21", "unrestricted service")
        ) or re.search(r"\bvrh\b", folded):
            _append_unique(service_areas, "OCEAN_GOING")

        if re.search(r"\bqcvn\s*21(?:\s*[:/]\s*\d{4})?\b", folded):
            _append_unique(explicit_exclusion_evidences, "STATUTORY_QCVN_21_SEA_SHIP")
        if re.search(r"(?:^|[^a-z0-9])\*?\s*vrh\b", folded) or re.search(
            r"\b(?:class|classification|cap\s+tau)\s*[:=]\s*\*?(?:vrh|dnv|abs|nk|lr|bv|rina|ccs|kr)\b",
            folded,
        ) or re.search(r"\b(?:dnv\s*\+?1a1|solas|iacs)\b", folded):
            _append_unique(explicit_exclusion_evidences, "STATUTORY_SEA_CLASS_NOTATION")
        if re.search(
            r"\b(?:qcvn\s*(?:25|50|51|54|55|56|84)|ferrocement|xi\s+mang\s+luoi\s+thep|"
            r"chat\s+deo\s+cot\s+soi\s+thuy\s+tinh|\bfrp\b|tau\s+vo\s+go|wooden\s+hull|"
            r"high[-\s]?speed\s+craft|tau\s+cao\s+toc|floating\s+dock|\bu\s+noi\b|"
            r"tau\s+quoc\s+phong|fishing\s+vessel|tau\s+ca)\b",
            folded,
        ):
            _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_1_EXCLUSION")

        ship_m = _SHIP_TYPE_RE.search(folded)
        if ship_m:
            stype = ship_m.group(1).strip().upper()
            if stype:
                _append_unique(ship_types, stype)
        elif "tau hang kho" in folded or "dry cargo" in folded:
            _append_unique(ship_types, "DRY CARGO")

        x_coord = entry.get("x")
        if x_coord is not None:
            stripped_folded = folded.strip()
            if _AP_ONLY_RE.fullmatch(stripped_folded):
                ap_coords.append(x_coord)
            elif _FP_ONLY_RE.fullmatch(stripped_folded):
                fp_coords.append(x_coord)

        for m in _PLATE_THICK_RE.finditer(folded):
            thk = _to_float(m.group(1))
            if thk is not None and 0.5 <= thk <= 80.0:
                extracted_plate_mm.append(round(thk, 3))

    return {
        "lpp_m_values": lpp_values,
        "breadth_m_values": breadth_values,
        "depth_m_values": depth_values,
        "draft_m_values": draft_values,
        "main_engine_values": main_engines,
        "class_notations": class_notations,
        "service_areas": service_areas,
        "explicit_exclusion_evidences": explicit_exclusion_evidences,
        "ship_types": ship_types,
        "claimed_scales": claimed_scales,
        "ap_x_coords": ap_coords,
        "fp_x_coords": fp_coords,
        "extracted_plate_thicknesses_mm": extracted_plate_mm,
    }


def _infer_drawing_code(raw_code: object, entries: list[dict[str, Any]]) -> str:
    explicit = normalize_marine_cad_text(str(raw_code or "")).strip()
    if explicit:
        return explicit
    codes: list[str] = []
    for entry in entries:
        matches = _CODE_TOKEN_RE.findall(entry["text"])
        if matches:
            for item in matches:
                cleaned = re.sub(r"\s+", " ", item).strip()
                if cleaned not in codes:
                    codes.append(cleaned)
    return " | ".join(codes)


def normalize_observation(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize either a structured dictionary or DXF snapshot into canonical observation form."""
    if not isinstance(raw, Mapping):
        raise TypeError("observation must be a mapping")
    if raw.get("_normalized_marine_obs") is True:
        return deepcopy(dict(raw))

    drawing_id = str(raw.get("drawing_id") or "UNSPECIFIED_DRAWING").strip()
    entries = _normalize_text_entries(raw.get("texts", []))
    drawing_code = _infer_drawing_code(raw.get("drawing_code"), entries)
    insunits = int(raw["insunits"]) if isinstance(raw.get("insunits"), int) else 0
    measurement = int(raw["measurement"]) if isinstance(raw.get("measurement"), int) else 0

    particulars = _extract_particulars(entries, raw)
    raw_metrics = raw.get("structural_metrics")
    structural_metrics = dict(raw_metrics) if isinstance(raw_metrics, Mapping) else {}
    if (
        "min_plate_thickness_mm" not in structural_metrics
        and particulars["extracted_plate_thicknesses_mm"]
    ):
        structural_metrics["min_plate_thickness_mm"] = min(
            particulars["extracted_plate_thicknesses_mm"]
        )

    blank_fields = _detect_blank_fields(entries, raw.get("blank_fields"))
    text_heights = sorted(
        {round(entry["height"], 4) for entry in entries if entry["height"] is not None and entry["height"] > 0}
    )

    claimed_scale = None
    if particulars["claimed_scales"]:
        claimed_scale = particulars["claimed_scales"][0]

    source_mode = str(raw.get("source_mode") or ("OCR_ONLY" if raw.get("ocr_only") else "STRUCTURED_OR_DXF"))
    return {
        "_normalized_marine_obs": True,
        "drawing_id": drawing_id,
        "drawing_code": drawing_code,
        "insunits": insunits,
        "measurement": measurement,
        "claimed_scale": claimed_scale,
        "source_mode": source_mode,
        "ocr_only": bool(raw.get("ocr_only", False) or source_mode.upper() == "OCR_ONLY"),
        "entity_counts": dict(raw.get("entity_counts", {}))
        if isinstance(raw.get("entity_counts"), Mapping)
        else {},
        "texts": entries,
        "particulars": particulars,
        "structural_metrics": structural_metrics,
        "blank_fields": blank_fields,
        "text_heights": text_heights,
    }


__all__ = [
    "normalize_observation",
    "observe_dxf_bytes",
    "observe_dxf_file",
]
