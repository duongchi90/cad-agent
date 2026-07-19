"""
test_conflict_resolver.py — Kiểm tra Conflict Resolver (conflict_resolver.py).
LUÔN CHẠY ĐƯỢC — mock Vision reader, không cần API key.
"""

import unittest
from unittest import TestCase

import numpy as np

from agent_lib.conflict_resolver import resolve_conflicts
from agent_lib.models import AgentReport
from primitive_ir_lib.models import (
    Calibration, CrossValidation, LineGeometry, Point2D, Primitive,
    SourceDocument, TextData, Trace, Validation, PrimitiveIRDocument,
)


def _make_primitive_doc_with_prims(prims: list) -> PrimitiveIRDocument:
    return PrimitiveIRDocument(
        source_document=SourceDocument(
            file_name="test.png", page_index=0,
            image_width_px=200, image_height_px=200,
        ),
        calibration=Calibration(
            unit="mm", pixel_to_unit_scale=2.5,
            origin_px=(0.0, 200.0), method="manual_override",
        ),
        primitives=prims,
    )


def _make_text_prim(pid: str, content: str, bbox_px: tuple = (10, 10, 100, 50)) -> Primitive:
    return Primitive(
        id=pid, type="text", source="text_vision", confidence=0.95,
        text_data=TextData(
            content=content, position=Point2D(0, 0),
            rotation_deg=0, height=5.0, parsed_value=float(content) if content.isdigit() else None,
            semantic_role="dimension_value" if content.isdigit() else "unknown",
        ),
        trace=Trace(bbox_px=bbox_px),
        validation=Validation(),
    )


def _make_line_prim(pid: str, bbox_px: tuple = (10, 60, 200, 70)) -> Primitive:
    return Primitive(
        id=pid, type="line", source="geometry_opencv", confidence=0.9,
        geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(100, 0)),
        trace=Trace(bbox_px=bbox_px),
        validation=Validation(),
    )


def _make_image(h: int = 200, w: int = 200) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


