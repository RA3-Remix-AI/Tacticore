import {commanderBadge} from './commanders';

/**
 * Decision-record contract (schema_version 1) and its plain-language view.
 *
 * Backend: RPC operation `run.decisions` (Python method `run_decisions`),
 * args `{run_id, since_seq?}` -> `{records: (DecisionRecord | MatchEndRecord)[]}`.
 * Every field may be null or missing; parsing never throws on partial data.
 *
 * Layered decisions (all optional, absent on an older backend): `layer`, `commander: {id, name}`, commander records'
 * `directive`, every record's `composer: {applied_intents, dropped}` and `decision.recorded_only`; the page's
 * `run` (run_start) adds `commander`, `decision_mode` and `opening_variant`.
 */

export type DecisionOutcomeStatus = 'applied' | 'rejected' | 'expired' | 'unknown';
export type MatchResult = 'victory' | 'defeat' | 'unknown';
export type DecisionLayer = 'commander' | 'economy' | 'tactical' | 'opening';
export type DecisionMode = 'layered' | 'single';

export interface CommanderRef {id: string | null; name: string | null}

export interface Directive {
  route: string | null;
  resource_split: {economy: number | null; army: number | null; tech: number | null; reserve: number | null} | null;
  primary_enemy: number | null;
  overrides: string[];
  valid_for_s: number | null;
}

export interface ComposerResult {applied_intents: string[]; dropped: {intent: string; reason: string | null}[]}

export interface DecisionRecord {
  schema_version: 1;
  run_id: string | null;
  seq: number;
  game_time_s: number | null;
  wall_time: string | null;
  situation: {
    own: {credits: number | null; income_hint: string | null; army_count: number | null; building_count: number | null} | null;
    enemies: {player_id: number | null; last_seen_s: number | null; visible_count: number | null}[];
    threats: string[];
  } | null;
  decision: {
    intents: string[]; objective: string | null; reasoning: string | null; valid_for_s: number | null;
    recorded_only: string[];
  } | null;
  outcome: {
    status: DecisionOutcomeStatus; reason_code: string | null; native_accepted: boolean | null; observed_effects: string[];
  } | null;
  model: {
    provider: string | null; model: string | null; latency_ms: number | null;
    input_bytes: number | null; output_bytes: number | null; error: string | null;
  } | null;
  prompt_version: string | null;
  layer: DecisionLayer | null;
  commander: CommanderRef | null;
  directive: Directive | null;
  composer: ComposerResult | null;
}

export interface RunStartRecord {
  kind: 'run_start';
  commander: CommanderRef | null;
  decision_mode: DecisionMode | null;
  opening_variant: string | null;
  model: string | null;
}

export interface MatchEndRecord {
  kind: 'match_end';
  seq: number | null;
  result: MatchResult;
  duration_s: number | null;
  players: unknown[];
}

export type DecisionStreamRecord = DecisionRecord | MatchEndRecord | RunStartRecord;

/** One table for every model action name. Unknown names fall back to the raw name. */
export const actionLabels: Record<string, string> = {
  regroup: '集结部队',
  scout: '侦察敌情',
  withdraw: '撤退回防',
  reinforce: '增援基地',
  deployattack: '组织进攻',
  deploydefense: '布置防守',
  expand: '扩张经济',
  attackenemy: '进攻敌方',
  raideconomy: '袭扰敌方经济',
  budgeteconomy: '资源优先：经济',
  budgetarmy: '资源优先：军队',
  budgettech: '资源优先：科技',
  pauseconstruction: '暂停建造',
  advanceconstruction: '继续建造',
  pauseproduction: '暂停生产',
  advanceproduction: '继续生产',
};

export function actionLabel(name: string): string {
  if (Object.hasOwn(actionLabels, name)) return actionLabels[name];
  const focus = /^focusenemy(\d{1,2})$/.exec(name);
  if (focus) return `集中对付玩家 ${focus[1]}`;
  return name;
}

export const outcomeLabels: Record<DecisionOutcomeStatus, {label: string; tone: 'good' | 'bad' | 'muted' | 'warn'}> = {
  applied: {label: '已执行', tone: 'good'},
  rejected: {label: '未采纳', tone: 'bad'},
  expired: {label: '已过期', tone: 'muted'},
  unknown: {label: '结果未知', tone: 'warn'},
};

