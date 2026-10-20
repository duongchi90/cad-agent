"""cad_agent/cleanroom_callouts_tables.py.

Batch S3: Detail Callouts, Section Marks, Area Labels, Detail Views & Schedule Tables.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierAWave1Handlers.cs: DetailCalloutHandler (cadmind-detail-callout)
  - TierAWave1Handlers.cs: SectionMarkHandler (cadmind-section-mark)
  - TierAWave1Handlers.cs: AreaLabelHandler (cadmind-area-label)
  - TierAWave6Handlers.cs: DetailViewHandler (cadmind-detail-view)
  - TierAWave6Handlers.cs: ScheduleTableHandler (cadmind-schedule-table)

Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D, Arc2D, CircleIR),
strict IEEE-754 machine-epsilon safety, Banker's rounding parity,
and zero external pip dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence

from cad_agent.cleanroom_mechanical import CircleIR, LineSegment2D, Point2D

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
    """Ensure value is strictly positive (> 1e-6) matching C# epsilon checks."""
    f = _validate_finite(val, name)
    if f <= 1e-6:
        raise DegenerateGeometryError(f"DEGENERATE_GEOMETRY: Parameter '{name}' must be positive (> 1e-6), got {f}.")
    return f


# ============================================================================
# 1. DETAIL CALLOUT (cadmind-detail-callout / TierA Wave 1)
# ============================================================================


@dataclass(frozen=True)
class DetailCalloutArgs:
    """Input arguments for circular detail callout bubbles."""

    center: Optional[Sequence[float]] = None
    radius: float = 6.0
    detail_id: str = "A"
    sheet_ref: str = "S-01"
    leader_endpoint: Optional[Sequence[float]] = None
    layer: str = "DIM"


@dataclass(frozen=True)
class DetailCalloutResult:
    """Result of detail callout placement."""

    status: str
    message: str
    detail_id: str
    sheet_ref: str
    bubble_circle: CircleIR
    dividing_chord: LineSegment2D
    detail_id_pos: Point2D
    sheet_ref_pos: Point2D
    leader_line: Optional[LineSegment2D] = None
    processed_count: int = 4
    layer: str = "DIM"


class DetailCalloutHandler:
    """Generates two-tier circular detail callouts with dividing chord line and optional leader."""

    def execute(self, args: DetailCalloutArgs) -> DetailCalloutResult:
        """Execute detail callout bubble layout with exact C# geometry and text positioning."""
        radius = _validate_positive(args.radius, "Radius")

        cx, cy = 0.0, 0.0
        if args.center is not None and len(args.center) >= 2:
            cx = _validate_finite(args.center[0], "Center[0]")
            cy = _validate_finite(args.center[1], "Center[1]")
        center = Point2D(cx, cy)

        layer = args.layer.strip() if args.layer and args.layer.strip() else "DIM"
        detail_id = args.detail_id.strip() if args.detail_id else "A"
        sheet_ref = args.sheet_ref.strip() if args.sheet_ref else "S-01"

        # 1. Bubble Circle
        bubble_circle = CircleIR(center=center, radius=radius)

        # 2. Dividing Chord Line: from (cx - radius, cy) to (cx + radius, cy)
        dividing_chord = LineSegment2D(
            Point2D(cx - radius, cy),
            Point2D(cx + radius, cy),
        )

        # 3. Detail ID (Upper Text) at (cx - 1.0, cy + radius * 0.25)
        detail_id_pos = Point2D(cx - 1.0, cy + (radius * 0.25))

        # 4. Sheet Ref (Lower Text) at (cx - 2.0, cy - radius * 0.65)
        sheet_ref_pos = Point2D(cx - 2.0, cy - (radius * 0.65))

        # 5. Optional Leader Line
        leader_line: Optional[LineSegment2D] = None
        processed_count = 4

        if args.leader_endpoint is not None and len(args.leader_endpoint) >= 2:
            lx = _validate_finite(args.leader_endpoint[0], "LeaderEndpoint[0]")
            ly = _validate_finite(args.leader_endpoint[1], "LeaderEndpoint[1]")
            leader_pt = Point2D(lx, ly)
            dist = center.distance_to(leader_pt)
            if dist > 1e-6:
                ux = (leader_pt.x - center.x) / dist
                uy = (leader_pt.y - center.y) / dist
                rim = Point2D(center.x + (ux * radius), center.y + (uy * radius))
                leader_line = LineSegment2D(rim, leader_pt)
                processed_count += 1

        msg = f"Detail callout bubble '{detail_id}/{sheet_ref}' placed at ({cx:.2f}, {cy:.2f})."
        return DetailCalloutResult(
            status="OK",
            message=msg,
            detail_id=detail_id,
            sheet_ref=sheet_ref,
            bubble_circle=bubble_circle,
            dividing_chord=dividing_chord,
            detail_id_pos=detail_id_pos,
            sheet_ref_pos=sheet_ref_pos,
            leader_line=leader_line,
            processed_count=processed_count,
            layer=layer,
        )


