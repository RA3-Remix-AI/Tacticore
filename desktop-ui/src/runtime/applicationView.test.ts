import {test} from 'node:test';
import assert from 'node:assert/strict';
import {applicationView} from './applicationView';
const profile={profile_id:'current',revision:2,effective:{effective_hash:'hash'}};
const applied={profile_id:'current',profile_revision:2,effective_hash:'hash',state:'host_profile_applied'};
test('saved/current values alone never claim host or model consumption',()=>{
  assert.deepEqual(applicationView(profile,undefined,undefined),{applied:false,called:false,responded:false});
  assert.deepEqual(applicationView(profile,applied,{...applied,calls_started:1,responses_returned:0,model_response_received:false}),{applied:true,called:true,responded:false});
});
test('foreign or previous configuration receipts cannot light up current style',()=>{
  for(const changed of [{profile_id:'other'},{profile_revision:1},{effective_hash:'other'}]){
    const receipt={...applied,...changed,calls_started:1,responses_returned:1,model_response_received:true};
    assert.deepEqual(applicationView(profile,receipt,receipt),{applied:false,called:false,responded:false});
  }
});
test('a bound returned model response is distinct from a started call',()=>{
  assert.deepEqual(applicationView(profile,applied,{...applied,calls_started:1,responses_returned:1,model_response_received:true}),{applied:true,called:true,responded:true});
});
