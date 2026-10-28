"""No-dispatch classification cannot hide a command or spend a new attach."""
from pathlib import Path
from types import SimpleNamespace
import sys,tempfile,unittest,uuid
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'integration'))
import journaled_trial,rotation_trial
from host_runtime.contracts import SessionBinding
from host_runtime.journal import CommandJournal
from preborrow import PlanningUnavailable

class PlanningRefusalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.output=self.root/'trial.json'
        self.binding=SessionBinding(1,str(uuid.uuid4()),3,str(uuid.uuid4()),1234,'2026-10-26T00:00:00+00:00',str(uuid.uuid4()),'a'*64,'b'*64)
        self.run=str(uuid.uuid4());self.journal=CommandJournal(self.root/'journal.sqlite3')
        self.runtime=SimpleNamespace(diagnostic=False,test_only=False,shared=SimpleNamespace(native_last_sequence=0),command_rows=[],actor_bytes=b'',output=self.root/'native.json')
        self.actor=SimpleNamespace(identity=SimpleNamespace(object_id=501,generation=1));self.record={}
        self.owner=SimpleNamespace(poll=Mock(return_value=None),snapshot=lambda:dict(tasks=[],unresolved=[]),reserve=Mock(side_effect=AssertionError('Reserve must not run')),shutdown=Mock())
    def tearDown(self):self.journal.close();self.temp.cleanup()
    def owner_factory(self,journal,run_id,binding,catalog,**kw):
        journal.register_run(run_id,binding.public());return self.owner
    def unavailable(self,runtime,binding,trial,*args):
        trial['planning_outcome']=dict(status='not_dispatched',reason_code='preborrow_no_home_and_endpoint_window_no_commands',tactical_commands_dispatched=0,control_acquired=False)
        raise PlanningUnavailable('preborrow_no_home_and_endpoint_window_no_commands')
    def run_trial(self,select):
        with patch.object(journaled_trial,'HostTactical',side_effect=self.owner_factory),patch.object(journaled_trial,'choose_target',side_effect=select):
            journaled_trial.run_trials(self.runtime,self.actor,self.binding,object(),self.record,self.output,home_window=object(),journal=self.journal,run_id=self.run,single_task=True)
    def test_no_reserve_or_recovery_and_explicit_durable_planning_outcome(self):
        with self.assertRaises(PlanningUnavailable):self.run_trial(self.unavailable)
        self.owner.reserve.assert_not_called()
        self.assertEqual(self.record['status'],'planning_unavailable_no_new_task_dispatched')
        self.assertEqual(self.record['journaled_tasks'][0]['status'],'not_dispatched')
        self.assertEqual(self.journal.commands_for_run(self.run),[])
        event=next(e for e in self.journal.events(self.run) if e['event_type']=='tactical_planning_not_dispatched')
        self.assertEqual(event['payload']['new_tactical_commands'],0)
        self.assertFalse(event['payload']['mission_effect_verified'])
    def test_sequence_change_during_selection_cannot_be_called_no_dispatch(self):
        def changed(*args):
            self.runtime.shared.native_last_sequence=1;return self.unavailable(*args)
        with self.assertRaisesRegex(ValueError,'dispatch_state_changed'):self.run_trial(changed)
        self.assertNotIn('reason_code',self.record)
        self.assertFalse(any(e['event_type']=='tactical_planning_not_dispatched' for e in self.journal.events(self.run)))
    def test_command_row_during_selection_cannot_be_called_no_dispatch(self):
        def changed(*args):
            self.journal.reserve_command(self.run,str(uuid.uuid4()),'reserve',dict(task_id=args[2]['task_id']))
            return self.unavailable(*args)
        with self.assertRaisesRegex(ValueError,'dispatch_state_changed'):self.run_trial(changed)
        self.assertEqual(len(self.journal.commands_for_run(self.run)),1)
        self.assertFalse(any(e['event_type']=='tactical_planning_not_dispatched' for e in self.journal.events(self.run)))
    def test_rotation_closes_first_unavailable_channel_without_any_successor_intent(self):
        self.runtime.output.write_text('{}',encoding='utf-8')
        client=SimpleNamespace(layout=SimpleNamespace(Actor=SimpleNamespace(from_buffer_copy=lambda _:object())),NativeRuntimeClient=Mock(side_effect=AssertionError('no successor attach')))
        record=dict(runtime_evidence='unused',runtime_evidence_sha256='a'*64);state={}
        def task(runtime,actor,binding,catalog,trial,output,**kw):
            kw['journal'].register_run(kw['run_id'],binding.public());kw['owner_state']['owner']=self.owner
            trial.update(status='planning_unavailable_no_new_task_dispatched',reason_code='preborrow_no_home_and_endpoint_window_no_commands')
            raise PlanningUnavailable(trial['reason_code'])
        with patch.object(rotation_trial,'run_trials',side_effect=task),patch.object(rotation_trial,'HomeWindow'),patch.object(rotation_trial,'capture',return_value={}),patch.object(rotation_trial,'assess_retirement',return_value=dict(no_control_acquired=True,control_released=False)),patch.object(rotation_trial,'retire_channel') as retire:
            self.runtime.poll=Mock(return_value={})
            rotation_trial.run_rotation_trials(client,self.runtime,self.actor,self.binding,object(),record,self.output,memory=object(),session_path=self.root/'session.json',state=state,epochs=4,hold_frames=675,lease_frames=900)
        retire.assert_not_called();client.NativeRuntimeClient.assert_not_called();self.owner.shutdown.assert_called_once()
        self.assertTrue(state['closed_verified']);self.assertEqual(len(record['rotation_channels']),1)
        self.assertEqual(record['unused_epochs'],3)
        self.assertEqual(record['status'],'rotation_planning_unavailable_requires_review')
        self.assertTrue(record['stopped_without_successor_attach'])
        with CommandJournal(self.root/'rotated-runtime.sqlite3') as journal:
            self.assertEqual(journal.commands_for_run(record['rotation_channels'][0]['journal_run_id']),[])

if __name__=='__main__':unittest.main()
