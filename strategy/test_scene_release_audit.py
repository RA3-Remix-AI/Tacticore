"""Release-only scene certificate cannot be substituted for tactical effects."""
import copy
from types import SimpleNamespace
import unittest

from mission_audit import scene_release_facts


class SceneAudit(unittest.TestCase):
    def fixture(self):
        sha='a'*64
        entry=dict(task_id='task',scene_release_evidence_sha256=sha)
        receipt=dict(status='failed',restoration_verified=False)
        events=[dict(kind='mission_scene_closed_control_release',task_id='task',evidence_sha256=sha,restoration_verified=False,return_verified=False,goal_observed=False)]
        memory=dict(missions=dict(recent_history=[dict(task_id='task',terminal_status='failed',phase='engage',last_evidence_sha256=sha,observations=dict(scene_closed_verified=True,restoration_verified=False))]))
        bridge=SimpleNamespace(verify_scene_release=lambda r,e:dict(sidecar_sha256=sha,source_sha256='b'*64))
        return bridge,receipt,entry,events,memory

    def test_independent_proof_and_both_certificates_release_only(self):
        result=scene_release_facts(*self.fixture())
        self.assertTrue(result['verified']);self.assertTrue(result['scene_closed_verified'])
        self.assertEqual(result['kind'],'verified_scene_closed_not_return')
        for field in ('restoration_verified','return_verified','physical_retreat_verified','completed'):self.assertIs(result[field],False)

    def test_missing_wrong_or_completion_claiming_certificates_fail(self):
        for change in ('ledger','event','event_hash','duplicate_event','return','goal','history','history_hash','history_success','history_restore'):
            args=list(self.fixture());entry,events,memory=args[2:];history=memory['missions']['recent_history']
            if change=='ledger':entry['scene_release_evidence_sha256']='c'*64
            elif change=='event':events.clear()
            elif change=='event_hash':events[0]['evidence_sha256']='c'*64
            elif change=='duplicate_event':events.append(copy.deepcopy(events[0]))
            elif change=='return':events[0]['return_verified']=True
            elif change=='goal':events[0]['goal_observed']=True
            elif change=='history':history.clear()
            elif change=='history_hash':history[0]['last_evidence_sha256']='c'*64
            elif change=='history_success':history[0]['terminal_status']='completed'
            else:history[0]['observations']['restoration_verified']=True
            with self.assertRaises(ValueError,msg=change):scene_release_facts(*args)

    def test_cached_flag_never_replaces_independent_verifier(self):
        args=list(self.fixture());args[1]['scene_disposed_control_release_verified']=True
        def reject(*_):raise ValueError('raw_scene_proof_invalid')
        args[0].verify_scene_release=reject
        with self.assertRaisesRegex(ValueError,'raw_scene_proof_invalid'):scene_release_facts(*args)
        args[0].verify_scene_release=lambda *_:None
        self.assertIsNone(scene_release_facts(*args))


if __name__=='__main__':unittest.main()
