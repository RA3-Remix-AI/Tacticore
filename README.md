# 弈核 Tacticore

弈核是独立的 Agent 指挥官程序，探索让通用智能模型观察战况、持续记忆、形成计划并与玩家配合。目前适配《红色警戒 3》，以局内独立指挥官身份参与战局。游戏与 Mod 的适配、指挥官角色、模型连接分别维护，项目名称不绑定 Remix。

当前处于早期开发阶段。Windows 侧继续迭代策略、模型交互与实机验证；新桌面负责配置、观察和交互体验。宣传网站、游戏 Mod 与本仓库分开维护。

## 当前工程状态

| 部分 | 当前状态 |
| --- | --- |
| 决策模型层 | `agent_runtime/` 使用 PydanticAI 2.61.0，三个模型 CLI 默认选择 `pydantic`；`legacy` 仅为显式回退 |
| 战局宿主与策略 | 已有会话绑定、己方视野、持续记忆、任务与受控执行链；新模型后端仍需 Windows 和真实服务商复验 |
| 桌面 | 唯一桌面工程为 `desktop-ui/` React + Tauri 2；六个工作区已提供本机备战、指挥官工坊、电台素材管理与离线演练，真实宿主接线待实现 |
| 旧客户端 | 原 `desktop/` WinForms 工程的 15 个源码、脚本与说明文件已删除，不再维护或恢复其构建入口 |
| 角色通讯 | 局内指挥官与右上角电台入口已存在；新桌面已实现本地视频 / 音频 / 字幕素材库与事件演练，真实局内事件同步待接 |
| 配置体验 | 备战计划保存 / 导出、四类打法预设、五维五档倾向、行为预览和素材试听已实现；游戏读回与宿主应用待接 |

历史整场记录说明链路曾运行至结算，但不证明本次 PydanticAI 后端、新桌面或所有战术效果已通过。当前能力与失败记录见 [视野与战术验收](acceptance/vision-tactics-status.md) 和 [阶段状态](acceptance/stage-report.md)。

## 桌面界面预览

以下截图来自 2026-10-25 的本机浏览器开发预览，与 Tauri 桌面使用同一套 React 界面。图中展示的是本机配置和离线功能；真实 Windows 游戏宿主尚未接线，不能据截图认定已完成实战接入。

**战前备战室**：选择阵营、指挥官关系与开局资金计划，分别管理生产额度和资源保留底线，保存或导出下一局方案。

![弈核桌面战前备战室：阵营、资金与指挥官配置](docs/images/desktop/preparation.jpg)

<details>
<summary>展开指挥官工坊与战场电台截图</summary>

**指挥官工坊**：四种打法预设、五维五档倾向与即时行为说明；本机偏好草案尚未下发真实模型。

![弈核桌面指挥官工坊：打法预设和五档倾向](docs/images/desktop/commander-workshop.jpg)

**战场电台**：按指挥官管理本机视频、音频和字幕素材，试听场景通讯，调整频率、音量与字幕模式；局内事件触发待接入。

![弈核桌面战场电台：素材预览和通讯偏好](docs/images/desktop/radio.jpg)

</details>

## 开发 Feature 计划

| 状态 | Feature | 当前交付或后续目标 |
| --- | --- | --- |
| 已完成 · 本机 | 战前备战室 | 阵营、地图、初始资金计划、队友 / 对手关系、独立资源限制，支持保存、恢复与导出 |
| 已完成 · 本机 | 指挥官工坊 | 四种产品预设、五维五档调节、三类行为预览、人格与偏好适配草案 |
| 已完成 · 本机 | 战场电台 | 视频 / 音频 / 字幕素材库、试听与六类场景演练、频率、冷却、优先级、中断和过期处理 |
| 下一步 · P0 | Windows 真实宿主接线 | 新 GUI 的档案、检查、启动、观察与停止确认闭环，完成目标环境验收 |
| 下一步 · P0 | 真实配置与电台事件 | 游戏设置读回、受支持的资金设置、倾向下发与应用回执，连接局内事件和电台播放 |
| 后续 · P1 | 看懂并配合指挥官 | 可追溯的当前意图与执行回执、战中伴随小窗、受支持的快速配合意图 |
| 后续 · P1 | 战后复盘与运行状态 | 关键时刻、任务结果和通讯回看，模型延迟、用量与故障解释 |
| 后续 · P2 | 多 Agent 搭档与对抗 | 在会话、视野、资源与执行隔离验证后，支持多指挥官分工和同场对照 |

