"""Explicit scoped quota/prompt and urgent epoch tests; no provider/game I/O."""
import asyncio
import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest
import uuid
from battle_agent import BattleAgent,TacticalEvidence
from engine import ContractError,StrategyEngine,validate_policy
from fixtures import binding,COMMANDER,CONNECTION,SESSION
from http_adapter import Endpoint,Profile,system_prompt,tactical_example,prebound_pair_versions
from tactical_fixtures import tactical_snapshot,tactical_policy,intent

class PaidPair(unittest.IsolatedAsyncioTestCase):
    def make(self):
        raw=tactical_snapshot();raw['battlefield']['formations']=[dict(raw['battlefield']['formations'][0],roles={'infantry':1,'anti_air':1})]
        evidence=TacticalEvidence(str(uuid.uuid4()),SESSION,3,'simulated',(('combined_arms',('coordinate_force',)),('attack',('main_attack',))), (('combined_arms','coordinate_force',('infantry','anti_air')),('attack','main_attack',('infantry',))))
        agent=BattleAgent(StrategyEngine(binding()),tactical_evidence=evidence);agent.observe(raw);return agent,raw
    def task(self,**changes):return intent('combined_arms','coordinate_force',required_roles=['infantry','anti_air'],force_fraction=1,**changes)
    async def test_pair_fraction_one_has_independent_quota_at_all_three_strategy_gates(self):
        agent,raw=self.make();agent.set_prebound_paid_pairs({'formation_main':1})
        async def model(context):return tactical_policy(context,[self.task()])
        result=await agent.decide(raw,model);self.assertEqual(result.status,'accepted')
        job=next(j for j in agent.jobs()['jobs'] if j['module']=='combined_arms')
        self.assertTrue(job['host_dispatch_candidate']);self.assertEqual(job['force_fraction'],1)
        self.assertLess(1-dict(agent.engine.current.budget)['reserve'],1)
        context=agent.context(agent.latest.model_context(binding()))
        scope=context['capability_manifest']['combined_arms']['purpose_allocation_scopes']['coordinate_force'];self.assertEqual(scope['scope'],'prebound_paid_pair');self.assertEqual(scope['request_force_fraction'],1)
    async def test_same_pair_without_trusted_scope_does_not_bypass_old_budget(self):
        agent,raw=self.make()
        async def model(context):return tactical_policy(context,[self.task()])
        result=await agent.decide(raw,model);self.assertEqual(result.status,'local_fallback');self.assertEqual(agent.engine.metrics['accepted'],0)
    async def test_trusted_pair_cannot_be_used_for_old_single_actor_purpose(self):
        agent,raw=self.make();agent.set_prebound_paid_pairs({'formation_main':1})
        async def model(context):return tactical_policy(context,[intent(force_fraction=.5)])
        result=await agent.decide(raw,model);self.assertNotEqual(result.status,'accepted')
    async def test_only_exact_formation_version_and_fraction_one_are_exempt(self):
        for versions,force in (({'formation_other':1},1),({'formation_main':2},1),({'formation_main':1},.5)):
            agent,raw=self.make();agent.set_prebound_paid_pairs(versions)
            async def model(context):return tactical_policy(context,[dict(self.task(),force_fraction=force)])
            with self.subTest(versions=versions,force=force):self.assertNotEqual((await agent.decide(raw,model)).status,'accepted')
    async def test_prompt_example_uses_two_actual_paid_roles_without_free_n4(self):
        agent,raw=self.make();agent.set_prebound_paid_pairs({'formation_main':1});context=agent.context(agent.latest.model_context(binding()))
        example=tactical_example(context);self.assertEqual(len(example),1);self.assertEqual(example[0]['module'],'combined_arms');self.assertEqual(example[0]['force_fraction'],1)
        profile=Profile(COMMANDER,'mock',CONNECTION,'自定义','fixture-model',0,'',Endpoint.parse('http://localhost:1'),'')
        prompt=system_prompt(profile,context);self.assertIn('prebound_paid_pair',prompt);self.assertIn('separate paid-pair quota',prompt);self.assertIn('Never assign that held pair to attack, raid',prompt)
        # Actual new Pydantic assembly imports this same system_prompt function.
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'agent_runtime/src'))
        from tacticore_agent_runtime.factory import create_backend
        backend=create_backend(profile);self.assertEqual(backend.backend_name,'pydantic');self.assertEqual(backend._prompt(context),prompt)
    async def test_scope_wrong_purpose_version_or_absent_true_pair_never_invents_example(self):
        agent,raw=self.make();agent.set_prebound_paid_pairs({'formation_main':1});context=agent.context(agent.latest.model_context(binding()))
        for mutate in ('purpose','version','unavailable','role'):
            current=copy.deepcopy(context)
            if mutate=='purpose':current['capability_manifest']['combined_arms']['verified_purposes']=[]
            elif mutate=='version':current['working_memory']['battlefield']['formations'][0]['version']=2
            elif mutate=='unavailable':current['working_memory']['battlefield']['formations'][0]['available']=False
            else:current['working_memory']['battlefield']['formations'][0]['roles']={'infantry':2}
            with self.subTest(mutate=mutate):self.assertEqual(prebound_pair_versions(current),{})
    async def test_one_urgent_epoch_bypasses_two_and_fifteen_second_hold_once(self):
        agent,raw=self.make();calls=[]
        async def model(context):calls.append(context['snapshot_id']);return tactical_policy(context,[])
        self.assertEqual((await agent.decide(raw,model)).status,'accepted')
        later=tactical_snapshot(2,101);self.assertEqual((await agent.decide(later,model)).status,'held')
        self.assertTrue(agent.engine.request_urgent_capability('verified-controller-ready'))
        self.assertEqual((await agent.decide(later,model)).status,'accepted');self.assertEqual(calls,[1,2])
        self.assertFalse(agent.engine.request_urgent_capability('verified-controller-ready'))
        self.assertEqual((await agent.decide(tactical_snapshot(3,102),model)).status,'held')
    async def test_obsolete_transport_is_cancelled_and_drained_before_urgent_request(self):
        agent,raw=self.make();started=asyncio.Event();cancelled=asyncio.Event();active=0
        async def slow(context):
            nonlocal active
            active+=1;started.set()
            try:await asyncio.Event().wait()
            finally:active-=1;cancelled.set()
        old=asyncio.create_task(agent.decide(raw,slow));await started.wait();old.cancel();await asyncio.gather(old,return_exceptions=True);await agent.engine.drain_obsolete_request()
        self.assertTrue(cancelled.is_set());self.assertEqual(active,0)
        agent.engine.request_urgent_capability('new-real-ready-epoch')
        async def next_model(context):self.assertEqual(active,0);return tactical_policy(context,[])
        self.assertEqual((await agent.decide(tactical_snapshot(2,101),next_model)).status,'accepted')

if __name__=='__main__':unittest.main()
