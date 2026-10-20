"""cad_agent/cleanroom_electrical_calculations.py.

Batch E3: Electrical Calculations, Raceway Routing, Home Runs, Wire Tags & Symbol Legend.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierBWave20Handlers.cs: VoltageDropHandler (cadmind-voltage-drop)
  - TierBWave20Handlers.cs: WireSizingHandler (cadmind-wire-sizing)
  - TierBWave20Handlers.cs: BreakerSelectHandler (cadmind-breaker-select)
  - TierBWave20Handlers.cs: RacewayRunHandler (cadmind-raceway-run)
  - TierBWave20Handlers.cs: HomeRunHandler (cadmind-home-run)
  - TierAWave4Handlers.cs: WireTagHandler (cadmind-wire-tag)
  - TierAWave5Handlers.cs: SymbolLegendHandler (cadmind-symbol-legend)

Final batch of Domain 4 (ELECTRICAL) completing all 19 tools and the entire 90-tool master suite!
Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D, CircleIR),
strict IEEE-754 machine-epsilon safety, Banker's rounding parity,
and zero external pip dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from cad_agent.cleanroom_electrical_schematics import DeviceSymbolHandler
from cad_agent.cleanroom_mechanical import CircleIR, LineSegment2D, Point2D

# ============================================================================
# EXCEPTION HIERARCHY
# ============================================================================


class CleanroomError(ValueError):
    """Base exception for cleanroom electrical calculation errors."""

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
        raise DegenerateGeometryError(f"INVALID_{name.upper()}: {name} must be positive and finite.")
    return float(val)


# ============================================================================
# 1. VOLTAGE DROP DTOs & HANDLER (cadmind-voltage-drop)
# ============================================================================


@dataclass(frozen=True)
class VoltageDropArgs:
    """Arguments matching TierBWave20Contracts.VoltageDropArgs."""

    current: float = 10.0
    length: float = 50.0
    area: float = 2.5
    phase: int = 3
    voltage: Optional[float] = None
    material: str = "copper"
    limit: float = 5.0


@dataclass(frozen=True)
class VoltageDropResult:
    """Result matching TierBWave20Contracts.VoltageDropResult."""

    status: str
    message: str
    current: float
    length: float
    area: float
    phase: int
    voltage: float
    material: str
    drop_volts: float
    drop_percent: float
    limit_percent: float
    pass_: bool
    resistance: float
    standard: str
    disclaimer: str


class VoltageDropHandler:
    """Handler for cadmind-voltage-drop with strict C# parity."""

    def execute(self, args: VoltageDropArgs) -> VoltageDropResult:
        if not isinstance(args.current, (int, float)) or isinstance(args.current, bool) or args.current <= 0.0 or math.isnan(args.current) or math.isinf(args.current):
            raise DegenerateGeometryError("INVALID_CURRENT: Current must be positive and finite.")

        if not isinstance(args.length, (int, float)) or isinstance(args.length, bool) or args.length <= 0.0 or math.isnan(args.length) or math.isinf(args.length):
            raise DegenerateGeometryError("INVALID_LENGTH: Length must be positive and finite.")

        if not isinstance(args.area, (int, float)) or isinstance(args.area, bool) or args.area <= 0.0 or math.isnan(args.area) or math.isinf(args.area):
            raise DegenerateGeometryError("INVALID_AREA: Area must be positive and finite.")

        if args.phase not in (1, 3):
            raise DegenerateGeometryError("INVALID_PHASE: Phase must be either 1 or 3.")

        if not isinstance(args.limit, (int, float)) or isinstance(args.limit, bool) or args.limit <= 0.0 or math.isnan(args.limit) or math.isinf(args.limit):
            raise DegenerateGeometryError("INVALID_LIMIT: Limit percentage must be positive and finite.")

        if args.voltage is not None and (not isinstance(args.voltage, (int, float)) or isinstance(args.voltage, bool) or args.voltage <= 0.0 or math.isnan(args.voltage) or math.isinf(args.voltage)):
            raise DegenerateGeometryError("INVALID_VOLTAGE: Voltage must be positive and finite.")

        raw_mat = args.material.strip().lower() if args.material and args.material.strip() else "copper"
        if raw_mat in ("copper", "cu"):
            rho = 0.0214  # ohm.mm2/m at 75C per IEC 60364-5-52
            canonical_mat = "copper"
        elif raw_mat in ("aluminium", "aluminum", "al"):
            rho = 0.0353  # ohm.mm2/m at 75C per IEC 60364-5-52
            canonical_mat = "aluminium"
        else:
            raise DegenerateGeometryError(
                f"UNSUPPORTED_MATERIAL: Conductor material '{args.material}' is not supported. Only copper and aluminium are supported."
            )

        k = 2.0 if args.phase == 1 else math.sqrt(3.0)
        v_nom = float(args.voltage) if args.voltage is not None else (230.0 if args.phase == 1 else 400.0)

        # Vdrop = k * I * L * rho / A
        v_drop = k * args.current * args.length * rho / args.area
        drop_percent = (v_drop / v_nom) * 100.0
        pass_result = bool(drop_percent <= args.limit)
        resistance = args.length * rho / args.area

        msg = (
            f"Voltage drop calculated: {v_drop:.2f} V ({drop_percent:.2f}%) - "
            f"{'PASS' if pass_result else 'FAIL'} against {args.limit:.1f}% limit."
        )

        return VoltageDropResult(
            status="SUCCESS",
            message=msg,
            current=float(args.current),
            length=float(args.length),
            area=float(args.area),
            phase=args.phase,
            voltage=v_nom,
            material=canonical_mat,
            drop_volts=round(v_drop, 3),
            drop_percent=round(drop_percent, 2),
            limit_percent=float(args.limit),
            pass_=pass_result,
            resistance=round(resistance, 4),
            standard="Cleanroom Ohm-Resistive Model (IEC 60364-5-52)",
            disclaimer="Informational calculation only. Independent engineering verification required.",
        )


