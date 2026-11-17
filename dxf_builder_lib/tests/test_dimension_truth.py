"""Dimension-truth regression tests for `dxf_builder_lib.reviewer`."""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf
import pytest
from ezdxf.entities import DimStyleOverride

from dxf_builder_lib.builder import NativeLinearDimensionSpec, build_dxf
from dxf_builder_lib.reviewer import (
    review_dxf,
    review_dxf_with_dimension_line_integrity,
)
from primitive_ir_lib.models import (
    Calibration,
    CrossValidation,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
)


def _clean_doc(length_mm: float = 100.0) -> PrimitiveIRDocument:
    line = Primitive(
        id="line-1",
        type="line",
        source="geometry_pdfvector",
        confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 100, 10)),
        geometry=LineGeometry(start=Point2D(0.0, 0.0), end=Point2D(length_mm, 0.0)),
    )
    return PrimitiveIRDocument(
        source_document=SourceDocument("synthetic.png", 0, 200, 100),
        calibration=Calibration("mm", 1.0, (0, 0), "manual_override"),
        primitives=[line],
        cross_validations=[
            CrossValidation(
                id="cv-1",
                text_primitive_id="t-1",
                geometry_primitive_id="line-1",
                status="confirmed",
                text_value=length_mm,
                geometry_measured_length=length_mm,
                delta_percent=0.0,
            )
        ],
    )


