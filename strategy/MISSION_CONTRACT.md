# Persistent continuous mission contract

`missions.py` owns one stable task's strategic memory and locks. It never emits
SDK calls. One bounded native executor lease owns approach, preparation, attack,
retreat and return; progress polling never creates new native orders. Existing
primitive evidence cannot enable this protocol.

## Trusted capability and commit

```python
from battle_agent import MissionEvidence, MissionObservations

evidence = MissionEvidence(
    evidence_id, session_id, player_id, commander_id, source,
    (("attack", ("main_attack",)), ("raid", ("harass_economy",)),
     ("combined_arms", ("coordinate_force",))),
    max_duration_game_seconds=300,
)
# Construct only after independent new raw/grant verification, not from model JSON.
agent = BattleAgent(engine, tactical_evidence=purpose_proof,
                    mission_evidence=evidence)
agent.host_commit_task(task_id,
    mission_deadline_game_seconds=committed_expires_frame / 15,
    retreat_region="home_base")
```

The stable mission ID is the canonical UUID form of `task_id`. The board freezes
target contact, purpose, formation versions, requested roles, force budget,
retreat region and absolute deadline. Repeated commit is idempotent only with the
same parameters. The task remains `dispatch_pending` or `active` across 45-second
plan expiry/refresh. A new plan with an explicitly different target requests
retreat; ordinary TTL expiry does not. Formation, module and budget locks remain
held until a proven safe terminal outcome. Same-target failure backoff survives
roster-version changes. A game-time deadline never auto-completes or releases an
unknown mission.

Continuous missions require a currently visible enemy ground contact, including
`coordinate_force`. Harassment additionally requires role `economy`; the real
executor and native qualifier still restrict exact templates and weapon scope.
The model must supply its own opaque contact and formation IDs from the frozen
message. The host does not silently add a target to a model's coordinated order.

## Progress versus evidence

```python
agent.record_mission_progress(task_id, receipt["mission"],
    observations=MissionObservations(
        target_currently_visible=host_current_visible,
        distance_to_goal=receipt["mission"]["approach_distance"],
    ),
    evidence_sha256=bound_published_report_sha256,
)
```

The `mission` dictionary has exactly:

```json
{
  "mission_id": "canonical task UUID",
  "stage": "approach",
  "revision": 123,
  "observed_frame": 1560,
  "deadline_frame": 5700,
  "approach_distance": 400,
  "own_hp": 70,
  "damage": 0,
  "reason": "active"
}
```

Stages are `approach`, `prepare`, `engage`, `retreat`, `restored`. Revisions are
strictly increasing published native event sequence numbers; a duplicate must
be identical. Polling may skip short phases, so phase telemetry never proves a
complete chain. Backward phases, changed deadline, nonfinite values, changed
mission identity and arbitrary reason text are rejected. Native reasons are the
15 fixed labels shared with the executor. Observations are trusted host facts;
their verification booleans may remain false while telemetry advances. Reported
damage does not become verified source damage merely by appearing in progress.

After independently requalifying the complete raw trace:

```python
agent.certify_mission_result(task_id,
    observations=MissionObservations(
        target_currently_visible=False,
        approach_verified=actual_approach_proved,
        source_damage_amount=actual_bound_source_damage,
        coordination_verified=actual_two_role_coordination_proved,
        retreat_verified=actual_retreat_proved,
        restoration_verified=actual_control_release_proved,
        distance_to_goal=final_progress_distance,
    ),
    evidence_sha256=final_raw_report_sha256,
)
# Then the existing strict record_feedback started/completed/failed lifecycle.
```

This enrichment does not invent a new native revision. Completed attack/harass
requires verified approach, positive attributed damage, actual retreat and
restoration. Coordinate additionally uses its independent coordination fact.
Progress alone does not satisfy those gates. Unknown or unrestored work keeps
its lock and is quarantined on generic service stop.

For an explicit persisted client rejection before issuance, use
`certify_mission_not_dispatched(task_id, evidence_sha256=...)`, then ordinary
cancelled feedback. This is accepted only while reserved with no started receipt
or native progress. It records safe no-dispatch evidence without fabricating a
native stage/revision, retreat or effect.

For a unit that becomes invalid during a mission, first independently reverify
the dedicated disposal sidecar (same actor/session/command, two advancing native
frames without the object ID, all 14 original hook entries and timer cleanup).
Only then call `certify_mission_disposed(task_id, evidence_sha256=...)`. It retains
the last real phase/revision and records `disposed_verified`, not a native return
or a fictitious restored phase. Only failed/cancelled feedback with proven
restoration may release this task. It can never count as completed, retreat or
purpose coverage. Ordinary telemetry cannot assert disposal, and unknown
disposal remains locked/quarantined.

`pending_mission_retreats()` returns task/mission ID and fixed host reason for
the bridge to send one idempotent retreat request. It does not stop the executor
globally or release reservations. Host reasons and native telemetry reasons are
separate enumerations.

## Terminal drain clock

Daily future progress is rejected/deferred until the next real collection.
During terminal drain only, `record_mission_progress` accepts optional
`verified_terminal_clock=observed_frame/15` when stage is `restored` and the host
has already independently proved restoration. The immutable deadline remains
unchanged. Read-only final observation is bounded to deadline +90 frames; actual
native issuance/return must still satisfy the original deadline in the raw
verifier. The override neither advances the battlefield snapshot nor triggers a
model request.

## Model memory and independent harassment audit

The bounded `working_memory.persistent_missions` contains active targets, phases,
retreat requests and qualified effect coverage. Full local history is capped at
8 missions. Completion/failure counters survive history compaction. Prompting
asks the model to consider useful uncovered purposes when current facts and
capabilities allow; no hardcoded task is injected to manufacture coverage.
Attack and coordinated missions retain the existing shared `main_force` lock.

`tactical/mission_qualification.py` separately checks economic semantics using a
host-created `TrustedHarassRoute`, then calls the producer's independent complete
native mission qualifier. It checks exact refinery function/type, contact and
actor identity, child UUIDs, session/player/commander, frozen deadline and trusted
retreat. A calibration can establish economic capability without being a formal
model-task result. Formal success additionally requires a matching `raid` /
`harass_economy` completion receipt. Renaming a main-attack receipt, a WarFactory
or a damage counter does not establish harassment. Tests mock the native verifier
only to test this outer boundary; they are not field evidence.
# 整场只读审计（新增）

`mission_audit.py --session <run/session.json>` 从现成文件检查持续任务生命周期，并调用 integration 的纯原始证据校验器复核三目的效果与控制释放。它不连接游戏、调用模型或写目标run；结果写到标准输出，若需保存请使用新审阅文件名，不能覆盖原件。

BattleAgent 配置 `memory_path=.../agent-state.json` 时，会在真实 adapter 调用前追加 `agent-state.context-audit.jsonl`。该日志只保留同任务的opaque身份/目标ID、phase/deadline、压缩计数、输入字节数和SHA，不记录请求正文、坐标、端点或密钥。持有旧计划而未实际请求模型不会产生伪请求记录。

审计分别报告：同ID跨原plan TTL、其它新计划被接受期间仍存续、压缩后实际模型请求仍包含该任务、one dispatch、阶段revision单调、actor租约是否重叠，以及终态原始效果/释放。三目的真实效果与至少一个跨TTL/多计划/压缩的任务都存在，且宿主无fault、无未结束/未证实任务时，才可能给出整体验收通过。

旧run缺少context元数据时明确输出observability gap，不以静态代码或最终memory推断当时发出的模型上下文。伤害量不自动等于经济压制或胜利因果。
