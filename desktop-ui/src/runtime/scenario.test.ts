import {test} from 'node:test';
import assert from 'node:assert/strict';
import {factionLabel, parseScenario, scenarioView} from './scenario';

const withAi = {
  map_id: 'map_mp_4_feasel', display_map: '任意地图', mode: 'human_with_ai', model_player_id: 3,
  players: [
    {player_id: 4, kind: 'native_ai', team: 2, difficulty: 'brutal', faction: 'Allies'},
    {player_id: 1, kind: 'human', team: 1, difficulty: null, faction: 'Empire'},
    {player_id: 3, kind: 'model_ai', team: 1, difficulty: 'medium', faction: 'Soviet'},
    {player_id: 5, kind: 'native_ai', team: null, difficulty: 'easy', faction: null},
  ],
};

test('scenario parses and groups players by team with the model seat highlighted', () => {
  const scenario = parseScenario(withAi);
  assert.ok(scenario);
  const view = scenarioView(scenario);
  assert.equal(view.known, true);
  assert.equal(view.map, '任意地图');
  assert.equal(view.modeLabel, '并肩作战：你和弈核 AI 一队');
  assert.deepEqual(view.teams.map(team => team.label), ['队伍 1', '队伍 2', '无队伍']);
  const [team1, team2, solo] = view.teams;
  assert.deepEqual(team1.players.map(row => [row.seat, row.role, row.isModel]), [['玩家 1', '玩家', false], ['玩家 3', '弈核 AI', true]]);
  assert.equal(team1.players[0].detail, '升阳帝国');
  assert.equal(team1.players[1].detail, '苏联', 'difficulty is only shown for native computers');
  assert.equal(team2.players[0].detail, '盟军', 'an unverified lobby difficulty is never shown as fact');
  assert.equal(solo.players[0].detail, '');
  assert.equal(view.summary, '1 名玩家，1 个弈核 AI，2 个电脑');
  assert.deepEqual(view.notes, []);
  const verified = scenarioView(parseScenario({...withAi, difficulty_verified: true}));
  assert.equal(verified.teams[1].players[0].detail, '盟军 · 凶残');
  assert.equal(verified.teams[2].players[0].detail, '简单');
});

test('backend extras: observers and a start away from position 2 become plain notes', () => {
  const view = scenarioView(parseScenario({...withAi, teams: {'1': [1, 3]}, own_region: 'region_1_1', enemy_regions: [],
    enemy_regions_exact: false, own_start_waypoint: 'Player_3_Start', observer_player_ids: [2, 'x'], difficulty_verified: false}));
  assert.deepEqual(view.notes, ['观察者：玩家 2', '弈核电脑不在 2 号出生点：这局「集结部队」「撤退回防」不可用。']);
  const home = scenarioView(parseScenario({...withAi, own_start_waypoint: 'Player_2_Start'}));
  assert.deepEqual(home.notes, []);
});

test('malformed scenario fields degrade instead of failing', () => {
  const scenario = parseScenario({mode: 'free_for_all', display_map: '  ', map_id: 'x', model_player_id: '3',
    players: [{player_id: 'a', kind: 'human'}, {player_id: 2, kind: 'alien'}, {player_id: 6, kind: 'human', team: 1.5, difficulty: 'insane'}, null]});
  assert.ok(scenario);
  assert.equal(scenario.mode, 'other');
  assert.equal(scenario.display_map, null);
  assert.equal(scenario.model_player_id, null);
  assert.deepEqual(scenario.players, [{player_id: 6, kind: 'human', team: null, difficulty: null, faction: null}]);
  assert.equal(scenarioView(scenario).map, 'x');
  assert.equal(scenarioView(scenario).modeLabel, '其他组合');
});

test('absent scenario (older backend) falls back to legacy candidate fields', () => {
  assert.equal(parseScenario(undefined), null);
  assert.equal(parseScenario([1, 2]), null);
  const view = scenarioView(null, {map: '旧版地图名', faction: 'Soviet', player_id: 3});
  assert.equal(view.known, false);
  assert.equal(view.map, '旧版地图名');
  assert.deepEqual(view.teams, []);
  assert.equal(view.summary, '弈核 AI 控制玩家 3（苏联）');
  assert.equal(scenarioView(null).map, '未知地图');
  assert.equal(scenarioView(null).summary, '当前版本没有提供完整的席位信息');
});

test('faction labels cover RA3 sides and keep unknown names', () => {
  assert.equal(factionLabel('Soviet'), '苏联');
  assert.equal(factionLabel('allied'), '盟军');
  assert.equal(factionLabel('Rising Sun'), '升阳帝国');
  assert.equal(factionLabel('Celestial'), 'Celestial');
  assert.equal(factionLabel(null), null);
});