# ============================================================================
# 2. SECTION MARK (cadmind-section-mark / TierA Wave 1)
# ============================================================================


@dataclass(frozen=True)
class SectionMarkArgs:
    """Input arguments for section cutting plane indicators."""

    start_point: Optional[Sequence[float]] = None
    end_point: Optional[Sequence[float]] = None
    section_id: str = "A"
    direction: str = "Normal"
    arrow_size: float = 4.0
    layer: str = "DIM"


@dataclass(frozen=True)
class SectionMarkResult:
    """Result of section cutting mark placement."""

    status: str
    message: str
    full_label: str
    tip_label: str
    cut_line: LineSegment2D
    arrow_line_start: LineSegment2D
    arrow_line_end: LineSegment2D
    text_pos_start: Point2D
    text_pos_end: Point2D
    processed_count: int = 5
    layer: str = "DIM"


class SectionMarkHandler:
    """Generates orthogonal cutting plane indicators with terminal direction arrows and paired identifiers."""

    def execute(self, args: SectionMarkArgs) -> SectionMarkResult:
        """Execute section mark with exact perpendicular arrow offsets and ID normalization."""
        arrow_size = _validate_positive(args.arrow_size, "ArrowSize")

        p1_x, p1_y = 0.0, 0.0
        p2_x, p2_y = 100.0, 0.0

        if args.start_point is not None and len(args.start_point) >= 2:
            p1_x = _validate_finite(args.start_point[0], "StartPoint[0]")
            p1_y = _validate_finite(args.start_point[1], "StartPoint[1]")

        if args.end_point is not None and len(args.end_point) >= 2:
            p2_x = _validate_finite(args.end_point[0], "EndPoint[0]")
            p2_y = _validate_finite(args.end_point[1], "EndPoint[1]")

        p1 = Point2D(p1_x, p1_y)
        p2 = Point2D(p2_x, p2_y)

        dx = p2.x - p1.x
        dy = p2.y - p1.y
        length = math.hypot(dx, dy)

        if length <= 1e-6:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Section cutting line start and end points are coincident."
            )

        layer = args.layer.strip() if args.layer and args.layer.strip() else "DIM"

        # Direction vector along cutting plane, normal perpendicular
        dir_x = dx / length
        dir_y = dy / length
        norm_x = -dir_y
        norm_y = dir_x

        # 1. Main Cutting Line
        cut_line = LineSegment2D(p1, p2)

        # 2. Arrow Line 1 at StartPoint
        arr_end1 = Point2D(p1.x + (norm_x * arrow_size), p1.y + (norm_y * arrow_size))
        arrow_line_start = LineSegment2D(p1, arr_end1)

        # 3. Arrow Line 2 at EndPoint
        arr_end2 = Point2D(p2.x + (norm_x * arrow_size), p2.y + (norm_y * arrow_size))
        arrow_line_end = LineSegment2D(p2, arr_end2)

        # 4. Section ID Normalization
        raw_id = args.section_id.strip() if args.section_id and args.section_id.strip() else "A"
        if "-" in raw_id:
            parts = raw_id.split("-")
            tip_text = parts[0].strip() if parts[0].strip() else "A"
            full_label = raw_id
        else:
            full_label = f"{raw_id}-{raw_id}"
            tip_text = raw_id

        # 5. Section ID Text Positions (arrow_end + normal * 1.5)
        text_pos1 = Point2D(arr_end1.x + (norm_x * 1.5), arr_end1.y + (norm_y * 1.5))
        text_pos2 = Point2D(arr_end2.x + (norm_x * 1.5), arr_end2.y + (norm_y * 1.5))

        msg = f"Section cutting mark '{full_label}' drawn with {5} entities on layer '{layer}'."
        return SectionMarkResult(
            status="OK",
            message=msg,
            full_label=full_label,
            tip_label=tip_text,
            cut_line=cut_line,
            arrow_line_start=arrow_line_start,
            arrow_line_end=arrow_line_end,
            text_pos_start=text_pos1,
            text_pos_end=text_pos2,
            processed_count=5,
            layer=layer,
        )


