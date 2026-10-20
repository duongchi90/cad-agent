"""
Pytest Test Oracles for Batch M1: Cleanroom Mechanical Capabilities.

Covers:
1. HoleCallout (ASME Y14.5 / ISO formatting, Unicode symbols, reverse parser, edge cases)
2. BoltCircle (Polar array coordinates, chordal/circumferential pitch, centroid identity, CircleIR)
3. CenterlineBisector (Parallel overlap projection, separation, ΔL extension, non-parallel/collinear rejection)
4. SlotGenerator (Obround 4 tangent vertices, exact G1 continuity, analytical area & perimeter)
5. IsoToleranceFit (ISO 286 deviations EI, ES, ei, es, clearance/transition/interference classification)
"""

from __future__ import annotations

import math
import pytest

from cad_agent.cleanroom_mechanical import (
    SYM_CBORE,
    SYM_CSINK,
    SYM_DEPTH,
    SYM_DIA,
    BoltCircle,
    CenterlineBisector,
    CircleIR,
    FitClassification,
    HoleCallout,
    HoleType,
    IsoToleranceFit,
    Point2D,
    SlotGenerator,
)


# =============================================================================
# 1. HOLE CALLOUT ORACLES
# =============================================================================


class TestHoleCallout:
    def test_unicode_constants_exact(self) -> None:
        assert SYM_DIA == "\u2300"
        assert SYM_CBORE == "\u2334"
        assert SYM_CSINK == "\u2335"
        assert SYM_DEPTH == "\u21a7"

    def test_simple_thru_hole(self) -> None:
        hc = HoleCallout(diameter=6.5, is_thru=True, quantity=1)
        assert hc.hole_type == HoleType.SIMPLE
        formatted = hc.format()
        assert formatted == "\u23006.5 THRU"
        parsed = HoleCallout.parse(formatted)
        assert parsed == hc

    def test_repeated_blind_hole(self) -> None:
        hc = HoleCallout(diameter=8.0, is_thru=False, depth=15.25, quantity=4)
        formatted = hc.format()
        assert formatted == "4X \u23008 \u21a715.25"
        parsed = HoleCallout.parse(formatted)
        assert parsed == hc

    def test_counterbore_thru_and_blind_callout(self) -> None:
        hc_thru = HoleCallout(
            diameter=6.6,
            is_thru=True,
            quantity=6,
            cbore_dia=11.0,
            cbore_depth=6.5,
        )
        assert hc_thru.hole_type == HoleType.COUNTERBORE
        expected_thru = "6X \u23006.6 THRU\n\u2334\u230011 \u21a76.5"
        assert hc_thru.format() == expected_thru
        assert HoleCallout.parse(expected_thru) == hc_thru

        hc_blind = HoleCallout(
            diameter=5.0,
            is_thru=False,
            depth=20.0,
            quantity=2,
            cbore_dia=9.5,
            cbore_depth=5.4,
        )
        expected_blind = "2X \u23005 \u21a720\n\u2334\u23009.5 \u21a75.4"
        assert hc_blind.format() == expected_blind
        assert HoleCallout.parse(expected_blind) == hc_blind

    def test_countersink_callout_and_roundtrip(self) -> None:
        hc = HoleCallout(
            diameter=4.5,
            is_thru=True,
            quantity=8,
            csink_dia=9.0,
            csink_angle_deg=82.0,
        )
        assert hc.hole_type == HoleType.COUNTERSINK
        expected = "8X \u23004.5 THRU\n\u2335\u23009 X 82\u00b0"
        assert hc.format() == expected
        assert HoleCallout.parse(expected) == hc

    def test_threaded_hole_callout(self) -> None:
        hc = HoleCallout(
            diameter=6.8,
            is_thru=False,
            depth=16.0,
            quantity=4,
            thread_spec="M8x1.25 - 6H",
        )
        expected = "4X \u23006.8 \u21a716 M8x1.25 - 6H"
        assert hc.format() == expected
        assert HoleCallout.parse(expected) == hc

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"diameter": 0.0},
            {"diameter": -5.0},
            {"diameter": float("nan")},
            {"diameter": float("inf")},
            {"diameter": 5.0, "is_thru": True, "depth": 10.0},
            {"diameter": 5.0, "is_thru": False, "depth": None},
            {"diameter": 5.0, "is_thru": False, "depth": -1.0},
            {"diameter": 5.0, "quantity": 0},
            {"diameter": 5.0, "quantity": True},
            {"diameter": 10.0, "cbore_dia": 8.0, "cbore_depth": 4.0},
            {"diameter": 10.0, "cbore_dia": 10.0, "cbore_depth": 4.0},
            {
                "diameter": 10.0,
                "is_thru": False,
                "depth": 10.0,
                "cbore_dia": 16.0,
                "cbore_depth": 10.0,
            },
            {"diameter": 10.0, "csink_dia": 9.0, "csink_angle_deg": 90.0},
            {"diameter": 10.0, "csink_dia": 15.0, "csink_angle_deg": 180.0},
            {
                "diameter": 10.0,
                "cbore_dia": 15.0,
                "cbore_depth": 4.0,
                "csink_dia": 15.0,
                "csink_angle_deg": 90.0,
            },
        ],
    )
    def test_invalid_hole_callout_raises(self, kwargs: dict) -> None:
        with pytest.raises(ValueError):
            HoleCallout(**kwargs)

    @pytest.mark.parametrize(
        "bad_str",
        [
            "",
            "   ",
            "10.0 THRU",
            "\u230010",
            "\u230010 THRU\nINVALID LINE",
            "\u230010 THRU\n\u2334\u230015 \u21a75\nEXTRA LINE",
        ],
    )
    def test_invalid_parse_strings_raise(self, bad_str: str) -> None:
        with pytest.raises(ValueError):
            HoleCallout.parse(bad_str)


