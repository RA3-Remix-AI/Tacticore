import {test} from 'node:test';
import assert from 'node:assert/strict';
import {strategicLifecycleView} from './strategicLifecycleView';
test('stop or result candidate alone never enables a new run', () => {
  for (const state of ['stopping', 'stopped', 'fault', 'result_candidate', 'uncertain']) {
    const view = strategicLifecycleView({state}); assert.equal(view.locked, true); assert.match(view.next, /尚不能/);
  }
});
test('released terminal faults permit a fresh session without being labelled strategic success', () => {
  const view = strategicLifecycleView({state: 'fault', native_release_verified: true, host_process_alive: false, status_stale: true});
  assert.equal(view.locked, false); assert.match(view.state, /需要处理/); assert.match(view.next, /新的受支持会话/);
  assert.match(view.observation, /最后保存/); assert.doesNotMatch(JSON.stringify(view), /战略成功|胜利/);
});
test('visual confirmation and delivery uncertainty stay distinct from actual outcome', () => {
  const candidate = strategicLifecycleView({state: 'result_candidate', reason_code: 'native_result_requires_visual_confirmation'});
  assert.match(candidate.reason, /尚未认定胜负/);
  assert.match(strategicLifecycleView({state: 'uncertain', reason_code: 'delivery_unknown'}).reason, /不要重新启动/);
});
test('unknown reason and state text cannot enter the product', () => {
  const view = strategicLifecycleView({state: 'PRIVATE_STATE', reason_code: 'PRIVATE_REASON'});
  assert.equal(view.locked, true); assert.doesNotMatch(JSON.stringify(view), /PRIVATE/);
});
test('no-native cancellation needs the independent release flag and terminal state', () => {
  assert.match(strategicLifecycleView({state: 'stopped', native_release_verified: true, no_native_execution_started: true}).release, /没有新增原生指挥/);
  assert.doesNotMatch(strategicLifecycleView({state: 'starting', no_native_execution_started: true}).release, /没有新增/);
  const running = strategicLifecycleView({state: 'running', native_release_verified: true});
  assert.equal(running.locked, true); assert.match(running.release, /尚未收到当前终态/);
});
