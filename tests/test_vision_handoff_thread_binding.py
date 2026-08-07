from __future__ import annotations

import importlib
from dataclasses import replace
from datetime import timedelta
import inspect
from pathlib import Path

import pytest

from tests.test_vision_handoff import NOW, _authority_context, _base_payload, _bind, _write_schema


def _module():
    try:
        return importlib.import_module("cad_agent.vision_handoff")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Task 2 production boundary is missing: {exc}")


def _thread_inputs(handoff, *, thread_id: str = "THREAD-001") -> dict[str, object]:
    return {
        "thread_id": thread_id,
        "worker_context": _worker_context(handoff),
    }


def _worker_context(handoff, *, adapter_version: str = "adapter-1.0", sandbox_policy=None):
    module = _module()
    workspace = handoff.payload["workspace"]
    return module.ServerOwnedWorkerBindingContext(
        adapter_version=adapter_version,
        sandbox_policy=sandbox_policy
        or {
            "roots": list(workspace["roots"]),
            "write_policy": workspace["write_policy"],
            "cwd": workspace["roots"][0],
        },
    )


def _bind_thread(handoff, *, thread_id: str = "THREAD-001", **overrides: object):
    module = _module()
    inputs = _thread_inputs(handoff, thread_id=thread_id)
    authority_context = overrides.pop(
        "authority_context", _authority_context(dict(handoff.payload))
    )
    inputs.update(overrides)
    return module.bind_worker_thread(
        handoff,
        authority_context=authority_context,
        now=NOW,
        **inputs,
    )


def _resume_thread(handoff, bound, **overrides: object):
    module = _module()
    inputs = _thread_inputs(handoff, thread_id=bound.thread_id)
    authority_context = overrides.pop(
        "authority_context", _authority_context(dict(handoff.payload))
    )
    inputs.update(overrides)
    return module.resume_worker_thread(
        bound,
        handoff,
        authority_context=authority_context,
        now=NOW,
        **inputs,
    )


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
    bound = _bind_thread(handoff)

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
        module.resume_worker_thread(
            "THREAD-001",
            handoff,
            authority_context=_authority_context(dict(handoff.payload)),
            now=NOW,
            **inputs,
        )


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
            authority_context=_authority_context(dict(handoff.payload)),
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
        module.resume_worker_thread(
            bound,
            consumed,
            authority_context=_authority_context(dict(consumed.payload)),
            now=NOW,
            **inputs,
        )


