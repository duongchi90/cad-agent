from __future__ import annotations

from primitive_ir_lib.calibration import auto_estimate_calibration
from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.text_extraction import RawText, classify_semantic_role


def _candidate_pair(value: str, center_x: float, line_length: float, suffix: str):
    role, parsed_value = classify_semantic_role(value)
    text = RawText(
        id=f"text-{suffix}",
        content=value,
        bbox_px=(center_x - 5, 45, center_x + 5, 55),
        rotation_deg=0.0,
        confidence=1.0,
        source="text_vision",
        parsed_value=parsed_value,
        semantic_role=role,
    )
    line = RawLine(
        id=f"line-{suffix}",
        p1_px=(center_x - line_length / 2, 60),
        p2_px=(center_x + line_length / 2, 60),
        confidence=1.0,
        bbox_px=(center_x - line_length / 2, 60, center_x + line_length / 2, 60),
    )
    return text, line


def _estimate(pairs, *, require_consensus: bool = False):
    texts = [text for text, _line in pairs]
    lines = [line for _text, line in pairs]
    return auto_estimate_calibration(
        texts,
        lines,
        image_height_px=200,
        require_consensus=require_consensus,
    )


def test_zero_dimension_first_does_not_hide_later_usable_reference():
    zero = _candidate_pair("00.00", 300, 100, "zero")
    valid = _candidate_pair("1000", 600, 500, "valid")

    calibration = _estimate([zero, valid])

    assert calibration is not None
    assert calibration.pixel_to_unit_scale == 2.0
    assert calibration.status == "needs_verification"


def test_all_zero_dimensions_abstain_instead_of_returning_zero_scale():
    zero = _candidate_pair("00.00", 300, 100, "zero")

    calibration = _estimate([zero])

    assert calibration is None


def test_valid_only_reference_remains_usable():
    valid = _candidate_pair("1000", 300, 500, "valid")

    calibration = _estimate([valid])

    assert calibration is not None
    assert calibration.pixel_to_unit_scale == 2.0
    assert calibration.status == "needs_verification"


def test_valid_reference_before_zero_preserves_valid_first_selection():
    valid = _candidate_pair("1000", 300, 500, "valid")
    zero = _candidate_pair("00.00", 600, 100, "zero")

    calibration = _estimate([valid, zero])

    assert calibration is not None
    assert calibration.pixel_to_unit_scale == 2.0
    assert calibration.status == "needs_verification"


def test_default_ordering_between_usable_references_is_preserved():
    first = _candidate_pair("1200", 300, 400, "first")
    second = _candidate_pair("1000", 600, 500, "second")

    calibration = _estimate([first, second])

    assert calibration is not None
    assert calibration.pixel_to_unit_scale == 3.0
    assert calibration.status == "needs_verification"
