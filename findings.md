# 发现与决策

## 需求
- 做一个本地运行的协议网关工具，而不是仅供 Codex 使用的专用 bridge。
- 第一版上游只支持 `DeepSeek`。
- `Codex` 是首个重点验证客户端，目标是稳定跑通 agent loop。
- 不重复实现 `CC-Switch` 已有功能，例如 provider 管理、切换、UI、配置面板和路由管理。
- 与 `CC-Switch` 的关系是手动接入，而不是自动注册或改写其数据库。
- 新增方向：希望网关能感知各类 Agent 工具触发的权限授权请求，并统一通知用户。
- 后续希望补一个统一授权页面，交互形态偏“桌面宠物”，而不是传统控制台或设置页。
- 视觉沟通偏好：不使用浏览器 companion；如果需要视觉稿，优先生成本地 HTML 文档供用户自行打开查看。

## 研究发现
- `Codex` 当前依赖 `Responses` 风格接口与事件语义，而不是旧式 `chat/completions` 心智模型。
- `DeepSeek` 官方主接口是 `chat/completions`，因此需要协议翻译层。
- 类似工具的关键难点不是普通请求转发，而是流式事件、tool calls、tool outputs、reasoning 和完成态事件的整流。
- 参考 `CC-Switch` 的价值在于它的“中间人翻译 / rectifier”思路，而不是复制它的产品管理面。
- 当前仓库还没有代码、README 或设计文档，只有 `task_plan.md`、`findings.md`、`progress.md` 三个规划文件。
- `professor-synapse` 当前可直接调用的专家只有 `domain-researcher` 和 `skill-engineer`，没有现成的“协议网关 / LLM runtime”专家。
- 因此当前更适合先做架构主持与需求澄清；如果后续需要补充外部协议知识，再按需调用研究型专家。
- “统一授权”如果成立，本质上更像一个独立子系统：`authorization event interception + user notification + approval center`，它与基础协议翻译内核是强相关但不同层的问题。
- 用户这里说的“授权”特指 `Codex`、`Claude Code` 等 agent 宿主运行时里的权限批准事件，例如命令执行、文件访问、提权、网络访问等，不是模型协议层里的普通 tool call 确认。
- 这意味着统一授权更接近 `agent host control plane`，而不是单纯的 LLM protocol translation。
- 阶段 5 本地验证暴露出一个关键差距：此前 `/v1/responses` 端点虽然可返回文本，但返回体和 SSE 事件仍是内部 canonical 形状，不足以支撑真正的 `Responses`-style client loop。
- 要保住 tool loop fidelity，网关不只要把上游 `tool_calls` 整流成输出项，还必须接受下游回传的 `function_call` 与 `function_call_output` 输入项，并把它们映射回 `chat/completions` 的 assistant/tool message 序列。
- 在当前 Codex 沙箱里，本地 socket bind 和 localhost HTTP 请求默认都可能被限制；做真实 smoke 需要提权启动服务并通过提权请求本地端口。
- 一旦提权启动，本地 gateway 已能真实转发到 DeepSeek：非流式成功返回 `gateway-ok`，流式成功按 `response.created -> ... -> response.completed` 输出 `stream-ok`。

