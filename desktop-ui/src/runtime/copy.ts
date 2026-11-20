/** Plain-language messages for host reason codes. Unknown codes show a generic line plus the code. */
import {HostError} from './nativeRpc';
import {DiagnosticError} from './diagnosticsDownload';

export const APP_VERSION = '0.1.0-beta.4';

const reasons: Record<string, string> = {
  // Finding a match
  session_discovery_unavailable: '还没有完成游戏设置，请先在「游戏与 Mod」中完成准备。',
  discovery_policy_invalid: '游戏设置记录无效，请在「游戏与 Mod」中重新准备。',
  discovery_source_unavailable: '暂时读不到游戏或运行组件，请确认游戏已打开后重试。',
  discovery_source_changed: '游戏或运行组件有变化，请在「游戏与 Mod」中重新准备。',
  session_discovery_too_many_processes: '同时打开了多个游戏，请只保留要用的那一个。',
  session_scope_unsupported: '这局的设置暂不支持（例如席位或队伍组合）。请按「对局模式」里的提示调整大厅后重试。',
  session_probe_invalid: '对局信息还不稳定，请等几秒后重新查找。',
  session_probe_unavailable: '暂时读不到对局信息，请进入对局后重试。',
  session_paused: '游戏处于暂停状态，继续游戏后再试。',
  session_candidate_expired: '找到的对局已过期，请重新查找。',
  session_selection_required: '请先选择要使用的对局。',
  session_unavailable: '还没有找到可用的对局。',
  session_not_ready: '对局还没准备好，请确认已经进入对局。',
  // Preparing / checking a match
  session_preparation_changed: '对局记录发生了变化，请重新查找对局。',
  session_registration_uncertain: '无法确认对局是否登记成功，可以再试一次；AI 不会被启动。',
  session_root_conflict: '本机对局记录有冲突，请在「游戏与 Mod」中重新准备。',
  session_registration_conflict: '上一局还没有完全结束，请先确认它已停止。',
  session_registration_changed: '本机对局记录已变化，请重新查找对局。',
  session_root_invalid: '本机对局记录无效，请重启客户端后重试。',
  macro_runtime_same_epoch_reattach_unsupported: '这个游戏进程已经用过一次。请完全退出游戏并重新打开，再开始新的对局。',
  legacy_executor_player_unsupported: '弈核 AI 暂不支持当前席位，请换一个席位或调整大厅。',
  capability_unavailable: '这局所需的能力暂不可用。',
  readiness_expired: '检查结果已过期，请再点一次「开始」。',
  readiness_invalid: '检查结果无效，请再点一次「开始」。',
  opening_wait_expired: '等待超过五分钟，已取消自动开始。',
  // Configuration
  adapter_unavailable: '本机服务还没有准备好，请稍后重试。',
  profile_library_unavailable: '找不到本机 AI 配置，请在「模型与 API Key」中初始化。',
  runtime_library_unregistered: '请先在「模型与 API Key」中完成初始化。',
  runtime_library_unavailable: '本机 AI 配置暂时无法读取。',
  registered_library_changed: '本机 AI 配置有变化，请重新打开「模型与 API Key」确认。',
  runtime_configuration_invalid: '本机配置无效，请在「模型与 API Key」中重新确认。',
  runtime_configuration_changed: '本机配置已变化，请在「模型与 API Key」中重新确认。',
  connection_config_recovery_required: '模型设置有未完成的保存，请在「模型与 API Key」中处理。',
  profile_revision_conflict: 'AI 风格在其他地方被修改了，请重新载入。',
  effective_profile_changed: 'AI 设置已变化，请重新开始。',
  traits_budget_exceeded: '补充要求太长了，请缩短一些（风格说明与补充要求合计不超过 1200 字节）。',
  model_context_capacity_exceeded_shorten_style: '补充要求太长，模型放不下。请缩短后重试。',
  model_context_capacity_provider_unavailable: '暂时无法确认这个模型服务的容量，请重新保存模型设置后重试。',
  model_context_capacity_contract_invalid: '客户端版本和运行组件不匹配，请重新安装最新版本。',
  credentials_unavailable: '读不到保存的 API Key，请在「模型与 API Key」中重新填写。',
  // Runs
  delivery_unknown: '无法确认操作是否送达。客户端会继续查询状态，请不要重复开始。',
  run_state_conflict: '还有一局没有确认结束，请先处理它。',
  run_history_unverifiable: '上一局的记录不完整，暂时不能开始新的对局。请导出诊断信息并反馈。',
  run_not_found: '找不到这局的运行记录。',
  user_stop: '已按你的要求停止。',
  // Packaging
  runtime_layout_unavailable: '运行组件不完整，请重新安装。',
  runtime_packaging_unavailable: '这个版本缺少运行组件，请安装正式发布包。',
  runtime_packaging_invalid: '运行组件校验失败，请重新安装正式发布包。',
  // Diagnostics
  diagnostics_read_failed: '诊断文件没有读取完整，请重新导出。',
  diagnostics_integrity_invalid: '诊断文件校验失败，没有下载。',
  diagnostics_binding_invalid: '诊断文件不属于当前对局，没有下载。',
  diagnostics_receipt_invalid: '诊断导出结果无效，没有下载。',
  diagnostics_document_invalid: '诊断文件格式无效，没有下载。',
  diagnostics_unavailable: '暂时无法导出诊断信息。',
};

export function reasonText(code: string | undefined | null): string {
  if (!code) return '操作没有完成。';
  return reasons[code] ?? `操作没有完成（代码：${code}）。`;
}

export function hasReason(code: string): boolean {
  return Object.hasOwn(reasons, code);
}

export function errorText(error: unknown): string {
  if (error instanceof HostError || error instanceof DiagnosticError) return reasonText(error.code);
  return '操作没有完成，请确认客户端服务正常后重试。';
}

/** Plain run-state names for the details panel. */
export const runStateLabels: Record<string, string> = {
  running: '指挥中', starting: '启动中', stopping: '停止中', stopped: '已停止', completed: '已结束',
  fault: '出现问题', failed: '出现问题', uncertain: '状态确认中', result_candidate: '对局可能已结算', sampling_wait: '等待游戏数据',
};

export function releaseText(verified: boolean | undefined): string {
  return verified === true ? '已确认交还' : '尚未确认交还';
}
