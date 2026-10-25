import type { Commander, Doctrine } from "./settings";

export type PreferenceLevel = 1 | 2 | 3 | 4 | 5;
export type PreferenceKey =
  "attack" | "risk" | "economy" | "scouting" | "pursuit";
export type PreferencePreset =
  "steady" | "balanced" | "pressure" | "flank" | "custom";
export type CommanderPreferences = {
  preset: PreferencePreset;
} & Record<PreferenceKey, PreferenceLevel>;

export const preferenceAxes: {
  key: PreferenceKey;
  label: string;
  low: string;
  high: string;
  descriptions: readonly string[];
}[] = [
  {
    key: "attack",
    label: "进攻时机",
    low: "等待优势",
    high: "主动施压",
    descriptions: [
      "优先巩固阵线，出现明确优势再进攻。",
      "先确认兵力与情报，再寻找交战机会。",
      "根据敌情与资源，平衡推进和准备。",
      "更早寻找施压窗口，同时保留基础防守。",
      "积极创造交战机会，争取持续掌握节奏。",
    ],
  },
  {
    key: "risk",
    label: "风险承受",
    low: "保全部队",
    high: "接受交换",
    descriptions: [
      "倾向保留主力，遇到不利局面尽早脱离。",
      "谨慎投入兵力，预留撤退与接应空间。",
      "结合目标价值判断是否值得投入。",
      "愿为重要目标接受有限损失。",
      "高价值窗口出现时，倾向接受更大的兵力交换。",
    ],
  },
  {
    key: "economy",
    label: "经济投入",
    low: "维持兵力",
    high: "优先扩张",
    descriptions: [
      "优先补充当前作战力量，经济扩张靠后。",
      "先满足必要兵力，再逐步发展经济。",
      "保持作战与经济投入的平衡。",
      "保留基础防守后，更重视经济增长。",
      "局势允许时优先扩张，积累后续资源。",
    ],
  },
  {
    key: "scouting",
    label: "侦察积极",
    low: "必要侦察",
    high: "持续探路",
    descriptions: [
      "围绕当前任务补充必要情报。",
      "在投入主力前确认关键区域。",
      "定期更新关键方向的可见信息。",
      "更主动确认侧翼、威胁与行动窗口。",
      "持续寻找侦察机会，优先减少未知信息。",
    ],
  },
  {
    key: "pursuit",
    label: "追击尺度",
    low: "及时收队",
    high: "扩大战果",
    descriptions: [
      "达成当前目标后倾向收队整补。",
      "限制追击距离，优先保持队形与退路。",
      "根据视野和接应条件决定是否继续。",
      "条件允许时继续施压，争取扩大优势。",
      "积极利用胜势，但仍受视野、时效和执行限制。",
    ],
  },
];

export const preferencePresets: {
  id: Exclude<PreferencePreset, "custom">;
  label: string;
  description: string;
  doctrine: Doctrine;
  values: CommanderPreferences;
}[] = [
  {
    id: "steady",
    label: "稳健经营",
    description: "先稳住阵线，再积累资源。",
    doctrine: "defense",
    values: {
      preset: "steady",
      attack: 2,
      risk: 1,
      economy: 4,
      scouting: 3,
      pursuit: 1,
    },
  },
  {
    id: "balanced",
    label: "均衡应变",
    description: "根据局势，在发展与交战间取舍。",
    doctrine: "defense",
    values: {
      preset: "balanced",
      attack: 3,
      risk: 3,
      economy: 3,
      scouting: 3,
      pursuit: 3,
    },
  },
  {
    id: "pressure",
    label: "主动施压",
    description: "寻找早期窗口，主动争取节奏。",
    doctrine: "assault",
    values: {
      preset: "pressure",
      attack: 4,
      risk: 4,
      economy: 2,
      scouting: 3,
      pursuit: 4,
    },
  },
  {
    id: "flank",
    label: "侧翼游击",
    description: "用侦察与机动寻找局部机会。",
    doctrine: "maneuver",
    values: {
      preset: "flank",
      attack: 3,
      risk: 2,
      economy: 3,
      scouting: 5,
      pursuit: 2,
    },
  },
];

