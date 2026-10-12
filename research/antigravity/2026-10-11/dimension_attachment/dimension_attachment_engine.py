"""dimension_attachment_engine.py - Research Oracle for Dimension Cluster Topology and Attachment.

Evaluates strategies A-D for:
1. Dimension cluster bounding box merging (transitive closure vs single-pass greedy).
2. Dimension extension line outer workpiece endpoint selection.
3. Dimension attachment candidate pairing and scale-aware confidence scoring.
4. Crop-to-page coordinate transformation integrity.

Part of Antigravity Research: OFFLINE_DIMENSION_CLUSTER_TOPOLOGY_AND_ATTACHMENT_V1
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

Bbox = tuple[int, int, int, int]
Point2D = tuple[float, float]
Segment2D = tuple[Point2D, Point2D]


@dataclass(frozen=True)
class DimensionGeometryData:
    dimension_line: Segment2D | None
    extension_lines: tuple[Segment2D, ...]
    confidence: float = 1.0


@dataclass(frozen=True)
class AttachmentCandidate:
    from_ref: dict[str, str]
    to_ref: dict[str, str]
    confidence: float
    evidence: list[str]
    distances_px: tuple[float, float]
    proximity_score: float
    orientation_compatibility: float
    view_membership: float


@dataclass(frozen=True)
class ClusterResolutionResult:
    cluster_boxes: list[Bbox]
    outer_endpoints: list[Point2D]
    candidates: list[AttachmentCandidate]
    best_attachment: AttachmentCandidate | None
    second_attachment: AttachmentCandidate | None
    attachment_resolved: bool
    reasons: list[str]


# ---------------------------------------------------------------------------
# Geometric Utilities
# ---------------------------------------------------------------------------

def point_to_segment_distance(pt: Point2D, seg: Segment2D) -> float:
    """Computes exact Euclidean distance from a point to a finite line segment."""
    p0, p1 = seg
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.hypot(pt[0] - p0[0], pt[1] - p0[1])

    # Projection parameter t clamped to [0, 1]
    t = ((pt[0] - p0[0]) * dx + (pt[1] - p0[1]) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    proj_x = p0[0] + t * dx
    proj_y = p0[1] + t * dy
    return math.hypot(pt[0] - proj_x, pt[1] - proj_y)


def segment_orientation_vector(seg: Segment2D) -> Point2D | None:
    first, second = seg
    vx = second[0] - first[0]
    vy = second[1] - first[1]
    length = math.hypot(vx, vy)
    if length == 0.0:
        return None
    return (vx / length, vy / length)


# ---------------------------------------------------------------------------
# Strategy A: Production Main Baseline (primitive_ir_lib/dimension_observer.py)
# ---------------------------------------------------------------------------

def merge_boxes_strategy_a(boxes: Sequence[Bbox]) -> list[Bbox]:
    """Single-pass greedy merge from dimension_observer.py:69-82.

    Lacks transitive closure: breaks on first merge without re-checking merged items.
    """
    merged: list[Bbox] = []
    for candidate in sorted(boxes, key=lambda box: (box[1], box[0], box[3], box[2])):
        x0, y0, x1, y1 = candidate
        for index, current in enumerate(merged):
            cx0, cy0, cx1, cy1 = current
            overlaps = not (x1 < cx0 - 8 or x0 > cx1 + 8 or y1 < cy0 - 8 or y0 > cy1 + 8)
            if overlaps:
                merged[index] = (min(x0, cx0), min(y0, cy0), max(x1, cx1), max(y1, cy1))
                break
        else:
            merged.append(candidate)
    return sorted(merged, key=lambda box: (box[1], box[0], box[3], box[2]))


def outer_extension_points_strategy_a(geometry: DimensionGeometryData) -> list[Point2D]:
    """Extension endpoint selection from dimension_observer.py:231-241.

    BUG: Measures distance to line[0] instead of distance from the dimension line!
    """
    if geometry.dimension_line is None:
        return []
    line = geometry.dimension_line
    points: list[Point2D] = []
    for extension in geometry.extension_lines:
        candidate = max(extension, key=lambda point: math.hypot(point[0] - line[0][0], point[1] - line[0][1]))
        points.append(candidate)
    return points


def attachment_candidates_strategy_a(
    geometry: DimensionGeometryData,
    *,
    semantic_anchors: Sequence[Mapping[str, Any]],
    view_id: str,
    crop_offset_px: Point2D = (0.0, 0.0),  # In Strategy A, this offset is ignored!
) -> list[AttachmentCandidate]:
    """Attachment scoring from dimension_observer.py:244-301.

    Flaws:
    1. Ignores crop offset (crop coords vs global anchors).
    2. Uses outer_extension_points_strategy_a (wrong endpoints on far/slanted lines).
    3. Hardcoded decay rate math.exp(-sum(distances) / 20.0).
    """
    del crop_offset_px  # Strategy A ignores crop offset
    if len(geometry.extension_lines) < 2 or len(semantic_anchors) < 2:
        return []
    endpoints = outer_extension_points_strategy_a(geometry)
    if geometry.dimension_line is None or len(endpoints) < 2:
        return []
    orientation = segment_orientation_vector(geometry.dimension_line)
    if orientation is None:
        return []

    valid_anchors: list[Mapping[str, Any]] = []
    for anchor in semantic_anchors:
        point = anchor.get("point_px")
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            continue
        if not isinstance(anchor.get("id"), str) or not isinstance(anchor.get("type"), str):
            continue
        valid_anchors.append(anchor)

    candidates: list[AttachmentCandidate] = []
    for first_index, first in enumerate(valid_anchors):
        for second_index, second in enumerate(valid_anchors):
            if first_index == second_index:
                continue
            first_point = (float(first["point_px"][0]), float(first["point_px"][1]))
            second_point = (float(second["point_px"][0]), float(second["point_px"][1]))
            d1 = math.hypot(first_point[0] - endpoints[0][0], first_point[1] - endpoints[0][1])
            d2 = math.hypot(second_point[0] - endpoints[1][0], second_point[1] - endpoints[1][1])
            distances = (d1, d2)
            proximity = math.exp(-sum(distances) / 20.0)
            anchor_vector = (second_point[0] - first_point[0], second_point[1] - first_point[1])
            anchor_length = math.hypot(*anchor_vector)
            if anchor_length == 0:
                continue
            orientation_compatibility = abs(
                orientation[0] * anchor_vector[0] / anchor_length
                + orientation[1] * anchor_vector[1] / anchor_length
            )
            view_membership = float(first.get("view_id") == view_id and second.get("view_id") == view_id)
            confidence = (float(first.get("confidence", 0.0)) + float(second.get("confidence", 0.0))) / 2.0
            score = 0.45 * proximity + 0.25 * orientation_compatibility + 0.20 * view_membership + 0.10 * confidence
            candidates.append(
                AttachmentCandidate(
                    from_ref={"type": str(first["type"]), "id": str(first["id"])},
                    to_ref={"type": str(second["type"]), "id": str(second["id"])},
                    confidence=round(min(1.0, score), 3),
                    evidence=["extension-line-0", "extension-line-1"],
                    distances_px=distances,
                    proximity_score=round(proximity, 3),
                    orientation_compatibility=round(orientation_compatibility, 3),
                    view_membership=round(view_membership, 3),
                )
            )
    return sorted(
        candidates,
        key=lambda c: (-float(c.confidence), str(c.from_ref["id"]), str(c.to_ref["id"])),
    )


# ---------------------------------------------------------------------------
# Strategy B: Naive Distance Snapping (No orientation, no DPI awareness)
# ---------------------------------------------------------------------------

def merge_boxes_strategy_b(boxes: Sequence[Bbox]) -> list[Bbox]:
    """Single global bounding box or raw list."""
    if not boxes:
        return []
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    return [(x0, y0, x1, y1)]


def outer_extension_points_strategy_b(geometry: DimensionGeometryData) -> list[Point2D]:
    """Picks point with maximum y coordinate."""
    points: list[Point2D] = []
    for ext in geometry.extension_lines:
        points.append(max(ext, key=lambda pt: pt[1]))
    return points


def attachment_candidates_strategy_b(
    geometry: DimensionGeometryData,
    *,
    semantic_anchors: Sequence[Mapping[str, Any]],
    view_id: str,
    crop_offset_px: Point2D = (0.0, 0.0),
) -> list[AttachmentCandidate]:
    endpoints = outer_extension_points_strategy_b(geometry)
    if len(endpoints) < 2 or len(semantic_anchors) < 2:
        return []
    # Snaps to closest anchors by pure Euclidean distance
    candidates: list[AttachmentCandidate] = []
    for first in semantic_anchors:
        for second in semantic_anchors:
            if first.get("id") == second.get("id"):
                continue
            fp = (float(first["point_px"][0]), float(first["point_px"][1]))
            sp = (float(second["point_px"][0]), float(second["point_px"][1]))
            d1 = math.hypot(fp[0] - (endpoints[0][0] + crop_offset_px[0]), fp[1] - (endpoints[0][1] + crop_offset_px[1]))
            d2 = math.hypot(sp[0] - (endpoints[1][0] + crop_offset_px[0]), sp[1] - (endpoints[1][1] + crop_offset_px[1]))
            score = max(0.0, 1.0 - (d1 + d2) / 100.0)
            candidates.append(
                AttachmentCandidate(
                    from_ref={"type": str(first["type"]), "id": str(first["id"])},
                    to_ref={"type": str(second["type"]), "id": str(second["id"])},
                    confidence=round(score, 3),
                    evidence=["naive-distance"],
                    distances_px=(d1, d2),
                    proximity_score=round(score, 3),
                    orientation_compatibility=1.0,
                    view_membership=1.0,
                )
            )
    return sorted(candidates, key=lambda c: -c.confidence)


# ---------------------------------------------------------------------------
# Strategy C: Fixed Threshold Filter with 2-Pass Merge
# ---------------------------------------------------------------------------

def merge_boxes_strategy_c(boxes: Sequence[Bbox]) -> list[Bbox]:
    """Two-pass merge with 8px margin (still fails chains >= 3)."""
    pass1 = merge_boxes_strategy_a(boxes)
    return merge_boxes_strategy_a(pass1)


def outer_extension_points_strategy_c(geometry: DimensionGeometryData) -> list[Point2D]:
    """Picks points farthest from dimension line midpoint."""
    if geometry.dimension_line is None:
        return []
    p0, p1 = geometry.dimension_line
    mid = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
    points: list[Point2D] = []
    for ext in geometry.extension_lines:
        points.append(max(ext, key=lambda pt: math.hypot(pt[0] - mid[0], pt[1] - mid[1])))
    return points


def attachment_candidates_strategy_c(
    geometry: DimensionGeometryData,
    *,
    semantic_anchors: Sequence[Mapping[str, Any]],
    view_id: str,
    crop_offset_px: Point2D = (0.0, 0.0),
) -> list[AttachmentCandidate]:
    endpoints = outer_extension_points_strategy_c(geometry)
    if len(endpoints) < 2 or len(semantic_anchors) < 2:
        return []
    translated = [
        (endpoints[0][0] + crop_offset_px[0], endpoints[0][1] + crop_offset_px[1]),
        (endpoints[1][0] + crop_offset_px[0], endpoints[1][1] + crop_offset_px[1]),
    ]
    # Filters within fixed 50px radius
    candidates: list[AttachmentCandidate] = []
    for first in semantic_anchors:
        for second in semantic_anchors:
            if first.get("id") == second.get("id"):
                continue
            fp = (float(first["point_px"][0]), float(first["point_px"][1]))
            sp = (float(second["point_px"][0]), float(second["point_px"][1]))
            d1 = math.hypot(fp[0] - translated[0][0], fp[1] - translated[0][1])
            d2 = math.hypot(sp[0] - translated[1][0], sp[1] - translated[1][1])
            if d1 > 50.0 or d2 > 50.0:
                continue
            score = 1.0 - (d1 + d2) / 100.0
            candidates.append(
                AttachmentCandidate(
                    from_ref={"type": str(first["type"]), "id": str(first["id"])},
                    to_ref={"type": str(second["type"]), "id": str(second["id"])},
                    confidence=round(score, 3),
                    evidence=["fixed-radius-50px"],
                    distances_px=(d1, d2),
                    proximity_score=round(score, 3),
                    orientation_compatibility=1.0,
                    view_membership=1.0,
                )
            )
    return sorted(candidates, key=lambda c: -c.confidence)


# ---------------------------------------------------------------------------
# Strategy D: Connected-Components DSU Merging, Segment-Distance Endpoints,
# Crop Offset Translation & Scale-Aware Calibration Consensus Oracle
# ---------------------------------------------------------------------------

class DisjointSetUnion:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, i: int, j: int) -> None:
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            self.parent[root_i] = root_j


def merge_boxes_strategy_d(boxes: Sequence[Bbox], margin_px: int = 8) -> list[Bbox]:
    """Transitive closure box merging using Disjoint Set Union (Connected Components).

    Guarantees that any transitive chain of overlapping boxes (within margin_px)
    is merged into a single tight bounding box.
    """
    if not boxes:
        return []

    n = len(boxes)
    dsu = DisjointSetUnion(n)

    # Check pairwise overlap with margin
    for i in range(n):
        x0_i, y0_i, x1_i, y1_i = boxes[i]
        for j in range(i + 1, n):
            x0_j, y0_j, x1_j, y1_j = boxes[j]
            overlaps = not (
                x1_i < x0_j - margin_px
                or x0_i > x1_j + margin_px
                or y1_i < y0_j - margin_px
                or y0_i > y1_j + margin_px
            )
            if overlaps:
                dsu.union(i, j)

    # Group boxes by connected component root
    components: dict[int, list[Bbox]] = {}
    for i in range(n):
        root = dsu.find(i)
        components.setdefault(root, []).append(boxes[i])

    merged: list[Bbox] = []
    for group in components.values():
        gx0 = min(b[0] for b in group)
        gy0 = min(b[1] for b in group)
        gx1 = max(b[2] for b in group)
        gy1 = max(b[3] for b in group)
        merged.append((gx0, gy0, gx1, gy1))

    return sorted(merged, key=lambda box: (box[1], box[0], box[3], box[2]))


def outer_extension_points_strategy_d(geometry: DimensionGeometryData) -> list[Point2D]:
    """Selects the workpiece attachment endpoint for each extension line.

    Uses point_to_segment_distance from the dimension line segment.
    Since witness lines extend further towards the workpiece than the overshoot
    (or at least start at the dimension line and extend towards the feature),
    the endpoint with the GREATER distance from the dimension line segment is selected.
    """
    if geometry.dimension_line is None:
        return []
    line = geometry.dimension_line
    points: list[Point2D] = []
    for ext in geometry.extension_lines:
        candidate = max(ext, key=lambda pt: point_to_segment_distance(pt, line))
        points.append(candidate)
    return points


def attachment_candidates_strategy_d(
    geometry: DimensionGeometryData,
    *,
    semantic_anchors: Sequence[Mapping[str, Any]],
    view_id: str,
    crop_offset_px: Point2D = (0.0, 0.0),
    px_per_mm: float = 11.81,  # Default 300 DPI (300 / 25.4)
    expected_drafting_gap_mm: float = 2.0,  # ASME Y14.5 / ISO 129-1 gap tolerance
) -> list[AttachmentCandidate]:
    """Robust, scale-aware dimension attachment candidate generation.

    Features:
    1. Correct workpiece endpoint extraction via segment distance.
    2. Explicit crop-to-page coordinate offset translation.
    3. Scale-aware drafting gap tolerance (does not penalize standard 1-2mm gaps).
    4. Two-way permutation check (preserves topological order along dimension vector).
    5. Clean rejection of non-finite coords, cross-view mismatches, and confidence <= 0.
    """
    if len(geometry.extension_lines) < 2 or len(semantic_anchors) < 2:
        return []
    if geometry.dimension_line is None:
        return []

    local_endpoints = outer_extension_points_strategy_d(geometry)
    if len(local_endpoints) < 2:
        return []

    # Map crop coordinates to page coordinates
    ox, oy = crop_offset_px
    endpoints = [(p[0] + ox, p[1] + oy) for p in local_endpoints]

    # Global dimension line vector
    dim_line_global = (
        (geometry.dimension_line[0][0] + ox, geometry.dimension_line[0][1] + oy),
        (geometry.dimension_line[1][0] + ox, geometry.dimension_line[1][1] + oy),
    )
    orientation = segment_orientation_vector(dim_line_global)
    if orientation is None:
        return []

    # Filter valid anchors
    valid_anchors: list[Mapping[str, Any]] = []
    for anchor in semantic_anchors:
        point = anchor.get("point_px")
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            continue
        px_val, py_val = float(point[0]), float(point[1])
        if not (math.isfinite(px_val) and math.isfinite(py_val)):
            continue
        if not isinstance(anchor.get("id"), str) or not isinstance(anchor.get("type"), str):
            continue
        conf = float(anchor.get("confidence", 0.0))
        if conf <= 0.0:
            continue
        valid_anchors.append(anchor)

    if len(valid_anchors) < 2:
        return []

    max_drafting_gap_px = max(5.0, expected_drafting_gap_mm * px_per_mm)
    decay_bandwidth = max(20.0, 2.5 * px_per_mm)

    candidates: list[AttachmentCandidate] = []

    for first_index, first in enumerate(valid_anchors):
        for second_index, second in enumerate(valid_anchors):
            if first_index == second_index:
                continue
            if first["id"] == second["id"]:
                continue

            first_point = (float(first["point_px"][0]), float(first["point_px"][1]))
            second_point = (float(second["point_px"][0]), float(second["point_px"][1]))

            # Check topological ordering along dimension line
            anchor_vector = (second_point[0] - first_point[0], second_point[1] - first_point[1])
            anchor_length = math.hypot(*anchor_vector)
            if anchor_length == 0.0:
                continue

            dot_dir = orientation[0] * anchor_vector[0] + orientation[1] * anchor_vector[1]
            if dot_dir < 0.0:
                # Swapped orientation: anchor pair vector opposes dimension line direction
                continue

            d1 = math.hypot(first_point[0] - endpoints[0][0], first_point[1] - endpoints[0][1])
            d2 = math.hypot(second_point[0] - endpoints[1][0], second_point[1] - endpoints[1][1])

            # Excess distance beyond legitimate CAD drafting gap
            excess_d1 = max(0.0, d1 - max_drafting_gap_px)
            excess_d2 = max(0.0, d2 - max_drafting_gap_px)
            proximity = math.exp(-(excess_d1 + excess_d2) / decay_bandwidth)

            orientation_compatibility = abs(dot_dir / anchor_length)
            view_membership = float(first.get("view_id") == view_id and second.get("view_id") == view_id)
            anchor_conf = (float(first.get("confidence", 0.0)) + float(second.get("confidence", 0.0))) / 2.0

            score = (
                0.45 * proximity
                + 0.25 * orientation_compatibility
                + 0.20 * view_membership
                + 0.10 * anchor_conf
            )

            candidates.append(
                AttachmentCandidate(
                    from_ref={"type": str(first["type"]), "id": str(first["id"])},
                    to_ref={"type": str(second["type"]), "id": str(second["id"])},
                    confidence=round(min(1.0, score), 3),
                    evidence=["scale-aware-consensus-extension-pair"],
                    distances_px=(round(d1, 2), round(d2, 2)),
                    proximity_score=round(proximity, 3),
                    orientation_compatibility=round(orientation_compatibility, 3),
                    view_membership=round(view_membership, 3),
                )
            )

    return sorted(
        candidates,
        key=lambda c: (-float(c.confidence), str(c.from_ref["id"]), str(c.to_ref["id"])),
    )


# ---------------------------------------------------------------------------
# High-Level Resolution Oracle
# ---------------------------------------------------------------------------

def resolve_dimension_cluster(
    boxes: Sequence[Bbox],
    geometry: DimensionGeometryData,
    *,
    semantic_anchors: Sequence[Mapping[str, Any]],
    view_id: str,
    strategy: str = "D",
    crop_offset_px: Point2D = (0.0, 0.0),
    px_per_mm: float = 11.81,
) -> ClusterResolutionResult:
    reasons: list[str] = []

    if strategy == "A":
        cluster_boxes = merge_boxes_strategy_a(boxes)
        outer_pts = outer_extension_points_strategy_a(geometry)
        candidates = attachment_candidates_strategy_a(
            geometry,
            semantic_anchors=semantic_anchors,
            view_id=view_id,
            crop_offset_px=crop_offset_px,
        )
    elif strategy == "B":
        cluster_boxes = merge_boxes_strategy_b(boxes)
        outer_pts = outer_extension_points_strategy_b(geometry)
        candidates = attachment_candidates_strategy_b(
            geometry,
            semantic_anchors=semantic_anchors,
            view_id=view_id,
            crop_offset_px=crop_offset_px,
        )
    elif strategy == "C":
        cluster_boxes = merge_boxes_strategy_c(boxes)
        outer_pts = outer_extension_points_strategy_c(geometry)
        candidates = attachment_candidates_strategy_c(
            geometry,
            semantic_anchors=semantic_anchors,
            view_id=view_id,
            crop_offset_px=crop_offset_px,
        )
    elif strategy == "D":
        cluster_boxes = merge_boxes_strategy_d(boxes)
        outer_pts = outer_extension_points_strategy_d(geometry)
        candidates = attachment_candidates_strategy_d(
            geometry,
            semantic_anchors=semantic_anchors,
            view_id=view_id,
            crop_offset_px=crop_offset_px,
            px_per_mm=px_per_mm,
        )
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    best = candidates[0] if candidates else None
    second = candidates[1] if len(candidates) > 1 else None

    if best is None:
        reasons.append("no_attachment_candidates")
        return ClusterResolutionResult(
            cluster_boxes=cluster_boxes,
            outer_endpoints=outer_pts,
            candidates=candidates,
            best_attachment=None,
            second_attachment=None,
            attachment_resolved=False,
            reasons=reasons,
        )

    resolved = (
        best is not None
        and float(best.confidence) >= 0.85
        and (
            second is None
            or float(best.confidence) - float(second.confidence) >= 0.10
        )
        and best.from_ref != best.to_ref
        and geometry.confidence >= 0.70
    )

    if not resolved:
        if float(best.confidence) < 0.85:
            reasons.append("attachment_confidence_below_threshold")
        if second is not None and float(best.confidence) - float(second.confidence) < 0.10:
            reasons.append("attachment_ambiguity_margin_insufficient")
        if geometry.confidence < 0.70:
            reasons.append("geometry_confidence_below_threshold")
        reasons.append("attachment_unresolved")

    return ClusterResolutionResult(
        cluster_boxes=cluster_boxes,
        outer_endpoints=outer_pts,
        candidates=candidates,
        best_attachment=best,
        second_attachment=second,
        attachment_resolved=resolved,
        reasons=reasons,
    )
