"""cad_agent/cleanroom_basic_shared.py.

Batch S1: Basic Shared CAD Tools (Wave 7, 8, 9 & Core Tools).
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierBWave7Handlers.cs: GridAxesHandler (cadmind-grid-axes)
  - TierBWave7Handlers.cs: RevCloudHandler (cadmind-rev-cloud)
  - TierBWave8Handlers.cs: RoomNumberHandler (cadmind-room-number)
  - TierBWave9Handlers.cs: AutoNumberHandler (cadmind-auto-number)
  - DrawingFrameHandler.cs: DrawingFrameHandler (cadmind-drawing-frame)

Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D, Arc2D, CircleIR),
strict IEEE-754 machine-epsilon safety, Banker's rounding parity,
and zero external pip dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from cad_agent.cleanroom_mechanical import LineSegment2D, Point2D

# ============================================================================
# EXCEPTION HIERARCHY
# ============================================================================


class CleanroomError(ValueError):
    """Base exception for cleanroom validation errors."""

    pass


class DegenerateGeometryError(CleanroomError):
    """Raised when geometric parameters violate physical construction rules."""

    pass


# ============================================================================
# INTERNAL IEEE-754 VALIDATION HELPERS
# ============================================================================


def _validate_finite(val: float, name: str) -> float:
    """Ensure value is finite (not NaN, not Inf)."""
    if not isinstance(val, (int, float)) or isinstance(val, bool) or math.isnan(val) or math.isinf(val):
        raise DegenerateGeometryError(f"DEGENERATE_GEOMETRY: Numeric arguments must be finite numbers ({name}={val}).")
    return float(val)


def _validate_positive(val: float, name: str) -> float:
    """Ensure value is strictly positive (> 1e-4) matching C# epsilon checks."""
    f = _validate_finite(val, name)
    if f <= 1e-4:
        raise DegenerateGeometryError(f"DEGENERATE_GEOMETRY: Parameter '{name}' must be positive (> 1e-4), got {f}.")
    return f


def _validate_non_negative(val: float, name: str) -> float:
    """Ensure value is non-negative (>= 0.0) matching C# check."""
    f = _validate_finite(val, name)
    if f < 0.0:
        raise DegenerateGeometryError(f"DEGENERATE_GEOMETRY: Parameter '{name}' must be non-negative (>= 0), got {f}.")
    return f


# ============================================================================
# 1. GRID AXES (cadmind-grid-axes / TierB Wave 7)
# ============================================================================


@dataclass(frozen=True)
class GridAxesArgs:
    """Input arguments for grid axes generation."""

    horizontal_spacings: Optional[Sequence[float]] = None
    vertical_spacings: Optional[Sequence[float]] = None
    origin: Optional[Sequence[float]] = None
    extension: float = 25.0
    bubble_radius: float = 6.0
    text_height: float = 4.0
    start_alpha: str = "A"
    start_number: int = 1
    bubble_at_start: bool = True
    bubble_at_end: bool = False
    layer: str = "S-GRID"


@dataclass(frozen=True)
class GridBubbleIR:
    """Intermediate representation of a grid axis annotation bubble."""

    center: Point2D
    radius: float
    label: str
    text_height: float
    position: str  # "START" or "END"


@dataclass(frozen=True)
class GridAxisLineIR:
    """Intermediate representation of a single grid line with attached bubbles."""

    axis_type: str  # "HORIZONTAL" or "VERTICAL"
    label: str
    line: LineSegment2D
    bubbles: List[GridBubbleIR] = field(default_factory=list)


@dataclass(frozen=True)
class GridAxesResult:
    """Result of grid axes generation."""

    status: str
    message: str
    horizontal_axis_count: int
    vertical_axis_count: int
    bubble_count: int
    processed_count: int
    axes: List[GridAxisLineIR] = field(default_factory=list)
    layer: str = "S-GRID"


