# Agent Gateway 设计文档

Date: 2026-05-12  
Status: Draft approved in conversation, pending user review

## 1. 目标

设计一个本地运行的 `agent-gateway`，作为通用 multi-protocol gateway。

Phase 1 约束如下：
- Downstream interface 使用 `Responses`-style API
- Upstream provider 先只接 `DeepSeek chat/completions`
- Primary validation client 是 `Codex`
- 核心目标是稳定跑通 agent loop，而不只是 basic chat

## 2. 非目标

Phase 1 不包含以下内容：
- CC-Switch 的 provider management、routing UI、config panels、database integration
- 自动注册到 CC-Switch
- `Agent-Gateway App`
- desktop pet UI
- unified notification / approval UI
- 超出首个 `DeepSeek` adapter 的通用 multi-provider 支持

系统仍需为未来的 host permission handling 和 UI layer 保留 extension points。

## 3. 架构摘要

系统采用 `Split-core` 架构：

- `Canonical`：protocol execution semantics
- `host-control`：host permission control semantics

这两个 domain 被刻意分离。`Canonical` 专注于 turns、messages、events、tool calls 和 completion state；`host-control` 负责 permission requests、decisions、capabilities 和 policy interfaces。

两个 domain 通过一个 minimal blocking placeholder 连接：
- `blocked_by_permission`
- `permission_request_id`
- `permission_kind`

这样 runtime 可以显式表达“执行流被权限阻塞”，但不会把完整的 host-control semantics 污染到 protocol core。

## 4. High-Level Data Flow

Phase 1 的 request path 如下：

1. Client 向 gateway ingress 发送 `Responses`-style request
2. Ingress 将 request normalize 为 `CanonicalTurn` input
3. Runtime 基于 canonical state 和 adapter contract 执行
4. `DeepSeek` adapter 将 canonical request translate 为 `chat/completions`
5. Provider stream 被 rectified 成 `CanonicalStreamEvent`
6. `ResponseProjection` 将 event fold 成 canonical response view
7. Gateway 向 client 输出 `Responses`-compatible stream

概念上是：

`Responses -> Canonical -> DeepSeek -> Canonical -> Responses`

## 5. Canonical Runtime

### 5.1 职责

`Canonical` 是内部 standard semantic layer，它的作用是：
- 当前只支持一个 downstream protocol 时，也不把 provider semantics hard-code 到各处
- 通过 adapters 和 rectifiers 吸收未来 protocol variation
- 让 runtime logic 不依赖 `DeepSeek` 的 response shape

### 5.2 最小 Canonical Objects

Phase 1 的 canonical core 包含：

- `CanonicalResponse`
- `CanonicalTurn`
- `CanonicalMessage`
- `CanonicalToolCall`
- `CanonicalStreamEvent`
- `CanonicalBlock`

这些对象足以覆盖：
- request/response lifecycle
- streaming state progression
- tool loop execution
- minimal permission blocking

### 5.3 对象意图

`CanonicalResponse`
- top-level response container
- 包含 `response_id`、`turn_id`、`status`、`usage`

`CanonicalTurn`
- 一个 agent turn 的 execution lifecycle
- 统一挂接 input、output、tool activity、blocking 和 completion

`CanonicalMessage`
- normalized message unit
- 包含 `role` 和 `segments`

`CanonicalToolCall`
- normalized tool invocation
- 包含 `call_id`、`name`、`arguments`、`status`

`CanonicalStreamEvent`
- append-only source of truth，用于表达 streaming behavior

`CanonicalBlock`
- minimal execution block representation
- Phase 1 只要求覆盖 permission blocking

## 6. Streaming State Machine

### 6.1 Core Model

Phase 1 采用 dual-layer streaming model：

- `CanonicalStreamEvent` 是 source of truth
- `ResponseProjection` 是 consumer-facing folded view

Runtime 必须把 event log 视为 append-only；projection 是 derived 且 disposable 的 view。

