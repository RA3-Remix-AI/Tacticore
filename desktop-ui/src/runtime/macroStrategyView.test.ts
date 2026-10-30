import {test} from 'node:test';
import assert from 'node:assert/strict';
import {macroStrategyView} from './macroStrategyView';
import type {MacroStrategyPublicState} from './nativeRpc';

function sample():MacroStrategyPublicState {
  return {schema_version:1,kind:'macro_strategy_public_state',stopped:false,unknown_command_count:0,unreleased_command_count:1,
    last_guard_reason:'strategy_minimum_hold',recent_outcomes:[],current_strategy:{strategy_id:'d341591e-2ad2-4562-95ca-da20b79fb5b1',
      objective:'build_force',phase:'prepare',public_fact_refs:['own.credits'],expected_observation:'production_queue',
      continue_conditions:['capability_available'],replan_conditions:['facts_changed'],resource_priorities:{economy:.2,army:.5,tech:.1,reserve:.2},
      updated_game_seconds:100,last_outcome:null}};
}
function result(outcome:MacroStrategyPublicState['recent_outcomes'][number]['outcome'],effect=false) {
  return {plan_id:'d341591e-2ad2-4562-95ca-da20b79fb5b1',outcome,effect_verified:effect,reason_code:'bounded_native_fact',at_game_seconds:110};
}

test('goal and expectation are readable labels without declaring completion',()=>{
  const view=macroStrategyView(sample());
  assert.equal(view.available,true);assert.equal(view.objective,'补充与调整兵力');assert.equal(view.phase,'准备条件');
  assert.equal(view.expectation,'出现新的生产队列');assert.match(view.latest,/尚无已核验/);
  assert.match(view.guard,/保持当前目标/);assert.match(view.pending,/1 条宏观意图/);
  assert.doesNotMatch(JSON.stringify(view),/own\.credits|d341591e|完成|归还/);
});
test('bounded effects, expiry and cancellation never turn into full control release or guaranteed success',()=>{
  for(const outcome of ['effect_observed','expired','cancelled','replaced'] as const){
    const value=sample();value.current_strategy!.last_outcome=result(outcome,true);
    const view=macroStrategyView(value);
    assert.match(view.latest,/有界/);assert.doesNotMatch(view.latest,/整体.*归还|全军|胜利|完工|全部完成/);
  }
});
test('unknown and known pending counts are separate and a stop retains uncertainty',()=>{
  const value=sample();value.unknown_command_count=1;value.unreleased_command_count=3;value.stopped=true;
  value.current_strategy!.last_outcome=result('unknown');value.last_guard_reason='strategy_unknown_outcome';
  const view=macroStrategyView(value);
  assert.equal(view.uncertain,true);assert.match(view.pending,/结果未知 1 条/);assert.match(view.pending,/另有 2 条意图/);
  assert.match(view.pending,/已停止新增指挥/);assert.match(view.latest,/不能认定成功或失败/);
});
test('unknown after earlier evidence preserves both facts instead of claiming a final success',()=>{
  const value=sample();value.current_strategy!.last_outcome=result('unknown',true);
  assert.equal(macroStrategyView(value).latest,'此前曾观测到效果；当前结果仍未知。');
});
test('previous plan evidence is labelled previous when the current goal has no outcome',()=>{
  const value=sample();value.recent_outcomes=[result('effect_observed',true)];
  assert.match(macroStrategyView(value).latest,/^此前意图：/);
});
test('missing or explicitly rejected records do not display unverified raw state',()=>{
  assert.match(macroStrategyView(undefined).objective,/等待模型声明/);
  const view=macroStrategyView({raw:'PRIVATE_PAYLOAD'},true);
  assert.equal(view.available,false);assert.equal(view.uncertain,true);assert.match(view.objective,/不可核验/);
  assert.doesNotMatch(JSON.stringify(view),/PRIVATE/);
});
test('malformed counters and unknown enums cannot leak text through labels',()=>{
  for(const changes of [{unknown_command_count:true},{unknown_command_count:65},{unknown_command_count:2,unreleased_command_count:1}]){
    assert.equal(macroStrategyView({...sample(),...changes}).available,false);
  }
  const value=sample() as unknown as Record<string,unknown>;
  (value.current_strategy as Record<string,unknown>).objective='PRIVATE_MODEL_RESPONSE';
  const view=macroStrategyView(value);
  assert.equal(view.available,false);assert.equal(view.uncertain,true);assert.doesNotMatch(JSON.stringify(view),/PRIVATE/);
});
test('unknown but valid reason codes remain generic rather than being echoed into the product',()=>{
  for(const reason of ['private_future_code','constructor']){
    const value=sample();value.last_guard_reason=reason;
    assert.equal(typeof macroStrategyView(value).guard,'string');
    assert.match(macroStrategyView(value).guard,/已记录/);
    assert.doesNotMatch(JSON.stringify(macroStrategyView(value)),/private_future_code|constructor/);
  }
});
