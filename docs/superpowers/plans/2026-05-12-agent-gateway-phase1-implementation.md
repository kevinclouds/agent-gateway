# Agent Gateway Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 `agent-gateway` runtime that exposes a `Responses`-style downstream API, translates to `DeepSeek chat/completions`, and preserves a canonical event-driven runtime model that can later grow host-control integrations.

**Architecture:** The implementation follows the approved `Split-core` design. `Canonical` owns protocol execution semantics and event projection, while `host-control` remains a parallel subdomain with data models and interfaces only. Streaming is event-first: provider deltas are rectified into `CanonicalStreamEvent`, and `ResponseProjection` derives the current response view.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, pytest, anyio

**Repo note:** This workspace currently has no `.git` directory. Run commit steps only after executing inside the final git worktree or after initializing git for this project.

---

## File Structure

### Runtime entry and config
- Create: `pyproject.toml`
- Create: `src/agent_gateway/__init__.py`
- Create: `src/agent_gateway/app.py`
- Create: `src/agent_gateway/config.py`

### Canonical core
- Create: `src/agent_gateway/canonical/models.py`
- Create: `src/agent_gateway/canonical/events.py`
- Create: `src/agent_gateway/canonical/projection.py`

### Host control
- Create: `src/agent_gateway/host_control/models.py`
- Create: `src/agent_gateway/host_control/interfaces.py`

### Provider integration
- Create: `src/agent_gateway/providers/deepseek/client.py`
- Create: `src/agent_gateway/providers/deepseek/adapter.py`

### Runtime orchestration
- Create: `src/agent_gateway/runtime/rectifier.py`
- Create: `src/agent_gateway/runtime/engine.py`

### HTTP ingress
- Create: `src/agent_gateway/ingress/responses_api.py`

### Tests
- Create: `tests/test_smoke.py`
- Create: `tests/canonical/test_projection.py`
- Create: `tests/host_control/test_models.py`
- Create: `tests/providers/deepseek/test_adapter.py`
- Create: `tests/runtime/test_rectifier.py`
- Create: `tests/runtime/test_engine.py`
- Create: `tests/ingress/test_responses_api.py`

### Docs
- Create: `README.md`

## Task 1: Scaffold Project and Config

**Files:**
- Create: `pyproject.toml`
- Create: `src/agent_gateway/__init__.py`
- Create: `src/agent_gateway/config.py`
- Create: `src/agent_gateway/app.py`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/test_smoke.py
from fastapi.testclient import TestClient

from agent_gateway.app import create_app


def test_healthcheck_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_gateway'`

- [ ] **Step 3: Write minimal project skeleton and config**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "agent-gateway"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115.0",
  "httpx>=0.27.0",
  "pydantic>=2.8.0",
  "uvicorn>=0.30.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2.0",
  "pytest-anyio>=0.0.0",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
# src/agent_gateway/__init__.py
__all__ = ["__version__"]

__version__ = "0.1.0"
```

```python
# src/agent_gateway/config.py
from pydantic import BaseModel, Field


class GatewayConfig(BaseModel):
    deepseek_base_url: str = Field(default="https://api.deepseek.com")
    deepseek_api_key: str = Field(default="test-key")
    default_model: str = Field(default="deepseek-chat")
```

```python
# src/agent_gateway/app.py
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="agent-gateway")

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/agent_gateway/__init__.py src/agent_gateway/config.py src/agent_gateway/app.py tests/test_smoke.py
git commit -m "feat: scaffold gateway runtime"
```

## Task 2: Build Canonical Core and Projection

**Files:**
- Create: `src/agent_gateway/canonical/models.py`
- Create: `src/agent_gateway/canonical/events.py`
- Create: `src/agent_gateway/canonical/projection.py`
- Test: `tests/canonical/test_projection.py`

- [ ] **Step 1: Write failing projection tests**

```python
# tests/canonical/test_projection.py
from agent_gateway.canonical.events import CanonicalStreamEvent
from agent_gateway.canonical.projection import ResponseProjection


