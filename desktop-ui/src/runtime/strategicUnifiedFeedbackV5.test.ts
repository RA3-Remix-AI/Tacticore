import { test } from 'node:test';
import assert from 'node:assert/strict';
import { strategicCommandView } from './strategicCommandView';
import { strategicUnifiedFeedbackV5 } from './strategicUnifiedFeedbackV5';

test('four strategic domains display together without claiming global stopping or mission completion',()=>{
  const offered=['expand','budgetarmy','pauseconstruction','advanceconstruction','pauseproduction','advanceproduction'];
  const view=strategicCommandView({schema_version:1,kind:'commander_strategic_client_record_v1',boundary:'strategic_only',
    available_actions:offered,current_actions:['expand','budgetarmy','pauseconstruction','advanceproduction'],current_intent_state:'reported',
    budget_adoption:'not_observed',budget_policy:null,unconnected_intents:[],details_owner:'native_ai',record_only:true,
    dispatch_authorized:false,native_acceptance_proves_success:false,extra_preferences_clear_is_global_stop:false});
  assert.equal(view.available,true);assert.equal(view.unconnected.length,0);assert.match(view.current,/原生扩张/);
});
test('observed manager state remains separate from completed construction',()=>{
  const row={action:'pauseconstruction',status:'native_manager_state_observed',observed_frame:1500,
    preference_active:true,component_state_adopted:true,state_already_satisfied:false,active_native_task_observed:false,
    movement_observed:false,mission_success_verified:false,exclusive_attribution_verified:false};
  const sample={source:'bound_native_strategy_v5',details_owner:'native_ai',observed_frame:1501,observations:[row]};
  const text=strategicUnifiedFeedbackV5(sample).join('');assert.match(text,/已读回原生调度状态/);assert.match(text,/结果仍待观察/);
  assert.deepEqual(strategicUnifiedFeedbackV5({...sample,observations:[{...row,mission_success_verified:true}]}),[]);
  assert.deepEqual(strategicUnifiedFeedbackV5({...sample,observations:[{...row,observed_frame:1600}]}),[]);
});
