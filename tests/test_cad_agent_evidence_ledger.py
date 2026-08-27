from __future__ import annotations

import copy

import pytest

from cad_agent.evidence_ledger import (
    EvidenceLedgerError,
    first_unsatisfied_gate,
    make_verification_receipt,
    validate_verification_receipt,
)


HEAD = "1" * 40
OLD_HEAD = "2" * 40
ARTIFACT = "artifact:global-png:abc123"


def _receipt(
    gate_id: str,
    verdict: str = "PASS",
    *,
    head_sha: str = HEAD,
    artifact_identity: str = "NONE",
) -> dict[str, object]:
    return make_verification_receipt(
        head_sha=head_sha,
        gate_id=gate_id,
        artifact_identity=artifact_identity,
        verification_class="OFFLINE_DETERMINISTIC",
        verdict=verdict,
        source_evidence_ref=f"github:run:{gate_id}",
        verifier_role="SOL_WEB",
        observed_at="2026-08-27T10:00:00Z",
    )


def _contract(*, reuse_relations: list[dict[str, str]] | None = None) -> dict[str, object]:
    return {
        "schema_version": "cad-acceptance-contract-1.0",
        "gates": [
            {
                "gate_id": "SNAPSHOT",
                "verification_class": "OFFLINE_DETERMINISTIC",
                "artifact_bound": False,
            },
            {
                "gate_id": "GLOBAL_ARTIFACT",
                "verification_class": "OFFLINE_DETERMINISTIC",
                "artifact_bound": True,
            },
            {
                "gate_id": "CLEANUP",
                "verification_class": "OFFLINE_DETERMINISTIC",
                "artifact_bound": False,
            },
        ],
        "reuse_relations": reuse_relations or [],
    }


def test_receipt_round_trip_and_tamper_detection() -> None:
    receipt = _receipt("SNAPSHOT")
    assert validate_verification_receipt(receipt) == receipt

    tampered = copy.deepcopy(receipt)
    tampered["verdict"] = "FAIL"
    with pytest.raises(EvidenceLedgerError, match="receipt_sha256"):
        validate_verification_receipt(tampered)


@pytest.mark.parametrize("verdict", ["FAIL", "SKIP", "NOT_RUN", "BLOCKED"])
def test_non_pass_verdicts_do_not_satisfy_required_gate(verdict: str) -> None:
    receipts = [_receipt("SNAPSHOT", verdict)]
    assert (
        first_unsatisfied_gate(
            _contract(), receipts, head_sha=HEAD, artifact_identity=ARTIFACT
        )
        == "SNAPSHOT"
    )


def test_not_required_is_explicitly_satisfying() -> None:
    receipts = [
        _receipt("SNAPSHOT", "NOT_REQUIRED"),
        _receipt("GLOBAL_ARTIFACT", artifact_identity=ARTIFACT),
        _receipt("CLEANUP"),
    ]
    assert (
        first_unsatisfied_gate(
            _contract(), receipts, head_sha=HEAD, artifact_identity=ARTIFACT
        )
        is None
    )


def test_returns_first_unsatisfied_gate_in_contract_order() -> None:
    receipts = [_receipt("SNAPSHOT")]
    assert (
        first_unsatisfied_gate(
            _contract(), receipts, head_sha=HEAD, artifact_identity=ARTIFACT
        )
        == "GLOBAL_ARTIFACT"
    )


def test_artifact_bound_receipt_cannot_transfer_to_other_artifact() -> None:
    receipts = [
        _receipt("SNAPSHOT"),
        _receipt("GLOBAL_ARTIFACT", artifact_identity="artifact:other"),
    ]
    assert (
        first_unsatisfied_gate(
            _contract(), receipts, head_sha=HEAD, artifact_identity=ARTIFACT
        )
        == "GLOBAL_ARTIFACT"
    )


def test_head_bound_receipt_cannot_transfer_without_explicit_relation() -> None:
    receipts = [_receipt("SNAPSHOT", head_sha=OLD_HEAD)]
    assert (
        first_unsatisfied_gate(
            _contract(), receipts, head_sha=HEAD, artifact_identity=ARTIFACT
        )
        == "SNAPSHOT"
    )


def test_exact_reuse_relation_can_transfer_one_named_gate_only() -> None:
    receipts = [
        _receipt("SNAPSHOT", head_sha=OLD_HEAD),
        _receipt("GLOBAL_ARTIFACT", head_sha=HEAD, artifact_identity=ARTIFACT),
        _receipt("CLEANUP", head_sha=HEAD),
    ]
    contract = _contract(
        reuse_relations=[
            {
                "from_head_sha": OLD_HEAD,
                "to_head_sha": HEAD,
                "gate_id": "SNAPSHOT",
                "artifact_identity": "NONE",
                "source_ref": "issue:131#accepted-reuse",
            }
        ]
    )
    assert (
        first_unsatisfied_gate(
            contract, receipts, head_sha=HEAD, artifact_identity=ARTIFACT
        )
        is None
    )


def test_rejects_unknown_verdict() -> None:
    with pytest.raises(EvidenceLedgerError, match="verdict"):
        _receipt("SNAPSHOT", "MAYBE")
