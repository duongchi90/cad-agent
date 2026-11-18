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


@pytest.mark.parametrize("text", [r"{\W0;100}", r"{\W0;1}00"])
def test_zero_width_primary_digits_cannot_qualify(tmp_path: Path, text: str) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    _set_rendered_block_text(dim, text)
    doc.saveas(built.output_path)
    before = Path(built.output_path).read_bytes()
    result = review_dxf_with_dimension_line_integrity(built)
    assert Path(built.output_path).read_bytes() == before
    assert result.qualification == "FAILED"
    assert not result.passed


def test_supported_nonzero_width_is_not_a_readability_threshold(tmp_path: Path) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    _set_rendered_block_text(dim, r"{\W0.5;100}")
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "QUALIFIED"


@pytest.mark.parametrize("label", ["- 100", "−100", "－100", "− 100 mm", "4x Ø−100", "100 −", "unknown −100"])
def test_complete_signed_claim_cannot_be_reduced_to_positive_substring(tmp_path: Path, label: str) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    dim.dxf.text = label
    _set_rendered_block_text(dim, label)
    doc.saveas(built.output_path)
    before = Path(built.output_path).read_bytes()
    result = review_dxf_with_dimension_line_integrity(built)
    assert Path(built.output_path).read_bytes() == before
    assert result.qualification == "FAILED"


@pytest.mark.parametrize("label", ["+ 100", "＋100", "4x Ø+100 mm", "4x M100"])
def test_explicit_positive_signed_claim_remains_supported(tmp_path: Path, label: str) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    dim.dxf.text = label
    _set_rendered_block_text(dim, label)
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "QUALIFIED"


@pytest.mark.parametrize("text", [r"{\H0x;100}", r"{\H0x;1}00", r"{\H0;100}"])
def test_known_zero_height_is_suppression_not_unverified(tmp_path: Path, text: str) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    _set_rendered_block_text(dim, text)
    doc.saveas(built.output_path)
    result = review_dxf_with_dimension_line_integrity(built)
    assert result.qualification == "FAILED"


@pytest.mark.parametrize("label", ["100 cm", "100 in", "100m", "100 mm"])
def test_explicit_unit_claim_cannot_hide_physical_disagreement(tmp_path: Path, label: str) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    assert doc.units == 4  # The existing builder declares native millimetres.
    dim.dxf.text = label
    _set_rendered_block_text(dim, label)
    doc.saveas(built.output_path)
    before = Path(built.output_path).read_bytes()
    result = review_dxf_with_dimension_line_integrity(built)
    assert Path(built.output_path).read_bytes() == before
    assert result.qualification == ("QUALIFIED" if label == "100 mm" else "FAILED")


@pytest.mark.parametrize("length,label", [(100.0, "10 cm"), (25.4, "1 in"), (100.0, "100 REF"), (100.0, "100 mm TYP")])
def test_known_unit_conversion_and_literal_qualifiers_are_supported(tmp_path: Path, length: float, label: str) -> None:
    built = _build_seed(tmp_path, length_mm=length)
    doc = ezdxf.readfile(built.output_path)
    dim = doc.entitydb[built.dimension_handle_by_cross_validation_id["cv-1"]]
    dim.dxf.text = label
    _set_rendered_block_text(dim, label)
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "QUALIFIED"


@pytest.mark.parametrize("mode", ["override", "placeholder", "dimpost"])
def test_units_are_checked_for_every_display_source(tmp_path: Path, mode: str) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    if mode == "override":
        dim.dxf.text = "100 cm"
    elif mode == "placeholder":
        dim.dxf.text = "<> cm"
    else:
        override = DimStyleOverride(dim)
        override["dimpost"] = "<> cm"
        override.commit()
    _set_rendered_block_text(dim, "100 cm")
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "FAILED"


@pytest.mark.parametrize("label", ["100 widgets", "100 mmREF", "100 cm/in", "100REF"])
def test_unsupported_unit_or_annotation_semantics_are_unknown(tmp_path: Path, label: str) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    dim.dxf.text = label
    _set_rendered_block_text(dim, label)
    doc.saveas(built.output_path)
    result = review_dxf_with_dimension_line_integrity(built)
    assert result.qualification == "UNKNOWN"
    assert any("dim_unverified" in reason for reason in result.semantic_review.dimension_mismatches)


def test_explicit_unit_conversion_does_not_expand_numeric_error_allowance(tmp_path: Path) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    dim.dxf.text = "10.000001 cm"
    _set_rendered_block_text(dim, "10.000001 cm")
    doc.saveas(built.output_path)
    result = review_dxf_with_dimension_line_integrity(built)
    assert result.qualification == "FAILED"


def test_physical_contradiction_is_not_downgraded_by_unknown_rendering(tmp_path: Path) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    dim.dxf.text = "100 cm"
    _set_rendered_block_text(dim, "100 cm")
    for text in dim.get_geometry_block().query("MTEXT"):
        text.dxf.char_height = math.nan
    doc.saveas(built.output_path)
    result = review_dxf_with_dimension_line_integrity(built)
    assert result.qualification == "FAILED"


@pytest.mark.parametrize("label", ["0°30'", "-0°30'", "−0°30'"])
def test_angular_dms_claim_preserves_sign_when_degrees_are_zero(tmp_path: Path, label: str) -> None:
    from dxf_builder_lib._dimension_truth import audit_dimension_truth

    doc = ezdxf.new("R2010", setup=True)
    angle = math.radians(0.5)
    override = doc.modelspace().add_angular_dim_2l(
        base=(10, 0.05), line1=((0, 0), (10, 0)),
        line2=((0, 0), (10 * math.cos(angle), 10 * math.sin(angle))),
        override={"dimtxt": 1.0, "dimaunit": 1, "dimadec": 2}, text=label,
    )
    override.render()
    dim = override.dimension
    _set_rendered_block_text(dim, label)
    path = tmp_path / "angular.dxf"
    doc.saveas(path)
    before = path.read_bytes()
    reopened = ezdxf.readfile(path)
    entity = reopened.entitydb[dim.dxf.handle]
    assert entity.get_measurement() == pytest.approx(0.5)
    reasons = audit_dimension_truth(reopened, entity)
    assert path.read_bytes() == before
    if label == "0°30'":
        assert reasons == []
    else:
        assert any("dim_override_disagrees" in reason for reason in reasons)


def test_linear_unit_on_angular_claim_remains_unverified(tmp_path: Path) -> None:
    from dxf_builder_lib._dimension_truth import audit_dimension_truth

    doc = ezdxf.new("R2010", setup=True)
    override = doc.modelspace().add_angular_dim_2l(
        base=(5, 5), line1=((0, 0), (10, 0)), line2=((0, 0), (0, 10)),
        override={"dimtxt": 1.0}, text="90 mm",
    )
    override.render()
    dim = override.dimension
    _set_rendered_block_text(dim, "90 mm")
    path = tmp_path / "angular-unit.dxf"
    doc.saveas(path)
    reopened = ezdxf.readfile(path)
    reasons = audit_dimension_truth(reopened, reopened.entitydb[dim.dxf.handle])
    assert any("dim_unverified" in reason for reason in reasons)


@pytest.mark.parametrize("unit,label,want_pass", [(2, "100g", True), (2, "90g", False), (3, "1.5707963267948966r", True)])
def test_existing_angular_unit_interpretation_is_preserved(tmp_path: Path, unit: int, label: str, want_pass: bool) -> None:
    from dxf_builder_lib._dimension_truth import audit_dimension_truth

    doc = ezdxf.new("R2010", setup=True)
    override = doc.modelspace().add_angular_dim_2l(
        base=(5, 5), line1=((0, 0), (10, 0)), line2=((0, 0), (0, 10)),
        override={"dimtxt": 1.0, "dimaunit": unit}, text=label,
    )
    override.render()
    dim = override.dimension
    _set_rendered_block_text(dim, label)
    path = tmp_path / "angular-style.dxf"
    doc.saveas(path)
    reopened = ezdxf.readfile(path)
    reasons = audit_dimension_truth(reopened, reopened.entitydb[dim.dxf.handle])
    assert (not reasons) is want_pass


