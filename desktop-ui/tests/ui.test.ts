import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MatchCard, ScenarioDetails, candidateView} from '../src/ui/MatchCard.tsx';
import {DecisionFeed} from '../src/ui/DecisionFeed.tsx';
import {ReviewPage} from '../src/ui/ReviewPage.tsx';
import {ModeStep} from '../src/ui/ModeStep.tsx';
import {StylePanel} from '../src/ui/StylePanel.tsx';
import {builtInCommanders, mergeCommanders} from '../src/runtime/commanders.ts';
import {parseDecisionRecords} from '../src/runtime/decisions.ts';
import type {Draft, Profile} from '../src/runtime/hostTypes.ts';
import {decisionFixtureRecords} from '../src/runtime/decisionFixtures.ts';
import {scenarioView, parseScenario} from '../src/runtime/scenario.ts';
import {connectionTestText, parseConnectionTest, testConnection} from '../src/runtime/connectionConfigRpcV1.ts';
import {HostError} from '../src/runtime/nativeRpc.ts';
import type {DiscoveredSession} from '../src/runtime/openingStart.ts';

const runId = '44444444-4444-4444-8444-444444444444';
const base: DiscoveredSession = {candidate_id: 'c1', display_name: '旧显示名', map: '旧版地图', faction: 'Soviet', player_id: 3,
  expires_in_seconds: 30, requires_preflight: true};
const scenario = {map_id: 'm', display_map: '海岛要塞', mode: 'human_vs_ai', model_player_id: 2,
  players: [{player_id: 1, kind: 'human', team: 1, difficulty: null, faction: 'Allies'},
    {player_id: 2, kind: 'model_ai', team: 2, difficulty: null, faction: 'Empire'}]};
const noop = () => {};

test('match card renders the scenario contract with teams and the model seat', () => {
  const html = renderToStaticMarkup(createElement(MatchCard, {candidates: [{...base, scenario}], selectedId: 'c1', onSelect: noop,
    bound: null, mode: 'human_vs_ai', disabled: false}));
  assert.match(html, /海岛要塞/);
  assert.match(html, /对战：你对抗弈核 AI/);
  assert.match(html, /队伍 1/);
  assert.match(html, /class="is-model"/);
  assert.match(html, /升阳帝国/);
  assert.doesNotMatch(html, /native-warning/, 'matching mode shows no mismatch notice');
});

test('match card tolerates an older backend without scenario and warns on mode mismatch', () => {
  const legacy = renderToStaticMarkup(createElement(MatchCard, {candidates: [base], selectedId: '', onSelect: noop,
    bound: null, mode: 'ai_vs_native', disabled: false}));
  assert.match(legacy, /旧版地图/);
  assert.match(legacy, /对局详情暂不可用/);
  assert.match(legacy, /弈核 AI 控制玩家 3（苏联）/);
  const mismatch = renderToStaticMarkup(createElement(MatchCard, {candidates: [{...base, scenario}], selectedId: '', onSelect: noop,
    bound: null, mode: 'ai_vs_native', disabled: false}));
  assert.match(mismatch, /和你选择的「观战：弈核 AI 对战电脑」不同/);
  const many = renderToStaticMarkup(createElement(MatchCard, {candidates: [base, {...base, candidate_id: 'c2', scenario}],
    selectedId: 'c2', onSelect: noop, bound: null, mode: null, disabled: false}));
  assert.match(many, /找到 2 个对局/);
  assert.equal((many.match(/role="radio"/g) ?? []).length, 2);
  assert.match(many, /aria-checked="true"/);
  const empty = renderToStaticMarkup(createElement(MatchCard, {candidates: [], selectedId: '', onSelect: noop, bound: null, mode: null, disabled: false}));
  assert.match(empty, /还没有找到对局/);
  assert.equal(candidateView({...base, scenario: 'junk'}).known, false);
});

test('decision feed shows the strategy, translated intents, badges and the mock marker', () => {
  const records = decisionFixtureRecords(runId);
  const html = renderToStaticMarkup(createElement(DecisionFeed, {records, state: 'ok', live: true, mock: true}));
  assert.match(html, /集中突破北侧，目标敌方建造厂/);
  assert.match(html, /集中对付玩家 4/);
  assert.match(html, /未采纳/);
  assert.match(html, /结果未知/);
  assert.match(html, /示例数据/);
  assert.ok(html.indexOf('06:10') < html.indexOf('00:05'), 'live feed lists newest first');
  const unavailable = renderToStaticMarkup(createElement(DecisionFeed, {records: [], state: 'unavailable', live: true, mock: false}));
  assert.match(unavailable, /还没有提供决策记录/);
  assert.match(unavailable, /AI 还没有做出决定/);
});

