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

from .contracts import MarineKnowledgeError
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

_MAX_OBSERVATION_TEXT_ITEMS = 5000
_MAX_TEXT_LENGTH = 4096

_L_DESIGN_RE = re.compile(
    r"(?:^|\b)(?:chieu\s+dai\s+tau(?:\s*\(?l\)?)?|chieu\s+dai\s+thiet\s+ke|design\s+length|ltk|l)\s*[:=]\s*"
    r"([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_LPP_RE = re.compile(
    r"\b(?:lpp|l\.p\.p|length\s*\(?l\.?p\.?p\)?|chieu\s+dai\s+giua\s+2\s+tru)\b\s*[:=]?\s*"
    r"([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_LWL_RE = re.compile(
    r"\b(?:lwl|chieu\s+dai\s+duong\s+nuoc(?:\s+thiet\s+ke)?)\b\s*[:=]?\s*"
    r"([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_BREADTH_RE = re.compile(
    r"(?:^|\b)(?:breadth(?:\s*\(?b\)?)?|chieu\s+rong(?:\s*\(?b\)?)?|b)\s*[:=]\s*"
    r"([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_DEPTH_RE = re.compile(
    r"(?:^|\b)(?:depth(?:\s*\(?d\)?)?|chieu\s+cao\s+man(?:\s*\(?d\)?)?|d)\s*[:=]\s*"
    r"([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_DRAFT_WORD_RE = re.compile(
    r"(?:^|\b)(?:draught|draft|chieu\s+chim(?:\s*\(?t\)?)?|mon\s+nuoc)\s*[:=]?\s*"
    r"([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_DRAFT_SYMBOL_T_RE = re.compile(
    r"(?:^|\b)T\s*[:=]\s*([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_CORRUPTED_NUMBER_RE = re.compile(
    r"(?:^|\b)(?:lpp|l\.p\.p|ltk|lwl|l|b|d|t|breadth|depth|draught|draft)\b\s*[:=]\s*"
    r"([0-9]+[.,][0-9]*[oOiIlLsS]+[0-9a-zA-Z]*|[0-9]+[oOiIlLsS]+[0-9]*)",
    re.IGNORECASE,
)
_ENGINE_RE = re.compile(r"(?:main\s*engine|may\s*chinh)\s*[:=]?\s*(.+)$", re.IGNORECASE)
_HULL_NO_RE = re.compile(r"\b(?:hull\s*no\.?|so\s+hieu\s+tau|yard\s*no\.?)\s*[:=]\s*([A-Za-z0-9_./-]+)", re.IGNORECASE)
_SCALE_RE = re.compile(r"\b(?:ty\s+le|scale)\s*[:=]?\s*1\s*[:/]\s*([0-9]+(?:[.,][0-9]+)?)\b")
_PLATE_THICK_RE = re.compile(
    r"\bs\s*=\s*([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])(?:\s*(mm))?(?!\s*(?:cm|m|s|t|kw|hp)\b)|"
    r"(?:^|\b)(?:t|chieu\s+day)\s*=\s*([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*mm\b"
)
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
_NEGATED_SCOPE_RE = re.compile(
    r"\b(?:khong\s+ap\s+dung|khong\s+phai|not\s+applicable|ngoai\s+tru|loai\s+tru)\b"
)
_NON_MARINE_DOMAIN_RE = re.compile(
    r"\b(?:truc\s+bac|chi\s+tiet\s+truc|banh\s+rang|chi\s+tiet\s+may|xe\s+o\s+to|o\s+to\s+tai|"
    r"xe\s+co\s+gioi|so\s+mi\s+ro\s+mooc|kiem\s+dinh\s+xe|may\s+tien|thep\s+c45|mechanical\s+shaft)\b"
)

_STRUCTURAL_PLATE_CTX_RE = re.compile(
    r"\b(?:ton\s+day|ton\s+hong|ton\s+ha\s+ma|ton\s+man|ton\s+boong|ton\s+bao|than\s+tau|"
    r"ket\s+cau|song\s+day|da\s+ngang|vach|bottom|bilge|keel|side\s+shell|deck|shell\s+plate|hull\s+plate)\b"
)