def test_explicit_override_cache_cannot_hide_configured_limits(tmp_path: Path) -> None:
    built, doc, dim = _explicit_truth_control(
        tmp_path, dimlim=1, dimtol=0, dimtp=0.1, dimtm=0.1,
    )
    dim.dxf.text = "100"
    _set_rendered_block_text(dim, "100")
    doc.saveas(built.output_path)
    before = Path(built.output_path).read_bytes()
    result = review_dxf_with_dimension_line_integrity(built)
    assert Path(built.output_path).read_bytes() == before
    assert not result.passed
    assert result.qualification != "QUALIFIED"


def test_converted_unit_cannot_conceal_physical_tolerance_mismatch(tmp_path: Path) -> None:
    from ezdxf.render.dim_base import Tolerance

    built, doc, dim = _explicit_truth_control(
        tmp_path, dimtol=1, dimtp=0.1, dimtm=0.1,
        dimtfac=0.5, dimtdec=2, dimtzin=0,
    )
    dim.dxf.text = "10 cm"
    expected = Tolerance(DimStyleOverride(dim)).compile_mtext("10 cm")
    _set_rendered_block_text(dim, expected)
    doc.saveas(built.output_path)
    before = Path(built.output_path).read_bytes()
    result = review_dxf_with_dimension_line_integrity(built)
    assert Path(built.output_path).read_bytes() == before
    assert not result.passed
    assert result.qualification != "QUALIFIED"


def test_native_mm_tolerance_control_remains_supported(tmp_path: Path) -> None:
    from ezdxf.render.dim_base import Tolerance

    built, doc, dim = _explicit_truth_control(
        tmp_path, dimtol=1, dimtp=0.1, dimtm=0.1,
        dimtfac=0.5, dimtdec=2, dimtzin=0,
    )
    dim.dxf.text = "100 mm"
    _set_rendered_block_text(dim, Tolerance(DimStyleOverride(dim)).compile_mtext("100 mm"))
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "QUALIFIED"


def test_converted_primary_without_tolerance_remains_supported(tmp_path: Path) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    dim.dxf.text = "10 cm"
    _set_rendered_block_text(dim, "10 cm")
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "QUALIFIED"


def test_explicit_override_cannot_skip_unsupported_alternate_units(tmp_path: Path) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path, dimalt=1)
    dim.dxf.text = "100"
    _set_rendered_block_text(dim, "100")
    doc.saveas(built.output_path)
    assert not review_dxf_with_dimension_line_integrity(built).passed


@pytest.mark.parametrize("style_values,label", [
    ({"dimlim": 1, "dimtol": 0, "dimtp": 0.1, "dimtm": 0.1}, "99"),
    ({"dimtol": 1, "dimtp": 0.1, "dimtm": 0.1}, "99 cm"),
    ({"dimalt": 1}, "99"),
])
def test_known_primary_contradiction_remains_failed_with_unverified_style(
    tmp_path: Path, style_values: dict, label: str,
) -> None:
    from ezdxf.render.dim_base import Tolerance

    built, doc, dim = _explicit_truth_control(tmp_path, **style_values)
    dim.dxf.text = label
    rendered = Tolerance(DimStyleOverride(dim)).compile_mtext(label) if style_values.get("dimtol") else label
    _set_rendered_block_text(dim, rendered)
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "FAILED"


def test_converted_tolerance_context_is_explicitly_unverified(tmp_path: Path) -> None:
    from ezdxf.render.dim_base import Tolerance

    built, doc, dim = _explicit_truth_control(
        tmp_path, dimtol=1, dimtp=0.1, dimtm=0.1, dimtdec=2, dimtzin=0,
    )
    dim.dxf.text = "10 cm"
    _set_rendered_block_text(dim, Tolerance(DimStyleOverride(dim)).compile_mtext("10 cm"))
    doc.saveas(built.output_path)
    result = review_dxf_with_dimension_line_integrity(built)
    assert result.qualification == "UNKNOWN"
    assert any("dim_unverified_tolerance_units" in reason for reason in result.semantic_review.dimension_mismatches)


@pytest.mark.parametrize("halign,distance,height_matches,want_pass", [
    (5, 0.0, True, False),
    (3, 0.0, True, False),
    (5, 10.0, True, True),
    (3, 10.0, True, True),
    (3, 10.0, False, False),
    (0, 0.0, True, True),
])
def test_native_text_stretch_is_checked_after_save_reopen(
    tmp_path: Path, halign: int, distance: float, height_matches: bool, want_pass: bool,
) -> None:
    from ezdxf.addons.drawing.properties import RenderContext
    from ezdxf.addons.drawing.text import _get_extra_transform
    from ezdxf.addons.drawing.unified_text_renderer import UnifiedTextRenderer

    built, doc, dim = _explicit_truth_control(tmp_path)
    block = dim.get_geometry_block()
    for cached in list(block.query("TEXT MTEXT")):
        block.delete_entity(cached)
    text = block.add_text("100", dxfattribs={
        "height": 1.0, "insert": (0, 0, 0),
        "align_point": (distance, 0, 0), "halign": halign,
    })
    if halign == 3 and distance and height_matches:
        # A legitimate ALIGNED label scales height too; declare that source
        # height rather than using raw DXF height as a visibility oracle.
        face = RenderContext(doc).resolve_font(text)
        width = UnifiedTextRenderer().get_text_line_width("100", face, 1.0)
        height = _get_extra_transform(text, width).transform_direction((0, 1, 0)).magnitude
        override = DimStyleOverride(dim)
        override["dimtxt"] = height
        override.commit()
    doc.saveas(built.output_path)
    before = Path(built.output_path).read_bytes()
    reopened = ezdxf.readfile(built.output_path)
    assert reopened.entitydb[text.dxf.handle].dxftype() == "TEXT"
    result = review_dxf_with_dimension_line_integrity(built)
    assert Path(built.output_path).read_bytes() == before
    assert result.passed is want_pass
    assert result.qualification == ("QUALIFIED" if want_pass else "FAILED")
    assert review_dxf_with_dimension_line_integrity(built, verify_dimension_truth=False).passed


def test_native_text_unresolved_stretch_font_is_not_qualified(tmp_path: Path) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    block = dim.get_geometry_block()
    for cached in list(block.query("TEXT MTEXT")):
        block.delete_entity(cached)
    block.add_text("100", dxfattribs={
        "height": 1.0, "insert": (0, 0, 0), "align_point": (10, 0, 0),
        "halign": 5, "style": "MISSING_SOURCE_STYLE",
    })
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "UNKNOWN"
    assert review_dxf_with_dimension_line_integrity(built, verify_dimension_truth=False).passed


@pytest.mark.parametrize("kind,raw,override,want_pass", [
    ("TEXT", "100", "100", True),
    ("TEXT", r"{\H0;100}", "100", False),
    ("TEXT", r"1\C900;00", "100", False),
    ("TEXT", "%%c100", "%%c100", True),
    ("MTEXT", r"{\H1x;100}", "100", True),
    ("MTEXT", r"{\\H0;100}", "100", False),
])
def test_cached_entity_text_uses_its_own_literal_semantics(
    tmp_path: Path, kind: str, raw: str, override: str, want_pass: bool,
) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    dim.dxf.text = override
    block = dim.get_geometry_block()
    for cached in list(block.query("TEXT MTEXT")):
        block.delete_entity(cached)
    if kind == "TEXT":
        text = block.add_text(raw, dxfattribs={"height": 1.0})
    else:
        text = block.add_mtext(raw, dxfattribs={"char_height": 1.0})
    doc.saveas(built.output_path)
    reopened = ezdxf.readfile(built.output_path)
    assert reopened.entitydb[text.dxf.handle].dxftype() == kind
    before = Path(built.output_path).read_bytes()
    result = review_dxf_with_dimension_line_integrity(built)
    assert result.passed is want_pass
    assert Path(built.output_path).read_bytes() == before
    assert review_dxf_with_dimension_line_integrity(built, verify_dimension_truth=False).passed