# ============================================================================
# 3. AREA LABEL (cadmind-area-label / TierA Wave 1)
# ============================================================================


@dataclass(frozen=True)
class AreaLabelArgs:
    """Input arguments for geometric area calculation and callout label."""

    position: Optional[Sequence[float]] = None
    prefix: str = "Area: "
    unit: str = "m2"
    scale_factor: float = 0.000001
    area_value_mm2: float = 1000000.0  # Headless analytical input area in mm²
    layer: str = "TEXT"


@dataclass(frozen=True)
class AreaLabelResult:
    """Result of area label placement."""

    status: str
    message: str
    label_text: str
    display_area: float
    raw_area: float
    position: Point2D
    processed_count: int = 1
    layer: str = "TEXT"


class AreaLabelHandler:
    """Calculates scaled area callouts and formats standard square meter or custom unit text tags."""

    def execute(self, args: AreaLabelArgs) -> AreaLabelResult:
        """Execute area scaling and formatting matching C# ScaleFactor logic."""
        if not isinstance(args.scale_factor, (int, float)) or args.scale_factor <= 0.0 or math.isnan(args.scale_factor) or math.isinf(args.scale_factor):
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: ScaleFactor must be positive and non-zero.")
        scale_factor = float(args.scale_factor)

        if not isinstance(args.area_value_mm2, (int, float)) or args.area_value_mm2 <= 0.0 or math.isnan(args.area_value_mm2) or math.isinf(args.area_value_mm2):
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: AreaValueMm2 must be positive and non-zero.")
        raw_area = float(args.area_value_mm2)

        px, py = 0.0, 0.0
        if args.position is not None and len(args.position) >= 2:
            px = _validate_finite(args.position[0], "Position[0]")
            py = _validate_finite(args.position[1], "Position[1]")
        pos = Point2D(px, py)

        layer = args.layer.strip() if args.layer and args.layer.strip() else "TEXT"
        prefix = args.prefix if args.prefix is not None else "Area: "
        unit = args.unit if args.unit is not None else "m2"

        display_area = raw_area * scale_factor
        label_text = f"{prefix}{display_area:.2f} {unit}"

        msg = f"Area label '{label_text}' placed on layer '{layer}'."
        return AreaLabelResult(
            status="OK",
            message=msg,
            label_text=label_text,
            display_area=display_area,
            raw_area=raw_area,
            position=pos,
            processed_count=1,
            layer=layer,
        )


# ============================================================================
# 4. DETAIL VIEW (cadmind-detail-view / TierA Wave 6)
# ============================================================================


@dataclass(frozen=True)
class DetailViewArgs:
    """Input arguments for mechanical detail view callout."""

    center: Optional[Sequence[float]] = None
    radius: float = 10.0
    label: str = "A"
    scale: Optional[str] = None
    leader_angle: float = 45.0
    height: float = 3.5
    layer: str = "M-DETAIL"


@dataclass(frozen=True)
class DetailViewResult:
    """Result of detail view callout generation."""

    status: str
    message: str
    label: str
    radius: float
    boundary_circle: CircleIR
    leader_line: LineSegment2D
    shoulder_line: LineSegment2D
    label_text_pos: Point2D
    scale_text_pos: Optional[Point2D] = None
    processed_count: int = 4
    layer: str = "M-DETAIL"


