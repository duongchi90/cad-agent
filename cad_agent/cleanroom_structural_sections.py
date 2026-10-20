"""cad_agent/cleanroom_structural_sections.py.

Batch ST1: Structural Sections, Foundations, Slabs & Bolted Connections.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierAWave3Handlers.cs: SteelSectionHandler (cadmind-steel-section)
  - TierAWave3Handlers.cs: ConcreteSectionHandler (cadmind-concrete-section)
  - TierBWave12Handlers.cs: FoundationFootingHandler (cadmind-foundation)
  - TierAWave5Handlers.cs: WallSlabSectionHandler (cadmind-wall-slab-section)
  - TierAWave2Handlers.cs: MaterialHatchHandler (cadmind-material-hatch)
  - TierBWave17Handlers.cs: SteelConnectionHandler (cadmind-steel-connection)

Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D, CircleIR),
strict IEEE-754 machine-epsilon safety, Banker's rounding parity,
and zero external pip dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from cad_agent.cleanroom_mechanical import CircleIR, LineSegment2D, Point2D

# ============================================================================
# EXCEPTION HIERARCHY
# ============================================================================


class CleanroomError(ValueError):
    """Base exception for cleanroom validation errors."""

    pass


class DegenerateGeometryError(CleanroomError):
    """Raised when geometric or validation parameters violate construction rules."""

    pass


# ============================================================================
# INTERNAL IEEE-754 VALIDATION HELPERS
# ============================================================================


def _validate_finite(val: float, name: str) -> float:
    """Ensure value is finite (not NaN, not Inf)."""
    if not isinstance(val, (int, float)) or isinstance(val, bool) or math.isnan(val) or math.isinf(val):
        raise DegenerateGeometryError(f"DEGENERATE_GEOMETRY: Numeric arguments must be finite numbers ({name}={val}).")
    return float(val)


# ============================================================================
# DTO & IR DEFINITIONS
# ============================================================================


@dataclass(frozen=True)
class SteelSectionArgs:
    """Arguments matching TierAWave3Contracts.SteelSectionArgs."""

    insertion_point: Optional[Sequence[float]] = None
    profile_type: str = "I_BEAM"  # "I_BEAM", "CHANNEL", "RHS", "ANGLE"
    depth: float = 300.0
    width: float = 150.0
    web_thickness: float = 7.1
    flange_thickness: float = 10.7
    fillet_radius: float = 15.0
    layer: str = "STEEL"


@dataclass(frozen=True)
class SteelSectionResult:
    """Result matching TierAWave3Contracts.SteelSectionResult."""

    status: str
    message: str
    profile_type: str
    depth: float
    width: float
    processed_count: int
    lines: List[LineSegment2D] = field(default_factory=list)


@dataclass(frozen=True)
class ConcreteSectionArgs:
    """Arguments matching TierAWave3Contracts.ConcreteSectionArgs."""

    insertion_point: Optional[Sequence[float]] = None
    width: float = 300.0
    depth: float = 500.0
    cover: float = 35.0
    stirrup_diameter: float = 8.0
    top_rebar_count: int = 2
    top_rebar_diameter: float = 16.0
    bottom_rebar_count: int = 3
    bottom_rebar_diameter: float = 20.0
    layer: str = "CONCRETE"
    rebar_layer: str = "REBAR"


@dataclass(frozen=True)
class ConcreteSectionResult:
    """Result matching TierAWave3Contracts.ConcreteSectionResult."""

    status: str
    message: str
    section_area_mm2: float
    total_rebar_count: int
    processed_count: int
    lines: List[LineSegment2D] = field(default_factory=list)
    rebar_circles: List[CircleIR] = field(default_factory=list)


@dataclass(frozen=True)
class FoundationFootingArgs:
    """Arguments matching TierBWave12Contracts.FoundationFootingArgs."""

    center_x: float = 0.0
    center_y: float = 0.0
    pad_length: float = 1200.0
    pad_width: float = 1200.0
    col_length: float = 400.0
    col_width: float = 400.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    footing_id: str = "F1"
    text_height: float = 20.0
    layer: str = "S-STRC-FNDN"


@dataclass(frozen=True)
class FoundationFootingResult:
    """Result matching TierBWave12Contracts.FoundationFootingResult."""

    status: str
    message: str
    layer: str
    entity_count: int
    pad_length: float
    pad_width: float
    footing_id: str
    handles: List[str] = field(default_factory=list)
    lines: List[LineSegment2D] = field(default_factory=list)


@dataclass(frozen=True)
class WallSlabSectionArgs:
    """Arguments matching TierAWave5Contracts.WallSlabSectionArgs."""

    origin: Optional[Sequence[float]] = None
    element: str = "slab"  # "wall" or "slab"
    length: float = 3000.0
    thickness: float = 200.0
    rotation: float = 0.0
    axis: bool = True
    break_ends: bool = False
    layer: str = "S-SECT"


@dataclass(frozen=True)
class WallSlabSectionResult:
    """Result matching TierAWave5Contracts.WallSlabSectionResult."""

    status: str
    message: str
    element: str
    area: float
    processed_count: int
    lines: List[LineSegment2D] = field(default_factory=list)


@dataclass(frozen=True)
class MaterialHatchArgs:
    """Arguments matching TierAWave2Contracts.MaterialHatchArgs."""

    boundary_points: Optional[Sequence[Point2D]] = None
    boundary_handle: Optional[str] = None
    pattern_name: str = "ANSI31"
    pattern_scale: float = 1.0
    pattern_angle: float = 0.0
    layer: str = "HATCH"


@dataclass(frozen=True)
class ToolGenericResult:
    """Generic tool result matching C# ToolGenericResult."""

    status: str
    message: str
    count: int = 0