@pytest.mark.parametrize("unit", [1, 3, 4, 5, 6])
@pytest.mark.parametrize("label", ["<>", "<> mm"])
def test_unsupported_primary_format_cannot_borrow_decimal_cache(
    tmp_path: Path, unit: int, label: str,
) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path, dimlunit=unit)
    dim.dxf.text = label
    _set_rendered_block_text(dim, label.replace("<>", "100"))
    doc.saveas(built.output_path)
    before = Path(built.output_path).read_bytes()
    result = review_dxf_with_dimension_line_integrity(built)
    assert result.qualification == "UNKNOWN"
    assert any("dim_unverified_primary_format" in reason for reason in result.semantic_review.dimension_mismatches)
    assert Path(built.output_path).read_bytes() == before
    assert review_dxf_with_dimension_line_integrity(built, verify_dimension_truth=False).passed


@pytest.mark.parametrize("unit", [1, 2, 3, 4, 5, 6])
def test_literal_primary_override_does_not_depend_on_generated_format(tmp_path: Path, unit: int) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path, dimlunit=unit)
    dim.dxf.text = "100"
    _set_rendered_block_text(dim, "100")
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "QUALIFIED"


def test_literal_primary_does_not_verify_unsupported_tolerance_format(tmp_path: Path) -> None:
    from ezdxf.render.dim_base import Tolerance

    built, doc, dim = _explicit_truth_control(tmp_path, dimlunit=4, dimtol=1, dimtp=0.1, dimtm=0.1)
    dim.dxf.text = "100"
    _set_rendered_block_text(dim, Tolerance(DimStyleOverride(dim)).compile_mtext("100"))
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "UNKNOWN"


@pytest.mark.parametrize("with_tolerance", [False, True])
def test_known_literal_contradiction_stays_failed_with_unsupported_primary_format(
    tmp_path: Path, with_tolerance: bool,
) -> None:
    from ezdxf.render.dim_base import Tolerance

    built, doc, dim = _explicit_truth_control(
        tmp_path, dimlunit=4, dimtol=int(with_tolerance), dimtp=0.1, dimtm=0.1,
    )
    dim.dxf.text = "99"
    cached = Tolerance(DimStyleOverride(dim)).compile_mtext("99") if with_tolerance else "99"
    _set_rendered_block_text(dim, cached)
    doc.saveas(built.output_path)
    assert review_dxf_with_dimension_line_integrity(built).qualification == "FAILED"


@pytest.mark.parametrize(
    "arrow_variant",
    [
        "default_closedfilled_and_defpoints",
        "standard_autocad_arrows",
        "two_level_pure_geometry_insert",
        "diamond_dag_pure_geometry_insert",
        "mirrored_negative_scale_and_mixed_case_insert",
    ],
)
def test_pure_geometry_dimension_arrow_blocks_and_defpoints_stay_qualified(
    tmp_path: Path, arrow_variant: str,
) -> None:
    from ezdxf.render.arrows import ARROWS

    built, doc, dim = _explicit_truth_control(tmp_path / arrow_variant)
    block = dim.get_geometry_block()
    if "Defpoints" not in doc.layers:
        doc.layers.add("Defpoints", dxfattribs={"plot": 0})
    block.add_point((0.0, 0.0, 0.0), dxfattribs={"layer": "Defpoints"})

    if arrow_variant == "standard_autocad_arrows":
        for arrow_name in (ARROWS.open, ARROWS.dot, ARROWS.architectural_tick, ARROWS.origin_indicator):
            blk_name = ARROWS.create_block(doc.blocks, arrow_name)
            block.add_blockref(blk_name, (0.0, 0.0, 0.0))
    elif arrow_variant == "two_level_pure_geometry_insert":
        leaf = doc.blocks.new("PURE_GEO_LEAF")
        leaf.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        leaf.add_arc((0.0, 0.0), radius=1.0, start_angle=0.0, end_angle=90.0)
        leaf.add_circle((0.0, 0.0), radius=0.5)
        leaf.add_lwpolyline([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)], close=True)
        leaf.add_trace([(0.0, 0.0), (1.0, 0.0), (1.0, 0.2), (0.0, 0.2)])
        leaf.add_line((0.0, 0.0), (1.0, 0.0))
        leaf.add_point((0.0, 0.0, 0.0))
        outer = doc.blocks.new("PURE_GEO_OUTER")
        outer.add_blockref(leaf.name, (0.0, 0.0, 0.0))
        block.add_blockref(outer.name, (0.0, 0.0, 0.0))
    elif arrow_variant == "diamond_dag_pure_geometry_insert":
        leaf = doc.blocks.new("DAG_LEAF")
        leaf.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        mid_a = doc.blocks.new("DAG_MID_A")
        mid_a.add_blockref(leaf.name, (0.0, 0.0, 0.0))
        mid_b = doc.blocks.new("DAG_MID_B")
        mid_b.add_blockref(leaf.name, (1.0, 0.0, 0.0))
        top = doc.blocks.new("DAG_TOP")
        top.add_blockref(mid_a.name, (0.0, 0.0, 0.0))
        top.add_blockref(mid_b.name, (0.0, 0.0, 0.0))
        block.add_blockref(top.name, (0.0, 0.0, 0.0))
    elif arrow_variant == "mirrored_negative_scale_and_mixed_case_insert":
        arrow = doc.blocks.new("MIXED_CASE_ARROW")
        arrow.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        block.add_blockref(
            "mixed_case_arrow",
            (0.0, 0.0, 0.0),
            dxfattribs={"xscale": -1.0, "yscale": -1.0, "zscale": 1.0, "rotation": 180.0},
        )

    doc.saveas(built.output_path)
    before = Path(built.output_path).read_bytes()
    strict = review_dxf_with_dimension_line_integrity(built)
    semantic = review_dxf(built, verify_dimension_truth=True)
    assert Path(built.output_path).read_bytes() == before
    assert strict.qualification == "QUALIFIED"
    assert strict.passed
    assert semantic.passed


