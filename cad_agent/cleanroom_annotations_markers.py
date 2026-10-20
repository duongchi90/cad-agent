"""cad_agent/cleanroom_annotations_markers.py.

Batch S2: Architectural & Engineering Annotations, Markers, and Openings.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierBWave7Handlers.cs: GeneralNotesHandler (cadmind-general-notes)
  - TierBWave7Handlers.cs: LevelMarkerHandler (cadmind-level-marker)
  - TierBWave8Handlers.cs: SlopeArrowHandler (cadmind-slope-arrow)
  - TierBWave9Handlers.cs: GridBubbleHandler (cadmind-grid-bubble)
  - TierBWave16Handlers.cs: OpeningInsertHandler (cadmind-opening-insert)

Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D, Arc2D, CircleIR),
strict IEEE-754 machine-epsilon safety, Banker's rounding parity,
and zero external pip dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from cad_agent.cleanroom_mechanical import Arc2D, CircleIR, LineSegment2D, Point2D

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


# ============================================================================
# 1. GENERAL NOTES (cadmind-general-notes / TierB Wave 7)
# ============================================================================


@dataclass(frozen=True)
class GeneralNotesArgs:
    """Input arguments for general notes generation."""

    origin: Optional[Sequence[float]] = None
    title: str = "GENERAL NOTES"
    notes: Optional[Sequence[str]] = None
    width: float = 120.0
    header_height: float = 4.0
    text_height: float = 2.5
    line_spacing: float = 5.0
    has_border: bool = True
    layer: str = "S-NOTE"


@dataclass(frozen=True)
class GeneralNoteParagraphIR:
    """Intermediate representation of an individual numbered note paragraph."""

    index: int
    text: str
    location: Point2D
    width: float
    text_height: float
    estimated_lines: int
    height: float


@dataclass(frozen=True)
class GeneralNotesResult:
    """Result of general notes generation."""

    status: str
    message: str
    title: str
    note_count: int
    total_height: float
    processed_count: int
    paragraphs: List[GeneralNoteParagraphIR] = field(default_factory=list)
    border_vertices: Optional[List[Point2D]] = None
    divider: Optional[LineSegment2D] = None
    layer: str = "S-NOTE"


class GeneralNotesHandler:
    """Generates formatted multi-line general notes with header, divider, and border enclosure."""

    def execute(self, args: GeneralNotesArgs) -> GeneralNotesResult:
        """Execute general notes layout with exact C# geometry and wrapping estimates."""
        if args.notes is None or len(args.notes) == 0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Notes array must contain at least one note.")

        width = _validate_positive(args.width, "Width")
        header_height = _validate_positive(args.header_height, "HeaderHeight")
        text_height = _validate_positive(args.text_height, "TextHeight")
        line_spacing = _validate_positive(args.line_spacing, "LineSpacing")

        ox, oy = 0.0, 0.0
        if args.origin is not None and len(args.origin) >= 2:
            ox = _validate_finite(args.origin[0], "Origin[0]")
            oy = _validate_finite(args.origin[1], "Origin[1]")

        title = args.title.strip() if args.title and args.title.strip() else "GENERAL NOTES"
        layer = args.layer.strip() if args.layer and args.layer.strip() else "S-NOTE"

        total_entities = 0
        margin = 5.0
        usable_width = max(10.0, width - (2.0 * margin))

        # 1. Title Text
        cur_y = oy - margin - header_height
        total_entities += 1

        # 2. Horizontal divider below title
        cur_y -= 3.0
        divider = LineSegment2D(Point2D(ox, cur_y), Point2D(ox + width, cur_y))
        total_entities += 1

        # 3. Notes paragraphs
        cur_y -= margin
        note_index = 1
        paragraphs: List[GeneralNoteParagraphIR] = []

        for raw_note in args.notes:
            if not raw_note or not raw_note.strip():
                continue
            note = raw_note.strip()
            if not note[0].isdigit():
                note = f"{note_index}. {note}"

            loc = Point2D(ox + margin, cur_y)
            total_entities += 1

            # Advance cursor down matching C# calculation
            char_per_line = max(10.0, usable_width / (text_height * 0.6))
            est_lines = int(max(1.0, math.ceil(len(note) / char_per_line)))
            note_h = (est_lines * text_height * 1.3) + line_spacing

            paragraphs.append(
                GeneralNoteParagraphIR(
                    index=note_index,
                    text=note,
                    location=loc,
                    width=usable_width,
                    text_height=text_height,
                    estimated_lines=est_lines,
                    height=note_h,
                )
            )
            cur_y -= note_h
            note_index += 1

        cur_y -= margin
        total_height = abs(oy - cur_y)

        # 4. Outer border polyline
        border_vertices: Optional[List[Point2D]] = None
        if args.has_border:
            border_vertices = [
                Point2D(ox, oy),
                Point2D(ox + width, oy),
                Point2D(ox + width, oy - total_height),
                Point2D(ox, oy - total_height),
            ]
            total_entities += 1

        actual_notes_count = len(paragraphs)
        msg = f"General notes created successfully with {actual_notes_count} notes."
        return GeneralNotesResult(
            status="OK",
            message=msg,
            title=title,
            note_count=actual_notes_count,
            total_height=total_height,
            processed_count=total_entities,
            paragraphs=paragraphs,
            border_vertices=border_vertices,
            divider=divider,
            layer=layer,
        )


