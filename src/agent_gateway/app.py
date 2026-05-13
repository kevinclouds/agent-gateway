import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agent_gateway.config import GatewayConfig
from agent_gateway.canonical.events import CanonicalStreamEvent
from agent_gateway.canonical.models import CanonicalTurn
from agent_gateway.providers.deepseek.adapter import DeepSeekAdapter
from agent_gateway.providers.deepseek.client import DeepSeekClient
from agent_gateway.runtime.engine import RuntimeEngine
from agent_gateway.runtime.rectifier import DeepSeekRectifier


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = GatewayConfig.from_env()
    app.state.config = config
    app.state.adapter = DeepSeekAdapter(default_model=config.default_model)
    app.state.engine = RuntimeEngine()
    yield


def _extract_api_key(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth.removeprefix("Bearer ").strip()
    return request.headers.get("x-api-key") or None


def _parse_sse_data(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("data: "):
        return stripped[6:]
    return None


def _event_to_sse(event: CanonicalStreamEvent) -> str:
    return f"event: {event.type}\ndata: {json.dumps(event.data)}\n\n"


def _response_to_dict(response) -> dict[str, object]:
    return {
        "id": response.response_id,
        "status": response.status,
        "messages": [
            {
                "id": msg.message_id,
                "role": msg.role,
                "content": list(msg.segments),
            }
            for msg in response.messages
        ],
    }


async def _stream_events(
    deepseek_resp,
    *,
    response_id: str,
    message_id: str,
    rectifier: DeepSeekRectifier,
    client: DeepSeekClient,
) -> AsyncIterator[str]:
    try:
        yield _event_to_sse(
            CanonicalStreamEvent(type="response.started", data={"response_id": response_id})
        )

        async for line in deepseek_resp.aiter_lines():
            payload = _parse_sse_data(line)
            if payload is None:
                continue
            if payload == "[DONE]":
                break
            chunk = json.loads(payload)
            for event in rectifier.rectify(chunk, response_id=response_id, message_id=message_id):
                yield _event_to_sse(event)

        yield _event_to_sse(CanonicalStreamEvent(type="response.completed"))
    finally:
        await client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="agent-gateway", lifespan=lifespan)

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/responses")
    async def create_response(request: Request):
        try:
            return await _handle_create_response(request)
        except Exception as e:
            return JSONResponse(
                status_code=502,
                content={"error": f"upstream request failed: {type(e).__name__}: {e}"},
            )


    async def _handle_create_response(request: Request) -> JSONResponse | StreamingResponse:
        api_key = _extract_api_key(request)
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"error": "missing API key — send x-api-key or Authorization: Bearer header"},
            )

        body = await request.json()
        model = body.get("model", request.app.state.config.default_model)
        input_items = body.get("input", [])
        stream = body.get("stream", False)

        response_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())

        turn = CanonicalTurn(
            turn_id=response_id,
            model=model,
            input_items=[
                {"role": item["role"], "content": item.get("content", "")}
                for item in input_items
            ],
        )

        client = DeepSeekClient(
            base_url=request.app.state.config.deepseek_base_url,
            api_key=api_key,
        )

        deepseek_payload = request.app.state.adapter.build_request(turn)

        try:
            deepseek_resp = await client.stream_chat_completions(deepseek_payload)
        except Exception:
            await client.aclose()
            raise

        rectifier = DeepSeekRectifier()

        if stream:
            return StreamingResponse(
                _stream_events(
                    deepseek_resp,
                    response_id=response_id,
                    message_id=message_id,
                    rectifier=rectifier,
                    client=client,
                ),
                media_type="text/event-stream",
            )

        # Non-streaming: buffer all events then project
        try:
            events: list[CanonicalStreamEvent] = [
                CanonicalStreamEvent(type="response.started", data={"response_id": response_id}),
            ]
            async for line in deepseek_resp.aiter_lines():
                payload = _parse_sse_data(line)
                if payload is None:
                    continue
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                events.extend(
                    rectifier.rectify(chunk, response_id=response_id, message_id=message_id)
                )
            events.append(CanonicalStreamEvent(type="response.completed"))

            snapshot = request.app.state.engine.consume(events)
            return JSONResponse(content=_response_to_dict(snapshot))
        finally:
            await client.aclose()

    return app
