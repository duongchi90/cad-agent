"""Deterministic DXF DIMENSION truth, style-visibility, and rendered-block checks.

Adapted from leaf helpers of `U-C4N/Autocad-MCP`
(`backends/entity_fields.py`, `engineering/dimtext.py`,
`engineering/understand/labels.py`, observed upstream revision
`6f6a538255ca9f885232e845ac32f10b4433fe3e`) with zero external runtime
dependencies beyond `ezdxf` and the Python standard library.

MIT License

Copyright (c) 2026 Umutcan Edizsalan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
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
_NUMERIC_TOKEN_RE = re.compile(r"[-+]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][-+]?\d+)?")
_NUMERIC_SIGNS = str.maketrans({"\u2212": "-", "\uff0d": "-", "\uff0b": "+"})
_DMS_RE = re.compile(r"^\s*([-+]?\d+)\u00b0\s*(\d+)'(?:\s*(\d+(?:[.,]\d+)?)\")?\s*$")
_COUNT_PREFIX_RE = re.compile(rf"^\s*\d+\s*[xX\u00d7](?:\s*(?=[{DIAMETER_SIGNS}MR])|\s+(?=[+-]?\s*(?:\d|[.,]\d)))")
_UNSAFE_PLACEHOLDER_NEIGHBORS = frozenset("0123456789.,+-eE")

_DEFAULTS: dict[str, object] = {
    "dimdec": 2,
    "dimrnd": 0.0,
    "dimzin": 8,
    "dimdsep": ".",
    "dimpost": "",
    "dimlfac": 1.0,
    "dimlunit": 2,
    "dimadec": 2,
    "dimazin": 2,
    "dimaunit": 0,
    "dimalt": 0,
    "dimtol": 0,
    "dimlim": 0,
    "dimtxt": 2.5,
    "dimscale": 1.0,
    "dimtfac": 0.5,
    "dimtp": 0.0,
    "dimtm": 0.0,
    "dimtdec": 2,
    "dimtzin": 8,
    "dimtxsty": "Standard",
}


@dataclass(frozen=True)
class DimensionDisplay:
    """Resolved displayed string and claimed numeric value for one DIMENSION."""

    text: str | None
    value: float | None
    scaled_value: float | None
    tolerance: float
    source: str
    claim_unit_factor: float = 1.0


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


def _has_unsafe_placeholder(template: str) -> bool:
    """Reject multiple `<>` placeholders or numeric/syntax glue adjoining `<>`."""
    count = template.count("<>")
    if count > 1:
        return True
    if count == 0:
        return False
    idx = template.find("<>")
    before = template[idx - 1] if idx > 0 else ""
    after = template[idx + 2] if idx + 2 < len(template) else ""
    return (
        before in (_UNSAFE_PLACEHOLDER_NEIGHBORS - {"e", "E"})
        or after in _UNSAFE_PLACEHOLDER_NEIGHBORS
    )


def _has_unsafe_dimpost(dimpost: str) -> bool:
    if "<>" in dimpost:
        return _has_unsafe_placeholder(dimpost)
    return bool(dimpost and dimpost[0] in _UNSAFE_PLACEHOLDER_NEIGHBORS)


class _UnverifiedClaim(ValueError):
    """The complete claim contains unsupported unit or annotation semantics."""


def _claim_in_reference_units(value: float, suffix: str, *, angular: bool, angle_unit: int) -> float:
    """Reuse ezdxf's unit catalog; references remain millimetres or degrees."""
    tokens = suffix.split()
    if tokens and tokens[-1] in {"REF", "TYP"}:
        if len(tokens) == 1 and suffix and not suffix[0].isspace():
            raise _UnverifiedClaim("concatenated annotation suffix")
        tokens.pop()
    if len(tokens) > 1:
        raise _UnverifiedClaim("ambiguous unit/annotation suffix")
    unit = tokens[0] if tokens else ""
    if angular:
        # Inverse of the existing _format_measured DIMAUNIT output, not a new
        # angle-expression parser. Linear units never convert angular claims.
        expected = {0: "°", 1: "°", 2: "g", 3: "r", 4: "°"}.get(angle_unit)
        if expected is None or unit not in {"", expected}:
            raise _UnverifiedClaim("unsupported angular unit/annotation suffix")
        if angle_unit == 2:
            return value * 360.0 / 400.0
        if angle_unit == 3:
            return math.degrees(value)
        return value
    if not unit:
        return value
    from ezdxf import units

    for candidate in units.InsertUnits:
        abbreviation = units.decode(candidate)
        if abbreviation is not None and unit == abbreviation:
            try:
                return value * units.conversion_factor(candidate, units.MM)
            except (TypeError, ValueError, IndexError) as exc:
                raise _UnverifiedClaim("unsupported linear conversion") from exc
    raise _UnverifiedClaim("unsupported linear unit/annotation suffix")


