# 受视野局势和战术任务契约

此扩展兼容旧schema1快照与不带tactical_tasks的模型策略。新增字段均有严格允许清单；它们不包含原生地址、ObjectID、模板、坐标、代码或API密钥。角色现允许anti_air、anti_armor、infantry、naval、air、armor、economy、structure，未知模板不能伪装成已知角色。

## 可选snapshot.battlefield

完整样例由`tactical_fixtures.tactical_snapshot()`生成，可执行验证：

```python
from engine import Snapshot
from tactical_fixtures import tactical_snapshot
snapshot = Snapshot.from_dict(tactical_snapshot())  # 全部合成数据
assert snapshot.to_dict() == tactical_snapshot()
```

battlefield精确字段如下：

```json
{
  "schema_version": 1,
  "viewer_player_id": 3,
  "visibility_verified": true,
  "regions": [{"region_id":"home_base","relation":"self","observed_at_game_seconds":100,"currently_visible":true,"role_counts":{}}],
  "contacts": [{"contact_id":"contact_ore","owner_player_id":4,"relation":"enemy","role":"economy","region_id":"east_ore","observed_at_game_seconds":100,"currently_visible":true,"stealth_state":"visible"}],
  "formations": [{"formation_id":"formation_main","version":1,"roles":{"infantry":4,"anti_air":2},"region_id":"home_base","available":true}]
}
```

viewer_player_id必须是整数并精确等于根snapshot.player_id。电脑3只可使用电脑3视野，observer2的全图数据即使标记verified也会被拒绝。visibility_verified是可信采集器的断言，Python契约本身无法证明原生视野算法正确；宿主应验证版本/视角/地形/对象可见缓存/隐形风险后才置真。

region_id必须已经在capabilities.regions中注册。slug遵循`[a-z][a-z0-9_]{0,47}`；负网格需编码为region_m1_2等，不能放负号。region最多256项。relation仅self/ally/enemy/neutral/unknown；这是当前关系，不允许从颜色猜测。角色计数必须有限非负整数。

contacts最多64项，contact_id必须为不含地址的会话内抽象ID；纯数字或0x十六进制形式会被拒绝。采集器在内部维护抽象ID到原生ObjectID的映射，不能把内部映射送入模型。owner_player_id范围0–15，self关系必须与根player_id一致。敌我/盟友变化必须生成新联系身份，不能原ID静默换所属方。

currently_visible=true时，stealth_state只能visible/detected，观测不能比当前游戏时间旧超过3秒。unknown代表无法排除隐形或探测问题，不能当当前可攻击目标。visibility/projection.py另要求原生footprint观测及schema_version=2、object_visibility_method=native_footprint_reconstruction、footprint_live_verified=true的新proof，旧cache-only proof不能解锁新算法。last_seen由currently_visible=false表示；保留最后实际看见的位置对应region和原观测时间，禁止更新隐藏目标当前地区、时间或角色。BattleAgent只有亲自收到过该contact的已验证可见记录，才接受其last_seen；首次注入历史会拒绝unseen_contact_history。因此新的Agent应清空采集缓存，或只先投影当前可见记录。默认60游戏秒后删去过期联系，模型摘要明确标记visible/last_seen和年龄。

visibility_verified=false时contacts必须为空，不接受敌方地区、地区可见角色数据，旧enemy_observations也必须为空。即使检测失败，宿主仍可提供己方formations；不能借用观察者视野填补未知。

formations最多32项，formation_id是宿主注册的抽象编队ID，version为1..2^31-1整数。roles给非空、非全零的己方角色计数。宿主必须保证编队只含当前电脑拥有的单位、注册表成员集合互斥；成员、归属或角色变化时增加版本。契约只看到聚合计数，无法证明两个不同formation_id没有重叠单位，此项必须在宿主注册表验证。

## 模型可选tactical_tasks

合法策略仍包含原有绑定、生产方向、预算和期限字段，可增加最多3项tactical_tasks，每模块一项，精确形状：

```json
{"module":"attack","purpose":"main_attack","target_region":"east_ore","target_contact_id":"contact_ore","formation_ids":["formation_main"],"required_roles":["infantry"],"force_fraction":0.6}
```

