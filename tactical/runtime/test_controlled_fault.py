"""Diagnostic intent durability, native-point selection and pre-effect ordering."""
import json,hashlib,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import controlled_fault,diagnose,preborrow

class ControlledFaultTests(unittest.TestCase):
    def test_intent_is_fsynced_exclusive_and_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory()as d:
            output=Path(d)/'trial.json';events=[]
            fsync=controlled_fault.os.fsync
            with patch.object(controlled_fault.os,'fsync',side_effect=lambda fd:(events.append('fsync'),fsync(fd))):
                result=controlled_fault.seal_owned_intent(output,'controlled-fault-intent.json',dict(seq=3),dict(source='controlled_diagnostic_native_move'))
            self.assertEqual(events,['fsync']);original=Path(result['file']).read_bytes()
            self.assertEqual(hashlib.sha256(original).hexdigest(),result['sha256'])
            with self.assertRaises(FileExistsError):controlled_fault.seal_owned_intent(output,'controlled-fault-intent.json',dict(seq=4),{})
            self.assertEqual(Path(result['file']).read_bytes(),original)
            with self.assertRaisesRegex(ValueError,'name_unreviewed'):controlled_fault.seal_owned_intent(output,'../outside.json',{}, {})

    def runtime(self,points):
        return SimpleNamespace(observe_actor=lambda binding:dict(settled=True,stance=2,team=20,script_team=20,xyz=[40,0,0]),
            reserved_home=lambda task,lease:dict(xyz=[0,0,0]),targets=lambda:points)

    def test_fault_point_requires_current_native_candidate_outside_home_and_near_actor(self):
        points=dict(home=[0,0,0],near=[45,0,0],far=[200,0,0],high=[80,0,3],eligible=[80,0,0])
        key,proof=controlled_fault.choose_fault_point(self.runtime(points),None,dict(task_id='t',lease_id='l'))
        self.assertEqual(key,'eligible');self.assertEqual(proof['target_xyz'],[80,0,0]);self.assertFalse(proof['ordinary_authority_granted'])

    def test_no_native_point_or_unsettled_actor_does_not_create_an_injection_target(self):
        state=dict(task_id='t',lease_id='l')
        self.assertEqual(controlled_fault.choose_fault_point(self.runtime({}),None,state),(None,None))
        runtime=self.runtime({});runtime.observe_actor=lambda binding:dict(settled=False)
        with self.assertRaisesRegex(ValueError,'not_stopped_no_injection'):controlled_fault.choose_fault_point(runtime,None,state)

    def drive(self,directory,fail_fsync=False):
        events=[];output=Path(directory)/'trial.json'
        class Runtime:
            phase='idle';frame=100;task=None;lease=None
            def admit(self,binding):return SimpleNamespace(game_frame=self.frame,monotonic_ms=1000)
            def approved_target(self,key):return [80,0,0]if key=='fault'else[40,0,0]
            def submit(self,wire):
                events.append(wire['operation']);self.task=wire['task_id'];self.lease=wire['lease_id']
                if wire['operation']=='diagnostic_foreign_move':
                    sealed=json.loads((output.parent/'controlled-fault-intent.json').read_text(encoding='utf-8'))
                    if sealed['wire']!=wire or 'fsync'not in events:raise AssertionError('Effect preceded sealed intent')
                    self.phase='uncertain';return dict(status='started',phase='holding')
                self.phase='ready'if wire['operation']=='reserve'else'holding'
                return dict(status='accepted',phase=self.phase)
            def poll(self):
                self.frame+=20
                return dict(phase=self.phase,game_frame=self.frame,task_id=self.task,lease_id=self.lease)
        runtime=Runtime();actor=SimpleNamespace(identity=SimpleNamespace(object_id=501,generation=1),born_frame=90)
        binding=SimpleNamespace(binding_hash='binding',host_id='host');record={};fsync=controlled_fault.os.fsync
        def synced(fd):
            events.append('fsync')
            if fail_fsync:raise OSError('diagnostic disk refusal before SDK')
            return fsync(fd)
        with patch.object(preborrow,'choose_target',return_value='out'),patch.object(preborrow,'choose_commit_target',return_value='out'),patch.object(controlled_fault,'choose_fault_point',return_value=('fault',dict(source='current_native_endpoint_registry'))),patch.object(controlled_fault.os,'fsync',side_effect=synced),patch.object(diagnose.time,'sleep'):
            with self.assertRaises(OSError if fail_fsync else ValueError):
                diagnose.run_direct_trial(runtime,actor,binding,record,output,home_window=object(),reconcile_return_experiment=True,controlled_fault_experiment=True)
        return events,record

    def test_driver_seals_intent_before_one_fault_and_keeps_real_guard_failure(self):
        with tempfile.TemporaryDirectory()as d:
            events,record=self.drive(d)
            self.assertEqual(events,['reserve','commit','fsync','diagnostic_foreign_move'])
            self.assertEqual(record['runtime_commands'][-1]['wire']['seq'],3)
            self.assertEqual(len(record['runtime_commands']),3)

    def test_driver_never_sends_fault_if_intent_fsync_fails(self):
        with tempfile.TemporaryDirectory()as d:
            events,record=self.drive(d,True)
            self.assertEqual(events,['reserve','commit','fsync'])
            self.assertEqual(len(record['runtime_commands']),2)

if __name__=='__main__':unittest.main()
