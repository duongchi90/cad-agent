from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Callable

import pytest

import cad_agent.vision_handoff as vision_handoff
from agent_lib.codex_worker import (
    AdapterRequest,
    CodexWorkerError,
    CodexWorkerSession,
    LazyOfficialSdkAdapter,
    fork_codex_worker,
    resume_codex_worker,
)
from agent_lib.tests.test_codex_worker import (
    SENTINEL,
    _FakeAdapter,
    _FakeProcessBoundary,
    _assert_failed,
    _fixture,
    _fresh_target,
    _start,
)
from tests.test_vision_handoff import NOW


WORKER_SOURCE = Path(__file__).parents[1] / "agent_lib" / "codex_worker.py"
HANDOFF_SOURCE = Path(__file__).parents[1] / "cad_agent" / "vision_handoff.py"
GAP = "WORKER_SDK_ATTESTATION_GAP"
MISMATCH = "WORKER_AUTHORITY_MISMATCH"
_UNSET = object()


def _observation(authority: object, binding: object, worker_context: object) -> dict[str, object]:
    policy = authority.provider_policy
    sandbox = worker_context.sandbox_policy
    return {
        "thread_id": binding.thread_id,
        "instruction_sources": [dict(item) for item in binding.instruction_source_identity],
        "approval_mode": policy["approval_mode"],
        "experimental_api": policy["experimental_api"],
        "model_identity": binding.model_config_identity["model_identity"],
        "config_sha256": binding.model_config_identity["config_sha256"],
        "adapter_version": binding.adapter_version,
        "sandbox_write_policy": sandbox["write_policy"],
        "cwd": sandbox["cwd"],
        "writable_roots": list(sandbox["roots"]),
        "full_access": False,
        "auto_review": False,
        "approval_escalation": False,
        "transport": "official_sdk",
        "alternate_transports": [],
    }


def _validator() -> Callable[..., object]:
    validator = getattr(vision_handoff, "validate_provider_effective_attestation", None)
    assert callable(validator), "Task-5 provider effective attestation validator is missing"
    return validator


def _validate(fx: object, observed: object) -> None:
    _validator()(
        observed,
        binding=fx.binding,
        authority_context=fx.authority,
        worker_context=fx.worker_context,
    )


def _assert_validator_rejects(fx: object, observed: object) -> None:
    with pytest.raises(vision_handoff.VisionHandoffError) as caught:
        _validate(fx, observed)
    assert SENTINEL not in str(caught.value)
    assert SENTINEL not in repr(caught.value)


class _AttestingBoundary(_FakeProcessBoundary):
    def __init__(self, observation_factory: Callable[[AdapterRequest], object]) -> None:
        super().__init__()
        self.observation_factory = observation_factory
        self.attest_calls: list[AdapterRequest] = []
        self.attestation_mutators: dict[str, Callable[[dict[str, object]], None]] = {}
        self.attestation_responses: dict[str, object] = {}
        self.attestation_failures: dict[str, BaseException] = {}

    def attest(self, handle: object, request: AdapterRequest) -> object:
        del handle
        self.calls.append(("attest", request))
        self.attest_calls.append(request)
        failure = self.attestation_failures.get(request.operation)
        if failure is not None:
            raise failure
        response = self.attestation_responses.get(request.operation, _UNSET)
        if response is not _UNSET:
            return response
        observed = self.observation_factory(request)
        if not isinstance(observed, dict):
            return observed
        copied = {
            key: (
                [dict(item) for item in value]
                if key == "instruction_sources"
                else list(value)
                if key in {"writable_roots", "alternate_transports"}
                else value
            )
            for key, value in observed.items()
        }
        mutator = self.attestation_mutators.get(request.operation)
        if mutator is not None:
            mutator(copied)
        return copied


def _enable_attestation(fx: object) -> _AttestingBoundary:
    process = _AttestingBoundary(
        lambda _request: _observation(fx.authority, fx.binding, fx.worker_context)
    )
    process.adapter = fx.adapter
    fx.process = process
    return process


def _open_failure(fx: object, code: str) -> CodexWorkerError:
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx)
    assert caught.value.code == code
    assert caught.value.primary_code == code
    assert SENTINEL not in str(caught.value)
    return caught.value


