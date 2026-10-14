from __future__ import annotations

import inspect
import math

import pytest

from dxf_builder_lib.builder import NativeLinearDimensionSpec, build_dxf
from primitive_ir_lib.models import (
    Calibration,
    CircleGeometry,
    CrossValidation,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    TextData,
    Trace,
)


def _line(primitive_id: str, start: tuple[float, float], end: tuple[float, float]) -> Primitive:
    return Primitive(
        id=primitive_id,
        type="line",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 40, 10)),
        geometry=LineGeometry(
            start=Point2D(*start),
            end=Point2D(*end),
        ),
    )


def _document(*primitives: Primitive) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(
            file_name="synthetic-dimension-placement.png",
            page_index=0,
            image_width_px=100,
            image_height_px=100,
        ),
        calibration=Calibration(
            unit="mm",
            pixel_to_unit_scale=1.0,
            origin_px=(0, 0),
            method="manual_override",
        ),
        primitives=list(primitives),
    )


def _fixture(*, sides: tuple[int, ...] = (1,)) -> PrimitiveIRDocument:
    measured = _line("measured", (0.0, 0.0), (40.0, 0.0))
    neighbors = [
        _line(f"neighbor-{side}", (-5.0, side * 5.0), (45.0, side * 5.0))
        for side in sides
    ]
    return _document(measured, *neighbors)


def _build(document, path, policy=None):
    kwargs = {"build_dimensions": True, "dimension_specs": [
        NativeLinearDimensionSpec(
            id="DIM-40",
            geometry_primitive_id="measured",
            approved_value_mm=40.0,
            source_ref="synthetic-approved-40mm",
        ),
    ]}
    if policy is not None:
        kwargs["dimension_placement_policy"] = policy
    return build_dxf(document, str(path), **kwargs)


def _dimension_and_graphics(path):
    import ezdxf

    drawing = ezdxf.readfile(path)
    dimensions = [entity for entity in drawing.modelspace() if entity.dxftype() == "DIMENSION"]
    assert len(dimensions) == 1
    dimension = dimensions[0]
    lines = [
        (tuple(entity.dxf.start), tuple(entity.dxf.end))
        for entity in dimension.virtual_entities()
        if entity.dxftype() == "LINE"
    ]
    return drawing, dimension, lines


def _has_positive_horizontal_overlap(segments, y: float, start_x: float, end_x: float) -> bool:
    for first, second in segments:
        if abs(first[1] - second[1]) > 1e-6 or abs(first[1] - y) > 1e-6:
            continue
        shared = min(max(first[0], second[0]), end_x) - max(min(first[0], second[0]), start_x)
        if shared > 1e-6:
            return True
    return False


def _positive_collinear_overlap(segment, obstacle_start, obstacle_end) -> bool:
    tolerance = 1e-6
    ax, ay = segment[0][0], segment[0][1]
    bx, by = segment[1][0], segment[1][1]
    cx, cy = obstacle_start
    dx, dy = obstacle_end
    ux, uy = bx - ax, by - ay
    vx, vy = dx - cx, dy - cy
    length = math.hypot(ux, uy)
    obstacle_length = math.hypot(vx, vy)
    if length <= tolerance or obstacle_length <= tolerance:
        return False
    if max(abs(ux * (py - ay) - uy * (px - ax)) / length for px, py in ((cx, cy), (dx, dy))) > tolerance:
        return False
    if abs(ux * vy - uy * vx) / length > tolerance:
        return False
    first_interval = (0.0, length)
    second_projection = (
        ((cx - ax) * ux + (cy - ay) * uy) / length,
        ((dx - ax) * ux + (dy - ay) * uy) / length,
    )
    overlap = min(first_interval[1], max(second_projection)) - max(first_interval[0], min(second_projection))
    return overlap > tolerance


def _anonymous_dimension_blocks(drawing):
    return {
        block.name
        for block in drawing.blocks
        if block.name.startswith("*D")
    }


def test_builder_exposes_exact_opt_in_policy_and_keeps_legacy_default():
    parameter = inspect.signature(build_dxf).parameters.get("dimension_placement_policy")

    assert parameter is not None
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default == "legacy"


def test_legacy_default_preserves_current_overlapping_side(tmp_path):
    result = _build(_fixture(), tmp_path / "legacy.dxf")
    drawing, dimension, lines = _dimension_and_graphics(result.output_path)

    assert dimension.get_measurement() == pytest.approx(40.0)
    assert _has_positive_horizontal_overlap(lines, 5.0, -5.0, 45.0)
    assert len(_anonymous_dimension_blocks(drawing)) == 1


