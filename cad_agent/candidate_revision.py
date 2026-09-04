"""Pure immutable candidate-revision sealing for the R4 offline core.

This module consumes already-issued DARA and R3 evidence.  It does not own
artifact custody, component/view identity, currentness, persistence, or any
approval or publication state.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from cad_agent import base_cad_adapter as _base_cad
from cad_agent import component_view_registry as _r3
from cad_agent import drawing_artifact_reference as _dara
from cad_agent.drawing_contracts import canonical_json_sha256


CANDIDATE_REVISION_SCHEMA_VERSION = "candidate-revision-1.0"
CANDIDATE_REVISION_V11_SCHEMA_VERSION = "candidate-revision-1.1"
CANDIDATE_REVISION_ROOT_KIND = "ROOT_PRE_REPAIR"
CANDIDATE_REVISION_POST_REPAIR_KIND = "POST_REPAIR"
CANDIDATE_REVISION_STATE_SCHEMA_VERSION = "candidate-revision-state-1.0"
CANDIDATE_REVISION_STATE_TRANSITION_SCHEMA_VERSION = (
    "candidate-revision-state-transition-1.0"
)


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
_ROOT_V11_FIELDS = (
    "schema_version",
    "candidate_kind",
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
_IMPACT_FIELDS = ("component_ids", "view_ids", "layout_bindings", "link_ids")
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
_CHANGE_IMPACT_FIELDS = (
    "registry_snapshot_sha256",
    "impact",
    "correspondence",
    "upstream_context",
    "correspondence_context",
)
_CORRESPONDENCE_CONTEXT_FIELDS = (
    "parent_reference",
    "parent_observation",
    "parent_artifact_bytes",
    "child_reference",
    "child_observation",
    "child_artifact_bytes",
    "accepted_transition_evidence_sha256",
)
_ROOT_CHANGE_IMPACT_FIELDS = (
    "registry_snapshot_sha256",
    "impact",
    "provenance_evidence",
    "upstream_context",
    "root_candidate_reference",
    "root_candidate_observation",
    "root_candidate_artifact_bytes",
)
_ROOT_MUTATION_FIELDS = (
    "evidence_kind",
    "evidence_id",
    "r3_candidate_reference_id",
    "r3_candidate_reference_sha256",
    "candidate_artifact_sha256",
    "registry_snapshot_sha256",
)
_ROOT_PROVENANCE_FIELDS = (
    "identity_kind",
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


def _normalize_handoff(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        _fail("BASE_CAD_HANDOFF_INVALID")
    try:
        return _base_cad.validate_base_cad_reuse_handoff(value)
    except Exception as error:
        raise CandidateRevisionError("BASE_CAD_HANDOFF_INVALID") from error


def _normalize_registry(
    value: object,
    handoff: dict[str, object] | None,
    upstream_context: object,
) -> dict[str, object]:
    try:
        registry = _r3.validate_component_view_registry(
            value, upstream_context=upstream_context
        )
    except Exception as error:
        raise CandidateRevisionError("REGISTRY_INVALID") from error

    upstream = registry["upstream_bindings"]
    if not isinstance(upstream, Mapping):
        _fail("UPSTREAM_BINDINGS_INVALID")
    if (
        registry["schema_version"]
        == _r3.COMPONENT_VIEW_REGISTRY_GENERATED_SCHEMA_VERSION
    ):
        if handoff is not None:
            _fail("GENERATED_HANDOFF_FORBIDDEN")
        if upstream.get("provenance_mode") != "GENERATED_MECHANICAL_PILOT":
            _fail("GENERATED_UPSTREAM_INVALID")
        if set(upstream) != {
            "provenance_mode",
            "pilot_id",
            "source_sha256",
            "candidate_id",
            "candidate_drawing_sha256",
            "candidate_path_binding_sha256",
            "build_evidence_sha256",
            "pilot_evidence_sha256",
            "provenance_packet_sha256",
        }:
            _fail("GENERATED_UPSTREAM_INVALID")
        return registry
    if handoff is None:
        _fail("BASE_CAD_HANDOFF_INVALID")
    if upstream["candidate_drawing_sha256"] != handoff["candidate_output_sha256"]:
        _fail("R2_CANDIDATE_MISMATCH")
    for field in (
        "source_bundle_sha256",
        "source_custody_sha256",
        "source_fusion_sha256",
    ):
        if upstream[field] != handoff[field]:
            _fail("R1_R2_BINDING_MISMATCH")
    if upstream["reuse_handoff_sha256"] != _base_cad.base_cad_reuse_handoff_sha256(
        handoff
    ):
        _fail("R2_HANDOFF_HASH_MISMATCH")
    return registry


def _normalize_impact(
    value: object,
    registry: dict[str, object],
) -> dict[str, object]:
    root = _closed(value, _CHANGE_IMPACT_FIELDS, "CHANGE_IMPACT_INVALID")
    registry_sha = registry["registry_snapshot_sha256"]
    if root["registry_snapshot_sha256"] != registry_sha:
        _fail("CHANGE_REGISTRY_MISMATCH")

    impact = _closed(root["impact"], _IMPACT_FIELDS, "IMPACT_INVALID")
    try:
        expected_impact = _r3.project_linked_view_impacts(
            registry=registry,
            component_ids=impact["component_ids"],
            view_ids=impact["view_ids"],
            upstream_context=root["upstream_context"],
        )
    except Exception as error:
        raise CandidateRevisionError("IMPACT_INVALID") from error
    normalized_impact = deepcopy(impact)
    for field in ("component_ids", "view_ids", "link_ids"):
        if type(normalized_impact[field]) is not list:
            _fail("IMPACT_INVALID")
        normalized_impact[field] = sorted(normalized_impact[field])
    if type(normalized_impact["layout_bindings"]) is not list:
        _fail("IMPACT_INVALID")
    normalized_impact["layout_bindings"] = sorted(
        normalized_impact["layout_bindings"],
        key=lambda item: str(item.get("layout_id", ""))
        if isinstance(item, Mapping)
        else "",
    )
    if normalized_impact != expected_impact:
        _fail("IMPACT_REGISTRY_MISMATCH")

    correspondence = _closed(
        root["correspondence"], _CORRESPONDENCE_FIELDS, "CORRESPONDENCE_INVALID"
    )
    context = _closed(
        root["correspondence_context"],
        _CORRESPONDENCE_CONTEXT_FIELDS,
        "CORRESPONDENCE_CONTEXT_INVALID",
    )
    try:
        expected_correspondence = _r3.finalize_component_view_correspondence(
            registry=registry,
            upstream_context=root["upstream_context"],
            parent_reference=context["parent_reference"],
            parent_observation=context["parent_observation"],
            parent_artifact_bytes=context["parent_artifact_bytes"],
            child_reference=context["child_reference"],
            child_observation=context["child_observation"],
            child_artifact_bytes=context["child_artifact_bytes"],
            accepted_transition_evidence_sha256=context[
                "accepted_transition_evidence_sha256"
            ],
        )
    except Exception as error:
        raise CandidateRevisionError("CORRESPONDENCE_INVALID") from error
    if correspondence != expected_correspondence:
        _fail("CORRESPONDENCE_REGISTRY_MISMATCH")
    return {
        "registry_snapshot_sha256": registry_sha,
        "impact": deepcopy(expected_impact),
        "correspondence": deepcopy(expected_correspondence),
    }


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
    material = {
        key: mutation[key] for key in _MUTATION_FIELDS if key != "evidence_sha256"
    }
    if mutation["evidence_sha256"] != canonical_json_sha256(material):
        _fail("MUTATION_EVIDENCE_INVALID")
    return mutation


def _candidate_schema_kind(
    schema_version: object, candidate_kind: object
) -> tuple[str, str | None]:
    if schema_version == CANDIDATE_REVISION_SCHEMA_VERSION:
        if candidate_kind is not None:
            _fail("CANDIDATE_KIND_INVALID")
        return CANDIDATE_REVISION_SCHEMA_VERSION, None
    if schema_version == CANDIDATE_REVISION_V11_SCHEMA_VERSION:
        if candidate_kind not in {
            CANDIDATE_REVISION_ROOT_KIND,
            CANDIDATE_REVISION_POST_REPAIR_KIND,
        }:
            _fail("CANDIDATE_KIND_INVALID")
        return CANDIDATE_REVISION_V11_SCHEMA_VERSION, str(candidate_kind)
    _fail("CANDIDATE_SCHEMA_INVALID")


def _lineage_record_v11(value: object) -> dict[str, object]:
    record = _closed(value, _ROOT_V11_FIELDS, "LINEAGE_RECORD_INVALID")
    _candidate_schema_kind(record["schema_version"], record["candidate_kind"])
    if record["state"] != "SEALED_CANDIDATE":
        _fail("LINEAGE_RECORD_INVALID")
    _text(record["revision_id"], "LINEAGE_RECORD_INVALID")
    _text(record["run_id"], "LINEAGE_RECORD_INVALID")
    _sha(record["baseline_revision"], "LINEAGE_RECORD_INVALID")
    parent = record["parent_candidate_revision_sha256"]
    if parent is not None:
        _sha(parent, "LINEAGE_RECORD_INVALID")
    _sha(record["candidate_revision_sha256"], "LINEAGE_RECORD_INVALID")
    artifacts = record["candidate_artifacts"]
    if not isinstance(artifacts, Mapping):
        _fail("LINEAGE_RECORD_INVALID")
    if set(artifacts) != {
        "reference_id",
        "reference_sha256",
        "artifact_sha256",
        "accepted_transition_evidence_sha256",
    }:
        _fail("LINEAGE_RECORD_INVALID")
    _text(artifacts["reference_id"], "LINEAGE_RECORD_INVALID")
    for field in ("reference_sha256", "artifact_sha256"):
        _sha(artifacts[field], "LINEAGE_RECORD_INVALID")
    kind = record["candidate_kind"]
    accepted = artifacts["accepted_transition_evidence_sha256"]
    mutation = record["mutation_evidence"]
    if kind == CANDIDATE_REVISION_ROOT_KIND:
        if parent is not None or accepted is not None:
            _fail("ROOT_TRANSITION_FORBIDDEN")
        mutation = _closed(mutation, _ROOT_MUTATION_FIELDS, "LINEAGE_RECORD_INVALID")
        if mutation["evidence_kind"] != "R4_ROOT_PRE_REPAIR":
            _fail("LINEAGE_RECORD_INVALID")
    else:
        if parent is None or not isinstance(accepted, str):
            _fail("POST_REPAIR_TRANSITION_REQUIRED")
        _sha(accepted, "LINEAGE_RECORD_INVALID")
        mutation = _closed(mutation, _MUTATION_FIELDS, "LINEAGE_RECORD_INVALID")
        if mutation["evidence_kind"] != "R4_CANDIDATE_BUILD":
            _fail("LINEAGE_RECORD_INVALID")
    without_checksum = {
        key: record[key] for key in _ROOT_V11_FIELDS if key != "candidate_revision_sha256"
    }
    if record["candidate_revision_sha256"] != canonical_json_sha256(without_checksum):
        _fail("LINEAGE_RECORD_INVALID")
    identity = {
        key: record[key]
        for key in _ROOT_V11_FIELDS
        if key not in {"revision_id", "candidate_revision_sha256"}
    }
    if record["revision_id"] != "candidate:" + canonical_json_sha256(identity):
        _fail("LINEAGE_RECORD_INVALID")
    return record


def _lineage_record(value: object) -> dict[str, object]:
    if isinstance(value, Mapping) and value.get("schema_version") == CANDIDATE_REVISION_V11_SCHEMA_VERSION:
        return _lineage_record_v11(value)
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
    without_checksum = {
        key: record[key] for key in _ROOT_FIELDS if key != "candidate_revision_sha256"
    }
    if record["candidate_revision_sha256"] != canonical_json_sha256(without_checksum):
        _fail("LINEAGE_RECORD_INVALID")
    identity = {
        key: record[key]
        for key in _ROOT_FIELDS
        if key not in {"revision_id", "candidate_revision_sha256"}
    }
    if record["revision_id"] != "candidate:" + canonical_json_sha256(identity):
        _fail("LINEAGE_RECORD_INVALID")
    return record


def _validate_lineage(
    parent: object,
    lineage_context: object,
    *,
    run_id: str,
    baseline_revision: str,
    schema_version: str = CANDIDATE_REVISION_SCHEMA_VERSION,
) -> dict[str, object] | None:
    _candidate_schema_kind(schema_version, None if schema_version == CANDIDATE_REVISION_SCHEMA_VERSION else CANDIDATE_REVISION_ROOT_KIND)
    if parent is None:
        if lineage_context not in ((), [], None):
            _fail("LINEAGE_CONTEXT_UNEXPECTED")
        return None
    parent_record = _lineage_record(parent)
    if parent_record["schema_version"] != schema_version:
        _fail("STATE_SCHEMA_MIXED")
    if parent_record["run_id"] != run_id:
        _fail("LINEAGE_SCOPE_MISMATCH")
    if parent_record["baseline_revision"] != baseline_revision:
        _fail("STALE_BASELINE")
    required_parent = parent_record["parent_candidate_revision_sha256"]
    if required_parent is None:
        if schema_version == CANDIDATE_REVISION_SCHEMA_VERSION:
            if lineage_context not in ((), [], None):
                _fail("LINEAGE_CONTEXT_UNEXPECTED")
            return parent_record
        if lineage_context in ((), [], None):
            return parent_record
        if not isinstance(lineage_context, Mapping):
            _fail("LINEAGE_CONTEXT_INVALID")
        context = _closed(
            lineage_context,
            ("schema_version", "scope", "baseline_reference", "ancestors"),
            "LINEAGE_CONTEXT_INVALID",
        )
        if context["schema_version"] != "candidate-lineage-context-1.0":
            _fail("LINEAGE_CONTEXT_INVALID")
        scope = _closed(
            context["scope"],
            ("run_id", "project_id", "drawing_id"),
            "LINEAGE_SCOPE_INVALID",
        )
        baseline = _dara.validate_drawing_artifact_reference(
            context["baseline_reference"], expected_artifact_role="BASELINE"
        )
        if any(
            scope[field] != baseline[field]
            for field in ("run_id", "project_id", "drawing_id")
        ):
            _fail("LINEAGE_SCOPE_MISMATCH")
        if baseline["reference_sha256"] != baseline_revision:
            _fail("LINEAGE_BASELINE_MISMATCH")
        ancestors = context["ancestors"]
        if type(ancestors) is not list or len(ancestors) != 1:
            _fail("LINEAGE_CONTEXT_INVALID")
        item = _closed(
            ancestors[0],
            ("candidate_revision_sha256", "candidate_record"),
            "LINEAGE_ANCESTOR_INVALID",
        )
        sha = _sha(item["candidate_revision_sha256"], "LINEAGE_ANCESTOR_INVALID")
        if sha != parent_record["candidate_revision_sha256"]:
            _fail("LINEAGE_ANCESTOR_MISMATCH")
        record = _lineage_record(item["candidate_record"])
        if record != parent_record or record["schema_version"] != schema_version:
            _fail("LINEAGE_ANCESTOR_MISMATCH")
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
    scope = _closed(
        context["scope"],
        ("run_id", "project_id", "drawing_id"),
        "LINEAGE_SCOPE_INVALID",
    )
    baseline = _dara.validate_drawing_artifact_reference(
        context["baseline_reference"], expected_artifact_role="BASELINE"
    )
    if any(
        scope[field] != baseline[field]
        for field in ("run_id", "project_id", "drawing_id")
    ):
        _fail("LINEAGE_SCOPE_MISMATCH")
    if baseline["reference_sha256"] != baseline_revision:
        _fail("LINEAGE_BASELINE_MISMATCH")
    ancestors = context["ancestors"]
    if type(ancestors) is not list:
        _fail("LINEAGE_CONTEXT_INVALID")
    by_sha: dict[str, dict[str, object]] = {}
    for entry in ancestors:
        item = _closed(
            entry,
            ("candidate_revision_sha256", "candidate_record"),
            "LINEAGE_ANCESTOR_INVALID",
        )
        sha = _sha(item["candidate_revision_sha256"], "LINEAGE_ANCESTOR_INVALID")
        if sha in by_sha:
            _fail("LINEAGE_DUPLICATE")
        record = _lineage_record(item["candidate_record"])
        if record["schema_version"] != schema_version:
            _fail("STATE_SCHEMA_MIXED")
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


def _normalize_root_inputs(
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
    if parent_candidate is not None:
        _fail("ROOT_TRANSITION_FORBIDDEN")
    if lineage_context not in ((), [], None):
        _fail("LINEAGE_CONTEXT_UNEXPECTED")
    if not isinstance(change_impact, Mapping):
        _fail("ROOT_TRANSITION_FORBIDDEN")
    if set(change_impact) != set(_ROOT_CHANGE_IMPACT_FIELDS):
        _fail("ROOT_TRANSITION_FORBIDDEN")
    raw_impact = deepcopy(dict(change_impact))
    normalized_registry = _normalize_registry(
        registry, handoff, raw_impact["upstream_context"]
    )
    if raw_impact["registry_snapshot_sha256"] != normalized_registry[
        "registry_snapshot_sha256"
    ]:
        _fail("REGISTRY_INVALID")
    impact = _closed(raw_impact["impact"], _IMPACT_FIELDS, "ROOT_EVIDENCE_INVALID")
    try:
        expected_impact = _r3.project_linked_view_impacts(
            registry=normalized_registry,
            component_ids=impact["component_ids"],
            view_ids=impact["view_ids"],
            upstream_context=raw_impact["upstream_context"],
        )
    except Exception as error:
        raise CandidateRevisionError("ROOT_EVIDENCE_INVALID") from error
    normalized_impact = deepcopy(impact)
    for field in ("component_ids", "view_ids", "link_ids"):
        if type(normalized_impact[field]) is not list:
            _fail("ROOT_EVIDENCE_INVALID")
        normalized_impact[field] = sorted(normalized_impact[field])
    if type(normalized_impact["layout_bindings"]) is not list:
        _fail("ROOT_EVIDENCE_INVALID")
    normalized_impact["layout_bindings"] = sorted(
        normalized_impact["layout_bindings"],
        key=lambda item: str(item.get("layout_id", ""))
        if isinstance(item, Mapping)
        else "",
    )
    if normalized_impact != expected_impact:
        _fail("REGISTRY_INVALID")
    try:
        provenance = _r3.component_view_registry_provenance_evidence(
            normalized_registry,
            upstream_context=raw_impact["upstream_context"],
        )
    except Exception as error:
        raise CandidateRevisionError("REGISTRY_INVALID") from error
    if raw_impact["provenance_evidence"] != provenance:
        _fail("REGISTRY_INVALID")
    root_reference = _dara.validate_drawing_artifact_reference(
        raw_impact["root_candidate_reference"], expected_artifact_role="R3_CANDIDATE"
    )
    root_bytes = raw_impact["root_candidate_artifact_bytes"]
    if not isinstance(root_bytes, bytes):
        _fail("BASELINE_CURRENTNESS_INVALID")
    try:
        root_observation = _dara.validate_drawing_artifact_current_observation(
            raw_impact["root_candidate_observation"]
        )
        _dara.require_current_drawing_artifact_reference(
            reference=root_reference,
            observation=root_observation,
            artifact_bytes=root_bytes,
        )
    except Exception as error:
        raise CandidateRevisionError("BASELINE_CURRENTNESS_INVALID") from error
    baseline_reference = baseline["reference"]
    if any(
        root_reference[field] != baseline_reference[field]
        for field in ("run_id", "project_id", "drawing_id")
    ):
        _fail("BASELINE_CURRENTNESS_INVALID")
    if normalized_registry["schema_version"] == (
        _r3.COMPONENT_VIEW_REGISTRY_GENERATED_SCHEMA_VERSION
    ):
        if handoff is not None:
            _fail("GENERATED_HANDOFF_FORBIDDEN")
        if root_reference["artifact_sha256"] != normalized_registry[
            "upstream_bindings"
        ]["candidate_drawing_sha256"]:
            _fail("GENERATED_CANDIDATE_MISMATCH")
    else:
        if handoff is None:
            _fail("BASE_CAD_HANDOFF_INVALID")
        if root_reference["artifact_sha256"] != handoff["candidate_output_sha256"]:
            _fail("R2_CANDIDATE_MISMATCH")
    binding = root_reference.get("r3_provenance_binding")
    if not isinstance(binding, Mapping) or dict(binding) != {
        "registry_snapshot_sha256": provenance["registry_snapshot_sha256"],
        "provenance_sha256": provenance["provenance_sha256"],
    }:
        _fail("REGISTRY_INVALID")
    mutation = _closed(
        mutation_evidence, _ROOT_MUTATION_FIELDS, "ROOT_TRANSITION_FORBIDDEN"
    )
    if mutation["evidence_kind"] != "R4_ROOT_PRE_REPAIR":
        _fail("ROOT_TRANSITION_FORBIDDEN")
    _text(mutation["evidence_id"], "ROOT_EVIDENCE_INVALID")
    _text(mutation["r3_candidate_reference_id"], "ROOT_EVIDENCE_INVALID")
    for field in (
        "r3_candidate_reference_sha256",
        "candidate_artifact_sha256",
        "registry_snapshot_sha256",
    ):
        _sha(mutation[field], "ROOT_EVIDENCE_INVALID")
    if mutation["r3_candidate_reference_id"] != root_reference["reference_id"]:
        _fail("R2_CANDIDATE_MISMATCH")
    if mutation["r3_candidate_reference_sha256"] != root_reference["reference_sha256"]:
        _fail("R2_CANDIDATE_MISMATCH")
    if mutation["candidate_artifact_sha256"] != root_reference["artifact_sha256"]:
        _fail("R2_CANDIDATE_MISMATCH")
    if mutation["registry_snapshot_sha256"] != normalized_registry[
        "registry_snapshot_sha256"
    ]:
        _fail("REGISTRY_INVALID")
    return {
        "baseline": baseline,
        "handoff": handoff,
        "registry": normalized_registry,
        "root_impact": {
            "registry_snapshot_sha256": normalized_registry[
                "registry_snapshot_sha256"
            ],
            "impact": deepcopy(expected_impact),
            "provenance_evidence": deepcopy(provenance),
        },
        "root_reference": root_reference,
        "root_observation": root_observation,
        "root_artifact_bytes": root_bytes,
        "mutation": mutation,
        "parent": None,
    }


def _normalize_inputs(
    *,
    registry: object,
    base_cad_handoff: object,
    baseline_context: object,
    parent_candidate: object | None,
    change_impact: object,
    mutation_evidence: object,
    lineage_context: object,
    schema_version: str = CANDIDATE_REVISION_SCHEMA_VERSION,
) -> dict[str, object]:
    baseline = _normalize_baseline(baseline_context)
    handoff = _normalize_handoff(base_cad_handoff)
    raw_impact = _closed(change_impact, _CHANGE_IMPACT_FIELDS, "CHANGE_IMPACT_INVALID")
    normalized_registry = _normalize_registry(
        registry, handoff, raw_impact["upstream_context"]
    )
    normalized_impact = _normalize_impact(raw_impact, normalized_registry)
    normalized_mutation = _normalize_mutation(mutation_evidence)
    correspondence = normalized_impact["correspondence"]
    if correspondence["child_reference_sha256"] != normalized_mutation[
        "r3_candidate_reference_sha256"
    ]:
        _fail("CORRESPONDENCE_CANDIDATE_MISMATCH")
    if correspondence["child_reference_id"] != normalized_mutation[
        "r3_candidate_reference_id"
    ]:
        _fail("CORRESPONDENCE_CANDIDATE_MISMATCH")
    baseline_reference = baseline["reference"]
    parent_record = _validate_lineage(
        parent_candidate,
        lineage_context,
        run_id=str(baseline_reference["run_id"]),
        baseline_revision=str(baseline_reference["reference_sha256"]),
        schema_version=schema_version,
    )
    return {
        "baseline": baseline,
        "handoff": handoff,
        "registry": normalized_registry,
        "impact": normalized_impact,
        "mutation": normalized_mutation,
        "parent": parent_record,
    }


def _lineages(
    registry: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
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


def _record_for_v11(
    normalized: dict[str, object], candidate_kind: str
) -> dict[str, object]:
    baseline = normalized["baseline"]["reference"]
    registry = normalized["registry"]
    mutation = normalized["mutation"]
    parent = normalized["parent"]
    component_lineage, view_lineage = _lineages(registry)
    if candidate_kind == CANDIDATE_REVISION_ROOT_KIND:
        change_scope = deepcopy(normalized["root_impact"])
        accepted_transition = None
    else:
        change_scope = deepcopy(normalized["impact"])
        accepted_transition = mutation["accepted_transition_evidence_sha256"]
    record: dict[str, object] = {
        "schema_version": CANDIDATE_REVISION_V11_SCHEMA_VERSION,
        "candidate_kind": candidate_kind,
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
            "accepted_transition_evidence_sha256": accepted_transition,
        },
        "change_scope": change_scope,
        "component_lineage": component_lineage,
        "view_lineage": view_lineage,
        "mutation_evidence": deepcopy(mutation),
        "candidate_revision_sha256": "",
    }
    identity = {
        key: record[key]
        for key in _ROOT_V11_FIELDS
        if key not in {"revision_id", "candidate_revision_sha256"}
    }
    record["revision_id"] = "candidate:" + canonical_json_sha256(identity)
    without_checksum = {
        key: record[key]
        for key in _ROOT_V11_FIELDS
        if key != "candidate_revision_sha256"
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
    schema_version: str = CANDIDATE_REVISION_SCHEMA_VERSION,
    candidate_kind: str | None = None,
) -> dict[str, object]:
    normalized_schema, normalized_kind = _candidate_schema_kind(
        schema_version, candidate_kind
    )
    if normalized_schema == CANDIDATE_REVISION_SCHEMA_VERSION:
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
    if normalized_kind == CANDIDATE_REVISION_ROOT_KIND:
        normalized = _normalize_root_inputs(
            registry=registry,
            base_cad_handoff=base_cad_handoff,
            baseline_context=baseline_context,
            parent_candidate=parent_candidate,
            change_impact=change_impact,
            mutation_evidence=mutation_evidence,
            lineage_context=lineage_context,
        )
    else:
        if parent_candidate is None:
            _fail("ROOT_TRANSITION_FORBIDDEN")
        if not isinstance(mutation_evidence, Mapping) or mutation_evidence.get(
            "accepted_transition_evidence_sha256"
        ) is None:
            _fail("POST_REPAIR_TRANSITION_REQUIRED")
        normalized = _normalize_inputs(
            registry=registry,
            base_cad_handoff=base_cad_handoff,
            baseline_context=baseline_context,
            parent_candidate=parent_candidate,
            change_impact=change_impact,
            mutation_evidence=mutation_evidence,
            lineage_context=lineage_context,
            schema_version=normalized_schema,
        )
    return deepcopy(_record_for_v11(normalized, normalized_kind))


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
    schema_version: str = CANDIDATE_REVISION_SCHEMA_VERSION,
    candidate_kind: str | None = None,
) -> dict[str, object]:
    normalized_schema, normalized_kind = _candidate_schema_kind(
        schema_version, candidate_kind
    )
    if normalized_schema == CANDIDATE_REVISION_SCHEMA_VERSION:
        normalized = _normalize_inputs(
            registry=registry,
            base_cad_handoff=base_cad_handoff,
            baseline_context=baseline_context,
            parent_candidate=parent_candidate,
            change_impact=change_impact,
            mutation_evidence=mutation_evidence,
            lineage_context=lineage_context,
        )
    elif normalized_kind == CANDIDATE_REVISION_ROOT_KIND:
        normalized = _normalize_root_inputs(
            registry=registry,
            base_cad_handoff=base_cad_handoff,
            baseline_context=baseline_context,
            parent_candidate=parent_candidate,
            change_impact=change_impact,
            mutation_evidence=mutation_evidence,
            lineage_context=lineage_context,
        )
    else:
        if parent_candidate is None:
            _fail("ROOT_TRANSITION_FORBIDDEN")
        if not isinstance(mutation_evidence, Mapping) or mutation_evidence.get(
            "accepted_transition_evidence_sha256"
        ) is None:
            _fail("POST_REPAIR_TRANSITION_REQUIRED")
        normalized = _normalize_inputs(
            registry=registry,
            base_cad_handoff=base_cad_handoff,
            baseline_context=baseline_context,
            parent_candidate=parent_candidate,
            change_impact=change_impact,
            mutation_evidence=mutation_evidence,
            lineage_context=lineage_context,
            schema_version=normalized_schema,
        )
    return _validate_record(
        payload,
        _record_for(normalized)
        if normalized_schema == CANDIDATE_REVISION_SCHEMA_VERSION
        else _record_for_v11(normalized, normalized_kind),
    )


def _state_candidates(value: object) -> list[dict[str, object]]:
    if type(value) is not list or not value:
        _fail("STATE_CANDIDATES_INVALID")
    candidates: list[dict[str, object]] = []
    by_sha: set[str] = set()
    schema_versions: set[str] = set()
    scope: tuple[object, object] | None = None
    upstream: object = None
    for value_candidate in value:
        candidate = _lineage_record(value_candidate)
        schema_versions.add(str(candidate["schema_version"]))
        if len(schema_versions) > 1:
            _fail("STATE_SCHEMA_MIXED")
        candidate_sha = str(candidate["candidate_revision_sha256"])
        if candidate_sha in by_sha:
            _fail("STATE_CANDIDATE_DUPLICATE")
        by_sha.add(candidate_sha)
        candidate_scope = (candidate["run_id"], candidate["baseline_revision"])
        if scope is None:
            scope = candidate_scope
            upstream = candidate["upstream_bindings"]
        elif candidate_scope != scope:
            _fail("STATE_BASELINE_SCOPE_MISMATCH")
        elif candidate["upstream_bindings"] != upstream:
            _fail("STATE_UPSTREAM_R3_R2_BINDING_MISMATCH")
        candidates.append(candidate)
    candidates.sort(key=lambda candidate: str(candidate["candidate_revision_sha256"]))
    return candidates


def _state_record(
    candidates: list[dict[str, object]], selected_sha: str | None
) -> dict[str, object]:
    if selected_sha is not None:
        _sha(selected_sha, "STATE_CURRENT_CANDIDATE_INVALID")
        if not any(
            candidate["candidate_revision_sha256"] == selected_sha
            for candidate in candidates
        ):
            _fail("STATE_CURRENT_CANDIDATE_NOT_MEMBER")
    state: dict[str, object] = {
        "schema_version": CANDIDATE_REVISION_STATE_SCHEMA_VERSION,
        "candidate_revisions": deepcopy(candidates),
        "current_candidate_revision_sha256": selected_sha,
        "state_sha256": "",
    }
    state["state_sha256"] = canonical_json_sha256(
        {key: value for key, value in state.items() if key != "state_sha256"}
    )
    return state


def build_candidate_revision_state(
    *,
    candidate_revisions: object,
    current_candidate_revision_sha256: str | None = None,
) -> dict[str, object]:
    """Build a deterministic, caller-owned snapshot of candidate selection state."""

    return _state_record(
        _state_candidates(candidate_revisions), current_candidate_revision_sha256
    )


def validate_candidate_revision_state(payload: object) -> dict[str, object]:
    """Validate and return an independent canonical candidate-state snapshot."""

    state = _closed(
        payload,
        (
            "schema_version",
            "candidate_revisions",
            "current_candidate_revision_sha256",
            "state_sha256",
        ),
        "STATE_FIELDS_INVALID",
    )
    if state["schema_version"] != CANDIDATE_REVISION_STATE_SCHEMA_VERSION:
        _fail("STATE_SCHEMA_INVALID")
    _sha(state["state_sha256"], "STATE_CHECKSUM_INVALID")
    expected = _state_record(
        _state_candidates(state["candidate_revisions"]),
        state["current_candidate_revision_sha256"],
    )
    if state["state_sha256"] != expected["state_sha256"]:
        _fail("STATE_CHECKSUM_INVALID")
    if state != expected:
        _fail("STATE_CANONICAL_INVALID")
    return deepcopy(expected)


def _transition_record(value: object) -> dict[str, object]:
    transition = _closed(
        value,
        (
            "schema_version",
            "transition_kind",
            "candidate_revision_sha256",
            "expected_current_candidate_revision_sha256",
        ),
        "TRANSITION_FIELDS_INVALID",
    )
    if transition["schema_version"] != CANDIDATE_REVISION_STATE_TRANSITION_SCHEMA_VERSION:
        _fail("TRANSITION_SCHEMA_INVALID")
    if not isinstance(transition["transition_kind"], str) or transition[
        "transition_kind"
    ] not in {"SELECT", "SUPERSEDE", "ROLLBACK"}:
        _fail("TRANSITION_KIND_UNKNOWN")
    _sha(transition["candidate_revision_sha256"], "TRANSITION_CANDIDATE_INVALID")
    expected = transition["expected_current_candidate_revision_sha256"]
    if expected is not None:
        _sha(expected, "TRANSITION_EXPECTED_CURRENT_INVALID")
    return transition


def _is_ancestor(
    target_sha: str,
    selected: dict[str, object],
    candidates: dict[str, dict[str, object]],
) -> bool:
    parent_sha = selected["parent_candidate_revision_sha256"]
    visited: set[str] = set()
    while parent_sha is not None:
        if parent_sha in visited:
            _fail("STATE_LINEAGE_CYCLE")
        visited.add(parent_sha)
        if parent_sha == target_sha:
            return True
        parent = candidates.get(str(parent_sha))
        if parent is None:
            _fail("STATE_LINEAGE_PARENT_MISSING")
        parent_sha = parent["parent_candidate_revision_sha256"]
    return False


def transition_candidate_revision_state(
    *,
    state: object,
    candidate_revision: object,
    transition: object,
) -> dict[str, object]:
    """Apply a closed logical selection transition without retaining state."""

    normalized_state = validate_candidate_revision_state(state)
    normalized_transition = _transition_record(transition)
    try:
        candidate = _lineage_record(candidate_revision)
    except CandidateRevisionError as error:
        raise CandidateRevisionError("CANDIDATE_CHECKSUM_INVALID") from error
    candidate_sha = str(candidate["candidate_revision_sha256"])
    if normalized_transition["candidate_revision_sha256"] != candidate_sha:
        _fail("TRANSITION_CANDIDATE_BINDING_MISMATCH")

    candidates = {
        str(item["candidate_revision_sha256"]): item
        for item in normalized_state["candidate_revisions"]
    }
    stored = candidates.get(candidate_sha)
    if stored is None or stored != candidate:
        _fail("CANDIDATE_BINDING_CHECKSUM_MISMATCH")

    selected_sha = normalized_state["current_candidate_revision_sha256"]
    expected_sha = normalized_transition[
        "expected_current_candidate_revision_sha256"
    ]
    if expected_sha != selected_sha:
        _fail("TRANSITION_EXPECTED_CURRENT_STALE")
    if candidate_sha == selected_sha:
        _fail("TRANSITION_CURRENT_REPLAY")

    kind = normalized_transition["transition_kind"]
    if kind == "SELECT":
        if selected_sha is not None:
            _fail("SELECT_CURRENT_CONFLICT")
    elif kind == "SUPERSEDE":
        if selected_sha is None or candidate["parent_candidate_revision_sha256"] != selected_sha:
            _fail("SUPERSEDE_PARENT_NOT_CURRENT")
    else:
        if selected_sha is None or not _is_ancestor(
            candidate_sha, candidates[str(selected_sha)], candidates
        ):
            _fail("ROLLBACK_CANDIDATE_NOT_ANCESTOR")

    return _state_record(list(candidates.values()), candidate_sha)


__all__ = [
    "CANDIDATE_REVISION_SCHEMA_VERSION",
    "CANDIDATE_REVISION_V11_SCHEMA_VERSION",
    "CANDIDATE_REVISION_ROOT_KIND",
    "CANDIDATE_REVISION_POST_REPAIR_KIND",
    "CANDIDATE_REVISION_STATE_SCHEMA_VERSION",
    "CANDIDATE_REVISION_STATE_TRANSITION_SCHEMA_VERSION",
    "CandidateRevisionError",
    "build_candidate_revision",
    "build_candidate_revision_state",
    "transition_candidate_revision_state",
    "validate_candidate_revision",
    "validate_candidate_revision_state",
]
