from __future__ import annotations

import json
from pathlib import Path

import cv2
import fitz
import numpy as np
import pytest

from cad_agent import cli, manifest as manifest_owner, pdf as pdf_owner
from cad_agent.manifest import ManifestError, new_manifest, read_manifest, sha256_file
from cad_agent.pdf import new_pdf_manifest, read_pdf_manifest, run_pdf_stages
from primitive_ir_lib.run_image import run as run_image


CLOSED_RING = "closed_ring_identity_v1"
RING_TOOL = "opencv-contour-ring-identity-v1"
TERMINAL = "GEOMETRY_PROPOSALS_NEED_REVIEW"


def _image(path: Path, center: tuple[int, int] = (64, 64)) -> None:
    image = np.full((128, 160, 3), 255, dtype=np.uint8)
    cv2.circle(image, center, 22, (0, 0, 0), 2, cv2.LINE_8)
    assert cv2.imwrite(str(path), image)


def _pdf(path: Path) -> None:
    document = fitz.open()
    document.new_page(width=160, height=128)
    document.save(str(path))
    document.close()


def _primitive(path: Path, *, calibration_status: str = "verified") -> None:
    image_path = path.with_suffix(".png")
    _image(image_path)
    source_hash = sha256_file(image_path)
    run_image(
        str(image_path), str(path), scale_mm_per_px=0.5,
        circle_strategy=CLOSED_RING,
        calibration_status=calibration_status,
        calibration_source_sha256=(source_hash if calibration_status != "verified" else None),
    )


def _stage(state: str, artifact: str | None, digest: str | None) -> dict:
    return {"state": state, "artifact": artifact, "sha256": digest, "details": None}


def _prepared_pdf_candidate(root: Path, *, include_child: bool = False) -> tuple[Path, Path, dict]:
    source = root / "source.pdf"
    _pdf(source)
    output = root / "run"
    lower = output / "pdf"
    rendered = lower / "rendered" / "page_01.png"
    rendered.parent.mkdir(parents=True)
    _image(rendered)
    primitive = lower / "primitive_ir" / "page_01.json"
    primitive.parent.mkdir(parents=True)
    _primitive(primitive)
    candidates: list[dict] = []
    if include_child:
        child_image = lower / "primitive_ir" / "view_ir" / "page_01" / "view_01.png"
        child_image.parent.mkdir(parents=True)
        _image(child_image, (45, 45))
        child_ir = child_image.with_suffix(".json")
        _primitive(child_ir, calibration_status="needs_verification")
        candidates = [{
            "child_ir": child_ir.relative_to(lower).as_posix(),
            "child_image": child_image.relative_to(lower).as_posix(),
            "child_ir_sha256": sha256_file(child_ir),
            "child_image_sha256": sha256_file(child_image),
            "child_calibration_status": "needs_verification",
            "child_state": "needs_verification",
        }]
    lower_manifest_path = lower / "manifest.json"
    lower_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    lower_manifest_path.write_text(json.dumps({
        "pages": [{
            "page": 1,
            "rendered_png": "rendered/page_01.png",
            "primitive_ir": "primitive_ir/page_01.json",
            "scale_label_candidates": candidates,
        }],
    }), encoding="utf-8")
    manifest = new_pdf_manifest(source, 0.5, "ticket-123", 144,
                                circle_strategy=CLOSED_RING)
    manifest["render"] = _stage(
        "completed", "pdf/manifest.json", sha256_file(lower_manifest_path)
    )
    page = pdf_owner._page_record(1, primitive, rendered, output, candidates)
    manifest["pages"] = [page]
    manifest_path = output / pdf_owner.PDF_MANIFEST_NAME
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_owner.write_manifest(manifest_path, manifest)
    return source, manifest_path, manifest


