# VS-T1 Dimension Observer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Planned

**Planning base SHA:** `2932febe5e95b042b202a767604d2143e6a6cc4f`

**Implementation base:** Create `task/vs-t1-dimension-observer` from fresh integrated `main` and record that exact SHA before changing code.

**Goal:** Build an offline Dimension Observer that accounts for every detected source dimension cluster, parses values and symbols, records attachment evidence, and emits a validated `dimension_register` without inventing text, units, values, roles, or authoritative attachments.

**Architecture:** Recognition stays in `primitive_ir_lib`; `cad_agent` only snapshots files, hashes artifacts, validates contracts, and writes outputs. Reuse `detect_text_candidate_rois()`, `extract_text_tesseract()`, `RawText`, OpenCV, NumPy, Tesseract, `canonical_json_sha256()`, `sha256_file()`, and the integrated VS-T0 validator. No OpenAI API or AutoCAD call is allowed in VS-T1.

**Tech Stack:** Windows, Python 3.11, OpenCV 5, NumPy 2, Tesseract 5.4.0.20240606, pytest.

## Global Constraints

- Do not create another image/PDF pipeline.
- Do not infer Model Space coordinates or authoritative scale from pixels.
- A readable number without valid attachments remains `UNRESOLVED`.
- An observation with role `AMBIGUOUS` cannot be `CONFIRMED`.
- Only explicit profile metadata may assign `DRIVING`, `REFERENCE`, or `DERIVED`.
- Only `CONFIRMED` plus `DRIVING` with valid `from_ref` and `to_ref` may later control geometry.
- Critical unresolved or conflicting observations declare `blocker_scope`.
- Every detected cluster receives exactly one observer disposition: `CONFIRMED`, `UNRESOLVED`, `CONFLICT`, or `NOT_A_DIMENSION`.
- `NOT_A_DIMENSION` remains in observer evidence but is excluded from `dimension_register.dimensions`.
- A completely unreadable observation uses `display_text: ""`, `value: null`, and `unit: null`; never insert a sentinel that looks like source text.
- Source images, crops, OCR outputs, customer data, and run directories stay outside Git.
- Synthetic tests create images in memory or temporary directories.
- Every task begins with a failing focused test and ends with focused tests, `git diff --check`, diff inspection, and a bounded commit.
- `real_data`, OpenAI API, and AutoCAD Mechanical remain `NOT RUN`.

---

## File Structure

### Recognition

- `primitive_ir_lib/dimension_symbols.py` — numeric, symbol, repetition, unit, and tolerance parsing.
- `primitive_ir_lib/dimension_geometry.py` — dimension line, extension line, arrowhead, and leader evidence.
- `primitive_ir_lib/dimension_observer.py` — stable clusters, OCR fusion, attachment scoring, disposition, role/status, and coverage.

### Orchestration

- `cad_agent/dimension_observer_run.py` — immutable source snapshot, evidence/crop writer, register assembly, atomic output.
- `cad_agent/run_dimension_observer.py` — CLI only.

### Tests

- `primitive_ir_lib/tests/dimension_test_helpers.py`
- `primitive_ir_lib/tests/test_dimension_symbols.py`
- `primitive_ir_lib/tests/test_dimension_geometry.py`
- `primitive_ir_lib/tests/test_dimension_observer.py`
- `tests/test_dimension_observer_run.py`
- `tests/test_dimension_register_runtime_policy.py`

## Contract Amendment

Extend `dimension-register-1.0` without changing the meaning of existing confirmed observations:

1. `display_text` may be empty only when status is `UNRESOLVED` or `CONFLICT`.
2. `value` may be `null` only when status is `UNRESOLVED` or `CONFLICT`.
3. `unit` may be `null` only when status is `UNRESOLVED` or `CONFLICT`.
4. `CONFIRMED` requires non-empty `display_text`, finite numeric `value`, and non-empty `unit`.
5. Add these optional closed evidence fields:

```json
{
  "raw_text_candidates": ["⌀20", "020"],
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
    "observation_sha256": "9999999999999999999999999999999999999999999999999999999999999999"
  }
}
```

Every new object is closed with `additionalProperties: false`. Validate finite coordinates, exact lowercase SHA-256, confidence in `[0, 1]`, and tolerance modes `NONE`, `SYMMETRIC`, `LIMITS`, `PLUS_MINUS`.

