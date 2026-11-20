import {test} from 'node:test';
import assert from 'node:assert/strict';
import {
  actionLabel, actionLabels, currentStrategy, decisionRow, gameClock, isMatchEnd, lastSeq, mergeDecisionRecords,
  parseDecisionRecords, reviewStats, type DecisionRecord,
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
  assert.ok(!isMatchEnd(first) && first.decision === null && first.outcome === null);
  assert.ok(!isMatchEnd(second));
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
  assert.equal(lastSeq(merged), 9);
  assert.equal(lastSeq([]), undefined);
  const updated = mergeDecisionRecords(merged, [{...(all[0] as DecisionRecord), outcome: null}]);
  assert.equal((updated[0] as DecisionRecord).outcome, null, 'a later copy of the same seq replaces the earlier one');
});

test('decision rows translate intents and explain non-applied outcomes', () => {
  const records = decisionFixtureRecords(runId).filter((row): row is DecisionRecord => !isMatchEnd(row));
  const attack = decisionRow(records.find(row => row.seq === 7)!);
  assert.deepEqual(attack.intents, ['组织进攻', '集中对付玩家 4']);
  assert.equal(attack.badge.label, '已执行');
  assert.equal(attack.reason, null);
  assert.equal(attack.clock, '07:32');
  const rejected = decisionRow(records.find(row => row.seq === 5)!);
  assert.equal(rejected.badge.tone, 'bad');
  assert.equal(rejected.reason, '游戏内 AI 没有接受这条指令');
  const timedOut = decisionRow(records.find(row => row.seq === 6)!);
  assert.equal(timedOut.failed, true);
  assert.deepEqual(timedOut.intents, []);
  assert.equal(timedOut.badge.label, '结果未知');
});

test('current strategy is the latest decision with an intent; empty feed has a plain placeholder', () => {
  const records = decisionFixtureRecords(runId);
  const strategy = currentStrategy(records);
  assert.equal(strategy.available, true);
  assert.equal(strategy.objective, '总攻');
  assert.deepEqual(strategy.intents, ['进攻敌方']);
  assert.equal(strategy.since, '10:40');
  const partial = currentStrategy(records.slice(0, 6));
  assert.equal(partial.objective, '升级科技，准备中期部队', 'a decision without intents does not replace the strategy');
  const empty = currentStrategy([]);
  assert.equal(empty.available, false);
  assert.equal(empty.objective, 'AI 还没有做出决定');
});

test('review stats count outcomes, latency and the final result', () => {
  const stats = reviewStats(decisionFixtureRecords(runId));
  assert.equal(stats.decisions, 9);
  assert.equal(stats.applied, 6);
  assert.equal(stats.rejected, 1);
  assert.equal(stats.expired, 1);
  assert.equal(stats.unknown, 1);
  assert.equal(stats.modelErrors, 1);
  assert.equal(stats.result, 'victory');
  assert.equal(stats.resultLabel, '胜利');
  assert.equal(stats.duration, '11:42');
  assert.equal(stats.ended, true);
  const latencies = rawDecisionFixtures(runId).flatMap(row => (row.model ? [(row.model as {latency_ms: number}).latency_ms] : []));
  assert.equal(stats.averageLatencyMs, Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length));
  assert.equal(stats.topIntents[0].count >= 1, true);
  const unfinished = reviewStats(decisionFixtureRecords(runId).slice(0, 3));
  assert.equal(unfinished.ended, false);
  assert.equal(unfinished.resultLabel, '对局未结算');
  assert.equal(unfinished.duration, '03:21');
  assert.equal(reviewStats([]).averageLatencyMs, null);
});

test('game clock formats seconds and rejects junk', () => {
  assert.equal(gameClock(0), '00:00');
  assert.equal(gameClock(65.9), '01:05');
  assert.equal(gameClock(null), '--:--');
  assert.equal(gameClock(-1), '--:--');
  assert.equal(gameClock(Number.NaN), '--:--');
});
