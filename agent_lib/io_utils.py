"""
io_utils.py — Lưu AgentReport ra JSON và đọc lại report đã duyệt.

`load_agent_report()` rebuild một report đã lưu chỉ cho bước application tách
biệt, có ràng buộc SHA-256. Lần chạy Agent thông thường vẫn forward-only và
advisory.

Tách logic save/load ra khỏi `demo_pipeline.py` (trước đây tự `json.dump`
inline) để `run.py` và các caller khác tái use cùng 1 hàm.
"""

from __future__ import annotations

import json

from .models import AgentAction, AgentReport, AgentTask, Evidence


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


def load_agent_report(path: str) -> AgentReport:
    """Load a saved AgentReport for a separately approved application step."""
    payload = load_document_dict(path)
    report = AgentReport(
        id=payload["id"],
        schema_version=payload["schema_version"],
        timestamp=payload["timestamp"],
        skipped_count=payload.get("skipped_count", 0),
        skip_reasons=dict(payload.get("skip_reasons", {})),
        summary=dict(payload.get("summary", {})),
    )
    report.tasks = [AgentTask(**task) for task in payload.get("tasks", [])]
    actions = []
    for item in payload.get("actions", []):
        action = dict(item)
        evidence = action.get("evidence")
        if evidence is not None:
            action["evidence"] = Evidence(**evidence)
        actions.append(AgentAction(**action))
    report.actions = actions
    if payload.get("task_count") != report.task_count:
        raise ValueError("Agent report task_count does not match its tasks.")
    if payload.get("action_count") != report.action_count:
        raise ValueError("Agent report action_count does not match its actions.")
    return report
