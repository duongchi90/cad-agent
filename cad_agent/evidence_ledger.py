"""Pure verification receipt validation and acceptance queries.

Receipts are derived evidence references, not a second acceptance/currentness store.
This module performs no persistence and grants no authority.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from cad_agent.drawing_contracts import canonical_json_sha256


RECEIPT_SCHEMA_VERSION = "cad-verification-receipt-1.0"
ACCEPTANCE_SCHEMA_VERSION = "cad-acceptance-contract-1.0"
VERDICTS = frozenset(
    {"PASS", "FAIL", "NOT_RUN", "SKIP", "BLOCKED", "NOT_REQUIRED"}
)
SATISFYING_VERDICTS = frozenset({"PASS", "NOT_REQUIRED"})
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "head_sha",
        "gate_id",
        "artifact_identity",
        "verification_class",
        "verdict",
        "source_evidence_ref",
        "verifier_role",
        "observed_at",
        "receipt_sha256",
    }
)


class EvidenceLedgerError(ValueError):
    """Raised when a verification receipt or acceptance contract is invalid."""


def _fail(message: str) -> None:
    raise EvidenceLedgerError(message)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")
    return value


def _sha(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _GIT_SHA.fullmatch(text) is None:
        _fail(f"{field} must be a lowercase 40-character Git SHA")
    return text


def _closed(
    value: Mapping[str, object], *, fields: frozenset[str], name: str
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{name} must be a mapping")
    keys = set(value)
    missing = sorted(fields - keys)
    unexpected = sorted(keys - fields)
    if missing:
        _fail(f"{name} missing required fields: {', '.join(missing)}")
    if unexpected:
        _fail(f"{name} has unexpected fields: {', '.join(unexpected)}")
    return dict(value)


def make_verification_receipt(
    *,
    head_sha: str,
    gate_id: str,
    artifact_identity: str,
    verification_class: str,
    verdict: str,
    source_evidence_ref: str,
    verifier_role: str,
    observed_at: str,
) -> dict[str, object]:
    """Create one sealed verification receipt from an exact evidence event."""

    normalized_verdict = _text(verdict, field="verdict")
    if normalized_verdict not in VERDICTS:
        _fail(f"verdict must be one of {sorted(VERDICTS)}")
    material: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "head_sha": _sha(head_sha, field="head_sha"),
        "gate_id": _text(gate_id, field="gate_id"),
        "artifact_identity": _text(artifact_identity, field="artifact_identity"),
        "verification_class": _text(
            verification_class, field="verification_class"
        ),
        "verdict": normalized_verdict,
        "source_evidence_ref": _text(
            source_evidence_ref, field="source_evidence_ref"
        ),
        "verifier_role": _text(verifier_role, field="verifier_role"),
        "observed_at": _text(observed_at, field="observed_at"),
    }
    return {**material, "receipt_sha256": canonical_json_sha256(material)}


def validate_verification_receipt(
    receipt: Mapping[str, object],
) -> dict[str, object]:
    """Validate closed receipt shape and exact canonical seal."""

    payload = _closed(receipt, fields=_RECEIPT_FIELDS, name="receipt")
    if payload["schema_version"] != RECEIPT_SCHEMA_VERSION:
        _fail(f"schema_version must be {RECEIPT_SCHEMA_VERSION!r}")
    verdict = _text(payload["verdict"], field="verdict")
    if verdict not in VERDICTS:
        _fail(f"verdict must be one of {sorted(VERDICTS)}")
    material: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "head_sha": _sha(payload["head_sha"], field="head_sha"),
        "gate_id": _text(payload["gate_id"], field="gate_id"),
        "artifact_identity": _text(
            payload["artifact_identity"], field="artifact_identity"
        ),
        "verification_class": _text(
            payload["verification_class"], field="verification_class"
        ),
        "verdict": verdict,
        "source_evidence_ref": _text(
            payload["source_evidence_ref"], field="source_evidence_ref"
        ),
        "verifier_role": _text(payload["verifier_role"], field="verifier_role"),
        "observed_at": _text(payload["observed_at"], field="observed_at"),
    }
    supplied = _text(payload["receipt_sha256"], field="receipt_sha256")
    if re.fullmatch(r"[0-9a-f]{64}", supplied) is None:
        _fail("receipt_sha256 must be a lowercase SHA-256")
    expected = canonical_json_sha256(material)
    if supplied != expected:
        _fail("receipt_sha256 does not match canonical receipt material")
    canonical = {**material, "receipt_sha256": supplied}
    if dict(payload) != canonical:
        _fail("receipt is not in canonical normalized form")
    return canonical


def _validate_contract(
    acceptance_contract: Mapping[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    payload = _closed(
        acceptance_contract,
        fields=frozenset({"schema_version", "gates", "reuse_relations"}),
        name="acceptance_contract",
    )
    if payload["schema_version"] != ACCEPTANCE_SCHEMA_VERSION:
        _fail(f"acceptance schema_version must be {ACCEPTANCE_SCHEMA_VERSION!r}")
    gates_value = payload["gates"]
    if isinstance(gates_value, (str, bytes)) or not isinstance(gates_value, Sequence):
        _fail("gates must be a list")
    gates: list[dict[str, object]] = []
    gate_ids: set[str] = set()
    for index, item in enumerate(gates_value):
        if not isinstance(item, Mapping) or set(item) != {
            "gate_id",
            "verification_class",
            "artifact_bound",
        }:
            _fail(f"gates[{index}] has invalid closed shape")
        gate_id = _text(item["gate_id"], field=f"gates[{index}].gate_id")
        if gate_id in gate_ids:
            _fail("gate_id values must be unique")
        gate_ids.add(gate_id)
        artifact_bound = item["artifact_bound"]
        if not isinstance(artifact_bound, bool):
            _fail(f"gates[{index}].artifact_bound must be boolean")
        gates.append(
            {
                "gate_id": gate_id,
                "verification_class": _text(
                    item["verification_class"],
                    field=f"gates[{index}].verification_class",
                ),
                "artifact_bound": artifact_bound,
            }
        )
    if not gates:
        _fail("gates must be non-empty")

    relations_value = payload["reuse_relations"]
    if isinstance(relations_value, (str, bytes)) or not isinstance(
        relations_value, Sequence
    ):
        _fail("reuse_relations must be a list")
    relations: list[dict[str, str]] = []
    for index, item in enumerate(relations_value):
        if not isinstance(item, Mapping) or set(item) != {
            "from_head_sha",
            "to_head_sha",
            "gate_id",
            "artifact_identity",
            "source_ref",
        }:
            _fail(f"reuse_relations[{index}] has invalid closed shape")
        relation = {
            "from_head_sha": _sha(
                item["from_head_sha"],
                field=f"reuse_relations[{index}].from_head_sha",
            ),
            "to_head_sha": _sha(
                item["to_head_sha"], field=f"reuse_relations[{index}].to_head_sha"
            ),
            "gate_id": _text(
                item["gate_id"], field=f"reuse_relations[{index}].gate_id"
            ),
            "artifact_identity": _text(
                item["artifact_identity"],
                field=f"reuse_relations[{index}].artifact_identity",
            ),
            "source_ref": _text(
                item["source_ref"], field=f"reuse_relations[{index}].source_ref"
            ),
        }
        if relation["gate_id"] not in gate_ids:
            _fail(f"reuse_relations[{index}].gate_id is not declared")
        relations.append(relation)
    return gates, relations


def _relation_allows(
    relations: Sequence[Mapping[str, str]],
    *,
    receipt_head: str,
    target_head: str,
    gate_id: str,
    artifact_identity: str,
) -> bool:
    return any(
        relation["from_head_sha"] == receipt_head
        and relation["to_head_sha"] == target_head
        and relation["gate_id"] == gate_id
        and relation["artifact_identity"] == artifact_identity
        for relation in relations
    )


def _select_gate_receipts(
    validated: Sequence[Mapping[str, object]],
    relations: Sequence[Mapping[str, str]],
    *,
    gate_id: str,
    verification_class: str,
    target_head: str,
    expected_artifact: str,
) -> list[Mapping[str, object]]:
    matching = [
        receipt
        for receipt in validated
        if receipt["gate_id"] == gate_id
        and receipt["verification_class"] == verification_class
        and receipt["artifact_identity"] == expected_artifact
    ]
    current = [receipt for receipt in matching if receipt["head_sha"] == target_head]
    if current:
        return current
    return [
        receipt
        for receipt in matching
        if _relation_allows(
            relations,
            receipt_head=str(receipt["head_sha"]),
            target_head=target_head,
            gate_id=gate_id,
            artifact_identity=expected_artifact,
        )
    ]


def first_unsatisfied_gate(
    acceptance_contract: Mapping[str, object],
    receipts: Sequence[Mapping[str, object]],
    *,
    head_sha: str,
    artifact_identity: str = "NONE",
) -> str | None:
    """Return the first ordered acceptance gate lacking exact satisfying evidence."""

    target_head = _sha(head_sha, field="head_sha")
    target_artifact = _text(artifact_identity, field="artifact_identity")
    gates, relations = _validate_contract(acceptance_contract)
    if isinstance(receipts, (str, bytes)) or not isinstance(receipts, Sequence):
        _fail("receipts must be a list")
    validated = [validate_verification_receipt(receipt) for receipt in receipts]

    for gate in gates:
        gate_id = str(gate["gate_id"])
        verification_class = str(gate["verification_class"])
        expected_artifact = target_artifact if gate["artifact_bound"] else "NONE"
        candidates = _select_gate_receipts(
            validated,
            relations,
            gate_id=gate_id,
            verification_class=verification_class,
            target_head=target_head,
            expected_artifact=expected_artifact,
        )
        if not candidates:
            return gate_id
        verdicts = {str(receipt["verdict"]) for receipt in candidates}
        if len(verdicts) > 1:
            provenance = (
                "current"
                if any(receipt["head_sha"] == target_head for receipt in candidates)
                else "reused"
            )
            _fail(f"conflicting {provenance} receipts for gate {gate_id}")
        verdict = next(iter(verdicts))
        if verdict not in SATISFYING_VERDICTS:
            return gate_id
    return None
