"""Server-owned, single-use authorization consumption for production repair.

This module is deliberately a small process-local seam.  It does not issue an
engineering verdict, execute a repair operation, publish a drawing, or persist
authorization state.  The issued token is an opaque object whose provenance is
the private weak registry below; equal fields on another object are not enough
to authorize consumption.
"""

from __future__ import annotations

import math
import secrets
import threading
import weakref
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


REPAIR_AUTHORIZATION_SCHEMA_VERSION = "repair-authorization-1.0"
REPAIR_AUTHORIZATION_VERSION = REPAIR_AUTHORIZATION_SCHEMA_VERSION
MAX_AUTHORIZATION_TTL_SECONDS = 24 * 60 * 60

_BOUND_FIELDS = (
    "run_id",
    "work_item_id",
    "candidate_revision_id",
    "candidate_revision_sha256",
    "r5_failure_id",
    "r5_failure_sha256",
    "repair_plan_id",
    "repair_plan_sha256",
    "repair_plan_version",
    "repair_operation_contract_version",
    "repair_operation_contract_fingerprint",
)
_REQUIRED_FIELDS = frozenset(
    {
        "run_id",
        "work_item_id",
        "candidate_revision_id",
        "r5_failure_id",
        "r5_failure_sha256",
        "repair_plan_id",
        "repair_plan_sha256",
        "repair_plan_version",
    }
)
_OPTIONAL_FIELDS = frozenset(
    {
        "candidate_revision_sha256",
        "repair_operation_contract_version",
        "repair_operation_contract_fingerprint",
    }
)

# The aliases retain compatibility with the vocabulary used by the accepted
# R4/R5 owners while maintaining one canonical internal tuple.
_ALIASES: dict[str, tuple[str, ...]] = {
    "run_id": ("run_id",),
    "work_item_id": ("work_item_id", "repair_work_item_id"),
    "candidate_revision_id": ("candidate_revision_id", "r4_candidate_revision_id"),
    "candidate_revision_sha256": (
        "candidate_revision_sha256",
        "candidate_revision_hash",
        "r4_candidate_revision_sha256",
    ),
    "r5_failure_id": (
        "r5_failure_id",
        "r5_verdict_id",
        "r5_fail_verdict_id",
        "r5_failure_reference",
    ),
    "r5_failure_sha256": (
        "r5_failure_sha256",
        "r5_failure_hash",
        "r5_verdict_sha256",
        "r5_verdict_hash",
        "r5_fail_verdict_sha256",
        "r5_fail_verdict_hash",
    ),
    "repair_plan_id": ("repair_plan_id", "r5_repair_plan_id"),
    "repair_plan_sha256": (
        "repair_plan_sha256",
        "repair_plan_hash",
        "r5_repair_plan_sha256",
    ),
    "repair_plan_version": ("repair_plan_version", "r5_repair_plan_version"),
    "repair_operation_contract_version": (
        "repair_operation_contract_version",
        "operation_contract_version",
        "repair_operation_version",
    ),
    "repair_operation_contract_fingerprint": (
        "repair_operation_contract_fingerprint",
        "operation_contract_fingerprint",
        "repair_operation_fingerprint",
        "operation_fingerprint",
    ),
}
_KNOWN_INPUT_FIELDS = frozenset(
    alias for aliases in _ALIASES.values() for alias in aliases
) | {"ttl_seconds", "ttl", "expires_in"}


class RepairAuthorizationError(ValueError):
    """Categorical, privacy-safe failure from the repair authorization seam."""

    _CODES = frozenset(
        {
            "MALFORMED",
            "TUPLE_INVALID",
            "TUPLE_MISMATCH",
            "INTEGRITY_INVALID",
            "PROVENANCE_MISSING",
            "EXPIRED",
            "ALREADY_CONSUMED",
        }
    )

    def __init__(self, code: str) -> None:
        if type(code) is not str or code not in self._CODES:
            code = "MALFORMED"
        self.code = code
        super().__init__(code)


def _fail(code: str) -> None:
    raise RepairAuthorizationError(code)