## Stable Interfaces

```python
# primitive_ir_lib/dimension_symbols.py
from dataclasses import dataclass

@dataclass(frozen=True)
class ParsedDimensionText:
    display_text: str
    raw_text_candidates: tuple[str, ...]
    value: float | None
    unit: str | None
    kind_hint: str | None
    symbol_text: str | None
    repeat_count: int | None
    tolerance_mode: str | None
    tolerance_upper: float | None
    tolerance_lower: float | None
    confidence: float


def parse_dimension_text(
    text: str,
    *,
    default_unit: str | None = None,
) -> ParsedDimensionText:
    """Parse one candidate without inventing unreadable values or units."""
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
    """Detect controlled geometry evidence in one crop."""
```

```python
# primitive_ir_lib/dimension_observer.py
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import numpy as np
from primitive_ir_lib.text_extraction import RawText

Bbox = tuple[int, int, int, int]
OcrReader = Callable[[np.ndarray], Sequence[RawText]]

@dataclass(frozen=True)
class DimensionCluster:
    cluster_id: str
    bbox_px: Bbox
    member_boxes: tuple[Bbox, ...]

@dataclass(frozen=True)
class DimensionDisposition:
    cluster_id: str
    disposition: str
    observation: Mapping[str, object] | None
    reasons: tuple[str, ...]


def detect_dimension_clusters(image_bgr: np.ndarray) -> list[DimensionCluster]:
    """Return stable reading-order clusters without running OCR."""


def observe_dimension_cluster(
    image_bgr: np.ndarray,
    cluster: DimensionCluster,
    *,
    page_id: str,
    view_id: str,
    source_sha256: str,
    ocr_reader: OcrReader,
    semantic_anchors: Sequence[Mapping[str, object]] = (),
    explicit_role: str | None = None,
    default_unit: str | None = None,
    blocker_scope: Sequence[str] = (),
) -> DimensionDisposition:
    """Return exactly one disposition for the supplied cluster."""


def build_dimension_register(
    *,
    run_id: str,
    source_sha256: str,
    page_id: str,
    view_id: str,
    total_area_px: int,
    inspected_area_px: int,
    detected_cluster_ids: Sequence[str],
    dispositions: Sequence[DimensionDisposition],
) -> dict[str, object]:
    """Reject missing/duplicate dispositions and compute measured coverage."""
```

```python
# cad_agent/dimension_observer_run.py
from pathlib import Path
from primitive_ir_lib.dimension_observer import OcrReader


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
    profile_path: Path | None = None,
    ocr_reader: OcrReader | None = None,
) -> Path:
    """Write crops, observer evidence, and dimension-register.json atomically."""
```

## Synthetic Test Helpers

Create `primitive_ir_lib/tests/dimension_test_helpers.py` with deterministic helpers used by later tasks:

```python
from pathlib import Path
import cv2
import numpy as np
from primitive_ir_lib.dimension_observer import DimensionDisposition
from primitive_ir_lib.text_extraction import RawText


def synthetic_horizontal_dimension() -> np.ndarray:
    image = np.full((140, 420, 3), 255, dtype=np.uint8)
    cv2.line(image, (80, 35), (340, 35), (0, 0, 0), 2)
    cv2.line(image, (80, 35), (80, 115), (0, 0, 0), 2)
    cv2.line(image, (340, 35), (340, 115), (0, 0, 0), 2)
    cv2.fillConvexPoly(image, np.array([[80, 35], [94, 29], [94, 41]]), (0, 0, 0))
    cv2.fillConvexPoly(image, np.array([[340, 35], [326, 29], [326, 41]]), (0, 0, 0))
    cv2.putText(image, "4500", (170, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return image


def synthetic_isolated_number_crop() -> np.ndarray:
    image = np.full((80, 180, 3), 255, dtype=np.uint8)
    cv2.putText(image, "4500", (25, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    return image


def fake_ocr_4500(image_bgr: np.ndarray) -> list[RawText]:
    del image_bgr
    return [RawText(
        id="rawtext-4500",
        content="4500",
        bbox_px=(20, 15, 100, 55),
        rotation_deg=0.0,
        confidence=0.99,
        source="text_tesseract",
        parsed_value=4500.0,
        semantic_role="dimension_value",
    )]


def not_a_dimension_disposition(cluster_id: str) -> DimensionDisposition:
    return DimensionDisposition(
        cluster_id=cluster_id,
        disposition="NOT_A_DIMENSION",
        observation=None,
        reasons=("text_not_dimension_like",),
    )


def write_synthetic_dimension_page(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), synthetic_horizontal_dimension())
    return path
```

