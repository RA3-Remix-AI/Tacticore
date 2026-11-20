/**
 * Commander identities and the nine-parameter personality (plan §12, characters doc §5–§7).
 *
 * Profile contract: the draft carries `{commander_id, personality, voice_note}`; `profiles.list` may also return
 * `commanders: [{id, name, full_name, faction, available}]`. Everything here tolerates an older backend that sends
 * neither: built-in metadata is the fallback and Hammer is the default commander.
 */

export type CommanderId = 'hammer' | 'bastion' | 'ghost';
export type CommanderChoice = CommanderId | 'custom';
export type PersonalityKey =
  | 'aggression' | 'risk' | 'persistence' | 'punish' | 'preserve' | 'deception' | 'grudge' | 'adaptability'
  | 'bait_awareness';
export type Personality = Record<PersonalityKey, number>;

export interface CommanderMeta {
  id: CommanderId;
  name: string;
  codename: string;
  full_name: string;
  faction: string;
  available: boolean;
  style: string;
  tagline: string;
  description: string;
  tough: string;
  portrait: string;
  image: string;
  /** Reserved for the owner's future cutscene assets; not played yet. */
  video?: string;
  personality: Personality;
}

export const VOICE_NOTE_MAX_BYTES = 300;

/** The nine parameters with a one-line explanation of what each changes in play (plan §12.1). */
export const personalityParams: {key: PersonalityKey; label: string; hint: string}[] = [
  {key: 'aggression', label: '进攻性', hint: '越高越早出手、越少龟缩；影响总指挥选路线和战术参谋选姿态。'},
  {key: 'risk', label: '冒险', hint: '越高越敢贪经济或速攻，全力出击的门槛也越低。'},
  {key: 'persistence', label: '纠缠度', hint: '越高骚扰越频繁、越持久，不停摸你的矿车。'},
  {key: 'punish', label: '惩罚意识', hint: '越高越会在你扩张、攀科技或主力离家时立刻打你的薄弱点。'},
  {key: 'preserve', label: '惜兵', hint: '越高越早撤退、保存单位反复骚扰；越低越愿意以命换命。'},
  {key: 'deception', label: '诡诈', hint: '越高越常佯攻正面、同时偷袭侧翼或矿区。'},
  {key: 'grudge', label: '记仇', hint: '越高越会盯住同一个对手或同一个弱点反复打。'},
  {key: 'adaptability', label: '适应性', hint: '越高越会利用它对你的了解，同一招不让它吃两次亏。'},
  {key: 'bait_awareness', label: '识破诱饵', hint: '越高越会先侦察确认“窗口”和“撤退”，不容易中你的诱饵。'},
];

const values = (...levels: number[]): Personality =>
  Object.fromEntries(personalityParams.map((param, index) => [param.key, levels[index]])) as Personality;

export const builtInCommanders: readonly CommanderMeta[] = [
  {
    id: 'hammer', name: '铁锤', codename: 'HAMMER', full_name: '维克托·莫罗佐夫', faction: '苏联', available: true,
    style: '主动施压', tagline: '看清战线，再集中突破。',
    description: '主动侦察，寻找集中兵力的突破窗口。保留必要的防空与经济，避免缺少情报的正面消耗。',
    tough: '他不乱打，但只要你露出破绽，就会集中兵力砸在那一点上；佯攻和诱饵很难骗到他，打完就收。',
    portrait: '/commanders/hammer-portrait.webp', image: '/commanders/hammer.webp',
    personality: values(4, 3, 3, 5, 3, 2, 3, 4, 5),
  },
  {
    id: 'bastion', name: '堡垒', codename: 'BASTION', full_name: '伊芙琳·卡特', faction: '盟军', available: false,
    style: '稳健经营', tagline: '稳住后方，才有下一步。',
    description: '先稳固资源与防线，保留可以接应的预备力量。依据已侦察威胁安排支援，不因追击打乱阵线。',
    tough: '她很难被一波打死；你的主力离家时，她的预备队会出现在你的矿区；防线也会换位置。',
    portrait: '/commanders/bastion-portrait.webp', image: '/commanders/bastion.webp',
    personality: values(2, 2, 2, 4, 5, 3, 2, 5, 4),
  },
  {
    id: 'ghost', name: '幽灵', codename: 'GHOST', full_name: '神崎凛', faction: '升阳', available: false,
    style: '侧翼机动', tagline: '绕过锋芒，创造交战窗口。',
    description: '优先侦察侧翼与撤退路线，在局部形成兵力优势。以机动与协同寻找机会，避免陷入正面消耗。',
    tough: '她几乎不和你主力正面交战，却总在你防不到的地方出现；进攻路线每局都不一样。',
    portrait: '/commanders/ghost-portrait.webp', image: '/commanders/ghost.webp',
    personality: values(3, 4, 5, 4, 4, 5, 3, 5, 3),
  },
];

const object = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const isCommanderId = (v: unknown): v is CommanderId => v === 'hammer' || v === 'bastion' || v === 'ghost';

