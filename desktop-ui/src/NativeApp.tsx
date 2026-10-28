import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Button } from './components/ui';
import { preferenceAxes, preferencePresets, type CommanderPreferences } from './state/preferences';
import type { Doctrine } from './state/settings';
import { hostRpc, HostError } from './runtime/nativeRpc';
import { startAtOpening } from './runtime/openingStart';
import { applicationView, type AppliedReceipt, type ConsumptionReceipt } from './runtime/applicationView';
import { createDiagnosticsDownload, DiagnosticError, saveDiagnosticFile } from './runtime/diagnosticsDownload';
import { eventDescription, preservePendingStart, releaseDescription, runLocksControls, sameRun, localPreparationDescription, type NativeEvent } from './runtime/nativeProcess';
import './native.css';

type Draft = {schema_version:1;profile_id:string;name:string;revision:number;connection_id:string;model:string;doctrine:Doctrine;custom_traits:string;preferences?:CommanderPreferences};
type Profile = {profile_id:string;name:string;revision:number;model:string;connection_id:string;draft:Draft;state:string;validation:{ok:boolean;reason_code:string};
  effective:null|{effective_hash:string;traits:string;traits_bytes:number;axis_support:Record<string,{execution_status:string}>}};
type Connection = {id:string;name:string;provider:string;endpoint:string;model:string;credential_check:string;credential_configured:boolean|null;remember_key:boolean};
type Session = {id:string;map:string;player_name:string;faction:string};
type Limits = {production_total_budget:number;reserve_floor:number;max_command_budget:number};
type Capabilities = {control_mode?:string;native_macro?:boolean;available_macro_actions?:string[];base_defense_granted?:boolean;group_roles_granted?:string[];supported_units?:string[];supported_foci?:string[];tactics_supported?:boolean;runtime_tactical_supported?:boolean};
type Ready = {ready:boolean;session_id:string;ready_token:string;expires_at:number;reason_code?:string;session?:Session;execution_limits?:Limits;capabilities?:Capabilities};
type Task = {task_id:string;module?:string;purpose?:string;status?:string;reason_code?:string;stage?:string;budget?:{fraction:number};expires_at_game_seconds?:number;physical_home?:boolean;control_released?:boolean};
type Run = {run_id:string;session_id:string;state:string;profile_id?:string;profile_revision?:number;effective_hash?:string;native_release_verified?:boolean;no_native_execution_started?:boolean;
  profile_application?:AppliedReceipt;profile_consumption?:ConsumptionReceipt;session?:Session;execution_limits?:Limits;capabilities?:Capabilities;
  latest_snapshot?:{game_time_seconds?:number;paused?:boolean;resources?:{credits:number}};execution?:{remaining_budget?:number;executor_connected?:boolean;enabled?:boolean};
  metrics?:{requests?:number;accepted?:number};task_counters?:{dispatches?:number;started?:number;completed?:number;failed?:number;blocked?:number};
  tasks?:Task[];tasks_cursor?:{total_count:number;truncated:boolean};events?:NativeEvent[];
  current_plan?:{macro_actions?:string[];macro_production?:{action:string;additional_count:number}};macro_feedback?:{status:string;selected_policy:string|null};
  macro_production_feedback?:{observed_new_queue_count:number;additional_count_requested:number;new_own_unit_observations:number;policy_released:boolean;release_reason:string|null;completed_units_verified:false};
  macro_construction_feedback?:{observed_new_queue_count:number;new_own_construction_object_observations:number;fully_paid_queue_observations:number;policy_released:boolean;construction_completed_verified:false};
  macro_scouting_feedback?:{active_native_tactics:number;moved_native_groups:number;new_legal_contacts_since_intent:number;policy_released:boolean};
  macro_regional_feedback?:{target_region:string;active_native_tactics:number;moved_native_groups:number;groups_progressing_toward_region:number;policy_released:boolean;goal?:string;defender_groups_near_infrastructure?:number;groups_near_home_region?:number;withdrawing_native_groups?:number};
  local_preparation?:{state?:string;reason_code?:string;paid_units_available?:number};
  events_cursor?:{first_seq:number|null;last_seq:number|null;total_count:number;overflow:number;truncated:boolean}};