Task 4 may add `synthetic_page_with_two_dimension_clusters_and_one_note()` using three non-overlapping copies of these primitives; it must be implemented in this same helper file before the test imports it.

---

### Task 1: Extend the Dimension Register Evidence Surface

**Files:**
- Modify: `cad_agent/visual_contracts.py`
- Modify: `contracts/visual-supervisor/dimension-register.schema.json`
- Modify: `contracts/visual-supervisor/examples/dimension-register.json`
- Modify: `tests/visual_supervisor_fixtures.py`
- Modify: `tests/test_visual_supervisor_contracts.py`
- Modify: `tests/test_visual_supervisor_schema_alignment.py`

- [ ] **Step 1: Write failing tests**

```python
def test_unreadable_observation_accepts_empty_text_null_value_and_unit() -> None:
    payload = valid_dimension_register()
    item = payload["dimensions"][0]
    item.update({
        "display_text": "",
        "value": None,
        "unit": None,
        "role": "AMBIGUOUS",
        "status": "UNRESOLVED",
        "blocker_scope": ["SIDE-CABIN"],
        "raw_text_candidates": [],
    })
    payload["summary"] = {"confirmed": 0, "unresolved": 1, "conflicts": 0}
    assert validate_visual_contract(payload, contract="dimension_register") == payload


def test_confirmed_observation_requires_text_value_and_unit() -> None:
    for field, invalid in (("display_text", ""), ("value", None), ("unit", None)):
        payload = valid_dimension_register()
        payload["dimensions"][0][field] = invalid
        with pytest.raises(VisualContractError, match=field):
            validate_visual_contract(payload, contract="dimension_register")


def test_dimension_register_accepts_closed_observer_evidence_fields() -> None:
    payload = valid_dimension_register()
    payload["dimensions"][0].update(valid_dimension_observer_evidence())
    assert validate_visual_contract(payload, contract="dimension_register") == payload


def test_observer_evidence_rejects_unknown_property() -> None:
    payload = valid_dimension_register()
    evidence = valid_dimension_observer_evidence()
    evidence["provenance"]["codex_guess"] = True
    payload["dimensions"][0].update(evidence)
    with pytest.raises(VisualContractError, match="Unexpected properties"):
        validate_visual_contract(payload, contract="dimension_register")
```

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement matching validator/schema support**

Preserve all VS-T0 authority rules. Add the nullable/conditional rules and optional evidence fields exactly as specified above.

- [ ] **Step 4: Verify GREEN and commit**

```powershell
python -m pytest tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_schema_alignment.py -q -p no:cacheprovider
git diff --check
git add cad_agent/visual_contracts.py contracts/visual-supervisor tests/visual_supervisor_fixtures.py tests/test_visual_supervisor_contracts.py tests/test_visual_supervisor_schema_alignment.py
git commit -m "feat: extend dimension register observation evidence"
```

---

### Task 2: Parse Values, Symbols, Repetition, and Tolerances

**Files:**
- Create: `primitive_ir_lib/dimension_symbols.py`
- Create: `primitive_ir_lib/tests/dimension_test_helpers.py`
- Create: `primitive_ir_lib/tests/test_dimension_symbols.py`

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.parametrize(
    ("text", "value", "unit", "kind", "symbol", "repeat_count"),
    [
        ("4500", 4500.0, None, None, None, None),
        ("4500 mm", 4500.0, "mm", None, None, None),
        ("⌀20", 20.0, None, "DIAMETER", "⌀", None),
        ("R12,5", 12.5, None, "RADIUS", "R", None),
        ("4x⌀10", 10.0, None, "DIAMETER", "⌀", 4),
        ("45°", 45.0, "deg", "ANGULAR", "°", None),
    ],
)
def test_parse_dimension_forms(text, value, unit, kind, symbol, repeat_count) -> None:
    parsed = parse_dimension_text(text)
    assert parsed.value == value
    assert parsed.unit == unit
    assert parsed.kind_hint == kind
    assert parsed.symbol_text == symbol
    assert parsed.repeat_count == repeat_count


