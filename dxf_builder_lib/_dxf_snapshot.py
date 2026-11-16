"""Decode an immutable DXF snapshot and optionally observe STYLE declarations."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from io import BytesIO, TextIOWrapper

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


def read_dxf_snapshot(
    data: bytes, *, observe_styles: bool = False,
) -> tuple[Drawing, set[StyleRecordKey]]:
    """Read a DXF and collect repeated ACAD STYLE records before normalization."""
    repeated_style_records: set[StyleRecordKey] = set()

    def load(tags: Iterable[DXFTag]) -> Drawing:
        # ezdxf keeps the last XDATA block for an APPID.
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
