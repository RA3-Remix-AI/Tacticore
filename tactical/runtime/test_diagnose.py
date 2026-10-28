"""Failure cleanup regression tests; no game, mappings or model calls."""
import importlib.util
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('runtime_diagnostic_cleanup', HERE / 'diagnose.py')
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class CLIAdmissionTests(unittest.TestCase):
    def test_host_first_home_is_owned_separate_and_requires_both_evidence_pairs(self):
        base=['diagnose.py','--session','not-opened.json','--output','not-created.json','--journaled-first-home-experiment']
        complete=['--execute','--controlled-native-move','--reconcile-return-home-experiment','--runtime-evidence','basic.json',
            '--runtime-sha256','a'*64,'--runtime-recovery-evidence','recovery.json','--runtime-recovery-sha256','b'*64]
        variants=[[],complete+['--journaled-repeat'],complete+['--journaled-rotation-experiment']]
        for missing in ('--controlled-native-move','--reconcile-return-home-experiment','--execute'):
            variants.append([v for v in complete if v!=missing])
        variants.append(complete[:-2])
        for flags in variants:
            with self.subTest(flags=flags),patch.object(diagnostic.sys,'argv',base+flags),patch.object(diagnostic,'load',side_effect=AssertionError('No native access')),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit)as raised:diagnostic.main()
                self.assertEqual(raised.exception.code,2)

    def test_controlled_fault_requires_explicit_owned_recovery_mode_before_native_access(self):
        base=['diagnose.py','--session','not-opened.json','--output','not-created.json','--controlled-native-move']
        for flags in ([],['--execute'],['--reconcile-return-home-experiment'],['--execute','--reconcile-return-home-experiment','--journaled-repeat']):
            with self.subTest(flags=flags),patch.object(diagnostic.sys,'argv',base+flags),patch.object(diagnostic,'load',side_effect=AssertionError('No native access')),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit)as raised:diagnostic.main()
                self.assertEqual(raised.exception.code,2)

    def test_first_home_recovery_is_owned_direct_and_separate_before_native_access(self):
        base=['diagnose.py','--session','not-opened.json','--output','not-created.json','--reconcile-return-home-experiment']
        for flags in ([],['--execute','--journaled-repeat'],['--execute','--yield-abort-experiment'],['--execute','--source-team-order-experiment']):
            with self.subTest(flags=flags),patch.object(diagnostic.sys,'argv',base+flags),patch.object(diagnostic,'load',side_effect=AssertionError('No native access')),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit)as raised:diagnostic.main()
                self.assertEqual(raised.exception.code,2)

    def test_long_rotation_and_paid_settings_are_bounded_before_native_access(self):
        base=['diagnose.py','--session','not-opened.json','--output','not-created.json']
        variants=[['--rotation-epochs','4'],['--rotation-hold-frames','675'],
            ['--execute','--journaled-repeat','--journaled-rotation-experiment','--rotation-epochs','5'],
            ['--execute','--journaled-repeat','--journaled-rotation-experiment','--rotation-hold-frames','675','--rotation-lease-frames','750'],
            ['--execute','--journaled-repeat','--journaled-rotation-experiment','--rotation-epochs','4','--rotation-fresh-paid-actors']]
        for flags in variants:
            with self.subTest(flags=flags),patch.object(diagnostic.sys,'argv',base+flags),\
                    patch.object(diagnostic,'load',side_effect=AssertionError('No native/client access permitted')),\
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:diagnostic.main()
                self.assertEqual(raised.exception.code,2)

    def test_rotation_is_owned_journaled_and_separate_from_budget_exhaustion(self):
        base=['diagnose.py','--session','not-opened.json','--output','not-created.json','--journaled-rotation-experiment']
        for flags in ([],['--execute'],['--journaled-repeat'],['--execute','--journaled-repeat','--journaled-budget-recovery-experiment']):
            with self.subTest(flags=flags),patch.object(diagnostic.sys,'argv',base+flags),\
                    patch.object(diagnostic,'load',side_effect=AssertionError('No native/client access permitted')),\
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:diagnostic.main()
                self.assertEqual(raised.exception.code,2)

    def test_budget_experiment_cannot_start_without_owned_journaled_execution(self):
        base=['diagnose.py','--session','not-opened.json','--output','not-created.json',
            '--journaled-budget-recovery-experiment']
        for flags in ([],['--execute'],['--journaled-repeat']):
            with self.subTest(flags=flags),patch.object(diagnostic.sys,'argv',base+flags),\
                    patch.object(diagnostic,'load',side_effect=AssertionError('No native/client access permitted')),\
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:diagnostic.main()
                self.assertEqual(raised.exception.code,2)


