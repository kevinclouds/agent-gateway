# 进度日志

## 会话：2026-05-15（btw 分支 — Codex 集成调试）

### 三层适配器重构 + Codex 集成 bug 修复
- **状态：** in_progress（未提交的 4 个文件变更待 commit）
- 执行的操作：
  - **三层适配器体系**：新增 `BaseProviderAdapter` ABC、`AdapterRegistry`（三层解析：model → type → default），将 `DeepSeekAdapter` 拆分为 `DeepSeekBaseAdapter / DeepSeekStandardAdapter / DeepSeekThinkingAdapter`
  - **config.py**：`thinking_models` 替换为 `model_type_map`（JSON，默认将 `deepseek-reasoner / DeepSeek-V4-Flash / DeepSeek-V4-Pro` 映射到 `deepseek-thinking` 类型），新增 `MODEL_TYPE_MAP` 环境变量支持
  - **ReasoningStore 持久化**：新增 `runtime/reasoning_store.py`，`dict` 子类，写入时自动持久化到 `.reasoning_store.json`（默认路径），网关重启后 `reasoning_content` 不再丢失
  - **并行 function_call 修复**：连续多个 `function_call` item 现合并为一个 assistant 消息的多个 `tool_calls`，修复 DeepSeek "insufficient tool messages" 400 错误
  - **null content 修复**：DeepSeek thinking 模型在推理阶段会发送 `"content": null`，`str(None) = "None"` 被当成文字输出（导致 Codex 看到 `NoneNoneNone...`）；将 `if "content" in delta:` 改为 `if delta.get("content"):` 跳过 null 和空字符串
  - **未知模型回退**：registry `_resolve_model` 改为对 model_map 和 model_type_map 均未命中的模型名回退 `default_model`，而非透传；修复 `gpt-5.4-mini` 被原样发给 DeepSeek 的问题
  - **reasoning_content 自动降级**：当 thinking 模型返回 400 "reasoning_content must be passed back" 时（store 中无对应 call_id），自动用 `deepseek-chat`（`DeepSeekStandardAdapter`）重试，而非直接返回 502
  - 提交 `9e0a411`（三层适配器 + 持久化 + 并行 tool call 修复）
  - 当前待提交：app.py（reasoning fallback）、registry.py（未知模型回退）、rectifier.py（null content）、tests/runtime/test_rectifier.py（新增 null content 测试）
- 创建/修改的文件：
  - `src/agent_gateway/providers/base.py`（新增）
  - `src/agent_gateway/providers/registry.py`（新增 + 修改）
  - `src/agent_gateway/providers/deepseek/adapter.py`（重写，3 类）
  - `src/agent_gateway/runtime/reasoning_store.py`（新增）
  - `src/agent_gateway/runtime/rectifier.py`（null content 修复）
  - `src/agent_gateway/config.py`（model_type_map 替换 thinking_models）
  - `src/agent_gateway/app.py`（registry 接入 + reasoning fallback）
  - `tests/providers/deepseek/test_adapter.py`（更新）
  - `tests/runtime/test_rectifier.py`（新增 null content 测试）

---

## 会话：2026-05-15

### 端口与 README 收尾
- **状态：** complete
- 执行的操作：
  - 将默认端口从 `8000` 改为 `9321`（`cli.py` 第 8 行）
  - 重构 README 快速启动章节为编号步骤（安装依赖 → 配置 → 启动 → 验证）
  - 将环境变量说明改为表格，所有端口引用统一为 `9321`
  - 提交 `ba97d5a` 并推送到 `origin/master`
- 创建/修改的文件：
  - `src/agent_gateway/cli.py`（端口默认值 8000→9321）
  - `README.md`（启动章节重构 + 端口统一）

---

## 会话：2026-05-13

