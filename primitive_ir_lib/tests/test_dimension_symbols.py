from __future__ import annotations

import pytest

from primitive_ir_lib.dimension_symbols import parse_dimension_text


@pytest.mark.parametrize(
    ("text", "value", "unit", "kind", "symbol", "repeat_count"),
    [
        ("4500", 4500.0, None, None, None, None),
        ("4500 mm", 4500.0, "mm", None, None, None),
        ("⌀20", 20.0, None, "DIAMETER", "⌀", None),
        ("R12,5", 12.5, None, "RADIUS", "R", None),
        ("4x⌀10", 10.0, None, "DIAMETER", "⌀", 4),
        ("45°", 45.0, "deg", "ANGULAR", "°", None),
    ],
)
def test_parse_dimension_forms(text, value, unit, kind, symbol, repeat_count) -> None:
    parsed = parse_dimension_text(text)
    assert parsed.value == value
    assert parsed.unit == unit
    assert parsed.kind_hint == kind
    assert parsed.symbol_text == symbol
    assert parsed.repeat_count == repeat_count


def test_parse_symmetric_tolerance() -> None:
    parsed = parse_dimension_text("100 ±0.2 mm")
    assert parsed.value == 100.0
    assert parsed.unit == "mm"
    assert parsed.tolerance_mode == "SYMMETRIC"
    assert parsed.tolerance_upper == 0.2
    assert parsed.tolerance_lower == -0.2


def test_parse_plus_minus_tolerance() -> None:
    parsed = parse_dimension_text("100 +0.2/-0.1 mm")
    assert parsed.tolerance_mode == "PLUS_MINUS"
    assert parsed.tolerance_upper == 0.2
    assert parsed.tolerance_lower == -0.1


def test_default_unit_is_used_only_for_a_readable_number() -> None:
    assert parse_dimension_text("4500", default_unit="mm").unit == "mm"
    assert parse_dimension_text("8O?O", default_unit="mm").unit is None


def test_ambiguous_ocr_does_not_replace_letters_with_digits() -> None:
    parsed = parse_dimension_text("8O?O")
    assert parsed.display_text == "8O?O"
    assert parsed.value is None
    assert parsed.unit is None
    assert parsed.confidence < 0.5


def test_autocad_dimension_control_codes_parsed_correctly() -> None:
    # AutoCAD diameter code %%c / %%C
    p_diam = parse_dimension_text('%%c25')
    assert p_diam.value == 25.0
    assert p_diam.kind_hint == 'DIAMETER'
    assert p_diam.symbol_text == '⌀'

    p_diam_repeat = parse_dimension_text('4x%%C10')
    assert p_diam_repeat.value == 10.0
    assert p_diam_repeat.kind_hint == 'DIAMETER'
    assert p_diam_repeat.repeat_count == 4
    assert p_diam_repeat.symbol_text == '⌀'

    # AutoCAD degree code %%d / %%D
    p_deg = parse_dimension_text('45%%d')
    assert p_deg.value == 45.0
    assert p_deg.unit == 'deg'
    assert p_deg.kind_hint == 'ANGULAR'
    assert p_deg.symbol_text == '°'

    # AutoCAD plus-minus tolerance code %%p / %%P
    p_tol = parse_dimension_text('100 %%p0.2 mm')
    assert p_tol.value == 100.0
    assert p_tol.unit == 'mm'
    assert p_tol.tolerance_mode == 'SYMMETRIC'
    assert p_tol.tolerance_upper == 0.2
    assert p_tol.tolerance_lower == -0.2
