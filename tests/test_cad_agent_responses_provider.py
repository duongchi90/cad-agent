from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import replace

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256
from cad_agent.responses_provider import (
    RESPONSES_MODEL,
    RESPONSES_PROVIDER,
    ResponsesProviderEvent,
    ResponsesHttpClient,
    ResponsesProviderError,
    ResponsesRequest,
    ResponsesTask6Result,
    execute_responses_attempt,
    responses_input_payload,
    validate_responses_task6_result,
)


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["provider_verdict", "regions"],
    "properties": {
        "provider_verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
        "regions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["region_id", "status"],
                "properties": {
                    "region_id": {"type": "string", "minLength": 1},
                    "status": {"type": "string", "enum": ["PASS", "FAIL"]},
                },
            },
        },
    },
}
SCHEMA_BYTES = json.dumps(SCHEMA, sort_keys=True, separators=(",", ":")).encode()
SCHEMA_SHA = hashlib.sha256(SCHEMA_BYTES).hexdigest()
REQUEST_SHA = "a" * 64
CANDIDATE_SHA = "b" * 64
STATE_SHA = "c" * 64
SENTINEL = "sk-test-only-never-a-real-key"


def _request(**changes: object) -> ResponsesRequest:
    request = ResponsesRequest(
        request_id="request-1",
        run_id="run-1",
        task6_epoch_id="epoch-1",
        model=RESPONSES_MODEL,
        input_text="Review the bounded visual regions.",
        input_image_data_url="data:image/png;base64,AA==",
        input_sha256=canonical_json_sha256(
            responses_input_payload(
                input_text="Review the bounded visual regions.",
                input_image_data_url="data:image/png;base64,AA==",
            )
        ),
        schema_name="r5_visual_verdict",
        schema_bytes=SCHEMA_BYTES,
        schema_sha256=SCHEMA_SHA,
        validator_version="r5-validator-1",
        candidate_revision_sha256=CANDIDATE_SHA,
        candidate_state_sha256=STATE_SHA,
        request_sha256=REQUEST_SHA,
        timeout_seconds=5.0,
    )
    return replace(request, **changes)


def _response(
    *,
    response_id: str = "resp-1",
    status: str = "completed",
    model: str = RESPONSES_MODEL,
    output: object | None = None,
    usage: object | None = None,
    **extra: object,
) -> dict[str, object]:
    if output is None:
        output = [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "provider_verdict": "PASS",
                                "regions": [{"region_id": "r1", "status": "PASS"}],
                            }
                        ),
                    }
                ],
            }
        ]
    value: dict[str, object] = {
        "id": response_id,
        "object": "response",
        "status": status,
        "model": model,
        "output": output,
        "error": None,
        "incomplete_details": None,
        "usage": {"input_tokens": 10, "output_tokens": 8} if usage is None else usage,
    }
    value.update(extra)
    return value


class _FakeResponsesClient:
    def __init__(self, *responses: dict[str, object]) -> None:
        self.responses = list(responses)
        self.create_payloads: list[dict[str, object]] = []
        self.retrieve_ids: list[str] = []
        self.cancel_ids: list[str] = []

    def create(self, payload: dict[str, object]) -> dict[str, object]:
        self.create_payloads.append(payload)
        return self.responses.pop(0)

    def retrieve(self, response_id: str) -> dict[str, object]:
        self.retrieve_ids.append(response_id)
        return self.responses.pop(0)

    def cancel(self, response_id: str) -> dict[str, object]:
        self.cancel_ids.append(response_id)
        return self.responses.pop(0)


def test_request_has_no_caller_response_or_codex_thread_identity() -> None:
    parameters = inspect.signature(ResponsesRequest).parameters
    assert "response_id" not in parameters
    assert "task6_thread_id" not in parameters
    with pytest.raises(TypeError):
        inspect.signature(ResponsesRequest).bind_partial(response_id="caller-fake")


