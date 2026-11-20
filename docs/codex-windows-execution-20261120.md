# Windows 实机执行文档（第 1 轮）

日期：2026-11-20 · 分支：`rework/beta4` · 执行者：Codex（Windows 机器）
工作规则：先读仓库根目录的 [AGENTS.md](../AGENTS.md)，本文件只写本轮要做的事。

## 背景（一段话）

`rework/beta4` 是一次大规模重构，以下内容都还**从未在实机上跑过**：
- 原生层只保留 Native7，删掉了约 3.6 万行代码；
- 支持任意地图和人类参战；
- 每局写一份决策记录 `decisions.jsonl`；
- 新版桌面客户端；
- 分层决策：总指挥、经济参谋、战术参谋，指挥官是铁锤。

本轮目标只有一个：**让它在实机上跑通，并把问题如实报回来。**不做新功能，不加验证层。遇到问题先修最小的那一处，修不了就报“阻塞”。

## 任务清单

按顺序执行。每个任务完成后按 AGENTS.md 的格式报告一次。

### T0 环境与基线

1. 拉取分支：`git fetch origin && git switch rework/beta4`。
2. 准备 Python 3.12 环境：
   ```powershell
   py -3.12 -m venv .venv
   .\agent_runtime\Install-Windows.ps1 -Python (Resolve-Path .\.venv\Scripts\python.exe).Path
   ```
3. 按 AGENTS.md 的“测试”一节跑全部测试，把失败列表存成基线，后面只报告新增失败。

**完成标准**：测试能跑完，基线已保存。Windows 上原本在 Mac 上报 `ctypes.WinDLL` 的测试应该能跑了。如果它们失败，那是真问题，要报告。

### T1 构建

1. 准备 Python 运行时：`python desktop-ui\scripts\stage-python-runtime.py --output C:\stage\runtime`。
2. 从 Beta 3 已安装的运行时复制原生数据文件，并重新封存：
   ```powershell
   python desktop-ui\scripts\stage-native-data.py --runtime C:\stage\runtime --from-runtime <Beta3 安装目录>\runtime
   ```
3. 编译原生运行时（编译器必须是哈希匹配 `build.py` 里 `COMPILER_SHA` 的 `i686-w64-mingw32-g++.exe`）：
   ```powershell
   python native-ai\strategic-portable-runtime-v7\build.py --runtime C:\stage\runtime --source-root <仓库根目录> --compiler <编译器路径> --field-candidate
   ```
   构建会核对 `manager_host.exe --layout`。`client.py` 里的 ctypes 结构必须对得上：Shared 4736 字节、Journal 4656 字节、Focus 144 字节。
4. 原生离线测试：用同一工具链编译并运行 `native-ai\tests\native_locked_inputs.cpp`、`native_wake_schedule.cpp`、`strategic_enemy_focus_lease_v1.cpp`。
5. 桌面：在 `desktop-ui` 里运行 `.\scripts\build-windows.ps1 -NativeTests`（等同 `cargo test`），然后正式构建安装包。

**完成标准**：生成安装包；原生测试和 `cargo test` 通过。
**如果编译器哈希对不上**：报“阻塞”，写明你手上的编译器版本和哈希。不要修改 `COMPILER_SHA`。

### T2 安装与首次配置

1. 关闭游戏，把新安装包覆盖安装到 Beta 3 上。
2. 打开客户端，走一遍首次设置向导：游戏与 Mod → 模型与 API Key → 对局模式。
3. 检查：
   - 状态显示环境已变化，需要重新准备；
   - 旧的运行记录被归档，不会阻塞查找新对局；
   - 向导里没有内部术语（例如“归还”“准入”“epoch”“资格”）。
4. “测试连接”按钮：本轮后端如果还没实现，会显示“当前版本还不能在这里测试”，这是预期结果。

**完成标准**：向导走通，能进入主屏，配置重开客户端后仍在。

### T3 查找对局与任意地图

在下面每种设置下，进入对局后在客户端点“查找对局”：

