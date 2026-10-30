import type {MacroStrategyPublicState,MacroStrategyObjective,MacroStrategyPhase,MacroStrategyExpected,MacroStrategyOutcome} from './nativeRpc';

const objectives:Record<MacroStrategyObjective,string>={economic_stability:'稳定经济',expand_economy:'扩充经济',develop_technology:'推进科技',
  build_force:'补充与调整兵力',scout:'获取战场情报',pressure:'向敌方施压',defend_base:'防守己方基地',recover_force:'撤回并恢复兵力',hold:'保持当前态势'};
const phases:Record<MacroStrategyPhase,string>={prepare:'准备条件',execute:'执行当前意图',assess:'核对效果并调整',wait:'等待合适条件'};
const expectations:Record<MacroStrategyExpected,string>={resource_recovery:'资源状况改善',construction_queue:'出现新的建造队列',
  building_operational:'设施可运转的核验结果',production_queue:'出现新的生产队列',unit_completed:'单位出厂的核验结果',
  technology_unlocked:'科技解锁的核验结果',new_lawful_contact:'获得新的合法情报',force_region_change:'己方部队部署变化',
  threat_reduced:'威胁减轻的观测',no_change:'维持现有状态'};
const guards:Record<string,string>={strategy_allowed:'当前计划通过战略检查。',strategy_stopped:'已停止新增战略指挥。',
  strategy_unknown_outcome:'等待未知结果核对，暂不新增指挥。',strategy_intent_in_flight:'同类意图仍在进行，等待结果。',
  strategy_no_effect_cooldown:'相同条件下先等待，避免重复无效指挥。',strategy_production_renewal_wait:'等待生产变化，再决定是否补充。',
  strategy_minimum_hold:'暂时保持当前目标，等待新的事实。',strategy_plan_already_dispatched:'同一计划已处理，避免重复执行。',
  strategy_game_paused:'游戏已暂停，等待恢复。'};