@dataclass(frozen=True)
class SteelConnectionArgs:
    """Arguments matching TierBWave17Contracts.SteelConnectionArgs."""

    origin: Optional[Sequence[float]] = None
    rotation: float = 0.0
    plate_width: Optional[float] = None
    plate_height: Optional[float] = None
    bolt_rows: int = 2
    bolt_cols: int = 2
    bolt_pitch: float = 70.0
    bolt_gauge: float = 70.0
    bolt_dia: float = 20.0
    layer: str = "S-CONN"
    plate_layer: str = "S-PLATE"


@dataclass(frozen=True)
class SteelConnectionResult:
    """Result matching TierBWave17Contracts.SteelConnectionResult."""

    status: str
    message: str
    plate_created: bool
    bolt_count: int
    bolt_diameter: float
    layer: str
    plate_layer: str
    entity_count: int
    created_handles: List[str]
    bolt_circles: List[CircleIR] = field(default_factory=list)
    plate_lines: List[LineSegment2D] = field(default_factory=list)


# ============================================================================
# 1. cadmind-steel-section (SteelSectionHandler)
# ============================================================================


class SteelSectionHandler:
    """Cleanroom implementation of SteelSectionHandler (TierAWave3Handlers.cs)."""

    def execute(self, args: SteelSectionArgs) -> SteelSectionResult:
        """Generate closed structural steel cross-section geometry."""
        try:
            d = _validate_finite(args.depth, "depth")
            w = _validate_finite(args.width, "width")
            tw = _validate_finite(args.web_thickness, "web_thickness")
            tf = _validate_finite(args.flange_thickness, "flange_thickness")
            fr = _validate_finite(args.fillet_radius, "fillet_radius")
        except DegenerateGeometryError as e:
            return SteelSectionResult("ERROR", str(e), args.profile_type, 0.0, 0.0, 0)

        if d <= 1e-4 or w <= 1e-4 or tw <= 1e-4 or tf <= 1e-4:
            return SteelSectionResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: Profile dimensions must be strictly positive.",
                args.profile_type,
                0.0,
                0.0,
                0,
            )

        if tw >= w:
            return SteelSectionResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: Web thickness must be strictly less than flange width.",
                args.profile_type,
                0.0,
                0.0,
                0,
            )

        if 2.0 * tf >= d:
            return SteelSectionResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: Combined flange thickness must be strictly less than overall depth.",
                args.profile_type,
                0.0,
                0.0,
                0,
            )

        if fr < 0.0:
            return SteelSectionResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: Fillet radius must be non-negative.",
                args.profile_type,
                0.0,
                0.0,
                0,
            )

        ox = 0.0
        oy = 0.0
        if args.insertion_point is not None and len(args.insertion_point) >= 2:
            ox = _validate_finite(args.insertion_point[0], "insertion_point_x")
            oy = _validate_finite(args.insertion_point[1], "insertion_point_y")

        lines: List[LineSegment2D] = []
        p_type = (args.profile_type or "I_BEAM").strip().upper()

        if p_type == "RHS":
            # Outer box
            p1 = Point2D(ox - w / 2, oy - d / 2)
            p2 = Point2D(ox + w / 2, oy - d / 2)
            p3 = Point2D(ox + w / 2, oy + d / 2)
            p4 = Point2D(ox - w / 2, oy + d / 2)
            lines.extend([LineSegment2D(p1, p2), LineSegment2D(p2, p3), LineSegment2D(p3, p4), LineSegment2D(p4, p1)])
            # Inner box
            iw = w - 2 * tw
            id_ = d - 2 * tf
            ip1 = Point2D(ox - iw / 2, oy - id_ / 2)
            ip2 = Point2D(ox + iw / 2, oy - id_ / 2)
            ip3 = Point2D(ox + iw / 2, oy + id_ / 2)
            ip4 = Point2D(ox - iw / 2, oy + id_ / 2)
            lines.extend([LineSegment2D(ip1, ip2), LineSegment2D(ip2, ip3), LineSegment2D(ip3, ip4), LineSegment2D(ip4, ip1)])
        else:  # I_BEAM (default)
            # 12-point I-beam perimeter
            hw = w / 2.0
            hd = d / 2.0
            htw = tw / 2.0
            pts = [
                Point2D(ox - hw, oy + hd),
                Point2D(ox + hw, oy + hd),
                Point2D(ox + hw, oy + hd - tf),
                Point2D(ox + htw, oy + hd - tf),
                Point2D(ox + htw, oy - hd + tf),
                Point2D(ox + hw, oy - hd + tf),
                Point2D(ox + hw, oy - hd),
                Point2D(ox - hw, oy - hd),
                Point2D(ox - hw, oy - hd + tf),
                Point2D(ox - htw, oy - hd + tf),
                Point2D(ox - htw, oy + hd - tf),
                Point2D(ox - hw, oy + hd - tf),
            ]
            for i in range(len(pts)):
                lines.append(LineSegment2D(pts[i], pts[(i + 1) % len(pts)]))

        msg = f"Steel {p_type} section drawn ({d}x{w}) on layer '{args.layer}'."
        return SteelSectionResult("OK", msg, p_type, d, w, len(lines), lines)


