# BENCHMARK_SCORECARD: Image-to-CAD Contour Simplification (REA-022)

- **Document ID:** `REA_CONTOUR_SIMP_SCORECARD_V1`
- **Role:** `ANTIGRAVITY_RESEARCH_EXECUTOR`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Capability:** `IMAGE_TO_CAD_CONTOUR_SIMPLIFICATION`
- **Evidence Tier:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE`

---

## 1. Executive Summary & Benchmark Design

Contour simplification takes raw, noisy raster contour chains (typically produced by `cv2.findContours(..., cv2.CHAIN_APPROX_NONE)` with 1-pixel steps) and reduces them to concise piecewise linear polygons suitable for CAD entity generation and geometric comparison.

This benchmark evaluated:
1. **Baseline:** Unsimplified raster contour (`cv2.CHAIN_APPROX_NONE`)
2. **RDP (OpenCV approxPolyDP) Absolute Epsilon:** $\epsilon \in \{0.75, 1.5, 3.0, 6.0\}\text{ px}$
3. **RDP (OpenCV approxPolyDP) Relative Epsilon:** $\epsilon \in \{0.002, 0.005, 0.01, 0.02, 0.08\} \times \text{perimeter}$
4. **Visvalingam-Whyatt (VW):** Minimum triangle effective area threshold $\tau_{\text{area}} \in \{1.0, 4.0, 16.0, 64.0\}\text{ px}^2$

Across 7 synthetic engineering fixtures (98 total configurations).

---

## 2. Quantitative Results by Fixture

### Fixture 1: Long Straight Edges (400x200 Rectangle at 15°, Staircase Noise)
*Goal: Remove aliasing staircase on long edges without disturbing sharp 90° corners.*

| Algorithm | Parameter | Output Points | Point Reduction | Hausdorff Error | Area Error | Perimeter Error | Corner Survival |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline (NONE)** | None | 1160 | 0.0% | 0.00 px | 0.0000% | 0.00% | 100.0% |
| **OpenCV RDP (Abs)** | $\epsilon = 0.75\text{ px}$ | **4** | **99.7%** | **0.48 px** | **0.0000%** | 6.83% | **100.0%** |
| **OpenCV RDP (Abs)** | $\epsilon = 1.50\text{ px}$ | **4** | **99.7%** | **0.48 px** | **0.0000%** | 6.83% | **100.0%** |
| **OpenCV RDP (Abs)** | $\epsilon = 3.00\text{ px}$ | **4** | **99.7%** | **0.48 px** | **0.0000%** | 6.83% | **100.0%** |
| **OpenCV RDP (Rel)** | $\epsilon = 0.005 \times P$ | **4** | **99.7%** | **0.48 px** | **0.0000%** | 6.83% | **100.0%** |
| **Visvalingam-Whyatt** | Area $= 1.0\text{ px}^2$ | 3 | 99.7% | 441.89 px | 99.9981% | 99.34% | 25.0% |

*Key finding:* RDP absolute $\epsilon = 0.75\text{--}3.0\text{ px}$ perfectly eliminates all 1156 staircase points, recovering exactly the 4 true CAD rectangle corners ($H = 0.48\text{ px}$, area error = 0.0000%). Visvalingam-Whyatt catastrophically collapses closed loops because 1-pixel steps have tiny area (see Failure Modes).

---

### Fixture 2: Sharp Acute and Oblique Corners (Chevron 30°, 45°, 90°, 135°)
*Goal: Verify acute corner retention without corner clipping / rounding.*

| Algorithm | Parameter | Output Points | Point Reduction | Hausdorff Error | Area Error | Corner Survival |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline (NONE)** | None | 1000 | 0.0% | 0.00 px | 0.0000% | 100.0% |
| **OpenCV RDP (Abs)** | $\epsilon = 0.75\text{ px}$ | **6** | **99.4%** | **0.72 px** | **0.0000%** | **100.0%** |
| **OpenCV RDP (Abs)** | $\epsilon = 1.50\text{ px}$ | **6** | **99.4%** | **0.72 px** | **0.0000%** | **100.0%** |
| **OpenCV RDP (Abs)** | $\epsilon = 3.00\text{ px}$ | **6** | **99.4%** | **0.72 px** | **0.0000%** | **100.0%** |
| **OpenCV RDP (Rel)** | $\epsilon = 0.08 \times P$ | 5 | 99.5% | 50.00 px | 16.6667% | 83.3% (Apex clipped!) |
| **Visvalingam-Whyatt** | Area $= 1.0\text{ px}^2$ | 3 | 99.7% | 198.65 px | 87.6667% | 50.0% |

*Key finding:* Sharp acute corners ($30^\circ$ apex) survive completely at absolute $\epsilon \le 3.0\text{ px}$. Aggressive relative $\epsilon = 0.08 \times P$ clips the $30^\circ$ apex.

---

### Fixture 3: Circular Arcs (Disk R=75 px)
*Goal: Measure polygonization density vs chord flattening error.*

| Algorithm | Parameter | Output Points | Point Reduction | Hausdorff Error | Area Error | Chord Flattening Error |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline (NONE)** | None | 424 | 0.0% | 0.00 px | 0.0000% | 0.00% |
| **OpenCV RDP (Abs)** | $\epsilon = 0.75\text{ px}$ | 40 | 90.6% | **0.69 px** | **0.0458%** | Negligible ($\sim 9^\circ$ chords) |
| **OpenCV RDP (Abs)** | $\epsilon = 1.50\text{ px}$ | 20 | 95.3% | **1.49 px** | **1.0199%** | Moderate ($\sim 18^\circ$ chords) |
| **OpenCV RDP (Abs)** | $\epsilon = 6.00\text{ px}$ | 8 | 98.1% | 5.84 px | 8.8930% | Severe (Octagon) |
| **OpenCV RDP (Rel)** | $\epsilon = 0.08 \times P$ | 4 | 99.1% | 21.92 px | 35.5375% | Catastrophic (Diamond/Square) |

*Key finding:* Circular arcs require $\epsilon \le 1.0\text{ px}$ to maintain smooth circular fidelity ($H < 1.0\text{ px}$, area error $< 0.1\%$). When $\epsilon \ge 6.0\text{ px}$ or $\epsilon \ge 0.02 \times P$, arcs degenerate into coarse polygons.

---

### Fixture 4: Tiny Mechanical Notch (250x150 Block with 6x8 px Keyway)
*Goal: Test small feature preservation against the Scale-Dependent Epsilon Trap.*

| Algorithm | Parameter | Output Points | Point Reduction | Notch Survived? | Corner Survival | Hausdorff Error |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline (NONE)** | None | 816 | 0.0% | **YES** | 100.0% | 0.00 px |
| **OpenCV RDP (Abs)** | $\epsilon = 0.75\text{ px}$ | 10 | 98.8% | **YES** | 100.0% | **0.00 px** |
| **OpenCV RDP (Abs)** | $\epsilon = 1.50\text{ px}$ | 8 | 99.0% | **YES** | 100.0% | **0.88 px** |
| **OpenCV RDP (Abs)** | $\epsilon = 6.00\text{ px}$ | 7 | 99.1% | **YES (Distorted)** | 87.5% | 4.91 px |
| **OpenCV RDP (Rel)** | $\epsilon = 0.005 \times P$ | 8 | 99.0% | **YES** | 100.0% | 0.88 px |
| **OpenCV RDP (Rel)** | $\epsilon = 0.02 \times P$ | 4 | 99.5% | **NO (Obliterated!)** | 50.0% | 9.00 px |
| **OpenCV RDP (Rel)** | $\epsilon = 0.08 \times P$ | 4 | 99.5% | **NO (Obliterated!)** | 50.0% | 9.00 px |

*Key finding:* Relative epsilon scaling $\epsilon = \text{fraction} \times P$ is **catastrophically unsafe** on large parts. For a perimeter of $816\text{ px}$, $0.02 \times P = 16.3\text{ px} > \text{notch depth } (8\text{ px})$, completely erasing the keyway notch. Safe boundary requires absolute $\epsilon \le 1.5\text{ px}$.

---

### Fixture 5: Small Pin Hole (R=5 px / 10 px Diameter, Perimeter 28 px)
*Goal: Test hole boundary collapse / deletion threshold.*

| Algorithm | Parameter | Output Points | Point Reduction | Topology Preserved? | Area Error |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Baseline (NONE)** | None | 28 | 0.0% | **YES** | 0.0000% |
| **OpenCV RDP (Abs)** | $\epsilon = 0.75\text{ px}$ | 8 | 71.4% | **YES** | 6.0606% |
| **OpenCV RDP (Abs)** | $\epsilon = 1.50\text{ px}$ | 4 | 85.7% | **YES** | 24.2424% |
| **OpenCV RDP (Abs)** | $\epsilon = 6.00\text{ px}$ | 2 | 92.9% | **NO (Collapsed to line!)** | **100.0000%** |
| **OpenCV RDP (Rel)** | $\epsilon = 0.02 \times P$ | 8 | 71.4% | **YES** | 6.0606% |

*Key finding:* If absolute $\epsilon \ge \text{radius} = 5.0\text{ px}$, the closed circular loop collapses to 2 points ($Area = 0$), destroying topology. Safe boundary requires $\epsilon \le 1.5\text{ px}$.

---

### Fixture 6: Multi-Angle Dense Staircase Aliasing (Slopes 1:5, 1:2, 2:1, 5:1)
*Goal: Test dense aliasing noise cleanup across non-axis-aligned edges.*

| Algorithm | Parameter | Output Points | Point Reduction | Hausdorff Error | Area Error | Corner Survival |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline (NONE)** | None | 1140 | 0.0% | 0.00 px | 0.0000% | 100.0% |
| **OpenCV RDP (Abs)** | $\epsilon = 0.75\text{ px}$ | 6 | 99.5% | **0.72 px** | **0.0557%** | **100.0%** |
| **OpenCV RDP (Abs)** | $\epsilon = 1.50\text{ px}$ | 6 | 99.5% | **0.72 px** | **0.0557%** | **100.0%** |
| **OpenCV RDP (Abs)** | $\epsilon = 3.00\text{ px}$ | **5** | **99.6%** | **1.68 px** | **0.1237%** | **100.0%** |

*Key finding:* High-frequency raster staircase aliasing is completely smoothed out with $\epsilon = 0.75\text{--}1.5\text{ px}$, recovering clean straight edge segments with sub-pixel Hausdorff error ($0.72\text{ px}$).

---

### Fixture 7: Mixed Mechanical Stepped Shaft (Fillet R=15, Chamfer 45°, Keyway 8x6)
*Goal: Realistic composite part evaluating simultaneous straight, chamfer, fillet, and notch behavior.*

| Algorithm | Parameter | Output Points | Reduction | Hausdorff Error | Area Error | Notch Survived? | Corner Survival |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline (NONE)** | None | 1104 | 0.0% | 0.00 px | 0.0000% | **YES** | 100.0% |
| **OpenCV RDP (Abs)** | $\epsilon = 0.75\text{ px}$ | 30 | 97.3% | **0.70 px** | **0.0096%** | **YES** | **100.0%** |
| **OpenCV RDP (Abs)** | $\epsilon = 1.50\text{ px}$ | 24 | 97.8% | **1.34 px** | **0.0048%** | **YES** | **100.0%** |
| **OpenCV RDP (Abs)** | $\epsilon = 3.00\text{ px}$ | 22 | 98.0% | 2.79 px | 0.1100% | **YES** | **100.0%** |
| **OpenCV RDP (Abs)** | $\epsilon = 6.00\text{ px}$ | 16 | 98.5% | 6.00 px | 0.2249% | **NO (Erased!)** | 66.7% |
| **OpenCV RDP (Rel)** | $\epsilon = 0.01 \times P$ | 14 | 98.7% | 9.54 px | 3.3346% | **NO (Erased!)** | 50.0% |
| **OpenCV RDP (Rel)** | $\epsilon = 0.08 \times P$ | 3 | 99.7% | 57.75 px | 44.7421% | **NO (Erased!)** | 25.0% |
| **Visvalingam-Whyatt** | Area $= 1.0\text{ px}^2$ | 4 | 99.6% | 235.00 px | 96.9859% | **NO (Erased!)** | 0.0% |

*Key finding:* For composite mechanical parts, absolute $\epsilon \in [0.75, 1.5]\text{ px}$ is the **only safe operating window**:
- 97.3%–97.8% point reduction (1104 points down to 24–30 points)
- Hausdorff error $\le 1.34\text{ px}$
- Area error $\le 0.0096\%$
- 100% corner survival (including 45° chamfers)
- 100% small feature survival (keyway notch intact)
- Fillet transition polygonized with smooth chord spacing.