_EQUIPMENT_ACCESSORY_RE = re.compile(
    r"\b(?:xuong\s+cuu\s+sinh|lifeboat|liferaft|phao\s+cuu\s+sinh|lifebuoy|lifejacket|"
    r"locker|cabinet|enclosure|extinguisher|binh\s+chua\s+chay|fire\s+hose|fire\s+station|"
    r"davit|seat|chair|furniture|console|hatch\s+cover|door|window|decal|nameplate|"
    r"tu\s+dung|hop\s+dung|tu\s+chua|hop\s+chua)\b"
)
_VESSEL_FRP_RE = re.compile(
    r"\bqcvn\s*56(?:\s*[:/]\s*\d{4})?\b|"
    r"\b(?:hull\s+material|vat\s+lieu\s+(?:vo|than\s+tau)|material)\s*[:=]\s*(?:frp|chat\s+deo\s+cot\s+soi\s+thuy\s+tinh)\b|"
    r"\b(?:vo\s+frp|tau\s+(?:vo\s+)?(?:frp|chat\s+deo\s+cot\s+soi\s+thuy\s+tinh)|frp\s+(?:hull|vessel|craft|boat|ship)|"
    r"vr\s*-?\s*(?:sb|si|sii|siii)\s+frp)\b"
)
_ALUMINUM_HULL_RE = re.compile(
    r"\bvr\s*-?\s*(?:sb|si|sii|siii)\s+al\b|"
    r"\b(?:hull\s+material|vat\s+lieu\s+(?:vo|than\s+tau)|material)\s*[:=]\s*"
    r"(?:aluminum(?:\s+alloy)?|aluminium(?:\s+alloy)?|al\b|nhom|hop\s+kim\s+nhom|hop\s+kim\s+nhe)\b|"
    r"\b(?:vo\s+nhom|tau\s+(?:vo\s+)?(?:nhom|hop\s+kim\s+nhom|hop\s+kim\s+nhe)|"
    r"(?:aluminum|aluminium)\s+(?:alloy\s+)?(?:hull|vessel|craft))\b"
)
_STEEL_HULL_RE = re.compile(
    r"\b(?:hull\s+material|vat\s+lieu\s+(?:vo|than\s+tau)|material)\s*[:=]\s*"
    r"(?:welded\s+steel|shipbuilding\s+steel|steel|thep\s+han|thep\s+dong\s+tau|thep|grade\s+[abde]\b|ah3[26]\b)|"
    r"\b(?:vo\s+thep|tau\s+(?:vo\s+)?thep(?:\s+han)?|(?:welded\s+)?steel\s+hull)\b"
)
_CONCRETE_HULL_RE = re.compile(
    r"\bvr\s*-?\s*(?:sb|si|sii|siii)\s+btct\b|"
    r"\b(?:hull\s+material|vat\s+lieu\s+(?:vo|than\s+tau)|material)\s*[:=]\s*(?:btct|be\s+tong\s+cot\s+thep|reinforced\s+concrete)\b|"
    r"\b(?:vo\s+btct|tau\s+(?:vo\s+)?be\s+tong\s+cot\s+thep|reinforced\s+concrete\s+hull)\b"
)

_MAX_BLOCK_TEXT_ITEMS = 250
_MAX_INSERT_RECURSION_DEPTH = 8


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


def _unit_value_to_meters(raw_num: str, unit: str | None, *, insunits: int = 0) -> tuple[float | None, bool]:
    val = _to_float(raw_num)
    if val is None or val <= 0:
        return None, False
    unit_norm = (unit or "").lower().strip()
    if unit_norm == "mm":
        return round(val / 1000.0, 4), True
    if unit_norm == "cm":
        return round(val / 100.0, 4), True
    if unit_norm == "m":
        return round(val, 4), True
    if insunits == 4:
        return round(val / 1000.0, 4), True
    if insunits == 5:
        return round(val / 100.0, 4), True
    if insunits == 6:
        return round(val, 4), True
    return round(val, 4), False


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


def _entity_text_payload(entity: Any, style_fonts: Mapping[str, str]) -> dict[str, Any] | None:
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
    x = _to_float(getattr(insert, "x", None)) or 0.0
    y = _to_float(getattr(insert, "y", None)) or 0.0
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


