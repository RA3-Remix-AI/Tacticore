import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sessionDisplay} from '../src/runtime/sessionDisplay';
import {applicationView} from '../src/runtime/applicationView';

type Identity={id:string;map?:string};
type Run={run_id:string;session_id:string;state:string;native_release_verified?:boolean;session?:Identity;
  status_stale?:boolean;latest_snapshot?:{game_time_seconds:number;resources:{credits:number}};
  profile_application?:{state:string;profile_id:string;profile_revision:number;effective_hash:string};
  profile_consumption?:{profile_id:string;profile_revision:number;effective_hash:string;calls_started:number;responses_returned:number;model_response_received:boolean}};
const selectView=(run:Run|undefined,inspected?:Identity,ready?:{ready:boolean;session_id:string;session?:Identity})=>sessionDisplay<Identity,Run,{ready:boolean;session_id:string;session?:Identity}>(run,inspected,ready);
const old=():Run=>({run_id:'old-run',session_id:'old-session',state:'stopped',native_release_verified:true,
  session:{id:'old-session',map:'TemplePrime'},status_stale:true,
  latest_snapshot:{game_time_seconds:695,resources:{credits:12345}},
  profile_application:{state:'host_profile_applied',profile_id:'profile',profile_revision:1,effective_hash:'hash'},
  profile_consumption:{profile_id:'profile',profile_revision:1,effective_hash:'hash',calls_started:1,responses_returned:1,model_response_received:true}});

test('new prepared session never borrows previous host 695 seconds or funds',()=>{
  const previous=old();const view=selectView(previous,{id:'new-session',map:'TemplePrime'});
  assert.equal(view.sessionId,'new-session');assert.equal(view.current,undefined);assert.equal(view.current?.latest_snapshot,undefined);
  assert.equal(view.historical,previous);assert.equal(view.locked,false);
});
test('same profile/revision/hash does not transfer application/model receipts across sessions',()=>{
  const profile={profile_id:'profile',revision:1,effective:{effective_hash:'hash'}};
  const previous=old();assert.equal(applicationView(profile,previous.profile_application,previous.profile_consumption).responded,true);
  const view=selectView(previous,{id:'new-session'});
  const result=applicationView(profile,view.current?.profile_application,view.current?.profile_consumption);
  assert.equal(result.applied,false);assert.equal(result.called,false);assert.equal(result.responded,false);
});
test('unknown or unverified old run keeps original lock and original identity',()=>{
  const previous={...old(),state:'uncertain',native_release_verified:false,session:undefined};
  const view=selectView(previous,{id:'new-session'}, {ready:true,session_id:'new-session',session:{id:'new-session'}});
  assert.equal(view.locked,true);assert.equal(view.sessionId,'old-session');assert.equal(view.identity,undefined);assert.equal(view.readiness,undefined);
  assert.equal(view.current,previous);assert.equal(view.historical,undefined);
});
test('same-session terminal sample is explicitly last-host data rather than fresh game time',()=>{
  const view=selectView({...old(),status_stale:false},{id:'old-session'});
  assert.equal(view.current?.latest_snapshot?.game_time_seconds,695);assert.equal(view.lastHostSample,true);
});
test('late old status or malformed readiness summary cannot replace inspected new identity',()=>{
  const view=selectView(old(),{id:'new-session'}, {ready:true,session_id:'new-session',session:{id:'old-session'}});
  assert.equal(view.sessionId,'new-session');assert.equal(view.current?.latest_snapshot,undefined);assert.equal(view.historical?.session_id,'old-session');
  assert.equal(view.readiness,undefined);
  const failed=selectView(old(),{id:'new-session'}, {ready:false,session_id:'old-session',session:{id:'old-session'}});
  assert.equal(failed.sessionId,'new-session');assert.equal(failed.current?.latest_snapshot,undefined);
});
test('matching readiness selects current identity and retains only current capabilities',()=>{
  const admission={ready:true,session_id:'new-session',session:{id:'new-session'},capabilities:{native_macro:true}};
  const view=sessionDisplay(old(),{id:'old-session'},admission);
  assert.equal(view.sessionId,'new-session');assert.equal(view.identity,admission.session);assert.equal(view.readiness,admission);
  assert.equal(view.current,undefined);assert.equal(view.historical?.run_id,'old-run');
});
test('stopped independent release unlocks without treating terminal state or stale data as release',()=>{
  for(const state of ['stopped','fault','result_candidate','completed']){
    assert.equal(selectView({...old(),state,native_release_verified:true},{id:'new-session'}).locked,false);
    for(const verified of [undefined,false]){
      const view=selectView({...old(),state,native_release_verified:verified},{id:'new-session'});
      assert.equal(view.locked,true);assert.equal(view.sessionId,'old-session');
    }
  }
  const running=selectView({...old(),state:'running',status_stale:false,native_release_verified:true},{id:'new-session'});
  assert.equal(running.locked,true);assert.equal(running.lastHostSample,false);
});
test('readiness identity without summary uses only a matching inspected summary',()=>{
  const view=selectView(old(),{id:'new-session'}, {ready:true,session_id:'new-session'});
  assert.equal(view.identity?.id,'new-session');assert.equal(view.current,undefined);assert.equal(view.locked,false);
  assert.equal(selectView(old(),{id:'old-session'},{ready:true,session_id:'new-session'}).identity,undefined);
});
