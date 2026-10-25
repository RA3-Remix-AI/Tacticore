import test from 'node:test';
import assert from 'node:assert/strict';
import { createDemoRuntime, createDisconnectedRuntime } from './provider';
import type { DesktopRuntime } from './types';

let serial = 0;
function request(runtime: DesktopRuntime, id = `request-${++serial}`) {
  const profile = runtime.getSnapshot().profile;
  return { requestId: id, profileId: profile.id, profileRevision: profile.revision };
}
async function ready(runtime: DesktopRuntime) {
  assert.equal((await runtime.check(request(runtime))).ok, true);
  const snapshot = runtime.getSnapshot();
  return { ...request(runtime), sessionId: snapshot.session!.id, readyToken: snapshot.readiness!.token };
}

test('no-game, stale and failed checks fail closed and offer a next action', async () => {
  const runtime = createDemoRuntime({ checkDelayMs: 0 });
  try {
    for (const [scenario, code] of [['no-game', 'game_not_found'], ['stale', 'stale_session'], ['failure', 'check_failed']] as const) {
      runtime.setScenario(scenario);
      assert.equal((await runtime.check(request(runtime))).code, code);
      assert.equal(runtime.getSnapshot().state, 'fault');
      assert.equal(runtime.getSnapshot().readiness, null);
      assert.ok(runtime.getSnapshot().reason!.action);
    }
  } finally { runtime.dispose(); }
});

test('expired, foreign-session and changed-profile readiness cannot start', async () => {
  let clock = 100;
  const runtime = createDemoRuntime({ checkDelayMs: 0, now: () => clock });
  try {
    const start = await ready(runtime);
    assert.equal((await runtime.start({ ...start, requestId: 'wrong-session', sessionId: 'other' })).code, 'binding_changed');
    clock += 20_001;
    assert.equal((await runtime.start(start)).code, 'readiness_expired');
    const second = await ready(runtime);
    runtime.selectProfile({ ...runtime.getSnapshot().profile, revision: 2 });
    assert.equal((await runtime.start(second)).code, 'configuration_changed');
    assert.equal(runtime.getSnapshot().state, 'idle');
  } finally { runtime.dispose(); }
});

test('cancelled checks and delayed responses after edits never grant readiness', async () => {
  const runtime = createDemoRuntime({ checkDelayMs: 15 });
  try {
    const controller = new AbortController();
    const cancelled = runtime.check(request(runtime), controller.signal);
    await Promise.resolve(); controller.abort();
    assert.equal((await cancelled).code, 'cancelled');
    assert.equal(runtime.getSnapshot().state, 'idle');
    const stale = runtime.check(request(runtime));
    await Promise.resolve();
    runtime.selectProfile({ id: 'sentinel', name: '堡垒', revision: 1 });
    assert.equal((await stale).code, 'superseded');
    assert.equal(runtime.getSnapshot().profile.id, 'sentinel');
    assert.equal(runtime.getSnapshot().readiness, null);
  } finally { runtime.dispose(); }
});

test('duplicate starts are idempotent; reused request identity cannot change operation', async () => {
  const runtime = createDemoRuntime({ checkDelayMs: 0 });
  try {
    const start = await ready(runtime);
    const [a, b] = await Promise.all([runtime.start(start), runtime.start(start)]);
    assert.deepEqual(a, b);
    assert.equal(a.code, 'started');
    assert.equal(runtime.getSnapshot().logs.filter(item => item.message.startsWith('离线指挥演示开始')).length, 1);
    assert.equal((await runtime.stop(start)).code, 'request_conflict');
    assert.equal((await runtime.start({ ...start, requestId: 'new-start' })).code, 'not_ready');
    assert.equal(runtime.selectProfile({ id: 'other', name: '另一个', revision: 1 }).code, 'session_active');
  } finally { runtime.dispose(); }
});

test('detach only ends observation; stop waits for acknowledgement and deduplicates', async () => {
  const runtime = createDemoRuntime({ checkDelayMs: 0, stopDelayMs: 15 });
  try {
    await runtime.start(await ready(runtime));
    runtime.detach();
    assert.equal(runtime.getSnapshot().observing, false);
    assert.equal(runtime.getSnapshot().state, 'running');
    runtime.attach();
    const stop = { ...request(runtime), sessionId: runtime.getSnapshot().session!.id };
    assert.equal((await runtime.stop({ ...stop, requestId: 'wrong-stop', sessionId: 'foreign' })).code, 'binding_changed');
    const stopping = runtime.stop(stop);
    await Promise.resolve();
    assert.equal(runtime.getSnapshot().state, 'stopping');
    assert.equal((await runtime.stop({ ...stop, requestId: 'second-stop' })).code, 'stop_pending');
    assert.deepEqual(await stopping, await runtime.stop(stop));
    assert.equal(runtime.getSnapshot().state, 'stopped');
    assert.equal((await runtime.stop({ ...stop, requestId: 'third-stop' })).code, 'already_stopped');
  } finally { runtime.dispose(); }
});

test('native provider cannot check, launch or execute and never claims a live adapter', async () => {
  const runtime = createDisconnectedRuntime();
  try {
    assert.equal(runtime.getSnapshot().adapterConnected, false);
    assert.equal((await runtime.check(request(runtime))).code, 'adapter_unavailable');
    assert.equal((await runtime.start({ ...request(runtime), sessionId: 'invented', readyToken: 'invented' })).code, 'adapter_unavailable');
    assert.ok(runtime.getSnapshot().capabilities.every(item => item.status !== 'demo'));
    assert.equal(runtime.getSnapshot().state, 'fault');
  } finally { runtime.dispose(); }
});

test('dispose cancels pending work and never emits another update', async () => {
  const runtime = createDemoRuntime({ checkDelayMs: 15 });
  let updates = 0;
  runtime.subscribe(() => updates++);
  const checking = runtime.check(request(runtime));
  await Promise.resolve(); runtime.dispose();
  const count = updates;
  assert.equal((await checking).code, 'superseded');
  assert.equal(updates, count);
  assert.equal((await runtime.check(request(runtime))).code, 'disposed');
});

test('disposing from a running subscriber never creates an orphan interval', async (context) => {
  const runtime = createDemoRuntime({ checkDelayMs: 0 });
  const start = await ready(runtime);
  const interval = context.mock.method(globalThis, 'setInterval');
  runtime.subscribe(() => { if (runtime.getSnapshot().state === 'running') runtime.dispose(); });
  try {
    assert.equal((await runtime.start(start)).code, 'superseded');
    assert.equal(interval.mock.callCount(), 0);
    assert.equal(runtime.getSnapshot().logs.some(item => item.message.startsWith('离线指挥演示开始')), false);
  } finally { runtime.dispose(); }
});

test('profile changes from a ready subscriber invalidate the completed check', async () => {
  const runtime = createDemoRuntime({ checkDelayMs: 0 });
  runtime.subscribe(() => {
    if (runtime.getSnapshot().state === 'ready') runtime.selectProfile({ id: 'new', name: '新指挥官', revision: 1 });
  });
  try {
    assert.equal((await runtime.check(request(runtime))).code, 'superseded');
    assert.equal(runtime.getSnapshot().state, 'idle');
    assert.equal(runtime.getSnapshot().readiness, null);
    assert.equal(runtime.getSnapshot().logs.some(item => item.message.startsWith('演示检查通过')), false);
  } finally { runtime.dispose(); }
});