export function validatePreferences(value: unknown): string | null {
  if (!value || typeof value !== "object" || Array.isArray(value))
    return "指挥倾向格式无效。";
  const candidate = value as Record<string, unknown>;
  if (
    typeof candidate.preset !== "string" ||
    !["steady", "balanced", "pressure", "flank", "custom"].includes(
      candidate.preset,
    )
  )
    return "指挥风格预设无效。";
  for (const axis of preferenceAxes) {
    const level = candidate[axis.key];
    if (
      typeof level !== "number" ||
      !Number.isInteger(level) ||
      level < 1 ||
      level > 5
    )
      return "每项指挥倾向需要选择 1–5 档。";
  }
  const preset = preferencePresets.find((p) => p.id === candidate.preset);
  if (
    preset &&
    preferenceAxes.some(
      (axis) => candidate[axis.key] !== preset.values[axis.key],
    )
  )
    return "预设与倾向不一致，请重新选择或使用自定义风格。";
  return null;
}

export function publicPreferences(
  value: CommanderPreferences,
): CommanderPreferences {
  return {
    preset: value.preset,
    attack: value.attack,
    risk: value.risk,
    economy: value.economy,
    scouting: value.scouting,
    pursuit: value.pursuit,
  };
}

export function profilePreferences(
  profile: Pick<Commander, "doctrine" | "preferences">,
): CommanderPreferences {
  if (profile.preferences && !validatePreferences(profile.preferences))
    return publicPreferences(profile.preferences);
  const preset = preferencePresets.find(
    (p) => p.doctrine === profile.doctrine,
  )!;
  return publicPreferences(preset.values);
}

export function commanderStyleName(
  profile: Pick<Commander, "doctrine" | "preferences">,
): string {
  const preferences = profilePreferences(profile);
  return (
    preferencePresets.find((p) => p.id === preferences.preset)?.label ??
    "自定义风格"
  );
}

export function preferenceSummary(
  profile: Pick<Commander, "doctrine" | "preferences">,
): string {
  const preferences = profilePreferences(profile);
  return preferenceAxes
    .map((axis) => axis.descriptions[preferences[axis.key] - 1])
    .join("");
}

export function commanderPreview(
  profile: Pick<Commander, "doctrine" | "preferences">,
) {
  const preferences = profilePreferences(profile);
  return [
    {
      id: "opening",
      title: "开局准备",
      text: `${preferences.scouting >= 4 ? "先寻找侦察窗口，确认关键通路和侧翼。" : "先确认周边情报与基础防守。"}${preferences.economy >= 4 ? "局势允许时，优先积累资源与扩张。" : preferences.attack >= 4 ? "必要兵力到位后，更早寻找施压机会。" : "根据可见威胁，平衡发展和作战准备。"}`,
    },
    {
      id: "under-attack",
      title: "受到突袭",
      text: `${preferences.risk <= 2 ? "先保留主力与退路，尽量避免不利交换。" : "结合威胁与目标价值，判断是否投入兵力。"}${preferences.attack >= 4 ? "防线稳定后，尝试寻找反击窗口。" : "先稳定当前阵线，再调整下一步计划。"}`,
    },
    {
      id: "advantage",
      title: "取得优势",
      text:
        preferences.pursuit >= 4
          ? "在视野与接应条件允许时继续施压，争取扩大优势；失去条件时重新判断。"
          : preferences.pursuit <= 2
            ? "倾向完成当前目标后整补，保留队形与退路，再决定是否继续。"
            : "复核情报、资源与任务反馈，决定继续推进或收队整补。",
    },
  ];
}

export function commanderPlan(profile: Commander) {
  const personality = ({ assault: 0, defense: 1, maneuver: 2 } as const)[
    profile.doctrine
  ];
  return {
    schemaVersion: 1,
    scope: "local_preference_draft",
    commanderName: profile.name,
    personality,
    personalityName: ["assault", "fortifier", "raider"][personality],
    preferences: profilePreferences(profile),
    generatedTraits: preferenceSummary(profile),
    customTraits: profile.traits,
    appliedToHost: false,
  };
}
