"""
cleanroom_fasteners_annotations.py
Production-grade cleanroom implementation of mechanical fasteners and manufacturing annotations:
1. KeywaySlot (Cross-section and top slot profiles)
2. HexBolt (Standard ISO bolt profile representation)
3. ThreadRod (Threaded rod profile with chamfer and minor diameter)
4. WeldSymbol (ISO 2553 / AWS welding symbol)
5. SurfaceFinish (ISO 1302 surface texture symbol)
"""

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import List, Optional, Union

from cad_agent.cleanroom_mechanical import (
    Arc2D,
    LineSegment2D,
    Point2D,
)


def _validate_finite_positive(val: float, name: str) -> float:
    """Validate that a value is a finite, positive IEEE-754 float."""
    if not isinstance(val, (int, float)):
        raise TypeError(f"Parameter '{name}' must be numeric, got {type(val)}")
    f_val = float(val)
    if not math.isfinite(f_val):
        raise ValueError(f"Parameter '{name}' must be finite, got {f_val}")
    if f_val <= 0.0:
        raise ValueError(f"Parameter '{name}' must be positive (> 0), got {f_val}")
    return f_val


def _validate_non_negative(val: float, name: str) -> float:
    """Validate that a value is a finite, non-negative IEEE-754 float."""
    if not isinstance(val, (int, float)):
        raise TypeError(f"Parameter '{name}' must be numeric, got {type(val)}")
    f_val = float(val)
    if not math.isfinite(f_val):
        raise ValueError(f"Parameter '{name}' must be finite, got {f_val}")
    if f_val < 0.0:
        raise ValueError(f"Parameter '{name}' must be non-negative (>= 0), got {f_val}")
    return f_val


# ============================================================================
# 1. KEYWAY SLOT HANDLER
# ============================================================================


class KeywaySlotType(str, Enum):
    CROSS_SECTION = "cross_section"
    TOP_SLOT = "top_slot"


@dataclass
class KeywaySlotParams:
    shaft_diameter: float
    width: float
    depth: float
    slot_type: KeywaySlotType = KeywaySlotType.CROSS_SECTION
    center: Point2D = field(default_factory=lambda: Point2D(0.0, 0.0))

    def __post_init__(self):
        self.shaft_diameter = _validate_finite_positive(self.shaft_diameter, "shaft_diameter")
        self.width = _validate_finite_positive(self.width, "width")
        self.depth = _validate_finite_positive(self.depth, "depth")

        if self.width >= 0.6 * self.shaft_diameter:
            raise ValueError(
                f"Keyway width ({self.width}) must be < 0.6 * shaft_diameter ({0.6 * self.shaft_diameter})"
            )
        if self.depth >= 0.5 * self.shaft_diameter:
            raise ValueError(
                f"Keyway depth ({self.depth}) must be < 0.5 * shaft_diameter ({0.5 * self.shaft_diameter})"
            )


