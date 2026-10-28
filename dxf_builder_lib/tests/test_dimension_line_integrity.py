from __future__ import annotations

import ezdxf
import pytest

from dxf_builder_lib.builder import build_dxf
from dxf_builder_lib.reviewer import review_dxf_with_dimension_line_integrity
from primitive_ir_lib.models import (
    Calibration, CrossValidation, LineGeometry, Point2D, Primitive,
    PrimitiveIRDocument, SourceDocument, Trace,
)


def _document() -> PrimitiveIRDocument:
    line = Primitive(
        id="line-1", type="line", source="geometry_opencv", confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 100, 10)),
        geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(100, 0)),
    )
    return PrimitiveIRDocument(
        source_document=SourceDocument(file_name="synthetic.png", page_index=0,
                                       image_width_px=100, image_height_px=20),
        calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0,
                                origin_px=(0, 0), method="manual_override"),
        primitives=[line],
        cross_validations=[CrossValidation(
            text_primitive_id="text-1", geometry_primitive_id="line-1",
            status="confirmed", text_value=100.0,
            geometry_measured_length=100.0, delta_percent=0.0,
        )],
    )


def test_opt_in_capture_detects_deleted_dimension_definition_line(tmp_path):
    built = build_dxf(
        _document(), str(tmp_path / "candidate.dxf"), build_dimensions=True,
        capture_dimension_line_integrity=True,
    )
    assert built.dimension_line_expectations
    assert len(built.dimension_line_expectations) == 1
    assert review_dxf_with_dimension_line_integrity(built).passed

    doc = ezdxf.readfile(built.output_path)
    block_name = built.dimension_line_expectations[0].block_name
    block = doc.blocks[block_name]
    lines = [entity for entity in block if entity.dxftype() == "LINE"]
    assert lines
    block.delete_entity(lines[0])
    doc.saveas(built.output_path)

    result = review_dxf_with_dimension_line_integrity(built)
    assert result.qualification == "FAILED"
    assert any("LINE" in item for item in result.mismatches)


@pytest.mark.parametrize("change,qualification", [
    ("alter", "FAILED"), ("duplicate", "FAILED"),
    ("reverse", "QUALIFIED"), ("within", "QUALIFIED"),
    ("outside", "FAILED"), ("unsupported_extrusion", "UNKNOWN"),
    ("reassociate", "UNKNOWN"),
])
def test_integrity_review_classifies_line_and_frame_changes(tmp_path, change, qualification):
    built = build_dxf(
        _document(), str(tmp_path / f"{change}.dxf"), build_dimensions=True,
        capture_dimension_line_integrity=True,
    )
    expectation = built.dimension_line_expectations[0]
    doc = ezdxf.readfile(built.output_path)
    dimension = doc.entitydb[expectation.dimension_handle]
    block = doc.blocks[expectation.block_name]
    line = next(entity for entity in block if entity.dxftype() == "LINE")
    start, end = line.dxf.start, line.dxf.end
    if change == "alter":
        line.dxf.end = (end.x + 0.01, end.y, end.z)
    elif change == "duplicate":
        block.add_entity(line.copy())
    elif change == "reverse":
        line.dxf.start, line.dxf.end = end, start
    elif change in {"within", "outside"}:
        delta = 0.5e-6 if change == "within" else 2e-6
        line.dxf.end = (end.x + delta, end.y, end.z)
    elif change == "unsupported_extrusion":
        dimension.dxf.extrusion = (0, 0, -1)
    elif change == "reassociate":
        dimension.dxf.geometry = "*D999"
    doc.saveas(built.output_path)

    result = review_dxf_with_dimension_line_integrity(built)
    assert result.qualification == qualification
    assert result.passed is (qualification == "QUALIFIED")


