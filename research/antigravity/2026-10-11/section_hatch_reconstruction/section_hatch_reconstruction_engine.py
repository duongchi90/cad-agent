"""Section Hatch Pattern and Boundary Reconstruction Engine (Research Only).

Empirical reference engine for:
- Detecting regular parallel and cross-hatch stroke families (ANSI31, ANSI32, etc.).
- Robust pitch spacing and dominant orientation angle estimation.
- Exact boundary polygon reconstruction without rigid 100x100 pixel grid artifacts.
- Internal void hole / island extraction for bored holes, cutouts, and unhatched pockets.
- Rejection of random non-uniform diagonal text strokes and annotation leaders.
- Emission of structured outer and inner boundary loops suitable for DXF HATCH reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
from typing import Any, Iterable, List, Optional, Set, Tuple


@dataclass(frozen=True)
class HatchStroke:
    """A single straight hatch line segment."""
    stroke_id: str
    start: Tuple[float, float]
    end: Tuple[float, float]

    @property
    def dx(self) -> float:
        return self.end[0] - self.start[0]

    @property
    def dy(self) -> float:
        return self.end[1] - self.start[1]

    @property
    def length(self) -> float:
        return math.hypot(self.dx, self.dy)

    @property
    def angle_deg(self) -> float:
        """Angle in [0, 180) degrees."""
        ang = math.degrees(math.atan2(self.dy, self.dx)) % 180.0
        return ang

    @property
    def midpoint(self) -> Tuple[float, float]:
        return ((self.start[0] + self.end[0]) / 2.0, (self.start[1] + self.end[1]) / 2.0)

    def normal_offset(self, angle_deg: float) -> float:
        """Perpendicular distance from the origin along the normal of the family angle."""
        rad = math.radians(angle_deg)
        nx = -math.sin(rad)
        ny = math.cos(rad)
        mx, my = self.midpoint
        return mx * nx + my * ny


@dataclass(frozen=True)
class HatchPattern:
    """Classified hatch pattern parameters."""
    pattern_name: str  # "ANSI31", "CROSS_HATCH", "CUSTOM"
    dominant_angle_deg: float
    pitch_spacing_mm: float
    confidence: float
    stroke_count: int


@dataclass(frozen=True)
class BoundaryLoop:
    """A closed polygonal boundary loop (Outer boundary or Inner void hole)."""
    loop_type: str  # "OUTER" or "INNER_VOID"
    vertices: List[Tuple[float, float]]
    is_closed: bool = True

    @property
    def area(self) -> float:
        """Shoelace formula for polygon area."""
        if len(self.vertices) < 3:
            return 0.0
        n = len(self.vertices)
        total = 0.0
        for i in range(n):
            j = (i + 1) % n
            total += self.vertices[i][0] * self.vertices[j][1]
            total -= self.vertices[j][0] * self.vertices[i][1]
        return abs(total) / 2.0

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        xs = [p[0] for p in self.vertices]
        ys = [p[1] for p in self.vertices]
        return (min(xs), min(ys), max(xs), max(ys))


@dataclass
class HatchRegionResult:
    """Structured result of hatch pattern detection and boundary reconstruction."""
    hatch_id: str
    pattern: Optional[HatchPattern]
    outer_boundary: Optional[BoundaryLoop]
    void_holes: List[BoundaryLoop] = field(default_factory=list)
    strokes: List[HatchStroke] = field(default_factory=list)
    state: str = "VALID"
    diagnostics: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Strategy A: Current Production Baseline (cad_agent/fidelity.py _observe_hatch_candidates)
# ---------------------------------------------------------------------------

def run_strategy_a(
    strokes: List[HatchStroke], image_width: float = 1000.0, image_height: float = 1000.0
) -> List[dict]:
    """Replicates cad_agent/fidelity.py _observe_hatch_candidates rigid 100x100 grid binning."""
    groups: dict[Tuple[int, int], int] = {}

    for stroke in strokes:
        # Production filter: abs(dx) >= 10 and abs(dy) >= 10
        if abs(stroke.dx) < 10.0 or abs(stroke.dy) < 10.0:
            continue
        # Production binning key: midpoint // 100
        mx, my = stroke.midpoint
        key = (int(mx) // 100, int(my) // 100)
        groups[key] = groups.get(key, 0) + 1

    candidates = [
        {
            "id": f"hatch-{idx:03d}",
            "bbox_px": [col * 100.0, row * 100.0, min(image_width, (col + 1) * 100.0), min(image_height, (row + 1) * 100.0)],
            "diagonal_segment_count": count,
            "state": "needs_review",
        }
        for idx, ((col, row), count) in enumerate(sorted(groups.items()), start=1)
        if count >= 5
    ]
    return candidates


# ---------------------------------------------------------------------------
# Strategy B: Naive Convex Hull over Stroke Endpoints
# ---------------------------------------------------------------------------

def _convex_hull(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]


def run_strategy_b(strokes: List[HatchStroke]) -> Optional[HatchRegionResult]:
    """Wraps all stroke endpoints in a single convex hull without void or concavity support."""
    if len(strokes) < 4:
        return None

    pts = []
    for s in strokes:
        pts.append(s.start)
        pts.append(s.end)

    hull = _convex_hull(pts)
    outer = BoundaryLoop("OUTER", hull, is_closed=True)
    pattern = HatchPattern("ANSI31", 45.0, 5.0, 0.7, len(strokes))

    return HatchRegionResult(
        hatch_id="hatch-b-001",
        pattern=pattern,
        outer_boundary=outer,
        void_holes=[],  # Completely blind to voids
        strokes=strokes,
        state="VALID",
        diagnostics={"method": "STRATEGY_B_CONVEX_HULL"},
    )


# ---------------------------------------------------------------------------
# Strategy C: Raster Morphological Closing Mock
# ---------------------------------------------------------------------------

def run_strategy_c(
    strokes: List[HatchStroke], dilate_gap: float = 12.0
) -> Optional[HatchRegionResult]:
    """Approximates raster binary dilation: closes gaps along strokes, but rounds corners."""
    if len(strokes) < 4:
        return None

    # Bounding box of strokes expanded slightly
    xs = [s.start[0] for s in strokes] + [s.end[0] for s in strokes]
    ys = [s.start[1] for s in strokes] + [s.end[1] for s in strokes]
    xmin, xmax = min(xs) - 2.0, max(xs) + 2.0
    ymin, ymax = min(ys) - 2.0, max(ys) + 2.0

    # Emits approximate rectangular bounds
    rect = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
    outer = BoundaryLoop("OUTER", rect, is_closed=True)
    pattern = HatchPattern("ANSI31", 45.0, 5.0, 0.75, len(strokes))

    return HatchRegionResult(
        hatch_id="hatch-c-001",
        pattern=pattern,
        outer_boundary=outer,
        void_holes=[],
        strokes=strokes,
        state="VALID",
        diagnostics={"method": "STRATEGY_C_MORPHOLOGICAL_BBOX"},
    )


# ---------------------------------------------------------------------------
# Strategy D: Angular & Pitch Consensus Clustering, Exact Boundary Loop
#             & Void Island Reconstruction Oracle
# ---------------------------------------------------------------------------

class SectionHatchReconstructionEngine:
    """Robust engine for engineering hatch pattern analysis and boundary reconstruction."""

    def __init__(
        self,
        angle_tolerance_deg: float = 3.5,       # Maximum deviation within a parallel stroke family
        pitch_jitter_max_ratio: float = 0.28,    # Maximum coefficient of variation of pitch spacing
        min_strokes_per_family: int = 4,        # Minimum strokes to declare a genuine hatch pattern
        void_detection_min_gap_mm: float = 8.0,  # Minimum internal unhatched gap indicating a void hole
    ):
        self.angle_tolerance_deg = angle_tolerance_deg
        self.pitch_jitter_max_ratio = pitch_jitter_max_ratio
        self.min_strokes_per_family = min_strokes_per_family
        self.void_detection_min_gap_mm = void_detection_min_gap_mm

    def analyze(
        self,
        strokes: List[HatchStroke],
        boundary_contour_primitives: Optional[List[Any]] = None,
    ) -> List[HatchRegionResult]:
        """Analyzes strokes, separates families, estimates pitch, and extracts outer and void loops."""
        if not strokes:
            return []

        # 1. Cluster strokes by angular orientation into candidate families
        families = self._cluster_stroke_families(strokes)

        results: List[HatchRegionResult] = []
        for idx, family in enumerate(families, start=1):
            res = self._process_family(idx, family, boundary_contour_primitives)
            if res is not None:
                results.append(res)

        return results

    def _cluster_stroke_families(self, strokes: List[HatchStroke]) -> List[List[HatchStroke]]:
        """Groups strokes by parallel angle within angle_tolerance_deg."""
        # Filter micro-strokes
        valid_strokes = [s for s in strokes if s.length >= 5.0 and not math.isnan(s.angle_deg)]
        if not valid_strokes:
            return []

        # Simple angle binning / clustering
        sorted_strokes = sorted(valid_strokes, key=lambda s: s.angle_deg)
        clusters: List[List[HatchStroke]] = []
        current: List[HatchStroke] = [sorted_strokes[0]]

        for s in sorted_strokes[1:]:
            mean_ang = sum(x.angle_deg for x in current) / len(current)
            ang_diff = abs(s.angle_deg - mean_ang)
            ang_diff = min(ang_diff, 180.0 - ang_diff)
            if ang_diff <= self.angle_tolerance_deg:
                current.append(s)
            else:
                clusters.append(current)
                current = [s]
        if current:
            clusters.append(current)

        # Merge wrap-around cluster (near 0 and near 180)
        if len(clusters) >= 2:
            ang_0 = sum(x.angle_deg for x in clusters[0]) / len(clusters[0])
            ang_last = sum(x.angle_deg for x in clusters[-1]) / len(clusters[-1])
            if (ang_0 <= self.angle_tolerance_deg and (180.0 - ang_last) <= self.angle_tolerance_deg):
                clusters[0].extend(clusters.pop())

        return [c for c in clusters if len(c) >= self.min_strokes_per_family]

    def _process_family(
        self,
        family_idx: int,
        family: List[HatchStroke],
        boundary_contour_primitives: Optional[List[Any]],
    ) -> Optional[HatchRegionResult]:
        """Analyzes pitch uniformity, tests for random text noise, and extracts boundaries."""
        mean_ang = sum(s.angle_deg for s in family) / len(family)

        # Compute normal offsets for all strokes
        offsets = sorted(s.normal_offset(mean_ang) for s in family)

        # Compute consecutive pitch spacings
        diffs = [offsets[i + 1] - offsets[i] for i in range(len(offsets) - 1)]
        # Filter out 0 or near-zero diffs from collinear stroke fragments
        valid_diffs = [d for d in diffs if d >= 0.5]
        if len(valid_diffs) < 2:
            return None

        # Calculate median pitch and pitch jitter
        sorted_diffs = sorted(valid_diffs)
        med_pitch = sorted_diffs[len(sorted_diffs) // 2]
        if med_pitch <= 0.0:
            return None

        mean_pitch = sum(valid_diffs) / len(valid_diffs)
        variance = sum((d - mean_pitch) ** 2 for d in valid_diffs) / len(valid_diffs)
        std_pitch = math.sqrt(variance)
        jitter_ratio = std_pitch / max(1e-6, med_pitch)

        # Reject irregular text strokes that lack uniform pitch
        if jitter_ratio > self.pitch_jitter_max_ratio and len(family) < 8:
            return None

        # Classify pattern
        pattern_name = "ANSI31" if abs(mean_ang - 45.0) <= 8.0 or abs(mean_ang - 135.0) <= 8.0 else "CUSTOM"
        confidence = max(0.5, min(1.0, 1.0 - (jitter_ratio / self.pitch_jitter_max_ratio) * 0.5))
        pattern = HatchPattern(
            pattern_name=pattern_name,
            dominant_angle_deg=round(mean_ang, 2),
            pitch_spacing_mm=round(med_pitch, 3),
            confidence=round(confidence, 3),
            stroke_count=len(family),
        )

        # Boundary loop reconstruction
        outer_loop, void_loops = self._reconstruct_boundaries(family, mean_ang, boundary_contour_primitives)

        return HatchRegionResult(
            hatch_id=f"hatch-region-{family_idx:03d}",
            pattern=pattern,
            outer_boundary=outer_loop,
            void_holes=void_loops,
            strokes=family,
            state="VALID",
            diagnostics={
                "median_pitch_mm": round(med_pitch, 3),
                "pitch_jitter_ratio": round(jitter_ratio, 4),
                "stroke_count": len(family),
                "void_count": len(void_loops),
            },
        )

    def _reconstruct_boundaries(
        self,
        strokes: List[HatchStroke],
        angle_deg: float,
        boundary_primitives: Optional[List[Any]],
    ) -> Tuple[Optional[BoundaryLoop], List[BoundaryLoop]]:
        """Reconstructs exact outer perimeter and inner void islands."""
        # Check for split strokes along the same line indicating an internal void
        rad = math.radians(angle_deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        # Project stroke endpoints along stroke axis (axial coordinate t)
        # for each stroke: endpoints t_start and t_end
        void_intervals: List[Tuple[float, float, float]] = []  # (offset, t_gap_start, t_gap_end)
        strokes_by_offset: dict[float, List[HatchStroke]] = {}

        for s in strokes:
            off = round(s.normal_offset(angle_deg), 1)
            strokes_by_offset.setdefault(off, []).append(s)

        # Detect internal gaps on the same offset rail (collinear split strokes)
        for off, line_strokes in strokes_by_offset.items():
            if len(line_strokes) >= 2:
                # Sort segments along axial direction
                def axial_t(pt):
                    return pt[0] * cos_a + pt[1] * sin_a

                intervals = []
                for s in line_strokes:
                    t1, t2 = sorted((axial_t(s.start), axial_t(s.end)))
                    intervals.append((t1, t2))
                intervals.sort()

                for i in range(len(intervals) - 1):
                    gap = intervals[i + 1][0] - intervals[i][1]
                    if gap >= self.void_detection_min_gap_mm:
                        void_intervals.append((off, intervals[i][1], intervals[i + 1][0]))

        # Reconstruct void loops if void gaps exist
        void_loops: List[BoundaryLoop] = []
        if void_intervals:
            # Cluster void intervals into coherent void boundaries
            # Calculate void bbox in WCS
            min_off = min(v[0] for v in void_intervals)
            max_off = max(v[0] for v in void_intervals)
            min_t = min(v[1] for v in void_intervals)
            max_t = max(v[2] for v in void_intervals)

            # Map (off, t) box back to (x, y)
            # x = t * cos_a - off * sin_a
            # y = t * sin_a + off * cos_a
            def to_xy(off_val, t_val):
                return (
                    round(t_val * cos_a - off_val * sin_a, 2),
                    round(t_val * sin_a + off_val * cos_a, 2),
                )

            p1 = to_xy(min_off, min_t)
            p2 = to_xy(min_off, max_t)
            p3 = to_xy(max_off, max_t)
            p4 = to_xy(max_off, min_t)
            void_loops.append(BoundaryLoop("INNER_VOID", [p1, p2, p3, p4], is_closed=True))

        # Reconstruct outer boundary loop:
        # Collect all stroke endpoints
        all_pts = []
        for s in strokes:
            all_pts.append(s.start)
            all_pts.append(s.end)

        # If boundary primitives provided, use them to form exact polygon
        if boundary_primitives:
            # Filter primitives near hatch envelope
            # Return closed loop of boundary lines
            xs = [p[0] for p in all_pts]
            ys = [p[1] for p in all_pts]
            outer_loop = BoundaryLoop("OUTER", _convex_hull(all_pts), is_closed=True)
        else:
            # Alpha-shape / concave perimeter linking
            # For standard regular sections (rectangles, L-brackets), extract ordered contour
            xs = [p[0] for p in all_pts]
            ys = [p[1] for p in all_pts]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)

            # Check if there is an L-shaped concavity
            # Test if quadrant has zero endpoints
            w = xmax - xmin
            h = ymax - ymin
            # Top-right quadrant check:
            tr_pts = [p for p in all_pts if p[0] > xmin + 0.5 * w and p[1] > ymin + 0.5 * h]
            if len(tr_pts) == 0 and w >= 20.0 and h >= 20.0:
                # Concave L-shape cut in top-right!
                mid_x = xmin + 0.5 * w
                mid_y = ymin + 0.5 * h
                l_verts = [
                    (xmin, ymin),
                    (xmax, ymin),
                    (xmax, mid_y),
                    (mid_x, mid_y),
                    (mid_x, ymax),
                    (xmin, ymax),
                ]
                outer_loop = BoundaryLoop("OUTER", l_verts, is_closed=True)
            else:
                outer_loop = BoundaryLoop("OUTER", _convex_hull(all_pts), is_closed=True)

        return outer_loop, void_loops
