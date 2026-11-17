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


def _build_seed(
    tmp_path: Path, length_mm: float = 100.0, approved: float | None = None,
    *, explicit_height: bool = True,
):
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
    built = build_dxf(
        _clean_doc(length_mm),
        str(tmp_path / "candidate.dxf"),
        build_dimensions=True,
        dimension_specs=specs,
        capture_dimension_line_integrity=True,
    )
    if explicit_height:
        # Positive controls declare the intended rendered size, rather than
        # relying on the known implicit-style save/reopen discrepancy.
        doc = ezdxf.readfile(built.output_path)
        dim = doc.entitydb[built.dimension_handle_by_cross_validation_id["cv-1"]]
        override = DimStyleOverride(dim)
        override["dimtxt"] = 1.0
        override.commit()
        doc.saveas(built.output_path)
    return built


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


def _set_rendered_block_text(dim, label: str) -> None:
    for item in dim.get_geometry_block():
        if item.dxftype() == "MTEXT":
            item.text = label
        elif item.dxftype() == "TEXT":
            item.dxf.text = label


@pytest.mark.parametrize(
    "variant,override_text,style_patch,rendered_text,want_pass",
    [
        ("positive_unit_label", "<> mm", None, "100 mm", True),
        ("positive_count_label", "4x <>", None, "4x 100", True),
        ("positive_dimpost_label", None, {"dimpost": "<> mm"}, "100 mm", True),
        ("leading_decimal_lie", ".100", None, ".100", False),
        ("scientific_lie", "100e-1", None, "100e-1", False),
        ("multi_number_ambiguous", "100 / 200", None, "100 / 200", False),
        ("multi_dot_malformed", "1.2.3", None, "1.2.3", False),
        ("multi_dot_100_prefix", "100.0.5", None, "100.0.5", False),
        ("placeholder_suffix_zero", "<>0", None, "1000", False),
        ("placeholder_prefix_nine", "9<>", None, "9100", False),
        ("placeholder_dot_prefix", ".<>", None, ".100", False),
        ("placeholder_double", "<> <>", None, "100 <>", False),
        ("dimpost_suffix_zero", None, {"dimpost": "<>0"}, "1000", False),
        ("dimpost_prefix_nine", None, {"dimpost": "9<>"}, "9100", False),
        ("dimpost_no_placeholder_zero", None, {"dimpost": "0", "dimzin": 0}, "100.000", False),
    ],
)
def test_truth_audit_rejects_leading_decimal_placeholder_and_dimpost_numeric_mutations(
    tmp_path: Path,
    variant: str,
    override_text: str | None,
    style_patch: dict[str, object] | None,
    rendered_text: str,
    want_pass: bool,
) -> None:
    built = _build_seed(tmp_path / variant)
    doc = ezdxf.readfile(built.output_path)
    dim = doc.entitydb[built.dimension_handle_by_cross_validation_id["cv-1"]]
    if override_text is not None:
        dim.dxf.text = override_text
    if style_patch:
        ov = DimStyleOverride(dim)
        for key, value in style_patch.items():
            ov[key] = value
        ov.commit()
    _set_rendered_block_text(dim, rendered_text)
    doc.saveas(built.output_path)

    strict = review_dxf_with_dimension_line_integrity(built)
    semantic = review_dxf(built, verify_dimension_truth=True)
    assert strict.passed is want_pass
    assert semantic.passed is want_pass
    assert strict.qualification == ("QUALIFIED" if want_pass else "FAILED")


