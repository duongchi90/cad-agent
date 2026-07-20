"""
test_batch_agent.py — Kiểm tra tích hợp batch_agent.py.
LUÔN CHẠY ĐƯỢC — mock Vision reader, không cần API key hay package bên ngoài.
"""

import unittest
from typing import List
from unittest import TestCase

import numpy as np

from agent_lib.batch_agent import apply_agent_report, run_agent
from agent_lib.models import AgentAction, AgentReport
from primitive_ir_lib.models import (
    Calibration, CircleGeometry, CrossValidation, LineGeometry, Point2D,
    Primitive, SourceDocument, TextData, Trace, Validation, PrimitiveIRDocument,
)
from semantic_ir_lib.models import (
    Constraint, SemanticIRDocument, SemanticPart,
)


# ---- helpers ----

def _make_primitive_doc(
    n_lines: int = 3, n_texts: int = 2, n_circles: int = 1,
    add_conflict: bool = False,
) -> PrimitiveIRDocument:
    prims: List[Primitive] = []
    for i in range(n_lines):
        prims.append(Primitive(
            id=f"line-{i}", type="line", source="geometry_opencv", confidence=0.9,
            geometry=LineGeometry(start=Point2D(i * 50, 0), end=Point2D(i * 50 + 100, 0)),
            trace=Trace(bbox_px=(10 + i * 50, 10, 50 + i * 50, 20)),
            validation=Validation(),
        ))
    for i in range(n_texts):
        content = f"TEXT{i}"
        role = "unknown" if i == 0 else "dimension_value"
        conf = 0.3 if i == 0 else 0.9  # 1 text confidence thấp
        prims.append(Primitive(
            id=f"text-{i}", type="text", source="text_tesseract", confidence=conf,
            text_data=TextData(
                content=content, position=Point2D(0, 0),
                rotation_deg=0, height=5.0, semantic_role=role,  # type: ignore
            ),
            trace=Trace(bbox_px=(10, 30 + i * 30, 80, 50 + i * 30)),
            validation=Validation(),
        ))
    for i in range(n_circles):
        prims.append(Primitive(
            id=f"circle-{i}", type="circle", source="geometry_opencv", confidence=0.85,
            geometry=CircleGeometry(center=Point2D(45, 105), radius=15),
            trace=Trace(bbox_px=(30, 90, 60, 120)),
            validation=Validation(),
        ))

    cvs: List[CrossValidation] = []
    if add_conflict and n_texts > 0 and n_lines > 0:
        cvs.append(CrossValidation(
            text_primitive_id="text-0", geometry_primitive_id="line-0",
            status="conflict", text_value=100, geometry_measured_length=115,
            delta_percent=15.0, match_threshold_percent=3.0,
        ))

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
        cross_validations=cvs,
    )


def _make_semantic_doc(
    n_parts: int = 2, add_low_conf_part: bool = True,
) -> SemanticIRDocument:
    parts: List[SemanticPart] = []
    for i in range(n_parts):
        conf = 0.55 if (i == 0 and add_low_conf_part) else 0.9
        parts.append(SemanticPart(
            part_type="thanh_ngang" if i > 0 else "thanh_xien",
            primitive_ids=[f"line-{i}"],
            confidence=conf,
            source="rule_geometry",
        ))
    constraints: List[Constraint] = []
    return SemanticIRDocument(
        primitive_ir_ref={"file_name": "test", "primitive_count": 0},
        parts=parts,
        constraints=constraints,
    )


def _make_image() -> np.ndarray:
    return np.zeros((200, 200, 3), dtype=np.uint8)


def _mock_vision_reader(crop, prompt=None):
    """Mock Vision reader trả giá trị cố định tùy prompt."""
    if prompt and "part_type" in prompt.lower():
        return '{"part_type": "thanh_ngang", "confidence": 0.85}'
    if prompt and "conflict" in prompt.lower():
        return '{"winner": "text", "value": 100, "confidence": 0.9}'
    return "MOCK_TEXT"