class GridAxesHandler:
    """Generates structural grid lines and circular bubble callouts with alphanumeric indexing."""

    @staticmethod
    def _get_alpha_label(index: int) -> str:
        """Derive 1- or 2-letter column label (A-Z, AA-AZ, BA-BZ, etc.)."""
        if index < 26:
            return chr(ord("A") + index)
        first = (index // 26) - 1
        second = index % 26
        return f"{chr(ord('A') + first)}{chr(ord('A') + second)}"

    def execute(self, args: GridAxesArgs) -> GridAxesResult:
        """Execute grid axes layout with strict C# parity."""
        bubble_radius = _validate_positive(args.bubble_radius, "BubbleRadius")
        text_height = _validate_positive(args.text_height, "TextHeight")
        extension = _validate_non_negative(args.extension, "Extension")

        h_spacings = list(args.horizontal_spacings) if args.horizontal_spacings is not None else []
        v_spacings = list(args.vertical_spacings) if args.vertical_spacings is not None else []

        if len(h_spacings) == 0 and len(v_spacings) == 0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: At least one axis spacing required.")

        for i, s in enumerate(h_spacings):
            _validate_positive(s, f"HorizontalSpacings[{i}]")

        for i, s in enumerate(v_spacings):
            _validate_positive(s, f"VerticalSpacings[{i}]")

        ox, oy = 0.0, 0.0
        if args.origin is not None and len(args.origin) >= 2:
            ox = _validate_finite(args.origin[0], "Origin[0]")
            oy = _validate_finite(args.origin[1], "Origin[1]")

        layer = args.layer.strip() if args.layer and args.layer.strip() else "S-GRID"

        total_width = sum(v_spacings) if v_spacings else 100.0
        total_height = sum(h_spacings) if h_spacings else 100.0

        min_x = ox
        max_x = ox + total_width
        min_y = oy
        max_y = oy + total_height

        h_count = 0
        v_count = 0
        bubble_count = 0
        total_entities = 0
        axes_ir: List[GridAxisLineIR] = []

        # 1. Horizontal Axes (lines along X-axis at Y elevations)
        y_coords: List[float] = []
        if len(h_spacings) > 0:
            cur_y = oy
            y_coords.append(cur_y)
            for s in h_spacings:
                cur_y += s
                y_coords.append(cur_y)
        else:
            y_coords.append(oy)

        axis_number = args.start_number
        for y in y_coords:
            h_count += 1
            line_start_x = min_x - extension
            line_end_x = max_x + extension
            bubbles: List[GridBubbleIR] = []
            num_str = str(axis_number)

            if args.bubble_at_start:
                b_center = Point2D(line_start_x - bubble_radius, y)
                bubbles.append(
                    GridBubbleIR(
                        center=b_center,
                        radius=bubble_radius,
                        label=num_str,
                        text_height=text_height,
                        position="START",
                    )
                )
                total_entities += 2  # circle + text
                bubble_count += 1

            if args.bubble_at_end:
                b_center = Point2D(line_end_x + bubble_radius, y)
                bubbles.append(
                    GridBubbleIR(
                        center=b_center,
                        radius=bubble_radius,
                        label=num_str,
                        text_height=text_height,
                        position="END",
                    )
                )
                total_entities += 2  # circle + text
                bubble_count += 1

            grid_line = LineSegment2D(Point2D(line_start_x, y), Point2D(line_end_x, y))
            total_entities += 1  # line
            axes_ir.append(
                GridAxisLineIR(
                    axis_type="HORIZONTAL",
                    label=num_str,
                    line=grid_line,
                    bubbles=bubbles,
                )
            )
            axis_number += 1

        # 2. Vertical Axes (lines along Y-axis at X offsets)
        x_coords: List[float] = []
        if len(v_spacings) > 0:
            cur_x = ox
            x_coords.append(cur_x)
            for s in v_spacings:
                cur_x += s
                x_coords.append(cur_x)
        else:
            x_coords.append(ox)

        start_alpha_str = args.start_alpha.strip().upper() if args.start_alpha and args.start_alpha.strip() else "A"
        alpha_index = 0
        if len(start_alpha_str) == 1 and "A" <= start_alpha_str <= "Z":
            alpha_index = ord(start_alpha_str) - ord("A")

        for x in x_coords:
            v_count += 1
            line_start_y = min_y - extension
            line_end_y = max_y + extension
            alpha_label = self._get_alpha_label(alpha_index)
            alpha_index += 1
            bubbles = []

            if args.bubble_at_start:
                b_center = Point2D(x, line_start_y - bubble_radius)
                bubbles.append(
                    GridBubbleIR(
                        center=b_center,
                        radius=bubble_radius,
                        label=alpha_label,
                        text_height=text_height,
                        position="START",
                    )
                )
                total_entities += 2
                bubble_count += 1

            if args.bubble_at_end:
                b_center = Point2D(x, line_end_y + bubble_radius)
                bubbles.append(
                    GridBubbleIR(
                        center=b_center,
                        radius=bubble_radius,
                        label=alpha_label,
                        text_height=text_height,
                        position="END",
                    )
                )
                total_entities += 2
                bubble_count += 1

            grid_line = LineSegment2D(Point2D(x, line_start_y), Point2D(x, line_end_y))
            total_entities += 1
            axes_ir.append(
                GridAxisLineIR(
                    axis_type="VERTICAL",
                    label=alpha_label,
                    line=grid_line,
                    bubbles=bubbles,
                )
            )

        msg = (
            f"Grid axes created successfully with {h_count} horizontal, "
            f"{v_count} vertical axes, and {bubble_count} bubbles."
        )
        return GridAxesResult(
            status="OK",
            message=msg,
            horizontal_axis_count=h_count,
            vertical_axis_count=v_count,
            bubble_count=bubble_count,
            processed_count=total_entities,
            axes=axes_ir,
            layer=layer,
        )


# ============================================================================
# 2. REVISION CLOUD (cadmind-rev-cloud / TierB Wave 7)
# ============================================================================


@dataclass(frozen=True)
class RevCloudArgs:
    """Input arguments for revision cloud generation."""

    boundary_points: Optional[Sequence[Sequence[float]]] = None
    arc_length: float = 12.0
    bulge: float = 0.52
    rev_tag: Optional[str] = None
    tag_size: float = 7.0
    layer: str = "REV"


@dataclass(frozen=True)
class RevCloudArcIR:
    """Intermediate representation of an individual rev cloud arc chord."""

    start: Point2D
    end: Point2D
    bulge: float


@dataclass(frozen=True)
class RevCloudTagIR:
    """Intermediate representation of a revision delta triangle tag."""

    center: Point2D
    triangle_vertices: List[Point2D]
    text: str
    text_height: float


@dataclass(frozen=True)
class RevCloudResult:
    """Result of revision cloud generation."""

    status: str
    message: str
    segment_count: int
    has_tag: bool
    rev_tag: Optional[str]
    processed_count: int
    vertices: List[Point2D] = field(default_factory=list)
    bulge: float = 0.52
    tag: Optional[RevCloudTagIR] = None
    layer: str = "REV"


class RevCloudHandler:
    """Generates revision cloud boundary polylines with outward bulging arcs and optional delta tags."""

    def execute(self, args: RevCloudArgs) -> RevCloudResult:
        """Execute revision cloud with strict C# outward bulge and delta tag parity."""
        has_tag = bool(args.rev_tag and args.rev_tag.strip())
        tag_str = args.rev_tag.strip() if has_tag and args.rev_tag else None

        if args.boundary_points is None or len(args.boundary_points) < 3:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Revision cloud requires at least 3 boundary vertices."
            )

        arc_length = _validate_positive(args.arc_length, "ArcLength")
        bulge = _validate_positive(args.bulge, "Bulge")

        pts: List[Point2D] = []
        for i, pt in enumerate(args.boundary_points):
            if pt is None or len(pt) < 2:
                continue
            x = _validate_finite(pt[0], f"BoundaryPoints[{i}][0]")
            y = _validate_finite(pt[1], f"BoundaryPoints[{i}][1]")
            pts.append(Point2D(x, y))

        if len(pts) < 3:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Revision cloud requires at least 3 valid boundary vertices."
            )

        layer = args.layer.strip() if args.layer and args.layer.strip() else "REV"

        # Calculate signed area to determine winding order:
        # Area = 0.5 * sum(x_i * y_{i+1} - x_{i+1} * y_i)
        signed_area = 0.0
        n = len(pts)
        for i in range(n):
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            signed_area += (p1.x * p2.y) - (p2.x * p1.y)
        signed_area *= 0.5

        # Bulge sign parity:
        # If CCW (signed_area > 0), outward billowing requires negative bulge (-abs(Bulge)).
        # If CW (signed_area <= 0), outward billowing requires positive bulge (+abs(Bulge)).
        outward_bulge = -abs(bulge) if signed_area > 0.0 else abs(bulge)

        # Subdivide edges into arc segments
        cloud_vertices: List[Point2D] = []
        for i in range(n):
            p_start = pts[i]
            p_end = pts[(i + 1) % n]
            dist = math.hypot(p_end.x - p_start.x, p_end.y - p_start.y)
            segs = max(1, int(round(dist / arc_length)))

            dx = (p_end.x - p_start.x) / segs
            dy = (p_end.y - p_start.y) / segs

            for s in range(segs):
                cloud_vertices.append(Point2D(p_start.x + (s * dx), p_start.y + (s * dy)))

        total_entities = 1  # polyline

        # Optional Revision Delta Tag
        tag_ir: Optional[RevCloudTagIR] = None
        if has_tag and tag_str:
            tag_size = max(2.0, float(args.tag_size))
            h = tag_size * math.sqrt(3.0) / 2.0

            # Place tag near first vertex, shifted outward
            v0 = pts[0]
            tx = v0.x + tag_size
            ty = v0.y + tag_size

            # Equilateral triangle
            triangle = [
                Point2D(tx, ty + (2.0 * h / 3.0)),  # Apex
                Point2D(tx - (tag_size / 2.0), ty - (h / 3.0)),
                Point2D(tx + (tag_size / 2.0), ty - (h / 3.0)),
            ]
            tag_ir = RevCloudTagIR(
                center=Point2D(tx, ty),
                triangle_vertices=triangle,
                text=tag_str,
                text_height=tag_size * 0.45,
            )
            total_entities += 2  # triangle polyline + text

        msg = f"Revision cloud created with {len(cloud_vertices)} arc segments."
        return RevCloudResult(
            status="OK",
            message=msg,
            segment_count=len(cloud_vertices),
            has_tag=has_tag,
            rev_tag=tag_str,
            processed_count=total_entities,
            vertices=cloud_vertices,
            bulge=outward_bulge,
            tag=tag_ir,
            layer=layer,
        )


