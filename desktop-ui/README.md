# 弈核 Tacticore 桌面工程

这是 React + Tauri 2 工程。浏览器中的六工作区演示与 Windows 原生开发窗口使用不同入口：`npm run dev` 保留离线演示；Tauri 窗口使用 `NativeApp`，经受限的 Rust RPC 与 Python 宿主服务通信。

2026-10-26 的 Windows debug 验收已实际完成原生编译、开窗、读取三个指挥官档案、保存风格以及关闭重开恢复。保存后的同一 revision/hash 也经过一次真实模型 HTTP 请求验证。该探针使用合成观测，没有游戏访问或执行授权，不能证明风格已改变局内行为。实机对局及自然结算仍须单独验收。证据见 [原生验收记录](../reports/desktop-native-acceptance-20261026.json)。

## 当前可运行客户端与已验范围 · 2026-10-30

普通操作见[玩家使用指引](../docs/desktop-next/player-guide.md)。本机 debug EXE 路径为 `src-tauri/target/debug/tacticore-desktop.exe`，实际文件及运行组件必须对应本次冻结候选的版本清单。此前的 SHA-256 `168ebbad430c76cdd60c2b66bf3312737abd4e24bbceb0cc9657c6bf13cc57aa`／`index-DAJnEEyf.js` 属于旧隔离预览，不能确认后来重建的客户端。从仓库根目录运行：

```powershell
& '.\desktop-ui\src-tauri\target\debug\tacticore-desktop.exe'
```

该 EXE 使用仓库 Python 环境；单独复制 EXE 不能替代部署运行组件。当前产品只让模型判断高层意图，具体建筑、选址、顺序、兵种、数量和单位操作均由原生 AI 决定。Native5试运行候选已接入十四项高层入口，包括建设／生产调度门和原生扩张偏好；预算偏好、已满足状态、任务活动与实际战略成功分别记录，逐项与综合验收仍须完成。

当前已有普通GUI真实模型运行、启动前取消、已接管停止、独立归还、实际诊断下载及过程回放的分项原件。v9产品宿主骤停后的未知状态、只读归还与下一局解锁亦已独审；正式自然局已通过 **3/3**，F01–F07已按本机固定范围完成总审；v9历史容量缺陷、实机专用事件来源和开发版发布限制见[最终报告](../reports/strategic-final-acceptance-v9-20261030-v1/README.md)。最新范围见[产品集成进度](../docs/commander-strategic-product-integration-20261029.md)。下列配置和控制通路记录保留其原固定版本与当时的未测项，不能据旧“当前／本次”描述推断后来候选的状态，也不因新记录而把旧失败补绿。

- 真实 GUI 已核验：旧 `d142…` 构建查询已登记库的连接、显示上局最后记录、无游戏时发现/检查拒绝且启动禁用；随后在隔离 D 盘业务库实际验证首用初始化、人工假密钥保存、普通配置自动重载、关闭重开持久化，以及中断事务的手动恢复。恢复未重输假密钥，最终库、注册、完成收据和 DPAPI 互通均经只读独核。
- 临时库与假密钥已核验：首用初始化、真实 Windows DPAPI 与现有模型读取 API 互通、保存与幂等、旧配置拒绝、跨文件中断恢复、风格保留、旧预检失效，以及独立配置通道到普通 RPC 的重载。组件测试还覆盖成功、重查、保存/恢复提示和失败不自动重试。
- 未修改用户既有连接或使用真实密钥，也没有通过 GUI 新启模型/游戏。旧 `d142…` 构建在 pending 配置时仍显示可检查/自动等待的 UI 缺口原件保留，后端 barrier 当时仍严格拒绝。本次新构建已增加父组件联动：未核验、处理中、pending 或 unknown 时禁检查/启动/自动等待并取消已 armed 状态；恢复 ready 后须重新检查。119 项前端回归和实际 React 父组件逆向已过，新构建实际 GUI 待复测；完整 F05 与正式自然局仍未通过，正式为 **0/3**。

软件冻结见[集成记录](../reports/commander-strategic-client-config-integrated-20261029-v1/handoff.json)与[提示修复增量](../reports/connection-query-notice-ui-delta-20261029-v1/source-manifest.json)，实际 GUI 见[首次只读核验](../reports/strategic-client-gui-readonly-20261029-v1/observation.json)、[查询提示复核](../reports/strategic-client-gui-readonly-20261029-v2/observation.json)、[隔离首用/保存](../reports/strategic-client-first-use-gui-20261029-v1/observation.json)与[重开/中断恢复](../reports/strategic-client-reopen-recovery-gui-20261029-v1/observation.json)。这些本机原件不一定随源码分发。

