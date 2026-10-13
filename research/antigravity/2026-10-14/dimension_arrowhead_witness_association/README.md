# Proactive Research Precompute: Dimension Arrowhead & Witness Line Association (REA-021)

- **Document ID:** `REA_DIMASSOC_PRECOMPUTE_V1`
- **Executor Role:** `CAD_AGENT_REA_GHIDRA_CROSS_MACHINE_RESEARCH_EXECUTOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Basis Commit:** `86318afc722939d88f355437e55405d012cba356` (`origin/main`)
- **Research Branch:** `research/antigravity-2026-10-11`
- **Production Status:** `RESEARCH_ONLY = YES`, `PRODUCTION_CODE_CHANGE = NO`, `PR505_CHANGE = NO`, `AUTOCAD_MUTATION = NO`

---

## 1. Executive Summary & Objective

In engineering drawings, linear dimensions consist of three distinct entity types:
1. **Dimension Line:** Collinear or parallel to the measured dimension, carrying arrows at both ends.
2. **Extension / Witness Lines:** Orthogonal (or oblique) lines extending from the feature definition points to beyond the dimension line.
3. **Dimension Text:** Numerical measurement value and optional tolerance annotations placed along or above the dimension line.

In current production code (`primitive_ir_lib/cross_validation.py`), association between dimension text and CAD line primitives relies on an unconstrained Euclidean nearest-neighbor search (`find_nearest_line`). When dimension text is placed near a corner or on narrow features, witness lines are often geometrically closer to the text centroid than the dimension line itself. Because witness lines represent the offset distance (e.g. 15mm) rather than the measured span (e.g. 100mm), this triggers a false positive discrepancy (delta = 85%), marking valid drawing dimensions as conflicts (`status = "conflict"`).

This research package formulates the formal behavioral contracts, geometric invariants, discriminator algorithm, and deterministic Python test oracle to prevent witness-line misbinding and ensure zero production regressions.

---

## 2. Directory & Deliverables Map

```text
research/antigravity/2026-10-14/dimension_arrowhead_witness_association/
├── README.md                                  # Master precompute documentation (this file)
├── EXTERNAL_PRIOR_AND_SPEC_REPORT.md          # Industry standards (ISO 129-1, ASME Y14.5), LibreCAD, DXF
├── BEHAVIORAL_CONTRACT_AND_INVARIANTS.md      # Formal invariants, geometric proofs, and failure modes
├── DISCRIMINATOR_ALGORITHM.md                 # 3-Stage discriminator algorithm specification
├── CAD_AGENT_OWNER_MAP.md                     # Existing owner mapping (primitive_ir_lib, dxf_builder_lib)
├── CODE_AVOIDANCE_ANALYSIS.md                 # Measured work reductions and avoided engineering activities
└── TRANSFER_ORACLE.py                         # Deterministic unit test oracle (100% PASS, 4/4 test cases)
```

---

## 3. Core Geometric Invariants & Mathematical Formulation

### Invariant 1: Collinear/Parallel Alignment of Dimension Line and Text
For any linear dimension with text rotation angle $\theta_{\text{text}}$ and dimension line angle $\theta_{\text{dim}}$:
$$\Delta\theta(\theta_{\text{dim}}, \theta_{\text{text}}) = \min(|\theta_{\text{dim}} - \theta_{\text{text}}| \pmod{180^\circ}, 180^\circ - (|\theta_{\text{dim}} - \theta_{\text{text}}| \pmod{180^\circ})) \le \epsilon_{\text{angle}}$$
Where default tolerance $\epsilon_{\text{angle}} = 10^\circ$.

### Invariant 2: Orthogonality of Witness Lines
For valid witness lines with angle $\theta_{\text{wit}}$:
$$|\Delta\theta(\theta_{\text{wit}}, \theta_{\text{text}}) - 90^\circ| \le \epsilon_{\text{angle}}$$
Lines satisfying this condition are guaranteed to be witness/extension lines and MUST NOT be evaluated as dimension line candidates.

### Invariant 3: Arrowhead Flip Threshold Rule
When feature span $L$ is narrow relative to arrow size $S_{\text{arrow}}$ and text bounding box width $W_{\text{text}}$:
$$L < 2 \cdot S_{\text{arrow}} + W_{\text{text}}$$
The arrowheads flip outward ($\theta_{\text{arrow}} \to \theta_{\text{arrow}} + 180^\circ$), pointing inward toward the witness lines from the exterior.

---

## 4. Test Oracle Results (`TRANSFER_ORACLE.py`)

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