# ============================================================================
# 2. LEVEL MARKER (cadmind-level-marker / TierB Wave 7)
# ============================================================================


@dataclass(frozen=True)
class LevelMarkerArgs:
    """Input arguments for elevation datum level marker."""

    origin: Optional[Sequence[float]] = None
    elevation: float = 0.0
    shelf_length: float = 25.0
    marker_size: float = 5.0
    text_height: float = 3.0
    direction: str = "Right"  # "Right" or "Left"
    precision: int = 3
    prefix: str = "EL. "
    layer: str = "S-LEVEL"


@dataclass(frozen=True)
class LevelMarkerResult:
    """Result of level marker generation."""

    status: str
    message: str
    formatted_elevation: str
    elevation: float
    processed_count: int
    indicator_triangle: List[Point2D] = field(default_factory=list)
    shelf_line: Optional[LineSegment2D] = None
    text_position: Optional[Point2D] = None
    layer: str = "S-LEVEL"


class LevelMarkerHandler:
    """Places elevation datum level markers with inverted triangle target, horizontal shelf, and formatted label."""

    @staticmethod
    def format_elevation(elevation: float, prefix: Optional[str], precision: int) -> str:
        """Format signed elevation with plus/minus prefix and fixed decimal precision matching C#."""
        pfx = prefix if prefix is not None else "EL. "
        prec = max(0, min(8, int(precision)))
        if abs(elevation) < 1e-6:
            return f"{pfx}\u00B1{0.0:.{prec}f}"
        if elevation > 0.0:
            return f"{pfx}+{elevation:.{prec}f}"
        return f"{pfx}-{abs(elevation):.{prec}f}"

    def execute(self, args: LevelMarkerArgs) -> LevelMarkerResult:
        """Execute level marker layout with strict inverted triangle and shelf parity."""
        marker_size = _validate_positive(args.marker_size, "MarkerSize")
        shelf_length = _validate_positive(args.shelf_length, "ShelfLength")
        text_height = _validate_positive(args.text_height, "TextHeight")
        elevation = _validate_finite(args.elevation, "Elevation")

        ox, oy = 0.0, 0.0
        if args.origin is not None and len(args.origin) >= 2:
            ox = _validate_finite(args.origin[0], "Origin[0]")
            oy = _validate_finite(args.origin[1], "Origin[1]")

        layer = args.layer.strip() if args.layer and args.layer.strip() else "S-LEVEL"
        dir_x = -1.0 if args.direction and args.direction.strip().lower() == "left" else 1.0
        formatted_elevation = self.format_elevation(elevation, args.prefix, args.precision)

        total_entities = 0

        # 1. Triangle Indicator (inverted triangle: apex at (ox, oy), flat top at y = oy + marker_size)
        half_size = marker_size / 2.0
        triangle = [
            Point2D(ox, oy),  # Apex
            Point2D(ox - half_size, oy + marker_size),
            Point2D(ox + half_size, oy + marker_size),
        ]
        total_entities += 1

        # 2. Shelf Line extending horizontally from top of triangle
        shelf_start_y = oy + marker_size
        shelf_start_x = ox
        shelf_end_x = ox + (dir_x * shelf_length)
        shelf = LineSegment2D(Point2D(shelf_start_x, shelf_start_y), Point2D(shelf_end_x, shelf_start_y))
        total_entities += 1

        # 3. Elevation Text above shelf line
        text_x = ox + 2.0 if dir_x > 0 else ox - 2.0
        text_y = shelf_start_y + 1.0
        text_pos = Point2D(text_x, text_y)
        total_entities += 1

        msg = f"Level marker placed: {formatted_elevation}"
        return LevelMarkerResult(
            status="OK",
            message=msg,
            formatted_elevation=formatted_elevation,
            elevation=elevation,
            processed_count=total_entities,
            indicator_triangle=triangle,
            shelf_line=shelf,
            text_position=text_pos,
            layer=layer,
        )


