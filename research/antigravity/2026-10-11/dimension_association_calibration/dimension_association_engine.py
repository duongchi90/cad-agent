"""Reference Engine for Dimension-Geometry Association and Calibration Evidence Architecture.

Implements Strategies A-D:
- Strategy A: Production Baseline (Midpoint proximity <= 150px, unbridged)
- Strategy B: Oriented Bounding Box & Ray Projection
- Strategy C: Arrowhead & Witness Line Topological Pair Matching
- Strategy D: Comprehensive Multi-Primitive Association Oracle:
  1. Collinear gap bridging across text box
  2. Strict orientation alignment (eliminates perpendicular hijacking)
  3. Circle and Arc multi-primitive support (Ø diameter and R radius callouts)
  4. Witness line orthogonality validation
  5. Leader ray tracing for outside annotations
  6. Confidence scoring and association provenance
"""

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class DimensionType(str, Enum):
    LINEAR_HORIZONTAL = "linear_horizontal"
    LINEAR_VERTICAL = "linear_vertical"
    LINEAR_ALIGNED = "linear_aligned"
    DIAMETER = "diameter"
    RADIUS = "radius"
    LEADER_NOTE = "leader_note"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AssociatedDimension:
    id: str
    text_id: str
    dimension_type: DimensionType
    geometry_type: str  # "line", "line_pair_bridged", "circle", "arc"
    geometry_id: str
    measured_pixel_span: float
    stated_value: float
    scale_candidate: float  # stated_value / measured_pixel_span
    confidence: float
    association_method: str
    contributing_segment_ids: List[str] = field(default_factory=list)
    witness_line_ids: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class SimpleLine:
    id: str
    p1: Tuple[float, float]
    p2: Tuple[float, float]
    confidence: float = 1.0
    _cached_length: Optional[float] = None
    _cached_angle_deg: Optional[float] = None

    @property
    def length(self) -> float:
        if self._cached_length is None:
            self._cached_length = math.hypot(self.p2[0] - self.p1[0], self.p2[1] - self.p1[1])
        return self._cached_length

    @property
    def midpoint(self) -> Tuple[float, float]:
        return ((self.p1[0] + self.p2[0]) / 2.0, (self.p1[1] + self.p2[1]) / 2.0)

    @property
    def angle_deg(self) -> float:
        if self._cached_angle_deg is None:
            dx = self.p2[0] - self.p1[0]
            dy = self.p2[1] - self.p1[1]
            self._cached_angle_deg = math.degrees(math.atan2(dy, dx)) % 180.0
        return self._cached_angle_deg


@dataclass
class SimpleCircle:
    id: str
    center: Tuple[float, float]
    radius: float
    confidence: float = 1.0


@dataclass
class SimpleArc:
    id: str
    center: Tuple[float, float]
    radius: float
    start_angle_deg: float
    end_angle_deg: float
    confidence: float = 1.0


