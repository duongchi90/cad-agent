from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
from pathlib import Path

import fitz
import numpy as np
import pytest

from cad_agent.cli import main
from cad_agent.manifest import ManifestError, sha256_file, write_manifest
from cad_agent.pdf import (
    _requires_auto_ocr_checkpoint_regeneration,
    _resolve_pdf_resume_artifact,
    _validate_pdf_resume_artifacts,
    _write_page_stage,
    new_pdf_manifest,
    read_pdf_manifest,
    run_pdf_stages,
)


def test_pdf_run_image_consumes_the_rendered_source_bytes_when_shared_png_is_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_module = importlib.import_module("primitive_ir_lib.run_pdf")
    image_module = importlib.import_module("primitive_ir_lib.run_image")
    source = tmp_path / "source.pdf"
    replacement = tmp_path / "replacement.pdf"
    output = tmp_path / "run"

    source_document = fitz.open()
    source_page = source_document.new_page(width=400, height=300)
    source_page.draw_line((30, 50), (350, 50), width=3)
    source_document.save(source)
    source_document.close()

    replacement_document = fitz.open()
    replacement_page = replacement_document.new_page(width=400, height=300)
    replacement_page.draw_line((30, 250), (350, 250), width=3)
    replacement_document.save(replacement)
    replacement_document.close()

    with fitz.open(source) as source_document:
        source_bytes = source_document[0].get_pixmap(alpha=False).tobytes("png")
    with fitz.open(replacement) as replacement_document:
        replacement_bytes = replacement_document[0].get_pixmap(alpha=False).tobytes("png")
    expected_pixels = image_module.cv2.imdecode(
        np.frombuffer(source_bytes, dtype=np.uint8),
        image_module.cv2.IMREAD_COLOR,
    )
    expected_pixels_sha256 = hashlib.sha256(expected_pixels.tobytes()).hexdigest()
    observed_geometry_input_hashes: list[str] = []
    original_extract = image_module.extract_raw_geometry
    original_run = pdf_module.run

    def observe_geometry_input(image, **kwargs):
        observed_geometry_input_hashes.append(hashlib.sha256(image.tobytes()).hexdigest())
        return original_extract(image, **kwargs)

    def replace_shared_png_before_image_read(*args, **kwargs):
        Path(kwargs["image_path"]).write_bytes(replacement_bytes)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(image_module, "extract_raw_geometry", observe_geometry_input)
    monkeypatch.setattr(pdf_module, "run", replace_shared_png_before_image_read)

    with pytest.raises(ValueError, match="rendered page changed"):
        pdf_module.run_pdf(
            source,
            output,
            scale_mm_per_px=0.5,
            dpi=72,
            auto_ocr_roi=False,
        )

    assert observed_geometry_input_hashes == [expected_pixels_sha256]
    failed_manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert failed_manifest["status"] == "failed"
    assert failed_manifest["pages"] == []
    assert hashlib.sha256(source_bytes).hexdigest() != hashlib.sha256(replacement_bytes).hexdigest()
    assert not (output / "primitive_ir" / "page_01.json").exists()


def _pdf(path: Path, label: str = "A") -> None:
    document = fitz.open()
    for index in range(2):
        page = document.new_page(width=400, height=300)
        page.draw_line((30, 50 + index * 30), (350, 50 + index * 30))
        page.insert_text((50, 100), f"{label}-{index + 1}")
    document.save(path)
    document.close()


def test_pdf_resume_accepts_windows_short_path_alias_for_manifest_root(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows short-path aliases are only available on Windows")

    import ctypes

    output = tmp_path / "run"
    output.mkdir()
    short_buffer = ctypes.create_unicode_buffer(32768)
    get_short_path = ctypes.windll.kernel32.GetShortPathNameW
    get_short_path.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint)
    get_short_path.restype = ctypes.c_uint
    length = get_short_path(str(output), short_buffer, len(short_buffer))
    if not length or length >= len(short_buffer):
        pytest.skip("The temporary directory has no Windows short-path alias")
    short_output = Path(short_buffer.value)
    if os.path.normcase(str(short_output)) == os.path.normcase(str(output)):
        pytest.skip("8.3 short paths are unavailable for the temporary directory")

    source = tmp_path / "source.pdf"
    source.write_bytes(b"source")
    manifest = {
        "render": {"state": "pending", "artifact": "pdf/manifest.json"},
        "pages": [],
    }

    paths = _validate_pdf_resume_artifacts(
        output.resolve(),
        short_output / "pdf-run-manifest.json",
        source,
        manifest,
    )
    assert paths[("run", "render")] == output / "pdf" / "manifest.json"
    assert _resolve_pdf_resume_artifact(
        short_output,
        "pdf/primitive_ir/page_01.json",
        "pdf/primitive_ir/page_01.json",
        "test",
    ) == output / "pdf" / "primitive_ir" / "page_01.json"


def test_pdf_stage_checkpoint_accepts_mixed_windows_path_aliases(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows short-path aliases are only available on Windows")

    import ctypes

    output = tmp_path / "run"
    output.mkdir()
    short_buffer = ctypes.create_unicode_buffer(32768)
    get_short_path = ctypes.windll.kernel32.GetShortPathNameW
    get_short_path.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint)
    get_short_path.restype = ctypes.c_uint
    length = get_short_path(str(output), short_buffer, len(short_buffer))
    if not length or length >= len(short_buffer):
        pytest.skip("The temporary directory has no Windows short-path alias")
    short_output = Path(short_buffer.value)
    if os.path.normcase(str(short_output)) == os.path.normcase(str(output)):
        pytest.skip("8.3 short paths are unavailable for the temporary directory")

    artifact = output / "semantic_ir" / "page_01.json"
    artifact.parent.mkdir()
    artifact.write_text("{}", encoding="utf-8")
    manifest_path = short_output / "pdf-run-manifest.json"
    manifest: dict[str, object] = {}
    page = {"stages": {}}

    _write_page_stage(
        manifest_path,
        manifest,
        page,
        "semantic_ir",
        artifact,
        "Semantic IR generated.",
    )

    assert page["stages"]["semantic_ir"]["artifact"] == "semantic_ir/page_01.json"


def _dimension_pdf(path: Path, label: str = "1077") -> None:
    document = fitz.open()
    page = document.new_page(width=900, height=600)
    page.draw_line((180, 360), (720, 360), width=1.5)
    page.draw_line((180, 330), (180, 390), width=1.5)
    page.draw_line((720, 330), (720, 390), width=1.5)
    page.insert_text((420, 335), label, fontsize=16, fontname="helv")
    document.save(path)
    document.close()


def _numeric_note_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=900, height=600)
    page.draw_line((180, 360), (720, 360), width=1.5)
    page.insert_text((420, 335), "1077", fontsize=16, fontname="helv")
    document.save(path)
    document.close()


def _numeric_note_with_separate_dimension_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=900, height=600)
    page.draw_line((180, 260), (720, 260), width=1.5)
    page.insert_text((420, 235), "540", fontsize=16, fontname="helv")
    page.draw_line((180, 430), (480, 430), width=1.5)
    page.draw_line((180, 400), (180, 460), width=1.5)
    page.draw_line((480, 400), (480, 460), width=1.5)
    page.insert_text((305, 405), "300", fontsize=16, fontname="helv")
    document.save(path)
    document.close()


