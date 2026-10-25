# 移动终点偏差的独立只读复核

结论：现有原始数据不支持“SDK 默认在距目标 70 左右停车”，也不能确认具体是哪块水面、岸线或建筑占地。可以确认候选规划没有验证目标的地面可通行性，且三个实验分别是两个不同终点的长期停留和一次超出租约时间的绕行。原始 15 单位到达阈值保持不变，全部失败判定保持不变。

## 原始租约窗口重新计算

仅统计 native `kind=3` 且 `issued_frame <= frame < returned_frame` 的坐标，排除归还后原生 AI 的行动。输入路径、SHA256 和完整数值见 `movement-evidence.json`。

| case | 原始目标 XY | 租约帧 | 长期停点/最后租约点 XY | 目标距离 | 观察 |
|---|---|---|---|---|---|
| trial-30b1-01 | 3060,2820 | 1615..2065 | 3010,2870 | 70.710678 | 1665..2063 同点，共 398 帧跨度 |
| trial-30b1-03 | 3100,2780 | 2317..2768 | 3190,2830 | 102.956301 | 2426..2766 同点，共 340 帧跨度 |
| trial-30b1-06 | 1540,2100 | 3482..3933 | 1231.731079,2087.056152 | 308.540550 | 租约内持续移动，最小距离 233.967889，无长期停点 |

06 在归还后的 frame 4022 才到达 1530,2110，距离 14.142；这不能计为私人租约内到达，更不能把归还后视野归到原任务。01 和 03 的停点均落在 `20*n+10` 的 XY 格中心，但当前样本只能说明网格端点特征，尚未独立证明路径网格的所有语义。

## 已确认的移动 ABI 和写入

从本机 `E:/RedRar3/Data/RA3_1.12.game` 和 `tactical/all-text-temporary.txt` 提取，摘录保存在 `movement-disassembly.txt`。EXE SHA256 与旧受检构建相同，详见 JSON。

* `0x6eff70` 是 `thiscall(Update*, Coord3D*, uint32 source)`，`ret 8`。第二个栈参数最终写 `Update+0x50`；没有传入停车半径的额外参数。不要把第三参数改成距离值。
* 入口先调用 `Update+0x3c` 状态机虚方法 `+0x38`，再调用 `0x603a70(SM, target, FLT_MAX)`。
* `0x603a70` 在 `SM+0x78` 非零时不更新；正常分支把传入 XYZ 原样复制到 `SM+0x2c` 和 `SM+0x48`，清 `SM+0x44`，把浮点值写 `SM+0x54`。`0xc0d47c` 的实际字节为 `ff ff 7f 7f`，即 `FLT_MAX`，不是 70 或半径。随后入口切换到状态 ID `0x4e`。
* EXE 自带类型名区分 `UnitAICreatePathState` 与 `UnitAICreatePathExactState`。前者名称 getter 是 `0x7ee800`，vtable `0xc50f48`；后者 getter `0x7ee840`，vtable `0xc50fb0`。这里的 Exact 类型存在不等于已找到、可安全替换的用户移动 ABI。
* 普通 CreatePath 的进入函数 `0x801f90` 从 `SM+0x2c` 取目标，经过 `0x6dd230`（转发对象 `+0x10c` 的 `0x6b30a0`），再调用 `0x7a9580(Update, SM+0x2c, selectedGoal)`；`selectedGoal` 取 `SM+0x48` 或原目标，取决于 `SM+0x44`。
* `0x7a9580` 在 `Update+0x210` 非零时，把第一个目标写到 `Update+0x168..0x170`，把两个目标 XY 差写 `Update+0x174/0x178`，再调用 `0x7a9510`。这些是有静态证据的诊断候选，不能先命名为“最终可达终点”。
* `0x7f51e0` 读取 `Update+0x150` 的路径对象，再读取该对象 `+0x10` 的节点，并访问节点 `+0x0c/+0x10` 的 XY；它还会调用 `0x69d770` 修改路径。节点是起点还是终点、完整链方向，应先静态核实或只读对照已知成功短移，不能猜测。

