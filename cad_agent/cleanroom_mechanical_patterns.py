"""cad_agent/cleanroom_mechanical_patterns.py.

Batch M6: Mechanical Patterns, Thread Callouts, Tapers & Engineering Calculations.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierBWave8Handlers.cs: HolePatternHandler (cadmind-hole-pattern)
  - ExtendedHandlers.cs: ThreadCalloutHandler (cadmind-thread-callout)
  - TierAWave2Handlers.cs: TaperSymbolHandler (cadmind-taper-symbol)
  - TierBWave13Handlers.cs: CutLengthHandler (cadmind-cut-length)
  - TierBWave14Handlers.cs: MechLayerCheckHandler (cadmind-mech-layer-check)

Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D, CircleIR),
strict IEEE-754 machine-epsilon safety, Banker's rounding parity,
and zero external pip dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

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
class HolePatternArgs:
    """Arguments matching TierBWave8Contracts.HolePatternArgs."""

    pattern_type: str = "RECTANGULAR"  # "RECTANGULAR" or "CIRCULAR"
    origin_x: float = 0.0
    origin_y: float = 0.0
    hole_diameter: float = 20.0
    rows_or_count: int = 2
    columns: int = 2
    spacing_x_or_bcd: float = 100.0
    spacing_y: float = 100.0
    start_angle_deg: float = 0.0
    layer: str = "M-HOLE"


@dataclass(frozen=True)
class HolePatternResult:
    """Result matching TierBWave8Contracts.HolePatternResult."""

    status: str
    message: str
    layer: str
    pattern_type: str
    hole_count: int
    entity_count: int
    hole_radius: float
    circles: List[CircleIR] = field(default_factory=list)
    handles: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ThreadCalloutArgs:
    """Arguments matching ExtendedContracts.ThreadCalloutArgs."""

    handles: Optional[Sequence[str]] = None
    thread_spec: str = "M12x1.75-6H"
    layer: str = "DIM"


@dataclass(frozen=True)
class ToolGenericResult:
    """Generic tool result matching C# ToolGenericResult."""

    status: str
    message: str
    count: int = 0
    lines: List[LineSegment2D] = field(default_factory=list)


@dataclass(frozen=True)
class TaperSymbolArgs:
    """Arguments matching TierAWave2Contracts.TaperSymbolArgs."""

    insertion_point: Point2D = field(default_factory=lambda: Point2D(0.0, 0.0))
    ratio: str = "1:10"
    symbol_type: str = "Taper"  # "Taper" or "Slope"
    direction: str = "Right"  # "Right", "Left", "Up", "Down"
    symbol_size: float = 5.0
    layer: str = "DIM"


@dataclass(frozen=True)
class CutLengthItem:
    """Result item for cut length measurement."""

    handle: str
    label: Optional[str]
    length: float
    is_closed: bool


@dataclass(frozen=True)
class CutLengthArgs:
    """Arguments matching TierBWave13Contracts.CutLengthArgs."""

    handles: Sequence[str]
    labels: Optional[Sequence[str]] = None
    scale: float = 1.0
    decimals: int = 1


@dataclass(frozen=True)
class CutLengthResult:
    """Result matching TierBWave13Contracts.CutLengthResult."""

    status: str
    message: str
    total_length: float
    count: int
    items: List[CutLengthItem]
    skipped_handles: List[str]


@dataclass(frozen=True)
class MechLayerCheckArgs:
    """Arguments matching TierBWave14Contracts.MechLayerCheckArgs."""

    allowed_layers: Optional[Sequence[str]] = None
    allowed_prefixes: Optional[Sequence[str]] = None


@dataclass(frozen=True)
class MechLayerCheckResult:
    """Result matching TierBWave14Contracts.MechLayerCheckResult."""

    status: str
    message: str
    total_layers: int
    standard_layers_count: int
    non_standard_layers_count: int
    compliance_rate_percent: float
    standard_layers: List[str]
    non_standard_layers: List[str]


# ============================================================================
# 1. cadmind-hole-pattern (HolePatternHandler)
# ============================================================================


