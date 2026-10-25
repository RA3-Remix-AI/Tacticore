"""Offline movement evidence only. Never attaches to a process or issues commands."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct

ROOT=Path(__file__).resolve().parents[2]


def positions(events,issued,returned,target):
    groups=[]
    for event in events:
        if event.get('kind')!=3 or not issued<=event['frame']<returned:continue
        point=tuple(event[key] for key in ('x','y','z'))
        if not all(math.isfinite(number) for number in point):raise ValueError('Nonfinite recorded position')
        if groups and groups[-1]['point']==point:
            groups[-1]['last_frame']=event['frame'];groups[-1]['samples']+=1
        else:groups.append(dict(first_frame=event['frame'],last_frame=event['frame'],point=point,samples=1,distance=math.hypot(point[0]-target[0],point[1]-target[1])))
    return groups


def audit(path):
    raw=path.read_bytes();report=json.loads(raw.decode('utf-8-sig'));native=report['native'];target=native['target']
    issued,returned=native['issued_frame'],native['returned_frame']
    if not 0<issued<=returned:raise ValueError('Missing observed lease window')
    groups=positions(report['events'],issued,returned,target)
    if not groups:raise ValueError('No recorded native lease position samples')
    plateaus=sorted(groups,key=lambda row:row['last_frame']-row['first_frame'],reverse=True)
    arrival=[group for group in groups if group['distance']<=15]
    length=sum(math.dist(a['point'][:2],b['point'][:2]) for a,b in zip(groups,groups[1:]))
    return dict(report=str(path.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),session_id=report['session_id'],object_id=report['preflight']['selected']['object_id'],target=target,issued_frame=issued,returned_frame=returned,lease_frames=returned-issued,move_calls=native['move_calls'],native_move_calls=native['native_move'],reported_arrival_samples=native['arrival_samples'],independent_samples_within_15=sum(group['samples'] for group in arrival),minimum_lease_distance=min(row['distance'] for row in groups),recorded_lease_polyline_length=length,final_lease_position=groups[-1],longest_plateau=plateaus[0],independent_assessment='failed_original_15_radius' if not arrival else 'arrival_samples_require_full_other_guards',capabilities_granted=[])


def image_constants(path):
    raw=path.read_bytes();pe=struct.unpack_from('<I',raw,0x3c)[0];number=struct.unpack_from('<H',raw,pe+6)[0];opt=struct.unpack_from('<H',raw,pe+20)[0];base=struct.unpack_from('<I',raw,pe+52)[0]
    def offset(address):
        for i in range(number):
            header=pe+24+opt+40*i;virtual_size,rva,size,start=struct.unpack_from('<IIII',raw,header+8)
            if rva<=address-base<rva+min(virtual_size,size):return start+address-base-rva
        raise ValueError('VA outside file-backed section')
    return dict(executable_sha256=hashlib.sha256(raw).hexdigest(),move_extra_float=dict(address='0xc0d47c',bytes=raw[offset(0xc0d47c):offset(0xc0d47c)+4].hex(),value=struct.unpack_from('<f',raw,offset(0xc0d47c))[0]),create_path_constants={hex(va):struct.unpack_from('<f',raw,offset(va))[0] for va in (0xbe6200,0xbe667c,0xc0a4e4)})


def audit_formation(path):
    raw=path.read_bytes();report=json.loads(raw.decode('utf-8-sig'));native=report['native'];units=report['units'];result=[]
    for unit in units:
        events=[event for event in report['events'] if event['kind']==3 and event['unit_id']==unit['id'] and native['issued_frame']<=event['frame']<native['returned_frame']]
        distances=[(event['frame'],math.hypot(event['x']-unit['hold'][0],event['y']-unit['hold'][1])) for event in events if event['stage']==1]
        goals=[math.hypot(event['x']-unit['goal'][0],event['y']-unit['goal'][1]) for event in events]
        result.append(dict(object_id=unit['id'],hold=unit['hold'],goal=unit['goal'],last_position=[events[-1][key] for key in ('x','y','z')] if events else None,first_stage1_drift_outside_15=next((frame for frame,distance in distances if distance>15),None),max_stage1_hold_drift=max((distance for _,distance in distances),default=None),minimum_goal_distance=min(goals,default=None),native_move_override_count=unit['native_move']))
    return dict(source_report=str(path.relative_to(ROOT)),source_sha256=hashlib.sha256(raw).hexdigest(),issued_frame=native['issued_frame'],returned_frame=native['returned_frame'],units=result,causality='No new Move hook does not distinguish a previous path from a newly projected path. Stop/path-state observations required.',capabilities_granted=[])


def self_test():
    samples=[dict(kind=3,frame=f,x=x,y=0,z=0) for f,x in [(99,0),(100,20),(101,20),(102,20),(105,0),(106,0)]]
    groups=positions(samples,100,105,[0,0,0])
    assert len(groups)==1 and groups[0]['distance']==20
    assert groups[0]['first_frame']==100 and groups[0]['last_frame']==102 and groups[0]['samples']==3
    # Post-return arrivals must never be credited to the private lease.
    assert not any(group['distance']<=15 for group in groups)
    bad=[dict(kind=3,frame=100,x=float('nan'),y=0,z=0)]
    try:positions(bad,100,105,[0,0,0])
    except ValueError:pass
    else:raise AssertionError('Nonfinite evidence accepted')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--self-test',action='store_true');parser.add_argument('--executable',type=Path,default=Path('E:/RedRar3/Data/RA3_1.12.game'));parser.add_argument('--output',type=Path,default=Path(__file__).with_name('movement-evidence.json'));args=parser.parse_args()
    self_test()
    if args.self_test:print('Movement audit boundary checks passed; no game/API access.');return
    records=[audit(ROOT/'tactical'/'recon'/(name+'-native.json')) for name in ('trial-30b1-01','trial-30b1-03','trial-30b1-06')]
    result=dict(schema_version=1,source='offline_immutable_native_reports_and_file_disassembly',game_process_access=False,commands_issued=0,arrival_radius_unchanged=15,trials=records,static=image_constants(args.executable),conclusion='No common 70-unit stopping radius. Two clipped/stable endpoints differ; the third remains moving until lease expiry. Terrain type and exact path adjustment cause are not proven.')
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    hold_path=ROOT/'acceptance/runs/20261024-234355-commander/formation02.json'
    if hold_path.exists():args.output.with_name('movement-hold-evidence.json').write_text(json.dumps(audit_formation(hold_path),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    ranges=[(0x6eff70,0x6effb9),(0x603a70,0x603ab2),(0x7ee790,0x7ee845),(0x801f90,0x801fe5),(0x7a9580,0x7a95e9),(0x7f51e0,0x7f5250),(0x69d770,0x69d8f0),(0x601850,0x6018a4),(0x6efa70,0x6efab4),(0x54b0a0,0x54b12b),(0x590ca0,0x590cd1),(0x787784,0x787796),(0x787d36,0x787d4c),(0x721c4d,0x721cb2)]
    source=ROOT/'tactical'/'all-text-temporary.txt';lines=[]
    for line in source.open(encoding='utf-8',errors='replace'):
        match=re.match(r'\s*([0-9a-f]+):',line)
        if match and any(start<=int(match[1],16)<end for start,end in ranges):lines.append(line)
    args.output.with_name('movement-disassembly.txt').write_text(''.join(lines),encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),trials=len(records),commands_issued=0,capabilities_granted=[])))


if __name__=='__main__':main()
