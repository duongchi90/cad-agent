"""Pure composition boundary for post-provider visual-verdict finalization.

This module intentionally owns no scope, currentness, worker, revision, evidence,
or provider-transport authority. It reuses the existing owners, verifies the
post-provider state, and seals only the final R5 request/observation/verdict
identity needed by downstream gates.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from datetime import datetime

from agent_lib.codex_worker import CodexWorkerResult, consume_task6_result
from agent_lib.codex_worker_process import WorkerCleanupResult
from cad_agent.candidate_revision import validate_candidate_revision_state
from cad_agent.drawing_artifact_reference import (
    require_current_drawing_artifact_reference,
)
from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.vision_handoff import (
    BoundWorkerThread,
    ServerOwnedAuthorityContext,
    ServerOwnedWorkerBindingContext,
    ValidatedVisionHandoff,
    resume_worker_thread,
)
from cad_agent.visual_contracts import validate_visual_contract
from cad_agent.visual_evidence import validate_visual_evidence_freshness


R5_VISUAL_VERDICT_RESULT_SCHEMA_VERSION = "r5-visual-verdict-result-1.0"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_CRITICALITIES = frozenset({"CRITICAL", "NORMAL"})
_REGION_STATUSES = frozenset({"PASS", "FAIL", "SKIP", "NOT_RUN"})
_VERDICTS = frozenset({"PASS", "FAIL", "NEEDS_HUMAN"})


class VisualSupervisorAdapterError(ValueError):
    """Categorical, fail-closed refusal for malformed or stale evidence."""


def _fail(message: str) -> None:
    raise VisualSupervisorAdapterError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object mapping")
    if any(type(key) is not str for key in value):
        _fail(f"{label} properties must use string keys")
    return value


def _plain_string(value: object, *, label: str) -> str:
    if type(value) is not str:
        _fail(f"{label} must be an exact built-in string")
    return value


def _identifier(value: object, *, label: str) -> str:
    value = _plain_string(value, label=label)
    if _IDENTIFIER.fullmatch(value) is None:
        _fail(f"{label} is invalid")
    return value


def _sha(value: object, *, label: str) -> str:
    value = _plain_string(value, label=label)
    if _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def _closed(
    value: Mapping[str, object],
    required: set[str],
    *,
    label: str,
    optional: set[str] | frozenset[str] = frozenset(),
) -> None:
    keys = set(value)
    missing = required - keys
    if missing:
        _fail(f"{label} is missing required field(s): {', '.join(sorted(missing))}")
    unknown = keys - required - set(optional)
    if unknown:
        _fail(f"{label} contains unknown field(s): {', '.join(sorted(unknown))}")


def _task6_result(value: object, *, label: str) -> CodexWorkerResult:
    """Validate the accepted Task6 public result, never a caller-made mapping."""

    if not isinstance(value, CodexWorkerResult):
        _fail("R5_B3_TASK6_PUBLIC_SEAM_MISSING: task6_result must be CodexWorkerResult")
    if value.operation not in {"turn", "steer"}:
        _fail(f"{label} operation is not a visual provider turn")
    if value.status != "COMPLETED" or value.success is not True:
        _fail(f"{label} terminal result is timeout/cancel/late or failed")
    if value.failure_code is not None:
        _fail(f"{label} carries a worker failure code")
    if value.candidate_trusted is not False or value.promotion_safe is not False:
        _fail(f"{label} exposes trusted/promotion-safe candidate output")
    _identifier(value.thread_id, label=f"{label}.thread_id")
    if value.turn_id is None:
        _fail(
            "R5_B3_TASK6_PUBLIC_SEAM_MISSING: completed Task6 result has no turn identity"
        )
    _identifier(value.turn_id, label=f"{label}.turn_id")
    if not isinstance(value.events, tuple) or not value.events:
        _fail(f"{label}.events must contain terminal worker events")
    if value.cleanup_result is not None and not isinstance(
        value.cleanup_result, WorkerCleanupResult
    ):
        _fail(f"{label}.cleanup_result is not accepted worker cleanup evidence")
    return value


def _cleanup_result(value: object, *, label: str) -> WorkerCleanupResult:
    if not isinstance(value, WorkerCleanupResult):
        _fail(
            "R5_B3_TASK6_PUBLIC_SEAM_MISSING: cleanup_result must be "
            "accepted WorkerCleanupResult"
        )
    if not (
        value.status == "CLEANUP_SUCCEEDED"
        and value.success is True
        and value.promotion_safe is True
        and value.survivor_pids == ()
        and value.survivor_count == 0
        and value.error_code is None
    ):
        _fail(f"{label} is not verified cleanup evidence")
    return value


_OWNER_STATE_FIELDS = {
    "visual_review_scope",
    "candidate_revision_state",
    "drawing_reference",
    "drawing_observation",
    "drawing_artifact_bytes",
    "visual_evidence",
    "visual_run_manifest",
    "manifest_bytes_sha256",
    "drawing_sha256_before_dispatch",
    "task6_result",
    "cleanup_result",
}
_CAMERA_OWNER_FIELDS = {"visual_capture_plan", "native_render_evidence"}


def _owner_state(value: object, *, label: str) -> Mapping[str, object]:
    state = _mapping(value, label=label)
    if "task6_result" not in state:
        _fail(
            "R5_B3_TASK6_PUBLIC_SEAM_MISSING: owner state has no accepted task6_result"
        )
    _closed(
        state,
        _OWNER_STATE_FIELDS,
        label=label,
        optional={"pre_repair_r5_verdict", *_CAMERA_OWNER_FIELDS},
    )
    has_plan = "visual_capture_plan" in state
    has_native = "native_render_evidence" in state
    if has_plan != has_native:
        _fail("canonical camera plan and native render evidence must be declared together")
    _sha(state["manifest_bytes_sha256"], label=f"{label}.manifest_bytes_sha256")
    _sha(
        state["drawing_sha256_before_dispatch"],
        label=f"{label}.drawing_sha256_before_dispatch",
    )
    if not isinstance(state["drawing_artifact_bytes"], bytes):
        _fail(f"{label}.drawing_artifact_bytes must be bytes from the DARA owner")
    _task6_result(state["task6_result"], label=f"{label}.task6_result")
    _cleanup_result(state["cleanup_result"], label=f"{label}.cleanup_result")
    return state


def _provider(
    value: object,
) -> tuple[CodexWorkerResult, str, str, list[dict[str, object]]]:
    provider = _mapping(value, label="provider_result")
    required = {"task6_result", "provider_verdict", "candidate_revision_sha256", "regions"}
    _closed(provider, required, label="provider_result")
    task6 = _task6_result(provider["task6_result"], label="provider_result.task6_result")
    candidate_sha = _sha(
        provider["candidate_revision_sha256"],
        label="provider_result.candidate_revision_sha256",
    )
    verdict = _plain_string(
        provider["provider_verdict"], label="provider_result.provider_verdict"
    )
    if verdict not in _VERDICTS:
        _fail("provider verdict is unknown")
    raw_regions = provider["regions"]
    if not isinstance(raw_regions, Sequence) or isinstance(
        raw_regions, (str, bytes, bytearray)
    ):
        _fail("provider regions must be a list")
    normalized: list[dict[str, object]] = []
    for index, region in enumerate(raw_regions):
        item = _mapping(region, label=f"provider_result.regions[{index}]")
        required_region = {
            "region_id",
            "view_id",
            "sheet_id",
            "layout_id",
            "criticality",
            "status",
        }
        _closed(item, required_region, label=f"provider_result.regions[{index}]")
        record: dict[str, object] = {}
        for field in ("region_id", "view_id", "sheet_id", "layout_id"):
            record[field] = _identifier(
                item[field], label=f"provider_result.regions[{index}].{field}"
            )
        criticality = _plain_string(
            item["criticality"],
            label=f"provider_result.regions[{index}].criticality",
        )
        if criticality not in _CRITICALITIES:
            _fail(f"provider_result.regions[{index}].criticality is invalid")
        record["criticality"] = criticality
        status = _plain_string(
            item["status"], label=f"provider_result.regions[{index}].status"
        )
        if status not in _REGION_STATUSES:
            _fail(f"provider_result.regions[{index}].status is unknown")
        record["status"] = status
        normalized.append(record)
    if not normalized:
        _fail("provider regions must not be empty")
    normalized.sort(key=lambda item: str(item["region_id"]))
    if len({str(item["region_id"]) for item in normalized}) != len(normalized):
        _fail("provider regions contain duplicate region identity")
    return task6, candidate_sha, verdict, normalized


def _scope_payload_from_regions(
    regions: Sequence[Mapping[str, object]], template: Mapping[str, object]
) -> dict[str, object]:
    if not regions:
        _fail("provider regions must not be empty")
    return {
        "schema_version": template["schema_version"],
        "scope_id": template["scope_id"],
        "run_id": template["run_id"],
        "registry_snapshot_sha256": template["registry_snapshot_sha256"],
        "candidate_revision_sha256": template["candidate_revision_sha256"],
        "candidate_state_sha256": template["candidate_state_sha256"],
        "regions": [
            {
                key: region[key]
                for key in (
                    "region_id",
                    "view_id",
                    "sheet_id",
                    "layout_id",
                    "criticality",
                )
            }
            for region in regions
        ],
    }


def _evidence_payload(value: object, *, label: str) -> Mapping[str, object]:
    root = _mapping(value, label=label)
    payload = root.get("payload")
    if payload is None:
        return root
    return _mapping(payload, label=f"{label}.payload")


def _stable_evidence_identity(value: object, *, label: str) -> dict[str, object]:
    payload = _evidence_payload(value, label=label)
    region_id = _identifier(payload.get("region_id"), label=f"{label}.region_id")
    stable: dict[str, object] = {"region_id": region_id}
    for field in (
        "drawing_sha256_before",
        "drawing_sha256_after",
        "latest_mutation_sha256",
        "visual_run_manifest_sha256",
        "region_config_sha256",
        "session_state_sha256_before",
        "session_state_sha256_after",
    ):
        stable[field] = _sha(payload.get(field), label=f"{label}.{field}")

    artifacts = payload.get("artifacts")
    if type(artifacts) is not list or not artifacts:
        _fail("R5_EVIDENCE_SET_INVALID")
    stable_artifacts: list[dict[str, object]] = []
    for index, raw_artifact in enumerate(artifacts):
        artifact = _mapping(raw_artifact, label=f"{label}.artifacts[{index}]")
        kind = _identifier(
            artifact.get("kind"), label=f"{label}.artifacts[{index}].kind"
        )
        sha256 = _sha(
            artifact.get("sha256"), label=f"{label}.artifacts[{index}].sha256"
        )
        byte_length = artifact.get("byte_length")
        if type(byte_length) is not int or byte_length <= 0:
            _fail("R5_EVIDENCE_SET_INVALID")
        mime_type = _plain_string(
            artifact.get("mime_type"),
            label=f"{label}.artifacts[{index}].mime_type",
        )
        item: dict[str, object] = {
            "kind": kind,
            "sha256": sha256,
            "byte_length": byte_length,
            "mime_type": mime_type,
        }
        for dimension in ("width", "height"):
            if dimension in artifact:
                dimension_value = artifact[dimension]
                if type(dimension_value) is not int or dimension_value <= 0:
                    _fail("R5_EVIDENCE_SET_INVALID")
                item[dimension] = dimension_value
        stable_artifacts.append(item)
    stable_artifacts.sort(key=lambda item: str(item["kind"]))
    if len({str(item["kind"]) for item in stable_artifacts}) != len(stable_artifacts):
        _fail("R5_EVIDENCE_SET_INVALID")
    stable["artifacts"] = stable_artifacts
    try:
        fingerprint = canonical_json_sha256(stable)
    except Exception:
        _fail("R5_EVIDENCE_SET_INVALID")
    return {
        "region_id": region_id,
        "evidence_fingerprint_sha256": fingerprint,
    }


def _validate_evidence_set(
    state: Mapping[str, object],
    *,
    scope: Mapping[str, object],
    label: str,
) -> dict[str, object]:
    raw = state["visual_evidence"]
    if type(raw) is not list:
        _fail("R5_EVIDENCE_SET_INVALID")
    raw_regions = scope.get("regions")
    if not isinstance(raw_regions, Sequence) or isinstance(
        raw_regions, (str, bytes, bytearray)
    ):
        _fail("R5_EVIDENCE_SET_INVALID")
    expected_ids = [
        _identifier(region.get("region_id"), label=f"{label}.scope.region_id")
        for region in raw_regions
        if isinstance(region, Mapping)
    ]
    if len(expected_ids) != len(raw_regions) or len(set(expected_ids)) != len(expected_ids):
        _fail("R5_EVIDENCE_SET_INVALID")
    if len(raw) != len(expected_ids):
        _fail("R5_EVIDENCE_SET_INVALID")

    records: list[tuple[str, object]] = []
    identities: list[dict[str, object]] = []
    observed_ids: set[str] = set()
    for index, evidence in enumerate(raw):
        try:
            validated = validate_visual_evidence_freshness(
                evidence,
                state["manifest_bytes_sha256"],
                state["visual_run_manifest"],
                state["drawing_sha256_before_dispatch"],
            )
        except Exception:
            _fail("R5_EVIDENCE_STALE")
        payload = _evidence_payload(
            validated, label=f"{label}.visual_evidence[{index}]"
        )
        run_id = _identifier(
            payload.get("run_id"),
            label=f"{label}.visual_evidence[{index}].run_id",
        )
        region_id = _identifier(
            payload.get("region_id"),
            label=f"{label}.visual_evidence[{index}].region_id",
        )
        if run_id != scope.get("run_id") or region_id not in expected_ids:
            _fail("R5_EVIDENCE_SET_INVALID")
        if region_id in observed_ids:
            _fail("R5_EVIDENCE_SET_INVALID")
        observed_ids.add(region_id)
        records.append((region_id, copy.deepcopy(validated)))
        identities.append(
            _stable_evidence_identity(
                validated, label=f"{label}.visual_evidence[{index}]"
            )
        )
    if observed_ids != set(expected_ids):
        _fail("R5_EVIDENCE_SET_INVALID")
    records.sort(key=lambda item: item[0])
    identities.sort(key=lambda item: str(item["region_id"]))
    return {
        "records": [item[1] for item in records],
        "identities": identities,
    }


_NATIVE_EVIDENCE_FIELDS = {
    "schema_version",
    "request_id",
    "run_id",
    "drawing_sha256",
    "latest_mutation_sha256",
    "visual_run_manifest_sha256",
    "layout",
    "artifact_kind",
    "render_options",
    "renderer",
    "artifact",
    "capture_timestamp",
    "changed",
    "dbmod_before",
    "dbmod_after",
    "warnings",
    "visual_capture_receipt",
}
_NATIVE_CAMERA_FIELDS = {
    "schema_version",
    "capture_id",
    "capture_class",
    "parent_region_id",
    "region_id",
    "scope_id",
    "view_id",
    "sheet_id",
    "layout_id",
    "candidate_revision_sha256",
    "candidate_state_sha256",
    "visual_capture_plan_sha256",
    "zoom_mode",
    "wcs_bbox",
    "margin_ratio",
    "view_direction",
    "ucs",
    "visual_style",
}


def _positive_int(value: object, *, label: str) -> int:
    if type(value) is not int or value <= 0:
        _fail(f"{label} must be a positive integer")
    return value


def _native_camera_state(
    state: Mapping[str, object],
    *,
    scope: Mapping[str, object],
    label: str,
) -> dict[str, object] | None:
    if "visual_capture_plan" not in state:
        return None
    try:
        plan = validate_visual_contract(
            state["visual_capture_plan"],
            contract="visual_capture_plan",
            server_scope=scope,
        )
        plan_sha = canonical_json_sha256(plan)
    except Exception:
        _fail("native camera plan is invalid or outside server-owned scope")

    raw = state["native_render_evidence"]
    if type(raw) is not list:
        _fail("native camera evidence must be a list")
    captures = plan.get("captures")
    if type(captures) is not list or not captures:
        _fail("native camera plan has no captures")
    expected = {
        _identifier(capture.get("capture_id"), label=f"{label}.camera.capture_id"): capture
        for capture in captures
        if isinstance(capture, Mapping)
    }
    if len(expected) != len(captures) or len(raw) != len(expected):
        _fail("native camera evidence coverage does not match every plan capture")

    manifest = _mapping(
        state["visual_run_manifest"], label=f"{label}.visual_run_manifest"
    )
    latest_mutation = _sha(
        manifest.get("latest_mutation_sha256"),
        label=f"{label}.visual_run_manifest.latest_mutation_sha256",
    )
    manifest_sha = _sha(
        state["manifest_bytes_sha256"], label=f"{label}.manifest_bytes_sha256"
    )
    drawing_before = _sha(
        state["drawing_sha256_before_dispatch"],
        label=f"{label}.drawing_sha256_before_dispatch",
    )
    drawing_reference = _mapping(
        state["drawing_reference"], label=f"{label}.drawing_reference"
    )
    drawing_artifact = _sha(
        drawing_reference.get("artifact_sha256"),
        label=f"{label}.drawing_reference.artifact_sha256",
    )
    if drawing_before != drawing_artifact:
        _fail("native camera drawing identity is stale against the current DARA artifact")
    if plan.get("latest_mutation_sha256") != latest_mutation:
        _fail("native camera plan is stale against the latest mutation")

    records: list[tuple[str, object]] = []
    identities: list[dict[str, object]] = []
    observed: set[str] = set()
    for index, raw_evidence in enumerate(raw):
        evidence = _mapping(raw_evidence, label=f"{label}.native_render_evidence[{index}]")
        _closed(
            evidence,
            _NATIVE_EVIDENCE_FIELDS,
            label=f"{label}.native_render_evidence[{index}]",
        )
        if evidence["schema_version"] != "autocad-native-render-evidence-1.0":
            _fail("native camera evidence schema is unsupported")
        _plain_string(evidence["request_id"], label=f"{label}.native.request_id")
        if evidence["run_id"] != plan.get("run_id"):
            _fail("native camera evidence run is foreign")
        if evidence["drawing_sha256"] != drawing_artifact:
            _fail("native camera evidence drawing is stale")
        if evidence["latest_mutation_sha256"] != latest_mutation:
            _fail("native camera evidence mutation is stale")
        if evidence["visual_run_manifest_sha256"] != manifest_sha:
            _fail("native camera evidence manifest is stale")
        if evidence["artifact_kind"] != "PNG" or evidence["renderer"] != "AUTOCAD_NATIVE":
            _fail("native camera evidence is not an AutoCAD-native PNG")
        if evidence["changed"] is not False:
            _fail("native camera evidence changed the drawing")
        dbmod_before = evidence["dbmod_before"]
        dbmod_after = evidence["dbmod_after"]
        if (
            type(dbmod_before) is not int
            or type(dbmod_after) is not int
            or dbmod_before < 0
            or dbmod_after < 0
            or dbmod_before != dbmod_after
        ):
            _fail("native camera evidence DBMOD is not read-only")
        warnings = evidence["warnings"]
        if type(warnings) is not list or any(type(item) is not str for item in warnings):
            _fail("native camera evidence warnings are invalid")

        layout = _mapping(evidence["layout"], label=f"{label}.native.layout")
        _closed(layout, {"identity", "name"}, label=f"{label}.native.layout")
        layout_identity = _identifier(
            layout["identity"], label=f"{label}.native.layout.identity"
        )
        _plain_string(layout["name"], label=f"{label}.native.layout.name")

        options = _mapping(
            evidence["render_options"], label=f"{label}.native.render_options"
        )
        _closed(
            options,
            {"background", "dpi", "fit_to_paper", "paper_size", "plot_style", "camera"},
            label=f"{label}.native.render_options",
        )
        if not (
            options["background"] == "white"
            and options["dpi"] == 300
            and options["fit_to_paper"] is True
            and options["paper_size"] == "A4"
            and options["plot_style"] == "monochrome.ctb"
        ):
            _fail("native camera evidence does not use the canonical render policy")
        camera = _mapping(options["camera"], label=f"{label}.native.camera")
        _closed(camera, _NATIVE_CAMERA_FIELDS, label=f"{label}.native.camera")

        try:
            receipt = validate_visual_contract(
                evidence["visual_capture_receipt"],
                contract="visual_capture_receipt",
                server_scope=plan,
            )
        except Exception:
            _fail("native camera visual capture receipt is invalid")
        capture_id = _identifier(
            receipt.get("capture_id"), label=f"{label}.native.receipt.capture_id"
        )
        capture = expected.get(capture_id)
        if capture is None:
            _fail("native camera evidence contains a foreign capture")
        if capture_id in observed:
            _fail("native camera evidence contains duplicate capture coverage")
        observed.add(capture_id)

        expected_camera = {
            "schema_version": "canonical-camera-render-1.0",
            "capture_id": capture["capture_id"],
            "capture_class": capture["capture_class"],
            "parent_region_id": capture["parent_region_id"],
            "region_id": capture["region_id"],
            "scope_id": plan["scope_id"],
            "view_id": capture["view_id"],
            "sheet_id": capture["sheet_id"],
            "layout_id": capture["layout_id"],
            "candidate_revision_sha256": plan["candidate_revision_sha256"],
            "candidate_state_sha256": plan["candidate_state_sha256"],
            "visual_capture_plan_sha256": plan_sha,
            "zoom_mode": capture["zoom_mode"],
            "wcs_bbox": copy.deepcopy(capture["wcs_bbox"]),
            "margin_ratio": capture["margin_ratio"],
            "view_direction": capture["view_direction"],
            "ucs": capture["ucs"],
            "visual_style": capture["visual_style"],
        }
        if dict(camera) != expected_camera:
            _fail("native camera render context does not match the server-owned plan")
        if layout_identity != capture["layout_id"]:
            _fail("native camera layout is foreign to the selected plan capture")

        artifact = _mapping(evidence["artifact"], label=f"{label}.native.artifact")
        _closed(
            artifact,
            {"relative_path", "sha256", "width", "height"},
            label=f"{label}.native.artifact",
        )
        artifact_path = _plain_string(
            artifact["relative_path"], label=f"{label}.native.artifact.relative_path"
        )
        if not artifact_path:
            _fail("native camera artifact path is empty")
        artifact_sha = _sha(
            artifact["sha256"], label=f"{label}.native.artifact.sha256"
        )
        artifact_width = _positive_int(
            artifact["width"], label=f"{label}.native.artifact.width"
        )
        artifact_height = _positive_int(
            artifact["height"], label=f"{label}.native.artifact.height"
        )
        if (
            receipt.get("artifact_sha256") != artifact_sha
            or receipt.get("artifact_width") != artifact_width
            or receipt.get("artifact_height") != artifact_height
        ):
            _fail("native camera receipt does not match its render artifact")
        capture_timestamp = _plain_string(
            evidence["capture_timestamp"], label=f"{label}.native.capture_timestamp"
        )
        if receipt.get("captured_at_utc") != capture_timestamp:
            _fail("native camera receipt timestamp does not match render evidence")
        try:
            receipt_sha = canonical_json_sha256(receipt)
        except Exception:
            _fail("native camera receipt identity cannot be sealed")
        records.append((capture_id, copy.deepcopy(evidence)))
        identities.append(
            {
                "capture_id": capture_id,
                "artifact_sha256": artifact_sha,
                "visual_capture_receipt_sha256": receipt_sha,
            }
        )

    if observed != set(expected):
        _fail("native camera evidence coverage is incomplete")
    records.sort(key=lambda item: item[0])
    identities.sort(key=lambda item: str(item["capture_id"]))
    return {
        "plan": plan,
        "visual_capture_plan_sha256": plan_sha,
        "records": [item[1] for item in records],
        "identities": identities,
    }


def _validate_owner_state(
    state: Mapping[str, object], *, label: str, server_scope: Mapping[str, object]
) -> dict[str, object]:
    try:
        scope = validate_visual_contract(
            state["visual_review_scope"],
            contract="visual_review_scope",
            server_scope=server_scope,
        )
        candidate = validate_candidate_revision_state(state["candidate_revision_state"])
        require_current_drawing_artifact_reference(
            reference=state["drawing_reference"],
            observation=state["drawing_observation"],
            artifact_bytes=state["drawing_artifact_bytes"],
        )
    except VisualSupervisorAdapterError:
        raise
    except Exception:
        _fail(f"{label} accepted owner validation failed")
    evidence = _validate_evidence_set(state, scope=scope, label=label)
    native_camera = _native_camera_state(state, scope=scope, label=label)
    return {
        "scope": scope,
        "candidate": candidate,
        "evidence": evidence,
        "native_camera": native_camera,
    }


def _assert_r5_not_stale(
    authoritative: Mapping[str, object],
    authoritative_manifest: Mapping[str, object],
) -> None:
    previous = authoritative.get("pre_repair_r5_verdict")
    if previous is None:
        return
    previous_map = _mapping(previous, label="authoritative_state.pre_repair_r5_verdict")
    previous_mutation = _sha(
        previous_map.get("latest_mutation_sha256"),
        label="pre_repair_r5_verdict.latest_mutation_sha256",
    )
    current_mutation = _sha(
        authoritative_manifest.get("latest_mutation_sha256"),
        label="authoritative_state.visual_run_manifest.latest_mutation_sha256",
    )
    if previous_map.get("verdict") == "PASS" and previous_mutation != current_mutation:
        _fail("pre-repair R5 verdict is stale after R6 mutation/review")


def _request_binding_facts(
    *,
    request_handoff: ValidatedVisionHandoff | None,
    worker_binding: BoundWorkerThread | None,
    authority_context: ServerOwnedAuthorityContext | None,
    worker_context: ServerOwnedWorkerBindingContext | None,
    task6: CodexWorkerResult,
    run_id: object,
    now: datetime | None,
) -> dict[str, object]:
    try:
        resumed = resume_worker_thread(
            worker_binding,  # type: ignore[arg-type]
            request_handoff,  # type: ignore[arg-type]
            thread_id=task6.thread_id,
            authority_context=authority_context,  # type: ignore[arg-type]
            worker_context=worker_context,  # type: ignore[arg-type]
            now=now,
        )
    except Exception:
        _fail("R5_REQUEST_BINDING_INVALID")

    expected_run = _identifier(run_id, label="visual_scope.run_id")
    resumed_run = _identifier(
        getattr(resumed, "run_id", None), label="request_binding.run_id"
    )
    resumed_thread = _identifier(
        getattr(resumed, "thread_id", None), label="request_binding.thread_id"
    )
    if resumed_run != expected_run or resumed_thread != task6.thread_id:
        _fail("R5_REQUEST_BINDING_INVALID")

    provider_policy = _mapping(
        getattr(authority_context, "provider_policy", None),
        label="request_binding.provider_policy",
    )
    _closed(
        provider_policy,
        {"approval_mode", "experimental_api", "model_identity", "config_sha256"},
        label="request_binding.provider_policy",
    )
    approval_mode = _plain_string(
        provider_policy["approval_mode"],
        label="request_binding.provider_policy.approval_mode",
    )
    if approval_mode != "deny_all" or provider_policy["experimental_api"] is not False:
        _fail("R5_REQUEST_BINDING_INVALID")
    model_identity = _identifier(
        provider_policy["model_identity"],
        label="request_binding.provider_policy.model_identity",
    )
    config_sha256 = _sha(
        provider_policy["config_sha256"],
        label="request_binding.provider_policy.config_sha256",
    )

    model_config = _mapping(
        getattr(resumed, "model_config_identity", None),
        label="request_binding.model_config_identity",
    )
    _closed(
        model_config,
        {"model_identity", "config_sha256"},
        label="request_binding.model_config_identity",
    )
    if (
        _identifier(
            model_config["model_identity"],
            label="request_binding.model_config_identity.model_identity",
        )
        != model_identity
        or _sha(
            model_config["config_sha256"],
            label="request_binding.model_config_identity.config_sha256",
        )
        != config_sha256
    ):
        _fail("R5_REQUEST_BINDING_INVALID")

    sources = getattr(resumed, "instruction_source_identity", None)
    if not isinstance(sources, Sequence) or isinstance(
        sources, (str, bytes, bytearray)
    ):
        _fail("R5_REQUEST_BINDING_INVALID")
    normalized_sources: list[dict[str, object]] = []
    for index, source in enumerate(sources):
        item = _mapping(
            source, label=f"request_binding.instruction_source_identity[{index}]"
        )
        _closed(
            item,
            {"source_id", "role", "sha256"},
            label=f"request_binding.instruction_source_identity[{index}]",
        )
        normalized_sources.append(
            {
                "source_id": _identifier(
                    item["source_id"],
                    label=f"request_binding.instruction_source_identity[{index}].source_id",
                ),
                "role": _identifier(
                    item["role"],
                    label=f"request_binding.instruction_source_identity[{index}].role",
                ),
                "sha256": _sha(
                    item["sha256"],
                    label=f"request_binding.instruction_source_identity[{index}].sha256",
                ),
            }
        )
    normalized_sources.sort(key=lambda item: str(item["source_id"]))
    if len({str(item["source_id"]) for item in normalized_sources}) != len(
        normalized_sources
    ):
        _fail("R5_REQUEST_BINDING_INVALID")

    facts = {
        "adapter_version": _identifier(
            getattr(resumed, "adapter_version", None),
            label="request_binding.adapter_version",
        ),
        "model_config_identity": {
            "model_identity": model_identity,
            "config_sha256": config_sha256,
        },
        "provider_policy": {
            "approval_mode": approval_mode,
            "experimental_api": False,
        },
        "instruction_source_identity": normalized_sources,
        "output_schema_sha256": _sha(
            getattr(resumed, "output_schema_sha256", None),
            label="request_binding.output_schema_sha256",
        ),
        "output_validator_version": _identifier(
            getattr(resumed, "output_validator_version", None),
            label="request_binding.output_validator_version",
        ),
        "approval_reference": _identifier(
            getattr(resumed, "approval_reference", None),
            label="request_binding.approval_reference",
        ),
        "approval_authority": _plain_string(
            getattr(resumed, "approval_authority", None),
            label="request_binding.approval_authority",
        ),
    }
    if facts["approval_authority"] not in {"OWNER", "MASTER_PO"}:
        _fail("R5_REQUEST_BINDING_INVALID")
    return facts


_RESULT_FIELDS = {
    "schema_version",
    "request_sha256",
    "observation_sha256",
    "verdict_id",
    "verdict_sha256",
    "verdict",
    "candidate_revision_sha256",
    "candidate_state_sha256",
    "registry_snapshot_sha256",
    "drawing_reference_sha256",
    "drawing_observation_sha256",
    "latest_mutation_sha256",
    "task6_thread_id",
    "task6_turn_id",
    "regions",
}


def _normalize_result_regions(value: object) -> list[dict[str, object]]:
    if type(value) is not list or not value:
        _fail("R5_VERDICT_RESULT_INVALID")
    normalized: list[dict[str, object]] = []
    required = {
        "region_id",
        "view_id",
        "sheet_id",
        "layout_id",
        "criticality",
        "status",
    }
    for index, raw in enumerate(value):
        if type(raw) is not dict:
            _fail("R5_VERDICT_RESULT_INVALID")
        if set(raw) != required:
            _fail("R5_VERDICT_RESULT_INVALID")
        item: dict[str, object] = {}
        for field in ("region_id", "view_id", "sheet_id", "layout_id"):
            item[field] = _identifier(
                raw[field], label=f"verdict_result.regions[{index}].{field}"
            )
        criticality = _plain_string(
            raw["criticality"],
            label=f"verdict_result.regions[{index}].criticality",
        )
        status = _plain_string(
            raw["status"], label=f"verdict_result.regions[{index}].status"
        )
        if criticality not in _CRITICALITIES or status not in _REGION_STATUSES:
            _fail("R5_VERDICT_RESULT_INVALID")
        item["criticality"] = criticality
        item["status"] = status
        normalized.append(item)
    normalized.sort(key=lambda item: str(item["region_id"]))
    if len({str(item["region_id"]) for item in normalized}) != len(normalized):
        _fail("R5_VERDICT_RESULT_INVALID")
    return normalized


def validate_visual_verdict_result(
    result: object,
    *,
    expected_request_sha256: str | None = None,
    expected_candidate_revision_sha256: str | None = None,
    expected_candidate_state_sha256: str | None = None,
    expected_latest_mutation_sha256: str | None = None,
) -> dict[str, object]:
    """Validate one closed R5 result without consuming Task6 or owning persistence."""

    try:
        if type(result) is not dict or set(result) != _RESULT_FIELDS:
            _fail("R5_VERDICT_RESULT_INVALID")
        if result.get("schema_version") != R5_VISUAL_VERDICT_RESULT_SCHEMA_VERSION:
            _fail("R5_VERDICT_RESULT_INVALID")
        for field in (
            "request_sha256",
            "observation_sha256",
            "verdict_id",
            "verdict_sha256",
            "candidate_revision_sha256",
            "candidate_state_sha256",
            "registry_snapshot_sha256",
            "drawing_reference_sha256",
            "drawing_observation_sha256",
            "latest_mutation_sha256",
        ):
            _sha(result.get(field), label=f"verdict_result.{field}")
        verdict = _plain_string(result.get("verdict"), label="verdict_result.verdict")
        if verdict not in _VERDICTS:
            _fail("R5_VERDICT_RESULT_INVALID")
        _identifier(
            result.get("task6_thread_id"), label="verdict_result.task6_thread_id"
        )
        _identifier(result.get("task6_turn_id"), label="verdict_result.task6_turn_id")
        normalized_regions = _normalize_result_regions(result.get("regions"))

        normalized = copy.deepcopy(result)
        normalized["regions"] = normalized_regions
        verdict_sha = result["verdict_sha256"]
        if result["verdict_id"] != verdict_sha:
            _fail("R5_VERDICT_RESULT_INVALID")
        identity_payload = {
            key: copy.deepcopy(value)
            for key, value in normalized.items()
            if key not in {"verdict_id", "verdict_sha256"}
        }
        if canonical_json_sha256(identity_payload) != verdict_sha:
            _fail("R5_VERDICT_RESULT_INVALID")

        expected_bindings = (
            (expected_request_sha256, "request_sha256"),
            (expected_candidate_revision_sha256, "candidate_revision_sha256"),
            (expected_candidate_state_sha256, "candidate_state_sha256"),
            (expected_latest_mutation_sha256, "latest_mutation_sha256"),
        )
        for expected, field in expected_bindings:
            if expected is not None:
                if _sha(expected, label=f"expected_{field}") != normalized[field]:
                    _fail("R5_VERDICT_RESULT_INVALID")
        return copy.deepcopy(normalized)
    except VisualSupervisorAdapterError:
        raise
    except Exception:
        _fail("R5_VERDICT_RESULT_INVALID")


def finalize_visual_verdict(
    *,
    provider_result: Mapping[str, object],
    authoritative_state: Mapping[str, object],
    post_provider_state: Mapping[str, object],
    server_scope: Mapping[str, object],
    request_handoff: ValidatedVisionHandoff | None = None,
    worker_binding: BoundWorkerThread | None = None,
    authority_context: ServerOwnedAuthorityContext | None = None,
    worker_context: ServerOwnedWorkerBindingContext | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Revalidate owner records and seal the independent final R5 verdict."""

    external_scope = _mapping(server_scope, label="server_scope")
    authoritative = _owner_state(authoritative_state, label="authoritative_state")
    post_provider = _owner_state(post_provider_state, label="post_provider_state")
    task6, provider_candidate_sha, provider_verdict, regions = _provider(provider_result)
    owner_task6 = _task6_result(
        authoritative["task6_result"], label="authoritative_state.task6_result"
    )
    if task6 is not owner_task6 or post_provider["task6_result"] is not owner_task6:
        _fail("Task6 result identity changed or was replayed after provider return")

    auth_validated = _validate_owner_state(
        authoritative, label="authoritative_state", server_scope=external_scope
    )
    post_validated = _validate_owner_state(
        post_provider, label="post_provider_state", server_scope=external_scope
    )
    try:
        auth_scope = validate_visual_contract(
            authoritative["visual_review_scope"],
            contract="visual_review_scope",
            server_scope=external_scope,
        )
        post_scope = validate_visual_contract(
            post_provider["visual_review_scope"],
            contract="visual_review_scope",
            server_scope=external_scope,
        )
        provider_scope = validate_visual_contract(
            _scope_payload_from_regions(regions, external_scope),
            contract="visual_review_scope",
            server_scope=external_scope,
        )
    except Exception:
        _fail("server-owned visual scope validation failed")
    if auth_scope != post_scope or provider_scope != auth_scope:
        _fail("provider regions do not match the server-owned scope")

    auth_candidate = auth_validated["candidate"]
    post_candidate = post_validated["candidate"]
    if auth_candidate != post_candidate:
        _fail("candidate revision/current selection changed after provider return")
    for field, message in (
        ("drawing_reference", "DARA reference changed after provider return"),
        ("drawing_observation", "DARA observation changed after provider return"),
        ("drawing_artifact_bytes", "DARA bytes changed after provider return"),
        ("visual_run_manifest", "visual evidence manifest changed after provider return"),
        ("manifest_bytes_sha256", "visual evidence manifest bytes changed after provider return"),
        (
            "drawing_sha256_before_dispatch",
            "DARA drawing pre-dispatch identity changed after provider return",
        ),
    ):
        if authoritative[field] != post_provider[field]:
            _fail(message)

    selected = auth_candidate.get("current_candidate_revision_sha256")
    if selected is None or provider_candidate_sha != selected:
        _fail("provider candidate revision does not match current candidate")
    selected = _sha(selected, label="current_candidate_revision_sha256")
    candidate_state_sha = _sha(
        auth_candidate.get("state_sha256"), label="candidate_state_sha256"
    )
    if auth_scope["candidate_revision_sha256"] != selected:
        _fail("visual review scope is not bound to the current R4 candidate")
    if auth_scope["candidate_state_sha256"] != candidate_state_sha:
        _fail("visual review scope is not bound to the current R4 state")
    if post_scope["candidate_revision_sha256"] != post_candidate.get(
        "current_candidate_revision_sha256"
    ):
        _fail("post-provider visual scope is stale against R4 current candidate")
    if post_scope["candidate_state_sha256"] != post_candidate["state_sha256"]:
        _fail("post-provider visual scope is stale against R4 state")

    auth_evidence = auth_validated["evidence"]
    post_evidence = post_validated["evidence"]
    if auth_evidence["records"] != post_evidence["records"]:
        _fail("visual evidence freshness changed after provider return")
    if auth_evidence["identities"] != post_evidence["identities"]:
        _fail("visual evidence identity changed after provider return")
    auth_camera = auth_validated["native_camera"]
    post_camera = post_validated["native_camera"]
    if auth_camera != post_camera:
        _fail("native camera evidence changed after provider return")
    _assert_r5_not_stale(
        authoritative,
        _mapping(
            authoritative["visual_run_manifest"],
            label="authoritative_state.visual_run_manifest",
        ),
    )

    request_binding = _request_binding_facts(
        request_handoff=request_handoff,
        worker_binding=worker_binding,
        authority_context=authority_context,
        worker_context=worker_context,
        task6=owner_task6,
        run_id=auth_scope["run_id"],
        now=now,
    )

    drawing_reference = _mapping(
        authoritative["drawing_reference"], label="authoritative_state.drawing_reference"
    )
    drawing_observation = _mapping(
        authoritative["drawing_observation"],
        label="authoritative_state.drawing_observation",
    )
    visual_manifest = _mapping(
        authoritative["visual_run_manifest"],
        label="authoritative_state.visual_run_manifest",
    )
    drawing_reference_sha = _sha(
        drawing_reference.get("reference_sha256"),
        label="drawing_reference.reference_sha256",
    )
    drawing_artifact_sha = _sha(
        drawing_reference.get("artifact_sha256"),
        label="drawing_reference.artifact_sha256",
    )
    drawing_observation_sha = _sha(
        drawing_observation.get("lookup_sha256"),
        label="drawing_observation.lookup_sha256",
    )
    latest_mutation_sha = _sha(
        visual_manifest.get("latest_mutation_sha256"),
        label="visual_run_manifest.latest_mutation_sha256",
    )
    registry_snapshot_sha = _sha(
        auth_scope.get("registry_snapshot_sha256"),
        label="visual_scope.registry_snapshot_sha256",
    )
    manifest_bytes_sha = _sha(
        authoritative["manifest_bytes_sha256"],
        label="authoritative_state.manifest_bytes_sha256",
    )

    request_payload = {
        "visual_scope": copy.deepcopy(auth_scope),
        "candidate_revision_sha256": selected,
        "candidate_state_sha256": candidate_state_sha,
        "registry_snapshot_sha256": registry_snapshot_sha,
        "drawing_reference_sha256": drawing_reference_sha,
        "drawing_artifact_sha256": drawing_artifact_sha,
        "drawing_observation_sha256": drawing_observation_sha,
        "manifest_bytes_sha256": manifest_bytes_sha,
        "latest_mutation_sha256": latest_mutation_sha,
        "visual_evidence": copy.deepcopy(auth_evidence["identities"]),
        "request_binding": request_binding,
    }
    if auth_camera is not None:
        if auth_camera["plan"]["latest_mutation_sha256"] != latest_mutation_sha:
            _fail("native camera plan is stale at final R5 request sealing")
        request_payload["visual_capture_plan_sha256"] = auth_camera[
            "visual_capture_plan_sha256"
        ]
        request_payload["native_camera_evidence"] = copy.deepcopy(
            auth_camera["identities"]
        )
    try:
        request_sha = canonical_json_sha256(request_payload)
    except Exception:
        _fail("R5_REQUEST_BINDING_INVALID")

    observation_payload = {
        "request_sha256": request_sha,
        "candidate_revision_sha256": provider_candidate_sha,
        "provider_verdict": provider_verdict,
        "regions": copy.deepcopy(regions),
        "task6_thread_id": owner_task6.thread_id,
        "task6_turn_id": owner_task6.turn_id,
    }
    try:
        observation_sha = canonical_json_sha256(observation_payload)
    except Exception:
        _fail("R5_PROVIDER_OBSERVATION_INVALID")

    statuses = [str(region["status"]) for region in regions]
    if "FAIL" in statuses:
        verdict = "FAIL"
    elif any(status in {"SKIP", "NOT_RUN"} for status in statuses):
        verdict = "NEEDS_HUMAN"
    else:
        verdict = "PASS"

    result_payload: dict[str, object] = {
        "schema_version": R5_VISUAL_VERDICT_RESULT_SCHEMA_VERSION,
        "request_sha256": request_sha,
        "observation_sha256": observation_sha,
        "verdict": verdict,
        "candidate_revision_sha256": selected,
        "candidate_state_sha256": candidate_state_sha,
        "registry_snapshot_sha256": registry_snapshot_sha,
        "drawing_reference_sha256": drawing_reference_sha,
        "drawing_observation_sha256": drawing_observation_sha,
        "latest_mutation_sha256": latest_mutation_sha,
        "task6_thread_id": owner_task6.thread_id,
        "task6_turn_id": owner_task6.turn_id,
        "regions": copy.deepcopy(regions),
    }
    try:
        verdict_sha = canonical_json_sha256(result_payload)
    except Exception:
        _fail("R5_VERDICT_RESULT_INVALID")
    result = {
        **result_payload,
        "verdict_id": verdict_sha,
        "verdict_sha256": verdict_sha,
    }
    validated_result = validate_visual_verdict_result(
        result,
        expected_request_sha256=request_sha,
        expected_candidate_revision_sha256=selected,
        expected_candidate_state_sha256=candidate_state_sha,
        expected_latest_mutation_sha256=latest_mutation_sha,
    )

    try:
        consume_task6_result(
            owner_task6,
            run_id=auth_scope["run_id"],
            operation=owner_task6.operation,
            thread_id=owner_task6.thread_id,
            turn_id=owner_task6.turn_id,
        )
    except Exception:
        _fail("Task6 accepted result could not be consumed")
    return validated_result


__all__ = [
    "R5_VISUAL_VERDICT_RESULT_SCHEMA_VERSION",
    "VisualSupervisorAdapterError",
    "finalize_visual_verdict",
    "validate_visual_verdict_result",
]