def _parse_primary_numeric_claim(
    plain_text: str,
    *,
    angular: bool = False,
    angle_unit: int = 0,
) -> tuple[float | None, float]:
    """Keep the claim's conversion context beside its reference-unit value."""
    text = (plain_text or "").strip().translate(_NUMERIC_SIGNS)
    if not text:
        return None, 1.0
    if angular and angle_unit == 1:
        dms = _DMS_RE.match(text)
        if dms:
            deg = int(dms.group(1))
            mins = int(dms.group(2))
            secs = float((dms.group(3) or "0").replace(",", "."))
            sign = -1.0 if dms.group(1).startswith("-") else 1.0
            val = sign * (abs(deg) + mins / 60.0 + secs / 3600.0)
            return (val if math.isfinite(val) else None), 1.0

    cleaned = _COUNT_PREFIX_RE.sub("", text, count=1).strip()
    if cleaned and cleaned[0] in f"{DIAMETER_SIGNS}MR":
        cleaned = cleaned[1:].strip()
    cleaned = re.sub(r"^([+-])\s+", r"\1", cleaned)

    matches = list(_NUMERIC_TOKEN_RE.finditer(cleaned))
    if len(matches) != 1:
        return None, 1.0
    match = matches[0]
    # An unknown prefix cannot discard a sign. A complete suffix must resolve
    # through supported units/qualifiers rather than being treated as harmless.
    if match.start() != 0:
        return None, 1.0
    suffix = cleaned[match.end():]
    token = match.group()
    if "e" in token or "E" in token:
        return None, 1.0
    next_ch = cleaned[match.end()] if match.end() < len(cleaned) else ""
    if next_ch and next_ch in ".,%eE":
        return None, 1.0
    if suffix and not any(char.isalpha() or char == "°" for char in suffix):
        return None, 1.0
    try:
        parsed = float(token.replace(",", "."))
    except ValueError:
        return None, 1.0
    if not math.isfinite(parsed):
        return None, 1.0
    converted = _claim_in_reference_units(parsed, suffix, angular=angular, angle_unit=angle_unit)
    factor = _claim_in_reference_units(1.0, suffix, angular=angular, angle_unit=angle_unit)
    return (converted if math.isfinite(converted) else None), factor


def _extract_primary_numeric_claim(
    plain_text: str, *, angular: bool = False, angle_unit: int = 0,
) -> float | None:
    """Preserve the existing scalar helper while sharing one claim parser."""
    return _parse_primary_numeric_claim(plain_text, angular=angular, angle_unit=angle_unit)[0]


