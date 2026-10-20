"""cad_agent/cleanroom_electrical_schematics.py.

Batch E2: Electrical Schematics, Lighting Grid, Panel Layout, SLD Feeder, Panel Schedule & Device Symbols.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierBWave19Handlers.cs: LadderDiagramHandler (cadmind-ladder-diagram)
  - TierBWave19Handlers.cs: LightingGridHandler (cadmind-lighting-grid)
  - TierBWave19Handlers.cs: PanelLayoutHandler (cadmind-panel-layout)
  - TierBWave19Handlers.cs: SldFeederHandler (cadmind-sld-feeder)
  - TierAWave6Handlers.cs: PanelScheduleHandler (cadmind-panel-schedule)
  - TierAWave5Handlers.cs: DeviceSymbolHandler (cadmind-device-symbol)

Part of Domain 4 (ELECTRICAL: 19 registered tools).
Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D, CircleIR),
strict IEEE-754 machine-epsilon safety, Banker's rounding parity,
and zero external pip dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from cad_agent.cleanroom_mechanical import CircleIR, LineSegment2D, Point2D

# ============================================================================
# EXCEPTION HIERARCHY
# ============================================================================


class CleanroomError(ValueError):
    """Base exception for cleanroom electrical validation errors."""

    pass


class DegenerateGeometryError(CleanroomError):
    """Raised when geometric or validation parameters violate construction rules."""

    pass


# ============================================================================
# INTERNAL IEEE-754 VALIDATION HELPERS & 2D VECTOR MATH
# ============================================================================


def _validate_finite(val: float, name: str) -> float:
    """Ensure value is finite (not NaN, not Inf)."""
    if not isinstance(val, (int, float)) or isinstance(val, bool) or math.isnan(val) or math.isinf(val):
        raise DegenerateGeometryError(f"INVALID_{name.upper()}: {name} must be positive and finite.")
    return float(val)


def _rotate_vector(vx: float, vy: float, rad: float) -> Point2D:
    """Rotate 2D vector (vx, vy) by rad radians."""
    cos_theta = math.cos(rad)
    sin_theta = math.sin(rad)
    return Point2D(vx * cos_theta - vy * sin_theta, vx * sin_theta + vy * cos_theta)


# ============================================================================
# 1. LADDER DIAGRAM DTOs & HANDLER (cadmind-ladder-diagram)
# ============================================================================


@dataclass(frozen=True)
class LadderDiagramArgs:
    """Arguments matching TierBWave19Contracts.LadderDiagramArgs."""

    origin: Optional[Sequence[float]] = None
    width: float = 200.0
    rungs: int = 1
    spacing: float = 30.0
    numbers: bool = True
    layer: str = "E-SLD"


@dataclass(frozen=True)
class LadderDiagramResult:
    """Result matching TierBWave19Contracts.LadderDiagramResult."""

    status: str
    message: str
    rung_count: int
    width: float
    spacing: float
    has_numbers: bool
    layer: str
    entity_count: int
    created_handles: List[str] = field(default_factory=list)
    lines: List[LineSegment2D] = field(default_factory=list)


class LadderDiagramHandler:
    """Handler for cadmind-ladder-diagram with strict C# parity."""

    def execute(self, args: LadderDiagramArgs) -> LadderDiagramResult:
        if not isinstance(args.rungs, int) or isinstance(args.rungs, bool) or args.rungs <= 0:
            raise DegenerateGeometryError("INVALID_RUNGS: Rungs must be positive.")

        if not isinstance(args.width, (int, float)) or isinstance(args.width, bool) or args.width <= 0.0 or math.isnan(args.width) or math.isinf(args.width):
            raise DegenerateGeometryError("INVALID_WIDTH: Width must be positive and finite.")

        if not isinstance(args.spacing, (int, float)) or isinstance(args.spacing, bool) or args.spacing <= 0.0 or math.isnan(args.spacing) or math.isinf(args.spacing):
            raise DegenerateGeometryError("INVALID_SPACING: Spacing must be positive and finite.")

        ox = float(args.origin[0]) if args.origin and len(args.origin) >= 1 else 0.0
        oy = float(args.origin[1]) if args.origin and len(args.origin) >= 2 else 0.0
        _validate_finite(ox, "ORIGIN_X")
        _validate_finite(oy, "ORIGIN_Y")

        layer = args.layer.strip() if args.layer and args.layer.strip() else "E-SLD"
        handles: List[str] = []
        lines: List[LineSegment2D] = []

        total_height = (args.rungs + 1) * args.spacing

        # Left vertical power rail
        lines.append(LineSegment2D(Point2D(ox, oy), Point2D(ox, oy + total_height)))
        handles.append("LEFT_RAIL")

        # Right vertical power rail
        lines.append(LineSegment2D(Point2D(ox + args.width, oy), Point2D(ox + args.width, oy + total_height)))
        handles.append("RIGHT_RAIL")

        # Horizontal rungs
        for i in range(1, args.rungs + 1):
            ry = oy + (i * args.spacing)
            lines.append(LineSegment2D(Point2D(ox, ry), Point2D(ox + args.width, ry)))
            handles.append(f"RUNG_{i}")

            if args.numbers:
                handles.append(f"RUNG_NUM_{i}")

        entity_count = len(handles)
        msg = f"Created control ladder with {args.rungs} rungs and {entity_count} entities on layer '{layer}'."

        return LadderDiagramResult(
            status="SUCCESS",
            message=msg,
            rung_count=args.rungs,
            width=float(args.width),
            spacing=float(args.spacing),
            has_numbers=bool(args.numbers),
            layer=layer,
            entity_count=entity_count,
            created_handles=handles,
            lines=lines,
        )


