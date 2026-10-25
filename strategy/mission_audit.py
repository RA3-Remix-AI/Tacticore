"""Bounded request metadata and read-only continuous-mission lifecycle audit.

No request/response text, coordinates, credentials, game memory or network I/O.
Effect and release proofs are requalified by the trusted integration verifiers.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

PROTOCOL='continuous_tactical_v1'
PHASES=('reserved','approach','prepare','engage','retreat','restored')
ROOT=Path(__file__).resolve().parent.parent


def context_record(payload,metrics,source):
    memory=payload['working_memory']
    fields=('mission_id','task_id','module','purpose','target_contact_id',
            'deadline_game_seconds','phase','progress_seq')
    encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    return dict(protocol='model_mission_context_audit_v1',source=source,
        **{k:payload[k] for k in ('session_id','player_id','commander_id','snapshot_id','game_time_seconds')},
        payload_sha256=hashlib.sha256(encoded).hexdigest(),payload_bytes=len(encoded),
        events_compacted=memory['compressed_history']['events_compacted'],
        context_builds=metrics['context_builds'],
        missions=[{k:m[k] for k in fields} for m in memory.get('persistent_missions',{}).get('active',[])])


def append_context(path,payload,metrics,source):
    if path is None:return
    record=context_record(payload,metrics,source)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(record,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
        stream.flush()


def lines(path):
    if not path.exists():return []
    # A truncated trailing record is an audit gap, never silently discarded.
    return [json.loads(row) for row in path.read_text(encoding='utf-8-sig').splitlines() if row.strip()]


def analyze(session,identity,ledger,receipts,events,contexts,plans,memory):
    """Pure lifecycle metadata check; it does not confer native effect proof."""
    binding=identity.get('binding',identity);commander=session['scenario']['commander_id']
    expected=(session['session_id'],3,commander)
    if (identity.get('session_id'),identity.get('pid'),binding.get('commander_id'),identity.get('native',{}).get('player_index'))!=(session['session_id'],session['pid'],commander,3):raise ValueError('audit_identity')
    for row in events+contexts+plans:
        if (row.get('session_id'),row.get('player_id'),row.get('commander_id'))!=expected:raise ValueError('audit_record_binding')
    requests={r['request_id']:r for r in plans if r.get('event')=='request'}
    accepted=[(r['plan_id'],requests[r['request_id']]['game_time_seconds']) for r in plans if r.get('event')=='plan_accepted' and r.get('request_id') in requests]
    key=lambda r:(r.get('snapshot_id'),r.get('game_time_seconds'))
    requests_by_key={}
    contexts_by_key={}
    for row in requests.values():requests_by_key.setdefault(key(row),[]).append(row['request_id'])
    for row in contexts:contexts_by_key.setdefault(key(row),[]).append(row)
    accepted_by_request={r['request_id']:r['plan_id'] for r in plans if r.get('event')=='plan_accepted' and r.get('request_id') in requests}
    def accepted_context(row):
        matches=requests_by_key.get(key(row),[])
        # No guessed correlation when one key contains a retry or missing
        # context attempt. These records remain useful telemetry, not proof.
        if type(row.get('snapshot_id')) is not int or len(matches)!=1 or len(contexts_by_key.get(key(row),[]))!=1:return None
        return accepted_by_request.get(matches[0])
    errors=[];missions=[];commands=set();intervals=[]
    by_receipt={r['task_id']:r for r in receipts}
    for task,entry in ledger.items():
        if entry.get('mission_protocol')!=PROTOCOL:continue
        failures=[];command=entry['command_id']
        if command in commands:failures.append('command_reused')
        commands.add(command)
        accepted_events=[e for e in events if e['kind']=='tactical_dispatch_accepted' and e.get('task_id')==task]
        if len(accepted_events)!=(1 if entry.get('queued') else 0) or any(e.get('command_id')!=command for e in accepted_events):failures.append('dispatch_count_or_binding')
        feedback=[e for e in events if e['kind']=='tactical_task_feedback' and e.get('task_id')==task]
        starts=[e for e in feedback if e['status']=='started'];ends=[e for e in feedback if e['status'] in ('completed','failed','cancelled','blocked')]
        if len(starts)>1 or len(ends)>1:failures.append('feedback_duplicated')
        progress=[e for e in events if e['kind']=='mission_progress_observed' and e.get('task_id')==task]
        previous_revision=previous_frame=0;previous_phase=0
        for row in progress:
            phase=PHASES.index(row['stage']) if row.get('stage') in PHASES else -1
            if row.get('command_id')!=command or row.get('module')!=entry['module'] or row.get('deadline_frame')!=entry['expires_frame']:failures.append('progress_binding_or_deadline')
            if type(row.get('revision')) is not int or row['revision']<=previous_revision or type(row.get('observed_frame')) is not int or row['observed_frame']<previous_frame or phase<previous_phase:failures.append('progress_regression')
            previous_revision,previous_frame,previous_phase=row.get('revision',0),row.get('observed_frame',0),phase
        ttl=entry.get('model_plan_expires_game_seconds')
        if type(ttl) not in (int,float):failures.append('model_plan_metadata_missing')
        samples=[]
        for row in contexts:
            if entry['dispatch_frame']/15<row['game_time_seconds']<previous_frame/15 and not any(m.get('task_id')==task for m in row.get('missions',[])):
                failures.append('mission_missing_from_actual_request_context')
            for item in row.get('missions',[]):
                if item.get('task_id')!=task:continue
                if item.get('mission_id')!=str(__import__('uuid').UUID(task)) or item.get('deadline_game_seconds')!=entry['expires_frame']/15 or item.get('module')!=entry['module'] or item.get('purpose')!=entry['purpose'] or item.get('target_contact_id')!=entry.get('target_contact_id'):failures.append('context_mission_changed')
                samples.append(row)
        cross=bool(type(ttl) in (int,float) and any(e['observed_frame']/15>ttl for e in progress))
        request_cross=bool(type(ttl) in (int,float) and any(r['game_time_seconds']>ttl for r in samples))
        accepted_cross=[r for r in samples if type(ttl) in (int,float) and r['game_time_seconds']>ttl and accepted_context(r) not in (None,entry.get('model_plan_id'))]
        receipt=by_receipt.get(task,{})
        # The roster is reserved at acceptance, before native issuance. Waiting
        # children cannot overlap another accepted use of the same actors.
        start=accepted_events[0]['wall_seconds'] if accepted_events else (starts[0]['wall_seconds'] if starts else None)
        end=ends[0]['wall_seconds'] if ends else None
        if not entry.get('terminal'):failures.append('nonterminal_mission_at_stop')
        if ends and receipt.get('status')!=ends[0]['status']:failures.append('terminal_receipt_status_changed')
        if entry.get('started') and len(starts)!=1:failures.append('started_evidence_missing')
        if entry.get('terminal') and len(ends)!=1:failures.append('terminal_feedback_missing')
        intervals.append((task,set(entry.get('object_ids',[])),start,end))
        missions.append(dict(task_id=task,command_id=command,module=entry['module'],purpose=entry['purpose'],
            dispatches=len(accepted_events),started=len(starts)==1,terminal_status=receipt.get('status'),
            phases=list(dict.fromkeys(e['stage'] for e in progress)),progress_records=len(progress),
            cross_original_plan_ttl=cross,model_contexts_with_mission=len(samples),
            context_preserved_after_original_ttl=request_cross,
            context_preserved_during_compression=any(r.get('events_compacted',0)>0 for r in samples),
            accepted_post_ttl_contexts_with_mission=len(accepted_cross),
            accepted_post_ttl_compressed_contexts_with_mission=sum(r.get('events_compacted',0)>0 for r in accepted_cross),
            other_accepted_plans_during_mission=len({p for p,at in accepted if p!=entry.get('model_plan_id') and entry['dispatch_frame']/15<=at<=previous_frame/15}),
            errors=sorted(set(failures))))
    for i,(task,actors,start,end) in enumerate(intervals):
        if start is None:continue
        for other,other_actors,next_start,next_end in intervals[i+1:]:
            if next_start is not None and actors&other_actors and max(start,next_start)<min(end if end is not None else float('inf'),next_end if next_end is not None else float('inf')):errors.append(dict(code='actor_lease_overlap',tasks=[task,other]))
    for row in missions:
        errors.extend(dict(code=code,task_id=row['task_id']) for code in row['errors'])
    starts=sum(e['kind']=='host_started' for e in events);stops=sum(e['kind']=='host_stopped' for e in events)
    if starts!=1 or stops!=1:errors.append(dict(code='host_lifecycle_incomplete_or_restarted'))
    if any(e['kind'] in ('host_fault','terminal_feedback_incomplete','tactical_restoration_unverified','executor_restoration_unverified') for e in events):errors.append(dict(code='host_or_terminal_fault'))
    return dict(protocol='mission_lifecycle_audit_v1',session_id=session['session_id'],mutations=False,
        metadata_lifecycle_verified=bool(missions) and not errors,missions=missions,errors=errors,
        requests=len(requests),accepted_plans=len(accepted),context_audit_records=len(contexts),
        compactions=memory.get('metrics',{}).get('compactions'),
        observability_gaps=(["request_context_metadata_unavailable"] if not contexts else [])+(["no_continuous_mission_records"] if not missions else []),
        scope='Lifecycle metadata only; raw effect/release requalification is reported separately. No victory or economic-suppression claim.')


def audit_run(session):
    out=Path(session['run_directory']).resolve()/'battle-host'
    read=lambda name:json.loads((out/name).read_text(encoding='utf-8-sig'))
    identity=read('identity.json');ledger=read('tactical-dispatch-ledger.json');status=read('tactical-status.json')
    result=analyze(session,identity,ledger,status.get('ledger',[]),lines(out/'host-events.jsonl'),lines(out/'agent-state.context-audit.jsonl'),lines(out/'plans.jsonl'),read('agent-state.json'))
    # Import only local pure raw verifiers; no game connection is created.
    folder=ROOT/'integration';sys.path.insert(0,str(folder))
    spec=importlib.util.spec_from_file_location('mission_effect_audit_readonly',folder/'audit_mission_effects.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result['raw_effects']=module.audit(session)
    from continuous_evidence import terminal_facts,pre_dispatch_facts
    from tactical_bridge import TacticalBridge
    host=SimpleNamespace(session=session,binding=SimpleNamespace(session_id=session['session_id'],commander_id=session['scenario']['commander_id'],player_id=3))
    bridge=object.__new__(TacticalBridge);bridge.host=host
    receipts={r['task_id']:r for r in status.get('ledger',[])};releases=[]
    for task,saved in ledger.items():
        if saved.get('mission_protocol')!=PROTOCOL or not saved.get('terminal'):continue
        entry=dict(saved,task_id=task);receipt=receipts.get(task,{})
        try:
            disposed=any(x.get('control_release',{}).get('disposed_verified') is True for x in receipt.get('unit_results',[]))
            if disposed and entry['module'] in ('attack','raid'):bridge.verify_disposals(receipt,entry);kind='verified_disposal_not_return'
            elif not saved.get('started'):pre_dispatch_facts(host,receipt,entry);kind='verified_no_dispatch'
            else:terminal_facts(host,receipt,entry);kind='verified_native_release'
            releases.append(dict(task_id=task,verified=True,kind=kind))
        except (ValueError,KeyError,TypeError,OSError,ImportError):releases.append(dict(task_id=task,verified=False,kind='release_unproved'))
    result['raw_releases']=releases
    result['full_acceptance_verified']=result['metadata_lifecycle_verified'] and not result['observability_gaps'] and all(r['verified'] for r in releases) and result['raw_effects']['all_three_actual_effects_verified'] and any(m['accepted_post_ttl_compressed_contexts_with_mission']>0 for m in result['missions'])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--session',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(audit_run(json.loads(args.session.read_text(encoding='utf-8-sig'))),ensure_ascii=False,indent=2,allow_nan=False))
