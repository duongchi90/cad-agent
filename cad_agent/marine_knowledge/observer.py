"""Read-only marine CAD and structural observation extractor.

Reuses ``dxf_builder_lib._dxf_snapshot.read_dxf_snapshot`` for raw DXF reading
without importing ``ezdxf`` directly outside ``dxf_builder_lib/``, preserving
existing architecture boundaries.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import math
import os
from pathlib import Path
import re
from typing import Any

from cad_agent.file_integrity import open_bound_file
from dxf_builder_lib._dxf_snapshot import read_dxf_snapshot

from .contracts import MarineKnowledgeError
from .evidence_binding import (
    build_engineering_fact,
    evaluate_dimension_fact,
    strip_mtext_formatting,
    validate_engineering_fact,
)
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
    r"(?:(abt|approx)\.?\s*)?([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_LOA_RE = re.compile(
    r"\b(?:loa|l\.o\.a\.?|length\s*\(?o\.?a\.?\)?|chieu\s+dai\s+lon\s+nhat)\b\s*[:=]\s*"
    r"(?:(abt|approx)\.?\s*)?([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_LPP_RE = re.compile(
    r"\b(?:lpp|l\.p\.p\.?|length\s*\(?(?:l\.?)?p\.?p\.?\)?|chieu\s+dai\s+giua\s+2\s+tru)\b\s*[:=]?\s*"
    r"(?:(abt|approx)\.?\s*)?([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_LWL_RE = re.compile(
    r"\b(?:lwl|length\s*\(?w\.?l\.?\)?|chieu\s+dai\s+duong\s+nuoc(?:\s+thiet\s+ke)?)\b\s*[:=]?\s*"
    r"(?:(abt|approx)\.?\s*)?([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_BREADTH_RE = re.compile(
    r"(?:^|\b)(?:breadth(?:\s*\(?b\)?)?|chieu\s+rong(?:\s*\(?b\)?)?|b)\s*[:=]\s*"
    r"([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_DEPTH_RE = re.compile(
    r"(?:^|\b)(?:depth(?:\s*\(?d\)?)?|chieu\s+cao\s+man(?:\s*\(?d\)?)?|d)\s*[:=]\s*"
    r"([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_DRAFT_RE = re.compile(
    r"(?:^|\b)(?:draught|draft|chieu\s+chim(?:\s*\(?t\)?)?|mon\s+nuoc)\s*[:=]?\s*"
    r"([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b|"
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

_SINGLE_BOTTOM_RE = re.compile(r"\b(?:tau\s+day\s+don|day\s+don|single[-\s]?bottom)\b")

_DB_NON_CENTERLINE_CTX_RE = re.compile(
    r"\b(?:o\s+man|tai\s+man|phia\s+man|ben\s+man|at\s+side|at\s+bilge|margin\s+plate|o\s+hong|tai\s+hong)\b"
)
_DB_SIDE_HEIGHT_RE = re.compile(
    r"\b(?:"
    r"(?:chieu\s+cao\s+(?:cua\s+)?day\s+doi|double[-\s]?bottom\s+height|h_?(?:dd|db)|day\s+doi|double[-\s]?bottom)"
    r"[^;=\n]{0,48}?\b(?:o\s+man|tai\s+man|phia\s+man|ben\s+man|at\s+side|at\s+bilge|o\s+hong|tai\s+hong)\b[^:=\n]{0,20}?"
    r"|"
    r"margin\s+plate\s+height"
    r")\s*(?:[:=]\s*|\s+)([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_DB_HEIGHT_INLINE_RE = re.compile(
    r"\b(?:"
    r"chieu\s+cao\s+(?:cua\s+)?day\s+doi"
    r"(?:\s*(?:do\s+)?(?:tai\s+|o\s+)?\(?(?:mat\s+phang\s+doc\s+tam(?:\s+tau)?|mp\s*doc\s*tam|mpdt|doc\s+tam|cl|centerline|centreline)\)?)?"
    r"(?:\s*\(?(?:h(?:_?(?:dd|db))?|cl)\)?)?"
    r"\s*(?:[:=]\s*|\s+)"
    r"|"
    r"double[-\s]?bottom\s+height"
    r"(?:\s*(?:at\s+)?\(?(?:cl|centerline|centreline|mat\s+phang\s+doc\s+tam)\)?)?"
    r"(?:\s*\(?h(?:_?(?:db|dd))?\)?)?"
    r"\s*(?:[:=]\s*|\s+)"
    r"|"
    r"h_?(?:dd|db)(?:\s*(?:tai\s+|at\s+)?\(?(?:cl|centerline|centreline|mp\s*doc\s*tam|mpdt|mat\s+phang\s+doc\s+tam)\)?)?\s*[:=]\s*"
    r"|"
    r"(?:day\s+doi|double[-\s]?bottom)\s*(?:tai\s+|at\s+)?\(?(?:cl|centerline|centreline|mp\s*doc\s*tam|mpdt|mat\s+phang\s+doc\s+tam(?:\s+tau)?)\)?\s*[,:-]?\s*(?:chieu\s+cao\s*)?h(?:_?(?:dd|db))?\s*[:=]\s*"
    r")(?:(abt|approx)\.?\s*)?([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_BARE_UNBOUND_HEIGHT_RE = re.compile(
    r"(?:^|\b)(?:chieu\s+cao\s+)?h\s*[:=]\s*([0-9]+(?:[.,][0-9]+)?)(?![.,]?[a-z0-9])\s*(mm|cm|m)?\b"
)
_DB_CL_LABEL_RE = re.compile(
    r"\b(?:"
    r"chieu\s+cao\s+(?:cua\s+)?day\s+doi(?:\s*(?:tai\s+|o\s+)?\(?(?:cl|centerline|centreline|mp\s*doc\s*tam|mpdt|mat\s+phang\s+doc\s+tam(?:\s+tau)?)\)?)?"
    r"|"
    r"double[-\s]?bottom\s+height(?:\s*(?:at\s+)?\(?(?:cl|centerline|centreline)\)?)?"
    r"|"
    r"(?:day\s+doi|double[-\s]?bottom)\s*(?:tai\s+|at\s+)?\(?(?:cl|centerline|centreline|mp\s*doc\s*tam|mpdt|mat\s+phang\s+doc\s+tam(?:\s+tau)?)\)?"
    r"|"
    r"h_?(?:dd|db)(?:\s*(?:tai\s+|at\s+)?\(?(?:cl|centerline|centreline|mpdt|mp\s*doc\s*tam)\)?)?"
    r")\b"
)
_DB_DIM_TAG_RE = re.compile(
    r"\b(?:h_?(?:dd|db)|day\s+doi\s*(?:\(?cl\)?)?|double[-\s]?bottom\s*(?:\(?cl\)?)?|db\s+cl)\b"
)
_DB_DIM_LAYERS: frozenset[str] = frozenset(
    {"DAY_DOI_CL", "DB_CL", "DOUBLE_BOTTOM_CL", "H_DD_CL"}
)
_DB_DIM_MAX_PROXIMITY_UNITS = 3000.0

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


def _unit_value_to_mm(raw_num: str, unit: str | None, *, insunits: int = 0) -> tuple[float | None, bool]:
    val = _to_float(raw_num)
    if val is None or val <= 0:
        return None, False
    unit_norm = (unit or "").lower().strip()
    if unit_norm == "mm":
        return round(val, 4), True
    if unit_norm == "cm":
        return round(val * 10.0, 4), True
    if unit_norm == "m":
        return round(val * 1000.0, 4), True
    if insunits == 4:
        return round(val, 4), True
    if insunits == 5:
        return round(val * 10.0, 4), True
    if insunits == 6:
        return round(val * 1000.0, 4), True
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
        "entity_type": dxftype,
        "text": normalize_marine_cad_text(raw_text, font_hint=font_hint),
        "raw_text": raw_text,
        "font_hint": font_hint,
        "layer": str(getattr(entity.dxf, "layer", "0") or "0"),
        "x": round(x, 3),
        "y": round(y, 3),
        "height": round(height, 4),
    }


def _collect_dxf_texts(
    doc: Any, style_fonts: Mapping[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    texts: list[dict[str, Any]] = []
    dimensions: list[dict[str, Any]] = []
    entity_counts: dict[str, int] = {}
    referenced_blocks: dict[str, tuple[float, float]] = {}

    msp = doc.modelspace()
    for entity in msp:
        dxftype = entity.dxftype()
        entity_counts[dxftype] = entity_counts.get(dxftype, 0) + 1
        if dxftype == "DIMENSION":
            defpt = getattr(entity.dxf, "defpoint", None)
            txtmp = getattr(entity.dxf, "text_midpoint", None)
            def_x = _to_float(getattr(defpt, "x", None))
            def_y = _to_float(getattr(defpt, "y", None))
            mid_x = _to_float(getattr(txtmp, "x", None))
            mid_y = _to_float(getattr(txtmp, "y", None))
            anchor_x = mid_x if mid_x is not None else def_x
            anchor_y = mid_y if mid_y is not None else def_y
            dimensions.append(
                {
                    "handle": str(getattr(entity.dxf, "handle", "") or ""),
                    "layer": str(getattr(entity.dxf, "layer", "0") or "0"),
                    "raw_text": str(getattr(entity.dxf, "text", "") or ""),
                    "actual_measurement": _to_float(getattr(entity.dxf, "actual_measurement", None)),
                    "x": round(anchor_x, 3) if anchor_x is not None else None,
                    "y": round(anchor_y, 3) if anchor_y is not None else None,
                    "defpoint_x": round(def_x, 3) if def_x is not None else None,
                    "defpoint_y": round(def_y, 3) if def_y is not None else None,
                    "text_midpoint_x": round(mid_x, 3) if mid_x is not None else None,
                    "text_midpoint_y": round(mid_y, 3) if mid_y is not None else None,
                }
            )
            continue
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

    return texts, dimensions, entity_counts


def observe_dxf_bytes(
    data: bytes,
    *,
    drawing_id: str,
    drawing_code: str = "",
    claimed_scale: float | None = None,
    ocr_only: bool = False,
    _drawing_path: str | None = None,
) -> dict[str, Any]:
    """Read raw DXF bytes via ``dxf_builder_lib._dxf_snapshot`` into normalized observation."""
    drawing_sha256 = hashlib.sha256(data).hexdigest()
    doc, _styles = read_dxf_snapshot(data, observe_styles=True)
    style_fonts = _extract_style_font_hints(doc)
    texts, dimensions, entity_counts = _collect_dxf_texts(doc, style_fonts)

    insunits_raw = doc.header.get("$INSUNITS", 0)
    measurement_raw = doc.header.get("$MEASUREMENT", 0)
    insunits = int(insunits_raw) if isinstance(insunits_raw, (int, float)) else 0
    measurement = int(measurement_raw) if isinstance(measurement_raw, (int, float)) else 0

    return normalize_observation(
        {
            "drawing_id": drawing_id,
            "drawing_code": drawing_code,
            "drawing_path": _drawing_path,
            "drawing_sha256": drawing_sha256,
            "insunits": insunits,
            "measurement": measurement,
            "claimed_scale": claimed_scale,
            "ocr_only": bool(ocr_only),
            "source_mode": "OCR_ONLY" if ocr_only else "NATIVE_DXF_SNAPSHOT",
            "entity_counts": entity_counts,
            "texts": texts,
            "dimensions": dimensions,
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
    """Read an on-disk DXF file in bound regular-file read-only mode via ``open_bound_file``."""
    target = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd, _opened_stat = open_bound_file(target, flags=flags, label="Marine DXF")
    chunks: list[bytes] = []
    try:
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(fd)
    raw_bytes = b"".join(chunks)
    resolved_path = str(target.resolve())
    return observe_dxf_bytes(
        raw_bytes,
        drawing_id=drawing_id or target.stem,
        drawing_code=drawing_code,
        claimed_scale=claimed_scale,
        ocr_only=ocr_only,
        _drawing_path=resolved_path,
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
                "entity_type": str(item.get("entity_type") or "TEXT").upper(),
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


_SHEET_NO_RE = re.compile(
    r"\b(?:to\s+so|sheet(?:\s+no\.?)?)\s*[:=]\s*([0-9A-Za-z_-]{1,12})\b",
    re.IGNORECASE,
)
_TOTAL_SHEETS_RE = re.compile(
    r"\b(?:so\s+to|total\s+sheets?)\s*[:=]\s*([0-9A-Za-z_-]{1,12})\b",
    re.IGNORECASE,
)
_SHEET_OF_RE = re.compile(r"\bsheet\s+([0-9]{1,4})\s+of\s+([0-9]{1,4})\b", re.IGNORECASE)
_REVISION_RE = re.compile(
    r"(?:^|\b)(?:rev(?:ision)?\.?|lan\s+sua\s+doi)\s*[:=]\s*([A-Za-z0-9][A-Za-z0-9._-]{0,15})\b",
    re.IGNORECASE,
)
_ISSUE_DATE_RE = re.compile(r"^\s*((?:0?[1-9]|1[0-2])\s*/\s*(?:19|20)\d{2})\s*$")
_DESIGN_VARIANT_RE = re.compile(
    r"\b(phuong\s+an\s+[ivx0-9a-z]+|option\s+[0-9a-z]+)\b",
    re.IGNORECASE,
)
_VN_TITLE_SHIP_TYPE_RE = re.compile(
    r"^\s*(tau\s+(?:hang\s*[-–]\s*khach|hang\s*[-–]\s*thuc\s+tap|hang\s+kho|"
    r"cho\s+dau|cho\s+hoa\s+chat|cho\s+container|khach|keo|day|cong\s+trinh)|"
    r"sa\s+lan(?:\s+cho\s+[a-z]+)?)\b"
)


def _extract_sheet_and_revision(
    entries: list[dict[str, Any]],
) -> tuple[str | None, list[str], str | None, list[str], list[str], list[str]]:
    sheet_no: str | None = None
    total_sheets: str | None = None
    sheet_handles: list[str] = []
    revision: str | None = None
    revision_handles: list[str] = []
    issue_dates: list[str] = []
    design_variants: list[str] = []

    for entry in entries:
        folded = entry["folded"]
        text = entry["text"]
        m_of = _SHEET_OF_RE.search(folded)
        if m_of and sheet_no is None:
            sheet_no, total_sheets = m_of.group(1), m_of.group(2)
            _append_unique(sheet_handles, entry["handle"])
        m_sn = _SHEET_NO_RE.search(folded)
        if m_sn and sheet_no is None:
            sheet_no = m_sn.group(1).strip()
            _append_unique(sheet_handles, entry["handle"])
        m_ts = _TOTAL_SHEETS_RE.search(folded)
        if m_ts and total_sheets is None:
            total_sheets = m_ts.group(1).strip()
            _append_unique(sheet_handles, entry["handle"])
        m_rev = _REVISION_RE.search(text)
        if m_rev and revision is None:
            cand = m_rev.group(1).strip()
            if cand and cand != "?":
                revision = cand
                _append_unique(revision_handles, entry["handle"])
        m_dt = _ISSUE_DATE_RE.fullmatch(text)
        if m_dt:
            _append_unique(issue_dates, re.sub(r"\s+", "", m_dt.group(1)))
        m_var = _DESIGN_VARIANT_RE.search(folded)
        if m_var:
            _append_unique(design_variants, re.sub(r"\s+", " ", m_var.group(1)).upper())

    if sheet_no and total_sheets:
        sheet_id: str | None = f"{sheet_no}/{total_sheets}"
    elif sheet_no:
        sheet_id = sheet_no
    else:
        sheet_id = None
    return sheet_id, sheet_handles, revision, revision_handles, issue_dates, design_variants


def _nearest_right_row_match(
    label_entry: Mapping[str, Any],
    entries: list[dict[str, Any]],
    *,
    insunits: int = 0,
) -> dict[str, Any] | None:
    lx = label_entry.get("x")
    ly = label_entry.get("y")
    if lx is None or ly is None:
        return None
    h = label_entry.get("height") or 200.0
    row_items: list[tuple[float, dict[str, Any]]] = []
    for other in entries:
        if other is label_entry:
            continue
        ox = other.get("x")
        oy = other.get("y")
        if ox is None or oy is None:
            continue
        dx = ox - lx
        if dx <= 0.0 or dx > max(h * 80.0, 32000.0):
            continue
        if abs(oy - ly) > max(h * 1.8, 360.0):
            continue
        row_items.append((dx, other))
    row_items.sort(key=lambda pair: pair[0])

    qual_handles: list[str] = []
    is_approx = False
    for _dx, other in row_items:
        stripped_tok = other["folded"].strip(" .")
        if stripped_tok in {"abt", "approx", "xap xi", "khoang"}:
            _append_unique(qual_handles, other["handle"])
            is_approx = True
            continue
        m = re.fullmatch(
            r"\s*(?:(abt|approx)\.?\s*)?([0-9]+(?:[.,][0-9]+)?)\s*(mm|cm|m)?\s*",
            other["folded"],
        )
        if m:
            if m.group(1):
                is_approx = True
            val, verified = _unit_value_to_meters(m.group(2), m.group(3), insunits=insunits)
            if val is not None:
                handles = [str(label_entry["handle"]), *qual_handles, str(other["handle"])]
                raw_unit = (m.group(3) or "").lower().strip() or None
                raw_obs = f"{label_entry['text']} -> {other['text']}"
                if is_approx and "abt" not in raw_obs.lower() and "approx" not in raw_obs.lower():
                    raw_obs = f"{label_entry['text']} -> ABT. {other['text']}"
                return {
                    "val_m": val,
                    "verified": verified,
                    "raw_num": _to_float(m.group(2)),
                    "raw_unit": raw_unit,
                    "observed_raw": raw_obs,
                    "handles": handles,
                    "entity_type": str(other.get("entity_type") or label_entry.get("entity_type") or "TEXT"),
                    "layer": str(other.get("layer") or label_entry.get("layer") or "0"),
                    "is_approx": is_approx,
                }
    return None


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
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    design_length_l_m_values: list[float] = []
    loa_values: list[float] = []
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
    single_bottom_evidences: list[str] = []
    ship_types: list[str] = []
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
    raw_fact_seeds: list[dict[str, Any]] = []

    def _add_seed(
        *,
        fact_key: str,
        handles: list[str],
        entity_type: str,
        layer: str | None,
        observed_raw: str,
        observed_value: float | str | None,
        observed_unit: str | None,
        normalized_value: float | str | None,
        normalized_unit: str | None,
        unit_verified: bool = True,
        is_approx: bool = False,
        is_unbound: bool = False,
        reason_detail: str,
    ) -> None:
        raw_fact_seeds.append(
            {
                "fact_key": fact_key,
                "handles": handles,
                "entity_type": entity_type,
                "layer": layer,
                "observed_raw": observed_raw,
                "observed_value": observed_value,
                "observed_unit": observed_unit,
                "normalized_value": normalized_value if unit_verified and not is_unbound else None,
                "normalized_unit": normalized_unit if unit_verified and not is_unbound else None,
                "unit_verified": unit_verified,
                "is_approx": is_approx,
                "is_unbound": is_unbound,
                "reason_detail": reason_detail,
            }
        )

    raw_scale = _to_float(raw.get("claimed_scale"))
    if raw_scale is not None and raw_scale > 0:
        _append_unique(claimed_scales, round(raw_scale, 3))

    for entry in entries:
        text = entry["text"]
        folded = entry["folded"]
        ehandle = str(entry["handle"])
        etype = str(entry.get("entity_type") or "TEXT")
        elayer = str(entry.get("layer") or "0")

        for bad_tok in _CORRUPTED_NUMBER_RE.findall(text):
            _append_unique(corrupted_numeric_tokens, str(bad_tok).strip())

        for m in _L_DESIGN_RE.finditer(folded):
            val, verified = _unit_value_to_meters(m.group(2), m.group(3), insunits=insunits)
            if val is not None:
                is_apx = bool(m.group(1))
                if verified and not is_apx:
                    _append_unique(design_length_l_m_values, val)
                elif not verified:
                    _append_unique(unverified_unitless_particulars, f"L:{m.group(2)}")
                _add_seed(
                    fact_key="design_length_l_m",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=_to_float(m.group(2)),
                    observed_unit=(m.group(3) or "").lower() or None,
                    normalized_value=val,
                    normalized_unit="m",
                    unit_verified=verified,
                    is_approx=is_apx,
                    reason_detail=f"Regulatory design length L extracted from {etype} {ehandle}.",
                )

        loa_matched = False
        for m in _LOA_RE.finditer(folded):
            val, verified = _unit_value_to_meters(m.group(2), m.group(3), insunits=insunits)
            if val is not None:
                is_apx = bool(m.group(1)) or "abt" in folded
                if verified:
                    _append_unique(loa_values, val)
                else:
                    _append_unique(unverified_unitless_particulars, f"Loa:{m.group(2)}")
                _add_seed(
                    fact_key="loa_m",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=_to_float(m.group(2)),
                    observed_unit=(m.group(3) or "").lower() or None,
                    normalized_value=val,
                    normalized_unit="m",
                    unit_verified=verified,
                    is_approx=is_apx,
                    reason_detail=f"Length overall (Loa) extracted from {etype} {ehandle}.",
                )
                loa_matched = True
        if not loa_matched and (
            folded.startswith("length (o.a")
            or folded.startswith("length o.a")
            or folded.startswith("chieu dai lon nhat")
            or folded in {"loa", "l.o.a", "l.o.a."}
        ):
            rm = _nearest_right_row_match(entry, entries, insunits=insunits)
            if rm is not None:
                if rm["verified"]:
                    _append_unique(loa_values, rm["val_m"])
                else:
                    _append_unique(unverified_unitless_particulars, f"Loa:{rm['val_m']}")
                _add_seed(
                    fact_key="loa_m",
                    handles=rm["handles"],
                    entity_type=rm["entity_type"],
                    layer=rm["layer"],
                    observed_raw=rm["observed_raw"],
                    observed_value=rm["raw_num"],
                    observed_unit=rm["raw_unit"],
                    normalized_value=rm["val_m"],
                    normalized_unit="m",
                    unit_verified=rm["verified"],
                    is_approx=rm["is_approx"],
                    reason_detail=f"Paired table row Loa across handles {rm['handles']}.",
                )

        lpp_matched = False
        for m in _LPP_RE.finditer(folded):
            val, verified = _unit_value_to_meters(m.group(2), m.group(3), insunits=insunits)
            if val is not None:
                is_apx = bool(m.group(1))
                if verified and not is_apx:
                    _append_unique(lpp_values, val)
                elif not verified:
                    _append_unique(unverified_unitless_particulars, f"Lpp:{m.group(2)}")
                _add_seed(
                    fact_key="lpp_m",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=_to_float(m.group(2)),
                    observed_unit=(m.group(3) or "").lower() or None,
                    normalized_value=val,
                    normalized_unit="m",
                    unit_verified=verified,
                    is_approx=is_apx,
                    reason_detail=f"Length between perpendiculars (Lpp) from {etype} {ehandle}.",
                )
                lpp_matched = True
        if not lpp_matched and any(
            tok in folded for tok in ("length (l.p.p", "length (p.p", "chieu dai giua 2 tru")
        ):
            rm = _nearest_right_row_match(entry, entries, insunits=insunits)
            if rm is not None:
                if rm["verified"] and not rm["is_approx"]:
                    _append_unique(lpp_values, rm["val_m"])
                elif not rm["verified"]:
                    _append_unique(unverified_unitless_particulars, f"Lpp:{rm['val_m']}")
                _add_seed(
                    fact_key="lpp_m",
                    handles=rm["handles"],
                    entity_type=rm["entity_type"],
                    layer=rm["layer"],
                    observed_raw=rm["observed_raw"],
                    observed_value=rm["raw_num"],
                    observed_unit=rm["raw_unit"],
                    normalized_value=rm["val_m"],
                    normalized_unit="m",
                    unit_verified=rm["verified"],
                    is_approx=rm["is_approx"],
                    reason_detail=f"Paired table row Lpp across handles {rm['handles']}.",
                )

        lwl_matched = False
        for m in _LWL_RE.finditer(folded):
            val, verified = _unit_value_to_meters(m.group(2), m.group(3), insunits=insunits)
            if val is not None:
                is_apx = bool(m.group(1))
                if verified and not is_apx:
                    _append_unique(lwl_values, val)
                elif not verified:
                    _append_unique(unverified_unitless_particulars, f"Lwl:{m.group(2)}")
                _add_seed(
                    fact_key="lwl_m",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=_to_float(m.group(2)),
                    observed_unit=(m.group(3) or "").lower() or None,
                    normalized_value=val,
                    normalized_unit="m",
                    unit_verified=verified,
                    is_approx=is_apx,
                    reason_detail=f"Waterline length (Lwl) from {etype} {ehandle}.",
                )
                lwl_matched = True
        if not lwl_matched and (folded.startswith("length (w.l") or folded.startswith("chieu dai duong nuoc")):
            rm = _nearest_right_row_match(entry, entries, insunits=insunits)
            if rm is not None:
                if rm["verified"] and not rm["is_approx"]:
                    _append_unique(lwl_values, rm["val_m"])
                elif not rm["verified"]:
                    _append_unique(unverified_unitless_particulars, f"Lwl:{rm['val_m']}")
                _add_seed(
                    fact_key="lwl_m",
                    handles=rm["handles"],
                    entity_type=rm["entity_type"],
                    layer=rm["layer"],
                    observed_raw=rm["observed_raw"],
                    observed_value=rm["raw_num"],
                    observed_unit=rm["raw_unit"],
                    normalized_value=rm["val_m"],
                    normalized_unit="m",
                    unit_verified=rm["verified"],
                    is_approx=rm["is_approx"],
                    reason_detail=f"Paired table row Lwl across handles {rm['handles']}.",
                )

        b_matched = False
        for m in _BREADTH_RE.finditer(folded):
            val, verified = _unit_value_to_meters(m.group(1), m.group(2), insunits=insunits)
            if val is not None:
                if verified:
                    _append_unique(breadth_values, val)
                else:
                    _append_unique(unverified_unitless_particulars, f"B:{m.group(1)}")
                _add_seed(
                    fact_key="breadth_m",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=_to_float(m.group(1)),
                    observed_unit=(m.group(2) or "").lower() or None,
                    normalized_value=val,
                    normalized_unit="m",
                    unit_verified=verified,
                    reason_detail=f"Molded breadth B from {etype} {ehandle}.",
                )
                b_matched = True
        if not b_matched and (folded.startswith("breadth") or folded.startswith("chieu rong")):
            rm = _nearest_right_row_match(entry, entries, insunits=insunits)
            if rm is not None:
                if rm["verified"] and not rm["is_approx"]:
                    _append_unique(breadth_values, rm["val_m"])
                elif not rm["verified"]:
                    _append_unique(unverified_unitless_particulars, f"B:{rm['val_m']}")
                _add_seed(
                    fact_key="breadth_m",
                    handles=rm["handles"],
                    entity_type=rm["entity_type"],
                    layer=rm["layer"],
                    observed_raw=rm["observed_raw"],
                    observed_value=rm["raw_num"],
                    observed_unit=rm["raw_unit"],
                    normalized_value=rm["val_m"],
                    normalized_unit="m",
                    unit_verified=rm["verified"],
                    is_approx=rm["is_approx"],
                    reason_detail=f"Paired table row Breadth B across handles {rm['handles']}.",
                )

        d_matched = False
        for m in _DEPTH_RE.finditer(folded):
            val, verified = _unit_value_to_meters(m.group(1), m.group(2), insunits=insunits)
            if val is not None:
                if verified:
                    _append_unique(depth_values, val)
                else:
                    _append_unique(unverified_unitless_particulars, f"D:{m.group(1)}")
                _add_seed(
                    fact_key="depth_m",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=_to_float(m.group(1)),
                    observed_unit=(m.group(2) or "").lower() or None,
                    normalized_value=val,
                    normalized_unit="m",
                    unit_verified=verified,
                    reason_detail=f"Molded depth D from {etype} {ehandle}.",
                )
                d_matched = True
        if not d_matched and (folded.startswith("depth") or folded.startswith("chieu cao man")):
            rm = _nearest_right_row_match(entry, entries, insunits=insunits)
            if rm is not None:
                if rm["verified"] and not rm["is_approx"]:
                    _append_unique(depth_values, rm["val_m"])
                elif not rm["verified"]:
                    _append_unique(unverified_unitless_particulars, f"D:{rm['val_m']}")
                _add_seed(
                    fact_key="depth_m",
                    handles=rm["handles"],
                    entity_type=rm["entity_type"],
                    layer=rm["layer"],
                    observed_raw=rm["observed_raw"],
                    observed_value=rm["raw_num"],
                    observed_unit=rm["raw_unit"],
                    normalized_value=rm["val_m"],
                    normalized_unit="m",
                    unit_verified=rm["verified"],
                    is_approx=rm["is_approx"],
                    reason_detail=f"Paired table row Depth D across handles {rm['handles']}.",
                )

        draft_matched = False
        for m in _DRAFT_RE.finditer(text if "T" in text else folded):
            raw_num = m.group(1) or m.group(3)
            raw_unit = m.group(2) if m.group(1) else m.group(4)
            if raw_num:
                val, verified = _unit_value_to_meters(raw_num, raw_unit, insunits=insunits)
                if val is not None:
                    if verified:
                        _append_unique(draft_values, val)
                    else:
                        _append_unique(unverified_unitless_particulars, f"T:{raw_num}")
                    _add_seed(
                        fact_key="draft_m",
                        handles=[ehandle],
                        entity_type=etype,
                        layer=elayer,
                        observed_raw=text,
                        observed_value=_to_float(raw_num),
                        observed_unit=(raw_unit or "").lower() or None,
                        normalized_value=val,
                        normalized_unit="m",
                        unit_verified=verified,
                        reason_detail=f"Design draft T from {etype} {ehandle}.",
                    )
                    draft_matched = True
        if not draft_matched and (
            folded.startswith("draft")
            or folded.startswith("draught")
            or folded.startswith("chieu chim")
            or folded.startswith("mon nuoc")
        ):
            rm = _nearest_right_row_match(entry, entries, insunits=insunits)
            if rm is not None:
                if rm["verified"] and not rm["is_approx"]:
                    _append_unique(draft_values, rm["val_m"])
                elif not rm["verified"]:
                    _append_unique(unverified_unitless_particulars, f"T:{rm['val_m']}")
                _add_seed(
                    fact_key="draft_m",
                    handles=rm["handles"],
                    entity_type=rm["entity_type"],
                    layer=rm["layer"],
                    observed_raw=rm["observed_raw"],
                    observed_value=rm["raw_num"],
                    observed_unit=rm["raw_unit"],
                    normalized_value=rm["val_m"],
                    normalized_unit="m",
                    unit_verified=rm["verified"],
                    is_approx=rm["is_approx"],
                    reason_detail=f"Paired table row Draft T across handles {rm['handles']}.",
                )

        eng_match = _ENGINE_RE.search(text)
        if eng_match:
            rhs = re.sub(r"\s+", " ", eng_match.group(1)).strip(" :-=")
            if rhs and rhs != "?":
                _append_unique(main_engines, rhs)
                _add_seed(
                    fact_key="main_engine",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=rhs,
                    observed_unit=None,
                    normalized_value=rhs,
                    normalized_unit=None,
                    reason_detail=f"Main engine specification from {etype} {ehandle}.",
                )

        for hull_m in _HULL_NO_RE.finditer(text):
            hno = hull_m.group(1).strip()
            if hno and hno != "?":
                _append_unique(hull_nos, hno)
                _add_seed(
                    fact_key="hull_no",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=hno,
                    observed_unit=None,
                    normalized_value=hno.upper(),
                    normalized_unit=None,
                    reason_detail=f"Hull / yard number from {etype} {ehandle}.",
                )

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
                _add_seed(
                    fact_key="class_notation",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=tag,
                    observed_unit=None,
                    normalized_value=tag,
                    normalized_unit=None,
                    reason_detail=f"Inland class notation {tag} from {etype} {ehandle}.",
                )
            for m in _EXPLICIT_CAP_RE.finditer(clause_clean):
                tag = f"VR-{m.group(1).upper()}"
                _append_unique(class_notations, tag)
                _append_unique(service_areas, "INLAND_WATERWAY")
                _add_seed(
                    fact_key="class_notation",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=tag,
                    observed_unit=None,
                    normalized_value=tag,
                    normalized_unit=None,
                    reason_detail=f"Explicit class notation {tag} from {etype} {ehandle}.",
                )

            if any(tok in clause_clean for tok in ("thuy noi dia", "qcvn 72")):
                _append_unique(service_areas, "INLAND_WATERWAY")
                _add_seed(
                    fact_key="service_area",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value="INLAND_WATERWAY",
                    observed_unit=None,
                    normalized_value="INLAND_WATERWAY",
                    normalized_unit=None,
                    reason_detail=f"Inland waterway marker from {etype} {ehandle}.",
                )
            if any(
                tok in clause_clean
                for tok in ("ocean going", "vien duong", "tau bien", "qcvn 21", "unrestricted service")
            ) or re.search(r"\bvrh\b", clause_clean):
                _append_unique(service_areas, "OCEAN_GOING")
                _add_seed(
                    fact_key="service_area",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value="OCEAN_GOING",
                    observed_unit=None,
                    normalized_value="OCEAN_GOING",
                    normalized_unit=None,
                    reason_detail=f"Ocean-going service marker from {etype} {ehandle}.",
                )

            if re.search(r"\bqcvn\s*21(?:\s*[:/]\s*\d{4})?\b", clause_clean):
                _append_unique(explicit_exclusion_evidences, "STATUTORY_QCVN_21_SEA_SHIP")
            if re.search(r"(?:^|[^a-z0-9])\*?\s*vrh\b", clause_clean) or re.search(
                r"\b(?:class|classification|cap\s+tau)\s*[:=]\s*\*?(?:vrh|dnv|abs|nk|lr|bv|rina|ccs|kr)\b",
                clause_clean,
            ) or re.search(r"\b(?:dnv\s*\+?1a1|solas|iacs)\b", clause_clean):
                _append_unique(explicit_exclusion_evidences, "STATUTORY_SEA_CLASS_NOTATION")

            is_lifeboat_item = "xuong cuu sinh" in clause_clean or "lifeboat" in clause_clean
            if not is_lifeboat_item:
                if re.search(r"\bqcvn\s*25(?:\s*[:/]\s*\d{4})?\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_1_QCVN_25_SMALL_CRAFT")
                if re.search(r"\b(?:qcvn\s*50|tau\s+the\s+thao|vui\s+choi\s+giai\s+tri|leisure\s+craft)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_2_QCVN_50_LEISURE")
                if re.search(r"\b(?:qcvn\s*51|ferrocement|xi\s+mang\s+luoi\s+thep)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_2_QCVN_51_FERROCEMENT")
                if re.search(r"\b(?:qcvn\s*56|frp|chat\s+deo\s+cot\s+soi\s+thuy\s+tinh)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_2_QCVN_56_FRP")
                if re.search(r"\b(?:qcvn\s*84|tau\s+vo\s+go|tau\s+go|wooden\s+hull|wooden\s+craft)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_2_QCVN_84_WOOD")
                if re.search(r"\b(?:qcvn\s*54|high[-\s]?speed\s+craft|tau\s+cao\s+toc)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_2_QCVN_54_HSC")
                if re.search(r"\b(?:qcvn\s*55|floating\s+dock|u\s+noi)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_2_QCVN_55_DOCK")
                if re.search(r"\b(?:tau\s+quoc\s+phong|quoc\s+phong|an\s+ninh|defense\s+vessel|security\s+vessel)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_4_DEFENSE_SECURITY")
                if re.search(r"\b(?:tau\s+ca|fishing\s+vessel)\b", clause_clean):
                    _append_unique(explicit_exclusion_evidences, "STATUTORY_CLAUSE_1_1_4_FISHING_VESSEL")
                if _SINGLE_BOTTOM_RE.search(clause_clean):
                    _append_unique(single_bottom_evidences, text)
                    _add_seed(
                        fact_key="hull_bottom_configuration",
                        handles=[ehandle],
                        entity_type=etype,
                        layer=elayer,
                        observed_raw=text,
                        observed_value="SINGLE_BOTTOM",
                        observed_unit=None,
                        normalized_value="SINGLE_BOTTOM",
                        normalized_unit=None,
                        reason_detail=f"Single-bottom hull declaration from {etype} {ehandle}.",
                    )

        ship_m = _SHIP_TYPE_RE.search(folded)
        if ship_m:
            stype = ship_m.group(1).strip().upper()
            if stype:
                _append_unique(ship_types, stype)
                _add_seed(
                    fact_key="ship_type",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=stype,
                    observed_unit=None,
                    normalized_value=stype,
                    normalized_unit=None,
                    reason_detail=f"Ship type declaration from {etype} {ehandle}.",
                )
        elif "tau hang kho" in folded or "dry cargo" in folded:
            _append_unique(ship_types, "DRY CARGO")
            _add_seed(
                fact_key="ship_type",
                handles=[ehandle],
                entity_type=etype,
                layer=elayer,
                observed_raw=text,
                observed_value="DRY CARGO",
                observed_unit=None,
                normalized_value="DRY CARGO",
                normalized_unit=None,
                reason_detail=f"Dry-cargo ship type marker from {etype} {ehandle}.",
            )
        else:
            vn_st = _VN_TITLE_SHIP_TYPE_RE.search(folded)
            if vn_st:
                vn_norm = re.sub(r"\s*[-–]\s*", " - ", re.sub(r"\s+", " ", vn_st.group(1)).strip()).upper()
                _append_unique(ship_types, vn_norm)
                _add_seed(
                    fact_key="ship_type",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=vn_norm,
                    observed_unit=None,
                    normalized_value=vn_norm,
                    normalized_unit=None,
                    reason_detail=f"Title-block Vietnamese vessel type '{vn_norm}' from {etype} {ehandle}.",
                )

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
                    pkey = "plate_thickness_mm"
                    if any(tok in folded for tok in ("ton day", "bottom", "keel")):
                        bottom_plate_mm.append(rounded)
                        pkey = "bottom_plate_thickness_mm"
                    if any(tok in folded for tok in ("ton hong", "ton ha ma", "bilge")):
                        bilge_plate_mm.append(rounded)
                        pkey = "bilge_plate_thickness_mm"
                    _add_seed(
                        fact_key=pkey,
                        handles=[ehandle],
                        entity_type=etype,
                        layer=elayer,
                        observed_raw=text,
                        observed_value=rounded,
                        observed_unit="mm",
                        normalized_value=rounded,
                        normalized_unit="mm",
                        reason_detail=f"Component-bound hull plate thickness ({pkey}) from {etype} {ehandle}.",
                    )
                else:
                    unbound_plate_mm.append(rounded)
                    _add_seed(
                        fact_key="unbound_plate_thickness_mm",
                        handles=[ehandle],
                        entity_type=etype,
                        layer=elayer,
                        observed_raw=text,
                        observed_value=rounded,
                        observed_unit="mm",
                        normalized_value=None,
                        normalized_unit=None,
                        is_unbound=True,
                        reason_detail=(
                            f"Unbound CAD text '{text}' on {etype} {ehandle} lacks bottom/bilge/hull structural label."
                        ),
                    )

        db_matched_entry = False
        for m_side in _DB_SIDE_HEIGHT_RE.finditer(folded):
            raw_side = _to_float(m_side.group(1))
            if raw_side is not None and raw_side > 0:
                db_matched_entry = True
                _add_seed(
                    fact_key="unbound_double_bottom_height_mm",
                    handles=[ehandle],
                    entity_type=etype,
                    layer=elayer,
                    observed_raw=text,
                    observed_value=round(raw_side, 4),
                    observed_unit=(m_side.group(2) or "").lower() or None,
                    normalized_value=None,
                    normalized_unit=None,
                    is_unbound=True,
                    reason_detail=(
                        f"Non-centerline side/margin height '{text}' on {etype} {ehandle}: "
                        "QCVN 72 Clause 2.4.3-2 requires double-bottom height measured at centerline "
                        "(mặt phẳng dọc tâm tàu / CL), not at side/margin."
                    ),
                )

        if not db_matched_entry:
            for m_db in _DB_HEIGHT_INLINE_RE.finditer(folded):
                val_mm, verified_mm = _unit_value_to_mm(m_db.group(2), m_db.group(3), insunits=insunits)
                if val_mm is not None:
                    db_matched_entry = True
                    raw_num_db = _to_float(m_db.group(2))
                    raw_unit_db = (m_db.group(3) or "").lower() or None
                    if _DB_NON_CENTERLINE_CTX_RE.search(folded):
                        _add_seed(
                            fact_key="unbound_double_bottom_height_mm",
                            handles=[ehandle],
                            entity_type=etype,
                            layer=elayer,
                            observed_raw=text,
                            observed_value=raw_num_db,
                            observed_unit=raw_unit_db,
                            normalized_value=None,
                            normalized_unit=None,
                            is_unbound=True,
                            reason_detail=(
                                f"Non-centerline double-bottom height '{text}' on {etype} {ehandle}: "
                                "QCVN 72 Clause 2.4.3-2 requires measurement at centerline "
                                "(mặt phẳng dọc tâm tàu / CL), not at side/margin."
                            ),
                        )
                    else:
                        _add_seed(
                            fact_key="double_bottom_height_mm",
                            handles=[ehandle],
                            entity_type=etype,
                            layer=elayer,
                            observed_raw=text,
                            observed_value=raw_num_db,
                            observed_unit=raw_unit_db,
                            normalized_value=val_mm,
                            normalized_unit="mm",
                            unit_verified=verified_mm,
                            is_approx=bool(m_db.group(1)),
                            reason_detail=(
                                f"Centerline double-bottom height extracted from {etype} {ehandle} "
                                "(QCVN 72 Clause 2.4.3-2)."
                            ),
                        )

        if not db_matched_entry and not any(
            tok in folded for tok in ("day doi", "double bottom", "double-bottom")
        ):
            for m_ub in _BARE_UNBOUND_HEIGHT_RE.finditer(folded):
                raw_ub = _to_float(m_ub.group(1))
                if raw_ub is not None and raw_ub > 0:
                    _add_seed(
                        fact_key="unbound_double_bottom_height_mm",
                        handles=[ehandle],
                        entity_type=etype,
                        layer=elayer,
                        observed_raw=text,
                        observed_value=round(raw_ub, 4),
                        observed_unit=(m_ub.group(2) or "").lower() or None,
                        normalized_value=None,
                        normalized_unit=None,
                        is_unbound=True,
                        reason_detail=(
                            f"Unbound CAD height annotation '{text}' on {etype} {ehandle} lacks explicit "
                            "double-bottom (đáy đôi / double bottom) structural context."
                        ),
                    )

    return (
        {
            "design_length_l_m_values": design_length_l_m_values,
            "loa_m_values": loa_values,
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
            "single_bottom_evidences": single_bottom_evidences,
            "ship_types": ship_types,
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
        },
        raw_fact_seeds,
    )


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
        copied = deepcopy(dict(raw))
        existing_facts = copied.get("engineering_facts", [])
        if not isinstance(existing_facts, list):
            raise MarineKnowledgeError("FACT_SCHEMA_INVALID")
        copied["engineering_facts"] = [validate_engineering_fact(f) for f in existing_facts]
        return copied

    drawing_id = str(raw.get("drawing_id") or "UNSPECIFIED_DRAWING").strip()
    entries = _normalize_text_entries(raw.get("texts", []))
    drawing_code = _infer_drawing_code(raw.get("drawing_code"), entries)
    insunits = int(raw["insunits"]) if isinstance(raw.get("insunits"), int) else 0
    measurement = int(raw["measurement"]) if isinstance(raw.get("measurement"), int) else 0

    sheet_id, sheet_handles, revision, revision_handles, issue_dates, design_variants = _extract_sheet_and_revision(entries)
    if revision is None and isinstance(raw.get("revision"), str) and raw["revision"].strip():
        revision = raw["revision"].strip()
    if sheet_id is None and isinstance(raw.get("sheet_id"), str) and raw["sheet_id"].strip():
        sheet_id = raw["sheet_id"].strip()

    raw_dsha = raw.get("drawing_sha256")
    drawing_sha256 = (
        raw_dsha.strip().lower()
        if isinstance(raw_dsha, str) and len(raw_dsha.strip()) == 64
        else None
    )
    raw_dpath = raw.get("drawing_path")
    drawing_path = str(raw_dpath) if isinstance(raw_dpath, str) and raw_dpath.strip() else None

    particulars, raw_fact_seeds = _extract_particulars(entries, raw, insunits=insunits)
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
    raw_dims_in = raw.get("dimensions")
    dimensions: list[dict[str, Any]] = []
    if isinstance(raw_dims_in, list):
        for d_item in raw_dims_in:
            if isinstance(d_item, Mapping):
                dimensions.append(
                    {
                        "handle": str(d_item.get("handle") or ""),
                        "layer": str(d_item.get("layer") or "0"),
                        "raw_text": str(d_item.get("raw_text") or ""),
                        "actual_measurement": _to_float(d_item.get("actual_measurement")),
                        "x": _to_float(d_item.get("x")),
                        "y": _to_float(d_item.get("y")),
                        "defpoint_x": _to_float(d_item.get("defpoint_x")),
                        "defpoint_y": _to_float(d_item.get("defpoint_y")),
                        "text_midpoint_x": _to_float(d_item.get("text_midpoint_x")),
                        "text_midpoint_y": _to_float(d_item.get("text_midpoint_y")),
                    }
                )

    observed_handles = [entry["handle"] for entry in entries if entry.get("handle")]
    for dim_rec in dimensions:
        if dim_rec["handle"] and dim_rec["handle"] not in observed_handles:
            observed_handles.append(dim_rec["handle"])

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
        ("loa_m", "loa_m_values"),
        ("lpp_m", "lpp_m_values"),
        ("lwl_m", "lwl_m_values"),
        ("breadth_m", "breadth_m_values"),
        ("depth_m", "depth_m_values"),
        ("draft_m", "draft_m_values"),
        ("main_engine", "main_engine_values"),
    ):
        if p_key not in metric_provenance and particulars.get(p_list_key):
            metric_provenance[p_key] = "UNVERIFIED_OCR_TEXT" if is_ocr else "NATIVE_CAD_TEXT"

    has_native_dxf = (not is_ocr) and (drawing_sha256 is not None) and (source_mode.upper() == "NATIVE_DXF_SNAPSHOT")
    engineering_facts: list[dict[str, Any]] = []
    seen_fact_shas: set[str] = set()

    def _append_fact(fact: dict[str, Any]) -> None:
        if fact["fact_sha256"] not in seen_fact_shas:
            seen_fact_shas.add(fact["fact_sha256"])
            engineering_facts.append(fact)

    for seed in raw_fact_seeds:
        if is_ocr:
            prov_cls = "OCR_ONLY"
            v_state = "UNVERIFIED_OCR"
            reason = f"OCR_ONLY input: {seed['reason_detail']} Cannot verify CAD accuracy."
        elif seed["is_unbound"]:
            if has_native_dxf:
                prov_cls = "NATIVE_CAD_UNBOUND_TEXT"
                v_state = "UNVERIFIED_UNBOUND_TEXT"
                reason = seed["reason_detail"]
            else:
                prov_cls = "FIXTURE_SUPPLIED"
                v_state = "FIXTURE_UNBOUND_TO_DXF_BYTES"
                reason = f"Fixture-supplied unbound text without DXF bytes: {seed['reason_detail']}"
        elif has_native_dxf:
            prov_cls = "NATIVE_CAD_EVIDENCE"
            if not seed["unit_verified"]:
                v_state = "UNVERIFIED_UNITLESS"
                reason = f"Unitless drawing ($INSUNITS={insunits}) without explicit unit: {seed['reason_detail']}"
            elif seed["is_approx"]:
                v_state = "PROVISIONAL_APPROXIMATE"
                reason = f"Marked approximate (ABT./APPROX.) on CAD entity: {seed['reason_detail']}"
            else:
                v_state = "VERIFIED"
                reason = f"Bound native CAD entity evidence (sha256={drawing_sha256[:12]}): {seed['reason_detail']}"
        else:
            prov_cls = "FIXTURE_SUPPLIED"
            if not seed["unit_verified"]:
                v_state = "UNVERIFIED_UNITLESS"
                reason = f"Fixture-supplied unitless value ($INSUNITS={insunits}): {seed['reason_detail']}"
            elif seed["is_approx"]:
                v_state = "PROVISIONAL_APPROXIMATE"
                reason = f"Fixture-supplied approximate value: {seed['reason_detail']}"
            else:
                v_state = "FIXTURE_UNBOUND_TO_DXF_BYTES"
                reason = f"Structured fixture input without raw DXF SHA-256 bytes: {seed['reason_detail']}"

        _append_fact(
            build_engineering_fact(
                domain="marine",
                drawing_id=drawing_id,
                drawing_path=drawing_path,
                drawing_sha256=drawing_sha256,
                sheet_id=sheet_id,
                revision=revision,
                fact_key=seed["fact_key"],
                entity_handles=seed["handles"],
                entity_type=seed["entity_type"],
                layer=seed["layer"],
                observed_raw=seed["observed_raw"],
                observed_value=seed["observed_value"],
                observed_unit=seed["observed_unit"],
                normalized_value=seed["normalized_value"] if not is_ocr else None,
                normalized_unit=seed["normalized_unit"] if not is_ocr else None,
                provenance_class=prov_cls,
                verification_state=v_state,
                trust_reason=reason,
            )
        )

    if isinstance(raw_metrics, Mapping):
        for m_key, m_val in raw_metrics.items():
            if not isinstance(m_val, (int, float)) or isinstance(m_val, bool):
                continue
            fval = float(m_val)
            if not math.isfinite(fval):
                continue
            m_unit = "mm" if m_key.endswith("_mm") else "count"
            m_prov_raw = metric_provenance.get(m_key, "")
            if is_ocr or m_prov_raw == "UNVERIFIED_OCR_TEXT":
                _append_fact(
                    build_engineering_fact(
                        domain="marine",
                        drawing_id=drawing_id,
                        drawing_path=drawing_path,
                        drawing_sha256=drawing_sha256,
                        sheet_id=sheet_id,
                        revision=revision,
                        fact_key=str(m_key),
                        entity_handles=[],
                        entity_type="NONE",
                        layer=None,
                        observed_raw=f"{m_key}={fval}",
                        observed_value=fval,
                        observed_unit=m_unit,
                        normalized_value=None,
                        normalized_unit=None,
                        provenance_class="OCR_ONLY",
                        verification_state="UNVERIFIED_OCR",
                        trust_reason=f"Metric {m_key} originated from unverified OCR text.",
                    )
                )
            else:
                _append_fact(
                    build_engineering_fact(
                        domain="marine",
                        drawing_id=drawing_id,
                        drawing_path=drawing_path,
                        drawing_sha256=drawing_sha256,
                        sheet_id=sheet_id,
                        revision=revision,
                        fact_key=str(m_key),
                        entity_handles=[],
                        entity_type="NONE",
                        layer=None,
                        observed_raw=f"{m_key}={fval}",
                        observed_value=fval,
                        observed_unit=m_unit,
                        normalized_value=fval,
                        normalized_unit=m_unit,
                        provenance_class="FIXTURE_SUPPLIED",
                        verification_state="FIXTURE_UNBOUND_TO_DXF_BYTES",
                        trust_reason=f"Metric {m_key} supplied directly in observation payload without CAD handle binding.",
                    )
                )

    for dim_rec in dimensions:
        _append_fact(
            evaluate_dimension_fact(
                dim_rec,
                drawing_id=drawing_id,
                drawing_path=drawing_path,
                drawing_sha256=drawing_sha256,
                sheet_id=sheet_id,
                revision=revision,
                insunits=insunits,
                calibration_verified=False,
                verified_scale_to_mm=None,
                ocr_only=is_ocr,
            )
        )

    for db_dim_fact in _build_double_bottom_dimension_facts(
        entries=entries,
        dimensions=dimensions,
        drawing_id=drawing_id,
        drawing_path=drawing_path,
        drawing_sha256=drawing_sha256,
        sheet_id=sheet_id,
        revision=revision,
        insunits=insunits,
        calibration_verified=False,
        verified_scale_to_mm=None,
        ocr_only=is_ocr,
    ):
        _append_fact(db_dim_fact)

    drawing_evidence = {
        "drawing_id": drawing_id,
        "drawing_path": drawing_path,
        "drawing_sha256": drawing_sha256,
        "sheet_id": sheet_id,
        "sheet_handles": sheet_handles,
        "revision": revision,
        "revision_handles": revision_handles,
        "issue_dates": issue_dates,
        "design_variants": design_variants,
        "source_mode": source_mode,
        "insunits": insunits,
        "calibration_verified": insunits in {4, 5, 6},
        "fact_count": len(engineering_facts),
    }

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
        "texts": entries,
        "dimensions": dimensions,
        "drawing_evidence": drawing_evidence,
        "engineering_facts": engineering_facts,
        "particulars": particulars,
        "structural_metrics": structural_metrics,
        "metric_provenance": metric_provenance,
        "min_plate_from_unbound_text": min_plate_from_unbound_text,
        "blank_fields": blank_fields,
        "text_heights": text_heights,
    }


def _dim_anchor_points(dim_rec: Mapping[str, Any]) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for kx, ky in (
        ("text_midpoint_x", "text_midpoint_y"),
        ("defpoint_x", "defpoint_y"),
        ("x", "y"),
    ):
        px = _to_float(dim_rec.get(kx))
        py = _to_float(dim_rec.get(ky))
        if px is not None and py is not None:
            pair = (px, py)
            if pair not in pts:
                pts.append(pair)
    return pts


def _build_double_bottom_dimension_facts(
    *,
    entries: list[dict[str, Any]],
    dimensions: list[dict[str, Any]],
    drawing_id: str,
    drawing_path: str | None,
    drawing_sha256: str | None,
    sheet_id: str | None,
    revision: str | None,
    insunits: int,
    calibration_verified: bool,
    verified_scale_to_mm: float | None,
    ocr_only: bool,
) -> list[dict[str, Any]]:
    if not dimensions:
        return []

    cl_labels: list[dict[str, Any]] = []
    for entry in entries:
        folded = str(entry.get("folded") or "")
        if not folded or re.search(r"\d", folded):
            continue
        if _DB_NON_CENTERLINE_CTX_RE.search(folded) or _NEGATED_SCOPE_RE.search(folded):
            continue
        if _DB_CL_LABEL_RE.search(folded):
            cl_labels.append(entry)

    out_facts: list[dict[str, Any]] = []
    for dim_rec in dimensions:
        dim_handle = str(dim_rec.get("handle") or "").strip() or "UNKNOWN_DIM"
        dim_layer = str(dim_rec.get("layer") or "0").strip() or "0"
        dim_layer_norm = re.sub(r"[\s-]+", "_", dim_layer.upper())
        vis_folded = fold_marine_search_text(strip_mtext_formatting(str(dim_rec.get("raw_text") or "")))
        tagged_in_text = bool(_DB_DIM_TAG_RE.search(vis_folded)) and not bool(
            _DB_NON_CENTERLINE_CTX_RE.search(vis_folded)
        )
        tagged_by_layer = dim_layer_norm in _DB_DIM_LAYERS

        nearest_label: dict[str, Any] | None = None
        best_dist = _DB_DIM_MAX_PROXIMITY_UNITS + 1.0
        dim_pts = _dim_anchor_points(dim_rec)
        if dim_pts and cl_labels:
            for lbl in cl_labels:
                lx = _to_float(lbl.get("x"))
                ly = _to_float(lbl.get("y"))
                if lx is None or ly is None:
                    continue
                dist = min(math.hypot(lx - px, ly - py) for px, py in dim_pts)
                if dist <= _DB_DIM_MAX_PROXIMITY_UNITS and dist < best_dist:
                    best_dist = dist
                    nearest_label = lbl

        if nearest_label is None and not tagged_in_text and not tagged_by_layer:
            continue

        base_fact = evaluate_dimension_fact(
            dim_rec,
            drawing_id=drawing_id,
            drawing_path=drawing_path,
            drawing_sha256=drawing_sha256,
            sheet_id=sheet_id,
            revision=revision,
            insunits=insunits,
            calibration_verified=calibration_verified,
            verified_scale_to_mm=verified_scale_to_mm,
            ocr_only=ocr_only,
        )
        if nearest_label is not None:
            handles = [str(nearest_label["handle"]), dim_handle]
            obs_raw = f"{nearest_label['text']} -> {base_fact['observed_raw']}"
            binding_note = (
                f"Paired centerline double-bottom label {nearest_label['handle']} "
                f"(dist={best_dist:.1f} CAD units) with DIMENSION {dim_handle}: "
            )
        else:
            handles = [dim_handle]
            obs_raw = str(base_fact["observed_raw"])
            binding_note = f"Bound centerline double-bottom DIMENSION {dim_handle} on layer {dim_layer}: "

        out_facts.append(
            build_engineering_fact(
                domain="marine",
                drawing_id=drawing_id,
                drawing_path=drawing_path,
                drawing_sha256=drawing_sha256,
                sheet_id=sheet_id,
                revision=revision,
                fact_key="double_bottom_height_mm",
                entity_handles=handles,
                entity_type="DIMENSION",
                layer=base_fact["layer"],
                observed_raw=obs_raw,
                observed_value=base_fact["observed_value"],
                observed_unit=base_fact["observed_unit"],
                normalized_value=base_fact["normalized_value"],
                normalized_unit=base_fact["normalized_unit"],
                provenance_class=base_fact["provenance_class"],
                verification_state=base_fact["verification_state"],
                trust_reason=f"{binding_note}{base_fact['trust_reason']}",
            )
        )
    return out_facts


def rebind_double_bottom_dimension_facts(
    obs: Mapping[str, Any],
    *,
    calibration_verified: bool = False,
    verified_scale_to_mm: float | None = None,
) -> dict[str, Any]:
    """Re-attach centerline double-bottom DIMENSION facts after dimension calibration rebinding."""
    if type(calibration_verified) is not bool:
        raise MarineKnowledgeError("CALIBRATION_FLAG_INVALID")
    out = deepcopy(dict(obs))
    raw_dims = out.get("dimensions", [])
    raw_texts = out.get("texts", [])
    if not isinstance(raw_dims, list) or not raw_dims or not isinstance(raw_texts, list):
        return out
    ev = out.get("drawing_evidence") or {}
    existing = [
        validate_engineering_fact(f)
        for f in out.get("engineering_facts", [])
        if not (f.get("fact_key") == "double_bottom_height_mm" and f.get("entity_type") == "DIMENSION")
    ]
    rebound_db_dims = _build_double_bottom_dimension_facts(
        entries=list(raw_texts),
        dimensions=list(raw_dims),
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
    seen_shas = {f["fact_sha256"] for f in existing}
    for db_fact in rebound_db_dims:
        if db_fact["fact_sha256"] not in seen_shas:
            seen_shas.add(db_fact["fact_sha256"])
            existing.append(db_fact)
    out["engineering_facts"] = existing
    if isinstance(out.get("drawing_evidence"), dict):
        out["drawing_evidence"]["fact_count"] = len(existing)
    return out


__all__ = [
    "normalize_observation",
    "observe_dxf_bytes",
    "observe_dxf_file",
    "rebind_double_bottom_dimension_facts",
]