# ============================================================================
# 2. LIGHTING GRID DTOs & HANDLER (cadmind-lighting-grid)
# ============================================================================


@dataclass(frozen=True)
class LightingGridArgs:
    """Arguments matching TierBWave19Contracts.LightingGridArgs."""

    origin: Optional[Sequence[float]] = None
    width: float = 6000.0
    height: float = 4000.0
    rows: int = 2
    cols: int = 3
    fixture: str = "troffer"
    size: float = 300.0
    layer: str = "E-LITE"


@dataclass(frozen=True)
class LightingGridResult:
    """Result matching TierBWave19Contracts.LightingGridResult."""

    status: str
    message: str
    fixture_count: int
    rows: int
    cols: int
    fixture: str
    size: float
    layer: str
    entity_count: int
    centers: List[List[float]] = field(default_factory=list)
    created_handles: List[str] = field(default_factory=list)
    lines: List[LineSegment2D] = field(default_factory=list)
    circles: List[CircleIR] = field(default_factory=list)


class LightingGridHandler:
    """Handler for cadmind-lighting-grid with strict C# parity."""

    def execute(self, args: LightingGridArgs) -> LightingGridResult:
        if not isinstance(args.width, (int, float)) or isinstance(args.width, bool) or args.width <= 0.0 or math.isnan(args.width) or math.isinf(args.width):
            raise DegenerateGeometryError("INVALID_WIDTH: Width must be positive and finite.")

        if not isinstance(args.height, (int, float)) or isinstance(args.height, bool) or args.height <= 0.0 or math.isnan(args.height) or math.isinf(args.height):
            raise DegenerateGeometryError("INVALID_HEIGHT: Height must be positive and finite.")

        if not isinstance(args.rows, int) or isinstance(args.rows, bool) or args.rows <= 0:
            raise DegenerateGeometryError("INVALID_ROWS: Rows must be positive.")

        if not isinstance(args.cols, int) or isinstance(args.cols, bool) or args.cols <= 0:
            raise DegenerateGeometryError("INVALID_COLS: Cols must be positive.")

        if not isinstance(args.size, (int, float)) or isinstance(args.size, bool) or args.size <= 0.0 or math.isnan(args.size) or math.isinf(args.size):
            raise DegenerateGeometryError("INVALID_SIZE: Size must be positive and finite.")

        fixture_type = args.fixture.strip().lower() if args.fixture and args.fixture.strip() else "troffer"
        if fixture_type not in ("troffer", "downlight"):
            raise DegenerateGeometryError("INVALID_FIXTURE: Fixture must be 'troffer' or 'downlight'.")

        ox = float(args.origin[0]) if args.origin and len(args.origin) >= 1 else 0.0
        oy = float(args.origin[1]) if args.origin and len(args.origin) >= 2 else 0.0
        _validate_finite(ox, "ORIGIN_X")
        _validate_finite(oy, "ORIGIN_Y")

        layer = args.layer.strip() if args.layer and args.layer.strip() else "E-LITE"
        dx = args.width / args.cols
        dy = args.height / args.rows

        centers: List[List[float]] = []
        handles: List[str] = []
        lines: List[LineSegment2D] = []
        circles: List[CircleIR] = []

        fixture_idx = 0
        for r in range(args.rows):
            for c in range(args.cols):
                fixture_idx += 1
                cx = ox + (c + 0.5) * dx
                cy = oy + (r + 0.5) * dy
                centers.append([cx, cy])

                if fixture_type == "troffer":
                    # Troffer: rectangle + diagonal X
                    hw = min(args.size / 2.0, dx * 0.45)
                    hh = min(args.size / 4.0, dy * 0.45)

                    # 4 segments of rectangle
                    p0 = Point2D(cx - hw, cy - hh)
                    p1 = Point2D(cx + hw, cy - hh)
                    p2 = Point2D(cx + hw, cy + hh)
                    p3 = Point2D(cx - hw, cy + hh)
                    lines.append(LineSegment2D(p0, p1))
                    lines.append(LineSegment2D(p1, p2))
                    lines.append(LineSegment2D(p2, p3))
                    lines.append(LineSegment2D(p3, p0))
                    handles.append(f"TROFFER_BOX_{fixture_idx}")

                    # Cross diagonals
                    lines.append(LineSegment2D(p0, p2))
                    handles.append(f"TROFFER_DIAG1_{fixture_idx}")
                    lines.append(LineSegment2D(p3, p1))
                    handles.append(f"TROFFER_DIAG2_{fixture_idx}")
                else:
                    # Downlight: circle + cross
                    rad = min(args.size / 2.0, min(dx, dy) * 0.4)
                    circles.append(CircleIR(Point2D(cx, cy), rad, index=fixture_idx))
                    handles.append(f"DOWNLIGHT_CIRC_{fixture_idx}")

                    # Horizontal tick
                    lines.append(LineSegment2D(Point2D(cx - rad, cy), Point2D(cx + rad, cy)))
                    handles.append(f"DOWNLIGHT_HTICK_{fixture_idx}")

                    # Vertical tick
                    lines.append(LineSegment2D(Point2D(cx, cy - rad), Point2D(cx, cy + rad)))
                    handles.append(f"DOWNLIGHT_VTICK_{fixture_idx}")

        total_fixtures = args.rows * args.cols
        entity_count = len(handles)
        msg = f"Created lighting grid with {total_fixtures} fixtures ({args.rows}x{args.cols}) on layer '{layer}'."

        return LightingGridResult(
            status="SUCCESS",
            message=msg,
            fixture_count=total_fixtures,
            rows=args.rows,
            cols=args.cols,
            fixture=fixture_type,
            size=float(args.size),
            layer=layer,
            entity_count=entity_count,
            centers=centers,
            created_handles=handles,
            lines=lines,
            circles=circles,
        )