# =============================================================================
# 2. BOLT CIRCLE ORACLES
# =============================================================================


class TestBoltCircle:
    def test_six_hole_bolt_circle_analytical_oracle(self) -> None:
        # For N=6, chordal pitch equals radius R = BCD / 2
        center = (12.5, -7.25)
        bcd = 100.0
        hole_dia = 10.0
        res = BoltCircle.solve(
            center=center, bcd=bcd, hole_dia=hole_dia, num_holes=6, start_angle_deg=30.0
        )

        assert res.num_holes == 6
        assert math.isclose(res.bolt_circle_radius, 50.0, abs_tol=1e-12)
        assert math.isclose(res.angular_pitch_deg, 60.0, abs_tol=1e-12)
        assert math.isclose(res.chordal_pitch, 50.0, abs_tol=1e-12)
        assert math.isclose(res.circumferential_pitch, (math.pi * 100.0) / 6.0, abs_tol=1e-12)
        assert math.isclose(res.min_ligament, 40.0, abs_tol=1e-12)

        # Centroid identity: average of equispaced polar points for N >= 2 must equal bolt circle center
        assert math.isclose(res.centroid.x, center[0], abs_tol=1e-12)
        assert math.isclose(res.centroid.y, center[1], abs_tol=1e-12)

        # Verify each CircleIR lies exactly at R=50 and adjacent distance = chordal_pitch
        assert len(res.circles) == 6
        for i, c_ir in enumerate(res.circles):
            assert isinstance(c_ir, CircleIR)
            assert c_ir.index == i
            assert math.isclose(c_ir.diameter, hole_dia, abs_tol=1e-12)
            assert math.isclose(c_ir.center.distance_to(Point2D(*center)), 50.0, abs_tol=1e-12)
            next_c = res.circles[(i + 1) % 6]
            assert math.isclose(
                c_ir.center.distance_to(next_c.center), res.chordal_pitch, abs_tol=1e-12
            )

    def test_four_hole_quadrant_positions(self) -> None:
        res = BoltCircle.solve(
            center=(0.0, 0.0), bcd=200.0, hole_dia=16.0, num_holes=4, start_angle_deg=0.0
        )
        expected_pts = [(100.0, 0.0), (0.0, 100.0), (-100.0, 0.0), (0.0, -100.0)]
        for c_ir, (ex, ey) in zip(res.circles, expected_pts):
            assert math.isclose(c_ir.center.x, ex, abs_tol=1e-12)
            assert math.isclose(c_ir.center.y, ey, abs_tol=1e-12)
        assert math.isclose(res.chordal_pitch, 200.0 * math.sin(math.pi / 4.0), abs_tol=1e-12)

    def test_single_hole_edge_case(self) -> None:
        res = BoltCircle.solve(
            center=(0.0, 0.0), bcd=50.0, hole_dia=8.0, num_holes=1, start_angle_deg=90.0
        )
        assert len(res.circles) == 1
        assert math.isclose(res.circles[0].center.x, 0.0, abs_tol=1e-12)
        assert math.isclose(res.circles[0].center.y, 25.0, abs_tol=1e-12)
        assert res.chordal_pitch == 0.0
        assert math.isinf(res.min_ligament)

    def test_overlapping_holes_rejected_by_default(self) -> None:
        # N=4, BCD=20 -> chordal_pitch = 14.142 < hole_dia=15
        with pytest.raises(ValueError, match="overlap"):
            BoltCircle.solve(center=(0.0, 0.0), bcd=20.0, hole_dia=15.0, num_holes=4)

    @pytest.mark.parametrize(
        "center,bcd,hole_dia,num_holes,start_ang",
        [
            ((float("nan"), 0.0), 100.0, 10.0, 4, 0.0),
            ((0.0, 0.0), -100.0, 10.0, 4, 0.0),
            ((0.0, 0.0), 100.0, 0.0, 4, 0.0),
            ((0.0, 0.0), 100.0, 10.0, 0, 0.0),
            ((0.0, 0.0), 100.0, 10.0, 4, float("inf")),
        ],
    )
    def test_invalid_bolt_circle_inputs(self, center, bcd, hole_dia, num_holes, start_ang) -> None:
        with pytest.raises(ValueError):
            BoltCircle.solve(center, bcd, hole_dia, num_holes, start_ang)


