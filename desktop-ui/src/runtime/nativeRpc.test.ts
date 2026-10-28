import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHostRpc, HostError } from './nativeRpc';
const id = '706cc2a3-0689-4aba-94aa-9fdf552b49b8';
test('native save preserves exact CAS envelope and correlates reply', async () => {
  let observed: unknown;
  const rpc = createHostRpc(async (command, args) => {
    observed = {command, args};
    return {schema_version:1,request_id:id,ok:true,result:{state:'saved',host_applied:false}};
  });
  assert.deepEqual(await rpc('profiles.save', {draft:{revision:3},expected_revision:3},id), {state:'saved',host_applied:false});
  assert.deepEqual(observed, {command:'host_request',args:{request:{schema_version:1,request_id:id,operation:'profiles.save',args:{draft:{revision:3},expected_revision:3}}}});
});
test('lost native start is delivery unknown and sends exactly once', async () => {
  let calls=0;
  const rpc=createHostRpc(async()=>{calls++; throw new Error('private diagnostic');});
  await assert.rejects(rpc('run.start',{},id),(error:unknown)=>error instanceof HostError && error.code==='delivery_unknown' && !error.message.includes('private'));
  assert.equal(calls,1);
});
test('cross request success and malformed results cannot become ready',async()=>{
  for (const response of [
    {schema_version:1,request_id:crypto.randomUUID(),ok:true,result:{ready:true}},
    {schema_version:1,request_id:id,ok:true,result:null},
    {schema_version:2,request_id:id,ok:true,result:{}},
  ]) await assert.rejects(createHostRpc(async()=>response)('run.check',{},id), /delivery_unknown/);
});
test('fixed server rejection remains inspectable without exposing arbitrary messages',async()=>{
  const rpc=createHostRpc(async()=>({schema_version:1,request_id:id,ok:false,error:{code:'profile_revision_conflict',message:'not public'}}));
  await assert.rejects(rpc('profiles.save',{},id),(error:unknown)=>error instanceof HostError && error.code==='profile_revision_conflict' && !error.message.includes('not public'));
});
