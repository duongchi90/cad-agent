"""Robust Multi-View Orthographic Projection Alignment Engine (Research Only).

Empirical reference engine for:
- 1D coordinate interval alignment verification across orthographic drawing views.
- Feature edge ray tracing across horizontal and vertical projection paths.
- ISO 5456-2 (First Angle) vs ASME Y14.3 (Third Angle) projection system consensus.
- 45-degree miter depth correspondence between Plan (Top) and Elevation (Side) views.
- Geometric compatibility guards for multi-view component binding.
- Detection and rejection of inverted, transposed, or geometrically contradictory view layouts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Iterable, List, Optional, Set, Tuple


@dataclass(frozen=True)
class ViewPrimitive:
    """A geometric primitive situated in a 2D drawing view."""
    primitive_id: str
    primitive_type: str  # "LINE", "CIRCLE", "ARC"
    start: Tuple[float, float]
    end: Tuple[float, float]
    center: Optional[Tuple[float, float]] = None
    radius: Optional[float] = None
    layer: str = "0"

    def is_horizontal(self, tol: float = 1e-3) -> bool:
        if self.primitive_type == "LINE":
            return abs(self.start[1] - self.end[1]) <= tol
        return False

    def is_vertical(self, tol: float = 1e-3) -> bool:
        if self.primitive_type == "LINE":
            return abs(self.start[0] - self.end[0]) <= tol
        return False


@dataclass
class ViewRegion:
    """A bounded drawing region representing an orthographic or detail view."""
    view_id: str
    view_role: str = "UNKNOWN"  # "FRONT", "TOP", "RIGHT_SIDE", "LEFT_SIDE", "BOTTOM", "REAR", "ISOMETRIC", "UNKNOWN"
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # (xmin, ymin, xmax, ymax) in raw drawing units
    scale: float = 1.0  # drawing scale (e.g., 1.0 for 1:1, 0.5 for 1:2)
    primitives: List[ViewPrimitive] = field(default_factory=list)
    component_ids: List[str] = field(default_factory=list)
    semantic_projection_refs: List[str] = field(default_factory=list)
    layout_bindings: List[dict] = field(default_factory=list)

    @property
    def raw_width(self) -> float:
        return max(0.0, self.bbox[2] - self.bbox[0])

    @property
    def raw_height(self) -> float:
        return max(0.0, self.bbox[3] - self.bbox[1])

    @property
    def norm_width(self) -> float:
        s = self.scale if self.scale > 0.0 else 1.0
        return self.raw_width / s

    @property
    def norm_height(self) -> float:
        s = self.scale if self.scale > 0.0 else 1.0
        return self.raw_height / s

    @property
    def norm_bbox(self) -> Tuple[float, float, float, float]:
        s = self.scale if self.scale > 0.0 else 1.0
        return (self.bbox[0] / s, self.bbox[1] / s, self.bbox[2] / s, self.bbox[3] / s)

    @property
    def centroid(self) -> Tuple[float, float]:
        return ((self.bbox[0] + self.bbox[2]) / 2.0, (self.bbox[1] + self.bbox[3]) / 2.0)


@dataclass(frozen=True)
class AlignmentLink:
    """A verified structural relationship between two drawing views."""
    link_id: str
    relation_type: str
    source_id: str
    target_id: str
    evidence_refs: List[str] = field(default_factory=list)
    confidence: float = 1.0
    projection_system: str = "INDETERMINATE"
    diagnostics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "link_id": self.link_id,
            "relation_type": self.relation_type,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "evidence_refs": sorted(self.evidence_refs),
            "confidence": round(self.confidence, 4),
            "projection_system": self.projection_system,
            "diagnostics": self.diagnostics,
        }


def _make_link_id(relation_type: str, source_id: str, target_id: str, evidence: List[str]) -> str:
    src, tgt = sorted((source_id, target_id))
    payload = f"{relation_type}:{src}:{tgt}:{','.join(sorted(evidence))}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Strategy A: Current Production Baseline (component_view_registry.py _derive_links)
# ---------------------------------------------------------------------------

def run_strategy_a(views: List[ViewRegion]) -> List[AlignmentLink]:
    """Replicates cad_agent/component_view_registry.py _derive_links logic."""
    links: List[AlignmentLink] = []

    # View presented on layout links are intra-view/layout, focus on view-view pairs:
    for index, left in enumerate(views):
        left_id = str(left.view_id)
        for right in views[index + 1 :]:
            right_id = str(right.view_id)
            source_id, target_id = sorted((left_id, right_id))
            
            # 1. Component sharing: strict set intersection on string IDs
            if set(left.component_ids) & set(right.component_ids):
                link_id = _make_link_id("VIEWS_SHARE_COMPONENT", source_id, target_id, [])
                links.append(
                    AlignmentLink(
                        link_id=link_id,
                        relation_type="VIEWS_SHARE_COMPONENT",
                        source_id=source_id,
                        target_id=target_id,
                        evidence_refs=[],
                        confidence=1.0,
                        projection_system="INDETERMINATE",
                        diagnostics={"method": "STRATEGY_A_SET_INTERSECTION"},
                    )
                )

            # 2. Parameter evidence sharing: strict set intersection on string IDs
            shared_evidence = sorted(
                set(left.semantic_projection_refs) & set(right.semantic_projection_refs)
            )
            if shared_evidence:
                link_id = _make_link_id("VIEWS_SHARE_PARAMETER_EVIDENCE", source_id, target_id, shared_evidence)
                links.append(
                    AlignmentLink(
                        link_id=link_id,
                        relation_type="VIEWS_SHARE_PARAMETER_EVIDENCE",
                        source_id=source_id,
                        target_id=target_id,
                        evidence_refs=shared_evidence,
                        confidence=1.0,
                        projection_system="INDETERMINATE",
                        diagnostics={"method": "STRATEGY_A_EVIDENCE_INTERSECTION"},
                    )
                )

    links.sort(key=lambda link: (link.relation_type, link.source_id, link.target_id))
    return links


# ---------------------------------------------------------------------------
# Strategy B: Naive Bounding-Box Proximity Matcher
# ---------------------------------------------------------------------------

def run_strategy_b(views: List[ViewRegion], max_proximity_mm: float = 350.0) -> List[AlignmentLink]:
    """Clusters views based solely on Euclidean distance between bounding box centroids."""
    links: List[AlignmentLink] = []

    for index, left in enumerate(views):
        left_id = str(left.view_id)
        c_left = left.centroid
        for right in views[index + 1 :]:
            right_id = str(right.view_id)
            c_right = right.centroid
            dist = math.hypot(c_left[0] - c_right[0], c_left[1] - c_right[1])
            source_id, target_id = sorted((left_id, right_id))

            if dist <= max_proximity_mm:
                link_id = _make_link_id("VIEWS_PROXIMITY_CLUSTER", source_id, target_id, [])
                links.append(
                    AlignmentLink(
                        link_id=link_id,
                        relation_type="VIEWS_SHARE_COMPONENT",
                        source_id=source_id,
                        target_id=target_id,
                        evidence_refs=[],
                        confidence=max(0.1, 1.0 - (dist / max_proximity_mm)),
                        projection_system="INDETERMINATE",
                        diagnostics={"method": "STRATEGY_B_PROXIMITY", "distance": dist},
                    )
                )

    links.sort(key=lambda link: (link.relation_type, link.source_id, link.target_id))
    return links


# ---------------------------------------------------------------------------
# Strategy C: Axis-Aligned Interval Overlap Matcher
# ---------------------------------------------------------------------------

def run_strategy_c(views: List[ViewRegion]) -> List[AlignmentLink]:
    """Matches views if their raw 1D bounding box coordinate intervals overlap."""
    links: List[AlignmentLink] = []

    for index, left in enumerate(views):
        left_id = str(left.view_id)
        b_left = left.bbox
        for right in views[index + 1 :]:
            right_id = str(right.view_id)
            b_right = right.bbox
            source_id, target_id = sorted((left_id, right_id))

            # Y-overlap: [ymin1, ymax1] overlaps [ymin2, ymax2]
            y_overlap = max(0.0, min(b_left[3], b_right[3]) - max(b_left[1], b_right[1]))
            # X-overlap: [xmin1, xmax1] overlaps [xmin2, xmax2]
            x_overlap = max(0.0, min(b_left[2], b_right[2]) - max(b_left[0], b_right[0]))

            if y_overlap > 10.0:
                link_id = _make_link_id("VIEWS_ALIGNED_HORIZONTALLY", source_id, target_id, [])
                links.append(
                    AlignmentLink(
                        link_id=link_id,
                        relation_type="VIEWS_ALIGNED_HORIZONTALLY",
                        source_id=source_id,
                        target_id=target_id,
                        evidence_refs=[],
                        confidence=0.7,
                        projection_system="INDETERMINATE",
                        diagnostics={"method": "STRATEGY_C_Y_OVERLAP", "overlap": y_overlap},
                    )
                )

            if x_overlap > 10.0:
                link_id = _make_link_id("VIEWS_ALIGNED_VERTICALLY", source_id, target_id, [])
                links.append(
                    AlignmentLink(
                        link_id=link_id,
                        relation_type="VIEWS_ALIGNED_VERTICALLY",
                        source_id=source_id,
                        target_id=target_id,
                        evidence_refs=[],
                        confidence=0.7,
                        projection_system="INDETERMINATE",
                        diagnostics={"method": "STRATEGY_C_X_OVERLAP", "overlap": x_overlap},
                    )
                )

    links.sort(key=lambda link: (link.relation_type, link.source_id, link.target_id))
    return links


# ---------------------------------------------------------------------------
# Strategy D: Robust Multi-View Orthographic Projection Alignment Engine
# ---------------------------------------------------------------------------

class OrthographicAlignmentEngine:
    """Robust multi-view alignment engine enforcing CAD geometric invariants."""

    def __init__(
        self,
        span_relative_tolerance: float = 0.03,      # 3.0% maximum span deviation
        baseline_tolerance_mm: float = 2.0,          # 2.0 mm baseline alignment tolerance
        ray_coincidence_tolerance_mm: float = 1.5,   # 1.5 mm tolerance for feature projection ray matching
        min_feature_ray_support: float = 0.30,      # minimum 30% feature ray correspondence for high confidence
        depth_miter_tolerance: float = 0.03,         # 3.0% maximum depth mismatch between Top & Side views
    ):
        self.span_relative_tolerance = span_relative_tolerance
        self.baseline_tolerance_mm = baseline_tolerance_mm
        self.ray_coincidence_tolerance_mm = ray_coincidence_tolerance_mm
        self.min_feature_ray_support = min_feature_ray_support
        self.depth_miter_tolerance = depth_miter_tolerance

    def analyze(
        self, views: List[ViewRegion], declared_projection_system: Optional[str] = None
    ) -> dict:
        """Performs full orthographic alignment, projection inference, and consistency checks."""
        # Clean and validate input views
        valid_views = [v for v in views if self._validate_view(v)]
        
        incompatibilities: List[str] = []
        links: List[AlignmentLink] = []
        projection_votes: List[str] = []

        # 1. Pairwise orthographic alignment analysis
        for i, left in enumerate(valid_views):
            left_id = str(left.view_id)
            for right in valid_views[i + 1 :]:
                right_id = str(right.view_id)
                source_id, target_id = sorted((left_id, right_id))

                # Check horizontal elevation-side alignment (shared vertical span / height)
                h_link = self._check_horizontal_alignment(left, right, source_id, target_id)
                if h_link is not None:
                    links.append(h_link)
                    if h_link.projection_system in ("THIRD_ANGLE", "FIRST_ANGLE"):
                        projection_votes.append(h_link.projection_system)

                # Check vertical elevation-plan alignment (shared horizontal span / width)
                v_link = self._check_vertical_alignment(left, right, source_id, target_id)
                if v_link is not None:
                    links.append(v_link)
                    if v_link.projection_system in ("THIRD_ANGLE", "FIRST_ANGLE"):
                        projection_votes.append(v_link.projection_system)

                # Check 45-degree miter depth correspondence (Plan Depth vs Side Depth)
                d_link = self._check_depth_correspondence(left, right, source_id, target_id)
                if d_link is not None:
                    links.append(d_link)

                # Check geometric compatibility for declared component sharing
                compat_issue = self._check_component_compatibility(left, right)
                if compat_issue:
                    incompatibilities.append(compat_issue)
                elif set(left.component_ids) & set(right.component_ids):
                    # Validated component sharing
                    links.append(
                        AlignmentLink(
                            link_id=_make_link_id("VIEWS_SHARE_COMPONENT", source_id, target_id, []),
                            relation_type="VIEWS_SHARE_COMPONENT",
                            source_id=source_id,
                            target_id=target_id,
                            evidence_refs=[],
                            confidence=1.0,
                            projection_system="INDETERMINATE",
                            diagnostics={"status": "GEOMETRICALLY_COMPATIBLE"},
                        )
                    )

                # Retain validated semantic parameter evidence sharing
                shared_evidence = sorted(
                    set(left.semantic_projection_refs) & set(right.semantic_projection_refs)
                )
                if shared_evidence:
                    links.append(
                        AlignmentLink(
                            link_id=_make_link_id("VIEWS_SHARE_PARAMETER_EVIDENCE", source_id, target_id, shared_evidence),
                            relation_type="VIEWS_SHARE_PARAMETER_EVIDENCE",
                            source_id=source_id,
                            target_id=target_id,
                            evidence_refs=shared_evidence,
                            confidence=1.0,
                            projection_system="INDETERMINATE",
                            diagnostics={"evidence_count": len(shared_evidence)},
                        )
                    )

        # 2. Global projection system consensus and contradiction detection
        count_third = projection_votes.count("THIRD_ANGLE")
        count_first = projection_votes.count("FIRST_ANGLE")

        if declared_projection_system in ("THIRD_ANGLE", "FIRST_ANGLE"):
            system_consensus = declared_projection_system
            if declared_projection_system == "THIRD_ANGLE" and count_first > 0:
                incompatibilities.append(
                    f"ROLE_LAYOUT_INVERSION_REJECTED: layout contains {count_first} FIRST_ANGLE votes contradicting declared THIRD_ANGLE"
                )
            elif declared_projection_system == "FIRST_ANGLE" and count_third > 0:
                incompatibilities.append(
                    f"ROLE_LAYOUT_INVERSION_REJECTED: layout contains {count_third} THIRD_ANGLE votes contradicting declared FIRST_ANGLE"
                )
        else:
            if count_third > 0 and count_first > 0:
                incompatibilities.append(
                    f"PROJECTION_SYSTEM_CONTRADICTION_REJECTED: contradictory projection votes THIRD_ANGLE={count_third} and FIRST_ANGLE={count_first}"
                )
            system_consensus = self._resolve_projection_consensus(projection_votes)

        # 3. Role layout consistency and inversion guard
        role_issues = self._verify_role_layout_consistency(valid_views, system_consensus)
        incompatibilities.extend(role_issues)

        # 4. Synthesize high-order orthographic projection pair links
        pair_links = self._synthesize_projection_pairs(valid_views, links, system_consensus)
        links.extend(pair_links)

        links.sort(key=lambda link: (link.relation_type, link.source_id, link.target_id))

        return {
            "valid": len(incompatibilities) == 0,
            "incompatibilities": sorted(incompatibilities),
            "inferred_projection_system": system_consensus,
            "links": links,
            "view_count": len(valid_views),
        }

    def _validate_view(self, view: ViewRegion) -> bool:
        if not view.view_id:
            return False
        b = view.bbox
        if any(math.isnan(c) or math.isinf(c) for c in b):
            return False
        if b[2] <= b[0] or b[3] <= b[1]:
            return False
        if view.scale <= 0.0 or math.isnan(view.scale) or math.isinf(view.scale):
            return False
        return True

    def _check_horizontal_alignment(
        self, v1: ViewRegion, v2: ViewRegion, source_id: str, target_id: str
    ) -> Optional[AlignmentLink]:
        """Tests if two views share height and vertical coordinate span within tolerance."""
        # First ensure they are horizontally displaced (side-by-side, not stacked)
        b1, b2 = v1.norm_bbox, v2.norm_bbox
        # Horizontal separation: one view is left of the other
        x_overlap = max(0.0, min(b1[2], b2[2]) - max(b1[0], b2[0]))
        min_width = min(v1.norm_width, v2.norm_width)
        if x_overlap > 0.5 * min_width:
            # Views heavily overlap in X; they are stacked or overlapping, not horizontal elevation-side views
            return None

        h1, h2 = v1.norm_height, v2.norm_height
        if h1 <= 0.0 or h2 <= 0.0:
            return None

        # Check relative height error
        delta_h = abs(h1 - h2)
        rel_h_error = delta_h / min(h1, h2)
        if rel_h_error > self.span_relative_tolerance:
            return None

        # Check baseline alignment: delta_ymin and delta_ymax
        delta_ymin = abs(b1[1] - b2[1])
        delta_ymax = abs(b1[3] - b2[3])
        if delta_ymin > self.baseline_tolerance_mm and delta_ymax > self.baseline_tolerance_mm:
            return None

        # Feature ray tracing for horizontal rays
        ray_support, matched_rays, total_rays = self._trace_horizontal_rays(v1, v2)

        # Projection direction determination
        # Front is reference if known; otherwise check left-to-right
        system = "INDETERMINATE"
        v_left = v1 if b1[0] < b2[0] else v2
        v_right = v2 if b1[0] < b2[0] else v1

        if v_left.view_role == "FRONT" and v_right.view_role in ("RIGHT_SIDE", "SIDE"):
            system = "THIRD_ANGLE"
        elif v_left.view_role in ("RIGHT_SIDE", "SIDE") and v_right.view_role == "FRONT":
            system = "FIRST_ANGLE"
        elif v_left.view_role in ("LEFT_SIDE",) and v_right.view_role == "FRONT":
            system = "THIRD_ANGLE"
        elif v_left.view_role == "FRONT" and v_right.view_role in ("LEFT_SIDE",):
            system = "FIRST_ANGLE"

        confidence = max(0.5, min(1.0, 1.0 - rel_h_error + 0.2 * ray_support))

        return AlignmentLink(
            link_id=_make_link_id("VIEWS_ALIGNED_HORIZONTALLY", source_id, target_id, []),
            relation_type="VIEWS_ALIGNED_HORIZONTALLY",
            source_id=source_id,
            target_id=target_id,
            evidence_refs=[],
            confidence=confidence,
            projection_system=system,
            diagnostics={
                "height_delta_mm": round(delta_h, 3),
                "relative_height_error": round(rel_h_error, 4),
                "baseline_delta_mm": round(delta_ymin, 3),
                "horizontal_ray_support": round(ray_support, 4),
                "matched_rays": matched_rays,
                "total_rays": total_rays,
            },
        )

    def _check_vertical_alignment(
        self, v1: ViewRegion, v2: ViewRegion, source_id: str, target_id: str
    ) -> Optional[AlignmentLink]:
        """Tests if two views share width and horizontal coordinate span within tolerance."""
        b1, b2 = v1.norm_bbox, v2.norm_bbox
        # Vertical separation: one view is above the other
        y_overlap = max(0.0, min(b1[3], b2[3]) - max(b1[1], b2[1]))
        min_height = min(v1.norm_height, v2.norm_height)
        if y_overlap > 0.5 * min_height:
            # Views heavily overlap in Y; they are side-by-side or overlapping, not vertically stacked
            return None

        w1, w2 = v1.norm_width, v2.norm_width
        if w1 <= 0.0 or w2 <= 0.0:
            return None

        # Check relative width error
        delta_w = abs(w1 - w2)
        rel_w_error = delta_w / min(w1, w2)
        if rel_w_error > self.span_relative_tolerance:
            return None

        # Check baseline alignment: delta_xmin and delta_xmax
        delta_xmin = abs(b1[0] - b2[0])
        delta_xmax = abs(b1[2] - b2[2])
        if delta_xmin > self.baseline_tolerance_mm and delta_xmax > self.baseline_tolerance_mm:
            return None

        # Feature ray tracing for vertical rays
        ray_support, matched_rays, total_rays = self._trace_vertical_rays(v1, v2)

        # Projection direction determination
        system = "INDETERMINATE"
        v_bottom = v1 if b1[1] < b2[1] else v2
        v_top = v2 if b1[1] < b2[1] else v1

        if v_bottom.view_role == "FRONT" and v_top.view_role in ("TOP", "PLAN"):
            system = "THIRD_ANGLE"
        elif v_top.view_role == "FRONT" and v_bottom.view_role in ("TOP", "PLAN"):
            system = "FIRST_ANGLE"
        elif v_bottom.view_role in ("BOTTOM",) and v_top.view_role == "FRONT":
            system = "FIRST_ANGLE"
        elif v_top.view_role in ("BOTTOM",) and v_bottom.view_role == "FRONT":
            system = "THIRD_ANGLE"

        confidence = max(0.5, min(1.0, 1.0 - rel_w_error + 0.2 * ray_support))

        return AlignmentLink(
            link_id=_make_link_id("VIEWS_ALIGNED_VERTICALLY", source_id, target_id, []),
            relation_type="VIEWS_ALIGNED_VERTICALLY",
            source_id=source_id,
            target_id=target_id,
            evidence_refs=[],
            confidence=confidence,
            projection_system=system,
            diagnostics={
                "width_delta_mm": round(delta_w, 3),
                "relative_width_error": round(rel_w_error, 4),
                "baseline_delta_mm": round(delta_xmin, 3),
                "vertical_ray_support": round(ray_support, 4),
                "matched_rays": matched_rays,
                "total_rays": total_rays,
            },
        )

    def _check_depth_correspondence(
        self, v1: ViewRegion, v2: ViewRegion, source_id: str, target_id: str
    ) -> Optional[AlignmentLink]:
        """Tests 45-degree miter depth correspondence between Plan (Top) and Elevation (Side)."""
        roles = {v1.view_role, v2.view_role}
        top_view = v1 if v1.view_role in ("TOP", "PLAN") else (v2 if v2.view_role in ("TOP", "PLAN") else None)
        side_view = v1 if v1.view_role in ("SIDE", "RIGHT_SIDE", "LEFT_SIDE") else (
            v2 if v2.view_role in ("SIDE", "RIGHT_SIDE", "LEFT_SIDE") else None
        )

        # If roles not explicitly known, check if one can serve as Top and other as Side
        if top_view is None or side_view is None:
            # Test hypothesis: v1 is Top (depth is height), v2 is Side (depth is width)
            d1_top = v1.norm_height
            d2_side = v2.norm_width
            err1 = abs(d1_top - d2_side) / max(1e-6, min(d1_top, d2_side))

            d2_top = v2.norm_height
            d1_side = v1.norm_width
            err2 = abs(d2_top - d1_side) / max(1e-6, min(d2_top, d1_side))

            if err1 <= self.depth_miter_tolerance and err1 < err2:
                top_depth = d1_top
                side_depth = d2_side
                err = err1
            elif err2 <= self.depth_miter_tolerance:
                top_depth = d2_top
                side_depth = d1_side
                err = err2
            else:
                return None
        else:
            top_depth = top_view.norm_height
            side_depth = side_view.norm_width
            err = abs(top_depth - side_depth) / max(1e-6, min(top_depth, side_depth))
            if err > self.depth_miter_tolerance:
                return None

        confidence = max(0.6, 1.0 - err)
        return AlignmentLink(
            link_id=_make_link_id("VIEWS_DEPTH_CORRESPONDENCE", source_id, target_id, []),
            relation_type="VIEWS_DEPTH_CORRESPONDENCE",
            source_id=source_id,
            target_id=target_id,
            evidence_refs=[],
            confidence=confidence,
            projection_system="INDETERMINATE",
            diagnostics={
                "top_depth_mm": round(top_depth, 3),
                "side_depth_mm": round(side_depth, 3),
                "depth_delta_mm": round(abs(top_depth - side_depth), 3),
                "relative_depth_error": round(err, 4),
            },
        )

    def _trace_horizontal_rays(
        self, v1: ViewRegion, v2: ViewRegion
    ) -> Tuple[float, int, int]:
        """Traces horizontal projection rays between corresponding horizontal feature edges."""
        s1 = v1.scale if v1.scale > 0.0 else 1.0
        s2 = v2.scale if v2.scale > 0.0 else 1.0

        # Extract unique Y levels of horizontal lines
        y_levels_1 = {round((p.start[1] + p.end[1]) / (2.0 * s1), 2) for p in v1.primitives if p.is_horizontal()}
        # Also include top and bottom boundaries
        y_levels_1.add(round(v1.norm_bbox[1], 2))
        y_levels_1.add(round(v1.norm_bbox[3], 2))

        y_levels_2 = {round((p.start[1] + p.end[1]) / (2.0 * s2), 2) for p in v2.primitives if p.is_horizontal()}
        y_levels_2.add(round(v2.norm_bbox[1], 2))
        y_levels_2.add(round(v2.norm_bbox[3], 2))

        if not y_levels_1 or not y_levels_2:
            return 0.0, 0, 0

        matched = 0
        for y1 in y_levels_1:
            if any(abs(y1 - y2) <= self.ray_coincidence_tolerance_mm for y2 in y_levels_2):
                matched += 1

        total = len(y_levels_1)
        support = matched / total if total > 0 else 0.0
        return support, matched, total

    def _trace_vertical_rays(
        self, v1: ViewRegion, v2: ViewRegion
    ) -> Tuple[float, int, int]:
        """Traces vertical projection rays between corresponding vertical feature edges."""
        s1 = v1.scale if v1.scale > 0.0 else 1.0
        s2 = v2.scale if v2.scale > 0.0 else 1.0

        # Extract unique X levels of vertical lines
        x_levels_1 = {round((p.start[0] + p.end[0]) / (2.0 * s1), 2) for p in v1.primitives if p.is_vertical()}
        x_levels_1.add(round(v1.norm_bbox[0], 2))
        x_levels_1.add(round(v1.norm_bbox[2], 2))

        x_levels_2 = {round((p.start[0] + p.end[0]) / (2.0 * s2), 2) for p in v2.primitives if p.is_vertical()}
        x_levels_2.add(round(v2.norm_bbox[0], 2))
        x_levels_2.add(round(v2.norm_bbox[2], 2))

        if not x_levels_1 or not x_levels_2:
            return 0.0, 0, 0

        matched = 0
        for x1 in x_levels_1:
            if any(abs(x1 - x2) <= self.ray_coincidence_tolerance_mm for x2 in x_levels_2):
                matched += 1

        total = len(x_levels_1)
        support = matched / total if total > 0 else 0.0
        return support, matched, total

    def _check_component_compatibility(self, v1: ViewRegion, v2: ViewRegion) -> Optional[str]:
        """Ensures that views asserting the same component_id possess compatible dimensions."""
        shared_comps = set(v1.component_ids) & set(v2.component_ids)
        if not shared_comps:
            return None

        roles = {v1.view_role, v2.view_role}
        side_roles = {"SIDE", "RIGHT_SIDE", "LEFT_SIDE"}
        top_roles = {"TOP", "PLAN"}

        if "FRONT" in roles and bool(roles & side_roles):
            # Elevation & Side must match on HEIGHT (Z-axis in 3D)
            h_err = abs(v1.norm_height - v2.norm_height) / max(1e-6, min(v1.norm_height, v2.norm_height))
            if h_err > self.span_relative_tolerance:
                return f"GEOMETRIC_INCOMPATIBILITY_REJECTED: FRONT view and SIDE view share component {sorted(shared_comps)} but mismatch on height ({v1.norm_height} vs {v2.norm_height}, error={round(h_err, 4)})"

        elif "FRONT" in roles and bool(roles & top_roles):
            # Elevation & Plan must match on WIDTH (X-axis in 3D)
            w_err = abs(v1.norm_width - v2.norm_width) / max(1e-6, min(v1.norm_width, v2.norm_width))
            if w_err > self.span_relative_tolerance:
                return f"GEOMETRIC_INCOMPATIBILITY_REJECTED: FRONT view and TOP view share component {sorted(shared_comps)} but mismatch on width ({v1.norm_width} vs {v2.norm_width}, error={round(w_err, 4)})"

        elif bool(roles & top_roles) and bool(roles & side_roles):
            # Plan & Side must match on DEPTH (Y-axis in 3D: Top Height == Side Width)
            top_v = v1 if v1.view_role in top_roles else v2
            side_v = v2 if v1.view_role in top_roles else v1
            d_err = abs(top_v.norm_height - side_v.norm_width) / max(1e-6, min(top_v.norm_height, side_v.norm_width))
            if d_err > self.depth_miter_tolerance:
                return f"GEOMETRIC_INCOMPATIBILITY_REJECTED: TOP view and SIDE view share component {sorted(shared_comps)} but mismatch on depth ({top_v.norm_height} vs {side_v.norm_width}, error={round(d_err, 4)})"

        else:
            # Unknown roles: general compatibility
            h_match = abs(v1.norm_height - v2.norm_height) / max(1e-6, min(v1.norm_height, v2.norm_height)) <= self.span_relative_tolerance
            w_match = abs(v1.norm_width - v2.norm_width) / max(1e-6, min(v1.norm_width, v2.norm_width)) <= self.span_relative_tolerance
            if not (h_match or w_match):
                return f"GEOMETRIC_INCOMPATIBILITY_REJECTED: views {v1.view_id} and {v2.view_id} share component {sorted(shared_comps)} but mismatch on all dimensions"

        return None

    def _resolve_projection_consensus(self, votes: List[str]) -> str:
        """Determines drawing-wide projection system consensus from pairwise evidence."""
        if not votes:
            return "INDETERMINATE"
        count_third = votes.count("THIRD_ANGLE")
        count_first = votes.count("FIRST_ANGLE")
        if count_third > 0 and count_first == 0:
            return "THIRD_ANGLE"
        if count_first > 0 and count_third == 0:
            return "FIRST_ANGLE"
        if count_third > count_first:
            return "THIRD_ANGLE"
        if count_first > count_third:
            return "FIRST_ANGLE"
        return "INDETERMINATE"

    def _verify_role_layout_consistency(
        self, views: List[ViewRegion], system: str
    ) -> List[str]:
        """Detects inverted or transposed view roles against standard orthographic projection rules."""
        issues: List[str] = []
        front_views = [v for v in views if v.view_role == "FRONT"]
        if not front_views:
            return issues

        for v in views:
            if v.view_role == "FRONT":
                continue
            vb = v.norm_bbox

            if v.view_role in ("TOP", "PLAN"):
                # Find matching front view sharing horizontal span
                matching_fronts = [
                    f for f in front_views
                    if max(0.0, min(f.norm_bbox[2], vb[2]) - max(f.norm_bbox[0], vb[0])) >= 0.5 * min(f.norm_width, v.norm_width)
                ]
                if not matching_fronts:
                    issues.append(f"ROLE_LAYOUT_INVERSION_REJECTED: TOP view {v.view_id} is laterally displaced from all FRONT views")
                else:
                    front = matching_fronts[0]
                    fb = front.norm_bbox
                    if system == "THIRD_ANGLE" and vb[1] < fb[3]:
                        issues.append(f"ROLE_LAYOUT_INVERSION_REJECTED: TOP view {v.view_id} is placed below FRONT view in THIRD_ANGLE system")
                    elif system == "FIRST_ANGLE" and vb[3] > fb[1]:
                        issues.append(f"ROLE_LAYOUT_INVERSION_REJECTED: TOP view {v.view_id} is placed above FRONT view in FIRST_ANGLE system")

            elif v.view_role in ("RIGHT_SIDE",):
                # Find matching front view sharing vertical span
                matching_fronts = [
                    f for f in front_views
                    if max(0.0, min(f.norm_bbox[3], vb[3]) - max(f.norm_bbox[1], vb[1])) >= 0.5 * min(f.norm_height, v.norm_height)
                ]
                if not matching_fronts:
                    issues.append(f"ROLE_LAYOUT_INVERSION_REJECTED: RIGHT_SIDE view {v.view_id} is vertically displaced from all FRONT views")
                else:
                    front = matching_fronts[0]
                    fb = front.norm_bbox
                    if system == "THIRD_ANGLE" and vb[0] < fb[2]:
                        issues.append(f"ROLE_LAYOUT_INVERSION_REJECTED: RIGHT_SIDE view {v.view_id} is placed to the left of FRONT view in THIRD_ANGLE system")
                    elif system == "FIRST_ANGLE" and vb[2] > fb[0]:
                        issues.append(f"ROLE_LAYOUT_INVERSION_REJECTED: RIGHT_SIDE view {v.view_id} is placed to the right of FRONT view in FIRST_ANGLE system")

            elif v.view_role in ("LEFT_SIDE",):
                matching_fronts = [
                    f for f in front_views
                    if max(0.0, min(f.norm_bbox[3], vb[3]) - max(f.norm_bbox[1], vb[1])) >= 0.5 * min(f.norm_height, v.norm_height)
                ]
                if not matching_fronts:
                    issues.append(f"ROLE_LAYOUT_INVERSION_REJECTED: LEFT_SIDE view {v.view_id} is vertically displaced from all FRONT views")
                else:
                    front = matching_fronts[0]
                    fb = front.norm_bbox
                    if system == "THIRD_ANGLE" and vb[2] > fb[0]:
                        issues.append(f"ROLE_LAYOUT_INVERSION_REJECTED: LEFT_SIDE view {v.view_id} is placed to the right of FRONT view in THIRD_ANGLE system")
                    elif system == "FIRST_ANGLE" and vb[0] < fb[2]:
                        issues.append(f"ROLE_LAYOUT_INVERSION_REJECTED: LEFT_SIDE view {v.view_id} is placed to the left of FRONT view in FIRST_ANGLE system")

        return issues

    def _synthesize_projection_pairs(
        self, views: List[ViewRegion], existing_links: List[AlignmentLink], system: str
    ) -> List[AlignmentLink]:
        """Synthesizes high-level VIEWS_ORTHOGRAPHIC_PROJECTION_PAIR relations."""
        pair_links: List[AlignmentLink] = []
        # Find all pairs that have either horizontal or vertical alignment with positive ray support
        for link in existing_links:
            if link.relation_type in ("VIEWS_ALIGNED_HORIZONTALLY", "VIEWS_ALIGNED_VERTICALLY"):
                if link.confidence >= 0.70:
                    pair_id = _make_link_id("VIEWS_ORTHOGRAPHIC_PROJECTION_PAIR", link.source_id, link.target_id, [link.relation_type])
                    pair_links.append(
                        AlignmentLink(
                            link_id=pair_id,
                            relation_type="VIEWS_ORTHOGRAPHIC_PROJECTION_PAIR",
                            source_id=link.source_id,
                            target_id=link.target_id,
                            evidence_refs=[link.relation_type],
                            confidence=link.confidence,
                            projection_system=system,
                            diagnostics={
                                "base_relation": link.relation_type,
                                "base_confidence": link.confidence,
                            },
                        )
                    )
        return pair_links
