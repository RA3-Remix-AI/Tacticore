/**
 * Realistic mock decision records for a layered Hammer match (contract schema_version 1 plus the layered fields).
 * Used only when the `decisions` feature flag is 'mock' and by tests. Covers: run_start, the opening, commander
 * directives, staff decisions, a commander veto, an intent dropped for a directive override, record-only fields,
 * an expired and an unknown outcome, a model timeout and a final match_end record.
 */
import {parseDecisionRecords, type DecisionStreamRecord} from './decisions';

type Raw = Record<string, unknown>;

const hammer = {id: 'hammer', name: '铁锤'};

function decision(runId: string, seq: number, time: number, layer: string, fields: Raw): Raw {
  return {
    kind: 'decision', schema_version: 1, run_id: runId, seq, game_time_s: time, layer, commander: hammer,
    wall_time: new Date(Date.UTC(2026, 10, 20, 12, 0, time)).toISOString(),
    prompt_version: 'layered-v1',
    ...fields,
  };
}

const model = (latency: number, error: string | null = null) => ({
  provider: 'DeepSeek', model: 'deepseek-chat', latency_ms: latency,
  input_bytes: 4120 + latency, output_bytes: 380, error,
});
const own = (credits: number, army: number, buildings: number, income: string) =>
  ({credits, income_hint: income, army_count: army, building_count: buildings});
const applied = (...effects: string[]) =>
  ({status: 'applied', reason_code: null, native_accepted: true, observed_effects: effects});
const seen = (lastSeen: number, visible: number) => [{player_id: 4, last_seen_s: lastSeen, visible_count: visible}];
const composer = (appliedIntents: string[], dropped: {intent: string; reason: string}[] = []) =>
  ({applied_intents: appliedIntents, dropped});

