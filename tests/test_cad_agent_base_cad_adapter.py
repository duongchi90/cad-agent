"""R2 Gate-0 RED contract; production adapter is intentionally absent."""

from __future__ import annotations

import importlib

import pytest


def _adapter_module():
    """Turn the intentionally missing production owner into attributable RED."""
    try:
        return importlib.import_module("cad_agent.base_cad_adapter")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "R2 RED: cad_agent.base_cad_adapter is not implemented; "
            "Gate-0 production write is not authorized yet"
        )
        raise AssertionError from exc


@pytest.fixture
def exact_base_packet():
    return {
        "source_sha256": "source-sha",
        "source_revision": "rev-7",
        "xref_sha256": "xref-sha",
        "units": "mm",
        "ucs": "ucs-origin",
        "wcs": "wcs-origin",
        "entities": [
            {"handle": "A", "layer": "0", "block": "*Model_Space", "transform": "I"}
        ],
    }


def test_exact_base_provenance_is_immutable(exact_base_packet):
    adapter = _adapter_module()
    result = adapter.prepare_exact_base(packet=exact_base_packet)
    exact_base_packet["source_revision"] = "rev-8"
    assert result.provenance.source_revision == "rev-7"


def test_stale_xref_fails_closed(exact_base_packet):
    adapter = _adapter_module()
    stale = {**exact_base_packet, "xref_sha256": "different-xref"}
    with pytest.raises(adapter.BaseCadAdapterError, match="STALE_EXACT_BASE"):
        adapter.prepare_exact_base(packet=stale)


def test_units_ucs_wcs_ambiguity_fails_closed(exact_base_packet):
    adapter = _adapter_module()
    ambiguous = {**exact_base_packet, "units": None, "ucs": "unknown", "wcs": "unknown"}
    with pytest.raises(adapter.BaseCadAdapterError, match="FRAME_AMBIGUITY"):
        adapter.prepare_exact_base(packet=ambiguous)


def test_duplicate_handles_fail_closed(exact_base_packet):
    adapter = _adapter_module()
    duplicate = {**exact_base_packet, "entities": [{"handle": "A"}, {"handle": "A"}]}
    with pytest.raises(adapter.BaseCadAdapterError, match="DUPLICATE_HANDLE"):
        adapter.prepare_exact_base(packet=duplicate)


def test_replay_and_entity_order_are_deterministic(exact_base_packet):
    adapter = _adapter_module()
    reversed_packet = {**exact_base_packet, "entities": list(reversed(exact_base_packet["entities"]))}
    first = adapter.prepare_exact_base(packet=exact_base_packet)
    second = adapter.prepare_exact_base(packet=reversed_packet)
    assert first.identity == second.identity


def test_adapter_does_not_introduce_second_owner():
    adapter = _adapter_module()
    assert adapter.uses_existing_canonical_hash_owner is True
    assert adapter.owns_manifest is False
    assert adapter.owns_transport is False
    assert adapter.owns_extraction is False