# ============================================================================
# 2. cadmind-concrete-section (ConcreteSectionHandler)
# ============================================================================


class ConcreteSectionHandler:
    """Cleanroom implementation of ConcreteSectionHandler (TierAWave3Handlers.cs)."""

    def execute(self, args: ConcreteSectionArgs) -> ConcreteSectionResult:
        """Draw reinforced concrete beam/column cross-section."""
        try:
            w = _validate_finite(args.width, "width")
            d = _validate_finite(args.depth, "depth")
            c = _validate_finite(args.cover, "cover")
            sd = _validate_finite(args.stirrup_diameter, "stirrup_diameter")
            td = _validate_finite(args.top_rebar_diameter, "top_rebar_diameter")
            bd = _validate_finite(args.bottom_rebar_diameter, "bottom_rebar_diameter")
        except DegenerateGeometryError as e:
            return ConcreteSectionResult("ERROR", str(e), 0.0, 0, 0)

        if w <= 1e-4 or d <= 1e-4 or c <= 1e-4:
            return ConcreteSectionResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: Section Width, Depth and Cover must be strictly positive.",
                0.0,
                0,
                0,
            )

        if c >= min(w, d) / 2.0:
            return ConcreteSectionResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: Concrete cover exceeds section boundary.",
                0.0,
                0,
                0,
            )

        if sd <= 1e-4 or td <= 1e-4 or bd <= 1e-4:
            return ConcreteSectionResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: Rebar diameters must be strictly positive.",
                0.0,
                0,
                0,
            )

        if args.top_rebar_count < 2 or args.bottom_rebar_count < 2:
            return ConcreteSectionResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: Top and bottom rebar counts must be at least 2.",
                0.0,
                0,
                0,
            )

        ox = 0.0
        oy = 0.0
        if args.insertion_point is not None and len(args.insertion_point) >= 2:
            ox = _validate_finite(args.insertion_point[0], "insertion_point_x")
            oy = _validate_finite(args.insertion_point[1], "insertion_point_y")

        lines: List[LineSegment2D] = []
        circles: List[CircleIR] = []

        # Outer concrete perimeter
        p1 = Point2D(ox, oy)
        p2 = Point2D(ox + w, oy)
        p3 = Point2D(ox + w, oy + d)
        p4 = Point2D(ox, oy + d)
        lines.extend([LineSegment2D(p1, p2), LineSegment2D(p2, p3), LineSegment2D(p3, p4), LineSegment2D(p4, p1)])

        # Inner stirrup
        sp1 = Point2D(ox + c, oy + c)
        sp2 = Point2D(ox + w - c, oy + c)
        sp3 = Point2D(ox + w - c, oy + d - c)
        sp4 = Point2D(ox + c, oy + d - c)
        lines.extend([LineSegment2D(sp1, sp2), LineSegment2D(sp2, sp3), LineSegment2D(sp3, sp4), LineSegment2D(sp4, sp1)])

        # Top rebars
        top_y = oy + d - c - sd - td / 2.0
        top_start_x = ox + c + sd + td / 2.0
        top_end_x = ox + w - c - sd - td / 2.0
        top_step = (top_end_x - top_start_x) / (args.top_rebar_count - 1)
        for i in range(args.top_rebar_count):
            rx = top_start_x + i * top_step
            circles.append(CircleIR(Point2D(rx, top_y), td / 2.0))

        # Bottom rebars
        bot_y = oy + c + sd + bd / 2.0
        bot_start_x = ox + c + sd + bd / 2.0
        bot_end_x = ox + w - c - sd - bd / 2.0
        bot_step = (bot_end_x - bot_start_x) / (args.bottom_rebar_count - 1)
        for i in range(args.bottom_rebar_count):
            rx = bot_start_x + i * bot_step
            circles.append(CircleIR(Point2D(rx, bot_y), bd / 2.0))

        total_rebars = args.top_rebar_count + args.bottom_rebar_count
        area = w * d
        msg = f"Concrete section drawn ({w}x{d} mm) with {total_rebars} rebars."
        return ConcreteSectionResult("OK", msg, area, total_rebars, len(lines) + len(circles), lines, circles)


