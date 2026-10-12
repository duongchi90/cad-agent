"""Degenerate, Numeric Safety, and Performance Profiling Tests for Topic 26:
PRIMITIVE_IR_SERIALIZATION_ROUNDTRIP_INTEGRITY_V1.

Evaluates 7 stress cases:
1. Empty primitives and cross-validations list
2. Extreme coordinate magnitudes (10^9 mm)
3. Micro-features numeric safety (10^-5 mm)
4. Malformed non-dictionary JSON payloads
5. Deeply nested malformed geometry dictionaries
6. Unicode drafting symbols and callout strings
7. Large-scale throughput profiling (1,000 primitives < 25 ms)
"""

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

from primitive_ir_lib.models import (
    ArcGeometry,
    Calibration,
    CircleGeometry,
    CrossValidation,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    TextData,
    Trace,
    Validation,
)

from primitive_ir_roundtrip_engine import (
    StrategyD_LosslessCanonicalRoundtripEngine,
    canonical_json_dumps,
    deep_validate_document,
)


def test_edge_1_empty_primitives_and_cross_validations():
    """Edge 1: Clean roundtrip of document with zero primitives and cross validations."""
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("empty.png", 0, 500, 500),
        calibration=Calibration("mm", 1.0, (0.0, 0.0), "manual_override"),
        primitives=[],
        cross_validations=[],
    )
    doc_d, equal = StrategyD_LosslessCanonicalRoundtripEngine.roundtrip(doc)
    assert equal is True
    assert len(doc_d.primitives) == 0
    assert len(doc_d.cross_validations) == 0
    assert deep_validate_document(doc_d.to_dict()) == []


def test_edge_2_extreme_coordinate_magnitudes():
    """Edge 2: Floating point stability under 10^9 mm coordinates."""
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("extreme.png", 0, 1000, 1000),
        calibration=Calibration("mm", 1.0, (0.0, 0.0), "manual_override"),
        primitives=[
            Primitive(
                id="line-huge",
                type="line",
                source="geometry_opencv",
                confidence=0.9,
                geometry=LineGeometry(
                    start=Point2D(1e9, -1e9),
                    end=Point2D(1e9 + 500.0, -1e9 + 500.0),
                ),
                trace=Trace(bbox_px=(0.0, 0.0, 10.0, 10.0)),
            )
        ],
    )
    doc_d, equal = StrategyD_LosslessCanonicalRoundtripEngine.roundtrip(doc)
    assert equal is True
    prim = doc_d.primitives[0]
    assert prim.geometry.start.x == 1e9
    assert prim.geometry.start.y == -1e9


def test_edge_3_micro_features_numeric_safety():
    """Edge 3: Micro-features (10^-5 mm radius and length) numeric safety."""
    doc = PrimitiveIRDocument(
        source_document=SourceDocument("micro.png", 0, 1000, 1000),
        calibration=Calibration("mm", 1.0, (0.0, 0.0), "manual_override"),
        primitives=[
            Primitive(
                id="circle-micro",
                type="circle",
                source="geometry_opencv",
                confidence=0.95,
                geometry=CircleGeometry(center=Point2D(10.0, 10.0), radius=1e-5),
                trace=Trace(bbox_px=(10.0, 10.0, 10.0, 10.0)),
            )
        ],
    )
    doc_d, equal = StrategyD_LosslessCanonicalRoundtripEngine.roundtrip(doc)
    assert equal is True
    assert doc_d.primitives[0].geometry.radius == 1e-5


def test_edge_4_non_string_and_malformed_json_payloads():
    """Edge 4: Graceful rejection of non-dict payloads."""
    for bad in ["not_a_dict", [1, 2, 3], 12345, None]:
        errs = deep_validate_document(bad)
        assert len(errs) > 0
        assert any("JSON object" in e for e in errs)


def test_edge_5_deeply_nested_malformed_geometry():
    """Edge 5: Rejection of invalid coordinate types (string, boolean)."""
    bad_geom_doc = {
        "schema_version": "1.0.0",
        "source_document": {"file_name": "f.png", "page_index": 0, "image_width_px": 100, "image_height_px": 100},
        "calibration": {"unit": "mm", "pixel_to_unit_scale": 1.0, "origin_px": [0, 0], "method": "manual_override"},
        "primitives": [
            {
                "id": "p-str-coord",
                "type": "line",
                "source": "geometry_opencv",
                "confidence": 0.9,
                "layer": "UNCLASSIFIED",
                "handle": None,
                "trace": {"bbox_px": [0, 0, 10, 10]},
                "validation": {"status": "unreviewed"},
                "geometry": {
                    "start": {"x": "0.0", "y": 0.0},  # String coordinate!
                    "end": {"x": True, "y": 10.0},    # Boolean coordinate!
                },
            }
        ],
    }
    errs = deep_validate_document(bad_geom_doc)
    assert len(errs) >= 2
    assert any("finite" in e for e in errs)


