"""Focused RED/GREEN contract tests for the R6 repair authorization owner."""

from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from importlib import import_module

import pytest

try:
    repair_authorization = import_module("cad_agent.repair_authorization")
except ModuleNotFoundError:
    # Keep the first RED causal: the owner/consume seam is absent, not broken
    # by an unrelated fixture or import in an existing package.
    repair_authorization = None


_FIELDS = {
    "run_id": "run-r6-001",
    "work_item_id": "repair-work-001",
    "candidate_revision_id": "candidate-r6-001",
    "r5_failure_id": "r5-fail-001",
    "r5_failure_sha256": "a" * 64,
    "repair_plan_id": "repair-plan-001",
    "repair_plan_sha256": "b" * 64,
    "repair_plan_version": "repair-plan-1.0",
    "repair_operation_contract_version": "repair-operation-1.0",
    "repair_operation_contract_fingerprint": "c" * 64,
}


def _owner():
    if repair_authorization is None:
        pytest.fail("repair authorization owner/consume seam is not present")
    return repair_authorization


def _issue(**overrides):
    fields = {**_FIELDS, **overrides}
    return _owner().issue_repair_authorization(**fields)


def _consume(token, **overrides):
    fields = {**_FIELDS, **overrides}
    return _owner().consume_repair_authorization(token, **fields)


def test_owner_issued_authorization_consumes_once_on_exact_tuple() -> None:
    token = _issue()
    assert _consume(token) is token
    with pytest.raises(_owner().RepairAuthorizationError) as exc_info:
        _consume(token)
    assert exc_info.value.code == "ALREADY_CONSUMED"


def test_authorization_identity_is_server_owned_and_not_caller_chosen() -> None:
    token = _issue()
    assert type(token.authorization_id) is str
    assert token.authorization_id
    with pytest.raises(_owner().RepairAuthorizationError):
        _issue(authorization_id="caller-chosen")


def test_concurrent_exact_consumers_have_exactly_one_winner() -> None:
    token = _issue()

    def attempt():
        try:
            return _consume(token)
        except BaseException as exc:  # noqa: BLE001 - categorical outcome oracle
            return exc

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(8)))
    assert sum(result is token for result in outcomes) == 1
    failures = [result for result in outcomes if result is not token]
    assert failures
    assert all(isinstance(result, _owner().RepairAuthorizationError) for result in failures)
    assert {result.code for result in failures} == {"ALREADY_CONSUMED"}


@pytest.mark.parametrize(
    "field",
    [
        "run_id",
        "work_item_id",
        "candidate_revision_id",
        "r5_failure_id",
        "r5_failure_sha256",
        "repair_plan_id",
        "repair_plan_sha256",
        "repair_plan_version",
        "repair_operation_contract_version",
        "repair_operation_contract_fingerprint",
    ],
)
def test_wrong_bound_tuple_rejects_without_burning_authorization(field: str) -> None:
    token = _issue()
    changed = "foreign-value"
    if field.endswith("sha256") or field.endswith("fingerprint"):
        changed = "d" * 64
    with pytest.raises(_owner().RepairAuthorizationError) as exc_info:
        _consume(token, **{field: changed})
    assert exc_info.value.code == "TUPLE_MISMATCH"
    assert _consume(token) is token