## SDK 配置与候选规划的确定缺口

本机原版 SDK：`E:/RA3Modding/SDK/SAGEXML/Soviet/Units/SovietAntiVehicleInfantry.xml` 和 `SovietAntiInfantryInfantry.xml`：两者普通 Locomotor 都是 `TestReactiveLocomotorHUMAN`，速度 50；几何圆柱半径 5。`GlobalData/Locomotor.xml` 中这个 locomotor 的 `Surfaces=GROUND`、`FormationPriority=NO_FORMATION`、`FastTurnRadius=1`、`SlowTurnRadius=1`。`Schemas/xsd/AssetTypeLocomotorTemplate.xsd` 的 `CloseEnoughDist` 默认 1.0。它们不能证明当前加载模板每个值，但并未提供默认 70 停距或队形偏移的支持。

SDK `System/PathfindSettings.xml` 明确存在 `MaxCellsAdjustDestination`、`MaxCellsAdjustToPossibleDestination`、`MaxCellsAdjustToNearestGroundCell`、`MaxCellsAdjustToNearestValidCell`，默认搜索预算均为 400；这是引擎具有目标调整机制的本地配置证据，不能把 400 当距离值，也不能据此认定哪个分支已在实验中触发。

当前 `tactical/recon/probe.py:frontier_candidates` 仅选择玩家自己的 CLEAR 相邻 fog 格；`tactical/recon/logic.py:choose` 把格子的 XY 配上单位当前 Z。执行时比较初始 Z 与这个复制的 Z，不能验证目标真实地形高度，也不能验证 land/water、建筑占地、悬崖层、同一可通行连通分量。这个缺口已经确定，不需要用停车距离猜测。

## 下一次有区分力的只读诊断

不重复盲选 fog 点，不改变 arrival 半径，不调用未知目标调整函数。

1. 由唯一现场 runner 在已有授权的下一次单 Move 校准中，增加身份校验后的只读字段：原始请求 XYZ、`SM+0x2c`、`SM+0x48`、`SM+0x44/+0x78`、`SM+0x04` 当前状态及状态对象 `+0x04` 的 ID、`Update+0x168` XYZ、`Update+0x150` 路径对象及已核验节点坐标。取样时点：发令前、第一次路径形成、开始不动时、归还前。私有原生地址仅进入校准报告，不进入模型上下文。
2. 对成功的原来 40 单位短移先做同样读数对照，确认节点链方向和字段含义。若请求保持原样、路径终点已变到停点，是投影/裁剪证据；若路径终点仍是请求而单位停远处，应检查路径失败状态、局部碰撞或动作状态，不能自动归为地形裁剪。
3. 从受检地图文件或已核验的只读导航层，取得目标真实高度、GROUND 可通行格、静态/动态占地和同层连通性。只有 shroud 邻接不足以允许本次 GROUND 行动。若导航读接口尚不清楚，先把候选标记 `reachability=unknown` 并记录失败点，不能称已通过筛选。
4. 06 已证明直线距离不等于实际路程。未来规划需要经验证的路径长度/预计到达时间预算，或分段重新确认进展；单纯把目标置于 550 内不能保证 450 帧内完成。延长租约属于新校准，不可把旧实验在归还后到达改记成功。
5. 视野单独诊断：每一帧核对玩家 3、目标格 index/网格 origin/scale、单位脚下原生 terrain query、目标 query、单位实际所属 player 与 transfer 前后 vision。06 的近点不 CLEAR 及01的归还后视野变化需要独立处理；不改冻结 visibility 算法，也不以 observer2 的全图视野兜底。

## 复算

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' bridge-probe/strategy/reviews/movement-audit.py --self-test
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' bridge-probe/strategy/reviews/movement-audit.py
```

以上仅离线读取 JSON、EXE、反汇编和 SDK XML，未访问游戏进程、GUI、端点或密钥，未解锁任何战术能力。
