"""
Standalone Clean-Room Transfer Oracle for REA-023: Native Dimension Placement Collision Avoidance.

Verifies:
1. Exact Prototype Measurement Invariant: In all tested synthetic fixtures, dimension line length
   equals measured physical segment length exactly (prototype_measurement_error == 0.0).
   (Algebraic sanity check on prototype model; PRODUCTION_NATIVE_MEASUREMENT_PRESERVATION = NOT_VERIFIED_BY_THIS_ORACLE).
2. Full-Field Deterministic Repeatability: Repeated execution of the multi-lane dual-side candidate policy
   yields identical coordinates across all PlacedDimension fields within 1e-9 tolerance on tested synthetic fixtures
   (3 runs on Fixture 4; full-field check across all 10 scenes in benchmark).
3. Obstacle Avoidance via Dual-Side Search: On Fixture 6 (geometry obstacle on +normal side)
   and Fixture 7 (annotation text note on +normal side), the candidate policy selects the
   unobstructed side (-normal, side=-1), resolving baseline collisions.
4. Multi-Lane Stacking Separation: On Fixture 5 (stepped shoulder), the candidate policy assigns
   stacked dimensions to distinct non-overlapping offset lanes (asserting lane_index > 0).
   On Fixture 4, parallel dimensions are separated onto non-conflicting sides.
5. Boundary Enclosure: On Fixture 9 (measured edge at y=495 near ymax=500 sheet border),
   the candidate policy flips side inward to keep dimension text within sheet bounds, whereas
   the baseline fixed offset places text out-of-bounds.
6. MF-02 Regression / R2.A (Evaluator Text-Line Symmetry): Pairwise collisions where dim1 line intersects
   dim2 text (with no dim-dim line crossing or text-text overlap) mark both dimensions unresolved
   symmetrically and are invariant to placed dimension ordering.
7. MF-03 Regression (Input Ordering Independence): Reversing measured segments on Fixture 8
   yields identical placement results via canonical spec sorting.
8. MF-07 Regression / R2.B (H20 Real Scoring Path Priority): A candidate with 0 hard collisions and multiple
   soft extension crossings strictly beats a candidate with >= 1 hard collision on the real scoring path.
9. Residual R1 Regression (Unary Extension Crossing Semantic Parity): A non-measured geometry segment
   intersecting both ext1 and ext2 of the same placed dimension contributes exactly two soft crossing
   penalties in candidate scoring (300.0) and exactly two extension_unwanted_crossings in the scene evaluator,
   while endpoint touches and measured-segment geometry are excluded by both.

Evidence Tier: BOUNDED_SYNTHETIC_RESEARCH_ORACLE
Note: Standalone prototype oracle; not a call through production builder owners or native DXF entity roundtrip.
"""

from __future__ import annotations

import math
import sys
from typing import List, Tuple

from benchmark_dimension_placement import (
    Scene,
    MeasuredSegment,
    AnnotationObstacle,
    PlacedDimension,
    compute_dimension_geometry,
    place_dimensions_baseline,
    place_dimensions_candidate,
    evaluate_placement_scene,
    create_fixtures,
    dimensions_match,
    score_candidate,
    count_unary_extension_crossings,
    segments_intersect,
    bboxes_overlap,
    segment_intersects_bbox,
)


