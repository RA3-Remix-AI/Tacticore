import {useState} from 'react';
import {Brain, Warning} from '@phosphor-icons/react';
import {
  currentDirective, currentStrategy, decisionRow, decisionsOf, filterByLayer, layerCounts, runInfo,
  type DecisionRecord, type DecisionStreamRecord, type DirectiveView, type LayerFilter,
} from '../runtime/decisions';
import {CommanderAvatar} from './CommanderAvatar';

export type FeedState = 'idle' | 'loading' | 'ok' | 'unavailable' | 'error';
type Badge = {name: string; portrait: string | null};

export function DecisionItem({record}: {record: DecisionRecord}) {
  const row = decisionRow(record);
  const empty = row.failed ? '模型没有给出决定' : row.dropped.length ? '没有采纳的动作' : '保持当前部署';
  return <li className={`tc-decision tone-${row.badge.tone} ${row.layer ? `layer-${row.layer}` : ''}`}>
    <div className="tc-decision-head">
      <time className="tc-clock">{row.clock}</time>
      {row.commander && <CommanderAvatar commander={row.commander} size={24} />}
      {row.layerLabel && <span className={`tc-layer layer-${row.layer}`}>{row.layerLabel}</span>}
      <div className="tc-intents">
        {row.intents.length
          ? row.intents.map(label => <span className="tc-intent" key={label}>{label}</span>)
          : <span className="tc-intent is-empty">{empty}</span>}
      </div>
      <span className={`tc-badge tone-${row.badge.tone}`}>{row.badge.label}</span>
    </div>
    {row.directiveLine && <p className="tc-objective">{row.directiveLine}</p>}
    {row.objective && <p className="tc-objective">{row.objective}</p>}
    {row.reasoning && <p className="tc-reasoning">{row.reasoning}</p>}
    {row.threats.length > 0 && <p className="tc-threats"><Warning size={14} aria-hidden="true" /> {row.threats.join('；')}</p>}
    {row.reason && <p className="tc-reason">{row.reason}</p>}
    {row.dropped.map(text => <p className="tc-dropped" key={text}>{text}</p>)}
    {row.recordedOnly && <p className="tc-recorded-only">{row.recordedOnly}</p>}
    {row.effects.length > 0 && <ul className="tc-effects">{row.effects.map(effect => <li key={effect}>{effect}</li>)}</ul>}
    {row.modelLine && <small className="tc-model-line">{row.modelLine}</small>}
  </li>;
}

/** Ordered list of decisions. `newestFirst` for the live feed, chronological for review. */
export function DecisionList({records, newestFirst}: {records: readonly DecisionStreamRecord[]; newestFirst: boolean}) {
  const decisions = decisionsOf(records);
  const ordered = newestFirst ? [...decisions].reverse() : decisions;
  return <ol className="tc-timeline">{ordered.map(record => <DecisionItem key={record.seq} record={record} />)}</ol>;
}

/** Layer filter chips over a decision list. Without layered records (older backend) only the list is shown. */
export function LayeredTimeline({records, newestFirst, initial = 'all'}: {
  records: readonly DecisionStreamRecord[]; newestFirst: boolean; initial?: LayerFilter;
}) {
  const [layer, setLayer] = useState<LayerFilter>(initial);
  const counts = layerCounts(records);
  const chips: {id: LayerFilter; label: string; count: number}[] = [
    {id: 'all', label: '全部', count: decisionsOf(records).length},
    ...counts.map(row => ({id: row.layer, label: row.label, count: row.count})),
  ];
  return <>
    {counts.length > 0 && <div className="tc-layer-chips" role="group" aria-label="按决策层筛选">
      {chips.map(chip => <button type="button" key={chip.id} aria-pressed={layer === chip.id}
        className={`tc-chip layer-${chip.id}`} onClick={() => setLayer(chip.id)}>
        {chip.label} <small>{chip.count}</small>
      </button>)}
    </div>}
    <DecisionList records={filterByLayer(records, counts.length ? layer : 'all')} newestFirst={newestFirst} />
  </>;
}

