"""
Standalone Clean-Room Transfer Oracle for REA-023: Native Dimension Placement Collision Avoidance.

Verifies:
1. Exact Measurement Invariant: In all tested synthetic fixtures, dimension line length
   equals measured physical segment length exactly (measurement_error == 0.0).
2. Deterministic Repeatability: Repeated execution of the multi-lane dual-side candidate policy
   yields identical coordinates (repeatability == 100.0%).
3. Obstacle Avoidance via Dual-Side Search: On Fixture 6 (geometry obstacle on +normal side)
   and Fixture 7 (annotation text note on +normal side), the candidate policy selects the
   unobstructed side (-normal, side=-1), resolving baseline collisions.
4. Parallel Stacking via Multi-Lane Search: On Fixture 4 (two nearby parallel stepped edges),
   the candidate policy selects distinct non-overlapping offset lanes, eliminating baseline
   dimension-to-dimension text/line collision.
5. Boundary Enclosure: On Fixture 9 (measured edge at y=490 near ymax=500 sheet border),
   the candidate policy flips side inward to keep dimension text within sheet bounds, whereas
   the baseline fixed offset places text out-of-bounds.

Evidence Tier: BOUNDED_SYNTHETIC_RESEARCH_ORACLE
Note: Standalone prototype oracle; not a call through production builder owners.
"""

from __future__ import annotations

import math
import sys
from typing import List, Tuple

from benchmark_dimension_placement import (
    Scene,
    MeasuredSegment,
    AnnotationObstacle,
    compute_dimension_geometry,
    place_dimensions_baseline,
    place_dimensions_candidate,
    evaluate_placement_scene,
    create_fixtures,
)


