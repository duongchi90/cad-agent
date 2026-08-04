# VS-T1 Dimension Observer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Planned

**Planning base SHA:** `2932febe5e95b042b202a767604d2143e6a6cc4f`

**Implementation base:** Create `task/vs-t1-dimension-observer` from the fresh integrated `main` at the start of execution. Record the actual SHA in the PR body before changing code.

**Goal:** Build an offline, deterministic Dimension Observer that detects every source dimension cluster, parses values and symbols, records attachment evidence and role/status, and emits a validated `dimension_register` without inventing values or authoritative attachments.

**Architecture:** Keep recognition algorithms in `primitive_ir_lib`; `cad_agent` only coordinates files, hashes, contract validation, and artifact writing. Reuse `detect_text_candidate_rois()`, `extract_text_tesseract()`, `RawText`, OpenCV, NumPy, Tesseract, `canonical_json_sha256()`, `sha256_file()`, and the integrated VS-T0 `dimension_register` validator. No OpenAI API or AutoCAD call is made in VS-T1.

**Tech Stack:** Windows, Python 3.11, OpenCV 5, NumPy 2, Tesseract 5.4.0.20240606, pytest, existing Visual Supervisor contracts.

## Global Constraints

- Do not add a second image/PDF pipeline or duplicate Primitive IR orchestration.
- Do not infer Model Space coordinates or authoritative scale from pixels.
- A numeric OCR result without valid attachment remains `UNRESOLVED`.
- Only `CONFIRMED` plus `DRIVING` with valid `from_ref` and `to_ref` may later control geometry.
- `REFERENCE` and `DERIVED` are observation/checking roles only.
- Critical `AMBIGUOUS`, `CONFLICT`, or `UNRESOLVED` observations list their affected `blocker_scope`.
- Every detected cluster gets exactly one disposition: `CONFIRMED`, `UNRESOLVED`, `CONFLICT`, or explicit `NOT_A_DIMENSION` in observer evidence.
- `NOT_A_DIMENSION` evidence is audit-only and is not inserted into `dimension_register.dimensions`.
- Do not fabricate unreadable numbers: use `value: null` and preserve the original display text.
- Source images, crops, OCR outputs, customer data, and run directories remain outside Git.
- Synthetic tests generate images in memory or under pytest temporary directories.
- Every code task begins with a failing focused test and ends with focused tests, `git diff --check`, diff inspection, and a bounded commit.
- `real_data`, OpenAI API, and AutoCAD Mechanical remain `NOT RUN` for this slice.

---

## File Structure

### New recognition files

- `primitive_ir_lib/dimension_symbols.py` — parse numbers, decimal separators, diameter/radius/angular/repetition symbols, tolerances, and unit hints.
- `primitive_ir_lib/dimension_geometry.py` — detect dimension-line, extension-line, arrowhead, and leader candidates inside one crop.
- `primitive_ir_lib/dimension_observer.py` — cluster records, OCR candidate fusion, attachment scoring, role/status classification, and coverage accounting.

### New orchestration files

- `cad_agent/dimension_observer_run.py` — hash-bound file runner, crop/evidence writer, Dimension Register assembly, atomic JSON output, and contract validation.
- `cad_agent/run_dimension_observer.py` — CLI wrapper; no recognition logic.

### Tests

- `primitive_ir_lib/tests/test_dimension_symbols.py`
- `primitive_ir_lib/tests/test_dimension_geometry.py`
- `primitive_ir_lib/tests/test_dimension_observer.py`
- `tests/test_dimension_observer_run.py`
- `tests/test_dimension_register_runtime_policy.py`

### Contract amendment

VS-T1 needs evidence fields approved in the design but absent from the initial runtime schema. Extend the existing `dimension-register-1.0` observation object with these **optional** fields without changing existing field meanings:

```json
{
  "symbol_text": "⌀",
  "tolerance": {
    "mode": "SYMMETRIC",
    "upper": 0.2,
    "lower": -0.2,
    "unit": "mm"
  },
  "extension_geometry": {
    "dimension_line": [[100.0, 50.0], [300.0, 50.0]],
    "extension_lines": [
      [[100.0, 55.0], [100.0, 120.0]],
      [[300.0, 55.0], [300.0, 120.0]]
    ],
    "arrow_points": [[100.0, 50.0], [300.0, 50.0]]
  },
  "attachment_candidates": [
    {
      "from_ref": {"type": "DATUM", "id": "FRONT_AXLE_CENTER"},
      "to_ref": {"type": "DATUM", "id": "REAR_AXLE_CENTER"},
      "confidence": 0.94,
      "evidence": ["extension-line-0", "extension-line-1"]
    }
  ],
  "provenance": {
    "observer_version": "dimension-observer-1.0",
    "ocr_engine": "tesseract-5.4.0.20240606",
    "observation_sha256": "<64 lowercase hex>"
  }
}
```