def test_legacy_image_manifest_stays_1_0_and_explicit_selector_is_versioned(tmp_path: Path):
    source = tmp_path / "drawing.png"
    source.write_bytes(b"synthetic image bytes")
    legacy = new_manifest(source, 0.5, "ticket-123")
    explicit = new_manifest(source, 0.5, "ticket-123", circle_strategy=CLOSED_RING)
    assert legacy["schema_version"] == "1.0"
    assert "circle_strategy" not in legacy["configuration"]
    assert explicit["schema_version"] == "1.1"
    assert explicit["configuration"]["circle_strategy"] == CLOSED_RING


@pytest.mark.parametrize("selector", [None, " Hough", "Closed_Ring_Identity_V1", "alias"])
def test_image_manifest_rejects_non_exact_explicit_selector(tmp_path: Path, selector):
    source = tmp_path / "drawing.png"
    source.write_bytes(b"image")
    with pytest.raises(ManifestError):
        new_manifest(source, 0.5, "ticket", circle_strategy=selector)


@pytest.mark.parametrize(
    ("version", "selector", "valid"),
    [
        ("1.0", None, True), ("1.0", "hough", True),
        ("1.0", CLOSED_RING, False), ("1.1", CLOSED_RING, True),
        ("1.1", "hough", True), ("1.1", None, False),
        ("1.2", "hough", False),
    ],
)
def test_image_manifest_version_selector_matrix(tmp_path: Path, version, selector, valid):
    source = tmp_path / "drawing.png"
    source.write_bytes(b"image")
    payload = new_manifest(source, 0.5, "ticket")
    payload["schema_version"] = version
    if selector is not None:
        payload["configuration"]["circle_strategy"] = selector
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    if valid:
        read_manifest(path)
    else:
        with pytest.raises(ManifestError):
            read_manifest(path)


def test_image_cli_explicit_contour_stops_at_validated_candidate_and_terminal_resume(
    tmp_path: Path, monkeypatch,
):
    source = tmp_path / "drawing.png"
    _image(source)
    output = tmp_path / "run"
    monkeypatch.setattr(cli, "_run_semantic", lambda *a, **k: pytest.fail("semantic stage ran"))
    monkeypatch.setattr(cli, "_run_dxf", lambda *a, **k: pytest.fail("DXF stage ran"))
    assert cli.main([
        "run", "--input", str(source), "--output-dir", str(output),
        "--scale-mm-per-px", "0.5", "--calibration-approval", "ticket-123",
        "--circle-strategy", CLOSED_RING,
    ]) == 0

    path = output / "run-manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.1"
    assert payload["configuration"]["circle_strategy"] == CLOSED_RING
    assert payload["result"] == TERMINAL
    assert payload["stages"]["primitive_ir"]["state"] == "completed"
    assert payload["stages"]["semantic_ir"] == _stage("pending", None, None)
    assert payload["stages"]["dxf"] == _stage("pending", None, None)
    assert not (output / "semantic_ir.json").exists()
    assert not (output / "staged.dxf").exists()
    assert not (output / "build-evidence.json").exists()
    primitive = json.loads((output / payload["stages"]["primitive_ir"]["artifact"]).read_text())
    circles = [item for item in primitive["primitives"] if item["type"] == "circle"]
    assert circles and all(item["trace"]["extraction_tool"] == RING_TOOL for item in circles)

    def forbidden(*args, **kwargs):
        pytest.fail("terminal resume performed work")

    monkeypatch.setattr(cli, "_run_primitive", forbidden)
    monkeypatch.setattr(cli, "_run_semantic", forbidden)
    monkeypatch.setattr(cli, "_run_dxf", forbidden)
    assert cli.main(["resume", "--manifest", str(path), "--input", str(source)]) == 0


def test_direct_image_orchestrator_rejects_1_1_without_selector_before_work(tmp_path: Path, monkeypatch):
    source = tmp_path / "drawing.png"
    _image(source)
    payload = new_manifest(source, 0.5, "ticket")
    payload["schema_version"] = "1.1"
    path = tmp_path / "run-manifest.json"

    def forbidden(*args, **kwargs):
        pytest.fail("invalid direct dictionary reached stage work")

    monkeypatch.setattr(cli, "_run_primitive", forbidden)
    with pytest.raises(ManifestError):
        cli.run_stages(source, tmp_path, path, payload)


