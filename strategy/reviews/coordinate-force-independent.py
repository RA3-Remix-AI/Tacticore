"""Independent raw two-role movement review. No native module/process imports."""
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'acceptance/runs/20261024-234355-commander/formation-stop-v2-03.json'
EVIDENCE=ROOT/'tactical/coordinate-force-evidence.json'


def distance(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])
def xyz(event):return [event[k] for k in ('x','y','z')]


def audit(report):
    events=report['events'];n=report['native'];pre=report['preflight'];rq=report['request'];units=report['units'];start=n['issued_frame'];end=n['returned_frame']
    checks=dict(finished=report.get('status')=='finished' and report.get('host_exit')==0,
        raw_sequence=[e['seq'] for e in events]==list(range(1,len(events)+1)),
        monotonic_frames=all(a['frame']<=b['frame'] for a,b in zip(events,events[1:])),
        binding=report['session_id']==pre['session_id']==n['session_id'] and n['commander_id']==pre['commander_id'] and all(n[k]==rq[k] for k in ('command_id','task_id','seq')),
        identity=all(e['thread']==pre['window_thread'] and (e['owner']==int(pre['owner'],0) if e['unit_id'] else e['kind'] in (0,4) and e['owner']==0) for e in events) and n['callback_thread']==pre['window_thread'],
        complete_clean_return=n['phase']==3 and n['restore_mask']==127 and n['active']==n['error']==n['overflow']==n['return_pending']==0,
        roles=len(units)==2 and [u['id'] for u in units]==[rq['front_id'],rq['support_id']] and len({u['id'] for u in units})==2 and [u['hash'] for u in units]==[0x19ab11af,0x2c358c61],
        bounded=start>0 and 0<=end-start<=rq['lease_frames']+5,
        stages=start<=n['front_arrival_frame']==n['support_issued_frame']<=end and n['stage']==3)
    stable=[];returns=[]
    for index,u in enumerate(units):
        ev=[e for e in events if e['unit_id']==u['id']]
        def select(kind,**values):return [e for e in ev if e['kind']==kind and all(e.get(k)==v for k,v in values.items())]
        stop=select(23,caller=0x787791,arg=1);gate=select(24,stage=0);move=select(10,tag=2);returned=select(16,tag=3,caller=0x83885b,arg=int(pre['ai'],0)+0x104)
        rows=[]
        if len(stop)==len(gate)==1:
            for e in ev:
                if e['kind']==3 and stop[0]['seq']<e['seq']<gate[0]['seq'] and stop[0]['frame']<e['frame']<=gate[0]['frame'] and (not rows or e['frame']!=rows[-1]['frame']):rows.append(e)
        rows=rows[-3:]
        clean=len(rows)==3 and all(e['path']==0 and e['sm_flags']&0xffff==0 and e['source']==1 for e in rows) and all(distance(xyz(a),xyz(b))<=1 for a,b in zip(rows,rows[1:]))
        clean=clean and len(gate)==1 and distance(xyz(rows[-1]),xyz(gate[0]))<=1 and gate[0]['path']==0 and gate[0]['sm_flags']&0xffff==0 and gate[0]['source']==1
        clean=clean and all(abs(a-b)<.001 for a,b in zip(xyz(gate[0]),u['hold']))
        checks[f'unit_{index}_stop_stable']=bool(clean)
        checks[f'unit_{index}_stop_chain']=len(select(20,tag=4,arg=1))==len(select(21,tag=4))==len(select(22,caller=0x787791,arg=1))==len(stop)==u['stop_calls']==u['private_stop_calls']==1
        checks[f'unit_{index}_move_chain']=len(move)==len(select(11,tag=2))==u['move_calls']==1 and len(gate)==1 and stop[0]['seq']<gate[0]['seq']<move[0]['seq'] and stop[0]['frame']<gate[0]['frame']<=move[0]['frame']
        checks[f'unit_{index}_returned']=len(returned)==u['detach_calls']==u['return_calls']==u['returned']==1 and len(select(18,tag=1,caller=0x838877,arg=int(pre['ai'],0)+0x104))==1 and returned[0]['frame']==end
        checks[f'unit_{index}_no_override']=all(u[k]==0 for k in ('native_move','native_attack','native_add','native_remove','native_stop')) and not any(e['tag']==0 and e['kind'] in (10,12,14,16,18,20,22) and start<=e['frame']<end for e in ev)
        checks[f'unit_{index}_goal_binding']=all(abs(a-b)<.001 for a,b in zip(u['goal'],rq['front_goal' if index==0 else 'support_goal']))
        stable.append(dict(unit_id=u['id'],stop_frame=stop[0]['frame'] if stop else None,frames=[e['frame'] for e in rows],xyz=[xyz(e) for e in rows],gate_frame=gate[0]['frame'] if gate else None,move_frame=move[0]['frame'] if move else None))
        returns.append(dict(unit_id=u['id'],frames=[e['frame'] for e in returned]))
    pairs=[]
    if len(units)==2:
        for a,b in zip(events,events[1:]):
            if a['kind']==b['kind']==3 and a['unit_id']==units[0]['id'] and b['unit_id']==units[1]['id'] and a['frame']==b['frame'] and a['tick']==b['tick'] and a['stage']==b['stage'] and start<=a['frame']<=end:pairs.append((a,b))
    held_ready=[];geometry=[];run=0;max_run=0;ready=0;max_ready=0;seen=set()
    for a,b in pairs:
        if a['frame'] in seen:continue
        seen.add(a['frame']);df=distance(xyz(a),units[0]['goal']);ds=distance(xyz(b),units[1]['goal']);spacing=distance(xyz(a),xyz(b));forward=sum((a[k]-b[k])*(units[0]['goal'][i]-units[0]['initial'][i]) for i,k in enumerate(('x','y')))
        held=a['stage']==1 and a['frame']<=n['support_issued_frame'] and distance(xyz(b),units[1]['hold'])<=15
        ready=ready+1 if held and df<=15 else 0;max_ready=max(max_ready,ready)
        if ready:held_ready.append(a['frame'])
        good=a['stage']==2 and n['support_issued_frame']<=a['frame']<=end and df<=20 and ds<=15 and rq['min_spacing']<=spacing<=rq['max_spacing'] and forward>0
        run=run+1 if good else 0;max_run=max(max_run,run)
        if good:geometry.append(dict(frame=a['frame'],tick=a['tick'],front_distance=df,support_distance=ds,spacing=spacing,forward=forward))
    checks['support_held_front_arrived_before_release']=max_ready>=3
    checks['three_distinct_same_tick_geometries']=max_run>=3 and len({g['frame'] for g in geometry})>=3
    return dict(verified=all(checks.values()),scope='coordinate_force:two_role_staged_advance_only',checks=checks,stable_stop=stable,held_front_ready_frames=held_ready,paired_geometry=geometry,returns=returns,attack_verified=False,raid_verified=False,cooperative_combat_verified=False)


