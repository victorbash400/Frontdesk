import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.agent_engine_client import AgentEngineClient, JsonEventDecoder


RESOURCE = "projects/front-desk-20260824/locations/us-central1/reasoningEngines/test-engine"


def test_stream_decoder_preserves_split_unicode_and_adjacent_events() -> None:
    decoder = JsonEventDecoder()
    encoded = '{"text":"café"}\n[{"text":"second"},{"text":"third"}]'.encode()
    events = []
    for byte in encoded:
        events.extend(decoder.feed(bytes([byte])))
    events.extend(decoder.feed(b"", final=True))
    assert events == [{"text": "café"}, {"text": "second"}, {"text": "third"}]


@pytest.mark.parametrize("payload", [b'{"unfinished":', b"null", b'{"error":{"code":503}}'])
def test_stream_decoder_reports_invalid_or_failed_streams(payload: bytes) -> None:
    with pytest.raises(RuntimeError):
        JsonEventDecoder().feed(payload, final=True)


@pytest.mark.parametrize("resource", ["", "https://example.com", RESOURCE + "/../query", RESOURCE + "?token=secret"])
def test_agent_engine_credentials_cannot_be_sent_to_arbitrary_hosts(resource: str) -> None:
    with pytest.raises(ValueError):
        AgentEngineClient(resource)


def test_stream_authenticates_and_preserves_tool_state_and_stop_actions() -> None:
    event = {
        "id": "event-1", "author": "front_desk_goal_worker", "invocationId": "invocation-1",
        "actions": {"endOfAgent": True, "stateDelta": {"loaded_goal_tool_ids": ["titan-mail"]}},
        "content": {"role": "model", "parts": [{"functionResponse": {
            "name": "complete_goal", "id": "call-1", "response": {"status": "completed"},
        }}]},
    }
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=json.dumps(event).encode())

    async def exercise() -> None:
        client = AgentEngineClient(RESOURCE)
        transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(client, "_headers", new=AsyncMock(return_value={"Authorization": "Bearer test-identity"})), patch("app.agent_engine_client.httpx.AsyncClient", return_value=transport_client):
            events = [item async for item in client.stream("async_stream_query", {"user_id": "account-1"})]
        assert len(events) == 1
        assert events[0].actions.end_of_agent
        assert events[0].actions.state_delta == {"loaded_goal_tool_ids": ["titan-mail"]}
        assert events[0].get_function_responses()[0].id == "call-1"

    asyncio.run(exercise())
    assert requests[0].headers["Authorization"] == "Bearer test-identity"
    assert str(requests[0].url) == f"https://us-central1-aiplatform.googleapis.com/v1/{RESOURCE}:streamQuery"
    assert json.loads(requests[0].content)["classMethod"] == "async_stream_query"


def test_agent_engine_http_errors_are_not_retried_or_hidden() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(403, json={"error": {"message": "Permission denied"}})

    async def exercise() -> None:
        client = AgentEngineClient(RESOURCE)
        transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(client, "_headers", new=AsyncMock(return_value={})), patch("app.agent_engine_client.httpx.AsyncClient", return_value=transport_client):
            with pytest.raises(httpx.HTTPStatusError):
                _ = [item async for item in client.stream("async_stream_query", {})]

    asyncio.run(exercise())
    assert len(requests) == 1
