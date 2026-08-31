"""Bounded, server-owned OpenAI Responses inference adapter.

The adapter deliberately owns only the direct Responses request and its
provider observation.  R5 verdict sealing, candidate/currentness authority,
and M3 epoch accounting remain in their existing owners.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from threading import Lock
from types import MappingProxyType
from typing import Any, Protocol

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.vision_handoff import (
    InferenceProviderObservation,
    validate_inference_provider_observation,
)


RESPONSES_MODEL = "gpt-5.6-sol"
RESPONSES_PROVIDER = "openai.responses"
RESPONSES_API_URL = "https://api.openai.com/v1/responses"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PROVIDER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
_TERMINAL_STATUSES = frozenset({"completed", "failed", "incomplete", "cancelled"})
_NON_TERMINAL_STATUSES = frozenset({"queued", "in_progress"})
_SCHEMA_KEYS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "minItems",
        "minLength",
    }
)


class ResponsesProviderError(ValueError):
    """Fail-closed error from the bounded Responses provider seam."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _fail(code: str) -> None:
    raise ResponsesProviderError(code)


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _string(value: object, *, code: str) -> str:
    if type(value) is not str or not value:
        _fail(code)
    return value


def _identifier(value: object, *, code: str) -> str:
    text = _string(value, code=code)
    if _IDENTIFIER.fullmatch(text) is None:
        _fail(code)
    return text


def _provider_id(value: object, *, code: str) -> str:
    text = _string(value, code=code)
    if _PROVIDER_ID.fullmatch(text) is None:
        _fail(code)
    return text


def _sha(value: object, *, code: str) -> str:
    text = _string(value, code=code)
    if _SHA256.fullmatch(text) is None:
        _fail(code)
    return text


def responses_input_payload(*, input_text: str, input_image_data_url: str) -> dict[str, object]:
    """Build the only input shape accepted by the bounded R5 adapter."""

    _string(input_text, code="INPUT_TEXT_INVALID")
    _validate_image_data_url(input_image_data_url)
    return {
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": input_text},
                    {"type": "input_image", "image_url": input_image_data_url},
                ],
            }
        ]
    }


def _validate_image_data_url(value: object) -> str:
    text = _string(value, code="INPUT_IMAGE_INVALID")
    if not text.startswith("data:image/") or ";base64," not in text:
        _fail("INPUT_IMAGE_INVALID")
    encoded = text.split(";base64,", 1)[1]
    if not encoded or len(encoded) > 16 * 1024 * 1024:
        _fail("INPUT_IMAGE_INVALID")
    try:
        base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError):
        _fail("INPUT_IMAGE_INVALID")
    return text


def _validate_schema_definition(value: object, *, code: str = "SCHEMA_INVALID") -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(code)
    if set(value) - _SCHEMA_KEYS:
        _fail(code)
    schema_type = value.get("type")
    if schema_type is not None and schema_type not in {
        "object",
        "array",
        "string",
        "number",
        "integer",
        "boolean",
        "null",
    }:
        _fail(code)
    if "properties" in value:
        properties = value["properties"]
        if not isinstance(properties, Mapping):
            _fail(code)
        for key, nested in properties.items():
            if type(key) is not str:
                _fail(code)
            _validate_schema_definition(nested, code=code)
    if "items" in value:
        _validate_schema_definition(value["items"], code=code)
    if "required" in value:
        required = value["required"]
        if not isinstance(required, list) or any(type(item) is not str for item in required):
            _fail(code)
        if len(set(required)) != len(required):
            _fail(code)
    if "additionalProperties" in value and type(value["additionalProperties"]) is not bool:
        _fail(code)
    if "enum" in value and (
        not isinstance(value["enum"], list) or not value["enum"]
    ):
        _fail(code)
    for field_name in ("minItems", "minLength"):
        if field_name in value and (
            type(value[field_name]) is not int or value[field_name] < 0
        ):
            _fail(code)
    return value