def test_01_exact_ordered_instruction_sources_and_exact_policy_attestation_pass(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    _validate(fx, observed)


def test_02_unexpected_user_instruction_source_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["instruction_sources"].append(
        {"source_id": "user", "role": "user", "sha256": "6" * 64}
    )
    _assert_validator_rejects(fx, observed)


def test_03_unexpected_project_agents_instruction_source_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["instruction_sources"].append(
        {"source_id": "agents-project", "role": "project", "sha256": "6" * 64}
    )
    _assert_validator_rejects(fx, observed)


def test_04_unexpected_global_instruction_source_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["instruction_sources"].append(
        {"source_id": "global", "role": "global", "sha256": "6" * 64}
    )
    _assert_validator_rejects(fx, observed)


def test_05_unexpected_mcp_instruction_source_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["instruction_sources"].append(
        {"source_id": "mcp", "role": "tool", "sha256": "6" * 64}
    )
    _assert_validator_rejects(fx, observed)


def test_06_missing_accepted_instruction_source_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["instruction_sources"] = observed["instruction_sources"][:-1]
    _assert_validator_rejects(fx, observed)


def test_07_reordered_instruction_sources_are_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["instruction_sources"] = list(reversed(observed["instruction_sources"]))
    _assert_validator_rejects(fx, observed)


def test_08_changed_instruction_source_hash_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["instruction_sources"][0]["sha256"] = "f" * 64
    _assert_validator_rejects(fx, observed)


def test_09_changed_instruction_source_role_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["instruction_sources"][0]["role"] = "developer"
    _assert_validator_rejects(fx, observed)


def test_10_duplicate_observed_instruction_source_id_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    duplicate = dict(observed["instruction_sources"][0])
    observed["instruction_sources"].append(duplicate)
    _assert_validator_rejects(fx, observed)


def test_11_caller_forged_attestation_cannot_replace_provider_observation(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    forged = _observation(fx.authority, fx.binding, fx.worker_context)
    process.attestation_mutators["start"] = lambda observed: observed.__setitem__(
        "model_identity", "foreign-model"
    )
    worker_module = __import__("agent_lib.codex_worker", fromlist=["start_codex_worker"])
    assert "provider_attestation" not in inspect.signature(worker_module.start_codex_worker).parameters
    _open_failure(fx, MISMATCH)
    assert forged["model_identity"] == fx.binding.model_config_identity["model_identity"]
    assert fx.adapter.calls == []


def test_12_unknown_or_extra_attestation_fields_are_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["unexpected_field"] = "unexpected"
    _assert_validator_rejects(fx, observed)


def test_13_approval_mode_other_than_deny_all_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["approval_mode"] = "on_request"
    _assert_validator_rejects(fx, observed)


def test_14_experimental_api_true_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["experimental_api"] = True
    _assert_validator_rejects(fx, observed)


def test_15_model_identity_drift_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["model_identity"] = "foreign-model"
    _assert_validator_rejects(fx, observed)


def test_16_config_hash_drift_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["config_sha256"] = "f" * 64
    _assert_validator_rejects(fx, observed)


def test_17_sandbox_write_policy_drift_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["sandbox_write_policy"] = "FULL_ACCESS"
    _assert_validator_rejects(fx, observed)


def test_18_cwd_drift_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["cwd"] = "C:/foreign"
    _assert_validator_rejects(fx, observed)


def test_19_inherited_or_extra_writable_root_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["writable_roots"].append("C:/foreign")
    _assert_validator_rejects(fx, observed)


def test_20_full_access_sandbox_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["full_access"] = True
    _assert_validator_rejects(fx, observed)


def test_21_auto_review_or_approval_escalation_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    for field in ("auto_review", "approval_escalation"):
        observed = _observation(fx.authority, fx.binding, fx.worker_context)
        observed[field] = True
        _assert_validator_rejects(fx, observed)


def test_22_alternate_or_fallback_transport_is_rejected(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    observed["transport"] = "app_server"
    observed["alternate_transports"] = ["cli", "mcp"]
    _assert_validator_rejects(fx, observed)


def test_23_start_attests_before_returning_usable_session(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    session = _start(fx)
    assert isinstance(session, CodexWorkerSession)
    assert [request.operation for request in process.attest_calls] == ["start"]
    names = [name for name, _ in process.calls]
    assert names.index("attest") < names.index("invoke")
    assert [request.operation for request in fx.adapter.calls] == ["start"]


def test_24_resume_reattests_and_rejects_post_start_policy_drift(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    process.attestation_mutators["resume"] = lambda observed: observed.__setitem__(
        "config_sha256", "f" * 64
    )
    with pytest.raises(CodexWorkerError) as caught:
        resume_codex_worker(
            handoff=fx.handoff,
            binding=fx.binding,
            authority_context=fx.authority,
            worker_context=fx.worker_context,
            adapter=fx.adapter,
            process_boundary=process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == MISMATCH
    assert [request.operation for request in process.attest_calls] == ["resume"]
    assert fx.adapter.calls == []


def test_25_fork_requires_fresh_target_attestation_not_inherited_source_history(tmp_path: Path) -> None:
    source = _fixture(tmp_path / "source")
    target = _fresh_target(tmp_path / "target")
    process = _AttestingBoundary(
        lambda _request: _observation(source.authority, source.binding, source.worker_context)
    )
    process.adapter = source.adapter
    with pytest.raises(CodexWorkerError) as caught:
        fork_codex_worker(
            source_handoff=source.handoff,
            source_binding=source.binding,
            source_authority_context=source.authority,
            source_worker_context=source.worker_context,
            handoff=target[0],
            binding=target[3],
            authority_context=target[1],
            worker_context=target[2],
            adapter=source.adapter,
            process_boundary=process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == MISMATCH
    assert [request.operation for request in process.attest_calls] == ["fork"]
    assert source.adapter.calls == []


def test_26_turn_reattests_and_rejects_post_start_instruction_drift(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    session = _start(fx)
    process.attestation_mutators["turn"] = lambda observed: observed["instruction_sources"].append(
        {"source_id": "ambient", "role": "user", "sha256": "6" * 64}
    )
    result = session.turn({"prompt": "bounded"}, timeout_seconds=1.0, now=NOW)
    _assert_failed(result, MISMATCH)
    assert [request.operation for request in process.attest_calls] == ["start", "turn"]
    assert [request.operation for request in fx.adapter.calls] == ["start"]


def test_27_steer_reattests_and_rejects_post_start_provider_policy_drift(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    session = _start(fx)
    process.attestation_mutators["steer"] = lambda observed: observed.__setitem__(
        "approval_mode", "on_request"
    )
    result = session.steer({"instruction": "bounded"}, timeout_seconds=1.0, now=NOW)
    _assert_failed(result, MISMATCH)
    assert [request.operation for request in process.attest_calls] == ["start", "steer"]
    assert [request.operation for request in fx.adapter.calls] == ["start"]


def test_28_attestation_mismatch_clears_pending_candidate_and_triggers_cleanup(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    session = _start(fx)
    first = session.turn({}, timeout_seconds=1.0, now=NOW)
    assert first.success is True and first.candidate_output is not None
    process.attestation_mutators["steer"] = lambda observed: observed.__setitem__(
        "cwd", "C:/foreign"
    )
    failed = session.steer({}, timeout_seconds=1.0, now=NOW)
    _assert_failed(failed, MISMATCH)
    assert [name for name, _ in process.calls].count("cleanup") == 1
    assert session.close(timeout_seconds=1.0, now=NOW) == failed


def test_29_sdk_with_no_attestation_evidence_fails_named_gap_before_provider_turn(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    process.attestation_responses["start"] = None
    error = _open_failure(fx, GAP)
    assert error.cleanup_result is not None
    assert fx.adapter.calls == []
    assert [name for name, _ in process.calls] == ["start", "attest", "cleanup"]


def test_30_sdk_policy_without_instruction_evidence_fails_named_gap(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    partial = _observation(fx.authority, fx.binding, fx.worker_context)
    partial.pop("instruction_sources")
    process.attestation_responses["start"] = partial
    _open_failure(fx, GAP)
    assert fx.adapter.calls == []


def test_31_sdk_instructions_without_effective_policy_evidence_fails_named_gap(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    partial = _observation(fx.authority, fx.binding, fx.worker_context)
    for key in (
        "approval_mode",
        "model_identity",
        "config_sha256",
        "sandbox_write_policy",
        "cwd",
        "writable_roots",
    ):
        partial.pop(key)
    process.attestation_responses["start"] = partial
    _open_failure(fx, GAP)
    assert fx.adapter.calls == []


def test_32_compatible_sdk_metadata_alone_is_not_effective_attestation(tmp_path: Path) -> None:
    fx = _fixture(tmp_path / "request")
    _start(fx)
    request = fx.adapter.calls[0]
    lazy = LazyOfficialSdkAdapter(
        adapter_factory=lambda _module: _FakeAdapter(),
        compatibility_check=lambda: {"status": "compatible", "version": "1.0"},
        module_loader=lambda _name: object(),
    )
    attest = getattr(lazy, "attest", None)
    assert callable(attest), "Task-5 official SDK attestation seam is missing"
    with pytest.raises(CodexWorkerError) as caught:
        attest(request)
    assert caught.value.code == GAP


def test_33_sdk_gap_has_no_implicit_app_server_fallback(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    process.attestation_responses["start"] = {}
    _open_failure(fx, GAP)
    source = WORKER_SOURCE.read_text(encoding="utf-8").lower()
    assert "app-server" not in source
    assert "app_server" not in source


def test_34_sdk_gap_has_no_implicit_cli_mcp_or_third_party_fallback(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    process.attestation_responses["start"] = {}
    _open_failure(fx, GAP)
    source = WORKER_SOURCE.read_text(encoding="utf-8").lower()
    for token in ("codex exec", "mcp_integration_lib", "third-party", "third_party"):
        assert token not in source


def test_35_attestation_failures_are_privacy_safe(tmp_path: Path) -> None:
    mismatch = _fixture(tmp_path / "mismatch")
    mismatch_process = _enable_attestation(mismatch)
    mismatch_process.attestation_mutators["start"] = lambda observed: observed.__setitem__(
        "thread_id", SENTINEL
    )
    mismatch_error = _open_failure(mismatch, MISMATCH)
    assert SENTINEL not in repr(mismatch_error)

    gap = _fixture(tmp_path / "gap")
    gap_process = _enable_attestation(gap)
    gap_process.attestation_responses["start"] = {"raw": SENTINEL}
    gap_error = _open_failure(gap, GAP)
    assert SENTINEL not in repr(gap_error)


def test_36_schema_identity_remains_exact_while_policy_attestation_is_added(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    session = _start(fx)
    assert session.binding.output_schema_sha256 == fx.binding.output_schema_sha256
    assert session.binding.output_validator_version == fx.binding.output_validator_version
    request = fx.adapter.calls[0]
    assert request.output_schema_sha256 == fx.binding.output_schema_sha256
    assert request.output_validator_version == fx.binding.output_validator_version
    assert request.handoff_sha256 == fx.binding.handoff_hash
    assert [item.operation for item in process.attest_calls] == ["start"]


def test_37_server_policy_and_authority_identities_cannot_be_provider_minted(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    before_policy = fx.binding.policy_identity
    before_authority = fx.binding.authority_context_identity
    observed = _observation(fx.authority, fx.binding, fx.worker_context)
    _validate(fx, observed)
    assert fx.binding.policy_identity == before_policy
    assert fx.binding.authority_context_identity == before_authority
    forged = dict(observed)
    forged["policy_identity"] = "f" * 64
    forged["authority_context_identity"] = "e" * 64
    _assert_validator_rejects(fx, forged)


def test_38_cleanup_and_interrupt_remain_callable_after_policy_failure_without_promotion(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    session = _start(fx)
    process.attestation_mutators["turn"] = lambda observed: observed.__setitem__(
        "experimental_api", True
    )
    failed = session.turn({}, timeout_seconds=1.0, now=NOW)
    _assert_failed(failed, MISMATCH)
    after = session.interrupt(timeout_seconds=1.0, now=NOW)
    assert after == failed
    assert [name for name, _ in process.calls].count("cleanup") == 1
    assert after.promotion_safe is False and after.candidate_output is None


def test_39_first_slice_uses_fake_evidence_only_and_never_imports_real_provider_or_auth(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    loaded: list[str] = []
    lazy = LazyOfficialSdkAdapter(
        adapter_factory=lambda _module: (_ for _ in ()).throw(
            AssertionError("real delegate must not be built")
        ),
        compatibility_check=lambda: (_ for _ in ()).throw(
            AssertionError("real compatibility must not run")
        ),
        module_loader=lambda name: loaded.append(name) or object(),
    )
    session = _start(fx, adapter=lazy)
    result = session.turn({}, timeout_seconds=1.0, now=NOW)
    assert result.success is True
    assert loaded == []
    assert isinstance(fx.adapter, _FakeAdapter)
    assert [request.operation for request in process.attest_calls] == ["start", "turn"]


def test_40_module_ownership_does_not_expand_into_forbidden_authority_owners() -> None:
    for path in (WORKER_SOURCE, HANDOFF_SOURCE):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        authority_symbols: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
                authority_symbols.update(
                    (alias.asname or alias.name.rsplit(".", 1)[-1]).lower()
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
                authority_symbols.update(
                    (alias.asname or alias.name).lower() for alias in node.names
                )
            elif isinstance(node, ast.Name):
                authority_symbols.add(node.id.lower())
            elif isinstance(node, ast.Attribute):
                authority_symbols.add(node.attr.lower())
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                authority_symbols.add(node.name.lower())
        roots = {name.split(".", 1)[0] for name in imported}
        assert roots.isdisjoint(
            {
                "autocad_plugin",
                "mcp_integration_lib",
                "dxf_builder_lib",
                "semantic_ir_lib",
                "primitive_ir_lib",
            }
        )
        lowered = source.lower()
        for token in (
            "source_integrity",
            "repair_executor",
            "verified_publisher",
            "manifest_store",
            "checkpoint_store",
        ):
            assert token not in lowered
        assert "cad_truth_authority" not in authority_symbols
    worker_lowered = WORKER_SOURCE.read_text(encoding="utf-8").lower()
    assert "file_ipc" not in worker_lowered
    assert "cad_truth_authority" not in worker_lowered


def _raw_session(fx: object, process: _FakeProcessBoundary) -> CodexWorkerSession:
    process.adapter = fx.adapter
    sandbox = fx.worker_context.sandbox_policy
    attestation, handle = process.start(
        expected_disposable_root=Path(sandbox["roots"][0]),
        expected_cwd=Path(sandbox["cwd"]),
    )
    return CodexWorkerSession(
        handoff=fx.handoff,
        binding=fx.binding,
        authority_context=fx.authority,
        worker_context=fx.worker_context,
        process_boundary=process,
        environment_attestation=attestation,
        process_handle=handle,
    )


def test_41_missing_attestation_on_custom_start_boundary_fails_closed_before_provider_invoke(
    tmp_path: Path,
) -> None:
    fx = _fixture(tmp_path)
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx)
    assert caught.value.code == GAP
    assert caught.value.primary_code == GAP
    assert fx.adapter.calls == []
    assert [name for name, _ in fx.process.calls] == ["start", "cleanup"]


def test_42_caller_minted_matching_mapping_is_not_authorized_provider_provenance(
    tmp_path: Path,
) -> None:
    fx = _fixture(tmp_path)
    process = _enable_attestation(fx)
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx)
    assert caught.value.code == GAP
    assert caught.value.primary_code == GAP
    assert fx.adapter.calls == []
    assert [name for name, _ in process.calls] == ["start", "attest", "cleanup"]


def test_43_resume_with_missing_attestation_fails_gap_before_provider_invoke(
    tmp_path: Path,
) -> None:
    fx = _fixture(tmp_path)
    with pytest.raises(CodexWorkerError) as caught:
        resume_codex_worker(
            handoff=fx.handoff,
            binding=fx.binding,
            authority_context=fx.authority,
            worker_context=fx.worker_context,
            adapter=fx.adapter,
            process_boundary=fx.process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == GAP
    assert caught.value.primary_code == GAP
    assert fx.adapter.calls == []
    assert [name for name, _ in fx.process.calls] == ["start", "cleanup"]


def test_44_fork_rejects_perfect_matching_mapping_from_caller_controlled_boundary(
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path / "source")
    target = _fresh_target(tmp_path / "target")
    process = _AttestingBoundary(
        lambda _request: _observation(target[1], target[3], target[2])
    )
    process.adapter = source.adapter
    with pytest.raises(CodexWorkerError) as caught:
        fork_codex_worker(
            source_handoff=source.handoff,
            source_binding=source.binding,
            source_authority_context=source.authority,
            source_worker_context=source.worker_context,
            handoff=target[0],
            binding=target[3],
            authority_context=target[1],
            worker_context=target[2],
            adapter=source.adapter,
            process_boundary=process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == GAP
    assert caught.value.primary_code == GAP
    assert source.adapter.calls == []
    assert [name for name, _ in process.calls] == ["start", "attest", "cleanup"]


@pytest.mark.parametrize("operation", ["turn", "steer"])
def test_45_session_lifecycle_rejects_caller_minted_provenance_and_cleans_without_candidate(
    tmp_path: Path,
    operation: str,
) -> None:
    fx = _fixture(tmp_path)
    process = _AttestingBoundary(
        lambda _request: _observation(fx.authority, fx.binding, fx.worker_context)
    )
    session = _raw_session(fx, process)
    result = getattr(session, operation)({}, timeout_seconds=1.0, now=NOW)
    _assert_failed(result, GAP)
    assert result.candidate_output is None
    assert result.promotion_safe is False
    assert fx.adapter.calls == []
    assert [name for name, _ in process.calls].count("cleanup") == 1
    assert [request.operation for request in process.attest_calls] == [operation]


# Task-5 remediation harness: provider-observed evidence is supplied only by
# the authorized Task-3 control seam. Raw custom boundaries remain untrusted.
@pytest.fixture(autouse=True)
def _task5_authorized_child_control(monkeypatch: pytest.MonkeyPatch) -> None:
    import agent_lib.codex_worker as worker_module
    from agent_lib.tests.test_codex_worker import _task3_harness_exchange

    monkeypatch.setattr(worker_module, "exchange_worker_control", _task3_harness_exchange)


def _enable_attestation(fx: object) -> object:  # noqa: F811
    from agent_lib.tests.test_codex_worker import _Task3HarnessBoundary

    process = fx.process
    assert isinstance(process, _Task3HarnessBoundary)
    return process


def test_25_fork_requires_fresh_target_attestation_not_inherited_source_history(  # noqa: F811
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path / "source")
    target = _fresh_target(tmp_path / "target")
    process = source.process
    process.attestation_factory = lambda _request: _observation(
        source.authority, source.binding, source.worker_context
    )
    with pytest.raises(CodexWorkerError) as caught:
        fork_codex_worker(
            source_handoff=source.handoff,
            source_binding=source.binding,
            source_authority_context=source.authority,
            source_worker_context=source.worker_context,
            handoff=target[0],
            binding=target[3],
            authority_context=target[1],
            worker_context=target[2],
            adapter=source.adapter,
            process_boundary=process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == MISMATCH
    assert [request.operation for request in process.attest_calls] == ["fork"]
    assert source.adapter.calls == []


def test_41_missing_attestation_on_custom_start_boundary_fails_closed_before_provider_invoke(  # noqa: F811
    tmp_path: Path,
) -> None:
    fx = _fixture(tmp_path)
    process = _FakeProcessBoundary()
    process.adapter = fx.adapter
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx, process_boundary=process)
    assert caught.value.code == GAP
    assert caught.value.primary_code == GAP
    assert fx.adapter.calls == []
    assert [name for name, _ in process.calls] == ["start", "cleanup"]


def test_42_caller_minted_matching_mapping_is_not_authorized_provider_provenance(  # noqa: F811
    tmp_path: Path,
) -> None:
    fx = _fixture(tmp_path)
    process = _AttestingBoundary(
        lambda _request: _observation(fx.authority, fx.binding, fx.worker_context)
    )
    process.adapter = fx.adapter
    with pytest.raises(CodexWorkerError) as caught:
        _start(fx, process_boundary=process)
    assert caught.value.code == GAP
    assert caught.value.primary_code == GAP
    assert fx.adapter.calls == []
    assert process.attest_calls == []
    assert [name for name, _ in process.calls] == ["start", "cleanup"]


def test_43_resume_with_missing_attestation_fails_gap_before_provider_invoke(  # noqa: F811
    tmp_path: Path,
) -> None:
    fx = _fixture(tmp_path)
    process = _FakeProcessBoundary()
    process.adapter = fx.adapter
    with pytest.raises(CodexWorkerError) as caught:
        resume_codex_worker(
            handoff=fx.handoff,
            binding=fx.binding,
            authority_context=fx.authority,
            worker_context=fx.worker_context,
            adapter=fx.adapter,
            process_boundary=process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == GAP
    assert caught.value.primary_code == GAP
    assert fx.adapter.calls == []
    assert [name for name, _ in process.calls] == ["start", "cleanup"]


def test_44_fork_rejects_perfect_matching_mapping_from_caller_controlled_boundary(  # noqa: F811
    tmp_path: Path,
) -> None:
    source = _fixture(tmp_path / "source")
    target = _fresh_target(tmp_path / "target")
    process = _AttestingBoundary(
        lambda _request: _observation(target[1], target[3], target[2])
    )
    process.adapter = source.adapter
    with pytest.raises(CodexWorkerError) as caught:
        fork_codex_worker(
            source_handoff=source.handoff,
            source_binding=source.binding,
            source_authority_context=source.authority,
            source_worker_context=source.worker_context,
            handoff=target[0],
            binding=target[3],
            authority_context=target[1],
            worker_context=target[2],
            adapter=source.adapter,
            process_boundary=process,
            timeout_seconds=1.0,
            now=NOW,
        )
    assert caught.value.code == GAP
    assert caught.value.primary_code == GAP
    assert source.adapter.calls == []
    assert process.attest_calls == []
    assert [name for name, _ in process.calls] == ["start", "cleanup"]


@pytest.mark.parametrize("operation", ["turn", "steer"])
def test_45_session_lifecycle_rejects_caller_minted_provenance_and_cleans_without_candidate(  # noqa: F811
    tmp_path: Path,
    operation: str,
) -> None:
    fx = _fixture(tmp_path)
    process = _AttestingBoundary(
        lambda _request: _observation(fx.authority, fx.binding, fx.worker_context)
    )
    session = _raw_session(fx, process)
    result = getattr(session, operation)({}, timeout_seconds=1.0, now=NOW)
    _assert_failed(result, GAP)
    assert result.candidate_output is None
    assert result.promotion_safe is False
    assert fx.adapter.calls == []
    assert [name for name, _ in process.calls].count("cleanup") == 1
    assert process.attest_calls == []


def _round2_real_target(tmp_path: Path):
    workspace = (tmp_path / "workspace").resolve()
    workspace.mkdir(parents=True)

    def bind_workspace(payload: dict[str, object]) -> None:
        workspace_payload = dict(payload["workspace"])
        workspace_payload["roots"] = [str(workspace)]
        payload["workspace"] = workspace_payload

    return _fresh_target(tmp_path / "bound", payload_mutator=bind_workspace), workspace


@pytest.mark.skipif(
    __import__("os").name != "nt",
    reason="requires a real Task-3 issued Windows process/control handle",
)
def test_46_noncanonical_task3_issued_handle_does_not_establish_child_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    import agent_lib.codex_worker as worker_module
    import agent_lib.codex_worker_process as process_owner

    target, workspace = _round2_real_target(tmp_path)
    handoff, authority, worker_context, binding = target
    observation = _observation(authority, binding, worker_context)
    marker = workspace / "noncanonical-handler-called.txt"
    repo_root = str(Path(__file__).parents[1])
    child_code = "\n".join(
        [
            "import sys",
            f"sys.path.insert(0, {repo_root!r})",
            "from pathlib import Path",
            "from agent_lib.codex_worker_process import run_worker_control_child",
            f"observation = {observation!r}",
            f"marker = Path({str(marker)!r})",
            "def handler(payload):",
            "    marker.write_text('called', encoding='utf-8')",
            "    if str(payload.get('operation', '')).startswith('__attest__.'):",
            "        return observation",
            "    return {'status': 'ready', 'thread_id': payload.get('thread_id'), "
            "'events': [{'type': 'thread.ready'}]}",
            "raise SystemExit(run_worker_control_child(handler))",
        ]
    )
    boundary = worker_module.Task3ProcessBoundary(
        cleanup_deadline_seconds=5.0,
        max_processes=8,
        _executable=Path(sys.executable).resolve(),
        _argv=("-c", child_code),
    )
    monkeypatch.setattr(
        worker_module,
        "exchange_worker_control",
        process_owner.exchange_worker_control,
    )
    captured: dict[str, object] = {}
    original_start = boundary.start

    def capture_start(
        *, expected_disposable_root: Path, expected_cwd: Path
    ) -> tuple[object, object]:
        result = original_start(
            expected_disposable_root=expected_disposable_root,
            expected_cwd=expected_cwd,
        )
        captured["handle"] = result[1]
        return result

    monkeypatch.setattr(boundary, "start", capture_start)
    try:
        with pytest.raises(CodexWorkerError) as caught:
            worker_module.start_codex_worker(
                handoff=handoff,
                binding=binding,
                authority_context=authority,
                worker_context=worker_context,
                adapter=_FakeAdapter(),
                process_boundary=boundary,
                timeout_seconds=1.0,
                now=NOW,
            )
        assert caught.value.code == GAP
        assert not marker.exists()
    finally:
        handle = captured.get("handle")
        if handle is not None:
            process_owner.cleanup_worker_process(handle)


@pytest.mark.skipif(
    __import__("os").name != "nt",
    reason="requires a real Task-3 issued Windows process/control handle",
)
def test_47_caller_cleanup_cannot_mint_task3_zero_survivor_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import agent_lib.codex_worker as worker_module
    import agent_lib.codex_worker_process as process_owner

    target, _workspace = _round2_real_target(tmp_path)
    handoff, authority, worker_context, binding = target
    task3 = worker_module.Task3ProcessBoundary(
        cleanup_deadline_seconds=5.0,
        max_processes=8,
    )
    forged = process_owner.WorkerCleanupResult(
        status="CLEANUP_SUCCEEDED",
        success=True,
        promotion_safe=True,
        survivor_pids=(),
        survivor_count=0,
        error_code=None,
    )

    class CallerCleanupBoundary:
        def __init__(self) -> None:
            self.cleanup_calls = 0
            self.handle: object | None = None

        def start(
            self,
            *,
            expected_disposable_root: Path,
            expected_cwd: Path,
        ) -> tuple[object, object]:
            result = task3.start(
                expected_disposable_root=expected_disposable_root,
                expected_cwd=expected_cwd,
            )
            self.handle = result[1]
            return result

        def cleanup(self, handle: object) -> object:
            assert handle is self.handle
            self.cleanup_calls += 1
            return forged

    boundary = CallerCleanupBoundary()
    monkeypatch.setattr(
        worker_module,
        "exchange_worker_control",
        process_owner.exchange_worker_control,
    )
    real_cleanup = process_owner.cleanup_worker_process
    owner_results: list[object] = []

    def canonical_cleanup(handle: object) -> object:
        result = real_cleanup(handle)
        owner_results.append(result)
        return result

    monkeypatch.setattr(worker_module, "cleanup_worker_process", canonical_cleanup)
    try:
        with pytest.raises(CodexWorkerError) as caught:
            worker_module.start_codex_worker(
                handoff=handoff,
                binding=binding,
                authority_context=authority,
                worker_context=worker_context,
                adapter=_FakeAdapter(),
                process_boundary=boundary,
                timeout_seconds=1.0,
                now=NOW,
            )
        assert boundary.cleanup_calls == 0
        assert len(owner_results) == 1
        assert caught.value.cleanup_result is owner_results[0]
        assert caught.value.cleanup_result is not forged
    finally:
        if boundary.handle is not None:
            real_cleanup(boundary.handle)


# Round-2 policy tests share the same test-only canonical cleanup-owner double
# as the worker regression module. This patches only the imported production
# owner symbol; it never calls or trusts process_boundary.cleanup().
@pytest.fixture(autouse=True)
def _task5_round2_authorized_cleanup_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    import agent_lib.codex_worker as worker_module
    from agent_lib.tests.test_codex_worker import _task3_harness_cleanup_worker_process

    monkeypatch.setattr(
        worker_module,
        "cleanup_worker_process",
        _task3_harness_cleanup_worker_process,
    )