本次还将既有运行的恢复观察、状态、停止与诊断分到独立限权控制通路，避免连接库与注册不一致时在 Rust 层先被阻断；新准入保持严格。真实隔离管道与 Rust 实际 dispatch 回归已过，实际 WebView 通路仍待复测，不能只凭按钮可点声称端到端通过。边界与原件说明见[独立控制通路](../docs/commander-control-only-channel-v1-20261029.md)。

## Windows 原生开发

需要 Node.js 22.22+、Rust MSVC 稳定工具链、Visual Studio 2022 C++ Build Tools、Windows SDK 和 WebView2。先准备仓库 `.venv` 中的宿主依赖及前端依赖：

```powershell
npm ci
.\scripts\build-windows.ps1
.\scripts\build-windows.ps1 -NativeTests
```

脚本通过 `vswhere` 加载 MSVC 环境并找到用户 Rust 安装，不依赖当前终端已有 cargo/cl PATH。构建输出为 `src-tauri/target/debug/tacticore-desktop.exe`。`npm run build` 只验证 TypeScript 与静态前端，不能替代原生编译和开窗验收。开发窗口使用仓库中的 Python 虚拟环境。

## Windows v0.1-beta 开发

发布工作在独立分支 `release/windows-v0.1-beta` 推进，完整交付顺序与门槛见[发布执行清单](../docs/windows-v0.1-beta-execution.md)。当前先实现锁定 Python 依赖的阶段包；它不包含具备可迁移资格的 Native 战略运行组件，不能作为游戏 beta 分发。

在仓库根目录，使用安装了 `agent_runtime/requirements-pydantic.lock` 精确版本的 Windows x64 CPython 3.12 环境执行：

```powershell
.venv\Scripts\python.exe -B desktop-ui\scripts\stage-python-runtime.py --output 'C:\TacticoreStage\runtime'
.venv\Scripts\python.exe -B desktop-ui\scripts\probe-python-stage.py --runtime 'C:\TacticoreStage\runtime' --output 'C:\TacticoreStage\python-smoke.json'
.venv\Scripts\python.exe -B desktop-ui\scripts\release_preflight.py --runtime 'C:\TacticoreStage\runtime' --output 'C:\TacticoreStage\preflight.json'
```

输出目录与报告必须是新的。构建机还需要 Git：应用源码仅从受版本管理的 Python 文件中收集，排除未跟踪脚本和 JSON；打包器按锁逐一选择 distribution 并核对 RECORD 的 SHA-256 与大小，拒绝缺失文件、版本冲突、导入钩子和路径逃逸，不再复制整个 site-packages。包内有解释器、锁和构建工具摘要、实际依赖/许可证文件清单及完整文件摘要。当前版本锁尚不是含 wheel 摘要的可重建下载锁，许可证清单中的 `pending` 也不是再分发许可结论。

烟测在临时的全新本机配置中验证 SDK 导入、首次初始化、档案查询和进程重开；不读取用户密钥，不调用模型或游戏。外部同名模块及错误 PYTHONHOME/PYTHONPATH 不得影响导入，烟测前后清单必须一致。它不能代替干净 Windows 上的安装器、WebView2 或游戏验收。

预检目前**预期非零退出**：Native5 helper、DLL 源清单/日志/Mod 路径及 schema13 资格仍绑定开发机，新便携合同、首用游戏接入与安装器尚未完成。报告逐项列出原因。`build-windows.ps1 -ReleaseDirectory ... -PythonExecutable ...` 会先运行同一预检并拒绝未完成候选；直接 release 编译也必须提供运行清单。旧 `package-runtime.py` 默认拒绝运行，只有显式 `--legacy-research` 可重现早期研究快照。

本轮不改旧资格及正式局计数。新 Native 运行组件必须与 SDK、只读归还读取器和用户数据路径一起冻结，随后由唯一实机控制者重新验收。

## 历史 Windows release companion