def _numeric_note_beside_dimension_structure_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=900, height=600)
    page.draw_line((180, 360), (720, 360), width=1.5)
    page.draw_line((180, 330), (180, 390), width=1.5)
    page.draw_line((720, 330), (720, 390), width=1.5)
    page.insert_text((390, 335), "540", fontsize=16, fontname="helv")
    document.save(path)
    document.close()


def _numeric_note_centered_on_dimension_structure_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=900, height=600)
    page.draw_line((180, 360), (720, 360), width=1.5)
    page.draw_line((180, 330), (180, 390), width=1.5)
    page.draw_line((720, 330), (720, 390), width=1.5)
    page.insert_text((420, 335), "540", fontsize=16, fontname="helv")
    document.save(path)
    document.close()


def test_new_and_historical_pdf_manifests_are_draft_reference(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    source.write_bytes(b"pdf")
    historical_path = tmp_path / "historical-pdf-run.json"
    historical_path.write_text(
        json.dumps(
            {
                "schema_version": "pdf-run-1.0",
                "source": {"name": "drawing.pdf", "sha256": "a" * 64, "kind": "pdf"},
                "configuration": {
                    "scale_mm_per_px": 0.5,
                    "dpi": 300,
                    "auto_ocr_roi": False,
                },
                "approvals": {
                    "calibration": {"approved": True, "reference": "ticket-123"}
                },
                "render": {
                    "state": "pending",
                    "artifact": "pdf/manifest.json",
                    "sha256": None,
                    "details": None,
                },
                "pages": [],
            }
        ),
        encoding="utf-8",
    )

    for manifest in (
        new_pdf_manifest(source, 0.5, "ticket-123", 300),
        read_pdf_manifest(historical_path),
    ):
        assert manifest["release_profile"] == "DRAFT_REFERENCE"
        assert manifest["authoritative_release_eligible"] is False
        assert manifest["drawing_setup_evidence"] is None


@pytest.mark.parametrize(
    ("scale", "label"),
    [(float("nan"), "NaN"), (float("inf"), "+Infinity"), (True, "Boolean True")],
)
def test_new_pdf_manifest_rejects_nonfinite_and_boolean_manual_scales(
    tmp_path: Path, scale: float | bool, label: str
) -> None:
    source = tmp_path / "drawing.pdf"
    source.write_bytes(b"pdf")

    manifest = None
    try:
        manifest = new_pdf_manifest(source, scale, "ticket-123", 144)  # type: ignore[arg-type]
    except ManifestError:
        pass

    assert manifest is None, (
        f"new_pdf_manifest accepted {label} manual scale and produced "
        f"configuration.scale_mm_per_px={manifest['configuration']['scale_mm_per_px']!r}"
    )


@pytest.mark.parametrize("scale_argument", ["nan", "inf"], ids=["nan", "infinity"])
def test_run_pdf_cli_rejects_nonfinite_scale_before_manifest_or_render_staging(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], scale_argument: str
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "run"
    _pdf(source)
    stage_calls: list[Path] = []

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "cad_agent.pdf.run_pdf_stages",
            lambda _source, output_dir, *_args: stage_calls.append(output_dir),
        )
        exit_code = main([
            "run-pdf",
            "--input", str(source),
            "--output-dir", str(output),
            "--scale-mm-per-px", scale_argument,
            "--calibration-approval", "ticket-123",
        ])

    assert exit_code == 2, (
        f"CLI accepted scale {scale_argument!r}; stage calls={len(stage_calls)}, "
        f"manifest exists={(output / 'pdf-run-manifest.json').exists()}, "
        f"stderr={capsys.readouterr().err!r}"
    )
    assert stage_calls == []
    assert not (output / "pdf-run-manifest.json").exists()
    assert not output.exists()


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("release_profile", "AUTHORITATIVE"),
        ("authoritative_release_eligible", True),
        ("drawing_setup_evidence", {"status": "SETUP_VERIFIED"}),
    ],
)
def test_pdf_manifest_refuses_unsafe_release_claim(
    tmp_path: Path, field: str, unsafe_value: object
) -> None:
    source = tmp_path / "drawing.pdf"
    source.write_bytes(b"pdf")
    manifest = new_pdf_manifest(source, 0.5, "ticket-123", 300)
    manifest[field] = unsafe_value
    path = tmp_path / "pdf-run-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ManifestError, match=field):
        read_pdf_manifest(path)


def test_pdf_run_writes_page_checkpoints_and_resume_preserves_them() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "run"
        _pdf(source)
        manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
        run_pdf_stages(source, output, output / "pdf-run-manifest.json", manifest)

        persisted = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        assert len(persisted["pages"]) == 2
        for page in persisted["pages"]:
            assert page["scale_label_candidates"] == []
            assert all(stage["state"] == "completed" and stage["sha256"] for stage in page["stages"].values())
            assert (output / page["stages"]["dxf"]["artifact"]).is_file()
            assert (output / page["stages"]["build_evidence"]["artifact"]).is_file()

        before = (output / "pdf-run-manifest.json").read_bytes()
        run_pdf_stages(source, output, output / "pdf-run-manifest.json", persisted)
        assert (output / "pdf-run-manifest.json").read_bytes() == before


