# REA + Ghidra Research Package Correction & Audit

- **Document ID:** `REA_CORRECTION_PACKAGE_README_V1`
- **Executor Role:** `ANTIGRAVITY_REA_BENCHMARK_AUDITOR_AND_TRUE_BLIND_VALIDATOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Basis Main:** `86318afc722939d88f355437e55405d012cba356`
- **Research Package Basis Head:** `8168cf5d74c97a5475eb61c1168d97e49bc51b66`
- **Canonical PO Review:** [`#491 Comment 6151289810`](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6151289810)

---

## 1. Purpose of this Correction Package

Following authoritative PO review, this package formally audits, rectifies, and recalibrates the findings published under commit `8168cf5d74c97a5475eb61c1168d97e49bc51b66`. Historical commit `8168cf5d` is preserved intact as historical research evidence; this correction package establishes the refined, audit-grade research truth.

---

## 2. Directory Structure

```text
research/antigravity/2026-10-13/rea_ghidra_maximum_capability_correction/
├── README.md                            # Package overview and governance principles
├── CONTAMINATION_AUDIT.md               # Audit of synthetic benchmark self-contamination
├── CLAIM_CORRECTION_TABLE.md            # Detailed table of old claims vs corrected truth
├── VALIDATED_TOOL_CAPABILITIES.md       # Technical operations proven to work stably
├── INVALIDATED_OR_UNPROVEN_CLAIMS.md    # Formally retracted or unproven assertions
└── REA020_CORRECTION.md                 # Hardened scope & disposition for REA-020
```

---

## 3. Key Corrections Summary

1. **Benchmark Classification:** Tiers 1–3 are formally classified as `TOOL_OPERATIONAL = PROVEN_ON_TESTED_SYNTHETIC_PE_FIXTURES`, with ceiling scores classified as `SELF_CONTAMINATED_NOT_VALID_FOR_BLIND_ACCURACY`. Population-level accuracy percentages are retracted.
2. **Internal Consistency:** Removed erroneous claims that Tier 1 recovered 3-point circle fitting or that Tier 2 recovered ARC/EOF opcodes.
3. **Repository Currentness:** Explicitly designated snapshot timestamps for PR tracking and corrected PR #504 status (`OPEN/DRAFT` at `9b3ced993625...`).
4. **REA-020 Hardening:** Downgraded `REA-020` to `CURRENT_DISPOSITION = RESEARCH_PRIOR`. Acknowledged that current main `dxf_builder_lib/builder.py` emits LINE/CIRCLE/ARC (no active LWPOLYLINE generation path) and `primitive_ir_lib` lacks arc extraction.
5. **Numerical Hygiene:** Clarified that $|b| < 10^{-7}$ snapping is a `PROJECT_HEURISTIC_UNVALIDATED_FOR_PRODUCTION`, not a normative Autodesk invariant.
6. **Code Avoidance:** Relabeled all developer time estimates to `HYPOTHESIZED_DISCOVERY_REDUCTION`.
7. **Strict Non-Interference:** Zero changes to production code; zero changes to PR #500–#504; zero live AutoCAD actions; Luna remains undisturbed on #491.
