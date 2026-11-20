import {Binoculars, Handshake, Sword} from '@phosphor-icons/react';
import {lobbyInstructions, modeNote, playModes, type PlayMode} from '../runtime/playMode';

const icons = {ai_vs_native: Binoculars, human_with_ai: Handshake, human_vs_ai: Sword} as const;

export function LobbyInstructions({mode}: {mode: PlayMode}) {
  const note = modeNote(mode);
  return <>
    <ol className="tc-lobby-steps">
      {lobbyInstructions(mode).map(line => <li key={line}>{line}</li>)}
    </ol>
    {note && <p className="native-muted">{note}</p>}
  </>;
}

/** Step 3: choose how to play, with lobby setup generated from the choice. */
export function ModeStep({mode, onChange}: {mode: PlayMode | null; onChange: (mode: PlayMode) => void}) {
  return <section className="native-panel setup-panel tc-mode-step">
    <div className="setup-panel-heading">
      <div>
        <h2>对局模式</h2>
        <p className="setup-description">选择你想怎么玩。任何 1.12 地图都可以，下面会告诉你在游戏大厅里怎么设置。</p>
      </div>
    </div>
    <div className="tc-mode-grid" role="radiogroup" aria-label="对局模式">
      {playModes.map(option => {
        const Icon = icons[option.id];
        const checked = mode === option.id;
        return <button type="button" role="radio" aria-checked={checked} key={option.id}
          className={`tc-mode-card ${checked ? 'is-selected' : ''}`} onClick={() => onChange(option.id)}>
          <Icon size={30} weight="duotone" aria-hidden="true" />
          <strong>{option.title}</strong>
          <span className="tc-mode-tagline">{option.tagline}</span>
          <span className="tc-mode-description">{option.description}</span>
        </button>;
      })}
    </div>
    {mode && <div className="tc-lobby">
      <h3>在游戏大厅这样设置</h3>
      <LobbyInstructions mode={mode} />
      <p className="native-muted">客户端不会替你修改游戏大厅。席位或队伍组合暂不支持时，开始前会提示你。</p>
    </div>}
  </section>;
}