def _check_supported_insert_transform(entity: Any) -> str | None:
    ext = getattr(entity.dxf, "extrusion", (0.0, 0.0, 1.0))
    try:
        ex, ey, ez = float(ext[0]), float(ext[1]), float(ext[2])
    except Exception:
        return "INVALID_EXTRUSION"
    if not (math.isfinite(ex) and math.isfinite(ey) and math.isfinite(ez)):
        return "NON_FINITE_EXTRUSION"
    if abs(ex) > 1e-6 or abs(ey) > 1e-6 or abs(ez - 1.0) > 1e-6:
        return f"NON_PLANAR_3D_EXTRUSION({round(ex, 4)},{round(ey, 4)},{round(ez, 4)})"

    ins = getattr(entity.dxf, "insert", None)
    for coord in (
        getattr(ins, "x", 0.0),
        getattr(ins, "y", 0.0),
        getattr(ins, "z", 0.0),
        getattr(entity.dxf, "xscale", 1.0),
        getattr(entity.dxf, "yscale", 1.0),
        getattr(entity.dxf, "zscale", 1.0),
        getattr(entity.dxf, "rotation", 0.0),
    ):
        try:
            if not math.isfinite(float(coord)):
                return "NON_FINITE_INSERT_TRANSFORM"
        except Exception:
            return "INVALID_INSERT_TRANSFORM"
    return None


def _expand_insert_texts(
    insert_entity: Any,
    style_fonts: Mapping[str, str],
    *,
    depth: int,
    ancestor_blocks: frozenset[str],
    collected: list[dict[str, Any]],
    unsupported: list[dict[str, Any]],
    root_handle: str,
) -> None:
    if len(collected) >= _MAX_BLOCK_TEXT_ITEMS:
        return
    block_name = str(getattr(insert_entity.dxf, "name", "") or "")
    if depth > _MAX_INSERT_RECURSION_DEPTH:
        unsupported.append(
            {"handle": root_handle, "block_name": block_name, "reason": "INSERT_NESTING_TOO_DEEP"}
        )
        return
    if block_name and block_name in ancestor_blocks:
        unsupported.append(
            {"handle": root_handle, "block_name": block_name, "reason": "CYCLIC_BLOCK_REFERENCE"}
        )
        return
    unsupported_reason = _check_supported_insert_transform(insert_entity)
    if unsupported_reason is not None:
        unsupported.append(
            {"handle": root_handle, "block_name": block_name, "reason": unsupported_reason}
        )
        return

    try:
        virtuals = list(insert_entity.virtual_entities())
    except Exception as exc:
        unsupported.append(
            {
                "handle": root_handle,
                "block_name": block_name,
                "reason": f"VIRTUAL_TRANSFORM_ERROR:{type(exc).__name__}",
            }
        )
        return

    next_ancestors = ancestor_blocks | ({block_name} if block_name else frozenset())
    for ve in virtuals:
        if len(collected) >= _MAX_BLOCK_TEXT_ITEMS:
            break
        vtype = ve.dxftype()
        if vtype == "INSERT":
            for attrib in getattr(ve, "attribs", ()):
                attr_item = _entity_text_payload(attrib, style_fonts)
                if attr_item is not None and len(collected) < _MAX_BLOCK_TEXT_ITEMS:
                    collected.append(attr_item)
            _expand_insert_texts(
                ve,
                style_fonts,
                depth=depth + 1,
                ancestor_blocks=next_ancestors,
                collected=collected,
                unsupported=unsupported,
                root_handle=root_handle,
            )
            continue
        item = _entity_text_payload(ve, style_fonts)
        if item is not None:
            if not item["handle"]:
                item["handle"] = root_handle
            collected.append(item)


