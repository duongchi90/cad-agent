from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

from cad_agent import pdf
from cad_agent.manifest import ManifestError
from cad_agent.source_bundle import build_source_bundle, source_bundle_sha256


def _r1c_configuration(tmp_path: Path) -> tuple[dict[str, object], Path]:
    approved_root = tmp_path / "approved-root"
    source = approved_root / "sources" / "exact.pdf"
    source.parent.mkdir(parents=True)
    source_bytes = b"test-only exact PDF source bytes"
    source.write_bytes(source_bytes)
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    bundle = build_source_bundle(
        bundle_id="BUNDLE-409-RED",
        run_id="RUN-409-RED",
        created_at_utc="2026-09-12T12:00:00Z",
        items=[
            {
                "source_id": "PDF-409-RED",
                "kind": "PDF",
                "role": "OVERALL",
                "relative_path": "sources/exact.pdf",
                "sha256": source_sha256,
                "media_type": "application/pdf",
                "page_ids": ["PAGE-001"],
                "region_ids": [],
                "captured_at_utc": "2026-09-12T12:00:00Z",
                "quality": {"distortion": "NONE", "legibility": "GOOD"},
            }
        ],
    )
    return (
        {
            "approved_root_id": "ROOT-409-RED",
            "approved_root_revision": "ROOT-REV-409-RED",
            "approved_root": approved_root,
            "identity_key": b"test-only-r1c-identity-material",
            "identity_key_revision": "KEY-REV-409-RED",
            "policy_limits": {
                "max_items": 10,
                "max_total_bytes": 1024,
                "max_file_bytes": 1024,
                "hash_chunk_size": 64,
                "max_final_path_chars": 260,
            },
            "source_bundle": bundle,
        },
        source,
    )


def test_pdf_executor_binds_complete_r1c_configuration_to_existing_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration, source = _r1c_configuration(tmp_path)
    bundle = configuration["source_bundle"]
    assert isinstance(bundle, dict)
    assert bundle["items"][0]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert len(source_bundle_sha256(bundle)) == 64

    signature = inspect.signature(pdf.run_pdf_stages)
    assert "r1c_configuration" in signature.parameters

    manifest = pdf.new_pdf_manifest(source, 1.0, "test-only", 144)
    monkeypatch.setattr(pdf, "_ensure_rendered", lambda *_args: None)
    evidence = pdf.run_pdf_stages(
        source,
        tmp_path / "output",
        tmp_path / "manifest.json",
        manifest,
        r1c_configuration=configuration,
    )

    assert evidence is not None
    assert evidence["source_bundle_sha256"] == source_bundle_sha256(bundle)
    assert evidence["items"][0]["observed_sha256"] == bundle["items"][0]["sha256"]


@pytest.mark.parametrize("mutation", ["missing", "extra", "invalid"])
def test_pdf_executor_rejects_incomplete_or_invalid_r1c_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    configuration, source = _r1c_configuration(tmp_path)
    if mutation == "missing":
        configuration.pop("source_bundle")
    elif mutation == "extra":
        configuration["unexpected"] = True
    else:
        configuration["identity_key"] = b""

    manifest = pdf.new_pdf_manifest(source, 1.0, "test-only", 144)

    def fail_render(*_args: object) -> None:
        raise AssertionError("invalid R1C configuration reached PDF staging")

    monkeypatch.setattr(pdf, "_ensure_rendered", fail_render)
    with pytest.raises(ManifestError, match="R1C_CONFIGURATION_INVALID"):
        pdf.run_pdf_stages(
            source,
            tmp_path / "output",
            tmp_path / "manifest.json",
            manifest,
            r1c_configuration=configuration,
        )
