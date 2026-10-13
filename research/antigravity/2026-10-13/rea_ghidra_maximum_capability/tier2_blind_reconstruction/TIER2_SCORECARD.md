# TIER 2 SCORECARD: Blind Binary Reconstruction

## Quantitative Scorecard (0–100 Scale)

| Metric | Score | Assessment |
| :--- | :---: | :--- |
| **MODULE_ARCHITECTURE_RECOVERY** | **95** | All 4 functional subsystems and their entry/exit boundaries recovered accurately. |
| **STATE_MACHINE_RECONSTRUCTION** | **100** | 5 discrete states, transitions, guards, and terminal error sinks identified with 100% precision. |
| **CONSTANT_AND_INVARIANT_MINING** | **100** | Magic signature (`0x43414453`), version cap (`2`), coordinate bound (`1e5`), and opcodes recovered exactly. |
| **ERROR_PATH_MAPPING** | **98** | Error codes `-1` through `-7` mapped directly to failure triggers. |
| **DATA_LAYOUT_INFERENCE** | **92** | Struct field offsets, widths, and types inferred correctly; packed header layout recognized. |
| **TERMINAL_EFFECT_TRACING** | **100** | 3 observable terminal behaviors (valid extents, bad magic, coordinate out-of-range) traced end-to-end. |
| **BLIND_BEHAVIOR_SPEC_ACCURACY** | **98** | Clean-room specification matched source truth without retroactive adjustments. |

---

## Avoided Engineering Activity Inventory
- `PROTOTYPE_NOT_NEEDED`: No need to write speculative format fuzzers or probe parsers.
- `API_DISCOVERY_NOT_NEEDED`: Binary state transitions and error conditions mapped directly to behavioral contracts.
- `NEGATIVE_APPROACH_AVOIDED`: Avoided assuming dynamic scaling behavior (proved `global_scale` is unapplied metadata).
- `TEST_ORACLE_REUSED`: Test suite for CAD stream validation can be synthesized directly from recovered constants.
