import {Brain, Warning} from '@phosphor-icons/react';
import {currentStrategy, decisionRow, isMatchEnd, type DecisionRecord, type DecisionStreamRecord} from '../runtime/decisions';

export type FeedState = 'idle' | 'loading' | 'ok' | 'unavailable' | 'error';

export function DecisionItem({record}: {record: DecisionRecord}) {
  const row = decisionRow(record);
  return <li className={`tc-decision tone-${row.badge.tone}`}>
    <div className="tc-decision-head">
      <time className="tc-clock">{row.clock}</time>
      <div className="tc-intents">
        {row.intents.length
          ? row.intents.map(label => <span className="tc-intent" key={label}>{label}</span>)
          : <span className="tc-intent is-empty">{row.failed ? '模型没有给出决定' : '保持当前部署'}</span>}
      </div>
      <span className={`tc-badge tone-${row.badge.tone}`}>{row.badge.label}</span>
    </div>
    {row.objective && <p className="tc-objective">{row.objective}</p>}
    {row.reasoning && <p className="tc-reasoning">{row.reasoning}</p>}
    {row.threats.length > 0 && <p className="tc-threats"><Warning size={14} aria-hidden="true" /> {row.threats.join('；')}</p>}
    {row.reason && <p className="tc-reason">{row.reason}</p>}
    {row.effects.length > 0 && <ul className="tc-effects">{row.effects.map(effect => <li key={effect}>{effect}</li>)}</ul>}
    {row.modelLine && <small className="tc-model-line">{row.modelLine}</small>}
  </li>;
}

/** Ordered list of decisions. `newestFirst` for the live feed, chronological for review. */
export function DecisionList({records, newestFirst}: {records: readonly DecisionStreamRecord[]; newestFirst: boolean}) {
  const decisions = records.filter((row): row is DecisionRecord => !isMatchEnd(row));
  const ordered = newestFirst ? [...decisions].reverse() : decisions;
  return <ol className="tc-timeline">{ordered.map(record => <DecisionItem key={record.seq} record={record} />)}</ol>;
}

function feedMessage(state: FeedState, live: boolean): string | null {
  if (state === 'unavailable') return '当前版本的后台还没有提供决策记录。弈核 AI 照常工作，详细信息里仍可查看运行状态。';
  if (state === 'error') return '暂时读不到决策记录，稍后会自动重试。';
  if (state === 'loading') return '正在读取决策记录…';
  if (state === 'idle') return live ? null : '开始对局后，这里会实时显示弈核 AI 的每次判断和理由。';
  return null;
}

/** Live decision feed: current strategy on top, then the newest decisions. */
export function DecisionFeed({records, state, live, mock}: {
  records: readonly DecisionStreamRecord[]; state: FeedState; live: boolean; mock: boolean;
}) {
  const strategy = currentStrategy(records);
  const message = feedMessage(state, live);
  return <section className="native-panel tc-feed" aria-label="AI 决策">
    <div className="tc-feed-head">
      <p className="eyebrow">AI 在想什么</p>
      {mock && <span className="tc-pill is-mock">示例数据</span>}
    </div>
    <div className="tc-strategy">
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
    </div>
    {message && <p className="native-muted tc-feed-message">{message}</p>}
    {records.length > 0 && <DecisionList records={records} newestFirst />}
    <p className="native-muted tc-feed-foot">弈核 AI 只决定大方向；具体建什么、造多少、怎么操作部队，由游戏自带的 AI 完成。</p>
  </section>;
}
