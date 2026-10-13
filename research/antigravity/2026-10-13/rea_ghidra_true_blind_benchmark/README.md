# Independent Blind Benchmark: REA + Ghidra Practical Capability Evaluation

- **Document ID:** `REA_TRUE_BLIND_PACKAGE_README_V1`
- **Executor Role:** `ANTIGRAVITY_REA_BENCHMARK_AUDITOR_AND_TRUE_BLIND_VALIDATOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Upstream Target:** Ghidra Version Tracking Training Target (`WallaceSrc.exe` & `WallaceVersion2.exe`)
- **License:** Apache-2.0 (National Security Agency / Ghidra Project)
- **Protocol:** Strict pre-reveal blind freeze with cryptographic verification

---

## 1. Overview & Objective

To establish a genuinely independent, uncontaminated capability benchmark for REA + Ghidra 12.1.4, this package evaluated pre-existing, independently authored native Windows PE binaries shipped with the Ghidra training distribution. Zero source code was authored by Anti, and zero source files were read or inspected until after blind findings were cryptographically frozen.

---

## 2. Package Directory Map

```text
research/antigravity/2026-10-13/rea_ghidra_true_blind_benchmark/
├── README.md                            # Benchmark package overview and governance
├── TARGET_FREEZE.md                     # Upstream metadata and binary target identity
├── BLIND_FINDINGS.md                    # Detailed findings extracted prior to source reveal
├── BLIND_BEHAVIORAL_SPEC.md             # Clean-room C++ specification and output prediction
├── BLIND_FREEZE_HASHES.txt              # Cryptographic SHA256 hashes of pre-reveal documents
├── SOURCE_REVEAL_COMPARISON.md          # 1-to-1 comparison against revealed upstream source
├── TRUE_BLIND_SCORECARD.md              # Measured capability scores on this target
├── scripts/                             # REA automated query and diff extraction scripts
└── logs/                                # Raw JSON outputs from REA/Ghidra operations
```

---

## 3. Cryptographic Verification Chain

```text
TARGET_A_BINARY_SHA256          = 168a175ccf74e80899d2519bbe6e1ae8b0fa2489af70e8cc0720afab1ad8b0ab
TARGET_B_BINARY_SHA256          = 94510664e6578bec7391d6023af414e2d2d8c4ff58ed3f618dd549ff648015cf
BLIND_FINDINGS_SHA256           = 177eb74ca69e85c45f39fceb5694e19a0ee98e62f5cbfbab4b8901f24af1ec37
BLIND_BEHAVIORAL_SPEC_SHA256    = fc5982e0878b1b46a98a7ef1cea7ce0ec155f64955e86eaa3e907418f91f1467
PRE_REVEAL_FROZEN_TIMESTAMP     = 2026-10-14T00:56:25+07:00
```

---

## 4. Key Benchmark Conclusions

1. **Independent Blind Accuracy:** On this target, Ghidra 12.1.4 via REA successfully recovered 100% of procedure entry points (8/8), calling conventions (`__thiscall` vs `__cdecl`), data structures (44-byte `Person` struct, 16-byte `Gadget` class), string constants, and algorithms.
2. **Differential Accuracy:** The differential comparison between `WallaceSrc.exe` and `WallaceVersion2.exe` isolated all 3 code modifications without error: removal of `rand()` import, shift from randomized to modulo 3 flag initialization, and expansion of the deployment condition.
3. **Generalization Boundary:** While this benchmark demonstrates that REA + Ghidra delivers Class A/B capability on modular C++ PE binaries, `GENERALIZATION_STATUS = UNKNOWN` is formally maintained. Generalization to large commercial CAD binaries requires evaluating multi-megabyte PE files with vtables and whole-program optimizations.
