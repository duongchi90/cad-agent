"""cad_agent/cleanroom_hardware_inspection.py.

Batch M5: Hardware Fasteners, Title Block Annotation & Geometric Inspection.
Strict 1:1 cleanroom fidelity with physical C# source:
  - TierBWave10Handlers.cs: RivetPinHandler (cadmind-rivet-pin)
  - TierBWave11Handlers.cs: MachiningNoteHandler (cadmind-machining-note)
  - TierBWave11Handlers.cs: SheetNumberHandler (cadmind-sheet-number)
  - TierBWave13Handlers.cs: SurfaceAreaHandler (cadmind-surface-area)
  - TierBWave13Handlers.cs: DivideMeasureHandler (cadmind-divide-measure)

Pure Python 3.11, strongly-typed IR (Point2D, LineSegment2D, Arc2D, CircleIR),
strict IEEE-754 machine-epsilon safety, Banker's rounding alignment,
and zero external pip dependencies.
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


# ============================================================================
# INTERNAL IEEE-754 VALIDATION HELPERS
# ============================================================================


def _validate_finite(val: float, name: str) -> float:
    """Ensure value is finite (not NaN, not Inf)."""
    if not isinstance(val, (int, float)) or isinstance(val, bool) or math.isnan(val) or math.isinf(val):
        raise DegenerateGeometryError(f"DEGENERATE_GEOMETRY: Numeric arguments must be finite numbers ({name}={val}).")
    return float(val)


def _normalize_angle(angle: float) -> float:
    """Normalize angle into [0, 2*pi) matching C# NormalizeAngle."""
    two_pi = 2.0 * math.pi
    angle %= two_pi
    if angle < 0.0:
        angle += two_pi
    return angle


# ============================================================================
# 1. RIVET PIN (cadmind-rivet-pin) - TierBWave10Handlers.cs
# ============================================================================


@dataclass(frozen=True)
class RivetPinArgs:
    """Input parameters for RivetPinHandler."""

    origin_x: float = 0.0
    origin_y: float = 0.0
    shank_diameter: float = 10.0
    shank_length: float = 50.0
    head_diameter: float = 0.0
    head_height: float = 0.0
    rotation_deg: float = 0.0
    layer: str = "M-FASTENER-RIVET"


@dataclass(frozen=True)
class RivetPinResult:
    """Output result and strongly-typed IR geometry for RivetPinHandler."""

    status: str
    message: str
    layer: str
    entity_count: int
    shank_diameter: float
    shank_length: float
    head_diameter: float
    head_height: float
    r_arc: float
    base_line: LineSegment2D
    dome_arc: Arc2D
    shank_segments: Tuple[LineSegment2D, LineSegment2D, LineSegment2D, LineSegment2D]
    centerline: LineSegment2D