def test_parse_symmetric_tolerance() -> None:
    parsed = parse_dimension_text("100 ±0.2 mm")
    assert parsed.value == 100.0
    assert parsed.unit == "mm"
    assert parsed.tolerance_mode == "SYMMETRIC"
    assert parsed.tolerance_upper == 0.2
    assert parsed.tolerance_lower == -0.2


def test_ambiguous_ocr_does_not_replace_letters_with_digits() -> None:
    parsed = parse_dimension_text("8O?O")
    assert parsed.display_text == "8O?O"
    assert parsed.value is None
    assert parsed.unit is None
    assert parsed.confidence < 0.5
```

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_dimension_symbols.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement deterministic parsing**

Use Unicode normalization, decimal-comma normalization only between digits, anchored regular expressions, and finite-number checks. Do not globally replace `O` with `0`. Apply `default_unit` only when an explicit drawing profile supplied it.

- [ ] **Step 4: Verify GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_dimension_symbols.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/dimension_symbols.py primitive_ir_lib/tests/dimension_test_helpers.py primitive_ir_lib/tests/test_dimension_symbols.py
git commit -m "feat: parse dimension text and tolerances"
```

---

### Task 3: Detect Dimension Geometry in a Crop

**Files:**
- Create: `primitive_ir_lib/dimension_geometry.py`
- Modify: `primitive_ir_lib/tests/dimension_test_helpers.py`
- Create: `primitive_ir_lib/tests/test_dimension_geometry.py`

- [ ] **Step 1: Write failing tests**

```python
def test_horizontal_dimension_geometry_is_deterministic() -> None:
    image = synthetic_horizontal_dimension()
    first = detect_dimension_geometry(image)
    second = detect_dimension_geometry(image.copy())
    assert first == second
    assert first.dimension_line is not None
    assert len(first.extension_lines) == 2
    assert len(first.arrow_points) == 2
    assert first.kind_hint == "HORIZONTAL_DISTANCE"


def test_blank_crop_has_no_false_dimension() -> None:
    image = np.full((80, 240, 3), 255, dtype=np.uint8)
    evidence = detect_dimension_geometry(image)
    assert evidence.dimension_line is None
    assert evidence.extension_lines == ()
    assert evidence.arrow_points == ()
```

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_dimension_geometry.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement controlled detection**

Use grayscale, adaptive threshold, `cv2.HoughLinesP`, orientation grouping, and contour-based triangular arrowhead candidates. Sort outputs by canonical endpoint order. Never infer scale or semantic attachment here.

- [ ] **Step 4: Verify GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_dimension_geometry.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/dimension_geometry.py primitive_ir_lib/tests/dimension_test_helpers.py primitive_ir_lib/tests/test_dimension_geometry.py
git commit -m "feat: detect source dimension geometry"
```

---

### Task 4: Detect Clusters and Produce One Disposition Per Cluster

**Files:**
- Create: `primitive_ir_lib/dimension_observer.py`
- Modify: `primitive_ir_lib/text_extraction.py`
- Modify: `primitive_ir_lib/tests/dimension_test_helpers.py`
- Create: `primitive_ir_lib/tests/test_dimension_observer.py`

- [ ] **Step 1: Write failing accounting and attachment tests**

```python
def test_number_without_attachment_is_unresolved_and_ambiguous() -> None:
    image = synthetic_isolated_number_crop()
    cluster = DimensionCluster(
        cluster_id="DIMCLUSTER-001",
        bbox_px=(0, 0, image.shape[1], image.shape[0]),
        member_boxes=((20, 20, 100, 55),),
    )
    disposition = observe_dimension_cluster(
        image,
        cluster,
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
    )
    assert disposition.observation is not None
    assert disposition.observation["value"] == 4500.0
    assert disposition.observation["role"] == "AMBIGUOUS"
    assert disposition.observation["status"] == "UNRESOLVED"
    assert "attachment_unresolved" in disposition.reasons


