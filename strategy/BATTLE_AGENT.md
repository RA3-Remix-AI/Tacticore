# 持续 BattleAgent 与宿主任务协议

`BattleAgent` 是一个绑定 `session_id / player_id / commander_id` 的长期存活实例。`service.py` 现在默认使用它，原CLI保持兼容。它保留当前战略、敌方已见事实和时效、活动目标、执行结果、失败原因及有限对话尾部；不会每轮把全部地图/单位/地址发给模型。HTTP和文件服务都不执行游戏指令。

受视野battlefield、战术TacticalEvidence/RestorationEvidence、编队版本和三模块回执扩展见[TACTICAL_CONTRACT.md](TACTICAL_CONTRACT.md)。未提供这些可信能力证据时仍默认锁定。

## 运行和产物

```powershell
python service.py --commander <UUID> --player 3 --snapshot-file <snapshot.json> --runtime <统一运行目录> --context-bytes 8192 --max-input-bytes 16384
python battle_demo.py --runtime <纯离线演练目录>
python -m unittest -v test_battle_agent test_engine test_http_adapter
```

这台机器的`python`别名不可用，可使用`C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。只有service会请求真实配置端点；battle_demo和测试只使用本地模拟器/localhost，不读取用户密钥。

实例目录除status.json、plans.jsonl、service-health.json，还输出agent-state.json和jobs.json。状态和任务文件只含结构化允许字段，不含密钥、端点、模型原始正文。状态原子写入。`agent-state.json`是观察和诊断产物，当前不自动恢复进程崩溃后的任务；宿主重启必须重新握手并处理执行器未完成任务，不能从旧文件直接重新派发。

## 记忆及输入预算

模型user消息协议为`agent_protocol=battle_agent_v1`，只发送working_memory、delta、pending_decisions、capability_manifest、有限conversation_tail及精确绑定/快照字段。working_memory内经济/产能是聚合值，不是全单位表；敌情只能来源于通过快照契约校验的采集结果。`power_balance=null`代表未知，空敌情不能推导敌人没有兵。

事件环默认32条，范围4–64；对话默认最近2轮合法战略，范围0–4。压缩由确定性代码把被移出的事件计数、完成/失败任务计数和最后压缩时刻并入摘要，不调用模型生成历史，不臆造战场事实。已见敌情默认60游戏秒过期（可配置5–300）；超过3秒未更新的可见性降为last_seen。

summary+delta默认上限8192 UTF-8字节，可配置4096–16384。过大时按固定顺序削减旧对话、旧反馈、旧delta详情、任务详情、地区候选和旧敌情；标记details_truncated并保留最少一个失败原因。模型只能选择本轮实际收到的地区。HTTP整个JSON默认另限16384字节，包含system提示及性格，超限在发请求前拒绝。性格traits最多1200 UTF-8字节，截断显式标记。模型仍返回engine.py规定的同一个有限策略对象，枚举必须单一字符串。

最小战略持有时间、暂停、超时本地接续、过期响应和绑定守卫沿用StrategyEngine。持有计划时不发送HTTP，也不消耗delta游标；等待模型期间继续接收快照，但已经冻结的请求上下文不会被新采样改写。若等待期间有执行失败要求重评，旧回答以reassessment_after_request拒绝。模型不可延长本地旧计划的有效期。

## 宿主接入与能力证据

实际游戏宿主应在同一进程直接import，不从UI字段或CLI参数解锁能力：

```python
from battle_agent import BattleAgent, BuildEvidence
from engine import StrategyEngine, Binding
from http_adapter import ChatAdapter, TransportPool, load_profile

# 宿主先核验游戏版本、mod握手、真实电脑UUID绑定、统一租约，以及
# 生产实验真实队列/扣款/出厂判据；这些步骤不是此记录自身能证明的。
binding = Binding(session_id, player_id, commander_id, commander_name, connection_id)
engine = StrategyEngine(binding, timeout_seconds=12.25)
evidence = BuildEvidence(evidence_uuid, session_id, player_id, "game_bridge",
                         supported_foci=("anti_air",))