### 阶段 5：真实 DeepSeek upstream smoke
- **状态：** complete
- 执行的操作：
  - 重新读取 `task_plan.md`、`progress.md`、`findings.md`，恢复阶段 5 上下文
  - 检查 `.venv/bin/agent-gateway` 可执行入口，确认可本地启动
  - 尝试在沙箱内绑定本地端口，发现 `uvicorn` bind `127.0.0.1:8765` 返回 `operation not permitted`
  - 提权启动本地 gateway 服务：`AG_HOST=127.0.0.1 AG_PORT=8765 .venv/bin/agent-gateway`
  - 调用 `GET /healthz`，确认服务返回 `200 {"status":"ok"}`
  - 使用真实 DeepSeek key 对 `POST /v1/responses` 发起非流式请求，prompt 为 `Reply with exactly: gateway-ok`
  - 非流式返回 `200`，响应正文输出 `gateway-ok`
  - 使用真实 DeepSeek key 对 `POST /v1/responses` 发起流式请求，prompt 为 `Reply with exactly: stream-ok`
  - 流式成功输出 `response.created`、`response.output_item.added`、`response.output_text.delta`、`response.output_item.done`、`response.completed`
  - 流式完成态正文为 `stream-ok`
  - 停止本地服务，确认服务进程正常 shutdown
- 创建/修改的文件：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### 阶段 6：补充 README
- **状态：** in_progress
- 执行的操作：
  - 读取 `config.py`、`cli.py`、`pyproject.toml`，确认启动方式、环境变量和脚本入口
  - 新增 `README.md`
  - 写入项目定位、Phase 1 范围、安装与启动方式、鉴权方式、非流式/流式 curl 示例、tool loop 输入示例、测试命令和当前限制
  - 按用户要求将 `README.md` 改为中文主导、术语保留英文的 mixed 风格
- 创建/修改的文件：
  - `README.md`

### 阶段 5：补齐 Responses 兼容测试与 tool loop 语义
- **状态：** in_progress
- 执行的操作：
  - 重新读取规划文件，确认当前主线为“阶段 5：测试与验证”
  - 直接运行裸 `pytest`，发现当前 shell 未激活项目环境，随后切换为 `.venv/bin/pytest`
  - 确认现有 17 项测试全部通过，但测试面缺少 `/v1/responses` 的真实集成覆盖
  - 为 `CanonicalTurn` 增加 `tools` / `tool_choice` 字段
  - 为 `ResponseProjection` 增加 `tool_call.started`、`tool_call.arguments.delta`、`tool_call.completed` 投影能力
  - 为 `DeepSeekRectifier` 增加上游 `tool_calls` delta 整流与 `finish_reason=tool_calls` 完成态处理
  - 为 `DeepSeekAdapter` 增加 `function_call` / `function_call_output` 输入映射，以及 `tools` / `tool_choice` 透传
  - 重写 `/v1/responses` 返回序列化：非流式输出改为 `Responses` 风格 `output` 数组
  - 新增 SSE 事件翻译层：对外输出 `response.created`、`response.output_item.added`、`response.output_text.delta`、`response.function_call_arguments.delta`、`response.completed` 等事件
  - 新增 API 集成测试，覆盖非流式文本、流式文本、tool call 输出、function_call_output 回合续接
  - 新增/补充单元测试，覆盖 rectifier tool call 整流、projection tool call 聚合、adapter tool loop 映射
- 创建/修改的文件：
  - `src/agent_gateway/app.py`
  - `src/agent_gateway/canonical/models.py`
  - `src/agent_gateway/canonical/projection.py`
  - `src/agent_gateway/providers/deepseek/adapter.py`
  - `src/agent_gateway/runtime/rectifier.py`
  - `tests/ingress/test_responses_api.py`
  - `tests/canonical/test_projection.py`
  - `tests/providers/deepseek/test_adapter.py`
  - `tests/runtime/test_rectifier.py`

### 阶段 4：修复 Internal Server Error + Git 初始化
- **状态：** complete
- 执行的操作：
  - 用户请求：`x-api-key` 改为客户端请求时携带而非服务端预配
  - 用户测试 curl 时遇到 Internal Server Error
  - 发现 `_handle_create_response` 缩进错误（定义在模块级而非 `create_app` 内），导致 `create_app()` 返回 None
  - 添加全局异常捕获，网络/上游失败时返回 502 及具体错误
  - 修复 TestClient lifespan 兼容性（smoke test 改用 `with TestClient(app) as client`）
  - 创建 `.gitignore`
  - `git init` + 首次 commit + 推送到 GitHub
  - 验证全部 17 项测试通过
- 创建/修改的文件：
  - `src/agent_gateway/app.py`（重写，修复缩进 + 错误处理 + per-request API key）
  - `tests/test_smoke.py`（TestClient lifespan 兼容）
  - `.gitignore`（新增）

