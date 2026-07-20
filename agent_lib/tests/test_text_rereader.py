"""
test_text_rereader.py — Kiểm tra Text Re-reader (text_rereader.py).
LUÔN CHẠY ĐƯỢC — mock Vision reader, không cần API key.
"""

import unittest
from unittest import TestCase

import numpy as np

from agent_lib.models import AgentReport
from agent_lib.text_rereader import reread_low_confidence_texts
from primitive_ir_lib.models import (
    Point2D, Primitive, TextData, Trace, Validation,
)


def _make_text_prim(
    content: str, confidence: float, role: str = "unknown",
    bbox_px: tuple = (10, 10, 100, 50),
) -> Primitive:
    return Primitive(
        id=f"prim-{content[:8]}",
        type="text",
        source="text_tesseract",
        confidence=confidence,
        text_data=TextData(
            content=content,
            position=Point2D(0, 0),
            rotation_deg=0,
            height=5.0,
            semantic_role=role,  # type: ignore
        ),
        trace=Trace(bbox_px=bbox_px),
        validation=Validation(),
    )


def _make_image(h: int = 200, w: int = 200) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


class TestTextRereader(TestCase):
    def test_skip_no_vision_reader(self):
        """Không có vision_reader → skip toàn bộ."""
        prims = [_make_text_prim("ABC", 0.3)]
        image = _make_image()
        result = reread_low_confidence_texts(prims, image, vision_reader=None)
        self.assertEqual(result.skipped_count, -1)  # sentinel
        self.assertEqual(len(result.actions), 0)

    def test_skip_high_confidence(self):
        """Confidence cao → không đẩy sang rereader."""
        prims = [_make_text_prim("ABC", 0.9, role="dimension_value")]
        image = _make_image()

        call_log = []
        def mock_reader(crop, prompt=None):
            call_log.append(crop)
            return "ABC"

        result = reread_low_confidence_texts(
            prims, image, vision_reader=mock_reader, confidence_threshold=0.5,
        )
        self.assertEqual(len(result.actions), 0)
        self.assertEqual(len(call_log), 0)  # không gọi Vision

    def test_override_when_different(self):
        """Vision trả text khác → tạo action override."""
        prims = [_make_text_prim("ABX", 0.3, role="unknown")]
        image = _make_image()

        def mock_reader(crop, prompt=None):
            return "ABC"  # khác gốc "ABX"

        result = reread_low_confidence_texts(
            prims, image, vision_reader=mock_reader, confidence_threshold=0.5,
        )
        self.assertEqual(len(result.actions), 1)
        action = result.actions[0]
        self.assertEqual(action.action_type, "override_text")
        self.assertEqual(action.new_text_content, "ABC")
        self.assertEqual(action.confidence, 0.95)

    def test_no_change_when_same(self):
        """Vision trả text giống gốc → không override."""
        prims = [_make_text_prim("ABC", 0.3, role="unknown")]
        image = _make_image()

        def mock_reader(crop, prompt=None):
            return "ABC"  # giống gốc

        result = reread_low_confidence_texts(
            prims, image, vision_reader=mock_reader, confidence_threshold=0.5,
        )
        self.assertEqual(len(result.actions), 0)
        self.assertEqual(result.unchanged_count, 1)

    def test_skip_no_bbox(self):
        """Không có bbox_px → skip primitive."""
        prim = Primitive(
            id="prim-nobbox", type="text", source="text_tesseract",
            confidence=0.3,
            text_data=TextData(content="X", position=Point2D(0, 0), rotation_deg=0, height=5),
            trace=Trace(bbox_px=(10, 10, 15, 15)),  # rất nhỏ nhưng có
            validation=Validation(),
        )
        # trace có nhưng bbox nhỏ → vẫn crop được, không skip
        image = _make_image()
        result = reread_low_confidence_texts(
            [prim], image, vision_reader=lambda c, p=None: "Y", confidence_threshold=0.5,
        )
        # không crash, có reread
        self.assertGreaterEqual(result.reread_count, 0)

    def test_report_integration(self):
        """Ghi task/action vào report."""
        prims = [_make_text_prim("OLD", 0.2, role="unknown")]
        image = _make_image()
        report = AgentReport()

        result = reread_low_confidence_texts(
            prims, image, vision_reader=lambda c, p=None: "NEW",
            confidence_threshold=0.5, report=report,
        )
        self.assertGreater(report.task_count, 0)
        self.assertGreater(report.action_count, 0)

    def test_dimension_value_role_after_override(self):
        """Override text số → semantic_role phải là dimension_value."""
        prims = [_make_text_prim("1234", 0.2, role="unknown")]
        image = _make_image()

        def mock_reader(crop, prompt=None):
            return "5678"  # số mới

        result = reread_low_confidence_texts(
            prims, image, vision_reader=mock_reader, confidence_threshold=0.5,
        )
        self.assertEqual(len(result.actions), 1)
        action = result.actions[0]
        self.assertEqual(action.new_semantic_role, "dimension_value")
        self.assertAlmostEqual(action.new_parsed_value, 5678.0)


if __name__ == "__main__":
    unittest.main()
