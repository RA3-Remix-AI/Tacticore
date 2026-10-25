# ADR 0001：在单次策略调用边界采用 PydanticAI

- 日期：2026-10-25
- 状态：**默认代码路径已迁移；离线通过，真实模型与 Windows 游戏验收未完成**
- 范围：新增 `agent_runtime/`，三处模型入口统一组装；保留 Windows 正在迭代的策略算法、记忆、任务和执行模块。详见迁移交接文件。

## 问题与决定

现有 `ChatAdapter(context)` 已提供有限 JSON 策略接口；`StrategyEngine` 负责绑定、有效期、超时和回退，`BattleAgent` 负责持续记忆、任务、预留与回执。我们需要统一可维护的模型适配能力，但没有证据说明应当把这些状态机整体迁入第三方框架。

选择 **PydanticAI slim + OpenAI-compatible provider** 作为默认模型后端，只用一次 `Agent.run`。继续调用现有 prompt 和 JSON parser；输出不在框架内执行，也不通过框架反复纠正。三个真实模型入口共用 `create_backend`，默认 PydanticAI；legacy 仅显式回退。默认代码切换不是实战验收结论，仍需完成下述验证门槛。

## 四个候选的取舍

| 候选 | 与当前工程的匹配 | 本轮结论 |
| --- | --- | --- |
| PydanticAI | 模型抽象、显式输出方式、FunctionModel 离线测试适合单次 policy 调用；不要求业务使用持久 graph | 选为独立模型层；使用 slim 仍有 SDK、graph、OTel 等传递依赖，并不宣称依赖最少 |
| OpenAI Agents SDK | 能通过 Chat Completions 连接兼容模型，也有明确 tracing 开关；若未来主要做 handoff / tools 可重新评估 | 当前不需要第二套 agent loop / session；不因名称就假设只支持 OpenAI，也不因能接兼容端点就宣称真实 DeepSeek 已通过 |
| LangGraph | 适合长期、有状态、可恢复的工作流 | 当前使命生命周期已经在本地实现；另建 graph/checkpoint 会增加状态归属、恢复与幂等成本。本轮不迁移 |
| CrewAI Flows | 事件流、结构化状态和持久化适合工作流组织 | 对已有 BattleAgent/宿主状态机重叠较多；角色编排并不能直接证明游戏内多指挥官协同有效 |

以上是依据现有代码边界做的工程判断，不是通用框架排名或性能结论。官方依据：[PydanticAI 模型接口](https://pydantic.dev/docs/ai/models/openai/)、[离线测试](https://pydantic.dev/docs/ai/guides/testing/)、[输出形式](https://pydantic.dev/docs/ai/core-concepts/output/)、[OpenAI Agents SDK 模型](https://openai.github.io/openai-agents-python/models/)、[tracing](https://openai.github.io/openai-agents-python/tracing/)、[LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)、[CrewAI Flows](https://docs.crewai.com/en/concepts/flows)。

## 避免重复状态与隐式重试

框架只处理一次模型请求，不管理跨轮历史、任务、队伍预留、恢复或游戏命令。每次传入的 `working_memory` 都来自原 `BattleAgent`。本轮用真正的两轮 `BattleAgent.decide` 验证 hold、current_strategy 和 delta 继续工作。

框架与供应商 SDK 的重试会叠加，因此配置 `retries=0`、SDK `max_retries=0`、transport `retries=0`，并设置 `request_limit=1`。没有 tools/output-tools；模型即使提出任意工具也不会执行。错误返回固定本地代码，避免把供应商异常中的凭证或上下文带到上层日志。[官方重试说明](https://pydantic.dev/docs/ai/core-concepts/retries/)

我们刻意选文本输出再走旧严格 parser，而非另抄一份 Pydantic policy：当前 schema 会在 Windows 侧持续变化，双 schema 容易漂移；还需保留重复键等原始 JSON 错误。`ContractError` 不改名、不包装、不吞掉。字段/预算/对象/会话有效性由原引擎最终校验。这意味着目前没有利用框架全部结构化输出能力，是为兼容性作出的限制。

模型调用的单调时钟 deadline 与游戏快照时间分离。外部取消向下传播，迟到结果不会由适配器放行；宿主仍必须检查请求绑定与最新战况。不增加后台重试或“先返回、后台继续”的自建调度器。

## 可验证性与隐私

使用 `pydantic-ai-slim[openai]==2.61.0`，精确传递依赖记录在独立版本锁。28 项离线测试覆盖实际框架运行、旧 ChatAdapter 本机 HTTP、DeepSeek 模拟请求、JSON 错误、任务记忆、快照过期、取消、deadline、重放、超限、重定向、无工具、单次请求及关闭 instrumentation。

没有添加 tracing exporter，没有读取任何真实连接库或密钥。`agent.instrument=False` 覆盖框架全局默认；模拟测试中故意开启全局 instrumentation，确认本适配器仍不构造 instrumentation capability。底层 SDK 被其他外部监控全局注入的情况不在此保证内。[官方可观测性说明](https://pydantic.dev/docs/ai/integrations/logfire/)

DeepSeek 使用用户已选择的模型名，不在本模块推荐或替换模型。这里验证的是 Chat Completions 请求形状，不能代替真实端点验收。[官方 DeepSeek provider 文档](https://pydantic.dev/docs/ai/models/deepseek/)

## 迁移门槛

1. 在 Windows 上安装锁定依赖，复跑离线测试，验证与旧策略模块的当前契约一致。
2. 用固定脱敏 contexts/replies 比较原后端与实验后端：绑定错误、过期、无效目标、输入预算、取消与重复请求行为一致。避免把游戏能力证据降为 UI 状态。
3. 经授权才调用真实模型，验证所选 DeepSeek/自定义/OpenAI 模型的 JSON 模式、超时、429、网络故障、关闭退出和实际调用次数。特别验证 SDK DNS 取消与原解析子进程的差异。
4. 测量启动/内存/每轮延迟、依赖维护成本、有效策略比例和实际费用，不能从换框架推断更快、更强或更便宜。
5. 默认入口已经切换，但部署验收仍应先做不派发回放，再在受控单机对局做有限范围复验；实际派发走现有会话与能力门禁。`--model-backend legacy` 是显式回退，配置/依赖错误绝不自动切换。

当前未完成：真实服务商对比、Windows 打包、跨版本协议升级、跨电脑控制、游戏端到端复验。原 WinForms 客户端已删除；新桌面当前只提供离线演示，不启动真实宿主。宿主 CLI 使用新默认，回退使用显式参数。未来桌面接入必须由宿主重新验证会话、能力证据和当前代码，不能复用 UI 就绪状态。
