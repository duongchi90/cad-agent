# Antigravity Empirical Research Manifest (2026-10-11)

- **Date:** 2026-10-11
- **Originating Commit:** `47808851b22472e213c8b8d77b735f9dbb88d699` (merged PR #493)
- **Branch:** `research/antigravity-2026-10-11`
- **Scope:** Research artifacts and empirical verification scripts only.
- **Production Impact:** `RESEARCH_ONLY = YES`, `DO_NOT_MODIFY_PRODUCTION_CODE = YES`, `DO_NOT_CREATE_PR = YES`.
- **Preserved Epics:** Issue #491 (`NATIVE_LINE_DIMASSOC_FORWARD_OPERABILITY_AND_PERSISTENCE_V1`) and `NO_TOUCH_ARC_CIRCLE_MUTATION_EPIC` unmodified.

## Summary of Preserved Research Groups

1. **Orientation (`research/antigravity/2026-10-11/orientation/`):**
   - Investigated target-to-base WCS registration policies.
   - Established Policy D (caller-declared orientation envelope) to eliminate rotational ambiguity and symmetry traps.
   - 5 empirical scripts + 2 formal specifications.

2. **Correspondence (`research/antigravity/2026-10-11/correspondence/`):**
   - Evaluated native LINE correspondence engine across Cases A-L.
   - Proven greedy collision ordering failure modes.
   - Defined `SOURCE_FUSION_LINE_ADD_PROPOSAL_V1` (queued for codex).
   - 3 empirical scripts + 1 formal specification.

3. **Removal (`research/antigravity/2026-10-11/removal/`):**
   - Analyzed 12 raster dropout failure modes proving `UNMATCHED_BASE != REMOVE`.
   - Formulated `SOURCE_NEGATIVE_LINE_SUPPORT_EVIDENCE_V1` pixel-domain verifier contract closure.
   - Completed behavioral causal RED, controls matrix (0, A-H), and threshold classification.
   - Retained native deletion as `BLOCKED` due to occlusion and entity lifecycle ambiguities.
   - 6 empirical scripts + 2 formal specifications.

4. **Thick Line Normalization (`research/antigravity/2026-10-11/thick_line/`):**
   - Baseline causal RED proving 100% duplicate Hough edge rate on current `extract_lines` across widths 1-15px.
   - Benchmarked 4 candidate strategies, proving topology-preserving thinning (Strat B) drops duplicates to 8.2% and offset to 0.13px.
   - Proved `GLOBAL_THINNING_SAFE = NO` due to destruction of solid disks/circles and OCR glyphs.
   - Hard safety gates verified: two real parallel lines, junctions (T, L, X), dense/sparse hatch, dimension lines, dashed gaps.
   - 7 empirical scripts + 1 formal specification.

5. **Circle False-Positive Perimeter Validation (`research/antigravity/2026-10-11/circle_validation/`):**
   - Baseline causal RED demonstrating 144 false-positive circles from HoughCircles on non-circle patterns (cross-hatch, dense hatch, text, grid crossings).
   - Arc vs circle conflation analysis showing semicircles (>= 180 deg) falsely proposed as full engineering circles.
   - Empirical validation of perimeter support oracle: minimum circumference support >= 75%, max unsupported angular gap <= 45 deg, radial gradient alignment >= 60%, and radial distance roundness sigma_r <= max(0.35, 0.04*r).
   - Proven that inside/outside contrast check is unsafe for solid disks and thick strokes.
   - Validated 100.0% false-positive elimination rate (0/144 false detections retained) while maintaining 100.0% true circle retention across 35 radius/stroke configs.
   - 5 empirical scripts + 1 formal specification.

6. **Cardinal Rotated Text Extraction (`research/antigravity/2026-10-11/text_extraction/`):**
   - Baseline causal RED demonstrating 100% failure rate of current production `extract_text_tesseract` on 90°, 180°, 270° text across 6 text classes.
   - Proved that demo pipeline's "longest non-empty string" heuristic fails 100% of the time (24/24) on short text, selecting longer hallucinated garbage over ground truth.
   - Proved that Tesseract OSD fails 100% on dimension/short crops ("Too few characters").
   - Benchmarked Strategy D (geometry-assisted aspect ratio pruning) achieving 100.0% exact match and 100.0% rotation accuracy while halving runtime (370.1 ms/ROI vs 719.5 ms/ROI).
   - Executed 280-run exact matrix across font sizes (12-48px), rotations, and paddings: 95.7% exact match, 100.0% rotation classification, with identical performance across 0°, 90°, 180°, 270°.
   - Demonstrated 100% non-text false-positive elimination (0/11 accepted) under composite evidence scoring.
   - Proved 100% numeric dimension safety (40/40 exact values, zero catastrophic substitutions).
   - 8 empirical scripts + 1 formal specification.

7. **Taubin Circular Arc Extraction (`research/antigravity/2026-10-11/arc_extraction/`):**
   - Public causal RED proving current `extract_raw_geometry` and `build_document` emit 0 `ArcGeometry` primitives on 90°, 180°, 270° source arcs while conflating 180°/270° arcs into full 360° circles.
   - Benchmarked 5 fitting strategies (Kåsa, Taubin, Pratt, OpenCV `minEnclosingCircle`, RANSAC+Taubin), proving Taubin (`0.744 px` mean center error, `3.13%` radius error, `522.5 us/fit`) wins on partial circular sweeps.
   - Proven that candidate-local distance-transform-weighted Taubin fitting (`M4`) with foreground-ring angular support and round-cap overhang compensation eliminates 100% of thick-stroke inner/outer duplicate arcs (`0/7` vs `7/7` on Canny edges, `0.205 px` mean radius error) and achieves `0.796 px` P95 endpoint error across widths 1-8px and wrap-around intervals.
   - Established exact Pixel (CW, +y down) to CAD (CCW, +y up) endpoint-derived angle contract (`2.25e-14 mm` algebraic identity error, `0.089 mm` mean raster endpoint reconstruction error).
   - Validated 0 false arcs across 51 consolidated negative-control fixtures (text glyphs `C,G,O,0,8,S,U,J,)`, hatch, corners, lines, circles, ellipses, noise), 100% rejection on ellipses with axis ratio >= 1.20 and sweep >= 90°, and `NONFINITE_OUTPUT_COUNT = 0` across 52 degenerate/numeric safety cases (`Evaluated Main SHA: 47808851b22472e213c8b8d77b735f9dbb88d699`).
   - 11 empirical scripts + 1 formal specification (`TAUBIN_ARC_EXTRACTION_V1_READY_FOR_CODEX`).

8. **Collinear Line Merging (`research/antigravity/2026-10-11/line_merging/`):**
   - Public causal RED demonstrating 6 failure modes on production `merge_collinear_lines`: first-segment angle skew (2.800° error, 20.49 px drift), single-endpoint perpendicular leak (12.90 px drift), parallel line collapse (4.0 px offset collapsed into 1 line), dimension chain bridging without text (93.3% loss of 90° witness boundaries), false tick detection on 45° cross-hatch, and T-junction stem bridging.
   - Benchmarked 4 strategies (A: Current Main, B: Dual-Bound Naive, C: Weighted PCA + Parallel Guard, D: Topology Oracle), proving Strategy D achieves 0.004° angle error, 0.029 px drift, 100% perp leak rejection, 100% parallel line preservation, 100% dimension chain recall, 100% hatch immunity, and 100% T-junction preservation at 35.1 µs/call.
   - Executed 105-case parallel matrix (offsets 2-8px, angles 0-90°, overlaps 20-100%): Strategy A collapsed 83/105 pairs (79.0% failure); Strategy D preserved 105/105 pairs (100.0% recall).
   - Executed 60-case dimension chain matrix (symbols, gaps 10-25px, angles 0-90°): Strategy D achieved 100% boundary preservation even with 0% OCR recall.
   - Executed 24-case hatch immunity matrix across spacings (8-20px) and angles (30-60°): Strategy D achieves 100% broken line merge recall via 64x64 normal clustering.
   - Proved 12-angle rotation circle stability (mean angle error = 0.0025°, lateral drift = 0.0090 px) and multi-fragment chain convergence (error = 0.0001°).
   - Verified 6 degenerate/numeric safety cases (empty, singletons, zero-length, micro-segments, duplicate/nested collapse, extreme coordinates 10^6 px, NaN/Inf safety) and runtime scalability up to N=1000 segments (5.6 ms at N=100).
   - 9 empirical scripts + 1 formal specification (`COLLINEAR_LINE_MERGING_V1_READY_FOR_CODEX`).

9. **Automatic Calibration Multi-Candidate Consensus (`research/antigravity/2026-10-11/calibration_consensus/`):**
   - Public causal RED reproducing 5 baseline failure modes on production `calibration.py`: 59.6% scale error from fragmented Hough line pairing (337px vs 538px), unverified single-candidate return under `require_consensus=False` default, permissive 10.0% consensus tolerance violating `AGENTS.md` 3% invariant, sheet number ("09") calibration hallucination (99% error), and cross-axis aspect ratio distortion blindness (25% axis stretching).
   - Benchmarked 4 strategies (A: Current Main, B: Naive 10% Consensus, C: Strict 3% Consensus, D: Topology Oracle), proving Strategy D achieves 0.00% scale error, 100% fragment immunity, 100% noise rejection, and 100% cross-axis verification at 223.4 µs/call.
   - Enforced `AGENTS.md` production invariant: >= 2 independent candidates with median relative error <= 3.0%, failing closed on single candidates, > 3% error, and conflicting mixed-scale views.
   - Verified 6 degenerate/numeric safety cases (empty, zero values, negative dimensions, NaN/Inf safety, zero-length points, extreme coordinates 10^6 px) and runtime scalability (7.77 ms for 50 texts x 200 lines).
   - 5 empirical scripts + 1 formal specification (`AUTOMATIC_CALIBRATION_CONSENSUS_V1_READY_FOR_CODEX`).

## File Inventory and SHA-256 Signatures

| Research Topic | Filename | Type | Status | SHA-256 Checksum | Description |
|---|---|---|---|---|---|
| `orientation` | [`orientation_policy_benchmark.py`](orientation/orientation_policy_benchmark.py) | Benchmark / Fixture Script | `RESEARCH_ONLY` | `af381f6705e2fccbbf73e8e8630da387aad2b4559134ed87eafb625466329a2d` | Positive fixtures & wrong-anchor safety matrix across 4 orientation policies |
| `orientation` | [`test_public_path_red.py`](orientation/test_public_path_red.py) | Public Path Test | `RESEARCH_ONLY` | `a37b5702908c0bdf6fe73404077d1e91c66ef3ced485c12915321f85d34690de` | Causal RED on compose_verified_native_line_delta under 90 degree rotation |
| `orientation` | [`test_symmetry_safety.py`](orientation/test_symmetry_safety.py) | Safety Test | `RESEARCH_ONLY` | `ffa4e0068e01a43d15287056516a87a6de08883cc67b21ff5046ae717cda012c` | Square symmetry false-alignment test comparing Policy B vs Policy D |
| `orientation` | [`test_registration_correction.py`](orientation/test_registration_correction.py) | Empirical Test | `RESEARCH_ONLY` | `86b37df39967b94a697276814d7efa7b475b9c9c7cb71c168506ae3c9e4ee621` | Double-scale corruption and collinear anchor Cases A-E |
| `orientation` | [`test_rotation_seam.py`](orientation/test_rotation_seam.py) | Seam Test | `RESEARCH_ONLY` | `c39d2716f0f56c9d0350ece4b83cf02e94a8a73a04d1a5a23ba1b05ba0018b75` | Target-base rotation parameter seam verification |
| `orientation` | [`target_base_orientation_policy_discriminator_specification.md`](orientation/target_base_orientation_policy_discriminator_specification.md) | Specification | `RESEARCH_ONLY` | `182546714180a1aca8c3ba261f656eadc483de279c52f0556bb7cfaf73bba325` | Formal technical specification for Policy D (declared orientation envelope) |
| `orientation` | [`raster_base_wcs_registration_empirical_specification.md`](orientation/raster_base_wcs_registration_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `706b87a82e68821b5174044a1e887f5e6730f476b22f51c1ce3ce28e7c11aec7` | Corrected 3-layer WCS registration empirical specification |
| `correspondence` | [`test_causal_matrix.py`](correspondence/test_causal_matrix.py) | Matrix Benchmark | `RESEARCH_ONLY` | `649d07f888bad45a65586269ac0da8200c1d6bd6d3ae0c39f7fa285591562cc9` | Measured execution of Cases A-L on compose_verified_native_line_delta |
| `correspondence` | [`test_greedy_order.py`](correspondence/test_greedy_order.py) | Benchmark | `RESEARCH_ONLY` | `bf400d8ed47cfbf228d8a5a73799b9fc836285a89d4d9198fced1c1711def080` | Greedy collision order dependency benchmark |
| `correspondence` | [`test_causal_red_line_add.py`](correspondence/test_causal_red_line_add.py) | Public Path Test | `RESEARCH_ONLY` | `9152eb3710c1898998e4fba8970de321980087c0269087c3328ef56fb58c4e97` | Causal RED for missing SOURCE_FUSION_LINE_ADD_PROPOSAL_V1 |
| `correspondence` | [`source_base_line_correspondence_gap_empirical_specification.md`](correspondence/source_base_line_correspondence_gap_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `f3a392d30f658ad841bd42701b36ad0440e922992a1aaff63ffaf36811c2be31` | Formal specification for Line ADD proposal and correspondence contract |
| `removal` | [`test_removal_failure_modes.py`](removal/test_removal_failure_modes.py) | Failure Analysis Script | `RESEARCH_ONLY` | `0cb654299b594e500d9c70f45527a89f0b7a229e649e18ce0ddd5c9e4bb8161f` | Benchmark of 12 raster dropout failure modes against naive deletion |
| `removal` | [`test_positive_removal_case.py`](removal/test_positive_removal_case.py) | Proof Script | `RESEARCH_ONLY` | `5b6f5f0d8a8e8a62afe0b0bf66cfd8b17ac5ae0b9f8ab8d72b46122d7815dda0` | Positive removal case and 5 distinguishing proofs on 3-rib bracket |
| `removal` | [`test_reverse_path.py`](removal/test_reverse_path.py) | Coordinate Mapping Test | `RESEARCH_ONLY` | `5ccccb56b183fc906b240403cfd58ae2214b445d3e5afd92b5c7bf8443c97e2a` | Reverse coordinate mapping from Base WCS to source pixels |
| `removal` | [`test_negative_support_pairs.py`](removal/test_negative_support_pairs.py) | Benchmark | `RESEARCH_ONLY` | `76f5990b7c9e38122a83a5f86f44d2a773a815fcbcf807f65f5ea4eca7d2ec81` | Benchmark across Pairs A-H proving naive threshold inversion is fatal |
| `removal` | [`test_negative_support_controls.py`](removal/test_negative_support_controls.py) | Controls Benchmark | `RESEARCH_ONLY` | `fd9a4c770e93284062ae542fd5b770c79a5f2a0c37d05630783770e48f58a5f1` | Empirical benchmark across controls 0 and A-H for threshold closure |
| `removal` | [`test_causal_red_negative_support.py`](removal/test_causal_red_negative_support.py) | Public Path Test | `RESEARCH_ONLY` | `08c626b7a25c8cc0dfa3976bfe4d338ddda692ee70e224c40aa9f6bd84b3afae` | Behavioral causal RED for missing raster absence evidence |
| `removal` | [`source_base_line_removal_evidence_empirical_specification.md`](removal/source_base_line_removal_evidence_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `9d6fd2e9598b86e1e5588dc041f5263a3e8a86dab305b03189b618aa08c870f5` | Core safety doctrine UNMATCHED_BASE != REMOVE specification |
| `removal` | [`source_negative_line_support_empirical_specification.md`](removal/source_negative_line_support_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `cba1e54007889f21bf9862a69f2762198133abed6831a6de475dab1d1e8b9081` | Observational absence evidence and raster verifier contract closure |
| `thick_line` | [`test_thick_line_causal_red.py`](thick_line/test_thick_line_causal_red.py) | Causal RED Test | `RESEARCH_ONLY` | `5af804b48683b971df2f5e19d4a250a0e8739a4121942f197bd068d119655afb` | 100% duplicate Hough edge line baseline failure across widths 1-15px and angles 0-90 deg |
| `thick_line` | [`test_thick_line_normalization_benchmark.py`](thick_line/test_thick_line_normalization_benchmark.py) | Strategy Benchmark | `RESEARCH_ONLY` | `2db8944f9c401ce235c2fca38fcb25a43250c85f900f25c328cf506724298545` | Empirical comparison of 4 normalization strategies (Current vs Morph vs Zhang-Suen vs Collapse) |
| `thick_line` | [`test_global_vs_line_thinning.py`](thick_line/test_global_vs_line_thinning.py) | Boundary Test | `RESEARCH_ONLY` | `3f438b841a1da05ae95dbc0e25f3780cea7ce1a37977c2d799c66ba110a0c655` | Proof that global thinning destroys solid disks and degrades circles vs line-only preprocessing |
| `thick_line` | [`test_parallel_lines_control.py`](thick_line/test_parallel_lines_control.py) | Negative Control | `RESEARCH_ONLY` | `ad84f974a52f4f80dc8f0bf53be6bfcc08e5d855d7b61c78237f35f41e2c873b` | Verification that distinct real parallel lines are preserved and not falsely merged |
| `thick_line` | [`test_junctions_benchmark.py`](thick_line/test_junctions_benchmark.py) | Topology Benchmark | `RESEARCH_ONLY` | `5a8d9d206545a03bd3abb907b2a652719613536484987751a8185146b8146e75` | T-junction, L-corner, X-crossing, rectangle, and polyline topological preservation |
| `thick_line` | [`test_hatch_and_dimension_controls.py`](thick_line/test_hatch_and_dimension_controls.py) | Control Benchmark | `RESEARCH_ONLY` | `e8109f97bf35537ebd9903fd785c81ee7f24e3dabd02c8ceea1a58dc709adc41` | Dense/sparse hatch, dimension extension lines, and dashed gap non-bridging tests |
| `thick_line` | [`test_circle_interaction.py`](thick_line/test_circle_interaction.py) | Interaction Benchmark | `RESEARCH_ONLY` | `7e39dfb708e364cefb70b607a654cb27d11bef8a957e3abd6fdb57b17949c05e` | Isolated circles, tangent lines, crossing lines, and rounded rectangle chord elimination |
| `thick_line` | [`thick_line_centerline_normalization_empirical_specification.md`](thick_line/thick_line_centerline_normalization_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `bcef57e693b8bab44cf0571db717e709f689e6c302005e4c127749181b676b85` | Formal technical specification for thick line centerline normalization |
| `circle_validation` | [`test_circle_false_positives_red.py`](circle_validation/test_circle_false_positives_red.py) | Causal RED Test | `RESEARCH_ONLY` | `bbc118fd86495c2271a514b1f422c3c1c5d3336e2a6b5a7167d8df7dee1d0520` | Baseline causal RED proving 144 false circles across 17 non-circle fixture families |
| `circle_validation` | [`test_arc_vs_circle.py`](circle_validation/test_arc_vs_circle.py) | Boundary Test | `RESEARCH_ONLY` | `f916d90eb559811f99cfb6cb1508fbca76b82e9b8893be7106a2e7d43b1a90f9` | Arc sweep vs Hough circle candidate proposal proving conflation for arcs >= 180 deg |
| `circle_validation` | [`test_circle_validator_oracle.py`](circle_validation/test_circle_validator_oracle.py) | Oracle Benchmark | `RESEARCH_ONLY` | `981a1376dfce4c0b4e2b85c0f5386e88fcd29bed1477fe0fe20684675307e937` | Component contribution analysis: support, angular bins, radial gradients, contrast |
| `circle_validation` | [`test_true_circle_positive_matrix.py`](circle_validation/test_true_circle_positive_matrix.py) | Positive Matrix Test | `RESEARCH_ONLY` | `e21ad27c5d0ff9c78dfbe431ee691d40d99d7336ed93fbada57f912e356f96b5` | True circle retention matrix (radii 5-120px, widths 1-8px, 100% retention on detections) |
| `circle_validation` | [`test_false_positive_negative_matrix.py`](circle_validation/test_false_positive_negative_matrix.py) | Negative Matrix Test | `RESEARCH_ONLY` | `5e372673555832e06f7ea584b2086e63bb1a39ed8cb2e0287239bfb2db5762cf` | Negative elimination matrix across 17 fixture families (100% false circles eliminated) |
| `circle_validation` | [`circle_false_positive_perimeter_validation_empirical_specification.md`](circle_validation/circle_false_positive_perimeter_validation_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `65224a2e5e53a19a5b2b9b0e65d60ff4c16d6e952c1daf622ac3be37116ee3a8` | Formal technical specification for circle false-positive perimeter validation |
| `text_extraction` | [`test_causal_red_cardinal_text.py`](text_extraction/test_causal_red_cardinal_text.py) | Causal RED Test | `RESEARCH_ONLY` | `f73ba4f7826e7a42d5e51f436b4a006472c6240ab7a6f67c0b860e6ab13f218b` | Baseline causal RED proving 100% failure on 90, 180, 270 deg text on current main |
| `text_extraction` | [`test_mock_length_heuristic_failure.py`](text_extraction/test_mock_length_heuristic_failure.py) | Benchmark | `RESEARCH_ONLY` | `64fec698d91d96418896166a0a52a954a4452c6162e7cfb0b5994b39e9d944e0` | Empirical proof of 100% failure rate for demo pipeline's max length selection heuristic |
| `text_extraction` | [`test_cardinal_rotation_benchmark.py`](text_extraction/test_cardinal_rotation_benchmark.py) | Strategy Benchmark | `RESEARCH_ONLY` | `ce18068c190a97339c36b7e07f9da27cb81091e724530e8a2c5b7a5adc5f1267` | Comparison of Strategies A, B, C, D proving Strategy D cuts runtime to 370 ms/ROI |
| `text_extraction` | [`test_cardinal_exact_matrix.py`](text_extraction/test_cardinal_exact_matrix.py) | Matrix Benchmark | `RESEARCH_ONLY` | `000a246fb9bcb604c4553c770fe38d7061bb2229ead313c34c79faf7b909cbbc` | 280-run matrix across classes, rotations (0-270), and font sizes (12-48px) |
| `text_extraction` | [`test_180_and_90_ambiguity.py`](text_extraction/test_180_and_90_ambiguity.py) | Ambiguity Benchmark | `RESEARCH_ONLY` | `bf75b706f76d4727b8a50b8294181592c419803cb6c86184f874c7e4cd902786` | 180-deg rotational ambiguity classification and 90 vs 270 deg confidence separation |
| `text_extraction` | [`test_numeric_dimension_safety.py`](text_extraction/test_numeric_dimension_safety.py) | Safety Benchmark | `RESEARCH_ONLY` | `a935f52a5bff2150507defd79fc1829077129b6c22e8ed642764c2df7e52da8f` | Exact numeric value preservation and catastrophic character substitution tracking |
| `text_extraction` | [`test_non_text_false_positives.py`](text_extraction/test_non_text_false_positives.py) | Negative Matrix Test | `RESEARCH_ONLY` | `efc9693bb4ded23c38cb3e5f8abba972bb53965ef7664cc1c59efc5103baf389` | False-positive control across 11 non-text ROIs proving zero garbage amplification |
| `text_extraction` | [`test_roi_detection_and_table_control.py`](text_extraction/test_roi_detection_and_table_control.py) | Integration Test | `RESEARCH_ONLY` | `fa013b8b62f8988d5bed2c1a5e9e636772f38874a56aa13955dc45c5211568ca` | ROI clustering orientation recall and table cell rotated header extraction |
| `text_extraction` | [`cardinal_rotated_text_extraction_empirical_specification.md`](text_extraction/cardinal_rotated_text_extraction_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `1802647e60003c0ef97909df4c895a1a3f38a3295ebd134d0436fa99d30dced5` | Formal technical specification for cardinal rotated text extraction |
| `arc_extraction` | [`test_causal_red_arc_extraction.py`](arc_extraction/test_causal_red_arc_extraction.py) | Causal RED Test | `RESEARCH_ONLY` | `8b94305c80b9a6c081fcb4df6cbd524f7f4858d3155b32d7148ffa4a0c5e481c` | Public causal RED proving 0 RawArc/ArcGeometry emitted and 180/270-deg arcs conflated into circles (main `47808851b22472e213c8b8d77b735f9dbb88d699`) |
| `arc_extraction` | [`test_fitting_strategies_benchmark.py`](arc_extraction/test_fitting_strategies_benchmark.py) | Strategy Benchmark | `RESEARCH_ONLY` | `02fdb31782938f60317e2208d1830f6f54ced7defa9559c520a29021453ec9c2` | Empirical comparison of Kåsa, Taubin, Pratt, OpenCV minEnclosingCircle, and RANSAC+Taubin across 40 clean & 40 contaminated arcs |
| `arc_extraction` | [`test_true_arc_matrix.py`](arc_extraction/test_true_arc_matrix.py) | Positive Matrix Test | `RESEARCH_ONLY` | `224201270c04608002e5d2afae360fbe44f5959599ee5da97a1adb4ffd171723` | True arc accuracy matrix across radii (5-120px), sweeps (15-330 deg), start angles, stroke widths (1-8px), and AA/non-AA controls |
| `arc_extraction` | [`test_arc_vs_line_discrimination.py`](arc_extraction/test_arc_vs_line_discrimination.py) | Discrimination Test | `RESEARCH_ONLY` | `b12e61ba767c4312314bd7915a780b99acfdc96cd9b82ccaae9a9b93eb2033d3` | ARC vs LINE 3-gate fail-closed discrimination across straight lines, shallow curves, corners, and polylines |
| `arc_extraction` | [`test_arc_vs_circle_boundary.py`](arc_extraction/test_arc_vs_circle_boundary.py) | Boundary Test | `RESEARCH_ONLY` | `7e2f477d843372a4f16f10e4ddf183dd973719943cba67bbc2d42f479974cad5` | ARC vs CIRCLE boundary discrimination (300-360 deg) and 0 dual-emission guarantee |
| `arc_extraction` | [`test_thick_stroke_arc_duplication.py`](arc_extraction/test_thick_stroke_arc_duplication.py) | Duplication Benchmark | `RESEARCH_ONLY` | `6959d028a473bff81def088c13f0e1d276513e4b62348107bb16a948df2d75d5` | Thick-stroke arc duplication benchmark across widths 1-15px proving 0% duplication for candidate-local medial distance evidence |
| `arc_extraction` | [`test_short_span_conditioning.py`](arc_extraction/test_short_span_conditioning.py) | Conditioning Test | `RESEARCH_ONLY` | `bcc3a4cae57971931206ca9ecacf45c49cfed625d270f356692ba405b7511a39` | Short-span algebraic conditioning and transverse jitter sensitivity proving MIN_STABLE_ARC_SWEEP = 45 deg |
| `arc_extraction` | [`test_angular_wrap_endpoints_and_cad_contract.py`](arc_extraction/test_angular_wrap_endpoints_and_cad_contract.py) | Contract & Seam Test | `RESEARCH_ONLY` | `259435bfe042227be863b64d23acb9c4e03bdf1bc15fc47149459f75eb8cc19e` | Angular wrap-around (0/360 deg), endpoint recovery estimators A-E, and Pixel-to-CAD angle/endpoint contract proof |
| `arc_extraction` | [`test_negative_matrix_and_ellipse_control.py`](arc_extraction/test_negative_matrix_and_ellipse_control.py) | Negative & Ellipse Matrix | `RESEARCH_ONLY` | `058e55ffdfdb23d4b427c73c37a40214de71da08606278b9fab8159f4453e824` | Consolidated 51-fixture negative-control matrix (0 false arcs) and ellipse axis-ratio/sweep discrimination benchmark |
| `arc_extraction` | [`test_degenerate_occluded_and_fillet_interactions.py`](arc_extraction/test_degenerate_occluded_and_fillet_interactions.py) | Safety & Interaction Test | `RESEARCH_ONLY` | `53af500070b2bf2fc80de3c13c0dab7bf5590d43629b775495dcfa3a424303df` | Degenerate/numeric safety (52 cases, 0 non-finite outputs), broken/dashed arcs, and line/tangency/fillet corridor subtraction |
| `arc_extraction` | [`test_degradation_and_performance_benchmark.py`](arc_extraction/test_degradation_and_performance_benchmark.py) | Degradation & Perf Benchmark | `RESEARCH_ONLY` | `1a655df1e6609ecebe8a4d6c55456890b6ce12fb3eeab7ed54a378908fff3890` | Monotonic confidence model, bounded raster degradation recall/precision, and sequential runtime profiling (300x300, 1000x1000, 2000x2000) |
| `arc_extraction` | [`taubin_arc_extraction_empirical_specification.md`](arc_extraction/taubin_arc_extraction_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `5e358dd0cee7288c2e3167b496648513b703920fa86a88d4056dd75f18bde24b` | Complete empirical specification for Taubin circular arc extraction (Sections 8-33, `TAUBIN_ARC_EXTRACTION_V1`) |
| `line_merging` | [`line_merging_engine.py`](line_merging/line_merging_engine.py) | Engine / Oracle | `RESEARCH_ONLY` | `7749d6b87ad0a91300fbb246584d72f8bdbd83a384875fba23251de93659f640` | Shared reference implementation of Strategies A-D for collinear line merging |
| `line_merging` | [`test_causal_red_line_merging.py`](line_merging/test_causal_red_line_merging.py) | Causal RED Test | `RESEARCH_ONLY` | `bcb0f5418b48154ed360025634eff5288f9adfc9680572cb49429772baa4cd37` | Public causal RED reproducing 6 baseline failure modes on production merge_collinear_lines |
| `line_merging` | [`test_merging_strategies_benchmark.py`](line_merging/test_merging_strategies_benchmark.py) | Strategy Benchmark | `RESEARCH_ONLY` | `f1d1e4908959525b79031ee6cdeb5bedfba39d436ac6b5f92dbf4578d73f2984` | Empirical benchmark comparing Strategies A, B, C, D across angle error, drift, leak rejection, and runtime |
| `line_merging` | [`test_parallel_lines_preservation.py`](line_merging/test_parallel_lines_preservation.py) | Parallel Lines Test | `RESEARCH_ONLY` | `416e69e2f3fe42d9baa40678d38e99588b79adec8c2c46997d4e4a03b8208f42` | 105-case matrix across offsets (2-8px), angles, and overlaps proving 100% parallel preservation |
| `line_merging` | [`test_dimension_chain_discrimination.py`](line_merging/test_dimension_chain_discrimination.py) | Dimension Chain Test | `RESEARCH_ONLY` | `abd528ae24eedd101a3ca6c596edfd099e810fdcfafea53a5c88013c83086c7c` | 60-case dimension chain benchmark proving 100% boundary preservation even with 0% OCR recall |
| `line_merging` | [`test_hatch_and_text_noise_rejection.py`](line_merging/test_hatch_and_text_noise_rejection.py) | Noise Control Test | `RESEARCH_ONLY` | `c1da825b0ff373191d804a94479183eb8ebafdf62489e14c1a039df6363a2802` | 24-case hatch immunity matrix and slanted text glyph rejection proving zero false tick triggers |
| `line_merging` | [`test_t_junction_and_crossing_controls.py`](line_merging/test_t_junction_and_crossing_controls.py) | Junction Controls Test | `RESEARCH_ONLY` | `661a06f41da4c238f6ccaf59484c7b0023c224ac6969b01c163815ac3115c954` | T-junction stem matrix (16 cases), continuous X-crossings, and spatial locality controls |
| `line_merging` | [`test_angle_drift_and_weighted_fit.py`](line_merging/test_angle_drift_and_weighted_fit.py) | Stability Benchmark | `RESEARCH_ONLY` | `f45d74d849598ec2ea67803cc5bd127b66702aff83ca3b7d74d353a3928a84f8` | 12-angle rotation circle benchmark and multi-fragment length-squared weighted fit attenuation |
| `line_merging` | [`test_degenerate_nonfinite_and_perf_benchmark.py`](line_merging/test_degenerate_nonfinite_and_perf_benchmark.py) | Edge & Perf Benchmark | `RESEARCH_ONLY` | `4631c2d661208a43437576c8458da2013002cec0ba70b0464dbdcb055c580638` | Zero-length points, duplicates, nested containment, extreme coordinates, NaN/Inf safety, and N=1000 scalability |
| `line_merging` | [`collinear_line_merging_empirical_specification.md`](line_merging/collinear_line_merging_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `0e868d18a56dad8b786bc7ca78feccf70e1a738ce40e9fedb1da6c500724047f` | Complete empirical specification for collinear line merging (Sections 10-22, `COLLINEAR_LINE_MERGING_V1`) |
| `calibration_consensus` | [`calibration_consensus_engine.py`](calibration_consensus/calibration_consensus_engine.py) | Engine / Oracle | `RESEARCH_ONLY` | `318fbe6b611cc573c17126600534ed637c0f5d7327414c05e9c56c917262a216` | Reference implementation of Strategies A-D for multi-candidate calibration consensus |
| `calibration_consensus` | [`test_causal_red_calibration.py`](calibration_consensus/test_causal_red_calibration.py) | Causal RED Test | `RESEARCH_ONLY` | `7866fe09f44a0d1ae8762fd628c4df95d8eba0295790091ffe45639e2df02664` | Public causal RED reproducing 5 baseline failure modes on production calibration.py |
| `calibration_consensus` | [`test_calibration_strategies_benchmark.py`](calibration_consensus/test_calibration_strategies_benchmark.py) | Strategy Benchmark | `RESEARCH_ONLY` | `a2e91fe148fd607afb793e05b3deba6d86996d04d7eacb4cbb6759b9f29dd436` | Empirical benchmark comparing Strategies A-D on realistic multi-view drawing scenario |
| `calibration_consensus` | [`test_positive_and_negative_consensus_controls.py`](calibration_consensus/test_positive_and_negative_consensus_controls.py) | Controls Test | `RESEARCH_ONLY` | `16b885dc0f6e01f7126e397e2935f78f37c020aa713b9fc612705dda2b6641fd` | Positive consensus fixtures and strong negative controls enforcing AGENTS.md 3% gate |
| `calibration_consensus` | [`test_calibration_degenerate_nonfinite_and_perf.py`](calibration_consensus/test_calibration_degenerate_nonfinite_and_perf.py) | Edge & Perf Benchmark | `RESEARCH_ONLY` | `5786985c8cbce13922e46e4534e4cce8d7842c2666ac4ab5178704eaaff5071c` | Empty collections, non-finite values, zero-length points, extreme coordinates, and scalability profiling |
| `calibration_consensus` | [`calibration_consensus_empirical_specification.md`](calibration_consensus/calibration_consensus_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `b15df585aec6124923a428b981aa18c415853d7609e73d0031c597677d385294` | Complete empirical specification for automatic calibration consensus (Sections 10-20, `AUTOMATIC_CALIBRATION_CONSENSUS_V1`) |

## Verification and Non-Interference Guarantees

- All scripts and specifications are self-contained or import directly from current repo structure.
- No production paths in `cad_agent/`, `primitive_ir_lib/`, or tests were mutated.
- Zero binary CAD drawings, raw logs, caches, or credentials are included.
