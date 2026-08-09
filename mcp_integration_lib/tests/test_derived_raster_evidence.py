from __future__ import annotations

import hashlib
import importlib
import inspect

import pytest


def _contract():
    return importlib.import_module("mcp_integration_lib.derived_raster_evidence")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _binding() -> dict[str, object]:
    return {
        "pdf_artifact_sha256": "a" * 64,
        "drawing_sha256": "b" * 64,
        "latest_mutation_sha256": "c" * 64,
        "visual_run_manifest_sha256": "d" * 64,
        "layout": {"identity": "layout-001", "name": "Layout1"},
        "render_options": {
            "paper_size": "A4",
            "dpi": 300,
            "background": "white",
            "opaque": True,
        },
        "dbmod_before": 7,
        "dbmod_after": 7,
    }


def _pdf(
    *,
    media_box: str = "0 0 595.2756 841.8898",
    crop_box: str = "0 0 595.2756 841.8898",
    user_unit: str = "1.0",
    encrypted: bool = False,
    alpha: bool = False,
) -> bytes:
    encryption = b"/Encrypt 7 0 R\n" if encrypted else b""
    transparency = b"/SMask 9 0 R\n" if alpha else b""
    content = b"0 0 0 rg\n100 100 200 200 re\nf\n"
    return (
        b"%PDF-1.7\n"
        + encryption
        + f"1 0 obj << /Type /Page /MediaBox [{media_box}] /CropBox [{crop_box}] /UserUnit {user_unit} /Contents 2 0 R >> endobj\n2 0 obj << /Length {len(content)} >> stream\n".encode()
        + transparency
        + content
        + b"endstream\nendobj\n%%EOF\n"
    )


def _derive(pdf_bytes: bytes | None = None, **overrides: object) -> dict[str, object]:
    source_pdf = _pdf() if pdf_bytes is None else pdf_bytes
    binding = _binding()
    binding["pdf_artifact_sha256"] = _sha256(source_pdf)
    values = {
        "pdf_bytes": source_pdf,
        "native_binding": binding,
        "page_number": 1,
    }
    values.update(overrides)
    return _contract().derive_raster_evidence(**values)


def test_encrypted_pdf_fails_closed_without_partial_or_private_output() -> None:
    contract = _contract()

    with pytest.raises(contract.DerivedRasterEvidenceError) as failure:
        _derive(_pdf(encrypted=True))

    assert not hasattr(failure.value, "partial_output")
    assert "pdf_bytes" not in str(failure.value)


def test_pdf_bytes_are_the_only_raster_authority_and_native_binding_is_closed() -> None:
    contract = _contract()
    signature = inspect.signature(contract.derive_raster_evidence)

    assert "png_bytes" not in signature.parameters
    evidence = _derive()
    assert evidence["source"] == "NATIVE_PDF_BINDING"
    assert evidence["pdf_sha256"] == _sha256(_pdf())
    assert len(evidence["png_sha256"]) == 64
    assert evidence["png_sha256"] != _sha256(b"caller-supplied-png")
    assert evidence["drawing_sha256"] == _binding()["drawing_sha256"]
    assert evidence["latest_mutation_sha256"] == _binding()["latest_mutation_sha256"]
    assert evidence["visual_run_manifest_sha256"] == _binding()["visual_run_manifest_sha256"]
    assert evidence["layout"] == _binding()["layout"]
    assert evidence["render_options"] == _binding()["render_options"]
    assert evidence["dbmod_before"] == evidence["dbmod_after"] == 7
    assert "pdf_bytes" not in evidence
    assert "png_bytes" not in evidence


def test_pdf_artifact_sha_mismatch_fails_closed() -> None:
    contract = _contract()
    binding = _binding()

    with pytest.raises(contract.DerivedRasterEvidenceError):
        _derive(native_binding=binding)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("crop_box", "0 0 500 700"),
        ("user_unit", "2.0"),
        ("media_box", "0 0 612 792"),
    ],
)
def test_geometry_requires_a4_media_box_user_unit_and_crop_box_alignment(
    field: str, value: str
) -> None:
    contract = _contract()
    kwargs = {field: value}

    with pytest.raises(contract.DerivedRasterEvidenceError):
        _derive(_pdf(**kwargs))


def test_exact_a4_300_dpi_geometry_is_opaque_and_has_no_alpha() -> None:
    evidence = _derive()

    assert evidence["paper_size"] == "A4"
    assert evidence["dpi"] == 300
    assert evidence["width_px"] == 2480
    assert evidence["height_px"] == 3508
    assert evidence["has_alpha"] is False
    assert evidence["opaque"] is True


def test_alpha_or_resource_limit_violation_fails_without_partial_output() -> None:
    contract = _contract()

    for pdf_bytes in (
        _pdf(alpha=True),
        _pdf() + b"x" * (8 * 1024 * 1024),
    ):
        with pytest.raises(contract.DerivedRasterEvidenceError) as failure:
            _derive(pdf_bytes)
        assert not hasattr(failure.value, "partial_output")
        assert "private" not in str(failure.value).casefold()


def test_provenance_layout_render_options_and_dbmod_must_match_binding() -> None:
    contract = _contract()

    for field, value in (
        ("drawing_sha256", "not-a-hash"),
        ("latest_mutation_sha256", "not-a-hash"),
        ("visual_run_manifest_sha256", "not-a-hash"),
        ("dbmod_after", 8),
    ):
        binding = _binding()
        binding[field] = value
        with pytest.raises(contract.DerivedRasterEvidenceError):
            _derive(native_binding=binding)


def test_at_least_five_replays_have_one_deterministic_identity() -> None:
    results = [_derive() for _ in range(5)]

    assert len({result["pdf_sha256"] for result in results}) == 1
    assert len({result["png_sha256"] for result in results}) == 1
    assert all(result == results[0] for result in results)


def test_pdf_content_changes_derived_raster_identity() -> None:
    first = _derive(_pdf())
    second = _derive(_pdf().replace(b"100 100 200 200", b"200 100 200 200"))

    assert first["pdf_sha256"] != second["pdf_sha256"]
    assert first["png_sha256"] != second["png_sha256"]


def test_geometry_tokens_without_a_renderable_page_fail_closed() -> None:
    contract = _contract()
    fake = (
        b"%PDF-1.7\n/MediaBox [0 0 595.2756 841.8898]\n"
        b"/CropBox [0 0 595.2756 841.8898]\n/UserUnit 1.0\n%%EOF\n"
    )
    binding = _binding()
    binding["pdf_artifact_sha256"] = _sha256(fake)

    with pytest.raises(contract.DerivedRasterEvidenceError):
        contract.derive_raster_evidence(pdf_bytes=fake, native_binding=binding, page_number=1)