## 会话：2026-05-12

### 阶段 1：需求与定位收敛
- **状态：** complete
- **开始时间：** 2026-05-12
- 执行的操作：
  - 从“Codex 专用 bridge”逐步收敛并修正为“通用多协议网关”定位
  - 确定第一版只接 `DeepSeek` 上游
  - 确定 `Codex` 为首个重点验证客户端
  - 确定不重复实现 CC-Switch 已有能力
  - 确定与 CC-Switch 采用手动接入方式
  - 确定技术栈使用 Python
  - 确定模型解析策略为 `model_map + default_model`
- 创建/修改的文件：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### 阶段 2：系统设计初步拆解
- **状态：** complete
- 执行的操作：
  - 讨论系统边界，并改为参考 CC-Switch 的分层设计
  - 确定关注 `ingress / rectifier / runtime / provider adapter`
  - 讨论内部 Canonical Model 的必要性
  - 识别下一步重点应是细化 Canonical Model 和流式状态机
  - 重新读取规划文件，恢复本轮上下文
  - 检查项目目录，确认当前仓库仅包含规划文件，尚无实现骨架
  - 检查 `professor-synapse` agent 索引，确认暂无协议网关方向的现成专家
  - 记录新增产品想法：统一拦截 Agent 权限授权请求，并通过通知和统一授权页面承接
  - 记录视觉沟通偏好：不打开浏览器，若需要视觉稿则生成本地 HTML 文件
  - 收敛统一授权首版边界：只覆盖 `agent-gateway` 内可拦截的授权请求
  - 收敛统一授权控制面抽象：先定义可扩展审批策略接口，暂不锁死同步或异步模式
  - 收敛统一授权拦截分层：正式规范以 `runtime / rectifier` 为主，adapter 只上报原始信号
  - 纠正“统一授权”的建模对象：聚焦 agent 宿主级权限事件，而不是普通 tool call
  - 收敛统一授权可行性边界：核心按网关内可裁决权限设计，外部 agent 授权仅作为旁路监听扩展
  - 调整范围：第一版不实现通知中心、统一授权 UI 或桌面宠物交互层
  - 保留扩展方向：仅沉淀宿主权限事件、通知和审批能力所需的抽象接口
  - 结合 `vibeisland.app` 截图提炼通知卡片信息结构，补充来源、状态、预览、跳转和动作槽位等字段要求
  - 将 `vibeisland.app` 交互细节降级为未来 `Agent-Gateway App` 参考，而非首版交付范围
  - 收敛扩展接口范围：第一版保留权限事件的数据模型与处理接口，不保留通知桥接出口
  - 收敛权限分层：`Canonical` 只保留最小权限阻塞占位，详细权限语义归 `host-control` 子域
  - 收敛最小权限阻塞占位符：状态 + 请求 ID + 权限类别
  - 确认总体架构方向：采用 `Split-core`，由 `Canonical` 和并行的 `host-control` 子域组成
  - 确认流式状态机方向：事件日志为真相源，响应投影为消费视图
  - 确认 `Canonical Model` 最小对象集合，覆盖响应、回合、消息、工具调用、流事件和阻塞点
  - 确认 `host-control` 最小子域，包含权限请求、决策、能力声明和两类处理接口
  - 输出正式设计文档到 `docs/superpowers/specs/2026-05-12-agent-gateway-design.md`
  - 完成 spec 自检，确认无 `TBD/TODO`、无明显截断，范围与已确认设计一致
- 创建/修改的文件：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
  - `docs/superpowers/specs/2026-05-12-agent-gateway-design.md`