class RivetPinHandler:
    """Cleanroom port of CadMind RivetPinHandler from TierBWave10Handlers.cs."""

    def execute(self, args: RivetPinArgs) -> RivetPinResult:
        ox = _validate_finite(args.origin_x, "OriginX")
        oy = _validate_finite(args.origin_y, "OriginY")
        d = _validate_finite(args.shank_diameter, "ShankDiameter")
        L = _validate_finite(args.shank_length, "ShankLength")
        hd_in = _validate_finite(args.head_diameter, "HeadDiameter")
        hh_in = _validate_finite(args.head_height, "HeadHeight")
        rot = _validate_finite(args.rotation_deg, "RotationDeg")

        if d <= 1e-4 or L <= 1e-4:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: ShankDiameter and ShankLength must be positive.")

        if hd_in < 0.0 or hh_in < 0.0:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: HeadDiameter and HeadHeight must not be negative.")

        Dh = 1.75 * d if abs(hd_in) <= 1e-6 else hd_in
        Hh = 0.75 * d if abs(hh_in) <= 1e-6 else hh_in

        if Dh <= d + 1e-4:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: HeadDiameter must strictly exceed ShankDiameter.")

        if Hh <= 1e-4 or Hh > Dh:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: HeadHeight must be positive and not exceed HeadDiameter.")

        layer = args.layer.strip() if args.layer and args.layer.strip() else "M-FASTENER-RIVET"

        rad = rot * math.pi / 180.0
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)

        def transform_point(lx: float, ly: float) -> Point2D:
            gx = ox + (lx * cos_r) - (ly * sin_r)
            gy = oy + (lx * sin_r) + (ly * cos_r)
            return Point2D(gx, gy)

        # 1. Head Base Line
        base_line = LineSegment2D(transform_point(0.0, -Dh / 2.0), transform_point(0.0, +Dh / 2.0))

        # 2. Button Head Dome Arc (Sagitta formula)
        r_arc = (Hh / 2.0) + ((Dh * Dh) / (8.0 * Hh))
        c_local_x = r_arc - Hh
        arc_center = transform_point(c_local_x, 0.0)

        local_angle_top = math.atan2(+Dh / 2.0, -c_local_x)
        local_angle_bot = math.atan2(-Dh / 2.0, -c_local_x)

        start_angle = _normalize_angle(local_angle_top + rad)
        end_angle = _normalize_angle(local_angle_bot + rad)
        dome_arc = Arc2D(center=arc_center, radius=r_arc, start_angle_rad=start_angle, end_angle_rad=end_angle)

        # 3. Shank Outline (4 vertices closed loop)
        p0 = transform_point(0.0, -d / 2.0)
        p1 = transform_point(L, -d / 2.0)
        p2 = transform_point(L, +d / 2.0)
        p3 = transform_point(0.0, +d / 2.0)
        shank_segments = (
            LineSegment2D(p0, p1),
            LineSegment2D(p1, p2),
            LineSegment2D(p2, p3),
            LineSegment2D(p3, p0),
        )

        # 4. Centerline
        cl_start = -Hh - (0.25 * d)
        cl_end = L + (0.25 * d)
        centerline = LineSegment2D(transform_point(cl_start, 0.0), transform_point(cl_end, 0.0))

        return RivetPinResult(
            status="OK",
            message="Rivet pin generated successfully.",
            layer=layer,
            entity_count=4,  # Matches C# handles.Count (baseLine, domeArc, shankPoly, cl)
            shank_diameter=d,
            shank_length=L,
            head_diameter=Dh,
            head_height=Hh,
            r_arc=r_arc,
            base_line=base_line,
            dome_arc=dome_arc,
            shank_segments=shank_segments,
            centerline=centerline,
        )


# ============================================================================
# 2. MACHINING NOTE (cadmind-machining-note) - TierBWave11Handlers.cs
# ============================================================================


@dataclass(frozen=True)
class MachiningNoteArgs:
    """Input parameters for MachiningNoteHandler."""

    target_x: float = 0.0
    target_y: float = 0.0
    landing_x: float = 15.0
    landing_y: float = 10.0
    note_text: str = "FINISH TURN"
    sub_note: str | None = None
    text_height: float = 2.5
    arrow_size: float = 3.0
    layer: str = "M-ANNO-NOTE"


@dataclass(frozen=True)
class MachiningNoteResult:
    """Output result and strongly-typed IR geometry for MachiningNoteHandler."""

    status: str
    message: str
    layer: str
    entity_count: int
    note_text: str
    sub_note: str | None
    arrowhead: Tuple[LineSegment2D, LineSegment2D, LineSegment2D]
    leader_line: LineSegment2D
    shelf_line: LineSegment2D
    primary_text_pos: Point2D
    primary_text_height: float
    sub_text_pos: Point2D | None
    sub_text_height: float | None


