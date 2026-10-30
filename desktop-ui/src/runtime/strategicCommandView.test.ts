import {test} from 'node:test';
import assert from 'node:assert/strict';
import {strategicCommandView, strategicPreflightView, type StrategicClientRecord} from './strategicCommandView';
function sample(): StrategicClientRecord {
  return {schema_version: 1, kind: 'commander_strategic_client_record_v1', boundary: 'strategic_only',
    available_actions: ['budgeteconomy', 'budgetarmy', 'scout', 'withdraw'], current_actions: ['withdraw'],
    current_intent_state: 'reported', budget_adoption: 'pending', budget_policy: 'budgetarmy',
    unconnected_intents: ['native_construction_pause', 'native_production_pause', 'resource_expansion'],
    details_owner: 'native_ai', record_only: true, dispatch_authorized: false,
    native_acceptance_proves_success: false, extra_preferences_clear_is_global_stop: false};
}
test('high-level labels do not claim an exact template, quota or successful effect', () => {
  const view = strategicCommandView(sample());
  assert.equal(view.available, true); assert.equal(view.current, '撤退意图');
  assert.match(view.budget, /等待原生采用/); assert.match(view.evidence, /不等于战略成功/);
  assert.doesNotMatch(JSON.stringify(view), /牛蛙|铁锤|征召兵|电厂|西侧起点|新增.*队列|schema|commander_strategic_client/);
});
test('budget priority never masquerades as expansion or a global pause', () => {
  const value = sample(); value.current_actions = ['budgeteconomy'];
  const view = strategicCommandView(value);
  assert.match(view.current, /预算偏好/); assert.equal(view.unconnected.length, 3);
  assert.ok(view.unconnected.every(row => row.includes('未接通')));
});
test('empty extras and a sampled absence do not prove all native work stopped', () => {
  const value = sample(); value.current_actions = []; value.budget_policy = null; value.budget_adoption = 'not_observed';
  const view = strategicCommandView(value);
  assert.match(view.current, /继续自主运作/); assert.match(view.budget, /其他原生任务仍需单独观察/);
});
test('precision, unknown raw fields and forged proof flags are not displayed', () => {
  for (const change of [{current_actions: ['producebullfrog']}, {available_actions: ['buildpower']}, {dispatch_authorized: true},
    {native_acceptance_proves_success: true}, {extra_preferences_clear_is_global_stop: true}, {raw: 'PRIVATE'}]) {
    const view = strategicCommandView({...sample(), ...change});
    assert.equal(view.available, false); assert.equal(view.uncertain, true); assert.doesNotMatch(JSON.stringify(view), /PRIVATE|producebullfrog|buildpower/);
  }
});
test('historical and missing boundary records do not inherit current product qualification', () => {
  const value = sample(); value.boundary = 'historical_precision'; value.available_actions = []; value.current_actions = null;
  value.current_intent_state = 'awaiting'; value.budget_adoption = 'unavailable'; value.budget_policy = null;
  const view = strategicCommandView(value);
  assert.equal(view.available, false); assert.equal(view.historical, true); assert.match(view.boundary, /历史研究/);
  assert.equal(strategicCommandView(undefined).uncertain, true);
});
test('malformed shapes and inconsistent counters never become an offered action', () => {
  for (const change of [{current_actions: ['scout', 'withdraw']}, {current_actions: ['regroup']},
    {current_actions: ['budgetarmy', 'budgeteconomy']}, {current_actions: ['scout', 'scout']},
    {current_actions: null}, {budget_adoption: 'adopted', budget_policy: null}, {schema_version: true}]) {
    assert.equal(strategicCommandView({...sample(), ...change}).available, false);
  }
});
test('invalid policy remains explicit, with no guessed replacement or replay', () => {
  const value = sample(); value.current_actions = null; value.current_intent_state = 'invalid';
  const view = strategicCommandView(value); assert.equal(view.available, true); assert.equal(view.uncertain, true);
  assert.match(view.current, /未展示为有效指挥/);
});
test('readiness capabilities are shown as a check without inventing a Host or native adoption', () => {
  const view = strategicPreflightView({native_macro: true, commander_boundary: 'native_ai_details_v1', available_macro_actions: ['scout']});
  assert.equal(view.available, true); assert.match(view.current, /尚未启动/); assert.match(view.budget, /等待有效/);
  assert.equal(strategicPreflightView({native_macro: true, available_macro_actions: ['scout']}).available, false);
});