export function rawDecisionFixtures(runId: string): Raw[] {
  return [
    {kind: 'run_start', schema_version: 1, run_id: runId, commander: hammer, decision_mode: 'layered',
      opening_variant: 'bear_scout_terror_raid', model: 'deepseek-chat', prompt_version: 'layered-v1'},
    decision(runId, 1, 5, 'opening', {
      situation: {own: own(10000, 1, 1, '开局'), enemies: [], threats: []},
      decision: {intents: ['scout'], objective: '战熊探路：确认对手阵营、建造方向和矿车路线',
        reasoning: '开局什么都看不见。先派战熊去敌方基地和矿区，看清楚再定打法。', valid_for_s: 60,
        recorded_only: ['protocol_pick_preference']},
      composer: composer(['scout']),
      outcome: applied('战熊已出发'),
      model: model(1620),
    }),
    decision(runId, 2, 40, 'commander', {
      situation: {own: own(7600, 2, 3, '开局'), enemies: seen(36, 2), threats: []},
      directive: {route: 'tech_pressure', resource_split: {economy: 0.45, army: 0.25, tech: 0.25, reserve: 0.05},
        primary_enemy: 4, overrides: ['no_expansion'], valid_for_s: 120},
      decision: {intents: [], objective: '科技压制：先拉经济，攀天启',
        reasoning: '对手是盟军，只有两台矿车。先不开分矿，把矿车数拉到领先，盯住玩家 4，准备攀天启。', valid_for_s: 120,
        recorded_only: []},
      composer: composer(['budgeteconomy', 'focusenemy4']),
      outcome: applied('资源倾向经济'),
      model: model(2410),
    }),
    decision(runId, 3, 65, 'tactical', {
      situation: {own: own(5200, 4, 4, '上升'), enemies: seen(60, 3), threats: []},
      decision: {intents: ['raideconomy'], objective: '恐怖机器人去摸玩家 4 的矿车',
        reasoning: '矿车路线已经确认，没有护卫。骚扰设 45 秒期限，矿车有护卫就撤。', valid_for_s: 45,
        recorded_only: ['power_usage']},
      composer: composer(['raideconomy']),
      outcome: applied('恐怖机器人接近敌方矿区'),
      model: model(1380),
    }),
    decision(runId, 4, 90, 'economy', {
      situation: {own: own(4800, 5, 5, '上升'), enemies: [], threats: []},
      decision: {intents: ['expand', 'advanceproduction'], objective: '多造矿车，准备第二块矿',
        reasoning: '资金积压，建议扩张并加快矿车生产。', valid_for_s: 60,
        recorded_only: ['capacity_target', 'tech_timing']},
      composer: composer(['advanceproduction'], [{intent: 'expand', reason: 'directive_override:no_expansion'}]),
      outcome: applied('新增 1 台矿车生产'),
      model: model(1750),
    }),
    decision(runId, 5, 130, 'tactical', {
      situation: {own: own(3900, 9, 6, '稳定'), enemies: seen(128, 4),
        threats: ['敌方部队正在后撤']},
      decision: {intents: ['deployattack'], objective: '追击后撤的敌军',
        reasoning: '敌军正在后撤，窗口马上关闭，建议立刻追击。', valid_for_s: 30, recorded_only: []},
      composer: composer([], [{intent: 'deployattack', reason: 'commander_veto'}]),
      outcome: {status: 'rejected', reason_code: 'commander_veto', native_accepted: null, observed_effects: []},
      model: model(1290),
    }),
    decision(runId, 6, 132, 'commander', {
      situation: {own: own(3900, 9, 6, '稳定'), enemies: seen(128, 4), threats: []},
      directive: {route: 'tech_pressure', resource_split: {economy: 0.35, army: 0.3, tech: 0.3, reserve: 0.05},
        primary_enemy: 4, overrides: ['no_expansion'], valid_for_s: 120},
      decision: {intents: [], objective: '不追，先看清退路',
        reasoning: '窗口太整齐了。先派战熊看一眼他们的退路，你们看见的是十秒前，不是现在。', valid_for_s: 120,
        recorded_only: []},
      composer: composer(['budgettech', 'focusenemy4']),
      outcome: applied('资源倾向科技'),
      model: model(2630),
    }),
    decision(runId, 7, 180, 'tactical', {
      situation: {own: own(4400, 11, 7, '稳定'), enemies: seen(176, 6), threats: []},
      decision: {intents: ['scout'], objective: '战熊确认敌方退路',
        reasoning: '按总指挥的要求先侦察北侧，确认是不是诱饵。', valid_for_s: 30, recorded_only: []},
      composer: composer(['scout']),
      outcome: applied('发现 6 辆敌方坦克埋伏在矿区北侧'),
      model: model(1210),
    }),
    decision(runId, 8, 220, 'tactical', {
      situation: {own: own(5100, 12, 7, '稳定'), enemies: seen(215, 2), threats: []},
      decision: {intents: ['withdraw'], objective: '恐怖机器人撤回',
        reasoning: '矿车有护卫了，骚扰到此为止，机器人转去盯分矿。', valid_for_s: 20, recorded_only: []},
      composer: composer(['withdraw']),
      outcome: {status: 'expired', reason_code: 'intent_expired', native_accepted: null, observed_effects: []},
      model: model(3480),
    }),
    decision(runId, 9, 270, 'economy', {
      situation: {own: own(6200, 14, 8, '高'), enemies: [], threats: []},
      decision: null,
      outcome: {status: 'unknown', reason_code: 'model_timeout', native_accepted: null, observed_effects: []},
      model: model(15000, 'timeout'),
    }),
    decision(runId, 10, 360, 'commander', {
      situation: {own: own(7400, 21, 9, '高'), enemies: seen(352, 5), threats: []},
      directive: {route: 'all_in', resource_split: {economy: 0.1, army: 0.8, tech: 0, reserve: 0.1},
        primary_enemy: 4, overrides: ['no_expansion', 'no_tech'], valid_for_s: 90},
      decision: {intents: [], objective: '全力出击：集中突破北侧',
        reasoning: '天启到位，防空伴随也齐了。北侧薄弱，集中突破，拿下建造厂就收。', valid_for_s: 90, recorded_only: []},
      composer: composer(['budgetarmy', 'focusenemy4']),
      outcome: applied('资源倾向军队'),
      model: model(2550),
    }),
    decision(runId, 11, 370, 'tactical', {
      situation: {own: own(6900, 22, 9, '高'), enemies: seen(368, 5), threats: []},
      decision: {intents: ['attackenemy'], objective: '集中突破北侧，目标敌方建造厂',
        reasoning: '主力和防空伴随一起推进，只打建造厂，不追残兵。', valid_for_s: 90, recorded_only: []},
      composer: composer(['attackenemy']),
      outcome: applied('4 支小队向敌方基地推进', '摧毁敌方建造厂'),
      model: model(1840),
    }),
    {kind: 'match_end', seq: 12, result: 'victory', duration_s: 452,
      players: [{player_id: 3, kind: 'model_ai', result: 'victory'}, {player_id: 4, kind: 'native_ai', result: 'defeat'}]},
  ];
}

export function decisionFixtureRecords(runId: string): DecisionStreamRecord[] {
  return parseDecisionRecords({records: rawDecisionFixtures(runId)});
}
