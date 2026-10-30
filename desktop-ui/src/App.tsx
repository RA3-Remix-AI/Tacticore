import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  ArrowSquareOut,
  CheckCircle,
  Circuitry,
  Crosshair,
  Flask,
  Flag,
  Broadcast,
  Info,
  Key,
  LinkBreak,
  List,
  PlugsConnected,
  ShieldCheck,
  UsersThree,
  Warning,
  X,
} from "@phosphor-icons/react";
import {
  createDemoRuntime,
  type DemoScenario,
  type OperationResult,
} from "./runtime";
import { Button, Modal } from "./components/ui";
import { OperationsPage, stateLabels } from "./pages/OperationsPage";
import { CommandersPage } from "./pages/CommandersPage";
import { ConnectionsPage } from "./pages/ConnectionsPage";
import { RecordsPage } from "./pages/RecordsPage";
import { PreparationPage } from "./pages/PreparationPage";
import { RadioPage } from "./pages/RadioPage";
import NativeApp from './NativeApp';
import { nativeAvailable } from './runtime/nativeRpc';
import {
  loadSettings,
  saveSettings,
  validateCommander,
  validateConnection,
  type Commander,
  type Connection,
  type Settings,
} from "./state/settings";
function availableStorage() {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}
const initial = loadSettings(availableStorage());
const first = initial.commanders.find((c) => c.id === initial.activeId)!;
// Module-scoped runtime survives StrictMode's effect rehearsal. It only simulates in memory.
const runtime = createDemoRuntime({
  profile: { id: first.id, name: first.name, revision: first.revision },
});
if (import.meta.hot) {
  // The session provider owns timers and must not survive a component-only refresh.
  // Reload this boundary so preserved React state never calls a disposed provider.
  import.meta.hot.accept(() => {
    document.documentElement.dataset.devReloading = "true";
    window.location.reload();
  });
  import.meta.hot.dispose(() => {
    document.documentElement.dataset.devReloading = "true";
    runtime.dispose();
  });
}
const pages = [
  { id: "preparation", label: "战前备战", english: "PREPARATION", icon: Flag },
  {
    id: "operations",
    label: "作战中心",
    english: "OPERATIONS",
    icon: Crosshair,
  },
  {
    id: "commanders",
    label: "指挥官工坊",
    english: "COMMANDERS",
    icon: UsersThree,
  },
  { id: "radio", label: "战场电台", english: "RADIO", icon: Broadcast },
  {
    id: "connections",
    label: "模型连接",
    english: "CONNECTIONS",
    icon: PlugsConnected,
  },
  { id: "records", label: "演练与记录", english: "SIMULATION", icon: Flask },
] as const;
type Page = (typeof pages)[number]["id"];
export default function App() {
  return nativeAvailable() ? <NativeApp /> : <DemoApp />;
}
function DemoApp() {
  const [page, setPage] = useState<Page>("preparation");
  const [settings, setSettings] = useState<Settings>(initial);
  const [dirty, setDirty] = useState(false);
  const [preparationDirty, setPreparationDirty] = useState(false);
  const [connectionId, setConnectionId] = useState(initial.connections[0].id);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [toast, setToast] = useState<{ text: string; error: boolean } | null>(
    null,
  );
  const [modal, setModal] = useState<"stop" | "environment" | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const operation = useRef(false);
  const checkAbort = useRef<AbortController | null>(null);
  const [scenario, setScenario] = useState<DemoScenario>("ready");
  const validating = false;
  const [validation, setValidation] = useState<string | null>(null);
  const [sidebar, setSidebar] = useState(false);
  const main = useRef<HTMLElement>(null);
  const snapshot = useSyncExternalStore(
    runtime.subscribe,
    runtime.getSnapshot,
    runtime.getSnapshot,
  );
  const profile = settings.commanders.find((c) => c.id === settings.activeId)!;
  const connection = settings.connections.find(
    (c) => c.id === profile.connectionId,
  )!;
  const locked = ["running", "stopping", "checking"].includes(snapshot.state);
  const invalidatePreparation = useCallback(() => {
    const current = runtime.getSnapshot().profile;
    runtime.selectProfile(current);
  }, []);
  const observed = useRef(snapshot);
  if (snapshot.observing) observed.current = snapshot;
  const displaySnapshot = snapshot.observing
    ? snapshot
    : {
        ...snapshot,
        tasks: observed.current.tasks,
        logs: observed.current.logs,
        metrics: observed.current.metrics,
      };
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    main.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    setSidebar(false);
  }, [page]);
  useEffect(() => {
    const before = (e: BeforeUnloadEvent) => {
      if (
        document.documentElement.dataset.devReloading !== "true" &&
        (dirty || preparationDirty || snapshot.state === "running")
      ) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", before);
    return () => window.removeEventListener("beforeunload", before);
  }, [dirty, preparationDirty, snapshot.state]);
  const notify = (text: string, error = false) => setToast({ text, error });
  function sync(next: Settings) {
    setSettings(next);
    const p = next.commanders.find((c) => c.id === next.activeId)!;
    runtime.selectProfile({ id: p.id, name: p.name, revision: p.revision });
  }
  function select(id: string) {
    if (locked) return;
    sync({ ...settings, activeId: id });
    // Preserve the selection without saving unrelated edits in the open workshop.
    try {
      const saved = loadSettings(availableStorage());
      if (saved.commanders.some((c) => c.id === id)) {
        saveSettings(localStorage, { ...saved, activeId: id });
      } else {
        setDirty(true);
      }
    } catch {
      setDirty(true);
      notify("选择已保留在当前窗口，请到工坊保存档案。", true);
    }
  }
  function changeProfile(patch: Partial<Commander>) {
    if (locked) return;
    const next = {
      ...settings,
      commanders: settings.commanders.map((c) =>
        c.id === profile.id ? { ...c, ...patch, revision: c.revision + 1 } : c,
      ),
    };
    sync(next);
    setDirty(true);
  }
  function changeConnection(patch: Partial<Connection>) {
    if (locked) return;
    sync({
      ...settings,
      connections: settings.connections.map((c) =>
        c.id === connectionId ? { ...c, ...patch } : c,
      ),
      commanders: settings.commanders.map((c) =>
        c.connectionId === connectionId
          ? { ...c, revision: c.revision + 1 }
          : c,
      ),
    });
    setDirty(true);
    setValidation(null);
  }
  function save() {
    const error =
      settings.commanders.map(validateCommander).find(Boolean) ||
      settings.connections.map(validateConnection).find(Boolean);
    if (error) {
      notify(error, true);
      return;
    }
    if (
      new Set(settings.commanders.map((c) => c.name.trim())).size !==
      settings.commanders.length
    ) {
      notify("请为每位指挥官设置不同的名称。", true);
      return;
    }
    try {
      saveSettings(localStorage, settings);
      setDirty(false);
      notify("演示设置已保存至本机。API Key 未保存。");
    } catch {
      notify("无法写入本机存储；修改仍保留在当前窗口。", true);
    }
  }
  function addProfile() {
    if (locked) return;
    const id = crypto.randomUUID();
    const next = {
      ...settings,
      activeId: id,
      commanders: [
        ...settings.commanders,
        {
          ...profile,
          id,
          name: `指挥官 ${settings.commanders.length + 1}`,
          callsign: String(settings.commanders.length + 1).padStart(2, "0"),
          revision: 1,
        },
      ],
    };
    sync(next);
    setDirty(true);
  }
  function addConnection() {
    if (locked) return;
    const id = crypto.randomUUID();
    sync({
      ...settings,
      connections: [
        ...settings.connections,
        {
          id,
          name: `新连接 ${settings.connections.length + 1}`,
          provider: "自定义",
          endpoint: "https://api.example.com/v1",
          model: "demo-model",
        },
      ],
    });
    setConnectionId(id);
    setDirty(true);
    setValidation(null);
  }
  async function act(kind: string, action: () => Promise<OperationResult>) {
    if (operation.current) return;
    operation.current = true;
    setBusy(kind);
    try {
      const result = await action();
      notify(result.message, !result.ok);
    } catch {
      notify("本地演示操作未完成，请重新检查。", true);
    } finally {
      operation.current = false;
      setBusy(null);
    }
  }
  const request = () => ({
    requestId: crypto.randomUUID(),
    profileId: profile.id,
    profileRevision: profile.revision,
  });
  function check() {
    if (operation.current) return;
    if (dirty || preparationDirty) {
      notify("请先保存指挥官、连接和备战方案。", true);
      return;
    }
    const controller = new AbortController();
    checkAbort.current = controller;
    void act("check", () =>
      runtime.check(request(), controller.signal),
    ).finally(() => {
      if (checkAbort.current === controller) checkAbort.current = null;
    });
  }
  function start() {
    if (!snapshot.session || !snapshot.readiness || dirty || preparationDirty)
      return;
    void act("start", () =>
      runtime.start({
        ...request(),
        sessionId: snapshot.session!.id,
        readyToken: snapshot.readiness!.token,
      }),
    );
  }
  function stop() {
    if (!snapshot.session) return;
    setModal(null);
    void act("stop", () =>
      runtime.stop({ ...request(), sessionId: snapshot.session!.id }),
    );
  }
  function changeScenario(value: DemoScenario) {
    const result = runtime.setScenario(value);
    if (result.ok) {
      setScenario(value);
      notify(result.message);
    } else notify(result.message, true);
  }
  function validate() {
    const current = settings.connections.find((c) => c.id === connectionId)!;
    const error = validateConnection(current);
    setValidation(
      error ?? "格式检查通过。本次没有请求模型，真实连接状态仍为未连接。",
    );
  }
  function exportRecords() {
    const payload = {
      format: "tacticore-demo-record-v1",
      warning: "离线演示数据，不代表实机能力或真实执行",
      exportedAt: new Date().toISOString(),
      state: snapshot.state,
      metrics: snapshot.metrics,
      logs: snapshot.logs,
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "tacticore-demo-record.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify("已导出演练记录，不含连接配置和密钥。");
  }
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳转到主要内容
      </a>
      <aside className={`sidebar ${sidebar ? "open" : ""}`}>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("operations");
          }}
          aria-label="弈核 Tacticore 作战中心"
        >
          <Circuitry size={32} weight="duotone" />
          <span>
            <strong>弈核</strong>
            <small>TACTICORE</small>
          </span>
        </a>
        <p className="sidebar-caption">独立 Agent 指挥系统</p>
        <div className="nav-divider" />
        <nav aria-label="主导航">
          {pages.map((p) => (
            <button
              key={p.id}
              aria-current={page === p.id ? "page" : undefined}
              className={page === p.id ? "active" : ""}
              onClick={() => setPage(p.id)}
            >
              <p.icon
                size={21}
                weight={page === p.id ? "duotone" : "regular"}
              />
              <span>
                {p.label}
                <small>{p.english}</small>
              </span>
              {page === p.id && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="system-label">
            <i />
            LOCAL WORKSPACE
          </span>
          <p>
            判断先于行动。
            <br />
            每一项指令，都有边界。
          </p>
          <button
            className="text-action"
            onClick={() => setModal("environment")}
          >
            <Info size={15} />
            关于此演示
          </button>
          <span className="build-label">PREVIEW 0.1 / OCT 2026</span>
        </div>
      </aside>
      {sidebar && (
        <button
          className="sidebar-backdrop"
          aria-label="关闭导航"
          onClick={() => setSidebar(false)}
        />
      )}
      <div className="app-content">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="展开导航"
            aria-expanded={sidebar}
            onClick={() => setSidebar(!sidebar)}
          >
            <List size={22} />
          </button>
          <div className="environment">
            <span className="environment-badge">DEMO</span>
            <strong>离线演示环境</strong>
            <span>不连接游戏或模型</span>
          </div>
          <div className="topbar-right">
            <span className="connection-status">
              <LinkBreak size={14} />
              适配层未连接
            </span>
            <button
              className="workspace-profile"
              onClick={() => setPage("commanders")}
            >
              <span className="avatar">{profile.name.slice(0, 1) || "弈"}</span>
              <span>{profile.name || "未命名"}</span>
            </button>
          </div>
        </header>
        <main
          id="main-content"
          className="main-content"
          data-page={page}
          tabIndex={-1}
          ref={main}
        >
          <section hidden={page !== "preparation"} aria-label="战前备战工作区">
            <PreparationPage
              commanders={settings.commanders}
              connections={settings.connections}
              activeCommanderId={profile.id}
              onSelectCommander={select}
              locked={locked}
              onOpenCommanders={() => setPage("commanders")}
              onOpenConnections={() => setPage("connections")}
              onPlanChanged={invalidatePreparation}
              onDirtyChange={setPreparationDirty}
            />
          </section>
          <section hidden={page !== "radio"} aria-label="战场电台工作区">
            <RadioPage
              commander={{ id: profile.id, name: profile.name }}
              session={
                snapshot.session
                  ? { id: snapshot.session.id, state: snapshot.state }
                  : null
              }
              active={page === "radio"}
            />
          </section>
          {page === "operations" ? (
            <OperationsPage
              snapshot={displaySnapshot}
              profile={profile}
              connection={connection}
              dirty={dirty || preparationDirty}
              busy={busy}
              onCheck={check}
              onCancelCheck={() => checkAbort.current?.abort()}
              onStart={start}
              onStop={() => setModal("stop")}
              onEdit={() => setPage("commanders")}
              onRecords={() => setPage("records")}
              onObserve={() => {
                snapshot.observing ? runtime.detach() : runtime.attach();
                notify(
                  snapshot.observing
                    ? "已暂停界面观察，演练仍在继续。"
                    : "已恢复界面观察。",
                );
              }}
            />
          ) : page === "commanders" ? (
            <CommandersPage
              profiles={settings.commanders}
              selected={profile}
              connections={settings.connections}
              dirty={dirty}
              locked={locked}
              onSelect={select}
              onChange={changeProfile}
              onSave={save}
              onAdd={addProfile}
            />
          ) : page === "connections" ? (
            <ConnectionsPage
              connections={settings.connections}
              selectedId={connectionId}
              onSelect={(id) => {
                setConnectionId(id);
                setValidation(null);
              }}
              onChange={changeConnection}
              onSave={save}
              onAdd={addConnection}
              onValidate={validate}
              dirty={dirty}
              locked={locked}
              keyValue={keys[connectionId] ?? ""}
              onKeyChange={(value) =>
                setKeys({ ...keys, [connectionId]: value })
              }
              validating={validating}
              validation={validation}
            />
          ) : page === "records" ? (
            <RecordsPage
              snapshot={displaySnapshot}
              scenario={scenario}
              onScenario={changeScenario}
              onCheck={check}
              onCancelCheck={() => checkAbort.current?.abort()}
              onExport={exportRecords}
              busy={!!busy}
              locked={locked}
            />
          ) : null}
        </main>
        <footer className="app-statusbar">
          <span>
            <span className={`status-dot ${snapshot.state}`} />
            {stateLabels[snapshot.state]}
            {!snapshot.observing ? " · 观察暂停" : ""}
          </span>
          <span>
            游戏接入未授权 <span className="status-separator">/</span>{" "}
            真实模型请求 0
          </span>
          <span>TACTICORE / LOCAL DEMO</span>
        </footer>
      </div>
      {toast && (
        <div className={`toast ${toast.error ? "error" : ""}`} role="status">
          {toast.error ? <Warning size={20} /> : <CheckCircle size={20} />}
          <span>{toast.text}</span>
          <button
            className="icon-button"
            aria-label="关闭提示"
            onClick={() => setToast(null)}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {modal === "stop" && (
        <Modal
          title="停止当前演练？"
          onClose={() => setModal(null)}
          footer={
            <>
              <Button onClick={() => setModal(null)}>继续演练</Button>
              <Button kind="danger" onClick={stop}>
                确认停止
              </Button>
            </>
          }
        >
          <div className="modal-icon">
            <ShieldCheck size={32} />
          </div>
          <p>
            将停止「{profile.name}」的离线演练，等待当前任务收尾并返回停止回执。
          </p>
          <p className="subtle">
            这不会关闭游戏，也不会向游戏或模型发送任何指令。演练记录会保留在当前窗口。
          </p>
        </Modal>
      )}
      {modal === "environment" && (
        <Modal
          title="弈核 Tacticore · 交互预览"
          onClose={() => setModal(null)}
          footer={
            <Button kind="primary" onClick={() => setModal(null)}>
              返回工作区
            </Button>
          }
        >
          <p>
            这是独立桌面客户端的离线交互环境，用于验证指挥官配置、会话控制和执行反馈。
          </p>
          <ul className="environment-details">
            <li>
              <Flask size={18} />
              任务、地图、决策和回执全部来自本地模拟。
            </li>
            <li>
              <Key size={18} />
              仅保存非敏感演示设置，密钥不保存、不发送。
            </li>
            <li>
              <LinkBreak size={18} />
              不会读取本机凭据、游戏内存或真实会话。
            </li>
          </ul>
          <p className="subtle">
            弈核是独立 Agent 指挥程序；Remix-Ai
            是游戏内容适配版本。当前仍处开发初期，跨游戏与多 Agent
            接入尚待验证。
          </p>
          <a
            className="text-action"
            href="https://github.com/RA3-Remix-AI/Tacticore"
            target="_blank"
            rel="noreferrer"
          >
            项目源代码
            <ArrowSquareOut size={15} />
          </a>
        </Modal>
      )}
    </div>
  );
}
