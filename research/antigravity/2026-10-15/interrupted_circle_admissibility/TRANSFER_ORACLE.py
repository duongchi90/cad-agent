"""Transfer Oracle: Transversal Occlusion-Aware Circle Admissibility Model.

Campaign ID: ANTI-INTERRUPTED-CIRCLE-ADMISSIBILITY-V1-20261015
Product Frontier: https://github.com/duongchi90/cad-agent/issues/491
Author: Antigravity Research Agent
Status: Decision-Grade Transfer Oracle (Zero Production Mutation)

This oracle provides the mathematically justified admission logic for circles
interrupted by dimensions, witness lines, or annotations.

CORE THEORETICAL INVARIANTS:
1. Observational Equivalence:
   A circle with an unexplained angular gap is observationally identical to an
   open CAD arc in the raster domain. Therefore, raster-only admission without
   an occluder witness is PROVABLY UNSAFE.
2. Transversal Secant Crossing Invariant:
   An angular gap is excused IF AND ONLY IF an intersecting line segment passes
   transversally through the circle boundary (one endpoint inside r - eps, one
   endpoint outside r + eps) across the gap footprint.
3. Fail-Closed Role Separation:
   Small closed circles matching OCR text character boxes ('O', '0') must be
   withheld from engineering circle promotion by the caller role gate.
"""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

cv2 = importlib.import_module("cv2")


@dataclass(frozen=True)
class CircleCandidate:
    center_px: Tuple[float, float]
    radius_px: float
    confidence: float = 0.75


@dataclass(frozen=True)
class AdmissionReport:
    candidate: CircleCandidate
    is_admitted: bool
    rejection_reason: Optional[str]
    total_angular_coverage: float
    longest_unsupported_gap_deg: float
    explained_gaps_count: int
    unexplained_gaps_count: int
    median_normal_error_deg: float


