"""
models.py — Dataclass Python cho Agent IR (Phase 5).

Cùng nguyên tắc đã áp dụng xuyên suột Phase 1–4: to_dict() phải sinh đúng
JSON structure, đây là lớp code DUY NHẤT "biết" chi tiết schema. Mọi module
khác (advisor, text_rereader, part_classifier, conflict_resolver, batch_agent)
chỉ import và dùng class ở đây, không tự build dict tay.

Agent IR là tầng dữ liệu nằm GIỮA Semantic IR (Phase 2) và DXF Builder
(Phase 3) trong pipeline. Vai trò: ghi nhận các quyết định mà LLM Agent đưa
ra cho từng case ambiguous, giữ audit trail đầy đủ (prompt + response) để
debug ngược, và tách bạch trách nhiệm — Agent chỉ khuyên, caller quyết định
apply hay không (đúng nguyên tắc "không đoán bừa", mục 7 tài liệu kiến trúc).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

SCHEMA_VERSION = "1.0.0"

TaskType = Literal[
    "reclassify_part",       # Part Re-classifier: LLM phân loại lại part_type
    "reread_text",           # Text Re-reader: LLM đọc lại text ambiguity
    "resolve_conflict",     # Conflict Resolver: LLM quyết định text vs geometry
    "advise_constraint",     # Constraint Advisor: rule-based khuyên drop constraint
]

ActionType = Literal[
    "override_part_type",    # LLM chọn part_type mới cho 1 SemanticPart
    "override_text",         # LLM đọc lại content của 1 Primitive text
    "pick_conflict_winner",  # LLM chọn text hoặc geometry làm giá trị đúng
    "drop_constraint",        # Advisor khuyên bỏ 1 constraint để solver converge
    "no_action",              # Agent quyết định không cần thay đổi
]

ResolutionWinner = Literal["text", "geometry", "new_value"]


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- AgentTask --
@dataclass
class AgentTask:
    """1 case ambiguous mà Agent cần xử lý. Caller sinh task, Agent trả action."""
    task_type: TaskType
    id: str = field(default_factory=lambda: new_id("task"))
    # 1 trong các field target này được điền, tùy task_type:
    primitive_id: Optional[str] = None       # cho reread_text, resolve_conflict
    part_id: Optional[str] = None            # cho reclassify_part
    constraint_id: Optional[str] = None      # cho advise_constraint
    cross_validation_id: Optional[str] = None # cho resolve_conflict
    priority: int = 0                        # 0 = cao nhất, số lớn = ưu tiên thấp hơn
    reason: str = ""                          # tại sao đẩy sang agent (vd "confidence 0.55 < ngưỡng 0.7")

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "task_type": self.task_type,
            "priority": self.priority,
            "reason": self.reason,
        }
        if self.primitive_id is not None:
            d["primitive_id"] = self.primitive_id
        if self.part_id is not None:
            d["part_id"] = self.part_id
        if self.constraint_id is not None:
            d["constraint_id"] = self.constraint_id
        if self.cross_validation_id is not None:
            d["cross_validation_id"] = self.cross_validation_id
        return d


# -------------------------------------------------------------- Evidence --
@dataclass
class Evidence:
    """Audit trail cho mỗi action: prompt gửi LLM + response nhận được.
    Giúp debug ngược khi Agent quyết định sai (xem 'tại sao lại override
    part_type này', 'prompt đã gửi gì, LLM đã trả gì')."""
    prompt: str
    response: str
    model: Optional[str] = None
    timestamp: str = field(default_factory=now_iso)

    def to_dict(self) -> dict:
        d = {
            "prompt": self.prompt,
            "response": self.response,
            "timestamp": self.timestamp,
        }
        if self.model is not None:
            d["model"] = self.model
        return d


# ------------------------------------------------------------- AgentAction --
@dataclass
class AgentAction:
    """Quyết định Agent đưa ra cho 1 task. Không tự apply — caller đọc
    action_type + values rồi quyết định có ghi đè lên Primitive/Semantic IR
    hay không (đúng nguyên tắc 'Agent chỉ khuyên')."""
    task_id: str                             # ref ngược tới AgentTask.id
    action_type: ActionType
    id: str = field(default_factory=lambda: new_id("action"))
    confidence: float = 0.0                  # confidence của chính quyết định này
    applied: bool = False                    # caller set True khi đã apply vào IR
    evidence: Optional[Evidence] = None      # audit trail (None nếu rule-based, không có LLM)
    # target trực tiếp (copy từ AgentTask để apply_agent_report không phụ thuộc
    # matching task_id — mỗi module gán task_id nội bộ khác nhau, dễ bị lệch):
    target_primitive_id: Optional[str] = None
    target_part_id: Optional[str] = None
    target_cross_validation_id: Optional[str] = None
    # giá trị override (điền tùy action_type):
    new_part_type: Optional[str] = None
    new_text_content: Optional[str] = None
    new_parsed_value: Optional[float] = None
    new_semantic_role: Optional[str] = None
    conflict_winner: Optional[ResolutionWinner] = None
    conflict_new_value: Optional[float] = None
    dropped_constraint_id: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self):
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"AgentAction {self.id}: confidence phải trong [0,1], nhận {self.confidence}"
            )

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "task_id": self.task_id,
            "action_type": self.action_type,
            "confidence": self.confidence,
            "applied": self.applied,
        }
        if self.evidence is not None:
            d["evidence"] = self.evidence.to_dict()
        if self.target_primitive_id is not None:
            d["target_primitive_id"] = self.target_primitive_id
        if self.target_part_id is not None:
            d["target_part_id"] = self.target_part_id
        if self.target_cross_validation_id is not None:
            d["target_cross_validation_id"] = self.target_cross_validation_id
        if self.new_part_type is not None:
            d["new_part_type"] = self.new_part_type
        if self.new_text_content is not None:
            d["new_text_content"] = self.new_text_content
        if self.new_parsed_value is not None:
            d["new_parsed_value"] = self.new_parsed_value
        if self.new_semantic_role is not None:
            d["new_semantic_role"] = self.new_semantic_role
        if self.conflict_winner is not None:
            d["conflict_winner"] = self.conflict_winner
        if self.conflict_new_value is not None:
            d["conflict_new_value"] = self.conflict_new_value
        if self.dropped_constraint_id is not None:
            d["dropped_constraint_id"] = self.dropped_constraint_id
        if self.notes is not None:
            d["notes"] = self.notes
        return d