def test_clear_legacy_placement_remains_on_existing_side(tmp_path):
    result = _build(_document(_line("measured", (0.0, 0.0), (40.0, 0.0))), tmp_path / "clear-legacy.dxf")
    _, dimension, lines = _dimension_and_graphics(result.output_path)

    assert dimension.get_measurement() == pytest.approx(40.0)
    assert any(abs(first[1] - 5.0) <= 1e-6 and abs(second[1] - 5.0) <= 1e-6 for first, second in lines)
    assert not any(abs(first[1] + 5.0) <= 1e-6 and abs(second[1] + 5.0) <= 1e-6 for first, second in lines)


def test_opt_in_uses_opposed_side_when_current_side_overlaps_source_line(tmp_path):
    document = _fixture()
    result = _build(document, tmp_path / "opposed.dxf", "avoid_source_line_overlap_v1")
    drawing, dimension, lines = _dimension_and_graphics(result.output_path)

    assert not _has_positive_horizontal_overlap(lines, 5.0, -5.0, 45.0)
    assert dimension.get_measurement() == pytest.approx(40.0)
    assert result.written_geometry_by_primitive_id["measured"] == {
        "type": "line", "start": (0.0, 0.0), "end": (40.0, 0.0),
    }
    assert len([entity for entity in drawing.modelspace() if entity.dxftype() == "DIMENSION"]) == 1
    assert _anonymous_dimension_blocks(drawing) == {dimension.dxf.geometry}


def test_opt_in_fails_before_save_when_both_sides_are_blocked(tmp_path):
    output = tmp_path / "both-blocked.dxf"

    with pytest.raises(ValueError, match="blocked|overlap"):
        _build(_fixture(sides=(-1, 1)), output, "avoid_source_line_overlap_v1")

    assert not output.exists()


@pytest.mark.parametrize("policy", ["avoid_source_line_overlap", "Avoid_Source_Line_Overlap_V1", "unknown"])
def test_policy_rejects_aliases_and_unknown_values_before_output(tmp_path, policy):
    document = _fixture()
    output = tmp_path / "invalid-policy.dxf"

    with pytest.raises(ValueError, match="dimension placement policy"):
        _build(document, output, policy)

    assert not output.exists()
    assert all(primitive.handle is None for primitive in document.primitives)


def test_nonlegacy_policy_requires_dimensions_enabled(tmp_path):
    document = _fixture()
    output = tmp_path / "dimensions-disabled.dxf"

    with pytest.raises(ValueError, match="build_dimensions"):
        build_dxf(
            document,
            str(output),
            dimension_placement_policy="avoid_source_line_overlap_v1",
        )

    assert not output.exists()
    assert all(primitive.handle is None for primitive in document.primitives)


def test_endpoint_only_touch_is_not_positive_overlap(tmp_path):
    document = _document(
        _line("measured", (0.0, 0.0), (40.0, 0.0)),
        _line("touching-neighbor", (19.0, 5.0), (20.0, 5.0)),
    )
    result = _build(document, tmp_path / "touch-only.dxf", "avoid_source_line_overlap_v1")
    _, dimension, lines = _dimension_and_graphics(result.output_path)

    assert dimension.get_measurement() == pytest.approx(40.0)
    assert any(
        abs(point[0] - 19.0) <= 1e-6 and abs(point[1] - 5.0) <= 1e-6
        for segment in lines
        for point in segment
    )
    assert not any(
        _positive_collinear_overlap(segment, (19.0, 5.0), (20.0, 5.0))
        for segment in lines
    )


