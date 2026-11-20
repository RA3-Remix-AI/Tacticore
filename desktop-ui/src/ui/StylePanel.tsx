import {Button} from '../components/ui';
import type {Draft, Profile} from '../runtime/hostTypes';
import {reasonText} from '../runtime/copy';
import {
  VOICE_NOTE_MAX_BYTES, chooseCommander, commanderMeta, commanderProblem, commanderProfile, editPersonality,
  personalityParams, voiceNoteBytes, type CommanderMeta, type CommanderProfile,
} from '../runtime/commanders';

/** One commander card. Unavailable commanders are visible but cannot be chosen for a run. */
function CommanderCard({meta, pressed, disabled, onChoose}: {
  meta: CommanderMeta; pressed: boolean; disabled: boolean; onChoose: () => void;
}) {
  return <button type="button" className={`tc-commander-card ${meta.available ? '' : 'is-soon'}`} aria-pressed={pressed}
    disabled={disabled || !meta.available} onClick={onChoose}>
    <img src={meta.portrait} alt={`${meta.name}（${meta.full_name}）人物概念图`} width={96} height={120} />
    <span className="tc-commander-text">
      <strong>{meta.name} <small>{meta.codename}</small></strong>
      <span>{meta.full_name} · {meta.faction}</span>
      <em>{meta.style}：{meta.tagline}</em>
      {!meta.available && <span className="tc-soon">即将推出</span>}
    </span>
  </button>;
}

/** Nine 1..5 sliders, each with a one-line explanation of what it changes in play. */
export function PersonalityEditor({value, disabled, onChange}: {
  value: CommanderProfile; disabled: boolean; onChange: (next: CommanderProfile) => void;
}) {
  const preset = commanderMeta(value.commander_id);
  return <fieldset className="tc-personality" disabled={disabled}>
    <legend>性格 · <span className="tc-preset-name">{preset ? `${preset.name}预设` : '自定义'}</span></legend>
    <div className="tc-personality-grid">
      {personalityParams.map(param => <label key={param.key}>
        <span>{param.label}<strong>{value.personality[param.key]} / 5</strong></span>
        <input type="range" min="1" max="5" step="1" value={value.personality[param.key]} name={param.key}
          onChange={event => onChange(editPersonality(value, param.key, Number(event.target.value)))} />
        <small>{param.hint}</small>
      </label>)}
    </div>
    <p className="native-muted">纠缠度、惜兵和惩罚意识要等骚扰控制器上线后才完全生效；目前主要影响总指挥的判断。</p>
  </fieldset>;
}

/** Commander choice, personality and voice note. Saved through `profiles.save`; applied at the next start. */
export function StylePanel({profiles, selected, profile, draft, dirty, disabled, commanders, supported,
  onChoose, onEdit, onSave, onReload}: {
  profiles: Profile[]; selected: string; profile: Profile | undefined; draft: Draft | null; dirty: boolean; disabled: boolean;
  commanders: readonly CommanderMeta[]; supported: boolean;
  onChoose: (id: string) => void; onEdit: (patch: Partial<Draft>) => void; onSave: () => void; onReload: () => void;
}) {
  if (!draft || !profile) {
    return <section className="native-panel setup-panel">
      <div className="setup-panel-heading"><div><h2>指挥官</h2>
        <p className="setup-description">完成「模型与 API Key」后，这里可以选择弈核 AI 的指挥官和性格。</p></div></div>
      <Button disabled={disabled} onClick={onReload}>重新载入</Button>
    </section>;
  }
  const value = commanderProfile(draft);
  const current = commanderMeta(value.commander_id, commanders);
  const problem = supported ? commanderProblem(value, commanders) : null;
  const bytes = voiceNoteBytes(value.voice_note);
  const editing = disabled || !supported;
  const apply = (next: CommanderProfile) => onEdit({...next});
  return <section className="native-panel setup-panel tc-style">
    <div className="setup-panel-heading">
      <div>
        <h2>指挥官</h2>
        <p className="setup-description">选择弈核 AI 的指挥官和性格。性格会改变它的决策，不只是说话的语气。保存后从下一局开始生效。</p>
      </div>
      <span className={`setup-badge ${dirty ? '' : 'is-ready'}`}>{dirty ? '未保存' : '已保存'}</span>
    </div>
    {!supported && <p className="native-warning">当前后台版本还不支持指挥官设置，升级后即可保存。现在只能修改模型名称。</p>}
    {profiles.length > 1 && <label>使用哪个 AI 配置
      <select value={selected} disabled={disabled} onChange={e => onChoose(e.target.value)}>
        {profiles.map(p => <option key={p.profile_id} value={p.profile_id}>{p.name}</option>)}
      </select>
    </label>}
    <div className="tc-commanders" role="group" aria-label="指挥官">
      {commanders.map(meta => <CommanderCard key={meta.id} meta={meta} pressed={value.commander_id === meta.id}
        disabled={editing} onChoose={() => { const next = chooseCommander(meta.id, commanders); if (next) apply(next); }} />)}
    </div>
    {current
      ? <article className="tc-commander-hero">
        <img src={current.image} alt="" aria-hidden="true" />
        <div>
          <p className="eyebrow">{current.codename} · {current.faction}</p>
          <h3>{current.name} · {current.full_name}</h3>
          <p>{current.description}</p>
          <p className="native-muted">为什么难缠：{current.tough}</p>
        </div>
      </article>
      : <p className="native-muted tc-custom-note">自定义性格：参数和任何一位指挥官的预设都不同。对局里仍由当前可用的苏联席位执行。</p>}
    <PersonalityEditor value={value} disabled={editing} onChange={apply} />
    <label>口吻说明（可选）
      <textarea rows={3} value={value.voice_note} disabled={editing} placeholder="例如：说话简短，提到对手时语气带点挑衅。"
        onChange={e => apply({...value, voice_note: e.target.value})} />
      <small className={`tc-byte-counter ${bytes > VOICE_NOTE_MAX_BYTES ? 'is-over' : ''}`}>
        {bytes} / {VOICE_NOTE_MAX_BYTES} 字节
      </small>
    </label>
    <label>模型名称（可选）
      <input value={draft.model} disabled={disabled} placeholder="留空则使用「模型与 API Key」中的模型"
        onChange={e => onEdit({model: e.target.value})} />
    </label>
    {problem && <p className="native-warning">{reasonText(problem)}</p>}
    {!problem && !profile.validation.ok && <p className="native-warning">{reasonText(profile.validation.reason_code)}</p>}
    <div className="native-actions">
      <Button kind="primary" disabled={disabled || !dirty || Boolean(problem)} onClick={onSave}>保存</Button>
      <Button disabled={disabled} onClick={onReload}>放弃修改</Button>
    </div>
  </section>;
}