### 6.2 Standard Event Shapes

Canonical event family 应覆盖：

- `response.started`
- `message.started`
- `content.delta`
- `reasoning.delta`
- `tool_call.started`
- `tool_call.arguments.delta`
- `tool_call.completed`
- `permission.blocked`
- `message.completed`
- `response.completed`
- `response.failed`

Exact naming 后续可以微调，但这些 semantics 必须存在。

### 6.3 为什么采用 Events First

该模型优先的原因：
- 更贴近 `Responses`-style streaming semantics
- 可以在不泄漏 provider-specific details 的前提下整流 `DeepSeek` delta stream
- 支持 replay、debugging、auditing 和 future sidecar features
- 能自然处理 partial tool calls 和 permission pauses

### 6.4 流中的 Permission Blocking

当 runtime 遇到 host permission boundary 时，stream 中记录：
- `blocked_by_permission`
- `permission_request_id`
- `permission_kind`

Stream 不承载完整 approval semantics；详细 permission handling 留在 `host-control`。

## 7. Host-Control Domain

### 7.1 目的

`host-control` 用于建模 host runtime permission semantics，例如：
- command execution approval
- file access approval
- network access approval
- privilege escalation approval

这些都不属于 ordinary model protocol semantics。

### 7.2 Phase 1 Data Models

`PermissionRequest`
- `request_id`
- `kind`
- `target`
- `source`
- `risk_level`
- `status`
- `created_at`
- `raw_context_ref`

`PermissionDecision`
- `request_id`
- `decision`
- `decided_by`
- `decided_at`
- `reason`

`PermissionCapability`
- 声明系统支持哪些 permission categories 和 decision modes

### 7.3 Phase 1 Interfaces

`PermissionHandler`
- 消费 raw host permission signals
- 产出 normalized `PermissionRequest`

`PolicyEvaluator`
- 评估 request 应如何处理
- Phase 1 可以只返回 no-op 或 unsupported，但 interface 本身必须存在

### 7.4 Scope Boundary

Phase 1 只保留：
- data models
- processing interfaces

Phase 1 不实现：
- notification sinks
- approval UI
- action bridges
- desktop pet interactions

## 8. Adapter 与 Rectifier 边界

### 8.1 Provider Adapter

`DeepSeek` adapter 负责：
- 将 canonical outbound request translate 成 provider payload
- 读取 provider deltas
- 在可能的情况下上报 raw permission-related host signals

Adapter 不应拥有 unified approval policy。

### 8.2 Runtime / Rectifier

`runtime / rectifier` 是 normalized execution semantics 的正式判定点。

它负责：
- 把 provider deltas 转成 canonical stream events
- 维护 event ordering guarantees
- 插入 canonical permission blocking markers
- 保留足够 context，以便未来接入 approval flow 后继续执行

## 9. Phase 1 Scope

Phase 1 应交付：

- gateway runtime 的 Python project skeleton
- `Responses`-style ingress
- canonical runtime 和 rectifier
- 首个 `DeepSeek chat/completions` adapter
- stable Codex agent-loop validation
- non-streaming、streaming、tool calls、tool outputs 的 tests

Phase 1 不应扩展到 app-shell 或 notification product work。

## 10. Validation Criteria

Phase 1 的成功标准：

- Codex 能稳定通过该 gateway 跑通 agent loop
- provider-specific stream deltas 能完整 rectified 成 canonical events
- gateway 能为 tool loop 保留足够 semantic fidelity
- 即使暂时没有 UI，runtime 仍能表达 permission boundaries
- 架构足够干净，便于未来增加 providers 和 host-control UI

## 11. Open Follow-Up Work

在这份 design 被接受后，下一步 planning 应明确：

- Python package layout
- ingress、runtime、rectifier、adapter、host-control 的 module boundaries
- config file structure
- startup 和 local run flow
- test strategy 和 fixtures
