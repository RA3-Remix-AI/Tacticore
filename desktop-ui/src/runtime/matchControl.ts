/**
 * The single primary Start/Stop control, derived from host state.
 * Pure and side-effect free: the backend still enforces every rule; this only
 * decides which one action to offer and how to describe the state plainly.
 */
import type {ConnectionConfigurationState} from './connectionConfigurationStateV1';

export type ControlAction = 'open_setup' | 'open_model' | 'open_style' | 'discover' | 'start' | 'stop' | 'cancel_wait' | 'refresh' | 'none';
export type ControlPhase = 'setup' | 'idle' | 'found' | 'ready' | 'waiting' | 'starting' | 'running' | 'stopping'
  | 'returning' | 'uncertain' | 'finished';

export interface ControlInput {
  /** null when this build cannot report game setup (debug builds). */
  gamePrepared: boolean | null;
  configuration: ConnectionConfigurationState;
  profileIssue: 'dirty' | 'invalid' | null;
  waiting: boolean;
  busy: boolean;
  run: {state: string; native_release_verified?: boolean} | null;
  runHoldsGame: boolean;
  candidateCount: number;
  candidateSelected: boolean;
  sessionPrepared: boolean;
  readyValid: boolean;
}

export interface ControlView {
  phase: ControlPhase;
  status: string;
  title: string;
  detail: string;
  primary: {label: string; action: ControlAction; tone: 'primary' | 'danger' | 'neutral'; disabled: boolean};
  live: boolean;
}

const terminal = new Set(['completed', 'stopped', 'fault', 'failed', 'result_candidate']);

function view(phase: ControlPhase, status: string, title: string, detail: string,
  label: string, action: ControlAction, tone: ControlView['primary']['tone'], disabled = false, live = false): ControlView {
  return {phase, status, title, detail, primary: {label, action, tone, disabled}, live};
}

export function matchControl(input: ControlInput): ControlView {
  const {busy} = input;
  if (input.runHoldsGame && input.run) {
    const state = input.run.state;
    if (state === 'stopping') {
      return view('stopping', '停止中', '正在停止弈核 AI',
        '已发出停止请求，正在等待游戏把控制权交还。确认完成前不能开始新的对局。',
        '正在交还控制…', 'none', 'neutral', true, true);
    }
    if (terminal.has(state)) {
      return view('returning', '交还控制中', '对局已结束，正在确认控制已交还',
        '弈核 AI 已不再下达新指令。客户端正在确认游戏控制已完全交还，完成后即可查看复盘。',
        '刷新状态', 'refresh', 'neutral', busy, true);
    }
    if (state === 'uncertain') {
      return view('uncertain', '确认中', '正在确认运行状态',
        '暂时无法确认弈核 AI 的状态，客户端会持续查询。请不要重复开始；如需结束，可以直接停止。',
        '停止 AI', 'stop', 'danger', busy, true);
    }
    if (state === 'starting') {
      return view('starting', '启动中', '弈核 AI 正在接手',
        '正在连接游戏并发起第一次模型调用。随时可以停止。', '停止 AI', 'stop', 'danger', busy, true);
    }
    return view('running', '指挥中', '弈核 AI 正在指挥',
      '下方会实时显示 AI 的每次判断和理由。需要结束时点击「停止 AI」。', '停止 AI', 'stop', 'danger', busy, true);
  }
  if (input.waiting) {
    return view('waiting', '等待对局', '正在等待对局开始',
      '进入对局后会自动找到它并开始，最多等待五分钟。', '取消等待', 'cancel_wait', 'neutral', false, true);
  }
  if (input.gamePrepared === false) {
    return view('setup', '需要设置', '先完成游戏设置', '选择 RA3 1.12 和兼容 Mod 后才能开始。',
      '继续设置', 'open_setup', 'primary');
  }
  if (input.configuration === 'checking') {
    return view('setup', '检查中', '正在检查模型设置', '请稍候。', '正在检查…', 'none', 'neutral', true);
  }
  if (input.configuration !== 'ready') {
    return view('setup', '需要设置', '模型设置需要确认',
      input.configuration === 'pending' ? '上次保存还没有完成，请在模型设置中处理。' : '请打开模型设置，确认模型服务和 API Key。',
      '打开模型设置', 'open_model', 'primary');
  }
  if (input.profileIssue === 'dirty') {
    return view('setup', '需要保存', 'AI 风格有未保存的修改', '保存后才能开始新的对局。', '去保存', 'open_style', 'primary');
  }
  if (input.profileIssue === 'invalid') {
    return view('setup', '需要设置', 'AI 设置不完整', '通常是还没有填写模型名称。', '完善模型设置', 'open_model', 'primary');
  }
  if (input.readyValid) {
    return view('ready', '可以开始', '一切就绪', '点击「开始」后，弈核 AI 会接手它的席位。', '开始', 'start', 'primary', busy);
  }
  if (input.candidateCount > 0 || input.sessionPrepared) {
    const needsChoice = input.candidateCount > 1 && !input.candidateSelected;
    return view('found', '已找到对局', needsChoice ? '找到多个对局' : '找到对局',
      needsChoice ? '请先在上方选择要使用的对局。' : '确认对局信息无误后点击「开始」。开始前会再检查一次。',
      '开始', 'start', 'primary', busy || (input.candidateCount > 0 && !input.candidateSelected));
  }
  if (input.run && !input.runHoldsGame) {
    return view('finished', '已结束', '上一局已结束',
      '想再来一局：先完全退出游戏并重新打开，在大厅里设置好对局并开始，然后点击「查找对局」。',
      '查找对局', 'discover', 'primary', busy);
  }
  return view('idle', '待命', '等待对局', '在游戏里开始一局遭遇战，然后点击「查找对局」。', '查找对局', 'discover', 'primary', busy);
}
