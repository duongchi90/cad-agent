"""
test_advisor.py — Kiểm tra Constraint Advisor (advisor.py).
Test drop lowest confidence, re-solve loop, skip cases.
LUÔN CHẠY ĐƯỢC — không cần python-solvespace (mock hoặc skip).
"""

import unittest
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from unittest import TestCase

from agent_lib.advisor import (
    advise_drop_constraints, apply_advisor_actions,
)
from agent_lib.models import AgentReport


# ---- mock Constraint (giống semantic_ir_lib.models.Constraint) ----

@dataclass
class MockConstraint:
    id: str
    type: str = "parallel"
    primitive_ids: List[str] = field(default_factory=list)
    confidence: float = 1.0
    tolerance: dict = field(default_factory=dict)
    measured: Optional[dict] = None


@dataclass
class MockSolveResult:
    status: str
    solved_primitives: Dict = field(default_factory=dict)


class TestConstraintAdvisor(TestCase):
    def test_skip_when_no_solve_result(self):
        """Không có solve_result → skip toàn bộ."""
        constraints = [MockConstraint(id="c1", confidence=0.8)]
        result = advise_drop_constraints(constraints, solve_result=None)
        self.assertEqual(result.final_status, "no_solve_result")
        self.assertEqual(len(result.actions), 0)

    def test_skip_when_solver_okay(self):
        """Solver đã converge → không cần advisor."""
        constraints = [MockConstraint(id="c1", confidence=0.5)]
        solve_result = MockSolveResult(status="okay")
        result = advise_drop_constraints(constraints, solve_result=solve_result)
        self.assertEqual(result.final_status, "converged")
        self.assertEqual(len(result.actions), 0)

    def test_drop_lowest_confidence(self):
        """Drop constraint có confidence thấp nhất."""
        c1 = MockConstraint(id="c-high", confidence=0.9)
        c2 = MockConstraint(id="c-mid", confidence=0.7)
        c3 = MockConstraint(id="c-low", confidence=0.5)
        constraints = [c1, c2, c3]

        solve_result = MockSolveResult(status="didnt_converge")
        result = advise_drop_constraints(
            constraints, solve_result=solve_result,
            max_iterations=1,  # chỉ 1 iteration, không re-solve
        )
        # phải đề xuất drop c-low (confidence 0.5)
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.actions[0].dropped_constraint_id, "c-low")
        self.assertEqual(result.final_status, "no_solve_result")  # không re-solve được

    def test_multiple_iterations(self):
        """Drop nhiều constraint qua nhiều iteration."""
        c1 = MockConstraint(id="c1", confidence=0.5)
        c2 = MockConstraint(id="c2", confidence=0.6)
        c3 = MockConstraint(id="c3", confidence=0.9)
        constraints = [c1, c2, c3]

        solve_result = MockSolveResult(status="didnt_converge")
        result = advise_drop_constraints(
            constraints, solve_result=solve_result,
            max_iterations=5,
        )
        # mỗi iteration drop 1 → 3 iterations (c1, c2, c3) hoặc dừng sớm
        self.assertGreater(len(result.actions), 0)
        self.assertTrue(result.iteration_count > 0)

    def test_empty_constraints(self):
        """Danh sách constraint rỗng → skip."""
        solve_result = MockSolveResult(status="didnt_converge")
        result = advise_drop_constraints([], solve_result=solve_result)
        self.assertEqual(result.final_status, "no_constraints")
        self.assertEqual(len(result.actions), 0)

    def test_max_iterations_limit(self):
        """Không vượt quá max_iterations khi có thể re-solve (giả lập bằng sys.modules)."""
        import sys
        import types

        constraints = [MockConstraint(id=f"c{i}", confidence=0.5 + i * 0.01) for i in range(20)]
        solve_result = MockSolveResult(status="didnt_converge")

        # tạo fake module semantic_ir_lib.constraint_solving với solve_constraints luôn fail
        fake_cs = types.ModuleType("semantic_ir_lib.constraint_solving")
        fake_cs.solve_constraints = lambda doc, csts: MockSolveResult(status="didnt_converge")
        original = sys.modules.get("semantic_ir_lib.constraint_solving")
        sys.modules["semantic_ir_lib.constraint_solving"] = fake_cs
        try:
            result = advise_drop_constraints(
                constraints, solve_result=solve_result,
                primitive_doc=object(),  # truthy để đi vào nhánh re-solve
                max_iterations=3,
            )
            self.assertEqual(result.iteration_count, 3)
            self.assertEqual(result.final_status, "still_failing")
        finally:
            if original is not None:
                sys.modules["semantic_ir_lib.constraint_solving"] = original
            else:
                del sys.modules["semantic_ir_lib.constraint_solving"]

    def test_report_integration(self):
        """Advisor ghi task/action vào report."""
        report = AgentReport()
        c1 = MockConstraint(id="c1", confidence=0.5)
        c2 = MockConstraint(id="c2", confidence=0.8)
        solve_result = MockSolveResult(status="didnt_converge")
        result = advise_drop_constraints(
            [c1, c2], solve_result=solve_result,
            max_iterations=1, report=report,
        )
        self.assertGreater(report.task_count, 0)
        self.assertGreater(report.action_count, 0)

    def test_apply_drop_actions(self):
        """apply_advisor_actions xóa đúng constraint."""
        c1 = MockConstraint(id="c1", confidence=0.5)
        c2 = MockConstraint(id="c2", confidence=0.8)
        c3 = MockConstraint(id="c3", confidence=0.6)
        constraints = [c1, c2, c3]

        from agent_lib.models import AgentAction
        actions = [
            AgentAction(task_id="t1", action_type="drop_constraint",
                        dropped_constraint_id="c1", confidence=0.9),
            AgentAction(task_id="t2", action_type="drop_constraint",
                        dropped_constraint_id="c3", confidence=0.9),
        ]
        kept = apply_advisor_actions(constraints, actions)
        kept_ids = [c.id for c in kept]
        self.assertEqual(kept_ids, ["c2"])
        # actions đã applied
        self.assertTrue(all(a.applied for a in actions))


if __name__ == "__main__":
    unittest.main()