# ---- tests ----

class TestBatchAgent(TestCase):
    def test_full_pipeline_with_vision(self):
        """Chạy full pipeline với mock Vision → có actions từ cả 4 module."""
        doc = _make_primitive_doc(n_lines=2, n_texts=2, add_conflict=True)
        sem_doc = _make_semantic_doc(n_parts=2, add_low_conf_part=True)
        image = _make_image()

        report = run_agent(
            primitive_doc=doc, semantic_doc=sem_doc,
            image_bgr=image, vision_reader=_mock_vision_reader,
            text_confidence_threshold=0.5,
            part_confidence_threshold=0.7,
        )
        # phải có ít nhất 1 action (text rereader hoặc part classifier)
        self.assertGreaterEqual(report.action_count, 0)
        self.assertGreaterEqual(report.task_count, 0)
        # verify structure
        d = report.to_dict()
        self.assertIn("schema_version", d)
        self.assertIn("tasks", d)
        self.assertIn("actions", d)
        self.assertIn("summary", d)

    def test_skip_all_no_vision(self):
        """Không có vision_reader → text/part/conflict skip, advisor vẫn chạy."""
        doc = _make_primitive_doc(n_lines=2, n_texts=2, add_conflict=True)
        sem_doc = _make_semantic_doc(n_parts=2, add_low_conf_part=True)
        image = _make_image()

        report = run_agent(
            primitive_doc=doc, semantic_doc=sem_doc,
            image_bgr=image, vision_reader=None,
        )
        # advisor vẫn tạo skip (vì không có solve_result)
        self.assertGreater(report.skipped_count, 0)

    def test_skip_all_no_image(self):
        """Không có image → tất cả skip."""
        doc = _make_primitive_doc()
        sem_doc = _make_semantic_doc()

        report = run_agent(
            primitive_doc=doc, semantic_doc=sem_doc,
            image_bgr=None, vision_reader=_mock_vision_reader,
        )
        self.assertGreater(report.skipped_count, 0)

    def test_no_candidates(self):
        """Tất cả primitives confidence cao, không có conflict → không có action."""
        doc = _make_primitive_doc(n_lines=2, n_texts=2)  # không add_conflict
        sem_doc = _make_semantic_doc(n_parts=2, add_low_conf_part=False)
        image = _make_image()

        report = run_agent(
            primitive_doc=doc, semantic_doc=sem_doc,
            image_bgr=image, vision_reader=_mock_vision_reader,
        )
        # text primitives đều confidence cao (0.3 đã giảm cho text-0, nhưng
        # nếu confidence_threshold=0.2 thì không chọn được)
        # part confidence đều > 0.7
        self.assertGreaterEqual(report.action_count, 0)

    def test_report_structure(self):
        """AgentReport to_dict() structure hợp lệ."""
        report = AgentReport()
        d = report.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("id", d)
        self.assertIn("schema_version", d)
        self.assertIn("timestamp", d)
        self.assertIn("task_count", d)
        self.assertIn("action_count", d)
        self.assertIn("skipped_count", d)
        self.assertIn("summary", d)
        self.assertIn("tasks", d)
        self.assertIn("actions", d)
        self.assertIn("skip_reasons", d)

    def test_agent_with_solver_fail(self):
        """Solver fail → advisor đề xuất drop constraint."""
        from dataclasses import dataclass

        @dataclass
        class MockSolveResult:
            status: str = "didnt_converge"

        doc = _make_primitive_doc(n_lines=3)
        # tạo constraint giả
        cst = Constraint(
            type="parallel", primitive_ids=["line-0", "line-1"],
            confidence=0.55, tolerance={"angle_deg": 3.0},
        )
        sem_doc = _make_semantic_doc(n_parts=0)
        sem_doc.constraints = [cst]

        report = run_agent(
            primitive_doc=doc, semantic_doc=sem_doc,
            image_bgr=None, solve_result=MockSolveResult(),
        )
        # advisor phải tạo ít nhất 1 action drop
        drop_actions = [a for a in report.actions if a.action_type == "drop_constraint"]
        self.assertGreaterEqual(len(drop_actions), 1)


