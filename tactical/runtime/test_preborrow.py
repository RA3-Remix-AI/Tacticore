"""Planning waits cannot borrow, replay a rejected Reserve, or reuse stale identity."""
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'integration'))
import preborrow

spec = importlib.util.spec_from_file_location('preborrow_diagnostic_driver', HERE / 'diagnose.py')
diagnose = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnose)


ACTOR = SimpleNamespace(object_id=55, thing=0x5000, owner=0x2000, update=0x6000,
                        type_hash=0x19ab11af, generation=1)
BINDING = SimpleNamespace(binding_hash='binding', host_id='host')


class Runtime:
    def __init__(self):
        self.frame = 0
        self.requests = []
        self.lease_deadline_frame = 750

    def admit(self, binding):
        self.frame += 1
        return SimpleNamespace(game_frame=self.frame, monotonic_ms=1000+self.frame)

    def poll(self):
        return dict(phase='idle')

    def observe_actor(self, binding):
        return dict(frame=self.frame, xyz=[0, 0, 0], object_id=55, generation=1, team=18, script_team=20,path=0,state_flags=0x10000,grounded=True,command_source=2,state_id=16,state_vtable=0xc55130,stance=0,foreign_epoch=0)

    def targets(self):
        return dict(endpoint=[40, 0, 0])

    def approved_target(self, point):
        return self.targets()[point]

    def submit(self, request):
        self.requests.append(request)
        # The scene can change after the planning read. Native rejection must
        # still prevail, without polling this into success or retrying.
        return dict(status='rejected', phase='idle', reason_code='private_home_ground_or_vacancy_unverified')


def census(frame, *, occupied=False, span=0):
    rows = [dict(object_id=55, address='0x5000', owner_address='0x2000', ai_address='0x6000',
                 type_hash='0x19ab11af', xyz=[0, 0, 0])]
    if occupied:
        rows.append(dict(object_id=798, type_hash='0x2c358c61', xyz=[0, 0, 0]))
    return dict(frame_start=frame, frame_end=frame+span, candidates=rows)


