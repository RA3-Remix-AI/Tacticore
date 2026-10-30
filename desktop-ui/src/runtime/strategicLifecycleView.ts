/** Human-readable F05/F06 state. This helper performs no operation or retry. */
import {runLocksControls} from './nativeProcess';
export interface StrategicLifecycleInput {
  state: string; native_release_verified?: boolean; no_native_execution_started?: boolean;
  host_process_alive?: boolean; status_stale?: boolean; reason_code?: string;
}
export interface StrategicLifecycleView {locked: boolean; state: string; release: string; next: string; observation: string; reason: string}
const states: Record<string, string> = {
  starting: '宿主正在启动', running: '指挥官正在运行', sampling_wait: '等待完整战况观测', stopping: '停止请求正在处理',
  uncertain: '运行结果尚未确认', stopped: '宿主已停止', completed: '宿主进程已结束', fault: '宿主需要处理',
  result_candidate: '已观察到结算候选，等待独立确认',
};
const reasons: Record<string, string> = {
  user_stop: '已记录用户停止请求。', native_result_requires_visual_confirmation: '原生结算候选仍需独立确认，尚未认定胜负。',
  delivery_unknown: '送达结果未知，请查询原运行；不要重新启动。',
  host_process_lost_control_returned: '宿主意外结束；已独立确认原生控制归还。原指令的未知送达记录仍保留。',
  strategy_context_before_memory: '战况与模型上下文的时序需要重新核验。',
  macro_runtime_same_epoch_reattach_unsupported: '本游戏进程已经使用过指挥通道，下一局需要正常退出后重新打开游戏。',
};
export function strategicLifecycleView(value: StrategicLifecycleInput): StrategicLifecycleView {
  const locked = runLocksControls(value.state, value.native_release_verified);
  const noNative = value.no_native_execution_started === true && value.native_release_verified === true && value.state === 'stopped';
  return {locked, state: Object.hasOwn(states, value.state) ? states[value.state] : '运行状态尚待核验',
    release: noNative ? '启动已在派发前取消，没有新增原生指挥。'
      : !locked ? '已收到独立控制归还验证。' : '尚未收到当前终态的独立控制归还验证。',
    next: locked ? '继续查询当前运行；尚不能开始下一局指挥。'
      : '可以保留诊断并发现下一局；下一局仍须使用新的受支持会话并重新检查。',
    observation: value.status_stale === true || value.host_process_alive === false
      ? '以下为宿主最后保存的记录，不视为当前战况。' : '以最近一次成功同步的宿主观测为准。',
    reason: value.reason_code ? Object.hasOwn(reasons, value.reason_code) ? reasons[value.reason_code] : '状态原因已记录，可导出诊断核对。' : ''};
}
