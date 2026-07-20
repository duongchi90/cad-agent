"""Regression tests for the reusable scanned-PDF benchmark CLI."""

from __future__ import annotations

import tempfile
from pathlib import Path

import fitz

from primitive_ir_lib.benchmark_pdf import benchmark_pdf


def test_benchmark_pdf_renders_page_and_writes_geometry_stats():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pdf_path = root / "fixture.pdf"
        output_dir = root / "benchmark"
        document = fitz.open()
        page = document.new_page(width=300, height=200)
        page.draw_line((20, 40), (280, 40), color=(0, 0, 0), width=1)
        page.insert_text((30, 100), "1700", fontsize=14)
        document.save(str(pdf_path))
        document.close()

        report = benchmark_pdf("fixture", pdf_path, output_dir, dpi=144, preset="default")

        assert report["source_file"] == "fixture.pdf"
        assert len(report["pages"]) == 1
        page_report = report["pages"][0]
        assert page_report["image_width_px"] == 600
        assert page_report["image_height_px"] == 400
        assert page_report["native_text_chars"] == 4
        assert page_report["raw_line_count"] >= 1
        assert (output_dir / page_report["rendered_png"]).is_file()


if __name__ == "__main__":
    test_benchmark_pdf_renders_page_and_writes_geometry_stats()
    print("1/1 test PASS")
