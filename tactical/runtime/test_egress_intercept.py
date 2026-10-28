"""A preparation hint cannot invent endpoints or override native readiness."""
from types import SimpleNamespace
import unittest
from egress_intercept import select_egress_target


ACTOR=SimpleNamespace(object_id=55,thing=0x5000,update=0x6000,owner=0x7000,type_hash=0x19ab11af)


class Runtime:
    def __init__(self):self.phase='ready';self.points=dict(egress=[40,0,0],away=[0,40,0])
    def poll(self):return dict(phase=self.phase)
    def observe_actor(self,binding):return dict(frame=20,settled=True,team=2,script_team=2,xyz=[0,0,0])
    def targets(self):return self.points
    def submit(self,request):raise AssertionError('Ranking never submits a command')


def record():
    samples=[]
    for frame,x in [(1,70),(6,50),(11,30),(16,0)]:
        actor=dict(object_id=55,address='0x5000',ai_address='0x6000',owner_address='0x7000',type_hash='0x19ab11af',xyz=[x,0,0])
        samples.append(dict(stage='selecting_before_borrow',census=dict(frame_start=frame,frame_end=frame,candidates=[
            actor,dict(object_id=7,type_hash='0x80d4ea1e',xyz=[100,0,0])])) )
    return dict(own_environment=dict(samples=samples),post_ready_target_selection=dict(reserve_home=dict(xyz=[0,0,0]),
        candidates=[dict(point_id='egress',xyz=[40,0,0]),dict(point_id='away',xyz=[0,40,0])]))


class EgressInterceptTests(unittest.TestCase):
    def test_observed_egress_ranks_only_current_admitted_points(self):
        r=record();self.assertEqual('egress',select_egress_target(Runtime(),None,r,ACTOR,'away'))
        self.assertFalse(r['egress_intercept_selection']['history_is_route_authority'])
        self.assertEqual(0,r['egress_intercept_selection']['candidates'][0]['cross_track_distance'])

    def test_an_unavailable_historical_point_cannot_become_a_target(self):
        runtime=Runtime();runtime.points.pop('egress')
        with self.assertRaisesRegex(ValueError,'no_supported_native_point_no_commit'):
            select_egress_target(runtime,None,record(),ACTOR,'away')

    def test_identity_mismatch_or_cross_frame_history_refuses_preparation(self):
        for mismatch in [True,False]:
            r=record()
            for sample in r['own_environment']['samples']:
                if mismatch:sample['census']['candidates'][0]['owner_address']='0x8000'
                else:sample['census']['frame_end']+=1
            with self.assertRaises(ValueError):select_egress_target(Runtime(),None,r,ACTOR,'away')

    def test_lost_native_ready_cannot_be_ranked_into_permission(self):
        runtime=Runtime();runtime.phase='uncertain'
        with self.assertRaisesRegex(ValueError,'current_native_ready'):
            select_egress_target(runtime,None,record(),ACTOR,'away')

    def test_observed_cell_corner_is_retained_without_a_euclidean_radius_substitute(self):
        runtime=Runtime();runtime.points=dict(corner=[50,50,0]);r=record()
        r['post_ready_target_selection']=dict(reserve_home=dict(xyz=[50,10,0]),
            candidates=[dict(point_id='corner',xyz=[50,50,0])])
        r['preborrow_home_wait']=dict(observations=[dict(frame_start=1,frame_end=1,actor_xyz=[58.494,43.371,0]),
            dict(frame_start=2,frame_end=2,actor_xyz=[50,10,0])])
        self.assertEqual('corner',select_egress_target(runtime,None,r,ACTOR,'corner'))
        chosen=r['egress_intercept_selection']['candidates'][0]
        self.assertTrue(chosen['observed_cell_match'])
        self.assertEqual([2,2],chosen['center_cell'])


if __name__=='__main__':unittest.main()
