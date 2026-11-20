/** Separate trusted native configuration channel, awaiting native fusion. */
import {invoke} from '@tauri-apps/api/core';
import {HostError} from './nativeRpc';
export type ConnectionConfigOperation = 'connections.configuration' | 'connections.configure' | 'connections.recover'
  | 'connections.cleanup_retired' | 'connections.bootstrap' | 'connections.test';
export interface ConnectionConfiguration {
  schema_version: 1; ready: boolean; config_fingerprint: string | null;
  connections: {id: string; name: string; provider: 'OpenAI' | 'DeepSeek' | '自定义'; endpoint: string; model: string;
    remember_key: boolean; credential_configured: boolean; credential_check: 'stored_not_read' | 'not_stored'}[];
  recovery: ConfigurationReference[]; retired_credentials: ConfigurationReference[];
  remote_connection_tested: false; host_recheck_required: true;
}
export interface ConfigurationReference {configuration_request_id: string; expected_config_fingerprint: string}
export interface ConfigureConnection {
  schema_version: 1; connection_id: string; expected_config_fingerprint: string;
  name: string; provider: 'OpenAI' | 'DeepSeek' | '自定义'; endpoint: string; model: string;
  credential_operation: 'keep' | 'set' | 'clear'; api_key?: string;
}
export type ConnectionConfigRpc = <T extends object>(operation: ConnectionConfigOperation, args: object, requestId?: string) => Promise<T>;
const uuid = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(v);
const sha = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const object = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const refs = (v: unknown): v is ConfigurationReference[] => Array.isArray(v) && v.length <= 1024
  && v.every(row => object(row) && Object.keys(row).sort().join(',') === 'configuration_request_id,expected_config_fingerprint'
    && uuid(row.configuration_request_id) && sha(row.expected_config_fingerprint));
export function connectionConfiguration(value: unknown): ConnectionConfiguration {
  if (!object(value) || value.schema_version !== 1 || typeof value.ready !== 'boolean'
    || !(value.config_fingerprint === null || sha(value.config_fingerprint)) || !refs(value.recovery) || !refs(value.retired_credentials)
    || value.remote_connection_tested !== false || value.host_recheck_required !== true
    || !Array.isArray(value.connections) || value.connections.length > 100
    || !value.connections.every(row => object(row) && uuid(row.id) && typeof row.name === 'string' && row.name.length <= 60
      && ['OpenAI', 'DeepSeek', '自定义'].includes(String(row.provider)) && typeof row.endpoint === 'string' && row.endpoint.length <= 2048
      && typeof row.model === 'string' && row.model.length <= 200 && typeof row.remember_key === 'boolean'
      && typeof row.credential_configured === 'boolean' && ['stored_not_read', 'not_stored'].includes(String(row.credential_check)))) {
    throw new HostError('connection_config_response_invalid', 'configuration');
  }
  if (value.ready ? !sha(value.config_fingerprint) || value.connections.length === 0 || value.recovery.length !== 0
    : value.config_fingerprint !== null || value.connections.length !== 0 || value.recovery.length === 0) {
    throw new HostError('connection_config_response_invalid', 'configuration');
  }
  return value as unknown as ConnectionConfiguration;
}
function responseSafe(value: unknown, depth = 0): boolean {
  if (depth > 16) return false;
  if (Array.isArray(value)) return value.every(row => responseSafe(row, depth + 1));
  if (!object(value)) return value === null || ['boolean', 'number', 'string'].includes(typeof value);
  const forbidden = new Set(['key', 'apikey', 'secret', 'credentialvalue', 'credentialreference', 'path', 'librarypath', 'commandline']);
  return Object.entries(value).every(([key, row]) => !forbidden.has(key.toLowerCase().replace(/[_-]/g, '')) && responseSafe(row, depth + 1));
}
/** At most one invocation. An uncertain save is reconciled, never repeated automatically. */
export function createConnectionConfigRpc(call: (command: string, args: {request: object}) => Promise<unknown> = invoke): ConnectionConfigRpc {
  return async<T extends object>(operation: ConnectionConfigOperation, args: object, requestId: string = crypto.randomUUID()): Promise<T> => {
    if (!uuid(requestId)) throw new HostError('invalid_request_id', requestId);
    const request = {schema_version: 1, request_id: requestId, operation, args};
    if (new TextEncoder().encode(JSON.stringify(request)).length > 16384) throw new HostError('request_too_large', requestId);
    let reply: unknown;
    try {reply = await call('connection_config_request', {request});}
    catch {throw new HostError('delivery_unknown', requestId);}
    if (!object(reply) || reply.schema_version !== 1 || reply.request_id !== requestId || typeof reply.ok !== 'boolean') {
      throw new HostError('delivery_unknown', requestId);
    }
    if (!reply.ok) {
      const code = object(reply.error) && typeof reply.error.code === 'string' && /^[a-z][a-z0-9_]{0,79}$/.test(reply.error.code)
        ? reply.error.code : 'connection_config_unavailable';
      throw new HostError(code, requestId);
    }
    if (!object(reply.result) || !responseSafe(reply.result)) throw new HostError('connection_config_response_invalid', requestId);
    return reply.result as T;
  };
}
export const connectionConfigRpc = createConnectionConfigRpc();
const errors: Record<string, string> = {
  connection_setup_required: '还没有初始化模型设置，请点击下方的「开始设置」。',
  connection_setup_existing_source: '本机已有模型设置，不会被覆盖。请点击「重新读取」。',
  connection_config_changed: '设置在别处被修改了，请重新读取后再保存。',
  connection_config_run_unreleased: '弈核 AI 正在使用游戏。请先停止它，再修改模型设置。',
  connection_config_recovery_required: '上次保存还没有完成，请点击「处理未完成的保存」。',
  connection_credential_reentry_required: '更换了服务商或接口地址，请重新填写 API Key，或选择清除已保存的 Key。',
  invalid_connection_endpoint: '接口地址需要以 https:// 开头（本机服务可以用 http://），不能包含用户名、密码或参数。',
  connection_credential_invalid: 'API Key 不能为空，也不能包含空格或换行。',
  delivery_unknown: '无法确认是否保存成功，请点击「重新读取」查看；不会自动重复保存。',
  request_id_conflict: '这次保存和之前的记录冲突，请重新读取后再试。',
};
export function connectionConfigError(error: unknown): string {
  return error instanceof HostError && Object.hasOwn(errors, error.code) ? errors[error.code]
    : '模型设置操作没有完成，请点击「重新读取」后再试。';
}

