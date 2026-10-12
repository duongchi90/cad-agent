"""Reference implementation of Strategies A-D for Cross-Validation Primitive Association.

Addresses core limitations in primitive_ir_lib/cross_validation.py and
primitive_ir_lib/calibration.py:
1. Angle filter bypass for horizontal 0° text (rotation_deg % 180 == 0).
2. Midpoint Euclidean distance trap causing staggered text to pair with orthogonal witness lines.
3. Lack of mutual exclusion / bipartite assignment leading to line stealing across chained dimensions.
4. Total blindness to circular/arc dimensions (Ø and R callouts).
5. Lack of perpendicular vs axial corridor decomposition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Literal, Dict, Any
import numpy as np


@dataclass
class RawLine:
    id: str
    p1_px: Tuple[float, float]
    p2_px: Tuple[float, float]
    confidence: float = 1.0
    bbox_px: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def __post_init__(self):
        if self.bbox_px == (0.0, 0.0, 0.0, 0.0):
            x1, y1 = self.p1_px
            x2, y2 = self.p2_px
            self.bbox_px = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

    def length_px(self) -> float:
        return float(math.hypot(self.p2_px[0] - self.p1_px[0], self.p2_px[1] - self.p1_px[1]))


@dataclass
class RawCircle:
    id: str
    center_px: Tuple[float, float]
    radius_px: float
    confidence: float = 1.0
    bbox_px: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def __post_init__(self):
        if self.bbox_px == (0.0, 0.0, 0.0, 0.0):
            cx, cy = self.center_px
            r = self.radius_px
            self.bbox_px = (cx - r, cy - r, cx + r, cy + r)


@dataclass
class RawArc:
    id: str
    center_px: Tuple[float, float]
    radius_px: float
    start_angle_deg: float
    end_angle_deg: float
    confidence: float = 1.0
    bbox_px: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def __post_init__(self):
        if self.bbox_px == (0.0, 0.0, 0.0, 0.0):
            cx, cy = self.center_px
            r = self.radius_px
            self.bbox_px = (cx - r, cy - r, cx + r, cy + r)


@dataclass
class RawText:
    id: str
    content: str
    bbox_px: Tuple[float, float, float, float]
    rotation_deg: float = 0.0
    confidence: float = 1.0
    source: str = "text_tesseract"
    parsed_value: Optional[float] = None
    semantic_role: str = "dimension_value"
    callout_type: str = "linear"  # "linear", "diameter", "radius"


@dataclass
class Calibration:
    pixel_to_unit_scale: float
    unit: str = "mm"
    origin_px: Tuple[float, float] = (0.0, 0.0)
    method: str = "known_dimension_reference"
    status: str = "verified"


@dataclass
class AssociationResult:
    text_id: str
    geometry_id: str
    geometry_type: str  # "line", "circle", "arc", "none"
    status: str  # "confirmed", "conflict", "unverified", "ambiguous"
    text_value: Optional[float]
    measured_value: Optional[float]
    delta_percent: Optional[float]
    association_cost: float
    strategy: str


# Helper math functions
def _bbox_center(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _line_angle_deg(line: RawLine) -> float:
    dx = line.p2_px[0] - line.p1_px[0]
    dy = line.p2_px[1] - line.p1_px[1]
    deg = math.degrees(math.atan2(dy, dx)) % 180.0
    return deg


def _angular_diff_deg(a: float, b: float) -> float:
    diff = abs((a % 180.0) - (b % 180.0))
    if diff > 90.0:
        diff = 180.0 - diff
    return diff


def _is_finite_val(val: float) -> bool:
    return not (math.isnan(val) or math.isinf(val))


# ---------------------------------------------------------------------------
# Strategy A: Current Production Baseline
# (Exact emulation of primitive_ir_lib/calibration.py and cross_validation.py)
# ---------------------------------------------------------------------------
def _find_nearest_line_production_a(
    text: RawText,
    lines: List[RawLine],
    max_distance_px: float = 150.0,
    angle_tolerance_deg: float = 20.0,
) -> Optional[RawLine]:
    tx, ty = _bbox_center(text.bbox_px)
    # Production flaw: disabled when rotation_deg % 180 == 0.0!
    apply_angle_filter = (text.rotation_deg % 180.0) != 0.0
    text_angle = text.rotation_deg % 180.0

    candidates: List[Tuple[RawLine, float]] = []
    for line in lines:
        if apply_angle_filter:
            if _angular_diff_deg(_line_angle_deg(line), text_angle) > angle_tolerance_deg:
                continue
        mx = (line.p1_px[0] + line.p2_px[0]) / 2.0
        my = (line.p1_px[1] + line.p2_px[1]) / 2.0
        dist = float(math.hypot(mx - tx, my - ty))
        if dist <= max_distance_px:
            candidates.append((line, dist))

    if not candidates:
        return None

    best_line, _ = min(candidates, key=lambda item: item[1])
    return best_line


def strategy_a_cross_validate(
    raw_texts: List[RawText],
    raw_lines: List[RawLine],
    calibration: Calibration,
    threshold_percent: float = 3.0,
    max_distance_px: float = 150.0,
) -> List[AssociationResult]:
    results: List[AssociationResult] = []

    for text in raw_texts:
        if text.semantic_role != "dimension_value" or text.parsed_value is None:
            continue

        if text.parsed_value == 0:
            results.append(
                AssociationResult(
                    text_id=text.id,
                    geometry_id="",
                    geometry_type="none",
                    status="unverified",
                    text_value=text.parsed_value,
                    measured_value=None,
                    delta_percent=None,
                    association_cost=math.inf,
                    strategy="STRATEGY_A_BASELINE",
                )
            )
            continue

        line = _find_nearest_line_production_a(text, raw_lines, max_distance_px=max_distance_px)

        if line is None:
            results.append(
                AssociationResult(
                    text_id=text.id,
                    geometry_id="",
                    geometry_type="none",
                    status="unverified",
                    text_value=text.parsed_value,
                    measured_value=None,
                    delta_percent=None,
                    association_cost=math.inf,
                    strategy="STRATEGY_A_BASELINE",
                )
            )
            continue

        measured = line.length_px() * calibration.pixel_to_unit_scale
        delta_percent = abs(text.parsed_value - measured) / text.parsed_value * 100.0
        status = "confirmed" if delta_percent <= threshold_percent else "conflict"

        results.append(
            AssociationResult(
                text_id=text.id,
                geometry_id=line.id,
                geometry_type="line",
                status=status,
                text_value=text.parsed_value,
                measured_value=round(measured, 3),
                delta_percent=round(delta_percent, 4),
                association_cost=0.0,
                strategy="STRATEGY_A_BASELINE",
            )
        )

    return results


# ---------------------------------------------------------------------------
# Strategy B: Angle-Enforced Midpoint Matcher
# (Always applies angular filter regardless of 0° rotation, but still midpoint dist)
# ---------------------------------------------------------------------------
def _find_nearest_line_strategy_b(
    text: RawText,
    lines: List[RawLine],
    max_distance_px: float = 150.0,
    angle_tolerance_deg: float = 20.0,
) -> Optional[RawLine]:
    tx, ty = _bbox_center(text.bbox_px)
    text_angle = text.rotation_deg % 180.0

    candidates: List[Tuple[RawLine, float]] = []
    for line in lines:
        # Enforce angle filter for ALL text rotations
        if _angular_diff_deg(_line_angle_deg(line), text_angle) > angle_tolerance_deg:
            continue
        mx = (line.p1_px[0] + line.p2_px[0]) / 2.0
        my = (line.p1_px[1] + line.p2_px[1]) / 2.0
        dist = float(math.hypot(mx - tx, my - ty))
        if dist <= max_distance_px:
            candidates.append((line, dist))

    if not candidates:
        return None

    best_line, _ = min(candidates, key=lambda item: item[1])
    return best_line


def strategy_b_cross_validate(
    raw_texts: List[RawText],
    raw_lines: List[RawLine],
    calibration: Calibration,
    threshold_percent: float = 3.0,
    max_distance_px: float = 150.0,
) -> List[AssociationResult]:
    results: List[AssociationResult] = []

    for text in raw_texts:
        if text.semantic_role != "dimension_value" or text.parsed_value is None:
            continue

        if text.parsed_value == 0:
            results.append(
                AssociationResult(
                    text_id=text.id,
                    geometry_id="",
                    geometry_type="none",
                    status="unverified",
                    text_value=text.parsed_value,
                    measured_value=None,
                    delta_percent=None,
                    association_cost=math.inf,
                    strategy="STRATEGY_B_ANGLE_ENFORCED",
                )
            )
            continue

        line = _find_nearest_line_strategy_b(text, raw_lines, max_distance_px=max_distance_px)

        if line is None:
            results.append(
                AssociationResult(
                    text_id=text.id,
                    geometry_id="",
                    geometry_type="none",
                    status="unverified",
                    text_value=text.parsed_value,
                    measured_value=None,
                    delta_percent=None,
                    association_cost=math.inf,
                    strategy="STRATEGY_B_ANGLE_ENFORCED",
                )
            )
            continue

        measured = line.length_px() * calibration.pixel_to_unit_scale
        delta_percent = abs(text.parsed_value - measured) / text.parsed_value * 100.0
        status = "confirmed" if delta_percent <= threshold_percent else "conflict"

        results.append(
            AssociationResult(
                text_id=text.id,
                geometry_id=line.id,
                geometry_type="line",
                status=status,
                text_value=text.parsed_value,
                measured_value=round(measured, 3),
                delta_percent=round(delta_percent, 4),
                association_cost=0.0,
                strategy="STRATEGY_B_ANGLE_ENFORCED",
            )
        )

    return results


# ---------------------------------------------------------------------------
# Strategy C: Perpendicular-Axial Corridor Matcher (Greedy 1-pass)
# Decomposes distance into perpendicular offset and axial interval check
# ---------------------------------------------------------------------------
def _corridor_distance_line(
    tx: float,
    ty: float,
    line: RawLine,
    max_perp_dist_px: float = 40.0,
    axial_margin_px: float = 30.0,
) -> Optional[float]:
    x1, y1 = line.p1_px
    x2, y2 = line.p2_px
    dx = x2 - x1
    dy = y2 - y1
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return None

    # Unit vectors
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux

    # Vector from p1 to text
    vx = tx - x1
    vy = ty - y1

    # Projections
    s = vx * ux + vy * uy
    d_perp = abs(vx * nx + vy * ny)

    if d_perp > max_perp_dist_px:
        return None

    if s < -axial_margin_px or s > L + axial_margin_px:
        return None

    # Combined corridor score: primarily perpendicular distance + small axial centering penalty
    axial_center_offset = abs(s - L / 2.0)
    score = d_perp + 0.1 * axial_center_offset
    return score


def strategy_c_cross_validate(
    raw_texts: List[RawText],
    raw_lines: List[RawLine],
    calibration: Calibration,
    threshold_percent: float = 3.0,
    max_perp_dist_px: float = 40.0,
    axial_margin_px: float = 30.0,
    angle_tolerance_deg: float = 20.0,
) -> List[AssociationResult]:
    results: List[AssociationResult] = []

    for text in raw_texts:
        if text.semantic_role != "dimension_value" or text.parsed_value is None:
            continue

        if text.parsed_value == 0:
            results.append(
                AssociationResult(
                    text_id=text.id,
                    geometry_id="",
                    geometry_type="none",
                    status="unverified",
                    text_value=text.parsed_value,
                    measured_value=None,
                    delta_percent=None,
                    association_cost=math.inf,
                    strategy="STRATEGY_C_CORRIDOR",
                )
            )
            continue

        tx, ty = _bbox_center(text.bbox_px)
        text_angle = text.rotation_deg % 180.0

        candidates: List[Tuple[RawLine, float]] = []
        for line in raw_lines:
            if _angular_diff_deg(_line_angle_deg(line), text_angle) > angle_tolerance_deg:
                continue
            score = _corridor_distance_line(tx, ty, line, max_perp_dist_px, axial_margin_px)
            if score is not None:
                candidates.append((line, score))

        if not candidates:
            results.append(
                AssociationResult(
                    text_id=text.id,
                    geometry_id="",
                    geometry_type="none",
                    status="unverified",
                    text_value=text.parsed_value,
                    measured_value=None,
                    delta_percent=None,
                    association_cost=math.inf,
                    strategy="STRATEGY_C_CORRIDOR",
                )
            )
            continue

        best_line, best_score = min(candidates, key=lambda item: item[1])
        measured = best_line.length_px() * calibration.pixel_to_unit_scale
        delta_percent = abs(text.parsed_value - measured) / text.parsed_value * 100.0
        status = "confirmed" if delta_percent <= threshold_percent else "conflict"

        results.append(
            AssociationResult(
                text_id=text.id,
                geometry_id=best_line.id,
                geometry_type="line",
                status=status,
                text_value=text.parsed_value,
                measured_value=round(measured, 3),
                delta_percent=round(delta_percent, 4),
                association_cost=round(best_score, 4),
                strategy="STRATEGY_C_CORRIDOR",
            )
        )

    return results


# ---------------------------------------------------------------------------
# Strategy D: Multimodal Bipartite Association Oracle
# 1. Multi-Geometry: supports RawLine, RawCircle, RawArc.
# 2. Callout awareness: Ø -> circle/arc diameter (2*R), R -> arc/circle radius (R).
# 3. Corridor scoring for lines, radial boundary scoring for circles/arcs.
# 4. Global Bipartite Matching: prevents duplicate line stealing across chained dimensions.
# 5. Ambiguity guard: detects equidistant ambiguous candidates.
# 6. Degenerate & non-finite guards.
# ---------------------------------------------------------------------------
@dataclass
class GeometricCandidate:
    id: str
    geom_type: str  # "line", "circle", "arc"
    entity: Any
    measured_cad_val_primary: float  # length or 2*R or R
    measured_cad_val_secondary: Optional[float] = None  # e.g. R for circle if primary is 2*R


def _evaluate_candidate_cost(
    text: RawText,
    cand: GeometricCandidate,
    calibration: Calibration,
    max_perp_dist_px: float = 40.0,
    axial_margin_px: float = 30.0,
    max_radial_dist_px: float = 60.0,
    angle_tolerance_deg: float = 20.0,
) -> Optional[Tuple[float, float]]:
    """Returns (cost, best_measured_val) or None if geometrically incompatible."""
    if text.parsed_value is None or text.parsed_value <= 0:
        return None

    tx, ty = _bbox_center(text.bbox_px)
    if not (_is_finite_val(tx) and _is_finite_val(ty)):
        return None

    if cand.geom_type == "line":
        # Callouts explicitly marked diameter or radius do not pair with lines
        if text.callout_type in ("diameter", "radius"):
            return None

        line: RawLine = cand.entity
        x1, y1 = line.p1_px
        x2, y2 = line.p2_px
        if not all(_is_finite_val(v) for v in (x1, y1, x2, y2)):
            return None

        dx = x2 - x1
        dy = y2 - y1
        L = math.hypot(dx, dy)
        if L < 1.0:
            return None

        # Angular alignment check
        text_angle = text.rotation_deg % 180.0
        line_ang = _line_angle_deg(line)
        ang_diff = _angular_diff_deg(line_ang, text_angle)
        if ang_diff > angle_tolerance_deg:
            return None

        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux

        vx = tx - x1
        vy = ty - y1

        s = vx * ux + vy * uy
        d_perp = abs(vx * nx + vy * ny)

        if d_perp > max_perp_dist_px:
            return None

        if s < -axial_margin_px or s > L + axial_margin_px:
            return None

        measured = cand.measured_cad_val_primary
        delta_pct = abs(text.parsed_value - measured) / text.parsed_value * 100.0

        # Weighted cost: perpendicular distance + axial center drift + length delta
        norm_perp = d_perp / max_perp_dist_px
        norm_axial = abs(s - L / 2.0) / (L / 2.0 + axial_margin_px)
        norm_ang = ang_diff / angle_tolerance_deg
        cost = 1.0 * norm_perp + 0.3 * norm_axial + 0.2 * norm_ang + 0.05 * min(delta_pct, 100.0)
        return (cost, measured)

    elif cand.geom_type in ("circle", "arc"):
        cx, cy = cand.entity.center_px
        r = cand.entity.radius_px
        if not (_is_finite_val(cx) and _is_finite_val(cy) and _is_finite_val(r)) or r < 1.0:
            return None

        # Distance from text center to circle boundary
        dist_to_center = math.hypot(tx - cx, ty - cy)
        dist_to_boundary = abs(dist_to_center - r)

        if dist_to_boundary > max_radial_dist_px:
            return None

        if cand.geom_type == "circle":
            diam_val = cand.measured_cad_val_primary
            rad_val = cand.measured_cad_val_secondary if cand.measured_cad_val_secondary is not None else diam_val / 2.0
        else:  # arc
            rad_val = cand.measured_cad_val_primary
            diam_val = cand.measured_cad_val_secondary if cand.measured_cad_val_secondary is not None else rad_val * 2.0

        if text.callout_type == "radius":
            best_val = rad_val
        elif text.callout_type == "diameter":
            best_val = diam_val
        else:
            err_diam = abs(text.parsed_value - diam_val)
            err_rad = abs(text.parsed_value - rad_val)
            best_val = diam_val if err_diam <= err_rad else rad_val

        delta_pct = abs(text.parsed_value - best_val) / text.parsed_value * 100.0
        norm_radial = dist_to_boundary / max_radial_dist_px
        cost = 1.0 * norm_radial + 0.05 * min(delta_pct, 100.0)
        return (cost, best_val)

    return None


def _solve_min_cost_bipartite_matching(
    cost_matrix: np.ndarray,
) -> List[Tuple[int, int]]:
    """Solve minimum weight bipartite matching using Hungarian algorithm if available,

    or greedy augmenting assignment.
    """
    num_texts, num_cands = cost_matrix.shape
    if num_texts == 0 or num_cands == 0:
        return []

    try:
        from scipy.optimize import linear_sum_assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        matches = []
        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] < 1e8:  # Valid assignment
                matches.append((int(r), int(c)))
        return matches
    except ImportError:
        # High-quality greedy fallback
        matches = []
        used_rows = set()
        used_cols = set()

        # Sort all valid entries by cost
        entries = []
        for r in range(num_texts):
            for c in range(num_cands):
                if cost_matrix[r, c] < 1e8:
                    entries.append((cost_matrix[r, c], r, c))
        entries.sort(key=lambda x: x[0])

        for cost, r, c in entries:
            if r not in used_rows and c not in used_cols:
                used_rows.add(r)
                used_cols.add(c)
                matches.append((r, c))
        return matches


def strategy_d_cross_validate(
    raw_texts: List[RawText],
    raw_lines: Optional[List[RawLine]] = None,
    raw_circles: Optional[List[RawCircle]] = None,
    raw_arcs: Optional[List[RawArc]] = None,
    calibration: Optional[Calibration] = None,
    threshold_percent: float = 3.0,
    max_perp_dist_px: float = 40.0,
    axial_margin_px: float = 30.0,
    max_radial_dist_px: float = 60.0,
    angle_tolerance_deg: float = 20.0,
    ambiguity_margin: float = 0.02,
) -> List[AssociationResult]:
    """Strategy D: Multimodal Bipartite Association Oracle."""
    if raw_lines is None:
        raw_lines = []
    if raw_circles is None:
        raw_circles = []
    if raw_arcs is None:
        raw_arcs = []
    if calibration is None:
        calibration = Calibration(pixel_to_unit_scale=1.0)

    scale = calibration.pixel_to_unit_scale

    # Build geometric candidates pool
    candidates: List[GeometricCandidate] = []
    for line in raw_lines:
        candidates.append(
            GeometricCandidate(
                id=line.id,
                geom_type="line",
                entity=line,
                measured_cad_val_primary=line.length_px() * scale,
            )
        )
    for circle in raw_circles:
        candidates.append(
            GeometricCandidate(
                id=circle.id,
                geom_type="circle",
                entity=circle,
                measured_cad_val_primary=circle.radius_px * 2.0 * scale,  # Diameter
                measured_cad_val_secondary=circle.radius_px * scale,  # Radius
            )
        )
    for arc in raw_arcs:
        candidates.append(
            GeometricCandidate(
                id=arc.id,
                geom_type="arc",
                entity=arc,
                measured_cad_val_primary=arc.radius_px * scale,  # Radius
                measured_cad_val_secondary=arc.radius_px * 2.0 * scale,  # Diameter
            )
        )

    # Filter texts eligible for dimension verification
    valid_texts: List[RawText] = []
    for text in raw_texts:
        valid_texts.append(text)

    if not valid_texts:
        return []

    if not candidates:
        # All texts unverified
        return [
            AssociationResult(
                text_id=t.id,
                geometry_id="",
                geometry_type="none",
                status="unverified",
                text_value=t.parsed_value,
                measured_value=None,
                delta_percent=None,
                association_cost=math.inf,
                strategy="STRATEGY_D_MULTIMODAL_BIPARTITE",
            )
            for t in valid_texts
        ]

    # Build cost matrix
    num_texts = len(valid_texts)
    num_cands = len(candidates)
    INF_COST = 1e9
    cost_matrix = np.full((num_texts, num_cands), INF_COST, dtype=np.float64)
    measured_matrix = np.full((num_texts, num_cands), np.nan, dtype=np.float64)

    for i, text in enumerate(valid_texts):
        if text.semantic_role != "dimension_value" or text.parsed_value is None or text.parsed_value == 0:
            continue
        for j, cand in enumerate(candidates):
            eval_res = _evaluate_candidate_cost(
                text,
                cand,
                calibration,
                max_perp_dist_px=max_perp_dist_px,
                axial_margin_px=axial_margin_px,
                max_radial_dist_px=max_radial_dist_px,
                angle_tolerance_deg=angle_tolerance_deg,
            )
            if eval_res is not None:
                cost, measured = eval_res
                cost_matrix[i, j] = cost
                measured_matrix[i, j] = measured

    # Solve bipartite assignment
    matches = _solve_min_cost_bipartite_matching(cost_matrix)
    match_dict: Dict[int, int] = {t_idx: c_idx for t_idx, c_idx in matches}

    results: List[AssociationResult] = []
    for i, text in enumerate(valid_texts):
        if text.semantic_role != "dimension_value" or text.parsed_value is None:
            continue

        if text.parsed_value == 0:
            results.append(
                AssociationResult(
                    text_id=text.id,
                    geometry_id="",
                    geometry_type="none",
                    status="unverified",
                    text_value=text.parsed_value,
                    measured_value=None,
                    delta_percent=None,
                    association_cost=math.inf,
                    strategy="STRATEGY_D_MULTIMODAL_BIPARTITE",
                )
            )
            continue

        if i not in match_dict:
            results.append(
                AssociationResult(
                    text_id=text.id,
                    geometry_id="",
                    geometry_type="none",
                    status="unverified",
                    text_value=text.parsed_value,
                    measured_value=None,
                    delta_percent=None,
                    association_cost=math.inf,
                    strategy="STRATEGY_D_MULTIMODAL_BIPARTITE",
                )
            )
            continue

        best_cand_idx = match_dict[i]
        best_cost = cost_matrix[i, best_cand_idx]
        best_cand = candidates[best_cand_idx]
        measured = float(measured_matrix[i, best_cand_idx])

        # Ambiguity check: check if any other candidate has virtually identical cost but different length
        row_costs = cost_matrix[i, :].copy()
        row_costs[best_cand_idx] = INF_COST
        second_best_idx = int(np.argmin(row_costs))
        second_best_cost = float(row_costs[second_best_idx])

        is_ambiguous = False
        if second_best_cost < INF_COST:
            if abs(second_best_cost - best_cost) < ambiguity_margin:
                second_cand = candidates[second_best_idx]
                second_meas = float(measured_matrix[i, second_best_idx])
                # If they measure significantly different CAD lengths, it is genuinely ambiguous
                if abs(second_meas - measured) > (text.parsed_value * threshold_percent / 100.0):
                    is_ambiguous = True

        if is_ambiguous:
            results.append(
                AssociationResult(
                    text_id=text.id,
                    geometry_id=best_cand.id,
                    geometry_type=best_cand.geom_type,
                    status="ambiguous",
                    text_value=text.parsed_value,
                    measured_value=round(measured, 3),
                    delta_percent=round(abs(text.parsed_value - measured) / text.parsed_value * 100.0, 4),
                    association_cost=round(best_cost, 4),
                    strategy="STRATEGY_D_MULTIMODAL_BIPARTITE",
                )
            )
            continue

        delta_percent = abs(text.parsed_value - measured) / text.parsed_value * 100.0
        status = "confirmed" if delta_percent <= threshold_percent else "conflict"

        results.append(
            AssociationResult(
                text_id=text.id,
                geometry_id=best_cand.id,
                geometry_type=best_cand.geom_type,
                status=status,
                text_value=text.parsed_value,
                measured_value=round(measured, 3),
                delta_percent=round(delta_percent, 4),
                association_cost=round(best_cost, 4),
                strategy="STRATEGY_D_MULTIMODAL_BIPARTITE",
            )
        )

    return results
