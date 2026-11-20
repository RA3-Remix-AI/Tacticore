import {test} from 'node:test';
import assert from 'node:assert/strict';
import {matchControl, type ControlInput} from './matchControl';
import {runLocksControls} from './nativeProcess';
import {APP_VERSION, errorText, reasonText} from './copy';
import {HostError} from './nativeRpc';
import {readFileSync} from 'node:fs';

const idle: ControlInput = {
  gamePrepared: true, configuration: 'ready', profileIssue: null, waiting: false, busy: false, run: null,
  runHoldsGame: false, candidateCount: 0, candidateSelected: false, sessionPrepared: false, readyValid: false,
};
const withRun = (state: string, released?: boolean): ControlInput => {
  const run = {state, native_release_verified: released};
  return {...idle, run, runHoldsGame: runLocksControls(state, released)};
};

test('setup gates come first and point to the right settings page', () => {
  assert.equal(matchControl({...idle, gamePrepared: false}).primary.action, 'open_setup');
  assert.equal(matchControl({...idle, gamePrepared: null}).primary.action, 'discover', 'debug builds are not blocked');
  assert.equal(matchControl({...idle, configuration: 'unverified'}).primary.action, 'open_model');
  assert.equal(matchControl({...idle, configuration: 'pending'}).detail, '上次保存还没有完成，请在模型设置中处理。');
  const checking = matchControl({...idle, configuration: 'checking'});
  assert.equal(checking.primary.disabled, true);
  assert.equal(matchControl({...idle, profileIssue: 'dirty'}).primary.action, 'open_style');
  assert.equal(matchControl({...idle, profileIssue: 'invalid'}).primary.action, 'open_model');
});

test('idle -> found -> start uses one primary button', () => {
  const ready = matchControl(idle);
  assert.equal(ready.phase, 'idle');
  assert.deepEqual([ready.primary.label, ready.primary.action], ['查找对局', 'discover']);
  const found = matchControl({...idle, candidateCount: 1, candidateSelected: true});
  assert.deepEqual([found.phase, found.primary.label, found.primary.action, found.primary.disabled], ['found', '开始', 'start', false]);
  const many = matchControl({...idle, candidateCount: 2, candidateSelected: false});
  assert.equal(many.primary.disabled, true);
  assert.equal(many.title, '找到多个对局');
  assert.equal(matchControl({...idle, sessionPrepared: true}).primary.action, 'start');
  assert.equal(matchControl({...idle, readyValid: true}).phase, 'ready');
  assert.equal(matchControl({...idle, readyValid: true, busy: true}).primary.disabled, true);
});

test('a run that holds the game always offers stop or a safe wait, never a new start', () => {
  for (const state of ['running', 'starting', 'uncertain', 'sampling_wait']) {
    const view = matchControl(withRun(state));
    assert.deepEqual([view.primary.action, view.primary.tone, view.live], ['stop', 'danger', true], state);
  }
  const stopping = matchControl(withRun('stopping'));
  assert.deepEqual([stopping.phase, stopping.primary.action, stopping.primary.disabled], ['stopping', 'none', true]);
  for (const state of ['stopped', 'completed', 'fault', 'result_candidate']) {
    const view = matchControl(withRun(state, false));
    assert.equal(view.phase, 'returning', `${state} without release proof keeps the game locked`);
    assert.equal(view.primary.action, 'refresh');
  }
  // Candidates or readiness cannot override a run that still holds the game.
  assert.equal(matchControl({...withRun('stopped', false), candidateCount: 1, candidateSelected: true, readyValid: true}).phase, 'returning');
});

test('after independent release the client explains how to play again', () => {
  const view = matchControl(withRun('stopped', true));
  assert.equal(view.phase, 'finished');
  assert.equal(view.primary.action, 'discover');
  assert.match(view.detail, /完全退出游戏并重新打开/);
  const waiting = matchControl({...idle, waiting: true});
  assert.deepEqual([waiting.primary.action, waiting.primary.disabled], ['cancel_wait', false]);
});

test('control copy is free of internal jargon', () => {
  const jargon = /归还|准入|epoch|资格|受信|宿主|原生/;
  const inputs: ControlInput[] = [idle, {...idle, gamePrepared: false}, {...idle, configuration: 'unknown'}, {...idle, candidateCount: 1},
    withRun('running'), withRun('stopping'), withRun('stopped', false), withRun('stopped', true), withRun('uncertain'), {...idle, waiting: true}];
  for (const input of inputs) {
    const view = matchControl(input);
    for (const text of [view.title, view.detail, view.status, view.primary.label]) assert.doesNotMatch(text, jargon, text);
  }
});

test('reason codes read as plain Chinese and unknown codes keep the code', () => {
  assert.match(reasonText('session_scope_unsupported'), /对局模式/);
  assert.doesNotMatch(reasonText('session_scope_unsupported'), /P3|出生位置|Infinity/);
  assert.equal(reasonText('brand_new_code'), '操作没有完成（代码：brand_new_code）。');
  assert.equal(errorText(new HostError('delivery_unknown', 'x')), reasonText('delivery_unknown'));
  assert.match(errorText(new Error('raw platform text')), /客户端服务/);
});

test('displayed version matches the package version', () => {
  const pkg = JSON.parse(readFileSync(new URL('../../package.json', import.meta.url), 'utf8'));
  assert.equal(APP_VERSION, pkg.version);
  assert.equal(APP_VERSION, '0.1.0-beta.4');
});
