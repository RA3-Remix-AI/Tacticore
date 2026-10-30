"""Synthetic own-perspective predicates; no game, file grant or model calls."""
import copy
import json
import unittest

from .contracts import ContractError
from .macro_expansion_scope import TARGETS
from .macro_expansion_feedback import ExpansionFeedback, compact_expansion_feedback, live_gate


def sample(action='buildpower',frame=1500,queues=(),targets=()):
    target,producer,domain=TARGETS[action]
    builder=dict(source='native_macro_builder_read_only',process_writes=0,native_calls=0,frame=frame,
        builders=[dict(factory=dict(thing_id=765,type_hash=producer,hp=1000.),observation_available=True,
            queue_candidate=dict(nodes=[dict(kind_raw=1,template_hash=target,production_id_raw=ident,
                native_cost_plus_30=1000,paid_accumulator_plus_68=paid) for ident,paid in queues]))],
        macro_entries=[dict(flag='expansion-'+action,dirty=False,state_score=1.,
                           entries=[dict(build_type_hash_raw=target)])])
    census=dict(frame=frame,enemy_details_read=False,own_objects=[dict(thing_id=765,type_hash=producer,hp=1000.)]+
                [dict(thing_id=ident,type_hash=target,hp=100.) for ident in targets])
    power=dict(native_supply=100,native_demand=200,native_energy_sufficient=False) if action=='buildpower' else \
          dict(native_supply=200,native_demand=100,native_energy_sufficient=True)
    readiness=dict(kind='native_own_readiness_observation',frame=frame,own_perspective=True,
        native_calls=0,process_writes=0,enemy_details_read=False,power=power,own_objects=[dict(
            thing_id=765,type_hash=producer,hp=1000.,currently_registered=True,named_template_supported=True,
            object_status={key:False for key in ('destroyed','under_construction','sold','reconstructing',
                'not_in_world','pending_construction','unpacking')})])
    dependency=dict(kind='native_required_object_dependency_observation',frame=frame,owner_index=3,
        native_calls=0,process_writes=0,enemy_details_read=False,own_lifecycles=[],
        session_identity=dict(game='0x10000',owner='0x20000',owner_index=3,template_factory='0x30000'),
        actions=[dict(action=action,target_type_hash=target,target_template_loaded=True,prerequisite_met=True,
            sdk_required_objects_match=True,native_required_objects_met=True,required_object_evidence=[],
            enqueue_admission_candidates=[dict(producer_thing_id=765,producer_type_hash=producer,
                native_factory_category_match=True,native_enqueue_admission_met=True,unresolved_admission_conditions=[],
                native_stop=False,native_unpacking=False)])])
    return dict(observation=dict(frame=frame,construction_feedback=census),build_observation=builder,
                readiness=readiness,dependency=dependency)