class TestConflictResolver(TestCase):
    def test_skip_no_vision_reader(self):
        """Không có vision_reader → skip toàn bộ."""
        text_prim = _make_text_prim("t1", "1700")
        line_prim = _make_line_prim("l1")
        doc = _make_primitive_doc_with_prims([text_prim, line_prim])
        conflict = CrossValidation(
            text_primitive_id="t1", geometry_primitive_id="l1",
            status="conflict", text_value=1700, geometry_measured_length=1955,
            delta_percent=15.0, match_threshold_percent=3.0,
        )
        image = _make_image()

        result = resolve_conflicts(
            doc, [conflict], image, vision_reader=None,
        )
        self.assertEqual(result.skipped_count, -1)
        self.assertEqual(len(result.actions), 0)

    def test_skip_no_conflicts(self):
        """Không có conflict → không xử lý."""
        text_prim = _make_text_prim("t1", "1700")
        line_prim = _make_line_prim("l1")
        doc = _make_primitive_doc_with_prims([text_prim, line_prim])
        confirmed = CrossValidation(
            text_primitive_id="t1", geometry_primitive_id="l1",
            status="confirmed",
        )
        image = _make_image()

        result = resolve_conflicts(
            doc, [confirmed], image,
            vision_reader=lambda c, p: "{}",
        )
        self.assertEqual(len(result.actions), 0)
        self.assertEqual(result.resolved_count, 0)

    def test_resolve_winner_text(self):
        """Vision chọn text → tạo action pick text."""
        text_prim = _make_text_prim("t1", "1700", bbox_px=(10, 10, 100, 50))
        line_prim = _make_line_prim("l1", bbox_px=(10, 60, 200, 70))
        doc = _make_primitive_doc_with_prims([text_prim, line_prim])
        conflict = CrossValidation(
            text_primitive_id="t1", geometry_primitive_id="l1",
            status="conflict", text_value=1700, geometry_measured_length=1955,
            delta_percent=15.0, match_threshold_percent=3.0,
        )
        image = _make_image()

        def mock_reader(crop, prompt):
            return '{"winner": "text", "value": 1700, "confidence": 0.9}'

        result = resolve_conflicts(
            doc, [conflict], image, vision_reader=mock_reader,
        )
        self.assertEqual(result.resolved_count, 1)
        self.assertEqual(len(result.actions), 1)
        action = result.actions[0]
        self.assertEqual(action.action_type, "pick_conflict_winner")
        self.assertEqual(action.conflict_winner, "text")

    def test_resolve_winner_geometry(self):
        """Vision chọn geometry → tạo action pick geometry."""
        text_prim = _make_text_prim("t1", "1700")
        line_prim = _make_line_prim("l1")
        doc = _make_primitive_doc_with_prims([text_prim, line_prim])
        conflict = CrossValidation(
            text_primitive_id="t1", geometry_primitive_id="l1",
            status="conflict", text_value=1700, geometry_measured_length=1955,
            delta_percent=15.0, match_threshold_percent=3.0,
        )
        image = _make_image()

        def mock_reader(crop, prompt):
            return '{"winner": "geometry", "value": 1955, "confidence": 0.85}'

        result = resolve_conflicts(
            doc, [conflict], image, vision_reader=mock_reader,
        )
        self.assertEqual(result.resolved_count, 1)
        action = result.actions[0]
        self.assertEqual(action.conflict_winner, "geometry")

    def test_resolve_winner_new_value(self):
        """Vision chọn giá trị mới → tạo action với new_value."""
        text_prim = _make_text_prim("t1", "1700")
        line_prim = _make_line_prim("l1")
        doc = _make_primitive_doc_with_prims([text_prim, line_prim])
        conflict = CrossValidation(
            text_primitive_id="t1", geometry_primitive_id="l1",
            status="conflict", text_value=1700, geometry_measured_length=1955,
            delta_percent=15.0, match_threshold_percent=3.0,
        )
        image = _make_image()

        def mock_reader(crop, prompt):
            return '{"winner": "new_value", "value": 1800, "confidence": 0.8}'

        result = resolve_conflicts(
            doc, [conflict], image, vision_reader=mock_reader,
        )
        self.assertEqual(result.resolved_count, 1)
        action = result.actions[0]
        self.assertEqual(action.conflict_winner, "new_value")
        self.assertAlmostEqual(action.conflict_new_value, 1800.0)

    def test_reject_invalid_response(self):
        """Vision trả response không hợp lệ → rejected."""
        text_prim = _make_text_prim("t1", "1700")
        line_prim = _make_line_prim("l1")
        doc = _make_primitive_doc_with_prims([text_prim, line_prim])
        conflict = CrossValidation(
            text_primitive_id="t1", geometry_primitive_id="l1",
            status="conflict", text_value=1700, geometry_measured_length=1955,
            delta_percent=15.0,
        )
        image = _make_image()

        def mock_reader(crop, prompt):
            return "không phải json"

        result = resolve_conflicts(
            doc, [conflict], image, vision_reader=mock_reader,
        )
        self.assertEqual(result.rejected_count, 1)
        self.assertEqual(len(result.actions), 0)

    def test_report_integration(self):
        """Ghi task/action vào report."""
        text_prim = _make_text_prim("t1", "1700")
        line_prim = _make_line_prim("l1")
        doc = _make_primitive_doc_with_prims([text_prim, line_prim])
        conflict = CrossValidation(
            text_primitive_id="t1", geometry_primitive_id="l1",
            status="conflict", text_value=1700, geometry_measured_length=1955,
            delta_percent=15.0, match_threshold_percent=3.0,
        )
        image = _make_image()
        report = AgentReport()

        result = resolve_conflicts(
            doc, [conflict], image,
            vision_reader=lambda c, p: '{"winner": "text", "value": 1700, "confidence": 0.9}',
            report=report,
        )
        self.assertGreater(report.task_count, 0)
        self.assertGreater(report.action_count, 0)


if __name__ == "__main__":
    unittest.main()
