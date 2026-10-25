# Windows 同步与策略验证指南

更新：2026-10-25。适用本批尚未发布的工程变更。本文是 Windows 侧接收本侧提交后的主入口，先离线验证，再单独验证真实模型、游戏执行与新桌面接线。命令均在仓库根目录运行，另有说明的除外。

## 接手顺序

1. 阅读 [README](../README.md) 和 [CHANGELOG](../CHANGELOG.md)，确认本批架构、删除和未完成项。
2. 按本指南合并、安装同一解释器并跑离线回归；先处理失败和意外跳过。
3. 阅读 [PydanticAI ADR](agent-runtime/0001-pydantic-decision-runtime.md) 与 [桌面接线合同](desktop-next/windows-handoff.md)，按职责继续开发。
4. 持续在 `strategy/` 迭代算法与记忆，在统一 factory 组装模型；不复制策略 schema 到 SDK 或 UI。
5. 顺序验证真实模型、网络取消、受控原语和完整对局，保留每个阶段的新证据。
6. 新 GUI 接线独立验收；不恢复已删除的旧桌面，也不把离线界面当实机控制端。

## 先统一工程方向

- **弈核 Tacticore** 是独立 Agent 指挥程序；RA3 是当前游戏适配对象，Remix-Ai 宣传站与 Mod 另行维护。
- `agent_runtime/` 的唯一 factory 管理模型请求。`strategy/service.py`、`integration/battle_host.py`、`integration/probe_strategy.py` 默认使用 PydanticAI；`--model-backend legacy` 是显式对照或回退，不是自动降级。
- `strategy/` 继续管理严格策略合同、持续记忆、任务、快照时效与本地接续。PydanticAI 每次只处理一次受限模型请求，不接管游戏工具、长期记忆或执行授权。
- `integration/`、视野和执行端核验真实会话、玩家、能力证据与资源，最终决定是否执行。模型输出成功和 UI 就绪都不等于可以派单。
- 唯一桌面工程为 React + Tauri 的 `desktop-ui/`；原 `desktop/` 15 个文件已删除。新桌面目前是离线演示，尚无真实配置/凭据写入、游戏检查或宿主控制。不要恢复旧 WinForms 来承接新开发。

架构细节见 [模型层迁移](agent-runtime/migration-handoff.md)、[桌面接线合同](desktop-next/windows-handoff.md)。

## 1. 合并本侧变更，保留 Windows 算法进展

同步前先检查并保存 Windows 当前策略迭代，使用正常提交或独立分支；不要用目录覆盖、硬重置或清理未跟踪文件的方式合并。本指南不要求改写任何已有验收记录。

| 本侧范围 | 合并时的处理 |
| --- | --- |
| `agent_runtime/` | 新运行时、固定依赖、统一 factory、安装脚本与测试一起接收 |
| `strategy/model_backend.py` | 接收源码 bootstrap，确保实际加载本仓库模型层 |
| `strategy/service.py`、`integration/battle_host.py`、`integration/probe_strategy.py` | 合并模型组装、后端选项和缺依赖错误；保留 Windows 侧正在迭代的其他逻辑 |
| `strategy/test_http_adapter.py` | 保留标准 Chat Completions 测试 envelope 补全，不倒退成 SDK 不接受的极简假包 |
| `desktop-ui/` | 接收唯一新桌面、运行契约、离线演练和构建锁文件 |
| 原 `desktop/` | 保留删除结果；旧 GUI 的启动、构建与历史兼容入口不再作为产品路径 |
| 文档、`.gitignore` | 接收当前职责、配置目录与规划；缓存、凭据、编译产物继续不入库 |

本侧未改 `strategy/engine.py`、`battle_agent.py`、`missions.py`、`http_adapter.py` 的算法或合同，也未改原生执行代码。Windows 侧可继续迭代这些模块；发生交叉修改时逐段合并，不整文件替换。原 prompt 与严格 parser 经依赖注入继续生效，不另复制一套 policy schema。

源码与原始证据可能按字节哈希绑定，CRLF/LF 变化也会使哈希不同。先识别差异来源，不全局修改 Git 设置来“让检查通过”，不改历史证据结论或跳过哈希。保留原始证据字节；新版本需要重新取得证据时，建立新的验收目录并注明所用提交和构建。

## 2. 建立同一个 Python 环境

需要 Python 3.12+。推荐从本仓库根目录建立独立虚拟环境；`.venv/` 已忽略。已有可用环境可直接把 `$tacticorePython` 设为它的完整 `python.exe` 路径，不必再建环境。

