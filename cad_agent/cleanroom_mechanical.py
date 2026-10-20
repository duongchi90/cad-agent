"""
CAD Agent Batch M1: Cleanroom Mechanical Capabilities Module.

Implements five core mechanical engineering and geometric solvers:
1. HoleCallout: ASME Y14.5 / ISO 15786 multi-line hole callout generator and parser.
2. BoltCircle: Polar hole pattern solver with chordal/circumferential analytics and CircleIR.
3. CenterlineBisector: Parallel line segment overlap projection and mid-axis bisector.
4. SlotGenerator: Straight obround slot G1 boundary solver and mass property calculator.
5. IsoToleranceFit: ISO 286-1 / ISO 286-2 limits, deviations, and fit classification engine.

Constraints: Pure Python 3.11+ standard library, strict IEEE-754 float validation.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


# =============================================================================
# CONSTANTS & UNICODE SYMBOLS (ASME Y14.5 / ISO)
# =============================================================================

SYM_DIA: str = "\u2300"  # ⌀ Diameter
SYM_CBORE: str = "\u2334"  # ⌴ Counterbore
SYM_CSINK: str = "\u2335"  # ⌵ Countersink
SYM_DEPTH: str = "\u21a7"  # ↧ Depth

GEOM_TOL: float = 1e-9


# =============================================================================
# IEEE-754 & NUMERIC VALIDATION HELPERS
# =============================================================================


def _validate_finite(val: float, name: str) -> float:
    """Validate that a numeric value is a finite IEEE-754 float."""
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ValueError(f"Parameter '{name}' must be a numeric type, got {type(val).__name__}.")
    fval = float(val)
    if not math.isfinite(fval):
        raise ValueError(f"Parameter '{name}' must be a finite IEEE-754 float, got {val}.")
    return fval


def _validate_positive(val: float, name: str) -> float:
    """Validate that a numeric value is strictly positive (> 0)."""
    fval = _validate_finite(val, name)
    if fval <= 0.0:
        raise ValueError(f"Parameter '{name}' must be strictly positive (> 0), got {fval}.")
    return fval


def _validate_non_negative(val: float, name: str) -> float:
    """Validate that a numeric value is non-negative (>= 0)."""
    fval = _validate_finite(val, name)
    if fval < 0.0:
        raise ValueError(f"Parameter '{name}' must be non-negative (>= 0), got {fval}.")
    return fval


def _format_num(val: float, precision: int = 4) -> str:
    """Format a float cleanly without trailing zeros while preserving integer form if exact."""
    fval = round(_validate_finite(val, "val"), precision)
    if abs(fval) < 1e-12:
        fval = 0.0
    s = f"{fval:.{precision}f}".rstrip("0").rstrip(".")
    return s if s else "0"


# =============================================================================
# SHARED GEOMETRY IR PRIMITIVES
# =============================================================================


@dataclass(frozen=True)
class Point2D:
    """Immutable 2D Cartesian point with strict IEEE-754 validation."""

    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _validate_finite(self.x, "Point2D.x"))
        object.__setattr__(self, "y", _validate_finite(self.y, "Point2D.y"))

    def distance_to(self, other: Point2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass(frozen=True)
class LineSegment2D:
    """Immutable 2D directed line segment."""

    start: Point2D
    end: Point2D

    def __post_init__(self) -> None:
        if self.start.distance_to(self.end) <= GEOM_TOL:
            raise ValueError(
                "LineSegment2D start and end points cannot be coincident (degenerate zero-length segment)."
            )

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)

    @property
    def midpoint(self) -> Point2D:
        return Point2D((self.start.x + self.end.x) * 0.5, (self.start.y + self.end.y) * 0.5)

    @property
    def direction(self) -> Tuple[float, float]:
        L = self.length
        return ((self.end.x - self.start.x) / L, (self.end.y - self.start.y) / L)


@dataclass(frozen=True)
class CircleIR:
    """Intermediate Representation for a 2D Circle primitive."""

    center: Point2D
    radius: float
    index: int = 0
    angle_deg: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "radius", _validate_positive(self.radius, "CircleIR.radius"))
        object.__setattr__(
            self, "angle_deg", _validate_finite(self.angle_deg, "CircleIR.angle_deg")
        )
        if not isinstance(self.index, int) or isinstance(self.index, bool) or self.index < 0:
            raise ValueError(f"CircleIR.index must be a non-negative integer, got {self.index}.")

    @property
    def diameter(self) -> float:
        return self.radius * 2.0


@dataclass(frozen=True)
class Arc2D:
    """Immutable 2D Circular Arc primitive (CCW convention from start_angle_rad to end_angle_rad)."""

    center: Point2D
    radius: float
    start_angle_rad: float
    end_angle_rad: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "radius", _validate_positive(self.radius, "Arc2D.radius"))
        object.__setattr__(
            self, "start_angle_rad", _validate_finite(self.start_angle_rad, "Arc2D.start_angle_rad")
        )
        object.__setattr__(
            self, "end_angle_rad", _validate_finite(self.end_angle_rad, "Arc2D.end_angle_rad")
        )

    @property
    def start_point(self) -> Point2D:
        return Point2D(
            self.center.x + self.radius * math.cos(self.start_angle_rad),
            self.center.y + self.radius * math.sin(self.start_angle_rad),
        )

    @property
    def end_point(self) -> Point2D:
        return Point2D(
            self.center.x + self.radius * math.cos(self.end_angle_rad),
            self.center.y + self.radius * math.sin(self.end_angle_rad),
        )


# =============================================================================
# TOOL 1: HoleCallout (ASME Y14.5 / ISO Multi-Line Formatter & Parser)
# =============================================================================


class HoleType(str, Enum):
    SIMPLE = "SIMPLE"
    COUNTERBORE = "COUNTERBORE"
    COUNTERSINK = "COUNTERSINK"


@dataclass(frozen=True)
class HoleCallout:
    """
    ASME Y14.5M / ISO 15786 Hole Callout model, formatter, and reverse parser.

    Supports:
    - Simple through and blind holes
    - Counterbored holes (⌴, \u2334)
    - Countersunk holes (⌵, \u2335)
    - Repeat quantity prefixes (e.g. '4X ')
    - Precision formatting and lossless reverse string parsing
    """

    diameter: float
    is_thru: bool = True
    depth: Optional[float] = None
    quantity: int = 1
    cbore_dia: Optional[float] = None
    cbore_depth: Optional[float] = None
    csink_dia: Optional[float] = None
    csink_angle_deg: Optional[float] = None
    thread_spec: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "diameter", _validate_positive(self.diameter, "diameter"))

        if (
            not isinstance(self.quantity, int)
            or isinstance(self.quantity, bool)
            or self.quantity < 1
        ):
            raise ValueError(f"Parameter 'quantity' must be an integer >= 1, got {self.quantity}.")

        if not isinstance(self.is_thru, bool):
            raise ValueError("Parameter 'is_thru' must be a boolean.")

        if self.is_thru:
            if self.depth is not None:
                raise ValueError("Through hole (is_thru=True) cannot specify a finite 'depth'.")
        else:
            if self.depth is None:
                raise ValueError("Blind hole (is_thru=False) must specify a positive 'depth'.")
            object.__setattr__(self, "depth", _validate_positive(self.depth, "depth"))

        has_cbore = (self.cbore_dia is not None) or (self.cbore_depth is not None)
        has_csink = (self.csink_dia is not None) or (self.csink_angle_deg is not None)

        if has_cbore and has_csink:
            raise ValueError(
                "HoleCallout cannot simultaneously specify both counterbore and countersink features."
            )

        if has_cbore:
            if self.cbore_dia is None or self.cbore_depth is None:
                raise ValueError("Counterbore requires both 'cbore_dia' and 'cbore_depth'.")
            cb_d = _validate_positive(self.cbore_dia, "cbore_dia")
            cb_h = _validate_positive(self.cbore_depth, "cbore_depth")
            if cb_d <= self.diameter:
                raise ValueError(
                    f"Counterbore diameter ({cb_d}) must be strictly greater than primary hole diameter ({self.diameter})."
                )
            if not self.is_thru and self.depth is not None and cb_h >= self.depth:
                raise ValueError(
                    f"Counterbore depth ({cb_h}) must be strictly less than blind hole depth ({self.depth})."
                )
            object.__setattr__(self, "cbore_dia", cb_d)
            object.__setattr__(self, "cbore_depth", cb_h)

        if has_csink:
            if self.csink_dia is None or self.csink_angle_deg is None:
                raise ValueError("Countersink requires both 'csink_dia' and 'csink_angle_deg'.")
            cs_d = _validate_positive(self.csink_dia, "csink_dia")
            cs_a = _validate_positive(self.csink_angle_deg, "csink_angle_deg")
            if cs_d <= self.diameter:
                raise ValueError(
                    f"Countersink diameter ({cs_d}) must be strictly greater than primary hole diameter ({self.diameter})."
                )
            if cs_a <= 0.0 or cs_a >= 180.0:
                raise ValueError(
                    f"Countersink angle ({cs_a}) must be strictly between 0 and 180 degrees."
                )
            object.__setattr__(self, "csink_dia", cs_d)
            object.__setattr__(self, "csink_angle_deg", cs_a)

        if self.thread_spec is not None:
            cleaned = self.thread_spec.strip()
            if not cleaned:
                raise ValueError("thread_spec cannot be an empty or whitespace-only string.")
            object.__setattr__(self, "thread_spec", cleaned)

    @property
    def hole_type(self) -> HoleType:
        if self.cbore_dia is not None:
            return HoleType.COUNTERBORE
        if self.csink_dia is not None:
            return HoleType.COUNTERSINK
        return HoleType.SIMPLE

    def format(self, precision: int = 4) -> str:
        """
        Format the hole callout according to ASME Y14.5M multi-line notation.

        Line 1: [<qty>X ]⌀<dia> [THRU | ↧<depth>] [THREAD <spec>]
        Line 2 (optional): ⌴⌀<cbore_dia> ↧<cbore_depth>  OR  ⌵⌀<csink_dia> X <angle>°
        """
        if not isinstance(precision, int) or precision < 0:
            raise ValueError("Precision must be a non-negative integer.")

        prefix = f"{self.quantity}X " if self.quantity > 1 else ""
        dia_str = _format_num(self.diameter, precision)

        if self.is_thru:
            depth_part = "THRU"
        else:
            assert self.depth is not None
            depth_part = f"{SYM_DEPTH}{_format_num(self.depth, precision)}"

        line1 = f"{prefix}{SYM_DIA}{dia_str} {depth_part}"
        if self.thread_spec:
            line1 = f"{line1} {self.thread_spec}"

        lines = [line1]

        if self.hole_type == HoleType.COUNTERBORE:
            assert self.cbore_dia is not None and self.cbore_depth is not None
            cb_d_str = _format_num(self.cbore_dia, precision)
            cb_h_str = _format_num(self.cbore_depth, precision)
            lines.append(f"{SYM_CBORE}{SYM_DIA}{cb_d_str} {SYM_DEPTH}{cb_h_str}")
        elif self.hole_type == HoleType.COUNTERSINK:
            assert self.csink_dia is not None and self.csink_angle_deg is not None
            cs_d_str = _format_num(self.csink_dia, precision)
            cs_a_str = _format_num(self.csink_angle_deg, precision)
            lines.append(f"{SYM_CSINK}{SYM_DIA}{cs_d_str} X {cs_a_str}\u00b0")

        return "\n".join(lines)

    @classmethod
    def parse(cls, text: str) -> HoleCallout:
        """
        Reverse-parse an ASME Y14.5 / ISO formatted multi-line hole callout string
        back into a validated HoleCallout instance.
        """
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Callout text must be a non-empty string.")

        raw_lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
        if not raw_lines or len(raw_lines) > 2:
            raise ValueError(f"Expected 1 or 2 lines in callout, got {len(raw_lines)}.")

        # Line 1 pattern:
        # Optional "<qty>X "
        # ⌀<dia>
        # "THRU" or "↧<depth>"
        # Optional thread_spec
        line1_pattern = re.compile(
            r"^(?:(?P<qty>\d+)\s*[xX]\s+)?"
            r"\u2300\s*(?P<dia>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
            r"\s+(?:(?P<thru>THRU)|(?:\u21a7\s*(?P<depth>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)))"
            r"(?:\s+(?P<thread>.+))?$"
        )
        m1 = line1_pattern.match(raw_lines[0])
        if not m1:
            raise ValueError(f"Malformed primary hole callout line: '{raw_lines[0]}'")

        qty_str = m1.group("qty")
        quantity = int(qty_str) if qty_str is not None else 1
        diameter = float(m1.group("dia"))
        is_thru = m1.group("thru") is not None
        depth = float(m1.group("depth")) if m1.group("depth") is not None else None
        thread_spec = m1.group("thread")

        cbore_dia: Optional[float] = None
        cbore_depth: Optional[float] = None
        csink_dia: Optional[float] = None
        csink_angle_deg: Optional[float] = None

        if len(raw_lines) == 2:
            line2 = raw_lines[1]
            cbore_pattern = re.compile(
                r"^\u2334\s*\u2300\s*(?P<cb_dia>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
                r"\s+\u21a7\s*(?P<cb_depth>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)$"
            )
            csink_pattern = re.compile(
                r"^\u2335\s*\u2300\s*(?P<cs_dia>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
                r"\s*[xX]\s*(?P<cs_ang>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*\u00b0$"
            )
            m_cb = cbore_pattern.match(line2)
            m_cs = csink_pattern.match(line2)
            if m_cb:
                cbore_dia = float(m_cb.group("cb_dia"))
                cbore_depth = float(m_cb.group("cb_depth"))
            elif m_cs:
                csink_dia = float(m_cs.group("cs_dia"))
                csink_angle_deg = float(m_cs.group("cs_ang"))
            else:
                raise ValueError(f"Malformed secondary modifier callout line: '{line2}'")

        return cls(
            diameter=diameter,
            is_thru=is_thru,
            depth=depth,
            quantity=quantity,
            cbore_dia=cbore_dia,
            cbore_depth=cbore_depth,
            csink_dia=csink_dia,
            csink_angle_deg=csink_angle_deg,
            thread_spec=thread_spec,
        )


# =============================================================================
# TOOL 2: BoltCircle (Polar Array Solver, Pitch Analytics, CircleIR Generation)
# =============================================================================


@dataclass(frozen=True)
class BoltCircleResult:
    """Result packet for BoltCircle solver."""

    bolt_circle_diameter: float
    bolt_circle_radius: float
    hole_diameter: float
    num_holes: int
    start_angle_deg: float
    angular_pitch_deg: float
    chordal_pitch: float
    circumferential_pitch: float
    min_ligament: float
    centroid: Point2D
    circles: Tuple[CircleIR, ...]


class BoltCircle:
    """
    Polar bolt-hole array solver.

    Computes exact Cartesian coordinates, CircleIR entities, chordal pitch,
    circumferential arc pitch, minimum inter-hole ligament, and verifies centroid identity.
    """

    @staticmethod
    def solve(
        center: Tuple[float, float] | Point2D,
        bcd: float,
        hole_dia: float,
        num_holes: int,
        start_angle_deg: float = 0.0,
        allow_overlapping_holes: bool = False,
    ) -> BoltCircleResult:
        """
        Solve a full 360-degree equispaced bolt circle pattern.

        Parameters
        ----------
        center : (x, y) or Point2D
            Center of the bolt circle.
        bcd : float
            Bolt Circle Diameter (must be > 0).
        hole_dia : float
            Individual bolt hole diameter (must be > 0).
        num_holes : int
            Number of equispaced holes N >= 1.
        start_angle_deg : float
            Angle of hole 0 in degrees measured CCW from +X axis.
        allow_overlapping_holes : bool
            If False (default), raises ValueError if adjacent holes touch or overlap.
        """
        if isinstance(center, Point2D):
            c_pt = center
        elif isinstance(center, (tuple, list)) and len(center) == 2:
            c_pt = Point2D(center[0], center[1])
        else:
            raise ValueError("Parameter 'center' must be a Point2D or a 2-tuple (x, y).")

        bcd_val = _validate_positive(bcd, "bcd")
        h_dia = _validate_positive(hole_dia, "hole_dia")
        start_ang = _validate_finite(start_angle_deg, "start_angle_deg")

        if not isinstance(num_holes, int) or isinstance(num_holes, bool) or num_holes < 1:
            raise ValueError(f"Parameter 'num_holes' must be an integer >= 1, got {num_holes}.")

        R = bcd_val * 0.5
        r_hole = h_dia * 0.5

        if num_holes == 1:
            angular_pitch_deg = 360.0
            chordal_pitch = 0.0
            circumferential_pitch = math.pi * bcd_val
            min_ligament = float("inf")
        else:
            angular_pitch_deg = 360.0 / num_holes
            chordal_pitch = bcd_val * math.sin(math.pi / num_holes)
            circumferential_pitch = (math.pi * bcd_val) / num_holes
            min_ligament = chordal_pitch - h_dia
            if not allow_overlapping_holes and min_ligament <= 0.0:
                raise ValueError(
                    f"Adjacent bolt holes overlap or touch: chordal_pitch={chordal_pitch:.6f}, "
                    f"hole_dia={h_dia:.6f}, ligament={min_ligament:.6f} <= 0."
                )

        circles_list: List[CircleIR] = []
        sum_x = 0.0
        sum_y = 0.0

        for idx in range(num_holes):
            ang_deg = start_ang + idx * (360.0 / num_holes)
            ang_rad = math.radians(ang_deg)
            hx = c_pt.x + R * math.cos(ang_rad)
            hy = c_pt.y + R * math.sin(ang_rad)
            sum_x += hx
            sum_y += hy
            circles_list.append(
                CircleIR(
                    center=Point2D(hx, hy),
                    radius=r_hole,
                    index=idx,
                    angle_deg=ang_deg % 360.0,
                )
            )

        if num_holes == 1:
            centroid = circles_list[0].center
        else:
            centroid = Point2D(sum_x / num_holes, sum_y / num_holes)

        return BoltCircleResult(
            bolt_circle_diameter=bcd_val,
            bolt_circle_radius=R,
            hole_diameter=h_dia,
            num_holes=num_holes,
            start_angle_deg=start_ang,
            angular_pitch_deg=angular_pitch_deg,
            chordal_pitch=chordal_pitch,
            circumferential_pitch=circumferential_pitch,
            min_ligament=min_ligament,
            centroid=centroid,
            circles=tuple(circles_list),
        )


# =============================================================================
# TOOL 3: CenterlineBisector (Parallel Segment Mid-Axis Bisector & Extension)
# =============================================================================


@dataclass(frozen=True)
class CenterlineResult:
    """Result packet for CenterlineBisector solver."""

    bisector: LineSegment2D
    unextended_bisector: LineSegment2D
    separation_distance: float
    overlap_length: float
    extension_delta_l: float
    midpoint: Point2D
    unit_direction: Tuple[float, float]


class CenterlineBisector:
    """
    Parallel line segment mid-axis bisector calculator.

    Validates parallelism, non-collinearity (separation > 0), longitudinal projection
    overlap, and generates the symmetrically extended centerline bisector segment (+ΔL at each end).
    """

    @staticmethod
    def compute(
        seg1_start: Tuple[float, float] | Point2D,
        seg1_end: Tuple[float, float] | Point2D,
        seg2_start: Tuple[float, float] | Point2D,
        seg2_end: Tuple[float, float] | Point2D,
        delta_l: float = 0.0,
        angle_tol_rad: float = 1e-6,
    ) -> CenterlineResult:
        """
        Compute the centerline bisector of two parallel 2D segments over their mutually
        overlapping projection interval, extended by `delta_l` on both ends.
        """
        p1 = seg1_start if isinstance(seg1_start, Point2D) else Point2D(*seg1_start)
        p2 = seg1_end if isinstance(seg1_end, Point2D) else Point2D(*seg1_end)
        q1 = seg2_start if isinstance(seg2_start, Point2D) else Point2D(*seg2_start)
        q2 = seg2_end if isinstance(seg2_end, Point2D) else Point2D(*seg2_end)

        ext = _validate_non_negative(delta_l, "delta_l")
        tol = _validate_positive(angle_tol_rad, "angle_tol_rad")

        s1 = LineSegment2D(p1, p2)
        s2 = LineSegment2D(q1, q2)

        u1x, u1y = s1.direction
        u2x, u2y = s2.direction

        # Check parallelism via 2D cross product of unit direction vectors
        cross_u = u1x * u2y - u1y * u2x
        if abs(cross_u) > math.sin(tol):
            raise ValueError(
                f"Segments are not parallel: |u1 x u2| = {abs(cross_u):.6e} exceeds tolerance {math.sin(tol):.6e}."
            )

        # Unit normal to seg1: n1 = (-u1y, u1x)
        nx, ny = -u1y, u1x

        # Signed perpendicular offset from seg1's line (origin p1) to seg2's line (point q1)
        dqx = q1.x - p1.x
        dqy = q1.y - p1.y
        signed_sep = dqx * nx + dqy * ny
        separation = abs(signed_sep)

        if separation <= GEOM_TOL:
            raise ValueError(
                f"Segments are collinear (separation={separation:.6e} <= {GEOM_TOL}); "
                "a distinct parallel bisector is undefined."
            )

        # Project all 4 endpoints onto seg1's longitudinal axis originating at p1
        t_p1 = 0.0
        t_p2 = s1.length
        t_q1 = (q1.x - p1.x) * u1x + (q1.y - p1.y) * u1y
        t_q2 = (q2.x - p1.x) * u1x + (q2.y - p1.y) * u1y

        s1_min, s1_max = min(t_p1, t_p2), max(t_p1, t_p2)
        s2_min, s2_max = min(t_q1, t_q2), max(t_q1, t_q2)

        ov_start = max(s1_min, s2_min)
        ov_end = min(s1_max, s2_max)
        overlap_len = ov_end - ov_start

        if overlap_len <= GEOM_TOL:
            raise ValueError(
                f"Parallel segments do not have a positive overlapping projection interval "
                f"(overlap_length={overlap_len:.6f} <= 0)."
            )

        # Mid-axis origin shifted halfway along the normal from p1 toward seg2's line
        mid_origin_x = p1.x + 0.5 * signed_sep * nx
        mid_origin_y = p1.y + 0.5 * signed_sep * ny

        unext_start = Point2D(
            mid_origin_x + ov_start * u1x,
            mid_origin_y + ov_start * u1y,
        )
        unext_end = Point2D(
            mid_origin_x + ov_end * u1x,
            mid_origin_y + ov_end * u1y,
        )
        unextended_seg = LineSegment2D(unext_start, unext_end)

        ext_start = Point2D(
            mid_origin_x + (ov_start - ext) * u1x,
            mid_origin_y + (ov_start - ext) * u1y,
        )
        ext_end = Point2D(
            mid_origin_x + (ov_end + ext) * u1x,
            mid_origin_y + (ov_end + ext) * u1y,
        )
        extended_seg = LineSegment2D(ext_start, ext_end)

        return CenterlineResult(
            bisector=extended_seg,
            unextended_bisector=unextended_seg,
            separation_distance=separation,
            overlap_length=overlap_len,
            extension_delta_l=ext,
            midpoint=extended_seg.midpoint,
            unit_direction=(u1x, u1y),
        )


# =============================================================================
# TOOL 4: SlotGenerator (Obround/Slot Geometry, G1 Tangency, Area & Perimeter)
# =============================================================================


@dataclass(frozen=True)
class SlotGeometry:
    """
    Complete analytical representation of a 2D straight obround slot.

    The boundary traverses counter-clockwise (CCW):
    1. Bottom line segment: V1 -> V2
    2. Right (End 2) semicircle arc: V2 -> V3 around center C2
    3. Top line segment: V3 -> V4
    4. Left (End 1) semicircle arc: V4 -> V1 around center C1
    """

    center: Point2D
    center_1: Point2D
    center_2: Point2D
    width: float
    radius: float
    center_distance: float
    overall_length: float
    angle_deg: float
    tangent_vertices: Tuple[Point2D, Point2D, Point2D, Point2D]
    line_segments: Tuple[LineSegment2D, LineSegment2D]
    end_arcs: Tuple[Arc2D, Arc2D]
    area: float
    perimeter: float
    max_g1_tangent_error_rad: float


class SlotGenerator:
    """
    Analytical obround / straight slot generator with exact G1 continuity verification.
    """

    @staticmethod
    def from_center_to_center(
        center: Tuple[float, float] | Point2D,
        center_distance: float,
        width: float,
        angle_deg: float = 0.0,
    ) -> SlotGeometry:
        """
        Generate a slot from its midpoint `center`, center-to-center arc distance `center_distance` (> 0),
        slot width `width` (> 0), and orientation `angle_deg` in degrees.
        """
        c_pt = center if isinstance(center, Point2D) else Point2D(*center)
        L_c = _validate_positive(center_distance, "center_distance")
        W = _validate_positive(width, "width")
        ang_deg = _validate_finite(angle_deg, "angle_deg")

        R = W * 0.5
        overall_len = L_c + W
        theta = math.radians(ang_deg)

        ux = math.cos(theta)
        uy = math.sin(theta)
        nx = -uy
        ny = ux

        half_L = L_c * 0.5
        c1 = Point2D(c_pt.x - half_L * ux, c_pt.y - half_L * uy)
        c2 = Point2D(c_pt.x + half_L * ux, c_pt.y + half_L * uy)

        # 4 Tangent vertices (CCW loop: V1 -> V2 -> V3 -> V4 -> V1)
        # V1: C1 - R*n (Bottom-Left)
        # V2: C2 - R*n (Bottom-Right)
        # V3: C2 + R*n (Top-Right)
        # V4: C1 + R*n (Top-Left)
        v1 = Point2D(c1.x - R * nx, c1.y - R * ny)
        v2 = Point2D(c2.x - R * nx, c2.y - R * ny)
        v3 = Point2D(c2.x + R * nx, c2.y + R * ny)
        v4 = Point2D(c1.x + R * nx, c1.y + R * ny)

        seg_bottom = LineSegment2D(v1, v2)
        seg_top = LineSegment2D(v3, v4)

        # Right semicircle around C2: from theta - pi/2 (V2) to theta + pi/2 (V3)
        arc_right = Arc2D(
            center=c2,
            radius=R,
            start_angle_rad=theta - 0.5 * math.pi,
            end_angle_rad=theta + 0.5 * math.pi,
        )
        # Left semicircle around C1: from theta + pi/2 (V4) to theta + 3*pi/2 (V1)
        arc_left = Arc2D(
            center=c1,
            radius=R,
            start_angle_rad=theta + 0.5 * math.pi,
            end_angle_rad=theta + 1.5 * math.pi,
        )

        # Analytical Area & Perimeter
        area = (W * L_c) + (math.pi * R * R)
        perimeter = (2.0 * L_c) + (math.pi * W)

        # Verify G1 tangent continuity at all 4 vertices
        # For a CCW arc of angle phi, unit tangent is (-sin(phi), cos(phi))
        def _arc_tan(phi: float) -> Tuple[float, float]:
            return (-math.sin(phi), math.cos(phi))

        def _ang_diff(t1: Tuple[float, float], t2: Tuple[float, float]) -> float:
            dot = max(-1.0, min(1.0, t1[0] * t2[0] + t1[1] * t2[1]))
            return math.acos(dot)

        t_bot = seg_bottom.direction
        t_top = seg_top.direction

        err_v1 = _ang_diff(_arc_tan(arc_left.end_angle_rad), t_bot)
        err_v2 = _ang_diff(t_bot, _arc_tan(arc_right.start_angle_rad))
        err_v3 = _ang_diff(_arc_tan(arc_right.end_angle_rad), t_top)
        err_v4 = _ang_diff(t_top, _arc_tan(arc_left.start_angle_rad))
        max_g1_err = max(err_v1, err_v2, err_v3, err_v4)

        return SlotGeometry(
            center=c_pt,
            center_1=c1,
            center_2=c2,
            width=W,
            radius=R,
            center_distance=L_c,
            overall_length=overall_len,
            angle_deg=ang_deg,
            tangent_vertices=(v1, v2, v3, v4),
            line_segments=(seg_bottom, seg_top),
            end_arcs=(arc_right, arc_left),
            area=area,
            perimeter=perimeter,
            max_g1_tangent_error_rad=max_g1_err,
        )

    @staticmethod
    def from_overall_length(
        center: Tuple[float, float] | Point2D,
        overall_length: float,
        width: float,
        angle_deg: float = 0.0,
    ) -> SlotGeometry:
        """
        Generate a slot from its midpoint `center`, total end-to-end `overall_length`,
        slot `width`, and orientation `angle_deg`. Requires `overall_length > width`.
        """
        L_total = _validate_positive(overall_length, "overall_length")
        W = _validate_positive(width, "width")
        if L_total <= W:
            raise ValueError(
                f"Slot overall_length ({L_total}) must be strictly greater than width ({W}) "
                "to form a non-degenerate straight slot."
            )
        return SlotGenerator.from_center_to_center(
            center=center,
            center_distance=L_total - W,
            width=W,
            angle_deg=angle_deg,
        )


# =============================================================================
# TOOL 5: IsoToleranceFit (ISO 286-1 / ISO 286-2 Deviations & Fit Engine)
# =============================================================================


class FitClassification(str, Enum):
    CLEARANCE = "CLEARANCE"
    TRANSITION = "TRANSITION"
    INTERFERENCE = "INTERFERENCE"


# ISO 286-1 Table 1: Nominal diameter steps (mm): (lower_exclusive, upper_inclusive)
# Note: Per ISO 286-1, nominal sizes up to 3 mm covers (0 < D <= 3).
_ISO_SIZE_STEPS: Tuple[Tuple[float, float], ...] = (
    (0.0, 3.0),
    (3.0, 6.0),
    (6.0, 10.0),
    (10.0, 18.0),
    (18.0, 30.0),
    (30.0, 50.0),
    (50.0, 80.0),
    (80.0, 120.0),
    (120.0, 180.0),
    (180.0, 250.0),
    (250.0, 315.0),
    (315.0, 400.0),
    (400.0, 500.0),
)

# Sub-steps for fundamental deviations where ISO 286-2 subdivides main steps (in micrometers, µm)
# Keyed by (lower_exclusive, upper_inclusive)
# Shaft fundamental deviations:
# - Upper deviation `es` (µm) for shafts a-h
# - Lower deviation `ei` (µm) for shafts j-zc
_SHAFT_DEVIATION_TABLES_UM: Dict[str, Tuple[Tuple[float, float, float], ...]] = {
    "c": (
        (0.0, 3.0, -60.0),
        (3.0, 6.0, -70.0),
        (6.0, 10.0, -80.0),
        (10.0, 18.0, -95.0),
        (18.0, 30.0, -110.0),
        (30.0, 40.0, -120.0),
        (40.0, 50.0, -130.0),
        (50.0, 65.0, -140.0),
        (65.0, 80.0, -150.0),
        (80.0, 100.0, -170.0),
        (100.0, 120.0, -180.0),
        (120.0, 140.0, -200.0),
        (140.0, 160.0, -210.0),
        (160.0, 180.0, -230.0),
        (180.0, 200.0, -240.0),
        (200.0, 225.0, -260.0),
        (225.0, 250.0, -280.0),
        (250.0, 280.0, -300.0),
        (280.0, 315.0, -330.0),
        (315.0, 355.0, -360.0),
        (355.0, 400.0, -400.0),
        (400.0, 450.0, -440.0),
        (450.0, 500.0, -480.0),
    ),
    "d": (
        (0.0, 3.0, -20.0),
        (3.0, 6.0, -30.0),
        (6.0, 10.0, -40.0),
        (10.0, 18.0, -50.0),
        (18.0, 30.0, -65.0),
        (30.0, 50.0, -80.0),
        (50.0, 80.0, -100.0),
        (80.0, 120.0, -120.0),
        (120.0, 180.0, -145.0),
        (180.0, 250.0, -170.0),
        (250.0, 315.0, -190.0),
        (315.0, 400.0, -210.0),
        (400.0, 500.0, -230.0),
    ),
    "e": (
        (0.0, 3.0, -14.0),
        (3.0, 6.0, -20.0),
        (6.0, 10.0, -25.0),
        (10.0, 18.0, -32.0),
        (18.0, 30.0, -40.0),
        (30.0, 50.0, -50.0),
        (50.0, 80.0, -60.0),
        (80.0, 120.0, -72.0),
        (120.0, 180.0, -85.0),
        (180.0, 250.0, -100.0),
        (250.0, 315.0, -110.0),
        (315.0, 400.0, -125.0),
        (400.0, 500.0, -135.0),
    ),
    "f": (
        (0.0, 3.0, -6.0),
        (3.0, 6.0, -10.0),
        (6.0, 10.0, -13.0),
        (10.0, 18.0, -16.0),
        (18.0, 30.0, -20.0),
        (30.0, 50.0, -25.0),
        (50.0, 80.0, -30.0),
        (80.0, 120.0, -36.0),
        (120.0, 180.0, -43.0),
        (180.0, 250.0, -50.0),
        (250.0, 315.0, -56.0),
        (315.0, 400.0, -62.0),
        (400.0, 500.0, -68.0),
    ),
    "g": (
        (0.0, 3.0, -2.0),
        (3.0, 6.0, -4.0),
        (6.0, 10.0, -5.0),
        (10.0, 18.0, -6.0),
        (18.0, 30.0, -7.0),
        (30.0, 50.0, -9.0),
        (50.0, 80.0, -10.0),
        (80.0, 120.0, -12.0),
        (120.0, 180.0, -14.0),
        (180.0, 250.0, -15.0),
        (250.0, 315.0, -17.0),
        (315.0, 400.0, -18.0),
        (400.0, 500.0, -20.0),
    ),
    "h": ((0.0, 500.0, 0.0),),
    # k for grades IT4 to IT7 (standard engineering fit k6)
    "k_4_7": (
        (0.0, 3.0, 0.0),
        (3.0, 6.0, 1.0),
        (6.0, 10.0, 1.0),
        (10.0, 18.0, 1.0),
        (18.0, 30.0, 2.0),
        (30.0, 50.0, 2.0),
        (50.0, 80.0, 2.0),
        (80.0, 120.0, 3.0),
        (120.0, 180.0, 3.0),
        (180.0, 250.0, 4.0),
        (250.0, 315.0, 4.0),
        (315.0, 400.0, 4.0),
        (400.0, 500.0, 5.0),
    ),
    "k_other": ((0.0, 500.0, 0.0),),
    "m": (
        (0.0, 3.0, 2.0),
        (3.0, 6.0, 4.0),
        (6.0, 10.0, 6.0),
        (10.0, 18.0, 7.0),
        (18.0, 30.0, 8.0),
        (30.0, 50.0, 9.0),
        (50.0, 80.0, 11.0),
        (80.0, 120.0, 13.0),
        (120.0, 180.0, 15.0),
        (180.0, 250.0, 17.0),
        (250.0, 315.0, 20.0),
        (315.0, 400.0, 21.0),
        (400.0, 500.0, 23.0),
    ),
    "n": (
        (0.0, 3.0, 4.0),
        (3.0, 6.0, 8.0),
        (6.0, 10.0, 10.0),
        (10.0, 18.0, 12.0),
        (18.0, 30.0, 15.0),
        (30.0, 50.0, 17.0),
        (50.0, 80.0, 20.0),
        (80.0, 120.0, 23.0),
        (120.0, 180.0, 27.0),
        (180.0, 250.0, 31.0),
        (250.0, 315.0, 34.0),
        (315.0, 400.0, 37.0),
        (400.0, 500.0, 40.0),
    ),
    "p": (
        (0.0, 3.0, 6.0),
        (3.0, 6.0, 12.0),
        (6.0, 10.0, 15.0),
        (10.0, 18.0, 18.0),
        (18.0, 30.0, 22.0),
        (30.0, 50.0, 26.0),
        (50.0, 80.0, 32.0),
        (80.0, 120.0, 37.0),
        (120.0, 180.0, 43.0),
        (180.0, 250.0, 50.0),
        (250.0, 315.0, 56.0),
        (315.0, 400.0, 62.0),
        (400.0, 500.0, 68.0),
    ),
    "r": (
        (0.0, 3.0, 10.0),
        (3.0, 6.0, 15.0),
        (6.0, 10.0, 19.0),
        (10.0, 18.0, 23.0),
        (18.0, 30.0, 28.0),
        (30.0, 50.0, 34.0),
        (50.0, 65.0, 41.0),
        (65.0, 80.0, 43.0),
        (80.0, 100.0, 51.0),
        (100.0, 120.0, 54.0),
        (120.0, 140.0, 63.0),
        (140.0, 160.0, 65.0),
        (160.0, 180.0, 68.0),
        (180.0, 200.0, 77.0),
        (200.0, 225.0, 80.0),
        (225.0, 250.0, 84.0),
        (250.0, 280.0, 94.0),
        (280.0, 315.0, 98.0),
        (315.0, 355.0, 108.0),
        (355.0, 400.0, 114.0),
        (400.0, 450.0, 126.0),
        (450.0, 500.0, 132.0),
    ),
    "s": (
        (0.0, 3.0, 14.0),
        (3.0, 6.0, 19.0),
        (6.0, 10.0, 23.0),
        (10.0, 18.0, 28.0),
        (18.0, 30.0, 35.0),
        (30.0, 50.0, 43.0),
        (50.0, 65.0, 53.0),
        (65.0, 80.0, 59.0),
        (80.0, 100.0, 71.0),
        (100.0, 120.0, 79.0),
        (120.0, 140.0, 92.0),
        (140.0, 160.0, 100.0),
        (160.0, 180.0, 108.0),
        (180.0, 200.0, 122.0),
        (200.0, 225.0, 130.0),
        (225.0, 250.0, 140.0),
        (250.0, 280.0, 158.0),
        (280.0, 315.0, 170.0),
        (315.0, 355.0, 190.0),
        (355.0, 400.0, 208.0),
        (400.0, 450.0, 232.0),
        (450.0, 500.0, 252.0),
    ),
    "u": (
        (0.0, 3.0, 18.0),
        (3.0, 6.0, 23.0),
        (6.0, 10.0, 28.0),
        (10.0, 18.0, 33.0),
        (18.0, 24.0, 41.0),
        (24.0, 30.0, 48.0),
        (30.0, 40.0, 60.0),
        (40.0, 50.0, 70.0),
        (50.0, 65.0, 87.0),
        (65.0, 80.0, 102.0),
        (80.0, 100.0, 124.0),
        (100.0, 120.0, 144.0),
        (120.0, 140.0, 170.0),
        (140.0, 160.0, 190.0),
        (160.0, 180.0, 210.0),
        (180.0, 200.0, 236.0),
        (200.0, 225.0, 258.0),
        (225.0, 250.0, 284.0),
        (250.0, 280.0, 315.0),
        (280.0, 315.0, 350.0),
        (315.0, 355.0, 390.0),
        (355.0, 400.0, 435.0),
        (400.0, 450.0, 490.0),
        (450.0, 500.0, 540.0),
    ),
}

# ISO 286-1 Standard Tolerance Grades IT5 through IT11 in micrometers (µm)
# Indexed by the 13 main nominal size steps in `_ISO_SIZE_STEPS`.
_IT_TABLE_UM: Dict[int, Tuple[float, ...]] = {
    5: (4.0, 5.0, 6.0, 8.0, 9.0, 11.0, 13.0, 15.0, 18.0, 20.0, 23.0, 25.0, 27.0),
    6: (6.0, 8.0, 9.0, 11.0, 13.0, 16.0, 19.0, 22.0, 25.0, 29.0, 32.0, 36.0, 40.0),
    7: (10.0, 12.0, 15.0, 18.0, 21.0, 25.0, 30.0, 35.0, 40.0, 46.0, 52.0, 57.0, 63.0),
    8: (14.0, 18.0, 22.0, 27.0, 33.0, 39.0, 46.0, 54.0, 63.0, 72.0, 81.0, 89.0, 97.0),
    9: (25.0, 30.0, 36.0, 43.0, 52.0, 62.0, 74.0, 87.0, 100.0, 115.0, 130.0, 140.0, 155.0),
    10: (40.0, 48.0, 58.0, 70.0, 84.0, 100.0, 120.0, 140.0, 160.0, 185.0, 210.0, 230.0, 250.0),
    11: (60.0, 75.0, 90.0, 110.0, 130.0, 160.0, 190.0, 220.0, 250.0, 290.0, 320.0, 360.0, 400.0),
}


@dataclass(frozen=True)
class IsoComponentLimits:
    """ISO 286 tolerance zone result for an individual Hole or Shaft component (in mm)."""

    nominal_dia: float
    symbol: str
    is_hole: bool
    letter: str
    it_grade: int
    it_value_mm: float
    upper_deviation_mm: float  # ES for hole, es for shaft
    lower_deviation_mm: float  # EI for hole, ei for shaft
    max_limit_mm: float
    min_limit_mm: float


@dataclass(frozen=True)
class IsoFitResult:
    """Complete ISO 286 Hole/Shaft fit evaluation result (all dimensions in mm)."""

    nominal_dia: float
    hole_symbol: str
    shaft_symbol: str
    hole: IsoComponentLimits
    shaft: IsoComponentLimits
    ES: float
    EI: float
    es: float
    ei: float
    max_clearance_mm: float
    min_clearance_mm: float
    max_interference_mm: float
    min_interference_mm: float
    fit_type: FitClassification


class IsoToleranceFit:
    """
    ISO 286-1 / ISO 286-2 tolerance calculator for standard mechanical fits.

    Supports nominal sizes 0 < D <= 500 mm, IT grades 5..11, and standard fundamental
    deviation classes:
    - Holes: C, D, E, F, G, H, JS, K, M, N, P, R, S, U
    - Shafts: c, d, e, f, g, h, js, k, m, n, p, r, s, u
    """

    @staticmethod
    def _get_step_index(nominal_dia: float) -> int:
        d = _validate_positive(nominal_dia, "nominal_dia")
        if d > 500.0:
            raise ValueError(
                f"Nominal diameter {d} mm exceeds ISO 286 basic range (0 < D <= 500 mm)."
            )
        for idx, (low, high) in enumerate(_ISO_SIZE_STEPS):
            if low < d <= high:
                return idx
        raise ValueError(f"Nominal diameter {d} mm out of range.")

    @staticmethod
    def _lookup_substep_um(
        nominal_dia: float, table: Tuple[Tuple[float, float, float], ...]
    ) -> float:
        for low, high, val_um in table:
            if low < nominal_dia <= high:
                return val_um
        raise ValueError(f"Nominal diameter {nominal_dia} mm not found in deviation table.")

    @classmethod
    def get_it_tolerance_mm(cls, nominal_dia: float, it_grade: int) -> float:
        """Return standard tolerance IT value in millimeters (mm) for nominal diameter and IT grade."""
        step_idx = cls._get_step_index(nominal_dia)
        if (
            not isinstance(it_grade, int)
            or isinstance(it_grade, bool)
            or it_grade not in _IT_TABLE_UM
        ):
            raise ValueError(
                f"Unsupported IT grade '{it_grade}'. Supported grades: {sorted(_IT_TABLE_UM.keys())}."
            )
        return _IT_TABLE_UM[it_grade][step_idx] * 1e-3

    @classmethod
    def evaluate_component(cls, nominal_dia: float, symbol: str) -> IsoComponentLimits:
        """
        Evaluate a single ISO tolerance symbol (e.g., 'H7', 'g6', 'p6', 'JS7') at `nominal_dia` (mm).
        """
        d = _validate_positive(nominal_dia, "nominal_dia")
        step_idx = cls._get_step_index(d)

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Tolerance symbol must be a non-empty string.")

        m = re.match(r"^(?P<letter>[A-Za-z]+)(?P<grade>\d+)$", symbol.strip())
        if not m:
            raise ValueError(
                f"Invalid ISO tolerance symbol '{symbol}'. Expected format like 'H7', 'g6', 'js6'."
            )

        raw_letter = m.group("letter")
        it_grade = int(m.group("grade"))

        if raw_letter.isupper():
            is_hole = True
            norm_letter = raw_letter.lower()
        elif raw_letter.islower():
            is_hole = False
            norm_letter = raw_letter
        else:
            raise ValueError(f"Mixed-case tolerance letter '{raw_letter}' is invalid in ISO 286.")

        it_um = cls.get_it_tolerance_mm(d, it_grade) * 1e3

        # Symmetrical deviation JS / js
        if norm_letter == "js":
            upper_um = +0.5 * it_um
            lower_um = -0.5 * it_um
        elif not is_hole:
            # Shaft computation
            if norm_letter in ("c", "d", "e", "f", "g", "h"):
                es_um = cls._lookup_substep_um(d, _SHAFT_DEVIATION_TABLES_UM[norm_letter])
                ei_um = es_um - it_um
            elif norm_letter == "k":
                tbl = (
                    _SHAFT_DEVIATION_TABLES_UM["k_4_7"]
                    if 4 <= it_grade <= 7
                    else _SHAFT_DEVIATION_TABLES_UM["k_other"]
                )
                ei_um = cls._lookup_substep_um(d, tbl)
                es_um = ei_um + it_um
            elif norm_letter in ("m", "n", "p", "r", "s", "u"):
                ei_um = cls._lookup_substep_um(d, _SHAFT_DEVIATION_TABLES_UM[norm_letter])
                es_um = ei_um + it_um
            else:
                raise ValueError(f"Unsupported shaft fundamental deviation letter '{raw_letter}'.")
            upper_um, lower_um = es_um, ei_um
        else:
            # Hole computation (ISO 286-1 rule: EI = -es for A-H; ES = -ei + Delta for K-ZC)
            if norm_letter in ("c", "d", "e", "f", "g", "h"):
                es_shaft_um = cls._lookup_substep_um(d, _SHAFT_DEVIATION_TABLES_UM[norm_letter])
                EI_um = -es_shaft_um
                ES_um = EI_um + it_um
            elif norm_letter in ("k", "m", "n", "p", "r", "s", "u"):
                # Delta = IT(n) - IT(n-1) for grades <= 8 when D > 3 mm
                delta_um = 0.0
                if step_idx > 0 and 6 <= it_grade <= 8:
                    delta_um = (
                        _IT_TABLE_UM[it_grade][step_idx] - _IT_TABLE_UM[it_grade - 1][step_idx]
                    )
                if norm_letter == "k":
                    tbl = (
                        _SHAFT_DEVIATION_TABLES_UM["k_4_7"]
                        if 4 <= it_grade <= 8
                        else _SHAFT_DEVIATION_TABLES_UM["k_other"]
                    )
                    ei_shaft_um = cls._lookup_substep_um(d, tbl)
                else:
                    ei_shaft_um = cls._lookup_substep_um(d, _SHAFT_DEVIATION_TABLES_UM[norm_letter])
                ES_um = -ei_shaft_um + delta_um
                EI_um = ES_um - it_um
            else:
                raise ValueError(f"Unsupported hole fundamental deviation letter '{raw_letter}'.")
            upper_um, lower_um = ES_um, EI_um

        upper_mm = round(upper_um * 1e-3, 9)
        lower_mm = round(lower_um * 1e-3, 9)
        it_mm = round(it_um * 1e-3, 9)

        return IsoComponentLimits(
            nominal_dia=d,
            symbol=symbol.strip(),
            is_hole=is_hole,
            letter=raw_letter,
            it_grade=it_grade,
            it_value_mm=it_mm,
            upper_deviation_mm=upper_mm,
            lower_deviation_mm=lower_mm,
            max_limit_mm=round(d + upper_mm, 9),
            min_limit_mm=round(d + lower_mm, 9),
        )

    @classmethod
    def evaluate_fit(
        cls,
        nominal_dia: float,
        hole_symbol: str,
        shaft_symbol: str,
    ) -> IsoFitResult:
        """
        Evaluate a mated ISO 286 Hole and Shaft fit (e.g. nominal_dia=25.0, hole_symbol='H7', shaft_symbol='g6').

        Classifies the fit strictly into:
        - CLEARANCE: min_clearance >= 0 (i.e. EI >= es)
        - INTERFERENCE: max_clearance <= 0 (i.e. ES <= ei)
        - TRANSITION: max_clearance > 0 and min_clearance < 0
        """
        hole = cls.evaluate_component(nominal_dia, hole_symbol)
        if not hole.is_hole:
            raise ValueError(f"hole_symbol '{hole_symbol}' must use uppercase letters (e.g. 'H7').")

        shaft = cls.evaluate_component(nominal_dia, shaft_symbol)
        if shaft.is_hole:
            raise ValueError(
                f"shaft_symbol '{shaft_symbol}' must use lowercase letters (e.g. 'g6')."
            )

        ES = hole.upper_deviation_mm
        EI = hole.lower_deviation_mm
        es = shaft.upper_deviation_mm
        ei = shaft.lower_deviation_mm

        max_clearance = round(ES - ei, 9)
        min_clearance = round(EI - es, 9)

        max_interference = round(-min_clearance, 9)
        min_interference = round(-max_clearance, 9)

        if min_clearance >= -1e-12:
            fit_type = FitClassification.CLEARANCE
        elif max_clearance <= 1e-12:
            fit_type = FitClassification.INTERFERENCE
        else:
            fit_type = FitClassification.TRANSITION

        return IsoFitResult(
            nominal_dia=hole.nominal_dia,
            hole_symbol=hole.symbol,
            shaft_symbol=shaft.symbol,
            hole=hole,
            shaft=shaft,
            ES=ES,
            EI=EI,
            es=es,
            ei=ei,
            max_clearance_mm=max_clearance,
            min_clearance_mm=min_clearance,
            max_interference_mm=max_interference,
            min_interference_mm=min_interference,
            fit_type=fit_type,
        )
