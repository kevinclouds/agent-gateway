import asyncio

import httpx

from agent_gateway.canonical.models import CanonicalTurn
from agent_gateway.providers.deepseek.adapter import DeepSeekAdapter
from agent_gateway.providers.deepseek.client import DeepSeekClient


def test_adapter_translates_turn_to_chat_completions_payload() -> None:
    adapter = DeepSeekAdapter(default_model="deepseek-chat")
    turn = CanonicalTurn(
        turn_id="t1",
        model="codex-mini",
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