def _utc_now() -> datetime:
    """Return the owner clock; tests may replace this private seam."""

    return datetime.now(timezone.utc)


def _validate_text(value: object, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if type(value) is not str or not value:
        _fail("TUPLE_INVALID")
    return value


def _validate_clock(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        _fail("MALFORMED")
    return value.astimezone(timezone.utc)


def _normalise_fields(raw: dict[str, object], *, consume: bool) -> tuple[dict[str, str | None], float | None]:
    """Validate a caller tuple without invoking hostile equality/hash hooks."""

    if type(raw) is not dict:
        _fail("MALFORMED")
    if any(type(key) is not str for key in raw):
        _fail("MALFORMED")
    if any(key not in _KNOWN_INPUT_FIELDS for key in raw):
        _fail("MALFORMED")

    ttl_keys = [key for key in ("ttl_seconds", "ttl", "expires_in") if key in raw]
    if consume and ttl_keys:
        _fail("MALFORMED")
    if len(ttl_keys) > 1:
        _fail("MALFORMED")
    ttl: float | None = None
    if ttl_keys:
        candidate_ttl = raw[ttl_keys[0]]
        if type(candidate_ttl) is timedelta:
            ttl = candidate_ttl.total_seconds()
        elif type(candidate_ttl) in (int, float) and not isinstance(candidate_ttl, bool):
            ttl = float(candidate_ttl)
        else:
            _fail("MALFORMED")
        if not math.isfinite(ttl) or ttl <= 0 or ttl > MAX_AUTHORIZATION_TTL_SECONDS:
            _fail("MALFORMED")

    values: dict[str, str | None] = {}
    for canonical in _BOUND_FIELDS:
        aliases = _ALIASES[canonical]
        present = [alias for alias in aliases if alias in raw]
        if len(present) > 1:
            _fail("MALFORMED")
        if not present:
            if canonical in _REQUIRED_FIELDS:
                _fail("MALFORMED")
            values[canonical] = None
            continue
        optional = canonical in _OPTIONAL_FIELDS
        values[canonical] = _validate_text(raw[present[0]], optional=optional)
    return values, ttl


class RepairAuthorization:
    """Opaque immutable handle minted only by :func:`issue_repair_authorization`."""

    __slots__ = (
        "_authorization_id",
        "_tuple_values",
        "_created_at",
        "_expires_at",
        "__weakref__",
    )
    # Kept private-by-convention for focused provenance tests; this is not an
    # issuance or registration API.
    _public_fields = ("authorization_id", "tuple_values", "created_at", "expires_at")

    def __new__(cls, *args: object, **kwargs: object) -> RepairAuthorization:
        del args, kwargs
        raise TypeError("RepairAuthorization is owner-issued")

    @classmethod
    def _mint(
        cls,
        *,
        authorization_id: str,
        tuple_values: tuple[str | None, ...],
        created_at: datetime,
        expires_at: datetime,
    ) -> RepairAuthorization:
        token = object.__new__(cls)
        object.__setattr__(token, "_authorization_id", authorization_id)
        object.__setattr__(token, "_tuple_values", tuple_values)
        object.__setattr__(token, "_created_at", created_at)
        object.__setattr__(token, "_expires_at", expires_at)
        return token

    @property
    def authorization_id(self) -> str:
        return self._authorization_id

    @property
    def tuple_values(self) -> tuple[str | None, ...]:
        return self._tuple_values

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def expires_at(self) -> datetime:
        return self._expires_at

    def __repr__(self) -> str:
        return "<RepairAuthorization owner-issued>"

    def __copy__(self) -> RepairAuthorization:
        return self._mint(
            authorization_id=self._authorization_id,
            tuple_values=self._tuple_values,
            created_at=self._created_at,
            expires_at=self._expires_at,
        )

    def __deepcopy__(self, memo: dict[int, object]) -> RepairAuthorization:
        del memo
        return self.__copy__()

    def __reduce__(self) -> object:
        raise TypeError("RepairAuthorization cannot be serialized")


@dataclass
class _AuthorizationState:
    authorization_id: str
    tuple_values: tuple[str | None, ...]
    created_at: datetime
    expires_at: datetime
    consumed: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


_REGISTRY_LOCK = threading.RLock()
_ISSUED: weakref.WeakKeyDictionary[RepairAuthorization, _AuthorizationState] = (
    weakref.WeakKeyDictionary()
)


def issue_repair_authorization(**raw_fields: object) -> RepairAuthorization:
    """Mint one server-owned, single-use repair authorization handle."""

    values, ttl = _normalise_fields(raw_fields, consume=False)
    if ttl is None:
        ttl = 300.0
    created_at = _validate_clock(_utc_now())
    expires_at = created_at + timedelta(seconds=ttl)
    authorization_id = secrets.token_hex(32)
    tuple_values = tuple(values[field] for field in _BOUND_FIELDS)
    token = RepairAuthorization._mint(
        authorization_id=authorization_id,
        tuple_values=tuple_values,
        created_at=created_at,
        expires_at=expires_at,
    )
    state = _AuthorizationState(
        authorization_id=authorization_id,
        tuple_values=tuple_values,
        created_at=created_at,
        expires_at=expires_at,
    )
    with _REGISTRY_LOCK:
        _ISSUED[token] = state
    return token


def _handle_matches_issuance_snapshot(
    authorization: RepairAuthorization, state: _AuthorizationState
) -> bool:
    """Compare caller-visible handle fields to the private issuance snapshot."""

    if type(authorization._authorization_id) is not str:
        return False
    if authorization._authorization_id != state.authorization_id:
        return False
    if type(authorization._tuple_values) is not tuple:
        return False
    if len(authorization._tuple_values) != len(state.tuple_values):
        return False
    for actual, expected in zip(authorization._tuple_values, state.tuple_values):
        if actual is None or expected is None:
            if actual is not expected:
                return False
        elif type(actual) is not str or type(expected) is not str:
            return False
        elif actual != expected:
            return False
    if type(authorization._created_at) is not datetime:
        return False
    if type(authorization._expires_at) is not datetime:
        return False
    if authorization._created_at.tzinfo is not timezone.utc:
        return False
    if authorization._expires_at.tzinfo is not timezone.utc:
        return False
    if state.created_at.tzinfo is not timezone.utc:
        return False
    if state.expires_at.tzinfo is not timezone.utc:
        return False
    return (
        authorization._created_at == state.created_at
        and authorization._expires_at == state.expires_at
    )


def consume_repair_authorization(
    authorization: object, **raw_fields: object
) -> RepairAuthorization:
    """Atomically consume one exact, unexpired owner-issued authorization."""

    if type(authorization) is not RepairAuthorization:
        _fail("PROVENANCE_MISSING")
    expected, _ = _normalise_fields(raw_fields, consume=True)
    expected_tuple = tuple(expected[field] for field in _BOUND_FIELDS)
    with _REGISTRY_LOCK:
        state = _ISSUED.get(authorization)
    if state is None:
        _fail("PROVENANCE_MISSING")

    with state.lock:
        if state.consumed:
            _fail("ALREADY_CONSUMED")
        if not _handle_matches_issuance_snapshot(authorization, state):
            _fail("INTEGRITY_INVALID")
        if _validate_clock(_utc_now()) >= state.expires_at:
            _fail("EXPIRED")
        if any(
            type(actual) is not type(expected_value) or actual != expected_value
            for actual, expected_value in zip(state.tuple_values, expected_tuple)
        ):
            _fail("TUPLE_MISMATCH")
        state.consumed = True
    return authorization  # type: ignore[return-value]


__all__ = [
    "MAX_AUTHORIZATION_TTL_SECONDS",
    "REPAIR_AUTHORIZATION_SCHEMA_VERSION",
    "REPAIR_AUTHORIZATION_VERSION",
    "RepairAuthorization",
    "RepairAuthorizationError",
    "consume_repair_authorization",
    "issue_repair_authorization",
]
