"""Tests for extended DXF snapshot extraction in `dxf_builder_lib._dxf_snapshot`."""

from __future__ import annotations

from pathlib import Path

import ezdxf

from dxf_builder_lib._dxf_snapshot import extract_dxf_readback_snapshot


def test_extract_dxf_readback_snapshot_preserves_insunits_xdata_text_and_dimension_fields(
    tmp_path: Path,
) -> None:
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    doc.appids.new("CAD_AGENT_TEST")
    doc.styles.add("ISOCPEUR", font="isocpeur.ttf")
    msp = doc.modelspace()
    line = msp.add_line((0.0, 0.0), (100.0, 0.0))
    line.set_xdata("CAD_AGENT_TEST", [(1000, "PART=BRACKET")])
    txt = msp.add_text(
        "NOTE-A",
        dxfattribs={
            "height": 3.5,
            "width": 0.85,
            "oblique": 12.0,
            "rotation": 90.0,
            "style": "ISOCPEUR",
            "insert": (10.0, 20.0),
        },
    )
    dim_ov = msp.add_linear_dim(base=(50.0, 15.0), p1=(0.0, 0.0), p2=(100.0, 0.0))
    dim_ov.render()
    dxf_path = tmp_path / "rich.dxf"
    doc.saveas(dxf_path)

    snap = extract_dxf_readback_snapshot(dxf_path)
    assert snap["insunits"] == 4
    assert snap["dxf_version"] == "AC1032"
    assert len(snap["lines"]) == 1
    assert snap["lines"][0]["handle"] == line.dxf.handle
    assert snap["lines"][0]["xdata"]["CAD_AGENT_TEST"] == [[1000, "PART=BRACKET"]]
    assert len(snap["texts"]) == 1
    t = snap["texts"][0]
    assert t["handle"] == txt.dxf.handle
    assert t["text"] == "NOTE-A"
    assert t["width"] == 0.85
    assert t["oblique"] == 12.0
    assert t["rotation_deg"] == 90.0
    assert t["style"] == "ISOCPEUR"
    assert t["style_font"] == "isocpeur.ttf"
    assert len(snap["dimensions"]) == 1
    d = snap["dimensions"][0]
    assert d["handle"] == dim_ov.dimension.dxf.handle
    assert d["measurement"] == 100.0
    assert d["rendered_text"] == "100"