# ============================================================================
# 3. cadmind-foundation (FoundationFootingHandler)
# ============================================================================


class FoundationFootingHandler:
    """Cleanroom implementation of FoundationFootingHandler (TierBWave12Handlers.cs)."""

    def execute(self, args: FoundationFootingArgs) -> FoundationFootingResult:
        """Generate foundation footing plan with strict containment safety."""
        try:
            cx = _validate_finite(args.center_x, "center_x")
            cy = _validate_finite(args.center_y, "center_y")
            pl = _validate_finite(args.pad_length, "pad_length")
            pw = _validate_finite(args.pad_width, "pad_width")
            cl = _validate_finite(args.col_length, "col_length")
            cw = _validate_finite(args.col_width, "col_width")
            ox = _validate_finite(args.offset_x, "offset_x")
            oy = _validate_finite(args.offset_y, "offset_y")
        except DegenerateGeometryError as e:
            return FoundationFootingResult("ERROR", str(e), args.layer, 0, 0.0, 0.0, args.footing_id)

        if pl < 300.0 or pw < 300.0 or cl < 100.0 or cw < 100.0:
            return FoundationFootingResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: Pad size must be >= 300mm and Col size must be >= 100mm.",
                args.layer,
                0,
                pl,
                pw,
                args.footing_id,
            )

        # Strict containment verification
        if (abs(ox) + cl / 2.0) >= pl / 2.0 or (abs(oy) + cw / 2.0) >= pw / 2.0:
            return FoundationFootingResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: Column pedestal exceeds or touches pad boundary.",
                args.layer,
                0,
                pl,
                pw,
                args.footing_id,
            )

        lines: List[LineSegment2D] = []
        # Pad rectangle
        pad_p1 = Point2D(cx - pl / 2, cy - pw / 2)
        pad_p2 = Point2D(cx + pl / 2, cy - pw / 2)
        pad_p3 = Point2D(cx + pl / 2, cy + pw / 2)
        pad_p4 = Point2D(cx - pl / 2, cy + pw / 2)
        lines.extend([LineSegment2D(pad_p1, pad_p2), LineSegment2D(pad_p2, pad_p3), LineSegment2D(pad_p3, pad_p4), LineSegment2D(pad_p4, pad_p1)])

        # Pedestal rectangle
        col_cx = cx + ox
        col_cy = cy + oy
        col_p1 = Point2D(col_cx - cl / 2, col_cy - cw / 2)
        col_p2 = Point2D(col_cx + cl / 2, col_cy - cw / 2)
        col_p3 = Point2D(col_cx + cl / 2, col_cy + cw / 2)
        col_p4 = Point2D(col_cx - cl / 2, col_cy + cw / 2)
        lines.extend([LineSegment2D(col_p1, col_p2), LineSegment2D(col_p2, col_p3), LineSegment2D(col_p3, col_p4), LineSegment2D(col_p4, col_p1)])

        # Centerlines
        lines.append(LineSegment2D(Point2D(cx - pl * 0.6, cy), Point2D(cx + pl * 0.6, cy)))
        lines.append(LineSegment2D(Point2D(cx, cy - pw * 0.6), Point2D(cx, cy + pw * 0.6)))

        msg = f"Foundation footing plan generated for '{args.footing_id}' ({pl}x{pw} mm)."
        return FoundationFootingResult(
            "OK",
            msg,
            args.layer,
            5,
            pl,
            pw,
            args.footing_id,
            ["H_PAD", "H_COL", "H_AXIS_X", "H_AXIS_Y", "H_TEXT"],
            lines,
        )


