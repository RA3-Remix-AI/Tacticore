/**
 * Decision-record contract (schema_version 1) and its plain-language view.
 *
 * Backend: RPC operation `run.decisions` (Python method `run_decisions`),
 * args `{run_id, since_seq?}` -> `{records: (DecisionRecord | MatchEndRecord)[]}`.
 * Every field may be null or missing; parsing never throws on partial data.
 */

export type DecisionOutcomeStatus = 'applied' | 'rejected' | 'expired' | 'unknown';
export type MatchResult = 'victory' | 'defeat' | 'unknown';

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
  decision: {intents: string[]; objective: string | null; reasoning: string | null; valid_for_s: number | null} | null;
  outcome: {
    status: DecisionOutcomeStatus; reason_code: string | null; native_accepted: boolean | null; observed_effects: string[];
  } | null;
  model: {
    provider: string | null; model: string | null; latency_ms: number | null;
    input_bytes: number | null; output_bytes: number | null; error: string | null;
  } | null;
  prompt_version: string | null;
}

export interface MatchEndRecord {
  kind: 'match_end';
  seq: number | null;
  result: MatchResult;
  duration_s: number | null;
  players: unknown[];
}

export type DecisionStreamRecord = DecisionRecord | MatchEndRecord;

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
  };
}

function parseMatchEnd(v: Record<string, unknown>): MatchEndRecord {
  const result = v.result === 'victory' || v.result === 'defeat' ? v.result : 'unknown';
  return {kind: 'match_end', seq: num(v.seq), result, duration_s: num(v.duration_s),
    players: Array.isArray(v.players) ? v.players.slice(0, 16) : []};
}

/** Tolerant parser: drops malformed rows instead of failing the whole feed. */
export function parseDecisionRecords(value: unknown): DecisionStreamRecord[] {
  const rows = object(value) && Array.isArray(value.records) ? value.records : [];
  const parsed: DecisionStreamRecord[] = [];
  for (const row of rows.slice(0, 5000)) {
    if (!object(row)) continue;
    if (row.kind === 'match_end') parsed.push(parseMatchEnd(row));
    else if (row.schema_version === 1 || row.schema_version === undefined || row.schema_version === null) {
      const decision = parseDecision(row);
      if (decision) parsed.push(decision);
    }
  }
  return parsed;
}

export const isMatchEnd = (row: DecisionStreamRecord): row is MatchEndRecord => 'kind' in row && row.kind === 'match_end';

/** Merge an incremental page into the known feed; de-duplicates by seq and keeps order. */
export function mergeDecisionRecords(known: readonly DecisionStreamRecord[], page: readonly DecisionStreamRecord[]) {
  const decisions = new Map<number, DecisionRecord>();
  let end: MatchEndRecord | null = null;
  for (const row of [...known, ...page]) {
    if (isMatchEnd(row)) end = row;
    else decisions.set(row.seq, row);
  }
  const ordered: DecisionStreamRecord[] = [...decisions.values()].sort((a, b) => a.seq - b.seq);
  if (end) ordered.push(end);
  return ordered;
}

export function lastSeq(records: readonly DecisionStreamRecord[]): number | undefined {
  let value: number | undefined;
  for (const row of records) if (!isMatchEnd(row) && (value === undefined || row.seq > value)) value = row.seq;
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
}

export function decisionRow(record: DecisionRecord): DecisionRow {
  const status = record.outcome?.status ?? 'unknown';
  const model = record.model;
  const modelParts = [model?.model, model?.latency_ms !== null && model?.latency_ms !== undefined ? `${Math.round(model.latency_ms)} ms` : null]
    .filter(Boolean);
  return {
    seq: record.seq,
    clock: gameClock(record.game_time_s),
    intents: (record.decision?.intents ?? []).map(actionLabel),
    objective: record.decision?.objective ?? null,
    reasoning: record.decision?.reasoning ?? null,
    badge: outcomeLabels[status],
    reason: status === 'applied' ? null : outcomeReason(record.outcome?.reason_code),
    effects: record.outcome?.observed_effects ?? [],
    threats: record.situation?.threats ?? [],
    modelLine: modelParts.length ? modelParts.join(' · ') : null,
    failed: Boolean(model?.error),
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
  const decisions = records.filter((row): row is DecisionRecord => !isMatchEnd(row));
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
}

export const resultLabels: Record<MatchResult, string> = {victory: '胜利', defeat: '失败', unknown: '结果未知'};

export function reviewStats(records: readonly DecisionStreamRecord[]): ReviewStats {
  const decisions = records.filter((row): row is DecisionRecord => !isMatchEnd(row));
  const end = records.find(isMatchEnd) ?? null;
  const count = (status: DecisionOutcomeStatus) => decisions.filter(row => (row.outcome?.status ?? 'unknown') === status).length;
  const latencies = decisions.map(row => row.model?.latency_ms).filter((v): v is number => typeof v === 'number' && v >= 0);
  const tally = new Map<string, number>();
  for (const row of decisions) for (const intent of row.decision?.intents ?? []) tally.set(intent, (tally.get(intent) ?? 0) + 1);
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
  };
}