以下流程和验收属于旧配置／RPC发布快照。当前Native5本机debug候选不继承该发布资格；完整Native5非Python制品及运行闭包尚须另行打包验证。可移植安装不作为本轮战略产品自然验收的新增前置。

从仓库根目录，用当前 Python 3.12 虚拟环境建立一个新的独立目录；再在 `desktop-ui` 构建 release：

```powershell
.venv\Scripts\python.exe desktop-ui\scripts\package-runtime.py --legacy-research --output 'C:\TacticoreRelease\runtime'
cd desktop-ui
.\scripts\build-windows.ps1 -ReleaseDirectory 'C:\TacticoreRelease'
```

包包含独立 CPython、依赖、固定宿主源码和所需原生制品，不收集配置库、会话目录、运行日志或 DPAPI 凭据。固定 `_pth` 禁用环境、工作目录和用户 site 导入；包内清单列举全部文件 SHA-256，清单摘要编译进 Rust。release 只启动 exe 旁 `runtime/python/python.exe`，不会借用开发仓库、系统 Python 或 shell；缺文件、篡改或额外可导入代码会阻断 RPC。没有提供 manifest 的 release 构建仍返回 `runtime_packaging_unavailable`。

初版 8,636 文件的 companion 已在仓库外实际开窗，并恢复既有 revision 2 风格；插入一个未登记 `.py` 后，真实窗口已验证完整性拦截。独立烟测还验证了恶意 PYTHONHOME/PYTHONPATH/cwd 被忽略。见 [release 验收记录](../reports/desktop-release-acceptance-20261026.json)。该快照仅验配置与 RPC，未验证外部新会话的真实游戏宿主；最终集成后必须重新采集源码、生成 manifest 并重编译 Rust pin。当前没有签名安装器或更新器。

当前普通首次使用可在窗口的“本机连接配置”点击“初始化本机配置”，再保存提供方、接口、默认模型和密钥；不会覆盖无关的已有来源。已有配置直接查询即可。修改提供方或接口时，不能沿用隐含的旧密钥，必须重新输入新接口密钥或选择停用保存密钥。

以下 CLI 仅供维护者显式登记既有库，不是普通首次配置或每局操作步骤。请勿为通过检查而手改登记或会话文件：

```powershell
..\.venv\Scripts\python.exe -m host_runtime.desktop_registry --library 'C:\absolute\path\library.v2.json'
```

CLI 在 `%LOCALAPPDATA%/Tacticore/desktop-runtime-config.json` 保存稳定登记 ID、绝对本机引用与原库 SHA-256；不复制配置库、DPAPI 凭据或 API Key，不扫描旧目录。它拒绝冲突登记和原库字节变化，迁移需另行安排停止会话后的流程。登记完成后重启原生窗口。WebView 无权提交任意路径、可执行文件或 shell 命令。

原生窗口允许配置连接、保存风格、发现/准备/检查/启动/观察/停止宿主和导出脱敏诊断。所有操作走命名 RPC；检查结果、会话绑定和执行权限仍由宿主验证。连接更新仅在已停止且独立归还后进行；成功保存或恢复会清除旧预检与配置服务缓存，后续普通 RPC 重读新登记，无需用户手改注册文件。外部擅改来源或未恢复的中断仍会拒绝新启动。关闭窗口只关闭配置/RPC 服务；真实运行宿主必须通过“请求停止”和独立归还管理。

风格草稿保存在 `%LOCALAPPDATA%/Tacticore/desktop-runtime` 的独立 ProfileStore 中。普通列表与模型读取不写配置库；专用可信配置服务可更新连接和相应绑定，并保留已保存风格、更新修订号。界面分别展示“已保存”、宿主应用回执和模型消费证据。保存成功本身不等于宿主应用或局内效果验证。

### 新配置通道的 release 软件清单

`package-runtime.py` 的 `SOURCES` 已包含 `integration` 和 `strategy`，并递归收集非测试 `.py`。因此新 `host_runtime/connection_config_{atomic,bootstrap,credentials,rpc,schema,server,service}_v1.py` 与 `macro_strategic_client_v1.py` 会自动进入 `app/integration/host_runtime/`，其源码和生成的 checked-hash 缓存须全部纳入新 `manifest.json`。前端面板随静态资产嵌入 EXE，原生命令还需同时保留 Rust 注册和 Tauri ACL。