- raid允许recon/harass_economy；attack允许main_attack；combined_arms允许coordinate_force/defend_base。
- formation_ids为1–4个已注册可用编队，required_roles必须实际存在，force_fraction为0.01..1，所有任务之和不超过1-budget.reserve。
- 同一编队不能被分配给不同任务。combined_arms至少明确两类实际存在的角色；defend_base地区关系必须self/ally。
- main_attack和harass_economy必须带当前已验证可见的敌方contact，后者必须economy角色。recon仅使用已注册地区且contact必须null；last_seen不能当作对象攻击目标。
- 地区、编队和contact必须在本次实际发送给模型的有限上下文中出现。截断后不可选择没见到的ID。
- formation版本由引擎从请求/最新快照捕获，不是模型输出字段。晚响应遇版本变化、编队不可用、contact不再可见会拒绝；计划持有期间遇此变化只阻止新派发，不擅自修改已执行任务。

本版输出仍为battle_agent_v1的summary+delta。联系记忆<=64，网络按确定性顺序最多选择12个当前可见联系和4个历史联系，优先当前目标，再按观测时间和抽象ID排序；编队详情最多8、地区候选最多12。context_limits明确标记省略数量与details_truncated。记录压缩不会生成新的敌情，所有执行反馈只收结构化允许字段。

ChatAdapter提供不触发I/O的input_size(context)，BattleAgent会把完整HTTP JSON（system提示、性格、模型名、转义开销等）与memory字节同时计入预算，按结构删减详情，绝不截断JSON字节。无法装下最小上下文时记录context_rejected并本地接续，不让整局抛异常。包装适配器若隐藏input_size/max_input_bytes方法将只能使用memory预算；可信宿主应直接传ChatAdapter或把这两个预算接口显式透传。

## 宿主能力证据

```python
from battle_agent import BattleAgent, TacticalEvidence
proof = TacticalEvidence(
    evidence_id, session_id, 3, "game_bridge",
    supported_purposes=(("raid", ("recon",)),)
)
agent = BattleAgent(engine, tactical_evidence=proof)
```

证据只允许可信宿主在真实派发、目标达成、控制来源、自然AI干扰和原生恢复测试全部通过后构造。CLI、模型响应和UI没有创建证据的开关。缺证据始终unavailable；验证recon不会顺带解锁harass_economy、attack或combined_arms。BuildEvidence仍独立控制生产方向。

purpose证据不替代具体单位类型、数量、距离、地形、租约时长和目标范围白名单；宿主必须依据实测范围再次检查。恢复原生common pool和恢复原小队不是同一件事；若受控测试只验证common pool归还，报告必须保留这个范围，不能改称恢复原小队。

jobs结构沿用task_id/plan_id/generation/expiry/budget，增加target_contact_id、formation_ids、formation_versions（`[["formation_main",1]]`）、required_roles。host_dispatch_candidate仅表示可供宿主审核，execution_authorized仍为false。宿主必须再次确认session/player租约、编队实际成员互斥、版本、当前视野、敌我关系和任务期限，再解析内部坐标/原生对象。禁止从last_seen生成原生对象攻击。

同plan的refresh不换任务ID，active跨plan保留原任务和版本，不能重复发令；新plan可创建后续任务。生产队列、主力/骚扰分组以及具体formation的冲突会blocked。任务结果不能由模型生成。

可信宿主先持久化exactly-once派发记录并reserve编队，再调用`agent.host_commit_task(task_id)`，然后才能跨`await executor.submit(...)`边界。此方法只把已验证planned任务变为dispatch_pending，不记录started，不创建native execution元数据，也不使未验证能力可执行。这样下一采样把available改为false、模型换计划或原计划过期时，待派发任务仍保留原ID、版本、期限和预算/编队锁。方法对pending/active重复调用幂等，暂停、过期、未知和unavailable新任务均拒绝。

IN_FLIGHT导出常量同时包含dispatch_pending和active，宿主不能只把active当作资源占用。收到实际native issued证据后才用started回执转active；明确尚未发出的no_route/expired等失败或取消可终止pending。pending的generic execution_error、native_interference、restoration_unverified等未知执行结果没有原生证据时不会被当作“未派发失败”释放占用。模型、CLI和任意状态文件都不能调用host_commit_task。

## 战术执行回执

仍使用BATTLE_AGENT.md的绑定/任务/status/reason/time/source，started与completed额外必须带execution：

```json
{"formation_versions":{"formation_main":1},"issued_frame":1500,"expires_frame":1650,"command_source":"game_thread_bridge","interference":"none","goal_observed":false,"restoration_verified":false}
```

此对象精确允许上述7项。issued/expires必须为有限整数，expires严格大于issued且最多相差900帧。真实source要求command_source=game_thread_bridge；模拟要求simulated。interference允许none/native_ai_override/unknown。

