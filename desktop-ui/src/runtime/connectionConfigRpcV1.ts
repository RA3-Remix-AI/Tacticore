/** Separate trusted native configuration channel, awaiting native fusion. */
import {invoke} from '@tauri-apps/api/core';
import {HostError} from './nativeRpc';
export type ConnectionConfigOperation = 'connections.configuration' | 'connections.configure' | 'connections.recover'
  | 'connections.cleanup_retired' | 'connections.bootstrap';
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
  connection_setup_required: '尚未建立本机连接配置，可使用下方初始化按钮。',
  connection_setup_existing_source: '已有本机配置来源，当前不会覆盖；请重新查询并核对配置。',
  connection_config_changed: '配置已在另一处更新，请重新载入后再保存。',
  connection_config_run_unreleased: '当前运行尚未确认归还，请先停止并核验后修改连接。',
  connection_config_recovery_required: '上次配置更新尚未核验，请查询并核对未完成的保存。',
  connection_credential_reentry_required: '更改提供方或接口时，需要重新输入该接口的密钥，或选择停用密钥。',
  invalid_connection_endpoint: '请填写 HTTPS 接口根地址；本机服务可使用 HTTP。地址不能含用户名、密码、查询参数或补全路径。',
  connection_credential_invalid: '密钥不能为空，也不能含空格或换行。',
  delivery_unknown: '保存结果未知，请重新查询配置；不会自动重复保存。',
  request_id_conflict: '操作标识与已有保存不一致，请重新载入配置。',
};
export function connectionConfigError(error: unknown): string {
  return error instanceof HostError && Object.hasOwn(errors, error.code) ? errors[error.code]
    : '本机连接配置操作未完成，请保留现场并重新查询。';
}
