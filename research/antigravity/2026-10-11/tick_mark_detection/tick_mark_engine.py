"""
tick_mark_engine.py — Reference Engine for Tick Mark and Boundary Symbol Detection Strategies A, B, C, D.

Empirically benchmarks and compares dimension boundary detection algorithms:
- Strategy A: Current Production Main (primitive_ir_lib/tick_mark_detection.py)
- Strategy B: Naive Two-Segment Angle Matcher (checks 2 segments, fails on acute arrows & diagonals)
- Strategy C: Orientation-Rotated Column Projection (rotation invariant, but fails on oblique slashes)
- Strategy D: Multi-Model Boundary Oracle (Rotated-frame projection, dual-symmetry arrowhead scoring, architectural oblique slash filter, hatch & text descender rejection)
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Sequence, Dict, Any

_repo_root = str(Path(__file__).resolve().parents[4])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import cv2
import numpy as np

from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.models import new_id
from primitive_ir_lib.tick_mark_detection import (
    detect_tick_mark_at_point as detect_tick_mark_strategy_a,
    find_internal_boundary_offsets as find_internal_offsets_strategy_a,
    split_raw_line_at_internal_witness_lines as split_lines_strategy_a,
    _perpendicular_witness_at_point as perp_witness_strategy_a,
)


@dataclass(frozen=True)
class BoundarySymbolEvidence:
    has_boundary: bool
    symbol_kind: str  # "NONE", "OBLIQUE_TICK", "ARROWHEAD", "PERPENDICULAR_WITNESS"
    confidence: float
    detected_points: Tuple[Tuple[float, float], ...] = ()


def make_raw_line(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    id_: str = "",
) -> RawLine:
    x1, y1 = float(p1[0]), float(p1[1])
    x2, y2 = float(p2[0]), float(p2[1])
    bbox = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    return RawLine(
        id=id_ or new_id("line"),
        p1_px=(x1, y1),
        p2_px=(x2, y2),
        confidence=0.9,
        bbox_px=bbox,
    )


# ---------------------------------------------------------------------------
# Strategy A: Current Production Main
# ---------------------------------------------------------------------------

def run_strategy_a_endpoint(
    image_bgr: Optional[np.ndarray],
    point: Tuple[float, float],
    ref_angle: float,
) -> BoundarySymbolEvidence:
    """Strategy A: Production detect_tick_mark_at_point."""
    hit = detect_tick_mark_strategy_a(
        image_bgr, point, ref_angle,
        window_px=20.0,
        diagonal_angle_min_deg=25.0,
        diagonal_angle_max_deg=65.0,
        proximity_px=6.0,
        min_segments=1,
    )
    return BoundarySymbolEvidence(
        has_boundary=hit,
        symbol_kind="OBLIQUE_TICK" if hit else "NONE",
        confidence=0.85 if hit else 0.0,
        detected_points=(point,) if hit else (),
    )


def run_strategy_a_split(
    line: RawLine,
    image_bgr: Optional[np.ndarray],
) -> List[RawLine]:
    """Strategy A: Production split_raw_line_at_internal_witness_lines."""
    return split_lines_strategy_a(line, image_bgr)


# ---------------------------------------------------------------------------
# Strategy B: Naive Two-Segment Angle Matcher
# ---------------------------------------------------------------------------

def run_strategy_b_endpoint(
    image_bgr: Optional[np.ndarray],
    point: Tuple[float, float],
    ref_angle: float,
    window_px: float = 20.0,
) -> BoundarySymbolEvidence:
    """Strategy B: Requires at least 2 diagonal segments, but still unrotated patch."""
    hit = detect_tick_mark_strategy_a(
        image_bgr, point, ref_angle,
        window_px=window_px,
        diagonal_angle_min_deg=25.0,
        diagonal_angle_max_deg=65.0,
        proximity_px=6.0,
        min_segments=2,
    )
    return BoundarySymbolEvidence(
        has_boundary=hit,
        symbol_kind="ARROWHEAD" if hit else "NONE",
        confidence=0.85 if hit else 0.0,
        detected_points=(point,) if hit else (),
    )


def run_strategy_b_split(
    line: RawLine,
    image_bgr: Optional[np.ndarray],
) -> List[RawLine]:
    """Strategy B: Does not support internal line splitting."""
    return [line]


# ---------------------------------------------------------------------------
# Strategy C: Orientation-Rotated Column Projection
# ---------------------------------------------------------------------------

def run_strategy_c_endpoint(
    image_bgr: Optional[np.ndarray],
    point: Tuple[float, float],
    ref_angle_rad: float,
) -> BoundarySymbolEvidence:
    """Strategy C: Only detects orthogonal 90-degree crossing lines."""
    if image_bgr is None:
        return BoundarySymbolEvidence(False, "NONE", 0.0)
    gray = image_bgr if image_bgr.ndim == 2 else cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    patch, _ = _crop_and_rotate_patch(gray, point, ref_angle_rad, patch_size=32)
    # Checks 90 degree column projection only
    edges = cv2.Canny(patch, 50, 150)
    segs = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=5, minLineLength=5, maxLineGap=2)
    if segs is not None:
        for s in segs.reshape(-1, 4):
            ang = math.degrees(math.atan2(float(s[3] - s[1]), float(s[2] - s[0]))) % 180.0
            rel_ang = ang if ang <= 90.0 else 180.0 - ang
            if 80.0 <= rel_ang <= 90.0:
                return BoundarySymbolEvidence(True, "PERPENDICULAR_WITNESS", 0.85, (point,))
    return BoundarySymbolEvidence(False, "NONE", 0.0)


def run_strategy_c_split(
    line: RawLine,
    image_bgr: Optional[np.ndarray],
) -> List[RawLine]:
    """Strategy C: Normalizes patch rotation, but only checks 90-degree witness lines."""
    if image_bgr is None:
        return [line]
    return split_lines_strategy_a(line, image_bgr)


# ---------------------------------------------------------------------------
# Strategy D: Multi-Model Boundary Oracle
# ---------------------------------------------------------------------------

def run_strategy_d_endpoint(
    image_bgr: Optional[np.ndarray],
    point: Tuple[float, float],
    ref_angle_rad: float,
) -> BoundarySymbolEvidence:
    """Strategy D: Multi-model endpoint symbol detector."""
    return detect_boundary_symbol_at_point(image_bgr, point, ref_angle_rad)


def run_strategy_d_split(
    line: RawLine,
    image_bgr: Optional[np.ndarray],
) -> List[RawLine]:
    """Strategy D: Multi-model line boundary splitter."""
    return split_line_at_boundaries(line, image_bgr)

def _crop_and_rotate_patch(
    gray: np.ndarray,
    center: Tuple[float, float],
    ref_angle_rad: float,
    patch_size: int = 40,
) -> Tuple[np.ndarray, np.ndarray]:
    """Crops a square patch centered at point and rotates it so ref_angle is horizontal (+x).
    Returns (rotated_patch, M_rotation_inverse).
    """
    h_img, w_img = gray.shape[:2]
    cx, cy = center
    half = patch_size / 2.0

    # Expand slightly for rotation bounding
    diag = int(math.ceil(patch_size * 1.414))
    x0 = int(round(cx - diag / 2.0))
    y0 = int(round(cy - diag / 2.0))
    x1 = x0 + diag
    y1 = y0 + diag

    # Pad if outside boundaries
    pad_left = max(0, -x0)
    pad_top = max(0, -y0)
    pad_right = max(0, x1 - w_img)
    pad_bottom = max(0, y1 - h_img)

    crop_x0 = max(0, x0)
    crop_y0 = max(0, y0)
    crop_x1 = min(w_img, x1)
    crop_y1 = min(h_img, y1)

    sub = gray[crop_y0:crop_y1, crop_x0:crop_x1]
    if sub.size == 0:
        return np.full((patch_size, patch_size), 255, dtype=np.uint8), np.eye(3)

    if pad_left > 0 or pad_top > 0 or pad_right > 0 or pad_bottom > 0:
        sub = cv2.copyMakeBorder(sub, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_CONSTANT, value=255)

    # Center of sub
    sub_cx = diag / 2.0
    sub_cy = diag / 2.0

    angle_deg = math.degrees(ref_angle_rad)
    M = cv2.getRotationMatrix2D((sub_cx, sub_cy), -angle_deg, 1.0)
    rotated = cv2.warpAffine(sub, M, (diag, diag), borderValue=255)

    # Crop inner patch_size x patch_size
    px0 = int(round(sub_cx - half))
    py0 = int(round(sub_cy - half))
    final_patch = rotated[py0 : py0 + patch_size, px0 : px0 + patch_size]
    return final_patch, M


def _count_distinct_tracks(
    segs: Sequence[Tuple[int, int, int, int, float]],
    min_cluster_gap: float = 5.0,
) -> int:
    """Counts the maximum number of distinct parallel tracks (spatial offset clusters) at similar angle."""
    max_tracks = 0
    for s1 in segs:
        ang1 = s1[4]
        rad1 = math.radians(ang1)
        offsets: List[float] = []
        for s2 in segs:
            if abs(s2[4] - ang1) <= 8.0:
                mx = (s2[0] + s2[2]) / 2.0
                my = (s2[1] + s2[3]) / 2.0
                off = -mx * math.sin(rad1) + my * math.cos(rad1)
                offsets.append(off)
        if not offsets:
            continue
        offsets.sort()
        clusters = [offsets[0]]
        for o in offsets[1:]:
            if o - clusters[-1] >= min_cluster_gap:
                clusters.append(o)
        if len(clusters) > max_tracks:
            max_tracks = len(clusters)
    return max_tracks


def _is_solid_arrowhead(
    patch: np.ndarray,
    pcx: int,
    pcy: int,
    dark_threshold: int = 180,
) -> bool:
    """Detects solid filled triangular arrowhead (e.g. AutoCAD _CLOSEDFILLED)."""
    _, binary = cv2.threshold(patch, dark_threshold, 255, cv2.THRESH_BINARY_INV)
    if binary[pcy, pcx] == 0:
        return False
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    lbl = int(labels[pcy, pcx])
    if lbl <= 0:
        return False
    x0, y0, w, h, area = stats[lbl]
    # Plain line rejection: transverse height h must be >= 7
    if h < 7 or w < 7:
        return False
    solidity = area / float(w * h)
    if not (0.32 <= solidity <= 0.75):
        return False
    # Symmetry check: must have pixels on both sides of pcy
    pts = np.argwhere(labels == lbl)
    top_pts = np.sum(pts[:, 0] < pcy - 2)
    bot_pts = np.sum(pts[:, 0] > pcy + 2)
    if top_pts == 0 or bot_pts == 0:
        return False
    ratio = min(top_pts, bot_pts) / max(1.0, float(max(top_pts, bot_pts)))
    return ratio >= 0.4


def detect_boundary_symbol_at_point(
    image_bgr: Optional[np.ndarray],
    point: Tuple[float, float],
    ref_angle_rad: float,
    window_px: float = 24.0,
    dark_threshold: int = 180,
) -> BoundarySymbolEvidence:
    """Strategy D: Multi-Model Boundary Detection at line endpoint.

    Rotates patch so reference line points horizontally along +x axis.
    Tests 3 boundary modes:
    1. Oblique Architectural Tick Mark: stroke at 45° (+/- 15°) with no parallel hatch field.
    2. Converging Arrowhead: acute converging strokes (3.5°-35°) or filled triangle.
    3. Perpendicular Witness: orthogonal crossing line at 70°-110° (+/- 20°).
    """
    if image_bgr is None:
        return BoundarySymbolEvidence(False, "NONE", 0.0)

    px, py = point
    if not (math.isfinite(px) and math.isfinite(py) and math.isfinite(ref_angle_rad)):
        return BoundarySymbolEvidence(False, "NONE", 0.0)

    gray = image_bgr if image_bgr.ndim == 2 else cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    patch_size = int(round(window_px * 2.0))
    patch, _ = _crop_and_rotate_patch(gray, point, ref_angle_rad, patch_size=patch_size)

    pcx = patch_size // 2
    pcy = patch_size // 2

    # Check for solid filled arrowhead first
    if _is_solid_arrowhead(patch, pcx, pcy, dark_threshold=dark_threshold):
        return BoundarySymbolEvidence(
            has_boundary=True,
            symbol_kind="ARROWHEAD",
            confidence=0.95,
            detected_points=(point,),
        )

    edges = cv2.Canny(patch, 50, 150)
    segments = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=5, minLineLength=4, maxLineGap=2)
    if segments is None:
        return BoundarySymbolEvidence(False, "NONE", 0.0)

    raw_segs = np.asarray(segments).reshape(-1, 4)

    enriched: List[Tuple[int, int, int, int, float]] = []
    for s in raw_segs:
        x1, y1, x2, y2 = int(s[0]), int(s[1]), int(s[2]), int(s[3])
        ang = math.degrees(math.atan2(float(y2 - y1), float(x2 - x1))) % 180.0
        rel_ang = ang if ang <= 90.0 else 180.0 - ang
        enriched.append((x1, y1, x2, y2, rel_ang))

    # Reject repetitive hatch fields: only consider non-horizontal tracks (rel_ang >= 20.0)
    hatch_candidates = [s for s in enriched if s[4] >= 20.0]
    if len(hatch_candidates) >= 3:
        tracks = _count_distinct_tracks(hatch_candidates, min_cluster_gap=5.0)
        if tracks >= 3:
            return BoundarySymbolEvidence(False, "NONE", 0.0)

    # 1. Check for Acute Converging Arrowhead (wings with angle 3.5°..35° near center)
    wings_top: List[Tuple[float, float]] = []
    wings_bot: List[Tuple[float, float]] = []
    for x1, y1, x2, y2, rel_ang in enriched:
        d = min(math.hypot(x1 - pcx, y1 - pcy), math.hypot(x2 - pcx, y2 - pcy))
        if 3.5 <= rel_ang <= 35.0 and d <= 10.0:
            mid_y = (y1 + y2) / 2.0
            if mid_y <= pcy + 1.0:
                wings_top.append((rel_ang, d))
            if mid_y >= pcy - 1.0:
                wings_bot.append((rel_ang, d))

    if len(wings_top) >= 1 and len(wings_bot) >= 1:
        return BoundarySymbolEvidence(
            has_boundary=True,
            symbol_kind="ARROWHEAD",
            confidence=0.96,
            detected_points=(point,),
        )

    # 2. Check for Oblique Architectural Tick Mark (30°..60°, near center)
    for x1, y1, x2, y2, rel_ang in enriched:
        if 30.0 <= rel_ang <= 60.0:
            d = min(math.hypot(x1 - pcx, y1 - pcy), math.hypot(x2 - pcx, y2 - pcy))
            mid_d = math.hypot((x1 + x2) / 2.0 - pcx, (y1 + y2) / 2.0 - pcy)
            if d <= 8.0 or mid_d <= 8.0:
                return BoundarySymbolEvidence(
                    has_boundary=True,
                    symbol_kind="OBLIQUE_TICK",
                    confidence=0.92,
                    detected_points=(point,),
                )

    # 3. Check for Perpendicular Witness Line (65°..90°, near center)
    for x1, y1, x2, y2, rel_ang in enriched:
        if 65.0 <= rel_ang <= 90.0:
            d = min(math.hypot(x1 - pcx, y1 - pcy), math.hypot(x2 - pcx, y2 - pcy))
            mid_d = math.hypot((x1 + x2) / 2.0 - pcx, (y1 + y2) / 2.0 - pcy)
            if d <= 6.0 or mid_d <= 6.0:
                return BoundarySymbolEvidence(
                    has_boundary=True,
                    symbol_kind="PERPENDICULAR_WITNESS",
                    confidence=0.90,
                    detected_points=(point,),
                )

    return BoundarySymbolEvidence(False, "NONE", 0.0)


def _check_internal_boundary_at_patch(
    patch: np.ndarray,
    dark_threshold: int = 180,
) -> Tuple[bool, str]:
    """Evaluates whether rotated patch contains an internal boundary mark or noise.

    Returns (is_boundary, symbol_kind).
    Distinguishes 1D crossing strokes (witness line, oblique slash) from 2D text glyphs and repetitive hatching.
    """
    ph, pw = patch.shape[:2]
    cx = pw // 2
    cy = ph // 2
    _, binary = cv2.threshold(patch, dark_threshold, 255, cv2.THRESH_BINARY_INV)

    # Erase horizontal corridor
    cleaned = binary.copy()
    cleaned[cy - 2 : cy + 3, :] = 0

    # Must cross dimension line: strokes on BOTH top and bottom near center
    has_top = np.any(cleaned[: cy - 2, cx - 8 : cx + 9] > 0)
    has_bot = np.any(cleaned[cy + 3 :, cx - 8 : cx + 9] > 0)
    if not (has_top and has_bot):
        return False, "NOT_CROSSING"

    # 1. Text rejection via PCA
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    for i in range(1, num_labels):
        x0, y0, w, h, area = stats[i]
        touches = (y0 + h >= cy - 3 and y0 <= cy - 2) or (y0 <= cy + 3 and y0 + h >= cy + 2)
        near_center = (x0 - 2 <= cx <= x0 + w + 2)
        if touches and near_center:
            pts = np.argwhere(labels == i)
            if len(pts) >= 6:
                mean, ev, evals = cv2.PCACompute2(pts.astype(np.float32), mean=None)
                evs = evals.flatten()
                # 2D character check: transverse eigenvalue >= 2.0 and width >= 5px
                if evs[1] >= 2.0 and w >= 5:
                    return False, "REJECT_TEXT"

    # 2. Check for crossing strokes via HoughLinesP
    edges = cv2.Canny(patch, 50, 150)
    segs = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=5, minLineLength=5, maxLineGap=2)
    if segs is None:
        return False, "NO_SEGS"
    raw_segs = segs.reshape(-1, 4)

    enriched: List[Tuple[int, int, int, int, float]] = []
    for s in raw_segs:
        x1, y1, x2, y2 = int(s[0]), int(s[1]), int(s[2]), int(s[3])
        ang = math.degrees(math.atan2(float(y2 - y1), float(x2 - x1))) % 180.0
        rel_ang = ang if ang <= 90.0 else 180.0 - ang
        enriched.append((x1, y1, x2, y2, rel_ang))

    # Reject repetitive hatch fields
    hatch_candidates = [s for s in enriched if s[4] >= 20.0]
    if len(hatch_candidates) >= 3:
        tracks = _count_distinct_tracks(hatch_candidates, min_cluster_gap=5.0)
        if tracks >= 3:
            return False, "REJECT_HATCH"

    for x1, y1, x2, y2, rel_ang in enriched:
        seg_v = np.array([x2 - x1, y2 - y1], dtype=np.float32)
        seg_len = float(np.linalg.norm(seg_v))
        if seg_len < 1e-4:
            continue
        seg_u = seg_v / seg_len
        p_v = np.array([cx - x1, cy - y1], dtype=np.float32)
        proj = float(np.dot(p_v, seg_u))
        proj_clamped = max(0.0, min(seg_len, proj))
        closest_p = np.array([x1, y1], dtype=np.float32) + proj_clamped * seg_u
        dist_to_center = float(np.linalg.norm(closest_p - np.array([cx, cy])))

        # Perpendicular/tilted witness line: 65°..115°
        if 65.0 <= rel_ang <= 90.0 and dist_to_center <= 3.5:
            return True, "WITNESS"
        # Oblique architectural slash: 30°..60°
        if 30.0 <= rel_ang <= 60.0 and dist_to_center <= 3.5:
            return True, "OBLIQUE"

    return False, "NONE"


def split_line_at_boundaries(
    line: RawLine,
    image_bgr: Optional[np.ndarray],
    step_px: float = 2.0,
    endpoint_margin_px: float = 10.0,
    cluster_tol_px: float = 6.0,
) -> List[RawLine]:
    """Strategy D: Multi-Model Line Splitter.

    Scans along line length:
    - Normalizes rotation so line is horizontal.
    - Slices at both 90° perpendicular witness lines AND 45° oblique architectural slashes.
    - Rejects text descenders (PCA transverse eigenvalue) and cross-hatching noise.
    """
    if image_bgr is None:
        return [line]

    gray = image_bgr if image_bgr.ndim == 2 else cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    x1, y1 = line.p1_px
    x2, y2 = line.p2_px
    if not (math.isfinite(x1) and math.isfinite(y1) and math.isfinite(x2) and math.isfinite(y2)):
        return [line]
    length = math.hypot(x2 - x1, y2 - y1)
    if not math.isfinite(length) or length <= 2 * endpoint_margin_px:
        return [line]

    h_img, w_img = gray.shape[:2]
    angle_rad = math.atan2(y2 - y1, x2 - x1)
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)
    nx = -dy
    ny = dx

    hits: List[float] = []
    patch_size = 32

    t = endpoint_margin_px
    while t <= length - endpoint_margin_px:
        px = x1 + t * dx
        py = y1 + t * dy

        # Fast pre-check: does any dark pixel exist at +/- 7..10 px away from line corridor?
        has_nearby_dark = False
        v_dirs = (
            (nx, ny),
            ((nx + dx) * 0.707, (ny + dy) * 0.707),
            ((nx - dx) * 0.707, (ny - dy) * 0.707),
        )
        for d in (7.0, 10.0):
            for sgn in (-1.0, 1.0):
                for vx, vy in v_dirs:
                    sx = int(round(px + sgn * d * vx))
                    sy = int(round(py + sgn * d * vy))
                    if 0 <= sx < w_img and 0 <= sy < h_img and gray[sy, sx] < 190:
                        has_nearby_dark = True
                        break
                if has_nearby_dark:
                    break
            if has_nearby_dark:
                break

        if not has_nearby_dark:
            t += step_px
            continue

        patch, _ = _crop_and_rotate_patch(gray, (px, py), angle_rad, patch_size=patch_size)
        is_hit, _ = _check_internal_boundary_at_patch(patch)

        if is_hit:
            hits.append(t)

        t += step_px

    if not hits:
        return [line]

    # Cluster hits within cluster_tol_px
    clustered: List[List[float]] = [[hits[0]]]
    for h in hits[1:]:
        if h - clustered[-1][-1] <= cluster_tol_px:
            clustered[-1].append(h)
        else:
            clustered.append([h])

    offsets = [sorted(c)[len(c) // 2] for c in clustered]

    bounds = [0.0] + sorted(offsets) + [length]
    result: List[RawLine] = []
    for t0, t1 in zip(bounds[:-1], bounds[1:]):
        if t1 - t0 < 1e-6:
            continue
        p_start = (x1 + t0 * dx, y1 + t0 * dy)
        p_end = (x1 + t1 * dx, y1 + t1 * dy)
        bbox = (
            min(p_start[0], p_end[0]), min(p_start[1], p_end[1]),
            max(p_start[0], p_end[0]), max(p_start[1], p_end[1]),
        )
        result.append(RawLine(
            id=new_id("rawline-split"),
            p1_px=p_start,
            p2_px=p_end,
            confidence=line.confidence,
            bbox_px=bbox,
        ))

    return result or [line]
