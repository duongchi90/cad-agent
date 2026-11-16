"""Regression tests for read-only DXF entity census and $INSUNITS gating."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import ezdxf
import pytest

from dxf_builder_lib.dxf_inventory import inspect_dxf_inventory


_REAL_DXF_ENV = "CAD_AGENT_MARINE_DXF"


def _create_mixed_dxf(path: Path, *, insunits: int) -> bytes:
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = insunits
    doc.header["$MEASUREMENT"] = 1
    doc.styles.add("MARINE_VN", font=".VnArial")
    msp = doc.modelspace()
    msp.add_line((0.0, 0.0), (100.0, 0.0), dxfattribs={"layer": "HULL"})
    msp.add_spline([(0.0, 0.0), (40.0, 15.0), (80.0, 10.0), (120.0, 0.0)], degree=3)
    msp.add_lwpolyline([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)], close=True)
    msp.add_ellipse(center=(50.0, 50.0), major_axis=(20.0, 0.0), ratio=0.5)
    msp.add_mtext("FRAME 12\\PDECK", dxfattribs={"layer": "TEXT"})
    block = doc.blocks.new("VALVE_SYM")
    block.add_circle((0.0, 0.0), radius=3.0)
    block.add_attdef("TAG", (0.0, 0.0))
    ref = msp.add_blockref("VALVE_SYM", (25.0, 25.0))
    ref.add_auto_attribs({"TAG": "V-101"})
    doc.saveas(path)
    return path.read_bytes()


def test_missing_ezdxf_raises_clear_import_error(monkeypatch, tmp_path: Path) -> None:
    dxf_path = tmp_path / "sample.dxf"
    _create_mixed_dxf(dxf_path, insunits=4)
    monkeypatch.setitem(sys.modules, "ezdxf", None)
    with pytest.raises(ImportError, match="ezdxf"):
        inspect_dxf_inventory(dxf_path)


def test_inspect_dxf_inventory_reports_full_census_and_unitless_fail_closed(tmp_path: Path) -> None:
    dxf_path = tmp_path / "unitless.dxf"
    before = _create_mixed_dxf(dxf_path, insunits=0)

    report = inspect_dxf_inventory(dxf_path)
    assert report.total_entities == 6
    assert report.five_type_entity_count == 1
    assert report.dropped_entity_count == 5
    assert report.entity_counts_by_type == {
        "ELLIPSE": 1,
        "INSERT": 1,
        "LINE": 1,
        "LWPOLYLINE": 1,
        "MTEXT": 1,
        "SPLINE": 1,
    }
    assert report.dropped_counts_by_type == {
        "ELLIPSE": 1,
        "INSERT": 1,
        "LWPOLYLINE": 1,
        "MTEXT": 1,
        "SPLINE": 1,
    }
    assert report.insunits == 0
    assert report.calibration_required is True
    assert report.unit_status == "UNITLESS_REQUIRES_CALIBRATION"
    assert report.extended_entities == ()
    assert dxf_path.read_bytes() == before


def test_inspect_dxf_inventory_metric_units_and_extended_records(tmp_path: Path) -> None:
    dxf_path = tmp_path / "metric.dxf"
    _create_mixed_dxf(dxf_path, insunits=4)

    report = inspect_dxf_inventory(dxf_path, include_extended_entities=True)
    assert report.insunits == 4
    assert report.insunits_name == "millimetres"
    assert report.calibration_required is False
    assert report.unit_status == "KNOWN_METRIC"
    by_type = {rec.dxftype: rec for rec in report.extended_entities}
    assert set(by_type) == {"SPLINE", "LWPOLYLINE", "ELLIPSE", "MTEXT", "INSERT"}
    assert by_type["SPLINE"].details["degree"] == 3
    assert by_type["LWPOLYLINE"].details["closed"] is True
    assert by_type["LWPOLYLINE"].details["vertex_count"] == 3
    assert by_type["INSERT"].details["block_name"] == "VALVE_SYM"
    assert by_type["INSERT"].details["attrib_tags"] == ("TAG",)
    assert any(style.name == "MARINE_VN" and style.font == ".VnArial" for style in report.text_styles)


def test_inspect_dxf_inventory_refuses_oversized_extended_materialization(tmp_path: Path) -> None:
    dxf_path = tmp_path / "capped.dxf"
    _create_mixed_dxf(dxf_path, insunits=4)

    census_only = inspect_dxf_inventory(dxf_path, max_entities=3, include_extended_entities=False)
    assert census_only.total_entities == 6
    with pytest.raises(ValueError, match="max_entities"):
        inspect_dxf_inventory(dxf_path, max_entities=3, include_extended_entities=True)


@pytest.mark.real_data
def test_inspect_real_marine_dxf_census_and_insunits() -> None:
    raw_path = os.environ.get(_REAL_DXF_ENV)
    if not raw_path:
        pytest.skip(f"set {_REAL_DXF_ENV} to an approved local DXF path")
    path = Path(raw_path)
    assert path.is_file()
    expected_sha = os.environ.get("CAD_AGENT_MARINE_DXF_SHA256")
    report = inspect_dxf_inventory(path)
    if expected_sha:
        assert report.source_sha256 == expected_sha
    assert report.total_entities > 0
    assert hashlib.sha256(path.read_bytes()).hexdigest() == report.source_sha256