def _is_finite_number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _read_effective_style(doc, entity) -> tuple[object | None, dict[str, object] | None, float | None]:
    from ezdxf.entities import DimStyleOverride
    from ezdxf.render import dim_base

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

        dimscale_raw = vars_dict.get("dimscale")
        dimtxt_raw = vars_dict.get("dimtxt")
        if not _is_finite_number(dimscale_raw) or float(dimscale_raw) < 0.0:  # type: ignore[arg-type]
            return override, vars_dict, None
        if not _is_finite_number(dimtxt_raw) or float(dimtxt_raw) <= 0.0:  # type: ignore[arg-type]
            return override, vars_dict, None
        eff_scale = 1.0 if float(dimscale_raw) == 0.0 else float(dimscale_raw)  # type: ignore[arg-type]

        text_style_name = str(vars_dict.get("dimtxsty") or "Standard")
        text_style = dim_base.get_text_style(doc, text_style_name)
        ts_height_raw = text_style.dxf.get("height", 0.0)
        if not _is_finite_number(ts_height_raw) or float(ts_height_raw) < 0.0:
            return override, vars_dict, None
        ts_height = float(ts_height_raw)
        if ts_height > 0.0:
            nominal_h = ts_height * eff_scale
        else:
            nominal_h = float(dimtxt_raw) * eff_scale  # type: ignore[arg-type]
        vars_dict["height_authoritative"] = ts_height > 0.0 or "dimtxt" in override.dimstyle_attribs
        return override, vars_dict, nominal_h
    except Exception:
        return None, None, None


def _is_layer_visible_and_plotted(doc, layer_name: str) -> bool:
    """Return True only when `layer_name` exists, is ON, unfrozen, and plotted."""
    try:
        layer = doc.layers.get(layer_name)
    except Exception:
        return False
    if layer is None:
        return False
    return bool(layer.is_on() and not layer.is_frozen() and int(layer.dxf.get("plot", 1)))


class _SuppressedText(ValueError):
    """The existing text owner resolves a degenerate rendered token."""


def _mtext_height_profile(raw_text: str, base_height: float) -> list[tuple[str, float]]:
    """Use the existing parser's token contexts, never infer roles from size."""
    from ezdxf.tools.text import MTextContext, MTextParser

    context = MTextContext()
    context.cap_height = base_height
    profile: list[tuple[str, float]] = []
    for token in MTextParser(raw_text, ctx=context):
        if token.type.name == "WORD":
            text = plain_cad_text(str(token.data))
        elif token.type.name == "STACK":
            upper, lower, _divider = token.data
            text = plain_cad_text(str(upper)) + "/" + plain_cad_text(str(lower))
        else:
            continue
        width = float(token.ctx.width_factor)
        if text.strip() and width == 0.0:
            raise _SuppressedText("zero horizontal extent")
        if not math.isfinite(width):
            raise ValueError("unverified effective text width")
        height = float(token.ctx.cap_height)
        if text.strip() and height == 0.0:
            raise _SuppressedText("zero vertical extent")
        if not math.isfinite(height) or height <= 0.0:
            raise ValueError("invalid effective text height")
        profile.extend((char, height) for char in text if not char.isspace())
    return profile


def _render_alpha(context, entity) -> int:
    """Resolve supported ByLayer/ByBlock properties through ezdxf's owner."""
    from ezdxf.lldxf import validator

    if entity.dxf.hasattr("transparency") and not validator.is_transparency(entity.dxf.transparency):
        raise ValueError("invalid transparency")
    color = context.resolve_color(entity)
    return 255 if len(color) == 7 else int(color[7:9], 16)


def _text_height_profile(item, context, plain: str, base_height: float) -> list[tuple[str, float]]:
    """Resolve native TEXT stretching through the existing drawing owner."""
    from ezdxf.addons.drawing.text import _get_extra_transform
    from ezdxf.addons.drawing.unified_text_renderer import UnifiedTextRenderer
    from ezdxf.enums import TextEntityAlignment

    line_width = 0.0  # The owner needs glyph width only for FIT/ALIGNED.
    if item.get_align_enum() in (TextEntityAlignment.FIT, TextEntityAlignment.ALIGNED):
        face = context.resolve_font(item)
        if face is None:
            # Do not invent font metrics when this context cannot resolve them.
            raise ValueError("unverified native TEXT stretch font")
        line_width = UnifiedTextRenderer().get_text_line_width(item.plain_text(), face, base_height)
        if not math.isfinite(line_width) or line_width <= 0.0:
            raise ValueError("unverified native TEXT line width")
    transform = _get_extra_transform(item, line_width)
    x_scale = transform.transform_direction((1, 0, 0)).magnitude
    y_scale = transform.transform_direction((0, 1, 0)).magnitude
    if not math.isfinite(x_scale) or not math.isfinite(y_scale):
        raise ValueError("unverified native TEXT transform")
    if plain.strip() and (x_scale == 0.0 or y_scale == 0.0):
        raise _SuppressedText("collapsed native TEXT")
    height = base_height * y_scale
    if not math.isfinite(height) or height <= 0.0:
        raise ValueError("invalid native TEXT effective height")
    return [(char, height) for char in plain if not char.isspace()]


