from __future__ import annotations

import pytest

from cad_agent.marine_cross_view import (
    CrossViewCheckResult,
    GridWaterlineLabel,
    LinesCurve,
    LinesLine,
    LinesText,
    LinesViewRegion,
    verify_lines_plan_cross_view,
)


def _symmetric_lines_plan(
    *,
    lpp: float = 20000.0,
    half_b_wl: tuple[float, ...] = (1200.0, 2000.0, 2500.0),
    wl_zs: tuple[float, ...] = (0.0, 500.0, 1000.0, 1500.0),
    bp_shift_x: float = 0.0,
    hb_scale: float = 1.0,
    include_datum_labels: bool = True,
    declared_b: float | None = 5000.0,
    declared_lpp: float | None = 20000.0,
    base_keel_offset: float = 0.0,
):
    regions = [
        LinesViewRegion(view_type="sheer", bbox=(0.0, 6000.0, lpp, 8000.0)),
        LinesViewRegion(view_type="half_breadth", bbox=(0.0, 0.0, lpp, 3000.0)),
        LinesViewRegion(view_type="body_plan", bbox=(23000.0, 0.0, 29000.0, 2000.0)),
    ]
    bp_cl_x = 26000.0
    lines = [
        # HB CL + AP/FP stations
        LinesLine((0.0, 0.0), (lpp, 0.0), layer="CL", is_dashed=True),
        LinesLine((0.0, 0.0), (0.0, 2800.0), layer="STATION"),
        LinesLine((lpp, 0.0), (lpp, 2800.0), layer="STATION"),
        # BP CL + waterlines
        LinesLine((bp_cl_x, 0.0), (bp_cl_x, 1800.0), layer="CL", is_dashed=True),
    ]
    for z in wl_zs:
        lines.append(LinesLine((23500.0, z), (28500.0, z), layer="WL"))
        lines.append(LinesLine((0.0, 6000.0 + z), (lpp, 6000.0 + z), layer="WL"))

    curves = []
    # HB waterlines
    for idx, hb_w in enumerate(half_b_wl):
        y_mid = hb_w * hb_scale
        pts = tuple(
            (x, y_mid if idx < len(half_b_wl) else 0.0)
            for x in (0.0, 0.25 * lpp, 0.50 * lpp, 0.75 * lpp, lpp)
        )
        # Tapering at ends, full breadth in middle
        pts = (
            (0.0, 0.1 * y_mid),
            (0.25 * lpp, 0.8 * y_mid),
            (0.50 * lpp, y_mid),
            (0.75 * lpp, 0.8 * y_mid),
            (lpp, 0.1 * y_mid),
        )
        curves.append(LinesCurve(points=pts, layer="HULL_WL"))

    # BP transverse frame curve rising through wl_zs[1:] matching half_b_wl
    bp_stbd = [(bp_cl_x, base_keel_offset)] + [
        (bp_cl_x + (hb_w + bp_shift_x), z) for z, hb_w in zip(wl_zs[1:], half_b_wl)
    ]
    bp_port = [(bp_cl_x - (hb_w + bp_shift_x), z) for z, hb_w in zip(wl_zs[1:], half_b_wl)][::-1] + [
        (bp_cl_x, base_keel_offset)
    ]
    curves.append(LinesCurve(points=tuple(bp_stbd + bp_port[1:]), layer="FRAME"))

    texts: list[LinesText] = []
    if declared_lpp is not None and declared_b is not None:
        texts.append(LinesText(f"Lpp={declared_lpp / 1000.0:.2f}m B={declared_b / 1000.0:.2f}m", (1000.0, 9000.0)))
    if include_datum_labels:
        texts.extend(
            [
                LinesText("CL", (500.0, 50.0)),
                LinesText("WL 1000", (23600.0, 1000.0)),
                LinesText("BASE", (23400.0, 0.0)),
            ]
        )
    else:
        texts.extend(
            [
                LinesText("General Note A", (500.0, 50.0)),
                LinesText("General Note B", (23600.0, 1000.0)),
            ]
        )
    return regions, lines, curves, texts


def test_cross_view_consistent_calibrated_passes() -> None:
    regions, lines, curves, texts = _symmetric_lines_plan()
    res = verify_lines_plan_cross_view(regions, lines, curves, texts, insunits=4)
    assert isinstance(res, CrossViewCheckResult)
    assert res.status == "PASS"
    assert res.discrepancies == []
    assert res.principal_dims_mm["Pairs_Compared"] == 3
    assert res.principal_dims_mm["Lpp"] == pytest.approx(20000.0, abs=1e-3)


def test_cross_view_fails_closed_when_unitless_or_missing_datum_labels() -> None:
    regions, lines, curves, texts = _symmetric_lines_plan()
    res_unitless = verify_lines_plan_cross_view(regions, lines, curves, texts, insunits=0)
    assert res_unitless.status == "NOT_MEASURABLE_NO_SCALE"
    assert "UNITLESS_CAD_INSUNITS_0" in res_unitless.discrepancies

    _, _, _, uncalibrated_texts = _symmetric_lines_plan(include_datum_labels=False)
    res_nolbl = verify_lines_plan_cross_view(regions, lines, curves, uncalibrated_texts, insunits=4)
    assert res_nolbl.status == "NOT_MEASURABLE_NO_SCALE"
    assert "MISSING_CALIBRATED_DATUM_LABELS" in res_nolbl.discrepancies


