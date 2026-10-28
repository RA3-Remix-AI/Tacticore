"""Real gateway/owner/journal recovery composition; synthetic native IO only."""
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from host_runtime.host_tactical import HostTactical
from host_runtime.journal import CommandJournal
from host_runtime.contracts import ContractError, SessionBinding
from host_runtime.tactical_adapter import RuntimeSnapshot
from host_runtime.capabilities import CapabilityCatalog,VerifiedGrant
from host_runtime.contracts import canonical_json
import test_host_runtime_tactical_adapter as tactical_fixtures
from test_host_runtime_tactical_adapter import Transport, uid


class RecoveryTransport(Transport):
    def __init__(self,binding):
        super().__init__(binding)
        self.frame=100;self.ms=1000;self.sequence=0;self.mode='fail_commit'

    def admit(self,binding):
        self.frame+=1;self.ms+=10
        return RuntimeSnapshot(binding.binding_hash,self.frame,self.ms,False,self.sequence,
            self.executor_sha256,self.native_host_sha256,'synthetic_current')

    def submit(self,wire):
        self.calls.append(wire);self.sequence=wire['seq'];self.frame+=1;self.ms+=10
        if wire['operation']=='reconcile_release' and self.mode=='recovery_unknown':
            raise OSError('synthetic unknown recovery delivery')
        row=dict(command_id=wire['command_id'],task_id=wire['task_id'],lease_id=wire['lease_id'],
            seq=wire['seq'],binding_hash=self.binding.binding_hash,object_id=501,generation=1,
            status='completed',phase='ready',held=True,physical_home=False,control_released=False,
            stance_restored=False,game_frame=self.frame,monotonic_ms=self.ms,
            reason_code='ready_after_physical_stop',source_reference='synthetic_receipt_'+str(self.sequence),
            observation=dict(team=20,default_team=10,stance=2))
        if wire['operation']=='commit' and self.mode=='fail_commit':
            row.update(status='uncertain',phase='uncertain',reason_code='unknown_native_command_observed',sdk_calls=[1,1,2,1,0,0])
        elif wire['operation']!='reserve':
            row.update(status='released',phase='released',held=False,physical_home=wire['operation']=='commit',
                control_released=True,stance_restored=True,reason_code='native_control_release_observed',
                observation=dict(team=10,default_team=10,stance=0))
        if wire['operation']=='reconcile_release' and self.mode=='fake_release':row['observation']['team']=20
        if wire['operation']=='reserve' and self.mode=='fail_reserve':row.update(status='uncertain',phase='uncertain',reason_code='synthetic_borrow_unknown')
        if wire['operation']=='reconcile_return_home':
            row.update(physical_home=True,reason_code='native_control_release_without_goal_effect',sdk_calls=[1,1,4,2,1,1])
            if self.mode=='home_unknown':
                row.update(status='uncertain',phase='uncertain',physical_home=False,held=True,
                    control_released=False,stance_restored=False,reason_code='return_stalled_control_release_unknown',
                    sdk_calls=[1,1,3,2,0,0],observation=dict(team=20,default_team=10,stance=2))
            if self.mode=='home_release_without_home':row['physical_home']=False
            if self.mode=='home_fake_pool':row['observation']['team']=20
        self.raw.append(row)
        return row

    def poll(self):return dict(self.raw[-1])

    def observe_actor(self,binding):
        self.frame+=1;self.ms+=10
        return dict(frame=self.frame,monotonic_ms=self.ms,object_id=501,generation=1,
            state_id=94,state_vtable=0xc551a0,command_source=1,stance=2,path=0,state_flags=0x10000,
            team=20,script_team=20,foreign_epoch=0,xyz=[100,0,0],identity=True,birth_verified=True,
            live=True,grounded=True,paused=False)