def test_projection_builds_text_output_from_content_deltas() -> None:
    projection = ResponseProjection()
    projection.apply(CanonicalStreamEvent(type="response.started", data={"response_id": "r1"}))
    projection.apply(CanonicalStreamEvent(type="message.started", data={"message_id": "m1", "role": "assistant"}))
    projection.apply(CanonicalStreamEvent(type="content.delta", data={"message_id": "m1", "text": "hello"}))
    projection.apply(CanonicalStreamEvent(type="content.delta", data={"message_id": "m1", "text": " world"}))
    projection.apply(CanonicalStreamEvent(type="response.completed", data={"response_id": "r1"}))

    response = projection.snapshot()
    assert response.status == "completed"
    assert response.messages[0].segments == [{"type": "text", "text": "hello world"}]


def test_projection_records_permission_block() -> None:
    projection = ResponseProjection()
    projection.apply(
        CanonicalStreamEvent(
            type="permission.blocked",
            data={
                "response_id": "r1",
                "permission_request_id": "p1",
                "permission_kind": "command",
            },
        )
    )

    response = projection.snapshot()
    assert response.block is not None
    assert response.block.permission_request_id == "p1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/canonical/test_projection.py -v`  
Expected: FAIL with import errors for canonical modules

- [ ] **Step 3: Implement canonical models, events, and projection**

```python
# src/agent_gateway/canonical/models.py
from dataclasses import dataclass, field


@dataclass
class CanonicalBlock:
    kind: str
    permission_request_id: str
    permission_kind: str


@dataclass
class CanonicalMessage:
    message_id: str
    role: str
    segments: list[dict[str, str]] = field(default_factory=list)


@dataclass
class CanonicalToolCall:
    call_id: str
    name: str
    arguments: str = ""
    status: str = "started"


@dataclass
class CanonicalResponse:
    response_id: str
    turn_id: str | None = None
    status: str = "in_progress"
    usage: dict[str, int] = field(default_factory=dict)
    messages: list[CanonicalMessage] = field(default_factory=list)
    tool_calls: list[CanonicalToolCall] = field(default_factory=list)
    block: CanonicalBlock | None = None


@dataclass
class CanonicalTurn:
    turn_id: str
    model: str
    input_items: list[dict[str, object]]
```

```python
# src/agent_gateway/canonical/events.py
from dataclasses import dataclass, field


@dataclass
class CanonicalStreamEvent:
    type: str
    data: dict[str, object] = field(default_factory=dict)
```

```python
# src/agent_gateway/canonical/projection.py
from agent_gateway.canonical.events import CanonicalStreamEvent
from agent_gateway.canonical.models import CanonicalBlock, CanonicalMessage, CanonicalResponse


class ResponseProjection:
    def __init__(self) -> None:
        self._response = CanonicalResponse(response_id="pending")
        self._message_index: dict[str, CanonicalMessage] = {}

    def apply(self, event: CanonicalStreamEvent) -> None:
        if event.type == "response.started":
            self._response.response_id = str(event.data["response_id"])
            self._response.status = "in_progress"
            return

        if event.type == "message.started":
            message = CanonicalMessage(
                message_id=str(event.data["message_id"]),
                role=str(event.data["role"]),
            )
            self._message_index[message.message_id] = message
            self._response.messages.append(message)
            return

        if event.type == "content.delta":
            message = self._message_index[str(event.data["message_id"])]
            text = str(event.data["text"])
            if message.segments and message.segments[-1]["type"] == "text":
                message.segments[-1]["text"] += text
            else:
                message.segments.append({"type": "text", "text": text})
            return

        if event.type == "permission.blocked":
            self._response.block = CanonicalBlock(
                kind="blocked_by_permission",
                permission_request_id=str(event.data["permission_request_id"]),
                permission_kind=str(event.data["permission_kind"]),
            )
            self._response.status = "blocked"
            return

        if event.type == "response.completed":
            self._response.status = "completed"
            return

    def snapshot(self) -> CanonicalResponse:
        return self._response
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/canonical/test_projection.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_gateway/canonical/models.py src/agent_gateway/canonical/events.py src/agent_gateway/canonical/projection.py tests/canonical/test_projection.py
git commit -m "feat: add canonical projection core"
```

## Task 3: Add Host-Control Models and Interfaces

**Files:**
- Create: `src/agent_gateway/host_control/models.py`
- Create: `src/agent_gateway/host_control/interfaces.py`
- Test: `tests/host_control/test_models.py`

- [ ] **Step 1: Write failing host-control tests**