class ExpansionFeedbackTests(unittest.TestCase):
    def assertCode(self,code,call):
        with self.assertRaises(ContractError) as caught:call()
        self.assertEqual(code,caught.exception.code)

    def test_all_defined_targets_have_parameterised_queue_feedback(self):
        for action in TARGETS:
            data=sample(action)
            if action=='buildrefinery':data['dependency']['actions'][0]['native_open_resource_node_available']=True
            with self.subTest(action=action):
                tracker=ExpansionFeedback(action,data,100.);tracker.bind_native_window(1501,1600)
                observed=sample(action,1502,queues=[(18,10)])
                tracker.observe(observed,'expansion-'+action)
                value=compact_expansion_feedback(tracker.public(),1502/15)
                self.assertEqual(value['action'],action);self.assertEqual(value['observed_new_queue_count'],1)
                self.assertTrue(tracker.release_required)
                self.assertFalse(value['payment_verified']);self.assertFalse(value['unit_exit_verified'])

    def test_unknown_dependency_admission_or_power_never_grants_availability(self):
        for key in ('prerequisite_met','sdk_required_objects_match','native_required_objects_met'):
            data=sample();data['dependency']['actions'][0][key]=None
            self.assertCode('macro_expansion_native_prerequisite_unknown_or_missing',lambda:live_gate('buildpower',data,100.))
        data=sample();data['dependency']['actions'][0]['enqueue_admission_candidates'][0]['native_enqueue_admission_met']=None
        self.assertCode('macro_expansion_unique_ready_producer_required',lambda:live_gate('buildpower',data,100.))
        data=sample('producesickle');data['readiness']['power']['native_energy_sufficient']=None
        self.assertCode('macro_expansion_power_unknown_or_unavailable',lambda:live_gate('producesickle',data,100.))

    def test_refinery_open_node_unknown_is_not_a_product_probe_permission(self):
        data=sample('buildrefinery')
        self.assertCode('macro_expansion_open_resource_node_unknown',lambda:live_gate('buildrefinery',data,100.))

    def test_under_construction_destroyed_or_foreign_producer_is_not_ready(self):
        for key in ('under_construction','destroyed','not_in_world','unpacking'):
            data=sample();data['readiness']['own_objects'][0]['object_status'][key]=True
            self.assertCode('macro_expansion_unique_ready_producer_required',lambda:live_gate('buildpower',data,100.))
        data=sample();data['observation']['construction_feedback']['enemy_details_read']=True
        self.assertCode('macro_production_observation_source',lambda:live_gate('buildpower',data,100.))

    def test_repeat_queue_samples_count_once_and_after_window_does_not_backfill(self):
        tracker=ExpansionFeedback('buildpower',sample(),100.);tracker.bind_native_window(1501,1510)
        tracker.observe(sample(frame=1502,queues=[(18,10)]),'expansion-buildpower')
        tracker.observe(sample(frame=1503,queues=[(18,20)]),'expansion-buildpower')
        tracker.observe(sample(frame=1511,queues=[(18,30),(19,0)]),'expansion-buildpower')
        self.assertEqual(tracker.public()['observed_new_queue_count'],1)
        self.assertEqual(tracker.public()['additional_queue_observations_after_window'],1)

    def test_payment_regression_does_not_commit_partial_feedback(self):
        tracker=ExpansionFeedback('buildpower',sample(),100.);tracker.bind_native_window(1501,1600)
        tracker.observe(sample(frame=1502,queues=[(18,20)]),'expansion-buildpower')
        before=tracker.public()
        self.assertCode('macro_expansion_feedback_queue_regression',
            lambda:tracker.observe(sample(frame=1503,queues=[(18,10)]),'expansion-buildpower'))
        self.assertEqual(tracker.public(),before)

    def test_unproven_completion_bool_is_not_a_native_completion_edge(self):
        tracker=ExpansionFeedback('buildpower',sample(),100.);tracker.bind_native_window(1501,1600)
        value=sample(frame=1502,targets=[99])
        value['dependency']['own_lifecycles']=[dict(thing_id=99,type_hash=TARGETS['buildpower'][0],
            thing_address='private',template_address='private-template',construction_completed=True)]
        tracker.observe(value,'expansion-buildpower')
        self.assertEqual(tracker.public()['native_completion_edges_observed'],0)

    def test_raw_completion_edge_requires_both_samples_in_the_native_window(self):
        def state(frame,active):
            data=sample(frame=frame,targets=[99])
            data['dependency']['own_lifecycles']=[dict(thing_id=99,type_hash=TARGETS['buildpower'][0],
                thing_address='private',template_address='private-template',currently_registered=True,
                named_template_supported=True,hp=100.,native_unpack_completion_notified=not active,
                object_status=dict(destroyed=False,sold=False,not_in_world=False,under_construction=active,
                    pending_construction=False,unpacking=active,reconstructing=False),
                unpack=dict(native_unpack_in_progress=active,native_unpack_duration_frames=10,native_unpack_started_frame=1490))]
            return data
        for ending,expected in ((1503,1),(1511,0)):
            tracker=ExpansionFeedback('buildpower',sample(),100.);tracker.bind_native_window(1501,1510)
            tracker.observe(state(1502,True),'expansion-buildpower')
            tracker.observe(state(ending,False),'expansion-buildpower')
            self.assertEqual(tracker.public()['native_completion_edges_observed'],expected)

    def test_session_identity_change_does_not_mutate_feedback(self):
        data=sample()
        tracker=ExpansionFeedback('buildpower',data,100.);before=tracker.public()
        changed=sample(frame=1502);changed['dependency']['session_identity']={'game':3,'owner':2}
        self.assertCode('macro_expansion_feedback_session_changed',lambda:tracker.observe(changed,'expansion-buildpower'))
        self.assertEqual(tracker.public(),before)

    def test_slow_macro_component_or_old_readiness_is_not_fresh_or_attributable(self):
        data=sample();data['observation']['frame']=1441
        self.assertCode('macro_expansion_readiness_missing_or_stale',lambda:live_gate('buildpower',data,100.))
        tracker=ExpansionFeedback('buildpower',sample(),100.);tracker.bind_native_window(1501,1510)
        changed=sample(frame=1502,queues=[(18,0)]);changed['readiness']['frame']=1441
        self.assertCode('macro_expansion_feedback_dependency_stale',lambda:tracker.observe(changed,'expansion-buildpower'))
        self.assertEqual(tracker.public()['observed_new_queue_count'],0)

    def test_compact_projection_removes_private_identity_and_rejects_stale_or_forged_numbers(self):
        tracker=ExpansionFeedback('buildpower',sample(),100.)
        raw=dict(tracker.public(),address='private',native_raw='private',thing_id=123)
        compact=compact_expansion_feedback(raw,100.)
        self.assertNotIn('private',json.dumps(compact));self.assertNotIn('thing_id',compact)
        raw['observed_new_queue_count']=True
        self.assertCode('macro_expansion_feedback_invalid_or_stale',lambda:compact_expansion_feedback(raw,100.))
        self.assertCode('macro_expansion_feedback_invalid_or_stale',lambda:compact_expansion_feedback(tracker.public(),200.))