class KeywaySlotHandler:
    """Generates closed boundary primitive IR (LineSegment2D, Arc2D) for shaft keyway slots."""

    @staticmethod
    def generate(params: KeywaySlotParams) -> List[Union[LineSegment2D, Arc2D]]:
        D = params.shaft_diameter
        w = params.width
        t1 = params.depth
        cx, cy = params.center.x, params.center.y
        rad = D / 2.0

        primitives: List[Union[LineSegment2D, Arc2D]] = []

        if params.slot_type == KeywaySlotType.CROSS_SECTION:
            # Shaft outer arc from rad+alpha to rad-alpha, alpha = asin(w/D), left/bottom/right slot walls
            # Half-width at chord
            half_w = w / 2.0
            if half_w >= rad:
                raise ValueError("Keyway half-width exceeds shaft radius.")

            alpha = math.asin(half_w / rad)
            # Slot bottom depth from center: r_bottom = rad - t1
            r_bottom = rad - t1

            # Compute x intersection of slot wall with shaft circle at depth:
            # x_wall = half_w
            # y_wall on slot bottom is cy + r_bottom (assuming vertical slot oriented upwards)
            # More precisely, let's establish standard vertical orientation (keyway at top of shaft):
            # Shaft center at (cx, cy).
            # Slot walls rise vertically from bottom floor at y = cy + rad - t1 at x = cx - half_w and x = cx + half_w.
            # They intersect the shaft circle at y_intersect = cy + sqrt(rad^2 - half_w^2).

            y_floor = cy + rad - t1
            x_left = cx - half_w
            x_right = cx + half_w
            y_intersect = cy + math.sqrt(max(0.0, rad**2 - half_w**2))

            # 1. Floor line (horizontal segment at bottom of slot)
            primitives.append(
                LineSegment2D(start=Point2D(x_left, y_floor), end=Point2D(x_right, y_floor))
            )
            # 2. Left vertical wall segment
            primitives.append(
                LineSegment2D(start=Point2D(x_left, y_floor), end=Point2D(x_left, y_intersect))
            )
            # 3. Right vertical wall segment
            primitives.append(
                LineSegment2D(start=Point2D(x_right, y_floor), end=Point2D(x_right, y_intersect))
            )
            # 4. Shaft outer arc remaining boundary
            # Arc from angle pi/2 + alpha to pi/2 - alpha counter-clockwise around shaft center (cx, cy)
            start_angle = math.pi / 2.0 + alpha
            end_angle = math.pi / 2.0 - alpha
            primitives.append(
                Arc2D(
                    center=Point2D(cx, cy),
                    radius=rad,
                    start_angle_rad=start_angle,
                    end_angle_rad=end_angle,
                )
            )

        elif params.slot_type == KeywaySlotType.TOP_SLOT:
            # Obround / rectangular slot profile in flat view
            length = params.depth * 2.0  # proportional length or derived from slot specs
            half_w = w / 2.0
            # Symmetrical obround slot centered at (cx, cy)
            x0 = cx - length / 2.0 + half_w
            x1 = cx + length / 2.0 - half_w

            # Straight sides
            primitives.append(
                LineSegment2D(start=Point2D(x0, cy + half_w), end=Point2D(x1, cy + half_w))
            )
            primitives.append(
                LineSegment2D(start=Point2D(x0, cy - half_w), end=Point2D(x1, cy - half_w))
            )
            # End semicircles
            primitives.append(
                Arc2D(
                    center=Point2D(x0, cy),
                    radius=half_w,
                    start_angle_rad=math.pi / 2,
                    end_angle_rad=3 * math.pi / 2,
                )
            )
            primitives.append(
                Arc2D(
                    center=Point2D(x1, cy),
                    radius=half_w,
                    start_angle_rad=3 * math.pi / 2,
                    end_angle_rad=math.pi / 2,
                )
            )

        return primitives


# ============================================================================
# 2. HEX BOLT HANDLER
# ============================================================================


@dataclass
class HexBoltParams:
    nominal_diameter: float  # d
    shank_length: float  # L
    thread_length: float  # Lt
    include_centerline: bool = True
    origin: Point2D = field(default_factory=lambda: Point2D(0.0, 0.0))

    def __post_init__(self):
        self.nominal_diameter = _validate_finite_positive(self.nominal_diameter, "nominal_diameter")
        self.shank_length = _validate_finite_positive(self.shank_length, "shank_length")
        self.thread_length = _validate_finite_positive(self.thread_length, "thread_length")
        if self.thread_length > self.shank_length:
            raise ValueError("Thread length Lt cannot exceed shank length L.")

    @property
    def head_height(self) -> float:
        return 0.7 * self.nominal_diameter

    @property
    def across_corners_width(self) -> float:
        return 2.0 * self.nominal_diameter


