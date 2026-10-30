import {runLocksControls} from './nativeProcess';

interface Identity {id:string}
interface SessionRun<I extends Identity> {
  session_id:string;state:string;native_release_verified?:boolean;session?:I;status_stale?:boolean;
}
interface Readiness<I extends Identity> {ready:boolean;session_id:string;session?:I}

/** Select display data independently of the raw run used for control and diagnostics. */
export function sessionDisplay<I extends Identity,R extends SessionRun<I>,T extends Readiness<I>>(
  run:R|null|undefined,inspected:I|null|undefined,ready:T|null|undefined,
){
  const locked=runLocksControls(run?.state,run?.native_release_verified);
  // A mismatched summary is not a usable readiness identity or capability source.
  const admitted=ready?.ready&&(!ready.session||ready.session.id===ready.session_id)?ready:undefined;
  const sessionId=locked?run?.session_id:(admitted?.session_id??inspected?.id??run?.session_id);
  const summaries=locked?[run?.session,admitted?.session,inspected]:[admitted?.session,inspected,run?.session];
  const identity=summaries.find(value=>value?.id===sessionId)??undefined;
  const current=run?.session_id===sessionId?run:undefined;
  return {locked,sessionId,identity,current,historical:run&&!current?run:undefined,
    readiness:admitted?.session_id===sessionId?admitted:undefined,
    lastHostSample:!!current&&(current.status_stale===true||['completed','stopped','fault','result_candidate'].includes(current.state))};
}