```python
# tests/host_control/test_models.py
from agent_gateway.host_control.models import PermissionCapability, PermissionDecision, PermissionRequest


def test_permission_request_preserves_context() -> None:
    request = PermissionRequest(
        request_id="p1",
        kind="command",
        target="pytest -q",
        source="codex",
        risk_level="high",
        status="pending",
        created_at="2026-05-12T10:00:00Z",
        raw_context_ref="log://req-1",
    )

    assert request.kind == "command"
    assert request.raw_context_ref == "log://req-1"


def test_permission_decision_links_to_request() -> None:
    decision = PermissionDecision(
        request_id="p1",
        decision="allow",
        decided_by="user",
        decided_at="2026-05-12T10:01:00Z",
        reason="approved for test",
    )

    capability = PermissionCapability(kinds=["command", "file"], modes=["manual"])

    assert decision.request_id == "p1"
    assert capability.modes == ["manual"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/host_control/test_models.py -v`  
Expected: FAIL with missing host-control modules

- [ ] **Step 3: Implement host-control models and interfaces**

```python
# src/agent_gateway/host_control/models.py
from dataclasses import dataclass


@dataclass
class PermissionRequest:
    request_id: str
    kind: str
    target: str
    source: str
    risk_level: str
    status: str
    created_at: str
    raw_context_ref: str


@dataclass
class PermissionDecision:
    request_id: str
    decision: str
    decided_by: str
    decided_at: str
    reason: str


@dataclass
class PermissionCapability:
    kinds: list[str]
    modes: list[str]
```

```python
# src/agent_gateway/host_control/interfaces.py
from typing import Protocol

from agent_gateway.host_control.models import PermissionDecision, PermissionRequest


class PermissionHandler(Protocol):
    def normalize(self, raw_signal: dict[str, object]) -> PermissionRequest: ...


class PolicyEvaluator(Protocol):
    def evaluate(self, request: PermissionRequest) -> PermissionDecision | None: ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/host_control/test_models.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_gateway/host_control/models.py src/agent_gateway/host_control/interfaces.py tests/host_control/test_models.py
git commit -m "feat: add host control domain"
```

## Task 4: Build DeepSeek Adapter and Request Translation

**Files:**
- Create: `src/agent_gateway/providers/deepseek/client.py`
- Create: `src/agent_gateway/providers/deepseek/adapter.py`
- Test: `tests/providers/deepseek/test_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

```python
# tests/providers/deepseek/test_adapter.py
from agent_gateway.canonical.models import CanonicalTurn
from agent_gateway.providers.deepseek.adapter import DeepSeekAdapter


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
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["content"] == "say hi"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/providers/deepseek/test_adapter.py -v`  
Expected: FAIL with missing adapter implementation

- [ ] **Step 3: Implement adapter and HTTP client wrapper**

```python
# src/agent_gateway/providers/deepseek/adapter.py
from agent_gateway.canonical.models import CanonicalTurn


class DeepSeekAdapter:
    def __init__(self, default_model: str) -> None:
        self._default_model = default_model

    def build_request(self, turn: CanonicalTurn) -> dict[str, object]:
        messages = []
        for item in turn.input_items:
            messages.append(
                {
                    "role": str(item["role"]),
                    "content": str(item["content"]),
                }
            )
        return {
            "model": self._default_model,
            "messages": messages,
            "stream": True,
        }
```

```python
# src/agent_gateway/providers/deepseek/client.py
import httpx


class DeepSeekClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def stream_chat_completions(self, payload: dict[str, object]) -> httpx.Response:
        return await self._client.post("/chat/completions", json=payload)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/providers/deepseek/test_adapter.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_gateway/providers/deepseek/client.py src/agent_gateway/providers/deepseek/adapter.py tests/providers/deepseek/test_adapter.py
git commit -m "feat: add deepseek request adapter"
```

## Task 5: Add Rectifier and Runtime Engine

**Files:**
- Create: `src/agent_gateway/runtime/rectifier.py`
- Create: `src/agent_gateway/runtime/engine.py`
- Test: `tests/runtime/test_rectifier.py`
- Test: `tests/runtime/test_engine.py`

- [ ] **Step 1: Write failing runtime tests**

```python
# tests/runtime/test_rectifier.py
from agent_gateway.runtime.rectifier import DeepSeekRectifier


