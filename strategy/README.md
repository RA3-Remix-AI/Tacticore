# 策略层：合同、持续记忆与任务决策

`strategy/` 管理指挥实例绑定、可见局势合同、模型策略校验、持续记忆、任务生命周期及本地接续。当前真实模型请求由 `agent_runtime/` 的 **PydanticAI 默认后端**管理，游戏会话与执行由 `integration/` 及原生模块管理。新 React + Tauri 桌面仍是离线预览。

Windows 接收本批变更后，先按 [Windows 同步与策略验证](../docs/windows-validation.md) 安装同一 Python 环境并跑完整回归。模型层改动范围见 [迁移交接](../docs/agent-runtime/migration-handoff.md)。原有算法和合同不应为接入 SDK 而复制到框架或 UI。

## 模块职责

| 模块 | 当前职责 |
| --- | --- |
| `engine.py` | 严格快照 / policy 合同、绑定、时效、计划稳定性、暂停、停止、失败接续及审计 |
| `battle_agent.py`、`missions.py` | 有界持续记忆、摘要与增量、任务与使命的状态接续和执行反馈 |
| `http_adapter.py` | 连接库 / Windows DPAPI 读取、原 prompt 与诊断；原手写网络传输仅显式 legacy 使用 |
| `model_backend.py` | 加载本仓库 `agent_runtime/src` 的 bootstrap，转交唯一 factory |
| `../agent_runtime/` | 默认 PydanticAI 的受限模型调用、预算、严格原始响应检查、取消与遥测 |
| `service.py` | 文件快照模型服务，只产出经过验证的策略与建议，不包含游戏执行器 |
| `../integration/battle_host.py` | 真实会话、视野、能力证据、资源与任务执行宿主 |
| `demo.py`、`fixtures/` | 使用合成数据和适配器的纯离线 Engine 演示 |

默认工厂在三个模型 CLI 中统一使用：`service.py`、`integration/battle_host.py`、`integration/probe_strategy.py`。`--model-backend legacy` 是明确对照或回退，缺依赖不会自动换回旧传输。`service.py --http-retries 1` 仅允许与 legacy 配合。

## 安装与离线验证

核心 Engine 合成演示仍只需标准库；完整模型服务与回归需要 Python 3.12+ 和锁定的 PydanticAI 依赖。不要把“核心演示标准库可跑”理解成整个项目无需安装框架。

从仓库根目录执行，下面 `$tacticorePython` 必须是已经通过安装脚本准备好的完整解释器路径；环境建立步骤见 [Windows 指南](../docs/windows-validation.md)。

```powershell
$env:PYTHONPATH = (Join-Path $PWD 'agent_runtime\src') + ';' + (Join-Path $PWD 'strategy')
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYDANTIC_AI_NO_BANNER = '1'
$env:TACTICORE_REQUIRE_FRAMEWORK = '1'
& $tacticorePython -m unittest discover -s agent_runtime/tests -v
& $tacticorePython -m unittest discover -s strategy -p 'test*.py' -v
& $tacticorePython .\strategy\demo.py --output .\strategy\runtime-offline
```

demo 不读取连接库、访问外部模型或游戏，只写独立离线输出；不要用 `--write-fixtures` 覆盖仓库已有样例来替代新验收。框架 demo 见 [运行时 README](../agent_runtime/README.md)。

本侧基线：macOS 运行时 28 项通过；strategy 168 项中 166 通过、2 项 Windows DPAPI 跳过。Windows 须实际执行这两项，记录实际测试总数与跳过原因，后续新增用例不受历史数量约束。历史实机记录见 [视野与战术验收](../acceptance/vision-tactics-status.md)，不作为本次 PydanticAI 或新 GUI 已实战通过的证据。

## 实例绑定与模型接口

`Binding(session_id, player_id, commander_id, commander_name, connection_id)` 固定一个实例。会话及稳定 ID 使用标准 UUID，`player_id` 为 0 至 15；改显示名不改变身份。新对局、读档导致游戏时间倒退等情况需要重新建立匹配会话，不能让旧结果继续派单。

`engine.observe(snapshot)` 接收结构化局势；同一快照编号不得冲突，编号与游戏时间不能倒退。`await engine.decide(snapshot, adapter)` 继续消费异步 `context → dict policy` 合同。PydanticAI 仅替代模型请求组装，原 parser 与 Engine 仍审定结果；`BattleAgent` 的 summary / delta / pending decisions 继续承接游戏记忆，不启用 SDK 的第二份长期历史。

模型层没有游戏工具、任意命令或执行权。回应必须绑定原请求的 session、player、commander 与 snapshot；响应后重新检查当前事实、目标能力和时效。取消不能变为成功，迟到结果不能复活已停止的实例。

## 局势与策略合同

完整离线样例见 `fixtures/snapshot.json` 与 `fixtures/policy.json`。实际可接受字段与约束以当前 `engine.py` 为准；策略与执行扩展必须保留对应测试。

- 局势包含会话、玩家、游戏时间、暂停与来源、有限资源 / 生产 / 己方职责摘要、注册区域及敌方目击记录。电力 `null` 表示未知；最后目击与当前可见必须区分。可信视野过滤由真实采集端负责，Engine 不能仅凭输入声明证明迷雾公平性。
- policy 表达有限姿态、生产方向、资源比例、注册区域、有效期及已声明的战术能力。`native_baseline` 是有限本地接续意图，不授予新的执行能力。
- 资源比例与模型目标属于意图，实际资金、前置、供电、生产设施、控制权与能力证据由宿主和执行器重新核验。游戏初始资金、Agent 总生产支出上限和资源保留底线是不同概念。
- 严格 JSON 解析与 Engine 合同校验共同拒绝重复键、未知字段、NaN / Infinity、无效绑定与超限内容：parser 处理 JSON、重复键、非有限数值与大小，Engine 继续核验字段和绑定；不让 Pydantic 自动纠正替代原合同。
- 模型异常优先接续仍有效的旧计划，不延长其到期时间；失效后有限回退。暂停、停止、重大事件、资源预留与持续任务不能因换框架而被绕过。

持续任务具体接口与生命周期见 [BATTLE_AGENT.md](BATTLE_AGENT.md)。新 GUI 的五档倾向、阶段打法和视频电台编排尚在 [Feature 路线图](../docs/desktop-next/feature-roadmap.md)，不是已支持的额外引擎参数。

## 文件服务与执行边界

`service.py` 已提供真实模型调用、只读 `--check-profile`、单次或持续文件快照处理及绑定停止。完整参数、schema v2 连接库、DPAPI、输出文件与费用边界见 [HTTP_SERVICE.md](HTTP_SERVICE.md)。使用真实连接启动服务可能联网计费；离线 demo 与测试不会。

默认连接库为 `%LOCALAPPDATA%/Tacticore/library.v2.json`，非 Windows 为 `~/.local/share/Tacticore/library.v2.json`，支持 `--library`。旧 WinForms 已删除；新 GUI 不写真实库或密钥，不自动迁移历史数据。不要把桌面的演示配置当成宿主配置。

Engine / 文件服务状态中的 `execution.enabled=false`、`dry_run=true` 与 `computer_verified=false` 表示该层没有独立证明游戏执行与玩家身份；不能据此反推整个项目没有真实宿主。真实控制另经 `integration/` 的可信绑定与证据链。

审计记录协调器允许的字段、枚举、快照及本地生成的 ID；凭据、原始模型正文与任意异常内容不得写入公开状态。UI 应消费脱敏摘要，不能直接解释任意日志文本为执行命令。新桌面接线合同见 [Windows 原生协议](../docs/desktop-next/windows-handoff.md)。