def test_success_uses_provider_response_id_and_exact_direct_call_profile() -> None:
    client = _FakeResponsesClient(_response())

    result = execute_responses_attempt(_request(), client=client)

    payload = client.create_payloads[0]
    assert set(payload) == {"model", "background", "store", "input", "text"}
    assert payload["model"] == RESPONSES_MODEL
    assert payload["background"] is False
    assert payload["store"] is False
    assert "tools" not in payload
    assert "conversation" not in payload
    assert "previous_response_id" not in payload
    assert payload["input"][0]["content"][1]["type"] == "input_image"
    assert payload["text"]["format"] == {
        "type": "json_schema",
        "strict": True,
        "name": "r5_visual_verdict",
        "schema": SCHEMA,
    }
    assert result.response_id == "resp-1"
    assert result.task6_epoch_id == "epoch-1"
    assert result.status == "COMPLETED"
    assert result.success is True
    assert result.candidate_trusted is False
    assert not hasattr(result, "task6_thread_id")
    assert not hasattr(result, "turn_id")
    assert result.provider_status == "completed"
    assert result.usage == {"input_tokens": 10, "output_tokens": 8}
    assert validate_responses_task6_result(result) is result


def test_missing_provider_response_id_fails_closed() -> None:
    client = _FakeResponsesClient(_response(response_id=""))
    with pytest.raises(ResponsesProviderError, match="RESPONSE_ID_MISSING"):
        execute_responses_attempt(_request(), client=client)


def test_non_terminal_provider_states_fail_without_retrieve_or_cancel() -> None:
    client = _FakeResponsesClient(
        _response(response_id="resp-1", status="in_progress"),
        _response(response_id="resp-1", status="completed"),
    )
    with pytest.raises(ResponsesProviderError, match="NON_COMPLETED"):
        execute_responses_attempt(_request(), client=client)
    assert len(client.create_payloads) == 1
    assert client.retrieve_ids == []
    assert client.cancel_ids == []


@pytest.mark.parametrize("status", ["queued", "in_progress", "failed", "incomplete", "cancelled"])
def test_non_completed_provider_terminal_states_never_pass(status: str) -> None:
    client = _FakeResponsesClient(
        _response(status=status),
        _response(status="completed"),
    )
    with pytest.raises(ResponsesProviderError, match="NON_COMPLETED|FAILED|INCOMPLETE|CANCELLED"):
        execute_responses_attempt(_request(), client=client)
    assert len(client.create_payloads) == 1
    assert client.retrieve_ids == []
    assert client.cancel_ids == []


def test_provider_create_failure_is_non_retried_and_fails_closed() -> None:
    class _CreateFailureClient:
        def __init__(self) -> None:
            self.create_calls = 0
            self.retrieve_ids: list[str] = []
            self.cancel_ids: list[str] = []

        def create(self, payload: dict[str, object]) -> dict[str, object]:
            del payload
            self.create_calls += 1
            raise OSError("ambiguous transport failure")

    client = _CreateFailureClient()
    with pytest.raises(ResponsesProviderError, match="RESPONSES_PROVIDER_ERROR"):
        execute_responses_attempt(_request(), client=client)
    assert client.create_calls == 1
    assert client.retrieve_ids == []
    assert client.cancel_ids == []


def test_provider_error_never_becomes_success() -> None:
    client = _FakeResponsesClient(
        _response(status="failed", error={"code": "server_error", "message": "no"})
    )
    with pytest.raises(ResponsesProviderError, match="FAILED"):
        execute_responses_attempt(_request(), client=client)


def test_completed_response_with_incomplete_details_never_passes() -> None:
    client = _FakeResponsesClient(
        _response(incomplete_details={"reason": "max_output_tokens"})
    )
    with pytest.raises(ResponsesProviderError, match="INCOMPLETE"):
        execute_responses_attempt(_request(), client=client)


def test_observed_model_mismatch_fails_closed() -> None:
    client = _FakeResponsesClient(_response(model="foreign-model"))
    with pytest.raises(ResponsesProviderError, match="MODEL_MISMATCH"):
        execute_responses_attempt(_request(), client=client)


def test_schema_hash_mismatch_is_rejected_before_provider_call() -> None:
    client = _FakeResponsesClient(_response())
    with pytest.raises(ResponsesProviderError, match="SCHEMA_MISMATCH"):
        execute_responses_attempt(_request(schema_sha256="e" * 64), client=client)
    assert client.create_payloads == []


def test_output_schema_mismatch_is_rejected() -> None:
    output = [
        {
            "type": "message",
            "content": [{"type": "output_text", "text": '{"provider_verdict":"PASS"}'}],
        }
    ]
    with pytest.raises(ResponsesProviderError, match="OUTPUT_SCHEMA_MISMATCH"):
        execute_responses_attempt(_request(), client=_FakeResponsesClient(_response(output=output)))


