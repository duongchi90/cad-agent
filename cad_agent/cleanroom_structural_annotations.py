"""cad_agent/cleanroom_structural_annotations.py.

Batch ST2: Structural Schedules, Material Tags, Rebar Callouts & Area Takeoffs.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierAWave3Handlers.cs: BarScheduleHandler (cadmind-bar-schedule)
  - TierAWave2Handlers.cs: MaterialTagHandler (cadmind-material-tag)
  - TierAWave4Handlers.cs: RebarCalloutHandler (cadmind-rebar-callout)
  - ExtendedHandlers.cs: CoordLabelHandler (cadmind-coord-label)
  - TierBWave15Handlers.cs: AreaTakeoffHandler (cadmind-area-takeoff)
  - TierBWave14Handlers.cs: LayerStandardCheckHandler (cadmind-layer-standard-check)

Completes Domain 3 (STRUCTURAL: 25/25 registered tools).
Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D, CircleIR),
strict IEEE-754 machine-epsilon safety, Banker's rounding parity,
and zero external pip dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set

from cad_agent.cleanroom_mechanical import LineSegment2D, Point2D

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
class BarScheduleRow:
    """Specification of a bar bending schedule row."""

    bar_mark: str
    diameter: float
    num_members: int
    bars_per_member: int
    length_mm: float
    shape_code: str = "00"

    def __post_init__(self) -> None:
        _validate_finite(self.diameter, "diameter")
        _validate_finite(self.length_mm, "length_mm")
        if self.diameter <= 1e-4 or self.length_mm <= 1e-4:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Diameter and length must be positive.")
        if self.num_members <= 0 or self.bars_per_member <= 0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Member counts must be positive integers.")


@dataclass(frozen=True)
class BarScheduleArgs:
    """Arguments matching TierAWave3Contracts.BarScheduleArgs."""

    rows: Sequence[BarScheduleRow]
    insertion_point: Optional[Sequence[float]] = None
    title: str = "BAR BENDING SCHEDULE"
    row_height: float = 8.0
    column_widths: Optional[Sequence[float]] = None
    text_height: float = 3.0
    layer: str = "TABLE"
    text_layer: str = "TEXT"


@dataclass(frozen=True)
class BarScheduleResult:
    """Result matching TierAWave3Contracts.BarScheduleResult."""

    status: str
    message: str
    row_count: int
    total_weight_kg: float
    processed_count: int
    grid_lines: List[LineSegment2D] = field(default_factory=list)


@dataclass(frozen=True)
class MaterialTagArgs:
    """Arguments matching TierAWave2Contracts.MaterialTagArgs."""

    target_point: Optional[Sequence[float]] = None
    text_point: Optional[Sequence[float]] = None
    material_code: str = ""
    has_frame: bool = True
    text_height: float = 3.5
    layer: str = "TEXT"


@dataclass(frozen=True)
class ToolGenericResult:
    """Generic tool result matching C# ToolGenericResult."""

    status: str
    message: str
    count: int = 0
    lines: List[LineSegment2D] = field(default_factory=list)


@dataclass(frozen=True)
class RebarCalloutArgs:
    """Arguments matching TierAWave4Contracts.RebarCalloutArgs."""

    point: Optional[Sequence[float]] = None
    count: Optional[int] = None
    dia: Optional[float] = None
    spacing: Optional[float] = None
    bar: str = "D"
    leader_to: Optional[Sequence[float]] = None
    text: Optional[str] = None
    height: float = 200.0
    layer: str = "S-ANNO"


@dataclass(frozen=True)
class RebarCalloutResult:
    """Result matching TierAWave4Contracts.RebarCalloutResult."""

    status: str
    message: str
    callout_note: str
    entity_count: int


@dataclass(frozen=True)
class CoordLabelArgs:
    """Arguments matching ExtendedContracts.CoordLabelArgs."""

    x: float
    y: float
    prefix: str = ""
    layer: str = "COORD"


@dataclass(frozen=True)
class AreaTakeoffItem:
    """Individual item for area takeoff."""

    handle: str
    label: str
    raw_area: float
    scaled_area: float


@dataclass(frozen=True)
class AreaTakeoffArgs:
    """Arguments matching TierBWave15Contracts.AreaTakeoffArgs."""

    handles: Sequence[str]
    labels: Optional[Sequence[str]] = None
    scale: float = 1.0
    decimals: int = 2