# ============================================================================
# 2. WIRE SIZING DTOs & HANDLER (cadmind-wire-sizing)
# ============================================================================


@dataclass(frozen=True)
class WireAmpacityItem:
    """Wire ampacity entry matching TierBWave20Contracts.WireAmpacityItem."""

    size: float
    ampacity: float


@dataclass(frozen=True)
class WireSizingArgs:
    """Arguments matching TierBWave20Contracts.WireSizingArgs."""

    current: float = 16.0
    derating: float = 1.0
    table: Optional[Sequence[WireAmpacityItem]] = None
    loaded_conductors: int = 2


@dataclass(frozen=True)
class WireSizingResult:
    """Result matching TierBWave20Contracts.WireSizingResult."""

    status: str
    message: str
    design_current: float
    derating: float
    required_ampacity: float
    selected_size: float
    selected_ampacity: float
    spare_margin: float
    next_size_up: Optional[float]
    next_ampacity: Optional[float]
    standard: str
    disclaimer: str


class WireSizingHandler:
    """Handler for cadmind-wire-sizing with strict C# parity."""

    # IEC 60364-5-52:2009 Table B.52.2: Method C, Copper, PVC (70C), 2 loaded conductors
    DEFAULT_TABLE_2_LOADED = [
        WireAmpacityItem(1.5, 19.5),
        WireAmpacityItem(2.5, 27.0),
        WireAmpacityItem(4.0, 36.0),
        WireAmpacityItem(6.0, 46.0),
        WireAmpacityItem(10.0, 63.0),
        WireAmpacityItem(16.0, 85.0),
        WireAmpacityItem(25.0, 112.0),
        WireAmpacityItem(35.0, 138.0),
        WireAmpacityItem(50.0, 168.0),
        WireAmpacityItem(70.0, 213.0),
        WireAmpacityItem(95.0, 258.0),
        WireAmpacityItem(120.0, 299.0),
        WireAmpacityItem(150.0, 344.0),
        WireAmpacityItem(185.0, 392.0),
        WireAmpacityItem(240.0, 461.0),
        WireAmpacityItem(300.0, 530.0),
    ]

    # IEC 60364-5-52:2009 Table B.52.4: Method C, Copper, PVC (70C), 3 loaded conductors
    DEFAULT_TABLE_3_LOADED = [
        WireAmpacityItem(1.5, 17.5),
        WireAmpacityItem(2.5, 24.0),
        WireAmpacityItem(4.0, 32.0),
        WireAmpacityItem(6.0, 41.0),
        WireAmpacityItem(10.0, 57.0),
        WireAmpacityItem(16.0, 76.0),
        WireAmpacityItem(25.0, 96.0),
        WireAmpacityItem(35.0, 119.0),
        WireAmpacityItem(50.0, 144.0),
        WireAmpacityItem(70.0, 184.0),
        WireAmpacityItem(95.0, 223.0),
        WireAmpacityItem(120.0, 259.0),
        WireAmpacityItem(150.0, 299.0),
        WireAmpacityItem(185.0, 341.0),
        WireAmpacityItem(240.0, 403.0),
        WireAmpacityItem(300.0, 464.0),
    ]

    def execute(self, args: WireSizingArgs) -> WireSizingResult:
        if not isinstance(args.current, (int, float)) or isinstance(args.current, bool) or args.current <= 0.0 or math.isnan(args.current) or math.isinf(args.current):
            raise DegenerateGeometryError("INVALID_CURRENT: Current must be positive and finite.")

        if not isinstance(args.derating, (int, float)) or isinstance(args.derating, bool) or args.derating <= 0.0 or args.derating > 1.0 or math.isnan(args.derating) or math.isinf(args.derating):
            raise DegenerateGeometryError("INVALID_DERATING: Derating factor must be in range (0, 1].")

        if args.loaded_conductors not in (2, 3):
            raise DegenerateGeometryError(
                f"INVALID_LOADED_CONDUCTORS: LoadedConductors must be 2 (single-phase/DC) or 3 (three-phase), got {args.loaded_conductors}."
            )

        using_custom_table = args.table is not None and len(args.table) > 0
        if using_custom_table:
            table = [
                t for t in args.table  # type: ignore
                if t.size > 0.0 and t.ampacity > 0.0 and not math.isnan(t.size) and not math.isnan(t.ampacity)
            ]
            table.sort(key=lambda t: t.ampacity)
            if len(table) == 0:
                raise DegenerateGeometryError("INVALID_TABLE: Custom Table contains no valid positive entries.")
            standard = "User-Supplied External Ampacity Data (Uncertified)"
            disclaimer = "Externally supplied ampacity data. NOT certified against IEC 60364 normative tables. Independent engineering verification required."
        else:
            if args.loaded_conductors == 3:
                table = self.DEFAULT_TABLE_3_LOADED
                standard = "IEC 60364-5-52:2009 Table B.52.4 (Method C, Copper/PVC 70°C, 3 Loaded Conductors)"
                disclaimer = "Sized for 3 loaded conductors (three-phase circuits) per IEC 60364-5-52 Table B.52.4. Independent engineering verification required."
            else:
                table = self.DEFAULT_TABLE_2_LOADED
                standard = "IEC 60364-5-52:2009 Table B.52.2 (Method C, Copper/PVC 70°C, 2 Loaded Conductors)"
                disclaimer = "Sized for 2 loaded conductors (single-phase/DC circuits) per IEC 60364-5-52 Table B.52.2. For three-phase circuits, specify LoadedConductors=3. Independent engineering verification required."

        required_ampacity = args.current / args.derating

        match_idx = -1
        for i, item in enumerate(table):
            if item.ampacity >= required_ampacity:
                match_idx = i
                break

        if match_idx < 0:
            raise DegenerateGeometryError(
                f"EXCEEDS_MAX_CAPACITY: Required ampacity {required_ampacity:.1f}A exceeds largest cable size ({table[-1].ampacity}A)."
            )

        selected = table[match_idx]
        spare_margin = round(selected.ampacity - required_ampacity, 2)
        next_size = table[match_idx + 1].size if match_idx + 1 < len(table) else None
        next_amp = table[match_idx + 1].ampacity if match_idx + 1 < len(table) else None

        msg = (
            f"Selected {selected.size} mm2 cable ({selected.ampacity} A capacity) for required "
            f"{required_ampacity:.1f} A ({args.loaded_conductors} loaded conductors)."
        )

        return WireSizingResult(
            status="SUCCESS",
            message=msg,
            design_current=float(args.current),
            derating=float(args.derating),
            required_ampacity=round(required_ampacity, 2),
            selected_size=float(selected.size),
            selected_ampacity=float(selected.ampacity),
            spare_margin=spare_margin,
            next_size_up=next_size,
            next_ampacity=next_amp,
            standard=standard,
            disclaimer=disclaimer,
        )


