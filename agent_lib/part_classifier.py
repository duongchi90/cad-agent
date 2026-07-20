"""
part_classifier.py — Part Re-classifier (Phase 5, module #1): dùng Vision API
(LLM) để re-classify `part_type` cho SemanticPart có confidence thấp.

BỐI CẢNH: Phase 2 (semantic_ir_lib/pattern_recognition.py) phân loại part_type
dựa trên rule hình học thuần (góc line so với trục X, bán kính circle). Rule
hoạt động tốt cho case rõ ràng (line gần 0°/90° → thanh_ngang/thanh_doc) nhưng
gần biên (góc ~10° sát ngưỡng, hoặc circle bán kính gần 15mm sát biên
lo_bat_vit/duong_vien_tron) thì confidence thấp (~0.5) và classification có
thể sai. Module này gửi crop vùng bounding box của part tới Vision API, kèm
prompt mô tả các part_type có thể, để LLM chọn đúng loại linh kiện.

Schema semantic_ir.schema.json đã có chỗ cho `source: "vision_assisted"` (mục
11.1 tài liệu kiến trúc) — module này là bước điền đúng field đó: khi LLM
chọn part_type mới, cập nhật `source = "vision_assisted"` thay vì
`source = "rule_geometry"`.

THIẾT KẾ QUAN TRỌNG:
- LLM phản hồi JSON: {"part_type": "thanh_ngang", "confidence": 0.9}
- Nếu LLM trả part_type KHÔNG trong enum PartType → log warning, KHÔNG apply
  (đúng nguyên tắc "không đoán bừa", mục 7 tài liệu kiến trúc)
- Agent chỉ khuyên, caller quyết định apply (giống mọi module Phase 5)

Optional dependency: `anthropic` — nếu chưa cài, skip toàn bộ với lý do rõ ràng.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

import numpy as np

from semantic_ir_lib.models import SemanticPart

from .models import AgentAction, AgentReport, AgentTask, Evidence

# ngưỡng confidence mặc định: part có confidence dưới ngưỡng này sẽ được đẩy
# sang Vision để phân loại lại. 0.7 = giữa range [0.5, 1.0] — part có confidence
# < 0.7 thường nằm sát ngưỡng angle_tolerance hoặc radius threshold.
_DEFAULT_CONFIDENCE_THRESHOLD = 0.7
_DEFAULT_MODEL = "claude-sonnet-4-6"

# tập hợp part_type hợp lệ (từ semantic_ir_lib/models.py PartType)
_VALID_PART_TYPES: Set[str] = {
    "thanh_ngang", "thanh_doc", "thanh_xien",
    "lo_bat_vit", "duong_vien_tron",
    "khung_chu_nhat", "gia_do", "ban_le", "diem_noi",
    "unclassified",
}

# prompt gửi LLM (tiếng Việt, mô tả domain + yêu cầu phân loại)
_PART_CLASSIFY_PROMPT = (
    "Đây là crop từ bản vẽ kỹ thuật cải tạo ô tô tải (THACO). "
    "Phân loại thành phần cơ khí trong vùng crop này thành 1 trong các loại:\n"
    " - thanh_ngang: thanh dầm ngang (gần 0° hoặc 180° so với trục X)\n"
    " - thanh_doc: thanh dầm dọc (gần 90° so với trục X)\n"
    " - thanh_xien: thanh dầm xiên (góc khác 0°/90°)\n"
    " - lo_bat_vit: lỗ bắt vít (circle nhỏ, bán kính ≤ 15mm)\n"
    " - duong_vien_tron: đường viền tròn lớn (bán kính > 15mm)\n"
    " - khung_chu_nhat: khung chữ nhật kín (4 line tạo hình chữ nhật)\n"
    " - gia_do: giá đỡ góc L (2 thanh vuông góc nối tại 1 đầu)\n"
    " - ban_le: bản lề (2 thanh song song, có lỗ bắt vít ở đầu)\n"
    " - diem_noi: điểm nối/hàn (nhiều thanh hội tụ tại 1 điểm)\n"
    " - unclassified: không xác định được\n\n"
    "Trả ĐÚNG 1 dòng JSON: {\"part_type\": \"tên_loại\", \"confidence\": 0.9}\n"
    "confidence là độ tin cậy của bạn (0.0-1.0). KHÔNG thêm text khác."
)


def _safe_crop(
    image_bgr: np.ndarray,
    bbox_px: tuple,
    padding: int = 10,
) -> Optional[np.ndarray]:
    """Crop vùng bbox_px từ ảnh gốc với padding an toàn."""
    h, w = image_bgr.shape[:2]
    x0 = max(0, int(bbox_px[0]) - padding)
    y0 = max(0, int(bbox_px[1]) - padding)
    x1 = min(w, int(bbox_px[2]) + padding)
    y1 = min(h, int(bbox_px[3]) + padding)
    if x1 <= x0 or y1 <= y0:
        return None
    return image_bgr[y0:y1, x0:x1].copy()


def _merged_bbox(bboxes: List[tuple], padding: int = 15) -> Optional[tuple]:
    """Gộp nhiều bbox_px thành 1 bounding box lớn + padding."""
    if not bboxes:
        return None
    x0 = min(b[0] for b in bboxes) - padding
    y0 = min(b[1] for b in bboxes) - padding
    x1 = max(b[2] for b in bboxes) + padding
    y1 = max(b[3] for b in bboxes) + padding
    # clamp negative
    x0 = max(0, x0)
    y0 = max(0, y0)
    return (x0, y0, x1, y1)


def _parse_llm_response(response_text: str) -> Optional[Tuple[str, float]]:
    """Parse JSON response từ LLM. Trả (part_type, confidence) hoặc None
    nếu response không parse được hoặc part_type không hợp lệ."""
    response_text = response_text.strip()

    # thử tìm JSON trong response (LLM có thể thêm text xung quanh)
    json_match = re.search(r"\{[^}]+\}", response_text)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            pt = data.get("part_type", "")
            conf = float(data.get("confidence", 0.0))
            if pt in _VALID_PART_TYPES and 0.0 <= conf <= 1.0:
                return pt, conf
            else:
                return None  # part_type không hợp lệ
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    return None


@dataclass
class PartClassifierResult:
    """Kết quả 1 lần chạy part classifier."""
    actions: List[AgentAction] = field(default_factory=list)
    classified_count: int = 0
    skipped_count: int = 0
    rejected_count: int = 0    # LLM trả part_type không hợp lệ
    unchanged_count: int = 0
    details: List[str] = field(default_factory=list)


def reclassify_low_confidence_parts(
    parts: List[SemanticPart],
    primitives_by_id: Dict[str, object],
    image_bgr: np.ndarray,
    vision_reader: Optional[Callable[[np.ndarray, str], str]] = None,
    confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
    prompt: Optional[str] = None,
    report: Optional[AgentReport] = None,
) -> PartClassifierResult:
    """Quét SemanticParts, chọn những có confidence < threshold, crop vùng
    bounding box của tất cả primitive trong part, gửi tới Vision API để phân
    loại lại.

    `vision_reader`: callable nhận (numpy BGR crop, text prompt) → trả string
    response. Nếu None → bỏ qua toàn bộ.

    `prompt`: custom prompt cho LLM. Nếu None → dùng _PART_CLASSIFY_PROMPT.

    Trả `PartClassifierResult` chứa danh sách AgentAction — KHÔNG tự apply.
    """
    result = PartClassifierResult()
    effective_prompt = prompt or _PART_CLASSIFY_PROMPT

    if vision_reader is None:
        result.skipped_count = -1  # sentinel
        msg = "BỎ QUA: không có vision_reader (có thể anthropic chưa cài)"
        result.details.append(msg)
        if report is not None:
            report.add_skip(msg, "part-classifier-no-vision")
        return result

    # lọc parts cần re-classify
    candidates: List[SemanticPart] = []
    for part in parts:
        if part.confidence < confidence_threshold and part.part_type != "unclassified":
            candidates.append(part)

    if not candidates:
        result.details.append(
            f"Không có part nào cần re-classify "
            f"(confidence_threshold={confidence_threshold})"
        )
        return result

    result.details.append(
        f"tìm {len(candidates)} part cần re-classify "
        f"(confidence<{confidence_threshold})"
    )

    for part in candidates:
        # gom bbox_px của tất cả primitive trong part
        bboxes: List[tuple] = []
        for pid in part.primitive_ids:
            prim = primitives_by_id.get(pid)
            if prim is not None and hasattr(prim, "trace") and prim.trace is not None:
                bboxes.append(prim.trace.bbox_px)

        if not bboxes:
            result.skipped_count += 1
            msg = f"{part.id}: bỏ qua — không có bbox_px cho primitives {part.primitive_ids}"
            result.details.append(msg)
            continue

        merged = _merged_bbox(bboxes)
        if merged is None:
            result.skipped_count += 1
            continue

        crop = _safe_crop(image_bgr, merged, padding=0)
        if crop is None:
            result.skipped_count += 1
            msg = f"{part.id}: bỏ qua — merged bbox ngoài ảnh gốc"
            result.details.append(msg)
            continue

        # gọi Vision API với prompt phân loại
        try:
            # vision_reader nhận (crop_bgr, prompt_text)
            response = vision_reader(crop, effective_prompt)
        except Exception as exc:
            result.skipped_count += 1
            msg = f"{part.id}: Vision API lỗi — {exc}"
            result.details.append(msg)
            continue

        result.classified_count += 1

        # parse response
        parsed = _parse_llm_response(response)
        if parsed is None:
            result.rejected_count += 1
            msg = (
                f"{part.id}: LLM trả response không hợp lệ — '{response[:100]}' "
                f"-> KHÔNG apply (giữ nguyên part_type={part.part_type})"
            )
            result.details.append(msg)
            if report is not None:
                report.add_task(AgentTask(
                    task_type="reclassify_part",
                    part_id=part.id,
                    reason=f"confidence={part.confidence} < {confidence_threshold}",
                ))
                report.add_action(AgentAction(
                    task_id=f"classify-{part.id}",
                    action_type="no_action",
                    confidence=0.0,
                    notes=f"LLM response không hợp lệ: '{response[:100]}'",
                    evidence=Evidence(prompt=effective_prompt[:200], response=response[:200]),
                ))
            continue

        new_part_type, new_confidence = parsed

        if new_part_type == part.part_type:
            # LLM xác nhận part_type gốc → không cần thay đổi
            result.unchanged_count += 1
            result.details.append(
                f"{part.id}: LLM xác nhận part_type={new_part_type} "
                f"(conf={new_confidence}) -> không thay đổi"
            )
            if report is not None:
                report.add_task(AgentTask(
                    task_type="reclassify_part",
                    part_id=part.id,
                    reason=f"confidence={part.confidence} < {confidence_threshold}",
                ))
                report.add_action(AgentAction(
                    task_id=f"classify-{part.id}",
                    action_type="no_action",
                    confidence=new_confidence,
                    notes=f"LLM xác nhận part_type={new_part_type}",
                    evidence=Evidence(prompt=effective_prompt[:200], response=response[:200]),
                ))
            continue

        # LLM chọn part_type khác → tạo AgentAction override
        action = AgentAction(
            task_id=f"classify-{part.id}",
            action_type="override_part_type",
            confidence=new_confidence,
            target_part_id=part.id,
            new_part_type=new_part_type,
            notes=(
                f"override part {part.id}: {part.part_type} -> {new_part_type} "
                f"(confidence gốc={part.confidence}, LLM confidence={new_confidence}, "
                f"source: rule_geometry -> vision_assisted)"
            ),
            evidence=Evidence(
                prompt=effective_prompt[:200],
                response=response[:200],
                model=_DEFAULT_MODEL,
            ),
        )
        result.actions.append(action)

        if report is not None:
            report.add_task(AgentTask(
                task_type="reclassify_part",
                part_id=part.id,
                reason=f"confidence={part.confidence} < {confidence_threshold}",
            ))
            report.add_action(action)

        result.details.append(
            f"{part.id}: override {part.part_type} -> {new_part_type} "
            f"(LLM conf={new_confidence})"
        )

    return result
