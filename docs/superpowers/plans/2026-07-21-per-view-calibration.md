# Per-view Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect scale labels in mixed-scale scanned drawing sheets and attach non-production per-view calibration candidates to Primitive IR.

**Architecture:** Add a focused `view_calibration` module that parses scale labels anywhere on a page, converts a denominator to mm/px, and associates each label with a non-overlapping nearby geometry region. The page IR stays unchanged; each accepted crop becomes a separate child IR with its own local origin and `needs_verification` calibration. A candidate records optional in-region dimension cross-validation so a reviewer can see whether the declared scale agrees with detected dimensions.

**Tech Stack:** Python 3.11, dataclasses, OpenCV/Pytesseract outputs, pytest, JSON Schema Draft 2020-12.

## Global Constraints

- Use `mm_per_px = denominator * 25.4 / dpi`.
- Only status `needs_verification` is allowed for detected regions.
- Do not infer a calibrated region when label-to-region association is ambiguous.
- Preserve the existing `calibration` object and existing JSON payload compatibility.
- Do not alter existing batch artifacts under `output/`.

---

### Task 1: Scale-label parsing and conversion

**Files:**
- Create: `primitive_ir_lib/view_calibration.py`
- Create: `primitive_ir_lib/tests/test_view_calibration.py`

**Interfaces:**
- Produces: `parse_scale_label(content: str) -> int | None`
- Produces: `mm_per_px_for_scale(denominator: int, dpi: int) -> float`

- [ ] **Step 1: Write failing tests for clean and OCR-corrupted labels**

```python
from primitive_ir_lib.view_calibration import mm_per_px_for_scale, parse_scale_label

def test_parse_scale_label_accepts_common_title_variants():
    assert parse_scale_label("TL 1:40") == 40
    assert parse_scale_label("Tỷ lệ 1:8") == 8
    assert parse_scale_label("Tile 1:20") == 20
    assert parse_scale_label("4:40") is None

def test_mm_per_px_for_scale_uses_render_dpi():
    assert mm_per_px_for_scale(40, 144) == pytest.approx(7.0555555556)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv-py311\\Scripts\\python.exe -m pytest primitive_ir_lib/tests/test_view_calibration.py -v`

Expected: collection fails because `primitive_ir_lib.view_calibration` does not exist.

- [ ] **Step 3: Implement the minimal parser and converter**

```python
_SCALE_RE = re.compile(r"(?:TL|TY\\s*LE|TILE)\\s*[-:]?\\s*1\\s*:\\s*(\\d+)", re.I)

def parse_scale_label(content: str) -> int | None:
    normalized = unicodedata.normalize("NFD", content).encode("ascii", "ignore").decode().upper()
    match = _SCALE_RE.search(normalized)
    return int(match.group(1)) if match else None

def mm_per_px_for_scale(denominator: int, dpi: int) -> float:
    if denominator <= 0 or dpi <= 0:
        raise ValueError("denominator and dpi must be positive")
    return denominator * 25.4 / dpi
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `.venv-py311\\Scripts\\python.exe -m pytest primitive_ir_lib/tests/test_view_calibration.py -v`

Expected: all tests pass.

### Task 2: Manifest contract for reviewable child IRs

**Files:**
- Modify: `primitive_ir_lib/run_pdf.py`
- Modify: `primitive_ir_lib/tests/test_run_pdf.py`

**Interfaces:**
- Produces: manifest `view_candidates` entries with `bbox_px`,
  `scale_denominator`, `pixel_to_unit_scale`, `source_text_id`, `status`, and
  optional `child_ir`.

- [ ] **Step 1: Write a failing manifest test**

```python
def test_run_pdf_manifest_serializes_unverified_view_candidate():
    manifest = run_pdf(..., view_candidates=[candidate])
    assert manifest["view_candidates"] == [{
        "bbox_px": [100, 200, 500, 600],
        "scale_denominator": 40,
        "pixel_to_unit_scale": pytest.approx(7.0555555556),
        "source_text_id": "rawtext-scale",
        "status": "needs_verification",
    }]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv-py311\\Scripts\\python.exe -m pytest primitive_ir_lib/tests/test_run_pdf.py -k view_candidate -v`

Expected: manifest does not yet contain `view_candidates`.

- [ ] **Step 3: Add optional manifest entries without changing the page IR schema**

```python
manifest["view_candidates"] = [{
    "bbox_px": list(candidate.bbox_px),
    "scale_denominator": candidate.scale_denominator,
    "pixel_to_unit_scale": candidate.pixel_to_unit_scale,
    "source_text_id": candidate.source_text_id,
    "status": "needs_verification",
}]
```

Do not modify `primitive_ir.schema.json`; candidates are page-manifest review
metadata until a crop is deliberately emitted as its own IR.

- [ ] **Step 4: Run focused model/schema tests**

Run: `.venv-py311\\Scripts\\python.exe -m pytest primitive_ir_lib/tests/test_run_pdf.py -v`

Expected: all tests pass.

### Task 3: Full-page label discovery and geometry-region association

**Files:**
- Modify: `primitive_ir_lib/view_calibration.py`
- Modify: `primitive_ir_lib/run_image.py`
- Modify: `primitive_ir_lib/run_pdf.py`
- Modify: `primitive_ir_lib/tests/test_view_calibration.py`
- Modify: `primitive_ir_lib/tests/test_run_pdf.py`

**Interfaces:**
- Produces: `detect_view_candidates(raw_texts, raw_lines, image_width, image_height, dpi) -> list[ViewCandidate]`
- Consumes: OCR `RawText`, raw geometry, and rendered-page DPI.

- [ ] **Step 1: Write failing tests for conservative region selection**

```python
def test_detect_candidates_scans_labels_anywhere_on_page():
    labels = [_text("TL-1:5", (490, 150, 620, 180), id_="scale")]
    assert parse_scale_label(labels[0].content) == 5