test('review page shows result, counts and latency', () => {
  const html = renderToStaticMarkup(createElement(ReviewPage, {hasRun: true, live: false, records: decisionFixtureRecords(runId),
    state: 'ok', mock: false, scenario: scenarioView(parseScenario(scenario)), onRefresh: noop, busy: false}));
  assert.match(html, /胜利/);
  assert.match(html, /07:32/);
  assert.match(html, /决策次数/);
  assert.match(html, /<strong>11<\/strong><small>决策次数/);
  assert.match(html, /<strong>1<\/strong><small>未采纳/);
  assert.match(html, /<strong>2<\/strong><small>被丢弃的意图/);
  assert.match(html, /<strong>3<\/strong><small>含仅记录项的决策/);
  assert.match(html, /平均响应/);
  assert.match(html, /分层决策（总指挥 \+ 参谋）/);
  assert.match(html, /bear_scout_terror_raid/);
  assert.match(html, /维克托·莫罗佐夫/);
  assert.match(html, /总指挥<\/span><strong>3<\/strong>/);
  assert.match(html, /战术参谋<\/span><strong>5<\/strong>/);
  assert.ok(html.indexOf('00:05') < html.indexOf('06:10'), 'review lists chronologically');
  const none = renderToStaticMarkup(createElement(ReviewPage, {hasRun: false, live: false, records: [], state: 'idle', mock: false,
    scenario: null, onRefresh: noop, busy: false}));
  assert.match(none, /还没有可以复盘的对局/);
});

test('mode step renders three modes and instructions for the selected one', () => {
  const html = renderToStaticMarkup(createElement(ModeStep, {mode: 'human_with_ai', onChange: noop}));
  assert.equal((html.match(/role="radio"/g) ?? []).length, 3);
  assert.match(html, /和 AI 并肩作战/);
  assert.match(html, /相同的队伍/);
  assert.doesNotMatch(html, /TemplePrime|Infinity|P3|出生位置/);
  const details = renderToStaticMarkup(createElement(ScenarioDetails, {view: scenarioView(null, {map: 'X'})}));
  assert.match(details, /X/);
});

test('connection test parses results and degrades on older backends', async () => {
  assert.deepEqual(parseConnectionTest({reachable: true, latency_ms: 812.4, reason_code: null}), {reachable: true, latency_ms: 812.4, reason_code: null});
  assert.equal(parseConnectionTest({reachable: 'yes'}), null);
  assert.deepEqual(parseConnectionTest({reachable: false, latency_ms: 'x', reason_code: 'Bad Code'}), {reachable: false, latency_ms: null, reason_code: null});
  const ok = await testConnection(async () => ({reachable: true, latency_ms: 900, reason_code: null}) as never, 'id');
  assert.equal(connectionTestText(ok).text, '连接正常，响应用时 900 ms。');
  const failed = await testConnection(async () => ({reachable: false, latency_ms: null, reason_code: 'authentication_failed'}) as never, 'id');
  assert.equal(connectionTestText(failed).ok, false);
  assert.match(connectionTestText(failed).text, /API Key 无效/);
  const old = await testConnection(async () => { throw new HostError('operation_unsupported', 'id'); }, 'id');
  assert.deepEqual(old, {state: 'unsupported'});
  assert.match(connectionTestText(old).text, /还不能在这里测试/);
  const unknown = await testConnection(async () => { throw new HostError('delivery_unknown', 'id'); }, 'id');
  assert.match(connectionTestText(unknown).text, /无法确认/);
});

test('layered feed: directive banner, layer labels, chips, commander portrait, dropped and record-only lines', () => {
  const html = renderToStaticMarkup(createElement(DecisionFeed, {records: decisionFixtureRecords(runId), state: 'ok',
    live: true, mock: true}));
  assert.match(html, /当前方针/);
  assert.match(html, /全力出击/);
  assert.match(html, /主攻 玩家 4/);
  assert.match(html, /军队 80%/);
  assert.match(html, /class="tc-override">不扩张</);
  assert.match(html, /class="tc-override">暂停科技</);
  for (const label of ['总指挥', '经济参谋', '战术参谋', '开局']) {
    assert.match(html, new RegExp(`class="tc-layer layer-[a-z]+">${label}<`), label);
    assert.match(html, new RegExp(`aria-pressed="false" class="tc-chip layer-[a-z]+">${label}`), label);
  }
  assert.match(html, /aria-pressed="true" class="tc-chip layer-all">全部/);
  assert.match(html, /hammer-portrait\.webp/);
  assert.match(html, /class="tc-dropped">未采纳：扩张经济（与总指挥方针冲突：不扩张）</);
  assert.match(html, /class="tc-dropped">未采纳：组织进攻（总指挥否决）</);
  assert.match(html, /class="tc-recorded-only">仅记录，尚未执行：产能目标、科技时机</);
  assert.match(html, /没有采纳的动作/, 'a fully vetoed record does not look executed');
  // Opening-only feed: no directive yet, so the plain strategy block is shown.
  const opening = renderToStaticMarkup(createElement(DecisionFeed, {records: decisionFixtureRecords(runId).slice(0, 2),
    state: 'ok', live: true, mock: false, commander: {name: '铁锤', portrait: '/commanders/hammer-portrait.webp'}}));
  assert.doesNotMatch(opening, /当前方针/);
  assert.match(opening, /战熊探路/);
});

