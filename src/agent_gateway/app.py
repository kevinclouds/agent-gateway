import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

logger = logging.getLogger("agent_gateway")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agent_gateway.config import GatewayConfig
from agent_gateway.canonical.events import CanonicalStreamEvent
from agent_gateway.canonical.models import CanonicalTurn
from agent_gateway.canonical.projection import ResponseProjection
from agent_gateway.providers.deepseek.adapter import DeepSeekStandardAdapter, DeepSeekThinkingAdapter
from agent_gateway.providers.deepseek.client import DeepSeekClient
from agent_gateway.providers.registry import AdapterRegistry
from agent_gateway.runtime.engine import RuntimeEngine
from agent_gateway.runtime.reasoning_store import ReasoningStore
from agent_gateway.runtime.rectifier import DeepSeekRectifier


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = GatewayConfig.from_env()
    app.state.config = config
    app.state.registry = AdapterRegistry(
        default_adapter=DeepSeekStandardAdapter(),
        default_model=config.default_model,
        model_map=config.model_map,
        type_adapters={"deepseek-thinking": DeepSeekThinkingAdapter()},
        model_type_map=config.model_type_map,
    )
    app.state.engine = RuntimeEngine()
    app.state.reasoning_store = ReasoningStore(config.reasoning_store_file)
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


def _flatten_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
                continue
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"input_text", "output_text", "text"}:
                text_parts.append(str(part.get("text", "")))
        return "".join(text_parts)
    return ""


