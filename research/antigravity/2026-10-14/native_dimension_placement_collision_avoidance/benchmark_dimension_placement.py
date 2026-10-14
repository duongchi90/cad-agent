"""
Benchmark and empirical evaluation of native CAD dimension placement and collision avoidance.

Compares:
1. Baseline: Current dxf_builder_lib::_add_confirmed_dimensions behavior
   - Single outward normal: (-dy/L, dx/L)
   - Fixed offset: max(length * 0.08, 5.0)
   - No obstacle detection, no alternative side, no lane stacking.
2. Candidate Policy: Deterministic Multi-Lane Dual-Side Placement (Clean-Room Algorithm Transfer)
   - Evaluates both normal directions (+n and -n)
   - Evaluates bounded discrete offset lanes (d_0, d_1, d_2) based on research heuristic lane step increment
   - Deterministic penalty scoring against geometry segments and text/annotation bounding boxes
   - Lexicographic tie-breaking: prefer lowest collision penalty, then lowest lane index, then default normal side
   - Immutable prototype measurement truth: p1 and p2 are NEVER altered. Prototype measurement error is strictly 0.0.
     (PRODUCTION_NATIVE_MEASUREMENT_PRESERVATION=NOT_VERIFIED_BY_THIS_ORACLE).

Evaluates across 10 canonical synthetic engineering fixtures:
1. Isolated horizontal dimension
2. Isolated vertical dimension
3. Rotated/oblique dimension (45 deg)
4. Two nearby parallel dimensions (stacking collision in baseline)
5. Multiple dimensions sharing neighboring geometry (stepped shoulder)
6. One side blocked by model geometry (internal pocket / boss)
7. One side blocked by text/annotation obstacle (notes / callout box)
8. Crowded short measured segments (tight clearance)
9. Dimension close to sheet/view boundary (boundary clipping in baseline)
10. Mixed orientations in local region (perpendicular crossing hazards)

Measures:
- BASELINE_COLLISION_COUNT
- CANDIDATE_COLLISION_COUNT
- DIMENSION_TO_GEOMETRY_CROSSINGS
- DIMENSION_TO_ANNOTATION_OVERLAPS
- EXTENSION_LINE_UNWANTED_CROSSINGS
- MIN_OBSERVED_CLEARANCE
- MEASUREMENT_ERROR
- PLACEMENT_DISPLACEMENT
- DETERMINISTIC_REPEATABILITY
- UNRESOLVED_SCENES
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

Point2D = Tuple[float, float]
Segment2D = Tuple[Point2D, Point2D]
BBox2D = Tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax)
TextCorners = Tuple[Point2D, Point2D, Point2D, Point2D]  # (C1, C2, C3, C4) oriented rectangle

DEFAULT_SYNTHETIC_TEXT_WIDTH_MM: float = 12.0   # SYNTHETIC_RESEARCH_STYLE_PROXY
DEFAULT_SYNTHETIC_TEXT_HEIGHT_MM: float = 3.5  # SYNTHETIC_RESEARCH_STYLE_PROXY


# ---------------------------------------------------------------------------
# 2D Geometric Primitives & SAT Collision Routines
# ---------------------------------------------------------------------------

def ccw(a: Point2D, b: Point2D, c: Point2D) -> bool:
    return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])


def segments_intersect(s1: Segment2D, s2: Segment2D) -> bool:
    """Return True if line segment s1 strictly or endpoint-intersects segment s2."""
    p1, p2 = s1
    p3, p4 = s2

    # Check bounding box pre-filter
    if (max(p1[0], p2[0]) < min(p3[0], p4[0]) or
        max(p3[0], p4[0]) < min(p1[0], p2[0]) or
        max(p1[1], p2[1]) < min(p3[1], p4[1]) or
        max(p3[1], p4[1]) < min(p1[1], p2[1])):
        return False

    def on_segment(p: Point2D, q: Point2D, r: Point2D) -> bool:
        return (q[0] <= max(p[0], r[0]) and q[0] >= min(p[0], r[0]) and
                q[1] <= max(p[1], r[1]) and q[1] >= min(p[1], r[1]))

    def orientation(p: Point2D, q: Point2D, r: Point2D) -> int:
        val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
        if abs(val) < 1e-9:
            return 0  # Collinear
        return 1 if val > 0 else 2  # Clockwise or Counterclockwise

    o1 = orientation(p1, p2, p3)
    o2 = orientation(p1, p2, p4)
    o3 = orientation(p3, p4, p1)
    o4 = orientation(p3, p4, p2)

    # General case
    if o1 != o2 and o3 != o4:
        return True

    # Special collinear cases
    if o1 == 0 and on_segment(p1, p3, p2):
        return True
    if o2 == 0 and on_segment(p1, p4, p2):
        return True
    if o3 == 0 and on_segment(p3, p1, p4):
        return True
    if o4 == 0 and on_segment(p3, p2, p4):
        return True

    return False


def segment_intersects_bbox(seg: Segment2D, bbox: BBox2D) -> bool:
    """Return True if segment intersects bounding box (boundary or interior)."""
    p1, p2 = seg
    xmin, ymin, xmax, ymax = bbox

    # Check if either endpoint is inside bbox
    if (xmin <= p1[0] <= xmax and ymin <= p1[1] <= ymax) or \
       (xmin <= p2[0] <= xmax and ymin <= p2[1] <= ymax):
        return True

    # Check intersection with 4 bbox boundary edges
    box_edges: List[Segment2D] = [
        ((xmin, ymin), (xmax, ymin)),
        ((xmax, ymin), (xmax, ymax)),
        ((xmax, ymax), (xmin, ymax)),
        ((xmin, ymax), (xmin, ymin)),
    ]
    return any(segments_intersect(seg, edge) for edge in box_edges)


def bboxes_overlap(b1: BBox2D, b2: BBox2D) -> bool:
    """Return True if two axis-aligned bounding boxes overlap."""
    return not (b1[2] <= b2[0] or b2[2] <= b1[0] or b1[3] <= b2[1] or b2[3] <= b1[1])


def point_segment_distance(pt: Point2D, seg: Segment2D) -> float:
    """Euclidean distance from point pt to line segment."""
    p1, p2 = seg
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return math.hypot(pt[0] - p1[0], pt[1] - p1[1])
    t = max(0.0, min(1.0, ((pt[0] - p1[0]) * dx + (pt[1] - p1[1]) * dy) / L2))
    proj_x = p1[0] + t * dx
    proj_y = p1[1] + t * dy
    return math.hypot(pt[0] - proj_x, pt[1] - proj_y)


def _project_points(points: Tuple[Point2D, ...] | List[Point2D], axis: Point2D) -> Tuple[float, float]:
    """Project a sequence of 2D points onto an axis and return (min_proj, max_proj)."""
    p0 = points[0][0] * axis[0] + points[0][1] * axis[1]
    min_p = p0
    max_p = p0
    for p in points[1:]:
        val = p[0] * axis[0] + p[1] * axis[1]
        if val < min_p:
            min_p = val
        elif val > max_p:
            max_p = val
    return min_p, max_p


def _intervals_overlap(min1: float, max1: float, min2: float, max2: float, tol: float = 1e-9) -> bool:
    """Return True if 1D intervals [min1, max1] and [min2, max2] overlap (including touching)."""
    return not (max1 < min2 - tol or max2 < min1 - tol)


def text_within_bounds(text_corners: Tuple[Point2D, Point2D, Point2D, Point2D], sheet_boundary: BBox2D) -> bool:
    """Return True if all 4 corners of text rectangle lie within the sheet boundary."""
    xmin, ymin, xmax, ymax = sheet_boundary
    for c in text_corners:
        if not (xmin <= c[0] <= xmax and ymin <= c[1] <= ymax):
            return False
    return True


def text_intersects_segment(text_corners: Tuple[Point2D, Point2D, Point2D, Point2D], seg: Segment2D) -> bool:
    """
    Return True if oriented text rectangle intersects segment seg using Separating Axis Theorem (SAT).
    Tests 3 axes: the 2 edge normals of the text rectangle and the segment normal.
    """
    p1, p2 = seg
    # Broad-phase AABB pre-filter
    seg_min_x = min(p1[0], p2[0])
    seg_max_x = max(p1[0], p2[0])
    seg_min_y = min(p1[1], p2[1])
    seg_max_y = max(p1[1], p2[1])

    c_min_x = min(c[0] for c in text_corners)
    c_max_x = max(c[0] for c in text_corners)
    c_min_y = min(c[1] for c in text_corners)
    c_max_y = max(c[1] for c in text_corners)

    if c_max_x < seg_min_x - 1e-9 or seg_max_x < c_min_x - 1e-9 or \
       c_max_y < seg_min_y - 1e-9 or seg_max_y < c_min_y - 1e-9:
        return False

    # Axis 1: Edge along rectangle width (c1 - c2)
    axis_u = (text_corners[0][0] - text_corners[1][0], text_corners[0][1] - text_corners[1][1])
    # Axis 2: Edge along rectangle height (c1 - c4)
    axis_n = (text_corners[0][0] - text_corners[3][0], text_corners[0][1] - text_corners[3][1])

    seg_pts = (p1, p2)

    min_c, max_c = _project_points(text_corners, axis_u)
    min_s, max_s = _project_points(seg_pts, axis_u)
    if not _intervals_overlap(min_c, max_c, min_s, max_s):
        return False

    min_c, max_c = _project_points(text_corners, axis_n)
    min_s, max_s = _project_points(seg_pts, axis_n)
    if not _intervals_overlap(min_c, max_c, min_s, max_s):
        return False

    # Axis 3: Segment normal (-(p2.y - p1.y), p2.x - p1.x)
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    if abs(dx) > 1e-12 or abs(dy) > 1e-12:
        axis_seg = (-dy, dx)
        min_c, max_c = _project_points(text_corners, axis_seg)
        min_s, max_s = _project_points(seg_pts, axis_seg)
        if not _intervals_overlap(min_c, max_c, min_s, max_s):
            return False

    return True


def text_intersects_bbox(text_corners: Tuple[Point2D, Point2D, Point2D, Point2D], bbox: BBox2D) -> bool:
    """
    Return True if oriented text rectangle intersects axis-aligned bounding box using SAT.
    Tests 4 axes: axis_u, axis_n of text rectangle, and (1, 0), (0, 1) of bbox.
    """
    xmin, ymin, xmax, ymax = bbox

    # Check axes (1, 0) and (0, 1) first (broad-phase AABB overlap)
    c_min_x = min(c[0] for c in text_corners)
    c_max_x = max(c[0] for c in text_corners)
    if c_max_x < xmin - 1e-9 or xmax < c_min_x - 1e-9:
        return False

    c_min_y = min(c[1] for c in text_corners)
    c_max_y = max(c[1] for c in text_corners)
    if c_max_y < ymin - 1e-9 or ymax < c_min_y - 1e-9:
        return False

    bbox_corners = ((xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax))

    # Axis u
    axis_u = (text_corners[0][0] - text_corners[1][0], text_corners[0][1] - text_corners[1][1])
    min_c, max_c = _project_points(text_corners, axis_u)
    min_b, max_b = _project_points(bbox_corners, axis_u)
    if not _intervals_overlap(min_c, max_c, min_b, max_b):
        return False

    # Axis n
    axis_n = (text_corners[0][0] - text_corners[3][0], text_corners[0][1] - text_corners[3][1])
    min_c, max_c = _project_points(text_corners, axis_n)
    min_b, max_b = _project_points(bbox_corners, axis_n)
    if not _intervals_overlap(min_c, max_c, min_b, max_b):
        return False

    return True


def texts_intersect(
    text1_corners: Tuple[Point2D, Point2D, Point2D, Point2D],
    text2_corners: Tuple[Point2D, Point2D, Point2D, Point2D],
) -> bool:
    """
    Return True if two oriented text rectangles intersect using SAT.
    Tests 4 axes: 2 edge normals of text1 and 2 edge normals of text2.
    """
    # Broad-phase AABB check
    min1_x = min(c[0] for c in text1_corners)
    max1_x = max(c[0] for c in text1_corners)
    min2_x = min(c[0] for c in text2_corners)
    max2_x = max(c[0] for c in text2_corners)
    if max1_x < min2_x - 1e-9 or max2_x < min1_x - 1e-9:
        return False

    min1_y = min(c[1] for c in text1_corners)
    max1_y = max(c[1] for c in text1_corners)
    min2_y = min(c[1] for c in text2_corners)
    max2_y = max(c[1] for c in text2_corners)
    if max1_y < min2_y - 1e-9 or max2_y < min1_y - 1e-9:
        return False

    # Axes of text1 and text2
    axes = [
        (text1_corners[0][0] - text1_corners[1][0], text1_corners[0][1] - text1_corners[1][1]),
        (text1_corners[0][0] - text1_corners[3][0], text1_corners[0][1] - text1_corners[3][1]),
        (text2_corners[0][0] - text2_corners[1][0], text2_corners[0][1] - text2_corners[1][1]),
        (text2_corners[0][0] - text2_corners[3][0], text2_corners[0][1] - text2_corners[3][1]),
    ]

    for axis in axes:
        min1, max1 = _project_points(text1_corners, axis)
        min2, max2 = _project_points(text2_corners, axis)
        if not _intervals_overlap(min1, max1, min2, max2):
            return False

    return True


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class MeasuredSegment:
    spec_id: str
    start: Point2D
    end: Point2D
    text_override: Optional[str] = None


@dataclass
class AnnotationObstacle:
    name: str
    bbox: BBox2D  # (xmin, ymin, xmax, ymax)


@dataclass
class Scene:
    name: str
    description: str
    measured_segments: List[MeasuredSegment]
    geometry_segments: List[Segment2D]
    annotation_obstacles: List[AnnotationObstacle]
    sheet_boundary: BBox2D = (0.0, 0.0, 500.0, 500.0)


@dataclass
class PlacedDimension:
    spec_id: str
    side: int  # +1 or -1
    lane_index: int  # 0, 1, 2...
    offset: float
    base: Point2D
    dim_line_start: Point2D
    dim_line_end: Point2D
    ext_line_1_start: Point2D
    ext_line_1_end: Point2D
    ext_line_2_start: Point2D
    ext_line_2_end: Point2D
    text_bbox: BBox2D
    measured_length: float
    dimension_length: float
    text_corners: TextCorners = (
        (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)
    )


@dataclass
class PlacementEvaluation:
    fixture_name: str
    policy: str  # "Baseline_Fixed_Offset" vs "Candidate_Deterministic_MultiLane"
    total_dimensions: int
    collision_count: int
    dim_to_geometry_crossings: int
    dim_to_annotation_overlaps: int
    extension_unwanted_crossings: int
    min_observed_clearance: float
    prototype_measurement_error: float
    unresolved_dimensions: int


# ---------------------------------------------------------------------------
# Dimension Geometry Calculation Helper
# ---------------------------------------------------------------------------

def compute_dimension_geometry(
    start: Point2D,
    end: Point2D,
    offset: float,
    side: int,
    text_w: float = DEFAULT_SYNTHETIC_TEXT_WIDTH_MM,
    text_h: float = DEFAULT_SYNTHETIC_TEXT_HEIGHT_MM,
    ext_gap: float = 1.0,
    ext_overshoot: float = 2.0,
) -> Tuple[Point2D, Segment2D, Segment2D, Segment2D, BBox2D, float, TextCorners]:
    """
    Compute dimension line, extension lines, derived text bbox, dimension line length,
    and oriented text rectangle corners for a given side and offset.
    p1 = start, p2 = end.
    Side +1 uses outward normal (-dy/L, dx/L).
    Side -1 uses inward normal (dy/L, -dx/L).
    Text corners are aligned with dimension line unit vector u = (dx/L, dy/L)
    and unit normal vector n = ((-dy/L)*side, (dx/L)*side).
    """
    dx, dy = end[0] - start[0], end[1] - start[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        raise ValueError("Cannot dimension zero-length segment")

    # Unit vector along dimension line
    ux, uy = dx / L, dy / L

    # Unit normal vector
    nx, ny = (-dy / L) * side, (dx / L) * side
    mid_x, mid_y = (start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0

    base: Point2D = (mid_x + nx * offset, mid_y + ny * offset)

    dim_start: Point2D = (start[0] + nx * offset, start[1] + ny * offset)
    dim_end: Point2D = (end[0] + nx * offset, end[1] + ny * offset)
    dim_segment: Segment2D = (dim_start, dim_end)

    # Extension lines
    total_ext_reach = offset + ext_overshoot
    ext1_start: Point2D = (start[0] + nx * ext_gap, start[1] + ny * ext_gap)
    ext1_end: Point2D = (start[0] + nx * total_ext_reach, start[1] + ny * total_ext_reach)
    ext_seg1: Segment2D = (ext1_start, ext1_end)

    ext2_start: Point2D = (end[0] + nx * ext_gap, end[1] + ny * ext_gap)
    ext2_end: Point2D = (end[0] + nx * total_ext_reach, end[1] + ny * total_ext_reach)
    ext_seg2: Segment2D = (ext2_start, ext2_end)

    # Oriented text rectangle corners centered at base
    half_w, half_h = text_w / 2.0, text_h / 2.0
    c1: Point2D = (base[0] + half_w * ux + half_h * nx, base[1] + half_w * uy + half_h * ny)
    c2: Point2D = (base[0] - half_w * ux + half_h * nx, base[1] - half_w * uy + half_h * ny)
    c3: Point2D = (base[0] - half_w * ux - half_h * nx, base[1] - half_w * uy - half_h * ny)
    c4: Point2D = (base[0] + half_w * ux - half_h * nx, base[1] + half_w * uy - half_h * ny)
    text_corners: TextCorners = (c1, c2, c3, c4)

    # Derived enclosing axis-aligned bounding box (envelope / broad-phase)
    text_bbox: BBox2D = (
        min(c[0] for c in text_corners),
        min(c[1] for c in text_corners),
        max(c[0] for c in text_corners),
        max(c[1] for c in text_corners),
    )

    dim_line_len = math.hypot(dim_end[0] - dim_start[0], dim_end[1] - dim_start[1])

    return base, dim_segment, ext_seg1, ext_seg2, text_bbox, dim_line_len, text_corners


# ---------------------------------------------------------------------------
# Baseline Policy: Current dxf_builder_lib Implementation
# ---------------------------------------------------------------------------

def place_dimensions_baseline(scene: Scene) -> List[PlacedDimension]:
    """
    Reproduces current dxf_builder_lib/builder.py::_add_confirmed_dimensions behavior:
    offset = max(length * 0.08, 5.0)
    normal = (-dy/L, dx/L) (single deterministic side, side = +1)
    No obstacle awareness, no lane search.
    """
    placed: List[PlacedDimension] = []
    for spec in scene.measured_segments:
        start, end = spec.start, spec.end
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        offset = max(length * 0.08, 5.0)
        side = +1

        base, dim_seg, ext1, ext2, text_bbox, dim_len, text_corners = compute_dimension_geometry(
            start, end, offset, side
        )

        placed.append(PlacedDimension(
            spec_id=spec.spec_id,
            side=side,
            lane_index=0,
            offset=offset,
            base=base,
            dim_line_start=dim_seg[0],
            dim_line_end=dim_seg[1],
            ext_line_1_start=ext1[0],
            ext_line_1_end=ext1[1],
            ext_line_2_start=ext2[0],
            ext_line_2_end=ext2[1],
            text_bbox=text_bbox,
            measured_length=length,
            dimension_length=dim_len,
            text_corners=text_corners,
        ))
    return placed


# ---------------------------------------------------------------------------
# Candidate Policy: Deterministic Multi-Lane Dual-Side Placement
# ---------------------------------------------------------------------------

def count_unary_extension_crossings(
    ext1: Segment2D,
    ext2: Segment2D,
    g_seg: Segment2D,
    measured_seg: Optional[Segment2D] = None,
) -> int:
    """
    Count unwanted extension witness line crossings against a model geometry segment.
    Excludes the measured segment itself and endpoint touches where witness lines start.
    Evaluates ext1 and ext2 independently, returning 0, 1, or 2 crossings.
    """
    if measured_seg is not None:
        if g_seg == measured_seg or (g_seg[1] == measured_seg[0] and g_seg[0] == measured_seg[1]):
            return 0

    crossings = 0
    if segments_intersect(ext1, g_seg):
        if math.hypot(g_seg[0][0] - ext1[0][0], g_seg[0][1] - ext1[0][1]) > 1e-4 and \
           math.hypot(g_seg[1][0] - ext1[0][0], g_seg[1][1] - ext1[0][1]) > 1e-4:
            crossings += 1

    if segments_intersect(ext2, g_seg):
        if math.hypot(g_seg[0][0] - ext2[0][0], g_seg[0][1] - ext2[0][1]) > 1e-4 and \
           math.hypot(g_seg[1][0] - ext2[0][0], g_seg[1][1] - ext2[0][1]) > 1e-4:
            crossings += 1

    return crossings


def score_candidate(
    dim_seg: Segment2D,
    ext1: Segment2D,
    ext2: Segment2D,
    text_geometry: TextCorners | BBox2D,
    side: int,
    lane_idx: int,
    scene: Scene,
    already_placed: List[PlacedDimension],
    measured_seg: Segment2D,
) -> Tuple[int, float]:
    """
    Compute deterministic penalty score for a candidate dimension placement.
    Returns (hard_collision_count, soft_penalty_score).
    Zero hard collisions strictly beats any non-zero hard collisions (MF-07).
    Uses orientation-aware text rectangle footprint (exact parity with evaluator).
    """
    hard_collisions = 0
    soft_penalty = 0.0

    if isinstance(text_geometry[0], (int, float)):
        xmin, ymin, xmax, ymax = text_geometry  # type: ignore[misc]
        text_corners: TextCorners = (
            (xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)
        )
    else:
        text_corners = text_geometry  # type: ignore[assignment]

    # 1. Out of sheet bounds penalty (hardest rejection)
    if not text_within_bounds(text_corners, scene.sheet_boundary):
        hard_collisions += 1

    # 2. Dimension line crossings with model geometry (excluding the measured segment itself)
    for g_seg in scene.geometry_segments:
        if g_seg == measured_seg or (g_seg[1] == measured_seg[0] and g_seg[0] == measured_seg[1]):
            continue
        if segments_intersect(dim_seg, g_seg):
            hard_collisions += 1

    # 3. Dimension text overlapping model geometry (orientation-aware SAT)
    for g_seg in scene.geometry_segments:
        if text_intersects_segment(text_corners, g_seg):
            hard_collisions += 1

    # 4. Dimension line or text overlapping annotation obstacles (notes, labels, callouts)
    for obs in scene.annotation_obstacles:
        if segment_intersects_bbox(dim_seg, obs.bbox):
            hard_collisions += 1
        if text_intersects_bbox(text_corners, obs.bbox):
            hard_collisions += 1

    # 5. Extension lines crossing model geometry (unwanted witness crossing: soft penalty)
    for g_seg in scene.geometry_segments:
        crossings = count_unary_extension_crossings(ext1, ext2, g_seg, measured_seg)
        soft_penalty += crossings * 150.0

    # 6. Interaction with already placed dimensions
    for p in already_placed:
        p_dim_seg = (p.dim_line_start, p.dim_line_end)
        # Dimension lines crossing each other (severe drafting violation)
        if segments_intersect(dim_seg, p_dim_seg):
            hard_collisions += 1
        # Text overlapping previously placed dimension text (orientation-aware SAT)
        if texts_intersect(text_corners, p.text_corners):
            hard_collisions += 1
        # Text overlapping previously placed dimension line (orientation-aware SAT)
        if text_intersects_segment(text_corners, p_dim_seg):
            hard_collisions += 1
        # Dimension line overlapping previously placed text (orientation-aware SAT)
        if text_intersects_segment(p.text_corners, dim_seg):
            hard_collisions += 1

        # Symmetric extension line crossing checks (soft penalties, 300.0 each)
        # Extension lines crossing previously placed dimension line
        if segments_intersect(ext1, p_dim_seg):
            soft_penalty += 300.0
        if segments_intersect(ext2, p_dim_seg):
            soft_penalty += 300.0

        # Dimension line crossing previously placed extension lines (MF-07 symmetric check)
        p_ext1 = (p.ext_line_1_start, p.ext_line_1_end)
        p_ext2 = (p.ext_line_2_start, p.ext_line_2_end)
        if segments_intersect(dim_seg, p_ext1):
            soft_penalty += 300.0
        if segments_intersect(dim_seg, p_ext2):
            soft_penalty += 300.0

    # 7. Soft lane penalty: prefer lower lanes (closer to measured feature, standard drafting nesting)
    soft_penalty += lane_idx * 15.0

    # 8. Soft side tie-breaker: prefer default Side +1 over Side -1 when all else is equal
    if side == -1:
        soft_penalty += 1.0

    return hard_collisions, soft_penalty


def _spec_sort_key(s: MeasuredSegment) -> Tuple[float, Tuple[float, float], Tuple[float, float], str]:
    """Canonical tie-break sort key ensuring benchmark execution is independent of input-list order (MF-03)."""
    dx = s.end[0] - s.start[0]
    dy = s.end[1] - s.start[1]
    length = round(math.hypot(dx, dy), 6)
    p_min = min(s.start, s.end)
    p_max = max(s.start, s.end)
    return (length, p_min, p_max, s.spec_id)


def place_dimensions_candidate(scene: Scene) -> List[PlacedDimension]:
    """
    Deterministic Multi-Lane Dual-Side Placement Policy:
    1. Order dimensions canonically by length ascending, tie-breaking by endpoints and spec_id (MF-03).
       (Standard drafting rule: overall dimensions placed further out, smaller inside).
    2. For each dimension, evaluate 6 discrete candidates:
       - 2 sides: +1 (left normal), -1 (right normal)
       - 3 lanes: lane 0 (base offset), lane 1 (base + delta), lane 2 (base + 2*delta)
       where delta = max(7.5, text_height * 2.0) is a research heuristic lane step.
    3. Score each candidate: primary key = hard_collision_count, secondary key = soft_penalty_score (MF-07).
    4. Select minimum penalty candidate with lexicographic tie-breaking:
       (hard_collisions, soft_penalty, lane_idx, side_preference).
    """
    placed: List[PlacedDimension] = []

    # Sort specs canonically to be independent of input list ordering
    specs = sorted(scene.measured_segments, key=_spec_sort_key)

    for spec in specs:
        start, end = spec.start, spec.end
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        base_offset = max(length * 0.08, 6.0)  # Research heuristic base offset
        lane_step = max(7.5, 3.5 * 2.0)        # Research heuristic lane step increment

        best_key: Tuple[int, float, int, int] = (999999, float('inf'), 999, 999)
        best_placed: Optional[PlacedDimension] = None

        # Candidate grid: 2 sides x 3 lanes = 6 candidates
        candidate_options = [
            (side, lane_idx, base_offset + lane_idx * lane_step)
            for lane_idx in [0, 1, 2]
            for side in [+1, -1]
        ]

        for side, lane_idx, offset in candidate_options:
            base, dim_seg, ext1, ext2, text_bbox, dim_len, text_corners = compute_dimension_geometry(
                start, end, offset, side
            )
            hard_count, soft_score = score_candidate(
                dim_seg, ext1, ext2, text_corners, side, lane_idx,
                scene, placed, (start, end)
            )

            side_pref = 0 if side == 1 else 1
            cand_key = (hard_count, soft_score, lane_idx, side_pref)

            if cand_key < best_key:
                best_key = cand_key
                best_placed = PlacedDimension(
                    spec_id=spec.spec_id,
                    side=side,
                    lane_index=lane_idx,
                    offset=offset,
                    base=base,
                    dim_line_start=dim_seg[0],
                    dim_line_end=dim_seg[1],
                    ext_line_1_start=ext1[0],
                    ext_line_1_end=ext1[1],
                    ext_line_2_start=ext2[0],
                    ext_line_2_end=ext2[1],
                    text_bbox=text_bbox,
                    measured_length=length,
                    dimension_length=dim_len,
                    text_corners=text_corners,
                )

        if best_placed is not None:
            placed.append(best_placed)

    return placed


# ---------------------------------------------------------------------------
# Metric Evaluator
# ---------------------------------------------------------------------------

def evaluate_placement_scene(
    scene: Scene,
    placed: List[PlacedDimension],
    policy_name: str,
) -> PlacementEvaluation:
    total_dims = len(placed)
    dim_geom_crossings = 0
    dim_annot_overlaps = 0
    ext_crossings = 0
    min_clearance = float('inf')
    max_proto_err = 0.0
    unresolved_indices: set[int] = set()

    # Calculate measurement error
    for p in placed:
        err = abs(p.dimension_length - p.measured_length)
        if err > max_proto_err:
            max_proto_err = err

    # 1. Unary checks per placed dimension
    spec_map = {s.spec_id: (s.start, s.end) for s in scene.measured_segments}

    for i, p in enumerate(placed):
        dim_seg = (p.dim_line_start, p.dim_line_end)
        ext1 = (p.ext_line_1_start, p.ext_line_1_end)
        ext2 = (p.ext_line_2_start, p.ext_line_2_end)
        measured_seg = spec_map.get(p.spec_id)

        # Out of bounds check (orientation-aware)
        if not text_within_bounds(p.text_corners, scene.sheet_boundary):
            dim_annot_overlaps += 1
            unresolved_indices.add(i)

        # Check vs geometry segments
        for g in scene.geometry_segments:
            if segments_intersect(dim_seg, g):
                dim_geom_crossings += 1
                unresolved_indices.add(i)
            if text_intersects_segment(p.text_corners, g):
                dim_annot_overlaps += 1
                unresolved_indices.add(i)

            ext_crossings += count_unary_extension_crossings(ext1, ext2, g, measured_seg)

            # Clearance check
            d1 = point_segment_distance(p.base, g)
            if d1 < min_clearance:
                min_clearance = d1

        # Check vs annotation obstacles
        for obs in scene.annotation_obstacles:
            if segment_intersects_bbox(dim_seg, obs.bbox):
                dim_annot_overlaps += 1
                unresolved_indices.add(i)
            if text_intersects_bbox(p.text_corners, obs.bbox):
                dim_annot_overlaps += 1
                unresolved_indices.add(i)

    # 2. Pairwise checks between placed dimensions (MF-02 evaluator symmetry, orientation-aware)
    for i in range(len(placed)):
        p1 = placed[i]
        p1_dim = (p1.dim_line_start, p1.dim_line_end)
        for j in range(i + 1, len(placed)):
            p2 = placed[j]
            p2_dim = (p2.dim_line_start, p2.dim_line_end)

            # Dimension lines intersecting each other
            if segments_intersect(p1_dim, p2_dim):
                dim_geom_crossings += 1
                unresolved_indices.add(i)
                unresolved_indices.add(j)

            # Text footprints overlapping each other (orientation-aware SAT)
            if texts_intersect(p1.text_corners, p2.text_corners):
                dim_annot_overlaps += 1
                unresolved_indices.add(i)
                unresolved_indices.add(j)

            # Text vs Dimension Line (symmetric: dim2 vs text1, and dim1 vs text2)
            if text_intersects_segment(p1.text_corners, p2_dim):
                dim_annot_overlaps += 1
                unresolved_indices.add(i)
                unresolved_indices.add(j)
            if text_intersects_segment(p2.text_corners, p1_dim):
                dim_annot_overlaps += 1
                unresolved_indices.add(i)
                unresolved_indices.add(j)

            # Pairwise soft extension line interactions (R1)
            p1_ext1 = (p1.ext_line_1_start, p1.ext_line_1_end)
            p1_ext2 = (p1.ext_line_2_start, p1.ext_line_2_end)
            p2_ext1 = (p2.ext_line_1_start, p2.ext_line_1_end)
            p2_ext2 = (p2.ext_line_2_start, p2.ext_line_2_end)

            if segments_intersect(p1_ext1, p2_dim):
                ext_crossings += 1
            if segments_intersect(p1_ext2, p2_dim):
                ext_crossings += 1
            if segments_intersect(p2_ext1, p1_dim):
                ext_crossings += 1
            if segments_intersect(p2_ext2, p1_dim):
                ext_crossings += 1

    total_collisions = dim_geom_crossings + dim_annot_overlaps

    if min_clearance == float('inf'):
        min_clearance = 50.0  # default when no obstacles present

    return PlacementEvaluation(
        fixture_name=scene.name,
        policy=policy_name,
        total_dimensions=total_dims,
        collision_count=total_collisions,
        dim_to_geometry_crossings=dim_geom_crossings,
        dim_to_annotation_overlaps=dim_annot_overlaps,
        extension_unwanted_crossings=ext_crossings,
        min_observed_clearance=round(min_clearance, 3),
        prototype_measurement_error=round(max_proto_err, 6),
        unresolved_dimensions=len(unresolved_indices),
    )


# ---------------------------------------------------------------------------
# 10 Canonical Synthetic Engineering Fixtures
# ---------------------------------------------------------------------------

def create_fixtures() -> List[Scene]:
    scenes: List[Scene] = []

    # Fixture 1: Isolated horizontal dimension
    scenes.append(Scene(
        name="fixture_1_isolated_horizontal",
        description="Isolated horizontal 100 mm line with clear clearance on both sides",
        measured_segments=[
            MeasuredSegment("D1", (100.0, 200.0), (200.0, 200.0)),
        ],
        geometry_segments=[
            ((100.0, 200.0), (200.0, 200.0)),
        ],
        annotation_obstacles=[],
    ))

    # Fixture 2: Isolated vertical dimension
    scenes.append(Scene(
        name="fixture_2_isolated_vertical",
        description="Isolated vertical 80 mm line with clear clearance on both sides",
        measured_segments=[
            MeasuredSegment("D1", (150.0, 100.0), (150.0, 180.0)),
        ],
        geometry_segments=[
            ((150.0, 100.0), (150.0, 180.0)),
        ],
        annotation_obstacles=[],
    ))

    # Fixture 3: Rotated / oblique dimension (45 deg)
    scenes.append(Scene(
        name="fixture_3_rotated_oblique_45deg",
        description="45-degree chamfer edge length 50 mm",
        measured_segments=[
            MeasuredSegment("D1", (100.0, 100.0), (135.355, 135.355)),
        ],
        geometry_segments=[
            ((100.0, 100.0), (135.355, 135.355)),
        ],
        annotation_obstacles=[],
    ))

    # Fixture 4: Two nearby parallel dimensions (Stacking collision in baseline)
    # Line 1: (100, 200) to (180, 200) [inner, length 80]
    # Line 2: (100, 206) to (220, 206) [outer, length 120] separated by 6 mm
    # Baseline puts Line 1 at offset 6.4 (y=206.4), directly colliding with Line 2!
    scenes.append(Scene(
        name="fixture_4_two_nearby_parallel",
        description="Two parallel stepped edges separated by 6 mm causing baseline lane collision",
        measured_segments=[
            MeasuredSegment("D1", (100.0, 200.0), (180.0, 200.0)),
            MeasuredSegment("D2", (100.0, 208.0), (220.0, 208.0)),
        ],
        geometry_segments=[
            ((100.0, 200.0), (180.0, 200.0)),
            ((180.0, 200.0), (180.0, 208.0)),
            ((180.0, 208.0), (220.0, 208.0)),
        ],
        annotation_obstacles=[],
    ))

    # Fixture 5: Multiple dimensions sharing neighboring geometry (stepped shoulder)
    scenes.append(Scene(
        name="fixture_5_multiple_sharing_geometry",
        description="Three adjacent collinear shoulder segments sharing witness boundaries",
        measured_segments=[
            MeasuredSegment("D1", (100.0, 150.0), (140.0, 150.0)),
            MeasuredSegment("D2", (140.0, 150.0), (190.0, 150.0)),
            MeasuredSegment("D3", (100.0, 150.0), (190.0, 150.0)),  # Overall dim
        ],
        geometry_segments=[
            ((100.0, 150.0), (190.0, 150.0)),
            ((100.0, 100.0), (100.0, 150.0)),
            ((190.0, 100.0), (190.0, 150.0)),
        ],
        annotation_obstacles=[],
    ))

    # Fixture 6: One side blocked by model geometry (internal pocket / boss)
    # Horizontal line at y=200 from x=100 to x=200.
    # Left-hand normal points +y (y > 200).
    # But a solid pocket exists at [120..180, 202..230] directly on +y side!
    scenes.append(Scene(
        name="fixture_6_one_side_blocked_by_geometry",
        description="Measured edge with model geometry obstacle on +normal side; -normal side is clear",
        measured_segments=[
            MeasuredSegment("D1", (100.0, 200.0), (200.0, 200.0)),
        ],
        geometry_segments=[
            ((100.0, 200.0), (200.0, 200.0)),
            # Obstacle pocket on +y side
            ((120.0, 205.0), (180.0, 205.0)),
            ((180.0, 205.0), (180.0, 230.0)),
            ((180.0, 230.0), (120.0, 230.0)),
            ((120.0, 230.0), (120.0, 205.0)),
        ],
        annotation_obstacles=[],
    ))

    # Fixture 7: One side blocked by text/annotation obstacle
    # Notes block sitting at x in [130..170], y in [205..220]
    scenes.append(Scene(
        name="fixture_7_one_side_blocked_by_annotation",
        description="Measured edge with drawing note box on default +normal side",
        measured_segments=[
            MeasuredSegment("D1", (100.0, 200.0), (200.0, 200.0)),
        ],
        geometry_segments=[
            ((100.0, 200.0), (200.0, 200.0)),
        ],
        annotation_obstacles=[
            AnnotationObstacle("NOTE_1", (130.0, 205.0, 170.0, 220.0)),
        ],
    ))

    # Fixture 8: Crowded short measured segments
    scenes.append(Scene(
        name="fixture_8_crowded_short_segments",
        description="Two short 10 mm segments with neighboring cross-ribs",
        measured_segments=[
            MeasuredSegment("D1", (100.0, 100.0), (112.0, 100.0)),
            MeasuredSegment("D2", (112.0, 100.0), (124.0, 100.0)),
        ],
        geometry_segments=[
            ((100.0, 100.0), (124.0, 100.0)),
            ((112.0, 100.0), (112.0, 115.0)),  # Vertical rib dividing them
        ],
        annotation_obstacles=[],
    ))

    # Fixture 9: Dimension close to sheet/view boundary
    # Measured line at y=495, length 100. Sheet boundary is ymax=500.
    # Default +normal (offset 8 mm) puts base at y=503, text reaches y=504.75 (OUT OF BOUNDS!).
    scenes.append(Scene(
        name="fixture_9_close_to_sheet_boundary",
        description="Measured edge close to top sheet border where +normal escapes drawing boundary",
        measured_segments=[
            MeasuredSegment("D1", (150.0, 495.0), (250.0, 495.0)),
        ],
        geometry_segments=[
            ((150.0, 495.0), (250.0, 495.0)),
        ],
        annotation_obstacles=[],
        sheet_boundary=(0.0, 0.0, 500.0, 500.0),
    ))

    # Fixture 10: Mixed orientations in local region (perpendicular crossing hazards)
    scenes.append(Scene(
        name="fixture_10_mixed_orientations_local",
        description="L-bracket corner with horizontal and vertical dimensions meeting at (100, 100)",
        measured_segments=[
            MeasuredSegment("D_HORIZ", (100.0, 100.0), (200.0, 100.0)),
            MeasuredSegment("D_VERT", (100.0, 100.0), (100.0, 180.0)),
        ],
        geometry_segments=[
            ((100.0, 100.0), (200.0, 100.0)),
            ((100.0, 100.0), (100.0, 180.0)),
            ((200.0, 100.0), (200.0, 130.0)),
            ((200.0, 130.0), (130.0, 130.0)),
            ((130.0, 130.0), (130.0, 180.0)),
            ((130.0, 180.0), (100.0, 180.0)),
        ],
        annotation_obstacles=[],
    ))

    return scenes


# ---------------------------------------------------------------------------
# Benchmark Runner
# ---------------------------------------------------------------------------

def dimensions_match(p1: PlacedDimension, p2: PlacedDimension, tol: float = 1e-9) -> bool:
    """Verify full-field repeatability across all PlacedDimension fields (MF-03)."""
    if p1.spec_id != p2.spec_id or p1.side != p2.side or p1.lane_index != p2.lane_index:
        return False
    if abs(p1.offset - p2.offset) > tol or abs(p1.measured_length - p2.measured_length) > tol or abs(p1.dimension_length - p2.dimension_length) > tol:
        return False
    for pt1, pt2 in [
        (p1.base, p2.base),
        (p1.dim_line_start, p2.dim_line_start),
        (p1.dim_line_end, p2.dim_line_end),
        (p1.ext_line_1_start, p2.ext_line_1_start),
        (p1.ext_line_1_end, p2.ext_line_1_end),
        (p1.ext_line_2_start, p2.ext_line_2_start),
        (p1.ext_line_2_end, p2.ext_line_2_end),
    ]:
        if abs(pt1[0] - pt2[0]) > tol or abs(pt1[1] - pt2[1]) > tol:
            return False
    for b1, b2 in zip(p1.text_bbox, p2.text_bbox):
        if abs(b1 - b2) > tol:
            return False
    for pt1, pt2 in zip(p1.text_corners, p2.text_corners):
        if abs(pt1[0] - pt2[0]) > tol or abs(pt1[1] - pt2[1]) > tol:
            return False
    return True


def run_benchmark() -> Tuple[List[PlacementEvaluation], Dict[str, Any]]:
    scenes = create_fixtures()
    evaluations: List[PlacementEvaluation] = []

    summary_stats = {
        "total_fixtures": len(scenes),
        "baseline_total_collisions": 0,
        "candidate_total_collisions": 0,
        "baseline_unresolved_scenes": 0,
        "candidate_unresolved_scenes": 0,
        "prototype_measurement_error": 0.0,
        "production_native_measurement_preservation": "NOT_VERIFIED_BY_THIS_ORACLE",
        "placement_displacement": "NOT_MEASURED",
        "measured_repeatability_tested_fixtures_pct": 0.0,
        "repeatability_scope": "",
    }

    max_proto_err = 0.0
    total_dims = 0
    repeat_matches = 0

    for sc in scenes:
        # Run Baseline
        base_placed = place_dimensions_baseline(sc)
        base_eval = evaluate_placement_scene(sc, base_placed, "Baseline_Fixed_Offset")
        evaluations.append(base_eval)
        summary_stats["baseline_total_collisions"] += base_eval.collision_count
        if base_eval.unresolved_dimensions > 0:
            summary_stats["baseline_unresolved_scenes"] += 1

        # Run Candidate (Run 1)
        cand_placed = place_dimensions_candidate(sc)
        cand_eval = evaluate_placement_scene(sc, cand_placed, "Candidate_Deterministic_MultiLane")
        evaluations.append(cand_eval)
        summary_stats["candidate_total_collisions"] += cand_eval.collision_count
        if cand_eval.unresolved_dimensions > 0:
            summary_stats["candidate_unresolved_scenes"] += 1

        for p in cand_placed:
            err = abs(p.dimension_length - p.measured_length)
            if err > max_proto_err:
                max_proto_err = err

        # Run Candidate (Run 2 - measured full-field repeatability check)
        cand_placed_run2 = place_dimensions_candidate(sc)
        assert len(cand_placed) == len(cand_placed_run2), f"Dimension count mismatch on {sc.name}"
        for p1, p2 in zip(cand_placed, cand_placed_run2):
            total_dims += 1
            if dimensions_match(p1, p2):
                repeat_matches += 1

    summary_stats["prototype_measurement_error"] = max_proto_err
    repeatability_pct = (repeat_matches / total_dims * 100.0) if total_dims > 0 else 0.0
    summary_stats["measured_repeatability_tested_fixtures_pct"] = repeatability_pct
    summary_stats["repeatability_scope"] = (
        f"{repeat_matches}/{total_dims} dimensions full-field equal within 1e-9 across 2 repeated runs on all "
        f"{len(scenes)} tested synthetic fixtures (Fixture 4 tested across 3 runs in oracle)"
    )

    return evaluations, summary_stats


def main():
    print("Executing REA-023 Native Dimension Placement Collision Avoidance Benchmark...")
    evaluations, summary = run_benchmark()

    out_dir = Path("research/antigravity/2026-10-14/native_dimension_placement_collision_avoidance")
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "benchmark_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "evaluations": [asdict(e) for e in evaluations]
        }, f, indent=2)

    print(f"Benchmark complete! Evaluations saved to: {json_path}")
    print(f"Baseline Collisions: {summary['baseline_total_collisions']} across {summary['baseline_unresolved_scenes']} failed scenes")
    print(f"Candidate Collisions: {summary['candidate_total_collisions']} across {summary['candidate_unresolved_scenes']} failed scenes")
    print(f"Prototype Measurement Error: {summary['prototype_measurement_error']}")
    print(f"Native Measurement Preservation: {summary['production_native_measurement_preservation']}")
    print(f"Repeatability on Tested Fixtures: {summary['measured_repeatability_tested_fixtures_pct']}% ({summary['repeatability_scope']})")


if __name__ == "__main__":
    main()
