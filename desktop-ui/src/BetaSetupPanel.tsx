import { useEffect, useRef, useState } from 'react';
import { invoke as nativeInvoke } from '@tauri-apps/api/core';
import { Button } from './components/ui';
import { Check } from '@phosphor-icons/react';

import './native-setup.css';

export type BetaSetupResult = {
  prepared?: boolean; game_selected?: boolean; mod_selected?: boolean; cancelled?: boolean; game_launch_requested?: boolean;
  /** Last failure code of a status/prepare request, for the parent screen. */
  error?: string;
};

const messages: Record<string, string> = {
  beta_game_unsupported: '这个游戏文件不是受支持的版本。请选择 RA3 1.12 的 RA3_1.12.game 文件。',
  beta_base_game_config_unsupported: '游戏目录的配置不完整或不兼容。目前支持 RA3 1.12（繁体中文版配置），请保留完整的游戏目录。',
  beta_mod_unsupported: '这个 Mod 与当前版本不匹配，请选择兼容的弈核 Mod（.big 文件）。',
  beta_existing_run_unreleased: '上一局还没有确认停止。请先在「对局」页停止它，再修改游戏设置。',
  run_history_unverifiable: '上一局的记录不完整，暂时不能修改游戏设置。请导出诊断信息并反馈。',
  beta_owned_file_conflict: '目标位置已有不同的文件，原文件已保留。请检查游戏目录和 Mod。',
  beta_setup_changed_requires_migration: '现有设置不能自动更新。请先停止当前对局，再重新准备。',
  beta_release_required: '这一步需要使用正式安装的客户端。',
  beta_game_already_running: '游戏已经在运行。请直接在游戏里开始对局，或退出游戏后再从这里启动。',
  beta_game_launch_not_ready: '还不能启动游戏，请先完成上面的准备步骤。',
};

type StepItem = {title: string; description: string; done: boolean; operation: string; button: string};