/** Built-in metadata, with the backend's names and availability applied when it sends them. */
export function mergeCommanders(backend: unknown): CommanderMeta[] {
  const rows = Array.isArray(backend) ? backend.filter(object) : [];
  return builtInCommanders.map(meta => {
    const row = rows.find(value => value.id === meta.id);
    if (!row) return {...meta};
    const text = (v: unknown, fallback: string) => (typeof v === 'string' && v.trim() ? v.slice(0, 40) : fallback);
    return {
      ...meta,
      name: text(row.name, meta.name),
      full_name: text(row.full_name, meta.full_name),
      faction: text(row.faction, meta.faction),
      available: typeof row.available === 'boolean' ? row.available : meta.available,
    };
  });
}

export function commanderMeta(id: unknown, commanders: readonly CommanderMeta[] = builtInCommanders) {
  return commanders.find(row => row.id === id) ?? null;
}

const level = (v: unknown): number | null => (typeof v === 'number' && Number.isInteger(v) && v >= 1 && v <= 5 ? v : null);

/** A complete, valid personality; missing or invalid values come from the fallback. */
export function parsePersonality(value: unknown, fallback: Personality): Personality {
  const source = object(value) ? value : {};
  return Object.fromEntries(personalityParams.map(({key}) => [key, level(source[key]) ?? fallback[key]])) as Personality;
}

export function personalityValid(value: unknown): boolean {
  return object(value) && personalityParams.every(({key}) => level(value[key]) !== null);
}

/** The preset whose values match exactly, or 'custom'. */
export function presetFor(personality: Personality): CommanderChoice {
  const match = builtInCommanders.find(row => personalityParams.every(({key}) => row.personality[key] === personality[key]));
  return match?.id ?? 'custom';
}

export function voiceNoteBytes(text: string): number {
  return new TextEncoder().encode(text).length;
}

export interface CommanderProfile {
  commander_id: CommanderChoice;
  personality: Personality;
  voice_note: string;
}

type DraftLike = {commander_id?: unknown; personality?: unknown; voice_note?: unknown; [key: string]: unknown};

/** The commander settings in a draft, with Hammer as the default for an older backend. */
export function commanderProfile(draft: DraftLike | null | undefined): CommanderProfile {
  const id = draft?.commander_id;
  const base = commanderMeta(isCommanderId(id) ? id : 'hammer')!.personality;
  const personality = parsePersonality(draft?.personality, base);
  const commander_id: CommanderChoice = id === 'custom' ? 'custom' : isCommanderId(id) ? id : 'hammer';
  const voice = typeof draft?.voice_note === 'string' ? draft.voice_note : '';
  return {commander_id, personality, voice_note: voice};
}

/** Whether the backend understands commander settings (it returns them, or a commander list). */
export function commanderSupported(draft: DraftLike | null | undefined, commanders: unknown): boolean {
  return (draft !== null && draft !== undefined && 'commander_id' in draft) || Array.isArray(commanders);
}

/** Choosing a commander applies its exact preset values. Unavailable commanders cannot be chosen. */
export function chooseCommander(id: CommanderId, commanders: readonly CommanderMeta[]): CommanderProfile | null {
  const meta = commanderMeta(id, commanders);
  if (!meta?.available) return null;
  return {commander_id: id, personality: {...meta.personality}, voice_note: ''};
}

/** Editing any value switches to 'custom' unless the result equals a preset exactly. */
export function editPersonality(profile: CommanderProfile, key: PersonalityKey, value: number): CommanderProfile {
  const next = {...profile.personality, [key]: level(value) ?? profile.personality[key]};
  const changed = next[key] !== profile.personality[key];
  return {...profile, personality: next, commander_id: changed ? 'custom' : profile.commander_id};
}

export type CommanderProblem = 'voice_note_too_long' | 'commander_unavailable' | 'personality_invalid' | null;

export function commanderProblem(profile: CommanderProfile, commanders: readonly CommanderMeta[]): CommanderProblem {
  if (voiceNoteBytes(profile.voice_note) > VOICE_NOTE_MAX_BYTES) return 'voice_note_too_long';
  if (!personalityValid(profile.personality)) return 'personality_invalid';
  if (profile.commander_id !== 'custom' && !commanderMeta(profile.commander_id, commanders)?.available) {
    return 'commander_unavailable';
  }
  return null;
}

/** The draft for `profiles.save`. An older backend rejects unknown fields, so commander fields go only when supported. */
export function profileSaveDraft<T extends DraftLike>(draft: T, supported: boolean): T {
  if (supported) return draft;
  const rest = {...draft};
  delete rest.commander_id;
  delete rest.personality;
  delete rest.voice_note;
  return rest;
}

/** What the top bar and match screen show for a commander choice or a decision record's `commander`. */
export function commanderBadge(id: unknown, commanders: readonly CommanderMeta[] = builtInCommanders, name?: string | null) {
  const meta = commanderMeta(id, commanders);
  if (meta) return {name: meta.name, full_name: meta.full_name, portrait: meta.portrait as string | null};
  return {name: name || (id === 'custom' ? '自定义指挥官' : '指挥官'), full_name: null, portrait: null};
}
