"""Real strategy lifecycle with a fake native boundary; no game/API calls."""
import asyncio
import copy
import ctypes
import hashlib
import importlib.util
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch,MagicMock
import uuid

import battle_host
import tactical_bridge as bridge_module

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'strategy'))
from battle_agent import BattleAgent,TacticalEvidence
from engine import StrategyEngine
from fixtures import binding
from tactical_fixtures import tactical_snapshot,tactical_policy,intent


class Reservations:
    def __init__(self):self.reserved=set()
    def reserve(self,ids):
        if self.reserved.intersection(ids):raise ValueError('Already reserved')
        self.reserved.update(ids)
    def release(self,ids):self.reserved.difference_update(ids)


class Executor:
    def __init__(self):self.commands=[];self.ledger=[];self.reply='queued';self.state='running';self.stop_calls=0
    def update_context(self,*args):self.context=copy.deepcopy(args)
    def submit(self,request):
        self.commands.append(copy.deepcopy(request))
        if self.reply=='no_dispatch_rejected':return dict(status=self.reply,accepted=False,started=False,completed=False)
        return dict(status=self.reply,accepted=True,command_id=request['command_id'],task_id=request['task_id'],seq=request['seq'],object_ids=[11],started=False)
    def status(self):return dict(state=self.state,ledger=copy.deepcopy(self.ledger),manifest={})
    def stop(self):self.stop_calls+=1;self.state='stopped';return self.status()


