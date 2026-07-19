"""
text_rereader.py — Text Re-reader (Phase 5, module #2): dùng Vision API (LLM)
để đọc lại text primitives có confidence thấp hoặc semantic_role chưa xác định.

BỐI CẢNH: Phase 1 (primitive_ir_lib) đã trích xuất text bằng Tesseract (tier 1)
hoặc Vision (tier 3). Tesseract thất bại nặng trên: ghi chú dài chữ nhỏ, số
kích thước xoay dọc, text trong ô bảng nhiễu (mục 9.2 tài liệu kiến trúc).
Vision đọc đúng gần như tuyệt đối trên các case này — nhưng confidence rule-based
có thể thấp (vd Tesseract trả confidence 0.15 cho ghi chú dài; hoặc text_extraction
gán semantic_role = "unknown" vì không khớp pattern nào).

Module này: quét tất cả text primitives, chọn những có confidence thấp hoặc
semantic_role = "unknown", crop vùng bbox_px từ ảnh gốc, gửi crop + prompt
tiếng Việt tới Vision API, và nếu LLM trả nội dung khác → tạo AgentAction
override text content + parsed_value + semantic_role.

KHÔNG tự apply vào Primitive gốc — trả AgentAction để caller quyết định (đúng
nguyên tắc "Agent chỉ khuyên").

Optional dependency: `anthropic` (Claude Vision API) — nếu chưa cài, module
bỏ qua toàn bộ với lý do rõ ràng, KHÔNG crash (giống pattern lazy-import
đã dùng cho vision_client.py, constraint_solving.py, builder.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from primitive_ir_lib.models import Primitive, SemanticRole

from .models import AgentAction, AgentReport, AgentTask, Evidence, new_id

# ngưỡng confidence mặc định: text có confidence dưới ngưỡng này sẽ được đẩy
# sang Vision để đọc lại. 0.5 = Tesseract confidence thấp (thường ~0.15-0.4
# cho case thất bại nặng), Vision thường trả 0.95 (mục 9.2).
_DEFAULT_CONFIDENCE_THRESHOLD = 0.5
_DEFAULT_MODEL = "claude-sonnet-4-6"

# prompt gửi LLM (tiếng Việt, yêu cầu đọc chính xác — giữ pattern vision_client.py)
_TEXT_REREAD_PROMPT = (
    "Đây là crop từ bản vẽ kỹ thuật cải tạo ô tô tải. "
    "Hãy đọc CHÍNH XÁC toàn bộ text/chữ số trong vùng crop này. "
    "CHỈ trả nội dung text đọc được, KHÔNG giải thích, KHÔNG thêm dấu câu thừa. "
    "Nếu crop trống hoặc không có text, trả dấu ngoặc kép rỗng: \"\"."
)

# regex phân loại semantic role (tái dùng từ text_extraction.py, không import
# trực tiếp để tránh phụ thuộc circular — copy pattern, đã thống nhất ở Phase 1)
_PURE_NUMBER_RE = re.compile(r"^\d{2,5}([.,]\d+)?$")
_DRAWING_CODE_RE = re.compile(r"^[A-Z]{1,4}[-_][A-Z0-9]+([-_/][A-Z0-9]+)*$")


def _classify_semantic_role(content: str) -> Tuple[SemanticRole, Optional[float]]:
    """Phân loại semantic_role cho text đã đọc lại (tái dùng logic
    text_extraction.classify_semantic_role)."""
    content = content.strip()
    if not content:
        return "unknown", None

    m = _PURE_NUMBER_RE.match(content)
    if m:
        parsed = float(content.replace(",", "."))
        return "dimension_value", parsed

    if _DRAWING_CODE_RE.match(content):
        return "drawing_code", None

    if len(content) > 25 or len(content.split()) >= 4:
        return "general_note", None

    return "unknown", None


def _safe_crop(
    image_bgr: np.ndarray,
    bbox_px: tuple,
    padding: int = 5,
) -> Optional[np.ndarray]:
    """Crop vùng bbox_px từ ảnh gốc với padding an toàn. Trả None nếu
    bbox nằm ngoài ảnh hoặc crop trống."""
    h, w = image_bgr.shape[:2]
    x0 = max(0, int(bbox_px[0]) - padding)
    y0 = max(0, int(bbox_px[1]) - padding)
    x1 = min(w, int(bbox_px[2]) + padding)
    y1 = min(h, int(bbox_px[3]) + padding)
    if x1 <= x0 or y1 <= y0:
        return None
    return image_bgr[y0:y1, x0:x1].copy()


@dataclass
class TextRereaderResult:
    """Kết quả 1 lần chạy text rereader."""
    actions: List[AgentAction] = field(default_factory=list)
    reread_count: int = 0
    skipped_count: int = 0
    unchanged_count: int = 0
    details: List[str] = field(default_factory=list)


def reread_low_confidence_texts(
    primitives: List[Primitive],
    image_bgr: np.ndarray,
    vision_reader: Optional[Callable[[np.ndarray, str], str]] = None,
    confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
    prompt: Optional[str] = None,
    report: Optional[AgentReport] = None,
) -> TextRereaderResult:
    """Quét text primitives, chọn những có confidence thấp hoặc
    semantic_role = "unknown", dùng Vision để đọc lại.

    `vision_reader`: callable nhận (numpy BGR crop, text prompt) → trả string.
    Nếu None → bỏ qua toàn bộ với lý do rõ ràng (giống pattern ezdxf/solvespace).

    `prompt`: custom prompt cho LLM. Nếu None → dùng _TEXT_REREAD_PROMPT.

    Trả `TextRereaderResult` chứa danh sách AgentAction — KHÔNG tự apply
    vào primitives gốc.
    """
    result = TextRereaderResult()
    effective_prompt = prompt or _TEXT_REREAD_PROMPT

    if vision_reader is None:
        result.skipped_count = -1  # sentinel: không có vision_reader, skip toàn bộ
        msg = "BỎ QUA: không có vision_reader (có thể anthropic chưa cài)"
        result.details.append(msg)
        if report is not None:
            report.add_skip(msg, "text-rereader-no-vision")
        return result

    # lọc text primitives cần đọc lại
    candidates: List[Primitive] = []
    for prim in primitives:
        if prim.type != "text":
            continue
        if prim.confidence < confidence_threshold or prim.text_data.semantic_role == "unknown":
            candidates.append(prim)

    if not candidates:
        result.details.append(
            f"Không có text primitive nào cần đọc lại "
            f"(confidence_threshold={confidence_threshold})"
        )
        return result

    result.details.append(
        f"tìm {len(candidates)} text primitive cần đọc lại "
        f"(confidence<{confidence_threshold} hoặc role=unknown)"
    )

    for prim in candidates:
        if prim.trace is None or prim.trace.bbox_px is None:
            result.skipped_count += 1
            msg = f"{prim.id}: bỏ qua — không có bbox_px trong trace"
            result.details.append(msg)
            continue

        crop = _safe_crop(image_bgr, prim.trace.bbox_px)
        if crop is None:
            result.skipped_count += 1
            msg = f"{prim.id}: bỏ qua — bbox_px ngoài ảnh gốc"
            result.details.append(msg)
            continue

        # gọi Vision API
        try:
            new_text = vision_reader(crop, effective_prompt)
        except Exception as exc:
            result.skipped_count += 1
            msg = f"{prim.id}: Vision API lỗi — {exc}"
            result.details.append(msg)
            continue

        result.reread_count += 1

        # so sánh kết quả mới với gốc
        old_content = prim.text_data.content if prim.text_data else ""
        new_text_stripped = new_text.strip()

        if not new_text_stripped or new_text_stripped == old_content:
            # Vision trả trống hoặc giống gốc → không cần thay đổi
            result.unchanged_count += 1
            result.details.append(
                f"{prim.id}: Vision trả '{new_text_stripped}' — "
                f"{'giống gốc' if new_text_stripped == old_content else 'trống'} -> không override"
            )
            if report is not None:
                report.add_task(AgentTask(
                    task_type="reread_text",
                    primitive_id=prim.id,
                    reason=f"confidence={prim.confidence} < {confidence_threshold}",
                ))
                report.add_action(AgentAction(
                    task_id="text-rereader-scan",
                    action_type="no_action",
                    confidence=prim.confidence,
                    notes=f"Vision trả '{new_text_stripped}' — không thay đổi",
                ))
            continue

        # có thay đổi → tạo AgentAction override
        new_role, new_parsed = _classify_semantic_role(new_text_stripped)

        action = AgentAction(
            task_id=f"reread-{prim.id}",
            action_type="override_text",
            confidence=0.95,  # Vision confidence gần tuyệt đối trên benchmark
            target_primitive_id=prim.id,
            new_text_content=new_text_stripped,
            new_parsed_value=new_parsed,
            new_semantic_role=new_role,
            notes=(
                f"override text {prim.id}: '{old_content}' -> '{new_text_stripped}' "
                f"(confidence gốc={prim.confidence}, role gốc={prim.text_data.semantic_role})"
            ),
        )
        result.actions.append(action)

        if report is not None:
            report.add_task(AgentTask(
                task_type="reread_text",
                primitive_id=prim.id,
                reason=f"confidence={prim.confidence} < {confidence_threshold}, "
                       f"role={prim.text_data.semantic_role}",
            ))
            report.add_action(action)

        result.details.append(
            f"{prim.id}: override '{old_content}' -> '{new_text_stripped}' "
            f"(role: {prim.text_data.semantic_role} -> {new_role})"
        )

    return result
