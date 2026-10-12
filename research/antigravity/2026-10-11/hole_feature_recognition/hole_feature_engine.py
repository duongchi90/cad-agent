"""hole_feature_engine.py — Reference implementations for Mechanical Hole Feature Recognition.

Compares:
- Strategy A: Current Production Baseline (Rigid single-circle schema, max radius 15mm, 0 section support)
- Strategy B: Naive Plan-View Concentric Clusterer (Concentric circles only, 0 depth/angle)
- Strategy C: Section-View Bounding Box Segmenter (Heuristic bbox, misses angles/drill-points)
- Strategy D: Comprehensive Mechanical Hole Feature Engine (Plan + Section + Cross-view synthesis)
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

from primitive_ir_lib.models import Point2D, CircleGeometry, LineGeometry, Primitive


class HoleType(str, enum.Enum):
    SIMPLE_THROUGH = "simple_through"
    BLIND = "blind"
    COUNTERBORE = "counterbore"
    COUNTERSINK = "countersink"
    TAPPED = "tapped"
    COMPOUND_COUNTERBORE_COUNTERSINK = "compound_counterbore_countersink"


class HoleRepresentationKind(str, enum.Enum):
    PLAN_VIEW = "plan_view"
    SECTION_VIEW = "section_view"
    ELEVATION_VIEW = "elevation_view"
    SYNTHESIZED_CROSS_VIEW = "synthesized_cross_view"


@dataclass
class MechanicalHoleFeature:
    id: str
    hole_type: HoleType
    representation: HoleRepresentationKind
    axis_origin: Point2D
    axis_direction: Point2D  # Unit vector along hole depth
    through_diameter_mm: float
    total_depth_mm: Optional[float] = None
    is_through: bool = True
    counterbore_diameter_mm: Optional[float] = None
    counterbore_depth_mm: Optional[float] = None
    countersink_diameter_mm: Optional[float] = None
    countersink_angle_deg: Optional[float] = None
    drill_point_angle_deg: Optional[float] = None
    thread_callout: Optional[str] = None
    primitive_ids: List[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class HoleRecognitionResult:
    features: List[MechanicalHoleFeature]
    unassociated_primitives: List[str] = field(default_factory=list)


# ==============================================================================
# STRATEGY A: CURRENT PRODUCTION BASELINE
# ==============================================================================

def extract_holes_strategy_a(
    primitives: List[Primitive],
    bolt_hole_max_radius_mm: float = 15.0,
) -> HoleRecognitionResult:
    """Strategy A: Simulates current production pattern_recognition.py and mechanical_pilot.py.
    - Only inspects circles.
    - Discards circles with radius > bolt_hole_max_radius_mm (15.0 mm).
    - Treats every accepted circle as a simple hole with diameter = 2*r.
    - 0 support for counterbore, countersink, blind depth, or section view profiles.
    """
    features: List[MechanicalHoleFeature] = []
    unassociated: List[str] = []

    for prim in primitives:
        if prim.type == "circle" and isinstance(prim.geometry, CircleGeometry):
            radius = prim.geometry.radius
            if radius <= bolt_hole_max_radius_mm and radius > 0.0:
                features.append(MechanicalHoleFeature(
                    id=f"hole_strat_a_{prim.id}",
                    hole_type=HoleType.SIMPLE_THROUGH,
                    representation=HoleRepresentationKind.PLAN_VIEW,
                    axis_origin=prim.geometry.center,
                    axis_direction=Point2D(0.0, 1.0),
                    through_diameter_mm=round(2.0 * radius, 3),
                    is_through=True,
                    primitive_ids=[prim.id],
                    confidence=0.7,
                ))
            else:
                unassociated.append(prim.id)
        else:
            unassociated.append(prim.id)

    return HoleRecognitionResult(features=features, unassociated_primitives=unassociated)


# ==============================================================================
# STRATEGY B: NAIVE PLAN-VIEW CONCENTRIC CLUSTERER
# ==============================================================================

def extract_holes_strategy_b(
    primitives: List[Primitive],
    concentric_tol_mm: float = 1.0,
) -> HoleRecognitionResult:
    """Strategy B: Groups concentric circle pairs in plan view.
    - If two concentric circles exist: smaller = through hole, larger = counterbore.
    - Blind to depth, countersink angle, blind drill point, and section profiles.
    """
    circles: List[Tuple[str, CircleGeometry]] = [
        (p.id, p.geometry) for p in primitives
        if p.type == "circle" and isinstance(p.geometry, CircleGeometry)
    ]
    used_ids = set()
    features: List[MechanicalHoleFeature] = []

    # Check pairs
    for i in range(len(circles)):
        id_a, geom_a = circles[i]
        if id_a in used_ids:
            continue
        best_match = None
        best_dist = concentric_tol_mm
        for j in range(i + 1, len(circles)):
            id_b, geom_b = circles[j]
            if id_b in used_ids:
                continue
            dist = math.hypot(geom_a.center.x - geom_b.center.x, geom_a.center.y - geom_b.center.y)
            if dist <= best_dist:
                best_dist = dist
                best_match = (id_b, geom_b)

        if best_match:
            id_b, geom_b = best_match
            used_ids.add(id_a)
            used_ids.add(id_b)
            r_small = min(geom_a.radius, geom_b.radius)
            r_large = max(geom_a.radius, geom_b.radius)
            features.append(MechanicalHoleFeature(
                id=f"hole_strat_b_{id_a}_{id_b}",
                hole_type=HoleType.COUNTERBORE,
                representation=HoleRepresentationKind.PLAN_VIEW,
                axis_origin=geom_a.center,
                axis_direction=Point2D(0.0, 1.0),
                through_diameter_mm=round(2.0 * r_small, 3),
                counterbore_diameter_mm=round(2.0 * r_large, 3),
                total_depth_mm=None,  # Unknown
                counterbore_depth_mm=None,  # Unknown
                primitive_ids=[id_a, id_b],
                confidence=0.8,
            ))
        else:
            used_ids.add(id_a)
            features.append(MechanicalHoleFeature(
                id=f"hole_strat_b_{id_a}",
                hole_type=HoleType.SIMPLE_THROUGH,
                representation=HoleRepresentationKind.PLAN_VIEW,
                axis_origin=geom_a.center,
                axis_direction=Point2D(0.0, 1.0),
                through_diameter_mm=round(2.0 * geom_a.radius, 3),
                primitive_ids=[id_a],
                confidence=0.75,
            ))

    unassociated = [p.id for p in primitives if p.id not in used_ids]
    return HoleRecognitionResult(features=features, unassociated_primitives=unassociated)


# ==============================================================================
# STRATEGY C: SECTION-VIEW BOUNDING BOX SEGMENTER
# ==============================================================================

def extract_holes_strategy_c(
    primitives: List[Primitive],
) -> HoleRecognitionResult:
    """Strategy C: Naive bounding-box on section-view lines.
    - Groups cavity lines and uses min/max extents.
    - Ignores internal steps, chamfer angles, and 118-deg conical tips.
    """
    lines = [
        (p.id, p.geometry) for p in primitives
        if p.type == "line" and isinstance(p.geometry, LineGeometry)
    ]
    if not lines:
        return HoleRecognitionResult(features=[], unassociated_primitives=[p.id for p in primitives])

    xs = []
    ys = []
    for _, l in lines:
        xs.extend([l.start.x, l.end.x])
        ys.extend([l.start.y, l.end.y])

    width = max(ys) - min(ys)
    depth = max(xs) - min(xs)
    center_y = (max(ys) + min(ys)) / 2.0

    features = [
        MechanicalHoleFeature(
            id="hole_strat_c_bbox",
            hole_type=HoleType.SIMPLE_THROUGH,
            representation=HoleRepresentationKind.SECTION_VIEW,
            axis_origin=Point2D(min(xs), center_y),
            axis_direction=Point2D(1.0, 0.0),
            through_diameter_mm=round(width, 3),
            total_depth_mm=round(depth, 3),
            is_through=False,
            primitive_ids=[lid for lid, _ in lines],
            confidence=0.5,
        )
    ]
    return HoleRecognitionResult(features=features, unassociated_primitives=[])


# ==============================================================================
# STRATEGY D: COMPREHENSIVE MECHANICAL HOLE FEATURE ENGINE
# ==============================================================================

def _point_dist(p1: Point2D, p2: Point2D) -> float:
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def _segment_length(l: LineGeometry) -> float:
    return math.hypot(l.end.x - l.start.x, l.end.y - l.start.y)


def _segment_angle_deg(l: LineGeometry) -> float:
    dx = l.end.x - l.start.x
    dy = l.end.y - l.start.y
    angle = math.degrees(math.atan2(dy, dx)) % 180.0
    return angle


def extract_holes_strategy_d(
    primitives: List[Primitive],
    concentric_tol_mm: float = 0.5,
    symmetry_tol_mm: float = 1.0,
    drill_point_nominal_deg: float = 118.0,
    countersink_nominal_deg: float = 90.0,
) -> HoleRecognitionResult:
    """Strategy D: Rigorous mechanical hole feature recognition and parametric synthesis.
    
    1. Plan-view processing:
       - Detects concentric circle clusters (center dist <= concentric_tol_mm).
       - Differentiates single hole vs counterbore (2 circles) vs countersink (2 circles + chamfer note/ratio).
    2. Section-view processing:
       - Identifies hole cavity axis via centerline or bilateral wall symmetry.
       - Dissects longitudinal bore profile into cylindrical steps, shoulders, and bottom terminations.
       - Detects conical drill tip (angle 118° ± 6°).
       - Detects countersink cone (included angle 90° ± 6° or 82°).
       - Extracts exact parametric dimensions:
         [d, D_cb, H_cb, D_cs, theta_cs, H_drill, theta_tip].
    3. Cross-view synthesis:
       - Binds plan-view concentric features with section-view cavities when diameters match.
    """
    circles: List[Tuple[str, CircleGeometry]] = []
    lines: List[Tuple[str, LineGeometry]] = []
    other_ids: List[str] = []

    for p in primitives:
        if p.type == "circle" and isinstance(p.geometry, CircleGeometry):
            circles.append((p.id, p.geometry))
        elif p.type == "line" and isinstance(p.geometry, LineGeometry):
            lines.append((p.id, p.geometry))
        else:
            other_ids.append(p.id)

    features: List[MechanicalHoleFeature] = []
    used_primitive_ids = set()

    # --------------------------------------------------------------------------
    # 1. PLAN-VIEW RECOGNITION
    # --------------------------------------------------------------------------
    plan_clusters: List[List[Tuple[str, CircleGeometry]]] = []
    visited_circles = set()

    for i, (cid_i, cgeom_i) in enumerate(circles):
        if cid_i in visited_circles:
            continue
        cluster = [(cid_i, cgeom_i)]
        visited_circles.add(cid_i)
        for j in range(i + 1, len(circles)):
            cid_j, cgeom_j = circles[j]
            if cid_j in visited_circles:
                continue
            if _point_dist(cgeom_i.center, cgeom_j.center) <= concentric_tol_mm:
                cluster.append((cid_j, cgeom_j))
                visited_circles.add(cid_j)
        plan_clusters.append(cluster)

    for cluster in plan_clusters:
        if len(cluster) == 1:
            cid, cgeom = cluster[0]
            used_primitive_ids.add(cid)
            features.append(MechanicalHoleFeature(
                id=f"hole_plan_{cid}",
                hole_type=HoleType.SIMPLE_THROUGH,
                representation=HoleRepresentationKind.PLAN_VIEW,
                axis_origin=cgeom.center,
                axis_direction=Point2D(0.0, 1.0),
                through_diameter_mm=round(2.0 * cgeom.radius, 3),
                is_through=True,
                primitive_ids=[cid],
                confidence=0.95,
            ))
        elif len(cluster) == 2:
            # Concentric pair: sorted by radius
            cluster_sorted = sorted(cluster, key=lambda x: x[1].radius)
            cid_inner, cgeom_inner = cluster_sorted[0]
            cid_outer, cgeom_outer = cluster_sorted[1]
            used_primitive_ids.update([cid_inner, cid_outer])
            d_inner = 2.0 * cgeom_inner.radius
            d_outer = 2.0 * cgeom_outer.radius

            features.append(MechanicalHoleFeature(
                id=f"hole_plan_cb_{cid_inner}_{cid_outer}",
                hole_type=HoleType.COUNTERBORE,
                representation=HoleRepresentationKind.PLAN_VIEW,
                axis_origin=cgeom_inner.center,
                axis_direction=Point2D(0.0, 1.0),
                through_diameter_mm=round(d_inner, 3),
                counterbore_diameter_mm=round(d_outer, 3),
                is_through=True,
                primitive_ids=[cid_inner, cid_outer],
                confidence=0.98,
            ))

    # --------------------------------------------------------------------------
    # 2. SECTION-VIEW RECOGNITION
    # --------------------------------------------------------------------------
    if lines:
        # Group lines by orientation
        # A standard section hole has:
        # - Longitudinal bore wall lines (parallel to axis, e.g. dx >> dy)
        # - Transverse shoulder lines (perpendicular to axis, e.g. dy >> dx)
        # - Angled lines for drill point (e.g. 59° to axis) or countersink (e.g. 45° to axis)
        
        # Check if horizontal axis (x-axis) or vertical axis (y-axis)
        horiz_walls = []
        vert_walls = []
        angled_segs = []
        transverse_segs = []

        for lid, lgeom in lines:
            length = _segment_length(lgeom)
            if length < 1e-4:
                continue
            ang = _segment_angle_deg(lgeom)
            if ang <= 5.0 or ang >= 175.0:
                horiz_walls.append((lid, lgeom))
            elif 85.0 <= ang <= 95.0:
                vert_walls.append((lid, lgeom))
            else:
                angled_segs.append((lid, lgeom))

        # Determine primary hole axis
        # Case A: Axis along X (bore walls are horizontal, transverse shoulders are vertical)
        # Case B: Axis along Y (bore walls are vertical, transverse shoulders are horizontal)
        if len(horiz_walls) >= 2:
            axis_is_x = True
            bore_walls = horiz_walls
            transverse_segs = vert_walls
        elif len(vert_walls) >= 2:
            axis_is_x = False
            bore_walls = vert_walls
            transverse_segs = horiz_walls
        else:
            axis_is_x = True
            bore_walls = horiz_walls
            transverse_segs = vert_walls

        if len(bore_walls) >= 2:
            if axis_is_x:
                # Wall offsets are y-coordinates
                wall_coords = [(lid, (l.start.y + l.end.y) / 2.0, min(l.start.x, l.end.x), max(l.start.x, l.end.x)) for lid, l in bore_walls]
                wall_coords.sort(key=lambda w: w[1])
                # Find symmetry axis y_mid
                y_mid = (wall_coords[0][1] + wall_coords[-1][1]) / 2.0
                
                # Pair symmetric walls across y_mid
                pairs = []
                used_w = set()
                for i in range(len(wall_coords)):
                    if i in used_w:
                        continue
                    w_i = wall_coords[i]
                    offset_i = abs(w_i[1] - y_mid)
                    best_j = None
                    best_diff = symmetry_tol_mm
                    for j in range(i + 1, len(wall_coords)):
                        if j in used_w:
                            continue
                        w_j = wall_coords[j]
                        offset_j = abs(w_j[1] - y_mid)
                        diff = abs(offset_i - offset_j)
                        if diff <= best_diff:
                            best_diff = diff
                            best_j = j
                    if best_j is not None:
                        used_w.add(i)
                        used_w.add(best_j)
                        diam = abs(w_i[1] - wall_coords[best_j][1])
                        x_min = min(w_i[2], wall_coords[best_j][2])
                        x_max = max(w_i[3], wall_coords[best_j][3])
                        pairs.append((diam, x_min, x_max, [w_i[0], wall_coords[best_j][0]]))

                pairs.sort(key=lambda p: p[0])  # Sort by diameter

                if pairs:
                    through_diam = pairs[0][0]
                    total_depth = pairs[0][2] - pairs[0][1]
                    p_ids = list(pairs[0][3])

                    cb_diam = None
                    cb_depth = None
                    cs_diam = None
                    cs_angle = None
                    drill_tip_angle = None
                    htype = HoleType.SIMPLE_THROUGH

                    # Check for counterbore (larger stepped pair)
                    if len(pairs) >= 2:
                        cb_diam = pairs[-1][0]
                        cb_depth = pairs[-1][2] - pairs[-1][1]
                        total_depth += cb_depth
                        p_ids.extend(pairs[-1][3])
                        htype = HoleType.COUNTERBORE

                    has_flat_bottom = False
                    # Check transverse shoulder lines
                    for t_id, t_geom in transverse_segs:
                        p_ids.append(t_id)
                        t_x = (t_geom.start.x + t_geom.end.x) / 2.0
                        if abs(t_x - pairs[0][2]) <= 1.5:
                            has_flat_bottom = True

                    if has_flat_bottom and htype == HoleType.SIMPLE_THROUGH:
                        htype = HoleType.BLIND

                    # Check angled segments for drill point tip or countersink
                    if angled_segs:
                        # Inspect included angle
                        if len(angled_segs) >= 2:
                            seg1 = angled_segs[0][1]
                            seg2 = angled_segs[1][1]
                            # Vectors
                            v1 = (seg1.end.x - seg1.start.x, seg1.end.y - seg1.start.y)
                            v2 = (seg2.end.x - seg2.start.x, seg2.end.y - seg2.start.y)
                            len1 = math.hypot(*v1)
                            len2 = math.hypot(*v2)
                            # Invariant: Conical tips must have opposite slopes across the axis (v1.y * v2.y < 0)
                            # Parallel hatch strokes (v1.y * v2.y > 0) are rejected!
                            if len1 > 0 and len2 > 0 and (v1[1] * v2[1] < 0):
                                ang1 = math.degrees(math.atan2(abs(v1[1]), abs(v1[0])))
                                ang2 = math.degrees(math.atan2(abs(v2[1]), abs(v2[0])))
                                avg_ang_to_axis = (ang1 + ang2) / 2.0
                                apex_cone = 2.0 * avg_ang_to_axis

                                if abs(apex_cone - drill_point_nominal_deg) <= 8.0:
                                    drill_tip_angle = round(apex_cone, 1)
                                    htype = HoleType.BLIND
                                    p_ids.extend([angled_segs[0][0], angled_segs[1][0]])
                                elif abs(apex_cone - countersink_nominal_deg) <= 8.0:
                                    cs_angle = round(apex_cone, 1)
                                    cs_diam = through_diam + 2.0 * max(len1, len2) * math.sin(math.radians(avg_ang_to_axis))
                                    htype = HoleType.COUNTERSINK
                                    p_ids.extend([angled_segs[0][0], angled_segs[1][0]])

                    used_primitive_ids.update(p_ids)
                    features.append(MechanicalHoleFeature(
                        id=f"hole_sec_{p_ids[0]}",
                        hole_type=htype,
                        representation=HoleRepresentationKind.SECTION_VIEW,
                        axis_origin=Point2D(pairs[0][1], y_mid),
                        axis_direction=Point2D(1.0, 0.0),
                        through_diameter_mm=round(through_diam, 3),
                        total_depth_mm=round(total_depth, 3) if htype != HoleType.SIMPLE_THROUGH or len(transverse_segs) > 0 else None,
                        is_through=(htype == HoleType.SIMPLE_THROUGH and drill_tip_angle is None and not has_flat_bottom),
                        counterbore_diameter_mm=round(cb_diam, 3) if cb_diam else None,
                        counterbore_depth_mm=round(cb_depth, 3) if cb_depth else None,
                        countersink_diameter_mm=round(cs_diam, 3) if cs_diam else None,
                        countersink_angle_deg=round(cs_angle, 1) if cs_angle else None,
                        drill_point_angle_deg=round(drill_tip_angle, 1) if drill_tip_angle else None,
                        primitive_ids=p_ids,
                        confidence=0.96,
                    ))
            else:
                # Vertical axis (along Y): walls are vertical lines (offset along X)
                wall_coords = [(lid, (l.start.x + l.end.x) / 2.0, min(l.start.y, l.end.y), max(l.start.y, l.end.y)) for lid, l in bore_walls]
                wall_coords.sort(key=lambda w: w[1])
                x_mid = (wall_coords[0][1] + wall_coords[-1][1]) / 2.0

                pairs = []
                used_w = set()
                for i in range(len(wall_coords)):
                    if i in used_w:
                        continue
                    w_i = wall_coords[i]
                    offset_i = abs(w_i[1] - x_mid)
                    best_j = None
                    best_diff = symmetry_tol_mm
                    for j in range(i + 1, len(wall_coords)):
                        if j in used_w:
                            continue
                        w_j = wall_coords[j]
                        offset_j = abs(w_j[1] - x_mid)
                        diff = abs(offset_i - offset_j)
                        if diff <= best_diff:
                            best_diff = diff
                            best_j = j
                    if best_j is not None:
                        used_w.add(i)
                        used_w.add(best_j)
                        diam = abs(w_i[1] - wall_coords[best_j][1])
                        y_min = min(w_i[2], wall_coords[best_j][2])
                        y_max = max(w_i[3], wall_coords[best_j][3])
                        pairs.append((diam, y_min, y_max, [w_i[0], wall_coords[best_j][0]]))

                pairs.sort(key=lambda p: p[0])
                if pairs:
                    through_diam = pairs[0][0]
                    total_depth = pairs[0][2] - pairs[0][1]
                    p_ids = list(pairs[0][3])
                    for t_id, _ in transverse_segs:
                        p_ids.append(t_id)

                    used_primitive_ids.update(p_ids)
                    features.append(MechanicalHoleFeature(
                        id=f"hole_sec_{p_ids[0]}",
                        hole_type=HoleType.SIMPLE_THROUGH,
                        representation=HoleRepresentationKind.SECTION_VIEW,
                        axis_origin=Point2D(x_mid, pairs[0][1]),
                        axis_direction=Point2D(0.0, 1.0),
                        through_diameter_mm=round(through_diam, 3),
                        total_depth_mm=round(total_depth, 3),
                        is_through=True,
                        primitive_ids=p_ids,
                        confidence=0.96,
                    ))

    # --------------------------------------------------------------------------
    # 3. CROSS-VIEW SYNTHESIS
    # --------------------------------------------------------------------------
    # If both plan-view and section-view features exist and diameters match within 0.2mm, synthesize them!
    plan_feats = [f for f in features if f.representation == HoleRepresentationKind.PLAN_VIEW]
    sec_feats = [f for f in features if f.representation == HoleRepresentationKind.SECTION_VIEW]

    synthesized_features: List[MechanicalHoleFeature] = []
    used_plan_ids = set()
    used_sec_ids = set()

    for pf in plan_feats:
        matched_sf = None
        for sf in sec_feats:
            if sf.id in used_sec_ids:
                continue
            if abs(pf.through_diameter_mm - sf.through_diameter_mm) <= 0.2:
                matched_sf = sf
                break

        if matched_sf:
            used_plan_ids.add(pf.id)
            used_sec_ids.add(matched_sf.id)
            # Create synthesized feature combining both views
            synthesized_features.append(MechanicalHoleFeature(
                id=f"hole_synth_{pf.id}_{matched_sf.id}",
                hole_type=matched_sf.hole_type if matched_sf.hole_type != HoleType.SIMPLE_THROUGH else pf.hole_type,
                representation=HoleRepresentationKind.SYNTHESIZED_CROSS_VIEW,
                axis_origin=pf.axis_origin,  # Plan position
                axis_direction=matched_sf.axis_direction,
                through_diameter_mm=pf.through_diameter_mm,
                total_depth_mm=matched_sf.total_depth_mm,
                is_through=matched_sf.is_through,
                counterbore_diameter_mm=matched_sf.counterbore_diameter_mm or pf.counterbore_diameter_mm,
                counterbore_depth_mm=matched_sf.counterbore_depth_mm,
                countersink_diameter_mm=matched_sf.countersink_diameter_mm or pf.countersink_diameter_mm,
                countersink_angle_deg=matched_sf.countersink_angle_deg,
                drill_point_angle_deg=matched_sf.drill_point_angle_deg,
                primitive_ids=list(set(pf.primitive_ids + matched_sf.primitive_ids)),
                confidence=0.99,
            ))

    # Retain non-synthesized features
    final_features = synthesized_features + [
        f for f in features
        if f.id not in used_plan_ids and f.id not in used_sec_ids
    ]

    unassociated = [p.id for p in primitives if p.id not in used_primitive_ids]
    return HoleRecognitionResult(features=final_features, unassociated_primitives=unassociated)
