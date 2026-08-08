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
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
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
            "file_ipc",
            "cad_truth_authority",
        ):
            assert token not in lowered
