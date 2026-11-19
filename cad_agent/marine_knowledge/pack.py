"""Marine Knowledge Pack V0 loader, lookup, query, and safe disable toggle."""

from __future__ import annotations

from copy import deepcopy
import os
from typing import Any

from .contracts import MARINE_PACK_SCHEMA_VERSION, seal_knowledge_pack
from .knowledge_data import RAW_MARINE_RULES, RAW_MARINE_TERMS
from .manifest import get_marine_source_manifest
from .text_normalization import fold_marine_search_text

_DISABLE_ENV_VAR = "CAD_AGENT_DISABLE_MARINE_PACK"
_SEALED_MANIFEST = get_marine_source_manifest()

_SEALED_PACK = seal_knowledge_pack(
    {
        "schema_version": MARINE_PACK_SCHEMA_VERSION,
        "id": "MARINE_KNOWLEDGE_PACK_V0",
        "revision": "0.1.0",
        "status": "CANDIDATE_UNAPPROVED",
        "cad_mutation": False,
        "default_core_behavior_changed": False,
        "domain_pack_compatibility": {
            "target_schema": "domain-pack-1.0",
            "promotable": False,
            "requires_human_approval": True,
            "approved_by": None,
        },
        "domains": [
            "vietnam_inland_waterway",
            "naval_architecture_general",
            "shipbuilding_drafting_standards",
        ],
        "drawing_types": [
            "LINES_PLAN",
            "GENERAL_ARRANGEMENT",
            "MIDSHIP_STRUCTURAL",
            "BASIC_STRUCTURAL",
        ],
        "vocabulary": [item["term_id"] for item in RAW_MARINE_TERMS],
        "terms": [deepcopy(item) for item in RAW_MARINE_TERMS],
        "rules": [deepcopy(item) for item in RAW_MARINE_RULES],
    },
    source_manifest=_SEALED_MANIFEST,
)


def is_marine_pack_enabled(enabled: bool | None = None) -> bool:
    """Return False when env kill-switch is set or explicitly disabled."""
    raw = os.environ.get(_DISABLE_ENV_VAR, "").strip().lower()
    if raw in {"1", "true", "yes", "on", "disabled"}:
        return False
    if enabled is not None:
        return bool(enabled)
    return True


def get_marine_pack_status(*, enabled: bool | None = None) -> dict[str, Any]:
    """Return active pack or explicit DISABLED status preserving unchanged CAD Core behavior."""
    if not is_marine_pack_enabled(enabled):
        return {
            "status": "DISABLED",
            "cad_mutation": False,
            "default_core_behavior_changed": False,
            "pack": None,
        }
    return {
        "status": _SEALED_PACK["status"],
        "cad_mutation": False,
        "default_core_behavior_changed": False,
        "pack": deepcopy(_SEALED_PACK),
    }


def get_marine_knowledge_pack(*, enabled: bool | None = None) -> dict[str, Any]:
    """Return defensive copy of the sealed Marine V0 pack (raises if disabled cleanly via status)."""
    if not is_marine_pack_enabled(enabled):
        return get_marine_pack_status(enabled=False)
    return deepcopy(_SEALED_PACK)


def lookup_term(query: str, *, enabled: bool | None = None) -> dict[str, Any] | None:
    """Look up a sourced naval architecture term by canonical name, ID, or TCVN3/UTF-8 alias."""
    if not is_marine_pack_enabled(enabled):
        return None
    needle = fold_marine_search_text(query)
    if not needle:
        return None
    for term in _SEALED_PACK["terms"]:
        candidates = (
            term["term_id"],
            term["canonical_name_vi"],
            term["canonical_name_en"],
            *term["aliases"],
        )
        for cand in candidates:
            if needle == fold_marine_search_text(cand):
                return deepcopy(term)
    for term in _SEALED_PACK["terms"]:
        folded_vi = fold_marine_search_text(term["canonical_name_vi"])
        folded_en = fold_marine_search_text(term["canonical_name_en"])
        if needle in folded_vi or needle in folded_en or any(
            needle in fold_marine_search_text(alias) for alias in term["aliases"]
        ):
            return deepcopy(term)
    return None


def query_rules(
    *,
    domain: str | None = None,
    drawing_type: str | None = None,
    enabled: bool | None = None,
) -> list[dict[str, Any]]:
    """Filter sourced conditional rules deterministically by domain and drawing type."""
    if not is_marine_pack_enabled(enabled):
        return []
    out: list[dict[str, Any]] = []
    for rule in _SEALED_PACK["rules"]:
        if domain and domain not in rule["applicable_domains"]:
            continue
        if drawing_type and drawing_type not in rule["applicable_drawing_types"]:
            continue
        out.append(deepcopy(rule))
    return out
