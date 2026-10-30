"""Export a local, non-executable macro evidence timeline, without model prose."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import uuid
import re

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'integration'),str(ROOT/'strategy')]
from host_runtime.macro_policy_runtime import trial
from host_runtime.macro_expansion_scope import v2_trial
from host_runtime.macro_expansion_diagnostics_v4 import project_expansion_event_v4
from host_runtime.macro_release_review_v4 import v4_release_trial
from host_runtime.macro_group_role_contract import ROLE_GOALS,ROLE_FAMILIES
from host_runtime.macro_strategy_diagnostics import (STRATEGY_EVENTS,StrategyEvidence,native_receipts,
    project_strategy_event,event_seconds,read_strategy_state,project_declaration)
from host_runtime.macro_strategy_public import project_macro_strategy_state
from host_runtime.contracts import ContractError,content_hash,SessionBinding

LABELS=dict(budgeteconomy='经济投入优先',budgetarmy='军队投入优先',budgettech='科技投入优先',
    produceconscript='征召兵',produceflak='高射炮兵',producetank='铁锤坦克',buildreactor='超级反应堆',scout='侦察时机',
    deployattack='调度至西侧起点区域',deploydefense='调度至东侧起点区域',regroup='集结至己方区域',withdraw='向己方区域撤退',reinforce='增援己方基地')
LABELS.update(buildpower='普通电厂',buildbarracks='兵营',buildfactory='战车工厂',buildrefinery='矿场',
    buildbattlelab='作战实验室',producesickle='镰刀机甲',producebullfrog='牛蛙载具')
LABELS.update(expand='推动原生扩张',pauseconstruction='暂缓建设调度',advanceconstruction='推进建设调度',
    pauseproduction='暂缓生产调度',advanceproduction='推进生产调度')
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
STATUS.update(native_queue_observed='新增队列已观测',native_producer_unavailable='生产者不可用',
    native_expansion_pending='原生偏好执行中')
STRATEGY_GOALS=dict(economic_stability='稳定经济',expand_economy='扩充经济',develop_technology='推进科技',build_force='补充与调整兵力',
    scout='获取战场情报',pressure='向敌方施压',defend_base='防守己方基地',recover_force='撤回并恢复兵力',hold='保持当前态势')
STRATEGY_PHASES=dict(prepare='准备条件',execute='执行当前意图',assess='核对效果并调整',wait='等待合适条件')
STRATEGY_EXPECTED=dict(resource_recovery='资源状况改善',construction_queue='出现新的建造队列',building_operational='设施可运转核验',
    production_queue='出现新的生产队列',unit_completed='单位出厂核验',technology_unlocked='科技解锁核验',new_lawful_contact='新的合法情报',
    force_region_change='己方部署变化',threat_reduced='威胁减轻观测',no_change='维持现有状态')
STRATEGY_GUARDS=dict(strategy_allowed='计划通过战略检查',strategy_stopped='已停止新增战略指挥',strategy_unknown_outcome='等待未知结果核对',
    strategy_intent_in_flight='同类意图仍在进行',strategy_no_effect_cooldown='等待条件变化，避免无效重复',strategy_production_renewal_wait='等待生产变化后再决定补充',
    strategy_minimum_hold='暂时保持目标，等待新事实',strategy_plan_already_dispatched='同一计划已处理',strategy_game_paused='游戏暂停，等待恢复')


def strategy_row(kind,facts,at):
    if type(at) not in (int,float) or not math.isfinite(at) or not 0<=at<=86400:raise ValueError('timeline_strategy_time')
    value=dict(t=at,type='strategy',stage=kind.removeprefix('macro_strategy_'),facts=facts,
        global_native_release_verified=False)
    declared=facts.get('declaration')
    if declared:
        value.update(goal=STRATEGY_GOALS[declared['objective']],phase=STRATEGY_PHASES[declared['phase']],
            expectation=STRATEGY_EXPECTED[declared['expected_observation']])
    if 'reason_code' in facts:value['guard']=STRATEGY_GUARDS.get(facts['reason_code'],'已记录，等待核验')
    return value


def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def records(path):return [json.loads(s) for s in path.read_text().splitlines()]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def source_snapshot(path,maximum=32*1024*1024):
    """The exact stable bytes used for projection are also the hash source."""
    before=path.stat()
    with path.open('rb') as stream:raw=stream.read(maximum+1)
    after=path.stat()
    if (len(raw)>maximum or before.st_size!=after.st_size or len(raw)!=after.st_size
            or (before.st_mtime_ns,before.st_ino,before.st_dev)!=(after.st_mtime_ns,after.st_ino,after.st_dev)):
        raise ValueError('timeline_source_changed_or_oversized')
    return raw


def natural(value,maximum=8192):
    if type(value) is not int or not 0<=value<=maximum:raise ValueError('timeline_integer_bounds')
    return value


def recorded_trial(directory,*,snapshot=source_snapshot,contract_path=None,publication_v4_required=False,
                   v5_output=None,v5_release=None,publication_v5_required=False):
    """Route only from the hashed pre-execution manifest, never current UI state."""
    directory=Path(directory).resolve()
    def value(path):return json.loads(snapshot(path).decode('utf-8-sig'))
    pre=value(directory/'preflight.json');final=value(directory/'final-state.json')
    candidates=[row for row in pre.get('sources',[]) if type(row) is dict
        and type(row.get('path')) is str and Path(row['path']).name=='build-manifest.json']
    if len(candidates)!=1:raise ValueError('timeline_frozen_manifest_required')
    entry=candidates[0];copy=entry.get('copy')
    if type(copy) is not str or Path(copy).name!=copy:raise ValueError('timeline_frozen_manifest_path')
    path=(directory/'source'/copy).resolve()
    if path.parent!=(directory/'source').resolve():raise ValueError('timeline_frozen_manifest_path')
    manifest_bytes=snapshot(path)
    if hashlib.sha256(manifest_bytes).hexdigest()!=entry.get('sha256'):
        raise ValueError('timeline_frozen_manifest_changed')
    manifest=json.loads(manifest_bytes.decode('utf-8-sig'))
    protocol=manifest.get('protocol_version',1);flags=manifest.get('flags')
    kinds={1:'native_macro_policy_transport_candidate',2:'native_macro_policy_transport_v2_candidate'}
    if (type(protocol) is not int or protocol not in kinds or manifest.get('kind')!=kinds[protocol]
            or type(flags) is not list or len(flags)!=(20 if protocol==2 else 13)
            or any(type(flag) is not str or not flag for flag in flags) or len(set(flags))!=len(flags)):
        raise ValueError('timeline_native_protocol_manifest')
    if type(final.get('native',{}).get('version')) is not int or final['native']['version']!=protocol:
        raise ValueError('timeline_native_protocol_mismatch')
    if publication_v5_required and v5_output is None:raise ValueError('timeline_required_publication_v5_contract_missing')
    if v5_output is not None:
        if protocol!=2:raise ValueError('timeline_publication_v5_protocol_mismatch')
        from host_runtime.macro_catalog_release_route_v1 import reviewed_v5_trial
        v5_contract=Path(v5_output)/'publication-v5-contract.json';v5_review=Path(v5_output)/'publication-v5-release-review.json'
        contract_bytes=snapshot(v5_contract);sidecar_bytes=snapshot(v5_review)
        result=reviewed_v5_trial(directory,output=v5_output,release=v5_release,expected=manifest)
        if (result[4].get(str(v5_contract.resolve()))!=hashlib.sha256(contract_bytes).hexdigest()
                or v5_release.get('publication_v5_release_review_sha256')!=hashlib.sha256(sidecar_bytes).hexdigest()):
            raise ValueError('timeline_publication_v5_contract_changed')
    elif publication_v4_required and (contract_path is None or not Path(contract_path).is_file()):
        raise ValueError('timeline_required_publication_v4_contract_missing')
    elif contract_path is not None and Path(contract_path).exists():
        if protocol!=2:raise ValueError('timeline_publication_v4_protocol_mismatch')
        contract_path=Path(contract_path).resolve()
        contract_bytes=snapshot(contract_path)
        result=v4_release_trial(directory,contract_path=contract_path,expected=manifest)
        if result[4].get(str(contract_path))!=hashlib.sha256(contract_bytes).hexdigest():
            raise ValueError('timeline_publication_v4_contract_changed')
    else:result=v2_trial(directory,expected=manifest) if protocol==2 else trial(directory)
    actual_pre,actual_final,actual_manifest,rows,evidence=result
    original_rows=[json.loads(line) for line in snapshot(directory/'policy-probe.jsonl').decode('utf-8-sig').splitlines()]
    if (actual_pre!=pre or actual_final!=final or actual_manifest!=manifest or rows!=original_rows):
        raise ValueError('timeline_trial_source_changed')
    independent=final.get('independent_flags',{}).get('flags')
    if (type(independent) is not list or len(independent)!=len(flags)
            or any(type(row) is not dict for row in independent)
            or {row.get('name') for row in independent}!=set(flags)
            or any(type(row.get('present')) is not bool or row['present'] and row.get('value') is not False for row in independent)):
        raise ValueError('timeline_native_flags_not_cleared')
    evidence=dict(evidence)
    for source in (directory/'preflight.json',directory/'final-state.json',directory/'policy-probe.jsonl',path):
        digest=hashlib.sha256(snapshot(source)).hexdigest()
        if str(source) in evidence and evidence[str(source)]!=digest:raise ValueError('timeline_trial_source_changed')
        evidence[str(source)]=digest
    return actual_pre,actual_final,actual_manifest,rows,evidence


def model_record_summary(events):
    """Responses and rejected decisions remain records, not native effects."""
    counts={kind:sum(row.get('kind')==kind for row in events) for kind in
        ('commander_model_call_started','commander_model_response_returned','commander_model_call_failed','macro_strategy_response_rejected')}
    decisions=[row for row in events if row.get('kind')=='decision']
    return dict(calls_started=counts['commander_model_call_started'],responses_returned=counts['commander_model_response_returned'],
        call_failures=counts['commander_model_call_failed'],strategy_responses_rejected=counts['macro_strategy_response_rejected'],
        local_fallback_decisions=sum(row.get('status')=='local_fallback' for row in decisions),
        decision_adapter_errors=sum(row.get('reason_code')=='adapter_error' for row in decisions),
        decision_policy_rejections=sum(row.get('reason_code')=='policy_fields' for row in decisions),
        native_acknowledged_decisions=sum(row.get('kind') in ('model_macro_expansion_acknowledged','model_macro_native_acknowledged','model_macro_production_acknowledged',
            'model_macro_construction_acknowledged','model_macro_scout_acknowledged','model_macro_region_acknowledged') for row in events),
        model_to_native_effect_loop_verified=False)


def project(events,acknowledgements,snapshots):
    """Whitelist fields; no raw request, free text, object ID or native address."""
    result=[];seen={};last_request=None
    evidence=StrategyEvidence(events,native_receipts(acknowledgements))
    def add(value,key):
        signature=json.dumps({k:v for k,v in value.items() if k!='t'},sort_keys=True)
        if seen.get(key)==signature:return
        seen[key]=signature;result.append(value)
    for event in events:
        kind=event['kind']
        if kind in STRATEGY_EVENTS:
            try:facts=project_strategy_event(kind,event,evidence=evidence,at=event_seconds(event))
            except ContractError:raise ValueError('timeline_strategy_invalid') from None
            at=event_seconds(event);basis='recorded_host_frame'
            if at is None:at=facts.get('observed_game_seconds');basis='reported_observation'
            if at is None:
                receipt=evidence.receipts.get(event.get('command_id'),{})
                if type(receipt.get('native_start_frame')) is int:at=receipt['native_start_frame']/15;basis='native_start_frame'
            if at is None:at=last_request;basis='request_snapshot_lower_bound'
            if at is not None:
                row=strategy_row(kind,facts,at);row['time_basis']=basis;result.append(row)
        elif kind in ('model_macro_expansion_acknowledged','model_macro_native_acknowledged','model_macro_production_acknowledged','model_macro_construction_acknowledged','model_macro_scout_acknowledged','model_macro_region_acknowledged'):
            if kind=='model_macro_expansion_acknowledged':project_expansion_event_v4(kind,event)
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
        elif kind=='macro_expansion_feedback':
            facts=project_expansion_event_v4(kind,event)
            add(dict(t=facts['builder_frame']/15,type=facts['domain'],action=LABELS[facts['action']],
                status=STATUS.get(facts['status'],'等待进一步核验'),queues=facts['observed_new_queue_count'],
                own_objects=facts['new_own_target_observations'],fully_paid_fields=facts['fully_paid_queue_observations'],
                released=facts['policy_released'],completion_verified=False,payment_verified=False,
                exact_queue_to_object_link_verified=False,unit_exit_verified=False),facts['domain'])
        elif kind in ('macro_resource_feedback','macro_admission_current_state_reconciled'):
            facts=project_expansion_event_v4(kind,event)
            at=event_seconds(event);basis='recorded_host_frame'
            if at is None:at=last_request;basis='request_snapshot_lower_bound'
            if at is not None:add(dict(t=at,type='admission_buffer',facts=facts,time_basis=basis),'admission_buffer')
        elif kind=='macro_admission_request_not_delivered':
            at=event_seconds(event);basis='recorded_host_frame'
            if at is None:at=last_request;basis='request_snapshot_lower_bound'
            if at is not None:result.append(dict(t=at,type='not_delivered_record',time_basis=basis,facts=project_expansion_event_v4(kind,event)))
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
            context=event['context']
            if 'macro_default_contract' in context:
                from macro_policy import restore_public_defaults
                context=restore_public_defaults(context)
            at=context.get('game_time_seconds')
            if type(at) in (int,float) and math.isfinite(at) and 0<=at<=86400:last_request=at
            facts=context.get('own_infrastructure')
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
                        or not set(FORCE_UNITS)<=set(forces['named_unit_counts'])<=set(FORCE_UNITS)|{'sickle','bullfrog'}
                        or not -15<=context['game_time_seconds']*15-frame<=30):
                    raise ValueError('timeline_force_source_or_time')
                add(dict(t=frame/15,type='forces',roles=[natural(forces['mobile_role_counts'].get(k,0)) for k in FORCE_ROLES],
                    units=[natural(forces['named_unit_counts'][k]) for k in FORCE_UNITS]+
                        ([natural(forces['named_unit_counts'].get(k,0)) for k in ('sickle','bullfrog')]
                            if set(forces['named_unit_counts'])-set(FORCE_UNITS) else []),
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


def state_checkpoint(state,at):
    """A saved final record is positioned at capture, never its older goal time."""
    if type(at) not in (int,float) or not math.isfinite(at) or not 0<=at<=86400:raise ValueError('timeline_strategy_time')
    value=project_macro_strategy_state(state)
    current=value['current_strategy']
    result=dict(t=at,type='strategy_state',state=value,checkpoint_only=True,effect_replay_verified=False,
        global_native_release_verified=False)
    if current:result.update(goal=STRATEGY_GOALS[current['objective']],phase=STRATEGY_PHASES[current['phase']],
        expectation=STRATEGY_EXPECTED[current['expected_observation']])
    return result


def _write_package(package,out):
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_timeline_directory_required')
    encoded=json.dumps(package,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('&','\\u0026')
    template=(Path(__file__).parent/'macro_timeline.html').read_text(encoding='utf-8')
    if template.count('__MACRO_TIMELINE_DATA__')!=1:raise ValueError('timeline_template_placeholder')
    out.mkdir(parents=True)
    (out/'macro-timeline.json').write_text(json.dumps(package,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'macro-timeline.html').write_text(template.replace('__MACRO_TIMELINE_DATA__',encoded),encoding='utf-8')
    print(json.dumps(dict(output=str(out),events=len(package['events']),duration_seconds=package['duration_seconds'],
        native_release_verified=package['native_release_verified'],game_replay_fidelity_verified=False)))


def export(run,run_id,out,natural_watch=None):
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_timeline_directory_required')
    consumed={}
    def snapshot(path):
        if path not in consumed:consumed[path]=source_snapshot(path)
        return consumed[path]
    def json_source(path):return json.loads(snapshot(path).decode('utf-8-sig'))
    def record_source(path):return [json.loads(line) for line in snapshot(path).decode('utf-8-sig').splitlines()]
    host=run/'battle-host';status=json_source(host/'host-status.json')
    if status['state'] not in ('stopped','fault','result_candidate'):raise ValueError('terminal_macro_host_required')
    if status.get('native_transport_protocol')==5:
        raise ValueError('timeline_native5_raw_unsupported_use_redacted_diagnostics')
    release=json_source(host/'macro-release.json')
    events=record_source(host/'host-events.jsonl')
    from host_runtime.macro_catalog_release_route_v1 import requires_v5
    source_index=json_source(host/'sources.json')
    source_rows=source_index.get('sources') if type(source_index) is dict else None
    if type(source_rows) is not list or len(source_rows)<3:raise ValueError('timeline_frozen_bundle_source_required')
    source=source_rows[2];copy=source.get('copy') if type(source) is dict else None
    if type(copy) is not str or copy!='2-'+Path(source.get('path','')).name:raise ValueError('timeline_frozen_bundle_source_required')
    bundle_path=(host/'source'/copy).resolve()
    if bundle_path.parent!=(host/'source').resolve():raise ValueError('timeline_frozen_bundle_source_required')
    bundle_bytes=snapshot(bundle_path)
    if hashlib.sha256(bundle_bytes).hexdigest()!=source.get('sha256'):raise ValueError('timeline_frozen_bundle_source_changed')
    frozen_bundle=json.loads(bundle_bytes.decode('utf-8-sig'))
    publication_v5_required=requires_v5(host,release=release,bundle=frozen_bundle)
    extension_keys=('native_release_contract','publication_v4_contract_sha256','publication_v4_release_review_sha256')
    publication_v4_required=(any(key in release for key in extension_keys)
        or any(row.get('kind')=='macro_admission_publication_contract_frozen' for row in events))
    pre,final,manifest,raw,native_evidence=recorded_trial(ROOT/'reports'/('macro-desktop-'+run_id),snapshot=snapshot,
        contract_path=host/'publication-v4-contract.json',publication_v4_required=publication_v4_required and not publication_v5_required,
        v5_output=host if publication_v5_required else None,v5_release=release if publication_v5_required else None,
        publication_v5_required=publication_v5_required)
    if not publication_v5_required and (publication_v4_required or (host/'publication-v4-contract.json').exists()):
        from host_runtime.macro_release_review_v4 import KIND
        if (release.get('native_release_contract')!=KIND
                or release.get('publication_v4_contract_sha256')!=hashlib.sha256(snapshot(host/'publication-v4-contract.json')).hexdigest()
                or release.get('publication_v4_release_review_sha256')!=hashlib.sha256(snapshot(host/'publication-v4-release-review.json')).hexdigest()):
            raise ValueError('timeline_publication_v4_release_binding')
    binding=SessionBinding.from_dict(release['binding'])
    if (release.get('kind')!='macro_policy_native_release' or release.get('run_id')!=run_id
            or release.get('native_release_verified') is not True
            or release.get('final_state_sha256')!=hashlib.sha256(snapshot(ROOT/'reports'/('macro-desktop-'+run_id)/'final-state.json')).hexdigest()
            or any(release.get(key)!=status.get(key) for key in ('host_pid','host_start_time'))
            or final['session_id']!=status['session_id'] or binding.session_id!=status['session_id']
            or final['pid']!=status.get('pid') or binding.game_process_id!=status.get('pid')
            or binding.game_process_start!=status.get('process_start') or binding.mod_sha256!=final['mod_sha256']
            or status.get('runtime_macro',{}).get('run_id')!=run_id
            or status.get('runtime_macro',{}).get('binding_hash')!=binding.binding_hash):
        raise ValueError('timeline_session_or_run_mismatch')
    from host_runtime.session_discovery_native import require_creation
    require_creation(binding.game_process_start,final['process_creation_filetime'])
    events=record_source(host/'host-events.jsonl');snapshots=record_source(host/'macro-snapshots.jsonl')
    probe=ROOT/'reports'/('macro-desktop-'+run_id)/'policy-probe.jsonl'
    if record_source(probe)!=raw:raise ValueError('timeline_trial_source_changed')
    acks={r['command_id']:r for r in raw if r['kind']=='command_acknowledged'}
    data=project(events,acks,snapshots);profile=json_source(host/'profile.json')
    data.append(dict(t=final['native']['last_frame']/15,type='stop',native_release_verified=final['cleanup_verified']))
    data.sort(key=lambda row:row['t'])
    sources=[host/'host-events.jsonl',host/'macro-snapshots.jsonl',host/'sources.json',host/'profile.json',
        host/'host-status.json',host/'macro-release.json',
        ROOT/'reports'/('macro-desktop-'+run_id)/'policy-probe.jsonl']
    if natural_watch is not None:
        from assess_macro_outcome import evaluate as evaluate_outcome
        data.append(outcome_event(evaluate_outcome(run,natural_watch),status['session_id']))
        data.sort(key=lambda row:row['t'])
        sources.extend([run/'research-settlement.json',natural_watch/'preflight.json',natural_watch/'report.json',
            natural_watch/'native-match-transitions.jsonl',Path(__file__).with_name('assess_macro_outcome.py')])
    strategy_state=None;strategy_index=None;strategy_reason=None
    if status.get('macro_strategy') is not None or (host/'macro-strategy-state.json').exists():
        strategy_state,strategy_index,strategy_reason=read_strategy_state(host/'macro-strategy-state.json',host)
        try:status_strategy=project_macro_strategy_state(status.get('macro_strategy'))
        except ContractError:status_strategy=None
        if strategy_state is not None and strategy_state!=status_strategy:
            strategy_state=None;strategy_reason='strategy_state_snapshot_changed'
        if strategy_state is not None:
            # Captured only at the end of this export. Never insert the saved
            # latest feedback into the earlier updated_game_seconds of a goal.
            capture=max((r['t'] for r in data),default=final['native']['last_frame']/15)
            latest=status.get('latest_snapshot',{}).get('game_time_seconds')
            if type(latest) in (int,float) and math.isfinite(latest) and 0<=latest<=86400:capture=max(capture,latest)
            data.append(state_checkpoint(strategy_state,capture));data.sort(key=lambda row:row['t'])
    source_rows=[dict(name=p.name,sha256=hashlib.sha256(snapshot(p)).hexdigest()) for p in sources]
    if strategy_index and 'sha256' in strategy_index:
        source_rows.append(dict(name='macro-strategy-state.json',sha256=strategy_index['sha256'],bytes=strategy_index['bytes']))
    package=dict(schema_version=1,kind='recorded_macro_timeline',session_id=status['session_id'],run_id=run_id,
        profile_revision=profile['revision'],model=profile['effective']['model'],
        native_transport_protocol=manifest.get('protocol_version',1),native_flag_count=len(manifest['flags']),
        native_release_verified=final['cleanup_verified'],events=data,
        model_records=model_record_summary(events),
        start_seconds=round(min((r['t'] for r in data),default=0),2),
        duration_seconds=round(max((r['t'] for r in data),default=0),2),
        unit_animation_recorded=False,game_replay_fidelity_verified=False,formal_goal_complete=False,
        sources=source_rows,native_trial_evidence=[dict(name=Path(path).name,sha256=digest)
            for path,digest in sorted(native_evidence.items())])
    if strategy_index is not None or any(event.get('kind') in STRATEGY_EVENTS for event in events):
        package['strategy_extension']=dict(schema_version=1,state_available=strategy_state is not None,
            state_reason_code=strategy_reason,global_native_release_verified=False,
            projection_scope='recorded_macro_intent_not_lease_release')
    _write_package(package,out)


def _diagnostic_strategy_facts(kind,facts,at):
    """Recheck the exported immutable window, never derive it from latest state."""
    payload={key:facts.get(key) for key in ('plan_id','strategy_id','allowed','reason_code','delivery_unknown','work_effect_verified','observed_game_seconds')}
    payload.update(outcome=facts.get('outcome'),effect_observed=facts.get('effect_reported',False),
        native_release_verified=facts.get('intent_end_verified',False))
    if facts.get('reported_outcome')=='effect_observed' and facts.get('outcome')=='unknown':
        payload['outcome']='effect_observed'
    if facts.get('verification_scope')!='macro_intent_only' or facts.get('global_native_release_verified') is not False:
        raise ValueError('timeline_strategy_projection_invalid')
    class ExportedWindow:
        def bounds(self,plan_id,command_id):
            begin=facts.get('effect_window_start_seconds');end=facts.get('effect_window_end_seconds')
            if (type(begin) not in (int,float) or type(end) not in (int,float) or not math.isfinite(begin)
                    or not math.isfinite(end) or not 0<=begin<end<=86400 or end-begin>60):return None
            return begin,end
        def effect_valid(self,plan_id,command_id,seen,now=None):
            interval=self.bounds(plan_id,command_id)
            asserted=(facts.get('effect_window_verified') is True if kind=='macro_strategy_outcome'
                else facts.get('budget_observation_window_verified') is True)
            return bool(asserted and interval and interval[0]<=seen<interval[1] and (now is None or seen<=now))
        def declaration(self,plan_id,strategy_id):
            if facts.get('declaration') is None:return None
            declared=project_declaration(facts['declaration'])
            if declared['strategy_id']!=strategy_id:raise ValueError('timeline_strategy_declaration_binding')
            return declared
    presence=facts.get('intent_command_present') if kind=='macro_strategy_declared' else None
    if kind=='macro_strategy_declared' and type(presence) is not bool:raise ValueError('timeline_strategy_projection_invalid')
    try:return project_strategy_event(kind,payload,evidence=ExportedWindow(),at=at,command_presence=presence)
    except ContractError:raise ValueError('timeline_strategy_projection_invalid') from None


def unified_diagnostic_rows(facts):
    """Use original public component frames; never infer mission success."""
    from host_runtime.strategic_unified_feedback_v5 import project_unified_feedback
    try:value=project_unified_feedback(facts)
    except ContractError:raise ValueError('timeline_unified_feedback_invalid') from None
    return [dict(t=row['observed_frame']/15,type='unified',action=LABELS[row['action']],
        action_key=row['action'],status=row['status'],observed_frame=row['observed_frame'],
        feedback_observed_frame=value['observed_frame'],preference_active=row['preference_active'],
        active_native_task_observed=row['active_native_task_observed'],movement_observed=row['movement_observed'],
        component_state_adopted=row['component_state_adopted'],state_already_satisfied=row['state_already_satisfied'],
        mission_success_verified=False,exclusive_attribution_verified=False,record_only=True)
        for row in value['observations']]


def project_diagnostics(document):
    """Only already-redacted facts enter this source mode; no raw payload fallback."""
    result=[]
    for event in document['timeline']:
        if type(event) is not dict or event.get('payload_projected') is not True:continue
        kind=event.get('event_type');facts=event.get('facts')
        if type(facts) is not dict:continue
        frame=event.get('game_frame')
        at=frame/15 if type(frame) is int and 0<=frame<=0xffffffff else None
        if kind in STRATEGY_EVENTS:
            safe=_diagnostic_strategy_facts(kind,facts,at)
            if at is None:at=safe.get('observed_game_seconds')
            if at is not None:result.append(strategy_row(kind,safe,at))
        elif kind=='macro_unified_feedback':
            result.extend(unified_diagnostic_rows(facts))
        elif kind=='plan_applied' and event.get('plan_binding_matches') is True:
            plan=facts.get('plan') or {};actions=plan.get('macro_actions')
            if (type(actions) is not list or len(actions)>5 or any(type(a) is not str or a not in LABELS for a in actions)):
                raise ValueError('timeline_unsupported_action')
            if document.get('status',{}).get('native_transport_protocol')==5 or any(a in ('expand','pauseconstruction','advanceconstruction','pauseproduction','advanceproduction') for a in actions):
                from native_unified_contract_v5 import split_intents
                try:split_intents(actions)
                except ValueError:raise ValueError('timeline_unified_intent_invalid') from None
            if at is not None:result.append(dict(t=at,type='decision_record',actions=[LABELS[a] for a in actions],record_only=True))
        elif kind=='macro_native_feedback' and 'native_account_shares' in facts and 'observed_frame' in facts:
            result.extend(project([dict(facts,kind='macro_native_feedback')],{},[]))
        elif kind in ('macro_production_feedback','macro_construction_feedback'):
            keys=('action','status','observed_new_queue_count','fully_paid_queue_observations','policy_released','builder_frame')
            object_key='new_own_unit_observations' if kind=='macro_production_feedback' else 'new_own_construction_object_observations'
            if all(k in facts for k in (*keys,object_key)):
                result.extend(project([dict(facts,kind=kind)],{},[]))
        elif kind=='macro_regional_feedback':
            action=facts.get('action');goal=facts.get('goal')
            if action not in REGIONS or facts.get('target_region')!=REGIONS[action]:raise ValueError('timeline_regional_target_mismatch')
            required=('observed_frame','active_native_tactics','allocated_native_groups','moved_native_groups','groups_progressing_toward_region')
            if not all(key in facts for key in required):continue
            if (facts.get('source')!='native_regional_group_observation'
                    or any(type(facts.get(k)) is not bool for k in ('native_execution_observed','policy_released'))):
                raise ValueError('timeline_regional_source')
            row=dict(t=natural(facts['observed_frame'],0xffffffff)/15,type='regional',action=LABELS[action],
                active_tasks=natural(facts['active_native_tactics']),allocated_groups=natural(facts['allocated_native_groups']),
                moved_groups=natural(facts['moved_native_groups']),progressing_groups=natural(facts['groups_progressing_toward_region']),
                execution_observed=facts.get('native_execution_observed') is True,released=facts.get('policy_released') is True,
                arrival_verified=False,mission_success_verified=False,arbitrary_xy_control=False,record_only=True)
            if action in ROLE_GOALS:
                if goal!=ROLE_GOALS[action]:raise ValueError('timeline_group_role_binding')
                if not all(k in facts for k in ('groups_near_home_region','withdrawing_native_groups','defender_groups_near_infrastructure')):continue
                row.update(goal=goal,home_groups=natural(facts['groups_near_home_region']),
                    withdrawing_groups=natural(facts['withdrawing_native_groups']),defender_groups=natural(facts['defender_groups_near_infrastructure']))
            elif goal=='original_native_defense_of_own_infrastructure':
                if action!='deploydefense' or 'defender_groups_near_infrastructure' not in facts:raise ValueError('timeline_base_defense_binding')
                row.update(goal=goal,action='保护己方建筑',defender_groups=natural(facts['defender_groups_near_infrastructure']))
            result.append(row)
        elif kind=='macro_scouting_feedback' and all(k in facts for k in ('observed_frame','active_native_tactics','moved_native_groups','new_legal_contacts_since_intent')):
            if any(type(facts.get(k)) is not bool for k in ('native_execution_observed','policy_released')):raise ValueError('timeline_scouting_source')
            result.append(dict(t=natural(facts['observed_frame'],0xffffffff)/15,type='scouting',
                active_tasks=natural(facts['active_native_tactics']),moved_groups=natural(facts['moved_native_groups']),
                new_legal_contacts=natural(facts['new_legal_contacts_since_intent']),execution_observed=facts.get('native_execution_observed') is True,
                released=facts.get('policy_released') is True,exclusive_visibility_attribution_verified=False,mission_success_verified=False,record_only=True))
    status=document.get('status') or {};snapshot=status.get('latest_snapshot')
    if type(snapshot) is not dict:snapshot={}
    capture=snapshot.get('game_time_seconds')
    if type(capture) not in (int,float) or not math.isfinite(capture) or not 0<=capture<=86400:
        capture=max((r['t'] for r in result),default=0)
    else:capture=max(capture,max((r['t'] for r in result),default=0))
    extension=document.get('macro_strategy_extension')
    if extension is not None:
        if type(extension) is not dict or extension.get('schema_version')!=1 or extension.get('kind')!='macro_strategy_diagnostics_extension':
            raise ValueError('timeline_strategy_extension_invalid')
        if extension.get('state_available') is True:
            state=project_macro_strategy_state(extension.get('state'))
            if extension.get('state_projection_sha256')!=content_hash(state):raise ValueError('timeline_strategy_state_hash')
            result.append(state_checkpoint(state,capture))
    if status.get('state') in ('stopped','completed','fault','result_candidate'):
        result.append(dict(t=capture,type='stop',native_release_verified=False,recorded_stop=True))
    return sorted(result,key=lambda row:row['t'])


def export_diagnostics(path,out,expected_sha256=None):
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_timeline_directory_required')
    before=path.stat()
    with path.open('rb') as stream:raw=stream.read(8*1024*1024+1)
    after=path.stat()
    if len(raw)>8*1024*1024 or (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise ValueError('timeline_diagnostics_changed_or_oversized')
    digest=hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and (re.fullmatch('[0-9a-f]{64}',expected_sha256 or '') is None or digest!=expected_sha256):
        raise ValueError('timeline_diagnostics_hash')
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('timeline_diagnostics_duplicate_key')
            value[key]=item
        return value
    document=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('timeline_nonfinite_json')))
    if (type(document) is not dict or type(document.get('schema_version')) is not int or document['schema_version']!=1
            or document.get('kind')!='tacticore_redacted_diagnostics' or document.get('redacted') is not True
            or type(document.get('timeline')) is not list or len(document['timeline'])>10000
            or type(document.get('binding')) is not dict or type(document.get('events')) is not dict
            or type(document.get('status')) is not dict):
        raise ValueError('timeline_redacted_diagnostics_required')
    for value in (document.get('run_id'),document.get('binding',{}).get('session_id')):
        try:
            if type(value) is not str or str(uuid.UUID(value))!=value:raise ValueError()
        except (ValueError,AttributeError):raise ValueError('timeline_diagnostics_binding') from None
    if document.get('events',{}).get('timeline_sha256')!=content_hash(document['timeline']):raise ValueError('timeline_diagnostics_events_hash')
    data=project_diagnostics(document);profile=document.get('effective_profile')
    if type(profile) is not dict:profile={}
    model=profile.get('model');revision=profile.get('revision')
    if type(model) is not str or re.fullmatch(r'[A-Za-z0-9._:/-]{1,200}',model) is None:model='未记录'
    if type(revision) is not int or not 1<=revision<=2**53-1:revision=None
    package=dict(schema_version=1,kind='recorded_macro_timeline',source_mode='redacted_diagnostics',
        session_id=document['binding']['session_id'],run_id=document['run_id'],profile_revision=revision,model=model,
        native_release_verified=False,events=data,start_seconds=round(min((r['t'] for r in data),default=0),2),
        duration_seconds=math.ceil(max((r['t'] for r in data),default=0)),unit_animation_recorded=False,
        game_replay_fidelity_verified=False,formal_goal_complete=False,
        sources=[dict(name='downloaded-redacted-diagnostics.json',sha256=digest,bytes=len(raw))],
        strategy_extension=dict(schema_version=1,projection_scope='redacted_records_not_new_qualification',global_native_release_verified=False))
    package['strategy_extension']['pending_counts_complete']=document['events'].get('truncated') is False
    _write_package(package,out)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--run-directory',type=Path);source.add_argument('--diagnostics',type=Path)
    p.add_argument('--run-id');p.add_argument('--expected-sha256')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--natural-watch',type=Path);a=p.parse_args()
    if a.diagnostics:
        if a.run_id or a.natural_watch:p.error('--diagnostics does not accept --run-id/--natural-watch')
        export_diagnostics(a.diagnostics.resolve(),a.output.resolve(),a.expected_sha256)
    else:
        if not a.run_id or a.expected_sha256:p.error('--run-directory requires --run-id; hash applies only to --diagnostics')
        export(a.run_directory.resolve(),a.run_id,a.output.resolve(),a.natural_watch.resolve() if a.natural_watch else None)


if __name__=='__main__':main()
