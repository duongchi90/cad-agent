"""Regression test for the multi-page PDF to Primitive IR runner."""

import json
from pathlib import Path

import fitz

from primitive_ir_lib.run_pdf import run_pdf


def test_run_pdf_creates_manifest_and_page_ir(tmp_path: Path):
    pdf_path = tmp_path / "fixture.pdf"
    output_dir = tmp_path / "output"
    document = fitz.open()
    for offset in (0, 10):
        page = document.new_page(width=200, height=100)
        page.draw_line((10, 20 + offset), (190, 20 + offset), color=(0, 0, 0), width=1)
    document.save(str(pdf_path))
    document.close()

    manifest = run_pdf(pdf_path, output_dir, scale_mm_per_px=1.0, dpi=72, preset="default")

    assert len(manifest["pages"]) == 2
    saved = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(saved["pages"]) == 2
    for page in saved["pages"]:
        ir_path = output_dir / page["primitive_ir"]
        assert ir_path.is_file()
        payload = json.loads(ir_path.read_text(encoding="utf-8"))
        assert payload["source_document"]["image_width_px"] == 200
        assert page["primitive_count"] == len(payload["primitives"])


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        test_run_pdf_creates_manifest_and_page_ir(Path(directory))
    print("1/1 test PASS")