本机保存不等于游戏生效；初始资金、Agent 生产支出上限和资源保留底线分别管理。详细交互、依赖和验收条件见 [Feature 路线图](docs/desktop-next/feature-roadmap.md)，Windows 侧按 [验证交接](docs/windows-validation.md) 推进。

## 先从哪里开始

- **Windows 策略验证与本批合并**：[Windows 验证交接](docs/windows-validation.md)，按环境、离线回归、模型联调、受控实战的顺序推进。
- **查看本侧改动**：[Unreleased 改动说明](CHANGELOG.md)，包含默认后端变化、旧桌面移除和配置目录变化。
- **运行新桌面**：[桌面开发说明](desktop-ui/README.md)。
- **继续产品开发**：[Feature 路线图](docs/desktop-next/feature-roadmap.md) 与 [桌面接入合同](docs/desktop-next/windows-handoff.md)。
- **查找模块与验收文档**：[文档索引](docs/README.md)。

## 架构与职责

真实决策链由宿主采集并过滤战况，`BattleAgent` 维护记忆和任务，模型运行层请求策略，严格解析器与 `StrategyEngine` 校验结果，执行宿主再依据当前会话与已验证能力派发任务。模型生成策略不等于获得执行权；执行回执反馈给后续决策。

PydanticAI 管理一次有界的模型请求、provider 与取消，不另建一份游戏策略 schema，不接管原有游戏记忆或执行器。当前框架、SDK 和 HTTP 自动重试均为零。具体合同与取舍见 [决策层 ADR](docs/agent-runtime/0001-pydantic-decision-runtime.md)。

| 目录 | 职责 |
| --- | --- |
| `agent_runtime/` | 默认模型后端、统一 factory、版本锁、安装脚本与离线框架测试 |
| `strategy/` | 策略合同、严格解析、决策稳定性、持续记忆、任务生命周期与文件快照服务 |
| `integration/` | 游戏会话绑定、状态采集、生产和战术调度、宿主控制与执行回执 |
| `desktop-ui/` | React + Tauri 六工作区、本机配置与媒体存储、离线演练、前端状态契约；真实原生适配器待实现 |
| `visibility/` | 己方视角可见敌情、最后目击与视野过滤 |
| `production/`、`tactical/` | 受控生产、移动、交战、撤退与对应能力证据核验 |
| `native-ai/` | 局内指挥官登记、原生接口研究与适配辅助 |
| `benchmark/` | 场景、统计与性格对照实验 |
| `acceptance/`、`reports/` | 带范围与来源的验收记录和历史证据；部分本机产物不随源码分发 |
| `docs/` | 当前交接、架构决策、体验方案、验证说明与历史文档归档 |

## 本地开发

### Windows 决策运行时

需要 Python 3.12+。以下命令从仓库根目录运行，明确使用同一虚拟环境解释器安装、测试和后续启动宿主：

```powershell
py -3.12 -m venv .venv
$tacticorePython = (Resolve-Path '.\.venv\Scripts\python.exe').Path
.\agent_runtime\Install-Windows.ps1 -Python $tacticorePython
& $tacticorePython -m unittest discover -s strategy -v
```