agent = BattleAgent(engine, build_evidence=evidence)
profile = load_profile(library_path, commander_id)
adapter = ChatAdapter(profile, pool=TransportPool(2), total_timeout=12)

agent.observe(own_only_snapshot)       # 采样时持续更新
result = await agent.decide(own_only_snapshot, adapter)
proposals = agent.jobs()              # 供独立执行宿主检查
```

BuildEvidence是可信宿主的应用断言，不是加密证明。默认只涵盖anti_air；增加已验证方向时才扩展supported_foci。source和session/player必须匹配。CLI没有创建或导入BuildEvidence的开关，默认所有主动能力unavailable。

模块分别为build、raid、attack、combined_arms；每个任务含状态、预算和资源锁。共享production_queue/main_force/raid_force或总预算冲突被标为blocked，不伪称执行成功。未验证模块始终unavailable；其战略意图可以保留，但不会成为真实调兵命令。native_baseline是零开销被动本地AI计划，不是可派发主动任务。

## jobs.json

根对象包含schema_version=1、agent_protocol、binding、source、snapshot_id、execution_authorized=false以及jobs数组。每项包括：

- task_id：宿主exactly-once去重键。
- plan_id、generation、expires_at_game_seconds：任务产生的模型计划与世代、原计划期限。
- module、purpose、focus、target_region：有限意图，不含地址、代码或任意单位模板。
- status、reason_code、updated_at_game_seconds。
- spend_fraction、force_fraction、resource_locks、priority：抽象任务协调预算。
- budget={unit:"fraction_of_observed_credits",fraction:0..1}：只给比例；真实credits金额、单位数、前提条件、剩余资金由宿主再次校验，禁止直接把比例当金额。
- host_dispatch_candidate：仅当宿主提供对应BuildEvidence、主动build任务planned且等待派发时为true。该标记本身不授权执行；宿主仍需会话/player租约及能力核验。

同一个plan内的refresh/hold维持task_id，completed/failed/cancelled不再自动派发。新的合法模型plan允许新generation补充生产，避免一整局只造第一单位；这也意味着每个计划最多一个相应方向的宏观建造任务，具体数量由宿主有界解释。已started的active任务跨计划沿用原task_id，不会重复排队；即使原计划过期也保留到回执，不能把它当新候选任务。完成任务历史最多16项，较早结果进入确定性事件摘要。

## 执行反馈API

宿主通过`agent.record_feedback({...})`注入下列精确字段；CLI不监听任意文件回执，也不通过回执解锁能力：

```json
{"session_id":"<当前session UUID>","player_id":3,"commander_id":"<当前commander UUID>","task_id":"<已知任务ID>","status":"started","reason_code":"ok","at_game_seconds":120.0,"source":"game_bridge"}
```

status允许started/completed/failed/blocked/cancelled；reason_code允许ok/insufficient_funds/prerequisite_missing/no_route/target_lost/not_verified/execution_error/expired/lease_lost。时间必须有限，不早于该任务上次状态时间，不晚于当前观测时间。绑定必须精确匹配；只能反馈已验证主动build任务，拒绝未知任务、未验证能力、终态重复和额外字段。

正常生命周期：宿主接受后started，真实完成检查后completed；不要把“命令发出”当completed。失败/阻塞保留失败原因并让引擎提前重评，语义相同请求20游戏秒冷却，等待期间旧模型回答不能覆盖该失败。宿主必须自己持久化执行器任务与exactly-once记录；BattleAgent不操作游戏线程、不保证跨进程崩溃的事务原子性。

## 验证边界

本模块通过本地测试验证持续记忆、60轮压缩、失败接续、能力/预算/锁冲突、多实例隔离、HTTP超时和任务去重。它不声称真实整局对战、生产执行器或raid/attack/combined_arms已通过；这些证据由游戏宿主独立验收。
