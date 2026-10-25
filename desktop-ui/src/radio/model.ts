export const radioEvents = {
  opening: {
    label: "开局问候",
    priority: 20,
    ttlMs: 30_000,
    text: "我已就位。先确认局势，再一起寻找突破口。",
  },
  crisis: {
    label: "危机提醒",
    priority: 100,
    ttlMs: 12_000,
    text: "先稳住阵线。我们重新确认威胁，再决定下一步。",
  },
  loss: {
    label: "重大损失",
    priority: 80,
    ttlMs: 20_000,
    text: "这次损失已经记下。保住剩余力量，我们还有调整的机会。",
  },
  rescue: {
    label: "成功解围",
    priority: 55,
    ttlMs: 25_000,
    text: "这一轮配合奏效了。先重新整队，再扩大优势。",
  },
  victory: {
    label: "胜利回应",
    priority: 40,
    ttlMs: 30_000,
    text: "战斗结束。感谢并肩作战，我们一起回看这一局。",
  },
  defeat: {
    label: "失利关怀",
    priority: 90,
    ttlMs: 30_000,
    text: "这一局结束了。休整一下，再一起复盘值得改进的地方。",
  },
} as const;

export type RadioEventKind = keyof typeof radioEvents;
export type RadioFrequency = "quiet" | "standard" | "active";
export interface RadioPreferences {
  frequency: RadioFrequency;
  volume: number;
  muted: boolean;
  subtitlesOnly: boolean;
}
export interface RadioClip {
  id: string;
  commanderId: string;
  title: string;
  event: RadioEventKind;
  text: string;
  mediaType: "subtitle" | "audio" | "video";
  blob?: Blob;
  durationSeconds?: number;
  createdAt: number;
  builtin?: boolean;
}
export const defaultRadioPreferences: RadioPreferences = {
  frequency: "standard",
  volume: 70,
  muted: false,
  subtitlesOnly: false,
};
export function sameRadioPreferences(
  a: RadioPreferences,
  b: RadioPreferences,
): boolean {
  return (
    a.frequency === b.frequency &&
    a.volume === b.volume &&
    a.muted === b.muted &&
    a.subtitlesOnly === b.subtitlesOnly
  );
}
export const MAX_CLIP_BYTES = 32 * 1024 * 1024;
export const MAX_LIBRARY_BYTES = 128 * 1024 * 1024;
export const MAX_LIBRARY_CLIPS = 24;
export const acceptedMediaTypes = [
  "video/mp4",
  "video/webm",
  "video/quicktime",
  "audio/mpeg",
  "audio/mp4",
  "audio/wav",
  "audio/x-wav",
  "audio/ogg",
  "audio/webm",
];
export function validPreferences(value: unknown): value is RadioPreferences {
  if (!value || typeof value !== "object") return false;
  const p = value as RadioPreferences;
  return (
    ["quiet", "standard", "active"].includes(p.frequency) &&
    Number.isFinite(p.volume) &&
    p.volume >= 0 &&
    p.volume <= 100 &&
    typeof p.muted === "boolean" &&
    typeof p.subtitlesOnly === "boolean"
  );
}
export function validateClip(clip: RadioClip): string | null {
  if (
    !clip ||
    typeof clip.id !== "string" ||
    !clip.id ||
    clip.id.length > 160 ||
    typeof clip.commanderId !== "string" ||
    !clip.commanderId ||
    clip.commanderId.length > 100 ||
    typeof clip.title !== "string" ||
    !clip.title.trim() ||
    clip.title.length > 60
  )
    return "素材名称需为 1–60 个字符。";
  if (!Object.hasOwn(radioEvents, clip.event)) return "请选择有效的战况事件。";
  if (
    typeof clip.text !== "string" ||
    !clip.text.trim() ||
    clip.text.length > 300
  )
    return "请填写 1–300 字的字幕。";
  if (!["subtitle", "audio", "video"].includes(clip.mediaType))
    return "不支持的素材类型。";
  if (!Number.isFinite(clip.createdAt) || clip.createdAt < 0)
    return "素材记录的时间无效。";
  if (clip.mediaType !== "subtitle") {
    if (
      !(clip.blob instanceof Blob) ||
      !acceptedMediaTypes.includes(clip.blob.type) ||
      clip.blob.size === 0 ||
      clip.blob.size > MAX_CLIP_BYTES
    )
      return "请选择支持的视频或音频，单条不超过 32 MB。";
    if (!clip.blob.type.startsWith(`${clip.mediaType}/`))
      return "素材类型与文件不一致。";
    if (
      !Number.isFinite(clip.durationSeconds) ||
      clip.durationSeconds! <= 0 ||
      clip.durationSeconds! > 90
    )
      return "通讯片段需在 90 秒以内，并且能读取有效时长。";
  }
  return null;
}
export function validateLibraryAddition(
  existing: readonly RadioClip[],
  clip: RadioClip,
): string | null {
  const error = validateClip(clip);
  if (error) return error;
  const others = existing.filter((c) => c.id !== clip.id && !c.builtin);
  if (others.length >= MAX_LIBRARY_CLIPS)
    return "每位指挥官最多保存 24 条本地素材，请先删除部分内容。";
  if (
    others.reduce((sum, c) => sum + (c.blob?.size ?? 0), 0) +
      (clip.blob?.size ?? 0) >
    MAX_LIBRARY_BYTES
  )
    return "该指挥官素材总量不能超过 128 MB。";
  return null;
}
export function builtinClips(commanderId: string): RadioClip[] {
  return (Object.keys(radioEvents) as RadioEventKind[]).map((event) => ({
    id: `example-${commanderId}-${event}`,
    commanderId,
    title: `${radioEvents[event].label} · 示例字幕`,
    event,
    text: radioEvents[event].text,
    mediaType: "subtitle",
    createdAt: 0,
    builtin: true,
  }));
}
