import {
  DownloadSimple,
  Flask,
  Info,
  Play,
  Warning,
} from "@phosphor-icons/react";
import { Button, PageHeading, PanelHeading } from "../components/ui";
import type { DemoScenario, RuntimeSnapshot } from "../runtime";
import { stateLabels } from "./OperationsPage";
export const scenarios: {
  id: DemoScenario;
  label: string;
  description: string;
}[] = [
  {
    id: "ready",
    label: "就绪场景",
    description: "配置、会话与能力检查通过，体验指挥流程。",
  },
  {
    id: "no-game",
    label: "未发现游戏",
    description: "模拟没有可用会话，阻止开始指挥。",
  },
  {
    id: "stale",
    label: "会话已过期",
    description: "模拟历史信息失效，要求重新检查。",
  },
  {
    id: "failure",
    label: "能力检查失败",
    description: "模拟执行能力不可用，展示原因与下一步。",
  },
];
export function RecordsPage({
  snapshot,
  scenario,
  onScenario,
  onCheck,
  onCancelCheck,
  onExport,
  busy,
  locked,
}: {
  snapshot: RuntimeSnapshot;
  scenario: DemoScenario;
  onScenario: (id: DemoScenario) => void;
  onCheck: () => void;
  onCancelCheck: () => void;
  onExport: () => void;
  busy: boolean;
  locked: boolean;
}) {
  return (
    <>
      <PageHeading
        eyebrow="SIMULATION & TRACE / 演练与记录"
        title="看见决策，也看见边界。"
        description="在离线环境验证每一步交互。所有任务、会话和回执均为演示数据。"
      >
        <Button onClick={onExport} disabled={!snapshot.logs.length}>
          <DownloadSimple size={16} />
          导出演练记录
        </Button>
      </PageHeading>
      <div className="records-grid">
        <section className="panel scenario-panel">
          <PanelHeading eyebrow="SCENARIO LAB" title="选择演练场景">
            <Flask size={22} />
          </PanelHeading>
          <div className="scenario-list" role="group" aria-label="演练场景">
            {scenarios.map((s) => (
              <button
                key={s.id}
                className={`scenario-option ${scenario === s.id ? "selected" : ""}`}
                aria-pressed={scenario === s.id}
                disabled={locked || busy}
                onClick={() => onScenario(s.id)}
              >
                <span className="radio-dot" />
                <span>
                  <strong>{s.label}</strong>
                  <small>{s.description}</small>
                </span>
              </button>
            ))}
          </div>
          {snapshot.state === "checking" ? (
            <Button onClick={onCancelCheck}>取消检查</Button>
          ) : (
            <Button
              kind="primary"
              onClick={onCheck}
              disabled={locked || busy}
              loading={busy}
            >
              <Play size={15} />
              运行场景检查
            </Button>
          )}
          <p className="subtle">运行中的演练需先停止，再更换场景。</p>
        </section>
        <section className="panel trace-panel">
          <PanelHeading eyebrow="DECISION TRACE" title="会话事件">
            <span className="tiny-pill">{stateLabels[snapshot.state]}</span>
          </PanelHeading>
          <div className="trace-summary">
            <span>
              <b>{String(snapshot.metrics.decisions).padStart(2, "0")}</b>
              模拟决策
            </span>
            <span>
              <b>{String(snapshot.metrics.completed).padStart(2, "0")}</b>
              完成轮次
            </span>
            <span>
              <b>
                {snapshot.metrics.elapsedSeconds}
                <small>s</small>
              </b>
              演练时间
            </span>
          </div>
          <ol className="trace-log">
            {snapshot.logs.length ? (
              snapshot.logs
                .slice()
                .reverse()
                .map((entry) => (
                  <li key={entry.id} className={entry.level}>
                    <span>
                      {entry.level === "info" ? (
                        <Info size={15} />
                      ) : (
                        <Warning size={15} />
                      )}
                    </span>
                    <div>
                      <time>
                        {new Date(entry.at).toLocaleTimeString("zh-CN", {
                          hour12: false,
                        })}
                      </time>
                      <p>{entry.message}</p>
                    </div>
                    <small>模拟</small>
                  </li>
                ))
            ) : (
              <li className="empty-log">
                <Flask size={32} />
                <p>还没有事件。选择场景并运行检查，记录会出现在这里。</p>
              </li>
            )}
          </ol>
        </section>
      </div>
      {snapshot.reason && (
        <section className="diagnostic-panel" role="status">
          <Warning size={22} />
          <div>
            <strong>{snapshot.reason.message}</strong>
            <p>{snapshot.reason.action}</p>
            <code>{snapshot.reason.code}</code>
          </div>
        </section>
      )}
      <div className="info-banner">
        <Info size={22} />
        <p>
          <strong>演示与真实能力严格区分。</strong>{" "}
          导出的文件不包含连接地址、模型配置或密钥，不能作为实机验收证据。
        </p>
      </div>
    </>
  );
}
