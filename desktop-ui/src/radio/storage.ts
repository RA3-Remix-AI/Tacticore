import {
  defaultRadioPreferences,
  validPreferences,
  validateClip,
  validateLibraryAddition,
  type RadioClip,
  type RadioPreferences,
} from "./model";

const DATABASE = "tacticore-radio-v1";
function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined")
      return reject(new Error("本地素材存储不可用。"));
    const request = indexedDB.open(DATABASE, 1);
    let finished = false;
    const fail = (message: string) => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      reject(new Error(message));
    };
    const timeout = setTimeout(
      () => fail("本机素材库未响应，暂用窗口内模式。"),
      6000,
    );
    request.onupgradeneeded = () => {
      const db = request.result;
      const clips = db.createObjectStore("clips", { keyPath: "id" });
      clips.createIndex("commanderId", "commanderId");
      db.createObjectStore("preferences", { keyPath: "commanderId" });
    };
    request.onsuccess = () => {
      if (finished) {
        request.result.close();
        return;
      }
      finished = true;
      clearTimeout(timeout);
      resolve(request.result);
    };
    request.onerror = () => fail("无法打开本机素材库。");
    request.onblocked = () =>
      fail("素材库被其他窗口占用，请关闭其他窗口后重试。");
  });
}
export async function loadRadioLibrary(
  commanderId: string,
): Promise<{ clips: RadioClip[]; preferences: RadioPreferences }> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(["clips", "preferences"], "readonly");
    const clipsRequest = tx
      .objectStore("clips")
      .index("commanderId")
      .getAll(commanderId);
    const preferencesRequest = tx.objectStore("preferences").get(commanderId);
    tx.oncomplete = () => {
      db.close();
      const value = preferencesRequest.result?.value;
      resolve({
        clips: (clipsRequest.result as RadioClip[])
          .filter((c) => !validateClip(c) && c.commanderId === commanderId)
          .sort((a, b) => b.createdAt - a.createdAt),
        preferences: validPreferences(value)
          ? value
          : { ...defaultRadioPreferences },
      });
    };
    tx.onerror = tx.onabort = () => {
      db.close();
      reject(new Error("读取本机素材失败。"));
    };
  });
}
export async function saveRadioClip(clip: RadioClip): Promise<void> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("clips", "readwrite");
    const store = tx.objectStore("clips");
    const request = store.index("commanderId").getAll(clip.commanderId);
    let validation: string | null = null;
    request.onsuccess = () => {
      validation = validateLibraryAddition(request.result, clip);
      if (validation) tx.abort();
      else store.put(clip);
    };
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = tx.onabort = () => {
      db.close();
      reject(new Error(validation ?? "保存素材失败，可能是本机存储空间不足。"));
    };
  });
}
export async function deleteRadioClip(id: string): Promise<void> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("clips", "readwrite");
    tx.objectStore("clips").delete(id);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = tx.onabort = () => {
      db.close();
      reject(new Error("本机素材删除失败。"));
    };
  });
}
export async function saveRadioPreferences(
  commanderId: string,
  value: RadioPreferences,
): Promise<void> {
  if (!validPreferences(value)) throw new Error("通讯设置无效。");
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("preferences", "readwrite");
    tx.objectStore("preferences").put({
      commanderId,
      value: {
        frequency: value.frequency,
        volume: value.volume,
        muted: value.muted,
        subtitlesOnly: value.subtitlesOnly,
      },
    });
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = tx.onabort = () => {
      db.close();
      reject(new Error("通讯设置尚未保存，请重试。"));
    };
  });
}

export function readMediaDuration(
  file: File,
  signal?: AbortSignal,
): Promise<number> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const media = document.createElement(
      file.type.startsWith("video/") ? "video" : "audio",
    );
    const clean = () => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
      media.onloadedmetadata = null;
      media.onerror = null;
      media.removeAttribute("src");
      media.load();
      URL.revokeObjectURL(url);
    };
    const fail = (message: string) => {
      clean();
      reject(new Error(message));
    };
    const abort = () => fail("素材导入已取消。");
    const timer = setTimeout(
      () => fail("读取媒体超时，请换一个本机可播放的短片段。"),
      12_000,
    );
    if (signal?.aborted) return abort();
    signal?.addEventListener("abort", abort, { once: true });
    media.preload = "metadata";
    media.onloadedmetadata = () => {
      const duration = media.duration;
      clean();
      if (!Number.isFinite(duration) || duration <= 0 || duration > 90)
        reject(new Error("通讯片段需有有效时长，且不超过 90 秒。"));
      else resolve(duration);
    };
    media.onerror = () =>
      fail("本机无法读取此媒体，请使用可播放的 MP4、WebM 或音频文件。");
    media.src = url;
    media.load();
  });
}
