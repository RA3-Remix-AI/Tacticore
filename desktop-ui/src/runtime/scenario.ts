/**
 * Match scenario contract carried by discovered candidates (`candidate.scenario`).
 * Older backends omit it; every view here degrades to the legacy fields.
 */
export type ScenarioMode = 'ai_vs_native' | 'human_with_ai' | 'human_vs_ai' | 'other';
export type PlayerKind = 'model_ai' | 'native_ai' | 'human';
export type Difficulty = 'easy' | 'medium' | 'hard' | 'brutal';

export interface ScenarioPlayer {
  player_id: number;
  kind: PlayerKind;
  team: number | null;
  difficulty: Difficulty | null;
  faction: string | null;
}

export interface MatchScenario {
  map_id: string | null;
  display_map: string | null;
  mode: ScenarioMode;
  model_player_id: number | null;
  players: ScenarioPlayer[];
  /** Difficulty comes from the lobby and is not read from memory today; shown only when verified. */
  difficulty_verified: boolean;
  own_start_waypoint: string | null;
  observer_player_ids: number[];
}

const object = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const int = (v: unknown): number | null => (typeof v === 'number' && Number.isInteger(v) ? v : null);
const text = (v: unknown, max = 120): string | null => (typeof v === 'string' && v.trim() ? v.trim().slice(0, max) : null);
const modes: readonly string[] = ['ai_vs_native', 'human_with_ai', 'human_vs_ai', 'other'];
const kinds: readonly string[] = ['model_ai', 'native_ai', 'human'];
const difficulties: readonly string[] = ['easy', 'medium', 'hard', 'brutal'];

/** Returns null when the backend did not send a usable scenario. */
export function parseScenario(value: unknown): MatchScenario | null {
  if (!object(value)) return null;
  const players = Array.isArray(value.players)
    ? value.players.filter(object).slice(0, 8).flatMap(row => {
      const id = int(row.player_id);
      if (id === null || !kinds.includes(String(row.kind))) return [];
      return [{
        player_id: id,
        kind: row.kind as PlayerKind,
        team: int(row.team),
        difficulty: difficulties.includes(String(row.difficulty)) ? row.difficulty as Difficulty : null,
        faction: text(row.faction, 40),
      }];
    })
    : [];
  return {
    map_id: text(value.map_id),
    display_map: text(value.display_map),
    mode: modes.includes(String(value.mode)) ? value.mode as ScenarioMode : 'other',
    model_player_id: int(value.model_player_id),
    players,
    difficulty_verified: value.difficulty_verified === true,
    own_start_waypoint: text(value.own_start_waypoint, 40),
    observer_player_ids: Array.isArray(value.observer_player_ids)
      ? value.observer_player_ids.flatMap(row => (int(row) === null ? [] : [row as number])).slice(0, 8) : [],
  };
}

export const modeLabels: Record<ScenarioMode, string> = {
  ai_vs_native: '观战：弈核 AI 对战电脑',
  human_with_ai: '并肩作战：你和弈核 AI 一队',
  human_vs_ai: '对战：你对抗弈核 AI',
  other: '其他组合',
};

export const kindLabels: Record<PlayerKind, string> = {model_ai: '弈核 AI', native_ai: '电脑', human: '玩家'};
export const difficultyLabels: Record<Difficulty, string> = {easy: '简单', medium: '中等', hard: '困难', brutal: '凶残'};

const factionNames: Record<string, string> = {
  soviet: '苏联', soviets: '苏联', allies: '盟军', allied: '盟军', empire: '升阳帝国', japan: '升阳帝国',
  rising_sun: '升阳帝国', random: '随机',
};

export function factionLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  return factionNames[value.toLowerCase().replace(/[\s-]+/g, '_')] ?? value;
}

export interface PlayerRow {
  key: string;
  seat: string;
  role: string;
  detail: string;
  team: string;
  isModel: boolean;
}

export interface TeamGroup {key: string; label: string; players: PlayerRow[]}

export interface ScenarioView {
  known: boolean;
  map: string;
  modeLabel: string;
  mode: ScenarioMode | null;
  teams: TeamGroup[];
  summary: string;
  /** Plain notes about limits of this layout (observers, start position). */
  notes: string[];
}

function playerRow(player: ScenarioPlayer, modelId: number | null, difficultyVerified: boolean): PlayerRow {
  const isModel = player.kind === 'model_ai' || player.player_id === modelId;
  const detail = [
    factionLabel(player.faction),
    player.kind === 'native_ai' && difficultyVerified && player.difficulty ? difficultyLabels[player.difficulty] : null,
  ].filter(Boolean).join(' · ');
  return {
    key: `p${player.player_id}`,
    seat: `玩家 ${player.player_id}`,
    role: isModel ? kindLabels.model_ai : kindLabels[player.kind],
    detail,
    team: player.team === null ? '无队伍' : `队伍 ${player.team}`,
    isModel,
  };
}

/** Group players by team; players without a team each stand alone. */
export function scenarioView(
  scenario: MatchScenario | null,
  fallback: {map?: string | null; faction?: string | null; player_id?: number | null} = {},
): ScenarioView {
  if (!scenario) {
    const faction = factionLabel(fallback.faction ?? null);
    return {
      known: false,
      map: fallback.map || '未知地图',
      modeLabel: '对局详情暂不可用',
      mode: null,
      teams: [],
      notes: [],
      summary: fallback.player_id !== undefined && fallback.player_id !== null
        ? `弈核 AI 控制玩家 ${fallback.player_id}${faction ? `（${faction}）` : ''}`
        : '当前版本没有提供完整的席位信息',
    };
  }
  const groups = new Map<string, TeamGroup>();
  for (const player of [...scenario.players].sort((a, b) => (a.team ?? 99) - (b.team ?? 99) || a.player_id - b.player_id)) {
    const key = player.team === null ? `solo-${player.player_id}` : `team-${player.team}`;
    const group = groups.get(key) ?? {key, label: player.team === null ? '无队伍' : `队伍 ${player.team}`, players: []};
    group.players.push(playerRow(player, scenario.model_player_id, scenario.difficulty_verified));
    groups.set(key, group);
  }
  const count = (kind: PlayerKind) => scenario.players.filter(row => row.kind === kind).length;
  const parts = [
    count('human') ? `${count('human')} 名玩家` : null,
    count('model_ai') ? `${count('model_ai')} 个弈核 AI` : null,
    count('native_ai') ? `${count('native_ai')} 个电脑` : null,
  ].filter(Boolean);
  return {
    known: true,
    map: scenario.display_map || scenario.map_id || fallback.map || '未知地图',
    modeLabel: modeLabels[scenario.mode],
    mode: scenario.mode,
    teams: [...groups.values()],
    notes: [
      ...(scenario.observer_player_ids.length ? [`观察者：${scenario.observer_player_ids.map(id => `玩家 ${id}`).join('、')}`] : []),
      ...(scenario.own_start_waypoint && scenario.own_start_waypoint !== 'Player_2_Start'
        ? ['弈核电脑不在 2 号出生点：这局「集结部队」「撤退回防」不可用。'] : []),
    ],
    summary: parts.length ? parts.join('，') : '席位信息为空',
  };
}
