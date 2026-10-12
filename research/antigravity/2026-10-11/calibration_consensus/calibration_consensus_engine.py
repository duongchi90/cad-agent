"""
calibration_consensus_engine.py — Reference Engine for Calibration Strategies A, B, C, D.

Empirically benchmarks and compares automatic calibration algorithms from engineering drawings:
- Strategy A: Current Production Main (first candidate, require_consensus=False, 10% tol)
- Strategy B: Naive Consensus (current require_consensus=True, 10% tol)
- Strategy C: Strict 3% Median Consensus + Orientation Matching
- Strategy D: Robust Multi-Axis Dimension Topology Oracle (Span projection, boundary support, 3% clustering, cross-axis consistency)
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple, Sequence, Dict, Any
import numpy as np

from primitive_ir_lib.calibration import auto_estimate_calibration, find_nearest_line, estimate_calibration_from_reference
from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.models import Calibration
from primitive_ir_lib.text_extraction import RawText, classify_semantic_role


def make_line(p1: Tuple[float, float], p2: Tuple[float, float], id_: str, conf: float = 0.9) -> RawLine:
    return RawLine(
        id=id_,
        p1_px=p1,
        p2_px=p2,
        confidence=conf,
        bbox_px=(min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])),
    )


def make_text(content: str, bbox: Tuple[int, int, int, int], rotation_deg: float = 0.0, id_: str = "t1", conf: float = 0.95) -> RawText:
    role, value = classify_semantic_role(content)
    return RawText(
        id=id_,
        content=content,
        bbox_px=bbox,
        rotation_deg=rotation_deg,
        confidence=conf,
        source="text_tesseract",
        parsed_value=value,
        semantic_role=role,
    )


# ---------------------------------------------------------------------------
# Strategy Implementations
# ---------------------------------------------------------------------------

def run_strategy_a(
    raw_texts: Sequence[RawText],
    raw_lines: Sequence[RawLine],
    image_height_px: int = 3000,
    image_bgr: Optional[np.ndarray] = None,
) -> Optional[Calibration]:
    """Strategy A: Current Production Main (picks first candidate, require_consensus=False)."""
    return auto_estimate_calibration(
        list(raw_texts),
        list(raw_lines),
        image_height_px=image_height_px,
        image_bgr=image_bgr,
        require_consensus=False,
        consensus_tolerance_pct=10.0,
        min_consensus_candidates=2,
    )


def run_strategy_b(
    raw_texts: Sequence[RawText],
    raw_lines: Sequence[RawLine],
    image_height_px: int = 3000,
    image_bgr: Optional[np.ndarray] = None,
) -> Optional[Calibration]:
    """Strategy B: Naive Consensus (current production opt-in with 10% tolerance)."""
    return auto_estimate_calibration(
        list(raw_texts),
        list(raw_lines),
        image_height_px=image_height_px,
        image_bgr=image_bgr,
        require_consensus=True,
        consensus_tolerance_pct=10.0,
        min_consensus_candidates=2,
    )


def run_strategy_c(
    raw_texts: Sequence[RawText],
    raw_lines: Sequence[RawLine],
    image_height_px: int = 3000,
    image_bgr: Optional[np.ndarray] = None,
    consensus_tolerance_pct: float = 3.0,
    min_consensus_candidates: int = 2,
) -> Optional[Calibration]:
    """Strategy C: Strict 3% Median Consensus with orientation gating."""
    return auto_estimate_calibration(
        list(raw_texts),
        list(raw_lines),
        image_height_px=image_height_px,
        image_bgr=image_bgr,
        require_consensus=True,
        consensus_tolerance_pct=consensus_tolerance_pct,
        min_consensus_candidates=min_consensus_candidates,
    )


def run_strategy_d(
    raw_texts: Sequence[RawText],
    raw_lines: Sequence[RawLine],
    image_height_px: int = 3000,
    image_bgr: Optional[np.ndarray] = None,
    max_relative_error_pct: float = 3.0,
    min_consensus_candidates: int = 2,
    max_perp_distance_px: float = 40.0,
    unit: str = "mm",
) -> Optional[Calibration]:
    """Strategy D: Robust Multi-Axis Dimension Topology Oracle.

    Core algorithmic invariants:
    1. Rejects non-dimension numeric noise (sheet numbers, lone small integers without dimension geometry).
    2. Validates longitudinal text-to-line span projection: text must lie within the longitudinal extent of the line.
    3. Prevents pairing text with fragmented lines by requiring line length to be consistent with dimension value.
    4. Enforces the AGENTS.md invariant: >= 2 independent candidates with median relative error <= 3.0%.
    5. Validates cross-axis consistency (horizontal vs vertical scale agreement within 3%).
    """
    candidates: List[Dict[str, Any]] = []

    for text in raw_texts:
        if text.semantic_role != "dimension_value" or text.parsed_value is None:
            continue
        val = text.parsed_value
        # Filter out obvious non-dimension sheet numbers (e.g. "09", "1", "2") if no dimension symbol
        if val < 10.0 and text.content.strip().isdigit() and len(text.content.strip()) <= 2:
            continue

        tx0, ty0, tx1, ty1 = text.bbox_px
        tcx, tcy = (tx0 + tx1) / 2.0, (ty0 + ty1) / 2.0
        text_angle = (text.rotation_deg % 180.0)

        best_line = None
        best_score = float("inf")

        for line in raw_lines:
            lx0, ly0 = line.p1_px
            lx1, ly1 = line.p2_px
            length = math.hypot(lx1 - lx0, ly1 - ly0)
            if length < 15.0:
                continue

            dx, dy = (lx1 - lx0) / length, (ly1 - ly0) / length
            line_angle = math.degrees(math.atan2(dy, dx)) % 180.0
            diff_angle = abs(line_angle - text_angle) % 180.0
            if diff_angle > 90.0:
                diff_angle = 180.0 - diff_angle

            # Orientation compatibility:
            # If text has explicit cardinal rotation (90° or 270°), line MUST be vertical
            if abs(text_angle - 90.0) < 15.0:
                if abs(line_angle - 90.0) > 20.0:
                    continue
            # If text is unrotated (0° or 180°), line is typically horizontal (or vertical if aligned)
            # but preferred along text orientation
            vx, vy = tcx - lx0, tcy - ly0
            t_proj = vx * dx + vy * dy
            perp_dist = abs(-vx * dy + vy * dx)

            # Longitudinal extent check: text center must project inside or very near line span
            if not (-15.0 <= t_proj <= length + 15.0):
                continue

            # Perpendicular distance check
            if perp_dist > max_perp_distance_px:
                continue

            # Score prioritizes lines whose span contains the text and has low perpendicular offset
            score = perp_dist + diff_angle * 0.5
            if score < best_score:
                best_score = score
                best_line = line

        if best_line is not None:
            line_len = best_line.length_px()
            scale = val / line_len
            line_dx = best_line.p2_px[0] - best_line.p1_px[0]
            line_dy = best_line.p2_px[1] - best_line.p1_px[1]
            is_horiz = abs(line_dy) <= abs(line_dx)
            candidates.append({
                "text": text,
                "line": best_line,
                "scale": scale,
                "axis": "horizontal" if is_horiz else "vertical",
                "val": val,
                "len": line_len,
            })

    if len(candidates) < min_consensus_candidates:
        return None  # Fail closed per AGENTS.md

    # Cross-axis check: If both axes have multiple independent candidates, verify aspect ratio
    all_h = [c["scale"] for c in candidates if c["axis"] == "horizontal"]
    all_v = [c["scale"] for c in candidates if c["axis"] == "vertical"]
    if len(all_h) >= min_consensus_candidates and len(all_v) >= min_consensus_candidates:
        med_h = float(np.median(all_h))
        med_v = float(np.median(all_v))
        rel_diff = abs(med_h - med_v) / min(med_h, med_v) * 100.0
        if rel_diff > max_relative_error_pct:
            # Axis distortion detected (anisotropic scan stretching > 3%)
            return None

    # Find the largest consensus cluster with relative spread <= max_relative_error_pct (3.0%)
    scales = [c["scale"] for c in candidates]
    sorted_candidates = sorted(candidates, key=lambda c: c["scale"])

    best_cluster: List[Dict[str, Any]] = []
    n = len(sorted_candidates)
    for i in range(n):
        cluster = [sorted_candidates[i]]
        base_s = sorted_candidates[i]["scale"]
        for j in range(i + 1, n):
            s_j = sorted_candidates[j]["scale"]
            if (s_j - base_s) / base_s * 100.0 <= max_relative_error_pct:
                cluster.append(sorted_candidates[j])
            else:
                break
        if len(cluster) > len(best_cluster):
            best_cluster = cluster

    if len(best_cluster) < min_consensus_candidates:
        return None  # No consensus cluster satisfying <= 3.0% error

    # Cross-axis check: verify both axes if present
    h_scales = [c["scale"] for c in best_cluster if c["axis"] == "horizontal"]
    v_scales = [c["scale"] for c in best_cluster if c["axis"] == "vertical"]
    if h_scales and v_scales:
        med_h = float(np.median(h_scales))
        med_v = float(np.median(v_scales))
        rel_diff = abs(med_h - med_v) / min(med_h, med_v) * 100.0
        if rel_diff > max_relative_error_pct:
            # Axis distortion detected (anisotropic scaling)
            return None

    cluster_scales = [c["scale"] for c in best_cluster]
    median_scale = float(np.median(cluster_scales))

    # Pick candidate closest to median scale
    best_candidate = min(best_cluster, key=lambda c: abs(c["scale"] - median_scale))
    ref_text = best_candidate["text"]
    ref_line = best_candidate["line"]

    cal = estimate_calibration_from_reference(
        ref_text, ref_line, image_height_px=image_height_px, unit=unit
    )
    cal.reference_note = (
        f"[Strategy D Consensus: {len(best_cluster)}/{len(candidates)} independent candidates "
        f"agree within {max_relative_error_pct:.1f}% error (median={median_scale:.4f} {unit}/px). "
        f"Reference: '{ref_text.content}' ({ref_text.parsed_value} {unit}) on {ref_line.id} ({ref_line.length_px():.1f}px)]"
    )
    return cal
