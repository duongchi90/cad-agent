"""cad_agent/cleanroom_electrical_routing.py.

Batch E1: Electrical Routing, Cable Trench, Busbar, Circuit Numbering & Layer Audit.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierBWave18Handlers.cs: BusbarHandler (cadmind-busbar)
  - TierBWave18Handlers.cs: CableRunHandler (cadmind-cable-run)
  - TierBWave18Handlers.cs: CableTrenchHandler (cadmind-cable-trench)
  - TierBWave18Handlers.cs: CircuitNumberHandler (cadmind-circuit-number)
  - TierBWave17Handlers.cs: CircuitAuditHandler (cadmind-circuit-audit)
  - TierBWave15Handlers.cs: ElecLayerCheckHandler (cadmind-elec-layer-check)

Part of Domain 4 (ELECTRICAL: 19 registered tools).
Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D, CircleIR),
strict IEEE-754 machine-epsilon safety, Banker's rounding parity,
and zero external pip dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

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
# INTERNAL IEEE-754 VALIDATION HELPERS
# ============================================================================


def _validate_finite(val: float, name: str) -> float:
    """Ensure value is finite (not NaN, not Inf)."""
    if not isinstance(val, (int, float)) or isinstance(val, bool) or math.isnan(val) or math.isinf(val):
        raise DegenerateGeometryError(f"INVALID_{name.upper()}: {name} must be positive and finite.")
    return float(val)


# ============================================================================
# 1. BUSBAR DTOs & HANDLER (cadmind-busbar)
# ============================================================================


@dataclass(frozen=True)
class BusbarArgs:
    """Arguments matching TierBWave18Contracts.BusbarArgs."""

    origin: Optional[Sequence[float]] = None
    length: float = 1000.0
    bars: int = 3
    spacing: float = 40.0
    thickness: float = 8.0
    labels: Optional[Sequence[str]] = None
    layer: str = "E-BUS"


@dataclass(frozen=True)
class BusbarResult:
    """Result matching TierBWave18Contracts.BusbarResult."""

    status: str
    message: str
    bar_count: int
    length: float
    thickness: float
    spacing: float
    layer: str
    entity_count: int
    created_handles: List[str] = field(default_factory=list)
    lines: List[LineSegment2D] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)


class BusbarHandler:
    """Handler for cadmind-busbar with strict C# parity."""

    def execute(self, args: BusbarArgs) -> BusbarResult:
        if not isinstance(args.bars, int) or isinstance(args.bars, bool) or args.bars <= 0:
            raise DegenerateGeometryError("INVALID_BARS: Bars must be positive.")

        if not isinstance(args.length, (int, float)) or isinstance(args.length, bool) or args.length <= 0.0 or math.isnan(args.length) or math.isinf(args.length):
            raise DegenerateGeometryError("INVALID_LENGTH: Length must be positive and finite.")

        if not isinstance(args.thickness, (int, float)) or isinstance(args.thickness, bool) or args.thickness <= 0.0 or math.isnan(args.thickness) or math.isinf(args.thickness):
            raise DegenerateGeometryError("INVALID_THICKNESS: Thickness must be positive and finite.")

        if not isinstance(args.spacing, (int, float)) or isinstance(args.spacing, bool) or args.spacing <= 0.0 or math.isnan(args.spacing) or math.isinf(args.spacing):
            raise DegenerateGeometryError("INVALID_SPACING: Spacing must be positive and finite.")

        if args.spacing < args.thickness:
            raise DegenerateGeometryError("INVALID_SPACING: Spacing must be greater than or equal to bar thickness.")

        ox = float(args.origin[0]) if args.origin and len(args.origin) >= 1 else 0.0
        oy = float(args.origin[1]) if args.origin and len(args.origin) >= 2 else 0.0
        _validate_finite(ox, "ORIGIN_X")
        _validate_finite(oy, "ORIGIN_Y")

        layer = args.layer.strip() if args.layer and args.layer.strip() else "E-BUS"
        handles: List[str] = []
        lines: List[LineSegment2D] = []
        out_labels: List[str] = []

        for i in range(args.bars):
            by = oy + (i * args.spacing)
            # Polyline rectangle (4 segments)
            p0 = Point2D(ox, by)
            p1 = Point2D(ox + args.length, by)
            p2 = Point2D(ox + args.length, by + args.thickness)
            p3 = Point2D(ox, by + args.thickness)

            lines.append(LineSegment2D(p0, p1))
            lines.append(LineSegment2D(p1, p2))
            lines.append(LineSegment2D(p2, p3))
            lines.append(LineSegment2D(p3, p0))
            handles.append(f"BUS_BAR_{i + 1}")

            if args.labels and i < len(args.labels) and args.labels[i] and args.labels[i].strip():
                lbl = args.labels[i].strip()
                out_labels.append(lbl)
                handles.append(f"BUS_LBL_{i + 1}")

        entity_count = len(handles)
        msg = f"Created {entity_count} entities ({args.bars} busbars) on layer '{layer}'."

        return BusbarResult(
            status="SUCCESS",
            message=msg,
            bar_count=args.bars,
            length=float(args.length),
            thickness=float(args.thickness),
            spacing=float(args.spacing),
            layer=layer,
            entity_count=entity_count,
            created_handles=handles,
            lines=lines,
            labels=out_labels,
        )


