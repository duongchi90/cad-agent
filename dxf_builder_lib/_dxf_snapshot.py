"""Decode immutable DXF snapshots with optional checks on raw tags."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from io import BytesIO, TextIOWrapper
from itertools import chain
import math

from ezdxf.document import Drawing
from ezdxf.filemanagement import dxf_stream_info
from ezdxf.lldxf.extendedtags import ExtendedTags
from ezdxf.lldxf.tagger import ascii_tags_loader, binary_tags_loader
from ezdxf.lldxf.tags import DXFTag, group_tags
from ezdxf.lldxf.validator import make_table_key


StyleRecordKey = tuple[str, str]


def _observe_repeated_style_records(
    tags: Iterable[DXFTag], repeated_style_records: set[StyleRecordKey],
) -> Iterator[DXFTag]:
    in_tables = in_style_table = False
    for group in group_tags(tags):
        # Match Drawing.load's tag_compiler before it normalizes code-0 values.
        marker = group[0].value.strip()
        if marker == "SECTION":
            in_tables = len(group) > 1 and group[1] == (2, "TABLES")
            in_style_table = False
        elif marker == "ENDSEC":
            in_tables = in_style_table = False
        elif in_tables and marker == "TABLE":
            in_style_table = group.get_first_value(2, default=None) == "STYLE"
        elif marker == "ENDTAB":
            in_style_table = False
        elif in_style_table and marker == "STYLE":
            record = ExtendedTags(group)
            if sum(application[0] == (1001, "ACAD") for application in record.xdata) > 1:
                handle = record.noclass.get_first_value(5, default=None)
                if handle is None:
                    # R12 STYLE records may omit the handle.
                    name = next(
                        (tag.value for subclass in record.subclasses for tag in subclass if tag.code == 2), "",
                    )
                    repeated_style_records.add(("name", make_table_key(name)))
                else:
                    repeated_style_records.add(("handle", handle))
        yield from group


def _require_unique_xdata_application(
    tags: Iterable[DXFTag], appid: str,
) -> Iterator[DXFTag]:
    """Reject repeated blocks for one APPID before entity XDATA is normalized."""
    target = make_table_key(appid)
    remaining = iter(tags)
    for first in remaining:
        if first.code == 0:
            break
        # group_tags skips tags before its first structure marker.
        yield first
    else:
        return

    for group in group_tags(chain((first,), remaining)):
        possible_matches = sum(
            tag.code == 1001 and make_table_key(tag.value) == target for tag in group
        )
        if possible_matches > 1:
            record = ExtendedTags(group)
            matches = sum(make_table_key(block[0].value) == target for block in record.xdata)
            if matches > 1:
                handle = record.noclass.get_first_value(5, default=None)
                raise ValueError(f"Repeated XDATA application {appid!r} on DXF record {handle!r}")
        yield from group


def validate_planar_lwpolyline(entity) -> None:
    """Require an LWPOLYLINE in the supported zero-elevation, +Z plane.

    Opt in before consuming the raw vertices or bulges. General snapshot
    loading also supports valid DXF entities in other planes.
    """
    if entity.dxftype() != "LWPOLYLINE":
        raise ValueError("expected LWPOLYLINE")
    extrusion = tuple(entity.dxf.extrusion)
    if not all(map(math.isfinite, extrusion)) or any(
        abs(actual - expected) > 1e-6
        for actual, expected in zip(extrusion, (0.0, 0.0, 1.0), strict=True)
    ):
        raise ValueError(f"unsupported OCS extrusion {extrusion}")
    elevation = entity.dxf.elevation
    if not math.isfinite(elevation) or abs(elevation) > 1e-6:
        raise ValueError(f"nonplanar LWPOLYLINE elevation {elevation}")


def read_dxf_snapshot(
    data: bytes, *, observe_styles: bool = False,
    unique_xdata_appid: str | None = None,
) -> tuple[Drawing, set[StyleRecordKey]]:
    """Read a DXF and optionally inspect raw STYLE or XDATA declarations."""
    repeated_style_records: set[StyleRecordKey] = set()

    def load(tags: Iterable[DXFTag]) -> Drawing:
        # ezdxf keeps the last XDATA block for an APPID.
        if unique_xdata_appid is not None:
            tags = _require_unique_xdata_application(tags, unique_xdata_appid)
        if observe_styles:
            tags = _observe_repeated_style_records(tags, repeated_style_records)
        return Drawing.load(tags)

    if data.startswith(b"AutoCAD Binary DXF\r\n\x1a\x00"):
        document = load(binary_tags_loader(data, errors="surrogateescape"))
    else:
        with TextIOWrapper(BytesIO(data), encoding="utf-8", errors="ignore") as header_stream:
            info = dxf_stream_info(header_stream)
        with TextIOWrapper(BytesIO(data), encoding=info.encoding, errors="surrogateescape") as text_stream:
            document = load(ascii_tags_loader(text_stream))
    return document, repeated_style_records
