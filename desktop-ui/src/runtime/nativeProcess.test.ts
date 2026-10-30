import {test} from 'node:test';
import assert from 'node:assert/strict';
import {eventDescription,preservePendingStart,releaseDescription,runLocksControls,sameRun,localPreparationDescription} from './nativeProcess';

test('local readiness and closed waiting are distinct from task completion',()=>{
  assert.match(localPreparationDescription('available'),/等待模型选择/);
  assert.match(localPreparationDescription('retired_waiting_paid_unit'),/旧通道已清理/);
  assert.match(localPreparationDescription('waiting_native_readiness'),/等待/);
  assert.equal(localPreparationDescription('invented_success'),'等待宿主核验');
});
test('unknown/fault/result states remain locked and are never permission to retry start',()=>{
  for(const state of ['uncertain','starting','sampling_wait','fault','result_candidate','unknown_future_state'])assert.equal(runLocksControls(state),true);
  for(const code of ['delivery_unknown','bridge_unavailable','local_state_unavailable','run_state_conflict',undefined])assert.equal(preservePendingStart(code),true);
  assert.equal(preservePendingStart('readiness_expired'),false);
});
test('stopped host does not imply verified physical native release',()=>{
  assert.equal(runLocksControls('stopped'),true);
  assert.equal(runLocksControls('completed'),true);
  assert.equal(runLocksControls('stopped',true),false);
  assert.equal(runLocksControls('completed',true),false);
  assert.equal(releaseDescription(false),'尚未收到独立控制归还验证');
  assert.equal(releaseDescription(undefined),'尚未收到独立控制归还验证');
  assert.equal(releaseDescription(true),'已收到独立控制归还验证');
});
test('independent verified release unlocks a terminal fault, while a running or unknown run stays locked',()=>{
  assert.equal(runLocksControls('fault',true),false);
  assert.equal(runLocksControls('result_candidate',true),false);
  for(const state of ['running','uncertain','starting'])assert.equal(runLocksControls(state,true),true);
  assert.equal(runLocksControls('fault',false),true);
});
test('cross-run/session status cannot replace the pending run and a mismatched profile event remains explicit',()=>{
  assert.equal(sameRun({run_id:'one',session_id:'s'},{run_id:'two',session_id:'s'}),false);
  assert.equal(sameRun({run_id:'one',session_id:'s'},{run_id:'one',session_id:'foreign'}),false);
  assert.equal(sameRun({run_id:'one',session_id:'s'},{run_id:'one',session_id:'s'}),true);
  const label=eventDescription({seq:2,event_type:'commander_model_response_returned',created_at:'2026-10-26',profile_binding_matches:false});
  assert.match(label,/其他配置修订/);
});