def test_corrupt_image_terminal_fails_closed_without_regeneration(tmp_path: Path, monkeypatch):
    source = tmp_path / "drawing.png"
    _image(source)
    output = tmp_path / "run"
    assert cli.main([
        "run", "--input", str(source), "--output-dir", str(output),
        "--scale-mm-per-px", "0.5", "--calibration-approval", "ticket-123",
        "--circle-strategy", CLOSED_RING,
    ]) == 0
    manifest_path = output / "run-manifest.json"
    payload = read_manifest(manifest_path)
    artifact = output / payload["stages"]["primitive_ir"]["artifact"]
    artifact.write_text("{}", encoding="utf-8")
    before = manifest_path.read_bytes()
    monkeypatch.setattr(cli, "_run_primitive", lambda *a, **k: pytest.fail("terminal regenerated"))
    with pytest.raises(ManifestError):
        cli.run_stages(source, output, manifest_path, read_manifest(manifest_path))
    assert manifest_path.read_bytes() == before


def test_nonterminal_image_reextracts_bad_checkpoint_with_persisted_selector(tmp_path: Path):
    source = tmp_path / "drawing.png"
    _image(source)
    output = tmp_path / "run"
    output.mkdir()
    manifest = new_manifest(source, 0.5, "ticket-123", circle_strategy=CLOSED_RING)
    manifest["stages"]["primitive_ir"].update(
        state="completed", artifact="primitive_ir.json", sha256="0" * 64
    )
    path = output / "run-manifest.json"
    manifest_owner.write_manifest(path, manifest)

    cli.run_stages(source, output, path, manifest)

    assert manifest["result"] == TERMINAL
    primitive = json.loads((output / "primitive_ir.json").read_text(encoding="utf-8"))
    circles = [item for item in primitive["primitives"] if item["type"] == "circle"]
    assert circles and all(item["trace"]["extraction_tool"] == RING_TOOL for item in circles)


def test_explicit_hough_image_manifest_keeps_normal_stage_continuation(tmp_path: Path, monkeypatch):
    source = tmp_path / "drawing.png"
    _image(source)
    output = tmp_path / "run"
    output.mkdir()
    manifest = new_manifest(source, 0.5, "ticket-123", circle_strategy="hough")
    path = output / "run-manifest.json"
    manifest_owner.write_manifest(path, manifest)
    captured: list[str] = []

    def fake_primitive(source_path, output_path, scale, **kwargs):
        captured.append(kwargs["circle_strategy"])
        output_path.write_text("primitive", encoding="utf-8")

    def fake_semantic(primitive_path, output_path):
        output_path.write_text("semantic", encoding="utf-8")

    def fake_dxf(primitive_path, semantic_path, output_path, evidence_path):
        output_path.write_text("dxf", encoding="utf-8")
        evidence_path.write_text("evidence", encoding="utf-8")
        return "synthetic test stub"

    monkeypatch.setattr(cli, "_run_primitive_with_strategy", fake_primitive)
    monkeypatch.setattr(cli, "_run_semantic", fake_semantic)
    monkeypatch.setattr(cli, "_run_dxf", fake_dxf)
    cli.run_stages(source, output, path, manifest)
    assert captured == ["hough"]
    assert manifest["schema_version"] == "1.1"
    assert manifest.get("result") is None
    assert all(item["state"] == "completed" for item in manifest["stages"].values())


def test_legacy_pdf_manifest_stays_1_0_and_explicit_selector_is_versioned(tmp_path: Path):
    source = tmp_path / "drawing.pdf"
    _pdf(source)
    legacy = new_pdf_manifest(source, 0.5, "ticket", 144)
    explicit = new_pdf_manifest(source, 0.5, "ticket", 144, circle_strategy="hough")
    assert legacy["schema_version"] == "pdf-run-1.0"
    assert "circle_strategy" not in legacy["configuration"]
    assert explicit["schema_version"] == "pdf-run-1.1"
    assert explicit["configuration"]["circle_strategy"] == "hough"


