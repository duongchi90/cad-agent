# Proactive Research Precompute: Image-to-CAD Contour Simplification (REA-022)

- **Document ID:** `REA_CONTOUR_SIMP_PRECOMPUTE_V1`
- **Role:** `ANTIGRAVITY_RESEARCH_EXECUTOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Basis Commit:** `9ff8710107a60d30749f3018ef4719f0a94deefc` (`origin/research/antigravity-2026-10-11`)
- **Capability:** `IMAGE_TO_CAD_CONTOUR_SIMPLIFICATION`
- **Disposition:** `RESEARCH_PRIOR`
- **Evidence Tier:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE`
- **Production Status:** `RESEARCH_ONLY = YES`, `PRODUCTION_CODE_CHANGE = NO`, `PR_CHANGE = NO`, `AUTOCAD_MUTATION = NO`

---

## 1. Executive Summary & Objective

In image-to-CAD translation and contour-based geometry comparison (`primitive_ir_lib/geometry_comparator.py`), raw contours extracted from binary raster images via `cv2.findContours(..., cv2.CHAIN_APPROX_NONE)` contain dense chains of 1-pixel steps (typically 1,000–3,000 points per feature). This raster aliasing creates high-frequency staircase noise, distorts arc-length resampling, and inflates downstream processing time.

This research evaluates:
1. **Ramer-Douglas-Peucker (RDP / OpenCV approxPolyDP)** across absolute and relative parameterizations.
2. **Visvalingam-Whyatt (VW)** area-based simplification.
3. The **Scale-Dependent Epsilon Trap** where perimeter-relative formulas ($\epsilon = k \cdot P$) obliterate small mechanical features (notches, keyways, pin holes).

---

## 2. Directory Deliverables Map

```text
research/antigravity/2026-10-14/image_to_cad_contour_simplification/
├── README.md                                  # Master precompute documentation (this file)
├── BENCHMARK_SCORECARD.md                     # Quantitative results across 7 fixtures & 98 evaluations
├── FAILURE_MODES_AND_SAFETY_BOUNDS.md         # Critical failure modes & safe operating envelope
├── CAD_AGENT_OWNER_MAP.md                     # Mapping to existing owner (geometry_comparator.py)
├── benchmark_contour_simplification.py        # Complete 7-fixture automated evaluation harness
├── benchmark_results.json                     # Full 98-evaluation quantitative dataset
└── TRANSFER_ORACLE.py                         # Standalone clean-room test oracle (4/4 tests PASS)
```

---

## 3. Key Empirical Findings

1. **Ramer-Douglas-Peucker (OpenCV approxPolyDP) is Strictly Superior to Visvalingam-Whyatt:**
   - On straight edges with staircase aliasing, RDP achieves **99.7% point count reduction** (from 1160 points down to 4 vertices), with Hausdorff error of only **0.48 px** and area error of **0.0000%**.
   - Visvalingam-Whyatt fails catastrophically on closed raster loops because 1-pixel steps have tiny area ($0.5\text{ px}^2$), treating true CAD corners identically to flat-edge aliasing and collapsing shapes into coarse triangles.
2. **The Scale-Dependent Epsilon Trap:**
   - Using relative epsilon $\epsilon = k \cdot P$ (e.g. $k = 0.02$, as used in arrowhead extraction) on a mechanical part of perimeter $816\text{ px}$ yields $\epsilon = 16.3\text{ px}$, which **completely obliterates** a $6 \times 8\text{ px}$ keyway notch (`small_feature_survived = False`).
   - Absolute epsilon $\epsilon \in [0.75, 1.5]\text{ px}$ reliably eliminates staircase aliasing while preserving 100% of sharp corners and fine mechanical notches.
3. **Safe Operating Window for Image-to-CAD:**
   - **Recommended Absolute Epsilon:** $\epsilon = 1.0\text{ px}$ ($\pm 0.25\text{ px}$).
   - **Point Reduction:** $97.3\%\text{--}99.7\%$
   - **Hausdorff Error:** $\le 1.34\text{ px}$
   - **Area Fidelity:** Error $< 0.01\%$
   - **Corner Survival:** $100\%$

---

## 4. Test Oracle Results (`TRANSFER_ORACLE.py`)

Execution command:
```powershell
.\.venv-py311\Scripts\python.exe research/antigravity/2026-10-14/image_to_cad_contour_simplification/TRANSFER_ORACLE.py
```

Output:
```text
=== Running REA-022 Image-to-CAD Contour Simplification Transfer Oracle ===
Test 1 PASS: Staircase reduced from 1160 to 4 points (99.7% reduction). Exactly 4 corners retained.
Test 2 PASS: Safe absolute epsilon preserves 6x8 px notch (8 vertices total); relative epsilon (0.02*perim) destroys notch (bridges to 4 vertices).
Test 3 PASS: R=5 px hole retained with 8 vertices (area=70.0 px^2). Epsilon=6.0 px collapses hole to 2 points.
Test 4 PASS: Stepped shaft simplified from 1104 to 26 vertices (area error 0.0478%). Chamfers and fillet chords preserved.

ALL 4 ORACLE TESTS PASSED (100% Success). Oracle verified.
```

> [!IMPORTANT]
> **EVIDENCE_TIER: BOUNDED_SYNTHETIC_RESEARCH_ORACLE**
> `TRANSFER_ORACLE.py` is a standalone clean-room prototype using synthetic engineering contours. It does NOT call through current production `_contour_points()` and does NOT constitute production code. Production implementation requires a measured product RED on real drawing comparisons.

---

## 5. Catalog Registration

- **Identifier:** `REA-022`
- **Capability:** `IMAGE_TO_CAD_CONTOUR_SIMPLIFICATION`
- **External Source:** OpenCV `cv2.approxPolyDP` / Ramer (1972) & Douglas-Peucker (1973) algorithm
- **Reuse Class:** `DEPENDENCY_REUSE` (uses already-imported OpenCV `cv2.approxPolyDP`)
- **Current Owner:** `primitive_ir_lib/geometry_comparator.py`
- **Current Disposition:** `RESEARCH_PRIOR`
- **Do Not Repeat REA:** `YES`