# ============================================================================
# 3. BREAKER SELECT DTOs & HANDLER (cadmind-breaker-select)
# ============================================================================


@dataclass(frozen=True)
class BreakerSelectArgs:
    """Arguments matching TierBWave20Contracts.BreakerSelectArgs."""

    current: Optional[float] = None
    power: Optional[float] = None
    voltage: Optional[float] = None
    phase: int = 3
    power_factor: float = 0.8
    safety: float = 1.0
    cable_ampacity: Optional[float] = None
    ratings: Optional[Sequence[float]] = None


@dataclass(frozen=True)
class BreakerSelectResult:
    """Result matching TierBWave20Contracts.BreakerSelectResult."""

    status: str
    message: str
    load_current: float
    design_current: float
    selected_rating: float
    safety_factor: float
    cable_ampacity: Optional[float]
    cable_protected: bool
    coordination_warning: Optional[str]
    standard: str
    disclaimer: str


class BreakerSelectHandler:
    """Handler for cadmind-breaker-select with strict C# parity."""

    # IEC 60898-1 / IEC 60947-2 standard nominal ratings (A)
    DEFAULT_RATINGS = [
        6.0, 10.0, 13.0, 16.0, 20.0, 25.0, 32.0, 40.0, 50.0, 63.0,
        80.0, 100.0, 125.0, 160.0, 200.0, 250.0, 320.0, 400.0, 500.0, 630.0,
    ]

    def execute(self, args: BreakerSelectArgs) -> BreakerSelectResult:
        if args.current is not None:
            load_current = float(args.current)
        elif args.power is not None:
            if not isinstance(args.power, (int, float)) or isinstance(args.power, bool) or args.power <= 0.0 or math.isnan(args.power) or math.isinf(args.power):
                raise DegenerateGeometryError("INVALID_POWER: Power must be positive and finite.")
            if args.phase not in (1, 3):
                raise DegenerateGeometryError("INVALID_PHASE: Phase must be either 1 or 3.")
            if not isinstance(args.power_factor, (int, float)) or isinstance(args.power_factor, bool) or args.power_factor <= 0.0 or args.power_factor > 1.0 or math.isnan(args.power_factor) or math.isinf(args.power_factor):
                raise DegenerateGeometryError("INVALID_POWER_FACTOR: PowerFactor must be in range (0, 1].")
            if args.voltage is not None and (not isinstance(args.voltage, (int, float)) or isinstance(args.voltage, bool) or args.voltage <= 0.0 or math.isnan(args.voltage) or math.isinf(args.voltage)):
                raise DegenerateGeometryError("INVALID_VOLTAGE: Voltage must be positive and finite.")

            ph = 1 if args.phase == 1 else 3
            v = float(args.voltage) if args.voltage is not None else (230.0 if ph == 1 else 400.0)
            pf = float(args.power_factor)

            if ph == 1:
                load_current = args.power / (v * pf)
            else:
                load_current = args.power / (math.sqrt(3.0) * v * pf)
        else:
            raise DegenerateGeometryError("MISSING_LOAD: Either 'current' or 'power' must be provided.")

        if not isinstance(load_current, (int, float)) or isinstance(load_current, bool) or load_current <= 0.0 or math.isnan(load_current) or math.isinf(load_current):
            raise DegenerateGeometryError("INVALID_LOAD_CURRENT: Load current must be positive and finite.")

        if not isinstance(args.safety, (int, float)) or isinstance(args.safety, bool) or args.safety < 1.0 or math.isnan(args.safety) or math.isinf(args.safety):
            raise DegenerateGeometryError("INVALID_SAFETY_FACTOR: Safety factor must be finite and >= 1.0 (use 1.0 for direct IEC Ib <= In sizing).")

        sf = float(args.safety)
        design_current = load_current * sf

        ratings = (
            sorted([r for r in args.ratings if r > 0.0 and not math.isnan(r) and not math.isinf(r)])
            if args.ratings is not None and len(args.ratings) > 0
            else self.DEFAULT_RATINGS
        )

        selected_rating = -1.0
        for r in ratings:
            if r >= design_current:
                selected_rating = r
                break

        if selected_rating < 0.0:
            raise DegenerateGeometryError(
                f"EXCEEDS_MAX_BREAKER: Design current {design_current:.1f}A exceeds highest breaker rating ({ratings[-1]}A)."
            )

        cable_protected = True
        warning = None

        if args.cable_ampacity is not None:
            iz = float(args.cable_ampacity)
            if iz <= 0.0 or math.isnan(iz) or math.isinf(iz):
                raise DegenerateGeometryError("INVALID_CABLE_AMPACITY: Cable ampacity (Iz) must be positive and finite.")

            if load_current > iz:
                raise DegenerateGeometryError(
                    f"CONDUCTOR_UNDERSIZED: Load current ({load_current:.1f}A) exceeds cable ampacity ({iz:.1f}A). Conductor cannot be protected against overload."
                )

            # IEC 60364-4-43 Clause 433.1: Ib <= In <= Iz and I2 <= 1.45 * Iz
            i2 = 1.45 * selected_rating
            max_i2 = 1.45 * iz

            rule1_pass = selected_rating <= iz
            rule2_pass = i2 <= max_i2 + 1e-9

            if not rule1_pass or not rule2_pass:
                cable_protected = False
                warning = (
                    f"IEC 60364-4-43 Clause 433.1 violation: Selected breaker (In={selected_rating}A, I2={i2:.2f}A) "
                    f"exceeds cable ampacity (Iz={iz}A, 1.45*Iz={max_i2:.2f}A) - cable is not protected against overload."
                )

        msg = f"Selected {selected_rating} A breaker for load {load_current:.1f} A (design {design_current:.1f} A)."

        return BreakerSelectResult(
            status="SUCCESS",
            message=msg,
            load_current=round(load_current, 2),
            design_current=round(design_current, 2),
            selected_rating=selected_rating,
            safety_factor=sf,
            cable_ampacity=float(args.cable_ampacity) if args.cable_ampacity is not None else None,
            cable_protected=cable_protected,
            coordination_warning=warning,
            standard="IEC 60898-1 / IEC 60947-2 & IEC 60364-4-43 Clause 433.1",
            disclaimer="Overload coordination verified for IEC 60898-1 MCBs (I2 = 1.45*In <= 1.45*Iz). Safety defaults to 1.0 per IEC 60364-4-43 (Ib <= In <= Iz); for NEC 210.20(A) continuous loads pass Safety=1.25 explicitly.",
        )


