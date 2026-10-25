import {
  ArrowRight,
  ArrowUpRight,
  Check,
  Crosshair,
  Eye,
  Flag,
  Hexagon,
  LockSimple,
  Pause,
  Play,
  ShieldCheck,
  Stop,
  Target,
} from "@phosphor-icons/react";
import {
  Button,
  CommanderIcon,
  PanelHeading,
  TextAction,
} from "../components/ui";
import {
  doctrineDetails,
  doctrineLabels,
  type Commander,
  type Connection,
} from "../state/settings";
import type { RuntimeSnapshot } from "../runtime";
import { commanderStyleName, preferenceSummary } from "../state/preferences";
export const stateLabels: Record<RuntimeSnapshot["state"], string> = {
  idle: "尚无会话",
  checking: "检查中",
  ready: "演示就绪",
  running: "演练进行中",
  stopping: "正在收尾",
  stopped: "演练已停止",
  fault: "演练故障",
};
const stateInstructions: Record<RuntimeSnapshot["state"], string> = {
  idle: "检查演示环境，建立本地推演会话。",
  checking: "正在核对演示配置与会话；可随时取消检查。",
  ready: "检查已通过，请在 20 秒内开始演练；过期后需重新检查。",
  running: "正在推演并记录模拟回执；可暂停观察或停止演练。",
  stopping: "已请求停止，等待任务收尾与停止回执。",
  stopped: "停止回执已确认。可编辑档案，或重新检查并开启下一轮。",
  fault: "检查未通过。查看演练记录中的原因，再重新检查。",
};
export const phaseLabels: Record<string, string> = {
  reserved: "任务待命",
  planned: "任务待命",
  approach: "接近目标",
  prepare: "交战准备",
  engage: "交战推演",
  retreat: "撤退归还",
  restored: "控制已归还",
  completed: "任务完成",
  idle: "等待指令",
  observe: "战场感知",
  decide: "战术决策",
  execute: "本地调度",
  perception: "战场感知",
  reasoning: "局势判断",
  decision: "战术决策",
  dispatch: "本地调度",
  feedback: "反馈调整",
};
export function OperationsPage({
  snapshot,
  profile,
  connection,
  dirty,
  busy,
  onCheck,
  onCancelCheck,
  onStart,
  onStop,
  onEdit,
  onRecords,
  onObserve,
}: {
  snapshot: RuntimeSnapshot;
  profile: Commander;
  connection: Connection;
  dirty: boolean;
  busy: string | null;
  onCheck: () => void;
  onCancelCheck: () => void;
  onStart: () => void;
  onStop: () => void;
  onEdit: () => void;
  onRecords: () => void;
  onObserve: () => void;
}) {
  const doctrine = doctrineDetails[profile.doctrine];
  const running = snapshot.state === "running";
  const active = running || snapshot.state === "stopping";
  const task = snapshot.tasks[0];
  const stage = task?.stage ?? "";
  const hasSession = !!snapshot.session;
  const phases = ["感知", "推演", "决策", "调度", "反馈"];
  const step = hasSession ? Math.max(0, phases.indexOf(stage)) : 0;
  return (
    <>
      <header className="operations-heading">
        <div>
          <p className="eyebrow">COMMAND OPERATIONS / 作战中心</p>
          <h1>每一步，都有判断。</h1>
          <p className="page-description">
            读懂战局，选择时机，让行动与意图保持一致。
          </p>
        </div>
        <div className="session-caption">
          <span className="eyebrow">CURRENT SESSION</span>
          <strong>
            {hasSession ? "工业区 · 本地推演" : "等待建立演练会话"}
          </strong>
          <small>模拟场景 / 不读取游戏</small>
        </div>
      </header>
      <div className="operations-grid">
        <section className="panel commander-summary">
          <div className="profile-number">
            AGENT / {profile.callsign}
            <span className="tiny-pill">
              {doctrineLabels[profile.doctrine]}型
            </span>
          </div>
          <div className="commander-seal">
            <CommanderIcon doctrine={profile.doctrine} size={66} />
          </div>
          <p className="eyebrow">{doctrine.code}</p>
          <h2>{profile.name}</h2>
          <p className="doctrine-line">{commanderStyleName(profile)}</p>
          <p className="profile-traits">{profile.traits}</p>
          <p className="commander-preference-summary">
            {preferenceSummary(profile)}
          </p>
          <p className="weights-note">本机指挥偏好 · 尚未应用到游戏宿主</p>
          <div className="profile-connection">
            <span>演示模型</span>
            <strong>{profile.modelOverride || connection.model}</strong>
            <small>{connection.provider} / 未连接</small>
          </div>
          <TextAction onClick={onEdit}>编辑指挥官档案</TextAction>
        </section>
        <section className="panel tactical-panel">
          <PanelHeading eyebrow="TACTICAL SANDBOX" title="战术推演台">
            <span className={`live-label ${running ? "active" : ""}`}>
              <i />
              {running ? "模拟运行" : "OFFLINE"}
            </span>
          </PanelHeading>
          <div
            className={`tactical-map doctrine-${profile.doctrine} ${running ? "is-running" : ""}`}
            aria-label="本地模拟战术地图，非真实游戏地图"
          >
            <div className="map-grid" />
            <div className="map-contour contour-one" />
            <div className="map-contour contour-two" />
            <div className="map-contour contour-three" />
            <span className="map-coordinates">
              SECTOR 07
              <br />
              43.8 / 26.4
            </span>
            <span className="map-north">
              N <ArrowUpRight size={15} />
            </span>
            <div className="map-path path-one" />
            <div className="map-path path-two" />
            <div className="map-path path-three" />
            <span className="map-pin pin-home">
              <Hexagon size={20} weight="duotone" />
              <strong>前沿基地</strong>
              <small>己方 / 模拟</small>
            </span>
            <span className="map-pin pin-scout">
              <Eye size={20} />
              <strong>侧翼通路</strong>
              <small>{hasSession ? "已观察 / 模拟" : "待观察"}</small>
            </span>
            <span className="map-pin pin-target">
              <Target size={24} />
              <strong>交汇点</strong>
              <small>{running ? "推演目标" : "待命"}</small>
            </span>
            <span className="map-squad squad-one">
              <Flag size={17} weight="fill" /> A1
            </span>
            <span className="map-squad squad-two">
              <Flag size={17} weight="fill" /> B2
            </span>
            <div className="map-caption">
              <span>{running ? "当前战术意图" : "演练任务"}</span>
              <strong>
                {task?.detail ?? "建立观察，等待指挥官接入演练。"}
              </strong>
            </div>
          </div>
          <div className="phase-track" aria-label="演练决策阶段">
            {phases.map((phase, i) => (
              <div
                className={hasSession && i === step ? "active" : ""}
                key={phase}
              >
                <span>0{i + 1}</span>
                <strong>{phase}</strong>
              </div>
            ))}
          </div>
          <div className="tactical-footer">
            <span>
              <ShieldCheck size={14} /> 本地校验约束行动
            </span>
            <span>模拟数据 / 无执行权</span>
          </div>
        </section>
        <section className="panel mission-panel">
          <PanelHeading eyebrow="MISSION CONTROL" title="任务与回执">
            <span className="count-label">
              {String(snapshot.tasks.length).padStart(2, "0")}
            </span>
          </PanelHeading>
          <div className="mission-list">
            {snapshot.tasks.length ? (
              snapshot.tasks.slice(0, 3).map((item, i) => (
                <article className="mission-item" key={item.id}>
                  <div>
                    <span className="mission-index">0{i + 1}</span>
                    <strong>{item.title}</strong>
                    <i className={running ? "signal active" : "signal"} />
                  </div>
                  <span className="mission-stage">
                    {phaseLabels[item.stage] ?? item.stage}
                  </span>
                  <p>{item.detail}</p>
                </article>
              ))
            ) : (
              <div className="empty-mission">
                <Crosshair size={36} weight="thin" />
                <strong>尚无演练任务</strong>
                <p>检查演示环境后，即可观察一轮完整的指挥流程。</p>
              </div>
            )}
          </div>
          <div className="receipt">
            <span className="eyebrow">LATEST RECEIPT</span>
            <p>
              {snapshot.logs.at(-1)?.message ??
                "终端已准备就绪，等待你的指令。"}
            </p>
            <span>
              <Check size={13} />{" "}
              {snapshot.state === "stopped"
                ? "停止已确认 / 模拟"
                : snapshot.state === "stopping"
                  ? "等待收尾回执"
                  : "仅记录模拟事件"}
            </span>
          </div>
          <TextAction onClick={onRecords}>查看完整演练记录</TextAction>
        </section>
      </div>
      <section className="command-bar" aria-label="演练控制">
        <div className="command-state">
          <i className={`status-dot ${snapshot.state}`} />
          <div>
            <strong>{stateLabels[snapshot.state]}</strong>
            <span>
              {dirty
                ? "配置尚未保存，请先在备战室、工坊或模型连接中保存修改。"
                : (snapshot.reason?.message ??
                  (!snapshot.observing && running
                    ? "观察已暂停，演练仍在继续；可恢复观察或停止。"
                    : stateInstructions[snapshot.state]))}
            </span>
          </div>
        </div>
        <div className="command-actions">
          {active ? (
            <>
              <Button onClick={onObserve} disabled={!!busy}>
                {snapshot.observing ? <Pause size={16} /> : <Play size={16} />}{" "}
                {snapshot.observing ? "暂停观察" : "继续观察"}
              </Button>
              <Button
                kind="danger"
                onClick={onStop}
                disabled={!!busy || snapshot.state === "stopping"}
                loading={busy === "stop"}
              >
                <Stop size={16} />
                停止演练
              </Button>
            </>
          ) : (
            <>
              {snapshot.state === "checking" ? (
                <Button onClick={onCancelCheck}>取消检查</Button>
              ) : (
                <Button
                  onClick={onCheck}
                  disabled={!!busy || dirty}
                  loading={busy === "check"}
                >
                  <ShieldCheck size={17} />
                  {snapshot.state === "fault" ? "重新检查" : "检查演示环境"}
                </Button>
              )}
              <Button
                kind="primary"
                onClick={onStart}
                disabled={!!busy || dirty || snapshot.state !== "ready"}
                loading={busy === "start"}
              >
                <Play size={16} weight="fill" />
                开始演练
                <ArrowRight size={16} />
              </Button>
            </>
          )}
        </div>
      </section>
      <div className="capabilities-strip">
        <span className="eyebrow">能力边界</span>
        {snapshot.capabilities.map((item) => (
          <span
            className={`capability ${item.status}`}
            key={item.id}
            title={item.detail}
          >
            {item.status === "demo" ? (
              <Check size={13} />
            ) : (
              <LockSimple size={13} />
            )}
            <strong>{item.label}</strong>
            <small>
              {item.status === "demo"
                ? "演示"
                : item.status === "planned"
                  ? "规划中"
                  : "未授权"}
            </small>
          </span>
        ))}
      </div>
    </>
  );
}
