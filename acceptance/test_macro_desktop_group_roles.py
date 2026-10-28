"""Role evidence rejects acknowledgement-only, stale and unbound claims."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid

import assess_macro_desktop_group_roles as assessor
from integration.host_runtime.macro_infrastructure import TEMPLATES


def observation(frame,x=3500,*,action='withdraw',owner=3,members=1,census_frame=None,flag='role'):
    return dict(frame=frame,state_scores={flag:dict(score=1,group=7)},
        construction_feedback=dict(frame=frame if census_frame is None else census_frame,enemy_details_read=False,
            own_objects=[dict(type_hash=next(iter(TEMPLATES.values())),hp=100,xyz=[4404,2016,0])]),
        runtimes=[dict(group=7,native_execution_active=True,native_tactic_family=assessor.ROLE_FAMILIES[action],
            owned_groups=[dict(found=True,all_members_resolved=True,native_id=1,
                members=[dict(owner=owner,thing_id=i,address='own-'+str(i),type_hash='own-type',xyz=[x+i,2016,0])
                    for i in range(members)])])])


def feedback(action='withdraw',frame=1030):
    return dict(source='native_regional_group_observation',action=action,goal=assessor.ROLE_GOALS[action],
        target_region='region_8_3',target_policy=assessor.target_policy(action),
        native_tactic_family=assessor.ROLE_FAMILIES[action],native_execution_observed=True,
        observed_frame=frame,view_frame=frame,groups_near_home_region=1,withdrawing_native_groups=1,
        defender_groups_near_infrastructure=1,arrival_verified=False,mission_success_verified=False,
        arbitrary_xy_control=False,unit_operation_policy='native_ai')


def chain():
    session='12345678-1234-4234-8234-123456789012';plan_id='12345678-1234-4234-8234-123456789013'
    profile_hash='profile-hash';action='withdraw'
    command=str(uuid.uuid5(uuid.UUID(session),plan_id+':region:'+profile_hash))
    catalog=dict(domain='deployment',goal=assessor.ROLE_GOALS[action],target_region='region_8_3',
        target_policy=assessor.target_policy(action),maximum_duration_seconds=60,requires_existing_forward_force=True)
    context=dict(snapshot_id=1,session_id=session,player_id=3,commander_id=assessor.COMMANDER,
        game_time_seconds=60.,allowed_macro_actions=[action],macro_policy_catalog={action:catalog})
    later=dict(snapshot_id=2,session_id=session,player_id=3,commander_id=assessor.COMMANDER,
        game_time_seconds=1030/15,macro_regional_feedback=feedback())
    plan=dict(origin='model',snapshot_id=1,session_id=session,player_id=3,commander_id=assessor.COMMANDER,
        based_on_game_time_seconds=60.,expires_at_game_seconds=120.,objective_region='region_8_3',
        macro_actions=[action],macro_production=None,tactical_tasks=[],runtime_task=None)
    events=[dict(kind='model_macro_request_context',sequence=1,context=context),
        dict(kind='commander_model_response_returned',snapshot_id=1),dict(kind='plan_applied',plan_id=plan_id,plan=plan),
        dict(kind='model_macro_region_acknowledged',plan_id=plan_id,command_id=command,seq=1,actions=[action],
            goal=assessor.ROLE_GOALS[action],target_region='region_8_3'),
        *[dict(kind='macro_regional_feedback',**feedback(frame=f)) for f in (1000,1015,1030)],
        dict(kind='model_macro_request_context',sequence=2,context=later),
        dict(kind='commander_model_response_returned',snapshot_id=2),dict(kind='macro_host_stop_started')]
    for i,event in enumerate(events):
        event.update(session_id=session,commander_id=assessor.COMMANDER,player_id=3,wall_seconds=i)
        if event['kind']=='commander_model_response_returned':
            event.update(profile_revision=16,effective_hash=profile_hash,transport_receipt=dict(
                real_network_verified=True,injected_transport=False,expected_origin=True,https=True,
                loopback=False,http_status=200,response_complete=True))
    release=str(uuid.uuid5(uuid.UUID(session),plan_id+':region-release:'+profile_hash))
    raw=[dict(kind='command_acknowledged',command_id=command,seq=1,
            native=dict(last_frame=1000,deadline_frame=1800,applied_mask=2)),
        *[dict(kind='macro_observation',observation=observation(f,x,flag=assessor.ROLE_FLAGS[action])) for f,x in [(1000,3500),(1015,3540),(1030,3600)]],
        dict(kind='command_acknowledged',command_id=release,seq=2,native=dict(last_frame=1100,applied_mask=0))]
    consumers=[]
    for role in assessor.ROLE_GOALS:
        c=dict(action=role,flag=assessor.ROLE_FLAGS[role],goal=assessor.ROLE_GOALS[role],
            target_policy=assessor.target_policy(role),required_own_origin_region='region_8_3',
            native_tactic='ReactiveDefense' if role=='reinforce' else 'SimpleAttack',
            native_micro_manager='ReactiveDefenseMicroManager' if role=='reinforce' else 'GrowingAttacksMicroManager_MEDIUM',
            native_ai_selects_and_operates_group=True,unit_orders_exposed=False)
        if role!='reinforce':c.update(region_id='region_8_3',waypoint_xyz=[*assessor.HOME,0])
        consumers.append(c)
    manifest=dict(package_sha256=assessor.ATTACK_FIRST_SHA,consumers=consumers,flags=list(assessor.ROLE_FLAGS.values()))
    checks={k:True for k in ('exact_pre_execution_sources_retained','current_profile_consumed',
        'exact_public_request_context_retained','real_provider_response','macro_unit_jobs_absent',
        'native_cleanup_verified','multiple_real_model_rounds','native_feedback_in_each_followup_request','downloaded_export_matches')}
    common=dict(checks=checks,effective_hash=profile_hash,profile_revision=16,real_model_responses=2,evidence={})
    final=dict(session_id=session,cleanup_verified=True,native=dict(last_frame=1200))
    return events,raw,manifest,common,final


def evaluate_chain(events,raw,manifest,common,final):
    names=('macro_regions.py','macro_group_role_scope.py','macro_group_role_contract.py','macro_live.py')
    frozen=dict(sources=[dict(path=name,copy=name,sha256='hash') for name in names])
    with patch.object(assessor,'assess',return_value=common),patch.object(assessor,'trial',
            return_value=(dict(native=dict(player=3)),final,manifest,raw,{})),\
            patch.object(assessor,'records',return_value=events),patch.object(assessor,'load',return_value=frozen),\
            patch.object(assessor,'sha',return_value='hash'):
        return assessor.evaluate(Path('synthetic-run'),'run',Path('download'),Path('original'))


class GroupRoleEffectTests(unittest.TestCase):
    def test_withdraw_requires_an_initial_forward_force_and_pre_expiry_progress(self):
        rows=[observation(1000,3500),observation(1015,3600)]
        self.assertTrue(assessor.role_effect(rows,'role',3,1000,1016,'withdraw')['bounded_native_role_effect_verified'])
        self.assertFalse(assessor.role_effect(rows,'role',3,1000,1015,'withdraw')['bounded_native_role_effect_verified'])
        rows=[observation(1000,4200),observation(1015,4300)]
        self.assertFalse(assessor.role_effect(rows,'role',3,1000,1100,'withdraw')['bounded_native_role_effect_verified'])

    def test_regroup_requires_two_members_and_sustained_unique_frames(self):
        rows=[observation(f,4400,action='regroup',members=2) for f in (1000,1010,1020)]
        self.assertTrue(assessor.role_effect(rows,'role',3,1000,1100,'regroup')['bounded_native_role_effect_verified'])
        for bad in ([rows[0]]*4,rows[:2],[observation(f,4400,action='regroup') for f in (1000,1010,1020)]):
            self.assertFalse(assessor.role_effect(bad,'role',3,1000,1100,'regroup')['bounded_native_role_effect_verified'])

    def test_reinforce_requires_movement_and_sustained_own_infrastructure_presence(self):
        rows=[observation(f,x,action='reinforce') for f,x in ((1000,4200),(1010,4250),(1020,4300))]
        self.assertTrue(assessor.role_effect(rows,'role',3,1000,1100,'reinforce')['bounded_native_role_effect_verified'])
        static=[observation(f,4200,action='reinforce') for f in (1000,1010,1020)]
        self.assertFalse(assessor.role_effect(static,'role',3,1000,1100,'reinforce')['bounded_native_role_effect_verified'])
        for row in rows:row['construction_feedback']['own_objects']=[]
        self.assertFalse(assessor.role_effect(rows,'role',3,1000,1100,'reinforce')['bounded_native_role_effect_verified'])

    def test_foreign_wrong_family_and_unpaired_samples_never_supply_effect(self):
        with self.assertRaisesRegex(ValueError,'foreign_role_member'):
            assessor.role_effect([observation(1000,owner=4)],'role',3,1000,1100,'withdraw')
        with self.assertRaisesRegex(ValueError,'role_native_family_mismatch'):
            assessor.role_effect([observation(1000,action='reinforce')],'role',3,1000,1100,'withdraw')
        rows=[observation(1000,3500),observation(1015,3600,census_frame=1040)]
        value=assessor.role_effect(rows,'role',3,1000,1100,'withdraw')
        self.assertFalse(value['bounded_native_role_effect_verified']);self.assertEqual(value['discarded_unpaired_native_samples'],1)

    def test_census_or_view_at_deadline_cannot_complete_sustained_presence(self):
        rows=[observation(f,x,action='reinforce') for f,x in ((999,4200),(1007,4250),(1014,4300))]
        self.assertTrue(assessor.role_effect(rows,'role',3,990,1015,'reinforce')['bounded_native_role_effect_verified'])
        rows[-1]['construction_feedback']['frame']=1020
        result=assessor.role_effect(rows,'role',3,990,1015,'reinforce')
        self.assertFalse(result['bounded_native_role_effect_verified'])
        self.assertEqual(result['discarded_outside_window_census_samples'],1)
        rows[-1]['construction_feedback']['frame']=1014
        views={999:{999},1007:{1007},1014:{1015}}
        result=assessor.role_effect(rows,'role',3,990,1015,'reinforce',view_frames=views)
        self.assertFalse(result['bounded_native_role_effect_verified'])
        self.assertEqual(result['discarded_missing_or_outside_window_view_samples'],1)

    def test_role_feedback_rejects_stale_forged_success_or_boolean_counts(self):
        f=feedback();context=dict(game_time_seconds=1030/15)
        self.assertTrue(assessor.feedback_matches_request(context,f,'withdraw',1000,2000))
        for changes in ({'view_frame':900},{'goal':assessor.ROLE_GOALS['regroup']},
                {'mission_success_verified':True},{'withdrawing_native_groups':True}):
            self.assertFalse(assessor.feedback_matches_request(context,dict(f,**changes),'withdraw',1000,2000))


class GroupRoleJoinTests(unittest.TestCase):
    def test_model_expiry_cuts_effect_despite_native_diagnostic_tolerance(self):
        events,raw,manifest,common,final=chain()
        raw[0]['native']['deadline_frame']=1810
        raw=[raw[0],dict(kind='macro_observation',observation=observation(1000,3500,flag=assessor.ROLE_FLAGS['withdraw'])),
            dict(kind='macro_observation',observation=observation(1805,3600,flag=assessor.ROLE_FLAGS['withdraw'])),raw[-1]]
        raw[-1]['native']['last_frame']=1811;final['native']['last_frame']=1900
        for event in events:
            if event['kind']=='model_macro_request_context' and event['context']['snapshot_id']==2:
                event['context']['game_time_seconds']=1805/15;event['context']['macro_regional_feedback']=feedback(frame=1805)
            if event['kind']=='macro_regional_feedback' and event['observed_frame']==1030:
                event.update(feedback(frame=1805))
        result=evaluate_chain(events,raw,manifest,common,final)
        self.assertTrue(result['bounded_role_lifecycles_verified'])
        self.assertEqual(result['role_results'][0]['model_expiry_frame'],1800)
        self.assertEqual(result['role_results'][0]['effect_window_end'],1800)
        self.assertEqual(result['independently_qualified_model_deployment_roles'],[])

    def test_response_before_its_request_is_rejected(self):
        events,raw,manifest,common,final=chain()
        response=next(r for r in events if r['kind']=='commander_model_response_returned' and r['snapshot_id']==2)
        events.remove(response)
        index=next(i for i,r in enumerate(events) if r['kind']=='model_macro_request_context' and r['context']['snapshot_id']==2)
        events.insert(index,response)
        with self.assertRaisesRegex(ValueError,'group_role_response_before_request'):
            evaluate_chain(events,raw,manifest,common,final)

    def test_feedback_request_before_dispatch_or_forged_response_does_not_qualify(self):
        for mutation in ('early_request','wrong_response_profile','wrong_response_source','future_view_events'):
            events,raw,manifest,common,final=chain()
            request=next(r for r in events if r['kind']=='model_macro_request_context' and r['context']['snapshot_id']==2)
            response=next(r for r in events if r['kind']=='commander_model_response_returned' and r['snapshot_id']==2)
            if mutation=='early_request':events.remove(request);events.insert(0,request)
            if mutation=='wrong_response_profile':response['profile_revision']=15
            if mutation=='wrong_response_source':response['transport_receipt']['injected_transport']=True
            if mutation=='future_view_events':
                views=[r for r in events if r['kind']=='macro_regional_feedback']
                events=[r for r in events if r['kind']!='macro_regional_feedback']
                events.extend(views)
            with self.subTest(mutation=mutation):
                self.assertEqual(evaluate_chain(events,raw,manifest,common,final)['independently_qualified_model_deployment_roles'],[])

    def test_duplicate_dispatch_or_forged_command_identity_is_rejected(self):
        events,raw,manifest,common,final=chain()
        dispatch=next(r for r in events if r['kind']=='model_macro_region_acknowledged')
        with self.assertRaisesRegex(ValueError,'duplicate_group_role_regional_command_id'):
            evaluate_chain(events+[copy.deepcopy(dispatch)],raw,manifest,common,final)
        dispatch['command_id']='non-deterministic-command'
        with self.assertRaisesRegex(ValueError,'group_role_command_identity'):
            evaluate_chain(events,raw,manifest,common,final)

    def test_manifest_cannot_borrow_another_simple_attack_flag(self):
        events,raw,manifest,common,final=chain()
        next(r for r in manifest['consumers'] if r['action']=='withdraw')['flag']='other-simple-attack'
        with self.assertRaisesRegex(ValueError,'group_role_native_consumer_required'):
            evaluate_chain(events,raw,manifest,common,final)

    def test_valid_real_model_role_chain_qualifies_only_that_role(self):
        result=evaluate_chain(*chain())
        self.assertEqual(result['independently_qualified_model_deployment_roles'],['withdraw'])
        self.assertTrue(result['bounded_role_lifecycles_verified'])
        self.assertFalse(result['all_three_model_role_feedback_loops_verified'])
        self.assertFalse(result['full_G6_verified']);self.assertFalse(result['formal_goal_complete'])

    def test_gate_ack_alone_or_late_effect_never_qualifies(self):
        events,raw,manifest,common,final=chain()
        for records in ([r for r in raw if r['kind']!='macro_observation'],copy.deepcopy(raw)):
            if len(records)>2:records[0]['native']['deadline_frame']=1015
            self.assertEqual(evaluate_chain(events,records,manifest,common,final)['independently_qualified_model_deployment_roles'],[])

    def test_no_later_response_or_wrong_catalog_or_unbound_origin_never_qualifies(self):
        for mutation in ('response','catalog','origin','source','after_stop'):
            events,raw,manifest,common,final=chain()
            if mutation=='response':events=[r for r in events if not (r['kind']=='commander_model_response_returned' and r['snapshot_id']==2)]
            if mutation=='catalog':events[0]['context']['macro_policy_catalog']['withdraw']['requires_existing_forward_force']=False
            if mutation=='origin':events[2]['plan']['origin']='fixed'
            if mutation=='source':common['checks']['current_profile_consumed']=False
            if mutation=='after_stop':events.append(dict(kind='commander_model_call_started'))
            with self.subTest(mutation=mutation):
                self.assertEqual(evaluate_chain(events,raw,manifest,common,final)['independently_qualified_model_deployment_roles'],[])

    def test_later_native_replacement_cuts_effect_window(self):
        events,raw,manifest,common,final=chain()
        raw[-1]['seq']=3
        raw.append(dict(kind='command_acknowledged',command_id='replace',seq=2,native=dict(last_frame=1010,applied_mask=1)))
        result=evaluate_chain(events,raw,manifest,common,final)
        self.assertEqual(result['role_results'][0]['effect_window_end'],1010)
        self.assertEqual(result['independently_qualified_model_deployment_roles'],[])

    def test_duplicate_native_command_or_request_is_rejected(self):
        events,raw,manifest,common,final=chain()
        with self.assertRaisesRegex(ValueError,'duplicate_group_role_ack'):
            evaluate_chain(events,raw+[raw[0]],manifest,common,final)
        with self.assertRaisesRegex(ValueError,'duplicate_group_role_request'):
            evaluate_chain(events+[events[0]],raw,manifest,common,final)


if __name__=='__main__':unittest.main()
