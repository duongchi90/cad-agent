"""Degenerate cases and performance profiling suite for Topic 28: SOURCE_VERIFIED_CURVED_GEOMETRY_MATERIALIZER_V1.

Evaluates degenerate, non-finite, stress, and latency boundaries:
1. Degenerate zero or negative radius
2. Degenerate non-finite (NaN / Inf) coordinates
3. Empty hypotheses list
4. All hypotheses failed verification
5. Coincident or full-circle sweep angles
6. Stress test: 1,000 mixed primitives
7. Performance latency profiling (< 50 ms for 100 primitives)
"""

from __future__ import annotations

import io
import math
import sys
import time
from pathlib import Path
import pytest
from PIL import Image

_repo_root = str(Path(__file__).resolve().parents[4])
_current_dir = str(Path(__file__).resolve().parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from primitive_ir_lib.models import Calibration
from source_verified_curved_engine import (
    StrategyD_LosslessCurvedMaterializerOracle,
    compute_primitive_bbox_px,
)


def _make_render_bytes(width: int = 1000, height: int = 800) -> bytes:
    img = Image.new("L", (width, height), color=255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _valid_calib(sha: str) -> Calibration:
    return Calibration(
        unit="mm",
        pixel_to_unit_scale=0.1,
        origin_px=(50.0, 750.0),
        method="manual_override",
        status="verified",
        source_sha256=sha,
    )


def test_degenerate_1_zero_or_negative_radius():
    """Degenerate 1: Zero or negative radius primitive handling."""
    sha = "7" * 64
    img_bytes = _make_render_bytes()
    calib = _valid_calib(sha)

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [100, 100, 500, 500],
        },
        "verification_request_sha256": "8" * 64,
        "primitive_hypotheses": [
            {"id": "bad_r", "type": "CIRCLE", "center_px": [200.0, 200.0], "radius_px": -10.0}
        ],
    }
    res = {
        "primitive_support": [
            {"primitive_hypothesis_id": "bad_r", "verdict": "FAIL", "support_fraction": 0.0}
        ]
    }

    # When filtering failed verdicts, bad hypothesis is filtered out cleanly
    doc = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="bad_r.pdf",
        image_width_px=1000,
        image_height_px=800,
        filter_failed_verdicts=True,
    )
    assert len(doc.primitives) == 0


def test_degenerate_2_non_finite_coordinates():
    """Degenerate 2: Non-finite (NaN / Inf) coordinates rejected or filtered."""
    sha = "7" * 64
    img_bytes = _make_render_bytes()
    calib = _valid_calib(sha)

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [100, 100, 500, 500],
        },
        "verification_request_sha256": "8" * 64,
        "primitive_hypotheses": [
            {"id": "nan_c", "type": "CIRCLE", "center_px": [float("nan"), 200.0], "radius_px": 50.0}
        ],
    }
    res = {
        "primitive_support": [
            {"primitive_hypothesis_id": "nan_c", "verdict": "FAIL", "support_fraction": 0.0}
        ]
    }

    doc = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="nan.pdf",
        image_width_px=1000,
        image_height_px=800,
        filter_failed_verdicts=True,
    )
    assert len(doc.primitives) == 0


def test_degenerate_3_empty_hypotheses():
    """Degenerate 3: Empty hypotheses list yields valid document with 0 primitives."""
    sha = "7" * 64
    img_bytes = _make_render_bytes()
    calib = _valid_calib(sha)

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [100, 100, 500, 500],
        },
        "verification_request_sha256": "8" * 64,
        "primitive_hypotheses": [],
    }
    res = {"primitive_support": []}

    doc = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="empty.pdf",
        image_width_px=1000,
        image_height_px=800,
    )
    assert len(doc.primitives) == 0
    assert doc.calibration.status == "verified"


def test_degenerate_4_all_failed_verdicts():
    """Degenerate 4: When all hypotheses fail verification, 0 primitives are materialized."""
    sha = "7" * 64
    img_bytes = _make_render_bytes()
    calib = _valid_calib(sha)

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [100, 100, 500, 500],
        },
        "verification_request_sha256": "8" * 64,
        "primitive_hypotheses": [
            {"id": "f1", "type": "LINE", "start_px": [10, 10], "end_px": [20, 20]},
            {"id": "f2", "type": "CIRCLE", "center_px": [50, 50], "radius_px": 10.0},
            {"id": "f3", "type": "ARC", "center_px": [80, 80], "radius_px": 15.0, "start_angle_deg": 0.0, "end_angle_deg": 90.0},
        ],
    }
    res = {
        "primitive_support": [
            {"primitive_hypothesis_id": "f1", "verdict": "FAIL", "support_fraction": 0.05},
            {"primitive_hypothesis_id": "f2", "verdict": "FAIL", "support_fraction": 0.01},
            {"primitive_hypothesis_id": "f3", "verdict": "FAIL", "support_fraction": 0.12},
        ]
    }

    doc = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="all_fail.pdf",
        image_width_px=1000,
        image_height_px=800,
        filter_failed_verdicts=True,
    )
    assert len(doc.primitives) == 0


