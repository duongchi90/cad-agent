# Fidelity Reconstruction CLI Plan

**Status:** Completed

**Base SHA:** `506b9cc93f6649b2521a73861d02f1985f2cd102`

**Completion Head SHA:** `ef7140dd0e20b1db79391b0e53ff3e7471c38f7f`

**Verification:** `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` -> exit `0`; `327 passed, 6 deselected`. Private real-data evidence ran with the approved PDF and all nine approved text-reconstruction DXFs.

1. Completed: Add common fidelity context integrity and Mechanical provenance refusal.
2. Completed: Add SHA-bound page-region approval and an approved-region geometry candidate.
3. Completed: Add sidecar audits for OCR/table/linetype and Unicode candidate-text gate. Hash-bound OCR candidate observations, explicit per-text approvals, and local Unicode glyph-render validation are available; text remains outside DXF until a separate approved reconstruction step.
4. Completed: Compose approved regions and run the private nine-page reconstruction gate.
5. Completed: Integrate the CLI, focused tests, official verifier, private nine-page evidence, approved OCR-text reconstruction, and a fresh status entry. Follow-on work for dimensions, linetypes, hatch, and table-to-DXF mapping requires its own approved scope.

Required evidence: three independent reviews, synthetic tests, official
verification, and the approved private-PDF gate. AutoCAD Mechanical is NOT RUN
for fidelity unless a future approved profile explicitly changes that boundary.
