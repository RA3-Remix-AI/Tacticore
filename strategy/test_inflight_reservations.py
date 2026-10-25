"""An acknowledged lease reserves first, regardless of refreshed plan order."""
from dataclasses import replace
import unittest
import uuid

from battle_agent import TaskCoordinator,TaskRequest,TacticalEvidence
from engine import StrategyEngine
from fixtures import binding,SESSION


class InflightReservations(unittest.TestCase):
    def fixture(self):
        proof=TacticalEvidence(str(uuid.uuid4()),SESSION,3,'simulated',(('attack',('main_attack',)),('raid',('recon',))))
        board=TaskCoordinator(StrategyEngine(binding()),tactical_evidence=proof)
        old=TaskRequest('attack','main_attack','enemy_front',None,0,.5,('main_force',),10,'contact_ore',('formation_main',),(('formation_main',1),),('infantry',))
        board.reconcile([old],100,('enemy_front',),1,1,'simulated','p1',145)
        task=board.tasks[0];task.status='dispatch_pending'
        return board,old,task

    def apply(self,board,requests,cap=1):
        return board.reconcile(requests,110,('enemy_front',),cap,cap,'simulated','p2',155)

    def candidate(self,old,**kw):
        return replace(old,module='raid',purpose='recon',target_contact_id=None,priority=90,resource_locks=('raid_force',),**kw)

    def test_repeated_lease_cannot_be_preempted_by_high_priority_same_formation(self):
        board,old,task=self.fixture()
        for state in ('dispatch_pending','active'):
            task.status=state
            result=self.apply(board,[old,self.candidate(old)])
            raid=next(t for t in result if t.request.module=='raid')
            self.assertEqual((raid.status,raid.reason_code),('blocked','formation_conflict'))
            self.assertIs(next(t for t in result if t.task_id==task.task_id),task)
            self.assertEqual(task.status,state)

    def test_repeated_lease_budget_reserved_before_other_roster(self):
        board,old,task=self.fixture()
        new=self.candidate(old,formation_ids=('formation_other',),formation_versions=(('formation_other',1),),force_fraction=.6)
        raid=next(t for t in self.apply(board,[old,new]) if t.request.module=='raid')
        self.assertEqual((raid.status,raid.reason_code),('blocked','budget_conflict'))

    def test_repeated_lease_is_not_charged_twice(self):
        board,old,task=self.fixture()
        new=self.candidate(old,formation_ids=('formation_other',),formation_versions=(('formation_other',1),))
        result=self.apply(board,[old,new])
        self.assertEqual(next(t for t in result if t.request.module=='raid').status,'planned')
        self.assertEqual(sum(t.request.force_fraction for t in result if t.status!='blocked'),1)
        self.assertEqual(task.plan_id,'p1')

    def test_omitting_lease_still_keeps_reservation(self):
        board,old,task=self.fixture()
        raid=next(t for t in self.apply(board,[self.candidate(old)]) if t.request.module=='raid')
        self.assertEqual((raid.status,raid.reason_code),('blocked','formation_conflict'))
        self.assertIn(task,board.tasks)


if __name__=='__main__':unittest.main()
