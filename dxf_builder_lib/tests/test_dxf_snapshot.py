"""The opt-in plane check protects raw signed-bulge coordinates on DXF readback."""

from io import StringIO
import re

import ezdxf
import pytest

from dxf_builder_lib._dxf_snapshot import read_dxf_snapshot, validate_planar_lwpolyline


def _read_wire(group: int, value: str):
    drawing = ezdxf.new("R2010")
    modelspace = drawing.modelspace()
    wire = modelspace.add_lwpolyline(
        [(0, 0, -0.25), (4, 0, 0.125), (4, 3, 0)], format="xyb", close=True,
        dxfattribs={"elevation": 1.0, "extrusion": (0.0, 0.0, -1.0)},
    )
    stream = StringIO()
    drawing.write(stream)
    source = stream.getvalue()
    pattern = r"(^  0\nLWPOLYLINE\n)(.*?)(?=^  0\n)"
    match = re.search(pattern, source, flags=re.MULTILINE | re.DOTALL)
    assert match is not None
    header, record = match.groups()
    record = re.sub(r"(^ 38\n)[^\n]+", r"\g<1>0.0", record, flags=re.MULTILINE)
    record = re.sub(r"(^230\n)[^\n]+", r"\g<1>1.0", record, flags=re.MULTILINE)
    updated, count = re.subn(
        rf"(^{group:>3}\n)[^\n]+", rf"\g<1>{value}", record, flags=re.MULTILINE,
    )
    assert count == 1
    parsed, _ = read_dxf_snapshot((source[:match.start()] + header + updated + source[match.end():]).encode("ascii"))
    return parsed.entitydb[wire.dxf.handle]


def test_planar_wire_retains_signed_native_bulges():
    wire = _read_wire(230, "1.0")
    validate_planar_lwpolyline(wire)
    assert wire.closed
    assert list(wire.get_points("xyb")) == [(0, 0, -0.25), (4, 0, 0.125), (4, 3, 0)]


@pytest.mark.parametrize(("group", "value", "reason"), [
    (210, "nan", "extrusion"),
    (220, "nan", "extrusion"),
    (230, "nan", "extrusion"),
    (230, "inf", "extrusion"),
    (230, "-1.0", "extrusion"),
    (38, "nan", "elevation"),
    (38, "1.0", "elevation"),
])
def test_unsupported_plane_fails_only_at_opt_in_readback(group, value, reason):
    wire = _read_wire(group, value)
    with pytest.raises(ValueError, match=reason):
        validate_planar_lwpolyline(wire)


def test_planar_wire_guard_rejects_other_entity_types():
    line = ezdxf.new().modelspace().add_line((0, 0), (1, 0))
    with pytest.raises(ValueError, match="LWPOLYLINE"):
        validate_planar_lwpolyline(line)
