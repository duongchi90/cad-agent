"""Validate approved, source-bound semantic occurrence authority records.

This adjacent contract owner validates an already-authorized occurrence record.
It does not inspect source media, derive geometry, classify detector output, or
persist a registry. Existing custody, provenance, and fidelity owners remain
responsible for their respective records and for consuming this result.
"""

from __future__ import annotations

import datetime as _datetime
import re as _re
from collections.abc import Mapping
from copy import deepcopy

from cad_agent import source_fusion as _source_fusion
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.source_integrity import canonicalize_r1c_quantity


CONTRACT_VERSION = "SOURCE_BOUND_SEMANTIC_OCCURRENCE_AUTHORITY_V1"
SCHEMA_VERSION = "source-bound-semantic-occurrence-authority-1.0"

__all__ = ["validate_source_bound_semantic_occurrence_authority"]


_SHA256_RE = _re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = _re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_UTC_TIMESTAMP_RE = _re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_ROOT_FIELDS = {
    "schema_version",
    "contract_version",
    "source",
    "approval",
    "occurrences",
    "oracle_cases",
}
_SOURCE_FIELDS = {
    "source_pdf_sha256",
    "page_id",
    "render_sha256",
    "render_transform",
}
_APPROVAL_FIELDS = {"approval_identity", "approved_at", "contract_version"}
_OCCURRENCE_FIELDS = {"occurrence_id", "kind", "source_segment_px"}
_SEGMENT_FIELDS = {"p1", "p2"}
_CURRENTNESS_EVIDENCE_FIELDS = {
    "render_provenance",
    "page_locators",
    "custody",
    "primitive_artifact_sha256",
    "render_transform",
}
_ORACLE_EXPECTATIONS = {"DISTINCT", "SAME_OCCURRENCE", "UNRESOLVED_NON_PASS"}


class _AuthorityError(ValueError):
    """Raised when an authority record cannot be safely normalized."""