class TacticalHostBoundaries(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        host=self.host=battle_host.Host.__new__(battle_host.Host)
        host.output=self.root;host.binding=binding();host.engine=StrategyEngine(host.binding)
        host.agent=BattleAgent(host.engine,tactical_evidence=TacticalEvidence(str(uuid.uuid4()),host.binding.session_id,3,'game_bridge',(('attack',('main_attack',)),)),memory_path=self.root/'memory.json')
        raw=tactical_snapshot();raw['source']='game_bridge';host.last_snapshot=raw
        async def model(context):return tactical_policy(context)
        await host.agent.decide(raw,model)
        self.task=next(task for task in host.agent.goals.tasks if task.request.module=='attack')
        self.roster=Reservations()
        host.collector=types.SimpleNamespace(formations=self.roster,private_formations={'formation_main':dict(version=1,object_ids=[11,12],role='infantry')},private_regions={},visibility_proof_path=None,native={})
        host.phase='running';host.reason='observing';host.session=dict(pid=123,run_directory=str(self.root),session_id=host.binding.session_id,scenario={'participant_count':2})
        host.events=[];host.event=lambda kind,**fields:host.events.append(dict(kind=kind,**fields))
        host.tactical=bridge_module.TacticalBridge(host,dict(supported_purposes=(('attack',('main_attack',)),),grants=[]))
        self.bridge=host.tactical;self.executor=Executor();self.bridge.executor=self.executor
        self.verified=[]
        def verify(module,purpose,path,session,commander):
            record=json.loads(Path(path).read_text(encoding='utf-8'))
            if record.get('raw_evidence_complete') is not True:raise ValueError('raw_purpose_evidence_failed')
            self.verified.append((module,purpose,str(path)))
            return dict(module=module,purpose=purpose)
        self.verifier=types.SimpleNamespace(verify_purpose=verify)

    async def asyncTearDown(self):self.temp.cleanup()

    async def dispatch(self):
        await self.bridge.dispatch();return self.executor.commands[-1]

    def receipt(self,status='started',**changes):
        entry=self.bridge.sent[self.task.task_id]
        execution=dict(formation_versions=dict(entry['formation_versions']),issued_frame=1500,expires_frame=entry['expires_frame'],command_source='game_thread_bridge',interference='none',goal_observed=status=='completed',restoration_verified=status=='completed')
        result=dict(task_id=self.task.task_id,command_id=entry['command_id'],seq=entry['seq'],session_id=self.host.binding.session_id,commander_id=self.host.binding.commander_id,player_id=3,module=entry['module'],purpose=entry['purpose'],object_ids=[11],status=status,started=True,completed=status=='completed',goal_observed=status=='completed',restoration_verified=status=='completed',dispatch_attempted=True,no_dispatch_verified=False,execution=execution,unit_results=[])
        result.update(changes);return result

    def raw_report(self,receipt,oid=11,**changes):
        entry=self.bridge.sent[self.task.task_id];command=str(uuid.uuid5(uuid.UUID(entry['command_id']),str(oid)));task=str(uuid.uuid5(uuid.UUID(self.task.task_id),str(oid)))
        report=dict(session_id=self.host.binding.session_id,preflight=dict(pid=123,commander_id=self.host.binding.commander_id,player_id=3,selected={'object_id':oid}),request=dict(command_id=command,task_id=task,seq=1),native=dict(command_id=command,task_id=task,seq=1,issued_frame=entry['dispatch_frame'],returned_frame=entry['dispatch_frame']+15),raw_evidence_complete=True)
        report.update(changes);path=self.root/(str(oid)+'-raw.json');path.write_text(json.dumps(report),encoding='utf-8')
        receipt['unit_results'].append(dict(object_id=oid,report=str(path)));return path

    async def receive(self):
        with patch.object(bridge_module,'module',return_value=self.verifier):await self.bridge.receive()

    async def test_commit_precedes_submit_and_queued_is_never_started(self):
        original=self.executor.submit
        def submit(request):
            persisted=json.loads(self.bridge.journal.read_text(encoding='utf-8'))
            self.assertIn(request['task_id'],persisted);self.assertEqual(self.task.status,'dispatch_pending')
            self.assertIn('formation_main',self.roster.reserved)
            return original(request)
        self.executor.submit=submit;await self.dispatch()
        self.assertEqual(self.task.status,'dispatch_pending');self.assertIsNone(self.task.execution_start)
        self.assertEqual(self.host.agent.public_memory()['recent_execution_feedback'],[])

    async def test_queued_survives_reserved_snapshot_and_new_plan_without_duplicate_submit(self):
        request=await self.dispatch();original=(self.task.plan_id,self.task.request.formation_versions,self.task.expires_at_game_seconds)
        update=tactical_snapshot(2,116);update['source']='game_bridge';update['battlefield']['formations'][0]['available']=False;self.host.last_snapshot=update
        async def model(context):return tactical_policy(context,[],stance='expand',objective_region='north_expansion')
        await self.host.agent.decide(update,model);await self.bridge.dispatch()
        self.assertEqual(len(self.executor.commands),1);self.assertEqual(self.task.status,'dispatch_pending')
        self.assertEqual((self.task.plan_id,self.task.request.formation_versions,self.task.expires_at_game_seconds),original)
        self.assertNotEqual(self.host.agent.engine.current.plan_id,request['plan_id'])

    async def test_complete_requires_raw_reassessment_and_is_delivered_exactly_once(self):
        await self.dispatch();receipt=self.receipt('completed');self.raw_report(receipt);self.executor.ledger=[receipt]
        await self.receive();await self.receive();await self.bridge.dispatch()
        self.assertEqual(self.task.status,'completed');self.assertFalse(self.roster.reserved)
        self.assertEqual(len(self.verified),1);self.assertEqual(len(self.executor.commands),1)
        feedback=self.host.agent.public_memory()['recent_execution_feedback']
        self.assertEqual([item['status'] for item in feedback],['started','completed'])

    async def test_spoofed_or_absent_raw_never_completes(self):
        await self.dispatch();valid=self.receipt('completed');path=self.raw_report(valid)
        variants=[dict(unit_results=[]),dict(completed=False),dict(goal_observed=False),dict(restoration_verified=False),dict(command_id=str(uuid.uuid4())),dict(seq=999),dict(session_id=str(uuid.uuid4())),dict(commander_id=str(uuid.uuid4())),dict(player_id=2)]
        for changes in variants:
            self.executor.ledger=[dict(copy.deepcopy(valid),**changes)]
            with self.subTest(changes=changes),self.assertRaises((ValueError,RuntimeError)):await self.receive()
            self.assertNotEqual(self.task.status,'completed');self.assertIn('formation_main',self.roster.reserved)
        raw=json.loads(path.read_text());raw['raw_evidence_complete']=False;path.write_text(json.dumps(raw),encoding='utf-8');self.executor.ledger=[valid]
        with self.assertRaisesRegex(ValueError,'raw_purpose_evidence_failed'):await self.receive()
        self.assertNotEqual(self.task.status,'completed')

    async def test_changed_formation_version_or_expiry_cannot_start_or_release(self):
        await self.dispatch()
        for key,value in [('formation_versions',{'formation_main':2}),('expires_frame',1949)]:
            receipt=self.receipt();receipt['execution'][key]=value;self.executor.ledger=[receipt]
            with self.subTest(key=key),self.assertRaises(ValueError):await self.receive()
            self.assertEqual(self.task.status,'dispatch_pending');self.assertIn('formation_main',self.roster.reserved)

    async def test_completed_without_issued_never_completes(self):
        await self.dispatch();self.executor.ledger=[self.receipt('completed',started=False)]
        with self.assertRaisesRegex(ValueError,'never issued'):await self.receive()
        self.assertEqual(self.task.status,'dispatch_pending')

    async def test_explicit_preflight_rejection_releases_without_fake_started(self):
        self.executor.reply='no_dispatch_rejected';await self.dispatch()
        self.assertEqual(self.task.status,'cancelled');self.assertFalse(self.roster.reserved)
        self.assertEqual([item['status'] for item in self.host.agent.public_memory()['recent_execution_feedback']],['cancelled'])
        await self.bridge.dispatch();self.assertEqual(len(self.executor.commands),1)

    async def test_unknown_retains_reservation_and_prevents_any_new_dispatch(self):
        await self.dispatch();self.executor.ledger=[self.receipt('unknown',started=False)]
        with self.assertRaisesRegex(RuntimeError,'unknown'):await self.receive()
        await self.bridge.dispatch();self.assertEqual(len(self.executor.commands),1)
        self.assertEqual(self.task.status,'dispatch_pending');self.assertIn('formation_main',self.roster.reserved)

    async def test_missing_dispatch_attempted_is_not_proof_that_native_never_ran(self):
        await self.dispatch();receipt=self.receipt('failed',started=False);receipt.pop('dispatch_attempted');self.executor.ledger=[receipt]
        with self.assertRaises((RuntimeError,ValueError)):await self.receive()
        self.assertEqual(self.task.status,'dispatch_pending');self.assertIn('formation_main',self.roster.reserved)

    async def test_partial_or_duplicate_allocated_unit_results_cannot_complete(self):
        await self.dispatch();entry=self.bridge.sent[self.task.task_id];entry['object_ids']=[11,12]
        partial=self.receipt('completed',object_ids=[11,12]);self.raw_report(partial);self.executor.ledger=[partial]
        with self.assertRaises((RuntimeError,ValueError)):await self.receive()
        self.assertNotEqual(self.task.status,'completed');self.assertIn('formation_main',self.roster.reserved)
        duplicate=copy.deepcopy(partial);duplicate['unit_results']*=2;self.executor.ledger=[duplicate]
        with self.assertRaises((RuntimeError,ValueError)):await self.receive()
        self.assertNotEqual(self.task.status,'completed')

    async def test_raw_child_task_sequence_actor_session_and_path_are_rechecked(self):
        await self.dispatch();receipt=self.receipt('completed');path=self.raw_report(receipt)
        original=json.loads(path.read_text(encoding='utf-8'));entry=self.bridge.sent[self.task.task_id]
        changes=[('request','task_id',str(uuid.uuid4())),('native','task_id',str(uuid.uuid4())),('native','seq',2),('native','seq',True),('native','command_id',str(uuid.uuid4())),('preflight','pid',124)]
        with patch.object(bridge_module,'module',return_value=self.verifier):
            for section,key,value in changes:
                raw=copy.deepcopy(original);raw[section][key]=value;path.write_text(json.dumps(raw),encoding='utf-8')
                with self.subTest(section=section,key=key,value=value),self.assertRaises(ValueError):self.bridge.verify_completed(receipt,entry)
            raw=copy.deepcopy(original);raw['preflight']['selected']['object_id']=12;path.write_text(json.dumps(raw),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'actor mismatch'):self.bridge.verify_completed(receipt,entry)
            raw=copy.deepcopy(original);raw['session_id']=str(uuid.uuid4());path.write_text(json.dumps(raw),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'another match'):self.bridge.verify_completed(receipt,entry)
            with tempfile.TemporaryDirectory() as outside:
                other=Path(outside)/'outside.json';other.write_text(json.dumps(original),encoding='utf-8');receipt['unit_results'][0]['report']=str(other)
                with self.assertRaisesRegex(ValueError,'outside current match'):self.bridge.verify_completed(receipt,entry)
        self.assertEqual(self.task.status,'dispatch_pending')

    async def test_ack_cannot_allocate_foreign_units_and_unknown_remains_reserved(self):
        original=self.executor.submit
        def submit(request):return dict(original(request),object_ids=[999])
        self.executor.submit=submit
        with self.assertRaisesRegex(ValueError,'allocation'):await self.bridge.dispatch()
        self.assertEqual(self.task.status,'dispatch_pending');self.assertIn('formation_main',self.roster.reserved)
        self.assertFalse(self.bridge.sent[self.task.task_id]['terminal'])

    async def test_receipt_cannot_change_acknowledged_allocation(self):
        await self.dispatch();self.executor.ledger=[self.receipt(object_ids=[12])]
        with self.assertRaisesRegex(ValueError,'allocation changed'):await self.receive()
        self.assertEqual(self.task.status,'dispatch_pending');self.assertIn('formation_main',self.roster.reserved)

    async def test_calibration_or_other_purpose_receipt_never_becomes_a_real_task_result(self):
        await self.dispatch()
        for changes in [{'module':'calibration','purpose':'visible_attack_probe'},{'module':'attack','purpose':'harass_economy'},{'module':'raid','purpose':'main_attack'}]:
            self.executor.ledger=[self.receipt('completed',**changes)]
            with self.subTest(changes=changes),self.assertRaises(ValueError):await self.receive()
            self.assertEqual(self.task.status,'dispatch_pending');self.assertIn('formation_main',self.roster.reserved)
            self.assertFalse(self.host.agent.public_memory()['recent_execution_feedback'])

    async def test_started_failure_without_restoration_quarantines_exact_formation(self):
        await self.dispatch();receipt=self.receipt('failed');receipt['execution']['interference']='unknown';self.executor.ledger=[receipt]
        with self.assertRaisesRegex(RuntimeError,'restoration unverified'):await self.receive()
        self.assertEqual(self.task.status,'failed');self.assertEqual(self.host.agent.goals.quarantined_formations,{'formation_main':1})
        self.assertIn('formation_main',self.roster.reserved);self.assertTrue(self.bridge.sent[self.task.task_id]['terminal'])
        persisted=json.loads(self.bridge.journal.read_text(encoding='utf-8'))
        self.assertTrue(persisted[self.task.task_id]['terminal'])
        self.assertEqual([item['status'] for item in self.host.agent.public_memory()['recent_execution_feedback']],['started','failed'])

    async def disposal_fixture(self):
        """Synthetic inert/absent proof, verified by the real read-only verifier."""
        await self.dispatch();entry=self.bridge.sent[self.task.task_id]
        receipt=self.receipt('failed',restoration_verified=True);receipt['execution']['restoration_verified']=True
        verifier=bridge_module.module(bridge_module.ROOT.parent/'tactical/readonly_disposal.py','integration_actual_disposal')
        command=str(uuid.uuid5(uuid.UUID(entry['command_id']),'11'));task=str(uuid.uuid5(uuid.UUID(self.task.task_id),'11'))
        pre=dict(pid=123,commander_id=self.host.binding.commander_id,session_id=self.host.binding.session_id,player_id=3,window_thread=16052,owner='0x2000',ai='0x3000',logic='0x1000',selected=dict(object_id=11,address='0x4000',type_hash='0x19ab11af'))
        request=dict(command_id=command,task_id=task,seq=1,token=99)
        native=dict(session_id=self.host.binding.session_id,commander_id=self.host.binding.commander_id,command_id=command,task_id=task,seq=1,callback_thread=16052,phase=4,error=32,restore_mask=2047,active=0,overflow=0,issued_frame=entry['dispatch_frame'],returned_frame=0,detach_calls=1,return_calls=0,return_verified=0)
        events=[dict(kind=kind,tag=1,arg=0x3104,owner=0x2000,thread=16052,caller=0x838877,frame=entry['dispatch_frame']) for kind in (18,19)]
        path=self.raw_report(receipt,preflight=pre,request=request,native=native,events=events,native_binary_sha256=verifier.DLL,executable_sha256=verifier.EXE)
        state=dict(timer=0,active=0,phase=4,error=32,restore_mask=2047,token=99,seq=1,shared_pointer='0x5000',module_base='0x6000',pid=123,thread=16052,session_id=self.host.binding.session_id,commander_id=self.host.binding.commander_id,command_id=command,task_id=task,object_id=11,type_hash='0x19ab11af',owner='0x2000',entries=[dict(value,actual=value['expected']) for value in verifier.trusted_entries()])
        proof=path.with_suffix('.disposal.json')
        evidence=dict(source_report=str(path.resolve()),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reader_sha256=verifier.sha(verifier.__file__),session_id=self.host.binding.session_id,pid=123,layout=verifier.LAYOUT,completed=False,goal_observed=False,return_verified=False,inert_snapshots=[copy.deepcopy(state),copy.deepcopy(state)],scans=[dict(complete=True,logic='0x1000',frame=frame,end_frame=frame,ids=[1,2,3],count=3) for frame in (1502,1504)])
        proof.write_text(json.dumps(evidence),encoding='utf-8');release=verifier.verify_path(proof,path)
        self.assertTrue(release['disposed_verified']);self.assertTrue(release['restoration_verified']);self.assertFalse(release['return_verified']);self.assertFalse(release['completion_claim'])
        receipt['unit_results'][0]['control_release']=release
        return receipt,path,proof

    async def test_valid_disposal_is_independently_verified_then_failed_and_released(self):
        receipt,_,_=await self.disposal_fixture();self.executor.ledger=[receipt]
        await self.bridge.receive();await self.bridge.receive()
        self.assertEqual(self.task.status,'failed');self.assertFalse(self.roster.reserved)
        self.assertTrue(self.bridge.sent[self.task.task_id]['terminal']);self.assertFalse(self.host.agent.goals.quarantined_formations)
        feedback=self.host.agent.public_memory()['recent_execution_feedback']
        self.assertEqual([value['status'] for value in feedback],['started','failed'])
        self.assertFalse(feedback[-1]['execution']['goal_observed']);self.assertEqual(self.bridge.counters['attack']['completed'],0)

    async def test_disposal_raw_foreign_actor_match_old_task_and_issue_window_rejected(self):
        receipt,path,_=await self.disposal_fixture();entry=self.bridge.sent[self.task.task_id];original=json.loads(path.read_text(encoding='utf-8'))
        cases=[('preflight','pid',124),('preflight','commander_id',str(uuid.uuid4())),('request','task_id',str(uuid.uuid4())),('native','task_id',str(uuid.uuid4())),('native','command_id',str(uuid.uuid4())),('native','seq',True),('native','issued_frame',entry['dispatch_frame']-1),('native','issued_frame',entry['expires_frame'])]
        for section,key,value in cases:
            raw=copy.deepcopy(original);raw[section][key]=value;path.write_text(json.dumps(raw),encoding='utf-8')
            with self.subTest(section=section,key=key),self.assertRaises(ValueError):self.bridge.verify_disposals(receipt,entry)
        raw=copy.deepcopy(original);raw['session_id']=str(uuid.uuid4());path.write_text(json.dumps(raw),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'another actor or match'):self.bridge.verify_disposals(receipt,entry)
        raw=copy.deepcopy(original);raw['preflight']['selected']['object_id']=12;path.write_text(json.dumps(raw),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'another actor or match'):self.bridge.verify_disposals(receipt,entry)
        path.write_text(json.dumps(original),encoding='utf-8');foreign=copy.deepcopy(receipt);foreign['unit_results'][0]['object_id']=12
        with self.assertRaisesRegex(ValueError,'allocation mismatch'):self.bridge.verify_disposals(foreign,entry)
        self.assertEqual(self.task.status,'dispatch_pending');self.assertIn('formation_main',self.roster.reserved)

    async def test_disposal_proof_sha_source_sha_and_readonly_semantics_are_recomputed(self):
        receipt,path,proof=await self.disposal_fixture();entry=self.bridge.sent[self.task.task_id];original=proof.read_text(encoding='utf-8')
        proof.write_text(original+'\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'evidence changed'):self.bridge.verify_disposals(receipt,entry)
        for changes in [dict(source_sha256='0'*64),dict(completed=True),dict(return_verified=True),dict(goal_observed=True),dict(reader_sha256='0'*64)]:
            evidence=json.loads(original);evidence.update(changes);proof.write_text(json.dumps(evidence),encoding='utf-8')
            receipt['unit_results'][0]['control_release']['evidence_sha256']=hashlib.sha256(proof.read_bytes()).hexdigest()
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.bridge.verify_disposals(receipt,entry)
        self.assertIn('formation_main',self.roster.reserved)

    async def test_disposal_report_or_sidecar_outside_current_run_rejected(self):
        receipt,path,proof=await self.disposal_fixture();entry=self.bridge.sent[self.task.task_id]
        with tempfile.TemporaryDirectory() as folder:
            for key,source in [('report',path),('evidence_path',proof)]:
                outside=Path(folder)/source.name;outside.write_bytes(source.read_bytes());changed=copy.deepcopy(receipt)
                if key=='report':changed['unit_results'][0][key]=str(outside)
                else:changed['unit_results'][0]['control_release'][key]=str(outside)
                with self.subTest(key=key),self.assertRaisesRegex(ValueError,'outside current match'):self.bridge.verify_disposals(changed,entry)

    async def test_disposal_cannot_claim_completed_goal_or_native_pool_return(self):
        receipt,_,_=await self.disposal_fixture();entry=self.bridge.sent[self.task.task_id]
        for section,key,value in [('top','completed',True),('top','goal_observed',True),('top','status','completed'),('execution','goal_observed',True),('release','return_verified',True),('release','disposed_verified',False)]:
            changed=copy.deepcopy(receipt)
            if section=='top':changed[key]=value
            elif section=='release':changed['unit_results'][0]['control_release'][key]=value
            else:changed['execution'][key]=value
            with self.subTest(section=section,key=key),self.assertRaises(ValueError):self.bridge.verify_disposals(changed,entry)
        self.assertEqual(self.task.status,'dispatch_pending');self.assertEqual(self.bridge.counters['attack']['completed'],0)

    async def test_native_actor_loss_cannot_hide_disposal_by_omitting_labels_or_reports(self):
        receipt,_,_=await self.disposal_fixture();entry=self.bridge.sent[self.task.task_id]
        variants=[]
        changed=copy.deepcopy(receipt);changed['unit_results']=[];variants.append(changed)
        changed=copy.deepcopy(receipt);changed['unit_results'][0].pop('control_release');variants.append(changed)
        changed=copy.deepcopy(receipt);release=changed['unit_results'][0]['control_release'];release.update(disposed_verified=False,semantics='native_pool_return',return_verified=True);release.pop('evidence_path');release.pop('evidence_sha256');variants.append(changed)
        changed=copy.deepcopy(receipt);release=changed['unit_results'][0]['control_release'];release.pop('disposed_verified');release.pop('semantics');variants.append(changed)
        for index,changed in enumerate(variants):
            with self.subTest(index=index),self.assertRaises((ValueError,KeyError)):self.bridge.verify_disposals(changed,entry)
        self.assertEqual(self.task.status,'dispatch_pending');self.assertIn('formation_main',self.roster.reserved)

    async def test_invalid_disposal_sidecar_never_records_failed_as_restored_or_releases(self):
        receipt,_,proof=await self.disposal_fixture();proof.write_text(proof.read_text(encoding='utf-8')+'\n',encoding='utf-8');self.executor.ledger=[receipt]
        with self.assertRaisesRegex(ValueError,'evidence changed'):await self.bridge.receive()
        self.assertEqual(self.task.status,'active');self.assertFalse(self.bridge.sent[self.task.task_id]['terminal'])
        self.assertIn('formation_main',self.roster.reserved)
        self.assertEqual([item['status'] for item in self.host.agent.public_memory()['recent_execution_feedback']],['started'])

    async def test_raw_native_execution_window_cannot_precede_dispatch_or_exceed_expiry(self):
        await self.dispatch();receipt=self.receipt('completed');path=self.raw_report(receipt)
        original=json.loads(path.read_text(encoding='utf-8'));entry=self.bridge.sent[self.task.task_id]
        changes=[dict(issued_frame=entry['dispatch_frame']-1),dict(returned_frame=entry['expires_frame']+1),dict(returned_frame=entry['dispatch_frame']-1),dict(issued_frame=True),dict(returned_frame=1500.5)]
        with patch.object(bridge_module,'module',return_value=self.verifier):
            for change in changes:
                raw=copy.deepcopy(original);raw['native'].update(change);path.write_text(json.dumps(raw),encoding='utf-8')
                with self.subTest(change=change),self.assertRaisesRegex(ValueError,'frozen task window'):self.bridge.verify_completed(receipt,entry)
            raw=copy.deepcopy(original);raw['native'].update(issued_frame=1501,returned_frame=1515);path.write_text(json.dumps(raw),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'differs from native trace'):self.bridge.verify_completed(receipt,entry)
        self.assertEqual(self.task.status,'dispatch_pending');self.assertIn('formation_main',self.roster.reserved)

    async def test_unrestored_failure_faults_full_host_before_any_followup_dispatch(self):
        await self.dispatch();receipt=self.receipt('failed');receipt['execution']['interference']='unknown';self.executor.ledger=[receipt]
        host=self.host;host.pending=None;host.executor_ready=False;host.executor=None;host.observer=None;host.observer_output=None
        host.started=time.monotonic();host.args=types.SimpleNamespace(max_wall_seconds=1,interval=.01,execute=True);host.stop_requested=lambda:False
        snapshot=tactical_snapshot(2,101);snapshot['source']='game_bridge';host.collector.collect=lambda:snapshot;host.collector.native={}
        host.publish=lambda:None;host.counters={}
        async def no_native():return None
        host.connect_executor=no_native;host.receive_receipts=no_native;host.dispatch=no_native;self.bridge.connect=no_native
        with patch.object(battle_host,'player_lease',return_value=nullcontext()):result=await host.run()
        self.assertEqual(result['state'],'fault');self.assertEqual(len(self.executor.commands),1);self.assertEqual(self.executor.stop_calls,1)
        self.assertTrue(host.engine.stopped);self.assertIn('formation_main',self.roster.reserved)
        self.assertEqual(host.agent.goals.quarantined_formations,{'formation_main':1})
        self.assertTrue(any(event['kind']=='host_fault' for event in host.events))

    async def combined(self):
        host=self.host;host.engine=StrategyEngine(host.binding)
        host.agent=BattleAgent(host.engine,tactical_evidence=TacticalEvidence(str(uuid.uuid4()),host.binding.session_id,3,'game_bridge',(('combined_arms',('coordinate_force',)),)))
        async def model(context):return tactical_policy(context,[intent('combined_arms','coordinate_force',target_contact_id=None,required_roles=['infantry','anti_air'])])
        await host.agent.decide(host.last_snapshot,model)
        self.task=next(task for task in host.agent.goals.tasks if task.request.module=='combined_arms')
        host.tactical=bridge_module.TacticalBridge(host,dict(supported_purposes=(('combined_arms',('coordinate_force',)),),grants=[]));self.bridge=host.tactical;self.bridge.executor=self.executor
        original=self.executor.submit
        self.executor.submit=lambda request:dict(original(request),object_ids=[11,12])
        await self.dispatch()
        receipt=self.receipt('completed',object_ids=[11,12]);entry=self.bridge.sent[self.task.task_id]
        command=str(uuid.uuid5(uuid.UUID(entry['command_id']),'formation'));task=str(uuid.uuid5(uuid.UUID(self.task.task_id),'formation'))
        path=self.root/'formation-raw.json';raw=dict(session_id=host.binding.session_id,preflight=dict(pid=123,commander_id=host.binding.commander_id,player_id=3),request=dict(command_id=command,task_id=task,seq=3,front_id=11,support_id=12),native=dict(command_id=command,task_id=task,seq=3,issued_frame=entry['dispatch_frame'],returned_frame=entry['dispatch_frame']+15),units=[{'id':11},{'id':12}],raw_evidence_complete=True)
        path.write_text(json.dumps(raw),encoding='utf-8');receipt['unit_results']=[{'report':str(path)}]
        return receipt,path,raw

    async def test_combined_completion_requires_exact_pair_and_formation_child_binding(self):
        receipt,path,original=await self.combined();self.executor.ledger=[receipt]
        with patch.object(bridge_module,'module',return_value=self.verifier):
            for change in [{'units':[{'id':11}]},{'units':[{'id':11},{'id':11}]},{'units':[{'id':12},{'id':11}]}]:
                path.write_text(json.dumps(dict(copy.deepcopy(original),**change)),encoding='utf-8')
                with self.subTest(change=change),self.assertRaises(ValueError):self.bridge.verify_completed(receipt,self.bridge.sent[self.task.task_id])
        path.write_text(json.dumps(original),encoding='utf-8');await self.receive()
        self.assertEqual(self.task.status,'completed');self.assertFalse(self.roster.reserved)
        self.assertEqual(self.verified[0][:2],('combined_arms','coordinate_force'))

    async def test_paused_or_stale_private_formation_does_not_reach_executor(self):
        self.host.last_snapshot['paused']=True;await self.bridge.dispatch();self.host.last_snapshot['paused']=False
        self.host.collector.private_formations['formation_main']['version']=2;await self.bridge.dispatch()
        self.assertEqual(self.executor.commands,[]);self.assertFalse(self.roster.reserved)

    async def test_result_branch_drains_completed_tactical_memory_before_agent_stop(self):
        await self.dispatch();receipt=self.receipt('completed');self.raw_report(receipt);self.executor.ledger=[receipt]
        host=self.host;host.pending=None;host.executor_ready=False;host.executor=None;host.observer=None;host.observer_output=None
        host.started=time.monotonic();host.args=types.SimpleNamespace(max_wall_seconds=1,interval=.01,execute=True);host.stop_requested=lambda:False
        snapshot=tactical_snapshot(2,101);snapshot['source']='game_bridge';host.collector.collect=lambda:snapshot
        host.collector.native={'result_records':[{'victory_frame':1515,'defeat_frame':0}]};host.publish=lambda:None
        host.counters={};stop_observations=[];original=host.agent.stop
        def stop():
            persisted=json.loads((self.root/'memory.json').read_text(encoding='utf-8'))
            stop_observations.append([item['status'] for item in persisted['recent_execution_feedback']]);original()
        host.agent.stop=stop
        with patch.object(battle_host,'player_lease',return_value=nullcontext()),patch.object(bridge_module,'module',return_value=self.verifier):result=await host.run()
        self.assertEqual(result['state'],'result_candidate');self.assertEqual(stop_observations,[['started','completed']])
        self.assertEqual(self.task.status,'completed');self.assertTrue(host.engine.stopped);self.assertEqual(self.executor.stop_calls,1)


class PurposeManifest(unittest.TestCase):
    def test_each_exact_purpose_is_independently_verified_and_duplicates_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'manifest.json';calls=[]
            manifest=dict(schema_version=1,sources=[dict(module='raid',purpose='recon',report='not-real.json')]);path.write_text(json.dumps(manifest))
            def verify(module,purpose,*args):
                calls.append((module,purpose));raise ValueError('unsupported_purpose_evidence')
            with patch.object(bridge_module,'module',return_value=types.SimpleNamespace(verify_purpose=verify)),self.assertRaisesRegex(ValueError,'unsupported_purpose_evidence'):bridge_module.verify_manifest(path,{},str(uuid.uuid4()))
            self.assertEqual(calls,[('raid','recon')])
            manifest['sources']*=2;path.write_text(json.dumps(manifest))
            with patch.object(bridge_module,'module',return_value=types.SimpleNamespace(verify_purpose=lambda *args:{})),self.assertRaisesRegex(ValueError,'Duplicate tactical purpose'):bridge_module.verify_manifest(path,{},str(uuid.uuid4()))


class VerifiedFormationExecutorRouting(unittest.TestCase):
    """Actual client and frozen raw evidence; fake subprocess and kernel only."""
    @classmethod
    def setUpClass(cls):
        cls.tactical=Path(__file__).resolve().parents[1]/'tactical'
        spec=importlib.util.spec_from_file_location('independent_route_client',cls.tactical/'client.py');cls.client=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.client)
        cls.raw=json.loads((cls.tactical.parent/'acceptance/runs/20261024-234355-commander/formation-stop-v2-03.json').read_text(encoding='utf-8'))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.run=Path(self.temp.name)
        self.executor=self.client.TacticalExecutor('unused-session','unused-natural',self.raw['preflight']['commander_id'])
        e=self.executor;e.run=self.run;e.session={'session_id':self.raw['session_id'],'pid':26312};e.native_seq=0;e._binding=lambda:None
        e.commander_id=self.raw['preflight']['commander_id'];e.formations={};e.logic=0x1000
        schema=self.client.trusted_executor('formation-stop-v2')
        e.capability_grants={('combined_arms','coordinate_force'):dict(executor_directory='formation-stop-v2',native_binary_sha256=hashlib.sha256((self.tactical/'formation-stop-v2/bin'/schema['dll']).read_bytes()).hexdigest(),native_host_sha256=hashlib.sha256((self.tactical/'formation-stop-v2/bin/tactical_host.exe').read_bytes()).hexdigest())}
        self.command=str(uuid.uuid4());self.record=dict(kind='formation',module='combined_arms',purpose='coordinate_force',task_id=str(uuid.uuid4()),object_ids=[800,809],executor_directory='formation-stop-v2',dx=-40,dy=-40,rear_spacing=56.56854249,formation_versions={},unit_results=[])

    def fake_child(self,args,**kwargs):
        self.called=args;report=copy.deepcopy(self.raw)
        for key in ('command_id','task_id','seq'):
            value=args[args.index('--'+key.replace('_','-'))+1];value=int(value) if key=='seq' else value
            report['request'][key]=report['native'][key]=value
        report['native']['restore_mask']=getattr(self,'reported_mask',127)
        Path(args[args.index('--output')+1]).write_text(json.dumps(report),encoding='utf-8')
        return types.SimpleNamespace(poll=lambda:0,returncode=0)

    def test_verified_route_uses_new_wrapper_and_restore_127(self):
        with patch.object(self.client.subprocess,'Popen',side_effect=self.fake_child):self.executor._execute_formation(self.command,self.record)
        self.assertEqual(Path(self.called[1]),self.tactical/'formation-stop-v2/lease.py')
        self.assertTrue(self.record['completed']);self.assertTrue(self.record['restoration_verified'])
        self.assertEqual(self.record['unit_results'][0]['expected_restore_mask'],127)
        self.assertTrue(self.record['unit_results'][0]['batch_restoration']['restoration_verified'])

    def test_old_restore_mask_cannot_complete_new_executor(self):
        self.reported_mask=31
        with patch.object(self.client.subprocess,'Popen',side_effect=self.fake_child),self.assertRaisesRegex(ValueError,'formation_not_verified'):self.executor._execute_formation(self.command,self.record)
        self.assertFalse(self.record.get('completed',False));self.assertFalse(self.record['unit_results'][0]['batch_restoration']['restoration_verified'])

    def test_directory_and_revision_drift_reject_before_process_creation(self):
        with patch.object(self.client.subprocess,'Popen',side_effect=AssertionError('must not launch')):
            for mutation,reason in [(dict(executor_directory='formation'),'executor_grant_binding_changed'),(dict(executor_directory='../formation-stop-v2'),'executor_not_in_trusted_scope_table')]:
                r=dict(self.record,**mutation)
                with self.assertRaisesRegex(ValueError,reason):self.executor._execute_formation(self.command,r)
            self.executor.capability_grants[('combined_arms','coordinate_force')]['native_host_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'executor_revision_changed'):self.executor._execute_formation(self.command,self.record)

    def test_stop_maps_exact_new_layout_and_prefix_not_receipt_supplied_schema(self):
        schema,runtime=self.client.runtime_backend('formation-stop-v2');shared=runtime.Tactical();shared.token=912;shared.pid=26312
        path=self.run/'active.json';path.write_text(json.dumps(dict(request=dict(token=912,front_id=800,support_id=809))))
        self.executor.active=self.command;self.executor.ledger[self.command]=dict(active_report=str(path),executor_directory='formation-stop-v2',stop_schema=dict(mapping_prefix='untrusted'))
        kernel=types.SimpleNamespace(OpenFileMappingW=MagicMock(return_value=5),MapViewOfFile=MagicMock(return_value=ctypes.addressof(shared)),UnmapViewOfFile=MagicMock(),CloseHandle=MagicMock())
        with patch.object(self.client.backend,'k',kernel):self.executor._request_native_stop(path)
        kernel.OpenFileMappingW.assert_called_once_with(0xf001f,False,'Local\\RA3TacticalFormationStop2_26312_912')
        self.assertEqual(kernel.MapViewOfFile.call_args.args[-1],ctypes.sizeof(runtime.Tactical));self.assertEqual(shared.stop_requested,1)
        kernel.UnmapViewOfFile.assert_called_once();kernel.CloseHandle.assert_called_once()

    def test_stop_ignores_stale_report_and_wrong_token(self):
        schema,runtime=self.client.runtime_backend('formation-stop-v2');shared=runtime.Tactical();shared.token=999;shared.pid=26312
        path=self.run/'stale.json';path.write_text(json.dumps(dict(request=dict(token=912,front_id=800,support_id=809))))
        self.executor.active=self.command;self.executor.ledger[self.command]=dict(active_report=str(self.run/'different.json'),executor_directory='formation-stop-v2')
        kernel=types.SimpleNamespace(OpenFileMappingW=MagicMock(return_value=5),MapViewOfFile=MagicMock(return_value=ctypes.addressof(shared)),UnmapViewOfFile=MagicMock(),CloseHandle=MagicMock())
        with patch.object(self.client.backend,'k',kernel):
            self.executor._request_native_stop(path);kernel.OpenFileMappingW.assert_not_called()
            self.executor.ledger[self.command]['active_report']=str(path);self.executor._request_native_stop(path)
        self.assertEqual(shared.stop_requested,0);kernel.CloseHandle.assert_called_once()


if __name__=='__main__':unittest.main(verbosity=2)