# ============================================================================
# 3. SLOPE ARROW (cadmind-slope-arrow / TierB Wave 8)
# ============================================================================


@dataclass(frozen=True)
class SlopeArrowArgs:
    """Input arguments for slope gradient annotation arrow."""

    start_x: float = 0.0
    start_y: float = 0.0
    end_x: float = 500.0
    end_y: float = 0.0
    slope_percent: float = 2.0
    format: str = "PERCENT"  # "PERCENT", "RATIO", "DEGREE"
    arrow_head_size: float = 150.0
    text_height: float = 120.0
    layer: str = "S-SLOPE"


@dataclass(frozen=True)
class SlopeArrowResult:
    """Result of slope arrow annotation."""

    status: str
    message: str
    layer: str
    entity_count: int
    arrow_length: float
    angle_radians: float
    formatted_label: str
    shaft_line: Optional[LineSegment2D] = None
    arrow_head_vertices: Optional[List[Point2D]] = None
    text_position: Optional[Point2D] = None
    text_rotation: float = 0.0
    handles: Optional[List[str]] = None


class SlopeArrowHandler:
    """Generates directed gradient slope arrows with customizable ratio, percentage, or degree callouts."""

    @staticmethod
    def format_slope(percent: float, format_str: Optional[str]) -> str:
        """Format slope value into PERCENT, RATIO, or DEGREE matching C# format logic."""
        fmt = (format_str or "PERCENT").strip().upper()
        abs_percent = abs(percent)
        if fmt == "RATIO":
            ratio_val = round(100.0 / max(0.001, abs_percent))
            return f"1:{ratio_val:.0f}"
        if fmt == "DEGREE":
            deg = math.atan(abs_percent / 100.0) * 180.0 / math.pi
            return f"{deg:.2f}\u00B0"
        return f"{percent:.1f}%"

    def execute(self, args: SlopeArrowArgs) -> SlopeArrowResult:
        """Execute slope arrow generation with exact geometric shaft and arrowhead calculation."""
        sx = _validate_finite(args.start_x, "StartX")
        sy = _validate_finite(args.start_y, "StartY")
        ex = _validate_finite(args.end_x, "EndX")
        ey = _validate_finite(args.end_y, "EndY")
        slope_pct = _validate_finite(args.slope_percent, "SlopePercent")
        a_size = _validate_finite(args.arrow_head_size, "ArrowHeadSize")
        t_height = _validate_finite(args.text_height, "TextHeight")

        if a_size <= 1e-4 or t_height <= 1e-4:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: ArrowHeadSize and TextHeight must be positive.")

        dx = ex - sx
        dy = ey - sy
        length = math.hypot(dx, dy)

        if length < 3.0 * a_size:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Slope arrow shaft length too short for arrowhead and text."
            )

        if abs(slope_pct) < 1e-6 or abs(slope_pct) > 1000.0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: SlopePercent must be non-zero and within [-1000, 1000]."
            )

        fmt_upper = (args.format or "PERCENT").strip().upper()
        if fmt_upper not in ("PERCENT", "RATIO", "DEGREE"):
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Unknown Format. Expected PERCENT, RATIO, or DEGREE."
            )

        layer = args.layer.strip() if args.layer and args.layer.strip() else "S-SLOPE"
        label = self.format_slope(slope_pct, fmt_upper)
        angle = math.atan2(dy, dx)

        ux = dx / length
        uy = dy / length
        nx = -uy
        ny = ux

        # 1. Shaft line
        shaft = LineSegment2D(Point2D(sx, sy), Point2D(ex, ey))

        # 2. Arrowhead (closed 3-vertex Polyline at End)
        wing1_x = ex - (a_size * ux) + ((a_size / 3.0) * nx)
        wing1_y = ey - (a_size * uy) + ((a_size / 3.0) * ny)
        wing2_x = ex - (a_size * ux) - ((a_size / 3.0) * nx)
        wing2_y = ey - (a_size * uy) - ((a_size / 3.0) * ny)

        arrow_head = [
            Point2D(ex, ey),
            Point2D(wing1_x, wing1_y),
            Point2D(wing2_x, wing2_y),
        ]

        # 3. Label text position & rotation (always right-side up)
        mid_x = 0.5 * (sx + ex)
        mid_y = 0.5 * (sy + ey)
        text_rot = angle
        n_up_x = nx
        n_up_y = ny

        if angle > math.pi / 2.0 or angle <= -math.pi / 2.0:
            text_rot = angle + math.pi
            n_up_x = -nx
            n_up_y = -ny

        text_x = mid_x + (0.75 * t_height * n_up_x)
        text_y = mid_y + (0.75 * t_height * n_up_y)
        text_pos = Point2D(text_x, text_y)

        msg = f"Slope arrow created: {label}"
        return SlopeArrowResult(
            status="OK",
            message=msg,
            layer=layer,
            entity_count=3,
            arrow_length=length,
            angle_radians=angle,
            formatted_label=label,
            shaft_line=shaft,
            arrow_head_vertices=arrow_head,
            text_position=text_pos,
            text_rotation=text_rot,
            handles=[],
        )


