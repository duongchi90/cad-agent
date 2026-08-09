from __future__ import annotations

import importlib
from copy import deepcopy

import pytest


def _contract():
    return importlib.import_module("mcp_integration_lib.derived_raster_evidence")


def _native_binding() -> dict[str, object]:
    return {
        "binding_id": "native-binding-001",
        "source_sha256": "a" * 64,
        "renderer": "NATIVE",
    }


def _pdf(*, encrypted: bool = False) -> bytes:
    marker = b"/Encrypt 7 0 R\n" if encrypted else b""
    return b"%PDF-1.7\n" + marker + b"1 0 obj\n<<>>\nendobj\n%%EOF\n"


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"synthetic-in-memory-png"


def _derive(**overrides: object) -> dict[str, object]:
    values = {
        "pdf_bytes": _pdf(),
        "png_bytes": _png(),
        "native_binding": _native_binding(),
        "page_number": 1,
    }
    values.update(overrides)
    return _contract().derive_raster_evidence(**values)


def test_encrypted_pdf_fails_closed_without_partial_or_private_output() -> None:
    contract = _contract()

    with pytest.raises(contract.DerivedRasterEvidenceError):
        contract.derive_raster_evidence(
            pdf_bytes=_pdf(encrypted=True),
            png_bytes=_png(),
            native_binding=_native_binding(),
            page_number=1,
        )


def test_native_binding_and_exact_a4_300_dpi_geometry_are_closed() -> None:
    evidence = _derive()

    assert evidence == {
        "schema_version": "derived-raster-evidence-1.0",
        "source": "NATIVE_PDF_BINDING",
        "native_binding": _native_binding(),
        "page_number": 1,
        "paper_size": "A4",
        "dpi": 300,
        "width_px": 2480,
        "height_px": 3508,
        "pdf_sha256": "",
        "png_sha256": "",
    }
    assert set(evidence) == {
        "schema_version",
        "source",
        "native_binding",
        "page_number",
        "paper_size",
        "dpi",
        "width_px",
        "height_px",
        "pdf_sha256",
        "png_sha256",
    }


def test_invalid_binding_or_bytes_produce_no_partial_output() -> None:
    contract = _contract()

    for kwargs in (
        {"pdf_bytes": b"not-pdf", "png_bytes": _png()},
        {"pdf_bytes": _pdf(), "png_bytes": b"not-png"},
        {"pdf_bytes": _pdf(), "png_bytes": _png(), "native_binding": None},
    ):
        with pytest.raises(contract.DerivedRasterEvidenceError) as failure:
            contract.derive_raster_evidence(
                native_binding=_native_binding(),
                page_number=1,
                **kwargs,
            )
        assert not hasattr(failure.value, "partial_output")
        assert "pdf_bytes" not in str(failure.value)
        assert "png_bytes" not in str(failure.value)


def test_repeated_derivation_is_deterministic_and_detached() -> None:
    first = _derive()
    second = _derive()

    assert first == second
    assert deepcopy(first) == second
    first["native_binding"]["binding_id"] = "mutated"
    assert second["native_binding"]["binding_id"] == "native-binding-001"
