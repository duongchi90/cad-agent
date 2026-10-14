# Proactive Research Precompute: Native Dimension Placement Collision Avoidance (REA-023)

- **Document ID:** `REA_DIM_PLACEMENT_PRECOMPUTE_V2`
- **Role:** `ANTIGRAVITY_RESEARCH_EXECUTOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Basis Commit:** `473c1eb0de262e2b27cd007291d1b0d073f2e6e1` (`origin/research/antigravity-2026-10-11`)
- **Capability:** `NATIVE_DIMENSION_PLACEMENT_COLLISION_AVOIDANCE`
- **REA ID:** `REA-023`
- **Disposition:** `RESEARCH_PRIOR`
- **Evidence Tier:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE`
- **Production Status:** `RESEARCH_ONLY = YES`, `PRODUCTION_CODE_CHANGE = NO`, `PR_CHANGE = NO`, `AUTOCAD_MUTATION = NO`

---

## 1. Executive Summary & Objective

In native DXF dimension generation (`dxf_builder_lib/builder.py::_add_confirmed_dimensions`), linear dimensions are currently placed along a single deterministic left-hand outward normal at a fixed proportional offset:
$$d = \max(L \cdot 0.08, 5.0\text{ mm})$$
While this preserves physical measurement truth ($p_1, p_2$), it provides zero obstacle awareness, alternative side evaluation, or lane stacking. When measured features are near internal geometry pockets, annotation note blocks, adjacent parallel edges, or sheet borders, the baseline creates collisions and unreadable drawings.

This research evaluates whether a bounded, lightweight clean-room algorithm transfer (evaluating discrete $\pm \mathbf{n}$ normal sides and discrete stacked offset lanes) can avoid baseline drafting collisions on tested fixtures while preserving prototype measurement truth ($|L_{\text{dim}} - L_{\text{true}}| \equiv 0.0$).

---

## 2. Directory Deliverables Map

```text
research/antigravity/2026-10-14/native_dimension_placement_collision_avoidance/
├── README.md                                  # Master precompute documentation (this file)
├── EXTERNAL_PRIOR_AND_SPEC_REPORT.md          # ASME/ISO standards, AutoCAD DIMDLI, PFLP literature, licensing
├── CURRENT_OWNER_AND_BASELINE.md              # dxf_builder_lib owner analysis & baseline failure reproduction
├── PLACEMENT_POLICY_COMPARISON.md             # Benchmark scorecard comparing baseline vs candidate policy
├── FAILURE_MODES_AND_LIMITS.md                # Structural failure modes, boundary limits, and disclaimers
├── benchmark_dimension_placement.py           # 10-fixture automated benchmark runner & evaluation harness
├── benchmark_results.json                     # Complete quantitative benchmark results dataset
└── TRANSFER_ORACLE.py                         # Standalone clean-room test oracle (8/8 tests PASS)
```

---

## 3. Key Empirical Findings

1. **Baseline Failure Rate on Synthetic Fixtures:**
   - Across 10 canonical fixtures, the production baseline produced **17 collisions across 8 failed scenes** (9 dimension-to-geometry crossings, 8 dimension-to-annotation overlaps, 12 unwanted extension crossings; 10 unresolved dimensions).
   - Primary failure causes: single-side blindness when $+n$ is blocked by geometry or notes (Fixtures 6, 7), identical lane stacking overlap on parallel edges (Fixtures 4, 5, 8, 10), and drawing sheet boundary escape (Fixture 9).
2. **Candidate Policy Performance:**
   - The multi-lane dual-side candidate policy achieved **0 collisions across all 10 fixtures** (0 dimension-to-geometry crossings, 0 dimension-to-annotation overlaps, 4 unwanted extension crossings; 0 unresolved dimensions).
   - Side-flipping ($s = -1$) avoided obstacles on Fixtures 6, 7, and 9.
   - Discrete lane stepping ($k \in \{0, 1, 2\}$) resolved all parallel dimension overlaps on Fixtures 4, 5, 8, and 10.
