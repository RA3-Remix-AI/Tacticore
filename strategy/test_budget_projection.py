"""Economic/technology advice cannot silently fund military production."""
import unittest
import uuid

from battle_agent import BattleAgent, BuildEvidence
from engine import Snapshot, StrategyEngine, validate_policy
import fixtures


class ProjectionTests(unittest.IsolatedAsyncioTestCase):
    def plans(self):
        binding=fixtures.binding();snapshot=Snapshot.from_dict(fixtures.snapshot());context=snapshot.model_context(binding)
        first=fixtures.policy(context,production_focus='balanced',economy_policy='expand_if_defensible',
                              tech_policy='advance_if_affordable',budget={'economy':.6,'army':.1,'tech':.1,'reserve':.2})
        second=fixtures.policy(context,production_focus='balanced',economy_policy='stabilize',
                               tech_policy='hold_current_tier',budget={'economy':.1,'army':.6,'tech':.1,'reserve':.2})
        return [validate_policy(raw,snapshot,snapshot,binding,20) for raw in (first,second)]

    def test_valid_plan_budget_splits_no_longer_collapse_to_same_build_allowance(self):
        first,second=self.plans()
        one=next(request for request in BattleAgent._requests(None,first) if request.module=='build')
        two=next(request for request in BattleAgent._requests(None,second) if request.module=='build')
        self.assertEqual(one.spend_fraction,.1)
        self.assertEqual(two.spend_fraction,.6)
        self.assertNotEqual(one,two)

    async def test_actual_agent_jobs_and_memory_expose_unallocated_macro_budget(self):
        evidence=BuildEvidence(str(uuid.uuid4()),fixtures.SESSION,3,'simulated')
        agent=BattleAgent(StrategyEngine(fixtures.binding()),build_evidence=evidence)
        async def model(context):
            return fixtures.policy(context,production_focus='balanced',economy_policy='expand_if_defensible',
                                   tech_policy='advance_if_affordable',budget={'economy':.6,'army':.1,'tech':.1,'reserve':.2})
        await agent.decide(fixtures.snapshot(),model)
        build=next(task for task in agent.goals.tasks if task.request.module=='build')
        self.assertEqual(build.request.spend_fraction,.1)
        projection=agent._intent()['execution_projection']
        self.assertEqual(projection['unallocated_budget'],{'economy':.6,'tech':.1})
        self.assertEqual(projection['policy_support']['economy_policy'],'advisory_no_economic_actuator')
        self.assertEqual(projection['control_mode'],'native_assist')


if __name__=='__main__':unittest.main()