@pytest.mark.parametrize(
    ("version", "selector", "valid"),
    [
        ("pdf-run-1.0", None, True), ("pdf-run-1.0", "hough", True),
        ("pdf-run-1.0", CLOSED_RING, False), ("pdf-run-1.1", CLOSED_RING, True),
        ("pdf-run-1.1", "hough", True), ("pdf-run-1.1", None, False),
        ("pdf-run-1.2", "hough", False),
    ],
)
def test_pdf_manifest_version_selector_matrix(tmp_path: Path, version, selector, valid):
    source = tmp_path / "drawing.pdf"
    _pdf(source)
    payload = new_pdf_manifest(source, 0.5, "ticket", 144)
    payload["schema_version"] = version
    if selector is not None:
        payload["configuration"]["circle_strategy"] = selector
    path = tmp_path / "pdf-manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    if valid:
        read_pdf_manifest(path)
    else:
        with pytest.raises(ManifestError):
            read_pdf_manifest(path)


def test_pdf_candidate_terminal_and_child_hashes_are_read_only_on_resume(
    tmp_path: Path, monkeypatch,
):
    source, manifest_path, manifest = _prepared_pdf_candidate(tmp_path, include_child=True)
    output = manifest_path.parent
    monkeypatch.setattr(cli, "_run_semantic", lambda *a, **k: pytest.fail("semantic stage ran"))
    monkeypatch.setattr(cli, "_run_dxf", lambda *a, **k: pytest.fail("DXF stage ran"))

    run_pdf_stages(source, output, manifest_path, manifest)
    assert manifest["result"] == TERMINAL
    assert all(page["stages"][name]["state"] == "pending"
               and page["stages"][name]["artifact"] is None
               and page["stages"][name]["sha256"] is None
               for page in manifest["pages"] for name in ("semantic_ir", "dxf", "build_evidence"))
    before = manifest_path.read_bytes()
    resumed = read_pdf_manifest(manifest_path)
    monkeypatch.setattr(pdf_owner, "_ensure_rendered", lambda *a, **k: pytest.fail("terminal rerendered"))
    monkeypatch.setattr(cli, "_run_primitive", lambda *a, **k: pytest.fail("terminal re-extracted"))
    run_pdf_stages(source, output, manifest_path, resumed)
    assert manifest_path.read_bytes() == before


def test_nonterminal_pdf_regenerates_invalid_primitive_with_persisted_selector(
    tmp_path: Path, monkeypatch,
):
    source, manifest_path, manifest = _prepared_pdf_candidate(tmp_path)
    manifest["pages"][0]["stages"]["primitive_ir"]["sha256"] = "0" * 64
    manifest_owner.write_manifest(manifest_path, manifest)
    captured: list[str | None] = []
    original = cli._run_primitive_with_strategy

    def recording(*args, **kwargs):
        captured.append(kwargs.get("circle_strategy"))
        return original(*args, **kwargs)

    monkeypatch.setattr(cli, "_run_primitive_with_strategy", recording)
    run_pdf_stages(source, manifest_path.parent, manifest_path, manifest)
    assert captured == [CLOSED_RING]
    assert manifest["result"] == TERMINAL


