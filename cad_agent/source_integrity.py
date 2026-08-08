"""Closed, deterministic R1C numeric and evidence-contract helpers.

This module validates candidate in-memory records only. A normalized custody
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
    normalized = [
        _identifier(item, path=f"{path}[{index}]")
        for index, item in enumerate(value)
    ]
    return sorted(set(normalized))


def _hash_list(value: object, *, path: str) -> list[str]:
    if not isinstance(value, list):
        _fail(path, "must be an array of hashes")
    normalized = [
        _hash(item, path=f"{path}[{index}]")
        for index, item in enumerate(value)
    ]
    return sorted(set(normalized))


def _decimal(value: object, *, path: str) -> decimal.Decimal:
    if isinstance(value, bool) or not isinstance(
        value, (str, int, float, decimal.Decimal)
    ):
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
    left_value = decimal.Decimal(left_normalized["value"])
    right_value = decimal.Decimal(right_normalized["value"])
    tolerance_value = decimal.Decimal(tolerance_normalized["value"])
    with decimal.localcontext() as context:
        context.prec = max(
            64,
            len(left_value.as_tuple().digits) + 4,
            len(right_value.as_tuple().digits) + 4,
            len(tolerance_value.as_tuple().digits) + 4,
        )
        if tolerance_value < 0:
            _fail("tolerance", "must be non-negative")
        difference = abs(left_value - right_value)
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


def _nonnegative_int(
    value: object, *, path: str, allow_none: bool = False
) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(path, "must be a non-negative integer")
    if value > 2**63 - 1:
        _fail(path, "is outside the supported integer range")
    return value


def _safe_relative_path(value: object, *, path: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or not _RELATIVE_PATH_RE.fullmatch(value)
    ):
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
        "height_px": _nonnegative_int(
            media["height_px"], path=f"{path}.height_px"
        ),
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
            _fail(
                f"{path}.blocking_reason_code",
                "must be null for an eligible item",
            )
    elif not isinstance(reason, str) or not _REASON_RE.fullmatch(reason):
        _fail(
            f"{path}.blocking_reason_code",
            "must be a sanitized blocking code",
        )

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

    declared_sha = _hash(
        item["declared_sha256"], path=f"{path}.declared_sha256"
    )
    observed_sha = _optional_hash(
        item["observed_sha256"], path=f"{path}.observed_sha256"
    )
    declared_media_type = item["declared_media_type"]
    if not isinstance(declared_media_type, str) or not declared_media_type:
        _fail(f"{path}.declared_media_type", "must be a non-empty string")
    observed_media_type = item["observed_media_type"]
    if observed_media_type is not None and (
        not isinstance(observed_media_type, str) or not observed_media_type
    ):
        _fail(
            f"{path}.observed_media_type",
            "must be null or a non-empty string",
        )
    object_token = _optional_hash(
        item["file_object_identity_token"],
        path=f"{path}.file_object_identity_token",
    )
    path_binding = _optional_hash(
        item["path_binding_sha256"], path=f"{path}.path_binding_sha256"
    )

    if state in _ELIGIBLE_CUSTODY_STATES:
        if observed_sha is None:
            _fail(
                f"{path}.observed_sha256",
                "is required for an eligible VERIFIED or DUPLICATE_BYTES item",
            )
        if observed_media_type is None:
            _fail(
                f"{path}.observed_media_type",
                "is required for an eligible VERIFIED or DUPLICATE_BYTES item",
            )
        if object_token is None:
            _fail(
                f"{path}.file_object_identity_token",
                "is required for an eligible VERIFIED or DUPLICATE_BYTES item",
            )
        if path_binding is None:
            _fail(
                f"{path}.path_binding_sha256",
                "is required for an eligible VERIFIED or DUPLICATE_BYTES item",
            )
        if observed_sha != declared_sha:
            _fail(
                f"{path}.custody_state",
                "cannot be eligible when declared and observed SHA-256 differ",
            )
        if observed_media_type != declared_media_type:
            _fail(
                f"{path}.custody_state",
                "cannot be eligible when declared and observed media types differ",
            )

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
        "declared_sha256": declared_sha,
        "observed_sha256": observed_sha,
        "size_bytes": _nonnegative_int(
            item["size_bytes"], path=f"{path}.size_bytes", allow_none=True
        ),
        "declared_media_type": declared_media_type,
        "observed_media_type": observed_media_type,
        "media_metadata": _validate_media_metadata(
            item["media_metadata"], path=f"{path}.media_metadata"
        ),
        "page_ids": _identifier_list(item["page_ids"], path=f"{path}.page_ids"),
        "region_ids": _identifier_list(
            item["region_ids"], path=f"{path}.region_ids"
        ),
        "file_object_identity_token": object_token,
        "path_binding_sha256": path_binding,
        "identity_scheme": identity_scheme
        if identity_scheme == "HMAC-SHA-256"
        else _fail(f"{path}.identity_scheme", "must equal HMAC-SHA-256"),
        "identity_scheme_version": identity_version
        if identity_version == "r1c-file-identity-v1"
        else _fail(
            f"{path}.identity_scheme_version",
            "must equal r1c-file-identity-v1",
        ),
        "identity_key_revision": _identifier(
            key_revision, path=f"{path}.identity_key_revision"
        ),
        "approved_root_revision": _identifier(
            root_revision, path=f"{path}.approved_root_revision"
        ),
        "alias_group_id": None
        if item["alias_group_id"] is None
        else _identifier(
            item["alias_group_id"], path=f"{path}.alias_group_id"
        ),
        "custody_state": state,
        "blocking_reason_code": reason,
    }


def _validate_alias_groups(
    value: object, *, item_ids: set[str]
) -> list[dict[str, object]]:
    if not isinstance(value, list):
        _fail("alias_groups", "must be an array")
    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, raw_group in enumerate(value):
        path = f"alias_groups[{index}]"
        group = _closed_mapping(
            raw_group, required=_ALIAS_GROUP_FIELDS, path=path
        )
        group_id = _identifier(
            group["alias_group_id"], path=f"{path}.alias_group_id"
        )
        if group_id in seen_ids:
            _fail(
                "alias_groups",
                "must contain unique alias_group_id values",
            )
        seen_ids.add(group_id)
        group_type = group["group_type"]
        if group_type not in {"SAME_FILE_ALIAS", "DUPLICATE_BYTES"}:
            _fail(f"{path}.group_type", "has an unsupported value")
        source_ids = _identifier_list(
            group["source_ids"], path=f"{path}.source_ids"
        )
        if len(source_ids) < 2 or not set(source_ids).issubset(item_ids):
            _fail(
                f"{path}.source_ids",
                "must contain at least two custody items",
            )
        observed_sha = _hash(
            group["observed_sha256"], path=f"{path}.observed_sha256"
        )
        tokens = _hash_list(
            group["file_object_identity_tokens"],
            path=f"{path}.file_object_identity_tokens",
        )
        path_bindings = _hash_list(
            group["path_bindings"], path=f"{path}.path_bindings"
        )
        if len(tokens) != 1 and group_type == "SAME_FILE_ALIAS":
            _fail(
                f"{path}.file_object_identity_tokens",
                "must identify one shared object",
            )
        if len(tokens) < 2 and group_type == "DUPLICATE_BYTES":
            _fail(
                f"{path}.file_object_identity_tokens",
                "must identify distinct objects",
            )
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
    root = _closed_mapping(
        payload, required=_CUSTODY_ROOT_FIELDS, path="SourceCustody"
    )
    if root["schema_version"] != SOURCE_CUSTODY_SCHEMA_VERSION:
        _fail("schema_version", "must equal source-custody-1.0")
    if root["identity_scheme"] != "HMAC-SHA-256":
        _fail("identity_scheme", "must equal HMAC-SHA-256")
    if root["identity_scheme_version"] != "r1c-file-identity-v1":
        _fail(
            "identity_scheme_version",
            "must equal r1c-file-identity-v1",
        )
    if root["numeric_policy_version"] != R1C_NUMERIC_POLICY_VERSION:
        _fail("numeric_policy_version", "must equal r1c-numeric-v1")
    status = root["status"]
    if status not in {"READY", "BLOCKED"}:
        _fail("status", "must be READY or BLOCKED")
    items_value = root["items"]
    if (
        not isinstance(items_value, list)
        or not items_value
        or len(items_value) > 10000
    ):
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
    alias_groups = _validate_alias_groups(
        root["alias_groups"], item_ids=set(source_ids)
    )
    group_ids = {str(group["alias_group_id"]) for group in alias_groups}
    items_by_id = {
        str(item["source_id"]): item for item in normalized_items
    }
    for item in normalized_items:
        group_id = item["alias_group_id"]
        if group_id is not None and group_id not in group_ids:
            _fail(
                "items.alias_group_id",
                "must reference an alias group",
            )
        if (
            item["custody_state"] in {"SAME_FILE_ALIAS", "DUPLICATE_BYTES"}
            and group_id is None
        ):
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

        member_items = [
            items_by_id[source_id] for source_id in group["source_ids"]
        ]
        if any(
            item["custody_state"] != group["group_type"]
            for item in member_items
        ):
            _fail(
                f"alias_groups.{group_id}",
                "group_type must match every member custody_state",
            )

        observed_hashes = {
            item["observed_sha256"] for item in member_items
        }
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

        member_tokens = [
            item["file_object_identity_token"] for item in member_items
        ]
        member_paths = [
            item["path_binding_sha256"] for item in member_items
        ]
        if any(token is None for token in member_tokens) or any(
            path_binding is None for path_binding in member_paths
        ):
            _fail(
                f"alias_groups.{group_id}",
                "member object and path identities are required",
            )
        if len(set(member_paths)) != len(member_items):
            _fail(
                f"alias_groups.{group_id}",
                "member path bindings must be distinct",
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
        if (
            group["group_type"] == "SAME_FILE_ALIAS"
            and len(expected_tokens) != 1
        ):
            _fail(
                f"alias_groups.{group_id}",
                "SAME_FILE_ALIAS requires one shared object identity",
            )
        if group["group_type"] == "DUPLICATE_BYTES" and (
            len(expected_tokens) < 2
            or len(expected_tokens) != len(member_items)
        ):
            _fail(
                f"alias_groups.{group_id}",
                "DUPLICATE_BYTES requires independent object identities",
            )

    eligible_count = sum(
        item["custody_state"] in _ELIGIBLE_CUSTODY_STATES
        for item in normalized_items
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
        "approved_root_id": _identifier(
            root["approved_root_id"], path="approved_root_id"
        ),
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
        _fail(
            "evaluation_time_utc",
            "must be RFC 3339 UTC with six fractional digits and Z",
        )
    try:
        _datetime.datetime.fromisoformat(value[:-1])
    except ValueError as exc:
        raise SourceIntegrityError(
            "evaluation_time_utc must be a valid UTC timestamp"
        ) from exc
    return value


def validate_source_fusion_evaluation(payload: object) -> dict[str, object]:
    """Normalize injected evaluation evidence without reading an ambient clock."""
    value = _closed_mapping(
        payload,
        required=_EVALUATION_FIELDS,
        path="SourceFusionEvaluation",
    )
    if value["schema_version"] != SOURCE_FUSION_EVALUATION_SCHEMA_VERSION:
        _fail(
            "schema_version",
            "must equal source-fusion-evaluation-1.0",
        )
    if value["expiry_policy_version"] != R1C_EXPIRY_POLICY_VERSION:
        _fail("expiry_policy_version", "must equal r1c-expiry-v1")
    status = value["status"]
    if status not in _EVALUATION_STATUSES:
        _fail("status", "has an unsupported value")
    blocking_codes = _identifier_list(
        value["blocking_codes"], path="blocking_codes"
    )
    if status == "REUSABLE" and blocking_codes:
        _fail("blocking_codes", "must be empty for REUSABLE")
    if status != "REUSABLE" and not blocking_codes:
        _fail(
            "blocking_codes",
            "must be non-empty for a blocked evaluation",
        )
    source = value["evaluation_time_source"]
    if not isinstance(source, str) or not _IDENTIFIER_RE.fullmatch(source):
        _fail(
            "evaluation_time_source",
            "must be a closed server-owned identifier",
        )
    return {
        "schema_version": SOURCE_FUSION_EVALUATION_SCHEMA_VERSION,
        "run_id": _identifier(value["run_id"], path="run_id"),
        "source_fusion_sha256": _hash(
            value["source_fusion_sha256"], path="source_fusion_sha256"
        ),
        "fusion_input_sha256": _hash(
            value["fusion_input_sha256"], path="fusion_input_sha256"
        ),
        "evaluation_time_utc": _evaluation_timestamp(
            value["evaluation_time_utc"]
        ),
        "evaluation_time_source": source,
        "evaluation_time_evidence_sha256": _hash(
            value["evaluation_time_evidence_sha256"],
            path="evaluation_time_evidence_sha256",
        ),
        "expiry_policy_version": R1C_EXPIRY_POLICY_VERSION,
        "evaluated_reference_hashes": _hash_list(
            value["evaluated_reference_hashes"],
            path="evaluated_reference_hashes",
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


# R1C Task 2 byte-custody implementation. This intentionally returns transient
# byte evidence, not a parser-complete SourceCustody record.
import ctypes
from ctypes import wintypes
import hashlib
import hmac
import ntpath
import struct
import sys

from cad_agent.source_bundle import source_bundle_sha256, validate_source_bundle


_IDENTITY_SCHEME = "HMAC-SHA-256"
_IDENTITY_SCHEME_VERSION = "r1c-file-identity-v1"
_FILE_OBJECT_DOMAIN = b"cad-agent:r1c:file-object:v1"
_PATH_BINDING_DOMAIN = b"cad-agent:r1c:path-binding:v1"
_APPROVED_ROOT_DOMAIN = b"cad-agent:r1c:approved-root:v1"
_POLICY_LIMIT_KEYS = {
    "max_items",
    "max_total_bytes",
    "max_file_bytes",
    "hash_chunk_size",
    "max_final_path_chars",
}
_MAX_FINAL_PATH_CHARS = 32768
_MAX_HASH_CHUNK_SIZE = 16 * 1024 * 1024
_MAX_INT64 = 2**63 - 1
_FILE_ID_INFO_CLASS = 18
_FILE_ID_BYTES = 16


def _frame_parts(*parts: bytes) -> bytes:
    framed = bytearray()
    for part in parts:
        framed.extend(struct.pack(">I", len(part)))
        framed.extend(part)
    return bytes(framed)


def _text_part(value: str) -> bytes:
    return value.encode("utf-8", errors="strict")


def _u64_part(value: object) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
    if value > 2**64 - 1:
        raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
    return struct.pack(">Q", value)


def _file_id_part(value: object) -> bytes:
    if not isinstance(value, bytes) or len(value) != _FILE_ID_BYTES:
        raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
    return value


def _hmac_token(key: bytes, domain: bytes, *parts: bytes) -> str:
    message = _frame_parts(domain, *parts)
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _validate_identity_key(value: object) -> bytes:
    if not isinstance(value, bytes) or not value:
        raise SourceIntegrityError("IDENTITY_KEY_INVALID")
    return value


def _validate_policy_limits(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping) or set(value) != _POLICY_LIMIT_KEYS:
        raise SourceIntegrityError("POLICY_LIMITS_INVALID")
    normalized: dict[str, int] = {}
    for key in sorted(_POLICY_LIMIT_KEYS):
        raw = value[key]
        if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
            raise SourceIntegrityError("POLICY_LIMITS_INVALID")
        if raw > _MAX_INT64:
            raise SourceIntegrityError("POLICY_LIMITS_INVALID")
        normalized[key] = raw
    if normalized["max_items"] > 10000:
        raise SourceIntegrityError("POLICY_LIMITS_INVALID")
    if normalized["hash_chunk_size"] > _MAX_HASH_CHUNK_SIZE:
        raise SourceIntegrityError("POLICY_LIMITS_INVALID")
    if normalized["max_final_path_chars"] > _MAX_FINAL_PATH_CHARS:
        raise SourceIntegrityError("POLICY_LIMITS_INVALID")
    if normalized["max_total_bytes"] < normalized["max_file_bytes"]:
        raise SourceIntegrityError("POLICY_LIMITS_INVALID")
    return normalized


def _normalize_windows_final_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
    path = value
    lowered = path.casefold()
    if lowered.startswith("\\\\?\\unc\\"):
        path = "\\\\" + path[8:]
    elif lowered.startswith("\\\\?\\"):
        path = path[4:]
    normalized = ntpath.normpath(path)
    if not normalized or normalized in {".", ".."}:
        raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
    return ntpath.normcase(normalized)


def _normalize_declared_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or ":" in value or "\\" in value:
        raise SourceIntegrityError("PATH_ESCAPE")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise SourceIntegrityError("PATH_ESCAPE")
    parts = value.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise SourceIntegrityError("PATH_ESCAPE")
    normalized = ntpath.normpath(value.replace("/", "\\"))
    if ntpath.isabs(normalized) or normalized.startswith(".."):
        raise SourceIntegrityError("PATH_ESCAPE")
    return ntpath.normcase(normalized)


def _final_relative_path(
    *, root_final_path: object, source_final_path: object, declared: str
) -> str:
    root = _normalize_windows_final_path(root_final_path)
    source = _normalize_windows_final_path(source_final_path)
    try:
        common = ntpath.commonpath([root, source])
        relative = ntpath.relpath(source, root)
    except ValueError:
        raise SourceIntegrityError("FINAL_PATH_OUTSIDE_ROOT") from None
    if common != root or relative in {".", ".."} or relative.startswith("..\\"):
        raise SourceIntegrityError("FINAL_PATH_OUTSIDE_ROOT")
    normalized_relative = ntpath.normcase(ntpath.normpath(relative))
    if normalized_relative != _normalize_declared_relative_path(declared):
        raise SourceIntegrityError("FINAL_PATH_OUTSIDE_ROOT")
    return normalized_relative.replace("\\", "/")


def _snapshot_identity(snapshot: Mapping[str, object]) -> tuple[int, bytes]:
    volume = snapshot.get("volume_serial")
    file_id = snapshot.get("file_id")
    return (
        int.from_bytes(_u64_part(volume), "big"),
        _file_id_part(file_id),
    )


def _snapshot_size(snapshot: Mapping[str, object]) -> int:
    raw = snapshot.get("size")
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0 or raw > _MAX_INT64:
        raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
    return raw


def _safe_snapshot(
    adapter: object, handle: object, *, max_final_path_chars: int
) -> dict[str, object]:
    try:
        raw = adapter.snapshot(handle, max_final_path_chars=max_final_path_chars)
    except SourceIntegrityError:
        raise
    except Exception:
        raise SourceIntegrityError("EVIDENCE_UNAVAILABLE") from None
    if not isinstance(raw, Mapping):
        raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
    required = {"final_path", "volume_serial", "file_id", "size", "reparse"}
    if set(raw) != required or not isinstance(raw["reparse"], bool):
        raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
    _normalize_windows_final_path(raw["final_path"])
    _snapshot_identity(raw)
    _snapshot_size(raw)
    return dict(raw)


def _object_identity_token(
    *, key: bytes, key_revision: str, snapshot: Mapping[str, object]
) -> str:
    volume, file_id = _snapshot_identity(snapshot)
    return _hmac_token(
        key,
        _FILE_OBJECT_DOMAIN,
        _text_part(_IDENTITY_SCHEME),
        _text_part(_IDENTITY_SCHEME_VERSION),
        _text_part(key_revision),
        _u64_part(volume),
        _file_id_part(file_id),
    )


def _approved_root_configuration_sha256(
    *,
    key: bytes,
    approved_root_id: str,
    approved_root_revision: str,
    identity_key_revision: str,
    root_snapshot: Mapping[str, object],
    policy_limits: Mapping[str, int],
) -> str:
    volume, file_id = _snapshot_identity(root_snapshot)
    root_path = _normalize_windows_final_path(root_snapshot["final_path"])
    limits_sha = canonical_json_sha256(dict(policy_limits))
    return _hmac_token(
        key,
        _APPROVED_ROOT_DOMAIN,
        _text_part(approved_root_id),
        _text_part(approved_root_revision),
        _text_part(_IDENTITY_SCHEME),
        _text_part(_IDENTITY_SCHEME_VERSION),
        _text_part(identity_key_revision),
        _u64_part(volume),
        _file_id_part(file_id),
        _text_part(root_path),
        _text_part(limits_sha),
    )


def _path_binding_sha256(
    *,
    key: bytes,
    approved_root_configuration_sha256: str,
    approved_root_revision: str,
    relative_path: str,
    object_token: str,
) -> str:
    return _hmac_token(
        key,
        _PATH_BINDING_DOMAIN,
        _text_part(approved_root_configuration_sha256),
        _text_part(approved_root_revision),
        _text_part(ntpath.normcase(relative_path.replace("/", "\\"))),
        _text_part(object_token),
    )


def _stream_handle_sha256(
    adapter: object,
    handle: object,
    *,
    chunk_size: int,
    max_file_bytes: int,
) -> tuple[str, int]:
    try:
        adapter.rewind(handle)
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = adapter.read(handle, chunk_size)
            if not isinstance(chunk, bytes):
                raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
            if not chunk:
                break
            total += len(chunk)
            if total > max_file_bytes:
                raise SourceIntegrityError("RESOURCE_LIMIT")
            digest.update(chunk)
        return digest.hexdigest(), total
    except SourceIntegrityError:
        raise
    except Exception:
        raise SourceIntegrityError("EVIDENCE_UNAVAILABLE") from None


def _same_snapshot(before: Mapping[str, object], after: Mapping[str, object]) -> bool:
    return (
        _normalize_windows_final_path(before["final_path"])
        == _normalize_windows_final_path(after["final_path"])
        and _snapshot_identity(before) == _snapshot_identity(after)
        and _snapshot_size(before) == _snapshot_size(after)
        and before["reparse"] is after["reparse"]
    )


def _group_id(group_type: str, members: list[Mapping[str, object]]) -> str:
    material = {
        "group_type": group_type,
        "source_ids": sorted(str(item["source_id"]) for item in members),
        "observed_sha256": str(members[0]["observed_sha256"]),
        "file_object_identity_tokens": sorted(
            {str(item["file_object_identity_token"]) for item in members}
        ),
        "path_bindings": sorted(str(item["path_binding_sha256"]) for item in members),
    }
    return "GROUP-" + canonical_json_sha256(material)[:24]


def _derive_groups(items: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    assigned: set[str] = set()
    by_object: dict[str, list[dict[str, object]]] = {}
    for item in items:
        by_object.setdefault(str(item["file_object_identity_token"]), []).append(item)
    for members in by_object.values():
        if len(members) < 2:
            continue
        hashes = {str(item["observed_sha256"]) for item in members}
        if len(hashes) != 1:
            raise SourceIntegrityError("IDENTITY_CHANGED")
        for item in members:
            item["byte_custody_state"] = "SAME_FILE_ALIAS"
            assigned.add(str(item["source_id"]))
        groups.append(
            {
                "alias_group_id": _group_id("SAME_FILE_ALIAS", members),
                "group_type": "SAME_FILE_ALIAS",
                "source_ids": sorted(str(item["source_id"]) for item in members),
                "observed_sha256": str(members[0]["observed_sha256"]),
                "file_object_identity_tokens": sorted(
                    {str(item["file_object_identity_token"]) for item in members}
                ),
                "path_bindings": sorted(
                    str(item["path_binding_sha256"]) for item in members
                ),
            }
        )

    by_hash: dict[str, list[dict[str, object]]] = {}
    for item in items:
        if str(item["source_id"]) not in assigned:
            by_hash.setdefault(str(item["observed_sha256"]), []).append(item)
    for members in by_hash.values():
        if len(members) < 2:
            continue
        tokens = {str(item["file_object_identity_token"]) for item in members}
        if len(tokens) != len(members):
            raise SourceIntegrityError("IDENTITY_CHANGED")
        for item in members:
            item["byte_custody_state"] = "DUPLICATE_BYTES"
        groups.append(
            {
                "alias_group_id": _group_id("DUPLICATE_BYTES", members),
                "group_type": "DUPLICATE_BYTES",
                "source_ids": sorted(str(item["source_id"]) for item in members),
                "observed_sha256": str(members[0]["observed_sha256"]),
                "file_object_identity_tokens": sorted(tokens),
                "path_bindings": sorted(
                    str(item["path_binding_sha256"]) for item in members
                ),
            }
        )
    groups.sort(key=lambda group: str(group["alias_group_id"]))
    return groups


class _WindowsHandle:
    def __init__(self, kernel32: object, value: int) -> None:
        self._kernel32 = kernel32
        self.value = value

    def __enter__(self) -> "_WindowsHandle":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if not self._kernel32.CloseHandle(wintypes.HANDLE(self.value)):
            raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


class _FileId128(ctypes.Structure):
    _fields_ = [("Identifier", ctypes.c_ubyte * _FILE_ID_BYTES)]


class _FileIdInfo(ctypes.Structure):
    _fields_ = [
        ("VolumeSerialNumber", ctypes.c_ulonglong),
        ("FileId", _FileId128),
    ]


class _WindowsHandleAdapter:
    _GENERIC_READ = 0x80000000
    _FILE_READ_ATTRIBUTES = 0x80
    _FILE_SHARE_READ = 0x1
    _FILE_SHARE_DELETE = 0x4
    _OPEN_EXISTING = 3
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x400
    _INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
    _FILE_BEGIN = 0

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise SourceIntegrityError("WINDOWS_HANDLE_EVIDENCE_UNAVAILABLE")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._invalid_handle = ctypes.c_void_p(-1).value

        self._kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self._kernel32.CreateFileW.restype = wintypes.HANDLE
        self._kernel32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
        self._kernel32.GetFileAttributesW.restype = wintypes.DWORD
        self._kernel32.GetFinalPathNameByHandleW.argtypes = [
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        self._kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
        self._kernel32.GetFileInformationByHandle.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_ByHandleFileInformation),
        ]
        self._kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
        self._kernel32.GetFileInformationByHandleEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        self._kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
        self._kernel32.SetFilePointerEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong),
            wintypes.DWORD,
        ]
        self._kernel32.SetFilePointerEx.restype = wintypes.BOOL
        self._kernel32.ReadFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        self._kernel32.ReadFile.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL

    def _create(self, path: str, *, directory: bool) -> _WindowsHandle:
        access = self._FILE_READ_ATTRIBUTES if directory else (
            self._GENERIC_READ | self._FILE_READ_ATTRIBUTES
        )
        flags = self._FILE_FLAG_OPEN_REPARSE_POINT
        if directory:
            flags |= self._FILE_FLAG_BACKUP_SEMANTICS
        handle = self._kernel32.CreateFileW(
            path,
            access,
            self._FILE_SHARE_READ | self._FILE_SHARE_DELETE,
            None,
            self._OPEN_EXISTING,
            flags,
            None,
        )
        value = ctypes.cast(handle, ctypes.c_void_p).value
        if value in {None, self._invalid_handle}:
            raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
        return _WindowsHandle(self._kernel32, int(value))

    def open_root(self, approved_root: object, *, max_final_path_chars: int) -> _WindowsHandle:
        return self._create(str(approved_root), directory=True)

    def _root_path(self, root_handle: _WindowsHandle, max_final_path_chars: int) -> str:
        return str(
            self.snapshot(
                root_handle, max_final_path_chars=max_final_path_chars
            )["final_path"]
        )

    def open_source(
        self,
        root_handle: _WindowsHandle,
        relative_path: str,
        *,
        max_final_path_chars: int,
    ) -> _WindowsHandle:
        root = self._root_path(root_handle, max_final_path_chars)
        return self._create(
            ntpath.join(root, relative_path.replace("/", "\\")),
            directory=False,
        )

    def reopen_source(
        self,
        root_handle: _WindowsHandle,
        relative_path: str,
        *,
        max_final_path_chars: int,
    ) -> _WindowsHandle:
        return self.open_source(
            root_handle,
            relative_path,
            max_final_path_chars=max_final_path_chars,
        )

    def check_no_reparse(self, root_handle: _WindowsHandle, relative_path: str) -> None:
        root = self._root_path(root_handle, _MAX_FINAL_PATH_CHARS)
        current = root
        for component in relative_path.replace("/", "\\").split("\\"):
            current = ntpath.join(current, component)
            attributes = int(self._kernel32.GetFileAttributesW(current)) & 0xFFFFFFFF
            if attributes == self._INVALID_FILE_ATTRIBUTES:
                raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
            if attributes & self._FILE_ATTRIBUTE_REPARSE_POINT:
                raise SourceIntegrityError("REPARSE_POINT")

    def snapshot(
        self, handle: _WindowsHandle, *, max_final_path_chars: int
    ) -> dict[str, object]:
        buffer_size = min(512, max_final_path_chars)
        final_path: str | None = None
        while buffer_size <= max_final_path_chars:
            buffer = ctypes.create_unicode_buffer(buffer_size)
            length = self._kernel32.GetFinalPathNameByHandleW(
                wintypes.HANDLE(handle.value), buffer, buffer_size, 0
            )
            if length == 0:
                raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
            if length < buffer_size:
                final_path = buffer.value
                break
            next_size = max(buffer_size * 2, int(length) + 1)
            if next_size <= buffer_size or next_size > max_final_path_chars:
                break
            buffer_size = next_size
        if final_path is None or len(final_path) > max_final_path_chars:
            raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")

        basic = _ByHandleFileInformation()
        if not self._kernel32.GetFileInformationByHandle(
            wintypes.HANDLE(handle.value), ctypes.byref(basic)
        ):
            raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
        file_id_info = _FileIdInfo()
        if not self._kernel32.GetFileInformationByHandleEx(
            wintypes.HANDLE(handle.value),
            _FILE_ID_INFO_CLASS,
            ctypes.byref(file_id_info),
            ctypes.sizeof(file_id_info),
        ):
            raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
        size = (int(basic.nFileSizeHigh) << 32) | int(basic.nFileSizeLow)
        file_id = bytes(file_id_info.FileId.Identifier)
        if len(file_id) != _FILE_ID_BYTES:
            raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
        return {
            "final_path": final_path,
            "volume_serial": int(file_id_info.VolumeSerialNumber),
            "file_id": file_id,
            "size": size,
            "reparse": bool(
                basic.dwFileAttributes & self._FILE_ATTRIBUTE_REPARSE_POINT
            ),
        }

    def rewind(self, handle: _WindowsHandle) -> None:
        new_position = ctypes.c_longlong()
        if not self._kernel32.SetFilePointerEx(
            wintypes.HANDLE(handle.value),
            ctypes.c_longlong(0),
            ctypes.byref(new_position),
            self._FILE_BEGIN,
        ):
            raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")

    def read(self, handle: _WindowsHandle, size: int) -> bytes:
        buffer = ctypes.create_string_buffer(size)
        read_count = wintypes.DWORD()
        if not self._kernel32.ReadFile(
            wintypes.HANDLE(handle.value),
            buffer,
            size,
            ctypes.byref(read_count),
            None,
        ):
            raise SourceIntegrityError("EVIDENCE_UNAVAILABLE")
        return buffer.raw[: int(read_count.value)]


_WINDOWS_ADAPTER_FACTORY = _WindowsHandleAdapter


def inspect_source_bundle(
    *,
    approved_root_id: str,
    approved_root_revision: str,
    approved_root: object,
    identity_key: bytes,
    identity_key_revision: str,
    policy_limits: Mapping[str, int],
    source_bundle: object,
) -> dict[str, object]:
    """Inspect source bytes through custody-owned handles without parsing media."""
    root_id = _identifier(approved_root_id, path="approved_root_id")
    root_revision = _identifier(
        approved_root_revision, path="approved_root_revision"
    )
    key_revision = _identifier(identity_key_revision, path="identity_key_revision")
    key = _validate_identity_key(identity_key)
    limits = _validate_policy_limits(policy_limits)
    try:
        bundle = validate_source_bundle(source_bundle)
        bundle_hash = source_bundle_sha256(bundle)
    except Exception as exc:
        if exc.__class__.__name__ == "SourceBundleError":
            raise SourceIntegrityError("SOURCE_BUNDLE_INVALID") from None
        raise
    items_value = bundle["items"]
    if not isinstance(items_value, list) or len(items_value) > limits["max_items"]:
        raise SourceIntegrityError("RESOURCE_LIMIT")
    try:
        adapter = _WINDOWS_ADAPTER_FACTORY()
        with adapter.open_root(
            approved_root,
            max_final_path_chars=limits["max_final_path_chars"],
        ) as root_handle:
            root_snapshot = _safe_snapshot(
                adapter,
                root_handle,
                max_final_path_chars=limits["max_final_path_chars"],
            )
            if root_snapshot["reparse"]:
                raise SourceIntegrityError("REPARSE_POINT")
            root_config = _approved_root_configuration_sha256(
                key=key,
                approved_root_id=root_id,
                approved_root_revision=root_revision,
                identity_key_revision=key_revision,
                root_snapshot=root_snapshot,
                policy_limits=limits,
            )
            observed_items: list[dict[str, object]] = []
            total_bytes = 0
            for item in items_value:
                relative_path = str(item["relative_path"])
                _normalize_declared_relative_path(relative_path)
                adapter.check_no_reparse(root_handle, relative_path)
                with adapter.open_source(
                    root_handle,
                    relative_path,
                    max_final_path_chars=limits["max_final_path_chars"],
                ) as source_handle:
                    before = _safe_snapshot(
                        adapter,
                        source_handle,
                        max_final_path_chars=limits["max_final_path_chars"],
                    )
                    if before["reparse"]:
                        raise SourceIntegrityError("REPARSE_POINT")
                    final_relative = _final_relative_path(
                        root_final_path=root_snapshot["final_path"],
                        source_final_path=before["final_path"],
                        declared=relative_path,
                    )
                    expected_size = _snapshot_size(before)
                    if expected_size > limits["max_file_bytes"]:
                        raise SourceIntegrityError("RESOURCE_LIMIT")
                    if total_bytes + expected_size > limits["max_total_bytes"]:
                        raise SourceIntegrityError("RESOURCE_LIMIT")
                    object_token = _object_identity_token(
                        key=key,
                        key_revision=key_revision,
                        snapshot=before,
                    )
                    path_binding = _path_binding_sha256(
                        key=key,
                        approved_root_configuration_sha256=root_config,
                        approved_root_revision=root_revision,
                        relative_path=final_relative,
                        object_token=object_token,
                    )
                    observed_sha, read_size = _stream_handle_sha256(
                        adapter,
                        source_handle,
                        chunk_size=limits["hash_chunk_size"],
                        max_file_bytes=limits["max_file_bytes"],
                    )
                    after = _safe_snapshot(
                        adapter,
                        source_handle,
                        max_final_path_chars=limits["max_final_path_chars"],
                    )
                    if after["reparse"]:
                        raise SourceIntegrityError("REPARSE_POINT")
                    if not _same_snapshot(before, after) or read_size != expected_size:
                        raise SourceIntegrityError("CHANGED_DURING_READ")
                    _final_relative_path(
                        root_final_path=root_snapshot["final_path"],
                        source_final_path=after["final_path"],
                        declared=relative_path,
                    )
                    adapter.check_no_reparse(root_handle, relative_path)
                    with adapter.reopen_source(
                        root_handle,
                        relative_path,
                        max_final_path_chars=limits["max_final_path_chars"],
                    ) as reopened_handle:
                        reopened = _safe_snapshot(
                            adapter,
                            reopened_handle,
                            max_final_path_chars=limits["max_final_path_chars"],
                        )
                        if reopened["reparse"]:
                            raise SourceIntegrityError("REPARSE_POINT")
                        reopened_relative = _final_relative_path(
                            root_final_path=root_snapshot["final_path"],
                            source_final_path=reopened["final_path"],
                            declared=relative_path,
                        )
                        if (
                            _snapshot_identity(reopened) != _snapshot_identity(before)
                            or reopened_relative != final_relative
                            or _snapshot_size(reopened) != expected_size
                        ):
                            raise SourceIntegrityError("IDENTITY_CHANGED_REPLACED")
                if not hmac.compare_digest(observed_sha, str(item["sha256"])):
                    raise SourceIntegrityError("HASH_MISMATCH")
                total_bytes += read_size
                if total_bytes > limits["max_total_bytes"]:
                    raise SourceIntegrityError("RESOURCE_LIMIT")
                observed_items.append(
                    {
                        "source_id": item["source_id"],
                        "kind": item["kind"],
                        "role": item["role"],
                        "relative_path": item["relative_path"],
                        "declared_sha256": item["sha256"],
                        "observed_sha256": observed_sha,
                        "size_bytes": read_size,
                        "declared_media_type": item["media_type"],
                        "page_ids": copy.deepcopy(item["page_ids"]),
                        "region_ids": copy.deepcopy(item["region_ids"]),
                        "file_object_identity_token": object_token,
                        "path_binding_sha256": path_binding,
                        "byte_custody_state": "VERIFIED_BYTES",
                    }
                )
            observed_items.sort(key=lambda item: str(item["source_id"]))
            groups = _derive_groups(observed_items)
            return {
                "bundle_id": bundle["bundle_id"],
                "run_id": bundle["run_id"],
                "source_bundle_sha256": bundle_hash,
                "approved_root_id": root_id,
                "approved_root_revision": root_revision,
                "approved_root_configuration_sha256": root_config,
                "identity_scheme": _IDENTITY_SCHEME,
                "identity_scheme_version": _IDENTITY_SCHEME_VERSION,
                "identity_key_revision": key_revision,
                "items": copy.deepcopy(observed_items),
                "alias_groups": copy.deepcopy(groups),
            }
    except SourceIntegrityError:
        raise
    except Exception:
        raise SourceIntegrityError("EVIDENCE_UNAVAILABLE") from None


def _constant_hash_equal(left: object, right: object) -> bool:
    return isinstance(left, str) and isinstance(right, str) and hmac.compare_digest(
        left, right
    )


def require_source_custody_match(
    *,
    approved_root_id: str,
    approved_root_revision: str,
    approved_root: object,
    identity_key: bytes,
    identity_key_revision: str,
    policy_limits: Mapping[str, int],
    source_bundle: object,
    custody: object,
) -> None:
    """Require current byte custody to match a complete SourceCustody record."""
    normalized = validate_source_custody(custody)
    if normalized["approved_root_id"] != approved_root_id:
        raise SourceIntegrityError("CUSTODY_STALE_ROOT")
    if normalized["approved_root_revision"] != approved_root_revision:
        raise SourceIntegrityError("CUSTODY_STALE_ROOT")
    if normalized["identity_key_revision"] != identity_key_revision:
        raise SourceIntegrityError("CUSTODY_STALE_KEY")
    evidence = inspect_source_bundle(
        approved_root_id=approved_root_id,
        approved_root_revision=approved_root_revision,
        approved_root=approved_root,
        identity_key=identity_key,
        identity_key_revision=identity_key_revision,
        policy_limits=policy_limits,
        source_bundle=source_bundle,
    )
    if normalized["bundle_id"] != evidence["bundle_id"]:
        raise SourceIntegrityError("CUSTODY_STALE_DECLARATION")
    if normalized["run_id"] != evidence["run_id"]:
        raise SourceIntegrityError("CUSTODY_STALE_DECLARATION")
    for field in (
        "source_bundle_sha256",
        "approved_root_configuration_sha256",
    ):
        if not _constant_hash_equal(normalized[field], evidence[field]):
            raise SourceIntegrityError("CUSTODY_STALE_CONTEXT")
    current_by_id = {str(item["source_id"]): item for item in evidence["items"]}
    custody_by_id = {str(item["source_id"]): item for item in normalized["items"]}
    if set(current_by_id) != set(custody_by_id):
        raise SourceIntegrityError("CUSTODY_STALE_SOURCE_SET")
    declaration_fields = (
        "kind",
        "role",
        "declared_media_type",
        "page_ids",
        "region_ids",
    )
    for source_id, current in current_by_id.items():
        prior = custody_by_id[source_id]
        if any(prior[field] != current[field] for field in declaration_fields):
            raise SourceIntegrityError("CUSTODY_STALE_DECLARATION")
        if prior["relative_path"] != current["relative_path"]:
            raise SourceIntegrityError("CUSTODY_STALE_PATH")
        if prior["size_bytes"] != current["size_bytes"]:
            raise SourceIntegrityError("CUSTODY_STALE_SIZE")
        for field in (
            "declared_sha256",
            "observed_sha256",
            "file_object_identity_token",
            "path_binding_sha256",
        ):
            if not _constant_hash_equal(prior[field], current[field]):
                if field == "file_object_identity_token":
                    raise SourceIntegrityError("CUSTODY_STALE_IDENTITY")
                if field == "path_binding_sha256":
                    raise SourceIntegrityError("CUSTODY_STALE_PATH")
                raise SourceIntegrityError("CUSTODY_STALE_BYTES")
    if canonical_json_sha256(normalized["alias_groups"]) != canonical_json_sha256(
        evidence["alias_groups"]
    ):
        raise SourceIntegrityError("CUSTODY_STALE_ALIAS_CLASSIFICATION")


__all__.extend(["inspect_source_bundle", "require_source_custody_match"])
