import {Trophy, SmileySad, Question, ArrowClockwise} from '@phosphor-icons/react';
import {Button} from '../components/ui';
import {reviewStats, type DecisionStreamRecord} from '../runtime/decisions';
import type {ScenarioView} from '../runtime/scenario';
import {ScenarioDetails} from './MatchCard';
import {DecisionList, type FeedState} from './DecisionFeed';

const resultIcon = {victory: Trophy, defeat: SmileySad, unknown: Question} as const;

function Stat({label, value, tone}: {label: string; value: string | number; tone?: string}) {
  return <div className={`tc-stat ${tone ? `tone-${tone}` : ''}`}>
    <strong>{value}</strong>
    <small>{label}</small>
  </div>;
}

/** Post-match review for the last run. */
export function ReviewPage({hasRun, live, records, state, mock, scenario, onRefresh, busy}: {
  hasRun: boolean; live: boolean; records: readonly DecisionStreamRecord[]; state: FeedState; mock: boolean;
  scenario: ScenarioView | null; onRefresh: () => void; busy: boolean;
}) {
  if (!hasRun) {
    return <section className="native-panel tc-review is-empty">
      <h2>还没有可以复盘的对局</h2>
      <p className="native-muted">完成一局后，这里会显示结果、AI 的每次决定和统计。</p>
    </section>;
  }
  const stats = reviewStats(records);
  const Icon = resultIcon[stats.result];
  return <div className="tc-review">
    <section className={`native-panel tc-review-head result-${stats.result}`}>
      <Icon size={44} weight="duotone" aria-hidden="true" />
      <div>
        <p className="eyebrow">{live ? '对局进行中' : '复盘'}{mock ? ' · 示例数据' : ''}</p>
        <h2>{live ? '对局还在进行' : stats.resultLabel}</h2>
        <p className="native-muted">时长 {stats.duration}</p>
      </div>
      <Button disabled={busy} onClick={onRefresh}><ArrowClockwise size={16} /> 刷新</Button>
    </section>
    {state === 'unavailable' && <p className="native-warning">当前版本的后台还没有提供决策记录，暂时只能查看诊断信息。</p>}
    {state === 'error' && <p className="native-warning">暂时读不到决策记录，请稍后刷新。</p>}
    <section className="native-panel tc-stats" aria-label="统计">
      <Stat label="决策次数" value={stats.decisions} />
      <Stat label="已执行" value={stats.applied} tone="good" />
      <Stat label="未采纳" value={stats.rejected} tone={stats.rejected ? 'bad' : undefined} />
      <Stat label="结果未知" value={stats.unknown} tone={stats.unknown ? 'warn' : undefined} />
      <Stat label="已过期" value={stats.expired} />
      <Stat label="平均响应" value={stats.averageLatencyMs === null ? '—' : `${(stats.averageLatencyMs / 1000).toFixed(1)} 秒`} />
    </section>
    <div className="tc-review-grid">
      {scenario && <section className="native-panel"><p className="eyebrow">对局</p><ScenarioDetails view={scenario} /></section>}
      <section className="native-panel">
        <p className="eyebrow">最常用的决定</p>
        {stats.topIntents.length
          ? <ol className="tc-top-intents">{stats.topIntents.map(row => <li key={row.label}><span>{row.label}</span><strong>{row.count}</strong></li>)}</ol>
          : <p className="native-muted">没有记录。</p>}
        {stats.modelErrors > 0 && <p className="native-warning">有 {stats.modelErrors} 次模型调用出错。可以在「设置 → 模型与 API Key」中测试连接。</p>}
      </section>
    </div>
    <section className="native-panel">
      <p className="eyebrow">决策时间线</p>
      {records.length ? <DecisionList records={records} newestFirst={false} /> : <p className="native-muted">没有决策记录。</p>}
    </section>
  </div>;
}
