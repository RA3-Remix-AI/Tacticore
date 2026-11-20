import {Button, CommanderIcon} from '../components/ui';
import {commanderPreview, preferenceAxes, preferencePresets} from '../state/preferences';
import type {Draft, Profile} from '../runtime/hostTypes';
import {reasonText} from '../runtime/copy';

/** Optional AI playing style. Saved through `profiles.save`; applied at the next start. */
export function StylePanel({profiles, selected, profile, draft, dirty, disabled, onChoose, onEdit, onSave, onReload}: {
  profiles: Profile[]; selected: string; profile: Profile | undefined; draft: Draft | null; dirty: boolean; disabled: boolean;
  onChoose: (id: string) => void; onEdit: (patch: Partial<Draft>) => void; onSave: () => void; onReload: () => void;
}) {
  if (!draft || !profile) {
    return <section className="native-panel setup-panel">
      <div className="setup-panel-heading"><div><h2>AI 风格</h2>
        <p className="setup-description">完成「模型与 API Key」后，这里可以调整弈核 AI 的打法。</p></div></div>
      <Button disabled={disabled} onClick={onReload}>重新载入</Button>
    </section>;
  }
  const preferences = draft.preferences ?? preferencePresets.find(p => p.doctrine === draft.doctrine)?.values ?? preferencePresets[1].values;
  return <section className="native-panel setup-panel tc-style">
    <div className="setup-panel-heading">
      <div>
        <h2>AI 风格</h2>
        <p className="setup-description">可选。调整弈核 AI 的打法倾向，保存后从下一局开始生效。</p>
      </div>
      <span className={`setup-badge ${dirty ? '' : 'is-ready'}`}>{dirty ? '未保存' : '已保存'}</span>
    </div>
    {profiles.length > 1 && <label>使用哪个 AI
      <select value={selected} disabled={disabled} onChange={e => onChoose(e.target.value)}>
        {profiles.map(p => <option key={p.profile_id} value={p.profile_id}>{p.name}</option>)}
      </select>
    </label>}
    <fieldset className="nw-presets" disabled={disabled}>
      <legend>打法</legend>
      <div>
        {preferencePresets.map(preset => <button type="button" key={preset.id} aria-pressed={preferences.preset === preset.id}
          onClick={() => onEdit({doctrine: preset.doctrine, preferences: {...preset.values}})}>
          <CommanderIcon doctrine={preset.doctrine} size={25} />
          <strong>{preset.label}</strong>
          <span>{preset.description}</span>
        </button>)}
      </div>
    </fieldset>
    <details className="setup-details">
      <summary>细调倾向</summary>
      <div className="native-axes">
        {preferenceAxes.map(axis => <label key={axis.key}>
          <span>{axis.label}<strong>{preferences[axis.key]} / 5</strong></span>
          <input type="range" min="1" max="5" step="1" value={preferences[axis.key]} disabled={disabled}
            onChange={e => onEdit({preferences: {...preferences, preset: 'custom', [axis.key]: Number(e.target.value)}})} />
          <small>{axis.descriptions[preferences[axis.key] - 1]}</small>
        </label>)}
      </div>
      <div className="nw-style-preview">
        <h3>同样的战况，不同的判断</h3>
        <p className="native-muted">只用来说明这种倾向，不代表实际对局结果。</p>
        <div>{commanderPreview({doctrine: draft.doctrine, preferences}).map(scene => <article key={scene.id}>
          <h4>{scene.title}</h4><p>{scene.text}</p>
        </article>)}</div>
      </div>
    </details>
    <label>补充要求（可选）
      <textarea rows={3} value={draft.custom_traits} disabled={disabled} placeholder="例如：优先保护矿车，不要过早进攻。"
        onChange={e => onEdit({custom_traits: e.target.value})} />
    </label>
    <label>模型名称（可选）
      <input value={draft.model} disabled={disabled} placeholder="留空则使用「模型与 API Key」中的模型"
        onChange={e => onEdit({model: e.target.value})} />
    </label>
    {!profile.validation.ok && <p className="native-warning">{reasonText(profile.validation.reason_code)}</p>}
    <div className="native-actions">
      <Button kind="primary" disabled={disabled || !dirty} onClick={onSave}>保存风格</Button>
      <Button disabled={disabled} onClick={onReload}>放弃修改</Button>
    </div>
  </section>;
}