本轮只核对了该收集规则，没有构建新的完整 companion。旧 2026-10-26 portable 快照不能代替新配置通道和当前游戏宿主的验证；release 仍须生成新完整清单、重编 Rust 摘要，再验证包外开窗、首用、恢复和真实运行流程。当前可用交付是上述本机 debug EXE。

## 原生可信会话登记

日常流程使用窗口内的“发现游戏 / 准备下一局”及“准备所选对局”，不要求用户编辑 session。受信运行组件、游戏发现配置与匹配宏观包仍需维护者预备。以下是维护/验收用登记接口。

当前宏观宿主使用独立schema2登记：可信CLI的`--macro-bundle 'C:\TrustedAcceptance\new-run\macro-budget-bundle.json'`替代历史`--production-report`和`--persistent-status`，两类输入不能混用。宏观bundle核对原生预算实机证据、当前制品及己方视野；当前模型目录按战略边界限制为已有资格的预算、侦察和区域调度入口，单位移动与交战仍由原生AI负责；精确建筑/兵种数量不进入当前目录。实现及实际客户端验收进展见[宏观客户端记录](../docs/commander-macro-desktop-20261028.md)。

在仓库 `integration` 目录运行以下可信 CLI；不要把路径加入 WebView RPC 或模型输入：

```powershell
..\.venv\Scripts\python.exe -m host_runtime.desktop_session_registry --session-root 'C:\TrustedAcceptance' --session 'C:\TrustedAcceptance\new-run\session.json' --production-report 'C:\TrustedAcceptance\proof\production-report.json' --persistent-status 'C:\TrustedAcceptance\proof\persistent-production-status.json'
```

CLI 在固定 desktop-runtime 状态目录保存根登记及三个文件的身份/内容 hash，不读取游戏内存或调用模型。根与全部输入必须是显式绝对本机路径；文件必须落在该根内，session 的 run_directory 必须与其位置一致。服务不会从 session JSON、模型、WebView 或历史目录推断可信根。登记后重新打开窗口并进行真实预检；登记本身不会授予能力。

同一登记可幂等重用。替换会话须显式 `--replace-stopped`，并通过全部历史运行已终止、无未决命令以及独立控制归还核验；单有停止回执不够。根登记冲突明确拒绝，另行安排停止后的迁移。运行中的服务发现根变化会清除旧预检令牌并拒绝新启动；已接受运行的查询和停止仍按原绑定处理。

宿主通过固定 argv 接收 `--acceptance-root`，原始证据重新评估仍核对 game/mod/process 与原生生产边界。portable 包中的历史二进制绝对路径仅通过受清单保护的 provenance 对比；实际二进制和源码读取始终指向当前包内固定位置，不回读原开发仓库。

Windows venv redirector 的 Popen PID 与 Python 自报 PID 不同，因此原生 debug bootstrap 和宿主子进程会直接启动基础 CPython，用隔离参数加入固定依赖。不能通过放宽进程身份比对来兼容 redirector。

## 浏览器离线演示

```powershell
npm run dev
npm test
npm run build
```

浏览器打开 `http://127.0.0.1:5174`。六工作区覆盖备战、作战中心、指挥官工坊、战场电台、模型连接和演练记录；它们使用离线数据，不调用真实模型或游戏。演示档案/备战草稿使用 localStorage，媒体使用 IndexedDB，均属于当前 origin；它们不会自动迁入原生 ProfileStore。

演示电台支持视频、音频、字幕、试听、冷却和中断。每条媒体上限 32 MiB / 90 秒，每位指挥官最多 24 条自定义媒体、合计 128 MiB。素材不上传。演示的备战资金、生产额度与偏好设置不构成真实游戏配置。

## 相关文档

- [Windows 同步与验证指南](../docs/windows-validation.md)
- [Windows 接入契约](../docs/desktop-next/windows-handoff.md)
- [架构迭代计划](../docs/architecture-iteration-plan-20261026.md)
- [架构实施状态](../docs/architecture-implementation-status.md)
- [策略 HTTP 服务](../strategy/HTTP_SERVICE.md)

历史演示说明中的“未接真实宿主/模型”只适用于浏览器入口。当前真实对局能力应以架构实施记录及对应实机证据为准。

2026-10-31：当前Python提示生成已修复临界容量测量差异，验证与历史v9资格范围见[修复说明](../docs/commander-prompt-budget-fix-20261031.md)。