@dataclass(frozen=True)
class _RenderedBlockRead:
    text: str | None
    group42: float | None
    hidden_text_count: int
    too_small_count: int
    transparent_count: int
    unreadable_count: int
    block_missing: bool


_NON_LABEL_RENDERED_GEOMETRY_TYPES = frozenset({
    "LINE",
    "POINT",
    "SOLID",
    "TRACE",
    "3DFACE",
    "ARC",
    "CIRCLE",
    "ELLIPSE",
    "SPLINE",
    "LWPOLYLINE",
    "POLYLINE",
    "HATCH",
    "WIPEOUT",
})
_MAX_NESTED_INSERT_DEPTH = 32


def _has_finite_coords(value: object) -> bool:
    try:
        coords = tuple(value)  # type: ignore[arg-type]
    except TypeError:
        return False
    return len(coords) in {2, 3} and all(_is_finite_number(coord) for coord in coords)


def _insert_is_non_label_geometry(
    doc,
    insert_entity,
    *,
    active_blocks: frozenset[str],
    verified_heights: dict[str, int],
    depth: int = 0,
) -> bool:
    """Return True iff `insert_entity` resolves to bounded, cycle-free non-label geometry."""
    if depth >= _MAX_NESTED_INSERT_DEPTH:
        return False
    if getattr(insert_entity, "attribs", ()):
        return False
    try:
        if int(insert_entity.dxf.get("attribs_follow", 0) or 0):
            return False
    except (TypeError, ValueError, OverflowError):
        return False
    if not _has_finite_coords(insert_entity.dxf.get("insert", (0.0, 0.0, 0.0))):
        return False
    if not _has_finite_coords(insert_entity.dxf.get("extrusion", (0.0, 0.0, 1.0))):
        return False
    for attr, default in (
        ("xscale", 1.0),
        ("yscale", 1.0),
        ("zscale", 1.0),
        ("rotation", 0.0),
        ("row_spacing", 0.0),
        ("column_spacing", 0.0),
    ):
        if not _is_finite_number(insert_entity.dxf.get(attr, default)):
            return False
    for count_attr in ("row_count", "column_count"):
        raw_count = insert_entity.dxf.get(count_attr, 1)
        if (
            not _is_finite_number(raw_count)
            or not float(raw_count).is_integer()  # type: ignore[arg-type]
            or int(raw_count) < 1  # type: ignore[arg-type]
        ):
            return False

    raw_name = insert_entity.dxf.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        return False
    try:
        target_block = doc.blocks.get(raw_name)
    except Exception:
        return False
    if target_block is None or bool(getattr(target_block, "is_any_layout", False)):
        return False
    block_header = getattr(target_block, "block", None)
    if block_header is None:
        return False
    try:
        flags = int(block_header.dxf.get("flags", 0) or 0)
        xref_path = str(block_header.dxf.get("xref_path", "") or "").strip()
    except (TypeError, ValueError, OverflowError):
        return False
    if (
        bool(getattr(block_header, "is_xref", False))
        or bool(getattr(block_header, "is_xref_overlay", False))
        or bool(flags & 0x0C)
        or bool(xref_path)
    ):
        return False
    if not _has_finite_coords(getattr(target_block, "base_point", (0.0, 0.0, 0.0))):
        return False

    block_key = str(getattr(target_block, "name", raw_name)).casefold()
    if block_key in active_blocks:
        return False
    cached_height = verified_heights.get(block_key)
    if cached_height is not None:
        return depth + cached_height <= _MAX_NESTED_INSERT_DEPTH

    next_active = active_blocks | {block_key}
    max_child_height = 0
    for child in target_block:
        child_kind = child.dxftype()
        if child_kind in _NON_LABEL_RENDERED_GEOMETRY_TYPES:
            continue
        if child_kind == "INSERT":
            if not _insert_is_non_label_geometry(
                doc,
                child,
                active_blocks=next_active,
                verified_heights=verified_heights,
                depth=depth + 1,
            ):
                return False
            child_name = child.dxf.get("name")
            child_target = doc.blocks.get(child_name) if isinstance(child_name, str) else None
            child_key = str(getattr(child_target, "name", child_name)).casefold()
            max_child_height = max(max_child_height, verified_heights.get(child_key, 1))
            continue
        return False

    subtree_height = 1 + max_child_height
    verified_heights[block_key] = subtree_height
    return depth + subtree_height <= _MAX_NESTED_INSERT_DEPTH