const object = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const str = (v: unknown, max = 2000): string | null => (typeof v === 'string' ? v.slice(0, max) : null);
const bool = (v: unknown): boolean | null => (typeof v === 'boolean' ? v : null);
const strings = (v: unknown, limit = 32): string[] =>
  Array.isArray(v) ? v.filter((row): row is string => typeof row === 'string').slice(0, limit).map(row => row.slice(0, 400)) : [];
const statuses: readonly string[] = ['applied', 'rejected', 'expired', 'unknown'];
const layers: readonly string[] = ['commander', 'economy', 'tactical', 'opening'];

function parseCommander(v: unknown): CommanderRef | null {
  if (!object(v)) return null;
  return {id: str(v.id, 40), name: str(v.name, 40)};
}

function parseDirective(v: unknown): Directive | null {
  if (!object(v)) return null;
  const split = object(v.resource_split) ? v.resource_split : null;
  return {
    route: str(v.route, 40),
    resource_split: split && {
      economy: num(split.economy), army: num(split.army), tech: num(split.tech), reserve: num(split.reserve),
    },
    primary_enemy: num(v.primary_enemy),
    overrides: strings(v.overrides, 12),
    valid_for_s: num(v.valid_for_s),
  };
}

function parseComposer(v: unknown): ComposerResult | null {
  if (!object(v)) return null;
  const dropped = Array.isArray(v.dropped) ? v.dropped.filter(object).slice(0, 16) : [];
  return {
    applied_intents: strings(v.applied_intents, 16),
    dropped: dropped.flatMap(row => {
      const intent = str(row.intent, 100);
      return intent ? [{intent, reason: str(row.reason, 200)}] : [];
    }),
  };
}

function parseDecision(v: Record<string, unknown>): DecisionRecord | null {
  const seq = num(v.seq);
  if (seq === null) return null;
  const situation = object(v.situation) ? v.situation : null;
  const own = situation && object(situation.own) ? situation.own : null;
  const decision = object(v.decision) ? v.decision : null;
  const outcome = object(v.outcome) ? v.outcome : null;
  const model = object(v.model) ? v.model : null;
  return {
    schema_version: 1,
    run_id: str(v.run_id, 64),
    seq,
    game_time_s: num(v.game_time_s),
    wall_time: str(v.wall_time, 64),
    situation: situation && {
      own: own && {
        credits: num(own.credits), income_hint: str(own.income_hint, 200),
        army_count: num(own.army_count), building_count: num(own.building_count),
      },
      enemies: Array.isArray(situation.enemies)
        ? situation.enemies.filter(object).slice(0, 16).map(row => ({
          player_id: num(row.player_id), last_seen_s: num(row.last_seen_s), visible_count: num(row.visible_count),
        }))
        : [],
      threats: strings(situation.threats),
    },
    decision: decision && {
      intents: strings(decision.intents, 16),
      objective: str(decision.objective, 400),
      reasoning: str(decision.reasoning),
      valid_for_s: num(decision.valid_for_s),
      recorded_only: strings(decision.recorded_only, 16),
    },
    outcome: outcome && {
      status: (statuses.includes(String(outcome.status)) ? outcome.status : 'unknown') as DecisionOutcomeStatus,
      reason_code: str(outcome.reason_code, 100),
      native_accepted: bool(outcome.native_accepted),
      observed_effects: strings(outcome.observed_effects),
    },
    model: model && {
      provider: str(model.provider, 100), model: str(model.model, 200), latency_ms: num(model.latency_ms),
      input_bytes: num(model.input_bytes), output_bytes: num(model.output_bytes), error: str(model.error, 400),
    },
    prompt_version: str(v.prompt_version, 100),
    layer: layers.includes(String(v.layer)) ? (v.layer as DecisionLayer) : null,
    commander: parseCommander(v.commander),
    directive: parseDirective(v.directive ?? decision?.directive),
    composer: parseComposer(v.composer),
  };
}

function parseRunStart(v: Record<string, unknown>): RunStartRecord {
  const mode = v.decision_mode === 'layered' || v.decision_mode === 'single' ? v.decision_mode : null;
  return {
    kind: 'run_start', commander: parseCommander(v.commander), decision_mode: mode,
    opening_variant: str(v.opening_variant, 80), model: str(v.model, 200),
  };
}

