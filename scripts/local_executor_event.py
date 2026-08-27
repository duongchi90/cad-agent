from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

DISPATCH_MARKER = "LOCAL_EXECUTOR_DISPATCH_V1"
ACK_MARKER = "LOCAL_EXECUTOR_ACK_V1"
TERMINAL_MARKER = "LOCAL_EXECUTOR_TERMINAL_V1"
WATCHDOG_MARKER = "LOCAL_EXECUTOR_WATCHDOG_V1"
CONTROL_ISSUE_NUMBER = 131
ALLOWED_ACTIONS = frozenset({"STATE_CHECK", "VERIFY"})
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class DispatchRequest:
    control_seq: int
    action: str
    expected_branch: str
    expected_sha: str


def _field_values(body: str, key: str) -> list[str]:
    prefix = f"{key}="
    return [
        line[len(prefix) :].strip()
        for line in body.splitlines()
        if line.strip().startswith(prefix)
    ]


def _single_field(body: str, key: str) -> str | None:
    values = _field_values(body, key)
    if len(values) != 1 or not values[0]:
        return None
    return values[0]


def _valid_branch(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if (
        not _BRANCH_RE.fullmatch(value)
        or ".." in value
        or value.startswith("/")
        or value.endswith("/")
    ):
        return None
    return value


def _valid_sha(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if _SHA_RE.fullmatch(value) else None


def parse_dispatch_comment(
    body: str,
    *,
    issue_number: int,
    author_login: str,
    repository_owner: str,
) -> DispatchRequest | None:
    if issue_number != CONTROL_ISSUE_NUMBER or author_login != repository_owner:
        return None
    if sum(1 for line in body.splitlines() if line.strip() == DISPATCH_MARKER) != 1:
        return None

    seq_text = _single_field(body, "CONTROL_SEQ")
    action = _single_field(body, "LOCAL_ACTION")
    branch = _single_field(body, "LOCAL_EXPECTED_BRANCH")
    sha = _single_field(body, "LOCAL_EXPECTED_SHA")
    if None in {seq_text, action, branch, sha}:
        return None

    assert seq_text is not None
    assert action is not None
    assert branch is not None
    assert sha is not None

    if not seq_text.isdecimal() or int(seq_text) <= 0:
        return None
    if action not in ALLOWED_ACTIONS:
        return None
    branch = _valid_branch(branch)
    sha = _valid_sha(sha)
    if branch is None or sha is None:
        return None

    return DispatchRequest(
        control_seq=int(seq_text),
        action=action,
        expected_branch=branch,
        expected_sha=sha,
    )


def gate_event(
    event_name: str,
    event: dict[str, Any],
    *,
    repository_owner: str,
    run_id: str,
) -> dict[str, str]:
    ignored = {
        "should_run": "false",
        "dispatch_comment_id": "",
        "control_seq": "",
        "action": "",
        "expected_branch": "",
        "expected_sha": "",
    }

    if event_name == "issue_comment":
        issue = event.get("issue")
        comment = event.get("comment")
        if not isinstance(issue, dict) or not isinstance(comment, dict):
            return ignored
        user = comment.get("user")
        if not isinstance(user, dict):
            return ignored
        issue_number = issue.get("number")
        comment_id = comment.get("id")
        if not isinstance(issue_number, int) or not isinstance(comment_id, int):
            return ignored

        request = parse_dispatch_comment(
            str(comment.get("body", "")),
            issue_number=issue_number,
            author_login=str(user.get("login", "")),
            repository_owner=repository_owner,
        )
        if request is None:
            return ignored
        return {
            "should_run": "true",
            "dispatch_comment_id": str(comment_id),
            "control_seq": str(request.control_seq),
            "action": request.action,
            "expected_branch": request.expected_branch,
            "expected_sha": request.expected_sha,
        }

    if event_name == "workflow_dispatch":
        inputs = event.get("inputs")
        if not isinstance(inputs, dict):
            return ignored
        seq_text = str(inputs.get("control_seq", "")).strip()
        action = str(inputs.get("local_action", "")).strip()
        branch = _valid_branch(inputs.get("expected_branch"))
        sha = _valid_sha(inputs.get("expected_sha"))
        if (
            not seq_text.isdecimal()
            or int(seq_text) <= 0
            or action not in ALLOWED_ACTIONS
            or branch is None
            or sha is None
        ):
            return ignored
        return {
            "should_run": "true",
            "dispatch_comment_id": f"manual-{run_id}",
            "control_seq": seq_text,
            "action": action,
            "expected_branch": branch,
            "expected_sha": sha,
        }

    return ignored


def _parse_created_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _comment_dispatch_id(body: str, marker: str) -> str | None:
    if sum(1 for line in body.splitlines() if line.strip() == marker) != 1:
        return None
    return _single_field(body, "LOCAL_DISPATCH_COMMENT_ID")


def find_watchdog_alert(
    comments: Iterable[dict[str, Any]],
    *,
    now: datetime,
    issue_number: int,
    repository_owner: str,
    threshold_seconds: int = 720,
) -> dict[str, object] | None:
    if issue_number != CONTROL_ISSUE_NUMBER or threshold_seconds <= 0:
        return None

    normalized_now = now.astimezone(timezone.utc)
    rows = list(comments)
    dispatches: list[tuple[int, datetime, DispatchRequest]] = []
    for comment in rows:
        body = comment.get("body")
        user = comment.get("user")
        if not isinstance(body, str) or not isinstance(user, dict):
            continue
        created_at = _parse_created_at(comment.get("created_at"))
        comment_id = comment.get("id")
        if created_at is None or not isinstance(comment_id, int):
            continue
        request = parse_dispatch_comment(
            body,
            issue_number=issue_number,
            author_login=str(user.get("login", "")),
            repository_owner=repository_owner,
        )
        if request is not None:
            dispatches.append((comment_id, created_at, request))

    for dispatch_id, created_at, request in sorted(
        dispatches,
        key=lambda item: item[0],
        reverse=True,
    ):
        dispatch_token = str(dispatch_id)
        ack_time: datetime | None = None
        completed = False
        already_alerted = False

        for comment in rows:
            body = comment.get("body")
            if not isinstance(body, str):
                continue
            if _comment_dispatch_id(body, TERMINAL_MARKER) == dispatch_token:
                completed = True
                break
            if _comment_dispatch_id(body, WATCHDOG_MARKER) == dispatch_token:
                already_alerted = True
            if _comment_dispatch_id(body, ACK_MARKER) == dispatch_token:
                timestamp = _parse_created_at(comment.get("created_at"))
                if timestamp is not None and (
                    ack_time is None or timestamp > ack_time
                ):
                    ack_time = timestamp

        if completed or already_alerted:
            continue

        anchor = ack_time or created_at
        age_seconds = int((normalized_now - anchor).total_seconds())
        if age_seconds < threshold_seconds:
            continue
        return {
            "dispatch_comment_id": dispatch_token,
            "control_seq": request.control_seq,
            "state": "ACK_STALLED" if ack_time is not None else "NO_ACK",
            "age_seconds": age_seconds,
        }

    return None
