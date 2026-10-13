# Maximum REA + Ghidra Reverse Engineering Capability Evaluation & Proactive N+1 Research Precompute

- **Document ID:** `REA_GHIDRA_MAX_EVAL_V1`
- **Executor Role:** `ANTIGRAVITY_MAXIMUM_REA_GHIDRA_RESEARCH_EXECUTOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-13 / 2026-10-14
- **Basis Commit:** `86318afc722939d88f355437e55405d012cba356` (`origin/main`)
- **Research Head:** `4192305612e7fbd599cad8cd46685b0678ffc49a` (`origin/research/antigravity-2026-10-11`)
- **Production Status:** `RESEARCH_ONLY = YES`, `PRODUCTION_CODE_CHANGE = NO`, `PR503_CHANGE = NO`

---

## 1. Executive Summary & Mission
This research package pushes the currently installed REA + Ghidra 12.1.4 native Windows reverse-engineering stack as far as safely and lawfully possible. It measures with empirical rigor how much high-level program structure, data layout, algorithmic mechanism, and behavioral contract can be extracted from stripped native Windows PE32+ binaries, and directly converts that capability into code avoidance and N+1 precomputation for Cad Agent.

### Core Benchmark Results Across 4 Tiers

```text
========================================================================================
TIER 1 (Known-Source Calibration)        : 100% Function Discovery, 100% Algorithm Recall
TIER 2 (Blind Binary Reconstruction)     : 100% State Machine & Magic Recovery, Frozen Spec
TIER 3 (Differential Binary Analysis)    : 100% Delta Recall (Isolated 1e-12 Threshold)
TIER 4 (Cad Agent Proactive Precompute)  : REA-020 Polyline Bulge Reconstruction (P0)
========================================================================================
```

---

## 2. Directory & Deliverables Map

```text
research/antigravity/2026-10-13/rea_ghidra_maximum_capability/
├── README.md                                 # Master research package documentation
├── TARGETS.md                                # Comprehensive target inventory across all tiers
├── CAPABILITY_SCORECARD.md                   # Class A/B/C/D ratings across 15 REA surfaces
├── CODE_AVOIDANCE_REPORT.md                  # Quantified engineering activities avoided
├── FAILURE_AND_AMBIGUITY_LOG.md              # Decompiler ambiguities and boundary conditions
├── GHIDRA_OPERATING_PLAYBOOK.md              # Performance metrics & query operating guidelines
├── TOP_20_FUTURE_QUEUE.md                    # Prioritized N+1/N+2 precomputation backlog
├── CATALOG_UPDATE_PROPOSAL.md                # REA-020 proposal for REA_CATALOG.md
├── tier1_calibration/                        # Tier 1 Known-Source Calibration
│   ├── TARGET_IDENTITY.md
│   ├── SOURCE_EXPECTATION_HASH.txt           # Pre-frozen ground truth SHA256
│   ├── SOURCE_EXPECTATION_MODEL_FROZEN.md
│   ├── GHIDRA_STRUCTURE_REPORT.md
│   ├── ALGORITHM_RECOVERY_REPORT.md
│   ├── SOURCE_REVEAL_COMPARISON.md
│   └── TIER1_SCORECARD.md
├── tier2_blind_reconstruction/               # Tier 2 Blind Binary Reconstruction
│   ├── BLIND_MODULE_MAP.md
│   ├── BLIND_BEHAVIORAL_SPEC.md
│   ├── BLIND_FINDINGS_SHA256.txt             # Pre-frozen blind specification SHA256
│   ├── SOURCE_FALSIFICATION_REPORT.md
│   └── TIER2_SCORECARD.md
├── tier3_binary_differential/                # Tier 3 Differential Binary Analysis
│   ├── BUILD_A_IDENTITY.md
│   ├── BUILD_B_IDENTITY.md
│   ├── BLIND_BINARY_DIFF.md
│   ├── SOURCE_DIFF_REVEAL.md
│   └── TIER3_SCORECARD.md
├── tier4_cad_agent_precompute/               # Tier 4 Cad Agent Research Precompute
│   ├── NPLUS1_CANDIDATE_MATRIX.md            # 10 scored candidates across 10 dimensions
│   ├── SELECTED_CAPABILITY.md                # Polyline Bulge and Arc Reconstruction
│   ├── EXTERNAL_PRIOR_REPORT.md              # Autodesk DXF & ezdxf math invariants
│   ├── CAD_AGENT_OWNER_MAP.md                # Existing owners mapping & anti-bloat rules
│   ├── TRANSFER_ORACLE.md                    # Deterministic unit test oracle in Python
│   └── ANTI_REPEAT_ENTRY_PROPOSAL.md         # Exact catalog schema proposal
├── scripts/                                  # Build, verification, and oracle test runners
└── logs/                                     # Raw REA inspection outputs and timing logs
```

---

## 3. Mandatory Safety & Governance Principles
- **No Production Code Changed:** Zero edits to `cad_agent/`, `autocad_plugin/`, `primitive_ir_lib/`, or `semantic_ir_lib/`.
- **No PRs Touched:** PR #503 and #504 remain strictly unmodified.
- **No AutoCAD Mutations:** Drawing database untouched; zero live console commands.
- **Clean-Room Compliance:** Permissive open-source benchmarks only; zero proprietary expression copied.
