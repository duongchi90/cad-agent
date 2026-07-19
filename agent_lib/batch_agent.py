"""
batch_agent.py — Entry point Phase 5: nhận PrimitiveIRDocument + SemanticIRDocument
+ ảnh gốc, chạy 4 module Agent theo thứ tự, trả AgentReport tổng hợp.

THỨ TỰ CHẠY (có ý, không thay đổi tùy ý):
  1. Text Re-reader: đọc lại text confidence thấp → phải đúng TRƯỚC khi
     re-classify part (vì part_type có thể phụ thuộc vào text semantic_role,
     vd "dimension_value" vs "general_note")
  2. Part Re-classifier: phân loại lại part confidence thấp bằng Vision
  3. Conflict Resolver: xử lý cross-validation conflicts (cần text ĐÃ đúng
     từ bước 1)
  4. Constraint Advisor: drop constraint nếu solver fail (cần constraints ĐÃ
     clean từ bước 2/3 — part_type có thể ảnh hưởng đến việc giữ/bỏ constraint
     liên quan đến part đó)

THIẾT KẾ:
- `vision_reader`: callable nhận (numpy BGR crop, text prompt) → string response.
  Nếu None → module 1/2/3 skip, module 4 (advisor) vẫn chạy (rule-based).
- Mặc định tất cả module đều skip nếu input không đủ (không có image, không có
  vision_reader, không có conflicts, solver đã converge).
- Trả AgentReport đầy đủ để caller log/audit/apply từng action.
- KHÔNG tự apply action vào Primitive/Semantic IR — caller đọc report rồi quyết
  định apply từng action (đúng nguyên tắc "Agent chỉ khuyên", mục 7 tài liệu
  kiến trúc).

Optional dependencies: `anthropic` (module 1/2/3), `python-solvespace` (module 4
  re-solve verification) — cùng chiến lược lazy-import/graceful-skip đã dùng
  xuyên suốt Phase 1–4.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

import numpy as np

from primitive_ir_lib.models import PrimitiveIRDocument
from semantic_ir_lib.models import SemanticIRDocument

from .advisor import advise_drop_constraints
from .conflict_resolver import resolve_conflicts
from .models import AgentReport
from .part_classifier import reclassify_low_confidence_parts
from .text_rereader import reread_low_confidence_texts

# ngưỡng mặc định cho cả 2 module dùng confidence threshold
_DEFAULT_TEXT_CONFIDENCE_THRESHOLD = 0.5
_DEFAULT_PART_CONFIDENCE_THRESHOLD = 0.7


def _build_prim_index(primitive_doc: PrimitiveIRDocument) -> Dict[str, object]:
    """Index primitive by id cho lookup nhanh."""
    return {p.id: p for p in primitive_doc.primitives}


def run_agent(
    primitive_doc: PrimitiveIRDocument,
    semantic_doc: SemanticIRDocument,
    image_bgr: Optional[np.ndarray] = None,
    solve_result: Optional[object] = None,
    vision_reader: Optional[Callable] = None,
    text_confidence_threshold: float = _DEFAULT_TEXT_CONFIDENCE_THRESHOLD,
    part_confidence_threshold: float = _DEFAULT_PART_CONFIDENCE_THRESHOLD,
) -> AgentReport:
    """Entry point Phase 5: chạy 4 module Agent trên PrimitiveIRDocument +
    SemanticIRDocument.

    Parameters:
        primitive_doc: PrimitiveIRDocument (đầu ra Phase 1).
        semantic_doc: SemanticIRDocument (đầu ra Phase 2).
        image_bgr: ảnh gốc (numpy BGR). Nếu None → module 1/2/3 skip.
        solve_result: kết quả constraint_solving.solve_constraints().
            Nếu None hoặc status="okay" → module 4 skip.
        vision_reader: callable (crop_bgr, prompt_text) → str.
            Nếu None → module 1/2/3 skip (module 4 vẫn chạy).
        text_confidence_threshold: ngưỡng confidence để đẩy text sang rereader.
        part_confidence_threshold: ngưỡng confidence để đẩy part sang classifier.

    Returns:
        AgentReport chứa tất cả tasks + actions từ 4 module.
    """
    report = AgentReport()
    details: List[str] = []

    # ================================================================
    # 1. Text Re-reader
    # ================================================================
    if image_bgr is not None:
        text_result = reread_low_confidence_texts(
            primitive_doc.primitives,
            image_bgr,
            vision_reader=vision_reader,
            confidence_threshold=text_confidence_threshold,
            report=report,
        )
        details.append(
            f"[text-rereader] reread={text_result.reread_count} "
            f"skipped={text_result.skipped_count} "
            f"unchanged={text_result.unchanged_count} "
            f"actions={len(text_result.actions)}"
        )
        for d in text_result.details:
            details.append(f"  {d}")
    else:
        details.append("[text-rereader] BỎ QUA: không có image_bgr")
        report.add_skip("không có image_bgr", "text-rereader-no-image")

    # ================================================================
    # 2. Part Re-classifier
    # ================================================================
    if image_bgr is not None:
        prim_index = _build_prim_index(primitive_doc)
        part_result = reclassify_low_confidence_parts(
            semantic_doc.parts,
            prim_index,
            image_bgr,
            vision_reader=vision_reader,
            confidence_threshold=part_confidence_threshold,
            report=report,
        )
        details.append(
            f"[part-classifier] classified={part_result.classified_count} "
            f"skipped={part_result.skipped_count} "
            f"rejected={part_result.rejected_count} "
            f"unchanged={part_result.unchanged_count} "
            f"actions={len(part_result.actions)}"
        )
        for d in part_result.details:
            details.append(f"  {d}")
    else:
        details.append("[part-classifier] BỎ QUA: không có image_bgr")
        report.add_skip("không có image_bgr", "part-classifier-no-image")

    # ================================================================
    # 3. Conflict Resolver
    # ================================================================
    if image_bgr is not None and primitive_doc.cross_validations:
        conflict_result = resolve_conflicts(
            primitive_doc,
            primitive_doc.cross_validations,
            image_bgr,
            vision_reader=vision_reader,
            report=report,
        )
        details.append(
            f"[conflict-resolver] resolved={conflict_result.resolved_count} "
            f"skipped={conflict_result.skipped_count} "
            f"rejected={conflict_result.rejected_count} "
            f"actions={len(conflict_result.actions)}"
        )
        for d in conflict_result.details:
            details.append(f"  {d}")
    else:
        if image_bgr is None:
            details.append("[conflict-resolver] BỎ QUA: không có image_bgr")
            report.add_skip("không có image_bgr", "conflict-resolver-no-image")
        else:
            details.append("[conflict-resolver] không có cross-validation nào")

    # ================================================================
    # 4. Constraint Advisor (rule-based, không cần Vision)
    # ================================================================
    advisor_result = advise_drop_constraints(
        semantic_doc.constraints,
        solve_result=solve_result,
        primitive_doc=primitive_doc,
        report=report,
    )
    details.append(
        f"[constraint-advisor] actions={len(advisor_result.actions)} "
        f"dropped={len(advisor_result.dropped_constraint_ids)} "
        f"iterations={advisor_result.iteration_count} "
        f"status={advisor_result.final_status}"
    )
    for d in advisor_result.details:
        details.append(f"  {d}")

    return report


def apply_agent_report(
    primitive_doc: PrimitiveIRDocument,
    semantic_doc: SemanticIRDocument,
    cross_validations: List[object],
    constraints: List[object],
    report: AgentReport,
) -> dict:
    """Áp dụng tất cả actions trong AgentReport vào Primitive/Semantic IR.

    Dùng `target_primitive_id`/`target_part_id`/`target_cross_validation_id`
    đã được copy trực tiếp vào action (không phụ thuộc matching `task_id` qua
    report.tasks — vì mỗi module gán task_id theo id nội bộ riêng, dễ bị lệch).

    Mỗi action được apply an toàn: chỉ thay đổi field liên quan, không đập
    lại toàn bộ object. Caller có thể chọn apply từng action riêng (đọc
    report.actions rồi apply manually) thay vì dùng hàm này.

    Returns dict tóm tắt: {"text_overridden": N, "parts_reclassified": N,
    "conflicts_resolved": N, "constraints_dropped": N}
    """
    from .advisor import apply_advisor_actions

    summary = {
        "text_overridden": 0,
        "parts_reclassified": 0,
        "conflicts_resolved": 0,
        "constraints_dropped": 0,
    }

    # build index
    prim_index = {p.id: p for p in primitive_doc.primitives}
    part_index = {p.id: p for p in semantic_doc.parts}
    cv_index = {cv.id: cv for cv in cross_validations}

    for action in report.actions:
        if action.applied:
            continue  # đã apply trước đó

        # --- override text ---
        if action.action_type == "override_text":
            pid = action.target_primitive_id
            prim = prim_index.get(pid) if pid else None
            if prim is not None and prim.text_data is not None:
                if action.new_text_content is not None:
                    prim.text_data.content = action.new_text_content
                if action.new_parsed_value is not None:
                    prim.text_data.parsed_value = action.new_parsed_value
                if action.new_semantic_role is not None:
                    prim.text_data.semantic_role = action.new_semantic_role  # type: ignore
                prim.confidence = max(prim.confidence, action.confidence)
                action.applied = True
                summary["text_overridden"] += 1

        # --- override part_type ---
        elif action.action_type == "override_part_type":
            part_id = action.target_part_id
            part = part_index.get(part_id) if part_id else None
            if part is not None and action.new_part_type is not None:
                part.part_type = action.new_part_type  # type: ignore
                part.confidence = action.confidence
                part.source = "vision_assisted"  # type: ignore
                action.applied = True
                summary["parts_reclassified"] += 1

        # --- resolve conflict ---
        elif action.action_type == "pick_conflict_winner":
            cv_id = action.target_cross_validation_id
            cv = cv_index.get(cv_id) if cv_id else None
            if cv is not None:
                if action.conflict_winner == "text":
                    cv.status = "confirmed"
                elif action.conflict_winner == "geometry":
                    cv.status = "confirmed"
                elif action.conflict_winner == "new_value" and action.conflict_new_value is not None:
                    cv.text_value = action.conflict_new_value
                    cv.status = "confirmed"
                action.applied = True
                summary["conflicts_resolved"] += 1

        # --- drop constraint ---
        elif action.action_type == "drop_constraint":
            # drop xử lý riêng bên dưới (list operation), chỉ mark applied
            if not action.applied:
                action.applied = True

    # drop constraints (tách riêng vì cần list operation)
    drop_ids = {
        action.dropped_constraint_id
        for action in report.actions
        if action.action_type == "drop_constraint" and action.dropped_constraint_id
    }
    if drop_ids:
        kept = apply_advisor_actions(constraints, report.actions)
        constraints[:] = kept  # modify in-place
        summary["constraints_dropped"] = len(drop_ids)

    return summary
