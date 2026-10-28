import {test} from 'node:test';
import assert from 'node:assert/strict';
import {startAtOpening} from './openingStart';
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