const conditions=new Set(['capability_available','resources_sufficient','prerequisite_met','no_new_threat','target_valid','effect_pending','effect_observed','facts_changed','goal_unobserved']);
const outcomes=new Set(['pending','effect_observed','no_effect','failed','cancelled','expired','replaced','unknown']);
const object=(v:unknown):v is Record<string,unknown>=>typeof v==='object'&&v!==null&&!Array.isArray(v);
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const code=/^[a-z][a-z0-9_]{0,63}$/;
const time=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=86400;
const count=(v:unknown):v is number=>typeof v==='number'&&Number.isInteger(v)&&v>=0&&v<=64;
const member=(v:unknown,set:object)=>typeof v==='string'&&Object.hasOwn(set,v);
const conditionList=(v:unknown)=>Array.isArray(v)&&v.length>=1&&v.length<=3&&v.every(x=>typeof x==='string'&&conditions.has(x))&&new Set(v).size===v.length;
function outcome(value:unknown):value is MacroStrategyOutcome {
  return object(value)&&typeof value.plan_id==='string'&&uuid.test(value.plan_id)&&typeof value.outcome==='string'&&outcomes.has(value.outcome)
    &&typeof value.effect_verified==='boolean'&&typeof value.reason_code==='string'&&code.test(value.reason_code)&&time(value.at_game_seconds)
    &&(value.outcome!=='effect_observed'||value.effect_verified)&&(!['pending','no_effect'].includes(value.outcome)||!value.effect_verified);
}
function state(value:unknown):value is MacroStrategyPublicState {
  if(!object(value)||value.schema_version!==1||value.kind!=='macro_strategy_public_state'||typeof value.stopped!=='boolean'
    ||!count(value.unknown_command_count)||!count(value.unreleased_command_count)||value.unknown_command_count>value.unreleased_command_count
    ||!(value.last_guard_reason===null||typeof value.last_guard_reason==='string'&&code.test(value.last_guard_reason))
    ||!Array.isArray(value.recent_outcomes)||value.recent_outcomes.length>4||!value.recent_outcomes.every(outcome))return false;
  const current=value.current_strategy;
  if(current===null)return true;
  if(!object(current)||typeof current.strategy_id!=='string'||!uuid.test(current.strategy_id)||!member(current.objective,objectives)
    ||!member(current.phase,phases)||!member(current.expected_observation,expectations)||!time(current.updated_game_seconds)
    ||!Array.isArray(current.public_fact_refs)||current.public_fact_refs.length<1||current.public_fact_refs.length>4
    ||!current.public_fact_refs.every(x=>typeof x==='string'&&/^[a-z][a-z0-9_.]{0,95}$/.test(x))
    ||!conditionList(current.continue_conditions)||!conditionList(current.replan_conditions)
    ||!(current.last_outcome===null||outcome(current.last_outcome))||!object(current.resource_priorities))return false;
  const priorities=current.resource_priorities;
  const keys=['economy','army','tech','reserve'];
  return Object.keys(priorities).length===4&&keys.every(k=>typeof priorities[k]==='number'&&Number.isFinite(priorities[k])&&(priorities[k] as number)>=0&&(priorities[k] as number)<=1)
    &&Math.abs(keys.reduce((sum,k)=>sum+(priorities[k] as number),0)-1)<=1e-6;
}
function describeOutcome(value:MacroStrategyOutcome):string {
  if(value.outcome==='unknown')return value.effect_verified?'此前曾观测到效果；当前结果仍未知。':'结果未知，不能认定成功或失败。';
  if(value.outcome==='effect_observed')return '已观测到对应的有界原生效果。';
  const labels={pending:'等待原生效果核验。',no_effect:'有效窗口内未取得合格效果，意图已结束。',failed:'本条意图未达预期，已结束。',
    cancelled:'本条意图已取消。',expired:'本条意图已到期。',replaced:'本条意图已被后续指令替换。'};
  return labels[value.outcome]+(value.effect_verified?' 此前观测到有界效果。':'');
}
export interface MacroStrategyView {
  available:boolean;objective:string;phase:string;expectation:string;latest:string;guard:string;pending:string;uncertain:boolean;updated:string;
}
/** Render only known labels and bounded counters; never echo unknown codes or raw state. */
export function macroStrategyView(value:unknown,unavailable=false):MacroStrategyView {
  if(unavailable||!state(value)){
    const rejected=unavailable||value!==undefined&&value!==null;
    return {available:false,objective:rejected?'长期战略记录暂不可核验':'等待模型声明长期目标',phase:'等待核验',
      expectation:'等待有效声明',latest:'尚无可展示的核验结果。',guard:'等待战略状态同步。',pending:'未取得有效的未决状态记录。',uncertain:rejected,updated:''};
  }
  const current=value.current_strategy,previous=value.recent_outcomes.at(-1);
  const known=value.unreleased_command_count-value.unknown_command_count;
  let pending:string;
  if(value.unknown_command_count>0)pending=`${value.stopped?'已停止新增指挥；':''}结果未知 ${value.unknown_command_count} 条${known>0?`，另有 ${known} 条意图等待结束核验`:''}。先核对未知结果，暂不新增指挥。`;
  else if(known>0)pending=`${value.stopped?'已停止新增指挥，仍有':''}${known} 条宏观意图正在执行或等待结束核验。`;
  else pending=value.stopped?'已停止新增战略指挥。':'暂无等待结束核验的宏观意图。';
  return {available:true,objective:current?objectives[current.objective]:'等待模型声明长期目标',phase:current?phases[current.phase]:'等待声明',
    expectation:current?expectations[current.expected_observation]:'等待有效声明',
    latest:current?.last_outcome?describeOutcome(current.last_outcome):previous?'此前意图：'+describeOutcome(previous):'尚无已核验的效果结果。',
    guard:value.last_guard_reason?(Object.hasOwn(guards,value.last_guard_reason)?guards[value.last_guard_reason]:'战略检查结果已记录，可查看诊断。'):'等待下一次战略检查。',
    pending,uncertain:value.unknown_command_count>0,updated:current?`游戏时间 ${Math.floor(current.updated_game_seconds)} 秒更新`:''};
}
