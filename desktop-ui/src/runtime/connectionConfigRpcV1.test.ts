import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createConnectionConfigRpc, connectionConfigError, connectionConfiguration} from './connectionConfigRpcV1';
import {HostError} from './nativeRpc';
const id = '11111111-1111-4111-8111-111111111111';
const key = 'FAKE-ONLY-FRONTEND-KEY';
test('separate trusted channel sends one bounded request, never a path or command line', async () => {
  let count = 0;
  const rpc = createConnectionConfigRpc(async (command, {request}) => {
    count++; assert.equal(command, 'connection_config_request');
    const value = request as {request_id: string; args: {api_key?: string}};
    assert.equal(value.args.api_key, key);
    return {schema_version: 1, request_id: value.request_id, ok: true, result: {saved: true}};
  });
  assert.deepEqual(await rpc('connections.configure', {api_key: key}, id), {saved: true});
  assert.equal(count, 1);
});
test('unknown save delivery is not repeated and no native exception or key is echoed', async () => {
  let count = 0;
  const rpc = createConnectionConfigRpc(async () => {count++; throw new Error(key);});
  await assert.rejects(rpc('connections.configure', {api_key: key}, id), error => {
    assert.ok(error instanceof HostError); assert.equal(error.code, 'delivery_unknown');
    assert.doesNotMatch(connectionConfigError(error), /FAKE/); return true;
  });
  assert.equal(count, 1);
});
test('sensitive fields in a mistaken response are rejected instead of reaching the panel', async () => {
  const rpc = createConnectionConfigRpc(async () => ({schema_version: 1, request_id: id, ok: true, result: {api_key: key}}));
  await assert.rejects(rpc('connections.configuration', {}, id), /connection_config_response_invalid/);
});
test('oversized input is rejected before invoking native service', async () => {
  let count = 0;
  const rpc = createConnectionConfigRpc(async () => {count++; return {};});
  await assert.rejects(rpc('connections.configure', {api_key: 'a'.repeat(16384)}, id), /request_too_large/);
  assert.equal(count, 0);
});
test('pending recovery has no selectable connection and cannot masquerade as ready', () => {
  const value = {schema_version: 1, ready: false, config_fingerprint: null, connections: [],
    recovery: [{configuration_request_id: id, expected_config_fingerprint: 'a'.repeat(64)}], retired_credentials: [],
    remote_connection_tested: false, host_recheck_required: true};
  assert.equal(connectionConfiguration(value).ready, false);
  assert.throws(() => connectionConfiguration({...value, ready: true}), /response_invalid/);
});
test('unknown errors remain generic and reentry rules are explained without secret references', () => {
  assert.doesNotMatch(connectionConfigError(new HostError(key, id)), /FAKE/);
  assert.match(connectionConfigError(new HostError('connection_credential_reentry_required', id)), /重新输入/);
});
