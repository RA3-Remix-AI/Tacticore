import type { DemoScenario, DesktopRuntime, OperationResult, RuntimeProfile, RuntimeRequest, RuntimeSnapshot, SessionRequest, StartRequest } from './types';

export interface DemoOptions {
  profile?: RuntimeProfile;
  now?: () => number;
  checkDelayMs?: number;
  stopDelayMs?: number;
  tickMs?: number;
}

const result = (ok: boolean, code: string, message: string): OperationResult => ({ ok, code, message });
const defaultProfile = { id: 'iron', name: '铁锤', revision: 1 };

/** Local simulation only: never imports Tauri IPC, accesses the game, or sends a request. */
export function createDemoRuntime(options: DemoOptions = {}): DesktopRuntime {
  return createRuntime('demo', options);
}

/** Native mode deliberately fails closed until the separately developed adapter exists. */
export function createDisconnectedRuntime(options: DemoOptions = {}): DesktopRuntime {
  return createRuntime('native', options);
}

function createRuntime(mode: 'demo' | 'native', options: DemoOptions): DesktopRuntime {
  const now = options.now ?? Date.now;
  let scenario: DemoScenario = 'ready';
  let epoch = 0;
  let serial = 0;
  let disposed = false;
  let tick: ReturnType<typeof setInterval> | undefined;
  const listeners = new Set<() => void>();
  const pending = new Set<() => void>();
  const requests = new Map<string, { fingerprint: string; promise: Promise<OperationResult> }>();
  let state: RuntimeSnapshot = {
    schemaVersion: 1, mode, adapterConnected: false, state: 'idle', revision: 0,
    profile: { ...(options.profile ?? defaultProfile) }, session: null, readiness: null, observing: true,
    reason: mode === 'native' ? { code: 'adapter_unavailable', message: 'Windows 游戏适配层尚未连接', action: '可切换离线演示；真实接入由 Windows 端完成。' } : null,
    capabilities: [
      { id: 'observation', label: '战场感知', status: mode === 'demo' ? 'demo' : 'unavailable', detail: '演示数据；没有读取真实战场' },
      { id: 'decision', label: '指挥决策', status: mode === 'demo' ? 'demo' : 'unavailable', detail: '预设离线流程；没有调用通用模型' },
      { id: 'execution', label: '任务调度', status: mode === 'demo' ? 'demo' : 'unavailable', detail: '模拟任务；不向游戏发送指令' },
      { id: 'multi-agent', label: '多 Agent 协作', status: 'planned', detail: '后续探索，当前未接入' },
    ],
    tasks: [], logs: [], metrics: { decisions: 0, completed: 0, elapsedSeconds: 0 },
  };

  function publish(update: Partial<RuntimeSnapshot>) {
    if (disposed) return;
    const wasObserving = state.observing;
    state = { ...state, ...update, revision: state.revision + 1 };
    if (state.observing || wasObserving) for (const listener of listeners) listener();
  }
  function log(message: string, level: 'info' | 'warning' | 'error' = 'info') {
    publish({ logs: [...state.logs, { id: `log-${++serial}`, at: now(), level, message }].slice(-100) });
  }
  function reject(code: string, message: string, action: string) {
    publish({ state: 'fault', readiness: null, reason: { code, message, action } });
    log(message, 'warning');
    return result(false, code, message);
  }
  function validate(request: RuntimeRequest): OperationResult | null {
    if (disposed) return result(false, 'disposed', '观察器已关闭');
    if (!request.requestId.trim()) return result(false, 'invalid_request', '请求缺少唯一编号');
    if (request.profileId !== state.profile.id || request.profileRevision !== state.profile.revision) return result(false, 'configuration_changed', '指挥官配置已改变，请重新检查');
    return null;
  }
  function execute(kind: string, request: RuntimeRequest, action: () => Promise<OperationResult>): Promise<OperationResult> {
    const invalid = validate(request);
    if (invalid) return Promise.resolve(invalid);
    const fingerprint = JSON.stringify([kind, request]);
    const prior = requests.get(request.requestId);
    if (prior) return prior.fingerprint === fingerprint ? prior.promise : Promise.resolve(result(false, 'request_conflict', '请求编号已用于另一项操作'));
    // Reserve before the action starts so duplicate concurrent clicks share one outcome.
    const promise = Promise.resolve().then(action);
    requests.set(request.requestId, { fingerprint, promise });
    // Bounded request history is per provider lifetime; real adapter must persist dispatch receipts.
    if (requests.size > 200) requests.delete(requests.keys().next().value!);
    return promise;
  }
  function delay(ms: number, signal?: AbortSignal): Promise<boolean> {
    return new Promise(resolve => {
      let timer: ReturnType<typeof setTimeout>;
      const finish = (completed: boolean) => {
        clearTimeout(timer); signal?.removeEventListener('abort', abort); pending.delete(cancel); resolve(completed);
      };
      const abort = () => finish(false);
      const cancel = () => finish(false);
      pending.add(cancel);
      timer = setTimeout(() => finish(true), ms);
      signal?.addEventListener('abort', abort, { once: true });
      if (signal?.aborted || disposed) finish(false);
    });
  }
  function clearTick() { if (tick !== undefined) clearInterval(tick); tick = undefined; }
  function canEdit() { return !['running', 'stopping'].includes(state.state); }
  function invalidate() { epoch++; for (const cancel of [...pending]) cancel(); }
  function nativeUnavailable() { return reject('adapter_unavailable', 'Windows 游戏适配层尚未连接', '此版本只能离线演示；请勿填写真实密钥。'); }

  return {
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    selectProfile(profile) {
      if (disposed) return result(false, 'disposed', '观察器已关闭');
      if (!canEdit()) return result(false, 'session_active', '请先停止当前指挥，再修改档案');
      if (!profile.id.trim() || !Number.isInteger(profile.revision) || profile.revision < 1) return result(false, 'invalid_profile', '档案编号或版本无效');
      invalidate();
      publish({ profile: { ...profile }, state: 'idle', session: null, readiness: null, reason: null, tasks: [] });
      return result(true, 'profile_selected', '档案已更换，需要重新检查');
    },
    setScenario(value) {
      if (disposed) return result(false, 'disposed', '观察器已关闭');
      if (!canEdit()) return result(false, 'session_active', '运行期间不能更换演示场景');
      invalidate(); scenario = value;
      publish({ state: 'idle', session: null, readiness: null, reason: null, tasks: [] });
      return result(true, 'scenario_selected', '演示场景已切换');
    },
    check(request, signal) {
      return execute('check', request, async () => {
        const invalid = validate(request); if (invalid) return invalid;
        if (mode === 'native') return nativeUnavailable();
        if (!canEdit()) return result(false, 'session_active', '当前会话仍在运行');
        invalidate(); const operation = epoch;
        publish({ state: 'checking', session: null, readiness: null, reason: null });
        log('正在检查演示会话与配置；没有连接真实游戏。');
        const complete = await delay(options.checkDelayMs ?? 650, signal);
        if (operation !== epoch || disposed) return result(false, 'superseded', '检查已被新配置或请求替代');
        if (!complete) { publish({ state: 'idle', reason: null }); log('已取消检查。'); return result(false, 'cancelled', '检查已取消'); }
        if (scenario === 'no-game') return reject('game_not_found', '没有找到可用游戏会话（演示）', '选择“就绪场景”体验流程；真实游戏接入尚待实现。');
        if (scenario === 'stale') return reject('stale_session', '会话信息已过期（演示）', '刷新检查；不要沿用历史会话授权。');
        if (scenario === 'failure') return reject('check_failed', '能力检查未通过（演示）', '查看诊断说明，或切换就绪场景重新检查。');
        const session = { id: `demo-session-${++serial}`, map: '工业区 · 离线示意', playerName: state.profile.name, faction: '苏联' };
        publish({ state: 'ready', session, readiness: { token: `demo-ready-${++serial}`, expiresAt: now() + 20_000 }, reason: null });
        if (disposed || operation !== epoch) return result(false, 'superseded', '检查已被新配置或请求替代');
        log('演示检查通过，20 秒内可开始离线推演。');
        if (disposed || operation !== epoch) return result(false, 'superseded', '检查已被新配置或请求替代');
        return result(true, 'ready', '离线演示已就绪');
      });
    },
    start(request: StartRequest) {
      return execute('start', request, async () => {
        const invalid = validate(request); if (invalid) return invalid;
        if (mode === 'native') return nativeUnavailable();
        if (state.state !== 'ready') return result(false, 'not_ready', '请先检查启动条件');
        if (!state.session || request.sessionId !== state.session.id || request.readyToken !== state.readiness?.token) return result(false, 'binding_changed', '会话或检查令牌不匹配');
        if (now() >= state.readiness.expiresAt) return reject('readiness_expired', '启动检查已过期', '重新检查当前会话后再开始。');
        const operation = epoch;
        publish({ state: 'running', readiness: null, reason: null, metrics: { decisions: 0, completed: 0, elapsedSeconds: 0 }, tasks: [{ id: 'demo-task-1', title: '控制前沿交汇点', stage: '感知', detail: '整理示意地形与已知信息，建立共同判断。' }] });
        if (disposed || operation !== epoch) return result(false, 'superseded', '启动观察器已关闭或会话已改变');
        log('离线指挥演示开始；没有模型请求与游戏命令。');
        if (disposed || operation !== epoch) return result(false, 'superseded', '启动观察器已关闭或会话已改变');
        clearTick();
        let step = 0;
        const phases = [
          ['感知', '整理示意地形与已知信息，建立共同判断。'],
          ['推演', '比较正面与侧翼两条路线，评估协同窗口。'],
          ['决策', '保留支援力量，选择当前推进方向。'],
          ['调度', '示意前排推进与后排接应，不执行游戏指令。'],
          ['反馈', '记录本轮模拟结果，进入下一轮判断。'],
        ];
        tick = setInterval(() => {
          if (disposed || state.state !== 'running') return;
          step++;
          const phase = phases[step % phases.length]!;
          publish({ tasks: [{ id: 'demo-task-1', title: '控制前沿交汇点', stage: phase[0]!, detail: phase[1]! }], metrics: { decisions: Math.floor(step / 5) + 1, completed: Math.floor(step / 5), elapsedSeconds: Math.floor(step * (options.tickMs ?? 1800) / 1000) } });
          if (step % 5 === 0) log('一轮离线推演完成，结果仅用于展示产品流程。');
        }, options.tickMs ?? 1800);
        return result(true, 'started', '离线演示正在运行');
      });
    },
    stop(request: SessionRequest) {
      return execute('stop', request, async () => {
        const invalid = validate(request); if (invalid) return invalid;
        if (mode === 'native') return nativeUnavailable();
        if (request.sessionId !== state.session?.id) return result(false, 'binding_changed', '停止请求不属于当前会话');
        if (state.state === 'stopped') return result(true, 'already_stopped', '会话已停止');
        if (state.state === 'stopping') return result(true, 'stop_pending', '已请求停止，正在等待反馈');
        if (state.state !== 'running') return result(false, 'not_running', '没有正在运行的会话');
        clearTick(); const operation = ++epoch;
        publish({ state: 'stopping', reason: null }); log('已请求停止，正在等待演示任务收尾。');
        const complete = await delay(options.stopDelayMs ?? 900);
        if (!complete || disposed || operation !== epoch) return result(false, 'superseded', '停止观察器已关闭');
        publish({ state: 'stopped', tasks: state.tasks.map(task => ({ ...task, stage: '已停止', detail: '离线任务已收尾；没有影响游戏或原生 AI。' })) });
        if (disposed || operation !== epoch) return result(false, 'superseded', '停止观察器已关闭或配置已改变');
        log('演示已停止。真实适配层须等待宿主明确反馈后显示此状态。');
        if (disposed || operation !== epoch) return result(false, 'superseded', '停止观察器已关闭或配置已改变');
        return result(true, 'stopped', '离线会话已停止');
      });
    },
    detach() { publish({ observing: false }); },
    attach() { publish({ observing: true }); },
    dispose() { disposed = true; epoch++; clearTick(); for (const cancel of [...pending]) cancel(); listeners.clear(); requests.clear(); },
  };
}