# ============================================================================
# 4. GRID BUBBLE (cadmind-grid-bubble / TierB Wave 9)
# ============================================================================


@dataclass(frozen=True)
class GridBubbleArgs:
    """Input arguments for individual grid axis bubble callout."""

    center_x: float = 0.0
    center_y: float = 0.0
    bubble_radius: float = 250.0
    label: str = "A"
    text_height: float = 250.0
    has_tail: bool = True
    tail_start_x: float = -500.0
    tail_start_y: float = 0.0
    layer: str = "S-GRID"


@dataclass(frozen=True)
class GridBubbleResult:
    """Result of grid bubble generation."""

    status: str
    message: str
    layer: str
    entity_count: int
    label: str
    bubble_radius: float
    center_x: float
    center_y: float
    circle_ir: Optional[CircleIR] = None
    tail_line: Optional[LineSegment2D] = None
    text_position: Optional[Point2D] = None
    handles: Optional[List[str]] = None


class GridBubbleHandler:
    """Places circular grid bubbles with alphanumeric identifiers and optional lead tail lines."""

    def execute(self, args: GridBubbleArgs) -> GridBubbleResult:
        """Execute grid bubble layout with radial tail line termination at perimeter."""
        cx = _validate_finite(args.center_x, "CenterX")
        cy = _validate_finite(args.center_y, "CenterY")
        radius = _validate_finite(args.bubble_radius, "BubbleRadius")
        text_height = _validate_finite(args.text_height, "TextHeight")
        tail_sx = _validate_finite(args.tail_start_x, "TailStartX")
        tail_sy = _validate_finite(args.tail_start_y, "TailStartY")

        if radius <= 1e-4 or text_height <= 1e-4:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: BubbleRadius and TextHeight must be positive.")

        if not args.label or not args.label.strip():
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Label must not be empty.")

        dx = cx - tail_sx
        dy = cy - tail_sy
        tail_len = math.hypot(dx, dy)

        if args.has_tail and tail_len <= radius + 1e-4:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Tail start point must lie strictly outside the bubble circumference."
            )

        layer = args.layer.strip() if args.layer and args.layer.strip() else "S-GRID"
        label = args.label.strip().upper()

        tail_line: Optional[LineSegment2D] = None
        entity_count = 2  # circle + text

        # 1. Optional tail line terminating at bubble perimeter
        if args.has_tail:
            ux = dx / tail_len
            uy = dy / tail_len
            term_x = cx - (radius * ux)
            term_y = cy - (radius * uy)
            tail_line = LineSegment2D(Point2D(tail_sx, tail_sy), Point2D(term_x, term_y))
            entity_count += 1

        # 2. Bubble Circle
        circle_ir = CircleIR(center=Point2D(cx, cy), radius=radius)

        # 3. Text Position centered
        text_pos = Point2D(cx, cy)

        msg = f"Grid bubble placed: [{label}]"
        return GridBubbleResult(
            status="OK",
            message=msg,
            layer=layer,
            entity_count=entity_count,
            label=label,
            bubble_radius=radius,
            center_x=cx,
            center_y=cy,
            circle_ir=circle_ir,
            tail_line=tail_line,
            text_position=text_pos,
            handles=[],
        )