class ReservedYieldWaitTests(unittest.TestCase):
    def test_team_order_wait_is_bounded_and_never_commits(self):
        class Runtime:
            frame=100
            def observe_actor(self,binding):return dict(frame=self.frame)
            def poll(self):self.frame+=30;return dict(phase='ready')
            def submit(self,*a,**k):raise AssertionError('Roster observation cannot commit')
        record={}
        with tempfile.TemporaryDirectory() as d:
            diagnostic.wait_source_team_order(Runtime(),None,record,Path(d)/'trial.json')
        self.assertEqual('source_team_order_observed_no_commit',record['status'])
        self.assertFalse(record['source_team_order_wait']['goal_commit_permitted'])

    def run_wait(self, phases, frames):
        class Runtime:
            index=-1
            def observe_actor(self,binding):
                index=max(0,self.index)
                return dict(frame=frames[index],xyz=[0,0,0])
            def poll(self):
                self.index+=1
                return dict(phase=phases[self.index])
            def submit(self,request):raise AssertionError('Ready wait must never submit a command')
        record={}
        with tempfile.TemporaryDirectory() as directory,patch.object(diagnostic.time,'sleep'):
            diagnostic.wait_reserved_yield(Runtime(),None,record,Path(directory)/'trial.json')
        return record

    def test_no_yield_is_bounded_and_cannot_commit(self):
        with self.assertRaisesRegex(ValueError,'reserved_yield_not_observed_no_commit'):
            self.run_wait(['ready','ready'],[100,400])

    def test_return_can_finish_after_ready_budget_but_requires_independent_review(self):
        record=self.run_wait(['ready','returning','released'],[100,401,410])
        self.assertEqual('native_terminal_requires_independent_review',record['status'])
        self.assertFalse(record['reserved_yield_wait']['commit_permitted'])
        self.assertNotIn('native_yield_verified',record)

    def test_uncertain_is_preserved_for_cleanup(self):
        with self.assertRaisesRegex(ValueError,'reserved_yield_native_result_uncertain'):
            self.run_wait(['uncertain'],[100])