@pytest.mark.parametrize(
    "tool_item",
    [
        {"type": "function_call", "call_id": "call-1", "name": "danger", "arguments": "{}"},
        {"type": "web_search_call", "id": "call-1"},
        {"type": "function_call_output", "call_id": "call-1", "output": "x"},
    ],
)
def test_any_tool_call_or_tool_output_is_rejected(tool_item: dict[str, object]) -> None:
    with pytest.raises(ResponsesProviderError, match="TOOL_OUTPUT_UNEXPECTED"):
        execute_responses_attempt(
            _request(),
            client=_FakeResponsesClient(_response(output=[tool_item])),
        )


def test_two_independent_attempts_have_distinct_provider_ids_and_no_linkage() -> None:
    client = _FakeResponsesClient(_response(response_id="resp-pre"), _response(response_id="resp-post"))
    pre = execute_responses_attempt(_request(task6_epoch_id="epoch-pre"), client=client)
    post = execute_responses_attempt(_request(task6_epoch_id="epoch-post"), client=client)

    assert pre.response_id != post.response_id
    assert pre.task6_epoch_id != post.task6_epoch_id
    for payload in client.create_payloads:
        assert "previous_response_id" not in payload
        assert "conversation" not in payload


def test_result_is_provider_issued_not_a_caller_constructed_record() -> None:
    with pytest.raises(ResponsesProviderError, match="SERVER_ISSUED"):
        validate_responses_task6_result(
            object()
        )


def test_credential_is_explicit_in_memory_and_redacted_from_public_surfaces() -> None:
    client = ResponsesHttpClient(api_key=SENTINEL)
    assert SENTINEL not in repr(client)
    assert SENTINEL not in str(client)
    assert "CODEX_HOME" not in repr(client)


def test_credential_does_not_enter_result_evidence_or_wire_payload() -> None:
    client = _FakeResponsesClient(_response())
    result = execute_responses_attempt(_request(), client=client)
    assert SENTINEL not in json.dumps(result.to_evidence(), sort_keys=True)
    assert SENTINEL not in json.dumps(client.create_payloads[0], sort_keys=True)


def test_manually_constructed_result_without_server_issue_is_rejected() -> None:
    forged = ResponsesTask6Result(
        operation="turn",
        task6_epoch_id="epoch-1",
        response_id="resp-fake",
        run_id="run-1",
        request_id="request-1",
        model=RESPONSES_MODEL,
        provider=RESPONSES_PROVIDER,
        provider_status="completed",
        error=None,
        incomplete_details=None,
        status="COMPLETED",
        success=True,
        events=(ResponsesProviderEvent("responses.completed"),),
        candidate_output={"provider_verdict": "PASS"},
        candidate_trusted=False,
        failure_code=None,
        cleanup_result=None,
        promotion_safe=False,
        request_sha256=REQUEST_SHA,
        input_sha256="d" * 64,
        candidate_revision_sha256=CANDIDATE_SHA,
        candidate_state_sha256=STATE_SHA,
        schema_sha256=SCHEMA_SHA,
        validator_version="r5-validator-1",
        usage={"input_tokens": 1, "output_tokens": 1},
    )
    with pytest.raises(ResponsesProviderError, match="SERVER_ISSUED"):
        validate_responses_task6_result(forged)


def test_http_client_uses_official_methods_and_explicit_credential_header() -> None:
    class HttpResponse:
        def __init__(self, value: dict[str, object]) -> None:
            self.value = value

        def __enter__(self) -> "HttpResponse":
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def read(self) -> bytes:
            return json.dumps(self.value).encode()

    requests: list[object] = []

    def urlopen(request: object, *, timeout: float) -> HttpResponse:
        del timeout
        requests.append(request)
        return HttpResponse(_response())

    client = ResponsesHttpClient(api_key=SENTINEL, urlopen=urlopen)
    assert not hasattr(client, "retrieve")
    assert not hasattr(client, "cancel")
    client.create({"model": RESPONSES_MODEL})
    assert [request.get_method() for request in requests] == ["POST"]
    assert all(request.get_header("Authorization") == f"Bearer {SENTINEL}" for request in requests)
