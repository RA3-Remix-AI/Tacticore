"""Independent existing-file audit. Writes only new reports beside this script."""
import hashlib,json,math,uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'acceptance/runs/20261025-034721-commander'
BASE=RUN/'battle-host'
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def rows(path):return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

host=load(BASE/'host-status.json');memory=load(BASE/'agent-state.json')
plans=rows(BASE/'plans.jsonl');events=rows(BASE/'host-events.jsonl')
ledger=load(BASE/'tactical-dispatch-ledger.json');executor=rows(RUN/'tactical-executor.jsonl')
decisions=[e for e in plans if e['event']=='decision'];requests=[e for e in plans if e['event']=='request']
accepted=[e for e in plans if e['event']=='plan_accepted'];guards=[e for e in plans if e['event']=='policy_guard_rejected']
rejects=[e for e in plans if e['event']=='policy_rejected'];watch=load(RUN/'settlement-watch/status.json')
state=load(BASE/'match-state.json');snapshot=load(BASE/'snapshot.json');proof=load(BASE/'visibility-proof.json')
participants=load(BASE/'participants.json');session=load(RUN/'session.json')
sid=host['session_id'];commander=host['binding']['commander_id']
resultframe=next(r['victory_frame'] for r in state['result_records'] if r['victory_frame'])
cases=[]
for item in [e for e in executor if e.get('event')=='task_feedback']:
    receipt=item['receipt'];entry=ledger[receipt['task_id']]
    for child in receipt['unit_results']:
        path=Path(child['report']);r=load(path);n=r['native'];q=r['request'];pre=r['preflight'];actor=child['object_id'];ev=r['events']
        ret=next(e for e in ev if e['kind']==15 and e['tag']==3 and e['arg']==1)
        lease=[e for e in ev if e['frame']>=n['issued_frame'] and e['seq']<=ret['seq']]
        samples=[e for e in lease if e['kind']==3];target=n['target'];private=r['private_target']
        checks={
            'single_actor_allocation':receipt['object_ids']==entry['object_ids']==[actor] and actor in entry['allowed_object_ids'] and pre['selected']['object_id']==actor and pre['selected']['type_hash']=='0x19ab11af',
            'session_player_commander':sid==r['session_id']==pre['session_id']==n['session_id']==receipt['session_id'] and pre['pid']==host['pid'] and receipt['player_id']==pre['player_id']==3 and commander==pre['commander_id']==n['commander_id']==receipt['commander_id'],
            'child_command_task_seq':str(uuid.uuid5(uuid.UUID(entry['command_id']),str(actor)))==n['command_id']==q['command_id'] and str(uuid.uuid5(uuid.UUID(receipt['task_id']),str(actor)))==n['task_id']==q['task_id'] and n['seq']==q['seq']>0,
            'native_event_sequence':all(b['seq']==a['seq']+1 and b['frame']>=a['frame'] for a,b in zip(ev,ev[1:])),
            'within_public_dispatch_expiry':entry['dispatch_frame']<=n['issued_frame']<n['returned_frame']<=entry['expires_frame'],
            'native_order_count':n['attack_calls'] in [0,1] and n['attack_calls']==n['attack_facade_calls']==n['attack_private_calls'],
            'no_native_override_during_lease':not any(e['tag']==0 and e['kind'] in [10,12,14,16,18,30,40] for e in lease),
            'owner_thread_bound':all(e['owner']==int(pre['owner'],0) and e['thread']==pre['window_thread'] for e in lease),
            'goal_not_falsely_completed':receipt['status']=='failed' and receipt['completed'] is False and receipt['goal_observed'] is False and r['assessment']['status']=='not_passed',
            'actual_damage_absent':n['damage_count']==n['commit_own_calls']==n['shot_samples']==0 and not any(e['kind'] in [20,22,24] for e in lease),
            'actual_native_return':sum(e['kind']==15 and e['tag']==3 and e['arg']==1 for e in lease)==1 and ret['team']==int(pre['default_team'],0) and ret['frame']==n['returned_frame'] and n['return_verified']==n['detach_calls']==n['return_calls']==1,
            'normal_clean_finish':r['status']=='finished' and r['host_exit']==0 and n['phase']==3 and n['restore_mask']==4095 and all(n[k]==0 for k in ['error','active','lifecycle_fail','owner_fail','overflow','return_pending']),
            'target_identity_scope':private['object_id']==q['target_object_id']==n['target_id'] and private['owner_player_id']==4 and (receipt['purpose']!='harass_economy' or private['type_hash']=='0xc45aaeab' and q['target_role']=='economy'),
            'target_sample_fresh':0<=n['issued_frame']-private['observed_frame']<=60,
            'source_exe_package':r['executable_sha256']=='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165' and r['package_sha256']==session['mod_sha256']==host['mod_sha256'],
        }
        binary_fields={'native_binary_sha256':'bin/TacticalOrderedCombo.dll','native_host_sha256':'bin/tactical_host.exe','wrapper_sha256':'lease.py','native_source_sha256':'lease.cpp','native_shared_sha256':'shared.h'}
        checks['pinned_executor']=all(r[field]==sha(ROOT/'tactical/ordered-combo'/name) for field,name in binary_fields.items())
        gates=[e for e in lease if e['kind']==38 and e['lease_stage']==2]
        stops=[e for e in lease if e['kind']==33 and e['lease_stage']==2 and e['tag']==4];clean=[]
        if len(gates)==len(stops)==1:
            for e in samples:
                if e['lease_stage']==2 and stops[0]['seq']<e['seq']<gates[0]['seq'] and e['frame']>stops[0]['frame'] and (not clean or clean[-1]['frame']!=e['frame']):clean.append(e)
        clean=clean[-3:]
        checks['post_stop_three_distinct_clean']=len(clean)==3 and all(e['path']==e['holder']==0 and e['source']==1 and not(e['sm_flags']&0xffff) for e in clean) and all(math.hypot(b['x']-a['x'],b['y']-a['y'])<=1 for a,b in zip(clean,clean[1:]))
        frames=dict(dispatch=entry['dispatch_frame'],issued=n['issued_frame'],toggle=n['toggle_frame'],prepared=n['prepare_gate_frame'],attack=n['attack_issued_frame'],stop=n['stop_issue_frame'],returned=n['returned_frame'],public_expiry=entry['expires_frame'])
        case=dict(task_id=receipt['task_id'],module=receipt['module'],purpose=receipt['purpose'],actor_id=actor,target_id=n['target_id'],target_role=q['target_role'],source_report=str(path),source_sha256=sha(path),checks=checks,failed_checks=[k for k,v in checks.items() if not v],raw_frame=frames)
        case.update(lease_frames=q['lease_frames'],elapsed_lease_frames=n['returned_frame']-n['issued_frame'],attack_frames_to_stop=n['stop_issue_frame']-n['attack_issued_frame'] if n['attack_issued_frame'] else None,ammo=[n['weapon_ammo'],n['last_ammo']],damage_total=n['damage_total'],post_stop_clean_frames=[e['frame'] for e in clean])
        case.update(initial_distance_to_dispatch_position=round(math.dist([samples[0][a] for a in 'xyz'],target),3),last_distance_to_dispatch_position=round(math.dist([samples[-1][a] for a in 'xyz'],target),3),distance_caveat='Dispatch-position distance; moving targets may subsequently move.')
        case['root_cause_class']='bounded_chase_without_shot_or_bound_damage' if n['attack_calls'] else 'preparation_early_exit_without_attack'
        case['cause_boundary']='180-frame bound includes preparation; no AK shot before stop; distance does not prove path feasibility.' if n['attack_calls'] else 'No explicit termination reason. Visibility/target-validity guard fits early exit; exact operand not recoverable.'
        cases.append(case)
