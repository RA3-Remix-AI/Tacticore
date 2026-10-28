import copy
import json
import unittest

from .contracts import ContractError
from .macro_infrastructure import observe_infrastructure,compact_infrastructure
from .test_macro_construction import sample


class InfrastructureTests(unittest.TestCase):
    def field(self):
        builder,census=sample(1500,[(7,0)],[814])
        for row in census['own_objects']:row['hp']=5000.
        return builder,census

    def test_foundation_and_queue_are_current_presence_not_completed_technology(self):
        builder,census=self.field()
        value=compact_infrastructure(observe_infrastructure(builder,census),100.)
        self.assertEqual(value['own_template_presence_counts']['super_reactor'],1)
        self.assertEqual(value['construction_queues']['super_reactor']['observed_queue_count'],1)
        self.assertEqual(value['construction_queues']['super_reactor']['observed_paid_field_sum'],0)
        self.assertFalse(value['completed_technology_verified']);self.assertFalse(value['grants_capability'])
        self.assertNotIn('thing_id',json.dumps(value));self.assertNotIn('0x',json.dumps(value))

    def test_duplicate_builder_interfaces_count_the_same_native_queue_once(self):
        builder,census=self.field();builder['builders'].append(copy.deepcopy(builder['builders'][0]))
        self.assertEqual(observe_infrastructure(builder,census)['construction_queues']['super_reactor']['observed_queue_count'],1)

    def test_foreign_builder_queue_is_never_added_to_own_queue_counts(self):
        builder,census=self.field();builder['builders'][0]['factory']['thing_id']=888
        value=observe_infrastructure(builder,census)
        self.assertEqual(value['available_construction_yards'],0)
        self.assertEqual(value['construction_queues']['super_reactor']['observed_queue_count'],0)

    def test_enemy_or_unsynchronized_samples_are_refused(self):
        for enemy,frame in ((True,1500),(False,1530)):
            builder,census=self.field();census.update(enemy_details_read=enemy,frame=frame)
            with self.assertRaises(ContractError):observe_infrastructure(builder,census)

    def test_stale_facts_rejected_and_nested_private_fields_do_not_reach_provider(self):
        value=observe_infrastructure(*self.field());value['address']='private'
        value['construction_queues']['super_reactor']['production_id']='private'
        public=compact_infrastructure(value,100.)
        self.assertNotIn('private',json.dumps(public))
        with self.assertRaisesRegex(ContractError,'stale'):compact_infrastructure(value,103.)

    def test_false_upgrade_claim_is_replaced_with_conservative_public_meaning(self):
        value=observe_infrastructure(*self.field());value['completed_technology_verified']=True
        public=compact_infrastructure(value,100.)
        self.assertFalse(public['completed_technology_verified'])
        value['construction_queues']['super_reactor']['observed_paid_field_sum']=2001
        with self.assertRaisesRegex(ContractError,'queue'):compact_infrastructure(value,100.)

    def test_provider_gets_current_own_facts_outside_compactable_memory(self):
        from .macro_policy_runtime import MacroRequestAudit
        facts=observe_infrastructure(*self.field())
        budget=dict(status='native_delegation_observed',selected_policy=None,actions=[],observed_frame=1500,native_effect_verified=False)
        audit=MacroRequestAudit(None,lambda *a,**k:None,feedback_supplier=lambda:budget,
            infrastructure_supplier=lambda:facts)
        public=audit.prepare(dict(game_time_seconds=100.,working_memory={}))
        self.assertEqual(public['own_infrastructure']['own_template_presence_counts']['super_reactor'],1)
        with self.assertRaisesRegex(ContractError,'stale'):audit.prepare(dict(game_time_seconds=103.,working_memory={}))

    def test_real_frozen_construction_stream_projects_foundation_with_no_completion_claim(self):
        from pathlib import Path
        field=Path(__file__).resolve().parents[2]/'reports/macro-early-build-69152-20261028-v1/transport/policy-probe.jsonl'
        census=None;positive=[]
        for line in field.read_text().splitlines():
            row=json.loads(line)
            if row['kind']=='macro_observation' and 'observation' in row:census=row['observation']['construction_feedback']
            if row['kind']=='native_builder_observation' and 'observation' in row and census:
                value=compact_infrastructure(observe_infrastructure(row['observation'],census),row['observation']['frame']/15)
                if value['own_template_presence_counts']['super_reactor']:positive.append(value)
        self.assertTrue(positive)
        self.assertTrue(any(v['construction_queues']['super_reactor']['observed_queue_count'] for v in positive))
        self.assertTrue(all(v['completed_technology_verified'] is False for v in positive))


if __name__=='__main__':unittest.main()
