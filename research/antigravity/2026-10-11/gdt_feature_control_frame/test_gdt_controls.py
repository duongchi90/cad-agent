"""Controls suite for GD&T Feature Control Frame and Datum Feature Parsing.

Testing:
- Positive controls (projected tolerance zone, tangent plane, free state)
- Strong negative controls (regular dimensions immunity, general notes immunity)
- ASME Y14.5 syntax validation warnings (form tolerance datum violation, orientation missing datum)
- Datum feature symbol parsing ([-A-], [B], DATUM C)
- Spherical tolerance zone parsing (S⌀)
- Degenerate cases (empty brackets, missing characteristic, zero/negative tolerances)
- Nonfinite cases (NaN / Inf values)
"""

import sys
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from gdt_engine import (
    GeometricCharacteristic,
    MaterialCondition,
    ToleranceZoneShape,
    run_strategy_d,
    parse_datum_feature_symbol,
)


def test_positive_control_projected_tangent_free_state():
    """Positive Control: Projected zone (P 25), tangent plane (T), and free state (F)."""
    text = "[⌖ | ⌀0.05 Ⓟ 25 Ⓣ Ⓕ | A | B]"
    res = run_strategy_d(text)
    assert res is not None
    assert res.characteristic == GeometricCharacteristic.POSITION
    assert res.tolerance_zone.projected_height == 25.0
    assert res.tolerance_zone.tangent_plane is True
    assert res.tolerance_zone.free_state is True


def test_negative_control_regular_dimension_immunity():
    """Negative Control: Regular linear and diameter dimensions are NOT parsed as FCFs."""
    regular_dims = [
        "100.0 ± 0.05",
        "4x ⌀12.5 +0.02/-0.01",
        "R 25.0",
        "45°",
        "TL 1:10",
    ]
    for d in regular_dims:
        res = run_strategy_d(d)
        assert res is None, f"Regular dimension '{d}' should not be parsed as FCF"


def test_negative_control_general_notes_immunity():
    """Negative Control: General text notes are NOT parsed as FCFs."""
    notes = [
        "HEAT TREAT TO HRC 58-62",
        "MATERIAL: STRUCTURAL STEEL AISI 1045",
        "ALL UNSPECIFIED RADII R3",
        "BREAK SHARP EDGES 0.5 MAX",
    ]
    for note in notes:
        res = run_strategy_d(note)
        assert res is None, f"Text note '{note}' should not be parsed as FCF"


def test_asme_y14_5_warning_form_with_datum():
    """ASME Rule: Form tolerances (flatness, circularity) cannot have datum references."""
    text = "[⏥ | 0.05 | A]"  # Flatness with datum A violates ASME Y14.5
    res = run_strategy_d(text)
    assert res is not None
    assert res.characteristic == GeometricCharacteristic.FLATNESS
    assert len(res.warnings) > 0
    assert "form tolerance and cannot reference datums" in res.warnings[0]


def test_asme_y14_5_warning_orientation_missing_datum():
    """ASME Rule: Orientation tolerances (parallelism, perpendicularity) require datum reference."""
    text = "[⟂ | 0.02]"  # Perpendicularity without datum violates ASME Y14.5
    res = run_strategy_d(text)
    assert res is not None
    assert res.characteristic == GeometricCharacteristic.PERPENDICULARITY
    assert len(res.warnings) > 0
    assert "requires at least a primary datum" in res.warnings[0]


def test_datum_feature_symbol_parser():
    """Datum feature identifier tags: [-A-], [B], DATUM C."""
    d1 = parse_datum_feature_symbol("[-A-]")
    assert d1 is not None and d1.letter == "A"

    d2 = parse_datum_feature_symbol("[B]")
    assert d2 is not None and d2.letter == "B"

    d3 = parse_datum_feature_symbol("DATUM C")
    assert d3 is not None and d3.letter == "C"

    # Non-datum text
    assert parse_datum_feature_symbol("100.0") is None
    assert parse_datum_feature_symbol("SECTION A-A") is None


def test_spherical_tolerance_zone():
    """Spherical tolerance zone 'S⌀0.04'."""
    text = "[⌖ | S⌀0.04 | A | B]"
    res = run_strategy_d(text)
    assert res is not None
    assert res.tolerance_zone.shape == ToleranceZoneShape.SPHERICAL
    assert res.tolerance_zone.value == 0.04


def test_degenerate_and_nonfinite_rejections():
    """Degenerate & nonfinite cases safely return None."""
    assert run_strategy_d("") is None
    assert run_strategy_d("[]") is None
    assert run_strategy_d("[ | ]") is None
    assert run_strategy_d("[⌖ | -0.05 | A]") is None  # Negative tolerance rejected
    assert run_strategy_d("[⌖ | 0.0 | A]") is None   # Zero tolerance rejected
    assert run_strategy_d("[⌖ | NaN | A]") is None   # NaN tolerance rejected
    assert run_strategy_d("[⌖ | Inf | A]") is None   # Inf tolerance rejected