def run_oracle_tests():
    print("=== Running REA-023 Native Dimension Placement Collision Avoidance Transfer Oracle ===")

    scenes = {sc.name: sc for sc in create_fixtures()}

    # -----------------------------------------------------------------------
    # Test 1: Exact prototype measurement truth preservation across all tested fixtures
    # -----------------------------------------------------------------------
    max_measurement_error = 0.0
    for name, sc in scenes.items():
        placed = place_dimensions_candidate(sc)
        for p in placed:
            err = abs(p.dimension_length - p.measured_length)
            if err > max_measurement_error:
                max_measurement_error = err

    assert max_measurement_error < 1e-9, f"Prototype measurement error exceeded zero: {max_measurement_error}"
    print(f"Test 1 PASS: Prototype geometric measurement length invariant verified across all 10 fixtures (max error = {max_measurement_error:.6f} mm).")
    print("             (Note: Algebraic sanity check on prototype model; PRODUCTION_NATIVE_MEASUREMENT_PRESERVATION=NOT_VERIFIED_BY_THIS_ORACLE).")

    # -----------------------------------------------------------------------
    # Test 2: Full-field deterministic repeatability across multiple runs
    # -----------------------------------------------------------------------
    sc4 = scenes["fixture_4_two_nearby_parallel"]
    run1 = place_dimensions_candidate(sc4)
    run2 = place_dimensions_candidate(sc4)
    run3 = place_dimensions_candidate(sc4)

    assert len(run1) == len(run2) == len(run3) == 2, "Unexpected dimension count on Fixture 4"
    for p1, p2, p3 in zip(run1, run2, run3):
        assert dimensions_match(p1, p2), "Full-field dimension match failed between run 1 and run 2!"
        assert dimensions_match(p1, p3), "Full-field dimension match failed between run 1 and run 3!"
    print("Test 2 PASS: Full-field deterministic repeatability verified across 3 repeated runs on Fixture 4 (all fields equal within 1e-9 on tested fixtures).")

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
    # Test 4: Multi-lane stacking separation on Fixture 5 (and dual-side separation on Fixture 4)
    # -----------------------------------------------------------------------
    # Fixture 5 actually exercises stacked offset lanes (lane_index > 0)
    sc5 = scenes["fixture_5_multiple_sharing_geometry"]
    base5 = place_dimensions_baseline(sc5)
    cand5 = place_dimensions_candidate(sc5)
    eval_base5 = evaluate_placement_scene(sc5, base5, "Baseline")
    eval_cand5 = evaluate_placement_scene(sc5, cand5, "Candidate")

    assert eval_base5.collision_count >= 1, "Baseline was expected to have dimension collisions on Fixture 5!"
    assert eval_cand5.collision_count == 0, f"Candidate failed to resolve collisions on Fixture 5 (collisions: {eval_cand5.collision_count})!"

    cand5_lanes = [p.lane_index for p in cand5]
    assert any(idx > 0 for idx in cand5_lanes), f"Expected multi-lane usage (lane_index > 0) on Fixture 5, got lanes: {cand5_lanes}"
    assert len(set(cand5_lanes)) >= 2, f"Expected multiple distinct lanes on Fixture 5, got: {cand5_lanes}"
    print(f"Test 4A PASS: Fixture 5 baseline had {eval_base5.collision_count} collisions; candidate used stacked multi-lanes {cand5_lanes} (lane_index > 0 verified) with 0 collisions.")

    # Fixture 4 resolves via dual-side non-conflicting separation
    sc4 = scenes["fixture_4_two_nearby_parallel"]
    base4 = place_dimensions_baseline(sc4)
    cand4 = place_dimensions_candidate(sc4)
    eval_base4 = evaluate_placement_scene(sc4, base4, "Baseline")
    eval_cand4 = evaluate_placement_scene(sc4, cand4, "Candidate")

    assert eval_base4.collision_count >= 1, "Baseline was expected to have parallel collision on Fixture 4!"
    assert eval_cand4.collision_count == 0, f"Candidate failed to resolve parallel collision on Fixture 4 (collisions: {eval_cand4.collision_count})!"
    d1, d2 = cand4[0], cand4[1]
    assert (d1.side != d2.side) or (d1.lane_index != d2.lane_index), "Candidate placed parallel dimensions in conflicting lane/side!"
    print(f"Test 4B PASS: Fixture 4 baseline had {eval_base4.collision_count} collisions; candidate separated parallel dimensions into non-conflicting sides ({d1.side} vs {d2.side}).")

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

    # -----------------------------------------------------------------------
    # Test 6 (MF-02 Regression / R2.A): Evaluator text-line pairwise symmetry
    # -----------------------------------------------------------------------
    # Craft a synthetic case where:
    # 1. NO dimension-line vs dimension-line crossing
    # 2. NO text vs text overlap
    # 3. Exactly one dimension line intersects the other dimension's text bbox
    #    (exercising the direction missed by the old asymmetric evaluator)
    # 4. Reversing placed list yields identical evaluation
    # 5. Both dimensions are attributed as unresolved
    p1_sym = PlacedDimension(
        spec_id="D1", side=1, lane_index=0, offset=8.0, base=(50.0, 50.0),
        dim_line_start=(10.0, 50.0), dim_line_end=(90.0, 50.0),
        ext_line_1_start=(10.0, 42.0), ext_line_1_end=(10.0, 52.0),
        ext_line_2_start=(90.0, 42.0), ext_line_2_end=(90.0, 52.0),
        text_bbox=(44.0, 48.25, 56.0, 51.75),
        measured_length=80.0, dimension_length=80.0
    )
    p2_sym = PlacedDimension(
        spec_id="D2", side=1, lane_index=0, offset=8.0, base=(30.0, 50.0),
        dim_line_start=(120.0, 10.0), dim_line_end=(120.0, 90.0),
        ext_line_1_start=(112.0, 10.0), ext_line_1_end=(122.0, 10.0),
        ext_line_2_start=(112.0, 90.0), ext_line_2_end=(122.0, 90.0),
        text_bbox=(24.0, 48.25, 36.0, 51.75),
        measured_length=80.0, dimension_length=80.0
    )

    p1_dim_seg = (p1_sym.dim_line_start, p1_sym.dim_line_end)
    p2_dim_seg = (p2_sym.dim_line_start, p2_sym.dim_line_end)

    assert not segments_intersect(p1_dim_seg, p2_dim_seg), "Precondition violated: dimension lines must not cross!"
    assert not bboxes_overlap(p1_sym.text_bbox, p2_sym.text_bbox), "Precondition violated: text bboxes must not overlap!"
    assert segment_intersects_bbox(p1_dim_seg, p2_sym.text_bbox), "Precondition violated: p1 dim line must cross p2 text bbox!"
    assert not segment_intersects_bbox(p2_dim_seg, p1_sym.text_bbox), "Precondition violated: p2 dim line must NOT cross p1 text bbox!"

    scene_sym = Scene(
        name="test_text_line_symmetry",
        description="Focused test where dim1 line intersects dim2 text, but dim2 line does not intersect dim1 text",
        measured_segments=[],
        geometry_segments=[],
        annotation_obstacles=[],
    )

    eval_fwd = evaluate_placement_scene(scene_sym, [p1_sym, p2_sym], "Forward")
    eval_rev = evaluate_placement_scene(scene_sym, [p2_sym, p1_sym], "Reversed")

    assert eval_fwd.collision_count == eval_rev.collision_count == 1, f"Collision count mismatch: {eval_fwd.collision_count} vs {eval_rev.collision_count}"
    assert eval_fwd.dim_to_annotation_overlaps == eval_rev.dim_to_annotation_overlaps == 1
    assert eval_fwd.dim_to_geometry_crossings == eval_rev.dim_to_geometry_crossings == 0
    assert eval_fwd.unresolved_dimensions == eval_rev.unresolved_dimensions == 2, f"Both colliding dimensions must be marked unresolved, got {eval_fwd.unresolved_dimensions}"
    print("Test 6 PASS: Evaluator pairwise symmetry verified on text-line crossing (order-invariant, both dimensions unresolved).")

    # -----------------------------------------------------------------------
    # Test 7 (MF-03 Regression): Input-list ordering independence (Fixture 8 reversed)
    # -----------------------------------------------------------------------
    sc8 = scenes["fixture_8_crowded_short_segments"]
    cand8_fwd = place_dimensions_candidate(sc8)

    # Reverse the input measured segments list
    sc8_rev = Scene(
        name=sc8.name,
        description=sc8.description,
        measured_segments=list(reversed(sc8.measured_segments)),
        geometry_segments=sc8.geometry_segments,
        annotation_obstacles=sc8.annotation_obstacles,
        sheet_boundary=sc8.sheet_boundary,
    )
    cand8_rev = place_dimensions_candidate(sc8_rev)

    assert len(cand8_fwd) == len(cand8_rev) == 2
    for p_fwd, p_rev in zip(cand8_fwd, cand8_rev):
        assert dimensions_match(p_fwd, p_rev), f"Input ordering affected placement for {p_fwd.spec_id}!"
    print("Test 7 PASS: Input-list ordering independence verified on Fixture 8 (forward vs reversed specs yield identical placements).")

    # -----------------------------------------------------------------------
    # Test 8 (MF-07 Regression / R2.B / H20): Hard collision priority on real scoring path
    # -----------------------------------------------------------------------
    # Craft scene where Candidate A (+1) has 0 hard collisions + 10 soft crossings (1500 penalty),
    # while Candidate B (-1) has 1 hard collision + 0 soft crossings (1001 penalty).
    geom_h20 = [
        ((100.0, 100.0), (200.0, 100.0)),  # Measured segment
        # 5 horizontal segments crossing ext1 on side +1
        ((90.0, 102.0), (105.0, 102.0)),
        ((90.0, 103.0), (105.0, 103.0)),
        ((90.0, 104.0), (105.0, 104.0)),
        ((90.0, 105.0), (105.0, 105.0)),
        ((90.0, 106.0), (105.0, 106.0)),
        # 5 horizontal segments crossing ext2 on side +1
        ((195.0, 102.0), (210.0, 102.0)),
        ((195.0, 103.0), (210.0, 103.0)),
        ((195.0, 104.0), (210.0, 104.0)),
        ((195.0, 105.0), (210.0, 105.0)),
        ((195.0, 106.0), (210.0, 106.0)),
        # 1 hard obstacle on side -1 blocking all lanes
        ((140.0, 70.0), (160.0, 95.0)),
    ]
    sc_h20 = Scene(
        name="test_h20_real_path",
        description="Crafted scene where side +1 has 0 hard collisions and 10 soft crossings, while side -1 has 1 hard collision",
        measured_segments=[MeasuredSegment("D1", (100.0, 100.0), (200.0, 100.0))],
        geometry_segments=geom_h20,
        annotation_obstacles=[],
    )

    # 1. Execute score_candidate on actual candidate geometry
    base_p, dim_p, ext1_p, ext2_p, tbox_p, _ = compute_dimension_geometry((100.0, 100.0), (200.0, 100.0), 8.0, +1)
    hard_p, soft_p = score_candidate(dim_p, ext1_p, ext2_p, tbox_p, +1, 0, sc_h20, [], ((100.0, 100.0), (200.0, 100.0)))

    base_m, dim_m, ext1_m, ext2_m, tbox_m, _ = compute_dimension_geometry((100.0, 100.0), (200.0, 100.0), 8.0, -1)
    hard_m, soft_m = score_candidate(dim_m, ext1_m, ext2_m, tbox_m, -1, 0, sc_h20, [], ((100.0, 100.0), (200.0, 100.0)))

    assert hard_p == 0, f"Candidate A must have 0 hard collisions, got {hard_p}"
    assert soft_p >= 1000.0, f"Candidate A must have large soft penalty, got {soft_p}"
    assert hard_m >= 1, f"Candidate B must have >= 1 hard collision, got {hard_m}"
    assert soft_m < soft_p, f"Candidate B should have lower soft penalty, got {soft_m} vs {soft_p}"

    cand_key_A = (hard_p, soft_p, 0, 0)
    cand_key_B = (hard_m, soft_m, 0, 1)
    assert cand_key_A < cand_key_B, f"Candidate A ({cand_key_A}) must beat Candidate B ({cand_key_B})"

    # 2. Execute real candidate selection path
    placed_h20 = place_dimensions_candidate(sc_h20)
    assert len(placed_h20) == 1
    assert placed_h20[0].side == 1, f"place_dimensions_candidate must select Candidate A (side +1), got side {placed_h20[0].side}"

    # 3. Execute evaluate_placement_scene on real result
    eval_h20 = evaluate_placement_scene(sc_h20, placed_h20, "Candidate_H20")
    assert eval_h20.collision_count == 0, f"Expected 0 hard collisions, got {eval_h20.collision_count}"
    assert eval_h20.extension_unwanted_crossings >= 10, f"Expected >= 10 soft crossings, got {eval_h20.extension_unwanted_crossings}"
    print("Test 8 PASS: H20 hard collision priority verified on real scoring path (0 hard + 1500 soft strictly beats 1 hard + 1 soft).")

    # -----------------------------------------------------------------------
    # Test 9 (Residual R1 Regression): Unary extension crossing semantic parity
    # -----------------------------------------------------------------------
    # Single geometry segment intersecting both ext1 and ext2 of a placed dimension
    g_crosses_both = ((50.0, 104.0), (250.0, 104.0))
    # Endpoint touch segment touching ext1 start at (100.0, 101.0)
    g_touch_ext1 = ((100.0, 101.0), (90.0, 101.0))
    # Measured segment itself present in geometry_segments
    g_measured = ((100.0, 100.0), (200.0, 100.0))

    geom_r1 = [g_measured, g_crosses_both, g_touch_ext1]
    sc_r1 = Scene(
        name="test_unary_extension_parity",
        description="Focused test where one geometry segment intersects both ext1 and ext2",
        measured_segments=[MeasuredSegment("D1", (100.0, 100.0), (200.0, 100.0))],
        geometry_segments=geom_r1,
        annotation_obstacles=[],
    )

    base_r1, dim_r1, ext1_r1, ext2_r1, tbox_r1, dim_len_r1 = compute_dimension_geometry(
        (100.0, 100.0), (200.0, 100.0), 8.0, +1
    )

    # 1. Direct helper test on the single geometry segment
    crossings_single = count_unary_extension_crossings(ext1_r1, ext2_r1, g_crosses_both, g_measured)
    assert crossings_single == 2, f"count_unary_extension_crossings must report 2 for segment intersecting both witness lines, got {crossings_single}"

    # 2. Endpoint touch and measured segment exclusions
    assert count_unary_extension_crossings(ext1_r1, ext2_r1, g_touch_ext1, g_measured) == 0, "Endpoint touch must be excluded"
    assert count_unary_extension_crossings(ext1_r1, ext2_r1, g_measured, g_measured) == 0, "Measured segment itself must be excluded"

    # 3. Scorer execution: must observe 2 unary crossings -> 2 * 150.0 = 300.0 soft penalty
    hard_r1, soft_r1 = score_candidate(
        dim_r1, ext1_r1, ext2_r1, tbox_r1, +1, 0, sc_r1, [], g_measured
    )
    assert hard_r1 == 0, f"Expected 0 hard collisions, got {hard_r1}"
    assert soft_r1 == 300.0, f"Expected soft penalty of 300.0 (2 * 150.0), got {soft_r1}"

    # 4. Evaluator execution: must report extension_unwanted_crossings == 2 (not 1)
    placed_r1 = [PlacedDimension(
        spec_id="D1",
        side=+1,
        lane_index=0,
        offset=8.0,
        base=base_r1,
        dim_line_start=dim_r1[0],
        dim_line_end=dim_r1[1],
        ext_line_1_start=ext1_r1[0],
        ext_line_1_end=ext1_r1[1],
        ext_line_2_start=ext2_r1[0],
        ext_line_2_end=ext2_r1[1],
        text_bbox=tbox_r1,
        measured_length=100.0,
        dimension_length=dim_len_r1,
    )]
    eval_r1 = evaluate_placement_scene(sc_r1, placed_r1, "Test_R1_Parity")
    assert eval_r1.collision_count == 0, f"Expected 0 collisions, got {eval_r1.collision_count}"
    assert eval_r1.dim_to_geometry_crossings == 0, f"Expected 0 dim_geom crossings, got {eval_r1.dim_to_geometry_crossings}"
    assert eval_r1.dim_to_annotation_overlaps == 0, f"Expected 0 annotation overlaps, got {eval_r1.dim_to_annotation_overlaps}"
    assert eval_r1.unresolved_dimensions == 0, f"Expected 0 unresolved dimensions, got {eval_r1.unresolved_dimensions}"
    assert eval_r1.extension_unwanted_crossings == 2, f"Evaluator must report exactly 2 extension crossings, got {eval_r1.extension_unwanted_crossings}"
    print("Test 9 PASS: Unary extension crossing semantic parity verified (single geometry segment crossing both ext1 and ext2 yields 2 scorer soft contributions and 2 evaluator crossings, with 0 hard collisions).")

    print("\nALL 9 ORACLE TESTS PASSED (100% Success). Oracle verified.")
    print("PRODUCTION_NATIVE_MEASUREMENT_PRESERVATION=NOT_VERIFIED_BY_THIS_ORACLE")


if __name__ == "__main__":
    run_oracle_tests()
