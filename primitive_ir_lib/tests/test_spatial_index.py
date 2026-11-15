"""Regression and parity tests for bounded 2D AABB-BVH spatial indexing."""

from __future__ import annotations

import math
import random

import pytest

from primitive_ir_lib.calibration import Calibration, auto_estimate_calibration, find_nearest_line
from primitive_ir_lib.cross_validation import cross_validate
from primitive_ir_lib.geometry_extraction import RawLine
from primitive_ir_lib.spatial_index import (
    SpatialIndex2D,
    point_to_polyline_distance,
    point_to_segment_distance,
)
from primitive_ir_lib.text_extraction import RawText


def _line(x0: float, y0: float, x1: float, y1: float, id_: str) -> RawLine:
    return RawLine(
        id=id_,
        p1_px=(x0, y0),
        p2_px=(x1, y1),
        confidence=0.9,
        bbox_px=(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)),
    )


def _dim_text(value: str, parsed: float, cx: float, cy: float, id_: str, rot: float = 0.0) -> RawText:
    return RawText(
        id=id_,
        content=value,
        bbox_px=(int(cx - 10), int(cy - 6), int(cx + 10), int(cy + 6)),
        rotation_deg=rot,
        confidence=0.95,
        source="text_tesseract",
        parsed_value=parsed,
        semantic_role="dimension_value",
    )


def test_point_to_segment_and_polyline_distances() -> None:
    assert math.isclose(point_to_segment_distance(5.0, 3.0, 0.0, 0.0, 10.0, 0.0), 3.0, rel_tol=1e-9)
    assert math.isclose(point_to_segment_distance(-3.0, 4.0, 0.0, 0.0, 10.0, 0.0), 5.0, rel_tol=1e-9)
    assert math.isclose(point_to_segment_distance(2.0, 2.0, 2.0, 2.0, 2.0, 2.0), 0.0, abs_tol=1e-12)

    pts = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    assert math.isclose(point_to_polyline_distance(14.0, 7.0, pts), 4.0, rel_tol=1e-9)
    assert math.isclose(point_to_polyline_distance(5.0, 2.0, [(5.0, 5.0)]), 3.0, rel_tol=1e-9)


def test_spatial_index_query_bbox_matches_linear_scan_with_order() -> None:
    rng = random.Random(42)
    items = []
    for i in range(180):
        x0 = rng.uniform(0.0, 2000.0)
        y0 = rng.uniform(0.0, 2000.0)
        x1 = x0 + rng.uniform(0.0, 120.0)
        y1 = y0 + rng.uniform(0.0, 120.0)
        items.append((f"item-{i}", (x0, y0, x1, y1)))

    index = SpatialIndex2D.from_items(items, bbox_fn=lambda entry: entry[1], leaf_size=8)
    assert index.count == 180

    for _ in range(35):
        qx0 = rng.uniform(-50.0, 1900.0)
        qy0 = rng.uniform(-50.0, 1900.0)
        qx1 = qx0 + rng.uniform(10.0, 450.0)
        qy1 = qy0 + rng.uniform(10.0, 450.0)
        pad = rng.choice([0.0, 15.0])
        hits = index.query_bbox((qx0, qy0, qx1, qy1), pad=pad, preserve_order=True)
        expected = [
            entry
            for entry in items
            if not (
                entry[1][2] < qx0 - pad
                or entry[1][0] > qx1 + pad
                or entry[1][3] < qy0 - pad
                or entry[1][1] > qy1 + pad
            )
        ]
        assert hits == expected