class HolePatternHandler:
    """Cleanroom implementation of HolePatternHandler (TierBWave8Handlers.cs)."""

    def execute(self, args: HolePatternArgs) -> HolePatternResult:
        """Generate rectangular or circular hole patterns with boundary safety."""
        # 1. Validate numeric finiteness
        try:
            ox = _validate_finite(args.origin_x, "origin_x")
            oy = _validate_finite(args.origin_y, "origin_y")
            hd = _validate_finite(args.hole_diameter, "hole_diameter")
            s_x = _validate_finite(args.spacing_x_or_bcd, "spacing_x_or_bcd")
            s_y = _validate_finite(args.spacing_y, "spacing_y")
        except DegenerateGeometryError as e:
            return HolePatternResult(
                status="ERROR",
                message=str(e),
                layer=args.layer,
                pattern_type=args.pattern_type,
                hole_count=0,
                entity_count=0,
                hole_radius=0.0,
            )

        # 2. Hole diameter validation
        if hd <= 1e-4:
            return HolePatternResult(
                status="ERROR",
                message="DEGENERATE_GEOMETRY: HoleDiameter must be positive (> 1e-4).",
                layer=args.layer,
                pattern_type=args.pattern_type,
                hole_count=0,
                entity_count=0,
                hole_radius=0.0,
            )

        p_type = (args.pattern_type or "RECTANGULAR").strip().upper()
        if p_type not in ("RECTANGULAR", "CIRCULAR"):
            return HolePatternResult(
                status="ERROR",
                message="DEGENERATE_GEOMETRY: PatternType must be RECTANGULAR or CIRCULAR.",
                layer=args.layer,
                pattern_type=p_type,
                hole_count=0,
                entity_count=0,
                hole_radius=0.0,
            )

        r = hd / 2.0
        circles: List[CircleIR] = []

        if p_type == "RECTANGULAR":
            rows = args.rows_or_count
            cols = args.columns
            total_holes = rows * cols

            if rows < 1 or cols < 1:
                return HolePatternResult(
                    status="ERROR",
                    message="DEGENERATE_GEOMETRY: Rows and Columns must be at least 1.",
                    layer=args.layer,
                    pattern_type=p_type,
                    hole_count=0,
                    entity_count=0,
                    hole_radius=r,
                )

            if total_holes < 2 or total_holes > 256:
                return HolePatternResult(
                    status="ERROR",
                    message=f"DEGENERATE_GEOMETRY: Total holes ({total_holes}) must be between 2 and 256.",
                    layer=args.layer,
                    pattern_type=p_type,
                    hole_count=0,
                    entity_count=0,
                    hole_radius=r,
                )

            if cols > 1 and s_x <= 1.1 * hd:
                return HolePatternResult(
                    status="ERROR",
                    message=f"DEGENERATE_GEOMETRY: SpacingX ({s_x}) must exceed 1.1 * HoleDiameter ({1.1 * hd:.2f}) to avoid overlap.",
                    layer=args.layer,
                    pattern_type=p_type,
                    hole_count=0,
                    entity_count=0,
                    hole_radius=r,
                )

            if rows > 1 and s_y <= 1.1 * hd:
                return HolePatternResult(
                    status="ERROR",
                    message=f"DEGENERATE_GEOMETRY: SpacingY ({s_y}) must exceed 1.1 * HoleDiameter ({1.1 * hd:.2f}) to avoid overlap.",
                    layer=args.layer,
                    pattern_type=p_type,
                    hole_count=0,
                    entity_count=0,
                    hole_radius=r,
                )

            for col_idx in range(cols):
                for row_idx in range(rows):
                    cx = ox + col_idx * s_x
                    cy = oy + row_idx * s_y
                    circles.append(CircleIR(Point2D(cx, cy), r))

            hole_count = len(circles)
            entity_count = hole_count
            msg = f"Generated rectangular hole pattern: {rows}x{cols} ({hole_count} holes)."

        else:  # CIRCULAR
            n = args.rows_or_count
            bcd = s_x

            if n < 3 or n > 128:
                return HolePatternResult(
                    status="ERROR",
                    message=f"DEGENERATE_GEOMETRY: Circular pattern hole count ({n}) must be between 3 and 128.",
                    layer=args.layer,
                    pattern_type=p_type,
                    hole_count=0,
                    entity_count=0,
                    hole_radius=r,
                )

            if bcd <= hd:
                return HolePatternResult(
                    status="ERROR",
                    message=f"DEGENERATE_GEOMETRY: BCD ({bcd}) must exceed HoleDiameter ({hd}).",
                    layer=args.layer,
                    pattern_type=p_type,
                    hole_count=0,
                    entity_count=0,
                    hole_radius=r,
                )

            # Chord pitch between adjacent holes
            chord = bcd * math.sin(math.pi / n)
            if chord <= 1.1 * hd:
                return HolePatternResult(
                    status="ERROR",
                    message=f"DEGENERATE_GEOMETRY: Hole collision or insufficient ligament (chord {chord:.2f} <= {1.1 * hd:.2f}).",
                    layer=args.layer,
                    pattern_type=p_type,
                    hole_count=0,
                    entity_count=0,
                    hole_radius=r,
                )

            # Reference BCD circle
            bcd_radius = bcd / 2.0
            circles.append(CircleIR(Point2D(ox, oy), bcd_radius))

            start_rad = math.radians(args.start_angle_deg)
            step_rad = 2.0 * math.pi / n

            for i in range(n):
                angle = start_rad + i * step_rad
                cx = ox + bcd_radius * math.cos(angle)
                cy = oy + bcd_radius * math.sin(angle)
                circles.append(CircleIR(Point2D(cx, cy), r))

            hole_count = n
            entity_count = n + 1  # 1 BCD reference circle + n hole circles
            msg = f"Generated circular bolt pattern: {n} holes on BCD {bcd:.2f}."

        return HolePatternResult(
            status="OK",
            message=msg,
            layer=args.layer,
            pattern_type=p_type,
            hole_count=hole_count,
            entity_count=entity_count,
            hole_radius=r,
            circles=circles,
            handles=[f"H_{i:04X}" for i in range(1, entity_count + 1)],
        )


