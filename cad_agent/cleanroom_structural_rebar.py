"""cad_agent/cleanroom_structural_rebar.py.

Batch M4: Structural Rebar & Civil Concrete Drafting + Quantity Takeoff.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierBWave12Handlers.cs (RebarBeam, RebarHook, RebarMesh, FoundationFooting)
  - TierBWave15Handlers.cs (SteelWeight)
Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D, Arc2D, CircleIR),
strict IEEE-754 validation, zero external pip dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

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


class ContainmentError(DegenerateGeometryError):
    """Raised when an internal geometry exceeds outer structural boundary."""

    pass


class InvalidRebarParameterError(CleanroomError):
    """Raised when schedule rows or bar sizing parameters are invalid."""

    pass


# ============================================================================
# INTERNAL IEEE-754 VALIDATION HELPERS
# ============================================================================


def _check_finite(val: float, name: str) -> float:
    if math.isnan(val) or math.isinf(val):
        raise DegenerateGeometryError(
            f"DEGENERATE_GEOMETRY: Numeric arguments must be finite numbers ({name}={val})."
        )
    return float(val)


# ============================================================================
# 1. REBAR BEAM HANDLER (cadmind-rebar-beam)
# ============================================================================


@dataclass
class RebarBeamResult:
    status: str
    message: str
    layer: str
    entity_count: int
    width: float
    depth: float
    mark: str
    stirrup_lines: List[LineSegment2D]
    top_bar_line: LineSegment2D
    bottom_bar_line: LineSegment2D
    corner_bars: List[CircleIR]
    label_position: Point2D
    text_height: float


class RebarBeamHandler:
    """Generates structural concrete beam cross-section reinforcement."""

    @staticmethod
    def execute(
        origin_x: float = 0.0,
        origin_y: float = 0.0,
        width: float = 300.0,
        depth: float = 500.0,
        cover: float = 35.0,
        rebar_dia: float = 20.0,
        stirrup_dia: float = 8.0,
        bar_count_top: int = 2,
        bar_count_bot: int = 2,
        mark: str = "B1-4T20",
        text_height: float = 15.0,
        layer: str = "S-CONC-REBR",
    ) -> RebarBeamResult:
        _check_finite(origin_x, "OriginX")
        _check_finite(origin_y, "OriginY")
        _check_finite(width, "Width")
        _check_finite(depth, "Depth")
        _check_finite(cover, "Cover")
        _check_finite(rebar_dia, "RebarDia")
        _check_finite(stirrup_dia, "StirrupDia")
        _check_finite(text_height, "TextHeight")

        if width < 100.0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Beam width must be at least 100 mm."
            )
        if depth < 150.0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Beam depth must be at least 150 mm."
            )

        min_dim = min(width, depth)
        if cover < 15.0 or cover >= min_dim / 3.0:
            raise DegenerateGeometryError(
                f"DEGENERATE_GEOMETRY: Concrete cover must be between 15 mm and 1/3 minimum dimension ({min_dim / 3.0:.1f} mm)."
            )

        if rebar_dia < 6.0 or rebar_dia > 50.0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Rebar diameter must be between 6 and 50 mm."
            )

        if stirrup_dia < 6.0 or stirrup_dia > 16.0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Stirrup diameter must be between 6 and 16 mm."
            )

        if bar_count_top < 2 or bar_count_bot < 2:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Bar count top and bottom must be at least 2."
            )

        if not mark or not mark.strip():
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Beam mark cannot be empty or whitespace."
            )

        stirrup_w = width - 2.0 * cover
        stirrup_d = depth - 2.0 * cover
        if stirrup_w <= 2.0 * stirrup_dia or stirrup_d <= 2.0 * stirrup_dia:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Concrete cover and stirrup diameter exceed beam dimensions."
            )

        # 1. Stirrup (closed perimeter - 4 line segments)
        s_bl = Point2D(origin_x + cover, origin_y + cover)
        s_br = Point2D(origin_x + width - cover, origin_y + cover)
        s_tr = Point2D(origin_x + width - cover, origin_y + depth - cover)
        s_tl = Point2D(origin_x + cover, origin_y + depth - cover)
        stirrup_lines = [
            LineSegment2D(start=s_bl, end=s_br),
            LineSegment2D(start=s_br, end=s_tr),
            LineSegment2D(start=s_tr, end=s_tl),
            LineSegment2D(start=s_tl, end=s_bl),
        ]

        # 2. Top longitudinal bar (Line)
        top_y = origin_y + depth - cover - stirrup_dia / 2.0
        top_bar = LineSegment2D(
            start=Point2D(origin_x + cover, top_y),
            end=Point2D(origin_x + width - cover, top_y),
        )

        # 3. Bottom longitudinal bar (Line)
        bot_y = origin_y + cover + stirrup_dia / 2.0
        bot_bar = LineSegment2D(
            start=Point2D(origin_x + cover, bot_y),
            end=Point2D(origin_x + width - cover, bot_y),
        )

        # 4. 4 Corner Section Reinforcements (Circle x 4)
        bar_rad = rebar_dia / 2.0
        inset_x = cover + stirrup_dia + bar_rad
        inset_y = cover + stirrup_dia + bar_rad
        corner_bars = [
            CircleIR(center=Point2D(origin_x + inset_x, origin_y + inset_y), radius=bar_rad),
            CircleIR(
                center=Point2D(origin_x + width - inset_x, origin_y + inset_y),
                radius=bar_rad,
            ),
            CircleIR(
                center=Point2D(origin_x + width - inset_x, origin_y + depth - inset_y),
                radius=bar_rad,
            ),
            CircleIR(
                center=Point2D(origin_x + inset_x, origin_y + depth - inset_y),
                radius=bar_rad,
            ),
        ]

        # 5. Label position: (origin_x + width / 2.0, origin_y + depth + 25.0)
        label_pos = Point2D(origin_x + width / 2.0, origin_y + depth + 25.0)
        effective_text_height = text_height if text_height > 0.0 else 15.0

        return RebarBeamResult(
            status="OK",
            message="Rebar beam section successfully created.",
            layer=layer,
            entity_count=8,  # stirrup (1) + top_bar (1) + bot_bar (1) + corners (4) + text (1)
            width=width,
            depth=depth,
            mark=mark.strip(),
            stirrup_lines=stirrup_lines,
            top_bar_line=top_bar,
            bottom_bar_line=bot_bar,
            corner_bars=corner_bars,
            label_position=label_pos,
            text_height=effective_text_height,
        )


# ============================================================================
# 2. REBAR HOOK HANDLER (cadmind-rebar-hook)
# ============================================================================


@dataclass
class RebarHookResult:
    status: str
    message: str
    layer: str
    entity_count: int
    bend_angle_deg: float
    bend_radius: float
    tag: str
    leg_line: LineSegment2D
    tail_line: LineSegment2D
    hook_arc: Arc2D
    mandrel_circle: CircleIR
    bulge: float
    tag_position: Point2D
    text_height: float


class RebarHookHandler:
    """Generates standard rebar hook with mandrel bend and orientation."""

    @staticmethod
    def execute(
        start_x: float = 0.0,
        start_y: float = 0.0,
        leg_length: float = 100.0,
        bend_angle_deg: float = 90.0,
        bend_radius: float = 30.0,
        tail_length: float = 50.0,
        direction_x: float = 1.0,
        direction_y: float = 0.0,
        bend_left: bool = True,
        tag: str = "H-T20",
        text_height: float = 12.0,
        layer: str = "S-CONC-REBR",
    ) -> RebarHookResult:
        _check_finite(start_x, "StartX")
        _check_finite(start_y, "StartY")
        _check_finite(leg_length, "LegLength")
        _check_finite(bend_angle_deg, "BendAngleDeg")
        _check_finite(bend_radius, "BendRadius")
        _check_finite(tail_length, "TailLength")
        _check_finite(direction_x, "DirectionX")
        _check_finite(direction_y, "DirectionY")
        _check_finite(text_height, "TextHeight")

        if leg_length < 50.0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Leg length must be at least 50 mm.")
        if tail_length < 30.0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Tail length must be at least 30 mm."
            )
        if bend_radius < 12.0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Bend radius must be at least 12 mm."
            )

        dir_len = math.hypot(direction_x, direction_y)
        if dir_len < 1e-6:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Direction vector cannot be degenerate."
            )

        if not any(
            math.isclose(bend_angle_deg, valid, abs_tol=1e-4) for valid in (90.0, 135.0, 180.0)
        ):
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Supported hook bend angles are exactly 90, 135, or 180 degrees."
            )

        if not tag or not tag.strip():
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Hook tag cannot be empty or whitespace."
            )

        ux = direction_x / dir_len
        uy = direction_y / dir_len
        nx = -uy if bend_left else uy
        ny = ux if bend_left else -ux
        theta = math.radians(bend_angle_deg)

        p0 = Point2D(start_x, start_y)
        t1 = Point2D(start_x + ux * leg_length, start_y + uy * leg_length)
        center = Point2D(t1.x + nx * bend_radius, t1.y + ny * bend_radius)

        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        t2_x = center.x - nx * (bend_radius * cos_t) + ux * (bend_radius * sin_t)
        t2_y = center.y - ny * (bend_radius * cos_t) + uy * (bend_radius * sin_t)
        t2 = Point2D(t2_x, t2_y)

        exit_ux = ux * cos_t + nx * sin_t
        exit_uy = uy * cos_t + ny * sin_t
        p3 = Point2D(t2.x + exit_ux * tail_length, t2.y + exit_uy * tail_length)

        bulge = math.tan(theta / 4.0) * (1.0 if bend_left else -1.0)

        # Hook Profile primitives: leg segment, tangent arc, tail segment
        leg_line = LineSegment2D(start=p0, end=t1)
        tail_line = LineSegment2D(start=t2, end=p3)

        # Arc from t1 to t2 centered at mandrel center
        ang1_rad = math.atan2(t1.y - center.y, t1.x - center.x) % (2.0 * math.pi)
        ang2_rad = math.atan2(t2.y - center.y, t2.x - center.x) % (2.0 * math.pi)
        hook_arc = Arc2D(
            center=center,
            radius=bend_radius,
            start_angle_rad=ang1_rad,
            end_angle_rad=ang2_rad,
        )

        mandrel_circle = CircleIR(center=center, radius=bend_radius)

        tag_pos = Point2D(
            start_x + ux * (leg_length / 2.0) + nx * 15.0,
            start_y + uy * (leg_length / 2.0) + ny * 15.0,
        )
        effective_text_height = text_height if text_height > 0.0 else 12.0

        return RebarHookResult(
            status="OK",
            message="Rebar hook profile successfully created.",
            layer=layer,
            entity_count=3,  # hook pline (1) + mandrel circle (1) + tag text (1)
            bend_angle_deg=bend_angle_deg,
            bend_radius=bend_radius,
            tag=tag.strip(),
            leg_line=leg_line,
            tail_line=tail_line,
            hook_arc=hook_arc,
            mandrel_circle=mandrel_circle,
            bulge=bulge,
            tag_position=tag_pos,
            text_height=effective_text_height,
        )


# ============================================================================
# 3. REBAR MESH HANDLER (cadmind-rebar-mesh)
# ============================================================================


@dataclass
class RebarMeshResult:
    status: str
    message: str
    layer: str
    entity_count: int
    length: float
    width: float
    mesh_code: str
    boundary_lines: List[LineSegment2D]
    longitudinal_lines: List[LineSegment2D]
    transverse_lines: List[LineSegment2D]
    centroid: Point2D
    text_height: float


class RebarMeshHandler:
    """Generates welded wire mesh reinforcing fabric layout."""

    @staticmethod
    def execute(
        origin_x: float = 0.0,
        origin_y: float = 0.0,
        length: float = 600.0,
        width: float = 400.0,
        spacing_x: float = 50.0,
        spacing_y: float = 50.0,
        mesh_code: str = "A252",
        text_height: float = 18.0,
        layer: str = "S-CONC-REBR",
    ) -> RebarMeshResult:
        _check_finite(origin_x, "OriginX")
        _check_finite(origin_y, "OriginY")
        _check_finite(length, "Length")
        _check_finite(width, "Width")
        _check_finite(spacing_x, "SpacingX")
        _check_finite(spacing_y, "SpacingY")
        _check_finite(text_height, "TextHeight")

        if length < 200.0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Mesh length must be at least 200 mm."
            )
        if width < 200.0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Mesh width must be at least 200 mm."
            )
        if spacing_x <= 0.0 or spacing_y <= 0.0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Wire spacing must be positive.")
        if not mesh_code or not mesh_code.strip():
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Mesh code cannot be empty or whitespace."
            )

        # 1. Boundary (closed rectangle - 4 segments)
        b0 = Point2D(origin_x, origin_y)
        b1 = Point2D(origin_x + length, origin_y)
        b2 = Point2D(origin_x + length, origin_y + width)
        b3 = Point2D(origin_x, origin_y + width)
        boundary_lines = [
            LineSegment2D(start=b0, end=b1),
            LineSegment2D(start=b1, end=b2),
            LineSegment2D(start=b2, end=b3),
            LineSegment2D(start=b3, end=b0),
        ]

        # 2. 3 Longitudinal reinforcement wires (Line x 3) at yFractions = 0.25, 0.50, 0.75
        longitudinal_lines: List[LineSegment2D] = []
        for yf in (0.25, 0.50, 0.75):
            wy = origin_y + yf * width
            longitudinal_lines.append(
                LineSegment2D(
                    start=Point2D(origin_x, wy),
                    end=Point2D(origin_x + length, wy),
                )
            )

        # 3. 3 Transverse reinforcement wires (Line x 3) at xFractions = 0.25, 0.50, 0.75
        transverse_lines: List[LineSegment2D] = []
        for xf in (0.25, 0.50, 0.75):
            wx = origin_x + xf * length
            transverse_lines.append(
                LineSegment2D(
                    start=Point2D(wx, origin_y),
                    end=Point2D(wx, origin_y + width),
                )
            )

        centroid = Point2D(origin_x + length / 2.0, origin_y + width / 2.0)
        effective_text_height = text_height if text_height > 0.0 else 18.0

        return RebarMeshResult(
            status="OK",
            message="Rebar mesh successfully created.",
            layer=layer,
            entity_count=8,  # boundary (1) + 3 long wires + 3 trans wires + 1 text = 8
            length=length,
            width=width,
            mesh_code=mesh_code.strip(),
            boundary_lines=boundary_lines,
            longitudinal_lines=longitudinal_lines,
            transverse_lines=transverse_lines,
            centroid=centroid,
            text_height=effective_text_height,
        )


# ============================================================================
# 4. FOUNDATION FOOTING HANDLER (cadmind-foundation)
# ============================================================================


@dataclass
class FoundationFootingResult:
    status: str
    message: str
    layer: str
    entity_count: int
    pad_length: float
    pad_width: float
    footing_id: str
    pad_lines: List[LineSegment2D]
    pedestal_lines: List[LineSegment2D]
    centerline_x: LineSegment2D
    centerline_y: LineSegment2D
    mark_position: Point2D
    text_height: float


class FoundationFootingHandler:
    """Generates structural foundation pad and column pedestal plan."""

    @staticmethod
    def execute(
        center_x: float = 0.0,
        center_y: float = 0.0,
        pad_length: float = 1200.0,
        pad_width: float = 1200.0,
        col_length: float = 400.0,
        col_width: float = 400.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        footing_id: str = "F1",
        text_height: float = 20.0,
        layer: str = "S-STRC-FNDN",
    ) -> FoundationFootingResult:
        _check_finite(center_x, "CenterX")
        _check_finite(center_y, "CenterY")
        _check_finite(pad_length, "PadLength")
        _check_finite(pad_width, "PadWidth")
        _check_finite(col_length, "ColLength")
        _check_finite(col_width, "ColWidth")
        _check_finite(offset_x, "OffsetX")
        _check_finite(offset_y, "OffsetY")
        _check_finite(text_height, "TextHeight")

        if pad_length < 300.0 or pad_width < 300.0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Footing pad length and width must be at least 300 mm."
            )
        if col_length < 100.0 or col_width < 100.0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Column pedestal length and width must be at least 100 mm."
            )

        # Strict containment check from C# source:
        # Math.Abs(args.OffsetX) + args.ColLength / 2.0 >= args.PadLength / 2.0 ||
        # Math.Abs(args.OffsetY) + args.ColWidth / 2.0 >= args.PadWidth / 2.0
        if (
            abs(offset_x) + col_length / 2.0 >= pad_length / 2.0
            or abs(offset_y) + col_width / 2.0 >= pad_width / 2.0
        ):
            raise ContainmentError(
                "DEGENERATE_GEOMETRY: Column pedestal must be strictly contained within footing pad boundary."
            )

        if not footing_id or not footing_id.strip():
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Footing identifier cannot be empty or whitespace."
            )

        half_pad_l = pad_length / 2.0
        half_pad_w = pad_width / 2.0

        # 1. Outer Concrete Pad (closed rectangle)
        p0 = Point2D(center_x - half_pad_l, center_y - half_pad_w)
        p1 = Point2D(center_x + half_pad_l, center_y - half_pad_w)
        p2 = Point2D(center_x + half_pad_l, center_y + half_pad_w)
        p3 = Point2D(center_x - half_pad_l, center_y + half_pad_w)
        pad_lines = [
            LineSegment2D(start=p0, end=p1),
            LineSegment2D(start=p1, end=p2),
            LineSegment2D(start=p2, end=p3),
            LineSegment2D(start=p3, end=p0),
        ]

        # 2. Inner Column Pedestal (closed rectangle)
        ped_cx = center_x + offset_x
        ped_cy = center_y + offset_y
        half_col_l = col_length / 2.0
        half_col_w = col_width / 2.0

        c0 = Point2D(ped_cx - half_col_l, ped_cy - half_col_w)
        c1 = Point2D(ped_cx + half_col_l, ped_cy - half_col_w)
        c2 = Point2D(ped_cx + half_col_l, ped_cy + half_col_w)
        c3 = Point2D(ped_cx - half_col_l, ped_cy + half_col_w)
        pedestal_lines = [
            LineSegment2D(start=c0, end=c1),
            LineSegment2D(start=c1, end=c2),
            LineSegment2D(start=c2, end=c3),
            LineSegment2D(start=c3, end=c0),
        ]

        # 3. Centerline X (extends 10% beyond pad length)
        cl_x = LineSegment2D(
            start=Point2D(center_x - half_pad_l * 1.1, center_y),
            end=Point2D(center_x + half_pad_l * 1.1, center_y),
        )

        # 4. Centerline Y (extends 10% beyond pad width)
        cl_y = LineSegment2D(
            start=Point2D(center_x, center_y - half_pad_w * 1.1),
            end=Point2D(center_x, center_y + half_pad_w * 1.1),
        )

        # 5. Schedule Mark Text Position
        mark_pos = Point2D(center_x - half_pad_l + 30.0, center_y + half_pad_w - 40.0)
        effective_text_height = text_height if text_height > 0.0 else 20.0

        return FoundationFootingResult(
            status="OK",
            message="Foundation footing plan successfully created.",
            layer=layer,
            entity_count=5,  # pad (1) + ped (1) + cl_x (1) + cl_y (1) + mark (1)
            pad_length=pad_length,
            pad_width=pad_width,
            footing_id=footing_id.strip(),
            pad_lines=pad_lines,
            pedestal_lines=pedestal_lines,
            centerline_x=cl_x,
            centerline_y=cl_y,
            mark_position=mark_pos,
            text_height=effective_text_height,
        )


# ============================================================================
# 5. STEEL WEIGHT HANDLER (cadmind-steel-weight)
# ============================================================================


@dataclass
class SteelWeightRowResult:
    mark: str
    dia_mm: float
    length_mm: float
    count: int
    total_length_m: float
    unit_weight_kg_per_m: float
    total_weight_kg: float


@dataclass
class SteelWeightResult:
    status: str
    message: str
    row_count: int
    total_length_m: float
    total_weight_kg: float
    rows: List[SteelWeightRowResult]


class SteelWeightHandler:
    """Calculates rebar schedule quantity takeoff with unit weight d^2 / 162."""

    @staticmethod
    def execute(
        rows: Sequence[Tuple[str, float, float, int]],
        decimals: int = 2,
    ) -> SteelWeightResult:
        if rows is None or len(rows) == 0:
            raise InvalidRebarParameterError("EMPTY_INPUT: Rows cannot be empty.")

        if decimals < 0 or decimals > 8:
            raise InvalidRebarParameterError("INVALID_DECIMALS: Decimals must be between 0 and 8.")

        row_results: List[SteelWeightRowResult] = []
        grand_length_m = 0.0
        grand_weight_kg = 0.0

        for row in rows:
            mark, dia, length_mm, count = row
            _check_finite(dia, "Dia")
            _check_finite(length_mm, "Length")

            if dia <= 0.0:
                raise InvalidRebarParameterError(
                    "INVALID_DIA: Bar diameter must be positive and finite."
                )
            if length_mm <= 0.0:
                raise InvalidRebarParameterError(
                    "INVALID_LENGTH: Bar cut length must be positive and finite."
                )
            if count <= 0:
                raise InvalidRebarParameterError(
                    "INVALID_COUNT: Bar count must be greater than zero."
                )

            # Standard civil engineering rebar formula:
            # unit_weight = dia^2 / 162.0 kg/m
            # total_length = (length_mm * count) / 1000.0 m
            # total_weight = total_length * unit_weight kg
            row_total_len_m = (length_mm * count) / 1000.0
            unit_wt = (dia * dia) / 162.0
            row_total_wt_kg = row_total_len_m * unit_wt

            grand_length_m += row_total_len_m
            grand_weight_kg += row_total_wt_kg

            row_results.append(
                SteelWeightRowResult(
                    mark=str(mark) if mark is not None else "",
                    dia_mm=round(dia, decimals),
                    length_mm=round(length_mm, decimals),
                    count=count,
                    total_length_m=round(row_total_len_m, decimals),
                    unit_weight_kg_per_m=round(unit_wt, 4),
                    total_weight_kg=round(row_total_wt_kg, decimals),
                )
            )

        grand_length_m = round(grand_length_m, decimals)
        grand_weight_kg = round(grand_weight_kg, decimals)

        return SteelWeightResult(
            status="SUCCESS",
            message=f"Calculated rebar weight for {len(row_results)} rows: Total Length = {grand_length_m} m, Total Weight = {grand_weight_kg} kg.",
            row_count=len(row_results),
            total_length_m=grand_length_m,
            total_weight_kg=grand_weight_kg,
            rows=row_results,
        )
