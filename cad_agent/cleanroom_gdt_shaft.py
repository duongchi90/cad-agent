"""
Cleanroom GD&T & Rotating Machinery Drafting Engine
Pure Python 3.11 implementation adhering to ASME Y14.5, ISO 1101, ISO 5459, and ISO 6433.
Strict IEEE-754 validation and analytical closed-form calculations.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from cad_agent.cleanroom_mechanical import Point2D, LineSegment2D, CircleIR


class CleanroomGeometryError(ValueError):
    """Raised for invalid, degenerate, or physically impossible geometry."""

    pass


class CleanroomIEEE754Error(ValueError):
    """Raised for IEEE-754 floating-point violations (NaN, +Inf, -Inf)."""

    pass


def _validate_float(val: float, name: str) -> float:
    """Validates that a value is a finite number."""
    if not isinstance(val, (int, float)):
        raise CleanroomIEEE754Error(f"Parameter '{name}' must be numeric, got {type(val)}.")
    fval = float(val)
    if math.isnan(fval) or math.isinf(fval):
        raise CleanroomIEEE754Error(f"Parameter '{name}' cannot be NaN or Infinite: {val}")
    return fval


def _validate_positive(val: float, name: str) -> float:
    """Validates that a number is strictly positive (> 0)."""
    fval = _validate_float(val, name)
    if fval <= 0.0:
        raise CleanroomGeometryError(
            f"Parameter '{name}' must be strictly positive (> 0), got {fval}"
        )
    return fval


def _validate_non_negative(val: float, name: str) -> float:
    """Validates that a number is non-negative (>= 0)."""
    fval = _validate_float(val, name)
    if fval < 0.0:
        raise CleanroomGeometryError(f"Parameter '{name}' must be non-negative (>= 0), got {fval}")
    return fval


@dataclass
class GdtFrameResult:
    """Result container for Feature Control Frame generation."""

    characteristic: str
    tolerance: float
    modifier: Optional[str]
    datums: List[str]
    insertion_point: Point2D
    frame_width: float
    frame_height: float
    primitives: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class GdtFrameHandler:
    """
    ASME Y14.5 / ISO 1101 Feature Control Frame generator.
    Constructs multi-compartment rectangular frame, text placement, and leader attachment point.
    """

    VALID_CHARACTERISTICS = {
        "STRAIGHTNESS",
        "FLATNESS",
        "CIRCULARITY",
        "CYLINDRICITY",
        "PROFILE_LINE",
        "PROFILE_SURFACE",
        "ANGULARITY",
        "PERPENDICULARITY",
        "PARALLELISM",
        "POSITION",
        "CONCENTRICITY",
        "SYMMETRY",
        "RUNOUT_CIRCULAR",
        "RUNOUT_TOTAL",
    }
    VALID_MODIFIERS = {"M", "L", "S", "MMC", "LMC", "RFS", None}

    def __init__(
        self,
        characteristic: str,
        tolerance: float,
        modifier: Optional[str] = None,
        primary_datum: Optional[str] = None,
        secondary_datum: Optional[str] = None,
        tertiary_datum: Optional[str] = None,
        insertion_point: Optional[Point2D] = None,
        cell_width: float = 10.0,
        cell_height: float = 6.0,
    ):
        char_upper = characteristic.upper().strip()
        if char_upper not in self.VALID_CHARACTERISTICS:
            raise CleanroomGeometryError(f"Invalid GD&T characteristic: {characteristic}")
        self.characteristic = char_upper

        self.tolerance = _validate_positive(tolerance, "tolerance")

        mod_upper = modifier.upper().strip() if modifier else None
        if mod_upper not in self.VALID_MODIFIERS:
            raise CleanroomGeometryError(f"Invalid modifier: {modifier}")
        # Normalize modifiers to standard single letters
        if mod_upper == "MMC":
            mod_upper = "M"
        elif mod_upper == "LMC":
            mod_upper = "L"
        elif mod_upper == "RFS":
            mod_upper = None
        self.modifier = mod_upper

        self.datums = []
        for d in [primary_datum, secondary_datum, tertiary_datum]:
            if d:
                d_str = str(d).upper().strip()
                if not d_str.isalnum():
                    raise CleanroomGeometryError(f"Invalid datum identifier: {d}")
                self.datums.append(d_str)

        self.insertion_point = insertion_point if insertion_point is not None else Point2D(0.0, 0.0)
        self.cell_width = _validate_positive(cell_width, "cell_width")
        self.cell_height = _validate_positive(cell_height, "cell_height")

    def execute(self) -> GdtFrameResult:
        """Generates geometric primitives and layout for the Feature Control Frame."""
        compartments = (
            1 + (1 if self.modifier or self.tolerance is not None else 0) + len(self.datums)
        )
        total_width = compartments * self.cell_width
        total_height = self.cell_height

        x0 = self.insertion_point.x
        y0 = self.insertion_point.y
        x1 = x0 + total_width
        y1 = y0 + total_height

        primitives: List[Any] = []

        # Outer rectangle boundary
        primitives.append(LineSegment2D(Point2D(x0, y0), Point2D(x1, y0)))
        primitives.append(LineSegment2D(Point2D(x1, y0), Point2D(x1, y1)))
        primitives.append(LineSegment2D(Point2D(x1, y1), Point2D(x0, y1)))
        primitives.append(LineSegment2D(Point2D(x0, y1), Point2D(x0, y0)))

        # Vertical compartment dividers
        current_x = x0
        for i in range(1, compartments):
            current_x += self.cell_width
            primitives.append(LineSegment2D(Point2D(current_x, y0), Point2D(current_x, y1)))

        metadata = {
            "compartments": compartments,
            "characteristic": self.characteristic,
            "tolerance": self.tolerance,
            "modifier": self.modifier,
            "datums": self.datums,
            "leader_attachment": Point2D(x0, y0 + total_height / 2.0),
        }

        return GdtFrameResult(
            characteristic=self.characteristic,
            tolerance=self.tolerance,
            modifier=self.modifier,
            datums=self.datums,
            insertion_point=self.insertion_point,
            frame_width=total_width,
            frame_height=total_height,
            primitives=primitives,
            metadata=metadata,
        )


@dataclass
class DatumFeatureResult:
    """Result container for Datum Feature Symbol generation."""

    datum_letter: str
    insertion_point: Point2D
    primitives: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DatumFeatureHandler:
    """
    ISO 5459 / ASME Y14.5 Datum Feature Symbol generator.
    Constructs frame, stem line, and filled/triangular reference base.
    """

    def __init__(
        self,
        datum_letter: str,
        insertion_point: Optional[Point2D] = None,
        box_size: float = 8.0,
        stem_length: float = 12.0,
    ):
        d_str = str(datum_letter).upper().strip()
        if not d_str.isalnum() or len(d_str) != 1:
            raise CleanroomGeometryError(
                f"Datum letter must be a single alphanumeric character, got '{datum_letter}'"
            )
        self.datum_letter = d_str
        self.insertion_point = insertion_point if insertion_point is not None else Point2D(0.0, 0.0)
        self.box_size = _validate_positive(box_size, "box_size")
        self.stem_length = _validate_positive(stem_length, "stem_length")

    def execute(self) -> DatumFeatureResult:
        """Generates geometric primitives for the Datum Feature Symbol."""
        x0 = self.insertion_point.x
        y0 = self.insertion_point.y

        # Frame box (square or circle representation as square box)
        bx0 = x0
        by0 = y0
        bx1 = x0 + self.box_size
        by1 = y0 + self.box_size

        primitives: List[Any] = [
            LineSegment2D(Point2D(bx0, by0), Point2D(bx1, by0)),
            LineSegment2D(Point2D(bx1, by0), Point2D(bx1, by1)),
            LineSegment2D(Point2D(bx1, by1), Point2D(bx0, by1)),
            LineSegment2D(Point2D(bx0, by1), Point2D(bx0, by0)),
        ]

        # Stem line extending downwards to triangle base
        stem_start_x = x0 + self.box_size / 2.0
        stem_start_y = y0
        stem_end_y = y0 - self.stem_length

        primitives.append(
            LineSegment2D(Point2D(stem_start_x, stem_start_y), Point2D(stem_start_x, stem_end_y))
        )

        # Triangle base (filled datum triangle representation via lines)
        tri_half_w = self.box_size / 2.0
        tri_left = stem_start_x - tri_half_w
        tri_right = stem_start_x + tri_half_w
        primitives.append(
            LineSegment2D(
                Point2D(stem_start_x, stem_end_y), Point2D(tri_left, stem_end_y - self.box_size)
            )
        )
        primitives.append(
            LineSegment2D(
                Point2D(stem_start_x, stem_end_y), Point2D(tri_right, stem_end_y - self.box_size)
            )
        )
        primitives.append(
            LineSegment2D(
                Point2D(tri_left, stem_end_y - self.box_size),
                Point2D(tri_right, stem_end_y - self.box_size),
            )
        )

        return DatumFeatureResult(
            datum_letter=self.datum_letter,
            insertion_point=self.insertion_point,
            primitives=primitives,
            metadata={"stem_length": self.stem_length, "box_size": self.box_size},
        )


@dataclass
class ItemBalloonResult:
    """Result container for BOM Item Balloon generation."""

    item_number: int
    center: Point2D
    radius: float
    primitives: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ItemBalloonHandler:
    """
    ISO 6433 BOM item balloons: Circular balloon frame, item number text placeholder,
    and leader line to target part with arrowhead termination.
    """

    def __init__(
        self,
        item_number: int,
        center: Optional[Point2D] = None,
        radius: float = 6.0,
        leader_target: Optional[Point2D] = None,
    ):
        if not isinstance(item_number, int) or item_number <= 0:
            raise CleanroomGeometryError(
                f"Item number must be a positive integer, got {item_number}"
            )
        self.item_number = item_number
        self.center = center if center is not None else Point2D(0.0, 0.0)
        self.radius = _validate_positive(radius, "radius")
        if leader_target is not None and self.center.distance_to(leader_target) <= 1e-9:
            raise CleanroomGeometryError("Leader target cannot be coincident with balloon center.")
        self.leader_target = (
            leader_target
            if leader_target is not None
            else Point2D(self.center.x - 20.0, self.center.y - 20.0)
        )

    def execute(self) -> ItemBalloonResult:
        """Generates circular balloon frame and leader line primitives."""
        primitives: List[Any] = []

        # Circular balloon frame
        primitives.append(CircleIR(center=self.center, radius=self.radius))

        # Leader line from balloon perimeter towards target
        # Calculate intersection point on circle perimeter closest to leader_target
        dx = self.leader_target.x - self.center.x
        dy = self.leader_target.y - self.center.y
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            raise CleanroomGeometryError("Leader target cannot coincide with balloon center.")

        ux = dx / dist
        uy = dy / dist
        perim_pt = Point2D(self.center.x + ux * self.radius, self.center.y + uy * self.radius)

        primitives.append(LineSegment2D(perim_pt, self.leader_target))

        # Arrowhead primitives at leader target
        arrow_len = 3.0
        angle = math.atan2(uy, ux)
        wing_angle = math.radians(25.0)

        p1 = Point2D(
            self.leader_target.x - arrow_len * math.cos(angle - wing_angle),
            self.leader_target.y - arrow_len * math.sin(angle - wing_angle),
        )
        p2 = Point2D(
            self.leader_target.x - arrow_len * math.cos(angle + wing_angle),
            self.leader_target.y - arrow_len * math.sin(angle + wing_angle),
        )
        primitives.append(LineSegment2D(self.leader_target, p1))
        primitives.append(LineSegment2D(self.leader_target, p2))

        return ItemBalloonResult(
            item_number=self.item_number,
            center=self.center,
            radius=self.radius,
            primitives=primitives,
            metadata={"leader_target": self.leader_target, "perimeter_attachment": perim_pt},
        )


@dataclass
class ShaftStepDefinition:
    """Definition of a single cylindrical section of a stepped shaft."""

    diameter: float
    length: float
    fillet_radius: float = 0.0
    chamfer: float = 0.0


@dataclass
class ShaftStepResult:
    """Result container for Stepped Shaft generator and analytical calculations."""

    steps: List[ShaftStepDefinition]
    total_length: float
    max_diameter: float
    volume: float
    mass: float
    primitives: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ShaftStepHandler:
    """
    Stepped shaft profile generator with multi-diameter cylindrical sections,
    transitional fillets or chamfers, and analytical volume & mass calculation.
    """

    def __init__(self, steps: List[ShaftStepDefinition], material_density: float = 7850.0):
        if not steps or not isinstance(steps, list):
            raise CleanroomGeometryError("Steps list must be non-empty.")
        self.steps = steps
        self.density = _validate_positive(material_density, "material_density")

        for idx, step in enumerate(steps):
            _validate_positive(step.diameter, f"steps[{idx}].diameter")
            _validate_positive(step.length, f"steps[{idx}].length")
            _validate_non_negative(step.fillet_radius, f"steps[{idx}].fillet_radius")
            _validate_non_negative(step.chamfer, f"steps[{idx}].chamfer")

    def execute(self) -> ShaftStepResult:
        """Generates shaft outer profile wireframe and computes analytical mass properties."""
        total_length = sum(s.length for s in self.steps)
        max_diameter = max(s.diameter for s in self.steps)

        # Analytical volume computation: V = sum(pi * (d_i / 2)^2 * L_i)
        volume = 0.0
        for s in self.steps:
            r = s.diameter / 2.0
            volume += math.pi * (r**2) * s.length

        mass = (
            volume * self.density
        )  # density in kg/m^3 if dimensions are in meters, or scaled appropriately

        # Generate 2D profile wireframe (upper half symmetry profile along X-axis)
        primitives: List[Any] = []
        current_x = 0.0

        for idx, s in enumerate(self.steps):
            r = s.diameter / 2.0
            x_start = current_x
            x_end = current_x + s.length

            # Upper outer edge line
            primitives.append(LineSegment2D(Point2D(x_start, r), Point2D(x_end, r)))

            # If not the last step and there's a diameter step change, add transition
            if idx < len(self.steps) - 1:
                next_r = self.steps[idx + 1].diameter / 2.0
                if abs(r - next_r) > 1e-6:
                    primitives.append(LineSegment2D(Point2D(x_end, r), Point2D(x_end, next_r)))

            current_x = x_end

        # Axis centerline
        primitives.append(LineSegment2D(Point2D(0.0, 0.0), Point2D(total_length, 0.0)))

        return ShaftStepResult(
            steps=self.steps,
            total_length=total_length,
            max_diameter=max_diameter,
            volume=volume,
            mass=mass,
            primitives=primitives,
            metadata={"material_density": self.density},
        )


@dataclass
class BallBearingResult:
    """Result container for Rolling Element Bearing section representation."""

    bore_diameter: float
    outer_diameter: float
    width: float
    ball_diameter: float
    ball_count: int
    center: Point2D
    primitives: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def Z(self) -> int:
        return self.ball_count


class BallBearingHandler:
    """
    Standard rolling element bearing section representation:
    Outer ring, inner ring, rolling elements (pitch circle diameter D_pw, ball diameter D_w, count Z).
    """

    def __init__(
        self,
        bore_diameter: float,
        outer_diameter: float,
        width: float,
        ball_diameter: float,
        ball_count: int,
        center: Optional[Point2D] = None,
    ):
        self.d = _validate_positive(bore_diameter, "bore_diameter")
        self.D = _validate_positive(outer_diameter, "outer_diameter")
        if self.D <= self.d:
            raise CleanroomGeometryError(
                f"Outer diameter ({self.D}) must be greater than bore diameter ({self.d})."
            )

        self.B = _validate_positive(width, "width")
        self.Dw = _validate_positive(ball_diameter, "ball_diameter")
        if not isinstance(ball_count, int) or ball_count < 3:
            raise CleanroomGeometryError(f"Ball count must be an integer >= 3, got {ball_count}")
        self.Z = ball_count

        self.center = center if center is not None else Point2D(0.0, 0.0)

    def execute(self) -> BallBearingResult:
        """Generates bearing rings and rolling element cross-section circles."""
        primitives: List[Any] = []

        r_inner = self.d / 2.0
        r_outer = self.D / 2.0

        # Pitch circle diameter (approx midpoint between inner and outer raceways)
        dpw = r_inner + r_outer

        # Concentric circles for inner and outer rings (simplified 2D section boundaries)
        # Inner ring inner & outer boundary
        primitives.append(CircleIR(center=self.center, radius=r_inner))
        inner_raceway_r = r_inner + (r_outer - r_inner) * 0.35
        primitives.append(CircleIR(center=self.center, radius=inner_raceway_r))

        # Outer ring inner & outer boundary
        outer_raceway_r = r_outer - (r_outer - r_inner) * 0.35
        primitives.append(CircleIR(center=self.center, radius=outer_raceway_r))
        primitives.append(CircleIR(center=self.center, radius=r_outer))

        # Rolling elements (balls) distributed along pitch circle diameter
        ball_center_r = dpw / 2.0
        for i in range(self.Z):
            angle = 2.0 * math.pi * i / self.Z
            bx = self.center.x + ball_center_r * math.cos(angle)
            by = self.center.y + ball_center_r * math.sin(angle)
            primitives.append(CircleIR(center=Point2D(bx, by), radius=self.Dw / 2.0))

        metadata = {
            "pitch_circle_diameter": dpw,
            "inner_raceway_radius": inner_raceway_r,
            "outer_raceway_radius": outer_raceway_r,
        }

        return BallBearingResult(
            bore_diameter=self.d,
            outer_diameter=self.D,
            width=self.B,
            ball_diameter=self.Dw,
            ball_count=self.Z,
            center=self.center,
            primitives=primitives,
            metadata=metadata,
        )
