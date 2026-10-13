# FAILURE_AND_AMBIGUITY_LOG: Edge Cases, Ambiguities, and Failure Modes

## 1. Decompiler Ambiguities Identified During Benchmark

1. **Struct Type Demotion:**
   - **Observation:** In stripped PE binaries, Ghidra's decompiler frequently represents pointer-to-struct types (e.g. `CadPoint2D*`) as generic integer pointers (`undefined8*`, `longlong*`, or `double*`).
   - **Ambiguity:** Field access `p->y` is presented as `*(double *)(p + 8)` or `*(undefined8 *)(p + 1)`.
   - **Resolution:** Reconstructed offsets across multiple callers and checked memory width (8 bytes = IEEE 754 float).

2. **Aggressive Compiler Optimization (-O2):**
   - **Observation:** Tiny leaf functions (e.g. `cadgeom_bbox_expand` or coordinate limit validators) are often inlined directly into callers at `-O2`, eliminating the discrete call edge in the call graph.
   - **Ambiguity:** The decompiler shows the inlined logic inside the caller without an explicit `CALL` instruction.
   - **Resolution:** Correlated with assembly disassembly (`procedure_assembly`). When an instruction sequence repeats across multiple caller locations, an inlined helper is deduced.

3. **Tail-Call Optimization (TCO):**
   - **Observation:** When a function calls another as its final statement, MSVC emits a `JMP` rather than `CALL ... RET`.
   - **Ambiguity:** Ghidra's control-flow graph may interpret this jump as an unconditional jump rather than a function call.
   - **Resolution:** Cross-checked target address against `.text` procedure start boundaries.

4. **Floating-Point Representation in Disassembly:**
   - **Observation:** Immediate floating-point constants are loaded from `.rdata` via RIP-relative addressing (e.g. `movsd xmm0, [RIP + 0x1234]`).
   - **Ambiguity:** The raw instruction references a memory address, not a decimal value.
   - **Resolution:** Read memory bytes at the target address using `read-bytes` or check normalized constants in Ghidra data references.

---

## 2. When Ghidra Becomes Ambiguous and Requires Higher Oracles
- When decompiled code exhibits vector SIMD intrinsics (AVX2 / SSE4) where pseudocode is obfuscated, direct **assembly inspection** is required.
- When dynamic library dispatch or virtual methods (`vtable`) are used, static xrefs must be augmented with **runtime execution observation** or **source ground truth**.
- If a data relationship remains ambiguous: declare **`UNKNOWN`** rather than guessing.
