"""
compound_feature_engine.py — Reference Engine for Compound Feature Assembly (Slots, Filleted Frames, Lugs).

Empirically benchmarks and compares compound part recognition strategies:
- Strategy A: Current Production Main (semantic_ir_lib/pattern_compound.py)
- Strategy B: Naive Bounding Box Overlap Clusterer (blind geometric proximity)
- Strategy C: Line-Only Polygon Cycle Matcher (ignores all curved transitions)
- Strategy D: Constraint-Driven Multi-Primitive Feature Grammar (Selected Oracle)
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

_repo_root = str(Path(__file__).resolve().parents[4])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from primitive_ir_lib.models import (
    ArcGeometry,
    CircleGeometry,
    LineGeometry,
    Point2D,
    Primitive,
    Trace,
    new_id,
)
from semantic_ir_lib.models import Constraint, GeometrySummary, PartType, SemanticPart
from semantic_ir_lib.pattern_compound import (
    build_compound_parts as run_strategy_a_compound,
    _index_constraints_by_pair,
    _constraints_between,
    _constraint_pairs,
    _pair_neighbors,
    _avg_confidence,
)


def make_point(x: float, y: float) -> Point2D:
    return Point2D(x=float(x), y=float(y))


def _safe_bbox(c1: float, c2: float, c3: float, c4: float) -> Tuple[int, int, int, int]:
    if math.isfinite(c1) and math.isfinite(c2) and math.isfinite(c3) and math.isfinite(c4):
        return (int(c1), int(c2), int(c3), int(c4))
    return (0, 0, 0, 0)


def make_line(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    id_: str = "",
) -> Primitive:
    return Primitive(
        id=id_ or new_id("line"),
        type="line",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=_safe_bbox(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1]))),
        geometry=LineGeometry(start=make_point(p1[0], p1[1]), end=make_point(p2[0], p2[1])),
    )


def make_circle(
    center: Tuple[float, float],
    radius: float,
    id_: str = "",
) -> Primitive:
    return Primitive(
        id=id_ or new_id("circle"),
        type="circle",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=_safe_bbox(center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)),
        geometry=CircleGeometry(center=make_point(center[0], center[1]), radius=float(radius)),
    )


def make_arc(
    center: Tuple[float, float],
    radius: float,
    start_deg: float,
    end_deg: float,
    id_: str = "",
) -> Primitive:
    return Primitive(
        id=id_ or new_id("arc"),
        type="arc",
        source="geometry_opencv",
        confidence=0.95,
        trace=Trace(bbox_px=_safe_bbox(center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)),
        geometry=ArcGeometry(
            center=make_point(center[0], center[1]),
            radius=float(radius),
            start_angle_deg=float(start_deg),
            end_angle_deg=float(end_deg),
        ),
    )


def make_constraint(
    type_: str,
    id1: str,
    id2: str,
    confidence: float = 0.95,
    tolerance: Optional[dict] = None,
    measured: Optional[dict] = None,
) -> Constraint:
    return Constraint(
        type=type_,
        primitive_ids=[id1, id2],
        confidence=confidence,
        tolerance=tolerance or {"distance_mm": 5.0},
        measured=measured or {},
    )


# ---------------------------------------------------------------------------
# Strategy B: Naive Bounding Box Overlap Clusterer
# ---------------------------------------------------------------------------

def run_strategy_b(
    primitives: Sequence[Primitive],
    constraints: Sequence[Constraint],
    overlap_margin_px: float = 2.0,
) -> List[SemanticPart]:
    """Strategy B: Groups primitives if their axis-aligned bounding boxes overlap."""
    n = len(primitives)
    adj: Dict[int, Set[int]] = {i: set() for i in range(n)}

    for i in range(n):
        b1 = primitives[i].trace.bbox_px
        for j in range(i + 1, n):
            b2 = primitives[j].trace.bbox_px
            # Check overlap with margin
            x_overlap = not (b1[2] + overlap_margin_px < b2[0] or b2[2] + overlap_margin_px < b1[0])
            y_overlap = not (b1[3] + overlap_margin_px < b2[1] or b2[3] + overlap_margin_px < b1[1])
            if x_overlap and y_overlap:
                adj[i].add(j)
                adj[j].add(i)

    visited: Set[int] = set()
    parts: List[SemanticPart] = []
    for i in range(n):
        if i in visited:
            continue
        cluster = []
        q = [i]
        visited.add(i)
        while q:
            curr = q.pop()
            cluster.append(curr)
            for neighbor in adj[curr]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    q.append(neighbor)
        if len(cluster) >= 2:
            parts.append(SemanticPart(
                part_type="unclassified",
                primitive_ids=[primitives[k].id for k in cluster],
                confidence=0.5,
                source="rule_geometry",
            ))
    return parts


# ---------------------------------------------------------------------------
# Strategy C: Line-Only Polygon Cycle Matcher
# ---------------------------------------------------------------------------

def run_strategy_c(
    primitives: Sequence[Primitive],
    constraints: Sequence[Constraint],
) -> List[SemanticPart]:
    """Strategy C: Only traverses line coincident_endpoint cycles, ignoring all arcs."""
    lines = [p for p in primitives if p.type == "line"]
    idx = _index_constraints_by_pair(list(constraints))
    parallel_pairs = _constraint_pairs(constraints, "parallel")
    coincident_pairs = _constraint_pairs(constraints, "coincident_endpoint")
    coincident_neighbors = _pair_neighbors(coincident_pairs)

    from semantic_ir_lib.pattern_compound import _find_khung_chu_nhat, _find_gia_do
    raw = []
    raw += _find_khung_chu_nhat(idx, parallel_pairs, coincident_neighbors)
    perpendicular_pairs = _constraint_pairs(constraints, "perpendicular")
    raw += _find_gia_do(idx, perpendicular_pairs, coincident_pairs)

    raw.sort(key=lambda p: (-len(p.primitive_ids), -p.confidence))
    consumed: Set[str] = set()
    parts: List[SemanticPart] = []
    for p in raw:
        if any(pid in consumed for pid in p.primitive_ids):
            continue
        parts.append(p)
        consumed.update(p.primitive_ids)
    return parts


# ---------------------------------------------------------------------------
# Strategy D: Constraint-Driven Multi-Primitive Feature Grammar (Selected)
# ---------------------------------------------------------------------------

def _find_filleted_khung_chu_nhat(
    prim_by_id: Dict[str, Primitive],
    idx: Dict[Tuple[str, str], List[Constraint]],
    parallel_pairs: Set[Tuple[str, str]],
    perpendicular_pairs: Set[Tuple[str, str]],
    coincident_neighbors: Dict[str, Set[str]],
    tangent_pairs: Set[Tuple[str, str]],
    arc_ids: List[str],
) -> List[SemanticPart]:
    """Finds rectangular frames: both sharp (4 lines) and filleted (4 lines + 4 corner arcs)."""
    parts: List[SemanticPart] = []
    all_parallels = list(parallel_pairs)

    # 1. Filleted rectangular frames (4 lines + 4 corner arcs)
    for i in range(len(all_parallels)):
        p1_a, p1_b = all_parallels[i]
        for j in range(i + 1, len(all_parallels)):
            p2_a, p2_b = all_parallels[j]
            lines_4 = {p1_a, p1_b, p2_a, p2_b}
            if len(lines_4) != 4:
                continue

            # Verify perpendicular relations between opposite pairs
            perp_count = 0
            for l1 in (p1_a, p1_b):
                for l2 in (p2_a, p2_b):
                    pair = tuple(sorted((l1, l2)))
                    if pair in perpendicular_pairs:
                        perp_count += 1
            if perp_count < 2:
                continue

            # Check if each corner is connected by a tangent fillet arc
            matched_arcs: List[str] = []
            corner_pairs = [
                (p1_a, p2_a),
                (p1_a, p2_b),
                (p1_b, p2_a),
                (p1_b, p2_b),
            ]
            for la, lb in corner_pairs:
                for arc_id in arc_ids:
                    if arc_id in matched_arcs:
                        continue
                    has_tan_a = bool(_constraints_between(idx, la, arc_id, "tangent"))
                    has_tan_b = bool(_constraints_between(idx, lb, arc_id, "tangent"))
                    if has_tan_a and has_tan_b:
                        matched_arcs.append(arc_id)
                        break

            if len(matched_arcs) == 4:
                # 4 corner arcs found! Filleted rectangle
                all_pids = sorted(list(lines_4) + matched_arcs)
                all_cs: List[Constraint] = []
                for a, b in combinations(all_pids, 2):
                    all_cs.extend(_constraints_between(idx, a, b))
                conf = _avg_confidence(all_cs) if all_cs else 0.90
                parts.append(SemanticPart(
                    part_type="khung_chu_nhat",
                    primitive_ids=all_pids,
                    confidence=round(conf, 3),
                    source="rule_geometry",
                    geometry_summary=GeometrySummary(),
                ))

    return parts


def _find_filleted_gia_do(
    idx: Dict[Tuple[str, str], List[Constraint]],
    perpendicular_pairs: Set[Tuple[str, str]],
    arc_ids: List[str],
) -> List[SemanticPart]:
    """Finds L-brackets with a fillet transition at the corner: 2 lines + 1 tangent arc."""
    parts: List[SemanticPart] = []
    for l1, l2 in perpendicular_pairs:
        for arc_id in arc_ids:
            has_tan_1 = bool(_constraints_between(idx, l1, arc_id, "tangent"))
            has_tan_2 = bool(_constraints_between(idx, l2, arc_id, "tangent"))
            if has_tan_1 and has_tan_2:
                all_cs = _constraints_between(idx, l1, arc_id) + _constraints_between(idx, l2, arc_id)
                conf = _avg_confidence(all_cs) if all_cs else 0.85
                parts.append(SemanticPart(
                    part_type="gia_do",
                    primitive_ids=sorted([l1, l2, arc_id]),
                    confidence=round(conf, 3),
                    source="rule_geometry",
                    geometry_summary=GeometrySummary(),
                ))
    return parts


def _find_slot_features(
    idx: Dict[Tuple[str, str], List[Constraint]],
    parallel_pairs: Set[Tuple[str, str]],
    arc_ids: List[str],
) -> List[SemanticPart]:
    """Finds elongated slots (mechanical_hole_feature): 2 parallel lines + 2 tangent arcs."""
    parts: List[SemanticPart] = []

    for l1, l2 in parallel_pairs:
        # Candidate arcs tangent to BOTH l1 and l2
        connecting_arcs = []
        for arc_id in arc_ids:
            has_tan_1 = bool(_constraints_between(idx, l1, arc_id, "tangent"))
            has_tan_2 = bool(_constraints_between(idx, l2, arc_id, "tangent"))
            if has_tan_1 and has_tan_2:
                connecting_arcs.append(arc_id)

        if len(connecting_arcs) >= 2:
            # Found 2 end arcs tangent to both lines!
            selected_arcs = connecting_arcs[:2]
            pids = sorted([l1, l2] + selected_arcs)
            all_cs = []
            for a, b in combinations(pids, 2):
                all_cs.extend(_constraints_between(idx, a, b))
            conf = _avg_confidence(all_cs) if all_cs else 0.92
            parts.append(SemanticPart(
                part_type="mechanical_hole_feature",
                primitive_ids=pids,
                confidence=round(conf, 3),
                source="rule_geometry",
                geometry_summary=GeometrySummary(),
            ))

    return parts


def _find_mounting_lugs(
    idx: Dict[Tuple[str, str], List[Constraint]],
    arc_ids: List[str],
    circle_ids: List[str],
    line_ids: List[str],
) -> List[SemanticPart]:
    """Finds mounting lugs / tabs: outer arc + concentric inner bolt hole circle + 2 tangent lines."""
    parts: List[SemanticPart] = []

    for arc_id in arc_ids:
        # Look for concentric circle (bolt hole)
        concentric_circles = []
        for c_id in circle_ids:
            if _constraints_between(idx, arc_id, c_id, "concentric"):
                concentric_circles.append(c_id)

        if not concentric_circles:
            continue

        c_hole = concentric_circles[0]

        # Look for lines tangent to outer arc
        tangent_lines = []
        for l_id in line_ids:
            if _constraints_between(idx, l_id, arc_id, "tangent"):
                tangent_lines.append(l_id)

        if len(tangent_lines) >= 2:
            l1, l2 = tangent_lines[0], tangent_lines[1]
            pids = sorted([arc_id, c_hole, l1, l2])
            all_cs = []
            for a, b in combinations(pids, 2):
                all_cs.extend(_constraints_between(idx, a, b))
            conf = _avg_confidence(all_cs) if all_cs else 0.90
            parts.append(SemanticPart(
                part_type="ban_le",  # Hinge/mounting tab
                primitive_ids=pids,
                confidence=round(conf, 3),
                source="rule_geometry",
                geometry_summary=GeometrySummary(),
            ))

    return parts


def detect_compound_features(
    primitives: Sequence[Primitive],
    constraints: Sequence[Constraint],
) -> List[SemanticPart]:
    """Strategy D: Multi-Primitive Constraint-Driven Compound Feature Assembly.

    Recognizes:
    1. Filleted & Sharp Rectangular Frames (khung_chu_nhat)
    2. Elongated Slots (mechanical_hole_feature / ranh_then)
    3. Filleted & Sharp L-Brackets (gia_do)
    4. Mounting Lugs / Flange Tabs (ban_le)
    5. Multi-Line Structural Joints (diem_noi)
    """
    prim_by_id: Dict[str, Primitive] = {p.id: p for p in primitives}
    line_ids = [p.id for p in primitives if p.type == "line"]
    circle_ids = [p.id for p in primitives if p.type == "circle"]
    arc_ids = [p.id for p in primitives if p.type == "arc"]

    constraint_list = list(constraints)
    idx = _index_constraints_by_pair(constraint_list)
    parallel_pairs = _constraint_pairs(constraint_list, "parallel")
    coincident_pairs = _constraint_pairs(constraint_list, "coincident_endpoint")
    perpendicular_pairs = _constraint_pairs(constraint_list, "perpendicular")
    tangent_pairs = _constraint_pairs(constraint_list, "tangent")
    concentric_pairs = _constraint_pairs(constraint_list, "concentric")
    coincident_neighbors = _pair_neighbors(coincident_pairs)

    raw: List[SemanticPart] = []

    # 1. Filleted rectangular frames (8 primitives: 4 lines + 4 corner arcs)
    raw += _find_filleted_khung_chu_nhat(
        prim_by_id, idx, parallel_pairs, perpendicular_pairs, coincident_neighbors, tangent_pairs, arc_ids
    )

    # 2. Elongated slots (4 primitives: 2 lines + 2 tangent arcs)
    raw += _find_slot_features(idx, parallel_pairs, arc_ids)

    # 3. Mounting lugs (4 primitives: 1 outer arc + 1 concentric circle + 2 tangent lines)
    raw += _find_mounting_lugs(idx, arc_ids, circle_ids, line_ids)

    # 4. Filleted L-brackets (3 primitives: 2 lines + 1 corner arc)
    raw += _find_filleted_gia_do(idx, perpendicular_pairs, arc_ids)

    # 5. Legacy sharp features from Strategy A
    from semantic_ir_lib.pattern_compound import (
        _find_khung_chu_nhat as _find_sharp_khung,
        _find_gia_do as _find_sharp_gia_do,
        _find_ban_le as _find_sharp_ban_le,
        _find_diem_noi,
    )
    raw += _find_sharp_khung(idx, parallel_pairs, coincident_neighbors)
    raw += _find_sharp_gia_do(idx, perpendicular_pairs, coincident_pairs)
    raw += _find_sharp_ban_le(prim_by_id, line_ids, circle_ids, idx, 30.0, 50.0)
    raw += _find_diem_noi(prim_by_id, line_ids, idx, 5.0)

    # Greedy dedup by size and confidence: larger compound parts win
    raw.sort(key=lambda p: (-len(p.primitive_ids), -p.confidence))
    consumed: Set[str] = set()
    parts: List[SemanticPart] = []
    for p in raw:
        if any(pid in consumed for pid in p.primitive_ids):
            continue
        parts.append(p)
        consumed.update(p.primitive_ids)

    return parts
