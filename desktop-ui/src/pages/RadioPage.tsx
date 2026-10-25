import { useEffect, useRef, useState } from "react";
import {
  Broadcast,
  CheckCircle,
  FilmStrip,
  FloppyDisk,
  Headphones,
  Pause,
  Play,
  Plus,
  SkipForward,
  SpeakerHigh,
  SpeakerSlash,
  Subtitles,
  Trash,
  UploadSimple,
  WarningCircle,
} from "@phosphor-icons/react";
import { Button, PageHeading, PanelHeading } from "../components/ui";
import {
  acceptedMediaTypes,
  builtinClips,
  defaultRadioPreferences,
  MAX_CLIP_BYTES,
  radioEvents,
  sameRadioPreferences,
  validateLibraryAddition,
  type RadioClip,
  type RadioEventKind,
  type RadioPreferences,
} from "../radio/model";
import {
  advanceRadio,
  createRadioSchedule,
  discardClip,
  enqueueRadio,
  type RadioDelivery,
} from "../radio/scheduler";
import {
  deleteRadioClip,
  loadRadioLibrary,
  readMediaDuration,
  saveRadioClip,
  saveRadioPreferences,
} from "../radio/storage";
import "./radio.css";

function useVisible() {
  const [visible, setVisible] = useState(
    () => document.visibilityState !== "hidden",
  );
  useEffect(() => {
    const change = () => setVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", change);
    return () => document.removeEventListener("visibilitychange", change);
  }, []);
  return visible;
}

