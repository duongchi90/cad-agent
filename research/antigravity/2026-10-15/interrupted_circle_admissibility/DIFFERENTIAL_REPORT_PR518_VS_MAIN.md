# Differential Analysis: Current Main vs Former PR #518 vs Candidate F

**Campaign ID:** `ANTI-INTERRUPTED-CIRCLE-ADMISSIBILITY-V1-20261015`
**Phase:** 30
**Date:** 2026-10-15
**Status:** Frozen Differential Analysis

---

## 1. Executive Comparison

| Dimension | Current Main (`6c50a4b6`) | Former PR #518 (`d7764f9b`) | Candidate F + Hybrid Gate |
| :--- | :--- | :--- | :--- |
| **Max Radius Search Bound** | 80 px (hardcoded in `real_scan_tuned_v1`) | 400 px | 400 px |
| **Recovery of Large Circles ($r > 80\text{ px}$)** | **0%** (drops P03, P22 Payloadchamber Ø50) | **50%** (recovers P03, drops P22) | **100%** (recovers P03, P22) |
| **Interrupted / Dimensioned Circle Admission** | Admitted if Hough votes; no verification | **0%** (completely rejects P08, P22) | **100%** (admits via gap explanation) |
| **Open Arc Rejection ($30^\circ - 330^\circ$)** | **FAILED** (admits N05, N06, N07, N08, N09) | **100% PASS** (rejects all N01–N16) | **100% PASS** (rejects all N01–N16) |
| **Text Glyph Role Separation ('O', '0')** | None in `extract_circles` | Filters OCR character boxes in `run_image` | Role gate + size/context suppression |
| **Failure Modes** | High False Positives on Arcs & Hatch | Severe False Negatives on Dimensioned Parts | Requires OCR context for text glyphs |

---

## 2. What Former PR #518 Fixed

1. **Large Radius Recovery for Isolated Circles:**
   - Expanded search preset `max_radius` from 80 px to 400 px, enabling detection of large engineering circles such as `motor-mount-top` main-view circle ($r \approx 312.5\text{ px}$).
2. **Elimination of Spurious Open Arcs:**
   - Raw OpenCV HoughCircles detects circular arcs as full circles (e.g. semicircles, quarter arcs, 300° arcs).
   - PR #518 eliminated false arcs by requiring a complete closed contour in `cv2.findContours`.
3. **Suppression of Title Block Text Glyphs:**
   - Introduced `_ocr_character_boxes` in `primitive_ir_lib/run_image.py` to withhold circle promotion when a detected circle corresponds to an OCR-confirmed 'o' or '0' character box.

---

## 3. What Former PR #518 Broke (The Causal Core of PO Closure)

1. **Topological Contradiction with Real Engineering Drawings:**
   - PR #518 implemented `_fit_supported_circle_contours`, which demanded:
     1. A single continuous closed contour from `cv2.findContours(edges, cv2.RETR_LIST)`.
     2. Every point on that contour must satisfy $|d_r| \le \sqrt{2}\text{ px}$.
     3. Maximum angular gap between consecutive points on the contour must satisfy $\Delta \theta \le 2\arcsin\left(\frac{\text{bound}}{2r}\right)$ (pixel-spacing bound).
   - **The Breaking Mechanism:**
     - In real mechanical drawings (e.g. `payloadchamber.pdf`), circles are intentionally intersected by dimension lines, witness lines, centerlines, and leader lines.
     - An intersection creates a 3-way or 4-way edge junction. `cv2.findContours` branches along the intersecting line, contaminating the contour with non-circular points ($d_r \gg \sqrt{2}\text{ px}$) or fragmenting the circle into multiple disconnected sub-contours.
     - Each sub-contour has large angular gaps across the missing segments ($\gg \text{pixel-spacing bound}$).
   - **Result:**
     - The authentic Ø50 circle from `payloadchamber.pdf` (vector path #17, $r = 106.32\text{ px}$) was **100% rejected** by PR #518.
     - Any circle intersected by a dimension line or partially occluded by a dimension text box was **100% rejected**.

---

## 4. Why Candidate F Solves the Dilemma Without False Arcs

Candidate F replaces topological contour closure with **Circumferential Support + Transversal Gap Explanation**:
1. **Distributed Binned Support:**
   - Divides circumference into 72 angular bins ($5^\circ$ each).
   - Bins are supported if edge points satisfy derived position and normal bounds ($d_r \le \epsilon_{\text{pos}}$ and $\Delta \phi \le \epsilon_{\text{normal}}$).
2. **Transversal Secant Crossing Invariant:**
   - Any gap larger than pixel quantization must be explained by an observed occluder.
   - An occluder line must physically cross the circle boundary transversally ($\min(d_0, d_1) < r - \epsilon$ and $\max(d_0, d_1) > r + \epsilon$).
   - Tangential chords or lines stopping short (Attacks 1 & 2) fail the transversality test and cannot explain the gap.
3. **Provable Outcome:**
   - Interrupted circles with crossing dimension lines (P05, P06, P07, P08, P22) have their gaps explained $\to$ **ADMITTED**.
   - Partial arcs (N01 through N16) have unexplained gaps with no crossing occluder $\to$ **REJECTED**.
