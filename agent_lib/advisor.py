"""
advisor.py — Constraint Advisor (rule-based thuần, KHÔNG cần Vision API).

Vai trò: khi Constraint Solving (Phase 2, constraint_solving.py) trả về
status != "okay" (didnt_converge hoặc inconsistent), advisor phân tích
danh sách constraints và đề xuất XÓT constraint có confidence thấp nhất, lặp
đến khi solver converge hoặc đạt giới hạn retry.

Đây là module duy nhất trong agent_lib KHÔNG dùng LLM/Vision — quyết định
drop dựa trên confidence đã có trong constraint (rule-based thuần, đúng
nguyên tắc mục 7 tài liệu kiến trúc: "ưu tiên rule-based/deterministic; AI
chỉ xử lý phần confidence thấp/ký hiệu lạ").

Thiết kế: KHÔNG tự apply drop vào constraint list gốc — trả danh sách
AgentAction để caller quyết định (đúng nguyên tắc "Agent chỉ khuyên" đã áp
dụng cho toàn bộ Phase 5).

Optional dependency: `python-solvespace` (cần cho bước re-solve sau mỗi
drop) — nếu chưa cài, advisor vẫn đề xuất drop nhưng KHÔNG re-solve để xác
nhận (caller nhận action list nhưng biết là chưa verify bằng solver thật).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import AgentAction, AgentReport, AgentTask, Evidence, new_id


@dataclass
class AdvisorResult:
    """Kết quả 1 lần chạy advisor."""
    actions: List[AgentAction] = field(default_factory=list)
    dropped_constraint_ids: List[str] = field(default_factory=list)
    final_status: Optional[str] = None       # "converged" | "still_failing" | "no_constraints" | "no_solve_result"
    iteration_count: int = 0
    details: List[str] = field(default_factory=list)


def _sorted_by_confidence(
    constraints: list, ascending: bool = True,
) -> list:
    """Sắp xếp constraint theo confidence (thấp nhất trước hoặc cao nhất trước)."""
    return sorted(constraints, key=lambda c: c.confidence, reverse=not ascending)


def _find_lowest_confidence_constraint(constraints: list) -> Optional[object]:
    """Tìm constraint có confidence thấp nhất. Trả None nếu danh sách rỗng."""
    if not constraints:
        return None
    return min(constraints, key=lambda c: c.confidence)


def advise_drop_constraints(
    constraints: list,
    solve_result: Optional[object] = None,
    primitive_doc: Optional[object] = None,
    max_iterations: int = 10,
    report: Optional[AgentReport] = None,
) -> AdvisorResult:
    """Phân tích constraints + solve result, đề xuất drop constraint có
    confidence thấp nhất cho đến khi solver converge hoặc hết retry.

    Nếu `solve_result` là None hoặc status == "okay" → không cần advisor,
    trả danh sách action rỗng với lý do rõ ràng.

    Nếu `python-solvespace` chưa cài → vẫn đề xuất drop (dựa trên confidence)
    nhưng KHÔNG re-solve, nên `final_status = "no_solve_result"`.

    Optional dependency `python-solvespace`: cài thì advisor re-solve sau mỗi
    drop để verify; không cài thì chỉ đề xuất, caller tự verify bằng cách khác.
    """
    result = AdvisorResult()

    # --- kiểm tra đầu vào ---
    if solve_result is None:
        result.final_status = "no_solve_result"
        result.details.append(
            "BỎ QUA: không có solve_result (có thể python-solvespace chưa cài "
            "hoặc chưa chạy constraint_solving)"
        )
        if report is not None:
            report.add_skip(result.details[-1], "advisor-no-solve-result")
        return result

    solve_status = getattr(solve_result, "status", None)
    if solve_status == "okay":
        result.final_status = "converged"
        result.details.append("Solver đã converge — không cần advisor")
        return result

    if not constraints:
        result.final_status = "no_constraints"
        result.details.append("BỎ QUA: danh sách constraint rỗng")
        return result

    # --- bắt đầu vòng lặp drop ---
    remaining = list(constraints)  # copy, không sửa list gốc
    dropped_ids: List[str] = []

    for iteration in range(max_iterations):
        result.iteration_count = iteration + 1

        if not remaining:
            result.final_status = "no_constraints"
            result.details.append(
                f"iteration {iteration}: đã drop hết constraint, solver vẫn không converge"
            )
            break

        # tìm constraint có confidence thấp nhất
        weakest = _find_lowest_confidence_constraint(remaining)
        if weakest is None:
            break

        # tạo AgentAction đề xuất drop
        action = AgentAction(
            task_id=f"advisor-iter-{iteration}",
            action_type="drop_constraint",
            confidence=0.9,  # advisor tự tin — đề xuất dựa trên confidence có sẵn
            dropped_constraint_id=weakest.id,
            notes=(
                f"iteration {iteration}: drop constraint {weakest.id} "
                f"(type={weakest.type}, conf={weakest.confidence:.4f}) — "
                f"confidence thấp nhất trong {len(remaining)} constraint còn lại"
            ),
        )
        result.actions.append(action)
        dropped_ids.append(weakest.id)

        if report is not None:
            report.add_task(AgentTask(
                task_type="advise_constraint",
                constraint_id=weakest.id,
                reason=f"lowest confidence={weakest.confidence:.4f} in iteration {iteration}",
            ))
            report.add_action(action)

        # drop constraint khỏi danh sách còn lại
        remaining = [c for c in remaining if c.id != weakest.id]

        # thử re-solve với danh sách rút gọn (cần python-solvespace)
        try:
            from semantic_ir_lib.constraint_solving import solve_constraints
            if primitive_doc is None:
                # không có primitive_doc → không thể re-solve. Vẫn đề xuất
                # drop dựa trên confidence nhưng status báo rõ chưa verify.
                result.final_status = "no_solve_result"
                result.details.append(
                    f"iteration {iteration}: drop {weakest.id} nhưng không có "
                    f"primitive_doc để re-solve — drop đề xuất chưa verify"
                )
                break

            new_solve = solve_constraints(primitive_doc, remaining)
            new_status = getattr(new_solve, "status", None)

            if new_status == "okay":
                result.final_status = "converged"
                result.details.append(
                    f"iteration {iteration}: drop {weakest.id} -> solver "
                    f"converge ({len(remaining)} constraints còn lại)"
                )
                break
            else:
                result.details.append(
                    f"iteration {iteration}: drop {weakest.id} -> solver vẫn "
                    f"status={new_status}, tiếp tục..."
                )
        except ImportError:
            result.final_status = "no_solve_result"
            result.details.append(
                f"iteration {iteration}: drop {weakest.id} — python-solvespace "
                f"chưa cài, không re-solve để verify"
            )
            break
    else:
        # hết iteration mà vẫn không converge
        result.final_status = "still_failing"
        result.details.append(
            f"đạt giới hạn {max_iterations} iterations, solver vẫn không converge "
            f"({len(remaining)} constraints còn lại, {len(dropped_ids)} đã drop)"
        )

    result.dropped_constraint_ids = dropped_ids
    return result


def apply_advisor_actions(
    constraints: list,
    actions: List[AgentAction],
) -> List[object]:
    """Áp dụng danh sách action drop_constraint vào constraint list.
    Trả danh sách constraint còn lại (đã drop).

    Lưu ý: hàm này MUTATE danh sách constraints gốc nếu caller truyền reference.
    Nên dùng: constraints_kept = apply_advisor_actions(list(constraints), actions)
    """
    drop_ids = set()
    for action in actions:
        if action.action_type == "drop_constraint" and action.dropped_constraint_id:
            drop_ids.add(action.dropped_constraint_id)
            action.applied = True

    kept = [c for c in constraints if c.id not in drop_ids]
    return kept
