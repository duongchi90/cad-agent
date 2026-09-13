from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from cad_agent import source_bound_semantic_occurrence_authority as authority_module
from cad_agent.source_bound_semantic_occurrence_authority import (
    validate_source_bound_semantic_occurrence_authority,
)
from cad_agent.source_integrity import source_custody_sha256
from tests.test_cad_agent_source_fusion import (
    PDF_RASTER_SHA256,
    OTHER_PRIMITIVE_ARTIFACT_SHA256,
    PDF_SHA256,
    PRIMITIVE_ARTIFACT_SHA256,
    _custody,
    _page_payload,
    _pdf_render_record,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "source-bound-semantic-occurrence-authority-v1.json"
)


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_approved_authority_v1_contract_is_validated_fail_closed() -> None:
    """The selected adjacent owner validates the approved contract and oracle."""
    payload = _fixture()
    result = validate_source_bound_semantic_occurrence_authority(
        payload,
    )
    assert result["contract_version"] == "SOURCE_BOUND_SEMANTIC_OCCURRENCE_AUTHORITY_V1"
    assert result["currentness"] == "UNRESOLVED_NON_PASS"
    assert {
        case["case_id"]: case["status"]
        for case in result["oracle_results"]
    } == {
        "DISTINCT_PARALLEL_OCCURRENCES": "DISTINCT",
        "SAME_OCCURRENCE_DUPLICATE_OBSERVATIONS": "SAME_OCCURRENCE",
        "MULTI_MATCH": "UNRESOLVED_NON_PASS",
        "STALE_RENDER_BINDING": "UNRESOLVED_NON_PASS",
    }

    stale_binding = deepcopy(payload["source"])
    stale_binding["render_sha256"] = "333" * 21 + "3"
    stale_result = validate_source_bound_semantic_occurrence_authority(
        payload,
        current_source_binding=stale_binding,
    )
    assert stale_result["currentness"] == "UNRESOLVED_NON_PASS"


def test_self_echoed_binding_without_owner_evidence_cannot_grant_currentness() -> None:
    payload = _fixture()
    result = validate_source_bound_semantic_occurrence_authority(
        payload,
        current_source_binding=payload["source"],
    )
    assert result["currentness"] == "UNRESOLVED_NON_PASS"


def test_zero_match_is_fail_closed() -> None:
    payload = _fixture()
    payload["oracle_cases"].append(
        {
            "case_id": "ZERO_MATCH",
            "observations": [
                {"candidate_id": "RAW-NONE", "matched_occurrence_ids": []}
            ],
            "expected": "UNRESOLVED_NON_PASS",
        }
    )
    try:
        result = validate_source_bound_semantic_occurrence_authority(payload)
    except Exception as exc:  # pragma: no cover - causal RED until ZERO_MATCH exists
        pytest.fail(f"ZERO_MATCH must return a fail-closed result: {exc}")
    assert {
        case["case_id"]: case["status"]
        for case in result["oracle_results"]
    }["ZERO_MATCH"] == "UNRESOLVED_NON_PASS"


def test_multi_match_aggregates_all_observations_fail_closed() -> None:
    payload = _fixture()
    payload["oracle_cases"][2]["observations"] = [
        {
            "candidate_id": "RAW-AMBIGUOUS",
            "matched_occurrence_ids": ["OCC-LINE-A", "OCC-LINE-B"],
        },
        {
            "candidate_id": "RAW-UNIQUE-LATER",
            "matched_occurrence_ids": ["OCC-LINE-A"],
        },
    ]

    result = validate_source_bound_semantic_occurrence_authority(payload)

    assert {
        case["case_id"]: case["status"]
        for case in result["oracle_results"]
    }["MULTI_MATCH"] == "UNRESOLVED_NON_PASS"


def test_currentness_consumes_existing_source_fusion_evidence() -> None:
    payload = _fixture()
    payload["source"].update(
        {
            "source_pdf_sha256": PDF_SHA256,
            "page_id": "PAGE-99",
            "render_sha256": PDF_RASTER_SHA256,
        }
    )
    payload["oracle_cases"][3]["source_render_sha256"] = "4" * 64
    custody = _custody()
    page_locators = _page_payload(custody)
    render_provenance = [_pdf_render_record(custody, page_locators)]
    normalized_render = authority_module._source_fusion.validate_render_provenance(
        render_provenance,
        page_locators=page_locators,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )[0]
    payload["source"]["render_transform"] = (
        authority_module._render_transform_identity(normalized_render)
    )
    result = validate_source_bound_semantic_occurrence_authority(
        payload,
        currentness_evidence={
            "render_provenance": render_provenance,
            "page_locators": page_locators,
            "custody": custody,
            "primitive_artifact_sha256": PRIMITIVE_ARTIFACT_SHA256,
        },
    )
    assert result["currentness"] == "CURRENT"


