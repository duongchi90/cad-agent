"""
test_io_utils.py — Kiểm tra agent_lib/io_utils.py.
LUÔN CHẠY ĐƯỢC — chỉ dùng json + tempfile, không cần package ngoài.
"""

import json
import os
import tempfile
import unittest
from unittest import TestCase

from agent_lib.io_utils import load_document_dict, save_document
from agent_lib.models import (
    AgentAction, AgentReport, AgentTask, Evidence, ResolutionWinner,
)


def _make_sample_report() -> AgentReport:
    """Tạo AgentReport mẫu có đủ loại field để test round-trip."""
    report = AgentReport()
    report.add_task(AgentTask(
        task_type="reread_text",
        primitive_id="text-001",
        reason="confidence=0.3 < 0.5",
    ))
    report.add_action(AgentAction(
        task_id=report.tasks[0].id,
        action_type="override_text",
        confidence=0.95,
        target_primitive_id="text-001",
        new_text_content="1700",
        new_semantic_role="dimension_value",
        notes="Ghi chú tiếng Việt: đọc lại số kích thước xoay dọc — fallback sang Vision",
    ))
    report.add_skip("không có solve_result", "advisor-no-solve-result")
    return report


class TestSaveDocument(TestCase):
    """Kiểm tra save_document — ghi AgentReport ra JSON."""

    def test_save_creates_file(self):
        """save_document tạo file JSON hợp lệ."""
        report = _make_sample_report()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_document(report, path)
            self.assertTrue(os.path.exists(path))
            # đọc lại bằng json.load để verify format
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["schema_version"], "1.0.0")
            self.assertEqual(data["task_count"], 1)
            self.assertEqual(data["action_count"], 1)
            self.assertEqual(data["skipped_count"], 1)
        finally:
            os.unlink(path)

    def test_save_preserves_vietnamese(self):
        """ensure_ascii=False giữ ký tự tiếng Việt trong notes."""
        report = _make_sample_report()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_document(report, path)
            with open(path, "rb") as f:
                raw = f.read()
            # tiếng Việt "Ghi chú tiếng Việt" phải nằm nguyên trong file, không escape \u
            self.assertIn("Ghi chú tiếng Việt".encode("utf-8"), raw)
            # KHÔNG chứa escape Unicode (ensure_ascii=False)
            self.assertNotIn(b"\\u", raw)
        finally:
            os.unlink(path)

    def test_save_empty_report(self):
        """AgentReport rỗng không crash khi save."""
        report = AgentReport()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_document(report, path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["task_count"], 0)
            self.assertEqual(data["action_count"], 0)
        finally:
            os.unlink(path)


class TestLoadDocumentDict(TestCase):
    """Kiểm tra load_document_dict — đọc file JSON → dict thô."""

    def test_load_roundtrip_matches_to_dict(self):
        """save → load → so khớp với to_dict() gốc."""
        report = _make_sample_report()
        expected = report.to_dict()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_document(report, path)
            loaded = load_document_dict(path)
            # so từng field quan trọng
            self.assertEqual(loaded["schema_version"], expected["schema_version"])
            self.assertEqual(loaded["task_count"], expected["task_count"])
            self.assertEqual(loaded["action_count"], expected["action_count"])
            self.assertEqual(loaded["skipped_count"], expected["skipped_count"])
            self.assertEqual(loaded["summary"], expected["summary"])
            self.assertEqual(len(loaded["tasks"]), len(expected["tasks"]))
            self.assertEqual(len(loaded["actions"]), len(expected["actions"]))
            self.assertEqual(loaded["skip_reasons"], expected["skip_reasons"])
        finally:
            os.unlink(path)

    def test_load_missing_file_raises(self):
        """File không tồn tại → FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            load_document_dict("/tmp/khong_ton_tai_agent_report_12345.json")


class TestRoundTrip(TestCase):
    """Kiểm tra save → load toàn diện hơn."""

    def test_roundtrip_complex_report(self):
        """AgentReport có nhiều loại task/action → round-trip giữ nguyên số liệu."""
        report = AgentReport()
        # thêm nhiều task/action đa dạng
        report.add_task(AgentTask(task_type="reclassify_part", part_id="part-1", reason="conf=0.55"))
        report.add_task(AgentTask(task_type="resolve_conflict", cross_validation_id="cv-1", reason="delta=15%"))
        report.add_task(AgentTask(task_type="advise_constraint", constraint_id="cst-1", reason="solver fail"))

        report.add_action(AgentAction(
            task_id="t1", action_type="override_part_type", confidence=0.85,
            target_part_id="part-1", new_part_type="thanh_ngang",
        ))
        report.add_action(AgentAction(
            task_id="t2", action_type="pick_conflict_winner", confidence=0.9,
            target_cross_validation_id="cv-1", conflict_winner="text",
            notes="winner=text: text_value=4200, geometry=287.5, delta=93.2%",
            evidence=Evidence(prompt="prompt dài...", response='{"winner": "text"}'),
        ))
        report.add_action(AgentAction(
            task_id="t3", action_type="drop_constraint", confidence=0.9,
            dropped_constraint_id="cst-1",
        ))
        report.add_action(AgentAction(
            task_id="t4", action_type="no_action", confidence=0.7,
            notes="LLM xác nhận part_type gốc đúng",
        ))

        report.add_skip("không có image_bgr", "text-rereader-no-image")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_document(report, path)
            loaded = load_document_dict(path)

            self.assertEqual(loaded["task_count"], 3)
            self.assertEqual(loaded["action_count"], 4)
            self.assertEqual(loaded["skipped_count"], 1)
            self.assertEqual(loaded["summary"]["override_part_type"], 1)
            self.assertEqual(loaded["summary"]["pick_conflict_winner"], 1)
            self.assertEqual(loaded["summary"]["drop_constraint"], 1)
            self.assertEqual(loaded["summary"]["no_action"], 1)
            # verify evidence được lưu đúng
            action2 = loaded["actions"][1]
            self.assertIsNotNone(action2["evidence"])
            self.assertEqual(action2["evidence"]["prompt"], "prompt dài...")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
