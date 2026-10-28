import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createDiagnosticsDownload,DiagnosticError,type DiagnosticRun} from './diagnosticsDownload';
const run:DiagnosticRun={run_id:'7233de3c-d636-471d-9fd1-33af63bdc566',session_id:'f76d0537-8b7b-4540-b5ed-c1558b2b7e32',
  profile_id:'c37de935-529b-4129-85f2-7596ccdc6a12',profile_revision:2,effective_hash:'a'.repeat(64)};
const exportId='37c61e0d-13bb-4acb-96a3-bc42459d2e3d';
function artifact(changes:Record<string,unknown>={}){
  const document={schema_version:1,kind:'tacticore_redacted_diagnostics',redacted:true,export_id:exportId,run_id:run.run_id,
    binding:{session_id:run.session_id,commander_id:run.profile_id},effective_profile_available:true,
    effective_profile:{profile_id:run.profile_id,revision:run.profile_revision,effective_hash:run.effective_hash},...changes};
  const content=JSON.stringify(document),bytes=Buffer.byteLength(content),sha256=createHash('sha256').update(content).digest('hex');
  return {receipt:{export_id:exportId,run_id:run.run_id,sha256,bytes,event_count:3,exported_event_count:2,truncated:true,redacted:true},
    read:{export_id:exportId,sha256,bytes,content}};
}
const code=(expected:string)=>(error:unknown)=>error instanceof DiagnosticError&&error.code===expected;

test('exports once, reads UUID and SHA only, verifies exact UTF8 bytes then saves real JSON',async()=>{
  const data=artifact(),calls:unknown[]=[],saved:unknown[]=[];
  const download=createDiagnosticsDownload(async(operation,args)=>{calls.push([operation,args]);return data.receipt;},
    async(command,args)=>{calls.push([command,args]);return data.read;},(filename,content)=>saved.push([filename,content]));
  const result=await download(run);
  assert.deepEqual(calls,[['diagnostics.export',{run_id:run.run_id}],['diagnostics_read',{exportId,expectedSha256:data.receipt.sha256}]]);
  assert.deepEqual(saved,[[`tacticore-diagnostics-${exportId}.json`,data.read.content]]);
  assert.equal(result.truncated,true);assert.equal(result.effective_profile_available,true);
});
test('foreign run receipt is refused before native file read',async()=>{
  const data=artifact();let reads=0,saves=0;
  const download=createDiagnosticsDownload(async()=>({...data.receipt,run_id:run.session_id}),async()=>{reads++;return data.read;},()=>{saves++;});
  await assert.rejects(download(run),code('diagnostics_receipt_invalid'));assert.equal(reads,0);assert.equal(saves,0);
});
test('unknown native read failure never retries export or sends a start operation',async()=>{
  const data=artifact();let exports=0,reads=0,saves=0;
  const download=createDiagnosticsDownload(async(operation)=>{assert.equal(operation,'diagnostics.export');exports++;return data.receipt;},
    async()=>{reads++;throw new Error('PRIVATE_PLATFORM_EXCEPTION');},()=>{saves++;});
  await assert.rejects(download(run),code('diagnostics_read_failed'));
  assert.equal(exports,1);assert.equal(reads,1);assert.equal(saves,0);
});
test('changed content is refused even when native metadata repeats the expected SHA',async()=>{
  const data=artifact();let saves=0;
  const content=data.read.content.replace('tacticore','xacticore');
  const download=createDiagnosticsDownload(async()=>data.receipt,async()=>({...data.read,content}),()=>{saves++;});
  await assert.rejects(download(run),code('diagnostics_integrity_invalid'));assert.equal(saves,0);
});
test('valid hashes do not authorize another profile, revision, session or effective hash',async()=>{
  const variants=[{binding:{session_id:run.run_id,commander_id:run.profile_id}},
    {binding:{session_id:run.session_id,commander_id:run.run_id}},
    {effective_profile:{profile_id:run.run_id,revision:2,effective_hash:run.effective_hash}},
    {effective_profile:{profile_id:run.profile_id,revision:1,effective_hash:run.effective_hash}},
    {effective_profile:{profile_id:run.profile_id,revision:2,effective_hash:'b'.repeat(64)}}];
  for(const changes of variants){const data=artifact(changes);let saves=0;
    await assert.rejects(createDiagnosticsDownload(async()=>data.receipt,async()=>data.read,()=>{saves++;})(run),code('diagnostics_binding_invalid'));
    assert.equal(saves,0);}
});
test('unknown schema or missing redaction is never downloaded',async()=>{
  for(const changes of [{schema_version:2},{redacted:false},{kind:'raw_log'}]){
    const data=artifact(changes);let saves=0;
    await assert.rejects(createDiagnosticsDownload(async()=>data.receipt,async()=>data.read,()=>{saves++;})(run));
    assert.equal(saves,0);}
});
test('explicitly unavailable historical profile stays unavailable in download receipt',async()=>{
  const data=artifact({effective_profile_available:false,effective_profile:null});let saves=0;
  const result=await createDiagnosticsDownload(async()=>data.receipt,async()=>data.read,()=>{saves++;})(run);
  assert.equal(result.effective_profile_available,false);assert.equal(saves,1);
});