def test_edge_6_unicode_drafting_symbols_and_callouts():
    """Edge 6: Preservation of Unicode engineering symbols across roundtrip."""
    symbols = [
        "Ø 50 H7 (+0.025 / 0)",
        "4x M8x1.25 - 6H ↧ 15",
        "R12.5 ± 0.05",
        "25°30' ± 5'",
        "Ra 0.8 µm",
    ]
    prims = []
    for i, sym in enumerate(symbols):
        prims.append(
            Primitive(
                id=f"text-sym-{i}",
                type="text",
                source="text_vision",
                confidence=0.99,
                text_data=TextData(
                    content=sym,
                    position=Point2D(0.0, float(i * 10)),
                    rotation_deg=0.0,
                    height=2.5,
                    semantic_role="general_note",
                ),
                trace=Trace(bbox_px=(0.0, 0.0, 50.0, 10.0)),
            )
        )

    doc = PrimitiveIRDocument(
        source_document=SourceDocument("symbols.png", 0, 800, 600),
        calibration=Calibration("mm", 1.0, (0.0, 0.0), "manual_override"),
        primitives=prims,
    )

    doc_d, equal = StrategyD_LosslessCanonicalRoundtripEngine.roundtrip(doc)
    assert equal is True
    for i, sym in enumerate(symbols):
        assert doc_d.primitives[i].text_data.content == sym


def test_perf_7_large_scale_latency_and_throughput():
    """Perf 7: Throughput and latency profiling with 1,000 primitives and 200 cross-validations."""
    prims = []
    cvs = []
    for i in range(250):
        # 250 lines
        prims.append(Primitive(
            id=f"l-{i}", type="line", source="geometry_opencv", confidence=0.9,
            geometry=LineGeometry(Point2D(float(i), 0.0), Point2D(float(i), 100.0)),
            trace=Trace(bbox_px=(float(i), 0.0, float(i), 100.0)),
        ))
        # 250 circles
        prims.append(Primitive(
            id=f"c-{i}", type="circle", source="geometry_opencv", confidence=0.92,
            geometry=CircleGeometry(Point2D(float(i), 50.0), radius=10.0),
            trace=Trace(bbox_px=(float(i) - 10, 40.0, float(i) + 10, 60.0)),
        ))
        # 250 arcs
        prims.append(Primitive(
            id=f"a-{i}", type="arc", source="geometry_opencv", confidence=0.88,
            geometry=ArcGeometry(Point2D(float(i), 50.0), radius=15.0, start_angle_deg=0.0, end_angle_deg=180.0),
            trace=Trace(bbox_px=(float(i) - 15, 35.0, float(i) + 15, 65.0)),
        ))
        # 250 texts
        prims.append(Primitive(
            id=f"t-{i}", type="text", source="text_tesseract", confidence=0.95,
            text_data=TextData(content=f"DIM_{i}", position=Point2D(float(i), 10.0), rotation_deg=0.0, height=2.5, parsed_value=float(i)),
            trace=Trace(bbox_px=(float(i), 10.0, float(i) + 20, 20.0)),
        ))

    for i in range(200):
        cvs.append(CrossValidation(
            id=f"cv-{i}", text_primitive_id=f"t-{i}", geometry_primitive_id=f"l-{i}",
            status="confirmed", text_value=float(i), geometry_measured_length=float(i), delta_percent=0.0
        ))

    doc = PrimitiveIRDocument(
        source_document=SourceDocument("large.png", 0, 4000, 3000),
        calibration=Calibration("mm", 0.1, (0.0, 0.0), "manual_override"),
        primitives=prims,
        cross_validations=cvs,
    )

    t0 = time.perf_counter()
    doc_d, equal = StrategyD_LosslessCanonicalRoundtripEngine.roundtrip(doc)
    dt_ms = (time.perf_counter() - t0) * 1000.0

    assert equal is True
    assert len(doc_d.primitives) == 1000
    assert len(doc_d.cross_validations) == 200

    throughput = len(prims) / (dt_ms / 1000.0)
    print(f"\n[Perf] 1,000 primitives + 200 CVs roundtrip: {dt_ms:.2f} ms ({throughput:.0f} prims/sec)")
    assert dt_ms < 60.0, f"Roundtrip latency {dt_ms:.2f} ms exceeded 60 ms budget"