class HexBoltHandler:
    """Generates standard ISO hex bolt profile representation."""

    @staticmethod
    def generate(params: HexBoltParams) -> List[Union[LineSegment2D, Arc2D]]:
        d = params.nominal_diameter
        L = params.shank_length
        Lt = params.thread_length
        cx, cy = params.origin.x, params.origin.y

        k = 0.7 * d  # Head height
        e = 2.0 * d  # Across-corners width
        r_shank = d / 2.0

        primitives: List[Union[LineSegment2D, Arc2D]] = []

        # Head outline (rect representation of head extending upwards from origin y=0 to y=k)
        # Head width across flats is s = e * sqrt(3)/2 approx d*1.732, but using across-corners e for outer envelope
        head_half_w = e / 2.0
        # Head box: from y = 0 to y = k, x from -head_half_w to +head_half_w
        primitives.append(
            LineSegment2D(start=Point2D(cx - head_half_w, cy), end=Point2D(cx + head_half_w, cy))
        )  # base of head
        primitives.append(
            LineSegment2D(
                start=Point2D(cx - head_half_w, cy + k), end=Point2D(cx + head_half_w, cy + k)
            )
        )  # top of head
        primitives.append(
            LineSegment2D(
                start=Point2D(cx - head_half_w, cy), end=Point2D(cx - head_half_w, cy + k)
            )
        )  # left head wall
        primitives.append(
            LineSegment2D(
                start=Point2D(cx + head_half_w, cy), end=Point2D(cx + head_half_w, cy + k)
            )
        )  # right head wall

        # Hex flats division lines at -e/4 and +e/4 inside head
        primitives.append(
            LineSegment2D(start=Point2D(cx - e / 4.0, cy), end=Point2D(cx - e / 4.0, cy + k))
        )
        primitives.append(
            LineSegment2D(start=Point2D(cx + e / 4.0, cy), end=Point2D(cx + e / 4.0, cy + k))
        )

        # Shank outline extending downwards from y = 0 to y = -L
        shank_tip_y = cy - L
        primitives.append(
            LineSegment2D(start=Point2D(cx - r_shank, cy), end=Point2D(cx - r_shank, shank_tip_y))
        )
        primitives.append(
            LineSegment2D(start=Point2D(cx + r_shank, cy), end=Point2D(cx + r_shank, shank_tip_y))
        )
        # Shank bottom tip
        primitives.append(
            LineSegment2D(
                start=Point2D(cx - r_shank, shank_tip_y), end=Point2D(cx + r_shank, shank_tip_y)
            )
        )

        # Thread limit line at y = cy - (L - Lt)
        thread_start_y = cy - (L - Lt)
        primitives.append(
            LineSegment2D(
                start=Point2D(cx - r_shank, thread_start_y),
                end=Point2D(cx + r_shank, thread_start_y),
            )
        )

        # Minor thread diameter lines (at +/- 0.85 * d / 2) from thread_start_y to shank_tip_y
        r_minor = 0.85 * r_shank
        primitives.append(
            LineSegment2D(
                start=Point2D(cx - r_minor, thread_start_y), end=Point2D(cx - r_minor, shank_tip_y)
            )
        )
        primitives.append(
            LineSegment2D(
                start=Point2D(cx + r_minor, thread_start_y), end=Point2D(cx + r_minor, shank_tip_y)
            )
        )

        # Optional centerline
        if params.include_centerline:
            primitives.append(
                LineSegment2D(start=Point2D(cx, cy + k + 2.0), end=Point2D(cx, shank_tip_y - 2.0))
            )

        return primitives


# ============================================================================
# 3. THREADED ROD HANDLER
# ============================================================================


@dataclass
class ThreadRodParams:
    major_diameter: float
    length: float
    pitch: float = 1.5
    include_centerline: bool = True
    origin: Point2D = field(default_factory=lambda: Point2D(0.0, 0.0))

    def __post_init__(self):
        self.major_diameter = _validate_finite_positive(self.major_diameter, "major_diameter")
        self.length = _validate_finite_positive(self.length, "length")
        self.pitch = _validate_finite_positive(self.pitch, "pitch")


