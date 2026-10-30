export interface NativeEvent {seq:number;event_type:string;created_at:string;facts?:Record<string,unknown>;profile_binding_matches?:boolean}
const labels:Record<string,string>={run_registered:'登记对局与宿主身份',command_reserved:'持久记录操作意图',dispatch_intent_committed:'操作已进入派发阶段',
  macro_native_feedback:'收到原生宏观反馈',model_macro_dispatch_prepared:'宏观意图等待派发',model_macro_native_acknowledged:'原生宏观标志已回执',model_macro_dispatch_unknown:'宏观投递结果未知',
  model_macro_production_prepared:'模型生产意图已记录',model_macro_production_acknowledged:'原生生产偏好已回执',macro_production_preference_released:'生产偏好已释放',macro_production_feedback:'收到原生生产观测',
  macro_plan_not_dispatched:'战况变化，旧宏观计划未派发',
  model_macro_construction_prepared:'模型建造意图已记录',model_macro_construction_acknowledged:'原生建造偏好已回执',macro_construction_preference_released:'建造偏好已释放',macro_construction_feedback:'收到原生施工观测',
  command_outcome:'收到操作回执',native_sequence_reserved:'分配原生指令序号',host_started:'宿主已启动',host_stopped:'宿主已停止',host_fault:'宿主需要处理',
  executor_connected:'执行器握手通过',natural_observer_started:'开始观察原生生产',entered_match:'已进入真实对局',task_feedback:'任务回执',
  dispatch_pending:'任务等待派发',dispatch_unknown:'任务派发结果未知',decision:'策略评估完成',sample_retry:'丢弃不完整采样并重新观察',sampling_failed:'无法继续观察游戏',
  native_result_candidate:'观察到结算候选，等待独立确认',native_result_candidate_after_cleanup:'清理后观察到结算候选',
  commander_profile_applied:'宿主应用了配置',commander_model_backend_constructed:'模型适配器已构造',commander_model_call_started:'模型调用已发起',
  commander_model_response_returned:'模型响应已返回',commander_model_call_failed:'模型调用失败',commander_model_call_cancelled:'模型调用已取消',
  runtime_model_task_feedback:'局部机动回执',runtime_model_preparation_exhausted:'本次单位准备结束',runtime_tactical_waiting_successor:'通道已清理，等待新单位',runtime_tactical_epoch_renewed:'局部通道已接续',
  executor_restoration_unverified:'执行器控制归还尚未验证',unprojected_event:'其他事件（详情已脱敏）'};
export function eventDescription(event:NativeEvent){
  const name=labels[event.event_type]??'宿主状态更新';
  if(event.profile_binding_matches===false)return `${name} · 对应其他配置修订`;
  const reason=event.facts?.reason_code;
  return typeof reason==='string'&&/^[a-z][a-z0-9_]{0,79}$/.test(reason)?`${name} · ${reason}`:name;
}
export function runLocksControls(state:string|undefined,releaseVerified?:boolean){
  // A stop/fault/result candidate is not independent control-release evidence.
  if(state===undefined)return false;
  return !(['completed','stopped','fault','result_candidate'].includes(state)&&releaseVerified===true);
}
export function releaseDescription(verified:boolean|undefined){return verified===true?'已收到独立控制归还验证':'尚未收到独立控制归还验证';}
export function localPreparationDescription(state:string|undefined){
  const names:Record<string,string>={waiting_paid_unit:'等待付费单位生产完成',retired_waiting_paid_unit:'旧通道已清理，等待新的付费单位',
    waiting_native_readiness:'等待单位状态和安全地点就绪',waiting_production_barrier:'等待当前生产回执后清理通道',available:'单位和地点已就绪，等待模型选择',active:'正在执行已接受的局部任务'};
  return state&&names[state]||'等待宿主核验';
}
export const definitelyRefusedStart=new Set(['readiness_invalid','readiness_expired','session_changed','session_unavailable','session_mismatch',
  'session_not_ready','capability_unavailable','credentials_unavailable','effective_profile_changed','profile_revision_conflict']);
export function preservePendingStart(code:string|undefined){return !code||!definitelyRefusedStart.has(code);}
export function sameRun(expected:{run_id:string;session_id:string},actual:{run_id:string;session_id:string}){
  return expected.run_id===actual.run_id&&expected.session_id===actual.session_id;
}