class MachiningNoteHandler:
    """Cleanroom port of CadMind MachiningNoteHandler from TierBWave11Handlers.cs."""

    def execute(self, args: MachiningNoteArgs) -> MachiningNoteResult:
        tx = _validate_finite(args.target_x, "TargetX")
        ty = _validate_finite(args.target_y, "TargetY")
        lx = _validate_finite(args.landing_x, "LandingX")
        ly = _validate_finite(args.landing_y, "LandingY")
        ht = _validate_finite(args.text_height, "TextHeight")
        a_size = _validate_finite(args.arrow_size, "ArrowSize")

        dx = lx - tx
        dy = ly - ty
        leader_len = math.hypot(dx, dy)
        if leader_len < 1e-3:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Target and landing points must not be coincident.")

        if not args.note_text or not args.note_text.strip():
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: NoteText must not be empty.")

        if ht <= 1e-4 or a_size <= 1e-4:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: TextHeight and ArrowSize must be positive.")

        layer = args.layer.strip() if args.layer and args.layer.strip() else "M-ANNO-NOTE"

        ux = dx / leader_len
        uy = dy / leader_len
        nx = -uy
        ny = ux

        # 1. Closed Arrowhead Polyline (3 segments)
        v0 = Point2D(tx, ty)
        v1 = Point2D(tx + a_size * ux + 0.35 * a_size * nx, ty + a_size * uy + 0.35 * a_size * ny)
        v2 = Point2D(tx + a_size * ux - 0.35 * a_size * nx, ty + a_size * uy - 0.35 * a_size * ny)
        arrowhead = (
            LineSegment2D(v0, v1),
            LineSegment2D(v1, v2),
            LineSegment2D(v2, v0),
        )

        # 2. Angled Leader Line
        leader_line = LineSegment2D(v0, Point2D(lx, ly))

        # 3. Horizontal Shelf Line
        sigma = 1.0 if lx >= tx else -1.0
        shelf_len = max(4.0 * ht, len(args.note_text.strip()) * 0.75 * ht)
        shelf_end_x = lx + sigma * shelf_len
        shelf_end_y = ly
        shelf_line = LineSegment2D(Point2D(lx, ly), Point2D(shelf_end_x, shelf_end_y))

        # 4. Primary Note Text
        text_start_x = min(lx, shelf_end_x) + 0.2 * ht
        primary_text_pos = Point2D(text_start_x, ly + 0.35 * ht)

        # 5. Optional SubNote Text
        sub_text_pos = None
        sub_text_height = None
        has_sub = bool(args.sub_note and args.sub_note.strip())
        if has_sub:
            sub_text_pos = Point2D(text_start_x, ly - 1.35 * ht)
            sub_text_height = 0.85 * ht

        entity_count = 5 if has_sub else 4

        return MachiningNoteResult(
            status="OK",
            message=f"Machining note placed successfully ({entity_count} entities).",
            layer=layer,
            entity_count=entity_count,
            note_text=args.note_text.strip(),
            sub_note=args.sub_note.strip() if has_sub else None,
            arrowhead=arrowhead,
            leader_line=leader_line,
            shelf_line=shelf_line,
            primary_text_pos=primary_text_pos,
            primary_text_height=ht,
            sub_text_pos=sub_text_pos,
            sub_text_height=sub_text_height,
        )


# ============================================================================
# 3. SHEET NUMBER (cadmind-sheet-number) - TierBWave11Handlers.cs
# ============================================================================


@dataclass(frozen=True)
class SheetBadgeIR:
    """Intermediate Representation of an individual sheet badge."""

    center: Point2D
    radius: float
    circle: CircleIR
    divider: LineSegment2D
    upper_text: str
    upper_text_pos: Point2D
    upper_text_height: float
    lower_text: str
    lower_text_pos: Point2D
    lower_text_height: float
    title_line: LineSegment2D | None = None
    title_text: str | None = None
    title_text_pos: Point2D | None = None
    title_text_height: float | None = None


@dataclass(frozen=True)
class SheetNumberArgs:
    """Input parameters for SheetNumberHandler."""

    center_x: float = 0.0
    center_y: float = 0.0
    radius: float = 6.0
    sheet_no: str = "A-101"
    total_sheets: str = "10"
    sheet_title: str | None = None
    count: int = 1
    batch_step_x: float = 0.0
    text_height: float = 2.5
    layer: str = "G-ANNO-TTLB"


@dataclass(frozen=True)
class SheetNumberResult:
    """Output result and strongly-typed IR geometry for SheetNumberHandler."""

    status: str
    message: str
    layer: str
    entity_count: int
    sheet_no: str
    total_sheets: str
    count: int
    badges: List[SheetBadgeIR]