def test_staged_pdf_primitive_path_does_not_reconnect_two_source_runs() -> None:
    """The production PDF stage enables merging; source support must survive it."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "two-source-runs.pdf"
        output = root / "run"
        document = fitz.open()
        page = document.new_page(width=600, height=300)
        page.draw_line((75, 150), (175, 150), color=(0, 0, 0), width=2)
        page.draw_line((181, 150), (281, 150), color=(0, 0, 0), width=2)
        document.save(source)
        document.close()

        manifest = new_pdf_manifest(source, 1.0, "test-reference", 144)
        run_pdf_stages(source, output, output / "pdf-run-manifest.json", manifest)

        persisted = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        page_ir_path = output / persisted["pages"][0]["stages"]["primitive_ir"]["artifact"]
        primitive_ir = json.loads(page_ir_path.read_text(encoding="utf-8"))
        line_boxes = [
            primitive["trace"]["bbox_px"]
            for primitive in primitive_ir["primitives"]
            if primitive.get("type") == "line"
        ]
        assert line_boxes, f"staged primitive IR contained no lines: {primitive_ir['primitives']}"

        # The PDF stage renders at 144 DPI, so the 6 pt source gap is 12 px.
        source_gap = (350, 362)
        assert any(box[0] <= 250 and box[2] >= 250 and box[3] - box[1] <= 6 for box in line_boxes), line_boxes
        assert any(box[0] <= 450 and box[2] >= 450 and box[3] - box[1] <= 6 for box in line_boxes), line_boxes
        assert not any(
            box[0] < source_gap[0] and box[2] > source_gap[1]
            and box[3] - box[1] <= 6
            for box in line_boxes
        ), f"staged PDF -> _run_primitive reconnected the source gap: {line_boxes}"


def test_pdf_resume_rejects_changed_source() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        changed = root / "changed.pdf"
        output = root / "run"
        _pdf(source, "A")
        _pdf(changed, "B")
        manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
        run_pdf_stages(source, output, output / "pdf-run-manifest.json", manifest)

        from cad_agent.manifest import ManifestError

        try:
            run_pdf_stages(changed, output, output / "pdf-run-manifest.json", manifest)
        except ManifestError as exc:
            assert "SHA-256" in str(exc)
        else:  # pragma: no cover - assertion guard
            raise AssertionError("changed PDF was accepted")


@pytest.mark.parametrize("scale", ["0.5", " 5e-1 ", 0.5])
def test_pdf_manual_resume_preserves_finite_positive_numeric_scale_compatibility(
    tmp_path: Path, scale: str | float
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "run"
    _pdf(source)
    manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
    manifest_path = output / "pdf-run-manifest.json"
    run_pdf_stages(source, output, manifest_path, manifest)

    persisted = read_pdf_manifest(manifest_path)
    persisted["configuration"]["scale_mm_per_px"] = scale
    manifest_path.write_text(json.dumps(persisted), encoding="utf-8")
    before = {path: path.read_bytes() for path in output.rglob("*") if path.is_file()}

    run_pdf_stages(source, output, manifest_path, read_pdf_manifest(manifest_path))

    assert {path: path.read_bytes() for path in output.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize(
    ("scale", "label"),
    [
        (float("nan"), "NaN"),
        (float("inf"), "+Infinity"),
        (True, "Boolean True"),
        ("nan", "string NaN"),
        ("inf", "string Infinity"),
        ("0", "zero string"),
        ("-0.5", "negative string"),
        ("not a number", "malformed string"),
        (None, "null"),
        ([], "array"),
        ({}, "object"),
    ],
)
def test_pdf_resume_rejects_invalid_scale_before_cached_render_downstream_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scale: object, label: str
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "run"
    _pdf(source)
    manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
    manifest["configuration"]["scale_mm_per_px"] = scale

    render_manifest_path = output / "pdf" / "manifest.json"
    rendered_path = output / "pdf" / "rendered" / "page_01.png"
    primitive_path = output / "pdf" / "primitive_ir" / "page_01.json"
    for path in (render_manifest_path, rendered_path, primitive_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    render_manifest_path.write_text('{"pages": []}', encoding="utf-8")
    rendered_path.write_bytes(b"verified rendered page")
    primitive_path.write_text('{"primitives": []}', encoding="utf-8")

    def completed(path: Path) -> dict[str, object]:
        return {
            "state": "completed",
            "artifact": path.relative_to(output).as_posix(),
            "sha256": sha256_file(path),
            "details": None,
        }

    def pending(relative_path: str) -> dict[str, object]:
        return {"state": "pending", "artifact": relative_path, "sha256": None, "details": None}

    manifest["render"] = completed(render_manifest_path)
    manifest["pages"] = [{
        "page": 1,
        "scale_label_candidates": [],
        "rendered_png": completed(rendered_path),
        "stages": {
            "primitive_ir": completed(primitive_path),
            "semantic_ir": pending("semantic_ir/page_01.json"),
            "dxf": pending("dxf/page_01.dxf"),
            "build_evidence": pending("build_evidence/page_01.json"),
        },
    }]
    manifest_path = output / "pdf-run-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    before = {path: path.read_bytes() for path in output.rglob("*") if path.is_file()}
    downstream_calls: list[str] = []

    def fake_semantic(_primitive_path: Path, semantic_path: Path) -> None:
        downstream_calls.append("semantic")
        semantic_path.parent.mkdir(parents=True, exist_ok=True)
        semantic_path.write_text("{}", encoding="utf-8")

    def fake_dxf(
        _primitive_path: Path, _semantic_path: Path, dxf_path: Path, evidence_path: Path
    ) -> str:
        downstream_calls.append("dxf")
        for path in (dxf_path, evidence_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic", encoding="utf-8")
        return "synthetic build evidence"

    monkeypatch.setattr("cad_agent.cli._run_semantic", fake_semantic)
    monkeypatch.setattr("cad_agent.cli._run_dxf", fake_dxf)
    caught: ManifestError | None = None
    try:
        run_pdf_stages(source, output, manifest_path, read_pdf_manifest(manifest_path))
    except ManifestError as exc:
        caught = exc

    changed_files = [
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file() and (path not in before or path.read_bytes() != before[path])
    ]
    assert caught is not None, (
        f"resume accepted {label} scale with a cached render; downstream calls={downstream_calls}, "
        f"changed files={changed_files}"
    )
    assert downstream_calls == []
    assert changed_files == []
    assert {path: path.read_bytes() for path in output.rglob("*") if path.is_file()} == before


def test_pdf_resume_rebuilds_only_affected_page_stages() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "run"
        _pdf(source)
        manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
        run_pdf_stages(source, output, output / "pdf-run-manifest.json", manifest)
        original = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        unaffected = original["pages"][1]["stages"]
        (output / original["pages"][0]["stages"]["semantic_ir"]["artifact"]).unlink()

        run_pdf_stages(source, output, output / "pdf-run-manifest.json", original)

        resumed = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        assert resumed["pages"][1]["stages"] == unaffected
        assert all(stage["state"] == "completed" for stage in resumed["pages"][0]["stages"].values())


def test_pdf_resume_regenerates_missing_primitive_from_verified_render() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "run"
        _pdf(source)
        manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
        run_pdf_stages(source, output, output / "pdf-run-manifest.json", manifest)
        persisted = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        (output / persisted["pages"][0]["stages"]["primitive_ir"]["artifact"]).unlink()

        run_pdf_stages(source, output, output / "pdf-run-manifest.json", persisted)

        resumed = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        assert all(stage["state"] == "completed" for stage in resumed["pages"][0]["stages"].values())


@pytest.mark.parametrize("damage", ["missing", "hash-invalid"], ids=["missing", "hash-invalid"])
def test_pdf_resume_excludes_unverified_embedded_text_and_preserves_unaffected_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    image_module = importlib.import_module("primitive_ir_lib.run_image")
    monkeypatch.setattr(
        image_module,
        "detect_text_candidate_rois",
        lambda image: [(0, 0, image.shape[1], image.shape[0])],
    )
    monkeypatch.setattr(image_module, "extract_text_tesseract", lambda *args, **kwargs: [])
    monkeypatch.setattr(image_module, "_configure_tesseract", lambda command: None)

    source = tmp_path / "embedded-text.pdf"
    document = fitz.open()
    first = document.new_page(width=400, height=300)
    first.draw_line((25, 50), (350, 50), width=1)
    first.insert_text((40, 100), "R7,50", fontsize=14)
    second = document.new_page(width=400, height=300)
    second.draw_line((25, 60), (350, 60), width=1)
    second.insert_text((40, 110), "PAGE TWO", fontsize=14)
    document.save(source)
    document.close()

    output = tmp_path / "run"
    manifest_path = output / "pdf-run-manifest.json"
    manifest = new_pdf_manifest(source, 0.5, "synthetic-scale", 144, auto_ocr_roi=True)
    run_pdf_stages(source, output, manifest_path, manifest)
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_page, second_page = persisted["pages"]
    first_primitive = output / first_page["stages"]["primitive_ir"]["artifact"]
    second_page_files = {
        artifact: sha256_file(output / artifact)
        for artifact in [
            second_page["rendered_png"]["artifact"],
            *(stage["artifact"] for stage in second_page["stages"].values()),
        ]
    }

    original_primitive = json.loads(first_primitive.read_text(encoding="utf-8"))
    original_text = [
        item for item in original_primitive["primitives"]
        if item["type"] == "text" and item["text_data"]["content"] == "R7,50"
    ]
    assert original_text == []
    assert first_page["pdf_vector_text_visibility"] == "not_assessed"
    assert first_page["excluded_unverified_pdf_vector_text_span_count"] == 1
    if damage == "missing":
        first_primitive.unlink()
    else:
        first_primitive.write_text("invalid cached primitive", encoding="utf-8")

    run_pdf_stages(source, output, manifest_path, persisted)

    resumed = json.loads(manifest_path.read_text(encoding="utf-8"))
    regenerated = output / resumed["pages"][0]["stages"]["primitive_ir"]["artifact"]
    primitive = json.loads(regenerated.read_text(encoding="utf-8"))
    vector_text = [
        item for item in primitive["primitives"]
        if item["type"] == "text" and item["text_data"]["content"] == "R7,50"
    ]
    assert vector_text == []
    assert resumed["pages"][0]["pdf_vector_text_visibility"] == "not_assessed"
    assert resumed["pages"][0]["excluded_unverified_pdf_vector_text_span_count"] == 1
    assert all(stage["state"] == "completed" for stage in resumed["pages"][0]["stages"].values())

    dxf_path = output / resumed["pages"][0]["stages"]["dxf"]["artifact"]
    dxf_lines = dxf_path.read_text(encoding="utf-8").splitlines()
    assert not any(
        group_code.strip() == "1" and value == "R7,50"
        for group_code, value in zip(dxf_lines, dxf_lines[1:])
    )
    assert {
        artifact: sha256_file(output / artifact) for artifact in second_page_files
    } == second_page_files

    primitive_sha256 = sha256_file(regenerated)
    manifest_bytes = manifest_path.read_bytes()

    def reject_unexpected_regeneration(*args: object, **kwargs: object) -> None:
        raise AssertionError("valid PDF page artifacts were regenerated during resume")

    monkeypatch.setattr("primitive_ir_lib.run_pdf.run_pdf", reject_unexpected_regeneration)
    run_pdf_stages(source, output, manifest_path, resumed)
    assert sha256_file(regenerated) == primitive_sha256
    assert manifest_path.read_bytes() == manifest_bytes


def test_pdf_auto_ocr_resume_rejects_cached_unverified_pdf_text(tmp_path: Path) -> None:
    primitive = tmp_path / "primitive.json"
    primitive.write_text(json.dumps({
        "cross_validations": [],
        "primitives": [{"id": "pdf-old", "source": "text_pdfvector"}],
    }), encoding="utf-8")

    assert _requires_auto_ocr_checkpoint_regeneration(primitive)


@pytest.mark.parametrize("path_kind", ["parent-traversal", "absolute", "symlink"])
def test_pdf_resume_refuses_artifact_paths_outside_output_root_without_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path_kind: str,
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "run"
    manifest_path = output / "pdf-run-manifest.json"
    outside = tmp_path / "outside.json"
    _pdf(source)
    manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
    run_pdf_stages(source, output, manifest_path, manifest)
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    page = persisted["pages"][0]
    outside.write_text("protected sentinel", encoding="utf-8")

    if path_kind == "parent-traversal":
        artifact = "../outside.json"
    elif path_kind == "absolute":
        artifact = str(outside.resolve())
    else:
        link = output / "pdf" / "primitive_ir" / "escape.json"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            pytest.skip(f"file symlink unavailable on this workstation: {exc}")
        artifact = link.relative_to(output).as_posix()

    page["stages"]["primitive_ir"]["artifact"] = artifact
    page["stages"]["primitive_ir"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(persisted), encoding="utf-8")
    manifest_before = manifest_path.read_bytes()
    outputs_before = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file() and path != manifest_path
    }
    sentinel_before = outside.read_bytes()

    manifest_module = importlib.import_module("cad_agent.manifest")
    actual_sha256_file = manifest_module.sha256_file
    external_reads: list[Path] = []

    def observe_external_reads(path: Path) -> str:
        if Path(path).resolve() == outside.resolve():
            external_reads.append(Path(path))
        return actual_sha256_file(path)

    monkeypatch.setattr(manifest_module, "sha256_file", observe_external_reads)

    def reject_extraction(*args: object, **kwargs: object) -> None:
        raise AssertionError("PDF extraction started before unsafe artifact-path refusal")

    monkeypatch.setattr("primitive_ir_lib.run_pdf.run_pdf", reject_extraction)
    with pytest.raises(ManifestError, match="artifact|path|output root"):
        run_pdf_stages(source, output, manifest_path, read_pdf_manifest(manifest_path))

    assert external_reads == []
    assert outside.read_bytes() == sentinel_before
    assert manifest_path.read_bytes() == manifest_before
    assert {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file() and path != manifest_path
    } == outputs_before


def test_pdf_resume_refuses_hardlinked_semantic_artifact_before_overwrite(
    tmp_path: Path,
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "run"
    manifest_path = output / "pdf-run-manifest.json"
    _pdf(source)
    manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
    run_pdf_stages(source, output, manifest_path, manifest)

    persisted = read_pdf_manifest(manifest_path)
    semantic = output / persisted["pages"][0]["stages"]["semantic_ir"]["artifact"]
    semantic.unlink()
    outside = tmp_path / "outside-semantic.json"
    sentinel = b"protected external content"
    outside.write_bytes(sentinel)
    try:
        os.link(outside, semantic)
    except OSError as exc:
        pytest.skip(f"hard links unavailable on this workstation: {exc}")

    persisted["pages"][0]["stages"]["semantic_ir"].update(
        {"state": "pending", "sha256": None}
    )
    manifest_path.write_text(json.dumps(persisted), encoding="utf-8")

    with pytest.raises(ManifestError, match="hard link|multiple links"):
        run_pdf_stages(source, output, manifest_path, read_pdf_manifest(manifest_path))

    assert outside.read_bytes() == sentinel
    after = read_pdf_manifest(manifest_path)
    assert after["pages"][0]["stages"]["semantic_ir"]["state"] == "pending"


def test_pdf_resume_refuses_hardlinked_run_manifest_before_render_write(
    tmp_path: Path,
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "run"
    manifest_path = output / "pdf-run-manifest.json"
    outside = tmp_path / "outside-run-manifest.json"
    _pdf(source)
    manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
    output.mkdir()
    outside.write_text(json.dumps(manifest), encoding="utf-8")
    try:
        os.link(outside, manifest_path)
    except OSError as exc:
        pytest.skip(f"hard links unavailable on this workstation: {exc}")
    sentinel = outside.read_bytes()

    with pytest.raises(ManifestError, match="hard link|multiple links"):
        run_pdf_stages(source, output, manifest_path, read_pdf_manifest(manifest_path))

    assert outside.read_bytes() == sentinel
    assert not (output / "pdf" / "manifest.json").exists()


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_manifest_write_preserves_external_bytes_at_preexisting_temp_alias(
    tmp_path: Path,
    link_kind: str,
) -> None:
    manifest_path = tmp_path / "pdf-run-manifest.json"
    temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    outside = tmp_path / "outside-manifest.json"
    sentinel = b"protected external bytes"
    outside.write_bytes(sentinel)
    try:
        if link_kind == "symlink":
            temporary.symlink_to(outside)
        else:
            os.link(outside, temporary)
    except OSError as exc:
        pytest.skip(f"{link_kind} unavailable on this workstation: {exc}")

    write_manifest(manifest_path, {"state": "updated"})

    assert outside.read_bytes() == sentinel
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == {"state": "updated"}


def test_pdf_pending_render_refuses_later_page_symlink_before_renderer_write(
    tmp_path: Path,
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "run"
    manifest_path = output / "pdf-run-manifest.json"
    outside = tmp_path / "outside-page-two.json"
    sentinel = b"protected external content"
    outside.write_bytes(sentinel)
    _pdf(source)

    page_two = output / "pdf" / "primitive_ir" / "page_02.json"
    page_two.parent.mkdir(parents=True)
    try:
        page_two.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"file symlinks unavailable on this workstation: {exc}")

    manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
    with pytest.raises(ManifestError, match="redirect|reparse|symbolic link|escapes"):
        run_pdf_stages(source, output, manifest_path, manifest)

    assert outside.read_bytes() == sentinel
    assert not (output / "pdf" / "manifest.json").exists()


def test_pdf_resume_refuses_cross_page_artifact_alias_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "run"
    manifest_path = output / "pdf-run-manifest.json"
    _pdf(source)
    manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144)
    run_pdf_stages(source, output, manifest_path, manifest)
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_page, second_page = persisted["pages"]
    first_page["stages"]["primitive_ir"]["artifact"] = second_page["stages"]["primitive_ir"]["artifact"]
    first_page["stages"]["primitive_ir"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(persisted), encoding="utf-8")
    manifest_before = manifest_path.read_bytes()
    outputs_before = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file() and path != manifest_path
    }

    def reject_extraction(*args: object, **kwargs: object) -> None:
        raise AssertionError("PDF extraction started before cross-page alias refusal")

    monkeypatch.setattr("primitive_ir_lib.run_pdf.run_pdf", reject_extraction)
    with pytest.raises(ManifestError, match="artifact|page|alias|destination"):
        run_pdf_stages(source, output, manifest_path, read_pdf_manifest(manifest_path))

    assert manifest_path.read_bytes() == manifest_before
    assert {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file() and path != manifest_path
    } == outputs_before


def test_pdf_resume_does_not_complete_stages_when_source_render_identity_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_module = importlib.import_module("primitive_ir_lib.run_image")
    pdf_module = importlib.import_module("primitive_ir_lib.run_pdf")
    monkeypatch.setattr(
        image_module,
        "detect_text_candidate_rois",
        lambda image: [(0, 0, image.shape[1], image.shape[0])],
    )
    monkeypatch.setattr(image_module, "extract_text_tesseract", lambda *args, **kwargs: [])
    monkeypatch.setattr(image_module, "_configure_tesseract", lambda command: None)

    source = tmp_path / "identity-change.pdf"
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 100), "R7,50", fontsize=14)
    document.save(source)
    document.close()

    output = tmp_path / "run"
    manifest_path = output / "pdf-run-manifest.json"
    manifest = new_pdf_manifest(source, 0.5, "synthetic-scale", 144, auto_ocr_roi=True)
    run_pdf_stages(source, output, manifest_path, manifest)
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    page_record = persisted["pages"][0]
    primitive_path = output / page_record["stages"]["primitive_ir"]["artifact"]
    primitive_path.unlink()

    original_run_pdf = pdf_module.run_pdf

    def changed_render(*args: object, **kwargs: object) -> dict[str, object]:
        regenerated = original_run_pdf(*args, **kwargs)
        rendered_path = Path(args[1]) / regenerated["pages"][0]["rendered_png"]
        rendered_path.write_bytes(b"changed render identity")
        return regenerated

    monkeypatch.setattr(pdf_module, "run_pdf", changed_render)
    with pytest.raises(ManifestError, match="render differs"):
        run_pdf_stages(source, output, manifest_path, persisted)

    failed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert all(stage["state"] == "pending" for stage in failed["pages"][0]["stages"].values())
    assert not primitive_path.exists()


@pytest.mark.parametrize(
    ("ocr_policy", "expected_text", "expected_dimensions"),
    [
        (True, ["1077"], 0),
        (False, [], 0),
        (None, [], 0),
    ],
    ids=["default-on", "explicit-off", "historical-manifest"],
)
def test_pdf_resume_regenerates_missing_primitive_with_ocr_policy(
    ocr_policy: bool | None,
    expected_text: list[str],
    expected_dimensions: int,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "dimension.pdf"
        output = root / "run"
        _dimension_pdf(source)
        manifest = new_pdf_manifest(source, 1, "synthetic-scale", 144)
        if ocr_policy is None:
            manifest["configuration"].pop("auto_ocr_roi")
        else:
            manifest["configuration"]["auto_ocr_roi"] = ocr_policy

        manifest_path = output / "pdf-run-manifest.json"
        run_pdf_stages(source, output, manifest_path, manifest)
        persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
        primitive_path = output / persisted["pages"][0]["stages"]["primitive_ir"]["artifact"]
        primitive_path.unlink()

        run_pdf_stages(source, output, manifest_path, persisted)

        resumed = json.loads(manifest_path.read_text(encoding="utf-8"))
        primitive = json.loads(primitive_path.read_text(encoding="utf-8"))
        text = [item["text_data"]["content"] for item in primitive["primitives"] if item["type"] == "text"]
        evidence = json.loads((output / "build_evidence/page_01.json").read_text(encoding="utf-8"))
        assert text == expected_text
        assert evidence["build_result"]["dimension_count"] == expected_dimensions
        if ocr_policy:
            assert primitive["cross_validations"][0]["status"] == "unverified"
        if ocr_policy is None:
            assert "auto_ocr_roi" not in resumed["configuration"]
        else:
            assert resumed["configuration"]["auto_ocr_roi"] is ocr_policy


@pytest.mark.parametrize("remove_dxf", [True, False], ids=["missing-dxf", "completed-dxf"])
def test_pdf_resume_rebuilds_legacy_confirmed_ocr_primitive(remove_dxf: bool) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "dimension.pdf"
        output = root / "run"
        _dimension_pdf(source)
        manifest = new_pdf_manifest(source, 1, "synthetic-scale", 144, auto_ocr_roi=True)
        manifest_path = output / "pdf-run-manifest.json"
        run_pdf_stages(source, output, manifest_path, manifest)

        persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
        page = persisted["pages"][0]
        primitive_path = output / page["stages"]["primitive_ir"]["artifact"]
        primitive = json.loads(primitive_path.read_text(encoding="utf-8"))
        primitive["cross_validations"][0]["status"] = "confirmed"
        primitive_path.write_text(json.dumps(primitive), encoding="utf-8")
        page["stages"]["primitive_ir"]["sha256"] = sha256_file(primitive_path)
        dxf_path = output / page["stages"]["dxf"]["artifact"]
        evidence_path = output / page["stages"]["build_evidence"]["artifact"]
        if remove_dxf:
            dxf_path.unlink()
            evidence_path.unlink()
            page["stages"]["dxf"] = {"state": "pending", "artifact": None, "sha256": None, "details": None}
            page["stages"]["build_evidence"] = {"state": "pending", "artifact": None, "sha256": None, "details": None}
        manifest_path.write_text(json.dumps(persisted), encoding="utf-8")

        run_pdf_stages(source, output, manifest_path, persisted)

        repaired = json.loads(primitive_path.read_text(encoding="utf-8"))
        evidence = json.loads((output / "build_evidence/page_01.json").read_text(encoding="utf-8"))
        assert repaired["cross_validations"][0]["status"] == "unverified"
        assert evidence["build_result"]["dimension_count"] == 0


def test_pdf_cli_run_and_resume() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "run"
        _pdf(source)

        assert main([
            "run-pdf",
            "--input", str(source),
            "--output-dir", str(output),
            "--scale-mm-per-px", "0.5",
            "--calibration-approval", "ticket-123",
            "--dpi", "144",
        ]) == 0
        assert main([
            "resume-pdf",
            "--manifest", str(output / "pdf-run-manifest.json"),
            "--input", str(source),
        ]) == 0


@pytest.mark.parametrize("damage", ["missing", "hash-invalid"])
def test_pdf_cli_resume_rejects_invalid_rendered_page_without_mutating_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damage: str
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "run"
    _pdf(source)
    manifest_path = output / "pdf-run-manifest.json"

    assert main([
        "run-pdf",
        "--input", str(source),
        "--output-dir", str(output),
        "--scale-mm-per-px", "0.5",
        "--calibration-approval", "ticket-123",
        "--dpi", "144",
    ]) == 0
    manifest_before = manifest_path.read_bytes()
    persisted = json.loads(manifest_before)
    rendered = output / persisted["pages"][0]["rendered_png"]["artifact"]
    if damage == "missing":
        rendered.unlink()
    else:
        rendered.write_bytes(b"changed rendered page")

    result = main([
        "resume-pdf",
        "--manifest", str(manifest_path),
        "--input", str(source),
    ])
    capsys.readouterr()

    assert result != 0
    assert manifest_path.read_bytes() == manifest_before
    assert all(page["rendered_png"]["state"] == "completed" for page in persisted["pages"])


def test_pdf_cli_auto_calibration_candidate_stops_before_semantic_or_dxf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from primitive_ir_lib.geometry_extraction import RawGeometry, RawLine
    from primitive_ir_lib.text_extraction import RawText

    source = tmp_path / "drawing.pdf"
    output = tmp_path / "candidate"
    _pdf(source)

    def synthetic_geometry(image, **kwargs):
        return RawGeometry(lines=[RawLine(
            id="synthetic-dimension-line",
            p1_px=(40.0, 100.0),
            p2_px=(240.0, 100.0),
            confidence=1.0,
            bbox_px=(40.0, 100.0, 240.0, 100.0),
        )])

    def synthetic_text(image, roi_boxes, **kwargs):
        return [RawText(
            id="synthetic-dimension-text",
            content="100",
            bbox_px=(130, 80, 150, 95),
            rotation_deg=0.0,
            confidence=1.0,
            source="text_tesseract",
            parsed_value=100.0,
            semantic_role="dimension_value",
        )]

    monkeypatch.setattr("primitive_ir_lib.run_image.extract_raw_geometry", synthetic_geometry)
    monkeypatch.setattr("primitive_ir_lib.run_image.detect_text_candidate_rois", lambda image: [(0, 0, image.shape[1], image.shape[0])])
    monkeypatch.setattr("primitive_ir_lib.run_image.extract_text_tesseract", synthetic_text)
    monkeypatch.setattr("primitive_ir_lib.run_image._configure_tesseract", lambda command: None)
    result = main([
        "run-pdf", "--input", str(source), "--output-dir", str(output),
        "--auto-calibrate",
    ])

    assert result == 0
    assert "CALIBRATION_NEEDS_VERIFICATION" in capsys.readouterr().out
    manifest = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
    assert manifest["release_profile"] == "DRAFT_REFERENCE"
    assert manifest["authoritative_release_eligible"] is False
    assert manifest["result"] == "CALIBRATION_NEEDS_VERIFICATION"
    registry = json.loads((output / "calibration-registry.json").read_text(encoding="utf-8"))
    assert [record["id"] for record in registry["records"]] == ["run_pdf_page01", "run_pdf_page02"]
    assert all(record["status"] == "needs_verification" for record in registry["records"])
    for page in manifest["pages"]:
        primitive_path = output / page["stages"]["primitive_ir"]["artifact"]
        primitive = json.loads(primitive_path.read_text(encoding="utf-8"))
        assert primitive["calibration"]["status"] == "needs_verification"
        assert page["calibration"]["status"] == "needs_verification"
        assert page["calibration"]["candidate_id"] == f"run_pdf_page{page['page']:02d}"
        assert page["stages"]["semantic_ir"]["state"] == "pending"
        assert page["stages"]["dxf"]["state"] == "pending"
        assert page["stages"]["build_evidence"]["state"] == "pending"
    assert not list(output.rglob("semantic_ir"))
    assert not list(output.rglob("*.dxf"))
    assert not list(output.rglob("build_evidence"))


def test_pdf_cli_auto_calibration_candidate_rejects_manual_calibration(
    tmp_path: Path,
) -> None:
    source = tmp_path / "drawing.pdf"
    _pdf(source)

    result = main([
        "run-pdf", "--input", str(source), "--output-dir", str(tmp_path / "candidate"),
        "--auto-calibrate", "--scale-mm-per-px", "0.5",
        "--calibration-approval", "verified-ticket",
    ])
    assert result == 2


def test_pdf_no_candidate_resume_returns_terminal_without_reextraction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lower_pdf = importlib.import_module("primitive_ir_lib.run_pdf")
    image_module = importlib.import_module("primitive_ir_lib.run_image")
    geometry_module = importlib.import_module("primitive_ir_lib.geometry_extraction")
    original_run = lower_pdf.run
    extraction_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def count_run(*args: object, **kwargs: object) -> str:
        extraction_calls.append((args, kwargs))
        return original_run(*args, **kwargs)

    monkeypatch.setattr(lower_pdf, "run", count_run)
    monkeypatch.setattr(
        image_module,
        "extract_raw_geometry",
        lambda *_args, **_kwargs: geometry_module.RawGeometry(),
    )
    monkeypatch.setattr(image_module, "detect_text_candidate_rois", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(image_module, "extract_text_tesseract", lambda *_args, **_kwargs: [])

    source = tmp_path / "no-calibration.pdf"
    output = tmp_path / "no-calibration"
    manifest_path = output / "pdf-run-manifest.json"
    _pdf(source)

    from cad_agent.pdf import run_pdf_calibration_candidate

    manifest = run_pdf_calibration_candidate(source, output, manifest_path, 144)
    no_candidate_result = "CALIBRATION_CANDIDATE_EXTRACTION_NOT_SUPPORTED_FOR_THIS_SOURCE"
    assert manifest["result"] == no_candidate_result
    assert 0 < len(manifest["details"]) <= 500
    assert manifest["render"]["state"] == "pending"
    assert manifest["pages"] == []
    assert not (output / "calibration-registry.json").exists()
    assert len(extraction_calls) == 1

    with pytest.raises(ManifestError) as resume_error:
        run_pdf_stages(source, output, manifest_path, read_pdf_manifest(manifest_path))
    assert len(extraction_calls) == 1
    assert no_candidate_result in str(resume_error.value)
    assert not (output / "semantic_ir").exists()
    assert not (output / "dxf").exists()
    assert not (output / "build_evidence").exists()

    malformed = read_pdf_manifest(manifest_path)
    malformed["details"] = "x" * 501
    with pytest.raises(ManifestError, match="terminal diagnostics are invalid"):
        run_pdf_stages(source, output, manifest_path, malformed)
    assert len(extraction_calls) == 1

    source.write_bytes(source.read_bytes() + b"changed source")
    with pytest.raises(ManifestError, match="SHA-256 does not match"):
        run_pdf_stages(source, output, manifest_path, read_pdf_manifest(manifest_path))
    assert len(extraction_calls) == 1


def test_pdf_candidate_does_not_misclassify_unrelated_value_error_with_matching_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_module = importlib.import_module("primitive_ir_lib.run_image")
    geometry_module = importlib.import_module("primitive_ir_lib.geometry_extraction")
    from cad_agent.pdf import run_pdf_calibration_candidate

    monkeypatch.setattr(
        image_module,
        "extract_raw_geometry",
        lambda *_args, **_kwargs: geometry_module.RawGeometry(),
    )
    monkeypatch.setattr(
        image_module,
        "detect_text_candidate_rois",
        lambda *_args, **_kwargs: [(1, 1, 40, 40)],
    )

    def raise_unrelated_error(*_args: object, **_kwargs: object) -> list[object]:
        raise ValueError(
            "OCR decoding failed; auto_calibrate không tìm được cặp is only diagnostic text"
        )

    monkeypatch.setattr(image_module, "extract_text_tesseract", raise_unrelated_error)
    unrelated_source = tmp_path / "unrelated-error.pdf"
    unrelated_output = tmp_path / "unrelated-error"
    _pdf(unrelated_source)
    with pytest.raises(ValueError, match="OCR decoding failed"):
        run_pdf_calibration_candidate(
            unrelated_source,
            unrelated_output,
            unrelated_output / "pdf-run-manifest.json",
            144,
        )


@pytest.mark.parametrize("entry_point", ["direct", "resume-cli"])
@pytest.mark.parametrize("approved", [False, True], ids=["unapproved", "approval-edited"])
def test_pdf_candidate_manifest_is_rejected_before_resume_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    entry_point: str,
    approved: bool,
) -> None:
    source = tmp_path / "drawing.pdf"
    output = tmp_path / "run"
    output.mkdir()
    _pdf(source)

    rendered_path = output / "pdf" / "rendered_page01.png"
    primitive_path = output / "pdf" / "primitive_ir" / "page_01.json"
    rendered_path.parent.mkdir(parents=True)
    primitive_path.parent.mkdir(parents=True)
    rendered_path.write_bytes(b"synthetic rendered page")
    primitive_path.write_text(
        json.dumps({
            "calibration": {
                "status": "needs_verification",
                "source_sha256": sha256_file(rendered_path),
            },
        }),
        encoding="utf-8",
    )
    lower_manifest_path = output / "pdf" / "manifest.json"
    lower_manifest_path.write_text("{}", encoding="utf-8")

    manifest = new_pdf_manifest(source, 0.5, "synthetic-approval", 144)
    manifest["configuration"].pop("scale_mm_per_px")
    manifest["configuration"]["calibration_mode"] = "auto_candidate"
    manifest["approvals"]["calibration"] = {
        "approved": approved,
        "reference": "edited-approval" if approved else None,
        "status": "needs_verification",
    }
    manifest["result"] = "CALIBRATION_NEEDS_VERIFICATION"
    manifest["render"] = {
        "state": "completed",
        "artifact": "pdf/manifest.json",
        "sha256": sha256_file(lower_manifest_path),
        "details": None,
    }
    manifest["pages"] = [{
        "page": 1,
        "rendered_png": {
            "state": "completed",
            "artifact": "pdf/rendered_page01.png",
            "sha256": sha256_file(rendered_path),
            "details": None,
        },
        "calibration": {
            "candidate_id": "run_pdf_page01",
            "status": "needs_verification",
            "source_sha256": sha256_file(rendered_path),
        },
        "stages": {
            "primitive_ir": {
                "state": "completed",
                "artifact": "pdf/primitive_ir/page_01.json",
                "sha256": sha256_file(primitive_path),
                "details": None,
            },
            "semantic_ir": {"state": "pending", "artifact": None, "sha256": None, "details": None},
            "dxf": {"state": "pending", "artifact": None, "sha256": None, "details": None},
            "build_evidence": {"state": "pending", "artifact": None, "sha256": None, "details": None},
        },
    }]
    manifest_path = output / "pdf-run-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    original_manifest_bytes = manifest_path.read_bytes()
    downstream_calls: list[str] = []

    def record_downstream(*args: object, **kwargs: object) -> None:
        downstream_calls.append("_ensure_rendered")
        raise AssertionError("candidate manifest reached the resume renderer")

    monkeypatch.setattr("cad_agent.pdf._ensure_rendered", record_downstream)
    expected_error = "Auto-calibration candidate manifests cannot be resumed."

    if entry_point == "direct":
        with pytest.raises(ManifestError, match=expected_error):
            run_pdf_stages(source, output, manifest_path, read_pdf_manifest(manifest_path))
    else:
        assert main([
            "resume-pdf", "--manifest", str(manifest_path), "--input", str(source),
        ]) == 2
        assert expected_error in capsys.readouterr().err

    assert downstream_calls == []
    assert manifest_path.read_bytes() == original_manifest_bytes
    assert not (output / "semantic_ir").exists()
    assert not (output / "dxf").exists()
    assert not (output / "build_evidence").exists()


def test_pdf_cli_persists_auto_ocr_roi_choice() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "drawing.pdf"
        output = root / "run"
        _pdf(source)

        assert main([
            "run-pdf",
            "--input", str(source),
            "--output-dir", str(output),
            "--scale-mm-per-px", "0.5",
            "--calibration-approval", "ticket-123",
            "--auto-ocr-roi",
        ]) == 0
        manifest = json.loads((output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        assert manifest["configuration"]["auto_ocr_roi"] is True


def test_pdf_manifest_helper_default_remains_geometry_only() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "dimension.pdf"
        output = root / "run"
        _dimension_pdf(source)

        manifest = new_pdf_manifest(source, 1, "synthetic-scale", 144)
        manifest_path = output / "pdf-run-manifest.json"
        run_pdf_stages(source, output, manifest_path, manifest)

        persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
        primitive = json.loads((output / "pdf/primitive_ir/page_01.json").read_text(encoding="utf-8"))
        evidence = json.loads((output / "build_evidence/page_01.json").read_text(encoding="utf-8"))
        assert persisted["configuration"]["auto_ocr_roi"] is False
        assert not [item for item in primitive["primitives"] if item["type"] == "text"]
        assert evidence["build_result"]["dimension_count"] == 0


def test_pdf_cli_defaults_to_ocr_and_retains_explicit_geometry_only_opt_out() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "dimension.pdf"
        _dimension_pdf(source)

        default_output = root / "default"
        assert main([
            "run-pdf", "--input", str(source), "--output-dir", str(default_output),
            "--scale-mm-per-px", "1", "--calibration-approval", "synthetic-scale",
        ]) == 0
        default_manifest = json.loads((default_output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        assert default_manifest["configuration"]["auto_ocr_roi"] is True
        primitive = json.loads((default_output / "pdf/primitive_ir/page_01.json").read_text(encoding="utf-8"))
        assert [item["text_data"]["content"] for item in primitive["primitives"] if item["type"] == "text"] == ["1077"]
        assert primitive["cross_validations"][0]["status"] == "unverified"
        evidence = json.loads((default_output / "build_evidence/page_01.json").read_text(encoding="utf-8"))
        assert evidence["build_result"]["dimension_count"] == 0
        assert main([
            "resume-pdf", "--manifest", str(default_output / "pdf-run-manifest.json"),
            "--input", str(source),
        ]) == 0
        resumed = json.loads((default_output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        assert resumed["configuration"]["auto_ocr_roi"] is True

        opt_out_output = root / "opt-out"
        assert main([
            "run-pdf", "--input", str(source), "--output-dir", str(opt_out_output),
            "--scale-mm-per-px", "1", "--calibration-approval", "synthetic-scale",
            "--no-auto-ocr-roi",
        ]) == 0
        opt_out_manifest = json.loads((opt_out_output / "pdf-run-manifest.json").read_text(encoding="utf-8"))
        assert opt_out_manifest["configuration"]["auto_ocr_roi"] is False
        opt_out_ir = json.loads((opt_out_output / "pdf/primitive_ir/page_01.json").read_text(encoding="utf-8"))
        assert not [item for item in opt_out_ir["primitives"] if item["type"] == "text"]
        opt_out_evidence = json.loads((opt_out_output / "build_evidence/page_01.json").read_text(encoding="utf-8"))
        assert opt_out_evidence["build_result"]["dimension_count"] == 0


def test_pdf_auto_ocr_does_not_create_dimension_without_cross_validation_support() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "dimension-conflict.pdf"
        output = root / "run"
        _dimension_pdf(source, label="1200")

        assert main([
            "run-pdf", "--input", str(source), "--output-dir", str(output),
            "--scale-mm-per-px", "1", "--calibration-approval", "synthetic-scale",
        ]) == 0
        primitive = json.loads((output / "pdf/primitive_ir/page_01.json").read_text(encoding="utf-8"))
        assert [item["text_data"]["content"] for item in primitive["primitives"] if item["type"] == "text"] == ["1200"]
        assert primitive["cross_validations"][0]["status"] == "unverified"
        evidence = json.loads((output / "build_evidence/page_01.json").read_text(encoding="utf-8"))
        assert evidence["build_result"]["dimension_count"] == 0


def test_pdf_auto_ocr_does_not_confirm_nearby_numeric_note_as_dimension() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "numeric-note.pdf"
        output = root / "run"
        _numeric_note_pdf(source)

        assert main([
            "run-pdf", "--input", str(source), "--output-dir", str(output),
            "--scale-mm-per-px", "1", "--calibration-approval", "synthetic-scale",
        ]) == 0
        primitive = json.loads((output / "pdf/primitive_ir/page_01.json").read_text(encoding="utf-8"))
        evidence = json.loads((output / "build_evidence/page_01.json").read_text(encoding="utf-8"))
        assert primitive["cross_validations"][0]["status"] != "confirmed"
        assert evidence["build_result"]["dimension_count"] == 0


def test_pdf_auto_ocr_does_not_borrow_separate_dimension_geometry_for_note() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "numeric-note-and-dimension.pdf"
        output = root / "run"
        _numeric_note_with_separate_dimension_pdf(source)

        assert main([
            "run-pdf", "--input", str(source), "--output-dir", str(output),
            "--scale-mm-per-px", "0.5", "--calibration-approval", "synthetic-scale",
        ]) == 0
        primitive = json.loads((output / "pdf/primitive_ir/page_01.json").read_text(encoding="utf-8"))
        cross_validations = {item["text_value"]: item["status"] for item in primitive["cross_validations"]}
        assert cross_validations[540.0] != "confirmed"
        assert cross_validations[300.0] == "unverified"
        evidence = json.loads((output / "build_evidence/page_01.json").read_text(encoding="utf-8"))
        assert evidence["build_result"]["dimension_count"] == 0


def test_pdf_auto_ocr_does_not_confirm_off_center_note_beside_dimension_geometry() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "numeric-note-beside-dimension.pdf"
        output = root / "run"
        _numeric_note_beside_dimension_structure_pdf(source)

        assert main([
            "run-pdf", "--input", str(source), "--output-dir", str(output),
            "--scale-mm-per-px", "0.5", "--calibration-approval", "synthetic-scale",
        ]) == 0
        primitive = json.loads((output / "pdf/primitive_ir/page_01.json").read_text(encoding="utf-8"))
        evidence = json.loads((output / "build_evidence/page_01.json").read_text(encoding="utf-8"))
        assert primitive["cross_validations"][0]["status"] != "confirmed"
        assert evidence["build_result"]["dimension_count"] == 0


def test_pdf_auto_ocr_does_not_confirm_centered_note_without_association() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "centered-numeric-note.pdf"
        output = root / "run"
        _numeric_note_centered_on_dimension_structure_pdf(source)

        assert main([
            "run-pdf", "--input", str(source), "--output-dir", str(output),
            "--scale-mm-per-px", "0.5", "--calibration-approval", "synthetic-scale",
        ]) == 0
        primitive = json.loads((output / "pdf/primitive_ir/page_01.json").read_text(encoding="utf-8"))
        evidence = json.loads((output / "build_evidence/page_01.json").read_text(encoding="utf-8"))
        assert primitive["cross_validations"][0]["status"] != "confirmed"
        assert evidence["build_result"]["dimension_count"] == 0


def test_historical_pdf_manifest_without_ocr_choice_remains_geometry_only() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "dimension.pdf"
        output = root / "run"
        _dimension_pdf(source)
        manifest = new_pdf_manifest(source, 1, "synthetic-scale", 144)
        manifest["configuration"].pop("auto_ocr_roi")
        manifest_path = output / "pdf-run-manifest.json"
        output.mkdir()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        historical = read_pdf_manifest(manifest_path)
        run_pdf_stages(source, output, manifest_path, historical)

        persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "auto_ocr_roi" not in persisted["configuration"]
        primitive = json.loads((output / "pdf/primitive_ir/page_01.json").read_text(encoding="utf-8"))
        assert not [item for item in primitive["primitives"] if item["type"] == "text"]
