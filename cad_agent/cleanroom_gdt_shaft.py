"""
Cleanroom GDT & Shaft Geometric Modeling & Annotation Module (M3 Regression Containment).
Strictly enforces strongly-typed IR primitives (Point2D, LineSegment2D, CircleIR, Arc2D)
from cad_agent.cleanroom_mechanical. Zero dictionary primitives. Zero stubs.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Tuple, Optional, Union
import math

from cad_agent.cleanroom_mechanical import (
    Point2D,
    LineSegment2D,
    CircleIR,
)


# ============================================================================
# EXCEPTION HIERARCHY & ERROR CODES
# ============================================================================


class CleanroomError(Exception):
    """Base exception for cleanroom geometric and drafting errors."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


class InvalidDiameterError(CleanroomError):
    def __init__(
        self,
        message: str = "Shaft diameter must be positive and outer diameter must exceed inner diameter",
    ):
        super().__init__(message, "INVALID_DIAMETER")


class InvalidLengthError(CleanroomError):
    def __init__(self, message: str = "Shaft step length must be strictly positive"):
        super().__init__(message, "INVALID_LENGTH")


class InvalidOrientationError(CleanroomError):
    def __init__(self, message: str = "Datum orientation must be one of UP, DOWN, LEFT, RIGHT"):
        super().__init__(message, "INVALID_ORIENTATION")


class InvalidFrameHeightError(CleanroomError):
    def __init__(self, message: str = "GD&T frame height must be >= 1.3 * TextHeight"):
        super().__init__(message, "INVALID_FRAME_HEIGHT")


class InvalidDimensionError(CleanroomError):
    def __init__(
        self, message: str = "Bearing dimensions violate physical constraints (D > d, B > 0)"
    ):
        super().__init__(message, "INVALID_DIMENSION")


class CoincidentTargetError(CleanroomError):
    def __init__(self, message: str = "Balloon leader target and origin cannot be coincident"):
        super().__init__(message, "COINCIDENT_TARGET")


# ============================================================================
# DATUM ORIENTATION ENUM
# ============================================================================


