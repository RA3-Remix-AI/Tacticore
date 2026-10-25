# Ground v2 与角色路线独立只读复核

仅本地读取、纯校验与测试，不调用 SDK/GUI/API，不修改生产组件、冻结原件或现场数据。

独立运行 `test_grounded_status_v2` 10项、`test_surface_route_client` 5项，以及 `mission-formation-v3/test_role_route_planner` 当前15项，合计30项通过。

Ground v2限定精确Cons/Flak ground-only模板，检查同帧两读的XYZ/HP、缓存有效位、有限height≤0.5、七状态字、无已知air/garrison/immobile、holder0及完整identity绑定。ground160只作诊断；未知、Bear和死亡不成为可用地面演员。client重新运行纯verifier，再匹配实际objectID/type/address/owner；没有合格样本时保留unknown原因，不宣称无军队。

实际只读控制文件 `acceptance/runs/20261025-122359-commander/ground-v2-controls-expanded-frame2160-readonly.json`，SHA `f276ba5f7242ce55bed6a4e7aec56a654e5ab888da7e7b1ea96e0fe4932ca20d`，frame_start=end=2160。独立重算7条record的结果与缓存判定一致：

- Flak788：HP120、cache0x7、ground160=False，grounded True。
- 775/798：HP0，grounded False。
- 801/805：实际garrison flag True，grounded False。
- 792：cache0x1无有效位且HP0，grounded False。这是混合负例，不能把现场结果仅归因于cache无效。
- 769：scope外模板，unknown/ineligible。

角色路线从完整版本2来源记录核验两helper指纹、同session/PID/玩家、真实帧和对象/HP/XYZ/七字/cache绑定。旧源、Bear、unknown均拒绝。前进段要求朝离开held support的方向，首段60..140、后段40..160；dot≥0与初始gap≥25的简化等价于该两段直线几何的holder排除。逆向按support-first真实阶段顺序检查两段clearance。旧route0反穿后排case被拒绝。搜索有时间/深度/状态上限，不用插值制造历史节点。

这些只证明当前地面点和有限角色几何，`walkable_route_verified=False`保持明确。真实路径障碍、地形、动态单位、推进/伤害/撤退及恢复仍须新raw逐项验证，不能由本报告授予任意边可走或战术效果能力。

## 追加：任务演员入场守卫

独立核 `mission_actor_admission.py`（SHA `9635d39a64e65ec95a67a757a4a4212c1835ae539cd00a44ba22a88ed999335b`）：地面点正证与演员可借出资格分离。守卫同帧双读Update、状态机及状态回指，限1/16、idle path0、SM低16锁清，并在后续ground再采样完整相等后才允许。任何普通1/16的回指不符合也保持unknown/ineligible，不得绕过。

独立运行5项 `test_mission_actor_admission` 全过，另6个Update→Thing、State→SM、SM→Thing、vtable或pointer损坏反例全部拒绝/unknown。直接读取精确EXPECTED SHA的本地游戏EXE，复核audit里的getter字节、ASCII名称、构造器VT写、注册字节及State+4写，确认54为 `UnitAIMoveToGoalAndEnterState`，77为 `UnitAIGarrisonedState`；不是只凭数字或汇总命名。

该守卫不保证采样后所有权；原生租约内干扰检查继续必要。没有把入场资格升级为路径可行或战术效果证据，未实际运行SDK。普通正常演员的新回指现场样本仍应单独保留验证，未知不能自动变为通过。