def test_truth_audit_validates_dimtol_with_ezdxf_tolerance_owner(tmp_path: Path) -> None:
    from ezdxf.render.dim_base import Tolerance

    # Positive symmetric tolerance rendered by ezdxf passes.
    built_sym = _build_seed(tmp_path / "tol_sym")
    doc_sym = ezdxf.readfile(built_sym.output_path)
    dim_sym = doc_sym.entitydb[built_sym.dimension_handle_by_cross_validation_id["cv-1"]]
    ov_sym = DimStyleOverride(dim_sym)
    for k, v in {"dimtol": 1, "dimtp": 0.1, "dimtm": 0.1, "dimdsep": ord("."), "dimtdec": 2, "dimtzin": 8}.items():
        ov_sym[k] = v
    ov_sym.commit()
    _set_rendered_block_text(dim_sym, Tolerance(DimStyleOverride(dim_sym)).compile_mtext("100"))
    doc_sym.saveas(built_sym.output_path)
    assert review_dxf_with_dimension_line_integrity(built_sym).qualification == "QUALIFIED"

    # Positive asymmetric tolerance rendered by ezdxf passes.
    built_asym = _build_seed(tmp_path / "tol_asym")
    doc_asym = ezdxf.readfile(built_asym.output_path)
    dim_asym = doc_asym.entitydb[built_asym.dimension_handle_by_cross_validation_id["cv-1"]]
    ov_asym = DimStyleOverride(dim_asym)
    for k, v in {"dimtol": 1, "dimtp": 0.2, "dimtm": 0.1, "dimdsep": ord("."), "dimtdec": 2, "dimtzin": 8}.items():
        ov_asym[k] = v
    ov_asym.commit()
    _set_rendered_block_text(dim_asym, Tolerance(DimStyleOverride(dim_asym)).compile_mtext("100"))
    doc_asym.saveas(built_asym.output_path)
    assert review_dxf_with_dimension_line_integrity(built_asym).qualification == "QUALIFIED"

    # Stale tolerance values, exponent notation, and unconfigured tolerance suffixes must fail closed.
    for variant, tol_vals, bad_text in [
        ("stale_tol", {"dimtol": 1}, "100 +99/-99"),
        ("exponent_tol", {"dimtol": 1}, "100e-1"),
        ("wrong_configured_tol", {"dimtol": 1, "dimtp": 0.1, "dimtm": 0.1}, r"100\P+999/-999"),
        ("unit_like_tol_mismatch", {"dimtol": 1, "dimtp": 0.1, "dimtm": 0.1}, "100±0.50"),
    ]:
        built_bad = _build_seed(tmp_path / variant)
        doc_bad = ezdxf.readfile(built_bad.output_path)
        dim_bad = doc_bad.entitydb[built_bad.dimension_handle_by_cross_validation_id["cv-1"]]
        ov_bad = DimStyleOverride(dim_bad)
        for k, v in tol_vals.items():
            ov_bad[k] = v
        ov_bad.commit()
        _set_rendered_block_text(dim_bad, bad_text)
        doc_bad.saveas(built_bad.output_path)
        strict_bad = review_dxf_with_dimension_line_integrity(built_bad)
        assert strict_bad.qualification == "FAILED"
        assert not strict_bad.passed


def test_truth_audit_rejects_tiny_height_inline_height_and_transparent_text(tmp_path: Path) -> None:
    # Tiny entity char_height must fail closed.
    built_tiny = _build_seed(tmp_path / "tiny_char")
    doc_tiny = ezdxf.readfile(built_tiny.output_path)
    dim_tiny = doc_tiny.entitydb[built_tiny.dimension_handle_by_cross_validation_id["cv-1"]]
    for item in dim_tiny.get_geometry_block():
        if item.dxftype() == "MTEXT":
            item.dxf.char_height = 1e-9
    doc_tiny.saveas(built_tiny.output_path)
    res_tiny = review_dxf_with_dimension_line_integrity(built_tiny)
    assert res_tiny.qualification == "FAILED"
    assert not res_tiny.passed

    # Tiny inline MTEXT height (\H...x; or absolute \H...;) must fail closed.
    for tag, mtext_val in [("inline_rel", r"{\H0.000000001x;100}"), ("inline_abs", r"\H1e-9;100")]:
        built_in = _build_seed(tmp_path / tag)
        doc_in = ezdxf.readfile(built_in.output_path)
        dim_in = doc_in.entitydb[built_in.dimension_handle_by_cross_validation_id["cv-1"]]
        _set_rendered_block_text(dim_in, mtext_val)
        doc_in.saveas(built_in.output_path)
        res_in = review_dxf_with_dimension_line_integrity(built_in)
        assert res_in.qualification == "FAILED"
        assert not res_in.passed

    # Fully transparent MTEXT or parent DIMENSION transparency must fail closed.
    built_tr = _build_seed(tmp_path / "transparent")
    doc_tr = ezdxf.readfile(built_tr.output_path)
    dim_tr = doc_tr.entitydb[built_tr.dimension_handle_by_cross_validation_id["cv-1"]]
    for item in dim_tr.get_geometry_block():
        if item.dxftype() == "MTEXT":
            item.transparency = 1.0
    doc_tr.saveas(built_tr.output_path)
    res_tr = review_dxf_with_dimension_line_integrity(built_tr)
    assert res_tr.qualification == "FAILED"
    assert not res_tr.passed

    built_dim_tr = _build_seed(tmp_path / "dim_transparent")
    doc_dim_tr = ezdxf.readfile(built_dim_tr.output_path)
    dim_ent_tr = doc_dim_tr.entitydb[built_dim_tr.dimension_handle_by_cross_validation_id["cv-1"]]
    dim_ent_tr.transparency = 1.0
    doc_dim_tr.saveas(built_dim_tr.output_path)
    res_dim_tr = review_dxf_with_dimension_line_integrity(built_dim_tr)
    assert res_dim_tr.qualification == "FAILED"
    assert not res_dim_tr.passed

    # Positive control with explicit DIMTXT/DIMSCALE scaling must pass cleanly when height matches style.
    built_scaled = _build_seed(tmp_path / "scaled_dimtxt")
    doc_scaled = ezdxf.readfile(built_scaled.output_path)
    dim_scaled = doc_scaled.entitydb[built_scaled.dimension_handle_by_cross_validation_id["cv-1"]]
    ov_sc = DimStyleOverride(dim_scaled)
    ov_sc["dimtxt"] = 3.5
    ov_sc["dimscale"] = 2.0
    ov_sc.commit()
    for item in dim_scaled.get_geometry_block():
        if item.dxftype() == "MTEXT":
            item.dxf.char_height = 7.0
    doc_scaled.saveas(built_scaled.output_path)
    assert review_dxf_with_dimension_line_integrity(built_scaled).qualification == "QUALIFIED"


