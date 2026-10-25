"""Trusted scene closure is exclusive-control release, never native return."""
import copy
import unittest

from engine import ContractError
import test_missions as fixtures


class SceneClosedMissions(unittest.IsolatedAsyncioTestCase):
    async def create(self,*,started=True,progress=True):
        self.f=fixtures.Missions()
        agent,task=await self.f.create()
        self.f.commit(agent,task)
        if started:agent.record_feedback(self.f.feedback(agent,task,'started'))
        if progress:
            raw=self.f.progress(agent,task,'engage',1,105,5)
            self.f.observe_progress(agent,task,raw,approach_verified=True,source_damage_amount=5)
        return agent,task

    async def test_certificate_preserves_actual_phase_damage_and_native_revision(self):
        agent,task=await self.create();mission=agent.missions.active[task.task_id]
        native=copy.deepcopy(mission.native_progress);last=mission.last_progress
        self.assertTrue(agent.certify_mission_scene_closed(task.task_id,evidence_sha256=fixtures.SHA))
        self.assertEqual((mission.phase,mission.progress_seq),('engage',1))
        self.assertEqual(mission.native_progress,native);self.assertEqual(mission.last_progress,last)
        self.assertEqual(mission.observations.source_damage_amount,5)
        self.assertTrue(mission.observations.scene_closed_verified)
        for field in ('restoration_verified','retreat_verified','no_dispatch_verified','disposed_verified','target_currently_visible'):
            self.assertIs(getattr(mission.observations,field),False)
        self.assertTrue(agent.missions.context()['active'][0]['scene_closed_verified'])

    async def test_only_failed_or_cancelled_with_false_return_and_goal_can_close(self):
        for status in ('failed','cancelled'):
            agent,task=await self.create()
            agent.certify_mission_scene_closed(task.task_id,evidence_sha256=fixtures.SHA)
            for bad,restored,goal in [('completed',True,True),('blocked',False,False),('failed',True,False),('failed',False,True)]:
                with self.assertRaisesRegex(ContractError,'mission_scene_closure_is_not_completion'):
                    agent.record_feedback(self.f.feedback(agent,task,bad,restored=restored,goal=goal))
            agent.record_feedback(self.f.feedback(agent,task,status))
            self.assertEqual(agent.missions.active,{})
            history=agent.missions.history[-1]
            self.assertEqual((history['phase'],history['progress_seq'],history['terminal_status']),('engage',1,status))
            self.assertFalse(history['observations']['restoration_verified'])
            self.assertTrue(history['observations']['scene_closed_verified'])
            self.assertEqual(agent.missions.coverage['raid']['completed'],0)
            self.assertTrue(agent.goals.quarantined_formations)
            self.assertFalse(agent.feedback[-1]['execution']['restoration_verified'])
            self.assertEqual(agent.missions.context()['recent_scene_closures'][0]['verified_source_damage'],5)

    async def test_unknown_uncommitted_and_invalid_sha_are_rejected(self):
        agent,task=await self.fresh_uncommitted()
        with self.assertRaisesRegex(ContractError,'mission_scene_closed_lifecycle'):
            agent.certify_mission_scene_closed(task.task_id,evidence_sha256=fixtures.SHA)
        self.f.commit(agent,task)
        for sha in ('bad','A'*64,None):
            with self.assertRaisesRegex(ContractError,'mission_progress_evidence'):
                agent.certify_mission_scene_closed(task.task_id,evidence_sha256=sha)
        with self.assertRaisesRegex(ContractError,'mission_scene_closed_lifecycle'):
            agent.certify_mission_scene_closed('foreign-task',evidence_sha256=fixtures.SHA)
        self.assertIsNone(agent.missions.active[task.task_id].observations)

    async def fresh_uncommitted(self):
        self.f=fixtures.Missions()
        return await self.f.create()

    async def test_certificate_is_idempotent_and_ordinary_telemetry_cannot_assert_it(self):
        agent,task=await self.create(progress=False)
        raw=self.f.progress(agent,task,'approach',1,101)
        with self.assertRaisesRegex(ContractError,'mission_scene_closure_requires_certificate'):
            self.f.observe_progress(agent,task,raw,scene_closed_verified=True)
        self.assertTrue(agent.certify_mission_scene_closed(task.task_id,evidence_sha256=fixtures.SHA))
        self.assertFalse(agent.certify_mission_scene_closed(task.task_id,evidence_sha256=fixtures.SHA))
        with self.assertRaisesRegex(ContractError,'mission_scene_closed_certificate_changed'):
            agent.certify_mission_scene_closed(task.task_id,evidence_sha256='b'*64)
        with self.assertRaisesRegex(ContractError,'mission_scene_closed_lifecycle'):
            self.f.observe_progress(agent,task,raw)

    async def test_first_poll_after_scene_termination_invents_no_native_telemetry(self):
        agent,task=await self.create(started=False,progress=False)
        agent.certify_mission_scene_closed(task.task_id,evidence_sha256=fixtures.SHA)
        mission=agent.missions.active[task.task_id]
        self.assertEqual((mission.phase,mission.progress_seq),('reserved',0))
        self.assertIsNone(mission.native_progress);self.assertIsNone(mission.last_progress)
        agent.record_feedback(self.f.feedback(agent,task,'failed'))
        self.assertEqual(agent.missions.history[-1]['phase'],'reserved')
        self.assertFalse(agent.missions.history[-1]['observations']['restoration_verified'])

    async def test_scene_certificate_cannot_replace_no_dispatch_or_disposal(self):
        for kind in ('not_dispatched','disposed'):
            agent,task=await self.create(started=False,progress=False)
            getattr(agent,'certify_mission_'+kind)(task.task_id,evidence_sha256=fixtures.SHA)
            with self.assertRaisesRegex(ContractError,'mission_scene_closed_lifecycle'):
                agent.certify_mission_scene_closed(task.task_id,evidence_sha256=fixtures.SHA)

    async def test_stop_or_replan_after_scene_closure_cannot_request_native_retreat(self):
        agent,task=await self.create()
        agent.request_mission_retreat(task.task_id,'low_hp')
        self.assertTrue(agent.pending_mission_retreats())
        agent.certify_mission_scene_closed(task.task_id,evidence_sha256=fixtures.SHA)
        self.assertEqual(agent.pending_mission_retreats(),[])
        self.assertFalse(agent.missions.request_retreat(task.task_id,'deadline'))
        agent.stop()
        self.assertEqual(agent.missions.active,{})
        history=agent.missions.history[-1]
        self.assertEqual((history['phase'],history['terminal_status']),('engage','cancelled'))
        self.assertFalse(history['observations']['restoration_verified'])
        self.assertTrue(agent.goals.quarantined_formations)

    async def test_context_is_bounded_and_tolerates_old_unobserved_history(self):
        agent,task=await self.create()
        agent.certify_mission_scene_closed(task.task_id,evidence_sha256=fixtures.SHA)
        agent.record_feedback(self.f.feedback(agent,task,'failed'))
        history=agent.missions.history[-1]
        for _ in range(4):agent.missions.history.append(copy.deepcopy(history))
        agent.missions.history.append(dict(observations=None))
        self.assertEqual(len(agent.missions.context()['recent_scene_closures']),3)


if __name__=='__main__':unittest.main()
