"""Decode immutable DXF snapshots with optional checks on raw tags."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from io import BytesIO, TextIOWrapper
from itertools import chain, count
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


def measure_planar_lwpolyline_signed_area(entity) -> float:
    """Measure oriented algebraic area in squared drawing units.

    Preserve circular bulges. Callers establish simple-loop topology, units
    and any hole relationships before using this value as material area.
    """
    validate_planar_lwpolyline(entity)
    if not entity.closed:
        raise ValueError("area measurement requires a closed LWPOLYLINE")
    points = entity.get_points("xyseb")
    if entity.dxf.get("const_width", 0.0) != 0.0 or any(
        start_width != 0.0 or end_width != 0.0 for _, _, start_width, end_width, _ in points
    ):
        raise ValueError("area measurement requires zero polyline width")
    return measure_signed_bulged_loop_area((x, y, bulge) for x, y, _, _, bulge in points)


def measure_signed_bulged_loop_area(vertices: Iterable[tuple[float, float, float]]) -> float:
    """Measure oriented area of an implicitly closed loop of (x, y, bulge) triples."""
    points = [(float(x), float(y), float(bulge)) for x, y, bulge in vertices]
    if len(points) < 2:
        raise ValueError("area measurement requires at least two vertices")
    if not all(math.isfinite(value) for point in points for value in point):
        raise ValueError("area measurement requires finite vertices and bulges")

    def decimal_fraction(value: Fraction) -> Decimal:
        return Decimal(value.numerator) / Decimal(value.denominator)

    def atan_unit(value: Decimal) -> Decimal:
        # Halve the angle three times before summing its alternating series.
        for _ in range(3):
            value /= 1 + (1 + value * value).sqrt()
        total = power = value
        multiplier = -value * value
        for denominator in count(3, 2):
            power *= multiplier
            updated = total + power / denominator
            if updated == total:
                return 8 * total
            total = updated

    def arc_factor(bulge: Decimal, half_pi: Decimal) -> Decimal:
        squared = bulge * bulge
        if bulge <= Decimal("0.25"):
            # Expand the full coefficient near zero so the linear terms of
            # atan(b) and b do not cancel before scaling by b squared.
            total = 2 * bulge / 3
            power = bulge
            for index in count(2):
                power *= squared if index == 2 else -squared
                denominator = (2 * index + 1) * (2 * index - 1) * (2 * index - 3)
                updated = total + 2 * power / denominator
                if updated == total:
                    return total
                total = updated
        angle = atan_unit(bulge) if bulge <= 1 else half_pi - atan_unit(1 / bulge)
        # Substitute sin(4 atan(b)) to avoid a separate transcendental term.
        return ((1 + squared) ** 2 * angle - bulge * (1 - squared)) / (4 * squared)

    # Keep determinants exact for the original binary64 coordinates.
    exact_points = [(Fraction(x), Fraction(y), bulge) for x, y, bulge in points]
    origin_x, origin_y, _ = exact_points[0]
    polygon_twice_area = Fraction()
    arc_chords: dict[float, Fraction] = {}
    for (x, y, bulge), (end_x, end_y, _) in zip(exact_points, exact_points[1:] + exact_points[:1], strict=True):
        dx, dy = end_x - x, end_y - y
        if dx == dy == 0:
            raise ValueError("area measurement cannot use coincident consecutive vertices")
        polygon_twice_area += (x - origin_x) * dy - (y - origin_y) * dx
        if bulge != 0.0:
            magnitude = abs(bulge)
            chord_squared = dx * dx + dy * dy
            signed_chord_squared = chord_squared if bulge > 0.0 else -chord_squared
            # Equal and opposite circular coefficients can cancel exactly.
            arc_chords[magnitude] = arc_chords.get(magnitude, Fraction()) + signed_chord_squared

    remaining_arcs = [(bulge, chord) for bulge, chord in arc_chords.items() if chord]
    try:
        if not remaining_arcs:
            return float(polygon_twice_area / 2)
        context = Context(prec=80, rounding=ROUND_HALF_EVEN, Emin=-10000, Emax=10000)
        with localcontext(context):
            half_pi = 2 * atan_unit(Decimal(1))
            twice_area = decimal_fraction(polygon_twice_area)
            magnitude = abs(twice_area)
            for bulge, chord in remaining_arcs:
                contribution = decimal_fraction(chord) * arc_factor(Decimal.from_float(bulge), half_pi)
                twice_area += contribution
                magnitude += abs(contribution)
            if abs(twice_area) <= magnitude.scaleb(-68):
                raise ValueError("signed area is below supported numerical resolution")
            area = float(twice_area / 2)
    except OverflowError as exc:
        raise ValueError("area measurement exceeds finite arithmetic range") from exc
    if not math.isfinite(area):
        raise ValueError("area measurement exceeds finite arithmetic range")
    return area


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