const reasons:Record<string,string>={adapter_unavailable:'宿主适配仍未就绪。',profile_library_unavailable:'未找到本机指挥官库，请检查已登记的配置。',
  runtime_library_unregistered:'请先完成本机指挥官配置库登记，再重新打开客户端。',runtime_library_unavailable:'已登记的指挥官配置库暂不可读取。',
  registered_library_changed:'已登记的配置库发生变化，请先核对本机配置，当前操作未执行。',
  runtime_configuration_invalid:'本机配置登记无效，请核对后重新打开客户端。',runtime_configuration_changed:'本机配置来源已变化，请重新打开客户端并再次检查对局。',
  profile_revision_conflict:'该配置已在另一窗口更新，请重新载入。',traits_budget_exceeded:'风格说明与补充要求合计超过 1200 UTF-8 字节，请缩短补充要求。',
  delivery_unknown:'送达结果未知，已保留运行编号并查询状态；请勿重新启动。',run_state_conflict:'已有运行或未确认的操作，需要先查询和核对。',
  runtime_layout_unavailable:'本机运行组件不完整。',runtime_packaging_unavailable:'此发布版本尚未包含经过验证的运行组件。',runtime_packaging_invalid:'运行组件完整性核验失败，请重新安装经过验证的发布包。',
  session_unavailable:'尚未登记可核验的真实对局。',session_not_ready:'真实对局尚未满足指挥条件，请检查游戏和电脑身份。',
  session_registration_changed:'本机对局登记已变化，请重新打开客户端并检查对局。',session_root_invalid:'本机对局目录登记无效，请核对原生登记后重新打开客户端。',
  legacy_executor_player_unsupported:'当前生产执行器仅验证了电脑席位 3，其他席位暂不可启动。',capability_unavailable:'当前证据未覆盖所需执行能力。',
  credentials_unavailable:'本机连接配置或保存的凭据无法读取，请在原生客户端检查连接。',readiness_expired:'检查结果已过期，请重新检查。',
  opening_wait_expired:'等待对局超过五分钟，自动启动已取消。',
  effective_profile_changed:'配置已经变化，请重新载入后核验。',diagnostics_read_failed:'诊断文件读取未完成，请重新导出；运行任务不会重启。',
  diagnostics_integrity_invalid:'诊断文件完整性核验失败，未下载。',diagnostics_binding_invalid:'诊断不属于当前运行或配置修订，未下载。',
  diagnostics_receipt_invalid:'诊断导出回执无效，未下载。',diagnostics_document_invalid:'诊断内容格式无效，未下载。',diagnostics_unavailable:'诊断暂不可导出。'};
const stateLabel:Record<string,string>={running:'运行中',starting:'启动中',stopping:'停止请求处理中',stopped:'宿主已停止',completed:'宿主进程已结束',fault:'需要处理',failed:'需要处理',
  uncertain:'结果未知，持续查询',result_candidate:'出现结算候选，等待确认',sampling_wait:'等待完整游戏采样'};
const taskStages:Record<string,string>={planned:'等待宿主准入',dispatch_pending:'待派发',active:'执行中',started:'已启动',stopping:'正在停止并归还',completed:'已完成',failed:'失败',blocked:'受阻',cancelled:'已取消',unavailable:'能力未就绪'};
const moduleNames:Record<string,string>={build:'生产',attack:'主攻',raid:'骚扰',combined_arms:'协同',recon:'侦察',local_maneuver:'局部机动'};
const lastRunKey='tacticore.desktop.native.last-run.v1';
const publicId=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function errorText(error:unknown){return error instanceof HostError||error instanceof DiagnosticError?(reasons[error.code]??`操作未完成（${error.code}）。`):'操作未完成，请检查本机服务。';}
function lastRun():Run|null{try{const value=JSON.parse(localStorage.getItem(lastRunKey)??'null');return value&&publicId.test(value.run_id)&&publicId.test(value.session_id)?
  {run_id:value.run_id,session_id:value.session_id,profile_id:publicId.test(value.profile_id??'')?value.profile_id:undefined,state:'uncertain'}:null;}catch{return null;}}
