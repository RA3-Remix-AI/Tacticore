/** Development-only harness. Not imported by either production entry point.
 * All native calls terminate here; no filesystem, network, model or game access.
 */
import React from 'react';
import {createRoot} from 'react-dom/client';
import NativeApp from '../src/NativeApp';
import {preferencePresets} from '../src/state/preferences';
import '../src/styles.css';

const params = new URLSearchParams(location.search);
const firstUse = params.has('first_use');
const profileId='11111111-1111-4111-8111-111111111111';
const connectionId='22222222-2222-4222-8222-222222222222';
const sessionId='33333333-3333-4333-8333-333333333333';
const runId='44444444-4444-4444-8444-444444444444';
const ref={configuration_request_id:'55555555-5555-4555-8555-555555555555',expected_config_fingerprint:'a'.repeat(64)};
const preset=preferencePresets[1];
let initialized=!firstUse, mode=params.get('mode')??'ready', prepared=!firstUse, gameSelected=!firstUse, modSelected=!firstUse;
let inspected=false, stops=0, holdCheck=false;
let releaseCheck:(()=>void)|undefined;
let connection={id:connectionId,name:'本机模型连接',provider:'OpenAI',endpoint:'https://api.example.com/v1',model:firstUse?'':'preview-model',remember_key:!firstUse,credential_configured:!firstUse,credential_check:firstUse?'not_stored':'stored_not_read'};
let draft={schema_version:1,profile_id:profileId,name:'铁锤',revision:1,connection_id:connectionId,model:'',doctrine:preset.doctrine,custom_traits:'优先保持经济稳定，观察敌情后再推进。',preferences:preset.values};
const profile=()=>({profile_id:profileId,name:draft.name,revision:draft.revision,connection_id:connectionId,model:draft.model||connection.model,draft,state:'library',validation:{ok:Boolean(draft.model||connection.model),reason_code:(draft.model||connection.model)?'':'credentials_unavailable'},effective:{effective_hash:'b'.repeat(64),traits:draft.custom_traits,traits_bytes:new TextEncoder().encode(draft.custom_traits).length,axis_support:{}}});
const session={id:sessionId,map:'TemplePrime',player_name:'P3',faction:'Soviet'};
const capabilities={control_mode:'macro',native_macro:true,available_macro_actions:['scout','regroup','withdraw','deployattack','deploydefense','expand']};
function makeRun(id:string){return {run_id:id,session_id:sessionId,profile_id:profileId,profile_revision:draft.revision,effective_hash:'b'.repeat(64),state:'running',native_release_verified:false,session,capabilities,latest_snapshot:{game_time_seconds:185,resources:{credits:3400}},metrics:{requests:7,accepted:6},events:[{seq:1,event_type:'host_started',created_at:new Date().toISOString()},{seq:2,event_type:'commander_model_response_returned',created_at:new Date().toISOString()}]};}
let run:ReturnType<typeof makeRun>|null=params.has('active_run')?makeRun(runId):null;
const calls:Record<string,number>={};
const counter=document.createElement('output');counter.setAttribute('aria-label','预览调用计数');
const bar=document.getElementById('preview-controls')!;
bar.style.cssText='position:fixed;top:0;left:0;right:0;z-index:100;padding:8px 20px;background:#29291d;color:#e1d4a5;font:12px system-ui;display:flex;gap:12px;align-items:center;flex-wrap:wrap;border-bottom:1px solid #67604b';
const previewStyle=document.createElement('style');
previewStyle.textContent='body{padding-top:var(--preview-toolbar-height,40px)} #preview-controls button{background:#1c2119;border:1px solid #67604b;color:#e1d4a5;padding:4px 8px} .nw-sidebar{top:var(--preview-toolbar-height,40px)!important} .nw-topbar{top:var(--preview-toolbar-height,40px)!important}';
document.head.append(previewStyle);
new ResizeObserver(()=>document.documentElement.style.setProperty('--preview-toolbar-height',bar.offsetHeight+'px')).observe(bar);
bar.append('交互预览 · 全部为模拟数据，不连接游戏或模型');
for(const [label,query] of [['已配置',''],['首次使用','?first_use=1'],['运行中','?active_run=1'],['配置待恢复','?mode=pending&active_run=1']]){const a=document.createElement('a');a.textContent=label;a.href=location.pathname+query;a.style.color='inherit';bar.append(a);}
for(const [label,value] of [['模拟配置待恢复','pending'],['模拟配置正常','ready']]){const b=document.createElement('button');b.textContent=label;b.onclick=()=>{mode=value;};bar.append(b);}
for(const [label,action] of [
 ['延迟下一次检查',()=>{holdCheck=true;}],
 ['返回延迟检查',()=>{holdCheck=false;releaseCheck?.();releaseCheck=undefined;}],
] as const){const b=document.createElement('button');b.textContent=label;b.onclick=action;bar.append(b);}
bar.append(counter);
const updateCounter=()=>{counter.textContent=`启动 ${calls['run.start']??0} · 停止 ${calls['run.stop']??0} · 查询连接 ${calls['connections.configuration']??0}`;};
updateCounter();
// Only this dedicated fixture installs a fake native transport.
Object.defineProperty(window,'__TAURI_INTERNALS__',{configurable:true,value:{invoke:async(command:string,input:any)=>{
 const operation=command==='game_setup_request'?input.operation:input.request?.operation;
 calls[operation]=(calls[operation]??0)+1;updateCounter();
 if(command==='game_setup_request'){
  if(operation==='select_game')gameSelected=true;
  if(operation==='select_mod')modSelected=true;
  if(operation==='prepare')prepared=gameSelected&&modSelected;
  return {prepared,game_selected:gameSelected,mod_selected:modSelected,...(operation==='launch'?{game_launch_requested:true}:{})};
 }
 const request=input.request;
 const ok=(result:unknown)=>({schema_version:1,request_id:request.request_id,ok:true,result});
 const fail=(code:string)=>({schema_version:1,request_id:request.request_id,ok:false,error:{code}});
 if(command==='connection_config_request'){
  if(operation==='connections.bootstrap'){initialized=true;return ok({initialized:true});}
  if(!initialized)return fail('connection_setup_required');
  if(operation==='connections.configuration')return ok({schema_version:1,ready:mode==='ready',config_fingerprint:mode==='ready'?'a'.repeat(64):null,connections:mode==='ready'?[connection]:[],recovery:mode==='ready'?[]:[ref],retired_credentials:[],remote_connection_tested:false,host_recheck_required:true});
  if(operation==='connections.configure'){
   const {name,provider,endpoint,model,credential_operation}=request.args;
   connection={...connection,name,provider,endpoint,model,...(credential_operation==='clear'?{credential_configured:false,remember_key:false,credential_check:'not_stored'}:{})};
   return ok({saved:true});
  }
  if(operation==='connections.recover'){mode='ready';return ok({saved:true});}
 }
 if(command==='host_request'){
  if(operation==='run.resume')return ok({run,observation_only:true,other_unreleased_runs:0});
  if(!initialized)return fail('runtime_library_unregistered');
  if(operation==='profiles.list')return ok({profiles:[profile()]});
  if(operation==='profiles.save'){draft={...draft,...request.args.draft,revision:draft.revision+1};return ok({profile:profile(),state:'saved',host_applied:false});}
  if(operation==='connections.list')return ok({connections:[connection]});
  if(operation==='session.inspect')return ok({session:inspected?session:null});
  if(operation==='session.discover')return ok({candidates:[{candidate_id:'preview-candidate',display_name:'TemplePrime · 苏军 P3',session}],issues:[]});
  if(operation==='session.prepare'){inspected=true;return ok({registered:true,requires_preflight:true,session});}
  if(operation==='run.check'){
   const result=mode==='ready'?{ready:true,session_id:sessionId,ready_token:'preview-only',expires_at:Date.now()+60000,session,capabilities}:{ready:false,reason_code:'session_not_ready'};
   if(holdCheck)await new Promise<void>(resolve=>{releaseCheck=resolve;});
   return ok(result);
  }
  if(operation==='run.start'){run=makeRun(request.request_id);return ok(run);}
  if(operation==='run.status'){
   if(run?.state==='stopping'&&++stops>=2)run={...run,state:'stopped',native_release_verified:true};
   return run?ok(run):fail('run_not_found');
  }
  if(operation==='run.stop'){if(run)run={...run,state:'stopping'};return run?ok(run):fail('run_not_found');}
  if(operation==='diagnostics.export')return fail('diagnostics_unavailable');
 }
 return fail('preview_operation_unavailable');
}}});
// Fixture storage remains isolated from normal app origins and tabs.
localStorage.removeItem('tacticore.desktop.native.last-run.v1');
createRoot(document.getElementById('root')!).render(<NativeApp/>);
