import {test} from 'node:test';
import assert from 'node:assert/strict';
import {
  actionLabel, actionLabels, currentDirective, currentStrategy, decisionRow, decisionsOf, droppedReason, filterByLayer,
  gameClock, isDecision, isMatchEnd, isRunStart, lastSeq, layerCounts, mergeDecisionRecords, parseDecisionRecords,
  recordedOnlyText, reviewStats, splitShares, type DecisionRecord,
} from './decisions';
import {decisionFixtureRecords, rawDecisionFixtures} from './decisionFixtures';

const runId = '44444444-4444-4444-8444-444444444444';

test('every contract action has a Chinese label; focus targets and unknown names fall back sensibly', () => {
  for (const name of ['regroup', 'scout', 'withdraw', 'reinforce', 'deployattack', 'deploydefense', 'expand', 'attackenemy',
    'raideconomy', 'budgeteconomy', 'budgetarmy', 'budgettech', 'pauseconstruction', 'advanceconstruction',
    'pauseproduction', 'advanceproduction']) {
    assert.ok(Object.hasOwn(actionLabels, name), name);
    assert.match(actionLabel(name), /[一-鿿]/, name);
  }
  assert.equal(actionLabel('focusenemy4'), '集中对付玩家 4');
  assert.equal(actionLabel('focusenemy12'), '集中对付玩家 12');
  assert.equal(actionLabel('some_new_action'), 'some_new_action');
  assert.equal(actionLabel('toString'), 'toString');
});

test('parser tolerates nulls, missing sections and junk rows without failing the feed', () => {
  const parsed = parseDecisionRecords({records: [
    {schema_version: 1, seq: 1, run_id: null, game_time_s: null, wall_time: null, situation: null, decision: null, outcome: null, model: null},
    {schema_version: 1, seq: 2, decision: {intents: ['scout', 7, null], objective: null, reasoning: 'r', valid_for_s: null},
      outcome: {status: 'weird', reason_code: null, native_accepted: 'yes', observed_effects: null}},
    {schema_version: 2, seq: 3},
    {seq: 'x'},
    'not-an-object',
    null,
    {kind: 'match_end', result: 'banana', duration_s: null, players: null},
  ]});
  assert.equal(parsed.length, 3);
  const [first, second, end] = parsed;
  assert.ok(isDecision(first) && first.decision === null && first.outcome === null);
  assert.ok(isDecision(second));
  assert.equal(first.layer, null, 'an older backend has no layer');
  assert.equal(first.composer, null);
  assert.deepEqual(second.decision?.recorded_only, []);
  assert.deepEqual(second.decision?.intents, ['scout']);
  assert.equal(second.outcome?.status, 'unknown');
  assert.equal(second.outcome?.native_accepted, null);
  assert.deepEqual(second.outcome?.observed_effects, []);
  assert.ok(isMatchEnd(end) && end.result === 'unknown' && end.players.length === 0);
  assert.deepEqual(parseDecisionRecords(null), []);
  assert.deepEqual(parseDecisionRecords({records: 'nope'}), []);
});

test('incremental pages merge by seq, keep order, and keep match_end last', () => {
  const all = decisionFixtureRecords(runId);
  const firstPage = all.slice(0, 4), secondPage = all.slice(3);
  const merged = mergeDecisionRecords(firstPage, secondPage);
  assert.equal(merged.length, all.length);
  assert.ok(isMatchEnd(merged[merged.length - 1]));
  assert.ok(isRunStart(merged[0]), 'run_start stays first');
  assert.equal(lastSeq(merged), 11);
  assert.equal(lastSeq([]), undefined);
  const updated = mergeDecisionRecords(merged, [{...(all[1] as DecisionRecord), outcome: null}]);
  assert.equal((updated[1] as DecisionRecord).outcome, null, 'a later copy of the same seq replaces the earlier one');
});

