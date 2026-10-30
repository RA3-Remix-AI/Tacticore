/** Read-only display of the explicit strategic boundary. Never issues commands. */
export const strategicActionLabels = {
  budgeteconomy: '经济投入优先（预算偏好）', budgetarmy: '军备投入优先（预算偏好）', budgettech: '科技投入优先（预算偏好）',
  scout: '额外侦察意图', deployattack: '进攻调度意图', deploydefense: '防守调度意图',
  regroup: '集结意图', withdraw: '撤退意图', reinforce: '增援意图',
  expand: '原生扩张意图', pauseconstruction: '暂缓原生建造调度', advanceconstruction: '推进原生建造调度',
  pauseproduction: '暂缓原生生产调度', advanceproduction: '推进原生生产调度',
} as const;
export type StrategicAction = keyof typeof strategicActionLabels;
export interface StrategicClientRecord {
  schema_version: 1; kind: 'commander_strategic_client_record_v1';
  boundary: 'strategic_only' | 'historical_precision' | 'unverified';
  available_actions: StrategicAction[]; current_actions: StrategicAction[] | null;
  current_intent_state: 'awaiting' | 'reported' | 'invalid';
  budget_adoption: 'adopted' | 'pending' | 'clearing' | 'not_observed' | 'unavailable';
  budget_policy: 'budgeteconomy' | 'budgetarmy' | 'budgettech' | null;
  unconnected_intents: string[];
  details_owner: 'native_ai'; record_only: true; dispatch_authorized: false;
  native_acceptance_proves_success: false; extra_preferences_clear_is_global_stop: false;
}
const object = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const member = (v: unknown, values: readonly string[]): v is string => typeof v === 'string' && values.includes(v);
const budgets = ['budgeteconomy', 'budgetarmy', 'budgettech'] as const;
const missing = ['native_construction_pause', 'native_production_pause', 'resource_expansion'];
const keys = ['schema_version', 'kind', 'boundary', 'available_actions', 'current_actions', 'current_intent_state',
  'budget_adoption', 'budget_policy', 'unconnected_intents', 'details_owner', 'record_only', 'dispatch_authorized',
  'native_acceptance_proves_success', 'extra_preferences_clear_is_global_stop'].sort().join(',');
const missingFor = (offered: readonly string[]) => missing.filter((_,i)=>!offered.includes(['pauseconstruction','pauseproduction','expand'][i]));
const gates = ['pauseconstruction','advanceconstruction','pauseproduction','advanceproduction'];
const actions = (v: unknown): v is StrategicAction[] => Array.isArray(v) && v.length <= 14
  && v.every(a => typeof a === 'string' && Object.hasOwn(strategicActionLabels, a)) && new Set(v).size === v.length;
