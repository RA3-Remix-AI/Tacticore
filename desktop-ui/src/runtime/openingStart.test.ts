import {test} from 'node:test';
import assert from 'node:assert/strict';
import {startAtOpening,discoveredOpeningCheck,type SessionDiscoveryResult} from './openingStart';
import {HostError} from './nativeRpc';

test('waits on admission then submits one start with that exact ready binding',async()=>{
  let checks=0,starts=0,clock=0;const ready={ready:true,session_id:'bound-session'};
  const outcome=await startAtOpening({signal:new AbortController().signal,now:()=>clock,
    sleep:async()=>{clock+=2000;},check:async()=>++checks===1?{ready:false,reason_code:'session_not_ready'}:ready,
    start:async value=>{starts++;assert.equal(value,ready);}});
  assert.equal(outcome,'submitted');assert.equal(checks,2);assert.equal(starts,1);
});
test('cancellation during an in-flight admission cannot later submit a start',async()=>{
  const controller=new AbortController();let starts=0;
  const outcome=await startAtOpening({signal:controller.signal,check:async()=>{controller.abort();return {ready:true};},
    start:async()=>{starts++;}});
  assert.equal(outcome,'cancelled');assert.equal(starts,0);
});
test('unknown start delivery is never retried by the opening waiter',async()=>{
  let checks=0,starts=0;
  await assert.rejects(startAtOpening({signal:new AbortController().signal,check:async()=>{checks++;return {ready:true};},
    start:async()=>{starts++;throw new HostError('delivery_unknown','test-request');}}),/delivery_unknown/);
  assert.equal(checks,1);assert.equal(starts,1);
});
test('a conflict or changed profile stops waiting without a new start intent',async()=>{
  for(const code of ['run_state_conflict','effective_profile_changed','session_registration_changed']){
    let starts=0;
    await assert.rejects(startAtOpening({signal:new AbortController().signal,
      check:async()=>({ready:false,reason_code:code}),start:async()=>{starts++;}}),new RegExp(code));
    assert.equal(starts,0);
  }
});
test('waiting has a deadline and creates no start when the game never becomes ready',async()=>{
  let clock=0,starts=0;
  await assert.rejects(startAtOpening({signal:new AbortController().signal,now:()=>clock,maximumWaitMs:4000,
    sleep:async()=>{clock+=2000;},check:async()=>({ready:false,reason_code:'session_unavailable'}),
    start:async()=>{starts++;}}),/opening_wait_expired/);
  assert.equal(starts,0);
});

const supported=(ids=['one']):SessionDiscoveryResult=>({candidates:ids.map(candidate_id=>({candidate_id,display_name:'TemplePrime / P3 苏军',map:'TemplePrime',faction:'Soviet',player_id:3,expires_in_seconds:90,requires_preflight:true})),issues:[],state:'select_session',native_execution_started:false});
test('missing registration is discovered and prepared before a fresh admission, with no host start',async()=>{
  const calls:string[]=[];let checks=0;
  const result=await discoveredOpeningCheck({signal:new AbortController().signal,
    check:async()=>{calls.push('check');return ++checks===1?{ready:false,reason_code:'session_unavailable'}:{ready:true};},
    discover:async()=>{calls.push('discover');return supported();},prepare:async id=>{calls.push('prepare:'+id);}});
  assert.equal(result.ready,true);assert.deepEqual(calls,['check','discover','prepare:one','check']);
});
test('already-ready admission does not rediscover or prepare anything',async()=>{
  let called=0;const ready={ready:true};
  assert.equal(await discoveredOpeningCheck({signal:new AbortController().signal,check:async()=>ready,
    discover:async()=>{called++;return supported();},prepare:async()=>{called++;}}),ready);
  assert.equal(called,0);
});
test('multiple candidates require a deliberate opaque selection',async()=>{
  let prepared=0;
  const options={signal:new AbortController().signal,check:async()=>({ready:false,reason_code:'session_unavailable'}),
    discover:async()=>supported(['one','two']),prepare:async(id:string)=>{prepared++;assert.equal(id,'two');}};
  await assert.rejects(discoveredOpeningCheck(options),/session_selection_required/);
  assert.equal(prepared,0);
  await discoveredOpeningCheck({...options,candidateId:'two'});assert.equal(prepared,1);
});
test('cancelling discovery prevents even metadata preparation',async()=>{
  const controller=new AbortController();let prepared=0;
  await discoveredOpeningCheck({signal:controller.signal,check:async()=>({ready:false,reason_code:'session_unavailable'}),
    discover:async()=>{controller.abort();return supported();},prepare:async()=>{prepared++;}});
  assert.equal(prepared,0);
});
test('unknown preparation result propagates and cannot reach another admission or start',async()=>{
  let checks=0;
  await assert.rejects(discoveredOpeningCheck({signal:new AbortController().signal,
    check:async()=>{checks++;return {ready:false,reason_code:'session_unavailable'};},discover:async()=>supported(),
    prepare:async()=>{throw new HostError('session_registration_uncertain','prepare');}}),/session_registration_uncertain/);
  assert.equal(checks,1);
});
test('an unsupported or paused scene reports its actual refusal instead of guessing readiness',async()=>{
  for(const issue of ['session_scope_unsupported','session_paused']){
    const result=await discoveredOpeningCheck({signal:new AbortController().signal,check:async()=>({ready:false,reason_code:'session_not_ready'}),
      discover:async()=>({...supported([]),issues:[issue]}),prepare:async()=>{assert.fail('must not prepare');}});
    assert.equal(result.ready,false);assert.equal(result.reason_code,issue);
  }
});
test('a missing discovery policy preserves existing explicit-registration opening waits',async()=>{
  const initial={ready:false,reason_code:'session_not_ready'};
  assert.equal(await discoveredOpeningCheck({signal:new AbortController().signal,check:async()=>initial,
    discover:async()=>{throw new HostError('session_discovery_unavailable','discover');},prepare:async()=>{assert.fail();}}),initial);
});
