/**
 * Realistic mock decision records (contract schema_version 1). Used only when
 * the `decisions` feature flag is 'mock' and by tests. Includes nulls, a
 * rejected and an unknown outcome, a model error and a final match_end record.
 */
import {parseDecisionRecords, type DecisionStreamRecord} from './decisions';

type Raw = Record<string, unknown>;

function decision(runId: string, seq: number, time: number, fields: Raw): Raw {
  return {
    schema_version: 1, run_id: runId, seq, game_time_s: time,
    wall_time: new Date(Date.UTC(2026, 10, 20, 12, 0, time)).toISOString(),
    prompt_version: 'strategic-v5.2',
    ...fields,
  };
}

const model = (latency: number, error: string | null = null) => ({
  provider: 'DeepSeek', model: 'deepseek-chat', latency_ms: latency, input_bytes: 6120 + latency, output_bytes: 410, error,
});

export function rawDecisionFixtures(runId: string): Raw[] {
  return [
    decision(runId, 1, 22, {
      situation: {own: {credits: 9800, income_hint: '开局', army_count: 0, building_count: 2}, enemies: [], threats: []},
      decision: {intents: ['budgeteconomy', 'scout'], objective: '先发展经济并摸清对手位置',
        reasoning: '开局没有任何敌方情报，资金充足。先把资源倾向经济，同时派出侦察确认对手出生点。', valid_for_s: 90},
      outcome: {status: 'applied', reason_code: null, native_accepted: true, observed_effects: ['新增 1 个矿车生产队列', '侦察单位已出发']},
      model: model(1840),
    }),
    decision(runId, 2, 118, {
      situation: {own: {credits: 4200, income_hint: '稳定', army_count: 6, building_count: 5},
        enemies: [{player_id: 4, last_seen_s: 104, visible_count: 3}], threats: []},
      decision: {intents: ['expand'], objective: '趁对手还在发展，抢占第二块矿区',
        reasoning: '侦察发现对手只有少量步兵，近期没有进攻迹象。现在扩张风险较低。', valid_for_s: 120},
      outcome: {status: 'applied', reason_code: null, native_accepted: true, observed_effects: ['开始建造矿场']},
      model: model(2310),
    }),
    decision(runId, 3, 201, {
      situation: {own: {credits: 1500, income_hint: '上升', army_count: 9, building_count: 7},
        enemies: [{player_id: 4, last_seen_s: 196, visible_count: 8}], threats: ['敌方部队正在接近我方矿区']},
      decision: {intents: ['deploydefense', 'budgetarmy'], objective: '守住新矿区',
        reasoning: '对手 8 个单位朝新矿区移动，资金偏低。先转向防守并把资源倾向军队，避免矿区被拔。', valid_for_s: 60},
      outcome: {status: 'applied', reason_code: null, native_accepted: true, observed_effects: ['3 支小队转向矿区防守']},
      model: model(1975),
    }),
    decision(runId, 4, 262, {
      situation: {own: {credits: 2100, income_hint: '稳定', army_count: 12, building_count: 7},
        enemies: [{player_id: 4, last_seen_s: 255, visible_count: 2}], threats: []},
      decision: {intents: ['regroup'], objective: '击退进攻后重新集结',
        reasoning: '敌方进攻已被击退，只剩 2 个可见单位。把分散的部队收回集结点，准备下一步。', valid_for_s: 60},
      outcome: {status: 'expired', reason_code: 'intent_expired', native_accepted: null, observed_effects: []},
      model: model(3420),
    }),
    decision(runId, 5, 330, {
      situation: {own: {credits: 3600, income_hint: '上升', army_count: 15, building_count: 8},
        enemies: [{player_id: 4, last_seen_s: 301, visible_count: 0}], threats: []},
      decision: {intents: ['budgettech', 'advanceproduction'], objective: '升级科技，准备中期部队',
        reasoning: '经济已经稳定，兵力足以守家。现在把资源倾向科技，为中期更强的部队做准备。', valid_for_s: 150},
      outcome: {status: 'rejected', reason_code: 'native_rejected', native_accepted: false, observed_effects: []},
      model: model(2050),
    }),
    decision(runId, 6, 395, {
      situation: {own: {credits: 2800, income_hint: '上升', army_count: 16, building_count: 9}, enemies: [], threats: []},
      decision: null,
      outcome: {status: 'unknown', reason_code: 'model_timeout', native_accepted: null, observed_effects: []},
      model: model(15000, 'timeout'),
    }),
    decision(runId, 7, 452, {
      situation: {own: {credits: 5200, income_hint: '高', army_count: 22, building_count: 10},
        enemies: [{player_id: 4, last_seen_s: 440, visible_count: 5}], threats: []},
      decision: {intents: ['deployattack', 'focusenemy4'], objective: '集中兵力进攻玩家 4',
        reasoning: '我方兵力 22 对可见的 5 个敌方单位，经济也占优。现在是主动出击的窗口。', valid_for_s: 120},
      outcome: {status: 'applied', reason_code: null, native_accepted: true, observed_effects: ['4 支小队开始向敌方基地推进']},
      model: model(2480),
    }),
    decision(runId, 8, 538, {
      situation: {own: {credits: 3900, income_hint: '高', army_count: 18, building_count: 10},
        enemies: [{player_id: 4, last_seen_s: 536, visible_count: 11}], threats: ['敌方防御塔火力较强']},
      decision: {intents: ['raideconomy', 'reinforce'], objective: '绕开防线，袭扰对方矿车',
        reasoning: '正面进攻遇到防御塔，损失偏大。改为袭扰对方经济，同时补充前线兵力。', valid_for_s: 90},
      outcome: {status: 'applied', reason_code: null, native_accepted: true, observed_effects: ['摧毁 2 台敌方矿车']},
      model: model(2205),
    }),
    decision(runId, 9, 640, {
      situation: {own: {credits: 6100, income_hint: '高', army_count: 27, building_count: 11},
        enemies: [{player_id: 4, last_seen_s: 632, visible_count: 4}], threats: []},
      decision: {intents: ['attackenemy'], objective: '总攻',
        reasoning: '对方经济被削弱，可见兵力很少。集中全部部队发起总攻。', valid_for_s: 180},
      outcome: {status: 'applied', reason_code: null, native_accepted: true, observed_effects: ['摧毁敌方建造厂']},
      model: model(1990),
    }),
    {kind: 'match_end', seq: 10, result: 'victory', duration_s: 702,
      players: [{player_id: 3, kind: 'model_ai', result: 'victory'}, {player_id: 4, kind: 'native_ai', result: 'defeat'}]},
  ];
}


export function decisionFixtureRecords(runId: string): DecisionStreamRecord[] {
  return parseDecisionRecords({records: rawDecisionFixtures(runId)});
}
