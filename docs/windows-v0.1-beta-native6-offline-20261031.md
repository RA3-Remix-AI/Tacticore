# Native6 可迁移离线候选

本文记录首批禁止附着候选，原制品和结论不变。后续新增的独立有界试运行模式、接入软件与持锁缺口修复见[接入记录](windows-v0.1-beta-native6-integration-20261031.md)，不为本文候选补发资格。

本批接在 Windows beta 的[第一批基础设施](windows-v0.1-beta-foundation-20261031.md)之后，完成新协议、相对运行清单、用户目录合同、SDK 迁移及离线编译/迁移烟测。**当前候选禁止附着游戏，没有产品资格、正式局或真实归还验收。** 默认客户端仍使用既有 Native5，未将 Native6 加入模型目录或回退通路。

## 实现边界

- Native6 使用独立的魔数、协议版本、映射名和日志尾标。绑定包含 PID/创建时间、回调线程、己方原生身份、会话/随机租约、Mod/源码闭包摘要，以及完整运行清单摘要、实际游戏路径、运行根目录和日志根目录。旧 Native5 日志不能补算为 Native6 日志。
- helper 从自身位置解析 `runtime/native/strategic6`，DLL 按运行根目录及相对文件名生成输入锁。运行合同不读取开发机工具链、游戏 SDK、历史 reports 或旧 schema13 原件；游戏仍使用固定 RA3 1.12 哈希与实际 OS 进程身份，Mod 仍使用固定资格化包哈希及受控 Documents/Red Alert 3/Mods 根目录。

  输入锁路径只完成离线合同与编译检查；由于本候选禁止附着，实际持锁、回调开销与归还仍待可启用候选验证。
- 用户路径来自 Windows Known Folder API，不信任继承的 LOCALAPPDATA/PYTHONPATH。报告及日志分别位于用户的 `Tacticore/desktop-runtime/native6/reports` 和 `journals`；拒绝网络路径、设备路径、重解析点及越界，不回退写入安装目录。
- 构建记录相对源码闭包和实际 Native 源/编译器摘要；所有应用 Python/缓存、解释器及扩展二进制列入编译输入锁，完整 companion 清单另外绑定依赖、Native 制品与元数据。编译器仅是构建输入，不随运行包携带。
- 原生调用与意图有效期逻辑、冲突掩码、未知结果不重发保留；回归直接比较旧/新 flag API、原生 tick 和 SDK 命令段，防止迁移顺带引入精确建筑、兵种或微操接管。
- SDK 具备 helper OS 身份留档及部分构造失败的查询句柄清理。独立只读收集器仅打开已有 FILE_MAP_READ，借用新鲜己方基线/旗标/租约核验；不构造 Probe、不发 STOP、不启动 helper、不改交付账本。它明确返回 `ownership_return_claimed=false`，尚不构成普通客户端的恢复能力。

## 已完成验证

| 项目 | 证据范围 |
| --- | --- |
| 新合同回归 | 12 项通过；含实际 Known Folder API、不可信环境、相对清单、换局/租约/路径/清单摘要绑定、旧协议、截断与重排日志、原控制逻辑保留 |
| 发布回归 | 15 项通过；新增检查 Native6 制品及自报资格位也不能让发布预检通过 |
| 实际 i386 构建 | DLL/helper 编译无错误，导出检查、1,026 个掩码候选、编译身份和 SDK 布局一致 |
| 布局三方交叉核验 | C++、64 位 Python ctypes 与独立固定布局解析器一致：Binding 4,332、Shared 4,592、Journal 4,512 字节，日志 flags 偏移 4,448 |
| 隔离运行 | 使用包内 Python，在仓库外、错误 PYTHONHOME/PYTHONPATH、同名 cwd 假模块和最小用户环境下通过；已导入模块全部位于 companion 内 |
| 原配置功能回归 | 在新 Native6 包中实际初始化临时配置、查询档案并跨进程重开读取通过，Pydantic 后端可导入；不读原用户密钥，不发模型请求 |
| 目录迁移 | 同一冻结包复制到含中文及空格的新目录，无需重新编译；完整清单与源码闭包不变，helper 相对根目录及 SDK 验证通过 |
| 真制品反向检查 | 修改 SDK、DLL 或伪造准入位均拒绝；恢复原字节后完整清单重新通过。反向检查只修改本批独立副本 |
| 附着阻断 | SDK 在创建输出、打开 Memory/WinDLL 或启动 helper 前拒绝；helper 的实际正 PID 调用返回离线拒绝码 24；DLL 导出入口亦有编译关闭门 |

离线解析器最初估算的 flags 偏移为 4,456；实际 C++ 布局显示 4,448，已在最终候选交叉核验前纠正。早期包保留其原版本，不将不同候选的结果混算。

最终候选为 `candidate-v3`，共 8,980 个清单文件、1,733 个编译代码输入锁；运行清单 SHA-256 为 `c493605c051a0e453a0ea59fbc0485a005da218c46836038eefb016bda4f6ed1`，源码闭包为 `f42d026afefd6a096ddbd3121ccf283b26474594c8064b84be1fae4858ff92bf`。本机原件位于 `D:\CodexScratch\tacticore-native6-offline-20261031-142210`：`build-v3.log`、`probe-v3-relocated.json`、`configuration-smoke-v3.json`、`payload-negative-checks-v3.json` 及 `release-preflight-v3.json`；另保留早期候选、迁移副本和回归日志。这些原件不随 Git 源码分发。

## 如何复现

先按[阶段包说明](../desktop-ui/README.md#windows-v01-beta-开发)准备精确 Python 依赖和 Git 源清单。Native6 新文件必须进入受版本管理的源码清单，阶段包才会收集。使用新的输出目录：

```powershell
.venv\Scripts\python.exe -B desktop-ui\scripts\stage-python-runtime.py --output 'C:\TacticoreNative6\runtime'
C:\TacticoreNative6\runtime\python\python.exe -I -S -B C:\TacticoreNative6\runtime\app\native-ai\strategic-portable-runtime-v6\build.py --runtime 'C:\TacticoreNative6\runtime' --source-root 'C:\absolute\source' --compiler 'C:\absolute\w64devkit\bin\i686-w64-mingw32-g++.exe'
.venv\Scripts\python.exe -B desktop-ui\scripts\probe-native6-runtime.py --runtime 'C:\TacticoreNative6\runtime' --relocate-to 'C:\TacticoreNative6\迁移 空格\runtime' --output 'C:\TacticoreNative6\offline-smoke.json'
```

构建器只接受已登记摘要的编译器及原生调度 API 头文件，没有 `--field` 或 `--approve` 开关。`FIELD_CANDIDATE=false` 是编译常量，JSON 改位不能使该二进制获得准入。

## 未完成与下一步

本批只完成阶段 B 的离线候选。新的发布资格/准入合同、合法观测适配器、Host/STOP/未知账本/独立归还路由、普通客户端接入尚未集成。真实基线收集、孤儿恢复、每回调持锁成本及实机效果均未验证。启用附着会产生不同二进制，必须重新冻结、复核并由唯一实机控制者验收，不能继承本批或 v9 的自然局计数。

旧 Native5 路径问题仍出现在默认产品路线的预检中；这是尚未替换的真实依赖，不能因新增 Native6 源码而移除阻断。安装器、首次游戏接入、含 wheel 摘要的可重建输入锁、完整工具链闭包及再分发审查仍按[执行清单](windows-v0.1-beta-execution.md)继续。
