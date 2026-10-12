"""Detail View Callout, Enlargement Scale, and Parent Bubble Correspondence Engine.

Empirical reference engine comparing:
- Strategy A: Current Production Baseline (parse_scale_label reduction-only, zero detail view correspondence).
- Strategy B: Naive Keyword Matcher (searches for 'DETAIL' text, nearest view, blind 1.0 scale).
- Strategy C: Isolated Bubble Matcher (matches tag letter between bubble and callout, but lacks magnification verification).
- Strategy D: Unified Detail View Callout, Enlargement Scale & Parent Bubble Correspondence Engine (Oracle).
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float

    def distance_to(self, other: Point2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass(frozen=True)
class DetailBubble:
    id: str
    parent_view_id: str
    center: Point2D
    radius: float
    identifier_tag: str  # e.g. "B"
    shape: Literal["circle", "ellipse", "spline"] = "circle"
    leader_line_ids: tuple[str, ...] = ()
    confidence: float = 0.95

    @property
    def bbox_px(self) -> tuple[float, float, float, float]:
        return (
            self.center.x - self.radius,
            self.center.y - self.radius,
            self.center.x + self.radius,
            self.center.y + self.radius,
        )


@dataclass(frozen=True)
class DetailViewCallout:
    id: str
    raw_text: str
    identifier_tag: str  # e.g. "B"
    scale_numerator: int
    scale_denominator: int
    magnification_factor: float  # e.g. 2.0 for 2:1, 5.0 for 5:1, 0.5 for 1:2
    bbox_px: tuple[float, float, float, float]
    confidence: float


@dataclass
class DetailViewRegion:
    id: str
    bbox_px: tuple[float, float, float, float]
    view_type: Literal["principal", "detail", "unclassified"] = "unclassified"
    title_callout: DetailViewCallout | None = None
    primitive_ids: list[str] = field(default_factory=list)
    feature_lengths: list[float] = field(default_factory=list)

    @property
    def center(self) -> Point2D:
        return Point2D(
            (self.bbox_px[0] + self.bbox_px[2]) / 2.0,
            (self.bbox_px[1] + self.bbox_px[3]) / 2.0,
        )


@dataclass
class DetailCorrespondence:
    id: str
    detail_tag: str
    parent_view_id: str
    detail_view_id: str
    bubble_id: str
    callout_id: str
    nominal_magnification: float
    measured_magnification: float
    magnification_error_percent: float
    status: Literal[
        "verified",
        "magnification_mismatch",
        "missing_parent_bubble",
        "missing_detail_view",
    ]
    confidence: float


# Regex supporting both reduction (1:N) AND enlargement (N:1, N:M) scales with multilingual prefixes
_DETAIL_RE = re.compile(
    r"^(?:DETAIL|DET\.?|CHI\s*TI[ẾE]T|CHI\s*TIET|VIEW|PHÓNG\s*ĐẠI)\s+"
    r"(?P<tag>[A-Z0-9]+)"
    r"(?:\s*\(?(?:SCALE|TL|THI|TY\s*LE)?\s*(?P<num>\d+)\s*[:/]\s*(?P<den>\d+)\)?)?$",
    re.IGNORECASE,
)
_BARE_SCALE_ANY_RE = re.compile(
    r"^(?:SCALE|TL|THI|TY\s*LE)?\s*(?P<num>\d+)\s*[:/]\s*(?P<den>\d+)$",
    re.IGNORECASE,
)


def parse_detail_scale_callout(
    content: str,
    text_id: str = "txt-0",
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
) -> DetailViewCallout | None:
    """Parse detail view title callouts with general N:M or N:1 scale ratios."""
    if not content or not isinstance(content, str):
        return None
    normalized = unicodedata.normalize("NFKC", content).strip()
    match = _DETAIL_RE.fullmatch(normalized)
    if not match:
        return None

    tag = match.group("tag").upper()
    num_raw = match.groupdict().get("num")
    den_raw = match.groupdict().get("den")

    if num_raw and den_raw:
        num = int(num_raw)
        den = int(den_raw)
        mag = (num / den) if den > 0 else 1.0
    else:
        num, den, mag = 1, 1, 1.0  # Default 1:1 if scale omitted

    return DetailViewCallout(
        id=text_id,
        raw_text=content,
        identifier_tag=tag,
        scale_numerator=num,
        scale_denominator=den,
        magnification_factor=mag,
        bbox_px=bbox,
        confidence=0.98 if num_raw else 0.85,
    )


def mm_per_px_for_general_scale(numerator: int, denominator: int, dpi: int) -> float:
    """Correct general formula converting paper pixel coordinates to CAD millimeters."""
    if numerator <= 0 or denominator <= 0 or dpi <= 0:
        raise ValueError("numerator, denominator, and dpi must be positive")
    # 1 pixel = (25.4 / dpi) mm on paper.
    # Scale is (paper / CAD) = (numerator / denominator).
    # Therefore: CAD mm = (paper mm) * (denominator / numerator).
    return (denominator / numerator) * (25.4 / dpi)


# =========================================================================
# STRATEGY A: Current Production Baseline
# =========================================================================
def run_strategy_a(
    views: Sequence[DetailViewRegion],
    texts: Sequence[Any],
    bubbles: Sequence[DetailBubble],
) -> list[DetailCorrespondence]:
    """Strategy A reproduces current production behavior: zero detail view understanding."""
    return []


# =========================================================================
# STRATEGY B: Naive Keyword Matcher
# =========================================================================
def run_strategy_b(
    views: Sequence[DetailViewRegion],
    texts: Sequence[Any],
    bubbles: Sequence[DetailBubble],
) -> list[DetailCorrespondence]:
    """Strategy B assigns 'DETAIL' texts to nearest view with blind 1.0 scale and no bubble info."""
    results: list[DetailCorrespondence] = []
    for t in texts:
        content = getattr(t, "content", "")
        if "DETAIL" in content.upper() or "CHI TIẾT" in content.upper():
            tb = getattr(t, "bbox_px", (0, 0, 0, 0))
            tc = Point2D((tb[0] + tb[2]) / 2.0, (tb[1] + tb[3]) / 2.0)
            closest_view = min(views, key=lambda v: tc.distance_to(v.center), default=None)
            if closest_view:
                other_views = [v for v in views if v.id != closest_view.id]
                parent = other_views[0] if other_views else closest_view
                results.append(DetailCorrespondence(
                    id=f"corr-b-{getattr(t, 'id', 'txt')}",
                    detail_tag="UNKNOWN",
                    parent_view_id=parent.id,
                    detail_view_id=closest_view.id,
                    bubble_id="unknown",
                    callout_id=getattr(t, "id", "txt"),
                    nominal_magnification=1.0,
                    measured_magnification=1.0,
                    magnification_error_percent=0.0,
                    status="verified",
                    confidence=0.4,
                ))
    return results


# =========================================================================
# STRATEGY C: Isolated Bubble Matcher
# =========================================================================
def run_strategy_c(
    views: Sequence[DetailViewRegion],
    texts: Sequence[Any],
    bubbles: Sequence[DetailBubble],
) -> list[DetailCorrespondence]:
    """Strategy C matches bubble tag with callout tag, but lacks feature magnification check."""
    results: list[DetailCorrespondence] = []
    callouts = [
        parse_detail_scale_callout(getattr(t, "content", ""), getattr(t, "id", ""), getattr(t, "bbox_px", (0, 0, 0, 0)))
        for t in texts
    ]
    callouts = [c for c in callouts if c is not None]

    for bubble in bubbles:
        matching_c = next((c for c in callouts if c.identifier_tag == bubble.identifier_tag), None)
        if not matching_c:
            continue
        c_pt = Point2D((matching_c.bbox_px[0] + matching_c.bbox_px[2]) / 2.0, (matching_c.bbox_px[1] + matching_c.bbox_px[3]) / 2.0)
        detail_view = min((v for v in views if v.id != bubble.parent_view_id), key=lambda v: c_pt.distance_to(v.center), default=None)
        if detail_view:
            results.append(DetailCorrespondence(
                id=f"corr-c-{bubble.identifier_tag}",
                detail_tag=bubble.identifier_tag,
                parent_view_id=bubble.parent_view_id,
                detail_view_id=detail_view.id,
                bubble_id=bubble.id,
                callout_id=matching_c.id,
                nominal_magnification=matching_c.magnification_factor,
                measured_magnification=matching_c.magnification_factor,  # Blind copy, no geometric measurement!
                magnification_error_percent=0.0,
                status="verified",
                confidence=0.7,
            ))
    return results


# =========================================================================
# STRATEGY D: Unified Detail View Callout & Parent Bubble Engine (Oracle)
# =========================================================================
class DetailViewCorrespondenceOracle:
    """Oracle detector pairing detail views to parent bubble ROIs with magnification verification."""

    def __init__(self, magnification_tolerance_percent: float = 5.0) -> None:
        self.magnification_tolerance_percent = magnification_tolerance_percent

    def parse_callouts(self, texts: Sequence[Any]) -> list[DetailViewCallout]:
        callouts: list[DetailViewCallout] = []
        for t in texts:
            content = getattr(t, "content", "")
            bbox = getattr(t, "bbox_px", (0.0, 0.0, 0.0, 0.0))
            tid = getattr(t, "id", "txt")
            c = parse_detail_scale_callout(content, tid, bbox)
            if c:
                callouts.append(c)
        return callouts

    def solve_correspondence(
        self,
        views: Sequence[DetailViewRegion],
        bubbles: Sequence[DetailBubble],
        texts: Sequence[Any],
        parent_feature_lengths: dict[str, list[float]] | None = None,
    ) -> list[DetailCorrespondence]:
        callouts = self.parse_callouts(texts)
        view_map = {v.id: v for v in views}
        correspondences: list[DetailCorrespondence] = []

        for bubble in bubbles:
            tag = bubble.identifier_tag
            parent_view = view_map.get(bubble.parent_view_id)
            if not parent_view:
                continue

            matching_callouts = [c for c in callouts if c.identifier_tag == tag]
            if not matching_callouts:
                # Detail view callout missing on sheet
                correspondences.append(DetailCorrespondence(
                    id=f"corr-{tag}-missing-detail",
                    detail_tag=tag,
                    parent_view_id=bubble.parent_view_id,
                    detail_view_id="",
                    bubble_id=bubble.id,
                    callout_id="",
                    nominal_magnification=1.0,
                    measured_magnification=1.0,
                    magnification_error_percent=0.0,
                    status="missing_detail_view",
                    confidence=0.0,
                ))
                continue

            callout = matching_callouts[0]
            # Find detail view closest to callout
            c_center = Point2D((callout.bbox_px[0] + callout.bbox_px[2]) / 2.0, (callout.bbox_px[1] + callout.bbox_px[3]) / 2.0)
            candidate_views = [v for v in views if v.id != parent_view.id]
            if not candidate_views:
                continue
            detail_view = min(candidate_views, key=lambda v: c_center.distance_to(v.center))

            nom_mag = callout.magnification_factor

            # Geometric verification: measure feature magnification
            # If parent feature lengths provided for bubble, compare with detail view features
            meas_mag = nom_mag
            err_percent = 0.0
            parent_lens = (parent_feature_lengths or {}).get(bubble.id, [])
            detail_lens = detail_view.feature_lengths

            if parent_lens and detail_lens:
                # Average ratio of matching largest feature lengths
                p_max = max(parent_lens)
                d_max = max(detail_lens)
                if p_max > 1e-6:
                    meas_mag = d_max / p_max
                    err_percent = abs(meas_mag - nom_mag) / nom_mag * 100.0

            is_match = err_percent <= self.magnification_tolerance_percent
            status: Literal["verified", "magnification_mismatch"] = (
                "verified" if is_match else "magnification_mismatch"
            )

            conf = 0.99 if is_match else 0.50

            correspondences.append(DetailCorrespondence(
                id=f"corr-{tag}-{parent_view.id}-{detail_view.id}",
                detail_tag=tag,
                parent_view_id=parent_view.id,
                detail_view_id=detail_view.id,
                bubble_id=bubble.id,
                callout_id=callout.id,
                nominal_magnification=nom_mag,
                measured_magnification=meas_mag,
                magnification_error_percent=err_percent,
                status=status,
                confidence=conf,
            ))

        return correspondences


def run_strategy_d(
    views: Sequence[DetailViewRegion],
    texts: Sequence[Any],
    bubbles: Sequence[DetailBubble],
    parent_feature_lengths: dict[str, list[float]] | None = None,
) -> list[DetailCorrespondence]:
    """Strategy D: Full Oracle Execution."""
    oracle = DetailViewCorrespondenceOracle()
    return oracle.solve_correspondence(views, bubbles, texts, parent_feature_lengths)
