"""Degenerate cases, stress scenarios, and performance tests for cutting plane correspondence."""

import math
import sys
import time
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from cutting_plane_engine import (
    Point2D,
    ViewRegion,
    run_strategy_d,
    CuttingPlaneCorrespondenceOracle,
)
from primitive_ir_lib.text_extraction import RawText
from primitive_ir_lib.geometry_extraction import RawLine


def test_perf_large_sheet_with_dense_primitives():
    """Performance test: 1,000 lines, 200 text elements, 10 views solved under 300ms."""
    views = [
        ViewRegion(id=f"view_{i}", bbox_px=(float(i * 300), 500.0, float(i * 300 + 200), 700.0))
        for i in range(5)
    ]
    # Add section views
    for i in range(5):
        views.append(ViewRegion(
            id=f"sec_{i}",
            bbox_px=(float(i * 300), 100.0, float(i * 300 + 200), 300.0)
        ))

    # Dense texts (mostly general notes and dimensions)
    texts: list[RawText] = []
    for i in range(200):
        texts.append(RawText(
            id=f"txt_{i}",
            content=f"NOTE {i}: General tolerance +/- 0.1",
            bbox_px=(float(i * 10), 800.0, float(i * 10 + 50), 820.0),
            rotation_deg=0.0,
            confidence=0.9,
            source="text",
        ))

    # Add section titles and cutting tags
    tags = ["A", "B", "C", "D", "E"]
    arrows: list[dict] = []
    for i, tag in enumerate(tags):
        texts.append(RawText(
            id=f"t_sec_{tag}",
            content=f"SECTION {tag}-{tag}",
            bbox_px=(float(i * 300), 320.0, float(i * 300 + 100), 340.0),
            rotation_deg=0.0,
            confidence=0.95,
            source="text",
        ))
        texts.append(RawText(id=f"lbl1_{tag}", content=tag, bbox_px=(float(i * 300 - 10), 590.0, float(i * 300), 610.0), rotation_deg=0.0, confidence=0.9, source="text"))
        texts.append(RawText(id=f"lbl2_{tag}", content=tag, bbox_px=(float(i * 300 + 200), 590.0, float(i * 300 + 210), 610.0), rotation_deg=0.0, confidence=0.9, source="text"))
        arrows.append({"tip": (float(i * 300), 580.0), "tail": (float(i * 300), 600.0), "primitive_ids": [f"a1_{tag}"]})
        arrows.append({"tip": (float(i * 300 + 200), 580.0), "tail": (float(i * 300 + 200), 600.0), "primitive_ids": [f"a2_{tag}"]})

    # Dense lines
    lines: list[RawLine] = []
    for i in range(1000):
        lines.append(RawLine(
            id=f"l_{i}",
            p1_px=(float(i), float(i % 100)),
            p2_px=(float(i + 50), float(i % 100)),
            confidence=0.9,
            bbox_px=(float(i), float(i % 100), float(i + 50), float(i % 100)),
        ))

    t0 = time.perf_counter()
    res = run_strategy_d(views, lines, texts, arrows)
    elapsed = time.perf_counter() - t0

    assert len(res) == 5
    assert all(c.status == "verified" for c in res)
    assert elapsed < 0.30, f"Expected runtime < 300ms, took {elapsed * 1000:.2f}ms"