All newly introduced object boundaries remain closed. Existing VS-T0 examples remain valid.

## Stable Interfaces

```python
# primitive_ir_lib/dimension_symbols.py
from dataclasses import dataclass

@dataclass(frozen=True)
class ParsedDimensionText:
    display_text: str
    value: float | None
    unit: str
    kind_hint: str | None
    symbol_text: str | None
    repeat_count: int | None
    tolerance_mode: str | None
    tolerance_upper: float | None
    tolerance_lower: float | None
    confidence: float


def parse_dimension_text(text: str, *, default_unit: str = "mm") -> ParsedDimensionText:
    """Parse one OCR/Vision text candidate without inventing unreadable values."""
```

```python
# primitive_ir_lib/dimension_geometry.py
from dataclasses import dataclass
import numpy as np

Point = tuple[float, float]
Segment = tuple[Point, Point]

@dataclass(frozen=True)
class DimensionGeometryEvidence:
    dimension_line: Segment | None
    extension_lines: tuple[Segment, ...]
    arrow_points: tuple[Point, ...]
    leader_lines: tuple[Segment, ...]
    kind_hint: str | None
    confidence: float


def detect_dimension_geometry(crop_bgr: np.ndarray) -> DimensionGeometryEvidence:
    """Detect controlled line/arrow/leader evidence inside one source crop."""
```

```python
# primitive_ir_lib/dimension_observer.py
from dataclasses import dataclass
from collections.abc import Callable, Mapping, Sequence
import numpy as np

Bbox = tuple[int, int, int, int]

@dataclass(frozen=True)
class DimensionCluster:
    cluster_id: str
    bbox_px: Bbox
    member_boxes: tuple[Bbox, ...]

@dataclass(frozen=True)
class AttachmentCandidate:
    from_ref: Mapping[str, str]
    to_ref: Mapping[str, str]
    confidence: float
    evidence: tuple[str, ...]

@dataclass(frozen=True)
class DimensionDisposition:
    cluster_id: str
    disposition: str
    observation: Mapping[str, object] | None
    reasons: tuple[str, ...]

OcrReader = Callable[[np.ndarray], Sequence[object]]


def detect_dimension_clusters(image_bgr: np.ndarray) -> list[DimensionCluster]:
    """Return stable reading-order clusters; do not run OCR here."""


def observe_dimension_cluster(
    image_bgr: np.ndarray,
    cluster: DimensionCluster,
    *,
    page_id: str,
    view_id: str,
    source_sha256: str,
    ocr_reader: OcrReader,
    semantic_anchors: Sequence[Mapping[str, object]] = (),
) -> DimensionDisposition:
    """Return exactly one disposition for one detected cluster."""


def build_dimension_register(
    *,
    run_id: str,
    source_sha256: str,
    page_id: str,
    view_id: str,
    page_coverage_percent: float,
    dispositions: Sequence[DimensionDisposition],
) -> dict[str, object]:
    """Assemble a VS-T0-compatible register and count every cluster disposition."""
```

```python
# cad_agent/dimension_observer_run.py
from collections.abc import Callable, Sequence
from pathlib import Path


def run_dimension_observer(
    *,
    run_id: str,
    source_image: Path,
    page_id: str,
    view_id: str,
    output_dir: Path,
    ocr_lang: str = "vie+eng",
    tesseract_cmd: str | None = None,
    semantic_anchors_path: Path | None = None,
) -> Path:
    """Write crops, observer evidence, and validated dimension-register.json atomically."""
```

---

### Task 1: Extend Dimension Register evidence fields

**Files:**
- Modify: `cad_agent/visual_contracts.py`
- Modify: `contracts/visual-supervisor/dimension-register.schema.json`
- Modify: `contracts/visual-supervisor/examples/dimension-register.json`
- Modify: `tests/visual_supervisor_fixtures.py`
- Modify: `tests/test_visual_supervisor_contracts.py`
- Modify: `tests/test_visual_supervisor_schema_alignment.py`

**Interfaces:**
- Consumes: `validate_visual_contract(payload, contract="dimension_register")`.
- Produces: optional evidence fields listed above; no new authority state.

- [ ] **Step 1: Write failing schema/validator tests**