# ============================================================================
# 3. PANEL LAYOUT DTOs & HANDLER (cadmind-panel-layout)
# ============================================================================


@dataclass(frozen=True)
class PanelLayoutArgs:
    """Arguments matching TierBWave19Contracts.PanelLayoutArgs."""

    origin: Optional[Sequence[float]] = None
    width: float = 600.0
    height: float = 800.0
    rows: int = 12
    cols: int = 2
    label: Optional[str] = None
    layer: str = "E-PANEL"


@dataclass(frozen=True)
class PanelLayoutResult:
    """Result matching TierBWave19Contracts.PanelLayoutResult."""

    status: str
    message: str
    width: float
    height: float
    rows: int
    cols: int
    total_slots: int
    label: Optional[str]
    layer: str
    entity_count: int
    created_handles: List[str] = field(default_factory=list)
    lines: List[LineSegment2D] = field(default_factory=list)


class PanelLayoutHandler:
    """Handler for cadmind-panel-layout with strict C# parity."""

    def execute(self, args: PanelLayoutArgs) -> PanelLayoutResult:
        if not isinstance(args.width, (int, float)) or isinstance(args.width, bool) or args.width <= 0.0 or math.isnan(args.width) or math.isinf(args.width):
            raise DegenerateGeometryError("INVALID_WIDTH: Width must be positive and finite.")

        if not isinstance(args.height, (int, float)) or isinstance(args.height, bool) or args.height <= 0.0 or math.isnan(args.height) or math.isinf(args.height):
            raise DegenerateGeometryError("INVALID_HEIGHT: Height must be positive and finite.")

        if not isinstance(args.rows, int) or isinstance(args.rows, bool) or args.rows <= 0:
            raise DegenerateGeometryError("INVALID_ROWS: Rows must be positive.")

        if not isinstance(args.cols, int) or isinstance(args.cols, bool) or args.cols <= 0:
            raise DegenerateGeometryError("INVALID_COLS: Cols must be positive.")

        ox = float(args.origin[0]) if args.origin and len(args.origin) >= 1 else 0.0
        oy = float(args.origin[1]) if args.origin and len(args.origin) >= 2 else 0.0
        _validate_finite(ox, "ORIGIN_X")
        _validate_finite(oy, "ORIGIN_Y")

        layer = args.layer.strip() if args.layer and args.layer.strip() else "E-PANEL"
        handles: List[str] = []
        lines: List[LineSegment2D] = []

        # Outer enclosure
        p0 = Point2D(ox, oy)
        p1 = Point2D(ox + args.width, oy)
        p2 = Point2D(ox + args.width, oy + args.height)
        p3 = Point2D(ox, oy + args.height)
        lines.append(LineSegment2D(p0, p1))
        lines.append(LineSegment2D(p1, p2))
        lines.append(LineSegment2D(p2, p3))
        lines.append(LineSegment2D(p3, p0))
        handles.append("PANEL_ENCLOSURE")

        available_height = args.height

        # Title strip if label provided
        if args.label and args.label.strip():
            title_h = min(args.height * 0.12, 60.0)
            title_line_y = oy + args.height - title_h

            lines.append(LineSegment2D(Point2D(ox, title_line_y), Point2D(ox + args.width, title_line_y)))
            handles.append("PANEL_TITLE_DIVIDER")
            handles.append("PANEL_TITLE_TEXT")

            available_height = args.height - title_h

        # Grid of breaker slots
        margin_x = args.width * 0.08
        margin_y = available_height * 0.06
        usable_w = args.width - (2.0 * margin_x)
        usable_h = available_height - (2.0 * margin_y)

        cell_w = usable_w / args.cols
        cell_h = usable_h / args.rows

        gap_x = cell_w * 0.15
        gap_y = cell_h * 0.15
        slot_w = cell_w - gap_x
        slot_h = cell_h - gap_y

        total_slots = args.rows * args.cols
        slot_idx = 0

        for r in range(args.rows):
            for c in range(args.cols):
                slot_idx += 1
                sx = ox + margin_x + (c * cell_w) + (gap_x / 2.0)
                sy = oy + margin_y + (r * cell_h) + (gap_y / 2.0)

                sp0 = Point2D(sx, sy)
                sp1 = Point2D(sx + slot_w, sy)
                sp2 = Point2D(sx + slot_w, sy + slot_h)
                sp3 = Point2D(sx, sy + slot_h)

                lines.append(LineSegment2D(sp0, sp1))
                lines.append(LineSegment2D(sp1, sp2))
                lines.append(LineSegment2D(sp2, sp3))
                lines.append(LineSegment2D(sp3, sp0))
                handles.append(f"BREAKER_SLOT_{slot_idx}")

        entity_count = len(handles)
        msg = f"Created panelboard layout with {total_slots} breaker slots and {entity_count} entities on layer '{layer}'."

        return PanelLayoutResult(
            status="SUCCESS",
            message=msg,
            width=float(args.width),
            height=float(args.height),
            rows=args.rows,
            cols=args.cols,
            total_slots=total_slots,
            label=args.label.strip() if args.label and args.label.strip() else None,
            layer=layer,
            entity_count=entity_count,
            created_handles=handles,
            lines=lines,
        )


