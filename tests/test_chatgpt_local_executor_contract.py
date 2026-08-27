from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "chatgpt-local-executor.yml"
EXECUTOR = ROOT / "scripts" / "local-executor.ps1"


def _texts() -> tuple[str, str]:
    return (
        WORKFLOW.read_text(encoding="utf-8"),
        EXECUTOR.read_text(encoding="utf-8"),
    )


def test_local_executor_has_no_arbitrary_command_surface() -> None:
    workflow, executor = _texts()

    assert "      command:" not in workflow
    assert "Invoke-Expression" not in workflow
    assert "Invoke-Expression" not in executor
    assert "iex " not in workflow.lower()
    assert "iex " not in executor.lower()


def test_dispatch_contract_is_closed_and_required() -> None:
    workflow, _ = _texts()

    assert "      expected_branch:" in workflow
    assert "      expected_sha:" in workflow
    assert "      mission_envelope_json:" in workflow
    for field in ("expected_branch", "expected_sha", "mission_envelope_json"):
        start = workflow.index(f"      {field}:")
        tail = workflow[start:]
        next_field = tail.find("\n      ", 1)
        block = tail if next_field == -1 else tail[:next_field]
        assert "required: true" in block
        assert "required: false" not in block


def test_mission_json_crosses_workflow_boundary_via_environment_only() -> None:
    workflow, _ = _texts()

    assert "CAD_AGENT_MISSION_ENVELOPE_JSON: ${{ inputs.mission_envelope_json }}" in workflow
    assert "CAD_AGENT_EXPECTED_BRANCH: ${{ inputs.expected_branch }}" in workflow
    assert "CAD_AGENT_EXPECTED_SHA: ${{ inputs.expected_sha }}" in workflow
    assert "$env:CAD_AGENT_MISSION_ENVELOPE_JSON" in workflow
    assert "$env:RUNNER_TEMP" in workflow
    assert "WriteAllText" in workflow
    assert 'Join-Path $env:RUNNER_TEMP "cad-agent-mission-envelope.json"' in workflow

    expression = "${{ inputs.mission_envelope_json }}"
    expression_lines = [line.strip() for line in workflow.splitlines() if expression in line]
    assert expression_lines == [
        "CAD_AGENT_MISSION_ENVELOPE_JSON: ${{ inputs.mission_envelope_json }}"
    ]


def test_workflow_invokes_only_typed_local_executor_boundary() -> None:
    workflow, _ = _texts()

    assert ".\\scripts\\local-executor.ps1" in workflow
    assert "-MissionEnvelopePath" in workflow
    assert "-ExpectedBranch" in workflow
    assert "-ExpectedSha" in workflow
    assert "github.event.inputs.command" not in workflow


def test_local_executor_uses_exact_identity_and_sealed_validation() -> None:
    workflow, executor = _texts()

    assert "StartsWith" not in workflow
    assert "StartsWith" not in executor
    assert "[Parameter(Mandatory = $true)]" in executor
    assert "$MissionEnvelopePath" in executor
    assert "$ExpectedBranch" in executor
    assert "$ExpectedSha" in executor
    assert "BRANCH_MISMATCH" in executor
    assert "HEAD_SHA_MISMATCH" in executor
    assert "validate_local_execution_envelope" in executor
    assert "active_pr_head_sha" in executor
    assert "RUNNER_TEMP" in executor


def test_local_executor_emits_non_authoritative_terminal_and_fixed_verify_path() -> None:
    _, executor = _texts()

    assert "mission-terminal.json" in executor
    assert "build_local_mission_terminal" in executor
    assert "bootstrap.ps1" in executor
    assert "verify.ps1" in executor
    assert '"NOT_RUN"' in executor
    assert "control_seq" not in executor.lower()
    assert "merge_authority" in executor
    assert "publication_authority" in executor