class DetailViewHandler:
    """Generates mechanical detail boundary circles with elbow leader lines and scale designations."""

    def execute(self, args: DetailViewArgs) -> DetailViewResult:
        """Execute detail view layout matching C# elbow shoulder offsets and scale positioning."""
        radius = _validate_positive(args.radius, "Radius")
        height = _validate_positive(args.height, "Height")
        leader_angle = _validate_finite(args.leader_angle, "LeaderAngle")

        cx, cy = 0.0, 0.0
        if args.center is not None and len(args.center) >= 2:
            cx = _validate_finite(args.center[0], "Center[0]")
            cy = _validate_finite(args.center[1], "Center[1]")
        center = Point2D(cx, cy)

        label = args.label.strip() if args.label and args.label.strip() else "A"
        layer = args.layer.strip() if args.layer and args.layer.strip() else "M-DETAIL"

        # 1. Detail boundary circle
        boundary_circle = CircleIR(center=center, radius=radius)
        total_entities = 1

        # 2. Leader line and shoulder
        rad = (leader_angle % 360.0) * math.pi / 180.0
        p_start = Point2D(cx + math.cos(rad) * radius, cy + math.sin(rad) * radius)
        ext_len = max(10.0, radius * 0.4)
        p_elbow = Point2D(p_start.x + math.cos(rad) * ext_len, p_start.y + math.sin(rad) * ext_len)

        dir_x = 1.0 if math.cos(rad) >= 0.0 else -1.0
        shoulder_len = 16.0
        p_end = Point2D(p_elbow.x + (dir_x * shoulder_len), p_elbow.y)

        leader_line = LineSegment2D(p_start, p_elbow)
        shoulder_line = LineSegment2D(p_elbow, p_end)
        total_entities += 2

        # 3. Label text position
        text_x = (p_elbow.x + 2.0) if dir_x > 0.0 else (p_end.x + 2.0)
        text_y = p_elbow.y + 1.5
        label_text_pos = Point2D(text_x, text_y)
        total_entities += 1

        # 4. Optional Scale Text
        scale_text_pos: Optional[Point2D] = None
        if args.scale and args.scale.strip():
            scale_y = p_elbow.y - (height * 1.3)
            scale_text_pos = Point2D(text_x, scale_y)
            total_entities += 1

        msg = f"Detail view '{label}' placed (Radius: {radius:.1f})."
        return DetailViewResult(
            status="OK",
            message=msg,
            label=label,
            radius=radius,
            boundary_circle=boundary_circle,
            leader_line=leader_line,
            shoulder_line=shoulder_line,
            label_text_pos=label_text_pos,
            scale_text_pos=scale_text_pos,
            processed_count=total_entities,
            layer=layer,
        )


# ============================================================================
# 5. SCHEDULE TABLE (cadmind-schedule-table / TierA Wave 6)
# ============================================================================


@dataclass(frozen=True)
class ScheduleTableArgs:
    """Input arguments for multi-column structural schedule tables."""

    origin: Optional[Sequence[float]] = None
    title: Optional[str] = None
    headers: Optional[Sequence[str]] = None
    rows: Optional[Sequence[Sequence[Any]]] = None
    sum_column: Optional[int] = None
    height: float = 3.0
    layer: str = "S-TABLE"


@dataclass(frozen=True)
class ScheduleTableCellIR:
    """Intermediate representation of an individual table cell."""

    row: int
    col: int
    text: str
    position: Point2D
    width: float
    height: float


@dataclass(frozen=True)
class ScheduleTableResult:
    """Result of schedule table generation."""

    status: str
    message: str
    column_count: int
    row_count: int
    sum_total: Optional[float]
    total_width: float
    total_height: float
    cells: List[ScheduleTableCellIR] = field(default_factory=list)
    grid_lines: List[LineSegment2D] = field(default_factory=list)
    processed_count: int = 0
    layer: str = "S-TABLE"


