import {HostError} from './nativeRpc';

type OpeningReady={ready:boolean;reason_code?:string};
const waitingReasons=new Set(['session_not_ready','session_unavailable']);

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