@pytest.mark.parametrize(
    "escape_case",
    [
        "nested_insert_text_99",
        "nested_insert_mtext_200",
        "two_level_nested_insert_text_999",
        "insert_with_visible_attrib_888",
        "insert_with_invisible_attrib_888",
        "nested_block_with_attdef_777",
        "direct_constant_attdef_777",
        "direct_leader",
        "nested_leader",
        "direct_mleader",
        "nested_mleader",
        "direct_tolerance",
        "nested_tolerance",
        "missing_target_block_insert",
        "xref_block_insert",
        "layout_block_insert",
        "deep_nested_insert_over_cap",
        "cyclic_insert_a_b_a",
        "self_cyclic_insert_a_a",
        "mixed_case_cyclic_insert",
        "direct_wipeout_masking",
        "nested_wipeout_masking",
        "direct_solid_hatch",
        "nested_solid_hatch",
        "nested_spline_glyph_outline",
        "nested_ellipse_outline",
        "nested_3dface",
        "direct_polyface_mesh",
        "nested_polyline2d",
        "blank_bg_fill_mtext_alongside_label",
        "minsert_multi_grid",
        "zero_xscale_insert",
        "zero_zscale_insert",
        "zero_extrusion_insert",
    ],
)
def test_uninspected_nested_or_non_text_rendered_structures_fail_closed(
    tmp_path: Path, escape_case: str,
) -> None:
    from ezdxf.math import Vec2, Vec3

    built, doc, dim = _explicit_truth_control(tmp_path / escape_case)
    block = dim.get_geometry_block()

    if escape_case == "nested_insert_text_99":
        child = doc.blocks.new("EXTRA_NATIVE_LABEL_TEXT")
        child.add_text("99", dxfattribs={"height": 1.0})
        block.add_blockref(child.name, (0.0, 0.0, 0.0))
    elif escape_case == "nested_insert_mtext_200":
        child = doc.blocks.new("EXTRA_NATIVE_LABEL_MTEXT")
        child.add_mtext("200", dxfattribs={"char_height": 1.0})
        block.add_blockref(child.name, (0.0, 0.0, 0.0))
    elif escape_case == "two_level_nested_insert_text_999":
        leaf = doc.blocks.new("LEAF_LABEL_999")
        leaf.add_text("999", dxfattribs={"height": 1.0})
        wrapper = doc.blocks.new("WRAPPER_BLK")
        wrapper.add_blockref(leaf.name, (0.0, 0.0, 0.0))
        block.add_blockref(wrapper.name, (0.0, 0.0, 0.0))
    elif escape_case in {"insert_with_visible_attrib_888", "insert_with_invisible_attrib_888"}:
        arrow = doc.blocks.new("ARROW_SOLID_ONLY")
        arrow.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        ref = block.add_blockref(arrow.name, (0.0, 0.0, 0.0))
        flags = 1 if "invisible" in escape_case else 0
        ref.add_attrib("FAKE_LABEL", "888", (0.0, 0.0, 0.0), dxfattribs={"height": 1.0, "flags": flags})
    elif escape_case == "nested_block_with_attdef_777":
        child = doc.blocks.new("BLK_CONST_ATTDEF")
        child.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        child.add_attdef("CONST_TAG", (0.0, 0.0, 0.0), "777", dxfattribs={"height": 1.0, "flags": 3})
        block.add_blockref(child.name, (0.0, 0.0, 0.0))
    elif escape_case == "direct_constant_attdef_777":
        block.add_attdef("CONST_TAG", (0.0, 0.0, 0.0), "777", dxfattribs={"height": 1.0, "flags": 2})
    elif escape_case == "direct_leader":
        block.add_leader([(0.0, 0.0), (5.0, 5.0), (10.0, 5.0)])
    elif escape_case == "nested_leader":
        child = doc.blocks.new("BLK_LEADER")
        child.add_leader([(0.0, 0.0), (5.0, 5.0), (10.0, 5.0)])
        block.add_blockref(child.name, (0.0, 0.0, 0.0))
    elif escape_case == "direct_mleader":
        ml = block.add_multileader_mtext()
        ml.quick_leader("999", target=Vec2(0.0, 0.0), segment1=Vec2(5.0, 5.0))
    elif escape_case == "nested_mleader":
        child = doc.blocks.new("BLK_MLEADER")
        ml = child.add_multileader_mtext()
        ml.quick_leader("999", target=Vec2(0.0, 0.0), segment1=Vec2(5.0, 5.0))
        block.add_blockref(child.name, (0.0, 0.0, 0.0))
    elif escape_case == "direct_tolerance":
        block.new_entity(
            "TOLERANCE",
            dxfattribs={"content": r"{\Fgdt;j}%%v0.05", "insert": (0.0, 0.0, 0.0), "dimstyle": "Standard"},
        )
    elif escape_case == "nested_tolerance":
        child = doc.blocks.new("BLK_TOLERANCE")
        child.new_entity(
            "TOLERANCE",
            dxfattribs={"content": r"{\Fgdt;j}%%v0.05", "insert": (0.0, 0.0, 0.0), "dimstyle": "Standard"},
        )
        block.add_blockref(child.name, (0.0, 0.0, 0.0))
    elif escape_case == "missing_target_block_insert":
        placeholder = doc.blocks.new("TEMP_VALID_TARGET")
        placeholder.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        ref = block.add_blockref(placeholder.name, (0.0, 0.0, 0.0))
        ref.dxf.name = "MISSING_TARGET_ARROW_BLK"
    elif escape_case == "xref_block_insert":
        doc.add_xref_def(filename="external_labels.dwg", name="XREF_LABEL_BLK")
        block.add_blockref("XREF_LABEL_BLK", (0.0, 0.0, 0.0))
    elif escape_case == "layout_block_insert":
        placeholder = doc.blocks.new("TEMP_LAYOUT_TARGET")
        placeholder.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        ref = block.add_blockref(placeholder.name, (0.0, 0.0, 0.0))
        ref.dxf.name = "*Paper_Space"
    elif escape_case == "deep_nested_insert_over_cap":
        prev = doc.blocks.new("DEEP_ARROW_LEAF")
        prev.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        for idx in range(34):
            nxt = doc.blocks.new(f"DEEP_ARROW_{idx}")
            nxt.add_blockref(prev.name, (0.0, 0.0, 0.0))
            prev = nxt
        block.add_blockref(prev.name, (0.0, 0.0, 0.0))
    elif escape_case == "cyclic_insert_a_b_a":
        cyc_a = doc.blocks.new("CYC_A")
        cyc_b = doc.blocks.new("CYC_B")
        cyc_a.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        cyc_a.add_blockref(cyc_b.name, (0.0, 0.0, 0.0))
        cyc_b.add_blockref(cyc_a.name, (0.0, 0.0, 0.0))
        block.add_blockref(cyc_a.name, (0.0, 0.0, 0.0))
    elif escape_case == "self_cyclic_insert_a_a":
        self_a = doc.blocks.new("SELF_A")
        self_a.add_blockref(self_a.name, (0.0, 0.0, 0.0))
        block.add_blockref(self_a.name, (0.0, 0.0, 0.0))
    elif escape_case == "mixed_case_cyclic_insert":
        cyc_a = doc.blocks.new("Cycle_Alpha")
        cyc_b = doc.blocks.new("cycle_beta")
        cyc_a.add_blockref("CYCLE_BETA", (0.0, 0.0, 0.0))
        cyc_b.add_blockref("cycle_alpha", (0.0, 0.0, 0.0))
        block.add_blockref("CYCLE_ALPHA", (0.0, 0.0, 0.0))
    elif escape_case == "direct_wipeout_masking":
        block.add_wipeout([(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0)])
    elif escape_case == "nested_wipeout_masking":
        child = doc.blocks.new("BLK_WIPEOUT_MASK")
        child.add_wipeout([(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0)])
        block.add_blockref(child.name, (0.0, 0.0, 0.0))
    elif escape_case == "direct_solid_hatch":
        hatch = block.add_hatch()
        hatch.paths.add_polyline_path([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)], is_closed=True)
    elif escape_case == "nested_solid_hatch":
        child = doc.blocks.new("BLK_SOLID_HATCH")
        hatch = child.add_hatch()
        hatch.paths.add_polyline_path([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)], is_closed=True)
        block.add_blockref(child.name, (0.0, 0.0, 0.0))
    elif escape_case == "nested_spline_glyph_outline":
        child = doc.blocks.new("BLK_SPLINE_GLYPH")
        child.add_spline([(0.0, 0.0, 0.0), (1.0, 2.0, 0.0), (2.0, 0.0, 0.0)])
        block.add_blockref(child.name, (0.0, 0.0, 0.0))
    elif escape_case == "nested_ellipse_outline":
        child = doc.blocks.new("BLK_ELLIPSE_GLYPH")
        child.add_ellipse(center=(0.0, 0.0, 0.0), major_axis=(2.0, 0.0, 0.0), ratio=0.5)
        block.add_blockref(child.name, (0.0, 0.0, 0.0))
    elif escape_case == "nested_3dface":
        child = doc.blocks.new("BLK_3DFACE")
        child.add_3dface([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)])
        block.add_blockref(child.name, (0.0, 0.0, 0.0))
    elif escape_case == "direct_polyface_mesh":
        pface = block.add_polyface()
        pface.append_face([(0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (5.0, 5.0, 0.0)])
    elif escape_case == "nested_polyline2d":
        child = doc.blocks.new("BLK_POLYLINE2D")
        child.add_polyline2d([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)], close=True)
        block.add_blockref(child.name, (0.0, 0.0, 0.0))
    elif escape_case == "blank_bg_fill_mtext_alongside_label":
        block.add_mtext("   ", dxfattribs={"char_height": 2.5, "bg_fill": 1, "bg_fill_color": 7})
    elif escape_case == "minsert_multi_grid":
        arrow = doc.blocks.new("ARROW_MINSERT")
        arrow.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        block.add_blockref(arrow.name, (0.0, 0.0, 0.0)).grid(size=(4, 4), spacing=(1.0, 1.0))
    elif escape_case == "zero_xscale_insert":
        arrow = doc.blocks.new("ARROW_ZERO_X")
        arrow.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        ref = block.add_blockref(arrow.name, (0.0, 0.0, 0.0))
        ref.dxf.unprotected_set("xscale", 0.0)
    elif escape_case == "zero_zscale_insert":
        arrow = doc.blocks.new("ARROW_ZERO_Z")
        arrow.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        ref = block.add_blockref(arrow.name, (0.0, 0.0, 0.0))
        ref.dxf.unprotected_set("zscale", 0.0)
    elif escape_case == "zero_extrusion_insert":
        arrow = doc.blocks.new("ARROW_ZERO_EXT")
        arrow.add_solid([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        ref = block.add_blockref(arrow.name, (0.0, 0.0, 0.0))
        ref.dxf.unprotected_set("extrusion", Vec3(0.0, 0.0, 0.0))

    doc.saveas(built.output_path)
    before = Path(built.output_path).read_bytes()

    strict = review_dxf_with_dimension_line_integrity(built)
    semantic = review_dxf(built, verify_dimension_truth=True)
    assert Path(built.output_path).read_bytes() == before
    assert review_dxf_with_dimension_line_integrity(built, verify_dimension_truth=False).passed
    assert not strict.passed
    assert strict.qualification == "UNKNOWN"
    assert not semantic.passed
    assert any("dim_unverified_rendered_structure" in msg for msg in semantic.dimension_mismatches)


def test_primary_contradiction_stays_failed_even_with_nested_insert_label(tmp_path: Path) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    dim.dxf.text = "99"
    _set_rendered_block_text(dim, "99")
    child = doc.blocks.new("EXTRA_NESTED_200")
    child.add_text("200", dxfattribs={"height": 1.0})
    dim.get_geometry_block().add_blockref(child.name, (0.0, 0.0, 0.0))
    doc.saveas(built.output_path)

    result = review_dxf_with_dimension_line_integrity(built)
    assert not result.passed
    assert result.qualification == "FAILED"


@pytest.mark.parametrize(
    ("rnd_val", "fake_rendered"),
    [(200.0, "0"), (60.0, "120"), (150.0, "150")],
)
def test_dimrnd_cannot_self_inflate_tolerance_to_hide_wrong_displayed_value(
    tmp_path: Path, rnd_val: float, fake_rendered: str,
) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path / f"rnd_{int(rnd_val)}", dimrnd=rnd_val)
    _set_rendered_block_text(dim, fake_rendered)
    doc.saveas(built.output_path)

    strict = review_dxf_with_dimension_line_integrity(built)
    semantic = review_dxf(built, verify_dimension_truth=True)
    assert not strict.passed
    assert strict.qualification == "FAILED"
    assert not semantic.passed


@pytest.mark.parametrize(
    "bad_style",
    [
        {"dimrnd": 1e-308},
        {"dimrnd": float("inf")},
        {"dimrnd": -0.5},
        {"dimdec": 500_000, "dimzin": 0},
        {"dimdec": -1},
    ],
)
def test_extreme_or_invalid_dimrnd_and_dimdec_fail_closed_in_o1_without_exception(
    tmp_path: Path, bad_style: dict[str, object],
) -> None:
    built, doc, _dim = _explicit_truth_control(tmp_path, **bad_style)
    doc.saveas(built.output_path)

    strict = review_dxf_with_dimension_line_integrity(built)
    semantic = review_dxf(built, verify_dimension_truth=True)
    assert not strict.passed
    assert strict.qualification in {"FAILED", "UNKNOWN"}
    assert not semantic.passed


@pytest.mark.parametrize(
    ("insunits", "label"),
    [(1, "100 mm"), (1, "10 cm"), (6, ""), (0, "100 mm")],
)
def test_non_millimetre_drawing_insunits_cannot_qualify_linear_reference(
    tmp_path: Path, insunits: int, label: str,
) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path / f"ins_{insunits}_{label.replace(' ', '_')}")
    doc.header["$INSUNITS"] = insunits
    if label:
        dim.dxf.text = label
        _set_rendered_block_text(dim, label)
    doc.saveas(built.output_path)

    strict = review_dxf_with_dimension_line_integrity(built)
    semantic = review_dxf(built, verify_dimension_truth=True)
    assert not strict.passed
    assert strict.qualification != "QUALIFIED"
    assert not semantic.passed


