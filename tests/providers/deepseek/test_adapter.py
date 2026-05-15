import asyncio

import httpx

from agent_gateway.canonical.models import CanonicalTurn
from agent_gateway.providers.deepseek.adapter import DeepSeekStandardAdapter, DeepSeekThinkingAdapter
from agent_gateway.providers.deepseek.client import DeepSeekClient
from agent_gateway.providers.registry import AdapterRegistry


def test_standard_adapter_builds_chat_completions_payload() -> None:
    adapter = DeepSeekStandardAdapter()
    turn = CanonicalTurn(
        turn_id="t1",
        model="deepseek-chat",
        input_items=[
            {"role": "system", "content": "be concise"},
            {"role": "user", "content": "say hi"},
        ],
    )

    payload = adapter.build_request(turn)

    assert payload["model"] == "deepseek-chat"
    assert payload["stream"] is True
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["content"] == "say hi"


def test_standard_adapter_ignores_reasoning_store() -> None:
    adapter = DeepSeekStandardAdapter()
    turn = CanonicalTurn(
        turn_id="t1",
        model="deepseek-chat",
        input_items=[
            {"type": "function_call", "call_id": "call_1", "name": "fn", "arguments": "{}"},
        ],
    )

    payload = adapter.build_request(turn, reasoning_store={"call_1": "thinking..."})

    assert "reasoning_content" not in payload["messages"][0]


def test_thinking_adapter_injects_reasoning_content() -> None:
    adapter = DeepSeekThinkingAdapter()
    turn = CanonicalTurn(
        turn_id="t1",
        model="deepseek-reasoner",
        input_items=[
            {"type": "function_call", "call_id": "call_1", "name": "fn", "arguments": "{}"},
        ],
    )

    payload = adapter.build_request(turn, reasoning_store={"call_1": "my reasoning"})

    assert payload["messages"][0]["reasoning_content"] == "my reasoning"


def test_registry_resolves_model_and_adapter() -> None:
    standard = DeepSeekStandardAdapter()
    thinking = DeepSeekThinkingAdapter()
    registry = AdapterRegistry(
        default_adapter=standard,
        default_model="deepseek-chat",
        model_map={"codex-mini": "deepseek-chat"},
        type_adapters={"deepseek-thinking": thinking},
        model_type_map={"deepseek-reasoner": "deepseek-thinking"},
    )

    # virtual model resolved to default model, uses standard adapter
    turn = CanonicalTurn(turn_id="t1", model="codex-mini", input_items=[{"role": "user", "content": "hi"}])
    payload = registry.build_request(turn)
    assert payload["model"] == "deepseek-chat"

    # thinking model resolved to thinking adapter
    turn2 = CanonicalTurn(
        turn_id="t2",
        model="deepseek-reasoner",
        input_items=[
            {"type": "function_call", "call_id": "c1", "name": "fn", "arguments": "{}"},
        ],
    )
    payload2 = registry.build_request(turn2, reasoning_store={"c1": "thoughts"})
    assert payload2["model"] == "deepseek-reasoner"
    assert payload2["messages"][0]["reasoning_content"] == "thoughts"


def test_adapter_translates_tool_loop_items_and_passthrough_fields() -> None:
    adapter = DeepSeekStandardAdapter()
    turn = CanonicalTurn(
        turn_id="t1",
        model="deepseek-chat",
        input_items=[
            {"type": "message", "role": "user", "content": "weather?"},
            {
                "type": "function_call",
                "call_id": "call_123",
                "name": "get_weather",
                "arguments": '{"city":"Boston"}',
            },
            {
                "type": "function_call_output",
                "call_id": "call_123",
                "output": '{"temperature":"70F"}',
            },
        ],
        tools=[{"type": "function", "name": "get_weather"}],
        tool_choice="auto",
    )

    payload = adapter.build_request(turn)

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
                        "arguments": '{"city":"Boston"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_123",
            "content": '{"temperature":"70F"}',
        },
    ]
    assert payload["tools"] == [{"type": "function", "function": {"name": "get_weather", "description": "", "parameters": {"type": "object", "properties": {}}}}]
    assert payload["tool_choice"] == "auto"


