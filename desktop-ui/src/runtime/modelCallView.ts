import type {NativeEvent} from './nativeProcess';
import type {ConsumptionReceipt} from './applicationView';

export interface ModelConsumptionReceipt extends ConsumptionReceipt {stage?: string}
interface CallScope {profile_id?: string; profile_revision?: number; effective_hash?: string}

export interface ModelCallView {state: 'unavailable' | 'waiting' | 'responded' | 'failed' | 'cancelled'; title: string; detail: string}
const unavailable: ModelCallView = {state: 'unavailable', title: '等待本局模型调用记录', detail: '本机配置保存成功不代表远端连接可用。'};
const labels: Record<string, ModelCallView> = {
  commander_model_call_started: {state: 'waiting', title: '已发起模型调用，等待响应', detail: '这条记录不区分网络等待和模型推理；请继续观察运行状态。'},
  commander_model_response_returned: {state: 'responded', title: '最近一次模型调用已返回', detail: '返回响应不等于方案通过校验，也不代表原生 AI 已执行或取得效果。'},
  commander_model_call_failed: {state: 'failed', title: '最近一次模型调用失败', detail: '当前记录无法确定是网络、服务、模型还是认证问题。请核对提供方服务状态与接口、模型设置；修改连接前先停止并等待控制归还。界面不会重复发送这次请求。'},
  commander_model_call_cancelled: {state: 'cancelled', title: '最近一次模型调用已取消', detail: '取消调用不代表控制已归还；请单独查看控制归还状态。'},
};

/** Read-only summary of the latest call in this run; no transport, retry or failure-cause inference. */
export function modelCallView(events: readonly NativeEvent[] | undefined,
  consumption?: ModelConsumptionReceipt, scope?: CallScope): ModelCallView {
  if (events !== undefined && !Array.isArray(events)) return unavailable;
  let latest: NativeEvent | undefined, previousSeq = -1, latestCall = -1;
  for (const event of events ?? []) {
    if (!event || !Number.isSafeInteger(event.seq) || event.seq <= previousSeq) return unavailable;
    previousSeq = event.seq;
    if (!Object.hasOwn(labels, event.event_type) || event.profile_binding_matches !== true) continue;
    const call = event.facts?.call_sequence;
    if (typeof call !== 'number' || !Number.isSafeInteger(call) || call < 1) return unavailable;
    // A late result for an earlier call must not replace a newer in-flight call.
    if (call < latestCall) continue;
    if (call === latestCall && (event.event_type === 'commander_model_call_started'
      || latest?.event_type !== 'commander_model_call_started')) return unavailable;
    latestCall = call; latest = event;
  }
  // run.status retains the current Host's consumption receipt even after the
  // latest-30-event window evicts every call event, including after reopening.
  // The scope and receipt must come from the same checked run.status response.
  const calls = consumption?.calls_started, responses = consumption?.responses_returned;
  const stageEvents: Record<string, string> = {call_started: 'commander_model_call_started',
    response_returned: 'commander_model_response_returned', call_failed: 'commander_model_call_failed',
    call_cancelled: 'commander_model_call_cancelled'};
  const receiptEvent = consumption?.stage && Object.hasOwn(stageEvents, consumption.stage)
    ? stageEvents[consumption.stage] : undefined;
  const bound = typeof scope?.profile_id === 'string' && scope.profile_id.length > 0
    && Number.isSafeInteger(scope.profile_revision) && (scope.profile_revision ?? 0) > 0
    && typeof scope.effective_hash === 'string' && /^[a-f0-9]{64}$/.test(scope.effective_hash)
    && consumption?.state === 'host_profile_applied' && consumption.profile_id === scope.profile_id
    && consumption.profile_revision === scope.profile_revision && consumption.effective_hash === scope.effective_hash;
  if (bound && receiptEvent && typeof calls === 'number' && Number.isSafeInteger(calls) && calls > 0
    && typeof responses === 'number' && Number.isSafeInteger(responses) && responses >= 0 && responses <= calls
    && consumption?.model_response_received === (responses > 0)
    && (receiptEvent !== 'commander_model_response_returned' || responses > 0)) {
    if (calls > latestCall) return labels[receiptEvent];
    // The event page is read before Host status. A bound terminal receipt can
    // advance the same call while its completion event is outside that page.
    if (calls === latestCall && latest?.event_type === 'commander_model_call_started'
      && receiptEvent !== 'commander_model_call_started') return labels[receiptEvent];
    // Journal delivery can precede the Host status flush for the same call.
    // A terminal event remains current while that receipt still says started.
    if (calls === latestCall && receiptEvent !== 'commander_model_call_started'
      && latest?.event_type !== receiptEvent) return unavailable;
  }
  return latest ? labels[latest.event_type] : unavailable;
}
