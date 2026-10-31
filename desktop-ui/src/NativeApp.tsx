import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Button } from './components/ui';
import { preferenceAxes, preferencePresets, type CommanderPreferences } from './state/preferences';
import type { Doctrine } from './state/settings';
import { hostRpc, HostError, type MacroStrategyPublicState, type MacroExpansionRecord, type MacroAdmissionRecord } from './runtime/nativeRpc';
import { macroStrategyView } from './runtime/macroStrategyView';
import { strategicCommandView, strategicPreflightView, type StrategicClientRecord } from './runtime/strategicCommandView';
import { strategicReevaluationView } from './runtime/strategicReevaluationView';
import { strategicUnifiedFeedbackV5 } from './runtime/strategicUnifiedFeedbackV5';
import { strategicLifecycleView } from './runtime/strategicLifecycleView';
import { macroExpansionView, macroAdmissionView, macroExpansionAvailabilityView } from './runtime/macroExpansionView';
import { sessionDisplay } from './runtime/sessionDisplay';
import { startAtOpening, discoveredOpeningCheck, type DiscoveredSession, type SessionDiscoveryResult } from './runtime/openingStart';
import { applicationView, type AppliedReceipt, type ConsumptionReceipt } from './runtime/applicationView';
import { createDiagnosticsDownload, DiagnosticError, saveDiagnosticFile } from './runtime/diagnosticsDownload';
import { eventDescription, preservePendingStart, releaseDescription, runLocksControls, sameRun, localPreparationDescription, type NativeEvent } from './runtime/nativeProcess';
import { ConnectionConfigPanelV1 } from './ConnectionConfigPanelV1';
import { BetaSetupPanel } from './BetaSetupPanel';
import { configurationAdmissionNotice, type ConnectionConfigurationState } from './runtime/connectionConfigurationStateV1';
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
type Run = {run_id:string;session_id:string;state:string;reason_code?:string;status_age_ms?:number;status_stale?:boolean;host_process_alive?:boolean;profile_id?:string;profile_revision?:number;effective_hash?:string;native_release_verified?:boolean;no_native_execution_started?:boolean;
  profile_application?:AppliedReceipt;profile_consumption?:ConsumptionReceipt;session?:Session;execution_limits?:Limits;capabilities?:Capabilities;
  latest_snapshot?:{game_time_seconds?:number;paused?:boolean;resources?:{credits:number}};execution?:{remaining_budget?:number;executor_connected?:boolean;enabled?:boolean};
  metrics?:{requests?:number;accepted?:number};task_counters?:{dispatches?:number;started?:number;completed?:number;failed?:number;blocked?:number};
  tasks?:Task[];tasks_cursor?:{total_count:number;truncated:boolean};events?:NativeEvent[];
  current_plan?:{macro_actions?:string[];macro_production?:{action:string;additional_count:number}};macro_feedback?:{status:string;selected_policy:string|null};
  macro_strategy?:MacroStrategyPublicState;macro_strategy_unavailable?:boolean;
  strategic_client?:StrategicClientRecord;strategic_client_unavailable?:boolean;
  macro_unified_feedback?:unknown;macro_unified_feedback_unavailable?:boolean;
  macro_expansion_feedback?:MacroExpansionRecord;macro_expansion_feedback_unavailable?:boolean;
  macro_resource_feedback?:MacroAdmissionRecord;macro_resource_feedback_unavailable?:boolean;
  macro_expansion_availability?:unknown;macro_expansion_availability_unavailable?:boolean;
  macro_production_feedback?:{observed_new_queue_count:number;additional_count_requested:number;new_own_unit_observations:number;policy_released:boolean;release_reason:string|null;completed_units_verified:false};
  macro_construction_feedback?:{observed_new_queue_count:number;new_own_construction_object_observations:number;fully_paid_queue_observations:number;policy_released:boolean;construction_completed_verified:false};
  macro_scouting_feedback?:{active_native_tactics:number;moved_native_groups:number;new_legal_contacts_since_intent:number;policy_released:boolean};
  macro_regional_feedback?:{target_region:string;active_native_tactics:number;moved_native_groups:number;groups_progressing_toward_region:number;policy_released:boolean;goal?:string;defender_groups_near_infrastructure?:number;groups_near_home_region?:number;withdrawing_native_groups?:number};
  local_preparation?:{state?:string;reason_code?:string;paid_units_available?:number};
  events_cursor?:{first_seq:number|null;last_seq:number|null;total_count:number;overflow:number;truncated:boolean}};