def test_cross_view_rejects_zero_curves_unit_1000x_and_beam_lpp_shifts() -> None:
    regions, lines, curves, texts = _symmetric_lines_plan()

    # 1. Zero curves must never PASS as 0 pairs
    res_zero = verify_lines_plan_cross_view(regions, lines, [], texts, insunits=4)
    assert res_zero.status == "INSUFFICIENT_GEOMETRY"

    # 2. 1000x unit discrepancy between HB (mm) and BP (m -> 0.001x)
    r_m, l_m, c_m, t_m = _symmetric_lines_plan(hb_scale=0.0005, declared_b=None, declared_lpp=None)
    res_1000 = verify_lines_plan_cross_view(r_m, l_m, c_m, t_m, insunits=4)
    assert res_1000.status == "CONFLICT_DETECTED"
    assert any("UNIT_MISMATCH_1000X" in d for d in res_1000.discrepancies)

    # 3. Correlated outward 2-view beam shift (+250mm per side = +500mm beam) caught against declared B
    r_b, l_b, c_b, t_b = _symmetric_lines_plan(
        half_b_wl=(1450.0, 2250.0, 2750.0),
        declared_b=5000.0,
    )
    res_beam = verify_lines_plan_cross_view(r_b, l_b, c_b, t_b, insunits=4)
    assert res_beam.status == "CONFLICT_DETECTED"
    assert any("BEAM_BOUND_MISMATCH" in d for d in res_beam.discrepancies)

    # 4. Baseline keel shift in BP
    r_k, l_k, c_k, t_k = _symmetric_lines_plan(base_keel_offset=200.0)
    res_keel = verify_lines_plan_cross_view(r_k, l_k, c_k, t_k, insunits=4)
    assert res_keel.status == "CONFLICT_DETECTED"
    assert any("BASELINE_MISMATCH" in d for d in res_keel.discrepancies)


def test_cross_view_grid_waterline_and_sheer_hb_lpp_conflicts() -> None:
    regions = [
        LinesViewRegion(view_type="sheer", bbox=(0.0, 6000.0, 20000.0, 8000.0)),
        LinesViewRegion(view_type="half_breadth", bbox=(0.0, 0.0, 20000.0, 3000.0)),
    ]
    curves = [
        LinesCurve(points=((0.0, 6500.0), (10000.0, 6500.0), (18500.0, 6500.0), (19000.0, 6500.0))),
        LinesCurve(points=((0.0, 500.0), (7000.0, 1200.0), (14000.0, 1200.0), (20000.0, 100.0))),
    ]
    res_lpp = verify_lines_plan_cross_view(regions, [], curves, [], insunits=4)
    assert res_lpp.status == "CONFLICT_DETECTED"
    assert any("LPP_CROSS_VIEW_MISMATCH" in d for d in res_lpp.discrepancies)

    r2, l2, c2, t2 = _symmetric_lines_plan()
    grid_labels = [
        GridWaterlineLabel("WL 2000", (1000.0, 6500.0, 1400.0, 6600.0)),
        GridWaterlineLabel("WL 4500", (1000.0, 7500.0, 1400.0, 7600.0)),
        GridWaterlineLabel("WL 2000", (23500.0, 500.0, 23900.0, 600.0)),
        GridWaterlineLabel("WL 4575", (23500.0, 1500.0, 23900.0, 1600.0)),
    ]
    res_grid = verify_lines_plan_cross_view(r2, l2, c2, t2, insunits=4, grid_labels=grid_labels)
    assert res_grid.status == "CONFLICT_DETECTED"
    assert any("waterlines" in d for d in res_grid.discrepancies)


def test_cross_view_parallel_middle_body_split_curves() -> None:
    # Split aft & fwd waterline halves leaving empty [28%..72%] midship gap (parallel middle body)
    lpp = 20000.0
    regions = [
        LinesViewRegion(view_type="half_breadth", bbox=(0.0, 0.0, lpp, 3000.0)),
        LinesViewRegion(view_type="body_plan", bbox=(23000.0, 0.0, 29000.0, 2000.0)),
    ]
    bp_cl_x = 26000.0
    wl_zs = (0.0, 500.0, 1000.0, 1500.0)
    half_b = (1200.0, 2000.0, 2500.0)
    lines = [
        LinesLine((0.0, 0.0), (lpp, 0.0), layer="CL", is_dashed=True),
        LinesLine((0.0, 0.0), (0.0, 2800.0), layer="STATION"),
        LinesLine((lpp, 0.0), (lpp, 2800.0), layer="STATION"),
        LinesLine((bp_cl_x, 0.0), (bp_cl_x, 1800.0), layer="CL", is_dashed=True),
    ] + [LinesLine((23500.0, z), (28500.0, z), layer="WL") for z in wl_zs]
    curves = []
    for hb_w in half_b:
        curves.append(LinesCurve(points=((0.0, 0.1 * hb_w), (1500.0, 0.5 * hb_w), (3000.0, 0.85 * hb_w), (4500.0, hb_w))))
        curves.append(LinesCurve(points=((15500.0, hb_w), (17000.0, 0.85 * hb_w), (18500.0, 0.5 * hb_w), (lpp, 0.1 * hb_w))))
    bp_pts = [(bp_cl_x, 0.0)] + [(bp_cl_x + hb_w, z) for z, hb_w in zip(wl_zs[1:], half_b)]
    curves.append(LinesCurve(points=tuple(bp_pts)))
    texts = [
        LinesText("Lpp=20.0m B=5.0m", (1000.0, 9000.0)),
        LinesText("CL", (500.0, 50.0)),
        LinesText("WL 1000", (23600.0, 1000.0)),
    ]
    res = verify_lines_plan_cross_view(regions, lines, curves, texts, insunits=4)
    assert res.status == "PASS"
    assert res.discrepancies == []
