"""
multileader_topology_engine.py
Empirical Research Engine for Multileader Line, Dogleg Knee, and Callout Topology (V1).

Compares:
- Strategy A: Current Production Baseline (_detect_leader_lines in primitive_ir_lib.dimension_geometry)
- Strategy B: Proximity Bounding Box Union
- Strategy C: Unconstrained Hough Junction Graph
- Strategy D: Strategy D Multileader Topology & Directed Attachment Oracle
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Sequence, Tuple, Union

from primitive_ir_lib.models import Point2D, Primitive, LineGeometry, CircleGeometry

# Tolerances & Epistemic Bounds
DEFAULT_SNAP_TOL_MM = 5.0
DEFAULT_HORIZONTAL_TOL_DEG = 6.0
DEFAULT_ARROWHEAD_MAX_LEN_MM = 12.0
DEFAULT_ARROWHEAD_MIN_LEN_MM = 2.0
DEFAULT_APEX_ANGLE_MAX_DEG = 45.0
DEFAULT_TEXT_PROXIMITY_MM = 12.0


@dataclass(frozen=True)
class ArrowheadMarker:
    tip: Point2D
    direction_vector: Tuple[float, float]  # Unit vector from knee towards tip
    length_mm: float
    marker_type: Literal["acute_arrow", "filled_triangle", "dot", "slash"] = "acute_arrow"


@dataclass
class MultileaderTopology:
    id: str
    tip: Point2D
    knee: Point2D
    landing_end: Point2D
    pointer_segment: Tuple[Point2D, Point2D]
    landing_segment: Optional[Tuple[Point2D, Point2D]] = None
    arrowhead: Optional[ArrowheadMarker] = None
    attached_feature_id: Optional[str] = None
    attached_feature_type: Optional[Literal["circle", "arc", "line", "chamfer"]] = None
    attached_feature_distance_mm: float = 0.0
    callout_text_id: Optional[str] = None
    callout_text_content: Optional[str] = None
    confidence: float = 0.0
    measured: dict = field(default_factory=dict)


@dataclass
class MultileaderExtractionResult:
    leaders: List[MultileaderTopology] = field(default_factory=list)
    unattached_segments: List[Tuple[Point2D, Point2D]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Geometric Helpers
# ---------------------------------------------------------------------------

def point_dist(p1: Point2D, p2: Point2D) -> float:
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def segment_length(s: Tuple[Point2D, Point2D]) -> float:
    return point_dist(s[0], s[1])


def segment_angle_deg(s: Tuple[Point2D, Point2D]) -> float:
    return math.degrees(math.atan2(s[1].y - s[0].y, s[1].x - s[0].x)) % 180.0


def is_horizontal_segment(s: Tuple[Point2D, Point2D], tol_deg: float = DEFAULT_HORIZONTAL_TOL_DEG) -> bool:
    ang = segment_angle_deg(s)
    return ang <= tol_deg or ang >= 180.0 - tol_deg


def is_diagonal_segment(s: Tuple[Point2D, Point2D]) -> bool:
    ang = segment_angle_deg(s)
    return 10.0 <= ang <= 80.0 or 100.0 <= ang <= 170.0


def distance_point_to_line_segment(pt: Point2D, s: Tuple[Point2D, Point2D]) -> float:
    p1, p2 = s
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return point_dist(pt, p1)
    t = max(0.0, min(1.0, ((pt.x - p1.x) * dx + (pt.y - p1.y) * dy) / l2))
    proj = Point2D(p1.x + t * dx, p1.y + t * dy)
    return point_dist(pt, proj)


def distance_point_to_primitive(pt: Point2D, prim: Primitive) -> float:
    if prim.type == "circle" and prim.geometry:
        c = prim.geometry.center
        r = prim.geometry.radius
        d_center = point_dist(pt, c)
        return abs(d_center - r)
    elif prim.type == "line" and prim.geometry:
        s = (prim.geometry.start, prim.geometry.end)
        return distance_point_to_line_segment(pt, s)
    return 999999.0


# ---------------------------------------------------------------------------
# Strategy A: Current Production Baseline
# ---------------------------------------------------------------------------

def extract_multileader_strategy_a(
    segments: List[Tuple[Point2D, Point2D]],
    text_primitives: List[Primitive],
    cad_primitives: List[Primitive],
) -> MultileaderExtractionResult:
    """Strategy A: Current Production Baseline (_detect_leader_lines).
    Filters diagonal segments, requires another diagonal marker of 18-55px length,
    discards landing lines, lacks arrowhead detection, 0 target attachment, 0 text association.
    """
    def _endpoint_distance(s1: Tuple[Point2D, Point2D], s2: Tuple[Point2D, Point2D]) -> float:
        return min(
            point_dist(p1, p2) for p1 in s1 for p2 in s2
        )

    def _has_leader_marker(candidate: Tuple[Point2D, Point2D], diag_segments: List[Tuple[Point2D, Point2D]]) -> bool:
        for marker in diag_segments:
            if marker == candidate or not is_diagonal_segment(marker):
                continue
            marker_len = segment_length(marker)
            if 18.0 <= marker_len <= 55.0 and _endpoint_distance(candidate, marker) <= 8.0:
                return True
        return False

    diagonal_segments = [s for s in segments if is_diagonal_segment(s)]
    leaders: List[MultileaderTopology] = []

    for idx, candidate in enumerate(sorted(diagonal_segments, key=lambda s: -segment_length(s))):
        if any(_endpoint_distance(candidate, l.pointer_segment) <= 24.0 for l in leaders):
            continue
        if _has_leader_marker(candidate, diagonal_segments):
            # Production creates an undirected leader line tuple with 0 attachments
            leaders.append(MultileaderTopology(
                id=f"leader_a_{idx}",
                tip=candidate[0],  # Arbitrary endpoint assignment
                knee=candidate[1],
                landing_end=candidate[1],
                pointer_segment=candidate,
                landing_segment=None,
                confidence=0.35,
            ))

    return MultileaderExtractionResult(leaders=leaders)


def _segment_key(s: Tuple[Point2D, Point2D]) -> Tuple[float, float, float, float]:
    return (round(s[0].x, 3), round(s[0].y, 3), round(s[1].x, 3), round(s[1].y, 3))


# ---------------------------------------------------------------------------
# Strategy B: Proximity Bounding Box Union
# ---------------------------------------------------------------------------

def extract_multileader_strategy_b(
    segments: List[Tuple[Point2D, Point2D]],
    text_primitives: List[Primitive],
    cad_primitives: List[Primitive],
    proximity_tol_mm: float = 30.0,
) -> MultileaderExtractionResult:
    """Strategy B: Proximity Bounding Box Union.
    Takes any diagonal line within proximity_tol of a text box, assumes the point furthest
    from text is the tip, and attaches to the nearest CAD primitive.
    Suffers from high false positives on nearby dimension lines/hatch and misses dogleg knee.
    """
    leaders: List[MultileaderTopology] = []
    used_segments: set = set()

    for idx, text in enumerate(text_primitives):
        t_pos = getattr(text, "text_data", None) and text.text_data.position or Point2D(0, 0)
        # Find diagonal segments near text
        for seg in segments:
            seg_k = _segment_key(seg)
            if seg_k in used_segments or not is_diagonal_segment(seg):
                continue
            d1 = point_dist(seg[0], t_pos)
            d2 = point_dist(seg[1], t_pos)
            if min(d1, d2) <= proximity_tol_mm:
                used_segments.add(seg_k)
                tip = seg[0] if d1 > d2 else seg[1]
                knee = seg[1] if d1 > d2 else seg[0]
                leaders.append(MultileaderTopology(
                    id=f"leader_b_{idx}",
                    tip=tip,
                    knee=knee,
                    landing_end=knee,
                    pointer_segment=seg,
                    callout_text_id=text.id,
                    callout_text_content=text.text_data.content if text.text_data else None,
                    confidence=0.55,
                ))
                break

    return MultileaderExtractionResult(leaders=leaders)


# ---------------------------------------------------------------------------
# Strategy C: Unconstrained Hough Junction Graph
# ---------------------------------------------------------------------------

def extract_multileader_strategy_c(
    segments: List[Tuple[Point2D, Point2D]],
    text_primitives: List[Primitive],
    cad_primitives: List[Primitive],
    junction_tol_mm: float = DEFAULT_SNAP_TOL_MM,
) -> MultileaderExtractionResult:
    """Strategy C: Unconstrained Hough Junction Graph.
    Forms an undirected graph of connected segments. If a diagonal connects to a horizontal,
    marks it as a leader without validating arrowhead or directed flow.
    Fails on broken scan knees, crosshairs, and bracket corners.
    """
    leaders: List[MultileaderTopology] = []
    diagonals = [s for s in segments if is_diagonal_segment(s)]
    horizontals = [s for s in segments if is_horizontal_segment(s)]

    for idx, diag in enumerate(diagonals):
        for horiz in horizontals:
            # Check 4 endpoint combinations
            junction_pairs = [
                (diag[0], horiz[0], diag[1], horiz[1]),
                (diag[0], horiz[1], diag[1], horiz[0]),
                (diag[1], horiz[0], diag[0], horiz[1]),
                (diag[1], horiz[1], diag[0], horiz[0]),
            ]
            for d_knee, h_knee, d_tip, h_end in junction_pairs:
                if point_dist(d_knee, h_knee) <= junction_tol_mm:
                    leaders.append(MultileaderTopology(
                        id=f"leader_c_{idx}",
                        tip=d_tip,
                        knee=d_knee,
                        landing_end=h_end,
                        pointer_segment=diag,
                        landing_segment=horiz,
                        confidence=0.60,
                    ))
                    break

    return MultileaderExtractionResult(leaders=leaders)


# ---------------------------------------------------------------------------
# Strategy D: Multileader Topology & Directed Attachment Oracle
# ---------------------------------------------------------------------------

def _detect_arrowhead_at_point(
    candidate_point: Point2D,
    all_segments: List[Tuple[Point2D, Point2D]],
    pointer_seg: Tuple[Point2D, Point2D],
    max_len_mm: float = DEFAULT_ARROWHEAD_MAX_LEN_MM,
    min_len_mm: float = DEFAULT_ARROWHEAD_MIN_LEN_MM,
) -> Tuple[Optional[ArrowheadMarker], Optional[Tuple[Point2D, Point2D]]]:
    """Detects acute arrowhead barb segments or triangular marker at candidate_point.
    Returns (ArrowheadMarker, matched_barb_segment).
    """
    pointer_dx = candidate_point.x - (pointer_seg[0].x if point_dist(candidate_point, pointer_seg[1]) < 1e-3 else pointer_seg[1].x)
    pointer_dy = candidate_point.y - (pointer_seg[0].y if point_dist(candidate_point, pointer_seg[1]) < 1e-3 else pointer_seg[1].y)
    ptr_len = math.hypot(pointer_dx, pointer_dy)
    if ptr_len <= 1e-4:
        return None, None
    dir_u = (pointer_dx / ptr_len, pointer_dy / ptr_len)

    barb_matches: List[Tuple[Point2D, Point2D]] = []
    tol_endpoint = max(1.0, min_len_mm * 1.5)
    for s in all_segments:
        if s == pointer_seg:
            continue
        s_len = segment_length(s)
        if min_len_mm <= s_len <= max_len_mm:
            # Check if one endpoint is near candidate_point
            if point_dist(s[0], candidate_point) <= tol_endpoint or point_dist(s[1], candidate_point) <= tol_endpoint:
                barb_matches.append(s)

    if barb_matches:
        barb_seg = barb_matches[0]
        return ArrowheadMarker(
            tip=candidate_point,
            direction_vector=dir_u,
            length_mm=segment_length(barb_seg),
            marker_type="acute_arrow",
        ), barb_seg
    return None, None


def extract_multileader_strategy_d(
    segments: List[Tuple[Point2D, Point2D]],
    text_primitives: List[Primitive],
    cad_primitives: List[Primitive],
    snap_tol_mm: float = DEFAULT_SNAP_TOL_MM,
    horizontal_tol_deg: float = DEFAULT_HORIZONTAL_TOL_DEG,
    text_proximity_mm: float = DEFAULT_TEXT_PROXIMITY_MM,
    min_pointer_len_mm: float = 10.0,
    min_landing_len_mm: float = 5.0,
    arrowhead_max_len_mm: float = DEFAULT_ARROWHEAD_MAX_LEN_MM,
    arrowhead_min_len_mm: float = DEFAULT_ARROWHEAD_MIN_LEN_MM,
) -> MultileaderExtractionResult:
    """Strategy D: Multileader Topology & Directed Attachment Oracle.
    1. Arrowhead verification at pointer terminus.
    2. Knee junction detection with horizontal landing shelf.
    3. Directed topology: tip -> knee -> landing_end.
    4. Target feature snapping (circle, arc, chamfer, edge) <= snap_tol_mm.
    5. Text callout association adjacent to landing shelf.
    """
    # Non-finite coordinates safety
    for s in segments:
        if not (math.isfinite(s[0].x) and math.isfinite(s[0].y) and math.isfinite(s[1].x) and math.isfinite(s[1].y)):
            raise ValueError("Segments contain non-finite coordinates")
    for t in text_primitives:
        if t.text_data and not (math.isfinite(t.text_data.position.x) and math.isfinite(t.text_data.position.y)):
            raise ValueError(f"Text primitive {t.id} contains non-finite position")

    # Filter diagonal candidates (pointer legs) and horizontal candidates (landing shelves)
    pointer_candidates = [s for s in segments if is_diagonal_segment(s) and segment_length(s) >= min_pointer_len_mm]
    landing_candidates = [s for s in segments if is_horizontal_segment(s, horizontal_tol_deg) and segment_length(s) >= min_landing_len_mm]

    leaders: List[MultileaderTopology] = []
    used_pointer_keys: set = set()
    used_landing_keys: set = set()
    used_arrowhead_keys: set = set()
    used_texts: set = set()

    for p_idx, ptr in enumerate(pointer_candidates):
        ptr_k = _segment_key(ptr)
        p_len = segment_length(ptr)
        if p_len <= 1e-4 or ptr_k in used_pointer_keys:
            continue

        # Evaluate both endpoints as candidate tip vs knee
        for tip_cand, knee_cand in [(ptr[0], ptr[1]), (ptr[1], ptr[0])]:
            # Step 1: Arrowhead detection at tip_cand
            arrowhead, barb_seg = _detect_arrowhead_at_point(
                tip_cand, segments, ptr, max_len_mm=arrowhead_max_len_mm, min_len_mm=arrowhead_min_len_mm
            )

            # Step 2: Target primitive proximity check at tip_cand
            best_target: Optional[Primitive] = None
            best_target_dist = 999999.0
            for prim in cad_primitives:
                d = distance_point_to_primitive(tip_cand, prim)
                if d <= snap_tol_mm and d < best_target_dist:
                    best_target_dist = d
                    best_target = prim

            # A valid tip should either have an arrowhead marker OR be snapped to a target CAD feature
            if not arrowhead and best_target is None:
                continue

            # Step 3: Find connecting horizontal landing shelf at knee_cand
            best_landing: Optional[Tuple[Point2D, Point2D]] = None
            best_knee_dist = 999999.0
            landing_end: Point2D = knee_cand

            for land in landing_candidates:
                land_k = _segment_key(land)
                if land_k in used_landing_keys:
                    continue
                d_l0 = point_dist(knee_cand, land[0])
                d_l1 = point_dist(knee_cand, land[1])
                min_k_dist = min(d_l0, d_l1)
                if min_k_dist <= snap_tol_mm and min_k_dist < best_knee_dist:
                    best_knee_dist = min_k_dist
                    best_landing = land
                    landing_end = land[1] if d_l0 <= d_l1 else land[0]

            # Step 4: Associate text callout near landing shelf or knee
            search_anchor = landing_end if best_landing else knee_cand
            best_text: Optional[Primitive] = None
            best_text_dist = 999999.0

            for text in text_primitives:
                if text.id in used_texts or not text.text_data:
                    continue
                t_pos = text.text_data.position
                # Check horizontal alignment and proximity
                dx = abs(t_pos.x - search_anchor.x)
                dy = abs(t_pos.y - search_anchor.y)
                dist = math.hypot(dx, dy)
                if dist <= text_proximity_mm and dy <= snap_tol_mm * 1.5:
                    if dist < best_text_dist:
                        best_text_dist = dist
                        best_text = text

            # Verified Multileader topology
            used_pointer_keys.add(ptr_k)
            if barb_seg:
                used_arrowhead_keys.add(_segment_key(barb_seg))
            if best_landing:
                used_landing_keys.add(_segment_key(best_landing))
            if best_text:
                used_texts.add(best_text.id)

            conf = 1.0
            if not arrowhead:
                conf -= 0.15
            if not best_landing:
                conf -= 0.20
            if not best_target:
                conf -= 0.15

            target_type = None
            if best_target:
                target_type = "circle" if best_target.type == "circle" else "line"

            leaders.append(MultileaderTopology(
                id=f"mleader_{len(leaders) + 1}",
                tip=tip_cand,
                knee=knee_cand,
                landing_end=landing_end,
                pointer_segment=ptr,
                landing_segment=best_landing,
                arrowhead=arrowhead,
                attached_feature_id=best_target.id if best_target else None,
                attached_feature_type=target_type,
                attached_feature_distance_mm=round(best_target_dist, 3) if best_target else 0.0,
                callout_text_id=best_text.id if best_text else None,
                callout_text_content=best_text.text_data.content if best_text and best_text.text_data else None,
                confidence=round(max(0.5, conf), 3),
                measured={
                    "pointer_length_mm": round(p_len, 3),
                    "landing_length_mm": round(segment_length(best_landing), 3) if best_landing else 0.0,
                    "pointer_angle_deg": round(segment_angle_deg(ptr), 2),
                },
            ))
            break

    # Unattached segments
    unattached = [
        s for s in segments
        if _segment_key(s) not in used_pointer_keys
        and _segment_key(s) not in used_landing_keys
        and _segment_key(s) not in used_arrowhead_keys
    ]

    return MultileaderExtractionResult(
        leaders=leaders,
        unattached_segments=unattached,
    )