class CleanupTests(unittest.TestCase):
    def first_home_experiment(self,mode):
        calls=[];samples=[];requests=[]
        class Runtime:
            _actor=SimpleNamespace(identity=SimpleNamespace(object_id=779,generation=1),born_frame=500)
            lease_deadline_frame=1400;last_sequence=2;command='original';phase='uncertain'
            command_rows=[dict(wire=dict(seq=1)),dict(wire=dict(seq=2))]
            def poll(self):return dict(phase=self.phase,held=self.phase!='released',command_id=self.command,task_id='task',lease_id='lease')
            def observe_actor(self,binding):
                row=dict(frame=1000+len(samples),state_id=94,state_vtable=0xc551a0,command_source=2,stance=2,path=0,state_flags=0x10000,team=20,script_team=20,foreign_epoch=2,xyz=[80,0,0]);samples.append(row);return row
            def admit(self,binding):return SimpleNamespace(game_frame=1010+len(samples),monotonic_ms=1000,last_sequence=self.last_sequence)
            def submit(self,wire):
                requests.append(wire);self.command_rows.append(dict(wire=wire));calls.append(wire['operation'])
                if wire['operation']=='reconcile_return_home' and mode!='success':
                    raw.write_text('{"stage":"after-home-attempt"}',encoding='utf-8')
                    if mode=='unknown':self.last_sequence=wire['seq'];self.command=wire['command_id']
                    return dict(status='uncertain'if mode=='unknown'else'rejected',phase='uncertain')
                self.command=wire['command_id'];self.last_sequence=wire['seq'];self.phase='released'
                return dict(status='released',phase='released',physical_home=mode=='success',control_released=True)
            def stop(self):calls.append('stop');return dict(control_released=self.phase=='released',physical_home=mode=='success')
            def close(self):calls.append('close')
        runtime=Runtime();runtime.command_rows=list(runtime.command_rows);record=dict(status='failed_or_unknown',reason_code='original_foreign_command',reconcile_return_home_experiment=True)
        with tempfile.TemporaryDirectory()as directory,patch.object(diagnostic.time,'sleep'):
            raw=Path(directory)/'native.json';raw.write_text('{"stage":"original-unknown"}',encoding='utf-8')
            diagnostic.cleanup_runtime(runtime,record,SimpleNamespace(binding_hash='b',host_id='h'),raw,Path(directory)/'trial.json')
            original=Path(record['recovery_prior_raw']).read_bytes()
            fallback=Path(record['failed_return_release_prior_raw']).read_bytes()if 'failed_return_release_prior_raw'in record else None
        return calls,samples,requests,record,original,fallback

    def test_new_first_home_request_can_return_without_changing_original_failure(self):
        calls,samples,requests,record,original,fallback=self.first_home_experiment('success')
        self.assertEqual(calls,['reconcile_return_home','stop','close']);self.assertEqual(len(samples),4)
        self.assertEqual(requests[0]['seq'],3);self.assertEqual(record['status'],'failed_or_unknown')
        self.assertEqual(record['reason_code'],'original_foreign_command');self.assertTrue(record['explicit_recovery_terminal']['physical_home'])
        self.assertEqual(original,b'{"stage":"original-unknown"}');self.assertIsNone(fallback)

    def test_unknown_new_home_move_only_gets_a_new_release_after_new_quiescence(self):
        calls,samples,requests,record,original,fallback=self.first_home_experiment('unknown')
        self.assertEqual(calls,['reconcile_return_home','reconcile_release','stop','close']);self.assertEqual(len(samples),8)
        self.assertEqual([v['seq']for v in requests],[3,4]);self.assertNotEqual(requests[0]['command_id'],requests[1]['command_id'])
        self.assertEqual(record['failed_return_release_of_command_id'],requests[0]['command_id'])
        self.assertFalse(record['failed_return_release_only_terminal']['physical_home']);self.assertEqual(record['status'],'failed_or_unknown')
        self.assertEqual(original,b'{"stage":"original-unknown"}');self.assertEqual(fallback,b'{"stage":"after-home-attempt"}')

    def test_refused_new_home_request_does_not_reuse_its_sequence_or_overwrite_prior(self):
        calls,samples,requests,record,original,fallback=self.first_home_experiment('rejected')
        self.assertEqual([v['seq']for v in requests],[3,4]);self.assertEqual(record['failed_return_release_of_command_id'],'original')
        self.assertEqual(calls.count('reconcile_return_home'),1);self.assertEqual(calls.count('reconcile_release'),1)
        self.assertEqual(len(samples),8);self.assertEqual(original,b'{"stage":"original-unknown"}')

    def test_return_that_stalls_during_stop_gets_one_fresh_release_only_reconciliation(self):
        calls=[];samples=[]
        class Runtime:
            phase='returning'
            _actor=SimpleNamespace(identity=SimpleNamespace(object_id=779,generation=1),born_frame=500)
            lease_deadline_frame=1300
            def poll(self):return dict(phase=self.phase,held=self.phase!='released',command_id='prior',task_id='task',lease_id='lease')
            def observe_actor(self,binding):
                value=dict(frame=800+len(samples),state_id=94,state_vtable=0xc551a0,command_source=1,stance=2,path=0,state_flags=0x10000,team=20,script_team=20,foreign_epoch=0,xyz=[60,0,0]);samples.append(value);return value
            def admit(self,binding):return SimpleNamespace(game_frame=810,monotonic_ms=1000,last_sequence=1)
            def submit(self,request):
                self.request=request;calls.append('reconcile');self.phase='released'
                return dict(status='released',phase='released',control_released=True,physical_home=False)
            def stop(self):
                calls.append('stop')
                if self.phase=='returning':self.phase='uncertain';raise TimeoutError('runtime_control_release_unknown')
                return dict(control_released=True,physical_home=False)
            def close(self):calls.append('close')
        runtime=Runtime();record=dict(status='failed_or_unknown')
        with tempfile.TemporaryDirectory() as directory,patch.object(diagnostic.time,'sleep'):
            raw=Path(directory)/'native.json';raw.write_text('{}')
            diagnostic.cleanup_runtime(runtime,record,SimpleNamespace(binding_hash='b',host_id='h'),raw,Path(directory)/'trial.json')
        self.assertEqual(['stop','reconcile','stop','close'],calls)
        self.assertEqual('reconcile_release',runtime.request['operation'])
        self.assertEqual(2,runtime.request['seq'])
        self.assertEqual(4,len(samples))
        self.assertEqual('TimeoutError',record['runtime_release_unknown'])
        self.assertTrue(record['post_stop_recovery_attempted'])
        self.assertTrue(record['runtime_stop']['control_released'])
        self.assertFalse(record['runtime_stop']['physical_home'])
        self.assertEqual('failed_or_unknown',record['status'])

    def test_recovery_waits_for_new_quiescent_frames_before_one_explicit_request(self):
        samples = []
        calls = []
        class Runtime:
            _actor = SimpleNamespace(identity=SimpleNamespace(object_id=781, generation=1), born_frame=100)
            lease_deadline_frame = 800
            def poll(self):
                return dict(phase='uncertain', held=True, command_id='old', task_id='task', lease_id='lease')
            def observe_actor(self, binding):
                index = len(samples)
                sample = dict(frame=110+index, state_id=26 if index==0 else 94,
                    state_vtable=0xc553d0 if index==0 else 0xc551a0,
                    command_source=1, stance=2, path=1 if index==0 else 0,
                    state_flags=0x10000, team=20, script_team=20,
                    foreign_epoch=1, xyz=[60,0,0])
                samples.append(sample)
                return sample
            def admit(self, binding):
                return SimpleNamespace(game_frame=120, monotonic_ms=1000, last_sequence=4)
            def submit(self, request):
                self.request=request;calls.append('reconcile')
                self.observed_before_request=len(samples)
                return dict(status='released', phase='released', physical_home=False)
            def stop(self):
                calls.append('stop');return dict(control_released=True, physical_home=False)
            def close(self):calls.append('close')
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory)/'native.json';raw.write_text('{}')
            runtime=Runtime();record=dict(status='failed_or_unknown')
            with patch.object(diagnostic.time,'sleep',return_value=None):
                diagnostic.cleanup_runtime(runtime,record,SimpleNamespace(binding_hash='b',host_id='host'),raw,Path(directory)/'trial.json')
            self.assertEqual(['reconcile','stop','close'],calls)
            self.assertEqual(5,runtime.observed_before_request)
            self.assertEqual([111,112,113,114],record['recovery_quiescent_frames'])
            self.assertEqual(5,runtime.request['seq'])
            self.assertEqual('reconcile_release',runtime.request['operation'])
            self.assertEqual('old',record['recovery_of_command_id'])
            self.assertEqual('failed_or_unknown',record['status'])
            self.assertFalse(record['explicit_recovery_terminal']['physical_home'])

    def test_no_quiescent_window_does_not_send_a_recovery_command(self):
        calls=[]
        class Runtime:
            _actor=object()
            def poll(self):return dict(phase='uncertain',held=True,command_id='old')
            def observe_actor(self,binding):return dict(frame=101,state_id=26,state_vtable=0xc553d0,
                command_source=1,stance=2,path=1,state_flags=0x10000,team=20,script_team=20,foreign_epoch=1,xyz=[0,0,0])
            def submit(self,request):raise AssertionError('No unverified recovery command')
            def stop(self):calls.append('stop');return None
            def close(self):calls.append('close')
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory)/'native.json';raw.write_text('{}');record=dict(status='failed_or_unknown')
            with patch.object(diagnostic.time,'monotonic',side_effect=[0,0,9]),patch.object(diagnostic.time,'sleep',return_value=None):
                diagnostic.cleanup_runtime(Runtime(),record,None,raw,Path(directory)/'trial.json')
            self.assertEqual(['stop','close'],calls)
            self.assertEqual([],record['recovery_quiescent_frames'])
            self.assertNotIn('explicit_recovery_request',record)
            self.assertEqual('ValueError',record['runtime_recovery_unknown'])

    def test_trace_overflow_still_requests_safety_stop_without_replaying_commands(self):
        calls = []

        class Runtime:
            def poll(self):
                calls.append('poll')
                raise ValueError('runtime_hook_trace_lost_or_regressed')

            def stop(self):
                calls.append('stop')
                return dict(control_released=True, physical_home=False)

            def close(self):
                calls.append('close')

            def submit(self, _):
                raise AssertionError('Never submit a command after lost evidence')

        record = dict(status='failed_or_unknown', reason_code='runtime_hook_trace_lost_or_regressed')
        diagnostic.cleanup_runtime(Runtime(), record, None, None, None)
        self.assertEqual(['poll', 'stop', 'close'], calls)
        self.assertEqual('ValueError', record['runtime_recovery_unknown'])
        self.assertEqual('failed_or_unknown', record['status'])
        self.assertEqual('runtime_hook_trace_lost_or_regressed', record['reason_code'])
        self.assertFalse(record['runtime_stop']['physical_home'])

    def test_failed_safety_stop_keeps_release_unknown_and_does_not_repeat_cleanup(self):
        calls = []

        class Runtime:
            def poll(self):
                raise ValueError('runtime_hook_trace_lost_or_regressed')

            def stop(self):
                calls.append('stop')
                raise TimeoutError('runtime_control_release_unknown')

            def close(self):
                raise AssertionError('Do not hide a failed stop with another attempt')

        record = dict(status='failed_or_unknown')
        diagnostic.cleanup_runtime(Runtime(), record, None, None, None)
        self.assertEqual(['stop'], calls)
        self.assertEqual('ValueError', record['runtime_recovery_unknown'])
        self.assertEqual('TimeoutError', record['runtime_release_unknown'])
        self.assertNotIn('runtime_stop', record)


if __name__ == '__main__':
    unittest.main()