class ThreadRodHandler:
    """Generates threaded rod profile with chamfer and minor diameter representations."""

    @staticmethod
    def generate(params: ThreadRodParams) -> List[Union[LineSegment2D, Arc2D]]:
        d = params.major_diameter
        L = params.length
        pitch = params.pitch
        cx, cy = params.origin.x, params.origin.y

        r_major = d / 2.0
        dr = d - 1.0825 * pitch
        r_minor = max(0.1 * r_major, dr / 2.0)
        c = 0.1 * d  # Chamfer size

        primitives: List[Union[LineSegment2D, Arc2D]] = []

        # Outer chamfered profile (8 vertices total or simplified envelope with chamfered tips at top & bottom)
        # Top end: y from cy to cy + L
        y_top = cy + L
        y_bottom = cy

        # Top chamfered points
        # Left side: from (cx - r_major + c, y_top) to (cx - r_major, y_top - c)
        primitives.append(
            LineSegment2D(
                start=Point2D(cx - r_major + c, y_top), end=Point2D(cx - r_major, y_top - c)
            )
        )
        # Top flat / edge
        primitives.append(
            LineSegment2D(
                start=Point2D(cx - r_major + c, y_top), end=Point2D(cx + r_major - c, y_top)
            )
        )
        # Right top chamfer
        primitives.append(
            LineSegment2D(
                start=Point2D(cx + r_major - c, y_top), end=Point2D(cx + r_major, y_top - c)
            )
        )

        # Bottom chamfered points
        primitives.append(
            LineSegment2D(
                start=Point2D(cx - r_major + c, y_bottom), end=Point2D(cx - r_major, y_bottom + c)
            )
        )
        primitives.append(
            LineSegment2D(
                start=Point2D(cx - r_major + c, y_bottom), end=Point2D(cx + r_major - c, y_bottom)
            )
        )
        primitives.append(
            LineSegment2D(
                start=Point2D(cx + r_major - c, y_bottom), end=Point2D(cx + r_major, y_bottom + c)
            )
        )

        # Left and right outer major diameter vertical walls (between chamfers)
        primitives.append(
            LineSegment2D(
                start=Point2D(cx - r_major, y_top - c), end=Point2D(cx - r_major, y_bottom + c)
            )
        )
        primitives.append(
            LineSegment2D(
                start=Point2D(cx + r_major, y_top - c), end=Point2D(cx + r_major, y_bottom + c)
            )
        )

        # Minor diameter dashed/solid lines inside
        primitives.append(
            LineSegment2D(
                start=Point2D(cx - r_minor, y_top - c), end=Point2D(cx - r_minor, y_bottom + c)
            )
        )
        primitives.append(
            LineSegment2D(
                start=Point2D(cx + r_minor, y_top - c), end=Point2D(cx + r_minor, y_bottom + c)
            )
        )

        # Centerline
        if params.include_centerline:
            primitives.append(
                LineSegment2D(start=Point2D(cx, y_top + 2.0), end=Point2D(cx, y_bottom - 2.0))
            )

        return primitives


# ============================================================================
# 4. WELD SYMBOL HANDLER
# ============================================================================


class WeldType(str, Enum):
    FILLET = "fillet"
    SQUARE_GROOVE = "square_groove"
    V_GROOVE = "v_groove"
    PLUG = "plug"


@dataclass
class WeldSymbolParams:
    origin: Point2D
    weld_type: WeldType = WeldType.FILLET
    reference_length: float = 25.0
    height: float = 5.0
    all_around: bool = False
    process_note: Optional[str] = None

    def __post_init__(self):
        self.reference_length = _validate_finite_positive(self.reference_length, "reference_length")
        self.height = _validate_finite_positive(self.height, "height")


class WeldSymbolHandler:
    """Generates ISO 2553 / AWS weld symbol geometry primitives."""

    @staticmethod
    def generate(params: WeldSymbolParams) -> List[Union[LineSegment2D, Arc2D]]:
        ox, oy = params.origin.x, params.origin.y
        ht = params.height
        ref_len = params.reference_length

        primitives: List[Union[LineSegment2D, Arc2D]] = []

        # 1. Leader line from origin to elbow
        elbow_x = ox + 10.0
        elbow_y = oy + 10.0
        primitives.append(LineSegment2D(start=Point2D(ox, oy), end=Point2D(elbow_x, elbow_y)))

        # 2. Reference line starting from elbow extending horizontally to the right
        ref_end_x = elbow_x + ref_len
        primitives.append(
            LineSegment2D(start=Point2D(elbow_x, elbow_y), end=Point2D(ref_end_x, elbow_y))
        )

        # 3. Closed arrowhead at origin (1.2*ht length, 0.35*ht width)
        arrow_len = 1.2 * ht
        arrow_w = 0.35 * ht
        # Direction vector from elbow to origin
        dx = ox - elbow_x
        dy = oy - elbow_y
        length_vec = math.hypot(dx, dy)
        if length_vec > 1e-6:
            ux, uy = dx / length_vec, dy / length_vec
            # Perpendicular vector
            px, py = -uy, ux
            tip_p = Point2D(ox, oy)
            base_p1 = Point2D(
                ox + ux * arrow_len + px * arrow_w, oy + uy * arrow_len + py * arrow_w
            )
            base_p2 = Point2D(
                ox + ux * arrow_len - px * arrow_w, oy + uy * arrow_len - py * arrow_w
            )
            primitives.append(LineSegment2D(start=tip_p, end=base_p1))
            primitives.append(LineSegment2D(start=tip_p, end=base_p2))
            primitives.append(LineSegment2D(start=base_p1, end=base_p2))

        # 4. Weld type symbol centered along reference line
        sym_center_x = elbow_x + ref_len / 2.0
        sym_center_y = elbow_y + ht / 2.0

        if params.weld_type == WeldType.FILLET:
            # Fillet triangle symbol
            p1 = Point2D(sym_center_x - ht / 2.0, elbow_y)
            p2 = Point2D(sym_center_x + ht / 2.0, elbow_y)
            p3 = Point2D(sym_center_x - ht / 2.0, elbow_y + ht)
            primitives.append(LineSegment2D(start=p1, end=p2))
            primitives.append(LineSegment2D(start=p2, end=p3))
            primitives.append(LineSegment2D(start=p3, end=p1))
        elif params.weld_type == WeldType.SQUARE_GROOVE:
            # Square groove symbol (two parallel vertical ticks with gap)
            hw = ht / 3.0
            primitives.append(
                LineSegment2D(
                    start=Point2D(sym_center_x - hw, elbow_y),
                    end=Point2D(sym_center_x - hw, elbow_y + ht),
                )
            )
            primitives.append(
                LineSegment2D(
                    start=Point2D(sym_center_x + hw, elbow_y),
                    end=Point2D(sym_center_x + hw, elbow_y + ht),
                )
            )

        # 5. All-around circle at elbow if requested
        if params.all_around:
            circle_rad = 0.4 * ht
            primitives.append(
                Arc2D(
                    center=Point2D(elbow_x, elbow_y + circle_rad + 1.0),
                    radius=circle_rad,
                    start_angle_rad=0.0,
                    end_angle_rad=2.0 * math.pi,
                )
            )

        return primitives


