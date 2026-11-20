/**
 * How the player wants to play. Generates lobby instructions for any RA3 1.12
 * map; nothing here names a specific map, seat number or start position.
 */
import type {ScenarioMode} from './scenario';
import {modeLabels} from './scenario';

export type PlayMode = Exclude<ScenarioMode, 'other'>;

export const playModes: {id: PlayMode; title: string; tagline: string; description: string}[] = [
  {
    id: 'ai_vs_native',
    title: '观战',
    tagline: '看弈核 AI 和游戏电脑对打',
    description: '你只观看。弈核 AI 指挥一个电脑席位，对手是游戏自带的电脑。',
  },
  {
    id: 'human_with_ai',
    title: '和 AI 并肩作战',
    tagline: '弈核 AI 是你的队友',
    description: '你和弈核 AI 在同一队伍，一起对抗游戏电脑或其他玩家。',
  },
  {
    id: 'human_vs_ai',
    title: '挑战 AI',
    tagline: '你亲自对抗弈核 AI',
    description: '你和弈核 AI 分属不同队伍，看看谁更会打。',
  },
];

/** The seat the model controls: a computer player using the compatible mod's commander AI. */
export const MODEL_SEAT_HINT = '兼容 Mod 提供的弈核指挥电脑';

export function lobbyInstructions(mode: PlayMode): string[] {
  const common = [
    '在游戏中进入「遭遇战」，选择任意一张 1.12 地图。',
  ];
  const finish = '开始游戏，然后回到本窗口点击「查找对局」。';
  switch (mode) {
    case 'ai_vs_native':
      return [
        ...common,
        '把你自己的位置设为「观察者」。',
        `添加一个电脑席位，选择${MODEL_SEAT_HINT}；阵营随意。`,
        '再添加至少一个普通电脑作为对手，难度随意，并放在和弈核 AI 不同的队伍。',
        finish,
      ];
    case 'human_with_ai':
      return [
        ...common,
        '你自己占一个玩家位置，选择喜欢的阵营。',
        `添加一个电脑席位，选择${MODEL_SEAT_HINT}，并设为和你相同的队伍。`,
        '添加对手（普通电脑或其他玩家），放在另一支队伍。',
        finish,
      ];
    case 'human_vs_ai':
      return [
        ...common,
        '你自己占一个玩家位置，选择喜欢的阵营。',
        `添加一个电脑席位，选择${MODEL_SEAT_HINT}，并设为和你不同的队伍。`,
        '需要的话，可以再添加普通电脑作为任意一方的队友。',
        finish,
      ];
  }
}

/** A gentle notice when the discovered lobby does not match what the player picked. */
export function modeMismatch(selected: PlayMode | null, discovered: ScenarioMode | null | undefined): string | null {
  if (!selected || !discovered || discovered === selected) return null;
  if (discovered === 'other') return '这局的席位组合不属于三种常用模式，可能暂不支持。如果开始失败，请按「对局模式」里的提示调整大厅。';
  return `发现的对局是「${modeLabels[discovered]}」，和你选择的「${modeLabels[selected]}」不同。仍可以开始，或在设置中切换模式。`;
}

export interface SetupPreferences {completed: boolean; mode: PlayMode | null}
export const setupPreferencesKey = 'tacticore.desktop.setup.v1';
type ReadStorage = Pick<Storage, 'getItem'>;
type WriteStorage = Pick<Storage, 'setItem'>;

/** Only non-secret UI choices are stored in the browser. */
export function loadSetupPreferences(storage: ReadStorage | null): SetupPreferences {
  try {
    const value = JSON.parse(storage?.getItem(setupPreferencesKey) ?? 'null');
    const mode = playModes.some(row => row.id === value?.mode) ? value.mode as PlayMode : null;
    return {completed: value?.completed === true, mode};
  } catch {
    return {completed: false, mode: null};
  }
}

export function saveSetupPreferences(storage: WriteStorage | null, value: SetupPreferences) {
  try {
    storage?.setItem(setupPreferencesKey, JSON.stringify({completed: value.completed, mode: value.mode}));
  } catch {
    // Losing this only means the wizard is shown again.
  }
}