def test_expired_authorization_rejects_without_payload_leakage(monkeypatch) -> None:
    owner = _owner()
    clock = [datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(owner, "_utc_now", lambda: clock[0])
    token = _issue(ttl_seconds=1)
    clock[0] += timedelta(seconds=2)
    with pytest.raises(owner.RepairAuthorizationError) as exc_info:
        _consume(token)
    assert exc_info.value.code == "EXPIRED"
    assert "run-r6-001" not in str(exc_info.value)
    assert "repair-plan-001" not in str(exc_info.value)


def test_caller_constructed_copy_and_equal_field_fake_are_rejected() -> None:
    owner = _owner()
    token = _issue()
    forged = object.__new__(owner.RepairAuthorization)
    for name in owner.RepairAuthorization._public_fields:
        object.__setattr__(forged, f"_{name}", getattr(token, name))
    copied = copy.copy(token)
    for fake in (forged, copied):
        with pytest.raises(owner.RepairAuthorizationError) as exc_info:
            _consume(fake)
        assert exc_info.value.code == "PROVENANCE_MISSING"
    assert _consume(token) is token


class _HostileString(str):
    def __eq__(self, other):  # pragma: no cover - should never be called
        raise AssertionError("hostile equality was invoked")

    def __hash__(self):  # pragma: no cover - should never be called
        raise AssertionError("hostile hash was invoked")


def test_hostile_string_subclass_cannot_satisfy_tuple_comparison() -> None:
    token = _issue()
    with pytest.raises(_owner().RepairAuthorizationError) as exc_info:
        _consume(token, run_id=_HostileString(_FIELDS["run_id"]))
    assert exc_info.value.code == "TUPLE_INVALID"
    assert _consume(token) is token


def test_bool_and_numeric_ambiguity_is_rejected() -> None:
    owner = _owner()
    with pytest.raises(owner.RepairAuthorizationError) as exc_info:
        _issue(ttl_seconds=True)
    assert exc_info.value.code == "MALFORMED"


def test_unknown_fields_are_rejected_and_do_not_burn() -> None:
    owner = _owner()
    with pytest.raises(owner.RepairAuthorizationError) as exc_info:
        _issue(unexpected_field="nope")
    assert exc_info.value.code == "MALFORMED"
    token = _issue()
    with pytest.raises(owner.RepairAuthorizationError) as exc_info:
        _consume(token, unexpected_field="nope")
    assert exc_info.value.code == "MALFORMED"
    assert _consume(token) is token


def test_issued_record_is_immutable_and_consumed_state_is_not_public() -> None:
    owner = _owner()
    token = _issue()
    assert not hasattr(token, "consumed")
    with pytest.raises(AttributeError):
        token.authorization_id = "caller-mutation"
    assert _consume(token) is token


@pytest.mark.parametrize(
    "slot",
    [
        "_authorization_id",
        "_tuple_values",
        "_created_at",
        "_expires_at",
    ],
)
def test_post_issue_handle_slot_tamper_fails_without_burning_canonical_authority(
    slot: str,
) -> None:
    owner = _owner()
    token = _issue()
    original = getattr(token, slot)
    if slot == "_authorization_id":
        replacement: object = "forged-authorization-id"
    elif slot == "_tuple_values":
        replacement = ("foreign-run",) + original[1:]
    elif slot == "_created_at":
        replacement = datetime(2026, 8, 12, 0, 1, tzinfo=timezone.utc)
    else:
        replacement = datetime(2026, 8, 13, 0, 0, tzinfo=timezone.utc)
    object.__setattr__(token, slot, replacement)
    with pytest.raises(owner.RepairAuthorizationError) as exc_info:
        _consume(token)
    assert exc_info.value.code == "INTEGRITY_INVALID"
    object.__setattr__(token, slot, original)
    assert _consume(token) is token


def test_operation_contract_binding_accepts_absent_optional_fingerprint() -> None:
    token = _issue(
        repair_operation_contract_version=None,
        repair_operation_contract_fingerprint=None,
    )
    assert _consume(
        token,
        repair_operation_contract_version=None,
        repair_operation_contract_fingerprint=None,
    ) is token


def test_privacy_safe_categories_do_not_echo_secret_or_path() -> None:
    owner = _owner()
    secret = r"C:\private\customer\drawing.dwg"
    token = _issue(run_id=secret)
    with pytest.raises(owner.RepairAuthorizationError) as exc_info:
        _consume(token, run_id="foreign")
    assert str(exc_info.value) == "TUPLE_MISMATCH"
    assert secret not in str(exc_info.value)


def test_registry_uses_weak_lifetime_without_public_mutable_store() -> None:
    owner = _owner()
    assert not hasattr(owner, "register_repair_authorization")
    assert not hasattr(owner, "reset_repair_authorizations")
    token = _issue()
    assert not hasattr(token, "_consumed")
    assert _consume(token) is token
