"""test_dimension_attachment_benchmark.py - Empirical Multi-Strategy Benchmark.

Compares Strategies A, B, C, and D across 8 dimension scenarios:
1. Baseline clean horizontal dimension (0 gap, no slant, origin crop).
2. Slanted extension line with overshoot past dimension line.
3. Standard 300 DPI drafting gap (1.5mm / 18px gap to workpiece datums).
4. Page-offset dimension cluster (crop offset at (250, 400)).
5. Transitive 3-box cluster topology (bridge box).
6. Multi-anchor disambiguation (4 datums: 2 target, 2 distractors).
7. Angled 45-degree dimension with overshoot.
8. Vertical dimension with overshoot and standard drafting gap.

Part of Antigravity Research: OFFLINE_DIMENSION_CLUSTER_TOPOLOGY_AND_ATTACHMENT_V1
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from dimension_attachment_engine import (
    DimensionGeometryData,
    resolve_dimension_cluster,
)


def scenario_1_clean_horizontal() -> tuple[list[tuple[int, int, int, int]], DimensionGeometryData, list[dict], str, tuple[float, float]]:
    boxes = [(50, 20, 150, 40)]
    geom = DimensionGeometryData(
        dimension_line=((80.0, 35.0), (340.0, 35.0)),
        extension_lines=(
            ((80.0, 35.0), (80.0, 115.0)),
            ((340.0, 35.0), (340.0, 115.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "DATUM_A", "type": "FEATURE", "view_id": "SIDE", "point_px": [80.0, 115.0], "confidence": 1.0},
        {"id": "DATUM_B", "type": "FEATURE", "view_id": "SIDE", "point_px": [340.0, 115.0], "confidence": 1.0},
    ]
    return boxes, geom, anchors, "SIDE", (0.0, 0.0)


def scenario_2_slanted_overshoot() -> tuple[list[tuple[int, int, int, int]], DimensionGeometryData, list[dict], str, tuple[float, float]]:
    boxes = [(50, 20, 150, 40)]
    geom = DimensionGeometryData(
        dimension_line=((80.0, 35.0), (340.0, 35.0)),
        extension_lines=(
            ((80.0, 15.0), (80.0, 100.0)),
            ((348.0, 20.0), (338.0, 100.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "DATUM_A", "type": "FEATURE", "view_id": "SIDE", "point_px": [80.0, 100.0], "confidence": 1.0},
        {"id": "DATUM_B", "type": "FEATURE", "view_id": "SIDE", "point_px": [338.0, 100.0], "confidence": 1.0},
    ]
    return boxes, geom, anchors, "SIDE", (0.0, 0.0)


def scenario_3_standard_300dpi_gap() -> tuple[list[tuple[int, int, int, int]], DimensionGeometryData, list[dict], str, tuple[float, float]]:
    boxes = [(50, 20, 150, 40)]
    geom = DimensionGeometryData(
        dimension_line=((80.0, 35.0), (340.0, 35.0)),
        extension_lines=(
            ((80.0, 15.0), (80.0, 97.0)),  # 18px gap to y=115
            ((340.0, 15.0), (340.0, 97.0)),  # 18px gap to y=115
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "DATUM_A", "type": "FEATURE", "view_id": "SIDE", "point_px": [80.0, 115.0], "confidence": 1.0},
        {"id": "DATUM_B", "type": "FEATURE", "view_id": "SIDE", "point_px": [340.0, 115.0], "confidence": 1.0},
    ]
    return boxes, geom, anchors, "SIDE", (0.0, 0.0)


def scenario_4_page_crop_offset() -> tuple[list[tuple[int, int, int, int]], DimensionGeometryData, list[dict], str, tuple[float, float]]:
    boxes = [(250, 400, 350, 440)]
    geom = DimensionGeometryData(
        dimension_line=((80.0, 35.0), (340.0, 35.0)),
        extension_lines=(
            ((80.0, 35.0), (80.0, 115.0)),
            ((340.0, 35.0), (340.0, 115.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "DATUM_A", "type": "FEATURE", "view_id": "TOP", "point_px": [330.0, 515.0], "confidence": 1.0},
        {"id": "DATUM_B", "type": "FEATURE", "view_id": "TOP", "point_px": [590.0, 515.0], "confidence": 1.0},
    ]
    return boxes, geom, anchors, "TOP", (250.0, 400.0)


def scenario_5_transitive_clustering() -> tuple[list[tuple[int, int, int, int]], DimensionGeometryData, list[dict], str, tuple[float, float]]:
    boxes = [
        (10, 10, 30, 30),
        (50, 10, 70, 30),
        (25, 15, 55, 35),
    ]
    geom = DimensionGeometryData(
        dimension_line=((20.0, 20.0), (60.0, 20.0)),
        extension_lines=(
            ((20.0, 20.0), (20.0, 40.0)),
            ((60.0, 20.0), (60.0, 40.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "DATUM_A", "type": "FEATURE", "view_id": "SIDE", "point_px": [20.0, 40.0], "confidence": 1.0},
        {"id": "DATUM_B", "type": "FEATURE", "view_id": "SIDE", "point_px": [60.0, 40.0], "confidence": 1.0},
    ]
    return boxes, geom, anchors, "SIDE", (0.0, 0.0)


def scenario_6_multi_anchor_disambiguation() -> tuple[list[tuple[int, int, int, int]], DimensionGeometryData, list[dict], str, tuple[float, float]]:
    boxes = [(50, 20, 150, 40)]
    geom = DimensionGeometryData(
        dimension_line=((80.0, 35.0), (340.0, 35.0)),
        extension_lines=(
            ((80.0, 35.0), (80.0, 115.0)),
            ((340.0, 35.0), (340.0, 115.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "DATUM_A", "type": "FEATURE", "view_id": "SIDE", "point_px": [80.0, 115.0], "confidence": 1.0},
        {"id": "DATUM_B", "type": "FEATURE", "view_id": "SIDE", "point_px": [340.0, 115.0], "confidence": 1.0},
        {"id": "DISTRACTOR_C", "type": "FEATURE", "view_id": "SIDE", "point_px": [80.0, 180.0], "confidence": 1.0},
        {"id": "DISTRACTOR_D", "type": "FEATURE", "view_id": "OTHER", "point_px": [340.0, 115.0], "confidence": 1.0},
    ]
    return boxes, geom, anchors, "SIDE", (0.0, 0.0)


def scenario_7_angled_45deg_dimension() -> tuple[list[tuple[int, int, int, int]], DimensionGeometryData, list[dict], str, tuple[float, float]]:
    boxes = [(40, 40, 250, 250)]
    # 45-degree dimension line from (50, 50) to (200, 200). Normal is (-1, 1)/sqrt(2).
    # Extension 0 at (50, 50) extends along normal to (30, 70), with overshoot to (60, 40).
    # Extension 1 at (200, 200) extends along normal to (180, 220), with overshoot to (210, 190).
    geom = DimensionGeometryData(
        dimension_line=((50.0, 50.0), (200.0, 200.0)),
        extension_lines=(
            ((60.0, 40.0), (30.0, 70.0)),
            ((210.0, 190.0), (180.0, 220.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "DATUM_A", "type": "FEATURE", "view_id": "ISO", "point_px": [30.0, 70.0], "confidence": 1.0},
        {"id": "DATUM_B", "type": "FEATURE", "view_id": "ISO", "point_px": [180.0, 220.0], "confidence": 1.0},
    ]
    return boxes, geom, anchors, "ISO", (0.0, 0.0)


def scenario_8_vertical_overshoot_and_gap() -> tuple[list[tuple[int, int, int, int]], DimensionGeometryData, list[dict], str, tuple[float, float]]:
    boxes = [(20, 50, 150, 350)]
    # Vertical dimension from (80, 50) to (80, 300).
    # Extensions extend horizontally to the right (+x) towards workpiece at x=160.
    # Extensions stop at x=142 (leaving 18px gap). Overshoot is at x=60.
    geom = DimensionGeometryData(
        dimension_line=((80.0, 50.0), (80.0, 300.0)),
        extension_lines=(
            ((60.0, 50.0), (142.0, 50.0)),
            ((60.0, 300.0), (142.0, 300.0)),
        ),
        confidence=1.0,
    )
    anchors = [
        {"id": "DATUM_A", "type": "FEATURE", "view_id": "FRONT", "point_px": [160.0, 50.0], "confidence": 1.0},
        {"id": "DATUM_B", "type": "FEATURE", "view_id": "FRONT", "point_px": [160.0, 300.0], "confidence": 1.0},
    ]
    return boxes, geom, anchors, "FRONT", (0.0, 0.0)


ALL_SCENARIOS = [
    ("Scenario 1 (Baseline Horizontal)", scenario_1_clean_horizontal),
    ("Scenario 2 (Slanted Overshoot)", scenario_2_slanted_overshoot),
    ("Scenario 3 (300 DPI Gap)", scenario_3_standard_300dpi_gap),
    ("Scenario 4 (Page Crop Offset)", scenario_4_page_crop_offset),
    ("Scenario 5 (Transitive Clustering)", scenario_5_transitive_clustering),
    ("Scenario 6 (Multi-Anchor Disambig)", scenario_6_multi_anchor_disambiguation),
    ("Scenario 7 (Angled 45-deg)", scenario_7_angled_45deg_dimension),
    ("Scenario 8 (Vertical Overshoot+Gap)", scenario_8_vertical_overshoot_and_gap),
]


def evaluate_strategy_on_scenarios(strategy: str) -> tuple[int, int, list[str]]:
    passed = 0
    total = len(ALL_SCENARIOS)
    failures: list[str] = []

    for name, scen_fn in ALL_SCENARIOS:
        boxes, geom, anchors, view_id, offset = scen_fn()
        res = resolve_dimension_cluster(
            boxes, geom, semantic_anchors=anchors, view_id=view_id, strategy=strategy, crop_offset_px=offset
        )
        # Check clustering transitive closure if multiple boxes
        cluster_ok = True
        if "Scenario 5" in name:
            cluster_ok = len(res.cluster_boxes) == 1

        attachment_ok = (
            res.attachment_resolved
            and res.best_attachment is not None
            and res.best_attachment.from_ref["id"] == "DATUM_A"
            and res.best_attachment.to_ref["id"] == "DATUM_B"
        )

        if cluster_ok and attachment_ok:
            passed += 1
        else:
            failures.append(f"{name}: cluster_ok={cluster_ok}, attachment_ok={attachment_ok}, reasons={res.reasons}")

    return passed, total, failures


def test_benchmark_strategy_a_accuracy() -> None:
    passed, total, failures = evaluate_strategy_on_scenarios("A")
    rate = passed / total
    # Strategy A fails on Scenarios 2, 3, 4, 5, 8 due to line[0] flaw, fixed 20px decay, offset ignoring, etc.
    assert rate == 0.375, f"Strategy A expected 37.5% (3/8), got {rate*100}%: {failures}"


def test_benchmark_strategy_b_accuracy() -> None:
    passed, total, failures = evaluate_strategy_on_scenarios("B")
    rate = passed / total
    # Strategy B naive distance fails without orientation or multi-anchor disambiguation
    assert rate == 0.625, f"Strategy B expected 62.5% (5/8), got {rate*100}%: {failures}"


def test_benchmark_strategy_c_accuracy() -> None:
    passed, total, failures = evaluate_strategy_on_scenarios("C")
    rate = passed / total
    # Strategy C fixed radius fails on gaps and multi-anchor disambiguation
    assert rate == 0.625, f"Strategy C expected 62.5% (5/8), got {rate*100}%: {failures}"


def test_benchmark_strategy_d_accuracy_100_percent() -> None:
    passed, total, failures = evaluate_strategy_on_scenarios("D")
    rate = passed / total
    assert rate == 1.0, f"Strategy D must achieve 100% accuracy, but failed: {failures}"
