"""Deterministic parsing of dimension text candidates."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedDimensionText:
    display_text: str
    raw_text_candidates: tuple[str, ...]
    value: float | None
    unit: str | None
    kind_hint: str | None
    symbol_text: str | None
    repeat_count: int | None
    tolerance_mode: str | None
    tolerance_upper: float | None
    tolerance_lower: float | None
    confidence: float


_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
_UNSIGNED_NUMBER = r"(?:\d+(?:\.\d*)?|\.\d+)"
_UNIT_RE = re.compile(r"\s*(mm|cm|m|in|inch(?:es)?|deg|°)\s*$", re.IGNORECASE)
_SYMMETRIC_TOLERANCE_RE = re.compile(
    rf"^(?P<base>.+?)\s*(?:±|\+/-|\+-)\s*(?P<tolerance>{_NUMBER})$"
)
_PLUS_MINUS_TOLERANCE_RE = re.compile(
    rf"^(?P<base>.+?)\s*\+(?P<upper>{_UNSIGNED_NUMBER})\s*(?:/|\s+)\s*-(?P<lower>{_UNSIGNED_NUMBER})$"
)
_REPEAT_RE = re.compile(r"^(?P<count>\d+)\s*x\s*(?P<body>.+)$", re.IGNORECASE)
_DIAMETER_RE = re.compile(rf"^⌀\s*(?P<number>{_NUMBER})$")
_RADIUS_RE = re.compile(rf"^R\s*(?P<number>{_NUMBER})$", re.IGNORECASE)
_NUMBER_RE = re.compile(rf"^{_NUMBER}$")


def _normalize_for_parse(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).strip()
    normalized = normalized.replace("Ø", "⌀").replace("ø", "⌀").replace("∅", "⌀")
    normalized = normalized.replace("×", "x").replace("−", "-")
    normalized = re.sub(r"(?<=\d),(?=\d)", ".", normalized)
    return re.sub(r"\s+", " ", normalized)


def _canonical_unit(value: str) -> str:
    key = value.casefold()
    if key in {"°", "deg"}:
        return "deg"
    if key in {"inch", "inches"}:
        return "in"
    return key


def _finite_float(value: str) -> float | None:
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _unresolved(display_text: str, *, confidence: float = 0.1) -> ParsedDimensionText:
    return ParsedDimensionText(
        display_text=display_text,
        raw_text_candidates=(display_text,) if display_text else (),
        value=None,
        unit=None,
        kind_hint=None,
        symbol_text=None,
        repeat_count=None,
        tolerance_mode=None,
        tolerance_upper=None,
        tolerance_lower=None,
        confidence=confidence,
    )


def _parse_core(body: str) -> tuple[float, str | None, str | None, int | None] | None:
    repeat_count: int | None = None
    repeat_match = _REPEAT_RE.fullmatch(body)
    if repeat_match:
        repeat_count = int(repeat_match.group("count"))
        body = repeat_match.group("body").strip()

    kind_hint: str | None = None
    symbol_text: str | None = None
    if "°" in body:
        if not body.endswith("°"):
            return None
        body = body[:-1].strip()
        kind_hint = "ANGULAR"
        symbol_text = "°"
    else:
        diameter_match = _DIAMETER_RE.fullmatch(body)
        radius_match = _RADIUS_RE.fullmatch(body)
        number_match = _NUMBER_RE.fullmatch(body)
        if diameter_match:
            number_text = diameter_match.group("number")
            kind_hint = "DIAMETER"
            symbol_text = "⌀"
        elif radius_match:
            number_text = radius_match.group("number")
            kind_hint = "RADIUS"
            symbol_text = "R"
        elif number_match:
            number_text = number_match.group(0)
        else:
            return None
        value = _finite_float(number_text)
        if value is None:
            return None
        return value, kind_hint, symbol_text, repeat_count

    value = _finite_float(body)
    if value is None:
        return None
    return value, kind_hint, symbol_text, repeat_count


def parse_dimension_text(
    text: str,
    *,
    default_unit: str | None = None,
) -> ParsedDimensionText:
    """Parse one OCR/text candidate without guessing unreadable values."""
    if not isinstance(text, str):
        raise TypeError("dimension text must be a string")

    display_text = text.strip()
    if not display_text:
        return _unresolved(display_text, confidence=0.0)

    normalized = _normalize_for_parse(display_text)
    explicit_unit: str | None = None
    degree_symbol = False
    unit_match = _UNIT_RE.search(normalized)
    if unit_match:
        degree_symbol = unit_match.group(1) == "°"
        explicit_unit = _canonical_unit(unit_match.group(1))
        normalized = normalized[: unit_match.start()].rstrip()

    tolerance_mode: str | None = None
    tolerance_upper: float | None = None
    tolerance_lower: float | None = None
    core_text = normalized

    symmetric_match = _SYMMETRIC_TOLERANCE_RE.fullmatch(normalized)
    if symmetric_match:
        tolerance = _finite_float(symmetric_match.group("tolerance"))
        if tolerance is None:
            return _unresolved(display_text)
        tolerance_mode = "SYMMETRIC"
        tolerance_upper = abs(tolerance)
        tolerance_lower = -abs(tolerance)
        core_text = symmetric_match.group("base").strip()
    else:
        plus_minus_match = _PLUS_MINUS_TOLERANCE_RE.fullmatch(normalized)
        if plus_minus_match:
            upper = _finite_float(plus_minus_match.group("upper"))
            lower = _finite_float(plus_minus_match.group("lower"))
            if upper is None or lower is None:
                return _unresolved(display_text)
            tolerance_mode = "PLUS_MINUS"
            tolerance_upper = abs(upper)
            tolerance_lower = -abs(lower)
            core_text = plus_minus_match.group("base").strip()

    parsed_core = _parse_core(core_text)
    if parsed_core is None:
        return _unresolved(display_text)

    value, kind_hint, symbol_text, repeat_count = parsed_core
    if explicit_unit == "deg" and kind_hint is None:
        kind_hint = "ANGULAR"
        if degree_symbol:
            symbol_text = "°"
    if explicit_unit is not None:
        unit = explicit_unit
    elif kind_hint == "ANGULAR":
        unit = "deg"
    elif default_unit is not None and default_unit.strip():
        unit = default_unit.strip()
    else:
        unit = None

    confidence = 0.99 if display_text == normalized else 0.98
    return ParsedDimensionText(
        display_text=display_text,
        raw_text_candidates=(display_text,),
        value=value,
        unit=unit,
        kind_hint=kind_hint,
        symbol_text=symbol_text,
        repeat_count=repeat_count,
        tolerance_mode=tolerance_mode,
        tolerance_upper=tolerance_upper,
        tolerance_lower=tolerance_lower,
        confidence=confidence,
    )


__all__ = ["ParsedDimensionText", "parse_dimension_text"]
