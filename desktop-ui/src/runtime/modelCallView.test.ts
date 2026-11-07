import {test} from 'node:test';
import assert from 'node:assert/strict';
import {modelCallView, type ModelConsumptionReceipt} from './modelCallView';
import type {NativeEvent} from './nativeProcess';
const event = (seq: number, event_type: string, call_sequence = 1): NativeEvent => ({seq, event_type,
  created_at: '2026-11-03T00:00:00Z', profile_binding_matches: true, facts: {call_sequence}});
const scope = {profile_id: 'current-profile', profile_revision: 11, effective_hash: 'a'.repeat(64)};
const receipt = (stage = 'response_returned', calls_started = 7): ModelConsumptionReceipt => ({...scope,
  state: 'host_profile_applied', stage, calls_started, responses_returned: 7, model_response_received: true});

test('saved configuration and foreign or unbound events never establish remote availability', () => {
  for (const events of [undefined, [], [event(1, 'commander_profile_applied')],
    [{...event(1, 'commander_model_response_returned'), profile_binding_matches: false}],
    [{...event(1, 'commander_model_response_returned'), profile_binding_matches: undefined}]]) {
    assert.equal(modelCallView(events).state, 'unavailable');
  }
});
test('a new call supersedes an old response and late old results cannot replace it', () => {
  const events = [event(1, 'commander_model_response_returned'), event(2, 'commander_model_call_started', 2),
    event(3, 'commander_model_call_failed', 1)];
  assert.equal(modelCallView(events).state, 'waiting');
  assert.equal(modelCallView([...events, event(4, 'commander_model_response_returned', 2)]).state, 'responded');
});
test('failure has an actionable bounded explanation without echoing provider data or guessing authentication', () => {
  const view = modelCallView([{...event(1, 'commander_model_call_failed'), facts: {call_sequence: 1,
    reason_code: 'PRIVATE_KEY', backend_diagnostics: {message: 'PRIVATE_ENDPOINT'}}}]);
  assert.equal(view.state, 'failed');
  assert.match(view.detail, /无法确定/); assert.match(view.detail, /停止并等待控制归还/);
  assert.doesNotMatch(JSON.stringify(view), /PRIVATE|密钥错误|自动重试/);
});
test('response is distinct from execution; cancellation is distinct from release', () => {
  assert.match(modelCallView([event(1, 'commander_model_response_returned')]).detail, /不代表原生 AI 已执行/);
  assert.match(modelCallView([event(1, 'commander_model_call_cancelled')]).detail, /不代表控制已归还/);
});
test('truncated valid event pages work, while reversed, duplicate and malformed sequences fail closed', () => {
  assert.equal(modelCallView([event(100, 'commander_model_call_failed', 20)]).state, 'failed');
  for (const events of [[event(2, 'host_started'), event(1, 'commander_model_response_returned')],
    [event(1, 'commander_model_call_started'), event(1, 'commander_model_response_returned')],
    [event(1, 'commander_model_call_failed', NaN)], [event(1, 'commander_model_call_failed', 0)],
    [event(1, 'commander_model_response_returned'), event(2, 'commander_model_call_started')],
    [event(1, 'commander_model_response_returned'), event(2, 'commander_model_call_failed')]]) {
    assert.equal(modelCallView(events).state, 'unavailable');
  }
});

test('the live latest-30 noise window and a reopened run retain the bound latest response', () => {
  const noise = Array.from({length: 30}, (_, i) => event(474 + i, 'macro_native_feedback'));
  assert.equal(modelCallView(noise, receipt(), scope).state, 'responded');
  assert.equal(modelCallView(undefined, receipt(), scope).state, 'responded');
  for (const [stage, state] of [['call_started', 'waiting'], ['call_failed', 'failed'], ['call_cancelled', 'cancelled']]) {
    assert.equal(modelCallView(noise, receipt(stage, 8), scope).state, state);
  }
});

test('old revisions, foreign receipts and invalid cumulative counters cannot supply a fallback', () => {
  for (const value of [{...receipt(), profile_revision: 10}, {...receipt(), effective_hash: 'b'.repeat(64)},
    {...receipt(), profile_id: 'other-profile'}, {...receipt(), calls_started: 6},
    {...receipt(), responses_returned: NaN}, {...receipt(), model_response_received: false},
    {...receipt(), stage: 'provider secret'}, {...receipt(), state: 'saved'}]) {
    assert.equal(modelCallView([], value, scope).state, 'unavailable');
  }
  assert.equal(modelCallView([], receipt()).state, 'unavailable');
});

test('receipt fallback preserves event ordering checks and cannot erase a newer call', () => {
  assert.equal(modelCallView([event(1, 'commander_model_call_started', 8)], receipt(), scope).state, 'waiting');
  assert.equal(modelCallView([event(1, 'commander_model_call_started', 7)], receipt(), scope).state, 'responded');
  assert.equal(modelCallView([event(2, 'host_started'), event(1, 'host_started')], receipt(), scope).state, 'unavailable');
});

test('a later Host receipt completes the same call after the event page was sampled', () => {
  const pending = [event(100, 'commander_model_call_started', 8)];
  for (const [stage, state] of [['response_returned', 'responded'], ['call_failed', 'failed'], ['call_cancelled', 'cancelled']]) {
    const later = {...receipt(stage, 8), responses_returned: stage === 'response_returned' ? 8 : 7};
    assert.equal(modelCallView(pending, later, scope).state, state);
  }
  assert.equal(modelCallView(pending, {...receipt('call_failed', 8), effective_hash: 'b'.repeat(64)}, scope).state, 'waiting');
});

test('terminal events survive a pending receipt while conflicting terminal records stay unavailable', () => {
  const completed = [event(100, 'commander_model_response_returned', 8)];
  assert.equal(modelCallView(completed, receipt('call_started', 8), scope).state, 'responded');
  assert.equal(modelCallView([event(100, 'commander_model_call_failed', 8)], receipt('call_started', 8), scope).state, 'failed');
  assert.equal(modelCallView([event(100, 'commander_model_call_cancelled', 8)], receipt('call_started', 8), scope).state, 'cancelled');
  assert.equal(modelCallView(completed, receipt('call_failed', 8), scope).state, 'unavailable');
  assert.equal(modelCallView([event(100, 'commander_model_call_failed', 8)], receipt('call_cancelled', 8), scope).state, 'unavailable');
});