def main():
    raw=SOURCE.read_bytes();r=json.loads(raw);e=json.loads(EVIDENCE.read_text());result=audit(r);directory=ROOT/'tactical/formation-stop-v2'
    actual={key:hashlib.sha256((directory/name).read_bytes()).hexdigest() for key,name in [('native_binary_sha256','bin/TacticalFormationStop2.dll'),('native_host_sha256','bin/tactical_host.exe'),('wrapper_sha256','lease.py'),('native_source_sha256','lease.cpp'),('native_shared_sha256','shared.h')]}
    result['checks']['current_frozen_hashes']=all(r[key]==value for key,value in actual.items())
    result['checks']['evidence_source_binding']=e['source_sha256']==hashlib.sha256(raw).hexdigest() and Path(e['source_report']).resolve()==SOURCE.resolve() and e['source_session_id']==r['session_id'] and e['commander_id']==r['preflight']['commander_id'] and e['module']=='combined_arms' and e['purpose']=='coordinate_force'
    result['checks']['evidence_executor_route']=e['executor_directory']=='formation-stop-v2' and e['stop_schema']==dict(dll='TacticalFormationStop2.dll',restore_mask=127,mapping_prefix='RA3TacticalFormationStop2_',kind='formation',success='two_role_staged_advance_primitive_verified',directory='formation-stop-v2') and all(e[key]==actual[key] for key in ('native_binary_sha256','native_host_sha256'))
    result['verified']=all(result['checks'].values());assert result['verified'],result
    mutants=[]
    bad=copy.deepcopy(r);bad['native']['restore_mask']=31;mutants.append(bad)
    bad=copy.deepcopy(r);bad['units'][1]['returned']=0;mutants.append(bad)
    bad=copy.deepcopy(r)
    for event in bad['events']:
        if event['kind']==3 and event['stage']==2:event['frame']=8188
    mutants.append(bad)
    bad=copy.deepcopy(r)
    for event in bad['events']:
        if event['kind']==3 and event['frame']==8152:event['x']+=50
    mutants.append(bad)
    assert all(not audit(record)['verified'] for record in mutants)
    result.update(source_report=str(SOURCE.relative_to(ROOT)),source_sha256=hashlib.sha256(raw).hexdigest(),current_hashes=actual,negative_cases=len(mutants),game_or_api_access=False)
    target=Path(__file__).with_name('coordinate-force-independent.json');target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(output=str(target),verified=True,scope=result['scope'])))


if __name__=='__main__':main()
