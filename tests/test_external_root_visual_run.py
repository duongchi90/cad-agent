from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from cad_agent import mechanical_pilot_provenance as provenance
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.visual_contracts import validate_visual_contract
from cad_agent.visual_evidence import (
    VisualEvidenceError,
    derive_external_root_visual_currentness_sha256,
)


def _external_artifacts(tmp_path: Path) -> dict[str, object]:
    helper_path = Path(__file__).with_name(
        "test_cad_agent_mechanical_pilot_provenance.py"
    )
    spec = importlib.util.spec_from_file_location(
        "external_root_visual_run_fixtures", helper_path
    )
    if spec is None or spec.loader is None:
        raise AssertionError("external provenance fixture loader unavailable")
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    return fixtures._external_artifacts_for_test(tmp_path)


def test_external_root_no_mutation_visual_run_contract_requires_mutation_binding(
    tmp_path: Path,
) -> None:
    """The existing manifest contract must represent a proven root without mutation."""

    artifacts = _external_artifacts(tmp_path)
    packet = provenance.build_external_geometry_provenance(
        pilot_id="external-geometry-ai-p1",
        primitive_ir_path=artifacts["primitive_path"],
        candidate_path=artifacts["candidate_path"],
        build_evidence_path=artifacts["build_evidence_path"],
        verification_request=artifacts["verification_request"],
        verification_result=artifacts["verification_result"],
        source_render_bytes=artifacts["source_render_bytes"],
    )
    # These are the authoritative identities available from the existing
    # external-root provenance owner; it emits no mutation evidence.
    assert "latest_mutation_sha256" not in packet
    assert "mutation_evidence" not in packet
    root_evidence_sha256 = canonical_json_sha256(packet)
    manifest = {
        "schema_version": "visual-run-manifest-1.0",
        "run_id": "external-root-red",
        "state": "CREATED",
        "authority": "DISPOSABLE_REVIEW",
        "source": {
            "source_type": "IMAGE",
            "source_sha256": packet["source_sha256"],
            "page_ids": ["PAGE-1"],
        },
        "drawing": {
            "absolute_path": str(artifacts["candidate_path"]),
            "initial_sha256": packet["candidate_sha256"],
        },
        "evidence_root": f"runs/{packet['candidate_id']}",
    }

    # The validator accepts a deterministic root-evidence hash as a SHA-256
    # at the shape level; this does not make it mutation evidence.
    with_root_hash = {
        **manifest,
        "latest_mutation_sha256": root_evidence_sha256,
    }
    validated = validate_visual_contract(
        with_root_hash,
        contract="visual_run_manifest",
    )
    assert validated["latest_mutation_sha256"] == root_evidence_sha256

    currentness_sha256 = derive_external_root_visual_currentness_sha256(packet)
    assert currentness_sha256 == canonical_json_sha256(
        {
            "schema_version": "external-root-visual-currentness-1.0",
            "provenance_mode": "EXTERNAL_GEOMETRY_ONLY",
            "candidate_id": packet["candidate_id"],
            "candidate_sha256": packet["candidate_sha256"],
            "build_evidence_sha256": packet["build_evidence_sha256"],
            "provenance_sha256": packet["provenance_sha256"],
            "source_sha256": packet["source_sha256"],
            "source_render_sha256": packet["source_render_sha256"],
        }
    )
    manifest["latest_mutation_sha256"] = currentness_sha256
    validated = validate_visual_contract(manifest, contract="visual_run_manifest")
    assert validated["latest_mutation_sha256"] == currentness_sha256


def test_external_root_currentness_fails_closed_for_wrong_or_mutating_identity(
    tmp_path: Path,
) -> None:
    artifacts = _external_artifacts(tmp_path)
    packet = provenance.build_external_geometry_provenance(
        pilot_id="external-geometry-ai-p1",
        primitive_ir_path=artifacts["primitive_path"],
        candidate_path=artifacts["candidate_path"],
        build_evidence_path=artifacts["build_evidence_path"],
        verification_request=artifacts["verification_request"],
        verification_result=artifacts["verification_result"],
        source_render_bytes=artifacts["source_render_bytes"],
    )

    wrong_mode = {**packet, "provenance_mode": "GENERATED_MECHANICAL_PILOT"}
    with pytest.raises(VisualEvidenceError, match="canonical external provenance"):
        derive_external_root_visual_currentness_sha256(wrong_mode)

    missing_identity = dict(packet)
    del missing_identity["source_render_sha256"]
    with pytest.raises(VisualEvidenceError, match="canonical external provenance"):
        derive_external_root_visual_currentness_sha256(missing_identity)

    mutation_bound = {**packet, "mutation_evidence": {}}
    with pytest.raises(VisualEvidenceError, match="canonical external provenance"):
        derive_external_root_visual_currentness_sha256(mutation_bound)


def test_external_root_currentness_rejects_forged_provenance_before_hashing(
    tmp_path: Path,
) -> None:
    artifacts = _external_artifacts(tmp_path)
    packet = provenance.build_external_geometry_provenance(
        pilot_id="external-geometry-ai-p1",
        primitive_ir_path=artifacts["primitive_path"],
        candidate_path=artifacts["candidate_path"],
        build_evidence_path=artifacts["build_evidence_path"],
        verification_request=artifacts["verification_request"],
        verification_result=artifacts["verification_result"],
        source_render_bytes=artifacts["source_render_bytes"],
    )
    forged = {**packet, "candidate_sha256": "f" * 64}

    with pytest.raises(VisualEvidenceError, match="canonical external provenance"):
        derive_external_root_visual_currentness_sha256(forged)
