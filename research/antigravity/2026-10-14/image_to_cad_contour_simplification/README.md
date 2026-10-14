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
2. **Clean-Room Direct-Area Visvalingam-Whyatt Variant** (direct area recomputation without monotonic hierarchy ladder).
3. The **Scale-Dependent Epsilon Trap** on tested full-part synthetic contours where perimeter-relative settings ($k \ge 0.01$) erased small notches.

---

## 2. Directory Deliverables Map

```text
research/antigravity/2026-10-14/image_to_cad_contour_simplification/
├── README.md                                  # Master precompute documentation (this file)
├── BENCHMARK_SCORECARD.md                     # Quantitative results across 7 fixtures & 98 evaluations
├── FAILURE_MODES_AND_SAFETY_BOUNDS.md         # Critical failure modes & safe operating envelope
├── CAD_AGENT_OWNER_MAP.md                     # Mapping to existing & future candidate owners
├── benchmark_contour_simplification.py        # Complete 7-fixture automated evaluation harness
├── benchmark_results.json                     # Full 98-evaluation quantitative dataset
└── TRANSFER_ORACLE.py                         # Standalone clean-room test oracle (4/4 tests PASS)
```

---

## 3. Key Empirical Findings (Fixture-Specific Synthetic Observations)

> [!IMPORTANT]
> **UNIVERSAL_EPSILON=NOT_PROVEN.**
> All numeric values cited below are **fixture-specific synthetic observations** on tested binary raster shapes with 1-pixel steps. They do NOT constitute an all-scale or universal production claim.

1. **RDP vs Clean-Room Direct-Area VW Variant on Tested Fixtures:**
   - On straight edges with staircase aliasing (Fixture 1, 1160 points), RDP with tested absolute $\epsilon = 0.75\text{--}3.0\text{ px}$ achieves **99.7% point count reduction** (down to exactly 4 vertices), with Hausdorff error of **0.48 px** and area error of **0.0000%**.
   - The evaluated `Clean_Room_Direct_Area_VW_Variant` (recomputing local triangle area directly without monotonic hierarchy propagation) collapsed tested closed raster loops to 3–4 points at tested thresholds $\tau \ge 1.0\text{ px}^2$ because individual 1-pixel steps have triangle area $\le 0.5\text{ px}^2$, similar to discrete grid corners. Canonical VW with monotonic hierarchy was not tested.
2. **The Scale-Dependent Epsilon Trap on Full Parts:**
   - Existing specialized reuse in `dimension_geometry.py::_contour_arrow_points` uses $0.08 \times P$ on small bounded arrowhead contours ($P \approx 30\text{--}50\text{ px}$, $\epsilon \approx 2.4\text{--}4.0\text{ px}$), which is effective and not defective in that scope.
   - On tested full-part synthetic shapes, tested settings where $\epsilon = k \cdot P$ exceeded feature depth (e.g. Fixture 4 with $P = 816\text{ px}$, $k = 0.02 \implies \epsilon = 16.32\text{ px} > 8\text{ px}$ notch depth) completely erased the keyway notch.
   - Tested settings where $\epsilon$ remained bounded below feature depth (e.g. tested absolute $\epsilon \in [0.75, 1.5]\text{ px}$) preserved 100% of tested corners and notches.
3. **Metric Scope & Geometry Dependence:**
   - **Straight-edge & staircase polygons (Fixtures 1, 2, 6):** 99.4%–99.7% point reduction under tested $\epsilon \in [0.75, 1.5]\text{ px}$ with $H \le 0.72\text{ px}$ and 100% corner survival.
   - **Composite stepped shaft (Fixture 7):** 97.3%–97.8% point reduction (1104 to 24–30 points) under tested $\epsilon \in [0.75, 1.5]\text{ px}$ with $H \le 1.34\text{ px}$, area error $\le 0.0096\%$, and notch intact.
   - **Curved profiles (Fixture 3 arc, Fixture 5 hole):** Lower reduction rates (71.4%–95.3%) to maintain geometric fidelity; arcs require chord chains to avoid chord-flattening error ($H = 0.69\text{ px}$ at $\epsilon = 0.75\text{ px}$, $H = 1.49\text{ px}$ at $\epsilon = 1.5\text{ px}$). Small hole ($R=5\text{ px}$) collapsed to a line when $\epsilon = 6.0\text{ px} > R$.
   - **Scale Generalization:** Strictly relative to tested synthetic pixel dimensions. No assertion is made for uncalibrated real-world scans or DPI invariance.

---

## 4. Test Oracle Results (`TRANSFER_ORACLE.py`)

Execution command:
```powershell
.\.venv-py311\Scripts\python.exe research/antigravity/2026-10-14/image_to_cad_contour_simplification/TRANSFER_ORACLE.py
```

Output:
```text
=== Running REA-022 Image-to-CAD Contour Simplification Transfer Oracle ===
Test 1 PASS: Fixture 1 staircase reduced from 1160 to 4 points (99.7% reduction). Exactly 4 corners retained.
Test 2 PASS: Tested absolute epsilon=1.0 px preserves 6x8 px notch on Fixture 4 (8 vertices total); tested relative epsilon=0.02*P bridges notch to 4 vertices.
Test 3 PASS: Fixture 5 R=5 px hole retained with 8 vertices (area=70.0 px^2) under tested eps=1.0 px; tested eps=6.0 px collapses hole to 2 points.
Test 4 PASS: Fixture 7 stepped shaft simplified from 1104 to 26 vertices (area error 0.0478%) under tested eps=1.0 px. Chamfers and fillet chords preserved.

ALL 4 ORACLE TESTS PASSED (100% Success). Oracle verified.
```

> [!IMPORTANT]
> **EVIDENCE_TIER: BOUNDED_SYNTHETIC_RESEARCH_ORACLE**
> `TRANSFER_ORACLE.py` is a standalone clean-room prototype using synthetic engineering contours. It does NOT call through current production `_contour_points()` and does NOT constitute production code. Production implementation requires a measured product RED on real drawing comparisons.

---

## 5. Catalog Registration & Owner Classification

- **Identifier:** `REA-022`
- **Capability:** `IMAGE_TO_CAD_CONTOUR_SIMPLIFICATION`
- **External Source:** OpenCV `cv2.approxPolyDP` / Ramer (1972) & Douglas-Peucker (1973) algorithm
- **Reuse Class:** `DEPENDENCY_REUSE` (uses already-imported OpenCV `cv2.approxPolyDP`)
- **EXISTING_SPECIALIZED_RDP_REUSE:** `primitive_ir_lib/dimension_geometry.py::_contour_arrow_points` (SCOPE: small bounded arrowhead contours)
- **FUTURE_FULL_CONTOUR_CANDIDATE_OWNER:** `primitive_ir_lib/geometry_comparator.py::_contour_points` (CONDITION: only after measured product RED)
- **PRODUCTION_TRANSFER_AUTHORIZED:** `NO`
- **Current Disposition:** `RESEARCH_PRIOR`
- **Do Not Repeat REA:** `YES`
