from __future__ import annotations

import json
import tempfile
from pathlib import Path

import fitz
import pytest

from cad_agent.cli import main
from cad_agent.manifest import ManifestError
from cad_agent.pdf import new_pdf_manifest, read_pdf_manifest, run_pdf_stages


def _pdf(path: Path, label: str = "A") -> None:
    document = fitz.open()
    for index in range(2):
        page = document.new_page(width=400, height=300)
        page.draw_line((30, 50 + index * 30), (350, 50 + index * 30))
        page.insert_text((50, 100), f"{label}-{index + 1}")
    document.save(path)
    document.close()


def _dimension_pdf(path: Path, label: str = "1077") -> None:
    document = fitz.open()
    page = document.new_page(width=900, height=600)
    page.draw_line((180, 360), (720, 360), width=1.5)
    page.draw_line((180, 330), (180, 390), width=1.5)
    page.draw_line((720, 330), (720, 390), width=1.5)
    page.insert_text((420, 335), label, fontsize=16, fontname="helv")
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


@pytest.mark.parametrize(
    ("ocr_policy", "expected_text", "expected_dimensions"),
    [
        (True, ["1077"], 1),
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
        if ocr_policy is None:
            assert "auto_ocr_roi" not in resumed["configuration"]
        else:
            assert resumed["configuration"]["auto_ocr_roi"] is ocr_policy


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
        assert primitive["cross_validations"][0]["status"] == "confirmed"
        evidence = json.loads((default_output / "build_evidence/page_01.json").read_text(encoding="utf-8"))
        assert evidence["build_result"]["dimension_count"] == 1
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
        assert primitive["cross_validations"][0]["status"] == "conflict"
        evidence = json.loads((output / "build_evidence/page_01.json").read_text(encoding="utf-8"))
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