def test_caller_supplied_transform_label_cannot_grant_currentness() -> None:
    payload = _fixture()
    payload["source"].update(
        {
            "source_pdf_sha256": PDF_SHA256,
            "page_id": "PAGE-99",
            "render_sha256": PDF_RASTER_SHA256,
            "render_transform": "caller-controlled-transform",
        }
    )
    payload["oracle_cases"][3]["source_render_sha256"] = "4" * 64
    custody = _custody()
    page_locators = _page_payload(custody)
    render_provenance = [_pdf_render_record(custody, page_locators)]
    result = validate_source_bound_semantic_occurrence_authority(
        payload,
        currentness_evidence={
            "render_provenance": render_provenance,
            "page_locators": page_locators,
            "custody": custody,
            "primitive_artifact_sha256": PRIMITIVE_ARTIFACT_SHA256,
        },
    )
    assert result["currentness"] == "UNRESOLVED_NON_PASS"


def test_option_b_packet_hash_binding_is_lossless_and_fail_closed() -> None:
    """The canonical approval packet remains the downstream authority input."""
    custody = _custody()
    page_locators = _page_payload(custody)
    render_provenance = [_pdf_render_record(custody, page_locators)]
    normalized_render = authority_module._source_fusion.validate_render_provenance(
        render_provenance,
        page_locators=page_locators,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )[0]
    page_99 = next(page for page in page_locators if page["page_id"] == "PAGE-99")
    currentness_evidence = {
        "render_provenance": render_provenance,
        "page_locators": page_locators,
        "custody": custody,
        "primitive_artifact_sha256": PRIMITIVE_ARTIFACT_SHA256,
    }
    packet = {
        "schema_version": "source-bound-semantic-occurrence-approval-1.0",
        "contract_version": "SOURCE_BOUND_SEMANTIC_OCCURRENCE_APPROVAL_V1",
        "source": {
            "source_pdf_sha256": PDF_SHA256,
            "page_id": "PAGE-99",
            "render_sha256": PDF_RASTER_SHA256,
            "render_transform": authority_module._render_transform_identity(
                normalized_render
            ),
            "source_custody_sha256": source_custody_sha256(custody),
            "page_locator_sha256": page_99["page_locator_sha256"],
            "render_provenance_sha256": normalized_render[
                "render_provenance_sha256"
            ],
        },
        "approval": {
            "approval_identity": "APPROVAL-OPTION-B-001",
            "approved_by": "PO",
            "approval_ref": "github-409-comment-5651227165",
            "approved_at": "2026-09-13T12:00:00Z",
        },
        "occurrences": deepcopy(_fixture()["occurrences"]),
        "packet_hash": "",
    }

    def recompute_packet_hash(value: dict[str, object]) -> dict[str, object]:
        value["packet_hash"] = authority_module.canonical_json_sha256(
            {key: item for key, item in value.items() if key != "packet_hash"}
        )
        return value

    recompute_packet_hash(packet)
    verified_decision = (
        authority_module.VerifiedApprovalDecision._from_trusted_boundary(
            approval_identity=packet["approval"]["approval_identity"],
            approved_by=packet["approval"]["approved_by"],
            approval_ref=packet["approval"]["approval_ref"],
            scope={
                "scope_kind": "SOURCE_BOUND_SEMANTIC_OCCURRENCE",
                "source_pdf_sha256": packet["source"]["source_pdf_sha256"],
                "page_id": packet["source"]["page_id"],
                "render_sha256": packet["source"]["render_sha256"],
                "occurrence_ids": [
                    item["occurrence_id"] for item in packet["occurrences"]
                ],
            },
        )
    )
    producer = getattr(
        authority_module,
        "validate_source_bound_semantic_occurrence_approval",
        None,
    )
    assert callable(producer), (
        "OPTION_B RED: the approval packet producer/validator is not yet "
        "implemented in the selected adjacent owner"
    )

    validated = producer(
        packet,
        currentness_evidence=currentness_evidence,
        verified_approval_decision=verified_decision,
    )
    assert validated["currentness"] == "CURRENT"
    assert validated["packet_hash"] == packet["packet_hash"]

    def authority_payload() -> dict[str, object]:
        payload = _fixture()
        payload["source"].update(
            {
                "source_pdf_sha256": PDF_SHA256,
                "page_id": "PAGE-99",
                "render_sha256": PDF_RASTER_SHA256,
                "render_transform": packet["source"]["render_transform"],
            }
        )
        payload["oracle_cases"][3]["source_render_sha256"] = "4" * 64
        return payload

    def downstream(value: dict[str, object], approval: dict[str, object]) -> dict[str, object]:
        return validate_source_bound_semantic_occurrence_authority(
            value,
            currentness_evidence=currentness_evidence,
            validated_approval_packet=approval,
        )

    baseline = downstream(authority_payload(), validated)
    assert baseline["currentness"] == "CURRENT"

    mutations: list[tuple[str, dict[str, object]]] = []
    for field, replacement in (
        ("approved_by", "HUMAN"),
        ("approval_ref", "github-409-comment-CHANGED"),
    ):
        changed = deepcopy(packet)
        changed["approval"][field] = replacement
        mutations.append((field, recompute_packet_hash(changed)))
    for field, replacement in (
        ("source_custody_sha256", "7" * 64),
        ("page_locator_sha256", "8" * 64),
        ("render_provenance_sha256", "9" * 64),
    ):
        changed = deepcopy(packet)
        changed["source"][field] = replacement
        mutations.append((field, recompute_packet_hash(changed)))
    changed_occurrence = deepcopy(packet)
    changed_occurrence["occurrences"][0]["source_segment_px"]["p2"][0] += 1
    mutations.append(("occurrence_material", recompute_packet_hash(changed_occurrence)))

    for label, changed in mutations:
        try:
            changed_validated = producer(
                changed,
                currentness_evidence=currentness_evidence,
                verified_approval_decision=verified_decision,
            )
        except ValueError:
            assert label in {"approved_by", "approval_ref"}
            continue
        changed_result = downstream(authority_payload(), changed_validated)
        assert (
            changed_validated["packet_hash"] != validated["packet_hash"]
            or changed_validated["currentness"] != validated["currentness"]
        ), label
        assert changed_result["authority_sha256"] != baseline["authority_sha256"], label

    forged = deepcopy(packet)
    forged["packet_hash"] = "f" * 64
    try:
        forged_result = producer(
            forged,
            currentness_evidence=currentness_evidence,
            verified_approval_decision=verified_decision,
        )
    except ValueError:
        pass
    else:
        assert forged_result["currentness"] == "UNRESOLVED_NON_PASS"

    stale_evidence = deepcopy(currentness_evidence)
    stale_evidence["primitive_artifact_sha256"] = OTHER_PRIMITIVE_ARTIFACT_SHA256
    stale_result = producer(
        packet,
        currentness_evidence=stale_evidence,
        verified_approval_decision=verified_decision,
    )
    assert stale_result["currentness"] == "UNRESOLVED_NON_PASS"

    tampered_payload = authority_payload()
    tampered_payload["occurrences"][0]["source_segment_px"]["p2"][0] += 10
    tampered_result = downstream(tampered_payload, validated)
    assert tampered_result["authority_sha256"] == baseline["authority_sha256"]


