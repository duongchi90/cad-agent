from __future__ import annotations

import json
from pathlib import Path

import pytest

from cad_agent.failure_registry import (
    FailureRegistryError,
    match_failure_family,
    recommended_probe,
    validate_failure_family,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "operating-model"
    / "windows-lisp-trigger-execution-boundary.json"
)


def _family() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_round_trip_and_probe_selection() -> None:
    family = validate_failure_family(_family())
    assert family["family_id"] == "WINDOWS_LISP_TRIGGER_EXECUTION_BOUNDARY"
    assert recommended_probe(family) == (
        "pytest:mcp_integration_lib/tests/test_file_ipc_windows_trigger.py"
    )


def test_exact_known_signature_set_matches_family() -> None:
    family = validate_failure_family(_family())
    matched = match_failure_family(family["required_signatures"], [family])
    assert matched == family


def test_missing_required_signature_does_not_match() -> None:
    family = validate_failure_family(_family())
    signatures = list(family["required_signatures"])[1:]
    assert match_failure_family(signatures, [family]) is None


def test_unknown_cross_layer_signature_does_not_get_absorbed() -> None:
    family = validate_failure_family(_family())
    signatures = list(family["required_signatures"]) + ["AUTOCAD_DATABASE_CORRUPTION"]
    assert match_failure_family(signatures, [family]) is None


def test_allowed_additional_signature_can_match_when_explicitly_declared() -> None:
    family = _family()
    family["allowed_additional_signatures"] = ["POSTMESSAGE_RETURN_ZERO"]
    validated = validate_failure_family(family)
    signatures = list(validated["required_signatures"]) + ["POSTMESSAGE_RETURN_ZERO"]
    assert match_failure_family(signatures, [validated]) == validated


def test_rejects_duplicate_signatures() -> None:
    family = _family()
    family["required_signatures"] = [
        "EXACT_HWND_PID_BINDING_MISSING",
        "EXACT_HWND_PID_BINDING_MISSING",
    ]
    with pytest.raises(FailureRegistryError, match="unique"):
        validate_failure_family(family)


def test_rejects_unknown_fields() -> None:
    family = _family()
    family["auto_execute"] = True
    with pytest.raises(FailureRegistryError, match="unexpected"):
        validate_failure_family(family)
