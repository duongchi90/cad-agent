"""cad_agent/cleanroom_mechanical_tables.py.

Batch M7: Mechanical Part Hatch, Hole Table & Bill of Materials (BOM) Table Engines.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierAWave4Handlers.cs: PartHatchHandler (cadmind-part-hatch)
  - TierAWave4Handlers.cs: HoleTableHandler (cadmind-hole-table)
  - TierAWave3Handlers.cs: BomTableHandler (cadmind-bom-table)

Completes Domain 2 (MECHANICAL: 22/22 registered tools).
Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D),
strict IEEE-754 machine-epsilon safety, Banker's rounding parity,
and zero external pip dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

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
class PartHatchArgs:
    """Arguments matching TierAWave4Contracts.PartHatchArgs."""

    handles: Sequence[str]
    pattern: str = "ANSI31"
    scale: float = 1.0
    start_angle: float = 45.0
    angle_step: float = 45.0
    layer: str = "M-HATCH"


@dataclass(frozen=True)
class PartHatchResult:
    """Result matching TierAWave4Contracts.PartHatchResult."""

    status: str
    message: str
    hatched_count: int
    processed_count: int


@dataclass(frozen=True)
class HoleRow:
    """Row in a Hole Table."""

    tag: str
    x: float
    y: float
    dia: float

    def __post_init__(self) -> None:
        _validate_finite(self.x, "x")
        _validate_finite(self.y, "y")
        _validate_finite(self.dia, "dia")
        if not self.tag or not self.tag.strip():
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Hole Tag must be non-empty.")
        if self.dia <= 1e-4:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Hole diameter must be positive and non-zero.")


@dataclass(frozen=True)
class HoleTableArgs:
    """Arguments matching TierAWave4Contracts.HoleTableArgs."""

    rows: Sequence[HoleRow]
    origin: Optional[Sequence[float]] = None
    row_height: float = 8.0
    text_height: float = 3.0
    layer: str = "TABLE"


@dataclass(frozen=True)
class HoleTableResult:
    """Result matching TierAWave4Contracts.HoleTableResult."""

    status: str
    message: str
    row_count: int
    processed_count: int
    grid_lines: List[LineSegment2D] = field(default_factory=list)


@dataclass(frozen=True)
class BomItem:
    """Item in a Bill of Materials (BOM) Table."""

    item_no: int
    description: str
    part_no: str
    material: str
    quantity: int
    unit_weight_kg: float = 0.0

    def __post_init__(self) -> None:
        if self.item_no <= 0 or self.quantity <= 0:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: Item quantity and item number must be positive (> 0)."
            )
        _validate_finite(self.unit_weight_kg, "unit_weight_kg")


@dataclass(frozen=True)
class BomTableArgs:
    """Arguments matching TierAWave3Contracts.BomTableArgs."""

    items: Sequence[BomItem]
    insertion_point: Optional[Sequence[float]] = None
    title: str = "BILL OF MATERIALS"
    row_height: float = 8.0
    column_widths: Optional[Sequence[float]] = None
    text_height: float = 3.0
    layer: str = "TABLE"
    text_layer: str = "TEXT"


@dataclass(frozen=True)
class BomTableResult:
    """Result matching TierAWave3Contracts.BomTableResult."""

    status: str
    message: str
    item_count: int
    total_weight_kg: float
    processed_count: int
    grid_lines: List[LineSegment2D] = field(default_factory=list)


# ============================================================================
# 1. cadmind-part-hatch (PartHatchHandler)
# ============================================================================


class PartHatchHandler:
    """Cleanroom implementation of PartHatchHandler (TierAWave4Handlers.cs)."""

    def execute(
        self,
        args: PartHatchArgs,
        boundary_database: Optional[Dict[str, bool]] = None,
        layer_locks: Optional[Dict[str, bool]] = None,
    ) -> PartHatchResult:
        """Apply mechanical crosshatching with boundary loop verification and lock checks.

        boundary_database maps handle -> is_closed.
        """
        if not args.handles or len(args.handles) == 0:
            return PartHatchResult(
                status="ERROR",
                message="DEGENERATE_GEOMETRY: Part hatch requires at least one boundary handle.",
                hatched_count=0,
                processed_count=0,
            )

        try:
            scale = _validate_finite(args.scale, "scale")
        except DegenerateGeometryError as e:
            return PartHatchResult(
                status="ERROR",
                message=str(e),
                hatched_count=0,
                processed_count=0,
            )

        if scale <= 1e-4:
            return PartHatchResult(
                status="ERROR",
                message="DEGENERATE_GEOMETRY: Pattern scale must be positive and non-zero.",
                hatched_count=0,
                processed_count=0,
            )

        locks = layer_locks or {}
        if locks.get(args.layer.strip().lower(), False):
            return PartHatchResult(
                status="ERROR",
                message=f"LOCKED_LAYER: Target layer '{args.layer}' is locked. Transaction rolled back.",
                hatched_count=0,
                processed_count=0,
            )

        boundaries = boundary_database or {}
        hatched_count = 0

        for h in args.handles:
            h_clean = h.strip()
            try:
                int(h_clean, 16)
            except ValueError:
                return PartHatchResult(
                    status="ERROR",
                    message=f"DEGENERATE_GEOMETRY: Entity handle '{h}' is invalid hex format.",
                    hatched_count=0,
                    processed_count=0,
                )

            # Check if boundary is closed
            if boundaries and h_clean in boundaries:
                is_closed = boundaries[h_clean]
                if not is_closed:
                    return PartHatchResult(
                        status="ERROR",
                        message=f"OPEN_BOUNDARY_LOOP: Entity handle '{h}' is not a closed boundary curve.",
                        hatched_count=0,
                        processed_count=0,
                    )

            hatched_count += 1

        msg = f"Part hatch applied to {hatched_count} boundary curves on layer '{args.layer}'."
        return PartHatchResult("OK", msg, hatched_count, hatched_count)


# ============================================================================
# 2. cadmind-hole-table (HoleTableHandler)
# ============================================================================


class HoleTableHandler:
    """Cleanroom implementation of HoleTableHandler (TierAWave4Handlers.cs)."""

    DEFAULT_COLUMN_WIDTHS: List[float] = [20.0, 30.0, 30.0, 30.0]  # Tag, X, Y, Dia

    def execute(
        self,
        args: HoleTableArgs,
        layer_locks: Optional[Dict[str, bool]] = None,
    ) -> HoleTableResult:
        """Draw structured hole table with 4 columns and coordinates formatting."""
        if not args.rows or len(args.rows) == 0:
            return HoleTableResult(
                status="ERROR",
                message="DEGENERATE_GEOMETRY: Hole table requires at least one row.",
                row_count=0,
                processed_count=0,
            )

        try:
            rh = _validate_finite(args.row_height, "row_height")
            th = _validate_finite(args.text_height, "text_height")
        except DegenerateGeometryError as e:
            return HoleTableResult(
                status="ERROR",
                message=str(e),
                row_count=0,
                processed_count=0,
            )

        if rh <= 1e-4 or th <= 1e-4 or rh <= th:
            return HoleTableResult(
                status="ERROR",
                message="DEGENERATE_GEOMETRY: RowHeight must be strictly greater than TextHeight and both must be positive.",
                row_count=0,
                processed_count=0,
            )

        ox = 0.0
        oy = 0.0
        if args.origin is not None and len(args.origin) >= 2:
            try:
                ox = _validate_finite(args.origin[0], "origin_x")
                oy = _validate_finite(args.origin[1], "origin_y")
            except DegenerateGeometryError as e:
                return HoleTableResult(
                    status="ERROR",
                    message=str(e),
                    row_count=0,
                    processed_count=0,
                )

        locks = layer_locks or {}
        if locks.get(args.layer.strip().lower(), False):
            return HoleTableResult(
                status="ERROR",
                message=f"LOCKED_LAYER: Target layer '{args.layer}' is locked. Transaction rolled back.",
                row_count=0,
                processed_count=0,
            )

        # Build table grid geometry
        col_w = list(self.DEFAULT_COLUMN_WIDTHS)
        total_w = sum(col_w)
        row_count = len(args.rows)
        total_h = (row_count + 1) * rh  # 1 header row + N data rows

        grid_lines: List[LineSegment2D] = []
        # Outer border
        grid_lines.append(LineSegment2D(Point2D(ox, oy), Point2D(ox + total_w, oy)))
        grid_lines.append(LineSegment2D(Point2D(ox + total_w, oy), Point2D(ox + total_w, oy - total_h)))
        grid_lines.append(LineSegment2D(Point2D(ox + total_w, oy - total_h), Point2D(ox, oy - total_h)))
        grid_lines.append(LineSegment2D(Point2D(ox, oy - total_h), Point2D(ox, oy)))

        # Header divider
        grid_lines.append(LineSegment2D(Point2D(ox, oy - rh), Point2D(ox + total_w, oy - rh)))

        # Row dividers
        for r_idx in range(1, row_count):
            curr_y = oy - (r_idx + 1) * rh
            grid_lines.append(LineSegment2D(Point2D(ox, curr_y), Point2D(ox + total_w, curr_y)))

        # Vertical column dividers
        curr_x = ox
        for w in col_w[:-1]:
            curr_x += w
            grid_lines.append(LineSegment2D(Point2D(curr_x, oy), Point2D(curr_x, oy - total_h)))

        # Total entities: top line, headers (4), divider (1), rows * (text 4 + divider 1), vert lines (5)
        processed_count = 1 + 4 + 1 + (row_count * (1 + 4 + 1)) + 5
        msg = f"Placed hole table with {row_count} rows at ({ox:g}, {oy:g}) on layer '{args.layer}'."
        return HoleTableResult("OK", msg, row_count, processed_count, grid_lines)


# ============================================================================
# 3. cadmind-bom-table (BomTableHandler)
# ============================================================================


class BomTableHandler:
    """Cleanroom implementation of BomTableHandler (TierAWave3Handlers.cs)."""

    DEFAULT_COLUMN_WIDTHS: List[float] = [15.0, 60.0, 30.0, 30.0, 15.0, 25.0, 25.0]

    def execute(
        self,
        args: BomTableArgs,
        layer_locks: Optional[Dict[str, bool]] = None,
    ) -> BomTableResult:
        """Draw comprehensive Bill of Materials (BOM) table with total weight calculation."""
        if not args.items or len(args.items) == 0:
            return BomTableResult(
                status="ERROR",
                message="DEGENERATE_GEOMETRY: BOM table requires at least one item.",
                item_count=0,
                total_weight_kg=0.0,
                processed_count=0,
            )

        try:
            rh = _validate_finite(args.row_height, "row_height")
            th = _validate_finite(args.text_height, "text_height")
        except DegenerateGeometryError as e:
            return BomTableResult(
                status="ERROR",
                message=str(e),
                item_count=0,
                total_weight_kg=0.0,
                processed_count=0,
            )

        if rh <= 1e-4 or th <= 1e-4:
            return BomTableResult(
                status="ERROR",
                message="DEGENERATE_GEOMETRY: RowHeight and TextHeight must be positive and non-zero.",
                item_count=0,
                total_weight_kg=0.0,
                processed_count=0,
            )

        if args.insertion_point is None or len(args.insertion_point) < 2:
            return BomTableResult(
                status="ERROR",
                message="DEGENERATE_GEOMETRY: InsertionPoint must be specified with valid [X, Y] coordinates.",
                item_count=0,
                total_weight_kg=0.0,
                processed_count=0,
            )

        try:
            ix = _validate_finite(args.insertion_point[0], "insertion_point_x")
            iy = _validate_finite(args.insertion_point[1], "insertion_point_y")
        except DegenerateGeometryError as e:
            return BomTableResult(
                status="ERROR",
                message=str(e),
                item_count=0,
                total_weight_kg=0.0,
                processed_count=0,
            )

        locks = layer_locks or {}
        if locks.get(args.layer.strip().lower(), False) or locks.get(args.text_layer.strip().lower(), False):
            return BomTableResult(
                status="ERROR",
                message=f"LOCKED_LAYER: Target layer '{args.layer}' is locked. Transaction rolled back.",
                item_count=0,
                total_weight_kg=0.0,
                processed_count=0,
            )

        # Accumulate total weight and validate items
        total_weight = 0.0
        for it in args.items:
            total_weight += it.quantity * it.unit_weight_kg

        col_w = list(args.column_widths or self.DEFAULT_COLUMN_WIDTHS)
        total_w = sum(col_w)
        item_count = len(args.items)
        # 1 title row + 1 header row + N item rows + 1 summary row = (N + 3) rows
        total_rows = item_count + 3
        total_h = total_rows * rh

        grid_lines: List[LineSegment2D] = []
        # Outer border
        grid_lines.append(LineSegment2D(Point2D(ix, iy), Point2D(ix + total_w, iy)))
        grid_lines.append(LineSegment2D(Point2D(ix + total_w, iy), Point2D(ix + total_w, iy - total_h)))
        grid_lines.append(LineSegment2D(Point2D(ix + total_w, iy - total_h), Point2D(ix, iy - total_h)))
        grid_lines.append(LineSegment2D(Point2D(ix, iy - total_h), Point2D(ix, iy)))

        # Dividers
        for r in range(1, total_rows):
            cy = iy - r * rh
            grid_lines.append(LineSegment2D(Point2D(ix, cy), Point2D(ix + total_w, cy)))

        # Vertical dividers (skip title row)
        cx = ix
        for w in col_w[:-1]:
            cx += w
            grid_lines.append(LineSegment2D(Point2D(cx, iy - rh), Point2D(cx, iy - total_h)))

        rounded_weight = round(total_weight, 2)
        # Processed count matching Oracle: Title(1) + Headers(7) + Rows(7*N) + Summary(2) + Borders/Dividers
        processed_count = 1 + 7 + (item_count * 7) + 2 + 1 + item_count + 6

        msg = (
            f"BOM table drawn with {item_count} items (total weight {rounded_weight:.2f} kg) "
            f"on layers '{args.layer}'/'{args.text_layer}'."
        )
        return BomTableResult("OK", msg, item_count, rounded_weight, processed_count, grid_lines)