# ============================================================================
# 3. ROOM NUMBER (cadmind-room-number / TierB Wave 8)
# ============================================================================


@dataclass(frozen=True)
class RoomNumberArgs:
    """Input arguments for room number annotation tag."""

    center_x: float = 0.0
    center_y: float = 0.0
    room_name: str = "OFFICE"
    room_number: str = "101"
    area_sq_m: float = 0.0
    box_width: float = 900.0
    box_height: float = 360.0
    text_height: float = 150.0
    layer: str = "A-ANNO-ROOM"


@dataclass(frozen=True)
class RoomBoxIR:
    """Intermediate representation of room annotation enclosure and text alignments."""

    center: Point2D
    box_width: float
    box_height: float
    box_vertices: List[Point2D]
    room_name: str
    room_name_pos: Point2D
    room_number: str
    room_number_pos: Point2D
    area_sq_m: float
    area_text: Optional[str] = None
    area_pos: Optional[Point2D] = None
    text_height: float = 150.0


@dataclass(frozen=True)
class RoomNumberResult:
    """Result of room number annotation."""

    status: str
    message: str
    layer: str
    entity_count: int
    room_name: str
    room_number: str
    box_width: float
    box_height: float
    handles: Optional[List[str]] = None
    box_ir: Optional[RoomBoxIR] = None


