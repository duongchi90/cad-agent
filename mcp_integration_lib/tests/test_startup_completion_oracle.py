from types import SimpleNamespace

import pytest

from mcp_integration_lib.mcp_client import (
    MCPTimeoutError,
    WindowsAutoCADStartTabSession,
    _START_TAB_BOOTSTRAP_COMPLETION_TOKEN,
    _START_TAB_EVALUATOR_ENTRY_TOKEN,
    _start_tab_completion_marker_expression,
)


def _exercise(mode: str, root):
    dispatcher = root / "mcp_dispatch.lsp"
    dispatcher.write_text("; test dispatcher\n", encoding="utf-8")
    session = WindowsAutoCADStartTabSession(
        "C:/Program Files/Autodesk/AutoCAD 2027/acad.exe",
        str(root),
        bootstrap_lisp_path=str(dispatcher),
        ipc_root=str(root),
        timeout_s=0.01,
        poll_interval_s=0,
    )
    marker = root / "completion.marker"
    evaluator_entry_marker = root / "evaluator-entry.marker"
    alternate_marker = root / "alternate.marker"
    session._completion_marker_path = marker
    session._evaluator_entry_marker_path = evaluator_entry_marker
    load_expression = session._dispatcher_load_expression(
        evaluator_entry_marker_path=evaluator_entry_marker
    )
    marker_expression = _start_tab_completion_marker_expression(marker)
    observation = {
        "load_expression_exact": (
            str(root).replace("\\", "/") in load_expression
            and str(dispatcher).replace("\\", "/") in load_expression
        ),
        "marker_expression_exact": (
            str(marker).replace("\\", "/") in marker_expression
            and _START_TAB_BOOTSTRAP_COMPLETION_TOKEN in marker_expression
        ),
        "load_attempted": False,
        "load_consumed": False,
        "marker_write_attempted": False,
        "marker_write_succeeded": False,
    }

    def raw_lisp_trigger(expression: str) -> None:
        if expression == load_expression:
            observation["load_attempted"] = True
            if mode == "NOT_EVALUATED":
                raise RuntimeError("simulated evaluator did not enter")
            evaluator_entry_marker.write_text(
                _START_TAB_EVALUATOR_ENTRY_TOKEN + "\n",
                encoding="ascii",
            )
            observation["load_consumed"] = True
            return
        if expression != marker_expression:
            raise AssertionError("unexpected bootstrap expression")
        observation["marker_write_attempted"] = True
        if mode == "EVALUATED_MARKER_NOT_WRITTEN":
            return
        target = alternate_marker if mode == "MARKER_WRITTEN_NOT_OBSERVED" else marker
        target.write_text(
            _START_TAB_BOOTSTRAP_COMPLETION_TOKEN + "\n",
            encoding="ascii",
        )
        observation["marker_write_succeeded"] = True

    error = None
    try:
        session._run_process_bound_runtime_bootstrap(
            SimpleNamespace(raw_lisp_trigger=raw_lisp_trigger)
        )
    except (MCPTimeoutError, RuntimeError) as exc:
        error = exc

    observation["observer_exact_path_token"] = (
        marker.is_file()
        and marker.read_text(encoding="ascii").strip()
        == _START_TAB_BOOTSTRAP_COMPLETION_TOKEN
    )
    if not observation["load_consumed"]:
        observation["classification"] = "NOT_EVALUATED"
    elif not observation["marker_write_succeeded"]:
        observation["classification"] = "EVALUATED_MARKER_NOT_WRITTEN"
    elif not observation["observer_exact_path_token"]:
        observation["classification"] = "MARKER_WRITTEN_NOT_OBSERVED"
    else:
        observation["classification"] = "EVALUATED_AND_OBSERVED"
    return observation, error


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("NOT_EVALUATED", "NOT_EVALUATED"),
        ("EVALUATED_MARKER_NOT_WRITTEN", "EVALUATED_MARKER_NOT_WRITTEN"),
        ("MARKER_WRITTEN_NOT_OBSERVED", "MARKER_WRITTEN_NOT_OBSERVED"),
        ("EVALUATED_AND_OBSERVED", "EVALUATED_AND_OBSERVED"),
    ],
)
def test_startup_completion_oracle_classifies_each_boundary(
    tmp_path, mode, expected
):
    observation, error = _exercise(mode, tmp_path)

    assert observation["load_expression_exact"]
    assert observation["marker_expression_exact"]
    assert observation["classification"] == expected
    if mode == "EVALUATED_AND_OBSERVED":
        assert error is None
        assert observation["observer_exact_path_token"]
    elif mode != "NOT_EVALUATED":
        assert isinstance(error, MCPTimeoutError)