def test_zero_count_prefix_cross_symbol_lies_and_surveyor_dimaunit_fail_closed(
    tmp_path: Path,
) -> None:
    from dxf_builder_lib._dimension_truth import audit_dimension_truth

    built_zero, doc_zero, dim_zero = _explicit_truth_control(tmp_path / "zero_mult")
    dim_zero.dxf.text = "0x 100"
    _set_rendered_block_text(dim_zero, "0x 100")
    doc_zero.saveas(built_zero.output_path)
    res_zero = review_dxf_with_dimension_line_integrity(built_zero)
    assert not res_zero.passed
    assert res_zero.qualification == "FAILED"

    built_two, doc_two, dim_two = _explicit_truth_control(tmp_path / "two_mult")
    dim_two.dxf.text = "2x 100"
    _set_rendered_block_text(dim_two, "2x 100")
    doc_two.saveas(built_two.output_path)
    assert review_dxf_with_dimension_line_integrity(built_two).qualification == "QUALIFIED"

    doc_rad = ezdxf.new("R2010", setup=True)
    doc_rad.header["$INSUNITS"] = 4
    ov_rad = doc_rad.modelspace().add_radius_dim(
        center=(0, 0), radius=13.5, angle=45,
        override={"dimtxt": 1.0, "dimlfac": 1.0, "dimscale": 1.0, "dimdec": 2, "dimzin": 0},
        text="%%c13.50",
    )
    ov_rad.render()
    _set_rendered_block_text(ov_rad.dimension, "\u00d813.50")
    rad_path = tmp_path / "rad_lie.dxf"
    doc_rad.saveas(rad_path)
    re_rad = ezdxf.readfile(rad_path)
    assert audit_dimension_truth(
        re_rad, re_rad.entitydb[ov_rad.dimension.dxf.handle],
        expected_measurement=13.5, approved_value_mm=13.5,
    )

    doc_rad_ok = ezdxf.new("R2010", setup=True)
    doc_rad_ok.header["$INSUNITS"] = 4
    ov_rad_ok = doc_rad_ok.modelspace().add_radius_dim(
        center=(0, 0), radius=13.5, angle=45,
        override={"dimtxt": 1.0, "dimlfac": 1.0, "dimscale": 1.0, "dimdec": 2, "dimzin": 0},
    )
    ov_rad_ok.render()
    ov_rad_ok.dimension.dxf.dimtype = 164
    _set_rendered_block_text(ov_rad_ok.dimension, r"\A1;R13.50")
    rad_ok_path = tmp_path / "rad_ok.dxf"
    doc_rad_ok.saveas(rad_ok_path)
    re_rad_ok = ezdxf.readfile(rad_ok_path)
    assert audit_dimension_truth(
        re_rad_ok, re_rad_ok.entitydb[ov_rad_ok.dimension.dxf.handle],
        expected_measurement=13.5, approved_value_mm=13.5,
    ) == []

    doc_dia = ezdxf.new("R2010", setup=True)
    doc_dia.header["$INSUNITS"] = 4
    ov_dia = doc_dia.modelspace().add_diameter_dim(
        center=(0, 0), radius=17.0, angle=45,
        override={"dimtxt": 1.0, "dimlfac": 1.0, "dimscale": 1.0},
        text="R34",
    )
    ov_dia.render()
    _set_rendered_block_text(ov_dia.dimension, "R34")
    dia_path = tmp_path / "dia_lie.dxf"
    doc_dia.saveas(dia_path)
    re_dia = ezdxf.readfile(dia_path)
    assert audit_dimension_truth(
        re_dia, re_dia.entitydb[ov_dia.dimension.dxf.handle],
        expected_measurement=34.0, approved_value_mm=34.0,
    )

    doc_ang = ezdxf.new("R2010", setup=True)
    ov_ang = doc_ang.modelspace().add_angular_dim_2l(
        base=(5, 5), line1=((0, 0), (10, 0)),
        line2=((0, 0), (5, 8.660254037844387)),
        override={"dimtxt": 1.0, "dimscale": 1.0, "dimaunit": 4, "dimadec": 0},
    )
    ov_ang.render()
    _set_rendered_block_text(ov_ang.dimension, "60\u00b0")
    ang_path = tmp_path / "ang_surveyor.dxf"
    doc_ang.saveas(ang_path)
    re_ang = ezdxf.readfile(ang_path)
    ang_reasons = audit_dimension_truth(
        re_ang, re_ang.entitydb[ov_ang.dimension.dxf.handle], expected_measurement=60.0,
    )
    assert any("dim_unverified_primary_format" in r for r in ang_reasons)


