import {test} from 'node:test';
import assert from 'node:assert/strict';
import {macroExpansionView,macroAdmissionView,expansionActionLabels} from './macroExpansionView';
import type {MacroExpansionRecord,MacroAdmissionRecord,MacroAdmissionStatus} from './nativeRpc';

function expansion():MacroExpansionRecord {
  return {source:'native_macro_expansion_observation',action:'producesickle',domain:'production',status:'native_queue_observed',release_reason:'queue_target_observed',
    additional_count_requested:1,observed_new_queue_count:1,new_own_target_observations:2,native_completion_edges_observed:0,fully_paid_queue_observations:0,
    additional_queue_observations_after_window:1,available_producer_count:1,positive_native_build_state_observed:true,policy_released:true,
    builder_frame:1500,own_census_frame:1501,observed_queue_cost_sum:850,observed_paid_field_sum:17,count_control_basis:'new_native_queue_acceptances',
    overall_production_permitted:null,cost_observation_semantics:'last_observed_fields_per_queue_not_total_cash_outflow',resource_reservation_verified:false,
    budget_hard_cap_verified:false,exact_queue_to_object_link_verified:false,payment_verified:false,unit_exit_verified:false,technology_unlock_verified:false,
    exclusive_macro_attribution_verified:false,automatic_retry_allowed:false,unit_operation_policy:'native_ai',record_only:true,global_native_release_verified:false};
}
function admission(status:MacroAdmissionStatus='preference_cleared'):MacroAdmissionRecord {
  const closed=status==='closed_after_current_state_reconciliation',early=['reserved','delivering','aborted_before_delivery'].includes(status);
  return {source:'active_preference_admission_buffer_v4',schema_version:4,status,active_buffer_amount:closed||status==='aborted_before_delivery'?0:850,
    known_ack:!early,independent_clear:closed||status==='preference_cleared',reconciled_credits:closed?596:null,
    reconciled_production_upgrade_debt_upper:closed?1890:null,reconciled_frames:closed?[1504,1505]:null,
    unverified_outcomes:['actual_cash_payment','refund','no_queue_ever_accepted','exclusive_enqueue_causality','latent_work_cancelled'],
    excluded_spending:['future_unaccepted_work_including_prior_selected_latent','future_native_autonomous_repair_and_ability_spending'],
    hard_spending_cap_verified:false,dispatch_authorized:false,next_requires_fresh_cost_and_state:true,automatic_retry:false,
    reconciliation_waiting:status==='preference_cleared',record_only:true,global_native_release_verified:false};
}
test('new queues and objects do not claim completed output, payment or global release',()=>{
  const view=macroExpansionView(expansion());
  assert.equal(view.available,true);assert.equal(view.action,'镰刀生产偏好');assert.match(view.queues,/新增原生队列 1 \/ 目标 1/);
  assert.match(view.queues,/窗口后另观测 1/);assert.match(view.observations,/同类己方对象观测 2/);
  assert.match(view.verification,/对应关系、实际出厂及付款尚未核验/);assert.match(view.preference,/整体控制归还.*独立核验/);
  assert.doesNotMatch(JSON.stringify(view),/已完成出厂|已付款|总支出已控制|schema|0x/);
});
test('construction state edges are separate from power, operation and technology qualification',()=>{
  const raw=expansion();raw.action='buildbattlelab';raw.domain='construction';raw.native_completion_edges_observed=1;
  const view=macroExpansionView(raw);assert.equal(view.action,'作战实验室建造偏好');assert.match(view.observations,/完工状态变化 1/);
  assert.match(view.verification,/供电可运转及科技解锁尚未核验/);assert.doesNotMatch(view.verification,/科技已解锁/);
});
test('clear keeps a held buffer while financial reconciliation is unavailable',()=>{
  const view=macroAdmissionView(admission());assert.equal(view.available,true);assert.match(view.buffer,/850/);
  assert.match(view.state,/独立清除.*缓冲仍保留/);assert.match(view.clear,/不证明付款/);
  assert.match(view.financial,/等待有效财务窗口.*继续保留/);assert.match(view.next,/重新核验费用和完整财务/);
});
test('closed uses historical cash and frames with known shortfall and no new authority',()=>{
  const view=macroAdmissionView(admission('closed_after_current_state_reconciliation'));
  assert.match(view.buffer,/缓冲 0/);assert.equal(view.state,'偏好缓冲已关闭。');
  assert.match(view.financial,/上次重核余额 596/);assert.match(view.financial,/义务上界 1,890/);
  assert.match(view.financial,/采样帧 1504–1505/);assert.match(view.financial,/当次缺口 1,294/);
  assert.match(view.next,/上次重核不授予新派发/);assert.doesNotMatch(view.financial,/当前可用|已付款|已退款/);
  assert.match(view.limits,/延迟工作取消仍未知/);assert.match(view.limits,/不承诺总支出上限/);
});
test('known acceptance, not-published abort and unknown delivery stay distinct',()=>{
  assert.match(macroAdmissionView(admission('acknowledged')).state,/已接受偏好/);
  assert.match(macroAdmissionView(admission('aborted_before_delivery')).state,/确认未发布/);
  const unknown=macroAdmissionView(admission('unknown'));assert.equal(unknown.uncertain,true);
  assert.match(unknown.state,/结果未知.*保留额度缓冲.*不会自动重发/);
});
test('invalid flags, mismatched states and unsafe amounts cannot become display facts',()=>{
  for(const change of [{dispatch_authorized:true},{active_buffer_amount:0},{known_ack:false},{reconciled_credits:100},
    {active_buffer_amount:Infinity},{active_buffer_amount:true},{unverified_outcomes:[]},{source:'PRIVATE_API_KEY'}]){
    const view=macroAdmissionView({...admission(),...change});assert.equal(view.available,false);assert.equal(view.uncertain,true);
    assert.doesNotMatch(JSON.stringify(view),/PRIVATE_API_KEY|Infinity/);
  }
  for(const change of [{payment_verified:true},{global_native_release_verified:true},{unit_exit_verified:true},
    {builder_frame:-1},{own_census_frame:1600},{observed_new_queue_count:true},{action:'PRIVATE_NATIVE_ADDRESS'}]){
    const view=macroExpansionView({...expansion(),...change});assert.equal(view.available,false);
    assert.doesNotMatch(JSON.stringify(view),/PRIVATE_NATIVE_ADDRESS/);
  }
});
test('legacy absence is quiet while a rejected optional record is visible',()=>{
  assert.equal(macroExpansionView(undefined).uncertain,false);assert.equal(macroAdmissionView(null).uncertain,false);
  assert.equal(macroExpansionView(undefined,true).uncertain,true);assert.equal(macroAdmissionView(undefined,true).uncertain,true);
  assert.equal(Object.keys(expansionActionLabels).length,7);
});
