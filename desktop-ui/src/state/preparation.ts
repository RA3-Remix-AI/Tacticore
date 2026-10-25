/** Local next-match planning only. These values never grant game execution. */
export type PlannedFaction = "soviet" | "allies" | "empire" | "random";
export type CommanderRelationship = "ally" | "opponent";
export interface PreparationPlan {
  schemaVersion: 1;
  revision: number;
  game: "ra3";
  map: string;
  faction: PlannedFaction;
  relationship: CommanderRelationship;
  playerSlot: number;
  startingFunds: number;
  productionLimit: number;
  reserveFloor: number;
}
export interface SavedPreparation {
  plan: PreparationPlan;
  savedAt: string | null;
}
export const preparationStorageKey = "tacticore.desktop.preparation.v1";
export const factionLabels: Record<PlannedFaction, string> = {
  soviet: "苏联",
  allies: "盟军",
  empire: "旭日帝国",
  random: "随机阵营",
};
export const defaultPreparation: PreparationPlan = {
  schemaVersion: 1,
  revision: 1,
  game: "ra3",
  map: "工业区",
  faction: "soviet",
  relationship: "ally",
  playerSlot: 3,
  startingFunds: 10000,
  productionLimit: 2000,
  reserveFloor: 1500,
};
const integerWithin = (value: unknown, min: number, max: number) =>
  typeof value === "number" &&
  Number.isInteger(value) &&
  value >= min &&
  value <= max;

export function validatePreparation(value: PreparationPlan): string | null {
  if (value?.schemaVersion !== 1 || value.game !== "ra3")
    return "此备战方案版本或游戏类型不受支持。";
  if (!integerWithin(value.revision, 1, Number.MAX_SAFE_INTEGER))
    return "方案修订号无效，请重置本机方案。";
  if (
    typeof value.map !== "string" ||
    !value.map.trim() ||
    value.map.trim().length > 60
  )
    return "地图名称需为 1–60 个字符。";
  if (!Object.hasOwn(factionLabels, value.faction))
    return "请选择有效的计划阵营。";
  if (!["ally", "opponent"].includes(value.relationship))
    return "请选择指挥官与玩家的关系。";
  if (!integerWithin(value.playerSlot, 0, 15))
    return "Agent 玩家索引需为 0–15 的整数。";
  if (!integerWithin(value.startingFunds, 0, 1000000))
    return "计划初始资金需为 0–1,000,000 的整数；游戏实际范围待核验。";
  if (!integerWithin(value.productionLimit, 220, 10000))
    return "Agent 生产额度需为 220–10,000 的整数。";
  if (!integerWithin(value.reserveFloor, 500, 10000))
    return "资源保留底线需为 500–10,000 的整数。";
  return null;
}

/** Explicit selection prevents unrelated fields or credentials reaching storage/export. */
export function publicPreparation(value: PreparationPlan): PreparationPlan {
  return {
    schemaVersion: 1,
    revision: value.revision,
    game: "ra3",
    map: value.map.trim(),
    faction: value.faction,
    relationship: value.relationship,
    playerSlot: value.playerSlot,
    startingFunds: value.startingFunds,
    productionLimit: value.productionLimit,
    reserveFloor: value.reserveFloor,
  };
}

export function loadPreparation(
  storage?: Pick<Storage, "getItem">,
): SavedPreparation {
  try {
    const value = JSON.parse(storage?.getItem(preparationStorageKey) ?? "null");
    if (!value || validatePreparation(value.plan))
      throw new Error("invalid_plan");
    if (
      typeof value.savedAt !== "string" ||
      !Number.isFinite(Date.parse(value.savedAt))
    )
      throw new Error("invalid_timestamp");
    return { plan: publicPreparation(value.plan), savedAt: value.savedAt };
  } catch {
    return { plan: structuredClone(defaultPreparation), savedAt: null };
  }
}

export function savePreparation(
  storage: Pick<Storage, "setItem">,
  plan: PreparationPlan,
  now = new Date(),
): SavedPreparation {
  const error = validatePreparation(plan);
  if (error) throw new Error(error);
  const document: SavedPreparation = {
    plan: publicPreparation(plan),
    savedAt: now.toISOString(),
  };
  storage.setItem(preparationStorageKey, JSON.stringify(document));
  return document;
}

export function exportPreparation(
  plan: PreparationPlan,
  commander: { id: string; name: string },
) {
  const error = validatePreparation(plan);
  if (error) throw new Error(error);
  return {
    schemaVersion: 1,
    scope: "prepared_plan_only" as const,
    executionAuthorized: false,
    gameValuesVerified: false,
    description: "本机下一局备战计划，不是游戏设置、宿主连接库或执行命令。",
    commander: { localProfileId: commander.id, name: commander.name },
    plan: publicPreparation(plan),
  };
}