def test_resume_rejects_server_owned_worker_context_drift(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    bound = _bind_thread(handoff)
    bad_adapter_context = _worker_context(handoff, adapter_version="adapter-2.0")
    with pytest.raises(ValueError, match="adapter|server-owned|binding"):
        _resume_thread(handoff, bound, worker_context=bad_adapter_context)

    bad_sandbox_context = _worker_context(
        handoff,
        sandbox_policy={
            "roots": ["C:/disposable/vision-run-001"],
            "write_policy": "DISPOSABLE_ONLY",
            "cwd": "C:/foreign",
        },
    )
    with pytest.raises(ValueError, match="sandbox|cwd|binding"):
        _resume_thread(handoff, bound, worker_context=bad_sandbox_context)


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
        module.resume_worker_thread(
            injected,
            handoff,
            authority_context=_authority_context(dict(handoff.payload)),
            now=NOW,
            **inputs,
        )


def test_fork_requires_fresh_handoff_and_approval(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    source = _bind(schema_path)
    source_bound = _bind_thread(source)
    same_inputs = _thread_inputs(source, thread_id="THREAD-002")
    with pytest.raises(ValueError, match="fresh|fork|approval|binding"):
        module.fork_worker_thread(
            source_bound,
            source,
            source_handoff=source,
            source_authority_context=_authority_context(dict(source.payload)),
            source_worker_context=_worker_context(source),
            authority_context=_authority_context(dict(source.payload)),
            now=NOW,
            **same_inputs,
        )

    reused_approval = _fresh_handoff(schema_path, approval_reference=source.payload["approval_reference"])
    reused_inputs = _thread_inputs(reused_approval, thread_id="THREAD-002")
    with pytest.raises(ValueError, match="fresh|approval|fork"):
        module.fork_worker_thread(
            source_bound,
            reused_approval,
            source_handoff=source,
            source_authority_context=_authority_context(dict(source.payload)),
            source_worker_context=_worker_context(source),
            authority_context=_authority_context(dict(reused_approval.payload)),
            now=NOW,
            **reused_inputs,
        )


def test_fork_binds_fresh_target_without_inherited_approval(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    source = _bind(schema_path)
    source_bound = _bind_thread(source)
    target = _fresh_handoff(schema_path)
    target_inputs = _thread_inputs(target, thread_id="THREAD-002")
    target_bound = module.fork_worker_thread(
        source_bound,
        target,
        source_handoff=source,
        source_authority_context=_authority_context(dict(source.payload)),
        source_worker_context=_worker_context(source),
        authority_context=_authority_context(dict(target.payload)),
        now=NOW,
        **target_inputs,
    )

    assert target_bound.handoff_id == "HANDOFF-002"
    assert target_bound.run_id == "RUN-002"
    assert target_bound.thread_id == "THREAD-002"
    assert target_bound.approval_reference == "APPROVAL-002"
    assert target_bound.approval_reference != source_bound.approval_reference
    assert target_bound.handoff_hash == target.handoff_sha256


def test_current_consumption_snapshot_blocks_start_resume_and_fork(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    consumed_context = replace(
        _authority_context(dict(handoff.payload)),
        consumed_handoff_ids=(handoff.payload["handoff_id"],),
    )

    with pytest.raises(ValueError, match="reused|consum"):
        _bind_thread(handoff, authority_context=consumed_context)

    bound = _bind_thread(handoff)
    with pytest.raises(ValueError, match="reused|consum"):
        _resume_thread(handoff, bound, authority_context=consumed_context)

    target = _fresh_handoff(schema_path)
    with pytest.raises(ValueError, match="reused|consum"):
        module.fork_worker_thread(
            bound,
            target,
            source_handoff=handoff,
            source_authority_context=consumed_context,
            source_worker_context=_worker_context(handoff),
            authority_context=_authority_context(dict(target.payload)),
            now=NOW,
            **_thread_inputs(target, thread_id="THREAD-002"),
        )


def test_fork_rebinds_and_rejects_tampered_source_history(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    source = _bind(schema_path)
    source_bound = _bind_thread(source)
    tampered = replace(
        source_bound,
        handoff_id="FOREIGN-HANDOFF",
        handoff_hash="f" * 64,
        approval_reference="FOREIGN-APPROVAL",
    )
    target = _fresh_handoff(schema_path)

    with pytest.raises(ValueError, match="source|binding|approval|history"):
        module.fork_worker_thread(
            tampered,
            target,
            source_handoff=source,
            source_authority_context=_authority_context(dict(source.payload)),
            source_worker_context=_worker_context(source),
            authority_context=_authority_context(dict(target.payload)),
            now=NOW,
            **_thread_inputs(target, thread_id="THREAD-002"),
        )


def test_fork_rejects_scope_or_policy_widening(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    source = _bind(schema_path)
    source_bound = _bind_thread(source)

    widened_payload = _base_payload()
    widened_payload.update(
        {
            "handoff_id": "HANDOFF-002",
            "run_id": "RUN-002",
            "request_id": "REQUEST-002",
            "approval_reference": "APPROVAL-002",
        }
    )
    widened_payload["scope"] = dict(widened_payload["scope"])
    widened_payload["scope"]["components"] = ["component-001", "component-002"]
    widened_payload["allowed_operations"] = [
        "READ_ONLY_VISION_ANALYSIS",
        "WRITE_DISPOSABLE_CANDIDATE",
    ]
    widened = _bind(
        schema_path,
        widened_payload,
        authority_context=_authority_context(widened_payload),
    )

    with pytest.raises(ValueError, match="policy|scope|widen|fork"):
        module.fork_worker_thread(
            source_bound,
            widened,
            source_handoff=source,
            source_authority_context=_authority_context(dict(source.payload)),
            source_worker_context=_worker_context(source),
            authority_context=_authority_context(widened_payload),
            now=NOW,
            **_thread_inputs(widened, thread_id="THREAD-002"),
        )


def test_adapter_and_sandbox_authority_are_server_owned(tmp_path: Path) -> None:
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)

    with pytest.raises(ValueError, match="adapter|server-owned"):
        _bind_thread(
            handoff,
            worker_context=_worker_context(handoff, adapter_version="adapter-2.0"),
        )
    with pytest.raises(ValueError, match="sandbox|cwd|server-owned"):
        _bind_thread(
            handoff,
            worker_context=_worker_context(
                handoff,
                sandbox_policy={
                    "roots": ["C:/disposable/vision-run-001"],
                    "write_policy": "DISPOSABLE_ONLY",
                    "cwd": "C:/foreign",
                },
            ),
        )


def test_model_and_instruction_identity_are_not_caller_override_surfaces(tmp_path: Path) -> None:
    module = _module()
    schema_path = _write_schema(tmp_path / "schema.json")
    handoff = _bind(schema_path)
    signature = inspect.signature(module.bind_worker_thread)
    assert "model_config_identity" not in signature.parameters
    assert "instruction_source_identity" not in signature.parameters
    with pytest.raises(TypeError, match="unexpected keyword|model_config_identity"):
        module.bind_worker_thread(
            handoff,
            thread_id="THREAD-001",
            worker_context=_worker_context(handoff),
            authority_context=_authority_context(dict(handoff.payload)),
            model_config_identity={
                "model_identity": "foreign-model",
                "config_sha256": "f" * 64,
            },
            now=NOW,
        )
