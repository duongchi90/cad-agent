# CONTAMINATION_AUDIT: Formal Benchmark Classification & Evaluation Scope

- **Document ID:** `REA_CONTAMINATION_AUDIT_V1`
- **Executor Role:** `ANTIGRAVITY_REA_BENCHMARK_AUDITOR_AND_TRUE_BLIND_VALIDATOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Basis Research Head:** `8168cf5d74c97a5475eb61c1168d97e49bc51b66`
- **Basis Main:** `86318afc722939d88f355437e55405d012cba356`
- **Canonical PO Review:** [`#491 Comment 6151289810`](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6151289810)

---

## 1. Executive Assessment of Benchmark Provenance

The Tier 1, Tier 2, and Tier 3 benchmark targets in research package `8168cf5d` were authored and compiled within the same agent session prior to analysis:
- **Tier 1:** `C:\Tools\benchmarks\tier1\cadgeom_core.exe` (authored by Anti agent)
- **Tier 2:** `C:\Tools\benchmarks\tier2\cadstream_format.exe` (authored by Anti agent)
- **Tier 3:** `C:\Tools\benchmarks\tier3\tolerance_guard_v1.exe` and `v2.exe` (authored by Anti agent)

Although hash-freezing was used prior to source reveal within the execution script, the experimental protocol was fundamentally **self-contaminated** because the agent that drafted the specifications and evaluated accuracy had prior awareness of the intended problem structures, algorithms, and test envelopes.

Therefore, the previous 95%–100% scores **MUST NOT** be characterized as independent blind capability-ceiling measurements.

---

## 2. Formal Classification Matrix

```text
TOOL_OPERATIONAL                        = PROVEN_ON_TESTED_SYNTHETIC_PE_FIXTURES
SYNTHETIC_CALIBRATION_VALUE             = USEFUL
INDEPENDENT_BLIND_CAPABILITY_SCORE      = NOT_PROVEN
TIER1_CEILING_SCORE_STATUS              = SELF_CONTAMINATED_NOT_VALID_FOR_BLIND_ACCURACY
TIER2_CEILING_SCORE_STATUS              = SELF_CONTAMINATED_NOT_VALID_FOR_BLIND_ACCURACY
TIER3_CEILING_SCORE_STATUS              = SELF_CONTAMINATED_NOT_VALID_FOR_BLIND_ACCURACY
```

---

## 3. Retained Bounded Observations vs Retracted Claims

### Retained Bounded Observations (Valid Technical Facts)
1. **PE Import & Section Mapping:** Ghidra 12.1.4 successfully parses PE32+ (x86-64) and PE32 (x86) headers, virtual addresses, permissions (`.text`, `.rdata`, `.data`), and entry points.
2. **Procedure Discovery:** Automated function boundary detection recovers entry points and basic block structures in stripped MSVC PE binaries without PDB symbols.
3. **Decompiler Operation:** Ghidra decompiler produces valid, readable C pseudocode matching basic program control flow, loops, and math operations.
4. **Cross-Reference Resolution:** Data references (string literals, numeric constants) and code references (call sites) are accurately cataloged.
5. **Assembly / Pseudocode Correlation:** Where decompiler type propagation defaults to generic integers or flat buffers, inspecting disassembly (`procedure_assembly`) resolves operand semantics.
6. **Differential Mechanics:** Comparing procedure lists and decompiled logic across two builds cleanly isolates code changes down to exact numeric constants and conditional branches.

### Retracted Claims (Invalid or Overclaimed Inferences)
1. **Universal Accuracy Percentages:** Retracted claims of "100% Function Discovery", "100% Algorithm Recall", "95% Binary-Only Reconstruction", and "100% Differential Recall" as population-level or general tool capability scores.
2. **Independent Blindness:** Retracted the assertion that Tier 2 and Tier 3 constituted independent blind validations.
3. **Universal Generalization:** Retracted generalization from small, self-authored synthetic PE fixtures to complex production CAD binaries.
