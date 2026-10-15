# Research: Line Detection Loss & Endpoint Ink Ray-Marching

- **Target Issue:** duongchi90/cad-agent#491
- **Focus:** `primitive_ir_lib/geometry_extraction.py::extract_lines`
- **Causal Defect:** LINE_DETECTION_LOSS on CASE01 arrowhead endpoints under `real_scan_tuned_v1`
- **Status:** Complete. Implementation ready for Luna.
- **Production Transfer Authorized:** NO (Handoff to Luna)

---

## Summary of Findings

1. **Failure Localization:**
   Hough line detection with `maxLineGap=5` prematurely terminates at $y=224$ and $y=364$ because Canny edge pixels depart from the line axis around the solid arrowhead flare, creating a 9-pixel edge gap along the central column.
2. **Rejection of Naive Gap Increases:**
   Increasing `maxLineGap=10` bridges intentional text gaps in other drawings (e.g. NIST FTC-11), manufacturing false geometry.
3. **Surviving Solution:**
   `_extend_line_along_ink` ray-marches from Hough endpoints into the adjacent raster. It extends lines through solid ink (recovering arrowhead tips up to extension lines in CASE01) while stopping dead within 1–2 px of hitting background white paper (preserving intentional gaps in FTC-11 and dashed lines).
4. **Verification:**
   Validated via `TRANSFER_ORACLE.py` across:
   - Synthetic arrowhead tip recovery (recovers 44 px of arrowhead tips up to boundary)
   - Synthetic intentional gap preservation (0.0 px gap invasion)
   - Synthetic dashed line negative control (no bridging across white gaps)
   - Degenerate inputs (zero length, non-finite, out of bounds)
   - Frozen CASE01 hash-bound render (recovers full span $y=208\dots 379$, passing Luna's regression)

## Files
- `TRANSFER_ORACLE.py`: Executable test suite and reference algorithm.
- `benchmark_results.json`: Frozen machine output from oracle run.
- `BEHAVIORAL_CONTRACT_AND_INVARIANTS.md`: Specification, invariants, and mathematical definitions.