# =============================================================================
# 3. CENTERLINE BISECTOR ORACLES
# =============================================================================


class TestCenterlineBisector:
    def test_horizontal_parallel_segments_with_extension(self) -> None:
        # Seg 1: y=0, x in [0, 100]
        # Seg 2: y=20, x in [20, 120] -> overlap x in [20, 100] (length 80), mid y = 10
        res = CenterlineBisector.compute(
            seg1_start=(0.0, 0.0),
            seg1_end=(100.0, 0.0),
            seg2_start=(20.0, 20.0),
            seg2_end=(120.0, 20.0),
            delta_l=5.0,
        )
        assert math.isclose(res.separation_distance, 20.0, abs_tol=1e-12)
        assert math.isclose(res.overlap_length, 80.0, abs_tol=1e-12)
        assert math.isclose(res.unextended_bisector.length, 80.0, abs_tol=1e-12)
        assert math.isclose(res.bisector.length, 90.0, abs_tol=1e-12)

        assert math.isclose(res.bisector.start.x, 15.0, abs_tol=1e-12)
        assert math.isclose(res.bisector.start.y, 10.0, abs_tol=1e-12)
        assert math.isclose(res.bisector.end.x, 105.0, abs_tol=1e-12)
        assert math.isclose(res.bisector.end.y, 10.0, abs_tol=1e-12)
        assert math.isclose(res.midpoint.x, 60.0, abs_tol=1e-12)
        assert math.isclose(res.midpoint.y, 10.0, abs_tol=1e-12)

    def test_antiparallel_rotated_segments_3_4_5_triangle(self) -> None:
        # Direction u = (0.8, 0.6), normal n = (-0.6, 0.8)
        # Seg 1: from (0,0) to (80, 60) (L=100)
        # Seg 2: shifted by +10 along n -> (-6, 8) to (74, 68), reversed orientation!
        res = CenterlineBisector.compute(
            seg1_start=(0.0, 0.0),
            seg1_end=(80.0, 60.0),
            seg2_start=(74.0, 68.0),
            seg2_end=(-6.0, 8.0),
            delta_l=10.0,
        )
        assert math.isclose(res.separation_distance, 10.0, abs_tol=1e-12)
        assert math.isclose(res.overlap_length, 100.0, abs_tol=1e-12)
        assert math.isclose(res.bisector.length, 120.0, abs_tol=1e-12)
        # Midpoint should be at (40, 30) + 5 * (-0.6, 0.8) = (37, 34)
        assert math.isclose(res.midpoint.x, 37.0, abs_tol=1e-12)
        assert math.isclose(res.midpoint.y, 34.0, abs_tol=1e-12)

    def test_non_parallel_segments_rejected(self) -> None:
        with pytest.raises(ValueError, match="not parallel"):
            CenterlineBisector.compute((0.0, 0.0), (10.0, 0.0), (0.0, 5.0), (10.0, 5.1))

    def test_collinear_segments_rejected(self) -> None:
        with pytest.raises(ValueError, match="collinear"):
            CenterlineBisector.compute((0.0, 0.0), (10.0, 0.0), (2.0, 0.0), (12.0, 0.0))

    def test_disjoint_projection_segments_rejected(self) -> None:
        with pytest.raises(ValueError, match="overlapping projection"):
            CenterlineBisector.compute((0.0, 0.0), (10.0, 0.0), (15.0, 5.0), (25.0, 5.0))


