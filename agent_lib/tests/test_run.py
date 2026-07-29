import hashlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from agent_lib.io_utils import save_document
from agent_lib.models import AgentAction, AgentReport
from agent_lib.run import (
    _DEFAULT_OUTPUT_DIR,
    _apply_report_with_approval,
    _json_sha256,
    run,
)

_SHA = "a" * 64


def _report_with_action() -> AgentReport:
    report = AgentReport()
    report.add_action(
        AgentAction(
            task_id="task-1",
            action_type="override_text",
            target_primitive_id="text-1",
            new_text_content="approved text",
            confidence=0.9,
        )
    )
    return report


def _documents():
    return (
        SimpleNamespace(cross_validations=[]),
        SimpleNamespace(constraints=[]),
    )


def test_default_is_advisory_and_does_not_apply_report():
    primitive_doc, semantic_doc = _documents()
    report = _report_with_action()

    with patch("agent_lib.batch_agent.apply_agent_report") as apply_report:
        audit = _apply_report_with_approval(
            primitive_doc,
            semantic_doc,
            report,
            confirm_agent_actions=None,
            approval_reference=None,
        )

    apply_report.assert_not_called()
    assert report.actions[0].applied is False
    assert audit["schema_version"] == "2.0.0"
    assert audit["application_requested"] is False
    assert audit["actions_applied"] is False
    assert audit["action_count"] == 1
    assert audit["approval_reference"] is None
    assert audit["approved_report_sha256"] is None
    assert audit["applied_action_set_sha256"] is None
    assert audit["summary"] is None


@pytest.mark.parametrize(
    ("confirmation", "reference", "report_path", "report_sha256"),
    [
        ("APPLY", None, "report.json", _SHA),
        (None, "review-42", "report.json", _SHA),
        ("YES", "review-42", "report.json", _SHA),
        ("APPLY", "   ", "report.json", _SHA),
        ("APPLY", "review-42", None, _SHA),
        ("APPLY", "review-42", "report.json", None),
        ("APPLY", "review-42", "report.json", "not-a-sha"),
    ],
)
def test_partial_or_invalid_approval_is_rejected_without_mutation(
    confirmation,
    reference,
    report_path,
    report_sha256,
):
    primitive_doc, semantic_doc = _documents()
    report = _report_with_action()

    with patch("agent_lib.batch_agent.apply_agent_report") as apply_report:
        with pytest.raises(ValueError, match="APPLY.*approval reference"):
            _apply_report_with_approval(
                primitive_doc,
                semantic_doc,
                report,
                confirm_agent_actions=confirmation,
                approval_reference=reference,
                approved_report_path=report_path,
                approved_report_sha256=report_sha256,
                approved_source_sha256=_SHA,
                approved_primitive_ir_sha256=_SHA,
                approved_semantic_ir_sha256=_SHA,
            )

    apply_report.assert_not_called()
    assert report.actions[0].applied is False


def test_explicit_approval_applies_report_and_records_reference():
    primitive_doc, semantic_doc = _documents()
    report = _report_with_action()
    expected_summary = {"override_text": 1}

    def mark_applied(*_args):
        report.actions[0].applied = True
        return expected_summary

    with patch(
        "agent_lib.batch_agent.apply_agent_report",
        side_effect=mark_applied,
    ) as apply_report:
        audit = _apply_report_with_approval(
            primitive_doc,
            semantic_doc,
            report,
            confirm_agent_actions="APPLY",
            approval_reference="review-42",
            approved_report_path="reviewed-report.json",
            approved_report_sha256=_SHA,
            approved_source_sha256=_SHA,
            approved_primitive_ir_sha256=_SHA,
            approved_semantic_ir_sha256=_SHA,
        )

    apply_report.assert_called_once_with(
        primitive_doc,
        semantic_doc,
        primitive_doc.cross_validations,
        semantic_doc.constraints,
        report,
    )
    assert audit["schema_version"] == "2.0.0"
    assert audit["application_requested"] is True
    assert audit["actions_applied"] is True
    assert audit["action_count"] == 1
    assert audit["approval_reference"] == "review-42"
    assert audit["approved_report_sha256"] == _SHA
    assert audit["summary"] == expected_summary
    assert audit["applied_action_set_sha256"] == _json_sha256(
        [report.actions[0].to_dict()]
    )


def test_default_output_uses_ignored_runtime_tree():
    assert Path(_DEFAULT_OUTPUT_DIR).parts[-2:] == ("output", "agent_runs")


def test_runner_resolves_again_after_approved_constraint_drop_for_dxf():
    report = AgentReport()
    report.add_action(
        AgentAction(
            task_id="task-1",
            action_type="drop_constraint",
            dropped_constraint_id="constraint-1",
            confidence=0.9,
        )
    )
    primitive_doc = SimpleNamespace(primitives=[], cross_validations=[])
    semantic_doc = SimpleNamespace(
        parts=[],
        constraints=[SimpleNamespace(id="constraint-1")],
    )
    solve_results = [
        SimpleNamespace(status="failed", solved_primitives={"old": "geometry"}),
        SimpleNamespace(status="okay", solved_primitives={"new": "geometry"}),
    ]
    built_with = {}

    def capture_build(*_args, **kwargs):
        built_with["solved_primitives"] = kwargs["solved_primitives"]
        return SimpleNamespace(entity_count=1, component_count=0)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        image = root / "source.png"
        primitive_ir = root / "primitive.json"
        semantic_ir = root / "semantic.json"
        approved_report = root / "approved-report.json"
        for path in (image, primitive_ir, semantic_ir):
            path.write_bytes(b"input")
        save_document(report, str(approved_report))
        report_sha256 = hashlib.sha256(approved_report.read_bytes()).hexdigest()

        with (
            patch("cv2.imread", return_value=np.zeros((2, 2, 3), dtype=np.uint8)),
            patch(
                "semantic_ir_lib.io_utils.load_primitive_ir_document",
                return_value=primitive_doc,
            ),
            patch(
                "semantic_ir_lib.io_utils.load_semantic_ir_document",
                return_value=semantic_doc,
            ),
            patch(
                "semantic_ir_lib.constraint_pruning.prune_constraints",
                side_effect=lambda constraints: SimpleNamespace(kept=list(constraints)),
            ),
            patch(
                "semantic_ir_lib.constraint_solving.solve_constraints",
                side_effect=solve_results,
            ) as solve,
            patch("dxf_builder_lib.builder.build_dxf", side_effect=capture_build),
            patch(
                "dxf_builder_lib.reviewer.review_dxf",
                return_value=SimpleNamespace(passed=True, checked_count=1),
            ),
        ):
            exit_code = run(
                image_path=str(image),
                primitive_ir_path=str(primitive_ir),
                semantic_ir_path=str(semantic_ir),
                output_dir=str(root / "output"),
                confirm_agent_actions="APPLY",
                agent_action_approval="review-42",
                approved_agent_report=str(approved_report),
                approved_agent_report_sha256=report_sha256,
                approved_source_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                approved_primitive_ir_sha256=hashlib.sha256(
                    primitive_ir.read_bytes()
                ).hexdigest(),
                approved_semantic_ir_sha256=hashlib.sha256(
                    semantic_ir.read_bytes()
                ).hexdigest(),
            )

        assert exit_code == 0
        assert solve.call_count == 2
        assert built_with["solved_primitives"] == {"new": "geometry"}
        assert semantic_doc.constraints == []
