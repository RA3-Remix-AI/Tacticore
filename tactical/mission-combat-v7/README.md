# MCT7：短促 AK 骚扰，独立候选

只在新的真实报告通过后授予能力。V6 的 90 HP / 18 次命中后死亡仍为失败；本目录不修改该报告或冻结资产。

固定策略是 `brief_raid_single_order_native_burst`：安全初始正常 Stop 后提前准备 AK，完整视野/合法记忆导航接近，最终正常 Stop 与当前视野确认，再下 **一条**正常 ScriptAttack（source1、原生连发）。目标为 `min(30 HP, 20% × 入场当前可见 HP)`；首次 Attack 起交战上限 **60 个逻辑帧（4 秒）**，达到目标或安全条件则提前撤退，不保证输出 30 HP。时间由游戏线程定时回调检查；如果调度迟到，立即按超时撤退，验收仍严格要求实际 Attack→Stop ≤60 帧，不把迟到当成功。

默认血量撤退比例 .8，合法范围 .2..8。低血、失视野、取消、异常指令、武器身份失配、总期限等安全退出保持。接近期只记最后合法目击点，900 帧记忆有效期；隐藏时不读/更新目标坐标与血量。完整任务原总期限 ≤4500，接近 ≤2100，回撤 ≤1800 不变。返回必须真实移动到冻结退点、3 个不同逻辑帧在 XY15/Z10 内、正常 Stop 和活体原生公共池归还。死亡只可另行只读证明独占控制释放，永远不算回家或完成。

同帧已实际达标又触发低血量退回时，仍优先立即退回且保留 `reason=low_hp`；仅在原生交战阶段，退回前先作既有自身武器纯读采样，避免漏掉刚发生的最后一发，再在正目标和实际伤害/致死证据满足时同步记录达标。不增加攻击、移动或等待，不读取隐藏目标；同帧重复采样没有新弹药变化就不产生新事件，武器身份错误标记也不会清除。独立验收允许这个真实低血退回分支，但仍须重算所有原始命中、目标和活体返回条件。接近期目标0、未达标、伪造低血样本、无返回或死亡均不能完成。首次SDK之前的 d099 与中间3f4d候选分别存档，无现场证据，不再部署。

源能力资格与运行时完成分开：

- `mission_combat_v7_qualification.py`：完整归因、目标和物理闭环，外加至少6个同源 AK/GUN hit、至少6发真实消耗、至少1个自然完整 refill（前后均有同源 hit）、hit 跨度至少15帧、实际回撤位移至少120。记忆 loss/reacquisition 与长接近的额外源准入由 Root 另行独立验证。
- `mission_combat_v7_runtime_qualification.py`：同一严格原始验收，仅移除上述“证明能力来源”的多发/长回撤条件。合法低血目标被真实击毁或短爆发达到目标后完整返回可以完成，但不谎称证明6发能力；超时未达标是 partial/failed，即使归还安全。
- 两者的 `qualify(report)` / `qualify_path(path)`、`control_release(report)`、`progress(report, mission_id)` API 保持。公开 progress 仍是9字段，早准备映射 approach。

准入限定精确征召兵、GroundedStatusV2 正证、helper2 的 state1 / 精确 Attack10(vtableC548C0) / idle16；拒绝7/54/77、锁、air、garrison、holder、dead 等。state10 现场接管证明仍须 MF4 对照，不能仅凭本目录离线测试授证10。模型不接收地址、按钮或私有坐标。

协议 `MCT7v15` / magic4d435437 / WM_APP+384；独立 DLL、mapping、timer：`TacticalMissionCombat7.dll`、`Local\RA3TacticalMissionCombat7_<PID>_<token>`、52413384。Event852 / Tactical3490916 / events1124；14入口，restore16383。旧目录全部保持。

仅由唯一现场 runner 串行执行（当前 MF4 任务结束且实际恢复后）：

```powershell
python bridge-probe/tactical/mission-combat-v7/lease.py --session <active-session.json> --natural <natural-production.json> --object-id <CURRENT_CONSCRIPT_ID> --mission-file <trusted-mission.json> --proof-file <fresh-visibility-proof.json> --contact-id <CURRENT_VISIBLE_CONTACT_ID> --command-id <NEW_UUID> --task-id <NEW_UUID> --seq <NEW_SEQUENCE> --expires-frame <FROZEN_DEADLINE> --post-frames 30 --execute --output <NEW_RAW_PATH>
```

可信 mission 输入 schema_version1 + implicit_actor_origin（或已有真实退点）、engage_frames60、retreat_hp_fraction.8；approach2100/retreat1800默认。父级 field helper 必须显式允许 v7，禁止静默回退 v6。按当前真实目标/新原始数据验收，不能把 V6 旧伤害合并成新成功。

离线：`python -m unittest test_mission_combat_v7 test_mission7_native_core -q`（在 tactical 目录）。包括真实 ctypes / 编译 ABI、原 EXE 14唯一入口字节、固定策略、raw 因果/装填、短击杀与 source 分离、死亡/缺归还/隐藏刷新/抢控负例；另从实际 C++ 提取准入与交战代码，编译纯内存/时钟 stub 运行边界，不加载游戏或 SDK。软件验证不会授权能力。
