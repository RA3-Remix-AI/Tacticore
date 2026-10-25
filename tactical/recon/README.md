# 独立侦察校准：一次移动、真实新增视野、归还原生AI

本目录是 `reusable/` 的独立命名空间实验副本，没有修改已验收的短距DLL或冻结visibility核心。沿用同一Transfer(false)→一次Move→Transfer(true)及5处被动观察链，仅将实验边界扩大为距离20..600、lease30..450模拟帧；独立mapping `RA3ReconProbe`、DLL `TacticalReconProbe.dll`。新范围必须以真实报告验收，不能借旧120范围测试宣称通过。

root统一执行/恢复游戏。子Agent仅离线构建和只读plan，不运行`run --execute`。与combat/formation/reusable hook串行；`--after-report`检查本session最近终态31/63及active0、error0，若新进程尚无tactical lease可使用`--no-prior-lease`，实际逐字核验Move/Attack/Transfer/Add/Remove五处原始入口两次。不是仅靠命令行flag认定空闲；native安装时还会检查原签名。

## CLI

```powershell
$python='C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python bridge-probe/tactical/recon/probe.py plan --session bridge-probe/acceptance/active-session.json --output bridge-probe/tactical/recon/plan-current.json
# root恢复游戏后立即执行。计划按模拟帧90帧有效期；建议同一次exec中plan后run。
& $python bridge-probe/tactical/recon/probe.py run --session bridge-probe/acceptance/active-session.json --plan bridge-probe/tactical/recon/plan-current.json --natural <当前run/natural-production.json> --no-prior-lease --execute --output bridge-probe/tactical/recon/trial-unique.json
# 存在上一tactical lease时，用--after-report <终态报告>替换--no-prior-lease。
& $python -m unittest discover -s bridge-probe/tactical/recon -p 'test_*.py'
```

plan只读本玩家网格、己方单位和身份。候选点从本玩家CLEAR格相邻FOGGED格生成，使用公开网格几何；不读取隐藏敌目标位置。遍历全部边界格后选择本地最近可用己方单位/边界点，模型只需要地区标识。源码/hash校验完成后再刷新己方ID/owner/template/update/team/HP/XYZ/frame，执行时再次刷新，不要求原位置锁死；真实当前距离仍必须≤600、目标仍是fog/clear边界、原生AI单位身份不变。

run只有一次detach/Move/return，不定时覆盖命令。它在本地并行只读采集指定电脑CLEAR格差集、自身位置、目标格和目标地区。报告保留位图和原生ID，`model_eligible=false`；不得直接送模型。

## 验收条件

必须同时满足：

- 本轮session、命令/任务UUID、原生目标点和选中己方单位匹配。
- Native primitive完整通过，独立位置事件至少3次真实进入到达半径；不是只看函数返回。
- 原生明确仅一次detach、Move、return，owner保持，恢复31、active0、error0、return_verified1。
- 出发前目标格真实FOGGED且不在baseline CLEAR；目标格和目标region在issued..returned+2帧采样内出现新增CLEAR。
- 实际位置/身份采样有效，lease≤450帧加5帧容差，没有采集错误。

只到点、只增加其他地区视野、归还不全、在lease很久以后被其他原生侦察揭开，都不通过。新增视野与本次移动处于同一原生租约窗口，但没有宣称排除其他原生侦察共同贡献，也不宣称已证明长期持续侦察能力。

前置拒绝为0派单，不覆盖旧报告；`return_pending`必须由root继续处理，不能当作已归还。DLL及跳板与已证reusable一样固定到该游戏进程退出；关闭hook并恢复原字节后不卸载跳板，避免detour仍活跃时释放。

## 当前离线结果

18个纯规划/验收测试通过，包括：到达却无新增视野拒绝、地区有新增但目标格未揭开拒绝、租约窗口之外新增拒绝、原生恢复不完整拒绝、重复Move拒绝、错误session/目标拒绝、未知/非己方可用单位不选。

两次早期真实run前置因坐标陈旧被拒绝，派单0。已修为bind之后刷新当前坐标，并取消40单位位移门槛。拒绝文件保留；本修正不改native DLL或visibility核心。

规划诊断现写到同名*-diagnostics.json：eligible角色计数、全部边界格候选数、最近距离、前3己方候选；明确representative_region_limit_used=false。当前暂停frame6445实例有508边界格，5Conscript/1Flak，最近106.42（unit1035）。无候选时只输出no_suitable_candidate诊断，不构造可执行假计划；应使用新计划输出文件，并只在plan成功实际写出后调用run。