def _collect_dxf_texts(
    doc: Any,
    style_fonts: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    texts: list[dict[str, Any]] = []
    entity_counts: dict[str, int] = {}
    unsupported_insert_transforms: list[dict[str, Any]] = []

    msp = doc.modelspace()
    for entity in msp:
        dxftype = entity.dxftype()
        entity_counts[dxftype] = entity_counts.get(dxftype, 0) + 1
        item = _entity_text_payload(entity, style_fonts)
        if item is not None:
            texts.append(item)
            continue
        if dxftype == "INSERT":
            root_handle = str(getattr(entity.dxf, "handle", "") or "")
            for attrib in getattr(entity, "attribs", ()):
                attr_item = _entity_text_payload(attrib, style_fonts)
                if attr_item is not None:
                    texts.append(attr_item)
            block_name = str(getattr(entity.dxf, "name", "") or "")
            if block_name and not block_name.startswith("*"):
                ins_items: list[dict[str, Any]] = []
                _expand_insert_texts(
                    entity,
                    style_fonts,
                    depth=0,
                    ancestor_blocks=frozenset(),
                    collected=ins_items,
                    unsupported=unsupported_insert_transforms,
                    root_handle=root_handle,
                )
                texts.extend(ins_items)

    return texts, entity_counts, unsupported_insert_transforms


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
    texts, entity_counts, unsupported_insert_transforms = _collect_dxf_texts(doc, style_fonts)

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
            "unsupported_insert_transforms": unsupported_insert_transforms,
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
    if len(raw_texts) > _MAX_OBSERVATION_TEXT_ITEMS:
        raise MarineKnowledgeError("OBSERVATION_INPUT_TOO_LARGE")
    for idx, item in enumerate(raw_texts):
        if not isinstance(item, Mapping):
            continue
        raw_str = str(item.get("raw_text", item.get("text", "")) or "")
        if len(raw_str) > _MAX_TEXT_LENGTH:
            raise MarineKnowledgeError("OBSERVATION_INPUT_TOO_LARGE")
        font_hint = str(item.get("font_hint", "") or "")
        if "raw_text" in item and item.get("text") is not None:
            norm_text = str(item.get("text") or "").strip()
            if len(norm_text) > _MAX_TEXT_LENGTH:
                raise MarineKnowledgeError("OBSERVATION_INPUT_TOO_LARGE")
        else:
            try:
                norm_text = normalize_marine_cad_text(
                    str(item.get("text", raw_str) or ""),
                    font_hint=font_hint,
                )
            except ValueError as exc:
                raise MarineKnowledgeError("OBSERVATION_INPUT_TOO_LARGE") from exc
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


def _nearest_right_numeric(
    label_entry: Mapping[str, Any],
    entries: list[dict[str, Any]],
    *,
    insunits: int = 0,
) -> tuple[float | None, bool]:
    lx = label_entry.get("x")
    ly = label_entry.get("y")
    if lx is None or ly is None:
        return None, False
    h = label_entry.get("height") or 200.0
    candidates: list[tuple[float, float, bool]] = []
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
        m = re.fullmatch(r"\s*([0-9]+(?:[.,][0-9]+)?)\s*(mm|cm|m)?\s*", other["folded"])
        if m:
            val, verified = _unit_value_to_meters(m.group(1), m.group(2), insunits=insunits)
            if val is not None:
                candidates.append((dx, val, verified))
    if not candidates:
        return None, False
    candidates.sort(key=lambda pair: pair[0])
    return candidates[0][1], candidates[0][2]


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


def _extract_particulars(
    entries: list[dict[str, Any]],
    raw: Mapping[str, Any],
    *,
    insunits: int = 0,
) -> dict[str, Any]:
    design_length_l_m_values: list[float] = []
    lpp_values: list[float] = []
    lwl_values: list[float] = []
    breadth_values: list[float] = []
    depth_values: list[float] = []
    draft_values: list[float] = []
    main_engines: list[str] = []
    hull_nos: list[str] = []
    class_notations: list[str] = []
    service_areas: list[str] = []
    explicit_exclusion_evidences: list[str] = []
    incidental_equipment_mentions: list[str] = []
    ship_types: list[str] = []
    hull_materials: list[str] = []
    claimed_scales: list[float] = []
    ap_coords: list[float] = []
    fp_coords: list[float] = []
    extracted_plate_mm: list[float] = []
    bottom_plate_mm: list[float] = []
    bilge_plate_mm: list[float] = []
    unbound_plate_mm: list[float] = []
    corrupted_numeric_tokens: list[str] = []
    unverified_unitless_particulars: list[str] = []
    non_marine_domain_hits: list[str] = []
    negated_scope_texts: list[str] = []

    raw_scale = _to_float(raw.get("claimed_scale"))
    if raw_scale is not None and raw_scale > 0:
        _append_unique(claimed_scales, round(raw_scale, 3))

    for entry in entries:
        text = entry["text"]
        folded = entry["folded"]

        for bad_tok in _CORRUPTED_NUMBER_RE.findall(text):
            _append_unique(corrupted_numeric_tokens, str(bad_tok).strip())

        for m in _L_DESIGN_RE.finditer(folded):
            val, verified = _unit_value_to_meters(m.group(1), m.group(2), insunits=insunits)
            if val is not None:
                if verified:
                    _append_unique(design_length_l_m_values, val)
                else:
                    _append_unique(unverified_unitless_particulars, f"L:{m.group(1)}")

        lpp_matched = False
        for m in _LPP_RE.finditer(folded):
            val, verified = _unit_value_to_meters(m.group(1), m.group(2), insunits=insunits)
            if val is not None:
                if verified:
                    _append_unique(lpp_values, val)
                else:
                    _append_unique(unverified_unitless_particulars, f"Lpp:{m.group(1)}")
                lpp_matched = True
        if not lpp_matched and any(tok in folded for tok in ("length (l.p.p)", "chieu dai giua 2 tru")):
            nb, nb_ok = _nearest_right_numeric(entry, entries, insunits=insunits)
            if nb is not None:
                if nb_ok:
                    _append_unique(lpp_values, nb)
                else:
                    _append_unique(unverified_unitless_particulars, f"Lpp:{nb}")

        for m in _LWL_RE.finditer(folded):
            val, verified = _unit_value_to_meters(m.group(1), m.group(2), insunits=insunits)
            if val is not None:
                if verified:
                    _append_unique(lwl_values, val)
                else:
                    _append_unique(unverified_unitless_particulars, f"Lwl:{m.group(1)}")

        b_matched = False
        for m in _BREADTH_RE.finditer(folded):
            val, verified = _unit_value_to_meters(m.group(1), m.group(2), insunits=insunits)
            if val is not None:
                if verified:
                    _append_unique(breadth_values, val)
                else:
                    _append_unique(unverified_unitless_particulars, f"B:{m.group(1)}")
                b_matched = True
        if not b_matched and folded.startswith("breadth"):
            nb, nb_ok = _nearest_right_numeric(entry, entries, insunits=insunits)
            if nb is not None:
                if nb_ok:
                    _append_unique(breadth_values, nb)
                else:
                    _append_unique(unverified_unitless_particulars, f"B:{nb}")

        d_matched = False
        for m in _DEPTH_RE.finditer(folded):
            val, verified = _unit_value_to_meters(m.group(1), m.group(2), insunits=insunits)
            if val is not None:
                if verified:
                    _append_unique(depth_values, val)
                else:
                    _append_unique(unverified_unitless_particulars, f"D:{m.group(1)}")
                d_matched = True
        if not d_matched and folded.startswith("depth"):
            nb, nb_ok = _nearest_right_numeric(entry, entries, insunits=insunits)
            if nb is not None:
                if nb_ok:
                    _append_unique(depth_values, nb)
                else:
                    _append_unique(unverified_unitless_particulars, f"D:{nb}")

        for m in _DRAFT_WORD_RE.finditer(folded):
            raw_num = m.group(1)
            raw_unit = m.group(2)
            if raw_num:
                val, verified = _unit_value_to_meters(raw_num, raw_unit, insunits=insunits)
                if val is not None:
                    if verified:
                        _append_unique(draft_values, val)
                    else:
                        _append_unique(unverified_unitless_particulars, f"T:{raw_num}")

        for m in _DRAFT_SYMBOL_T_RE.finditer(text):
            raw_num = m.group(1)
            raw_unit = m.group(2)
            if raw_num:
                val, verified = _unit_value_to_meters(raw_num, raw_unit, insunits=insunits)
                if val is not None:
                    if verified:
                        _append_unique(draft_values, val)
                    else:
                        _append_unique(unverified_unitless_particulars, f"T:{raw_num}")

        eng_match = _ENGINE_RE.search(text)
        if eng_match:
            rhs = re.sub(r"\s+", " ", eng_match.group(1)).strip(" :-=")
            if rhs and rhs != "?":
                _append_unique(main_engines, rhs)

        for hull_m in _HULL_NO_RE.finditer(text):
            hno = hull_m.group(1).strip()
            if hno and hno != "?":
                _append_unique(hull_nos, hno)

        for m in _SCALE_RE.finditer(folded):
            sc = _to_float(m.group(1))
            if sc is not None and sc > 0:
                _append_unique(claimed_scales, round(sc, 3))

        for nm_hit in _NON_MARINE_DOMAIN_RE.findall(folded):
            cleaned_nm = re.sub(r"\s+", " ", nm_hit).strip()
            if cleaned_nm:
                _append_unique(non_marine_domain_hits, cleaned_nm)

        for clause in re.split(r"[;\n]+", folded):
            clause_clean = clause.strip()
            if not clause_clean:
                continue
            if _NEGATED_SCOPE_RE.search(clause_clean):
                _append_unique(negated_scope_texts, clause_clean)
                continue

            for m in _CLASS_NOTATION_RE.finditer(clause_clean):
                tag = f"VR-{m.group(1).upper()}"
                _append_unique(class_notations, tag)
                _append_unique(service_areas, "INLAND_WATERWAY")
            for m in _EXPLICIT_CAP_RE.finditer(clause_clean):
                tag = f"VR-{m.group(1).upper()}"
                _append_unique(class_notations, tag)
                _append_unique(service_areas, "INLAND_WATERWAY")

            if any(tok in clause_clean for tok in ("thuy noi dia", "qcvn 72")):
                _append_unique(service_areas, "INLAND_WATERWAY")
            is_equipment_item = bool(_EQUIPMENT_ACCESSORY_RE.search(clause_clean))
            if is_equipment_item:
                if re.search(r"\b(?:frp|solas|imo|iacs|qcvn\s*(?:21|25|50|51|54|55|56|84))\b", clause_clean):
                    _append_unique(incidental_equipment_mentions, clause_clean)
            else:
                if any(
                    tok in clause_clean
                    for tok in ("ocean going", "vien duong", "tau bien", "qcvn 21", "unrestricted service")
                ) or re.search(r"\bvrh\b", clause_clean):
                    _append_unique(service_areas, "OCEAN_GOING")

                if re.search(r"\bqcvn\s*21(?:\s*[:/]\s*\d{4})?\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_QCVN_21_SEA_SHIP")
                if re.search(r"(?:^|[^a-z0-9])\*?\s*vrh\b", clause_clean) or re.search(
                    r"\b(?:class|classification|cap\s+tau)\s*[:=]\s*\*?(?:vrh|dnv|abs|nk|lr|bv|rina|ccs|kr)\b",
                    clause_clean,
                ) or re.search(r"\bdnv\s*\+?1a1\b", clause_clean) or (
                    re.search(r"\b(?:solas|iacs)\b", clause_clean)
                    and re.search(r"\b(?:class|classification|cap\s+tau|regulation|quy\s+chuan|convention|vessel|ship|tau)\b", clause_clean)
                ):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_SEA_CLASS_NOTATION")

                if re.search(r"\bqcvn\s*25(?:\s*[:/]\s*\d{4})?\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_1_QCVN_25_SMALL_CRAFT")
                if re.search(r"\b(?:qcvn\s*50|tau\s+the\s+thao|vui\s+choi\s+giai\s+tri|leisure\s+craft)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_2_QCVN_50_LEISURE")
                if re.search(r"\b(?:qcvn\s*51|ferrocement|xi\s+mang\s+luoi\s+thep)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_2_QCVN_51_FERROCEMENT")
                    _append_unique(hull_materials, "FERROCEMENT")
                if _VESSEL_FRP_RE.search(clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_2_QCVN_56_FRP")
                    _append_unique(hull_materials, "FRP")
                if re.search(r"\b(?:qcvn\s*84|tau\s+vo\s+go|tau\s+go|wooden\s+hull|wooden\s+craft)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_2_QCVN_84_WOOD")
                    _append_unique(hull_materials, "WOOD")
                if re.search(r"\b(?:qcvn\s*54|high[-\s]?speed\s+craft|tau\s+cao\s+toc)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_2_QCVN_54_HSC")
                if re.search(r"\b(?:qcvn\s*55|floating\s+dock|u\s+noi)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_2_QCVN_55_DOCK")
                if re.search(r"\b(?:tau\s+quoc\s+phong|quoc\s+phong|an\s+ninh|defense\s+vessel|security\s+vessel)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_4_DEFENSE_SECURITY")
                if re.search(r"\b(?:tau\s+ca|fishing\s+vessel)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_4_FISHING_VESSEL")

                if _ALUMINUM_HULL_RE.search(clause_clean):
                    _append_unique(hull_materials, "ALUMINUM")
                if _STEEL_HULL_RE.search(clause_clean):
                    _append_unique(hull_materials, "STEEL")
                if _CONCRETE_HULL_RE.search(clause_clean):
                    _append_unique(hull_materials, "CONCRETE")

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

        has_plate_ctx = bool(_STRUCTURAL_PLATE_CTX_RE.search(folded))
        for m in _PLATE_THICK_RE.finditer(folded):
            raw_thk = m.group(1) or m.group(3)
            thk = _to_float(raw_thk) if raw_thk else None
            if thk is not None and 0.5 <= thk <= 80.0:
                rounded = round(thk, 3)
                if has_plate_ctx:
                    extracted_plate_mm.append(rounded)
                    if any(tok in folded for tok in ("ton day", "bottom", "keel")):
                        bottom_plate_mm.append(rounded)
                    if any(tok in folded for tok in ("ton hong", "ton ha ma", "bilge")):
                        bilge_plate_mm.append(rounded)
                else:
                    unbound_plate_mm.append(rounded)

    return {
        "design_length_l_m_values": design_length_l_m_values,
        "lpp_m_values": lpp_values,
        "lwl_m_values": lwl_values,
        "breadth_m_values": breadth_values,
        "depth_m_values": depth_values,
        "draft_m_values": draft_values,
        "main_engine_values": main_engines,
        "hull_nos": hull_nos,
        "class_notations": class_notations,
        "service_areas": service_areas,
        "explicit_exclusion_evidences": explicit_exclusion_evidences,
        "incidental_equipment_mentions": incidental_equipment_mentions,
        "ship_types": ship_types,
        "hull_materials": hull_materials,
        "claimed_scales": claimed_scales,
        "ap_x_coords": ap_coords,
        "fp_x_coords": fp_coords,
        "extracted_plate_thicknesses_mm": extracted_plate_mm,
        "bottom_plate_thicknesses_mm": bottom_plate_mm,
        "bilge_plate_thicknesses_mm": bilge_plate_mm,
        "unbound_plate_thicknesses_mm": unbound_plate_mm,
        "corrupted_numeric_tokens": corrupted_numeric_tokens,
        "unverified_unitless_particulars": unverified_unitless_particulars,
        "non_marine_domain_hits": non_marine_domain_hits,
        "negated_scope_texts": negated_scope_texts,
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

    particulars = _extract_particulars(entries, raw, insunits=insunits)
    raw_metrics = raw.get("structural_metrics")
    structural_metrics = dict(raw_metrics) if isinstance(raw_metrics, Mapping) else {}
    min_plate_from_unbound_text = False
    if (
        "min_plate_thickness_mm" not in structural_metrics
        and particulars["extracted_plate_thicknesses_mm"]
    ):
        structural_metrics["min_plate_thickness_mm"] = min(
            particulars["extracted_plate_thicknesses_mm"]
        )
    elif (
        "min_plate_thickness_mm" not in structural_metrics
        and particulars["unbound_plate_thicknesses_mm"]
    ):
        min_plate_from_unbound_text = True

    if "min_bottom_plate_mm" not in structural_metrics and particulars["bottom_plate_thicknesses_mm"]:
        structural_metrics["min_bottom_plate_mm"] = min(particulars["bottom_plate_thicknesses_mm"])
    if "min_bilge_plate_mm" not in structural_metrics and particulars["bilge_plate_thicknesses_mm"]:
        structural_metrics["min_bilge_plate_mm"] = min(particulars["bilge_plate_thicknesses_mm"])

    blank_fields = _detect_blank_fields(entries, raw.get("blank_fields"))
    text_heights = sorted(
        {round(entry["height"], 4) for entry in entries if entry["height"] is not None and entry["height"] > 0}
    )

    claimed_scale = None
    if particulars["claimed_scales"]:
        claimed_scale = particulars["claimed_scales"][0]

    source_mode = str(raw.get("source_mode") or ("OCR_ONLY" if raw.get("ocr_only") else "STRUCTURED_OR_DXF"))
    entity_counts = dict(raw.get("entity_counts", {})) if isinstance(raw.get("entity_counts"), Mapping) else {}
    observed_handles = [entry["handle"] for entry in entries if entry.get("handle")]
    explicit_geom_status = str(raw.get("geometry_status") or "").strip().upper()
    if explicit_geom_status:
        geometry_status = explicit_geom_status
    elif raw.get("ocr_only") or source_mode.upper() == "OCR_ONLY":
        geometry_status = "OCR_ONLY"
    elif entity_counts or source_mode.upper() == "NATIVE_DXF_SNAPSHOT":
        prim_count = sum(
            int(entity_counts.get(kind, 0) or 0)
            for kind in ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "SPLINE", "ELLIPSE")
        )
        geometry_status = "PRESENT" if prim_count > 0 else "NO_GEOMETRY_PRIMITIVES"
    else:
        geometry_status = "METADATA_ONLY"

    raw_prov = raw.get("metric_provenance")
    metric_provenance: dict[str, str] = dict(raw_prov) if isinstance(raw_prov, Mapping) else {}
    is_ocr = bool(raw.get("ocr_only", False) or source_mode.upper() == "OCR_ONLY")
    for metric_key in structural_metrics:
        if metric_key in metric_provenance:
            continue
        if isinstance(raw_metrics, Mapping) and metric_key in raw_metrics:
            metric_provenance[metric_key] = "UNVERIFIED_OCR_TEXT" if is_ocr else "FIXTURE_SUPPLIED"
        else:
            metric_provenance[metric_key] = "UNVERIFIED_OCR_TEXT" if is_ocr else "NATIVE_CAD_TEXT"
    for p_key, p_list_key in (
        ("design_length_l_m", "design_length_l_m_values"),
        ("lpp_m", "lpp_m_values"),
        ("lwl_m", "lwl_m_values"),
        ("breadth_m", "breadth_m_values"),
        ("depth_m", "depth_m_values"),
        ("draft_m", "draft_m_values"),
        ("main_engine", "main_engine_values"),
        ("ship_type", "ship_types"),
        ("hull_material", "hull_materials"),
    ):
        if p_key not in metric_provenance and particulars.get(p_list_key):
            metric_provenance[p_key] = "UNVERIFIED_OCR_TEXT" if is_ocr else "NATIVE_CAD_TEXT"

    unsupported_insert_transforms = [
        deepcopy(item)
        for item in (raw.get("unsupported_insert_transforms") or [])
        if isinstance(item, (Mapping, str))
    ]

    invalid_structural_metrics: list[str] = []
    _non_dim_metric_keys = {"floor_spacing_region"}
    for mkey, mval in list(structural_metrics.items()):
        if mkey in _non_dim_metric_keys:
            continue
        if isinstance(mval, bool) or not isinstance(mval, (int, float)):
            invalid_structural_metrics.append(f"{mkey}={mval!r}")
            continue
        fval = float(mval)
        if not math.isfinite(fval):
            invalid_structural_metrics.append(f"{mkey}={mval!r}")
            continue
        if mkey == "transverse_watertight_bulkhead_count":
            if fval < 0 or not fval.is_integer():
                invalid_structural_metrics.append(f"{mkey}={mval!r}")
        elif fval <= 0.0:
            invalid_structural_metrics.append(f"{mkey}={mval!r}")

    return {
        "_normalized_marine_obs": True,
        "drawing_id": drawing_id,
        "drawing_code": drawing_code,
        "insunits": insunits,
        "measurement": measurement,
        "claimed_scale": claimed_scale,
        "source_mode": source_mode,
        "ocr_only": is_ocr,
        "geometry_status": geometry_status,
        "observed_handles": observed_handles,
        "entity_counts": entity_counts,
        "unsupported_insert_transforms": unsupported_insert_transforms,
        "invalid_structural_metrics": invalid_structural_metrics,
        "texts": entries,
        "particulars": particulars,
        "structural_metrics": structural_metrics,
        "metric_provenance": metric_provenance,
        "min_plate_from_unbound_text": min_plate_from_unbound_text,
        "blank_fields": blank_fields,
        "text_heights": text_heights,
    }


__all__ = [
    "normalize_observation",
    "observe_dxf_bytes",
    "observe_dxf_file",
]