function RadioPlayer({
  delivery,
  preferences,
  active,
  onFinished,
}: {
  delivery: RadioDelivery | null;
  preferences: RadioPreferences;
  active: boolean;
  onFinished: () => void;
}) {
  const [paused, setPaused] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [mediaFailed, setMediaFailed] = useState(false);
  const [source, setSource] = useState<{ id: string; url: string } | null>(
    null,
  );
  const url = source?.id === delivery?.id ? source?.url : null;
  const media = useRef<HTMLMediaElement | null>(null);
  const finished = useRef(onFinished);
  finished.current = onFinished;
  const currentDelivery = useRef(delivery?.id);
  currentDelivery.current = delivery?.id;
  const visible = useVisible();
  const allowed = active && visible;
  const playbackAllowed = useRef(allowed);
  playbackAllowed.current = allowed;
  const subtitleMode =
    preferences.subtitlesOnly ||
    delivery?.clip.mediaType === "subtitle" ||
    mediaFailed;
  const remaining = useRef(6000);
  useEffect(() => {
    setPaused(false);
    setBlocked(false);
    setMediaFailed(false);
    remaining.current = Math.min(
      15_000,
      Math.max(5000, (delivery?.clip.text.length ?? 0) * 130),
    );
  }, [delivery?.id]);
  useEffect(() => {
    if (
      !allowed ||
      !delivery?.clip.blob ||
      preferences.subtitlesOnly ||
      mediaFailed
    ) {
      setSource(null);
      return;
    }
    const next = URL.createObjectURL(delivery.clip.blob);
    setSource({ id: delivery.id, url: next });
    return () => {
      URL.revokeObjectURL(next);
    };
  }, [
    delivery?.id,
    delivery?.clip.blob,
    allowed,
    preferences.subtitlesOnly,
    mediaFailed,
  ]);
  useEffect(() => {
    const element = media.current;
    if (!element || !url) return;
    element.volume = preferences.volume / 100;
    element.muted = preferences.muted;
  }, [url, preferences.volume, preferences.muted]);
  useEffect(() => {
    const element = media.current;
    if (!element || !url) return;
    let canceled = false;
    if (paused || !allowed) element.pause();
    else
      void element
        .play()
        .then(() => {
          if (!canceled) setBlocked(false);
        })
        .catch(() => {
          if (!canceled) setBlocked(true);
        });
    return () => {
      canceled = true;
      element.pause();
    };
  }, [url, delivery?.id, paused, allowed]);
  useEffect(() => {
    if (!delivery || !allowed || paused || !subtitleMode) return;
    const started = Date.now();
    const timer = setTimeout(() => finished.current(), remaining.current);
    return () => {
      clearTimeout(timer);
      remaining.current = Math.max(
        0,
        remaining.current - (Date.now() - started),
      );
    };
  }, [delivery?.id, allowed, paused, subtitleMode]);
  async function toggle() {
    if (blocked && media.current) {
      const id = delivery?.id;
      try {
        await media.current.play();
        if (currentDelivery.current !== id || !playbackAllowed.current) return;
        setBlocked(false);
        setPaused(false);
      } catch {
        if (currentDelivery.current === id && playbackAllowed.current)
          setBlocked(true);
      }
    } else setPaused(!paused);
  }
  return (
    <section className="panel radio-player" aria-label="本地电台播放器">
      <PanelHeading eyebrow="LOCAL TRANSMISSION" title="通讯预览">
        <span className="tiny-pill">本地预览</span>
      </PanelHeading>
      <div className={`radio-screen ${delivery ? "has-transmission" : ""}`}>
        {delivery && url && !subtitleMode ? (
          delivery.clip.mediaType === "video" ? (
            <video
              key={delivery.id}
              ref={(node) => {
                media.current = node;
              }}
              src={url}
              playsInline
              preload="metadata"
              onEnded={() => {
                if (
                  currentDelivery.current === delivery.id &&
                  playbackAllowed.current
                )
                  finished.current();
              }}
              onError={() => {
                if (
                  currentDelivery.current === delivery.id &&
                  playbackAllowed.current
                )
                  setMediaFailed(true);
              }}
            />
          ) : (
            <>
              <Headphones size={64} weight="duotone" aria-hidden="true" />
              <audio
                key={delivery.id}
                ref={(node) => {
                  media.current = node;
                }}
                src={url}
                preload="metadata"
                onEnded={() => {
                  if (
                    currentDelivery.current === delivery.id &&
                    playbackAllowed.current
                  )
                    finished.current();
                }}
                onError={() => {
                  if (
                    currentDelivery.current === delivery.id &&
                    playbackAllowed.current
                  )
                    setMediaFailed(true);
                }}
              />
            </>
          )
        ) : (
          <Broadcast size={64} weight="duotone" aria-hidden="true" />
        )}
        <span className="radio-screen-label">
          {delivery ? radioEvents[delivery.event].label : "等待接入"}
        </span>
        {delivery && (
          <span className="radio-origin-label">
            {delivery.origin === "audition" ? "素材试听" : "场景演练"} /
            非游戏来电
          </span>
        )}
      </div>
      <div className="radio-caption" aria-live="polite">
        <strong>
          {delivery?.clip.title ?? "先试听素材，或触发一个演练场景。"}
        </strong>
        <p>
          {delivery?.clip.text ??
            "没有游戏事件接入。这里的每次通讯都由你主动预览。"}
        </p>
        {delivery && (
          <small>
            {mediaFailed
              ? "媒体无法播放，已降为字幕。"
              : !allowed
                ? "页面未显示，播放已暂停。"
                : blocked
                  ? "浏览器暂未允许播放，请点击继续。"
                  : paused
                    ? "已暂停"
                    : subtitleMode
                      ? "字幕播放中"
                      : "本机媒体播放中"}
          </small>
        )}
      </div>
      <div className="radio-player-controls">
        <Button onClick={() => void toggle()} disabled={!delivery || !allowed}>
          {paused || blocked ? <Play size={16} /> : <Pause size={16} />}{" "}
          {paused || blocked ? "继续播放" : "暂停播放"}
        </Button>
        <Button onClick={onFinished} disabled={!delivery}>
          <SkipForward size={16} />
          跳过通讯
        </Button>
      </div>
    </section>
  );
}