# =============================================================================
# 4. SLOT GENERATOR ORACLES
# =============================================================================


class TestSlotGenerator:
    def test_slot_geometry_area_perimeter_and_g1_continuity(self) -> None:
        # Center=(10, 20), L_c=30, W=12 (R=6), angle=37 deg
        slot = SlotGenerator.from_center_to_center(
            center=(10.0, 20.0),
            center_distance=30.0,
            width=12.0,
            angle_deg=37.0,
        )
        expected_area = 12.0 * 30.0 + math.pi * 6.0**2
        expected_perim = 2.0 * 30.0 + math.pi * 12.0

        assert math.isclose(slot.overall_length, 42.0, abs_tol=1e-12)
        assert math.isclose(slot.area, expected_area, abs_tol=1e-12)
        assert math.isclose(slot.perimeter, expected_perim, abs_tol=1e-12)
        assert slot.max_g1_tangent_error_rad < 1e-14

        # Verify that arc endpoints match the 4 tangent vertices exactly (C0 continuity)
        v1, v2, v3, v4 = slot.tangent_vertices
        arc_right, arc_left = slot.end_arcs
        assert v2.distance_to(arc_right.start_point) < 1e-12
        assert v3.distance_to(arc_right.end_point) < 1e-12
        assert v4.distance_to(arc_left.start_point) < 1e-12
        assert v1.distance_to(arc_left.end_point) < 1e-12

    def test_slot_from_overall_length_equivalence(self) -> None:
        s1 = SlotGenerator.from_center_to_center(
            (0.0, 0.0), center_distance=25.0, width=10.0, angle_deg=0.0
        )
        s2 = SlotGenerator.from_overall_length(
            (0.0, 0.0), overall_length=35.0, width=10.0, angle_deg=0.0
        )
        assert math.isclose(s1.area, s2.area, abs_tol=1e-12)
        assert math.isclose(s1.perimeter, s2.perimeter, abs_tol=1e-12)
        assert s1.tangent_vertices == s2.tangent_vertices

    def test_invalid_slot_parameters_raise(self) -> None:
        with pytest.raises(ValueError, match="strictly greater than width"):
            SlotGenerator.from_overall_length((0.0, 0.0), overall_length=10.0, width=10.0)
        with pytest.raises(ValueError):
            SlotGenerator.from_center_to_center((0.0, 0.0), center_distance=-5.0, width=10.0)


# =============================================================================
# 5. ISO 286 TOLERANCE FIT ORACLES
# =============================================================================


