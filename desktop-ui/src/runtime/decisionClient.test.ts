import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createDecisionClient, DECISIONS_OPERATION} from './decisionClient';
import {HostError} from './nativeRpc';
import {decisionSource, decisionFlagKey} from './features';
import {isDecision, isMatchEnd, isRunStart} from './decisions';

const runId = '44444444-4444-4444-8444-444444444444';

test('backend source calls run.decisions with since_seq only when known', async () => {
  const calls: [string, object][] = [];
  const fetch = createDecisionClient({source: 'backend', rpc: async (operation, args) => {
    calls.push([operation, args]);
    return {records: [{schema_version: 1, seq: 3, decision: {intents: ['scout']}}]};
  }});
  const first = await fetch(runId);
  await fetch(runId, 3);
  assert.equal(DECISIONS_OPERATION, 'run.decisions');
  assert.deepEqual(calls, [['run.decisions', {run_id: runId}], ['run.decisions', {run_id: runId, since_seq: 3}]]);
  assert.equal(first.state, 'ok');
  assert.equal(first.state === 'ok' && first.records.length, 1);
});

test('an older backend is reported as unavailable, other failures as errors', async () => {
  for (const code of ['operation_unsupported', 'request_invalid']) {
    const fetch = createDecisionClient({source: 'backend', rpc: async () => { throw new HostError(code, runId); }});
    assert.deepEqual(await fetch(runId), {state: 'unavailable', code});
  }
  const failing = createDecisionClient({source: 'backend', rpc: async () => { throw new HostError('run_not_found', runId); }});
  assert.deepEqual(await failing(runId), {state: 'error', code: 'run_not_found'});
  const crashing = createDecisionClient({source: 'backend', rpc: async () => { throw new Error('boom'); }});
  assert.deepEqual(await crashing(runId), {state: 'error', code: 'delivery_unknown'});
});

test('mock source reveals fixtures progressively and never calls the backend', async () => {
  let now = 1000;
  const fetch = createDecisionClient({source: 'mock', now: () => now, revealEveryMs: 1000,
    rpc: async () => { throw new Error('backend must not be called'); }});
  const first = await fetch(runId);
  assert.ok(first.state === 'ok' && first.source === 'mock');
  assert.equal(first.state === 'ok' && first.records.length, 2);
  now += 3000;
  const later = await fetch(runId, 2);
  assert.ok(later.state === 'ok' && later.records.every(row => !isDecision(row) || row.seq > 2));
  const complete = await fetch(runId, undefined, true);
  assert.ok(complete.state === 'ok' && complete.records.some(isMatchEnd));
});

test('feature flag defaults to backend and accepts env or storage opt-in', () => {
  assert.equal(decisionSource({}, null), 'backend');
  assert.equal(decisionSource({VITE_TACTICORE_DECISIONS: 'mock'}, null), 'mock');
  assert.equal(decisionSource({}, {getItem: key => (key === decisionFlagKey ? 'mock' : null)}), 'mock');
  assert.equal(decisionSource({}, {getItem: () => { throw new Error('blocked'); }}), 'backend');
  assert.equal(decisionSource({VITE_TACTICORE_DECISIONS: 'other'}, {getItem: () => 'backend'}), 'backend');
});

test('host pages: reads decisions + match_end, follows has_more and re-reads the open decision', async () => {
  const calls: object[] = [];
  const pages: Record<string, object> = {
    '0': {decisions: [{kind: 'decision', schema_version: 1, seq: 1, final: true}], match_end: null,
      has_more: true, next_since_seq: 1, open_seq: 2},
    '1': {decisions: [{kind: 'decision', schema_version: 1, seq: 2, final: false}], match_end: null,
      has_more: false, next_since_seq: 2, open_seq: 2},
  };
  const fetch = createDecisionClient({source: 'backend', rpc: async (_operation, args) => {
    calls.push(args);
    const since = String((args as {since_seq?: number}).since_seq ?? 0);
    return pages[since] ?? {decisions: [], match_end: {kind: 'match_end', result: 'victory', duration_s: 900,
      players: {'3': {outcome: 'victory', role: 'self'}}}, has_more: false, next_since_seq: 2, open_seq: null};
  }});
  const first = await fetch(runId);
  assert.ok(first.state === 'ok');
  assert.deepEqual(first.records.map(row => ('seq' in row ? row.seq : null)), [1, 2]);
  // Seq 2 is still open, so the next poll re-reads from 1 rather than from 2.
  await fetch(runId, 2);
  assert.deepEqual(calls[2], {run_id: runId, since_seq: 1});
  const review = await fetch(runId, undefined, true);
  assert.ok(review.state === 'ok');
});

test('host match_end players keyed by id become a list', async () => {
  const fetch = createDecisionClient({source: 'backend', rpc: async () => ({decisions: [],
    match_end: {kind: 'match_end', result: 'defeat', duration_s: 600, players: {'3': {outcome: 'defeat'}}},
    has_more: false})});
  const page = await fetch(runId);
  assert.ok(page.state === 'ok');
  const end = page.records.find(isMatchEnd);
  assert.equal(end?.result, 'defeat');
  assert.equal(end?.players.length, 1);
});

test('host page run (run_start) becomes the first record with commander, mode and opening variant', async () => {
  const fetch = createDecisionClient({source: 'backend', rpc: async () => ({
    run: {kind: 'run_start', schema_version: 1, commander: {id: 'hammer', name: '铁锤'}, decision_mode: 'layered',
      opening_variant: 'bear_scout_terror_raid'},
    decisions: [{kind: 'decision', schema_version: 1, seq: 1, layer: 'opening', final: false}],
    match_end: null, has_more: false})});
  const page = await fetch(runId);
  assert.ok(page.state === 'ok');
  const start = page.records[0];
  assert.ok(isRunStart(start));
  assert.equal(start.decision_mode, 'layered');
  assert.equal(start.opening_variant, 'bear_scout_terror_raid');
  assert.equal(start.commander?.id, 'hammer');
  const older = createDecisionClient({source: 'backend', rpc: async () => ({run: null, decisions: [], has_more: false})});
  const empty = await older(runId);
  assert.ok(empty.state === 'ok' && empty.records.length === 0);
});
