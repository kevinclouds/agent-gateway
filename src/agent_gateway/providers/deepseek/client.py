import json
import logging

import httpx

logger = logging.getLogger("agent_gateway.deepseek")


class DeepSeekClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def stream_chat_completions(self, payload: dict[str, object]) -> httpx.Response:
        logger.debug("→ DeepSeek payload: model=%s messages_count=%d", payload.get("model"), len(payload.get("messages", [])))
        for i, msg in enumerate(payload.get("messages", [])):
            logger.debug("  [%d] role=%s content_len=%d", i, msg.get("role"), len(str(msg.get("content", ""))))
        request = self._client.build_request("POST", "/chat/completions", json=payload)
        resp = await self._client.send(request, stream=True)
        if resp.status_code >= 400:
            body = await resp.aread()
            error_text = body.decode()
            logger.error("← DeepSeek %d: %s", resp.status_code, error_text)
            raise RuntimeError(f"DeepSeek {resp.status_code}: {error_text}")
        return resp

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "DeepSeekClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.aclose()
