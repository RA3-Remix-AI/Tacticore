# 弈核 Tacticore 桌面工程

这是 React + Tauri 2 工程。浏览器中的六工作区演示与 Windows 原生开发窗口使用不同入口：`npm run dev` 保留离线演示；Tauri 窗口使用 `NativeApp`，经受限的 Rust RPC 与 Python 宿主服务通信。

2026-10-26 的 Windows debug 验收已实际完成原生编译、开窗、读取三个指挥官档案、保存风格以及关闭重开恢复。保存后的同一 revision/hash 也经过一次真实模型 HTTP 请求验证。该探针使用合成观测，没有游戏访问或执行授权，不能证明风格已改变局内行为。实机对局及自然结算仍须单独验收。证据见 [原生验收记录](../reports/desktop-native-acceptance-20261026.json)。

## Windows 原生开发

需要 Node.js 22.22+、Rust MSVC 稳定工具链、Visual Studio 2022 C++ Build Tools、Windows SDK 和 WebView2。先准备仓库 `.venv` 中的宿主依赖及前端依赖：

```powershell
npm ci
.\scripts\build-windows.ps1
.\scripts\build-windows.ps1 -NativeTests
```

脚本通过 `vswhere` 加载 MSVC 环境并找到用户 Rust 安装，不依赖当前终端已有 cargo/cl PATH。构建输出为 `src-tauri/target/debug/tacticore-desktop.exe`。`npm run build` 只验证 TypeScript 与静态前端，不能替代原生编译和开窗验收。开发窗口使用仓库中的 Python 虚拟环境。

## Windows release companion

从仓库根目录，用当前 Python 3.12 虚拟环境建立一个新的独立目录；再在 `desktop-ui` 构建 release：

```powershell
.venv\Scripts\python.exe desktop-ui\scripts\package-runtime.py --output 'C:\TacticoreRelease\runtime'
cd desktop-ui
.\scripts\build-windows.ps1 -ReleaseDirectory 'C:\TacticoreRelease'
```

包包含独立 CPython、依赖、固定宿主源码和所需原生制品，不收集配置库、会话目录、运行日志或 DPAPI 凭据。固定 `_pth` 禁用环境、工作目录和用户 site 导入；包内清单列举全部文件 SHA-256，清单摘要编译进 Rust。release 只启动 exe 旁 `runtime/python/python.exe`，不会借用开发仓库、系统 Python 或 shell；缺文件、篡改或额外可导入代码会阻断 RPC。没有提供 manifest 的 release 构建仍返回 `runtime_packaging_unavailable`。

初版 8,636 文件的 companion 已在仓库外实际开窗，并恢复既有 revision 2 风格；插入一个未登记 `.py` 后，真实窗口已验证完整性拦截。独立烟测还验证了恶意 PYTHONHOME/PYTHONPATH/cwd 被忽略。见 [release 验收记录](../reports/desktop-release-acceptance-20261026.json)。该快照仅验配置与 RPC，未验证外部新会话的真实游戏宿主；最终集成后必须重新采集源码、生成 manifest 并重编译 Rust pin。当前没有签名安装器或更新器。

首次启动前，从仓库 `integration` 目录通过可信 Python CLI 显式登记一个已有配置库：

```powershell
..\.venv\Scripts\python.exe -m host_runtime.desktop_registry --library 'C:\absolute\path\library.v2.json'
```

CLI 在 `%LOCALAPPDATA%/Tacticore/desktop-runtime-config.json` 保存稳定登记 ID、绝对本机引用与原库 SHA-256；不复制配置库、DPAPI 凭据或 API Key，不扫描旧目录。它拒绝冲突登记和原库字节变化，迁移需另行安排停止会话后的流程。登记完成后重启原生窗口。WebView 无权提交任意路径、可执行文件或 shell 命令。

原生窗口允许读取档案/连接、保存风格、检查/开始/观察/停止宿主和导出脱敏诊断。所有操作走命名 RPC；检查结果、会话绑定和执行权限仍由宿主验证。连接源变化会中断配置服务并要求重启，不会静默替换已接受配置。关闭窗口只关闭配置/RPC 服务；真实运行宿主必须通过停止命令及确认回执管理。

风格草稿保存在 `%LOCALAPPDATA%/Tacticore/desktop-runtime` 的独立 ProfileStore 中，原始受保护配置库保持只读。界面分别展示“已保存”、宿主应用回执和模型消费证据。保存成功本身不等于宿主应用或局内效果验证。

## 原生可信会话登记

当前宏观宿主使用独立schema2登记：可信CLI的`--macro-bundle 'C:\TrustedAcceptance\new-run\macro-budget-bundle.json'`替代历史`--production-report`和`--persistent-status`，两类输入不能混用。宏观bundle核对原生预算实机证据、当前制品及己方视野；当前仅开放经济/军费投入优先级，单位移动与交战仍由原生AI负责。实现及实际客户端验收进展见[宏观客户端记录](../docs/commander-macro-desktop-20261028.md)。

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
