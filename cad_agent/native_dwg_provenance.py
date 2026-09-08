"""Closed provenance and composition for a full native-DWG drawing candidate."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.file_integrity import (
    FileIdentityError,
    assert_path_identity,
    open_bound_file,
)
from cad_agent.visual_evidence import _path_contains_windows_reparse_point


NATIVE_DWG_PROVENANCE_SCHEMA_VERSION = (
    "native-dwg-full-drawing-provenance-1.0"
)
NATIVE_DWG_PROVENANCE_MODE = "NATIVE_DWG_FULL_DRAWING"
NATIVE_DWG_PROFILE_ID = "native-dwg-full-drawing"
NATIVE_DWG_SCOPE = "FULL_DRAWING"
NATIVE_DWG_CALIBRATION_MODE = "NOT_APPLICABLE_NATIVE_CAD"
NATIVE_DWG_READBACK_SCHEMA_VERSION = "native-dwg-readback-1.0"

_PACKET_FIELDS = frozenset(
    {
        "schema_version",
        "provenance_mode",
        "profile_id",
        "scope",
        "source_format",
        "candidate_format",
        "source_path_binding_sha256",
        "candidate_path_binding_sha256",
        "source_sha256",
        "candidate_sha256",
        "candidate_id",
        "source_readback",
        "candidate_readback",
        "source_setup_audit_sha256",
        "candidate_setup_audit_sha256",
        "calibration_mode",
        "provenance_sha256",
    }
)
_READBACK_FIELDS = frozenset(
    {
        "schema_version",
        "artifact_path",
        "artifact_sha256",
        "entity_count",
        "entity_signature_sha256",
        "observation_sha256",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class NativeDwgProvenanceError(ValueError):
    """Categorical refusal for malformed or stale native-DWG evidence."""


def _fail(code: str) -> None:
    raise NativeDwgProvenanceError(code)


def _closed(
    value: object,
    fields: frozenset[str],
    code: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail(code)
    if any(type(key) is not str for key in value):
        _fail(code)
    return deepcopy(dict(value))


def _sha(value: object, code: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _text(value: object, code: str) -> str:
    if type(value) is not str or not value:
        _fail(code)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        _fail(code)
    return value


def _regular_file(value: object, code: str) -> Path:
    try:
        path = Path(value)
    except (TypeError, ValueError):
        _fail(code)
    if (
        not path.is_file()
        or path.is_symlink()
        or _path_contains_windows_reparse_point(path)
    ):
        _fail(code)
    try:
        return path.resolve(strict=True)
    except OSError as error:
        raise NativeDwgProvenanceError(code) from error


def _snapshot(value: object, code: str) -> tuple[Path, bytes, str]:
    path = _regular_file(value, code)
    descriptor = -1
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor, descriptor_stat = open_bound_file(
            path, flags=flags, label=code
        )
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            data = stream.read()
        assert_path_identity(path, descriptor_stat, label=code)
    except FileIdentityError as error:
        raise NativeDwgProvenanceError(code) from error
    except OSError as error:
        if descriptor >= 0:
            os.close(descriptor)
        raise NativeDwgProvenanceError(code) from error
    return path, data, hashlib.sha256(data).hexdigest()


def _path_binding(path: Path, *, role: str) -> str:
    return canonical_json_sha256(
        {
            "identity_kind": f"native-dwg-{role}-path-v1",
            "canonical_path": str(path.resolve(strict=False))
            .replace("/", "\\")
            .casefold(),
        }
    )


def _readback_hash(record: Mapping[str, object]) -> str:
    return canonical_json_sha256(
        {
            key: deepcopy(record[key])
            for key in _READBACK_FIELDS
            if key != "observation_sha256"
        }
    )


def _validate_readback(value: object) -> dict[str, object]:
    record = _closed(value, _READBACK_FIELDS, "READBACK_SCHEMA_INVALID")
    if record["schema_version"] != NATIVE_DWG_READBACK_SCHEMA_VERSION:
        _fail("READBACK_SCHEMA_INVALID")
    path = _text(record["artifact_path"], "READBACK_SCHEMA_INVALID")
    _sha(record["artifact_sha256"], "READBACK_SCHEMA_INVALID")
    if type(record["entity_count"]) is not int or record["entity_count"] < 0:
        _fail("READBACK_SCHEMA_INVALID")
    _sha(record["entity_signature_sha256"], "READBACK_SCHEMA_INVALID")
    observation_sha256 = _sha(
        record["observation_sha256"], "READBACK_HASH_MISMATCH"
    )
    if observation_sha256 != _readback_hash(record):
        _fail("READBACK_HASH_MISMATCH")
    record["artifact_path"] = path
    return record


def _packet_without_checksum(
    packet: Mapping[str, object],
) -> dict[str, object]:
    return {
        key: deepcopy(packet[key])
        for key in _PACKET_FIELDS
        if key != "provenance_sha256"
    }


def validate_native_dwg_provenance(payload: object) -> dict[str, object]:
    """Validate and detach one native-DWG full-drawing packet."""

    packet = _closed(payload, _PACKET_FIELDS, "PROVENANCE_SCHEMA_INVALID")
    if packet["schema_version"] != NATIVE_DWG_PROVENANCE_SCHEMA_VERSION:
        _fail("PROVENANCE_SCHEMA_INVALID")
    if packet["provenance_mode"] != NATIVE_DWG_PROVENANCE_MODE:
        _fail("PROVENANCE_SCHEMA_INVALID")
    if packet["profile_id"] != NATIVE_DWG_PROFILE_ID:
        _fail("PROVENANCE_SCHEMA_INVALID")
    if packet["scope"] != NATIVE_DWG_SCOPE:
        _fail("PROVENANCE_SCHEMA_INVALID")
    if packet["source_format"] != "DWG" or packet["candidate_format"] != "DXF":
        _fail("PROVENANCE_SCHEMA_INVALID")

    source_sha256 = _sha(
        packet["source_sha256"], "SOURCE_ARTIFACT_HASH_INVALID"
    )
    candidate_sha256 = _sha(
        packet["candidate_sha256"], "CANDIDATE_ARTIFACT_HASH_INVALID"
    )
    source_path_binding = _sha(
        packet["source_path_binding_sha256"],
        "SOURCE_PATH_BINDING_INVALID",
    )
    candidate_path_binding = _sha(
        packet["candidate_path_binding_sha256"],
        "CANDIDATE_PATH_BINDING_INVALID",
    )
    if packet["candidate_id"] != (
        "native-dwg-full-drawing:" + candidate_sha256
    ):
        _fail("CANDIDATE_ID_MISMATCH")
    source_readback = _validate_readback(packet["source_readback"])
    candidate_readback = _validate_readback(packet["candidate_readback"])
    if source_readback["artifact_sha256"] != source_sha256:
        _fail("SOURCE_ARTIFACT_HASH_MISMATCH")
    if candidate_readback["artifact_sha256"] != candidate_sha256:
        _fail("CANDIDATE_ARTIFACT_HASH_MISMATCH")
    if (
        source_readback["entity_count"]
        != candidate_readback["entity_count"]
    ):
        _fail("ENTITY_COUNT_MISMATCH")
    if (
        source_readback["entity_signature_sha256"]
        != candidate_readback["entity_signature_sha256"]
    ):
        _fail("ENTITY_SIGNATURE_MISMATCH")
    _sha(
        packet["source_setup_audit_sha256"],
        "SOURCE_SETUP_AUDIT_HASH_INVALID",
    )
    _sha(
        packet["candidate_setup_audit_sha256"],
        "CANDIDATE_SETUP_AUDIT_HASH_INVALID",
    )
    if packet["calibration_mode"] != NATIVE_DWG_CALIBRATION_MODE:
        _fail("PROVENANCE_SCHEMA_INVALID")
    if (
        source_path_binding
        != _path_binding(
            Path(source_readback["artifact_path"]), role="source"
        )
    ):
        _fail("SOURCE_PATH_BINDING_INVALID")
    if (
        candidate_path_binding
        != _path_binding(
            Path(candidate_readback["artifact_path"]), role="candidate"
        )
    ):
        _fail("CANDIDATE_PATH_BINDING_INVALID")
    expected_sha256 = canonical_json_sha256(_packet_without_checksum(packet))
    if packet["provenance_sha256"] != expected_sha256:
        _fail("PROVENANCE_HASH_MISMATCH")
    packet["provenance_sha256"] = expected_sha256
    return packet


def build_native_dwg_provenance(
    *,
    source_path: str | os.PathLike[str],
    candidate_path: str | os.PathLike[str],
    source_readback: Mapping[str, object],
    candidate_readback: Mapping[str, object],
    source_setup_audit_sha256: str,
    candidate_setup_audit_sha256: str,
) -> dict[str, object]:
    """Seal exact source/candidate files and equal native readback identity."""

    source, _source_bytes, source_sha256 = _snapshot(
        source_path, "SOURCE_ARTIFACT_INVALID"
    )
    candidate, _candidate_bytes, candidate_sha256 = _snapshot(
        candidate_path, "CANDIDATE_ARTIFACT_INVALID"
    )
    if source.suffix.casefold() != ".dwg":
        _fail("SOURCE_FORMAT_INVALID")
    if candidate.suffix.casefold() != ".dxf":
        _fail("CANDIDATE_FORMAT_INVALID")
    source_observation = _validate_readback(source_readback)
    candidate_observation = _validate_readback(candidate_readback)
    if Path(source_observation["artifact_path"]).resolve() != source:
        _fail("SOURCE_PATH_BINDING_INVALID")
    if Path(candidate_observation["artifact_path"]).resolve() != candidate:
        _fail("CANDIDATE_PATH_BINDING_INVALID")
    if source_observation["artifact_sha256"] != source_sha256:
        _fail("SOURCE_ARTIFACT_HASH_MISMATCH")
    if candidate_observation["artifact_sha256"] != candidate_sha256:
        _fail("CANDIDATE_ARTIFACT_HASH_MISMATCH")
    _sha(source_setup_audit_sha256, "SOURCE_SETUP_AUDIT_HASH_INVALID")
    _sha(candidate_setup_audit_sha256, "CANDIDATE_SETUP_AUDIT_HASH_INVALID")
    packet: dict[str, object] = {
        "schema_version": NATIVE_DWG_PROVENANCE_SCHEMA_VERSION,
        "provenance_mode": NATIVE_DWG_PROVENANCE_MODE,
        "profile_id": NATIVE_DWG_PROFILE_ID,
        "scope": NATIVE_DWG_SCOPE,
        "source_format": "DWG",
        "candidate_format": "DXF",
        "source_path_binding_sha256": _path_binding(source, role="source"),
        "candidate_path_binding_sha256": _path_binding(
            candidate, role="candidate"
        ),
        "source_sha256": source_sha256,
        "candidate_sha256": candidate_sha256,
        "candidate_id": "native-dwg-full-drawing:" + candidate_sha256,
        "source_readback": source_observation,
        "candidate_readback": candidate_observation,
        "source_setup_audit_sha256": source_setup_audit_sha256,
        "candidate_setup_audit_sha256": candidate_setup_audit_sha256,
        "calibration_mode": NATIVE_DWG_CALIBRATION_MODE,
        "provenance_sha256": "",
    }
    if (
        source_observation["entity_count"]
        != candidate_observation["entity_count"]
    ):
        _fail("ENTITY_COUNT_MISMATCH")
    if (
        source_observation["entity_signature_sha256"]
        != candidate_observation["entity_signature_sha256"]
    ):
        _fail("ENTITY_SIGNATURE_MISMATCH")
    packet["provenance_sha256"] = canonical_json_sha256(
        _packet_without_checksum(packet)
    )
    return validate_native_dwg_provenance(packet)


def build_native_dwg_r3_inputs(
    packet: Mapping[str, object],
) -> dict[str, object]:
    """Build the explicit native context and intentionally empty R3 inputs."""

    normalized = validate_native_dwg_provenance(packet)
    return {
        "upstream_context": {
            "provenance_mode": NATIVE_DWG_PROVENANCE_MODE,
            "candidate": {
                "candidate_id": normalized["candidate_id"],
                "candidate_drawing_sha256": normalized["candidate_sha256"],
            },
            "native_dwg_provenance": normalized,
        },
        "components": [],
        "views": [],
    }


def compose_native_dwg_query_binding(
    *,
    source_path: str | os.PathLike[str],
    candidate_path: str | os.PathLike[str],
    source_readback: Mapping[str, object],
    candidate_readback: Mapping[str, object],
    source_setup_audit_sha256: str,
    candidate_setup_audit_sha256: str,
    run_id: str,
    project_id: str,
    drawing_id: str,
) -> dict[str, object]:
    """Compose a current, read-only DARA/R3/R4 native-DWG binding."""

    from cad_agent import component_view_registry as r3
    from cad_agent import drawing_artifact_reference as dara
    from cad_agent.candidate_revision import (
        CANDIDATE_REVISION_ROOT_KIND,
        CANDIDATE_REVISION_V11_SCHEMA_VERSION,
        build_candidate_revision,
        build_candidate_revision_state,
    )

    packet = build_native_dwg_provenance(
        source_path=source_path,
        candidate_path=candidate_path,
        source_readback=source_readback,
        candidate_readback=candidate_readback,
        source_setup_audit_sha256=source_setup_audit_sha256,
        candidate_setup_audit_sha256=candidate_setup_audit_sha256,
    )
    r3_inputs = build_native_dwg_r3_inputs(packet)
    context = r3_inputs["upstream_context"]
    registry = r3.build_component_view_registry(**r3_inputs)
    registry_provenance = r3.component_view_registry_provenance_evidence(
        registry, upstream_context=context
    )
    artifact_path, artifact_bytes, artifact_sha256 = _snapshot(
        candidate_path, "CANDIDATE_ARTIFACT_INVALID"
    )
    if artifact_sha256 != packet["candidate_sha256"]:
        _fail("CANDIDATE_ARTIFACT_HASH_MISMATCH")
    scope = {"run_id": run_id, "project_id": project_id, "drawing_id": drawing_id}
    baseline_evidence = {
        "evidence_kind": "BASELINE_CUSTODY",
        "evidence_id": "native-dwg-baseline-" + packet["provenance_sha256"][:24],
        "evidence_sha256": canonical_json_sha256(
            {
                "identity_kind": "native-dwg-baseline-custody-v1",
                "scope": scope,
                "candidate_sha256": packet["candidate_sha256"],
                "provenance_sha256": packet["provenance_sha256"],
            }
        ),
    }
    baseline_reference = dara.issue_drawing_artifact_reference(
        **scope,
        artifact_role="BASELINE",
        artifact_bytes=artifact_bytes,
        upstream_evidence=baseline_evidence,
    )
    baseline_observation = dara.observe_drawing_artifact_currentness(
        reference=baseline_reference,
        artifact_bytes=artifact_bytes,
        observation_evidence_sha256=canonical_json_sha256(
            {
                "identity_kind": "native-dwg-baseline-observation-v1",
                "reference_sha256": baseline_reference["reference_sha256"],
            }
        ),
    )
    candidate_evidence = {
        "evidence_kind": "R3_CANDIDATE_CUSTODY",
        "evidence_id": "native-dwg-candidate-" + packet["provenance_sha256"][:24],
        "evidence_sha256": canonical_json_sha256(
            {
                "identity_kind": "native-dwg-candidate-custody-v1",
                "scope": scope,
                "candidate_sha256": packet["candidate_sha256"],
                "registry_snapshot_sha256": registry[
                    "registry_snapshot_sha256"
                ],
            }
        ),
    }
    candidate_reference = dara.issue_drawing_artifact_reference(
        **scope,
        artifact_role="R3_CANDIDATE",
        artifact_bytes=artifact_bytes,
        upstream_evidence=candidate_evidence,
        r3_provenance_binding={
            "registry_snapshot_sha256": registry[
                "registry_snapshot_sha256"
            ],
            "provenance_sha256": registry_provenance["provenance_sha256"],
        },
    )
    candidate_observation = dara.observe_drawing_artifact_currentness(
        reference=candidate_reference,
        artifact_bytes=artifact_bytes,
        observation_evidence_sha256=canonical_json_sha256(
            {
                "identity_kind": "native-dwg-candidate-observation-v1",
                "reference_sha256": candidate_reference["reference_sha256"],
            }
        ),
    )
    impact = r3.project_linked_view_impacts(
        registry=registry,
        component_ids=[],
        view_ids=[],
        upstream_context=context,
    )
    change_impact = {
        "registry_snapshot_sha256": registry["registry_snapshot_sha256"],
        "impact": impact,
        "provenance_evidence": registry_provenance,
        "upstream_context": deepcopy(context),
        "root_candidate_reference": deepcopy(candidate_reference),
        "root_candidate_observation": deepcopy(candidate_observation),
        "root_candidate_artifact_bytes": artifact_bytes,
    }
    mutation_evidence = {
        "evidence_kind": "R4_ROOT_PRE_REPAIR",
        "evidence_id": "native-dwg-root-" + packet["provenance_sha256"][:24],
        "r3_candidate_reference_id": candidate_reference["reference_id"],
        "r3_candidate_reference_sha256": candidate_reference[
            "reference_sha256"
        ],
        "candidate_artifact_sha256": candidate_reference["artifact_sha256"],
        "registry_snapshot_sha256": registry["registry_snapshot_sha256"],
    }
    baseline_context = {
        "reference": baseline_reference,
        "observation": baseline_observation,
        "artifact_bytes": artifact_bytes,
    }
    revision = build_candidate_revision(
        registry=registry,
        base_cad_handoff=None,
        baseline_context=baseline_context,
        parent_candidate=None,
        change_impact=change_impact,
        mutation_evidence=mutation_evidence,
        lineage_context=(),
        schema_version=CANDIDATE_REVISION_V11_SCHEMA_VERSION,
        candidate_kind=CANDIDATE_REVISION_ROOT_KIND,
    )
    candidate_state = build_candidate_revision_state(
        candidate_revisions=[revision],
        current_candidate_revision_sha256=revision[
            "candidate_revision_sha256"
        ],
    )
    return {
        "packet": packet,
        "reference": candidate_reference,
        "current_observation": candidate_observation,
        "artifact_bytes": artifact_bytes,
        "parent_reference": None,
        "accepted_transition_evidence_sha256": None,
        "registry": registry,
        "registry_upstream_context": context,
        "candidate_revision": revision,
        "candidate_state": candidate_state,
        "baseline_context": baseline_context,
        "change_impact": change_impact,
        "mutation_evidence": mutation_evidence,
        "expected_active_document_path": str(artifact_path),
        "base_cad_handoff": None,
    }


__all__ = [
    "NATIVE_DWG_PROVENANCE_SCHEMA_VERSION",
    "NATIVE_DWG_PROVENANCE_MODE",
    "NATIVE_DWG_PROFILE_ID",
    "NATIVE_DWG_SCOPE",
    "NATIVE_DWG_CALIBRATION_MODE",
    "NATIVE_DWG_READBACK_SCHEMA_VERSION",
    "NativeDwgProvenanceError",
    "build_native_dwg_provenance",
    "validate_native_dwg_provenance",
    "build_native_dwg_r3_inputs",
    "compose_native_dwg_query_binding",
]
