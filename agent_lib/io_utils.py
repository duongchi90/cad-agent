"""
io_utils.py — Lưu AgentReport ra JSON + đọc dict thô.

Khớp pattern `semantic_ir_lib/io_utils.py`: chỉ có `save_document()` và
`load_document_dict()`, KHÔNG có `from_dict()` / `load_agent_report()` — theo
chốt thiết kế Phase 5: Agent chỉ chạy forward (Primitive+Semantic → Agent →
save), không cần load lại AgentReport đã lưu để re-apply hoặc diff. Nếu sau
này cần đọc-ngược AgentReport thành object `AgentReport` thật, viết thêm các
helper `_agent_task_from_dict`/`_agent_action_from_dict`/`_evidence_from_dict`
theo pattern `semantic_ir_lib/io_utils.py` (xem note cuối file).

Tách logic save/load ra khỏi `demo_pipeline.py` (trước đây tự `json.dump`
inline) để `run.py` và các caller khác tái use cùng 1 hàm.
"""

from __future__ import annotations

import json

from .models import AgentReport


def save_document(report: AgentReport, path: str) -> None:
    """Lưu AgentReport ra file JSON, encoding utf-8 + ensure_ascii=False để
    giữ nguyên ký tự tiếng Việt trong `notes`/`reason`/`prompt`. Indent=2
    khớp mọi lib khác (primitive_ir_lib/semantic_ir_lib/dxf_builder_lib)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)


def load_document_dict(path: str) -> dict:
    """Đọc file JSON đã lưu (bởi save_document hoặc xuất thủ công theo
    `agent_ir.schema.json`) → dict thô. Caller tự rebuild object nếu cần.

    KHÔNG rebuild `AgentReport` tại đây — không có `AgentReport.from_dict()`
    (theo chốt thiết kế). Nếu cần inspect, đọc dict rồi tra field trực tiếp
    (report['task_count'], report['actions'], ...)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