function parseMatchEnd(v: Record<string, unknown>): MatchEndRecord {
  const result = v.result === 'victory' || v.result === 'defeat' ? v.result : 'unknown';
  // The host writes players as {"<player_id>": {...}}; older fixtures use an array.
  const players = Array.isArray(v.players)
    ? v.players
    : object(v.players)
      ? Object.entries(v.players).map(([id, row]) => (object(row) ? {player_id: Number(id), ...row} : {player_id: Number(id)}))
      : [];
  return {kind: 'match_end', seq: num(v.seq), result, duration_s: num(v.duration_s), players: players.slice(0, 16)};
}

/** Rows of a run.decisions page: `{run, decisions, match_end}` from the host, or `{records}` from fixtures. */
function pageRows(value: unknown): unknown[] {
  if (!object(value)) return [];
  if (Array.isArray(value.records)) return value.records;
  const rows: unknown[] = object(value.run) ? [{...value.run, kind: 'run_start'}] : [];
  if (Array.isArray(value.decisions)) rows.push(...value.decisions);
  if (object(value.match_end)) rows.push({...value.match_end, kind: 'match_end'});
  return rows;
}

/** Tolerant parser: drops malformed rows instead of failing the whole feed. */
export function parseDecisionRecords(value: unknown): DecisionStreamRecord[] {
  const rows = pageRows(value);
  const parsed: DecisionStreamRecord[] = [];
  for (const row of rows.slice(0, 5000)) {
    if (!object(row)) continue;
    if (row.kind === 'match_end') parsed.push(parseMatchEnd(row));
    else if (row.kind === 'run_start') parsed.push(parseRunStart(row));
    else if (row.kind !== undefined && row.kind !== null && row.kind !== 'decision') continue;
    else if (row.schema_version === 1 || row.schema_version === undefined || row.schema_version === null) {
      const decision = parseDecision(row);
      if (decision) parsed.push(decision);
    }
  }
  return parsed;
}

export const isMatchEnd = (row: DecisionStreamRecord): row is MatchEndRecord => 'kind' in row && row.kind === 'match_end';
export const isRunStart = (row: DecisionStreamRecord): row is RunStartRecord =>
  'kind' in row && row.kind === 'run_start';
export const isDecision = (row: DecisionStreamRecord): row is DecisionRecord => !('kind' in row);
export const decisionsOf = (records: readonly DecisionStreamRecord[]) => records.filter(isDecision);

/** Merge an incremental page into the known feed; de-duplicates by seq, run_start first and match_end last. */
export function mergeDecisionRecords(known: readonly DecisionStreamRecord[], page: readonly DecisionStreamRecord[]) {
  const decisions = new Map<number, DecisionRecord>();
  let end: MatchEndRecord | null = null;
  let start: RunStartRecord | null = null;
  for (const row of [...known, ...page]) {
    if (isMatchEnd(row)) end = row;
    else if (isRunStart(row)) start = row;
    else decisions.set(row.seq, row);
  }
  const ordered: DecisionStreamRecord[] = [...decisions.values()].sort((a, b) => a.seq - b.seq);
  if (start) ordered.unshift(start);
  if (end) ordered.push(end);
  return ordered;
}

export function lastSeq(records: readonly DecisionStreamRecord[]): number | undefined {
  let value: number | undefined;
  for (const row of decisionsOf(records)) if (value === undefined || row.seq > value) value = row.seq;
  return value;
}

export function gameClock(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return '--:--';
  const whole = Math.floor(seconds);
  const minutes = Math.floor(whole / 60), rest = whole % 60;
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
}

const reasonText: Record<string, string> = {
  native_rejected: '游戏内 AI 没有接受这条指令',
  intent_expired: '指令在执行前已过期',
  superseded: '被更新的决定替换',
  state_changed: '战况变化，指令未执行',
  capability_unavailable: '这局暂不支持该动作',
  delivery_unknown: '无法确认是否送达',
  model_call_failed: '模型调用失败',
  model_timeout: '模型响应超时',
  invalid_model_output: '模型输出无法解析',
  commander_veto: '总指挥否决了这个方案',
  directive_override: '与总指挥方针冲突',
};

export function outcomeReason(code: string | null | undefined): string | null {
  if (!code) return null;
  return reasonText[code] ?? code;
}