function record(v: unknown): v is StrategicClientRecord {
  if (!object(v) || Object.keys(v).sort().join(',') !== keys || v.schema_version !== 1
    || v.kind !== 'commander_strategic_client_record_v1' || !member(v.boundary, ['strategic_only', 'historical_precision', 'unverified'])
    || !actions(v.available_actions) || !(v.current_actions === null || actions(v.current_actions))
    || !member(v.current_intent_state, ['awaiting', 'reported', 'invalid'])
    || !member(v.budget_adoption, ['adopted', 'pending', 'clearing', 'not_observed', 'unavailable'])
    || !(v.budget_policy === null || member(v.budget_policy, budgets))
    || JSON.stringify(v.unconnected_intents) !== JSON.stringify(missingFor(v.available_actions)) || v.details_owner !== 'native_ai'
    || v.record_only !== true || v.dispatch_authorized !== false || v.native_acceptance_proves_success !== false
    || v.extra_preferences_clear_is_global_stop !== false) return false;
  if (v.boundary !== 'strategic_only') return v.available_actions.length === 0 && v.current_actions === null
    && v.current_intent_state === 'awaiting' && v.budget_adoption === 'unavailable' && v.budget_policy === null;
  if ((v.current_intent_state === 'reported') !== (v.current_actions !== null)) return false;
  const offered = v.available_actions;
  if (v.current_actions !== null && (v.current_actions.length > 4
    || v.current_actions.some(a => !offered.includes(a))
    || v.current_actions.filter(a => budgets.includes(a as typeof budgets[number])).length > 1
    || v.current_actions.filter(a => !budgets.includes(a as typeof budgets[number])&&!gates.includes(a)).length > 1
    || v.current_actions.filter(a => ['pauseconstruction','advanceconstruction'].includes(a)).length > 1
    || v.current_actions.filter(a => ['pauseproduction','advanceproduction'].includes(a)).length > 1)) return false;
  if (['adopted', 'pending'].includes(v.budget_adoption) && v.budget_policy === null) return false;
  if (v.budget_adoption === 'unavailable' && v.budget_policy !== null) return false;
  return v.budget_adoption !== 'not_observed' || v.budget_policy === null;
}
export interface StrategicCommandView {
  available: boolean; uncertain: boolean; historical: boolean; boundary: string; capabilities: string;
  current: string; budget: string; unconnected: string[]; nativeDetails: string; evidence: string;
}
const nativeDetails = '当前职责边界：具体建筑、落点、顺序、兵种、数量、搭配及全部单位操作由原生 AI 自主决定。';
const unconnected = ['整体暂停建设：未接通。', '整体暂停生产：未接通。', '资源扩张的原生高层入口：未接通。'];
const evidence = '收到命令回执不等于战略成功；原生自主效果也不全部归因于指挥官。';
export function strategicCommandView(value: unknown): StrategicCommandView {
  const empty = {available: false, uncertain: true, historical: false, boundary: '接管边界尚未核验',
    capabilities: '等待本局核验', current: '等待可核验的高层意图', budget: '等待有效的原生预算观测。',
    unconnected: [], nativeDetails, evidence};
  if (!record(value)) return empty;
  if (value.boundary !== 'strategic_only') return {...empty, historical: value.boundary === 'historical_precision',
    boundary: value.boundary === 'historical_precision' ? '历史研究记录，未按当前战略边界验收' : empty.boundary};
  const current = value.current_intent_state === 'invalid' ? '本条记录不符合高层边界，未展示为有效指挥。'
    : value.current_actions === null ? '等待模型提出高层意图。'
      : value.current_actions.length ? value.current_actions.map(a => strategicActionLabels[a]).join('、')
        : '未追加高层偏好；原生 AI 继续自主运作。';
  const budgetState = {adopted: '已观测原生采用预算偏好；战略效果仍待核验。', pending: '已记录预算偏好，等待原生采用证据。',
    clearing: '正在核对额外预算偏好的撤销；这不会停止全部原生工作。', not_observed: '本次预算采样未见额外预算偏好；其他原生任务仍需单独观察。',
    unavailable: '等待有效的原生预算观测。'};
  return {available: true, uncertain: value.current_intent_state === 'invalid', historical: false,
    boundary: '指挥官判断高层意图，原生 AI 决定执行细节',
    capabilities: value.available_actions.map(a => strategicActionLabels[a]).join('、') || '当前没有已接通的额外高层入口',
    current, budget: budgetState[value.budget_adoption], unconnected: value.unconnected_intents.map(name=>unconnected[missing.indexOf(name)]), nativeDetails, evidence};
}

/** Current readiness projection only; this is not a Host observation. */
export function strategicPreflightView(capabilities: unknown): StrategicCommandView {
  if (!object(capabilities) || capabilities.native_macro !== true || capabilities.commander_boundary !== 'native_ai_details_v1'
    || !actions(capabilities.available_macro_actions)) return strategicCommandView(undefined);
  const view = strategicCommandView({schema_version: 1, kind: 'commander_strategic_client_record_v1', boundary: 'strategic_only',
    available_actions: capabilities.available_macro_actions, current_actions: null, current_intent_state: 'awaiting',
    budget_adoption: 'unavailable', budget_policy: null, unconnected_intents: missingFor(capabilities.available_macro_actions), details_owner: 'native_ai', record_only: true,
    dispatch_authorized: false, native_acceptance_proves_success: false, extra_preferences_clear_is_global_stop: false});
  return {...view, current: '本次检查通过，尚未启动指挥官；等待模型提出高层意图。'};
}
