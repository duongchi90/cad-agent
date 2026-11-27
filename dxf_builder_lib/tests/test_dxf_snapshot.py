"""The opt-in plane check protects raw signed-bulge coordinates on DXF readback."""

from io import BytesIO, StringIO
import re

import ezdxf
import pytest
from ezdxf.lldxf.tags import DXFTag
from ezdxf.lldxf.tagwriter import BinaryTagWriter

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


def _fixture_drawing():
    drawing = ezdxf.new("R2010")
    for appid in ("CHECKED_ID", "OTHER_APP"):
        drawing.appids.new(appid)
    for i in range(2):
        line = drawing.modelspace().add_line((0, i), (4, i))
        line.set_xdata("CHECKED_ID", [(1000, "first")])
        line.set_xdata("OTHER_APP", [(1000, "other")])
    return drawing


def _encode_drawing(drawing, format_name):
    if format_name == "bin":
        stream = BytesIO()
        drawing.write(stream, fmt="bin")
        return stream.getvalue()
    stream = StringIO()
    drawing.write(stream)
    return stream.getvalue().encode("ascii")


def _xdata_block(format_name, appid, payload):
    if format_name == "bin":
        stream = BytesIO()
        writer = BinaryTagWriter(stream, dxfversion="AC1024")
        writer.write_tag2(1001, appid)
        writer.write_tag2(1000, payload)
        return stream.getvalue()
    return f"1001\n{appid}\n1000\n{payload}\n".encode("ascii")


@pytest.mark.parametrize("format_name", ["asc", "bin"])
@pytest.mark.parametrize(("duplicate_appid", "payload"), [
    ("CHECKED_ID", "first"),
    ("CHECKED_ID", "conflict"),
    ("checked_id", "conflict"),
])
def test_opt_in_rejects_repeated_application_on_one_record(format_name, duplicate_appid, payload):
    drawing = _fixture_drawing()
    original = _xdata_block(format_name, "CHECKED_ID", "first")
    duplicate = original + _xdata_block(format_name, duplicate_appid, payload)
    data = _encode_drawing(drawing, format_name)
    assert data.count(original) == 2
    data = data.replace(original, duplicate, 1)

    legacy, _ = read_dxf_snapshot(data)
    assert len(legacy.modelspace()) == 2
    with pytest.raises(ValueError, match="Repeated XDATA application 'CHECKED_ID'"):
        read_dxf_snapshot(data, unique_xdata_appid="CHECKED_ID")


@pytest.mark.parametrize("format_name", ["asc", "bin"])
def test_opt_in_preserves_distinct_records_unrelated_appid_and_style_observation(format_name):
    drawing = _fixture_drawing()
    style = drawing.styles.get("Standard")
    style.set_xdata("ACAD", [(1000, "first-font")])
    style_block = _xdata_block(format_name, "ACAD", "first-font")
    other_block = _xdata_block(format_name, "OTHER_APP", "other")
    data = _encode_drawing(drawing, format_name)
    assert data.count(style_block) == 1 and data.count(other_block) == 2
    data = data.replace(style_block, style_block * 2, 1).replace(other_block, other_block * 2, 1)
    parsed, styles = read_dxf_snapshot(data, observe_styles=True, unique_xdata_appid="checked_id")
    assert styles == {("handle", style.dxf.handle)}
    assert [list(line.get_xdata("CHECKED_ID")) for line in parsed.modelspace()] == [
        [(1000, "first")], [(1000, "first")],
    ]


def test_opt_in_passes_through_original_tags_and_counts_only_xdata_boundaries():
    from dxf_builder_lib._dxf_snapshot import _require_unique_xdata_application

    tags = [DXFTag(code, value) for code, value in (
        (1, "prefix"), (0, "LINE"), (5, "A"), (102, "{DATA"), (1001, "CHECKED_ID"),
        (102, "}"), (1001, "CHECKED_ID"), (1000, "payload"), (0, "EOF"),
    )]
    observed = list(_require_unique_xdata_application(iter(tags), "checked_id"))
    assert observed == tags
    assert all(actual is expected for actual, expected in zip(observed, tags, strict=True))