export interface DecisionRow {
  seq: number;
  clock: string;
  intents: string[];
  objective: string | null;
  reasoning: string | null;
  badge: {label: string; tone: 'good' | 'bad' | 'muted' | 'warn'};
  reason: string | null;
  effects: string[];
  threats: string[];
  modelLine: string | null;
  failed: boolean;
  layer: DecisionLayer | null;
  layerLabel: string | null;
  /** Shown for commander-layer records. */
  commander: {name: string; portrait: string | null} | null;
  directiveLine: string | null;
  /** "未采纳：<intent>（原因）" for every intent the composer dropped. */
  dropped: string[];
  /** "仅记录，尚未执行：…" when the layer asked for things the executor cannot do yet. */
  recordedOnly: string | null;
}

export function decisionRow(record: DecisionRecord): DecisionRow {
  const status = record.outcome?.status ?? 'unknown';
  const model = record.model;
  const modelParts = [model?.model, model?.latency_ms !== null && model?.latency_ms !== undefined ? `${Math.round(model.latency_ms)} ms` : null]
    .filter(Boolean);
  return {
    seq: record.seq,
    clock: gameClock(record.game_time_s),
    // With a composer result, only the intents it actually applied are shown as actions.
    intents: (record.composer ? record.composer.applied_intents : record.decision?.intents ?? []).map(actionLabel),
    objective: record.decision?.objective ?? null,
    reasoning: record.decision?.reasoning ?? null,
    badge: outcomeLabels[status],
    reason: status === 'applied' ? null : outcomeReason(record.outcome?.reason_code),
    effects: record.outcome?.observed_effects ?? [],
    threats: record.situation?.threats ?? [],
    modelLine: modelParts.length ? modelParts.join(' · ') : null,
    failed: Boolean(model?.error),
    layer: record.layer,
    layerLabel: record.layer ? layerLabels[record.layer] : null,
    commander: record.layer === 'commander'
      ? commanderBadge(record.commander?.id, undefined, record.commander?.name) : null,
    directiveLine: record.directive ? directiveLine(record.directive) : null,
    dropped: (record.composer?.dropped ?? []).map(row => droppedText(row.intent, row.reason)),
    recordedOnly: recordedOnlyText(record.decision?.recorded_only ?? []),
  };
}

// ----- layered decisions -----

export const layerLabels: Record<DecisionLayer, string> = {
  commander: '总指挥', economy: '经济参谋', tactical: '战术参谋', opening: '开局',
};
export const layerOrder: readonly DecisionLayer[] = ['commander', 'economy', 'tactical', 'opening'];

export const routeLabels: Record<string, string> = {
  rush: '速攻', steady_growth: '稳健发育', tech_pressure: '科技压制', all_in: '全力出击', defend_counter: '防守反击',
};

export const overrideLabels: Record<string, string> = {
  no_expansion: '不扩张', no_tech: '暂停科技', no_retreat: '不撤退', hold_base: '守住主基地',
  abandon_expansion: '放弃分矿', naval_transition: '转型海军',
};

const recordedOnlyLabels: Record<string, string> = {
  capacity_target: '产能目标', tech_timing: '科技时机', protocol_pick_preference: '协议选点',
  composition_need: '兵种需求', doctrine: '协同战法', power_usage: '协议技能使用',
};

const droppedReasons: Record<string, string> = {
  directive_override: '与总指挥方针冲突', override_conflict: '与总指挥方针冲突', override: '方针禁止',
  overrides: '方针禁止', commander_veto: '总指挥否决', vetoed: '总指挥否决', veto: '总指挥否决',
  domain_not_owned: '不属于这一层的职责', superseded: '被更新的决定替换', expired: '意图已过期',
  intent_expired: '意图已过期', capability_unavailable: '这局暂不支持该动作', military_task_taken: '同一时间只执行一个军事任务',
};

/** Staff postures are not native action names; give them labels too. */
const postureLabels: Record<string, string> = {
  attack: '进攻', defend: '防守', patrol: '巡逻', harass: '骚扰', all_in: '全力出击',
};

const lookup = (table: Record<string, string>, key: string) => (Object.hasOwn(table, key) ? table[key] : null);

export function routeLabel(route: string | null): string {
  return route ? lookup(routeLabels, route) ?? route : '未定';
}