def _validate_schema_value(value: object, schema: Mapping[str, object], *, code: str) -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, Mapping):
            _fail(code)
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if any(key not in value for key in required):
            _fail(code)
        if schema.get("additionalProperties") is False and any(
            key not in properties for key in value
        ):
            _fail(code)
        for key, nested in properties.items():
            if key in value:
                _validate_schema_value(value[key], nested, code=code)  # type: ignore[index]
    elif schema_type == "array":
        if type(value) is not list:
            _fail(code)
        if "minItems" in schema and len(value) < schema["minItems"]:
            _fail(code)
        if "items" in schema:
            for item in value:
                _validate_schema_value(item, schema["items"], code=code)  # type: ignore[index]
    elif schema_type == "string":
        if type(value) is not str:
            _fail(code)
        if "minLength" in schema and len(value) < schema["minLength"]:
            _fail(code)
    elif schema_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _fail(code)
    elif schema_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            _fail(code)
    elif schema_type == "boolean" and type(value) is not bool:
        _fail(code)
    elif schema_type == "null" and value is not None:
        _fail(code)
    if "enum" in schema and value not in schema["enum"]:
        _fail(code)
    if "const" in schema and value != schema["const"]:
        _fail(code)


@dataclass(frozen=True, slots=True, repr=False)
class ResponsesRequest:
    """Server-owned request identity; it intentionally has no response ID."""

    request_id: str
    run_id: str
    task6_epoch_id: str
    model: str
    input_text: str
    input_image_data_url: str
    input_sha256: str
    schema_name: str
    schema_bytes: bytes
    schema_sha256: str
    validator_version: str
    candidate_revision_sha256: str
    candidate_state_sha256: str
    request_sha256: str
    timeout_seconds: float

    def __repr__(self) -> str:
        return (
            "ResponsesRequest("
            f"request_id={self.request_id!r}, run_id={self.run_id!r}, "
            f"task6_epoch_id={self.task6_epoch_id!r}, model={self.model!r})"
        )


@dataclass(frozen=True, slots=True)
class ResponsesProviderEvent:
    kind: str


@dataclass
class _ConsumptionState:
    consumed: bool = False
    lock: Lock = field(default_factory=Lock)


_ISSUANCE_TOKEN = object()


@dataclass(frozen=True, slots=True, repr=False)
class ResponsesTask6Result:
    """Provider-neutral Task6 result with truthful Responses identities."""

    operation: str
    task6_epoch_id: str
    response_id: str
    run_id: str
    request_id: str
    model: str
    provider: str
    provider_status: str
    error: Mapping[str, object] | None
    incomplete_details: Mapping[str, object] | None
    status: str
    success: bool
    events: tuple[ResponsesProviderEvent, ...]
    candidate_output: object
    candidate_trusted: bool
    failure_code: str | None
    cleanup_result: object | None
    promotion_safe: bool
    request_sha256: str
    input_sha256: str
    candidate_revision_sha256: str
    candidate_state_sha256: str
    schema_sha256: str
    validator_version: str
    usage: Mapping[str, object]
    _issued_token: object = field(default=None, repr=False, compare=False)
    _consumption_state: _ConsumptionState | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "error", _freeze(self.error))
        object.__setattr__(self, "incomplete_details", _freeze(self.incomplete_details))
        object.__setattr__(self, "candidate_output", _freeze(self.candidate_output))
        object.__setattr__(self, "usage", _freeze(self.usage))

    def __repr__(self) -> str:
        return (
            "ResponsesTask6Result("
            f"task6_epoch_id={self.task6_epoch_id!r}, response_id={self.response_id!r}, "
            f"status={self.status!r}, success={self.success!r})"
        )

    def to_evidence(self) -> dict[str, object]:
        """Return the privacy-safe result surface; no credential is retained."""

        return {
            "provider": self.provider,
            "response_id": self.response_id,
            "task6_epoch_id": self.task6_epoch_id,
            "run_id": self.run_id,
            "request_id": self.request_id,
            "model": self.model,
            "provider_status": self.provider_status,
            "error": _thaw(self.error),
            "incomplete_details": _thaw(self.incomplete_details),
            "status": self.status,
            "success": self.success,
            "request_sha256": self.request_sha256,
            "input_sha256": self.input_sha256,
            "candidate_revision_sha256": self.candidate_revision_sha256,
            "candidate_state_sha256": self.candidate_state_sha256,
            "schema_sha256": self.schema_sha256,
            "validator_version": self.validator_version,
            "usage": _thaw(self.usage),
        }


class ResponsesClient(Protocol):
    def create(self, payload: dict[str, object]) -> Mapping[str, object]: ...

    def retrieve(self, response_id: str) -> Mapping[str, object]: ...

    def cancel(self, response_id: str) -> Mapping[str, object]: ...


