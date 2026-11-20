import {Button} from '../components/ui';
import type {Run} from '../runtime/hostTypes';
import {eventDescription, localPreparationDescription} from '../runtime/nativeProcess';
import {releaseText, runStateLabels} from '../runtime/copy';
import type {MacroStrategyView} from '../runtime/macroStrategyView';
import type {StrategicCommandView} from '../runtime/strategicCommandView';
import type {StrategicReevaluationView} from '../runtime/strategicReevaluationView';
import type {StrategicLifecycleView} from '../runtime/strategicLifecycleView';
import type {ModelCallView} from '../runtime/modelCallView';

const taskStages: Record<string, string> = {
  planned: '等待', dispatch_pending: '待下达', active: '执行中', started: '已开始', stopping: '正在停止',
  completed: '已完成', failed: '失败', blocked: '受阻', cancelled: '已取消', unavailable: '不可用',
};
const moduleNames: Record<string, string> = {
  build: '生产', attack: '主攻', raid: '骚扰', combined_arms: '协同', recon: '侦察', local_maneuver: '局部机动',
};
const number = (value: number | undefined) => (value === undefined ? '—' : value.toLocaleString('zh-CN'));

export interface DetailsData {
  run: Run | null;
  current: Run | undefined;
  historical: boolean;
  observedAt: number | null;
  application: {applied: boolean; called: boolean; responded: boolean};
  modelCall: ModelCallView;
  strategy: MacroStrategyView;
  strategic: StrategicCommandView;
  unifiedRows: string[];
  reevaluation: StrategicReevaluationView;
  lifecycle: StrategicLifecycleView | null;
  nativeMacro: boolean;
}

function Fact({label, children}: {label: string; children: React.ReactNode}) {
  return <><dt>{label}</dt><dd>{children}</dd></>;
}

/**
 * Everything internal: identifiers, release verification, host receipts,
 * native observations, tasks and raw events. Collapsed by default.
 */
export function DetailsPanel({data, busy, onDownload, onResume, onQuery}: {
  data: DetailsData; busy: boolean; onDownload: () => void; onResume: () => void; onQuery: () => void;
}) {
  const {run, current, strategy, strategic, reevaluation, lifecycle} = data;
  return <details className="native-panel tc-details">
    <summary>详细信息与诊断</summary>
    <p className="native-muted">这里是给排查问题用的技术信息。反馈问题时，请附上「下载诊断信息」生成的文件（不包含 API Key、模型输入或原始日志正文）。</p>
    <div className="native-actions">
      <Button disabled={busy || !run} onClick={onDownload}>下载诊断信息</Button>
      <Button disabled={busy} onClick={onResume}>重新连接已有对局</Button>
      {run && <Button disabled={busy} onClick={onQuery}>刷新状态</Button>}
    </div>

    {!run && <p className="native-muted">还没有运行记录。</p>}
    {run && <>
      <h3>运行</h3>
      <dl className="native-facts">
        <Fact label="状态">{runStateLabels[run.state] ?? run.state}</Fact>
        <Fact label="游戏控制">{releaseText(run.native_release_verified)}</Fact>
        <Fact label="运行编号"><code>{run.run_id}</code></Fact>
        <Fact label="对局编号"><code>{run.session_id}</code></Fact>
        {data.observedAt && <Fact label="最后同步">{new Date(data.observedAt).toLocaleTimeString('zh-CN')}</Fact>}
        {current?.latest_snapshot?.game_time_seconds !== undefined && <Fact label="游戏时间">
          {Math.floor(current.latest_snapshot.game_time_seconds)} 秒{current.latest_snapshot.paused ? '（暂停）' : ''}
        </Fact>}
        {current?.latest_snapshot?.resources && <Fact label="资金">{number(current.latest_snapshot.resources.credits)}</Fact>}
        <Fact label="模型请求">{number(run.metrics?.requests)} 次，采纳 {number(run.metrics?.accepted)} 次</Fact>
        <Fact label="任务">
          下达 {number(run.task_counters?.dispatches)} · 完成 {number(run.task_counters?.completed)} · 受阻 {number(run.task_counters?.blocked)}
        </Fact>
        {run.reason_code && <Fact label="原因代码"><code>{run.reason_code}</code></Fact>}
      </dl>
      {data.historical && <p className="native-muted">这是上一局的记录，不代表当前游戏状态。</p>}
      {current?.status_stale && <p className="native-warning">状态已过期，以上是最后一次记录。</p>}
      <p className="native-muted">「停止」和「游戏控制已交还」分别确认：游戏结束或进程退出，不等于控制已交还。</p>

      <h3>模型调用</h3>
      <dl className="native-facts">
        <Fact label="AI 设置">{data.application.applied ? '已应用当前设置' : '等待确认'}</Fact>
        <Fact label="模型">{data.application.responded ? '已收到响应' : data.application.called ? '已发起调用' : '还没有调用'}</Fact>
        <Fact label="最近一次">{data.modelCall.title}</Fact>
      </dl>
      <p className="native-muted">{data.modelCall.detail}</p>

      {data.nativeMacro && <>
        <h3>战略记录（游戏内 AI 反馈）</h3>
        <dl className="native-facts">
          <Fact label="当前目标">{strategy.objective}</Fact>
          <Fact label="阶段">{strategy.phase}</Fact>
          <Fact label="期待变化">{strategy.expectation}</Fact>
          <Fact label="最近结果">{strategy.latest}</Fact>
          <Fact label="当前意图">{strategic.current}</Fact>
          <Fact label="资源倾向">{strategic.budget}</Fact>
          <Fact label="本局能力">{strategic.capabilities}</Fact>
          {data.unifiedRows.length > 0 && <Fact label="游戏内反馈">{data.unifiedRows.map(row => <p key={row}>{row}</p>)}</Fact>}
          <Fact label="效果判断">{strategic.evidence}</Fact>
        </dl>
        {reevaluation.available && reevaluation.history.length > 0 && <>
          <h4>效果与重新评估</h4>
          <ol>{reevaluation.history.map((row, index) => <li key={index}>{row}</li>)}</ol>
          <p className="native-muted">{reevaluation.next}</p>
        </>}
        {lifecycle && <p className="native-muted">{lifecycle.next} {lifecycle.reason}</p>}
      </>}

      <h3>任务</h3>
      {run.tasks?.length ? <ul className="native-tasks">
        {run.tasks.map(task => <li key={task.task_id}>
          <strong>{moduleNames[task.module ?? ''] ?? '任务'} · {taskStages[task.status ?? ''] ?? '等待确认'}</strong>
          <span>{task.purpose ?? '—'}{task.budget ? ` · 预算 ${Math.round(task.budget.fraction * 100)}%` : ''}</span>
          {task.reason_code && <small>{task.reason_code}</small>}
        </li>)}
      </ul> : <p className="native-muted">没有任务记录。</p>}
      {current?.local_preparation && <p className="native-muted">局部机动：{localPreparationDescription(current.local_preparation.state)}</p>}

      <h3>事件</h3>
      {run.events_cursor && <p className="native-muted">
        显示 {run.events?.length ?? 0} / {run.events_cursor.total_count} 条{run.events_cursor.truncated ? '（较早的记录在诊断文件中）' : ''}。
      </p>}
      <ol className="native-events">
        {run.events?.map(event => <li key={event.seq}>
          <span>{eventDescription(event)}</span>
          <time dateTime={event.created_at}>{new Date(event.created_at).toLocaleTimeString('zh-CN')}</time>
        </li>)}
      </ol>
    </>}
  </details>;
}
