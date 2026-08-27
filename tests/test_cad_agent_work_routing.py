from __future__ import annotations

import pytest

from cad_agent.work_routing import WorkRoutingError, classify_work


def _action(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "requires_unpushed_local_state": False,
        "requires_windows_toolchain": False,
        "requires_autocad": False,
        "requires_com_rot_ui": False,
        "requires_netload": False,
        "requires_live_file_ipc": False,
        "requires_owner_decision": False,
        "requires_private_secret": False,
        "requires_irreversible_approval": False,
        "web_capable_analysis": True,
        "preferred_executor": "SOL",
        "reason": "GitHub and reasoning only",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, "WEB_CAPABLE"),
        ({"preferred_executor": "LUNA"}, "WEB_CAPABLE"),
        (
            {
                "requires_unpushed_local_state": True,
                "web_capable_analysis": False,
                "reason": "unpushed local checkout bytes required",
            },
            "LOCAL_REPO_REQUIRED",
        ),
        (
            {
                "requires_windows_toolchain": True,
                "web_capable_analysis": False,
                "reason": "Windows-only build evidence required",
            },
            "LOCAL_WINDOWS_REQUIRED",
        ),
        (
            {
                "requires_autocad": True,
                "web_capable_analysis": False,
                "reason": "AutoCAD Mechanical real-surface evidence required",
            },
            "LOCAL_AUTOCAD_REQUIRED",
        ),
        (
            {
                "requires_com_rot_ui": True,
                "web_capable_analysis": False,
                "reason": "COM/ROT/UI evidence required",
            },
            "LOCAL_AUTOCAD_REQUIRED",
        ),
        (
            {
                "requires_netload": True,
                "web_capable_analysis": False,
                "reason": "NETLOAD required",
            },
            "LOCAL_AUTOCAD_REQUIRED",
        ),
        (
            {
                "requires_live_file_ipc": True,
                "web_capable_analysis": False,
                "reason": "live File-IPC required",
            },
            "LOCAL_AUTOCAD_REQUIRED",
        ),
        (
            {
                "requires_owner_decision": True,
                "web_capable_analysis": False,
                "reason": "owner product preference required",
            },
            "HUMAN_ONLY",
        ),
    ],
)
def test_routing_matrix(overrides: dict[str, object], expected: str) -> None:
    result = classify_work(_action(**overrides))
    assert result["classification"] == expected
    assert result["reason"]
    assert result["required_evidence_surface"]


def test_human_only_precedes_local_machine_need() -> None:
    result = classify_work(
        _action(
            requires_owner_decision=True,
            requires_autocad=True,
            web_capable_analysis=False,
            reason="owner approval precedes AutoCAD execution",
        )
    )
    assert result["classification"] == "HUMAN_ONLY"


def test_local_classification_requires_matching_capability_flag() -> None:
    with pytest.raises(WorkRoutingError, match="web_capable_analysis"):
        classify_work(
            _action(
                web_capable_analysis=False,
                preferred_executor="LUNA",
                reason="preference is not capability evidence",
            )
        )


def test_rejects_unknown_fields() -> None:
    action = _action()
    action["token_saving_mode"] = True
    with pytest.raises(WorkRoutingError, match="unexpected"):
        classify_work(action)
