"""Geometric Dimensioning and Tolerancing (GD&T) Feature Control Frame Reference Engine.

Empirical reference engine comparing:
- Strategy A: Current Production Baseline (parse_dimension_text -> _unresolved).
- Strategy B: Naive Keyword Substring Matcher (extracts symbol and first number only).
- Strategy C: Simple Pipe Splitter (splits on '|', fails on missing delimiters, modifiers, composite frames).
- Strategy D: Unified GD&T Feature Control Frame & Datum Reference System Parser (Oracle).
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Sequence


class GeometricCharacteristic(str, Enum):
    # Form (No Datum Allowed)
    STRAIGHTNESS = "STRAIGHTNESS"
    FLATNESS = "FLATNESS"
    CIRCULARITY = "CIRCULARITY"
    CYLINDRICITY = "CYLINDRICITY"
    # Profile
    PROFILE_OF_LINE = "PROFILE_OF_LINE"
    PROFILE_OF_SURFACE = "PROFILE_OF_SURFACE"
    # Orientation (Requires Datum)
    ANGULARITY = "ANGULARITY"
    PERPENDICULARITY = "PERPENDICULARITY"
    PARALLELISM = "PARALLELISM"
    # Location (Requires Datum)
    POSITION = "POSITION"
    CONCENTRICITY = "CONCENTRICITY"
    SYMMETRY = "SYMMETRY"
    # Runout (Requires Datum)
    CIRCULAR_RUNOUT = "CIRCULAR_RUNOUT"
    TOTAL_RUNOUT = "TOTAL_RUNOUT"


class ToleranceZoneShape(str, Enum):
    PLANAR = "PLANAR"
    DIAMETRIC = "DIAMETRIC"
    SPHERICAL = "SPHERICAL"


class MaterialCondition(str, Enum):
    RFS = "RFS"  # Regardless of Feature Size (Default)
    MMC = "MMC"  # Maximum Material Condition (Ⓜ)
    LMC = "LMC"  # Least Material Condition (Ⓛ)


@dataclass(frozen=True)
class DatumReference:
    letter: str  # e.g. "A", "B", "C", or compound "A-B"
    material_boundary: MaterialCondition = MaterialCondition.RFS
    order: Literal["primary", "secondary", "tertiary"] = "primary"


@dataclass(frozen=True)
class ToleranceZone:
    value: float
    shape: ToleranceZoneShape = ToleranceZoneShape.PLANAR
    material_condition: MaterialCondition = MaterialCondition.RFS
    projected_height: float | None = None
    free_state: bool = False
    tangent_plane: bool = False


@dataclass(frozen=True)
class FeatureControlFrame:
    id: str
    raw_text: str
    characteristic: GeometricCharacteristic
    tolerance_zone: ToleranceZone
    datums: tuple[DatumReference, ...] = ()
    is_composite_lower_tier: bool = False
    confidence: float = 0.98
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatumFeatureSymbol:
    id: str
    raw_text: str
    letter: str
    confidence: float = 0.99


# Symbol mappings
_CHAR_MAP: dict[str, GeometricCharacteristic] = {
    "⌖": GeometricCharacteristic.POSITION,
    "POS": GeometricCharacteristic.POSITION,
    "POSITION": GeometricCharacteristic.POSITION,
    "⏥": GeometricCharacteristic.FLATNESS,
    "FLAT": GeometricCharacteristic.FLATNESS,
    "FLATNESS": GeometricCharacteristic.FLATNESS,
    "⫽": GeometricCharacteristic.PARALLELISM,
    "PAR": GeometricCharacteristic.PARALLELISM,
    "PARALLELISM": GeometricCharacteristic.PARALLELISM,
    "⟂": GeometricCharacteristic.PERPENDICULARITY,
    "PERP": GeometricCharacteristic.PERPENDICULARITY,
    "PERPENDICULARITY": GeometricCharacteristic.PERPENDICULARITY,
    "◎": GeometricCharacteristic.CONCENTRICITY,
    "CONC": GeometricCharacteristic.CONCENTRICITY,
    "CONCENTRICITY": GeometricCharacteristic.CONCENTRICITY,
    "⌭": GeometricCharacteristic.CYLINDRICITY,
    "CYL": GeometricCharacteristic.CYLINDRICITY,
    "CYLINDRICITY": GeometricCharacteristic.CYLINDRICITY,
    "○": GeometricCharacteristic.CIRCULARITY,
    "CIRC": GeometricCharacteristic.CIRCULARITY,
    "CIRCULARITY": GeometricCharacteristic.CIRCULARITY,
    "ROUNDNESS": GeometricCharacteristic.CIRCULARITY,
    "⌓": GeometricCharacteristic.PROFILE_OF_SURFACE,
    "PROF_SURF": GeometricCharacteristic.PROFILE_OF_SURFACE,
    "PROFILE": GeometricCharacteristic.PROFILE_OF_SURFACE,
    "⌒": GeometricCharacteristic.PROFILE_OF_LINE,
    "PROF_LINE": GeometricCharacteristic.PROFILE_OF_LINE,
    "∠": GeometricCharacteristic.ANGULARITY,
    "ANG": GeometricCharacteristic.ANGULARITY,
    "ANGULARITY": GeometricCharacteristic.ANGULARITY,
    "↗": GeometricCharacteristic.CIRCULAR_RUNOUT,
    "RUNOUT": GeometricCharacteristic.CIRCULAR_RUNOUT,
    "CIRC_RUNOUT": GeometricCharacteristic.CIRCULAR_RUNOUT,
    "⌰": GeometricCharacteristic.TOTAL_RUNOUT,
    "TOT_RUNOUT": GeometricCharacteristic.TOTAL_RUNOUT,
    "TOTAL_RUNOUT": GeometricCharacteristic.TOTAL_RUNOUT,
    "⌯": GeometricCharacteristic.SYMMETRY,
    "SYMMETRY": GeometricCharacteristic.SYMMETRY,
    "-": GeometricCharacteristic.STRAIGHTNESS,
    "STR": GeometricCharacteristic.STRAIGHTNESS,
    "STRAIGHTNESS": GeometricCharacteristic.STRAIGHTNESS,
}

_MODIFIER_MAP: dict[str, MaterialCondition] = {
    "Ⓜ": MaterialCondition.MMC,
    "(M)": MaterialCondition.MMC,
    "[M]": MaterialCondition.MMC,
    "MMC": MaterialCondition.MMC,
    "Ⓛ": MaterialCondition.LMC,
    "(L)": MaterialCondition.LMC,
    "[L]": MaterialCondition.LMC,
    "LMC": MaterialCondition.LMC,
    "Ⓢ": MaterialCondition.RFS,
    "(S)": MaterialCondition.RFS,
    "[S]": MaterialCondition.RFS,
    "RFS": MaterialCondition.RFS,
}

_DATUM_FEATURE_RE = re.compile(
    r"^(?:\[-?(?P<d1>[A-Z])-?\]|DATUM\s+(?P<d2>[A-Z])|-?(?P<d3>[A-Z])-?)$",
    re.IGNORECASE,
)


def _normalize_gdt_string(text: str) -> str:
    s = text.replace("Ⓜ", " (M) ").replace("Ⓛ", " (L) ").replace("Ⓢ", " (S) ").replace("Ⓟ", " (P) ").replace("Ⓣ", " (T) ").replace("Ⓕ", " (F) ")
    s = unicodedata.normalize("NFKC", s).strip()
    s = s.replace("Ø", "⌀").replace("ø", "⌀").replace("∅", "⌀").replace("%%c", "⌀")
    s = s.replace("||", "|").replace("¦", "|")
    # Clean bracket enclosures
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1].strip()
    return s


def parse_datum_feature_symbol(text: str, text_id: str = "datum-0") -> DatumFeatureSymbol | None:
    s = text.strip()
    m = _DATUM_FEATURE_RE.fullmatch(s)
    if not m:
        return None
    letter = (m.group("d1") or m.group("d2") or m.group("d3")).upper()
    return DatumFeatureSymbol(id=text_id, raw_text=text, letter=letter)


# =========================================================================
# STRATEGY A: Current Production Baseline
# =========================================================================
def run_strategy_a(text: str) -> FeatureControlFrame | None:
    """Strategy A reproduces current production behavior: returns None for GD&T FCFs."""
    from primitive_ir_lib.dimension_symbols import parse_dimension_text
    parsed = parse_dimension_text(text)
    # If production returns _unresolved (value is None), it fails to parse FCF
    if parsed.value is None or parsed.kind_hint is None:
        return None
    return None


# =========================================================================
# STRATEGY B: Naive Keyword Substring Matcher
# =========================================================================
def run_strategy_b(text: str) -> FeatureControlFrame | None:
    """Strategy B finds symbol and first float number, ignores datums and modifiers."""
    s = _normalize_gdt_string(text)
    char = None
    for sym, c in _CHAR_MAP.items():
        if sym in s:
            char = c
            break
    if not char:
        return None

    nums = re.findall(r"\d+(?:\.\d+)?", s)
    if not nums:
        return None
    val = float(nums[0])
    shape = ToleranceZoneShape.DIAMETRIC if "⌀" in s else ToleranceZoneShape.PLANAR
    return FeatureControlFrame(
        id="fcf-strat-b",
        raw_text=text,
        characteristic=char,
        tolerance_zone=ToleranceZone(value=val, shape=shape, material_condition=MaterialCondition.RFS),
        datums=(),
        confidence=0.5,
        warnings=("Strategy B omits datums and modifiers",),
    )


# =========================================================================
# STRATEGY C: Simple Pipe Splitter
# =========================================================================
def run_strategy_c(text: str) -> FeatureControlFrame | None:
    """Strategy C splits on pipe '|', but fails on missing delimiters and complex modifiers."""
    s = _normalize_gdt_string(text)
    if "|" not in s:
        return None
    parts = [p.strip() for p in s.split("|") if p.strip()]
    if len(parts) < 2:
        return None

    char_str = parts[0].upper()
    char = _CHAR_MAP.get(char_str)
    if not char:
        return None

    tol_part = parts[1]
    nums = re.findall(r"\d+(?:\.\d+)?", tol_part)
    if not nums:
        return None
    val = float(nums[0])
    shape = ToleranceZoneShape.DIAMETRIC if "⌀" in tol_part else ToleranceZoneShape.PLANAR

    # Simple datums
    datums: list[DatumReference] = []
    order_labels: list[Literal["primary", "secondary", "tertiary"]] = ["primary", "secondary", "tertiary"]
    for i, p in enumerate(parts[2:5]):
        clean_d = re.sub(r"[^A-Z]", "", p.upper())
        if clean_d:
            datums.append(DatumReference(letter=clean_d, material_boundary=MaterialCondition.RFS, order=order_labels[i]))

    return FeatureControlFrame(
        id="fcf-strat-c",
        raw_text=text,
        characteristic=char,
        tolerance_zone=ToleranceZone(value=val, shape=shape, material_condition=MaterialCondition.RFS),
        datums=tuple(datums),
        confidence=0.75,
    )


# =========================================================================
# STRATEGY D: Unified GD&T Feature Control Frame & DRS Parser (Oracle)
# =========================================================================
class GDTFeatureControlFrameOracle:
    """Oracle parser implementing ASME Y14.5 and ISO 1101 syntax specification."""

    def __init__(self) -> None:
        pass

    def parse_fcf(self, text: str, frame_id: str = "fcf-oracle") -> FeatureControlFrame | None:
        if not text or not isinstance(text, str):
            return None
        norm = _normalize_gdt_string(text)
        if not norm:
            return None

        # Check for pipe delimiters or split by space compartments
        if "|" in norm:
            compartments = [c.strip() for c in norm.split("|") if c.strip()]
        else:
            # Fallback to token stream decomposition: e.g. "POS DIA 0.05 MMC A B C"
            tokens = norm.split()
            if len(tokens) >= 2:
                compartments = self._tokenize_compartments(tokens)
            else:
                return None

        if len(compartments) < 2:
            return None

        # Compartment 1: Characteristic
        char_raw = compartments[0].upper()
        char = _CHAR_MAP.get(char_raw)
        if not char:
            # Try prefix match or search
            for sym, c in _CHAR_MAP.items():
                if sym.upper() in char_raw:
                    char = c
                    break
        if not char:
            return None

        # Compartment 2: Tolerance Zone
        tol_raw = compartments[1]
        tol_zone = self._parse_tolerance_zone(tol_raw)
        if not tol_zone:
            return None

        # Compartments 3, 4, 5: Datum References
        datums: list[DatumReference] = []
        orders: list[Literal["primary", "secondary", "tertiary"]] = ["primary", "secondary", "tertiary"]
        for i, comp in enumerate(compartments[2:]):
            if i >= 3:
                break
            datum_ref = self._parse_datum_reference(comp, orders[i])
            if datum_ref:
                datums.append(datum_ref)

        warnings: list[str] = []
        # ASME Y14.5 rule: Form tolerances cannot have datum references
        if char in {
            GeometricCharacteristic.FLATNESS,
            GeometricCharacteristic.STRAIGHTNESS,
            GeometricCharacteristic.CIRCULARITY,
            GeometricCharacteristic.CYLINDRICITY,
        }:
            if datums:
                warnings.append(f"ASME Y14.5 violation: {char.value} is a form tolerance and cannot reference datums.")

        # Orientation and Location tolerances require at least one datum
        if char in {
            GeometricCharacteristic.ANGULARITY,
            GeometricCharacteristic.PERPENDICULARITY,
            GeometricCharacteristic.PARALLELISM,
            GeometricCharacteristic.POSITION,
            GeometricCharacteristic.CONCENTRICITY,
            GeometricCharacteristic.SYMMETRY,
            GeometricCharacteristic.CIRCULAR_RUNOUT,
            GeometricCharacteristic.TOTAL_RUNOUT,
        }:
            if not datums:
                warnings.append(f"ASME Y14.5 requirement: {char.value} requires at least a primary datum reference.")

        conf = 0.99 if not warnings else 0.85

        return FeatureControlFrame(
            id=frame_id,
            raw_text=text,
            characteristic=char,
            tolerance_zone=tol_zone,
            datums=tuple(datums),
            confidence=conf,
            warnings=tuple(warnings),
        )

    def _tokenize_compartments(self, tokens: list[str]) -> list[str]:
        """Convert tokenized words into standard FCF compartments."""
        comps: list[str] = [tokens[0]]
        # Next tokens until single letters
        tol_tokens: list[str] = []
        datum_tokens: list[str] = []
        for t in tokens[1:]:
            if len(t) == 1 and t.isalpha() and t.isupper():
                datum_tokens.append(t)
            elif any(mod in t.upper() for mod in ["(M)", "(L)", "MMC", "LMC"]):
                if datum_tokens:
                    datum_tokens[-1] += f" {t}"
                else:
                    tol_tokens.append(t)
            else:
                tol_tokens.append(t)
        comps.append(" ".join(tol_tokens))
        comps.extend(datum_tokens)
        return comps

    def _parse_tolerance_zone(self, raw: str) -> ToleranceZone | None:
        s = raw.strip()
        shape = ToleranceZoneShape.PLANAR
        if s.startswith("S⌀") or s.startswith("SØ") or "SPH" in s.upper():
            shape = ToleranceZoneShape.SPHERICAL
            s = re.sub(r"^(?:S⌀|SØ|SPH(?:ERICAL)?)\s*", "", s, flags=re.IGNORECASE)
        elif s.startswith("⌀") or "DIA" in s.upper():
            shape = ToleranceZoneShape.DIAMETRIC
            s = re.sub(r"^(?:⌀|DIA)\s*", "", s, flags=re.IGNORECASE)

        # Extract material condition modifier
        mat = MaterialCondition.RFS
        for mod_str, m_enum in _MODIFIER_MAP.items():
            if mod_str in s:
                mat = m_enum
                s = s.replace(mod_str, "")
                break

        # Extract numeric tolerance value (the primary tolerance magnitude)
        num_match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", s)
        if not num_match:
            return None
        val = float(num_match.group(0))
        if not math.isfinite(val) or val <= 0.0:
            return None
        # Remove primary tolerance value from s to prevent confusion with projected height
        s_after_val = s[: num_match.start()] + s[num_match.end() :]

        # Projected tolerance zone: (P)
        projected = None
        p_match = re.search(r"(?:\(P\)|Ⓟ|\bP\b)\s*(\d+(?:\.\d+)?)?", s_after_val)
        if p_match:
            projected = float(p_match.group(1)) if p_match.group(1) else 0.0

        free_state = "(F)" in s or "Ⓕ" in s
        tangent = "(T)" in s or "Ⓣ" in s

        return ToleranceZone(
            value=val,
            shape=shape,
            material_condition=mat,
            projected_height=projected,
            free_state=free_state,
            tangent_plane=tangent,
        )

    def _parse_datum_reference(
        self,
        raw: str,
        order: Literal["primary", "secondary", "tertiary"],
    ) -> DatumReference | None:
        s = raw.strip()
        mat = MaterialCondition.RFS
        for mod_str, m_enum in _MODIFIER_MAP.items():
            if mod_str in s:
                mat = m_enum
                s = s.replace(mod_str, "")
                break
        clean_letter = re.sub(r"[^A-Z\-]", "", s.upper()).strip()
        if not clean_letter:
            return None
        return DatumReference(letter=clean_letter, material_boundary=mat, order=order)


def run_strategy_d(text: str, frame_id: str = "fcf-oracle") -> FeatureControlFrame | None:
    """Strategy D: Full Oracle Execution."""
    oracle = GDTFeatureControlFrameOracle()
    return oracle.parse_fcf(text, frame_id)