/** Game and mod selection. All file access happens in the native layer; this only names fixed operations. */
export function BetaSetupPanel({locked, onPrepared, onStatusChange, invoke = nativeInvoke}: {
  locked: boolean; onPrepared: () => void; onStatusChange?: (result: BetaSetupResult) => void;
  invoke?: <T>(command: string, args: {operation: string}) => Promise<T>;
}) {
  const [state, setState] = useState<BetaSetupResult>({});
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState('选择游戏和 Mod，然后点击「检查并准备」。');
  const [failed, setFailed] = useState(false);
  const pending = useRef(false);

  async function call(operation: string) {
    if (pending.current || (locked && operation !== 'status')) return;
    pending.current = true; setBusy(operation); setFailed(false);
    try {
      const value = await invoke<BetaSetupResult>('game_setup_request', {operation});
      if (value.cancelled) { setNotice('已取消选择，保留原来的设置。'); return; }
      const reselected = operation === 'select_game' || operation === 'select_mod';
      const next = {...state, ...value, error: undefined, ...(reselected ? {prepared: false} : {})};
      setState(next); onStatusChange?.(next);
      if (operation === 'prepare' && value.prepared) {
        setNotice('准备完成。可以启动游戏了。'); onPrepared();
      } else if (operation === 'prepare') {
        setFailed(true); setNotice('准备没有完成，请检查所选文件后重试。');
      } else if (operation === 'launch' && value.game_launch_requested) {
        setNotice('正在启动游戏。');
      } else if (operation === 'select_game') {
        setNotice(value.mod_selected ? '游戏和 Mod 都已选好，请点击「检查并准备」。' : '已选择游戏，接下来选择 Mod。');
      } else if (operation === 'select_mod') {
        setNotice(value.game_selected ? '游戏和 Mod 都已选好，请点击「检查并准备」。' : '已选择 Mod，接下来选择游戏文件。');
      } else if (operation === 'status') {
        setNotice(value.prepared ? '游戏和 Mod 已准备好。' : '选择游戏和 Mod，然后点击「检查并准备」。');
      }
    } catch (error) {
      if (operation === 'status' || operation === 'prepare') {
        const next = {...state, prepared: false, error: String(error)}; setState(next); onStatusChange?.(next);
      }
      setFailed(true);
      setNotice(messages[String(error)] ?? '准备没有完成，请重新检查所选文件。');
    } finally {
      pending.current = false; setBusy('');
    }
  }
  useEffect(() => { void call('status'); }, []);

  const blocked = Boolean(busy) || locked;
  const step = state.prepared ? 3 : !state.game_selected ? 0 : !state.mod_selected ? 1 : 2;
  const items: StepItem[] = [
    {
      title: '选择游戏', description: '游戏目录 Data 文件夹中的 RA3_1.12.game',
      done: Boolean(state.game_selected || state.prepared), operation: 'select_game',
      button: state.game_selected || state.prepared ? '更换游戏' : '选择游戏文件',
    },
    {
      title: '选择 Mod', description: '兼容的弈核 Mod（.big 文件）',
      done: Boolean(state.mod_selected || state.prepared), operation: 'select_mod',
      button: state.mod_selected || state.prepared ? '更换 Mod' : '选择 Mod 文件',
    },
    {
      title: '检查并准备', description: '检查版本是否兼容，并准备运行所需的组件',
      done: Boolean(state.prepared), operation: 'prepare',
      button: state.prepared ? '重新准备' : '检查并准备',
    },
  ];
  const steps = <ol className="setup-steps">
    {items.map((item, index) => {
      const current = step === index;
      const waitsForFiles = item.operation === 'prepare' && (!state.game_selected || !state.mod_selected);
      return <li className={`setup-step ${current ? 'is-current' : ''} ${item.done ? 'is-done' : ''}`}
        aria-current={current ? 'step' : undefined} key={item.operation}>
        <span className="setup-step-number">
          {item.done ? <Check size={18} weight="bold" aria-hidden="true" /> : index + 1}
        </span>
        <div className="setup-step-copy">
          <h3>{item.title}</h3>
          <p>{item.description}</p>
        </div>
        <Button kind={current ? 'primary' : ''} loading={busy === item.operation}
          disabled={blocked || waitsForFiles} onClick={() => void call(item.operation)}>{item.button}</Button>
      </li>;
    })}
  </ol>;

  return <section className="native-panel native-setup setup-panel">
    <div className="setup-panel-heading">
      <div>
        <h2>游戏与 Mod</h2>
        <p className="setup-description">告诉弈核你的红色警戒 3（1.12）和兼容 Mod 在哪里。游戏和 Mod 需自行提供。</p>
      </div>
      <span className={`setup-badge ${state.prepared ? 'is-ready' : ''}`}>
        {busy ? '处理中' : state.prepared ? '已就绪' : '未完成'}
      </span>
    </div>
    {state.prepared ? <>
      <div className="setup-ready">
        <span className="setup-ready-mark"><Check size={24} weight="bold" aria-hidden="true" /></span>
        <div><h3>游戏已就绪</h3><p>可以从这里启动游戏，也可以自己打开游戏。</p></div>
        <Button kind="primary" disabled={blocked} loading={busy === 'launch'} onClick={() => void call('launch')}>启动游戏</Button>
      </div>
      <details className="setup-details">
        <summary>更换游戏或 Mod</summary>
        <p>更换时需要重新选择游戏和 Mod 两项，再检查一次。</p>
        {steps}
      </details>
    </> : steps}
    <div className={`setup-notice ${failed ? 'is-error' : ''}`} role="status">{notice}</div>
    <div className="setup-footer">
      <span className="setup-description">设置有变化时，可以重新检查。</span>
      <Button disabled={blocked} onClick={() => void call('status')}>重新检查</Button>
    </div>
    {locked && <p className="setup-notice is-warning">弈核 AI 正在使用游戏。请先停止它，再修改游戏设置。</p>}
  </section>;
}