@dataclass(frozen=True)
class AreaTakeoffResult:
    """Result matching TierBWave15Contracts.AreaTakeoffResult."""

    status: str
    message: str
    grand_total_area: float
    total_entities_processed: int
    items: List[AreaTakeoffItem]
    per_label_totals: Dict[str, float]
    skipped_handles: List[str]


@dataclass(frozen=True)
class LayerStandardCheckArgs:
    """Arguments matching TierBWave14Contracts.LayerStandardCheckArgs."""

    allowed_layers: Optional[Sequence[str]] = None
    allowed_prefixes: Optional[Sequence[str]] = None


@dataclass(frozen=True)
class LayerStandardCheckResult:
    """Result matching TierBWave14Contracts.LayerStandardCheckResult."""

    status: str
    message: str
    total_layers: int
    standard_layers_count: int
    non_standard_layers_count: int
    compliance_rate_percent: float
    standard_layers: List[str]
    non_standard_layers: List[str]


# ============================================================================
# 1. cadmind-bar-schedule (BarScheduleHandler)
# ============================================================================


class BarScheduleHandler:
    """Cleanroom implementation of BarScheduleHandler (TierAWave3Handlers.cs)."""

    DEFAULT_COLUMN_WIDTHS: List[float] = [25.0, 15.0, 20.0, 20.0, 20.0, 25.0, 30.0]

    def execute(
        self,
        args: BarScheduleArgs,
        layer_locks: Optional[Dict[str, bool]] = None,
    ) -> BarScheduleResult:
        """Draw Bar Bending Schedule with rebar unit weight formula (d^2 / 162.0)."""
        if not args.rows or len(args.rows) == 0:
            return BarScheduleResult(
                status="ERROR",
                message="DEGENERATE_GEOMETRY: Bar schedule requires at least one row.",
                row_count=0,
                total_weight_kg=0.0,
                processed_count=0,
            )

        try:
            rh = _validate_finite(args.row_height, "row_height")
            th = _validate_finite(args.text_height, "text_height")
        except DegenerateGeometryError as e:
            return BarScheduleResult("ERROR", str(e), 0, 0.0, 0)

        if rh <= 1e-4 or th <= 1e-4:
            return BarScheduleResult(
                "ERROR",
                "DEGENERATE_GEOMETRY: RowHeight and TextHeight must be positive and non-zero.",
                0,
                0.0,
                0,
            )

        ox = 0.0
        oy = 0.0
        if args.insertion_point is not None and len(args.insertion_point) >= 2:
            ox = _validate_finite(args.insertion_point[0], "insertion_point_x")
            oy = _validate_finite(args.insertion_point[1], "insertion_point_y")

        locks = layer_locks or {}
        if locks.get(args.layer.strip().lower(), False) or locks.get(args.text_layer.strip().lower(), False):
            return BarScheduleResult(
                "ERROR",
                f"LOCKED_LAYER: Target layer '{args.layer}' is locked. Transaction rolled back.",
                0,
                0.0,
                0,
            )

        # Accumulate weight using exact standard rebar formula: (d^2 / 162.0) * length_m * total_bars
        total_weight = 0.0
        for r in args.rows:
            length_m = r.length_mm / 1000.0
            total_bars = r.num_members * r.bars_per_member
            unit_weight = (r.diameter * r.diameter) / 162.0
            row_weight = unit_weight * length_m * total_bars
            total_weight += row_weight

        col_w = list(args.column_widths or self.DEFAULT_COLUMN_WIDTHS)
        total_w = sum(col_w)
        row_count = len(args.rows)
        total_rows = row_count + 3  # title + header + N rows + summary
        total_h = total_rows * rh

        grid_lines: List[LineSegment2D] = []
        # Outer border
        grid_lines.append(LineSegment2D(Point2D(ox, oy), Point2D(ox + total_w, oy)))
        grid_lines.append(LineSegment2D(Point2D(ox + total_w, oy), Point2D(ox + total_w, oy - total_h)))
        grid_lines.append(LineSegment2D(Point2D(ox + total_w, oy - total_h), Point2D(ox, oy - total_h)))
        grid_lines.append(LineSegment2D(Point2D(ox, oy - total_h), Point2D(ox, oy)))

        # Dividers
        for r_idx in range(1, total_rows):
            cy = oy - r_idx * rh
            grid_lines.append(LineSegment2D(Point2D(ox, cy), Point2D(ox + total_w, cy)))

        # Column dividers
        cx = ox
        for w in col_w[:-1]:
            cx += w
            grid_lines.append(LineSegment2D(Point2D(cx, oy - rh), Point2D(cx, oy - total_h)))

        rounded_weight = round(total_weight, 2)
        processed_count = 1 + 7 + (row_count * 7) + 2 + len(grid_lines)

        msg = f"Bar schedule drawn with {row_count} rows (total rebar weight {rounded_weight:.2f} kg)."
        return BarScheduleResult("OK", msg, row_count, rounded_weight, processed_count, grid_lines)