export function overrideLabel(name: string): string {
  return lookup(overrideLabels, name) ?? name;
}

function intentLabel(intent: string): string {
  return lookup(postureLabels, intent) ?? actionLabel(intent);
}

/** A reason like `directive_override:no_expansion` reads "与总指挥方针冲突：不扩张". */
export function droppedReason(reason: string | null): string {
  if (!reason) return '原因未记录';
  const [code, detail] = reason.split(':', 2);
  const text = lookup(droppedReasons, code) ?? reason;
  if (!detail || text === reason) return text;
  return `${text}：${overrideLabel(detail)}`;
}

export function droppedText(intent: string, reason: string | null): string {
  return `未采纳：${intentLabel(intent)}（${droppedReason(reason)}）`;
}

export function recordedOnlyText(fields: readonly string[]): string | null {
  if (!fields.length) return null;
  return `仅记录，尚未执行：${fields.map(name => lookup(recordedOnlyLabels, name) ?? name).join('、')}`;
}

function directiveLine(directive: Directive): string {
  const parts = [`方针：${routeLabel(directive.route)}`];
  if (directive.primary_enemy !== null) parts.push(`主攻玩家 ${directive.primary_enemy}`);
  parts.push(...directive.overrides.map(overrideLabel));
  return parts.join(' · ');
}

export interface SplitShare {key: 'economy' | 'army' | 'tech' | 'reserve'; label: string; percent: number}

const splitLabels = {economy: '经济', army: '军队', tech: '科技', reserve: '储备'} as const;

/** Resource split as whole percentages of its own total (the backend may send fractions or percents). */
export function splitShares(split: Directive['resource_split']): SplitShare[] {
  if (!split) return [];
  const keys = Object.keys(splitLabels) as SplitShare['key'][];
  const total = keys.reduce((sum, key) => sum + Math.max(0, split[key] ?? 0), 0);
  if (total <= 0) return [];
  const percent = (key: SplitShare['key']) => Math.round((Math.max(0, split[key] ?? 0) / total) * 100);
  return keys.map(key => ({key, label: splitLabels[key], percent: percent(key)})).filter(row => row.percent > 0);
}

export interface DirectiveView {
  route: string;
  shares: SplitShare[];
  primaryEnemy: string | null;
  overrides: string[];
  since: string;
  validFor: string | null;
  reasoning: string | null;
  commander: {name: string; portrait: string | null} | null;
}

/** "当前方针": the latest commander record that carries a directive. */
export function currentDirective(records: readonly DecisionStreamRecord[]): DirectiveView | null {
  const latest = [...decisionsOf(records)].reverse().find(row => row.layer === 'commander' && row.directive);
  const directive = latest?.directive;
  if (!latest || !directive) return null;
  return {
    route: routeLabel(directive.route),
    shares: splitShares(directive.resource_split),
    primaryEnemy: directive.primary_enemy === null ? null : `玩家 ${directive.primary_enemy}`,
    overrides: directive.overrides.map(overrideLabel),
    since: gameClock(latest.game_time_s),
    validFor: directive.valid_for_s === null ? null : `${Math.round(directive.valid_for_s)} 秒`,
    reasoning: latest.decision?.reasoning ?? null,
    commander: commanderBadge(latest.commander?.id, undefined, latest.commander?.name),
  };
}

export type LayerFilter = DecisionLayer | 'all';

export function filterByLayer(records: readonly DecisionStreamRecord[], layer: LayerFilter): DecisionStreamRecord[] {
  return layer === 'all' ? [...records] : records.filter(row => !isDecision(row) || row.layer === layer);
}

/** Layers present in the feed, in display order, with counts. Empty for an older (single-layer) backend. */
export type LayerCount = {layer: DecisionLayer; label: string; count: number};

export function layerCounts(records: readonly DecisionStreamRecord[]): LayerCount[] {
  const decisions = decisionsOf(records);
  return layerOrder
    .map(layer => ({layer, label: layerLabels[layer], count: decisions.filter(row => row.layer === layer).length}))
    .filter(row => row.count > 0);
}

export interface RunInfo {
  commander: {name: string; full_name: string | null; portrait: string | null} | null;
  decisionMode: string | null;
  openingVariant: string | null;
}

const decisionModeLabels: Record<DecisionMode, string> = {layered: '分层决策（总指挥 + 参谋）', single: '单一决策'};