def test_untrusted_approval_cannot_self_authorize_current_packet() -> None:
    """An approval requires an independent verifier result."""
    custody = _custody()
    page_locators = _page_payload(custody)
    render_provenance = [_pdf_render_record(custody, page_locators)]
    normalized_render = authority_module._source_fusion.validate_render_provenance(
        render_provenance,
        page_locators=page_locators,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )[0]
    page_99 = next(page for page in page_locators if page["page_id"] == "PAGE-99")
    currentness_evidence = {
        "render_provenance": render_provenance,
        "page_locators": page_locators,
        "custody": custody,
        "primitive_artifact_sha256": PRIMITIVE_ARTIFACT_SHA256,
    }
    packet = {
        "schema_version": "source-bound-semantic-occurrence-approval-1.0",
        "contract_version": "SOURCE_BOUND_SEMANTIC_OCCURRENCE_APPROVAL_V1",
        "source": {
            "source_pdf_sha256": PDF_SHA256,
            "page_id": "PAGE-99",
            "render_sha256": PDF_RASTER_SHA256,
            "render_transform": authority_module._render_transform_identity(
                normalized_render
            ),
            "source_custody_sha256": source_custody_sha256(custody),
            "page_locator_sha256": page_99["page_locator_sha256"],
            "render_provenance_sha256": normalized_render[
                "render_provenance_sha256"
            ],
        },
        "approval": {
            "approval_identity": "APPROVAL-OPTION-B-001",
            "approved_by": "PO",
            "approval_ref": "github-409-comment-5651227165",
            "approved_at": "2026-09-13T12:00:00Z",
        },
        "occurrences": deepcopy(_fixture()["occurrences"]),
        "packet_hash": "",
    }
    packet["packet_hash"] = authority_module.canonical_json_sha256(
        {key: item for key, item in packet.items() if key != "packet_hash"}
    )
    authorized_witness = (
        authority_module.VerifiedApprovalDecision._from_trusted_boundary(
            approval_identity=packet["approval"]["approval_identity"],
            approved_by=packet["approval"]["approved_by"],
            approval_ref=packet["approval"]["approval_ref"],
            scope={
                "scope_kind": "SOURCE_BOUND_SEMANTIC_OCCURRENCE",
                "source_pdf_sha256": packet["source"]["source_pdf_sha256"],
                "page_id": packet["source"]["page_id"],
                "render_sha256": packet["source"]["render_sha256"],
                "occurrence_ids": [
                    item["occurrence_id"] for item in packet["occurrences"]
                ],
            },
        )
    )

    try:
        authorized = authority_module.validate_source_bound_semantic_occurrence_approval(
            packet,
            currentness_evidence=currentness_evidence,
            verified_approval_decision=authorized_witness,
        )
    except ValueError:
        pytest.fail("the exact approved PO decision binding must remain usable")
    assert authorized["currentness"] == "CURRENT"

    def assert_rejected(untrusted_packet: dict[str, object]) -> None:
        untrusted_packet["packet_hash"] = authority_module.canonical_json_sha256(
            {
                key: item
                for key, item in untrusted_packet.items()
                if key != "packet_hash"
            }
        )
        try:
            validated = authority_module.validate_source_bound_semantic_occurrence_approval(
                untrusted_packet,
                currentness_evidence=currentness_evidence,
            )
        except ValueError:
            return

        authority_payload = _fixture()
        authority_payload["source"].update(
            {
                "source_pdf_sha256": PDF_SHA256,
                "page_id": "PAGE-99",
                "render_sha256": PDF_RASTER_SHA256,
                "render_transform": untrusted_packet["source"]["render_transform"],
            }
        )
        authority_payload["oracle_cases"][3]["source_render_sha256"] = "4" * 64
        downstream = validate_source_bound_semantic_occurrence_authority(
            authority_payload,
            currentness_evidence=currentness_evidence,
            validated_approval_packet=validated,
        )
        assert downstream["currentness"] == "UNRESOLVED_NON_PASS", (
            "APPROVAL_AUTHENTICITY RED: a correctly hashed untrusted approval "
            "must not reach CURRENT through the existing authority owner"
        )

    synthetic = deepcopy(packet)
    synthetic["approval"].update(
        {
            "approval_identity": "INVENTED-UNTRUSTED-001",
            "approval_ref": "synthetic-approval-ref",
        }
    )
    assert_rejected(synthetic)

    wrong_authority_class = deepcopy(packet)
    wrong_authority_class["approval"]["approved_by"] = "HUMAN"
    assert_rejected(wrong_authority_class)


