"""
demo_pipeline.py — Demo Phase 5 (Agent): chạy trên output Phase 1 + Phase 2,
sau đó chạy Phase 3 để chứng minh output tốt hơn sau agent.

Pipeline: Phase 1 → Phase 2 → **Phase 5 (Agent)** → Phase 3

Demo tạo 1 ảnh tổng hợp (giống primitive_ir_lib/demo_pipeline.py), chạy
toàn bộ pipeline thật (geometry extraction, text extraction, pattern
recognition, constraint detection → agent → DXF build + review). Không cần
API key hay package bên ngoài — Agent tự skip khi không có vision_reader,
Constraint Advisor vẫn chạy (rule-based).

Chạy (từ thư mục cad_agent):
    python -m agent_lib.demo_pipeline
"""

from __future__ import annotations

import os
import sys

import cv2
import numpy as np


def _configure_console_output() -> None:
    """Use UTF-8 when the Windows console defaults to a legacy code page."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# đảm bảo import được package khi chạy từ thư mục cha
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from primitive_ir_lib.assemble import build_document
from primitive_ir_lib.calibration import Calibration
from primitive_ir_lib.cross_validation import cross_validate
from primitive_ir_lib.demo_pipeline import (
    IMG_H, IMG_W, make_synthetic_drawing, TABLE_ROI,
)
from primitive_ir_lib.geometry_extraction import extract_raw_geometry
from primitive_ir_lib.models import CrossValidation
from primitive_ir_lib.table_extraction import extract_table_cells
from semantic_ir_lib.assemble import build_semantic_document
from semantic_ir_lib.constraint_pruning import prune_constraints


# ---- stub Vision reader (giả lập LLM response cho demo) ----

class _StubVisionReader:
    """Stub Vision reader cho demo: trả nội dung cố định dựa vào crop size.
    Giả lập hành vi: nếu crop nhỏ → trả số (dimension), nếu crop lớn → trả text dài."""

    def __init__(self):
        self.call_count = 0

    def __call__(self, crop_bgr, prompt=None):
        self.call_count += 1
        h, w = crop_bgr.shape[:2]
        area = h * w

        # Phân loại dựa trên prompt content
        if prompt and "part_type" in prompt.lower():
            return '{"part_type": "thanh_ngang", "confidence": 0.85}'

        if prompt and ("winner" in prompt.lower() or "conflict" in prompt.lower()):
            return '{"winner": "text", "value": 1700, "confidence": 0.9}'

        # mặc định: trả text dựa vào crop area
        if area < 5000:
            return "1700"  # số kích thước nhỏ
        elif area < 20000:
            return "TP-TL-A001/07/26"  # mã bản vẽ
        else:
            return "GHI CHU: Kiem tra toa do truoc khi cat"  # ghi chú dài


def _stub_cell_reader(image_bgr, bbox):
    """Stub reader cho tier-2 (giống verify_full.py)."""
    x0, y0, x1, y1 = bbox
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    col = min(2, int((cx - TABLE_ROI[0]) / (TABLE_ROI[2] - TABLE_ROI[0]) * 3))
    row = 0 if cy < (TABLE_ROI[1] + TABLE_ROI[3]) / 2 else 1
    expected = [["DAI", "RONG", "CAO"], ["4200", "1900", "2100"]]
    return expected[row][col]


def main() -> int:
    _configure_console_output()
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo_output")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("CAD Agent — Phase 5 Demo (Agent)")
    print("Pipeline: Phase 1 → Phase 2 → Phase 5 → Phase 3")
    print("=" * 60)

    # ================================================================
    # Phase 1: Geometry + Text Extraction
    # ================================================================
    print("\n--- Phase 1: Primitive IR ---")
    image = make_synthetic_drawing()

    raw_geom = extract_raw_geometry(image, hough_threshold=50, min_line_length=40, max_line_gap=5)
    print(f"[geometry] {len(raw_geom.lines)} line, {len(raw_geom.circles)} circle")

    # Tier 2 (table)
    cells, raw_texts = extract_table_cells(
        image, raw_geom.lines, TABLE_ROI, cell_reader=_stub_cell_reader,
    )
    print(f"[tier2] {len(cells)} ô, {len(raw_texts)} text")

    # Calibration
    from primitive_ir_lib.models import Calibration as Cal
    calibration = Cal(
        unit="mm", pixel_to_unit_scale=2.5,
        origin_px=(0.0, float(IMG_H)),
        method="manual_override",
        reference_note="demo: giả định scale=2.5mm/px",
    )

    # Cross-validate
    cvs = cross_validate(raw_texts, raw_geom.lines, calibration, threshold_percent=3.0)
    print(f"[cross-validate] {len(cvs)} so khớp")

    # Tạo 1 conflict giả để demo Phase 5 conflict resolver
    if cvs:
        conflict_cv = CrossValidation(
            text_primitive_id=cvs[0].text_primitive_id,
            geometry_primitive_id=cvs[0].geometry_primitive_id,
            status="conflict",
            text_value=cvs[0].text_value,
            geometry_measured_length=cvs[0].geometry_measured_length * 1.15,  # làm lệch 15%
            delta_percent=15.0,
            match_threshold_percent=3.0,
        )
        cvs.append(conflict_cv)
        print(f"[demo] thêm 1 cross-validation conflict giả (delta=15%)")

    # Assemble
    doc = build_document(
        file_name="demo_phase5.png", page_index=0,
        image_width_px=IMG_W, image_height_px=IMG_H,
        calibration=calibration, raw_lines=raw_geom.lines,
        raw_circles=raw_geom.circles, raw_texts=raw_texts,
    )
    doc.cross_validations = cvs
    print(f"[assemble] {len(doc.primitives)} primitives")

    # Giảm confidence 1 text primitive để demo rereader
    for prim in doc.primitives:
        if prim.type == "text" and prim.text_data:
            if prim.text_data.semantic_role == "general_note":
                prim.confidence = 0.3  # giảm xuống dưới ngưỡng
                print(f"[demo] giảm confidence text '{prim.text_data.content[:30]}...' -> 0.3")

    # ================================================================
    # Phase 2: Pattern Recognition + Constraint Detection
    # ================================================================
    print("\n--- Phase 2: Semantic IR ---")
    semantic_doc = build_semantic_document(
        doc, primitive_ir_file_name="demo_phase5.png",
    )
    print(f"[pattern-recognition] {len(semantic_doc.parts)} parts")
    print(f"[constraint-detection] {len(semantic_doc.constraints)} constraints")

    pruned = prune_constraints(semantic_doc.constraints)
    print(f"[constraint-pruning] {len(semantic_doc.constraints)} -> {len(pruned.kept)} constraints")

    # Thử solve
    solve_result = None
    try:
        from semantic_ir_lib.constraint_solving import solve_constraints
        solve_result = solve_constraints(doc, pruned.kept)
        print(f"[constraint-solving] status={solve_result.status}")
    except ImportError:
        print("[constraint-solving] BỎ QUA — python-solvespace chưa cài")

    # Giảm confidence 1 part để demo classifier
    if semantic_doc.parts:
        p = semantic_doc.parts[0]
        old_conf = p.confidence
        p.confidence = 0.55  # giảm xuống dưới ngưỡng 0.7
        print(f"[demo] giảm confidence part {p.part_type} ({p.id}): {old_conf} -> 0.55")

    # ================================================================
    # Phase 5: Agent
    # ================================================================
    print("\n--- Phase 5: Agent ---")
    from agent_lib.batch_agent import run_agent, apply_agent_report

    stub_reader = _StubVisionReader()
    report = run_agent(
        primitive_doc=doc,
        semantic_doc=semantic_doc,
        image_bgr=image,
        solve_result=solve_result,
        vision_reader=stub_reader,
        text_confidence_threshold=0.5,
        part_confidence_threshold=0.7,
    )

    print(f"[agent] tasks={report.task_count}, actions={report.action_count}, "
          f"skipped={report.skipped_count}")
    for action in report.actions:
        print(f"    - {action.action_type}: {action.notes[:80] if action.notes else ''}")
    for reason in report.skip_reasons.values():
        print(f"    - SKIP: {reason}")

    # Apply agent actions
    if report.action_count > 0:
        summary = apply_agent_report(
            doc, semantic_doc,
            doc.cross_validations, semantic_doc.constraints,
            report,
        )
        print(f"[agent-apply] {summary}")

    # Lưu agent report
    from .io_utils import save_document
    report_path = os.path.join(output_dir, "agent_report.json")
    save_document(report, report_path)
    print(f"[save] agent report -> {report_path}")

    # ================================================================
    # Phase 3: DXF Builder + Reviewer (có hoặc không có ezdxf)
    # ================================================================
    print("\n--- Phase 3: DXF Builder ---")
    try:
        from dxf_builder_lib.builder import build_dxf
        from dxf_builder_lib.reviewer import review_dxf

        out_path = os.path.join(output_dir, "cad_agent_phase5_demo.dxf")
        build_result = build_dxf(
            doc, out_path,
            semantic_doc=semantic_doc,
            solved_primitives=solve_result.solved_primitives if solve_result and solve_result.status == "okay" else {},
            build_components=True,
        )
        print(f"[dxf-builder] {build_result.entity_count} entity -> {out_path}")
        print(f"[semantic-components] {build_result.component_count} linh kiện")

        review_result = review_dxf(build_result)
        if review_result.passed:
            print(f"[reviewer#1] OK — {review_result.checked_count} entity khớp tuyệt đối")
        else:
            print(f"[reviewer#1] LỖI ({len(review_result.mismatches)}):")
            for m in review_result.mismatches[:5]:
                print(f"  - {m}")

    except ImportError as exc:
        print(f"[dxf-builder] BỎ QUA — {exc}")

    print("\n" + "=" * 60)
    print(">>> DEMO PHASE 5 COMPLETE")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