class SheetNumberHandler:
    """Cleanroom port of CadMind SheetNumberHandler from TierBWave11Handlers.cs."""

    def execute(self, args: SheetNumberArgs) -> SheetNumberResult:
        cx_base = _validate_finite(args.center_x, "CenterX")
        cy_base = _validate_finite(args.center_y, "CenterY")
        r = _validate_finite(args.radius, "Radius")
        ht_in = _validate_finite(args.text_height, "TextHeight")
        step_x = _validate_finite(args.batch_step_x, "BatchStepX")

        if r <= 1e-4:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Radius must be positive.")

        if ht_in <= 1e-4:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: TextHeight must be positive.")

        if not args.sheet_no or not args.sheet_no.strip():
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: SheetNo must not be empty.")

        if not isinstance(args.count, int) or isinstance(args.count, bool) or args.count < 1:
            raise DegenerateGeometryError("DEGENERATE_GEOMETRY: Count must be at least 1.")

        if args.count > 1 and abs(step_x) < 2.0 * r:
            raise DegenerateGeometryError(
                "DEGENERATE_GEOMETRY: BatchStepX magnitude must be at least 2 * Radius to avoid overlapping badges."
            )

        layer = args.layer.strip() if args.layer and args.layer.strip() else "G-ANNO-TTLB"
        ht = min(ht_in, 0.42 * r)
        has_title = bool(args.sheet_title and args.sheet_title.strip())

        badges: List[SheetBadgeIR] = []
        total_entities = 0

        # Alphanumeric start number parsing
        sheet_no_trimmed = args.sheet_no.strip()
        parsed_start_num: int | None = None
        try:
            parsed_start_num = int(sheet_no_trimmed)
        except ValueError:
            parsed_start_num = None

        for i in range(args.count):
            cx = cx_base + i * step_x
            cy = cy_base

            # 1. Outer Circle
            circle = CircleIR(center=Point2D(cx, cy), radius=r, index=i)

            # 2. Horizontal Divider Line
            divider = LineSegment2D(Point2D(cx - r, cy), Point2D(cx + r, cy))

            # 3. Upper Hemisphere SheetNo DBText
            if args.count > 1 and parsed_start_num is not None:
                current_no = str(parsed_start_num + i)
            elif args.count > 1:
                current_no = f"{sheet_no_trimmed}-{i + 1}"
            else:
                current_no = sheet_no_trimmed

            upper_pos = Point2D(cx, cy + 0.22 * r)
            upper_height = ht

            # 4. Lower Hemisphere TotalSheets DBText
            total_sheets_trimmed = args.total_sheets.strip() if args.total_sheets else ""
            total_str = "SHEET" if not total_sheets_trimmed else f"OF {total_sheets_trimmed}"
            lower_pos = Point2D(cx, cy - 0.55 * r)
            lower_height = 0.75 * ht

            # 5. Optional SheetTitle extension
            title_line = None
            title_text = None
            title_text_pos = None
            title_text_height = None
            if has_title:
                t_str = args.sheet_title.strip()  # type: ignore[union-attr]
                title_len = max(5.0 * ht, len(t_str) * 0.75 * ht)
                title_line = LineSegment2D(Point2D(cx + r, cy), Point2D(cx + r + title_len, cy))
                title_text = t_str
                title_text_pos = Point2D(cx + r + 0.4 * ht, cy + 0.25 * ht)
                title_text_height = ht
                total_entities += 6
            else:
                total_entities += 4

            badges.append(
                SheetBadgeIR(
                    center=Point2D(cx, cy),
                    radius=r,
                    circle=circle,
                    divider=divider,
                    upper_text=current_no,
                    upper_text_pos=upper_pos,
                    upper_text_height=upper_height,
                    lower_text=total_str,
                    lower_text_pos=lower_pos,
                    lower_text_height=lower_height,
                    title_line=title_line,
                    title_text=title_text,
                    title_text_pos=title_text_pos,
                    title_text_height=title_text_height,
                )
            )

        return SheetNumberResult(
            status="OK",
            message=f"Sheet number placed successfully ({total_entities} entities).",
            layer=layer,
            entity_count=total_entities,
            sheet_no=sheet_no_trimmed,
            total_sheets=args.total_sheets.strip() if args.total_sheets else "",
            count=args.count,
            badges=badges,
        )


# ============================================================================
# 4. SURFACE AREA (cadmind-surface-area) - TierBWave13Handlers.cs
# ============================================================================


@dataclass(frozen=True)
class SurfaceAreaItem:
    """Individual face calculation result with Banker's rounding parity."""

    handle: str
    face_area_mm2: float
    perimeter_mm: float
    surface_area_mm2: float


@dataclass(frozen=True)
class SurfaceAreaArgs:
    """Input parameters for SurfaceAreaHandler."""

    profiles: Sequence[Sequence[Point2D] | CircleIR]
    handles: Sequence[str] | None = None
    thickness: float = 0.0
    decimals: int = 1