# ============================================================================
# 5. OPENING INSERT (cadmind-opening-insert / TierB Wave 16)
# ============================================================================


@dataclass(frozen=True)
class OpeningInsertArgs:
    """Input arguments for architectural door or window opening insertion."""

    width: float = 900.0
    point: Optional[Sequence[float]] = None
    wall_thickness: float = 220.0
    rotation: float = 0.0
    type: str = "door"  # "door" or "window"
    hinge: str = "left"  # "left" or "right"
    open: str = "up"  # "up" or "down"
    layer: Optional[str] = None


@dataclass(frozen=True)
class OpeningInsertResult:
    """Result of door or window opening insertion."""

    status: str
    message: str
    type: str
    width: float
    wall_thickness: float
    rotation: float
    layer: str
    entity_count: int
    left_jamb: Optional[LineSegment2D] = None
    right_jamb: Optional[LineSegment2D] = None
    glass_lines: Optional[List[LineSegment2D]] = None
    leaf_line: Optional[LineSegment2D] = None
    swing_arc: Optional[Arc2D] = None
    created_handles: Optional[List[str]] = None


class OpeningInsertHandler:
    """Generates 2D architectural wall openings (doors with 90° swing arcs or double-glazed windows)."""

    def execute(self, args: OpeningInsertArgs) -> OpeningInsertResult:
        """Execute opening layout with jambs, glass lines, and swing arcs matching C# vector algebra."""
        width = _validate_finite(args.width, "Width")
        if width <= 0.0:
            raise DegenerateGeometryError("INVALID_WIDTH: Opening width must be positive and finite.")

        wall_thickness = _validate_finite(args.wall_thickness, "WallThickness")
        if wall_thickness <= 0.0:
            raise DegenerateGeometryError("INVALID_WALL_THICKNESS: Wall thickness must be positive and finite.")

        rotation = _validate_finite(args.rotation, "Rotation")

        cx = float(args.point[0]) if args.point is not None and len(args.point) >= 1 else 0.0
        cy = float(args.point[1]) if args.point is not None and len(args.point) >= 2 else 0.0
        center = Point2D(cx, cy)

        is_window = bool(args.type and args.type.strip().lower() == "window")
        kind_str = "window" if is_window else "door"

        target_layer = (
            args.layer.strip()
            if args.layer and args.layer.strip()
            else ("A-GLAZ" if is_window else "A-DOOR")
        )

        rot_rad = rotation * math.pi / 180.0
        # Unit vector u along wall, v normal across wall
        ux = math.cos(rot_rad)
        uy = math.sin(rot_rad)
        vx = -math.sin(rot_rad)
        vy = math.cos(rot_rad)

        hw = width / 2.0
        ht = wall_thickness / 2.0

        # Left jamb: from (C - hw*u - ht*v) to (C - hw*u + ht*v)
        j1_start = Point2D(center.x - (hw * ux) - (ht * vx), center.y - (hw * uy) - (ht * vy))
        j1_end = Point2D(center.x - (hw * ux) + (ht * vx), center.y - (hw * uy) + (ht * vy))
        left_jamb = LineSegment2D(j1_start, j1_end)

        # Right jamb: from (C + hw*u - ht*v) to (C + hw*u + ht*v)
        j2_start = Point2D(center.x + (hw * ux) - (ht * vx), center.y + (hw * uy) - (ht * vy))
        j2_end = Point2D(center.x + (hw * ux) + (ht * vx), center.y + (hw * uy) + (ht * vy))
        right_jamb = LineSegment2D(j2_start, j2_end)

        glass_lines: Optional[List[LineSegment2D]] = None
        leaf_line: Optional[LineSegment2D] = None
        swing_arc: Optional[Arc2D] = None

        if is_window:
            offset = ht / 3.0
            g1_start = Point2D(center.x - (hw * ux) - (offset * vx), center.y - (hw * uy) - (offset * vy))
            g1_end = Point2D(center.x + (hw * ux) - (offset * vx), center.y + (hw * uy) - (offset * vy))
            glass1 = LineSegment2D(g1_start, g1_end)

            g2_start = Point2D(center.x - (hw * ux) + (offset * vx), center.y - (hw * uy) + (offset * vy))
            g2_end = Point2D(center.x + (hw * ux) + (offset * vx), center.y + (hw * uy) + (offset * vy))
            glass2 = LineSegment2D(g2_start, g2_end)

            glass_lines = [glass1, glass2]
            entity_count = 4
        else:
            swing_dir = -1.0 if args.open and args.open.strip().lower() == "down" else 1.0
            is_right_hinge = bool(args.hinge and args.hinge.strip().lower() == "right")

            hinge_pt = (
                Point2D(center.x + (hw * ux), center.y + (hw * uy))
                if is_right_hinge
                else Point2D(center.x - (hw * ux), center.y - (hw * uy))
            )
            open_end = Point2D(
                hinge_pt.x + (width * swing_dir * vx),
                hinge_pt.y + (width * swing_dir * vy),
            )
            leaf_line = LineSegment2D(hinge_pt, open_end)

            # 90 degree swing arc
            if not is_right_hinge:
                if swing_dir > 0:
                    start_angle = rot_rad
                    end_angle = rot_rad + (math.pi / 2.0)
                else:
                    start_angle = rot_rad - (math.pi / 2.0)
                    end_angle = rot_rad
            else:
                if swing_dir > 0:
                    start_angle = rot_rad + (math.pi / 2.0)
                    end_angle = rot_rad + math.pi
                else:
                    start_angle = rot_rad + math.pi
                    end_angle = rot_rad + (3.0 * math.pi / 2.0)

            two_pi = 2.0 * math.pi
            start_angle = (start_angle % two_pi + two_pi) % two_pi
            end_angle = (end_angle % two_pi + two_pi) % two_pi

            swing_arc = Arc2D(
                center=hinge_pt,
                radius=width,
                start_angle_rad=start_angle,
                end_angle_rad=end_angle,
            )
            entity_count = 4

        msg = (
            f"Drawn {kind_str} opening (W={width}, T={wall_thickness}) with "
            f"{entity_count} entities on layer '{target_layer}'."
        )
        return OpeningInsertResult(
            status="SUCCESS",
            message=msg,
            type=kind_str,
            width=width,
            wall_thickness=wall_thickness,
            rotation=rotation,
            layer=target_layer,
            entity_count=entity_count,
            left_jamb=left_jamb,
            right_jamb=right_jamb,
            glass_lines=glass_lines,
            leaf_line=leaf_line,
            swing_arc=swing_arc,
            created_handles=[],
        )
