# 连续任务正式局独审清单

本清单仅定义后续真实日志的核验办法，不代替实机结果。原始 run、模型输出、执行器报告及已失败案例保持原样。

## 身份与连续性

从 session、lobby scenario、host identity、进程生命周期和连续快照核对同一局、同一电脑玩家及 commander UUID。统计实际模型 attempt、HTTP/JSON 响应、接受和固定拒绝码，分别报告；不能用响应数推断末请求已取消。

每个 continuous dispatch ledger 的 `model_plan_id`、`model_plan_generation`、`model_plan_expires_game_seconds` 与独立 hard expiry 联结。若任务跨原计划 TTL，必须能观察到同 task/command/actor allocation/target/deadline 保持不变、progress 继续推进且未重新 submit。模型后续改计划不等于原任务失效。

## 任务与控制释放

将 `mission_progress_observed` 按 task/revision/frame 联结对应 published native event 与 raw SHA，阶段反馈只作遥测。检查 revision 单调、重复轮询无新命令、总 deadline 不被 progress 延长。记录已请求撤退的原因及请求次数；请求本身不证明撤退达成。

同一 actor 只能在已独立证明正常返回、可信 no-lease 拒绝或独立死亡释放后再派。失败、超时、未知状态或全局 stop 不能自行解锁。no-lease sidecar 必须保持 return/restoration/completed 为 false，不能伪造原生归还。

## 效果与来源

逐条完成回执重新读取 raw 并运行相应固定版本 qualifier；不接受缓存 qualification 或 dispatch 数。分别统计 attack、harass、coordinate 的真实接近、来源伤害、撤退和完整控制释放。骚扰必须是已审精确 economy 模板和该任务明确锁定的目标；main 标签命中经济建筑不自动变成独立骚扰任务。

伤害必须有同订单/武器/来源/目标的实际 DamageInfo 和 HP 提交依据；耗弹或总 HP 差不能单独替代。协同另外核双角色同 tick 几何和角色效果，不用两个 Move 冒充。

逐失败任务保留真实原因和阈值，包括 native error、期限、距离/路径停滞、失视野、prepare、伤害链、部分死亡和返回失败；不在审计时放宽阈值追认。

## 整场结论

最终至少列出各目的任务数、真实 started/qualified/failed/unknown 数、来源伤害量、持续时间、跨 TTL 个数、安全释放状态、记忆压缩/上下文上限和宿主断档。`integration/audit_mission_effects.py` 可辅助独立重算三目的覆盖，但还须检查全过程生命周期。

命中 5 HP / 2400 HP 仅证明有界执行链路，不能称经济压制、战略强度或胜利原因。结算胜者另外依据原生状态和 runner 保留的游戏 UI，不能只看 result_candidate。

## 本轮离线核验

- MCT3 late-origin 与 native-gate：`test_mct3_origin_gate`、`test_mission_combat_v3`，独立运行 17 项全部通过。implicit 退点在最后 pre-native 只读采同一演员真实位置；explicit fixed 保持固定。gate 交叉核演员/owner/commander/线程和 14 个精确原始入口，未取得控制不伪归还。
- 连续宿主耦合：`test_continuous_bridge`，独立运行 12 项全部通过，包括跨 plan TTL、未来终态 drain、首次轮询死亡、预派发拒绝、重复 progress 与撤退后保留锁。
- MFM2 最小修正另见 `mfm-v2-static-review.md`。以上仅离线/静态结论，所有新能力仍须真实 raw 逐项证明。
