# VALIDATED_TOOL_CAPABILITIES: Empirically Proven REA + Ghidra Operations

- **Document ID:** `REA_VALIDATED_TOOL_CAPABILITIES_V1`
- **Executor Role:** `ANTIGRAVITY_REA_BENCHMARK_AUDITOR_AND_TRUE_BLIND_VALIDATOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`

---

## 1. Verified Tool Operational Boundaries

The following operations of the REA + Ghidra 12.1.4 integration on Windows 10/11 x64 are proven to function correctly and stably:

### A. Binary Ingestion & Parsing
- **Format Support:** Accurately imports and parses PE32 (x86) and PE32+ (x86-64) executables.
- **Header & Layout Recovery:** Recovers DOS headers, PE headers, section tables (`.text`, `.rdata`, `.data`, `.reloc`, etc.), base addresses, memory protections, and entry points.
- **Import Table Reconstruction:** Correctly parses imported DLLs and functions from `.idata` (e.g. `KERNEL32.DLL`, `MSVCR*.DLL`).

### B. Procedure Enumeration & Disassembly
- **Entry Point Identification:** Automatically identifies function prologues and procedure boundaries in stripped native binaries without PDB files or symbol tables.
- **Assembly Decoding:** Accurately disassembles instruction streams across standard x86 and x64 ISAs, including SSE/AVX vector instructions and conditional jump logic.
- **Cross-Reference Indexing:** Correctly indexes call sites (callees, callers) and data references (global pointers, string literals, constant floating-point IEEE-754 bit patterns).

### C. Decompilation Pseudocode
- **Control Flow Structuring:** Ghidra's decompiler successfully reconstructs structured `if/else`, `while`, `for`, and `switch` statements from native branch topologies.
- **Arithmetic Expression Recovery:** Reconstructs floating-point expressions (e.g., Euclidean distance, vector cross products, determinant calculations) with arithmetic fidelity.
- **Guard & Error Path Mapping:** Isolates input validation guards, bounds checks, and negative return codes.

### D. Differential Localization Mechanics
- **Change Detection:** When presented with two versions of a binary, comparing decompilation and disassembly reliably isolates modified functions, new conditional branches, altered constants, and changed error codes.

---

## 2. Operational Caveats & Execution Constraints
1. **Cold Launch Latency:** Headless Ghidra launches an ephemeral Java VM project per query, resulting in ~18–35 seconds of execution overhead on Windows.
2. **Type Propagation Boundaries:** In stripped binaries, pointer arguments frequently decompile as generic integer pointers (`undefined8*`, `longlong*`) or flat offset arrays. Inspection of disassembly (`MOVQ`, `MOVSD`) is required to confirm exact data types.
3. **Compiler Inlining:** Aggressive compiler optimization (`/O2` or `-O3`) inlines short leaf helpers, merging their operations into callers and concealing their distinct identity in the procedure list.