/** "当前方针": route, resource split, primary enemy and overrides from the latest commander directive. */
export function DirectiveBanner({directive}: {directive: DirectiveView}) {
  return <div className="tc-directive" aria-label="当前方针">
    {directive.commander && <CommanderAvatar commander={directive.commander} size={48} />}
    <div>
      <p className="eyebrow">当前方针 · {directive.since} 起{directive.validFor ? ` · 有效 ${directive.validFor}` : ''}</p>
      <h2>{directive.route}{directive.primaryEnemy ? <small> · 主攻 {directive.primaryEnemy}</small> : null}</h2>
      {directive.shares.length > 0 && <div className="tc-split" role="img"
        aria-label={`资源分配：${directive.shares.map(row => `${row.label} ${row.percent}%`).join('，')}`}>
        {directive.shares.map(row => <span key={row.key} className={`split-${row.key}`} style={{flexGrow: row.percent}}
          title={`${row.label} ${row.percent}%`}>{row.percent >= 12 ? `${row.label} ${row.percent}%` : ''}</span>)}
      </div>}
      {directive.overrides.length > 0 && <div className="tc-overrides">
        {directive.overrides.map(name => <span className="tc-override" key={name}>{name}</span>)}
      </div>}
      {directive.reasoning && <p className="tc-reasoning">{directive.reasoning}</p>}
    </div>
  </div>;
}

function feedMessage(state: FeedState, live: boolean): string | null {
  if (state === 'unavailable') return '当前版本的后台还没有提供决策记录。弈核 AI 照常工作，详细信息里仍可查看运行状态。';
  if (state === 'error') return '暂时读不到决策记录，稍后会自动重试。';
  if (state === 'loading') return '正在读取决策记录…';
  if (state === 'idle') return live ? null : '开始对局后，这里会实时显示弈核 AI 的每次判断和理由。';
  return null;
}

/** Live decision feed: current directive (or strategy) on top, then the newest decisions. */
export function DecisionFeed({records, state, live, mock, commander}: {
  records: readonly DecisionStreamRecord[]; state: FeedState; live: boolean; mock: boolean;
  /** The selected commander, shown until the run reports its own. */
  commander?: Badge | null;
}) {
  const directive = currentDirective(records);
  const strategy = currentStrategy(records);
  const message = feedMessage(state, live);
  const shown = runInfo(records).commander ?? commander ?? null;
  return <section className="native-panel tc-feed" aria-label="AI 决策">
    <div className="tc-feed-head">
      <p className="eyebrow">AI 在想什么</p>
      {shown && <span className="tc-feed-commander"><CommanderAvatar commander={shown} size={28} /> {shown.name}</span>}
      {mock && <span className="tc-pill is-mock">示例数据</span>}
    </div>
    {directive
      ? <DirectiveBanner directive={directive} />
      : <div className="tc-strategy">
        <Brain size={28} weight="duotone" aria-hidden="true" />
        <div>
          <h2>{strategy.objective}</h2>
          {strategy.available && <p className="native-muted">
            {strategy.since} 起{strategy.intents.length ? ` · ${strategy.intents.join('、')}` : ''}
            {strategy.credits !== null ? ` · 资金 ${strategy.credits.toLocaleString('zh-CN')}` : ''}
            {strategy.army !== null ? ` · 部队 ${strategy.army}` : ''}
          </p>}
          {strategy.reasoning && <p className="tc-reasoning">{strategy.reasoning}</p>}
        </div>
      </div>}
    {message && <p className="native-muted tc-feed-message">{message}</p>}
    {records.length > 0 && <LayeredTimeline records={records} newestFirst />}
    <p className="native-muted tc-feed-foot">弈核 AI 只决定大方向；具体建什么、造多少、怎么操作部队，由游戏自带的 AI 完成。</p>
  </section>;
}
