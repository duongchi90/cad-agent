# Fidelity Reconstruction CLI Plan

**Status:** Executing

**Base SHA:** `506b9cc93f6649b2521a73861d02f1985f2cd102`

1. Completed: Add common fidelity context integrity and Mechanical provenance refusal.
2. Completed: Add SHA-bound page-region approval and an approved-region geometry candidate.
3. Executing: Add sidecar audits for OCR/table/linetype and Unicode candidate-text gate. Hash-bound OCR candidate observations exist; per-text approval and glyph rendering remain.
4. Completed: Compose approved regions and run the private nine-page reconstruction gate.
5. Executing: Integrate the CLI, focused tests, official verifier, and fresh status entry.

Required evidence: three independent reviews, synthetic tests, official
verification, and the approved private-PDF gate. AutoCAD Mechanical is NOT RUN
for fidelity unless a future approved profile explicitly changes that boundary.
