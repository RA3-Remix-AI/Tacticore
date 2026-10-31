import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Button } from './components/ui';

type Result={prepared?:boolean;game_selected?:boolean;mod_selected?:boolean;cancelled?:boolean;game_launch_requested?:boolean};
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
export function BetaSetupPanel({locked,onPrepared}:{locked:boolean;onPrepared:()=>void}){
  const [state,setState]=useState<Result>({}),[busy,setBusy]=useState(false),[notice,setNotice]=useState('首次使用请选择自己的游戏文件和兼容 Mod，再完成本机准备。');
  async function call(operation:string){
    setBusy(true);
    try{
      const value=await invoke<Result>('game_setup_request',{operation});
      setState(old=>({...old,...value}));
      if(operation==='prepare'){setNotice('本机准备完成。配置模型连接后，启动游戏并进入受支持的对局，再点击下方“发现游戏”。');onPrepared();}
      else if(operation==='launch')setNotice('已请求启动游戏；进入受支持对局后再发现和核验。尚未启动指挥官。');
      else if(operation==='status'&&value.prepared)setNotice('已核验本机游戏与 Mod 登记。进入受支持的对局后可发现游戏。');
    }catch(error){const code=String(error);setNotice(messages[code]??`本机准备未完成（${code}）。`);}
    finally{setBusy(false);}
  }
  useEffect(()=>{void call('status');},[]);
  return <section className="native-panel native-setup">
    <h2>游戏接入 · v0.1.0-beta.1</h2>
    <p className="native-muted">支持已核验的 RA3 1.12 繁体中文配置、TemplePrime、P3 苏军、P4 原生电脑对手和已验证出生位置。安装包不包含游戏或 Mod；请选择自己已有的兼容文件。</p>
    <ol className="native-status"><li>游戏文件：{state.game_selected||state.prepared?'已选择 / 已登记':'待选择 Data 目录中的 RA3_1.12.game'}</li>
      <li>兼容 Mod：{state.mod_selected||state.prepared?'已选择 / 已登记':'待选择 BIG 文件'}</li><li>本机准备：{state.prepared?'已完成':'待核验'}</li></ol>
    <div className="native-actions">
      <Button disabled={busy||locked} onClick={()=>void call('select_game')}>选择游戏文件</Button>
      <Button disabled={busy||locked} onClick={()=>void call('select_mod')}>选择兼容 Mod</Button>
      <Button disabled={busy||locked||!state.game_selected||!state.mod_selected} onClick={()=>void call('prepare')}>核验并准备</Button>
      <Button disabled={busy||locked||!state.prepared} onClick={()=>void call('launch')}>启动受支持游戏</Button>
      <Button disabled={busy||locked} onClick={()=>void call('status')}>重新核验</Button>
    </div><p role="status" className="native-muted">{notice}</p>
  </section>;
}