@pytest.mark.parametrize("corruption", [
    "render_hash", "render_missing", "render_path", "missing_pages", "duplicate_page",
    "child_missing", "child_provenance", "orphan_dxf",
])
def test_pdf_terminal_corruption_fails_closed_without_repair(tmp_path: Path, monkeypatch, corruption):
    source, manifest_path, manifest = _prepared_pdf_candidate(tmp_path, include_child=True)
    output = manifest_path.parent
    run_pdf_stages(source, output, manifest_path, manifest)
    terminal = read_pdf_manifest(manifest_path)
    if corruption == "render_hash":
        terminal["render"]["sha256"] = "0" * 64
    elif corruption == "render_missing":
        (output / terminal["render"]["artifact"]).unlink()
    elif corruption == "render_path":
        terminal["render"]["artifact"] = "pdf/alternate-manifest.json"
    elif corruption == "missing_pages":
        terminal["pages"] = []
    elif corruption == "duplicate_page":
        terminal["pages"].append(dict(terminal["pages"][0]))
    elif corruption == "child_missing":
        candidate = terminal["pages"][0]["scale_label_candidates"][0]
        (output / "pdf" / candidate["child_ir"]).unlink()
    elif corruption == "child_provenance":
        candidate = terminal["pages"][0]["scale_label_candidates"][0]
        child_ir = output / "pdf" / candidate["child_ir"]
        payload = json.loads(child_ir.read_text(encoding="utf-8"))
        circle = next(item for item in payload["primitives"] if item["type"] == "circle")
        circle["trace"]["extraction_tool"] = "other-tool"
        child_ir.write_text(json.dumps(payload), encoding="utf-8")
        candidate["child_ir_sha256"] = sha256_file(child_ir)
    elif corruption == "orphan_dxf":
        dxf = output / "dxf" / "orphan.dxf"
        dxf.parent.mkdir(parents=True)
        dxf.write_text("orphan", encoding="utf-8")
    if corruption not in {"render_missing", "child_missing", "orphan_dxf"}:
        manifest_owner.write_manifest(manifest_path, terminal)
        terminal = read_pdf_manifest(manifest_path)

    before = manifest_path.read_bytes()
    monkeypatch.setattr(pdf_owner, "_ensure_rendered", lambda *a, **k: pytest.fail("corrupt terminal rerendered"))
    monkeypatch.setattr(cli, "_run_primitive_with_strategy", lambda *a, **k: pytest.fail("corrupt terminal re-extracted"))
    monkeypatch.setattr(cli, "_run_semantic", lambda *a, **k: pytest.fail("corrupt terminal ran semantic"))
    monkeypatch.setattr(cli, "_run_dxf", lambda *a, **k: pytest.fail("corrupt terminal ran DXF"))
    with pytest.raises(ManifestError):
        run_pdf_stages(source, output, manifest_path, terminal)
    assert manifest_path.read_bytes() == before


def test_direct_pdf_orchestrator_rejects_1_1_missing_selector_before_render(tmp_path: Path, monkeypatch):
    source = tmp_path / "drawing.pdf"
    _pdf(source)
    manifest = new_pdf_manifest(source, 0.5, "ticket", 144)
    manifest["schema_version"] = "pdf-run-1.1"
    path = tmp_path / "run" / pdf_owner.PDF_MANIFEST_NAME
    monkeypatch.setattr(pdf_owner, "_ensure_rendered", lambda *a, **k: pytest.fail("invalid manifest rendered"))
    with pytest.raises(ManifestError):
        run_pdf_stages(source, path.parent, path, manifest)


def test_pdf_terminal_rejects_outside_root_artifact_before_work(tmp_path: Path, monkeypatch):
    source, manifest_path, manifest = _prepared_pdf_candidate(tmp_path)
    manifest["pages"][0]["stages"]["primitive_ir"]["artifact"] = "../outside.json"
    manifest["result"] = TERMINAL
    manifest_owner.write_manifest(manifest_path, manifest)
    monkeypatch.setattr(pdf_owner, "_ensure_rendered", lambda *a, **k: pytest.fail("invalid terminal rendered"))
    with pytest.raises(ManifestError):
        run_pdf_stages(source, manifest_path.parent, manifest_path,
                       read_pdf_manifest(manifest_path))


def test_pdf_cli_rejects_explicit_selector_with_auto_calibration_before_staging(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    source = tmp_path / "drawing.pdf"
    _pdf(source)
    output = tmp_path / "new-output"
    result = cli.main([
        "run-pdf", "--input", str(source), "--output-dir", str(output),
        "--auto-calibrate", "--circle-strategy", "hough",
    ])
    assert result == 2
    assert "auto-calibrate" in capsys.readouterr().err
    assert not output.exists()

