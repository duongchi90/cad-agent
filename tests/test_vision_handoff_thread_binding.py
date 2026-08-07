from __future__ import annotations

import importlib
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from tests.test_vision_handoff import NOW, _authority_context, _base_payload, _bind, _write_schema


def _module():
    try:
        return importlib.import_module("cad_agent.vision_handoff")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Task 2 production boundary is missing: {exc}")


def _thread_inputs(handoff, *, thread_id: str = "THREAD-001") -> dict[str, object]:
    workspace = handoff.payload["workspace"]
    policy = handoff.payload["provider_policy"]
    return {
        "thread_id": thread_id,
        "adapter_version": "adapter-1.0",
        "model_config_identity": {
            "model_identity": policy["model_identity"],
            "config_sha256": policy["config_sha256"],
        },
        "instruction_source_identity": [dict(source) for source in handoff.payload["instruction_sources"]],
        "sandbox_policy": {
            "roots": list(workspace["roots"]),
            "write_policy": workspace["write_policy"],
            "cwd": workspace["roots"][0],
        },
    }


def _bind_thread(handoff, *, thread_id: str = "THREAD-001", **overrides: object):
    module = _module()
    inputs = _thread_inputs(handoff, thread_id=thread_id)
    inputs.update(overrides)
    return module.bind_worker_thread(handoff, now=NOW, **inputs)


def _resume_thread(handoff, bound, **overrides: object):
    module = _module()
    inputs = _thread_inputs(handoff, thread_id=bound.thread_id)
    inputs.update(overrides)
    return module.resume_worker_thread(bound, handoff, now=NOW, **inputs)


def _fresh_handoff(schema_path: Path, *, approval_reference: str = "APPROVAL-002"):
    payload = _base_payload()
    payload.update(
        {
            "handoff_id": "HANDOFF-002",
            "run_id": "RUN-002",
            "request_id": "REQUEST-002",
            "approval_reference": approval_reference,
        }
    )
    return _bind(schema_path, payload, authority_context=_authority_context(payload))


def test_valid_start_creates_immutable_complete_binding(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)

    model_config = {
        "model_identity": handoff.payload["provider_policy"]["model_identity"],
        "config_sha256": handoff.payload["provider_policy"]["config_sha256"],
    }
    instructions = [dict(source) for source in handoff.payload["instruction_sources"]]
    sandbox = {
        "roots": list(handoff.payload["workspace"]["roots"]),
        "write_policy": handoff.payload["workspace"]["write_policy"],
        "cwd": handoff.payload["workspace"]["roots"][0],
    }
    bound = _bind_thread(
        handoff,
        model_config_identity=model_config,
        instruction_source_identity=instructions,
        sandbox_policy=sandbox,
    )

    assert isinstance(bound, _module().BoundWorkerThread)
    assert bound.handoff_id == handoff.payload["handoff_id"]
    assert bound.handoff_hash == handoff.handoff_sha256
    assert bound.run_id == handoff.payload["run_id"]
    assert bound.thread_id == "THREAD-001"
    assert bound.adapter_version == "adapter-1.0"
    assert bound.model_config_identity["model_identity"] == "fake-disposable-model"
    assert bound.output_schema_sha256 == handoff.payload["output_schema_sha256"]
    assert bound.output_validator_version == handoff.payload["output_validator_version"]
    assert bound.approval_reference == handoff.payload["approval_reference"]
    assert bound.approval_authority == handoff.payload["approval_authority"]

    model_config["model_identity"] = "foreign-model"
    instructions[0]["sha256"] = "f" * 64
    sandbox["cwd"] = "C:/foreign"
    assert bound.model_config_identity["model_identity"] == "fake-disposable-model"
    assert bound.instruction_source_identity[0]["sha256"] == "3" * 64
    assert bound.sandbox_policy["cwd"] == "C:/disposable/vision-run-001"
    with pytest.raises((AttributeError, TypeError)):
        bound.thread_id = "FOREIGN-THREAD"