# ============================================================================
# 2. CABLE RUN DTOs & HANDLER (cadmind-cable-run)
# ============================================================================


@dataclass(frozen=True)
class CableRunArgs:
    """Arguments matching TierBWave18Contracts.CableRunArgs."""

    points: Sequence[Sequence[float]]
    closed: bool = False
    homerun: bool = False
    layer: str = "E-WIRE"


@dataclass(frozen=True)
class CableRunResult:
    """Result matching TierBWave18Contracts.CableRunResult."""

    status: str
    message: str
    point_count: int
    total_length: float
    is_closed: bool
    has_homerun: bool
    layer: str
    entity_count: int
    created_handles: List[str] = field(default_factory=list)
    lines: List[LineSegment2D] = field(default_factory=list)


class CableRunHandler:
    """Handler for cadmind-cable-run with strict C# parity."""

    def execute(self, args: CableRunArgs) -> CableRunResult:
        if args.points is None or len(args.points) < 2:
            raise DegenerateGeometryError("INVALID_POINTS: Points list must contain at least 2 coordinate vertices.")

        valid_pts: List[Point2D] = []
        for pt in args.points:
            if pt is None or len(pt) < 2 or not isinstance(pt[0], (int, float)) or isinstance(pt[0], bool) or not isinstance(pt[1], (int, float)) or isinstance(pt[1], bool) or math.isnan(pt[0]) or math.isinf(pt[0]) or math.isnan(pt[1]) or math.isinf(pt[1]):
                raise DegenerateGeometryError("INVALID_COORDINATES: All route points must have valid finite [x, y] coordinates.")
            valid_pts.append(Point2D(float(pt[0]), float(pt[1])))

        layer = args.layer.strip() if args.layer and args.layer.strip() else "E-WIRE"
        handles: List[str] = []
        lines: List[LineSegment2D] = []
        total_length = 0.0

        for i in range(1, len(valid_pts)):
            prev = valid_pts[i - 1]
            curr = valid_pts[i]
            dx = curr.x - prev.x
            dy = curr.y - prev.y
            dist = math.sqrt(dx * dx + dy * dy)
            total_length += dist
            lines.append(LineSegment2D(prev, curr))

        if args.closed:
            first = valid_pts[0]
            last = valid_pts[-1]
            dx = first.x - last.x
            dy = first.y - last.y
            dist = math.sqrt(dx * dx + dy * dy)
            total_length += dist
            lines.append(LineSegment2D(last, first))

        handles.append("CABLE_RUN_PLINE")

        # Home-run mark: 3 slash strokes on the first segment
        if args.homerun and len(valid_pts) >= 2:
            p0 = valid_pts[0]
            p1 = valid_pts[1]
            dx = p1.x - p0.x
            dy = p1.y - p0.y
            seg_len = math.sqrt(dx * dx + dy * dy)

            if seg_len > 1e-4:
                ux = dx / seg_len
                uy = dy / seg_len
                nx = -uy
                ny = ux

                base_offset = min(15.0, seg_len * 0.25)
                tick_spacing = 5.0
                tick_half_len = 4.0

                for t in range(3):
                    dist = base_offset + (t * tick_spacing)
                    cx = p0.x + (ux * dist)
                    cy = p0.y + (uy * dist)

                    tick_start = Point2D(cx - (nx * tick_half_len), cy - (ny * tick_half_len))
                    tick_end = Point2D(cx + (nx * tick_half_len), cy + (ny * tick_half_len))
                    lines.append(LineSegment2D(tick_start, tick_end))
                    handles.append(f"HOMERUN_TICK_{t + 1}")

        entity_count = len(handles)
        msg = f"Created cable run with {entity_count} entities, length {total_length:.2f} on layer '{layer}'."

        return CableRunResult(
            status="SUCCESS",
            message=msg,
            point_count=len(valid_pts),
            total_length=total_length,
            is_closed=bool(args.closed),
            has_homerun=bool(args.homerun),
            layer=layer,
            entity_count=entity_count,
            created_handles=handles,
            lines=lines,
        )


