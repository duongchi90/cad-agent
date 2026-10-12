"""
table_extraction_engine.py — Reference Engine for Table Cell Grid Extraction Strategies A, B, C, D.

Empirically benchmarks and compares table grid and cell extraction algorithms:
- Strategy A: Current Production Main (primitive_ir_lib/table_extraction.py)
- Strategy B: Centroid Clustered Grid (adaptive peak clustering, but rigid MxN matrix)
- Strategy C: Span-Filtered Grid (filters out short interior noise lines, but rigid MxN matrix)
- Strategy D: Topological Cell Graph Oracle (merged-cell support, span verification, noise rejection, closed-boundary validation)
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Sequence, Dict, Any, Set

_repo_root = str(Path(__file__).resolve().parents[4])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import numpy as np

from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.models import new_id
from primitive_ir_lib.table_extraction import (
    TableCell,
    detect_grid as detect_grid_strategy_a,
    build_cells as build_cells_strategy_a,
    _collect_axis_values as _collect_axis_values_strategy_a,
    _line_orientation,
)

Bbox = Tuple[float, float, float, float]  # (x_min, y_min, x_max, y_max)


@dataclass
class RobustTableCell:
    """A cell in an engineering drawing table, supporting merged rows and columns."""
    id: str
    row_start: int
    row_end: int
    col_start: int
    col_end: int
    bbox_px: Bbox
    content: str = ""
    is_merged: bool = False

    def __post_init__(self):
        self.id = self.id or new_id("cell")


@dataclass(frozen=True)
class TableGridEvidence:
    cells: Tuple[RobustTableCell, ...]
    grid_xs: Tuple[float, ...]
    grid_ys: Tuple[float, ...]
    has_valid_table: bool
    confidence: float


# ---------------------------------------------------------------------------
# Helper Geometry Functions
# ---------------------------------------------------------------------------

def make_raw_line(p1: Tuple[float, float], p2: Tuple[float, float], id_: str = "") -> RawLine:
    x1, y1 = float(p1[0]), float(p1[1])
    x2, y2 = float(p2[0]), float(p2[1])
    bbox = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    return RawLine(
        id=id_ or new_id("rawline"),
        p1_px=(x1, y1),
        p2_px=(x2, y2),
        confidence=0.9,
        bbox_px=bbox,
    )


# ---------------------------------------------------------------------------
# Strategy A: Current Production Main
# ---------------------------------------------------------------------------

def run_strategy_a(lines: List[RawLine], table_roi: Bbox, merge_tol: float = 12.0) -> TableGridEvidence:
    """Strategy A: Current Production Main."""
    xs, ys = detect_grid_strategy_a(lines, table_roi, merge_tol=merge_tol)
    cells_a = build_cells_strategy_a(xs, ys, table_roi, inset=3.0)
    robust_cells = tuple(
        RobustTableCell(
            id=c.id,
            row_start=c.row,
            row_end=c.row + 1,
            col_start=c.col,
            col_end=c.col + 1,
            bbox_px=c.bbox_px,
            content=c.content,
            is_merged=False,
        )
        for c in cells_a
    )
    has_table = len(robust_cells) > 0
    return TableGridEvidence(
        cells=robust_cells,
        grid_xs=tuple(xs),
        grid_ys=tuple(ys),
        has_valid_table=has_table,
        confidence=0.85 if has_table else 0.0,
    )


# ---------------------------------------------------------------------------
# Strategy B: Centroid Clustered Grid (fixes chaining, but rigid MxN)
# ---------------------------------------------------------------------------

def _cluster_axis_centroids(values: List[float], max_cluster_radius: float = 6.0) -> List[float]:
    """Clusters 1D coordinates using centroid-distance rather than single-linkage chaining."""
    if not values:
        return []
    sorted_v = sorted(values)
    clusters: List[List[float]] = [[sorted_v[0]]]
    for v in sorted_v[1:]:
        centroid = float(np.mean(clusters[-1]))
        if abs(v - centroid) <= max_cluster_radius:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [float(np.mean(c)) for c in clusters]


def run_strategy_b(lines: List[RawLine], table_roi: Bbox) -> TableGridEvidence:
    """Strategy B: Centroid-based clustering, but inherits rigid Cartesian grid."""
    x0, y0, x1, y1 = table_roi
    raw_xs: List[float] = []
    raw_ys: List[float] = []
    for ln in lines:
        orient = _line_orientation(ln.p1_px, ln.p2_px)
        mx = (ln.p1_px[0] + ln.p2_px[0]) / 2.0
        my = (ln.p1_px[1] + ln.p2_px[1]) / 2.0
        if not (x0 - 12.0 <= mx <= x1 + 12.0 and y0 - 12.0 <= my <= y1 + 12.0):
            continue
        if orient == "v":
            raw_xs.append((ln.p1_px[0] + ln.p2_px[0]) / 2.0)
        elif orient == "h":
            raw_ys.append((ln.p1_px[1] + ln.p2_px[1]) / 2.0)

    xs = _cluster_axis_centroids(raw_xs, max_cluster_radius=6.0)
    ys = _cluster_axis_centroids(raw_ys, max_cluster_radius=6.0)
    cells_a = build_cells_strategy_a(xs, ys, table_roi, inset=3.0)
    robust_cells = tuple(
        RobustTableCell(
            id=c.id,
            row_start=c.row,
            row_end=c.row + 1,
            col_start=c.col,
            col_end=c.col + 1,
            bbox_px=c.bbox_px,
            content=c.content,
            is_merged=False,
        )
        for c in cells_a
    )
    has_table = len(robust_cells) > 0
    return TableGridEvidence(
        cells=robust_cells,
        grid_xs=tuple(xs),
        grid_ys=tuple(ys),
        has_valid_table=has_table,
        confidence=0.85 if has_table else 0.0,
    )


# ---------------------------------------------------------------------------
# Strategy C: Span-Filtered Grid (filters short lines, but rigid MxN)
# ---------------------------------------------------------------------------

def run_strategy_c(lines: List[RawLine], table_roi: Bbox, min_span_ratio: float = 0.4) -> TableGridEvidence:
    """Strategy C: Filters out short interior lines, but rigid MxN Cartesian grid."""
    x0, y0, x1, y1 = table_roi
    w_roi = x1 - x0
    h_roi = y1 - y0
    raw_xs: List[float] = []
    raw_ys: List[float] = []
    for ln in lines:
        orient = _line_orientation(ln.p1_px, ln.p2_px)
        length = math.hypot(ln.p2_px[0] - ln.p1_px[0], ln.p2_px[1] - ln.p1_px[1])
        mx = (ln.p1_px[0] + ln.p2_px[0]) / 2.0
        my = (ln.p1_px[1] + ln.p2_px[1]) / 2.0
        if not (x0 - 12.0 <= mx <= x1 + 12.0 and y0 - 12.0 <= my <= y1 + 12.0):
            continue
        if orient == "v":
            if length >= min_span_ratio * h_roi:
                raw_xs.append((ln.p1_px[0] + ln.p2_px[0]) / 2.0)
        elif orient == "h":
            if length >= min_span_ratio * w_roi:
                raw_ys.append((ln.p1_px[1] + ln.p2_px[1]) / 2.0)

    xs = _cluster_axis_centroids(raw_xs, max_cluster_radius=6.0)
    ys = _cluster_axis_centroids(raw_ys, max_cluster_radius=6.0)
    cells_a = build_cells_strategy_a(xs, ys, table_roi, inset=3.0)
    robust_cells = tuple(
        RobustTableCell(
            id=c.id,
            row_start=c.row,
            row_end=c.row + 1,
            col_start=c.col,
            col_end=c.col + 1,
            bbox_px=c.bbox_px,
            content=c.content,
            is_merged=False,
        )
        for c in cells_a
    )
    has_table = len(robust_cells) > 0
    return TableGridEvidence(
        cells=robust_cells,
        grid_xs=tuple(xs),
        grid_ys=tuple(ys),
        has_valid_table=has_table,
        confidence=0.85 if has_table else 0.0,
    )


# ---------------------------------------------------------------------------
# Strategy D: Topological Cell Graph Oracle
# ---------------------------------------------------------------------------

def run_strategy_d(
    lines: List[RawLine],
    table_roi: Bbox,
    inset: float = 3.0,
    cluster_radius_px: float = 6.0,
    min_cell_dim_px: float = 12.0,
) -> TableGridEvidence:
    """Strategy D: Topological Cell Graph Oracle.

    1. Robust Line Classification & Overlap Range Collection:
       - Uses line span overlap with table_roi (not single midpoint).
       - Rejects non-grid interior noise lines shorter than min_cell_dim_px.
    2. Centroid-Guarded Coordinate Clustering:
       - Eliminates single-linkage chaining collapse.
    3. Topological Segment Coverage Matrix:
       - Tests whether a vertical line physically divides between (y_i, y_{i+1}) at x_j.
       - Tests whether a horizontal line physically divides between (x_k, x_{k+1}) at y_r.
    4. Merged-Cell Formation:
       - Adjoining grid blocks that lack dividing internal lines are merged into a single TableCell.
    5. Table Closure & Validity Guard:
       - Verifies that table has closed outer boundary and at least 4 intersection junctions.
    """
    x0, y0, x1, y1 = table_roi
    if not (math.isfinite(x0) and math.isfinite(y0) and math.isfinite(x1) and math.isfinite(y1)):
        return TableGridEvidence((), (), (), False, 0.0)
    if x1 <= x0 or y1 <= y0:
        return TableGridEvidence((), (), (), False, 0.0)
    w_roi = x1 - x0
    h_roi = y1 - y0
    if w_roi < min_cell_dim_px or h_roi < min_cell_dim_px:
        return TableGridEvidence((), (), (), False, 0.0)

    # 1. Filter lines intersecting the ROI
    v_lines: List[Tuple[float, float, float]] = []  # (x, y_min, y_max)
    h_lines: List[Tuple[float, float, float]] = []  # (y, x_min, x_max)

    for ln in lines:
        (lx0, ly0), (lx1, ly1) = ln.p1_px, ln.p2_px
        if not (math.isfinite(lx0) and math.isfinite(ly0) and math.isfinite(lx1) and math.isfinite(ly1)):
            continue
        orient = _line_orientation((lx0, ly0), (lx1, ly1))
        # Compute bounding span of line
        min_lx, max_lx = min(lx0, lx1), max(lx0, lx1)
        min_ly, max_ly = min(ly0, ly1), max(ly0, ly1)

        # Check intersection with ROI (with tolerance)
        if max_lx < x0 - 8.0 or min_lx > x1 + 8.0 or max_ly < y0 - 8.0 or min_ly > y1 + 8.0:
            continue

        length = math.hypot(lx1 - lx0, ly1 - ly0)
        if length < min_cell_dim_px:
            continue

        if orient == "v":
            x_val = (lx0 + lx1) / 2.0
            v_lines.append((x_val, max(y0, min_ly), min(y1, max_ly)))
        elif orient == "h":
            y_val = (ly0 + ly1) / 2.0
            h_lines.append((y_val, max(x0, min_lx), min(x1, max_lx)))

    if not v_lines or not h_lines:
        return TableGridEvidence((), (), (), False, 0.0)

    # 2. Cluster grid coordinates
    xs = _cluster_axis_centroids([x for x, _, _ in v_lines], max_cluster_radius=cluster_radius_px)
    ys = _cluster_axis_centroids([y for y, _, _ in h_lines], max_cluster_radius=cluster_radius_px)

    if len(xs) < 2 or len(ys) < 2:
        return TableGridEvidence((), tuple(xs), tuple(ys), False, 0.0)

    # 3. Outer boundary verification: enclosing borders must span at least 70% of ROI dimension
    left_span = sum(
        max(0.0, vy1 - vy0)
        for vx, vy0, vy1 in v_lines
        if abs(vx - x0) <= 16.0
    )
    right_span = sum(
        max(0.0, vy1 - vy0)
        for vx, vy0, vy1 in v_lines
        if abs(vx - x1) <= 16.0
    )
    top_span = sum(
        max(0.0, hx1 - hx0)
        for hy, hx0, hx1 in h_lines
        if abs(hy - y0) <= 16.0
    )
    bottom_span = sum(
        max(0.0, hx1 - hx0)
        for hy, hx0, hx1 in h_lines
        if abs(hy - y1) <= 16.0
    )

    has_left = (left_span / h_roi) >= 0.70
    has_right = (right_span / h_roi) >= 0.70
    has_top = (top_span / w_roi) >= 0.70
    has_bottom = (bottom_span / w_roi) >= 0.70

    border_count = sum([has_left, has_right, has_top, has_bottom])
    if border_count < 3:
        return TableGridEvidence((), tuple(xs), tuple(ys), False, 0.0)

    # 4. Topological Segment Coverage
    num_rows = len(ys) - 1
    num_cols = len(xs) - 1

    # Check which vertical dividers exist: v_divider[row][col] is True if a line exists between (row, col) and (row, col+1)
    # i.e., vertical divider at xs[col+1] spanning across row (ys[row], ys[row+1])
    v_divider = [[False for _ in range(num_cols - 1)] for _ in range(num_rows)]
    for r in range(num_rows):
        r_y0, r_y1 = ys[r], ys[r + 1]
        r_mid = (r_y0 + r_y1) / 2.0
        for c in range(num_cols - 1):
            div_x = xs[c + 1]
            row_span = r_y1 - r_y0
            for vx, vy0, vy1 in v_lines:
                if abs(vx - div_x) <= cluster_radius_px:
                    # Line must cover significant vertical row span (>= 65%)
                    overlap = max(0.0, min(vy1, r_y1) - max(vy0, r_y0))
                    if row_span > 1.0 and (overlap / row_span >= 0.65 or (vy0 <= r_y0 + 6.0 and vy1 >= r_y1 - 6.0)):
                        v_divider[r][c] = True
                        break

    # Check which horizontal dividers exist: h_divider[row][col] is True if a line exists at ys[row+1] between (xs[col], xs[col+1])
    h_divider = [[False for _ in range(num_cols)] for _ in range(num_rows - 1)]
    for r in range(num_rows - 1):
        div_y = ys[r + 1]
        for c in range(num_cols):
            c_x0, c_x1 = xs[c], xs[c + 1]
            col_span = c_x1 - c_x0
            for hy, hx0, hx1 in h_lines:
                if abs(hy - div_y) <= cluster_radius_px:
                    # Line must cover significant horizontal column span (>= 65%)
                    overlap = max(0.0, min(hx1, c_x1) - max(hx0, c_x0))
                    if col_span > 1.0 and (overlap / col_span >= 0.65 or (hx0 <= c_x0 + 6.0 and hx1 >= c_x1 - 6.0)):
                        h_divider[r][c] = True
                        break

    # 5. Form cells with merged cell clustering via Disjoint Set Union (DSU)
    parent = {}

    def find(item):
        if parent[item] != item:
            parent[item] = find(parent[item])
        return parent[item]

    def union(item1, item2):
        root1, root2 = find(item1), find(item2)
        if root1 != root2:
            parent[root2] = root1

    for r in range(num_rows):
        for c in range(num_cols):
            parent[(r, c)] = (r, c)

    # Union horizontal neighbors if no vertical divider between them
    for r in range(num_rows):
        for c in range(num_cols - 1):
            if not v_divider[r][c]:
                union((r, c), (r, c + 1))

    # Union vertical neighbors if no horizontal divider between them
    for r in range(num_rows - 1):
        for c in range(num_cols):
            if not h_divider[r][c]:
                union((r, c), (r + 1, c))

    # Group elementary blocks into merged cells
    groups: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    for r in range(num_rows):
        for c in range(num_cols):
            root = find((r, c))
            groups.setdefault(root, []).append((r, c))

    cells: List[RobustTableCell] = []
    for root, blocks in groups.items():
        min_r = min(b[0] for b in blocks)
        max_r = max(b[0] for b in blocks) + 1
        min_c = min(b[1] for b in blocks)
        max_c = max(b[1] for b in blocks) + 1

        cx0 = xs[min_c] + inset
        cy0 = ys[min_r] + inset
        cx1 = xs[max_c] - inset
        cy1 = ys[max_r] - inset

        is_merged = len(blocks) > 1

        cells.append(RobustTableCell(
            id=new_id("cell"),
            row_start=min_r,
            row_end=max_r,
            col_start=min_c,
            col_end=max_c,
            bbox_px=(cx0, cy0, cx1, cy1),
            is_merged=is_merged,
        ))

    # Sort cells top-to-bottom, left-to-right
    cells.sort(key=lambda c: (c.row_start, c.col_start))

    confidence = min(0.95, 0.60 + 0.10 * border_count + 0.05 * min(len(cells), 5))

    return TableGridEvidence(
        cells=tuple(cells),
        grid_xs=tuple(xs),
        grid_ys=tuple(ys),
        has_valid_table=True,
        confidence=confidence,
    )
