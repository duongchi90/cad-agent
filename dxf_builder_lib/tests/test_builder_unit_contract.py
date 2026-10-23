from __future__ import annotations

import pytest

import ezdxf
from dxf_builder_lib.builder import build_dxf
from dxf_builder_lib.reviewer import review_dxf
from primitive_ir_lib.models import (
    Calibration,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)


_SENTINEL = b"owned scratch sentinel; must remain byte-identical"


def _document(unit: object, *, status: str = "verified") -> tuple[PrimitiveIRDocument, Primitive]:
    primitive = Primitive(
        id="unit-contract-line",
        type="line",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace(bbox_px=(0.0, 0.0, 20.0, 0.0)),
        geometry=LineGeometry(Point2D(0.0, 0.0), Point2D(20.0, 0.0)),
        handle="SOURCE-HANDLE",
    )
    document = PrimitiveIRDocument(
        source_document=SourceDocument("synthetic.png", 0, 21, 1),
        calibration=Calibration(
            unit=unit,
            pixel_to_unit_scale=1.0,
            origin_px=(0.0, 0.0),
            method="manual_override",
            status=status,
        ),
        primitives=[primitive],
    )
    return document, primitive


@pytest.mark.parametrize("unit", ["cm", "m", "MM", "inch", None])
def test_non_mm_calibration_is_rejected_before_file_or_input_mutation(tmp_path, unit):
    document, primitive = _document(unit)
    primitive_before = primitive.to_dict()
    calibration_before = document.calibration.to_dict()
    output_path = tmp_path / "candidate.dxf"
    output_path.write_bytes(_SENTINEL)
    sentinel_path = tmp_path / "owned-scratch.txt"
    sentinel_path.write_bytes(_SENTINEL)

    with pytest.raises(ValueError, match="canonical millimetres"):
        build_dxf(document, str(output_path))

    assert output_path.read_bytes() == _SENTINEL
    assert sentinel_path.read_bytes() == _SENTINEL
    assert primitive.to_dict() == primitive_before
    assert document.calibration.to_dict() == calibration_before


def test_non_mm_calibration_is_rejected_before_creating_destination_directory(tmp_path):
    document, _ = _document("cm")
    output_dir = tmp_path / "not-created"

    with pytest.raises(ValueError, match="canonical millimetres"):
        build_dxf(document, str(output_dir / "candidate.dxf"))

    assert not output_dir.exists()


def test_unverified_calibration_error_keeps_precedence_over_unit_error(tmp_path):
    document, primitive = _document("cm", status="needs_verification")
    output_path = tmp_path / "candidate.dxf"

    with pytest.raises(ValueError, match="needs_verification"):
        build_dxf(document, str(output_path))

    assert not output_path.exists()
    assert primitive.handle == "SOURCE-HANDLE"


def test_mm_calibration_still_writes_and_reviews_mm_geometry(tmp_path):
    document, _ = _document("mm")
    output_path = tmp_path / "candidate.dxf"

    result = build_dxf(document, str(output_path))
    review = review_dxf(result)
    written = ezdxf.readfile(str(output_path))
    line = next(iter(written.modelspace().query("LINE")))

    assert written.header["$INSUNITS"] == 4
    assert line.dxf.start.x == 0.0
    assert line.dxf.end.x == 20.0
    assert review.passed
    assert review.checked_count == 1