class RoomNumberHandler:
    """Places architectural room identifier tags with box enclosure, room name, and optional area."""

    def execute(self, args: RoomNumberArgs) -> RoomNumberResult:
        """Execute room number tag with strict C# layout parity."""
        cx = _validate_finite(args.center_x, "CenterX")
        cy = _validate_finite(args.center_y, "CenterY")
        box_w = _validate_finite(args.box_width, "BoxWidth")
        box_h = _validate_finite(args.box_height, "BoxHeight")
        text_h = _validate_finite(args.text_height, "TextHeight")
        area_sq_m = _validate_finite(args.area_sq_m, "AreaSqM")

        if not args.room_name or not args.room_name.strip() or not args.room_number or not args.room_number.strip():
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: RoomName and RoomNumber must not be empty."
            )

        if box_w <= 1e-4 or box_h <= 1e-4 or text_h <= 1e-4:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: BoxWidth, BoxHeight, and TextHeight must be positive."
            )

        if box_h < 1.4 * text_h or box_w < 2.0 * text_h:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Box dimensions too small for text height."
            )

        if area_sq_m < 0.0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: AreaSqM cannot be negative."
            )

        layer = args.layer.strip() if args.layer and args.layer.strip() else "A-ANNO-ROOM"
        r_name = args.room_name.strip().upper()
        r_num = args.room_number.strip()

        hw = box_w / 2.0
        hh = box_h / 2.0

        # 1. Closed 4-vertex Box Polyline centered at (cx, cy)
        box_vertices = [
            Point2D(cx - hw, cy - hh),
            Point2D(cx + hw, cy - hh),
            Point2D(cx + hw, cy + hh),
            Point2D(cx - hw, cy + hh),
        ]

        # 2. Room Number text centered in box
        num_pos = Point2D(cx, cy)

        # 3. Room Name text centered above box
        name_y = cy + hh + (0.85 * text_h)
        name_pos = Point2D(cx, name_y)

        # 4. Optional Area text below box
        area_text_str: Optional[str] = None
        area_pos: Optional[Point2D] = None
        if area_sq_m > 0.0:
            area_y = cy - hh - (0.75 * text_h)
            area_text_str = f"{area_sq_m:.1f} m\u00B2"
            area_pos = Point2D(cx, area_y)

        entity_count = 4 if area_sq_m > 0.0 else 3

        box_ir = RoomBoxIR(
            center=Point2D(cx, cy),
            box_width=box_w,
            box_height=box_h,
            box_vertices=box_vertices,
            room_name=r_name,
            room_name_pos=name_pos,
            room_number=r_num,
            room_number_pos=num_pos,
            area_sq_m=area_sq_m,
            area_text=area_text_str,
            area_pos=area_pos,
            text_height=text_h,
        )

        msg = f"Room number tag placed: {r_name} {r_num}"
        return RoomNumberResult(
            status="OK",
            message=msg,
            layer=layer,
            entity_count=entity_count,
            room_name=r_name,
            room_number=r_num,
            box_width=box_w,
            box_height=box_h,
            handles=[],
            box_ir=box_ir,
        )