@pytest.mark.parametrize(
    "rendered_tamper",
    [
        "mtext_nan_insert",
        "mtext_zero_extrusion",
        "mtext_edgeon_extrusion",
        "mtext_zero_text_direction",
        "text_nan_rotation",
        "text_nan_oblique",
        "multi_mtext_bgfill_mask",
        "inline_strikethrough_K",
        "inline_percent_k_strikethrough",
        "inline_zero_tracking_T0",
        "inline_oblique_90_Q90",
        "inline_symbol_font_Fgdt",
        "style_symbol_font_gdt",
    ],
)
def test_rendered_text_transform_split_bgfill_and_inline_mtext_escapes_fail_closed(
    tmp_path: Path, rendered_tamper: str,
) -> None:
    from ezdxf.math import Vec3

    built, doc, dim = _explicit_truth_control(tmp_path / rendered_tamper)
    blk = dim.get_geometry_block()
    mt = next(e for e in blk if e.dxftype() == "MTEXT")

    if rendered_tamper == "mtext_nan_insert":
        mt.dxf.unprotected_set("insert", Vec3(math.nan, 0.0, 0.0))
    elif rendered_tamper == "mtext_zero_extrusion":
        mt.dxf.unprotected_set("extrusion", Vec3(0.0, 0.0, 0.0))
    elif rendered_tamper == "mtext_edgeon_extrusion":
        mt.dxf.extrusion = (0.0, 1.0, 0.0)
    elif rendered_tamper == "mtext_zero_text_direction":
        mt.dxf.unprotected_set("text_direction", Vec3(0.0, 0.0, 0.0))
    elif rendered_tamper == "text_nan_rotation":
        blk.delete_entity(mt)
        t = blk.add_text("100", dxfattribs={"height": 1.0})
        t.dxf.unprotected_set("rotation", math.nan)
    elif rendered_tamper == "text_nan_oblique":
        blk.delete_entity(mt)
        t = blk.add_text("100", dxfattribs={"height": 1.0})
        t.dxf.unprotected_set("oblique", math.nan)
    elif rendered_tamper == "multi_mtext_bgfill_mask":
        dim.dxf.text = "100 mm"
        blk.delete_entity(mt)
        blk.add_mtext("100", dxfattribs={"char_height": 1.0, "insert": (50.0, 8.0, 0.0)})
        blk.add_mtext(
            "mm",
            dxfattribs={"char_height": 1.0, "insert": (50.0, 8.0, 0.0), "bg_fill": 1, "bg_fill_color": 7},
        )
    elif rendered_tamper == "inline_strikethrough_K":
        _set_rendered_block_text(dim, r"{\K100}")
    elif rendered_tamper == "inline_percent_k_strikethrough":
        _set_rendered_block_text(dim, "%%k100")
    elif rendered_tamper == "inline_zero_tracking_T0":
        _set_rendered_block_text(dim, r"{\T0;100}")
    elif rendered_tamper == "inline_oblique_90_Q90":
        _set_rendered_block_text(dim, r"{\Q90;100}")
    elif rendered_tamper == "inline_symbol_font_Fgdt":
        _set_rendered_block_text(dim, r"{\Fgdt;100}")
    elif rendered_tamper == "style_symbol_font_gdt":
        doc.styles.get("Standard").dxf.font = "gdt.shx"

    doc.saveas(built.output_path)
    strict = review_dxf_with_dimension_line_integrity(built)
    semantic = review_dxf(built, verify_dimension_truth=True)
    assert not strict.passed
    assert strict.qualification in {"FAILED", "UNKNOWN"}
    assert not semantic.passed


@pytest.mark.parametrize(
    ("override_val", "rendered_val"),
    [
        (None, "99 : dim_unverified_x"),
        ("99 / 88 : dim_unverified_", "99 / 88 : dim_unverified_"),
    ],
)
def test_untrusted_dim_unverified_substring_cannot_downgrade_failed_contradiction(
    tmp_path: Path, override_val: str | None, rendered_val: str,
) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    if override_val is not None:
        dim.dxf.text = override_val
    _set_rendered_block_text(dim, rendered_val)
    doc.saveas(built.output_path)

    strict = review_dxf_with_dimension_line_integrity(built)
    assert not strict.passed
    assert strict.qualification == "FAILED"


def _rendered_mtext(dim):
    return next(e for e in dim.get_geometry_block() if e.dxftype() == "MTEXT")


@pytest.mark.parametrize(
    "tamper_case",
    [
        "custom_bg_fill_17_with_text_frame",
        "unknown_bg_fill_bit_64",
        "excessive_box_fill_scale",
        "inline_truecolor_white_self_erasure",
        "inline_aci0_byblock_color",
        "inline_aci1_without_dimclrt",
        "inline_aci255_white",
        "inline_aci256_bylayer",
        "inline_font_sans_serif_default_bypass",
        "entity_truecolor_white_self_erasure",
        "entity_aci255_white_self_erasure",
        "layer_truecolor_white_self_erasure",
        "dimclrt_255_white_self_erasure",
        "style_mirrored_generation_flag",
        "text_mirrored_generation_flag",
    ],
)
def test_rendered_block_r7_bg_fill_color_and_font_escapes_stay_non_qualified(
    tmp_path: Path, tamper_case: str,
) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path / tamper_case)
    blk = dim.get_geometry_block()
    mt = _rendered_mtext(dim)
    if tamper_case == "custom_bg_fill_17_with_text_frame":
        mt.set_bg_color(7, text_frame=True)
    elif tamper_case == "unknown_bg_fill_bit_64":
        mt.dxf.unprotected_set("bg_fill", 64)
    elif tamper_case == "excessive_box_fill_scale":
        mt.dxf.bg_fill = 3
        mt.dxf.box_fill_scale = 20.0
    elif tamper_case == "inline_truecolor_white_self_erasure":
        mt.text = r"{\c16777215;100}"
    elif tamper_case == "inline_aci0_byblock_color":
        mt.text = r"{\C0;100}"
    elif tamper_case == "inline_aci1_without_dimclrt":
        mt.text = r"{\C1;100}"
    elif tamper_case == "inline_aci255_white":
        mt.text = r"{\C255;100}"
    elif tamper_case == "inline_aci256_bylayer":
        mt.text = r"{\C256;100}"
    elif tamper_case == "inline_font_sans_serif_default_bypass":
        mt.text = r"{\fsans-serif;100}"
    elif tamper_case == "entity_truecolor_white_self_erasure":
        mt.rgb = (255, 255, 255)
    elif tamper_case == "entity_aci255_white_self_erasure":
        mt.dxf.color = 255
    elif tamper_case == "layer_truecolor_white_self_erasure":
        mt.dxf.color = 256
        doc.layers.get(mt.dxf.layer).rgb = (255, 255, 255)
    elif tamper_case == "dimclrt_255_white_self_erasure":
        from ezdxf.entities import DimStyleOverride

        ovr = DimStyleOverride(dim)
        ovr.update({"dimclrt": 255})
        ovr.commit()
    elif tamper_case == "style_mirrored_generation_flag":
        doc.styles.get("Standard").dxf.generation_flags = 2
    elif tamper_case == "text_mirrored_generation_flag":
        blk.delete_entity(mt)
        blk.add_text("100", dxfattribs={"height": 1.0, "text_generation_flag": 2})

    doc.saveas(built.output_path)
    strict = review_dxf_with_dimension_line_integrity(built)
    semantic = review_dxf(built, verify_dimension_truth=True)
    assert not strict.passed
    assert strict.qualification in {"FAILED", "UNKNOWN"}
    assert not semantic.passed


