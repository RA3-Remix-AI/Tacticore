import { useEffect, useState } from "react";
import {
  ArrowRight,
  CheckCircle,
  DownloadSimple,
  FloppyDisk,
  GameController,
  Info,
  LockSimple,
  MapTrifold,
  ShieldCheck,
  Shuffle,
  SlidersHorizontal,
  WarningCircle,
} from "@phosphor-icons/react";
import {
  Button,
  CommanderIcon,
  PageHeading,
  PanelHeading,
} from "../components/ui";
import type { Commander, Connection } from "../state/settings";
import {
  defaultPreparation,
  exportPreparation,
  factionLabels,
  loadPreparation,
  savePreparation,
  validatePreparation,
  type PreparationPlan,
} from "../state/preparation";
import "./preparation.css";

function localStorageIfAvailable() {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}
const money = (value: number) =>
  Number.isFinite(value) ? value.toLocaleString("zh-CN") : "—";
const inputNumber = (value: string) =>
  value === "" ? Number.NaN : Number(value);

export interface PreparationPageProps {
  commanders: Commander[];
  connections?: Connection[];
  activeCommanderId: string;
  onSelectCommander: (id: string) => void;
  locked: boolean;
  onOpenCommanders: () => void;
  onOpenConnections: () => void;
  onPlanChanged?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
}

