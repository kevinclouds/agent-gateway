# agent-gateway

`agent-gateway` 是一个本地运行的 protocol gateway，对下游暴露 `Responses`-style API，对上游转发到 `DeepSeek chat/completions`。

Phase 1 故意收窄范围，只做最小可用链路：

- 单一 upstream provider：`DeepSeek`
- 单一 downstream contract：`POST /v1/responses`
- local runtime only
- 重点保证 text streaming 和 tool loop compatibility

## 项目定位

`agent-gateway` 位于 agent client 和 DeepSeek 之间：

`Responses -> Canonical events -> DeepSeek chat/completions -> Canonical events -> Responses`

当前已支持：

- non-streaming `POST /v1/responses`
- streaming `POST /v1/responses`，返回 `text/event-stream`
- assistant text output projection
- 将 upstream `tool_calls` rectified 为 function-call output items
- 将 downstream `function_call` 和 `function_call_output` input items 映射回 DeepSeek message history

Phase 1 当前明确不做：

- multi-provider routing
- auth UI / approval center / desktop app shell
- automatic CC-Switch registration

## 环境要求

- Python `3.12+`
- 推荐使用 `uv` 管理环境和依赖

## 安装

```bash
uv sync --extra dev
```

## 快速启动

### 1. 安装依赖

```bash
uv sync --extra dev
```

### 2. 配置环境变量（可选）

可用变量及其默认值：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API 地址 |
| `DEFAULT_MODEL` | `deepseek-chat` | 上游使用的模型名 |
| `AG_HOST` | `0.0.0.0` | 监听地址 |
| `AG_PORT` | `9321` | 监听端口 |

### 3. 启动服务

```bash
.venv/bin/agent-gateway
```

或者用 `uvicorn` 手动启动：

```bash
.venv/bin/python -m uvicorn agent_gateway.app:create_app --factory --host 0.0.0.0 --port 9321
```

### 4. 验证服务

```bash
curl http://127.0.0.1:9321/healthz
```

预期返回：

```json
{"status":"ok"}
```

## 鉴权方式

Phase 1 不要求服务端预先配置 DeepSeek key。客户端需要在每次请求中携带 upstream key，支持两种方式：

- `x-api-key: <DEEPSEEK_KEY>`
- `Authorization: Bearer <DEEPSEEK_KEY>`

## API 示例

### 非流式文本请求

```bash
curl http://127.0.0.1:9321/v1/responses \
  -H 'Content-Type: application/json' \
  -H "x-api-key: $DEEPSEEK_API_KEY" \
  -d '{
    "model": "codex-mini",
    "input": [
      {"role": "user", "content": "Say hello in one short sentence."}
    ]
  }'
```

### 流式文本请求

```bash
curl http://127.0.0.1:9321/v1/responses \
  -N \
  -H 'Content-Type: application/json' \
  -H "x-api-key: $DEEPSEEK_API_KEY" \
  -d '{
    "model": "codex-mini",
    "stream": true,
    "input": [
      {"role": "user", "content": "Count from 1 to 3."}
    ]
  }'
```

当前 stream 会输出 `Responses`-style SSE events，包括：

- `response.created`
- `response.output_item.added`
- `response.output_text.delta`
- `response.function_call_arguments.delta`
- `response.output_item.done`
- `response.completed`

### Tool loop continuation

gateway 接受带历史 tool items 的 `input`，这样 client 可以继续下一轮 tool loop：

```json
{
  "model": "codex-mini",
  "tools": [
    {
      "type": "function",
      "name": "get_weather",
      "parameters": {
        "type": "object",
        "properties": {
          "city": {"type": "string"}
        },
        "required": ["city"]
      }
    }
  ],
  "tool_choice": "auto",
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [{"type": "input_text", "text": "What is the weather in Boston?"}]
    },
    {
      "type": "function_call",
      "call_id": "call_123",
      "name": "get_weather",
      "arguments": "{\"city\":\"Boston\"}"
    },
    {
      "type": "function_call_output",
      "call_id": "call_123",
      "output": "{\"temperature\":\"70F\"}"
    }
  ]
}
```

## 开发与测试

运行测试：

```bash
.venv/bin/pytest -q
```

当前本地测试覆盖：

- health check
- canonical projection
- DeepSeek adapter payload translation
- rectifier text/tool-call event shaping
- `/v1/responses` non-streaming behavior
- `/v1/responses` streaming SSE behavior
- tool-call output projection
- `function_call_output` loop continuation

## 集成说明

- 下游请求里的 `model` 目前会被接受，用来保持 downstream compatibility；但上游实际发送的模型仍使用 `DEFAULT_MODEL`
- 与 CC-Switch 的集成在 Phase 1 里仍然是 manual 接入
- 当前还差最后一项真实验证：用真实 Codex client 对这个 gateway 跑一轮 end-to-end smoke，而不只是本地 mocked integration tests