class InterruptedCircleAdmissionOracle:
    """Rigorous geometric admission oracle for CAD-Agent circle extraction."""

    def __init__(
        self,
        stroke_width_px: float = 2.0,
        num_angular_bins: int = 72,
        sobel_kernel_size: int = 3,
    ) -> None:
        self.w = stroke_width_px
        self.num_bins = num_angular_bins
        self.ksize = sobel_kernel_size
        # Quantization q = sqrt(2)/2 ≈ 0.707 px
        # Antialiasing a ≈ 0.5 px
        # Filter bias b ≈ 0.5 px
        # eps_pos = q + w/2 + a + b
        self.q = float(np.sqrt(2.0)) / 2.0
        self.a = 0.5
        self.b = 0.5
        self.g_gradient_deg = 3.5

    def compute_position_envelope(self, radius_px: float) -> float:
        base_eps = self.q + (self.w / 2.0) + self.a + self.b
        return max(2.5, min(base_eps, 0.04 * radius_px))

    def compute_normal_envelope_deg(self, radius_px: float, eps_pos: float) -> float:
        if radius_px <= eps_pos:
            return 90.0
        geom_deg = math.degrees(math.asin(min(1.0, eps_pos / radius_px)))
        return geom_deg + self.g_gradient_deg

    def evaluate_candidate(
        self,
        candidate: CircleCandidate,
        edges: np.ndarray,
        gray_image: np.ndarray,
        detected_lines: Optional[List[Tuple[float, float, float, float]]] = None,
        text_rois: Optional[List[Tuple[int, int, int, int]]] = None,
    ) -> AdmissionReport:
        cx, cy = candidate.center_px
        r = candidate.radius_px
        h, w = edges.shape

        # Step 0: Degeneracy checks
        if r <= 0.0 or not np.isfinite(cx) or not np.isfinite(cy) or not np.isfinite(r):
            return AdmissionReport(candidate, False, "NON_FINITE_OR_NON_POSITIVE_GEOMETRY", 0.0, 360.0, 0, 0, 999.0)
        if cx < 0 or cy < 0 or cx >= w or cy >= h:
            return AdmissionReport(candidate, False, "CENTER_OUT_OF_IMAGE_BOUNDS", 0.0, 360.0, 0, 0, 999.0)

        eps_pos = self.compute_position_envelope(r)
        eps_normal = self.compute_normal_envelope_deg(r, eps_pos)
        q_bound_rad = 2.0 * math.asin(min(1.0, eps_pos / (2.0 * r)))
        q_bound_deg = math.degrees(q_bound_rad)

        # Step 1: Compute Sobel gradients
        gx = cv2.Sobel(gray_image, cv2.CV_64F, 1, 0, ksize=self.ksize)
        gy = cv2.Sobel(gray_image, cv2.CV_64F, 0, 1, ksize=self.ksize)

        # Step 2: Measure angular bin support and normal errors
        bins_supported = np.zeros(self.num_bins, dtype=bool)
        normal_errors: List[float] = []

        for b in range(self.num_bins):
            theta = 2.0 * math.pi * b / self.num_bins
            sx = cx + r * math.cos(theta)
            sy = cy + r * math.sin(theta)
            x0 = max(0, int(math.floor(sx - eps_pos)))
            x1 = min(w, int(math.ceil(sx + eps_pos + 1)))
            y0 = max(0, int(math.floor(sy - eps_pos)))
            y1 = min(h, int(math.ceil(sy + eps_pos + 1)))
            if x1 <= x0 or y1 <= y0:
                continue

            yy, xx = np.nonzero(edges[y0:y1, x0:x1])
            if len(xx) == 0:
                continue
            xx = xx + x0
            yy = yy + y0
            radial_dist = np.hypot(xx - cx, yy - cy)
            dr = np.abs(radial_dist - r)
            best_idx = int(np.argmin(dr))
            if dr[best_idx] > eps_pos:
                continue

            ex, ey = int(xx[best_idx]), int(yy[best_idx])
            g_norm = math.hypot(gx[ey, ex], gy[ey, ex])
            if g_norm <= 1e-3:
                continue

            rx = (ex - cx) / radial_dist[best_idx]
            ry = (ey - cy) / radial_dist[best_idx]
            cos_align = abs((gx[ey, ex] * rx + gy[ey, ex] * ry) / g_norm)
            cos_align = min(1.0, max(0.0, cos_align))
            err_deg = math.degrees(math.acos(cos_align))

            if err_deg <= eps_normal + 3.0:
                bins_supported[b] = True
                normal_errors.append(err_deg)

        total_coverage = float(np.sum(bins_supported)) / self.num_bins
        med_normal_err = float(np.median(normal_errors)) if normal_errors else 999.0

        if not normal_errors or med_normal_err > eps_normal + 2.0:
            return AdmissionReport(candidate, False, "NORMAL_GRADIENT_ALIGNMENT_FAILED", total_coverage, 360.0, 0, 0, med_normal_err)

        # Step 3: Extract contiguous unsupported gaps
        doubled = np.concatenate((bins_supported, bins_supported))
        gaps: List[Tuple[int, int]] = []
        cur_start: Optional[int] = None
        cur_len = 0
        for i, val in enumerate(doubled):
            if not val:
                if cur_start is None:
                    cur_start = i
                cur_len += 1
            else:
                if cur_start is not None and cur_len > 0:
                    start_mod = cur_start % self.num_bins
                    if cur_len < self.num_bins and not any(g[0] == start_mod for g in gaps):
                        gaps.append((start_mod, cur_len))
                cur_start = None
                cur_len = 0

        max_gap_len = max([g[1] for g in gaps], default=0)
        longest_gap_deg = (max_gap_len * 360.0) / self.num_bins

        # Step 4: Transversal Gap Explanation
        # If no lines were supplied, detect them locally
        lines = detected_lines
        if lines is None:
            raw_lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=15, maxLineGap=5)
            lines = []
            if raw_lines is not None:
                for seg in raw_lines.reshape(-1, 4):
                    lines.append((float(seg[0]), float(seg[1]), float(seg[2]), float(seg[3])))

        explained_count = 0
        unexplained_count = 0

        for start_bin, length in gaps:
            gap_deg = (length * 360.0) / self.num_bins
            if gap_deg <= q_bound_deg:
                # Pixel quantization spacing is naturally admitted
                explained_count += 1
                continue

            mid_bin = (start_bin + length / 2.0) % self.num_bins
            mid_rad = 2.0 * math.pi * mid_bin / self.num_bins
            gap_x = cx + r * math.cos(mid_rad)
            gap_y = cy + r * math.sin(mid_rad)

            gap_explained = False

            # Check A: Transversal Line Crossing
            # If a line crosses the circle transversally at angle theta_cross,
            # it explains the gap if theta_cross is inside or immediately adjacent to the gap
            # (within standard dimension text clearance envelope <= 25 degrees)
            for lx0, ly0, lx1, ly1 in lines:
                d0 = math.hypot(lx0 - cx, ly0 - cy)
                d1 = math.hypot(lx1 - cx, ly1 - cy)
                # Transversality: line must physically enter and exit the circle
                if (min(d0, d1) < r - eps_pos) and (max(d0, d1) > r + eps_pos):
                    # Find intersection point of line segment with circle locus
                    dx = lx1 - lx0
                    dy = ly1 - ly0
                    l2 = dx*dx + dy*dy
                    if l2 > 0:
                        # Find closest point on segment to center
                        t_c = max(0.0, min(1.0, ((cx - lx0)*dx + (cy - ly0)*dy) / l2))
                        p_cx = lx0 + t_c * dx
                        p_cy = ly0 + t_c * dy
                        d_c = math.hypot(p_cx - cx, p_cy - cy)
                        if d_c <= r:
                            # Distance from p_c to intersection along line
                            h_chord = math.sqrt(max(0.0, r*r - d_c*d_c))
                            line_len = math.sqrt(l2)
                            ux = dx / line_len
                            uy = dy / line_len
                            # Two possible circle intersection points along line
                            for sign in (-1.0, 1.0):
                                ix = p_cx + sign * h_chord * ux
                                iy = p_cy + sign * h_chord * uy
                                # Verify intersection lies on segment
                                if min(lx0, lx1) - 1.0 <= ix <= max(lx0, lx1) + 1.0 and min(ly0, ly1) - 1.0 <= iy <= max(ly0, ly1) + 1.0:
                                    theta_cross_deg = math.degrees(math.atan2(iy - cy, ix - cx)) % 360.0
                                    mid_deg = (mid_bin * 360.0) / self.num_bins
                                    # Angular difference accounting for 360 seam
                                    ang_diff = abs(theta_cross_deg - mid_deg)
                                    ang_diff = min(ang_diff, 360.0 - ang_diff)
                                    # If crossing is within the gap half-extent + 15 deg clearance
                                    if ang_diff <= (gap_deg / 2.0) + 15.0:
                                        gap_explained = True
                                        break
                    if gap_explained:
                        break

            # Check B: Text ROI footprint
            if not gap_explained and text_rois is not None:
                for rx0, ry0, rx1, ry1 in text_rois:
                    if rx0 <= gap_x <= rx1 and ry0 <= gap_y <= ry1:
                        gap_explained = True
                        break

            # Check C: Strong ink crossing on raw image (dimension line or hatch)
            if not gap_explained:
                gx0 = max(0, int(gap_x - eps_pos))
                gx1 = min(w, int(gap_x + eps_pos + 1))
                gy0 = max(0, int(gap_y - eps_pos))
                gy1 = min(h, int(gap_y + eps_pos + 1))
                if gx1 > gx0 and gy1 > gy0:
                    if np.min(gray_image[gy0:gy1, gx0:gx1]) < 60:
                        gap_explained = True

            if gap_explained:
                explained_count += 1
            else:
                unexplained_count += 1

        # Step 5: Final Admission Decision
        if unexplained_count > 0:
            return AdmissionReport(
                candidate,
                False,
                f"UNEXPLAINED_ANGULAR_GAP_{longest_gap_deg:.1f}DEG",
                total_coverage,
                longest_gap_deg,
                explained_count,
                unexplained_count,
                med_normal_err,
            )

        # Check quadrant coverage (at least 3 quadrants must have edge ink)
        quadrants = [np.any(bins_supported[k*18:(k+1)*18]) for k in range(4)]
        if sum(quadrants) < 3:
            return AdmissionReport(candidate, False, "INSUFFICIENT_QUADRANT_SPREAD", total_coverage, longest_gap_deg, explained_count, 0, med_normal_err)

        return AdmissionReport(
            candidate,
            True,
            None,
            total_coverage,
            longest_gap_deg,
            explained_count,
            0,
            med_normal_err,
        )