# ============================================================================
# 2. cadmind-material-tag (MaterialTagHandler)
# ============================================================================


class MaterialTagHandler:
    """Cleanroom implementation of MaterialTagHandler (TierAWave2Handlers.cs)."""

    def execute(
        self,
        args: MaterialTagArgs,
        layer_locks: Optional[Dict[str, bool]] = None,
    ) -> ToolGenericResult:
        """Place structural material tag with leader and optional frame."""
        code = (args.material_code or "").strip()
        if not code:
            return ToolGenericResult("ERROR", "DEGENERATE_GEOMETRY: MaterialCode must be specified and non-empty.", 0)

        if args.target_point is None or len(args.target_point) < 2 or args.text_point is None or len(args.text_point) < 2:
            return ToolGenericResult("ERROR", "DEGENERATE_GEOMETRY: TargetPoint and TextPoint must both be specified.", 0)

        tx = _validate_finite(args.target_point[0], "target_x")
        ty = _validate_finite(args.target_point[1], "target_y")
        px = _validate_finite(args.text_point[0], "text_x")
        py = _validate_finite(args.text_point[1], "text_y")

        dist = math.hypot(px - tx, py - ty)
        if dist <= 1e-4:
            return ToolGenericResult("ERROR", "DEGENERATE_GEOMETRY: TargetPoint and TextPoint are coincident.", 0)

        th = _validate_finite(args.text_height, "text_height")
        if th <= 1e-4:
            return ToolGenericResult("ERROR", "DEGENERATE_GEOMETRY: TextHeight must be positive and non-zero.", 0)

        locks = layer_locks or {}
        if locks.get(args.layer.strip().lower(), False):
            return ToolGenericResult("ERROR", f"LOCKED_LAYER: Target layer '{args.layer}' is locked.", 0)

        lines: List[LineSegment2D] = [LineSegment2D(Point2D(tx, ty), Point2D(px, py))]

        if args.has_frame:
            # Box frame around text
            bw = len(code) * th * 0.8 + 4.0
            bh = th * 1.5 + 2.0
            lines.append(LineSegment2D(Point2D(px, py - bh / 2), Point2D(px + bw, py - bh / 2)))
            lines.append(LineSegment2D(Point2D(px + bw, py - bh / 2), Point2D(px + bw, py + bh / 2)))
            lines.append(LineSegment2D(Point2D(px + bw, py + bh / 2), Point2D(px, py + bh / 2)))
            lines.append(LineSegment2D(Point2D(px, py + bh / 2), Point2D(px, py - bh / 2)))

        msg = f"Material tag '{code}' placed on layer '{args.layer}'."
        return ToolGenericResult("OK", msg, len(lines), lines)


# ============================================================================
# 3. cadmind-rebar-callout (RebarCalloutHandler)
# ============================================================================


class RebarCalloutHandler:
    """Cleanroom implementation of RebarCalloutHandler (TierAWave4Handlers.cs)."""

    def execute(self, args: RebarCalloutArgs) -> RebarCalloutResult:
        """Generate formatted rebar callout note and leader."""
        note = args.text
        if not note or not note.strip():
            if args.count is not None and args.dia is not None and args.spacing is not None:
                note = f"{args.count}{args.bar}{args.dia:g}@{args.spacing:g}"
            elif args.dia is not None:
                note = f"{args.bar}{args.dia:g}"
            else:
                note = "REBAR_CALLOUT"

        if args.point is not None and args.leader_to is not None:
            if len(args.point) >= 2 and len(args.leader_to) >= 2:
                dist = math.hypot(args.leader_to[0] - args.point[0], args.leader_to[1] - args.point[1])
                if dist <= 1e-4:
                    return RebarCalloutResult("ERROR", "DEGENERATE_GEOMETRY: Leader start and end are coincident.", note, 0)

        msg = f"Rebar callout '{note}' placed on layer '{args.layer}'."
        return RebarCalloutResult("OK", msg, note, 1)


