"""Admission tests for the headless DXF review tolerance policy."""

import math

import pytest

from dxf_builder_lib.builder import BuildResult
from dxf_builder_lib.reviewer import review_dxf


@pytest.mark.parametrize(
    "tolerance_mm",
    [math.nan, math.inf, -math.inf, -1.0, True, False, "1", object(), 10**1000],
    ids=["nan", "positive-infinity", "negative-infinity", "negative", "true", "false", "string", "object", "integer-overflow"],
)
def test_invalid_tolerance_is_rejected_before_dxf_path_access(tolerance_mm, tmp_path):
    missing_path = tmp_path / "does-not-exist.dxf"

    with pytest.raises(ValueError, match="tolerance_mm"):
        review_dxf(BuildResult(output_path=str(missing_path)), tolerance_mm=tolerance_mm)

    assert not missing_path.exists()


def _line_build_result(tmp_path, actual_end_x=10.0):
    ezdxf = pytest.importorskip("ezdxf")
    output_path = tmp_path / "candidate.dxf"
    doc = ezdxf.new("R2010")
    entity = doc.modelspace().add_line((0, 0), (actual_end_x, 0))
    doc.saveas(output_path)
    return BuildResult(
        output_path=str(output_path),
        handle_by_primitive_id={"line-1": entity.dxf.handle},
        layer_by_primitive_id={"line-1": "0"},
        written_geometry_by_primitive_id={
            "line-1": {"type": "line", "start": (0.0, 0.0, 0.0), "end": (10.0, 0.0, 0.0)},
        },
    )


@pytest.mark.parametrize("tolerance_mm", [None, 0, 0.25, 1.0], ids=["default", "zero", "positive-float", "positive-int"])
def test_finite_nonnegative_tolerance_preserves_matching_review(tolerance_mm, tmp_path):
    build_result = _line_build_result(tmp_path)

    result = review_dxf(build_result) if tolerance_mm is None else review_dxf(
        build_result, tolerance_mm=tolerance_mm,
    )

    assert result.passed
    assert result.checked_count == 1
    assert result.mismatches == []


def test_positive_tolerance_still_rejects_ordinary_geometry_mismatch(tmp_path):
    build_result = _line_build_result(tmp_path, actual_end_x=20.0)

    result = review_dxf(build_result, tolerance_mm=0.1)

    assert not result.passed
    assert result.checked_count == 1
    assert any("điểm cuối LINE lệch" in mismatch for mismatch in result.mismatches)


def test_nan_tolerance_cannot_turn_altered_geometry_into_false_pass(tmp_path):
    build_result = _line_build_result(tmp_path, actual_end_x=20.0)
    before = (tmp_path / "candidate.dxf").read_bytes()

    with pytest.raises(ValueError, match="tolerance_mm"):
        review_dxf(build_result, tolerance_mm=math.nan)

    assert (tmp_path / "candidate.dxf").read_bytes() == before