def test_resolved_attachment_without_explicit_role_remains_unresolved() -> None:
    disposition = observe_dimension_cluster(
        synthetic_horizontal_dimension(),
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        semantic_anchors=matching_horizontal_anchors(),
        explicit_role=None,
    )
    assert disposition.observation["role"] == "AMBIGUOUS"
    assert disposition.observation["status"] == "UNRESOLVED"
    assert "role_unresolved" in disposition.reasons


def test_explicit_reference_role_may_confirm_resolved_observation() -> None:
    disposition = observe_dimension_cluster(
        synthetic_horizontal_dimension(),
        horizontal_dimension_cluster(),
        page_id="PAGE-001",
        view_id="SIDE",
        source_sha256="1" * 64,
        ocr_reader=fake_ocr_4500,
        semantic_anchors=matching_horizontal_anchors(),
        explicit_role="REFERENCE",
        default_unit="mm",
    )
    assert disposition.observation["role"] == "REFERENCE"
    assert disposition.observation["status"] == "CONFIRMED"


def test_register_rejects_missing_cluster_disposition() -> None:
    with pytest.raises(DimensionObserverError, match="disposition"):
        build_dimension_register(
            run_id="RUN-VS-T1-001",
            source_sha256="1" * 64,
            page_id="PAGE-001",
            view_id="SIDE",
            total_area_px=10000,
            inspected_area_px=10000,
            detected_cluster_ids=["DIMCLUSTER-001", "DIMCLUSTER-002"],
            dispositions=[not_a_dimension_disposition("DIMCLUSTER-001")],
        )
```

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest primitive_ir_lib/tests/test_dimension_observer.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement stable IDs and OCR fusion**

Cluster IDs derive from page/view and canonical bbox order. OCR rotations are `0`, `90`, and `-90`. Accept a parsed value only when candidates agree or one candidate has at least `0.15` higher confidence. Preserve all candidate strings.

- [ ] **Step 4: Implement attachment scoring**

```text
0.45 endpoint proximity
0.25 orientation compatibility
0.20 view membership
0.10 anchor confidence
```

Resolve only when score is at least `0.85`, second-best margin is at least `0.10`, references are distinct, and geometry confidence is at least `0.70`.

- [ ] **Step 5: Implement role/status policy**

- no readable value or unresolved attachment: `UNRESOLVED`;
- competing authoritative interpretations: `CONFLICT`;
- resolved value/attachment but no explicit role: `AMBIGUOUS` plus `UNRESOLVED`;
- resolved value/attachment plus explicit `DRIVING`, `REFERENCE`, or `DERIVED`: `CONFIRMED`;
- `DRIVING` requires both semantic references and profile permission.

- [ ] **Step 6: Verify GREEN and commit**

```powershell
python -m pytest primitive_ir_lib/tests/test_dimension_observer.py primitive_ir_lib/tests/test_dimension_symbols.py primitive_ir_lib/tests/test_dimension_geometry.py -q -p no:cacheprovider
git diff --check
git add primitive_ir_lib/dimension_observer.py primitive_ir_lib/text_extraction.py primitive_ir_lib/tests/dimension_test_helpers.py primitive_ir_lib/tests/test_dimension_observer.py
git commit -m "feat: observe and classify dimension clusters"
```

---

### Task 5: Add the Hash-Bound Runner and CLI

**Files:**
- Create: `cad_agent/dimension_observer_run.py`
- Create: `cad_agent/run_dimension_observer.py`
- Create: `tests/test_dimension_observer_run.py`

- [ ] **Step 1: Write failing runner tests**

```python
def test_runner_writes_validated_hash_bound_register(tmp_path: Path) -> None:
    source = write_synthetic_dimension_page(tmp_path / "source.png")
    register_path = run_dimension_observer(
        run_id="RUN-VS-T1-001",
        source_image=source,
        page_id="PAGE-001",
        view_id="SIDE",
        output_dir=tmp_path / "run",
        ocr_reader=fake_ocr_4500,
    )
    register = read_visual_contract(register_path, contract="dimension_register")
    assert register["source_sha256"] == sha256_file(source)
    assert (register_path.parent / "observer-evidence.json").is_file()