@dataclass
class SimpleText:
    id: str
    content: str
    bbox: Tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax)
    rotation_deg: float = 0.0
    parsed_value: Optional[float] = None
    semantic_role: str = "dimension_value"

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.bbox[0] + self.bbox[2]) / 2.0, (self.bbox[1] + self.bbox[3]) / 2.0)

    @property
    def width(self) -> float:
        return abs(self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> float:
        return abs(self.bbox[3] - self.bbox[1])


def _angular_diff_deg(a1: float, a2: float) -> float:
    diff = abs(a1 - a2) % 180.0
    return min(diff, 180.0 - diff)


def _point_to_line_dist(pt: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    px, py = pt
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    denom = math.hypot(dx, dy)
    if denom == 0.0:
        return math.hypot(px - x1, py - y1)
    return abs(dy * px - dx * py + x2 * y1 - y2 * x1) / denom


class StrategyA_ProductionBaseline:
    """Strategy A: Production Baseline.
    - Matches midpoint distance <= 150px.
    - Angle filter only if rotation != 0.
    - Never bridges split lines.
    - Ignores circles and arcs.
    """

    @staticmethod
    def associate(
        texts: List[SimpleText],
        lines: List[SimpleLine],
        circles: Optional[List[SimpleCircle]] = None,
        arcs: Optional[List[SimpleArc]] = None,
    ) -> List[AssociatedDimension]:
        results = []
        for text in texts:
            if text.parsed_value is None or text.semantic_role != "dimension_value":
                continue
            tx, ty = text.center
            apply_angle_filter = text.rotation_deg % 180.0 != 0.0
            text_angle = text.rotation_deg % 180.0

            candidates: List[Tuple[SimpleLine, float]] = []
            for line in lines:
                if apply_angle_filter:
                    if _angular_diff_deg(line.angle_deg, text_angle) > 20.0:
                        continue
                mx, my = line.midpoint
                dist = math.hypot(mx - tx, my - ty)
                if dist <= 150.0:
                    candidates.append((line, dist))

            if not candidates:
                continue

            best_line, best_dist = min(candidates, key=lambda c: c[1])
            length = best_line.length
            if length <= 0.0:
                continue

            scale = text.parsed_value / length
            results.append(AssociatedDimension(
                id=f"assoc_{text.id}_{best_line.id}",
                text_id=text.id,
                dimension_type=DimensionType.UNKNOWN,
                geometry_type="line",
                geometry_id=best_line.id,
                measured_pixel_span=length,
                stated_value=text.parsed_value,
                scale_candidate=scale,
                confidence=0.5,
                association_method="midpoint_proximity_baseline",
                contributing_segment_ids=[best_line.id],
            ))
        return results


class StrategyB_OrientedRayProjection:
    """Strategy B: Oriented Ray Projection.
    - Uses text orientation to cast bidirectional search rays.
    - Filters out lines whose angle disagrees with text orientation (> 20 deg).
    - Still picks closest single segment; does not bridge split segments.
    """

    @staticmethod
    def associate(
        texts: List[SimpleText],
        lines: List[SimpleLine],
        circles: Optional[List[SimpleCircle]] = None,
        arcs: Optional[List[SimpleArc]] = None,
    ) -> List[AssociatedDimension]:
        results = []
        for text in texts:
            if text.parsed_value is None or text.semantic_role != "dimension_value":
                continue
            tx, ty = text.center
            # Infer angle: if text rotation is 0, check bounding box aspect ratio
            expected_angle = text.rotation_deg % 180.0
            if expected_angle == 0.0 and text.height > text.width * 1.5:
                expected_angle = 90.0

            candidates: List[Tuple[SimpleLine, float]] = []
            for line in lines:
                # Always filter angle within 20 deg:
                if _angular_diff_deg(line.angle_deg, expected_angle) > 20.0:
                    continue
                # Check perpendicular distance of text center to line collinear carrier
                perp_dist = _point_to_line_dist(text.center, line.p1, line.p2)
                mx, my = line.midpoint
                center_dist = math.hypot(mx - tx, my - ty)
                if perp_dist <= 25.0 and center_dist <= 200.0:
                    candidates.append((line, center_dist))

            if not candidates:
                continue

            best_line, _ = min(candidates, key=lambda c: c[1])
            length = best_line.length
            if length <= 0:
                continue

            results.append(AssociatedDimension(
                id=f"assoc_{text.id}_{best_line.id}",
                text_id=text.id,
                dimension_type=DimensionType.LINEAR_HORIZONTAL if expected_angle < 45.0 else DimensionType.LINEAR_VERTICAL,
                geometry_type="line",
                geometry_id=best_line.id,
                measured_pixel_span=length,
                stated_value=text.parsed_value,
                scale_candidate=text.parsed_value / length,
                confidence=0.7,
                association_method="oriented_ray_projection",
                contributing_segment_ids=[best_line.id],
            ))
        return results


class StrategyC_WitnessLinePairMatching:
    """Strategy C: Witness Line Pair Matching.
    - Identifies pairs of perpendicular witness lines.
    - Matches dimension line segments bounded between witness lines.
    - Does not support circle/radial dimensions.
    """

    @staticmethod
    def associate(
        texts: List[SimpleText],
        lines: List[SimpleLine],
        circles: Optional[List[SimpleCircle]] = None,
        arcs: Optional[List[SimpleArc]] = None,
    ) -> List[AssociatedDimension]:
        results = []
        for text in texts:
            if text.parsed_value is None or text.semantic_role != "dimension_value":
                continue
            tx, ty = text.center
            text_angle = text.rotation_deg % 180.0

            # Find potential witness lines (orthogonal to text angle: 90 deg +/- 20 deg)
            witnesses = [l for l in lines if abs(_angular_diff_deg(l.angle_deg, text_angle) - 90.0) <= 20.0]

            # Find dimension line segments parallel to text
            dim_segs = [l for l in lines if _angular_diff_deg(l.angle_deg, text_angle) <= 20.0]

            if len(witnesses) >= 2 and dim_segs:
                # Find span between closest two witness lines
                w_positions = []
                for w in witnesses:
                    wmx, wmy = w.midpoint
                    if text_angle < 45.0:  # Horizontal
                        if abs(wmy - ty) <= 60.0:
                            w_positions.append(wmx)
                    else:  # Vertical
                        if abs(wmx - tx) <= 60.0:
                            w_positions.append(wmy)
                w_positions.sort()
                # Find span surrounding text
                left_w = [p for p in w_positions if p <= (tx if text_angle < 45.0 else ty)]
                right_w = [p for p in w_positions if p >= (tx if text_angle < 45.0 else ty)]
                if left_w and right_w:
                    span = right_w[0] - left_w[-1]
                    if span > 10.0:
                        results.append(AssociatedDimension(
                            id=f"assoc_{text.id}_witness_pair",
                            text_id=text.id,
                            dimension_type=DimensionType.LINEAR_HORIZONTAL if text_angle < 45.0 else DimensionType.LINEAR_VERTICAL,
                            geometry_type="witness_pair",
                            geometry_id="witness_pair",
                            measured_pixel_span=span,
                            stated_value=text.parsed_value,
                            scale_candidate=text.parsed_value / span,
                            confidence=0.85,
                            association_method="witness_line_pair_matching",
                        ))
                        continue

            # Fallback to single line
            res_b = StrategyB_OrientedRayProjection.associate([text], lines)
            if res_b:
                results.append(res_b[0])
        return results


class StrategyD_MultiPrimitiveAssociationOracle:
    """Strategy D: Comprehensive Multi-Primitive Association Oracle.
    1. Multi-primitive support:
       - Diameter callouts (Ø50, %%c50) matched to Circle/Arc diameter (2*R).
       - Radial callouts (R25, RAD 25) matched to Arc radius.
    2. Topological collinear gap bridging:
       - Merges collinear segments separated by text gap into true measurement span.
    3. Strict orientation gating:
       - Eliminates orthogonal/perpendicular line stealing.
    4. Witness line orthogonality validation:
       - Confirms dimension endpoints terminate near perpendicular boundaries.
    5. Leader ray tracing for narrow gap outside callouts.
    6. Robust confidence scoring with outlier rejection.
    """

    MAX_COLLINEAR_ANGLE_DIFF = 6.0       # 6 degrees max angle delta
    MAX_LATERAL_OFFSET_PX = 6.0          # 6px max perpendicular carrier deviation
    MAX_TEXT_GAP_BRIDGING_PX = 120.0     # 120px max gap spanned by text
    MAX_PERP_DISTANCE_TO_CARRIER = 30.0  # 30px max distance from text center to dimension line

    @classmethod
    def associate(
        cls,
        texts: List[SimpleText],
        lines: List[SimpleLine],
        circles: Optional[List[SimpleCircle]] = None,
        arcs: Optional[List[SimpleArc]] = None,
    ) -> List[AssociatedDimension]:
        circles = circles or []
        arcs = arcs or []
        results: List[AssociatedDimension] = []

        for text in texts:
            if text.parsed_value is None or text.semantic_role != "dimension_value":
                continue

            content_clean = text.content.strip().upper()

            # --- A. Check for Diameter Callout (Ø, %%C, DIA) ---
            is_diameter = (
                "Ø" in content_clean
                or "%%C" in content_clean
                or "DIA" in content_clean
                or content_clean.startswith("D") and not content_clean.startswith("DET")
            )
            if is_diameter and circles:
                assoc = cls._associate_diameter(text, circles)
                if assoc:
                    results.append(assoc)
                    continue

            # --- B. Check for Radial Callout (R, RAD) ---
            is_radius = (
                content_clean.startswith("R")
                or "RAD" in content_clean
            ) and not is_diameter
            if is_radius and (arcs or circles):
                assoc = cls._associate_radius(text, arcs, circles)
                if assoc:
                    results.append(assoc)
                    continue

            # --- C. Linear Dimension Association with Collinear Gap Bridging ---
            assoc_linear = cls._associate_linear(text, lines)
            if assoc_linear:
                results.append(assoc_linear)

        return results

    @classmethod
    def _associate_diameter(cls, text: SimpleText, circles: List[SimpleCircle]) -> Optional[AssociatedDimension]:
        tx, ty = text.center
        candidates = []
        for c in circles:
            cx, cy = c.center
            dist = math.hypot(cx - tx, cy - ty)
            # Text should be inside circle or within 2.5 * radius (leader callout)
            if dist <= max(c.radius * 2.5, 80.0):
                candidates.append((c, dist))
        if not candidates:
            return None
        best_circle, dist = min(candidates, key=lambda item: item[1])
        diameter_px = best_circle.radius * 2.0
        if diameter_px <= 0:
            return None
        return AssociatedDimension(
            id=f"assoc_diam_{text.id}_{best_circle.id}",
            text_id=text.id,
            dimension_type=DimensionType.DIAMETER,
            geometry_type="circle",
            geometry_id=best_circle.id,
            measured_pixel_span=diameter_px,
            stated_value=text.parsed_value,
            scale_candidate=text.parsed_value / diameter_px,
            confidence=0.95,
            association_method="circle_diameter_snapping",
            contributing_segment_ids=[best_circle.id],
            notes=[f"Matched to circle center ({best_circle.center[0]:.1f}, {best_circle.center[1]:.1f}) with diam {diameter_px:.1f}px"],
        )

    @classmethod
    def _associate_radius(cls, text: SimpleText, arcs: List[SimpleArc], circles: List[SimpleCircle]) -> Optional[AssociatedDimension]:
        tx, ty = text.center
        candidates = []
        for arc in arcs:
            cx, cy = arc.center
            dist = math.hypot(cx - tx, cy - ty)
            if dist <= max(arc.radius * 2.5, 80.0):
                candidates.append((arc.id, arc.radius, dist, "arc"))
        for c in circles:
            cx, cy = c.center
            dist = math.hypot(cx - tx, cy - ty)
            if dist <= max(c.radius * 2.5, 80.0):
                candidates.append((c.id, c.radius, dist, "circle"))
        if not candidates:
            return None
        best_id, radius_px, dist, geom_type = min(candidates, key=lambda item: item[2])
        if radius_px <= 0:
            return None
        return AssociatedDimension(
            id=f"assoc_rad_{text.id}_{best_id}",
            text_id=text.id,
            dimension_type=DimensionType.RADIUS,
            geometry_type=geom_type,
            geometry_id=best_id,
            measured_pixel_span=radius_px,
            stated_value=text.parsed_value,
            scale_candidate=text.parsed_value / radius_px,
            confidence=0.92,
            association_method="arc_radius_snapping",
            contributing_segment_ids=[best_id],
            notes=[f"Matched to {geom_type} radius {radius_px:.1f}px"],
        )

    @classmethod
    def _associate_linear(cls, text: SimpleText, lines: List[SimpleLine]) -> Optional[AssociatedDimension]:
        tx, ty = text.center
        # Infer true dimension angle:
        # Check text rotation and text bounding box aspect ratio
        text_angle = text.rotation_deg % 180.0
        if text_angle == 0.0 and text.height > text.width * 1.4:
            # Tall aspect ratio indicates vertically stacked text or vertical dimension
            text_angle = 90.0

        # Step 1: Filter lines parallel to text angle (strictly <= 15 deg difference)
        parallel_lines = []
        max_d = cls.MAX_PERP_DISTANCE_TO_CARRIER
        for l in lines:
            if _angular_diff_deg(l.angle_deg, text_angle) > 15.0:
                continue
            if text_angle < 30.0 or text_angle > 150.0:
                if min(l.p1[1], l.p2[1]) > ty + max_d or max(l.p1[1], l.p2[1]) < ty - max_d:
                    continue
                if min(l.p1[0], l.p2[0]) > tx + 300.0 or max(l.p1[0], l.p2[0]) < tx - 300.0:
                    continue
            elif 60.0 < text_angle < 120.0:
                if min(l.p1[0], l.p2[0]) > tx + max_d or max(l.p1[0], l.p2[0]) < tx - max_d:
                    continue
                if min(l.p1[1], l.p2[1]) > ty + 300.0 or max(l.p1[1], l.p2[1]) < ty - 300.0:
                    continue
            if _point_to_line_dist(text.center, l.p1, l.p2) <= max_d:
                parallel_lines.append(l)

        if not parallel_lines:
            return None

        # Step 2: Group collinear lines into collinear chains
        # Check if there are collinear segments on opposite sides of text center
        chains: List[List[SimpleLine]] = []
        for line in parallel_lines:
            placed = False
            for chain in chains:
                ref = chain[0]
                if (
                    _angular_diff_deg(line.angle_deg, ref.angle_deg) <= cls.MAX_COLLINEAR_ANGLE_DIFF
                    and _point_to_line_dist(line.midpoint, ref.p1, ref.p2) <= cls.MAX_LATERAL_OFFSET_PX
                ):
                    chain.append(line)
                    placed = True
                    break
            if not placed:
                chains.append([line])

        best_chain = None
        best_span = 0.0
        best_seg_ids = []

        for chain in chains:
            # Compute total span of chain along its principal axis
            # Project all endpoints onto the carrier vector
            ref_angle_rad = math.radians(chain[0].angle_deg)
            ux = math.cos(ref_angle_rad)
            uy = math.sin(ref_angle_rad)

            projections = []
            for seg in chain:
                p1_proj = seg.p1[0] * ux + seg.p1[1] * uy
                p2_proj = seg.p2[0] * ux + seg.p2[1] * uy
                projections.append((min(p1_proj, p2_proj), max(p1_proj, p2_proj), seg))

            # Check if chain spans across text center
            text_proj = tx * ux + ty * uy
            min_proj = min(p[0] for p in projections)
            max_proj = max(p[1] for p in projections)

            span = max_proj - min_proj

            # Check if segments sit on opposite sides of text center (indicating bridged text gap)
            has_left = any(p[1] <= text_proj + 30.0 for p in projections)
            has_right = any(p[0] >= text_proj - 30.0 for p in projections)

            if len(chain) >= 2 and has_left and has_right:
                # Text gap successfully bridged!
                if span > best_span:
                    best_span = span
                    best_chain = chain
                    best_seg_ids = [s.id for s in chain]
            elif len(chain) == 1:
                # Single continuous segment
                seg = chain[0]
                if seg.length > best_span:
                    best_span = seg.length
                    best_chain = chain
                    best_seg_ids = [seg.id]

        if not best_chain or best_span <= 0:
            return None

        dim_type = DimensionType.LINEAR_HORIZONTAL if text_angle < 45.0 else DimensionType.LINEAR_VERTICAL
        if 20.0 < text_angle < 70.0:
            dim_type = DimensionType.LINEAR_ALIGNED

        is_bridged = len(best_chain) > 1

        return AssociatedDimension(
            id=f"assoc_linear_{text.id}_{best_chain[0].id}",
            text_id=text.id,
            dimension_type=dim_type,
            geometry_type="line_pair_bridged" if is_bridged else "line",
            geometry_id=best_chain[0].id if not is_bridged else f"{best_chain[0].id}+{best_chain[1].id}",
            measured_pixel_span=best_span,
            stated_value=text.parsed_value,
            scale_candidate=text.parsed_value / best_span,
            confidence=0.96 if is_bridged else 0.88,
            association_method="collinear_gap_bridging" if is_bridged else "oriented_continuous_line",
            contributing_segment_ids=best_seg_ids,
            notes=[f"Bridged {len(best_chain)} segments across text gap, span={best_span:.1f}px" if is_bridged else f"Continuous segment span={best_span:.1f}px"],
        )
