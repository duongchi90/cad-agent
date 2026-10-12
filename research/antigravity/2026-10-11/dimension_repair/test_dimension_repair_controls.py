"""
test_dimension_repair_controls.py — Positive Fixtures and Strong Negative Controls
for Headless Linear Dimension & Associativity Repair in DXF Builder.

Positive fixtures:
- PF1: Horizontal dimension repair round-trip
- PF2: Vertical dimension repair round-trip
- PF3: Chained multi-dimension repair (3 adjacent dimensions)
- PF4: Dynamic layer creation on demand

Strong negative controls:
- NC1: Missing written_geometry in BuildResult safely skipped
- NC2: Non-line primitive referenced by dimension spec safely skipped
- NC3: Zero-length line geometry safely skipped (no division by zero)
- NC4: Empty mismatches list returns immediately without file mutation
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
import pytest

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from primitive_ir_lib.models import (
    Calibration, CircleGeometry, LineGeometry, Point2D, Primitive,
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


def test_positive_horizontal_dimension_repair():
    """PF1: Clean repair of standard horizontal dimension."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        doc = PrimitiveIRDocument(
            source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=200, image_height_px=200),
            calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
            primitives=[
                Primitive(id="l1", type="line", source="geo", confidence=1.0,
                          trace=Trace(bbox_px=(0, 0, 10, 10)),
                          geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(100, 0)))
            ],
        )
        p = os.path.join(tmp, "out.dxf")
        spec = NativeLinearDimensionSpec("DIM-H", "l1", 100.0, "REF-H")
        built = build_dxf(doc, p, build_dimensions=True, dimension_specs=[spec])

        # Tamper
        dxf = ezdxf.readfile(p)
        dxf.entitydb.get(built.dimension_handle_by_cross_validation_id["DIM-H"]).dxf.layer = "BAD"
        dxf.saveas(p)

        rev1 = review_dxf(built)
        assert not rev1.passed

        rep = repair_dimensions_strategy_d(built, rev1.dimension_mismatches)
        assert rep.repaired_count == 1
        assert rep.skipped_count == 0

        rev2 = review_dxf(built)
        assert rev2.passed is True