class ScheduleTableHandler:
    """Generates dynamic multi-column schedule tables with automated column sizing and summation rows."""

    def execute(self, args: ScheduleTableArgs) -> ScheduleTableResult:
        """Execute schedule table layout matching C# dynamic cell width and summation algorithms."""
        if args.headers is None or len(args.headers) == 0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Schedule table requires at least one header column.")

        if args.rows is None or len(args.rows) == 0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Schedule table requires at least one data row.")

        height = _validate_positive(args.height, "Height")

        ox, oy = 0.0, 0.0
        if args.origin is not None and len(args.origin) >= 2:
            ox = _validate_finite(args.origin[0], "Origin[0]")
            oy = _validate_finite(args.origin[1], "Origin[1]")

        layer = args.layer.strip() if args.layer and args.layer.strip() else "S-TABLE"
        col_count = len(args.headers)
        row_count = len(args.rows)
        t_height = height
        r_height = max(7.0, t_height * 2.5)

        # Dynamic column width computation based on string lengths
        col_widths: List[float] = []
        for c in range(col_count):
            max_len = len(str(args.headers[c])) if args.headers[c] is not None else 0
            for row in args.rows:
                if row is not None and c < len(row) and row[c] is not None:
                    s_len = len(str(row[c]))
                    if s_len > max_len:
                        max_len = s_len
            col_widths.append(max(24.0, (max_len * t_height * 0.9) + 6.0))

        total_width = sum(col_widths)
        total_entities = 0
        cur_y = oy
        cells: List[ScheduleTableCellIR] = []
        grid_lines: List[LineSegment2D] = []

        # 1. Top border
        grid_lines.append(LineSegment2D(Point2D(ox, cur_y), Point2D(ox + total_width, cur_y)))
        total_entities += 1

        # Optional Title Band
        if args.title and args.title.strip():
            title_text = args.title.strip()
            title_y = cur_y - r_height + ((r_height - (t_height * 1.2)) / 2.0)
            cells.append(
                ScheduleTableCellIR(
                    row=-1,
                    col=0,
                    text=title_text,
                    position=Point2D(ox + 4.0, title_y),
                    width=total_width,
                    height=r_height,
                )
            )
            total_entities += 1

            cur_y -= r_height
            grid_lines.append(LineSegment2D(Point2D(ox, cur_y), Point2D(ox + total_width, cur_y)))
            total_entities += 1

        # 2. Header Row
        col_x = ox
        for c in range(col_count):
            h_str = str(args.headers[c]) if args.headers[c] is not None else ""
            h_y = cur_y - r_height + ((r_height - t_height) / 2.0)
            cells.append(
                ScheduleTableCellIR(
                    row=0,
                    col=c,
                    text=h_str,
                    position=Point2D(col_x + 3.0, h_y),
                    width=col_widths[c],
                    height=r_height,
                )
            )
            total_entities += 1
            col_x += col_widths[c]

        cur_y -= r_height
        grid_lines.append(LineSegment2D(Point2D(ox, cur_y), Point2D(ox + total_width, cur_y)))
        total_entities += 1

        # 3. Data Rows
        sum_total: Optional[float] = None
        has_sum = (
            args.sum_column is not None
            and 0 <= args.sum_column < col_count
        )
        if has_sum:
            sum_total = 0.0

        for r in range(row_count):
            row_data = args.rows[r]
            col_x = ox
            for c in range(col_count):
                cell_val = row_data[c] if (row_data is not None and c < len(row_data)) else ""
                val_str = str(cell_val) if cell_val is not None else ""

                if has_sum and c == args.sum_column:
                    try:
                        num = float(cell_val)
                        if not math.isnan(num) and not math.isinf(num):
                            sum_total = (sum_total or 0.0) + num
                    except (ValueError, TypeError):
                        pass

                c_y = cur_y - r_height + ((r_height - t_height) / 2.0)
                cells.append(
                    ScheduleTableCellIR(
                        row=r + 1,
                        col=c,
                        text=val_str,
                        position=Point2D(col_x + 3.0, c_y),
                        width=col_widths[c],
                        height=r_height,
                    )
                )
                total_entities += 1
                col_x += col_widths[c]

            cur_y -= r_height
            grid_lines.append(LineSegment2D(Point2D(ox, cur_y), Point2D(ox + total_width, cur_y)))
            total_entities += 1

        # 4. Optional Summation Row
        if has_sum and sum_total is not None:
            sum_str = f"TOTAL: {sum_total:.2f}"
            tot_y = cur_y - r_height + ((r_height - t_height) / 2.0)
            cells.append(
                ScheduleTableCellIR(
                    row=row_count + 1,
                    col=args.sum_column if args.sum_column is not None else 0,
                    text=sum_str,
                    position=Point2D(ox + 4.0, tot_y),
                    width=total_width,
                    height=r_height,
                )
            )
            total_entities += 1

            cur_y -= r_height
            grid_lines.append(LineSegment2D(Point2D(ox, cur_y), Point2D(ox + total_width, cur_y)))
            total_entities += 1

        # 5. Vertical Grid Lines
        v_x = ox
        v_lines_x = [ox]
        for w in col_widths:
            v_x += w
            v_lines_x.append(v_x)

        for vx in v_lines_x:
            grid_lines.append(LineSegment2D(Point2D(vx, oy), Point2D(vx, cur_y)))
            total_entities += 1

        total_table_height = abs(oy - cur_y)
        msg = f"Schedule table drawn with {col_count} columns and {row_count} rows."

        return ScheduleTableResult(
            status="OK",
            message=msg,
            column_count=col_count,
            row_count=row_count,
            sum_total=sum_total,
            total_width=total_width,
            total_height=total_table_height,
            cells=cells,
            grid_lines=grid_lines,
            processed_count=total_entities,
            layer=layer,
        )