started仅表示已派发，必须记录实际编队版本与命令有效窗口。completed必须先有started，保持相同formation_versions/issued_frame/expires_frame/command_source，并要求goal_observed=true、restoration_verified=true、interference=none。只发出move或两条move不能证明combined_arms完成，宿主需要各角色到位/支援协同的原始证据。

未实际派发的failed/blocked/cancelled可以省略execution，不能用于已active任务。已派发任务的失败必须附execution；若恢复未验证，编队进入quarantined_formations，不会因冷却结束或新计划而重新派发。允许的新增原因包括native_interference/formation_changed/restoration_unverified/visibility_lost/goal_unobserved。

只有可信宿主验证原生恢复后，才可显式调用：

```python
from battle_agent import RestorationEvidence
agent.confirm_restoration(RestorationEvidence(
    new_evidence_id, session_id, 3, "game_bridge", (("formation_main",1),)
))
```

这也是应用断言，不是密码学证明。它必须精确对应被隔离版本，没有CLI或模型解锁途径。已失败任务仍保留失败记录；解除隔离只允许后续合法计划继续。

## 本地验证

```powershell
python -m unittest -v test_tactical_prompt test_host_commit test_recorded_tactical_review test_visibility_boundary test_tactical_contract test_battle_agent test_engine test_http_adapter
```

本地模拟涵盖视角混用、未知隐形、历史更新泄露、过期联系、编队版本、跨模块冲突、purpose能力隔离、三模块反馈、伪completed拒绝、原生干扰隔离/恢复和输入预算。不调用真实API、不发送游戏命令；真实战术能力仍由宿主与游戏侧验证。

当前107项通过；新增test_tactical_prompt覆盖真实授权目的的消息内示例、45秒窗口、combined力预算与16KB完整请求上限。input-budget-proof.json保留此前64联系/32编队/长性格的纯本地预算样本；提示词扩展后，测试按当前完整HTTP请求重新编码计算，持续检查16384及更严12288字节上限。review_tactical_report.py独立读取原始JSON，不调用或导入游戏执行器；reviews目录保存旧失败与新成功短移实验的独立复核。即使短移原语全通过，复核工具也固定raid/attack/combined_arms=False，完整战术目标需要另外验收。
Trusted purpose-level actor limits
--------------------------------

`TacticalEvidence.actor_roles` is an optional immutable tuple of
`(module, purpose, (role, ...))`. For example, a host may assert
`(('raid', 'recon', ('air',)),)` only after its air-recon proof passes.
An empty top-level tuple preserves legacy fixture compatibility; an entry with
empty roles, unknown roles, duplicate purpose, or an ungranted purpose is invalid.
This field is trusted-host input and cannot be supplied in model policy JSON.

The context exposes constraints as
`capability_manifest[module].purpose_actor_roles[purpose]`. Requested roles must
be allowed and actually present in each selected formation. Single-actor tasks
allocate only the requested role, so an infantry/anti-air roster may supply one
infantry actor under infantry-only evidence. Unallocated members do not expand
the capability scope. Combined arms retains the restriction that all nonzero
formation roles must be allowed, plus its two-role checks. Examples use the same
semantics, also rechecked before host commit. Missing constraints do not grant a
purpose. The trusted executor independently checks the allocated actor's actual
native type, role, weapon and purpose evidence.
When a purpose has trusted actor constraints, `recon`, `main_attack` and
`harass_economy` each require exactly one `required_roles` entry. Current ground
actors targeting an air contact must explicitly request `anti_air`, from a
formation that actually contains it. The host must select the actual actor
using this exact requested role, rather than choosing a different eligible
unit from a mixed formation. Coordinate-force retains both reviewed roles.

Current reviewed ground actor scope is infantry/anti_air. Future air-only recon
must have its own real purpose evidence; role metadata alone never unlocks it.

After an adapter returns, frozen-context and actor guards emit an independent
`policy_guard_rejected` audit event with binding, snapshot, game time and a fixed
allowlisted `reason_code`. The memory counter is
`metrics.post_response_guard_rejections`. JSON parse guards have their own fixed
codes; an unexpected contract code becomes `post_response_contract`. Adapter
transport failures do not receive a guessed policy-guard reason, and ordinary
engine policy validation still has its existing rejection diagnostics. No model
body, HTTP content, secret or arbitrary exception message enters this event.
This diagnostic applies to new decisions only; historical `adapter_error`
records cannot be retrospectively assigned a more specific cause.

