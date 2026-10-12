"""
test_dimension_symbol_controls.py — Positive Fixtures & Strong Negative Controls for Dimension Symbols.

Tests:
Positive Controls:
1. Symmetrical Tolerance (100 ± 0.1 mm)
2. Angular Dimension (45°, 90 deg)
3. Spherical Radius and Diameter (SR15, S⌀30)
4. Comma Decimal with Bilateral Tolerance (75,5 +0,05 / -0,02)

Negative Controls:
5. Drawing Code (DWG-2026-A100) -> rejected (value=None).
6. Revision Date String (2026-10-12) -> rejected (value=None).
7. General Note (ALL DIMENSIONS IN MM) -> rejected (value=None).
8. Text Punctuation Noise (---, N/A, MATERIAL: STEEL) -> rejected (value=None).
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from dimension_symbol_engine import parse_mechanical_dimension


def test_positive_1_symmetrical_tolerance():
    """Positive 1: Standard linear dimension with symmetric tolerance: 100 ± 0.1 mm."""
    res = parse_mechanical_dimension("100 ± 0.1 mm")
    assert res.value == 100.0
    assert res.unit == "mm"
    assert res.tolerance_mode == "SYMMETRIC"
    assert res.tolerance_upper == 0.1
    assert res.tolerance_lower == -0.1
    assert res.confidence >= 0.98


def test_positive_2_angular_dimension():
    """Positive 2: Angular dimension callout: 45° and 90 deg."""
    res1 = parse_mechanical_dimension("45°")
    assert res1.value == 45.0
    assert res1.unit == "deg"
    assert res1.kind_hint == "ANGULAR"
    assert res1.symbol_text == "°"

    res2 = parse_mechanical_dimension("90 deg")
    assert res2.value == 90.0
    assert res2.unit == "deg"
    assert res2.kind_hint == "ANGULAR"


def test_positive_3_spherical_features():
    """Positive 3: Spherical radius (SR15) and Spherical diameter (S⌀30)."""
    res_r = parse_mechanical_dimension("SR15")
    assert res_r.value == 15.0
    assert res_r.kind_hint == "SPHERICAL_RADIUS"
    assert res_r.symbol_text == "SR"

    res_d = parse_mechanical_dimension("S⌀30")
    assert res_d.value == 30.0
    assert res_d.kind_hint == "SPHERICAL_DIAMETER"
    assert res_d.symbol_text == "S⌀"


def test_positive_4_comma_decimal_bilateral_tolerance():
    """Positive 4: European comma decimal notation: 75,5 +0,05 / -0,02."""
    res = parse_mechanical_dimension("75,5 +0,05 / -0,02")
    assert res.value == 75.5
    assert res.tolerance_upper == 0.05
    assert res.tolerance_lower == -0.02
    assert res.tolerance_mode == "PLUS_MINUS"


def test_negative_5_drawing_code():
    """Negative 5: Title block drawing code string must not parse as a dimension."""
    res = parse_mechanical_dimension("DWG-2026-A100")
    assert res.value is None
    assert res.confidence <= 0.1


def test_negative_6_revision_date_string():
    """Negative 6: ISO revision date format (2026-10-12) must not parse as dimension."""
    res = parse_mechanical_dimension("2026-10-12")
    assert res.value is None
    assert res.confidence <= 0.1


def test_negative_7_general_note():
    """Negative 7: General drawing notes must not parse as dimension."""
    res = parse_mechanical_dimension("ALL DIMENSIONS IN MM UNLESS NOTED")
    assert res.value is None
    assert res.confidence <= 0.1


def test_negative_8_punctuation_and_material_noise():
    """Negative 8: Noise strings, dashes, and material callouts."""
    assert parse_mechanical_dimension("---").value is None
    assert parse_mechanical_dimension("N/A").value is None
    assert parse_mechanical_dimension("MATERIAL: SS304").value is None
    assert parse_mechanical_dimension("SCALE 1:2").value is None
