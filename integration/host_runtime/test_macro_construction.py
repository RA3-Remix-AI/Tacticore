"""Native field replay and bounded model building preferences, no game mutation."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .contracts import ContractError
from .macro_construction_feedback import ConstructionFeedback,compact_construction_feedback,TARGET,PRODUCER
from .macro_construction_scope import extend_construction_scope
from . import macro_construction_scope as qualification
from . import test_macro_production_runtime as fixture
from .test_macro_production_choices import base_scope
from .macro_policy_runtime import MacroRequestAudit
from .macro_bundle import create_bundle,load_bundle

ROOT=Path(__file__).resolve().parents[2]
FIELD=ROOT/'reports/macro-early-build-69152-20261028-v1'


def sample(frame=1500,queues=(),objects=(),alive=True,producer=763):
    builder=dict(source='native_macro_builder_read_only',process_writes=0,native_calls=0,frame=frame,
        builders=[dict(factory=dict(thing_id=producer,type_hash=PRODUCER,hp=5000.),observation_available=True,
            queue_candidate=dict(nodes=[dict(kind_raw=1,template_hash=TARGET,production_id_raw=q,
                native_cost_plus_30=2000,paid_accumulator_plus_68=paid) for q,paid in queues]))] if alive else [],
        macro_entries=[dict(flag='private-reactor',state_score=1.,entries=[dict(build_type_hash_raw=TARGET)])])
    census=dict(frame=frame,enemy_details_read=False,own_objects=(
        [dict(thing_id=producer,type_hash=PRODUCER,hp=5000.)] if alive else [])+
        [dict(thing_id=i,type_hash=TARGET,hp=3400.) for i in objects])
    return builder,census


class ConstructionTests(unittest.TestCase):
    def setup_controller(self):
        self.fixture=fixture.ProductionRuntimeTests();self.fixture.setUp()
        self.controller=self.fixture.controller
        self.controller.scope=replace(self.fixture.scope,construction_flag='private-reactor')
        self.fixture.plan.macro_actions=('buildreactor','budgetarmy');self.fixture.plan.macro_production=None
        self.refresh()

    def refresh(self,**kwargs):
        builder,census=sample(**kwargs)
        self.controller.refresh(dict(build_observation=builder,observation=dict(construction_feedback=census)))

    def test_real_native_field_grants_only_reactor_and_does_not_claim_completion(self):
        scope=extend_construction_scope(base_scope(),FIELD)
        self.assertIn('buildreactor',scope.available_actions)
        self.assertNotIn('buildtech',scope.available_actions)
        self.assertTrue(scope.public()['construction_granted'])
        self.assertFalse(scope.public()['construction_completed_guaranteed'])
        _,_,manifest,rows,_=qualification.trial(FIELD/'transport')
        flag=scope.construction_flag;census=None;tracker=None
        for row in rows:
            if row['kind']=='macro_observation' and 'observation' in row:census=row['observation']['construction_feedback']
            if row['kind']=='native_builder_observation' and 'observation' in row and census:
                if tracker is None:tracker=ConstructionFeedback(row['observation'],census)
                tracker.observe(row['observation'],census,flag)
        result=tracker.public()
        self.assertEqual(result['observed_new_queue_count'],1)
        self.assertEqual(result['new_own_construction_object_observations'],1)
        self.assertEqual(result['fully_paid_queue_observations'],0)
        self.assertFalse(result['construction_completed_verified'])

    def test_missing_native_score_does_not_qualify_construction(self):
        records=copy.deepcopy(qualification.trial(FIELD/'transport'))
        for row in records[3]:
            if row['kind']=='native_builder_observation' and 'observation' in row:
                for item in row['observation']['macro_entries']:item['state_score']=0
        with patch.object(qualification,'trial',return_value=records),self.assertRaisesRegex(ContractError,'native_sequence'):
            extend_construction_scope(base_scope(),FIELD)

    def test_existing_and_full_health_objects_never_prove_completed_building(self):
        tracker=ConstructionFeedback(*sample(queues=[(7,1900)],objects=[814]))
        tracker.observe(*sample(1510,[(7,1950)],[814]),'private-reactor')
        self.assertEqual(tracker.public()['observed_new_queue_count'],0)
        self.assertEqual(tracker.public()['new_own_construction_object_observations'],0)
        self.assertFalse(tracker.release_required)
        tracker.observe(*sample(1520,[(7,2000),(8,0)],[814,815]),'private-reactor')
        feedback=compact_construction_feedback(tracker.public(),1520/15)
        self.assertEqual(feedback['new_own_construction_object_observations'],1)
        self.assertFalse(feedback['construction_completed_verified'])
        self.assertNotIn('0x',json.dumps(feedback));self.assertNotIn('thing_id',json.dumps(feedback))

    def test_invalid_samples_do_not_mutate_feedback(self):
        tracker=ConstructionFeedback(*sample());tracker.observe(*sample(1510,[(7,100)]),'private-reactor')
        old=tracker.public()
        for pair in [sample(1500),sample(1520,[(7,50)]),sample(1520,[(8,2001)])]:
            with self.assertRaises(ContractError):tracker.observe(*pair,'private-reactor')
            self.assertEqual(tracker.public(),old)
        with self.assertRaisesRegex(ContractError,'stale'):compact_construction_feedback(old,200.)

    def test_first_native_queue_releases_preference_once_and_duplicate_cannot_renew(self):
        self.setup_controller();self.assertIn('buildreactor',self.controller.available_actions(100.))
        first=self.fixture.dispatch();self.assertEqual(self.fixture.dispatch(),first)
        self.assertEqual(len(self.fixture.calls),1);self.assertEqual(self.controller.available_actions(100.),())
        self.refresh(frame=1510,queues=[(7,0)],objects=[814]);self.controller.tick(1510/15)
        self.controller.tick(1520/15)
        self.assertEqual([row[0] for row in self.fixture.calls],[['buildreactor','budgetarmy'],[]])
        self.assertEqual(self.controller.construction_feedback()['release_reason'],'queue_observed')
        self.assertEqual(self.fixture.dispatch(),first);self.assertEqual(len(self.fixture.calls),2)
        self.assertFalse(self.controller.construction_feedback()['construction_completed_verified'])

    def test_existing_native_build_or_target_revokes_new_build_authority(self):
        self.setup_controller();self.refresh(queues=[(7,0)])
        self.assertNotIn('buildreactor',self.controller.available_actions(100.))
        self.refresh(objects=[814]);self.assertNotIn('buildreactor',self.controller.available_actions(100.))
        self.refresh(frame=1470);self.assertNotIn('buildreactor',self.controller.available_actions(100.))
        with self.assertRaisesRegex(ContractError,'not_currently_available'):self.fixture.dispatch()
        self.assertEqual(self.fixture.calls,[])

    def test_builder_replacement_does_not_attribute_new_builders_queue_to_old_intent(self):
        self.setup_controller();self.fixture.dispatch()
        self.refresh(frame=1510,queues=[(7,0)],producer=900);self.controller.tick(1510/15)
        feedback=self.controller.construction_feedback()
        self.assertEqual(feedback['observed_new_queue_count'],0)
        self.assertEqual(feedback['release_reason'],'builder_unavailable')

    def test_expiry_and_stop_release_without_automatic_retry(self):
        self.setup_controller();self.fixture.dispatch();self.controller.tick(150.)
        self.assertEqual(self.controller.construction_feedback()['release_reason'],'expired')
        self.assertEqual(len(self.fixture.calls),2)
        self.setup_controller();self.fixture.dispatch();self.controller.stop()
        self.assertEqual(self.controller.construction_feedback()['release_reason'],'stopped')
        self.assertEqual(self.controller.available_actions(100.),())

    def test_unknown_dispatch_is_terminal_and_cannot_retry(self):
        self.setup_controller()
        def fail(*args):raise OSError('unknown')
        self.fixture.native.apply=fail
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):self.fixture.dispatch()
        with self.assertRaisesRegex(ContractError,'stopped'):self.fixture.dispatch()

    def test_exact_public_feedback_reaches_request_outside_historical_memory(self):
        feedback=ConstructionFeedback(*sample()).public()
        budget=dict(status='native_delegation_observed',selected_policy=None,actions=[],observed_frame=1500,native_effect_verified=False)
        audit=MacroRequestAudit(None,lambda *args,**kw:None,feedback_supplier=lambda:budget,construction_supplier=lambda:feedback)
        context=audit.prepare(dict(control_mode='macro_native',game_time_seconds=100.,working_memory={}))
        self.assertEqual(context['macro_construction_feedback']['action'],'buildreactor')
        self.assertFalse(context['macro_construction_feedback']['construction_completed_verified'])

    def test_host_can_offer_bound_construction_during_opening_without_overriding_native_heuristics(self):
        from macro_host import MacroHost
        from types import SimpleNamespace
        self.setup_controller();host=object.__new__(MacroHost)
        host.controller=self.controller;host.sampler=SimpleNamespace(scope=self.controller.scope)
        host.latest={'game_time_seconds':29.};host.event=lambda *args,**kw:None
        builder,census=sample(435)
        host.production_tick(dict(build_observation=builder,observation=dict(construction_feedback=census)))
        self.assertEqual(host.latest['macro_control']['available_actions'],[])
        builder,census=sample(450);host.latest['game_time_seconds']=30.
        host.production_tick(dict(build_observation=builder,observation=dict(construction_feedback=census)))
        self.assertIn('buildreactor',host.latest['macro_control']['available_actions'])
        self.assertEqual(self.fixture.calls,[])

    def test_model_contract_rejects_combined_build_and_production_before_dispatch(self):
        from macro_policy import validate_actions,public_descriptions
        allowed=['buildreactor','produceconscript','budgeteconomy']
        with self.assertRaisesRegex(ValueError,'conflicting_macro_work_actions'):
            validate_actions(allowed,allowed,allowed)
        for work in ('buildreactor','produceconscript'):
            self.assertEqual(validate_actions([work,'budgeteconomy'],allowed,allowed),(work,'budgeteconomy'))
            self.assertTrue(public_descriptions(allowed)[work]['exclusive_with_other_construction_or_production'])

    def test_bundle_pins_construction_evidence_and_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bundle.json'
            create_bundle(path,build=ROOT/'native-ai/macro-policy-runtime/bin/policy-v19-production-count3-20261028',
                visibility=ROOT/'reports/macro-visibility-2bb7bb23-derived-20261028-v1',
                normal=ROOT/'reports/macro-policy-budget-73924-20261028-v3',
                host_loss=ROOT/'reports/macro-policy-host-loss-73924-20261028-v4',
                expiry=ROOT/'reports/macro-policy-expiry-71320-20261028-v1',
                production=ROOT/'reports/macro-production-count-69152-20261028-v1',
                production_static=ROOT/'reports/macro-builder-static-20261028-v2',construction=FIELD)
            value,scope=load_bundle(path);self.assertEqual(value['schema_version'],4)
            self.assertIn('buildreactor',scope.available_actions)
            value['pins'][str((ROOT/'integration/host_runtime/macro_construction_feedback.py').resolve())]='0'*64
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ContractError,'not_qualified'):load_bundle(path)


if __name__=='__main__':unittest.main()
