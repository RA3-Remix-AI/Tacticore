"""Independent immutable Stop->Move review; no process/native imports or calls."""
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'acceptance/runs/20261024-234355-commander/stop-move01.json'


def audit(report):
    events=report['events'];native=report['native'];pre=report['preflight'];request=report['request']
    start=native['issued_frame'];end=native['returned_frame'];move=native['move_issued_frame'];goal=request['target']
    def select(kind,**fields):return [e for e in events if e['kind']==kind and all(e.get(key)==value for key,value in fields.items())]
    stops=select(23,arg=1,caller=0x787791);gates=select(24);moves=select(10,tag=2);returns=select(14,tag=3)
    boundary=stops[0] if len(stops)==1 else {'seq':0,'frame':0}
    gate=gates[0] if len(gates)==1 else {'seq':0,'frame':0,'x':0,'y':0}
    clean=[]
    for event in select(3):
        if boundary['seq']<event['seq']<gate['seq'] and boundary['frame']<event['frame']<=gate['frame'] and (not clean or event['frame']!=clean[-1]['frame']):clean.append(event)
    clean=clean[-3:]
    stable=len(clean)==3 and all(e['path']==0 and e['sm_flags']&0xffff==0 and e['source']==1 for e in clean)
    stable=stable and all(math.hypot(a['x']-b['x'],a['y']-b['y'])<=1 for a,b in zip(clean,clean[1:])) and math.hypot(clean[-1]['x']-gate['x'],clean[-1]['y']-gate['y'])<=1
    arrival=[e for e in select(3) if move<=e['frame']<=end and (not returns or e['seq']<returns[0]['seq']) and math.hypot(e['x']-goal[0],e['y']-goal[1])<=15 and abs(e['z']-goal[2])<=2]
    checks=dict(raw_finished=report.get('status')=='finished' and report.get('host_exit')==0,clean_restore=native['phase']==3 and native['error']==0 and native['restore_mask']==127 and native['active']==0,session_bound=report['session_id']==pre['session_id']==native['session_id'] and pre['commander_id']==native['commander_id'],command_bound=all(request[key]==native[key] for key in ('command_id','task_id','seq')),event_sequence=[e['seq'] for e in events]==list(range(1,len(events)+1)),monotonic_frames=all(a['frame']<=b['frame'] for a,b in zip(events,events[1:])),identity=all(e['owner']==int(pre['owner'],0) and e['thread']==pre['window_thread'] for e in events),single_stop_facade=len(select(20,tag=4,arg=1))==len(select(21,tag=4))==native['stop_calls']==1,single_actual_stop=len(select(22,arg=1,caller=0x787791))==len(stops)==native['private_stop_calls']==1,three_distinct_clean_stable_frames=bool(stable),ordered_move=len(gates)==len(moves)==1 and boundary['frame']<gate['frame']==move and boundary['seq']<gate['seq']<moves[0]['seq'],single_move_chain=len(moves)==len(select(11,tag=2))==native['move_calls']==1,single_native_transfer=native['detach_calls']==native['return_calls']==native['return_verified']==len(returns)==1,actual_arrival=len(arrival)==native['arrival_samples']==3 and len({e['frame'] for e in arrival})==3,target_unmodified=native['target']==goal,no_override=all(native[key]==0 for key in ('native_move','native_attack','native_add','native_remove')),bounded=0<start<=move<=end<=start+request['lease_frames']+5)
    return dict(primitive_verified=all(checks.values()),checks=checks,stable_frames=[e['frame'] for e in clean],arrival_frames=[e['frame'] for e in arrival],path_was_nonzero_before_stop=bool(select(20)[0]['path']) if select(20) else None,proves_preexisting_nonzero_path_cancellation=False,purpose_capabilities_granted=[])


def main():
    raw=SOURCE.read_bytes();original=json.loads(raw.decode('utf-8-sig'));result=audit(original)
    assert result['primitive_verified']
    mutants=[]
    bad=copy.deepcopy(original);bad['native']['restore_mask']=126;mutants.append(bad)
    bad=copy.deepcopy(original)
    for e in bad['events']:
        if e['kind'] in (22,23):e['caller']=0
    mutants.append(bad)
    bad=copy.deepcopy(original)
    for e in bad['events']:
        if e['kind']==3 and e['frame']==4073:e['x']+=50
    mutants.append(bad)
    bad=copy.deepcopy(original)
    for e in bad['events']:
        if e['kind']==3 and 4083<=e['frame']<=4086:e['frame']=4083
    mutants.append(bad)
    assert all(not audit(record)['primitive_verified'] for record in mutants)
    result.update(source_report=str(SOURCE.relative_to(ROOT)),source_sha256=hashlib.sha256(raw).hexdigest(),independent_negative_cases=len(mutants),game_or_api_access=False)
    target=Path(__file__).with_name('stop-move01-independent.json');target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(target),primitive_verified=result['primitive_verified'],purpose_capabilities_granted=[])))


if __name__=='__main__':main()