# ============================================================================
# 3. CABLE TRENCH DTOs & HANDLER (cadmind-cable-trench)
# ============================================================================


@dataclass(frozen=True)
class CableTrenchArgs:
    """Arguments matching TierBWave18Contracts.CableTrenchArgs."""

    origin: Optional[Sequence[float]] = None
    width: float = 600.0
    depth: float = 900.0
    cables: int = 1
    cable_dia: float = 50.0
    cable_depth: Optional[float] = None
    layer: str = "E-SECTION"


@dataclass(frozen=True)
class CableTrenchResult:
    """Result matching TierBWave18Contracts.CableTrenchResult."""

    status: str
    message: str
    width: float
    depth: float
    cable_count: int
    cable_diameter: float
    cable_depth: float
    layer: str
    entity_count: int
    created_handles: List[str] = field(default_factory=list)
    lines: List[LineSegment2D] = field(default_factory=list)
    circles: List[CircleIR] = field(default_factory=list)


class CableTrenchHandler:
    """Handler for cadmind-cable-trench with strict C# parity."""

    def execute(self, args: CableTrenchArgs) -> CableTrenchResult:
        if not isinstance(args.width, (int, float)) or isinstance(args.width, bool) or args.width <= 0.0 or math.isnan(args.width) or math.isinf(args.width):
            raise DegenerateGeometryError("INVALID_WIDTH: Width must be positive and finite.")

        if not isinstance(args.depth, (int, float)) or isinstance(args.depth, bool) or args.depth <= 0.0 or math.isnan(args.depth) or math.isinf(args.depth):
            raise DegenerateGeometryError("INVALID_DEPTH: Depth must be positive and finite.")

        if not isinstance(args.cables, int) or isinstance(args.cables, bool) or args.cables <= 0:
            raise DegenerateGeometryError("INVALID_CABLES: Cables count must be positive.")

        if not isinstance(args.cable_dia, (int, float)) or isinstance(args.cable_dia, bool) or args.cable_dia <= 0.0 or math.isnan(args.cable_dia) or math.isinf(args.cable_dia):
            raise DegenerateGeometryError("INVALID_CABLE_DIA: CableDia must be positive and finite.")

        cable_depth = args.cable_depth if args.cable_depth is not None else (0.75 * args.depth)
        if not isinstance(cable_depth, (int, float)) or isinstance(cable_depth, bool) or cable_depth <= 0.0 or cable_depth >= args.depth or math.isnan(cable_depth) or math.isinf(cable_depth):
            raise DegenerateGeometryError("INVALID_CABLE_DEPTH: CableDepth must be positive and strictly less than trench depth.")

        ox = float(args.origin[0]) if args.origin and len(args.origin) >= 1 else 0.0
        oy = float(args.origin[1]) if args.origin and len(args.origin) >= 2 else 0.0
        _validate_finite(ox, "ORIGIN_X")
        _validate_finite(oy, "ORIGIN_Y")

        layer = args.layer.strip() if args.layer and args.layer.strip() else "E-SECTION"
        handles: List[str] = []
        lines: List[LineSegment2D] = []
        circles: List[CircleIR] = []
        hw = args.width / 2.0

        # 1. Grade line
        lines.append(LineSegment2D(Point2D(ox - args.width, oy), Point2D(ox + args.width, oy)))
        handles.append("TRENCH_GRADE_LINE")

        # 2. Trench outline (U-shaped polyline: 3 segments)
        p0 = Point2D(ox - hw, oy)
        p1 = Point2D(ox - hw, oy - args.depth)
        p2 = Point2D(ox + hw, oy - args.depth)
        p3 = Point2D(ox + hw, oy)
        lines.append(LineSegment2D(p0, p1))
        lines.append(LineSegment2D(p1, p2))
        lines.append(LineSegment2D(p2, p3))
        handles.append("TRENCH_PLINE")

        # 3. Sand bed line (100mm from bottom)
        sand_y = oy - args.depth + min(100.0, args.depth * 0.15)
        lines.append(LineSegment2D(Point2D(ox - hw, sand_y), Point2D(ox + hw, sand_y)))
        handles.append("TRENCH_SAND_LINE")

        # 4. Warning tape line (30% depth from surface)
        tape_y = oy - (args.depth * 0.30)
        lines.append(LineSegment2D(Point2D(ox - hw, tape_y), Point2D(ox + hw, tape_y)))
        handles.append("TRENCH_TAPE_LINE")

        # 5. Cable circles at cableDepth
        cable_center_y = oy - cable_depth
        cable_radius = args.cable_dia / 2.0

        for c in range(args.cables):
            if args.cables == 1:
                cx = ox
            else:
                cx = ox - hw + ((args.width / (args.cables + 1)) * (c + 1))

            circles.append(CircleIR(Point2D(cx, cable_center_y), cable_radius, index=c + 1))
            handles.append(f"TRENCH_CABLE_{c + 1}")

        entity_count = len(handles)
        msg = f"Created cable trench cross-section with {entity_count} entities ({args.cables} cables) on layer '{layer}'."

        return CableTrenchResult(
            status="SUCCESS",
            message=msg,
            width=float(args.width),
            depth=float(args.depth),
            cable_count=args.cables,
            cable_diameter=float(args.cable_dia),
            cable_depth=float(cable_depth),
            layer=layer,
            entity_count=entity_count,
            created_handles=handles,
            lines=lines,
            circles=circles,
        )