def _read_rendered_block(
    doc,
    entity,
    *,
    context,
    nominal_base_height: float,
    expected_mtext: str | None,
) -> _RenderedBlockRead:
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
        return _RenderedBlockRead(None, group42, 0, 0, 0, 0, True)

    parts: list[str] = []
    profile: list[tuple[str, float]] = []
    hidden_count = transparent_count = unreadable_count = height_mismatch = 0
    root_block_name = str(getattr(block, "name", "") or "").casefold()
    initial_active = frozenset({root_block_name}) if root_block_name else frozenset()
    verified_insert_heights: dict[str, int] = {}
    for item in block:
        kind = item.dxftype()
        if kind in _NON_LABEL_RENDERED_GEOMETRY_TYPES:
            continue
        if kind == "INSERT":
            if not _insert_is_non_label_geometry(
                doc,
                item,
                active_blocks=initial_active,
                verified_heights=verified_insert_heights,
            ):
                unreadable_count += 1
            continue
        if kind not in {"TEXT", "MTEXT"}:
            unreadable_count += 1
            continue
        raw_content = item.text if kind == "MTEXT" else item.dxf.get("text", "")
        # Native TEXT preserves backslashes/braces which are MTEXT commands.
        plain = item.plain_text() if kind == "TEXT" else plain_cad_text(raw_content)
        if plain:
            parts.append(plain)
        layer = context.resolve_layer(item)
        if bool(int(item.dxf.get("invisible", 0) or 0)) or not _is_layer_visible_and_plotted(doc, layer):
            hidden_count += 1
        try:
            if _render_alpha(context, item) == 0:
                transparent_count += 1
        except (ValueError, TypeError, AttributeError):
            unreadable_count += 1
        raw_h = item.dxf.get("char_height" if kind == "MTEXT" else "height")
        if not _is_finite_number(raw_h) or float(raw_h) <= 0.0:
            unreadable_count += 1
            continue
        try:
            if kind == "MTEXT":
                profile.extend(_mtext_height_profile(raw_content, float(raw_h)))
            else:
                profile.extend(_text_height_profile(item, context, plain, float(raw_h)))
        except _SuppressedText:
            hidden_count += 1
        except (ValueError, TypeError, AttributeError, IndexError):
            unreadable_count += 1
    if expected_mtext is not None:
        try:
            expected = _mtext_height_profile(expected_mtext, nominal_base_height)
            if [c for c, _h in expected] != [c for c, _h in profile]:
                unreadable_count += 1
            elif any(not math.isclose(a[1], b[1], rel_tol=1e-9, abs_tol=1e-12)
                     for a, b in zip(expected, profile)):
                height_mismatch += 1
        except (ValueError, TypeError, AttributeError, IndexError):
            unreadable_count += 1
    text = " ".join(parts)
    return _RenderedBlockRead(text or None, group42, hidden_count,
                              height_mismatch, transparent_count, unreadable_count, False)


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