@pytest.mark.parametrize("bg_fill_val", [0, 2, 3, 16, 18, 19])
def test_legitimate_dimtfill_canvas_mask_and_text_frame_remain_qualified(
    tmp_path: Path, bg_fill_val: int,
) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path)
    mt = _rendered_mtext(dim)
    mt.dxf.bg_fill = bg_fill_val
    doc.saveas(built.output_path)

    strict = review_dxf_with_dimension_line_integrity(built)
    assert strict.passed
    assert strict.qualification == "QUALIFIED"


def test_legitimate_dimclrt_rendered_and_inline_matching_aci_remain_qualified() -> None:
    from dxf_builder_lib._dimension_truth import audit_dimension_truth

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0))
    dim_tol = msp.add_linear_dim(
        base=(0, 20),
        p1=(0, 0),
        p2=(100, 0),
        text="<>",
        override={"dimtxt": 2.5, "dimclrt": 1, "dimtol": 1, "dimtp": 0.1, "dimtm": 0.1},
    )
    dim_tol.render()
    assert audit_dimension_truth(doc, dim_tol.dimension, expected_measurement=100.0) == []

    dim_inline = msp.add_linear_dim(
        base=(0, 40),
        p1=(0, 0),
        p2=(100, 0),
        text="<>",
        override={"dimtxt": 2.5, "dimclrt": 1},
    )
    dim_inline.render()
    mt = next(e for e in dim_inline.dimension.get_geometry_block() if e.dxftype() == "MTEXT")
    mt.text = r"{\C1;100}"
    assert audit_dimension_truth(doc, dim_inline.dimension, expected_measurement=100.0) == []

    dim_yellow = msp.add_linear_dim(
        base=(0, 60),
        p1=(0, 0),
        p2=(100, 0),
        text="<>",
        override={"dimtxt": 2.5, "dimclrt": 2},
    )
    dim_yellow.render()
    assert audit_dimension_truth(doc, dim_yellow.dimension, expected_measurement=100.0) == []


@pytest.mark.parametrize(
    "r8_escape",
    [
        "override_unterminated_align_100_A1999",
        "override_semicolon_align_A1999_semi_100",
        "override_height_arg_H1x999_semi_100",
        "dimpost_unterminated_align_1999",
        "mtext_unicode_escaped_percent_k",
        "text_caret_escaped_percent_k",
        "mtext_cif_U005C_zero_height_H0",
        "mtext_pct092_fake_font_999",
        "mtext_pct049_literal_codes",
        "mtext_column_break_backslash_N",
        "mtext_empty_font_family_charset2",
        "mtext_txt_font_symbol_charset2",
        "mtext_paragraph_indent_pxi10000",
        "mtext_spoof_style_wingdings",
        "text_spoof_style_mirrored",
        "root_dblock_xref_flag_and_path",
        "dim_edgeon_extrusion_semantic",
        "dimdec_10_exceeds_autocad_max_8",
    ],
)
def test_r8_unified_lexer_style_xref_extrusion_and_precision_escapes_stay_non_qualified(
    tmp_path: Path, r8_escape: str,
) -> None:
    from ezdxf.entities import DimStyleOverride

    built, doc, dim = _explicit_truth_control(tmp_path / r8_escape)
    blk = dim.get_geometry_block()
    mt = _rendered_mtext(dim)
    if r8_escape == "override_unterminated_align_100_A1999":
        dim.dxf.text = r"100\A1999"
    elif r8_escape == "override_semicolon_align_A1999_semi_100":
        dim.dxf.text = r"\A1999;100"
    elif r8_escape == "override_height_arg_H1x999_semi_100":
        dim.dxf.text = r"\H1x999;100"
    elif r8_escape == "dimpost_unterminated_align_1999":
        ov = DimStyleOverride(dim)
        ov["dimpost"] = r"<>\A1999"
        ov.commit()
    elif r8_escape == "mtext_unicode_escaped_percent_k":
        mt.text = r"\U+0025%k100"
    elif r8_escape == "text_caret_escaped_percent_k":
        blk.delete_entity(mt)
        blk.add_text("^e^ek100", dxfattribs={"height": 1.0})
    elif r8_escape == "mtext_cif_U005C_zero_height_H0":
        mt.text = r"\U+005CH0;100"
    elif r8_escape == "mtext_pct092_fake_font_999":
        mt.text = "%%092f999;100"
    elif r8_escape == "mtext_pct049_literal_codes":
        mt.text = "%%049%%048%%048"
    elif r8_escape == "mtext_column_break_backslash_N":
        mt.text = r"1\N00"
    elif r8_escape == "mtext_empty_font_family_charset2":
        mt.text = r"{\f|b1|c2;100}"
    elif r8_escape == "mtext_txt_font_symbol_charset2":
        mt.text = r"{\ftxt|c2;100}"
    elif r8_escape == "mtext_paragraph_indent_pxi10000":
        mt.text = r"{\pxi10000;100}"
    elif r8_escape == "mtext_spoof_style_wingdings":
        doc.styles.add("SPOOF_STYLE", font="wingdings.ttf")
        mt.dxf.style = "SPOOF_STYLE"
    elif r8_escape == "text_spoof_style_mirrored":
        doc.styles.add("SPOOF_STYLE", font="Arial.ttf", dxfattribs={"generation_flags": 2})
        blk.delete_entity(mt)
        blk.add_text("100", dxfattribs={"height": 1.0, "style": "SPOOF_STYLE"})
    elif r8_escape == "root_dblock_xref_flag_and_path":
        blk.block.dxf.flags = int(blk.block.dxf.get("flags", 0)) | 4
        blk.block.dxf.xref_path = "evil_overlay.dwg"
    elif r8_escape == "dim_edgeon_extrusion_semantic":
        dim.dxf.extrusion = (0.0, 1.0, 0.0)
    elif r8_escape == "dimdec_10_exceeds_autocad_max_8":
        ov = DimStyleOverride(dim)
        ov["dimdec"] = 10
        ov.commit()

    doc.saveas(built.output_path)
    strict = review_dxf_with_dimension_line_integrity(built)
    semantic = review_dxf(built, verify_dimension_truth=True)
    assert not strict.passed
    assert strict.qualification in {"FAILED", "UNKNOWN"}
    assert not semantic.passed


def test_r8_validation_id_prefix_collision_cannot_downgrade_failed_to_unknown(tmp_path: Path) -> None:
    from dxf_builder_lib.builder import NativeLinearDimensionSpec
    from ezdxf.entities import DimStyleOverride

    l1 = Primitive(
        id="l1",
        type="line",
        source="geometry_pdfvector",
        confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 10, 10)),
        geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(100, 0)),
    )
    l2 = Primitive(
        id="l2",
        type="line",
        source="geometry_pdfvector",
        confidence=1.0,
        trace=Trace(bbox_px=(0, 20, 10, 30)),
        geometry=LineGeometry(start=Point2D(0, 20), end=Point2D(100, 20)),
    )
    ir = PrimitiveIRDocument(
        source_document=SourceDocument("s.png", 0, 200, 100),
        calibration=Calibration("mm", 1.0, (0, 0), "manual_override"),
        primitives=[l1, l2],
        cross_validations=[],
    )
    built = build_dxf(
        ir,
        str(tmp_path / "candidate.dxf"),
        build_dimensions=True,
        dimension_specs=[
            NativeLinearDimensionSpec("cv", "l1", 100.0, "t1"),
            NativeLinearDimensionSpec("cv: dim_unverified_spoof", "l2", 100.0, "t2"),
        ],
        capture_dimension_line_integrity=True,
    )
    doc = ezdxf.readfile(built.output_path)
    for h in built.dimension_handle_by_cross_validation_id.values():
        ov = DimStyleOverride(doc.entitydb[h])
        ov["dimtxt"] = 1.0
        ov.commit()
    dim2 = doc.entitydb[built.dimension_handle_by_cross_validation_id["cv: dim_unverified_spoof"]]
    dim2.dxf.text = "999"
    _set_rendered_block_text(dim2, "999")
    doc.saveas(built.output_path)

    strict = review_dxf_with_dimension_line_integrity(built)
    assert strict.qualification == "FAILED"


