from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.local_executor_event import find_watchdog_alert, gate_event, parse_dispatch_comment

OWNER = "duongchi90"
SHA = "1" * 40
REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_EXECUTOR_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "chatgpt-local-executor.yml"
WATCHDOG_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "chatgpt-local-executor-watchdog.yml"


def dispatch_body(
    seq: int = 295,
    action: str = "VERIFY",
    branch: str = "infra/test",
    sha: str = SHA,
) -> str:
    return "\n".join(
        [
            "SOL AUTHORITY",
            "LOCAL_EXECUTOR_DISPATCH_V1",
            f"CONTROL_SEQ={seq}",
            f"LOCAL_ACTION={action}",
            f"LOCAL_EXPECTED_BRANCH={branch}",
            f"LOCAL_EXPECTED_SHA={sha}",
        ]
    )


class LocalExecutorEventTests(unittest.TestCase):
    def test_accepts_strict_owner_dispatch_on_issue_131(self) -> None:
        request = parse_dispatch_comment(
            dispatch_body(),
            issue_number=131,
            author_login=OWNER,
            repository_owner=OWNER,
        )
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.control_seq, 295)
        self.assertEqual(request.action, "VERIFY")
        self.assertEqual(request.expected_branch, "infra/test")
        self.assertEqual(request.expected_sha, SHA)

    def test_accepts_active_successor_ledger_and_returns_trusted_source_issue(self) -> None:
        body = dispatch_body(seq=339) + "\nCONTROL_ISSUE_NUMBER=131"
        request = parse_dispatch_comment(
            body,
            issue_number=294,
            author_login=OWNER,
            repository_owner=OWNER,
        )
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.control_issue_number, 294)

        outputs = gate_event(
            "issue_comment",
            {
                "issue": {"number": 294},
                "comment": {
                    "id": 3390,
                    "body": body,
                    "user": {"login": OWNER},
                },
            },
            repository_owner=OWNER,
            run_id="339",
        )
        self.assertEqual(outputs["should_run"], "true")
        self.assertEqual(outputs["control_issue_number"], "294")

    def test_rejects_foreign_stale_or_wrong_issue_dispatches(self) -> None:
        cases = [
            dict(issue_number=130, author_login=OWNER, body=dispatch_body()),
            dict(issue_number=295, author_login=OWNER, body=dispatch_body()),
            dict(
                issue_number=294,
                author_login=OWNER,
                body=dispatch_body() + "\nLOCAL_EXECUTOR_TERMINAL_V1",
            ),
            dict(issue_number=294, author_login="github-actions[bot]", body=dispatch_body()),
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertIsNone(
                    parse_dispatch_comment(
                        case["body"],
                        issue_number=case["issue_number"],
                        author_login=case["author_login"],
                        repository_owner=OWNER,
                    )
                )

    def test_rejects_untrusted_or_malformed_dispatches(self) -> None:
        cases = [
            dict(issue_number=130, author_login=OWNER, body=dispatch_body()),
            dict(issue_number=131, author_login="someone-else", body=dispatch_body()),
            dict(issue_number=131, author_login=OWNER, body=dispatch_body(action="SHELL")),
            dict(
                issue_number=131,
                author_login=OWNER,
                body=dispatch_body() + "\nLOCAL_ACTION=STATE_CHECK",
            ),
            dict(issue_number=131, author_login=OWNER, body=dispatch_body(sha="abc")),
            dict(
                issue_number=131,
                author_login=OWNER,
                body=dispatch_body(branch="bad branch"),
            ),
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertIsNone(
                    parse_dispatch_comment(
                        case["body"],
                        issue_number=case["issue_number"],
                        author_login=case["author_login"],
                        repository_owner=OWNER,
                    )
                )

    def test_watchdog_alerts_once_after_12_minutes_without_terminal(self) -> None:
        comments = [
            {
                "id": 100,
                "body": dispatch_body(),
                "created_at": "2026-08-27T14:00:00Z",
                "user": {"login": OWNER},
            },
            {
                "id": 101,
                "body": "\n".join(
                    [
                        "LOCAL_EXECUTOR_ACK_V1",
                        "LOCAL_DISPATCH_COMMENT_ID=100",
                        "CONTROL_SEQ=295",
                    ]
                ),
                "created_at": "2026-08-27T14:01:00Z",
                "user": {"login": "github-actions[bot]"},
            },
        ]
        now = datetime(2026, 8, 27, 14, 13, 1, tzinfo=timezone.utc)
        alert = find_watchdog_alert(
            comments,
            now=now,
            issue_number=131,
            repository_owner=OWNER,
            threshold_seconds=720,
        )
        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertEqual(alert["dispatch_comment_id"], "100")
        self.assertEqual(alert["state"], "ACK_STALLED")

        comments.append(
            {
                "id": 102,
                "body": "\n".join(
                    [
                        "LOCAL_EXECUTOR_WATCHDOG_V1",
                        "LOCAL_DISPATCH_COMMENT_ID=100",
                        "CONTROL_SEQ=295",
                    ]
                ),
                "created_at": "2026-08-27T14:13:02Z",
                "user": {"login": "github-actions[bot]"},
            }
        )
        self.assertIsNone(
            find_watchdog_alert(
                comments,
                now=now,
                issue_number=131,
                repository_owner=OWNER,
                threshold_seconds=720,
            )
        )

    def test_watchdog_ignores_completed_dispatch(self) -> None:
        comments = [
            {
                "id": 100,
                "body": dispatch_body(),
                "created_at": "2026-08-27T14:00:00Z",
                "user": {"login": OWNER},
            },
            {
                "id": 103,
                "body": "\n".join(
                    [
                        "LOCAL_EXECUTOR_TERMINAL_V1",
                        "LOCAL_DISPATCH_COMMENT_ID=100",
                        "CONTROL_SEQ=295",
                        "RESULT=success",
                    ]
                ),
                "created_at": "2026-08-27T14:05:00Z",
                "user": {"login": "github-actions[bot]"},
            },
        ]
        now = datetime(2026, 8, 27, 15, 0, 0, tzinfo=timezone.utc)
        self.assertIsNone(
            find_watchdog_alert(
                comments,
                now=now,
                issue_number=131,
                repository_owner=OWNER,
                threshold_seconds=720,
            )
        )

    def test_untrusted_terminal_marker_cannot_suppress_watchdog(self) -> None:
        comments = [
            {
                "id": 200,
                "body": dispatch_body(seq=400),
                "created_at": "2026-08-27T14:00:00Z",
                "user": {"login": OWNER},
            },
            {
                "id": 201,
                "body": "\n".join(
                    [
                        "LOCAL_EXECUTOR_TERMINAL_V1",
                        "LOCAL_DISPATCH_COMMENT_ID=200",
                        "CONTROL_SEQ=400",
                        "RESULT=success",
                    ]
                ),
                "created_at": "2026-08-27T14:01:00Z",
                "user": {"login": "untrusted-commenter"},
            },
        ]
        alert = find_watchdog_alert(
            comments,
            now=datetime(2026, 8, 27, 14, 13, 0, tzinfo=timezone.utc),
            issue_number=131,
            repository_owner=OWNER,
            threshold_seconds=720,
        )
        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertEqual(alert["dispatch_comment_id"], "200")
        self.assertEqual(alert["state"], "NO_ACK")

    def test_watchdog_alerts_for_active_successor_ledger(self) -> None:
        alert = find_watchdog_alert(
            [
                {
                    "id": 29400,
                    "body": dispatch_body(seq=339),
                    "created_at": "2026-08-27T14:00:00Z",
                    "user": {"login": OWNER},
                }
            ],
            now=datetime(2026, 8, 27, 14, 13, 0, tzinfo=timezone.utc),
            issue_number=294,
            repository_owner=OWNER,
            threshold_seconds=720,
        )
        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertEqual(alert["dispatch_comment_id"], "29400")
        self.assertEqual(alert["control_seq"], 339)

    def test_workflows_route_status_to_the_dispatch_source_ledger(self) -> None:
        executor_workflow = LOCAL_EXECUTOR_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("control_issue_number", executor_workflow)
        self.assertIn("issues/${CONTROL_ISSUE_NUMBER}/comments", executor_workflow)
        self.assertNotIn("github.event.issue.number == 131", executor_workflow)
        self.assertNotIn("issues/131/comments", executor_workflow)

        watchdog_workflow = WATCHDOG_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("for issue_number in 131 294", watchdog_workflow)
        self.assertIn("issues/${issue_number}/comments", watchdog_workflow)
        self.assertIn("control_issue_number", watchdog_workflow)
        self.assertNotIn("issues/131/comments", watchdog_workflow)

    def test_issue_comment_event_yields_dispatch_outputs(self) -> None:
        event = {
            "issue": {"number": 131},
            "comment": {
                "id": 555,
                "body": dispatch_body(
                    seq=301,
                    action="STATE_CHECK",
                    branch="main",
                ),
                "user": {"login": OWNER},
            },
        }
        outputs = gate_event(
            "issue_comment",
            event,
            repository_owner=OWNER,
            run_id="77",
        )
        self.assertEqual(outputs["should_run"], "true")
        self.assertEqual(outputs["dispatch_comment_id"], "555")
        self.assertEqual(outputs["control_seq"], "301")
        self.assertEqual(outputs["action"], "STATE_CHECK")
        self.assertEqual(outputs["expected_branch"], "main")
        self.assertEqual(outputs["expected_sha"], SHA)

    def test_manual_event_is_strictly_allowlisted(self) -> None:
        valid = {
            "inputs": {
                "control_seq": "302",
                "local_action": "VERIFY",
                "expected_branch": "infra/local-executor-event",
                "expected_sha": SHA,
            }
        }
        outputs = gate_event(
            "workflow_dispatch",
            valid,
            repository_owner=OWNER,
            run_id="88",
        )
        self.assertEqual(outputs["should_run"], "true")
        self.assertEqual(outputs["dispatch_comment_id"], "manual-88")

        invalid = {"inputs": {**valid["inputs"], "local_action": "SHELL"}}
        self.assertEqual(
            gate_event(
                "workflow_dispatch",
                invalid,
                repository_owner=OWNER,
                run_id="89",
            )["should_run"],
            "false",
        )


if __name__ == "__main__":
    unittest.main()