def _tolerance_rendered_candidates(override_obj, disp_text: str) -> set[str] | None:
    """Return normalized valid rendered strings via `ezdxf.render.dim_base.Tolerance`."""
    from ezdxf.render.dim_base import Tolerance

    try:
        tol = Tolerance(override_obj)
        if not tol.has_tolerance:
            return None
        candidates = {normalize_dim_text(plain_cad_text(tol.compile_mtext(disp_text))) or ""}
        if tol.text:
            candidates.add(normalize_dim_text(f"{disp_text} {tol.text}") or "")
        else:
            candidates.add(normalize_dim_text(f"{disp_text}{tol.text_upper}/{tol.text_lower}") or "")
            candidates.add(normalize_dim_text(f"{disp_text} {tol.text_upper}/{tol.text_lower}") or "")
        candidates.discard("")
        return candidates or None
    except Exception:
        return None


def resolve_dimension_display(
    dimtype: int,
    measurement: float | None,
    override: str,
    dimlfac: float | None,
    style: Mapping[str, object] | None,
) -> DimensionDisplay:
    """Resolve what plain text and numeric value a DIMENSION displays."""
    angular = dimtype in _ANGULAR_TYPES
    angle_unit = int(style["dimaunit"]) if style and "dimaunit" in style else 0  # type: ignore[arg-type]
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
        try:
            parsed, unit_factor = _parse_primary_numeric_claim(plain, angular=angular, angle_unit=angle_unit)
        except _UnverifiedClaim:
            return DimensionDisplay(plain, None, scaled, 0.0, "unverified_claim")
        return DimensionDisplay(plain, parsed, scaled, 0.0, "override", unit_factor)

    if style is None:
        return DimensionDisplay(None, None, scaled, 0.0, "unknown")
    if not angular and int(style.get("dimlunit", 2)) != 2:
        # ezdxf's dimension renderer falls back to decimal for these formats;
        # that fallback does not prove the configured generated label.
        return DimensionDisplay(None, None, scaled, 0.0, "unverified_primary_format")
    if int(style["dimlim"]) and not int(style["dimtol"]):  # type: ignore[arg-type]
        return DimensionDisplay(None, None, scaled, 0.0, "limits")
    if int(style["dimalt"]):  # type: ignore[arg-type]
        return DimensionDisplay(None, None, scaled, 0.0, "alternate_units")
    if scaled is None:
        return DimensionDisplay(None, None, None, 0.0, "unknown")

    dimpost = str(style["dimpost"] or "")
    if _has_unsafe_dimpost(dimpost) or ("<>" in override and _has_unsafe_placeholder(override)):
        return DimensionDisplay(None, None, scaled, 0.0, "unsafe_placeholder")

    formatted = _format_measured(scaled, dimtype, style)
    places = max(0, int(style["dimadec" if angular else "dimdec"]))  # type: ignore[arg-type]
    rounding = 0.0 if angular else float(style["dimrnd"] or 0.0)  # type: ignore[arg-type]
    tol = max(0.5 * 10.0 ** (-places), rounding / 2.0) if rounding > 0 else 0.5 * 10.0 ** (-places)
    raw_text = override.replace("<>", formatted, 1) if override and override != "<>" else formatted
    shown_text = normalize_dim_text(plain_cad_text(raw_text))
    try:
        claim, unit_factor = _parse_primary_numeric_claim(shown_text or "", angular=angular, angle_unit=angle_unit)
    except _UnverifiedClaim:
        return DimensionDisplay(shown_text, None, scaled, tol, "unverified_claim")
    return DimensionDisplay(shown_text, claim, scaled, tol, "measurement", unit_factor)