def test_approval_requires_opaque_authenticated_decision_scope() -> None:
    """Approval follows only an opaque, scope-bound verifier result."""
    custody = _custody()
    page_locators = _page_payload(custody)
    render_provenance = [_pdf_render_record(custody, page_locators)]
    normalized_render = authority_module._source_fusion.validate_render_provenance(
        render_provenance,
        page_locators=page_locators,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )[0]
    page_99 = next(page for page in page_locators if page["page_id"] == "PAGE-99")
    currentness_evidence = {
        "render_provenance": render_provenance,
        "page_locators": page_locators,
        "custody": custody,
        "primitive_artifact_sha256": PRIMITIVE_ARTIFACT_SHA256,
    }
    occurrences = deepcopy(_fixture()["occurrences"])

    def make_packet(
        *, approval_identity: str, approved_by: str, approval_ref: str
    ) -> dict[str, object]:
        packet = {
            "schema_version": "source-bound-semantic-occurrence-approval-1.0",
            "contract_version": "SOURCE_BOUND_SEMANTIC_OCCURRENCE_APPROVAL_V1",
            "source": {
                "source_pdf_sha256": PDF_SHA256,
                "page_id": "PAGE-99",
                "render_sha256": PDF_RASTER_SHA256,
                "render_transform": authority_module._render_transform_identity(
                    normalized_render
                ),
                "source_custody_sha256": source_custody_sha256(custody),
                "page_locator_sha256": page_99["page_locator_sha256"],
                "render_provenance_sha256": normalized_render[
                    "render_provenance_sha256"
                ],
            },
            "approval": {
                "approval_identity": approval_identity,
                "approved_by": approved_by,
                "approval_ref": approval_ref,
                "approved_at": "2026-09-13T12:00:00Z",
            },
            "occurrences": deepcopy(occurrences),
            "packet_hash": "",
        }
        packet["packet_hash"] = authority_module.canonical_json_sha256(
            {key: item for key, item in packet.items() if key != "packet_hash"}
        )
        return packet

    occurrence_ids = [item["occurrence_id"] for item in occurrences]
    occurrence_scope = {
        "scope_kind": "SOURCE_BOUND_SEMANTIC_OCCURRENCE",
        "source_pdf_sha256": PDF_SHA256,
        "page_id": "PAGE-99",
        "render_sha256": PDF_RASTER_SHA256,
        "occurrence_ids": occurrence_ids,
    }
    occurrence_witness = authority_module.VerifiedApprovalDecision._from_trusted_boundary(
        approval_identity="TEST-OCCURRENCE-AUTHORITY-001",
        approved_by="PO",
        approval_ref="test-verified-occurrence-decision-001",
        scope=occurrence_scope,
    )
    contract_witness = authority_module.VerifiedApprovalDecision._from_trusted_boundary(
        approval_identity="APPROVAL-OPTION-B-001",
        approved_by="PO",
        approval_ref="github-409-comment-5651227165",
        scope={"scope_kind": "SEMANTIC_MULTIPLICITY_CONTRACT_ONLY"},
    )
    contract_packet = make_packet(
        approval_identity=contract_witness.approval_identity,
        approved_by=contract_witness.approved_by,
        approval_ref=contract_witness.approval_ref,
    )
    occurrence_packet = make_packet(
        approval_identity=occurrence_witness.approval_identity,
        approved_by=occurrence_witness.approved_by,
        approval_ref=occurrence_witness.approval_ref,
    )
    fake_witness_mapping = {
        "approval_identity": occurrence_witness.approval_identity,
        "approved_by": occurrence_witness.approved_by,
        "approval_ref": occurrence_witness.approval_ref,
        "scope": deepcopy(occurrence_scope),
    }
    mismatched_class_witness = authority_module.VerifiedApprovalDecision._from_trusted_boundary(
        approval_identity=occurrence_witness.approval_identity,
        approved_by="HUMAN",
        approval_ref=occurrence_witness.approval_ref,
        scope=occurrence_scope,
    )

    def evaluate(
        packet: dict[str, object], witness: object = None
    ) -> tuple[str, str]:
        kwargs: dict[str, object] = {"currentness_evidence": currentness_evidence}
        if witness is not None:
            kwargs["verified_approval_decision"] = witness
        try:
            validated = authority_module.validate_source_bound_semantic_occurrence_approval(
                packet,
                **kwargs,
            )
        except TypeError as exc:
            return "API_MISSING", str(exc)
        except ValueError as exc:
            return "REJECTED", str(exc)
        if validated["currentness"] != "CURRENT":
            return "REJECTED", str(validated["currentness"])

        authority_payload = _fixture()
        authority_payload["source"].update(
            {
                "source_pdf_sha256": PDF_SHA256,
                "page_id": "PAGE-99",
                "render_sha256": PDF_RASTER_SHA256,
                "render_transform": packet["source"]["render_transform"],
            }
        )
        authority_payload["oracle_cases"][3]["source_render_sha256"] = "4" * 64
        try:
            downstream = validate_source_bound_semantic_occurrence_authority(
                authority_payload,
                currentness_evidence=currentness_evidence,
                validated_approval_packet=validated,
            )
        except ValueError as exc:
            return "REJECTED", str(exc)
        return (
            "CURRENT",
            str(downstream["currentness"]),
        )

    outcomes = {
        "contract_only_scope": evaluate(contract_packet, contract_witness),
        "exact_occurrence_scope": evaluate(occurrence_packet, occurrence_witness),
        "no_authenticated_decision": evaluate(occurrence_packet),
        "fake_witness_mapping": evaluate(occurrence_packet, fake_witness_mapping),
        "authority_class_mismatch": evaluate(
            occurrence_packet,
            mismatched_class_witness,
        ),
    }

    assert outcomes["contract_only_scope"][0] == "REJECTED"
    assert "SCOPE_MISMATCH" in outcomes["contract_only_scope"][1]
    assert outcomes["exact_occurrence_scope"] == ("CURRENT", "CURRENT")
    assert outcomes["no_authenticated_decision"][0] == "REJECTED"
    assert outcomes["fake_witness_mapping"][0] == "REJECTED"
    assert outcomes["authority_class_mismatch"][0] == "REJECTED"


