import {HostError} from './nativeRpc';

type OpeningReady={ready:boolean;reason_code?:string};
const waitingReasons=new Set(['session_not_ready','session_unavailable','session_paused']);

function pause(signal:AbortSignal,milliseconds:number){
  return new Promise<void>(resolve=>{
    if(signal.aborted){resolve();return;}
    const finish=()=>{clearTimeout(timer);signal.removeEventListener('abort',finish);resolve();};
    const timer=setTimeout(finish,milliseconds);signal.addEventListener('abort',finish,{once:true});
  });
}

/** Wait only on read-only admission. A start is submitted at most once. */
export async function startAtOpening<T extends OpeningReady>(options:{
  check:()=>Promise<T>;start:(ready:T)=>Promise<void>;signal:AbortSignal;
  now?:()=>number;sleep?:(signal:AbortSignal,milliseconds:number)=>Promise<void>;
  maximumWaitMs?:number;
}):Promise<'cancelled'|'submitted'>{
  const now=options.now??Date.now,sleep=options.sleep??pause;
  const deadline=now()+(options.maximumWaitMs??300_000);
  while(now()<deadline){
    if(options.signal.aborted)return 'cancelled';
    const ready=await options.check();
    if(options.signal.aborted)return 'cancelled';
    if(ready.ready){await options.start(ready);return 'submitted';}
    if(!waitingReasons.has(ready.reason_code??''))throw new HostError(ready.reason_code??'session_not_ready','opening-wait');
    await sleep(options.signal,2000);
  }
  throw new HostError('opening_wait_expired','opening-wait');
}

export type DiscoveredSession={candidate_id:string;display_name:string;map:string;faction:string;player_id:number;expires_in_seconds:number;requires_preflight:boolean};
export type SessionDiscoveryResult={candidates:DiscoveredSession[];issues:string[];state:string;native_execution_started:false};

/** Prepare an opaque, supported session before admission; never starts a host. */
export async function discoveredOpeningCheck<T extends OpeningReady>(options:{
  check:()=>Promise<T>;discover:()=>Promise<SessionDiscoveryResult>;prepare:(candidateId:string)=>Promise<void>;
  candidateId?:string;signal:AbortSignal;
}):Promise<T>{
  const initial=await options.check();
  if(options.signal.aborted||initial.ready||!['session_unavailable','session_not_ready','session_registration_changed'].includes(initial.reason_code??''))return initial;
  let discovered:SessionDiscoveryResult;
  try{discovered=await options.discover();}catch(error){
    // Existing explicit registrations retain their read-only opening wait even
    // when no new discovery policy has been installed.
    if(error instanceof HostError&&error.code==='session_discovery_unavailable'&&initial.reason_code==='session_not_ready')return initial;
    throw error;
  }
  if(options.signal.aborted)return initial;
  if(!discovered.candidates.length)return {...initial,reason_code:discovered.issues[0]??'session_not_ready'};
  const candidate=options.candidateId?discovered.candidates.find(value=>value.candidate_id===options.candidateId):
    discovered.candidates.length===1?discovered.candidates[0]:undefined;
  if(!candidate)throw new HostError('session_selection_required','opening-wait');
  await options.prepare(candidate.candidate_id);
  if(options.signal.aborted)return initial;
  return options.check();
}