def test_positive_vertical_dimension_repair():
    """PF2: Clean repair of vertical dimension."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        doc = PrimitiveIRDocument(
            source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=200, image_height_px=200),
            calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
            primitives=[
                Primitive(id="l1", type="line", source="geo", confidence=1.0,
                          trace=Trace(bbox_px=(0, 0, 10, 10)),
                          geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(0, 150)))
            ],
        )
        p = os.path.join(tmp, "out.dxf")
        spec = NativeLinearDimensionSpec("DIM-V", "l1", 150.0, "REF-V")
        built = build_dxf(doc, p, build_dimensions=True, dimension_specs=[spec])

        # Tamper
        dxf = ezdxf.readfile(p)
        dxf.entitydb.get(built.dimension_handle_by_cross_validation_id["DIM-V"]).dxf.layer = "BAD_V"
        dxf.saveas(p)

        rev1 = review_dxf(built)
        assert not rev1.passed

        rep = repair_dimensions_strategy_d(built, rev1.dimension_mismatches)
        assert rep.repaired_count == 1

        rev2 = review_dxf(built)
        assert rev2.passed is True


def test_positive_chained_multi_dimension_repair():
    """PF3: 3 adjacent chained dimensions all repaired simultaneously."""
    if not _HAS_EZDXF:
        pytest.skip("ezdxf required")
    with tempfile.TemporaryDirectory() as tmp:
        doc = PrimitiveIRDocument(
            source_document=SourceDocument(file_name="fx.png", page_index=0, image_width_px=300, image_height_px=300),
            calibration=Calibration(unit="mm", pixel_to_unit_scale=1.0, origin_px=(0, 0), method="manual_override"),
            primitives=[
                Primitive(id="l1", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                          geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(50, 0))),
                Primitive(id="l2", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                          geometry=LineGeometry(start=Point2D(50, 0), end=Point2D(120, 0))),
                Primitive(id="l3", type="line", source="geo", confidence=1.0, trace=Trace(bbox_px=(0,0,1,1)),
                          geometry=LineGeometry(start=Point2D(120, 0), end=Point2D(200, 0))),
            ],
        )
        p = os.path.join(tmp, "out.dxf")
        specs = [
            NativeLinearDimensionSpec("D1", "l1", 50.0, "R1"),
            NativeLinearDimensionSpec("D2", "l2", 70.0, "R2"),
            NativeLinearDimensionSpec("D3", "l3", 80.0, "R3"),
        ]
        built = build_dxf(doc, p, build_dimensions=True, dimension_specs=specs)

        # Delete all 3 dimensions
        dxf = ezdxf.readfile(p)
        for d in ("D1", "D2", "D3"):
            dxf.modelspace().delete_entity(dxf.entitydb.get(built.dimension_handle_by_cross_validation_id[d]))
        dxf.saveas(p)

        rev1 = review_dxf(built)
        assert not rev1.passed

        rep = repair_dimensions_strategy_d(built, rev1.dimension_mismatches)
        assert rep.repaired_count == 3

        rev2 = review_dxf(built)
        assert rev2.passed is True


def test_positive_layer_creation_on_demand():
    """PF4: Ensures target layer is created if absent from DXF."""
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
        spec = NativeLinearDimensionSpec("DIM-CUSTOM", "l1", 80.0, "REF")
        built = build_dxf(doc, p, build_dimensions=True, dimension_specs=[spec])

        # Change expected layer in build_result to a custom layer
        built.written_dimension_by_cross_validation_id["DIM-CUSTOM"]["layer"] = "CUSTOM_DIM_LAYER"

        rev1 = review_dxf(built)
        assert not rev1.passed

        rep = repair_dimensions_strategy_d(built, rev1.dimension_mismatches)
        assert rep.repaired_count == 1

        dxf = ezdxf.readfile(p)
        assert "CUSTOM_DIM_LAYER" in dxf.layers
        rev2 = review_dxf(built)
        assert rev2.passed is True


def test_negative_missing_written_geometry_safely_skipped():
    """NC1: Missing written_geometry in BuildResult is safely skipped."""
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

        # Remove l1 from written_geometry
        del built.written_geometry_by_primitive_id["l1"]

        rep = repair_dimensions_strategy_d(built, ["D1: expected measurement 80.0, actual 50.0"])
        assert rep.repaired_count == 0
        assert rep.skipped_count == 1
        assert "D1" in rep.skipped_validation_ids


def test_negative_non_line_primitive_safely_skipped():
    """NC2: Non-line primitive referenced by dimension spec is safely skipped."""
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

        # Change primitive type to circle in written_geometry
        built.written_geometry_by_primitive_id["l1"] = {
            "type": "circle", "center": (0, 0), "radius": 40.0
        }

        rep = repair_dimensions_strategy_d(built, ["D1: expected measurement 80.0, actual 50.0"])
        assert rep.repaired_count == 0
        assert rep.skipped_count == 1
        assert "D1" in rep.skipped_validation_ids


def test_negative_zero_length_line_safely_skipped():
    """NC3: Zero-length line geometry is safely skipped without crash."""
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

        # Change geometry to zero-length
        built.written_geometry_by_primitive_id["l1"]["end"] = (0.0, 0.0)

        rep = repair_dimensions_strategy_d(built, ["D1: expected measurement 80.0, actual 0.0"])
        assert rep.repaired_count == 0
        assert rep.skipped_count == 1
        assert "D1" in rep.skipped_validation_ids


def test_negative_empty_mismatches_noop():
    """NC4: Empty mismatches list returns immediately without opening DXF."""
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

        stat_before = os.stat(p).st_mtime_ns

        rep = repair_dimensions_strategy_d(built, [])
        assert rep.repaired_count == 0
        assert rep.skipped_count == 0

        # File was not modified
        assert os.stat(p).st_mtime_ns == stat_before