def test_spatial_index_query_nearest_matches_brute_force_with_view_and_score_hook() -> None:
    rng = random.Random(7)
    segments = []
    for i in range(150):
        x0 = rng.uniform(0.0, 1500.0)
        y0 = rng.uniform(0.0, 1500.0)
        dx = rng.uniform(5.0, 90.0) if i % 2 == 0 else rng.uniform(1.0, 4.0)
        dy = rng.uniform(1.0, 4.0) if i % 2 == 0 else rng.uniform(10.0, 90.0)
        segments.append((f"seg-{i}", ((x0, y0), (x0 + dx, y0 + dy))))

    index = SpatialIndex2D.from_items(
        segments,
        bbox_fn=lambda item: (
            min(item[1][0][0], item[1][1][0]),
            min(item[1][0][1], item[1][1][1]),
            max(item[1][0][0], item[1][1][0]),
            max(item[1][0][1], item[1][1][1]),
        ),
        leaf_size=12,
    )

    view_bbox = (150.0, 150.0, 750.0, 750.0)
    cross_pen = 80.0
    min_mult = 0.72

    def _dist_fn(px: float, py: float, item: tuple) -> float:
        (x0, y0), (x1, y1) = item[1]
        return point_to_segment_distance(px, py, x0, y0, x1, y1)

    def _mult_fn(item: tuple, bbox: tuple[float, float, float, float]) -> float:
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        return 0.72 if h > 2.5 * max(w, 1e-3) else 1.0

    for _ in range(25):
        ax = rng.uniform(0.0, 1400.0)
        ay = rng.uniform(0.0, 1400.0)
        bvh_hits = index.query_nearest(
            ax,
            ay,
            dist_fn=_dist_fn,
            score_multiplier_fn=_mult_fn,
            min_score_multiplier=min_mult,
            view_bbox=view_bbox,
            view_pad=12.0,
            cross_view_penalty=cross_pen,
            limit=3,
        )

        brute = []
        vx0, vy0, vx1, vy1 = (
            view_bbox[0] - 12.0,
            view_bbox[1] - 12.0,
            view_bbox[2] + 12.0,
            view_bbox[3] + 12.0,
        )
        for idx_orig, item in enumerate(segments):
            (x0, y0), (x1, y1) = item[1]
            bbox = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            cx, cy = 0.5 * (bbox[0] + bbox[2]), 0.5 * (bbox[1] + bbox[3])
            same_view = (vx0 <= cx <= vx1) and (vy0 <= cy <= vy1)
            raw_d = _dist_fn(ax, ay, item)
            eff = (raw_d + (0.0 if same_view else cross_pen)) * _mult_fn(item, bbox)
            brute.append((eff, idx_orig, raw_d, item, same_view))
        brute.sort(key=lambda row: (row[0], row[1]))
        expected = [(eff, raw_d, item, sv) for eff, _, raw_d, item, sv in brute[:3]]

        assert len(bvh_hits) == len(expected)
        for got, exp in zip(bvh_hits, expected):
            assert got[2][0] == exp[2][0]
            assert got[3] is exp[3]
            assert math.isclose(got[0], exp[0], rel_tol=1e-12, abs_tol=1e-12)
            assert math.isclose(got[1], exp[1], rel_tol=1e-12, abs_tol=1e-12)


@pytest.mark.parametrize("leaf_size", [1, 16])
@pytest.mark.parametrize("limit, expected", [
    (1, ["first"]),
    (2, ["first", "second"]),
    (3, ["first", "second", "third"]),
])
def test_query_nearest_retains_original_order_when_equal_distances_have_different_bounds(
    leaf_size: int, limit: int, expected: list[str],
) -> None:
    segments = [
        ("first", (-2.0, math.sqrt(2.0), 2.0, math.sqrt(2.0))),
        ("second", (0.0, 2.0, 2.0, 0.0)),
        ("third", (0.0, -2.0, 2.0, 0.0)),
    ]
    index = SpatialIndex2D.from_items(
        segments,
        bbox_fn=lambda item: (
            min(item[1][0], item[1][2]), min(item[1][1], item[1][3]),
            max(item[1][0], item[1][2]), max(item[1][1], item[1][3]),
        ),
        leaf_size=leaf_size,
    )

    def distance(x: float, y: float, item: tuple) -> float:
        return point_to_segment_distance(x, y, *item[1])

    # Exact distances tie; bbox distance must not decide which item survives top-k.
    assert [distance(0.0, 0.0, item) for item in segments] == [math.sqrt(2.0)] * 3
    hits = index.query_nearest(0.0, 0.0, dist_fn=distance, limit=limit)
    assert [item[0] for _, _, item, _ in hits] == expected