const reasons:Record<string,string>={
  session_discovery_unavailable:'尚未安装当前版本的受信游戏发现配置，请先完成本机运行组件准备。',
  discovery_policy_invalid:'受信游戏发现配置无效，尚未准备新对局。',discovery_source_unavailable:'受信游戏或运行组件暂不可读取。',
  discovery_source_changed:'游戏或运行组件已变化，请重新核验当前版本。',session_discovery_too_many_processes:'发现的候选过多，请保留需要使用的游戏实例后重试。',
  session_scope_unsupported:'当前只支持已验证的 TemplePrime、P3 苏军及出生位置，请检查对局设置。',
  session_probe_invalid:'游戏身份观测不一致，请等待稳定后重新发现。',session_probe_unavailable:'暂时无法核验游戏身份，请进入受支持的对局后重试。',
  session_paused:'游戏已暂停，恢复后再检查。',session_candidate_expired:'发现结果已过期，请重新发现游戏。',
  session_selection_required:'请先从候选列表选择需要使用的对局。',run_history_unverifiable:'旧运行的归还证据不完整，请先核对运行与诊断，当前不会准备新对局。',
  session_preparation_changed:'已准备的对局记录发生变化，请保留现场并核对诊断。',session_registration_uncertain:'对局登记结果尚未确认，可重试准备；不会启动指挥官。',
  session_root_conflict:'受信会话来源发生冲突，请先核对本机配置。',session_registration_conflict:'旧对局登记尚不能替换，请先查询运行并确认归还。',
  macro_runtime_same_epoch_reattach_unsupported:'当前游戏进程已使用过指挥通道。请正常退出并重新打开受支持的游戏，再准备下一局。',
  adapter_unavailable:'宿主适配仍未就绪。',profile_library_unavailable:'未找到本机指挥官库，请检查已登记的配置。',
  runtime_library_unregistered:'请使用本页初始化本机配置或重新查询连接，再载入配置并检查对局。',runtime_library_unavailable:'已登记的指挥官配置库暂不可读取。',
  registered_library_changed:'已登记的配置库发生变化，请先核对本机配置，当前操作未执行。',
  runtime_configuration_invalid:'本机配置登记无效，请在本页查询并核对配置。',runtime_configuration_changed:'本机配置来源已变化，请在本页重新查询连接、载入配置并检查对局。',
  profile_revision_conflict:'该配置已在另一窗口更新，请重新载入。',traits_budget_exceeded:'风格说明与补充要求合计超过 1200 UTF-8 字节，请缩短补充要求。',
  model_context_capacity_exceeded_shorten_style:'风格说明与战略核心上下文的容量预留合计超限。请缩短补充要求，尤其是大量引号或反斜杠，再重新检查；尚未启用原生指挥通道。',
  model_context_capacity_provider_unavailable:'暂不能确认当前连接提供方的容量配置。请重新载入已保存配置并检查；尚未启用原生指挥通道。',
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
function regionalDetail(value:NonNullable<Run['macro_regional_feedback']>){
  const tasks=`原生任务 ${value.active_native_tactics}`;
  if(value.goal==='original_native_defense_of_own_infrastructure')return `保护己方建筑，${tasks}，基础设施附近的防守小队 ${value.defender_groups_near_infrastructure??0}；原生 AI 选择建筑和操作部队，防守结果仍需核验。`;
  if(value.goal==='reinforce_own_base_through_original_reactive_defense')return `增援己方基地，${tasks}，基础设施附近的小队 ${value.defender_groups_near_infrastructure??0}；原生 AI 选择基地并操作部队，任务成败仍需核验。`;
  if(value.goal==='regroup_native_force_at_own_home_waypoint')return `集结至己方区域，${tasks}，集结区域的小队 ${value.groups_near_home_region??0}；不保证全部到达，原生 AI 负责操作。`;
  if(value.goal==='withdraw_native_group_to_own_home_region')return `向己方区域撤退，${tasks}，已向己方区域推进的小队 ${value.withdrawing_native_groups??0}；不保证全军归队，原生 AI 负责操作。`;
  return `目标 ${value.target_region==='region_1_3'?'西侧起点区域':'东侧起点区域'}，${tasks}，朝目标推进的小队 ${value.groups_progressing_toward_region}；到达及任务成功需另行核验。`;
}
const downloadDiagnostics=createDiagnosticsDownload((operation,args)=>hostRpc(operation,args),invoke,saveDiagnosticFile);

export default function NativeApp(){
  const [profiles,setProfiles]=useState<Profile[]>([]),[connections,setConnections]=useState<Connection[]>([]);
  const [selected,setSelected]=useState(''),[draft,setDraft]=useState<Draft|null>(null),[dirty,setDirty]=useState(false);
  const [ready,setReady]=useState<Ready|null>(null),[run,setRun]=useState<Run|null>(lastRun),[session,setSession]=useState<Session|null>(null);
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('正在读取本机指挥官…'),[clock,setClock]=useState(Date.now());
  const [candidates,setCandidates]=useState<DiscoveredSession[]>([]),[candidateId,setCandidateId]=useState('');
  const [observedAt,setObservedAt]=useState<number|null>(null);
  const preparationRequests=useRef(new Map<string,string>());
  const [openingWaiting,setOpeningWaiting]=useState(false),openingAbort=useRef<AbortController|null>(null);
  const [configurationState,setConfigurationState]=useState<ConnectionConfigurationState>('unverified');
  const configurationGate=useRef<{state:ConnectionConfigurationState;generation:number}>({state:'unverified',generation:0});
  const configurationReady=configurationState==='ready';
  function configurationChanged(state:ConnectionConfigurationState){
    configurationGate.current={state,generation:configurationGate.current.generation+1};
    setConfigurationState(state);setReady(null);
    openingAbort.current?.abort();setOpeningWaiting(false);
  }
  function configurationCurrent(generation=configurationGate.current.generation){
    return configurationGate.current.state==='ready'&&configurationGate.current.generation===generation;
  }
  const pending=useRef(false),profile=profiles.find(p=>p.profile_id===selected);
  const locked=runLocksControls(run?.state,run?.native_release_verified),polling=!!run&&locked;
  const display=sessionDisplay<Session,Run,Ready>(run,session,ready?.ready&&ready.expires_at>clock?ready:null);
  const currentRun=display.current,validReady=!!display.readiness;
  const application=applicationView(dirty||validReady?undefined:profile,currentRun?.profile_application,currentRun?.profile_consumption);
  const strategy=macroStrategyView(currentRun?.macro_strategy,currentRun?.macro_strategy_unavailable);
  const strategic=currentRun?strategicCommandView(currentRun.strategic_client):strategicPreflightView(display.readiness?.capabilities);
  const reevaluation=strategicReevaluationView(currentRun?.macro_strategy);
  const unifiedRows=strategicUnifiedFeedbackV5(currentRun?.macro_unified_feedback);
  const lifecycle=currentRun?strategicLifecycleView(currentRun):null;
  const expansion=macroExpansionView(currentRun?.macro_expansion_feedback,currentRun?.macro_expansion_feedback_unavailable);
  const admission=macroAdmissionView(currentRun?.macro_resource_feedback,currentRun?.macro_resource_feedback_unavailable);
  const availability=macroExpansionAvailabilityView(currentRun?.macro_expansion_availability,currentRun?.macro_expansion_availability_unavailable);
  const connection=connections.find(c=>c.id===draft?.connection_id),limits=display.readiness?.execution_limits??currentRun?.execution_limits;
  const identity=display.identity,capabilities=display.readiness?.capabilities??currentRun?.capabilities;
  function updateRun(value:Run){rememberRun(value);setRun(value);setObservedAt(Date.now());}
  async function perform(work:()=>Promise<void>){if(pending.current)return;pending.current=true;setBusy(true);
    try{await work();}catch(error){setNotice(errorText(error));}finally{pending.current=false;setBusy(false);}}
  async function load(){
    const [p,c,resumed]=await Promise.all([hostRpc<{profiles:Profile[]}>('profiles.list',{}),hostRpc<{connections:Connection[]}>('connections.list',{}),
      hostRpc<{run:Run|null;observation_only:true;other_unreleased_runs:number}>('run.resume',{})]);
    setProfiles(p.profiles);setConnections(c.connections);
    if(resumed.run)updateRun(resumed.run);
    const next=p.profiles.find(value=>value.profile_id===(resumed.run?.profile_id??run?.profile_id??selected))??p.profiles[0];
    if(next){setSelected(next.profile_id);setDraft(structuredClone(next.draft));}
    setDirty(false);setReady(null);
    setNotice(resumed.other_unreleased_runs?'已恢复观察；还有其他未确认归还的运行，请逐项核对，当前不能开始新指挥。':
      resumed.run&&runLocksControls(resumed.run.state,resumed.run.native_release_verified)?'已恢复观察现有宿主，没有新增启动请求。':'已读取本机配置，可发现游戏并准备对局。');
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
  async function discover(){
    setReady(null);const result=await hostRpc<SessionDiscoveryResult>('session.discover',{});
    setCandidates(result.candidates);setCandidateId(current=>result.candidates.some(value=>value.candidate_id===current)?current:
      result.candidates.length===1?result.candidates[0].candidate_id:'');
    setNotice(result.candidates.length?'已发现受支持的对局，选择后准备并检查。':
      reasons[result.issues[0]??'']??'尚未发现受支持的对局，请进入 TemplePrime 的 P3 苏军对局后重新发现。');
  }
  async function prepareCandidate(id:string=candidateId){
    if(!id)throw new HostError('session_selection_required','session-prepare');
    const requestId=preparationRequests.current.get(id)??crypto.randomUUID();preparationRequests.current.set(id,requestId);
    const result=await hostRpc<{registered:boolean;requires_preflight:true;session:Session}>('session.prepare',{candidate_id:id},requestId);
    setSession(result.session);setReady(null);setCandidates([]);setCandidateId('');
    setNotice('对局已准备，请检查当前配置；尚未启动指挥官。');
  }
  async function resume(){
    const result=await hostRpc<{run:Run|null;observation_only:true;other_unreleased_runs:number}>('run.resume',{});
    if(result.run)updateRun(result.run);
    setNotice(result.run?'已恢复观察已有运行，没有新增启动请求。':'尚未发现已登记的宿主运行。');
  }
  async function check(){if(!configurationCurrent()||!profile)return;const generation=configurationGate.current.generation;setReady(null);setSession(null);
    const result=await hostRpc<Ready>('run.check',{profile_id:profile.profile_id,profile_revision:profile.revision,effective_hash:profile.effective?.effective_hash});
    if(!configurationCurrent(generation))return;
    setReady(result);setClock(Date.now());if(result.session)setSession(result.session);
    else{const inspected=await hostRpc<{session:Session|null}>('session.inspect',{profile_id:profile.profile_id});if(!configurationCurrent(generation))return;setSession(inspected.session);}
    setNotice(result.ready?'对局检查通过，可在有效期内启动。':(reasons[result.reason_code??'']??`尚未就绪（${result.reason_code??'not_ready'}）。`));}
  async function start(admission:Ready|null=ready,generation=configurationGate.current.generation){
    if(!configurationCurrent(generation))return;
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
    if(!configurationCurrent()||!profile||dirty||locked)return;
    const generation=configurationGate.current.generation;
    const controller=new AbortController();openingAbort.current=controller;setOpeningWaiting(true);setReady(null);
    setNotice('等待进入受支持的对局，发现、准备并核验通过后自动启动；五分钟内可随时取消等待。');
    try{
      const result=await startAtOpening({signal:controller.signal,
        check:()=>discoveredOpeningCheck({signal:controller.signal,candidateId:candidateId||undefined,
          check:()=>{if(!configurationCurrent(generation))throw new HostError('connection_config_recovery_required','configuration');
            return hostRpc<Ready>('run.check',{profile_id:profile.profile_id,profile_revision:profile.revision,effective_hash:profile.effective?.effective_hash});},
          discover:()=>hostRpc<SessionDiscoveryResult>('session.discover',{}),prepare:prepareCandidate}),
        start:async admission=>{if(!configurationCurrent(generation))return;setOpeningWaiting(false);if(admission.session)setSession(admission.session);await start(admission,generation);}});
      if(result==='cancelled')setNotice('已取消等待，没有新增启动请求。');
    }finally{openingAbort.current=null;setOpeningWaiting(false);}
  }
  async function query(){if(!run)return;const value=await hostRpc<Run>('run.status',{run_id:run.run_id});
    if(!sameRun(run,value))throw new HostError('delivery_unknown',run.run_id);updateRun(value);}
  async function stop(){if(!run)return;const value=await hostRpc<Run>('run.stop',{run_id:run.run_id,session_id:run.session_id});
    if(!sameRun(run,value))throw new HostError('delivery_unknown',run.run_id);updateRun(value);setNotice('已请求停止，控制是否归还仍以独立验证为准。');}
  async function download(){if(!run)return;const receipt=await downloadDiagnostics(run);setNotice(`脱敏诊断已生成，已发起下载：${receipt.exported_event_count} / ${receipt.event_count} 条事件${receipt.truncated?'（仅最近记录，已明确截断）':''}。${receipt.effective_profile_available?'':'历史配置快照不可用，文件已注明。'}文件包含完整性哈希，自由文本和原始日志正文未打包。`);}
  const preferences=draft?.preferences??preferencePresets.find(p=>p.doctrine===draft?.doctrine)?.values??preferencePresets[1].values;
  return <div className="native-app">
    <header className="native-header"><div><p className="eyebrow">TACTICORE / 本机客户端</p><h1>配置指挥官，进入战场</h1></div><span className="native-tag">原生连接</span></header>
    <p role="status" className="native-notice">{configurationAdmissionNotice(configurationState)??notice}</p>
    <BetaSetupPanel locked={locked} onPrepared={()=>{setReady(null);setSession(null);setCandidates([]);}} />
    <ConnectionConfigPanelV1 locked={locked} onConfigurationState={configurationChanged} onSaved={async()=>{setReady(null);await load();}} />
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
          <dt>本机读取核验</dt><dd>{validReady?'当前配置已通过本机读取检查':'尚未通过当前配置的对局检查'}</dd></dl>
        <label>指挥官模型<input value={draft.model} disabled={busy||locked} onChange={e=>edit({model:e.target.value})} placeholder="留空使用连接默认模型"/></label>
        <p className="native-muted">列表不会读取密钥。连接和凭据由原生客户端管理；远端可用性以实际模型调用结果为准。</p>
      </>}
    </section><section className="native-panel"><h2>对局与应用状态</h2>
      <ol className="native-status"><li>配置：{dirty?'有未保存修改':profile?.state==='saved'?'已保存':'本机库原始配置'}</li>
        <li>宿主应用：{application.applied?'已收到当前修订的应用回执':'等待当前风格的应用回执'}</li>
        <li>模型消费：{application.responded?'已收到模型响应':application.called?'已发起模型调用':'等待当前风格的消费回执'}</li>
        <li>对局：{validReady?'检查通过':currentRun?stateLabel[currentRun.state]??'等待核对宿主状态':identity?'已准备，等待检查':'等待检查'}</li>
        <li>控制归还：{!currentRun?'当前对局尚未启动指挥官':currentRun.no_native_execution_started?'启动已在派发前取消，未新增原生指挥':releaseDescription(currentRun.native_release_verified)}</li></ol>
      <p className="native-muted">停止与结算候选均需单独核验控制归还。配置变化后必须重新检查。</p>
      {validReady&&<p className="native-muted">检查有效期剩余 {Math.max(0,Math.ceil((ready!.expires_at-clock)/1000))} 秒。</p>}
      {currentRun&&observedAt&&<p className="native-muted">最后成功同步：{new Date(observedAt).toLocaleTimeString('zh-CN')}。查询失败时保留上次观测，不视为当前事实。</p>}
      {currentRun?.status_stale&&<p className="native-warning">{currentRun.host_process_alive===false?'宿主进程已结束，以下为最后保存的状态。':`宿主状态已 ${Math.floor((currentRun.status_age_ms??0)/1000)} 秒未更新，以下为上次记录。`}</p>}
      {currentRun?.reason_code&&currentRun.reason_code!=='user_stop'&&<p className="native-muted">{reasons[currentRun.reason_code]??`运行状态说明：${currentRun.reason_code}`}</p>}
      <div className="native-actions"><Button disabled={busy||locked} onClick={()=>void perform(discover)}>发现游戏 / 准备下一局</Button>
        <Button disabled={busy} onClick={()=>void perform(resume)}>恢复观察已有宿主</Button></div>
      {!!candidates.length&&<><label>受支持的对局<select value={candidateId} disabled={busy||locked} onChange={e=>setCandidateId(e.target.value)}>
        <option value="">请选择对局</option>{candidates.map((candidate,index)=><option key={candidate.candidate_id} value={candidate.candidate_id}>{candidate.display_name} · {index+1}</option>)}</select></label>
        <div className="native-actions"><Button disabled={busy||locked||!candidateId} onClick={()=>void perform(prepareCandidate)}>准备所选对局</Button></div></>}
      {run&&!locked&&<p className="native-muted">{run.no_native_execution_started?'上一轮启动在派发前取消，未取得原生控制。':'上一轮已独立确认归还。'}准备下一局时仍须发现并核验新的受支持会话；当前同进程再次接入尚未开放。</p>}
      <div className="native-actions"><Button disabled={!configurationReady||busy||dirty||locked||!profile?.validation.ok} onClick={()=>void perform(check)}>检查对局</Button>
        <Button disabled={!configurationReady||busy||dirty||locked||!validReady} onClick={()=>void perform(start)}>启动指挥官</Button>
        {openingWaiting?<Button onClick={()=>openingAbort.current?.abort()}>取消等待</Button>:
          <Button disabled={!configurationReady||busy||dirty||locked||!profile?.validation.ok} onClick={()=>void perform(openingStart)}>进入对局后自动启动</Button>}
        <Button disabled={busy||!locked} onClick={()=>void perform(stop)}>请求停止</Button>{run&&<Button disabled={busy} onClick={()=>void perform(query)}>查询运行状态</Button>}</div>
      <h3>绑定的真实对局</h3><dl className="native-facts"><dt>地图</dt><dd>{identity?.map??'尚未核验'}</dd><dt>电脑</dt><dd>{identity?.player_name??'尚未核验'}{identity?.faction==='Soviet'?' · 苏军':''}</dd>
        <dt>{display.lastHostSample?'宿主最后采样时间':'游戏时间'}</dt><dd>{currentRun?.latest_snapshot?.game_time_seconds===undefined?'等待当前对局采样':`${Math.floor(currentRun.latest_snapshot.game_time_seconds)} 秒${currentRun.latest_snapshot.paused?' · 暂停':''}`}</dd>
        <dt>{display.lastHostSample?'宿主最后采样资金':'当前资金'}</dt><dd>{number(currentRun?.latest_snapshot?.resources?.credits)}</dd></dl>
      {display.sessionId&&<p className="native-id">对局编号 {display.sessionId}{currentRun&&<><br/>运行编号 {currentRun.run_id}</>}</p>}
      {display.historical&&<p className="native-muted">已保留上一局宿主记录；该局的采样、应用回执和模型回执不会用于当前对局。查询与诊断对应下方注明编号的上一局记录。</p>}
      {capabilities?.native_macro&&<><h3>{display.lastHostSample?'长期战略（宿主最后记录）':'长期战略'}</h3>
        <dl className="native-facts"><dt>当前目标</dt><dd>{strategy.objective}</dd><dt>当前阶段</dt><dd>{strategy.phase}</dd>
          <dt>期待变化</dt><dd>{strategy.expectation}</dd><dt>最近观测结果</dt><dd>{strategy.latest}</dd>
          <dt>保持或调整</dt><dd>{strategy.guard}</dd></dl>
        <p className={strategy.uncertain?'native-warning':'native-muted'}>{strategy.pending}</p>
        {strategy.updated&&<p className="native-muted">{strategy.updated}。期待变化是模型目标，是否发生以观测结果为准。</p>}
        {reevaluation.available&&<><h4>效果与重评记录</h4><ul>{reevaluation.history.map((row,index)=><li key={index}>{row}</li>)}</ul>
          <p className={reevaluation.uncertain?'native-warning':'native-muted'}>{reevaluation.next}</p></>}
        <p className="native-muted">本条宏观意图结束与整体控制归还分别核验；整体归还以上方独立验证为准。</p>
        {lifecycle&&<p className="native-muted">{lifecycle.next} {lifecycle.reason}</p>}</>}
      <h3>执行边界</h3>{capabilities?.native_macro?<dl className="native-facts">
        <dt>职责核验</dt><dd>{strategic.boundary}</dd>
        <dt>本局高层能力</dt><dd>{strategic.capabilities}</dd>
        <dt>{display.lastHostSample?'最近模型意图（最后记录）':'当前模型意图'}</dt><dd>{strategic.current}</dd>
        <dt>{display.lastHostSample?'原生预算反馈（最后记录）':'原生预算反馈'}</dt><dd>{strategic.budget}</dd>
        <dt>具体执行</dt><dd>{strategic.nativeDetails}</dd>
        {strategic.available&&strategic.unconnected.length>0&&<><dt>尚未接通</dt><dd>{strategic.unconnected.join(' ')}</dd></>}
        {strategic.available&&unifiedRows.length>0&&<><dt>原生战略观测</dt><dd>{unifiedRows.map(row=><p key={row}>{row}</p>)}</dd></>}
        {currentRun?.macro_unified_feedback_unavailable&&<><dt>原生战略观测</dt><dd>当前记录无法核验，等待新的有效观测。</dd></>}
        {strategic.available&&currentRun?.macro_scouting_feedback&&<><dt>侦察观测</dt><dd>原生任务 {currentRun.macro_scouting_feedback.active_native_tactics}，已移动小队 {currentRun.macro_scouting_feedback.moved_native_groups}，新增合法接触 {currentRun.macro_scouting_feedback.new_legal_contacts_since_intent}；{currentRun.macro_scouting_feedback.policy_released?'侦察偏好已释放':'原生 AI 执行中'}。新增情报也可能来自其他己方单位。</dd></>}
        {strategic.available&&currentRun?.macro_regional_feedback&&<><dt>区域调度观测</dt><dd>{regionalDetail(currentRun.macro_regional_feedback)} {currentRun.macro_regional_feedback.policy_released?'偏好已释放':'原生 AI 执行中'}。</dd></>}
        <dt>效果判断</dt><dd>{strategic.evidence}</dd></dl>:<dl className="native-facts"><dt>生产总预算</dt><dd>{number(limits?.production_total_budget)}</dd><dt>资金保留底线</dt><dd>{number(limits?.reserve_floor)}</dd>
        <dt>单次预算上限</dt><dd>{number(limits?.max_command_budget)}</dd><dt>剩余生产预算</dt><dd>{number(currentRun?.execution?.remaining_budget)}</dd>
        <dt>已准入单位</dt><dd>{capabilities?.supported_units?.map(unit=>unit==='conscript'?'动员兵':unit).join('、')||'等待证据核验'}</dd></dl>}
      <p className="native-muted">核心负责宏观决策，具体操作沿用原生 AI。只执行本局检查已授予的能力；各任务受资源、队伍可用性和期限约束。风格偏好不会自动授予执行能力。</p>
      {capabilities?.native_macro&&strategic.historical&&<p className="native-muted">历史精细研究记录可从诊断保留，不作为当前战略能力展示。</p>}
      {capabilities?.native_macro&&strategic.historical&&(availability.rows.length>0||availability.uncertain)&&<>
        <h3>扩展能力等待原因{display.lastHostSample?'（宿主最后记录）':''}</h3>
        {availability.available?<ul>{availability.rows.map(row=><li key={row}>{row}</li>)}</ul>
          :<p className="native-warning">准入检查记录暂不可核验。</p>}
        <p className="native-muted">以下为上次检查结果；派发前会再次检查。未决请求不会自动重发。</p>
      </>}
      {capabilities?.native_macro&&strategic.historical&&(currentRun?.macro_expansion_feedback||currentRun?.macro_expansion_feedback_unavailable)&&<>
        <h3>{display.lastHostSample?'扩展观测（宿主最后记录）':'扩展观测'}</h3>
        {expansion.available?<><dl className="native-facts"><dt>本条目标</dt><dd>{expansion.action}</dd>
          <dt>队列观测</dt><dd>{expansion.queues}</dd><dt>己方对象观测</dt><dd>{expansion.observations}</dd>
          <dt>偏好状态</dt><dd>{expansion.preference}</dd></dl><p className="native-muted">{expansion.updated}。{expansion.verification}</p></>
          :<p className="native-warning">{expansion.verification}</p>}</>}
      {capabilities?.native_macro&&strategic.historical&&(currentRun?.macro_resource_feedback||currentRun?.macro_resource_feedback_unavailable)&&<>
        <h3>{display.lastHostSample?'请求额度（宿主最后记录）':'请求额度'}</h3>
        {admission.available?<><dl className="native-facts"><dt>额度缓冲</dt><dd>{admission.buffer}</dd>
          <dt>请求状态</dt><dd className={admission.uncertain?'native-warning':undefined}>{admission.state}</dd>
          <dt>独立清除</dt><dd>{admission.clear}</dd><dt>财务重核</dt><dd>{admission.financial}</dd></dl>
          <p className="native-muted">{admission.next}</p><p className="native-muted">{admission.limits}</p></>
          :<p className="native-warning">{admission.state} {admission.next}</p>}</>}
      {currentRun?.local_preparation&&<p className="native-muted">局部机动准备：{localPreparationDescription(currentRun.local_preparation.state)}</p>}
    </section></div>
    {run&&<section className="native-panel native-process"><div className="native-section-heading"><div><h2>{display.historical?'上一局任务与过程记录':'任务与过程记录'}</h2><p className="native-id">运行编号 {run.run_id} · 对局编号 {run.session_id}</p><p className="native-muted">模型请求 {number(run.metrics?.requests)} · 接受方案 {number(run.metrics?.accepted)} · 实际派发 {number(run.task_counters?.dispatches)} · 完成 {number(run.task_counters?.completed)} · 受阻 {number(run.task_counters?.blocked)}</p></div>
      <Button disabled={busy} onClick={()=>void perform(download)}>下载脱敏诊断</Button></div>
      {display.historical&&<p className="native-muted">上一局状态：{stateLabel[run.state]??'等待核对宿主状态'} · {releaseDescription(run.native_release_verified)}。{observedAt?`该运行最后成功同步于 ${new Date(observedAt).toLocaleTimeString('zh-CN')}。`:''}</p>}
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
