import {
  profilePreferences,
  preferencePresets,
  validatePreferences,
  type CommanderPreferences,
} from "./preferences";
export type Doctrine = "assault" | "defense" | "maneuver";
export type Commander = {
  id: string;
  name: string;
  callsign: string;
  doctrine: Doctrine;
  traits: string;
  connectionId: string;
  modelOverride: string;
  revision: number;
  preferences?: CommanderPreferences;
};
export type Connection = {
  id: string;
  name: string;
  provider: "OpenAI" | "DeepSeek" | "自定义";
  endpoint: string;
  model: string;
};
export type Settings = {
  schemaVersion: 1;
  activeId: string;
  commanders: Commander[];
  connections: Connection[];
};
export const storageKey = "tacticore.desktop.demo.v1";
export const doctrineLabels: Record<Doctrine, string> = {
  assault: "突击",
  defense: "守备",
  maneuver: "机动",
};
export const doctrineDetails: Record<
  Doctrine,
  { code: string; summary: string }
> = {
  assault: {
    code: "VANGUARD",
    summary: "集中突破，抢占先机",
  },
  defense: {
    code: "SENTINEL",
    summary: "稳固阵线，保持预备",
  },
  maneuver: {
    code: "PATHFINDER",
    summary: "侦察侧翼，创造窗口",
  },
};
export const defaultSettings: Settings = {
  schemaVersion: 1,
  activeId: "iron",
  commanders: [
    {
      id: "iron",
      name: "铁锤",
      callsign: "01",
      doctrine: "assault",
      traits:
        "主动侦察，集中突破。保留必要的防空和经济，避免没有情报支撑的正面消耗。",
      connectionId: "deepseek",
      modelOverride: "",
      revision: 1,
    },
    {
      id: "bastion",
      name: "堡垒",
      callsign: "02",
      doctrine: "defense",
      traits:
        "先稳固资源与防线，保留预备力量。根据已侦察威胁安排支援，不盲目追击。",
      connectionId: "openai",
      modelOverride: "",
      revision: 1,
    },
    {
      id: "ghost",
      name: "幽灵",
      callsign: "03",
      doctrine: "maneuver",
      traits:
        "优先侦察侧翼与撤退路线，在局部形成优势。以机动和协同创造交战窗口。",
      connectionId: "deepseek",
      modelOverride: "",
      revision: 1,
    },
  ],
  connections: [
    {
      id: "deepseek",
      name: "DeepSeek · 演示连接",
      provider: "DeepSeek",
      endpoint: "https://api.deepseek.com",
      model: "demo-tactical-model",
    },
    {
      id: "openai",
      name: "OpenAI · 演示连接",
      provider: "OpenAI",
      endpoint: "https://api.openai.com/v1",
      model: "demo-general-model",
    },
  ],
};
export function validateConnection(value: Connection): string | null {
  if (!value.name.trim() || value.name.trim().length > 60)
    return "连接名称需为 1–60 个字符。";
  if (!value.model.trim() || value.model.length > 200)
    return "请填写有效的演示模型名称（最多 200 字符）。";
  try {
    const u = new URL(value.endpoint);
    if (u.username || u.password || u.search || u.hash)
      return "基础地址不能包含认证信息、查询参数或片段。";
    if (
      u.protocol !== "https:" &&
      !(
        u.protocol === "http:" &&
        ["localhost", "127.0.0.1", "[::1]"].includes(u.hostname)
      )
    )
      return "请使用 HTTPS，或本地 HTTP 地址。";
    if (u.pathname.endsWith("/chat/completions"))
      return "填写基础地址即可，不要附加 /chat/completions。";
  } catch {
    return "请输入完整有效的基础地址。";
  }
  return null;
}
export function validateCommander(value: Commander): string | null {
  if (
    typeof value.name !== "string" ||
    !value.name.trim() ||
    value.name.trim().length > 24
  )
    return "指挥官名称需为 1–24 个字符。";
  if (typeof value.traits !== "string" || value.traits.length > 800)
    return "指挥偏好请限制在 800 字符以内。";
  if (
    typeof value.modelOverride !== "string" ||
    value.modelOverride.length > 200
  )
    return "模型名称不能超过 200 字符。";
  if (value.preferences !== undefined) {
    const error = validatePreferences(value.preferences);
    if (error) return error;
    const preset = preferencePresets.find(
      (p) => p.id === value.preferences?.preset,
    );
    if (preset && preset.doctrine !== value.doctrine)
      return "指挥人格与打法预设不一致，请重新选择预设。";
  }
  return null;
}
// Select fields explicitly: a credential accidentally added to a draft can never reach storage.
export function publicSettings(value: Settings): Settings {
  return {
    schemaVersion: 1,
    activeId: value.activeId,
    commanders: value.commanders.map((c) => ({
      id: c.id,
      name: c.name,
      callsign: c.callsign,
      doctrine: c.doctrine,
      traits: c.traits,
      connectionId: c.connectionId,
      modelOverride: c.modelOverride,
      revision: c.revision,
      preferences: profilePreferences(c),
    })),
    connections: value.connections.map((c) => ({
      id: c.id,
      name: c.name,
      provider: c.provider,
      endpoint: c.endpoint,
      model: c.model,
    })),
  };
}
export function loadSettings(
  storage: Pick<Storage, "getItem"> | undefined,
): Settings {
  try {
    const value = JSON.parse(storage?.getItem(storageKey) ?? "null");
    if (
      value?.schemaVersion !== 1 ||
      !Array.isArray(value.commanders) ||
      !Array.isArray(value.connections) ||
      value.commanders.length < 1 ||
      value.commanders.length > 20 ||
      value.connections.length < 1 ||
      value.connections.length > 20
    )
      throw Error();
    for (const c of value.connections)
      if (
        typeof c.id !== "string" ||
        !["OpenAI", "DeepSeek", "自定义"].includes(c.provider) ||
        validateConnection(c)
      )
        throw Error();
    for (const c of value.commanders)
      if (
        typeof c.id !== "string" ||
        typeof c.callsign !== "string" ||
        !Number.isInteger(c.revision) ||
        !Object.hasOwn(doctrineLabels, c.doctrine) ||
        validateCommander(c) ||
        !value.connections.some((x: Connection) => x.id === c.connectionId)
      )
        throw Error();
    if (!value.commanders.some((c: Commander) => c.id === value.activeId))
      throw Error();
    return publicSettings(value);
  } catch {
    return structuredClone(defaultSettings);
  }
}
export function saveSettings(
  storage: Pick<Storage, "setItem">,
  value: Settings,
) {
  const error = value.commanders.map(validateCommander).find(Boolean);
  if (error) throw new Error(error);
  storage.setItem(storageKey, JSON.stringify(publicSettings(value)));
}
