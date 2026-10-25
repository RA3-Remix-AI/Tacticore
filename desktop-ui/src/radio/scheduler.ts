import {
  radioEvents,
  type RadioClip,
  type RadioEventKind,
  type RadioPreferences,
} from "./model";

export interface RadioDelivery {
  id: string;
  scope: string;
  event: RadioEventKind;
  clip: RadioClip;
  createdAt: number;
  expiresAt: number;
  origin: "scenario" | "audition";
}
export interface RadioSchedule {
  scope: string;
  epoch: number;
  current: RadioDelivery | null;
  queue: readonly RadioDelivery[];
  lastPlayed: Readonly<Partial<Record<RadioEventKind, number>>>;
  sequence: number;
}
let scheduleEpoch = 0;
export interface ScheduleResult {
  state: RadioSchedule;
  message: string;
  accepted: boolean;
}
export function createRadioSchedule(scope: string): RadioSchedule {
  return {
    scope,
    epoch: ++scheduleEpoch,
    current: null,
    queue: [],
    lastPlayed: {},
    sequence: 0,
  };
}
export function advanceRadio(state: RadioSchedule, now: number): RadioSchedule {
  const queue = state.queue.filter(
    (x) => x.scope === state.scope && x.expiresAt > now,
  );
  const [current, ...rest] = queue;
  return {
    ...state,
    current: current ?? null,
    queue: rest,
    lastPlayed: current
      ? { ...state.lastPlayed, [current.event]: now }
      : state.lastPlayed,
  };
}
export function discardClip(
  state: RadioSchedule,
  id: string,
  now: number,
): RadioSchedule {
  const next = { ...state, queue: state.queue.filter((x) => x.clip.id !== id) };
  return next.current?.clip.id === id ? advanceRadio(next, now) : next;
}
export function enqueueRadio(
  state: RadioSchedule,
  scope: string,
  clip: RadioClip,
  preferences: RadioPreferences,
  now: number,
  origin: RadioDelivery["origin"] = "scenario",
): ScheduleResult {
  if (scope !== state.scope)
    return { state, message: "旧会话通讯已忽略。", accepted: false };
  const event = clip.event;
  if (!Object.hasOwn(radioEvents, event))
    return { state, message: "未知事件已忽略。", accepted: false };
  // A changed battlefield invalidates celebration even when the new notice is
  // suppressed by cooldown. Reconcile facts before deciding whether to speak.
  const reversal = event === "crisis" || event === "loss" || event === "defeat";
  let current =
    state.current && state.current.expiresAt > now ? state.current : null;
  let queue = state.queue.filter(
    (x) =>
      x.expiresAt > now &&
      x.scope === scope &&
      !(reversal && ["victory", "rescue"].includes(x.event)),
  );
  if (reversal && current && ["victory", "rescue"].includes(current.event)) {
    current = null;
    queue = [];
  }
  if (!current) queue = [];
  state = { ...state, current, queue };
  const cooldown = { quiet: 120_000, standard: 45_000, active: 15_000 }[
    preferences.frequency
  ];
  if (origin === "scenario") {
    if (
      preferences.frequency === "quiet" &&
      (event === "opening" || event === "rescue")
    )
      return {
        state,
        message: "安静作战已略过氛围通讯，可直接试听素材。",
        accepted: false,
      };
    if (
      state.current?.event === event ||
      state.queue.some((x) => x.event === event)
    )
      return {
        state,
        message: "相同事件已经在播放或排队，已合并。",
        accepted: false,
      };
    const previous = state.lastPlayed[event];
    if (previous !== undefined && now - previous < cooldown)
      return {
        state,
        message: "该类事件仍在冷却，已略过重复通讯。",
        accepted: false,
      };
  }
  const delivery: RadioDelivery = {
    id: `${state.scope}-${state.epoch}-${state.sequence + 1}`,
    scope,
    event,
    clip,
    createdAt: now,
    expiresAt: now + radioEvents[event].ttlMs,
    origin,
  };
  const terminal = event === "victory" || event === "defeat";
  const interrupt =
    origin === "audition" ||
    terminal ||
    !current ||
    radioEvents[event].priority > radioEvents[current.event].priority;
  if (interrupt) {
    return {
      state: {
        ...state,
        current: delivery,
        queue: terminal || origin === "audition" ? [] : queue,
        sequence: state.sequence + 1,
        lastPlayed:
          origin === "scenario"
            ? { ...state.lastPlayed, [event]: now }
            : state.lastPlayed,
      },
      message:
        origin === "audition"
          ? "正在本地试听，不会向游戏发送通讯。"
          : current
            ? "高优先级通讯已接入，原片段不再续播。"
            : "本地场景通讯已接入。",
      accepted: true,
    };
  }
  if (queue.length >= 6)
    return {
      state,
      message: "通讯队列已满，已略过低优先级片段。",
      accepted: false,
    };
  queue = [...queue, delivery].sort(
    (a, b) =>
      radioEvents[b.event].priority - radioEvents[a.event].priority ||
      a.createdAt - b.createdAt,
  );
  return {
    state: { ...state, current, queue, sequence: state.sequence + 1 },
    message: "通讯已排队，将在当前片段结束后接入。",
    accepted: true,
  };
}
