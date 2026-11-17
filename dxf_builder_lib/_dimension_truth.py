"""Deterministic DXF DIMENSION truth, style-visibility, and rendered-block checks.

Adapted from the pure-Python MIT leaf logic of `U-C4N/Autocad-MCP`
(`backends/entity_fields.py`, `engineering/dimtext.py`,
`engineering/understand/labels.py`) with zero external runtime dependencies
beyond `ezdxf` and the Python standard library.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Mapping

DIAMETER_SIGN = "\u00d8"
DIAMETER_SIGNS = "\u00d8\u00f8\u2205\u2300"
RADIUS_SIGN = "R"

_LINEAR_OR_RADIAL_TYPES = frozenset({0, 1, 3, 4, 6})
_ANGULAR_TYPES = frozenset({2, 5})
_ARG_CODES = frozenset("fFHWQTACcp")
_TOGGLE_CODES = frozenset("LlOoKkN")
_PERCENT_CHARS = {"c": DIAMETER_SIGN, "d": "\u00b0", "p": "\u00b1"}
_CARET_CHARS = {"J": "\n", "M": "\n", "I": "\t", " ": "^"}

_UNICODE_ESCAPE = re.compile(r"\\[Uu]\+([0-9A-Fa-f]{4})")
_PERCENT_CODE = re.compile(r"%%(\d{3}|[cdpCDP]|[uoUOkK])")
_CARET = re.compile(r"\^([JMI ])")
_NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
_COUNT_PREFIX_RE = re.compile(rf"^\s*\d+\s*[xX\u00d7]\s*(?=[{DIAMETER_SIGNS}MR]|\s+[\d{DIAMETER_SIGNS}MR])")

_DEFAULTS: dict[str, object] = {
    "dimdec": 2,
    "dimrnd": 0.0,
    "dimzin": 8,
    "dimdsep": ".",
    "dimpost": "",
    "dimlfac": 1.0,
    "dimadec": 2,
    "dimazin": 2,
    "dimaunit": 0,
    "dimalt": 0,
    "dimtol": 0,
    "dimlim": 0,
    "dimtxt": 2.5,
}


@dataclass(frozen=True)
class DimensionDisplay:
    """Resolved displayed string and claimed numeric value for one DIMENSION."""

    text: str | None
    value: float | None
    scaled_value: float | None
    tolerance: float
    source: str


def plain_cad_text(text: str | None) -> str:
    """Decode AutoCAD control escapes and strip MTEXT formatting codes."""
    if not text:
        return ""
    source = _UNICODE_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), str(text))
    source = _CARET.sub(lambda m: _CARET_CHARS[m.group(1)], source)
    source = source.replace("%%%", "\x00")

    def _percent(match: re.Match[str]) -> str:
        code = match.group(1)
        if code.isdigit():
            return chr(int(code))
        return _PERCENT_CHARS.get(code.lower(), "")

    source = _PERCENT_CODE.sub(_percent, source).replace("\x00", "%")
    out: list[str] = []
    i, n = 0, len(source)
    while i < n:
        ch = source[i]
        if ch == "\\" and i + 1 < n:
            code = source[i + 1]
            if code in "\\{}":
                out.append(code)
                i += 2
            elif code in "PX":
                out.append("\n")
                i += 2
            elif code == "~":
                out.append(" ")
                i += 2
            elif code == "S":
                end = source.find(";", i + 2)
                end = n if end < 0 else end
                out.append(re.sub(r"[\^#]", "/", source[i + 2 : end]))
                i = end + 1
            elif code in _ARG_CODES:
                end = source.find(";", i + 2)
                i = n if end < 0 else end + 1
            elif code in _TOGGLE_CODES:
                i += 2
            else:
                out.append(code)
                i += 2
        elif ch in "{}":
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out).strip()


def normalize_dim_text(text: str | None) -> str | None:
    """Normalize diameter symbols and whitespace for rendered-vs-expected checks."""
    if text is None:
        return None
    out = _UNICODE_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), str(text))
    out = re.sub(
        r"%%([cCdDpP])",
        lambda m: _PERCENT_CHARS[m.group(1).lower()],
        out,
    )
    for sign in DIAMETER_SIGNS:
        out = out.replace(sign, DIAMETER_SIGN)
    return " ".join(out.split())


def _decimal_separator(value: object) -> str:
    if isinstance(value, str):
        return value or "."
    code = int(value)  # type: ignore[arg-type]
    return "," if code == 0 else chr(code)


def _suppress_zeros(text: str, leading: bool, trailing: bool) -> str:
    if not leading and not trailing:
        return text
    if float(text) == 0.0:
        return "0"
    sign = ""
    if text[0] in "-+":
        sign, text = text[0], text[1:]
    if leading:
        text = text.lstrip("0")
    if trailing and "." in text:
        text = text.rstrip("0")
    if text and text[-1] in ".,":
        text = text[:-1]
    return sign + (text or "0")


def _format_decimal(value: float, places: int, zin: int, sep: str, rounding: float) -> str:
    if rounding and rounding > 0:
        factor = 1.0 / float(rounding)
        value = round(value * factor) / factor
    text = f"{value:.{max(0, int(places))}f}"
    text = _suppress_zeros(text, bool(zin & 4), bool(zin & 8))
    return text.replace(".", sep) if sep != "." else text


def _format_dms(degrees: float, places: int, zin: int, sep: str) -> str:
    total = abs(degrees)
    d = int(total)
    minutes_full = (total - d) * 60.0
    m = int(minutes_full)
    s = (minutes_full - m) * 60.0
    sign = "-" if degrees < 0 else ""
    if places > 4:
        return f"{sign}{d}\u00b0{m}'{_format_decimal(s, places - 5, zin, sep, 0.0)}\""
    if places > 2:
        return f"{sign}{d}\u00b0{m}'{s:.0f}\""
    if places > 0:
        return f"{sign}{d}\u00b0{m}'"
    return f"{sign}{d}\u00b0"


def _apply_dimpost(text: str, post: str) -> str:
    if not post:
        return text
    if "<>" in post:
        return post.replace("<>", text, 1)
    return text + post


def _read_effective_style(entity) -> dict[str, object] | None:
    from ezdxf.entities import DimStyleOverride

    try:
        override = DimStyleOverride(entity)
        vars_dict: dict[str, object] = {}
        for name, default in _DEFAULTS.items():
            value = override.get(name, default)
            if name == "dimrnd":
                value = float(value or 0.0)
            elif isinstance(value, bool):
                value = int(value)
            vars_dict[name] = value
        vars_dict["dimdsep"] = override.get_decimal_separator()
        return vars_dict
    except Exception:
        return None


def _is_layer_visible_and_plotted(doc, layer_name: str) -> bool:
    """Return True only when `layer_name` exists, is ON, unfrozen, and plotted."""
    try:
        layer = doc.layers.get(layer_name)
    except Exception:
        return False
    if layer is None:
        return False
    return bool(layer.is_on() and not layer.is_frozen() and int(layer.dxf.get("plot", 1)))


@dataclass(frozen=True)
class _RenderedBlockRead:
    text: str | None
    group42: float | None
    hidden_text_count: int
    block_missing: bool


def _read_rendered_block(doc, entity) -> _RenderedBlockRead:
    raw_g42 = entity.dxf.get("actual_measurement")
    try:
        group42 = None if raw_g42 is None else float(raw_g42)
    except (TypeError, ValueError, OverflowError):
        group42 = math.nan
    try:
        block = entity.get_geometry_block()
    except Exception:
        block = None
    if block is None:
        return _RenderedBlockRead(None, group42, 0, True)
    visible_parts: list[str] = []
    hidden_text_count = 0
    for item in block:
        kind = item.dxftype()
        if kind == "MTEXT":
            plain = plain_cad_text(item.text)
        elif kind == "TEXT":
            plain = plain_cad_text(item.dxf.get("text", ""))
        else:
            continue
        item_layer = str(item.dxf.get("layer", "0"))
        item_hidden = bool(int(item.dxf.get("invisible", 0) or 0))
        if not item_hidden and item_layer != "0":
            item_hidden = not _is_layer_visible_and_plotted(doc, item_layer)
        if item_hidden:
            hidden_text_count += 1
            continue
        if plain:
            visible_parts.append(plain)
    text = " ".join(visible_parts)
    return _RenderedBlockRead((text or None), group42, hidden_text_count, False)


def _format_measured(value: float, dimtype: int, style: Mapping[str, object]) -> str:
    if dimtype in _ANGULAR_TYPES:
        places = int(style["dimadec"])  # type: ignore[arg-type]
        zin = int(style["dimazin"]) << 2  # type: ignore[arg-type]
        sep = _decimal_separator(style["dimdsep"])
        unit = int(style["dimaunit"])  # type: ignore[arg-type]
        if unit == 1:
            text = _format_dms(value, places, zin, sep)
        elif unit == 2:
            text = _format_decimal(value * 400.0 / 360.0, places, zin, sep, 0.0) + "g"
        elif unit == 3:
            text = _format_decimal(math.radians(value), places, zin, sep, 0.0) + "r"
        else:
            text = _format_decimal(value, places, zin, sep, 0.0) + "\u00b0"
        return _apply_dimpost(text, str(style["dimpost"] or ""))
    text = _format_decimal(
        value,
        int(style["dimdec"]),  # type: ignore[arg-type]
        int(style["dimzin"]),  # type: ignore[arg-type]
        _decimal_separator(style["dimdsep"]),
        float(style["dimrnd"] or 0.0),  # type: ignore[arg-type]
    )
    text = _apply_dimpost(text, str(style["dimpost"] or ""))
    prefix = {3: DIAMETER_SIGN, 4: RADIUS_SIGN}.get(dimtype)
    if prefix and text and text[0] != prefix:
        text = prefix + text
    return text


def resolve_dimension_display(
    dimtype: int,
    measurement: float | None,
    override: str,
    dimlfac: float | None,
    style: Mapping[str, object] | None,
) -> DimensionDisplay:
    """Resolve what plain text and numeric value a DIMENSION displays."""
    angular = dimtype in _ANGULAR_TYPES
    if measurement is None or not math.isfinite(measurement):
        scaled = None
    elif angular:
        scaled = float(measurement)
    elif dimlfac is None or not math.isfinite(dimlfac):
        scaled = None
    else:
        scaled = float(measurement) * float(dimlfac)

    if override == " ":
        return DimensionDisplay("", None, scaled, 0.0, "suppressed")
    if override and override != "<>" and "<>" not in override:
        plain = normalize_dim_text(plain_cad_text(override)) or ""
        cleaned = _COUNT_PREFIX_RE.sub("", plain, count=1)
        found = _NUMBER_RE.search(cleaned)
        parsed = float(found.group().replace(",", ".")) if found else None
        return DimensionDisplay(plain, parsed, scaled, 0.0, "override")

    if style is None:
        return DimensionDisplay(None, None, scaled, 0.0, "unknown")
    if int(style["dimlim"]) and not int(style["dimtol"]):  # type: ignore[arg-type]
        return DimensionDisplay(None, None, scaled, 0.0, "limits")
    if int(style["dimalt"]):  # type: ignore[arg-type]
        return DimensionDisplay(None, None, scaled, 0.0, "alternate_units")
    if scaled is None:
        return DimensionDisplay(None, None, None, 0.0, "unknown")

    formatted = _format_measured(scaled, dimtype, style)
    places = max(0, int(style["dimadec" if angular else "dimdec"]))  # type: ignore[arg-type]
    rounding = 0.0 if angular else float(style["dimrnd"] or 0.0)  # type: ignore[arg-type]
    tol = max(0.5 * 10.0 ** (-places), rounding / 2.0) if rounding > 0 else 0.5 * 10.0 ** (-places)
    raw_text = override.replace("<>", formatted, 1) if override and override != "<>" else formatted
    shown_text = normalize_dim_text(plain_cad_text(raw_text))
    return DimensionDisplay(shown_text, scaled, scaled, tol, "measurement")


def audit_dimension_truth(
    doc,
    entity,
    *,
    expected_measurement: float | None = None,
    approved_value_mm: float | None = None,
    tolerance_mm: float = 1e-6,
) -> list[str]:
    """Audit one DXF DIMENSION entity for override lies, scaling traps, stale *D text, and hidden visibility."""
    reasons: list[str] = []
    dxf = entity.dxf
    dimtype = int(dxf.get("dimtype", 0)) & 0x0F
    override = str(dxf.get("text", "") or "")
    style = _read_effective_style(entity)
    if style is None:
        reasons.append("dim_style_unreadable")
        return reasons

    raw_lfac = style.get("dimlfac")
    if isinstance(raw_lfac, bool) or not isinstance(raw_lfac, (int, float)) or not math.isfinite(raw_lfac) or raw_lfac <= 0.0:
        reasons.append(f"dim_dimlfac_invalid({raw_lfac!r})")
        dimlfac = None
    else:
        dimlfac = float(raw_lfac)
        if dimtype in _LINEAR_OR_RADIAL_TYPES and abs(dimlfac - 1.0) > 1e-9:
            reasons.append(f"dim_dimlfac_scaled({dimlfac})")

    if int(dxf.get("invisible", 0) or 0):
        reasons.append("dim_entity_invisible")

    layer_name = str(dxf.get("layer", "0"))
    if not _is_layer_visible_and_plotted(doc, layer_name):
        reasons.append(f"dim_layer_hidden_or_noplot({layer_name!r})")

    raw_dimtxt = style.get("dimtxt")
    if isinstance(raw_dimtxt, bool) or not isinstance(raw_dimtxt, (int, float)) or not math.isfinite(raw_dimtxt) or float(raw_dimtxt) <= 0.0:
        reasons.append(f"dim_dimtxt_non_positive({raw_dimtxt!r})")

    try:
        measured_raw = entity.get_measurement()
        measured = float(measured_raw) if isinstance(measured_raw, (int, float)) else math.nan
    except Exception:
        measured = math.nan

    disp = resolve_dimension_display(dimtype, measured, override, dimlfac, style)
    ref_value = approved_value_mm if approved_value_mm is not None else expected_measurement
    if ref_value is None and math.isfinite(measured):
        ref_value = measured

    if disp.source == "suppressed":
        reasons.append("dim_value_suppressed")
    elif disp.source == "override":
        if disp.value is None or not math.isfinite(disp.value):
            reasons.append(f"dim_override_non_numeric(shown={disp.text!r})")
        elif ref_value is not None and math.isfinite(ref_value):
            if abs(disp.value - float(ref_value)) > max(float(tolerance_mm), 1e-6):
                reasons.append(f"dim_override_disagrees(shown={disp.text!r}, expected={ref_value})")

    rendered = _read_rendered_block(doc, entity)
    if rendered.hidden_text_count > 0:
        reasons.append("dim_rendered_text_hidden")
    rendered_text, group42 = rendered.text, rendered.group42
    if disp.source != "suppressed":
        if disp.text is None:
            reasons.append(f"dim_display_unreadable(source={disp.source})")
        if rendered.block_missing or rendered_text is None:
            reasons.append("dim_render_missing")
    if rendered_text is not None and disp.text is not None:
        have = normalize_dim_text(rendered_text)
        want = normalize_dim_text(disp.text)
        matched = have == want
        if not matched and int(style["dimtol"]) and have is not None and want is not None and have.startswith(want):  # type: ignore[arg-type]
            rest = have[len(want) :]
            matched = not (rest[:1].isdigit() or rest[:1] in ".,")
        if not matched:
            reasons.append(f"dim_render_stale(rendered={rendered_text!r}, expected={disp.text!r})")

    # AutoCAD _SAVEAS without DIMREGEN may emit DXF group 42 = -1.0 (unpopulated sentinel).
    if group42 is not None:
        if not math.isfinite(group42):
            reasons.append("dim_group42_non_finite")
        elif group42 >= 0.0 and expected_measurement is not None and math.isfinite(expected_measurement):
            if abs(group42 - float(expected_measurement)) > max(float(tolerance_mm), 1e-4):
                reasons.append(f"dim_group42_stale(grp42={group42}, expected={expected_measurement})")

    return reasons
