/** Composed RPC/view helpers with fake replies. This is not an actual UI/field acceptance. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {createHostRpc, HostError} from './nativeRpc';
import {strategicCommandView, type StrategicClientRecord} from './strategicCommandView';
import {strategicLifecycleView} from './strategicLifecycleView';
import {sessionDisplay} from './sessionDisplay';
import {sameRun, preservePendingStart} from './nativeProcess';
import {createDiagnosticsDownload} from './diagnosticsDownload';
type Case = {name: string; preflight_capabilities: {commander_boundary: string; available_macro_actions: string[]}; public_record: StrategicClientRecord};
const cases = JSON.parse(readFileSync(new URL('../../tests/fixtures/strategic-client-v1.json', import.meta.url), 'utf8')) as Case[];
const pick = (name: string) => cases.find(row => row.name === name)!;
const runId = 'd341591e-2ad2-4562-95ca-da20b79fb5b1', sessionId = '11111111-1111-4111-8111-111111111111';
const requestId = '22222222-2222-4222-8222-222222222222';

test('actual Python public fixtures are accepted by the strict frontend or visibly held unverified', () => {
  for (const row of cases) {
    const view = strategicCommandView(row.public_record);
    assert.equal(view.available, row.public_record.boundary === 'strategic_only', row.name);
    assert.equal(view.uncertain, row.public_record.boundary !== 'strategic_only' || row.public_record.current_intent_state === 'invalid', row.name);
    assert.doesNotMatch(JSON.stringify(view), /producebullfrog|buildpower|bullfrog|新增.*队列/);
  }
});
test('configured-user check/start/observe/stop/next-session helper path sends one launch and waits for independent release', async () => {
  const calls: string[] = []; let query = 0;
  const bound = {run_id: runId, session_id: sessionId};
  const rpc = createHostRpc(async (_command, envelope) => {
    const request = envelope.request as {schema_version: number; request_id: string; operation: string; args: Record<string, unknown>};
    calls.push(request.operation); let result: object;
    if (request.operation === 'run.check') result = {ready: true, session_id: sessionId, ready_token: 'opaque', capabilities: pick('running_pending').preflight_capabilities};
    else if (request.operation === 'run.start') result = {...bound, state: 'starting'};
    else if (request.operation === 'run.stop') result = {...bound, state: 'stopping', native_release_verified: false};
    else if (request.operation === 'run.status') result = ++query === 1
      ? {...bound, state: 'running', native_release_verified: false, strategic_client: pick('running_pending').public_record}
      : {...bound, state: 'stopped', native_release_verified: query === 3, host_process_alive: false, status_stale: true};
    else result = {registered: true, requires_preflight: true, session: {id: 'new-session'}};
    return {schema_version: 1, request_id: request.request_id, ok: true, result};
  });
  const checked = await rpc<{ready: boolean; session_id: string; ready_token: string}>('run.check', {});
  assert.equal(checked.ready, true);
  const starting = await rpc<typeof bound & {state: string}>('run.start', {session_id: checked.session_id, ready_token: checked.ready_token}, runId);
  assert.equal(sameRun(bound, starting), true);
  const observed = await rpc<typeof bound & {state: string; strategic_client: StrategicClientRecord}>('run.status', {run_id: runId});
  assert.equal(strategicCommandView(observed.strategic_client).current, '撤退意图');
  const stopping = await rpc<typeof bound & {state: string}>('run.stop', bound);
  assert.equal(strategicLifecycleView(stopping).locked, true);
  const terminal = await rpc<typeof bound & {state: string; native_release_verified: boolean}>('run.status', {run_id: runId});
  assert.equal(strategicLifecycleView(terminal).locked, true);
  const released = await rpc<typeof terminal>('run.status', {run_id: runId});
  assert.equal(strategicLifecycleView(released).locked, false);
  const next = await rpc<{session: {id: string}}>('session.prepare', {candidate_id: 'opaque-new-candidate'});
  const display = sessionDisplay(released, next.session, null);
  assert.equal(display.current, undefined); assert.equal(display.historical?.run_id, runId);
  assert.equal(calls.filter(op => op === 'run.start').length, 1);
  assert.equal(calls.filter(op => op === 'run.stop').length, 1);
});
test('unknown launch delivery preserves the original operation and cannot cause an automatic retry', async () => {
  let calls = 0;
  const rpc = createHostRpc(async () => {calls++; throw new Error('PRIVATE_PLATFORM_ERROR');});
  await assert.rejects(rpc('run.start', {session_id: sessionId}, requestId), error => {
    assert.ok(error instanceof HostError); assert.equal(error.code, 'delivery_unknown');
    assert.equal(error.requestId, requestId); assert.equal(preservePendingStart(error.code), true); return true;
  });
  assert.equal(calls, 1); assert.equal(strategicLifecycleView({state: 'uncertain'}).locked, true);
});
test('a late old status cannot become the new-session strategic record', () => {
  const old = {run_id: runId, session_id: sessionId, state: 'stopped', native_release_verified: true,
    strategic_client: pick('running_pending').public_record};
  assert.equal(sameRun({run_id: 'new-run', session_id: 'new-session'}, old), false);
  const view = sessionDisplay(old, {id: 'new-session'}, null);
  assert.equal(view.current, undefined); assert.equal(view.historical?.strategic_client, old.strategic_client);
});
test('diagnostic read failure reports failure without saving bytes or creating any new host operation', async () => {
  let exported = 0, read = 0, saved = 0;
  const content = JSON.stringify({schema_version: 1, kind: 'tacticore_redacted_diagnostics', redacted: true,
    export_id: requestId, run_id: runId, binding: {session_id: sessionId}, effective_profile_available: false, effective_profile: null});
  const receipt = {export_id: requestId, run_id: runId, sha256: createHash('sha256').update(content).digest('hex'),
    bytes: Buffer.byteLength(content), event_count: 0, exported_event_count: 0, truncated: false, redacted: true};
  const download = createDiagnosticsDownload(async () => {exported++; return receipt;},
    async () => {read++; throw new Error('PRIVATE_READ_ERROR');}, () => {saved++;});
  await assert.rejects(download({run_id: runId, session_id: sessionId}), /diagnostics_read_failed/);
  assert.equal(exported, 1); assert.equal(read, 1); assert.equal(saved, 0);
});
