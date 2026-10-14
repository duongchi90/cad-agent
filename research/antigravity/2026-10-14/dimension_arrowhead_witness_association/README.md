# Proactive Research Precompute: Dimension Arrowhead & Witness Line Association (REA-021)

- **Document ID:** `REA_DIMASSOC_PRECOMPUTE_V1`
- **Executor Role:** `CAD_AGENT_REA_GHIDRA_CROSS_MACHINE_RESEARCH_EXECUTOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Basis Commit:** `86318afc722939d88f355437e55405d012cba356` (`origin/main`)
- **Research Branch:** `research/antigravity-2026-10-11`
- **Production Status:** `RESEARCH_ONLY = YES`, `PRODUCTION_CODE_CHANGE = NO`, `PR505_CHANGE = NO`, `AUTOCAD_MUTATION = NO`
- **Correction:** `CLAIM_CORRECTED_2026-10-14` — Oracle scope, owner mapping, invariant scope, and provenance corrected per PO review.

---

## 1. Executive Summary & Objective

In engineering drawings, linear dimensions consist of three distinct entity types:
1. **Dimension Line:** Collinear or parallel to the measured dimension, carrying arrows at both ends.
2. **Extension / Witness Lines:** Typically perpendicular (or oblique) lines extending from the feature definition points to beyond the dimension line.
3. **Dimension Text:** Numerical measurement value and optional tolerance annotations placed along or above the dimension line.

In current production code (`primitive_ir_lib/cross_validation.py`), association between dimension text and CAD line primitives relies on an unconstrained Euclidean nearest-neighbor search (`find_nearest_line`). When dimension text is placed near a corner or on narrow features, witness lines are often geometrically closer to the text centroid than the dimension line itself. Because witness lines represent the offset distance (e.g. 15mm) rather than the measured span (e.g. 100mm), this triggers a false positive discrepancy (delta = 85%), marking valid drawing dimensions as conflicts (`status = "conflict"`).

This research package formulates the formal behavioral contracts, geometric invariants, discriminator algorithm, and a deterministic standalone Python test oracle. It is a `RESEARCH_PRIOR` only — it does NOT modify production code and does NOT constitute a production transfer authority.

---

## 2. Directory & Deliverables Map

```text
research/antigravity/2026-10-14/dimension_arrowhead_witness_association/
├── README.md                                  # Master precompute documentation (this file)
├── EXTERNAL_PRIOR_AND_SPEC_REPORT.md          # Provenance: ISO 129-1, ASME Y14.5, LibreCAD, DXF (corrected license classification)
├── BEHAVIORAL_CONTRACT_AND_INVARIANTS.md      # Formal invariants and geometric heuristics (corrected scope classification)
├── DISCRIMINATOR_ALGORITHM.md                 # 3-Stage discriminator algorithm specification
├── CAD_AGENT_OWNER_MAP.md                     # Existing owner mapping with gap analysis (corrected — P1/P2 are GAPs, not existing facts)
├── CODE_AVOIDANCE_ANALYSIS.md                 # Avoided engineering activities (hypothesized, not measured product RED)
└── TRANSFER_ORACLE.py                         # Standalone clean-room research oracle (100% PASS, 4/4 synthetic test cases)
```

---

## 3. Core Geometric Invariants & Mathematical Formulation

### Invariant 1: Collinear/Parallel Alignment of Dimension Line and Text
For any linear dimension with text rotation angle $\theta_{\text{text}}$ and dimension line angle $\theta_{\text{dim}}$:
$$\Delta\theta(\theta_{\text{dim}}, \theta_{\text{text}}) = \min(|\theta_{\text{dim}} - \theta_{\text{text}}| \pmod{180^\circ}, 180^\circ - (|\theta_{\text{dim}} - \theta_{\text{text}}| \pmod{180^\circ})) \le \epsilon_{\text{angle}}$$
Where default tolerance $\epsilon_{\text{angle}} = 10^\circ$ (`IMPLEMENTATION_HEURISTIC`).

### Invariant 2: Perpendicularity of Witness Lines (Perpendicular Case Only)
For standard linear dimensions where witness lines are perpendicular to the dimension line:
$$|\Delta\theta(\theta_{\text{wit}}, \theta_{\text{text}}) - 90^\circ| \le \epsilon_{\text{angle}}$$
Lines satisfying this condition are witness/extension line candidates. **Note:** Oblique extension lines (permitted in ISO 129-1 / ASME Y14.5 for angled features) will NOT satisfy this condition and must not be misclassified as contour lines.

### Invariant 3: Arrowhead Flip Threshold Rule (Observed Behavioral Heuristic)
An observed behavioral pattern in LibreCAD (`IMPLEMENTATION_HEURISTIC`, not a universal standard):
$$L < 2 \cdot S_{\text{arrow}} + W_{\text{text}}$$
When feature span $L$ satisfies this condition, arrowheads flip outward. Different CAD applications may use different thresholds.

---

## 4. Test Oracle Results (`TRANSFER_ORACLE.py`)

> **EVIDENCE_TIER:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE`
>
> `TRANSFER_ORACLE.py` is a **standalone clean-room prototype** using synthetic test inputs. It is **NOT** a call through the current production `cross_validate()` function, `find_nearest_line()`, or `builder.py`. Passing these synthetic tests does NOT constitute a production transfer GREEN.
>
> Production transfer requires: `MEASURED_CURRENT_PRODUCT_RED` on a real drawing + integration into the actual owner (`primitive_ir_lib/cross_validation.py`) + product test suite passing.

Execution command:
```powershell
python research/antigravity/2026-10-14/dimension_arrowhead_witness_association/TRANSFER_ORACLE.py
```

Output:
```text
=== Running Dimension & Witness Line Association Oracle Tests ===
Test 1 PASS: Standard horizontal dimension correctly associated.
Test 2 PASS: Witness-line misbinding trap successfully avoided.
Test 3 PASS: Arrowhead outward flip threshold accurately verified.
Test 4 PASS: 45-degree aligned dimension and orthogonal witness lines verified.

ALL 4 TEST CASES PASSED (100% Success). Oracle verified.
```

---

## 5. Catalog Registration

This research is registered in `research/antigravity/2026-10-11/REA_CATALOG.md` under:
- **Identifier:** `REA-021`
- **Topic:** `DIMENSION_ARROWHEAD_WITNESS_ASSOCIATION`
- **Disposition:** `RESEARCH_PRIOR` (per PO policy: requires measured product RED before production promotion)
- **Reuse Class:** `ALGORITHM_TRANSFER`
- **Evidence Tier:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE` (corrected from prior `VERIFIED_ALGORITHM_AND_ORACLE`)