@pytest.mark.causal_red
def test_caller_can_mint_verified_decision_before_issuer_boundary() -> None:
    """Causal RED: the nominal verifier factory remains caller-reachable."""
    custody = _custody()
    page_locators = _page_payload(custody)
    render_provenance = [_pdf_render_record(custody, page_locators)]
    normalized_render = authority_module._source_fusion.validate_render_provenance(
        render_provenance,
        page_locators=page_locators,
        custody=custody,
        primitive_artifact_sha256=PRIMITIVE_ARTIFACT_SHA256,
    )[0]
    page_99 = next(page for page in page_locators if page["page_id"] == "PAGE-99")
    currentness_evidence = {
        "render_provenance": render_provenance,
        "page_locators": page_locators,
        "custody": custody,
        "primitive_artifact_sha256": PRIMITIVE_ARTIFACT_SHA256,
    }
    occurrences = deepcopy(_fixture()["occurrences"])
    source = {
        "source_pdf_sha256": PDF_SHA256,
        "page_id": "PAGE-99",
        "render_sha256": PDF_RASTER_SHA256,
        "render_transform": authority_module._render_transform_identity(
            normalized_render
        ),
        "source_custody_sha256": source_custody_sha256(custody),
        "page_locator_sha256": page_99["page_locator_sha256"],
        "render_provenance_sha256": normalized_render[
            "render_provenance_sha256"
        ],
    }
    caller_witness = (
        authority_module.VerifiedApprovalDecision._from_trusted_boundary(
            approval_identity="CALLER-MINTED-PO-001",
            approved_by="PO",
            approval_ref="caller-minted-approval-ref",
            scope={
                "scope_kind": "SOURCE_BOUND_SEMANTIC_OCCURRENCE",
                "source_pdf_sha256": source["source_pdf_sha256"],
                "page_id": source["page_id"],
                "render_sha256": source["render_sha256"],
                "occurrence_ids": [
                    item["occurrence_id"] for item in occurrences
                ],
            },
        )
    )
    packet = {
        "schema_version": "source-bound-semantic-occurrence-approval-1.0",
        "contract_version": "SOURCE_BOUND_SEMANTIC_OCCURRENCE_APPROVAL_V1",
        "source": source,
        "approval": {
            "approval_identity": caller_witness.approval_identity,
            "approved_by": caller_witness.approved_by,
            "approval_ref": caller_witness.approval_ref,
            "approved_at": "2026-09-13T12:00:00Z",
        },
        "occurrences": occurrences,
        "packet_hash": "",
    }
    packet["packet_hash"] = authority_module.canonical_json_sha256(
        {key: item for key, item in packet.items() if key != "packet_hash"}
    )

    result = authority_module.validate_source_bound_semantic_occurrence_approval(
        packet,
        currentness_evidence=currentness_evidence,
        verified_approval_decision=caller_witness,
    )
    assert result["currentness"] == "UNRESOLVED_NON_PASS", (
        "APPROVAL_ISSUER RED: ordinary callers must not mint a trusted "
        "approval decision that reaches CURRENT"
    )