```powershell
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw '创建 Python 环境失败' }
$tacticorePython = (Resolve-Path '.\.venv\Scripts\python.exe').Path
& $tacticorePython -c "import sys; assert sys.version_info >= (3, 12); print(sys.executable); print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw 'Python 版本不符合要求' }
.\agent_runtime\Install-Windows.ps1 -Python $tacticorePython
```

安装会从包源下载锁定依赖，运行 `pip check` 和离线框架测试；不会启动模型端点或游戏。脚本也支持自动发现 `py -3.12` / `python`，但之后必须使用它输出的同一解释器。不要把依赖装到 A 环境，再用 PATH 中的 B 环境启动宿主。安装脚本尚未在本侧 macOS 执行 Windows PowerShell 验证。

## 3. 先跑完整离线回归

安装完成后在同一个 PowerShell 窗口设置：

```powershell
$env:PYTHONPATH = (Join-Path $PWD 'agent_runtime\src') + ';' + (Join-Path $PWD 'strategy')
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYDANTIC_AI_NO_BANNER = '1'
$env:TACTICORE_REQUIRE_FRAMEWORK = '1'

& $tacticorePython -m unittest discover -s agent_runtime/tests -v
if ($LASTEXITCODE -ne 0) { throw 'PydanticAI 离线回归失败' }
& $tacticorePython -m unittest discover -s strategy -p 'test*.py' -v
if ($LASTEXITCODE -ne 0) { throw '策略层回归失败' }
& $tacticorePython -m tacticore_agent_runtime.demo
if ($LASTEXITCODE -ne 0) { throw '框架离线 demo 失败' }
```

这些测试使用内存模型、MockTransport 或进程内 localhost 假服务，不调用真实供应商。demo 应为 `status: accepted`、`execution_enabled: false`。`TACTICORE_REQUIRE_FRAMEWORK=1` 必须保留，否则缺依赖可能使框架用例跳过，不能算框架通过。

本侧基线为运行时 28 项通过，策略层 168 项中 166 通过、2 项 Windows DPAPI 跳过。Windows 应实际执行两个 DPAPI 用例：`Profiles.test_real_dpapi_fake_key_default_and_override` 和 `HttpTests.test_cli_reads_desktop_dpapi_and_writes_validated_dry_run_files`；后者名称保留历史称呼，不依赖已删除的 C# 客户端。它们仅使用临时假密钥。未来算法迭代会增加测试，不把 28 / 168 固定成通过门槛；记录实际总数、失败和跳过原因。

重点复核默认后端选择、显式 legacy、缺依赖固定 JSON 错误、无静默回退、两轮记忆接续、过时响应拒绝、停止取消，以及 completion 原始 `finish_reason == "stop"` 的严格验证。缺依赖测试已有隔离模拟，不必卸载工作环境依赖来测试。新默认不允许非零 HTTP 重试；legacy 的可终止 DNS 测试不能代替 PydanticAI SDK 的真实网络取消验证。

## 4. 准备真实档案，先做只读检查

默认连接库为 `%LOCALAPPDATA%/Tacticore/library.v2.json`，非 Windows 为 `~/.local/share/Tacticore/library.v2.json`，支持 `--library` 明确指定。没有旧目录回退或自动迁移。schema v2、稳定 UUID 与凭据合同见 [HTTP 服务说明](../strategy/HTTP_SERVICE.md)。远端凭据仍须通过当前 Windows 用户的 DPAPI 文件加载；不要把明文密钥塞入 JSON、环境样例或提交。

**当前新 GUI 的“保存配置”只保存演示设置，不创建真实连接库或 DPAPI 凭据。** 使用 Windows 侧经审阅的配置准备流程；缺少配置或凭据写入能力时记录阻塞，不能靠改 parser 或虚构密钥绕过。

准备好实际配置后，替换下面的 UUID，再运行只读档案检查：

```powershell
$tacticoreCommander = '替换为真实指挥官 UUID'
$tacticoreLibrary = Join-Path $env:LOCALAPPDATA 'Tacticore\library.v2.json'
& $tacticorePython .\strategy\service.py --library $tacticoreLibrary --commander $tacticoreCommander --check-profile
```

`--check-profile` 检查依赖和本地档案，可解密所选凭据，但不发模型请求；只输出脱敏就绪状态。检查通过不证明供应商接受参数。三个模型 CLI 都支持 `--model-backend pydantic|legacy`，默认 pydantic；对照时显式记录后端，不在异常后自动改用 legacy。

`battle_host.py --check` 的当前分支只采样并核验本地会话、映射与二进制，不调用模型或派单，但可能创建本地输出与采样记录。应使用 Windows 侧已经审阅的完整命令与当前有效证据，仅进入 `--check` 分支；不要复制旧场次 PID、UUID 或证据路径。`can_start` 还取决于执行请求、证据和构建是否就绪，缺少这些条件时应按实际拒绝结果记录，不能把参数缺项当通过。本指南不提供直接 `--execute` 开战命令。

