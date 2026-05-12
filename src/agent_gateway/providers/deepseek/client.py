import httpx


class DeepSeekClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def stream_chat_completions(self, payload: dict[str, object]) -> httpx.Response:
        request = self._client.build_request("POST", "/chat/completions", json=payload)
        return await self._client.send(request, stream=True)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "DeepSeekClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.aclose()