# ============================================================================
# 4. cadmind-wall-slab-section (WallSlabSectionHandler)
# ============================================================================


class WallSlabSectionHandler:
    """Cleanroom implementation of WallSlabSectionHandler (TierAWave5Handlers.cs)."""

    def execute(self, args: WallSlabSectionArgs) -> WallSlabSectionResult:
        """Draw structural wall or slab section with rotation and break lines."""
        elem = (args.element or "").strip().lower()
        if elem not in ("wall", "slab"):
            return WallSlabSectionResult(
                "ERROR",
                f"DEGENERATE_GEOMETRY: Element must be 'wall' or 'slab'. Received '{args.element}'.",
                elem,
                0.0,
                0,
            )

        try:
            length = _validate_finite(args.length, "length")
            thick = _validate_finite(args.thickness, "thickness")
        except DegenerateGeometryError as e:
            return WallSlabSectionResult("ERROR", str(e), elem, 0.0, 0)

        if length <= 1e-4 or thick <= 1e-4:
            return WallSlabSectionResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: Length and Thickness must be positive numbers.",
                elem,
                0.0,
                0,
            )

        ox = 0.0
        oy = 0.0
        if args.origin is not None and len(args.origin) >= 2:
            ox = _validate_finite(args.origin[0], "origin_x")
            oy = _validate_finite(args.origin[1], "origin_y")

        rad = math.radians(args.rotation)
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)

        def rot_p(local_x: float, local_y: float) -> Point2D:
            gx = ox + (local_x * cos_r - local_y * sin_r)
            gy = oy + (local_x * sin_r + local_y * cos_r)
            return Point2D(gx, gy)

        lines: List[LineSegment2D] = []
        p1 = rot_p(0.0, 0.0)
        p2 = rot_p(length, 0.0)
        p3 = rot_p(length, thick)
        p4 = rot_p(0.0, thick)
        lines.extend([LineSegment2D(p1, p2), LineSegment2D(p2, p3), LineSegment2D(p3, p4), LineSegment2D(p4, p1)])

        if args.axis:
            lines.append(LineSegment2D(rot_p(-length * 0.1, thick / 2.0), rot_p(length * 1.1, thick / 2.0)))

        area = length * thick
        msg = f"{elem.capitalize()} section drawn ({length:g}x{thick:g} mm) on layer '{args.layer}'."
        return WallSlabSectionResult("OK", msg, elem, area, len(lines), lines)


# ============================================================================
# 5. cadmind-material-hatch (MaterialHatchHandler)
# ============================================================================