| 编号 | 地图 | 设置 |
| --- | --- | --- |
| 3a | Infinity Isle（2 人图） | 观战；弈核 AI 在大厅第 2 位、苏军、出生点 2；1 个原生电脑对手 |
| 3b | 另一张从未用过的 2 人图 | 同上 |
| 3c | 一张 4 人图 | 观战；2 个互为盟友的原生电脑对手 |
| 3d | 同一张 4 人图 | 你和弈核 AI 同队，对 2 个原生电脑 |
| 3e | 一张 2 人图 | 你对弈核 AI |
| 3f | 任意图 | 弈核 AI 不在出生点 2 |

**每项检查**：
- 能否找到对局；
- 对局卡片上的地图、模式、队伍、席位是否正确；
- 3f：“集结部队”“撤退回防”是否被标为不可用。

**完成标准**：3a–3e 都能找到对局，信息正确。哪项不对，就附上客户端截图和诊断文件。

### T4 对局跑通（最重要）

在 3a 和 3d 两种设置下各跑一整局：

1. 点“开始”，确认实时决策流里出现决策：时间、意图、理由、结果。
2. 让对局正常打到结束，或中途点“停止 AI”。
3. 停止后，确认客户端显示控制已交还，且运行目录的 `macro-release.json` 里 `native_release_verified=true`。
4. 打开复盘页：检查胜负、时长、决策数，以及每条决策属于哪一层（总指挥、经济、战术）、是哪位指挥官。
5. 不重启客户端，开下一局，确认能正常开始。

**每局交付**：运行目录里的 `battle-host/decisions.jsonl`、`macro-release.json`、客户端诊断导出文件，以及复盘页截图。

**完成标准**：两局都跑通，停止后能确认交还，第二局能正常开。

### T5 敌人优先攻击

在 3c（1 对 2）和 3d（带人类盟友）中：
- 在 `decisions.jsonl` 里找带 `focusenemy<id>` 的决策，`<id>` 必须是存活的敌人，绝不能是你或盟友；
- 下发后，原生 AI 的进攻目标是否确实偏向该敌人（截图或日志即可）。

**完成标准**：意图只指向存活敌人，下发后能观察到效果。观察不到效果也照实报告，不要改判定标准。

### T6 自动连续开局与评估

1. 用 computer use 写一个开局脚本，放在 `benchmark/eval/` 下，按配置设置大厅（地图、席位、对手、难度、初始资金 10000、关闭宝箱），开局后启动客户端的查找与开始，对局结束后退出游戏，再开下一局。
2. 每局结束后，用 `benchmark/eval/record_result.py` 写入结果标签。纯原生对照组没有宿主，也要用它记录结果。
3. 先跑一组小样本：同一张 2 人图、对手中等难度，**纯原生 10 局 + 弈核 10 局**。
4. 运行评估：`python benchmark\eval\evaluate.py --runs-root <结果目录> --out reports\eval-20261120`。

**完成标准**：脚本能无人值守连续跑完 20 局；评估报告生成。报告里的胜率、过程指标原样贴回来，不做解读。

## 本轮不做的事

- 不做单位直接控制（借出/交还）的实现。等本轮跑通后单独安排。
- 不做盟军、升阳指挥官。
- 不改模型提示词和决策逻辑。发现决策明显不合理，写进报告的“建议”一节，附上对应的 `decisions.jsonl` 片段。
- 不为通过某项检查而放宽或修改判定标准。

## 出问题时收集什么

- 客户端：设置页的“详细信息与诊断”里导出诊断文件。
- 宿主：运行目录下的 `battle-host/`、`decisions.jsonl`、`native-context.json`、`macro-release.json`。
- 原生：`%LOCALAPPDATA%\Tacticore\beta1\desktop-runtime\native7\journals\` 下对应的日志。
- 截图：出错时的客户端界面和游戏画面。

把这些文件放在本机一个目录里，报告里写路径即可，不要提交进 git。