export function RadioPage({
  commander,
  session,
  active = true,
}: {
  commander: { id: string; name: string };
  session: { id: string; state: string } | null;
  active?: boolean;
}) {
  const scope = `${commander.id}:${session?.id ?? "local-preview"}`;
  const [clips, setClips] = useState<RadioClip[]>([]);
  const [preferences, setPreferences] = useState<RadioPreferences>({
    ...defaultRadioPreferences,
  });
  const [preferenceDirty, setPreferenceDirty] = useState(false);
  const [savingPreferences, setSavingPreferences] = useState(false);
  const currentPreferences = useRef(preferences);
  const preferenceSavePending = useRef(false);
  const [storageState, setStorageState] = useState<
    "loading" | "saved" | "memory"
  >("loading");
  const [schedule, setSchedule] = useState(() => createRadioSchedule(scope));
  const [message, setMessage] = useState("选择场景，预览指挥官会怎样联系你。");
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [event, setEvent] = useState<RadioEventKind>("opening");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState<"all" | RadioEventKind>("all");
  const generation = useRef(0);
  const importer = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const visible = useVisible();
  const allClips = [
    ...clips.filter((clip) => clip.commanderId === commander.id),
    ...builtinClips(commander.id),
  ];
  useEffect(() => {
    const version = ++generation.current;
    importer.current?.abort();
    setBusy(false);
    setClips([]);
    setPreferences({ ...defaultRadioPreferences });
    currentPreferences.current = { ...defaultRadioPreferences };
    preferenceSavePending.current = false;
    setSavingPreferences(false);
    setPreferenceDirty(false);
    setStorageState("loading");
    setTitle("");
    setSubtitle("");
    setFile(null);
    if (fileInput.current) fileInput.current.value = "";
    void loadRadioLibrary(commander.id)
      .then((value) => {
        if (generation.current !== version) return;
        setClips(value.clips);
        setPreferences(value.preferences);
        currentPreferences.current = value.preferences;
        setStorageState("saved");
      })
      .catch(() => {
        if (generation.current !== version) return;
        setStorageState("memory");
        setMessage("本机素材存储不可用，内容只保留在当前窗口；刷新后会丢失。");
      });
    return () => {
      ++generation.current;
      importer.current?.abort();
    };
  }, [commander.id]);
  useEffect(() => {
    setSchedule(createRadioSchedule(scope));
    setMessage("会话已切换，旧通讯与排队内容已清除。");
  }, [scope]);
  useEffect(() => {
    if (
      session?.state === "stopping" ||
      session?.state === "stopped" ||
      session?.state === "fault"
    )
      setSchedule(createRadioSchedule(scope));
  }, [session?.state, scope]);
  useEffect(() => {
    if (!active || !visible) setSchedule((value) => ({ ...value, queue: [] }));
    else
      setSchedule((value) =>
        value.current && value.current.expiresAt <= Date.now()
          ? { ...value, current: null, queue: [] }
          : value,
      );
  }, [active, visible]);
  function changePreferences(patch: Partial<RadioPreferences>) {
    const next = { ...currentPreferences.current, ...patch };
    currentPreferences.current = next;
    setPreferences(next);
    setPreferenceDirty(true);
  }
  async function persistPreferences() {
    if (preferenceSavePending.current) return;
    const version = generation.current;
    const saved = { ...currentPreferences.current };
    preferenceSavePending.current = true;
    setSavingPreferences(true);
    try {
      await saveRadioPreferences(commander.id, saved);
      if (version === generation.current) {
        const unchanged = sameRadioPreferences(
          saved,
          currentPreferences.current,
        );
        setPreferenceDirty(!unchanged);
        setMessage(
          unchanged
            ? "通讯偏好已保存至本机。素材仍只在本机使用。"
            : "先前版本已保存；刚刚修改的通讯偏好仍未保存。",
        );
      }
    } catch {
      if (version === generation.current)
        setMessage("通讯设置尚未保存；当前窗口仍按所选设置预览。");
    } finally {
      if (version === generation.current) {
        preferenceSavePending.current = false;
        setSavingPreferences(false);
      }
    }
  }
  function play(clip: RadioClip, origin: "scenario" | "audition") {
    if (clip.commanderId !== commander.id) return;
    const result = enqueueRadio(
      schedule,
      scope,
      clip,
      preferences,
      Date.now(),
      origin,
    );
    setSchedule(result.state);
    setMessage(result.message);
  }
  function scenario(kind: RadioEventKind) {
    const clip = allClips.find((c) => c.event === kind)!;
    play(clip, "scenario");
  }
  function finish(id?: string) {
    setSchedule((value) =>
      id && value.current?.id !== id ? value : advanceRadio(value, Date.now()),
    );
  }
  async function addClip() {
    const version = generation.current;
    const owner = commander.id;
    if (busy || storageState === "loading") return;
    if (
      file &&
      (!acceptedMediaTypes.includes(file.type) ||
        file.size === 0 ||
        file.size > MAX_CLIP_BYTES)
    ) {
      setMessage("请选择支持的本地媒体，单条不超过 32 MB。");
      return;
    }
    const controller = new AbortController();
    importer.current = controller;
    setBusy(true);
    try {
      const durationSeconds = file
        ? await readMediaDuration(file, controller.signal)
        : undefined;
      if (version !== generation.current || controller.signal.aborted) return;
      const clip: RadioClip = {
        id: crypto.randomUUID(),
        commanderId: owner,
        title: title.trim(),
        event,
        text: subtitle.trim(),
        mediaType: file
          ? file.type.startsWith("video/")
            ? "video"
            : "audio"
          : "subtitle",
        blob: file ?? undefined,
        durationSeconds,
        createdAt: Date.now(),
      };
      const error = validateLibraryAddition(clips, clip);
      if (error) {
        setMessage(error);
        return;
      }
      let persisted = true;
      try {
        await saveRadioClip(clip);
      } catch {
        persisted = false;
      }
      if (version !== generation.current) return;
      setClips((value) => [clip, ...value]);
      setTitle("");
      setSubtitle("");
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      if (!persisted) setStorageState("memory");
      setMessage(
        persisted
          ? "素材已保存至本机；未上传，也未发送到游戏。"
          : "本机保存失败；素材仅保留在当前窗口，刷新后会丢失。",
      );
    } catch (error) {
      if (version === generation.current)
        setMessage(error instanceof Error ? error.message : "素材导入未完成。");
    } finally {
      if (version === generation.current) setBusy(false);
      if (importer.current === controller) importer.current = null;
    }
  }
  async function remove(clip: RadioClip) {
    const version = generation.current;
    let deleted = true;
    try {
      await deleteRadioClip(clip.id);
    } catch {
      deleted = false;
    }
    if (generation.current !== version) return;
    setClips((value) => value.filter((c) => c.id !== clip.id));
    setSchedule((value) => discardClip(value, clip.id, Date.now()));
    if (!deleted) setStorageState("memory");
    setMessage(
      deleted
        ? "本机素材已删除。"
        : "素材已从当前窗口移除，但本机删除失败；刷新后可能重新出现。",
    );
  }
  return (
    <div className="radio-workspace">
      <PageHeading
        eyebrow="COMMANDER RADIO / 战场电台"
        title="每次联系，都恰逢其时。"
        description={`为${commander.name}准备本机通讯素材，试听不同战况下的回应。当前没有游戏电台桥接。`}
      >
        <span className="tiny-pill">素材与偏好按指挥官保存</span>
      </PageHeading>
      <div
        className={`radio-storage-status ${storageState === "memory" ? "warning" : ""}`}
        role="status"
      >
        {storageState === "saved" ? (
          <CheckCircle size={16} />
        ) : (
          <WarningCircle size={16} />
        )}
        <span>
          {storageState === "loading"
            ? "正在读取本机素材库…"
            : storageState === "memory"
              ? "窗口内模式 · 部分内容未持久保存"
              : "本机素材库已就绪 · 不上传文件"}
        </span>
      </div>
      <div className="radio-grid">
        <div className="radio-main-column">
          <RadioPlayer
            delivery={schedule.scope === scope ? schedule.current : null}
            preferences={preferences}
            active={active}
            onFinished={() => finish(schedule.current?.id)}
          />
          <section className="panel radio-scenarios">
            <PanelHeading eyebrow="SCENARIO PREVIEW" title="演练一次战况" />
            <p className="subtle">
              手动触发本地预览。优先使用该事件的最新自定义素材；没有素材时播放示例字幕。
            </p>
            <div className="radio-scenario-buttons">
              {(Object.keys(radioEvents) as RadioEventKind[]).map((kind) => (
                <button
                  key={kind}
                  type="button"
                  disabled={storageState === "loading"}
                  onClick={() => scenario(kind)}
                >
                  <Broadcast size={16} />
                  <span>{radioEvents[kind].label}</span>
                  <small>
                    {radioEvents[kind].priority >= 80 ? "优先接入" : "场景预览"}
                  </small>
                </button>
              ))}
            </div>
            <div className="radio-live-message" role="status">
              {message}
            </div>
            <div className="radio-queue">
              <span>待接入 {schedule.queue.length} / 6</span>
              {schedule.queue.length > 0 ? (
                <ol>
                  {schedule.queue.map((item) => (
                    <li key={item.id}>{item.clip.title}</li>
                  ))}
                </ol>
              ) : (
                <small>无排队通讯。高优先级事件可打断当前片段。</small>
              )}
            </div>
          </section>
        </div>
        <section className="panel radio-preferences">
          <PanelHeading eyebrow="COMMUNICATION STYLE" title="通讯偏好" />
          <p className="subtle">只影响电台表达，不改变战术偏好或模型决策。</p>
          <fieldset disabled={storageState === "loading"}>
            <label>
              通讯频率
              <select
                value={preferences.frequency}
                onChange={(e) =>
                  changePreferences({
                    frequency: e.target.value as RadioPreferences["frequency"],
                  })
                }
              >
                <option value="quiet">安静作战 · 关键提醒</option>
                <option value="standard">标准陪伴 · 适度关怀</option>
                <option value="active">活跃电台 · 更多回应</option>
              </select>
            </label>
            <small className="radio-help">
              同类事件冷却：
              {preferences.frequency === "quiet"
                ? "120"
                : preferences.frequency === "standard"
                  ? "45"
                  : "15"}{" "}
              秒。安静模式略过开场与解围氛围通讯。
            </small>
            <label className="radio-volume">
              <span>
                <SpeakerHigh size={17} />
                播放音量 <output>{preferences.volume}%</output>
              </span>
              <input
                aria-label="播放音量"
                type="range"
                min={0}
                max={100}
                step={5}
                value={preferences.volume}
                onChange={(e) =>
                  changePreferences({ volume: Number(e.target.value) })
                }
              />
            </label>
            <label className="radio-toggle">
              <input
                type="checkbox"
                checked={preferences.muted}
                onChange={(e) => changePreferences({ muted: e.target.checked })}
              />
              <SpeakerSlash size={18} />
              <span>静音播放</span>
            </label>
            <label className="radio-toggle">
              <input
                type="checkbox"
                checked={preferences.subtitlesOnly}
                onChange={(e) =>
                  changePreferences({ subtitlesOnly: e.target.checked })
                }
              />
              <Subtitles size={18} />
              <span>仅字幕，不解码媒体</span>
            </label>
          </fieldset>
          <Button
            kind="primary"
            onClick={() => void persistPreferences()}
            disabled={
              !preferenceDirty ||
              storageState === "loading" ||
              savingPreferences
            }
            loading={savingPreferences}
          >
            <FloppyDisk size={16} />
            保存通讯设置
          </Button>
          <div className="radio-boundaries">
            <strong>通讯编排规则</strong>
            <ul>
              <li>危机可打断开场和闲聊。</li>
              <li>重复事件合并，同类事件有冷却。</li>
              <li>战况反转后丢弃过期庆祝。</li>
              <li>换会话或停止演练后清空通讯。</li>
              <li>页面隐藏时停止媒体解码。</li>
            </ul>
          </div>
        </section>
      </div>
      <section className="panel radio-library">
        <PanelHeading
          eyebrow="LOCAL MEDIA LIBRARY"
          title={`${commander.name}的通讯素材`}
        >
          <span className="tiny-pill">{clips.length} / 24 自定义</span>
        </PanelHeading>
        <div className="radio-library-layout">
          <div className="radio-import">
            <h3>
              <UploadSimple size={19} />
              添加本地素材
            </h3>
            <p className="subtle">
              可选视频或音频；留空则建立字幕通讯。支持单条 32 MB / 90
              秒，每位指挥官总量 128 MB。
            </p>
            <fieldset disabled={busy || storageState === "loading"}>
              <label>
                素材名称
                <input
                  value={title}
                  maxLength={60}
                  placeholder="例如：逆风时的鼓励"
                  onChange={(e) => setTitle(e.target.value)}
                />
              </label>
              <label>
                适用战况
                <select
                  value={event}
                  onChange={(e) => setEvent(e.target.value as RadioEventKind)}
                >
                  {(Object.keys(radioEvents) as RadioEventKind[]).map(
                    (kind) => (
                      <option key={kind} value={kind}>
                        {radioEvents[kind].label}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label>
                字幕内容
                <textarea
                  rows={3}
                  value={subtitle}
                  maxLength={300}
                  placeholder="填写片段台词，或作为纯字幕通讯。"
                  onChange={(e) => setSubtitle(e.target.value)}
                />
                <small>{subtitle.length} / 300 字</small>
              </label>
              <label className="radio-file-input">
                视频或音频（可选）
                <input
                  ref={fileInput}
                  type="file"
                  accept={acceptedMediaTypes.join(",")}
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </label>
            </fieldset>
            <Button
              kind="primary"
              onClick={() => void addClip()}
              loading={busy}
              disabled={storageState === "loading"}
            >
              <Plus size={16} />{" "}
              {busy ? "正在读取素材" : file ? "导入本机素材" : "添加字幕通讯"}
            </Button>
            {busy && (
              <Button onClick={() => importer.current?.abort()}>
                取消导入
              </Button>
            )}
          </div>
          <div className="radio-clip-list">
            <label className="radio-filter">
              筛选战况
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value as typeof filter)}
              >
                <option value="all">全部战况</option>
                {(Object.keys(radioEvents) as RadioEventKind[]).map((kind) => (
                  <option key={kind} value={kind}>
                    {radioEvents[kind].label}
                  </option>
                ))}
              </select>
            </label>
            {allClips
              .filter((clip) => filter === "all" || clip.event === filter)
              .map((clip) => (
                <article className="radio-clip" key={clip.id}>
                  <div className="radio-clip-icon">
                    {clip.mediaType === "video" ? (
                      <FilmStrip size={22} />
                    ) : clip.mediaType === "audio" ? (
                      <Headphones size={22} />
                    ) : (
                      <Subtitles size={22} />
                    )}
                  </div>
                  <div className="radio-clip-copy">
                    <strong>{clip.title}</strong>
                    <small>
                      {radioEvents[clip.event].label} ·{" "}
                      {clip.builtin
                        ? "内置示例 / 仅字幕"
                        : clip.mediaType === "subtitle"
                          ? "自定义字幕"
                          : `${clip.mediaType === "video" ? "视频" : "音频"} / ${Math.ceil(clip.durationSeconds ?? 0)} 秒 / ${((clip.blob?.size ?? 0) / 1024 / 1024).toFixed(1)} MB`}
                    </small>
                    <p>{clip.text}</p>
                  </div>
                  <div className="radio-clip-actions">
                    <button
                      className="icon-button"
                      aria-label={`试听：${clip.title}`}
                      title="仅本机试听"
                      onClick={() => play(clip, "audition")}
                    >
                      <Play size={18} />
                    </button>
                    {!clip.builtin && (
                      <button
                        className="icon-button"
                        aria-label={`删除：${clip.title}`}
                        onClick={() => void remove(clip)}
                      >
                        <Trash size={18} />
                      </button>
                    )}
                  </div>
                </article>
              ))}
          </div>
        </div>
      </section>
    </div>
  );
}
