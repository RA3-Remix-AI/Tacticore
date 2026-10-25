"""Offline narrow auxiliary arrival/return review, separate from later survival."""
import copy,hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'acceptance/runs/20261025-013326-commander/ground-normal-short01.json'

def audit(r):
    e=r['events'];n=r['native'];p=r['preflight'];q=r['request'];start=n['issued_frame'];end=n['returned_frame'];target=q['target']
    def get(kind,**fields):return [x for x in e if x['kind']==kind and all(x.get(k)==v for k,v in fields.items())]
    stops=get(23,arg=1,caller=0x787791);gates=get(24);rows=[]
    if len(stops)==len(gates)==1:
        for x in get(3):
            if stops[0]['seq']<x['seq']<gates[0]['seq'] and stops[0]['frame']<x['frame']<=gates[0]['frame'] and (not rows or x['frame']!=rows[-1]['frame']):rows.append(x)
    rows=rows[-3:]
    stable=len(rows)==3 and all(x['path']==0 and x['sm_flags']&0xffff==0 and x['source']==1 for x in rows) and all(math.hypot(a['x']-b['x'],a['y']-b['y'])<=1 for a,b in zip(rows,rows[1:]))
    returns=get(14,tag=3,arg=1);stopseq=returns[0]['seq'] if len(returns)==1 else 0
    arrival=[dict(seq=x['seq'],frame=x['frame'],distance=math.hypot(x['x']-target[0],x['y']-target[1])) for x in get(3) if n['move_issued_frame']<=x['frame']<=end and x['seq']<stopseq and math.hypot(x['x']-target[0],x['y']-target[1])<=15 and abs(x['z']-target[2])<=2]
    normal=get(30,tag=2,arg=1);private=get(10,tag=2,arg=1,caller=0x6d3b7d);finished=get(4);after=[x for x in get(3) if x['frame']>end]
    checks=dict(binding=r['session_id']==p['session_id']==n['session_id'] and n['commander_id']==p['commander_id'] and all(n[k]==q[k] for k in ('command_id','task_id','seq')),
        finite_target=len(target)==3 and all(type(x) in (int,float) and math.isfinite(x) for x in target),
        owner_thread=all(x['owner']==int(p['owner'],0) and x['thread']==p['window_thread'] for x in e) and n['callback_thread']==p['window_thread'],
        ordered_log=[x['seq'] for x in e]==list(range(1,len(e)+1)) and all(a['frame']<=b['frame'] for a,b in zip(e,e[1:])),
        stable_stop=bool(stable) and len(gates)==1 and math.hypot(rows[-1]['x']-gates[0]['x'],rows[-1]['y']-gates[0]['y'])<=1,
        stop_before_unique_normal_move=n['stop_calls']==n['private_stop_calls']==n['move_calls']==1 and len(normal)==len(private)==len(get(11,tag=2))==len(get(31,tag=2))==1 and stops[0]['seq']<gates[0]['seq']<normal[0]['seq']<private[0]['seq'] and stops[0]['frame']<gates[0]['frame']==normal[0]['frame']==n['move_issued_frame'],
        exact_target_and_state=all(x['command_xyz']==target for x in normal+private) and all(x['source']==1 and x['state_id']==1 and x['requested']==x['effective']==target for x in get(11,tag=2)),
        three_distinct_arrivals=len(arrival)==3 and len({x['frame'] for x in arrival})==3 and n['arrival_samples']==3,
        leased_identity_and_no_override=all(x['source']==1 and x['team']==int(p['script_team'],0) for x in get(3) if n['move_issued_frame']<=x['frame']<=end) and not any(x['tag']==0 and x['kind'] in (10,12,14,16,18,20,22,30) and start<=x['frame']<end for x in e),
        normal_pool_return=n['detach_calls']==n['return_calls']==n['return_verified']==len(returns)==1 and any(x['kind']==18 and x['tag']==1 and x['caller']==0x838877 and x['arg']==int(p['ai'],0)+0x104 for x in e) and any(x['kind']==16 and x['tag']==3 and x['caller']==0x83885b and x['arg']==int(p['ai'],0)+0x104 and x['frame']==end for x in e) and any(x['kind']==15 and x['tag']==3 and x['arg']==1 and x['frame']==end and x['team']==int(p['default_team'],0) for x in e),
        bounded=0<start<n['move_issued_frame']<end<=start+q['lease_frames'],
        only_post_return_actor_failure=r['status']=='finished' and r['host_exit']==9 and n['phase']==4 and n['error']==32 and n['lifecycle_fail']==1 and len(finished)==1 and finished[0]['frame']>end and bool(after),
        hooks_quiescent=n['restore_mask']==255 and n['active']==n['overflow']==n['return_pending']==0,
        native_recruitment_after_return=any(x['team'] not in (int(p['default_team'],0),int(p['script_team'],0)) for x in after))
    return dict(auxiliary_verified=all(checks.values()),checks=checks,stop_frames=[x['frame'] for x in rows],arrivals=arrival,returned_frame=end,first_recruitment_frame=next((x['frame'] for x in after if x['team'] not in (int(p['default_team'],0),int(p['script_team'],0))),None),post_failure_frame=finished[0]['frame'] if finished else None,scope='calibration_approach_auxiliary_only',post_return_actor_invalidity_is_not_a_failed_return=True,death_cause_independently_proven=False,timer_zero_direct_memory_observation=False,purpose_capabilities_granted=[])

def main():
    raw=SOURCE.read_bytes();r=json.loads(raw);result=audit(r);folder=ROOT/'tactical/ground-normal-aux'
    files={'native_binary_sha256':'bin/TacticalGroundNormalAux.dll','native_host_sha256':'bin/tactical_host.exe','native_source_sha256':'lease.cpp','native_shared_sha256':'shared.h','wrapper_sha256':'lease.py'}
    actual={key:hashlib.sha256((folder/name).read_bytes()).hexdigest() for key,name in files.items()};result['checks']['frozen_build_matches']=all(r[key]==value for key,value in actual.items());result['auxiliary_verified']=all(result['checks'].values());assert result['auxiliary_verified'],result
    mutants=[]
    bad=copy.deepcopy(r);bad['native']['return_verified']=0;mutants.append(bad)
    bad=copy.deepcopy(r);bad['events'][-1]['frame']=bad['native']['returned_frame'];mutants.append(bad)
    bad=copy.deepcopy(r)
    for event in bad['events']:
        if event['kind']==3 and event['frame'] in (5255,5257,5259):event['frame']=5255
    mutants.append(bad)
    bad=copy.deepcopy(r);next(x for x in bad['events'] if x['kind']==10)['arg']=0;mutants.append(bad)
    assert all(not audit(record)['auxiliary_verified'] for record in mutants)
    result.update(source_report=str(SOURCE),source_sha256=hashlib.sha256(raw).hexdigest(),build_hashes=actual,negative_cases=len(mutants),game_or_api_access=False,timer_cleanup_evidence='Hash-matched native finish() calls KillTimer and clears timer before event4/hook restoration/terminal phase. This is control-flow evidence, not a separate direct timer read.',original_assessment_preserved=r['assessment']['status'])
    output=Path(__file__).with_name('ground-normal-short01-independent.json');output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