class TacticalRecoveryTests(unittest.TestCase):
    def test_default_catalog_cannot_grant_first_home_or_diagnostic_injection(self):
        for operation in ('reconcile_return_home','diagnostic_foreign_move'):
            result=self.owner.gateway.submit(uid(),operation,dict(task_id=self.task))
            self.assertEqual(result['status'],'rejected')
            self.assertEqual(result['receipt']['reason_code'],'capability_unsupported'if operation=='reconcile_return_home'else'operation_unsupported')
        self.assertEqual(self.transport.calls,[])
        self.assertEqual(self.journal.native_sequence_high_water(self.binding.public()),0)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'ledger.sqlite3'
        self.journal=CommandJournal(self.path)
        self.binding=SessionBinding(1,uid(),7,uid(),1234,'2026-10-26T00:00:00+00:00',uid(),'a'*64,'b'*64)
        fixture=tactical_fixtures.TacticalAdapterTests();fixture.binding=self.binding;self.catalog=fixture.catalog_for()
        self.run=uid();self.task=uid();self.transport=RecoveryTransport(self.binding)
        self.owner=HostTactical(self.journal,self.run,self.binding,self.catalog,test_transport=self.transport)

    def tearDown(self):self.journal.close();self.temp.cleanup()

    def failed(self):
        self.owner.reserve(self.task,object_id=501,actor_generation=1)
        result=self.owner.commit(self.task,target_point_id=self.transport.point)
        self.assertEqual(result['status'],'uncertain')
        return result

    def recover(self,failed):
        with patch('host_runtime.host_tactical.time.sleep'):
            return self.owner.reconcile_release(self.task,uncertain_command_id=failed['command_id'])

    def enable_first_home_scope(self,**changes):
        base=self.catalog.require('tactics.move_hold_return',self.binding)
        scope=dict(base.public()['execution_constraints'],purpose='reconcile_return_home',module='runtime_first_home_recovery_v1',evidence_id='synthetic-recovery-proof')
        scope.update(changes)
        grant=VerifiedGrant('tactics.reconcile_return_home','synthetic-recovery-proof','f'*64,scope['executor_sha256'],'test-only first home',canonical_json(scope))
        catalog=CapabilityCatalog.verify(self.binding,[base,grant],lambda candidate,binding:candidate)
        self.owner.adapter.catalog=catalog;self.owner.gateway.capabilities=catalog

    def home(self,failed):
        with patch('host_runtime.host_tactical.time.sleep'):
            return self.owner.reconcile_return_home(self.task,uncertain_command_id=failed['command_id'])

    def test_first_home_requires_its_own_grant_before_intent_or_native_sequence(self):
        failed=self.failed()
        with self.assertRaisesRegex(ContractError,'capability_unsupported'):self.home(failed)
        self.assertEqual(len(self.transport.calls),2)
        self.assertEqual(self.journal.native_sequence_high_water(self.binding.public()),2)
        self.assertEqual(len(self.journal.commands_for_run(self.run)),2)

    def test_first_home_scope_cannot_reuse_basic_movement_or_other_binary(self):
        failed=self.failed()
        for changes in (dict(purpose='move_hold_return'),dict(module='unverified'),dict(executor_sha256='a'*64),dict(native_host_sha256='b'*64)):
            self.enable_first_home_scope(**changes)
            with self.subTest(changes=changes),self.assertRaisesRegex(ValueError,'first_home_recovery_scope_unverified'):self.home(failed)
        self.assertEqual(len(self.transport.calls),2)

    def test_first_home_keeps_old_failure_and_credits_only_physical_recovery(self):
        self.enable_first_home_scope();failed=self.failed();original=dict(failed)
        released=self.home(failed);facts=released['receipt']['facts']
        self.assertEqual(released['status'],'released');self.assertTrue(facts['physical_home'])
        self.assertFalse(facts['mission_effect_verified']);self.assertEqual(facts['recovery_of_command_id'],failed['command_id'])
        self.assertEqual(self.journal.get_command(self.run,failed['request_id']),original)
        self.assertEqual(self.journal.unresolved(self.run),[])
        self.assertEqual(self.home(failed)['command_id'],released['command_id'])
        self.assertEqual([w['operation']for w in self.transport.calls],['reserve','commit','reconcile_return_home'])
        self.assertEqual([w['seq']for w in self.transport.calls],[1,2,3])
        self.transport.mode='ok';self.assertEqual(self.owner.reserve(uid(),object_id=501,actor_generation=1)['status'],'completed')
        self.journal.close();self.journal=CommandJournal(self.path)
        self.assertEqual(self.journal.get_command(self.run,failed['request_id'])['status'],'uncertain')
        self.assertEqual(self.journal.get_command(self.run,released['request_id'])['status'],'released')

    def test_first_home_rejects_already_attempted_or_unverified_move_counter(self):
        self.enable_first_home_scope();failed=self.failed()
        for calls in ([1,1,3,2,0,0],None,[1,1,2,True,0,0],[1,1,2,1,0]):
            self.transport.raw[-1]['sdk_calls']=calls
            with self.subTest(calls=calls),self.assertRaisesRegex(ContractError,'return_requires_unattempted_home'):self.home(failed)
        self.assertEqual(len(self.transport.calls),2)
        self.assertEqual(self.journal.native_sequence_high_water(self.binding.public()),2)

    def test_first_home_unknown_never_retried_and_new_release_closes_control_ancestry(self):
        self.enable_first_home_scope();failed=self.failed();original=dict(failed)
        self.transport.mode='home_unknown';unknown=self.home(failed);old_home=dict(unknown)
        self.assertEqual(unknown['status'],'uncertain');self.assertEqual(self.home(failed),unknown)
        with self.assertRaisesRegex(ContractError,'tactical_intent_changed'):self.home(unknown)
        # Revoking physical authority cannot turn a readonly replay into a retry,
        # nor prevent the separately admitted release-only safety operation.
        self.owner.adapter.catalog=self.catalog;self.owner.gateway.capabilities=self.catalog
        self.assertEqual(self.home(failed),unknown)
        self.assertEqual(len(self.transport.calls),3)
        self.assertEqual(len(self.journal.unresolved(self.run)),3)
        released=self.recover(unknown)
        self.assertEqual(released['status'],'released');self.assertFalse(released['receipt']['facts']['physical_home'])
        self.assertEqual(released['receipt']['facts']['recovery_of_command_id'],unknown['command_id'])
        self.assertEqual(self.journal.unresolved(self.run),[])
        self.assertEqual(self.journal.get_command(self.run,failed['request_id']),original)
        self.assertEqual(self.journal.get_command(self.run,unknown['request_id']),old_home)
        self.assertEqual([w['operation']for w in self.transport.calls],['reserve','commit','reconcile_return_home','reconcile_release'])
        self.assertEqual([w['seq']for w in self.transport.calls],[1,2,3,4])
        self.journal.close();self.journal=CommandJournal(self.path)
        self.assertEqual(self.journal.unresolved(self.run),[])
        self.assertEqual(self.journal.unresolved_for_session(self.binding.public()),[])

    def test_first_home_unverified_physical_or_pool_return_remains_unknown(self):
        self.enable_first_home_scope();failed=self.failed();self.transport.mode='home_release_without_home'
        result=self.home(failed)
        self.assertEqual(result['status'],'uncertain')
        self.assertNotEqual(self.owner.snapshot()['tasks'][0]['control']['state'],'released')
        self.assertEqual(len(self.journal.unresolved(self.run)),3)

    def test_first_home_success_flags_cannot_hide_wrong_native_pool(self):
        self.enable_first_home_scope();failed=self.failed();self.transport.mode='home_fake_pool'
        result=self.home(failed)
        self.assertEqual(result['status'],'uncertain')
        self.assertNotEqual(self.owner.snapshot()['tasks'][0]['control']['state'],'released')

    def test_first_home_is_not_a_retry_of_failed_reserve(self):
        self.enable_first_home_scope();self.transport.mode='fail_reserve'
        ready=self.owner.reserve(self.task,object_id=501,actor_generation=1)
        self.assertEqual(ready['status'],'uncertain')
        with self.assertRaisesRegex(ContractError,'prior_unknown_required'):self.owner.reconcile_return_home(self.task,uncertain_command_id=ready['command_id'])
        self.assertEqual(len(self.transport.calls),1)

    def test_first_home_rejects_backwards_observation_clock_without_sending(self):
        self.enable_first_home_scope();failed=self.failed();observe=self.transport.observe_actor
        def regressed(binding):
            sample=observe(binding);sample['monotonic_ms']=1;return sample
        self.transport.observe_actor=regressed
        with self.assertRaisesRegex(ContractError,'clock_regressed'):self.home(failed)
        self.assertEqual(len(self.transport.calls),2)

    def test_recovery_audit_keeps_four_distinct_frames_despite_repeated_reads(self):
        self.enable_first_home_scope();failed=self.failed();observe=self.transport.observe_actor
        first=self.transport.frame+1;frames=iter([first,first,first+1,first+1,first+2,first+3])
        def repeated(binding):
            sample=observe(binding);sample['frame']=next(frames);return sample
        self.transport.observe_actor=repeated
        result=self.home(failed);self.assertEqual(result['status'],'released')
        event=next(e for e in self.journal.events(self.run)if e['event_type']=='tactical_recovery_quiescence_observed')
        self.assertEqual(event['payload']['frames'],[first,first+1,first+2,first+3])
        self.assertEqual([s['frame']for s in event['payload']['observations']],event['payload']['frames'])

    def test_new_release_retains_original_failure_survives_reopen_and_allows_next_task(self):
        failed=self.failed();original=self.journal.get_command(self.run,failed['request_id'])
        released=self.recover(failed)
        self.assertEqual(released['status'],'released')
        self.assertFalse(released['receipt']['facts']['mission_effect_verified'])
        self.assertFalse(released['receipt']['facts']['physical_home'])
        self.assertEqual(released['receipt']['facts']['recovery_of_command_id'],failed['command_id'])
        self.assertEqual(self.journal.get_command(self.run,failed['request_id']),original)
        self.assertEqual(self.journal.unresolved(self.run),[])
        self.assertEqual([w['seq'] for w in self.transport.calls],[1,2,3])
        self.assertEqual([w['operation'] for w in self.transport.calls],['reserve','commit','reconcile_release'])
        self.assertEqual(self.recover(failed)['command_id'],released['command_id'])
        self.assertEqual(len(self.transport.calls),3)
        self.journal.close();self.journal=CommandJournal(self.path)
        self.assertEqual(self.journal.unresolved(self.run),[])
        self.assertEqual(self.journal.unresolved_for_session(self.binding.public()),[])
        self.assertEqual(self.journal.get_command(self.run,failed['request_id'])['status'],'uncertain')
        owner=HostTactical(self.journal,uid(),self.binding,self.catalog,test_transport=self.transport)
        self.transport.mode='ok'
        self.assertEqual(owner.reserve(uid(),object_id=501,actor_generation=1)['status'],'completed')
        self.assertEqual(self.transport.calls[-1]['seq'],4)

    def test_unknown_recovery_delivery_never_retried_or_resolved(self):
        failed=self.failed();self.transport.mode='recovery_unknown';result=self.recover(failed)
        self.assertEqual(result['status'],'uncertain')
        self.assertEqual(self.recover(failed)['command_id'],result['command_id'])
        self.assertEqual(len(self.transport.calls),3)
        self.assertEqual(len(self.journal.unresolved(self.run)),3)
        self.assertEqual(self.owner.snapshot()['tasks'][0]['control']['state'],'return_requested')
        with self.assertRaisesRegex(ContractError,'not_released'):self.owner.reserve(uid(),object_id=501,actor_generation=1)

    def test_external_source2_stop_is_only_quiescence_for_one_new_release(self):
        failed=self.failed();original=self.journal.get_command(self.run,failed['request_id'])
        observe=self.transport.observe_actor
        def external_stop(binding):
            sample=observe(binding);sample.update(command_source=2,settled=False,foreign_epoch=2)
            return sample
        self.transport.observe_actor=external_stop
        released=self.recover(failed)
        self.assertEqual(released['status'],'released')
        self.assertFalse(released['receipt']['facts']['mission_effect_verified'])
        self.assertFalse(released['receipt']['facts']['physical_home'])
        self.assertEqual(self.journal.get_command(self.run,failed['request_id']),original)
        events=[r for r in self.journal.events(self.run) if r['event_type']=='tactical_recovery_quiescence_observed']
        self.assertEqual(len(events),1)
        self.assertTrue(all(s['command_source']==2 and s['settled'] is False for s in events[0]['payload']['observations']))
        self.assertEqual([w['operation'] for w in self.transport.calls],['reserve','commit','reconcile_release'])
        self.assertEqual(self.recover(failed)['command_id'],released['command_id'])
        self.assertEqual(len(self.transport.calls),3)

    def test_wrong_native_identity_does_not_publish_recovery(self):
        failed=self.failed();self.transport.raw[-1]['object_id']=502
        result=self.recover(failed)
        self.assertEqual(result['status'],'rejected')
        self.assertIn('current_unknown_unverified',result['receipt']['reason_code'])
        self.assertEqual(len(self.transport.calls),2)
        self.assertEqual(len(self.journal.unresolved(self.run)),2)

    def test_unverified_release_leaves_both_unknowns_and_ownership(self):
        failed=self.failed();self.transport.mode='fake_release';result=self.recover(failed)
        self.assertEqual(result['status'],'uncertain')
        self.assertEqual(len(self.journal.unresolved(self.run)),3)
        self.assertNotEqual(self.owner.snapshot()['tasks'][0]['control']['state'],'released')

    def test_poll_and_normal_stop_cannot_reconcile_unknown(self):
        failed=self.failed();self.assertEqual(self.owner.poll(),failed)
        stopped=self.owner.stop(self.task)
        self.assertEqual(stopped['status'],'rejected')
        self.assertEqual(len(self.transport.calls),2)
        self.assertEqual(self.journal.get_command(self.run,failed['request_id'])['status'],'uncertain')

    def test_changed_reference_or_non_unknown_refused(self):
        ready=self.owner.reserve(self.task,object_id=501,actor_generation=1)
        with self.assertRaisesRegex(ContractError,'prior_unknown_required'):
            self.owner.reconcile_release(self.task,uncertain_command_id=ready['command_id'])
        failed=self.owner.commit(self.task,target_point_id=self.transport.point)
        self.recover(failed)
        with self.assertRaisesRegex(ContractError,'intent_changed'):
            self.owner.reconcile_release(self.task,uncertain_command_id=uid())
        self.assertEqual(len(self.transport.calls),3)

    def test_fresh_quiescence_required_before_new_intent(self):
        failed=self.failed();observe=self.transport.observe_actor
        def moving(binding):
            sample=observe(binding);sample['state_flags']=1
            return sample
        self.transport.observe_actor=moving
        with patch('host_runtime.host_tactical.time.monotonic',side_effect=[0,0,9]),patch('host_runtime.host_tactical.time.sleep'):
            with self.assertRaisesRegex(ContractError,'no_quiescent_window'):self.recover(failed)
        self.assertEqual(len(self.transport.calls),2)
        self.assertEqual(len(self.journal.unresolved(self.run)),2)


if __name__=='__main__':unittest.main()