### 阶段 3：等待用户审阅设计文档
- **状态：** in_progress
- 执行的操作：
  - 将当前会话停在 spec 审阅门，不进入实现规划
  - 根据用户要求将 spec 改为中英双语版本
  - 根据用户进一步要求，将 spec 从双语对照改为中文主导、术语保留英文的 mixed 风格
  - 用户确认 spec 可继续，切换到 `writing-plans` 生成 implementation plan
  - 输出 implementation plan 到 `docs/superpowers/plans/2026-05-12-agent-gateway-phase1-implementation.md`
  - 完成 implementation plan 自检，修复 README 示例代码块嵌套问题，并确认无占位词残留
  - 选择 `Subagent-Driven` 执行 implementation plan
  - Task 1 初次执行时代码已落盘，但因本地未安装 `fastapi` 导致测试阻塞
  - 识别本地使用 `uv` 管理 Python 依赖，并将虚拟环境安装到项目 `.venv/`，缓存写入 `.uv-cache/`
  - 通过提权运行 `UV_CACHE_DIR=.uv-cache uv sync --extra dev` 完成依赖安装
  - 重新运行 `source .venv/bin/activate && pytest tests/test_smoke.py -v`，确认 Task 1 smoke test 通过
  - 完成 Task 1 spec review，确认实现符合计划要求
  - 完成 Task 1 code-quality review，修复默认假 API key 与过宽 dev 依赖范围问题
  - 再次运行 Task 1 code-quality review，确认 Task 1 完整通过
  - 完成 Task 2 implementer 执行，新增 canonical models / events / projection，并通过 `tests/canonical/test_projection.py`
  - 完成 Task 2 spec review，确认实现与计划一致
  - 完成 Task 2 code-quality review，修复 permission.blocked 未同步 response_id、snapshot 暴露可变内部状态、测试覆盖不足等问题
  - 再次运行 Task 2 code-quality review，确认 Task 2 完整通过
  - 完成 Task 3 implementer 执行，新增 host-control models / interfaces，并通过 `tests/host_control/test_models.py`
  - 完成 Task 3 spec review，确认实现与计划一致
  - 完成 Task 3 code-quality review，修复 stringly-typed 状态、可变 value objects、测试覆盖过弱等问题
  - 再次运行 Task 3 code-quality review，确认 Task 3 完整通过
  - 完成 Task 4 implementer 执行，新增 DeepSeek adapter / client，并通过 `tests/providers/deepseek/test_adapter.py`
  - 完成 Task 4 spec review，确认实现与计划一致
  - 完成 Task 4 code-quality review，修复伪流式传输、缺少 client 生命周期管理、测试覆盖不足等问题
  - 再次运行 Task 4 code-quality review，确认 Task 4 完整通过
  - 完成 Task 5 implementer 执行，新增 rectifier / runtime engine，并通过 `tests/runtime/test_rectifier.py` 与 `tests/runtime/test_engine.py`
  - 完成 Task 5 spec review，确认实现与计划一致
  - 完成 Task 5 code-quality review，修复 rectifier 输出与 projection 前提不一致、测试未覆盖真实整流链路等问题
  - 再次运行 Task 5 code-quality review，确认 Task 5 完整通过
- 创建/修改的文件：
  - `task_plan.md`
  - `progress.md`
  - `docs/superpowers/specs/2026-05-12-agent-gateway-design.md`
  - `docs/superpowers/plans/2026-05-12-agent-gateway-phase1-implementation.md`
  - `pyproject.toml`
  - `src/agent_gateway/__init__.py`
  - `src/agent_gateway/config.py`
  - `src/agent_gateway/app.py`
  - `tests/test_smoke.py`
  - `src/agent_gateway/canonical/models.py`
  - `src/agent_gateway/canonical/events.py`
  - `src/agent_gateway/canonical/projection.py`
  - `tests/canonical/test_projection.py`
  - `src/agent_gateway/host_control/models.py`
  - `src/agent_gateway/host_control/interfaces.py`
  - `tests/host_control/test_models.py`
  - `src/agent_gateway/providers/deepseek/client.py`
  - `src/agent_gateway/providers/deepseek/adapter.py`
  - `tests/providers/deepseek/test_adapter.py`
  - `src/agent_gateway/runtime/rectifier.py`
  - `src/agent_gateway/runtime/engine.py`
  - `tests/runtime/test_rectifier.py`
  - `tests/runtime/test_engine.py`

### 阶段 4：补齐 CLI 入口 + 网关路由
- **状态：** complete
- 执行的操作：
  - `config.py`: 新增 `from_env()` 类方法，从环境变量加载配置
  - `app.py`: 重写为完整网关应用
    - 添加 lifespan 管理 `DeepSeekClient` 生命周期
    - 添加 `POST /v1/responses` 端点，支持 `stream: true/false`
    - 非流式模式：收集事件后通过 `RuntimeEngine.consume()` 投影返回 JSON
    - 流式模式：通过 `text/event-stream` SSE 实时推送 canonical events
    - 未设置 API key 时返回 400 错误
  - `cli.py`: 新增 `agent-gateway` CLI 入口，支持 `AG_HOST`/`AG_PORT` 环境变量
  - `pyproject.toml`: 添加 `[project.scripts]` 入口
  - 验证全部 17 项已有测试通过，新增 endpoint 行为正常
