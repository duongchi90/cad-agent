from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "chatgpt-local-executor.yml"
EXECUTOR = ROOT / "scripts" / "local-executor.ps1"


def test_local_executor_has_no_arbitrary_command_surface() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    executor = EXECUTOR.read_text(encoding="utf-8")

    assert "      command:" not in workflow
    assert "Invoke-Expression" not in workflow
    assert "Invoke-Expression" not in executor
    assert "iex " not in workflow.lower()
    assert "iex " not in executor.lower()