# ============================================================================
# 4. CIRCUIT NUMBER DTOs & HANDLER (cadmind-circuit-number)
# ============================================================================


@dataclass(frozen=True)
class CircuitNumberArgs:
    """Arguments matching TierBWave18Contracts.CircuitNumberArgs."""

    points: Sequence[Sequence[float]]
    prefix: str = "P1-"
    start: int = 1
    pad: int = 2
    height: float = 2.5
    layer: str = "E-CIRCUIT"


@dataclass(frozen=True)
class CircuitNumberResult:
    """Result matching TierBWave18Contracts.CircuitNumberResult."""

    status: str
    message: str
    tags_created: int
    layer: str
    entity_count: int
    generated_labels: List[str] = field(default_factory=list)
    created_handles: List[str] = field(default_factory=list)
    positions: List[Point2D] = field(default_factory=list)


class CircuitNumberHandler:
    """Handler for cadmind-circuit-number with strict C# parity."""

    def execute(self, args: CircuitNumberArgs) -> CircuitNumberResult:
        if args.points is None or len(args.points) == 0:
            raise DegenerateGeometryError("INVALID_POINTS: Points list must contain at least 1 coordinate vertex.")

        if not isinstance(args.height, (int, float)) or isinstance(args.height, bool) or args.height <= 0.0 or math.isnan(args.height) or math.isinf(args.height):
            raise DegenerateGeometryError("INVALID_HEIGHT: Height must be positive and finite.")

        if not isinstance(args.pad, int) or isinstance(args.pad, bool) or args.pad < 0:
            raise DegenerateGeometryError("INVALID_PAD: Pad width cannot be negative.")

        valid_pts: List[Point2D] = []
        for pt in args.points:
            if pt is None or len(pt) < 2 or not isinstance(pt[0], (int, float)) or isinstance(pt[0], bool) or not isinstance(pt[1], (int, float)) or isinstance(pt[1], bool) or math.isnan(pt[0]) or math.isinf(pt[0]) or math.isnan(pt[1]) or math.isinf(pt[1]):
                raise DegenerateGeometryError("INVALID_COORDINATES: All tag points must have valid finite [x, y] coordinates.")
            valid_pts.append(Point2D(float(pt[0]), float(pt[1])))

        layer = args.layer.strip() if args.layer and args.layer.strip() else "E-CIRCUIT"
        prefix = args.prefix if args.prefix is not None else "P1-"
        labels: List[str] = []
        handles: List[str] = []

        for i, pt in enumerate(valid_pts):
            num = args.start + i
            num_str = str(num).zfill(args.pad) if args.pad > 0 else str(num)
            label = f"{prefix}{num_str}"
            labels.append(label)
            handles.append(f"CIRCUIT_TAG_{i + 1}")

        entity_count = len(handles)
        msg = f"Generated {len(labels)} sequential circuit tags on layer '{layer}'."

        return CircuitNumberResult(
            status="SUCCESS",
            message=msg,
            tags_created=len(labels),
            layer=layer,
            generated_labels=labels,
            entity_count=entity_count,
            created_handles=handles,
            positions=valid_pts,
        )