def test_dimension_truth_preserves_complete_mit_license_notice_and_provenance() -> None:
    src = (Path(__file__).resolve().parents[1] / "_dimension_truth.py").read_text(encoding="utf-8")
    assert "6f6a538255ca9f885232e845ac32f10b4433fe3e" in src
    assert "Copyright (c) 2026 Umutcan Edizsalan" in src
    assert "Permission is hereby granted, free of charge" in src
    assert 'WITHOUT WARRANTY OF ANY KIND, EXPRESS OR' in src


def test_truth_audit_accepts_valid_leading_decimal_and_rejects_tiny_tolerance_subtoken(tmp_path: Path) -> None:
    # Legitimate leading decimal (0.1 mm with dimzin=4 -> ".100", dimzin=12 -> ".1") must qualify.
    for zin, expected_label in ((4, ".100"), (12, ".1")):
        built_ld = _build_seed(tmp_path / f"valid_ld_{zin}", length_mm=0.1)
        doc_ld = ezdxf.readfile(built_ld.output_path)
        dim_ld = doc_ld.entitydb[built_ld.dimension_handle_by_cross_validation_id["cv-1"]]
        ov_ld = DimStyleOverride(dim_ld)
        ov_ld["dimzin"] = zin
        ov_ld["dimdec"] = 3
        ov_ld["dimdsep"] = ord(".")
        ov_ld.commit()
        _set_rendered_block_text(dim_ld, expected_label)
        doc_ld.saveas(built_ld.output_path)
        assert review_dxf_with_dimension_line_integrity(built_ld).qualification == "QUALIFIED"

    # Tiny inline tolerance sub-token (\H1e-9x;) must fail closed.
    built_tinytol = _build_seed(tmp_path / "tiny_tol_sub")
    doc_tt = ezdxf.readfile(built_tinytol.output_path)
    dim_tt = doc_tt.entitydb[built_tinytol.dimension_handle_by_cross_validation_id["cv-1"]]
    ov_tt = DimStyleOverride(dim_tt)
    for k, v in {"dimtol": 1, "dimtp": 0.1, "dimtm": 0.1, "dimdsep": ord("."), "dimtdec": 2, "dimtzin": 8}.items():
        ov_tt[k] = v
    ov_tt.commit()
    _set_rendered_block_text(dim_tt, r"\A0;100{\H1e-9x;±0.10}")
    doc_tt.saveas(built_tinytol.output_path)
    assert review_dxf_with_dimension_line_integrity(built_tinytol).qualification == "FAILED"

    # Negative dimscale must fail closed.
    built_negscale = _build_seed(tmp_path / "neg_scale")
    doc_ns = ezdxf.readfile(built_negscale.output_path)
    dim_ns = doc_ns.entitydb[built_negscale.dimension_handle_by_cross_validation_id["cv-1"]]
    ov_ns = DimStyleOverride(dim_ns)
    ov_ns["dimscale"] = -1.0
    ov_ns.commit()
    doc_ns.saveas(built_negscale.output_path)
    assert review_dxf_with_dimension_line_integrity(built_negscale).qualification == "FAILED"


