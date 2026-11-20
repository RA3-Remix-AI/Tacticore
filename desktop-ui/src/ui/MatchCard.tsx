import {MapTrifold, Robot, User, Desktop} from '@phosphor-icons/react';
import {parseScenario, scenarioView, type MatchScenario, type ScenarioView} from '../runtime/scenario';
import {modeMismatch, type PlayMode} from '../runtime/playMode';
import type {DiscoveredSession} from '../runtime/openingStart';

const roleIcon = (role: string) => (role === '弈核 AI' ? Robot : role === '玩家' ? User : Desktop);

/** Map, mode and players of one match. Works with or without the scenario contract. */
export function ScenarioDetails({view}: {view: ScenarioView}) {
  return <div className="tc-scenario">
    <div className="tc-scenario-head">
      <MapTrifold size={22} weight="duotone" aria-hidden="true" />
      <div>
        <strong className="tc-scenario-map">{view.map}</strong>
        <small>{view.modeLabel}</small>
      </div>
    </div>
    {view.teams.length > 0
      ? <div className="tc-teams">
        {view.teams.map(team => <div className="tc-team" key={team.key}>
          <span className="tc-team-label">{team.label}</span>
          <ul>
            {team.players.map(player => {
              const Icon = roleIcon(player.role);
              return <li key={player.key} className={player.isModel ? 'is-model' : undefined}>
                <Icon size={16} weight={player.isModel ? 'fill' : 'regular'} aria-hidden="true" />
                <span className="tc-player-role">{player.role}</span>
                <span className="tc-player-seat">{player.seat}</span>
                {player.detail && <span className="tc-player-detail">{player.detail}</span>}
              </li>;
            })}
          </ul>
        </div>)}
      </div>
      : <p className="native-muted">{view.summary}</p>}
  </div>;
}

export function candidateView(candidate: DiscoveredSession): ScenarioView {
  return scenarioView(parseScenario(candidate.scenario), {map: candidate.map, faction: candidate.faction, player_id: candidate.player_id});
}

/**
 * Discovered candidates (selectable) or the match the AI is bound to.
 * `bound` is shown when there are no fresh candidates.
 */
export function MatchCard({candidates, selectedId, onSelect, bound, mode, disabled}: {
  candidates: DiscoveredSession[]; selectedId: string; onSelect: (id: string) => void;
  bound: {view: ScenarioView; label: string} | null; mode: PlayMode | null; disabled: boolean;
}) {
  if (candidates.length > 0) {
    const selected = candidates.find(row => row.candidate_id === selectedId) ?? (candidates.length === 1 ? candidates[0] : undefined);
    const mismatch = selected ? modeMismatch(mode, parseScenario(selected.scenario)?.mode) : null;
    return <section className="native-panel tc-match-card" aria-label="找到的对局">
      <p className="eyebrow">找到的对局</p>
      {candidates.length > 1 && <p className="native-muted">找到 {candidates.length} 个对局，请选择要使用的那一个。</p>}
      <div className="tc-candidates" role={candidates.length > 1 ? 'radiogroup' : undefined}>
        {candidates.map(candidate => {
          const checked = candidate.candidate_id === selected?.candidate_id;
          const body = <ScenarioDetails view={candidateView(candidate)} />;
          if (candidates.length === 1) return <div key={candidate.candidate_id}>{body}</div>;
          return <button type="button" role="radio" aria-checked={checked} disabled={disabled} key={candidate.candidate_id}
            className={`tc-candidate ${checked ? 'is-selected' : ''}`} onClick={() => onSelect(candidate.candidate_id)}>
            {body}
          </button>;
        })}
      </div>
      {mismatch && <p className="native-warning">{mismatch}</p>}
    </section>;
  }
  if (bound) {
    return <section className="native-panel tc-match-card" aria-label="当前对局">
      <p className="eyebrow">{bound.label}</p>
      <ScenarioDetails view={bound.view} />
    </section>;
  }
  return <section className="native-panel tc-match-card is-empty" aria-label="对局">
    <p className="eyebrow">对局</p>
    <MapTrifold size={34} weight="thin" aria-hidden="true" />
    <p className="native-muted">还没有找到对局。在游戏里开始一局遭遇战后，点击「查找对局」。</p>
  </section>;
}

export function boundView(scenario: MatchScenario | null, session: {map?: string; faction?: string} | null | undefined): ScenarioView {
  return scenarioView(scenario, {map: session?.map, faction: session?.faction});
}