```python
def test_dimension_register_accepts_closed_observer_evidence_fields() -> None:
    payload = valid_dimension_register()
    payload["dimensions"][0].update(valid_dimension_observer_evidence())
    assert validate_visual_contract(payload, contract="dimension_register") == payload


def test_attachment_candidate_rejects_out_of_range_confidence() -> None:
    payload = valid_dimension_register()
    evidence = valid_dimension_observer_evidence()
    evidence["attachment_candidates"][0]["confidence"] = 1.1
    payload["dimensions"][0].update(evidence)
    with pytest.raises(VisualContractError, match="attachment_candidates"):
        validate_visual_contract(payload, contract="dimension_register")


def test_dimension_observer_evidence_rejects_unknown_property() -> None:
    payload = valid_dimension_register()
    evidence = valid_dimension_observer_evidence()
    evidence["provenance"]["codex_guess"] = True
    payload["dimensions"][0].update(evidence)
    with pytest.raises(VisualContractError, match="Unexpected properties"):
        validate_visual_contract(payload, contract="dimension_register")
```

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
```

Expected: failure because the optional fields are rejected.

- [ ] **Step 3: Implement minimal closed validation and matching schema**

Validate finite coordinates, confidence in `[0, 1]`, exact SHA-256, exact tolerance modes `NONE|SYMMETRIC|LIMITS|PLUS_MINUS`, and exact attachment reference shape. Do not require these fields for legacy synthetic examples.

- [ ] **Step 4: Run GREEN and inspect**

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
git diff --check
```

- [ ] **Step 5: Commit**

```powershell
git add cad_agent/visual_contracts.py contracts/visual-supervisor tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_schema_alignment.py
git commit -m "feat: extend dimension register observation evidence"
```

---

### Task 2: Parse dimension values, symbols, repetition, and tolerances

**Files:**
- Create: `primitive_ir_lib/dimension_symbols.py`
- Create: `primitive_ir_lib/tests/test_dimension_symbols.py`

**Interfaces:**
- Produces: `ParsedDimensionText`, `parse_dimension_text()`.

- [ ] **Step 1: Write failing parser tests**

```python
@pytest.mark.parametrize(
    ("text", "value", "kind", "symbol", "repeat_count"),
    [
        ("4500", 4500.0, None, None, None),
        ("⌀20", 20.0, "DIAMETER", "⌀", None),
        ("R12,5", 12.5, "RADIUS", "R", None),
        ("4x⌀10", 10.0, "DIAMETER", "⌀", 4),
        ("45°", 45.0, "ANGULAR", "°", None),
    ],
)
def test_parse_dimension_text_forms(text, value, kind, symbol, repeat_count) -> None:
    parsed = parse_dimension_text(text)
    assert parsed.value == value
    assert parsed.kind_hint == kind
    assert parsed.symbol_text == symbol
    assert parsed.repeat_count == repeat_count


def test_parse_symmetric_tolerance() -> None:
    parsed = parse_dimension_text("100 ±0.2")
    assert parsed.value == 100.0
    assert parsed.tolerance_mode == "SYMMETRIC"
    assert parsed.tolerance_upper == 0.2
    assert parsed.tolerance_lower == -0.2


def test_unreadable_text_returns_null_value() -> None:
    parsed = parse_dimension_text("8O?O")
    assert parsed.value is None
    assert parsed.confidence < 0.5
```

- [ ] **Step 2: Run and verify RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_dimension_symbols.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement deterministic parsing**

Use Unicode normalization, decimal-comma normalization only between digits, anchored regular expressions, and finite-number checks. Do not globally replace `O` with `0`; ambiguous OCR remains unreadable.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_dimension_symbols.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/dimension_symbols.py primitive_ir_lib/tests/test_dimension_symbols.py
git commit -m "feat: parse dimension text and tolerances"
```

---

### Task 3: Detect dimension geometry inside a crop

**Files:**
- Create: `primitive_ir_lib/dimension_geometry.py`
- Create: `primitive_ir_lib/tests/test_dimension_geometry.py`

**Interfaces:**
- Consumes: BGR crop `np.ndarray`.
- Produces: `DimensionGeometryEvidence`.

- [ ] **Step 1: Write synthetic failing tests**

Generate white images with OpenCV, draw two extension lines, one dimension line, and filled triangular arrowheads. Assert the detector returns one main line, two extensions, two arrow points, finite coordinates, and stable output across two calls.

```python
def test_detect_horizontal_dimension_geometry_is_deterministic() -> None:
    image = synthetic_horizontal_dimension()
    first = detect_dimension_geometry(image)
    second = detect_dimension_geometry(image.copy())
    assert first == second
    assert first.dimension_line is not None
    assert len(first.extension_lines) == 2
    assert len(first.arrow_points) == 2
    assert first.kind_hint == "HORIZONTAL_DISTANCE"