# ============================================================================
# 4. RACEWAY RUN DTOs & HANDLER (cadmind-raceway-run)
# ============================================================================


@dataclass(frozen=True)
class RacewayRunArgs:
    """Arguments matching TierBWave20Contracts.RacewayRunArgs."""

    points: Optional[Sequence[Sequence[float]]] = None
    width: float = 300.0
    type: str = "tray"
    rung: float = 0.0
    layer: str = "E-TRAY"


@dataclass(frozen=True)
class RacewayRunResult:
    """Result matching TierBWave20Contracts.RacewayRunResult."""

    status: str
    message: str
    vertex_count: int
    width: float
    type: str
    rung_spacing: float
    rung_count: int
    layer: str
    entity_count: int
    created_handles: List[str] = field(default_factory=list)
    lines: List[LineSegment2D] = field(default_factory=list)


class RacewayRunHandler:
    """Handler for cadmind-raceway-run with strict C# parity."""

    def execute(self, args: RacewayRunArgs) -> RacewayRunResult:
        if args.points is None or len(args.points) < 2:
            raise DegenerateGeometryError("INVALID_POINTS: At least two vertices are required for raceway run.")

        if not isinstance(args.width, (int, float)) or isinstance(args.width, bool) or args.width <= 0.0 or math.isnan(args.width) or math.isinf(args.width):
            raise DegenerateGeometryError("INVALID_WIDTH: Width must be positive and finite.")

        if not isinstance(args.rung, (int, float)) or isinstance(args.rung, bool) or args.rung < 0.0 or math.isnan(args.rung) or math.isinf(args.rung):
            raise DegenerateGeometryError("INVALID_RUNG: Rung spacing cannot be negative.")

        n = len(args.points)
        half_w = args.width / 2.0
        layer = args.layer.strip() if args.layer and args.layer.strip() else "E-TRAY"
        raceway_type = args.type.strip().lower() if args.type and args.type.strip() else "tray"

        seg_dirs: List[Point2D] = []
        seg_norms: List[Point2D] = []
        seg_lens: List[float] = []
        total_length = 0.0

        for i in range(n - 1):
            x1, y1 = float(args.points[i][0]), float(args.points[i][1])
            x2, y2 = float(args.points[i + 1][0]), float(args.points[i + 1][1])
            _validate_finite(x1, "X1")
            _validate_finite(y1, "Y1")
            _validate_finite(x2, "X2")
            _validate_finite(y2, "Y2")

            dx = x2 - x1
            dy = y2 - y1
            length = math.sqrt(dx * dx + dy * dy)
            if length <= 1e-6:
                length = 1e-6

            dir_v = Point2D(dx / length, dy / length)
            norm_v = Point2D(-dir_v.y, dir_v.x)

            seg_dirs.append(dir_v)
            seg_norms.append(norm_v)
            seg_lens.append(length)
            total_length += length

        left_points: List[Point2D] = []
        right_points: List[Point2D] = []

        for i in range(n):
            px, py = float(args.points[i][0]), float(args.points[i][1])
            if i == 0:
                v_norm = seg_norms[0]
            elif i == n - 1:
                v_norm = seg_norms[-1]
            else:
                avg_x = seg_norms[i - 1].x + seg_norms[i].x
                avg_y = seg_norms[i - 1].y + seg_norms[i].y
                avg_len = math.sqrt(avg_x * avg_x + avg_y * avg_y)
                if avg_len <= 1e-6:
                    v_norm = seg_norms[i]
                else:
                    v_norm = Point2D(avg_x / avg_len, avg_y / avg_len)

            left_points.append(Point2D(px + half_w * v_norm.x, py + half_w * v_norm.y))
            right_points.append(Point2D(px - half_w * v_norm.x, py - half_w * v_norm.y))

        handles: List[str] = []
        lines: List[LineSegment2D] = []

        # Left rail
        for i in range(len(left_points) - 1):
            lines.append(LineSegment2D(left_points[i], left_points[i + 1]))
        handles.append("RACEWAY_LEFT_RAIL")

        # Right rail
        for i in range(len(right_points) - 1):
            lines.append(LineSegment2D(right_points[i], right_points[i + 1]))
        handles.append("RACEWAY_RIGHT_RAIL")

        rung_count = 0
        if raceway_type in ("tray", "ladder") and args.rung > 0.0:
            cursor = args.rung
            seg_idx = 0
            dist_in_seg = cursor

            while cursor < total_length and seg_idx < len(seg_lens):
                while seg_idx < len(seg_lens) and dist_in_seg > seg_lens[seg_idx]:
                    dist_in_seg -= seg_lens[seg_idx]
                    seg_idx += 1

                if seg_idx >= len(seg_lens):
                    break

                p1x, p1y = float(args.points[seg_idx][0]), float(args.points[seg_idx][1])
                dir_v = seg_dirs[seg_idx]
                norm_v = seg_norms[seg_idx]

                cx = p1x + (dist_in_seg * dir_v.x)
                cy = p1y + (dist_in_seg * dir_v.y)

                lines.append(
                    LineSegment2D(
                        Point2D(cx + half_w * norm_v.x, cy + half_w * norm_v.y),
                        Point2D(cx - half_w * norm_v.x, cy - half_w * norm_v.y),
                    )
                )
                handles.append(f"RACEWAY_RUNG_{rung_count + 1}")
                rung_count += 1

                cursor += args.rung
                dist_in_seg += args.rung

        entity_count = len(handles)
        msg = (
            f"Created {raceway_type} raceway with {entity_count} entities "
            f"(2 rails, {rung_count} rungs, length={total_length:.1f}) on layer '{layer}'."
        )

        return RacewayRunResult(
            status="SUCCESS",
            message=msg,
            vertex_count=n,
            width=float(args.width),
            type=raceway_type,
            rung_spacing=float(args.rung),
            rung_count=rung_count,
            layer=layer,
            entity_count=entity_count,
            created_handles=handles,
            lines=lines,
        )


