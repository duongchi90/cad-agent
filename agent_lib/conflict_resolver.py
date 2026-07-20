"""
conflict_resolver.py — Cross-validation Conflict Resolver (Phase 5, module #3):
dùng Vision API (LLM) để xử lý cross_validations có status = "conflict".

BỐI CẢNH: Phase 1 (primitive_ir_lib/cross_validation.py) đối chiếu text value
(đọc bởi Vision/Tesseract) với geometry measured length (đo bởi OpenCV).
Khi chênh lệch vượt ngưỡng (mặc định 3%), status = "conflict". Nguyên tắc
mục 7 tài liệu kiến trúc: "status = conflict không được tự động chọn nguồn nào
thắng — phải đẩy sang Reviewer".

Module này thực thi nguyên tắc đó bằng cách: crop vùng chứa cả text VÀ
geometry (merged bbox mở rộng) → gửi tới Vision API kèm prompt mô tả xung đột
(text đọc được = X, geometry đo được = Y) → LLM đọc lại bản vẽ và quyết định:
  1. text đúng → giữ nguyên text, bỏ geometry
  2. geometry đúng → giữ nguyên geometry, bỏ text
  3. giá trị mới → LLM đề xuất 1 giá trị khác (vd text bị OCR nhầm 1 chữ số)

Tùy kết quả, tạo AgentAction phù hợp. KHÔNG tự apply — caller quyết định.

THIẾT KẾ QUAN TRỌNG:
- Vision KHÔNG đo toạ độ/chiều dài (đó là việc của OpenCV) — Vision chỉ ĐỌC
  LẠI text/ký số in sẵn trên bản vẽ (mục 7 tài liệu kiến trúc đã phân biệt rõ)
- Module gửi 2 giá trị cho LLM, hỏi "bản vẽ ghi giá trị nào" — đây là đọc
  text, không phải đo hình học, nên nằm trong khả năng của Vision (đã benchmark
  chính xác gần 100% ở mục 9.2)
- Nếu LLM chọn giá trị mới → tạo text primitive mới hoặc update parsed_value

Optional dependency: `anthropic` — nếu chưa cài, skip toàn bộ với lý do rõ ràng.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np

from primitive_ir_lib.models import CrossValidation, Primitive, PrimitiveIRDocument

from .models import (
    AgentAction, AgentReport, AgentTask, Evidence,
)

# prompt gửi LLM khi có conflict (tiếng Việt)
_CONFLICT_RESOLVE_PROMPT_TEMPLATE = (
    "Đây là crop từ bản vẽ kỹ thuật. Có 1 kích thước/biểu thị bị xung đột:\n"
    " - Giá trị đọc bởi OCR/Vision (text): {text_value} {text_unit}\n"
    " - Giá trị đo bằng hình học (OpenCV): {geometry_value} {geometry_unit}\n"
    "Chênh lệch: {delta_percent:.1f}%\n\n"
    "Hãy nhìn crop và xác nhận giá trị ĐÚNG trên bản vẽ.\n"
    "Trả ĐÚNG 1 dòng JSON: "
    "{{\"winner\": \"text\" | \"geometry\" | \"new_value\", \"value\": <số>, "
    "\"confidence\": 0.9}}\n"
    "- winner=\"text\": text value đúng, geometry đo sai\n"
    "- winner=\"geometry\": geometry đo đúng, text đọc sai\n"
    "- winner=\"new_value\": cả hai đều sai, value là giá trị đúng bạn đọc được\n"
    "confidence là độ tin cậy (0.0-1.0). KHÔNG thêm text khác."
)

# regex parse JSON response
_JSON_RE = re.compile(r"\{[^}]+\}")


def _safe_crop(
    image_bgr: np.ndarray,
    bbox_px: tuple,
    padding: int = 20,
) -> Optional[np.ndarray]:
    """Crop vùng bbox_px với padding."""
    h, w = image_bgr.shape[:2]
    x0 = max(0, int(bbox_px[0]) - padding)
    y0 = max(0, int(bbox_px[1]) - padding)
    x1 = min(w, int(bbox_px[2]) + padding)
    y1 = min(h, int(bbox_px[3]) + padding)
    if x1 <= x0 or y1 <= y0:
        return None
    return image_bgr[y0:y1, x0:x1].copy()


def _merge_bboxes(bboxes: List[tuple], padding: int = 30) -> Optional[tuple]:
    """Gộp nhiều bbox thành 1 bounding box lớn + padding."""
    if not bboxes:
        return None
    x0 = min(b[0] for b in bboxes) - padding
    y0 = min(b[1] for b in bboxes) - padding
    x1 = max(b[2] for b in bboxes) + padding
    y1 = max(b[3] for b in bboxes) + padding
    return (max(0, x0), max(0, y0), x1, y1)


def _primitive_by_id(primitive_doc: PrimitiveIRDocument, pid: str) -> Optional[Primitive]:
    """Tra primitive theo id trong PrimitiveIRDocument."""
    for p in primitive_doc.primitives:
        if p.id == pid:
            return p
    return None


def _parse_conflict_response(response_text: str) -> Optional[dict]:
    """Parse JSON response từ LLM cho conflict resolution."""
    response_text = response_text.strip()
    match = _JSON_RE.search(response_text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        winner = data.get("winner", "")
        value = data.get("value")
        conf = float(data.get("confidence", 0.0))
        if winner in ("text", "geometry", "new_value") and 0.0 <= conf <= 1.0:
            return {"winner": winner, "value": value, "confidence": conf}
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    return None


@dataclass
class ConflictResolverResult:
    """Kết quả 1 lần chạy conflict resolver."""
    actions: List[AgentAction] = field(default_factory=list)
    resolved_count: int = 0
    skipped_count: int = 0
    rejected_count: int = 0
    details: List[str] = field(default_factory=list)


def resolve_conflicts(
    primitive_doc: PrimitiveIRDocument,
    cross_validations: List[CrossValidation],
    image_bgr: np.ndarray,
    vision_reader: Optional[Callable[[np.ndarray, str], str]] = None,
    report: Optional[AgentReport] = None,
) -> ConflictResolverResult:
    """Quét cross_validations có status = "conflict", crop vùng chứa cả text
    VÀ geometry, gửi tới Vision API để quyết định giá trị đúng.

    `vision_reader`: callable nhận (numpy BGR crop, text prompt) → trả string.
    Nếu None → bỏ qua toàn bộ.

    Trả `ConflictResolverResult` chứa danh sách AgentAction — KHÔNG tự apply.
    """
    result = ConflictResolverResult()

    if vision_reader is None:
        result.skipped_count = -1
        msg = "BỎ QUA: không có vision_reader (có thể anthropic chưa cài)"
        result.details.append(msg)
        if report is not None:
            report.add_skip(msg, "conflict-resolver-no-vision")
        return result

    # lọc conflicts
    conflicts = [cv for cv in cross_validations if cv.status == "conflict"]
    if not conflicts:
        result.details.append("Không có cross-validation nào ở trạng thái conflict")
        return result

    result.details.append(f"tìm {len(conflicts)} cross-validation conflict")

    # build index primitive by id
    prim_index: Dict[str, Primitive] = {}
    for p in primitive_doc.primitives:
        prim_index[p.id] = p

    for cv in conflicts:
        text_prim = prim_index.get(cv.text_primitive_id)
        geo_prim = prim_index.get(cv.geometry_primitive_id)

        if text_prim is None or geo_prim is None:
            result.skipped_count += 1
            msg = (
                f"{cv.id}: bỏ qua — không tìm thấy primitive "
                f"(text={cv.text_primitive_id}, geo={cv.geometry_primitive_id})"
            )
            result.details.append(msg)
            continue

        # gộp bbox của text + geometry
        bboxes = []
        if text_prim.trace and text_prim.trace.bbox_px:
            bboxes.append(text_prim.trace.bbox_px)
        if geo_prim.trace and geo_prim.trace.bbox_px:
            bboxes.append(geo_prim.trace.bbox_px)

        if not bboxes:
            result.skipped_count += 1
            msg = f"{cv.id}: bỏ qua — không có bbox_px"
            result.details.append(msg)
            continue

        merged = _merge_bboxes(bboxes)
        crop = _safe_crop(image_bgr, merged, padding=0)
        if crop is None:
            result.skipped_count += 1
            msg = f"{cv.id}: bỏ qua — merged bbox ngoài ảnh gốc"
            result.details.append(msg)
            continue

        # xây prompt cho conflict này
        text_val = cv.text_value if cv.text_value is not None else "?"
        geo_val = cv.geometry_measured_length if cv.geometry_measured_length is not None else "?"
        unit = getattr(primitive_doc.calibration, "unit", "mm") if hasattr(primitive_doc, "calibration") else "mm"
        delta = cv.delta_percent if cv.delta_percent is not None else 0.0

        prompt = _CONFLICT_RESOLVE_PROMPT_TEMPLATE.format(
            text_value=text_val,
            geometry_value=geo_val,
            text_unit=unit,
            geometry_unit=unit,
            delta_percent=delta,
        )

        # gọi Vision API
        try:
            response = vision_reader(crop, prompt)
        except Exception as exc:
            result.skipped_count += 1
            msg = f"{cv.id}: Vision API lỗi — {exc}"
            result.details.append(msg)
            continue

        # parse response
        parsed = _parse_conflict_response(response)
        if parsed is None:
            result.rejected_count += 1
            msg = (
                f"{cv.id}: LLM trả response không hợp lệ — '{response[:100]}' "
                f"-> KHÔNG resolve (giữ nguyên status=conflict)"
            )
            result.details.append(msg)
            if report is not None:
                report.add_task(AgentTask(
                    task_type="resolve_conflict",
                    primitive_id=cv.text_primitive_id,
                    cross_validation_id=cv.id,
                    reason=f"conflict: text={text_val} vs geometry={geo_val} (delta={delta:.1f}%)",
                ))
                report.add_action(AgentAction(
                    task_id=f"resolve-{cv.id}",
                    action_type="no_action",
                    confidence=0.0,
                    notes=f"LLM response không hợp lệ: '{response[:100]}'",
                    evidence=Evidence(prompt=prompt[:200], response=response[:200]),
                ))
            continue

        winner = parsed["winner"]
        new_value = parsed["value"]
        llm_conf = parsed["confidence"]

        # tạo AgentAction phù hợp với winner
        action = AgentAction(
            task_id=f"resolve-{cv.id}",
            action_type="pick_conflict_winner",
            confidence=llm_conf,
            target_cross_validation_id=cv.id,
            target_primitive_id=cv.text_primitive_id,
            conflict_winner=winner,
            notes=(
                f"resolve conflict {cv.id}: winner={winner} "
                f"(text={text_val}, geometry={geo_val}, delta={delta:.1f}%, "
                f"LLM conf={llm_conf})"
            ),
            evidence=Evidence(
                prompt=prompt[:200],
                response=response[:200],
            ),
        )

        if winner == "new_value" and new_value is not None:
            try:
                action.conflict_new_value = float(new_value)
            except (ValueError, TypeError):
                action.conflict_winner = "text"  # fallback: giữ text gốc
                action.notes += " (fallback: không parse được new_value -> giữ text)"

        result.resolved_count += 1
        result.actions.append(action)

        if report is not None:
            report.add_task(AgentTask(
                task_type="resolve_conflict",
                primitive_id=cv.text_primitive_id,
                cross_validation_id=cv.id,
                reason=f"conflict: text={text_val} vs geometry={geo_val} (delta={delta:.1f}%)",
            ))
            report.add_action(action)

        result.details.append(
            f"{cv.id}: resolved winner={winner} "
            f"(text={text_val}, geo={geo_val}, LLM conf={llm_conf})"
        )

    return result
