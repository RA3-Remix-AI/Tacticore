import {test} from 'node:test';
import assert from 'node:assert/strict';
import {lobbyInstructions, loadSetupPreferences, modeMismatch, modeNote, playModes, saveSetupPreferences, setupPreferencesKey} from './playMode';
import {canFinishWizard, firstIncompleteStep, nextStep, previousStep, showWizard, wizardSteps, type WizardInput} from './wizard';

const pinned = /TemplePrime|Infinity\s*Isle|InfinityIsle|P3|P4|出生位置|10000|宝箱/i;

test('lobby instructions exist for each mode and never pin a map, seat or start position', () => {
  for (const mode of playModes) {
    const lines = lobbyInstructions(mode.id);
    assert.ok(lines.length >= 4, mode.id);
    for (const line of lines) assert.doesNotMatch(line, pinned, line);
    assert.ok(lines.some(line => line.includes('任意一张 1.12 地图')));
    assert.ok(lines.at(-1)!.includes('查找对局'));
  }
  assert.ok(lobbyInstructions('ai_vs_native').some(line => line.includes('观察者')));
  assert.ok(lobbyInstructions('human_with_ai').some(line => line.includes('相同的队伍')));
  assert.ok(lobbyInstructions('human_vs_ai').some(line => line.includes('不同的队伍')));
  assert.ok(!lobbyInstructions('human_with_ai').some(line => line.includes('观察者')), 'playing modes never ask for observer');
  for (const mode of playModes) {
    // Real runtime limits: model seat is lobby slot 2 and Soviet; start 2 is a recommendation.
    assert.ok(lobbyInstructions(mode.id).some(line => line.includes('第 2 个位置') && line.includes('苏联')), mode.id);
    assert.ok(lobbyInstructions(mode.id).some(line => line.startsWith('建议') && line.includes('2 号出生点')), mode.id);
  }
  assert.equal(modeNote('ai_vs_native'), null);
  assert.match(modeNote('human_vs_ai')!, /部分指令/);
});

test('mode mismatch is a gentle notice only when the lobby differs', () => {
  assert.equal(modeMismatch('human_with_ai', 'human_with_ai'), null);
  assert.equal(modeMismatch(null, 'human_vs_ai'), null);
  assert.equal(modeMismatch('ai_vs_native', undefined), null);
  assert.match(modeMismatch('ai_vs_native', 'human_vs_ai')!, /对战：你对抗弈核 AI/);
  assert.match(modeMismatch('ai_vs_native', 'other')!, /可能暂不支持/);
});

test('setup preferences store only completion and mode, and survive junk', () => {
  const store = new Map<string, string>();
  const storage = {getItem: (key: string) => store.get(key) ?? null, setItem: (key: string, value: string) => { store.set(key, value); }};
  assert.deepEqual(loadSetupPreferences(storage), {completed: false, mode: null});
  saveSetupPreferences(storage, {completed: true, mode: 'human_vs_ai', apiKey: 'secret'} as never);
  assert.deepEqual(JSON.parse(store.get(setupPreferencesKey)!), {completed: true, mode: 'human_vs_ai'});
  assert.deepEqual(loadSetupPreferences(storage), {completed: true, mode: 'human_vs_ai'});
  store.set(setupPreferencesKey, '{"completed":"yes","mode":"chaos"}');
  assert.deepEqual(loadSetupPreferences(storage), {completed: false, mode: null});
  store.set(setupPreferencesKey, '{not json');
  assert.deepEqual(loadSetupPreferences(storage), {completed: false, mode: null});
  assert.deepEqual(loadSetupPreferences(null), {completed: false, mode: null});
  assert.doesNotThrow(() => saveSetupPreferences({setItem: () => { throw new Error('quota'); }}, {completed: true, mode: null}));
});

const empty: WizardInput = {gamePrepared: false, configurationReady: false, credentialSaved: null, mode: null};

test('wizard steps complete in order and finishing needs all three', () => {
  assert.deepEqual(wizardSteps(empty).map(step => step.done), [false, false, false]);
  assert.equal(firstIncompleteStep(empty), 'game');
  const gameDone = {...empty, gamePrepared: true};
  assert.equal(firstIncompleteStep(gameDone), 'model');
  const modelDone = {...gameDone, configurationReady: true, credentialSaved: false};
  assert.equal(firstIncompleteStep(modelDone), 'mode');
  assert.equal(wizardSteps(modelDone)[1].hint, '已保存；尚未填写 API Key');
  assert.equal(canFinishWizard(modelDone), false);
  const all = {...modelDone, mode: 'ai_vs_native' as const};
  assert.equal(firstIncompleteStep(all), null);
  assert.equal(canFinishWizard(all), true);
  assert.equal(nextStep('game'), 'model');
  assert.equal(nextStep('mode'), null);
  assert.equal(previousStep('model'), 'game');
  assert.equal(previousStep('game'), null);
});

test('a run that holds the game always bypasses the wizard so Stop stays reachable', () => {
  assert.equal(showWizard({completed: false, runHoldsGame: false}), true);
  assert.equal(showWizard({completed: false, runHoldsGame: true}), false);
  assert.equal(showWizard({completed: true, runHoldsGame: false}), false);
});