@dataclass(frozen=True)
class SurfaceAreaResult:
    """Output summary for SurfaceAreaHandler matching C# SurfaceAreaResult."""

    status: str
    message: str
    total_face_area_mm2: float
    total_face_area_cm2: float
    total_surface_area_mm2: float
    total_surface_area_cm2: float
    item_count: int
    items: List[SurfaceAreaItem]
    skipped: List[str]


class SurfaceAreaHandler:
    """Cleanroom port of CadMind SurfaceAreaHandler from TierBWave13Handlers.cs."""

    def execute(self, args: SurfaceAreaArgs) -> SurfaceAreaResult:
        if not args.profiles and not args.handles:
            raise ValueError("EMPTY_INPUT: At least one entity handle must be provided.")

        if not isinstance(args.thickness, (int, float)) or isinstance(args.thickness, bool) or math.isnan(args.thickness) or math.isinf(args.thickness) or args.thickness < 0.0:
            raise ValueError("INVALID_THICKNESS: Thickness must be non-negative and finite.")

        th = float(args.thickness)

        if not isinstance(args.decimals, int) or isinstance(args.decimals, bool) or not (0 <= args.decimals <= 8):
            raise ValueError("INVALID_DECIMALS: Decimals must be between 0 and 8.")

        dec = args.decimals
        profiles = list(args.profiles)
        handles = list(args.handles) if args.handles else [f"{1000 + idx:X}" for idx in range(len(profiles))]

        items: List[SurfaceAreaItem] = []
        skipped: List[str] = []
        total_face_mm2 = 0.0
        total_surface_mm2 = 0.0

        for idx, prof in enumerate(profiles):
            h_str = handles[idx] if idx < len(handles) else f"{1000 + idx:X}"

            try:
                area = 0.0
                perim = 0.0

                if isinstance(prof, CircleIR):
                    area = math.pi * prof.radius * prof.radius
                    perim = 2.0 * math.pi * prof.radius
                elif isinstance(prof, (list, tuple)):
                    pts = list(prof)
                    if len(pts) < 3:
                        skipped.append(h_str)
                        continue

                    # Shoelace polygon area & perimeter
                    n = len(pts)
                    area_sum = 0.0
                    perim_sum = 0.0
                    for j in range(n):
                        p1 = pts[j]
                        p2 = pts[(j + 1) % n]
                        area_sum += p1.x * p2.y - p2.x * p1.y
                        perim_sum += math.hypot(p2.x - p1.x, p2.y - p1.y)

                    area = 0.5 * abs(area_sum)
                    perim = perim_sum
                else:
                    skipped.append(h_str)
                    continue

                if area <= 1e-6 or perim <= 1e-6:
                    skipped.append(h_str)
                    continue

                surf = (2.0 * area + perim * th) if th > 0.0 else area

                # Per-item Banker's rounding
                items.append(
                    SurfaceAreaItem(
                        handle=h_str,
                        face_area_mm2=round(area, dec),
                        perimeter_mm=round(perim, dec),
                        surface_area_mm2=round(surf, dec),
                    )
                )

                # C# accumulates unrounded sums
                total_face_mm2 += area
                total_surface_mm2 += surf

            except Exception:
                skipped.append(h_str)

        return SurfaceAreaResult(
            status="SUCCESS",
            message=f"Calculated surface area across {len(items)} closed faces.",
            total_face_area_mm2=round(total_face_mm2, dec),
            total_face_area_cm2=round(total_face_mm2 / 100.0, dec),
            total_surface_area_mm2=round(total_surface_mm2, dec),
            total_surface_area_cm2=round(total_surface_mm2 / 100.0, dec),
            item_count=len(items),
            items=items,
            skipped=skipped,
        )


# ============================================================================
# 5. DIVIDE & MEASURE (cadmind-divide-measure) - TierBWave13Handlers.cs
# ============================================================================


@dataclass(frozen=True)
class DivideMeasureArgs:
    """Input parameters for DivideMeasureHandler."""

    curves: Sequence[LineSegment2D | Arc2D | Sequence[Point2D]]
    mode: str = "divide"
    n: int | None = None
    distance: float | None = None
    layer: str = "MARKS"
    marker: str = "point"
    align: bool = True
    handles: Sequence[str] | None = None


@dataclass(frozen=True)
class DivideMeasureResult:
    """Output summary for DivideMeasureHandler matching C# DivideMeasureResult."""

    status: str
    message: str
    marker_count: int
    processed_curves: int
    skipped_curves: int
    marker_points: List[Point2D]