3. **Formal Invariant vs Research Heuristic Scope:**
   - **`PROTOTYPE_MEASUREMENT_ERROR = 0.000000 mm`:** Definition point identity ($p_1, p_2$) is maintained algebraically in the prototype geometry model by construction.
   - **`PRODUCTION_NATIVE_MEASUREMENT_PRESERVATION = NOT_VERIFIED_BY_THIS_ORACLE`:** Native DXF DIMENSION entity rendering and binary AutoCAD database roundtrip were not evaluated by this oracle.
   - **`EXTENSION_UNWANTED_CROSSINGS = 12 (BASELINE) VS 4 (CANDIDATE)`:** Evaluated using unified pairwise dim/ext soft interaction semantics matching candidate scoring.
   - **`PLACEMENT_DISPLACEMENT = NOT_MEASURED`:** Displacement relative to unguided baseline is not recorded as a quality metric.
   - **`DETERMINISTIC_REPEATABILITY = 100.0%`:** Verified across 2 repeated runs on all 10 synthetic fixtures (15/15 dimensions full-field identical within 1e-9 tolerance) and 3 runs on Fixture 4.
   - **`BASE_FLOOR_HEURISTIC`:** Candidate base floor $\max(L \cdot 0.08, 6.0\text{ mm})$ vs baseline $\max(L \cdot 0.08, 5.0\text{ mm})$ and lane step increment $\Delta d = \max(7.5, 2 \cdot H_{\text{text}})$ are empirical research heuristic model changes, not drafting standards.
   - **`SELECTION_PRIORITY_H20`:** Hard collisions strictly dominate candidate selection over soft extension crossings ($\text{Primary Key} = \text{hard\_collision\_count}$, $\text{Secondary Key} = \text{soft\_penalty\_score}$).
4. **Anti-Bloat & Zero-Dependency Profile:**
   - Pure Python 2D segment-box geometric primitives. Zero new libraries, zero global solver daemons, zero ML models. Evaluation time is under $25\ \mu\text{s}$ per dimension.

---

## 4. Test Oracle Results (`TRANSFER_ORACLE.py`)

Execution command:
```powershell
.\.venv-py311\Scripts\python.exe research/antigravity/2026-10-14/native_dimension_placement_collision_avoidance/TRANSFER_ORACLE.py
```

Output:
```text
=== Running REA-023 Native Dimension Placement Collision Avoidance Transfer Oracle ===
Test 1 PASS: Prototype geometric measurement length invariant verified across all 10 fixtures (max error = 0.000000 mm).
             (Note: Algebraic sanity check on prototype model; PRODUCTION_NATIVE_MEASUREMENT_PRESERVATION=NOT_VERIFIED_BY_THIS_ORACLE).
Test 2 PASS: Full-field deterministic repeatability verified across 3 repeated runs on Fixture 4 (all fields equal within 1e-9 on tested fixtures).
Test 3A PASS: Fixture 6 baseline had 2 collisions on +normal side; candidate selected side=-1 with 0 collisions.
Test 3B PASS: Fixture 7 baseline had 2 collisions on +normal side; candidate selected side=-1 with 0 collisions.
Test 4A PASS: Fixture 5 baseline had 1 collisions; candidate used stacked multi-lanes [0, 1, 2] (lane_index > 0 verified) with 0 collisions.
Test 4B PASS: Fixture 4 baseline had 1 collisions; candidate separated parallel dimensions into non-conflicting sides (-1 vs 1).
Test 5 PASS: Fixture 9 baseline escaped top sheet border (out-of-bounds); candidate flipped inward to side=-1 with 0 boundary collisions.
Test 6 PASS: Evaluator pairwise symmetry verified on text-line crossing (order-invariant, both dimensions unresolved).
Test 7 PASS: Input-list ordering independence verified on Fixture 8 (forward vs reversed specs yield identical placements).
Test 8 PASS: H20 hard collision priority verified on real scoring path (0 hard + 1500 soft strictly beats 1 hard + 1 soft).

ALL 8 ORACLE TESTS PASSED (100% Success). Oracle verified.
PRODUCTION_NATIVE_MEASUREMENT_PRESERVATION=NOT_VERIFIED_BY_THIS_ORACLE
```

---

## 5. Catalog Registration & Owner Classification

- **Identifier:** `REA-023`
- **Capability:** `NATIVE_DIMENSION_PLACEMENT_COLLISION_AVOIDANCE`
- **External Sources & Licenses:**
  - ASME Y14.5 / ISO 129-1: `COPYRIGHTED_SPECIFICATION_OR_DOCUMENTATION_PRIOR`, `DIRECT_CODE_REUSE=NO`
  - AutoCAD DIMDLI / DIMBASELINE: `PROPRIETARY_DOCUMENTATION_OR_BEHAVIORAL_PRIOR`, `DIRECT_CODE_REUSE=NO`
  - ezdxf (1.4.4) LinearDimension API: `MIT`, `DEPENDENCY_REUSE`, `DIRECT_CODE_REUSE=YES`
  - Jon Christensen, Joe Marks, Stuart M. Shieber (1995) PFLP (ACM Transactions on Graphics 14(3), 1995, pp. 203–232): `ACADEMIC_ALGORITHMIC_PRIOR`, `ALGORITHM_TRANSFER`, `DIRECT_CODE_REUSE=NO` (clean-room transfer only)
- **Current Owner:** `dxf_builder_lib/builder.py::_add_confirmed_dimensions`
- **Condition for Future Transfer:** Only after measured product RED on real drawing comparisons
- **Production Transfer Authorized:** `NO`
- **Current Disposition:** `RESEARCH_PRIOR`
- **Do Not Repeat REA:** `YES`
