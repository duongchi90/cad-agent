"""
test_dimension_repair_degenerate_and_perf.py — Degenerate, Non-Finite & Performance
Benchmarks for Headless Linear Dimension & Associativity Repair in DXF Builder.

Test matrix:
- D1: NaN coordinate in feature geometry -> safe skip
- D2: Inf coordinate in feature geometry -> safe skip
- D3: Extreme coordinates (10^6 mm) handled without numeric overflow
- D4: Micro-segment line (0.001 mm) handled with finite precision
- D5: Malformed mismatch strings without delimiter -> safe skip
- P1: Performance benchmark: 50 dimension repairs completed in < 150 ms
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
import time
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from primitive_ir_lib.models import (
    Calibration, LineGeometry, Point2D, Primitive,
    PrimitiveIRDocument, SourceDocument, Trace,
)
from dxf_builder_lib.builder import NativeLinearDimensionSpec, build_dxf
from dxf_builder_lib.reviewer import review_dxf

try:
    import ezdxf
    _HAS_EZDXF = True
except ImportError:
    _HAS_EZDXF = False

from dimension_repair_engine import repair_dimensions_strategy_d


def test_degenerate_nan_coordinate_failsafe():
    """D1: NaN coordinates in line geometry are skipped safely without crash."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        doc = PrimitiveIRDocument(
            source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=200, image_height_px=200),
            calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
            primitives=[
                Primitive(id="l1", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                          geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(80, 0))),
            ],
        )
        p = os.path.join(tmp, "out.dxf")
        spec = NativeLinearDimensionSpec("D1", "l1", 80.0, "REF")
        built = build_dxf(doc, p, build_dimensions=True, dimension_specs=[spec])

        built.written_geometry_by_primitive_id["l1"]["start"] = (float("nan"), 0.0)

        rep = repair_dimensions_strategy_d(built, ["D1: expected measurement 80.0, actual 50.0"])
        assert rep.repaired_count == 0
        assert rep.skipped_count == 1
        assert "D1" in rep.skipped_validation_ids


def test_degenerate_inf_coordinate_failsafe():
    """D2: Inf coordinates in line geometry are skipped safely without crash."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        doc = PrimitiveIRDocument(
            source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=200, image_height_px=200),
            calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
            primitives=[
                Primitive(id="l1", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                          geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(80, 0))),
            ],
        )
        p = os.path.join(tmp, "out.dxf")
        spec = NativeLinearDimensionSpec("D1", "l1", 80.0, "REF")
        built = build_dxf(doc, p, build_dimensions=True, dimension_specs=[spec])

        built.written_geometry_by_primitive_id["l1"]["end"] = (float("inf"), 0.0)

        rep = repair_dimensions_strategy_d(built, ["D1: expected measurement 80.0, actual 50.0"])
        assert rep.repaired_count == 0
        assert rep.skipped_count == 1
        assert "D1" in rep.skipped_validation_ids


def test_degenerate_extreme_coordinates():
    """D3: Coordinates at 10^6 mm handled without overflow."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        doc = PrimitiveIRDocument(
            source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=200, image_height_px=200),
            calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
            primitives=[
                Primitive(id="l1", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                          geometry=LineGeometry(start=Point2D(1_000_000, 1_000_000), end=Point2D(1_000_100, 1_000_000))),
            ],
        )
        p = os.path.join(tmp, "out.dxf")
        spec = NativeLinearDimensionSpec("D_EXTREME", "l1", 100.0, "REF")
        built = build_dxf(doc, p, build_dimensions=True, dimension_specs=[spec])

        # Tamper
        dxf = ezdxf.readfile(p)
        dxf.entitydb.get(built.dimension_handle_by_cross_validation_id["D_EXTREME"]).dxf.layer = "BAD"
        dxf.saveas(p)

        rev1 = review_dxf(built)
        assert not rev1.passed

        rep = repair_dimensions_strategy_d(built, rev1.dimension_mismatches)
        assert rep.repaired_count == 1

        rev2 = review_dxf(built)
        assert rev2.passed is True


def test_degenerate_micro_segment():
    """D4: Micro-segment (0.01 mm) handled with finite precision."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        doc = PrimitiveIRDocument(
            source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=200, image_height_px=200),
            calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
            primitives=[
                Primitive(id="l1", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                          geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(0.01, 0))),
            ],
        )
        p = os.path.join(tmp, "out.dxf")
        spec = NativeLinearDimensionSpec("D_MICRO", "l1", 0.01, "REF")
        built = build_dxf(doc, p, build_dimensions=True, dimension_specs=[spec])

        # Tamper
        dxf = ezdxf.readfile(p)
        dxf.entitydb.get(built.dimension_handle_by_cross_validation_id["D_MICRO"]).dxf.layer = "BAD"
        dxf.saveas(p)

        rev1 = review_dxf(built)
        assert not rev1.passed

        rep = repair_dimensions_strategy_d(built, rev1.dimension_mismatches)
        assert rep.repaired_count == 1

        rev2 = review_dxf(built)
        assert rev2.passed is True


def test_degenerate_malformed_mismatch_strings():
    """D5: Strings without colon or malformed entries are ignored safely."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        doc = PrimitiveIRDocument(
            source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=200, image_height_px=200),
            calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
            primitives=[
                Primitive(id="l1", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                          geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(50, 0))),
            ],
        )
        p = os.path.join(tmp, "out.dxf")
        spec = NativeLinearDimensionSpec("D1", "l1", 50.0, "REF")
        built = build_dxf(doc, p, build_dimensions=True, dimension_specs=[spec])

        malformed = [
            "Random unformatted error string",
            "",
            "   ",
            ":: missing id",
        ]
        rep = repair_dimensions_strategy_d(built, malformed)
        assert rep.repaired_count == 0
        assert rep.skipped_count == 0
        assert review_dxf(built).passed is True


def test_performance_50_dimension_repairs():
    """P1: Benchmark repairing 50 simultaneous dimensions in < 150 ms."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    N = 50
    with tempfile.TemporaryDirectory() as tmp:
        prims = []
        specs = []
        for i in range(N):
            lid = f"line_{i:03d}"
            did = f"DIM_{i:03d}"
            y = i * 20.0
            prims.append(
                Primitive(id=lid, type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                          geometry=LineGeometry(start=Point2D(0, y), end=Point2D(100, y)))
            )
            specs.append(NativeLinearDimensionSpec(did, lid, 100.0, f"REF_{i}"))

        doc = PrimitiveIRDocument(
            source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=500, image_height_px=1500),
            calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
            primitives=prims,
        )
        p = os.path.join(tmp, "perf.dxf")
        built = build_dxf(doc, p, build_dimensions=True, dimension_specs=specs)

        # Corrupt all 50 dimensions by changing layer
        dxf = ezdxf.readfile(p)
        for i in range(N):
            did = f"DIM_{i:03d}"
            h = built.dimension_handle_by_cross_validation_id[did]
            dxf.entitydb.get(h).dxf.layer = "BAD_LAYER"
        dxf.saveas(p)

        rev1 = review_dxf(built)
        assert len(rev1.dimension_mismatches) == N

        t0 = time.perf_counter()
        rep = repair_dimensions_strategy_d(built, rev1.dimension_mismatches)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert rep.repaired_count == N
        assert elapsed_ms < 150.0, f"Repair latency {elapsed_ms:.2f} ms exceeded 150 ms budget"

        rev2 = review_dxf(built)
        assert rev2.passed is True