@pytest.mark.parametrize(
    "translation,angle_deg,reverse,mirror_side",
    [
        ((0.0, 0.0), 0.0, False, 1),
        ((123.0, -48.0), 90.0, False, 1),
        ((-70.0, 23.0), 30.0, True, 1),
        ((18.0, 95.0), -45.0, False, -1),
    ],
)
def test_opposed_side_policy_preserves_measurement_under_transforms(
    tmp_path, translation, angle_deg, reverse, mirror_side,
):
    theta = math.radians(angle_deg)
    tx, ty = translation
    unit = (math.cos(theta), math.sin(theta))
    normal = (-unit[1], unit[0])
    start = (tx, ty)
    end = (tx + 40.0 * unit[0], ty + 40.0 * unit[1])
    if reverse:
        start, end = end, start
        normal = (-normal[0], -normal[1])
    neighbor_start = (
        start[0] - 5.0 * ((end[0] - start[0]) / 40.0) + 5.0 * mirror_side * normal[0],
        start[1] - 5.0 * ((end[1] - start[1]) / 40.0) + 5.0 * mirror_side * normal[1],
    )
    neighbor_end = (
        end[0] + 5.0 * ((end[0] - start[0]) / 40.0) + 5.0 * mirror_side * normal[0],
        end[1] + 5.0 * ((end[1] - start[1]) / 40.0) + 5.0 * mirror_side * normal[1],
    )
    document = _document(
        _line("measured", start, end),
        _line("neighbor", neighbor_start, neighbor_end),
    )
    result = _build(document, tmp_path / f"transformed-{angle_deg}-{reverse}-{mirror_side}.dxf", "avoid_source_line_overlap_v1")
    _, dimension, rendered_lines = _dimension_and_graphics(result.output_path)

    assert dimension.get_measurement() == pytest.approx(40.0, abs=1e-6)
    assert result.written_geometry_by_primitive_id["measured"]["start"] == start
    assert result.written_geometry_by_primitive_id["measured"]["end"] == end
    assert not any(
        _positive_collinear_overlap(segment, neighbor_start, neighbor_end)
        for segment in rendered_lines
    )


def test_nonfinite_measured_line_fails_closed_before_save(tmp_path):
    document = _document(_line("measured", (0.0, 0.0), (math.inf, 0.0)))
    output = tmp_path / "nonfinite-measurement.dxf"

    with pytest.raises(ValueError):
        _build(document, output, "avoid_source_line_overlap_v1")

    assert not output.exists()


def test_zero_length_measurement_is_rejected_only_by_opt_in_policy(tmp_path):
    def zero_length_document():
        document = _document(_line("measured", (0.0, 0.0), (0.0, 0.0)))
        document.cross_validations.append(
            CrossValidation(
                text_primitive_id="dimension-text",
                geometry_primitive_id="measured",
                status="confirmed",
                text_value=0.0,
                geometry_measured_length=0.0,
                delta_percent=0.0,
            )
        )
        return document

    opt_in_output = tmp_path / "zero-opt-in.dxf"
    with pytest.raises(ValueError, match="zero-length|invalid.*LINE"):
        build_dxf(
            zero_length_document(),
            str(opt_in_output),
            build_dimensions=True,
            dimension_placement_policy="avoid_source_line_overlap_v1",
        )
    assert not opt_in_output.exists()

    legacy_output = tmp_path / "zero-legacy.dxf"
    legacy = build_dxf(zero_length_document(), str(legacy_output), build_dimensions=True)
    assert legacy.dimension_count == 0


def test_mixed_non_line_geometry_remains_outside_the_line_overlap_predicate(tmp_path):
    circle = Primitive(
        id="unclassified-circle",
        type="circle",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 40, 10)),
        geometry=CircleGeometry(center=Point2D(20.0, 5.0), radius=1.0),
    )
    label = Primitive(
        id="label",
        type="text",
        source="text_tesseract",
        confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 40, 10)),
        text_data=TextData(content="40", position=Point2D(20.0, 5.0), rotation_deg=0.0, height=3.5),
    )
    document = _document(_line("measured", (0.0, 0.0), (40.0, 0.0)), circle, label)

    result = _build(document, tmp_path / "mixed.dxf", "avoid_source_line_overlap_v1")
    _, dimension, _ = _dimension_and_graphics(result.output_path)

    assert dimension.get_measurement() == pytest.approx(40.0)


def test_virtual_graphics_enumeration_error_fails_closed_before_save(tmp_path, monkeypatch):
    import ezdxf.entities.dimension

    def fail_enumeration(self):
        raise RuntimeError("synthetic virtual-entity enumeration failure")

    monkeypatch.setattr(ezdxf.entities.dimension.Dimension, "virtual_entities", fail_enumeration)
    output = tmp_path / "enumeration-failure.dxf"

    with pytest.raises(ValueError, match="enumerat|classified") as exc_info:
        _build(_fixture(), output, "avoid_source_line_overlap_v1")

    assert not output.exists()
    assert isinstance(exc_info.value.__cause__, RuntimeError)
