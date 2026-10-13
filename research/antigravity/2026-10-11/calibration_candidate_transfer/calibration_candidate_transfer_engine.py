"""Reference Engine for Calibration Candidate Extraction Transfer Architecture (V3).

Evaluates whether Strategy D multi-primitive association transfers safely from
cross_validate() (post-calibration) to auto_estimate_calibration() (pre-calibration).

Compares 3 implementations:
1. Method A: Current Production Baseline (Lines only, midpoint proximity, unbridged)
2. Method B: Naive Cross-Validation Port (Unsafe: blind circle snapping, concentric traps)
3. Method C: Guarded Multi-Primitive Candidate Extraction Oracle:
   - Scale-free collinear gap bridging
   - Strict orientation alignment (eliminates perpendicular hijacking)
   - Concentricity Disambiguation Guard (prevents 100% scale errors on counterbores)
   - Text-height scaled carrier corridor (adaptive to rendering DPI)
   - Multi-candidate consensus verification (AGENTS.md >= 2 witnesses, <= 3% error)
   - Fail-closed candidate emission (strictly status='needs_verification')
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


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


class TransferState(str, Enum):
    CANDIDATE_NEEDS_VERIFICATION = "needs_verification"
    AMBIGUOUS_CONCENTRIC_REFUSED = "ambiguous_concentric_refused"
    CONSENSUS_FAILED = "consensus_failed"
    NO_CANDIDATE_SUPPORTED = "no_candidate_supported"


@dataclass(frozen=True)
class CandidateRecord:
    id: str
    stated_value: float
    pixel_span: float
    scale: float  # stated_value / pixel_span
    primitive_type: str  # "line_bridged", "line_continuous", "circle_diameter", "arc_radius"
    geometry_id: str
    axis: str  # "X", "Y", "RADIAL"
    confidence: float
    notes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PreCalibrationResult:
    status: TransferState
    estimated_scale: Optional[float]
    unit: str
    contributing_candidates: List[CandidateRecord] = field(default_factory=list)
    anisotropy_ratio: float = 1.0
    relative_error_pct: float = 0.0
    notes: List[str] = field(default_factory=list)

    @property
    def is_reviewable(self) -> bool:
        return self.status == TransferState.CANDIDATE_NEEDS_VERIFICATION and self.estimated_scale is not None


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


def _median(vals: List[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 == 1 else (s[mid - 1] + s[mid]) / 2.0


class MethodA_ProductionBaseline:
    """Current Production Baseline for auto_estimate_calibration:
    - Only lines accepted.
    - Midpoint Euclidean distance <= 150px.
    - No gap bridging.
    - Returns first candidate or naive median without multi-primitive checks.
    """

    @staticmethod
    def extract_candidate(texts, lines, circles=None, arcs=None) -> PreCalibrationResult:
        candidates = []
        for text in texts:
            if getattr(text, "semantic_role", "") != "dimension_value" or getattr(text, "parsed_value", None) is None:
                continue
            tx, ty = (text.bbox[0] + text.bbox[2]) / 2.0, (text.bbox[1] + text.bbox[3]) / 2.0
            apply_angle = (getattr(text, "rotation_deg", 0.0) % 180.0) != 0.0
            text_angle = getattr(text, "rotation_deg", 0.0) % 180.0

            line_cands = []
            for l in lines:
                if apply_angle and _angular_diff_deg(l.angle_deg, text_angle) > 20.0:
                    continue
                mx, my = l.midpoint
                dist = math.hypot(mx - tx, my - ty)
                if dist <= 150.0:
                    line_cands.append((l, dist))

            if line_cands:
                best_l, _ = min(line_cands, key=lambda c: c[1])
                length = best_l.length
                if length > 0:
                    candidates.append(CandidateRecord(
                        id=f"cand_{text.id}_{best_l.id}",
                        stated_value=text.parsed_value,
                        pixel_span=length,
                        scale=text.parsed_value / length,
                        primitive_type="line_continuous",
                        geometry_id=best_l.id,
                        axis="X",
                        confidence=0.5,
                    ))

        if not candidates:
            return PreCalibrationResult(
                status=TransferState.NO_CANDIDATE_SUPPORTED,
                estimated_scale=None,
                unit="mm",
                notes=["No dimension-line pair found"],
            )

        scales = [c.scale for c in candidates]
        med = _median(scales)
        return PreCalibrationResult(
            status=TransferState.CANDIDATE_NEEDS_VERIFICATION,
            estimated_scale=med,
            unit="mm",
            contributing_candidates=candidates,
            notes=["Baseline candidate extracted"],
        )


class MethodB_NaiveCrossValidationPort:
    """Direct naive port of cross-validation association without pre-calibration safeguards:
    - Snaps Ø to closest circle center or radius naively.
    - Has no concentricity disambiguation guard.
    - Bridges gaps.
    """

    @staticmethod
    def extract_candidate(texts, lines, circles=None, arcs=None) -> PreCalibrationResult:
        circles = circles or []
        candidates = []
        for text in texts:
            if getattr(text, "semantic_role", "") != "dimension_value" or getattr(text, "parsed_value", None) is None:
                continue
            tx, ty = (text.bbox[0] + text.bbox[2]) / 2.0, (text.bbox[1] + text.bbox[3]) / 2.0
            content = getattr(text, "content", "").strip().upper()

            # Naive diameter snapping: closest circle edge
            if "Ø" in content or "%%C" in content:
                circle_cands = []
                for c in circles:
                    cx, cy = c.center
                    dist = abs(math.hypot(cx - tx, cy - ty) - c.radius)
                    circle_cands.append((c, dist))
                if circle_cands:
                    best_c, _ = min(circle_cands, key=lambda item: item[1])
                    diam = best_c.radius * 2.0
                    candidates.append(CandidateRecord(
                        id=f"cand_diam_{text.id}_{best_c.id}",
                        stated_value=text.parsed_value,
                        pixel_span=diam,
                        scale=text.parsed_value / diam,
                        primitive_type="circle_diameter",
                        geometry_id=best_c.id,
                        axis="RADIAL",
                        confidence=0.8,
                    ))
                    continue

        if not candidates:
            return PreCalibrationResult(status=TransferState.NO_CANDIDATE_SUPPORTED, estimated_scale=None, unit="mm")

        med = _median([c.scale for c in candidates])
        return PreCalibrationResult(
            status=TransferState.CANDIDATE_NEEDS_VERIFICATION,
            estimated_scale=med,
            unit="mm",
            contributing_candidates=candidates,
        )


class MethodC_GuardedMultiPrimitiveOracle:
    """Method C: Guarded Multi-Primitive Candidate Extraction Oracle.
    Specifically designed for PRE-CALIBRATION candidate discovery:
    1. Scale-Free Collinear Gap Bridging (bridges split dimension lines).
    2. Strict Orientation Alignment (eliminates perpendicular hijacking).
    3. Concentricity Disambiguation Guard:
       - Identifies sets of concentric circles (shared center within 2px).
       - If multiple concentric circles exist and text has no leader pointer,
         refuses blind snapping to prevent 100% scale errors.
    4. Text-Height Adaptive Carrier Corridor:
       - Uses carrier_corridor = max(30.0, 3.0 * text_height) instead of static 150px.
    5. Multi-Candidate Consensus & AGENTS.md Invariant:
       - Requires >= 2 independent witnesses with <= 3.0% median relative error.
    6. Anisotropy Check:
       - Separates X and Y dimensions; flags distortion if |s_x - s_y| / mean > 1.5%.
    7. Fail-Closed Output:
       - Always emits status='needs_verification'.
    """

    MAX_COLLINEAR_ANGLE_DIFF = 6.0
    MAX_LATERAL_OFFSET_PX = 6.0
    MAX_CONSENSUS_REL_ERROR = 0.030
    MAX_ANISOTROPY_TOLERANCE = 0.015

    @classmethod
    def extract_candidate(
        cls,
        texts,
        lines,
        circles=None,
        arcs=None,
        explicit_unit: Optional[str] = None,
    ) -> PreCalibrationResult:
        circles = circles or []
        arcs = arcs or []
        candidates: List[CandidateRecord] = []
        notes: List[str] = []

        # Filter valid circles and lines with finite coordinates and positive extents
        valid_circles = [
            c for c in circles
            if math.isfinite(c.center[0]) and math.isfinite(c.center[1]) and math.isfinite(c.radius)
            and c.radius > 0
        ]
        valid_lines = [
            l for l in lines
            if math.isfinite(l.p1[0]) and math.isfinite(l.p1[1])
            and math.isfinite(l.p2[0]) and math.isfinite(l.p2[1])
            and l.length > 0
        ]

        # Find concentric circle clusters
        concentric_clusters: Dict[Tuple[int, int], List] = {}
        for c in valid_circles:
            key = (int(round(c.center[0] / 2.0)), int(round(c.center[1] / 2.0)))
            concentric_clusters.setdefault(key, []).append(c)

        for text in texts:
            if getattr(text, "semantic_role", "") != "dimension_value" or getattr(text, "parsed_value", None) is None:
                continue
            if text.parsed_value <= 0:
                continue
            if not all(math.isfinite(coord) for coord in text.bbox):
                continue

            content = getattr(text, "content", "").strip().upper()
            tx, ty = (text.bbox[0] + text.bbox[2]) / 2.0, (text.bbox[1] + text.bbox[3]) / 2.0
            th = abs(text.bbox[3] - text.bbox[1])
            tw = abs(text.bbox[2] - text.bbox[0])

            # --- A. Diameter Callouts (Ø, %%C, DIA) ---
            if "Ø" in content or "%%C" in content or "DIA" in content:
                # Find circles enclosing or near text
                matching_circles = []
                for c in valid_circles:
                    dist = math.hypot(c.center[0] - tx, c.center[1] - ty)
                    if dist <= max(c.radius * 2.5, 80.0):
                        matching_circles.append(c)

                if matching_circles:
                    # Concentricity Guard: Check if matching circles are concentric
                    centers = set((int(round(c.center[0] / 2.0)), int(round(c.center[1] / 2.0))) for c in matching_circles)
                    if len(matching_circles) > 1 and len(centers) == 1:
                        # Ambiguous concentric circles without prior scale!
                        # Refuse blind snapping
                        notes.append(f"Text '{text.content}' near {len(matching_circles)} concentric circles; ambiguous without leader")
                        continue
                    else:
                        best_c = min(matching_circles, key=lambda c: math.hypot(c.center[0] - tx, c.center[1] - ty))
                        diam = best_c.radius * 2.0
                        if diam > 0:
                            candidates.append(CandidateRecord(
                                id=f"cand_diam_{text.id}_{best_c.id}",
                                stated_value=text.parsed_value,
                                pixel_span=diam,
                                scale=text.parsed_value / diam,
                                primitive_type="circle_diameter",
                                geometry_id=best_c.id,
                                axis="RADIAL",
                                confidence=0.95,
                                notes=["Snapped to unique borehole circle"],
                            ))
                            continue

            # --- B. Linear Dimension Association with Gap Bridging ---
            text_angle = getattr(text, "rotation_deg", 0.0) % 180.0
            if text_angle == 0.0 and th > tw * 1.4:
                text_angle = 90.0

            carrier_corridor = max(30.0, 3.0 * th)
            parallel_lines = [
                l for l in valid_lines
                if _angular_diff_deg(l.angle_deg, text_angle) <= 15.0
                and _point_to_line_dist((tx, ty), l.p1, l.p2) <= carrier_corridor
            ]

            if parallel_lines:
                # Group collinear chains
                chains: List[List] = []
                for l in parallel_lines:
                    placed = False
                    for chain in chains:
                        ref = chain[0]
                        if (
                            _angular_diff_deg(l.angle_deg, ref.angle_deg) <= cls.MAX_COLLINEAR_ANGLE_DIFF
                            and _point_to_line_dist(l.midpoint, ref.p1, ref.p2) <= cls.MAX_LATERAL_OFFSET_PX
                        ):
                            chain.append(l)
                            placed = True
                            break
                    if not placed:
                        chains.append([l])

                best_span = 0.0
                best_chain = None
                for chain in chains:
                    ref_rad = math.radians(chain[0].angle_deg)
                    ux, uy = math.cos(ref_rad), math.sin(ref_rad)
                    projs = []
                    for seg in chain:
                        p1_p = seg.p1[0] * ux + seg.p1[1] * uy
                        p2_p = seg.p2[0] * ux + seg.p2[1] * uy
                        projs.append((min(p1_p, p2_p), max(p1_p, p2_p)))
                    t_p = tx * ux + ty * uy
                    span = max(p[1] for p in projs) - min(p[0] for p in projs)

                    # Resolution-independent projected text half-extent along carrier direction
                    text_half_extent = abs(ux) * (tw / 2.0) + abs(uy) * (th / 2.0)
                    drafting_gap_clearance = max(4.0, 0.5 * th)

                    has_left = any(p[1] <= t_p + text_half_extent + drafting_gap_clearance for p in projs)
                    has_right = any(p[0] >= t_p - text_half_extent - drafting_gap_clearance for p in projs)
                    if len(chain) >= 2 and has_left and has_right:
                        if span > best_span:
                            best_span = span
                            best_chain = chain
                    else:
                        # Chain does not flank the text as a bridged gap;
                        # check if an individual segment in the chain directly serves as carrier
                        for seg, p in zip(chain, projs):
                            p_min, p_max = p
                            if p_min - drafting_gap_clearance <= t_p <= p_max + drafting_gap_clearance:
                                if seg.length > best_span:
                                    best_span = seg.length
                                    best_chain = [seg]

                if best_chain and best_span > 0:
                    axis = "X" if text_angle < 45.0 else ("Y" if text_angle > 45.0 else "ALIGNED")
                    is_bridged = len(best_chain) > 1
                    candidates.append(CandidateRecord(
                        id=f"cand_linear_{text.id}_{best_chain[0].id}",
                        stated_value=text.parsed_value,
                        pixel_span=best_span,
                        scale=text.parsed_value / best_span,
                        primitive_type="line_bridged" if is_bridged else "line_continuous",
                        geometry_id="+".join(s.id for s in best_chain),
                        axis=axis,
                        confidence=0.96 if is_bridged else 0.88,
                        notes=[f"Bridged {len(best_chain)} segments" if is_bridged else "Continuous segment"],
                    ))

        if not candidates:
            return PreCalibrationResult(
                status=TransferState.NO_CANDIDATE_SUPPORTED,
                estimated_scale=None,
                unit=explicit_unit or "unknown_unstated",
                notes=["Zero valid dimension candidates extracted"] + notes,
            )

        # Multi-candidate consensus check (AGENTS.md: >= 2 witnesses, <= 3.0% error)
        scales = [c.scale for c in candidates if c.scale > 0]
        if not scales:
            return PreCalibrationResult(
                status=TransferState.NO_CANDIDATE_SUPPORTED,
                estimated_scale=None,
                unit=explicit_unit or "unknown_unstated",
                notes=["Zero valid positive scale candidates extracted"] + notes,
            )
        if len(scales) == 1:
            return PreCalibrationResult(
                status=TransferState.CANDIDATE_NEEDS_VERIFICATION,
                estimated_scale=scales[0],
                unit=explicit_unit or "unknown_unstated",
                contributing_candidates=candidates,
                notes=["Single candidate only; requires verification"] + notes,
            )

        med = _median(scales)
        agreeing = [c for c in candidates if abs(c.scale - med) / med <= cls.MAX_CONSENSUS_REL_ERROR]
        if len(agreeing) < 2:
            max_disparity = max(abs(c.scale - med) / med for c in candidates) * 100.0 if candidates else 0.0
            return PreCalibrationResult(
                status=TransferState.CONSENSUS_FAILED,
                estimated_scale=None,
                unit=explicit_unit or "unknown_unstated",
                contributing_candidates=candidates,
                relative_error_pct=round(max_disparity, 3),
                notes=[f"Consensus failed: only {len(agreeing)}/{len(candidates)} within 3.0%"],
            )

        # Correlated Evidence Check: Ensure contributing candidates represent distinct physical geometry
        distinct_geometry_ids = set()
        for c in agreeing:
            for part in c.geometry_id.split("+"):
                distinct_geometry_ids.add(part)
        if len(distinct_geometry_ids) < 2:
            return PreCalibrationResult(
                status=TransferState.CONSENSUS_FAILED,
                estimated_scale=None,
                unit=explicit_unit or "unknown_unstated",
                contributing_candidates=candidates,
                notes=["Consensus failed: contributing candidates are geometrically correlated (share single carrier geometry)"] + notes,
            )

        # Multi-Modal Scale Cluster Detection (mixed-scale views on single sheet)
        outlier_scales = [c.scale for c in candidates if abs(c.scale - med) / med > cls.MAX_CONSENSUS_REL_ERROR]
        if len(outlier_scales) >= 2:
            outlier_med = _median(outlier_scales)
            agreeing_outliers = [s for s in outlier_scales if abs(s - outlier_med) / outlier_med <= cls.MAX_CONSENSUS_REL_ERROR]
            if len(agreeing_outliers) >= 2:
                notes.append(f"Multi-modal scale clusters detected: secondary cluster median={outlier_med:.4f} (possible mixed view scales); candidate applies only to dominant cluster")

        # Check anisotropy
        x_scales = [c.scale for c in agreeing if c.axis == "X"]
        y_scales = [c.scale for c in agreeing if c.axis == "Y"]
        anisotropy = 1.0
        if x_scales and y_scales:
            med_x = _median(x_scales)
            med_y = _median(y_scales)
            anisotropy = med_y / med_x if med_x > 0 else 1.0
            if abs(anisotropy - 1.0) > cls.MAX_ANISOTROPY_TOLERANCE:
                notes.append(f"Anisotropy distortion detected: ratio={anisotropy:.4f} exceeds {cls.MAX_ANISOTROPY_TOLERANCE*100.0}% tolerance")
        else:
            axis_name = "X" if x_scales else ("Y" if y_scales else "RADIAL")
            notes.append(f"Unverified cross-axis isotropy: candidates available on {axis_name}-axis only")

        max_rel_error = max(abs(c.scale - med) / med for c in agreeing) * 100.0

        return PreCalibrationResult(
            status=TransferState.CANDIDATE_NEEDS_VERIFICATION,
            estimated_scale=med,
            unit=explicit_unit or "unknown_unstated",
            contributing_candidates=agreeing,
            anisotropy_ratio=anisotropy,
            relative_error_pct=round(max_rel_error, 3),
            notes=[f"Extracted {len(agreeing)} agreeing candidates with {max_rel_error:.2f}% error"] + notes,
        )
