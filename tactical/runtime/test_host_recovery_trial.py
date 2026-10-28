"""Real SQLite/Host recovery wiring with explicit synthetic native IO only."""
import json,tempfile,unittest,uuid,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'integration'))
import host_recovery_trial as trial
import test_host_runtime_tactical_recovery as fixtures


class HostRecoveryTrial(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.TacticalRecoveryTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.fixture.enable_first_home_scope();self.failed=self.fixture.failed()
        self.root=Path(self.fixture.temp.name);self.output=self.root/'trial.json';self.raw=self.root/'native.json'
        self.raw.write_text('{"synthetic_old_unknown":true}',encoding='utf-8')
        self.record=dict(native_report=str(self.raw),model_requests=0)
        owner_fixture=self.fixture
        class Runtime:
            diagnostic=True;controlled_fault_experiment=True;reconcile_return_experiment=True;test_only=True
            lease_deadline_frame=900
            @property
            def shared(self):return SimpleNamespace(native_last_sequence=owner_fixture.transport.sequence)
            @property
            def command_rows(self):return owner_fixture.transport.calls
            def admit(self,binding):return owner_fixture.transport.admit(binding)
        self.runtime=Runtime()
    def diagnostic_row(self):
        f=self.fixture;j=f.journal
        row=j.reserve_command(f.run,str(uuid.uuid4()),'diagnostic_foreign_move',{})
        seq=j.reserve_native_sequence(f.run,row['command_id'],2);self.assertEqual(seq,3)
        j.mark_dispatching(f.run,row['request_id']);j.record_outcome(f.run,row['request_id'],'completed',dict(reason_code='synthetic_fault_ack_only'))
        f.transport.calls.append(dict(operation='diagnostic_foreign_move',seq=3))
        # Observation highwater still2, exactly the verified publication window.
        self.assertEqual(f.transport.sequence,2)
    def recover(self):
        f=self.fixture
        with patch('host_runtime.host_tactical.time.sleep'),patch('host_recovery_trial.time.sleep'):
            return trial.recover_once(f.owner,self.runtime,f.journal,f.run,self.failed,self.record,self.output)

    def test_actual_host_allocator_uses4_after_durable_fault3_despite_old_observation2(self):
        self.diagnostic_row();self.recover();f=self.fixture
        self.assertEqual([w['seq']for w in f.transport.calls],[1,2,3,4])
        self.assertEqual(self.record['journaled_recovery']['status'],'first_home_released_old_task_still_failed')
        self.assertEqual(self.record['journaled_recovery']['original_after'],self.failed)
        self.assertEqual(f.journal.unresolved(f.run),[])
        self.assertEqual(self.raw.read_bytes(),(self.root/'native-pre-host-recovery.json').read_bytes())
        with self.assertRaisesRegex(ValueError,'already_attempted'):self.recover()
        self.assertEqual(len(f.transport.calls),4)

    def test_failed_home_gets_one_separate_release_with_both_failures_retained(self):
        self.diagnostic_row();self.fixture.transport.mode='home_unknown'
        with self.assertRaises(ValueError):self.recover()
        f=self.fixture;rows=f.journal.commands_for_run(f.run)
        self.assertEqual([w['operation']for w in f.transport.calls],['reserve','commit','diagnostic_foreign_move','reconcile_return_home','reconcile_release'])
        self.assertEqual([w['seq']for w in f.transport.calls],[1,2,3,4,5])
        self.assertEqual([r['status']for r in rows],['completed','uncertain','completed','uncertain','released'])
        self.assertEqual(f.journal.unresolved(f.run),[])
        self.assertEqual(self.record['journaled_recovery']['status'],'released_only_first_home_failed')

    def test_fault_intent_and_sql_dispatch_claim_are_durable_before_native_submit(self):
        f=self.fixture;state=dict(task_id=f.task,lease_id=self.failed['payload']['lease_id'])
        selected=(f.transport.point,dict(source='synthetic_native_point_for_wiring_test'))
        def submit(wire):
            row=f.journal.get_command(f.run,self.record['controlled_fault_request_id'])
            self.assertEqual(row['status'],'dispatching')
            self.assertEqual(json.loads((self.root/'controlled-fault-intent.json').read_text())['wire'],wire)
            self.assertEqual(f.journal.get_native_sequence(f.run,row['command_id']),3)
            return dict(command_id=wire['command_id'],seq=wire['seq'],status='started',reason_code='controlled_native_move_sent')
        self.runtime.submit=submit
        with patch('host_recovery_trial.choose_fault_point',return_value=selected):
            row=trial.inject_once(self.runtime,f.transport.actor,f.binding,f.journal,f.run,state,self.record,self.output)
            self.assertEqual(row['status'],'completed');self.assertFalse(row['receipt']['facts']['mission_effect_verified'])
            with self.assertRaisesRegex(ValueError,'already_attempted'):trial.inject_once(self.runtime,f.transport.actor,f.binding,f.journal,f.run,state,self.record,self.output)

    def test_fsync_failure_does_not_send_or_retry_fault(self):
        f=self.fixture;state=dict(task_id=f.task,lease_id=self.failed['payload']['lease_id']);calls=[]
        self.runtime.submit=lambda wire:calls.append(wire)
        with patch('host_recovery_trial.choose_fault_point',return_value=(f.transport.point,{})),patch('host_recovery_trial.seal_owned_intent',side_effect=OSError('synthetic fsync failure')):
            with self.assertRaises(OSError):trial.inject_once(self.runtime,f.transport.actor,f.binding,f.journal,f.run,state,self.record,self.output)
            with self.assertRaisesRegex(ValueError,'already_attempted'):trial.inject_once(self.runtime,f.transport.actor,f.binding,f.journal,f.run,state,self.record,self.output)
        self.assertEqual(calls,[])
        self.assertEqual(f.journal.get_command(f.run,self.record['controlled_fault_request_id'])['status'],'reserved')

    def test_run_refuses_synthetic_or_non_owned_transport_before_journal_creation(self):
        with self.assertRaisesRegex(ValueError,'owned_host_recovery_experiment_required'):
            trial.run_trial(self.runtime,None,None,None,self.record,self.output,home_window=None)
        self.assertFalse((self.root/'first-home-runtime.sqlite3').exists())

if __name__=='__main__':unittest.main()