# ============================================================================
# 2. cadmind-thread-callout (ThreadCalloutHandler)
# ============================================================================


class ThreadCalloutHandler:
    """Cleanroom implementation of ThreadCalloutHandler (ExtendedHandlers.cs)."""

    def execute(
        self,
        args: ThreadCalloutArgs,
        target_circles: Optional[Sequence[CircleIR]] = None,
    ) -> ToolGenericResult:
        """Place thread callout leaders and text annotations on circular features."""
        spec = (args.thread_spec or "").strip()
        if not spec:
            return ToolGenericResult("ERROR", "DEGENERATE_GEOMETRY: Thread specification must be non-empty.", 0)

        circles = list(target_circles or [])
        if not circles:
            return ToolGenericResult("OK", "No circles found to place thread callout.", 0)

        lines: List[LineSegment2D] = []
        for c in circles:
            # Leader from rim at 45 deg (+cos45, +sin45)
            rim_x = c.center.x + c.radius * 0.7071067811865476
            rim_y = c.center.y + c.radius * 0.7071067811865476
            leader_elbow = Point2D(rim_x + 6.0, rim_y + 4.0)
            leader_end = Point2D(leader_elbow.x + 8.0, leader_elbow.y)

            lines.append(LineSegment2D(Point2D(rim_x, rim_y), leader_elbow))
            lines.append(LineSegment2D(leader_elbow, leader_end))

        count = len(circles)
        msg = f"Thread callout '{spec}' placed on {count} handles on layer '{args.layer}'."
        return ToolGenericResult("OK", msg, count, lines)


# ============================================================================
# 3. cadmind-taper-symbol (TaperSymbolHandler)
# ============================================================================


class TaperSymbolHandler:
    """Cleanroom implementation of TaperSymbolHandler (TierAWave2Handlers.cs)."""

    DIRECTION_ANGLES: Dict[str, float] = {
        "RIGHT": 0.0,
        "LEFT": math.pi,
        "UP": math.pi / 2.0,
        "DOWN": -math.pi / 2.0,
    }

    def execute(self, args: TaperSymbolArgs) -> ToolGenericResult:
        """Generate ISO 3040 taper or slope symbol geometry with orientation vector."""
        ratio_str = (args.ratio or "").strip()
        if not ratio_str:
            return ToolGenericResult("ERROR", "DEGENERATE_GEOMETRY: Taper ratio must be specified.", 0)

        size = _validate_finite(args.symbol_size, "symbol_size")
        if size <= 1e-4:
            return ToolGenericResult("ERROR", "DEGENERATE_GEOMETRY: SymbolSize must be positive (> 1e-4).", 0)

        dir_norm = (args.direction or "RIGHT").strip().upper()
        if dir_norm not in self.DIRECTION_ANGLES:
            dir_norm = "RIGHT"
        theta = self.DIRECTION_ANGLES[dir_norm]

        # Geometry: Baseline, center axis, and taper triangle
        # Base triangle along local X
        local_p0 = Point2D(0.0, 0.0)
        local_p1 = Point2D(size, size * 0.25)
        local_p2 = Point2D(size, -size * 0.25)

        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        def rot(p: Point2D) -> Point2D:
            rx = args.insertion_point.x + (p.x * cos_t - p.y * sin_t)
            ry = args.insertion_point.y + (p.x * sin_t + p.y * cos_t)
            return Point2D(rx, ry)

        lines: List[LineSegment2D] = [
            LineSegment2D(rot(local_p0), rot(local_p1)),
            LineSegment2D(rot(local_p1), rot(local_p2)),
            LineSegment2D(rot(local_p2), rot(local_p0)),
            # Centerline
            LineSegment2D(rot(Point2D(-size * 0.2, 0.0)), rot(Point2D(size * 1.2, 0.0))),
        ]

        msg = f"Taper symbol '{ratio_str}' ({args.symbol_type}) placed pointing {dir_norm}."
        return ToolGenericResult("OK", msg, len(lines), lines)