# ============================================================================
# 4. SLD FEEDER DTOs & HANDLER (cadmind-sld-feeder)
# ============================================================================


@dataclass(frozen=True)
class SldFeederLoad:
    """Feeder load matching TierBWave19Contracts.SldFeederLoad."""

    tag: str
    rating: Optional[str] = None


@dataclass(frozen=True)
class SldFeederArgs:
    """Arguments matching TierBWave19Contracts.SldFeederArgs."""

    origin: Optional[Sequence[float]] = None
    loads: Optional[Sequence[SldFeederLoad]] = None
    spacing: float = 300.0
    drop: float = 400.0
    layer: str = "E-SLD"


@dataclass(frozen=True)
class SldFeederResult:
    """Result matching TierBWave19Contracts.SldFeederResult."""

    status: str
    message: str
    feeder_count: int
    spacing: float
    drop: float
    layer: str
    entity_count: int
    created_handles: List[str] = field(default_factory=list)
    lines: List[LineSegment2D] = field(default_factory=list)


class SldFeederHandler:
    """Handler for cadmind-sld-feeder with strict C# parity."""

    def execute(self, args: SldFeederArgs) -> SldFeederResult:
        if args.loads is None or len(args.loads) == 0:
            raise DegenerateGeometryError("MISSING_LOADS: Loads must contain at least one feeder load item.")

        for ld in args.loads:
            if not ld or not ld.tag or not ld.tag.strip():
                raise DegenerateGeometryError("INVALID_LOAD_TAG: Each load must have a non-empty tag.")

        if not isinstance(args.spacing, (int, float)) or isinstance(args.spacing, bool) or args.spacing <= 0.0 or math.isnan(args.spacing) or math.isinf(args.spacing):
            raise DegenerateGeometryError("INVALID_SPACING: Spacing must be positive and finite.")

        if not isinstance(args.drop, (int, float)) or isinstance(args.drop, bool) or args.drop <= 0.0 or math.isnan(args.drop) or math.isinf(args.drop):
            raise DegenerateGeometryError("INVALID_DROP: Drop must be positive and finite.")

        ox = float(args.origin[0]) if args.origin and len(args.origin) >= 1 else 0.0
        oy = float(args.origin[1]) if args.origin and len(args.origin) >= 2 else 0.0
        _validate_finite(ox, "ORIGIN_X")
        _validate_finite(oy, "ORIGIN_Y")

        layer = args.layer.strip() if args.layer and args.layer.strip() else "E-SLD"
        handles: List[str] = []
        lines: List[LineSegment2D] = []

        # Main bus line
        bus_length = (len(args.loads) + 1) * args.spacing
        lines.append(LineSegment2D(Point2D(ox, oy), Point2D(ox + bus_length, oy)))
        handles.append("SLD_MAIN_BUS")

        box_w = min(args.spacing * 0.25, 40.0)
        box_h = min(args.drop * 0.12, 30.0)

        for i, ld in enumerate(args.loads):
            fx = ox + ((i + 1) * args.spacing)

            # Feeder drop line
            lines.append(LineSegment2D(Point2D(fx, oy), Point2D(fx, oy - args.drop)))
            handles.append(f"SLD_DROP_{i + 1}")

            # Breaker box at 40% down the drop
            cy = oy - (args.drop * 0.4)
            bp0 = Point2D(fx - (box_w / 2.0), cy - (box_h / 2.0))
            bp1 = Point2D(fx + (box_w / 2.0), cy - (box_h / 2.0))
            bp2 = Point2D(fx + (box_w / 2.0), cy + (box_h / 2.0))
            bp3 = Point2D(fx - (box_w / 2.0), cy + (box_h / 2.0))

            lines.append(LineSegment2D(bp0, bp1))
            lines.append(LineSegment2D(bp1, bp2))
            lines.append(LineSegment2D(bp2, bp3))
            lines.append(LineSegment2D(bp3, bp0))
            handles.append(f"SLD_BOX_{i + 1}")

            # Tag text
            handles.append(f"SLD_TAG_{i + 1}")

            # Rating text if provided
            if ld.rating and ld.rating.strip():
                handles.append(f"SLD_RATE_{i + 1}")

        entity_count = len(handles)
        msg = f"Created single-line diagram with {len(args.loads)} feeder drops and {entity_count} entities on layer '{layer}'."

        return SldFeederResult(
            status="SUCCESS",
            message=msg,
            feeder_count=len(args.loads),
            spacing=float(args.spacing),
            drop=float(args.drop),
            layer=layer,
            entity_count=entity_count,
            created_handles=handles,
            lines=lines,
        )


