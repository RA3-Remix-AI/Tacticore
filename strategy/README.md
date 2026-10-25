# 策略服务：离线验收模块

更新（2026-10-25）：本文下方说明最初离线`StrategyEngine/demo.py`，不代表整个项目仍仅离线。持续`BattleAgent`、HTTP适配器及`../integration/battle_host.py`已接通己方视野、真实生产和受控战术任务，并完成铁锤对原生奥列格的完整比赛。模型56次请求、177次记忆压缩，整场链路成立；本场攻击/骚扰目标均未完成。当前证据与限制见 [本轮结果](../acceptance/vision-tactics-status.md) 和 [独立验收](reviews/formal-match-034721-independent.md)。

本目录只使用 Python 标准库，负责验收项3的**契约、决策接续和日志**。后续已增加独立HTTP适配器和读取桌面DPAPI配置的文件快照服务，见HTTP_SERVICE.md；下面的demo仍完全离线。没有游戏内存接口、生产执行器或自动接管。即使输入标为 `game_bridge`，执行仍禁用，状态为 `read_only`。不能据此宣称模型在真实战场制定并执行了策略。

## 运行

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest -v test_engine
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\demo.py --write-fixtures .\fixtures
```

从本目录运行。`demo.py`只使用本地合成适配器，生成 `runtime/status.json`、`runtime/plans.jsonl` 和 `runtime/acceptance.json`。`fixtures/offline-status.json` 可供桌面只读导入，另有空闲和回退状态样例。没有真实服务启动/停止CLI；`StrategyEngine.stop()`只停止本实例决策，不操作游戏进程或其他实例。

## 绑定和接口

`Binding(session_id, player_id, commander_id, commander_name, connection_id)` 对每个实例固定。桌面生成的UUID可直接传入；session_id要求标准UUID格式，player_id要求0至15的整数。`commander_id`、`connection_id`为本地不变标识；指挥官名字可修改但不参与绑定验证。连接ID仅用于本地状态，**不会传给模型适配器**。

`engine.observe(snapshot)` 更新结构化局势。快照必须匹配会话/玩家，编号与游戏时间不能回退，同编号内容不能发生冲突，来源不能在同一实例中改变。新对局或读档导致时间倒退时应创建新会话及引擎实例。

`await engine.decide(snapshot, adapter)` 返回 `Decision(status, reason_code, plan)`。adapter为异步函数，仅接收局势和commander_id，返回一个策略字典或JSON。多个实例可复用同一个连接adapter；响应必须精确回显各自commander_id、session_id、player_id和请求snapshot_id，避免串流。未来的真实控制宿主还需为一个会话/玩家维护唯一控制租约，本模块不提供游戏执行权。

适配器示例：

```python
async def adapter(context):
    # 未来可在这里调用连接库；不得把密钥、HTTP响应正文或异常文本写入计划日志。
    return finite_policy_dictionary
```

## 局势契约

完整可解析样例见 `fixtures/snapshot.json`。允许：

- 会话、玩家、快照编号、游戏时间、暂停状态、来源。
- 资金和电力摘要，真实采集器提供的生产队列数量、空闲生产设施数量和己方兵种职责计数。电力显式允许null表示未知，不代表0或停电。
- 本地注册的生产方向和区域ID。`native_baseline`必须始终可用，表示不干预原生生产逻辑的回退意图。
- 敌方目击记录必须区分当前可见和最后目击时间，时间不能位于未来。**这不能验证战争迷雾公平性**，采集器必须自己过滤隐藏信息，尚未实现该采集器。
- 有限事件：基地受袭、发现空军、重大损失、阶段改变。事件应为新事件通知，不应每个快照重复同一告警。

不接受对象内存地址、未知字段、任意代码、不可注册目标、NaN/Infinity、布尔值冒充整数、负资源或未来情报。

## 策略契约

完整样例见 `fixtures/policy.json`。允许 `defend/scout/pressure/raid/expand` 姿态，有限生产方向、经济策略、科技策略，注册区域和5至60游戏秒有效期。

预算为经济、军队、科技、预留四个0至1比例，总和必须为1，预留比例限制在0.05至0.6。**预算是意图，不是批准花费**；未来执行器必须检查真实资金、供电、科技、生产设施及建造空间。引擎不假设原生AI能直接执行策略JSON。

JSON限制16 KiB，拒绝重复键、未知字段、非有限数值。模型没有自定义plan_id或任意文本日志字段，plan_id由协调器生成。

## 失效与稳定性

- 默认模型期限2秒墙钟，晚返回不能自动提交；超过期限后取消在途请求。
- 即使适配器拒绝响应取消，也不会无限生成并发请求；在旧任务实际结束前，后续请求使用本地接续。无法强制结束不合作适配器的网络线程，真实HTTP适配器仍必须实现传输层超时。
- 默认接受最近10游戏秒内、严格绑定原请求的响应；较新快照允许存在，但会重新检查能力/目标及重大新事件。
- 有效模型计划默认保持至少15游戏秒；重大事件可以提前重评，但最短2游戏秒内不反复请求。相同战略意图的刷新不增加plan_changes指标。
- 无效回答、超时或异常优先继续仍有效的旧计划，**不延长它的到期时间**；失效后创建10游戏秒的保守 `native_baseline` 回退。基地遭袭时不延续进攻姿态。
- 暂停不发模型请求，不按墙钟消耗计划寿命；等待中发生暂停不会提交新计划。
- stop使在途响应失效并清空计划，晚返回不能复活它。停止不是向游戏下达“停止移动”。

## 桌面只读状态协议

`schema_version=1`；`service_state`为 `idle/planning/holding/fallback/stopped`。`mode`为 `simulation` 或 `read_only`。`source`与`provenance`均提供 `kind`、`description`。

`binding`含 session_id、player_id、commander_id、commander_name、connection_id、computer_verified。**本模块始终 computer_verified=false**，因为未连接可信的电脑玩家识别器。

`latest_snapshot`含快照编号、游戏时间、暂停状态；`current_plan`为有限策略与到期时间或null；`last_result`为固定状态和原因码；`execution`始终 `enabled=false`、`dry_run=true`；`metrics`含 requests、accepted、rejected、timeouts、adapter_errors、plan_changes。

状态写入采用同目录临时文件后原子替换，桌面只读，不修改服务文件。多实例应使用独立路径，例如 `runtime/<session>/<player>/<commander>/status.json`，不要共享一个写入目标。

审计是JSONL，只记录协调器允许的字段、枚举、快照编号和内部生成ID。不记录快照全文、模型回答、连接地址、密钥、任意模型原因文本或异常正文。commander_name只在状态中显示，不进入审计。

## 验收范围

22项自动测试覆盖绑定隔离、无效预算/目标/指令、过时响应、能力变化、暂停、停止、超时、取消、计划稳定性、失败接续、双指挥官共享适配器和日志秘密内容排除。验收结果属于本地软件行为，真实队列、资源花费、出厂单位、小队微操和模型实际效果仍由其他验收项完成。