安装脚本包含新运行时离线测试和 `pip check`，不会启动游戏或请求真实模型。后续运行 `strategy/service.py`、`integration/battle_host.py`、`integration/probe_strategy.py` 时继续使用 `& $tacticorePython`；三者默认使用 PydanticAI，回退需显式传 `--model-backend legacy`。完整命令、失败处理和实战前置见 [Windows 验证交接](docs/windows-validation.md) 与 [运行时说明](agent_runtime/README.md)。

真实游戏开发另需正版《红色警戒 3》1.12 的 x86 环境、匹配的适配包与能力证据，以及原生桥接的 x86 C++ 工具链；打包相关辅助可能需要 RA3 SDK。根 `Build.ps1` 是原生桥接构建入口，不能代替桌面构建。部分实验脚本仍需按本机环境配置路径。

### 桌面离线预览

需要 Node.js 22.22+。在独立终端运行：

```powershell
Set-Location desktop-ui
npm ci
npm test
npm run dev
```

打开 `http://127.0.0.1:5174/`。演示不调用模型、不读游戏、不发送游戏命令，也不需要真实 API Key。`npm run build` 验证 TypeScript 与前端构建。

原生窗口另需 Rust 稳定工具链；Windows 需要 MSVC C++ 工具链与 WebView2，macOS 需要 Xcode Command Line Tools。进入 `desktop-ui/` 后运行 `npm run tauri -- dev` 或 `npm run tauri -- build --no-bundle`。原生窗口构建成功不代表真实游戏接入成功，详见 [桌面开发说明](desktop-ui/README.md)。

## 配置与数据

真实宿主默认读取 `%LOCALAPPDATA%/Tacticore/library.v2.json`；非 Windows 为 `~/.local/share/Tacticore/library.v2.json`。可用 `--library` 显式指定配置，不自动迁移旧目录。当前新 UI 的保存仅用于离线演示，不创建真实连接库或写入宿主凭据；真实配置格式和 Windows DPAPI 要求见 [模型服务说明](strategy/HTTP_SERVICE.md)。

游戏初始资金、Agent 生产总支出上限和资源保留底线是三个独立概念。当前 `--total-budget` 与 `--reserve` 不设置游戏初始资金。备战室可保存和导出本机计划；工坊可调整五档软偏好并查看人格与摘要映射，旧百分比演示权重已移除。这些本机配置尚未写入游戏或下发给策略宿主，实际生效仍须由 Windows 原生适配器应用并读回。详见 [Feature 路线图](docs/desktop-next/feature-roadmap.md)。

电台支持本地视频、音频和字幕通讯，素材与通讯偏好按指挥官保存在当前运行环境的 IndexedDB，不上传远端。单条媒体上限 32 MiB / 90 秒，每位指挥官最多 24 条自定义素材、媒体合计 128 MiB；内置示例字幕不计入条数。浏览器不同 origin（主机名、端口、协议）以及 Tauri 原生窗口的数据相互独立，不会自动共享素材，完整用法见 [桌面说明](desktop-ui/README.md)。

密钥、DPAPI 文件、本机连接配置、模型流量、运行锁、编译产物、下载工具链与 `node_modules/` 不提交。会话、源码、适配包、执行器或能力证据不满足时，宿主仍须拒绝执行；不能补造历史证据来使检查通过。

## 本批验证与下一步

本侧 macOS 决策层开发验证记录：运行时 28 项通过；strategy 回归 166 项通过、2 项 Windows DPAPI 测试跳过。本轮桌面测试、构建和交互检查以 [验证记录](docs/desktop-next/verification.md) 为准。**Windows 安装、DPAPI、真实网络取消、模型兼容性、游戏实战和新 GUI 接线仍待验证**。

本轮已实现备战室、指挥官工坊和战场电台的桌面本机功能。下一步优先完成真实宿主接线、游戏设置读回、偏好下发和局内电台事件，再扩展意图回执、伴随小窗、快速配合、战后复盘与多 Agent。初始资金写入、真实局内通讯和运行中修改策略仍需 Windows 原生适配器支持。