cases.sort(key=lambda i:i['raw_frame']['issued'])
outcomes=[e for e in decisions if e['status'] in ['accepted','rejected','fallback_continuing','local_fallback']]
guard_snapshots={e['snapshot_id'] for e in guards}
unattributed=[{k:e[k] for k in ['snapshot_id','game_time_seconds','status']} for e in decisions if e.get('reason_code')=='adapter_error' and e['snapshot_id'] not in guard_snapshots]
checks={
    'one_host_start':sum(e['kind']=='host_started' for e in events)==1,
    'one_match_entry':sum(e['kind']=='entered_match' for e in events)==1,
    'one_host_stop':sum(e['kind']=='host_stopped' for e in events)==1,
    'no_host_fault':not any('fault' in e['kind'] for e in events),
    'same_session_player_commander':all((e['session_id'],e['player_id'],e['commander_id'])==(sid,3,commander) for e in events+plans),
    'decision_snapshots_contiguous':[e['snapshot_id'] for e in decisions]==list(range(1,178)),
    'decision_game_clock_strict':all(b['game_time_seconds']>a['game_time_seconds'] for a,b in zip(decisions,decisions[1:])),
    'all_requests_have_decision_outcome':{e['snapshot_id'] for e in requests}=={e['snapshot_id'] for e in outcomes},
    'last_request_accepted':requests[-1]['snapshot_id']==accepted[-1]['snapshot_id']==176,
    'native_candidate_then_stop':[e['kind'] for e in events[-2:]]==['native_result_candidate','host_stopped'],
    'watch_saw_result_and_lifecycle_exit':watch['had_live_match'] and watch['had_native_result_candidate'] and watch['native_lifecycle_ended'],
    'all_tactical_terminal':all(e['terminal'] for e in ledger.values()),
    'all_tactical_released_safely':all(all(c['checks'].values()) for c in cases),
}
report=dict(schema_version=1,kind='independent_formal_match_audit',source_run=str(RUN),session_id=sid,pid=host['pid'],host_pid=host['host_pid'],method='Existing files only; no game/GUI/API/model calls. Only new independent audit files written.')
report['lifecycle']=dict(checks=checks,verified=all(checks.values()),first_model_game_seconds=requests[0]['game_time_seconds'],last_model_game_seconds=requests[-1]['game_time_seconds'],last_observation_game_seconds=host['latest_snapshot']['game_time_seconds'],native_result_frame=resultframe,native_result_game_seconds=resultframe/15,decisions=len(decisions),max_decision_game_gap_seconds=max(b['game_time_seconds']-a['game_time_seconds'] for a,b in zip(decisions,decisions[1:])),max_decision_wall_gap_seconds=max((datetime.fromisoformat(b['at_utc'])-datetime.fromisoformat(a['at_utc'])).total_seconds() for a,b in zip(decisions,decisions[1:])),retryable_sample_events=sum(e['kind']=='sample_retry' for e in events),watch_samples=watch['samples'])
report['model']=dict(engine_metrics=host['metrics'],transport_metrics=host['transport'],guard_counts=dict(Counter(e['reason_code'] for e in guards)),engine_rejection_counts=dict(Counter(e['reason_code'] for e in rejects)),unattributed_adapter_errors=unattributed,outcome_counts=dict(Counter(e['status'] for e in outcomes)),plan_changes_per_game_minute=host['metrics']['plan_changes']/(host['latest_snapshot']['game_time_seconds']/60),response_counter_semantics='Decoded complete policy JSON, not every HTTP response. One adapter-internal failure subtype not persisted. Last request accepted; no final cancellation evidence.')
report['memory']=dict(metrics=host['memory'],ring_length=len(memory['event_ring']),ring_event_ids=[e['event_id'] for e in memory['event_ring']],dialogue_length=len(memory['conversation_tail']),summary=memory['compressed_history'],failure_memory=memory['failure_memory'],feedback_length=len(memory['recent_execution_feedback']),boundary='Final memory plus live monitoring checkpoints support continuity. Complete wire prompts/responses intentionally not retained; historical per-message reconstruction unavailable.')
reconciled={status:dict(memory['compressed_history'][key]) for status,key in [('completed','completed_tasks'),('failed','failed_tasks')]}
for event in memory['event_ring']:
    if event['kind']=='execution_feedback' and event.get('status') in reconciled:
        reconciled[event['status']][event['module']]+=1