def _closed(value: object, fields: set[str], path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise _AuthorityError(f"{path}: CLOSED_RECORD_INVALID")
    return value


def _identifier(value: object, path: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise _AuthorityError(f"{path}: IDENTIFIER_INVALID")
    return value


def _sha256(value: object, path: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise _AuthorityError(f"{path}: SHA256_INVALID")
    return value


def _timestamp(value: object, path: str) -> str:
    if not isinstance(value, str) or _UTC_TIMESTAMP_RE.fullmatch(value) is None:
        raise _AuthorityError(f"{path}: UTC_TIMESTAMP_INVALID")
    try:
        _datetime.datetime.fromisoformat(value[:-1])
    except ValueError as exc:
        raise _AuthorityError(f"{path}: UTC_TIMESTAMP_INVALID") from exc
    return value


def _pixel(value: object, path: str) -> int:
    try:
        normalized = canonicalize_r1c_quantity(
            value,
            quantity="pixel_coordinate",
            unit="px",
        )["value"]
    except Exception as exc:
        raise _AuthorityError(f"{path}: PIXEL_COORDINATE_INVALID") from exc
    return int(normalized)


def _source(value: object) -> dict[str, str]:
    source = _closed(value, _SOURCE_FIELDS, "source")
    transform = source["render_transform"]
    if not isinstance(transform, str) or not transform:
        raise _AuthorityError("source.render_transform: TRANSFORM_INVALID")
    return {
        "source_pdf_sha256": _sha256(source["source_pdf_sha256"], "source.source_pdf_sha256"),
        "page_id": _identifier(source["page_id"], "source.page_id"),
        "render_sha256": _sha256(source["render_sha256"], "source.render_sha256"),
        "render_transform": transform,
    }


def _approval(value: object) -> dict[str, str]:
    approval = _closed(value, _APPROVAL_FIELDS, "approval")
    contract_version = approval["contract_version"]
    if contract_version != CONTRACT_VERSION:
        raise _AuthorityError("approval.contract_version: CONTRACT_VERSION_INVALID")
    return {
        "approval_identity": _identifier(
            approval["approval_identity"], "approval.approval_identity"
        ),
        "approved_at": _timestamp(approval["approved_at"], "approval.approved_at"),
        "contract_version": CONTRACT_VERSION,
    }


def _point(value: object, path: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        raise _AuthorityError(f"{path}: POINT_INVALID")
    return [_pixel(coordinate, f"{path}[{index}]") for index, coordinate in enumerate(value)]


def _occurrences(value: object) -> tuple[list[dict[str, object]], set[str]]:
    if not isinstance(value, list) or not value:
        raise _AuthorityError("occurrences: OCCURRENCES_INVALID")
    normalized: list[dict[str, object]] = []
    occurrence_ids: set[str] = set()
    for index, item in enumerate(value):
        path = f"occurrences[{index}]"
        record = _closed(item, _OCCURRENCE_FIELDS, path)
        occurrence_id = _identifier(record["occurrence_id"], f"{path}.occurrence_id")
        if occurrence_id in occurrence_ids:
            raise _AuthorityError(f"{path}.occurrence_id: OCCURRENCE_ID_DUPLICATE")
        kind = _identifier(record["kind"], f"{path}.kind")
        segment = _closed(record["source_segment_px"], _SEGMENT_FIELDS, f"{path}.source_segment_px")
        p1 = _point(segment["p1"], f"{path}.source_segment_px.p1")
        p2 = _point(segment["p2"], f"{path}.source_segment_px.p2")
        if p1 == p2:
            raise _AuthorityError(f"{path}.source_segment_px: ZERO_LENGTH")
        occurrence_ids.add(occurrence_id)
        normalized.append(
            {
                "occurrence_id": occurrence_id,
                "kind": kind,
                "source_segment_px": {"p1": p1, "p2": p2},
            }
        )
    return normalized, occurrence_ids


def _observation(value: object, path: str, occurrence_ids: set[str]) -> dict[str, str]:
    record = _closed(value, {"candidate_id", "occurrence_id"}, path)
    candidate_id = _identifier(record["candidate_id"], f"{path}.candidate_id")
    occurrence_id = _identifier(record["occurrence_id"], f"{path}.occurrence_id")
    if occurrence_id not in occurrence_ids:
        raise _AuthorityError(f"{path}.occurrence_id: OCCURRENCE_UNKNOWN")
    return {"candidate_id": candidate_id, "occurrence_id": occurrence_id}


def _oracle_case(
    value: object,
    *,
    index: int,
    source: dict[str, str],
    occurrence_ids: set[str],
) -> dict[str, str]:
    path = f"oracle_cases[{index}]"
    if not isinstance(value, Mapping):
        raise _AuthorityError(f"{path}: ORACLE_CASE_INVALID")
    case_id = _identifier(value.get("case_id"), f"{path}.case_id")
    expected = value.get("expected")
    if expected not in _ORACLE_EXPECTATIONS:
        raise _AuthorityError(f"{path}.expected: ORACLE_EXPECTATION_INVALID")

    if case_id in {
        "DISTINCT_PARALLEL_OCCURRENCES",
        "SAME_OCCURRENCE_DUPLICATE_OBSERVATIONS",
    }:
        record = _closed(value, {"case_id", "observations", "expected"}, path)
        observations = record["observations"]
        if not isinstance(observations, list) or len(observations) < 2:
            raise _AuthorityError(f"{path}.observations: OBSERVATIONS_INVALID")
        normalized = [
            _observation(item, f"{path}.observations[{item_index}]", occurrence_ids)
            for item_index, item in enumerate(observations)
        ]
        matched_ids = [item["occurrence_id"] for item in normalized]
        if case_id == "DISTINCT_PARALLEL_OCCURRENCES":
            status = "DISTINCT" if len(set(matched_ids)) == len(matched_ids) else "UNRESOLVED_NON_PASS"
        else:
            status = "SAME_OCCURRENCE" if len(set(matched_ids)) == 1 else "UNRESOLVED_NON_PASS"
    elif case_id == "MULTI_MATCH":
        record = _closed(value, {"case_id", "observations", "expected"}, path)
        observations = record["observations"]
        if not isinstance(observations, list) or not observations:
            raise _AuthorityError(f"{path}.observations: OBSERVATIONS_INVALID")
        for item_index, item in enumerate(observations):
            observation = _closed(
                item,
                {"candidate_id", "matched_occurrence_ids"},
                f"{path}.observations[{item_index}]",
            )
            _identifier(
                observation["candidate_id"],
                f"{path}.observations[{item_index}].candidate_id",
            )
            matches = observation["matched_occurrence_ids"]
            if not isinstance(matches, list):
                raise _AuthorityError(f"{path}.observations[{item_index}]: MATCHES_INVALID")
            normalized_matches = [
                _identifier(
                    match,
                    f"{path}.observations[{item_index}].matched_occurrence_ids[{match_index}]",
                )
                for match_index, match in enumerate(matches)
            ]
            if len(normalized_matches) != 1 or normalized_matches[0] not in occurrence_ids:
                status = "UNRESOLVED_NON_PASS"
            else:
                status = "UNIQUE_MATCH"
        status = locals().get("status", "UNRESOLVED_NON_PASS")
    elif case_id == "ZERO_MATCH":
        record = _closed(value, {"case_id", "observations", "expected"}, path)
        observations = record["observations"]
        if not isinstance(observations, list) or not observations:
            raise _AuthorityError(f"{path}.observations: OBSERVATIONS_INVALID")
        outcomes: list[str] = []
        for item_index, item in enumerate(observations):
            observation = _closed(
                item,
                {"candidate_id", "matched_occurrence_ids"},
                f"{path}.observations[{item_index}]",
            )
            _identifier(
                observation["candidate_id"],
                f"{path}.observations[{item_index}].candidate_id",
            )
            matches = observation["matched_occurrence_ids"]
            if not isinstance(matches, list):
                raise _AuthorityError(f"{path}.observations[{item_index}]: MATCHES_INVALID")
            normalized_matches = [
                _identifier(
                    match,
                    f"{path}.observations[{item_index}].matched_occurrence_ids[{match_index}]",
                )
                for match_index, match in enumerate(matches)
            ]
            outcomes.append(
                "UNIQUE_MATCH"
                if len(normalized_matches) == 1
                and normalized_matches[0] in occurrence_ids
                else "UNRESOLVED_NON_PASS"
            )
        status = (
            "UNIQUE_MATCH"
            if all(outcome == "UNIQUE_MATCH" for outcome in outcomes)
            else "UNRESOLVED_NON_PASS"
        )
    elif case_id == "STALE_RENDER_BINDING":
        record = _closed(value, {"case_id", "source_render_sha256", "expected"}, path)
        observed_render_sha256 = _sha256(
            record["source_render_sha256"],
            f"{path}.source_render_sha256",
        )
        status = (
            "UNRESOLVED_NON_PASS"
            if observed_render_sha256 != source["render_sha256"]
            else "CURRENT"
        )
    else:
        raise _AuthorityError(f"{path}.case_id: ORACLE_CASE_UNSUPPORTED")

    if status != expected:
        raise _AuthorityError(f"{path}: ORACLE_EXPECTATION_MISMATCH")
    return {"case_id": case_id, "status": status}


def _currentness_from_owner_evidence(
    source: dict[str, str],
    evidence: Mapping[str, object] | None,
) -> str:
    """Use the existing provenance owner before declaring a binding current."""
    if not isinstance(evidence, Mapping) or set(evidence) != _CURRENTNESS_EVIDENCE_FIELDS:
        return "UNRESOLVED_NON_PASS"
    render_transform = evidence["render_transform"]
    if not isinstance(render_transform, str) or not render_transform:
        return "UNRESOLVED_NON_PASS"
    page_locators = evidence["page_locators"]
    try:
        normalized_renders = _source_fusion.validate_render_provenance(
            evidence["render_provenance"],
            page_locators=page_locators,
            custody=evidence["custody"],
            primitive_artifact_sha256=evidence["primitive_artifact_sha256"],
        )
    except Exception:
        return "UNRESOLVED_NON_PASS"

    page_ids_by_locator = {
        str(page["page_locator_sha256"]): str(page["page_id"])
        for page in page_locators
        if isinstance(page, Mapping)
        and "page_locator_sha256" in page
        and "page_id" in page
    }
    for render in normalized_renders:
        if (
            render.get("provenance_kind") == "PDF_RENDER"
            and render.get("observed_source_sha256") == source["source_pdf_sha256"]
            and render.get("raster_sha256") == source["render_sha256"]
            and page_ids_by_locator.get(str(render.get("page_locator_sha256")))
            == source["page_id"]
            and render_transform == source["render_transform"]
        ):
            return "CURRENT"
    return "UNRESOLVED_NON_PASS"


def validate_source_bound_semantic_occurrence_authority(
    payload: object,
    *,
    currentness_evidence: Mapping[str, object] | None = None,
    current_source_binding: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return a normalized authority record or a fail-closed result.

    ``currentness_evidence`` is the existing source-fusion owner's validated
    custody/provenance evidence. A raw caller-supplied source/render tuple is
    intentionally ignored and never grants current authority.
    """
    root = _closed(payload, _ROOT_FIELDS, "authority")
    if root["schema_version"] != SCHEMA_VERSION:
        raise _AuthorityError("authority.schema_version: SCHEMA_VERSION_INVALID")
    if root["contract_version"] != CONTRACT_VERSION:
        raise _AuthorityError("authority.contract_version: CONTRACT_VERSION_INVALID")

    source = _source(root["source"])
    approval = _approval(root["approval"])
    occurrences, occurrence_ids = _occurrences(root["occurrences"])
    oracle_results_value = root["oracle_cases"]
    if not isinstance(oracle_results_value, list) or not oracle_results_value:
        raise _AuthorityError("oracle_cases: ORACLE_CASES_INVALID")
    oracle_results = [
        _oracle_case(
            item,
            index=index,
            source=source,
            occurrence_ids=occurrence_ids,
        )
        for index, item in enumerate(oracle_results_value)
    ]

    del current_source_binding
    currentness = _currentness_from_owner_evidence(source, currentness_evidence)
    authority_material = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "source": source,
        "approval": approval,
        "occurrences": occurrences,
    }
    return {
        **deepcopy(authority_material),
        "authority_sha256": canonical_json_sha256(authority_material),
        "currentness": currentness,
        "oracle_results": deepcopy(oracle_results),
    }