# ============================================================================
# 5. SURFACE FINISH HANDLER
# ============================================================================


class MachiningType(str, Enum):
    ANY = "any"
    REMOVAL_REQUIRED = "removal_required"
    REMOVAL_PROHIBITED = "removal_prohibited"


@dataclass
class SurfaceFinishParams:
    origin: Point2D
    roughness_ra: float = 3.2
    machining_type: MachiningType = MachiningType.REMOVAL_REQUIRED
    height: float = 4.0

    def __post_init__(self):
        self.roughness_ra = _validate_finite_positive(self.roughness_ra, "roughness_ra")
        self.height = _validate_finite_positive(self.height, "height")


class SurfaceFinishHandler:
    """Generates ISO 1302 surface finish symbol geometry primitives."""

    @staticmethod
    def generate(params: SurfaceFinishParams) -> List[Union[LineSegment2D, Arc2D]]:
        ox, oy = params.origin.x, params.origin.y
        ht = params.height

        H1 = 1.4 * ht
        H2 = 3.0 * ht
        inv_sqrt3 = 1.0 / math.sqrt(3.0)

        primitives: List[Union[LineSegment2D, Arc2D]] = []

        # V-check mark with 60-degree arms
        # Vertex 1 at origin (ox, oy)
        v1 = Point2D(ox, oy)
        # Vertex 2 (left up arm end)
        v2x = ox - H1 * inv_sqrt3
        v2y = oy + H1
        v2 = Point2D(v2x, v2y)

        # Vertex 3 (right up arm end)
        v3x = v2x + H2
        v3y = v2y  # Or slanted right arm per ISO 1302
        v3 = Point2D(v3x, v3y)

        primitives.append(LineSegment2D(start=v1, end=v2))
        primitives.append(LineSegment2D(start=v2, end=v3))

        # Machining types additions
        if params.machining_type == MachiningType.REMOVAL_REQUIRED:
            # Horizontal crossbar on first arm or across V
            bar_start = Point2D(v2x + 0.2 * ht, v2y - 0.5 * ht)
            bar_end = Point2D(v2x + 1.2 * ht, v2y - 0.5 * ht)
            primitives.append(LineSegment2D(start=bar_start, end=bar_end))
        elif params.machining_type == MachiningType.REMOVAL_PROHIBITED:
            # Tangent circle of radius 0.5 * ht inside V
            circle_rad = 0.5 * ht
            circle_center = Point2D(ox + 1.0 * ht, oy + 1.5 * ht)
            primitives.append(
                Arc2D(
                    center=circle_center,
                    radius=circle_rad,
                    start_angle_rad=0.0,
                    end_angle_rad=2.0 * math.pi,
                )
            )

        # Horizontal shelf extending from v3
        shelf_x = v3x + 3.5 * ht
        primitives.append(LineSegment2D(start=v3, end=Point2D(shelf_x, v3y)))

        return primitives