/**
 * Optional backend operation `connections.test` (args `{connection_id}`): one
 * real request with the saved key, performed by the host. The key never
 * reaches the WebView. Older backends answer operation_unsupported.
 */
export interface ConnectionTestResult {reachable: boolean; latency_ms: number | null; reason_code: string | null}
export type ConnectionTestOutcome =
  | {state: 'ok'; result: ConnectionTestResult}
  | {state: 'unsupported'}
  | {state: 'failed'; code: string};

export function parseConnectionTest(value: unknown): ConnectionTestResult | null {
  if (!object(value) || typeof value.reachable !== 'boolean') return null;
  const latency = typeof value.latency_ms === 'number' && Number.isFinite(value.latency_ms) ? value.latency_ms : null;
  const reason = typeof value.reason_code === 'string' && /^[a-z][a-z0-9_]{0,79}$/.test(value.reason_code) ? value.reason_code : null;
  return {reachable: value.reachable, latency_ms: latency, reason_code: reason};
}

export async function testConnection(rpc: ConnectionConfigRpc, connectionId: string): Promise<ConnectionTestOutcome> {
  try {
    const result = parseConnectionTest(await rpc('connections.test', {connection_id: connectionId}));
    return result ? {state: 'ok', result} : {state: 'failed', code: 'connection_test_response_invalid'};
  } catch (error) {
    const code = error instanceof HostError ? error.code : 'delivery_unknown';
    // An older native layer rejects the unknown operation before delivery.
    return code === 'operation_unsupported' || code === 'request_invalid' ? {state: 'unsupported'} : {state: 'failed', code};
  }
}

const testReasons: Record<string, string> = {
  authentication_failed: 'API Key 无效或没有权限。',
  model_not_found: '服务商找不到这个模型名称。',
  endpoint_unreachable: '连不上接口地址，请检查网络和地址。',
  rate_limited: '请求太频繁或额度不足。',
  timeout: '等待响应超时。',
  credentials_unavailable: '还没有保存 API Key。',
};

export function connectionTestText(outcome: ConnectionTestOutcome): {text: string; ok: boolean} {
  if (outcome.state === 'unsupported') {
    return {ok: false, text: '当前版本还不能在这里测试连接。开始对局后，模型是否正常会显示在决策记录里。'};
  }
  if (outcome.state === 'failed') {
    return {ok: false, text: outcome.code === 'delivery_unknown'
      ? '无法确认测试结果，请稍后再试。' : `测试没有完成（${outcome.code}）。`};
  }
  const {result} = outcome;
  if (result.reachable) {
    return {ok: true, text: `连接正常${result.latency_ms === null ? '' : `，响应用时 ${Math.round(result.latency_ms)} ms`}。`};
  }
  return {ok: false, text: `连接失败：${testReasons[result.reason_code ?? ''] ?? (result.reason_code ?? '原因未知')}`};
}
