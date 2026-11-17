"""Decode an immutable DXF snapshot and optionally observe STYLE declarations."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from io import BytesIO, TextIOWrapper
from pathlib import Path
from typing import Any

from ezdxf.document import Drawing
from ezdxf.entities import DimStyleOverride
from ezdxf.filemanagement import dxf_stream_info
from ezdxf.lldxf.extendedtags import ExtendedTags
from ezdxf.lldxf.tagger import ascii_tags_loader, binary_tags_loader
from ezdxf.lldxf.tags import DXFTag, group_tags
from ezdxf.lldxf.validator import make_table_key
from ezdxf.tools.text import plain_mtext


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


def _collect_xdata(entity) -> dict[str, list[list[Any]]]:
    if getattr(entity, "xdata", None) is None:
        return {}
    out: dict[str, list[list[Any]]] = {}
    for app in sorted(entity.xdata.data):
        out[str(app)] = [[int(tag.code), tag.value] for tag in entity.get_xdata(app)]
    return out


def extract_dxf_readback_snapshot(source: str | Path | bytes) -> dict[str, Any]:
    """Extract header units, styles, LINE/XData, full DBText, and DIMENSION fields from DXF."""
    data = source if isinstance(source, (bytes, bytearray)) else Path(source).read_bytes()
    doc, repeated = read_dxf_snapshot(bytes(data), observe_styles=True)
    styles = {
        style.dxf.name: {
            "font": str(style.dxf.get("font", "")),
            "width": float(style.dxf.get("width", 1.0)),
            "oblique": float(style.dxf.get("oblique", 0.0)),
        }
        for style in doc.styles
    }
    lines: list[dict[str, Any]] = []
    texts: list[dict[str, Any]] = []
    dimensions: list[dict[str, Any]] = []
    for entity in doc.modelspace():
        kind = entity.dxftype()
        if kind == "LINE":
            lines.append({
                "handle": entity.dxf.handle,
                "layer": entity.dxf.layer,
                "start": [float(v) for v in entity.dxf.start],
                "end": [float(v) for v in entity.dxf.end],
                "xdata": _collect_xdata(entity),
            })
        elif kind == "TEXT":
            style_name = str(entity.dxf.get("style", "Standard"))
            texts.append({
                "handle": entity.dxf.handle,
                "layer": entity.dxf.layer,
                "text": str(entity.dxf.get("text", "")),
                "insert": [float(v) for v in entity.dxf.insert],
                "height": float(entity.dxf.get("height", 0.0)),
                "rotation_deg": float(entity.dxf.get("rotation", 0.0)),
                "width": float(entity.dxf.get("width", 1.0)),
                "oblique": float(entity.dxf.get("oblique", 0.0)),
                "style": style_name,
                "style_font": styles.get(style_name, {}).get("font"),
                "halign": int(entity.dxf.get("halign", 0)),
                "valign": int(entity.dxf.get("valign", 0)),
                "xdata": _collect_xdata(entity),
            })
        elif kind == "DIMENSION":
            try:
                measured = entity.get_measurement()
                measurement = float(measured) if isinstance(measured, (int, float)) else None
            except Exception:
                measurement = None
            try:
                dimlfac = float(DimStyleOverride(entity).get("dimlfac", 1.0))
            except Exception:
                dimlfac = None
            block = None
            try:
                block = entity.get_geometry_block()
            except Exception:
                block = None
            rendered_parts: list[str] = []
            if block is not None:
                for item in block:
                    if item.dxftype() == "MTEXT":
                        rendered_parts.append(plain_mtext(item.text).strip())
                    elif item.dxftype() == "TEXT":
                        rendered_parts.append(str(item.dxf.get("text", "")).strip())
            raw_g42 = entity.dxf.get("actual_measurement")
            dimensions.append({
                "handle": entity.dxf.handle,
                "layer": entity.dxf.layer,
                "dimtype": int(entity.dxf.get("dimtype", 0)) & 0x0F,
                "measurement": measurement,
                "override": str(entity.dxf.get("text", "") or ""),
                "dimstyle": str(entity.dxf.get("dimstyle", "Standard")),
                "dimlfac": dimlfac,
                "angle": float(entity.dxf.get("angle", 0.0)),
                "rendered_text": " ".join(p for p in rendered_parts if p) or None,
                "group42": None if raw_g42 is None else float(raw_g42),
            })
    return {
        "dxf_version": doc.dxfversion,
        "insunits": doc.header.get("$INSUNITS"),
        "repeated_style_records": sorted(list(item) for item in repeated),
        "styles": styles,
        "lines": lines,
        "texts": texts,
        "dimensions": dimensions,
    }
