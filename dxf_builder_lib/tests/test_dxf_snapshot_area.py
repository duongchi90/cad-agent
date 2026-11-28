from decimal import ROUND_CEILING, localcontext
from io import BytesIO, StringIO
import math

import ezdxf
from ezdxf.lldxf.tagwriter import BinaryTagWriter, TagWriter
import pytest

from dxf_builder_lib import _dxf_snapshot as owner


def polyline(points, *, closed=True, **dxfattribs):
    return ezdxf.new().modelspace().add_lwpolyline(
        points, format="xyb", close=closed, dxfattribs=dxfattribs,
    )


def test_signed_circular_area_and_reversed_winding():
    measure = owner.measure_planar_lwpolyline_signed_area
    assert measure(polyline([(0, 0, 1), (100, 0, 1)])) == pytest.approx(math.pi * 2500)
    assert measure(polyline([(100, 0, -1), (0, 0, -1)])) == pytest.approx(-math.pi * 2500)


def test_chord_and_major_arc_have_different_area():
    measure = owner.measure_planar_lwpolyline_signed_area
    base = [(0, 0, 0), (100, 0, 0), (100, 80, 0), (0, 80, 0)]
    assert measure(polyline(base)) == 8000
    base[0] = (0, 0, 2)
    r = 62.5
    theta = 4 * math.atan(2)
    assert measure(polyline(base)) == pytest.approx(8000 + r * r * (theta - math.sin(theta)) / 2)


def test_tiny_bulge_keeps_first_order_area_at_large_offset():
    measure = owner.measure_planar_lwpolyline_signed_area
    # For a small b the area added by the arc approaches chord squared times b/3.
    c, b, origin = 1e5, 1e-8, 1e10
    result = measure(polyline([(origin, origin, b), (origin + c, origin, 0)]))
    assert result == pytest.approx(c * c * b / 3, rel=1e-12)


@pytest.mark.parametrize(
    "points, options, message",
    [
        ([(0, 0, 0), (10, 0, 0), (0, 10, 0)], {"closed": False}, "closed"),
        ([(0, 0, 0), (10, 0, 0), (0, 10, 0)], {"const_width": 1.0}, "width"),
        ([(0, 0, 0), (10, 0, 0), (0, 10, 0)], {"elevation": 0.01}, "elevation"),
        ([(0, 0, 0), (10, 0, 0), (0, 10, 0)], {"extrusion": (0, 0, -1)}, "extrusion"),
        ([(0, 0, 0), (10, 0, float("nan")), (0, 10, 0)], {}, "finite"),
        ([(0, 0, 0), (float("inf"), 0, 0), (0, 10, 0)], {}, "finite"),
        ([(0, 0, 0), (0, 0, 0.2), (0, 10, 0)], {}, "coincident"),
        ([(0, 0, 0)], {}, "two vertices"),
    ],
)
def test_invalid_measurement_input_is_refused(points, options, message):
    with pytest.raises(ValueError, match=message):
        owner.measure_planar_lwpolyline_signed_area(polyline(points, **options))

def test_geometry_builder_can_reuse_area_without_constructing_a_dxf_entity():
    points = iter([(0, 0, 1), (100, 0, 1)])
    assert owner.measure_signed_bulged_loop_area(points) == pytest.approx(math.pi * 2500)

@pytest.mark.parametrize("binary", [False, True])
@pytest.mark.parametrize("width", [0.0, 7.0, float("nan"), float("inf")])
def test_zero_constant_width_does_not_hide_raw_vertex_widths(binary, width):
    document = ezdxf.new()
    document.modelspace().add_lwpolyline(
        [(0, 0, width, 0, 0), (1, 0, 0, width, 0), (0, 1, 0, 0, 0)],
        format="xyseb", close=True, dxfattribs={"const_width": 0},
    )
    if binary:
        binary_stream = BytesIO()
        writer = BinaryTagWriter(binary_stream, dxfversion=document.dxfversion)
        writer.write_signature()
    else:
        text_stream = StringIO()
        writer = TagWriter(text_stream, dxfversion=document.dxfversion)
    writer.force_optional = True
    document.update_all()
    document.export_sections(writer)
    data = binary_stream.getvalue() if binary else text_stream.getvalue().encode("ascii")
    loaded, _ = owner.read_dxf_snapshot(data)
    entity, = loaded.modelspace().query("LWPOLYLINE")
    assert entity.dxf.hasattr("const_width") and entity.dxf.const_width == 0
    if width == 0:
        assert owner.measure_planar_lwpolyline_signed_area(entity) == 0.5
    else:
        with pytest.raises(ValueError, match="width"):
            owner.measure_planar_lwpolyline_signed_area(entity)


def test_cancellation_does_not_erase_a_real_triangle_or_depend_on_first_vertex():
    n = 2 ** 27
    loop = [(0, 0, 0), (n, n - 1, 0), (n + 1, n, 0)]
    measure = owner.measure_signed_bulged_loop_area
    assert measure(loop) == 0.5
    assert measure(loop[1:] + loop[:1]) == 0.5
    assert measure(loop[::-1]) == -0.5


def test_overflowing_double_area_is_reported_when_final_area_is_finite():
    side = 1.5e154
    loop = [(0, 0, 0), (side, 0, 0), (0, side, 0)]
    assert owner.measure_signed_bulged_loop_area(loop) == pytest.approx(1.125e308)


def test_subnormal_chord_with_finite_large_bulge_has_measurable_arc_area():
    chord, bulge = 1e-323, 1e308
    loop = [(0, 0, bulge), (chord, 0, 0)]
    radius = chord * bulge / 4
    assert owner.measure_signed_bulged_loop_area(loop) == pytest.approx(math.pi * radius**2, rel=1e-12, abs=0)

@pytest.mark.parametrize("binary", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_nearly_cancelled_arcs_preserve_area_sign_after_readback(binary, reverse):
    chord = 100_000_000.0
    bulges = (0.1, -0.10000000000000002)
    points = [(0, 0, bulges[0]), (chord, 0, bulges[1])]
    if reverse:
        points = [(chord, 0, -bulges[0]), (0, 0, -bulges[1])]
    entity = polyline(points)
    if binary:
        stream = BytesIO()
        entity.doc.write(stream, fmt="bin")
        data = stream.getvalue()
    else:
        stream = StringIO()
        entity.doc.write(stream)
        data = stream.getvalue().encode("ascii")
    doc, _ = owner.read_dxf_snapshot(data)
    contour, = doc.modelspace().query("LWPOLYLINE")
    expected = 0.0465361906678802 if reverse else -0.0465361906678802
    assert owner.measure_planar_lwpolyline_signed_area(contour) == pytest.approx(expected, rel=1e-13, abs=0)

def test_independent_shallow_arc_cancellation_counterexample():
    loop = [(0, 0, 0.05), (1e9, 0, -0.05000000000000001)]
    signed = owner.measure_signed_bulged_loop_area(loop)
    assert signed == pytest.approx(-2.316432018846525, rel=1e-13, abs=0)
    with localcontext() as caller_context:
        caller_context.prec = 8
        caller_context.Emin = -12
        caller_context.Emax = 12
        caller_context.rounding = ROUND_CEILING
        assert owner.measure_signed_bulged_loop_area(loop) == signed
