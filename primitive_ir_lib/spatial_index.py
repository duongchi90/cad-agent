"""Bounded 2D AABB-BVH spatial index for primitive_ir_lib geometry queries."""

from __future__ import annotations

import heapq
import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Generic, Optional, Tuple, TypeVar

Bbox2D = Tuple[float, float, float, float]
Point2DTuple = Tuple[float, float]
T = TypeVar("T")

_DEFAULT_LEAF_SIZE = 16
DEFAULT_INDEX_MIN_LINES = 64


def point_to_segment_distance(
    px: float,
    py: float,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> float:
    """Return exact Euclidean distance from ``(px, py)`` to segment ``(x0, y0)-(x1, y1)``."""
    dx = x1 - x0
    dy = y1 - y0
    len_sq = dx * dx + dy * dy
    if len_sq <= 1e-12:
        return math.hypot(px - x0, py - y0)
    t = ((px - x0) * dx + (py - y0) * dy) / len_sq
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def point_to_polyline_distance(
    px: float,
    py: float,
    points: Sequence[Point2DTuple],
) -> float:
    """Return minimum Euclidean distance from ``(px, py)`` to a polyline vertex sequence."""
    if not points:
        raise ValueError("points must contain at least one coordinate pair")
    if len(points) == 1:
        return math.hypot(px - points[0][0], py - points[0][1])
    best = point_to_segment_distance(
        px, py, points[0][0], points[0][1], points[1][0], points[1][1]
    )
    for idx in range(1, len(points) - 1):
        d = point_to_segment_distance(
            px, py, points[idx][0], points[idx][1], points[idx + 1][0], points[idx + 1][1]
        )
        if d < best:
            best = d
    return best


def _bbox_point_distance(px: float, py: float, x0: float, y0: float, x1: float, y1: float) -> float:
    dx = 0.0 if x0 <= px <= x1 else (x0 - px if px < x0 else px - x1)
    dy = 0.0 if y0 <= py <= y1 else (y0 - py if py < y0 else py - y1)
    return math.hypot(dx, dy)


@dataclass(slots=True)
class _IndexedRecord(Generic[T]):
    orig_idx: int
    item: T
    gx0: float
    gy0: float
    gx1: float
    gy1: float
    cx: float
    cy: float


@dataclass(slots=True)
class _BvhNode(Generic[T]):
    gx0: float
    gy0: float
    gx1: float
    gy1: float
    cx0: float
    cy0: float
    cx1: float
    cy1: float
    left: Optional[_BvhNode[T]] = None
    right: Optional[_BvhNode[T]] = None
    items: Optional[Tuple[_IndexedRecord[T], ...]] = None


class SpatialIndex2D(Generic[T]):
    """Read-only 2D AABB bounding-volume hierarchy with exact tie-break parity."""

    def __init__(
        self,
        records: Sequence[_IndexedRecord[T]],
        *,
        leaf_size: int = _DEFAULT_LEAF_SIZE,
    ) -> None:
        if leaf_size < 1:
            raise ValueError("leaf_size must be at least 1")
        self.count = len(records)
        self.last_leaf_items_checked = 0
        self._root: Optional[_BvhNode[T]] = (
            self._build(list(records), depth=0, leaf_size=leaf_size) if records else None
        )

    @classmethod
    def from_items(
        cls,
        items: Iterable[T],
        bbox_fn: Callable[[T], Bbox2D],
        *,
        centroid_fn: Optional[Callable[[T, Bbox2D], Point2DTuple]] = None,
        leaf_size: int = _DEFAULT_LEAF_SIZE,
    ) -> SpatialIndex2D[T]:
        """Build a 2D AABB-BVH from arbitrary items using ``bbox_fn``."""
        records: list[_IndexedRecord[T]] = []
        for idx, item in enumerate(items):
            x0, y0, x1, y1 = bbox_fn(item)
            gx0, gx1 = (float(x0), float(x1)) if x0 <= x1 else (float(x1), float(x0))
            gy0, gy1 = (float(y0), float(y1)) if y0 <= y1 else (float(y1), float(y0))
            if centroid_fn is not None:
                cx, cy = centroid_fn(item, (gx0, gy0, gx1, gy1))
                cx_f, cy_f = float(cx), float(cy)
            else:
                cx_f = 0.5 * (gx0 + gx1)
                cy_f = 0.5 * (gy0 + gy1)
            records.append(_IndexedRecord(idx, item, gx0, gy0, gx1, gy1, cx_f, cy_f))
        return cls(records, leaf_size=leaf_size)

    @classmethod
    def from_midpoints(
        cls,
        lines: Iterable[T],
        *,
        endpoints_fn: Optional[Callable[[T], Tuple[Point2DTuple, Point2DTuple]]] = None,
        leaf_size: int = _DEFAULT_LEAF_SIZE,
    ) -> SpatialIndex2D[T]:
        """Build a midpoint point-cloud BVH compatible with ``find_nearest_line``."""
        def _line_midpoint_bbox(line: T) -> Bbox2D:
            if endpoints_fn is not None:
                p1, p2 = endpoints_fn(line)
            else:
                p1 = line.p1_px  # type: ignore[attr-defined]
                p2 = line.p2_px  # type: ignore[attr-defined]
            mx = (p1[0] + p2[0]) / 2.0
            my = (p1[1] + p2[1]) / 2.0
            return (mx, my, mx, my)

        return cls.from_items(lines, bbox_fn=_line_midpoint_bbox, leaf_size=leaf_size)

    @classmethod
    def _build(
        cls,
        recs: list[_IndexedRecord[T]],
        depth: int,
        leaf_size: int,
    ) -> _BvhNode[T]:
        gx0 = min(r.gx0 for r in recs)
        gy0 = min(r.gy0 for r in recs)
        gx1 = max(r.gx1 for r in recs)
        gy1 = max(r.gy1 for r in recs)
        cx0 = min(r.cx for r in recs)
        cy0 = min(r.cy for r in recs)
        cx1 = max(r.cx for r in recs)
        cy1 = max(r.cy for r in recs)
        if len(recs) <= leaf_size or depth >= 24:
            return _BvhNode(gx0, gy0, gx1, gy1, cx0, cy0, cx1, cy1, items=tuple(recs))

        if (cx1 - cx0) >= (cy1 - cy0):
            recs.sort(key=lambda r: (r.cx, r.orig_idx))
        else:
            recs.sort(key=lambda r: (r.cy, r.orig_idx))
        mid = len(recs) // 2
        if mid <= 0 or mid >= len(recs):
            return _BvhNode(gx0, gy0, gx1, gy1, cx0, cy0, cx1, cy1, items=tuple(recs))

        left = cls._build(recs[:mid], depth + 1, leaf_size)
        right = cls._build(recs[mid:], depth + 1, leaf_size)
        return _BvhNode(gx0, gy0, gx1, gy1, cx0, cy0, cx1, cy1, left=left, right=right)

    def query_bbox(
        self,
        bbox: Bbox2D,
        *,
        pad: float = 0.0,
        preserve_order: bool = True,
    ) -> list[T]:
        """Return items whose indexed AABB overlaps ``bbox`` expanded by ``pad``."""
        self.last_leaf_items_checked = 0
        if self._root is None:
            return []
        qx0 = min(bbox[0], bbox[2]) - pad
        qy0 = min(bbox[1], bbox[3]) - pad
        qx1 = max(bbox[0], bbox[2]) + pad
        qy1 = max(bbox[1], bbox[3]) + pad

        stack: list[_BvhNode[T]] = [self._root]
        hits: list[Tuple[int, T]] = []
        checked = 0
        while stack:
            node = stack.pop()
            if node.gx1 < qx0 or node.gx0 > qx1 or node.gy1 < qy0 or node.gy0 > qy1:
                continue
            if node.items is not None:
                for rec in node.items:
                    checked += 1
                    if not (rec.gx1 < qx0 or rec.gx0 > qx1 or rec.gy1 < qy0 or rec.gy0 > qy1):
                        hits.append((rec.orig_idx, rec.item))
            else:
                if node.left is not None:
                    stack.append(node.left)
                if node.right is not None:
                    stack.append(node.right)
        self.last_leaf_items_checked = checked
        if preserve_order:
            hits.sort(key=lambda pair: pair[0])
        return [item for _, item in hits]

    def query_nearest(
        self,
        ax: float,
        ay: float,
        *,
        cx: Optional[float] = None,
        cy: Optional[float] = None,
        dist_fn: Callable[[float, float, T], float],
        score_multiplier_fn: Optional[Callable[[T, Bbox2D], float]] = None,
        min_score_multiplier: float = 1.0,
        view_bbox: Optional[Bbox2D] = None,
        view_pad: float = 0.0,
        cross_view_penalty: float = 0.0,
        limit: int = 2,
    ) -> list[Tuple[float, float, T, bool]]:
        """Best-first priority-queue k-NN search over AABB bounds with admissible pruning."""
        if min_score_multiplier <= 0.0:
            raise ValueError("min_score_multiplier must be positive")
        self.last_leaf_items_checked = 0
        if self._root is None or limit <= 0:
            return []

        has_second_anchor = cx is not None and cy is not None
        bx = ax if not has_second_anchor else float(cx)  # type: ignore[arg-type]
        by = ay if not has_second_anchor else float(cy)  # type: ignore[arg-type]

        has_view = view_bbox is not None
        if has_view:
            vx0p = view_bbox[0] - view_pad  # type: ignore[index]
            vy0p = view_bbox[1] - view_pad  # type: ignore[index]
            vx1p = view_bbox[2] + view_pad  # type: ignore[index]
            vy1p = view_bbox[3] + view_pad  # type: ignore[index]
        else:
            vx0p = vy0p = vx1p = vy1p = 0.0

        def _node_lb(node: _BvhNode[T]) -> float:
            lb_d = _bbox_point_distance(ax, ay, node.gx0, node.gy0, node.gx1, node.gy1)
            if has_second_anchor:
                lb_d = min(lb_d, _bbox_point_distance(bx, by, node.gx0, node.gy0, node.gx1, node.gy1))
            can_same = True
            if has_view:
                can_same = not (
                    node.cx1 < vx0p or node.cx0 > vx1p or node.cy1 < vy0p or node.cy0 > vy1p
                )
            return min_score_multiplier * (lb_d + (0.0 if can_same else cross_view_penalty))

        counter = 0
        pq: list[Tuple[float, int, _BvhNode[T]]] = [(_node_lb(self._root), counter, self._root)]
        top_heap: list[Tuple[float, int, float, T, bool]] = []
        cutoff = float("inf")
        checked = 0

        while pq:
            node_lb, _, node = heapq.heappop(pq)
            if len(top_heap) >= limit and node_lb > cutoff + 1e-9:
                break
            if node.items is not None:
                for rec in node.items:
                    checked += 1
                    lb_d = _bbox_point_distance(ax, ay, rec.gx0, rec.gy0, rec.gx1, rec.gy1)
                    if has_second_anchor:
                        lb_d = min(
                            lb_d,
                            _bbox_point_distance(bx, by, rec.gx0, rec.gy0, rec.gx1, rec.gy1),
                        )
                    same_view = True
                    if has_view:
                        same_view = (vx0p <= rec.cx <= vx1p) and (vy0p <= rec.cy <= vy1p)
                    lb_eff = min_score_multiplier * (lb_d + (0.0 if same_view else cross_view_penalty))
                    if len(top_heap) >= limit and lb_eff > cutoff + 1e-9:
                        continue
                    raw_d = float(dist_fn(ax, ay, rec.item))
                    if has_second_anchor:
                        raw_d = min(raw_d, float(dist_fn(bx, by, rec.item)))
                    mult = (
                        float(score_multiplier_fn(rec.item, (rec.gx0, rec.gy0, rec.gx1, rec.gy1)))
                        if score_multiplier_fn is not None
                        else 1.0
                    )
                    eff_dist = (raw_d + (0.0 if same_view else cross_view_penalty)) * mult
                    entry = (-eff_dist, -rec.orig_idx, raw_d, rec.item, same_view)
                    if len(top_heap) < limit:
                        heapq.heappush(top_heap, entry)
                        if len(top_heap) == limit:
                            cutoff = -top_heap[0][0]
                    elif entry > top_heap[0]:
                        heapq.heapreplace(top_heap, entry)
                        cutoff = -top_heap[0][0]
            else:
                if node.left is not None:
                    lb_l = _node_lb(node.left)
                    if len(top_heap) < limit or lb_l <= cutoff + 1e-9:
                        counter += 1
                        heapq.heappush(pq, (lb_l, counter, node.left))
                if node.right is not None:
                    lb_r = _node_lb(node.right)
                    if len(top_heap) < limit or lb_r <= cutoff + 1e-9:
                        counter += 1
                        heapq.heappush(pq, (lb_r, counter, node.right))

        self.last_leaf_items_checked = checked
        best = [
            (-neg_eff, raw_d, item, same_view, -neg_orig)
            for neg_eff, neg_orig, raw_d, item, same_view in top_heap
        ]
        best.sort(key=lambda row: (row[0], row[4]))
        return [(eff, raw_d, item, sv) for eff, raw_d, item, sv, _ in best]