def _normalize_input_items(input_items: list[object]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for raw_item in input_items:
        if not isinstance(raw_item, dict):
            continue
        item_type = str(raw_item.get("type", "message"))
        if item_type == "function_call_output":
            normalized.append(
                {
                    "type": "function_call_output",
                    "call_id": str(raw_item["call_id"]),
                    "output": str(raw_item.get("output", "")),
                }
            )
            continue
        if item_type == "function_call":
            normalized.append(
                {
                    "type": "function_call",
                    "call_id": str(raw_item["call_id"]),
                    "name": str(raw_item["name"]),
                    "arguments": str(raw_item.get("arguments", "")),
                }
            )
            continue
        normalized.append(
            {
                "type": "message",
                "role": str(raw_item.get("role", "user")),
                "content": _flatten_content(raw_item.get("content", "")),
            }
        )
    return normalized


def _event_to_sse(event_type: str, payload: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


def _serialize_message(message) -> dict[str, object]:
    return {
        "type": "message",
        "id": message.message_id,
        "status": "completed",
        "role": message.role,
        "content": [
            {
                "type": "output_text",
                "text": segment["text"],
                "annotations": [],
            }
            for segment in message.segments
            if segment["type"] == "text"
        ],
    }


def _serialize_tool_call(tool_call) -> dict[str, object]:
    return {
        "type": "function_call",
        "id": tool_call.call_id,
        "call_id": tool_call.call_id,
        "name": tool_call.name,
        "arguments": tool_call.arguments,
        "status": tool_call.status,
    }


def _response_to_dict(response, *, model: str) -> dict[str, object]:
    return {
        "id": response.response_id,
        "object": "response",
        "status": response.status,
        "model": model,
        "output": [
            *[_serialize_message(message) for message in response.messages],
            *[_serialize_tool_call(tool_call) for tool_call in response.tool_calls],
        ],
    }


class _ResponsesEventTranslator:
    def __init__(self, *, response_id: str, model: str) -> None:
        self._response_id = response_id
        self._model = model
        self._projection = ResponseProjection()
        self._output_index_by_item_id: dict[str, int] = {}
        self._finalized_item_ids: set[str] = set()
        self._next_output_index = 0

    def start(self) -> list[str]:
        event = CanonicalStreamEvent(type="response.started", data={"response_id": self._response_id})
        self._projection.apply(event)
        return [
            _event_to_sse(
                "response.created",
                {
                    "type": "response.created",
                    "response": _response_to_dict(
                        self._projection.snapshot(),
                        model=self._model,
                    ),
                },
            )
        ]

    def apply(self, event: CanonicalStreamEvent) -> list[str]:
        payloads: list[str] = []
        if event.type == "message.started":
            self._projection.apply(event)
            output_index = self._reserve_output_index(str(event.data["message_id"]))
            payloads.append(
                _event_to_sse(
                    "response.output_item.added",
                    {
                        "type": "response.output_item.added",
                        "output_index": output_index,
                        "item": {
                            "type": "message",
                            "id": str(event.data["message_id"]),
                            "status": "in_progress",
                            "role": str(event.data["role"]),
                            "content": [],
                        },
                    },
                )
            )
            payloads.append(
                _event_to_sse(
                    "response.content_part.added",
                    {
                        "type": "response.content_part.added",
                        "item_id": str(event.data["message_id"]),
                        "output_index": output_index,
                        "content_index": 0,
                        "part": {"type": "output_text", "text": "", "annotations": []},
                    },
                )
            )
            return payloads

        if event.type == "content.delta":
            self._projection.apply(event)
            payloads.append(
                _event_to_sse(
                    "response.output_text.delta",
                    {
                        "type": "response.output_text.delta",
                        "item_id": str(event.data["message_id"]),
                        "output_index": self._output_index_by_item_id[str(event.data["message_id"])],
                        "content_index": 0,
                        "delta": str(event.data["text"]),
                    },
                )
            )
            return payloads

        if event.type == "tool_call.started":
            self._projection.apply(event)
            output_index = self._reserve_output_index(str(event.data["call_id"]))
            payloads.append(
                _event_to_sse(
                    "response.output_item.added",
                    {
                        "type": "response.output_item.added",
                        "output_index": output_index,
                        "item": {
                            "type": "function_call",
                            "id": str(event.data["call_id"]),
                            "call_id": str(event.data["call_id"]),
                            "name": str(event.data["name"]),
                            "arguments": "",
                            "status": "in_progress",
                        },
                    },
                )
            )
            return payloads

        if event.type == "tool_call.arguments.delta":
            self._projection.apply(event)
            payloads.append(
                _event_to_sse(
                    "response.function_call_arguments.delta",
                    {
                        "type": "response.function_call_arguments.delta",
                        "item_id": str(event.data["call_id"]),
                        "output_index": self._output_index_by_item_id[str(event.data["call_id"])],
                        "delta": str(event.data["text"]),
                    },
                )
            )
            return payloads

        if event.type == "tool_call.completed":
            self._projection.apply(event)
            snapshot = self._projection.snapshot()
            completed = next(
                tool_call for tool_call in snapshot.tool_calls if tool_call.call_id == str(event.data["call_id"])
            )
            output_index = self._output_index_by_item_id[completed.call_id]
            self._finalized_item_ids.add(completed.call_id)
            payloads.append(
                _event_to_sse(
                    "response.function_call_arguments.done",
                    {
                        "type": "response.function_call_arguments.done",
                        "item_id": completed.call_id,
                        "output_index": output_index,
                        "arguments": completed.arguments,
                        "name": completed.name,
                    },
                )
            )
            payloads.append(
                _event_to_sse(
                    "response.output_item.done",
                    {
                        "type": "response.output_item.done",
                        "output_index": output_index,
                        "item": _serialize_tool_call(completed),
                    },
                )
            )
            return payloads

        if event.type == "response.completed":
            self._projection.apply(event)
            snapshot = self._projection.snapshot()
            for message in snapshot.messages:
                if message.message_id in self._finalized_item_ids:
                    continue
                output_index = self._output_index_by_item_id[message.message_id]
                text = "".join(
                    segment["text"]
                    for segment in message.segments
                    if segment["type"] == "text"
                )
                payloads.append(
                    _event_to_sse(
                        "response.output_text.done",
                        {
                            "type": "response.output_text.done",
                            "item_id": message.message_id,
                            "output_index": output_index,
                            "content_index": 0,
                            "text": text,
                        },
                    )
                )
                payloads.append(
                    _event_to_sse(
                        "response.content_part.done",
                        {
                            "type": "response.content_part.done",
                            "item_id": message.message_id,
                            "output_index": output_index,
                            "content_index": 0,
                            "part": {"type": "output_text", "text": text, "annotations": []},
                        },
                    )
                )
                payloads.append(
                    _event_to_sse(
                        "response.output_item.done",
                        {
                            "type": "response.output_item.done",
                            "output_index": output_index,
                            "item": _serialize_message(message),
                        },
                    )
                )
                self._finalized_item_ids.add(message.message_id)
            payloads.append(
                _event_to_sse(
                    "response.completed",
                    {
                        "type": "response.completed",
                        "response": _response_to_dict(snapshot, model=self._model),
                    },
                )
            )
            return payloads

        self._projection.apply(event)
        return payloads

    def _reserve_output_index(self, item_id: str) -> int:
        output_index = self._next_output_index
        self._output_index_by_item_id[item_id] = output_index
        self._next_output_index += 1
        return output_index


async def _collect_events(
    deepseek_resp,
    *,
    response_id: str,
    message_id: str,
    rectifier: DeepSeekRectifier,
    reasoning_store: dict[str, str],
) -> list[CanonicalStreamEvent]:
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
        new_events = rectifier.rectify(chunk, response_id=response_id, message_id=message_id)
        for event in new_events:
            if event.type == "tool_call.completed" and event.data.get("reasoning_content"):
                reasoning_store[str(event.data["call_id"])] = str(event.data["reasoning_content"])
        events.extend(new_events)
    events.append(CanonicalStreamEvent(type="response.completed", data={"response_id": response_id}))
    return events


async def _stream_events(
    deepseek_resp,
    *,
    response_id: str,
    message_id: str,
    model: str,
    rectifier: DeepSeekRectifier,
    client: DeepSeekClient,
    reasoning_store: dict[str, str],
) -> AsyncIterator[str]:
    translator = _ResponsesEventTranslator(response_id=response_id, model=model)
    try:
        for payload in translator.start():
            yield payload

        async for line in deepseek_resp.aiter_lines():
            payload = _parse_sse_data(line)
            if payload is None:
                continue
            if payload == "[DONE]":
                break
            chunk = json.loads(payload)
            for event in rectifier.rectify(chunk, response_id=response_id, message_id=message_id):
                if event.type == "tool_call.completed" and event.data.get("reasoning_content"):
                    reasoning_store[str(event.data["call_id"])] = str(event.data["reasoning_content"])
                for encoded in translator.apply(event):
                    yield encoded

        for encoded in translator.apply(
            CanonicalStreamEvent(type="response.completed", data={"response_id": response_id})
        ):
            yield encoded
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
        model = str(body.get("model", request.app.state.config.default_model))
        input_items = _normalize_input_items(body.get("input", []))
        stream = bool(body.get("stream", False))
        logger.debug("stream=%s model=%s", stream, model)

        response_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())

        turn = CanonicalTurn(
            turn_id=response_id,
            model=model,
            input_items=input_items,
            tools=list(body.get("tools", [])),
            tool_choice=body.get("tool_choice"),
        )

        client = DeepSeekClient(
            base_url=request.app.state.config.deepseek_base_url,
            api_key=api_key,
        )

        reasoning_store: dict[str, str] = request.app.state.reasoning_store
        deepseek_payload = request.app.state.registry.build_request(turn, reasoning_store=reasoning_store)

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
                    model=model,
                    rectifier=rectifier,
                    client=client,
                    reasoning_store=reasoning_store,
                ),
                media_type="text/event-stream",
            )

        try:
            events = await _collect_events(
                deepseek_resp,
                response_id=response_id,
                message_id=message_id,
                rectifier=rectifier,
                reasoning_store=reasoning_store,
            )
            snapshot = request.app.state.engine.consume(events)
            return JSONResponse(content=_response_to_dict(snapshot, model=model))
        finally:
            await client.aclose()

    return app
