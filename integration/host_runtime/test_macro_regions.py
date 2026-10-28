import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid
import tempfile
from unittest.mock import patch

from .contracts import ContractError
from .macro_policy_runtime import BudgetScope,COMMANDER,MacroRequestAudit
from .macro_region_scope import RegionalScope,verified_regional_field
from .macro_regions import MacroRegionalController,RegionalFeedback,compact_regional_feedback
from .test_macro_scouting import observed
from .test_macro_production_feedback import sample

ROOT=Path(__file__).resolve().parents[2]

def regional_sample(frame=1500,x=0,active=True):
    obs,view=observed(frame,active=False)
    obs['state_scores']['private-region']=dict(domain='strategic',group='private-region-state',score=1.)
    obs['runtimes'].append(dict(group='private-region-state',native_execution_active=active,native_tactic_family='simple_attack',
        owned_groups=[dict(found=True,all_members_resolved=True,native_id=12,
            members=[dict(thing_id=88,owner='private-owner',xyz=[x,0,0])])]))
    return obs,view

class RegionalControllerTests(unittest.TestCase):
    def setUp(self):
        self.sid=str(uuid.uuid4());self.calls=[];self.events=[]
        b=BudgetScope('a'*64,{},('private-scout','private-region'),dict(budgetarmy='private-army'),{})
        self.scope=RegionalScope(b,'private-flak',{},scout_flag='private-scout',
            regional_targets=(('deployattack','region_1_3','private-region',100,0),))
        def apply(actions,duration,ident):self.calls.append((actions,duration,ident));return dict(seq=len(self.calls))
        transport=SimpleNamespace(session=dict(session_id=self.sid,mod_sha256='a'*64),apply=apply,close=lambda:None)
        self.controller=MacroRegionalController(transport,self.scope,self.sid,'b'*64,lambda k,**v:self.events.append((k,v)))
        self.plan=SimpleNamespace(origin='model',session_id=self.sid,commander_id=COMMANDER,player_id=3,
            based_on_game_time_seconds=100.,expires_at_game_seconds=160.,tactical_tasks=(),runtime_task=None,
            macro_actions=('deployattack','budgetarmy'),macro_production=None,objective_region='region_1_3',plan_id='one')
        self.refresh()

    def refresh(self,frame=1500,x=0,active=True):
        obs,view=regional_sample(frame,x,active);builder,census=sample(frame);obs['construction_feedback']=census
        self.controller.observe_snapshot(view);self.controller.refresh(dict(observation=obs,build_observation=builder))

    def dispatch(self):return self.controller.dispatch(self.plan,100.,effective_hash='b'*64)

    def test_exact_region_once_bounded_expiry_releases_without_unit_orders(self):
        first=self.dispatch();self.assertEqual(first,self.dispatch())
        self.assertEqual(self.calls[0][:2],(['deployattack','budgetarmy'],900))
        self.assertTrue(self.controller.busy);self.assertEqual(self.controller.available_actions(100.),())
        self.controller.tick(160.);self.controller.tick(161.)
        self.assertEqual(len(self.calls),2);self.assertEqual(self.calls[-1][:2],([],1))
        self.assertEqual(self.controller.regional_feedback()['release_reason'],'expired')

    def test_native_movement_and_progress_are_separate_from_arrival_or_mission_success(self):
        self.dispatch();self.refresh(1510,80)
        value=compact_regional_feedback(self.controller.regional_feedback(),1510/15)
        self.assertEqual(value['groups_progressing_toward_region'],1);self.assertEqual(value['moved_native_groups'],1)
        self.assertFalse(value['arrival_verified']);self.assertFalse(value['mission_success_verified'])
        self.assertNotIn('private',json.dumps(value));self.assertNotIn('thing_id',value)
        self.refresh(1520,80,False);self.controller.tick(1520/15)
        self.assertEqual(self.controller.regional_feedback()['release_reason'],'native_execution_inactive')

    def test_wrong_region_mixed_work_and_changed_revision_never_dispatch(self):
        for change in (dict(objective_region='region_8_3'),dict(macro_actions=('deployattack','scout')),
                dict(macro_actions=('deployattack','produceflak'))):
            original=copy.copy(self.plan);self.plan.__dict__.update(change)
            with self.assertRaises(ContractError):self.dispatch()
            self.plan=original
        with self.assertRaises(ContractError):self.controller.dispatch(self.plan,100.,effective_hash='c'*64)
        self.assertEqual(self.calls,[])

    def test_foreign_or_stale_native_view_cannot_offer_region_action(self):
        for fault in ('foreign','stale','wrong_tactic'):
            obs,view=regional_sample()
            if fault=='foreign':obs['runtimes'][-1]['owned_groups'][0]['members'][0]['owner']='foreign'
            elif fault=='stale':obs['frame']=1400
            else:obs['runtimes'][-1]['native_tactic_family']='unsupported'
            with self.subTest(fault=fault),self.assertRaises(ContractError):RegionalFeedback(obs,view,self.scope.regional_targets[0])

    def test_unknown_delivery_is_terminal_and_not_retried(self):
        count=[]
        def fail(*a):count.append(1);raise RuntimeError('private native error')
        self.controller.transport.apply=fail
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):self.dispatch()
        with self.assertRaises(ContractError):self.dispatch()
        self.assertEqual(len(count),1)

    def test_actual_fixed_field_has_both_region_effects_and_rejects_driver_changes(self):
        directory=ROOT/'reports/macro-region-waypoint-72380-20261028-v3'
        pre,final,manifest,targets,evidence=verified_regional_field(directory)
        self.assertEqual(len(targets),2);self.assertTrue(final['cleanup_verified'])
        from . import macro_region_scope as module
        original=module.load
        def changed(path):
            value=original(path)
            if Path(path).name=='driver-preflight.json':value['driver_sha256']='f'*64
            return value
        with patch.object(module,'load',side_effect=changed),self.assertRaisesRegex(ContractError,'fixed_field_binding'):
            verified_regional_field(directory)

    def test_schema7_binds_preserved_base_new_package_and_regional_field(self):
        from .macro_bundle import create_bundle,load_bundle
        old=json.loads((ROOT/'acceptance/runs/20261028-075720-macro-probe/macro-budget-bundle.json').read_text())
        keys=('normal','host_loss','expiry','production','production_static','production_choices','construction','technology_budget','scouting')
        args={key:old[key] for key in keys}
        args.update(build=ROOT/'native-ai/macro-policy-runtime/bin/policy-v32-desktop-regions-20261028',
            qualification_build=old['build'],visibility=ROOT/'reports/macro-visibility-4a65c9b6-derived-20261028-v1',
            regional=ROOT/'reports/macro-region-waypoint-72380-20261028-v3',
            regional_static=ROOT/'reports/macro-region-package-preservation-20261028-v3')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'bundle.json';create_bundle(path,**args);value,scope=load_bundle(path)
            self.assertEqual(value['schema_version'],7);self.assertIn('deployattack',scope.available_actions)
            self.assertIn('scout',scope.available_actions);self.assertIn('buildreactor',scope.available_actions)
            value['pins'][str((args['regional']/'transport/policy-probe.jsonl').resolve())]='0'*64
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ContractError,'not_qualified'):load_bundle(path)

    def test_actual_context_fits_wire_budget_and_keeps_both_bound_public_regions(self):
        from engine import Snapshot,Binding,StrategyEngine
        from battle_agent import BattleAgent
        from http_adapter import macro_system_prompt
        path=ROOT/'acceptance/runs/20261028-075720-macro-probe/battle-host/macro-snapshots.jsonl'
        raw=json.loads(path.read_text().splitlines()[0]);frame=round(raw['game_time_seconds']*15)
        raw['capabilities']['regions']=sorted(set(raw['capabilities']['regions'])|{'region_1_3','region_8_3'})
        raw['macro_control']['available_actions']+=['deployattack','deploydefense']
        raw['macro_control']['region_targets']=dict(deployattack='region_1_3',deploydefense='region_8_3')
        request=Snapshot.from_dict(raw);binding=Binding(request.session_id,3,COMMANDER,'commander','23968c8e-25d3-47bd-8c84-5f0d5bbfd43b')
        agent=BattleAgent(StrategyEngine(binding));agent.observe(raw)
        profile=SimpleNamespace(traits='风格偏好'*100,personality=1)
        def wire(context):
            return len(json.dumps({'messages':[dict(role='system',content=macro_system_prompt(profile,context)),
                dict(role='user',content=json.dumps(context,ensure_ascii=False,separators=(',',':')))]},ensure_ascii=False).encode())+1024
        regional=dict(source='native_regional_group_observation',action='deployattack',target_region='region_1_3',
            observed_frame=frame,view_frame=frame,active_native_tactics=1,allocated_native_groups=1,
            native_execution_observed=True,moved_native_groups=1,groups_progressing_toward_region=1,
            policy_released=False,release_reason=None)
        budget=dict(status='native_delegation_observed',selected_policy=None,actions=[],observed_frame=frame,native_effect_verified=False)
        audit=MacroRequestAudit(SimpleNamespace(input_size=wire),lambda *a,**k:None,
            feedback_supplier=lambda:budget,regional_supplier=lambda:regional)
        context=agent.context(request.model_context(binding),wire_size=audit.input_size,wire_limit=16384)
        self.assertLessEqual(audit.input_size(context),16384)
        self.assertTrue({'region_1_3','region_8_3'}<=set(context['allowed_regions']))
        self.assertEqual(audit.prepare(context)['macro_regional_feedback']['groups_progressing_toward_region'],1)

if __name__=='__main__':unittest.main()
