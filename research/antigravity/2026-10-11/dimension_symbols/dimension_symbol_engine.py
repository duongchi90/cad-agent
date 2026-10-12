"""
dimension_symbol_engine.py — Reference Engine for Mechanical Dimension & Tolerance Parsing.

Empirically benchmarks and compares dimension text parsing strategies:
- Strategy A: Current Production Main (primitive_ir_lib/dimension_symbols.py)
- Strategy B: Naive Regex Strip (strips non-digits, loses fits, threads, chamfers)
- Strategy C: Strict Position Matcher (inflexible token ordering)
- Strategy D: Tokenized Mechanical Dimension Grammar (Selected Oracle)
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from primitive_ir_lib.dimension_symbols import (
    ParsedDimensionText,
    parse_dimension_text as run_strategy_a_parse,
)


@dataclass(frozen=True)
class EnhancedParsedDimension:
    display_text: str
    raw_text_candidates: tuple[str, ...]
    value: float | None
    unit: str | None
    kind_hint: str | None           # LINEAR, DIAMETER, RADIUS, THREAD, CHAMFER, ANGULAR, REFERENCE
    symbol_text: str | None         # ⌀, R, M, C, °
    repeat_count: int | None
    tolerance_mode: str | None      # SYMMETRIC, PLUS_MINUS, ISO_FIT, BASIC, REFERENCE
    tolerance_upper: float | None
    tolerance_lower: float | None
    fit_class: str | None           # H7, g6, k6, H7/g6, etc.
    depth_mm: float | None          # ↧ 15, DEEP 20
    is_thru: bool                   # THRU, THROUGH
    confidence: float


# ---------------------------------------------------------------------------
# Strategy B: Naive Regex Strip
# ---------------------------------------------------------------------------

def run_strategy_b_parse(text: str) -> EnhancedParsedDimension:
    """Strategy B: Blindly extracts first floating-point number, dropping all semantics."""
    clean = text.strip()
    match = re.search(r"\d+(?:\.\d+)?", clean)
    if not match:
        return EnhancedParsedDimension(
            display_text=clean,
            raw_text_candidates=(clean,),
            value=None,
            unit=None,
            kind_hint=None,
            symbol_text=None,
            repeat_count=None,
            tolerance_mode=None,
            tolerance_upper=None,
            tolerance_lower=None,
            fit_class=None,
            depth_mm=None,
            is_thru=False,
            confidence=0.1,
        )
    val = float(match.group(0))
    return EnhancedParsedDimension(
        display_text=clean,
        raw_text_candidates=(clean,),
        value=val,
        unit="mm",
        kind_hint="LINEAR",
        symbol_text=None,
        repeat_count=None,
        tolerance_mode=None,
        tolerance_upper=None,
        tolerance_lower=None,
        fit_class=None,
        depth_mm=None,
        is_thru=False,
        confidence=0.5,
    )


# ---------------------------------------------------------------------------
# Strategy C: Strict Position Matcher
# ---------------------------------------------------------------------------

def run_strategy_c_parse(text: str) -> EnhancedParsedDimension:
    """Strategy C: Hardcoded exact regexes requiring exact token ordering."""
    clean = text.strip()
    # Simple strict regex
    m = re.fullmatch(r"^(⌀|R|M)?\s*(\d+(?:\.\d+)?)\s*([A-Za-z]\d+)?$", clean)
    if not m:
        return EnhancedParsedDimension(
            display_text=clean,
            raw_text_candidates=(clean,),
            value=None,
            unit=None,
            kind_hint=None,
            symbol_text=None,
            repeat_count=None,
            tolerance_mode=None,
            tolerance_upper=None,
            tolerance_lower=None,
            fit_class=None,
            depth_mm=None,
            is_thru=False,
            confidence=0.1,
        )
    sym, val_str, fit = m.groups()
    val = float(val_str)
    kind = "DIAMETER" if sym == "⌀" else ("RADIUS" if sym == "R" else ("THREAD" if sym == "M" else "LINEAR"))
    return EnhancedParsedDimension(
        display_text=clean,
        raw_text_candidates=(clean,),
        value=val,
        unit="mm",
        kind_hint=kind,
        symbol_text=sym,
        repeat_count=None,
        tolerance_mode="ISO_FIT" if fit else None,
        tolerance_upper=None,
        tolerance_lower=None,
        fit_class=fit,
        depth_mm=None,
        is_thru=False,
        confidence=0.8,
    )


# ---------------------------------------------------------------------------
# Strategy D: Tokenized Mechanical Dimension Grammar (Selected Oracle)
# ---------------------------------------------------------------------------

_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
_UNSIGNED_NUMBER = r"(?:\d+(?:\.\d*)?|\.\d+)"
_ISO_FIT_CLASS = r"(?:[A-Z]{1,2}\d{1,2}(?:/[a-z]{1,2}\d{1,2})?|[a-z]{1,2}\d{1,2})"


def _normalize_dimension_text(text: str) -> Tuple[str, bool, bool]:
    """Normalizes Unicode symbols, comma decimals, and detects reference/basic brackets.
    Returns: (normalized_text, is_reference, is_basic).
    """
    s = unicodedata.normalize("NFKC", text).strip()
    # Unicode diameter variants
    s = s.replace("Ø", "⌀").replace("ø", "⌀").replace("∅", "⌀").replace("Φ", "⌀").replace("φ", "⌀")
    # Multiplication & minus
    s = s.replace("×", "x").replace("−", "-").replace("–", "-")
    # Decimal comma: 25,4 -> 25.4
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)

    is_reference = False
    is_basic = False

    # Reference dimension (50)
    if s.startswith("(") and s.endswith(")"):
        is_reference = True
        s = s[1:-1].strip()
    # Basic / theoretically exact dimension [50]
    elif s.startswith("[") and s.endswith("]"):
        is_basic = True
        s = s[1:-1].strip()

    # Clean whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s, is_reference, is_basic


def parse_mechanical_dimension(
    text: str,
    *,
    default_unit: str = "mm",
) -> EnhancedParsedDimension:
    """Strategy D: Comprehensive Tokenized Mechanical Dimension Grammar.

    Parses:
    - Standard Linear, Diameter (⌀, DIA), Radius (R, RAD), Spherical (S⌀, SR)
    - ISO 286 Limits and Fits (e.g. ⌀25 H7, ⌀50 g6, 30 k6, 40 H7/g6)
    - Symmetric (±0.05) & Asymmetric Tolerances (+0.05/0, 0/-0.02, +0.1/-0.05)
    - Metric Threads (M10, M8x1.25, M16-6H)
    - Chamfers (C2, C1.5, 2x45°, 1.5 x 45°)
    - Reference ((50)) & Basic ([50]) Dimensions
    - Hole Depth (↧ 15, DEEP 15, DP 15) & Through Holes (THRU, THROUGH)
    - Repeat Counts (4x ⌀10, 2 - ⌀8)
    """
    if not isinstance(text, str):
        raise TypeError("dimension text must be a string")

    display_text = text.strip()
    if not display_text:
        return EnhancedParsedDimension(
            display_text=display_text,
            raw_text_candidates=(),
            value=None,
            unit=None,
            kind_hint=None,
            symbol_text=None,
            repeat_count=None,
            tolerance_mode=None,
            tolerance_upper=None,
            tolerance_lower=None,
            fit_class=None,
            depth_mm=None,
            is_thru=False,
            confidence=0.0,
        )

    norm, is_ref, is_basic = _normalize_dimension_text(display_text)

    # 1. Check unit suffix (mm, cm, m, in, deg, °)
    unit = default_unit
    unit_m = re.search(r"\s*(mm|cm|m|in|inch(?:es)?|deg|°)\s*$", norm, re.IGNORECASE)
    if unit_m:
        u_str = unit_m.group(1).lower()
        unit = "deg" if u_str in {"deg", "°"} else ("in" if "in" in u_str else u_str)
        norm = norm[: unit_m.start()].strip()

    # 2. Check Depth & Through modifiers (↧ 15, DP 15, DEEP 15, THRU)
    depth_mm: Optional[float] = None
    is_thru = False

    thru_m = re.search(r"\b(THRU|THROUGH(?:\s+ALL)?)\b", norm, re.IGNORECASE)
    if thru_m:
        is_thru = True
        norm = (norm[: thru_m.start()] + " " + norm[thru_m.end() :]).strip()

    depth_m = re.search(rf"(?:↧|⤓|\b(?:DP|DEEP|DEPTH)\b)\s*(?P<dp>{_UNSIGNED_NUMBER})", norm, re.IGNORECASE)
    if depth_m:
        depth_val = float(depth_m.group("dp"))
        if math.isfinite(depth_val):
            depth_mm = depth_val
        norm = (norm[: depth_m.start()] + " " + norm[depth_m.end() :]).strip()

    # 3. Repeat Count prefix (e.g. "4x ⌀10", "4 x 10", "4-⌀10")
    repeat_count: Optional[int] = None
    repeat_m = re.match(r"^(?P<cnt>\d+)\s*(?:x|-)\s*(?P<body>.+)$", norm, re.IGNORECASE)
    if repeat_m and not re.match(r"^\d+\s*x\s*45", norm, re.IGNORECASE):  # Don't confuse "2x45°" chamfer with repeat count!
        repeat_count = int(repeat_m.group("cnt"))
        norm = repeat_m.group("body").strip()

    # 4. Chamfer callout (e.g. "C2", "C1.5", "2x45°", "2 x 45°")
    chamfer_m = re.match(rf"^(?:C\s*(?P<c_val>{_UNSIGNED_NUMBER})|(?P<c_val2>{_UNSIGNED_NUMBER})\s*x\s*45(?:\.0*)?°?)$", norm, re.IGNORECASE)
    if chamfer_m:
        c_str = chamfer_m.group("c_val") or chamfer_m.group("c_val2")
        val = float(c_str)
        return EnhancedParsedDimension(
            display_text=display_text,
            raw_text_candidates=(display_text,),
            value=val,
            unit=unit,
            kind_hint="CHAMFER",
            symbol_text="C",
            repeat_count=repeat_count,
            tolerance_mode=None,
            tolerance_upper=None,
            tolerance_lower=None,
            fit_class=None,
            depth_mm=depth_mm,
            is_thru=is_thru,
            confidence=0.98,
        )

    # 5. Metric Thread callout (e.g. "M10", "M8x1.25", "M16-6H", "M12 x 1.5")
    thread_m = re.match(rf"^M\s*(?P<dia>{_UNSIGNED_NUMBER})(?:\s*x\s*(?P<pitch>{_UNSIGNED_NUMBER}))?(?:\s*-\s*(?P<class>[A-Za-z0-9]+))?$", norm, re.IGNORECASE)
    if thread_m:
        t_dia = float(thread_m.group("dia"))
        t_class = thread_m.group("class")
        return EnhancedParsedDimension(
            display_text=display_text,
            raw_text_candidates=(display_text,),
            value=t_dia,
            unit=unit,
            kind_hint="THREAD",
            symbol_text="M",
            repeat_count=repeat_count,
            tolerance_mode="ISO_FIT" if t_class else None,
            tolerance_upper=None,
            tolerance_lower=None,
            fit_class=t_class,
            depth_mm=depth_mm,
            is_thru=is_thru,
            confidence=0.98,
        )

    # 6. Tolerances & Fits
    tolerance_mode: Optional[str] = None
    tolerance_upper: Optional[float] = None
    tolerance_lower: Optional[float] = None
    fit_class: Optional[str] = None

    # 6a. ISO 286 Fit Class (e.g. "H7", "g6", "k6", "H7/g6", "js6")
    # Must follow a nominal number (e.g. "25 H7")
    fit_m = re.search(rf"(?<=\d)\s*(?P<fit>{_ISO_FIT_CLASS})\s*$", norm)
    if fit_m and not re.match(rf"^(?:R|SR|M|C|IN|MM|DEG)\b", fit_m.group("fit"), re.IGNORECASE):
        fit_class = fit_m.group("fit")
        tolerance_mode = "ISO_FIT"
        norm = norm[: fit_m.start()].strip()

    # 6b. Symmetric Tolerance (±0.05, +/-0.05)
    sym_m = re.search(rf"(?:±|\+/-|\+-)\s*(?P<tol>{_UNSIGNED_NUMBER})\s*$", norm)
    if sym_m:
        tol_val = float(sym_m.group("tol"))
        tolerance_mode = "SYMMETRIC"
        tolerance_upper = abs(tol_val)
        tolerance_lower = -abs(tol_val)
        norm = norm[: sym_m.start()].strip()

    # 6c. Asymmetric / Zero-limit Tolerance (e.g. "+0.05 / 0", "0 / -0.02", "+0.05 -0.02")
    asym_m = re.search(
        rf"(?:\+(?P<u_pos>{_UNSIGNED_NUMBER})|0(?:\.0*)?)\s*(?:/|\s+)\s*(?:-(?P<l_neg>{_UNSIGNED_NUMBER})|0(?:\.0*)?)\s*$",
        norm,
    )
    if asym_m:
        u_val = float(asym_m.group("u_pos")) if asym_m.group("u_pos") else 0.0
        l_val = -float(asym_m.group("l_neg")) if asym_m.group("l_neg") else 0.0
        tolerance_mode = "PLUS_MINUS"
        tolerance_upper = u_val
        tolerance_lower = l_val
        norm = norm[: asym_m.start()].strip()

    # 7. Kind hint & Symbol prefixes (⌀, DIA, R, RAD, SR, S⌀)
    kind_hint: str = "LINEAR"
    symbol_text: Optional[str] = None

    if is_ref:
        tolerance_mode = tolerance_mode or "REFERENCE"
    elif is_basic:
        tolerance_mode = tolerance_mode or "BASIC"

    # Angular degree symbol
    if unit == "deg" or norm.endswith("°"):
        kind_hint = "ANGULAR"
        symbol_text = "°"
        unit = "deg"
        norm = norm.rstrip("°").strip()
    # Diameter
    elif re.match(r"^(?:⌀|DIA\.?|D\b)\s*", norm, re.IGNORECASE):
        kind_hint = "DIAMETER"
        symbol_text = "⌀"
        norm = re.sub(r"^(?:⌀|DIA\.?|D\b)\s*", "", norm, flags=re.IGNORECASE).strip()
    # Radius
    elif re.match(r"^(?:R|RAD\.?)\s*", norm, re.IGNORECASE):
        kind_hint = "RADIUS"
        symbol_text = "R"
        norm = re.sub(r"^(?:R|RAD\.?)\s*", "", norm, flags=re.IGNORECASE).strip()
    # Spherical Diameter / Radius
    elif re.match(r"^(?:S⌀|SDIA)\s*", norm, re.IGNORECASE):
        kind_hint = "SPHERICAL_DIAMETER"
        symbol_text = "S⌀"
        norm = re.sub(r"^(?:S⌀|SDIA)\s*", "", norm, flags=re.IGNORECASE).strip()
    elif re.match(r"^(?:SR|SRAD)\s*", norm, re.IGNORECASE):
        kind_hint = "SPHERICAL_RADIUS"
        symbol_text = "SR"
        norm = re.sub(r"^(?:SR|SRAD)\s*", "", norm, flags=re.IGNORECASE).strip()

    # 8. Core Number Parse
    num_m = re.match(rf"^{_NUMBER}$", norm)
    if not num_m:
        return EnhancedParsedDimension(
            display_text=display_text,
            raw_text_candidates=(display_text,),
            value=None,
            unit=unit,
            kind_hint=kind_hint if kind_hint != "LINEAR" else None,
            symbol_text=symbol_text,
            repeat_count=repeat_count,
            tolerance_mode=tolerance_mode,
            tolerance_upper=tolerance_upper,
            tolerance_lower=tolerance_lower,
            fit_class=fit_class,
            depth_mm=depth_mm,
            is_thru=is_thru,
            confidence=0.1,
        )

    val = float(num_m.group(0))
    if not math.isfinite(val):
        val = None

    conf = 0.99 if val is not None else 0.1
    return EnhancedParsedDimension(
        display_text=display_text,
        raw_text_candidates=(display_text,),
        value=val,
        unit=unit,
        kind_hint=kind_hint,
        symbol_text=symbol_text,
        repeat_count=repeat_count,
        tolerance_mode=tolerance_mode,
        tolerance_upper=tolerance_upper,
        tolerance_lower=tolerance_lower,
        fit_class=fit_class,
        depth_mm=depth_mm,
        is_thru=is_thru,
        confidence=conf,
    )
