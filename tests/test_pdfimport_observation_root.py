from __future__ import annotations

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.visual_evidence import (
    VisualEvidenceError,
    derive_pdfimport_observation_root_currentness_sha256,
)


def _packet() -> dict[str, str]:
    return {
        "schema_version": "pdfimport-observation-root-1.0",
        "provenance_mode": "INITIAL_PDFIMPORT_OBSERVATION_ROOT",
        "source_pdf_sha256": "1" * 64,
        "import_script_sha256": "2" * 64,
        "completed_receipt_sha256": "3" * 64,
        "candidate_path": r"D:\Cad agent temp\case02\candidate.dwg",
        "candidate_sha256": "4" * 64,
    }


def test_pdfimport_observation_root_digest_is_domain_separated_and_deterministic() -> None:
    packet = _packet()

    assert derive_pdfimport_observation_root_currentness_sha256(packet) == (
        canonical_json_sha256(packet)
    )
    assert derive_pdfimport_observation_root_currentness_sha256(packet) == (
        derive_pdfimport_observation_root_currentness_sha256(dict(packet))
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "pdfimport-observation-root-0.9"),
        ("provenance_mode", "EXTERNAL_GEOMETRY_ONLY"),
        ("source_pdf_sha256", "not-a-sha"),
        ("import_script_sha256", "A" * 64),
        ("completed_receipt_sha256", ""),
        ("candidate_path", "relative\\candidate.dwg"),
        ("candidate_sha256", "f" * 63),
    ],
)
def test_pdfimport_observation_root_rejects_invalid_identity_fields(
    field: str,
    value: str,
) -> None:
    packet = _packet()
    packet[field] = value

    with pytest.raises(VisualEvidenceError):
        derive_pdfimport_observation_root_currentness_sha256(packet)


def test_pdfimport_observation_root_rejects_open_or_non_mapping_packets() -> None:
    packet = _packet()
    packet["mutation_evidence"] = "not-authorized"

    with pytest.raises(VisualEvidenceError, match="fields"):
        derive_pdfimport_observation_root_currentness_sha256(packet)
    with pytest.raises(VisualEvidenceError, match="object"):
        derive_pdfimport_observation_root_currentness_sha256([])  # type: ignore[arg-type]
