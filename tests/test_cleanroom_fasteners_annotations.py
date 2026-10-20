"""
test_cleanroom_fasteners_annotations.py
Comprehensive pytest suite for cleanroom fasteners and annotations with analytical oracles and edge cases.
"""

import math
import pytest
from cad_agent.cleanroom_mechanical import Point2D, LineSegment2D, Arc2D
from cad_agent.cleanroom_fasteners_annotations import (
    KeywaySlotParams,
    KeywaySlotHandler,
    KeywaySlotType,
    HexBoltParams,
    HexBoltHandler,
    ThreadRodParams,
    ThreadRodHandler,
    WeldSymbolParams,
    WeldSymbolHandler,
    WeldType,
    SurfaceFinishParams,
    SurfaceFinishHandler,
    MachiningType,
)


class TestKeywaySlot:
    def test_keyway_slot_cross_section_analytical_oracle(self):
        D = 50.0
        w = 12.0
        t1 = 5.0
        rad = D / 2.0
        half_w = w / 2.0
        params = KeywaySlotParams(
            shaft_diameter=D, width=w, depth=t1, slot_type=KeywaySlotType.CROSS_SECTION
        )
        primitives = KeywaySlotHandler.generate(params)
        assert len(primitives) >= 4

        # Verify arc properties
        arcs = [p for p in primitives if isinstance(p, Arc2D)]
        assert len(arcs) == 1
        arc = arcs[0]
        assert math.isclose(arc.radius, rad, abs_tol=1e-9)
        alpha = math.asin(half_w / rad)
        assert math.isclose(arc.start_angle_rad, math.pi / 2.0 + alpha, abs_tol=1e-9)
        assert math.isclose(arc.end_angle_rad, math.pi / 2.0 - alpha, abs_tol=1e-9)

        # Verify floor line
        lines = [p for p in primitives if isinstance(p, LineSegment2D)]
        floor_lines = [l for l in lines if math.isclose(l.start.y, l.end.y, abs_tol=1e-9)]
        assert len(floor_lines) >= 1
        floor = floor_lines[0]
        assert math.isclose(floor.start.x, -half_w, abs_tol=1e-9)
        assert math.isclose(floor.end.x, half_w, abs_tol=1e-9)
        assert math.isclose(floor.start.y, rad - t1, abs_tol=1e-9)

    def test_keyway_slot_top_slot_generation(self):
        params = KeywaySlotParams(
            shaft_diameter=40.0, width=10.0, depth=4.0, slot_type=KeywaySlotType.TOP_SLOT
        )
        primitives = KeywaySlotHandler.generate(params)
        assert len(primitives) >= 4
        arcs = [p for p in primitives if isinstance(p, Arc2D)]
        lines = [p for p in primitives if isinstance(p, LineSegment2D)]
        assert len(arcs) == 2
        assert len(lines) == 2

    @pytest.mark.parametrize(
        "D,w,t1",
        [
            (50.0, 30.0, 5.0),  # w >= 0.6 * D
            (50.0, 31.0, 5.0),  # w > 0.6 * D
            (50.0, 10.0, 25.0),  # t1 >= 0.5 * D
            (50.0, 10.0, 26.0),  # t1 > 0.5 * D
            (-10.0, 5.0, 2.0),  # negative diameter
            (0.0, 5.0, 2.0),  # zero diameter
            (50.0, -5.0, 2.0),  # negative width
            (50.0, 5.0, -2.0),  # negative depth
            (float("nan"), 5.0, 2.0),
            (50.0, float("inf"), 2.0),
        ],
    )
    def test_keyway_slot_validation_raises(self, D, w, t1):
        with pytest.raises((ValueError, TypeError)):
            KeywaySlotParams(shaft_diameter=D, width=w, depth=t1)


class TestHexBolt:
    def test_hex_bolt_analytical_proportions(self):
        d = 12.0
        L = 60.0
        Lt = 30.0
        params = HexBoltParams(nominal_diameter=d, shank_length=L, thread_length=Lt)
        primitives = HexBoltHandler.generate(params)
        assert len(primitives) >= 6

        # Check head height k = 0.7 * d and across-corners e = 2.0 * d
        expected_k = 0.7 * d
        expected_e = 2.0 * d
        assert math.isclose(params.head_height, expected_k, abs_tol=1e-9)
        assert math.isclose(params.across_corners_width, expected_e, abs_tol=1e-9)

        # Centerline check
        centerlines = [
            p for p in primitives if isinstance(p, LineSegment2D) and p.start.x == p.end.x
        ]
        assert len(centerlines) > 0

    @pytest.mark.parametrize(
        "d,L,Lt",
        [
            (10.0, 30.0, 40.0),  # Lt > L
            (0.0, 30.0, 20.0),  # d <= 0
            (10.0, -30.0, 20.0),  # L < 0
            (10.0, 30.0, 0.0),  # Lt <= 0
            (float("nan"), 30.0, 20.0),
            (10.0, float("inf"), 20.0),
        ],
    )
    def test_hex_bolt_validation_raises(self, d, L, Lt):
        with pytest.raises((ValueError, TypeError)):
            HexBoltParams(nominal_diameter=d, shank_length=L, thread_length=Lt)


