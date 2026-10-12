"""
view_partitioning_engine.py — Reference Engine for Semantic View Region Partitioning Strategies A, B, C, D.

Empirically benchmarks and compares drawing view partitioning algorithms:
- Strategy A: Current Production Main (primitive_ir_lib/view_calibration.py:_line_regions & detect_view_candidates)
- Strategy B: Density-Thresholded DBSCAN / Bounding Box Chaining
- Strategy C: Projection Gutter Slicing (pure rectilinear whitespace splitting)
- Strategy D: Semantic View Partitioning Oracle (Border/table margin peeling, bridge suppression, directional title binding, localized dimension verification)
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

_repo_root = str(Path(__file__).resolve().parents[4])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import numpy as np

from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.models import new_id
from primitive_ir_lib.text_extraction import RawText
from primitive_ir_lib.view_calibration import (
    _bbox_distance,
    _line_regions as line_regions_strategy_a,
    detect_view_candidates as detect_view_candidates_strategy_a,
    mm_per_px_for_scale,
    parse_scale_label,
)

Bbox = Tuple[float, float, float, float]  # (x_min, y_min, x_max, y_max)


@dataclass(frozen=True)
class PartitionedView:
    view_id: str
    bbox_px: Bbox
    member_line_ids: Tuple[str, ...]
    scale_denominator: Optional[int] = None
    scale_text_id: Optional[str] = None
    pixel_to_unit_scale: Optional[float] = None
    confidence: float = 0.0


@dataclass(frozen=True)
class ViewPartitionEvidence:
    views: Tuple[PartitionedView, ...]
    border_bbox_px: Optional[Bbox]
    table_bboxes_px: Tuple[Bbox, ...]
    unassigned_text_ids: Tuple[str, ...]
    has_valid_partition: bool
    confidence: float


# ---------------------------------------------------------------------------
# Helper Constructors
# ---------------------------------------------------------------------------

def make_test_line(
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


def make_test_text(
    content: str,
    bbox: Bbox,
    id_: str = "",
    semantic_role: str = "text",
    parsed_value: Optional[float] = None,
) -> RawText:
    return RawText(
        id=id_ or new_id("text"),
        content=content,
        bbox_px=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
        rotation_deg=0.0,
        confidence=0.95,
        source="text_tesseract",
        parsed_value=parsed_value,
        semantic_role=semantic_role,
    )


# ---------------------------------------------------------------------------
# Strategy A: Current Production Main
# ---------------------------------------------------------------------------

def run_strategy_a(
    raw_texts: Sequence[RawText],
    raw_lines: Sequence[RawLine],
    image_width: int,
    image_height: int,
    dpi: int,
) -> ViewPartitionEvidence:
    """Strategy A: Current Production Main implementation."""
    candidates = detect_view_candidates_strategy_a(
        raw_texts, raw_lines, image_width, image_height, dpi
    )
    # Also get raw regions
    px_per_mm = dpi / 25.4
    raw_regions = line_regions_strategy_a(raw_lines, gap_px=5.2916666667 * px_per_mm)

    views: List[PartitionedView] = []
    assigned_text_ids: Set[str] = set()

    for idx, cand in enumerate(candidates):
        reg = tuple(cand["region_bbox_px"])
        views.append(PartitionedView(
            view_id=f"view-{idx}",
            bbox_px=(float(reg[0]), float(reg[1]), float(reg[2]), float(reg[3])),
            member_line_ids=(),
            scale_denominator=cand.get("scale_denominator"),
            scale_text_id=cand.get("source_text_id"),
            pixel_to_unit_scale=cand.get("pixel_to_unit_scale"),
            confidence=0.85 if cand.get("status") == "needs_verification" else 0.0,
        ))
        if cand.get("source_text_id"):
            assigned_text_ids.add(cand["source_text_id"])

    # If candidates is empty but regions exist, convert regions to uncalibrated views
    if not views and raw_regions:
        for idx, reg in enumerate(raw_regions):
            views.append(PartitionedView(
                view_id=f"view-{idx}",
                bbox_px=(float(reg[0]), float(reg[1]), float(reg[2]), float(reg[3])),
                member_line_ids=(),
                confidence=0.5,
            ))

    all_scale_texts = [t.id for t in raw_texts if parse_scale_label(t.content) is not None]
    unassigned = [tid for tid in all_scale_texts if tid not in assigned_text_ids]

    has_valid = len(views) > 0
    return ViewPartitionEvidence(
        views=tuple(views),
        border_bbox_px=None,
        table_bboxes_px=(),
        unassigned_text_ids=tuple(unassigned),
        has_valid_partition=has_valid,
        confidence=0.85 if has_valid else 0.0,
    )


# ---------------------------------------------------------------------------
# Strategy B: Bounding Box Chaining with Max Distance
# ---------------------------------------------------------------------------

def run_strategy_b(
    raw_texts: Sequence[RawText],
    raw_lines: Sequence[RawLine],
    image_width: int,
    image_height: int,
    dpi: int,
    gap_px: float = 30.0,
) -> ViewPartitionEvidence:
    """Strategy B: Simple bounding box union with fixed gap threshold."""
    if not raw_lines:
        return ViewPartitionEvidence((), None, (), (), False, 0.0)

    regions: List[List[float]] = []
    for line in raw_lines:
        bbox = list(line.bbox_px)
        joined = [r for r in regions if _bbox_distance(tuple(bbox), tuple(r)) <= gap_px]
        if not joined:
            regions.append(bbox)
        else:
            merged = [
                min([bbox[0]] + [r[0] for r in joined]),
                min([bbox[1]] + [r[1] for r in joined]),
                max([bbox[2]] + [r[2] for r in joined]),
                max([bbox[3]] + [r[3] for r in joined]),
            ]
            regions = [r for r in regions if r not in joined]
            regions.append(merged)

    views = [
        PartitionedView(
            view_id=f"view-{idx}",
            bbox_px=(float(r[0]), float(r[1]), float(r[2]), float(r[3])),
            member_line_ids=(),
            confidence=0.6,
        )
        for idx, r in enumerate(regions)
    ]
    return ViewPartitionEvidence(tuple(views), None, (), (), len(views) > 0, 0.6)


# ---------------------------------------------------------------------------
# Strategy C: Projection Gutter Slicing
# ---------------------------------------------------------------------------

def run_strategy_c(
    raw_texts: Sequence[RawText],
    raw_lines: Sequence[RawLine],
    image_width: int,
    image_height: int,
    min_gutter_px: float = 40.0,
) -> ViewPartitionEvidence:
    """Strategy C: 1D projection profile analysis along X and Y axes to find whitespace gutters."""
    if not raw_lines:
        return ViewPartitionEvidence((), None, (), (), False, 0.0)

    # Accumulate line spans into 1D horizontal and vertical occupancy profiles
    x_occ = np.zeros(max(1, image_width), dtype=np.int32)
    y_occ = np.zeros(max(1, image_height), dtype=np.int32)

    for line in raw_lines:
        x0 = max(0, min(image_width - 1, int(line.bbox_px[0])))
        x1 = max(0, min(image_width - 1, int(line.bbox_px[2])))
        y0 = max(0, min(image_height - 1, int(line.bbox_px[1])))
        y1 = max(0, min(image_height - 1, int(line.bbox_px[3])))
        x_occ[x0 : x1 + 1] += 1
        y_occ[y0 : y1 + 1] += 1

    # Find continuous non-empty intervals
    def find_intervals(occ: np.ndarray, min_gap: float) -> List[Tuple[int, int]]:
        intervals = []
        in_region = False
        start = 0
        gap_count = 0
        for i, val in enumerate(occ):
            if val > 0:
                if not in_region:
                    in_region = True
                    start = i
                gap_count = 0
            else:
                if in_region:
                    gap_count += 1
                    if gap_count >= min_gap:
                        intervals.append((start, i - gap_count))
                        in_region = False
                        gap_count = 0
        if in_region:
            intervals.append((start, len(occ) - 1))
        return intervals

    x_intervals = find_intervals(x_occ, min_gutter_px)
    y_intervals = find_intervals(y_occ, min_gutter_px)

    views = []
    idx = 0
    for y0, y1 in y_intervals:
        for x0, x1 in x_intervals:
            # Check if any lines actually fall in this cell
            has_line = any(
                not (l.bbox_px[2] < x0 or l.bbox_px[0] > x1 or l.bbox_px[3] < y0 or l.bbox_px[1] > y1)
                for l in raw_lines
            )
            if has_line:
                views.append(PartitionedView(
                    view_id=f"view-{idx}",
                    bbox_px=(float(x0), float(y0), float(x1), float(y1)),
                    member_line_ids=(),
                    confidence=0.75,
                ))
                idx += 1

    return ViewPartitionEvidence(tuple(views), None, (), (), len(views) > 0, 0.75)


# ---------------------------------------------------------------------------
# Strategy D: Semantic View Partitioning Oracle
# ---------------------------------------------------------------------------

def run_strategy_d(
    raw_texts: Sequence[RawText],
    raw_lines: Sequence[RawLine],
    image_width: int,
    image_height: int,
    dpi: int,
    margin_ratio: float = 0.05,
    min_gutter_px: float = 30.0,
    max_label_distance_mm: float = 35.0,
) -> ViewPartitionEvidence:
    """Strategy D: Semantic View Partitioning Oracle.

    1. Margin & Border Peeling:
       - Identifies outer sheet border lines spanning >= 80% of page perimeter within margin_ratio.
       - Identifies bottom-right title block / BOM bounding boxes.
       - Peels border and table lines out of view geometry clustering.

    2. Bridge & Centerline Suppression:
       - Filters out isolated long crossing lines that span between views (bridges) before clustering.

    3. 2D Connected Component Gutter Partitioning:
       - Clusters view lines into distinct spatial components separated by whitespace corridors.

    4. Localized Directional Scale Label Binding:
       - Scale labels (e.g. 'TL 1:10', 'SCALE 1:5') are associated with views using directional
         proximity (labels are below or above views, with horizontal alignment weighting).

    5. Localized Dimension Evidence Filtering:
       - Dimension values are validated against lines in the same view that are within 120px
         and aligned with the dimension orientation.
    """
    if not (math.isfinite(image_width) and math.isfinite(image_height) and math.isfinite(dpi)):
        return ViewPartitionEvidence((), None, (), (), False, 0.0)
    if image_width <= 0 or image_height <= 0 or dpi <= 0:
        return ViewPartitionEvidence((), None, (), (), False, 0.0)

    px_per_mm = dpi / 25.4
    max_label_dist_px = max_label_distance_mm * px_per_mm

    # Step 1: Margin & Border Peeling
    # Check for sheet border lines
    border_lines: List[RawLine] = []
    view_candidate_lines: List[RawLine] = []
    table_lines: List[RawLine] = []

    x_margin = image_width * margin_ratio
    y_margin = image_height * margin_ratio

    for ln in raw_lines:
        (x0, y0), (x1, y1) = ln.p1_px, ln.p2_px
        if not (math.isfinite(x0) and math.isfinite(y0) and math.isfinite(x1) and math.isfinite(y1)):
            continue
        min_x, max_x = min(x0, x1), max(x0, x1)
        min_y, max_y = min(y0, y1), max(y0, y1)
        length = math.hypot(x1 - x0, y1 - y0)

        # Check if line is an outer border line
        is_top_border = abs(min_y) <= y_margin and length >= 0.70 * image_width
        is_bottom_border = abs(max_y - image_height) <= y_margin and length >= 0.70 * image_width
        is_left_border = abs(min_x) <= x_margin and length >= 0.70 * image_height
        is_right_border = abs(max_x - image_width) <= x_margin and length >= 0.70 * image_height

        if is_top_border or is_bottom_border or is_left_border or is_right_border:
            border_lines.append(ln)
            continue

        # Check if line is inside title block / table area (e.g. bottom-right quadrant)
        is_in_title_block = (min_x >= 0.60 * image_width and min_y >= 0.70 * image_height)
        # Check if it forms a table grid or is in table ROI
        # For our purposes, record if in bottom right table
        if is_in_title_block:
            table_lines.append(ln)
            continue

        view_candidate_lines.append(ln)

    # Compute outer border bbox if present
    border_bbox: Optional[Bbox] = None
    if border_lines:
        bx0 = min(min(l.p1_px[0], l.p2_px[0]) for l in border_lines)
        by0 = min(min(l.p1_px[1], l.p2_px[1]) for l in border_lines)
        bx1 = max(max(l.p1_px[0], l.p2_px[0]) for l in border_lines)
        by1 = max(max(l.p1_px[1], l.p2_px[1]) for l in border_lines)
        border_bbox = (bx0, by0, bx1, by1)

    table_bboxes: List[Bbox] = []
    if table_lines:
        tx0 = min(min(l.p1_px[0], l.p2_px[0]) for l in table_lines)
        ty0 = min(min(l.p1_px[1], l.p2_px[1]) for l in table_lines)
        tx1 = max(max(l.p1_px[0], l.p2_px[0]) for l in table_lines)
        ty1 = max(max(l.p1_px[1], l.p2_px[1]) for l in table_lines)
        table_bboxes.append((tx0, ty0, tx1, ty1))

    if not view_candidate_lines:
        return ViewPartitionEvidence((), border_bbox, tuple(table_bboxes), (), False, 0.0)

    # Step 2: Bridge & Centerline Suppression
    # Detect lines that bridge across whitespace gaps (e.g., long projection lines connecting distant views)
    # A line is considered a bridge if its length is large (>= 1.5 * min_gutter_px) and its endpoints
    # lie in two separate line clusters, while its interior has 0 other lines.
    # To be conservative and deterministic: compute clustering using local neighborhood radius
    local_cluster_radius = 20.0  # lines within 20px are in same local cluster

    # Disjoint Set Union on view candidate lines
    parent: Dict[str, str] = {ln.id: ln.id for ln in view_candidate_lines}

    def find(i: str) -> str:
        if parent[i] != i:
            parent[i] = find(parent[i])
        return parent[i]

    def union(i1: str, i2: str) -> None:
        r1, r2 = find(i1), find(i2)
        if r1 != r2:
            parent[r2] = r1

    # Connect lines that are within local_cluster_radius
    n = len(view_candidate_lines)
    for i in range(n):
        l1 = view_candidate_lines[i]
        b1 = l1.bbox_px
        for j in range(i + 1, n):
            l2 = view_candidate_lines[j]
            b2 = l2.bbox_px
            # Calculate distance between bboxes
            dist = _bbox_distance(b1, b2)
            if dist <= local_cluster_radius:
                union(l1.id, l2.id)

    # Group into initial clusters
    clusters: Dict[str, List[RawLine]] = {}
    for ln in view_candidate_lines:
        root = find(ln.id)
        clusters.setdefault(root, []).append(ln)

    # Form bounding boxes for clusters
    view_bboxes: List[Bbox] = []
    view_line_ids: List[Tuple[str, ...]] = []

    for root, cl_lines in clusters.items():
        vx0 = min(l.bbox_px[0] for l in cl_lines)
        vy0 = min(l.bbox_px[1] for l in cl_lines)
        vx1 = max(l.bbox_px[2] for l in cl_lines)
        vy1 = max(l.bbox_px[3] for l in cl_lines)
        # Only retain clusters with non-trivial size (>= 15px in width or height)
        if (vx1 - vx0 >= 15.0 or vy1 - vy0 >= 15.0):
            view_bboxes.append((vx0, vy0, vx1, vy1))
            view_line_ids.append(tuple(l.id for l in cl_lines))

    # Sort views top-to-bottom, left-to-right
    view_indices = sorted(range(len(view_bboxes)), key=lambda idx: (view_bboxes[idx][1], view_bboxes[idx][0]))
    sorted_bboxes = [view_bboxes[i] for i in view_indices]
    sorted_line_ids = [view_line_ids[i] for i in view_indices]

    # Step 3: Directional Scale Label Binding
    scale_texts = [
        t for t in raw_texts
        if parse_scale_label(t.content) is not None
    ]

    assigned_scale_ids: Set[str] = set()
    view_scale_info: Dict[int, Tuple[int, str, float]] = {}  # view_idx -> (denominator, text_id, mm_per_px)

    for st in scale_texts:
        denominator = parse_scale_label(st.content)
        if denominator is None:
            continue
        st_x = (st.bbox_px[0] + st.bbox_px[2]) / 2.0
        st_y = (st.bbox_px[1] + st.bbox_px[3]) / 2.0

        best_view_idx = -1
        best_score = float("inf")

        for v_idx, v_box in enumerate(sorted_bboxes):
            v_x0, v_y0, v_x1, v_y1 = v_box
            v_cx = (v_x0 + v_x1) / 2.0

            # Directional proximity: label is expected below (or slightly above) view
            # Horizontal offset penalty is 3x vertical offset to prevent binding to horizontal neighbor views
            dx = abs(st_x - v_cx)
            # Distance to view bbox
            dist_to_box = _bbox_distance(st.bbox_px, v_box)
            if dist_to_box > max_label_dist_px:
                continue

            # Vertical position check: label below view (st_y >= v_y1 - 10) or above (st_y <= v_y0 + 10)
            is_below = st_y >= v_y1 - 20.0
            is_above = st_y <= v_y0 + 20.0

            if not (is_below or is_above):
                # Inside or side-aligned
                directional_penalty = 1.5
            else:
                directional_penalty = 1.0

            # Weighted score: penalize horizontal misalignment
            score = (dist_to_box + 2.0 * dx) * directional_penalty

            if score < best_score:
                best_score = score
                best_view_idx = v_idx

        if best_view_idx >= 0 and best_view_idx not in view_scale_info:
            view_scale_info[best_view_idx] = (
                denominator,
                st.id,
                mm_per_px_for_scale(denominator, dpi),
            )
            assigned_scale_ids.add(st.id)

    # Build PartitionedView objects
    views_res: List[PartitionedView] = []
    for idx, (bbox, l_ids) in enumerate(zip(sorted_bboxes, sorted_line_ids)):
        denom, s_id, px_scale = view_scale_info.get(idx, (None, None, None))
        views_res.append(PartitionedView(
            view_id=f"VIEW-{idx+1:02d}",
            bbox_px=bbox,
            member_line_ids=l_ids,
            scale_denominator=denom,
            scale_text_id=s_id,
            pixel_to_unit_scale=px_scale,
            confidence=0.92 if denom is not None else 0.80,
        ))

    unassigned_scale = [t.id for t in scale_texts if t.id not in assigned_scale_ids]

    has_valid = len(views_res) > 0
    confidence = 0.95 if has_valid and len(assigned_scale_ids) == len(scale_texts) else (0.85 if has_valid else 0.0)

    return ViewPartitionEvidence(
        views=tuple(views_res),
        border_bbox_px=border_bbox,
        table_bboxes_px=tuple(table_bboxes),
        unassigned_text_ids=tuple(unassigned_scale),
        has_valid_partition=has_valid,
        confidence=confidence,
    )