# ============================================================================
# 5. HOME RUN DTOs & HANDLER (cadmind-home-run)
# ============================================================================


@dataclass(frozen=True)
class HomeRunItem:
    """Home run item matching TierBWave20Contracts.HomeRunItem."""

    point: Optional[Sequence[float]] = None
    angle: float = 90.0
    circuit: Optional[str] = None
    wires: int = 2
    ground: bool = False


@dataclass(frozen=True)
class HomeRunArgs:
    """Arguments matching TierBWave20Contracts.HomeRunArgs."""

    runs: Optional[Sequence[HomeRunItem]] = None
    length: float = 30.0
    height: float = 2.5
    layer: str = "E-HOMERUN"


@dataclass(frozen=True)
class HomeRunResult:
    """Result matching TierBWave20Contracts.HomeRunResult."""

    status: str
    message: str
    runs_count: int
    length: float
    height: float
    layer: str
    entity_count: int
    created_handles: List[str] = field(default_factory=list)
    lines: List[LineSegment2D] = field(default_factory=list)


class HomeRunHandler:
    """Handler for cadmind-home-run with strict C# parity."""

    def execute(self, args: HomeRunArgs) -> HomeRunResult:
        if args.runs is None or len(args.runs) == 0:
            raise DegenerateGeometryError("INVALID_RUNS: At least one home run item must be provided.")

        if not isinstance(args.length, (int, float)) or isinstance(args.length, bool) or args.length <= 0.0 or math.isnan(args.length) or math.isinf(args.length):
            raise DegenerateGeometryError("INVALID_LENGTH: Length must be positive and finite.")

        if not isinstance(args.height, (int, float)) or isinstance(args.height, bool) or args.height <= 0.0 or math.isnan(args.height) or math.isinf(args.height):
            raise DegenerateGeometryError("INVALID_HEIGHT: Height must be positive and finite.")

        layer = args.layer.strip() if args.layer and args.layer.strip() else "E-HOMERUN"
        handles: List[str] = []
        lines: List[LineSegment2D] = []

        for idx, run in enumerate(args.runs):
            px = float(run.point[0]) if run.point and len(run.point) >= 1 else 0.0
            py = float(run.point[1]) if run.point and len(run.point) >= 2 else 0.0
            _validate_finite(px, "POINT_X")
            _validate_finite(py, "POINT_Y")

            angle_rad = run.angle * math.pi / 180.0
            ux = math.cos(angle_rad)
            uy = math.sin(angle_rad)
            nx = -uy
            ny = ux

            end_x = px + (args.length * ux)
            end_y = py + (args.length * uy)

            # 1. Shaft line
            lines.append(LineSegment2D(Point2D(px, py), Point2D(end_x, end_y)))
            handles.append(f"HOMERUN_SHAFT_{idx + 1}")

            # 2. Arrowhead barbs
            barb_len = min(args.length * 0.25, args.height * 2.0)
            b1_rad = angle_rad + (150.0 * math.pi / 180.0)
            b2_rad = angle_rad - (150.0 * math.pi / 180.0)

            lines.append(LineSegment2D(Point2D(end_x, end_y), Point2D(end_x + barb_len * math.cos(b1_rad), end_y + barb_len * math.sin(b1_rad))))
            handles.append(f"HOMERUN_BARB1_{idx + 1}")

            lines.append(LineSegment2D(Point2D(end_x, end_y), Point2D(end_x + barb_len * math.cos(b2_rad), end_y + barb_len * math.sin(b2_rad))))
            handles.append(f"HOMERUN_BARB2_{idx + 1}")

            # 3. Conductor ticks
            wires = max(1, run.wires)
            tick_spacing = args.height * 1.5
            tick_half = args.height * 0.8
            base_dist = args.length * 0.4

            for w in range(wires):
                tc_x = px + ((base_dist + (w * tick_spacing)) * ux)
                tc_y = py + ((base_dist + (w * tick_spacing)) * uy)

                lines.append(
                    LineSegment2D(
                        Point2D(tc_x - tick_half * nx, tc_y - tick_half * ny),
                        Point2D(tc_x + tick_half * nx, tc_y + tick_half * ny),
                    )
                )
                handles.append(f"HOMERUN_TICK_{idx + 1}_{w + 1}")

            # 4. Ground tick
            if run.ground:
                g_dist = base_dist + (wires * tick_spacing)
                gc_x = px + (g_dist * ux)
                gc_y = py + (g_dist * uy)
                g_tick_half = tick_half * 1.5

                lines.append(
                    LineSegment2D(
                        Point2D(gc_x - g_tick_half * nx, gc_y - g_tick_half * ny),
                        Point2D(gc_x + g_tick_half * nx, gc_y + g_tick_half * ny),
                    )
                )
                handles.append(f"HOMERUN_GROUND_{idx + 1}")

            # 5. Circuit tag text
            if run.circuit and run.circuit.strip():
                handles.append(f"HOMERUN_TEXT_{idx + 1}")

        entity_count = len(handles)
        msg = f"Created {len(args.runs)} home run arrows with {entity_count} entities on layer '{layer}'."

        return HomeRunResult(
            status="SUCCESS",
            message=msg,
            runs_count=len(args.runs),
            length=float(args.length),
            height=float(args.height),
            layer=layer,
            entity_count=entity_count,
            created_handles=handles,
            lines=lines,
        )