export function PreparationPage({
  commanders,
  connections = [],
  activeCommanderId,
  onSelectCommander,
  locked,
  onOpenCommanders,
  onOpenConnections,
  onPlanChanged,
  onDirtyChange,
}: PreparationPageProps) {
  const [saved, setSaved] = useState(() =>
    loadPreparation(localStorageIfAvailable()),
  );
  const [plan, setPlan] = useState(saved.plan);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selected =
    commanders.find((c) => c.id === activeCommanderId) ?? commanders[0];
  const connection = connections.find((c) => c.id === selected?.connectionId);
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  function change(patch: Partial<PreparationPlan>) {
    if (locked) return;
    setPlan((previous) => ({
      ...previous,
      ...patch,
      revision: previous.revision + 1,
    }));
    setDirty(true);
    setMessage(null);
    setError(null);
    onPlanChanged?.();
  }
  function save() {
    if (locked) return;
    const issue = validatePreparation(plan);
    if (issue) {
      setError(issue);
      setMessage(null);
      return;
    }
    try {
      const storage = localStorageIfAvailable();
      if (!storage) throw new Error("storage_unavailable");
      const document = savePreparation(storage, plan);
      setSaved(document);
      setPlan(document.plan);
      setDirty(false);
      setError(null);
      setMessage("本机备战方案已保存。游戏仍未核验，请在大厅确认开局设置。");
    } catch {
      setError(
        "无法保存到本机，当前修改仍留在窗口中。请检查浏览器存储权限或空间。",
      );
      setMessage(null);
    }
  }
  function reset() {
    change({ ...structuredClone(defaultPreparation), revision: plan.revision });
    setMessage("已恢复默认草稿；保存后才会替换本机方案。");
  }
  function exportPlan() {
    if (!selected) return;
    try {
      const exportedPlan = exportPreparation(plan, selected);
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(exportedPlan, null, 2)], {
          type: "application/json",
        }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = "tacticore-prepared-plan.json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setError(null);
      setMessage(
        "已导出下一局计划，不含连接地址、模型配置或凭据；这不是游戏执行命令。",
      );
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : "请先修正备战方案。");
      setMessage(null);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="PREPARATION / 战前备战室"
        title="先定战局，再选打法。"
        description="准备下一局的规则、指挥官和资源约束。游戏实际设置由大厅与适配器核验。"
      >
        <Button onClick={exportPlan} disabled={locked || !selected}>
          <DownloadSimple size={16} /> 导出备战计划
        </Button>
      </PageHeading>
      <div className="prep-status" role="status">
        <span className={`tiny-pill ${dirty ? "warning" : ""}`}>
          {dirty
            ? "有未保存修改"
            : saved.savedAt
              ? "本机方案已保存"
              : "默认本机草案"}
        </span>
        <span>
          <WarningCircle size={16} /> 游戏设置未核验
        </span>
        <span>RA3 适配版本待确认</span>
      </div>
      {locked && (
        <div className="info-banner prep-lock">
          <LockSimple size={20} />
          <p>
            <strong>当前会话配置已锁定。</strong>{" "}
            停止演练后可编辑下一局方案，正在检查时也不能改变检查依据。
          </p>
        </div>
      )}
      <div className="preparation-grid">
        <div className="prep-editors">
          <section className="panel prep-panel">
            <PanelHeading eyebrow="01 / MATCH RULES" title="这场，怎么开始？">
              <GameController size={22} />
            </PanelHeading>
            <fieldset disabled={locked}>
              <div className="prep-game-row">
                <GameController size={23} />
                <div>
                  <strong>红色警戒 3</strong>
                  <small>当前游戏适配 · 实际版本、地图与阵营仍待核验</small>
                </div>
                <span className="tiny-pill warning">未连接游戏</span>
              </div>
              <div className="form-grid">
                <label>
                  地图计划
                  <input
                    value={plan.map}
                    maxLength={60}
                    list="preparation-maps"
                    onChange={(e) => change({ map: e.target.value })}
                  />
                  <datalist id="preparation-maps">
                    <option value="工业区" />
                  </datalist>
                  <small>
                    可填写本机地图名，此处不表示适配器已支持该地图。
                  </small>
                </label>
                <label>
                  Agent 玩家索引
                  <input
                    type="number"
                    min={0}
                    max={15}
                    step={1}
                    value={
                      Number.isFinite(plan.playerSlot) ? plan.playerSlot : ""
                    }
                    onChange={(e) =>
                      change({ playerSlot: inputNumber(e.target.value) })
                    }
                  />
                  <small>用于备战计划，实际玩家绑定由会话重新确认。</small>
                </label>
              </div>
              <span className="field-label">计划阵营</span>
              <div className="prep-factions" role="group" aria-label="计划阵营">
                {(
                  Object.entries(factionLabels) as [
                    PreparationPlan["faction"],
                    string,
                  ][]
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    className={plan.faction === id ? "selected" : ""}
                    aria-pressed={plan.faction === id}
                    onClick={() => change({ faction: id })}
                  >
                    {id === "random" ? (
                      <Shuffle size={34} />
                    ) : (
                      <img
                        src={`/games/ra3/factions/${id === "allies" ? "allied" : id}.png`}
                        alt=""
                      />
                    )}
                    <strong>{label}</strong>
                    <small>{id.toUpperCase()}</small>
                  </button>
                ))}
              </div>
              <div className="prep-money-label">
                <label htmlFor="prep-starting-funds">游戏初始资金</label>
                <span>下一局计划 / 尚未写入</span>
              </div>
              <div
                className="prep-fund-presets"
                role="group"
                aria-label="初始资金草案档位"
              >
                {[5000, 10000, 20000, 40000].map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={plan.startingFunds === value}
                    className={plan.startingFunds === value ? "selected" : ""}
                    onClick={() => change({ startingFunds: value })}
                  >
                    {money(value)}
                  </button>
                ))}
              </div>
              <label className="prep-number-label">
                <span>自定义计划资金</span>
                <div className="prep-currency">
                  <span aria-hidden="true">$</span>
                  <input
                    id="prep-starting-funds"
                    aria-label="自定义计划初始资金"
                    type="number"
                    min={0}
                    max={1000000}
                    step={1}
                    value={
                      Number.isFinite(plan.startingFunds)
                        ? plan.startingFunds
                        : ""
                    }
                    onChange={(e) =>
                      change({ startingFunds: inputNumber(e.target.value) })
                    }
                  />
                </div>
                <small>
                  这些是本机草案快捷值。游戏可用档位和范围待适配器核验，请在大厅手动设置。
                </small>
              </label>
              <div className="prep-readback">
                <Info size={17} />
                <div>
                  <strong>游戏实际初始资金：未知</strong>
                  <p>
                    保存本机方案不会修改游戏。开局后该规则锁定；后续接入后再核对实际值与计划是否一致。
                  </p>
                </div>
              </div>
            </fieldset>
          </section>
          <section className="panel prep-panel">
            <PanelHeading
              eyebrow="02 / EXECUTION LIMITS"
              title="给指挥官，明确的资源边界。"
            >
              <ShieldCheck size={22} />
            </PanelHeading>
            <p className="prep-panel-intro">
              下列两项分别限制生产支出与剩余资源，不改变游戏初始资金。当前只保存为本机计划。
            </p>
            <fieldset disabled={locked}>
              <div className="form-grid">
                <label>
                  Agent 生产总支出上限
                  <div className="prep-currency">
                    <span aria-hidden="true">$</span>
                    <input
                      type="number"
                      min={220}
                      max={10000}
                      step={1}
                      value={
                        Number.isFinite(plan.productionLimit)
                          ? plan.productionLimit
                          : ""
                      }
                      onChange={(e) =>
                        change({ productionLimit: inputNumber(e.target.value) })
                      }
                    />
                  </div>
                  <small>
                    220–10,000。宿主可承诺生产的累计额度，不是一次开局奖励。
                  </small>
                </label>
                <label>
                  资源保留底线
                  <div className="prep-currency">
                    <span aria-hidden="true">$</span>
                    <input
                      type="number"
                      min={500}
                      max={10000}
                      step={1}
                      value={
                        Number.isFinite(plan.reserveFloor)
                          ? plan.reserveFloor
                          : ""
                      }
                      onChange={(e) =>
                        change({ reserveFloor: inputNumber(e.target.value) })
                      }
                    />
                  </div>
                  <small>
                    500–10,000。生产后仍须保留的资源；实际派单时重新检查。
                  </small>
                </label>
              </div>
            </fieldset>
            <div className="prep-resource-rule">
              <SlidersHorizontal size={16} />
              <p>
                游戏资金、生产额度、保留底线分别管理。额度不足或资源不足时，宿主仍可拒绝行动。
              </p>
            </div>
          </section>
        </div>
        <aside className="prep-summary-column">
          <section className="panel prep-summary">
            <PanelHeading eyebrow="03 / COMMANDER" title="谁来指挥？" />
            <fieldset disabled={locked}>
              <label>
                本局指挥官
                <select
                  value={activeCommanderId}
                  onChange={(e) => {
                    onSelectCommander(e.target.value);
                    onPlanChanged?.();
                  }}
                >
                  {commanders.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
                <small>选择跟随指挥官档案保存，不改变局内已绑定身份。</small>
              </label>
              <div className="prep-commander">
                <CommanderIcon
                  doctrine={selected?.doctrine ?? "assault"}
                  size={34}
                />
                <div>
                  <strong>{selected?.name ?? "未选择指挥官"}</strong>
                  <small>{connection?.name ?? "连接未配置"}</small>
                </div>
              </div>
              <div
                className="prep-relationship"
                role="group"
                aria-label="指挥官关系"
              >
                <button
                  type="button"
                  aria-pressed={plan.relationship === "ally"}
                  className={plan.relationship === "ally" ? "selected" : ""}
                  onClick={() => change({ relationship: "ally" })}
                >
                  并肩作战<small>计划作为队友</small>
                </button>
                <button
                  type="button"
                  aria-pressed={plan.relationship === "opponent"}
                  className={plan.relationship === "opponent" ? "selected" : ""}
                  onClick={() => change({ relationship: "opponent" })}
                >
                  正面对抗<small>计划作为对手</small>
                </button>
              </div>
            </fieldset>
            <div className="prep-links">
              <button className="text-action" onClick={onOpenCommanders}>
                调整指挥风格
                <ArrowRight size={15} />
              </button>
              <button className="text-action" onClick={onOpenConnections}>
                查看模型连接
                <ArrowRight size={15} />
              </button>
            </div>
          </section>
          <section className="panel prep-summary">
            <PanelHeading eyebrow="NEXT MATCH / PLAN" title="开战确认单" />
            <dl className="prep-recap">
              <div>
                <dt>
                  <MapTrifold size={15} />
                  地图
                </dt>
                <dd>{plan.map.trim() || "待填写"}</dd>
              </div>
              <div>
                <dt>Agent 阵营</dt>
                <dd>{factionLabels[plan.faction]}</dd>
              </div>
              <div>
                <dt>初始资金计划</dt>
                <dd>{money(plan.startingFunds)}</dd>
              </div>
              <div>
                <dt>生产总额度</dt>
                <dd>{money(plan.productionLimit)}</dd>
              </div>
              <div>
                <dt>资源保留底线</dt>
                <dd>{money(plan.reserveFloor)}</dd>
              </div>
            </dl>
            <ol className="prep-checklist">
              <li>
                {!dirty && saved.savedAt ? (
                  <CheckCircle size={16} />
                ) : (
                  <Info size={16} />
                )}
                <span>
                  本机计划
                  <small>
                    {dirty
                      ? "修改后等待保存"
                      : saved.savedAt
                        ? "已保存，重开可恢复"
                        : "默认方案，尚未保存"}
                  </small>
                </span>
              </li>
              <li>
                <WarningCircle size={16} />
                <span>
                  游戏大厅设置<small>请在游戏中手动确认</small>
                </span>
              </li>
              <li>
                <WarningCircle size={16} />
                <span>
                  会话与指挥官绑定<small>适配器未连接，尚未核验</small>
                </span>
              </li>
            </ol>
            {saved.savedAt && (
              <p className="prep-saved-time">
                最近保存：{new Date(saved.savedAt).toLocaleString("zh-CN")}
              </p>
            )}
          </section>
        </aside>
      </div>
      <div className={`prep-feedback ${error ? "error" : ""}`} role="status">
        {error ? <WarningCircle size={18} /> : <Info size={18} />}
        <p>
          {error ??
            message ??
            "本页准备下一局计划；保存到本机与游戏实际生效是两个独立状态。"}
        </p>
      </div>
      <div className="prep-save-bar">
        <div>
          <strong>
            {dirty
              ? "准备好后，保存这份方案。"
              : saved.savedAt
                ? "方案已在本机，等待大厅确认。"
                : "从默认方案开始，按你的玩法调整。"}
          </strong>
          <p>
            {locked
              ? "当前会话已锁定配置，停止后可以继续编辑。"
              : "保存不会发起模型请求，也不会启动或修改游戏。"}
          </p>
        </div>
        <div className="button-group">
          <Button onClick={reset} disabled={locked}>
            恢复默认草稿
          </Button>
          <Button
            kind="primary"
            onClick={save}
            disabled={locked || (!dirty && !!saved.savedAt)}
          >
            <FloppyDisk size={16} />
            保存本机方案
          </Button>
        </div>
      </div>
    </>
  );
}