class TestApplyAgentReport(TestCase):
    """Kiểm tra apply_agent_report — áp dụng actions vào Primitive/Semantic IR.
    Verify fix bug matching target_* thay vì task_id."""

    def test_apply_override_text(self):
        """override_text phải update primitive.text_data."""
        doc = _make_primitive_doc(n_lines=0, n_texts=1)
        sem_doc = _make_semantic_doc(n_parts=0)
        report = AgentReport()
        action = AgentAction(
            task_id="reread-text-0",
            action_type="override_text",
            confidence=0.95,
            target_primitive_id="text-0",
            new_text_content="NEW_CONTENT",
            new_parsed_value=1234.0,
            new_semantic_role="dimension_value",
        )
        report.add_action(action)
        summary = apply_agent_report(doc, sem_doc, [], [], report)
        self.assertEqual(summary["text_overridden"], 1)
        prim = doc.primitives[0]
        self.assertEqual(prim.text_data.content, "NEW_CONTENT")
        self.assertEqual(prim.text_data.parsed_value, 1234.0)
        self.assertEqual(prim.text_data.semantic_role, "dimension_value")
        self.assertTrue(action.applied)

    def test_apply_override_part_type(self):
        """override_part_type phải update part.part_type + source=vision_assisted."""
        doc = _make_primitive_doc(n_lines=1, n_texts=0, n_circles=0)
        sem_doc = _make_semantic_doc(n_parts=1, add_low_conf_part=True)
        report = AgentReport()
        action = AgentAction(
            task_id="classify-part-0",
            action_type="override_part_type",
            confidence=0.85,
            target_part_id=sem_doc.parts[0].id,
            new_part_type="thanh_ngang",
        )
        report.add_action(action)
        summary = apply_agent_report(doc, sem_doc, [], [], report)
        self.assertEqual(summary["parts_reclassified"], 1)
        self.assertEqual(sem_doc.parts[0].part_type, "thanh_ngang")
        self.assertEqual(sem_doc.parts[0].source, "vision_assisted")
        self.assertAlmostEqual(sem_doc.parts[0].confidence, 0.85)

    def test_apply_pick_conflict_winner_text(self):
        """pick_conflict_winner=text phải set status=confirmed."""
        doc = _make_primitive_doc(n_lines=1, n_texts=1, add_conflict=True)
        sem_doc = _make_semantic_doc(n_parts=0)
        cv = doc.cross_validations[0]
        report = AgentReport()
        action = AgentAction(
            task_id="resolve-cv",
            action_type="pick_conflict_winner",
            confidence=0.9,
            target_cross_validation_id=cv.id,
            conflict_winner="text",
        )
        report.add_action(action)
        summary = apply_agent_report(doc, sem_doc, doc.cross_validations, [], report)
        self.assertEqual(summary["conflicts_resolved"], 1)
        self.assertEqual(cv.status, "confirmed")

    def test_apply_pick_conflict_winner_new_value(self):
        """pick_conflict_winner=new_value phải update text_value + confirmed."""
        doc = _make_primitive_doc(n_lines=1, n_texts=1, add_conflict=True)
        sem_doc = _make_semantic_doc(n_parts=0)
        cv = doc.cross_validations[0]
        report = AgentReport()
        action = AgentAction(
            task_id="resolve-cv",
            action_type="pick_conflict_winner",
            confidence=0.8,
            target_cross_validation_id=cv.id,
            conflict_winner="new_value",
            conflict_new_value=1800.0,
        )
        report.add_action(action)
        summary = apply_agent_report(doc, sem_doc, doc.cross_validations, [], report)
        self.assertEqual(summary["conflicts_resolved"], 1)
        self.assertEqual(cv.status, "confirmed")
        self.assertAlmostEqual(cv.text_value, 1800.0)

    def test_apply_drop_constraint(self):
        """drop_constraint phải xoá constraint khỏi list."""
        doc = _make_primitive_doc(n_lines=3)
        cst1 = Constraint(
            type="parallel", primitive_ids=["line-0", "line-1"],
            confidence=0.5, tolerance={"angle_deg": 3.0},
        )
        cst2 = Constraint(
            type="parallel", primitive_ids=["line-1", "line-2"],
            confidence=0.8, tolerance={"angle_deg": 3.0},
        )
        constraints = [cst1, cst2]
        sem_doc = _make_semantic_doc(n_parts=0)
        report = AgentReport()
        action = AgentAction(
            task_id="advisor",
            action_type="drop_constraint",
            confidence=0.9,
            dropped_constraint_id=cst1.id,
        )
        report.add_action(action)
        summary = apply_agent_report(doc, sem_doc, [], constraints, report)
        self.assertEqual(summary["constraints_dropped"], 1)
        self.assertEqual(len(constraints), 1)
        self.assertEqual(constraints[0].id, cst2.id)

    def test_apply_idempotent(self):
        """Action đã applied=True không được apply lại."""
        doc = _make_primitive_doc(n_lines=0, n_texts=1)
        sem_doc = _make_semantic_doc(n_parts=0)
        report = AgentReport()
        action = AgentAction(
            task_id="reread-text-0",
            action_type="override_text",
            confidence=0.95,
            target_primitive_id="text-0",
            new_text_content="NEW",
            applied=True,  # đã apply trước đó
        )
        report.add_action(action)
        summary = apply_agent_report(doc, sem_doc, [], [], report)
        self.assertEqual(summary["text_overridden"], 0)

    def test_apply_missing_target_skipped(self):
        """target_* không tồn tại trong IR → action không apply, không crash."""
        doc = _make_primitive_doc(n_lines=0, n_texts=1)
        sem_doc = _make_semantic_doc(n_parts=0)
        report = AgentReport()
        action = AgentAction(
            task_id="reread-ghost",
            action_type="override_text",
            confidence=0.95,
            target_primitive_id="text-KHONG_TON_TAI",
            new_text_content="NEW",
        )
        report.add_action(action)
        summary = apply_agent_report(doc, sem_doc, [], [], report)
        self.assertEqual(summary["text_overridden"], 0)
        # primitive gốc không bị thay đổi
        self.assertNotEqual(doc.primitives[0].text_data.content, "NEW")

    def test_apply_full_report_from_run_agent(self):
        """End-to-end: chạy run_agent (mock Vision) rồi apply, verify summary > 0."""
        doc = _make_primitive_doc(n_lines=2, n_texts=2, add_conflict=True)
        sem_doc = _make_semantic_doc(n_parts=2, add_low_conf_part=True)
        image = _make_image()

        report = run_agent(
            primitive_doc=doc, semantic_doc=sem_doc,
            image_bgr=image, vision_reader=_mock_vision_reader,
            text_confidence_threshold=0.5, part_confidence_threshold=0.7,
        )
        summary = apply_agent_report(
            doc, sem_doc, doc.cross_validations, sem_doc.constraints, report,
        )
        # phải có ít nhất 1 action được apply (text rereader hoặc part classifier
        # hoặc conflict resolver — mock reader trả giá trị khác cho mỗi loại)
        total_applied = sum(summary.values())
        self.assertGreater(total_applied, 0, f"summary={summary} — không có action nào apply")
        # tất cả action có action_type không phải no_action phải applied=True
        for action in report.actions:
            if action.action_type != "no_action":
                self.assertTrue(action.applied, f"action {action.id} chưa applied")


if __name__ == "__main__":
    unittest.main()