```

Also test a leader line and a blank crop.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_dimension_geometry.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement controlled detection**

Use grayscale, adaptive threshold, `cv2.HoughLinesP`, line-length/orientation grouping, and contour-based triangular arrowhead candidates. Sort every output by `(y, x)` or endpoint order. Never infer scale or semantic attachment here.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_dimension_geometry.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/dimension_geometry.py primitive_ir_lib/tests/test_dimension_geometry.py
git commit -m "feat: detect source dimension geometry"
```

---

### Task 4: Detect clusters and produce one disposition per cluster

**Files:**
- Create: `primitive_ir_lib/dimension_observer.py`
- Create: `primitive_ir_lib/tests/test_dimension_observer.py`
- Modify: `primitive_ir_lib/text_extraction.py`

**Interfaces:**
- Consumes: `detect_text_candidate_rois()`, `parse_dimension_text()`, `detect_dimension_geometry()`.
- Produces: cluster/disposition types and `build_dimension_register()`.

- [ ] **Step 1: Write failing cluster-accounting tests**

```python
def test_every_detected_cluster_has_exactly_one_disposition() -> None:
    image = synthetic_page_with_two_dimension_clusters_and_one_note()
    clusters = detect_dimension_clusters(image)
    dispositions = [
        observe_dimension_cluster(
            image,
            cluster,
            page_id="PAGE-001",
            view_id="SIDE",
            source_sha256="1" * 64,
            ocr_reader=fake_ocr_reader,
        )
        for cluster in clusters
    ]
    assert len(dispositions) == len(clusters)
    assert len({item.cluster_id for item in dispositions}) == len(clusters)


def test_number_without_attachment_is_unresolved() -> None:
    disposition = observe_dimension_cluster(...)
    assert disposition.observation["value"] == 4500.0
    assert disposition.observation["status"] == "UNRESOLVED"
    assert "attachment" in disposition.reasons


def test_non_dimension_text_is_audited_but_not_registered() -> None:
    register = build_dimension_register(...)
    assert register["coverage"]["clusters_processed"] == 1
    assert register["dimensions"] == []
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_dimension_observer.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement deterministic cluster IDs and OCR fusion**

Cluster ID is derived from page/view plus canonical bbox order, not random UUID. Crop OCR at rotations `0`, `90`, `-90`; select a value only when parses agree or one candidate strictly dominates by confidence. Preserve all candidate texts in observer evidence.

- [ ] **Step 4: Implement attachment scoring**

Score only supplied semantic anchors and detected extension endpoints. Exact scoring:

```text
0.45 endpoint proximity
0.25 orientation compatibility
0.20 view membership
0.10 anchor confidence
```

A resolved pair requires score `>= 0.85`, second-best margin `>= 0.10`, distinct references, and geometry confidence `>= 0.70`. Otherwise keep candidate list and status `UNRESOLVED`.

- [ ] **Step 5: Implement role/status policy**

- resolved value + known kind + valid attachments + no conflict: `CONFIRMED`;
- no valid attachment or unreadable value: `UNRESOLVED`;
- two authoritative anchor/value interpretations: `CONFLICT`;
- default role is `AMBIGUOUS` until profile rules explicitly classify it;
- role may become `REFERENCE` or `DERIVED` from explicit supplied metadata;
- never infer `DRIVING` solely from placement or font size.

- [ ] **Step 6: Run GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_dimension_observer.py primitive_ir_lib/tests/test_dimension_symbols.py primitive_ir_lib/tests/test_dimension_geometry.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/dimension_observer.py primitive_ir_lib/text_extraction.py primitive_ir_lib/tests/test_dimension_observer.py
git commit -m "feat: observe and classify dimension clusters"
```

---

### Task 5: Add the hash-bound file runner and CLI

**Files:**
- Create: `cad_agent/dimension_observer_run.py`
- Create: `cad_agent/run_dimension_observer.py`
- Create: `tests/test_dimension_observer_run.py`

**Interfaces:**
- Consumes: observer functions, `validate_visual_contract()`, `sha256_file()`.
- Produces: `<output_dir>/dimension-register.json`, `<output_dir>/observer-evidence.json`, and `<output_dir>/crops/*.png`.

- [ ] **Step 1: Write failing runner tests**