# ============================================================================
# 5. CIRCUIT AUDIT DTOs & HANDLER (cadmind-circuit-audit)
# ============================================================================


@dataclass(frozen=True)
class CircuitDuplicateGroup:
    """Duplicate tag group matching TierBWave17Contracts.CircuitDuplicateGroup."""

    tag: str
    count: int
    handles: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CircuitAuditArgs:
    """Arguments matching TierBWave17Contracts.CircuitAuditArgs."""

    layer: str = "E-CIRCUIT"
    prefix: Optional[str] = None


@dataclass(frozen=True)
class CircuitAuditResult:
    """Result matching TierBWave17Contracts.CircuitAuditResult."""

    status: str
    message: str
    layer: str
    prefix: Optional[str]
    total_tags_scanned: int
    unique_tags_count: int
    duplicate_tags_count: int
    duplicates: List[CircuitDuplicateGroup] = field(default_factory=list)


class CircuitAuditHandler:
    """Handler for cadmind-circuit-audit with strict C# parity."""

    def execute(
        self,
        args: CircuitAuditArgs,
        entities: Optional[Sequence[Any]] = None,
    ) -> CircuitAuditResult:
        target_layer = args.layer.strip() if args.layer and args.layer.strip() else "E-CIRCUIT"
        prefix_filter = args.prefix.strip() if args.prefix and args.prefix.strip() else None

        tag_map: Dict[str, List[str]] = {}
        total_scanned = 0

        if entities is not None:
            for ent in entities:
                ent_layer = ""
                ent_text = ""
                ent_handle = "HANDLE"

                if isinstance(ent, dict):
                    ent_layer = str(ent.get("layer", ""))
                    ent_text = str(ent.get("text", ""))
                    ent_handle = str(ent.get("handle", "HANDLE"))
                else:
                    ent_layer = getattr(ent, "layer", "")
                    ent_text = getattr(ent, "text", getattr(ent, "text_string", getattr(ent, "contents", "")))
                    ent_handle = getattr(ent, "handle", "HANDLE")

                if not ent_layer or ent_layer.strip().lower() != target_layer.lower():
                    continue

                if not ent_text or not ent_text.strip():
                    continue

                clean_text = ent_text.strip()

                if prefix_filter and not clean_text.lower().startswith(prefix_filter.lower()):
                    continue

                total_scanned += 1
                key = clean_text
                # Find existing key case-insensitively
                found_key = None
                for k in tag_map:
                    if k.lower() == key.lower():
                        found_key = k
                        break
                if found_key is not None:
                    tag_map[found_key].append(ent_handle)
                else:
                    tag_map[key] = [ent_handle]

        duplicates: List[CircuitDuplicateGroup] = []
        for tag, hlist in tag_map.items():
            if len(hlist) > 1:
                duplicates.append(CircuitDuplicateGroup(tag=tag, count=len(hlist), handles=hlist))

        # OrderByDescending(g => g.Count).ThenBy(g => g.Tag)
        duplicates.sort(key=lambda g: (-g.count, g.tag))

        msg = f"Scanned {total_scanned} tags on layer '{target_layer}'. Found {len(duplicates)} duplicate tag groups."

        return CircuitAuditResult(
            status="SUCCESS",
            message=msg,
            layer=target_layer,
            prefix=prefix_filter,
            total_tags_scanned=total_scanned,
            unique_tags_count=len(tag_map),
            duplicate_tags_count=len(duplicates),
            duplicates=duplicates,
        )


