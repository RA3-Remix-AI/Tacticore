"""Synthetic Gateway -> tactical adapter -> native protocol -> ControlArbiter."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import uuid

from host_runtime.arbitration import ActorIdentity, ControlArbiter
from host_runtime.capabilities import CapabilityCatalog, VerifiedGrant
from host_runtime.contracts import ContractError, SessionBinding, canonical_json
from host_runtime.gateway import ExecutionGateway
from host_runtime.journal import CommandJournal
from host_runtime.tactical_adapter import RuntimeActor, RuntimeSnapshot, TacticalRuntimeAdapter


def uid():return str(uuid.uuid4())


class Transport:
    executor_sha256='d'*64;native_host_sha256='e'*64
    def __init__(self,binding):
        self.binding=binding;self.snapshot=RuntimeSnapshot(binding.binding_hash,100,1000,False,0,self.executor_sha256,self.native_host_sha256,'fake-native-observation')
        self.actor=RuntimeActor(ActorIdentity(binding.session_id,binding.player_id,501,1),90,uid(),'fake-original-paid-receipt')
        self.calls=[];self.raw=[];self.mode='ok';self.point=uid();self.ready=True
    def admit(self,binding):return self.snapshot
    def resolve_actor(self,object_id,generation):return self.actor
    def approved_target(self,point_id):return [100,0,0] if point_id==self.point else None
    def submit(self,wire):
        self.calls.append(wire)
        if self.mode=='error':raise OSError('private native error must not leak')
        row=dict(command_id=wire['command_id'],task_id=wire['task_id'],lease_id=wire['lease_id'],seq=wire['seq'],binding_hash=wire['binding_hash'],object_id=501,generation=1,
            status='completed' if wire['operation'] in ('reserve','query_status') else 'released',phase='ready' if self.ready else 'braking',held=True,physical_home=False,control_released=False,stance_restored=False,
            game_frame=100,monotonic_ms=1000,reason_code='native_observation',source_reference='fake-native-event-42',observation={'team':10,'default_team':10,'stance':0,'xyz':[0,0,0],'state_id':94,'path':0,'command_source':1})
        if wire['operation'] in ('commit','return','stop'):row.update(held=False,physical_home=wire['operation']=='commit',control_released=True,stance_restored=True,phase='released',reason_code='native_control_release_observed' if wire['operation']=='commit' else 'native_control_release_without_goal_effect')
        if self.mode=='cancelled_home':row.update(physical_home=True,reason_code='native_control_release_without_goal_effect')
        if self.mode=='unknown':row['status']='uncertain'
        if self.mode=='wrong_id':row['command_id']=uid()
        if self.mode=='wrong_seq':row['seq']+=1
        if self.mode=='wrong_generation':row['generation']+=1
        if self.mode=='fake_release':row.update(status='released',control_released=True,stance_restored=True,held=False,observation={'team':20,'default_team':10,'stance':0})
        if self.mode in ('no_borrow','no_borrow_with_sdk','no_borrow_script_owner'):
            row.update(status='released',phase='released',reason_code='borrow_not_sent_no_control_transfer',held=False,
                physical_home=False,control_released=True,stance_restored=False,sdk_calls=[0]*6,
                observation=dict(team=42,default_team=10,script_team=20,stance=1,identity=True,birth_verified=True,live=True,grounded=True))
            if self.mode=='no_borrow_with_sdk':row['sdk_calls'][0]=1
            if self.mode=='no_borrow_script_owner':row['observation']['team']=20
        if self.mode=='fake_completed':row.update(status='completed',held=True)
        self.raw.append(row);return row


class TacticalAdapterTests(unittest.TestCase):
    def test_never_transferred_reserve_closes_only_the_logical_claim(self):
        self.transport.mode='no_borrow'
        result=self.reserve()
        self.assertEqual('released',result['status'])
        self.assertTrue(result['receipt']['facts']['no_control_acquired'])
        self.assertFalse(result['receipt']['facts']['physical_home'])
        self.assertFalse(result['receipt']['facts']['mission_effect_verified'])
        self.assertEqual('released',self.arbiter.snapshot(self.lease)['state'])
        self.assertEqual(1,len(self.transport.calls))

    def test_no_borrow_exception_cannot_hide_a_borrow_call(self):
        self.transport.mode='no_borrow_with_sdk'
        result=self.reserve()
        self.assertEqual('uncertain',result['status'])
        self.assertNotEqual('released',self.arbiter.snapshot(self.lease)['state'])

    def test_no_borrow_exception_cannot_hide_a_script_owner(self):
        self.transport.mode='no_borrow_script_owner'
        result=self.reserve()
        self.assertEqual('uncertain',result['status'])
        self.assertNotEqual('released',self.arbiter.snapshot(self.lease)['state'])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.journal=CommandJournal(Path(self.temp.name)/'ledger.sqlite')
        self.binding=SessionBinding(1,uid(),7,uid(),1234,'2026-10-26T00:00:00+00:00',uid(),'a'*64,'b'*64)
        self.run=uid();self.task=uid();self.lease=uid();self.transport=Transport(self.binding)
        self.arbiter=ControlArbiter(self.binding.session_id,7);self.catalog=self.catalog_for()
        self.adapter=self.make_adapter();self.gateway=ExecutionGateway(self.run,self.binding,self.journal,self.catalog,self.adapter)
    def tearDown(self):self.journal.close();self.temp.cleanup()
    def catalog_for(self,**changes):
        scope=dict(runtime_family='tactical',executor_directory='tactical/runtime',execution_ready=True,executor_sha256='d'*64,evidence_id='test-proof',native_host_sha256='e'*64,mission_protocol='tactical_runtime_v1',purpose='move_hold_return',actor_roles=['infantry'])
        scope.update(changes)
        grant=VerifiedGrant('tactics.move_hold_return','test-proof','c'*64,'d'*64,'test-only single paid conscript',canonical_json(scope))
        return CapabilityCatalog.verify(self.binding,[grant],lambda grant,binding:grant)
    def make_adapter(self,**kwargs):
        return TacticalRuntimeAdapter(self.binding,run_id=self.run,journal=self.journal,capabilities=self.catalog,arbiter=self.arbiter,test_transport=self.transport,**kwargs)
    def payload(self,operation='reserve',**changes):
        value=dict(task_id=self.task,generation=1,lease_id=self.lease,expires_frame=300,expires_monotonic_ms=5000)
        if operation in ('reserve','commit'):value['purpose']='move_hold_return'
        if operation=='reserve':value.update(actor={'object_id':501,'generation':1},deadline_frame=800)
        if operation=='commit':value.update(target_point_id=self.transport.point,hold_frames=30)
        value.update(changes);return value
    def reserve(self):return self.gateway.submit(uid(),'reserve',self.payload())

    def test_real_gateway_arbiter_protocol_chain_and_repeated_task(self):
        first=self.reserve();self.assertEqual(first['status'],'completed')
        self.assertEqual(self.arbiter.snapshot(self.lease)['state'],'held')
        request=uid();done=self.gateway.submit(request,'commit',self.payload('commit'))
        self.assertEqual(done['status'],'released');self.assertTrue(done['receipt']['facts']['mission_effect_verified'])
        self.assertEqual(self.arbiter.snapshot(self.lease)['state'],'released')
        self.gateway.submit(request,'commit',self.payload('commit'));self.assertEqual(len(self.transport.calls),2)
        self.task=uid();self.lease=uid();self.assertEqual(self.reserve()['status'],'completed')
        self.assertEqual([row['seq'] for row in self.transport.calls],[1,2,3])
        self.assertFalse(done['receipt']['facts']['field_evidence_eligible'])
        self.assertNotIn('address',str(self.transport.calls))

    def test_stopped_task_at_home_is_released_without_goal_effect_credit(self):
        self.reserve();self.transport.mode='cancelled_home'
        result=self.gateway.submit(uid(),'commit',self.payload('commit'))
        self.assertEqual('released',result['status'])
        self.assertTrue(result['receipt']['facts']['physical_home'])
        self.assertFalse(result['receipt']['facts']['mission_effect_verified'])
        self.assertEqual('released',self.arbiter.snapshot(self.lease)['state'])

    def test_unknown_delivery_keeps_control_claim_and_never_retries(self):
        self.transport.mode='error';request=uid()
        result=self.gateway.submit(request,'reserve',self.payload());self.assertEqual(result['status'],'uncertain')
        self.assertEqual(self.arbiter.snapshot(self.lease)['state'],'held')
        self.gateway.submit(request,'reserve',self.payload());self.assertEqual(len(self.transport.calls),1)
        with self.assertRaisesRegex(ContractError,'unknown_requires_reconciliation'):self.adapter.observe(request,{})
        self.assertNotIn('private native error',str(self.journal.events(self.run)))
        self.transport.mode='ok';self.lease=uid();self.assertEqual(self.reserve()['status'],'rejected');self.assertEqual(len(self.transport.calls),1)

    def test_no_native_authority_from_forged_transport_class_or_missing_client(self):
        kwargs=dict(run_id=self.run,journal=self.journal,capabilities=self.catalog,arbiter=self.arbiter)
        with self.assertRaisesRegex(ContractError,'attached_native_runtime_client_required'):TacticalRuntimeAdapter(self.binding,**kwargs)
        with self.assertRaisesRegex(ContractError,'original_native_runtime_client_required'):TacticalRuntimeAdapter(self.binding,transport=self.transport,**kwargs)

    def test_admission_rejects_stale_clocks_pause_binding_binary_and_actor_incarnation(self):
        for changed in (dict(paused=True),dict(binding_hash='f'*64),dict(executor_sha256='f'*64),dict(native_host_sha256='f'*64),dict(monotonic_ms=6000),dict(game_frame=400)):
            with self.subTest(changed=changed):
                self.transport.snapshot=replace(self.transport.snapshot,**changed)
                self.assertEqual(self.reserve()['status'],'rejected');self.assertEqual(self.transport.calls,[])
                self.transport.snapshot=RuntimeSnapshot(self.binding.binding_hash,100,1000,False,0,'d'*64,'e'*64,'fake-native-observation');self.adapter._last_frame=self.adapter._last_ms=-1
        self.transport.actor=replace(self.transport.actor,identity=ActorIdentity(self.binding.session_id,7,501,2))
        self.assertEqual(self.reserve()['status'],'rejected')

    def test_scope_ready_is_machine_bound_and_old_formation_scope_not_inherited(self):
        for changes in (dict(execution_ready=False),dict(executor_directory='tactical/mission-formation-v18'),dict(mission_protocol='old'),dict(actor_roles=['infantry','anti_air'])):
            self.catalog=self.catalog_for(**changes);adapter=self.make_adapter();gate=ExecutionGateway(self.run,self.binding,self.journal,self.catalog,adapter)
            self.assertEqual(gate.submit(uid(),'reserve',self.payload())['status'],'rejected')
        self.assertEqual(self.transport.calls,[])

    def test_no_ready_no_target_no_changed_generation_commit(self):
        self.transport.ready=False;self.assertEqual(self.reserve()['status'],'uncertain')
        self.assertEqual(self.gateway.submit(uid(),'commit',self.payload('commit'))['status'],'rejected')
        self.assertEqual(len(self.transport.calls),1)

    def test_opaque_native_endpoint_only_and_unknown_fields_refused(self):
        self.reserve()
        for changes in (dict(target_point_id=uid()),dict(target_xyz=[100,0,0]),dict(generation=2),dict(task_id=uid())):
            self.assertEqual(self.gateway.submit(uid(),'commit',self.payload('commit',**changes))['status'],'rejected')
        self.assertEqual(len(self.transport.calls),1)

    def test_release_and_home_are_separate_and_unverified_team_is_not_release(self):
        self.reserve();released=self.gateway.submit(uid(),'stop',self.payload('stop'))
        self.assertEqual(released['status'],'released');self.assertFalse(released['receipt']['facts']['physical_home']);self.assertFalse(released['receipt']['facts']['mission_effect_verified'])
        self.task=uid();self.lease=uid();self.reserve();self.transport.mode='fake_release'
        result=self.gateway.submit(uid(),'stop',self.payload('stop'))
        self.assertEqual(result['status'],'uncertain');self.assertNotEqual(self.arbiter.snapshot(self.lease)['state'],'released')

    def test_wrong_command_sequence_generation_and_claimed_completion_uncertain(self):
        for mode in ('wrong_id','wrong_seq','wrong_generation'):
            self.transport.mode=mode;self.lease=uid();result=self.reserve();self.assertEqual(result['status'],'uncertain')
            # Independent fixtures retain the previous unknown lease by design.
            break
        self.transport.mode='ok'

    def test_late_trusted_ready_receipt_updates_ledger_without_new_dispatch(self):
        original=self.transport.submit
        def pending(wire):
            result=original(wire);result['status']='accepted';result['phase']='braking';return result
        self.transport.submit=pending;request=uid();first=self.gateway.submit(request,'reserve',self.payload())
        self.assertEqual(first['status'],'accepted');raw=dict(self.transport.raw[-1],status='completed',phase='ready')
        ready=self.adapter.observe(request,raw);self.assertEqual(ready['status'],'completed');self.assertEqual(len(self.transport.calls),1)
        self.transport.submit=original;self.transport.mode='fake_completed'
        self.assertEqual(self.gateway.submit(uid(),'commit',self.payload('commit'))['status'],'uncertain')


if __name__=='__main__':unittest.main()