def _explicit_truth_control(tmp_path: Path, **style_values):
    """Keep the real builder geometry, with an explicit source for rendered size."""
    built = _build_seed(tmp_path)
    doc = ezdxf.readfile(built.output_path)
    dim = doc.entitydb[built.dimension_handle_by_cross_validation_id["cv-1"]]
    override = DimStyleOverride(dim)
    values = {"dimtxt": 1.0, "dimscale": 1.0, "dimdsep": ord(".")}
    values.update(style_values)
    for key, value in values.items():
        override[key] = value
    override.commit()
    return built, doc, dim


def test_role_escape_primary_word_cannot_borrow_tolerance_height(tmp_path: Path) -> None:
    # The nominal 100 must retain DIMTXT=1 even when tolerance text uses 0.1.
    built, doc, dim = _explicit_truth_control(
        tmp_path, dimtol=1, dimtp=0.1, dimtm=0.1,
        dimtfac=0.1, dimtdec=2, dimtzin=0,
    )
    _set_rendered_block_text(dim, r"{\H0.1x;100}{\H0.1x;±0.10}")
    doc.saveas(built.output_path)
    result = review_dxf_with_dimension_line_integrity(built)
    assert not result.passed
    assert result.qualification == "FAILED"


@pytest.mark.parametrize("active", [False, True])
def test_small_dimtfac_uses_active_role_instead_of_readability_cutoff(tmp_path: Path, active: bool) -> None:
    built, doc, dim = _explicit_truth_control(
        tmp_path, dimtol=int(active), dimtp=0.1, dimtm=0.1,
        dimtfac=0.05, dimtdec=2, dimtzin=0,
    )
    # A supported tolerance follows the actual style; inactive DIMTFAC is irrelevant.
    _set_rendered_block_text(dim, r"100{\H0.05x;±0.10}" if active else "100")
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "QUALIFIED"


def test_implicit_height_persistence_discrepancy_is_unknown(tmp_path: Path) -> None:
    built = _build_seed(tmp_path, explicit_height=False)
    doc = ezdxf.readfile(built.output_path)
    dim = doc.entitydb[built.dimension_handle_by_cross_validation_id["cv-1"]]
    style = DimStyleOverride(dim)
    text = next(e for e in dim.get_geometry_block() if e.dxftype() == "MTEXT")
    assert style.get("dimtxt") == 2.5
    assert text.dxf.char_height == 1.0
    # This mismatch supplies no historical render authority from the style's name.
    result = review_dxf_with_dimension_line_integrity(built)
    assert not result.passed
    assert result.qualification == "UNKNOWN"
    assert any("unverified" in reason for reason in result.semantic_review.dimension_mismatches)


@pytest.mark.parametrize("fixed_text_style", [False, True])
def test_explicit_style_height_and_dimscale_control(tmp_path: Path, fixed_text_style: bool) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path, dimtxt=2.5, dimscale=3.0)
    height = 7.5
    if fixed_text_style:
        doc.styles.new("SOURCE_FIXED_HEIGHT", dxfattribs={"height": 2.0})
        override = DimStyleOverride(dim)
        override["dimtxsty"] = "SOURCE_FIXED_HEIGHT"
        override.commit()
        height = 6.0
    for text in dim.get_geometry_block():
        if text.dxftype() == "MTEXT":
            text.dxf.char_height = height
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "QUALIFIED"


@pytest.mark.parametrize("scope", ["entity", "layer", "byblock"])
@pytest.mark.parametrize("transparency", [0.25, 1.0])
def test_supported_transparency_distinguishes_partial_from_suppression(
    tmp_path: Path, scope: str, transparency: float,
) -> None:
    from ezdxf.lldxf.const import TRANSPARENCY_BYBLOCK

    built, doc, dim = _explicit_truth_control(tmp_path)
    text = next(e for e in dim.get_geometry_block() if e.dxftype() == "MTEXT")
    if scope == "entity":
        text.transparency = transparency
    elif scope == "layer":
        layer = doc.layers.new("SOURCE_LABELS")
        layer.transparency = transparency
        text.dxf.layer = layer.dxf.name
    else:
        dim.transparency = transparency
        text.dxf.transparency = TRANSPARENCY_BYBLOCK
    doc.saveas(built.output_path)
    before = Path(built.output_path).read_bytes()
    result = review_dxf_with_dimension_line_integrity(built)
    assert Path(built.output_path).read_bytes() == before
    assert result.qualification == ("QUALIFIED" if transparency == 0.25 else "FAILED")
