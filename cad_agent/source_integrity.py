"""Closed, deterministic R1C numeric and evidence-contract helpers.

This module validates candidate in-memory records only.  A normalized custody
record is not evidence that source bytes were inspected or are currently fresh,
and an evaluation record does not confer approval, verdict, or publication
authority.
"""

from __future__ import annotations

import copy
import datetime as _datetime
import decimal
import re
from collections.abc import Mapping

from cad_agent.drawing_contracts import canonical_json_sha256


R1C_NUMERIC_POLICY_VERSION = "r1c-numeric-v1"
R1C_TOLERANCE_POLICY_VERSION = "r1c-tolerance-v1"
R1C_EXPIRY_POLICY_VERSION = "r1c-expiry-v1"
SOURCE_CUSTODY_SCHEMA_VERSION = "source-custody-1.0"
SOURCE_FUSION_EVALUATION_SCHEMA_VERSION = "source-fusion-evaluation-1.0"


class SourceIntegrityError(ValueError):
    """Raised when a closed R1C contract is malformed or unsupported."""


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UTC_EVALUATION_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$"
)
_RELATIVE_PATH_RE = re.compile(r"^[^\\/][^\\]*$")
_REASON_RE = re.compile(r"^[A-Z][A-Z0-9_:-]{0,63}$")


class _QuantityPolicy:
    __slots__ = ("canonical_unit", "quantum", "minimum", "maximum", "units")

    def __init__(
        self,
        *,
        canonical_unit: str,
        quantum: str,
        minimum: str,
        maximum: str,
        units: Mapping[str, str | tuple[str, str]],
    ) -> None:
        self.canonical_unit = canonical_unit
        self.quantum = decimal.Decimal(quantum)
        self.minimum = decimal.Decimal(minimum)
        self.maximum = decimal.Decimal(maximum)
        self.units = {
            unit: (
                (decimal.Decimal(factor[0]), decimal.Decimal(factor[1]))
                if isinstance(factor, tuple)
                else (decimal.Decimal(factor), decimal.Decimal("1"))
            )
            for unit, factor in units.items()
        }


_PHYSICAL_LENGTH_POLICY = _QuantityPolicy(
    canonical_unit="mm",
    quantum="0.001",
    minimum="-1000000000",
    maximum="1000000000",
    units={"mm": "1", "cm": "10", "m": "1000", "in": "25.4"},
)
_PDF_COORDINATE_POLICY = _QuantityPolicy(
    canonical_unit="pt",
    quantum="0.001",
    minimum="-1000000000",
    maximum="1000000000",
    units={
        "pt": ("1", "1"),
        "in": ("72", "1"),
        "mm": ("72", "25.4"),
        "cm": ("720", "25.4"),
        "m": ("72000", "25.4"),
    },
)
_PIXEL_POLICY = _QuantityPolicy(
    canonical_unit="px",
    quantum="1",
    minimum="0",
    maximum="2147483647",
    units={"px": "1"},
)
_ANGLE_POLICY = _QuantityPolicy(
    canonical_unit="degree",
    quantum="0.000001",
    minimum="-360000",
    maximum="360000",
    units={"degree": "1", "deg": "1"},
)
_CONFIDENCE_POLICY = _QuantityPolicy(
    canonical_unit="unitless",
    quantum="0.000001",
    minimum="0",
    maximum="1",
    units={"unitless": "1"},
)
_DPI_POLICY = _QuantityPolicy(
    canonical_unit="dpi",
    quantum="0.001",
    minimum="0.001",
    maximum="1000000",
    units={"dpi": "1"},
)
_MATRIX_POLICY = _QuantityPolicy(
    canonical_unit="unitless",
    quantum="0.000000001",
    minimum="-1000000000",
    maximum="1000000000",
    units={"unitless": "1"},
)
_SCALE_POLICY = _QuantityPolicy(
    canonical_unit="ratio",
    quantum="0.000000001",
    minimum="-1000000000",
    maximum="1000000000",
    units={"ratio": "1"},
)

