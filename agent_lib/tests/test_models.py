"""
test_models.py — Kiểm tra dataclass Agent IR (models.py).
Test serialize/deserialize, validate field, AgentReport tổng hợp.
"""

import unittest
from unittest import TestCase

from agent_lib.models import (
    AgentAction, AgentReport, AgentTask, Evidence,
    SCHEMA_VERSION,
)


class TestAgentTask(TestCase):
    def test_default_fields(self):
        task = AgentTask(task_type="reread_text")
        self.assertEqual(task.task_type, "reread_text")
        self.assertIsNotNone(task.id)
        self.assertTrue(task.id.startswith("task-"))
        self.assertIsNone(task.primitive_id)
        self.assertIsNone(task.part_id)
        self.assertEqual(task.priority, 0)

    def test_to_dict_minimal(self):
        task = AgentTask(task_type="advise_constraint", constraint_id="cst-abc")
        d = task.to_dict()
        self.assertEqual(d["task_type"], "advise_constraint")
        self.assertEqual(d["constraint_id"], "cst-abc")
        self.assertNotIn("primitive_id", d)
        self.assertNotIn("part_id", d)

    def test_to_dict_all_fields(self):
        task = AgentTask(
            task_type="resolve_conflict",
            primitive_id="prim-1",
            cross_validation_id="cv-1",
            priority=3,
            reason="delta 15% > ngưỡng 3%",
        )
        d = task.to_dict()
        self.assertEqual(d["primitive_id"], "prim-1")
        self.assertEqual(d["cross_validation_id"], "cv-1")
        self.assertEqual(d["priority"], 3)
        self.assertEqual(d["reason"], "delta 15% > ngưỡng 3%")

    def test_task_types(self):
        for tt in ["reclassify_part", "reread_text", "resolve_conflict", "advise_constraint"]:
            task = AgentTask(task_type=tt)
            self.assertEqual(task.task_type, tt)


class TestEvidence(TestCase):
    def test_to_dict(self):
        ev = Evidence(prompt="test prompt", response="test response", model="claude-sonnet-4-6")
        d = ev.to_dict()
        self.assertEqual(d["prompt"], "test prompt")
        self.assertEqual(d["response"], "test response")
        self.assertEqual(d["model"], "claude-sonnet-4-6")
        self.assertIn("timestamp", d)

    def test_to_dict_no_model(self):
        ev = Evidence(prompt="p", response="r")
        d = ev.to_dict()
        self.assertNotIn("model", d)


class TestAgentAction(TestCase):
    def test_default_fields(self):
        action = AgentAction(task_id="task-1", action_type="no_action")
        self.assertEqual(action.confidence, 0.0)
        self.assertFalse(action.applied)
        self.assertIsNone(action.evidence)

    def test_confidence_validation(self):
        with self.assertRaises(ValueError):
            AgentAction(task_id="t1", action_type="no_action", confidence=1.5)
        with self.assertRaises(ValueError):
            AgentAction(task_id="t1", action_type="no_action", confidence=-0.1)

    def test_to_dict_minimal(self):
        action = AgentAction(task_id="t1", action_type="no_action", confidence=0.9)
        d = action.to_dict()
        self.assertEqual(d["action_type"], "no_action")
        self.assertEqual(d["confidence"], 0.9)
        self.assertNotIn("new_part_type", d)

    def test_to_dict_override_part(self):
        action = AgentAction(
            task_id="t1", action_type="override_part_type",
            confidence=0.85, new_part_type="thanh_doc",
            notes="override từ thanh_xien",
        )
        d = action.to_dict()
        self.assertEqual(d["new_part_type"], "thanh_doc")
        self.assertEqual(d["notes"], "override từ thanh_xien")

    def test_to_dict_with_evidence(self):
        ev = Evidence(prompt="prompt", response="resp", model="m")
        action = AgentAction(
            task_id="t1", action_type="override_text",
            confidence=0.95, new_text_content="ABC", evidence=ev,
        )
        d = action.to_dict()
        self.assertIn("evidence", d)
        self.assertEqual(d["evidence"]["model"], "m")
        self.assertEqual(d["new_text_content"], "ABC")


class TestAgentReport(TestCase):
    def test_empty_report(self):
        report = AgentReport()
        d = report.to_dict()
        self.assertEqual(d["schema_version"], SCHEMA_VERSION)
        self.assertEqual(d["task_count"], 0)
        self.assertEqual(d["action_count"], 0)
        self.assertEqual(d["skipped_count"], 0)

    def test_add_task_action(self):
        report = AgentReport()
        report.add_task(AgentTask(task_type="reread_text"))
        report.add_task(AgentTask(task_type="advise_constraint"))
        report.add_action(AgentAction(task_id="t1", action_type="override_text", confidence=0.9))
        report.add_action(AgentAction(task_id="t2", action_type="drop_constraint", confidence=0.8))
        report.add_action(AgentAction(task_id="t3", action_type="no_action", confidence=0.5))

        self.assertEqual(report.task_count, 2)
        self.assertEqual(report.action_count, 3)
        self.assertEqual(report.summary.get("override_text"), 1)
        self.assertEqual(report.summary.get("drop_constraint"), 1)
        self.assertEqual(report.summary.get("no_action"), 1)

    def test_add_skip(self):
        report = AgentReport()
        report.add_skip("no vision reader", "text-rereader")
        report.add_skip("no image", "part-classifier")
        self.assertEqual(report.skipped_count, 2)
        d = report.to_dict()
        self.assertEqual(len(d["skip_reasons"]), 2)

    def test_to_dict_full(self):
        report = AgentReport()
        report.add_task(AgentTask(task_type="reread_text", primitive_id="p1"))
        report.add_action(AgentAction(
            task_id="t1", action_type="override_text",
            confidence=0.95, new_text_content="ABC",
        ))
        d = report.to_dict()
        self.assertEqual(len(d["tasks"]), 1)
        self.assertEqual(len(d["actions"]), 1)
        self.assertEqual(d["actions"][0]["new_text_content"], "ABC")


if __name__ == "__main__":
    unittest.main()