function rememberRun(value:Run){try{localStorage.setItem(lastRunKey,JSON.stringify({run_id:value.run_id,session_id:value.session_id,profile_id:value.profile_id}));}catch{}}
const number=(value:number|undefined)=>value===undefined?'—':value.toLocaleString('zh-CN');
const macroNames:Record<string,string>={budgeteconomy:'经济投入优先',budgetarmy:'军队投入优先',budgettech:'科技投入优先',produceflak:'高射炮兵生产偏好',produceconscript:'征召兵生产偏好',producetank:'铁锤坦克生产偏好',buildreactor:'超级反应堆建造偏好',scout:'侦察时机（原生选择目标）',deployattack:'调度至西侧起点区域',deploydefense:'调度至东侧起点区域',regroup:'集结至己方区域',withdraw:'向己方区域撤退',reinforce:'增援己方基地'};
function regionalDetail(value:NonNullable<Run['macro_regional_feedback']>){
  const tasks=`原生任务 ${value.active_native_tactics}`;
  if(value.goal==='original_native_defense_of_own_infrastructure')return `保护己方建筑，${tasks}，基础设施附近的防守小队 ${value.defender_groups_near_infrastructure??0}；原生 AI 选择建筑和操作部队，防守结果仍需核验。`;
  if(value.goal==='reinforce_own_base_through_original_reactive_defense')return `增援己方基地，${tasks}，基础设施附近的小队 ${value.defender_groups_near_infrastructure??0}；原生 AI 选择基地并操作部队，任务成败仍需核验。`;
  if(value.goal==='regroup_native_force_at_own_home_waypoint')return `集结至己方区域，${tasks}，集结区域的小队 ${value.groups_near_home_region??0}；不保证全部到达，原生 AI 负责操作。`;
  if(value.goal==='withdraw_native_group_to_own_home_region')return `向己方区域撤退，${tasks}，已向己方区域推进的小队 ${value.withdrawing_native_groups??0}；不保证全军归队，原生 AI 负责操作。`;
  return `目标 ${value.target_region==='region_1_3'?'西侧起点区域':'东侧起点区域'}，${tasks}，朝目标推进的小队 ${value.groups_progressing_toward_region}；到达及任务成功需另行核验。`;
}
const macroLabels=(actions:string[]|undefined,baseDefense=false)=>actions?.map(action=>baseDefense&&action==='deploydefense'?'保护己方建筑（原生 AI 选择）':macroNames[action]).filter(Boolean).join('、')||'暂无宏观指令';
const downloadDiagnostics=createDiagnosticsDownload((operation,args)=>hostRpc(operation,args),invoke,saveDiagnosticFile);