test('older single-layer records show no layer chips or labels', () => {
  const records = parseDecisionRecords({records: [{schema_version: 1, seq: 1, game_time_s: 30,
    decision: {intents: ['scout'], objective: '侦察', reasoning: null, valid_for_s: 60},
    outcome: {status: 'applied', reason_code: null, native_accepted: true, observed_effects: []}}]});
  const html = renderToStaticMarkup(createElement(DecisionFeed, {records, state: 'ok', live: true, mock: false}));
  assert.doesNotMatch(html, /tc-layer-chips|tc-layer |当前方针|tc-dropped|tc-recorded-only/);
  assert.match(html, /侦察敌情/);
});

const draftBase: Draft = {schema_version: 1, profile_id: 'p1', name: '默认', revision: 3, connection_id: 'c1', model: ''};
const profileOf = (draft: Draft): Profile => ({profile_id: 'p1', name: '默认', revision: 3, model: '',
  connection_id: 'c1', draft, state: 'saved', validation: {ok: true, reason_code: ''}, effective: null});
const styleProps = (draft: Draft, supported = true) => ({
  profiles: [profileOf(draft)], selected: 'p1', profile: profileOf(draft), draft, dirty: false, disabled: false,
  commanders: mergeCommanders(undefined), supported, onChoose: noop, onEdit: noop, onSave: noop, onReload: noop,
});
const hammerPersonality = () => ({...builtInCommanders[0].personality});

test('commander page: three commanders, unavailable ones marked and disabled, Hammer preset values', () => {
  const draft: Draft = {...draftBase, commander_id: 'hammer', personality: hammerPersonality(), voice_note: ''};
  const html = renderToStaticMarkup(createElement(StylePanel, styleProps(draft)));
  for (const name of ['铁锤', '堡垒', '幽灵', '维克托·莫罗佐夫', '伊芙琳·卡特', '神崎凛']) assert.match(html, new RegExp(name));
  assert.equal((html.match(/即将推出/g) ?? []).length, 2);
  assert.match(html, /class="tc-commander-card is-soon" aria-pressed="false" disabled=""/);
  assert.match(html, /class="tc-commander-card " aria-pressed="true"/);
  assert.match(html, /铁锤预设/);
  assert.equal((html.match(/type="range"/g) ?? []).length, 9);
  assert.match(html, /name="punish" value="5"/);
  assert.match(html, /识破诱饵/);
  assert.match(html, /0 \/ 300 字节/);
  assert.match(html, /hammer\.webp/);
});

test('commander page: custom personality, over-long voice note and an older backend', () => {
  const custom: Draft = {...draftBase, commander_id: 'custom',
    personality: {...builtInCommanders[0].personality, risk: 5}, voice_note: '铁'.repeat(101)};
  const html = renderToStaticMarkup(createElement(StylePanel, {...styleProps(custom), dirty: true}));
  assert.match(html, /性格 · <span class="tc-preset-name">自定义/);
  assert.doesNotMatch(html, /aria-pressed="true"/);
  assert.match(html, /303 \/ 300 字节/);
  assert.match(html, /tc-byte-counter is-over/);
  assert.match(html, /口吻说明太长了/);
  assert.match(html, /<button[^>]*disabled=""[^>]*>保存<\/button>/, 'save is blocked while the note is too long');
  const legacyDraft: Draft = {...draftBase, doctrine: 'assault', custom_traits: ''};
  const legacy = renderToStaticMarkup(createElement(StylePanel, styleProps(legacyDraft, false)));
  assert.match(legacy, /当前后台版本还不支持指挥官设置/);
  assert.match(legacy, /铁锤预设/, 'an older backend shows Hammer as the default');
});
