# 完整局结算独立审阅：铁锤获胜

审阅范围：`acceptance/runs/20261024-192645-commander`，session `9feb4b8b-b7d5-450a-b80c-5cd1f944ccfd`，PID47332，工业区，两名参与者。仅阅读已保存JSON、直接查看两张PNG，并做一次只读采样；没有操作游戏或修改采集器。机器可审阅结论和来源SHA256见同目录 `settlement-20261024-192645-review.json`。

## 结论与证据链

**这一局可以确认：绿色铁锤（原生Player3）获胜，蓝色人类（Player2）失败。**

1. session设定两人局；同session的 `battle-host/identity.json` 读回Player3、人格ID `0x7664d9d9`、UUID `57e668b4-4d89-43bd-bc92-0dd436f046ef`，人格store/Side/包SHA核验通过。因此该电脑身份确为铁锤，而非仅依据UI名称。
2. 已保存 `battle-host/match-state.json` 在模拟帧4307、mode_raw2采到：VictoryConditions participant0的实际Player指针 `0x3321170`，Player+0x20为2、败旗1；participant1指针 `0x33224d0` 对应Player3、败旗0。记录native_index0有defeat_frame4284。这为本场人类败方提供原生证据；不是假定所有局都用“原生索引+2”。
3. 直接检查 `settlement-units.png`：下方名字/颜色区将蓝色1关联人类、绿色2关联“简单 铁锤”；图表的绿色曲线末端实际带胜利标记，蓝色曲线末端实际带骷髅标记。右下角“胜利/战败/超级武器”只是标记图例，**没有当作逐行结论**。图表端点标记与原生败旗和双人设定交叉确认结算。
4. `settlement-information.png` 信息页显示总造部队数：人类0、铁锤38。此页作为生产总量佐证，不能独立判胜负，也不能将38全部归因于模型订单。

AI的victory_frame仍为0，因此没有宣称读到了AI原生胜利事件。c0=2/c4=3仅保留为原始观察，**未作为唯一或必要胜负判据**。本次确认是“保存的原生败方证据+准确身份+结算图表标记”的联合审阅；还没有普适自动终局判别器。

## 生产执行交叉核对

独立程序核对11项条件全部通过。`persistent-production-status.json` 的14条ledger均completed，实际付款=成本，paid_verified/created/completion_observed/queue_preserved全真，各有存活采样、payment_error0；全部completion_frame不晚于4284。累计付款1595与spent_committed一致。最终state stopped、native_phase2/error0、restore_mask31、active_callbacks0。**31是恢复位掩码，不是生产31个单位。**

`battle-host/host-status.json` 的task_counters.completed仍13，落后于执行器最后一条完成回执；最终完整订单数以逐条执行器ledger的14为准。该不一致没有被悄悄改写。生产总量38也不等于模型14条生产订单。

本轮人类对手是闲置集成槽位，session明确competitive_benchmark=false；这证明具名LLM电脑的端到端完整局运行及真实订单完成，不能据此评价竞技胜率、模型胜因或性格可辨识度。

## 离局后的追加采样

独立read_match_state对PID47332追加只读读取时，原生已重置到frame0/mode9、participants为空、结果帧清零；保存于 `settlement-20261024-192645-readback.json`。这不是结算当时的独立活体复采，也不推翻先前已保存frame4307数据。没有使用迟到样本推断胜负。

因此后续自动化须在退出结算前固化状态/身份/截图；同PID、同GameLogic指针并不足以证明仍处于同一对局。当前审阅没有改动旧采集器固定的match_ended_verified=false字段，独立review明确本场联合证据已核验完成。