# ============================================================================
# 4. AUTO NUMBER (cadmind-auto-number / TierB Wave 9)
# ============================================================================


@dataclass(frozen=True)
class AutoNumberArgs:
    """Input arguments for sequential auto-numbering."""

    points: Optional[Sequence[Sequence[float]]] = None
    start_number: int = 1
    step: int = 1
    padding: int = 2
    prefix: str = "TAG-"
    suffix: str = ""
    text_height: float = 100.0
    enclosure: str = "NONE"  # "NONE", "CIRCLE", "BOX"
    enclosure_padding: float = 40.0
    layer: str = "A-ANNO-TAG"


@dataclass(frozen=True)
class AutoNumberTagIR:
    """Intermediate representation of an individual sequenced tag."""

    index: int
    point: Point2D
    label: str
    text_height: float
    enclosure: str
    circle_radius: Optional[float] = None
    box_vertices: Optional[List[Point2D]] = None


@dataclass(frozen=True)
class AutoNumberResult:
    """Result of sequential auto-numbering."""

    status: str
    message: str
    layer: str
    tag_count: int
    entity_count: int
    first_label: str
    last_label: str
    handles: Optional[List[str]] = None
    tags: List[AutoNumberTagIR] = field(default_factory=list)


class AutoNumberHandler:
    """Generates sequential annotation tags along point paths with optional circle or box enclosures."""

    def execute(self, args: AutoNumberArgs) -> AutoNumberResult:
        """Execute auto-numbering with strict C# padding, enclosure, and deduplication parity."""
        if args.points is None or len(args.points) == 0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Points array must not be empty.")

        if args.step == 0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Step cannot be zero.")

        text_height = _validate_positive(args.text_height, "TextHeight")

        if args.padding < 0 or args.padding > 8:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Padding must be between 0 and 8.")

        clean_points: List[Point2D] = []
        for i, pt in enumerate(args.points):
            if pt is None or len(pt) < 2:
                raise DegenerateGeometryError(
                    f"DEGENERATE_GEOMETRY: Point {i} contains invalid or non-finite coordinates."
                )
            px = _validate_finite(pt[0], f"Points[{i}][0]")
            py = _validate_finite(pt[1], f"Points[{i}][1]")
            p_cur = Point2D(px, py)

            if i > 0:
                p_prev = clean_points[i - 1]
                dx = p_cur.x - p_prev.x
                dy = p_cur.y - p_prev.y
                if math.sqrt((dx * dx) + (dy * dy)) <= 1e-4:
                    raise DegenerateGeometryError(
                        f"DEGENERATE_GEOMETRY: Consecutive duplicate points detected at index {i}."
                    )
            clean_points.append(p_cur)

        layer = args.layer.strip() if args.layer and args.layer.strip() else "A-ANNO-TAG"
        prefix = args.prefix if args.prefix is not None else ""
        suffix = args.suffix if args.suffix is not None else ""
        enclosure = (args.enclosure or "NONE").strip().upper()
        enclosure_padding = float(args.enclosure_padding)

        tags_ir: List[AutoNumberTagIR] = []
        first_label = ""
        last_label = ""

        for i, pt in enumerate(clean_points):
            num = args.start_number + (i * args.step)
            if args.padding > 0:
                if num < 0:
                    num_str = f"-{abs(num):0{args.padding}d}"
                else:
                    num_str = f"{num:0{args.padding}d}"
            else:
                num_str = str(num)

            label = f"{prefix}{num_str}{suffix}"
            if i == 0:
                first_label = label
            if i == len(clean_points) - 1:
                last_label = label

            px, py = pt.x, pt.y
            circle_radius: Optional[float] = None
            box_vertices: Optional[List[Point2D]] = None

            if enclosure == "CIRCLE":
                circle_radius = (0.5 * text_height * max(1.5, float(len(label)))) + enclosure_padding
            elif enclosure == "BOX":
                hw = (0.5 * text_height * max(1.5, float(len(label)))) + enclosure_padding
                hh = (0.75 * text_height) + enclosure_padding
                box_vertices = [
                    Point2D(px - hw, py - hh),
                    Point2D(px + hw, py - hh),
                    Point2D(px + hw, py + hh),
                    Point2D(px - hw, py + hh),
                ]

            tags_ir.append(
                AutoNumberTagIR(
                    index=i,
                    point=pt,
                    label=label,
                    text_height=text_height,
                    enclosure=enclosure,
                    circle_radius=circle_radius,
                    box_vertices=box_vertices,
                )
            )

        tag_count = len(clean_points)
        entity_count = tag_count if enclosure == "NONE" else tag_count * 2
        msg = f"Auto-numbered {tag_count} points."

        return AutoNumberResult(
            status="OK",
            message=msg,
            layer=layer,
            tag_count=tag_count,
            entity_count=entity_count,
            first_label=first_label,
            last_label=last_label,
            handles=[],
            tags=tags_ir,
        )