class TestIsoToleranceFit:
    def test_clearance_fit_25_H7_g6_exact_iso286_oracle(self) -> None:
        # Nominal 25 mm (step 18..30 mm):
        # H7: EI = 0, ES = +0.021 mm (+21 µm)
        # g6: es = -0.007 mm (-7 µm), IT6 = 13 µm -> ei = -0.020 mm (-20 µm)
        fit = IsoToleranceFit.evaluate_fit(25.0, "H7", "g6")
        assert fit.fit_type == FitClassification.CLEARANCE
        assert math.isclose(fit.EI, 0.0, abs_tol=1e-9)
        assert math.isclose(fit.ES, 0.021, abs_tol=1e-9)
        assert math.isclose(fit.es, -0.007, abs_tol=1e-9)
        assert math.isclose(fit.ei, -0.020, abs_tol=1e-9)
        assert math.isclose(fit.min_clearance_mm, 0.007, abs_tol=1e-9)
        assert math.isclose(fit.max_clearance_mm, 0.041, abs_tol=1e-9)

    def test_sliding_clearance_fit_50_H7_h6_oracle(self) -> None:
        # Nominal 50 mm (step 30..50 mm):
        # H7: EI = 0, ES = +0.025 mm
        # h6: es = 0, ei = -0.016 mm
        fit = IsoToleranceFit.evaluate_fit(50.0, "H7", "h6")
        assert fit.fit_type == FitClassification.CLEARANCE
        assert math.isclose(fit.min_clearance_mm, 0.0, abs_tol=1e-9)
        assert math.isclose(fit.max_clearance_mm, 0.041, abs_tol=1e-9)

    def test_transition_fit_30_H7_k6_oracle(self) -> None:
        # Nominal 30 mm (step 18..30 mm):
        # H7: EI = 0, ES = +0.021 mm
        # k6: ei = +0.002 mm (+2 µm), IT6 = 13 µm -> es = +0.015 mm (+15 µm)
        fit = IsoToleranceFit.evaluate_fit(30.0, "H7", "k6")
        assert fit.fit_type == FitClassification.TRANSITION
        assert math.isclose(fit.ei, 0.002, abs_tol=1e-9)
        assert math.isclose(fit.es, 0.015, abs_tol=1e-9)
        assert math.isclose(fit.max_clearance_mm, 0.019, abs_tol=1e-9)
        assert math.isclose(fit.min_clearance_mm, -0.015, abs_tol=1e-9)

    def test_interference_press_fit_40_H7_p6_oracle(self) -> None:
        # Nominal 40 mm (step 30..50 mm):
        # H7: EI = 0, ES = +0.025 mm
        # p6: ei = +0.026 mm (+26 µm), IT6 = 16 µm -> es = +0.042 mm (+42 µm)
        fit = IsoToleranceFit.evaluate_fit(40.0, "H7", "p6")
        assert fit.fit_type == FitClassification.INTERFERENCE
        assert math.isclose(fit.ei, 0.026, abs_tol=1e-9)
        assert math.isclose(fit.es, 0.042, abs_tol=1e-9)
        assert math.isclose(fit.max_clearance_mm, -0.001, abs_tol=1e-9)
        assert math.isclose(fit.min_clearance_mm, -0.042, abs_tol=1e-9)
        assert math.isclose(fit.min_interference_mm, 0.001, abs_tol=1e-9)
        assert math.isclose(fit.max_interference_mm, 0.042, abs_tol=1e-9)

    def test_symmetrical_js_fit_and_shaft_basis_hole(self) -> None:
        # 20 mm H7/js6 -> IT6 = 13 µm -> es = +6.5 µm, ei = -6.5 µm
        fit_js = IsoToleranceFit.evaluate_fit(20.0, "H7", "js6")
        assert fit_js.fit_type == FitClassification.TRANSITION
        assert math.isclose(fit_js.es, 0.0065, abs_tol=1e-9)
        assert math.isclose(fit_js.ei, -0.0065, abs_tol=1e-9)

        # Shaft-basis P7/h6 at 40 mm:
        # p shaft ei = +26 µm, Delta(IT7 - IT6) = 25 - 16 = 9 µm -> ES(P7) = -26 + 9 = -17 µm, EI(P7) = -42 µm
        fit_sb = IsoToleranceFit.evaluate_fit(40.0, "P7", "h6")
        assert fit_sb.fit_type == FitClassification.INTERFERENCE
        assert math.isclose(fit_sb.ES, -0.017, abs_tol=1e-9)
        assert math.isclose(fit_sb.EI, -0.042, abs_tol=1e-9)

    @pytest.mark.parametrize(
        "dia,h_sym,s_sym",
        [
            (0.0, "H7", "g6"),
            (501.0, "H7", "g6"),
            (float("nan"), "H7", "g6"),
            (25.0, "h7", "g6"),  # lowercase hole rejected
            (25.0, "H7", "G6"),  # uppercase shaft rejected
            (25.0, "H3", "g6"),  # unsupported IT3 grade
            (25.0, "Z7", "g6"),  # unsupported hole letter
        ],
    )
    def test_invalid_iso_fit_inputs_raise(self, dia: float, h_sym: str, s_sym: str) -> None:
        with pytest.raises(ValueError):
            IsoToleranceFit.evaluate_fit(dia, h_sym, s_sym)