class DivideMeasureHandler:
    """Cleanroom port of CadMind DivideMeasureHandler from TierBWave13Handlers.cs."""

    @staticmethod
    def _curve_length(curve: LineSegment2D | Arc2D | Sequence[Point2D]) -> float:
        if isinstance(curve, LineSegment2D):
            return curve.length
        elif isinstance(curve, Arc2D):
            sweep = curve.end_angle_rad - curve.start_angle_rad
            if sweep < 0.0:
                sweep += 2.0 * math.pi
            return curve.radius * sweep
        elif isinstance(curve, (list, tuple)):
            pts = list(curve)
            if len(pts) < 2:
                return 0.0
            return sum(math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y) for i in range(len(pts) - 1))
        return 0.0

    @staticmethod
    def _point_at_dist(curve: LineSegment2D | Arc2D | Sequence[Point2D], dist: float) -> Point2D:
        if isinstance(curve, LineSegment2D):
            ratio = dist / curve.length if curve.length > 0 else 0.0
            return Point2D(
                curve.start.x + ratio * (curve.end.x - curve.start.x),
                curve.start.y + ratio * (curve.end.y - curve.start.y),
            )
        elif isinstance(curve, Arc2D):
            sweep = curve.end_angle_rad - curve.start_angle_rad
            if sweep < 0.0:
                sweep += 2.0 * math.pi
            ang = curve.start_angle_rad + (dist / (curve.radius * sweep)) * sweep
            return Point2D(
                curve.center.x + curve.radius * math.cos(ang),
                curve.center.y + curve.radius * math.sin(ang),
            )
        elif isinstance(curve, (list, tuple)):
            pts = list(curve)
            accum = 0.0
            for i in range(len(pts) - 1):
                seg_len = math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y)
                if accum + seg_len >= dist:
                    rem = dist - accum
                    ratio = rem / seg_len if seg_len > 0 else 0.0
                    return Point2D(
                        pts[i].x + ratio * (pts[i + 1].x - pts[i].x),
                        pts[i].y + ratio * (pts[i + 1].y - pts[i].y),
                    )
                accum += seg_len
            return pts[-1]
        raise ValueError("Unsupported curve primitive.")

    def execute(self, args: DivideMeasureArgs) -> DivideMeasureResult:
        if not args.curves:
            raise ValueError("EMPTY_INPUT: At least one entity handle must be provided.")

        mode = (args.mode or "").strip().lower()
        if mode not in ("divide", "measure"):
            raise ValueError("INVALID_MODE: Mode must be either 'divide' or 'measure'.")

        if mode == "divide":
            if not isinstance(args.n, int) or isinstance(args.n, bool) or args.n < 2:
                raise ValueError("INVALID_N: Divide mode requires N >= 2 segments.")
        elif mode == "measure":
            if args.distance is None or not isinstance(args.distance, (int, float)) or isinstance(args.distance, bool):
                raise ValueError("INVALID_DISTANCE: Measure mode requires distance > 0.")
            if math.isnan(args.distance) or math.isinf(args.distance) or args.distance <= 0.0:
                raise ValueError("INVALID_DISTANCE: Measure mode requires distance > 0.")

        marker_points: List[Point2D] = []
        processed = 0
        skipped = 0

        for curve in args.curves:
            try:
                total_len = self._curve_length(curve)
                if total_len <= 1e-6:
                    skipped += 1
                    continue

                if mode == "divide":
                    parts = args.n  # type: ignore[assignment]
                    step = total_len / parts
                    for k in range(1, parts):
                        pt = self._point_at_dist(curve, k * step)
                        marker_points.append(pt)
                    processed += 1

                elif mode == "measure":
                    dist = float(args.distance)  # type: ignore[arg-type]
                    d = dist
                    while d < total_len - 1e-4:
                        pt = self._point_at_dist(curve, d)
                        marker_points.append(pt)
                        d += dist
                    processed += 1

            except Exception:
                skipped += 1

        marker_count = len(marker_points)
        return DivideMeasureResult(
            status="SUCCESS",
            message=f"Placed {marker_count} markers across {processed} curves.",
            marker_count=marker_count,
            processed_curves=processed,
            skipped_curves=skipped,
            marker_points=marker_points,
        )
