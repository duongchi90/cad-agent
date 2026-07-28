from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent_lib.models import AgentAction, AgentReport
from agent_lib.run import _apply_report_with_approval


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
    assert audit == {
        "schema_version": "1.0.0",
        "application_requested": False,
        "actions_applied": False,
        "action_count": 1,
        "approval_reference": None,
        "summary": None,
    }


@pytest.mark.parametrize(
    ("confirmation", "reference"),
    [
        ("APPLY", None),
        (None, "review-42"),
        ("YES", "review-42"),
        ("APPLY", "   "),
    ],
)
def test_partial_or_invalid_approval_is_rejected_without_mutation(
    confirmation,
    reference,
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
        )

    apply_report.assert_called_once_with(
        primitive_doc,
        semantic_doc,
        primitive_doc.cross_validations,
        semantic_doc.constraints,
        report,
    )
    assert audit == {
        "schema_version": "1.0.0",
        "application_requested": True,
        "actions_applied": True,
        "action_count": 1,
        "approval_reference": "review-42",
        "summary": expected_summary,
    }
