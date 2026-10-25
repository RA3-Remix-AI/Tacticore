import { useEffect, useState } from "react";
import {
  Check,
  CheckCircle,
  Copy,
  FloppyDisk,
  Lightbulb,
  Plus,
  SlidersHorizontal,
} from "@phosphor-icons/react";
import {
  Button,
  CommanderIcon,
  PageHeading,
  PanelHeading,
} from "../components/ui";
import { type Commander, type Connection } from "../state/settings";
import {
  commanderPlan,
  commanderPreview,
  commanderStyleName,
  preferenceAxes,
  preferencePresets,
  preferenceSummary,
  profilePreferences,
  type PreferenceLevel,
} from "../state/preferences";
import "./commanders.css";

export function CommandersPage({
  profiles,
  selected,
  connections,
  dirty,
  locked,
  onSelect,
  onChange,
  onSave,
  onAdd,
}: {
  profiles: Commander[];
  selected: Commander;
  connections: Connection[];
  dirty: boolean;
  locked: boolean;
  onSelect: (id: string) => void;
  onChange: (patch: Partial<Commander>) => void;
  onSave: () => void;
  onAdd: () => void;
}) {
  const preferences = profilePreferences(selected);
  const [copyStatus, setCopyStatus] = useState("");
  useEffect(() => setCopyStatus(""), [selected.id, selected.revision]);
  const plan = JSON.stringify(commanderPlan(selected), null, 2);

  async function copyPlan() {
    try {
      await navigator.clipboard.writeText(plan);
      setCopyStatus("已复制本机偏好草案，尚未应用到宿主。");
    } catch {
      setCopyStatus("无法自动复制，请选择下方参数文本后手动复制。");
    }
  }

  return (
    <>
      <PageHeading
        eyebrow="COMMANDER WORKSHOP / 指挥官工坊"
        title="选定风格，塑造你的指挥官。"
        description="从一套打法出发，微调判断偏好，并立刻看懂他会怎样应对战局。"
      >
        <Button onClick={onAdd} disabled={locked || profiles.length >= 12}>
          <Plus size={16} />
          新增指挥官
        </Button>
      </PageHeading>

      <div className="editor-grid commander-workshop">
        <aside className="profile-list" aria-label="指挥官档案">
          {profiles.map((profile) => (
            <button
              className={`profile-card ${profile.id === selected.id ? "selected" : ""}`}
              aria-pressed={profile.id === selected.id}
              key={profile.id}
              onClick={() => onSelect(profile.id)}
              disabled={locked}
            >
              <span className="profile-card-icon">
                <CommanderIcon doctrine={profile.doctrine} />
              </span>
              <span>
                <strong>{profile.name}</strong>
                <small>{commanderStyleName(profile)}</small>
              </span>
              {profile.id === selected.id ? (
                <Check size={16} />
              ) : (
                <span className="profile-card-number">{profile.callsign}</span>
              )}
            </button>
          ))}
          <div className="aside-note">
            <span className="eyebrow">A MIND OF ITS OWN</span>
            <p>
              倾向表达偏好。
              <br />
              指挥官仍会根据实际情报、资源与任务条件判断。
            </p>
          </div>
        </aside>

        <div className="commander-workspace">
          <section className="panel editor-panel">
            <PanelHeading
              eyebrow={`COMMANDER / ${selected.callsign}`}
              title="指挥风格"
            >
              <span className={`tiny-pill ${dirty ? "warning" : ""}`}>
                {dirty ? "有未保存修改" : "当前本机方案"}
              </span>
            </PanelHeading>
            <fieldset disabled={locked}>
              <label className="commander-name-label">
                指挥官名称
                <input
                  value={selected.name}
                  maxLength={24}
                  onChange={(event) => onChange({ name: event.target.value })}
                />
              </label>
              <div className="workshop-section-label">
                <span>选择打法预设</span>
                <small>选择后仍可逐项微调</small>
              </div>
              <div
                className="workshop-presets"
                role="group"
                aria-label="打法预设"
              >
                {preferencePresets.map((preset) => (
                  <button
                    type="button"
                    key={preset.id}
                    aria-pressed={preferences.preset === preset.id}
                    className={`workshop-preset ${preferences.preset === preset.id ? "selected" : ""}`}
                    onClick={() =>
                      onChange({
                        doctrine: preset.doctrine,
                        preferences: { ...preset.values },
                      })
                    }
                  >
                    <CommanderIcon doctrine={preset.doctrine} size={23} />
                    <strong>{preset.label}</strong>
                    <small>{preset.description}</small>
                    {preferences.preset === preset.id && (
                      <CheckCircle
                        className="preset-check"
                        size={16}
                        weight="fill"
                      />
                    )}
                  </button>
                ))}
              </div>
              <div className="workshop-section-label">
                <span>
                  <SlidersHorizontal size={17} />
                  五维指挥倾向
                </span>
                <small>{commanderStyleName(selected)} · 五档相对选择</small>
              </div>
              <div className="preference-controls">
                {preferenceAxes.map((axis) => {
                  const value = preferences[axis.key];
                  return (
                    <div className="preference-control" key={axis.key}>
                      <div className="preference-control-heading">
                        <label htmlFor={`preference-${axis.key}`}>
                          {axis.label}
                        </label>
                        <output htmlFor={`preference-${axis.key}`}>
                          {value} / 5 档
                        </output>
                      </div>
                      <input
                        id={`preference-${axis.key}`}
                        type="range"
                        min={1}
                        max={5}
                        step={1}
                        value={value}
                        aria-describedby={`preference-${axis.key}-description`}
                        aria-valuetext={`${value}档：${axis.descriptions[value - 1]}`}
                        onChange={(event) =>
                          onChange({
                            preferences: {
                              ...preferences,
                              preset: "custom",
                              [axis.key]: Number(
                                event.target.value,
                              ) as PreferenceLevel,
                            },
                          })
                        }
                      />
                      <div className="preference-endpoints">
                        <span>{axis.low}</span>
                        <span>{axis.high}</span>
                      </div>
                      <p id={`preference-${axis.key}-description`}>
                        {axis.descriptions[value - 1]}
                      </p>
                    </div>
                  );
                })}
              </div>
              <label className="workshop-custom-traits">
                补充指挥偏好
                <textarea
                  rows={3}
                  value={selected.traits}
                  maxLength={800}
                  onChange={(event) => onChange({ traits: event.target.value })}
                />
                <small>
                  补充内容独立保留，不会被预设覆盖。倾向是行为偏好，不保证每次行动。
                </small>
              </label>
              <details className="workshop-advanced">
                <summary>高级设置 · 模型连接与覆盖</summary>
                <div className="form-grid">
                  <label>
                    模型连接
                    <select
                      value={selected.connectionId}
                      onChange={(event) =>
                        onChange({ connectionId: event.target.value })
                      }
                    >
                      {connections.map((connection) => (
                        <option key={connection.id} value={connection.id}>
                          {connection.name}
                        </option>
                      ))}
                    </select>
                    <small>角色与打法不随模型连接切换而改变。</small>
                  </label>
                  <label>
                    模型覆盖<span className="optional">可选</span>
                    <input
                      value={selected.modelOverride}
                      maxLength={200}
                      placeholder="留空以继承连接中的模型"
                      onChange={(event) =>
                        onChange({ modelOverride: event.target.value })
                      }
                    />
                  </label>
                </div>
              </details>
            </fieldset>
            <div className="form-footer">
              <p>
                {locked
                  ? "演练进行中，指挥方案已锁定；停止后可编辑。"
                  : "保存到本机；当前尚未连接真实模型与游戏宿主。"}
              </p>
              <Button
                kind="primary"
                onClick={onSave}
                disabled={!dirty || locked}
              >
                <FloppyDisk size={16} />
                保存指挥方案
              </Button>
            </div>
          </section>

          <section className="panel workshop-preview" aria-label="行为预览">
            <PanelHeading
              eyebrow="STYLE IN ACTION"
              title="这个指挥官会怎么打？"
            >
              <Lightbulb size={21} />
            </PanelHeading>
            <p className="workshop-preview-intro">
              随设置即时更新的行为说明，不调用模型，也不代表真实战局推演。
            </p>
            <div className="behavior-cards" aria-live="polite">
              {commanderPreview(selected).map((scenario, index) => (
                <article key={scenario.id}>
                  <span className="behavior-number">0{index + 1}</span>
                  <h3>{scenario.title}</h3>
                  <p>{scenario.text}</p>
                </article>
              ))}
            </div>
            <div className="preference-summary">
              <span className="eyebrow">当前偏好摘要</span>
              <p>{preferenceSummary(selected)}</p>
            </div>
          </section>

          <details className="panel workshop-plan">
            <summary>查看宿主适配草案</summary>
            <div className="workshop-plan-content">
              <p>
                映射现有三类人格与偏好摘要。此草案供后续适配器接线使用，保存或复制不会调用模型、修改宿主配置或授予游戏执行权。
              </p>
              <Button onClick={copyPlan}>
                <Copy size={16} />
                复制参数草案
              </Button>
              <p className="workshop-copy-status" role="status">
                {copyStatus}
              </p>
              <textarea
                aria-label="宿主适配参数草案"
                readOnly
                value={plan}
                rows={12}
                spellCheck={false}
              />
            </div>
          </details>
        </div>
      </div>
    </>
  );
}