def test_huge_coordinates_macro_scale():
    """Macro scale: coordinates in tens of thousands (e.g. ship / building drawing)."""
    views = [
        ViewRegion(id="v_hull", bbox_px=(10000.0, 30000.0, 50000.0, 50000.0)),
        ViewRegion(id="v_sec", bbox_px=(10000.0, 5000.0, 50000.0, 25000.0)),
    ]
    texts = [
        RawText(id="t1", content="SECTION A-A", bbox_px=(29000, 25100, 31000, 25300), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t2", content="A", bbox_px=(9985, 39990, 9995, 40010), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t3", content="A", bbox_px=(50005, 39990, 50015, 40010), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows = [
        {"tip": (10000.0, 38000.0), "tail": (10000.0, 40000.0), "primitive_ids": ["a1"]},
        {"tip": (50000.0, 38000.0), "tail": (50000.0, 40000.0), "primitive_ids": ["a2"]},
    ]

    res = run_strategy_d(views, [], texts, arrows)
    assert len(res) == 1
    assert res[0].status == "verified"


def test_micro_scale_geometry():
    """Micro scale: dimensions in fractions of a millimeter (e.g. MEMS device)."""
    views = [
        ViewRegion(id="v_mems", bbox_px=(0.10, 0.30, 0.30, 0.50)),
        ViewRegion(id="v_sec", bbox_px=(0.10, 0.05, 0.30, 0.25)),
    ]
    texts = [
        RawText(id="t1", content="SECTION M-M", bbox_px=(0.10, 0.26, 0.20, 0.28), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t2", content="M", bbox_px=(0.09, 0.39, 0.098, 0.41), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t3", content="M", bbox_px=(0.302, 0.39, 0.310, 0.41), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows = [
        {"tip": (0.10, 0.38), "tail": (0.10, 0.40), "primitive_ids": ["a1"]},
        {"tip": (0.30, 0.38), "tail": (0.30, 0.40), "primitive_ids": ["a2"]},
    ]

    res = run_strategy_d(views, [], texts, arrows)
    assert len(res) == 1
    assert res[0].status == "verified"


def test_zero_length_arrow_rejection():
    """Degenerate case: arrow tip equals tail (zero length vector)."""
    views = [
        ViewRegion(id="v1", bbox_px=(100.0, 100.0, 200.0, 200.0)),
    ]
    arrows = [
        {"tip": (150.0, 150.0), "tail": (150.0, 150.0), "primitive_ids": ["a0"]},
    ]
    texts = [
        RawText(id="t1", content="A", bbox_px=(145, 145, 155, 155), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    oracle = CuttingPlaneCorrespondenceOracle()
    extracted = oracle.extract_viewing_arrows(arrows, texts)
    assert len(extracted) == 0


def test_empty_input_handling():
    """Degenerate case: empty views, lines, texts, arrows handled gracefully."""
    res = run_strategy_d([], [], [], [])
    assert res == []


def test_single_view_drawing_with_no_sections():
    """Drawing with single principal view and dimensions only."""
    views = [
        ViewRegion(id="v1", bbox_px=(100.0, 100.0, 300.0, 300.0)),
    ]
    texts = [
        RawText(id="t1", content="100.0", bbox_px=(150, 80, 180, 95), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    res = run_strategy_d(views, [], texts, [])
    assert res == []


def test_stability_repeated_execution():
    """Repeat execution 25 times to verify deterministic reproducibility."""
    views = [
        ViewRegion(id="v_front", bbox_px=(100.0, 300.0, 300.0, 500.0)),
        ViewRegion(id="v_sec", bbox_px=(100.0, 50.0, 300.0, 250.0)),
    ]
    texts = [
        RawText(id="t1", content="SECTION A-A", bbox_px=(100, 260, 200, 280), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t2", content="A", bbox_px=(90, 390, 98, 410), rotation_deg=0.0, confidence=0.9, source="text"),
        RawText(id="t3", content="A", bbox_px=(302, 390, 310, 410), rotation_deg=0.0, confidence=0.9, source="text"),
    ]
    arrows = [
        {"tip": (100.0, 380.0), "tail": (100.0, 400.0), "primitive_ids": ["a1"]},
        {"tip": (300.0, 380.0), "tail": (300.0, 400.0), "primitive_ids": ["a2"]},
    ]

    for _ in range(25):
        res = run_strategy_d(views, [], texts, arrows)
        assert len(res) == 1
        assert res[0].status == "verified"
        assert res[0].confidence > 0.95
