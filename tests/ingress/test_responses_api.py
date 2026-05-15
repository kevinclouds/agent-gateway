import json

from fastapi.testclient import TestClient

from agent_gateway.app import create_app


class _FakeStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeDeepSeekClient:
    instances: list["_FakeDeepSeekClient"] = []
    lines: list[str] = []

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.closed = False
        self.payloads: list[dict[str, object]] = []
        _FakeDeepSeekClient.instances.append(self)

    async def stream_chat_completions(self, payload: dict[str, object]) -> _FakeStreamResponse:
        self.payloads.append(payload)
        return _FakeStreamResponse(self.lines)

    async def aclose(self) -> None:
        self.closed = True


def test_responses_endpoint_returns_openai_style_output(monkeypatch: object) -> None:
    _FakeDeepSeekClient.instances.clear()
    _FakeDeepSeekClient.lines = [
        'data: {"choices":[{"delta":{"content":"Hel"}}]}',
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        "data: [DONE]",
    ]
    monkeypatch.setattr("agent_gateway.app.DeepSeekClient", _FakeDeepSeekClient)

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/responses",
            headers={"x-api-key": "test-key"},
            json={
                "model": "codex-mini",
                "input": [{"role": "user", "content": "say hi"}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "response"
    assert body["status"] == "completed"
    assert len(body["output"]) == 1
    assert body["output"][0]["type"] == "message"
    assert body["output"][0]["role"] == "assistant"
    assert body["output"][0]["content"] == [
        {"type": "output_text", "text": "Hello", "annotations": []}
    ]
    assert _FakeDeepSeekClient.instances[0].closed is True


def test_responses_stream_emits_responses_api_events(monkeypatch: object) -> None:
    _FakeDeepSeekClient.instances.clear()
    _FakeDeepSeekClient.lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        "data: [DONE]",
    ]
    monkeypatch.setattr("agent_gateway.app.DeepSeekClient", _FakeDeepSeekClient)

    with TestClient(create_app()) as client:
        with client.stream(
            "POST",
            "/v1/responses",
            headers={"x-api-key": "test-key"},
            json={
                "model": "codex-mini",
                "input": [{"role": "user", "content": "say hi"}],
                "stream": True,
            },
        ) as response:
            lines = [line for line in response.iter_lines() if line]

    joined = "\n".join(lines)
    assert response.status_code == 200
    assert "event: response.created" in joined
    assert "event: response.output_item.added" in joined
    assert "event: response.output_text.delta" in joined
    assert "event: response.output_item.done" in joined
    assert "event: response.completed" in joined
    assert _FakeDeepSeekClient.instances[0].closed is True


def test_responses_endpoint_projects_tool_calls(monkeypatch: object) -> None:
    _FakeDeepSeekClient.instances.clear()
    _FakeDeepSeekClient.lines = [
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_123","type":"function","function":{"name":"get_weather","arguments":"{\\"city\\":\\"Bos"}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"ton\\"}"}}]}}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
        "data: [DONE]",
    ]
    monkeypatch.setattr("agent_gateway.app.DeepSeekClient", _FakeDeepSeekClient)

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/responses",
            headers={"x-api-key": "test-key"},
            json={
                "model": "codex-mini",
                "tools": [
                    {
                        "type": "function",
                        "name": "get_weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": ["city"],
                        },
                    }
                ],
                "tool_choice": "auto",
                "input": [{"role": "user", "content": "weather?"}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["output"] == [
        {
            "type": "function_call",
            "id": "call_123",
            "call_id": "call_123",
            "name": "get_weather",
            "arguments": '{"city":"Boston"}',
            "status": "completed",
        }
    ]
    assert _FakeDeepSeekClient.instances[0].payloads[0]["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        }
    ]
    assert _FakeDeepSeekClient.instances[0].payloads[0]["tool_choice"] == "auto"


def test_responses_endpoint_forwards_function_call_outputs(monkeypatch: object) -> None:
    _FakeDeepSeekClient.instances.clear()
    _FakeDeepSeekClient.lines = [
        'data: {"choices":[{"delta":{"content":"It is sunny."}}]}',
        "data: [DONE]",
    ]
    monkeypatch.setattr("agent_gateway.app.DeepSeekClient", _FakeDeepSeekClient)

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/responses",
            headers={"x-api-key": "test-key"},
            json={
                "model": "codex-mini",
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "weather?"}],
                    },
                    {
                        "type": "function_call",
                        "call_id": "call_123",
                        "name": "get_weather",
                        "arguments": json.dumps({"city": "Boston"}),
                    },
                    {
                        "type": "function_call_output",
                        "call_id": "call_123",
                        "output": json.dumps({"temperature": "70F"}),
                    },
                ],
            },
        )

    assert response.status_code == 200
    payload = _FakeDeepSeekClient.instances[0].payloads[0]
    assert payload["messages"] == [
        {"role": "user", "content": "weather?"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"city": "Boston"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_123",
            "content": '{"temperature": "70F"}',
        },
    ]
    assert response.json()["output"][0]["content"][0]["text"] == "It is sunny."
