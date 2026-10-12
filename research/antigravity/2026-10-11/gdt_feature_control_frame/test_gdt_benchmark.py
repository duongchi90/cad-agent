"""Benchmark suite comparing Strategies A, B, C, and D across 8 engineering GD&T scenarios."""

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
    run_strategy_a,
    run_strategy_b,
    run_strategy_c,
    run_strategy_d,
)


def test_scenario_1_position_tolerance_mmc():
    """Scenario 1: True position at MMC with datums A, B, C."""
    text = "[⌖ | ⌀0.05 Ⓜ | A | B Ⓜ | C]"

    res_a = run_strategy_a(text)
    res_b = run_strategy_b(text)
    res_c = run_strategy_c(text)
    res_d = run_strategy_d(text)

    assert res_a is None  # Production fails

    assert res_b is not None
    assert res_b.datums == ()  # Strategy B misses all datums

    assert res_c is not None
    assert res_c.tolerance_zone.material_condition == MaterialCondition.RFS  # Strategy C misses MMC modifier

    assert res_d is not None
    assert res_d.characteristic == GeometricCharacteristic.POSITION
    assert res_d.tolerance_zone.value == 0.05
    assert res_d.tolerance_zone.shape == ToleranceZoneShape.DIAMETRIC
    assert res_d.tolerance_zone.material_condition == MaterialCondition.MMC
    assert len(res_d.datums) == 3
    assert res_d.datums[0].letter == "A"
    assert res_d.datums[1].letter == "B"
    assert res_d.datums[1].material_boundary == MaterialCondition.MMC
    assert res_d.datums[2].letter == "C"
    assert res_d.confidence > 0.95


def test_scenario_2_perpendicularity():
    """Scenario 2: Perpendicularity to Datums A and B."""
    text = "[⟂ | 0.02 | A | B]"

    res_d = run_strategy_d(text)
    assert res_d is not None
    assert res_d.characteristic == GeometricCharacteristic.PERPENDICULARITY
    assert res_d.tolerance_zone.value == 0.02
    assert res_d.tolerance_zone.shape == ToleranceZoneShape.PLANAR
    assert len(res_d.datums) == 2
    assert res_d.datums[0].letter == "A"
    assert res_d.datums[1].letter == "B"


def test_scenario_3_flatness_form_tolerance():
    """Scenario 3: Flatness form tolerance without datums."""
    text = "[⏥ | 0.03]"

    res_d = run_strategy_d(text)
    assert res_d is not None
    assert res_d.characteristic == GeometricCharacteristic.FLATNESS
    assert res_d.tolerance_zone.value == 0.03
    assert res_d.datums == ()
    assert not res_d.warnings  # Complies with ASME Y14.5 (no datums on form)


def test_scenario_4_cylindricity_bearing_journal():
    """Scenario 4: Cylindricity of precision shaft journal."""
    text = "[⌭ | 0.015]"

    res_d = run_strategy_d(text)
    assert res_d is not None
    assert res_d.characteristic == GeometricCharacteristic.CYLINDRICITY
    assert res_d.tolerance_zone.value == 0.015
    assert res_d.datums == ()


def test_scenario_5_profile_of_surface_compound_datum():
    """Scenario 5: Profile of surface with compound datum A-B and tertiary C."""
    text = "[⌓ | 0.1 | A-B | C]"

    res_d = run_strategy_d(text)
    assert res_d is not None
    assert res_d.characteristic == GeometricCharacteristic.PROFILE_OF_SURFACE
    assert res_d.tolerance_zone.value == 0.1
    assert len(res_d.datums) == 2
    assert res_d.datums[0].letter == "A-B"
    assert res_d.datums[1].letter == "C"


def test_scenario_6_concentricity_coaxiality():
    """Scenario 6: Concentricity of center bore to Datum A."""
    text = "[◎ | ⌀0.02 | A]"

    res_d = run_strategy_d(text)
    assert res_d is not None
    assert res_d.characteristic == GeometricCharacteristic.CONCENTRICITY
    assert res_d.tolerance_zone.value == 0.02
    assert res_d.tolerance_zone.shape == ToleranceZoneShape.DIAMETRIC
    assert len(res_d.datums) == 1
    assert res_d.datums[0].letter == "A"


def test_scenario_7_circular_runout():
    """Scenario 7: Circular runout of flange face to Datum A."""
    text = "[↗ | 0.04 | A]"

    res_d = run_strategy_d(text)
    assert res_d is not None
    assert res_d.characteristic == GeometricCharacteristic.CIRCULAR_RUNOUT
    assert res_d.tolerance_zone.value == 0.04
    assert len(res_d.datums) == 1
    assert res_d.datums[0].letter == "A"


def test_scenario_8_tokenized_ascii_gdt():
    """Scenario 8: Tokenized ASCII GD&T representation 'POS DIA 0.08 MMC A B'."""
    text = "POS DIA 0.08 MMC A B"

    res_c = run_strategy_c(text)
    res_d = run_strategy_d(text)

    # Strategy C fails because no pipe delimiters exist
    assert res_c is None

    # Strategy D successfully parses token stream
    assert res_d is not None
    assert res_d.characteristic == GeometricCharacteristic.POSITION
    assert res_d.tolerance_zone.value == 0.08
    assert res_d.tolerance_zone.shape == ToleranceZoneShape.DIAMETRIC
    assert res_d.tolerance_zone.material_condition == MaterialCondition.MMC
    assert len(res_d.datums) == 2
    assert res_d.datums[0].letter == "A"
    assert res_d.datums[1].letter == "B"