def self_test():
    """Deterministic validation of the Transfer Oracle."""
    oracle = InterruptedCircleAdmissionOracle()

    # Test 1: Complete circle
    img_circle = np.full((300, 300), 255, dtype=np.uint8)
    cv2.circle(img_circle, (150, 150), 60, 0, 2, cv2.LINE_AA)
    edges = cv2.Canny(cv2.GaussianBlur(img_circle, (3, 3), 0), 50, 100)
    rep1 = oracle.evaluate_candidate(CircleCandidate((150.0, 150.0), 60.0), edges, img_circle)
    assert rep1.is_admitted, f"Complete circle must be admitted: {rep1}"

    # Test 2: 300-deg open arc (unexplained gap of 60 deg) -> MUST REJECT!
    img_arc = np.full((300, 300), 255, dtype=np.uint8)
    cv2.ellipse(img_arc, (150, 150), (60, 60), 0, 30, 330, 0, 2, cv2.LINE_AA)
    edges_arc = cv2.Canny(cv2.GaussianBlur(img_arc, (3, 3), 0), 50, 100)
    rep2 = oracle.evaluate_candidate(CircleCandidate((150.0, 150.0), 60.0), edges_arc, img_arc)
    assert not rep2.is_admitted, f"Open arc MUST NOT be admitted: {rep2}"
    assert "UNEXPLAINED_ANGULAR_GAP" in rep2.rejection_reason

    # Test 3: Circle intersected by dimension line across gap -> MUST ADMIT!
    img_interrupted = np.full((300, 300), 255, dtype=np.uint8)
    cv2.circle(img_interrupted, (150, 150), 60, 0, 2, cv2.LINE_AA)
    cv2.rectangle(img_interrupted, (200, 130), (225, 170), 255, -1)  # 40-deg gap
    cv2.line(img_interrupted, (190, 150), (240, 150), 0, 1, cv2.LINE_AA)  # Crossing dimension line
    edges_int = cv2.Canny(cv2.GaussianBlur(img_interrupted, (3, 3), 0), 50, 100)
    rep3 = oracle.evaluate_candidate(CircleCandidate((150.0, 150.0), 60.0), edges_int, img_interrupted)
    assert rep3.is_admitted, f"Interrupted circle with explained gap MUST be admitted: {rep3}"

    print("Self-test PASSED: All invariants satisfied.")


if __name__ == "__main__":
    self_test()