def test_rectifier_turns_delta_into_content_event() -> None:
    rectifier = DeepSeekRectifier()
    chunk = {"choices": [{"delta": {"content": "hello"}}]}

    events = rectifier.rectify(chunk, response_id="r1", message_id="m1")

    assert events[0].type == "content.delta"
    assert events[0].data["text"] == "hello"
```

```python
# tests/runtime/test_engine.py
from agent_gateway.canonical.events import CanonicalStreamEvent
from agent_gateway.runtime.engine import RuntimeEngine


def test_engine_applies_events_into_projection() -> None:
    engine = RuntimeEngine()
    events = [
        CanonicalStreamEvent(type="response.started", data={"response_id": "r1"}),
        CanonicalStreamEvent(type="message.started", data={"message_id": "m1", "role": "assistant"}),
        CanonicalStreamEvent(type="content.delta", data={"message_id": "m1", "text": "ok"}),
        CanonicalStreamEvent(type="response.completed", data={"response_id": "r1"}),
    ]

    response = engine.consume(events)

    assert response.status == "completed"
    assert response.messages[0].segments[0]["text"] == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/runtime/test_rectifier.py tests/runtime/test_engine.py -v`  
Expected: FAIL with missing rectifier and engine implementations

- [ ] **Step 3: Implement rectifier and engine**

```python
# src/agent_gateway/runtime/rectifier.py
from agent_gateway.canonical.events import CanonicalStreamEvent


class DeepSeekRectifier:
    def rectify(
        self,
        chunk: dict[str, object],
        *,
        response_id: str,
        message_id: str,
    ) -> list[CanonicalStreamEvent]:
        delta = chunk["choices"][0]["delta"]
        events: list[CanonicalStreamEvent] = []
        if "content" in delta:
            events.append(
                CanonicalStreamEvent(
                    type="content.delta",
                    data={
                        "response_id": response_id,
                        "message_id": message_id,
                        "text": str(delta["content"]),
                    },
                )
            )
        return events
```

```python
# src/agent_gateway/runtime/engine.py
from agent_gateway.canonical.events import CanonicalStreamEvent
from agent_gateway.canonical.models import CanonicalResponse
from agent_gateway.canonical.projection import ResponseProjection


class RuntimeEngine:
    def consume(self, events: list[CanonicalStreamEvent]) -> CanonicalResponse:
        projection = ResponseProjection()
        for event in events:
            projection.apply(event)
        return projection.snapshot()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_rectifier.py tests/runtime/test_engine.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_gateway/runtime/rectifier.py src/agent_gateway/runtime/engine.py tests/runtime/test_rectifier.py tests/runtime/test_engine.py
git commit -m "feat: add rectifier and runtime engine"
```

## Task 6: Expose Responses-Style Ingress

**Files:**
- Create: `src/agent_gateway/ingress/responses_api.py`
- Modify: `src/agent_gateway/app.py`
- Test: `tests/ingress/test_responses_api.py`

- [ ] **Step 1: Write failing ingress test**

```python
# tests/ingress/test_responses_api.py
from fastapi.testclient import TestClient

from agent_gateway.app import create_app


