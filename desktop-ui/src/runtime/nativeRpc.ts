import { invoke, isTauri } from '@tauri-apps/api/core';

export const nativeAvailable = () => isTauri();
export type HostOperation = 'profiles.list' | 'profiles.get' | 'profiles.save' | 'connections.list'
  | 'session.inspect' | 'run.check' | 'run.start' | 'run.status' | 'run.stop' | 'diagnostics.export';
export class HostError extends Error {
  constructor(public readonly code: string, public readonly requestId: string) { super(code); }
}
export type InvokeHost = (command: string, args: {request: object}) => Promise<unknown>;
const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const codePattern = /^[a-z][a-z0-9_]{0,100}$/;

/** One invocation per request. Uncertain transport results are never retried. */
export function createHostRpc(call: InvokeHost = invoke) {
  return async function request<T extends object>(operation: HostOperation, args: object,
    requestId = crypto.randomUUID()): Promise<T> {
    if (!uuid.test(requestId)) throw new HostError('invalid_request_id', requestId);
    let response: unknown;
    try {
      response = await call('host_request', {request: {schema_version: 1, request_id: requestId, operation, args}});
    } catch (error) {
      // Rust emits fixed codes; arbitrary platform exception messages never enter UI/logs.
      const code = typeof error === 'string' && codePattern.test(error) ? error : 'delivery_unknown';
      throw new HostError(code, requestId);
    }
    if (!object(response) || response.schema_version !== 1 || response.request_id !== requestId || typeof response.ok !== 'boolean')
      throw new HostError('delivery_unknown', requestId);
    if (!response.ok) {
      const code = object(response.error) && typeof response.error.code === 'string' && codePattern.test(response.error.code)
        ? response.error.code : 'bridge_operation_failed';
      throw new HostError(code, requestId);
    }
    if (!object(response.result)) throw new HostError('delivery_unknown', requestId);
    return response.result as T;
  };
}

export const hostRpc = createHostRpc();