# ----------------------------------------------------------- AgentReport --
@dataclass
class AgentReport:
    """Tổng hợp toàn bộ output của 1 lần chạy Agent (batch_agent.py).
    Caller đọc report này để quyết định apply từng action vào IR gốc."""
    id: str = field(default_factory=lambda: new_id("report"))
    schema_version: str = SCHEMA_VERSION
    timestamp: str = field(default_factory=now_iso)
    tasks: List[AgentTask] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)
    skipped_count: int = 0
    skip_reasons: Dict[str, str] = field(default_factory=dict)
    # summary counters theo task_type
    summary: Dict[str, int] = field(default_factory=dict)

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    @property
    def action_count(self) -> int:
        return len(self.actions)

    def add_task(self, task: AgentTask) -> None:
        self.tasks.append(task)

    def add_action(self, action: AgentAction) -> None:
        self.actions.append(action)
        # update summary counter
        key = action.action_type
        self.summary[key] = self.summary.get(key, 0) + 1

    def add_skip(self, reason: str, ref: str = "") -> None:
        self.skipped_count += 1
        key = ref or f"skip-{self.skipped_count}"
        self.skip_reasons[key] = reason

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "task_count": self.task_count,
            "action_count": self.action_count,
            "skipped_count": self.skipped_count,
            "summary": dict(self.summary),
            "tasks": [t.to_dict() for t in self.tasks],
            "actions": [a.to_dict() for a in self.actions],
            "skip_reasons": dict(self.skip_reasons),
        }
