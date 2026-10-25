"""Tactical examples use the frozen transmitted contract, never hidden/latest data."""
import copy
from dataclasses import replace
import json
import unittest
import uuid

from battle_agent import BattleAgent,TacticalEvidence
from engine import Snapshot,StrategyEngine,validate_policy
from fixtures import binding,COMMANDER,CONNECTION,SESSION
from http_adapter import ChatAdapter,Endpoint,Profile,system_prompt,tactical_example
from tactical_fixtures import tactical_snapshot


class TacticalPrompt(unittest.IsolatedAsyncioTestCase):
    def profile(self):return Profile(COMMANDER,'mock',CONNECTION,'自定义','mock',2,'只使用已验证敌情。',Endpoint.parse('http://localhost:1'),'')

    def context(self,purposes=(),raw=None):
        raw=raw or tactical_snapshot();evidence=TacticalEvidence(str(uuid.uuid4()),SESSION,3,'simulated',purposes) if purposes else None
        agent=BattleAgent(StrategyEngine(binding()),tactical_evidence=evidence);request=agent.observe(raw)
        return agent,request,agent.context(request.model_context(binding()))

    def example(self,context):
        prompt=system_prompt(self.profile(),context);marker='choices when justified by the current evidence: '
        return json.JSONDecoder().raw_decode(prompt.split(marker,1)[1])[0]

    def test_authorized_visible_attack_example_is_valid_bound_and_has_45_second_window(self):
        agent,request,context=self.context((('attack',('main_attack',)),))
        example=self.example(context);plan=validate_policy(example,request,request,binding(),1)
        self.assertEqual(example['valid_for_game_seconds'],45);self.assertEqual(len(plan.tactical_tasks),1)
        self.assertEqual(plan.tactical_tasks[0].target_contact_id,'contact_ore');self.assertEqual(plan.tactical_tasks[0].formation_ids,('formation_main',))
        prompt=system_prompt(self.profile(),context)
        for text in ['does not mean dry-run','Stance alone does not dispatch','THIS message']:self.assertIn(text,prompt)
        questions={item['module']:item['question'] for item in context['pending_decisions']}
        self.assertEqual(questions['attack'],'choose_bound_tactical_task');self.assertEqual(questions['raid'],'harassment_intent_only')

    def test_unverified_wrong_purpose_or_no_transmitted_context_never_invents_example(self):
        _,_,context=self.context()
        self.assertEqual(self.example(context)['tactical_tasks'],[])
        context['capability_manifest']['attack']={'state':'planned_only','reason_code':'host_evidence_present','verified_purposes':['recon']}
        self.assertEqual(tactical_example(context),[])
        _,_,context=self.context((('attack',('main_attack',)),))
        context['working_memory']['battlefield']['contacts']=[]
        self.assertEqual(tactical_example(context),[])  # Latest Snapshot still has contact_ore.
        context['working_memory']['battlefield']['formations']=[]
        self.assertEqual(tactical_example(context),[])

    def test_hidden_stale_unavailable_and_host_reserved_bindings_remain_empty(self):
        _,_,original=self.context((('attack',('main_attack',)),))
        variants=[('contact','currently_visible',False),('contact','stealth_state','unknown'),('contact','observed_at_game_seconds',90),('formation','available',False)]
        for kind,key,value in variants:
            context=copy.deepcopy(original)
            if kind=='contact':context['working_memory']['battlefield']['contacts'][0][key]=value
            else:
                for formation in context['working_memory']['battlefield']['formations']:formation[key]=value
            with self.subTest(kind=kind,key=key):self.assertEqual(tactical_example(context),[])
        context=copy.deepcopy(original);context['working_memory']['active_goals']=[dict(status='dispatch_pending',formation_ids=['formation_main','formation_raid'])]
        self.assertEqual(tactical_example(context),[])

    def test_recon_and_two_role_examples_use_only_exact_granted_purpose(self):
        for pair in [('raid','recon'),('raid','harass_economy'),('combined_arms','coordinate_force'),('combined_arms','defend_base')]:
            _,request,context=self.context(((pair[0],(pair[1],)),))
            example=self.example(context);parsed=validate_policy(example,request,request,binding(),1)
            self.assertEqual((parsed.tactical_tasks[0].module,parsed.tactical_tasks[0].purpose),pair)
            if pair[0]=='combined_arms':
                self.assertGreaterEqual(len(example['tactical_tasks'][0]['required_roles']),2)
                self.assertEqual(example['tactical_tasks'][0]['force_fraction'],.5)
            if pair[1]=='recon':self.assertIsNone(example['tactical_tasks'][0]['target_contact_id'])

    def test_combined_example_does_not_offer_an_insufficient_two_actor_allocation(self):
        _,_,context=self.context((('combined_arms',('coordinate_force',)),))
        formation=context['working_memory']['battlefield']['formations'][0]
        context['working_memory']['battlefield']['formations']=[formation]
        formation['roles']={'infantry':1,'anti_air':1}
        self.assertEqual(tactical_example(context),[])
        formation['roles']={'infantry':2,'anti_air':2}
        example=tactical_example(context)
        self.assertEqual(len(example),1);self.assertEqual(example[0]['force_fraction'],.5)

    async def test_authorized_maximum_context_stays_within_actual_16kb_wire_budget(self):
        raw=tactical_snapshot();contact=raw['battlefield']['contacts'][0];formation=raw['battlefield']['formations'][0]
        raw['battlefield']['contacts']=[dict(contact,contact_id='contact_'+'c'*45+str(i)) for i in range(64)]
        raw['battlefield']['formations']=[dict(formation,formation_id='formation_'+'f'*43+str(i)) for i in range(32)]
        evidence=TacticalEvidence(str(uuid.uuid4()),SESSION,3,'simulated',(('attack',('main_attack',)),('raid',('recon','harass_economy')),('combined_arms',('coordinate_force',))),
            (('attack','main_attack',('infantry','anti_air')),('raid','recon',('air',)),('raid','harass_economy',('infantry','anti_air')),('combined_arms','coordinate_force',('infantry','anti_air'))))
        agent=BattleAgent(StrategyEngine(binding()),tactical_evidence=evidence,context_budget_bytes=8192)
        adapter=ChatAdapter(replace(self.profile(),traits='战'*4000,model='m'*200),max_input_bytes=16384)
        class FrozenModel:
            max_input_bytes=adapter.max_input_bytes
            def input_size(self,context):return adapter.input_size(context)
            async def __call__(self,context):
                self.context=copy.deepcopy(context);return json.JSONDecoder().raw_decode(system_prompt(adapter.profile,context).split('choices when justified by the current evidence: ',1)[1])[0]
        model=FrozenModel();result=await agent.decide(raw,model)
        self.assertEqual(result.status,'accepted');self.assertTrue(result.plan.tactical_tasks)
        self.assertLessEqual(adapter.input_size(model.context),16384)
        self.assertTrue(model.context['context_limits']['details_truncated'])


if __name__=='__main__':unittest.main(verbosity=2)
