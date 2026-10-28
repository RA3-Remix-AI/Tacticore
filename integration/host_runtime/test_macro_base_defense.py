import copy
from dataclasses import fields
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from .contracts import ContractError
from .macro_base_defense_scope import BaseDefenseScope,GOAL,defense_catalog_override,verify_base_defense_field
from .macro_bundle import create_bundle,load_bundle
from .macro_policy_runtime import BudgetScope,COMMANDER,MacroRequestAudit,trial
from .macro_regions import RegionalFeedback,MacroRegionalController,compact_regional_feedback
from .test_macro_regions import regional_sample
from .test_macro_production_feedback import sample

ROOT=Path(__file__).resolve().parents[2]
FIELD=ROOT/'reports/macro-base-defense-72168-20261028-v1'


def defense_sample(frame=1500,active=True):
    obs,view=regional_sample(frame,4410,active)
    obs['runtimes'][-1]['native_tactic_family']='static_defense'
    obs['runtimes'][-1]['owned_groups'][0]['members'][0]['xyz']=[4410,2010,0]
    builder,census=sample(frame)
    census['own_objects'][0]['xyz']=[4404,2016,0]
    obs['construction_feedback']=census
    return obs,view,builder


class BaseDefenseTests(unittest.TestCase):
    def test_opening_missing_yard_is_waitable_but_other_origin_is_not_qualified(self):
        from .macro_live import require_base_origin
        with self.assertRaisesRegex(ContractError,'session_not_ready'):require_base_origin(dict(own_objects=[]),'region_8_3')
        require_base_origin(dict(own_objects=[dict(type_hash='0xc16ff13f',xyz=[4416,2010,0])]),'region_8_3')
        with self.assertRaisesRegex(ContractError,'outside_qualified_scope'):
            require_base_origin(dict(own_objects=[dict(type_hash='0xc16ff13f',xyz=[850,2010,0])]),'region_8_3')

    def test_qualified_field_and_preserved_old_scopes_create_evidence_bound_bundle(self):
        original=json.loads((ROOT/'reports/macro-base-defense-desktop-bootstrap-20261028-v2/macro-budget-bundle.json').read_text())
        args={k:v for k,v in original.items() if k not in ('pins','schema_version','kind')}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bundle.json';public=create_bundle(path,**args)
            self.assertTrue(public['base_defense_granted']);self.assertGreater(path.stat().st_size,32768)
            _,scope=load_bundle(path);self.assertIsInstance(scope,BaseDefenseScope)
            changed=json.loads(path.read_text());changed['pins'][str(ROOT/'native-ai/macro_area_defense_observation.py')]='0'*64
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ContractError,'not_qualified'):load_bundle(path)

    def test_gate_ack_without_native_owned_defense_effect_cannot_grant_scope(self):
        changed=copy.deepcopy(trial(FIELD/'transport'))
        for row in changed[3]:
            for task in row.get('observation',{}).get('runtimes',[]):task['native_execution_active']=False
        with patch('host_runtime.macro_base_defense_scope.trial',return_value=changed):
            with self.assertRaisesRegex(ContractError,'effect_or_release_missing'):verify_base_defense_field(FIELD)

    def test_native_defense_feedback_uses_owned_infrastructure_and_not_point_progress(self):
        obs,view,_=defense_sample();target=('deploydefense','region_8_3','private-region',4404,2016)
        tracker=RegionalFeedback(obs,view,target,family='static_defense',goal=GOAL)
        value=compact_regional_feedback(tracker.public(),100.)
        self.assertEqual(value['defender_groups_near_infrastructure'],1)
        self.assertEqual(value['groups_progressing_toward_region'],0)
        self.assertEqual(value['target_policy'],'original_native_friendly_land_structure')
        self.assertFalse(value['mission_success_verified'])
        with self.assertRaisesRegex(ContractError,'native_tactic_type'):RegionalFeedback(obs,view,target)
        obs['runtimes'][-1]['owned_groups'][0]['members'][0]['owner']='foreign'
        with self.assertRaisesRegex(ContractError,'foreign_member'):RegionalFeedback(obs,view,target,family='static_defense',goal=GOAL)

    def test_native_task_releases_at_expiry_without_unit_orders_or_repeating_plan(self):
        sid=str(uuid.uuid4());calls=[]
        budget=BudgetScope('a'*64,{},('private-scout','private-region'),dict(budgetarmy='private-army'),{})
        scope=BaseDefenseScope(budget,'private-flak',{},scout_flag='private-scout',
            regional_targets=(('deploydefense','region_8_3','private-region',4404,2016),))
        def apply(actions,duration,ident):calls.append((actions,duration));return dict(seq=len(calls))
        transport=SimpleNamespace(session=dict(session_id=sid,mod_sha256='a'*64),apply=apply,close=lambda:None)
        controller=MacroRegionalController(transport,scope,sid,'b'*64,lambda *a,**k:None)
        obs,view,builder=defense_sample(active=False);controller.observe_snapshot(view)
        controller.refresh(dict(observation=obs,build_observation=builder))
        plan=SimpleNamespace(origin='model',session_id=sid,commander_id=COMMANDER,player_id=3,
            based_on_game_time_seconds=100.,expires_at_game_seconds=160.,tactical_tasks=(),runtime_task=None,
            macro_actions=('deploydefense','budgetarmy'),macro_production=None,objective_region='region_8_3',plan_id='base-defense')
        receipt=controller.dispatch(plan,100.,effective_hash='b'*64)
        self.assertEqual(receipt,controller.dispatch(plan,100.,effective_hash='b'*64))
        self.assertEqual(receipt['goal'],GOAL)
        controller.tick(160.);controller.tick(161.)
        self.assertEqual(calls,[(['deploydefense','budgetarmy'],900),([],1)])
        self.assertEqual(controller.regional_feedback()['release_reason'],'expired')

    def test_catalog_override_never_adds_an_action_or_changes_the_fixed_anchor(self):
        feedback=dict(status='native_budget_adopted',selected_policy='budgetarmy',actions=['budgetarmy'],
            observed_frame=1500,native_effect_verified=True)
        audit=MacroRequestAudit(None,lambda *a,**k:None,feedback_supplier=lambda:feedback,catalog_supplier=defense_catalog_override)
        context=dict(game_time_seconds=100.,allowed_macro_actions=['deploydefense'],
            macro_policy_catalog=dict(deploydefense=dict(target_region='region_8_3')))
        result=audit.prepare(context)
        self.assertEqual(result['macro_policy_catalog']['deploydefense']['goal'],GOAL)
        context['allowed_macro_actions']=[]
        self.assertEqual(audit.prepare(context)['macro_policy_catalog'],context['macro_policy_catalog'])
        context['allowed_macro_actions']=['deploydefense'];context['macro_policy_catalog']['deploydefense']['target_region']='region_1_3'
        with self.assertRaisesRegex(ContractError,'region_binding'):audit.prepare(context)


if __name__=='__main__':unittest.main()