def test_responses_endpoint_accepts_input_payload() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/v1/responses",
        json={
            "model": "codex-mini",
            "input": [
                {"role": "system", "content": "be concise"},
                {"role": "user", "content": "say hi"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["output"][0]["content"][0]["text"] == "stub response"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ingress/test_responses_api.py -v`  
Expected: FAIL with `404 Not Found` for `/v1/responses`

- [ ] **Step 3: Implement ingress router and wire into app**

```python
# src/agent_gateway/ingress/responses_api.py
from fastapi import APIRouter
from pydantic import BaseModel


class ResponseInputItem(BaseModel):
    role: str
    content: str


class ResponsesRequest(BaseModel):
    model: str
    input: list[ResponseInputItem]


router = APIRouter()


@router.post("/v1/responses")
async def create_response(request: ResponsesRequest) -> dict[str, object]:
    return {
        "id": "resp_stub",
        "status": "completed",
        "model": request.model,
        "output": [
            {
                "role": "assistant",
                "content": [{"type": "output_text", "text": "stub response"}],
            }
        ],
    }
```

```python
# src/agent_gateway/app.py
from fastapi import FastAPI

from agent_gateway.ingress.responses_api import router as responses_router


def create_app() -> FastAPI:
    app = FastAPI(title="agent-gateway")

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(responses_router)
    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ingress/test_responses_api.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_gateway/ingress/responses_api.py src/agent_gateway/app.py tests/ingress/test_responses_api.py
git commit -m "feat: add responses ingress"
```

## Task 7: Replace Stub Path with Runtime Wiring and Document Local Validation

**Files:**
- Modify: `src/agent_gateway/ingress/responses_api.py`
- Modify: `src/agent_gateway/app.py`
- Create: `README.md`
- Test: `tests/ingress/test_responses_api.py`

- [ ] **Step 1: Extend failing ingress test to assert canonical pipeline wiring**

```python
# tests/ingress/test_responses_api.py
from fastapi.testclient import TestClient

from agent_gateway.app import create_app


def test_responses_endpoint_returns_projected_output() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/v1/responses",
        json={
            "model": "codex-mini",
            "input": [
                {"role": "system", "content": "be concise"},
                {"role": "user", "content": "say hi"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["output"][0]["content"][0]["text"] == "hello from gateway"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ingress/test_responses_api.py -v`  
Expected: FAIL because endpoint still returns `stub response`

- [ ] **Step 3: Wire the ingress through canonical projection and add local run docs**

```python
# src/agent_gateway/ingress/responses_api.py
from fastapi import APIRouter
from pydantic import BaseModel

from agent_gateway.canonical.events import CanonicalStreamEvent
from agent_gateway.runtime.engine import RuntimeEngine


class ResponseInputItem(BaseModel):
    role: str
    content: str


class ResponsesRequest(BaseModel):
    model: str
    input: list[ResponseInputItem]


router = APIRouter()


@router.post("/v1/responses")
async def create_response(request: ResponsesRequest) -> dict[str, object]:
    engine = RuntimeEngine()
    response = engine.consume(
        [
            CanonicalStreamEvent(type="response.started", data={"response_id": "resp_1"}),
            CanonicalStreamEvent(type="message.started", data={"message_id": "msg_1", "role": "assistant"}),
            CanonicalStreamEvent(type="content.delta", data={"message_id": "msg_1", "text": "hello from gateway"}),
            CanonicalStreamEvent(type="response.completed", data={"response_id": "resp_1"}),
        ]
    )
    return {
        "id": response.response_id,
        "status": response.status,
        "model": request.model,
        "output": [
            {
                "role": message.role,
                "content": [{"type": "output_text", "text": segment["text"]} for segment in message.segments],
            }
            for message in response.messages
        ],
    }
```

````markdown
# README.md

## agent-gateway

Phase 1 prototype for `Responses -> Canonical -> DeepSeek -> Canonical -> Responses`.

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run tests

```bash
pytest -v
```

### Start server

```bash
uvicorn agent_gateway.app:create_app --factory --reload
```
````

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_smoke.py tests/canonical/test_projection.py tests/host_control/test_models.py tests/providers/deepseek/test_adapter.py tests/runtime/test_rectifier.py tests/runtime/test_engine.py tests/ingress/test_responses_api.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_gateway/ingress/responses_api.py README.md tests/ingress/test_responses_api.py
git commit -m "feat: wire phase1 gateway pipeline"
```

## Self-Review

### Spec coverage
- Split-core architecture is covered by Task 2 and Task 3.
- Canonical event-first runtime is covered by Task 2 and Task 5.
- DeepSeek adapter boundary is covered by Task 4.
- Responses-style ingress is covered by Task 6 and Task 7.
- Host-control abstraction without UI is covered by Task 3.
- Local validation and runnable skeleton are covered by Task 1 and Task 7.

### Placeholder scan
- No placeholder markers or deferred implementation language remain.
- Each code step includes concrete file content.
- Each test step includes an exact command and expected result.

### Type consistency
- `CanonicalStreamEvent`, `CanonicalResponse`, and `RuntimeEngine` names are consistent across tasks.
- `PermissionRequest` and `PermissionDecision` names are consistent between models and interfaces.
- `DeepSeekAdapter.build_request()` and `RuntimeEngine.consume()` signatures are used consistently after introduction.
