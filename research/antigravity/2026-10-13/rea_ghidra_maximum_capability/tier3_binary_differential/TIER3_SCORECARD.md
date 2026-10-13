# TIER 3 SCORECARD: Differential Binary Analysis

## Quantitative Scorecard (0–100 Scale)

| Metric | Score | Assessment |
| :--- | :---: | :--- |
| **CHANGED_FUNCTION_RECALL** | **100** | Successfully detected both changed procedures (`cad_vector_normalize` and caller). |
| **CHANGED_FUNCTION_PRECISION** | **100** | 0 unchanged procedures flagged as false positives. |
| **BEHAVIOR_DELTA_ACCURACY** | **100** | Exact causal behavior identified: addition of degenerate length check and error propagation. |
| **CONSTANT_DELTA_ACCURACY** | **100** | Numeric constant delta ($10^{-12}$) and return code (`-10`) identified with complete precision. |
| **TEST_PREDICTION_ACCURACY** | **100** | Predicted failing input vector $(0, 0)$ verified to trigger the exact error return. |

---

## Strategic Significance for Cad Agent
- **Version Upgrade Verification:** Proves that REA can automatically detect behavioral contract changes between consecutive builds of native CAD tools or dependencies.
- **Regression Localization:** When vendor libraries or native plugins change behavior without updated documentation, differential REA isolates the exact modified instructions without source access.
- `CAN_REA_LOCALIZE_VERSION_REGRESSION = YES`.
