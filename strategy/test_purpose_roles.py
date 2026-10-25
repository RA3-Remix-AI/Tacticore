"""Purpose-scoped actor constraints, using synthetic observations only."""
import copy
from dataclasses import replace
import unittest
import uuid

from battle_agent import BattleAgent,TacticalEvidence,TaskCoordinator
from engine import ContractError,StrategyEngine
from fixtures import binding,SESSION
from http_adapter import tactical_example
from tactical_fixtures import tactical_snapshot,tactical_policy,intent


class PurposeRoles(unittest.IsolatedAsyncioTestCase):
    def evidence(self,purposes=(("raid",("recon",)),),roles=(("raid","recon",("air",)),)):
        return TacticalEvidence(str(uuid.uuid4()),SESSION,3,"simulated",purposes,roles)

    def raw(self,roles=None):
        raw=tactical_snapshot()
        if roles is not None:raw['battlefield']['formations'][0]['roles']=roles
        return raw

    def agent(self,evidence=None):return BattleAgent(StrategyEngine(binding()),tactical_evidence=evidence or self.evidence())

    async def decide(self,agent,raw,task):
        async def model(context):return tactical_policy(context,[task])
        return await agent.decide(raw,model)

    def test_manifest_is_exact_purpose_scoped_and_does_not_grant_others(self):
        proof=self.evidence((("raid",("recon","harass_economy")),),(("raid","recon",("air",)),("raid","harass_economy",("infantry","anti_air"))))
        agent=self.agent(proof);manifest=agent.goals.capability_manifest('simulated')
        self.assertEqual(manifest['raid']['purpose_actor_roles'],{'recon':['air'],'harass_economy':['infantry','anti_air']})
        self.assertNotIn('purpose_actor_roles',manifest['attack']);self.assertEqual(manifest['attack']['state'],'unavailable')
        self.assertNotIn('purpose_actor_roles',agent.goals.capability_manifest('game_bridge')['raid'])

    def test_malformed_or_ungranted_host_role_constraints_are_rejected(self):
        for roles in [[('raid','recon',('air',))],(('raid','recon',()),),(('raid','recon',('air','air')),),(('raid','recon',('unknown',)),),(('raid','harass_economy',('infantry',)),),(('raid','recon',('air',)),('raid','recon',('infantry',))),(('raid','recon',['air']),),(('raid','recon',('air',),False),)]:
            with self.subTest(roles=roles),self.assertRaisesRegex(ContractError,'tactical_evidence_actor_roles'):self.agent(self.evidence(roles=roles))

    async def test_air_recon_rejects_missing_or_ungranted_requested_role(self):
        for roles,required in [({'infantry':4},['infantry']),({'air':1},['infantry'])]:
            agent=self.agent();result=await self.decide(agent,self.raw(roles),intent('raid','recon',target_contact_id=None,required_roles=required))
            with self.subTest(roles=roles,required=required):
                self.assertNotEqual(result.status,'accepted');self.assertEqual(agent.engine.metrics['accepted'],0)
                self.assertFalse(any(j['host_dispatch_candidate'] for j in agent.jobs()['jobs'] if j['module']=='raid'))

    async def test_air_recon_accepted_only_with_explicit_air_evidence(self):
        agent=self.agent();result=await self.decide(agent,self.raw({'air':2}),intent('raid','recon',target_contact_id=None,required_roles=['air']))
        self.assertEqual(result.status,'accepted');job=next(j for j in agent.jobs()['jobs'] if j['module']=='raid');self.assertTrue(job['host_dispatch_candidate'])
        self.assertEqual(job['required_roles'],('air',));self.assertFalse(agent.jobs()['execution_authorized'])

    async def test_ground_attack_and_harass_reject_ungranted_or_absent_requested_role(self):
        for module,purpose in [('attack','main_attack'),('raid','harass_economy')]:
            proof=self.evidence(((module,(purpose,)),),((module,purpose,('infantry','anti_air')),))
            for actors,required in [({'air':2},['air']),({'air':2},['infantry'])]:
                agent=self.agent(proof);result=await self.decide(agent,self.raw(actors),intent(module,purpose,required_roles=required))
                with self.subTest(purpose=purpose,actors=actors):self.assertNotEqual(result.status,'accepted')
            agent=self.agent(proof);self.assertEqual((await self.decide(agent,self.raw(),intent(module,purpose))).status,'accepted')

    async def test_mixed_formal_roster_allocates_only_requested_reviewed_infantry(self):
        # Exact late-match roster shape; synthetic observation, no live command.
        for module,purpose in [('attack','main_attack'),('raid','harass_economy')]:
            proof=self.evidence(((module,(purpose,)),),((module,purpose,('infantry',)),))
            for roster in [{'infantry':1,'anti_air':1},{'infantry':1,'air':1}]:
                agent=self.agent(proof);raw=self.raw(roster)
                raw['battlefield']['formations']=raw['battlefield']['formations'][:1]
                observed=agent.observe(raw);context=agent.context(observed.model_context(binding()))
                example=tactical_example(context)
                with self.subTest(purpose=purpose,roster=roster):
                    self.assertEqual(example[0]['required_roles'],['infantry'])
                    self.assertEqual(example[0]['force_fraction'],.5)
                    self.assertEqual((await self.decide(agent,raw,example[0])).status,'accepted')
                    task=next(t for t in agent.goals.tasks if t.request.module==module)
                    agent.host_commit_task(task.task_id)
                    self.assertEqual(task.status,'dispatch_pending')
                    invalid=self.agent(proof)
                    self.assertNotEqual((await self.decide(invalid,raw,intent(module,purpose,required_roles=['anti_air']))).status,'accepted')

    async def test_mixed_recon_roster_allocates_only_authorized_air_actor(self):
        agent=self.agent();raw=self.raw({'air':1,'infantry':1})
        raw['battlefield']['formations']=raw['battlefield']['formations'][:1]
        observed=agent.observe(raw);example=tactical_example(agent.context(observed.model_context(binding())))
        self.assertEqual(example[0]['required_roles'],['air'])
        self.assertEqual((await self.decide(agent,raw,example[0])).status,'accepted')

    async def test_coordinate_requires_both_roles_and_excludes_unreviewed_extra_actor(self):
        proof=self.evidence((('combined_arms',('coordinate_force',)),),(('combined_arms','coordinate_force',('infantry','anti_air')),))
        for actors,required,accepted in [({'infantry':4,'anti_air':2},['infantry','anti_air'],True),({'infantry':4,'air':2},['infantry','air'],False),({'infantry':4,'anti_air':2,'air':1},['infantry','anti_air'],False),({'infantry':4},['infantry'],False)]:
            agent=self.agent(proof);result=await self.decide(agent,self.raw(actors),intent('combined_arms','coordinate_force',target_contact_id=None,required_roles=required))
            with self.subTest(actors=actors):self.assertEqual(result.status=='accepted',accepted)

    async def test_roles_change_with_same_version_blocks_commit(self):
        agent=self.agent();await self.decide(agent,self.raw({'air':2}),intent('raid','recon',target_contact_id=None,required_roles=['air']))
        task=next(t for t in agent.goals.tasks if t.request.module=='raid');changed=tactical_snapshot(2,101);changed['battlefield']['formations'][0]['roles']={'infantry':2}
        agent.observe(changed)
        with self.assertRaisesRegex(ContractError,'host_commit_not_dispatchable'):agent.host_commit_task(task.task_id)
        self.assertEqual(task.status,'blocked');self.assertEqual(task.reason_code,'formation_changed')

    async def test_legacy_evidence_keeps_fixture_compatibility(self):
        proof=self.evidence(roles=());agent=self.agent(proof);result=await self.decide(agent,self.raw(),intent('raid','recon',target_contact_id=None))
        self.assertEqual(result.status,'accepted');self.assertNotIn('purpose_actor_roles',agent.goals.capability_manifest('simulated')['raid'])

    def test_examples_skip_wrong_roles_and_select_exact_air_formation(self):
        agent=self.agent();raw=self.raw();raw['battlefield']['formations'].append(dict(formation_id='formation_air',version=1,roles={'air':2},region_id='home_base',available=True))
        snapshot=agent.observe(raw);context=agent.context(snapshot.model_context(binding()));example=tactical_example(context)
        self.assertEqual(example[0]['formation_ids'],['formation_air']);self.assertEqual(example[0]['required_roles'],['air'])
        context['working_memory']['battlefield']['formations']=[f for f in context['working_memory']['battlefield']['formations'] if f['formation_id']!='formation_air']
        self.assertEqual(tactical_example(context),[])

    async def test_single_actor_purposes_reject_multiple_requested_roles(self):
        for module,purpose in [('raid','recon'),('raid','harass_economy'),('attack','main_attack')]:
            proof=self.evidence(((module,(purpose,)),),((module,purpose,('infantry','anti_air')),))
            agent=self.agent(proof);task=intent(module,purpose,required_roles=['infantry','anti_air'])
            if purpose=='recon':task['target_contact_id']=None
            result=await self.decide(agent,self.raw(),task)
            with self.subTest(purpose=purpose):self.assertNotEqual(result.status,'accepted')

    async def test_air_target_requires_explicit_anti_air_actor(self):
        proof=self.evidence((('attack',('main_attack',)),),(('attack','main_attack',('infantry','anti_air')),))
        for role,accepted in [('infantry',False),('anti_air',True)]:
            agent=self.agent(proof);raw=self.raw();raw['battlefield']['contacts'][0]['role']='air'
            result=await self.decide(agent,raw,intent(required_roles=[role]))
            with self.subTest(role=role):self.assertEqual(result.status=='accepted',accepted)

    def test_air_target_example_skips_infantry_formation_and_requests_anti_air(self):
        proof=self.evidence((('attack',('main_attack',)),),(('attack','main_attack',('infantry','anti_air')),))
        agent=self.agent(proof);raw=self.raw({'infantry':4});raw['battlefield']['contacts'][0]['role']='air'
        raw['battlefield']['formations'][1]['roles']={'infantry':4,'anti_air':2}
        snapshot=agent.observe(raw);context=agent.context(snapshot.model_context(binding()));example=tactical_example(context)
        self.assertEqual(example[0]['formation_ids'],['formation_raid']);self.assertEqual(example[0]['required_roles'],['anti_air'])
        context['working_memory']['battlefield']['formations']=context['working_memory']['battlefield']['formations'][:1]
        self.assertEqual(tactical_example(context),[])

    async def test_legacy_multi_role_single_actor_fixture_stays_compatible(self):
        proof=self.evidence((('attack',('main_attack',)),),());agent=self.agent(proof)
        self.assertEqual((await self.decide(agent,self.raw(),intent(required_roles=['infantry','anti_air']))).status,'accepted')

    async def test_infantry_only_evidence_skips_air_first_contact_for_ground_second(self):
        proof=self.evidence((('attack',('main_attack',)),),(('attack','main_attack',('infantry',)),))
        agent=self.agent(proof);raw=self.raw({'infantry':4});ground=copy.deepcopy(raw['battlefield']['contacts'][0])
        air=dict(ground,contact_id='contact_air_first',role='air');raw['battlefield']['contacts']=[air,ground]
        snapshot=agent.observe(raw);context=agent.context(snapshot.model_context(binding()))
        self.assertEqual(context['working_memory']['battlefield']['contacts'][0]['role'],'air')
        example=tactical_example(context)
        self.assertEqual(example[0]['target_contact_id'],ground['contact_id']);self.assertEqual(example[0]['required_roles'],['infantry'])
        self.assertEqual((await self.decide(self.agent(proof),raw,example[0])).status,'accepted')
        context['working_memory']['battlefield']['contacts']=[air]
        self.assertEqual(tactical_example(context),[])  # No compatible target does not force a task.

    def test_small_force_examples_round_to_at_least_one_actor(self):
        for module,purpose,role in [('attack','main_attack','infantry'),('raid','harass_economy','infantry'),('raid','recon','air')]:
            proof=self.evidence(((module,(purpose,)),),((module,purpose,(role,)),))
            agent=self.agent(proof);raw=self.raw({role:4});raw['battlefield']['formations']=raw['battlefield']['formations'][:1]
            snapshot=agent.observe(raw);original=agent.context(snapshot.model_context(binding()))
            for count,expected in [(1,None),(2,.5),(3,.5),(4,.25)]:
                context=copy.deepcopy(original);context['working_memory']['battlefield']['formations'][0]['roles']={role:count}
                example=tactical_example(context)
                with self.subTest(purpose=purpose,count=count):
                    if expected is None:self.assertEqual(example,[])
                    else:
                        self.assertEqual(example[0]['force_fraction'],expected);self.assertGreaterEqual(int(count*min(.5,expected)),1)

    def test_reserved_units_do_not_inflate_small_force_example_budget(self):
        proof=self.evidence((('attack',('main_attack',)),),(('attack','main_attack',('infantry',)),))
        agent=self.agent(proof);raw=self.raw({'infantry':1});raw['battlefield']['formations'][1]['roles']={'infantry':8}
        snapshot=agent.observe(raw);context=agent.context(snapshot.model_context(binding()))
        context['working_memory']['active_goals']=[dict(status='dispatch_pending',formation_ids=['formation_raid'])]
        self.assertEqual(tactical_example(context),[])


if __name__=='__main__':unittest.main()