# ============================================================================
# 4. cadmind-coord-label (CoordLabelHandler)
# ============================================================================


class CoordLabelHandler:
    """Cleanroom implementation of CoordLabelHandler (ExtendedHandlers.cs)."""

    def execute(self, args: CoordLabelArgs) -> ToolGenericResult:
        """Place coordinate point marker and label formatted as X=..., Y=..."""
        x = _validate_finite(args.x, "x")
        y = _validate_finite(args.y, "y")

        label = f"{args.prefix}X={x:.2f}, Y={y:.2f}"
        msg = f"Coord label ({x:.2f}, {y:.2f}) placed on layer '{args.layer}'."
        return ToolGenericResult("OK", msg, 1)


# ============================================================================
# 5. cadmind-area-takeoff (AreaTakeoffHandler)
# ============================================================================


class AreaTakeoffHandler:
    """Cleanroom implementation of AreaTakeoffHandler (TierBWave15Handlers.cs)."""

    def execute(
        self,
        args: AreaTakeoffArgs,
        entity_areas: Dict[str, float],
    ) -> AreaTakeoffResult:
        """Calculate scaled area takeoff per label and grand total.

        entity_areas maps handle -> raw_area
        """
        if not args.handles or len(args.handles) == 0:
            raise CleanroomError("EMPTY_INPUT: At least one entity handle must be provided.")

        scale = _validate_finite(args.scale, "scale")
        if scale <= 0.0:
            raise CleanroomError("INVALID_SCALE: Scale must be positive and finite.")

        if args.decimals < 0 or args.decimals > 8:
            raise CleanroomError("INVALID_DECIMALS: Decimals must be between 0 and 8.")

        items: List[AreaTakeoffItem] = []
        skipped: List[str] = []
        per_label_totals: Dict[str, float] = {}
        grand_total = 0.0

        for i, h in enumerate(args.handles):
            h_clean = h.strip()
            label = (
                args.labels[i].strip()
                if args.labels and i < len(args.labels) and args.labels[i] and args.labels[i].strip()
                else "UNLABELLED"
            )

            if h_clean in entity_areas:
                raw_area = entity_areas[h_clean]
                scaled_area = round(raw_area * scale, args.decimals)
                items.append(
                    AreaTakeoffItem(
                        handle=h_clean,
                        label=label,
                        raw_area=raw_area,
                        scaled_area=scaled_area,
                    )
                )
                per_label_totals[label] = round(
                    per_label_totals.get(label, 0.0) + scaled_area,
                    args.decimals,
                )
                grand_total += scaled_area
            else:
                skipped.append(h)

        grand_total_rounded = round(grand_total, args.decimals)
        msg = f"Area takeoff complete: {len(items)} areas processed, grand total = {grand_total_rounded}."
        return AreaTakeoffResult(
            status="SUCCESS",
            message=msg,
            grand_total_area=grand_total_rounded,
            total_entities_processed=len(items),
            items=items,
            per_label_totals=per_label_totals,
            skipped_handles=skipped,
        )


# ============================================================================
# 6. cadmind-layer-standard-check (LayerStandardCheckHandler)
# ============================================================================


class LayerStandardCheckHandler:
    """Cleanroom implementation of LayerStandardCheckHandler (TierBWave14Handlers.cs)."""

    DEFAULT_PREFIXES: List[str] = ["S-", "0", "Defpoints"]

    def execute(
        self,
        args: LayerStandardCheckArgs,
        drawing_layers: Sequence[str],
    ) -> LayerStandardCheckResult:
        """Verify layer compliance against structural CAD standards."""
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
            f"Structural layer standard check completed: {len(standard_layers)}/{total} compliant "
            f"({compliance_rate}%)."
        )
        return LayerStandardCheckResult(
            status="SUCCESS",
            message=msg,
            total_layers=total,
            standard_layers_count=len(standard_layers),
            non_standard_layers_count=len(non_standard_layers),
            compliance_rate_percent=compliance_rate,
            standard_layers=standard_layers,
            non_standard_layers=non_standard_layers,
        )