# ============================================================================
# 4. cadmind-cut-length (CutLengthHandler)
# ============================================================================


class CutLengthHandler:
    """Cleanroom implementation of CutLengthHandler (TierBWave13Handlers.cs)."""

    def execute(
        self,
        args: CutLengthArgs,
        curve_database: Dict[str, Tuple[float, bool]],
    ) -> CutLengthResult:
        """Calculate total cut lengths across curve handles with Banker's rounding.

        curve_database maps: handle -> (length, is_closed)
        """
        if not args.handles or len(args.handles) == 0:
            raise CleanroomError("INVALID_ARGUMENT: At least one entity handle must be provided.")

        scale = _validate_finite(args.scale, "scale")
        if scale <= 0.0:
            raise CleanroomError("INVALID_SCALE: Scale factor must be positive and finite.")

        if args.decimals < 0 or args.decimals > 8:
            raise CleanroomError("INVALID_DECIMALS: Decimals must be between 0 and 8.")

        items: List[CutLengthItem] = []
        skipped: List[str] = []
        raw_total = 0.0

        for i, h in enumerate(args.handles):
            label = args.labels[i] if args.labels and i < len(args.labels) else None

            # Attempt hex handle parse simulation
            h_clean = h.strip()
            try:
                int(h_clean, 16)
            except ValueError:
                skipped.append(h)
                continue

            if h_clean in curve_database:
                c_len, is_closed = curve_database[h_clean]
                scaled_len = round(c_len * scale, args.decimals)
                raw_total += scaled_len
                items.append(
                    CutLengthItem(
                        handle=h_clean,
                        label=label,
                        length=scaled_len,
                        is_closed=is_closed,
                    )
                )
            else:
                skipped.append(h)

        total_length = round(raw_total, args.decimals)
        msg = (
            f"Calculated cut lengths: {len(items)} curves processed, total length = {total_length:g} "
            f"({len(skipped)} skipped)."
        )
        return CutLengthResult(
            status="SUCCESS",
            message=msg,
            total_length=total_length,
            count=len(items),
            items=items,
            skipped_handles=skipped,
        )


# ============================================================================
# 5. cadmind-mech-layer-check (MechLayerCheckHandler)
# ============================================================================


class MechLayerCheckHandler:
    """Cleanroom implementation of MechLayerCheckHandler (TierBWave14Handlers.cs)."""

    DEFAULT_PREFIXES: List[str] = ["M-", "0", "Defpoints"]

    def execute(
        self,
        args: MechLayerCheckArgs,
        drawing_layers: Sequence[str],
    ) -> MechLayerCheckResult:
        """Verify layer compliance against mechanical standards."""
        allowed_prefixes = (
            list(args.allowed_prefixes)
            if args.allowed_prefixes is not None and len(args.allowed_prefixes) > 0
            else list(self.DEFAULT_PREFIXES)
        )

        allowed_layers: Set[str] = (
            {lyr.strip().lower() for lyr in args.allowed_layers}
            if args.allowed_layers is not None
            else set()
        )

        standard_layers: List[str] = []
        non_standard_layers: List[str] = []

        for lyr in drawing_layers:
            name_clean = lyr.strip()
            name_lower = name_clean.lower()

            is_standard = name_lower in allowed_layers or any(
                name_lower.startswith(p.lower()) for p in allowed_prefixes
            )

            if is_standard:
                standard_layers.append(name_clean)
            else:
                non_standard_layers.append(name_clean)

        total = len(standard_layers) + len(non_standard_layers)
        compliance_rate = (
            round((len(standard_layers) / total) * 100.0, 2) if total > 0 else 100.0
        )

        msg = (
            f"Mechanical layer standard check completed: {len(standard_layers)}/{total} compliant "
            f"({compliance_rate}%)."
        )
        return MechLayerCheckResult(
            status="SUCCESS",
            message=msg,
            total_layers=total,
            standard_layers_count=len(standard_layers),
            non_standard_layers_count=len(non_standard_layers),
            compliance_rate_percent=compliance_rate,
            standard_layers=standard_layers,
            non_standard_layers=non_standard_layers,
        )