class PreborrowTests(unittest.TestCase):
    def window(self):
        return preborrow.HomeWindow(object(), 3, ACTOR)

    def test_captured_source0_idle_cannot_accumulate_a_lender_window(self):
        window,record,runtime=self.window(),{},Runtime()
        window.begin(record,require_stationary=True)
        results=[]
        for frame in range(1,8):
            runtime.frame=frame;native=runtime.observe_actor(BINDING)
            if frame<=4:native['command_source']=0
            with patch.object(preborrow,'own_candidates',return_value=census(frame)):
                results.append(window.observe(native))
        self.assertEqual([False,False,False,False,False,False,True],results)
        self.assertEqual('home_lender_state_unverified_wait',record['preborrow_home_wait']['observations'][0]['reason'])
        self.assertEqual([],runtime.requests)

    def test_waits_for_blocker_then_three_distinct_clear_frames_without_dispatch(self):
        runtime, record, window = Runtime(), {}, self.window()
        def read(*args):
            return census(runtime.frame, occupied=runtime.frame <= 2)
        with patch.object(preborrow, 'own_candidates', side_effect=read), patch.object(preborrow.time, 'sleep'):
            selected = preborrow.choose_target(runtime, BINDING, record, window)
        self.assertEqual('endpoint', selected)
        self.assertEqual(5, runtime.frame)
        self.assertEqual([], runtime.requests)
        self.assertEqual([0, 0, 1, 2, 3], [x['distinct_clear_frames'] for x in record['preborrow_home_wait']['observations']])
        self.assertFalse(record['preborrow_home_wait']['native_authority_granted'])
        self.assertFalse(record['preborrow_home_wait']['route_verified'])

    def test_release_receipt_waits_for_new_ambient_frame_then_three_clear_frames(self):
        runtime,record=Runtime(),{}
        runtime.frame=9
        runtime.poll=lambda:dict(phase='released',game_frame=10)
        original=runtime.observe_actor
        def observe(binding):
            result=original(binding)
            if runtime.frame==10:result['team']=result['script_team']
            return result
        runtime.observe_actor=observe
        with patch.object(preborrow,'own_candidates',side_effect=lambda *args:census(runtime.frame)),patch.object(preborrow.time,'sleep'):
            self.assertEqual('endpoint',preborrow.choose_target(runtime,BINDING,record,self.window()))
        self.assertEqual(13,runtime.frame)
        self.assertEqual([],runtime.requests)
        self.assertEqual([10],[x['native_frame'] for x in record['released_observation_wait']])
        self.assertEqual([1,2,3],[x['distinct_clear_frames'] for x in record['preborrow_home_wait']['observations']])

    def test_fresh_script_ownership_still_refuses_and_retains_rejected_fields(self):
        runtime,record=Runtime(),{}
        runtime.frame=10
        runtime.poll=lambda:dict(phase='released',game_frame=10)
        original=runtime.observe_actor
        def observe(binding):
            result=original(binding);result['team']=result['script_team'];return result
        runtime.observe_actor=observe
        with patch.object(preborrow,'own_candidates',side_effect=lambda *args:census(runtime.frame)):
            with self.assertRaisesRegex(ValueError,'identity_or_owner_changed'):
                preborrow.choose_target(runtime,BINDING,record,self.window())
        refused=record['preborrow_home_wait']['refused_identity_observation']
        self.assertEqual(11,refused['native_actor']['frame'])
        self.assertEqual(20,refused['native_actor']['team'])
        self.assertEqual([],runtime.requests)

    def test_same_frame_and_cross_frame_reads_cannot_accumulate_a_window(self):
        window, record, runtime = self.window(), {}, Runtime()
        window.begin(record)
        runtime.frame = 10
        with patch.object(preborrow, 'own_candidates', return_value=census(10)):
            for _ in range(20):
                self.assertFalse(window.observe(runtime.observe_actor(BINDING)))
        self.assertEqual(1, window.clear_frames)
        runtime.frame = 11
        with patch.object(preborrow, 'own_candidates', return_value=census(11, span=1)):
            self.assertFalse(window.observe(runtime.observe_actor(BINDING)))
        self.assertEqual(0, window.clear_frames)

    def test_moving_actor_position_lag_between_distinct_clocks_does_not_require_a_stop(self):
        window, record = self.window(), {}
        window.begin(record)
        results = []
        for frame in (10,11,12):
            own = census(frame)
            own['candidates'][0]['xyz'] = [3.3333*frame,0,0]
            native = dict(frame=frame-1,xyz=[3.3333*(frame-1),0,0],object_id=55,generation=1,team=18,script_team=20)
            with patch.object(preborrow,'own_candidates',return_value=own):
                results.append(window.observe(native))
        self.assertEqual([False,False,True],results)
        self.assertAlmostEqual(3.3333,record['preborrow_home_wait']['observations'][-1]['position_lag_xy'])
        self.assertFalse(record['preborrow_home_wait']['native_authority_granted'])

    def test_home_preparation_does_not_capture_a_factory_egress_position(self):
        window,record,runtime=self.window(),{},Runtime()
        window.begin(record,require_stationary=True)
        results=[]
        for frame in range(1,7):
            runtime.frame=frame
            native=runtime.observe_actor(BINDING);native['path']=0x1234 if frame<=3 else 0
            own=census(frame)
            if frame<=3:
                own['candidates'][0]['xyz']=[3.3*frame,0,0];native['xyz']=list(own['candidates'][0]['xyz'])
            with patch.object(preborrow,'own_candidates',return_value=own):results.append(window.observe(native))
        self.assertEqual([False,False,False,False,False,True],results)
        self.assertEqual('home_not_stationary_wait',record['preborrow_home_wait']['observations'][0]['reason'])

    def test_real_sampler_tuple_coordinates_accumulate_the_stationary_window(self):
        # own_candidates decodes xyz with struct.unpack, which returns tuple;
        # runtime JSON samples use list. Both describe the same coordinate.
        runtime,record=Runtime(),{}
        runtime.targets=lambda:{}
        def actual_shape(*args):
            value=census(runtime.frame);value['candidates'][0]['xyz']=(0.,0.,0.)
            return value
        with patch.object(preborrow,'own_candidates',side_effect=actual_shape),patch.object(preborrow.time,'sleep'):
            self.assertIsNone(preborrow.choose_target(runtime,BINDING,record,self.window(),home_first=True))
        self.assertEqual(3,runtime.frame)
        self.assertEqual([1,2,3],[x['distinct_clear_frames'] for x in record['preborrow_home_wait']['observations']])
        self.assertEqual([],runtime.requests)

    def test_bounded_wait_expires_without_any_reserve_or_lease(self):
        runtime, record = Runtime(), {}
        with patch.object(preborrow, 'own_candidates', side_effect=lambda *args:census(runtime.frame, occupied=True)), \
                patch.object(preborrow.time, 'monotonic', side_effect=[0, 0, .1, 31]), \
                patch.object(preborrow.time, 'sleep'):
            with self.assertRaisesRegex(preborrow.PlanningUnavailable, 'no_commands'):
                preborrow.choose_target(runtime, BINDING, record, self.window())
        self.assertEqual([], runtime.requests)
        self.assertFalse(any(x['ready_for_native_check'] for x in record['preborrow_home_wait']['observations']))
        self.assertEqual(record['planning_outcome']['status'],'not_dispatched')
        self.assertEqual(record['planning_outcome']['home_ready_frames'],0)
        self.assertGreater(record['planning_outcome']['endpoint_ready_frames'],0)
        self.assertFalse(record['planning_outcome']['control_acquired'])

    def test_home_first_prepares_without_inventing_a_target_or_dispatch(self):
        runtime,record=Runtime(),{}
        runtime.targets=lambda:{}
        with patch.object(preborrow,'own_candidates',side_effect=lambda *args:census(runtime.frame)),patch.object(preborrow.time,'sleep'):
            self.assertIsNone(preborrow.choose_target(runtime,BINDING,record,self.window(),home_first=True))
        self.assertEqual(3,runtime.frame)
        self.assertEqual([],runtime.requests)
        self.assertEqual('home_first_bounded_ready_wait',record['preparation_mode'])
        self.assertEqual(30,record['endpoint_wait_budget_seconds'])

    def test_home_first_native_refusal_is_final_without_a_target_or_move(self):
        runtime,record=Runtime(),{}
        runtime.targets=lambda:{}
        actor=SimpleNamespace(identity=SimpleNamespace(object_id=55,generation=1),born_frame=1)
        with tempfile.TemporaryDirectory() as directory,patch.object(preborrow,'own_candidates',side_effect=lambda *args:census(runtime.frame)),patch.object(preborrow.time,'sleep'):
            with self.assertRaisesRegex(ValueError,'command_refused_or_unknown'):
                diagnose.run_direct_trial(runtime,actor,BINDING,record,Path(directory)/'trial.json',home_window=self.window(),home_first_preparation=True)
        self.assertEqual(['reserve'],[x['operation'] for x in runtime.requests])
        self.assertIsNone(record['preborrow_target_point_id'])

    def test_missing_read_or_reused_actor_cannot_be_treated_as_clear(self):
        for side_effect in (RuntimeError('read unavailable'), None):
            runtime, record, window = Runtime(), {}, self.window()
            changed = census(1)
            changed['candidates'][0]['address'] = '0x9000'
            with patch.object(preborrow, 'own_candidates', side_effect=side_effect, return_value=copy.deepcopy(changed)):
                with self.assertRaises((RuntimeError, ValueError)):
                    preborrow.choose_target(runtime, BINDING, record, window)
            self.assertEqual([], runtime.requests)

    def test_native_rejection_after_clear_window_is_final_and_not_retried(self):
        runtime, record, window = Runtime(), {}, self.window()
        actor = SimpleNamespace(identity=SimpleNamespace(object_id=55, generation=1), born_frame=1)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(preborrow, 'own_candidates', side_effect=lambda *args:census(runtime.frame)), \
                patch.object(preborrow.time, 'sleep'):
            with self.assertRaisesRegex(ValueError, 'command_refused_or_unknown'):
                diagnose.run_direct_trial(runtime, actor, BINDING, record, Path(directory)/'trial.json', home_window=window)
        self.assertEqual(['reserve'], [x['operation'] for x in runtime.requests])
        self.assertEqual('rejected', record['runtime_commands'][0]['response']['status'])
        self.assertNotIn('native_terminal', record)

    def test_post_ready_selection_replaces_stale_preborrow_point_before_any_commit(self):
        runtime, record = Runtime(), {}
        runtime.poll = lambda:dict(phase='ready')
        runtime.observe_actor = lambda binding:dict(frame=20,xyz=[25,0,0],settled=True,stance=2,team=20,script_team=20)
        runtime.reserved_home = lambda task,lease:dict(xyz=[0,0,0],frame=3,event_ticket=1)
        runtime.targets = lambda:dict(fresh_endpoint=[100,0,0])
        self.assertEqual('fresh_endpoint', preborrow.choose_commit_target(runtime,BINDING,record,'task','lease','stale_endpoint'))
        self.assertTrue(record['post_ready_target_selection']['changed'])
        self.assertEqual([0,0,0],record['post_ready_target_selection']['reserve_home']['xyz'])
        self.assertEqual([],runtime.requests)
        # A point within range of the stopped actor can still be outside the
        # original home's allowed trial range. Do not substitute actor xyz.
        runtime.observe_actor = lambda binding:dict(frame=20,xyz=[60,0,0],settled=True,stance=2,team=20,script_team=20)
        runtime.targets = lambda:dict(outside_home=[140,0,0])
        with patch.object(preborrow.time,'monotonic',side_effect=[0,0,9]), patch.object(preborrow.time,'sleep'):
            with self.assertRaisesRegex(ValueError,'no_commit'):
                preborrow.choose_commit_target(runtime,BINDING,record,'task','lease','stale_endpoint')
        self.assertEqual([],runtime.requests)

    def test_post_ready_wait_observes_vacancy_without_commands_or_lease_extension(self):
        runtime,record=Runtime(),{}
        runtime.frame=100
        def poll():runtime.frame+=1;return dict(phase='ready')
        runtime.poll=poll
        runtime.observe_actor=lambda binding:dict(frame=runtime.frame,xyz=[0,0,0],settled=True,stance=2,team=20,script_team=20)
        runtime.reserved_home=lambda task,lease:dict(xyz=[0,0,0],frame=90,event_ticket=1)
        runtime.targets=lambda:{} if runtime.frame<103 else dict(vacated=[60,0,0])
        with patch.object(preborrow.time,'sleep'):
            self.assertEqual('vacated',preborrow.choose_commit_target(runtime,BINDING,record,'task','lease',None))
        self.assertEqual(3,len(record['post_ready_target_selection']['observations']))
        self.assertEqual(750,runtime.lease_deadline_frame)
        self.assertEqual([],runtime.requests)
        # An almost expired lease must preserve the return margin rather than
        # borrowing more time or submitting an immediately available target.
        runtime.lease_deadline_frame=220
        with self.assertRaisesRegex(ValueError,'no_commit'):
            preborrow.choose_commit_target(runtime,BINDING,record,'task','lease','old')
        self.assertEqual([],runtime.requests)


if __name__ == '__main__':
    unittest.main()
