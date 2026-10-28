G6 纯战术规划与重放模块

范围
本目录新增可调用的软件，复用现有 Snapshot、Battlefield、TacticalIntent、Mission 和 MissionProgress。
main_attack 选择当前可见的地面目标；harass_economy 只选经济目标；coordinate_force 要求步兵与防空角色，等待组合准备回执。
规划建议覆盖 approach、prepare、engage、retreat、await_host_release、closed_reported。
这是建议缓存，不是另一个 MissionBoard、租约、任务账本或原生控制器。不会发送模型或游戏请求。
所有输出固定 execution_authorized=false、field_verified=false、mission_completed=false。
host 报告 restored 只会停止此建议槽位，不认证控制归还或任务完成。

运行测试（在 strategy 目录）
  ..\.venv\Scripts\python.exe -B -m unittest -v tactical_planning.test_planner
  ..\.venv\Scripts\python.exe -B -m unittest -q tactical_planning.test_planner test_missions test_purpose_roles test_visibility_boundary test_tactical_contract

运行重放（在 strategy 目录；只接受 simulated 来源）
  ..\.venv\Scripts\python.exe -B -m tactical_planning tactical_planning/example-main-attack.json
  ..\.venv\Scripts\python.exe -B -m tactical_planning tactical_planning/example-harass-economy.json
  ..\.venv\Scripts\python.exe -B -m tactical_planning tactical_planning/example-coordinate-force.json
样例全部为显式合成观察与回执，evidence SHA 为假样本，绝不授予实机权限。
同一输入产生相同建议序列和 digest；CLI 拒绝重复 JSON 键、非有限数、额外字段、超大输入和 live 来源。

对现有 BattleAgent 的实际适配 API
  from tactical_planning import plan_batch_for_agent, context_hints
  results = plan_batch_for_agent(agent,
      ['main_attack', 'harass_economy', 'coordinate_force'],
      memories=previous_memories, feedback=current_mission_progress,
      game_frame=host_observed_frame, monotonic_ms=host_monotonic_ms)

读取的是 agent.latest、agent.engine.binding、真实 capability_manifest、隔离编队和其他在途任务。
缺少 verified_purposes 或目的角色权限时等待，不凭 planner 存在就开战术。
批量输出按调用方明确优先序排队，已提议编队不能再被另一建议复用。
建议 TacticalIntent.public() 已与现有 validate_intents 互通。
新增实际集成测试分别把三个 purpose 的建议经过 BattleAgent.decide → validate_policy/TaskCoordinator → planned 任务，仍不授执行权限。

最小接线点（本交付不改其他文件）
1. strategy/battle_agent.py 的 context()/decide 构造模型上下文处：在已有可见联系人和编队裁剪之后调用
   hints = context_hints(results, context=payload, max_bytes=remaining_budget)
   再把 hints 放到 working_memory.tactical_planning_advice；仍运行原有最终字节预算/裁剪。
   context_hints 会拒绝把已被该次上下文裁掉的联系人/编队通过建议重新带回模型。
   注意 remaining_budget 必须至少256；不足则明确本轮无建议，不跳过旧上下文预算。
2. integration/battle_host.py 或其战术调度适配器：向规划调用方注入当前模拟帧与单调时钟；保存建议缓存。
   模型最终输出继续经过已有 validate_policy、TaskCoordinator、MissionBoard 和能力/账本/原生边界。
   不可把建议 action=propose/continue 直接翻译成 SDK 调用。request_retreat 必须关联真实任务 ID，进入原撤回路径。
3. 第一次真实任务由 TaskCoordinator/MissionBoard 建立后，以真实 Mission 代替建议 task UUID：
   memory_for_mission(binding, latest_snapshot, actual_mission,
       game_frame=host_frame, monotonic_ms=host_now,
       issued_monotonic_ms=original_persisted_task_time, generation=host_generation)
   原创建时间、总deadline、编队版本、target和真实task_id保持；原单调时间缺失时应恢复持久事件，不得用now重置期限。
   当前任务 MissionProgress 由宿主传入，并核对 task/mission/session/source/target/formation/序号。
   旧战略TTL刷新不会重派或更新目标。目标丢失、换region、角色/编队改变、权限撤销、停止、期限和原生干扰都会请求撤回。
   未有原记忆的活动 Mission 不会被自动覆盖。换局丢弃旧建议，不向新会话发送旧停止请求。

尚未解决的完整 G6/G0–G8 验收项
- 本模块不是已授权的攻击、经济骚扰或协同执行器，不证明真实伤害、物理回撤、归还或自然结算。
- 当前支持固定角色政策：主攻/骚扰为infantry，协同为infantry+anti_air；其他角色/空海目标不自动放行。
- 接近/准备/交战是高层建议；公共观测没有路径图、射程或HP，本模块不虚构威胁路线或生命值阈值。
  长程可达/路线威胁/射程与退路，仍需主线增加真实己方视野和原生能力接口。
- 新规划建议必须有真实调用者接线。上述最小接线未由本目录擅自修改活动 BattleAgent/宿主。
- 真实经济/科技/扩张/侦察动作、三战术逐项实效、长任务、模型整局和 G8 对照仍全部保留。

本目录的改动没有更改已有模块、当前游戏会话、登记、客户端、原生DLL或历史证据。