def test_runner_refuses_nonempty_output_directory(tmp_path: Path) -> None:
    source = write_synthetic_dimension_page(tmp_path / "source.png")
    output = tmp_path / "run"
    output.mkdir()
    (output / "unrelated.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(DimensionObserverRunError, match="non-empty"):
        run_dimension_observer(
            run_id="RUN-VS-T1-001",
            source_image=source,
            page_id="PAGE-001",
            view_id="SIDE",
            output_dir=output,
            ocr_reader=fake_ocr_4500,
        )
```

- [ ] **Step 2: Verify RED**

```powershell
python -m pytest tests/test_dimension_observer_run.py -q -p no:cacheprovider
```

- [ ] **Step 3: Implement immutable input and measured coverage**

Read source bytes once, hash those bytes, decode the snapshot, and run cluster detection over the complete decoded image. Set `total_area_px = width * height` and `inspected_area_px = total_area_px`; never accept a caller-supplied 100% coverage claim. Write under a temporary sibling directory, validate the register, hash all artifacts, confirm source bytes did not change, then rename atomically. Reject existing nonempty outputs.

Required outputs:

```text
dimension-register.json
observer-evidence.json
crops/<cluster-id>.png
```

- [ ] **Step 4: Add CLI**

```powershell
python -m cad_agent.run_dimension_observer --run-id RUN-VS-T1-001 --source page.png --page-id PAGE-001 --view-id SIDE --output D:\runs\RUN-VS-T1-001\dimensions\SIDE
```

The CLI constructs the Tesseract reader. Focused tests inject `ocr_reader` and do not require an external executable.

- [ ] **Step 5: Verify GREEN and commit**

```powershell
python -m pytest tests/test_dimension_observer_run.py primitive_ir_lib/tests/test_dimension_observer.py -q -p no:cacheprovider
git diff --check
git add cad_agent/dimension_observer_run.py cad_agent/run_dimension_observer.py tests/test_dimension_observer_run.py
git commit -m "feat: add offline dimension observer runner"
```

---

### Task 6: Enforce Runtime Policy and Record Status

**Files:**
- Create: `tests/test_dimension_register_runtime_policy.py`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/STATUS.md`
- Modify: `tests/test_documentation_contract.py`

- [ ] **Step 1: Add policy tests**

Prove:

- zero detected clusters after full-page inspection is valid;
- missing or duplicate dispositions are rejected;
- empty text/null value/null unit are allowed only for unresolved/conflict;
- readable number with unresolved attachment cannot become confirmed;
- resolved attachment with ambiguous role cannot become confirmed;
- critical unresolved observations block only declared scopes;
- `NOT_A_DIMENSION` remains auditable outside the register;
- no observer path assigns `DRIVING` without explicit profile metadata.

- [ ] **Step 2: Run focused verification**

```powershell
python -m pytest tests/test_dimension_register_runtime_policy.py tests/test_dimension_observer_run.py primitive_ir_lib/tests/test_dimension_observer.py -q -p no:cacheprovider
```

- [ ] **Step 3: Update canonical documentation**

Record exactly:

```text
VS-T1: Partially verified — offline synthetic Dimension Observer only.
OpenAI API: NOT RUN.
real_data: NOT RUN.
AutoCAD Mechanical: NOT RUN.
No authoritative geometry or publication permission is created.
```

- [ ] **Step 4: Run the authoritative verifier**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Record final head SHA and exact counts. Do not promote unavailable gates.

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
- [ ] Empty pages require no fake dimensions.
- [ ] Completely unreadable observations preserve empty text and null unit/value.
- [ ] Number-only observations without attachments remain `UNRESOLVED`.
- [ ] Ambiguous-role observations never become `CONFIRMED`.
- [ ] Attachment candidates, extension geometry, provenance, and confidence are recorded.
- [ ] No pixel coordinate becomes authoritative Model Space geometry.
- [ ] Output validates through the integrated VS-T0 contract.
- [ ] Focused tests and `scripts/verify.ps1` pass on final head.
- [ ] Private, OpenAI API, and AutoCAD gates remain `NOT RUN`.

## Execution Mode

Run VS-T1 in an isolated branch/worktree. VS-T2 may run in parallel because its runtime write set is disjoint. A single integration reviewer reviews both before VS-T6 consumes them.
