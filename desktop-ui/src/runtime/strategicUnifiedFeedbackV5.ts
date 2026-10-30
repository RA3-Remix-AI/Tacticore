import { strategicActionLabels } from './strategicCommandView';

export function strategicUnifiedFeedbackV5(value: unknown): string[] {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return [];
  const v = value as Record<string, unknown>;
  if (v.source !== 'bound_native_strategy_v5' || v.details_owner !== 'native_ai'
    || !Number.isInteger(v.observed_frame) || Number(v.observed_frame) <= 0
    || !Array.isArray(v.observations) || v.observations.length > 4) return [];
  const rows: string[] = [], seen = new Set<string>();
  for (const raw of v.observations) {
    if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) return [];
    const r = raw as Record<string, unknown>, action = r.action;
    if (typeof action !== 'string' || !Object.hasOwn(strategicActionLabels, action) || seen.has(action)
      || !['native_task_active', 'native_manager_state_observed', 'native_waiting_or_no_effect', 'preference_released'].includes(String(r.status))
      || ['preference_active', 'active_native_task_observed', 'movement_observed', 'component_state_adopted', 'state_already_satisfied'].some(k => typeof r[k] !== 'boolean')
      || r.mission_success_verified !== false || r.exclusive_attribution_verified !== false
      || !Number.isInteger(r.observed_frame) || Number(r.observed_frame) > Number(v.observed_frame)
      || Number(v.observed_frame) - Number(r.observed_frame) > 15) return [];
    seen.add(action);
    const state = !r.preference_active ? '额外偏好已释放。'
      : r.component_state_adopted ? `已读回原生调度状态${r.state_already_satisfied ? '（原状态已满足）' : ''}；具体建造、生产结果仍待观察。`
        : r.active_native_task_observed ? `原生任务活动中${r.movement_observed ? '，已观测己方成员移动' : '，尚未观测成员移动'}；任务完成尚未核验。`
          : '偏好仍有效，等待原生采用或可核验效果。';
    rows.push(`${strategicActionLabels[action as keyof typeof strategicActionLabels]}：${state}`);
  }
  return rows;
}