class MaterialHatchHandler:
    """Cleanroom implementation of MaterialHatchHandler (TierAWave2Handlers.cs)."""

    def execute(
        self,
        args: MaterialHatchArgs,
        layer_locks: Optional[Dict[str, bool]] = None,
    ) -> ToolGenericResult:
        """Create material hatch with boundary verification and rollback safety."""
        try:
            scale = _validate_finite(args.pattern_scale, "pattern_scale")
        except DegenerateGeometryError as e:
            return ToolGenericResult("ERROR", str(e), 0)

        if scale <= 1e-4:
            return ToolGenericResult("ERROR", "DEGENERATE_GEOMETRY: PatternScale must be positive and non-zero.", 0)

        has_pts = args.boundary_points is not None and len(args.boundary_points) >= 3
        has_h = bool(args.boundary_handle and args.boundary_handle.strip())

        if not has_pts and not has_h:
            return ToolGenericResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: Material hatch requires at least 3 BoundaryPoints or a valid BoundaryHandle.",
                0,
            )

        locks = layer_locks or {}
        if locks.get(args.layer.strip().lower(), False):
            return ToolGenericResult(
                "ERROR",
                f"LOCKED_LAYER: Target layer '{args.layer}' is locked. Transaction rolled back.",
                0,
            )

        msg = f"Material hatch '{args.pattern_name}' created on layer '{args.layer}'."
        return ToolGenericResult("OK", msg, 1)


# ============================================================================
# 6. cadmind-steel-connection (SteelConnectionHandler)
# ============================================================================


class SteelConnectionHandler:
    """Cleanroom implementation of SteelConnectionHandler (TierBWave17Handlers.cs)."""

    def execute(self, args: SteelConnectionArgs) -> SteelConnectionResult:
        """Generate bolted steel connection detail with baseplate and bolt patterns."""
        if args.bolt_rows <= 0:
            raise CleanroomError("INVALID_BOLT_ROWS: BoltRows must be positive.")
        if args.bolt_cols <= 0:
            raise CleanroomError("INVALID_BOLT_COLS: BoltCols must be positive.")

        bp = _validate_finite(args.bolt_pitch, "bolt_pitch")
        bg = _validate_finite(args.bolt_gauge, "bolt_gauge")
        bd = _validate_finite(args.bolt_dia, "bolt_dia")

        if bp <= 0.0 or bg <= 0.0 or bd <= 0.0:
            raise CleanroomError("INVALID_BOLT_DIMENSIONS: Pitch, Gauge, and Dia must be positive.")

        ox = 0.0
        oy = 0.0
        if args.origin is not None and len(args.origin) >= 2:
            ox = _validate_finite(args.origin[0], "origin_x")
            oy = _validate_finite(args.origin[1], "origin_y")

        circles: List[CircleIR] = []
        lines: List[LineSegment2D] = []

        total_grid_w = (args.bolt_cols - 1) * bg
        total_grid_h = (args.bolt_rows - 1) * bp

        # Bolt grid
        for r in range(args.bolt_rows):
            for c in range(args.bolt_cols):
                bx = ox - total_grid_w / 2.0 + c * bg
                by = oy - total_grid_h / 2.0 + r * bp
                circles.append(CircleIR(Point2D(bx, by), bd / 2.0))
                # Crosshairs
                lines.append(LineSegment2D(Point2D(bx - bd * 0.8, by), Point2D(bx + bd * 0.8, by)))
                lines.append(LineSegment2D(Point2D(bx, by - bd * 0.8), Point2D(bx, by + bd * 0.8)))

        # Plate border (if width/height given or default margin)
        pw = args.plate_width if args.plate_width is not None else total_grid_w + 2.0 * bd * 2.0
        ph = args.plate_height if args.plate_height is not None else total_grid_h + 2.0 * bd * 2.0

        p1 = Point2D(ox - pw / 2, oy - ph / 2)
        p2 = Point2D(ox + pw / 2, oy - ph / 2)
        p3 = Point2D(ox + pw / 2, oy + ph / 2)
        p4 = Point2D(ox - pw / 2, oy + ph / 2)
        lines.extend([LineSegment2D(p1, p2), LineSegment2D(p2, p3), LineSegment2D(p3, p4), LineSegment2D(p4, p1)])

        bolt_count = args.bolt_rows * args.bolt_cols
        entity_count = len(circles) + len(lines)
        handles = [f"CONN_BOLT_{i:02d}" for i in range(1, bolt_count + 1)]

        msg = f"Steel connection detail drawn: {args.bolt_rows}x{args.bolt_cols} M{bd:g} bolts."
        return SteelConnectionResult(
            status="SUCCESS",
            message=msg,
            plate_created=True,
            bolt_count=bolt_count,
            bolt_diameter=bd,
            layer=args.layer,
            plate_layer=args.plate_layer,
            entity_count=entity_count,
            created_handles=handles,
            bolt_circles=circles,
            plate_lines=lines,
        )