# ============================================================================
# 5. PANEL SCHEDULE DTOs & HANDLER (cadmind-panel-schedule)
# ============================================================================


@dataclass(frozen=True)
class CircuitScheduleItem:
    """Item matching TierAWave6Contracts.CircuitScheduleItem."""

    desc: str = ""
    load: float = 0.0
    trip: str = "20A"
    phase: Optional[str] = None


@dataclass(frozen=True)
class PanelScheduleArgs:
    """Arguments matching TierAWave6Contracts.PanelScheduleArgs."""

    origin: Optional[Sequence[float]] = None
    title: str = "PANEL SCHEDULE"
    circuits: Optional[Sequence[CircuitScheduleItem]] = None
    phases: int = 3
    height: float = 2.5
    layer: str = "E-TABLE"


@dataclass(frozen=True)
class PanelScheduleResult:
    """Result matching TierAWave6Contracts.PanelScheduleResult."""

    status: str
    message: str
    title: str
    circuit_count: int
    total_load_va: float
    processed_count: int
    lines: List[LineSegment2D] = field(default_factory=list)


class PanelScheduleHandler:
    """Handler for cadmind-panel-schedule with strict C# parity."""

    def execute(self, args: PanelScheduleArgs) -> PanelScheduleResult:
        title = args.title.strip() if args.title and args.title.strip() else "PANEL SCHEDULE"

        if args.circuits is None or len(args.circuits) == 0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Panel schedule requires at least one circuit entry.")

        if not isinstance(args.height, (int, float)) or isinstance(args.height, bool) or args.height <= 1e-4 or math.isnan(args.height) or math.isinf(args.height):
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Text height must be positive and non-zero.")

        ox = 0.0
        oy = 0.0
        if args.origin is not None and len(args.origin) >= 2:
            if math.isnan(args.origin[0]) or math.isnan(args.origin[1]) or math.isinf(args.origin[0]) or math.isinf(args.origin[1]):
                raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Origin coordinates must be finite numbers.")
            ox = float(args.origin[0])
            oy = float(args.origin[1])

        col_widths = [18.0, 50.0, 20.0, 16.0, 26.0]  # CKT, DESC, TRIP, PHASE, LOAD
        total_width = sum(col_widths)
        r_height = max(7.0, args.height * 2.8)

        total_entities = 0
        lines: List[LineSegment2D] = []
        cur_y = oy

        # 1. Top border
        lines.append(LineSegment2D(Point2D(ox, cur_y), Point2D(ox + total_width, cur_y)))
        total_entities += 1

        # 2. Title band
        cur_y -= r_height
        lines.append(LineSegment2D(Point2D(ox, cur_y), Point2D(ox + total_width, cur_y)))
        total_entities += 2  # line + title text

        # 3. Header row
        cur_y -= r_height
        lines.append(LineSegment2D(Point2D(ox, cur_y), Point2D(ox + total_width, cur_y)))
        total_entities += 1 + 5  # line + 5 column header texts

        # 4. Circuit rows
        total_load = 0.0
        for _ckt in args.circuits:
            cur_y -= r_height
            lines.append(LineSegment2D(Point2D(ox, cur_y), Point2D(ox + total_width, cur_y)))
            total_load += float(_ckt.load)
            total_entities += 1 + 5  # line + 5 cell texts

        # 5. Total row
        cur_y -= r_height
        lines.append(LineSegment2D(Point2D(ox, cur_y), Point2D(ox + total_width, cur_y)))
        total_entities += 1 + 2  # line + TOTAL label + total value text

        # 6. Vertical gridlines (from top border to bottom of total row)
        bottom_y = cur_y
        col_x = ox
        # Left outer border
        lines.append(LineSegment2D(Point2D(col_x, oy), Point2D(col_x, bottom_y)))
        total_entities += 1

        for w in col_widths:
            col_x += w
            lines.append(LineSegment2D(Point2D(col_x, oy - r_height), Point2D(col_x, bottom_y)))
            total_entities += 1

        msg = f"Created panel schedule '{title}' with {len(args.circuits)} circuits, total load {total_load:.1f} VA."

        return PanelScheduleResult(
            status="SUCCESS",
            message=msg,
            title=title,
            circuit_count=len(args.circuits),
            total_load_va=total_load,
            processed_count=total_entities,
            lines=lines,
        )


