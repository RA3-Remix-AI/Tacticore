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
from .macro_scouting import ScoutingScope,MacroScoutingController,ScoutFeedback,compact_scout_feedback
from .test_macro_production_feedback import sample

def observed(frame=1500,x=0,contact=False,active=True):
    obs=dict(frame=frame,source='native_macro_read_only',native_calls=0,process_writes=0,native=dict(player='private-owner'),
        state_scores={'private-scout':dict(domain='strategic',group='private-state',score=1.)},
        runtimes=[dict(group='private-state',native_execution_active=active,owned_groups=[dict(found=True,all_members_resolved=True,
            native_id=9,members=[dict(thing_id=44,owner='private-owner',xyz=[x,0,0])])])])
    view=dict(game_time_seconds=frame/15,battlefield=dict(viewer_player_id=3,visibility_verified=True,
        contacts=[dict(contact_id='lawful-contact',relation='enemy',currently_visible=True)] if contact else []))
    return obs,view

class ScoutingTests(unittest.TestCase):
    def setUp(self):
        self.sid=str(uuid.uuid4());self.calls=[];self.events=[]
        b=BudgetScope('a'*64,{},('private-scout',),dict(budgetarmy='private-army',budgeteconomy='private-economy'),{})
        self.scope=ScoutingScope(b,'private-flak',{},scout_flag='private-scout')
        def apply(actions,duration,ident):self.calls.append((actions,duration,ident));return dict(seq=len(self.calls))
        t=SimpleNamespace(session=dict(session_id=self.sid,mod_sha256='a'*64),apply=apply,close=lambda:None)
        self.controller=MacroScoutingController(t,self.scope,self.sid,'b'*64,lambda k,**v:self.events.append((k,v)))
        self.plan=SimpleNamespace(origin='model',session_id=self.sid,commander_id=COMMANDER,player_id=3,
            based_on_game_time_seconds=100.,expires_at_game_seconds=200.,tactical_tasks=(),runtime_task=None,
            macro_actions=('scout','budgetarmy'),macro_production=None,plan_id='one')
        self.refresh()

    def refresh(self,frame=1500,x=0,contact=False,active=True):
        obs,view=observed(frame,x,contact,active);builder,census=sample(frame)
        obs['construction_feedback']=census
        self.controller.observe_snapshot(view);self.controller.refresh(dict(observation=obs,build_observation=builder))

    def dispatch(self):return self.controller.dispatch(self.plan,100.,effective_hash='b'*64)

    def test_scoped_once_expiry_clears_all_preferences_without_unit_commands(self):
        first=self.dispatch();self.assertEqual(self.dispatch(),first)
        self.assertEqual(self.calls[0][:2],(['scout','budgetarmy'],1350));self.assertTrue(self.controller.busy)
        self.assertEqual(self.controller.available_actions(100.),())
        self.controller.tick(190.);self.controller.tick(191.)
        self.assertEqual(len(self.calls),2);self.assertEqual(self.calls[-1][:2],([],1));self.assertFalse(self.controller.busy)
        self.assertEqual(self.controller.scouting_feedback()['release_reason'],'expired')

    def test_native_group_movement_and_lawful_contacts_are_separate_observations(self):
        self.dispatch();self.refresh(1510,20,True)
        value=compact_scout_feedback(self.controller.scouting_feedback(),1510/15)
        self.assertEqual(value['moved_native_groups'],1);self.assertEqual(value['new_legal_contacts_since_intent'],1)
        self.assertTrue(value['native_execution_observed']);self.assertFalse(value['intelligence_exclusively_attributed_to_scout'])
        self.assertNotIn('private',json.dumps(value));self.assertFalse(value['arbitrary_region_selected'])
        self.refresh(1520,20,True,False);self.controller.tick(1520/15)
        self.assertEqual(self.controller.scouting_feedback()['release_reason'],'native_execution_inactive')

    def test_missing_stale_foreign_and_observer_samples_do_not_authorize(self):
        for mutate in ('stale','foreign','observer'):
            obs,view=observed()
            if mutate=='stale':obs['frame']=1400
            elif mutate=='foreign':obs['runtimes'][0]['owned_groups'][0]['members'][0]['owner']='foreign'
            else:view['battlefield']['viewer_player_id']=2
            with self.subTest(mutate=mutate),self.assertRaises(ContractError):ScoutFeedback(obs,view,'private-scout')
        self.controller.scout_latest=None
        with self.assertRaisesRegex(ContractError,'not_currently_available'):self.dispatch()
        self.assertEqual(self.calls,[])

    def test_production_combination_revision_and_id_reuse_are_refused_before_delivery(self):
        self.plan.macro_actions=('scout','produceflak')
        with self.assertRaises(ContractError):self.dispatch()
        self.assertEqual(self.calls,[])
        self.plan.macro_actions=('scout',);self.dispatch();self.plan.expires_at_game_seconds=180.
        with self.assertRaisesRegex(ContractError,'id_conflict'):self.dispatch()
        self.assertEqual(len(self.calls),1)

    def test_unknown_delivery_stops_controller_and_never_retries(self):
        def fail(*a):raise RuntimeError('private native error')
        self.controller.transport.apply=fail
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):self.dispatch()
        self.assertTrue(self.controller.stopped)
        with self.assertRaises(ContractError):self.dispatch()

    def test_original_budget_and_production_work_still_use_their_normal_controller(self):
        self.plan.macro_actions=('budgetarmy',);self.dispatch()
        self.assertEqual(self.calls[0][0],['budgetarmy']);self.assertIsNone(self.controller.scouting_feedback())
        self.plan.plan_id='two';self.plan.macro_actions=('produceflak',);self.plan.macro_production=SimpleNamespace(action='produceflak',additional_count=2)
        self.dispatch();self.assertTrue(self.controller.production_busy);self.assertNotIn('scout',self.controller.available_actions(100.))

    def test_stop_ends_intents_and_public_feedback_reaches_next_model_context(self):
        self.dispatch();self.refresh(1510,20,True);self.controller.stop()
        budget=dict(status='native_delegation_observed',selected_policy=None,actions=[],observed_frame=1510,native_effect_verified=False)
        audit=MacroRequestAudit(None,lambda *a,**k:None,feedback_supplier=lambda:budget,scouting_supplier=self.controller.scouting_feedback)
        payload=audit.prepare(dict(game_time_seconds=1510/15,working_memory={}))
        self.assertTrue(payload['macro_scouting_feedback']['policy_released'])
        self.assertEqual(payload['macro_scouting_feedback']['new_legal_contacts_since_intent'],1)
        with self.assertRaisesRegex(ContractError,'stale'):audit.prepare(dict(game_time_seconds=110.,working_memory={}))

    def test_real_fixed_field_stream_has_bound_native_movement_and_lawful_feedback(self):
        from .macro_scouting import extend_scouting_scope
        from .macro_policy_runtime import verify_budget_scope
        from .macro_production_runtime import verify_production_preference_scope
        root=Path(__file__).resolve().parents[2]
        b=verify_budget_scope(root/'reports/macro-policy-budget-73924-20261028-v3',root/'reports/macro-policy-host-loss-73924-20261028-v4',
            root/'reports/macro-policy-expiry-71320-20261028-v1',root/'native-ai/macro-policy-runtime/bin/policy-v25-desktop-technology-budget-20261028')
        p=verify_production_preference_scope(b,root/'reports/macro-production-count-69152-20261028-v1',root/'reports/macro-builder-static-20261028-v2')
        self.assertNotIn('scout',p.available_actions)
        scoped=extend_scouting_scope(p,root/'reports/macro-scout-feedback-77972-20261028-v1')
        self.assertIn('scout',scoped.available_actions);self.assertFalse(scoped.public()['arbitrary_region_selection_granted'])

    def test_positive_gate_without_native_group_movement_does_not_qualify(self):
        from . import macro_scouting as q
        root=Path(__file__).resolve().parents[2];directory=root/'reports/macro-scout-feedback-77972-20261028-v1'
        raw=copy.deepcopy(q.trial(directory/'transport'))
        for r in raw[3]:
            for t in r.get('observation',{}).get('runtimes',[]):
                for g in t.get('owned_groups',[]):
                    for m in g.get('members',[]):m['xyz']=[0,0,0]
        from .test_macro_production_choices import base_scope
        with patch.object(q,'trial',return_value=raw),self.assertRaisesRegex(ContractError,'effect_or_legal_feedback_missing'):
            q.extend_scouting_scope(base_scope(),directory)

    def test_schema6_pins_scout_proof_and_old_schema_does_not_grant_scout(self):
        from .macro_bundle import create_bundle,load_bundle
        root=Path(__file__).resolve().parents[2]
        args=dict(build=root/'native-ai/macro-policy-runtime/bin/policy-v25-desktop-technology-budget-20261028',
            visibility=root/'reports/macro-visibility-2bb7bb23-derived-20261028-v1',normal=root/'reports/macro-policy-budget-73924-20261028-v3',
            host_loss=root/'reports/macro-policy-host-loss-73924-20261028-v4',expiry=root/'reports/macro-policy-expiry-71320-20261028-v1',
            production=root/'reports/macro-production-count-69152-20261028-v1',production_static=root/'reports/macro-builder-static-20261028-v2',
            construction=root/'reports/macro-early-build-69152-20261028-v1',technology_budget=root/'reports/macro-budget-tech-77436-20261028-v3')
        with tempfile.TemporaryDirectory() as d:
            old=Path(d)/'old.json';new=Path(d)/'scout.json'
            create_bundle(old,**args);self.assertNotIn('scout',load_bundle(old)[1].available_actions)
            create_bundle(new,**args,scouting=root/'reports/macro-scout-feedback-77972-20261028-v1')
            value,scope=load_bundle(new);self.assertEqual(value['schema_version'],6);self.assertIn('scout',scope.available_actions)
            value['pins'][str((root/'reports/macro-scout-feedback-77972-20261028-v1/lawful-snapshots.jsonl').resolve())]='0'*64
            new.write_text(json.dumps(value))
            with self.assertRaisesRegex(ContractError,'not_qualified'):load_bundle(new)

if __name__=='__main__':unittest.main()