test('decision rows translate intents and explain non-applied outcomes', () => {
  const records = decisionsOf(decisionFixtureRecords(runId));
  const attack = decisionRow(records.find(row => row.seq === 11)!);
  assert.deepEqual(attack.intents, ['进攻敌方']);
  assert.equal(attack.badge.label, '已执行');
  assert.equal(attack.reason, null);
  assert.equal(attack.clock, '06:10');
  assert.equal(attack.layerLabel, '战术参谋');
  assert.equal(attack.commander, null, 'only commander-layer records carry the portrait');
  const vetoed = decisionRow(records.find(row => row.seq === 5)!);
  assert.equal(vetoed.badge.tone, 'bad');
  assert.equal(vetoed.reason, '总指挥否决了这个方案');
  assert.deepEqual(vetoed.intents, [], 'a dropped intent is not shown as an action');
  assert.deepEqual(vetoed.dropped, ['未采纳：组织进攻（总指挥否决）']);
  const timedOut = decisionRow(records.find(row => row.seq === 9)!);
  assert.equal(timedOut.failed, true);
  assert.deepEqual(timedOut.intents, []);
  assert.equal(timedOut.badge.label, '结果未知');
});

test('current strategy is the latest decision with an intent; empty feed has a plain placeholder', () => {
  const records = decisionFixtureRecords(runId);
  const strategy = currentStrategy(records);
  assert.equal(strategy.available, true);
  assert.equal(strategy.objective, '集中突破北侧，目标敌方建造厂');
  assert.deepEqual(strategy.intents, ['进攻敌方']);
  assert.equal(strategy.since, '06:10');
  const partial = currentStrategy(records.slice(0, 10));
  assert.equal(partial.objective, '恐怖机器人撤回', 'a decision without intents does not replace the strategy');
  const empty = currentStrategy([]);
  assert.equal(empty.available, false);
  assert.equal(empty.objective, 'AI 还没有做出决定');
});

test('review stats count outcomes, latency and the final result', () => {
  const stats = reviewStats(decisionFixtureRecords(runId));
  assert.equal(stats.decisions, 11);
  assert.equal(stats.applied, 8);
  assert.equal(stats.rejected, 1);
  assert.equal(stats.expired, 1);
  assert.equal(stats.unknown, 1);
  assert.equal(stats.modelErrors, 1);
  assert.equal(stats.result, 'victory');
  assert.equal(stats.resultLabel, '胜利');
  assert.equal(stats.duration, '07:32');
  assert.equal(stats.ended, true);
  const latencies = rawDecisionFixtures(runId).filter(row => row.kind === 'decision').flatMap(row => (row.model ? [(row.model as {latency_ms: number}).latency_ms] : []));
  assert.equal(stats.averageLatencyMs, Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length));
  assert.equal(stats.topIntents[0].count >= 1, true);
  assert.deepEqual(stats.topIntents[0], {label: '集中对付玩家 4', count: 3});
  assert.ok(!stats.topIntents.some(row => row.label === '组织进攻'), 'a vetoed intent is not counted as used');
  const unfinished = reviewStats(decisionFixtureRecords(runId).slice(0, 4));
  assert.equal(unfinished.ended, false);
  assert.equal(unfinished.resultLabel, '对局未结算');
  assert.equal(unfinished.duration, '01:05');
  assert.equal(reviewStats([]).averageLatencyMs, null);
});

test('game clock formats seconds and rejects junk', () => {
  assert.equal(gameClock(0), '00:00');
  assert.equal(gameClock(65.9), '01:05');
  assert.equal(gameClock(null), '--:--');
  assert.equal(gameClock(-1), '--:--');
  assert.equal(gameClock(Number.NaN), '--:--');
});

