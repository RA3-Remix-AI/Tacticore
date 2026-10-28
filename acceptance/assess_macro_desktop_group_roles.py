"""Independently join real model group-role intents, native effects and feedback.

Only bounded regroup/withdraw/reinforce effects are assessed. Native AI selects
and operates the units. No arrival, combat success or whole-goal claim is made.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'acceptance')]
from assess_macro_desktop import assess,records,load,sha
from assess_macro_group_roles import tracks,movement,ATTACK_FIRST_SHA
from integration.host_runtime.macro_group_role_contract import ROLE_GOALS,ROLE_FAMILIES,HOME_REGION
from integration.host_runtime.macro_policy_runtime import trial,COMMANDER

HOME=(4404.11669921875,2016.0247802734375)
ROLE_FLAGS={role:'/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_'+alias
    for role,alias in {'regroup':'build_airfield','withdraw':'buildtech','reinforce':'economyrefinery'}.items()}
DISPATCHES=('model_macro_native_acknowledged','model_macro_production_acknowledged',
    'model_macro_construction_acknowledged','model_macro_scout_acknowledged','model_macro_region_acknowledged')


def target_policy(action):
    return 'original_native_most_recently_attacked_own_base' if action=='reinforce' else 'fixed_public_own_home_start_waypoint'


def role_effect(observations,flag,owner,begin,end,action,*,view_frames=None,through_frame=None):
    """Replay paired native samples in [ack, min(expiry, release, replacement))."""
    if action not in ROLE_GOALS:raise ValueError('group_role_action_required')
    if any(type(v) is not int or v<0 for v in (begin,end)) or end<begin:
        raise ValueError('group_role_effect_window')
    eligible=[];outside=0;unpaired_view=0
    for obs in observations:
        frame=obs['frame']
        if begin<=frame<end:
            census=obs['construction_feedback'].get('frame')
            # A paired read may be close in age yet cross the model deadline.
            # Every sample contributing to the effect must itself precede it.
            if type(census) is not int or not begin<=census<end:
                outside+=1;continue
            if through_frame is not None and frame>through_frame:continue
            if view_frames is not None and not any(type(view) is int and begin<=view<end
                    and -15<=view-frame<=30 for view in view_frames.get(frame,())):
                unpaired_view+=1;continue
        eligible.append(obs)
    members,active,inactive,discarded=tracks(eligible,flag,owner,begin,end,ROLE_FAMILIES[action])
    summaries={key:movement(track,HOME) for key,track in members.items()}
    def sustained(frames):
        frames=set(frames)
        return len(frames)>=3 and max(frames)-min(frames)>=15
    near_home={key for key,track in members.items()
        if sustained(frame for frame,point,_ in track if math.dist(point[:2],HOME)<=500)}
    near_infrastructure={key for key,track in members.items()
        if sustained(frame for frame,_,near in track if near)}
    withdrawal={key for key,value in summaries.items() if value['samples']>=2
        and value['first_target_distance']>750 and value['displacement']>10 and value['target_progress']>50}
    reinforcement={key for key in near_infrastructure if summaries[key]['displacement']>10}
    positive={'regroup':len(near_home)>=2,'withdraw':bool(withdrawal),'reinforce':bool(reinforcement)}[action]
    return dict(own_member_tracks=len(members),active_native_task_samples=active,
        discarded_unpaired_native_samples=discarded,discarded_outside_window_census_samples=outside,
        discarded_missing_or_outside_window_view_samples=unpaired_view,native_inactive_after_window_samples=inactive,
        own_members_sustained_near_home=len(near_home),own_members_sustained_near_infrastructure=len(near_infrastructure),
        own_forward_members_progressing_home=len(withdrawal),own_moving_members_near_infrastructure=len(reinforcement),
        own_tracks=list(summaries.values()),bounded_native_role_effect_verified=positive,
        effect_within_model_maximum_60_seconds=0<end-begin<=900)


def feedback_matches_request(context,feedback,action,begin,next_begin):
    """Check public role semantics and freshness; raw effect is checked separately."""
    frame=feedback.get('observed_frame');view=feedback.get('view_frame')
    count='groups_near_home_region' if action=='regroup' else 'withdrawing_native_groups' if action=='withdraw' else 'defender_groups_near_infrastructure'
    return (type(frame) is int and type(view) is int and begin<frame<next_begin
        and all(-15<=context.get('game_time_seconds',-100)*15-value<=30 for value in (frame,view))
        and feedback.get('source')=='native_regional_group_observation'
        and feedback.get('action')==action and feedback.get('goal')==ROLE_GOALS[action]
        and feedback.get('target_region')==HOME_REGION and feedback.get('target_policy')==target_policy(action)
        and feedback.get('native_tactic_family')==ROLE_FAMILIES[action]
        and feedback.get('native_execution_observed') is True
        and type(feedback.get(count)) is int and 0<feedback[count]<=8192
        and feedback.get('arrival_verified') is False and feedback.get('mission_success_verified') is False
        and feedback.get('arbitrary_xy_control') is False and feedback.get('unit_operation_policy')=='native_ai')


def unique_index(rows,key,label):
    result={}
    for row in rows:
        value=key(row)
        if value in result:raise ValueError('duplicate_group_role_'+label)
        result[value]=row
    return result


def verify_consumers(manifest):
    if manifest.get('package_sha256')!=ATTACK_FIRST_SHA:raise ValueError('group_role_package_required')
    consumers=unique_index(manifest['consumers'],lambda row:row['action'],'consumer')
    for action,goal in ROLE_GOALS.items():
        c=consumers.get(action,{})
        if (c.get('flag')!=ROLE_FLAGS[action] or c.get('goal')!=goal or c.get('target_policy')!=target_policy(action)
                or c.get('native_tactic')!=('ReactiveDefense' if action=='reinforce' else 'SimpleAttack')
                or c.get('native_micro_manager')!=('ReactiveDefenseMicroManager' if action=='reinforce' else 'GrowingAttacksMicroManager_MEDIUM')
                or c.get('required_own_origin_region')!=HOME_REGION
                or c.get('native_ai_selects_and_operates_group') is not True or c.get('unit_orders_exposed') is not False):
            raise ValueError('group_role_native_consumer_required')
        if action!='reinforce' and (c.get('region_id')!=HOME_REGION or c.get('waypoint_xyz',[])[:2]!=list(HOME)):
            raise ValueError('group_role_native_home_anchor_required')
    return consumers


def response_bound(request,response,common,session):
    receipt=response.get('transport_receipt') or {}
    return (response.get('snapshot_id')==request['context']['snapshot_id']
        and all(response.get(k)==v for k,v in dict(session_id=session,player_id=3,commander_id=COMMANDER,
            profile_revision=common['profile_revision'],effective_hash=common['effective_hash']).items())
        and all(receipt.get(k)==v for k,v in dict(real_network_verified=True,injected_transport=False,
            expected_origin=True,https=True,loopback=False,http_status=200,response_complete=True).items()))


def evaluate(run,run_id,download,original):
    common=assess(run,run_id,download,original);host=run/'battle-host'
    pre,final,manifest,raw,native_evidence=trial(ROOT/'reports'/('macro-desktop-'+run_id))
    consumers=verify_consumers(manifest)
    events=records(host/'host-events.jsonl')
    positions={id(row):index for index,row in enumerate(events)}
    plans=unique_index([r for r in events if r['kind']=='plan_applied'],lambda r:r['plan_id'],'plan')
    requests=unique_index([r for r in events if r['kind']=='model_macro_request_context'],lambda r:r['context']['snapshot_id'],'request')
    responses=unique_index([r for r in events if r['kind']=='commander_model_response_returned'],lambda r:r['snapshot_id'],'response')
    for snapshot_id,response in responses.items():
        request=requests.get(snapshot_id)
        if request is None:raise ValueError('group_role_response_without_request')
        if positions[id(response)]<=positions[id(request)]:raise ValueError('group_role_response_before_request')
    regional=[r for r in events if r['kind']=='model_macro_region_acknowledged']
    for key in ('command_id','seq','plan_id'):unique_index(regional,lambda r:r[key],'regional_'+key)
    dispatches=[r for r in regional if set(r['actions'])&set(ROLE_GOALS)]
    acks=unique_index([r for r in raw if r['kind']=='command_acknowledged'],lambda r:r['command_id'],'ack')
    unique_index(acks.values(),lambda r:r['seq'],'native_seq')
    observations=[r['observation'] for r in raw if r['kind']=='macro_observation' and 'observation' in r]
    flags={action:c['flag'] for action,c in consumers.items()};results=[]
    for d in dispatches:
        roles=set(d['actions'])&set(ROLE_GOALS)
        if len(roles)!=1:raise ValueError('group_role_dispatch_conflict')
        action=next(iter(roles));goal=ROLE_GOALS[action]
        if d.get('goal')!=goal or d.get('target_region')!=HOME_REGION:raise ValueError('group_role_dispatch_goal')
        plan=plans.get(d['plan_id'],{}).get('plan',{});request=requests.get(plan.get('snapshot_id'),{})
        context=request.get('context',{});ack=acks.get(d['command_id'],{});native=ack.get('native',{})
        expected_command=str(uuid.uuid5(uuid.UUID(final['session_id']),d['plan_id']+':region:'+common['effective_hash']))
        if d['command_id']!=expected_command:raise ValueError('group_role_command_identity')
        begin=native.get('last_frame',0);deadline=native.get('deadline_frame',0)
        if type(begin) is not int or type(deadline) is not int:raise ValueError('group_role_native_frame_type')
        release_id=str(uuid.uuid5(uuid.UUID(final['session_id']),d['plan_id']+':region-release:'+common['effective_hash']))
        release=acks.get(release_id);release_frame=release['native']['last_frame'] if release else final['native']['last_frame']
        # Any later native command can replace gates. Do not credit movement
        # after a budget/production replacement to an older regional intent.
        replacement=min((r['native']['last_frame'] for r in acks.values() if r['seq']>d['seq']),default=0xffffffff)
        expires=plan.get('expires_at_game_seconds');based=plan.get('based_on_game_time_seconds')
        finite_times=type(expires) in (int,float) and type(based) in (int,float) and all(math.isfinite(v) for v in (expires,based))
        model_end=math.floor(expires*15) if finite_times else begin
        end=min(deadline,release_frame,replacement,model_end)
        views={};view_events=[]
        for event in events:
            if (event['kind']=='macro_regional_feedback' and event.get('action')==action
                    and event.get('goal')==goal and event.get('target_region')==HOME_REGION
                    and event.get('session_id')==final['session_id'] and event.get('player_id')==3
                    and event.get('commander_id')==COMMANDER and type(event.get('observed_frame')) is int
                    and positions[id(event)]>positions[id(d)]):
                views.setdefault(event['observed_frame'],set()).add(event.get('view_frame'))
                view_events.append(event)
        effect=role_effect(observations,flags[action],pre['native']['player'],begin,max(begin,end),action,view_frames=views)
        next_begin=min((acks[x['command_id']]['native']['last_frame'] for x in regional
            if x['seq']>d['seq'] and x['command_id'] in acks),default=0xffffffff)
        later=[]
        for snapshot_id,r in requests.items():
            c=r['context'];f=c.get('macro_regional_feedback') or {};frame=f.get('observed_frame')
            prior_views={}
            for event in view_events:
                if positions[id(event)]<positions[id(r)]:
                    prior_views.setdefault(event['observed_frame'],set()).add(event.get('view_frame'))
            if (snapshot_id not in responses or positions[id(r)]<=positions[id(d)]
                    or not response_bound(r,responses[snapshot_id],common,final['session_id'])
                    or c.get('session_id')!=final['session_id']
                    or c.get('commander_id')!=COMMANDER or c.get('player_id')!=3
                    or not feedback_matches_request(c,f,action,begin,next_begin)
                    or f.get('view_frame') not in prior_views.get(frame,())
                    or not any(o['frame']==frame for o in observations)):
                continue
            upto=role_effect(observations,flags[action],pre['native']['player'],begin,max(begin,end),action,
                view_frames=prior_views,through_frame=frame)
            if upto['bounded_native_role_effect_verified']:
                later.append(dict(sequence=r['sequence'],snapshot_id=snapshot_id,feedback=f))
        catalog=context.get('macro_policy_catalog',{}).get(action,{})
        catalog_bound=(action in context.get('allowed_macro_actions',[])
            and catalog.get('domain')=='deployment' and catalog.get('goal')==goal
            and catalog.get('target_region')==HOME_REGION and catalog.get('target_policy')==target_policy(action)
            and catalog.get('maximum_duration_seconds')==60
            and (action!='withdraw' or catalog.get('requires_existing_forward_force') is True))
        expected_mask=sum(1<<manifest['flags'].index(flags[a]) for a in d['actions'])
        model_bound=(plan.get('origin')=='model' and plan.get('macro_actions')==d['actions']
            and plan.get('objective_region')==HOME_REGION and plan.get('session_id')==final['session_id']
            and plan.get('commander_id')==COMMANDER and plan.get('player_id')==3
            and not plan.get('tactical_tasks') and plan.get('runtime_task') is None and plan.get('macro_production') is None
            and plan.get('snapshot_id') in responses and context.get('session_id')==final['session_id']
            and response_bound(request,responses[plan['snapshot_id']],common,final['session_id'])
            and positions[id(responses[plan['snapshot_id']])]<positions[id(d)]
            and positions[id(plans[d['plan_id']])]>positions[id(responses[plan['snapshot_id']])]
            and context.get('commander_id')==COMMANDER and context.get('player_id')==3
            and plan.get('based_on_game_time_seconds')==context.get('game_time_seconds'))
        bounded=(finite_times and 0<expires-based<=60
            and 0<deadline-begin<=900 and begin>=math.floor(based*15)-15 and deadline<=math.ceil(expires*15)+15)
        results.append(dict(plan_id=d['plan_id'],action=action,goal=goal,target_region=HOME_REGION,
            native_seq=d['seq'],begin_frame=begin,native_deadline_frame=deadline,model_expiry_frame=model_end,effect_window_end=end,
            release_or_stop_frame=release_frame,next_native_command_frame=replacement,
            real_model_plan_bound=model_bound,qualified_goal_in_actual_request=catalog_bound,
            native_ack_matches=ack.get('seq')==d['seq'] and native.get('applied_mask')==expected_mask,
            bounded_native_duration=bounded,
            known_release_or_terminal_cleanup=(release is not None and release['native']['applied_mask']==0
                and release_frame>=begin) or release is None and final['cleanup_verified'] is True,
            **effect,later_real_model_feedback=later,feedback_returned_to_later_model_verified=bool(later)))
    frozen=load(host/'sources.json')['sources'];names={'macro_regions.py','macro_group_role_scope.py','macro_group_role_contract.py','macro_live.py'}
    sources=[r for r in frozen if Path(r['path']).name in names]
    source_valid={Path(r['path']).name for r in sources}==names and all(sha(host/'source'/r['copy'])==r['sha256'] for r in sources)
    subset=('exact_pre_execution_sources_retained','current_profile_consumed','exact_public_request_context_retained',
        'real_provider_response','macro_unit_jobs_absent','native_cleanup_verified','multiple_real_model_rounds',
        'native_feedback_in_each_followup_request','downloaded_export_matches')
    shared={**{key:common['checks'][key] for key in subset},'pre_execution_role_sources_retained':source_valid}
    stop=next((i for i,r in enumerate(events) if r['kind']=='macro_host_stop_started'),None)
    quiet=stop is not None and not any(r['kind']=='commander_model_call_started' or r['kind'].endswith('_prepared')
        or r['kind'] in DISPATCHES for r in events[stop+1:])
    lifecycle=lambda r:all(r[k] for k in ('real_model_plan_bound','qualified_goal_in_actual_request',
        'native_ack_matches','bounded_native_duration','known_release_or_terminal_cleanup'))
    positive=lambda r:r['bounded_native_role_effect_verified'] and r['effect_within_model_maximum_60_seconds']
    bounded=bool(results) and all(lifecycle(r) for r in results)
    qualified=[action for action in ROLE_GOALS if all(shared.values()) and bounded and quiet
        and any(r['action']==action and positive(r) and r['feedback_returned_to_later_model_verified'] for r in results)]
    return dict(kind='desktop_model_original_native_group_roles_assessment',run_id=run_id,session_id=final['session_id'],
        shared_checks=shared,real_model_responses=common['real_model_responses'],group_role_commands=len(results),
        role_results=results,independently_qualified_model_deployment_roles=qualified,
        bounded_role_lifecycles_verified=bounded,no_new_commands_after_stop_verified=quiet,
        all_three_model_role_feedback_loops_verified=set(qualified)==set(ROLE_GOALS),
        native_ai_selects_and_operates_units=True,mission_success_verified=False,all_units_return_verified=False,
        full_G6_verified=False,formal_goal_complete=False,
        evidence={**common['evidence'],**native_evidence,str(host/'macro-snapshots.jsonl'):sha(host/'macro-snapshots.jsonl')})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run-directory','download','original-export','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--run-id',required=True);a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_group_role_model_assessment_required')
    value=evaluate(a.run_directory.resolve(),a.run_id,a.download.resolve(),a.original_export.resolve())
    out.mkdir();shutil.copy2(__file__,out/'assessor.py');shutil.copy2(ROOT/'acceptance/assess_macro_group_roles.py',out/'effect-helper.py')
    value['assessor_sha256']=sha(out/'assessor.py');value['effect_helper_sha256']=sha(out/'effect-helper.py')
    value['evidence'].update({str((out/name).resolve()):sha(out/name) for name in ('assessor.py','effect-helper.py')})
    (out/'assessment.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in value.items() if k not in ('role_results','evidence')}))


if __name__=='__main__':main()
