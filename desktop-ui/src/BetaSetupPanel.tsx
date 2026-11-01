import { useEffect, useRef, useState } from 'react';
import { invoke as nativeInvoke } from '@tauri-apps/api/core';
import { Button } from './components/ui';
import { Check } from '@phosphor-icons/react';

import './native-setup.css';

export type BetaSetupResult={prepared?:boolean;game_selected?:boolean;mod_selected?:boolean;cancelled?:boolean;game_launch_requested?:boolean};
const messages:Record<string,string>={
  beta_game_unsupported:'游戏版本不兼容。请选择已支持的 RA3 1.12 游戏文件。',
  beta_base_game_config_unsupported:'基础游戏配置不兼容或不完整。当前 beta 支持已核验的繁体中文 1.12 配置，请保留完整游戏目录。',
  beta_mod_unsupported:'这个 Mod 与当前版本不匹配，请选择兼容的指挥官 Mod BIG 文件。',
  beta_existing_run_unreleased:'旧版或当前指挥官尚未独立确认停止归还。请先回到原客户端查询和停止。',
  run_history_unverifiable:'旧版运行记录尚不能核验，已保留现场，当前不会覆盖或准备新指挥。',
  beta_owned_file_conflict:'目标位置已有不同文件，已保留原文件，请核对安装与 Mod。',
  beta_setup_changed_requires_migration:'现有登记不能安全自动更新。请保留记录，先完成停止、归还和迁移复核。',
  beta_release_required:'游戏接入需要使用随运行组件安装的 beta 客户端。',
  beta_game_already_running:'已有游戏进程。请在该游戏内准备对局，或正常退出后再启动。',
  beta_game_launch_not_ready:'游戏启动入口尚未准备好，请先完成兼容性核验。',
};
export function BetaSetupPanel({locked,onPrepared,onStatusChange,invoke = nativeInvoke}: {
  locked:boolean; onPrepared:()=>void; onStatusChange?:(result:BetaSetupResult)=>void;
  invoke?: <T>(command:string,args:{operation:string})=>Promise<T>;
}) {
  const [state,setState]=useState<BetaSetupResult>({});
  const [busy,setBusy]=useState(''), [notice,setNotice]=useState('先选择游戏与兼容 Mod，再核验本机环境。');
  const [failed,setFailed]=useState(false);
  const pending=useRef(false);
  async function call(operation:string) {
    if(pending.current || (locked && operation!=='status'))return;
    pending.current=true;setBusy(operation);setFailed(false);
    try {
      const value=await invoke<BetaSetupResult>('game_setup_request',{operation});
      if(value.cancelled){setNotice('已取消选择，保留当前设置。');return;}
      const next={...state,...value,...(operation==='select_game'||operation==='select_mod'?{prepared:false}:{})};
      setState(next);onStatusChange?.(next);
      if(operation==='prepare' && value.prepared){setNotice('本机环境已准备好。启动游戏并进入对局后，即可发现游戏。');onPrepared();}
      else if(operation==='prepare'){setFailed(true);setNotice('准备尚未完成，请核对所选文件后重试。');}
      else if(operation==='launch' && value.game_launch_requested)setNotice('已请求启动游戏。进入对局后，前往作战中心发现游戏。');
      else if(operation==='select_game')setNotice(value.mod_selected?'游戏与 Mod 均已选择，请重新核验。':'游戏文件已选择。修改环境需要重新选择游戏与 Mod 两项，请继续选择兼容 Mod。');
      else if(operation==='select_mod')setNotice(value.game_selected?'游戏与 Mod 均已选择，请重新核验。':'Mod 已选择。修改环境需要重新选择游戏与 Mod 两项，请继续选择游戏文件。');
      else if(operation==='status')setNotice(value.prepared?'游戏与 Mod 登记已核验，可以启动游戏。':'本机环境尚未准备。请完成下面三个步骤。');
    }catch(error){if(operation==='status'||operation==='prepare'){const next={...state,prepared:false};setState(next);onStatusChange?.(next);}setFailed(true);setNotice(messages[String(error)]??'本机准备未完成，请重新核验所选文件。');}
    finally{pending.current=false;setBusy('');}
  }
  useEffect(()=>{void call('status');},[]);
  const blocked=Boolean(busy)||locked;
  const step=state.prepared?3:!state.game_selected?0:!state.mod_selected?1:2;
  const steps=<ol className="setup-steps">
    {[
      {title:'选择游戏',description:'Data 目录中的 RA3_1.12.game',done:state.game_selected||state.prepared,operation:'select_game',button:state.game_selected||state.prepared?'更换游戏文件':'选择游戏文件'},
      {title:'选择 Mod',description:'已有的兼容指挥官 BIG 文件',done:state.mod_selected||state.prepared,operation:'select_mod',button:state.mod_selected||state.prepared?'更换兼容 Mod':'选择兼容 Mod'},
      {title:'核验与准备',description:'检查兼容性并准备本机运行组件',done:state.prepared,operation:'prepare',button:state.prepared?'重新准备':'核验并准备'},
    ].map((item,index)=><li className={`setup-step ${step===index?'is-current':''} ${item.done?'is-done':''}`} aria-current={step===index?'step':undefined} key={item.operation}>
      <span className="setup-step-number">{item.done?<Check size={18} weight="bold" aria-hidden="true" />:String(index+1).padStart(2,'0')}</span>
      <div className="setup-step-copy"><h3>{item.title}</h3><p>{item.description}</p><span className="setup-step-state">{item.done?'已完成':step===index?'当前步骤':'待完成'}</span></div>
      <Button kind={step===index?'primary':''} loading={busy===item.operation} disabled={blocked||(item.operation==='prepare'&&(!state.game_selected||!state.mod_selected))} onClick={()=>void call(item.operation)}>{item.button}</Button>
    </li>)}
  </ol>;
  return <section className="native-panel native-setup setup-panel">
    <div className="setup-panel-heading"><div><p className="eyebrow">LOCAL SETUP / 01</p><h2>准备游戏环境</h2><p className="setup-description">连接你的红色警戒 3，完成首次部署。</p></div><span className={`setup-badge ${state.prepared?'is-ready':''}`}>{busy?'正在处理':state.prepared?'环境已就绪':'等待准备'}</span></div>
    {state.prepared?<><div className="setup-ready"><span className="setup-ready-mark"><Check size={24} weight="bold" aria-hidden="true" /></span><div><h3>游戏环境已就绪</h3><p>进入受支持的对局后，前往作战中心发现游戏。</p></div><Button kind="primary" disabled={blocked} loading={busy==='launch'} onClick={()=>void call('launch')}>启动游戏</Button></div><details className="setup-details"><summary>查看或修改游戏与 Mod</summary><p>修改环境时，请重新选择游戏文件与 Mod 两项，再进行核验。</p>{steps}</details></>:steps}
    <div className={`setup-notice ${failed?'is-error':''}`} role="status">{notice}</div>
    <div className="setup-footer"><details className="setup-details setup-scope"><summary>查看 Beta 支持范围</summary><p>RA3 1.12 繁体中文配置 · TemplePrime · P3 苏军 · P4 原生电脑对手及已验证出生位置。游戏和 Mod 需自行提供。</p></details><Button disabled={blocked} onClick={()=>void call('status')}>重新核验</Button></div>
    {locked&&<p className="setup-notice is-warning">请先停止当前指挥并确认归还，再修改游戏环境。</p>}
  </section>;
}
