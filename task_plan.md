# 任务计划：agent-gateway 协议网关设计

## 目标
在 `agent-gateway` 中规划一个本地运行的通用多协议网关，第一版只对接 `DeepSeek` 上游，并以 `Codex` 作为首个重点验证客户端。

## 当前阶段
阶段 5（本地 Responses 兼容验证完成，待真实 Codex 集成 smoke）

## 各阶段

### 阶段 1：需求与发现
- [x] 理解用户意图
- [x] 确定约束条件和需求
- [x] 将发现记录到 findings.md
- **状态：** complete

### 阶段 2：规划与结构
- [x] 确定产品定位与边界
- [x] 确定第一版技术栈与接入方式
- [x] 细化内部标准模型与流式状态机
- [x] 输出正式设计文档
- **状态：** complete

### 阶段 3：项目骨架
- [x] 确定 Python 包结构
- [x] 确定配置文件格式与启动方式
- [x] 初始化项目目录结构
- **状态：** complete

### 阶段 4：实现
- [x] 实现 `Responses` 下游接入层
- [x] 实现 Canonical runtime / rectifier
- [x] 实现 DeepSeek provider adapter
- [x] 实现流式与 tool loop 兼容
- [x] 补齐 CLI 入口 + 网关路由（config 加载、lifespan、/v1/responses 端点）
- **状态：** complete

### 阶段 5：测试与验证
- [x] 补充非流式、流式、tool calls、tool outputs 测试
- [x] 将测试结果记录到 progress.md
- [x] 接真实 Codex 客户端 smoke，修复集成 bug（见阶段 5b）
- [ ] 验证 Codex agent loop 可稳定跑通（tool loop 无 502）
- **状态：** in_progress

### 阶段 5b：Codex 集成 Bug 修复（btw 分支）
- [x] 三层适配器重构：BaseProviderAdapter / AdapterRegistry / DeepSeekStandard+Thinking
- [x] ReasoningStore 持久化（`.reasoning_store.json`）
- [x] 并行 function_call 合并为单条 assistant 消息
- [x] null content 修复（`"content": null` → 不再输出 "None"）
- [x] 未知模型名回退 default_model（修复 gpt-5.4-mini 透传 DeepSeek）
- [x] reasoning_content 降级重试（thinking 模型 400 → 自动用 deepseek-chat 重试）
- [ ] 提交当前 4 个待提交文件
- [ ] 验证 Codex agent loop 稳定
- **状态：** in_progress

### 阶段 6：交付
- [ ] 检查输出文件与说明文档
- [ ] 明确手动接入 CC-Switch 的方式
- [ ] 交付给用户
- **状态：** pending

## 关键问题
1. 内部 Canonical Model 需要覆盖哪些最小执行语义，才能既服务 Codex 又不被 Codex 绑死？
2. `Responses -> Canonical -> DeepSeek -> Canonical -> Responses` 的流式状态机应如何建模？
3. 第一版项目结构和配置格式如何设计，既清晰又不重复实现 CC-Switch 已有能力？

## 已做决策
| 决策 | 理由 |
|------|------|
| 项目名使用 `agent-gateway` | 比 `Codex bridge` 更符合长期定位 |
| 外部定位为通用多协议网关 | 工具不只给 Codex 使用 |
| 第一版上游只接 `DeepSeek` | 先收敛范围，降低实现复杂度 |
| `Codex` 是首个重点验证客户端 | 它对 `Responses` 语义要求最严格，适合做验收对象 |
| 技术栈使用 `Python` | 验证协议和流式状态机最快，不为低概率的 Rust 并入付出成本 |
| 不重复实现 CC-Switch 已有功能 | CC-Switch 已负责 provider 管理、切换、UI、路由管理 |
| 接入方式采用手动接入 CC-Switch | 保持 bridge 边界干净，不操作 CC-Switch 配置或数据库 |
| 模型解析采用 `model_map + default_model` | 既支持假模型名映射，也能在未命中时稳定回退 |
| 未命中模型映射时回退 `default_model` | 比严格报错更稳，更适合首版实际使用 |
| 成功标准是 Codex 稳定跑通 agent loop | 第一版目标是可用性，而不是只跑通基本对话 |
| 系统设计参考 CC-Switch 的分层 | 重点借鉴 ingress / rectifier / runtime / provider adapter 思路 |

## 遇到的错误
| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
| 当前目录不是 git 仓库 | 1 | 暂不依赖 git，先记录规划文件 |
| 无法将设计文档提交到 git | 1 | 先将 spec 落盘到 `docs/superpowers/specs/`，等待用户审阅；若后续进入 git worktree 再补提交 |
| DeepSeek 400: reasoning_content must be passed back | 多次 | 新增 ReasoningStore 持久化；对 store 无记录情况自动用 deepseek-chat 降级重试 |
| DeepSeek 400: insufficient tool messages | 1 | 将连续 function_call items 合并为单条 assistant 消息的多个 tool_calls |
| Codex 输出 NoneNoneNone... | 1 | thinking 模型推理阶段 `"content": null`，`str(None)="None"` 被作为文字输出；改为 `if delta.get("content"):` 跳过 null |
| DeepSeek 400: unsupported model name gpt-5.4-mini | 1 | registry 对未命中 model_map 和 model_type_map 的模型名回退 default_model |
| CC-Switch 本地代理 404 | 1 | CC-Switch proxy 不支持 /chat/completions；恢复 DEEPSEEK_BASE_URL=https://api.deepseek.com |

## 备注
- 不要把 CC-Switch 的 provider 管理、切换和配置面板重新做一遍。
- `Agent-Gateway App / 桌面宠物 / 统一通知授权 UI` 暂不纳入第一版实现，只保留抽象扩展接口。
- 正式设计文档已写入 `docs/superpowers/specs/2026-05-12-agent-gateway-design.md`，当前等待用户审阅。
- implementation plan 已写入 `docs/superpowers/plans/2026-05-12-agent-gateway-phase1-implementation.md`，当前等待选择执行方式。
- 本地已补齐 Responses 兼容测试：非流式 JSON 输出、SSE 事件流、tool call 输出、function_call_output 回合续接。
- 已完成一轮真实 DeepSeek upstream smoke：本地服务可启动，非流式请求返回 `gateway-ok`，流式请求完整返回 `stream-ok` 及 `response.completed`。
- 尚未接真实 Codex 客户端做一轮端到端 smoke；当前“Codex agent loop”结论来自本地模拟的 Responses/tool loop 集成测试。
