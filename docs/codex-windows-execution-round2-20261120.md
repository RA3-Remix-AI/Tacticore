# Windows 实机执行文档（第 2 轮）：单位直接控制

日期：2026-11-20 · 分支：`rework/beta4` · 执行者：Codex（Windows 机器）
**开始条件：第 1 轮（[codex-windows-execution-20261120.md](codex-windows-execution-20261120.md)）的 T0–T4 已通过。**第 1 轮没跑通之前，不要开始本轮。

工作规则见 [AGENTS.md](../AGENTS.md)。设计依据见[分层决策实施计划](commander-layered-decision-plan-20261120.md) 第 7、8 节和[指挥官角色与战术设计](commander-characters-tactics-20261120.md) 第 5 节。

## 目标

让铁锤开局里“仅记录，尚未执行”的两步真正生效：侦察和低成本骚扰敌方矿车。做法是由我们的原生组件直接指挥单位移动和攻击，由宿主里的控制器每 0.2–1 秒运行一轮，模型不进实时循环。

## 参考：Ra3-Copilot

[ProbiusOfficial/Ra3-Copilot](https://github.com/ProbiusOfficial/Ra3-Copilot) 已经逆向出我们需要的大部分能力，作者已同意本项目使用。

| 需要 | Ra3-Copilot 里的位置 |
| --- | --- |
| 单位攻击和移动调用 | `ra3-copilot/src/aicmd.cpp`（`RVA_ATTACK`、`RVA_MOVE`，区分零售版和 Steam 版），调用方式见 `docs/AI接入指南.md` 5.3–5.4 |
| 全图对象枚举（归属、坐标、血量） | `ra3-copilot/src/battlefield.cpp`，说明见 `docs/MCP开放-脑机接口.md` |
| 判断零售版还是 Steam 版 | `ra3-copilot/src/buildinfo.cpp` |
| 地址逐字节预检 | `ra3-copilot/tools/precheck_aob.py` |
| 单位类型哈希 | `unit-codes/tools/sage_hash.py`（仓库已在用） |

**使用方式**：需要的代码可以直接复制进本仓库，放在 `native-ai/third_party/ra3-copilot/`，同时保留来源提交号，并带上上游的 LICENSE（作者补上后）。复制后更新 `docs/references-and-attributions.md` 的 Ra3-Copilot 一节。

**禁止使用它的作弊类功能**：召唤单位、加钱、全科技、免费建造、去迷雾、无敌、秒杀、收编。弈核的原则是不作弊。全图枚举只能作为原始数据来源，交给模型和控制器之前，必须用现有的 `visibility/` 模块过滤成己方合法视野。

## 任务清单

### 准备：Ra3-Copilot

1. 克隆 Ra3-Copilot 并切到固定提交 `d8abf9ecb0306f8b4a0b87a6cafa07ffd3dbcbd2`（仓库外的目录即可，本轮不复制进仓库）。
2. 用它的 `ra3-copilot\build.bat` 构建（需要 VS2022 BuildTools x86 和 Windows SDK 10.0.22621），R1 只用 `injector.exe` 和 `ra3copilot.dll` 注入。
3. **不要用它的启动器 `Ra3Copilot.exe` 的“战役扩展和全科技模式”**：它会改写游戏数据包。F12 面板里的功能一个都不点。

注意：Ra3-Copilot 的地址表来自另一份游戏文件（SHA `518ef272…`），弈核绑定的是 `ec230c6a…`。不过弈核自己的符号表 `native-ai/native-symbols.json` 里，移动函数在我们这份文件上也是 `0x6EFF70`，和它的零售版一致，所以布局大概率相同。R0 就是确认这一点。

### R0 离线预检（不进游戏）

运行：

```
python -X utf8 native-ai\unit_control_precheck.py --game "<游戏目录>\Data\RA3_1.12.game" --copilot "<Ra3-Copilot 目录>"
```

它检查：游戏文件 SHA 是否等于弈核绑定的 `GAME_SHA`；是否零售版布局；移动函数入口字节；攻击函数入口是否像函数开头；对象枚举用的 Thing 虚表形状。地址统一在 `native-ai/unit_control_addresses.py`。它还会顺带跑 Ra3-Copilot 自己的 `precheck_aob.py`，结果只作参考（那 30 处是它的面板功能，我们不用），但能看出 Ra3-Copilot 能不能在这份文件上正常加载。

**完成标准**：输出 `"verdict": "PASS"`。把整段 JSON 原样贴进报告，尤其是 `attack_object.bytes`，我会把这 24 字节固定进地址表。`BLOCKED` 就停下报告，不要改地址去凑。

### R1 覆盖实验（最关键，决定后面怎么做）

问题：我们给**原生 AI 名下**的单位下命令，原生 AI 多久会把命令覆盖掉？

1. 开一局普通遭遇战：无限岛，弈核 AI 席位设置和第 1 轮一样（大厅第 2 位、苏军），对手中等。**不启动弈核客户端。**
2. 进局后用 `injector.exe` 注入 Ra3-Copilot，确认 `curl http://127.0.0.1:17832/ping` 返回 `pong`。
3. 用 `python -X utf8 benchmark\r1_override.py units --owner <N>` 找到弈核 AI 席位的单位。`<N>` 是 Ra3-Copilot 报告的归属序号，先用 `/snapshot` 确认是哪个序号对应弈核 AI 席位，不要默认是 3。
4. 分三种情况，每种移动和攻击各 5 次：
   - `idle`：基地里空闲的单位；
   - `attacking`：正在执行原生进攻任务的单位；
   - `defending`：矿车附近防守的单位。

   移动：`python -X utf8 benchmark\r1_override.py trial --owner <N> --unit <thing> --situation idle --act move`（默认往 +x 方向 400，可用 `--dx/--dy` 或 `--x/--y` 指定，目标点要可通行）。

   攻击：加 `--act attack --target <敌方 thing>`。目标必须是弈核 AI 当时视野内能看到的敌方单位。

   每次记录 60 秒轨迹，追加到 `r1-trials.jsonl`。
5. 跑完后 `python -X utf8 benchmark\r1_override.py summary` 生成表格。

**完成标准**：把 `summary` 表格和 `r1-trials.jsonl` 附在报告里。脚本的判定是启发式的（离目标越来越远并持续 1.5 秒算被覆盖），有明显误判的单次，在报告里标出来即可，不要改脚本去凑。

**下一步怎么走由这张表决定**：
- 很少被覆盖：直接进入 R2。
- 经常在几秒内被覆盖：先停下报告。需要单位借出机制（把单位从原生 AI 的队伍里摘出来，用完再还），我会根据结果另行安排。

### R2 原生组件：单位感知与指挥

在 Native7 原生组件（`native-ai/strategic-portable-runtime-v7/`）里新增：

1. **单位列表**：己方单位（类型、位置、血量、是否空闲）；敌方单位只输出己方视野内的。
2. **指挥命令**：移动到坐标、攻击指定目标，各带命令编号。送达结果未知时不重发，这条规则和现有指令一致。
3. **交还**：控制器结束时，把单位交还原生 AI，并确认原生 AI 恢复使用。

地址和调用方式参考 Ra3-Copilot，统一放在一张地址表里，不散落在代码中。按 AGENTS.md，不为这一步新增资格认定或证明链：注入前的逐字节校验加上单元测试就够了。

**完成标准**：在一局里用宿主侧的测试脚本，让一个己方单位移动到指定位置、攻击一个可见敌方单位、结束后交还原生 AI，三步都成功。

### R3 宿主侧控制器

在 `integration/host_runtime/` 新增两个控制器，参数从性格规则（`personality_rules.py`）读取：

1. **侦察控制器**：选一个廉价、快速的单位（优先战熊），沿路线侦察敌方出生点和矿区。看到敌方基地或矿区时，产生 `scouting_report` 事件，交给分层决策。
2. **矿车骚扰控制器**：
   - 选一小队廉价单位（优先恐怖机器人，没有就用现有的快速单位）；
   - 只攻击视野内的敌方矿车；
   - 血量损失超过“惜兵”阈值就撤退；
   - 超过“纠缠度”时间盒（铁锤 75 秒），或者矿车得到护卫，就结束，并交还单位；
   - 在决策记录里写入：击毁矿车数、损失、用时。

战术参谋的 `harass` 姿态和开局执行器的骚扰步骤改为调用这个控制器，原来的 `raideconomy` 保留作对照。

**完成标准**：一局里控制器能自动完成一次“出发 → 找到矿车 → 攻击 → 按条件撤退 → 交还”，决策记录里能看到完整过程。

### R4 对照评估

同一张 2 人图、对手中等难度，铁锤分层模式各跑 10 局：
- A：骚扰用原生 `raideconomy`；
- B：骚扰用新的控制器。

**看这几项**：第 3 分钟和第 5 分钟的敌我矿车数、骚扰击毁的敌方矿车数、骚扰损失、首次发现敌方基地的时间、胜负。

**完成标准**：20 局跑完，评估报告原样贴回来。

## 本轮已知缺口（不要自己扩展去解决）

- **兵种生产**：要用恐怖机器人骚扰，得先有恐怖机器人，但目前不能指定原生 AI 生产什么。本轮先用原生 AI 已经造出来的单位。生产偏好以后用 Mod 标志或生产队列调用另行解决。
- **秘密协议**：选点和释放都不在本轮。
- **多支编组、集火、火力覆盖**：不在本轮。

遇到这些缺口，写进报告的“建议”一节即可。
