import {test} from 'node:test';
import assert from 'node:assert/strict';
import {strategicReevaluationView} from './strategicReevaluationView';
import type {MacroStrategyPublicState} from './nativeRpc';
function state(): MacroStrategyPublicState {
  return {schema_version: 1, kind: 'macro_strategy_public_state', current_strategy: null,
    recent_outcomes: [], last_guard_reason: 'strategy_minimum_hold', stopped: false,
    unknown_command_count: 0, unreleased_command_count: 0};
}
const row = (outcome: MacroStrategyPublicState['recent_outcomes'][number]['outcome'], time: number, verified = false) => ({
  plan_id: 'd341591e-2ad2-4562-95ca-da20b79fb5b1', outcome, reason_code: 'public_reason', at_game_seconds: time, effect_verified: verified,
});
test('no-effect evidence remains visible when a later decision waits before reconsidering', () => {
  const value = state(); value.recent_outcomes = [row('pending', 100), row('no_effect', 110)];
  value.last_guard_reason = 'strategy_no_effect_cooldown';
  const view = strategicReevaluationView(value);
  assert.equal(view.available, true); assert.match(view.history[1], /110.*未见合格效果/);
  assert.match(view.next, /避免重复无效指挥/); assert.doesNotMatch(view.next, /重新派发|策略成功/);
});
test('a later bounded effect does not erase an earlier failed expectation or imply victory', () => {
  const value = state(); value.recent_outcomes = [row('no_effect', 110), row('effect_observed', 130, true)];
  const view = strategicReevaluationView(value);
  assert.equal(view.history.length, 2); assert.match(view.history[0], /未见合格效果/); assert.match(view.history[1], /有界/);
  assert.doesNotMatch(JSON.stringify(view), /胜利|全部完成|付款|出厂/);
});
test('unknown after an earlier effect and stopping retains both facts and blocks a guessed retry', () => {
  const value = state(); value.recent_outcomes = [row('unknown', 140, true)]; value.stopped = true;
  value.unknown_command_count = 1; value.unreleased_command_count = 1; value.last_guard_reason = 'strategy_unknown_outcome';
  const view = strategicReevaluationView(value);
  assert.equal(view.uncertain, true); assert.match(view.history[0], /结果未知.*此前曾观测/);
  assert.match(view.next, /已停止新增指挥/); assert.match(view.next, /暂不新增指挥/);
});
test('reversed history and malformed raw records are not presented as a trusted sequence', () => {
  const value = state(); value.recent_outcomes = [row('no_effect', 130), row('pending', 100)];
  assert.equal(strategicReevaluationView(value).available, false);
  const view = strategicReevaluationView({private: 'PRIVATE'});
  assert.equal(view.available, false); assert.equal(view.uncertain, true); assert.doesNotMatch(JSON.stringify(view), /PRIVATE/);
});