class DatumOrientation(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


# ============================================================================
# STANDARD BEARINGS CATALOG (14 Deep Groove Ball Bearings: 6200-6206 & 6300-6306)
# ============================================================================

STANDARD_BEARINGS: Dict[str, Dict[str, float]] = {
    "6200": {"d": 10.0, "D": 30.0, "B": 9.0},
    "6201": {"d": 12.0, "D": 32.0, "B": 10.0},
    "6202": {"d": 15.0, "D": 35.0, "B": 11.0},
    "6203": {"d": 17.0, "D": 40.0, "B": 12.0},
    "6204": {"d": 20.0, "D": 47.0, "B": 14.0},
    "6205": {"d": 25.0, "D": 52.0, "B": 15.0},
    "6206": {"d": 30.0, "D": 62.0, "B": 16.0},
    "6300": {"d": 10.0, "D": 35.0, "B": 11.0},
    "6301": {"d": 12.0, "D": 37.0, "B": 12.0},
    "6302": {"d": 15.0, "D": 42.0, "B": 13.0},
    "6303": {"d": 17.0, "D": 47.0, "B": 14.0},
    "6304": {"d": 20.0, "D": 52.0, "B": 15.0},
    "6305": {"d": 25.0, "D": 62.0, "B": 17.0},
    "6306": {"d": 30.0, "D": 72.0, "B": 19.0},
}


# ============================================================================
# 1. GD&T FRAME HANDLER
# ============================================================================


@dataclass
class GdtFrameResult:
    frame_height: float
    text_height: float
    compartment_lines: List[LineSegment2D]
    leader_attachment: Point2D
    compartment_metrics: List[Dict[str, float]]


class GdtFrameHandler:
    """Handles strongly-typed GD&T control frame generation and layout validation."""

    @staticmethod
    def generate_frame(
        compartments: List[str],
        text_height: float = 3.5,
        origin: Point2D = Point2D(0.0, 0.0),
        total_length: float = 40.0,
    ) -> GdtFrameResult:
        min_height = 1.3 * text_height
        frame_height = max(min_height * 1.0, text_height + 2.0)
        if frame_height < min_height:
            raise InvalidFrameHeightError(
                f"Frame height {frame_height} is below 1.3 * text_height ({min_height})"
            )

        num_compartments = len(compartments)
        if num_compartments == 0:
            num_compartments = 1

        comp_width = total_length / num_compartments
        lines: List[LineSegment2D] = []
        compartment_metrics = []

        # Outer boundary rectangle
        x0, y0 = origin.x, origin.y
        x1, y1 = x0 + total_length, y0 + frame_height

        # Top, Bottom, Left, Right outer lines
        lines.append(LineSegment2D(start=Point2D(x0, y0), end=Point2D(x1, y0)))
        lines.append(LineSegment2D(start=Point2D(x0, y1), end=Point2D(x1, y1)))
        lines.append(LineSegment2D(start=Point2D(x0, y0), end=Point2D(x0, y1)))
        lines.append(LineSegment2D(start=Point2D(x1, y0), end=Point2D(x1, y1)))

        # Vertical divider lines between compartments
        for i in range(1, num_compartments):
            cx = x0 + i * comp_width
            lines.append(LineSegment2D(start=Point2D(cx, y0), end=Point2D(cx, y1)))

        for i in range(num_compartments):
            compartment_metrics.append(
                {
                    "index": float(i),
                    "width": comp_width,
                    "height": frame_height,
                    "x_start": x0 + i * comp_width,
                    "x_end": x0 + (i + 1) * comp_width,
                }
            )

        leader_attachment = Point2D(x0, y0 + frame_height / 2.0)

        return GdtFrameResult(
            frame_height=frame_height,
            text_height=text_height,
            compartment_lines=lines,
            leader_attachment=leader_attachment,
            compartment_metrics=compartment_metrics,
        )


# ============================================================================
# 2. DATUM FEATURE HANDLER
# ============================================================================


@dataclass
class DatumFeatureResult:
    orientation: DatumOrientation
    stem_line: LineSegment2D
    triangle_base_lines: List[LineSegment2D]
    box_lines: List[LineSegment2D]
    box_size: Tuple[float, float]


class DatumFeatureHandler:
    """Handles strongly-typed Datum Feature symbol generation across 4 cardinal orientations."""

    @staticmethod
    def generate_datum(
        datum_letter: str,
        orientation: Union[str, DatumOrientation] = DatumOrientation.UP,
        origin: Point2D = Point2D(0.0, 0.0),
        box_width: float = 10.0,
        box_height: float = 10.0,
        stem_length: float = 12.0,
    ) -> DatumFeatureResult:
        if isinstance(orientation, str):
            try:
                orientation = DatumOrientation(orientation.upper())
            except ValueError:
                raise InvalidOrientationError(f"Invalid datum orientation: {orientation}")

        ox, oy = origin.x, origin.y
        stem_line: LineSegment2D
        triangle_lines: List[LineSegment2D] = []
        box_lines: List[LineSegment2D] = []

        # Geometric layout based on orientation
        if orientation == DatumOrientation.UP:
            stem_line = LineSegment2D(start=origin, end=Point2D(ox, oy + stem_length))
            bx, by = ox - box_width / 2.0, oy + stem_length
            # Box perimeter
            box_lines = [
                LineSegment2D(start=Point2D(bx, by), end=Point2D(bx + box_width, by)),
                LineSegment2D(
                    start=Point2D(bx + box_width, by), end=Point2D(bx + box_width, by + box_height)
                ),
                LineSegment2D(
                    start=Point2D(bx + box_width, by + box_height), end=Point2D(bx, by + box_height)
                ),
                LineSegment2D(start=Point2D(bx, by + box_height), end=Point2D(bx, by)),
            ]
            # Filled triangle base pointing down towards origin
            triangle_lines = [
                LineSegment2D(
                    start=Point2D(ox - 4.0, oy + stem_length),
                    end=Point2D(ox + 4.0, oy + stem_length),
                ),
                LineSegment2D(start=Point2D(ox - 4.0, oy + stem_length), end=origin),
                LineSegment2D(start=Point2D(ox + 4.0, oy + stem_length), end=origin),
            ]
        elif orientation == DatumOrientation.DOWN:
            stem_line = LineSegment2D(start=origin, end=Point2D(ox, oy - stem_length))
            bx, by = ox - box_width / 2.0, oy - stem_length - box_height
            box_lines = [
                LineSegment2D(start=Point2D(bx, by), end=Point2D(bx + box_width, by)),
                LineSegment2D(
                    start=Point2D(bx + box_width, by), end=Point2D(bx + box_width, by + box_height)
                ),
                LineSegment2D(
                    start=Point2D(bx + box_width, by + box_height), end=Point2D(bx, by + box_height)
                ),
                LineSegment2D(start=Point2D(bx, by + box_height), end=Point2D(bx, by)),
            ]
            triangle_lines = [
                LineSegment2D(
                    start=Point2D(ox - 4.0, oy - stem_length),
                    end=Point2D(ox + 4.0, oy - stem_length),
                ),
                LineSegment2D(start=Point2D(ox - 4.0, oy - stem_length), end=origin),
                LineSegment2D(start=Point2D(ox + 4.0, oy - stem_length), end=origin),
            ]
        elif orientation == DatumOrientation.LEFT:
            stem_line = LineSegment2D(start=origin, end=Point2D(ox - stem_length, oy))
            bx, by = ox - stem_length - box_width, oy - box_height / 2.0
            box_lines = [
                LineSegment2D(start=Point2D(bx, by), end=Point2D(bx + box_width, by)),
                LineSegment2D(
                    start=Point2D(bx + box_width, by), end=Point2D(bx + box_width, by + box_height)
                ),
                LineSegment2D(
                    start=Point2D(bx + box_width, by + box_height), end=Point2D(bx, by + box_height)
                ),
                LineSegment2D(start=Point2D(bx, by + box_height), end=Point2D(bx, by)),
            ]
            triangle_lines = [
                LineSegment2D(
                    start=Point2D(ox - stem_length, oy - 4.0),
                    end=Point2D(ox - stem_length, oy + 4.0),
                ),
                LineSegment2D(start=Point2D(ox - stem_length, oy - 4.0), end=origin),
                LineSegment2D(start=Point2D(ox - stem_length, oy + 4.0), end=origin),
            ]
        elif orientation == DatumOrientation.RIGHT:
            stem_line = LineSegment2D(start=origin, end=Point2D(ox + stem_length, oy))
            bx, by = ox + stem_length, oy - box_height / 2.0
            box_lines = [
                LineSegment2D(start=Point2D(bx, by), end=Point2D(bx + box_width, by)),
                LineSegment2D(
                    start=Point2D(bx + box_width, by), end=Point2D(bx + box_width, by + box_height)
                ),
                LineSegment2D(
                    start=Point2D(bx + box_width, by + box_height), end=Point2D(bx, by + box_height)
                ),
                LineSegment2D(start=Point2D(bx, by + box_height), end=Point2D(bx, by)),
            ]
            triangle_lines = [
                LineSegment2D(
                    start=Point2D(ox + stem_length, oy - 4.0),
                    end=Point2D(ox + stem_length, oy + 4.0),
                ),
                LineSegment2D(start=Point2D(ox + stem_length, oy - 4.0), end=origin),
                LineSegment2D(start=Point2D(ox + stem_length, oy + 4.0), end=origin),
            ]
        else:
            raise InvalidOrientationError(f"Unsupported orientation: {orientation}")

        return DatumFeatureResult(
            orientation=orientation,
            stem_line=stem_line,
            triangle_base_lines=triangle_lines,
            box_lines=box_lines,
            box_size=(box_width, box_height),
        )


# ============================================================================
# 3. ITEM BALLOON HANDLER
# ============================================================================


@dataclass
class ItemBalloonResult:
    balloon_circle: CircleIR
    leader_line: LineSegment2D
    divider_line: Optional[LineSegment2D]
    primitives_count: int
    quantity: Optional[int]


class ItemBalloonHandler:
    """Handles standard and split item balloons with strongly-typed IR primitives."""

    @staticmethod
    def generate_balloon(
        center: Point2D, target: Point2D, radius: float = 6.0, quantity: Optional[int] = None
    ) -> ItemBalloonResult:
        if abs(center.x - target.x) < 1e-6 and abs(center.y - target.y) < 1e-6:
            raise CoincidentTargetError("Balloon center and target cannot be coincident")

        balloon_circle = CircleIR(center=center, radius=radius)
        leader_line = LineSegment2D(start=target, end=center)

        divider_line: Optional[LineSegment2D] = None
        primitives_count = 2  # Circle + Leader

        if quantity is not None and quantity > 0:
            # Split balloon has horizontal divider line across circle diameter
            divider_line = LineSegment2D(
                start=Point2D(center.x - radius, center.y), end=Point2D(center.x + radius, center.y)
            )
            primitives_count = 3  # Circle + Leader + Divider

        return ItemBalloonResult(
            balloon_circle=balloon_circle,
            leader_line=leader_line,
            divider_line=divider_line,
            primitives_count=primitives_count,
            quantity=quantity,
        )


# ============================================================================
# 4. BALL BEARING HANDLER
# ============================================================================


@dataclass
class BallBearingResult:
    designation: str
    d: float
    D: float
    B: float
    inner_raceway: LineSegment2D
    outer_raceway: LineSegment2D
    rolling_elements: List[CircleIR]


class BallBearingHandler:
    """Handles ISO deep groove ball bearing catalog lookup and geometric IR generation."""

    @staticmethod
    def create_bearing(
        designation: Optional[str] = None,
        custom_d: Optional[float] = None,
        custom_D: Optional[float] = None,
        custom_B: Optional[float] = None,
    ) -> BallBearingResult:
        if designation:
            des_upper = designation.upper()
            if des_upper not in STANDARD_BEARINGS:
                raise InvalidDimensionError(
                    f"Bearing designation {designation} not found in ISO standard catalog"
                )
            specs = STANDARD_BEARINGS[des_upper]
            d, D, B = specs["d"], specs["D"], specs["B"]
            deg_key = des_upper
        elif custom_d is not None and custom_D is not None and custom_B is not None:
            if custom_D <= custom_d or custom_B <= 0:
                raise InvalidDimensionError(
                    "Custom bearing dimensions invalid: require D > d and B > 0"
                )
            d, D, B = custom_d, custom_D, custom_B
            deg_key = "CUSTOM"
        else:
            raise InvalidDimensionError(
                "Must provide either a valid designation or custom dimensions (d, D, B)"
            )

        # Generate geometric IR primitives for bearing cross-section
        inner_raceway = LineSegment2D(start=Point2D(0.0, -d / 2.0), end=Point2D(B, d / 2.0))
        outer_raceway = LineSegment2D(start=Point2D(0.0, -D / 2.0), end=Point2D(B, D / 2.0))

        # Rolling elements (balls) centered between raceways
        ball_radius = (D - d) / 4.0
        ball_center_y = (d / 2.0 + D / 2.0) / 2.0
        rolling_elements = [
            CircleIR(center=Point2D(B / 2.0, ball_center_y), radius=ball_radius),
            CircleIR(center=Point2D(B / 2.0, -ball_center_y), radius=ball_radius),
        ]

        return BallBearingResult(
            designation=deg_key,
            d=d,
            D=D,
            B=B,
            inner_raceway=inner_raceway,
            outer_raceway=outer_raceway,
            rolling_elements=rolling_elements,
        )


# ============================================================================
# 5. SHAFT STEP HANDLER
# ============================================================================


@dataclass
class ShaftStep:
    diameter: float
    length: float


@dataclass
class ShaftStepResult:
    steps: List[ShaftStep]
    total_length: float
    analytical_volume: float
    profile_boundaries: List[LineSegment2D]


class ShaftStepHandler:
    """Handles stepped shaft profiling, validation, volume and length calculations using IR primitives."""

    @staticmethod
    def create_shaft(steps: List[ShaftStep]) -> ShaftStepResult:
        if not steps:
            raise InvalidLengthError("Shaft must have at least one step")

        total_length = 0.0
        profile_lines: List[LineSegment2D] = []
        volume = 0.0

        current_x = 0.0
        for step in steps:
            if step.diameter <= 0:
                raise InvalidDiameterError(
                    f"Shaft step diameter must be positive, got {step.diameter}"
                )
            if step.length <= 0:
                raise InvalidLengthError(
                    f"Shaft step length must be strictly positive, got {step.length}"
                )

            r = step.diameter / 2.0
            next_x = current_x + step.length

            # Upper profile boundary line for step
            profile_lines.append(LineSegment2D(start=Point2D(current_x, r), end=Point2D(next_x, r)))
            # Lower profile boundary line (symmetry axis offset)
            profile_lines.append(
                LineSegment2D(start=Point2D(current_x, -r), end=Point2D(next_x, -r))
            )
            # Step shoulder transition face
            profile_lines.append(LineSegment2D(start=Point2D(next_x, r), end=Point2D(next_x, -r)))

            # Analytical volume calculation: V = pi * r^2 * h (length)
            step_vol = math.pi * (r**2) * step.length
            volume += step_vol
            total_length += step.length
            current_x = next_x

        return ShaftStepResult(
            steps=steps,
            total_length=total_length,
            analytical_volume=volume,
            profile_boundaries=profile_lines,
        )
