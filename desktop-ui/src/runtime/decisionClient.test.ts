import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createDecisionClient, DECISIONS_OPERATION} from './decisionClient';
import {HostError} from './nativeRpc';
import {decisionSource, decisionFlagKey} from './features';
import {isMatchEnd} from './decisions';

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
  assert.ok(later.state === 'ok' && later.records.every(row => isMatchEnd(row) || row.seq > 2));
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
