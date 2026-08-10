"""Pure immutable candidate-revision sealing for the R4 offline core.

This module consumes already-issued DARA and R3 evidence.  It does not own
artifact custody, component/view identity, currentness, persistence, or any
approval or publication state.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib

from cad_agent import base_cad_adapter as _base_cad
from cad_agent import component_view_registry as _r3
from cad_agent import drawing_artifact_reference as _dara
from cad_agent.drawing_contracts import canonical_json_sha256


CANDIDATE_REVISION_SCHEMA_VERSION = "candidate-revision-1.0"


class CandidateRevisionError(ValueError):
    """Categorical refusal at the pure R4 candidate boundary."""


_ROOT_FIELDS = (
    "schema_version",
    "revision_id",
    "state",
    "run_id",
    "baseline_revision",
    "parent_candidate_revision_sha256",
    "upstream_bindings",
    "candidate_artifacts",
    "change_scope",
    "component_lineage",
    "view_lineage",
    "mutation_evidence",
    "candidate_revision_sha256",
)

_MUTATION_FIELDS = (
    "evidence_kind",
    "evidence_id",
    "r3_candidate_reference_id",
    "r3_candidate_reference_sha256",
    "candidate_artifact_sha256",
    "accepted_transition_evidence_sha256",
    "latest_mutation_evidence_sha256",
    "mutation_terminal",
    "evidence_sha256",
)

_IMPACT_FIELDS = (
    "component_ids",
    "view_ids",
    "layout_bindings",
    "link_ids",
)

_CORRESPONDENCE_FIELDS = (
    "parent_reference_id",
    "parent_reference_sha256",
    "child_reference_id",
    "child_reference_sha256",
    "registry_snapshot_sha256",
    "provenance_sha256",
    "component_bindings",
    "view_bindings",
)


def _fail(code: str) -> None:
    raise CandidateRevisionError(code)


def _closed(value: object, fields: tuple[str, ...], code: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != set(fields):
        _fail(code)
    return deepcopy(dict(value))


def _sha(value: object, code: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(code)
    return value


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(code)
    return value


def _sha256(value: object, code: str) -> str:
    if not isinstance(value, str):
        _fail(code)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sorted_sha_values(value: object, code: str) -> list[str]:
    if type(value) is not list:
        _fail(code)
    values = [_sha(item, code) for item in value]
    if len(values) != len(set(values)):
        _fail(code)
    return sorted(values)


def _normalize_baseline(value: object) -> dict[str, object]:
    context = _closed(
        value,
        ("reference", "observation", "artifact_bytes"),
        "BASELINE_CONTEXT_INVALID",
    )
    artifact_bytes = context["artifact_bytes"]
    if not isinstance(artifact_bytes, bytes):
        _fail("BASELINE_ARTIFACT_INVALID")
    try:
        reference = _dara.validate_drawing_artifact_reference(
            context["reference"], expected_artifact_role="BASELINE"
        )
        observation = _dara.validate_drawing_artifact_current_observation(
            context["observation"]
        )
        _dara.require_current_drawing_artifact_reference(
            reference=reference,
            observation=observation,
            artifact_bytes=artifact_bytes,
        )
    except Exception as error:
        raise CandidateRevisionError("BASELINE_CURRENTNESS_INVALID") from error
    return {
        "reference": reference,
        "observation": observation,
        "artifact_bytes": artifact_bytes,
    }


def _normalize_handoff(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("BASE_CAD_HANDOFF_INVALID")
    try:
        return _base_cad.validate_base_cad_reuse_handoff(value)
    except Exception as error:
        raise CandidateRevisionError("BASE_CAD_HANDOFF_INVALID") from error


def _normalize_registry(value: object, handoff: dict[str, object]) -> dict[str, object]:
    registry = _closed(
        value,
        (
            "schema_version",
            "upstream_bindings",
            "components",
            "views",
            "links",
            "registry_snapshot_sha256",
        ),
        "REGISTRY_INVALID",
    )
    if registry["schema_version"] != _r3.COMPONENT_VIEW_REGISTRY_SCHEMA_VERSION:
        _fail("REGISTRY_SCHEMA_INVALID")
    upstream = registry["upstream_bindings"]
    if not isinstance(upstream, Mapping):
        _fail("UPSTREAM_BINDINGS_INVALID")
    for field in (
        "source_bundle_sha256",
        "source_custody_sha256",
        "source_fusion_sha256",
        "reuse_handoff_sha256",
        "candidate_drawing_sha256",
    ):
        _sha(upstream.get(field), "UPSTREAM_BINDINGS_INVALID")
    _text(upstream.get("candidate_id"), "UPSTREAM_BINDINGS_INVALID")
    base_source = upstream.get("base_source")
    if not isinstance(base_source, Mapping):
        _fail("UPSTREAM_BINDINGS_INVALID")
    for field in ("source_id", "sha256", "revision"):
        _text(base_source.get(field), "UPSTREAM_BINDINGS_INVALID")
    if upstream["candidate_drawing_sha256"] != handoff["candidate_output_sha256"]:
        _fail("R2_CANDIDATE_MISMATCH")
    if upstream["source_bundle_sha256"] != handoff["source_bundle_sha256"]:
        _fail("R1_R2_BINDING_MISMATCH")
    if upstream["source_custody_sha256"] != handoff["source_custody_sha256"]:
        _fail("R1_R2_BINDING_MISMATCH")
    if upstream["source_fusion_sha256"] != handoff["source_fusion_sha256"]:
        _fail("R1_R2_BINDING_MISMATCH")
    if upstream["reuse_handoff_sha256"] != _base_cad.base_cad_reuse_handoff_sha256(
        handoff
    ):
        _fail("R2_HANDOFF_HASH_MISMATCH")

    components = registry["components"]
    views = registry["views"]
    links = registry["links"]
    if type(components) is not list or not components:
        _fail("COMPONENTS_INVALID")
    if type(views) is not list or type(links) is not list:
        _fail("REGISTRY_GRAPH_INVALID")

    normalized_components: list[dict[str, object]] = []
    component_ids: set[str] = set()
    for component in components:
        if not isinstance(component, Mapping):
            _fail("COMPONENT_INVALID")
        component_copy = deepcopy(dict(component))
        component_id = _sha(component_copy.get("component_id"), "COMPONENT_ID_INVALID")
        if component_id in component_ids:
            _fail("DUPLICATE_COMPONENT")
        component_ids.add(component_id)
        view_ids = _sorted_sha_values(component_copy.get("view_ids"), "COMPONENT_VIEW_IDS_INVALID")
        component_copy["view_ids"] = view_ids
        normalized_components.append(component_copy)
    normalized_components.sort(key=lambda item: str(item["component_id"]))

    normalized_views: list[dict[str, object]] = []
    view_ids: set[str] = set()
    for view in views:
        if not isinstance(view, Mapping):
            _fail("VIEW_INVALID")
        view_copy = deepcopy(dict(view))
        view_id = _sha(view_copy.get("view_id"), "VIEW_ID_INVALID")
        if view_id in view_ids:
            _fail("DUPLICATE_VIEW")
        view_ids.add(view_id)
        view_copy["component_ids"] = _sorted_sha_values(
            view_copy.get("component_ids"), "VIEW_COMPONENT_IDS_INVALID"
        )
        normalized_views.append(view_copy)
    normalized_views.sort(key=lambda item: str(item["view_id"]))

    normalized_links: list[dict[str, object]] = []
    link_ids: set[str] = set()
    for link in links:
        if not isinstance(link, Mapping):
            _fail("LINK_INVALID")
        link_copy = deepcopy(dict(link))
        link_id = _sha(link_copy.get("link_id"), "LINK_ID_INVALID")
        if link_id in link_ids:
            _fail("DUPLICATE_LINK")
        link_ids.add(link_id)
        _text(link_copy.get("relation_type"), "LINK_INVALID")
        _text(link_copy.get("source_id"), "LINK_INVALID")
        _text(link_copy.get("target_id"), "LINK_INVALID")
        link_copy["evidence_refs"] = _sorted_sha_values(
            link_copy.get("evidence_refs"), "LINK_INVALID"
        )
        normalized_links.append(link_copy)
    normalized_links.sort(
        key=lambda item: (
            str(item["relation_type"]),
            str(item["source_id"]),
            str(item["target_id"]),
            tuple(item["evidence_refs"]),
            str(item["link_id"]),
        )
    )

    material = {
        "schema_version": registry["schema_version"],
        "upstream_bindings": deepcopy(dict(upstream)),
        "components": normalized_components,
        "views": normalized_views,
        "links": normalized_links,
    }
    expected_snapshot = canonical_json_sha256(material)
    if _sha(registry["registry_snapshot_sha256"], "REGISTRY_SNAPSHOT_INVALID") != expected_snapshot:
        _fail("REGISTRY_SNAPSHOT_MISMATCH")
    normalized = deepcopy(material)
    normalized["registry_snapshot_sha256"] = expected_snapshot
    return normalized


def _normalize_impact(value: object, registry: dict[str, object]) -> dict[str, object]:
    impact_root = _closed(
        value,
        ("registry_snapshot_sha256", "impact", "correspondence"),
        "CHANGE_IMPACT_INVALID",
    )
    registry_sha = registry["registry_snapshot_sha256"]
    if impact_root["registry_snapshot_sha256"] != registry_sha:
        _fail("CHANGE_REGISTRY_MISMATCH")
    impact = _closed(impact_root["impact"], _IMPACT_FIELDS, "IMPACT_INVALID")
    component_ids = _sorted_sha_values(impact["component_ids"], "IMPACT_INVALID")
    view_ids = _sorted_sha_values(impact["view_ids"], "IMPACT_INVALID")
    link_ids = _sorted_sha_values(impact["link_ids"], "IMPACT_INVALID")
    layout_bindings = impact["layout_bindings"]
    if type(layout_bindings) is not list:
        _fail("IMPACT_INVALID")
    layouts = [deepcopy(dict(layout)) for layout in layout_bindings if isinstance(layout, Mapping)]
    if len(layouts) != len(layout_bindings):
        _fail("IMPACT_INVALID")
    layouts.sort(key=lambda item: str(item.get("layout_id", "")))
    actual_components = sorted(str(item["component_id"]) for item in registry["components"])
    actual_views = sorted(str(item["view_id"]) for item in registry["views"])
    actual_links = sorted(str(item["link_id"]) for item in registry["links"])
    if component_ids != actual_components or view_ids != actual_views or link_ids != actual_links:
        _fail("IMPACT_REGISTRY_MISMATCH")
    normalized_impact = {
        "component_ids": component_ids,
        "view_ids": view_ids,
        "layout_bindings": layouts,
        "link_ids": link_ids,
    }

    correspondence = _closed(
        impact_root["correspondence"], _CORRESPONDENCE_FIELDS, "CORRESPONDENCE_INVALID"
    )
    for field in (
        "parent_reference_id",
        "child_reference_id",
    ):
        _text(correspondence[field], "CORRESPONDENCE_INVALID")
    if correspondence["parent_reference_id"] == correspondence["child_reference_id"]:
        _fail("CORRESPONDENCE_INVALID")
    for field in (
        "parent_reference_sha256",
        "child_reference_sha256",
        "registry_snapshot_sha256",
        "provenance_sha256",
    ):
        _sha(correspondence[field], "CORRESPONDENCE_INVALID")
    if correspondence["registry_snapshot_sha256"] != registry_sha:
        _fail("CORRESPONDENCE_REGISTRY_MISMATCH")
    component_bindings = correspondence["component_bindings"]
    view_bindings = correspondence["view_bindings"]
    if type(component_bindings) is not list or type(view_bindings) is not list:
        _fail("CORRESPONDENCE_INVALID")
    expected_component_bindings = [
        {
            "component_id": item["component_id"],
            "record_sha256": canonical_json_sha256(item),
        }
        for item in registry["components"]
    ]
    expected_view_bindings = [
        {"view_id": item["view_id"], "record_sha256": canonical_json_sha256(item)}
        for item in registry["views"]
    ]
    expected_component_bindings.sort(key=lambda item: str(item["component_id"]))
    expected_view_bindings.sort(key=lambda item: str(item["view_id"]))
    supplied_components = sorted(
        (deepcopy(dict(item)) for item in component_bindings if isinstance(item, Mapping)),
        key=lambda item: str(item.get("component_id", "")),
    )
    supplied_views = sorted(
        (deepcopy(dict(item)) for item in view_bindings if isinstance(item, Mapping)),
        key=lambda item: str(item.get("view_id", "")),
    )
    if supplied_components != expected_component_bindings or supplied_views != expected_view_bindings:
        _fail("CORRESPONDENCE_REGISTRY_MISMATCH")
    provenance_material = {
        "identity_kind": "r3-component-view-registry-provenance-v1",
        "registry_snapshot_sha256": registry_sha,
        "component_bindings": expected_component_bindings,
        "view_bindings": expected_view_bindings,
    }
    if correspondence["provenance_sha256"] != canonical_json_sha256(provenance_material):
        _fail("CORRESPONDENCE_PROVENANCE_MISMATCH")
    normalized_root = {
        "registry_snapshot_sha256": registry_sha,
        "impact": normalized_impact,
        "correspondence": {
            **{field: correspondence[field] for field in _CORRESPONDENCE_FIELDS[:6]},
            "component_bindings": expected_component_bindings,
            "view_bindings": expected_view_bindings,
        },
    }
    return normalized_root


def _normalize_mutation(value: object) -> dict[str, object]:
    mutation = _closed(value, _MUTATION_FIELDS, "MUTATION_EVIDENCE_INVALID")
    _text(mutation["evidence_kind"], "MUTATION_EVIDENCE_INVALID")
    _text(mutation["evidence_id"], "MUTATION_EVIDENCE_INVALID")
    if mutation["evidence_kind"] != "R4_CANDIDATE_BUILD":
        _fail("MUTATION_EVIDENCE_INVALID")
    for field in (
        "r3_candidate_reference_sha256",
        "candidate_artifact_sha256",
        "accepted_transition_evidence_sha256",
        "latest_mutation_evidence_sha256",
        "evidence_sha256",
    ):
        _sha(mutation[field], "MUTATION_EVIDENCE_INVALID")
    _text(mutation["r3_candidate_reference_id"], "MUTATION_EVIDENCE_INVALID")
    _text(mutation["mutation_terminal"], "MUTATION_EVIDENCE_INVALID")
    if mutation["mutation_terminal"] != "SEALED":
        _fail("MUTATION_EVIDENCE_INVALID")
    material = {key: mutation[key] for key in _MUTATION_FIELDS if key != "evidence_sha256"}
    if mutation["evidence_sha256"] != canonical_json_sha256(material):
        _fail("MUTATION_EVIDENCE_INVALID")
    return mutation


def _lineage_record(value: object) -> dict[str, object]:
    record = _closed(value, _ROOT_FIELDS, "LINEAGE_RECORD_INVALID")
    if record["schema_version"] != CANDIDATE_REVISION_SCHEMA_VERSION:
        _fail("LINEAGE_RECORD_INVALID")
    if record["state"] != "SEALED_CANDIDATE":
        _fail("LINEAGE_RECORD_INVALID")
    _text(record["revision_id"], "LINEAGE_RECORD_INVALID")
    _text(record["run_id"], "LINEAGE_RECORD_INVALID")
    _sha(record["baseline_revision"], "LINEAGE_RECORD_INVALID")
    parent = record["parent_candidate_revision_sha256"]
    if parent is not None:
        _sha(parent, "LINEAGE_RECORD_INVALID")
    _sha(record["candidate_revision_sha256"], "LINEAGE_RECORD_INVALID")
    without_checksum = {key: record[key] for key in _ROOT_FIELDS if key != "candidate_revision_sha256"}
    if record["candidate_revision_sha256"] != canonical_json_sha256(without_checksum):
        _fail("LINEAGE_RECORD_INVALID")
    identity = {key: record[key] for key in _ROOT_FIELDS if key not in {"revision_id", "candidate_revision_sha256"}}
    if record["revision_id"] != "candidate:" + canonical_json_sha256(identity):
        _fail("LINEAGE_RECORD_INVALID")
    return record


def _validate_lineage(
    parent: object,
    lineage_context: object,
    *,
    run_id: str,
    baseline_revision: str,
) -> dict[str, object] | None:
    if parent is None:
        if lineage_context not in ((), [], None):
            _fail("LINEAGE_CONTEXT_UNEXPECTED")
        return None
    parent_record = _lineage_record(parent)
    if parent_record["run_id"] != run_id:
        _fail("LINEAGE_SCOPE_MISMATCH")
    if parent_record["baseline_revision"] != baseline_revision:
        _fail("STALE_BASELINE")
    required_parent = parent_record["parent_candidate_revision_sha256"]
    if required_parent is None:
        if lineage_context not in ((), [], None):
            _fail("LINEAGE_CONTEXT_UNEXPECTED")
        return parent_record
    if not isinstance(lineage_context, Mapping):
        _fail("LINEAGE_CONTEXT_REQUIRED")
    context = _closed(
        lineage_context,
        ("schema_version", "scope", "baseline_reference", "ancestors"),
        "LINEAGE_CONTEXT_INVALID",
    )
    if context["schema_version"] != "candidate-lineage-context-1.0":
        _fail("LINEAGE_CONTEXT_INVALID")
    scope = _closed(context["scope"], ("run_id", "project_id", "drawing_id"), "LINEAGE_SCOPE_INVALID")
    baseline = _dara.validate_drawing_artifact_reference(
        context["baseline_reference"], expected_artifact_role="BASELINE"
    )
    if any(scope[field] != baseline[field] for field in ("run_id", "project_id", "drawing_id")):
        _fail("LINEAGE_SCOPE_MISMATCH")
    if baseline["reference_sha256"] != baseline_revision:
        _fail("LINEAGE_BASELINE_MISMATCH")
    ancestors = context["ancestors"]
    if type(ancestors) is not list:
        _fail("LINEAGE_CONTEXT_INVALID")
    by_sha: dict[str, dict[str, object]] = {}
    for entry in ancestors:
        item = _closed(entry, ("candidate_revision_sha256", "candidate_record"), "LINEAGE_ANCESTOR_INVALID")
        sha = _sha(item["candidate_revision_sha256"], "LINEAGE_ANCESTOR_INVALID")
        if sha in by_sha:
            _fail("LINEAGE_DUPLICATE")
        record = _lineage_record(item["candidate_record"])
        if record["candidate_revision_sha256"] != sha:
            _fail("LINEAGE_ANCESTOR_MISMATCH")
        if record["run_id"] != run_id or record["baseline_revision"] != baseline_revision:
            _fail("LINEAGE_SCOPE_MISMATCH")
        by_sha[sha] = record
    current_sha = required_parent
    visited: set[str] = set()
    while current_sha is not None:
        if current_sha in visited:
            _fail("LINEAGE_CYCLE")
        visited.add(current_sha)
        record = by_sha.get(current_sha)
        if record is None:
            _fail("LINEAGE_ANCESTOR_MISSING")
        current_sha = record["parent_candidate_revision_sha256"]
    if visited != set(by_sha):
        _fail("LINEAGE_UNREACHABLE_ANCESTOR")
    return parent_record


def _normalize_inputs(
    *,
    registry: object,
    base_cad_handoff: object,
    baseline_context: object,
    parent_candidate: object | None,
    change_impact: object,
    mutation_evidence: object,
    lineage_context: object,
) -> dict[str, object]:
    baseline = _normalize_baseline(baseline_context)
    handoff = _normalize_handoff(base_cad_handoff)
    normalized_registry = _normalize_registry(registry, handoff)
    normalized_impact = _normalize_impact(change_impact, normalized_registry)
    normalized_mutation = _normalize_mutation(mutation_evidence)
    if normalized_impact["correspondence"]["child_reference_sha256"] != normalized_mutation[
        "r3_candidate_reference_sha256"
    ]:
        _fail("CORRESPONDENCE_CANDIDATE_MISMATCH")
    if normalized_impact["correspondence"]["child_reference_id"] != normalized_mutation[
        "r3_candidate_reference_id"
    ]:
        _fail("CORRESPONDENCE_CANDIDATE_MISMATCH")
    baseline_reference = baseline["reference"]
    parent_record = _validate_lineage(
        parent_candidate,
        lineage_context,
        run_id=str(baseline_reference["run_id"]),
        baseline_revision=str(baseline_reference["reference_sha256"]),
    )
    return {
        "baseline": baseline,
        "handoff": handoff,
        "registry": normalized_registry,
        "impact": normalized_impact,
        "mutation": normalized_mutation,
        "parent": parent_record,
    }


def _lineages(registry: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    components = [
        {"component_id": item["component_id"], "view_ids": list(item["view_ids"])}
        for item in registry["components"]
    ]
    views = [
        {"view_id": item["view_id"], "component_ids": list(item["component_ids"])}
        for item in registry["views"]
    ]
    components.sort(key=lambda item: str(item["component_id"]))
    views.sort(key=lambda item: str(item["view_id"]))
    return components, views


def _record_for(normalized: dict[str, object]) -> dict[str, object]:
    baseline = normalized["baseline"]["reference"]
    registry = normalized["registry"]
    impact = normalized["impact"]
    mutation = normalized["mutation"]
    parent = normalized["parent"]
    component_lineage, view_lineage = _lineages(registry)
    record: dict[str, object] = {
        "schema_version": CANDIDATE_REVISION_SCHEMA_VERSION,
        "revision_id": "",
        "state": "SEALED_CANDIDATE",
        "run_id": baseline["run_id"],
        "baseline_revision": baseline["reference_sha256"],
        "parent_candidate_revision_sha256": (
            None if parent is None else parent["candidate_revision_sha256"]
        ),
        "upstream_bindings": deepcopy(registry["upstream_bindings"]),
        "candidate_artifacts": {
            "reference_id": mutation["r3_candidate_reference_id"],
            "reference_sha256": mutation["r3_candidate_reference_sha256"],
            "artifact_sha256": mutation["candidate_artifact_sha256"],
            "accepted_transition_evidence_sha256": mutation[
                "accepted_transition_evidence_sha256"
            ],
        },
        "change_scope": deepcopy(impact),
        "component_lineage": component_lineage,
        "view_lineage": view_lineage,
        "mutation_evidence": deepcopy(mutation),
        "candidate_revision_sha256": "",
    }
    identity = {
        key: record[key]
        for key in _ROOT_FIELDS
        if key not in {"revision_id", "candidate_revision_sha256"}
    }
    record["revision_id"] = "candidate:" + canonical_json_sha256(identity)
    without_checksum = {
        key: record[key] for key in _ROOT_FIELDS if key != "candidate_revision_sha256"
    }
    record["candidate_revision_sha256"] = canonical_json_sha256(without_checksum)
    return record


def _validate_record(payload: object, expected: dict[str, object]) -> dict[str, object]:
    record = _lineage_record(payload)
    if record != expected:
        _fail("CANDIDATE_BINDING_MISMATCH")
    return deepcopy(record)


def build_candidate_revision(
    *,
    registry: object,
    base_cad_handoff: object,
    baseline_context: object,
    parent_candidate: object | None,
    change_impact: object,
    mutation_evidence: object,
    lineage_context: object = (),
) -> dict[str, object]:
    normalized = _normalize_inputs(
        registry=registry,
        base_cad_handoff=base_cad_handoff,
        baseline_context=baseline_context,
        parent_candidate=parent_candidate,
        change_impact=change_impact,
        mutation_evidence=mutation_evidence,
        lineage_context=lineage_context,
    )
    return deepcopy(_record_for(normalized))


def validate_candidate_revision(
    payload: object,
    *,
    registry: object,
    base_cad_handoff: object,
    baseline_context: object,
    parent_candidate: object | None,
    change_impact: object,
    mutation_evidence: object,
    lineage_context: object = (),
) -> dict[str, object]:
    normalized = _normalize_inputs(
        registry=registry,
        base_cad_handoff=base_cad_handoff,
        baseline_context=baseline_context,
        parent_candidate=parent_candidate,
        change_impact=change_impact,
        mutation_evidence=mutation_evidence,
        lineage_context=lineage_context,
    )
    return _validate_record(payload, _record_for(normalized))


__all__ = [
    "CANDIDATE_REVISION_SCHEMA_VERSION",
    "CandidateRevisionError",
    "build_candidate_revision",
    "validate_candidate_revision",
]