def test_nonzero_dimension_insert_is_unknown_with_unchanged_anonymous_block_lines(tmp_path):
    built = build_dxf(
        _document(), str(tmp_path / "insert-transform.dxf"), build_dimensions=True,
        capture_dimension_line_integrity=True,
    )
    expectation = built.dimension_line_expectations[0]
    doc = ezdxf.readfile(built.output_path)
    dimension = doc.entitydb[expectation.dimension_handle]
    block = doc.blocks[expectation.block_name]
    lines_before = [
        (tuple(entity.dxf.start), tuple(entity.dxf.end))
        for entity in block if entity.dxftype() == "LINE"
    ]

    dimension.dxf.insert = (7.0, 11.0, 0.0)
    doc.saveas(built.output_path)

    reopened = ezdxf.readfile(built.output_path)
    reopened_lines = [
        (tuple(entity.dxf.start), tuple(entity.dxf.end))
        for entity in reopened.blocks[expectation.block_name]
        if entity.dxftype() == "LINE"
    ]
    assert reopened_lines == lines_before
    result = review_dxf_with_dimension_line_integrity(built)
    assert result.qualification == "UNKNOWN"
    assert any("insert" in item.lower() for item in result.mismatches)


def test_missing_ephemeral_expectation_is_unknown_and_legacy_review_stays_passed(tmp_path):
    built = build_dxf(
        _document(), str(tmp_path / "legacy.dxf"), build_dimensions=True,
        capture_dimension_line_integrity=True,
    )
    assert review_dxf_with_dimension_line_integrity(built).passed
    built.dimension_line_expectations = None
    assert review_dxf_with_dimension_line_integrity(built).qualification == "UNKNOWN"


def test_matching_uses_augmenting_path_for_greedy_trap():
    from dxf_builder_lib.reviewer import _has_complete_line_matching

    expected = (
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ((0.9, 0.0, 0.0), (1.9, 0.0, 0.0)),
    )
    actual = (
        ((0.85, 0.0, 0.0), (1.85, 0.0, 0.0)),
        ((-0.8, 0.0, 0.0), (0.2, 0.0, 0.0)),
    )
    assert _has_complete_line_matching(expected, actual, 0.9)


def test_nonfinite_expectation_and_unsupported_dimension_type_are_unknown(tmp_path):
    from dataclasses import replace

    built = build_dxf(
        _document(), str(tmp_path / "unsupported.dxf"), build_dimensions=True,
        capture_dimension_line_integrity=True,
    )
    expectation = built.dimension_line_expectations[0]
    first = expectation.line_endpoints[0]
    bad_line = ((float("nan"), *first[0][1:]), first[1])
    built.dimension_line_expectations = (replace(
        expectation, line_endpoints=(bad_line, *expectation.line_endpoints[1:]),
    ),)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "UNKNOWN"

    built.dimension_line_expectations = (expectation,)
    doc = ezdxf.readfile(built.output_path)
    doc.entitydb[expectation.dimension_handle].dxf.dimtype = 2
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "UNKNOWN"


def test_capture_requires_dimensions_before_output_creation(tmp_path):
    output = tmp_path / "must-not-exist.dxf"
    with pytest.raises(ValueError, match="build_dimensions"):
        build_dxf(_document(), str(output), capture_dimension_line_integrity=True)
    assert not output.exists()


def test_capture_resource_limit_fails_closed_before_save(tmp_path, monkeypatch):
    # The approved cap is enforced by the owner; this test pins its public failure.
    from dxf_builder_lib import builder

    output = tmp_path / "must-not-exist.dxf"
    monkeypatch.setattr(builder, "_MAX_DIMENSION_LINE_EXPECTATIONS", 0, raising=False)
    with pytest.raises(ValueError, match="resource|limit|capture"):
        build_dxf(
            _document(), str(output), build_dimensions=True,
            capture_dimension_line_integrity=True,
        )
    assert not output.exists()


def test_capture_line_resource_limit_fails_before_save(tmp_path, monkeypatch):
    from dxf_builder_lib import builder

    output = tmp_path / "line-limit.dxf"
    monkeypatch.setattr(builder, "_MAX_LINES_PER_DIMENSION_EXPECTATION", 0)
    with pytest.raises(ValueError, match="incomplete|resource limit"):
        build_dxf(
            _document(), str(output), build_dimensions=True,
            capture_dimension_line_integrity=True,
        )
    assert not output.exists()


def test_zero_dimensions_cannot_qualify(tmp_path):
    document = _document()
    document.cross_validations = []
    output = tmp_path / "zero-dimensions.dxf"
    with pytest.raises(ValueError, match="zero dimensions"):
        build_dxf(document, str(output), build_dimensions=True,
                  capture_dimension_line_integrity=True)
    assert not output.exists()