```python
def test_runner_writes_validated_register_and_hash_bound_evidence(tmp_path: Path) -> None:
    source = write_synthetic_dimension_page(tmp_path / "source.png")
    register_path = run_dimension_observer(
        run_id="RUN-VS-T1-001",
        source_image=source,
        page_id="PAGE-001",
        view_id="SIDE",
        output_dir=tmp_path / "run",
        tesseract_cmd="FAKE-INJECTED-BY-TEST",
    )
    register = read_visual_contract(register_path, contract="dimension_register")
    assert register["source_sha256"] == sha256_file(source)
    assert (register_path.parent / "observer-evidence.json").is_file()


def test_runner_refuses_existing_nonempty_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "run"
    output.mkdir()
    (output / "unrelated.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(DimensionObserverRunError, match="non-empty"):
        run_dimension_observer(...)
```

Use dependency injection for OCR in unit tests; do not require the Tesseract executable in the focused suite.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_dimension_observer_run.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement immutable input snapshot and atomic output**

Read source bytes once, hash those exact bytes, decode from the snapshot, write all artifacts under a temporary sibling directory, validate the register, hash every artifact into `observer-evidence.json`, then rename the directory atomically. Reject changed source bytes before final rename.

- [ ] **Step 4: Add CLI**

```powershell
python -m cad_agent.run_dimension_observer --run-id RUN-VS-T1-001 --source page.png --page-id PAGE-001 --view-id SIDE --output D:\runs\RUN-VS-T1-001\dimensions\SIDE
```

CLI errors return nonzero and never partially replace an existing output directory.

- [ ] **Step 5: Run GREEN and commit**

```powershell
python -m pytest tests/test_dimension_observer_run.py primitive_ir_lib/tests/test_dimension_observer.py -q -p no:cacheprovider
git diff --check
git add cad_agent/dimension_observer_run.py cad_agent/run_dimension_observer.py tests/test_dimension_observer_run.py
git commit -m "feat: add offline dimension observer runner"
```

---

### Task 6: Enforce runtime gate and documentation boundaries

**Files:**
- Create: `tests/test_dimension_register_runtime_policy.py`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/STATUS.md`
- Modify: `tests/test_documentation_contract.py`

- [ ] **Step 1: Add failing policy tests**

Test all of these:

- zero clusters plus 100% coverage passes;
- detected cluster without disposition cannot pass coverage;
- numeric value with unresolved attachment does not become `CONFIRMED`;
- critical unresolved item blocks only listed regions;
- `NOT_A_DIMENSION` clusters remain in observer evidence but not register dimensions;
- no code path assigns `DRIVING` without explicit profile metadata.

- [ ] **Step 2: Run RED, implement minimal policy fixes, run GREEN**

```powershell
python -m pytest tests/test_dimension_register_runtime_policy.py tests/test_dimension_observer_run.py primitive_ir_lib/tests/test_dimension_observer.py -q -p no:cacheprovider
```

- [ ] **Step 3: Update canonical docs truthfully**

Record:

```text
VS-T1 state: Partially verified — offline synthetic observer only.
OpenAI API: NOT RUN.
real_data: NOT RUN.
AutoCAD Mechanical: NOT RUN.
No authoritative geometry or publication permission is created.
```

- [ ] **Step 4: Run the full verifier**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Expected: exit `0`; record exact test counts and final head SHA. Do not convert unavailable private/live gates to PASS.

- [ ] **Step 5: Final inspection and commit**

```powershell
git diff --check
git status --short
git diff --stat
git add docs/ARCHITECTURE.md docs/STATUS.md tests/test_documentation_contract.py tests/test_dimension_register_runtime_policy.py
git commit -m "docs: record VS-T1 dimension observer gate"
```

## Acceptance Checklist

- [ ] Every detected cluster has one auditable disposition.
- [ ] Empty pages are representable without fake dimensions.
- [ ] Unreadable values remain `null`.
- [ ] Number-only observations without attachments remain `UNRESOLVED`.
- [ ] Attachment candidates, extension geometry, parser provenance, and confidence are recorded.
- [ ] No pixel coordinate becomes authoritative Model Space geometry.
- [ ] Output register validates through the integrated VS-T0 contract.
- [ ] Focused tests and `scripts/verify.ps1` pass on the final head.
- [ ] Private, OpenAI API, and AutoCAD gates remain honestly `NOT RUN`.

## Execution Mode

Implement VS-T1 on its own branch/worktree. VS-T2 may run in parallel because its primary write set is disjoint. A single integration reviewer must review both before VS-T6 consumes their outputs.
