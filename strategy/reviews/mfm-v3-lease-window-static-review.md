# MFM3 租约计数边界独审

只读复核，未安装 DLL、未调用 SDK/GUI/模型，未修改执行器原件。结论仅支持 Root 批准首次现场诊断，不构成能力授证。

- DLL：`632400b1cbe1cc9e59c7f360f17633bef13251c72a3a8e04ef940f850321de5f`
- host：`e3348a5eb7aad71ba1d51f1e0539f3d13cae978c52fd29b3afb1c6d5f8ffaf6b`
- pure qualifier：`51e6a12673f300c485619f7fb6ff36252d428da564804526bfbdb6766432aede`

原生 `role_leased` 分别依据 front/support 的 detach_calls 和真实 return 标记，且必须已有 issued。issued 前清零两角色五类计数并保留 baseline71。正常与失败 cleanup 的归还均在 Transfer(true) 后立即核对 default team、设置该角色返回状态，再发 event5 并清除 tagged 调用上下文。先归还演员后续自然动作不会污染仍借出的另一个演员。

独立校验器按各角色 baseline71、detach event1、return event5 的 seq 定义租约边界；同帧事件仍按 seq 区分，不能用 frame 粗筛漏掉租约内覆盖。区间内未标记 move/attack/transfer/add/remove/stop/facade 行为和最终计数均须满足无覆盖要求。前后自然 AI 事件仍留在 raw，不删除。

独立运行 `python -m unittest -v test_mission`：41 项通过。另直接使用 `LeaseWindowTests.rec()`，分别向两角色租约内部插入 kind10/12/14/16/18/30/50、tag0 事件并重排 seq，14 个反例全部拒绝。

本次未放宽 Stop 稳定、双角色阶段几何、来源伤害、撤退或恢复门槛。MFM2 既有失败 raw 保持失败。真实案例仍须按两角色实际推进、命中、回撤和归还逐项独立重算。