# ============================================================================
# 5. DRAWING FRAME (cadmind-drawing-frame / Core Tools)
# ============================================================================


ISO_PAPER_SIZES: Dict[str, Tuple[float, float]] = {
    "A0": (1189.0, 841.0),
    "A1": (841.0, 594.0),
    "A2": (594.0, 420.0),
    "A3": (420.0, 297.0),
    "A4": (297.0, 210.0),
}


@dataclass(frozen=True)
class DrawingFrameArgs:
    """Input arguments for ISO drawing border and title block frame."""

    size: str = "A3"
    scale: float = 1.0
    standard: str = "ISO"
    orientation: str = "landscape"  # "landscape" or "portrait"
    title_block: bool = True
    layer: str = "FRAME"


@dataclass(frozen=True)
class DrawingFrameIR:
    """Intermediate representation of border polylines and title block area."""

    size: str
    standard: str
    scale: float
    orientation: str
    width: float
    height: float
    outer_border: List[Point2D]
    inner_margin_border: List[Point2D]
    title_block_border: Optional[List[Point2D]] = None


@dataclass(frozen=True)
class DrawingFrameResult:
    """Result of drawing frame generation."""

    status: str
    standard: str
    size: str
    scale: float
    width: float
    height: float
    frame_handles: List[str] = field(default_factory=list)
    frame_ir: Optional[DrawingFrameIR] = None


