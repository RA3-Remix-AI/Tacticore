"""Two-phase formation task admission; all memory/queue boundaries are fake."""
import tempfile
import unittest
from unittest.mock import MagicMock,patch
import test_client as boundary

m=boundary.m


class HeldPlanningClient(unittest.TestCase):
    def setup_case(self,folder):
        base=boundary.ModelBoundary();e=base.executor();task=base.task()
        task.update(module='combined_arms',purpose='coordinate_force',required_roles=['infantry','anti_air'],expires_frame=5500)
        e.capability_grants[('combined_arms','coordinate_force')]=dict(executor_directory='mission-formation-v4',stop_schema=dict(mission_protocol='continuous_tactical_v1',mission_duration_frames=4500))
        e.regions['region']['xyz']=[1000.,0.,210.]
        e.mission_context=dict(schema_version=1,formation_history_dir=folder,route=[{'xyz':[999,999,999]}])
        e._surface_ground_candidates=MagicMock(side_effect=lambda memory,units,owner,name:units)
        e._role_route_pair=MagicMock(side_effect=AssertionError('Parent must not preplan a moving pair'))
        pre=base.preflight();pre.update(frame=1000,logic='0x1000')
        for u in pre['units']:u['hp']=100.
        pre['units'] += [dict(address='0x30000',object_id=3,eligible=True,type_hash='0x19ab11af',xyz=[50.,0.,210.],hp=100.),dict(address='0x40000',object_id=4,eligible=True,type_hash='0x2c358c61',xyz=[-80.,0.,210.],hp=120.)]
        captured=[]
        def queue(**kwargs):
            captured.append(kwargs)
            receipt=dict(command_id=kwargs['command_id'],task_id=kwargs['task_id'],seq=kwargs['seq'],status='queued',accepted=True,started=False,completed=False,object_ids=[kwargs['front_id'],kwargs['support_id']],mission_input=kwargs['mission_input'])
            e.ledger[kwargs['command_id']]=receipt
            return dict(receipt)
        e.submit_formation_probe=queue
        return e,task,pre,captured

    def submit(self,e,task,pre):
        with patch.object(m.backend,'readiness',return_value=(pre,None,None,None,None,None,boundary.Memory())),patch.object(m,'mobility_status',return_value={'independently_movable':True}):
            return e.submit(task)

    def test_no_route_until_native_has_proven_stopped_positions(self):
        with tempfile.TemporaryDirectory() as folder:
            e,task,pre,captured=self.setup_case(folder);result=self.submit(e,task,pre)
        self.assertTrue(result['accepted'],result);self.assertFalse(result['started'])
        self.assertNotIn('route',captured[0]['mission_input']);self.assertEqual(captured[0]['mission_input']['formation_history_dir'],folder)
        self.assertEqual(result['object_ids'],[1,2]);e._role_route_pair.assert_not_called()
        self.assertEqual(e._surface_ground_candidates.call_args.args[-1],'mission_actor_admission_v2.py')

    def test_missing_history_never_queues_or_borrows_actors(self):
        with tempfile.TemporaryDirectory() as folder:
            e,task,pre,captured=self.setup_case(folder);e.mission_context.pop('formation_history_dir')
            result=self.submit(e,task,pre)
        self.assertFalse(result['accepted']);self.assertTrue(result['no_dispatch_verified']);self.assertFalse(captured)

    def test_pair_facing_target_is_preferred_without_preplanning(self):
        with tempfile.TemporaryDirectory() as folder:
            e,task,pre,captured=self.setup_case(folder)
            e.formations['f']['object_ids']=[1,2,3,4];pre['units'][1]['xyz']=[80.,0.,210.]
            result=self.submit(e,task,pre)
        self.assertTrue(result['accepted'],result);self.assertEqual(result['object_ids'],[3,4])
        e._role_route_pair.assert_not_called()

    def test_unverified_actor_surface_never_becomes_a_planning_lease(self):
        with tempfile.TemporaryDirectory() as folder:
            e,task,pre,captured=self.setup_case(folder);e._surface_ground_candidates.return_value=[];e._surface_ground_candidates.side_effect=None
            result=self.submit(e,task,pre)
        self.assertFalse(result['accepted']);self.assertFalse(captured)


if __name__=='__main__':unittest.main()