# ============================================================================
# 6. WIRE TAG DTOs & HANDLER (cadmind-wire-tag)
# ============================================================================


@dataclass(frozen=True)
class WireTagItem:
    """Wire tag item matching TierAWave4Contracts.WireTagItem."""

    point: Optional[Sequence[float]] = None
    id: str = ""
    from_node: Optional[str] = None
    to_node: Optional[str] = None
    size: Optional[str] = None


@dataclass(frozen=True)
class WireTagArgs:
    """Arguments matching TierAWave4Contracts.WireTagArgs."""

    tags: Optional[Sequence[WireTagItem]] = None
    height: float = 2.5
    underline: bool = True
    layer: str = "E-WIRE-TAG"


@dataclass(frozen=True)
class WireTagResult:
    """Result matching TierAWave4Contracts.WireTagResult."""

    status: str
    message: str
    tag_count: int
    processed_count: int
    lines: List[LineSegment2D] = field(default_factory=list)


class WireTagHandler:
    """Handler for cadmind-wire-tag with strict C# parity."""

    def execute(self, args: WireTagArgs) -> WireTagResult:
        if args.tags is None or len(args.tags) == 0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Wire tag requires at least one tag item.")

        if not isinstance(args.height, (int, float)) or isinstance(args.height, bool) or args.height <= 1e-4 or math.isnan(args.height) or math.isinf(args.height):
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Text height must be positive and non-zero.")

        total_entities = 0
        lines: List[LineSegment2D] = []

        for item in args.tags:
            if item.point is None or len(item.point) < 2 or math.isnan(item.point[0]) or math.isnan(item.point[1]) or math.isinf(item.point[0]) or math.isinf(item.point[1]):
                raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Invalid or non-finite tag position coordinates.")

            if not item.id or not item.id.strip():
                raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Wire tag Id must be non-empty.")

            px, py = float(item.point[0]), float(item.point[1])
            total_entities += 1  # Text entity

            # Text width approximation for underline
            composed = item.id.strip()
            if item.from_node and item.to_node:
                composed += f" ({item.from_node}->{item.to_node})"
            if item.size:
                composed += f" [{item.size}]"

            if args.underline:
                text_len = len(composed) * args.height * 0.6
                lines.append(LineSegment2D(Point2D(px, py - 0.5), Point2D(px + text_len, py - 0.5)))
                total_entities += 1

        msg = f"Placed {len(args.tags)} wire tags on layer '{args.layer}'."

        return WireTagResult(
            status="SUCCESS",
            message=msg,
            tag_count=len(args.tags),
            processed_count=total_entities,
            lines=lines,
        )