# ============================================================================
# 6. DEVICE SYMBOL DTOs & HANDLER (cadmind-device-symbol)
# ============================================================================


@dataclass(frozen=True)
class DeviceSymbolArgs:
    """Arguments matching TierAWave5Contracts.DeviceSymbolArgs."""

    points: Optional[Sequence[Sequence[float]]] = None
    type: str = "receptacle"
    size: float = 2.5
    rotation: float = 0.0
    layer: str = "E-POWER"


@dataclass(frozen=True)
class DeviceSymbolResult:
    """Result matching TierAWave5Contracts.DeviceSymbolResult."""

    status: str
    message: str
    symbol_type: str
    placed_count: int
    processed_count: int
    lines: List[LineSegment2D] = field(default_factory=list)
    circles: List[CircleIR] = field(default_factory=list)


class DeviceSymbolHandler:
    """Handler for cadmind-device-symbol with strict C# parity."""

    VALID_TYPES = {"receptacle", "switch", "light", "motor", "junction", "ground"}

    def execute(self, args: DeviceSymbolArgs) -> DeviceSymbolResult:
        if args.points is None or len(args.points) == 0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Device symbol requires at least one point.")

        if not isinstance(args.size, (int, float)) or isinstance(args.size, bool) or args.size <= 1e-4 or math.isnan(args.size) or math.isinf(args.size):
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Symbol size must be positive and non-zero.")

        stype = args.type.strip().lower() if args.type and args.type.strip() else "receptacle"
        if stype not in self.VALID_TYPES:
            raise DegenerateGeometryError(
                f"DEGENERATE_GEOMETRY: Invalid symbol type '{args.type}'. Supported types: receptacle, switch, light, motor, junction, ground."
            )

        valid_pts: List[Point2D] = []
        for pt in args.points:
            if pt is None or len(pt) < 2 or not isinstance(pt[0], (int, float)) or isinstance(pt[0], bool) or not isinstance(pt[1], (int, float)) or isinstance(pt[1], bool) or math.isnan(pt[0]) or math.isinf(pt[0]) or math.isnan(pt[1]) or math.isinf(pt[1]):
                raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Invalid or non-finite coordinate points.")
            valid_pts.append(Point2D(float(pt[0]), float(pt[1])))

        rad = (args.rotation % 360.0) * math.pi / 180.0
        total_entities = 0
        lines: List[LineSegment2D] = []
        circles: List[CircleIR] = []

        for p_idx, pt in enumerate(valid_pts):
            cx, cy = pt.x, pt.y

            if stype == "receptacle":
                # Circle + 2 parallel prong lines
                circles.append(CircleIR(Point2D(cx, cy), args.size, index=p_idx + 1))
                v1_s = _rotate_vector(-args.size * 0.4, 0.0, rad)
                v1_e = _rotate_vector(-args.size * 0.4, args.size * 1.5, rad)
                lines.append(LineSegment2D(Point2D(cx + v1_s.x, cy + v1_s.y), Point2D(cx + v1_e.x, cy + v1_e.y)))

                v2_s = _rotate_vector(args.size * 0.4, 0.0, rad)
                v2_e = _rotate_vector(args.size * 0.4, args.size * 1.5, rad)
                lines.append(LineSegment2D(Point2D(cx + v2_s.x, cy + v2_s.y), Point2D(cx + v2_e.x, cy + v2_e.y)))
                total_entities += 3

            elif stype == "switch":
                # Small circle + arm line at 45 deg
                circles.append(CircleIR(Point2D(cx, cy), args.size * 0.4, index=p_idx + 1))
                arm_s = _rotate_vector(args.size * 0.28, args.size * 0.28, rad)
                arm_e = _rotate_vector(args.size * 1.4, args.size * 1.4, rad)
                lines.append(LineSegment2D(Point2D(cx + arm_s.x, cy + arm_s.y), Point2D(cx + arm_e.x, cy + arm_e.y)))
                total_entities += 2

            elif stype == "light":
                # Circle + inscribed diagonal cross
                circles.append(CircleIR(Point2D(cx, cy), args.size, index=p_idx + 1))
                offset = args.size * 0.707
                x1_s = _rotate_vector(-offset, -offset, rad)
                x1_e = _rotate_vector(offset, offset, rad)
                lines.append(LineSegment2D(Point2D(cx + x1_s.x, cy + x1_s.y), Point2D(cx + x1_e.x, cy + x1_e.y)))

                x2_s = _rotate_vector(-offset, offset, rad)
                x2_e = _rotate_vector(offset, -offset, rad)
                lines.append(LineSegment2D(Point2D(cx + x2_s.x, cy + x2_s.y), Point2D(cx + x2_e.x, cy + x2_e.y)))
                total_entities += 3

            elif stype == "motor":
                # Circle + letter 'M' text
                circles.append(CircleIR(Point2D(cx, cy), args.size, index=p_idx + 1))
                total_entities += 2  # circle + text

            elif stype == "junction":
                # Simple junction box circle
                circles.append(CircleIR(Point2D(cx, cy), args.size * 0.6, index=p_idx + 1))
                total_entities += 1

            elif stype == "ground":
                # Vertical lead down to 3 horizontal stepping bars
                g_top = _rotate_vector(0.0, args.size, rad)
                lines.append(LineSegment2D(Point2D(cx + g_top.x, cy + g_top.y), Point2D(cx, cy)))

                b1_s = _rotate_vector(-args.size * 0.8, 0.0, rad)
                b1_e = _rotate_vector(args.size * 0.8, 0.0, rad)
                lines.append(LineSegment2D(Point2D(cx + b1_s.x, cy + b1_s.y), Point2D(cx + b1_e.x, cy + b1_e.y)))

                b2_s = _rotate_vector(-args.size * 0.5, -args.size * 0.3, rad)
                b2_e = _rotate_vector(args.size * 0.5, -args.size * 0.3, rad)
                lines.append(LineSegment2D(Point2D(cx + b2_s.x, cy + b2_s.y), Point2D(cx + b2_e.x, cy + b2_e.y)))

                b3_s = _rotate_vector(-args.size * 0.2, -args.size * 0.6, rad)
                b3_e = _rotate_vector(args.size * 0.2, -args.size * 0.6, rad)
                lines.append(LineSegment2D(Point2D(cx + b3_s.x, cy + b3_s.y), Point2D(cx + b3_e.x, cy + b3_e.y)))
                total_entities += 4

        msg = f"Placed {len(valid_pts)} '{stype}' device symbols."

        return DeviceSymbolResult(
            status="SUCCESS",
            message=msg,
            symbol_type=stype,
            placed_count=len(valid_pts),
            processed_count=total_entities,
            lines=lines,
            circles=circles,
        )