@pytest.mark.parametrize("axis", [0, 1])
@pytest.mark.parametrize("sign", [-1.0, 1.0])
@pytest.mark.parametrize("radius, offset", [(1e8, 2e-9), (2.0 ** 80, 2.0 ** 25)])
def test_indexed_witness_keeps_scalar_boundary_match_after_coordinate_cancellation(
    axis: int, sign: float, radius: float, offset: float,
) -> None:
    center = [0.0, 0.0]
    center[axis] = sign * radius
    midpoint = [0.0, 0.0]
    midpoint[axis] = -sign * offset
    boundary = _line(midpoint[0] - 1.0, midpoint[1],
                     midpoint[0] + 1.0, midpoint[1], "boundary")
    lines = [boundary] + [
        _line((5 + i) * radius, 0.0, (5 + i) * radius + 1.0, 0.0, f"far-{i}")
        for i in range(63)
    ]
    text = RawText(
        id="boundary-text", content="2", parsed_value=2.0,
        bbox_px=(center[0], center[1], center[0], center[1]),
        rotation_deg=0.0, confidence=1.0, source="synthetic",
        semantic_role="dimension_value",
    )
    scalar = find_nearest_line(text, lines, max_distance_px=radius)
    assert scalar is boundary
    indexed = find_nearest_line(
        text, lines, max_distance_px=radius,
        line_index=SpatialIndex2D.from_midpoints(lines),
    )
    assert indexed is boundary

    # The existing public caller automatically uses the index at 64 lines.
    results = cross_validate(
        [text], lines,
        Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0.0, 0.0),
                    method="manual_override"),
        max_distance_px=radius, merge_collinear=False, require_dimension_geometry=True,
    )
    assert len(results) == 1
    assert results[0].geometry_primitive_id == "boundary"
    assert results[0].status == "unverified"


def test_find_nearest_line_indexed_parity_and_sublinear_work() -> None:
    lines: list[RawLine] = []
    # Tie-break pair at exact same midpoint so original order matters.
    lines.append(_line(490.0, 500.0, 510.0, 500.0, "tie-first"))
    lines.append(_line(500.0, 490.0, 500.0, 510.0, "tie-second"))
    for i in range(400):
        bx = float((i % 20) * 300)
        by = float((i // 20) * 300)
        lines.append(_line(bx, by, bx + 100.0, by, f"grid-h-{i}"))

    index = SpatialIndex2D.from_midpoints(lines)
    texts = [
        _dim_text("20", 20.0, 500.0, 500.0, "t-tie", rot=0.0),
        _dim_text("20", 20.0, 500.0, 500.0, "t-tie-rot", rot=90.0),
        _dim_text("100", 100.0, 1250.0, 910.0, "t-grid", rot=0.0),
        _dim_text("999", 999.0, 10000.0, 10000.0, "t-miss", rot=0.0),
    ]

    for text in texts:
        brute = find_nearest_line(text, lines, max_distance_px=80.0)
        indexed = find_nearest_line(text, lines, max_distance_px=80.0, line_index=index)
        assert (indexed.id if indexed else None) == (brute.id if brute else None)

    assert index.last_leaf_items_checked < 40

    cal = Calibration(
        unit="mm",
        pixel_to_unit_scale=1.0,
        origin_px=(0.0, 0.0),
        method="manual_override",
        status="verified",
    )
    cv_results = cross_validate(texts, lines, cal, max_distance_px=80.0, merge_collinear=False)
    assert [r.geometry_primitive_id for r in cv_results] == ["tie-first", "tie-second", "grid-h-64", ""]

    est = auto_estimate_calibration(
        texts,
        lines,
        image_height_px=6000,
        max_distance_px=80.0,
        require_consensus=True,
        min_consensus_candidates=2,
        consensus_tolerance_pct=5.0,
    )
    assert est is not None
    assert math.isclose(est.pixel_to_unit_scale, 1.0, rel_tol=1e-6)