_QUANTITY_POLICIES = {
    "physical_length": _PHYSICAL_LENGTH_POLICY,
    "measurement": _PHYSICAL_LENGTH_POLICY,
    "tolerance": _PHYSICAL_LENGTH_POLICY,
    "pdf_coordinate": _PDF_COORDINATE_POLICY,
    "pdf_box_length": _PDF_COORDINATE_POLICY,
    "pixel_coordinate": _PIXEL_POLICY,
    "pixel_dimension": _PIXEL_POLICY,
    "angle": _ANGLE_POLICY,
    "rotation": _ANGLE_POLICY,
    "confidence": _CONFIDENCE_POLICY,
    "quality": _CONFIDENCE_POLICY,
    "dpi": _DPI_POLICY,
    "resolution": _DPI_POLICY,
    "render_matrix": _MATRIX_POLICY,
    "affine_matrix": _MATRIX_POLICY,
    "scale": _SCALE_POLICY,
    "calibration_ratio": _SCALE_POLICY,
}


def _fail(path: str, message: str) -> None:
    raise SourceIntegrityError(f"{path} {message}")


def _closed_mapping(
    value: object, *, required: set[str], path: str
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(path, "must be an object")
    keys = set(value)
    if any(not isinstance(key, str) for key in keys):
        _fail(path, "contains a non-string field")
    missing = sorted(required - keys)
    unsupported = sorted(keys - required)
    if missing:
        _fail(path, f"is missing required properties: {', '.join(missing)}")
    if unsupported:
        _fail(path, f"contains unsupported properties: {', '.join(unsupported)}")
    return value


def _identifier(value: object, *, path: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        _fail(path, "must be a stable identifier")
    return value


def _hash(value: object, *, path: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        _fail(path, "must be lowercase hexadecimal SHA-256")
    return value


def _optional_hash(value: object, *, path: str) -> str | None:
    if value is None:
        return None
    return _hash(value, path=path)


def _identifier_list(value: object, *, path: str) -> list[str]:
    if not isinstance(value, list):
        _fail(path, "must be an array")
    normalized = [_identifier(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    return sorted(set(normalized))


def _hash_list(value: object, *, path: str) -> list[str]:
    if not isinstance(value, list):
        _fail(path, "must be an array of hashes")
    normalized = [_hash(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    return sorted(set(normalized))


def _decimal(value: object, *, path: str) -> decimal.Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, decimal.Decimal)):
        _fail(path, "must be a finite numeric value")
    try:
        parsed = decimal.Decimal(str(value))
    except (decimal.InvalidOperation, ValueError) as exc:
        raise SourceIntegrityError(f"{path} must be a finite numeric value") from exc
    if not parsed.is_finite():
        _fail(path, "must be a finite numeric value")
    return parsed


def _fixed_decimal(value: decimal.Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text


def canonicalize_r1c_quantity(
    value: object, *, quantity: str, unit: str
) -> dict[str, str]:
    """Return one quantity in the closed R1C canonical numeric form."""
    policy = _QUANTITY_POLICIES.get(quantity)
    if policy is None:
        _fail("quantity", "is unsupported")
    if not isinstance(unit, str) or unit not in policy.units:
        _fail("unit", f"is unsupported for {quantity}")
    parsed = _decimal(value, path="value")
    numerator, denominator = policy.units[unit]
    with decimal.localcontext() as context:
        context.prec = max(64, len(parsed.as_tuple().digits) + 32)
        converted = parsed * numerator
        if denominator != 1:
            converted /= denominator
        if converted < policy.minimum or converted > policy.maximum:
            _fail("value", "is outside the closed range")
        if policy is _PIXEL_POLICY and converted != converted.to_integral_value():
            _fail("value", "must be an integer for pixel quantities")
        try:
            quantized = converted.quantize(
                policy.quantum, rounding=decimal.ROUND_HALF_EVEN
            )
        except decimal.InvalidOperation as exc:
            raise SourceIntegrityError("value cannot be canonically quantized") from exc
        if quantized < policy.minimum or quantized > policy.maximum:
            _fail("value", "is outside the closed range after quantization")
    if quantized == 0:
        quantized = abs(quantized)
    return {
        "policy_version": R1C_NUMERIC_POLICY_VERSION,
        "quantity": quantity,
        "unit": policy.canonical_unit,
        "value": _fixed_decimal(quantized),
    }


def r1c_quantity_within_tolerance(
    left: object,
    *,
    left_unit: str,
    right: object,
    right_unit: str,
    tolerance: object,
    tolerance_unit: str,
    quantity: str,
    tolerance_policy_version: str,
) -> bool:
    """Classify a numeric difference without merging the source identities."""
    if tolerance_policy_version != R1C_TOLERANCE_POLICY_VERSION:
        _fail("tolerance_policy_version", "must equal r1c-tolerance-v1")
    left_normalized = canonicalize_r1c_quantity(
        left, quantity=quantity, unit=left_unit
    )
    right_normalized = canonicalize_r1c_quantity(
        right, quantity=quantity, unit=right_unit
    )
    tolerance_normalized = canonicalize_r1c_quantity(
        tolerance, quantity=quantity, unit=tolerance_unit
    )
    tolerance_value = decimal.Decimal(tolerance_normalized["value"])
    if tolerance_value < 0:
        _fail("tolerance", "must be non-negative")
    difference = abs(
        decimal.Decimal(left_normalized["value"])
        - decimal.Decimal(right_normalized["value"])
    )
    return difference <= tolerance_value


_CUSTODY_ROOT_FIELDS = {
    "schema_version",
    "bundle_id",
    "run_id",
    "source_bundle_sha256",
    "approved_root_id",
    "approved_root_revision",
    "approved_root_configuration_sha256",
    "identity_scheme",
    "identity_scheme_version",
    "identity_key_revision",
    "numeric_policy_version",
    "status",
    "eligible_count",
    "blocking_count",
    "items",
    "alias_groups",
}
_CUSTODY_ITEM_FIELDS = {
    "source_id",
    "kind",
    "role",
    "relative_path",
    "declared_sha256",
    "observed_sha256",
    "size_bytes",
    "declared_media_type",
    "observed_media_type",
    "media_metadata",
    "page_ids",
    "region_ids",
    "file_object_identity_token",
    "path_binding_sha256",
    "identity_scheme",
    "identity_scheme_version",
    "identity_key_revision",
    "approved_root_revision",
    "alias_group_id",
    "custody_state",
    "blocking_reason_code",
}
_MEDIA_FIELDS = {
    "format",
    "width_px",
    "height_px",
    "mode",
    "dpi_x",
    "dpi_y",
}
_ALIAS_GROUP_FIELDS = {
    "alias_group_id",
    "group_type",
    "source_ids",
    "observed_sha256",
    "file_object_identity_tokens",
    "path_bindings",
}
_CUSTODY_STATES = {
    "VERIFIED",
    "DUPLICATE_BYTES",
    "SAME_FILE_ALIAS",
    "MISSING",
    "PATH_ESCAPE",
    "REPARSE_POINT",
    "FINAL_PATH_OUTSIDE_ROOT",
    "UNSUPPORTED_MEDIA",
    "MEDIA_MISMATCH",
    "HASH_MISMATCH",
    "CHANGED_DURING_READ",
    "IDENTITY_CHANGED",
    "UNREADABLE",
    "RESOURCE_LIMIT",
}
_ELIGIBLE_CUSTODY_STATES = {"VERIFIED", "DUPLICATE_BYTES"}
_CUSTODY_KINDS = {"IMAGE", "PDF", "EXACT_BASE_CAD", "ENGINEER_RECORD"}
_CUSTODY_ROLES = {
    "OVERALL",
    "DETAIL",
    "SECTION",
    "MATERIAL_TABLE",
    "BASE_CAD",
    "MEASUREMENT",
    "DECISION",
}


def _nonnegative_int(value: object, *, path: str, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(path, "must be a non-negative integer")
    if value > 2**63 - 1:
        _fail(path, "is outside the supported integer range")
    return value


def _safe_relative_path(value: object, *, path: str) -> str:
    if not isinstance(value, str) or not value or not _RELATIVE_PATH_RE.fullmatch(value):
        _fail(path, "must be a safe relative path")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        _fail(path, "must be a safe relative path")
    parts = value.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        _fail(path, "must be a safe relative path")
    return value


def _optional_canonical_dpi(value: object, *, path: str) -> str | None:
    if value is None:
        return None
    return canonicalize_r1c_quantity(value, quantity="dpi", unit="dpi")["value"]


def _validate_media_metadata(value: object, *, path: str) -> dict[str, object]:
    media = _closed_mapping(value, required=_MEDIA_FIELDS, path=path)
    format_name = media["format"]
    mode = media["mode"]
    if not isinstance(format_name, str) or not format_name:
        _fail(f"{path}.format", "must be a non-empty string")
    if not isinstance(mode, str) or not mode:
        _fail(f"{path}.mode", "must be a non-empty string")
    return {
        "format": format_name,
        "width_px": _nonnegative_int(media["width_px"], path=f"{path}.width_px"),
        "height_px": _nonnegative_int(media["height_px"], path=f"{path}.height_px"),
        "mode": mode,
        "dpi_x": _optional_canonical_dpi(media["dpi_x"], path=f"{path}.dpi_x"),
        "dpi_y": _optional_canonical_dpi(media["dpi_y"], path=f"{path}.dpi_y"),
    }


def _validate_custody_item(
    value: object, *, index: int, root: Mapping[str, object]
) -> dict[str, object]:
    path = f"items[{index}]"
    item = _closed_mapping(value, required=_CUSTODY_ITEM_FIELDS, path=path)
    state = item["custody_state"]
    if not isinstance(state, str) or state not in _CUSTODY_STATES:
        _fail(f"{path}.custody_state", "has an unsupported value")
    reason = item["blocking_reason_code"]
    if state in _ELIGIBLE_CUSTODY_STATES:
        if reason is not None:
            _fail(f"{path}.blocking_reason_code", "must be null for an eligible item")
    elif not isinstance(reason, str) or not _REASON_RE.fullmatch(reason):
        _fail(f"{path}.blocking_reason_code", "must be a sanitized blocking code")

    identity_scheme = item["identity_scheme"]
    identity_version = item["identity_scheme_version"]
    key_revision = item["identity_key_revision"]
    root_revision = item["approved_root_revision"]
    if identity_scheme != root["identity_scheme"]:
        _fail(f"{path}.identity_scheme", "must match the custody root")
    if identity_version != root["identity_scheme_version"]:
        _fail(f"{path}.identity_scheme_version", "must match the custody root")
    if key_revision != root["identity_key_revision"]:
        _fail(f"{path}.identity_key_revision", "must match the custody root")
    if root_revision != root["approved_root_revision"]:
        _fail(f"{path}.approved_root_revision", "must match the custody root")

    return {
        "source_id": _identifier(item["source_id"], path=f"{path}.source_id"),
        "kind": item["kind"]
        if isinstance(item["kind"], str) and item["kind"] in _CUSTODY_KINDS
        else _fail(f"{path}.kind", "has an unsupported value"),
        "role": item["role"]
        if isinstance(item["role"], str) and item["role"] in _CUSTODY_ROLES
        else _fail(f"{path}.role", "has an unsupported value"),
        "relative_path": _safe_relative_path(
            item["relative_path"], path=f"{path}.relative_path"
        ),
        "declared_sha256": _hash(item["declared_sha256"], path=f"{path}.declared_sha256"),
        "observed_sha256": _optional_hash(
            item["observed_sha256"], path=f"{path}.observed_sha256"
        ),
        "size_bytes": _nonnegative_int(
            item["size_bytes"], path=f"{path}.size_bytes", allow_none=True
        ),
        "declared_media_type": item["declared_media_type"]
        if isinstance(item["declared_media_type"], str)
        and item["declared_media_type"]
        else _fail(f"{path}.declared_media_type", "must be a non-empty string"),
        "observed_media_type": item["observed_media_type"]
        if item["observed_media_type"] is None
        or (isinstance(item["observed_media_type"], str) and item["observed_media_type"])
        else _fail(f"{path}.observed_media_type", "must be null or a non-empty string"),
        "media_metadata": _validate_media_metadata(
            item["media_metadata"], path=f"{path}.media_metadata"
        ),
        "page_ids": _identifier_list(item["page_ids"], path=f"{path}.page_ids"),
        "region_ids": _identifier_list(item["region_ids"], path=f"{path}.region_ids"),
        "file_object_identity_token": _optional_hash(
            item["file_object_identity_token"],
            path=f"{path}.file_object_identity_token",
        ),
        "path_binding_sha256": _optional_hash(
            item["path_binding_sha256"], path=f"{path}.path_binding_sha256"
        ),
        "identity_scheme": identity_scheme
        if identity_scheme == "HMAC-SHA-256"
        else _fail(f"{path}.identity_scheme", "must equal HMAC-SHA-256"),
        "identity_scheme_version": identity_version
        if identity_version == "r1c-file-identity-v1"
        else _fail(
            f"{path}.identity_scheme_version", "must equal r1c-file-identity-v1"
        ),
        "identity_key_revision": _identifier(
            key_revision, path=f"{path}.identity_key_revision"
        ),
        "approved_root_revision": _identifier(
            root_revision, path=f"{path}.approved_root_revision"
        ),
        "alias_group_id": None
        if item["alias_group_id"] is None
        else _identifier(item["alias_group_id"], path=f"{path}.alias_group_id"),
        "custody_state": state,
        "blocking_reason_code": reason,
    }


def _validate_alias_groups(value: object, *, item_ids: set[str]) -> list[dict[str, object]]:
    if not isinstance(value, list):
        _fail("alias_groups", "must be an array")
    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, raw_group in enumerate(value):
        path = f"alias_groups[{index}]"
        group = _closed_mapping(raw_group, required=_ALIAS_GROUP_FIELDS, path=path)
        group_id = _identifier(group["alias_group_id"], path=f"{path}.alias_group_id")
        if group_id in seen_ids:
            _fail("alias_groups", "must contain unique alias_group_id values")
        seen_ids.add(group_id)
        group_type = group["group_type"]
        if group_type not in {"SAME_FILE_ALIAS", "DUPLICATE_BYTES"}:
            _fail(f"{path}.group_type", "has an unsupported value")
        source_ids = _identifier_list(group["source_ids"], path=f"{path}.source_ids")
        if len(source_ids) < 2 or not set(source_ids).issubset(item_ids):
            _fail(f"{path}.source_ids", "must contain at least two custody items")
        observed_sha = _hash(group["observed_sha256"], path=f"{path}.observed_sha256")
        tokens = _hash_list(
            group["file_object_identity_tokens"],
            path=f"{path}.file_object_identity_tokens",
        )
        path_bindings = _hash_list(
            group["path_bindings"], path=f"{path}.path_bindings"
        )
        if len(tokens) != 1 and group_type == "SAME_FILE_ALIAS":
            _fail(f"{path}.file_object_identity_tokens", "must identify one shared object")
        if len(tokens) < 2 and group_type == "DUPLICATE_BYTES":
            _fail(f"{path}.file_object_identity_tokens", "must identify distinct objects")
        normalized.append(
            {
                "alias_group_id": group_id,
                "group_type": group_type,
                "source_ids": source_ids,
                "observed_sha256": observed_sha,
                "file_object_identity_tokens": tokens,
                "path_bindings": path_bindings,
            }
        )
    normalized.sort(key=lambda group: str(group["alias_group_id"]))
    return normalized


def validate_source_custody(payload: object) -> dict[str, object]:
    """Normalize a candidate custody mapping without inspecting source bytes."""
    root = _closed_mapping(payload, required=_CUSTODY_ROOT_FIELDS, path="SourceCustody")
    if root["schema_version"] != SOURCE_CUSTODY_SCHEMA_VERSION:
        _fail("schema_version", "must equal source-custody-1.0")
    if root["identity_scheme"] != "HMAC-SHA-256":
        _fail("identity_scheme", "must equal HMAC-SHA-256")
    if root["identity_scheme_version"] != "r1c-file-identity-v1":
        _fail("identity_scheme_version", "must equal r1c-file-identity-v1")
    if root["numeric_policy_version"] != R1C_NUMERIC_POLICY_VERSION:
        _fail("numeric_policy_version", "must equal r1c-numeric-v1")
    status = root["status"]
    if status not in {"READY", "BLOCKED"}:
        _fail("status", "must be READY or BLOCKED")
    items_value = root["items"]
    if not isinstance(items_value, list) or not items_value or len(items_value) > 10000:
        _fail("items", "must contain between 1 and 10000 entries")
    normalized_items = [
        _validate_custody_item(item, index=index, root=root)
        for index, item in enumerate(items_value)
    ]
    source_ids = [str(item["source_id"]) for item in normalized_items]
    relative_paths = [str(item["relative_path"]) for item in normalized_items]
    if len(set(source_ids)) != len(source_ids):
        _fail("items", "source_id values must be unique")
    if len(set(relative_paths)) != len(relative_paths):
        _fail("items", "relative_path values must be unique")
    normalized_items.sort(key=lambda item: str(item["source_id"]))
    alias_groups = _validate_alias_groups(root["alias_groups"], item_ids=set(source_ids))
    group_ids = {str(group["alias_group_id"]) for group in alias_groups}
    items_by_id = {str(item["source_id"]): item for item in normalized_items}
    for item in normalized_items:
        group_id = item["alias_group_id"]
        if group_id is not None and group_id not in group_ids:
            _fail("items.alias_group_id", "must reference an alias group")
        if item["custody_state"] in {"SAME_FILE_ALIAS", "DUPLICATE_BYTES"} and group_id is None:
            _fail(
                "items.alias_group_id",
                "is required for alias or duplicate custody states",
            )

    for group in alias_groups:
        group_id = str(group["alias_group_id"])
        source_id_set = set(group["source_ids"])
        referenced_ids = {
            source_id
            for source_id, item in items_by_id.items()
            if item["alias_group_id"] == group_id
        }
        if referenced_ids != source_id_set:
            _fail(
                f"alias_groups.{group_id}",
                "source_ids and item alias_group_id membership must agree",
            )

        member_items = [items_by_id[source_id] for source_id in group["source_ids"]]
        if any(item["custody_state"] != group["group_type"] for item in member_items):
            _fail(
                f"alias_groups.{group_id}",
                "group_type must match every member custody_state",
            )

        observed_hashes = {item["observed_sha256"] for item in member_items}
        if None in observed_hashes or len(observed_hashes) != 1:
            _fail(
                f"alias_groups.{group_id}",
                "observed_sha256 must match every member",
            )
        if group["observed_sha256"] != next(iter(observed_hashes)):
            _fail(
                f"alias_groups.{group_id}",
                "observed_sha256 does not match its members",
            )

        member_tokens = [item["file_object_identity_token"] for item in member_items]
        member_paths = [item["path_binding_sha256"] for item in member_items]
        if any(token is None for token in member_tokens) or any(
            path_binding is None for path_binding in member_paths
        ):
            _fail(
                f"alias_groups.{group_id}",
                "member object and path identities are required",
            )
        expected_tokens = sorted(set(member_tokens))
        expected_paths = sorted(set(member_paths))
        if group["file_object_identity_tokens"] != expected_tokens:
            _fail(
                f"alias_groups.{group_id}",
                "file_object_identity_tokens do not match its members",
            )
        if group["path_bindings"] != expected_paths:
            _fail(
                f"alias_groups.{group_id}",
                "path_bindings do not match its members",
            )
        if group["group_type"] == "SAME_FILE_ALIAS" and len(expected_tokens) != 1:
            _fail(
                f"alias_groups.{group_id}",
                "SAME_FILE_ALIAS requires one shared object identity",
            )
        if group["group_type"] == "DUPLICATE_BYTES" and (
            len(expected_tokens) < 2 or len(expected_tokens) != len(member_items)
        ):
            _fail(
                f"alias_groups.{group_id}",
                "DUPLICATE_BYTES requires independent object identities",
            )
    eligible_count = sum(
        item["custody_state"] in _ELIGIBLE_CUSTODY_STATES for item in normalized_items
    )
    blocking_count = len(normalized_items) - eligible_count
    if root["eligible_count"] != eligible_count:
        _fail("eligible_count", "does not match custody item states")
    if root["blocking_count"] != blocking_count:
        _fail("blocking_count", "does not match custody item states")
    if status == "READY" and blocking_count != 0:
        _fail("status", "READY requires zero blocking items")
    if status == "BLOCKED" and blocking_count == 0:
        _fail("status", "BLOCKED requires at least one blocking item")

    return {
        "schema_version": SOURCE_CUSTODY_SCHEMA_VERSION,
        "bundle_id": _identifier(root["bundle_id"], path="bundle_id"),
        "run_id": _identifier(root["run_id"], path="run_id"),
        "source_bundle_sha256": _hash(
            root["source_bundle_sha256"], path="source_bundle_sha256"
        ),
        "approved_root_id": _identifier(root["approved_root_id"], path="approved_root_id"),
        "approved_root_revision": _identifier(
            root["approved_root_revision"], path="approved_root_revision"
        ),
        "approved_root_configuration_sha256": _hash(
            root["approved_root_configuration_sha256"],
            path="approved_root_configuration_sha256",
        ),
        "identity_scheme": "HMAC-SHA-256",
        "identity_scheme_version": "r1c-file-identity-v1",
        "identity_key_revision": _identifier(
            root["identity_key_revision"], path="identity_key_revision"
        ),
        "numeric_policy_version": R1C_NUMERIC_POLICY_VERSION,
        "status": status,
        "eligible_count": _nonnegative_int(
            root["eligible_count"], path="eligible_count"
        ),
        "blocking_count": _nonnegative_int(
            root["blocking_count"], path="blocking_count"
        ),
        "items": copy.deepcopy(normalized_items),
        "alias_groups": copy.deepcopy(alias_groups),
    }


def source_custody_sha256(payload: object) -> str:
    """Return the canonical SHA-256 for a validated custody candidate."""
    return canonical_json_sha256(validate_source_custody(payload))


_EVALUATION_FIELDS = {
    "schema_version",
    "run_id",
    "source_fusion_sha256",
    "fusion_input_sha256",
    "evaluation_time_utc",
    "evaluation_time_source",
    "evaluation_time_evidence_sha256",
    "expiry_policy_version",
    "evaluated_reference_hashes",
    "status",
    "blocking_codes",
}
_EVALUATION_STATUSES = {"REUSABLE", "BLOCKED_EXPIRED", "STALE"}


def _evaluation_timestamp(value: object) -> str:
    if not isinstance(value, str) or not _UTC_EVALUATION_RE.fullmatch(value):
        _fail("evaluation_time_utc", "must be RFC 3339 UTC with six fractional digits and Z")
    try:
        _datetime.datetime.fromisoformat(value[:-1])
    except ValueError as exc:
        raise SourceIntegrityError("evaluation_time_utc must be a valid UTC timestamp") from exc
    return value


def validate_source_fusion_evaluation(payload: object) -> dict[str, object]:
    """Normalize injected evaluation evidence without reading an ambient clock."""
    value = _closed_mapping(
        payload, required=_EVALUATION_FIELDS, path="SourceFusionEvaluation"
    )
    if value["schema_version"] != SOURCE_FUSION_EVALUATION_SCHEMA_VERSION:
        _fail("schema_version", "must equal source-fusion-evaluation-1.0")
    if value["expiry_policy_version"] != R1C_EXPIRY_POLICY_VERSION:
        _fail("expiry_policy_version", "must equal r1c-expiry-v1")
    status = value["status"]
    if status not in _EVALUATION_STATUSES:
        _fail("status", "has an unsupported value")
    blocking_codes = _identifier_list(value["blocking_codes"], path="blocking_codes")
    if status == "REUSABLE" and blocking_codes:
        _fail("blocking_codes", "must be empty for REUSABLE")
    if status != "REUSABLE" and not blocking_codes:
        _fail("blocking_codes", "must be non-empty for a blocked evaluation")
    source = value["evaluation_time_source"]
    if not isinstance(source, str) or not _IDENTIFIER_RE.fullmatch(source):
        _fail("evaluation_time_source", "must be a closed server-owned identifier")
    return {
        "schema_version": SOURCE_FUSION_EVALUATION_SCHEMA_VERSION,
        "run_id": _identifier(value["run_id"], path="run_id"),
        "source_fusion_sha256": _hash(
            value["source_fusion_sha256"], path="source_fusion_sha256"
        ),
        "fusion_input_sha256": _hash(
            value["fusion_input_sha256"], path="fusion_input_sha256"
        ),
        "evaluation_time_utc": _evaluation_timestamp(value["evaluation_time_utc"]),
        "evaluation_time_source": source,
        "evaluation_time_evidence_sha256": _hash(
            value["evaluation_time_evidence_sha256"],
            path="evaluation_time_evidence_sha256",
        ),
        "expiry_policy_version": R1C_EXPIRY_POLICY_VERSION,
        "evaluated_reference_hashes": _hash_list(
            value["evaluated_reference_hashes"], path="evaluated_reference_hashes"
        ),
        "status": status,
        "blocking_codes": blocking_codes,
    }


def source_fusion_evaluation_sha256(payload: object) -> str:
    """Return the canonical SHA-256 for injected evaluation evidence."""
    return canonical_json_sha256(validate_source_fusion_evaluation(payload))


__all__ = [
    "R1C_EXPIRY_POLICY_VERSION",
    "R1C_NUMERIC_POLICY_VERSION",
    "R1C_TOLERANCE_POLICY_VERSION",
    "SOURCE_CUSTODY_SCHEMA_VERSION",
    "SOURCE_FUSION_EVALUATION_SCHEMA_VERSION",
    "SourceIntegrityError",
    "canonicalize_r1c_quantity",
    "r1c_quantity_within_tolerance",
    "source_custody_sha256",
    "source_fusion_evaluation_sha256",
    "validate_source_custody",
    "validate_source_fusion_evaluation",
]
