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

## Verification and Non-Interference Guarantees

- All scripts and specifications are self-contained or import directly from current repo structure.
- No production paths in `cad_agent/`, `primitive_ir_lib/`, or tests were mutated.
- Zero binary CAD drawings, raw logs, caches, or credentials are included.