def test_detect_candidates_rejects_ambiguous_label_to_region_assignment():
    label = _text("TL-1:5", (600, 300, 650, 330), id_="scale")
    assert detect_view_candidates([label], [left_region, right_region], 1200, 800, 144) == []

def test_candidate_records_in_region_dimension_delta():
    candidate = detect_view_candidates([scale_label, dimension_text], [dimension_line], 1200, 800, 144)[0]
    assert candidate.dimension_delta_percent == pytest.approx(0.0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv-py311\\Scripts\\python.exe -m pytest primitive_ir_lib/tests/test_view_calibration.py -v`

Expected: `detect_view_candidates` is unavailable; the first test demonstrates that label discovery is independent of title-block position.

- [ ] **Step 3: Implement full-page association and candidate evidence**

```python
def detect_view_candidates(raw_texts, raw_lines, image_width, image_height, dpi):
    # Parse every OCR scale label regardless of page position.
    # Cluster nearby lines into candidate view boxes; assign only when the
    # label has one nearest non-overlapping box within the distance limit.
    # Compare candidate scale with dimension-text/line pairs contained by that box.
```

Pass `dpi` from `run_pdf` to `run_image`; retain page IR unchanged. Persist
unassigned labels and ambiguous associations in the manifest. Only when a
candidate has a non-overlapping crop boundary and a recorded evidence result,
call `run_image` on that crop with its candidate scale and emit the child path.

- [ ] **Step 4: Run focused and regression tests**

Run: `.venv-py311\\Scripts\\python.exe -m pytest primitive_ir_lib/tests/test_view_calibration.py primitive_ir_lib/tests/test_run_pdf.py -v`

Expected: all tests pass.

### Task 4: Batch verification and review documentation

**Files:**
- Modify: `README.md`
- Create: `output/pdf/per_view_calibration_review.json` (generated, untracked)

- [ ] **Step 1: Document the safety boundary**

Add a README note that labels are found across the full page, and that only a
non-ambiguous label-to-geometry region with recorded cross-validation evidence
can become a review-only child IR; no candidate enables CAD-scale DXF export.

- [ ] **Step 2: Run the complete regression suite**

Run: `$env:PATH='C:\\Program Files\\Tesseract-OCR;'+$env:PATH; .venv-py311\\Scripts\\python.exe -m pytest primitive_ir_lib/tests -q`

Expected: all tests pass.

- [ ] **Step 3: Re-run the five-PDF batch and summarize candidates**

Run: `.venv-py311\\Scripts\\python.exe -m primitive_ir_lib.run_pdf --pdf <pdf> --output-dir output\\pdf\\per_view_calibration --auto-calibrate --auto-ocr-roi --merge-lines --dpi 144`

Expected: every page still writes Primitive IR; candidate regions are `needs_verification`; no candidate is treated as a production scale.

- [ ] **Step 4: Verify output integrity**

Run: `.venv-py311\\Scripts\\python.exe -m pytest primitive_ir_lib/tests -q`

Expected: no test failures; confirm generated JSON parses and all candidate statuses equal `needs_verification`.
