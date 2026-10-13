# TRUE_BLIND_SCORECARD: Independent Benchmark Capability Scores

- **Document ID:** `REA_TRUE_BLIND_SCORECARD_V1`
- **Executor Role:** `ANTIGRAVITY_REA_BENCHMARK_AUDITOR_AND_TRUE_BLIND_VALIDATOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Benchmark Target:** Upstream `WallaceSrc.exe` vs `WallaceVersion2.exe` (Ghidra Version Tracking Training Suite)
- **Protocol:** Pre-existing, independently authored binary; blind freeze before source reveal.

---

## 1. Measured Capability Scores on this Target

```text
========================================================================================
EVALUATION SCORES: ON_THIS_TARGET (WallaceSrc.exe & WallaceVersion2.exe)
========================================================================================
PROCEDURE_DISCOVERY           : 8/8 (100.0%) [main, addPeople, initializePeople, addPerson,
                                             deployGadget, Gadget::Gadget, Gadget::use,
                                             Gadget::print]
CALL_GRAPH                    : 8/8 call sites (100.0%) [Correct fan-in/fan-out hierarchy]
CONSTANT_RECOVERY             : 8/8 constants (100.0%) [6 character names, 1 device name,
                                                       1 format string]
DATA_STRUCTURE_RECOVERY       : 2/2 structs (100.0%) [Person: 44 bytes, 4 fields;
                                                     Gadget: 16 bytes, 4 fields]
ALGORITHM_IDENTIFICATION      : 3/3 algorithms (100.0%) [Singly-linked list prepend traversal,
                                                        random/modulo flag assignment,
                                                        linear target search & deploy]
ERROR_PATH_RECOVERY           : 2/2 guards (100.0%) [NULL check on next pointer;
                                                    is_deployed early return check]
DELTA_LOCALIZATION            : 3/3 deltas (100.0%) [Import removal of rand();
                                                    modulo 3 flag initialization;
                                                    boolean OR branch expansion]
========================================================================================
SAMPLE_COUNT                  : 1 independent target binary pair (2 executables, 8 procs)
GENERALIZATION_STATUS         : UNKNOWN (Valid empirical result for this binary pair;
                                        cannot be generalized to arbitrary commercial
                                        CAD engines or large-scale native PE binaries)
========================================================================================
```

---

## 2. Qualitative Observations on Independent Analysis

1. **High Decompilation Quality on MSVC C++:** For standard non-obfuscated MSVC 32-bit binaries, Ghidra's decompiler produces C pseudocode that corresponds directly to the original C++ classes, constructors, methods, and member variable offsets.
2. **Calling Convention Identification:** Ghidra automatically inferred the Microsoft `__thiscall` convention for `Gadget::use` and `Gadget::Gadget`, correctly mapping `ECX` as `this`.
3. **No Symbolic Oracle Needed for Clean-Room Recovery:** Despite symbols being completely stripped from the executable, the combination of string references, memory sizes passed to `operator new`, and structured control flow enabled 100% functional reconstruction.
4. **Generalization Limit:** This benchmark confirms tool operational efficacy and algorithm recovery on small, modular C++ utilities. Complex native CAD codebases (e.g. AutoCAD ObjectARX / `acad.exe` / `acdb*.dll`) feature far larger symbol spaces, deep inheritance hierarchies, virtual method tables (vtables), template bloat, and aggressive whole-program link-time optimization (LTO) that will introduce greater ambiguity.
