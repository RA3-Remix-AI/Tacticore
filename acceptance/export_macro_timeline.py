"""Export a local, non-executable macro evidence timeline, without model prose."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'integration')]
from host_runtime.macro_policy_runtime import trial
from host_runtime.macro_group_role_contract import ROLE_GOALS,ROLE_FAMILIES

LABELS=dict(budgeteconomy='经济投入优先',budgetarmy='军队投入优先',budgettech='科技投入优先',
    produceconscript='征召兵',produceflak='高射炮兵',producetank='铁锤坦克',buildreactor='超级反应堆',scout='侦察时机',
    deployattack='调度至西侧起点区域',deploydefense='调度至东侧起点区域',regroup='集结至己方区域',withdraw='向己方区域撤退',reinforce='增援己方基地')
REGIONS=dict(deployattack='region_1_3',deploydefense='region_8_3',regroup='region_8_3',withdraw='region_8_3',reinforce='region_8_3')
ACCOUNTS=('investment','special_operations','production','defense','technology','slush_fund')
BUILDINGS=('construction_yard','barracks','war_factory','refinery','super_reactor','battle_lab')
FORCE_ROLES=('infantry','armor','anti_air','anti_armor','air','naval')
FORCE_UNITS=('conscript','flak_trooper','hammer_tank','war_bear')
STATUS=dict(native_budget_adopted='原生预算已采用',native_budget_pending='等待原生预算采用',
    native_delegation_observed='原生自主选择',native_budget_clearing='等待清除',
    native_production_pending='原生生产等待中',native_production_queue_target_observed='新增生产队列已观测',
    native_production_partial_producer_unavailable='部分排队后生产者不可用',
    native_production_producer_unavailable='生产者不可用',native_construction_pending='原生建造等待中',
    native_construction_queue_observed='建造队列已观测',native_construction_object_observed='施工对象已观测')


def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def records(path):return [json.loads(s) for s in path.read_text().splitlines()]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def natural(value,maximum=8192):
    if type(value) is not int or not 0<=value<=maximum:raise ValueError('timeline_integer_bounds')
    return value


def project(events,acknowledgements,snapshots):
    """Whitelist fields; no raw request, free text, object ID or native address."""
    result=[];seen={}
    def add(value,key):
        signature=json.dumps({k:v for k,v in value.items() if k!='t'},sort_keys=True)
        if seen.get(key)==signature:return
        seen[key]=signature;result.append(value)
    for event in events:
        kind=event['kind']
        if kind in ('model_macro_native_acknowledged','model_macro_production_acknowledged','model_macro_construction_acknowledged','model_macro_scout_acknowledged','model_macro_region_acknowledged'):
            ack=acknowledgements.get(event['command_id'])
            if ack is None or ack['seq']!=event['seq']:raise ValueError('timeline_missing_native_ack')
            if any(a not in LABELS for a in event['actions']):raise ValueError('timeline_unsupported_action')
            regional=[a for a in event['actions'] if a in REGIONS]
            if regional and (len(regional)!=1 or event.get('target_region')!=REGIONS[regional[0]]):
                raise ValueError('timeline_regional_target_mismatch')
            result.append(dict(t=ack['native']['last_frame']/15,type='decision',seq=event['seq'],
                actions=['保护己方建筑' if a=='deploydefense' and event.get('goal')=='original_native_defense_of_own_infrastructure' else LABELS[a]
                    for a in event['actions']],additional_count=natural(event.get('additional_count',0),3),
                native_gate_acknowledged=event['native_gate_acknowledged'] is True))
        elif kind=='macro_native_feedback':
            shares=event.get('native_account_shares',{})
            values=[shares.get(a) for a in ACCOUNTS]
            if any(type(v) not in (float,int) or not math.isfinite(v) or not 0<=v<=1.00001 for v in values):
                raise ValueError('timeline_budget_bounds')
            add(dict(t=natural(event['observed_frame'],0xffffffff)/15,type='budget',
                status=STATUS.get(event['status'],'状态待核验'),
                selected=LABELS.get(event.get('selected_policy'),'原生自主选择'),
                adopted=event.get('native_effect_verified') is True,shares=[round(v,5) for v in values]),'budget')
        elif kind in ('macro_production_feedback','macro_construction_feedback'):
            action=event['action']
            if action not in LABELS:raise ValueError('timeline_unsupported_action')
            category='production' if kind=='macro_production_feedback' else 'construction'
            value=dict(t=natural(event['builder_frame'],0xffffffff)/15,type=category,action=LABELS[action],
                status=STATUS.get(event['status'],'等待进一步核验'),
                queues=natural(event['observed_new_queue_count']),
                own_objects=natural(event.get('new_own_unit_observations',event.get('new_own_construction_object_observations',0))),
                fully_paid_fields=natural(event['fully_paid_queue_observations']),released=event['policy_released'] is True,
                completion_verified=False,payment_verified=False)
            add(value,category)
        elif kind=='macro_scouting_feedback':
            add(dict(t=natural(event['observed_frame'],0xffffffff)/15,type='scouting',
                active_tasks=natural(event['active_native_tactics']),moved_groups=natural(event['moved_native_groups']),
                new_legal_contacts=natural(event['new_legal_contacts_since_intent']),
                execution_observed=event['native_execution_observed'] is True,released=event['policy_released'] is True,
                exclusive_visibility_attribution_verified=False,mission_success_verified=False),'scouting')
        elif kind=='macro_regional_feedback':
            action=event['action']
            if (action not in REGIONS or event.get('target_region')!=REGIONS[action]
                    or event.get('source')!='native_regional_group_observation'):
                raise ValueError('timeline_regional_target_mismatch')
            defense=event.get('goal')=='original_native_defense_of_own_infrastructure'
            if defense and (action!='deploydefense' or event.get('native_tactic_family')!='static_defense'
                    or event.get('target_policy')!='original_native_friendly_land_structure'):
                raise ValueError('timeline_base_defense_binding')
            role=action in ROLE_GOALS
            if role and (event.get('goal')!=ROLE_GOALS[action] or event.get('native_tactic_family')!=ROLE_FAMILIES[action]
                    or event.get('target_policy')!=('original_native_most_recently_attacked_own_base' if action=='reinforce'
                        else 'fixed_public_own_home_start_waypoint')):
                raise ValueError('timeline_group_role_binding')
            add(dict(t=natural(event['observed_frame'],0xffffffff)/15,type='regional',action='保护己方建筑' if defense else LABELS[action],
                **(dict(goal='original_native_defense_of_own_infrastructure',defender_groups=natural(event['defender_groups_near_infrastructure'])) if defense else {}),
                **(dict(goal=ROLE_GOALS[action],home_groups=natural(event['groups_near_home_region']),
                    withdrawing_groups=natural(event['withdrawing_native_groups']),
                    defender_groups=natural(event['defender_groups_near_infrastructure'])) if role else {}),
                active_tasks=natural(event['active_native_tactics']),allocated_groups=natural(event['allocated_native_groups']),
                moved_groups=natural(event['moved_native_groups']),progressing_groups=natural(event['groups_progressing_toward_region']),
                execution_observed=event['native_execution_observed'] is True,released=event['policy_released'] is True,
                arrival_verified=False,mission_success_verified=False,arbitrary_xy_control=False),'regional')
        elif kind=='model_macro_request_context':
            context=event['context'];facts=context.get('own_infrastructure')
            if facts:
                add(dict(t=natural(facts['own_census_frame'],0xffffffff)/15,type='infrastructure',
                    counts=[natural(facts['own_template_presence_counts'][name]) for name in BUILDINGS],
                    foundations_included=True,completed_technology_verified=False),'infrastructure')
            forces=context.get('own_forces')
            if forces:
                frame=natural(forces['observed_frame'],0xffffffff)
                if (forces.get('source')!='bound_own_force_presence' or forces.get('own_perspective') is not True
                        or forces.get('enemy_details_read') is not False
                        or type(forces.get('mobile_role_counts')) is not dict
                        or set(forces['mobile_role_counts'])-set(FORCE_ROLES)
                        or type(forces.get('named_unit_counts')) is not dict
                        or set(forces['named_unit_counts'])!=set(FORCE_UNITS)
                        or not -15<=context['game_time_seconds']*15-frame<=30):
                    raise ValueError('timeline_force_source_or_time')
                add(dict(t=frame/15,type='forces',roles=[natural(forces['mobile_role_counts'].get(k,0)) for k in FORCE_ROLES],
                    units=[natural(forces['named_unit_counts'][k]) for k in FORCE_UNITS],
                    unclassified_objects=natural(forces['unclassified_objects']),
                    recruitability_verified=False,ready_for_combat_verified=False),'forces')
    last=-100
    for snapshot in snapshots:
        at=snapshot['game_time_seconds'];credits=snapshot['resources']['credits']
        if not math.isfinite(at) or type(credits) not in (int,float) or not math.isfinite(credits) or not 0<=credits<=1e9:
            raise ValueError('timeline_snapshot_bounds')
        if at-last>=10:
            result.append(dict(t=at,type='credits',credits=round(credits)));last=at
    return sorted(result,key=lambda row:row['t'])


def outcome_event(value,session_id):
    if (value.get('session_id')!=session_id or value.get('native_winner_mapping_verified') is not True
            or value.get('model_side_outcome') not in ('victory','defeat')
            or {value.get('winner_player_index'),value.get('loser_player_index')}!={3,4}):
        raise ValueError('timeline_unverified_outcome')
    return dict(type='outcome',t=natural(value['last_live_frame'],0xffffffff)/15,
        model_side_outcome=value['model_side_outcome'],winner_player=value['winner_player_index'],
        loser_player=value['loser_player_index'],native_mapping_verified=True,model_win_contribution_verified=False)


def export(run,run_id,out,natural_watch=None):
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_timeline_directory_required')
    host=run/'battle-host';status=load(host/'host-status.json')
    if status['state'] not in ('stopped','fault','result_candidate'):raise ValueError('terminal_macro_host_required')
    pre,final,manifest,raw,_=trial(ROOT/'reports'/('macro-desktop-'+run_id))
    if final['session_id']!=status['session_id']:raise ValueError('timeline_session_mismatch')
    events=records(host/'host-events.jsonl');snapshots=records(host/'macro-snapshots.jsonl')
    acks={r['command_id']:r for r in raw if r['kind']=='command_acknowledged'}
    data=project(events,acks,snapshots);profile=load(host/'profile.json')
    data.append(dict(t=final['native']['last_frame']/15,type='stop',native_release_verified=final['cleanup_verified']))
    data.sort(key=lambda row:row['t'])
    sources=[host/'host-events.jsonl',host/'macro-snapshots.jsonl',host/'sources.json',host/'profile.json',
        ROOT/'reports'/('macro-desktop-'+run_id)/'policy-probe.jsonl']
    if natural_watch is not None:
        from assess_macro_outcome import evaluate as evaluate_outcome
        data.append(outcome_event(evaluate_outcome(run,natural_watch),status['session_id']))
        data.sort(key=lambda row:row['t'])
        sources.extend([run/'research-settlement.json',natural_watch/'preflight.json',natural_watch/'report.json',
            natural_watch/'native-match-transitions.jsonl',Path(__file__).with_name('assess_macro_outcome.py')])
    package=dict(schema_version=1,kind='recorded_macro_timeline',session_id=status['session_id'],run_id=run_id,
        profile_revision=profile['revision'],model=profile['effective']['model'],
        native_release_verified=final['cleanup_verified'],events=data,
        start_seconds=round(min((r['t'] for r in data),default=0),2),
        duration_seconds=round(max((r['t'] for r in data),default=0),2),
        unit_animation_recorded=False,game_replay_fidelity_verified=False,formal_goal_complete=False,
        sources=[dict(name=p.name,sha256=sha(p)) for p in sources])
    # Escape the HTML parser terminator even though every event field is bounded.
    encoded=json.dumps(package,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('&','\\u0026')
    template=(Path(__file__).parent/'macro_timeline.html').read_text(encoding='utf-8')
    if template.count('__MACRO_TIMELINE_DATA__')!=1:raise ValueError('timeline_template_placeholder')
    out.mkdir(parents=True)
    (out/'macro-timeline.json').write_text(json.dumps(package,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'macro-timeline.html').write_text(template.replace('__MACRO_TIMELINE_DATA__',encoded),encoding='utf-8')
    print(json.dumps(dict(output=str(out),events=len(data),duration_seconds=package['duration_seconds'],
        native_release_verified=package['native_release_verified'],game_replay_fidelity_verified=False)))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-directory',type=Path,required=True);p.add_argument('--run-id',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--natural-watch',type=Path);a=p.parse_args()
    export(a.run_directory.resolve(),a.run_id,a.output.resolve(),a.natural_watch.resolve() if a.natural_watch else None)


if __name__=='__main__':main()