/** Commander, decision mode and opening variant from run_start, with the records' commander as a fallback. */
export function runInfo(records: readonly DecisionStreamRecord[]): RunInfo {
  const start = records.find(isRunStart) ?? null;
  const ref = start?.commander ?? decisionsOf(records).find(row => row.commander)?.commander ?? null;
  return {
    commander: ref ? commanderBadge(ref.id, undefined, ref.name) : null,
    decisionMode: start?.decision_mode ? decisionModeLabels[start.decision_mode] : null,
    openingVariant: start?.opening_variant ?? null,
  };
}

export interface StrategySummary {
  available: boolean;
  objective: string;
  intents: string[];
  reasoning: string | null;
  since: string;
  credits: number | null;
  army: number | null;
  enemiesSeen: number;
}

/** The latest decision that carries intents is "what the AI is doing now". */
export function currentStrategy(records: readonly DecisionStreamRecord[]): StrategySummary {
  const decisions = decisionsOf(records);
  const latest = [...decisions].reverse().find(row => (row.decision?.intents.length ?? 0) > 0 || row.decision?.objective);
  if (!latest) {
    return {available: false, objective: 'AI 还没有做出决定', intents: [], reasoning: null, since: '--:--',
      credits: null, army: null, enemiesSeen: 0};
  }
  return {
    available: true,
    objective: latest.decision?.objective ?? (latest.decision?.intents.map(actionLabel).join('、') || '保持当前部署'),
    intents: (latest.decision?.intents ?? []).map(actionLabel),
    reasoning: latest.decision?.reasoning ?? null,
    since: gameClock(latest.game_time_s),
    credits: latest.situation?.own?.credits ?? null,
    army: latest.situation?.own?.army_count ?? null,
    enemiesSeen: latest.situation?.enemies.filter(row => (row.visible_count ?? 0) > 0).length ?? 0,
  };
}

export interface ReviewStats {
  result: MatchResult;
  resultLabel: string;
  duration: string;
  decisions: number;
  applied: number;
  rejected: number;
  expired: number;
  unknown: number;
  modelErrors: number;
  averageLatencyMs: number | null;
  topIntents: {label: string; count: number}[];
  ended: boolean;
  layers: LayerCount[];
  dropped: number;
  recordedOnly: number;
  run: RunInfo;
}

export const resultLabels: Record<MatchResult, string> = {victory: '胜利', defeat: '失败', unknown: '结果未知'};

export function reviewStats(records: readonly DecisionStreamRecord[]): ReviewStats {
  const decisions = decisionsOf(records);
  const end = records.find(isMatchEnd) ?? null;
  const count = (status: DecisionOutcomeStatus) => decisions.filter(row => (row.outcome?.status ?? 'unknown') === status).length;
  const latencies = decisions.map(row => row.model?.latency_ms).filter((v): v is number => typeof v === 'number' && v >= 0);
  const tally = new Map<string, number>();
  // Dropped intents were never used, so a composer result counts only what it applied.
  for (const row of decisions) {
    for (const intent of row.composer ? row.composer.applied_intents : row.decision?.intents ?? []) {
      tally.set(intent, (tally.get(intent) ?? 0) + 1);
    }
  }
  const lastTime = decisions.reduce<number | null>((max, row) => (row.game_time_s !== null && (max === null || row.game_time_s > max) ? row.game_time_s : max), null);
  const result = end?.result ?? 'unknown';
  return {
    result,
    resultLabel: end ? resultLabels[result] : '对局未结算',
    duration: gameClock(end?.duration_s ?? lastTime),
    decisions: decisions.length,
    applied: count('applied'),
    rejected: count('rejected'),
    expired: count('expired'),
    unknown: count('unknown'),
    modelErrors: decisions.filter(row => row.model?.error).length,
    averageLatencyMs: latencies.length ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length) : null,
    topIntents: [...tally.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5).map(([name, n]) => ({label: actionLabel(name), count: n})),
    ended: end !== null,
    layers: layerCounts(records),
    dropped: decisions.reduce((sum, row) => sum + (row.composer?.dropped.length ?? 0), 0),
    recordedOnly: decisions.filter(row => (row.decision?.recorded_only.length ?? 0) > 0).length,
    run: runInfo(records),
  };
}
