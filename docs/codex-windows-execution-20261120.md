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
5. 桌面：在 `desktop-ui` 里运行 `.\scripts\build-windows.ps1 -NativeTests`（等同 `cargo test`），然后正式构建安装包。`cargo test` 里应包含 `connection_test_names_a_saved_connection_only`。

**完成标准**：生成安装包；原生测试和 `cargo test` 通过。
**如果编译器哈希对不上**：报“阻塞”，写明你手上的编译器版本和哈希。不要修改 `COMPILER_SHA`。

### T2 安装与首次配置

1. 关闭游戏，把新安装包覆盖安装到 Beta 3 上。
2. 打开客户端，走一遍首次设置向导：游戏与 Mod → 模型与 API Key → 对局模式。
3. 检查：
   - 状态显示环境已变化，需要重新准备；
   - 旧的运行记录被归档，不会阻塞查找新对局；
   - 向导里没有内部术语（例如“归还”“准入”“epoch”“资格”）。
4. “测试连接”：
   - 正确的 Key 应显示“连接正常”和响应时间；
   - 错误的 Key 应显示“API Key 无效”；
   - 错误的模型名：记下服务商返回的 HTTP 状态码，以及客户端显示的原因；
   - 如果显示 `connection_test_runtime_unavailable`，说明打包的 Python 里缺 `pydantic_ai` 或 `httpx2`，这是打包问题，要报告。
5. 设置 →“指挥官”：
   - 三张头像和铁锤大图都能显示，没有被打包或 CSP（`img-src 'self'`）拦住；
   - 堡垒、幽灵显示“即将推出”，不能选；
   - 选铁锤并保存，重启客户端后仍是铁锤；改任意一个性格参数会变成“自定义”，保存后能读回；
   - 口吻说明超过 300 字节时，保存按钮不可用；
   - 顶栏显示当前指挥官的头像和名字。

**完成标准**：向导走通，能进入主屏，配置和指挥官选择在重开客户端后仍在，测试连接结果正确。

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

### T4b 分层决策（铁锤）

T4 的对局默认就是分层模式。用同一批运行目录检查下面几点，主要看 `battle-host/decisions.jsonl` 和 `battle-host/host-events.jsonl`：

1. **开局前**：`run_start` 里有 `decision_mode=layered`、`commander`、`opening_variant` 和 `opening_variant_name`。第一条 `layered_layer_requested` 是总指挥，带 `prematch=true`，发生在游戏时间第 30 秒之前。
2. **开局期间**：在 `layered_opening_handover` 之前，除了开局前那一次，没有别的模型调用。交接原因是 `scouting_report` 或 `opening_timeout`（最晚第 180 秒）。
3. **交接之后**：三层都有 `layered_layer_requested`。间隔大约是：战术 15 秒、经济 50 秒、总指挥 90 秒。同一层不会同时有两个在途请求。
4. **合成结果**：每次 `layered_composition` 之后，要么有 `plan_applied`，要么有带原因的 `macro_plan_not_dispatched`。下发的 `macro_actions` 里最多一个军事动作、一个 `focusenemy<id>`。
5. **骚扰时限**：开局下发 `raideconomy` 后，最晚约 75 秒内会改成 `scout`，或者出现停止事件。
6. **不重发**：出现一次“送达结果未知”之后，不再有新的 `layered_composition`。
7. **单层对照**：用 `--decision-mode single`（或环境变量 `TACTICORE_DECISION_MODE=single`）跑一局，行为应和 Beta 3 的单次调用一致，记录里 `decision_mode=single`。
8. **指挥官不可用**：UI 选堡垒或幽灵时，检查对局返回 `commander_unavailable`。Beta 3 留下的旧配置显示为铁锤，保存后能正常开局。
9. **请求大小**：记下每层模型调用的 `latency_ms` 和 `input_bytes`，确认都不超过 16 KiB。
10. **停止**：两个参谋同时有请求在途时点“停止 AI”，确认停止生效，原生 AI 设置正常恢复。

**完成标准**：1–10 都符合。不符合的逐条报告，附上对应的日志片段。

### T5 敌人优先攻击

在 3c（1 对 2）和 3d（带人类盟友）中：
- 在 `decisions.jsonl` 里找带 `focusenemy<id>` 的决策，`<id>` 必须是存活的敌人，绝不能是你或盟友；
- 下发后，原生 AI 的进攻目标是否确实偏向该敌人（截图或日志即可）。

**完成标准**：意图只指向存活敌人，下发后能观察到效果。观察不到效果也照实报告，不要改判定标准。

### T6 自动连续开局与评估

1. 用 computer use 写一个开局脚本，放在 `benchmark/eval/` 下，按配置设置大厅（地图、席位、对手、难度、初始资金 10000、关闭宝箱），开局后启动客户端的查找与开始，对局结束后退出游戏，再开下一局。
2. 每局结束后，用 `benchmark/eval/record_result.py` 写入结果标签。纯原生对照组没有宿主，也要用它记录结果。
3. 先跑一组小样本：同一张 2 人图、对手中等难度，三组各 10 局：
   - 纯原生；
   - 弈核单层（`single`）；
   - 弈核分层（`layered`，铁锤）。
4. 运行评估：`python benchmark\eval\evaluate.py --runs-root <结果目录> --out reports\eval-20261120`（`reports/` 已不进 git，报告留在本机）。

**完成标准**：脚本能无人值守连续跑完 30 局；评估报告生成。报告里的胜率、过程指标原样贴回来，不做解读。

## 本轮不做的事

- 不做单位直接控制（借出/交还）的实现。等本轮跑通后单独安排。
- 不做盟军、升阳指挥官。
- 不改模型提示词和决策逻辑，也不调整性格参数的换算规则（`integration/host_runtime/personality_rules.py`）。发现决策明显不合理，写进报告的“建议”一节，附上对应的 `decisions.jsonl` 片段。
- 开局方案里战熊侦察、恐怖机器人骚扰、协议选点等步骤目前“仅记录，尚未执行”，这是预期结果，不是缺陷。
- 不为通过某项检查而放宽或修改判定标准。

## 出问题时收集什么

- 客户端：设置页的“详细信息与诊断”里导出诊断文件。
- 宿主：运行目录下的 `battle-host/`、`decisions.jsonl`、`native-context.json`、`macro-release.json`。
- 原生：`%LOCALAPPDATA%\Tacticore\beta1\desktop-runtime\native7\journals\` 下对应的日志。
- 截图：出错时的客户端界面和游戏画面。

把这些文件放在本机一个目录里，报告里写路径即可，不要提交进 git。
