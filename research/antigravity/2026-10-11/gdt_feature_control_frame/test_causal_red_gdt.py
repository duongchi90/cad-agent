"""Causal RED tests for GD&T Feature Control Frame and Datum Reference Parsing.

These tests exercise CURRENT production code in:
- primitive_ir_lib/dimension_symbols.py
- semantic_ir_lib/models.py
- cad_agent/fidelity.py

Demonstrating the exact production gaps:
1. True position Feature Control Frame "[⌖ | ⌀0.05 Ⓜ | A | B | C]" returns _unresolved (confidence 0.1, value None).
2. Orientation tolerances (Parallelism "⫽ | 0.02 | A", Perpendicularity "⟂ | 0.01 | A") return _unresolved.
3. Form tolerances (Flatness "⏥ | 0.03", Cylindricity "⌭ | 0.02") return _unresolved.
4. Datum feature callouts "[-A-]" return _unresolved.
5. semantic_ir_lib/models.py ConstraintType omits all GD&T feature control and datum tolerance types.
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

from primitive_ir_lib.dimension_symbols import parse_dimension_text
from semantic_ir_lib.models import ConstraintType


def test_red_position_tolerance_fcf_unresolved():
    """RED 1: True position FCF is completely unrecognized by parse_dimension_text."""
    parsed = parse_dimension_text("⌖ | ⌀0.05 Ⓜ | A | B | C")
    assert parsed.value is None
    assert parsed.kind_hint is None
    assert parsed.confidence == 0.1  # Returns _unresolved() stub


def test_red_parallelism_and_perpendicularity_fcf_unresolved():
    """RED 2: Orientation tolerances (parallelism, perpendicularity) return unresolved stubs."""
    parsed_par = parse_dimension_text("⫽ | 0.02 | A")
    assert parsed_par.value is None
    assert parsed_par.confidence == 0.1

    parsed_perp = parse_dimension_text("⟂ | 0.01 | A | B")
    assert parsed_perp.value is None
    assert parsed_perp.confidence == 0.1


def test_red_flatness_and_cylindricity_form_tolerances_unresolved():
    """RED 3: Form tolerances (flatness, cylindricity) return unresolved stubs."""
    parsed_flat = parse_dimension_text("⏥ | 0.03")
    assert parsed_flat.value is None
    assert parsed_flat.confidence == 0.1

    parsed_cyl = parse_dimension_text("⌭ | 0.02")
    assert parsed_cyl.value is None
    assert parsed_cyl.confidence == 0.1


def test_red_datum_feature_symbol_unresolved():
    """RED 4: Datum feature symbols '[-A-]' or '[A]' return unresolved stubs."""
    parsed_datum = parse_dimension_text("[-A-]")
    assert parsed_datum.value is None
    assert parsed_datum.confidence == 0.1


def test_red_semantic_constraint_model_lacks_gdt_types():
    """RED 5: semantic_ir_lib/models.py ConstraintType literal lacks GD&T types."""
    import typing
    constraint_types = typing.get_args(ConstraintType)
    assert "position_tolerance" not in constraint_types
    assert "feature_control_frame" not in constraint_types
    assert "datum_reference" not in constraint_types
    assert "profile_tolerance" not in constraint_types
