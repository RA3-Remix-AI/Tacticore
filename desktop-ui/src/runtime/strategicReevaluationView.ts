/** Presentation of F04 history only. It does not maintain memory or dispatch. */
import type {MacroStrategyPublicState, MacroStrategyOutcomeKind} from './nativeRpc';
import {macroStrategyView} from './macroStrategyView';
const descriptions: Record<MacroStrategyOutcomeKind, string> = {
  pending: '等待原生效果核验', effect_observed: '已观察到有界原生效果', no_effect: '有效窗口内未见合格效果',
  failed: '本条意图未达预期', cancelled: '本条意图已取消', expired: '本条意图已到期',
  replaced: '已由后续意图替换', unknown: '结果未知，先核对且不自动重发',
};
export interface StrategicReevaluationView {available: boolean; uncertain: boolean; history: string[]; next: string}
export function strategicReevaluationView(value: unknown): StrategicReevaluationView {
  const validated = macroStrategyView(value);
  if (!validated.available) return {available: false, uncertain: value != null, history: [], next: '等待可核验的效果与重评记录。'};
  const state = value as MacroStrategyPublicState;
  if (state.recent_outcomes.some((row, index, rows) => index > 0 && row.at_game_seconds < rows[index - 1].at_game_seconds)) {
    return {available: false, uncertain: true, history: [], next: '效果记录的时间顺序尚未核验。'};
  }
  const history = state.recent_outcomes.map(row => `游戏时间 ${Math.floor(row.at_game_seconds)} 秒：${descriptions[row.outcome]}${
    row.effect_verified && row.outcome !== 'effect_observed' ? '；此前曾观测到有界效果' : ''}。`);
  return {available: true, uncertain: state.unknown_command_count > 0, history,
    next: `${validated.guard} ${validated.pending}`};
}
