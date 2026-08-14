"""Closed offline contracts for read-only AutoCAD-native render evidence."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import math
import re
from pathlib import PurePosixPath

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.visual_contracts import validate_visual_contract


REQUEST_SCHEMA_VERSION = "autocad-native-render-request-1.0"
EVIDENCE_SCHEMA_VERSION = "autocad-native-render-evidence-1.0"
CAMERA_RENDER_SCHEMA_VERSION = "canonical-camera-render-1.0"

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_UTC_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:")
_BBOX_REL_TOL = 1e-6
_BBOX_ABS_TOL = 1e-7

_REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "request_id",
        "run_id",
        "drawing_sha256",
        "latest_mutation_sha256",
        "visual_run_manifest_sha256",
        "layout",
        "artifact_kind",
        "render_options",
        "requested_at",
    }
)
_EVIDENCE_FIELDS = frozenset(
    {
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
    }
)
_LAYOUT_FIELDS = frozenset({"identity", "name"})
_RENDER_OPTION_FIELDS = frozenset(
    {"background", "dpi", "fit_to_paper", "paper_size", "plot_style"}
)
_CAMERA_RENDER_FIELDS = frozenset(
    {
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
)
_CAPTURE_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "receipt_id",
        "capture_id",
        "run_id",
        "scope_id",
        "region_id",
        "view_id",
        "sheet_id",
        "layout_id",
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "latest_mutation_sha256",
        "visual_capture_plan_sha256",
        "capture_class",
        "zoom_mode",
        "requested_wcs_bbox",
        "observed_wcs_bbox",
        "view_center",
        "view_width",
        "view_height",
        "view_direction",
        "ucs",
        "visual_style",
        "artifact_sha256",
        "artifact_width",
        "artifact_height",
        "captured_at_utc",
        "transient_state_restored",
    }
)
_PNG_ARTIFACT_FIELDS = frozenset({"relative_path", "sha256", "width", "height"})
_PDF_ARTIFACT_FIELDS = frozenset({"relative_path", "sha256", "page_count"})
_FORBIDDEN_FIELDS = frozenset(
    {
        "approval",
        "approved",
        "pass",
        "passed",
        "publication",
        "published",
        "repair",
        "verdict",
    }
)


class AutoCADRenderEvidenceError(ValueError):
    """Raised when a render request or evidence result is not closed and safe."""


def _error(message: str) -> None:
    raise AutoCADRenderEvidenceError(message)


def _mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _error(f"{context} must be a JSON object")
    if any(not isinstance(key, str) for key in value):
        _error(f"{context} keys must be strings")
    return dict(value)


def _reject_forbidden_fields(value: object, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                _error(f"{path} keys must be strings")
            if key.casefold() in _FORBIDDEN_FIELDS:
                _error(f"{path}.{key} is not allowed")
            _reject_forbidden_fields(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_fields(nested, f"{path}[{index}]")


def _closed_fields(value: object, expected: frozenset[str], context: str) -> dict[str, object]:
    result = _mapping(value, context)
    unknown = set(result) - expected
    missing = expected - set(result)
    if unknown:
        _error(f"{context} contains unknown field(s): {sorted(unknown)}")
    if missing:
        _error(f"{context} is missing field(s): {sorted(missing)}")
    return result


def _string(value: object, context: str, *, identifier: bool = False) -> str:
    if type(value) is not str or not value or len(value) > 512:
        _error(f"{context} must be a non-empty string")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        _error(f"{context} contains a control character")
    if identifier and not _ID_PATTERN.fullmatch(value):
        _error(f"{context} is not a safe identity")
    return value


def _nullable_identifier(value: object, context: str) -> str | None:
    if value is None:
        return None
    return _string(value, context, identifier=True)


def _hash(value: object, context: str) -> str:
    if type(value) is not str or not _HASH_PATTERN.fullmatch(value):
        _error(f"{context} must be a lowercase 64-character SHA-256")
    return value


def _timestamp(value: object, context: str) -> str:
    if type(value) is not str or not _UTC_TIMESTAMP_PATTERN.fullmatch(value):
        _error(f"{context} must be an ISO-8601 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AutoCADRenderEvidenceError(f"{context} is not a valid timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        _error(f"{context} must be UTC")
    return value


def _strict_int(value: object, context: str, *, maximum: int) -> int:
    if type(value) is not int or not 0 < value <= maximum:
        _error(f"{context} must be an integer from 1 through {maximum}")
    return value


def _finite_number(value: object, context: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _error(f"{context} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        _error(f"{context} must be finite")
    if positive and number <= 0.0:
        _error(f"{context} must be positive")
    return number


def _point(value: object, context: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 2:
        _error(f"{context} must contain exactly two numbers")
    return [
        _finite_number(value[0], f"{context}[0]"),
        _finite_number(value[1], f"{context}[1]"),
    ]


def _bbox(value: object, context: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 4:
        _error(f"{context} must be a four-number WCS bbox")
    result = [_finite_number(item, f"{context}[{index}]") for index, item in enumerate(value)]
    if result[2] <= result[0] or result[3] <= result[1]:
        _error(f"{context} must be a non-degenerate [xmin, ymin, xmax, ymax] bbox")
    return result


def _bbox_matches(left: list[float], right: list[float]) -> bool:
    return all(
        math.isclose(a, b, rel_tol=_BBOX_REL_TOL, abs_tol=_BBOX_ABS_TOL)
        for a, b in zip(left, right, strict=True)
    )


def _layout(value: object) -> dict[str, object]:
    result = _closed_fields(value, _LAYOUT_FIELDS, "layout")
    _string(result["identity"], "layout.identity", identifier=True)
    _string(result["name"], "layout.name")
    return result


def _camera_context(value: object) -> dict[str, object]:
    result = _closed_fields(value, _CAMERA_RENDER_FIELDS, "render_options.camera")
    if result["schema_version"] != CAMERA_RENDER_SCHEMA_VERSION:
        _error("render_options.camera.schema_version is unsupported")
    for field in ("capture_id", "scope_id", "view_id", "sheet_id", "layout_id"):
        _string(result[field], f"render_options.camera.{field}", identifier=True)
    parent_region_id = _nullable_identifier(
        result["parent_region_id"], "render_options.camera.parent_region_id"
    )
    region_id = _nullable_identifier(result["region_id"], "render_options.camera.region_id")
    for field in (
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "visual_capture_plan_sha256",
    ):
        _hash(result[field], f"render_options.camera.{field}")
    capture_class = result["capture_class"]
    if capture_class not in {"GLOBAL", "REGION", "DETAIL"}:
        _error("render_options.camera.capture_class is invalid")
    zoom_mode = result["zoom_mode"]
    if zoom_mode not in {"EXTENTS", "WINDOW"}:
        _error("render_options.camera.zoom_mode is invalid")
    margin = _finite_number(result["margin_ratio"], "render_options.camera.margin_ratio")
    if result["view_direction"] != "TOP":
        _error("render_options.camera.view_direction must be TOP")
    if result["ucs"] != "WORLD":
        _error("render_options.camera.ucs must be WORLD")
    if result["visual_style"] != "2D_WIREFRAME":
        _error("render_options.camera.visual_style must be 2D_WIREFRAME")

    bbox: list[float] | None
    if capture_class == "GLOBAL":
        if zoom_mode != "EXTENTS":
            _error("GLOBAL camera capture requires EXTENTS")
        if result["wcs_bbox"] is not None:
            _error("GLOBAL camera capture requires null wcs_bbox")
        if region_id is not None or parent_region_id is not None:
            _error("GLOBAL camera capture cannot carry region identity")
        if margin != 0.05:
            _error("GLOBAL camera margin_ratio must be 0.05")
        bbox = None
    else:
        if zoom_mode != "WINDOW":
            _error(f"{capture_class} camera capture requires WINDOW")
        bbox = _bbox(result["wcs_bbox"], "render_options.camera.wcs_bbox")
        if region_id is None:
            _error(f"{capture_class} camera capture requires region_id")
        if capture_class == "REGION":
            if parent_region_id is not None:
                _error("REGION camera capture requires null parent_region_id")
            if margin != 0.10:
                _error("REGION camera margin_ratio must be 0.10")
        else:
            if parent_region_id is None or parent_region_id != region_id:
                _error("DETAIL camera capture requires its accepted parent region identity")
            if margin != 0.05:
                _error("DETAIL camera margin_ratio must be 0.05")

    result["parent_region_id"] = parent_region_id
    result["region_id"] = region_id
    result["wcs_bbox"] = bbox
    result["margin_ratio"] = margin
    return result


def _render_options(value: object) -> dict[str, object]:
    raw = _mapping(value, "render_options")
    expected = _RENDER_OPTION_FIELDS | ({"camera"} if "camera" in raw else set())
    result = _closed_fields(raw, frozenset(expected), "render_options")
    if result["background"] not in {"black", "white"}:
        _error("render_options.background must be black or white")
    _strict_int(result["dpi"], "render_options.dpi", maximum=2400)
    if type(result["fit_to_paper"]) is not bool:
        _error("render_options.fit_to_paper must be a boolean")
    _string(result["paper_size"], "render_options.paper_size")
    _string(result["plot_style"], "render_options.plot_style")
    if "camera" in result:
        result["camera"] = _camera_context(result["camera"])
        if not (
            result["background"] == "white"
            and result["dpi"] == 300
            and result["fit_to_paper"] is True
            and result["paper_size"] == "A4"
            and result["plot_style"] == "monochrome.ctb"
        ):
            _error("canonical camera render must use the existing safe native-render policy")
    return result


def _artifact_path(value: object, artifact_kind: str) -> str:
    path = _string(value, "artifact.relative_path")
    if (
        path.startswith(("/", "\\"))
        or _DRIVE_PATH_PATTERN.match(path)
        or "\\" in path
        or "//" in path
        or "\x00" in path
    ):
        _error("artifact.relative_path must use a safe relative POSIX path")
    parts = PurePosixPath(path).parts
    if not parts or any(part in {".", ".."} for part in parts):
        _error("artifact.relative_path must not contain traversal")
    expected_suffix = f".{artifact_kind.casefold()}"
    if not path.endswith(expected_suffix):
        _error(f"artifact.relative_path must end with {expected_suffix}")
    return path


def _artifact(value: object, artifact_kind: str) -> dict[str, object]:
    expected = _PNG_ARTIFACT_FIELDS if artifact_kind == "PNG" else _PDF_ARTIFACT_FIELDS
    result = _closed_fields(value, expected, "artifact")
    _artifact_path(result["relative_path"], artifact_kind)
    _hash(result["sha256"], "artifact.sha256")
    if artifact_kind == "PNG":
        _strict_int(result["width"], "artifact.width", maximum=100_000)
        _strict_int(result["height"], "artifact.height", maximum=100_000)
        if result["width"] * result["height"] > 100_000_000:
            _error("PNG dimensions exceed the maximum pixel count")
    else:
        _strict_int(result["page_count"], "artifact.page_count", maximum=100_000)
    return result


def _warnings(value: object) -> list[str]:
    if type(value) is not list:
        _error("warnings must be a JSON list")
    for index, warning in enumerate(value):
        _string(warning, f"warnings[{index}]")
    return value


def _validate_identity_fields(result: Mapping[str, object], context: str) -> None:
    _string(result["request_id"], f"{context}.request_id", identifier=True)
    _string(result["run_id"], f"{context}.run_id", identifier=True)
    _hash(result["drawing_sha256"], f"{context}.drawing_sha256")
    _hash(result["latest_mutation_sha256"], f"{context}.latest_mutation_sha256")
    _hash(result["visual_run_manifest_sha256"], f"{context}.visual_run_manifest_sha256")


def _capture_receipt(
    value: object,
    *,
    evidence: Mapping[str, object],
    camera: Mapping[str, object],
) -> dict[str, object]:
    result = _closed_fields(value, _CAPTURE_RECEIPT_FIELDS, "visual_capture_receipt")
    if result["schema_version"] != "visual-capture-receipt-1.0":
        _error("visual_capture_receipt.schema_version is unsupported")
    _string(result["receipt_id"], "visual_capture_receipt.receipt_id", identifier=True)
    for field in ("capture_id", "run_id", "scope_id", "view_id", "sheet_id", "layout_id"):
        _string(result[field], f"visual_capture_receipt.{field}", identifier=True)
    region_id = _nullable_identifier(result["region_id"], "visual_capture_receipt.region_id")
    for field in (
        "candidate_revision_sha256",
        "candidate_state_sha256",
        "latest_mutation_sha256",
        "visual_capture_plan_sha256",
        "artifact_sha256",
    ):
        _hash(result[field], f"visual_capture_receipt.{field}")
    if result["capture_class"] not in {"GLOBAL", "REGION", "DETAIL"}:
        _error("visual_capture_receipt.capture_class is invalid")
    if result["zoom_mode"] not in {"EXTENTS", "WINDOW"}:
        _error("visual_capture_receipt.zoom_mode is invalid")
    if result["view_direction"] != "TOP":
        _error("visual_capture_receipt.view_direction must be TOP")
    if result["ucs"] != "WORLD":
        _error("visual_capture_receipt.ucs must be WORLD")
    if result["visual_style"] != "2D_WIREFRAME":
        _error("visual_capture_receipt.visual_style must be 2D_WIREFRAME")
    center = _point(result["view_center"], "visual_capture_receipt.view_center")
    width = _finite_number(
        result["view_width"], "visual_capture_receipt.view_width", positive=True
    )
    height = _finite_number(
        result["view_height"], "visual_capture_receipt.view_height", positive=True
    )
    _strict_int(result["artifact_width"], "visual_capture_receipt.artifact_width", maximum=100_000)
    _strict_int(result["artifact_height"], "visual_capture_receipt.artifact_height", maximum=100_000)
    _timestamp(result["captured_at_utc"], "visual_capture_receipt.captured_at_utc")
    if result["transient_state_restored"] is not True:
        _error("visual_capture_receipt.transient_state_restored must be true")

    comparisons = {
        "capture_id": camera["capture_id"],
        "scope_id": camera["scope_id"],
        "region_id": camera["region_id"],
        "view_id": camera["view_id"],
        "sheet_id": camera["sheet_id"],
        "layout_id": camera["layout_id"],
        "candidate_revision_sha256": camera["candidate_revision_sha256"],
        "candidate_state_sha256": camera["candidate_state_sha256"],
        "visual_capture_plan_sha256": camera["visual_capture_plan_sha256"],
        "capture_class": camera["capture_class"],
        "zoom_mode": camera["zoom_mode"],
        "view_direction": camera["view_direction"],
        "ucs": camera["ucs"],
        "visual_style": camera["visual_style"],
        "run_id": evidence["run_id"],
        "latest_mutation_sha256": evidence["latest_mutation_sha256"],
        "captured_at_utc": evidence["capture_timestamp"],
    }
    for field, expected in comparisons.items():
        if result[field] != expected:
            _error(f"visual_capture_receipt.{field} does not match the camera request")

    artifact = evidence["artifact"]
    if not isinstance(artifact, Mapping):
        _error("evidence.artifact is invalid")
    if result["artifact_sha256"] != artifact["sha256"]:
        _error("visual_capture_receipt artifact SHA does not match render artifact")
    if result["artifact_width"] != artifact["width"]:
        _error("visual_capture_receipt artifact width does not match render artifact")
    if result["artifact_height"] != artifact["height"]:
        _error("visual_capture_receipt artifact height does not match render artifact")

    camera_bbox = camera["wcs_bbox"]
    if camera["capture_class"] == "GLOBAL":
        if result["requested_wcs_bbox"] is not None or result["observed_wcs_bbox"] is not None:
            _error("GLOBAL visual_capture_receipt bbox values must be null")
    else:
        requested = _bbox(
            result["requested_wcs_bbox"], "visual_capture_receipt.requested_wcs_bbox"
        )
        observed = _bbox(
            result["observed_wcs_bbox"], "visual_capture_receipt.observed_wcs_bbox"
        )
        if not isinstance(camera_bbox, list) or not _bbox_matches(
            requested, [float(value) for value in camera_bbox]
        ):
            _error("visual_capture_receipt requested bbox does not match camera request")
        if not _bbox_matches(observed, requested):
            _error("visual_capture_receipt observed bbox is outside camera tolerance")
        min_x, min_y, max_x, max_y = requested
        expected_center = [(min_x + max_x) / 2.0, (min_y + max_y) / 2.0]
        if not all(
            math.isclose(
                actual,
                expected,
                rel_tol=_BBOX_REL_TOL,
                abs_tol=_BBOX_ABS_TOL,
            )
            for actual, expected in zip(center, expected_center, strict=True)
        ):
            _error("visual_capture_receipt view_center does not match camera bbox")
        margin = float(camera["margin_ratio"])
        expected_width = (max_x - min_x) * (1.0 + 2.0 * margin)
        expected_height = (max_y - min_y) * (1.0 + 2.0 * margin)
        if not math.isclose(
            width, expected_width, rel_tol=_BBOX_REL_TOL, abs_tol=_BBOX_ABS_TOL
        ):
            _error("visual_capture_receipt view_width does not match camera margin")
        if not math.isclose(
            height, expected_height, rel_tol=_BBOX_REL_TOL, abs_tol=_BBOX_ABS_TOL
        ):
            _error("visual_capture_receipt view_height does not match camera margin")

    result["region_id"] = region_id
    result["view_center"] = center
    result["view_width"] = width
    result["view_height"] = height
    return result


def validate_render_request(payload: object) -> dict[str, object]:
    """Validate and copy a closed native-render request."""
    _reject_forbidden_fields(payload)
    result = _closed_fields(payload, _REQUEST_FIELDS, "request")
    if result["schema_version"] != REQUEST_SCHEMA_VERSION:
        _error("request.schema_version is unsupported")
    _validate_identity_fields(result, "request")
    layout = _layout(result["layout"])
    artifact_kind = result["artifact_kind"]
    if artifact_kind not in {"PNG", "PDF"}:
        _error("request.artifact_kind must be PNG or PDF")
    options = _render_options(result["render_options"])
    if "camera" in options and artifact_kind != "PNG":
        _error("canonical camera native render is PNG-only")
    _timestamp(result["requested_at"], "request.requested_at")
    result["layout"] = layout
    result["render_options"] = options
    return deepcopy(result)


def build_render_evidence_request(
    *,
    request_id: str,
    run_id: str,
    drawing_sha256: str,
    latest_mutation_sha256: str,
    visual_run_manifest_sha256: str,
    layout: Mapping[str, object],
    artifact_kind: str,
    render_options: Mapping[str, object],
    requested_at: str,
) -> dict[str, object]:
    """Build a deterministic request and validate it before returning it."""
    return validate_render_request(
        {
            "schema_version": REQUEST_SCHEMA_VERSION,
            "request_id": request_id,
            "run_id": run_id,
            "drawing_sha256": drawing_sha256,
            "latest_mutation_sha256": latest_mutation_sha256,
            "visual_run_manifest_sha256": visual_run_manifest_sha256,
            "layout": dict(layout),
            "artifact_kind": artifact_kind,
            "render_options": dict(render_options),
            "requested_at": requested_at,
        }
    )


def build_canonical_camera_render_evidence_request(
    *,
    request_id: str,
    drawing_sha256: str,
    visual_run_manifest_sha256: str,
    layout: Mapping[str, object],
    artifact_kind: str,
    render_options: Mapping[str, object],
    requested_at: str,
    server_scope: Mapping[str, object],
    visual_capture_plan: Mapping[str, object],
    capture_id: str,
) -> dict[str, object]:
    """Derive one native-render camera request from server-owned R5 scope and plan."""
    if artifact_kind != "PNG":
        _error("canonical camera native render is PNG-only")
    if "camera" in render_options:
        _error("render_options.camera must be server-derived")
    try:
        plan = validate_visual_contract(
            visual_capture_plan,
            contract="visual_capture_plan",
            server_scope=server_scope,
        )
    except Exception as exc:
        raise AutoCADRenderEvidenceError(
            "visual capture plan does not match the server-owned scope"
        ) from exc
    selected_id = _string(capture_id, "capture_id", identifier=True)
    captures = plan.get("captures")
    if not isinstance(captures, list):
        _error("visual capture plan captures are invalid")
    matches = [
        capture
        for capture in captures
        if isinstance(capture, Mapping) and capture.get("capture_id") == selected_id
    ]
    if len(matches) != 1:
        _error("capture_id does not identify exactly one server-owned plan capture")
    capture = dict(matches[0])
    normalized_layout = _layout(layout)
    if normalized_layout["identity"] != capture["layout_id"]:
        _error("layout identity does not match the selected camera capture")
    try:
        plan_sha = canonical_json_sha256(plan)
    except Exception as exc:
        raise AutoCADRenderEvidenceError(
            "visual capture plan is not canonicalizable"
        ) from exc
    camera = {
        "schema_version": CAMERA_RENDER_SCHEMA_VERSION,
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
        "wcs_bbox": deepcopy(capture["wcs_bbox"]),
        "margin_ratio": capture["margin_ratio"],
        "view_direction": capture["view_direction"],
        "ucs": capture["ucs"],
        "visual_style": capture["visual_style"],
    }
    options = dict(render_options)
    options["camera"] = camera
    return build_render_evidence_request(
        request_id=request_id,
        run_id=str(plan["run_id"]),
        drawing_sha256=drawing_sha256,
        latest_mutation_sha256=str(plan["latest_mutation_sha256"]),
        visual_run_manifest_sha256=visual_run_manifest_sha256,
        layout=normalized_layout,
        artifact_kind=artifact_kind,
        render_options=options,
        requested_at=requested_at,
    )


def validate_render_evidence(
    payload: object,
    request: object | None = None,
) -> dict[str, object]:
    """Validate and copy closed read-only native-render evidence."""
    _reject_forbidden_fields(payload)
    raw = _mapping(payload, "evidence")
    raw_options = raw.get("render_options")
    has_camera = isinstance(raw_options, Mapping) and "camera" in raw_options
    expected_fields = _EVIDENCE_FIELDS | (
        {"visual_capture_receipt"} if has_camera else set()
    )
    result = _closed_fields(raw, frozenset(expected_fields), "evidence")
    if result["schema_version"] != EVIDENCE_SCHEMA_VERSION:
        _error("evidence.schema_version is unsupported")
    _validate_identity_fields(result, "evidence")
    result["layout"] = _layout(result["layout"])
    artifact_kind = result["artifact_kind"]
    if artifact_kind not in {"PNG", "PDF"}:
        _error("evidence.artifact_kind must be PNG or PDF")
    result["render_options"] = _render_options(result["render_options"])
    camera = result["render_options"].get("camera")
    if camera is not None and artifact_kind != "PNG":
        _error("canonical camera native render is PNG-only")
    if result["renderer"] != "AUTOCAD_NATIVE":
        _error("evidence.renderer must be AUTOCAD_NATIVE")
    result["artifact"] = _artifact(result["artifact"], artifact_kind)
    _timestamp(result["capture_timestamp"], "evidence.capture_timestamp")
    if type(result["changed"]) is not bool or result["changed"] is not False:
        _error("evidence.changed must be false")
    for field in ("dbmod_before", "dbmod_after"):
        if type(result[field]) is not int or result[field] < 0:
            _error(f"evidence.{field} must be a non-negative integer")
    if result["dbmod_before"] != result["dbmod_after"]:
        _error("evidence DBMOD values must be equal")
    result["warnings"] = _warnings(result["warnings"])
    if camera is not None:
        result["visual_capture_receipt"] = _capture_receipt(
            result["visual_capture_receipt"],
            evidence=result,
            camera=camera,
        )

    if request is not None:
        expected = validate_render_request(request)
        for field in (
            "request_id",
            "run_id",
            "drawing_sha256",
            "latest_mutation_sha256",
            "visual_run_manifest_sha256",
            "layout",
            "artifact_kind",
            "render_options",
        ):
            if result[field] != expected[field]:
                _error(f"evidence.{field} does not match request")
        expected_camera = expected["render_options"].get("camera")
        if expected_camera is None and "visual_capture_receipt" in result:
            _error("legacy render request cannot accept a camera receipt")
        if expected_camera is not None and "visual_capture_receipt" not in result:
            _error("camera render evidence is missing visual_capture_receipt")
    return deepcopy(result)


__all__ = [
    "AutoCADRenderEvidenceError",
    "CAMERA_RENDER_SCHEMA_VERSION",
    "EVIDENCE_SCHEMA_VERSION",
    "REQUEST_SCHEMA_VERSION",
    "build_canonical_camera_render_evidence_request",
    "build_render_evidence_request",
    "validate_render_evidence",
    "validate_render_request",
]
