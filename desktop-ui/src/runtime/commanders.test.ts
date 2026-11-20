import {test} from 'node:test';
import assert from 'node:assert/strict';
import {
  VOICE_NOTE_MAX_BYTES, builtInCommanders, chooseCommander, commanderBadge, commanderProblem, commanderProfile,
  commanderSupported, editPersonality, mergeCommanders, personalityParams, presetFor, profileSaveDraft, voiceNoteBytes,
} from './commanders';

test('three commanders with exact preset values from the characters doc; only Hammer is available', () => {
  assert.deepEqual(builtInCommanders.map(row => [row.id, row.name, row.full_name, row.faction, row.available]), [
    ['hammer', '铁锤', '维克托·莫罗佐夫', '苏联', true],
    ['bastion', '堡垒', '伊芙琳·卡特', '盟军', false],
    ['ghost', '幽灵', '神崎凛', '升阳', false],
  ]);
  const order = personalityParams.map(param => param.key);
  assert.deepEqual(order, ['aggression', 'risk', 'persistence', 'punish', 'preserve', 'deception', 'grudge', 'adaptability',
    'bait_awareness']);
  const levels = (id: string) => order.map(key => builtInCommanders.find(row => row.id === id)!.personality[key]);
  assert.deepEqual(levels('hammer'), [4, 3, 3, 5, 3, 2, 3, 4, 5]);
  assert.deepEqual(levels('bastion'), [2, 2, 2, 4, 5, 3, 2, 5, 4]);
  assert.deepEqual(levels('ghost'), [3, 4, 5, 4, 4, 5, 3, 5, 3]);
  for (const param of personalityParams) assert.ok(param.hint.length > 8 && /[一-鿿]/.test(param.label), param.key);
  for (const row of builtInCommanders) {
    assert.match(row.portrait, new RegExp(`^/commanders/${row.id}-portrait\\.webp$`));
    assert.equal(row.video, undefined, 'video is reserved, not used yet');
  }
});

test('backend commander list overrides names and availability; junk falls back to built-in metadata', () => {
  const merged = mergeCommanders([{id: 'bastion', name: '堡垒', full_name: '伊芙琳·卡特', faction: '盟军', available: true},
    {id: 'ghost', available: 'yes', name: ''}, 'junk', {id: 'zzz', available: true}]);
  assert.equal(merged.length, 3);
  assert.equal(merged.find(row => row.id === 'bastion')?.available, true);
  assert.equal(merged.find(row => row.id === 'ghost')?.available, false);
  assert.equal(merged.find(row => row.id === 'ghost')?.name, '幽灵');
  assert.deepEqual(mergeCommanders(undefined).map(row => row.available), [true, false, false]);
});

test('presets set exact values; editing any value switches to custom', () => {
  const hammer = chooseCommander('hammer', builtInCommanders)!;
  assert.equal(hammer.commander_id, 'hammer');
  assert.deepEqual(hammer.personality, builtInCommanders[0].personality);
  assert.equal(presetFor(hammer.personality), 'hammer');
  const edited = editPersonality(hammer, 'risk', 5);
  assert.equal(edited.commander_id, 'custom');
  assert.equal(edited.personality.risk, 5);
  assert.equal(hammer.personality.risk, 3, 'the preset is not mutated');
  assert.equal(presetFor(edited.personality), 'custom');
  assert.equal(editPersonality(hammer, 'risk', 3).commander_id, 'hammer', 'the same value is not an edit');
  assert.equal(editPersonality(hammer, 'risk', 9).personality.risk, 3, 'out-of-range values are ignored');
  const back = chooseCommander('hammer', builtInCommanders)!;
  assert.equal(back.commander_id, 'hammer', 'choosing the preset again restores it');
});

test('unavailable commanders cannot be chosen or saved', () => {
  assert.equal(chooseCommander('bastion', builtInCommanders), null);
  assert.equal(chooseCommander('ghost', builtInCommanders), null);
  const forged = {commander_id: 'ghost' as const, personality: builtInCommanders[2].personality, voice_note: ''};
  assert.equal(commanderProblem(forged, builtInCommanders), 'commander_unavailable');
  assert.equal(commanderProblem({...forged, commander_id: 'custom'}, builtInCommanders), null);
  const opened = mergeCommanders([{id: 'ghost', available: true}]);
  assert.ok(chooseCommander('ghost', opened));
});

test('voice note is limited to 300 UTF-8 bytes', () => {
  assert.equal(voiceNoteBytes('abc'), 3);
  assert.equal(voiceNoteBytes('铁锤'), 6);
  const profile = chooseCommander('hammer', builtInCommanders)!;
  assert.equal(commanderProblem({...profile, voice_note: '铁'.repeat(100)}, builtInCommanders), null);
  assert.equal(VOICE_NOTE_MAX_BYTES, 300);
  assert.equal(commanderProblem({...profile, voice_note: '铁'.repeat(101)}, builtInCommanders), 'voice_note_too_long');
});

test('older backends: Hammer by default, commander fields are not sent, invalid values fall back', () => {
  const legacy = {schema_version: 1, profile_id: 'p', name: 'n', revision: 1, connection_id: 'c', model: '',
    doctrine: 'assault', custom_traits: ''};
  assert.equal(commanderSupported(legacy, undefined), false);
  assert.equal(commanderSupported(legacy, []), true);
  assert.equal(commanderSupported({...legacy, commander_id: 'hammer'}, undefined), true);
  const profile = commanderProfile(legacy);
  assert.equal(profile.commander_id, 'hammer');
  assert.deepEqual(profile.personality, builtInCommanders[0].personality);
  const edited = {...legacy, commander_id: 'custom' as const, personality: profile.personality, voice_note: 'x'};
  assert.deepEqual(Object.keys(profileSaveDraft(edited, false)).sort(), Object.keys(legacy).sort());
  assert.equal(profileSaveDraft(edited, true).voice_note, 'x');
  const broken = commanderProfile({commander_id: 'custom', personality: {aggression: 9, risk: 1.5, grudge: 1}});
  assert.equal(broken.commander_id, 'custom');
  assert.equal(broken.personality.aggression, 4, 'invalid values use the Hammer preset');
  assert.equal(broken.personality.grudge, 1);
  assert.equal(commanderBadge('custom').name, '自定义指挥官');
  assert.equal(commanderBadge('hammer').portrait, '/commanders/hammer-portrait.webp');
  assert.equal(commanderBadge('unknown', undefined, '新指挥官').name, '新指挥官');
});