- 创建/修改的文件：
  - `src/agent_gateway/config.py` (修改)
  - `src/agent_gateway/app.py` (重写)
  - `src/agent_gateway/cli.py` (新增)
  - `pyproject.toml` (修改)
  - `progress.md` (更新)

## 测试结果
| 测试 | 输入 | 预期结果 | 实际结果 | 状态 |
|------|------|---------|---------|------|
| 规划文件初始化 | 新建工作目录 | 三个规划文件完成落盘并可恢复上下文 | 已创建 `task_plan.md`、`findings.md`、`progress.md` | 通过 |
| 设计文档自检 | `2026-05-12-agent-gateway-design.md` | 无占位符、无明显截断、与确认设计一致 | 通过关键词扫描和人工检查，未发现 `TBD/TODO` 或结构缺口 | 通过 |
| healthz 端点 | GET /healthz | 返回 200 `{"status":"ok"}` | 状态码 200 | 通过 |
| 无 API key 返回 400 | POST /v1/responses 无 KEY | 返回 400 错误 | 状态码 400 | 通过 |
| CLI 入口导入 | `from agent_gateway.cli import main` | 无错误 | 导入成功 | 通过 |
| 全部已有测试 | pytest | 17 through | 17 passed | 通过 |
| Internal Server Error 修复 | curl POST /v1/responses 假 key | 返回 502 带错误详情而非 500 | 状态码 502 | 通过 |
| API 集成测试（定向） | `.venv/bin/pytest tests/ingress/test_responses_api.py tests/runtime/test_rectifier.py tests/canonical/test_projection.py tests/providers/deepseek/test_adapter.py -q` | 新增 Responses / tool loop 相关测试通过 | 16 passed | 通过 |
| 全量回归 | `.venv/bin/pytest -q` | 所有测试通过 | 24 passed | 通过 |
| 真实 upstream 非流式 smoke | `POST /v1/responses` with real key | 返回固定文本 `gateway-ok` | 状态码 200，正文 `gateway-ok` | 通过 |
| 真实 upstream 流式 smoke | `POST /v1/responses` with real key and `stream=true` | 返回完整 `response.*` SSE 并以 `stream-ok` 完成 | 收到 `response.completed`，最终文本 `stream-ok` | 通过 |

## 错误日志
| 时间戳 | 错误 | 尝试次数 | 解决方案 |
|--------|------|---------|---------|
| 2026-05-12 | 当前目录不是 git 仓库 | 1 | 暂不依赖 git，先记录规划文件 |
| 2026-05-12 | 无法将设计文档提交到 git | 1 | 先写入本地 spec 文件，待进入 git worktree 后再补提交 |
| 2026-05-13 | curl POST /v1/responses 返回 Internal Server Error | 1 | 修复 `_handle_create_response` 缩进 + 添加全局异常捕获返回 502 |
| 2026-05-13 | 沙箱内本地 bind `127.0.0.1:8765` 失败 | 1 | 提权启动本地服务 |
| 2026-05-13 | 沙箱内 Python localhost 请求失败 `Operation not permitted` | 1 | 改用提权的本地 `curl` 做真实 smoke |

## 五问重启检查
| 问题 | 答案 |
|------|------|
| 我在哪里？ | 已完成真实 DeepSeek upstream smoke；Codex 客户端端到端验证仍未做 |
| 我要去哪里？ | 若要完成阶段 5 的最后一项，需要接真实 Codex 客户端做 agent loop smoke |
| 目标是什么？ | 规划一个本地运行的通用多协议网关，第一版只接 DeepSeek，上游重点验证客户端为 Codex |
| 我学到了什么？ | 见 findings.md，当前已明确 Split-core、Canonical 事件模型、host-control 子域和首版范围边界 |
| 我做了什么？ | 完成所有实现 Task、补齐 CLI + 网关路由、修复 Internal Server Error、补齐本地集成测试，并完成真实 DeepSeek upstream smoke |

---
*每个阶段完成后或遇到错误时更新此文件*