## 技术决策
| 决策 | 理由 |
|------|------|
| 使用 Python 实现第一版 | 协议验证、SSE 处理和 JSON 转换效率最高 |
| 采用通用多协议网关的外部定位 | 避免产品从一开始被 Codex 绑死 |
| 内部架构参考 CC-Switch 分层 | 保持 ingress、rectifier、runtime、provider adapter 的清晰边界 |
| 第一版仅暴露 `Responses` 风格下游接口 | 先满足最严格客户端 Codex 的验收需求 |
| 第一版只实现 `DeepSeek chat/completions` provider adapter | 控制范围，先把一条链路做硬 |
| 使用 `model_map + default_model` | 支持伪装模型名，同时在未命中时保持稳定性 |
| 统一授权第一版只覆盖 `agent-gateway` 自己可拦截的授权请求 | 明确边界，避免误把系统级或外部 Agent 内部授权纳入首版 |
| 授权处理模式先抽象为可扩展接口，不在首版锁死同步阻塞或异步挂起 | 为后续按风险等级、客户端能力和交互形态扩展保留空间 |
| 授权判定规范以 `runtime / rectifier` 为主，`provider adapter` 仅负责上报原始授权信号 | 保持统一审批语义，同时避免丢失 provider 特有上下文 |
| “统一授权”设计对象改为 agent 宿主级权限事件，而非普通模型 tool call | 与 Codex / Claude Code 的真实交互形态一致，避免抽象偏位 |
| 产品规范先按“网关内可控权限可真正裁决”设计，同时预留“外部 agent 旁路监听与通知”扩展层 | 先确保核心闭环真实可控，再兼容不可接管的外部宿主授权事件 |
| 第一版不实现通知中心、统一授权 UI 或桌面宠物交互层 | 当前先聚焦协议网关与运行时内核，避免 UI 子系统分散首版精力 |
| 仅保留宿主权限事件与后续通知/审批能力的抽象接口 | 让未来 `Agent-Gateway App + 桌面宠物` 可以接管，而不需要回头重构内核 |
| 第一版保留到“数据模型 + 处理接口”层，不保留通知/动作桥接出口 | 先为未来审批策略接入留钩子，同时避免过早把 UI/消息通道固化进内核 |
| 权限事件采用半进入策略：`Canonical` 只保留最小阻塞占位符，详细权限语义归入并行的 `host-control` 子域 | 避免宿主权限语义污染协议执行核心，同时保证 runtime 能显式处理权限阻塞点 |
| `Canonical` 中的最小权限阻塞占位符包含 `blocked_by_permission + permission_request_id + permission_kind` | 让 runtime 能关联具体权限请求并做最小分类，而不把详细宿主权限语义塞进核心模型 |
| `Canonical + host-control` 总体架构采用 `Split-core` 方案 | `Canonical` 保持协议执行核心，`host-control` 承载宿主权限控制，两者通过最小阻塞占位符和 request id 关联 |
| `Canonical runtime` 采用“双层流式模型”：`CanonicalStreamEvent` 为真相源，`ResponseProjection` 为消费视图 | 既兼容 `Responses` 事件语义，也能把 `DeepSeek chat/completions` 整流进统一状态机 |
| `Canonical Model` 最小对象集合包含 `CanonicalResponse / CanonicalTurn / CanonicalMessage / CanonicalToolCall / CanonicalStreamEvent / CanonicalBlock` | 覆盖首版协议翻译、流式状态机、tool loop 和最小权限阻塞表达，不把 UI 或策略细节塞进核心 |
| `host-control` 最小子域包含 `PermissionRequest / PermissionDecision / PermissionCapability / PermissionHandler / PolicyEvaluator` | 保留宿主权限语义与处理接口，为未来通知、审批和桌面宠物扩展预留稳定边界 |
| `/v1/responses` 对外返回 `Responses` 风格 JSON 与 `response.*` SSE 事件，而不是内部 canonical 事件 | 真实客户端消费的是 Responses 语义，内部 canonical 只应该存在于网关内部 |
| 下游输入标准化为三类：`message`、`function_call`、`function_call_output` | 这样才能把工具回合从 Responses 语义可靠映射到 DeepSeek `chat/completions` 上游 |
| 真实 upstream smoke 以本地最小 prompt 做双路径验证：非流式固定文本 + 流式固定文本 | 能最直接验证 gateway 的请求转发、响应整流和完成态事件是否正常 |

## 遇到的问题
| 问题 | 解决方案 |
|------|---------|
| 如果未来并入 CC-Switch 的概率低，Rust 成本偏高 | 调整为 Python 方案 |
| 如果项目不只服务 Codex，命名和内部模型不能使用 Codex 私有语义 | 改为通用网关定位，并采用 Canonical Model 思路 |

## 资源
- CC-Switch 的设计思路：ingress / rectifier / runtime / provider adapter
- 当前讨论出的内部方向：`Responses -> Canonical -> DeepSeek -> Canonical -> Responses`
- 当前新增讨论方向：`agent host permission interception -> notification -> unified approval UX`
- 当前项目目录：`/Users/kevin/KevinSpace/Code/Projects/agent-gateway`

## 视觉/浏览器发现
- 本次会话未使用浏览器进行视觉调研。
- 用户提供了 `vibeisland.app` 的截图，作为统一通知/授权体验的参考。
- 从截图看，通知中心展示的不是单一“弹窗标题”，而是“可一眼决策的工作卡片”，核心信息包括：
  - `agent / source`：例如 Claude、Codex、Gemini，以及宿主如 iTerm、Terminal、Ghostty
  - `task title / summary`：当前任务一句话摘要，例如 `fix auth bug`
  - `status`：进行中、等待授权、等待提问回答、已完成
  - `time context`：绝对时间或相对时间，例如 `Tue 1:15 PM`、`27m`
  - `action category`：如 Permission Request、Ask、Done、Monitor
  - `target object`：例如文件路径 `src/auth/middleware.ts`
  - `preview`：对用户做决定有帮助的局部上下文，例如代码 diff 片段、问题选项、执行摘要
  - `deeplink / jumpback`：回到原终端、tab 或 split pane 的入口
  - `candidate actions`：Monitor、Approve、Ask、Jump 等动作位
- 这些截图说明：即使第一版只做通知，事件模型也至少要支持“摘要 + 来源 + 风险类别 + 目标对象 + 预览 + 跳转入口 + 候选动作槽位”。
- 与此前的决定一致：首版动作可以只通知不执行，但动作槽位必须保留，否则未来桌面宠物无法平滑升级为快捷批准/拒绝界面。
- 但最新范围决定是：这些视觉与交互要求暂不进入第一版实现，只作为未来 `Agent-Gateway App` 的设计参考，当前仅沉淀为抽象事件接口的字段需求。

---
*每执行2次查看/浏览器/搜索操作后更新此文件*
*防止视觉信息丢失*