## 参考、借鉴与依赖工程

下表区分研究参考、实际技术依赖与素材来源。引用不表示上游项目、游戏厂商或 Remix 作者参与开发、授权合作或为弈核的能力背书；各项目及素材保留各自的权利与许可。

| 工程 / 来源 | 关系 | 在弈核中的具体用途 |
| --- | --- | --- |
| [Ra3-Copilot](https://github.com/ProbiusOfficial/Ra3-Copilot) | 接口研究参考与局部工具 / 数据复用 | 历史参考提交为 [`2d31f7c`](https://github.com/ProbiusOfficial/Ra3-Copilot/tree/2d31f7cc0ce47e257a5ecb95cc4f44a8b26f8015)。公开偏移、接口入口用于研究假设和结构命名；部分辅助脚本实际加载其 `sage_hash.py`、`battle_catalog.h` 或研究工具。未编译或加载整个上游修改器；局部复用范围见详细归属记录 |
| [MinHook](https://github.com/TsudaKageyu/minhook) | 实际原生组件依赖 | 多个原生构建脚本从 Ra3-Copilot 参考目录取用 MinHook 1.3.3 源码并编译到实验组件中；部分脚本复制其许可文件，构建和分发须保留相应声明 |
| [pySAGE / sage_apt](https://github.com/ClementJ18/pySAGE) | 实际离线解析工具依赖 | `native-ai/decompile_frontend.py` 导入 `sage_apt.aptfile`，用于前端 APT 的离线解析 / 转换；不代表弈核运行了其 viewer 或 server |
| [w64devkit](https://github.com/skeeto/w64devkit) | 实际构建工具链 | 用于 Windows x86 原生桥接与实验程序构建；历史使用的版本和下载哈希留存在开发记录，完整工具链不随本仓库分发 |
| [PydanticAI](https://github.com/pydantic/pydantic-ai) | 实际模型运行依赖 | 默认通过 `pydantic-ai-slim[openai]` 管理一次有界模型请求；当前固定版本为 2.61.0，策略合同、记忆与执行权仍由弈核模块负责 |
| [React](https://github.com/facebook/react)、[Vite](https://github.com/vitejs/vite)、[Tauri](https://github.com/tauri-apps/tauri) | 实际桌面技术依赖 | 分别用于界面组件、前端开发 / 构建和原生桌面外壳；实际版本以 `package-lock.json`、`Cargo.lock` 为准 |
| [Phosphor Icons](https://github.com/phosphor-icons/react) | 实际图标依赖与图标衍生 | 界面图标及 Circuitry 衍生应用图标；原 MIT 许可原文见 [桌面第三方说明](desktop-ui/THIRD_PARTY_NOTICES.md) |
| RA3 / Remix-Ai 宣传站的阵营参考素材 | 游戏主题与用户提供参考 | 备战室复用宣传站既有阵营图；它们不属于 Phosphor 的 MIT 许可范围，也不表示获得游戏或 Mod 的整体授权 |

游戏、SDK、RA3 阵营标识及相关资料的权利归 Electronic Arts 和相应权利人；Remix 原创 Mod 内容归对应作者与权利人。本仓库不包含游戏本体、第三方完整修改器或完整工具链。以上依赖各自的许可证不能解释为本仓库整体采用同一许可证。更完整的来源、使用范围和许可说明见 [参考与归属记录](docs/references-and-attributions.md)。

本项目仅用于学习、研究与交流，不开展商业化或盈利活动；此用途声明不改变第三方作品各自的权利归属。

## 历史开发记录

早期移动原型、私有机器环境、旧客户端与工具版本记录已迁至 [README 历史归档](docs/history/readme-development-records.md)。当前开发优先参考本页、带日期的验收记录和 Windows 交接，不按归档中的“后续优先级”执行。