def run_oracle_tests():
    print("=== Running REA-023 Native Dimension Placement Collision Avoidance Transfer Oracle ===")

    scenes = {sc.name: sc for sc in create_fixtures()}

    # -----------------------------------------------------------------------
    # Test 1: Exact measurement truth preservation across all tested fixtures
    # -----------------------------------------------------------------------
    max_measurement_error = 0.0
    for name, sc in scenes.items():
        placed = place_dimensions_candidate(sc)
        for p in placed:
            err = abs(p.dimension_length - p.measured_length)
            if err > max_measurement_error:
                max_measurement_error = err

    assert max_measurement_error < 1e-9, f"Measurement error exceeded zero: {max_measurement_error}"
    print(f"Test 1 PASS: Exact measurement length invariant verified across all 10 fixtures (max error = {max_measurement_error:.6f} mm).")

    # -----------------------------------------------------------------------
    # Test 2: Deterministic repeatability across multiple runs
    # -----------------------------------------------------------------------
    sc4 = scenes["fixture_4_two_nearby_parallel"]
    run1 = place_dimensions_candidate(sc4)
    run2 = place_dimensions_candidate(sc4)
    run3 = place_dimensions_candidate(sc4)

    assert len(run1) == len(run2) == len(run3) == 2, "Unexpected dimension count on Fixture 4"
    for p1, p2, p3 in zip(run1, run2, run3):
        assert p1.side == p2.side == p3.side, "Side placement non-deterministic!"
        assert p1.lane_index == p2.lane_index == p3.lane_index, "Lane selection non-deterministic!"
        assert abs(p1.base[0] - p2.base[0]) < 1e-9 and abs(p1.base[1] - p2.base[1]) < 1e-9, "Base coordinate non-deterministic!"
        assert abs(p1.base[0] - p3.base[0]) < 1e-9 and abs(p1.base[1] - p3.base[1]) < 1e-9, "Base coordinate non-deterministic!"
    print("Test 2 PASS: Deterministic repeatability verified across repeated runs on Fixture 4 (100.0% coordinate match).")

    # -----------------------------------------------------------------------
    # Test 3: Dual-side obstacle avoidance on Fixtures 6 and 7
    # -----------------------------------------------------------------------
    # Fixture 6: Model geometry obstacle on +normal side
    sc6 = scenes["fixture_6_one_side_blocked_by_geometry"]
    base6 = place_dimensions_baseline(sc6)
    cand6 = place_dimensions_candidate(sc6)
    eval_base6 = evaluate_placement_scene(sc6, base6, "Baseline")
    eval_cand6 = evaluate_placement_scene(sc6, cand6, "Candidate")

    assert eval_base6.collision_count >= 1, "Baseline was expected to collide with obstacle pocket on Fixture 6!"
    assert eval_cand6.collision_count == 0, f"Candidate failed to avoid obstacle pocket on Fixture 6 (collisions: {eval_cand6.collision_count})!"
    assert cand6[0].side == -1, f"Candidate was expected to flip to side=-1 on Fixture 6, got side={cand6[0].side}"
    print(f"Test 3A PASS: Fixture 6 baseline had {eval_base6.collision_count} collisions on +normal side; candidate selected side=-1 with 0 collisions.")

    # Fixture 7: Text note obstacle on +normal side
    sc7 = scenes["fixture_7_one_side_blocked_by_annotation"]
    base7 = place_dimensions_baseline(sc7)
    cand7 = place_dimensions_candidate(sc7)
    eval_base7 = evaluate_placement_scene(sc7, base7, "Baseline")
    eval_cand7 = evaluate_placement_scene(sc7, cand7, "Candidate")

    assert eval_base7.collision_count >= 1, "Baseline was expected to collide with text note on Fixture 7!"
    assert eval_cand7.collision_count == 0, f"Candidate failed to avoid text note on Fixture 7 (collisions: {eval_cand7.collision_count})!"
    assert cand7[0].side == -1, f"Candidate was expected to flip to side=-1 on Fixture 7, got side={cand7[0].side}"
    print(f"Test 3B PASS: Fixture 7 baseline had {eval_base7.collision_count} collisions on +normal side; candidate selected side=-1 with 0 collisions.")

    # -----------------------------------------------------------------------
    # Test 4: Multi-lane stacking separation on Fixture 4
    # -----------------------------------------------------------------------
    sc4 = scenes["fixture_4_two_nearby_parallel"]
    base4 = place_dimensions_baseline(sc4)
    cand4 = place_dimensions_candidate(sc4)
    eval_base4 = evaluate_placement_scene(sc4, base4, "Baseline")
    eval_cand4 = evaluate_placement_scene(sc4, cand4, "Candidate")

    assert eval_base4.collision_count >= 1, "Baseline was expected to have parallel lane collision on Fixture 4!"
    assert eval_cand4.collision_count == 0, f"Candidate failed to resolve parallel collision on Fixture 4 (collisions: {eval_cand4.collision_count})!"
    # Verify candidate dimensions do not share identical overlapping (side, lane)
    d1, d2 = cand4[0], cand4[1]
    assert (d1.side != d2.side) or (d1.lane_index != d2.lane_index), "Candidate placed parallel dimensions in conflicting lane!"
    print(f"Test 4 PASS: Fixture 4 baseline had {eval_base4.collision_count} collisions; candidate separated parallel dimensions into non-conflicting lanes/sides (0 collisions).")

    # -----------------------------------------------------------------------
    # Test 5: Boundary enclosure on Fixture 9
    # -----------------------------------------------------------------------
    sc9 = scenes["fixture_9_close_to_sheet_boundary"]
    base9 = place_dimensions_baseline(sc9)
    cand9 = place_dimensions_candidate(sc9)
    eval_base9 = evaluate_placement_scene(sc9, base9, "Baseline")
    eval_cand9 = evaluate_placement_scene(sc9, cand9, "Candidate")

    assert eval_base9.collision_count >= 1, "Baseline was expected to escape sheet bounds on Fixture 9!"
    assert eval_cand9.collision_count == 0, f"Candidate failed to stay inside sheet bounds on Fixture 9 (collisions: {eval_cand9.collision_count})!"
    assert cand9[0].side == -1, f"Candidate was expected to flip inward to side=-1 on Fixture 9, got side={cand9[0].side}"
    print(f"Test 5 PASS: Fixture 9 baseline escaped top sheet border (out-of-bounds); candidate flipped inward to side=-1 with 0 boundary collisions.")

    print("\nALL 5 ORACLE TESTS PASSED (100% Success). Oracle verified.")


if __name__ == "__main__":
    run_oracle_tests()