class TestThreadRod:
    def test_thread_rod_analytical_minor_diameter(self):
        d = 20.0
        L = 100.0
        P = 2.5
        params = ThreadRodParams(major_diameter=d, length=L, pitch=P)
        primitives = ThreadRodHandler.generate(params)
        assert len(primitives) >= 5

        # Check ISO minor diameter dr = d - 1.0825 * P
        expected_dr = d - 1.0825 * P
        lines = [p for p in primitives if isinstance(p, LineSegment2D)]
        assert len(lines) >= 4

    @pytest.mark.parametrize(
        "d,L,P",
        [
            (0.0, 100.0, 2.0),
            (-10.0, 100.0, 2.0),
            (20.0, 0.0, 2.0),
            (20.0, 100.0, 0.0),
            (20.0, 100.0, -1.0),
            (float("nan"), 100.0, 2.0),
            (20.0, float("inf"), 2.0),
        ],
    )
    def test_thread_rod_validation_raises(self, d, L, P):
        with pytest.raises((ValueError, TypeError)):
            ThreadRodParams(major_diameter=d, length=L, pitch=P)


class TestWeldSymbol:
    def test_weld_symbol_fillet_all_around_oracle(self):
        params = WeldSymbolParams(
            origin=Point2D(0.0, 0.0),
            weld_type=WeldType.FILLET,
            reference_length=30.0,
            height=6.0,
            all_around=True,
            process_note="111-MMAW",
        )
        primitives = WeldSymbolHandler.generate(params)
        assert len(primitives) >= 7

        # Check all-around circle exists
        arcs = [p for p in primitives if isinstance(p, Arc2D)]
        assert len(arcs) == 1
        assert math.isclose(arcs[0].radius, 0.4 * 6.0, abs_tol=1e-9)

        # Check leader and reference lines
        lines = [p for p in primitives if isinstance(p, LineSegment2D)]
        assert len(lines) >= 6

    def test_weld_symbol_square_groove(self):
        params = WeldSymbolParams(
            origin=Point2D(10.0, 10.0), weld_type=WeldType.SQUARE_GROOVE, all_around=False
        )
        primitives = WeldSymbolHandler.generate(params)
        assert len(primitives) >= 5
        arcs = [p for p in primitives if isinstance(p, Arc2D)]
        assert len(arcs) == 0

    def test_weld_symbol_invalid_inputs(self):
        with pytest.raises((ValueError, TypeError)):
            WeldSymbolParams(origin=Point2D(0.0, 0.0), reference_length=-10.0)
        with pytest.raises((ValueError, TypeError)):
            WeldSymbolParams(origin=Point2D(0.0, 0.0), height=0.0)


class TestSurfaceFinish:
    def test_surface_finish_removal_required_oracle(self):
        ht = 5.0
        params = SurfaceFinishParams(
            origin=Point2D(0.0, 0.0),
            height=ht,
            roughness_ra=3.2,
            machining_type=MachiningType.REMOVAL_REQUIRED,
        )
        primitives = SurfaceFinishHandler.generate(params)
        assert len(primitives) >= 4

        # Ensure crossbar line exists
        lines = [p for p in primitives if isinstance(p, LineSegment2D)]
        assert len(lines) >= 4

    def test_surface_finish_removal_prohibited_oracle(self):
        ht = 5.0
        params = SurfaceFinishParams(
            origin=Point2D(0.0, 0.0),
            height=ht,
            roughness_ra=1.6,
            machining_type=MachiningType.REMOVAL_PROHIBITED,
        )
        primitives = SurfaceFinishHandler.generate(params)
        assert len(primitives) >= 4

        # Ensure circle arc exists for removal prohibited
        arcs = [p for p in primitives if isinstance(p, Arc2D)]
        assert len(arcs) == 1
        assert math.isclose(arcs[0].radius, 0.5 * ht, abs_tol=1e-9)

    def test_surface_finish_any_machining(self):
        ht = 4.0
        params = SurfaceFinishParams(
            origin=Point2D(0.0, 0.0), height=ht, roughness_ra=6.3, machining_type=MachiningType.ANY
        )
        primitives = SurfaceFinishHandler.generate(params)
        assert len(primitives) >= 3
        arcs = [p for p in primitives if isinstance(p, Arc2D)]
        assert len(arcs) == 0

    def test_surface_finish_invalid_inputs(self):
        with pytest.raises((ValueError, TypeError)):
            SurfaceFinishParams(origin=Point2D(0.0, 0.0), height=-2.0)
        with pytest.raises((ValueError, TypeError)):
            SurfaceFinishParams(origin=Point2D(0.0, 0.0), roughness_ra=float("nan"))