def test_bare_thread_id_cannot_authorize_resume(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    inputs = _thread_inputs(handoff)
    with pytest.raises((TypeError, ValueError), match="BoundWorkerThread|binding|authority"):
        module.resume_worker_thread("THREAD-001", handoff, now=NOW, **inputs)


@pytest.mark.parametrize(
    "change",
    [
        {"handoff_id": "FOREIGN-HANDOFF"},
        {"run_id": "FOREIGN-RUN"},
        {"owner_intent": "foreign-history"},
    ],
)
def test_resume_rejects_foreign_handoff_run_or_hash(tmp_path: Path, change: dict[str, str]) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    bound = _bind_thread(handoff)
    foreign_payload = _base_payload()
    foreign_payload.update(change)
    foreign = _bind(schema_path, foreign_payload, authority_context=_authority_context(foreign_payload))
    with pytest.raises(ValueError, match="binding|foreign|mismatch"):
        _resume_thread(foreign, bound)


def test_stale_or_expired_handoff_is_rejected(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    bound = _bind_thread(handoff)
    inputs = _thread_inputs(handoff, thread_id=bound.thread_id)
    with pytest.raises(ValueError, match="stale|expired"):
        module.resume_worker_thread(
            bound,
            handoff,
            now=NOW + timedelta(hours=2),
            **inputs,
        )


def test_consumed_handoff_is_rejected(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    bound = _bind_thread(handoff)
    consumed_payload = dict(handoff.payload)
    consumed_payload["consumed"] = True
    consumed = replace(handoff, payload=consumed_payload)
    inputs = _thread_inputs(consumed, thread_id=bound.thread_id)
    with pytest.raises(ValueError, match="consum|stale|binding"):
        module.resume_worker_thread(bound, consumed, now=NOW, **inputs)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("adapter_version", "adapter-2.0"),
        ("model_config_identity", {"model_identity": "foreign-model", "config_sha256": "5" * 64}),
        (
            "instruction_source_identity",
            [
                {"source_id": "system", "role": "system", "sha256": "f" * 64},
                {"source_id": "project", "role": "project", "sha256": "4" * 64},
            ],
        ),
        (
            "sandbox_policy",
            {
                "roots": ["C:/disposable/vision-run-001"],
                "write_policy": "DISPOSABLE_ONLY",
                "cwd": "C:/foreign",
            },
        ),
    ],
)
def test_resume_rejects_adapter_policy_and_history_drift(
    tmp_path: Path, field: str, value: object
) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    bound = _bind_thread(handoff)
    with pytest.raises(ValueError, match="binding|identity|policy|instruction|sandbox"):
        _resume_thread(handoff, bound, **{field: value})


@pytest.mark.parametrize("field", ["output_schema_sha256", "output_validator_version"])
def test_resume_rejects_schema_identity_drift(tmp_path: Path, field: str) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    bound = _bind_thread(handoff)
    changed_payload = dict(handoff.payload)
    changed_payload[field] = "f" * 64 if field.endswith("sha256") else "foreign-validator"
    changed = replace(handoff, payload=changed_payload)
    with pytest.raises(ValueError, match="binding|schema|validator"):
        _resume_thread(changed, bound)


def test_resume_rejects_injected_or_inherited_approval(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    bound = _bind_thread(handoff)
    injected = replace(bound, approval_reference="FOREIGN-APPROVAL")
    inputs = _thread_inputs(handoff, thread_id=bound.thread_id)
    with pytest.raises(ValueError, match="approval|binding"):
        module.resume_worker_thread(injected, handoff, now=NOW, **inputs)


def test_fork_requires_fresh_handoff_and_approval(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    source = _bind(schema_path)
    source_bound = _bind_thread(source)
    same_inputs = _thread_inputs(source, thread_id="THREAD-002")
    with pytest.raises(ValueError, match="fresh|fork|approval|binding"):
        module.fork_worker_thread(source_bound, source, now=NOW, **same_inputs)

    reused_approval = _fresh_handoff(schema_path, approval_reference=source.payload["approval_reference"])
    reused_inputs = _thread_inputs(reused_approval, thread_id="THREAD-002")
    with pytest.raises(ValueError, match="fresh|approval|fork"):
        module.fork_worker_thread(source_bound, reused_approval, now=NOW, **reused_inputs)


def test_fork_binds_fresh_target_without_inherited_approval(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    source = _bind(schema_path)
    source_bound = _bind_thread(source)
    target = _fresh_handoff(schema_path)
    target_inputs = _thread_inputs(target, thread_id="THREAD-002")
    target_bound = module.fork_worker_thread(source_bound, target, now=NOW, **target_inputs)

    assert target_bound.handoff_id == "HANDOFF-002"
    assert target_bound.run_id == "RUN-002"
    assert target_bound.thread_id == "THREAD-002"
    assert target_bound.approval_reference == "APPROVAL-002"
    assert target_bound.approval_reference != source_bound.approval_reference
    assert target_bound.handoff_hash == target.handoff_sha256
