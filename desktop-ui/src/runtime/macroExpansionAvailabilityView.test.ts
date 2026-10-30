import {test} from 'node:test';
import assert from 'node:assert/strict';
import {macroExpansionAvailabilityView} from './macroExpansionView';

const record=()=>({schema_version:1,kind:'macro_expansion_availability_record_v1',entries:[{action:'producesickle',reason:'insufficient_funds'}],record_only:true,dispatch_authorized:false,automatic_retry:false,payment_verified:false,global_native_release_verified:false});
test('wait reason describes last check without granting cash or automatic dispatch',()=>{
 const view=macroExpansionAvailabilityView(record());assert.equal(view.available,true);assert.match(view.rows[0],/镰刀.*上次.*资金不足/);
 assert.equal(view.uncertain,false);assert.doesNotMatch(view.rows.join(''),/850|已付款|当前余额/);
});
test('producer and previous pending request stay distinct from funds',()=>{
 for(const [reason,text]of [['producer_unready','生产者'],['previous_request_pending','上一条请求'],['unverified','完整准入事实']]){
  const value=record();value.entries[0].reason=reason;assert.match(macroExpansionAvailabilityView(value).rows[0],new RegExp(text));
 }
});
test('forged authority payment release retry and malformed domain fail closed',()=>{
 for(const key of ['dispatch_authorized','automatic_retry','payment_verified','global_native_release_verified']){
  assert.equal(macroExpansionAvailabilityView({...record(),[key]:true}).available,false);
 }
 for(const value of [{...record(),schema_version:true},{...record(),entries:[{action:'arbitrary',reason:'unverified'}]},
  {...record(),entries:[...record().entries,...record().entries]},{...record(),entries:[{action:'producesickle',reason:'privatecredential123'}]},
  {...record(),entries:[{action:'producesickle',reason:'unverified',cash:999}]}]){
  const view=macroExpansionAvailabilityView(value);assert.equal(view.available,false);assert.deepEqual(view.rows,[]);assert.equal(view.uncertain,true);
 }
});
test('legacy absence differs from failed new-domain validation',()=>{
 assert.deepEqual(macroExpansionAvailabilityView(undefined),{available:false,uncertain:false,rows:[]});
 assert.equal(macroExpansionAvailabilityView(undefined,true).uncertain,true);
 assert.deepEqual(macroExpansionAvailabilityView({...record(),entries:[]}).rows,[]);
});
