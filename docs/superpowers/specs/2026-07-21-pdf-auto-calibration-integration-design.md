# PDF auto-calibration integration

## Scope

Integrate only these files from `cad-agent-updated_2.zip` into the current
checkout:

- `primitive_ir_lib/run_pdf.py`
- `primitive_ir_lib/tests/test_run_pdf.py`
- `primitive_ir_lib/run_image.py`
- `primitive_ir_lib/text_extraction.py`
- `primitive_ir_lib/calibration_registry.py`

No other ZIP file, generated artifact, documentation snapshot, or repository
metadata is copied into the checkout.

## Behaviour

`run_pdf` accepts either a verified manual scale or auto-calibration.  In
auto-calibration mode it forwards automatic OCR-region detection and
calibration options to each rendered page.  When a calibration registry is
supplied, each page receives a distinct `<prefix>_pageNN` record so its image
hash remains auditable.  The PDF manifest records `"auto"` at document level
and the resolved scale and calibration method for every page.

`run_image` supplies the forwarded options, `text_extraction` detects OCR
candidate regions, and `calibration_registry` records unverified automatic
calibrations without allowing them to be reused as verified records.

## Validation

Use the regression tests from the ZIP for missing-scale validation, missing
registry-prefix validation, and forwarding per-page IDs.  Run the relevant
Phase 1 tests after integration.  PyMuPDF-backed tests run when the installed
environment provides `fitz`.