def audit_dimension_truth(
    doc,
    entity,
    *,
    expected_measurement: float | None = None,
    approved_value_mm: float | None = None,
    tolerance_mm: float = 1e-6,
) -> list[str]:
    """Audit one DXF DIMENSION entity for override lies, scaling traps, stale *D text, and visibility."""
    reasons: list[str] = []
    dxf = entity.dxf
    dimtype = int(dxf.get("dimtype", 0)) & 0x0F
    override_text = str(dxf.get("text", "") or "")
    override_obj, style, nominal_base_height = _read_effective_style(doc, entity)
    if style is None or override_obj is None:
        reasons.append("dim_style_unreadable")
        return reasons

    raw_lfac = style.get("dimlfac")
    if not _is_finite_number(raw_lfac) or float(raw_lfac) <= 0.0:  # type: ignore[arg-type]
        reasons.append(f"dim_dimlfac_invalid({raw_lfac!r})")
        dimlfac = None
    else:
        dimlfac = float(raw_lfac)  # type: ignore[arg-type]
        if dimtype in _LINEAR_OR_RADIAL_TYPES and abs(dimlfac - 1.0) > 1e-9:
            reasons.append(f"dim_dimlfac_scaled({dimlfac})")

    if nominal_base_height is None or nominal_base_height <= 0.0:
        reasons.append("dim_style_height_or_scale_invalid")
        nominal_base_height = max(float(style.get("dimtxt") or 1.0), 1e-6) if _is_finite_number(style.get("dimtxt")) else 1.0  # type: ignore[arg-type]

    dimtol_enabled = bool(int(style["dimtol"]))
    dimlim_enabled = bool(int(style["dimlim"]))
    primary_format_unsupported = dimtype not in _ANGULAR_TYPES and int(style["dimlunit"]) != 2
    if dimtol_enabled and primary_format_unsupported:
        # A literal primary override does not establish tolerance formatting.
        reasons.append("dim_unverified_primary_format")
    if int(style["dimalt"]):
        reasons.append("dim_unverified_alternate_units")
    if dimlim_enabled and not dimtol_enabled:
        # Unsupported configured limits remain non-PASS for explicit overrides
        # as well as generated labels. Keep proven primary mismatches intact.
        reasons.append("dim_unverified_limits")
    if dimtol_enabled or dimlim_enabled:
        raw_dimtfac = style.get("dimtfac")
        if not _is_finite_number(raw_dimtfac) or float(raw_dimtfac) <= 0.0:
            reasons.append(f"dim_dimtfac_invalid({raw_dimtfac!r})")
        for tol_key in ("dimtp", "dimtm"):
            if not _is_finite_number(style.get(tol_key)):
                reasons.append(f"dim_{tol_key}_non_finite")

    if int(dxf.get("invisible", 0) or 0):
        reasons.append("dim_entity_invisible")

    from ezdxf.addons.drawing.properties import RenderContext

    context = RenderContext(doc)
    try:
        parent_properties = context.resolve_all(entity)
        if _render_alpha(context, entity) == 0:
            reasons.append("dim_entity_transparent")
        context.push_state(parent_properties)
    except (ValueError, TypeError, AttributeError):
        reasons.append("dim_unverified_transparency")

    layer_name = str(dxf.get("layer", "0"))
    if not _is_layer_visible_and_plotted(doc, layer_name):
        reasons.append(f"dim_layer_hidden_or_noplot({layer_name!r})")

    raw_dimtxt = style.get("dimtxt")
    if not _is_finite_number(raw_dimtxt) or float(raw_dimtxt) <= 0.0:  # type: ignore[arg-type]
        reasons.append(f"dim_dimtxt_non_positive({raw_dimtxt!r})")

    try:
        measured_raw = entity.get_measurement()
        measured = float(measured_raw) if isinstance(measured_raw, (int, float)) else math.nan
    except Exception:
        measured = math.nan

    disp = resolve_dimension_display(dimtype, measured, override_text, dimlfac, style)
    if dimtol_enabled and disp.claim_unit_factor != 1.0:
        # Tolerance's raw style amounts remain in native reference units. Its
        # literal output cannot establish a converted primary's tolerance units.
        reasons.append("dim_unverified_tolerance_units")
    ref_value = approved_value_mm if approved_value_mm is not None else expected_measurement
    if ref_value is None and math.isfinite(measured):
        ref_value = measured

    if disp.source == "suppressed":
        reasons.append("dim_value_suppressed")
    elif disp.source == "unsafe_placeholder":
        reasons.append("dim_placeholder_mutates_number")
    elif disp.source == "unverified_claim":
        reasons.append(f"dim_unverified_display_claim(shown={disp.text!r})")
    elif disp.source == "unverified_primary_format":
        reasons.append("dim_unverified_primary_format")
    elif disp.source == "override":
        if disp.value is None or not math.isfinite(disp.value):
            reasons.append(f"dim_override_non_numeric(shown={disp.text!r})")
        elif ref_value is not None and math.isfinite(ref_value):
            if abs(disp.value - float(ref_value)) > max(float(tolerance_mm), 1e-6):
                reasons.append(f"dim_override_disagrees(shown={disp.text!r}, expected={ref_value})")
    elif disp.source == "measurement":
        if disp.value is None or not math.isfinite(disp.value):
            reasons.append(f"dim_displayed_claim_unreadable(shown={disp.text!r})")
        else:
            allowed_tol = disp.tolerance + max(float(tolerance_mm), 1e-6)
            if ref_value is not None and math.isfinite(ref_value):
                if abs(disp.value - float(ref_value)) > allowed_tol:
                    reasons.append(f"dim_displayed_disagrees(shown={disp.text!r}, expected={ref_value})")

    expected_mtext = disp.text
    if dimtol_enabled and primary_format_unsupported:
        expected_mtext = None
    elif dimtol_enabled and disp.text is not None:
        from ezdxf.render.dim_base import Tolerance

        try:
            expected_mtext = Tolerance(override_obj).compile_mtext(disp.text)
        except (ValueError, TypeError, AttributeError):
            reasons.append("dim_unverified_tolerance_rendering")
            expected_mtext = None
    rendered = _read_rendered_block(
        doc, entity, context=context, nominal_base_height=nominal_base_height,
        expected_mtext=expected_mtext,
    )
    if rendered.hidden_text_count > 0:
        reasons.append("dim_rendered_text_hidden")
    if rendered.too_small_count > 0:
        if style.get("height_authoritative"):
            reasons.append("dim_rendered_height_mismatch")
        else:
            reasons.append("dim_unverified_render_height")
    if rendered.transparent_count > 0:
        reasons.append("dim_rendered_text_transparent")
    if rendered.unreadable_count > 0:
        reasons.append("dim_unverified_rendered_structure")

    rendered_text, group42 = rendered.text, rendered.group42
    if disp.source not in {"suppressed", "unsafe_placeholder"}:
        if disp.text is None and disp.source != "unverified_primary_format":
            reasons.append(f"dim_display_unreadable(source={disp.source})")
        if rendered.block_missing or rendered_text is None:
            reasons.append("dim_render_missing")
    if rendered_text is not None and disp.text is not None:
        have = normalize_dim_text(rendered_text)
        want = normalize_dim_text(disp.text)
        if dimtol_enabled:
            if not primary_format_unsupported:
                expected_tols = _tolerance_rendered_candidates(override_obj, disp.text)
                if expected_tols is None or have not in expected_tols:
                    reasons.append(f"dim_render_tolerance_mismatch(rendered={rendered_text!r})")
        elif have != want:
            reasons.append(f"dim_render_stale(rendered={rendered_text!r}, expected={disp.text!r})")

    # AutoCAD _SAVEAS without DIMREGEN may emit DXF group 42 = -1.0 (unpopulated sentinel).
    if group42 is not None:
        if not math.isfinite(group42):
            reasons.append("dim_group42_non_finite")
        elif group42 >= 0.0 and expected_measurement is not None and math.isfinite(expected_measurement):
            if abs(group42 - float(expected_measurement)) > max(float(tolerance_mm), 1e-4):
                reasons.append(f"dim_group42_stale(grp42={group42}, expected={expected_measurement})")

    return reasons
