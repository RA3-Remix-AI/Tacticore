import type {MacroExpansionAction,MacroExpansionRecord,MacroAdmissionRecord,MacroAdmissionStatus} from './nativeRpc';

export const expansionActionLabels:Record<MacroExpansionAction,string>={buildpower:'普通电厂建造偏好',buildbarracks:'兵营建造偏好',
  buildfactory:'战车工厂建造偏好',buildrefinery:'矿场建造偏好',buildbattlelab:'作战实验室建造偏好',
  producesickle:'镰刀生产偏好',producebullfrog:'牛蛙生产偏好'};
const object=(v:unknown):v is Record<string,unknown>=>typeof v==='object'&&v!==null&&!Array.isArray(v);
const amount=(v:unknown):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0;
const frame=(v:unknown):v is number=>amount(v)&&v>0&&v<=0xffffffff;
const count=(v:unknown):v is number=>amount(v)&&v<=100000;
const number=(v:number)=>v.toLocaleString('zh-CN');
const equals=(v:unknown,w:unknown)=>JSON.stringify(v)===JSON.stringify(w);
const availabilityReasons:Record<string,string>={insufficient_funds:'上次检查的可用资金不足，等待新的余额与队列核验。',
  producer_unready:'上次检查未找到唯一可用生产者，等待前置、生产队列与设施状态核验。',
  previous_request_pending:'上一条请求仍待核验，保留记录并等待处理。',unverified:'上次检查未取得完整准入事实，等待重新核验。'};
export function macroExpansionAvailabilityView(value:unknown,unavailable=false):{available:boolean;uncertain:boolean;rows:string[]} {
  const invalid=()=>({available:false,uncertain:unavailable||value!=null,rows:[]});
  if(unavailable||!object(value)||value.schema_version!==1||value.kind!=='macro_expansion_availability_record_v1'
    ||value.record_only!==true||value.dispatch_authorized!==false||value.automatic_retry!==false
    ||value.payment_verified!==false||value.global_native_release_verified!==false
    ||!Array.isArray(value.entries)||value.entries.length>7)return invalid();
  const actions=new Set<string>(),rows:string[]=[];
  for(const entry of value.entries){
    if(!object(entry)||Object.keys(entry).sort().join(',')!=='action,reason'||typeof entry.action!=='string'
      ||!Object.hasOwn(expansionActionLabels,entry.action)||actions.has(entry.action)||typeof entry.reason!=='string'
      ||!Object.hasOwn(availabilityReasons,entry.reason))return invalid();
    actions.add(entry.action);rows.push(`${expansionActionLabels[entry.action as MacroExpansionAction]}：${availabilityReasons[entry.reason]}`);
  }
  return {available:true,uncertain:false,rows};
}
const falseExpansion=['resource_reservation_verified','budget_hard_cap_verified','exact_queue_to_object_link_verified','payment_verified',
  'unit_exit_verified','technology_unlock_verified','exclusive_macro_attribution_verified','automatic_retry_allowed','global_native_release_verified'];
function expansion(value:unknown):value is MacroExpansionRecord {
  return object(value)&&value.source==='native_macro_expansion_observation'&&typeof value.action==='string'&&Object.hasOwn(expansionActionLabels,value.action)
    &&value.domain===(value.action.startsWith('produce')?'production':'construction')
    &&['native_queue_observed','native_producer_unavailable','native_expansion_pending'].includes(String(value.status))
    &&[null,'queue_target_observed','producer_unavailable','prerequisite_changed','expired','stopped'].includes(value.release_reason as string|null)
    &&value.additional_count_requested===1&&['observed_new_queue_count','new_own_target_observations','native_completion_edges_observed',
      'fully_paid_queue_observations','additional_queue_observations_after_window','available_producer_count'].every(k=>count(value[k]))
    &&['policy_released','positive_native_build_state_observed'].every(k=>typeof value[k]==='boolean')
    &&frame(value.builder_frame)&&frame(value.own_census_frame)&&Math.abs(value.builder_frame-value.own_census_frame)<=15
    &&amount(value.observed_queue_cost_sum)&&amount(value.observed_paid_field_sum)&&value.observed_paid_field_sum<=value.observed_queue_cost_sum
    &&falseExpansion.every(k=>value[k]===false)&&value.count_control_basis==='new_native_queue_acceptances'
    &&value.overall_production_permitted===null&&value.cost_observation_semantics==='last_observed_fields_per_queue_not_total_cash_outflow'
    &&value.unit_operation_policy==='native_ai'&&value.record_only===true;
}
const admissionStates:Record<MacroAdmissionStatus,string>={reserved:'正在复核准入，尚未确认送达。',delivering:'请求正在送达，结果仍待核验。',
  acknowledged:'原生已接受偏好，等待队列与效果。',preference_cleared:'偏好已独立清除，额度缓冲仍保留。',
  closed_after_current_state_reconciliation:'偏好缓冲已关闭。',aborted_before_delivery:'请求确认未发布，额度缓冲已撤回。',
  unknown:'送达或后续结果未知，保留额度缓冲；不会自动重发。'};
