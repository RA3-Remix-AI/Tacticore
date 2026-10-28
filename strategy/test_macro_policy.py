import copy
import ast
import hashlib
import json
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import unittest
from engine import Snapshot,StrategyEngine,ContractError,validate_policy
from fixtures import snapshot,policy,binding
from battle_agent import BattleAgent
from http_adapter import system_prompt


def macro_snapshot(actions=None):
    raw=snapshot();raw['macro_control']=dict(mode='macro_native',available_actions=actions if actions is not None else ['budgeteconomy','budgetarmy'])
    targets={a:region for a,region in [('deployattack','north_expansion'),('deploydefense','home_base')]
        if a in raw['macro_control']['available_actions']}
    if targets:raw['macro_control']['region_targets']=targets
    return Snapshot.from_dict(raw)


class MacroContractTests(unittest.TestCase):
    def test_deployment_is_bound_to_exact_requested_and_current_public_region(self):
        request=macro_snapshot(['deployattack']);context=request.model_context(binding())
        self.assertEqual(context['macro_policy_catalog']['deployattack']['target_region'],'north_expansion')
        self.assertEqual(Snapshot.from_dict(request.to_dict()),request)
        raw=policy(context,macro_actions=['deployattack'],objective_region='north_expansion')
        self.assertEqual(validate_policy(raw,request,request,binding(),20).objective_region,'north_expansion')
        for target in (None,'home_base'):
            raw['objective_region']=target
            with self.assertRaisesRegex(ContractError,'macro_region_target_binding'):validate_policy(raw,request,request,binding(),20)
        raw['objective_region']='north_expansion';changed=request.to_dict();changed['macro_control']['region_targets']['deployattack']='home_base'
        with self.assertRaisesRegex(ContractError,'macro_region_target_binding'):
            validate_policy(raw,request,Snapshot.from_dict(changed),binding(),20)

    def test_bare_deployment_capability_without_region_binding_is_rejected(self):
        raw=snapshot();raw['macro_control']=dict(mode='macro_native',available_actions=['deployattack'])
        with self.assertRaisesRegex(ContractError,'macro_region_capabilities_missing'):Snapshot.from_dict(raw)
    def test_native_target_macro_intent_does_not_need_an_invented_objective(self):
        request=macro_snapshot(['scout','budgeteconomy'])
        raw=policy(request.model_context(binding()),stance='scout',objective_region=None,macro_actions=['scout'])
        self.assertEqual(validate_policy(raw,request,request,binding(),20).macro_actions,('scout',))
        raw['objective_region']='invented_region'
        with self.assertRaisesRegex(ContractError,'objective_region'):validate_policy(raw,request,request,binding(),20)

    def test_legacy_and_regional_deployment_still_require_explicit_nondefense_region(self):
        for request,actions in [(Snapshot.from_dict(snapshot()),[]),(macro_snapshot(['deployattack']),['deployattack'])]:
            raw=policy(request.model_context(binding()),stance='pressure',objective_region=None,macro_actions=actions)
            with self.assertRaisesRegex(ContractError,'objective_required'):validate_policy(raw,request,request,binding(),20)

    def test_actual_scout_feedback_fits_wire_budget_without_duplicating_user_catalog(self):
        import http_adapter
        root=Path(__file__).resolve().parents[1];host=root/'acceptance/runs/20261028-073337-macro-probe/battle-host'
        events=[json.loads(l) for l in (host/'host-events.jsonl').read_text(encoding='utf8').splitlines()]
        context=copy.deepcopy([r['context'] for r in events if r['kind']=='model_macro_request_context'][-1])
        context['macro_scouting_feedback']=json.loads((host/'host-status.json').read_text())['macro_scouting_feedback']
        profile=json.loads((host/'profile.json').read_text())['effective']
        public=SimpleNamespace(traits=profile['traits'],personality=profile['personality'])
        source=next(r for r in json.loads((host/'sources.json').read_text())['sources'] if Path(r['path']).name=='http_adapter.py')
        frozen=host/'source'/source['copy'];raw=frozen.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),source['sha256'])
        function=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='macro_system_prompt')
        namespace={name:getattr(http_adapter,name) for name in ('Profile','STANCES','ECONOMY','TECH','REASONS')};namespace['json']=json
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(frozen),'exec'),namespace)
        def wire(prompt):
            return len(json.dumps({'messages':[dict(role='system',content=prompt),dict(role='user',content=json.dumps(
                context,ensure_ascii=False,allow_nan=False,separators=(',',':')))]},ensure_ascii=False).encode())+1024
        self.assertGreater(wire(namespace['macro_system_prompt'](public,context)),16384)
        self.assertLess(wire(http_adapter.macro_system_prompt(public,context)),16384)
        public.traits='风格偏好'*100
        self.assertEqual(len(public.traits.encode()),1200)
        self.assertLess(wire(http_adapter.macro_system_prompt(public,context)),16384)
        self.assertTrue(context['macro_scouting_feedback']['native_execution_observed'])
        self.assertNotIn('\nMacro catalog:',http_adapter.macro_system_prompt(public,context))

    def test_macro_snapshot_roundtrip_and_public_catalog(self):
        request=macro_snapshot();self.assertEqual(Snapshot.from_dict(request.to_dict()),request)
        context=request.model_context(binding())
        self.assertEqual(context['control_mode'],'macro_native')
        self.assertEqual(context['macro_policy_catalog']['budgeteconomy']['native_account_shares']['investment'],.4)
        self.assertEqual(set(context['macro_policy_catalog']),set(context['allowed_macro_actions']))

    def test_no_capability_is_implicitly_granted(self):
        for available in [[],None]:
            request=macro_snapshot([]) if available==[] else Snapshot.from_dict(snapshot())
            raw=policy(request.model_context(binding()));raw['macro_actions']=['budgeteconomy']
            with self.assertRaisesRegex(ContractError,'unsupported_macro_action'):
                validate_policy(raw,request,request,binding(),20)

    def test_unknown_duplicate_conflicting_actions_and_control_fields(self):
        request=macro_snapshot()
        for actions in [['Move'],['budgeteconomy']*2,['budgeteconomy','budgetarmy'],[{'flag':'x'}]]:
            raw=policy(request.model_context(binding()));raw['macro_actions']=actions
            with self.subTest(actions=actions),self.assertRaises(ContractError):validate_policy(raw,request,request,binding(),20)
        for control in [dict(mode='micro',available_actions=[]),dict(mode='macro_native',available_actions=['arbitrary']),dict(mode='macro_native',available_actions=[],authorized=True)]:
            raw=snapshot();raw['macro_control']=control
            with self.assertRaises(ContractError):Snapshot.from_dict(raw)

    def test_late_revocation_and_mode_change_reject_response(self):
        request=macro_snapshot();raw=policy(request.model_context(binding()));raw['macro_actions']=['budgeteconomy']
        for latest in [macro_snapshot(['budgetarmy']),Snapshot.from_dict(snapshot())]:
            with self.assertRaises(ContractError):validate_policy(raw,request,latest,binding(),20)

    def test_unit_tasks_cannot_enter_macro_plan(self):
        request=macro_snapshot()
        for change in [dict(tactical_tasks=[{}]),dict(runtime_task={})]:
            raw=policy(request.model_context(binding()));raw.update(change)
            with self.assertRaisesRegex(ContractError,'macro_mode_rejects_unit_tasks'):
                validate_policy(raw,request,request,binding(),20)

    def test_macro_changes_affect_intent_and_capability_revocation_expires_plan(self):
        request=macro_snapshot();raw=policy(request.model_context(binding()));raw['macro_actions']=['budgeteconomy']
        plan=validate_policy(raw,request,request,binding(),20);engine=StrategyEngine(binding())
        self.assertNotEqual(engine._intent(plan),engine._intent(replace(plan,macro_actions=('budgetarmy',))))
        self.assertTrue(engine._usable(plan,request));self.assertFalse(engine._usable(plan,macro_snapshot([])))
        self.assertEqual(plan.public()['macro_actions'],['budgeteconomy'])

    def test_actual_agent_payload_and_prompt_have_macro_boundary(self):
        request=macro_snapshot();agent=BattleAgent(StrategyEngine(binding()));agent.observe(request.to_dict())
        context=agent.context(request.model_context(binding()))
        self.assertEqual(context['control_mode'],'macro_native');self.assertEqual(context['allowed_macro_actions'],['budgeteconomy','budgetarmy'])
        self.assertEqual(context['working_memory']['battlefield']['formations'],[])
        self.assertEqual({r['module'] for r in context['pending_decisions']},{'macro'})
        prompt=system_prompt(SimpleNamespace(traits='Prefer economic investment.',personality=1),context)
        self.assertIn('Original native AI performs movement',prompt)
        self.assertIn('native_account_shares',prompt)
        self.assertNotIn('move_hold_return',prompt);self.assertNotIn('formation_ids',prompt)
        self.assertNotIn('/5TFMacro_',str(context));self.assertNotIn('0x',str(context))

    def test_production_requires_bounded_matching_quantity(self):
        request=macro_snapshot(['produceflak']);raw=policy(request.model_context(binding()))
        raw['macro_actions']=['produceflak']
        for quantity in [None,{},dict(action='producetank',additional_count=2),
                         dict(action='produceflak',additional_count=True),dict(action='produceflak',additional_count=4)]:
            raw['macro_production']=quantity
            with self.subTest(quantity=quantity),self.assertRaisesRegex(ContractError,'macro_production_quantity'):
                validate_policy(raw,request,request,binding(),20)
        raw['macro_production']=dict(action='produceflak',additional_count=2)
        plan=validate_policy(raw,request,request,binding(),20)
        self.assertEqual(plan.public()['macro_production'],raw['macro_production'])
        engine=StrategyEngine(binding());engine.current=plan;agent=BattleAgent(engine);agent.observe(request.to_dict())
        self.assertEqual(agent.public_memory()['current_strategy']['execution_projection']['macro_production'],raw['macro_production'])
        raw['macro_production']['additional_count']=1
        other=validate_policy(raw,request,request,binding(),20)
        self.assertNotEqual(StrategyEngine._intent(plan),StrategyEngine._intent(other))
        self.assertFalse(StrategyEngine(binding())._usable(plan,macro_snapshot([])))

    def test_quantity_without_qualified_action_cannot_become_dispatch(self):
        request=macro_snapshot();raw=policy(request.model_context(binding()))
        raw['macro_production']=dict(action='produceflak',additional_count=2)
        with self.assertRaisesRegex(ContractError,'without_action'):validate_policy(raw,request,request,binding(),20)

    def test_production_catalog_explains_queue_control_and_partial_completion(self):
        request=macro_snapshot(['produceflak']);context=request.model_context(binding())
        catalog=context['macro_policy_catalog']['produceflak']['quantity']
        self.assertEqual(catalog['control_basis'],'new_native_queue_acceptances')
        self.assertFalse(catalog['completed_units_guaranteed'])
        prompt=system_prompt(SimpleNamespace(traits='',personality=1),context)
        self.assertIn('macro_production',prompt);self.assertIn('not a guarantee of completed units',prompt)

    def test_host_qualified_count_catalog_and_late_revocation(self):
        raw=snapshot();raw['macro_control']=dict(mode='macro_native',available_actions=['produceflak'],production_counts={'produceflak':[2]})
        request=Snapshot.from_dict(raw);context=request.model_context(binding())
        self.assertEqual(Snapshot.from_dict(request.to_dict()),request)
        self.assertEqual(context['macro_policy_catalog']['produceflak']['quantity']['allowed_additional_counts'],[2])
        answer=policy(context);answer.update(macro_actions=['produceflak'],macro_production=dict(action='produceflak',additional_count=2))
        plan=validate_policy(answer,request,request,binding(),20)
        answer['macro_production']['additional_count']=1
        with self.assertRaisesRegex(ContractError,'quantity_not_qualified'):validate_policy(answer,request,request,binding(),20)
        raw['macro_control']['production_counts']['produceflak']=[1];latest=Snapshot.from_dict(raw)
        answer['macro_production']['additional_count']=2
        with self.assertRaisesRegex(ContractError,'quantity_not_qualified'):validate_policy(answer,request,latest,binding(),20)
        self.assertFalse(StrategyEngine(binding())._usable(plan,latest))

    def test_invalid_host_counts_cannot_enter_snapshot(self):
        for counts in ({'produceflak':[True]},{'produceflak':[]},{'produceflak':[2,2]},{'producetank':[2]},{}):
            raw=snapshot();raw['macro_control']=dict(mode='macro_native',available_actions=['produceflak'],production_counts=counts)
            with self.subTest(counts=counts),self.assertRaisesRegex(ContractError,'capability_counts'):Snapshot.from_dict(raw)


class MacroAgentLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_combined_native_work_is_rejected_but_next_building_decision_can_continue(self):
        allowed=['budgeteconomy','buildreactor','produceconscript']
        raw=snapshot();raw['macro_control']=dict(mode='macro_native',available_actions=allowed,production_counts={'produceconscript':[1]})
        agent=BattleAgent(StrategyEngine(binding(),min_hold_game_seconds=0))
        async def budget(context):return policy(context,macro_actions=['budgeteconomy'])
        first=await agent.decide(raw,budget);self.assertEqual(first.status,'accepted')
        async def conflicting(context):
            return policy(context,macro_actions=allowed,macro_production=dict(action='produceconscript',additional_count=1))
        raw.update(snapshot_id=2,game_time_seconds=102.)
        rejected=await agent.decide(raw,conflicting)
        self.assertEqual(rejected.reason_code,'conflicting_macro_work_actions')
        self.assertEqual(agent.engine.current.plan_id,first.plan.plan_id);self.assertFalse(agent.engine.stopped)
        async def building(context):return policy(context,macro_actions=['budgeteconomy','buildreactor'],macro_production=None)
        raw.update(snapshot_id=3,game_time_seconds=104.)
        next_plan=await agent.decide(raw,building)
        self.assertEqual(next_plan.status,'accepted');self.assertIn('buildreactor',next_plan.plan.macro_actions)
        self.assertEqual(agent.jobs()['jobs'],[])

    async def test_macro_policy_does_not_create_legacy_unit_or_build_jobs(self):
        request=macro_snapshot();agent=BattleAgent(StrategyEngine(binding()))
        async def model(context):
            raw=policy(context);raw['macro_actions']=['budgeteconomy'];return raw
        result=await agent.decide(request.to_dict(),model)
        self.assertEqual(result.status,'accepted')
        self.assertEqual(agent.jobs()['jobs'],[])
        self.assertEqual(agent.public_memory()['active_goals'],[])
        context=agent.context(request.model_context(binding()))
        self.assertEqual(context['working_memory']['active_goals'],[])


if __name__=='__main__':unittest.main()