test('layered records parse layer, commander, directive, composer and record-only fields', () => {
  const records = decisionsOf(decisionFixtureRecords(runId));
  const directive = records.find(row => row.seq === 2)!;
  assert.equal(directive.layer, 'commander');
  assert.deepEqual(directive.commander, {id: 'hammer', name: '铁锤'});
  assert.equal(directive.directive?.route, 'tech_pressure');
  assert.equal(directive.directive?.primary_enemy, 4);
  assert.deepEqual(directive.directive?.overrides, ['no_expansion']);
  assert.deepEqual(directive.composer?.applied_intents, ['budgeteconomy', 'focusenemy4']);
  const row = decisionRow(directive);
  assert.equal(row.layerLabel, '总指挥');
  assert.equal(row.commander?.name, '铁锤');
  assert.match(row.commander?.portrait ?? '', /hammer-portrait\.webp$/);
  assert.equal(row.directiveLine, '方针：科技压制 · 主攻玩家 4 · 不扩张');
  const economy = decisionRow(records.find(value => value.seq === 4)!);
  assert.deepEqual(economy.intents, ['继续生产'], 'only applied intents appear as actions');
  assert.deepEqual(economy.dropped, ['未采纳：扩张经济（与总指挥方针冲突：不扩张）']);
  assert.equal(economy.recordedOnly, '仅记录，尚未执行：产能目标、科技时机');
  // Junk in the layered fields is dropped without failing the record.
  const [junk] = parseDecisionRecords({records: [{schema_version: 1, seq: 1, layer: 'boss', commander: 'x',
    directive: [], composer: {applied_intents: 'no', dropped: [{intent: 3}, {intent: 'scout'}]},
    decision: {intents: [], recorded_only: ['tech_timing', 5]}}]});
  assert.ok(isDecision(junk));
  assert.equal(junk.layer, null);
  assert.equal(junk.commander, null);
  assert.equal(junk.directive, null);
  assert.deepEqual(junk.composer, {applied_intents: [], dropped: [{intent: 'scout', reason: null}]});
  assert.deepEqual(decisionRow(junk).dropped, ['未采纳：侦察敌情（原因未记录）']);
  assert.deepEqual(junk.decision?.recorded_only, ['tech_timing']);
});

test('dropped reasons and record-only fields read as plain Chinese, unknown codes stay visible', () => {
  assert.equal(droppedReason('commander_veto'), '总指挥否决');
  assert.equal(droppedReason('directive_override:no_tech'), '与总指挥方针冲突：暂停科技');
  assert.equal(droppedReason('directive_override:new_rule'), '与总指挥方针冲突：new_rule');
  assert.equal(droppedReason('brand_new_reason'), 'brand_new_reason');
  assert.equal(droppedReason(null), '原因未记录');
  assert.equal(recordedOnlyText([]), null);
  assert.equal(recordedOnlyText(['doctrine', 'later_field']), '仅记录，尚未执行：协同战法、later_field');
});

test('current directive comes from the latest commander record; resource split becomes percentages', () => {
  const records = decisionFixtureRecords(runId);
  const directive = currentDirective(records)!;
  assert.equal(directive.route, '全力出击');
  assert.equal(directive.primaryEnemy, '玩家 4');
  assert.deepEqual(directive.overrides, ['不扩张', '暂停科技']);
  assert.equal(directive.since, '06:00');
  assert.equal(directive.validFor, '90 秒');
  assert.deepEqual(directive.shares.map(row => [row.label, row.percent]), [['经济', 10], ['军队', 80], ['储备', 10]]);
  assert.equal(currentDirective(records.slice(0, 7))?.route, '科技压制');
  assert.equal(currentDirective(records.slice(0, 2)), null, 'no commander record yet');
  assert.deepEqual(splitShares({economy: 30, army: 50, tech: 10, reserve: 10}).map(row => row.percent), [30, 50, 10, 10]);
  assert.deepEqual(splitShares({economy: null, army: null, tech: null, reserve: null}), []);
  assert.deepEqual(splitShares(null), []);
});

test('layer counts, filters and the review summary of a layered run', () => {
  const records = decisionFixtureRecords(runId);
  assert.deepEqual(layerCounts(records).map(row => [row.label, row.count]),
    [['总指挥', 3], ['经济参谋', 2], ['战术参谋', 5], ['开局', 1]]);
  const commander = filterByLayer(records, 'commander');
  assert.deepEqual(decisionsOf(commander).map(row => row.seq), [2, 6, 10]);
  assert.ok(commander.some(isMatchEnd) && commander.some(isRunStart), 'filters keep run_start and match_end');
  assert.equal(filterByLayer(records, 'all').length, records.length);
  const stats = reviewStats(records);
  assert.equal(stats.dropped, 2);
  assert.equal(stats.recordedOnly, 3);
  assert.equal(stats.run.commander?.name, '铁锤');
  assert.equal(stats.run.commander?.full_name, '维克托·莫罗佐夫');
  assert.equal(stats.run.decisionMode, '分层决策（总指挥 + 参谋）');
  assert.equal(stats.run.openingVariant, 'bear_scout_terror_raid');
  const older = reviewStats(parseDecisionRecords({records: [{schema_version: 1, seq: 1}]}));
  assert.deepEqual(older.layers, []);
  assert.deepEqual(older.run, {commander: null, decisionMode: null, openingVariant: null});
});