# ============================================================================
# 7. SYMBOL LEGEND DTOs & HANDLER (cadmind-symbol-legend)
# ============================================================================


@dataclass(frozen=True)
class SymbolLegendEntry:
    """Legend entry matching TierAWave5Contracts.SymbolLegendEntry."""

    type: str
    description: str


@dataclass(frozen=True)
class SymbolLegendArgs:
    """Arguments matching TierAWave5Contracts.SymbolLegendArgs."""

    origin: Optional[Sequence[float]] = None
    title: str = "LEGEND"
    entries: Optional[Sequence[SymbolLegendEntry]] = None
    size: float = 2.5
    height: float = 2.5
    layer: str = "E-LEGEND"


@dataclass(frozen=True)
class SymbolLegendResult:
    """Result matching TierAWave5Contracts.SymbolLegendResult."""

    status: str
    message: str
    entry_count: int
    processed_count: int
    lines: List[LineSegment2D] = field(default_factory=list)
    circles: List[CircleIR] = field(default_factory=list)


class SymbolLegendHandler:
    """Handler for cadmind-symbol-legend with strict C# parity."""

    def execute(self, args: SymbolLegendArgs) -> SymbolLegendResult:
        if args.entries is None or len(args.entries) == 0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Symbol legend requires at least one entry.")

        if not isinstance(args.size, (int, float)) or isinstance(args.size, bool) or args.size <= 1e-4 or math.isnan(args.size) or math.isinf(args.size):
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Glyph size and text height must be positive and non-zero.")

        if not isinstance(args.height, (int, float)) or isinstance(args.height, bool) or args.height <= 1e-4 or math.isnan(args.height) or math.isinf(args.height):
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Glyph size and text height must be positive and non-zero.")

        for entry in args.entries:
            etype = entry.type.strip().lower() if entry.type and entry.type.strip() else ""
            if etype not in DeviceSymbolHandler.VALID_TYPES:
                raise DegenerateGeometryError(f"DEGENERATE_GEOMETRY: Invalid symbol type '{entry.type}' in legend entries.")

        ox = 0.0
        oy = 0.0
        if args.origin is not None and len(args.origin) >= 2:
            if math.isnan(args.origin[0]) or math.isnan(args.origin[1]) or math.isinf(args.origin[0]) or math.isinf(args.origin[1]):
                raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Origin coordinates must be finite numbers.")
            ox = float(args.origin[0])
            oy = float(args.origin[1])

        total_entities = 0
        lines: List[LineSegment2D] = []
        circles: List[CircleIR] = []

        # Title text
        total_entities += 1
        row_height = max(8.0, args.height * 3.0)
        cur_y = oy - row_height

        dev_handler = DeviceSymbolHandler()

        for idx, entry in enumerate(args.entries):
            glyph_center = [ox + 10.0, cur_y + (row_height / 2.0)]
            # Draw glyph via DeviceSymbolHandler
            dev_res = dev_handler.execute(
                type("TempArgs", (), {
                    "points": [glyph_center],
                    "type": entry.type,
                    "size": args.size,
                    "rotation": 0.0,
                    "layer": args.layer,
                })()
            )
            total_entities += dev_res.processed_count
            lines.extend(dev_res.lines)
            circles.extend(dev_res.circles)

            # Description text
            total_entities += 1
            cur_y -= row_height

        title = args.title.strip() if args.title and args.title.strip() else "LEGEND"
        msg = f"Placed symbol legend '{title}' with {len(args.entries)} entries."

        return SymbolLegendResult(
            status="SUCCESS",
            message=msg,
            entry_count=len(args.entries),
            processed_count=total_entities,
            lines=lines,
            circles=circles,
        )
