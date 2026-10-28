import json
import unittest

from export_macro_timeline import project,outcome_event


class MacroTimelineTests(unittest.TestCase):
    def test_native_base_defense_retains_semantics_without_waypoint_progress_claim(self):
        event=dict(kind='macro_regional_feedback',source='native_regional_group_observation',action='deploydefense',
            target_region='region_8_3',observed_frame=1500,active_native_tactics=1,allocated_native_groups=1,
            moved_native_groups=1,groups_progressing_toward_region=0,native_execution_observed=True,policy_released=False,
            goal='original_native_defense_of_own_infrastructure',native_tactic_family='static_defense',
            target_policy='original_native_friendly_land_structure',defender_groups_near_infrastructure=1)
        result=project([event],{},[])[0]
        self.assertEqual(result['action'],'保护己方建筑');self.assertEqual(result['defender_groups'],1)
        self.assertFalse(result['mission_success_verified'])
        event['native_tactic_family']='simple_attack'
        with self.assertRaisesRegex(ValueError,'base_defense_binding'):project([event],{},[])

    def test_terminal_outcome_is_whitelisted_and_does_not_claim_model_win_contribution(self):
        value=dict(session_id='own',native_winner_mapping_verified=True,model_side_outcome='defeat',
            winner_player_index=4,loser_player_index=3,last_live_frame=21753,address='private')
        result=outcome_event(value,'own')
        self.assertEqual(result['winner_player'],4)
        self.assertFalse(result['model_win_contribution_verified'])
        self.assertNotIn('address',result)
        for key,bad in [('session_id','foreign'),('native_winner_mapping_verified',False),('winner_player_index',9)]:
            changed=dict(value);changed[key]=bad
            with self.assertRaisesRegex(ValueError,'unverified_outcome'):outcome_event(changed,'own')

    def test_force_presence_is_bounded_without_unit_identifiers_or_readiness_claims(self):
        forces=dict(source='bound_own_force_presence',observed_frame=1500,own_perspective=True,enemy_details_read=False,
            mobile_role_counts={'infantry':4},named_unit_counts=dict(conscript=1,flak_trooper=2,hammer_tank=0,war_bear=1),
            unclassified_objects=2,address='PRIVATE',thing_id=763,recruitability_verified=True)
        event=dict(kind='model_macro_request_context',context=dict(game_time_seconds=100.,own_forces=forces))
        result=project([event],{},[])[0]
        self.assertEqual(result['units'],[1,2,0,1]);self.assertFalse(result['recruitability_verified'])
        self.assertNotIn('PRIVATE',json.dumps(result));self.assertNotIn('thing_id',result)
        event['context']['game_time_seconds']=103.
        with self.assertRaisesRegex(ValueError,'force_source_or_time'):project([event],{},[])

    def test_public_projection_drops_free_text_private_identifiers_and_native_addresses(self):
        events=[dict(kind='model_macro_request_context',context=dict(custom_traits='private text',address='0x12345678',
            own_infrastructure=dict(own_census_frame=1500,own_template_presence_counts={name:1 for name in
                ('construction_yard','barracks','war_factory','refinery','super_reactor','battle_lab')},thing_id=763)))]
        result=json.dumps(project(events,{},[]))
        for text in ('private text','0x12345678','thing_id','763'):self.assertNotIn(text,result)

    def test_full_payment_field_and_new_object_never_become_completion_or_payment_claim(self):
        events=[dict(kind='macro_production_feedback',builder_frame=1500,action='produceflak',
            status='native_production_queue_target_observed',observed_new_queue_count=2,new_own_unit_observations=2,
            fully_paid_queue_observations=2,policy_released=True,payment_verified=True,completed_units_verified=True)]
        result=project(events,{},[])[0]
        self.assertEqual(result['queues'],2);self.assertEqual(result['fully_paid_fields'],2)
        self.assertFalse(result['completion_verified']);self.assertFalse(result['payment_verified'])

    def test_unacknowledged_model_intent_cannot_appear_as_native_confirmation(self):
        event=dict(kind='model_macro_native_acknowledged',command_id='unrecorded',seq=1,actions=['budgeteconomy'])
        with self.assertRaisesRegex(ValueError,'missing_native_ack'):project([event],{},[])

    def test_unknown_action_and_invalid_ratios_are_rejected(self):
        event=dict(kind='model_macro_native_acknowledged',command_id='known',seq=1,actions=['move_unit'])
        with self.assertRaisesRegex(ValueError,'unsupported_action'):project([event],{'known':{'seq':1}},[])
        with self.assertRaisesRegex(ValueError,'budget_bounds'):
            project([dict(kind='macro_native_feedback',native_account_shares={})],{},[])

    def test_scout_feedback_retains_bounded_counts_without_attribution_or_private_fields(self):
        event=dict(kind='macro_scouting_feedback',observed_frame=1500,active_native_tactics=0,moved_native_groups=1,
            new_legal_contacts_since_intent=11,native_execution_observed=True,policy_released=True,
            mission_success_verified=True,thing_id=763,address='0x12345678')
        result=project([event],{},[])[0]
        self.assertEqual(result['type'],'scouting');self.assertEqual(result['moved_groups'],1)
        self.assertFalse(result['exclusive_visibility_attribution_verified']);self.assertFalse(result['mission_success_verified'])
        self.assertNotIn('address',result);self.assertNotIn('thing_id',result)

    def test_region_projection_requires_fixed_destination_and_drops_completion_claim(self):
        event=dict(kind='macro_regional_feedback',source='native_regional_group_observation',action='deploydefense',
            target_region='region_8_3',observed_frame=1500,active_native_tactics=1,allocated_native_groups=2,
            moved_native_groups=2,groups_progressing_toward_region=1,native_execution_observed=True,
            policy_released=False,arrival_verified=True,mission_success_verified=True,address='0x12345678')
        value=project([event],{},[])[0]
        self.assertEqual(value['progressing_groups'],1);self.assertFalse(value['arrival_verified'])
        self.assertFalse(value['mission_success_verified']);self.assertNotIn('address',value)
        event['target_region']='region_1_3'
        with self.assertRaisesRegex(ValueError,'regional_target_mismatch'):project([event],{},[])

    def test_region_confirmation_requires_matching_destination(self):
        event=dict(kind='model_macro_region_acknowledged',command_id='known',seq=2,actions=['deployattack'],
            target_region='region_1_3',native_gate_acknowledged=True)
        ack={'known':dict(seq=2,native=dict(last_frame=1500))}
        self.assertEqual(project([event],ack,[])[0]['seq'],2)
        event['target_region']='region_8_3'
        with self.assertRaisesRegex(ValueError,'regional_target_mismatch'):project([event],ack,[])


if __name__=='__main__':unittest.main()