class ResponsesHttpClient:
    """Small direct Responses client; the credential never enters a child."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = RESPONSES_API_URL,
        urlopen: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        if type(api_key) is not str or not api_key:
            _fail("API_CREDENTIAL_INVALID")
        if base_url != RESPONSES_API_URL:
            _fail("API_ENDPOINT_INVALID")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._urlopen = urlopen

    def __repr__(self) -> str:
        return f"ResponsesHttpClient(base_url={self._base_url!r})"

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=(
                None
                if payload is None
                else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            ),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with self._urlopen(request, timeout=60) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, ValueError):
            _fail("RESPONSES_PROVIDER_ERROR")
        if not isinstance(decoded, Mapping):
            _fail("RESPONSES_PROVIDER_ERROR")
        return decoded

    def create(self, payload: dict[str, object]) -> Mapping[str, object]:
        return self._request("POST", "", payload)

    def retrieve(self, response_id: str) -> Mapping[str, object]:
        _provider_id(response_id, code="RESPONSE_ID_MISSING")
        return self._request("GET", f"/{response_id}")

    def cancel(self, response_id: str) -> Mapping[str, object]:
        _provider_id(response_id, code="RESPONSE_ID_MISSING")
        return self._request("POST", f"/{response_id}/cancel", {})


def _validate_request(request: ResponsesRequest) -> Mapping[str, object]:
    if not isinstance(request, ResponsesRequest):
        _fail("REQUEST_INVALID")
    _identifier(request.request_id, code="REQUEST_ID_INVALID")
    _identifier(request.run_id, code="RUN_ID_INVALID")
    _identifier(request.task6_epoch_id, code="TASK6_EPOCH_ID_INVALID")
    if request.model != RESPONSES_MODEL:
        _fail("MODEL_MISMATCH")
    _validate_image_data_url(request.input_image_data_url)
    input_payload = responses_input_payload(
        input_text=request.input_text,
        input_image_data_url=request.input_image_data_url,
    )
    if request.input_sha256 != canonical_json_sha256(input_payload):
        _fail("INPUT_HASH_MISMATCH")
    if not isinstance(request.schema_bytes, bytes) or not request.schema_bytes:
        _fail("SCHEMA_INVALID")
    try:
        schema = json.loads(request.schema_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("SCHEMA_INVALID")
    _validate_schema_definition(schema)
    if hashlib.sha256(request.schema_bytes).hexdigest() != request.schema_sha256:
        _fail("SCHEMA_MISMATCH")
    _identifier(request.schema_name, code="SCHEMA_NAME_INVALID")
    _identifier(request.validator_version, code="VALIDATOR_VERSION_INVALID")
    for value, code in (
        (request.candidate_revision_sha256, "CANDIDATE_REVISION_INVALID"),
        (request.candidate_state_sha256, "CANDIDATE_STATE_INVALID"),
        (request.request_sha256, "REQUEST_HASH_INVALID"),
    ):
        _sha(value, code=code)
    if (
        isinstance(request.timeout_seconds, bool)
        or not isinstance(request.timeout_seconds, (int, float))
        or not math.isfinite(float(request.timeout_seconds))
        or not 0 < float(request.timeout_seconds) <= 300
    ):
        _fail("TIMEOUT_INVALID")
    return schema


def _request_payload(request: ResponsesRequest, schema: Mapping[str, object]) -> dict[str, object]:
    input_payload = responses_input_payload(
        input_text=request.input_text,
        input_image_data_url=request.input_image_data_url,
    )
    return {
        "model": RESPONSES_MODEL,
        "background": True,
        "store": False,
        "input": input_payload["input"],
        "text": {
            "format": {
                "type": "json_schema",
                "strict": True,
                "name": request.schema_name,
                "schema": _thaw(schema),
            }
        },
    }


def _extract_output(response: Mapping[str, object], schema: Mapping[str, object]) -> object:
    output = response.get("output")
    if not isinstance(output, list) or not output:
        _fail("OUTPUT_INVALID")
    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            _fail("TOOL_OUTPUT_UNEXPECTED")
        content = item.get("content")
        if not isinstance(content, list) or not content:
            _fail("OUTPUT_INVALID")
        for part in content:
            if not isinstance(part, Mapping) or part.get("type") != "output_text":
                _fail("TOOL_OUTPUT_UNEXPECTED")
            text_parts.append(_string(part.get("text"), code="OUTPUT_INVALID"))
    try:
        candidate = json.loads("".join(text_parts))
    except (TypeError, json.JSONDecodeError):
        _fail("OUTPUT_INVALID")
    _validate_schema_value(candidate, schema, code="OUTPUT_SCHEMA_MISMATCH")
    return candidate


def _observe(
    value: object,
    *,
    request: ResponsesRequest,
    expected_response_id: str | None = None,
) -> tuple[InferenceProviderObservation, object | None]:
    if not isinstance(value, Mapping):
        _fail("RESPONSES_PROVIDER_RESPONSE_INVALID")
    response_id = _provider_id(value.get("id"), code="RESPONSE_ID_MISSING")
    if expected_response_id is not None and response_id != expected_response_id:
        _fail("RESPONSE_ID_MISMATCH")
    model = _string(value.get("model"), code="MODEL_MISSING")
    if model != request.model:
        _fail("MODEL_MISMATCH")
    status = _string(value.get("status"), code="RESPONSE_STATUS_INVALID")
    if status not in _TERMINAL_STATUSES | _NON_TERMINAL_STATUSES:
        _fail("RESPONSE_STATUS_INVALID")
    error = value.get("error")
    if error is not None and not isinstance(error, Mapping):
        _fail("PROVIDER_ERROR_INVALID")
    incomplete_details = value.get("incomplete_details")
    if incomplete_details is not None and not isinstance(incomplete_details, Mapping):
        _fail("INCOMPLETE_DETAILS_INVALID")
    usage = value.get("usage")
    if usage is not None and not isinstance(usage, Mapping):
        _fail("USAGE_INVALID")
    observation = validate_inference_provider_observation(
        {
            "provider": RESPONSES_PROVIDER,
            "response_id": response_id,
            "model": model,
            "status": status,
            "error": error,
            "incomplete_details": incomplete_details,
            "usage": usage,
        },
        expected_provider=RESPONSES_PROVIDER,
        expected_model=request.model,
    )
    return observation, value.get("output")


def _raise_terminal_failure(
    *,
    status: str,
    error: Mapping[str, object] | None,
    incomplete_details: Mapping[str, object] | None,
) -> None:
    del error, incomplete_details
    _fail(
        {
            "failed": "RESPONSES_FAILED",
            "incomplete": "RESPONSES_INCOMPLETE",
            "cancelled": "RESPONSES_CANCELLED",
        }.get(status, "RESPONSES_NON_COMPLETED")
    )


def execute_responses_attempt(
    request: ResponsesRequest,
    *,
    client: ResponsesClient,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> ResponsesTask6Result:
    """Run one independent Responses call and return only a completed result."""

    schema = _validate_request(request)
    payload = _request_payload(request, schema)
    started = monotonic()
    try:
        raw = client.create(payload)
    except ResponsesProviderError:
        raise
    except Exception as exc:
        raise ResponsesProviderError("RESPONSES_PROVIDER_ERROR") from exc
    observation, _output = _observe(raw, request=request)
    response_id = observation.response_id
    status = observation.status
    error = observation.error
    incomplete_details = observation.incomplete_details
    while status in _NON_TERMINAL_STATUSES:
        if monotonic() >= started + float(request.timeout_seconds):
            try:
                cancelled = client.cancel(response_id)
            except Exception as exc:
                raise ResponsesProviderError("RESPONSES_CANCEL_ERROR") from exc
            cancel_observation, _ = _observe(
                cancelled,
                request=request,
                expected_response_id=response_id,
            )
            cancel_status = cancel_observation.status
            cancel_error = cancel_observation.error
            if cancel_status != "cancelled":
                _raise_terminal_failure(
                    status=cancel_status,
                    error=cancel_error,
                    incomplete_details=None,
                )
            _fail("RESPONSES_TIMEOUT")
        sleep(min(0.05, max(0.0, started + float(request.timeout_seconds) - monotonic())))
        try:
            raw = client.retrieve(response_id)
        except Exception as exc:
            raise ResponsesProviderError("RESPONSES_PROVIDER_ERROR") from exc
        observation, _output = _observe(
            raw,
            request=request,
            expected_response_id=response_id,
        )
        response_id = observation.response_id
        status = observation.status
        error = observation.error
        incomplete_details = observation.incomplete_details

    if status != "completed":
        _raise_terminal_failure(
            status=status,
            error=error,
            incomplete_details=incomplete_details,
        )
    if error is not None:
        _fail("RESPONSES_FAILED")
    if incomplete_details is not None:
        _fail("RESPONSES_INCOMPLETE")
    usage = raw.get("usage") if isinstance(raw, Mapping) else None
    if not isinstance(usage, Mapping):
        _fail("USAGE_MISSING")
    candidate = _extract_output(raw, schema)
    result = ResponsesTask6Result(
        operation="turn",
        task6_epoch_id=request.task6_epoch_id,
        response_id=response_id,
        run_id=request.run_id,
        request_id=request.request_id,
        model=request.model,
        provider=RESPONSES_PROVIDER,
        provider_status=status,
        error=error,
        incomplete_details=incomplete_details,
        status="COMPLETED",
        success=True,
        events=(ResponsesProviderEvent("responses.completed"),),
        candidate_output=candidate,
        candidate_trusted=False,
        failure_code=None,
        cleanup_result=None,
        promotion_safe=False,
        request_sha256=request.request_sha256,
        input_sha256=request.input_sha256,
        candidate_revision_sha256=request.candidate_revision_sha256,
        candidate_state_sha256=request.candidate_state_sha256,
        schema_sha256=request.schema_sha256,
        validator_version=request.validator_version,
        usage=usage,
        _issued_token=_ISSUANCE_TOKEN,
        _consumption_state=_ConsumptionState(),
    )
    validate_responses_task6_result(result)
    return result


def validate_responses_task6_result(value: object) -> ResponsesTask6Result:
    """Accept only an adapter-issued, completed, unconsumed result object."""

    if not isinstance(value, ResponsesTask6Result) or value._issued_token is not _ISSUANCE_TOKEN:
        _fail("SERVER_ISSUED_RESULT_REQUIRED")
    if value._consumption_state is None:
        _fail("SERVER_ISSUED_RESULT_REQUIRED")
    _identifier(value.task6_epoch_id, code="TASK6_EPOCH_ID_INVALID")
    _provider_id(value.response_id, code="RESPONSE_ID_MISSING")
    if value.operation != "turn":
        _fail("RESPONSES_OPERATION_INVALID")
    _identifier(value.run_id, code="RUN_ID_INVALID")
    _identifier(value.request_id, code="REQUEST_ID_INVALID")
    if value.provider != RESPONSES_PROVIDER or value.model != RESPONSES_MODEL:
        _fail("MODEL_MISMATCH")
    if value.provider_status != "completed" or value.status != "COMPLETED" or value.success is not True:
        _fail("RESPONSES_NON_COMPLETED")
    if value.candidate_trusted is not False or value.promotion_safe is not False:
        _fail("CANDIDATE_TRUST_BOUNDARY")
    if value.error is not None or value.incomplete_details is not None:
        _fail("RESPONSES_RESULT_INVALID")
    if not isinstance(value.usage, Mapping):
        _fail("USAGE_MISSING")
    for field_value, code in (
        (value.request_sha256, "REQUEST_HASH_INVALID"),
        (value.input_sha256, "INPUT_HASH_INVALID"),
        (value.candidate_revision_sha256, "CANDIDATE_REVISION_INVALID"),
        (value.candidate_state_sha256, "CANDIDATE_STATE_INVALID"),
        (value.schema_sha256, "SCHEMA_INVALID"),
    ):
        _sha(field_value, code=code)
    if value.failure_code is not None or not value.events:
        _fail("RESPONSES_RESULT_INVALID")
    return value


def consume_responses_task6_result(value: object) -> ResponsesTask6Result:
    result = validate_responses_task6_result(value)
    state = result._consumption_state
    assert state is not None
    with state.lock:
        if state.consumed:
            _fail("TASK6_RESULT_ALREADY_CONSUMED")
        state.consumed = True
    return result


__all__ = [
    "RESPONSES_API_URL",
    "RESPONSES_MODEL",
    "RESPONSES_PROVIDER",
    "ResponsesClient",
    "ResponsesHttpClient",
    "ResponsesProviderError",
    "ResponsesProviderEvent",
    "ResponsesRequest",
    "ResponsesTask6Result",
    "consume_responses_task6_result",
    "execute_responses_attempt",
    "responses_input_payload",
    "validate_responses_task6_result",
]