# ============================================================================
# 6. ELEC LAYER CHECK DTOs & HANDLER (cadmind-elec-layer-check)
# ============================================================================


@dataclass(frozen=True)
class ElecLayerReportItem:
    """Report item matching TierBWave15Contracts.ElecLayerReportItem."""

    layer_name: str
    entity_count: int
    is_standard: bool


@dataclass(frozen=True)
class ElecLayerCheckArgs:
    """Arguments matching TierBWave15Contracts.ElecLayerCheckArgs."""

    allowed_layers: Optional[Sequence[str]] = None
    allowed_prefixes: Optional[Sequence[str]] = None


@dataclass(frozen=True)
class ElecLayerCheckResult:
    """Result matching TierBWave15Contracts.ElecLayerCheckResult."""

    status: str
    message: str
    total_layers: int
    standard_layers_count: int
    non_standard_layers_count: int
    compliance_rate_percent: float
    standard_layers: List[str] = field(default_factory=list)
    non_standard_layers: List[ElecLayerReportItem] = field(default_factory=list)


class ElecLayerCheckHandler:
    """Handler for cadmind-elec-layer-check with strict C# parity."""

    def execute(
        self,
        args: ElecLayerCheckArgs,
        drawing_layers: Optional[Sequence[str]] = None,
        layer_counts: Optional[Dict[str, int]] = None,
    ) -> ElecLayerCheckResult:
        allowed_prefixes = (
            list(args.allowed_prefixes)
            if args.allowed_prefixes and len(args.allowed_prefixes) > 0
            else ["E-", "0", "Defpoints"]
        )

        allowed_layers_set: Set[str] = (
            {lyr.lower() for lyr in args.allowed_layers}
            if args.allowed_layers is not None
            else set()
        )

        all_layers = list(drawing_layers) if drawing_layers is not None else []
        counts = layer_counts if layer_counts is not None else {}

        standard_layers: List[str] = []
        non_standard_list: List[ElecLayerReportItem] = []

        for lname in all_layers:
            is_std = (
                lname.lower() in allowed_layers_set
                or any(lname.lower().startswith(p.lower()) for p in allowed_prefixes)
            )

            count = counts.get(lname, 0)

            if is_std:
                standard_layers.append(lname)
            else:
                non_standard_list.append(ElecLayerReportItem(layer_name=lname, entity_count=count, is_standard=False))

        # OrderByDescending(x => x.EntityCount).ThenBy(x => x.LayerName)
        non_standard_list.sort(key=lambda x: (-x.entity_count, x.layer_name))

        comp_rate = (
            round((len(standard_layers) / len(all_layers)) * 100.0, 2)
            if len(all_layers) > 0
            else 100.0
        )

        msg = (
            f"Audited {len(all_layers)} layers: {len(standard_layers)} standard, "
            f"{len(non_standard_list)} non-standard ({comp_rate}% compliance)."
        )

        return ElecLayerCheckResult(
            status="SUCCESS",
            message=msg,
            total_layers=len(all_layers),
            standard_layers_count=len(standard_layers),
            non_standard_layers_count=len(non_standard_list),
            compliance_rate_percent=comp_rate,
            standard_layers=standard_layers,
            non_standard_layers=non_standard_list,
        )
