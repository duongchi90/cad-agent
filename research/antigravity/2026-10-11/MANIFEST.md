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
   - Formulated `SOURCE_NEGATIVE_LINE_SUPPORT_EVIDENCE_V1` pixel-domain verifier contract.
   - Retained native deletion as `BLOCKED` due to occlusion ambiguities.
   - 5 empirical scripts + 2 formal specifications.

## File Inventory and SHA-256 Signatures

| Research Topic | Filename | Type | Status | SHA-256 Checksum | Description |
|---|---|---|---|---|---|
| `orientation` | [`orientation_policy_benchmark.py`](orientation_policy_benchmark.py) | Benchmark / Fixture Script | `RESEARCH_ONLY` | `af381f6705e2fccbbf73e8e8630da387aad2b4559134ed87eafb625466329a2d` | Positive fixtures & wrong-anchor safety matrix across 4 orientation policies |
| `orientation` | [`test_public_path_red.py`](test_public_path_red.py) | Public Path Test | `RESEARCH_ONLY` | `a37b5702908c0bdf6fe73404077d1e91c66ef3ced485c12915321f85d34690de` | Causal RED on compose_verified_native_line_delta under 90 degree rotation |
| `orientation` | [`test_symmetry_safety.py`](test_symmetry_safety.py) | Safety Test | `RESEARCH_ONLY` | `ffa4e0068e01a43d15287056516a87a6de08883cc67b21ff5046ae717cda012c` | Square symmetry false-alignment test comparing Policy B vs Policy D |
| `orientation` | [`test_registration_correction.py`](test_registration_correction.py) | Empirical Test | `RESEARCH_ONLY` | `86b37df39967b94a697276814d7efa7b475b9c9c7cb71c168506ae3c9e4ee621` | Double-scale corruption and collinear anchor Cases A-E |
| `orientation` | [`test_rotation_seam.py`](test_rotation_seam.py) | Seam Test | `RESEARCH_ONLY` | `c39d2716f0f56c9d0350ece4b83cf02e94a8a73a04d1a5a23ba1b05ba0018b75` | Target-base rotation parameter seam verification |
| `orientation` | [`target_base_orientation_policy_discriminator_specification.md`](target_base_orientation_policy_discriminator_specification.md) | Specification | `RESEARCH_ONLY` | `182546714180a1aca8c3ba261f656eadc483de279c52f0556bb7cfaf73bba325` | Formal technical specification for Policy D (declared orientation envelope) |
| `orientation` | [`raster_base_wcs_registration_empirical_specification.md`](raster_base_wcs_registration_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `706b87a82e68821b5174044a1e887f5e6730f476b22f51c1ce3ce28e7c11aec7` | Corrected 3-layer WCS registration empirical specification |
| `correspondence` | [`test_causal_matrix.py`](test_causal_matrix.py) | Matrix Benchmark | `RESEARCH_ONLY` | `649d07f888bad45a65586269ac0da8200c1d6bd6d3ae0c39f7fa285591562cc9` | Measured execution of Cases A-L on compose_verified_native_line_delta |
| `correspondence` | [`test_greedy_order.py`](test_greedy_order.py) | Benchmark | `RESEARCH_ONLY` | `bf400d8ed47cfbf228d8a5a73799b9fc836285a89d4d9198fced1c1711def080` | Greedy collision order dependency benchmark |
| `correspondence` | [`test_causal_red_line_add.py`](test_causal_red_line_add.py) | Public Path Test | `RESEARCH_ONLY` | `9152eb3710c1898998e4fba8970de321980087c0269087c3328ef56fb58c4e97` | Causal RED for missing SOURCE_FUSION_LINE_ADD_PROPOSAL_V1 |
| `correspondence` | [`source_base_line_correspondence_gap_empirical_specification.md`](source_base_line_correspondence_gap_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `f3a392d30f658ad841bd42701b36ad0440e922992a1aaff63ffaf36811c2be31` | Formal specification for Line ADD proposal and correspondence contract |
| `removal` | [`test_removal_failure_modes.py`](test_removal_failure_modes.py) | Failure Analysis Script | `RESEARCH_ONLY` | `0cb654299b594e500d9c70f45527a89f0b7a229e649e18ce0ddd5c9e4bb8161f` | Benchmark of 12 raster dropout failure modes against naive deletion |
| `removal` | [`test_positive_removal_case.py`](test_positive_removal_case.py) | Proof Script | `RESEARCH_ONLY` | `5b6f5f0d8a8e8a62afe0b0bf66cfd8b17ac5ae0b9f8ab8d72b46122d7815dda0` | Positive removal case and 5 distinguishing proofs on 3-rib bracket |
| `removal` | [`test_reverse_path.py`](test_reverse_path.py) | Coordinate Mapping Test | `RESEARCH_ONLY` | `5ccccb56b183fc906b240403cfd58ae2214b445d3e5afd92b5c7bf8443c97e2a` | Reverse coordinate mapping from Base WCS to source pixels |
| `removal` | [`test_negative_support_pairs.py`](test_negative_support_pairs.py) | Benchmark | `RESEARCH_ONLY` | `76f5990b7c9e38122a83a5f86f44d2a773a815fcbcf807f65f5ea4eca7d2ec81` | Benchmark across Pairs A-H proving naive threshold inversion is fatal |
| `removal` | [`test_causal_red_negative_support.py`](test_causal_red_negative_support.py) | Public Path Test | `RESEARCH_ONLY` | `faf8612f25ccdf26c721467cbe6072a9d9a523b008f7c23df11fd3a696e28ca2` | Causal RED for missing verify_native_line_source_absence_evidence |
| `removal` | [`source_base_line_removal_evidence_empirical_specification.md`](source_base_line_removal_evidence_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `9d6fd2e9598b86e1e5588dc041f5263a3e8a86dab305b03189b618aa08c870f5` | Core safety doctrine UNMATCHED_BASE != REMOVE specification |
| `removal` | [`source_negative_line_support_empirical_specification.md`](source_negative_line_support_empirical_specification.md) | Specification | `RESEARCH_ONLY` | `0d57efe6754f0d16c4741624f621ac9419ceef6cc078a28ea70b3bfee1365251` | Observational absence evidence and raster verifier contract specification |

## Verification and Non-Interference Guarantees

- All scripts and specifications are self-contained or import directly from current repo structure.
- No production paths in `cad_agent/`, `primitive_ir_lib/`, or tests were mutated.
- Zero binary CAD drawings, raw logs, caches, or credentials are included.