@pytest.mark.parametrize(
    "crash_probe",
    [
        "dimlfac_1e305_dimrnd_1e_5_overflow",
        "dimlfac_1e307_dimrnd_1_scaled_inf",
        "xdata_dstyle_dimtol_nan",
        "xdata_dstyle_dimlunit_str",
        "xdata_dstyle_dimalt_inf",
        "tampered_dimtype_6_ordinate",
        "tampered_dimtype_7_reserved",
        "tampered_dim_zero_extrusion",
        "ordinate_override_99999_audit",
        "nan_defpoint_override_99999_audit",
        "nan_caller_args_audit",
    ],
)
def test_r8_malformed_xdata_overflow_ordinate_and_nan_inputs_fail_closed_without_exception(
    tmp_path: Path, crash_probe: str,
) -> None:
    from dxf_builder_lib._dimension_truth import audit_dimension_truth
    from ezdxf.entities import DimStyleOverride
    from ezdxf.math import Vec3

    if crash_probe == "ordinate_override_99999_audit":
        doc_ord = ezdxf.new("R2010", setup=True)
        doc_ord.header["$INSUNITS"] = 4
        ov_ord = doc_ord.modelspace().add_ordinate_x_dim(
            feature_location=(100, 50),
            offset=(10, 10),
            override={"dimtxt": 1.0, "dimscale": 1.0, "dimlfac": 1.0},
            text="99999",
        )
        ov_ord.render()
        _set_rendered_block_text(ov_ord.dimension, "99999")
        assert audit_dimension_truth(doc_ord, ov_ord.dimension) != []
        return

    built, doc, dim = _explicit_truth_control(tmp_path / crash_probe)
    if crash_probe == "dimlfac_1e305_dimrnd_1e_5_overflow":
        ov = DimStyleOverride(dim)
        ov["dimlfac"] = 1e305
        ov["dimrnd"] = 1e-5
        ov.commit()
    elif crash_probe == "dimlfac_1e307_dimrnd_1_scaled_inf":
        ov = DimStyleOverride(dim)
        ov["dimlfac"] = 1e307
        ov["dimrnd"] = 1.0
        ov.commit()
    elif crash_probe == "xdata_dstyle_dimtol_nan":
        dim.set_xdata("ACAD", [(1000, "DSTYLE"), (1002, "{"), (1070, 140), (1040, 1.0), (1070, 71), (1040, math.nan), (1002, "}")])
    elif crash_probe == "xdata_dstyle_dimlunit_str":
        dim.set_xdata("ACAD", [(1000, "DSTYLE"), (1002, "{"), (1070, 140), (1040, 1.0), (1070, 277), (1000, "bad"), (1002, "}")])
    elif crash_probe == "xdata_dstyle_dimalt_inf":
        dim.set_xdata("ACAD", [(1000, "DSTYLE"), (1002, "{"), (1070, 140), (1040, 1.0), (1070, 170), (1040, math.inf), (1002, "}")])
    elif crash_probe == "tampered_dimtype_6_ordinate":
        dim.dxf.dimtype = 6
    elif crash_probe == "tampered_dimtype_7_reserved":
        dim.dxf.dimtype = 7
    elif crash_probe == "tampered_dim_zero_extrusion":
        dim.dxf.unprotected_set("extrusion", Vec3(0.0, 0.0, 0.0))
    elif crash_probe in {"nan_defpoint_override_99999_audit", "nan_caller_args_audit"}:
        dim.dxf.unprotected_set("defpoint2", Vec3(math.nan, 0.0, 0.0))
        dim.dxf.text = "99999"
        _set_rendered_block_text(dim, "99999")
        doc.saveas(built.output_path)
        re_doc = ezdxf.readfile(built.output_path)
        re_dim = re_doc.entitydb[built.dimension_handle_by_cross_validation_id["cv-1"]]
        if crash_probe == "nan_defpoint_override_99999_audit":
            assert audit_dimension_truth(re_doc, re_dim) != []
        else:
            assert audit_dimension_truth(re_doc, re_dim, expected_measurement=math.nan) != []
            assert audit_dimension_truth(re_doc, re_dim, expected_measurement=100.0, tolerance_mm=math.nan) != []
        return

    doc.saveas(built.output_path)
    strict = review_dxf_with_dimension_line_integrity(built)
    semantic = review_dxf(built, verify_dimension_truth=True)
    assert not strict.passed
    assert strict.qualification in {"FAILED", "UNKNOWN"}
    assert not semantic.passed


@pytest.mark.parametrize(
    "r9_probe",
    [
        "escaped_backslash_percent_u_command_synthesis",
        "escaped_backslash_percent_o_command_synthesis",
        "triple_percent_fusion_percent_k",
        "caret_bel_07_in_mtext",
        "caret_fs_1c_in_mtext",
        "caret_gs_1d_in_mtext",
        "caret_us_1f_in_mtext",
        "caret_vt_0b_in_mtext",
        "caret_ff_0c_in_mtext",
        "c1_nel_85_in_mtext",
        "native_text_us_1f_control_whitespace",
    ],
)
def test_r9_prelex_percent_command_synthesis_and_control_escapes_stay_non_qualified(
    tmp_path: Path, r9_probe: str
) -> None:
    built, doc, dim = _explicit_truth_control(tmp_path / r9_probe)
    if r9_probe == "escaped_backslash_percent_u_command_synthesis":
        dim.dxf.text = r"\%%uA1;100"
        _set_rendered_block_text(dim, r"\%%uA1;100")
    elif r9_probe == "escaped_backslash_percent_o_command_synthesis":
        dim.dxf.text = r"\%%oW1;100"
        _set_rendered_block_text(dim, r"\%%oW1;100")
    elif r9_probe == "triple_percent_fusion_percent_k":
        from dxf_builder_lib._dimension_truth import _has_disallowed_percent_code

        assert _has_disallowed_percent_code("%%%%%u%%%k100") is True
        return
    elif r9_probe == "caret_bel_07_in_mtext":
        dim.dxf.text = "100^G"
        _set_rendered_block_text(dim, "100^G")
    elif r9_probe == "caret_fs_1c_in_mtext":
        _set_rendered_block_text(dim, r"^\100")
    elif r9_probe == "caret_gs_1d_in_mtext":
        _set_rendered_block_text(dim, r"^]100")
    elif r9_probe == "caret_us_1f_in_mtext":
        _set_rendered_block_text(dim, r"^_100")
    elif r9_probe == "caret_vt_0b_in_mtext":
        _set_rendered_block_text(dim, "^K100")
    elif r9_probe == "caret_ff_0c_in_mtext":
        _set_rendered_block_text(dim, "^L100")
    elif r9_probe == "c1_nel_85_in_mtext":
        _set_rendered_block_text(dim, "\x85100")
    else:
        blk = doc.blocks.get(dim.dxf.geometry)
        for ent in list(blk):
            if ent.dxftype() == "MTEXT":
                blk.delete_entity(ent)
        blk.add_text("\x1f100", dxfattribs={"height": 1.0, "insert": (50.0, 20.0), "style": "Standard"})

    doc.saveas(built.output_path)
    strict = review_dxf_with_dimension_line_integrity(built)
    semantic = review_dxf(built, verify_dimension_truth=True)
    assert not strict.passed
    assert strict.qualification in {"FAILED", "UNKNOWN"}
    assert not semantic.passed


def test_r9_valid_percent_toggles_symbols_and_tabs_remain_qualified(tmp_path: Path) -> None:
    for idx, (dim_text, mtext_val) in enumerate(
        [
            ("<>", "%%u100%%u"),
            ("%%c<>", "%%c100"),
            ("<>", "^I100"),
            ("<>", "^J100"),
        ]
    ):
        built, doc, dim = _explicit_truth_control(tmp_path / f"pos_{idx}")
        dim.dxf.text = dim_text
        _set_rendered_block_text(dim, mtext_val)
        doc.saveas(built.output_path)
        strict = review_dxf_with_dimension_line_integrity(built)
        assert strict.passed, f"Expected QUALIFIED for ({dim_text!r}, {mtext_val!r}): {strict}"
        assert strict.qualification == "QUALIFIED"