class DrawingFrameHandler:
    """Generates standard ISO drawing sheets with filing margin and 180x36mm title block placeholder."""

    def execute(self, args: DrawingFrameArgs) -> DrawingFrameResult:
        """Execute drawing frame generation matching C# ISO dimensions and scale offsets."""
        scale = 1.0 if args.scale <= 0.0 or not math.isfinite(args.scale) else float(args.scale)

        size_key = args.size.strip().upper() if args.size else "A3"
        dims = ISO_PAPER_SIZES.get(size_key, (420.0, 297.0))

        w = dims[0] * scale
        h = dims[1] * scale

        orientation = args.orientation.strip().lower() if args.orientation else "landscape"
        if orientation == "portrait":
            w, h = h, w

        # 1. Outer border (0,0) to (w,h)
        outer_border = [
            Point2D(0.0, 0.0),
            Point2D(w, 0.0),
            Point2D(w, h),
            Point2D(0.0, h),
        ]

        # 2. Inner margin border (10mm standard, 25mm left filing margin)
        margin = 10.0 * scale
        left_margin = 25.0 * scale
        inner_margin_border = [
            Point2D(left_margin, margin),
            Point2D(w - margin, margin),
            Point2D(w - margin, h - margin),
            Point2D(left_margin, h - margin),
        ]

        # 3. Title block placeholder (180x36mm standard block anchored at lower-right)
        tb_border: Optional[List[Point2D]] = None
        handles = ["HANDLE_OUTER", "HANDLE_INNER"]
        if args.title_block:
            tb_w = 180.0 * scale
            tb_h = 36.0 * scale
            tb_x = w - margin - tb_w
            tb_y = margin
            tb_border = [
                Point2D(tb_x, tb_y),
                Point2D(tb_x + tb_w, tb_y),
                Point2D(tb_x + tb_w, tb_y + tb_h),
                Point2D(tb_x, tb_y + tb_h),
            ]
            handles.append("HANDLE_TITLEBLOCK")

        frame_ir = DrawingFrameIR(
            size=args.size,
            standard=args.standard,
            scale=scale,
            orientation=orientation,
            width=w,
            height=h,
            outer_border=outer_border,
            inner_margin_border=inner_margin_border,
            title_block_border=tb_border,
        )

        return DrawingFrameResult(
            status="OK",
            standard=args.standard,
            size=args.size,
            scale=scale,
            width=w,
            height=h,
            frame_handles=handles,
            frame_ir=frame_ir,
        )
