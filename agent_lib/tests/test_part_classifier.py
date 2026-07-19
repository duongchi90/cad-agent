"""
test_part_classifier.py — Kiểm tra Part Re-classifier (part_classifier.py).
LUÔN CHẠY ĐƯỢC — mock Vision reader, không cần API key.
"""

import unittest
from unittest import TestCase

import numpy as np

from agent_lib.models import AgentReport
from agent_lib.part_classifier import reclassify_low_confidence_parts
from primitive_ir_lib.models import (
    CircleGeometry, LineGeometry, Point2D, Primitive, Trace, Validation,
)
from semantic_ir_lib.models import (
    GeometrySummary, PartValidation, SemanticPart,
)


def _make_line_prim(pid: str, bbox_px: tuple = (10, 10, 100, 50)) -> Primitive:
    return Primitive(
        id=pid, type="line", source="geometry_opencv", confidence=0.9,
        geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(100, 0)),
        trace=Trace(bbox_px=bbox_px),
        validation=Validation(),
    )


def _make_circle_prim(pid: str, bbox_px: tuple = (30, 30, 60, 60)) -> Primitive:
    return Primitive(
        id=pid, type="circle", source="geometry_opencv", confidence=0.8,
        geometry=CircleGeometry(center=Point2D(50, 50), radius=10),
        trace=Trace(bbox_px=bbox_px),
        validation=Validation(),
    )


def _make_image(h: int = 200, w: int = 200) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


class TestPartClassifier(TestCase):
    def test_skip_no_vision_reader(self):
        """Không có vision_reader → skip toàn bộ."""
        parts = [SemanticPart(
            part_type="thanh_ngang", primitive_ids=["p1"],
            confidence=0.55, source="rule_geometry",
        )]
        prim_index = {"p1": _make_line_prim("p1")}
        image = _make_image()

        result = reclassify_low_confidence_parts(
            parts, prim_index, image, vision_reader=None,
        )
        self.assertEqual(result.skipped_count, -1)
        self.assertEqual(len(result.actions), 0)

    def test_skip_high_confidence(self):
        """Confidence cao → không đẩy sang classifier."""
        parts = [SemanticPart(
            part_type="thanh_ngang", primitive_ids=["p1"],
            confidence=0.9, source="rule_geometry",
        )]
        prim_index = {"p1": _make_line_prim("p1")}
        image = _make_image()

        call_log = []
        def mock_reader(crop, prompt):
            call_log.append(crop)
            return '{"part_type": "thanh_doc", "confidence": 0.8}'

        result = reclassify_low_confidence_parts(
            parts, prim_index, image, vision_reader=mock_reader,
            confidence_threshold=0.7,
        )
        self.assertEqual(len(result.actions), 0)
        self.assertEqual(len(call_log), 0)

    def test_override_part_type(self):
        """Vision trả part_type khác → tạo action override."""
        parts = [SemanticPart(
            part_type="thanh_xien", primitive_ids=["p1"],
            confidence=0.55, source="rule_geometry",
        )]
        prim_index = {"p1": _make_line_prim("p1")}
        image = _make_image()

        def mock_reader(crop, prompt):
            return '{"part_type": "thanh_ngang", "confidence": 0.85}'

        result = reclassify_low_confidence_parts(
            parts, prim_index, image, vision_reader=mock_reader,
            confidence_threshold=0.7,
        )
        self.assertEqual(len(result.actions), 1)
        action = result.actions[0]
        self.assertEqual(action.action_type, "override_part_type")
        self.assertEqual(action.new_part_type, "thanh_ngang")
        self.assertEqual(action.confidence, 0.85)

    def test_reject_invalid_part_type(self):
        """Vision trả part_type không hợp lệ → KHÔNG apply."""
        parts = [SemanticPart(
            part_type="thanh_xien", primitive_ids=["p1"],
            confidence=0.55, source="rule_geometry",
        )]
        prim_index = {"p1": _make_line_prim("p1")}
        image = _make_image()

        def mock_reader(crop, prompt):
            return '{"part_type": "something_invalid", "confidence": 0.9}'

        result = reclassify_low_confidence_parts(
            parts, prim_index, image, vision_reader=mock_reader,
            confidence_threshold=0.7,
        )
        self.assertEqual(len(result.actions), 0)
        self.assertEqual(result.rejected_count, 1)

    def test_no_change_when_same_type(self):
        """Vision xác nhận part_type gốc → không override."""
        parts = [SemanticPart(
            part_type="thanh_ngang", primitive_ids=["p1"],
            confidence=0.55, source="rule_geometry",
        )]
        prim_index = {"p1": _make_line_prim("p1")}
        image = _make_image()

        def mock_reader(crop, prompt):
            return '{"part_type": "thanh_ngang", "confidence": 0.8}'

        result = reclassify_low_confidence_parts(
            parts, prim_index, image, vision_reader=mock_reader,
            confidence_threshold=0.7,
        )
        self.assertEqual(len(result.actions), 0)
        self.assertEqual(result.unchanged_count, 1)

    def test_skip_unclassified(self):
        """part_type = unclassified → không đẩy sang classifier (không có gì để override)."""
        parts = [SemanticPart(
            part_type="unclassified", primitive_ids=["p1"],
            confidence=0.3, source="rule_geometry",
        )]
        prim_index = {"p1": _make_line_prim("p1")}
        image = _make_image()

        result = reclassify_low_confidence_parts(
            parts, prim_index, image, vision_reader=lambda c, p: "{}",
            confidence_threshold=0.7,
        )
        # unclassified không được chọn (điều kiện: part_type != "unclassified")
        self.assertEqual(len(result.actions), 0)

    def test_report_integration(self):
        """Ghi task/action vào report."""
        parts = [SemanticPart(
            part_type="thanh_doc", primitive_ids=["p1"],
            confidence=0.6, source="rule_geometry",
        )]
        prim_index = {"p1": _make_line_prim("p1")}
        image = _make_image()
        report = AgentReport()

        result = reclassify_low_confidence_parts(
            parts, prim_index, image,
            vision_reader=lambda c, p: '{"part_type": "thanh_doc", "confidence": 0.8}',
            confidence_threshold=0.7, report=report,
        )
        self.assertGreater(report.task_count, 0)
        # action là no_action vì LLM xác nhận cùng type
        self.assertGreater(report.action_count, 0)


if __name__ == "__main__":
    unittest.main()