def test_adapter_groups_parallel_function_calls_into_one_assistant_message() -> None:
    adapter = DeepSeekStandardAdapter()
    turn = CanonicalTurn(
        turn_id="t1",
        model="deepseek-chat",
        input_items=[
            {"type": "message", "role": "user", "content": "run both"},
            {"type": "function_call", "call_id": "c1", "name": "fn_a", "arguments": "{}"},
            {"type": "function_call", "call_id": "c2", "name": "fn_b", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "c1", "output": "result_a"},
            {"type": "function_call_output", "call_id": "c2", "output": "result_b"},
        ],
    )

    payload = adapter.build_request(turn)

    messages = payload["messages"]
    assert len(messages) == 4
    assert messages[1]["role"] == "assistant"
    assert len(messages[1]["tool_calls"]) == 2  # both calls in one assistant message
    assert messages[2]["role"] == "tool"
    assert messages[3]["role"] == "tool"


class _FakeAsyncClient:
    instances: list["_FakeAsyncClient"] = []

    def __init__(self, *, base_url: str, headers: dict[str, str], timeout: float) -> None:
        self.base_url = base_url
        self.headers = headers
        self.timeout = timeout
        self.build_request_calls: list[tuple[str, str, dict[str, object]]] = []
        self.send_calls: list[tuple[httpx.Request, bool]] = []
        self.post_calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False
        self.response = httpx.Response(200, request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"))
        _FakeAsyncClient.instances.append(self)

    def build_request(self, method: str, url: str, *, json: dict[str, object]) -> httpx.Request:
        self.build_request_calls.append((method, url, json))
        return httpx.Request(method, f"{self.base_url}{url}", json=json)

    async def send(self, request: httpx.Request, *, stream: bool = False) -> httpx.Response:
        self.send_calls.append((request, stream))
        return self.response

    async def post(self, url: str, *, json: dict[str, object]) -> httpx.Response:
        self.post_calls.append((url, json))
        return self.response

    async def aclose(self) -> None:
        self.closed = True

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.aclose()


def test_client_stream_chat_completions_uses_streaming_transport(monkeypatch: object) -> None:
    _FakeAsyncClient.instances.clear()
    monkeypatch.setattr("agent_gateway.providers.deepseek.client.httpx.AsyncClient", _FakeAsyncClient)

    async def run() -> None:
        client = DeepSeekClient(base_url="https://api.deepseek.com", api_key="test-key")
        payload = {"model": "deepseek-chat", "messages": [], "stream": True}

        response = await client.stream_chat_completions(payload)

        fake = _FakeAsyncClient.instances[0]
        assert response is fake.response
        assert fake.post_calls == []
        assert fake.build_request_calls == [("POST", "/chat/completions", payload)]
        assert len(fake.send_calls) == 1
        assert fake.send_calls[0][1] is True
        await client.aclose()

    asyncio.run(run())


def test_client_aclose_closes_owned_async_client(monkeypatch: object) -> None:
    _FakeAsyncClient.instances.clear()
    monkeypatch.setattr("agent_gateway.providers.deepseek.client.httpx.AsyncClient", _FakeAsyncClient)

    async def run() -> None:
        client = DeepSeekClient(base_url="https://api.deepseek.com", api_key="test-key")
        fake = _FakeAsyncClient.instances[0]

        assert fake.closed is False
        await client.aclose()
        assert fake.closed is True

    asyncio.run(run())


def test_client_async_context_manager_closes_owned_async_client(monkeypatch: object) -> None:
    _FakeAsyncClient.instances.clear()
    monkeypatch.setattr("agent_gateway.providers.deepseek.client.httpx.AsyncClient", _FakeAsyncClient)

    async def run() -> None:
        async with DeepSeekClient(base_url="https://api.deepseek.com", api_key="test-key") as client:
            fake = _FakeAsyncClient.instances[0]
            assert fake.closed is False
            assert isinstance(client, DeepSeekClient)

        assert _FakeAsyncClient.instances[0].closed is True

    asyncio.run(run())