export default function NativeApp(){
  const [profiles,setProfiles]=useState<Profile[]>([]),[connections,setConnections]=useState<Connection[]>([]);
  const [selected,setSelected]=useState(''),[draft,setDraft]=useState<Draft|null>(null),[dirty,setDirty]=useState(false);
  const [ready,setReady]=useState<Ready|null>(null),[run,setRun]=useState<Run|null>(lastRun),[session,setSession]=useState<Session|null>(null);
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('正在读取本机指挥官…'),[clock,setClock]=useState(Date.now());
  const [openingWaiting,setOpeningWaiting]=useState(false),openingAbort=useRef<AbortController|null>(null);
  const pending=useRef(false),profile=profiles.find(p=>p.profile_id===selected);
  const locked=runLocksControls(run?.state,run?.native_release_verified),polling=!!run&&locked;
  const application=applicationView(dirty||ready?.ready?undefined:profile,run?.profile_application,run?.profile_consumption);
  const connection=connections.find(c=>c.id===draft?.connection_id),limits=ready?.execution_limits??run?.execution_limits;
  const identity=ready?.session??(locked?run?.session:null)??session??run?.session,capabilities=ready?.capabilities??run?.capabilities;
  function updateRun(value:Run){rememberRun(value);setRun(value);}
  async function perform(work:()=>Promise<void>){if(pending.current)return;pending.current=true;setBusy(true);
    try{await work();}catch(error){setNotice(errorText(error));}finally{pending.current=false;setBusy(false);}}
  async function load(){
    const [p,c]=await Promise.all([hostRpc<{profiles:Profile[]}>('profiles.list',{}),hostRpc<{connections:Connection[]}>('connections.list',{})]);
    setProfiles(p.profiles);setConnections(c.connections);
    const next=p.profiles.find(value=>value.profile_id===(run?.profile_id??selected))??p.profiles[0];
    if(next){setSelected(next.profile_id);setDraft(structuredClone(next.draft));}
    setDirty(false);setReady(null);setNotice('已读取本机配置。保存后核验真实对局。');
  }
  useEffect(()=>{void perform(load);},[]);
  useEffect(()=>()=>openingAbort.current?.abort(),[]);
  useEffect(()=>{
    if(!run||!polling)return;let cancelled=false,inflight=false;
    const query=async()=>{if(inflight||pending.current)return;inflight=true;try{const value=await hostRpc<Run>('run.status',{run_id:run.run_id});
      if(!sameRun(run,value))throw new HostError('delivery_unknown',run.run_id);
      if(!cancelled)updateRun(value);
    }catch(error){if(!cancelled)setNotice(errorText(error));}finally{inflight=false;}};
    const timer=setInterval(()=>{void query();},2000);void query();return()=>{cancelled=true;clearInterval(timer);};
  },[run?.run_id,polling]);
  useEffect(()=>{if(!ready?.ready)return;const timer=setInterval(()=>setClock(Date.now()),1000);return()=>clearInterval(timer);},[ready]);
  useEffect(()=>{if(locked&&run?.profile_id&&run.profile_id!==selected){const next=profiles.find(value=>value.profile_id===run.profile_id);
    if(next){setSelected(next.profile_id);setDraft(structuredClone(next.draft));setDirty(false);setReady(null);}}},[run?.profile_id,profiles,locked]);
  function edit(patch:Partial<Draft>){if(draft){setDraft({...draft,...patch});setDirty(true);setReady(null);}}
  function choose(id:string){const next=profiles.find(p=>p.profile_id===id);if(next){setSelected(id);setDraft(structuredClone(next.draft));setDirty(false);setReady(null);setSession(null);}}
  async function save(){if(!draft||!profile)return;const result=await hostRpc<{profile:Profile;state:string;host_applied:false}>('profiles.save',
    {draft:{...draft,revision:profile.revision},expected_revision:profile.revision});setProfiles(values=>values.map(p=>p.profile_id===result.profile.profile_id?result.profile:p));
    setDraft(structuredClone(result.profile.draft));setDirty(false);setReady(null);setNotice('风格已保存，等待真实宿主应用回执。');}
  async function check(){if(!profile)return;setReady(null);setSession(null);
    const result=await hostRpc<Ready>('run.check',{profile_id:profile.profile_id,profile_revision:profile.revision,effective_hash:profile.effective?.effective_hash});
    setReady(result);setClock(Date.now());if(result.ready&&run?.session_id!==result.session_id)setRun(null);if(result.session)setSession(result.session);
    else{const inspected=await hostRpc<{session:Session|null}>('session.inspect',{profile_id:profile.profile_id});setSession(inspected.session);}
    setNotice(result.ready?'对局检查通过，可在有效期内启动。':(reasons[result.reason_code??'']??`尚未就绪（${result.reason_code??'not_ready'}）。`));}
  async function start(admission:Ready|null=ready){
    if(!profile||!admission?.ready||admission.expires_at<=Date.now()){setReady(null);setNotice('检查结果已过期，请重新检查。');return;}
    const requestId=crypto.randomUUID(),pendingRun:Run={run_id:requestId,session_id:admission.session_id,profile_id:profile.profile_id,state:'uncertain'};
    updateRun(pendingRun);
    try{const value=await hostRpc<Run>('run.start',{profile_id:profile.profile_id,profile_revision:profile.revision,effective_hash:profile.effective?.effective_hash,
      session_id:admission.session_id,ready_token:admission.ready_token},requestId);
      if(!sameRun(pendingRun,value))throw new HostError('delivery_unknown',requestId);
      updateRun(value);setNotice(value.no_native_execution_started?'启动已在派发前取消，未新增原生指挥。':'启动已受理，等待宿主应用和模型消费回执。');}
    catch(error){if(error instanceof HostError&&!preservePendingStart(error.code)){setRun(null);try{localStorage.removeItem(lastRunKey);}catch{}}throw error;}
    finally{setReady(null);}
  }
  async function openingStart(){
    if(!profile||dirty||locked)return;
    const controller=new AbortController();openingAbort.current=controller;setOpeningWaiting(true);setReady(null);
    setNotice('等待进入已登记的对局，核验通过后自动启动；五分钟内可随时取消等待。');
    try{
      const result=await startAtOpening({signal:controller.signal,
        check:()=>hostRpc<Ready>('run.check',{profile_id:profile.profile_id,profile_revision:profile.revision,effective_hash:profile.effective?.effective_hash}),
        start:async admission=>{setOpeningWaiting(false);if(admission.session)setSession(admission.session);await start(admission);}});
      if(result==='cancelled')setNotice('已取消等待，没有新增启动请求。');
    }finally{openingAbort.current=null;setOpeningWaiting(false);}
  }
  async function query(){if(!run)return;const value=await hostRpc<Run>('run.status',{run_id:run.run_id});
    if(!sameRun(run,value))throw new HostError('delivery_unknown',run.run_id);updateRun(value);}
  async function stop(){if(!run)return;const value=await hostRpc<Run>('run.stop',{run_id:run.run_id,session_id:run.session_id});
    if(!sameRun(run,value))throw new HostError('delivery_unknown',run.run_id);updateRun(value);setNotice('已请求停止，控制是否归还仍以独立验证为准。');}
  async function download(){if(!run)return;const receipt=await downloadDiagnostics(run);setNotice(`已下载脱敏诊断：${receipt.exported_event_count} / ${receipt.event_count} 条事件${receipt.truncated?'（仅最近记录，已明确截断）':''}。${receipt.effective_profile_available?'':'历史配置快照不可用，文件已注明。'}文件包含完整性哈希，自由文本和原始日志正文未打包。`);}
  const preferences=draft?.preferences??preferencePresets.find(p=>p.doctrine===draft?.doctrine)?.values??preferencePresets[1].values;
  const validReady=ready?.ready&&ready.expires_at>clock;
  return <div className="native-app">
    <header className="native-header"><div><p className="eyebrow">TACTICORE / 本机客户端</p><h1>配置指挥官，进入战场</h1></div><span className="native-tag">原生连接</span></header>
    <p role="status" className="native-notice">{notice}</p>
    <div className="native-grid"><section className="native-panel"><h2>指挥官风格</h2>
      <label>本机指挥官<select value={selected} disabled={busy||locked} onChange={e=>choose(e.target.value)}>{profiles.map(p=><option key={p.profile_id} value={p.profile_id}>{p.name}</option>)}</select></label>
      {draft&&profile&&<>
        <p className="native-muted">修订 {profile.revision} · {connection?.name??'连接未找到'} · {profile.model||'模型待配置'}</p>
        <label>打法预设<select value={preferences.preset} disabled={busy||locked} onChange={e=>{const preset=preferencePresets.find(p=>p.id===e.target.value);if(preset)edit({doctrine:preset.doctrine,preferences:{...preset.values}});}}>{preferencePresets.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}<option value="custom" disabled>自定义</option></select></label>
        <div className="native-axes">{preferenceAxes.map(axis=><label key={axis.key}><span>{axis.label}<strong>{preferences[axis.key]} / 5</strong></span>
          <input type="range" min="1" max="5" step="1" value={preferences[axis.key]} disabled={busy||locked} onChange={e=>edit({preferences:{...preferences,preset:'custom',[axis.key]:Number(e.target.value)}})}/>
          <small>{axis.descriptions[preferences[axis.key]-1]}</small><small className="native-muted">{profile.effective?.axis_support[axis.key]?.execution_status==='verified_scope'?'已验证部分执行能力':'模型决策偏好；相关执行能力尚未完整验证'}</small></label>)}</div>
        <label>补充要求<textarea rows={4} value={draft.custom_traits} disabled={busy||locked} onChange={e=>edit({custom_traits:e.target.value})}/></label>
        <p className="native-muted">风格说明与补充要求合计最多 1200 UTF-8 字节；当前已保存配置 {number(profile.effective?.traits_bytes)} 字节。</p>
        {!profile.validation.ok&&<p className="native-warning">{reasons[profile.validation.reason_code]??`配置需要处理（${profile.validation.reason_code}）`}</p>}
        <div className="native-actions"><Button disabled={busy||locked||!dirty} onClick={()=>void perform(save)}>保存风格</Button><Button disabled={busy||locked} onClick={()=>void perform(load)}>重新载入</Button></div>
        <h3>连接与模型</h3><dl className="native-facts"><dt>提供方</dt><dd>{connection?.provider??'—'}</dd><dt>接口</dt><dd>{connection?.endpoint??'—'}</dd>
          <dt>连接默认模型</dt><dd>{connection?.model||'未设置'}</dd><dt>当前有效模型</dt><dd>{profile.model||'待配置'}</dd>
          <dt>本机读取核验</dt><dd>{ready?.ready?'当前配置已通过本机读取检查':'尚未通过当前配置的对局检查'}</dd></dl>
        <label>指挥官模型<input value={draft.model} disabled={busy||locked} onChange={e=>edit({model:e.target.value})} placeholder="留空使用连接默认模型"/></label>
        <p className="native-muted">列表不会读取密钥。连接和凭据由原生客户端管理；远端可用性以实际模型调用结果为准。</p>
      </>}
    </section><section className="native-panel"><h2>对局与应用状态</h2>
      <ol className="native-status"><li>配置：{dirty?'有未保存修改':profile?.state==='saved'?'已保存':'本机库原始配置'}</li>
        <li>宿主应用：{application.applied?'已收到当前修订的应用回执':'等待当前风格的应用回执'}</li>
        <li>模型消费：{application.responded?'已收到模型响应':application.called?'已发起模型调用':'等待当前风格的消费回执'}</li>
        <li>对局：{validReady?'检查通过':run?stateLabel[run.state]??'等待核对宿主状态':'等待检查'}</li>
        <li>控制归还：{run?.no_native_execution_started?'启动已在派发前取消，未新增原生指挥':releaseDescription(run?.native_release_verified)}</li></ol>
      <p className="native-muted">停止与结算候选均需单独核验控制归还。配置变化后必须重新检查。</p>
      {validReady&&<p className="native-muted">检查有效期剩余 {Math.max(0,Math.ceil((ready!.expires_at-clock)/1000))} 秒。</p>}
      <div className="native-actions"><Button disabled={busy||dirty||locked||!profile?.validation.ok} onClick={()=>void perform(check)}>检查对局</Button>
        <Button disabled={busy||dirty||locked||!validReady} onClick={()=>void perform(start)}>启动指挥官</Button>
        {openingWaiting?<Button onClick={()=>openingAbort.current?.abort()}>取消等待</Button>:
          <Button disabled={busy||dirty||locked||!profile?.validation.ok} onClick={()=>void perform(openingStart)}>进入对局后自动启动</Button>}
        <Button disabled={busy||!locked} onClick={()=>void perform(stop)}>请求停止</Button>{run&&<Button disabled={busy} onClick={()=>void perform(query)}>查询运行状态</Button>}</div>
      <h3>绑定的真实对局</h3><dl className="native-facts"><dt>地图</dt><dd>{identity?.map??'尚未核验'}</dd><dt>电脑</dt><dd>{identity?.player_name??'尚未核验'}{identity?.faction==='Soviet'?' · 苏军':''}</dd>
        <dt>游戏时间</dt><dd>{run?.latest_snapshot?.game_time_seconds===undefined?'等待采样':`${Math.floor(run.latest_snapshot.game_time_seconds)} 秒${run.latest_snapshot.paused?' · 暂停':''}`}</dd>
        <dt>当前资金</dt><dd>{number(run?.latest_snapshot?.resources?.credits)}</dd></dl>
      {run&&<p className="native-id">运行编号 {run.run_id}<br/>对局编号 {run.session_id}</p>}
      <h3>执行边界</h3>{capabilities?.native_macro?<dl className="native-facts">
        <dt>已验证宏观能力</dt><dd>{macroLabels(capabilities.available_macro_actions,capabilities.base_defense_granted)}</dd>
        <dt>当前模型意图</dt><dd>{macroLabels(run?.current_plan?.macro_actions,capabilities.base_defense_granted)}</dd>
        {run?.current_plan?.macro_production&&<><dt>数量目标</dt><dd>新增 {run.current_plan.macro_production.additional_count} 个原生生产队列</dd></>}
        {run?.macro_production_feedback&&<><dt>生产观测</dt><dd>新增排队 {run.macro_production_feedback.observed_new_queue_count} / {run.macro_production_feedback.additional_count_requested}，新单位观测 {run.macro_production_feedback.new_own_unit_observations}；{run.macro_production_feedback.policy_released?'生产偏好已释放':'等待原生生产'}。完整造出数量尚未验证。</dd></>}
        {run?.macro_construction_feedback&&<><dt>建造观测</dt><dd>新增排队 {run.macro_construction_feedback.observed_new_queue_count}，己方施工对象观测 {run.macro_construction_feedback.new_own_construction_object_observations}；{run.macro_construction_feedback.policy_released?'建造偏好已释放':'等待原生施工'}。建筑完工尚未验证。</dd></>}
        {run?.macro_scouting_feedback&&<><dt>侦察观测</dt><dd>原生任务 {run.macro_scouting_feedback.active_native_tactics}，已移动小队 {run.macro_scouting_feedback.moved_native_groups}，新增合法接触 {run.macro_scouting_feedback.new_legal_contacts_since_intent}；{run.macro_scouting_feedback.policy_released?'侦察偏好已释放':'原生 AI 执行中'}。新增情报也可能来自其他己方单位。</dd></>}
        {run?.macro_regional_feedback&&<><dt>区域调度观测</dt><dd>{regionalDetail(run.macro_regional_feedback)} {run.macro_regional_feedback.policy_released?'偏好已释放':'原生 AI 执行中'}。</dd></>}
        <dt>原生反馈</dt><dd>{run?.native_release_verified?'已停止新增宏观指挥，原生 AI 继续运行':run?.macro_feedback?.status==='native_budget_adopted'?`已采用：${macroLabels(run.macro_feedback.selected_policy?[run.macro_feedback.selected_policy]:[])}`:run?.macro_feedback?.status==='native_delegation_observed'?'原生 AI 自主决策':'等待原生采用证据'}</dd>
        <dt>单位操作</dt><dd>原生 AI 负责移动、局部交战和技能</dd></dl>:<dl className="native-facts"><dt>生产总预算</dt><dd>{number(limits?.production_total_budget)}</dd><dt>资金保留底线</dt><dd>{number(limits?.reserve_floor)}</dd>
        <dt>单次预算上限</dt><dd>{number(limits?.max_command_budget)}</dd><dt>剩余生产预算</dt><dd>{number(run?.execution?.remaining_budget)}</dd>
        <dt>已准入单位</dt><dd>{capabilities?.supported_units?.map(unit=>unit==='conscript'?'动员兵':unit).join('、')||'等待证据核验'}</dd></dl>}
      <p className="native-muted">核心负责宏观决策，具体操作沿用原生 AI。只执行本局检查已授予的能力；各任务受资源、队伍可用性和期限约束。风格偏好不会自动授予执行能力。</p>
      {run?.local_preparation&&<p className="native-muted">局部机动准备：{localPreparationDescription(run.local_preparation.state)}</p>}
    </section></div>
    {run&&<section className="native-panel native-process"><div className="native-section-heading"><div><h2>任务与过程记录</h2><p className="native-muted">模型请求 {number(run.metrics?.requests)} · 接受方案 {number(run.metrics?.accepted)} · 实际派发 {number(run.task_counters?.dispatches)} · 完成 {number(run.task_counters?.completed)} · 受阻 {number(run.task_counters?.blocked)}</p></div>
      <Button disabled={busy} onClick={()=>void perform(download)}>下载脱敏诊断</Button></div>
      <p className="native-muted">诊断包含事件与配置指纹、版本和源文件哈希；自由文本、模型输入与原始日志正文不会打包。</p>
      {run.tasks?.length?<ul className="native-tasks">{run.tasks.map(task=><li key={task.task_id}><strong>{moduleNames[task.module??'']??'任务'} · {taskStages[task.status??'']??'等待核验'}</strong>
        <span>{task.module==='local_maneuver'?'移动、保持、返回':task.purpose??'—'}{task.budget?` · 预算比例 ${Math.round(task.budget.fraction*100)}%`:''}</span>
        {task.module==='local_maneuver'&&<small>实际回家：{task.physical_home===true?'已核验':'未核验'} · 控制归还：{task.control_released===true?'已核验':'未核验'}</small>}
        <small>{task.reason_code??''}</small></li>)}</ul>:<p className="native-muted">尚未收到任务记录。启动意图与宿主事件仍会记录在日志中。</p>}
      {run.tasks_cursor?.truncated&&<p className="native-muted">任务列表仅展示部分记录，共 {run.tasks_cursor.total_count} 项。</p>}
      <h3>最近日志</h3>{run.events_cursor&&<p className="native-muted">当前 {run.events?.length??0} 条 / 共 {run.events_cursor.total_count} 条{run.events_cursor.truncated?`，另有 ${run.events_cursor.overflow} 条较早记录未在此展开`:''}。</p>}
      <ol className="native-events">{run.events?.map(event=><li key={event.seq}><span>{eventDescription(event)}</span><time dateTime={event.created_at}>{new Date(event.created_at).toLocaleTimeString('zh-CN')}</time></li>)}</ol>
    </section>}
  </div>;
}