report['memory']['summary_plus_ring_terminal_counts']=reconciled
report['memory']['summary_plus_ring_events']=memory['compressed_history']['events_compacted']+len(memory['event_ring'])
report['visibility']=dict(viewer_player_id=snapshot['battlefield']['viewer_player_id'],observer_player_id=participants['observer_player_id'],proof_verified=all(proof.get(k) is True for k in ['footprint_live_verified','terrain_view_live_verified','object_view_live_verified','conservative_stealth_exclusion_reviewed','no_observer_fallback']),proof_session_bound=proof['session_id']==sid,object_visibility_method=proof['object_visibility_method'],current_contacts=sum(c['currently_visible'] for c in snapshot['battlefield']['contacts']),last_seen_contacts=sum(not c['currently_visible'] for c in snapshot['battlefield']['contacts']),unknown_power_is_null=snapshot['resources']['power_balance'] is None,boundary='Player3 verified viewer observed during monitoring, separate from observer2. Not an exhaustive archive of every public snapshot.')
report['tactical']=dict(counters=host['tactical']['counters'],accepted_native_leases=len(cases),actual_script_attack_orders=sum(bool(c['raw_frame']['attack']) for c in cases),qualified_goal_completions=0,combined_arms_tasks=0,source_damage_amount=sum(c['damage_total'] for c in cases),safe_returns=sum(c['checks']['actual_native_return'] and c['checks']['normal_clean_finish'] for c in cases),cases=cases)
report['settlement']=dict(native_result_frame=resultframe,native_participants=[{k:p[k] for k in ['player_index','defeated_flag_raw']} for p in state['victory_conditions']['participants']],ui_source=str(RUN/'settlement-units.png'),ui_sha256=sha(RUN/'settlement-units.png'),ui_independently_viewed=True,ui_iron_hammer='victory',ui_oleg='defeat',winner_based_on_ui_and_native_mapping=True,llm_causal_victory_claim=False)
report['conclusion']=dict(full_match_agent_lifecycle_verified=all(checks.values()),model_vs_native_match_reached_visual_settlement=True,all_three_purposes_effectiveness_passed=False,calibration_evidence_separate=True,production_audit_delegated=True,limitations=['Main attack 0/4, economy harassment 0/1, coordinate_force not executed in this match.','Three actual ScriptAttack orders, no observed shot or source-linked damage; two preparation early exits.','No causal attribution of victory to LLM. Native AI performed local control and most combat.','Early-stop exact guard operand unavailable. One adapter-internal failure subtype unavailable.'])
sources=[BASE/name for name in ['host-status.json','agent-state.json','plans.jsonl','host-events.jsonl','tactical-dispatch-ledger.json','visibility-proof.json','participants.json','match-state.json']]+[RUN/'tactical-executor.jsonl',RUN/'settlement-watch/status.json',RUN/'settlement-units.png']
report['source_fingerprints']={str(p):sha(p) for p in sources}
output=Path(__file__).with_name('formal-match-034721-independent.json')
output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
print(json.dumps(dict(report=str(output),lifecycle_checks=checks,raw_failures=[(c['actor_id'],c['failed_checks']) for c in cases],max_gap=report['lifecycle']['max_decision_game_gap_seconds'],outcomes=report['model']['outcome_counts']),ensure_ascii=False))