def _build_seed(tmp_path: Path, length_mm: float = 100.0, approved: float | None = None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    specs = None
    if approved is not None:
        specs = [
            NativeLinearDimensionSpec(
                id="cv-1",
                geometry_primitive_id="line-1",
                approved_value_mm=approved,
                source_ref="t-1",
            )
        ]
    return build_dxf(
        _clean_doc(length_mm),
        str(tmp_path / "candidate.dxf"),
        build_dimensions=True,
        dimension_specs=specs,
        capture_dimension_line_integrity=True,
    )


def test_integrity_review_rejects_override_lie_stale_block_dimlfac_and_hidden_dim(tmp_path: Path) -> None:
    # V1: text override lies about measured 100 mm geometry
    built_v1 = _build_seed(tmp_path / "v1")
    doc_v1 = ezdxf.readfile(built_v1.output_path)
    dim_v1 = doc_v1.entitydb[built_v1.dimension_handle_by_cross_validation_id["cv-1"]]
    dim_v1.dxf.text = "99.50"
    doc_v1.saveas(built_v1.output_path)
    res_v1 = review_dxf_with_dimension_line_integrity(built_v1)
    assert res_v1.qualification == "FAILED"
    assert not res_v1.passed

    # V2: stale *D rendered text + stale DXF group 42
    built_v2 = _build_seed(tmp_path / "v2")
    doc_v2 = ezdxf.readfile(built_v2.output_path)
    dim_v2 = doc_v2.entitydb[built_v2.dimension_handle_by_cross_validation_id["cv-1"]]
    dim_v2.dxf.actual_measurement = 88.0
    for entity in dim_v2.get_geometry_block():
        if entity.dxftype() == "MTEXT":
            entity.text = r"{\H0.7x;88.00}"
        elif entity.dxftype() == "TEXT":
            entity.dxf.text = "88.00"
    doc_v2.saveas(built_v2.output_path)
    res_v2 = review_dxf_with_dimension_line_integrity(built_v2)
    assert res_v2.qualification == "FAILED"
    assert not res_v2.passed

    # V3: DIMLFAC != 1 without re-rendering block
    built_v3 = _build_seed(tmp_path / "v3")
    doc_v3 = ezdxf.readfile(built_v3.output_path)
    dim_v3 = doc_v3.entitydb[built_v3.dimension_handle_by_cross_validation_id["cv-1"]]
    ov3 = DimStyleOverride(dim_v3)
    ov3["dimlfac"] = 2.0
    ov3.commit()
    doc_v3.saveas(built_v3.output_path)
    res_v3 = review_dxf_with_dimension_line_integrity(built_v3)
    assert res_v3.qualification == "FAILED"
    assert not res_v3.passed

    # V4: layer off + no-plot + dimtxt=0
    built_v4 = _build_seed(tmp_path / "v4")
    doc_v4 = ezdxf.readfile(built_v4.output_path)
    doc_v4.layers.get("DIMENSIONS").off()
    doc_v4.layers.get("DIMENSIONS").dxf.plot = 0
    dim_v4 = doc_v4.entitydb[built_v4.dimension_handle_by_cross_validation_id["cv-1"]]
    ov4 = DimStyleOverride(dim_v4)
    ov4["dimtxt"] = 0.0
    ov4.commit()
    doc_v4.saveas(built_v4.output_path)
    res_v4 = review_dxf_with_dimension_line_integrity(built_v4)
    assert res_v4.qualification == "FAILED"
    assert not res_v4.passed


@pytest.mark.parametrize(
    "override_text,length_mm,want_pass",
    [
        ("", 100.0, True),
        ("<>", 100.0, True),
        ("<> mm", 100.0, True),
        (r"4x %%c100.0", 100.0, True),
        ("57,50", 57.5, True),
        (" ", 100.0, False),
        ("99.50", 100.0, False),
        ("4x 99.50", 100.0, False),
    ],
)
def test_opt_in_dimension_truth_validates_overrides_and_labels(
    tmp_path: Path, override_text: str, length_mm: float, want_pass: bool,
) -> None:
    built = _build_seed(tmp_path, length_mm=length_mm)
    doc = ezdxf.readfile(built.output_path)
    dim = doc.entitydb[built.dimension_handle_by_cross_validation_id["cv-1"]]
    if override_text:
        dim.dxf.text = override_text
        ov = DimStyleOverride(dim)
        ov.render()
    doc.saveas(built.output_path)
    before = Path(built.output_path).read_bytes()

    result = review_dxf(built, verify_dimension_truth=True)
    assert result.passed is want_pass
    assert bool(result.dimension_mismatches) is (not want_pass)
    assert Path(built.output_path).read_bytes() == before


def test_dimension_truth_allows_autocad_sentinel_group42_negative_one_and_rejects_bad_dimlfac(
    tmp_path: Path,
) -> None:
    # AutoCAD _SAVEAS without DIMREGEN can store group 42 = -1.0 while keeping valid *D block text.
    built_ok = _build_seed(tmp_path / "g42")
    doc_ok = ezdxf.readfile(built_ok.output_path)
    dim_ok = doc_ok.entitydb[built_ok.dimension_handle_by_cross_validation_id["cv-1"]]
    dim_ok.dxf.actual_measurement = -1.0
    doc_ok.saveas(built_ok.output_path)
    assert review_dxf(built_ok, verify_dimension_truth=True).passed

    # Non-finite dimlfac fails closed.
    built_nan = _build_seed(tmp_path / "nanfac")
    doc_nan = ezdxf.readfile(built_nan.output_path)
    dim_nan = doc_nan.entitydb[built_nan.dimension_handle_by_cross_validation_id["cv-1"]]
    ov = DimStyleOverride(dim_nan)
    ov["dimlfac"] = math.nan
    ov.commit()
    doc_nan.saveas(built_nan.output_path)
    res_nan = review_dxf(built_nan, verify_dimension_truth=True)
    assert not res_nan.passed
    assert any("dimlfac" in msg.lower() for msg in res_nan.dimension_mismatches)


def test_verify_dimension_truth_flag_rejects_non_bool_before_file_read(tmp_path: Path) -> None:
    missing = tmp_path / "missing.dxf"
    built = build_dxf(
        PrimitiveIRDocument(
            SourceDocument("s.png", 0, 10, 10),
            Calibration("mm", 1.0, (0, 0), "manual_override"),
            [],
        ),
        str(tmp_path / "empty.dxf"),
    )
    built.output_path = str(missing)
    with pytest.raises(ValueError, match="verify_dimension_truth"):
        review_dxf(built, verify_dimension_truth="yes")  # type: ignore[arg-type]
    assert not missing.exists()


def test_truth_audit_rejects_blank_missing_and_unreadable_rendered_values(tmp_path: Path) -> None:
    # Blank rendered text in *D anonymous block must fail closed.
    built_blank = _build_seed(tmp_path / "blank")
    doc_blank = ezdxf.readfile(built_blank.output_path)
    dim_blank = doc_blank.entitydb[built_blank.dimension_handle_by_cross_validation_id["cv-1"]]
    for item in list(dim_blank.get_geometry_block()):
        if item.dxftype() == "MTEXT":
            item.text = " "
        elif item.dxftype() == "TEXT":
            item.dxf.text = " "
    doc_blank.saveas(built_blank.output_path)
    res_blank = review_dxf_with_dimension_line_integrity(built_blank)
    assert res_blank.qualification == "FAILED"
    assert not res_blank.passed
    assert any("dim_render_missing" in msg for msg in res_blank.semantic_review.dimension_mismatches)

    # Deleted TEXT/MTEXT entities in *D anonymous block must fail closed.
    built_missing = _build_seed(tmp_path / "missing")
    doc_missing = ezdxf.readfile(built_missing.output_path)
    dim_missing = doc_missing.entitydb[built_missing.dimension_handle_by_cross_validation_id["cv-1"]]
    block_missing = dim_missing.get_geometry_block()
    for item in list(block_missing):
        if item.dxftype() in {"TEXT", "MTEXT"}:
            block_missing.delete_entity(item)
    doc_missing.saveas(built_missing.output_path)
    res_missing = review_dxf_with_dimension_line_integrity(built_missing)
    assert res_missing.qualification == "FAILED"
    assert not res_missing.passed
    assert any("dim_render_missing" in msg for msg in res_missing.semantic_review.dimension_mismatches)

    # Unreadable display modes (e.g. dimalt=1) fail closed when required rendered truth cannot be verified.
    built_alt = _build_seed(tmp_path / "dimalt")
    doc_alt = ezdxf.readfile(built_alt.output_path)
    dim_alt = doc_alt.entitydb[built_alt.dimension_handle_by_cross_validation_id["cv-1"]]
    ov_alt = DimStyleOverride(dim_alt)
    ov_alt["dimalt"] = 1
    ov_alt.commit()
    doc_alt.saveas(built_alt.output_path)
    res_alt = review_dxf(built_alt, verify_dimension_truth=True)
    assert not res_alt.passed
    assert any("unreadable" in msg.lower() for msg in res_alt.dimension_mismatches)

    # Explicit suppressed semantics (" ") keep dim_value_suppressed cleanly without misreporting missing render.
    built_sup = _build_seed(tmp_path / "suppressed")
    doc_sup = ezdxf.readfile(built_sup.output_path)
    dim_sup = doc_sup.entitydb[built_sup.dimension_handle_by_cross_validation_id["cv-1"]]
    dim_sup.dxf.text = " "
    for item in list(dim_sup.get_geometry_block()):
        if item.dxftype() in {"TEXT", "MTEXT"}:
            dim_sup.get_geometry_block().delete_entity(item)
    doc_sup.saveas(built_sup.output_path)
    res_sup = review_dxf(built_sup, verify_dimension_truth=True)
    assert not res_sup.passed
    assert any("dim_value_suppressed" in msg for msg in res_sup.dimension_mismatches)
    assert not any("dim_render_missing" in msg for msg in res_sup.dimension_mismatches)


def test_truth_audit_rejects_invisible_dimension_and_hidden_rendered_text(tmp_path: Path) -> None:
    # Hidden DIMENSION entity (DXF group 60 invisible=1) must fail strict review.
    built_dim = _build_seed(tmp_path / "inv_dim")
    doc_dim = ezdxf.readfile(built_dim.output_path)
    dim_ent = doc_dim.entitydb[built_dim.dimension_handle_by_cross_validation_id["cv-1"]]
    dim_ent.dxf.invisible = 1
    doc_dim.saveas(built_dim.output_path)
    res_dim = review_dxf_with_dimension_line_integrity(built_dim)
    assert res_dim.qualification == "FAILED"
    assert not res_dim.passed
    assert any("dim_entity_invisible" in msg for msg in res_dim.semantic_review.dimension_mismatches)

    # Hidden MTEXT/TEXT inside *D anonymous block must fail strict review even when DIMENSION is visible.
    built_mtext = _build_seed(tmp_path / "inv_mtext")
    doc_mtext = ezdxf.readfile(built_mtext.output_path)
    dim_mtext = doc_mtext.entitydb[built_mtext.dimension_handle_by_cross_validation_id["cv-1"]]
    for item in dim_mtext.get_geometry_block():
        if item.dxftype() in {"TEXT", "MTEXT"}:
            item.dxf.invisible = 1
    doc_mtext.saveas(built_mtext.output_path)
    res_mtext = review_dxf_with_dimension_line_integrity(built_mtext)
    assert res_mtext.qualification == "FAILED"
    assert not res_mtext.passed
    assert any("dim_rendered_text_hidden" in msg for msg in res_mtext.semantic_review.dimension_mismatches)

    # Rendered MTEXT/TEXT inside *D placed on a hidden/noplot layer must also fail closed.
    built_layer = _build_seed(tmp_path / "hidden_text_layer")
    doc_layer = ezdxf.readfile(built_layer.output_path)
    hidden_layer = doc_layer.layers.new("HIDDEN_DIM_TEXT")
    hidden_layer.off()
    dim_layer = doc_layer.entitydb[built_layer.dimension_handle_by_cross_validation_id["cv-1"]]
    for item in dim_layer.get_geometry_block():
        if item.dxftype() in {"TEXT", "MTEXT"}:
            item.dxf.layer = "HIDDEN_DIM_TEXT"
    doc_layer.saveas(built_layer.output_path)
    res_layer = review_dxf_with_dimension_line_integrity(built_layer)
    assert res_layer.qualification == "FAILED"
    assert not res_layer.passed
    assert any("dim_rendered_text_hidden" in msg for msg in res_layer.semantic_review.dimension_mismatches)