## 5. 分阶段验证真实模型、游戏与新桌面

| 阶段 | 要验证什么 | 通过证据与限制 |
| --- | --- | --- |
| 真实模型连通 | 当前 provider / model 的标准 completion envelope、JSON 模式、token 字段与参数兼容性 | 手动发起的真实请求可能联网并计费；记录响应/拒绝码和用量，日志不能含密钥或完整私密请求 |
| 网络故障与退出 | DNS 不可用、连接超时、模型慢响应、停止时取消、client 关闭、进程退出 | 记录界限内是否退出、是否遗留请求/资源；不要因一次正常返回就宣称取消路径通过 |
| 受控游戏原语 | 当前游戏构建、己方视野、会话与玩家绑定、资源和能力证据、实际执行回执 | 先按既有模块规则重验允许能力；JSON 提案、HTTP 成功、native 调用返回都不等于实际效果 |
| 持续任务与整场 | 接近、交战、撤退、资源预留、目标稳定、失败重规划、停止与结算 | 新建本轮证据，分别记录胜负、任务完成与失败，不能沿用旧模型层历史战绩证明新默认 |
| 新 GUI 接线 | 档案、检查、启动、观察、停止的真实闭环 | 实现 [桌面合同](desktop-next/windows-handoff.md) 后另验；当前演示动画不是实机 GUI 验收 |

新的 Tauri Windows 构建还需 Node.js 22.22+、Rust 稳定工具链、MSVC C++ 和 WebView2，参见 [桌面 README](../desktop-ui/README.md)。可先运行 `npm ci`、`npm test`、`npm run build` 和 `npm run tauri -- build --no-bundle` 验证外壳；从 `desktop-ui/` 运行这些命令。原生窗口成功构建不意味着游戏适配器已实现。

## 6. 后续迭代按 Feature 路线图衔接

优先顺序为新 GUI 真实宿主接线、可视化备战与风格、电台媒体和意图回执，再到伴随小窗、配合意图、复盘与多 Agent。完整计划见 [Feature 路线图](desktop-next/feature-roadmap.md)。

- 初始资金是游戏开局规则；`--total-budget` 是 Agent 生产总支出上限，`--reserve` 是资源保留底线，三者独立。
- 指挥倾向映射现有 `personality` 三类与 `traits`；四个产品预设不是第四个后端枚举。新桌面已支持五档本机编辑、行为预览和人格/偏好草案，原有演示百分比已移除。Windows 适配器仍须明确消费并确认这些偏好，不把本机保存当作模型已采用，不增加未经支持的引擎参数。
- 用户确认局内独立指挥官及右上角电台入口已经存在；新桌面已实现本机媒体导入、字幕、试听、频率、冷却、中断与手动场景预览。真实游戏事件同步和局内电台播放仍待接线，不能把本地场景按钮当作实战触发。过期台词应丢弃，媒体失败不阻塞决策。

## 7. 每轮回传一份可复核结果

在新的验收目录保存下列摘要，并关联原始输出。未知或没跑的项目写“未验证”，不要用旧记录补填通过。

```text
验证时间 / 操作者：
提交 SHA / 分支 / 工作区是否有未提交修改：
Windows / Python 完整路径与版本 / 依赖锁文件版本或哈希：
游戏与适配包构建 / 能力证据版本：
模型后端 / provider / model / 是否真实联网：
场景：地图、玩家/阵营、初始资金、Agent UUID 与会话 ID：
硬约束：生产总支出上限、资源保留底线：
离线测试：总数、通过、失败、跳过及原因：
真实请求：接受、拒绝、超时、取消、请求耗时与可得用量：
执行结果：已提出、已接受、实际派发、完成、失败/阻止及原因：
停止 / 退出 / 残留进程与资源：
结算与任务效果分别记录：
证据目录 / 原始输出文件 / 独立复核结论：
仍未验证或阻塞的项目：
```

## 本侧提交前检查

本批应一起包含 `agent_runtime/`、`desktop-ui/`、`docs/`、`strategy/model_backend.py`、三个 CLI 组装入口、测试 fixture、README/改动说明及 `desktop/` 删除，避免只提交已跟踪文件而漏掉新目录。检查 `requirements-pydantic.lock`、`package-lock.json`、`src-tauri/Cargo.lock` 均在待提交清单；不提交 `.venv/`、`node_modules/`、`dist/`、`target/`、`.env`、真实配置和凭据。使用 `git status --short` 与 `git diff --check` 检查清单，最终暂存和提交由用户执行。