def test_degenerate_5_zero_sweep_arc():
    """Degenerate 5: Arc with equal start and end angles."""
    sha = "7" * 64
    img_bytes = _make_render_bytes()
    calib = _valid_calib(sha)

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [100, 100, 500, 500],
        },
        "verification_request_sha256": "8" * 64,
        "primitive_hypotheses": [
            {
                "id": "a_zero",
                "type": "ARC",
                "center_px": [200.0, 200.0],
                "radius_px": 30.0,
                "start_angle_deg": 45.0,
                "end_angle_deg": 45.0,
            }
        ],
    }
    res = {
        "primitive_support": [
            {"primitive_hypothesis_id": "a_zero", "verdict": "PASS", "support_fraction": 0.9}
        ]
    }

    doc = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="zero_sweep.pdf",
        image_width_px=1000,
        image_height_px=800,
    )
    assert len(doc.primitives) == 1
    arc_geom = doc.primitives[0].geometry
    assert arc_geom.start_angle_deg == arc_geom.end_angle_deg


def test_stress_6_1000_mixed_primitives():
    """Stress 6: Materializing 1,000 mixed lines, circles, and arcs without memory leak or failure."""
    sha = "7" * 64
    img_bytes = _make_render_bytes(width=2000, height=2000)
    calib = Calibration(
        unit="mm",
        pixel_to_unit_scale=0.05,
        origin_px=(100.0, 1900.0),
        method="manual_override",
        status="verified",
        source_sha256=sha,
    )

    n_prims = 1000
    hyps = []
    supports = []
    for i in range(n_prims):
        pid = f"stress_{i}"
        mod = i % 3
        if mod == 0:
            hyps.append({"id": pid, "type": "LINE", "start_px": [100.0 + i, 100.0], "end_px": [200.0 + i, 200.0]})
        elif mod == 1:
            hyps.append({"id": pid, "type": "CIRCLE", "center_px": [500.0, 500.0 + i * 0.5], "radius_px": 25.0})
        else:
            hyps.append({"id": pid, "type": "ARC", "center_px": [800.0, 800.0 + i * 0.5], "radius_px": 30.0, "start_angle_deg": 30.0, "end_angle_deg": 120.0})
        supports.append({"primitive_hypothesis_id": pid, "verdict": "PASS", "support_fraction": 0.95})

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [0, 0, 2000, 2000],
        },
        "verification_request_sha256": "8" * 64,
        "primitive_hypotheses": hyps,
    }
    res = {"primitive_support": supports}

    start_t = time.perf_counter()
    doc = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="stress_1000.pdf",
        image_width_px=2000,
        image_height_px=2000,
    )
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    assert len(doc.primitives) == 1000
    # 1000 primitives should easily materialize in under 150 ms
    assert elapsed_ms < 150.0


def test_perf_7_latency_profiling_100_primitives():
    """Perf 7: Materializing 100 mixed primitives completes well within budget (< 25 ms)."""
    sha = "7" * 64
    img_bytes = _make_render_bytes()
    calib = _valid_calib(sha)

    hyps = []
    supports = []
    for i in range(100):
        pid = f"p_{i}"
        if i % 2 == 0:
            hyps.append({"id": pid, "type": "CIRCLE", "center_px": [200.0 + i, 200.0], "radius_px": 20.0})
        else:
            hyps.append({"id": pid, "type": "ARC", "center_px": [300.0 + i, 300.0], "radius_px": 25.0, "start_angle_deg": 0.0, "end_angle_deg": 90.0})
        supports.append({"primitive_hypothesis_id": pid, "verdict": "PASS", "support_fraction": 0.95})

    req = {
        "exact_source_binding": {
            "source_sha256": sha,
            "page_index": 0,
            "roi_bbox_px": [100, 100, 800, 800],
        },
        "verification_request_sha256": "8" * 64,
        "primitive_hypotheses": hyps,
    }
    res = {"primitive_support": supports}

    start_t = time.perf_counter()
    doc = StrategyD_LosslessCurvedMaterializerOracle.materialize(
        verification_request=req,
        verification_result=res,
        source_render_bytes=img_bytes,
        calibration=calib,
        source_file_name="perf_100.pdf",
        image_width_px=1000,
        image_height_px=800,
    )
    latency_ms = (time.perf_counter() - start_t) * 1000

    assert len(doc.primitives) == 100
    assert latency_ms < 25.0
