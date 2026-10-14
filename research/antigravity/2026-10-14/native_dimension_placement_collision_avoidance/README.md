# Proactive Research Precompute: Native Dimension Placement Collision Avoidance (REA-023)

- **Document ID:** `REA_DIM_PLACEMENT_PRECOMPUTE_V1`
- **Role:** `ANTIGRAVITY_RESEARCH_EXECUTOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Basis Commit:** `c8c34af074497aeaf24e53c57665a0f10170fab0` (`origin/research/antigravity-2026-10-11`)
- **Capability:** `NATIVE_DIMENSION_PLACEMENT_COLLISION_AVOIDANCE`
- **REA ID:** `REA-023`
- **Disposition:** `RESEARCH_PRIOR`
- **Evidence Tier:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE`
- **Production Status:** `RESEARCH_ONLY = YES`, `PRODUCTION_CODE_CHANGE = NO`, `PR_CHANGE = NO`, `AUTOCAD_MUTATION = NO`

---

## 1. Executive Summary & Objective

In native DXF dimension generation (`dxf_builder_lib/builder.py::_add_confirmed_dimensions`), linear dimensions are currently placed along a single deterministic left-hand outward normal at a fixed proportional offset:
$$d = \max(L \cdot 0.08, 5.0\text{ mm})$$
While this preserves exact physical measurement truth ($p_1, p_2$), it provides zero obstacle awareness, alternative side evaluation, or lane stacking. When measured features are near internal geometry pockets, annotation note blocks, adjacent parallel edges, or sheet borders, the baseline creates severe collisions and unreadable drawings.

This research evaluates whether a bounded, lightweight clean-room algorithm transfer (evaluating discrete $\pm \mathbf{n}$ normal sides and discrete stacked offset lanes) can eliminate baseline drafting collisions while strictly preserving exact measurement truth ($|L_{\text{dim}} - L_{\text{true}}| \equiv 0.0$).

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
└── TRANSFER_ORACLE.py                         # Standalone clean-room test oracle (5/5 tests PASS)
```

---

## 3. Key Empirical Findings

1. **Baseline Failure Rate on Synthetic Fixtures:**
   - Across 10 canonical fixtures, the production baseline produced **16 collisions across 8 failed scenes**.
   - Primary failure causes: single-side blindness when $+n$ is blocked by geometry or notes (Fixtures 6, 7), identical lane stacking overlap on parallel edges (Fixtures 4, 5, 8, 10), and drawing sheet boundary escape (Fixture 9).
2. **Candidate Policy Performance:**
   - The multi-lane dual-side candidate policy achieved **0 collisions across all 10 fixtures** (100% collision elimination on tested synthetic scenes).
   - Side-flipping ($s = -1$) cleanly avoided obstacles on Fixtures 6, 7, and 9.
   - Discrete lane stepping ($k \in \{0, 1, 2\}$) resolved all parallel dimension overlaps on Fixtures 4, 5, and 10.
3. **Formal Invariant Guarantees:**
   - **`MEASUREMENT_ERROR = 0.000000 mm`:** Exact definition point identity ($p_1, p_2$) is maintained; measurement length is strictly immutable.
   - **`DETERMINISTIC_REPEATABILITY = 100.0%`:** Identical floating-point coordinates across repeated runs.
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
Test 1 PASS: Exact measurement length invariant verified across all 10 fixtures (max error = 0.000000 mm).
Test 2 PASS: Deterministic repeatability verified across repeated runs on Fixture 4 (100.0% coordinate match).
Test 3A PASS: Fixture 6 baseline had 2 collisions on +normal side; candidate selected side=-1 with 0 collisions.
Test 3B PASS: Fixture 7 baseline had 2 collisions on +normal side; candidate selected side=-1 with 0 collisions.
Test 4 PASS: Fixture 4 baseline had 1 collisions; candidate separated parallel dimensions into non-conflicting lanes/sides (0 collisions).
Test 5 PASS: Fixture 9 baseline escaped top sheet border (out-of-bounds); candidate flipped inward to side=-1 with 0 boundary collisions.

ALL 5 ORACLE TESTS PASSED (100% Success). Oracle verified.
```

---

## 5. Catalog Registration & Owner Classification

- **Identifier:** `REA-023`
- **Capability:** `NATIVE_DIMENSION_PLACEMENT_COLLISION_AVOIDANCE`
- **External Source:** ASME Y14.5 / ISO 129-1 drafting conventions, AutoCAD `DIMDLI` system variable contract, Christensen et al. (1995) PFLP discrete candidate model
- **Reuse Class:** `ALGORITHM_TRANSFER` (clean-room candidate selection pattern using existing `ezdxf` geometry primitives)
- **Current Owner:** `dxf_builder_lib/builder.py::_add_confirmed_dimensions`
- **Condition for Future Transfer:** Only after measured product RED on real drawing comparisons
- **Production Transfer Authorized:** `NO`
- **Current Disposition:** `RESEARCH_PRIOR`
- **Do Not Repeat REA:** `YES`