function admission(value:unknown):value is MacroAdmissionRecord {
  if(!object(value)||value.source!=='active_preference_admission_buffer_v4'||value.schema_version!==4||typeof value.status!=='string'
    ||!Object.hasOwn(admissionStates,value.status)||!amount(value.active_buffer_amount)||typeof value.known_ack!=='boolean'
    ||typeof value.independent_clear!=='boolean'||typeof value.reconciliation_waiting!=='boolean'||value.hard_spending_cap_verified!==false
    ||value.dispatch_authorized!==false||value.next_requires_fresh_cost_and_state!==true||value.automatic_retry!==false
    ||value.record_only!==true||value.global_native_release_verified!==false
    ||!equals(value.unverified_outcomes,['actual_cash_payment','refund','no_queue_ever_accepted','exclusive_enqueue_causality','latent_work_cancelled'])
    ||!equals(value.excluded_spending,['future_unaccepted_work_including_prior_selected_latent','future_native_autonomous_repair_and_ability_spending']))return false;
  const closed=value.status==='closed_after_current_state_reconciliation',aborted=value.status==='aborted_before_delivery';
  if((closed||aborted)!==(value.active_buffer_amount===0)||value.independent_clear&&!value.known_ack)return false;
  if(['reserved','delivering','aborted_before_delivery'].includes(value.status)&&(value.known_ack||value.independent_clear))return false;
  if(value.status==='acknowledged'&&(!value.known_ack||value.independent_clear))return false;
  if((closed||value.status==='preference_cleared')&&(!value.known_ack||!value.independent_clear))return false;
  if(closed)return !value.reconciliation_waiting&&amount(value.reconciled_credits)&&amount(value.reconciled_production_upgrade_debt_upper)
    &&Array.isArray(value.reconciled_frames)&&value.reconciled_frames.length===2&&value.reconciled_frames.every(frame)
    &&value.reconciled_frames[1]>=value.reconciled_frames[0]&&value.reconciled_frames[1]-value.reconciled_frames[0]<=2;
  return value.reconciled_credits===null&&value.reconciled_production_upgrade_debt_upper===null&&value.reconciled_frames===null;
}
export interface MacroExpansionView {available:boolean;uncertain:boolean;action:string;queues:string;observations:string;preference:string;verification:string;updated:string}
export function macroExpansionView(value:unknown,unavailable=false):MacroExpansionView {
  if(unavailable||!expansion(value))return {available:false,uncertain:unavailable||value!=null,action:'等待可核验的扩展观测',queues:'',observations:'',preference:'',verification:'扩展观测暂不可核验，未认定任务完成。',updated:''};
  return {available:true,uncertain:false,action:expansionActionLabels[value.action],
    queues:`新增原生队列 ${value.observed_new_queue_count} / 目标 ${value.additional_count_requested}${value.additional_queue_observations_after_window>0?`；窗口后另观测 ${value.additional_queue_observations_after_window} 条，未计入本次效果`:''}。`,
    observations:`新增同类己方对象观测 ${value.new_own_target_observations}；原生完工状态变化 ${value.native_completion_edges_observed}。`,
    preference:value.policy_released?'本条偏好记录已结束；整体控制归还以上方独立核验为准。':value.status==='native_producer_unavailable'?'生产或建造设施已不可用，等待核对偏好结束。':'等待原生队列与效果观测。',
    verification:value.domain==='production'?'队列与对象的对应关系、实际出厂及付款尚未核验。':'队列与对象的对应关系、供电可运转及科技解锁尚未核验。',
    updated:`观测采样帧 ${value.builder_frame} / ${value.own_census_frame}`};
}
export interface MacroAdmissionView {available:boolean;uncertain:boolean;buffer:string;state:string;clear:string;financial:string;next:string;limits:string}
export function macroAdmissionView(value:unknown,unavailable=false):MacroAdmissionView {
  if(unavailable||!admission(value))return {available:false,uncertain:unavailable||value!=null,buffer:'等待可核验的额度记录',state:'额度状态暂不可核验。',clear:'',financial:'',next:'未取得新的派发许可。',limits:''};
  const closed=value.status==='closed_after_current_state_reconciliation';
  const credits=value.reconciled_credits??0,debt=value.reconciled_production_upgrade_debt_upper??0;
  return {available:true,uncertain:value.status==='unknown',buffer:`活跃额度缓冲 ${number(value.active_buffer_amount)}`,
    state:admissionStates[value.status],clear:value.independent_clear?'本条偏好已独立清除；清除本身不证明付款。':value.known_ack?'原生接受已核验；独立清除仍待核验。':'尚无已核验的原生接受与独立清除。',
    financial:closed?`上次重核余额 ${number(credits)}，队列剩余义务上界 ${number(debt)}（采样帧 ${value.reconciled_frames!.join('–')}）${debt>credits?`；当次缺口 ${number(debt-credits)}`:''}。`
      :value.reconciliation_waiting||value.status==='preference_cleared'?'等待有效财务窗口，额度缓冲继续保留。':'尚无完整的财务重核记录。',
    next:'下一次请求仍须重新核验费用和完整财务；上次重核不授予新派发。',
    limits:'实际付款、退款及延迟工作取消仍未知；后续原生自主、维修和技能支出另计，不承诺总支出上限。'};
}
