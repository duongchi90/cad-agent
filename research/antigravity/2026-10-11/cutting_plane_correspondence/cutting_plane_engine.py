"""Cutting Plane Line, Viewing Arrow Vector, and Section View Correspondence Engine.

Empirical reference engine comparing:
- Strategy A: Current Production Baseline (view_calibration.py scale parser only, no section understanding).
- Strategy B: Naive Text Proximity (regex section title search + nearest view bbox assignment).
- Strategy C: Geometric Cutting Line Filter (finds candidate cutting lines, lacks arrow vector & cross-view validation).
- Strategy D: Unified Cutting Plane, Arrow Vector & Section View Correspondence Engine (Oracle).
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Sequence


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float

    def distance_to(self, other: Point2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass(frozen=True)
class ViewingArrow:
    tip: Point2D
    tail: Point2D
    viewing_vector: tuple[float, float]  # Normalized (vx, vy)
    label: str | None = None
    primitive_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CuttingPlaneSegment:
    start: Point2D
    end: Point2D
    is_end_termination: bool = False
    primitive_id: str | None = None

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)

    @property
    def direction(self) -> tuple[float, float]:
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        dist = math.hypot(dx, dy)
        if dist < 1e-9:
            return (0.0, 0.0)
        return (dx / dist, dy / dist)


@dataclass
class CuttingPlane:
    id: str
    identifier_tag: str  # e.g. "A"
    segments: list[CuttingPlaneSegment]
    arrows: list[ViewingArrow]
    parent_view_id: str | None
    kind: Literal["straight", "stepped", "offset"]
    normal_vector: tuple[float, float]  # Viewing direction (vx, vy)
    confidence: float
    tag_primitive_ids: list[str] = field(default_factory=list)

    @property
    def total_length(self) -> float:
        return sum(s.length for s in self.segments)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        pts = [s.start for s in self.segments] + [s.end for s in self.segments]
        for a in self.arrows:
            pts.extend([a.tip, a.tail])
        if not pts:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))


@dataclass(frozen=True)
class SectionViewCallout:
    id: str
    raw_text: str
    identifier_tag: str  # e.g. "A"
    scale_denominator: int | None
    bbox_px: tuple[float, float, float, float]
    confidence: float


@dataclass
class ViewRegion:
    id: str
    bbox_px: tuple[float, float, float, float]
    view_type: Literal["principal", "section", "detail", "unclassified"] = "unclassified"
    title_callout: SectionViewCallout | None = None
    primitive_ids: list[str] = field(default_factory=list)
    has_hatch: bool = False

    @property
    def center(self) -> Point2D:
        return Point2D(
            (self.bbox_px[0] + self.bbox_px[2]) / 2.0,
            (self.bbox_px[1] + self.bbox_px[3]) / 2.0,
        )


@dataclass
class SectionCorrespondence:
    id: str
    section_tag: str
    parent_view_id: str
    section_view_id: str
    cutting_plane_id: str
    callout_id: str
    viewing_vector: tuple[float, float]
    displacement_vector: tuple[float, float]  # center_section - center_parent
    spatial_consistency: bool
    scale_ratio: float
    status: Literal[
        "verified",
        "inconsistent_viewing_direction",
        "ambiguous",
        "missing_parent",
        "missing_section",
    ]
    confidence: float


# --- Regex for section titles ---
_SECTION_RE = re.compile(
    r"^(?:SECTION|SEC\.?|MẶT\s*CẮT|MAT\s*CAT|COUPE|SCHNITT|VIEW|CẮT)\s+"
    r"(?P<tag>[A-Z0-9])\s*[-–—]\s*(?P=tag)"
    r"(?:\s*\(?(?:SCALE|TL|THI|TY\s*LE)?\s*1\s*:\s*(?P<scale>\d+)\)?)?$",
    re.IGNORECASE,
)
_BARE_SECTION_RE = re.compile(
    r"^(?P<tag>[A-Z0-9])\s*[-–—]\s*(?P=tag)"
    r"(?:\s*\(?(?:SCALE|TL|THI|TY\s*LE)?\s*1\s*:\s*(?P<scale>\d+)\)?)?$",
    re.IGNORECASE,
)


def parse_section_callout_text(content: str, text_id: str = "txt-0", bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)) -> SectionViewCallout | None:
    """Deterministically parse section title candidates like 'SECTION A-A' or 'MẶT CẮT B-B (1:2)'."""
    if not content or not isinstance(content, str):
        return None
    normalized = unicodedata.normalize("NFKC", content).strip()
    match = _SECTION_RE.fullmatch(normalized) or _BARE_SECTION_RE.fullmatch(normalized)
    if not match:
        return None
    tag = match.group("tag").upper()
    scale_raw = match.groupdict().get("scale")
    scale_denom = int(scale_raw) if scale_raw else None
    return SectionViewCallout(
        id=text_id,
        raw_text=content,
        identifier_tag=tag,
        scale_denominator=scale_denom,
        bbox_px=bbox,
        confidence=0.95 if match.group("scale") is not None or "SECTION" in normalized.upper() else 0.85,
    )


def _point_in_bbox(pt: Point2D, bbox: tuple[float, float, float, float], margin: float = 1.0) -> bool:
    return (bbox[0] - margin) <= pt.x <= (bbox[2] + margin) and (bbox[1] - margin) <= pt.y <= (bbox[3] + margin)


def _unit_vector(dx: float, dy: float) -> tuple[float, float]:
    dist = math.hypot(dx, dy)
    if dist < 1e-9:
        return (0.0, 0.0)
    return (dx / dist, dy / dist)


# =========================================================================
# STRATEGY A: Current Production Baseline
# =========================================================================
def run_strategy_a(
    views: Sequence[ViewRegion],
    lines: Sequence[Any],
    texts: Sequence[Any],
) -> list[SectionCorrespondence]:
    """Strategy A reproduces current production behavior: zero section view understanding."""
    # Production view_calibration.py and fidelity.py do not extract cutting planes or section links
    return []


# =========================================================================
# STRATEGY B: Naive Text Proximity
# =========================================================================
def run_strategy_b(
    views: Sequence[ViewRegion],
    lines: Sequence[Any],
    texts: Sequence[Any],
) -> list[SectionCorrespondence]:
    """Strategy B assigns parsed section titles to nearest views, but lacks cutting plane geometry."""
    results: list[SectionCorrespondence] = []
    parsed_callouts: list[tuple[SectionViewCallout, Any]] = []

    for t in texts:
        content = getattr(t, "content", "")
        bbox = getattr(t, "bbox_px", (0.0, 0.0, 0.0, 0.0))
        tid = getattr(t, "id", "txt")
        c = parse_section_callout_text(content, tid, bbox)
        if c:
            parsed_callouts.append((c, t))

    # Match each callout to closest view
    for callout, _ in parsed_callouts:
        c_center = Point2D((callout.bbox_px[0] + callout.bbox_px[2]) / 2.0, (callout.bbox_px[1] + callout.bbox_px[3]) / 2.0)
        # Find closest view
        closest_view = min(views, key=lambda v: c_center.distance_to(v.center), default=None)
        if not closest_view:
            continue
        
        # Strategy B blindly assumes any other view is the parent, with no cutting plane info
        other_views = [v for v in views if v.id != closest_view.id]
        if other_views:
            parent_view = other_views[0]
            dx = closest_view.center.x - parent_view.center.x
            dy = closest_view.center.y - parent_view.center.y
            results.append(SectionCorrespondence(
                id=f"corr-{callout.identifier_tag}",
                section_tag=callout.identifier_tag,
                parent_view_id=parent_view.id,
                section_view_id=closest_view.id,
                cutting_plane_id="unknown",
                callout_id=callout.id,
                viewing_vector=(0.0, 0.0),  # Cannot determine viewing vector!
                displacement_vector=_unit_vector(dx, dy),
                spatial_consistency=True,  # Blind guess
                scale_ratio=1.0 if not callout.scale_denominator else (1.0 / callout.scale_denominator),
                status="ambiguous",
                confidence=0.4,
            ))
    return results


# =========================================================================
# STRATEGY C: Geometric Cutting Line Filter Only
# =========================================================================
def run_strategy_c(
    views: Sequence[ViewRegion],
    lines: Sequence[Any],
    texts: Sequence[Any],
) -> list[SectionCorrespondence]:
    """Strategy C detects candidate cutting lines in views but lacks arrow viewing vector and cross-view validation."""
    results: list[SectionCorrespondence] = []
    callouts = [
        parse_section_callout_text(getattr(t, "content", ""), getattr(t, "id", ""), getattr(t, "bbox_px", (0, 0, 0, 0)))
        for t in texts
    ]
    callouts = [c for c in callouts if c is not None]

    # For each view, look for lines marked as cutting lines or long dashed lines
    for view in views:
        view_lines = [l for l in lines if _point_in_bbox(Point2D(getattr(l, "p1_px", (0, 0))[0], getattr(l, "p1_px", (0, 0))[1]), view.bbox_px)]
        # Look for tag text inside view
        tag_texts = [
            t for t in texts
            if len(getattr(t, "content", "").strip()) == 1 and getattr(t, "content", "").strip().isupper()
            and _point_in_bbox(Point2D(getattr(t, "bbox_px", (0, 0, 0, 0))[0], getattr(t, "bbox_px", (0, 0, 0, 0))[1]), view.bbox_px)
        ]
        if not tag_texts or not view_lines:
            continue
        
        tag = getattr(tag_texts[0], "content", "").strip()
        # Find matching callout
        matching_callout = next((c for c in callouts if c.identifier_tag == tag), None)
        if matching_callout:
            # Find section view near callout
            c_center = Point2D((matching_callout.bbox_px[0] + matching_callout.bbox_px[2]) / 2.0, (matching_callout.bbox_px[1] + matching_callout.bbox_px[3]) / 2.0)
            sec_view = min((v for v in views if v.id != view.id), key=lambda v: c_center.distance_to(v.center), default=None)
            if sec_view:
                results.append(SectionCorrespondence(
                    id=f"corr-{tag}",
                    section_tag=tag,
                    parent_view_id=view.id,
                    section_view_id=sec_view.id,
                    cutting_plane_id=f"cp-{tag}",
                    callout_id=matching_callout.id,
                    viewing_vector=(0.0, 0.0),  # Strategy C does NOT extract arrows or viewing vectors
                    displacement_vector=(0.0, 0.0),
                    spatial_consistency=True,  # Blind assumption
                    scale_ratio=1.0,
                    status="ambiguous",
                    confidence=0.6,
                ))
    return results


# =========================================================================
# STRATEGY D: Unified Cutting Plane, Arrow Vector & Section View Correspondence (Oracle)
# =========================================================================
class CuttingPlaneCorrespondenceOracle:
    """Oracle detector uniting cutting planes, direction arrows, and cross-view validation."""

    def __init__(
        self,
        collinear_tolerance_deg: float = 3.0,
        arrow_tip_distance_tol_px: float = 12.0,
        tag_label_distance_tol_px: float = 25.0,
        view_direction_alignment_min_cosine: float = 0.5,
    ) -> None:
        self.collinear_tolerance_deg = collinear_tolerance_deg
        self.arrow_tip_distance_tol_px = arrow_tip_distance_tol_px
        self.tag_label_distance_tol_px = tag_label_distance_tol_px
        self.view_direction_alignment_min_cosine = view_direction_alignment_min_cosine

    def parse_callouts(self, texts: Sequence[Any]) -> list[SectionViewCallout]:
        callouts: list[SectionViewCallout] = []
        for t in texts:
            content = getattr(t, "content", "")
            bbox = getattr(t, "bbox_px", (0.0, 0.0, 0.0, 0.0))
            tid = getattr(t, "id", "txt")
            c = parse_section_callout_text(content, tid, bbox)
            if c:
                callouts.append(c)
        return callouts

    def extract_viewing_arrows(
        self,
        arrow_candidates: Sequence[dict[str, Any]],
        texts: Sequence[Any],
    ) -> list[ViewingArrow]:
        """Convert arrow primitives into ViewingArrow records with adjacent letter association."""
        arrows: list[ViewingArrow] = []
        for raw in arrow_candidates:
            tip = Point2D(float(raw["tip"][0]), float(raw["tip"][1]))
            tail = Point2D(float(raw["tail"][0]), float(raw["tail"][1]))
            dx = tip.x - tail.x
            dy = tip.y - tail.y
            dist = math.hypot(dx, dy)
            if dist < 1e-6 or not (math.isfinite(dist)):
                continue
            # Viewing vector points in sight direction (from tail to tip)
            vx, vy = dx / dist, dy / dist

            # Find nearby single-letter label
            best_label = None
            min_dist = float("inf")
            for t in texts:
                c = getattr(t, "content", "").strip()
                if len(c) == 1 and c.isalpha() and c.isupper():
                    tb = getattr(t, "bbox_px", (0, 0, 0, 0))
                    tc = Point2D((tb[0] + tb[2]) / 2.0, (tb[1] + tb[3]) / 2.0)
                    d = tail.distance_to(tc)
                    if d < self.tag_label_distance_tol_px and d < min_dist:
                        min_dist = d
                        best_label = c

            arrows.append(ViewingArrow(
                tip=tip,
                tail=tail,
                viewing_vector=(vx, vy),
                label=best_label,
                primitive_ids=tuple(raw.get("primitive_ids", ())),
            ))
        return arrows

    def detect_cutting_planes(
        self,
        line_primitives: Sequence[Any],
        arrows: Sequence[ViewingArrow],
        views: Sequence[ViewRegion],
    ) -> list[CuttingPlane]:
        """Detect straight and stepped cutting planes in parent views."""
        cutting_planes: list[CuttingPlane] = []

        # Group arrows by label tag
        arrows_by_tag: dict[str, list[ViewingArrow]] = {}
        for a in arrows:
            if a.label:
                arrows_by_tag.setdefault(a.label, []).append(a)

        for tag, tag_arrows in arrows_by_tag.items():
            if len(tag_arrows) < 2:
                # Need at least 2 arrows for ISO/ASME cutting plane
                continue

            a1, a2 = tag_arrows[0], tag_arrows[1]
            # Determine which view contains both arrows
            parent_view = None
            for v in views:
                if _point_in_bbox(a1.tip, v.bbox_px, margin=20.0) and _point_in_bbox(a2.tip, v.bbox_px, margin=20.0):
                    parent_view = v
                    break

            if not parent_view:
                continue

            # Average viewing normal vector
            avg_vx = (a1.viewing_vector[0] + a2.viewing_vector[0]) / 2.0
            avg_vy = (a1.viewing_vector[1] + a2.viewing_vector[1]) / 2.0
            v_norm = _unit_vector(avg_vx, avg_vy)

            # Collect segments connecting the arrow tips
            # If the vector between a1.tip and a2.tip is perpendicular to v_norm -> straight cut
            dx = a2.tip.x - a1.tip.x
            dy = a2.tip.y - a1.tip.y
            cut_dist = math.hypot(dx, dy)
            if cut_dist < 1e-6:
                continue

            cut_u = _unit_vector(dx, dy)
            # Dot product with viewing vector should be approximately 0
            dot = abs(cut_u[0] * v_norm[0] + cut_u[1] * v_norm[1])
            is_straight = dot < 0.15

            segments = [
                CuttingPlaneSegment(
                    start=a1.tip,
                    end=a2.tip,
                    is_end_termination=True,
                    primitive_id=f"seg-{tag}-main",
                )
            ]

            cutting_planes.append(CuttingPlane(
                id=f"cp-{tag}-{parent_view.id}",
                identifier_tag=tag,
                segments=segments,
                arrows=[a1, a2],
                parent_view_id=parent_view.id,
                kind="straight" if is_straight else "stepped",
                normal_vector=v_norm,
                confidence=0.95 if is_straight else 0.88,
                tag_primitive_ids=[a1.primitive_ids[0] if a1.primitive_ids else "", a2.primitive_ids[0] if a2.primitive_ids else ""],
            ))

        return cutting_planes

    def associate_views_and_callouts(
        self,
        views: Sequence[ViewRegion],
        callouts: Sequence[SectionViewCallout],
    ) -> list[ViewRegion]:
        """Pair section callouts with their corresponding view bounding boxes."""
        updated_views: list[ViewRegion] = []
        for v in views:
            v_copy = ViewRegion(
                id=v.id,
                bbox_px=v.bbox_px,
                view_type=v.view_type,
                title_callout=v.title_callout,
                primitive_ids=list(v.primitive_ids),
                has_hatch=v.has_hatch,
            )
            # Check if any callout belongs to this view (usually below or above the view)
            best_callout = None
            min_dist = float("inf")
            for c in callouts:
                c_center = Point2D((c.bbox_px[0] + c.bbox_px[2]) / 2.0, (c.bbox_px[1] + c.bbox_px[3]) / 2.0)
                # Distance to bottom or top of view bbox
                d = v_copy.center.distance_to(c_center)
                # Callout should be relatively close to view bbox
                if d < min_dist and d < max(v.bbox_px[2] - v.bbox_px[0], v.bbox_px[3] - v.bbox_px[1]) * 1.5:
                    min_dist = d
                    best_callout = c

            if best_callout:
                v_copy.view_type = "section"
                v_copy.title_callout = best_callout
            elif v_copy.view_type == "unclassified":
                v_copy.view_type = "principal"
            updated_views.append(v_copy)
        return updated_views

    def solve_correspondence(
        self,
        views: Sequence[ViewRegion],
        cutting_planes: Sequence[CuttingPlane],
        callouts: Sequence[SectionViewCallout],
    ) -> list[SectionCorrespondence]:
        """Establish end-to-end correspondence between parent cutting plane and section view."""
        annotated_views = self.associate_views_and_callouts(views, callouts)
        view_map = {v.id: v for v in annotated_views}

        correspondences: list[SectionCorrespondence] = []

        for cp in cutting_planes:
            tag = cp.identifier_tag
            parent_view = view_map.get(cp.parent_view_id) if cp.parent_view_id else None
            if not parent_view:
                continue

            # Find section view with matching title callout tag
            matching_sections = [
                v for v in annotated_views
                if v.id != parent_view.id and v.title_callout and v.title_callout.identifier_tag == tag
            ]

            if not matching_sections:
                # Missing section view on sheet
                correspondences.append(SectionCorrespondence(
                    id=f"corr-{tag}-{parent_view.id}-missing",
                    section_tag=tag,
                    parent_view_id=parent_view.id,
                    section_view_id="",
                    cutting_plane_id=cp.id,
                    callout_id="",
                    viewing_vector=cp.normal_vector,
                    displacement_vector=(0.0, 0.0),
                    spatial_consistency=False,
                    scale_ratio=1.0,
                    status="missing_section",
                    confidence=0.0,
                ))
                continue

            section_view = matching_sections[0]
            callout = section_view.title_callout
            assert callout is not None

            # Calculate displacement vector from parent view center to section view center
            dx = section_view.center.x - parent_view.center.x
            dy = section_view.center.y - parent_view.center.y
            disp_u = _unit_vector(dx, dy)

            # Check spatial consistency:
            # Viewing vector points in the direction the observer looks.
            # In first/third angle projection, the section view is projected along the viewing vector!
            # Dot product between viewing vector and displacement should be > 0.
            dot_product = cp.normal_vector[0] * disp_u[0] + cp.normal_vector[1] * disp_u[1]
            is_consistent = dot_product >= self.view_direction_alignment_min_cosine

            scale_ratio = 1.0
            if callout.scale_denominator:
                scale_ratio = 1.0 / callout.scale_denominator

            status: Literal["verified", "inconsistent_viewing_direction"] = (
                "verified" if is_consistent else "inconsistent_viewing_direction"
            )

            conf = 0.98 if is_consistent else 0.45

            correspondences.append(SectionCorrespondence(
                id=f"corr-{tag}-{parent_view.id}-{section_view.id}",
                section_tag=tag,
                parent_view_id=parent_view.id,
                section_view_id=section_view.id,
                cutting_plane_id=cp.id,
                callout_id=callout.id,
                viewing_vector=cp.normal_vector,
                displacement_vector=disp_u,
                spatial_consistency=is_consistent,
                scale_ratio=scale_ratio,
                status=status,
                confidence=conf,
            ))

        return correspondences


def run_strategy_d(
    views: Sequence[ViewRegion],
    lines: Sequence[Any],
    texts: Sequence[Any],
    arrow_candidates: Sequence[dict[str, Any]] | None = None,
) -> list[SectionCorrespondence]:
    """Strategy D: Full Oracle Execution."""
    oracle = CuttingPlaneCorrespondenceOracle()
    callouts = oracle.parse_callouts(texts)
    arrows = oracle.extract_viewing_arrows(arrow_candidates or [], texts)
    cutting_planes = oracle.detect_cutting_planes(lines, arrows, views)
    return oracle.solve_correspondence(views, cutting_planes, callouts)
